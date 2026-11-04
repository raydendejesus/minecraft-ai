"""The AI designs AND builds: for locked-away goals it has never seen, it invents a formula, then
writes the redstone blocks for its own formula. The lab server places exactly what it wrote and
every lever combination is checked against the goal.

    python test_ai_circuits.py designer.pt 2          2 goals per difficulty level, on the lab
    python test_ai_circuits.py designer.pt 10 --offline   no lab: does it write blocks that parse,
                                                      and the same circuit the teacher would?

Everything the AI wrote is saved in ai_circuits/.
"""

import os
import random
import sys

import circuit as C
import design_data as D
import redstone_lib as R
from model import Builder

HERE = os.path.dirname(os.path.abspath(__file__))


def goal_fn(f):
    bits = D.request(f).split()[1]                  # row = a b c d read as a binary number
    return lambda env: bits[env["a"] * 8 + env["b"] * 4 + env["c"] * 2 + env["d"]] == "1"


def main():
    path = sys.argv[1] if len(sys.argv) > 1 else "designer.pt"
    per = int(sys.argv[2]) if len(sys.argv) > 2 else 2
    offline = "--offline" in sys.argv
    random.seed(99)
    levels = {}
    for f in range(65536):
        if D.is_exam(f):
            levels.setdefault(D.gates(D.answer(f)), []).append(f)
    goals = [f for g in sorted(levels) for f in random.sample(levels[g], min(per, len(levels[g])))]
    ai = Builder(path)
    os.makedirs(os.path.join(HERE, "ai_circuits"), exist_ok=True)

    built = []                                      # (goal, formula, parts)
    stats = {"design wrong": 0, "unreadable": 0, "same as teacher": 0}
    for f in goals:
        design = ai.build(D.request(f), limit=160)
        formula = design.lstrip("#").strip()
        if not D.works(D.request(f), design):
            stats["design wrong"] += 1
            print(f"  {D.request(f)}: its design doesn't work ({design[:60]})", flush=True)
            continue
        text = ai.build(f"redstone circuit {formula}")
        with open(os.path.join(HERE, "ai_circuits", f"{f:05d}.txt"), "w", encoding="utf-8") as out:
            out.write(f"goal {D.request(f)}\nits formula {formula}\n\n{text}\n")
        steps = text.lstrip().startswith("#")       # build-order text (older models wrote sorted runs)
        try:
            parts = C.from_steps(text) if steps else R.from_runs(text)
            C.inputs_and_output(parts)
        except Exception as e:
            stats["unreadable"] += 1
            print(f"  {formula}: blocks unreadable ({str(e)[:60]})", flush=True)
            continue
        try:
            same = text.strip() == (C.lesson(formula) if steps else R.to_runs(C.build(formula))).strip()
        except RuntimeError:
            same = False
        stats["same as teacher"] += same
        built.append((f, formula, parts, same))
        print(f"  {formula}: {len(parts)} blocks{', same as the teacher would build' if same else ''}", flush=True)
    print(f"{len(goals)} goals: " + ", ".join(f"{k} {v}" for k, v in stats.items()), flush=True)
    if offline:
        return

    import test_circuits as T
    from lab import Lab
    good = 0
    with Lab(far_x=T.FAR_X) as lab:
        for f, formula, parts, same in built:
            if not T.fits(parts):
                print(f"  too wide for the lab: {formula}", flush=True)
                continue
            right, wrong = T.check(lab, parts, goal_fn(f))
            good += right == 16
            print(f"  {right:2d}/16  {formula}" + (f"   first wrong: {wrong}" if wrong else ""), flush=True)
    print(f"AI-designed, AI-built circuits that work in the lab: {good}/{len(goals)}")


if __name__ == "__main__":
    main()
