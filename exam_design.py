"""The design exam: logic goals the model has never seen, scored by whether its design works.

    python exam_design.py designer.pt 2000

Every goal here was locked away from training. A design passes if it really produces the requested
truth table, whatever it looks like. Also reports how close designs are to the shortest possible.
"""

import random
import sys

import design_data as D
from model import Builder

path = sys.argv[1] if len(sys.argv) > 1 else "designer.pt"
n = int(sys.argv[2]) if len(sys.argv) > 2 else 2000
random.seed(4242)
ai = Builder(path)
goals = random.sample([f for f in range(65536) if D.is_exam(f)], n)
passed, same_size, extra, shown = 0, 0, 0, []
by_size = {}
for i, f in enumerate(goals):
    req = D.request(f)
    got = ai.build(req, limit=160)
    ok = D.works(req, got)
    best = D.gates(D.answer(f))
    row = by_size.setdefault(best, [0, 0])
    row[1] += 1
    if ok:
        passed += 1
        row[0] += 1
        same_size += D.gates(got) <= best
        extra += max(0, D.gates(got) - best)
    if len(shown) < 5:
        shown.append((req, got[:70], ok))
    if (i + 1) % 500 == 0:
        print(f"  {i + 1}/{n}: {passed / (i + 1):.1%} working so far", flush=True)
print(f"Locked-away goals solved: {passed}/{n} ({passed / n:.1%})")
if passed:
    print(f"Of those, as short as the best possible: {same_size}/{passed}; average extra gates: {extra / passed:.2f}")
for size in sorted(by_size):
    good, total = by_size[size]
    print(f"  goals needing {size} gates: {good}/{total}")
for req, got, ok in shown:
    print(f"  {req} > {got}  {'works' if ok else 'wrong'}")
