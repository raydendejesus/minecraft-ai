"""Write circuit_lessons.jsonl: "redstone circuit <formula>" -> the circuit's blocks.

    python build_circuit_bank.py [file name]

Formulas come from practice goals only (locked-away exam goals never appear), every difficulty
level, plus random formulas so it learns circuits for formulas written any way, not just the
teacher's. Building one takes about a third of a second, so this runs on several cores.
"""

import json
import os
import random
import sys
from multiprocessing import Pool

import circuit as C
import data
import design_data as D
import redstone_lib as R

HERE = os.path.dirname(os.path.abspath(__file__))
PER_LEVEL = 3000
RANDOM = 3000


def lesson(expr):
    try:
        return f"redstone circuit {expr}", C.lesson(expr)       # build-order text
    except (RuntimeError, ValueError):
        return None


def function_of(expr):
    """The goal number a formula computes, read the same way design_data.works reads a design."""
    rows = "".join(str(int(data.eval_logic(expr, {"a": bool(r & 8), "b": bool(r & 4), "c": bool(r & 2),
                                                   "d": bool(r & 1)}))) for r in range(16))
    return int(rows, 2)


def random_formula(depth=0):
    if depth >= 3 or random.random() < 0.3:
        v = random.choice("abcd")
        return f"not {v}" if random.random() < 0.3 else v
    e = f"{random_formula(depth + 1)} {random.choice(('and', 'or', 'xor'))} {random_formula(depth + 1)}"
    e = f"({e})" if depth else e
    return f"not {e}" if random.random() < 0.15 and depth else e


def main():
    random.seed(2026)
    levels = {}
    for f in range(65536):
        if not D.is_exam(f):
            levels.setdefault(D.gates(D.answer(f)), []).append(D.answer(f)[2:])
    exprs = [e for g in sorted(levels) for e in random.sample(levels[g], min(PER_LEVEL, len(levels[g])))]
    randoms = (random_formula() for _ in range(RANDOM * 2))
    exprs += [e for e in randoms if not D.is_exam(function_of(e))][:RANDOM]   # never a locked goal
    exprs = list(dict.fromkeys(exprs))
    name = sys.argv[1] if len(sys.argv) > 1 else "circuit_lessons.jsonl"
    with Pool(6) as pool:
        out = [x for x in pool.imap(lesson, exprs, chunksize=20) if x]
    with open(os.path.join(HERE, name), "w", encoding="utf-8") as f:
        for x in out:
            f.write(json.dumps(x) + "\n")
    longest = max(len(a) for _, a in out)
    print(f"{len(out)}/{len(exprs)} circuits written to {name} (longest answer {longest} chars)")


if __name__ == "__main__":
    main()
