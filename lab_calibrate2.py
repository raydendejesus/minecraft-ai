"""Second calibration pass: torch sides, a real NOT gate, and dust reach."""

import time

from lab import Lab

Y = 101
SIDE = {"north": (0, -1), "south": (0, 1), "east": (1, 0), "west": (-1, 0)}


def main():
    with Lab() as lab:
        print("Torch side test: is torch_facing_direction the side its support block is on?")
        for i, (d, (dx, dz)) in enumerate(SIDE.items()):
            x, z = 4, i * 6 + 2
            lab.cmd(f"setblock {x + dx} {Y} {z + dz} stone")
            lab.cmd(f'setblock {x} {Y} {z} redstone_torch ["torch_facing_direction"="{d}"]')
            time.sleep(0.4)
            print(f"  {d:5s} support at ({dx:+d},{dz:+d}) -> torch stays: {lab.block_at(x, Y, z, 'redstone_torch')}")

        print("NOT gate: lever-free input = repeater pointing into the stone, torch on far side")
        x, z = 20, 0
        lab.cmd(f"setblock {x + 2} {Y} {z} stone")
        lab.cmd(f'setblock {x + 3} {Y} {z} redstone_torch ["torch_facing_direction"="west"]')
        lab.cmd(f"setblock {x + 4} {Y} {z} redstone_lamp")
        lab.cmd(f'setblock {x + 1} {Y} {z} unpowered_repeater ["minecraft:cardinal_direction"="west"]')
        time.sleep(0.6)
        print(f"  input off -> lamp lit: {lab.block_at(x + 4, Y, z, 'lit_redstone_lamp')}  (expect True)")
        lab.cmd(f"setblock {x} {Y} {z} redstone_block")
        time.sleep(0.8)
        print(f"  input on  -> lamp lit: {lab.block_at(x + 4, Y, z, 'lit_redstone_lamp')}  (expect False)")

        print("Dust reach: lamp at the END of a dust line of length n")
        for j, n in enumerate((14, 15, 16)):
            z = 10 + j * 3
            lab.cmd(f"setblock 30 {Y} {z} redstone_block")
            lab.cmd(f"fill 31 {Y} {z} {30 + n} {Y} {z} redstone_wire")
            lab.cmd(f"setblock {31 + n} {Y} {z} redstone_lamp")
        time.sleep(1.2)
        for j, n in enumerate((14, 15, 16)):
            print(f"  {n} dust -> lamp lit: {lab.block_at(31 + n, Y, 10 + j * 3, 'lit_redstone_lamp')}")


if __name__ == "__main__":
    main()
