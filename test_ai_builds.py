"""The AI builds: every circuit here is written by the Builder model, not taken from our designs.

    python test_ai_builds.py

For each circuit the model is asked for it, its text answer is turned into blocks, and only
those blocks are placed on the lab server and tested. The test harness knows which levers and
lamps to use, but no part of the circuit comes from the design library.
"""

import sys

import redstone_lib as R
import test_lab
from lab import Lab
from model import Builder

MODEL = sys.argv[1] if len(sys.argv) > 1 else "builder.pt"
ASK = {"not": "redstone not", "or": "redstone or", "nor": "redstone nor", "nand": "redstone nand",
       "and": "redstone and", "xor": "redstone xor", "half_adder": "redstone half_adder",
       "full_adder": "redstone full_adder", "rs_latch": "redstone rs_latch", "d_latch": "redstone d_latch",
       "ram_byte": "redstone ram 8"}


def main():
    ai = Builder(MODEL)
    written = {}
    for name, request in ASK.items():
        try:
            written[name] = R.from_compact(ai.build(request))
        except (ValueError, IndexError, KeyError) as e:
            written[name] = None
            print(f"  {name}: the model wrote something unbuildable ({e})", flush=True)

    def use_ai_parts(fn, name):
        def inner():
            _, *rest = fn()                  # keep only which levers/lamps to test; drop our parts
            return (written[name], *rest)
        return inner

    for table in (R.GATES, R.MEMORY):
        for name in list(table):
            if name in written and written[name] is not None:
                table[name] = use_ai_parts(table[name], name)

    base, results = (0, 8), {}
    with Lab() as lab:
        for name in ASK:
            if written[name] is None:
                results[name] = False
            elif name in R.MEMORY:
                results[name] = test_lab.run_memory(lab, name, base)
            else:
                results[name] = test_lab.run_gate(lab, name, base)
    print(f"\nBuilt by the AI: {sum(results.values())}/{len(results)} circuits work in the game")


if __name__ == "__main__":
    main()
