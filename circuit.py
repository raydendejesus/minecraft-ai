"""Teacher for "redstone circuit <formula>": turns any logic formula over a, b, c, d into a redstone
circuit. These circuits are only LESSONS. The test (test_ai_circuits.py) builds what the AI writes.

Layout, signals flowing east (+x):
  * four levers on the west edge, a at z=0, b at z=8, c at z=16, d at z=24, each followed by a
    repeater, so every input starts at full strength
  * one gate cell per and / or / xor / not in the formula, laid out like the formula's tree:
    each gate sits east of the parts it reads
  * one lamp: the circuit's output
  * every wire is laid by a router. One signal can feed several gates (a variable used twice),
    so a wire may branch off another wire of the SAME signal, never touch a different one

Gate cells are the lab-verified gates from redstone_lib, with each input lever swapped for a
repeater (so a long wire still arrives at full strength) and the output lamp swapped for a
repeater that starts the next wire.
"""

import heapq

import redstone_lib as R
from router import MAX_Y, Router

LEVER_Z = {"a": 0, "b": 12, "c": 24, "d": 36}
X0 = 8                  # first gate column, leaving room east of the levers for wires
LAST = {}               # the last circuit's gates: name -> (formula part, output cell), for lab debugging
PIECES = []             # the last circuit in build order: (header, origin (x, z), parts relative to it)


# ---- formula -> tree, read exactly like data.eval_logic: "not" takes the next item, and binary
# ops chain left to right
def parse(expr):
    toks = expr.replace("(", " ( ").replace(")", " ) ").split()
    pos = 0

    def atom():
        nonlocal pos
        t = toks[pos]
        pos += 1
        if t == "not":
            return ("not", atom())
        if t == "(":
            v = chain()
            pos += 1
            return v
        if t not in LEVER_Z:
            raise ValueError(f"unknown input {t!r}")
        return ("var", t)

    def chain():
        nonlocal pos
        v = atom()
        while pos < len(toks) and toks[pos] in ("and", "or", "xor", "nand", "nor"):
            op = toks[pos]
            pos += 1
            v = (op, v, atom())
            if op in ("nand", "nor"):
                v = ("not", (op[1:], v[1], v[2]))
        return v

    tree = chain()
    if pos != len(toks):
        raise ValueError("leftover words in the formula")
    return tree


# ---- gate cells: (parts, input goals (x, z) where a wire must end, output seed (x, z), width, top, bottom)
def _cell(gate):
    if gate == "not":
        parts = [R.rep(0, 0), R.block(1, 0), R.torch(2, 0, "west"), R.rep(3, 0), R.dust(4, 0)]
        return parts, [(-1, 0)], (4, 0), 5, 0, 0
    parts, ins, out, _ = getattr(R, f"g_{gate}")()
    for x, z in ins:
        parts = R.swap(parts, (x, z), R.rep(x, z))
    parts = R.swap(parts, out, R.rep(*out)) + [R.dust(out[0] + 1, out[1])]
    zs = [p[2] for p in parts]
    return parts, [(x - 1, z) for x, z in ins], (out[0] + 1, out[1]), out[0] + 2, min(zs), max(zs)


class NetRouter(Router):
    """The machines' router, plus nets: a wire may touch and branch off dust of its own signal.
    Tracks signal strength on every wire, so a branch knows how far it can go before it needs a
    repeater."""

    def __init__(self, parts, bounds):
        super().__init__(parts, bounds)
        self.net = {}            # dust cell -> signal name
        self.strength = {}       # dust cell -> signal strength (15 right after a repeater)
        self.ends = set()        # cells where a wire meets a gate input: never branch from these
        self.keep = {}           # cells beside a wire end, held for that wire's signal

    def seed(self, cell, net):
        self.occ[cell] = "dust"
        self.net[cell] = net
        self.strength[cell] = 15

    def reserve(self, cell, net):
        """A gate input's wire end, held for its signal so other wires keep away from it. The
        cells it can be reached from are held too: a wire passing by once boxed one in with the
        blocks holding it up."""
        self.occ[cell] = "dust"
        self.net[cell] = net
        self.ends.add(cell)
        x, y, z = cell
        for dx, dz in ((-1, 0), (0, -1), (0, 1)):
            for dy in (0, 1):
                self.keep.setdefault((x + dx, y + dy, z + dz), net)

    def _clear(self, x, y, z, net, goal, branch_from=None):
        """Can this signal's wire put dust here? It may touch its own signal's dust only where it
        branches off (branch_from): the lab caught a branch touching its own wire again past a
        repeater, which loops the repeater back on itself and holds the signal on for good."""
        if self.occ.get((x, y, z)) or (x, y, z) in self.air:
            return False
        if self.keep.get((x, y, z), net) != net or self.keep.get((x, y - 1, z), net) != net:
            return False
        below = self.occ.get((x, y - 1, z))
        if below in ("dust", "part"):
            return False
        if y - 1 >= 0 and (x, y - 1, z) in self.air:
            return False
        for dx, dz in ((1, 0), (-1, 0), (0, 1), (0, -1)):
            for dy in (-1, 0, 1):
                n = (x + dx, y + dy, z + dz)
                kind = self.occ.get(n)
                if kind == "dust" and n != goal and n != branch_from:
                    return False
                if kind == "part" and dy == 0:
                    return False
        return True

    STEP, TURN, CLIMB = 1, 3, 4      # what each block, each turn and each climb up or down costs

    def route_net(self, net, goal):
        """Cheapest wire from any of the signal's dust to the goal. Every block costs, and turns
        and climbs cost extra, so of the shortest ways it takes the straightest and flattest.

        A path can trip over itself: the lab caught a wire that rode over a spot and later had
        to step down beside it, where its own support block cut the step. Such a path is
        searched again with the offending cell banned."""
        ban = set()
        for _ in range(40):
            path = self._search(net, goal, ban)
            bad = self._self_conflicts(path)
            if not bad:
                return self._build_net(net, path)
            ban |= bad
        raise RuntimeError(f"no clean route for {net} to {goal}")

    @staticmethod
    def _self_conflicts(path):
        """Cells of the path that clash with its own support blocks or the air its steps need."""
        cells = set(path)
        bad = set()
        index = {c: i for i, c in enumerate(path)}
        for i, (x, y, z) in enumerate(path):          # never touching itself, except next in line
            for dx, dz in ((1, 0), (-1, 0), (0, 1), (0, -1)):
                for dy in (-1, 0, 1):
                    j = index.get((x + dx, y + dy, z + dz))
                    if j is not None and j > i + 1:     # ban a cell in between, never the goal
                        bad.add(path[j] if j < len(path) - 1 else path[max(i, 1)])
        for x, y, z in path[1:]:
            if y > 0 and (x, y - 1, z) in cells:
                bad.add((x, y, z))                    # its support would be the wire itself
        for a, b in zip(path, path[1:]):
            if a[1] != b[1]:
                low = a if a[1] < b[1] else b
                air = (low[0], low[1] + 1, low[2])
                if air in cells:
                    bad.add(air)
                if (air[0], air[1] + 1, air[2]) in cells:
                    bad.add((air[0], air[1] + 1, air[2]))   # its support block would fill the air
        return bad

    def _search(self, net, goal, ban, max_nodes=400000):
        x0, x1, z0, z1 = self.bounds
        starts = [c for c, n in self.net.items()
                  if n == net and c not in self.ends and self.strength.get(c, 0) >= 6]
        gx, gy, gz = goal

        def h(c):                    # never more than what's left, so the answer stays the cheapest
            return self.STEP * (abs(c[0] - gx) + abs(c[2] - gz)) + self.CLIMB * abs(c[1] - gy)

        best = {(s, None): 0 for s in starts}
        prev = {}
        heap = [(h(s), k, 0, s, None) for k, s in enumerate(sorted(starts))]
        heapq.heapify(heap)
        tie, seen = len(heap), 0
        while heap and seen < max_nodes:
            _, _, cost, cur, came = heapq.heappop(heap)
            if cost > best.get((cur, came), cost):
                continue
            seen += 1
            if cur == goal:
                path, key = [], (cur, came)
                while key in prev:
                    path.append(key[0])
                    key = prev[key]
                path.append(key[0])
                return path[::-1]
            x, y, z = cur
            for dx, dz in ((1, 0), (-1, 0), (0, 1), (0, -1)):
                nx, nz = x + dx, z + dz
                if not (x0 <= nx <= x1 and z0 <= nz <= z1):
                    continue
                for dy in (0, 1, -1):
                    n = (nx, y + dy, nz)
                    if not (0 <= n[1] <= MAX_Y) or n in ban:
                        continue
                    if n == goal:
                        if dy:
                            continue                 # arrive level, straight into the gate
                    elif not self._clear(*n, net, goal, cur if came is None else None):
                        continue
                    elif dy == 1 and self.occ.get((x, y + 1, z)):
                        continue
                    elif dy == -1 and self.occ.get((nx, y, nz)):
                        continue
                    step = self.STEP + (self.TURN if came and came != (dx, dz) else 0) + (self.CLIMB if dy else 0)
                    key = (n, (dx, dz))
                    if cost + step < best.get(key, 1 << 30):
                        best[key] = cost + step
                        prev[key] = (cur, came)
                        tie += 1
                        heapq.heappush(heap, (cost + step + h(n), tie, cost + step, n, (dx, dz)))
        raise RuntimeError(f"no route for {net} to {goal}")

    def _build_net(self, net, path):
        # path[0] is the existing dust it branches from
        last = len(path) - 1
        straight = [0 < i < last and self._straight(path[i - 1], path[i], path[i + 1]) for i in range(len(path))]
        parts, air, cells = [], set(), {}
        prev_s = self.strength[path[0]]               # strength of the dust just behind
        for i in range(1, len(path)):
            x, y, z = path[i]
            if y > 0 and (x, y - 1, z) not in self.occ:
                parts.append(R.block(x, z, y - 1))
            # a repeater goes on this straight cell if, without it, the signal would die before
            # the next straight cell (or before the end)
            nxt = next((j for j in range(i + 1, last) if straight[j]), None)
            short = prev_s - (nxt - i) < 1 if nxt else prev_s - (last - i + 1) < 1
            if straight[i] and i > 1 and short:
                parts.append(R.rep(x, z, self._dir(path[i - 1], path[i]), y))
                prev_s = 16                           # the dust after it gets 15
            else:
                prev_s -= 1
                if prev_s < 1:
                    raise RuntimeError("wire too long with no straight stretch for a repeater")
                parts.append(R.dust(x, z, y))
                cells[(x, y, z)] = prev_s
            if path[i - 1][1] != y:
                low = path[i - 1] if path[i - 1][1] < y else path[i]
                air.add((low[0], low[1] + 1, low[2]))
        for c, s in cells.items():                    # only a finished wire is recorded
            self.net[c] = net
            self.strength[c] = s
        for x, y, z, b in parts:
            self.occ[(x, y, z)] = "dust" if b == "redstone_wire" else "solid" if b == "stone" else "part"
        self.air |= air
        return parts


def circuit(expr, gap_x=6, gap_z=4):
    """Parts for the whole circuit, levers a-d and one lamp. Raises if the router can't wire it."""
    tree = parse(expr)
    parts, wires, seeds, gate_blocks = [], [], {}, []      # wires: (signal, goal cell)
    LAST.clear()
    PIECES.clear()

    def lay(node, x0, z0):
        """Place node's gates with its top-left at (x0, z0). Returns (signal, x_end, z_end):
        gates read from the west, so a gate goes east of whatever its inputs come out of."""
        if node[0] == "var":
            return node[1], x0, z0
        if node[0] == "not" and node[1][0] == "var":
            return "not " + node[1][1], x0, z0       # read from that lever's inverted copy
        if node[0] == "not":
            src, xe, ze = lay(node[1], x0, z0)
            srcs, gate = [src], "not"
        else:
            sl, xl, zl = lay(node[1], x0, z0)
            sr, xr, zr = lay(node[2], x0, max(zl, z0) + gap_z)
            srcs, gate, xe, ze = [sl, sr], node[0], max(xl, xr), max(zl, zr)
        x = x0 if xe == x0 else xe + gap_x
        cp, ins, out, width, top, bottom = _cell(gate)
        dz = z0 - top
        me = f"g{len(seeds)}"
        PIECES.append((f"# {gate} {me} at {x} {dz}", (x, dz), sorted(cp, key=lambda p: p[3] != "stone")))
        cp = R.shift(cp, x, dz)
        parts.extend(cp)
        gate_blocks.extend(p for p in cp if p[3] == "stone")
        for src, (ix, iz) in zip(srcs, ins):
            wires.append((src, (x + ix, 0, iz + dz)))
        seeds[me] = (x + out[0], 0, out[1] + dz)
        LAST[me] = (node, seeds[me])
        return me, x + width, max(ze, z0 + bottom - top + 1)

    for v, z in LEVER_Z.items():
        # the lever's signal at (2, z), and its inverted copy at (2, z + 6): a branch runs south
        # into a repeater, block and torch
        parts += [R.lever(0, z), R.rep(1, z), R.dust(2, z), R.dust(2, z + 1), R.dust(2, z + 2),
                  R.rep(2, z + 3, "south"), R.block(2, z + 4), R.torch(2, z + 5, "north"), R.dust(2, z + 6)]
        gate_blocks.append(R.block(2, z + 4))
        seeds[v] = (2, 0, z)
        seeds["not " + v] = (2, 0, z + 6)
    PIECES.append(("# inputs", (0, 0), list(parts)))
    root, x_end, z_end = lay(tree, X0, 0)
    if root in LEVER_Z:                                   # a formula with no gates: lever -> lamp
        wires.append((root, (x_end + gap_x, 0, 0)))
        lamp_at = (x_end + gap_x + 1, 0)
        PIECES.append((f"# lamp at {lamp_at[0]} {lamp_at[1]}", lamp_at, [R.lamp(0, 0)]))
    else:
        sx, _, sz = seeds[root]
        parts.remove(R.dust(sx, sz))                      # the last gate's output goes into the lamp
        lamp_at = (sx, sz)
        head, (ox, oz), cp = PIECES[-1]                   # the root is always the last gate laid
        cp = [R.lamp(sx - ox, sz - oz) if p == R.dust(sx - ox, sz - oz) else p for p in cp]
        PIECES[-1] = (head, (ox, oz), cp)
    parts.append(R.lamp(*lamp_at))

    bounds = (-2, max(x_end, lamp_at[0]) + 8, -8, max(z_end, 42) + 8)
    r = NetRouter(parts, bounds)
    for x, y, z, _ in gate_blocks:
        r.occ[(x, y, z)] = "part"            # no wire on a gate's blocks: dust would power them
    for x, y, z, b in parts:
        if b.startswith("redstone_torch"):
            r.occ.setdefault((x, y + 1, z), "part")   # a torch powers the block above it
    for name, cell in seeds.items():
        if name != root or root in LEVER_Z:
            r.seed(cell, name)
    for src, goal in wires:
        r.reserve(goal, src)
    for src, goal in sorted(wires, key=lambda w: -w[1][0]):   # far gates first, while there's room
        wire = r.route_net(src, goal)                  # ends with the dust at the gate's input
        parts += wire
        PIECES.append((f"# wire {src} to {goal[0]} {goal[2]}", (0, 0), wire))
        r.ends.discard(goal)
        r.strength[goal] = 1
    return parts


def build(expr):
    """circuit(), spreading things out further if the router gets stuck."""
    for gx, gz in ((6, 4), (8, 6), (10, 8), (12, 10)):
        try:
            return circuit(expr, gx, gz)
        except RuntimeError:
            continue
    raise RuntimeError(f"could not wire {expr!r}")


# ---- build-order text: what the AI writes. One piece at a time, in the order it's built: the
# inputs, each gate where it chose to put it, then each wire step by step. "# and g9 at 14 0" means
# the lines below are counted from (14, 0); a wire's lines are plain positions. A straight run of
# the same block is one line: "d 5 0 3 x-4" is 4 dust going west from (5, 0, 3).
def lesson(expr):
    """The teacher's circuit for a formula, as build-order text."""
    build(expr)
    return to_steps(PIECES)


def to_steps(pieces):
    out = []
    for head, _, parts in pieces:
        out.append(head)
        codes = [line.split() for line in (R.to_compact([p]) for p in parts)]
        i = 0
        while i < len(codes):
            k, x, y, z, *extra = codes[i]
            x, y, z = int(x), int(y), int(z)
            n, step = 1, None
            while i + n < len(codes):
                k2, x2, y2, z2, *e2 = codes[i + n]
                d = (int(x2) - x - (n - 1) * step[0], int(z2) - z - (n - 1) * step[1]) if step else \
                    (int(x2) - x, int(z2) - z)
                if k2 != k or e2 != extra or int(y2) != y or abs(d[0]) + abs(d[1]) != 1 or (step and d != step):
                    break
                step, n = d, n + 1
            run = "" if n == 1 else f" {'x' if step[0] else 'z'}{n if sum(step) > 0 else -n}"
            out.append(" ".join([k, str(x), str(y), str(z), *extra]) + run)
            i += n
    return "\n".join(out)


def from_steps(text):
    """The reverse of to_steps: the AI's text -> parts. Raises ValueError on anything malformed."""
    lines, ox, oz = [], 0, 0
    for line in text.strip().splitlines():
        p = line.split()
        if not p:
            continue
        if p[0] == "#":
            ox, oz = (int(p[-2]), int(p[-1])) if len(p) > 3 and p[-3] == "at" else (0, 0)
            continue
        n, axis = 1, None
        if p[-1][0] in "xz" and p[-1][1:].lstrip("-").isdigit():
            axis, n = p[-1][0], int(p[-1][1:])
            p = p[:-1]
        x, y, z = map(int, p[1:4])
        sign = 1 if n > 0 else -1
        for i in range(abs(n)):
            cx, cz = (x + sign * i, z) if axis == "x" else (x, z + sign * i) if axis == "z" else (x, z)
            lines.append(" ".join([p[0], str(cx + ox), str(y), str(cz + oz), *p[4:]]))
    return R.from_compact("\n".join(lines))


def inputs_and_output(parts):
    """Where the levers (a, b, c, d by z) and the lamp are in a list of parts, whoever wrote it."""
    levers = sorted((p for p in parts if p[3].startswith("lever")), key=lambda p: p[2])
    lamps = [p for p in parts if p[3] == "redstone_lamp"]
    if len(levers) != 4 or len(lamps) != 1:
        raise ValueError(f"needs 4 levers and 1 lamp, has {len(levers)} and {len(lamps)}")
    return [(p[0], p[2]) for p in levers], (lamps[0][0], lamps[0][2])
