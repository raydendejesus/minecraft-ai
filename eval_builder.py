"""Score a Builder model skill by skill on fresh requests.

    python eval_builder.py builder_merged.pt 500
"""

import collections
import random
import sys

import data
from model import Builder

path = sys.argv[1] if len(sys.argv) > 1 else "builder_merged.pt"
n = int(sys.argv[2]) if len(sys.argv) > 2 else 500
random.seed(2026)
b = Builder(path)
right, total, misses = collections.Counter(), collections.Counter(), {}
for i in range(n):
    req = data.random_request()
    op = req.split()[0]
    if op == "redstone":
        op = "redstone " + req.split()[1]
    got = b.build(req)
    total[op] += 1
    if got == data.reference(req).strip():
        right[op] += 1
    else:
        misses.setdefault(op, (req, got[:90], data.reference(req)[:90]))
    if (i + 1) % 100 == 0:
        print(f"  {i + 1}/{n}", flush=True)

print(f"\nOverall: {sum(right.values())}/{n} ({sum(right.values()) / n:.1%})\n")
for op in sorted(total, key=lambda o: right[o] / total[o]):
    print(f"  {op:22s} {right[op]:3d}/{total[op]:3d}  {right[op] / total[op]:.0%}")
print("\nExample misses:")
for op, (req, got, want) in list(misses.items())[:8]:
    print(f"  {req[:70]}\n    typed : {got!r}\n    answer: {want!r}")
