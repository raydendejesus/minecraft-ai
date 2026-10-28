"""Train one of the tiny models.

    python train.py                       train the Builder from scratch (~5 min on a 3090)
    python train.py --task planner        train the Survival Planner from scratch
    python train.py --resume [--task ..]  keep training the saved model (after adding corrections)
"""

import argparse
import importlib
import math
import os
import random
import time

import torch
import torch.nn.functional as F

import gentle
from data import encode, fmt
from model import DEFAULT_CONFIG, HERE, TinyGPT

TASKS = {"builder": ("data", "builder.pt"), "planner": ("planner_data", "planner.pt"),
         "merged": ("data", "builder_merged.pt"),   # builder + redstone + logic, one model
         "fight": ("fight_data", "fight.pt"),
         "brain": ("brain_data", "brain.pt")}      # everything merged, learned from the specialists


def make_batch(task, n, corrections, ctx, device):
    seqs, starts = [], []
    for _ in range(n):
        req, out = task.sample(corrections)
        prompt = encode(fmt(req))
        full = encode(fmt(req, out))[:ctx + 1]
        seqs.append(full)
        starts.append(len(prompt) - 1)  # first position whose *next* char is part of the answer
    T = max(len(s) for s in seqs) - 1
    x = torch.zeros(n, T, dtype=torch.long)
    y = torch.full((n, T), -100, dtype=torch.long)  # -100 = ignored by the loss
    for i, s in enumerate(seqs):
        s = torch.tensor(s)
        x[i, :len(s) - 1] = s[:-1]
        y[i, starts[i]:len(s) - 1] = s[starts[i] + 1:]
    return x.to(device), y.to(device)


def evaluate(task, model, corrections, n=60):
    """Exact-match accuracy on fresh random requests, plus on your corrections."""
    from model import Builder
    model.eval()
    b = Builder()
    b.model, b.mtime = model, float("inf")
    b._maybe_reload = lambda: None
    hits = sum(b.build(req) == task.reference(req) for req in (task.random_request() for _ in range(n)))
    fixed = sum(b.build(c["req"]) == c["out"] for c in corrections)
    model.train()
    return hits / n, fixed


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--resume", action="store_true")
    ap.add_argument("--steps", type=int, default=None)
    ap.add_argument("--batch", type=int, default=96)
    ap.add_argument("--task", choices=TASKS, default="builder")
    ap.add_argument("--dim", type=int, default=None, help="model width (default 256)")
    ap.add_argument("--layers", type=int, default=None, help="model depth (default 6)")
    args = ap.parse_args()
    module, ckpt_name = TASKS[args.task]
    task = importlib.import_module(module)
    CKPT_PATH = os.path.join(HERE, ckpt_name)

    gentle.setup()
    device = "cuda" if torch.cuda.is_available() else "cpu"
    if args.resume:
        ck = torch.load(CKPT_PATH, map_location=device)
        config = ck["config"]
        model = TinyGPT(**config).to(device)
        model.load_state_dict(ck["model"])
        steps, lr_max = args.steps or 800, 3e-4
    else:
        config = dict(DEFAULT_CONFIG)
        if args.dim:
            config["dim"] = args.dim
        if args.layers:
            config["layers"] = args.layers
        model = TinyGPT(**config).to(device)
        steps, lr_max = args.steps or 6000, (1e-3 if config["dim"] <= 256 else 6e-4)

    corrections = task.load_corrections()
    params = sum(p.numel() for p in model.parameters())
    print(f"{args.task}: {params / 1e6:.2f}M parameters on {device}, {steps} steps, "
          f"{len(corrections)} corrections from you", flush=True)

    opt = torch.optim.AdamW(model.parameters(), lr=lr_max, weight_decay=0.05, betas=(0.9, 0.95))
    warmup = min(200, steps // 10)
    t0 = time.time()
    for step in range(1, steps + 1):
        t_step = time.time()
        lr =lr_max * min(1, step / warmup) * (0.1 + 0.9 * 0.5 * (1 + math.cos(math.pi * step / steps)))
        for g in opt.param_groups:
            g["lr"] = lr
        x, y = make_batch(task, args.batch, corrections, config["ctx"], device)
        with torch.autocast(device_type="cuda", dtype=torch.bfloat16, enabled=device == "cuda"):
            logits = model(x)
        loss = F.cross_entropy(logits.float().view(-1, logits.size(-1)), y.view(-1), ignore_index=-100)
        opt.zero_grad(set_to_none=True)
        loss.backward()
        torch.nn.utils.clip_grad_norm_(model.parameters(), 1.0)
        opt.step()
        gentle.step(time.time() - t_step)

        if step % 100 == 0:
            print(f"step {step}/{steps}  loss {loss.item():.4f}  {time.time() - t0:.0f}s", flush=True)
        if step % 1000 == 0 or step == steps:
            acc, fixed = evaluate(task, model, corrections)
            print(f"  >> accuracy on new requests: {acc:.0%}   corrections learned: "
                  f"{fixed}/{len(corrections)}", flush=True)
            torch.save({"config": config, "model": model.state_dict()}, CKPT_PATH)

    print(f"done, saved {ckpt_name}", flush=True)


if __name__ == "__main__":
    random.seed()
    main()
