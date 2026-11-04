"""Mark the designer's circuit homework: it writes circuits for practice formulas (never a locked
exam goal), and every one that can't be read or has two signals' wires touching (a short) gets
the teacher's circuit added to circuit_corrections.jsonl, which designer_data mixes into its
practice more often. No lab needed: circuit.shorts() agreed with the lab on every circuit.

    python circuit_corrections.py designer.pt 120
"""

import json
import os
import random
import sys

import circuit as C
import design_data as D
from model import Builder

HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(HERE, "circuit_corrections.jsonl")
KEEP = 2000                     # newest corrections kept


def main():
    path = sys.argv[1] if len(sys.argv) > 1 else "designer.pt"
    n = int(sys.argv[2]) if len(sys.argv) > 2 else 120
    random.seed()
    levels = {}
    for f in range(65536):
        if not D.is_exam(f):
            levels.setdefault(D.gates(D.answer(f)), []).append(D.answer(f)[2:])
    ai = Builder(path)
    wrong, tally = [], {}
    for i in range(n):
        g = sorted(levels)[i % len(levels)]               # every size equally
        expr = random.choice(levels[g])
        try:
            teacher = C.lesson(expr)
        except RuntimeError:
            continue
        text = ai.build(f"redstone circuit {expr}")
        try:
            C.inputs_and_output(C.from_steps(text))
            bad = bool(C.shorts(text))
        except Exception:
            bad = True
        right, total = tally.get(g, (0, 0))
        tally[g] = (right + (not bad), total + 1)
        if bad:
            wrong.append([f"redstone circuit {expr}", teacher])
    old = []
    if os.path.exists(OUT):
        with open(OUT, encoding="utf-8") as f:
            old = [json.loads(line) for line in f]
    with open(OUT, "w", encoding="utf-8") as f:
        for x in (old + wrong)[-KEEP:]:
            f.write(json.dumps(x) + "\n")
    print("clean circuits by size: " + "  ".join(f"{g}:{r}/{t}" for g, (r, t) in sorted(tally.items())))
    print(f"{len(wrong)} corrections added ({min(len(old) + len(wrong), KEEP)} kept)")


if __name__ == "__main__":
    main()
