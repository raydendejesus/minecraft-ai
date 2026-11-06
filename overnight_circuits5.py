"""Circuits, another block of practice on the clearance lessons. Homework now marks all four
checks: shorts, gaps, wrong wiring (circuit.logic) and signals that die out before their gate
(circuit.weak, new: a repeater one block early made a 16-block run). 240 circuits per homework.
Logs to overnight4_report.txt.

    python overnight_circuits5.py
"""

import os

os.environ["MCAI_CLEARANCE"] = "2"      # the lessons in use came from this teacher
os.environ["MCAI_RAM"] = "1"

import overnight as O
import overnight4 as N

O.REPORT = os.path.join(O.HERE, "overnight4_report.txt")


if __name__ == "__main__":
    O.note("=== circuits: more practice, homework marks shorts, gaps, wrong wiring and weak signals ===")
    N.keep_going(8, homework=True, homework_n=240)
