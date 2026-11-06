"""Circuits, more practice on the clearance lessons (already in use, already lab-checked by
overnight_circuits2.py). Homework now marks gaps as well as shorts (circuit.breaks), so those
mistakes get extra practice too. Logs to overnight4_report.txt.

    python overnight_circuits3.py
"""

import os

os.environ["MCAI_CLEARANCE"] = "2"      # the lessons in use came from this teacher
os.environ["MCAI_RAM"] = "1"

import overnight as O
import overnight4 as N

O.REPORT = os.path.join(O.HERE, "overnight4_report.txt")


if __name__ == "__main__":
    O.note("=== circuits: more practice, homework marks shorts and gaps ===")
    N.keep_going(6, homework=True)
