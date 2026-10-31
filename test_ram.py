"""Check addressable RAM on the lab server: write a different value to each tested word, read
them all back, then overwrite one word and make sure the others didn't change.

    python test_ram.py 2 2      4 words of 2 bits
    python test_ram.py 4 8      16 bytes, every word
    python test_ram.py 7 8      128 bytes, a spread of 24 words across the whole stick
"""

import sys
import time

import redstone_lib as R
from lab import FLOOR_Y, Lab

Y = FLOOR_Y + 1
BASE = (2, 8)
OFF = R.lever(0, 0)[3]


def main():
    a_bits = int(sys.argv[1]) if len(sys.argv) > 1 else 2
    w_bits = int(sys.argv[2]) if len(sys.argv) > 2 else 2
    parts, inputs, outs = R.ram(a_bits, w_bits)
    far_z = max(p[2] for p in parts)
    commands = R.to_fills(parts, (BASE[0], Y, BASE[1]))
    # signals cross a repeater (0.1s) every 6 blocks, there and back
    settle = max(3, far_z / 6 * 0.1 * 2 + 2)
    print(f"RAM {1 << a_bits} words x {w_bits} bits: {len(parts)} parts in {len(commands)} commands, "
          f"x up to {max(p[0] for p in parts)}, z up to {far_z}, settle {settle:.0f}s", flush=True)

    with Lab(far_z=max(120, far_z + 16)) as lab:
        def set_input(name, on):
            x, z = inputs[name]
            lab.cmd(f"setblock {BASE[0] + x} {Y} {BASE[1] + z} {'redstone_block' if on else OFF}", wait=0.05)

        def set_addr(a):
            for k in range(a_bits):
                set_input(f"A{k}", a >> k & 1)

        def write(a, v):
            set_addr(a)
            for k in range(w_bits):
                set_input(f"D{k}", v >> k & 1)
            time.sleep(settle)
            set_input("W", True)
            time.sleep(settle)
            set_input("W", False)                # write goes off before anything else changes
            time.sleep(settle)

        def read(a):
            set_addr(a)
            time.sleep(settle + 1)
            bits = [lab.block_at(BASE[0] + x, Y + y, BASE[1] + z, "lit_redstone_lamp") for x, y, z in outs]
            return sum(1 << k for k, b in enumerate(bits) if b)

        t0 = time.time()
        for n, command in enumerate(commands):
            lab.cmd(command, wait=0.02)
            if n and n % 2000 == 0:
                lab.sync()                       # let the server catch up as we go
                print(f"  placed {n}/{len(commands)} commands, {time.time() - t0:.0f}s", flush=True)
        lab.sync()
        print(f"built in {time.time() - t0:.0f}s", flush=True)
        time.sleep(4 + settle)

        words, top = 1 << a_bits, 1 << w_bits
        tested = list(range(words)) if words <= 16 else sorted({round(i * (words - 1) / 23) for i in range(24)})
        # values spread over every bit, including the top one (the column farthest from the decoder)
        values = {a: (i * 37 + 133) % top for i, a in enumerate(tested)}
        for a, v in values.items():
            write(a, v)
        good = 0
        for a, v in values.items():
            got = read(a)
            good += got == v
            print(f"  word {a:3d}: wrote {v:3d}, read {got:3d}  {'ok' if got == v else 'WRONG'}", flush=True)
        first = tested[0]
        values[first] = (values[first] + 1) % top
        write(first, values[first])
        for a, v in values.items():
            got = read(a)
            good += got == v
            print(f"  after rewriting word {first}: word {a:3d} = {got:3d}  "
                  f"{'ok' if got == v else 'WRONG, should be ' + str(v)}", flush=True)
    print(f"{good}/{2 * len(tested)} reads correct")


if __name__ == "__main__":
    main()
