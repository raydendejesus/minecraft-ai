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

    def build(self, request):
        self._maybe_reload()
        return decode(self.model.generate(encode(fmt(request)))).strip()
