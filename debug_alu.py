"""Build the 2-bit ALU, set SUB and B0 on, and read inside the first XOR. Also list the SUB wire."""

import time

import redstone_lib as R
from lab import FLOOR_Y, Lab

Y = FLOOR_Y + 1
BX, BZ = 8, 12
parts, inputs, outs = R.alu(2)
cells = {(p[0], p[1], p[2]): p[3].split()[0] for p in parts}

# everything planned in the first XOR's neighbourhood, as a map (y=0)
for z in range(-6, 10):
    row = ""
    for x in range(-4, 13):
        k = cells.get((x, 0, z), "")
        up = (x, 1, z) in cells or (x, 2, z) in cells
        ch = {"redstone_wire": "d", "unpowered_repeater": "r", "unpowered_comparator": "c", "stone": "#", "lever": "L",
              "redstone_lamp": "m", "": "."}.get(k, "?")
        row += ch.upper() if up and ch == "d" else (":" if up and ch == "." else ch)
    print(f"z={z:3d} {row}")


def read(lab, x, y, z):
    kind = cells.get((x, y, z), "?")
    if kind == "redstone_wire":
        for s in range(16):
            if lab.block_at(BX + x, Y + y, BZ + z, f'redstone_wire ["redstone_signal"={s}]'):
                return s
    for name in ("powered_repeater", "unpowered_repeater", "powered_comparator", "unpowered_comparator"):
        if lab.block_at(BX + x, Y + y, BZ + z, name):
            return name
    return "other"


with Lab() as lab:
    for c in R.to_fills(parts, (BX, Y, BZ)):
        lab.cmd(c, wait=0.02)
    lab.sync()
    time.sleep(3)
    for name in ("B0", "SUB"):
        x, z = inputs[name]
        lab.cmd(f"setblock {BX + x} {Y} {BZ + z} redstone_block", wait=0.1)
    time.sleep(8)
    for label, c in (("A-in dust (1,3)", (1, 0, 3)), ("rear rep C1 (4,3)", (4, 0, 3)), ("C1 (5,3)", (5, 0, 3)),
                     ("side rep C1 (5,2)", (5, 0, 2)), ("(5,1)", (5, 0, 1)), ("(2,0)", (2, 0, 0)), ("(1,0)", (1, 0, 0)),
                     ("rear rep C2 (4,7)", (4, 0, 7)), ("C2 (5,7)", (5, 0, 7)), ("side rep C2 (5,6)", (5, 0, 6)),
                     ("(5,5)", (5, 0, 5)), ("out (6,3)", (6, 0, 3)), ("out (6,7)", (6, 0, 7)), ("(8,5)", (8, 0, 5))):
        print(f"  {label:20s} {cells.get(c, '(none)'):22s} {read(lab, *c)}", flush=True)
