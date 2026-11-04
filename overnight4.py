"""Overnight: the designer learns to build its own circuits from blocks, on top of everything else
it knows. Logs to overnight4_report.txt.

1. lab-check the teacher's circuits (the lessons must work before the AI learns them)
2. write the circuit lesson bank
3. practice rounds: the designer keeps its full lesson mix, with circuits added to the long
   lessons. After each round: can it write circuits for its OWN formulas (offline check), and has
   it kept its design skill (per-level exam)?
4. the real test on the lab: AI-designed, AI-built circuits for goals it never saw
5. machines from memory, to make sure nothing was forgotten

    python overnight4.py              all of it
    python overnight4.py --more 3     3 more practice rounds (teacher and lesson bank already done)
"""

import os
import re
import sys

os.environ["MCAI_RAM"] = "1"

import overnight as O
import overnight2 as T

O.REPORT = os.path.join(O.HERE, "overnight4_report.txt")
ROUNDS = 3


def last(out, pattern):
    hits = re.findall(pattern, out)
    return hits[-1] if hits else None


def main():
    if "--more" in sys.argv:
        rounds = int(sys.argv[sys.argv.index("--more") + 1])
        O.note(f"=== the designer keeps practising its circuits: {rounds} more rounds ===")
        practice_and_test(rounds)
        return
    O.note("=== the designer learns to build its circuits ===")
    code, out = O.run(["test_circuits.py", "24"], 3 * T.HOUR)
    T.keep("circuits", out)
    O.note("teacher circuits on the lab: " + (last(out, r"\d+/\d+ teacher circuits work.*") or f"failed to run {T.why(out)}"))
    m = re.search(r"(\d+)/(\d+) teacher circuits work", out)
    if not m or int(m[1]) < int(m[2]):
        O.note("some teacher circuits failed in the lab: not teaching broken lessons, stopping here")
        for line in out.splitlines():
            if "first wrong" in line:
                O.note("  " + line.strip())
        return

    bank, teacher = (os.path.join(O.HERE, n) for n in ("circuit_lessons.jsonl", "circuit.py"))
    if os.path.exists(bank) and os.path.getmtime(bank) > os.path.getmtime(teacher):
        O.note("lesson bank already written from the current teacher")
    else:
        code, out = O.run(["build_circuit_bank.py"], 2 * T.HOUR)
        O.note("lesson bank: " + (last(out, r"\d+/\d+ circuits written.*") or f"failed {T.why(out)}"))
        if code:
            return
    practice_and_test(ROUNDS)


def practice_and_test(rounds):
    for round_no in range(1, rounds + 1):
        O.note(f"practice round {round_no} of {rounds}: 20,000 steps, circuits added to the full mix")
        T.train(["--task", "designer", "--resume", "--steps", "20000", "--batch", "48"], 4, "practice")
        code, out = O.run(["test_ai_circuits.py", "designer.pt", "3", "--offline"], T.HOUR)
        T.keep("ai_circuits", out)
        O.note("  its own formulas -> blocks (offline): " + (last(out, r"\d+ goals: .*") or f"failed {T.why(out)}"))
        code, out = O.run(["exam_design.py", "designer.pt"], 2 * T.HOUR)
        T.keep("exam", out)
        levels = re.findall(r"goals needing (\d+) gates: \d+/\d+ \(([\d.]+)%\)", out)
        O.note("  design exam: " + "  ".join(f"{g}:{p}%" for g, p in levels))

    code, out = O.run(["test_ai_circuits.py", "designer.pt", "2"], 3 * T.HOUR)
    T.keep("ai_circuits", out)
    for line in out.splitlines():
        if "/16" in line:
            O.note("  lab: " + line.strip())
    O.note(last(out, r"AI-designed, AI-built circuits that work in the lab: .*") or f"lab test failed {T.why(out)}")

    code, out = O.run(["check_machines.py", "designer.pt"], 2 * T.HOUR)
    O.note("machines from memory: " + (last(out, r"\d+/\d+ machines exact") or "check failed to run"))
    O.note("=== finished ===")


if __name__ == "__main__":
    main()
