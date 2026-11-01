"""Check the ALU on the lab server: adding and subtracting.

    python test_alu.py 2      every combination, adding and subtracting
    python test_alu.py 4      a spread of 4-bit sums and differences

Subtraction wraps around like a real CPU: 3 - 5 on 4 bits is 14. The top lamp is the carry,
which is on when no borrow was needed.
"""

import random
import sys
import time

import redstone_lib as R
from lab import FLOOR_Y, Lab

Y = FLOOR_Y + 1
BASE = (8, 12)
OFF = R.lever(0, 0)[3]


def main():
    bits = int(sys.argv[1]) if len(sys.argv) > 1 else 2
    parts, inputs, outs = R.alu(bits)
    commands = R.to_fills(parts, (BASE[0], Y, BASE[1]))
    top = 1 << bits
    print(f"{bits}-bit ALU: {len(parts)} parts in {len(commands)} commands, x {min(p[0] for p in parts)} to "
          f"{max(p[0] for p in parts)}, z up to {max(p[2] for p in parts)}", flush=True)
    if bits <= 2:
        cases = [(a, b, s) for s in (0, 1) for a in range(top) for b in range(top)]
    else:
        random.seed(5)
        cases = [(15, 1, 0), (0, 1, 1), (7, 7, 1), (15, 15, 1), (3, 5, 1), (5, 3, 1), (8, 1, 1), (0, 0, 1)]
        cases += [(random.randrange(top), random.randrange(top), random.randrange(2)) for _ in range(8)]
    with Lab(verbose="-v" in sys.argv) as lab:
        for c in commands:
            lab.cmd(c, wait=0.02)
        lab.sync()
        time.sleep(4)
        good = 0
        for a, b, sub in cases:
            for i in range(bits):
                for name, value in ((f"A{i}", a), (f"B{i}", b)):
                    x, z = inputs[name]
                    block = "redstone_block" if value >> i & 1 else OFF
                    lab.cmd(f"setblock {BASE[0] + x} {Y} {BASE[1] + z} {block}", wait=0.02)
            x, z = inputs["SUB"]
            lab.cmd(f"setblock {BASE[0] + x} {Y} {BASE[1] + z} {'redstone_block' if sub else OFF}", wait=0.02)
            time.sleep(5 + bits * 3)
            lit = [lab.block_at(BASE[0] + x, Y, BASE[1] + z, "lit_redstone_lamp") for x, z in outs]
            got = sum(1 << i for i, v in enumerate(lit[:bits]) if v)
            want = (a - b) % top if sub else (a + b) % top
            ok = got == want
            good += ok
            print(f"  {a:2d} {'-' if sub else '+'} {b:2d} = {got:2d}  {'ok' if ok else 'WRONG, should be ' + str(want)}", flush=True)
    print(f"{good}/{len(cases)} correct")


if __name__ == "__main__":
    main()
