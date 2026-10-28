"""Print the game's raw replies to a few testforblock checks."""

from lab import Lab

with Lab() as lab:
    print(lab.cmd("setblock 2 101 8 redstone_lamp"))
    for b in ("redstone_lamp", "lit_redstone_lamp"):
        print(b, lab.cmd(f"testforblock 2 101 8 {b}"))
