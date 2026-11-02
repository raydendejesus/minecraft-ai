"""Prove the repeat shorthand rebuilds every machine exactly, block for block."""

import redstone_lib as R

CASES = {"ram 2 2": R.ram(2, 2)[0], "ram 4 8": R.ram(4, 8)[0], "ram 6 8": R.ram(6, 8)[0], "ram 7 8": R.ram(7, 8)[0],
         "counter 4": R.counter(4)[0], "alu 4": R.alu(4)[0]}
for name, parts in CASES.items():
    text = R.to_loops(parts)
    back = set(R.from_loops(text))
    print(f"{name:10s} {len(parts):6d} parts  {len(text):5d} chars  {'EXACT' if back == set(parts) else 'DIFFERENT'}", flush=True)
