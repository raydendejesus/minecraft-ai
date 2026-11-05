"""The PvP model: train it from scratch on the teacher's duels, then the PvP exam.
Logs to pvp_report.txt.

1. wait for pvp_lessons.jsonl (build_pvp_bank.py writes it on the CPU)
2. train pvp.pt from scratch: 4.8M parameters, short memory (a duel state is one line)
3. PvP exam against all 11 styles and the rulebook expert
"""

import os
import re
import time

import overnight as O
import overnight2 as T

O.REPORT = os.path.join(O.HERE, "pvp_report.txt")
BANK = os.path.join(O.HERE, "pvp_lessons.jsonl")


def main():
    O.note("=== the PvP model ===")
    while not os.path.exists(BANK) or os.path.exists(BANK + ".tmp"):
        time.sleep(60)
    with open(BANK, encoding="utf-8") as f:
        n = sum(1 for _ in f)
    O.note(f"lessons ready: {n:,} teacher moves")
    if not T.train(["--task", "pvp", "--ctx", "384", "--steps", "30000", "--batch", "256"], 6, "pvp training"):
        return
    code, out = O.run(["exam_pvp.py", "pvp.pt", "40"], 4 * T.HOUR)
    for line in out.splitlines():
        if line.strip().startswith("vs "):
            O.note("  " + line.strip())
    O.note(re.findall(r"PvP exam: .*", out)[-1] if "PvP exam:" in out else f"exam failed {T.why(out)}")
    O.note("=== finished ===")


if __name__ == "__main__":
    main()
