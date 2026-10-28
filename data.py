"""Training data for the tiny Builder model.

The Builder learns one narrow job: turn a short request line (written by Qwen)
into Bedrock commands. Requests use a small language:

    place <block> <x> <y> <z>          put one block at an offset
    remove <x> <y> <z>                 break one block (it drops as an item)
    floor <block> <w> <d>              flat floor under the build spot
    wall <block> <len> <h> <x|z>       straight wall along the x or z axis
    box <block> <w> <h> <d> <hollow|solid>
    pillar <block> <h>
    stairs <block> <h>                 diagonal staircase going up along +x
    clear <w> <h> <d>                  fill an area with air
    house <wall> <floor> <roof> <w> <h> <d> <north|south|east|west>
    roof <block> <w> <d>               stepped pyramid roof
    gable <block> <w> <d>              pitched roof, ridge runs along x
    frame <block> <w> <h> <d>          four corner posts (log corners on a house)
    tower <block> <r> <h>              round hollow tower, radius 2-5
    cylinder <block> <r> <h>           round solid pillar/silo
    pyramid <block> <w>                stepped hollow pyramid
    bridge <block> <len> <x|z>         3-wide deck with fence railings
    castle_wall <block> <len> <h> <x|z>  wall with crenellations on top
    windows <block> <len> <h> <x|z>    wall with glass windows every 3 blocks
    fence_ring <fence> <w> <d>         fenced pen with a gap for a gate
    farm <w> <d>                       farmland + water channel + wheat
    lamp_post <block> <h>              post with a lantern on top
    give <item> <count>                put items in the player's inventory
    describe <block>                   what a block looks like / is used for
    redstone <design>                  a lab-verified circuit (and, xor, full_adder, d_latch...)
    redstone ram <bits>                RAM, 1-8 bits
    logic <expr> | a=1 b=0 c=1         work out a logic expression -> "# 1"
    truth <expr>                       its whole truth table over a, b, c -> "# 01101001"

Redstone answers come out in the compact parts language from redstone_lib.py.

All coordinates are relative to the build spot (the anchor), extending into +x/+z.
`reference()` is the hand-written "teacher" used to generate examples; the model
never sees it at runtime, it has to learn the mapping.
"""

import json
import math
import os
import random
import string

HERE = os.path.dirname(os.path.abspath(__file__))
CORRECTIONS_PATH = os.path.join(HERE, "corrections.jsonl")

BLOCKS = [
    "stone", "cobblestone", "mossy_cobblestone", "oak_planks", "spruce_planks",
    "birch_planks", "dark_oak_planks", "oak_log", "spruce_log", "glass", "sandstone",
    "sand", "gravel", "dirt", "deepslate", "cobbled_deepslate", "obsidian", "glowstone",
    "iron_block", "gold_block", "diamond_block", "quartz_block", "netherrack",
    "blackstone", "end_stone", "bookshelf", "white_wool", "red_wool", "blue_wool",
    "snow", "ice", "packed_ice", "clay", "hay_block", "pumpkin", "crafting_table",
    # checked on the lab server (lab_blocks.py) - Bedrock spells some of these its own way
    "stone_bricks", "brick_block", "smooth_stone", "polished_andesite", "hardened_clay",
    "white_concrete", "gray_concrete", "cobblestone_wall", "chiseled_stone_bricks", "mud_bricks",
    "deepslate_bricks", "cherry_planks", "mangrove_planks", "bamboo_planks", "oak_leaves",
    "prismarine", "sea_lantern", "purpur_block", "nether_brick", "red_sandstone", "calcite", "tuff",
    "moss_block", "copper_block", "amethyst_block", "jungle_planks", "acacia_planks", "birch_log",
    "dark_oak_log", "stripped_oak_log", "polished_blackstone_bricks", "basalt",
]
FENCES = ["oak_fence", "spruce_fence", "dark_oak_fence", "cobblestone_wall"]

ITEMS = BLOCKS + [
    "diamond_pickaxe", "iron_pickaxe", "diamond_sword", "iron_sword", "diamond_axe",
    "bow", "arrow", "shield", "torch", "bread", "cooked_beef", "apple", "furnace",
    "chest", "bucket", "water_bucket", "flint_and_steel", "ender_pearl", "golden_apple",
]

DESCRIPTIONS = {
    "stone": "smooth gray block with faint darker speckles. the most common underground block, mine it with a pickaxe and it drops cobblestone.",
    "cobblestone": "rough gray block made of uneven chunky stones. cheap and blast resistant, great for early houses and walls.",
    "mossy_cobblestone": "cobblestone with green moss growing in the cracks. found in dungeons and jungle temples.",
    "oak_planks": "light tan wooden boards with visible grain lines. made from oak logs, the classic starter house block.",
    "spruce_planks": "darker brown wooden boards. made from spruce logs, looks great for cabins and roofs.",
    "birch_planks": "pale cream colored wooden boards. made from birch logs, gives a clean bright look.",
    "dark_oak_planks": "deep chocolate brown wooden boards. made from dark oak logs, good for a cozy rich style.",
    "oak_log": "a tree trunk block with brown bark on the sides and light rings on the ends. craft it into planks.",
    "spruce_log": "a tree trunk with dark brown bark. good for framing corners of a cabin.",
    "glass": "clear see-through block with a thin light frame. smelt sand to make it, use it for windows.",
    "sandstone": "pale yellow block with smooth layered bands. found under sand in deserts.",
    "sand": "pale yellow grainy block that falls down when nothing is under it. smelt it into glass.",
    "gravel": "gray block of small pebbles that falls like sand. sometimes drops flint when mined.",
    "dirt": "brown earthy block. grass spreads onto it and you can dig it by hand.",
    "deepslate": "very dark gray stone with vertical streaks, found deep below y level zero. slower to mine than stone.",
    "cobbled_deepslate": "dark gray chunky block, what deepslate drops when mined. tougher looking than cobblestone.",
    "obsidian": "glossy black block with purple tints. needs a diamond pickaxe, used for nether portals.",
    "glowstone": "bright yellow orange glowing block from the nether. gives off strong light.",
    "iron_block": "shiny light gray metal block with a pressed plate look. made from nine iron ingots.",
    "gold_block": "bright shiny yellow metal block. made from nine gold ingots.",
    "diamond_block": "brilliant light blue gem block. made from nine diamonds, mostly for showing off.",
    "quartz_block": "smooth bright white block from nether quartz. good for modern builds.",
    "netherrack": "red fleshy looking block that fills the nether. burns forever if lit on fire.",
    "blackstone": "black stone with gold specks, found in the nether. works like cobblestone for tools.",
    "end_stone": "pale yellow spongy looking stone that makes up the end islands.",
    "bookshelf": "wooden frame filled with colorful books. boosts enchanting tables nearby.",
    "white_wool": "soft fuzzy white block from sheep. comes in sixteen colors when dyed.",
    "red_wool": "soft fuzzy red block. sheared from a dyed sheep or crafted with red dye.",
    "blue_wool": "soft fuzzy blue block. made with lapis or cornflower dye.",
    "snow": "pure white soft block. made from four snowballs.",
    "ice": "light blue see-through slippery block. melts near light sources.",
    "packed_ice": "solid light blue block that never melts. very slippery, used for ice roads.",
    "clay": "smooth blue gray block found in shallow water. smelt it into terracotta.",
    "hay_block": "yellow bundle of wheat with brown bands. heals horses and softens falls.",
    "pumpkin": "orange ribbed block with a stem on top. carve it with shears to make a face.",
    "crafting_table": "wooden block with tools on the sides and a grid on top. used to craft most items.",
}

DIRS = ["north", "south", "east", "west"]

# Characters the model can read/write. "$" ends an answer, "\x00" is padding.
VOCAB = "\x00\n$>" + string.ascii_lowercase + string.digits + " ~-_@#.,'|()="
STOI = {c: i for i, c in enumerate(VOCAB)}


def encode(text):
    return [STOI[c] for c in text.lower() if c in STOI]


def decode(ids):
    return "".join(VOCAB[i] for i in ids)


def fmt(prompt, answer=None):
    """Training/inference text: '<request>\\n>' then the answer, ended by '$'."""
    text = f"{prompt}\n>"
    if answer is not None:
        text += answer + "$"
    return text


def _t(n):
    return f"~{n}"


def _fill(x1, y1, z1, x2, y2, z2, block, mode=""):
    cmd = f"fill {_t(x1)} {_t(y1)} {_t(z1)} {_t(x2)} {_t(y2)} {_t(z2)} {block}"
    return f"{cmd} {mode}" if mode else cmd


def reference(req):
    """The teacher: correct commands for a request, or raise ValueError."""
    p = req.split()
    op, a = p[0], p[1:]
    if op == "place":
        b, x, y, z = a[0], *map(int, a[1:4])
        return f"setblock {_t(x)} {_t(y)} {_t(z)} {b}"
    if op == "remove":
        x, y, z = map(int, a[:3])
        return f"setblock {_t(x)} {_t(y)} {_t(z)} air destroy"
    if op == "floor":
        b, w, d = a[0], int(a[1]), int(a[2])
        return _fill(0, -1, 0, w - 1, -1, d - 1, b)
    if op == "wall":
        b, n, h, axis = a[0], int(a[1]), int(a[2]), a[3]
        if axis == "x":
            return _fill(0, 0, 0, n - 1, h - 1, 0, b)
        return _fill(0, 0, 0, 0, h - 1, n - 1, b)
    if op == "box":
        b, w, h, d, mode = a[0], int(a[1]), int(a[2]), int(a[3]), a[4]
        return _fill(0, 0, 0, w - 1, h - 1, d - 1, b, "hollow" if mode == "hollow" else "")
    if op == "pillar":
        b, h = a[0], int(a[1])
        return _fill(0, 0, 0, 0, h - 1, 0, b)
    if op == "stairs":
        b, h = a[0], int(a[1])
        return "\n".join(f"setblock {_t(i)} {_t(i)} ~0 {b}" for i in range(h))
    if op == "clear":
        w, h, d = map(int, a[:3])
        return _fill(0, 0, 0, w - 1, h - 1, d - 1, "air")
    if op == "house":
        wall, floor, roof = a[0], a[1], a[2]
        w, h, d, door = int(a[3]), int(a[4]), int(a[5]), a[6]
        dx, dz = {"north": (w // 2, 0), "south": (w // 2, d - 1),
                  "west": (0, d // 2), "east": (w - 1, d // 2)}[door]
        return "\n".join([
            _fill(0, -1, 0, w - 1, h, d - 1, wall, "hollow"),
            _fill(1, -1, 1, w - 2, -1, d - 2, floor),
            _fill(0, h, 0, w - 1, h, d - 1, roof),
            _fill(dx, 0, dz, dx, 1, dz, "air"),
        ])
    if op == "roof":
        b, w, d = a[0], int(a[1]), int(a[2])
        return "\n".join(_fill(i, i, i, w - 1 - i, i, d - 1 - i, b)
                         for i in range((min(w, d) + 1) // 2))
    if op == "gable":
        b, w, d = a[0], int(a[1]), int(a[2])
        return "\n".join(_fill(0, i, i, w - 1, i, d - 1 - i, b) for i in range((d + 1) // 2))
    if op == "frame":
        b, w, h, d = a[0], int(a[1]), int(a[2]), int(a[3])
        return "\n".join(_fill(x, 0, z, x, h - 1, z, b)
                         for x, z in ((0, 0), (w - 1, 0), (0, d - 1), (w - 1, d - 1)))
    if op in ("tower", "cylinder"):
        b, rad, h = a[0], int(a[1]), int(a[2])
        out = []
        for dz in range(-rad, rad + 1):
            half = int(math.sqrt((rad + 0.5) ** 2 - dz * dz))
            out.append(_fill(rad - half, 0, rad + dz, rad + half, h - 1, rad + dz, b))
        if op == "tower":
            inner = rad - 1
            for dz in range(-inner, inner + 1):
                half = int(math.sqrt((inner + 0.5) ** 2 - dz * dz))
                out.append(_fill(rad - half, 0, rad + dz, rad + half, h - 1, rad + dz, "air"))
        return "\n".join(out)
    if op == "pyramid":
        b, w = a[0], int(a[1])
        return "\n".join(_fill(i, i, i, w - 1 - i, i, w - 1 - i, b, "hollow" if w - 2 * i > 2 else "")
                         for i in range((w + 1) // 2))
    if op == "bridge":
        b, n, axis = a[0], int(a[1]), a[2]
        rows = [(-1, 0, 2, b), (0, 0, 0, "oak_fence"), (0, 2, 2, "oak_fence")]
        if axis == "x":
            return "\n".join(_fill(0, y, z1, n - 1, y, z2, blk) for y, z1, z2, blk in rows)
        return "\n".join(_fill(z1, y, 0, z2, y, n - 1, blk) for y, z1, z2, blk in rows)
    if op == "castle_wall":
        b, n, h, axis = a[0], int(a[1]), int(a[2]), a[3]
        out = [reference(f"wall {b} {n} {h} {axis}")]
        for i in range(0, n, 2):
            x, z = (i, 0) if axis == "x" else (0, i)
            out.append(f"setblock {_t(x)} {_t(h)} {_t(z)} {b}")
        return "\n".join(out)
    if op == "windows":
        b, n, h, axis = a[0], int(a[1]), int(a[2]), a[3]
        out = [reference(f"wall {b} {n} {h} {axis}")]
        top = min(2, h - 2)
        for i in range(1, n - 1, 3):
            x, z = (i, 0) if axis == "x" else (0, i)
            out.append(_fill(x, 1, z, x, top, z, "glass"))
        return "\n".join(out)
    if op == "fence_ring":
        f, w, d = a[0], int(a[1]), int(a[2])
        return "\n".join([_fill(0, 0, 0, w - 1, 0, d - 1, f, "hollow"),
                          f"setblock {_t(w // 2)} ~0 ~0 air"])
    if op == "farm":
        w, d = int(a[0]), int(a[1])
        m = d // 2
        out = [_fill(0, -1, 0, w - 1, -1, d - 1, "farmland"), _fill(0, -1, m, w - 1, -1, m, "water")]
        if m > 0:
            out.append(_fill(0, 0, 0, w - 1, 0, m - 1, "wheat"))
        if m < d - 1:
            out.append(_fill(0, 0, m + 1, w - 1, 0, d - 1, "wheat"))
        return "\n".join(out)
    if op == "lamp_post":
        b, h = a[0], int(a[1])
        return "\n".join([_fill(0, 0, 0, 0, h - 2, 0, b), f"setblock ~0 {_t(h - 1)} ~0 lantern"])
    if op == "give":
        return f"give @s {a[0]} {int(a[1])}"
    if op == "describe":
        return "# " + DESCRIPTIONS.get(a[0], "i dont know that block yet.")
    if op == "redstone":
        import redstone_lib as R
        if a[0] == "ram":
            return R.to_compact(R.design_parts("ram", int(a[1])))
        return R.to_compact(R.design_parts(a[0]))
    if op == "logic":
        expr, vals = req[len("logic "):].split("|")
        env = dict(kv.split("=") for kv in vals.split())
        return "# " + str(int(eval_logic(expr, {k: v == "1" for k, v in env.items()})))
    if op == "truth":
        expr = req[len("truth "):]
        return "# " + "".join(str(int(eval_logic(expr, {"a": a_, "b": b_, "c": c_})))
                              for a_ in (0, 1) for b_ in (0, 1) for c_ in (0, 1))
    raise ValueError(f"unknown op {op}")


LOGIC_OPS = {"and": lambda x, y: x and y, "or": lambda x, y: x or y, "xor": lambda x, y: x != y,
             "nand": lambda x, y: not (x and y), "nor": lambda x, y: not (x or y)}


def eval_logic(expr, env):
    """Evaluate e.g. '(a and not b) or c'. Binary ops are left to right; parens group."""
    toks = expr.replace("(", " ( ").replace(")", " ) ").split()
    pos = 0

    def atom():
        nonlocal pos
        t = toks[pos]
        pos += 1
        if t == "not":
            return not atom()
        if t == "(":
            v = chain()
            pos += 1  # ')'
            return v
        if t in ("0", "1"):
            return t == "1"
        return bool(env[t])

    def chain():
        nonlocal pos
        v = atom()
        while pos < len(toks) and toks[pos] in LOGIC_OPS:
            op = toks[pos]
            pos += 1
            v = LOGIC_OPS[op](v, atom())
        return bool(v)

    return chain()


def random_expr(depth=0):
    if depth >= 2 or random.random() < 0.3:
        v = random.choice("abc")
        return f"not {v}" if random.random() < 0.25 else v
    left, right = random_expr(depth + 1), random_expr(depth + 1)
    e = f"{left} {random.choice(list(LOGIC_OPS))} {right}"
    if depth > 0:
        e = f"({e})"
    return f"not {e}" if random.random() < 0.15 else e


REDSTONE_DESIGNS = ["not", "or", "nor", "nand", "and", "xor", "half_adder", "full_adder",
                    "rs_latch", "d_latch"]


def _fake_block():
    """Made-up names teach the model to copy block names it has never seen."""
    parts = random.randint(1, 2)
    return "_".join("".join(random.choices(string.ascii_lowercase, k=random.randint(3, 7)))
                    for _ in range(parts))


def _block():
    return _fake_block() if random.random() < 0.15 else random.choice(BLOCKS)


def random_request():
    r = random.randint
    op = random.choices(
        ["place", "remove", "floor", "wall", "box", "pillar", "stairs", "clear", "house", "give",
         "describe", "roof", "gable", "frame", "redstone", "logic", "truth",
         "tower", "cylinder", "pyramid", "bridge", "castle_wall", "windows", "fence_ring", "farm",
         "lamp_post"],
        weights=[10, 6, 6, 8, 8, 4, 5, 3, 14, 5, 7, 8, 8, 7, 8, 9, 5,
                 8, 5, 6, 6, 6, 6, 5, 5, 5])[0]
    if op in ("tower", "cylinder"):
        return f"{op} {_block()} {r(2, 5)} {r(1, 10)}"
    if op == "pyramid":
        return f"pyramid {_block()} {r(3, 15)}"
    if op == "bridge":
        return f"bridge {_block()} {r(2, 15)} {random.choice('xz')}"
    if op == "castle_wall":
        return f"castle_wall {_block()} {r(2, 15)} {r(2, 9)} {random.choice('xz')}"
    if op == "windows":
        return f"windows {_block()} {r(3, 15)} {r(3, 10)} {random.choice('xz')}"
    if op == "fence_ring":
        return f"fence_ring {random.choice(FENCES)} {r(3, 15)} {r(3, 15)}"
    if op == "farm":
        return f"farm {r(3, 15)} {r(3, 15)}"
    if op == "lamp_post":
        return f"lamp_post {random.choice(FENCES + ['oak_log', 'stone_bricks'])} {r(2, 8)}"
    if op == "redstone":
        if random.random() < 0.4:
            return f"redstone ram {r(1, 8)}"
        return f"redstone {random.choice(REDSTONE_DESIGNS)}"
    if op == "logic":
        return f"logic {random_expr()} | a={r(0, 1)} b={r(0, 1)} c={r(0, 1)}"
    if op == "truth":
        return f"truth {random_expr()}"
    if op == "roof":
        return f"roof {_block()} {r(1, 15)} {r(1, 15)}"
    if op == "gable":
        return f"gable {_block()} {r(1, 15)} {r(1, 15)}"
    if op == "frame":
        return f"frame {_block()} {r(1, 15)} {r(1, 10)} {r(1, 15)}"
    if op == "place":
        return f"place {_block()} {r(-8, 8)} {r(-3, 8)} {r(-8, 8)}"
    if op == "remove":
        return f"remove {r(-8, 8)} {r(-3, 8)} {r(-8, 8)}"
    if op == "floor":
        return f"floor {_block()} {r(1, 15)} {r(1, 15)}"
    if op == "wall":
        return f"wall {_block()} {r(1, 15)} {r(1, 10)} {random.choice('xz')}"
    if op == "box":
        return f"box {_block()} {r(1, 15)} {r(1, 10)} {r(1, 15)} {random.choice(['hollow', 'solid'])}"
    if op == "pillar":
        return f"pillar {_block()} {r(1, 10)}"
    if op == "stairs":
        return f"stairs {_block()} {r(1, 10)}"
    if op == "clear":
        return f"clear {r(1, 15)} {r(1, 10)} {r(1, 15)}"
    if op == "house":
        return (f"house {_block()} {_block()} {_block()} {r(4, 15)} {r(2, 8)} {r(4, 15)} "
                f"{random.choice(DIRS)}")
    if op == "give":
        item = _fake_block() if random.random() < 0.1 else random.choice(ITEMS)
        return f"give {item} {r(1, 64)}"
    return f"describe {random.choice(list(DESCRIPTIONS))}"


def load_corrections():
    if not os.path.exists(CORRECTIONS_PATH):
        return []
    out = []
    with open(CORRECTIONS_PATH, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                out.append(json.loads(line))
    return out


def save_correction(req, commands):
    with open(CORRECTIONS_PATH, "a", encoding="utf-8") as f:
        f.write(json.dumps({"req": req, "out": commands}) + "\n")


def sample(corrections, correction_rate=0.25):
    """One (request, answer) pair. Your corrections are mixed in heavily so they stick."""
    if corrections and random.random() < correction_rate:
        c = random.choice(corrections)
        return c["req"], c["out"]
    req = random_request()
    return req, reference(req)


# Argument kinds per action: b=block, a=axis, m=hollow/solid, d=door side,
# (lo, hi)=number, pulled into the range the Builder was trained on.
XYZ = [(-8, 8), (-3, 8), (-8, 8)]
SIZE, TALL = (1, 15), (1, 10)
SHAPES = {
    "place": ["b", *XYZ], "remove": XYZ, "floor": ["b", SIZE, SIZE],
    "wall": ["b", SIZE, TALL, "a"], "box": ["b", SIZE, TALL, SIZE, "m"],
    "pillar": ["b", TALL], "stairs": ["b", TALL], "clear": [SIZE, TALL, SIZE],
    "house": ["b", "b", "b", (4, 15), (2, 8), (4, 15), "d"], "give": ["b", (1, 64)],
    "describe": ["b"], "roof": ["b", SIZE, SIZE], "gable": ["b", SIZE, SIZE],
    "frame": ["b", SIZE, TALL, SIZE],
    "tower": ["b", (2, 5), TALL], "cylinder": ["b", (2, 5), TALL], "pyramid": ["b", (3, 15)],
    "bridge": ["b", (2, 15), "a"], "castle_wall": ["b", (2, 15), (2, 9), "a"],
    "windows": ["b", (3, 15), (3, 10), "a"], "fence_ring": ["b", (3, 15), (3, 15)],
    "farm": [(3, 15), (3, 15)], "lamp_post": ["b", (2, 8)],
}


def validate_request(req):
    """Check a request line the chat model wrote. Returns a cleaned line or raises ValueError."""
    p = req.strip().lower().replace("minecraft:", "").split()
    if not p:
        raise ValueError("empty request")
    if p[0] == "redstone":
        if len(p) == 3 and p[1] == "ram" and p[2].isdigit():
            return f"redstone ram {max(1, min(8, int(p[2])))}"
        if len(p) == 2 and p[1] in REDSTONE_DESIGNS:
            return f"redstone {p[1]}"
        if len(p) == 2 and p[1] == "ram_byte":
            return "redstone ram 8"
        raise ValueError(f"known redstone designs: {', '.join(REDSTONE_DESIGNS)}, ram <1-8>")
    if p[0] in ("logic", "truth"):
        line = " ".join(p)
        try:
            reference(line)
        except Exception:
            raise ValueError("logic needs e.g. 'logic (a and not b) or c | a=1 b=0 c=1'")
        return line
    if p[0] not in SHAPES:
        raise ValueError(f"unknown action '{p[0]}'")
    shape = SHAPES[p[0]]
    if len(p) - 1 != len(shape):
        raise ValueError(f"'{p[0]}' needs {len(shape)} values, got {len(p) - 1}")
    out = [p[0]]
    for kind, val in zip(shape, p[1:]):
        if isinstance(kind, tuple):
            try:
                n = int(float(val))
            except ValueError:
                raise ValueError(f"'{val}' should be a number")
            val = str(max(kind[0], min(kind[1], n)))
        elif kind == "b" and not all(c in string.ascii_lowercase + "_" for c in val):
            raise ValueError(f"bad block name '{val}'")
        elif kind == "a" and val not in ("x", "z"):
            raise ValueError("wall axis must be x or z")
        elif kind == "m" and val not in ("hollow", "solid"):
            raise ValueError("box must be hollow or solid")
        elif kind == "d" and val not in DIRS:
            raise ValueError("door side must be north/south/east/west")
        out.append(val)
    return " ".join(out)
