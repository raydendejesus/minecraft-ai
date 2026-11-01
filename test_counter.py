"""Check the program counter on the lab server: pulse the clock and watch it count.

    python test_counter.py 1      one bit: should flip on every pulse
    python test_counter.py 4      4 bits: should count 1, 2, 3 ... 15, 0
"""

import sys
import time

import redstone_lib as R
from lab import FLOOR_Y, Lab

Y = FLOOR_Y + 1
BASE = (4, 10)
OFF = R.lever(0, 0)[3]


def main():
    bits = int(sys.argv[1]) if len(sys.argv) > 1 else 1
    parts, clock, outs = R.counter(bits)
    commands = R.to_fills(parts, (BASE[0], Y, BASE[1]))
    pulses = 4 if bits == 1 else 18
    print(f"{bits}-bit counter: {len(parts)} parts in {len(commands)} commands", flush=True)
    with Lab() as lab:
        for c in commands:
            lab.cmd(c, wait=0.02)
        lab.sync()
        time.sleep(3)
        x, z = clock

        def value():
            lit = [lab.block_at(BASE[0] + a, Y, BASE[1] + b, "lit_redstone_lamp") for a, b in outs]
            return sum(1 << i for i, v in enumerate(lit) if v)

        print("  woke up at:", value(), flush=True)
        reset = (BASE[0] - 2, Y, BASE[1] - 4)
        lab.cmd(f"setblock {reset[0]} {reset[1]} {reset[2]} redstone_block", wait=0.05)
        time.sleep(3)
        lab.cmd(f"setblock {reset[0]} {reset[1]} {reset[2]} {OFF}", wait=0.05)
        time.sleep(3)
        print("  after RESET:", value(), flush=True)
        good = 0
        for n in range(1, pulses + 1):
            lab.cmd(f"setblock {BASE[0] + x} {Y} {BASE[1] + z} redstone_block", wait=0.05)
            time.sleep(1.5)
            lab.cmd(f"setblock {BASE[0] + x} {Y} {BASE[1] + z} {OFF}", wait=0.05)
            time.sleep(1 + bits)
            got, want = value(), n % (1 << bits)
            good += got == want
            print(f"  pulse {n:2d}: count {got:2d}  {'ok' if got == want else 'WRONG, should be ' + str(want)}", flush=True)

        # RESET has to clear a real value: every bit on (15) is the hardest case
        while value() != (1 << bits) - 1:
            lab.cmd(f"setblock {BASE[0] + x} {Y} {BASE[1] + z} redstone_block", wait=0.05)
            time.sleep(1.5)
            lab.cmd(f"setblock {BASE[0] + x} {Y} {BASE[1] + z} {OFF}", wait=0.05)
            time.sleep(1 + bits)
        before = value()
        lab.cmd(f"setblock {reset[0]} {reset[1]} {reset[2]} redstone_block", wait=0.05)
        time.sleep(4)
        lab.cmd(f"setblock {reset[0]} {reset[1]} {reset[2]} {OFF}", wait=0.05)
        time.sleep(5)
        after = value()
        print(f"  RESET from {before}: now {after}  {'ok' if after == 0 else 'WRONG'}", flush=True)
    print(f"{good}/{pulses} correct, reset {'ok' if after == 0 else 'FAILED'}")


if __name__ == "__main__":
    main()
