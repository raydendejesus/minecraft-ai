"""Which moves does the teacher use, and show one low-health fight where it digs in."""

import random
from collections import Counter

import fight_data as D
import fight_sim as S

moves = Counter()
example = None
for i in range(1500):
    f = S.Fight(random.Random(i))
    lines = []
    for _ in range(120):
        if f.over():
            break
        a = D.teacher(f)
        moves[a.split()[0]] += 1
        lines.append(f"{f.state_text()}  ->  {a}")
        f.step(a)
    if example is None and any(l.endswith("->  hide") for l in lines) and f.hp > 0:
        example = (lines, "won" if f.won() else "died" if f.hp <= 0 else "survived")
print("moves used:", dict(moves.most_common()))
if example:
    print("\nexample with hiding:")
    for l in example[0][:26]:
        print(" ", l)
    print("  result:", example[1])
