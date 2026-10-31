"""Why is dust at (22,11) dead next to live dust at (21,11)? Read, wait, re-place, read again."""

import time

import redstone_lib as R
from lab import FLOOR_Y, Lab

Y = FLOOR_Y + 1
BX, BZ = 2, 4
parts, inputs, outs = R.adder(2)


def sig(lab, x, y, z):
    return next((s for s in range(16)
                 if lab.block_at(BX + x, Y + y, BZ + z, f'redstone_wire ["redstone_signal"={s}]')), "not dust")


def show(lab, label):
    print(f"{label}: " + "  ".join(f"{x},{z}={sig(lab, x, 0, z)}"
                                   for x, z in ((20, 11), (21, 11), (22, 11), (22, 12), (22, 13), (21, 13))), flush=True)


with Lab() as lab:
    for x, y, z, b in parts:
        lab.cmd(f"setblock {BX + x} {Y + y} {BZ + z} {b}", wait=0.02)
    time.sleep(2)
    for name in ("A0", "B0"):
        x, z = inputs[name]
        lab.cmd(f"setblock {BX + x} {Y} {BZ + z} redstone_block", wait=0.05)
    for t in (3, 8, 15):
        time.sleep(t if t == 3 else 6)
        show(lab, f"after ~{t}s")
    print("block at 22,11:", [n for n in ("redstone_wire", "redstone_lamp", "air", "stone")
                              if lab.block_at(BX + 22, Y, BZ + 11, n)])
    print("above 21,11:", [n for n in ("air", "stone", "redstone_wire")
                           if lab.block_at(BX + 21, Y + 1, BZ + 11, n)])
    lab.cmd(f"setblock {BX + 22} {Y} {BZ + 11} air", wait=0.3)
    lab.cmd(f"setblock {BX + 22} {Y} {BZ + 11} redstone_wire", wait=0.3)
    time.sleep(3)
    show(lab, "after re-placing the dust")
    print("final sum lamps:", [lab.block_at(BX + x, Y, BZ + z, "lit_redstone_lamp") for x, z in outs])
