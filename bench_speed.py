"""How fast each model writes, with the plain writer and the fast ones, on an idle GPU.
Every fast answer is checked against the plain one: speed must not change a single letter.
Writes speed_report.txt.

    python bench_speed.py
"""

import os
import random
import time

import torch

import fight_data as FD
import fight_sim as FS
from data import encode, fmt
from model import HERE, Builder, FastWriter

REPORT = os.path.join(HERE, "speed_report.txt")


def timed(fn, *a):
    torch.cuda.synchronize()
    t = time.perf_counter()
    out = fn(*a)
    torch.cuda.synchronize()
    return out, time.perf_counter() - t


def main():
    lines = [time.strftime("%Y-%m-%d %H:%M")]
    cases = [("builder.pt", ["build a house 7 by 5 with oak_planks", "redstone and gate"]),
             ("designer.pt", ["design 0110100110010110", "redstone circuit not a and not b",
                              "redstone circuit b xor (c and d)",
                              "redstone circuit not (not c and not d) and not (not a and (b xor d))"])]
    for path, reqs in cases:
        b = Builder(os.path.join(HERE, path))
        b._maybe_reload()
        m, fw = b.model, FastWriter(b.model)
        for req in reqs:
            ids = encode(fmt(req))
            m.generate(ids, 5), m.generate_fast(ids, 5), fw.generate(ids, 5)
            plain, t0 = timed(m.generate, ids, m.ctx)
            cache, t1 = timed(m.generate_fast, ids, m.ctx)
            graph, t2 = timed(fw.generate, ids, m.ctx)
            lines.append(f"{path} {req[:40]!r}: {len(plain)} chars | plain {t0:.2f}s | cache {t1:.2f}s"
                         f" (same: {cache == plain}) | graph {t2:.2f}s (same: {graph == plain})")
    # moves from a list: write it out vs choose in one pass (fight model, real fight states)
    ai = Builder(os.path.join(HERE, "fight.pt"))
    ai._maybe_reload()
    random.seed(4)
    agree, tb, tc, n = 0, 0.0, 0.0, 0
    while n < 150:
        seed = random.randrange(10 ** 9)
        f = FS.Fight(random.Random(seed), **FD.scenario_for(seed))
        for _ in range(40):
            if f.over() or n >= 150:
                break
            kinds = sorted({x.kind for x in f.alive()})
            opts = ["retreat", "flee", "strafe", "shield", "eat", "hide", "unhide", "wait"] + \
                   [f"{v} {k}" for k in kinds for v in ("attack", "crit", "combo", "shoot", "approach")]
            a, t = timed(ai.build, f.state_text(), 24)
            c, u = timed(ai.choose, f.state_text(), opts)
            agree, tb, tc, n = agree + (a == c), tb + t, tc + u, n + 1
            f.step(FD.teacher(f))
    lines.append(f"fight.pt moves: write it out {1000 * tb / n:.1f} ms, choose in one pass {1000 * tc / n:.1f} ms,"
                 f" same move {agree}/{n}")
    with open(REPORT, "a", encoding="utf-8") as out:
        out.write("\n".join(lines) + "\n\n")
    print("\n".join(lines))


if __name__ == "__main__":
    main()
