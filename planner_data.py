"""Training data for the Survival Planner.

The Planner decides the next move in survival, it doesn't move the body (the
in-game NPC script does that). It reads one state line and answers one action:

    goal build cobblestone 60 oak_planks 40 | have oak_log 2 wooden_pickaxe 1 | hunger 15
    > mine cobblestone 60

Actions:  chop oak_log <n> | mine <cobblestone|coal|raw_iron|diamond> <n> | dig sand <n>
          hunt cow <n> | craft <item> <n> | smelt <item> <n> | eat <food>
          build (all materials gathered) | done (a "get" goal is finished)

A small survival simulator with real recipes plays as the teacher: it plays out
random episodes and records what the right next move was at every step.
"""

import json
import math
import os
import random

HERE = os.path.dirname(os.path.abspath(__file__))
CORRECTIONS_PATH = os.path.join(HERE, "planner_corrections.jsonl")

# item: (output count, {ingredient: count}, needs crafting table)
CRAFT = {
    "oak_planks": (4, {"oak_log": 1}, False),
    "stick": (4, {"oak_planks": 2}, False),
    "crafting_table": (1, {"oak_planks": 4}, False),
    "wooden_pickaxe": (1, {"oak_planks": 3, "stick": 2}, True),
    "stone_pickaxe": (1, {"cobblestone": 3, "stick": 2}, True),
    "iron_pickaxe": (1, {"iron_ingot": 3, "stick": 2}, True),
    "diamond_pickaxe": (1, {"diamond": 3, "stick": 2}, True),
    "wooden_sword": (1, {"oak_planks": 2, "stick": 1}, True),
    "stone_sword": (1, {"cobblestone": 2, "stick": 1}, True),
    "iron_sword": (1, {"iron_ingot": 2, "stick": 1}, True),
    "furnace": (1, {"cobblestone": 8}, True),
    "chest": (1, {"oak_planks": 8}, True),
    "torch": (4, {"coal": 1, "stick": 1}, False),
    "bucket": (1, {"iron_ingot": 3}, True),
    "shield": (1, {"oak_planks": 6, "iron_ingot": 1}, True),
}
SMELT = {"iron_ingot": "raw_iron", "cooked_beef": "raw_beef", "glass": "sand"}
# gathered item: (verb, tool tier needed: 0 hand, 1 wood, 2 stone, 3 iron)
GATHER = {
    "oak_log": ("chop", 0), "sand": ("dig", 0), "raw_beef": ("hunt", 0),
    "cobblestone": ("mine", 1), "coal": ("mine", 1), "raw_iron": ("mine", 2), "diamond": ("mine", 3),
}
PICKS = ["wooden_pickaxe", "stone_pickaxe", "iron_pickaxe", "diamond_pickaxe"]
FOODS = {"cooked_beef": 8, "bread": 5, "apple": 4}

ITEM_ORDER = (list(GATHER) + list(SMELT) + list(CRAFT) + ["bread", "apple"])
GOAL_ITEMS = ["oak_planks", "cobblestone", "glass", "oak_log", "stick", "torch", "furnace",
              "chest", "iron_ingot", "stone_pickaxe", "iron_pickaxe", "diamond_pickaxe",
              "iron_sword", "stone_sword", "bucket", "shield", "coal", "cooked_beef"]


def pick_tier(inv):
    return max([i + 1 for i, p in enumerate(PICKS) if inv.get(p, 0) > 0], default=0)


def first_step(item, n, inv, depth=0):
    """Teacher: the first action toward having n of item, or None if we already do."""
    have = inv.get(item, 0)
    if have >= n or depth > 12:
        return None
    missing = n - have
    if item in GATHER:
        verb, tier = GATHER[item]
        if pick_tier(inv) < tier:
            return first_step(PICKS[tier - 1], 1, inv, depth + 1)
        if verb == "hunt":
            return f"hunt cow {missing}"
        return f"{verb} {item} {missing}"
    if item in SMELT:
        src = SMELT[item]
        fuel_coal = math.ceil(missing / 8)
        for need, cnt in (("furnace", 1), (src, missing)):
            step = first_step(need, cnt, inv, depth + 1)
            if step:
                return step
        if inv.get("coal", 0) < fuel_coal and inv.get("oak_planks", 0) < math.ceil(missing / 1.5):
            return first_step("oak_planks", math.ceil(missing / 1.5), inv, depth + 1)
        return f"smelt {item} {missing}"
    if item in CRAFT:
        out, ings, table = CRAFT[item]
        times = math.ceil(missing / out)
        if table:
            step = first_step("crafting_table", 1, inv, depth + 1)
            if step:
                return step
        for ing, cnt in ings.items():
            step = first_step(ing, cnt * times, inv, depth + 1)
            if step:
                return step
        return f"craft {item} {missing}"
    return None


def teacher(state):
    goal, inv, hunger = state["goal"], state["inv"], state["hunger"]
    if hunger <= 8:
        food = next((f for f in FOODS if inv.get(f, 0) > 0), None)
        if food:
            return f"eat {food}"
        step = first_step("cooked_beef", 2, inv)
        if step:
            return step
    for item, n in goal["items"]:
        step = first_step(item, n, inv)
        if step:
            return step
    return "build" if goal["kind"] == "build" else "done"


def apply(state, action):
    """Simulate doing the action, so the next step sees the new inventory."""
    inv = state["inv"]
    p = action.split()
    state["hunger"] = max(0, state["hunger"] - random.randint(0, 2))
    if p[0] == "eat":
        inv[p[1]] -= 1
        state["hunger"] = min(20, state["hunger"] + FOODS[p[1]])
    elif p[0] in ("chop", "mine", "dig"):
        inv[p[1]] = inv.get(p[1], 0) + int(p[2])
    elif p[0] == "hunt":
        inv["raw_beef"] = inv.get("raw_beef", 0) + int(p[2])
    elif p[0] == "craft":
        item, want = p[1], int(p[2])
        out, ings, _ = CRAFT[item]
        times = math.ceil(want / out)
        for ing, cnt in ings.items():
            inv[ing] -= cnt * times
        inv[item] = inv.get(item, 0) + out * times
    elif p[0] == "smelt":
        item, n = p[1], int(p[2])
        inv[SMELT[item]] -= n
        coal = math.ceil(n / 8)
        if inv.get("coal", 0) >= coal:
            inv["coal"] -= coal
        else:
            inv["oak_planks"] -= math.ceil(n / 1.5)
        inv[item] = inv.get(item, 0) + n
    for k in [k for k, v in inv.items() if v <= 0]:
        del inv[k]


def state_text(state):
    g = state["goal"]
    goal = " ".join(f"{i} {n}" for i, n in g["items"])
    have = " ".join(f"{i} {state['inv'][i]}" for i in ITEM_ORDER if state["inv"].get(i, 0) > 0)
    return f"goal {g['kind']} {goal} | have {have or 'nothing'} | hunger {state['hunger']}"


def random_state():
    kind = random.choice(["build", "get"])
    if kind == "build":
        mats = random.sample(["oak_planks", "cobblestone", "glass", "oak_log", "torch"], random.randint(1, 3))
        items = [(m, random.randint(4, 64) if m != "torch" else random.randint(1, 8)) for m in mats]
    else:
        items = [(i, random.randint(1, 3) if i in CRAFT and CRAFT[i][0] == 1 else random.randint(1, 16))
                 for i in random.sample(GOAL_ITEMS, random.randint(1, 2))]
    inv = {}
    for i in random.sample(ITEM_ORDER, random.randint(0, 6)):
        inv[i] = 1 if i in PICKS or i in ("crafting_table", "furnace") else random.randint(1, 20)
    return {"goal": {"kind": kind, "items": items}, "inv": inv, "hunger": random.randint(0, 20)}


def episode(max_steps=40):
    """Play one game with the teacher, returning every (state, action) along the way."""
    state, pairs = random_state(), []
    for _ in range(max_steps):
        action = teacher(state)
        pairs.append((state_text(state), action))
        if action in ("build", "done"):
            break
        apply(state, action)
    return pairs


_pool = []


def random_request():
    if not _pool:
        _pool.extend(episode())
        random.shuffle(_pool)
    return _pool.pop()[0]


def reference(req):
    """Re-derive the teacher's choice from a state line (used to check accuracy)."""
    return strip_count(teacher(parse_state(req)))


def strip_count(action):
    """The model only learns the choice ('mine raw_iron'); counts come from fill_count()."""
    p = action.split()
    return " ".join(p[:-1]) if p[-1].isdigit() else action


def parse_state(text):
    left, have, hunger = [s.strip() for s in text.split("|")]
    g = left.split()[1:]
    goal = {"kind": g[0], "items": [(g[i], int(g[i + 1])) for i in range(1, len(g), 2)]}
    h = have.split()[1:]
    inv = {} if h == ["nothing"] else {h[i]: int(h[i + 1]) for i in range(0, len(h), 2)}
    return {"goal": goal, "inv": inv, "hunger": int(hunger.split()[1])}


def fill_count(state, choice):
    """The calculator: how many to gather/craft for the chosen move, from the recipe tree."""
    full = teacher(state)
    if strip_count(full) == choice:
        return full
    if choice in ("build", "done") or choice.startswith("eat"):
        return choice
    item = choice.split()[-1]
    if choice.startswith("hunt"):
        return "hunt cow 3"
    if item in CRAFT:
        return f"{choice} {CRAFT[item][0]}"
    return f"{choice} {8 if choice.startswith(('mine', 'dig', 'chop')) else 1}"


def load_corrections():
    if not os.path.exists(CORRECTIONS_PATH):
        return []
    with open(CORRECTIONS_PATH, encoding="utf-8") as f:
        return [json.loads(l) for l in f if l.strip()]


def save_correction(req, action):
    with open(CORRECTIONS_PATH, "a", encoding="utf-8") as f:
        f.write(json.dumps({"req": req, "out": action}) + "\n")


def sample(corrections, correction_rate=0.25):
    if corrections and random.random() < correction_rate:
        c = random.choice(corrections)
        return c["req"], strip_count(c["out"])
    if not _pool:
        _pool.extend(episode())
        random.shuffle(_pool)
    state, action = _pool.pop()
    return state, strip_count(action)
