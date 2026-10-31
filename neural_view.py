"""Neural Viewer: one live page showing what's happening on this PC right now.

    python neural_view.py        then open http://localhost:8842

It shows the job that's running. When a model is training, it shows the real example that model
is practicing, what it answered, and how its neurons fired (from live_state.json, written by the
training job). Lab tests have no model in them, so those show their progress only. Uses no GPU.
"""

import json
import os
import subprocess
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

HERE = os.path.dirname(os.path.abspath(__file__))
PORT = 8842
STALE = 30      # seconds before a model snapshot counts as finished

JOBS = (("test_ram.py", "Redstone test: RAM on the lab server", "ram128_run.txt"),
        ("test_adder.py", "Redstone test: adder on the lab server", None),
        ("test_decoder.py", "Redstone test: decoder on the lab server", None),
        ("test_lab.py", "Redstone test on the lab server", None),
        ("rl_planner.py", "Survival Planner practicing (RL)", "rl_run.txt"),
        ("rl_fight.py", "Fight model practicing (RL)", "rl_fight_log.txt"),
        ("exam_loop.py", "Fight exam", "exam_loop_log.txt"),
        ("castle_exam.py", "Castle exam", "castle_model_10.txt"),
        ("distill.py", "Collecting decisions for the Brain", "distill_log.txt"),
        ("train.py", "Model training", None),
        ("lab_play.py", "Lab open to play in", None))


def last_line(name):
    try:
        with open(os.path.join(HERE, name), encoding="utf-8", errors="replace") as f:
            lines = f.read().strip().splitlines()
        return lines[-1].strip() if lines else ""
    except OSError:
        return ""


def snapshot():
    procs = subprocess.run(
        ["powershell", "-NoProfile", "-Command",
         "Get-CimInstance Win32_Process -Filter \"Name='python.exe'\" | ForEach-Object { $_.CommandLine }"],
        capture_output=True, text=True).stdout
    job, detail = None, ""
    for script, label, log in JOBS:
        if script in procs:
            job, detail = label, last_line(log) if log else ""
            break
    out = {"job": job, "detail": detail, "clock": time.strftime("%I:%M:%S %p"), "gpu": None, "model": None}
    try:
        g = subprocess.run(["nvidia-smi", "--query-gpu=temperature.gpu,utilization.gpu,power.draw",
                            "--format=csv,noheader,nounits"], capture_output=True, text=True, timeout=5).stdout.split(",")
        out["gpu"] = {"temp": float(g[0]), "load": float(g[1]), "power": float(g[2])}
    except Exception:
        pass
    try:
        with open(os.path.join(HERE, "live_state.json"), encoding="utf-8") as f:
            m = json.load(f)
        m["live"] = time.time() - m["time"] < STALE
        out["model"] = m
    except (OSError, ValueError):
        pass
    return out


class Handler(BaseHTTPRequestHandler):
    def log_message(self, *a):
        pass

    def _send(self, body, kind="application/json", code=200):
        self.send_response(code)
        self.send_header("Content-Type", kind)
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self):
        path = self.path.split("?")[0]
        if path == "/":
            with open(os.path.join(HERE, "neural.html"), "rb") as f:
                self._send(f.read(), "text/html; charset=utf-8")
        elif path == "/api/live":
            self._send(json.dumps(snapshot()).encode())
        else:
            self._send(b"{}", code=404)


if __name__ == "__main__":
    print(f"Neural Viewer running at http://localhost:{PORT}")
    ThreadingHTTPServer(("127.0.0.1", PORT), Handler).serve_forever()
