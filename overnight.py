"""The overnight chain. Runs after training, unattended, and logs to overnight_report.txt.

1. Ask the AI to write all 12 machines. If any are wrong, train more and ask again (5 rounds max).
2. Have the AI build the 4-bit machines on the lab server, using only its own blocks.
Failures are retried and logged; one failure never stops the rest.
"""

import os
import re
import subprocess
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
REPORT = os.path.join(HERE, "overnight_report.txt")
PY = sys.executable
ROUNDS = 5
MORE_STEPS = "10000"
BUILDS = [("counter", "4"), ("adder", "4"), ("decoder", "4"), ("alu", "4")]


def note(msg):
    line = f"{time.strftime('%Y-%m-%d %H:%M')}  {msg}"
    print(line, flush=True)
    with open(REPORT, "a", encoding="utf-8") as f:
        f.write(line + "\n")


def run(args, timeout):
    """Run a step and return (exit code, output). A hang is killed, not waited on forever."""
    try:
        r = subprocess.run([PY, "-u", *args], cwd=HERE, capture_output=True, text=True,
                           encoding="utf-8", errors="replace", timeout=timeout)
        return r.returncode, r.stdout + r.stderr
    except subprocess.TimeoutExpired as e:
        out = e.stdout.decode(errors="replace") if isinstance(e.stdout, bytes) else (e.stdout or "")
        return -1, out + "\n(step timed out)"


def clear_lab_servers():
    subprocess.run(["powershell", "-NoProfile", "-Command",
                    "Get-Process bedrock_server -ErrorAction SilentlyContinue | Where-Object "
                    "{ $_.Path -like '*MinecraftAI\\lab_server*' } | Stop-Process -Force"], capture_output=True)
    time.sleep(5)


def write_check():
    code, out = run(["check_machines.py", "builder_machines.pt"], 3 * 3600)
    with open(os.path.join(HERE, "overnight_machines.txt"), "a", encoding="utf-8") as f:
        f.write(f"\n--- {time.strftime('%Y-%m-%d %H:%M')}\n{out}")
    m = re.search(r"(\d+)/(\d+) machines exact", out)
    return (int(m[1]), int(m[2])) if m else (None, None)


def main():
    note("=== overnight chain started ===")
    for round_no in range(1, ROUNDS + 1):
        good, total = write_check()
        if good is None:
            note(f"writing test {round_no} failed to run, waiting 2 minutes")
            time.sleep(120)
        else:
            note(f"writing test {round_no}: the AI wrote {good} of {total} machines exactly")
            if good == total:
                break
        if round_no == ROUNDS:
            note("still not perfect after the last round, moving on to building anyway")
            break
        note(f"training {MORE_STEPS} more steps")
        code, out = run(["train.py", "--task", "machines", "--resume", "--steps", MORE_STEPS, "--batch", "48"], 4 * 3600)
        tail = [l for l in out.splitlines() if "accuracy" in l or "Error" in l][-1:]
        note(f"training finished (exit {code}) {tail[0].strip() if tail else ''}")
        if code != 0:
            time.sleep(120)              # e.g. the GPU dropped out: give it a moment, go again

    for kind, bits in BUILDS:
        result = None
        for attempt in (1, 2):
            clear_lab_servers()
            code, out = run(["test_ai_machines.py", kind, bits], 3600)
            with open(os.path.join(HERE, f"overnight_build_{kind}.txt"), "w", encoding="utf-8") as f:
                f.write(out)
            score = re.findall(r"^\d+/\d+ [^\n]*$", out, re.M)
            if score or code == 2:
                result = score[-1] if score else "the AI's answer couldn't be turned into blocks"
                break
            note(f"build {kind} attempt {attempt} didn't finish (exit {code}), lab problem, not a score")
        note(f"AI BUILD {kind} {bits}: {result or 'no result, the lab failed twice'}")
    clear_lab_servers()
    note("=== overnight chain finished ===")


if __name__ == "__main__":
    main()
