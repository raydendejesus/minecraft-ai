"""Build an n-bit adder on the lab server and check it really adds.

    python test_adder.py 2      every combination of two 2-bit numbers
    python test_adder.py 4      a spread of 4-bit sums, including the longest carry chains
"""

import random
import sys
import time

import redstone_lib as R
from lab import FLOOR_Y, Lab

Y = FLOOR_Y + 1
BASE = (2, 4)
OFF = R.lever(0, 0)[3]


def main():
    bits = int(sys.argv[1]) if len(sys.argv) > 1 else 4
    parts, inputs, outs = R.adder(bits)
    print(f"{bits}-bit adder: {len(parts)} parts, reaches x={max(p[0] for p in parts)} z={max(p[2] for p in parts)}, "
          f"wire levels up to y={max(p[1] for p in parts)}", flush=True)
    top = 1 << bits
    if bits <= 2:
        cases = [(a, b) for a in range(top) for b in range(top)]
    else:
        random.seed(4)
        cases = [(0, 0), (top - 1, 1), (top - 1, top - 1), (1, top - 1), (5, 10), (10, 5)]
        cases += [(random.randrange(top), random.randrange(top)) for _ in range(10)]
    with Lab() as lab:
        for x, y, z, b in parts:
            lab.cmd(f"setblock {BASE[0] + x} {Y + y} {BASE[1] + z} {b}", wait=0.02)
        time.sleep(3)
        good = 0
        for a, b in cases:
            for i in range(bits):
                for name, value in ((f"A{i}", a), (f"B{i}", b)):
                    x, z = inputs[name]
                    block = "redstone_block" if value >> i & 1 else OFF
                    lab.cmd(f"setblock {BASE[0] + x} {Y} {BASE[1] + z} {block}", wait=0.02)
            time.sleep(4 + bits * 3)            # carries ripple through one adder at a time
            lit = [lab.block_at(BASE[0] + x, Y, BASE[1] + z, "lit_redstone_lamp") for x, z in outs]
            got = sum(1 << i for i, v in enumerate(lit) if v)
            ok = got == a + b
            good += ok
            print(f"  {a:2d} + {b:2d} = {got:2d}  {'ok' if ok else 'WRONG, should be ' + str(a + b)}", flush=True)
    print(f"{good}/{len(cases)} sums correct")


if __name__ == "__main__":
    main()
