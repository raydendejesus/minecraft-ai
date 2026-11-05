"""PvP exam: the trained model fights every play style, and the rulebook expert, in fixed duels.

    python exam_pvp.py pvp.pt 40          40 duels per opponent

The model only sees what a player would see (pvp_sim.Duel.state_text) and picks one move per
quarter second from the moves it could make right now.
Prints the win rate against each opponent, and how long one move takes to think of.
"""

import collections
import random
import sys
import time

import pvp_data as P
import pvp_sim as S
from model import Builder

OPPONENTS = [(st, 0.9) for st in S.STYLES] + [("expert", 1.0)]


def model_player(ai):
    """The model rates every move it could make right now in one pass and plays its top pick
    (Builder.choose), the same knowledge as writing the move out, in one step instead of ~6."""
    def move(d, i, r):
        return ai.choose(d.state_text(i), P.candidates(d, i))
    return move


def geometry_quiz(ai, n=300):
    """Fresh math / geometry / hitbox questions; an answer counts only if it's exactly right."""
    random.seed(77)
    qs = [P.geometry_question() for _ in range(n)]
    right = collections.Counter()
    total = collections.Counter()
    for q, a in qs:
        kind = " ".join(q.split()[:2])
        total[kind] += 1
        right[kind] += ai.build(q, limit=120) == a
    for kind in sorted(total):
        print(f"  {kind:20s} {right[kind]}/{total[kind]}")
    print(f"geometry quiz: {sum(right.values())}/{n} exactly right")


def main():
    path = sys.argv[1] if len(sys.argv) > 1 else "pvp.pt"
    n = int(sys.argv[2]) if len(sys.argv) > 2 else 40
    ai = Builder(path)
    if "--geometry" in sys.argv:
        geometry_quiz(ai)
    me = model_player(ai)
    total, think, moves = collections.Counter(), 0.0, 0
    for style, skill in OPPONENTS:
        foe, res = S.bot(style, skill), collections.Counter()
        for s in range(n):
            r = random.Random(50_000 + s)          # fixed duels, never used for lessons
            d = S.Duel(rng=r)
            while not d.over():
                t = time.perf_counter()
                m = me(d, 0, r)
                think += time.perf_counter() - t
                moves += 1
                d.step(m, foe(d, 1, r))
            res[d.winner()] += 1
        total += res
        print(f"  vs {style:10s} (skill {skill}): win {100 * res[0] / n:.0f}%  lose {100 * res[1] / n:.0f}%  "
              f"draw {100 * res[None] / n:.0f}%", flush=True)
    t = sum(total.values())
    print(f"PvP exam: win {100 * total[0] / t:.0f}%  lose {100 * total[1] / t:.0f}%  draw {100 * total[None] / t:.0f}%"
          f"  ({t} duels, {1000 * think / moves:.0f} ms per move)")


if __name__ == "__main__":
    main()
