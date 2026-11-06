"""Freeze every training job (and the lab server) while you play, then carry on exactly where it
stopped. Nothing is lost: the processes are only frozen, not stopped.

    python pause_training.py pause
    python pause_training.py resume

The Neural Viewer and the keep-awake helper keep running (they use almost nothing). A frozen
trainer still holds its share of GPU memory (at most half the card), but uses no GPU time.
"""

import ctypes
import json
import os
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
STATE = os.path.join(HERE, "paused.json")
KEEP_RUNNING = ("neural_view.py", "keep_awake.py", "pause_training.py")


def targets():
    out = subprocess.run(["powershell", "-NoProfile", "-Command",
                          "Get-CimInstance Win32_Process | Where-Object { ($_.Name -eq 'python.exe' -and "
                          "$_.CommandLine -like '*MinecraftAI*') -or ($_.Name -eq 'bedrock_server.exe' -and "
                          "$_.ExecutablePath -like '*MinecraftAI*') } | ForEach-Object { \"$($_.ProcessId)|$($_.CommandLine)\" }"],
                         capture_output=True, text=True).stdout
    found = []
    for line in out.splitlines():
        pid, _, cmd = line.partition("|")
        if pid.strip().isdigit() and not any(k in cmd for k in KEEP_RUNNING) and int(pid) != os.getpid():
            found.append((int(pid), cmd.strip()))
    return found


def _call(fn, pid):
    nt = ctypes.windll.ntdll
    h = ctypes.windll.kernel32.OpenProcess(0x0800, False, pid)      # PROCESS_SUSPEND_RESUME
    if not h:
        return False
    try:
        return getattr(nt, fn)(h) == 0
    finally:
        ctypes.windll.kernel32.CloseHandle(h)


def main():
    what = sys.argv[1] if len(sys.argv) > 1 else "pause"
    if what == "pause":
        procs = targets()
        done = [(pid, cmd) for pid, cmd in procs if _call("NtSuspendProcess", pid)]
        with open(STATE, "w", encoding="utf-8") as f:
            json.dump(done, f, indent=1)
        for pid, cmd in done:
            print(f"  frozen {pid}: {cmd[-80:]}")
        print(f"paused {len(done)} processes")
    else:
        if not os.path.exists(STATE):
            print("nothing was paused")
            return
        with open(STATE, encoding="utf-8") as f:
            done = json.load(f)
        ok = sum(_call("NtResumeProcess", pid) for pid, _ in done)
        os.replace(STATE, STATE + ".last")
        print(f"resumed {ok}/{len(done)} processes")


if __name__ == "__main__":
    main()
