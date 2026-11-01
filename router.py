"""Wire router: connects two points with redstone dust without touching anything else.

    r = Router(parts_already_built, keepout=[...])
    wire = r.route(start, goal)     # start/goal are (x, y, z) dust positions
    r.add(wire)                     # later wires route around this one

It's a breadth-first search over dust positions, using the rules the Redstone Lab taught us:
  * dust links to dust beside it, and one block up or down a step, so another net's dust must
    not be next to ours, even diagonally up/down
  * every dust needs a solid block under it
  * a step up needs air above the lower dust, or the link is cut
  * a signal dies after 15 dust, so a repeater goes on a straight stretch every 12 or so
  * stay away from components: a repeater/comparator/torch reacts to dust beside it
A wire crosses another by climbing over it on a higher level.
"""

from collections import deque

import redstone_lib as R

MAX_Y = 6


def cell_kind(block):
    name = block.split()[0]
    # lamps count as parts: a powered lamp feeds any dust touching it
    return "dust" if name == "redstone_wire" else "solid" if name == "stone" else "part"


class Router:
    def __init__(self, parts=(), bounds=(-6, 60, -6, 90)):
        self.bounds = bounds
        self.occ = {}           # (x, y, z) -> dust / solid / part
        self.air = set()        # cells that must stay empty, so a stair stays connected
        for x, y, z, b in parts:
            self.occ[(x, y, z)] = cell_kind(b)

    def add(self, wire):
        parts = wire["parts"]
        for x, y, z, b in parts:
            self.occ[(x, y, z)] = cell_kind(b)
        self.air |= wire["air"]

    # ---- is this dust position allowed?
    def _clear(self, x, y, z, start, goal):
        if self.occ.get((x, y, z)) or (x, y, z) in self.air:
            return False
        below = self.occ.get((x, y - 1, z))
        if below in ("dust", "part"):
            return False                     # needs a block there, but something else is there
        if y - 1 >= 0 and (x, y - 1, z) in self.air:
            return False
        for dx, dz in ((1, 0), (-1, 0), (0, 1), (0, -1)):
            for dy in (-1, 0, 1):
                n = (x + dx, y + dy, z + dz)
                if n in (start, goal):
                    continue
                kind = self.occ.get(n)
                if kind == "dust":
                    return False             # would link up with another wire
                if kind == "part" and dy == 0:
                    return False             # would feed or read a component
        return True

    def route(self, start, goal, max_nodes=400000):
        """Shortest path of dust from start to goal. Returns {parts, air, length}."""
        x0, x1, z0, z1 = self.bounds
        prev = {start: None}
        q = deque([start])
        seen = 0
        while q and seen < max_nodes:
            cur = q.popleft()
            seen += 1
            if cur == goal:
                return self._build(prev, goal)
            x, y, z = cur
            for dx, dz in ((1, 0), (-1, 0), (0, 1), (0, -1)):
                nx, nz = x + dx, z + dz
                if not (x0 <= nx <= x1 and z0 <= nz <= z1):
                    continue
                for dy in (0, 1, -1):
                    ny = y + dy
                    n = (nx, ny, nz)
                    if n in prev or not (0 <= ny <= MAX_Y):
                        continue
                    if n != goal and not self._clear(nx, ny, nz, start, goal):
                        continue
                    # stair: the air above the lower dust must be free
                    if dy == 1 and self.occ.get((x, y + 1, z)):
                        continue
                    if dy == -1 and self.occ.get((nx, y, nz)):
                        continue
                    prev[n] = cur
                    q.append(n)
        raise RuntimeError(f"no route from {start} to {goal}")

    def _build(self, prev, goal):
        path, cur = [], goal
        while cur:
            path.append(cur)
            cur = prev[cur]
        path.reverse()
        parts, air = [], set()
        since = 0
        for i, (x, y, z) in enumerate(path):
            if y > 0 and (x, y - 1, z) not in self.occ:
                parts.append(R.block(x, z, y - 1))
            since += 1
            straight = 0 < i < len(path) - 1 and self._straight(path[i - 1], path[i], path[i + 1])
            if since >= 9 and straight:              # early, straight stretches can be rare
                parts.append(R.rep(x, z, self._dir(path[i - 1], path[i]), y))
                since = 0
            else:
                parts.append(R.dust(x, z, y))
            if i and path[i - 1][1] != y:            # a step: keep the air above the lower dust
                low = path[i - 1] if path[i - 1][1] < y else path[i]
                air.add((low[0], low[1] + 1, low[2]))
        if since >= 15:
            raise RuntimeError("wire too long with no straight stretch for a repeater")
        return {"parts": parts, "air": air, "length": len(path)}

    @staticmethod
    def _straight(a, b, c):
        return a[1] == b[1] == c[1] and b[0] - a[0] == c[0] - b[0] and b[2] - a[2] == c[2] - b[2]

    @staticmethod
    def _dir(a, b):
        return {(1, 0): "east", (-1, 0): "west", (0, 1): "south", (0, -1): "north"}[(b[0] - a[0], b[2] - a[2])]
