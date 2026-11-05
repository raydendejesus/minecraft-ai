"""The Builder: a tiny GPT trained from scratch, reading and writing one character at a time."""

import os

import torch
import torch.nn as nn
import torch.nn.functional as F

from data import VOCAB, STOI, encode, decode, fmt

HERE = os.path.dirname(os.path.abspath(__file__))
CKPT_PATH = os.path.join(HERE, "builder.pt")

DEFAULT_CONFIG = dict(vocab=len(VOCAB), ctx=1280, dim=256, layers=6, heads=8)


class Block(nn.Module):
    def __init__(self, dim, heads):
        super().__init__()
        self.heads = heads
        self.ln1 = nn.LayerNorm(dim)
        self.qkv = nn.Linear(dim, 3 * dim)
        self.proj = nn.Linear(dim, dim)
        self.ln2 = nn.LayerNorm(dim)
        self.mlp = nn.Sequential(nn.Linear(dim, 4 * dim), nn.GELU(), nn.Linear(4 * dim, dim))

    def forward(self, x):
        B, T, C = x.shape
        q, k, v = self.qkv(self.ln1(x)).split(C, dim=2)
        q, k, v = (t.view(B, T, self.heads, C // self.heads).transpose(1, 2) for t in (q, k, v))
        y = F.scaled_dot_product_attention(q, k, v, is_causal=True)
        x = x + self.proj(y.transpose(1, 2).reshape(B, T, C))
        return x + self.mlp(self.ln2(x))

    def cached(self, x, cache):
        """forward() for writing: keeps every earlier character's keys and values in `cache`, so
        each new character costs the same instead of re-reading the whole answer."""
        B, T, C = x.shape
        q, k, v = self.qkv(self.ln1(x)).split(C, dim=2)
        q, k, v = (t.view(B, T, self.heads, C // self.heads).transpose(1, 2) for t in (q, k, v))
        if cache:
            k, v = torch.cat([cache[0], k], dim=2), torch.cat([cache[1], v], dim=2)
        cache[:] = [k, v]
        y = F.scaled_dot_product_attention(q, k, v, is_causal=T > 1)
        x = x + self.proj(y.transpose(1, 2).reshape(B, T, C))
        return x + self.mlp(self.ln2(x))


class TinyGPT(nn.Module):
    def __init__(self, vocab, ctx, dim, layers, heads):
        super().__init__()
        self.ctx = ctx
        self.tok = nn.Embedding(vocab, dim)
        self.pos = nn.Embedding(ctx, dim)
        self.blocks = nn.ModuleList(Block(dim, heads) for _ in range(layers))
        self.ln = nn.LayerNorm(dim)
        self.head = nn.Linear(dim, vocab, bias=False)
        self.head.weight = self.tok.weight

    def forward(self, idx):
        T = idx.shape[1]
        x = self.tok(idx) + self.pos(torch.arange(T, device=idx.device))
        for b in self.blocks:
            x = b(x)
        return self.head(self.ln(x))

    @torch.no_grad()
    def generate(self, prompt_ids, max_new=1300):
        ids = torch.tensor([prompt_ids], device=self.head.weight.device)
        end = STOI["$"]
        out = []
        for _ in range(max_new):
            if ids.shape[1] >= self.ctx:
                break
            nxt = self(ids)[0, -1].argmax().item()
            if nxt == end:
                break
            out.append(nxt)
            ids = torch.cat([ids, torch.tensor([[nxt]], device=ids.device)], dim=1)
        return out

    @torch.no_grad()
    def generate_fast(self, prompt_ids, max_new=1300):
        """The same answer as generate(), using a key/value cache."""
        dev = self.head.weight.device
        caches = [[] for _ in self.blocks]
        end = STOI["$"]
        out, pos = [], 0
        x = torch.tensor([prompt_ids], device=dev)
        for _ in range(max_new):
            T = x.shape[1]
            if pos + T > self.ctx:
                break
            h = self.tok(x) + self.pos(torch.arange(pos, pos + T, device=dev))
            for b, c in zip(self.blocks, caches):
                h = b.cached(h, c)
            nxt = self.head(self.ln(h[:, -1])).argmax().item()
            pos += T
            if nxt == end:
                break
            out.append(nxt)
            if pos >= self.ctx:
                break
            x = torch.tensor([[nxt]], device=dev)
        return out


class FastWriter:
    """Writes the same answers as TinyGPT.generate() by replaying one character's whole step as a
    recorded CUDA graph. Measured on an idle GPU it was SLOWER than both other writers (it attends
    over the whole fixed-size cache every step), so nothing uses it; kept for bench_speed.py."""

    def __init__(self, model):
        self.m = m = model
        dev = m.head.weight.device
        b0 = m.blocks[0]
        C, H = m.tok.weight.shape[1], b0.heads
        self.k = [torch.zeros(1, H, m.ctx, C // H, device=dev) for _ in m.blocks]
        self.v = [torch.zeros(1, H, m.ctx, C // H, device=dev) for _ in m.blocks]
        self.tok_in = torch.zeros(1, 1, dtype=torch.long, device=dev)
        self.pos_in = torch.zeros(1, dtype=torch.long, device=dev)
        self.slots = torch.arange(m.ctx, device=dev)
        self.graph = None

    def _step(self):
        m, pos = self.m, self.pos_in
        h = m.tok(self.tok_in) + m.pos(pos)[None]
        mask = (self.slots <= pos)[None, None, None, :]
        for b, K, V in zip(m.blocks, self.k, self.v):
            B, T, C = h.shape
            q, k, v = b.qkv(b.ln1(h)).split(C, dim=2)
            q, k, v = (t.view(B, T, b.heads, C // b.heads).transpose(1, 2) for t in (q, k, v))
            K.index_copy_(2, pos, k)
            V.index_copy_(2, pos, v)
            y = F.scaled_dot_product_attention(q, K, V, attn_mask=mask)
            h = h + b.proj(y.transpose(1, 2).reshape(B, T, C))
            h = h + b.mlp(b.ln2(h))
        self.next = m.head(m.ln(h[:, -1])).argmax(-1)

    def _capture(self):
        s = torch.cuda.Stream()
        s.wait_stream(torch.cuda.current_stream())
        with torch.cuda.stream(s):
            for _ in range(2):
                self._step()                  # warm up before recording
        torch.cuda.current_stream().wait_stream(s)
        self.graph = torch.cuda.CUDAGraph()
        with torch.cuda.graph(self.graph):
            self._step()

    @torch.no_grad()
    def generate(self, prompt_ids, max_new=1300):
        m = self.m
        L = len(prompt_ids)
        if L >= m.ctx:
            return []
        if self.graph is None:
            self._capture()
        # read the question in one pass, filling the cache
        x = torch.tensor([prompt_ids], device=self.slots.device)
        h = m.tok(x) + m.pos(self.slots[:L])
        caches = [[] for _ in m.blocks]
        for b, c, K, V in zip(m.blocks, caches, self.k, self.v):
            h = b.cached(h, c)
            K[:, :, :L].copy_(c[0])
            V[:, :, :L].copy_(c[1])
        nxt = m.head(m.ln(h[:, -1])).argmax().item()
        end, out, pos = STOI["$"], [], L
        for _ in range(max_new):
            if nxt == end:
                break
            out.append(nxt)
            if pos + 1 >= m.ctx:
                break                           # the same limit as generate(): memory is full
            self.tok_in.fill_(nxt)
            self.pos_in.fill_(pos)
            self.graph.replay()
            nxt = self.next.item()
            pos += 1
        return out


class Builder:
    """Loads builder.pt and turns a request line into commands."""

    def __init__(self, path=CKPT_PATH):
        self.path = path
        self.model = None
        self.mtime = None
        self.device = "cuda" if torch.cuda.is_available() else "cpu"

    def ready(self):
        return os.path.exists(self.path)

    def _maybe_reload(self):
        mtime = os.path.getmtime(self.path)
        if self.model is None or mtime != self.mtime:
            ck = torch.load(self.path, map_location=self.device)
            m = TinyGPT(**ck["config"]).to(self.device)
            m.load_state_dict(ck["model"])
            m.eval()
            self.model, self.mtime = m, mtime

    @torch.no_grad()
    def choose(self, request, options):
        """The option the model rates most likely as its whole answer, all options scored in one
        pass. For short answers from a known list (a PvP move) this replaces writing letter by
        letter: one step instead of one per letter, and never a move that doesn't exist."""
        self._maybe_reload()
        m = self.model
        seqs = [encode(fmt(request, o)) for o in options]
        start = len(encode(fmt(request))) - 1
        T = max(len(s) for s in seqs)
        x = torch.zeros(len(seqs), T, dtype=torch.long, device=self.device)
        for i, s in enumerate(seqs):
            x[i, :len(s)] = torch.tensor(s)
        logp = torch.log_softmax(m(x[:, :-1]), dim=-1)
        best, best_score = None, None
        for i, s in enumerate(seqs):
            pos = torch.arange(start, len(s) - 1, device=self.device)
            score = logp[i, pos, x[i, pos + 1]].sum().item()
            if best_score is None or score > best_score:
                best, best_score = options[i], score
        return best

    def build(self, request, limit=None):
        self._maybe_reload()
        ids = encode(fmt(request))
        room = self.model.ctx - len(ids) - 1
        # with no limit the answer can be thousands of characters (a whole circuit): there the
        # key/value cache writes twice as fast; on short answers the plain way is a little faster.
        # Both give the same answer letter for letter (bench_speed.py, idle GPU, 2026-11-05)
        write = self.model.generate_fast if limit is None else self.model.generate
        return decode(write(ids, max_new=min(room, limit or room))).strip()
