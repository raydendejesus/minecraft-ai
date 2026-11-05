"""The PvP model, start to finish. Logs to pvp_report.txt.

1. wait for pvp_lessons.jsonl (build_pvp_bank.py writes it on the CPU)
2. train pvp.pt from scratch: 4.8M parameters, short memory (a duel state is one line)
3. PvP exam against all 11 styles and the rulebook expert
4. homework rounds: it plays its own duels, the teacher marks every move, the moves it got wrong
   get extra practice, then the exam again (keeps the best model)
5. the math / geometry / hitbox stage: Pythagoras, distances, reach at every height, where to aim,
   added on top of its PvP lessons; geometry quiz + PvP exam
"""

import os
import re
import shutil
import sys
import time

import overnight as O
import overnight2 as T

O.REPORT = os.path.join(O.HERE, "pvp_report.txt")
BANK = os.path.join(O.HERE, "pvp_lessons.jsonl")
MODEL, BEST = (os.path.join(O.HERE, n) for n in ("pvp.pt", "pvp_best.pt"))
HOMEWORK_ROUNDS = 3


def exam(extra=()):
    code, out = O.run(["exam_pvp.py", "pvp.pt", "40", *extra], 4 * T.HOUR)
    for line in out.splitlines():
        s = line.strip()
        if s.startswith("vs ") or (extra and re.match(r"(math|pvpmath|pvpinfo) ", s)):
            O.note("  " + s)
    for pat in (r"geometry quiz: .*", r"PvP exam: .*"):
        hits = re.findall(pat, out)
        if hits:
            O.note(hits[-1])
    m = re.search(r"PvP exam: win (\d+)%", out)
    if not m:
        O.note(f"exam failed {T.why(out)}")
    return int(m[1]) if m else None


def main():
    O.note("=== the PvP model ===")
    if "--from-homework" not in sys.argv:
        while not os.path.exists(BANK) or os.path.exists(BANK + ".tmp"):
            time.sleep(60)
        with open(BANK, encoding="utf-8") as f:
            n = sum(1 for _ in f)
        O.note(f"lessons ready: {n:,} teacher moves")
        if not T.train(["--task", "pvp", "--ctx", "384", "--steps", "30000", "--batch", "256"], 6, "pvp training"):
            return
    best = exam()
    if best is None:
        return
    shutil.copy(MODEL, BEST)

    for k in range(1, HOMEWORK_ROUNDS + 1):
        code, out = O.run(["pvp_homework.py", "pvp.pt", "300"], 3 * T.HOUR)
        O.note(f"homework {k}: " + (re.findall(r"homework: .*", out) or [f"failed {T.why(out)}"])[-1])
        if code:
            break
        if not T.train(["--task", "pvp", "--resume", "--steps", "8000", "--batch", "256"], 3, f"practice {k}"):
            break
        win = exam()
        if win is not None and win > best:
            best = win
            shutil.copy(MODEL, BEST)
            O.note(f"  new best: {best}% (saved as pvp_best.pt)")
    shutil.copy(BEST, MODEL)                     # carry on from the best one
    O.note(f"best PvP exam: {best}%")

    O.note("--- math, geometry and hitboxes ---")
    os.environ["MCAI_GEOMETRY"] = "1"            # the training run inherits it
    if T.train(["--task", "pvp", "--resume", "--steps", "10000", "--batch", "256"], 3, "geometry"):
        exam(["--geometry"])
    O.note("=== finished ===")


if __name__ == "__main__":
    main()
