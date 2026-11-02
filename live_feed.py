"""Live snapshots from whatever model is training, for the Neural Viewer page.

Training scripts call publish() after each step. At most every few seconds it runs the model on
the example it's practicing and writes what it answered and how its neurons fired to
live_state.json. Anything going wrong here is swallowed, so it can never stop training.
"""

import json
import math
import os
import time

import torch
import torch.nn.functional as F

from data import STOI, VOCAB, decode, encode, fmt

HERE = os.path.dirname(os.path.abspath(__file__))
STATE = os.path.join(HERE, "live_state.json")
EVERY = 3.0                # seconds between snapshots
_last = 0.0


@torch.no_grad()
def neurons(m, ids):
    """Forward pass that records every neuron's activity at the last character, per layer."""
    dev = m.head.weight.device
    idx = torch.tensor([ids], device=dev)
    T = idx.shape[1]
    x = m.tok(idx) + m.pos(torch.arange(T, device=dev))
    acts = []
    for b in m.blocks:
        C = x.shape[-1]
        q, k, v = b.qkv(b.ln1(x)).split(C, dim=2)
        q, k, v = (t.view(1, T, b.heads, C // b.heads).transpose(1, 2) for t in (q, k, v))
        y = F.scaled_dot_product_attention(q, k, v, is_causal=True)
        x = x + b.proj(y.transpose(1, 2).reshape(1, T, C))
        hidden = b.mlp[1](b.mlp[0](b.ln2(x)))
        x = x + b.mlp[2](hidden)
        acts.append(hidden[0, -1])
    return acts


def grid(a):
    """One layer's neurons as a string of digits, 0 (silent) to 9 (firing hard)."""
    return "".join(map(str, (a.clamp(0, 2.5) / 2.5 * 9).round().int().tolist()))


def publish(model, job, step, total, loss, sample, done=False):
    """sample() returns (request, correct answer) for the example to show."""
    global _last
    now = time.time()
    if now - _last < EVERY and not done:
        return
    _last = now
    try:
        req, answer = sample()
        ids = encode(fmt(req))[: model.ctx - 2]
        limit = min(300, model.ctx - len(ids) - 1)
        out = model.generate(ids, max_new=limit)
        typed = decode(out)
        # neurons at up to 24 points through the answer, so the page can animate them as it types
        points = sorted({round(i * len(out) / 23) for i in range(24)}) if out else [0]
        frames = []
        for k in points:
            acts = neurons(model, ids + out[:k])
            frames.append({"at": k, "grids": [grid(a) for a in acts],
                           "firing": [round(float((a > 0.1).float().mean()), 3) for a in acts]})
        cut_short = len(out) >= limit
        right = answer.startswith(typed) if cut_short else typed.strip() == answer.strip()
        if req.startswith("design "):              # any design that works is right
            import design_data
            right = design_data.works(req, typed)
        state = {"job": job, "step": step, "total": total, "loss": round(float(loss), 4), "time": now,
                 "request": req, "answer": answer, "typed": typed, "right": right, "frames": frames,
                 "params": sum(p.numel() for p in model.parameters()), "done": done}
        tmp = STATE + ".tmp"
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(state, f)
        os.replace(tmp, STATE)
    except Exception:
        pass
