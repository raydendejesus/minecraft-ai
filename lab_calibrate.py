"""Work out what Bedrock's direction states really mean, by testing them.
Every rig sends power toward +x (east) and checks whether the lamp at the end lights."""

import time

from lab import Lab

Y = 101
DIRS = ["north", "south", "east", "west"]


def lit(lab, x, z):
    return lab.block_at(x, Y, z, "lit_redstone_lamp")


def main():
    with Lab() as lab:
        print("Repeater / comparator: source at x, part at x+1, lamp at x+2")
        for part in ("unpowered_repeater", "unpowered_comparator"):
            for i, d in enumerate(DIRS):
                z = i * 3
                x = 0 if part == "unpowered_repeater" else 10
                lab.cmd(f"setblock {x + 2} {Y} {z} redstone_lamp")
                lab.cmd(f'setblock {x + 1} {Y} {z} {part} ["minecraft:cardinal_direction"="{d}"]')
                lab.cmd(f"setblock {x} {Y} {z} redstone_block")
            time.sleep(1)
            for i, d in enumerate(DIRS):
                x = 0 if part == "unpowered_repeater" else 10
                print(f"  {part:22s} cardinal_direction={d:5s} -> lamp lit: {lit(lab, x + 2, i * 3)}")

        print("Torch on the side of a block (NOT gate): stone at x, torch at x+1, lamp at x+2")
        for i, d in enumerate(DIRS + ["top"]):
            z, x = i * 3, 20
            lab.cmd(f"setblock {x} {Y} {z} stone")
            out = lab.cmd(f'setblock {x + 1} {Y} {z} redstone_torch ["torch_facing_direction"="{d}"]')
            lab.cmd(f"setblock {x + 2} {Y} {z} redstone_lamp")
            time.sleep(0.6)
            on = lit(lab, x + 2, z)
            lab.cmd(f"setblock {x - 1} {Y} {z} redstone_block")  # power the stone
            time.sleep(0.8)
            still = lab.block_at(x + 1, Y, z, "redstone_torch")
            off = lab.block_at(x + 1, Y, z, "unlit_redstone_torch")
            print(f"  torch_facing_direction={d:5s} placed={'Block placed' in ' '.join(out)} "
                  f"lamp lit={on} torch_on_after_power={still} torch_off_after_power={off}")

        print("Piston facing_direction 0-5: piston at x, redstone block placed below it")
        for f in range(6):
            x, z = 30, f * 4
            lab.cmd(f"setblock {x} {Y + 1} {z} piston [\"facing_direction\"={f}]")
            lab.cmd(f"setblock {x} {Y} {z} redstone_block")
        time.sleep(1)
        offsets = {"down": (0, -1, 0), "up": (0, 1, 0), "north": (0, 0, -1), "south": (0, 0, 1),
                   "west": (-1, 0, 0), "east": (1, 0, 0)}
        for f in range(6):
            x, z = 30, f * 4
            hit = [name for name, (dx, dy, dz) in offsets.items()
                   if lab.block_at(x + dx, Y + 1 + dy, z + dz, "piston_arm_collision")]
            print(f"  facing_direction={f} -> pushes {hit}")

        print("Redstone dust reach: source then a line of dust, lamps checked along it")
        lab.cmd(f"setblock 40 {Y} 0 redstone_block")
        lab.cmd(f"fill 41 {Y} 0 58 {Y} 0 redstone_wire")
        for n in (14, 15, 16):
            lab.cmd(f"setblock {40 + n + 1} {Y} 1 redstone_lamp")
        time.sleep(1)
        for n in (14, 15, 16):
            print(f"  lamp beside dust #{n}: lit={lit(lab, 40 + n + 1, 1)}")


if __name__ == "__main__":
    main()
