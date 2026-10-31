"""Ask a Builder model for every circuit and compare it to the lab-verified design, block by block.

    python check_circuits.py builder_merged.pt
"""

import sys

import data
from model import Builder

b = Builder(sys.argv[1] if len(sys.argv) > 1 else "builder_merged.pt")
requests = [f"redstone {d}" for d in data.REDSTONE_DESIGNS] + [f"redstone ram {n}" for n in range(1, 9)]
good = 0
for req in requests:
    want = data.reference(req).strip()
    got = b.build(req)
    ok = got == want
    good += ok
    print(f"  {req:22s} {len(want):5d} chars  {'exact match' if ok else 'DIFFERENT'}", flush=True)
print(f"{good}/{len(requests)} circuits exact")
