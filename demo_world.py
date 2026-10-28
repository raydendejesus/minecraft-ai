"""Drop the agent on the surface of a fresh world and send it after diamonds.

    python demo_world.py            one world, step by step
    python demo_world.py --runs 20  score it over many worlds
"""

import argparse
import random

import world_sim as W


def run(seed, verbose=True):
    world = W.World(seed=seed)
    agent = W.Agent(world, tier=3)      # iron pickaxe, needed for diamonds
    log = print if verbose else (lambda *_: None)
    log(f"world {seed}: start on the surface at {agent.pos}")
    ok = agent.find(W.DIAMOND, 3, log=log)
    log(f"  {'GOT' if ok else 'FAILED to get'} 3 diamonds: {agent.time / 60:.1f} min, walked {agent.walked} blocks, "
        f"mined {agent.mined} blocks, ended at y={agent.pos[1]}")
    log(f"  inventory: {dict(sorted(agent.inventory.items(), key=lambda kv: -kv[1]))}")
    return ok, agent.time


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--runs", type=int, default=1)
    args = ap.parse_args()
    if args.runs == 1:
        run(random.randrange(10 ** 6))
    else:
        results = [run(s, verbose=False) for s in range(args.runs)]
        wins = [t for ok, t in results if ok]
        print(f"got 3 diamonds in {len(wins)}/{args.runs} worlds, "
              f"avg {sum(wins) / max(1, len(wins)) / 60:.1f} min of game time")
