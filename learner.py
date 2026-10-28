"""Keeps the tiny models learning in the background while the app runs.

Every 10 minutes:
  * 3+ new Builder corrections since its last training  -> retrain the Builder on them
  * 3+ new Planner corrections                          -> retrain the Planner
  * 24h since the last RL session                       -> short RL session for the Planner
Only one job runs at a time; progress goes to learner_log.txt.
"""

import json
import os
import subprocess
import sys
import threading
import time

import data
import planner_data

HERE = os.path.dirname(os.path.abspath(__file__))
STATE_PATH = os.path.join(HERE, "learn_state.json")
LOG_PATH = os.path.join(HERE, "learner_log.txt")
PY = sys.executable


def _load():
    try:
        with open(STATE_PATH, encoding="utf-8") as f:
            return json.load(f)
    except (OSError, ValueError):
        return {"builder": len(data.load_corrections()),
                "planner": len(planner_data.load_corrections()), "last_rl": time.time()}


def _save(state):
    with open(STATE_PATH, "w", encoding="utf-8") as f:
        json.dump(state, f)


class Learner:
    def __init__(self, min_new=3, rl_every_hours=24, interval=600):
        self.min_new, self.rl_every, self.interval = min_new, rl_every_hours * 3600, interval
        self.proc, self.job = None, None

    def busy(self):
        return self.proc is not None and self.proc.poll() is None

    def _run(self, job, args):
        log = open(LOG_PATH, "a", encoding="utf-8")
        log.write(f"\n=== {time.strftime('%Y-%m-%d %H:%M')} {job} ===\n")
        log.flush()
        self.proc = subprocess.Popen([PY, "-u", *args], cwd=HERE, stdout=log, stderr=subprocess.STDOUT)
        self.job = job

    def tick(self):
        if self.busy():
            return
        state = _load()
        n_builder = len(data.load_corrections())
        n_planner = len(planner_data.load_corrections())
        if n_builder - state["builder"] >= self.min_new:
            state["builder"] = n_builder
            self._run("builder: learning your corrections", ["train.py", "--resume"])
        elif n_planner - state["planner"] >= self.min_new:
            state["planner"] = n_planner
            self._run("planner: learning your corrections", ["train.py", "--task", "planner", "--resume"])
        elif time.time() - state["last_rl"] > self.rl_every:
            state["last_rl"] = time.time()
            self._run("planner: RL practice", ["rl_planner.py", "--updates", "100"])
        _save(state)

    def start(self):
        def loop():
            time.sleep(60)  # let the app settle first
            while True:
                try:
                    self.tick()
                except Exception as e:
                    with open(LOG_PATH, "a", encoding="utf-8") as f:
                        f.write(f"learner error: {e}\n")
                time.sleep(self.interval)
        threading.Thread(target=loop, daemon=True, name="learner").start()

    def status(self):
        return {"busy": self.busy(), "job": self.job if self.busy() else None}
