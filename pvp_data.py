"""Lessons for the PvP model: player vs player only.

It reads a duel from its own side and answers one move:
    hp 14 abs 4 sprint regen | diamond_sword shield gap 2 | foe 2.7 hp 11 diamond blocking | foe did combo strafe block
    > axe

The teacher looks ahead: for every move it could make now, it plays the next 4 seconds out several
times (it as a solid all-round player, the opponent as itself) and picks the move that comes out
best. That makes the lessons better than any fixed rulebook, including the "expert" one it starts
from. The opponents are 11 play styles at different skill levels, in 8 kits, on flat
ground or hills (where height changes who can reach whom, see pvp_sim).

The lessons are written ahead of time by build_pvp_bank.py (the look-ahead is slow), into
pvp_lessons.jsonl. 1 in 20 is kept apart for the training log's accuracy check.
"""

import json
import math
import os
import random

import pvp_sim as S

HERE = os.path.dirname(os.path.abspath(__file__))
BANK = os.path.join(HERE, "pvp_lessons.jsonl")
CORRECTIONS_PATH = os.path.join(HERE, "pvp_corrections.jsonl")
HORIZON, ROLLOUTS = 16, 6          # 4 seconds ahead, 6 times per move
ITEM_VALUE = {"gaps": 4, "heals": 4, "pearls": 1.5, "strength_pots": 2, "speed_pots": 1, "arrows": 0.15}
EXPERT = S.bot("expert", 1.0)


def _value(d, i):
    me, foe = d.p[i], d.p[1 - i]
    w = d.winner()
    if w is not None:
        return 40.0 if w == i else -40.0
    items = sum(getattr(me, k) * v for k, v in ITEM_VALUE.items())
    return me.health() - foe.health() + 0.25 * items


def candidates(d, i):
    seen, out = set(), []
    for m in S.MOVES:
        legal = d._legal(i, m)
        if legal != m:
            continue
        if m in ("hit", "crit", "combo", "axe") and S.reach_gap(d.dist, d.dy(i)) > S.REACH + S.SPRINT * S.TICK:
            continue                        # out of reach these are just "in"
        if legal not in seen:
            seen.add(legal)
            out.append(legal)
    return out or ["wait"]


def teacher(d, i, foe_move):
    """The move for player i that comes out best over the next few seconds."""
    seeds = [random.randrange(10 ** 9) for _ in range(ROLLOUTS)]   # the same futures for every move
    best, best_score = None, None
    for m in candidates(d, i):
        score = 0.0
        for s in seeds:
            r = random.Random(s)
            c = d.copy(r)
            for t in range(HORIZON):
                if c.over():
                    break
                mine = m if t == 0 else EXPERT(c, i, r)
                theirs = foe_move(c, 1 - i, r)
                c.step(*((mine, theirs) if i == 0 else (theirs, mine)))
            score += _value(c, i)
        if best_score is None or score > best_score:
            best, best_score = m, score
    return best


def opponent(r):
    style = r.choice(S.STYLES + ["expert", "expert"])
    return S.bot(style, r.uniform(0.6, 1.0) if style != "expert" else r.uniform(0.85, 1.0))


def duel(seed, record=True):
    """One teacher duel. Returns (lessons, winner, opponent style, kit)."""
    r = random.Random(seed)
    random.seed(seed)
    d = S.Duel(rng=r)
    foe = opponent(r)
    lessons = []
    while not d.over():
        m = teacher(d, 0, foe)
        if record:
            lessons.append((d.state_text(0), m))
        d.step(m, foe(d, 1, r))
    return lessons, d.winner(), foe.style, d.kit


def pvp_question():
    """Fight math with this sim's (Bedrock-based) numbers."""
    r = random
    kind = r.choice(["taken", "hits", "kit"])
    if kind == "taken":
        dmg, armor = r.choice([5, 6, 7, 8, 9, 10, 12]), r.choice(list(S.ARMOR))
        return f"pvpmath taken {dmg} armor {armor}", f"# {S.armor_cut(dmg, armor):.1f}"
    if kind == "hits":
        w, armor, crit = r.choice(list(S.SWORD)), r.choice(list(S.ARMOR)), r.random() < 0.3
        per = S.armor_cut(S.SWORD[w] * (1.5 if crit else 1), armor)
        hits = int(-(-20 // per))
        return f"pvpmath hits {w} armor {armor}" + (" crit" if crit else ""), f"# {hits}"
    k = r.choice(list(S.KITS))
    return f"pvpkit {k}", "# " + " ".join(f"{a} {v}" for a, v in S.KITS[k].items())


GEOMETRY = os.environ.get("MCAI_GEOMETRY") == "1"     # the math / geometry / hitbox stage


def geometry_question():
    """Math and geometry a PvP player uses, with the numbers the fights themselves use (pvp_sim)."""
    r = random
    kind = r.choice(["hyp", "hyp", "dist3", "reach", "reach", "farthest", "aim", "hitbox", "fact"])
    if kind == "hyp":                                  # Pythagoras
        a, b = round(r.uniform(0.2, 6), 1), round(r.uniform(0.2, 6), 1)
        return f"math hypotenuse {a} {b}", f"# {math.hypot(a, b):.2f}"
    if kind == "dist3":
        p = [round(r.uniform(-5, 5), 1) for _ in range(6)]
        d = math.dist(p[:3], p[3:])
        return "math distance " + " ".join(map(str, p)), f"# {d:.2f}"
    dy = r.choice([-2, -1, 0, 1, 2])
    me_sneak, t_sneak = r.random() < 0.25, r.random() < 0.25
    eye, height = (S.SNEAK if me_sneak else S.STAND)[0], (S.SNEAK if t_sneak else S.STAND)[1]
    pose = (" me sneaking" if me_sneak else "") + (" target sneaking" if t_sneak else "")
    where = f"up {dy}" if dy > 0 else f"down {-dy}" if dy < 0 else "level"
    if kind == "reach":                                # can I hit them from here?
        dist = round(r.uniform(2.0, 4.0), 1)
        gap = S.reach_gap(dist, dy, eye, height)
        return f"pvpmath reach {dist} {where}{pose}", f"# {'yes' if gap <= S.REACH else 'no'} {gap:.2f}"
    if kind == "farthest":                             # how far away can I hit them?
        far = next(x / 100 for x in range(700, 0, -1) if S.reach_gap(x / 100, dy, eye, height) <= S.REACH)
        return f"pvpmath farthest {where}{pose}", f"# {far:.2f}"
    if kind == "aim":                                  # the nearest part of their hitbox
        e = eye - dy                                   # your eyes, measured from their feet
        if e < 0:
            part = "feet, the bottom of their box is above your eyes"
        elif e > height:
            part = "head, the top of their box is below your eyes"
        else:
            part = "straight ahead at their " + ("legs" if e < 0.75 else "body" if e < height - 0.4 else "head")
        return f"pvpmath aim {where}{pose}", f"# {part}"
    if kind == "hitbox":
        p = r.choice(["standing", "sneaking"])
        e, h = S.STAND if p == "standing" else S.SNEAK
        return f"pvpinfo hitbox {p}", f"# 0.6 wide {h} tall eyes {e}"
    fact = r.choice([
        ("pvpinfo reach", "# 3 blocks from your eyes to the nearest point of their hitbox"),
        ("pvpinfo headshot", "# no headshot bonus, a hit does the same damage anywhere, aim at the nearest part for reach"),
        ("pvpinfo high ground", "# higher up you reach down a slope to their head, so you must be closer than they must be"),
        ("pvpinfo immunity", "# 0.5 s after a hit, only a bigger hit does the difference"),
        ("pvpinfo shield", "# sneak to raise it, 0.25 s to come up, hitting it knocks you back, an axe disables it 5 s"),
        ("pvpinfo wtap", "# a sprint hit ends your sprint, let go of w and press it again before the next one")])
    return fact


_bank, _held = None, None


def _load():
    global _bank, _held
    if _bank is None:
        _bank, _held = [], []
        with open(BANK, encoding="utf-8") as f:
            for n, line in enumerate(f):
                (_held if n % 20 == 0 else _bank).append(tuple(json.loads(line)))


_answers = {}


def sample(corrections, correction_rate=0.25):
    _load()
    if corrections and random.random() < correction_rate:
        c = random.choice(corrections)
        return c["req"], c["out"]
    if GEOMETRY and random.random() < 0.2:
        return geometry_question()
    if random.random() < 0.05:
        return pvp_question()
    return random.choice(_bank)


def random_request():
    _load()
    req, out = random.choice(_held)
    _answers[req] = out
    return req


def reference(req):
    return _answers[req]


def load_corrections():
    if not os.path.exists(CORRECTIONS_PATH):
        return []
    with open(CORRECTIONS_PATH, encoding="utf-8") as f:
        return [json.loads(l) for l in f if l.strip()]
