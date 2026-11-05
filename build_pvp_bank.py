"""Write pvp_lessons.jsonl: lots of player-vs-player duels played by the look-ahead teacher.

    python build_pvp_bank.py 45000          45,000 duels (about 2 million moves)

Every duel is a fresh mix: one of 8 kits, flat ground or hills, and an opponent from 11 play
styles at a random skill level. Runs on several CPU cores; the teacher's results against each
style are printed at the end.
"""

import collections
import json
import os
import sys
from multiprocessing import Pool

import pvp_data as P

HERE = os.path.dirname(os.path.abspath(__file__))
WORKERS = 4            # leaves room for the GPU job's own CPU work


SEED0 = 1_000_000      # far from the exam's fixed duels (exam_pvp.py uses 50,000 and up)


def one(seed):
    lessons, winner, style, kit = P.duel(SEED0 + seed)
    return lessons, winner, style


def main():
    n = int(sys.argv[1]) if len(sys.argv) > 1 else 45000
    results = collections.defaultdict(collections.Counter)
    moves = 0
    tmp = P.BANK + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f, Pool(WORKERS) as pool:
        for k, (lessons, winner, style) in enumerate(pool.imap_unordered(one, range(n), chunksize=8)):
            for x in lessons:
                f.write(json.dumps(x) + "\n")
            moves += len(lessons)
            results[style][{0: "win", 1: "lose", None: "draw"}[winner]] += 1
            if (k + 1) % 2000 == 0:
                print(f"  {k + 1}/{n} duels, {moves:,} moves", flush=True)
    os.replace(tmp, P.BANK)
    print(f"{n} duels, {moves:,} moves written to pvp_lessons.jsonl")
    total = sum((c for c in results.values()), collections.Counter())
    print(f"teacher overall: win {100 * total['win'] / n:.0f}%  lose {100 * total['lose'] / n:.0f}%  "
          f"draw {100 * total['draw'] / n:.0f}%")
    for style, c in sorted(results.items()):
        t = sum(c.values())
        print(f"  vs {style:10s} win {100 * c['win'] / t:.0f}%  lose {100 * c['lose'] / t:.0f}%  ({t} duels)")


if __name__ == "__main__":
    main()
