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


_bank, _held = None, None


def _load():
    global _bank, _held
    if _bank is None:
        _bank, _held = [], []
        with open(BANK, encoding="utf-8") as f:
            for n, line in enumerate(f):
                (_held if n % 20 == 0 else _bank).append(tuple(json.loads(line)))


_answers = {}


def sample(corrections, correction_rate=0.1):
    _load()
    if corrections and random.random() < correction_rate:
        c = random.choice(corrections)
        return c["req"], c["out"]
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
