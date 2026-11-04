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
    def __init__(self, verbose=False, far_z=120, far_x=120):
        """far_z / far_x: how far south / east the test area reaches. A ticking area is limited
        to 100 chunks, so big builds use several, tiled along x and z."""
        self.far_z = far_z
        self.far_x = far_x
        self.verbose = verbose
        self.lines = queue.Queue()
        self.proc = None

    def __enter__(self):
        try:
            self.start()
        except BaseException:
            self.stop()         # a failed start must not leave a server holding the world
            raise
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
        # 9 chunks wide x 11 long = 99 chunks per area
        n = 0
        for x0 in range(-16, self.far_x + 1, 144):
            for z0 in range(-16, self.far_z + 1, 176):
                self.cmd(f"tickingarea add {x0} 0 {z0} {x0 + 143} 319 {z0 + 175} lab{n} true")
                n += 1
        self.cmd("gamerule doDaylightCycle false")
        for _ in range(120):                     # wait until the far corner has actually loaded
            # "couldn't be placed" also proves it's loaded (the block is already there);
            # an unloaded spot says "outside of the world"
            reply = " ".join(self.cmd(f"setblock {self.far_x} {FLOOR_Y} {self.far_z} stone", wait=0.5))
            if "placed" in reply:
                break
        else:
            raise RuntimeError(f"lab area didn't load, last reply: {reply[-120:]!r}")
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
        # fills are size-limited, so one layer and 129 x 200 blocks at a time
        for x0 in range(-8, self.far_x + 1, 129):
            x1 = min(x0 + 128, self.far_x)
            for z0 in range(-8, self.far_z + 1, 200):
                z1 = min(z0 + 199, self.far_z)
                self.cmd(f"fill {x0} {FLOOR_Y} {z0} {x1} {FLOOR_Y} {z1} smooth_stone", wait=0.1)
                for y in range(FLOOR_Y + 1, FLOOR_Y + 13):
                    self.cmd(f"fill {x0} {y} {z0} {x1} {y} {z1} air", wait=0.1)

    def sync(self, timeout=600):
        """Wait until the server has worked through every command sent so far (big builds
        queue up faster than it can place them)."""
        self.block_at(-8, FLOOR_Y, -8, "smooth_stone", timeout=timeout)

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
