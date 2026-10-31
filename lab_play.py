"""Open the Redstone Lab to play in: builds a circuit and keeps the server running so you can
join it in Minecraft, walk around and flip the levers yourself.

    python lab_play.py ram 4 8      16-byte RAM
    python lab_play.py adder 4      4-bit adder
    python lab_play.py decoder 4    address decoder

Join in Minecraft: Play > Servers > Add Server, address 127.0.0.1, port 19140.
Press Enter in this window to shut the server down. The lab world is wiped when it next starts.
"""

import subprocess
import sys

import redstone_lib as R
from lab import FLOOR_Y, Lab

Y = FLOOR_Y + 1
BASE = (2, 8)


def main():
    running = subprocess.run(["tasklist", "/FI", "IMAGENAME eq bedrock_server.exe"],
                             capture_output=True, text=True).stdout
    if "bedrock_server.exe" in running:
        print("A Bedrock server is already running (probably a test). Wait for it to finish first.")
        return
    what = sys.argv[1] if len(sys.argv) > 1 else "ram"
    nums = [int(a) for a in sys.argv[2:]]
    if what == "ram":
        parts, inputs, outs = R.ram(*(nums or [4, 8]))
    elif what == "adder":
        parts, inputs, outs = R.adder(*(nums or [4]))
    else:
        parts, inputs, outs = R.decoder(*(nums or [4]))
    far_z = max(p[2] for p in parts)
    commands = R.to_fills(parts, (BASE[0], Y, BASE[1]))
    print(f"Building {what}: {len(parts)} parts...")
    with Lab(far_z=max(120, far_z + 16)) as lab:
        for command in commands:
            lab.cmd(command, wait=0.02)
        lab.sync()
        print("\nReady. In Minecraft: Play > Servers > Add Server, address 127.0.0.1, port 19140.")
        print(f"Jump to the circuit with:  /tp @s {BASE[0]} {Y + 6} {BASE[1] - 8}\n")
        print("Levers (x y z):")
        for name, (x, z) in inputs.items():
            print(f"  {name:4s} {BASE[0] + x} {Y} {BASE[1] + z}")
        if what == "ram":
            print("\nTo save a number: set A levers, set D levers, flip W on, then off.")
            print("Change the address only while W is off. Lamps show the addressed word.")
        input("\nPress Enter here to shut the server down.\n")


if __name__ == "__main__":
    main()
