"""Build the 2-bit decoder and show what's on inside it with address 0."""

import time

import redstone_lib as R
from lab import FLOOR_Y, Lab

Y = FLOOR_Y + 1
BX, BZ = 2, 8
parts, inputs, outs = R.decoder(2)


def sig(lab, x, y, z):
    return next((s for s in range(16)
                 if lab.block_at(BX + x, Y + y, BZ + z, f'redstone_wire ["redstone_signal"={s}]')), "?")


with Lab() as lab:
    for x, y, z, b in sorted(parts, key=lambda p: p[1]):
        lab.cmd(f"setblock {BX + x} {Y + y} {BZ + z} {b}", wait=0.02)
    time.sleep(5)
    for x in (0, 3, 6, 9):
        print(f"line x={x}: start {sig(lab, x, 0, -4)}  top {sig(lab, x, 2, -2)}  z=2 {sig(lab, x, 2, 2)}  "
              f"z=11 {sig(lab, x, 2, 11)}", flush=True)
    for z in (0, 3, 6, 9):
        print(f"row z={z}: " + " ".join(str(sig(lab, x, 0, z)) for x in (0, 2, 5, 8, 11)), flush=True)
        print("   taps:", [(x, lab.block_at(BX + x, Y, BZ + z + 1, "powered_repeater"))
                           for x in (1, 4, 7, 10) if lab.block_at(BX + x, Y, BZ + z + 1, "unpowered_repeater")
                           or lab.block_at(BX + x, Y, BZ + z + 1, "powered_repeater")],
              " inverter rep on:", lab.block_at(BX + 12, Y, BZ + z, "powered_repeater"),
              " torch:", "on" if lab.block_at(BX + 14, Y, BZ + z, "redstone_torch") else
              "off" if lab.block_at(BX + 14, Y, BZ + z, "unlit_redstone_torch") else "MISSING", flush=True)
    print("lamp 15,0:", [n for n in ("redstone_lamp", "lit_redstone_lamp") if lab.block_at(BX + 15, Y, BZ, n)])
    print("tap dust (1,1,2):", sig(lab, 1, 1, 2), " tap dust (4,1,2):", sig(lab, 4, 1, 2))
