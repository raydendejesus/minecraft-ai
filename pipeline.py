"""Training queue: runs the jobs in pipeline_queue.json one at a time, automatically.

* waits until no other training job is running, then starts the next pending job
* marks each job done/failed in the queue file, with times, and logs to pipeline_log.txt
* when the queue is empty it keeps waiting, so jobs added later start on their own

Add a job by appending to pipeline_queue.json:
    {"name": "planner RL", "cmd": ["rl_planner.py", "--updates", "300"], "status": "pending"}

    python pipeline.py
"""

import json
import os
import subprocess
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
QUEUE = os.path.join(HERE, "pipeline_queue.json")
LOG = os.path.join(HERE, "pipeline_log.txt")
PY = sys.executable
TRAINING_SCRIPTS = ("train.py", "rl_planner.py", "rl_fight.py", "exam_loop.py", "distill.py")


def log(msg):
    line = f"{time.strftime('%Y-%m-%d %H:%M')}  {msg}"
    print(line, flush=True)
    with open(LOG, "a", encoding="utf-8") as f:
        f.write(line + "\n")


def load():
    with open(QUEUE, encoding="utf-8") as f:
        return json.load(f)


def save(q):
    with open(QUEUE, "w", encoding="utf-8") as f:
        json.dump(q, f, indent=2)


def other_training_running():
    """Is a training script already running (one we didn't start)?"""
    out = subprocess.run(
        ["powershell", "-NoProfile", "-Command",
         "Get-CimInstance Win32_Process -Filter \"Name='python.exe'\" | ForEach-Object { $_.CommandLine }"],
        capture_output=True, text=True).stdout
    me = str(os.getpid())
    return any(s in line for line in out.splitlines() for s in TRAINING_SCRIPTS if me not in line)


def main():
    log("queue started")
    announced_wait = announced_idle = False
    while True:
        if other_training_running():
            if not announced_wait:
                log("waiting for the current training job to finish")
                announced_wait = True
            time.sleep(30)
            continue
        announced_wait = False
        q = load()
        job = next((j for j in q if j.get("status") == "pending"), None)
        if job is None:
            if not announced_idle:
                log("queue empty, waiting for new jobs")
                announced_idle = True
            time.sleep(60)
            continue
        announced_idle = False
        log(f"START {job['name']}")
        job["status"], job["started"] = "running", time.strftime("%Y-%m-%d %H:%M")
        save(q)
        out_path = os.path.join(HERE, job.get("log", job["cmd"][0].replace(".py", "") + "_queue_log.txt"))
        with open(out_path, "w", encoding="utf-8") as out:
            code = subprocess.run([PY, "-u", *job["cmd"]], cwd=HERE, stdout=out, stderr=subprocess.STDOUT).returncode
        q = load()
        for j in q:
            if j["name"] == job["name"] and j.get("status") == "running":
                j["status"] = "done" if code == 0 else "failed"
                j["finished"] = time.strftime("%Y-%m-%d %H:%M")
        save(q)
        log(f"{'DONE' if code == 0 else 'FAILED'} {job['name']} (exit {code}, output in {os.path.basename(out_path)})")


if __name__ == "__main__":
    main()
