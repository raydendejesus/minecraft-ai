"""How long would the AI's answer be for bigger RAM, with runs alone and with repeats added?

A repeat: 'r 3 0 2 e z6n64' means that part, 64 times, every 6 blocks along z. Parts sitting at the
same spot in every row or bit collapse to one line, which is how RAM shrinks so much.
"""

import redstone_lib as R


def group(items, axis_index):
    """Find evenly spaced lines: returns (line, step, count) groups covering all the items."""
    left, out = set(items), []
    while left:
        first = min(left)
        best = (0, 1)
        others = sorted(v for v in left if v > first)
        for second in others[:64]:
            step = second - first
            n = 1
            while first + step * n in left:
                n += 1
            if n * 1 > best[1]:
                best = (step, n)
        step, n = best
        for i in range(n):
            left.discard(first + step * i)
        out.append((first, step, n))
    return out


def to_loops(parts):
    rows = {}
    for line in R.to_runs(parts).splitlines():
        p = line.split()
        z = int(p[3])
        key = (p[0], int(p[1]), int(p[2]), tuple(p[4:]))
        rows.setdefault(key, []).append(z)
    # first collapse along z, then along x
    by_z = {}
    for (kind, x, y, extra), zs in rows.items():
        for z, step, n in group(zs, 0):
            by_z.setdefault((kind, y, extra, z, step, n), []).append(x)
    lines = []
    for (kind, y, extra, z, step, n), xs in by_z.items():
        for x, xstep, xn in group(xs, 1):
            text = f"{kind} {x} {y} {z}" + (" " + " ".join(extra) if extra else "")
            if n > 1:
                text += f" z{step}n{n}"
            if xn > 1:
                text += f" x{xstep}n{xn}"
            lines.append(text)
    return "\n".join(lines)


for name, addr in (("16 bytes", 4), ("64 bytes", 6), ("128 bytes", 7)):
    parts = R.ram(addr, 8)[0]
    print(f"{name:10s} {len(parts):7d} parts   runs only {len(R.to_runs(parts)):7d} chars   "
          f"with repeats {len(to_loops(parts)):7d} chars", flush=True)
