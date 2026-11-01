"""See exactly what the server replies while the lab's far corner loads, and how long it takes."""

import collections
import subprocess
import time

from lab import FLOOR_Y, Lab

lab = Lab()
real_start = Lab.reset_area
Lab.reset_area = lambda self: None     # only testing loading here
t0 = time.time()
try:
    lab.start(timeout=120)
    print(f"loaded in {time.time() - t0:.0f}s")
except Exception as e:
    print(f"failed after {time.time() - t0:.0f}s: {e}")
    replies = collections.Counter()
    for _ in range(40):
        for l in lab.cmd(f"setblock 120 {FLOOR_Y} 120 stone", wait=0.5):
            replies[l.split("]", 1)[-1].strip()[:80]] += 1
    print("replies in the next 20s:", dict(replies))
    print(" ".join(lab.cmd("tickingarea list", wait=1))[:300])
print("server alive:", lab.proc.poll() is None)
print(subprocess.run(["tasklist", "/FI", "IMAGENAME eq bedrock_server.exe"], capture_output=True, text=True).stdout[-200:])
lab.stop()
