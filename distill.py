"""Collect the RL-trained specialists' decisions so the Brain can learn from them.

Runs the Planner and the Fight model on lots of situations (some from the teacher's games,
most from their own play) and writes what they decided:
    distill_plan.jsonl, distill_fight.jsonl    each line: {"req": state, "out": choice}

    python distill.py --plan 40000 --fight 40000
"""

import argparse
import json
import os
import random

import torch

import gentle
import planner_data as P
import rl_fight
import rl_planner
from model import HERE, TinyGPT


def load(name):
    ck = torch.load(os.path.join(HERE, name), map_location="cuda")
    m = TinyGPT(**ck["config"]).cuda()
    m.load_state_dict(ck["model"])
    m.eval()
    return m


def write(path, rows):
    with open(path, "w", encoding="utf-8") as f:
        for req, out in rows:
            f.write(json.dumps({"req": req, "out": out}) + "\n")


def collect_plan(model, n):
    rows = []
    while len(rows) < n:
        # its own games (on-policy) ...
        _, trail = rl_planner.play_batch(model, 32, greedy=True)
        rows += [(t, m) for t, m, _ in trail]
        # ... plus teacher-game states, re-labelled with the Planner's own choice
        states = [s for s, _ in P.episode()][:20]
        if states:
            rows += zip(states, rl_planner.choose(model, states, greedy=True))
        print(f"  plan {len(rows)}/{n}", flush=True)
        gentle.step(1.0)
    return rows[:n]


def collect_fight(model, n):
    rows = []
    while len(rows) < n:
        _, _, trail = rl_fight.play(model, [random.randrange(10 ** 9) for _ in range(32)], greedy=True)
        rows += [(t, a) for t, a, _ in trail]
        print(f"  fight {len(rows)}/{n}", flush=True)
        gentle.step(1.0)
    return rows[:n]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--plan", type=int, default=40000)
    ap.add_argument("--fight", type=int, default=40000)
    args = ap.parse_args()
    if not torch.cuda.is_available():
        raise SystemExit("No GPU available (driver reset?). Not writing empty distill files.")
    gentle.setup()
    write(os.path.join(HERE, "distill_plan.jsonl"), collect_plan(load("planner.pt"), args.plan))
    write(os.path.join(HERE, "distill_fight.jsonl"), collect_fight(load("fight.pt"), args.fight))
    print("done")


if __name__ == "__main__":
    main()
