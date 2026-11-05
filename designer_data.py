"""Lessons for the bigger model: everything the Builder knows, plus designing circuits.

The training log scores it on locked-away design goals only, and a design counts when it works,
so that number shows real problem solving rather than memory.
"""

import json
import os
import random

os.environ["MCAI_RAM"] = "1"          # RAM sticks are part of its lessons

import data
import design_data as D

EVAL_LIMIT = 160                      # characters allowed for an answer during the training log
DESIGN_SHARE = 0.6
CIRCUITS = os.path.join(os.path.dirname(os.path.abspath(__file__)), "circuit_lessons.jsonl")
FIXES = os.path.join(os.path.dirname(CIRCUITS), "circuit_corrections.jsonl")
_levels = None
_circuits = None
_fixes = None
if os.path.exists(CIRCUITS):
    LONG_EVERY = 2                    # circuits joined the long lessons, so they get more turns


def machine_sample():
    """A long lesson: a whole machine, or (once circuit_lessons.jsonl exists) two times in three a
    circuit for a logic formula, built from blocks. A third of those circuits are ones it got wrong
    (circuit_corrections.jsonl), so its mistakes get extra practice."""
    global _circuits, _fixes
    if _circuits is None:
        _circuits, _fixes = [], []
        if os.path.exists(CIRCUITS):
            with open(CIRCUITS, encoding="utf-8") as f:
                _circuits = [tuple(json.loads(line)) for line in f]
        if os.path.exists(FIXES):
            with open(FIXES, encoding="utf-8") as f:
                _fixes = [tuple(json.loads(line)) for line in f]
    if _circuits and random.random() < 2 / 3:
        if _fixes and random.random() < 1 / 3:
            return random.choice(_fixes)
        if random.random() < 0.5:                  # half the time every circuit size gets an equal share
            sizes = _circuit_sizes()
            return random.choice(sizes[random.choice(sorted(sizes))])
        return random.choice(_circuits)
    return data.machine_sample()


_sizes = None


def _circuit_sizes():
    """Circuit lessons grouped by how many and / or / xor gates the formula has. Picked at random,
    only about 1 in 2,000 circuits has no gates at all, and after the lessons changed the AI built a
    two-gate circuit for "b", a single wire to the lamp (the same gap design practice once had)."""
    global _sizes
    if _sizes is None:
        _sizes = {}
        for req, out in _circuits:
            words = req.split()[2:]
            n = sum(w.strip("()") in ("and", "or", "xor", "nand", "nor") for w in words)
            _sizes.setdefault(min(n, 7), []).append((req, out))
    return _sizes


def practice_levels():
    """Practice goals grouped by difficulty, locked-away exam goals left out. Picked at random from
    all 65,536, only about 1 lesson in 1,000 needs 0 or 1 gates, so the simplest goals were barely
    practiced and the exam showed it (0% and 56% on them)."""
    global _levels
    if _levels is None:
        _levels = {}
        for f in range(65536):
            if not D.is_exam(f):
                _levels.setdefault(D.gates(D.answer(f)), []).append(f)
    return _levels


def sample(corrections, correction_rate=0.0):
    if random.random() < DESIGN_SHARE:
        if random.random() < 0.5:     # half the time, every difficulty level gets an equal share
            levels = practice_levels()
            f = random.choice(levels[random.choice(sorted(levels))])
        else:
            f = D.random_function()
        return D.request(f), D.answer(f)
    return data.sample([])


def random_request():
    return D.request(D.random_function(exam=True))


def correct(req, got):
    return D.works(req, got)


def reference(req):
    return D.answer(int(req.split()[1], 2))


def load_corrections():
    return []
