"""Circuits, second try: lessons with a clearance rule. Logs to overnight4_report.txt.

The AI's big circuits failed from shorts: 76% next to the levers, 82% on its own routes, a wire
drawn a block off beside another signal's. The teacher now keeps a block of air between
different signals' wires (circuit.NetRouter.CLEARANCE = 2), so one slip no longer touches.

1. lab-check the new teacher (every circuit right on all 16 rows, or stop)
2. write the new lesson bank (skipped if already written from this teacher); the old bank and
   the old homework corrections are kept under new names, not deleted
3. practice with homework and a lab test every 2 rounds, until 13/15 or no new best
"""

import json
import os
import re
import shutil

os.environ["MCAI_CLEARANCE"] = "2"      # every step below, and every step they start, uses it
os.environ["MCAI_RAM"] = "1"

import overnight as O
import overnight2 as T
import overnight4 as N
from data import encode, fmt

O.REPORT = os.path.join(O.HERE, "overnight4_report.txt")
NEW = os.path.join(O.HERE, "circuit_lessons_clear.jsonl")
BANK = os.path.join(O.HERE, "circuit_lessons.jsonl")
FIXES = os.path.join(O.HERE, "circuit_corrections.jsonl")


def main():
    O.note("=== circuits, second try: a block of air between different signals' wires ===")
    code, out = O.run(["test_circuits.py", "24"], 3 * T.HOUR)
    T.keep("circuits", out)
    O.note("teacher with clearance on the lab: " + (N.last(out, r"\d+/\d+ teacher circuits work.*") or f"failed {T.why(out)}"))
    m = re.search(r"(\d+)/(\d+) teacher circuits work", out)
    if not m or int(m[1]) < int(m[2]):
        O.note("not every teacher circuit works: not teaching it, stopping here")
        return
    if not (os.path.exists(NEW) and os.path.getmtime(NEW) > os.path.getmtime(os.path.join(O.HERE, "circuit.py"))):
        code, out = O.run(["build_circuit_bank.py", os.path.basename(NEW)], 6 * T.HOUR)
        O.note("lesson bank: " + (N.last(out, r"\d+/\d+ circuits written.*") or f"failed {T.why(out)}"))
        if code:
            return
    rows = [json.loads(l) for l in open(NEW, encoding="utf-8")]
    keep = [r for r in rows if len(encode(fmt(r[0], r[1]))) <= 6144]
    shutil.copy(BANK, os.path.join(O.HERE, "circuit_lessons_clearance1.jsonl"))
    with open(BANK + ".tmp", "w", encoding="utf-8") as f:
        for r in keep:
            f.write(json.dumps(r) + "\n")
    os.replace(BANK + ".tmp", BANK)
    if os.path.exists(FIXES):
        os.replace(FIXES, os.path.join(O.HERE, "circuit_corrections_clearance1.jsonl"))
    O.note(f"new lessons in use: {len(keep)} circuits (old bank kept as circuit_lessons_clearance1.jsonl)")
    N.keep_going(6, homework=True)


if __name__ == "__main__":
    main()
