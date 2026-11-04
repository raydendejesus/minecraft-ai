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
    python overnight4.py --until 6    practise and lab-test until its circuits work, up to 6 rounds
    python overnight4.py --until 6 --homework    the same, giving its mistakes extra practice
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
    if "--until" in sys.argv:
        keep_going(int(sys.argv[sys.argv.index("--until") + 1]), homework="--homework" in sys.argv)
        return
    if "--more" in sys.argv:
        rounds = int(sys.argv[sys.argv.index("--more") + 1])
        O.note(f"=== the designer keeps practising its circuits: {rounds} more rounds ===")
        practice_and_test(rounds)
        check_machines()
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
    check_machines()


def keep_going(max_rounds, lab_every=2, good_enough=13, patience=2, homework=False):
    """Practice in blocks of lab_every rounds, testing on the lab after each block. Stops once
    good_enough of 15 circuits work, after `patience` lab tests in a row with no new best, or
    after max_rounds. homework: before each block, mark its circuits for practice formulas and
    give the ones it got wrong extra practice (circuit_corrections.py)."""
    O.note(f"=== the designer practises until its circuits work (up to {max_rounds} rounds"
           + (", homework marked before each block" if homework else "") + ") ===")
    best, stale, done = -1, 0, 0
    while done < max_rounds:
        if homework:
            code, out = O.run(["circuit_corrections.py", "designer.pt", "120"], 2 * T.HOUR)
            O.note("homework: " + (last(out, r"clean circuits by size: .*") or f"failed {T.why(out)}"))
            O.note("  " + (last(out, r"\d+ corrections added.*") or ""))
        n = min(lab_every, max_rounds - done)
        good = practice_and_test(n)
        done += n
        if good is None:
            O.note("lab test didn't run: stopping")
            return
        if good >= good_enough:
            O.note(f"{good}/15 circuits work: good enough, stopping")
            break
        if good > best:
            best, stale = good, 0
        else:
            stale += 1
            if stale >= patience:
                O.note(f"no new best for {patience} lab tests (best {best}/15): stopping")
                break
    check_machines()


def practice_and_test(rounds):
    """rounds of practice, then the lab test. Returns how many AI circuits worked, or None."""
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
    m = re.search(r"work in the lab: (\d+)/\d+", out)
    return int(m[1]) if m else None


def check_machines():
    code, out = O.run(["check_machines.py", "designer.pt"], 2 * T.HOUR)
    O.note("machines from memory: " + (last(out, r"\d+/\d+ machines exact") or "check failed to run"))
    O.note("=== finished ===")


if __name__ == "__main__":
    main()
