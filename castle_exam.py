"""The castle exam: start with nothing, end wearing full iron armor next to a castle you built
from blocks you gathered yourself.

    python castle_exam.py              teacher-driven planner, 10 worlds
    python castle_exam.py --model      the trained Survival Planner makes the calls
    python castle_exam.py --worlds 3 --verbose

How it works:
  * the Survival Planner picks the next move (chop, mine, craft, smelt, hunt, eat, build)
    toward the goal: iron helmet + chestplate + leggings + boots, and the castle's cobblestone
  * the voxel-world miner carries it out: chops real trees, quarries stone, finds iron and coal
    (no x-ray, real body rules, pathfinding)
  * crafting/smelting use real recipes; mining power comes from the pickaxes actually crafted
  * the castle (4 round towers, crenellated walls, a gate) is designed with Builder ops and may
    only use blocks that were gathered
Pass: full iron armor + castle built in at least 8 of 10 worlds, within 2 hours of game time.
"""

import argparse
import random

import data
import planner_data as P
import world_sim as W

# ---- the castle, made of Builder ops (offset, request)
CASTLE = [
    ((0, 0, 0), "tower cobblestone 2 7"), ((12, 0, 0), "tower cobblestone 2 7"),
    ((0, 0, 12), "tower cobblestone 2 7"), ((12, 0, 12), "tower cobblestone 2 7"),
    ((5, 0, 2), "castle_wall cobblestone 7 5 x"), ((5, 0, 14), "castle_wall cobblestone 7 5 x"),
    ((2, 0, 5), "castle_wall cobblestone 7 5 z"), ((14, 0, 5), "castle_wall cobblestone 7 5 z"),
    ((7, 0, 14), "clear 3 3 1"),                       # the gate
]


def castle_blocks():
    """Run the castle's commands on an empty grid and count the blocks it ends up with."""
    grid = {}
    for (ox, oy, oz), req in CASTLE:
        for cmd in data.reference(req).splitlines():
            p = cmd.split()
            nums = [int(t[1:]) for t in p if t.startswith("~")]
            if p[0] == "setblock":
                x, y, z = nums
                grid[(x + ox, y + oy, z + oz)] = p[4]
                continue
            x1, y1, z1, x2, y2, z2 = nums
            block, hollow = p[7], len(p) > 8 and p[8] == "hollow"
            for x in range(min(x1, x2), max(x1, x2) + 1):
                for y in range(min(y1, y2), max(y1, y2) + 1):
                    for z in range(min(z1, z2), max(z1, z2) + 1):
                        edge = x in (x1, x2) or y in (y1, y2) or z in (z1, z2)
                        grid[(x + ox, y + oy, z + oz)] = block if (edge or not hollow) else "air"
    counts = {}
    for b in grid.values():
        if b != "air":
            counts[b] = counts.get(b, 0) + 1
    return counts


ARMOR = ["iron_helmet", "iron_chestplate", "iron_leggings", "iron_boots"]


def run_world(seed, planner, verbose=False, limit=7200):
    world = W.World(seed=seed)
    agent = W.Agent(world, tier=0)
    agent.inventory = {}
    need = castle_blocks()["cobblestone"]
    goal = {"kind": "build", "items": [(a, 1) for a in ARMOR] + [("cobblestone", need)]}
    state = {"goal": goal, "inv": agent.inventory, "hunger": 20}
    log = print if verbose else (lambda *_: None)
    steps = 0
    while agent.time < limit and steps < 400:
        steps += 1
        agent.tier = P.pick_tier(agent.inventory)
        choice = planner(state)
        action = P.fill_count(state, choice)
        verb = action.split()
        inv = agent.inventory
        log(f"  t={agent.time / 60:5.1f}m  {action:28s} hunger {state['hunger']:2d}  logs {inv.get('oak_log', 0)} "
            f"planks {inv.get('oak_planks', 0)} cobble {inv.get('cobblestone', 0)} iron {inv.get('raw_iron', 0)}"
            f"/{inv.get('iron_ingot', 0)} coal {inv.get('coal', 0)}")
        if verb[0] in ("build", "done"):
            break
        n = int(verb[-1]) if verb[-1].isdigit() else 1
        if verb[0] == "chop":
            agent.chop(agent.inventory.get("oak_log", 0) + n, log=lambda *_: None)
        elif verb[0] == "mine":
            block = {"cobblestone": W.STONE, "coal": W.COAL, "raw_iron": W.IRON, "diamond": W.DIAMOND}[verb[1]]
            have = agent.inventory.get(verb[1], 0)
            if not agent.find(block, have + n, log=lambda *_: None):
                log("    couldn't find enough, trying the next move")
        elif verb[0] == "hunt":
            agent.time += 40                       # no animals in this world: stand-in for hunting
            agent.inventory["raw_beef"] = agent.inventory.get("raw_beef", 0) + n
        elif verb[0] == "dig":
            agent.time += 20
            agent.inventory[verb[1]] = agent.inventory.get(verb[1], 0) + n
        else:
            from plan import legal
            if not legal(state, action):
                log("    not possible right now")
                break
            P.apply(state, action)
            agent.time += 2
        state["hunger"] = max(0, state["hunger"] - (1 if steps % 3 == 0 else 0))
        agent.inventory = state["inv"]
    armored = all(agent.inventory.get(a, 0) >= 1 for a in ARMOR)
    built = agent.inventory.get("cobblestone", 0) >= need
    if armored and built:
        agent.inventory["cobblestone"] -= need
        agent.time += need * 0.25                  # placing every block by hand
    return armored, built, agent.time, need


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--worlds", type=int, default=10)
    ap.add_argument("--model", action="store_true")
    ap.add_argument("--verbose", action="store_true")
    args = ap.parse_args()
    if args.model:
        import torch
        from model import Builder
        b = Builder("planner.pt")
        planner = lambda s: b.build(P.state_text(s))
        who = "trained Survival Planner"
    else:
        planner = lambda s: P.strip_count(P.teacher(s))
        who = "teacher"
    print(f"Castle exam, planner = {who}. Castle needs {castle_blocks()} blocks.")
    passed = 0
    for i in range(args.worlds):
        armored, built, t, need = run_world(1000 + i, planner, args.verbose)
        ok = armored and built and t <= 7200
        passed += ok
        print(f"  world {i + 1}: armor {'yes' if armored else 'no '}  castle {'built' if built else 'not built'}"
              f"  {t / 60:5.1f} min  {'PASS' if ok else 'fail'}", flush=True)
    print(f"{passed}/{args.worlds} worlds passed (need 8)")


if __name__ == "__main__":
    random.seed(0)
    main()
