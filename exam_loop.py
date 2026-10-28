"""Keep practicing until the Fight model passes its final exam.

Each round: 100 RL practice updates, then the exam (hordes of 2/3/5 and 1v1 vs the PvP bot).
Stops as soon as every test passes, or after --rounds rounds.

    python exam_loop.py --rounds 15
"""

import argparse
import subprocess
import sys

PY = sys.executable


def exam():
    """Returns (passed everything, which kind of fight to focus practice on next)."""
    out = subprocess.run([PY, "exam_fight.py"], capture_output=True, text=True).stdout
    print(out, flush=True)
    failing = [l for l in out.splitlines() if "not yet" in l]
    focus = "duel" if any("1v1" in l for l in failing) else "horde" if failing else None
    return "4/4 tests passed" in out, focus


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--rounds", type=int, default=15)
    args = ap.parse_args()
    print("== exam before practice ==", flush=True)
    passed, focus = exam()
    if passed:
        print("PASSED the fight exam")
        return
    for r in range(1, args.rounds + 1):
        print(f"== practice round {r}/{args.rounds} (focus: {focus}) ==", flush=True)
        subprocess.run([PY, "-u", "rl_fight.py", "--updates", "100", "--focus", focus])
        passed, focus = exam()
        if passed:
            print(f"PASSED the fight exam after {r} practice rounds")
            return
    print("Not passed yet: more rounds, a bigger model, or a better teacher needed")


if __name__ == "__main__":
    main()
