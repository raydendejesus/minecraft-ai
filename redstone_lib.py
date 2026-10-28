"""Verified redstone designs for Bedrock.

Rules learned by testing in the lab (lab_calibrate*.py), not guessed:
  * repeater/comparator "minecraft:cardinal_direction" is the side the signal comes FROM
    (signal flowing east -> "west")
  * torch "torch_facing_direction" is the side its support block is on
  * piston "facing_direction": 1 up, 2 south, 3 north, 4 east, 5 west
  * dust carries 15 blocks; a straight dust line only powers what's at its end

Every design is a list of (x, y, z, block) relative to the build spot, signals flowing
east (+x). Inputs are levers; outputs are lamps. `test_lab.py` checks each design's
truth table on the lab server.
"""

OPPOSITE = {"east": "west", "west": "east", "north": "south", "south": "north"}


def lever(x, z, y=0):
    return (x, y, z, 'lever ["lever_direction"="up_north_south"]')


def dust(x, z, y=0):
    return (x, y, z, "redstone_wire")


def rep(x, z, to="east", y=0, delay=0):
    return (x, y, z, f'unpowered_repeater ["minecraft:cardinal_direction"="{OPPOSITE[to]}",'
                     f'"repeater_delay"={delay}]')


def block(x, z, y=0, b="stone"):
    return (x, y, z, b)


def torch(x, z, support="west", y=0):
    return (x, y, z, f'redstone_torch ["torch_facing_direction"="{support}"]')


def lamp(x, z, y=0):
    return (x, y, z, "redstone_lamp")


def comparator(x, z, to="east", subtract=False, y=0):
    return (x, y, z, f'unpowered_comparator ["minecraft:cardinal_direction"="{OPPOSITE[to]}",'
                     f'"output_subtract_bit"={"true" if subtract else "false"}]')


def bridge_north(x, z_from, over):
    """Carry a wire north along x, from dust at (x, z_from) over a wire running east-west at
    z=over. Climbs onto floating blocks so the two wires never touch. Ends with dust at
    (x, over - 3) on the ground. z_from must be over + 3."""
    assert z_from == over + 3
    c = over
    return [dust(x, c + 3),
            block(x, c + 2), dust(x, c + 2, y=1),
            block(x, c + 1, y=1), dust(x, c + 1, y=2),
            block(x, c, y=1), dust(x, c, y=2),
            block(x, c - 1, y=1), dust(x, c - 1, y=2),
            block(x, c - 2), dust(x, c - 2, y=1),
            dust(x, c - 3)]


def inverter(x, z):
    """Signal in from the west at x-1 -> repeater, block, torch. Output powers x+3."""
    return [rep(x, z), block(x + 1, z), torch(x + 2, z, "west")]


# ---- gates: name -> (parts, input positions, output lamp position, truth function)

def g_not():
    return [lever(0, 0), *inverter(1, 0), lamp(4, 0)], [(0, 0)], (4, 0), lambda a: not a


def g_or():
    parts = [lever(0, 0), lever(0, 2), dust(1, 0), dust(2, 0), dust(2, 1), dust(2, 2), dust(1, 2),
             dust(3, 1), lamp(4, 1)]
    return parts, [(0, 0), (0, 2)], (4, 1), lambda a, b: a or b


def g_nor():
    parts = [lever(0, 0), lever(0, 2), dust(1, 0), dust(2, 0), dust(2, 1), dust(2, 2), dust(1, 2),
             *inverter(3, 1), lamp(6, 1)]
    return parts, [(0, 0), (0, 2)], (6, 1), lambda a, b: not (a or b)


def _inverted_pair():
    """NOT A on row 0, NOT B on row 4, joined by a dust column at x=4 (= NAND)."""
    return [lever(0, 0), lever(0, 4), *inverter(1, 0), *inverter(1, 4),
            *[dust(4, z) for z in range(5)]]


def g_nand():
    return [*_inverted_pair(), dust(5, 2), lamp(6, 2)], [(0, 0), (0, 4)], (6, 2), \
        lambda a, b: not (a and b)


def g_and():
    return [*_inverted_pair(), *inverter(5, 2), lamp(8, 2)], [(0, 0), (0, 4)], (8, 2), \
        lambda a, b: a and b


def g_xor():
    """Two comparators in subtract mode: C1 = A - B, C2 = B - A, outputs OR'd together.
    Every comparator input goes through a repeater so all signals arrive at full strength 15."""
    parts = [
        # A (lever at 0,1) -> C1 rear, and branch south -> C2 side
        lever(0, 1), dust(1, 1), dust(2, 1), dust(3, 1), rep(4, 1),
        dust(3, 2), dust(3, 3), dust(4, 3), dust(5, 3), rep(5, 4, to="south"),
        # B (lever at 0,5) -> C2 rear, and branch north over A's wire -> C1 side
        lever(0, 5), dust(1, 5), dust(2, 5), dust(3, 5), rep(4, 5),
        *bridge_north(1, 4, over=1),
        dust(2, -2), dust(3, -2), dust(4, -2), dust(5, -2), dust(5, -1), rep(5, 0, to="south"),
        comparator(5, 1, subtract=True), comparator(5, 5, subtract=True),
        # OR the two comparator outputs into the lamp
        dust(6, 1), dust(7, 1), dust(7, 2), dust(7, 3), dust(7, 4), dust(7, 5), dust(6, 5),
        dust(8, 3), lamp(9, 3),
    ]
    return parts, [(0, 1), (0, 5)], (9, 3), lambda a, b: a != b


def shift(parts, dx, dz, dy=0):
    return [(x + dx, y + dy, z + dz, b) for x, y, z, b in parts]


def swap(parts, pos, new):
    """Replace whatever sits at ground position pos=(x, z) (e.g. a lever -> dust)."""
    out = [p for p in parts if not (p[0] == pos[0] and p[2] == pos[1] and p[1] == 0)]
    return out + ([new] if new else [])


def g_half_adder():
    """sum = A xor B (C1 = A-B, C2 = B-A, merged), carry = B - C2 = A and B (C4).
    Rows are kept apart so no dust touches a different signal."""
    parts = _half_adder_parts()
    return parts, [(0, 1), (0, 6)], [(9, 3), (9, 7)], lambda a, b: (a != b, a and b)


def g_full_adder():
    """Two half adders: HA1(A, B) -> s1, c1;  HA2(s1, Cin) -> sum, c2;  cout = c1 or c2.
    HA2 sits at offset (10, 2). c1 runs south of everything along z=11 to meet c2."""
    ha1 = _half_adder_parts()
    ha1 = swap(ha1, (9, 3), rep(9, 3))             # s1 out, refreshed -> into HA2's A input
    ha1 = swap(ha1, (9, 7), None)                  # c1 no longer ends in a lamp
    ha2 = shift(_half_adder_parts(), 10, 2)
    ha2 = swap(ha2, (10, 3), dust(10, 3))          # HA2's A lever becomes the s1 wire
    ha2 = swap(ha2, (19, 9), dust(19, 9))          # c2 continues toward the OR
    carry = [dust(8, 8), dust(8, 9), dust(8, 10), dust(8, 11),
             *[dust(x, 11) for x in range(9, 13)], rep(13, 11),
             *[dust(x, 11) for x in range(14, 22)],
             dust(20, 9), dust(20, 10), lamp(22, 11)]
    parts = ha1 + ha2 + carry
    return parts, [(0, 1), (0, 6), (10, 8)], [(19, 5), (22, 11)], \
        lambda a, b, c: ((a + b + c) % 2, a + b + c >= 2)


def _half_adder_parts():
    return [
        lever(0, 1), dust(1, 1), dust(2, 1), dust(3, 1), rep(4, 1),           # A -> C1 rear
        dust(3, 2), dust(3, 3), dust(3, 4), dust(4, 4), dust(5, 4),
        rep(5, 5, to="south"),                                                 # A -> C2 side
        lever(0, 6), dust(1, 6), dust(2, 6), dust(3, 6), rep(4, 6),           # B -> C2 rear
        dust(1, 5), *bridge_north(1, 4, over=1),                               # B over A ...
        dust(2, -2), dust(3, -2), dust(4, -2), dust(5, -2), dust(5, -1),
        rep(5, 0, to="south"),                                                 # ... -> C1 side
        dust(3, 7), dust(4, 7), rep(5, 7),                                     # B -> C4 rear
        comparator(5, 1, subtract=True), comparator(5, 6, subtract=True),
        comparator(6, 7, subtract=True),                                       # C4, side = C2 out
        # sum: merge C1 and C2 outputs
        dust(6, 1), dust(7, 1), dust(7, 2), dust(7, 3), dust(7, 4), dust(7, 5), dust(7, 6),
        dust(6, 6), dust(8, 3), lamp(9, 3),
        # carry
        rep(7, 7), dust(8, 7), lamp(9, 7),
    ]


GATES = {"not": g_not, "or": g_or, "nor": g_nor, "nand": g_nand, "and": g_and, "xor": g_xor,
         "half_adder": g_half_adder, "full_adder": g_full_adder}


# ---- memory: name -> (parts, {input name: position}, [output lamps], steps)
# steps: list of (inputs switched on this step, expected lamp states)

def m_rs_latch():
    """Two torch NOT gates feeding each other. S sets Q on, R resets it, Q holds in between."""
    parts = [
        block(2, 0), torch(3, 0, "west"), lamp(3, -1),           # X block, T1 = Q, Q lamp
        dust(4, 0), dust(4, 1), rep(4, 2, to="south"),            # Q -> Y
        block(4, 3), torch(4, 4, "north"),                        # Y block, T2 = not Q
        dust(3, 4), dust(2, 4), dust(1, 4), dust(1, 3), dust(1, 2), dust(1, 1),
        dust(0, 1), dust(0, 0), rep(1, 0),                        # not Q -> X
        rep(2, -1, to="south"), lever(2, -2),                     # R input into X
        rep(5, 3, to="west"), lever(6, 3),                        # S input into Y
    ]
    inputs = {"S": (6, 3), "R": (2, -2)}
    steps = [({"S"}, [1]), (set(), [1]), ({"R"}, [0]), (set(), [0]), ({"S"}, [1]), (set(), [1])]
    return parts, inputs, [(3, -1)], steps


def _ram_bits(n):
    """n D latches in a column (one every 4 blocks along z) sharing one write-enable line.
    Each bit: D lever -> repeater -> lamp. A side repeater locks it whenever write is OFF,
    so it holds its bit. The lock line is NOT(write), run down x=4 with refresh repeaters.

    The lock line must NOT touch the lamps: a lamp powered by a repeater becomes a powered
    block and would feed the lock line, freezing the latch forever (found in the lab)."""
    parts = [lever(4, -5), rep(4, -4, to="south"), block(4, -3), torch(4, -2, "north")]
    last = 4 * (n - 1) + 2
    for z in range(-1, last + 1):
        parts.append(rep(4, z, to="south") if z % 12 == 0 and z > 0 else dust(4, z))
    inputs, outputs = {"W": (4, -5)}, []
    for i in range(n):
        z = 4 * i
        parts += [lever(0, z), rep(1, z), lamp(2, z),
                  rep(1, z + 1, to="north"),             # lock repeater into the bit's side
                  dust(3, z + 2), dust(2, z + 2), dust(1, z + 2)]   # branch from the lock line
        inputs[f"D{i}"] = (0, z)
        outputs.append((2, z))
    return parts, inputs, outputs


def m_d_latch():
    parts, inputs, outputs = _ram_bits(1)
    steps = [({"W", "D0"}, [1]), ({"D0"}, [1]), (set(), [1]),   # written 1, holds when W off
             ({"W"}, [0]), (set(), [0]), ({"D0"}, [0]),         # written 0, ignores D when W off
             ({"W", "D0"}, [1])]
    return parts, inputs, outputs, steps


def m_ram_byte():
    parts, inputs, outputs = _ram_bits(8)
    a = [1, 0, 1, 1, 0, 0, 1, 0]
    b = [0, 1, 0, 0, 1, 1, 0, 1]
    on = lambda bits: {f"D{i}" for i, v in enumerate(bits) if v}
    steps = [(on(a) | {"W"}, a),          # write byte a
             (on(b), a),                  # change inputs with write off -> still a
             (set(), a),
             (on(b) | {"W"}, b),          # write byte b
             (set(), b)]
    return parts, inputs, outputs, steps


MEMORY = {"rs_latch": m_rs_latch, "d_latch": m_d_latch, "ram_byte": m_ram_byte}


def to_commands(parts, at=(0, 0, 0)):
    ox, oy, oz = at
    return [f"setblock ~{x + ox} ~{y + oy} ~{z + oz} {b}" for x, y, z, b in parts]


# ---- compact parts language the Builder model reads and writes
#   b x y z        stone block          d x y z      redstone dust
#   l x y z        lever                m x y z      lamp
#   r x y z e      repeater -> east     t x y z w    torch on a west support
#   c x y z e s    comparator -> east, s = subtract mode (k = compare mode)

DESIGNS = {**{k: v for k, v in GATES.items()}, **{k: v for k, v in MEMORY.items()}}


def to_compact(parts):
    lines = []
    for x, y, z, b in parts:
        name = b.split()[0]
        if name == "unpowered_repeater":
            code = f"r {x} {y} {z} {OPPOSITE[_state(b, 'minecraft:cardinal_direction')][0]}"
        elif name == "unpowered_comparator":
            sub = "s" if "output_subtract_bit\"=true" in b else "k"
            code = f"c {x} {y} {z} {OPPOSITE[_state(b, 'minecraft:cardinal_direction')][0]} {sub}"
        elif name == "redstone_torch":
            code = f"t {x} {y} {z} {_state(b, 'torch_facing_direction')[0]}"
        else:
            code = {"redstone_wire": "d", "lever": "l", "redstone_lamp": "m", "stone": "b"}[name] + f" {x} {y} {z}"
        lines.append((0 if name == "stone" else 1, y, z, x, code))
    # support blocks first so torches never pop off, then a fixed reading order
    return "\n".join(l[-1] for l in sorted(set(lines)))


def _state(b, key):
    return b.split(f'"{key}"="')[1].split('"')[0]


DIR = {"n": "north", "s": "south", "e": "east", "w": "west"}


def from_compact(text):
    """Compact lines -> parts. Raises ValueError on anything malformed."""
    parts = []
    for line in text.strip().splitlines():
        p = line.split()
        x, y, z = map(int, p[1:4])
        k = p[0]
        if k == "b":
            parts.append(block(x, z, y))
        elif k == "d":
            parts.append(dust(x, z, y))
        elif k == "l":
            parts.append(lever(x, z, y))
        elif k == "m":
            parts.append(lamp(x, z, y))
        elif k == "r":
            parts.append(rep(x, z, DIR[p[4]], y))
        elif k == "t":
            parts.append(torch(x, z, DIR[p[4]], y))
        elif k == "c":
            parts.append(comparator(x, z, DIR[p[4]], p[5] == "s", y))
        else:
            raise ValueError(f"unknown part '{k}'")
    return parts


def design_parts(name, n=None):
    """Parts for a named design ('ram' takes a bit count)."""
    if name == "ram":
        return _ram_bits(n)[0]
    return DESIGNS[name]()[0]
