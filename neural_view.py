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

JOBS = (("test_ai_machines.py", "The AI's build is being tested on the lab server", "overnight_report.txt"),
        ("check_machines.py", "The AI is writing out every machine from memory", "overnight_report.txt"),
        ("overnight", "Overnight chain", "overnight_report.txt"),
        ("test_ram.py", "Redstone test: RAM on the lab server", "ram128_run.txt"),
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


MODEL_FILES = (("machines", "builder_machines.pt"), ("merged", "builder_merged.pt"), ("planner", "planner.pt"),
               ("Survival Planner", "planner.pt"), ("fight", "fight.pt"), ("Fight", "fight.pt"), ("builder", "builder.pt"))
SHOWN = 20          # neurons drawn per layer
_weights = {"file": None, "mtime": None, "state": None}
_net = {"time": None, "net": None}


def connections(m):
    """Which neurons to draw, and how strongly each drives the next layer's, from the real weights.
    Read from the saved model on the CPU, so training is never touched."""
    import torch
    if _net["time"] == m["time"]:
        return _net["net"]
    name = next((f for key, f in MODEL_FILES if key in m["job"]), None)
    path = os.path.join(HERE, name) if name else None
    if not path or not os.path.exists(path):
        return None
    mtime = os.path.getmtime(path)
    if _weights["file"] != path or _weights["mtime"] != mtime:
        try:
            state = torch.load(path, map_location="cpu")["model"]
        except Exception:
            state = None                                 # caught it mid-save, use the last good one
        if state is not None:
            keys = [k for k in state if k.endswith(("mlp.0.weight", "mlp.2.weight"))]
            _weights.update(file=path, mtime=mtime, state={k: state[k] for k in keys})
    if _weights["state"] is None:
        return None
    layers = len(m["frames"][0]["grids"])
    picks = []
    for L in range(layers):
        peak = [0] * len(m["frames"][0]["grids"][L])
        for fr in m["frames"]:
            for i, ch in enumerate(fr["grids"][L]):
                peak[i] = max(peak[i], ord(ch) - 48)
        picks.append(sorted(sorted(range(len(peak)), key=lambda i: -peak[i])[:SHOWN]))
    links = []
    w = _weights["state"]
    for L in range(layers - 1):
        a, b = torch.tensor(picks[L]), torch.tensor(picks[L + 1])
        M = w[f"blocks.{L + 1}.mlp.0.weight"][b] @ w[f"blocks.{L}.mlp.2.weight"][:, a]
        links.append([[round(float(v), 3) for v in row] for row in M.T])
    _net.update(time=m["time"], net={"picks": picks, "links": links})
    return _net["net"]


def snapshot():
    procs = subprocess.run(
        ["powershell", "-NoProfile", "-Command",
         "Get-CimInstance Win32_Process -Filter \"Name='python.exe'\" | ForEach-Object { $_.CommandLine }"],
        capture_output=True, text=True).stdout
    job, detail = None, ""
    for script, label, log in JOBS:
        if script in procs:
            job, detail = label, last_line(log) if log else ""
            if script == "test_ai_machines.py":          # say which machine, and the last result
                what = procs.split("test_ai_machines.py", 1)[1].splitlines()[0].strip()
                job = f"{label}: {what}"
                detail = f"No model is running in this step. Last result: {detail}"
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
        m["net"] = connections(m)
    except (OSError, ValueError, KeyError, IndexError):
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
