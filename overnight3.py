"""Keep practicing design until EVERY difficulty level passes 95% on goals it never saw, then let
the other models practice. Logs to overnight2_report.txt.

    python overnight3.py                          practice, then machines check, Fight RL, Planner RL
    python overnight3.py --design-only --rounds 12   practice only (stops early once every level passes)
"""

import os
import re
import shutil
import sys

os.environ["MCAI_RAM"] = "1"

import overnight as O
import overnight2 as T

ROUNDS = int(sys.argv[sys.argv.index("--rounds") + 1]) if "--rounds" in sys.argv else 8
DESIGN_ONLY = "--design-only" in sys.argv


def level_exam():
    code, out = O.run(["exam_design.py", "designer.pt"], 2 * T.HOUR)
    T.keep("exam", out)
    levels = re.findall(r"goals needing (\d+) gates: (\d+/\d+) \(([\d.]+)%\)", out)
    verdict = re.search(r"Every level at 95%: (YES|NO).*", out)
    if not verdict:
        O.note(f"design exam failed to run (exit {code}) {T.why(out)}")
        return False
    O.note("DESIGN EXAM by level: " + "  ".join(f"{g} gates {p}%" for g, _, p in levels))
    O.note("  " + verdict[0])
    return verdict[1] == "YES"


def main():
    O.note("=== practice until every level passes 95% ===")
    for round_no in range(1, ROUNDS + 1):
        if level_exam():
            O.note("every level passed")
            break
        O.note(f"design practice round {round_no} of {ROUNDS}: 20,000 steps")
        T.train(["--task", "designer", "--resume", "--steps", "20000", "--batch", "48"], 4, "practice")
    else:
        level_exam()
        O.note("out of practice rounds: the report above shows where it stands")
    if DESIGN_ONLY:
        O.note("=== finished ===")
        return

    code, out = O.run(["check_machines.py", "designer.pt"], 2 * T.HOUR)
    m = re.search(r"\d+/\d+ machines exact", out)
    O.note(f"15M model writing machines from memory: {m[0] if m else 'check failed to run'}")

    code, out = O.run(["rl_fight.py", "--updates", "300", "--focus", "duel"], 3 * T.HOUR)
    T.keep("fight", out)
    O.note(f"Fight RL finished (exit {code}) {T.why(out)}")
    code, out = O.run(["exam_fight.py"], T.HOUR)
    for line in out.splitlines():
        if "won" in line or "passed" in line:
            O.note("  fight exam: " + line.strip())

    shutil.copy(os.path.join(O.HERE, "planner.pt"), os.path.join(O.HERE, "planner_before_rl.pt"))
    code, out = O.run(["rl_planner.py", "--updates", "300", "--games", "16"], 3 * T.HOUR)
    T.keep("planner", out)
    best = [l.strip() for l in out.splitlines() if "RL start" in l or "RL done" in l]
    O.note(f"Planner RL finished (exit {code}): {' / '.join(best)} {T.why(out) if code else ''}")
    O.note("=== finished ===")


if __name__ == "__main__":
    main()
