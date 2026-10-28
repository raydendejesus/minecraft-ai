"""Build the 1-bit latch and print each part's state as inputs change."""

import time

import redstone_lib as R
from lab import FLOOR_Y, Lab

Y = FLOOR_Y + 1
BX, BZ = 0, 8
CHECKS = [
    ("write-in repeater", (3, -4), ["powered_repeater", "unpowered_repeater"]),
    ("lock torch", (3, -2), ["redstone_torch", "unlit_redstone_torch"]),
    ("lock repeater", (1, 1), ["powered_repeater", "unpowered_repeater"]),
    ("bit repeater", (1, 0), ["powered_repeater", "unpowered_repeater"]),
    ("lamp", (2, 0), ["lit_redstone_lamp", "redstone_lamp"]),
]


def show(lab, label):
    states = []
    for name, (x, z), options in CHECKS:
        found = next((o for o in options if lab.block_at(BX + x, Y, BZ + z, o)), "?")
        states.append(f"{name}={found}")
    print(f"{label:14s} " + "  ".join(states))


with Lab() as lab:
    parts, inputs, outs = R._ram_bits(1)
    for y in range(Y, Y + 4):
        lab.cmd(f"fill -8 {y} 0 40 {y} 40 air")
    for x, y, z, b in parts:
        lab.cmd(f"setblock {BX + x} {Y + y} {BZ + z} {b}", wait=0.05)
    time.sleep(1)
    show(lab, "built")
    for label, on in [("W+D", {"W", "D0"}), ("none", set()), ("W", {"W"}), ("W again", {"W"})]:
        for nm, (x, z) in inputs.items():
            b = "redstone_block" if nm in on else R.lever(0, 0)[3]
            lab.cmd(f"setblock {BX + x} {Y} {BZ + z} {b}", wait=0.05)
        time.sleep(1.2)
        show(lab, label)
