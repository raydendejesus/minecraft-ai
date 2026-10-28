"""Check every redstone design's full truth table on the lab server.

    python test_lab.py            test all gates
    python test_lab.py and xor    test some
"""

import itertools
import sys
import time

import redstone_lib as R
from lab import FLOOR_Y, Lab

Y = FLOOR_Y + 1


def place(lab, parts, base):
    bx, bz = base
    for x, y, z, b in parts:
        lab.cmd(f"setblock {bx + x} {Y + y} {bz + z} {b}", wait=0.05)


def run_gate(lab, name, base):
    parts, inputs, outs, fn = R.GATES[name]()
    if not isinstance(outs, list):
        outs, single = [outs], fn
        fn = lambda *a: (single(*a),)
    ok = True
    rows = []
    for combo in itertools.product([0, 1], repeat=len(inputs)):
        clear(lab, base)
        place(lab, parts, base)
        for (x, z), v in zip(inputs, combo):
            if v:  # swap the lever for a redstone block = input switched on
                lab.cmd(f"setblock {base[0] + x} {Y} {base[1] + z} redstone_block", wait=0.05)
        time.sleep(1.2)
        got = "".join(str(int(lab.block_at(base[0] + x, Y, base[1] + z, "lit_redstone_lamp")))
                      for x, z in outs)
        want = "".join(str(int(bool(v))) for v in fn(*combo))
        ok &= got == want
        rows.append(f"{''.join(map(str, combo))}->{got}{'' if got == want else ' (WRONG, want ' + want + ')'}")
    print(f"  {name:8s} {'PASS' if ok else 'FAIL'}   " + "  ".join(rows), flush=True)
    return ok


def run_memory(lab, name, base):
    """Memory can't be checked with a truth table: flip inputs step by step and check it holds."""
    parts, inputs, outs, steps = R.MEMORY[name]()
    clear(lab, base)
    place(lab, parts, base)
    time.sleep(1.0)
    ok, rows = True, []
    def set_inputs(names, on):
        for nm in names:
            x, z = inputs[nm]
            b = "redstone_block" if nm in on else R.lever(0, 0)[3]
            lab.cmd(f"setblock {base[0] + x} {Y} {base[1] + z} {b}", wait=0.05)

    data = [n for n in inputs if n != "W"]
    for on, want in steps:
        # Like a real computer: write switches off before data changes, and only switches
        # on after the data is steady, otherwise lock and data race each other.
        if "W" in inputs and "W" not in on:
            set_inputs(["W"], on)
            time.sleep(0.8)
        set_inputs(data, on)
        time.sleep(0.8)
        if "W" in on:
            set_inputs(["W"], on)
        time.sleep(1.2)
        got = [int(lab.block_at(base[0] + x, Y, base[1] + z, "lit_redstone_lamp")) for x, z in outs]
        good = got == list(want)
        ok &= good
        label = "+".join(sorted(on)) if len(on) < 4 else f"{len(on)} on"
        rows.append(f"{label}->{''.join(map(str, got))}{'' if good else ' (WRONG, want ' + ''.join(map(str, want)) + ')'}")
    print(f"  {name:8s} {'PASS' if ok else 'FAIL'}   " + "  ".join(rows), flush=True)
    return ok


def clear(lab, base):
    """Wipe the whole build zone so designs can't interfere with each other."""
    bx, bz = base
    for y in range(Y, Y + 4):
        lab.cmd(f"fill {bx - 8} {y} {bz - 8} {bx + 40} {y} {bz + 40} air", wait=0.05)
    time.sleep(0.4)


def use_compact_order():
    """Rebuild every design from its compact text, in the exact order the model writes it."""
    def wrap(fn):
        def inner():
            parts, *rest = fn()
            return (R.from_compact(R.to_compact(parts)), *rest)
        return inner
    for table in (R.GATES, R.MEMORY):
        for k in table:
            table[k] = wrap(table[k])


def main():
    args = sys.argv[1:]
    if "--compact" in args:
        args.remove("--compact")
        use_compact_order()
    names = args or list(R.GATES) + list(R.MEMORY)
    with Lab() as lab:
        results = []
        base = (0, 8)
        for n in names:
            results.append(run_memory(lab, n, base) if n in R.MEMORY else run_gate(lab, n, base))
    print(f"{sum(results)}/{len(results)} designs passed")


if __name__ == "__main__":
    main()
