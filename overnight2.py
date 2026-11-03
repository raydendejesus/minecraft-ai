"""The long run: the 15M model learns to design, then the other models practice.

1. Train the 15M model on everything the Builder knows plus design (60,000 steps).
2. Exam on locked-away goals; if under 95%, train 20,000 more and retake it (2 rounds max).
3. Check it can still write every machine.
4. Fight model: RL practice focused on the PvP bot, then its exam.
5. Survival Planner: RL with a lighter load, last, because this job has crashed the GPU before.
Everything logs to overnight2_report.txt. A failed stage is logged and the chain moves on.
"""

import os
import re
import shutil
import time

os.environ["MCAI_RAM"] = "1"

import overnight as O

O.REPORT = os.path.join(O.HERE, "overnight2_report.txt")
HOUR = 3600


def exam():
    code, out = O.run(["exam_design.py", "designer.pt", "2000"], 2 * HOUR)
    with open(os.path.join(O.HERE, "overnight2_exam.txt"), "a", encoding="utf-8") as f:
        f.write(f"\n--- {time.strftime('%Y-%m-%d %H:%M')}\n{out}")
    m = re.search(r"solved: (\d+)/(\d+) \(([\d.]+)%\)", out)
    if not m:
        O.note(f"design exam failed to run (exit {code})")
        return None
    extra = re.search(r"Of those.*", out)
    O.note(f"DESIGN EXAM on goals it never saw: {m[1]}/{m[2]} solved ({m[3]}%). {extra[0] if extra else ''}")
    return float(m[3])


def keep(name, out):
    """Every step's full output is saved, so a failure can be read afterward."""
    with open(os.path.join(O.HERE, f"overnight2_{name}.txt"), "a", encoding="utf-8") as f:
        f.write(f"\n--- {time.strftime('%Y-%m-%d %H:%M')}\n{out}")


def why(out):
    lines = [l.strip() for l in out.strip().splitlines()]
    return lines[-1][:160] if lines else ""


def train(args, hours, label):
    code, out = O.run(["train.py", *args], hours * HOUR)
    keep("training", out)
    last = [l.strip() for l in out.splitlines() if "accuracy" in l][-1:]
    O.note(f"{label} finished (exit {code}) {last[0] if last else ''} {why(out) if code else ''}")
    return code == 0


def main():
    O.note("=== long run started ===")
    # dim 384 / 8 heads = 48 per head. Head sizes must be multiples of 8, or attention falls back
    # to a slow mode that runs out of GPU memory on long answers
    fresh = ["--task", "designer", "--dim", "384", "--layers", "7", "--ctx", "6144", "--steps", "60000", "--batch", "48"]
    if not train(fresh, 11, "15M model training"):
        model_file = os.path.join(O.HERE, "designer.pt")
        if not os.path.exists(model_file):
            O.note("training failed before its first save, stopping here: nothing else can run without it")
            return
        O.note("training stopped early, waiting 3 minutes then resuming from the last save")
        time.sleep(180)
        train(["--task", "designer", "--resume", "--steps", "30000", "--batch", "48"], 6, "15M model training, resumed")

    score = exam()
    for round_no in range(1, 3):
        if score is not None and score >= 95:
            break
        O.note(f"more design practice, round {round_no}")
        train(["--task", "designer", "--resume", "--steps", "20000", "--batch", "48"], 4, "extra training")
        score = exam()

    code, out = O.run(["check_machines.py", "designer.pt"], 2 * HOUR)
    m = re.search(r"\d+/\d+ machines exact", out)
    O.note(f"15M model writing machines from memory: {m[0] if m else 'check failed to run'}")

    code, out = O.run(["rl_fight.py", "--updates", "300", "--focus", "duel"], 3 * HOUR)
    keep("fight", out)
    O.note(f"Fight RL finished (exit {code}) {why(out)}")
    code, out = O.run(["exam_fight.py"], HOUR)
    for line in out.splitlines():
        if "won" in line or "passed" in line:
            O.note("  fight exam: " + line.strip())

    shutil.copy(os.path.join(O.HERE, "planner.pt"), os.path.join(O.HERE, "planner_before_rl.pt"))
    O.note("Planner RL starting (lighter load).")
    code, out = O.run(["rl_planner.py", "--updates", "300", "--games", "16"], 3 * HOUR)
    keep("planner", out)
    best = [l.strip() for l in out.splitlines() if "RL start" in l or "RL done" in l]
    O.note(f"Planner RL finished (exit {code}): {' / '.join(best)} {why(out) if code else ''}")
    O.note("=== long run finished ===")


if __name__ == "__main__":
    main()
