"""How does the teacher do in the fight simulator? And print one example fight."""

import random
from collections import Counter

import fight_data as D
import fight_sim as S

random.seed(7)
f = S.Fight(random.Random(11))
for _ in range(40):
    if f.over():
        break
    a = D.teacher(f)
    print(f"{f.state_text():70s} -> {a}")
    f.step(a)
print("result:", "won" if f.won() else "died" if f.hp <= 0 else "survived" if f.survived() else "timeout", "\n")

out = Counter()
for i in range(2000):
    f = S.Fight(random.Random(i))
    for _ in range(80):
        if f.over():
            break
        f.step(D.teacher(f))
    out["won" if f.won() else "died" if f.hp <= 0 else "survived" if f.survived() else "timeout"] += 1
print("teacher over 2000 fights:", dict(out))
print(D.math_question(), D.math_question(), D.math_question())
