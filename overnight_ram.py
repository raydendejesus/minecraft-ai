"""The RAM stage, after the overnight chain. Teaches the AI to write RAM sticks with repeats,
then has it build them on the lab server from its own answers. Logs to overnight_report.txt.
"""

import os
import re
import subprocess

os.environ["MCAI_RAM"] = "1"                  # the RAM sticks join the lessons for this stage

import overnight as O


def main():
    O.note("=== RAM stage started ===")
    for round_no in range(1, 5):
        O.note(f"RAM training round {round_no}: 15000 steps")
        code, out = O.run(["train.py", "--task", "machines", "--resume", "--steps", "15000", "--batch", "48"], 5 * 3600)
        O.note(f"training finished (exit {code})")
        good, total = O.write_check()
        O.note(f"writing test: the AI wrote {good} of {total} machines exactly, RAM sticks included")
        if good is not None and good == total:
            break
    for label, args, limit in (("16 bytes", ("4", "8"), 3600), ("64 bytes", ("6", "8"), 2 * 3600), ("128 bytes", ("7", "8"), 4 * 3600)):
        result = None
        for attempt in (1, 2):
            O.clear_lab_servers()
            code, out = O.run(["test_ai_machines.py", "ram", *args], limit)
            with open(os.path.join(O.HERE, f"overnight_build_ram_{args[0]}.txt"), "w", encoding="utf-8") as f:
                f.write(out)
            score = re.findall(r"^\d+/\d+ [^\n]*$", out, re.M)
            if score or code == 2:
                result = score[-1] if score else "the AI's answer couldn't be turned into blocks"
                break
            O.note(f"RAM {label} attempt {attempt} didn't finish (exit {code}), lab problem, not a score")
        O.note(f"AI BUILD RAM {label}: {result or 'no result, the lab failed twice'}")
    O.clear_lab_servers()
    O.note("=== RAM stage finished ===")


if __name__ == "__main__":
    main()
