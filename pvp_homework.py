"""PvP homework: the model plays its own duels, and at every moment it reaches the teacher works out
the best move. Wherever they disagree, the teacher's move goes into pvp_corrections.jsonl, which
pvp_data mixes into practice. The model learns the situations ITS OWN play leads to, which the
teacher's duels alone never show it.

    python pvp_homework.py pvp.pt 300        300 duels
"""

import collections
import json
import os
import random
import sys

import pvp_data as P
import pvp_sim as S
from model import Builder

KEEP = 30000


def main():
    path = sys.argv[1] if len(sys.argv) > 1 else "pvp.pt"
    n = int(sys.argv[2]) if len(sys.argv) > 2 else 300
    ai = Builder(path)
    seen = agree = 0
    wins = collections.Counter()
    fixes = []
    for k in range(n):
        seed = 2_000_000 + random.randrange(10 ** 8)      # away from the exam's and the bank's duels
        r = random.Random(seed)
        random.seed(seed)
        d = S.Duel(rng=r)
        foe = P.opponent(r)
        while not d.over():
            state = d.state_text(0)
            mine = ai.choose(state, P.candidates(d, 0))
            best = P.teacher(d, 0, foe)
            seen += 1
            if mine == best:
                agree += 1
            else:
                fixes.append({"req": state, "out": best})
            d.step(mine, foe(d, 1, r))                    # it plays ITS move: its own situations
        wins[d.winner()] += 1
    old = P.load_corrections()
    with open(P.CORRECTIONS_PATH, "w", encoding="utf-8") as f:
        for x in (old + fixes)[-KEEP:]:
            f.write(json.dumps(x) + "\n")
    print(f"homework: {n} duels, won {100 * wins[0] / n:.0f}% lost {100 * wins[1] / n:.0f}%,"
          f" agreed with the teacher on {100 * agree / max(1, seen):.0f}% of {seen} moves,"
          f" {len(fixes)} corrections added")


if __name__ == "__main__":
    main()
