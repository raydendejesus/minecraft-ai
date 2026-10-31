"""Build the 2-bit adder, force a carry out of bit 0, and read the signal along the carry wire."""

import time

import redstone_lib as R
from lab import FLOOR_Y, Lab
from router import Router

Y = FLOOR_Y + 1
BX, BZ = 2, 4

parts, inputs, outs = R.adder(2)
base = []
for i in range(2):
    off = i * 20
    fa = R.shift(R.g_full_adder()[0], 0, off)
    if i > 0:
        fa = R.swap(fa, (10, 8 + off), None)
    if i < 1:
        fa = R.swap(fa, (22, 11 + off), None)
    base += fa
wire = [p for p in parts if p not in base]
print("wire parts:", len(wire))
for p in wire:
    print("  ", p[0], p[1], p[2], p[3].split()[0])

with Lab() as lab:
    for x, y, z, b in parts:
        lab.cmd(f"setblock {BX + x} {Y + y} {BZ + z} {b}", wait=0.02)
    time.sleep(2)
    for name in ("A0", "B0"):
        x, z = inputs[name]
        lab.cmd(f"setblock {BX + x} {Y} {BZ + z} redstone_block", wait=0.05)
    time.sleep(3)
    print("with A0 + B0 on, signal along the wire:")
    for x, y, z, b in wire:
        if b.startswith("redstone_wire"):
            pos = (BX + x, Y + y, BZ + z)
            sig = next((s for s in range(16)
                        if lab.block_at(*pos, f'redstone_wire ["redstone_signal"={s}]')), "not dust!")
            print(f"  dust {x} {y} {z}: {sig}", flush=True)
        elif b.startswith("unpowered_repeater"):
            on = lab.block_at(BX + x, Y + y, BZ + z, "powered_repeater")
            print(f"  repeater {x} {y} {z}: {'on' if on else 'off'}", flush=True)
    for label, (x, z) in (("row before wire", (21, 11)), ("row start", (14, 11))):
        sig = next((s for s in range(16)
                    if lab.block_at(BX + x, Y, BZ + z, f'redstone_wire ["redstone_signal"={s}]')), "?")
        print(f"  {label} {x},{z}: {sig}")
    print("  sum bit 0 lamp lit:", lab.block_at(BX + 19, Y, BZ + 5, "lit_redstone_lamp"))
