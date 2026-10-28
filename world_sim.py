"""A small Minecraft-like voxel world for the agent to practice moving and mining in.

What the agent knows about its own body (real Minecraft numbers):
    height 1.8 blocks, width 0.6  -> it fills 1 x 2 x 1 blocks (feet + head)
    eyes at 1.62                  -> it sees from its head block
    step up 1 block (jump)        -> needs 3 clear blocks above where it starts
    safe drop 3 blocks            -> more than that costs health
    tunnels must be 2 tall, and it never digs a block touching lava or water,
    never digs straight down, can't break bedrock, and ores need the right pickaxe.

It has no x-ray: it only knows about blocks it has seen (blocks touching air near it).
Pathfinding (A*) treats solid blocks as "costs mining time", so the path it picks is the
truly fastest one: walking around a hill or straight through it, whichever is quicker.
"""

import heapq
import random

import numpy as np

AIR, STONE, DIRT, GRASS, DEEPSLATE, BEDROCK, LOG, LEAVES, COAL, IRON, DIAMOND, LAVA, WATER = range(13)
NAMES = ["air", "stone", "dirt", "grass_block", "deepslate", "bedrock", "oak_log", "leaves",
         "coal_ore", "iron_ore", "diamond_ore", "lava", "water"]
SOLID = {STONE, DIRT, GRASS, DEEPSLATE, BEDROCK, LOG, LEAVES, COAL, IRON, DIAMOND}
FLUID = {LAVA, WATER}
# seconds to break with the best pickaxe tier you have: 0 hand, 1 wood, 2 stone, 3 iron, 4 diamond
HARDNESS = {STONE: 1.5, DIRT: 0.5, GRASS: 0.6, DEEPSLATE: 3.0, LOG: 2.0, LEAVES: 0.2,
            COAL: 3.0, IRON: 3.0, DIAMOND: 3.0}
NEEDS_TIER = {STONE: 1, DEEPSLATE: 1, COAL: 1, IRON: 2, DIAMOND: 3}
TIER_SPEED = {0: 1.0, 1: 2.0, 2: 4.0, 3: 6.0, 4: 8.0}

BODY_HEIGHT = 2          # blocks (1.8 tall)
STEP_UP = 1
SAFE_DROP = 3
Y_MIN = -64              # world bottom, like real Minecraft
SEE_RADIUS = 6


class World:
    def __init__(self, size=48, height=168, seed=None):
        self.rng = random.Random(seed)
        self.size, self.height = size, height
        self.b = np.zeros((size, height, size), dtype=np.uint8)   # [x, y - Y_MIN, z]
        self._generate()

    # ---- coordinates use real Minecraft y (-64 at the bottom)
    def get(self, x, y, z):
        if not (0 <= x < self.size and 0 <= z < self.size):
            return BEDROCK                         # world edge acts like a wall
        if y < Y_MIN:
            return BEDROCK
        if y >= Y_MIN + self.height:
            return AIR
        return int(self.b[x, y - Y_MIN, z])

    def set(self, x, y, z, v):
        if 0 <= x < self.size and 0 <= z < self.size and Y_MIN <= y < Y_MIN + self.height:
            self.b[x, y - Y_MIN, z] = v

    def surface(self, x, z):
        """Top ground block (ignores trees)."""
        for y in range(Y_MIN + self.height - 1, Y_MIN, -1):
            if self.get(x, y, z) in SOLID - {LOG, LEAVES}:
                return y
        return Y_MIN

    def _generate(self):
        rng, S = self.rng, self.size
        hills = [(rng.uniform(0, S), rng.uniform(0, S), rng.uniform(4, 12), rng.uniform(6, 16)) for _ in range(5)]
        for x in range(S):
            for z in range(S):
                top = 64 + int(sum(h * np.exp(-((x - cx) ** 2 + (z - cz) ** 2) / (2 * w * w)) for cx, cz, h, w in hills))
                for y in range(Y_MIN, top + 1):
                    if y <= Y_MIN + rng.randint(0, 3):
                        v = BEDROCK
                    elif y < 0:
                        v = DEEPSLATE
                    elif y < top - 3:
                        v = STONE
                    elif y < top:
                        v = DIRT
                    else:
                        v = GRASS
                    self.set(x, y, z, v)
        # caves: wandering worms of air
        for _ in range(10):
            x, y, z = rng.uniform(0, S), rng.uniform(-55, 50), rng.uniform(0, S)
            for _ in range(rng.randint(30, 80)):
                r = rng.uniform(1.2, 2.5)
                for dx in range(-3, 4):
                    for dy in range(-3, 4):
                        for dz in range(-3, 4):
                            if dx * dx + dy * dy + dz * dz <= r * r:
                                px, py, pz = int(x + dx), int(y + dy), int(z + dz)
                                if 0 <= px < S and 0 <= pz < S and Y_MIN + 5 < py < 60:
                                    self.set(px, py, pz, AIR)
                x += rng.uniform(-1.5, 1.5)
                y += rng.uniform(-0.8, 0.8)
                z += rng.uniform(-1.5, 1.5)
        # ores at their real heights: diamonds mostly near the bottom
        for ore, lo, hi, count, vein in ((COAL, 0, 90, 140, 6), (IRON, -24, 56, 110, 4), (DIAMOND, -63, 16, 45, 3)):
            for _ in range(count):
                if ore == DIAMOND:
                    y = int(min(hi, lo + abs(rng.gauss(0, 18))))
                else:
                    y = rng.randint(lo, hi)
                x, z = rng.randrange(S), rng.randrange(S)
                for _ in range(rng.randint(1, vein)):
                    if self.get(x, y, z) in (STONE, DEEPSLATE):
                        self.set(x, y, z, ore)
                    x, y, z = x + rng.choice((-1, 0, 1)), y + rng.choice((-1, 0, 1)), z + rng.choice((-1, 0, 1))
        # lava pools deep down, like real Minecraft
        for _ in range(8):
            x, y, z = rng.randrange(S), rng.randint(-60, -50), rng.randrange(S)
            for dx in range(-2, 3):
                for dz in range(-2, 3):
                    if self.get(x + dx, y, z + dz) != BEDROCK and 0 <= x + dx < S and 0 <= z + dz < S:
                        self.set(x + dx, y, z + dz, LAVA)
        # trees
        for _ in range(12):
            x, z = rng.randrange(2, S - 2), rng.randrange(2, S - 2)
            y = self.surface(x, z) + 1
            for h in range(5):
                self.set(x, y + h, z, LOG)
            for dx in range(-2, 3):
                for dz in range(-2, 3):
                    for dy in (3, 4, 5):
                        if self.get(x + dx, y + dy, z + dz) == AIR:
                            self.set(x + dx, y + dy, z + dz, LEAVES)


class Agent:
    def __init__(self, world, tier=3):
        self.w = world
        x = z = world.size // 2
        self.pos = (x, world.surface(x, z) + 1, z)   # feet block
        self.tier = tier
        self.seen = {}            # (x, y, z) -> block id, everything it has laid eyes on
        self.inventory = {}
        self.time = 0.0           # seconds spent
        self.mined = 0
        self.walked = 0
        self.look()

    # ---- senses

    def look(self):
        """Remember every block near the head that touches air (no x-ray)."""
        hx, hy, hz = self.pos[0], self.pos[1] + 1, self.pos[2]
        r = SEE_RADIUS
        for x in range(hx - r, hx + r + 1):
            for y in range(hy - r, hy + r + 1):
                for z in range(hz - r, hz + r + 1):
                    v = self.w.get(x, y, z)
                    if v == AIR:
                        continue
                    if any(self.w.get(x + dx, y + dy, z + dz) == AIR
                           for dx, dy, dz in ((1, 0, 0), (-1, 0, 0), (0, 1, 0), (0, -1, 0), (0, 0, 1), (0, 0, -1))):
                        self.seen[(x, y, z)] = v

    def known(self, block):
        return [p for p, v in self.seen.items() if v == block and self.w.get(*p) == block]

    # ---- body rules

    def dig_cost(self, x, y, z):
        """Seconds to clear this block, or None if it must not be dug."""
        v = self.w.get(x, y, z)
        if v in (AIR,):
            return 0.0
        if v in FLUID or v == BEDROCK:
            return None
        if NEEDS_TIER.get(v, 0) > self.tier:
            return None
        if any(self.w.get(x + dx, y + dy, z + dz) in FLUID
               for dx, dy, dz in ((1, 0, 0), (-1, 0, 0), (0, 1, 0), (0, 0, 1), (0, 0, -1))):
            return None                                 # would let lava/water flow in
        return HARDNESS.get(v, 1.0) / TIER_SPEED[self.tier] + 0.25

    def _clear(self, cells):
        total = 0.0
        for c in cells:
            cost = self.dig_cost(*c)
            if cost is None:
                return None
            total += cost
        return total

    def _moves(self, x, y, z):
        """Every place the body can go next from feet at (x, y, z), with its cost in seconds."""
        w = self.w
        if w.get(x, y - 1, z) not in SOLID:
            return []                                   # mid-air: falls handled by drop moves
        for dx, dz in ((1, 0), (-1, 0), (0, 1), (0, -1)):
            nx, nz = x + dx, z + dz
            # walk straight (dig feet + head if needed)
            c = self._clear([(nx, y, nz), (nx, y + 1, nz)])
            if c is not None and w.get(nx, y - 1, nz) in SOLID:
                yield (nx, y, nz), 0.25 + c
            # step up 1: needs room above our own head too (we are 2 tall)
            c = self._clear([(x, y + 2, z), (nx, y + 1, nz), (nx, y + 2, nz)])
            if c is not None and w.get(nx, y, nz) in SOLID:
                yield (nx, y + 1, nz), 0.45 + c
            # step down / drop up to 3 safely
            if self._clear([(nx, y, nz), (nx, y + 1, nz)]) == 0:
                for d in range(1, SAFE_DROP + 1):
                    below = w.get(nx, y - d, nz)
                    if below in FLUID:
                        break
                    if below in SOLID:
                        yield (nx, y - d + 1, nz), 0.3 + 0.1 * d
                        break
        # stair down: dig the block ahead at feet level and one below it (never straight down)
        for dx, dz in ((1, 0), (-1, 0), (0, 1), (0, -1)):
            nx, nz = x + dx, z + dz
            c = self._clear([(nx, y + 1, nz), (nx, y, nz), (nx, y - 1, nz)])
            if c is not None and w.get(nx, y - 2, nz) in SOLID:
                yield (nx, y - 1, nz), 0.4 + c

    def path_to(self, goal_fn, heuristic, limit=60000):
        """A*: the fastest way (walking + mining time) to any feet position where goal_fn is True."""
        start = self.pos
        frontier = [(heuristic(start), 0.0, start)]
        cost, came = {start: 0.0}, {start: None}
        while frontier and len(came) < limit:
            _, g, cur = heapq.heappop(frontier)
            if goal_fn(cur):
                path = []
                while cur:
                    path.append(cur)
                    cur = came[cur]
                return path[::-1], g
            if g > cost.get(cur, 1e18):
                continue
            for nxt, step in self._moves(*cur):
                ng = g + step
                if ng < cost.get(nxt, 1e18):
                    cost[nxt], came[nxt] = ng, cur
                    heapq.heappush(frontier, (ng + heuristic(nxt), ng, nxt))
        return None, None

    # ---- doing things

    def follow(self, path):
        for nx, ny, nz in path[1:]:
            x, y, z = self.pos
            if ny > y:      # stepping up: room above our head, then the 2 blocks we step into
                cells = [(x, y + 2, z), (nx, ny, nz), (nx, ny + 1, nz)]
            else:           # walking, stairing or dropping: everything we pass through
                cells = [(nx, k, nz) for k in range(y + 1, ny - 1, -1)]
            for c in cells:
                if self.w.get(*c) in SOLID:
                    self.break_block(*c)
            self.time += 0.25
            self.walked += 1
            self.pos = (nx, ny, nz)
            self.look()

    def break_block(self, x, y, z):
        v = self.w.get(x, y, z)
        cost = self.dig_cost(x, y, z)
        if cost is None:
            raise RuntimeError(f"tried to break {NAMES[v]} at {(x, y, z)}")
        self.time += cost
        self.w.set(x, y, z, AIR)
        self.mined += 1
        drop = {STONE: "cobblestone", DEEPSLATE: "cobbled_deepslate", COAL: "coal", IRON: "raw_iron",
                DIAMOND: "diamond", GRASS: "dirt"}.get(v, NAMES[v])
        self.inventory[drop] = self.inventory.get(drop, 0) + 1

    def reach_and_mine(self, target):
        """Walk/dig to a spot where the target is next to our feet or head, then break it."""
        tx, ty, tz = target

        def touching(p):
            x, y, z = p
            return any((x + dx, y + dy, z + dz) == target
                       for dy in (0, 1) for dx, dz in ((1, 0), (-1, 0), (0, 1), (0, -1)))

        path, secs = self.path_to(touching, lambda p: 1.2 * (abs(p[0] - tx) + abs(p[1] - ty) + abs(p[2] - tz)))
        if path is None:
            return False
        self.follow(path)
        self.break_block(*target)
        self.look()
        return True

    def find(self, block, count, log=print):
        """Gather `count` of a block the way a smart player would."""
        drop = {DIAMOND: "diamond", IRON: "raw_iron", COAL: "coal"}[block]
        best_y = {DIAMOND: -58, IRON: 15, COAL: 40}[block]
        direction, lane_shift = (1, 0), 1
        while self.inventory.get(drop, 0) < count and self.time < 3600:
            spots = self.known(block)
            if spots:
                # nearest by real travel+mining time, not straight-line distance
                spots.sort(key=lambda p: abs(p[0] - self.pos[0]) + abs(p[1] - self.pos[1]) + abs(p[2] - self.pos[2]))
                target = spots[0]
                if self.reach_and_mine(target):
                    log(f"  mined {NAMES[block]} at {target}  (t={self.time:.0f}s)")
                    continue
                self.seen.pop(target, None)            # unreachable safely, forget it
                continue
            if abs(self.pos[1] - best_y) > 2:
                # staircase toward the best depth (never straight down), 12 blocks per leg;
                # each block of depth costs ~1-2s of digging, so the estimate is scaled to match
                y0 = self.pos[1]
                gy = max(best_y, y0 - 12) if y0 > best_y else min(best_y, y0 + 12)
                path, _ = self.path_to(lambda p: abs(p[1] - gy) <= 1 if gy == best_y else
                                       (p[1] <= gy if gy < y0 else p[1] >= gy),
                                       lambda p: 1.5 * abs(p[1] - gy), limit=40000)
                if path is None:
                    log("  can't find a safe way down")
                    return False
                log(f"  no {NAMES[block]} seen yet, staircasing y={y0} -> {path[-1][1]} (heading for y={best_y})")
                self.follow(path)
                continue
            # strip mine like a player: long straight 2-tall tunnel, then shift 3 blocks over
            # (so each tunnel reveals fresh walls) and mine back the other way
            x, y, z = self.pos
            nxt = (x + direction[0], y, z)
            step = next((n for n, _ in self._moves(x, y, z) if n == nxt), None)
            if step:
                self.follow([self.pos, step])
                continue
            gz = z + 3 * lane_shift
            if not (1 <= gz < self.w.size - 1):
                lane_shift = -lane_shift
                gz = z + 3 * lane_shift
            path, _ = self.path_to(lambda p: p[2] == gz and abs(p[1] - best_y) <= 2,
                                   lambda p: 1.5 * abs(p[2] - gz), limit=20000)
            if path is None:
                log("  boxed in, giving up")
                return False
            self.follow(path)
            direction = (-direction[0], 0)
        return self.inventory.get(drop, 0) >= count
