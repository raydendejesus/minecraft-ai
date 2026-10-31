"""Check an address decoder on the lab server: every address must light exactly its own line.

    python test_decoder.py 2
    python test_decoder.py 4
"""

import sys
import time

import redstone_lib as R
from lab import FLOOR_Y, Lab

Y = FLOOR_Y + 1
BASE = (2, 8)
OFF = R.lever(0, 0)[3]


def main():
    bits = int(sys.argv[1]) if len(sys.argv) > 1 else 2
    parts, inputs, outs = R.decoder(bits)
    print(f"{bits}-bit decoder: {len(parts)} parts, reaches x={max(p[0] for p in parts)} "
          f"z={max(p[2] for p in parts)}", flush=True)
    with Lab() as lab:
        for x, y, z, b in sorted(parts, key=lambda p: p[1]):   # floor level first, then upward
            lab.cmd(f"setblock {BASE[0] + x} {Y + y} {BASE[1] + z} {b}", wait=0.02)
        t0 = time.time()
        lab.sync()
        print(f"server caught up after {time.time() - t0:.0f}s", flush=True)
        time.sleep(4)
        good = 0
        for addr in range(1 << bits):
            for k in range(bits):
                x, z = inputs[f"A{k}"]
                block = "redstone_block" if addr >> k & 1 else OFF
                lab.cmd(f"setblock {BASE[0] + x} {Y} {BASE[1] + z} {block}", wait=0.02)
            time.sleep(4)
            lit = [i for i, (x, z) in enumerate(outs)
                   if lab.block_at(BASE[0] + x, Y, BASE[1] + z, "lit_redstone_lamp")]
            ok = lit == [addr]
            good += ok
            print(f"  address {addr:2d} -> lines on: {lit}  {'ok' if ok else 'WRONG'}", flush=True)
    print(f"{good}/{1 << bits} addresses correct")


if __name__ == "__main__":
    main()
