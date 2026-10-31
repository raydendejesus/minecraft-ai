"""Neural Viewer: watch the trained models think, on a local web page.

    python neural_view.py        then open http://localhost:8842

Runs a real model on your text and records, for every character it writes: how active the
neurons in each layer were, which earlier characters each layer paid attention to, and its top
guesses for the next character. Pathways are computed from the model's real weights.

"Neurons" here are the 1,024 units in the middle of each layer (the GELU activations). Runs on
the CPU with 2 threads, so it never touches the GPU.
"""

import json
import math
import os
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

import torch
import torch.nn.functional as F

from data import STOI, VOCAB, encode, fmt
from model import HERE, TinyGPT

PORT = 8842
SHOWN = 20          # neurons drawn per layer
BRAINS = {
    "builder": ("Builder", "builder.pt", "house cobblestone oak_planks spruce_planks 7 4 7 south"),
    "planner": ("Survival Planner", "planner.pt",
                "goal build iron_helmet 1 iron_boots 1 cobblestone 300 | have oak_log 3 wooden_pickaxe 1 | hunger 15"),
    "fight": ("Fight model", "fight.pt",
              "hp 8 food 2 hunger full sprint | iron_sword armor iron shield bow 12 pickaxe | creeper 3 hp20 fuse | zombie 6 hp20"),
}
torch.set_num_threads(2)
_models = {}


def load(key):
    if key not in _models:
        path = os.path.join(HERE, BRAINS[key][1])
        ck = torch.load(path, map_location="cpu")
        m = TinyGPT(**ck["config"])
        m.load_state_dict(ck["model"])
        m.eval()
        _models[key] = (m, ck["config"], os.path.getsize(path))
    return _models[key]


def size_info(key):
    m, cfg, file_size = load(key)
    def count(mods):
        return sum(p.numel() for mod in mods for p in mod.parameters())
    blocks = list(m.blocks)
    groups = [
        ("Character memory", m.tok.weight.numel()),
        ("Position memory", m.pos.weight.numel()),
        ("Attention", count([b.qkv for b in blocks] + [b.proj for b in blocks])),
        ("Neurons (thinking)", count([b.mlp for b in blocks])),
        ("Normalizers", count([b.ln1 for b in blocks] + [b.ln2 for b in blocks] + [m.ln])),
    ]
    return {"name": BRAINS[key][0], "params": sum(p.numel() for p in m.parameters()), "groups": groups,
            "file_mb": file_size / 1e6, "layers": cfg["layers"], "heads": cfg["heads"], "dim": cfg["dim"],
            "neurons_per_layer": cfg["dim"] * 4, "neurons_total": cfg["dim"] * 4 * cfg["layers"],
            "context": cfg["ctx"], "vocab": cfg["vocab"]}


@torch.no_grad()
def trace(m, ids):
    """One forward pass that records the last position's neurons and attention in every layer."""
    idx = torch.tensor([ids])
    T = idx.shape[1]
    x = m.tok(idx) + m.pos(torch.arange(T))
    mask = torch.triu(torch.ones(T, T, dtype=torch.bool), 1)
    acts, attn = [], []
    for b in m.blocks:
        C = x.shape[-1]
        q, k, v = b.qkv(b.ln1(x)).split(C, dim=2)
        q, k, v = (t.view(1, T, b.heads, C // b.heads).transpose(1, 2) for t in (q, k, v))
        w = (q @ k.transpose(-2, -1)) / math.sqrt(q.shape[-1])
        w = w.masked_fill(mask, float("-inf")).softmax(-1)
        y = (w @ v).transpose(1, 2).reshape(1, T, C)
        x = x + b.proj(y)
        hidden = b.mlp[1](b.mlp[0](b.ln2(x)))
        x = x + b.mlp[2](hidden)
        acts.append(hidden[0, -1].clone())
        attn.append(w[0, :, -1, :].mean(0).clone())
    return m.head(m.ln(x))[0, -1], acts, attn


def run(key, text, max_new):
    m, cfg, _ = load(key)
    prompt = encode(fmt(text))[: cfg["ctx"] - 2]
    ids = list(prompt)
    frames, written = [], []
    usable = cfg["vocab"]
    for _ in range(max_new):
        if len(ids) >= cfg["ctx"]:
            break
        logits, acts, attn = trace(m, ids)
        probs = F.softmax(logits, -1)
        top = probs.topk(6)
        nxt = int(logits.argmax())
        frames.append({"acts": acts, "attn": attn,
                       "guess": [[VOCAB[i], round(float(p), 4)] for p, i in zip(top.values, top.indices)],
                       "char": VOCAB[nxt], "chosen": nxt, "pos": len(ids) - 1})
        if nxt == STOI["$"]:
            break
        ids.append(nxt)
        written.append(VOCAB[nxt])

    layers = len(m.blocks)
    # the same most-active neurons stay on screen for the whole run, so you can watch them change
    stack = [torch.stack([f["acts"][L] for f in frames]) for L in range(layers)]
    picks = [s.abs().max(0).values.topk(SHOWN).indices for s in stack]

    # pathways: how strongly a neuron in one layer drives a neuron in the next (real weights)
    links = []
    for L in range(layers - 1):
        out_w = m.blocks[L].mlp[2].weight[:, picks[L]]
        in_w = m.blocks[L + 1].mlp[0].weight[picks[L + 1], :]
        M = in_w @ out_w
        links.append([[round(float(v), 4) for v in row] for row in M.T])

    out_frames = []
    scale = [float(s[:, p].abs().max()) or 1.0 for s, p in zip(stack, picks)]
    for f in frames:
        out_frames.append({
            "char": "⏎" if f["char"] == "\n" else "■" if f["char"] == "$" else f["char"],
            "guess": [["⏎" if c == "\n" else "■" if c == "$" else "␠" if c == " " else c, p] for c, p in f["guess"]],
            "pos": f["pos"],
            "layers": [{
                "acts": [round(float(f["acts"][L][i]) / scale[L], 3) for i in picks[L]],
                "firing": round(float((f["acts"][L] > 0.1).float().mean()), 3),
                "attn": [round(float(a), 3) for a in f["attn"][L]],
            } for L in range(layers)],
        })
    shown_prompt = "".join("⏎" if VOCAB[i] == "\n" else VOCAB[i] for i in prompt)
    return {"prompt": shown_prompt, "written": written, "frames": out_frames, "links": links,
            "ids": [[int(i) for i in p] for p in picks], "size": size_info(key)}


class Handler(BaseHTTPRequestHandler):
    def log_message(self, *a):
        pass

    def _send(self, body, kind="application/json", code=200):
        self.send_response(code)
        self.send_header("Content-Type", kind)
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self):
        if self.path == "/":
            with open(os.path.join(HERE, "neural.html"), "rb") as f:
                self._send(f.read(), "text/html; charset=utf-8")
        elif self.path == "/api/brains":
            have = {k: {"name": v[0], "example": v[2]} for k, v in BRAINS.items()
                    if os.path.exists(os.path.join(HERE, v[1]))}
            self._send(json.dumps(have).encode())
        else:
            self._send(b"{}", code=404)

    def do_POST(self):
        n = int(self.headers.get("Content-Length") or 0)
        req = json.loads(self.rfile.read(n) or b"{}")
        try:
            out = run(req["brain"], req.get("text", "")[:400], min(int(req.get("max_new", 80)), 200))
            self._send(json.dumps(out).encode())
        except Exception as e:
            self._send(json.dumps({"error": str(e)}).encode(), code=500)


if __name__ == "__main__":
    print(f"Neural Viewer running at http://localhost:{PORT}")
    ThreadingHTTPServer(("127.0.0.1", PORT), Handler).serve_forever()
