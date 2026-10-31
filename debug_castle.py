"""Replay castle world 1000 until wood gets stuck, then show what the miner sees."""

import castle_exam as C
import planner_data as P
import world_sim as W

world = W.World(seed=1000)
agent = W.Agent(world, tier=0)
agent.inventory = {}
need = C.castle_blocks()["cobblestone"]
state = {"goal": {"kind": "build", "items": [(a, 1) for a in C.ARMOR] + [("cobblestone", need)]},
         "inv": agent.inventory, "hunger": 20}
for step in range(60):
    agent.tier = P.pick_tier(agent.inventory)
    action = P.fill_count(state, P.strip_count(P.teacher(state)))
    v = action.split()
    before = agent.inventory.get("oak_log", 0)
    t0 = agent.time
    if v[0] == "chop":
        agent.chop(before + int(v[-1]), log=lambda *_: None)
    if v[0] == "chop" and agent.inventory.get("oak_log", 0) <= before:
        print(f"step {step}: chop got nothing in {agent.time - t0:.1f}s")
        x, y, z = agent.pos
        print("stuck on:", action, "| pos", agent.pos, "surface", world.surface(x, z), "| logs seen:",
              len(agent.known(W.LOG)), "| logs left in world:", int((world.b == W.LOG).sum()),
              "| inv oak_log", agent.inventory.get("oak_log"))
        print("moves from here:", list(agent._moves(*agent.pos))[:6])
        break
    n = int(v[-1]) if v[-1].isdigit() else 1
    if v[0] == "chop":
        pass
    elif v[0] == "mine":
        b = {"cobblestone": W.STONE, "coal": W.COAL, "raw_iron": W.IRON}[v[1]]
        agent.find(b, agent.inventory.get(v[1], 0) + n, log=lambda *_: None)
    elif v[0] == "hunt":
        agent.inventory["raw_beef"] = agent.inventory.get("raw_beef", 0) + n
    else:
        P.apply(state, action)
    agent.inventory = state["inv"]
