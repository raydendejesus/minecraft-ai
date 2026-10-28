"""Print one duel against the PvP bot, tick by tick."""

import random

import fight_data as D
import fight_sim as S

f = S.Fight(random.Random(3), scenario="duel")
for _ in range(60):
    if f.over():
        break
    a = D.teacher(f)
    print(f"{f.state_text():95s} -> {a}")
    f.step(a)
print("result:", "won" if f.won() else "died" if f.hp <= 0 else "other")
