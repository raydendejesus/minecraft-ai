"""Try a command list in the lab and print what the game says back. Usage: python lab_probe.py"""

from lab import Lab

TESTS = [
    'setblock 0 101 0 redstone_lamp',
    'setblock 0 101 1 redstone_block',
    'testforblock 0 101 0 lit_redstone_lamp',
    'setblock 2 101 0 unpowered_repeater ["minecraft:cardinal_direction"="east"]',
    'setblock 3 101 0 unpowered_repeater ["direction"=1]',
    'setblock 4 101 0 redstone_torch ["torch_facing_direction"="top"]',
    'setblock 5 101 0 unpowered_comparator ["minecraft:cardinal_direction"="south"]',
    'setblock 6 101 0 piston ["facing_direction"=2]',
    'setblock 7 101 0 observer ["minecraft:facing_direction"="up"]',
    'setblock 8 101 0 redstone_wire',
    'setblock 9 101 0 lever ["lever_direction"="up_north_south"]',
    'testforblock 2 101 0 unpowered_repeater',
    'testforblock 99 300 99 air',
]

if __name__ == "__main__":
    with Lab() as lab:
        for t in TESTS:
            print(">", t)
            for line in lab.cmd(t, 0.4):
                print("   ", line)
