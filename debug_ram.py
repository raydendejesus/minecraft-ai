"""Build a tiny RAM, write 1 into word 0 bit 0, and read every stage of that cell."""

import time

import redstone_lib as R
from lab import FLOOR_Y, Lab

Y = FLOOR_Y + 1
BX, BZ = 2, 8
OFF = R.lever(0, 0)[3]
parts, inputs, outs = R.ram(2, 2)
width = 12
xn = width + 2
c = xn + 3


def sig(lab, x, y, z):
    return next((s for s in range(16)
                 if lab.block_at(BX + x, Y + y, BZ + z, f'redstone_wire ["redstone_signal"={s}]')), "?")


def rep_state(lab, x, y, z):
    return "on" if lab.block_at(BX + x, Y + y, BZ + z, "powered_repeater") else \
        "off" if lab.block_at(BX + x, Y + y, BZ + z, "unpowered_repeater") else "MISSING"


def comp_state(lab, x, y, z):
    return "on" if lab.block_at(BX + x, Y + y, BZ + z, "powered_comparator") else \
        "off" if lab.block_at(BX + x, Y + y, BZ + z, "unpowered_comparator") else "MISSING"


def show(lab, label):
    print(f"--- {label}")
    print(f"  word0 R row x={width},{c}: {sig(lab, width, 0, 0)} {sig(lab, c, 0, 0)}   "
          f"L row x={width},{xn + 1},{c}: {sig(lab, width, 0, 4)} {sig(lab, xn + 1, 0, 4)} {sig(lab, c, 0, 4)}")
    print(f"  word1 R row: {sig(lab, c, 0, 6)}  L row: {sig(lab, c, 0, 10)}")
    print(f"  NOT-write line z=2: {sig(lab, xn, 2, 2)}  tap: {sig(lab, xn + 1, 1, 2)}  tap rep: {rep_state(lab, xn + 1, 0, 3)}")
    print(f"  data-in line z=2: {sig(lab, c, 2, 2)}  tap: {sig(lab, c + 1, 1, 2)}")
    print(f"  R1: {rep_state(lab, c + 2, 0, 2)}  lock rep: {rep_state(lab, c + 2, 0, 3)}  "
          f"comparator: {comp_state(lab, c + 3, 0, 2)}  side rep: {rep_state(lab, c + 3, 0, 1)}")
    print(f"  up-dust: {sig(lab, c + 4, 1, 2)}  data-out z=2: {sig(lab, c + 5, 2, 2)}  z=-1: {sig(lab, c + 5, 2, -1)}  "
          f"lamp lit: {lab.block_at(BX + outs[0][0], Y + 2, BZ - 2, 'lit_redstone_lamp')}", flush=True)


with Lab() as lab:
    for x, y, z, b in sorted(parts, key=lambda p: p[1]):
        lab.cmd(f"setblock {BX + x} {Y + y} {BZ + z} {b}", wait=0.02)
    lab.sync()
    time.sleep(4)
    show(lab, "idle, address 0, no data")
    x, z = inputs["D0"]
    lab.cmd(f"setblock {BX + x} {Y} {BZ + z} redstone_block", wait=0.1)
    time.sleep(3)
    show(lab, "data on, write off")
    x, z = inputs["W"]
    lab.cmd(f"setblock {BX + x} {Y} {BZ + z} redstone_block", wait=0.1)
    time.sleep(3)
    show(lab, "write ON")
    lab.cmd(f"setblock {BX + x} {Y} {BZ + z} {OFF}", wait=0.1)
    time.sleep(3)
    show(lab, "write off again")
