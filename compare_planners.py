"""Compare saved Planner versions on the same survival games, one light GPU call at a time.

    python compare_planners.py planner_rl81.pt planner.pt
"""

import random
import sys

import planner_data as P
from model import Builder
from plan import play

GAMES = 300

for path in sys.argv[1:]:
    random.seed(777)
    planner = Builder(path)
    wins = sum(play(planner, P.random_state()) for _ in range(GAMES))
    print(f"{path:22s} won {wins}/{GAMES} ({wins / GAMES:.1%})", flush=True)
