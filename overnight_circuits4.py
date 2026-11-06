"""Circuits, another block of practice on the clearance lessons. Homework now also marks circuits
whose wiring computes the wrong thing (circuit.logic: a signal brought to the wrong gate input),
which shorts and gaps both missed in the lab, and marks twice as many circuits (240) so the
corrections cover more formulas. Logs to overnight4_report.txt.

    python overnight_circuits4.py
"""

import os

os.environ["MCAI_CLEARANCE"] = "2"      # the lessons in use came from this teacher
os.environ["MCAI_RAM"] = "1"

import overnight as O
import overnight4 as N

O.REPORT = os.path.join(O.HERE, "overnight4_report.txt")


if __name__ == "__main__":
    O.note("=== circuits: more practice, homework also marks wrong wiring, 240 circuits ===")
    N.keep_going(8, homework=True, homework_n=240)
