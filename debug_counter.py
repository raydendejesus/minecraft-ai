"""Build the 2-bit counter and read the first bit's parts while pulsing the clock and RESET."""

import time

import redstone_lib as R
from lab import FLOOR_Y, Lab

Y = FLOOR_Y + 1
BX, BZ = 4, 10
OFF = R.lever(0, 0)[3]
parts, clock, outs = R.counter(2)
cells = {(p[0], p[1], p[2]): p[3].split()[0] for p in parts}


def st(lab, x, z):
    k = cells.get((x, 0, z), "")
    if k == "redstone_wire":
        return next((s for s in range(16) if lab.block_at(BX + x, Y, BZ + z, f'redstone_wire ["redstone_signal"={s}]')), "?")
    if "repeater" in k:
        return "ON" if lab.block_at(BX + x, Y, BZ + z, "powered_repeater") else "off"
    if "torch" in k:
        return "ON" if lab.block_at(BX + x, Y, BZ + z, "redstone_torch") else "off"
    return k or "none"


def show(lab, label):
    names = (("CK", 7, 2), ("RA", 4, 0), ("lockA", 4, 1), ("RB", 6, 0), ("lockB", 6, 1), ("Q", 7, 0), ("notQ torch", 3, 0),
             ("notCK torch", 6, 6), ("into lockA", 4, 3), ("rst row", -1, 3), ("rst slow", 2, 1), ("rst clk", 7, 3), ("rst col", -2, 0))
    print(f"{label:12s} " + "  ".join(f"{n}={st(lab, x, z)}" for n, x, z in names), flush=True)


with Lab() as lab:
    for c in R.to_fills(parts, (BX, Y, BZ)):
        lab.cmd(c, wait=0.02)
    lab.sync()
    time.sleep(3)
    show(lab, "idle")
    cx, cz = clock
    lab.cmd(f"setblock {BX + cx} {Y} {BZ + cz} redstone_block", wait=0.05); time.sleep(2)
    show(lab, "clock on")
    lab.cmd(f"setblock {BX + cx} {Y} {BZ + cz} {OFF}", wait=0.05); time.sleep(3)
    show(lab, "clock off")
    lab.cmd(f"setblock {BX - 2} {Y} {BZ - 4} redstone_block", wait=0.05); time.sleep(3)
    show(lab, "reset on")
    lab.cmd(f"setblock {BX - 2} {Y} {BZ - 4} {OFF}", wait=0.05); time.sleep(3)
    show(lab, "reset off")
