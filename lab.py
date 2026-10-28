"""The Redstone Lab: a private copy of your Bedrock server (flat world, port 19140) used to
test circuits for real. Your actual world is never touched.

    from lab import Lab
    with Lab() as lab:
        print(lab.cmd("setblock 0 101 0 redstone_lamp"))

Circuits are built on a stone platform at y=100 around (0, 0). A ticking area keeps
those chunks running even with nobody online, so redstone actually updates.
"""

import os
import queue
import subprocess
import threading
import time

HERE = os.path.dirname(os.path.abspath(__file__))
LAB_DIR = os.path.join(HERE, "lab_server")
FLOOR_Y = 100


class Lab:
    def __init__(self, verbose=False):
        self.verbose = verbose
        self.lines = queue.Queue()
        self.proc = None

    def __enter__(self):
        self.start()
        return self

    def __exit__(self, *exc):
        self.stop()

    def start(self, timeout=120):
        self.proc = subprocess.Popen(
            [os.path.join(LAB_DIR, "bedrock_server.exe")], cwd=LAB_DIR, stdin=subprocess.PIPE,
            stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, bufsize=1,
            encoding="utf-8", errors="replace")
        threading.Thread(target=self._pump, daemon=True).start()
        end = time.time() + timeout
        while time.time() < end:
            try:
                line = self.lines.get(timeout=1)
            except queue.Empty:
                continue
            if "Server started" in line:
                break
        else:
            raise RuntimeError("lab server didn't start")
        self.cmd("tickingarea remove_all")
        self.cmd("tickingarea add -16 0 -16 79 319 79 lab true")
        self.cmd("gamerule doDaylightCycle false")
        self.reset_area()

    def _pump(self):
        for line in self.proc.stdout:
            line = line.rstrip("\n")
            if self.verbose:
                print("  |", line)
            self.lines.put(line)

    def cmd(self, command, wait=0.25):
        """Send one console command and return the console lines it produced."""
        while not self.lines.empty():
            self.lines.get_nowait()
        self.proc.stdin.write(command + "\n")
        self.proc.stdin.flush()
        out, end = [], time.time() + wait
        while time.time() < end:
            try:
                out.append(self.lines.get(timeout=max(0.01, end - time.time())))
            except queue.Empty:
                pass
        return out

    def reset_area(self):
        """Wipe the test area and lay a fresh stone floor."""
        self.cmd(f"fill -8 {FLOOR_Y} -8 63 {FLOOR_Y} 63 smooth_stone")
        for y in range(FLOOR_Y + 1, FLOOR_Y + 20, 4):
            self.cmd(f"fill -8 {y} -8 63 {y + 3} 63 air")

    def block_at(self, x, y, z, expected, timeout=5):
        """True if the block at x y z is `expected` (block states optional). Waits for the
        reply that names these coordinates, so a slow server can't cause a misread."""
        while not self.lines.empty():
            self.lines.get_nowait()
        self.proc.stdin.write(f"testforblock {x} {y} {z} {expected}\n")
        self.proc.stdin.flush()
        tag, end = f"{x},{y},{z}", time.time() + timeout
        while time.time() < end:
            try:
                line = self.lines.get(timeout=0.1)
            except queue.Empty:
                continue
            if tag in line:
                return "Successfully found" in line
        raise RuntimeError(f"no reply checking block at {tag}")

    def stop(self):
        if self.proc and self.proc.poll() is None:
            self.proc.stdin.write("stop\n")
            self.proc.stdin.flush()
            try:
                self.proc.wait(timeout=30)
            except subprocess.TimeoutExpired:
                self.proc.terminate()
