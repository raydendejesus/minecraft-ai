"""Training data for the Fight model.

It reads the fight state and answers one move:
    hp 14 food 2 iron_sword armor iron shield | creeper 3 hp20 fuse | zombie 6 hp20
    > shield

Moves: attack <mob> | crit <mob> | shoot <mob> | approach <mob> | retreat | flee | strafe |
       shield | eat | hide (dig into a wall) | unhide | wait
It also learns how every mob attacks:   mobinfo creeper  > # sneaks up, hisses ...
It also learns fight math with Bedrock numbers:
    math hits iron_sword zombie        > # 3
    math taken 7 armor iron            > # 2.8
    math blast 2 armor none            > # 14.7
"""

import json
import os
import random

import fight_sim as S

HERE = os.path.dirname(os.path.abspath(__file__))
CORRECTIONS_PATH = os.path.join(HERE, "fight_corrections.jsonl")


RANGED = {k for k, s in S.MOBS.items() if s["style"] == "ranged"}


def teacher(f):
    """An experienced player's call for this moment."""
    threats = sorted(f.threats(), key=lambda m: m.dist)
    if not threats:
        return "wait"
    near = threats[0]
    kinds = {m.kind for m in threats}

    if f.digging:
        return "hide"                         # finish sealing the wall, don't run mid-dig
    # sealed in a wall: refill hunger so health comes back, wait for them to give up
    if f.hidden:
        if not f.full and f.food:
            return "eat"
        if f.hp >= 18 and "warden" not in kinds:
            return "unhide"
        return "wait"

    # a warden: never fight it, hiding doesn't help either (its boom goes through walls)
    if "warden" in kinds:
        return "flee"

    # a duel against another player: no running, out-play it
    if near.kind == "pvp_bot":
        bot = near
        if bot.drawn and bot.dist > S.REACH:
            return "shield" if f.shield else "strafe"     # block its arrow
        if f.hp <= 8 and f.food:
            return "eat"                                  # golden apple, even mid-fight
        if bot.shielding and bot.dist <= S.REACH:
            return "wait"                                 # don't swing into a raised shield
        if bot.dist > 7 and bot.arrows:
            return "wait"                                 # its arrows get blocked, let it run dry
        if bot.dist <= S.REACH:
            return "combo pvp_bot" if f.sprint_ready else "attack pvp_bot"   # W-tap combo
        return "approach pvp_bot"

    # a lit creeper close by: get out of the blast, or block it
    for m in threats:
        if m.kind == "creeper" and m.fuse is not None and m.dist < 6:
            if m.dist <= S.REACH and m.hp <= S.WEAPONS[f.weapon] and m.fuse > S.TICK:
                return "attack creeper"       # one hit kills it before it blows
            return "shield" if f.shield and m.dist < 4 else "retreat"

    danger = S.danger(f)
    # very low and losing: dig into a wall and wait for health to come back
    if f.hp <= 6 and f.dig and danger > f.hp * 0.5 and (f.full or f.food):
        return "hide"

    # a fight we can't win: walk away
    if danger > f.hp * 0.85:
        return "hide" if f.dig and near.dist > 3 and (f.full or f.food) else "flee"

    # heal when there's a breather
    if f.hp <= 8 and f.food > 0 and near.dist > 4:
        return "eat"

    # pick the most dangerous target: creepers, then ranged mobs, then the closest
    target = min(threats, key=lambda m: (0 if m.kind == "creeper" else 1 if m.kind in RANGED else 2, m.dist))
    if target.kind == "ghast":
        return "shoot ghast" if f.bow and f.arrows else "flee"
    if target.kind == "phantom":
        if f.bow and f.arrows:
            return "shoot phantom"
        if target.dist <= S.REACH:
            return "attack phantom"           # it's swooping in right now
        return "shield" if f.shield else "wait"
    if target.kind in RANGED:
        if f.bow and f.arrows and target.dist > 5:
            return f"shoot {target.kind}"
        if target.dist > S.REACH:
            return f"approach {target.kind}"
        return f"attack {target.kind}"
    if target.kind == "enderman":             # arrows don't work on endermen
        return "attack enderman" if target.dist <= S.REACH else "approach enderman"
    if target.kind == "creeper" and target.dist > S.REACH:
        if f.bow and f.arrows and target.dist > 4:
            return "shoot creeper"
        # don't walk into a creeper: deal with others, or stand still and let it come to you
        others = [m for m in threats if m.kind != "creeper"]
        if others and others[0].dist <= S.REACH:
            return f"attack {others[0].kind}"
        if f.bow and f.arrows:
            return "shoot creeper"
        return "strafe"
    if target.kind == "creeper":
        # in reach and not lit: hit it, then back off when it lights (hit and run)
        return "attack creeper"
    # kite: two or more melee mobs on us at once -> back off so they string out, fight one at a time
    swarm = [m for m in threats if m.dist <= S.REACH and m.s["style"] == "melee"]
    if len(swarm) >= 2 and f.hp < 16:
        return "retreat"
    if near.dist <= S.REACH:
        return f"attack {near.kind}"
    if f.bow and f.arrows and near.dist > 6:
        return f"shoot {near.kind}"
    return f"approach {near.kind}"


def scenario_for(seed):
    """Same mix everywhere: mostly normal fights, plus hordes of 2-5 and duels vs the PvP bot."""
    k = seed % 20
    if k < 4:
        return dict(scenario="horde", n_mobs=2 + seed % 4)
    if k < 7:
        return dict(scenario="duel")
    return {}


def episode(rng=None, max_steps=160):
    seed = random.randrange(10 ** 9)
    f = S.Fight(rng or random.Random(seed), **scenario_for(seed))
    pairs = []
    for _ in range(max_steps):
        if f.over():
            break
        a = teacher(f)
        pairs.append((f.state_text(), a))
        f.step(a)
    return pairs


def math_question():
    r = random
    kind = r.choice(["hits", "taken", "blast", "mobinfo", "mobinfo"])
    if kind == "mobinfo":
        m = r.choice(list(S.MOBS))
        return f"mobinfo {m}", f"# {S.MOBS[m]['info']}"
    if kind == "hits":
        w, m = r.choice(list(S.WEAPONS)), r.choice(list(S.MOBS))
        crit = r.random() < 0.3
        q = f"math hits {w} {m}" + (" crit" if crit else "")
        return q, f"# {S.hits_to_kill(w, m, crit)}"
    if kind == "taken":
        d, a = r.randint(1, 20), r.choice(list(S.ARMOR))
        return f"math taken {d} armor {a}", f"# {S.armor_cut(d, S.ARMOR[a]):.1f}"
    dist, a = r.randint(0, 6), r.choice(list(S.ARMOR))
    blast = S.armor_cut(S.MOBS["creeper"]["dmg"] * max(0.0, 1 - dist / 6), S.ARMOR[a])
    return f"math blast {dist} armor {a}", f"# {blast:.1f}"


_pool = []


def _next():
    while not _pool:      # some fights are over before they start (e.g. only a calm enderman)
        if random.random() < 0.15:
            _pool.extend(math_question() for _ in range(20))
        else:
            _pool.extend(episode())
        random.shuffle(_pool)
    return _pool.pop()


def random_request():
    req, out = _next()
    _answers[req] = out
    return req


_answers = {}


def reference(req):
    """Recompute the right answer. Fight states can't be rebuilt from text, so they're cached."""
    if req.startswith("mobinfo"):
        return f"# {S.MOBS[req.split()[1]]['info']}"
    if req.startswith("math"):
        p = req.split()
        if p[1] == "hits":
            return f"# {S.hits_to_kill(p[2], p[3], len(p) > 4)}"
        if p[1] == "taken":
            return f"# {S.armor_cut(int(p[2]), S.ARMOR[p[4]]):.1f}"
        dist = int(p[2])
        return f"# {S.armor_cut(S.MOBS['creeper']['dmg'] * max(0.0, 1 - dist / 6), S.ARMOR[p[4]]):.1f}"
    return _answers[req]


def sample(corrections, correction_rate=0.25):
    if corrections and random.random() < correction_rate:
        c = random.choice(corrections)
        return c["req"], c["out"]
    req, out = _next()
    _answers[req] = out
    if len(_answers) > 200000:
        _answers.clear()
    return req, out


def load_corrections():
    if not os.path.exists(CORRECTIONS_PATH):
        return []
    with open(CORRECTIONS_PATH, encoding="utf-8") as f:
        return [json.loads(l) for l in f if l.strip()]


def save_correction(req, action):
    with open(CORRECTIONS_PATH, "a", encoding="utf-8") as f:
        f.write(json.dumps({"req": req, "out": action}) + "\n")
