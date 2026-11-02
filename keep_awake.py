"""Keeps Windows from going to sleep while jobs are queued, then lets go.

This asks Windows nicely (like a video player does) and changes no settings. The screens can
still turn off. It ends by itself when nothing is pending or running in pipeline_queue.json.
"""

import ctypes
import json
import os
import time

HERE = os.path.dirname(os.path.abspath(__file__))
ES_CONTINUOUS, ES_SYSTEM_REQUIRED = 0x80000000, 0x00000001


def jobs_left():
    try:
        with open(os.path.join(HERE, "pipeline_queue.json"), encoding="utf-8") as f:
            return any(j.get("status") in ("pending", "running") for j in json.load(f))
    except (OSError, ValueError):
        return True                 # the file was mid-write, ask again next time


while True:
    ctypes.windll.kernel32.SetThreadExecutionState(ES_CONTINUOUS | ES_SYSTEM_REQUIRED)
    if not jobs_left():
        break
    time.sleep(60)
ctypes.windll.kernel32.SetThreadExecutionState(ES_CONTINUOUS)
