"""Keeps training from lagging the PC. Settings live in gentle.json and are re-read every 20s,
so you can change them while training runs:

    pause_while_gaming  true = stop completely while Minecraft (or another listed game) is open
    duty                fraction of time the GPU works (0.5 = half, 1.0 = flat out)
    vram_fraction       share of the 24 GB the trainer may use (read once at start)
    priority            "idle", "below_normal" or "normal" CPU priority (read once at start)
    max_temp            GPU temperature that pauses training until it cools to resume_temp
    slow_temp           above this, training gradually eases off so it rarely reaches max_temp
Temperatures are logged to gpu_temp_log.csv every 30s.

    import gentle; gentle.setup()       # once at start
    gentle.step(seconds_the_step_took)  # after every training step
Set MCAI_FULL_SPEED=1 to turn all of this off.
"""

import ctypes
import json
import os
import subprocess
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
CONFIG_PATH = os.path.join(HERE, "gentle.json")
GAMES = ["Minecraft.Windows.exe", "javaw.exe", "eldenring.exe", "SkyrimSE.exe"]
DEFAULTS = {"pause_while_gaming": True, "duty": 0.5, "vram_fraction": 0.25, "priority": "idle"}
PRIORITIES = {"idle": 0x40, "below_normal": 0x4000, "normal": 0x20}
FULL = os.environ.get("MCAI_FULL_SPEED") == "1"
_cfg, _cfg_time = dict(DEFAULTS), 0.0
_last_check, _gaming = 0.0, False


def config():
    global _cfg, _cfg_time
    if time.time() - _cfg_time > 20:
        _cfg_time = time.time()
        try:
            with open(CONFIG_PATH, encoding="utf-8") as f:
                _cfg = {**DEFAULTS, **json.load(f)}
        except (OSError, ValueError):
            _cfg = dict(DEFAULTS)
    return _cfg


def setup():
    if FULL:
        return
    cfg = config()
    if sys.platform == "win32":
        ctypes.windll.kernel32.SetPriorityClass(ctypes.windll.kernel32.GetCurrentProcess(),
                                                PRIORITIES.get(cfg["priority"], 0x40))
    try:
        import torch
        if torch.cuda.is_available():
            torch.cuda.set_per_process_memory_fraction(float(cfg["vram_fraction"]))
    except Exception:
        pass


def gaming():
    global _last_check, _gaming
    if time.time() - _last_check > 20:
        _last_check = time.time()
        try:
            out = subprocess.run(["tasklist"], capture_output=True, text=True, timeout=10).stdout
            _gaming = any(g.lower() in out.lower() for g in GAMES)
        except Exception:
            _gaming = False
    return _gaming


TEMP_LOG = os.path.join(HERE, "gpu_temp_log.csv")
_gpu, _gpu_time, _log_time = (0, 0, 0.0), 0.0, 0.0


def gpu():
    """(temperature C, load %, power W), checked at most every 5s."""
    global _gpu, _gpu_time, _log_time
    if time.time() - _gpu_time > 5:
        _gpu_time = time.time()
        try:
            out = subprocess.run(["nvidia-smi", "--query-gpu=temperature.gpu,utilization.gpu,power.draw",
                                  "--format=csv,noheader,nounits"], capture_output=True, text=True,
                                 timeout=10).stdout.strip().split(",")
            _gpu = (float(out[0]), float(out[1]), float(out[2]))
        except Exception:
            pass
        if time.time() - _log_time > 10:
            _log_time = time.time()
            new = not os.path.exists(TEMP_LOG)
            with open(TEMP_LOG, "a", encoding="utf-8") as f:
                if new:
                    f.write("time,temp_c,load_pct,power_w\n")
                f.write(f"{time.strftime('%Y-%m-%d %H:%M:%S')},{_gpu[0]:.0f},{_gpu[1]:.0f},{_gpu[2]:.0f}\n")
    return _gpu


def step(took):
    if FULL:
        return
    cfg = config()
    duty = min(1.0, max(0.05, float(cfg["duty"])))
    temp = gpu()[0]
    hot, cool, slow_from = float(cfg.get("max_temp", 90)), float(cfg.get("resume_temp", 75)), float(cfg.get("slow_temp", 82))
    if temp >= hot:
        print(f"  (GPU at {temp:.0f}C, hit the {hot:.0f}C limit: pausing until it cools to {cool:.0f}C)", flush=True)
        while gpu()[0] > cool:
            time.sleep(5)
        print(f"  (GPU back to {gpu()[0]:.0f}C, resuming)", flush=True)
    elif temp >= slow_from:
        duty *= max(0.2, (hot - temp) / (hot - slow_from))   # ease off as it heats up
    if duty < 1.0:
        time.sleep(took * (1 - duty) / duty)
    announced = False
    while config()["pause_while_gaming"] and gaming():
        if not announced:
            print("  (paused: you're playing, training resumes when the game closes)", flush=True)
            announced = True
        time.sleep(20)
