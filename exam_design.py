"""The design exam: logic goals the model has never seen, scored by whether its design works.

    python exam_design.py designer.pt

Every goal here was locked away from training. A design passes if it really produces the requested
truth table, whatever it looks like.

Goals are grouped by how hard they are (the fewest gates any design needs, 0-7). Each level is
tested on its own: every locked-away goal for the small levels, 400 for the big ones. To pass, EVERY
level has to reach 95%, so a weak spot can't hide inside a good average.
"""

import random
import sys

import design_data as D
import live_feed
from model import Builder

PASS = 95.0
PER_LEVEL = 400

path = sys.argv[1] if len(sys.argv) > 1 else "designer.pt"
random.seed(4242)
ai = Builder(path)
levels = {}
for f in range(65536):
    if D.is_exam(f):
        levels.setdefault(D.gates(D.answer(f)), []).append(f)
passed_all, lowest, shortest, solved, tried, shown = True, (101.0, None), 0, 0, 0, []
EXPECTED = sum(min(len(v), PER_LEVEL) for v in levels.values())
ai._maybe_reload()                         # so the live view can use the model right away
results = {}
for size in sorted(levels):
    goals = levels[size] if len(levels[size]) <= PER_LEVEL else random.sample(levels[size], PER_LEVEL)
    good = 0
    for f in goals:
        req = D.request(f)
        got = ai.build(req, limit=160)
        tried_so_far = tried + goals.index(f) + 1
        live_feed.publish(ai.model, "design exam", tried_so_far, EXPECTED, None,
                          lambda: (req, D.answer(int(req.split()[1], 2))))
        if D.works(req, got):
            good += 1
            shortest += D.gates(got) <= size
        elif len(shown) < 6:
            shown.append((req, got[:70]))
    pct = 100 * good / len(goals)
    results[size] = (good, len(goals), pct)
    solved, tried = solved + good, tried + len(goals)
    passed_all &= pct >= PASS
    if pct < lowest[0]:
        lowest = (pct, size)
    print(f"  goals needing {size} gates: {good}/{len(goals)} ({pct:.1f}%) {'PASS' if pct >= PASS else 'not yet'}", flush=True)

print(f"Locked-away goals solved: {solved}/{tried} ({100 * solved / tried:.1f}%)")
print(f"Of those, as short as the best possible: {shortest}/{solved}")
print(f"Every level at {PASS:.0f}%: {'YES' if passed_all else 'NO'} (lowest {lowest[0]:.1f}% at {lowest[1]} gates)")
for req, got in shown:
    print(f"  missed: {req} > {got}")
