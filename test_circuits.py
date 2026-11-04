"""Build logic circuits on the lab server and check every input combination against the formula.

    python test_circuits.py 30        teacher check: 30 formulas from the design table, every size

check() takes any list of parts, so test_ai_circuits.py uses it on what the AI wrote. The levers
(a, b, c, d sorted by z) and the lamp are found in the parts themselves.
"""

import random
import sys
import time

import circuit as C
import data
import design_data as D
from lab import FLOOR_Y, Lab

Y = FLOOR_Y + 1
BASE = (-6, 10)
FAR_X = 250             # circuits reach further east than other lab builds; open the lab with Lab(far_x=FAR_X)
OFF = 'lever ["lever_direction"="up_north_south"]'
SETTLE = 7              # seconds for a signal to get through the longest circuits (measured in the
                        # lab: a 5-gate circuit could still be changing at 3s, never after 7s)


def fits(parts):
    xs = [BASE[0] + p[0] for p in parts]
    zs = [BASE[1] + p[2] for p in parts]
    return min(xs) >= -8 and max(xs) <= FAR_X and min(zs) >= -8


def check(lab, parts, expr):
    """Returns (rows right out of 16, first wrong row or None). expr is a formula, or a function
    taking {a, b, c, d} -> bool (to judge a build against the goal itself)."""
    want = expr if callable(expr) else (lambda env: data.eval_logic(expr, env))
    levers, lamp = C.inputs_and_output(parts)
    lab.reset_area()
    for x, y, z, b in parts:
        lab.cmd(f"setblock {BASE[0] + x} {Y + y} {BASE[1] + z} {b}", wait=0.01)
    lab.sync()
    time.sleep(2)
    right, wrong = 0, None
    for row in range(16):
        env = {v: bool(row >> (3 - i) & 1) for i, v in enumerate("abcd")}
        for (x, z), v in zip(levers, "abcd"):
            lab.cmd(f"setblock {BASE[0] + x} {Y} {BASE[1] + z} {'redstone_block' if env[v] else OFF}", wait=0.01)
        lab.sync()
        time.sleep(SETTLE)
        lit = lab.block_at(BASE[0] + lamp[0], Y, BASE[1] + lamp[1], "lit_redstone_lamp")
        if lit == want(env):
            right += 1
        elif wrong is None:
            wrong = "".join(str(int(env[v])) for v in "abcd") + f" lamp {'on' if lit else 'off'}"
    return right, wrong


def main():
    n = int(sys.argv[1]) if len(sys.argv) > 1 else 30
    random.seed(11)
    by_size = {}
    for f in random.sample(range(65536), 20000):
        by_size.setdefault(D.gates(D.answer(f)), []).append(D.answer(f)[2:])
    exprs = [by_size[g][k] for k in range(n) for g in sorted(by_size) if k < len(by_size[g])][:n]
    good = skipped = 0
    with Lab(far_x=FAR_X) as lab:
        for expr in exprs:
            try:
                parts = C.build(expr)
            except RuntimeError:
                print(f"  could not wire: {expr}", flush=True)
                skipped += 1
                continue
            if not fits(parts):
                print(f"  too wide for the lab: {expr}", flush=True)
                skipped += 1
                continue
            right, wrong = check(lab, parts, expr)
            good += right == 16
            print(f"  {right:2d}/16  {len(parts):4d} parts  {expr}" + (f"   first wrong: {wrong}" if wrong else ""), flush=True)
    print(f"{good}/{len(exprs) - skipped} teacher circuits work on every row ({skipped} skipped)")


if __name__ == "__main__":
    main()
