"""Training data for the Brain: one model that does every job, each request tagged by job.

    build: house cobblestone oak_planks spruce_planks 7 4 7 south   (Builder, redstone, logic)
    plan: goal get iron_pickaxe 1 | have oak_log 3 | hunger 12       (Survival Planner)
    fight: hp 8 food 0 hunger full | iron_sword armor iron | ...     (Fight model)
    fight: mobinfo creeper / fight: math hits iron_sword zombie      (fight knowledge)

Building comes from the exact teacher. Planning and fighting come from the RL-trained
specialists (distill_*.jsonl), so what they learned by practicing carries over.
Your corrections for every job are mixed in too.
"""

import json
import os
import random

import data
import fight_data
import planner_data

HERE = os.path.dirname(os.path.abspath(__file__))
MIX = [("build", 0.5), ("plan", 0.25), ("fight", 0.25)]


def _load(name):
    path = os.path.join(HERE, name)
    if not os.path.exists(path):
        return []
    with open(path, encoding="utf-8") as f:
        return [json.loads(l) for l in f if l.strip()]


_distill = {"plan": _load("distill_plan.jsonl"), "fight": _load("distill_fight.jsonl")}
if not _distill["plan"] or not _distill["fight"]:
    raise SystemExit("distill_plan.jsonl / distill_fight.jsonl are missing or empty: run distill.py first")
_answers = {}


def _pick():
    job = random.choices([j for j, _ in MIX], [w for _, w in MIX])[0]
    if job == "build":
        req, out = data.sample(data.load_corrections() if random.random() < 0.01 else [])
    elif job == "plan":
        c = planner_data.load_corrections() if random.random() < 0.01 else []
        if c and random.random() < 0.3:
            row = random.choice(c)
        else:
            row = random.choice(_distill["plan"])
        req, out = row["req"], planner_data.strip_count(row["out"])
    else:
        if random.random() < 0.15:
            req, out = fight_data.math_question()
        else:
            row = random.choice(_distill["fight"])
            req, out = row["req"], row["out"]
    return f"{job}: {req}", out


def sample(corrections, correction_rate=0.0):
    req, out = _pick()
    _answers[req] = out
    if len(_answers) > 300000:
        _answers.clear()
    return req, out


def random_request():
    req, out = _pick()
    _answers[req] = out
    return req


def reference(req):
    return _answers[req]


def load_corrections():
    return []
