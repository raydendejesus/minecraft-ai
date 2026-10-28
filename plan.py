"""Watch the Survival Planner play games in the survival simulator.

    python plan.py              play 1 game step by step, then score 200 games
    python plan.py --games 500

Every step the Planner picks the next move; the simulator carries it out. A game is
won when the Planner says build/done with the goal actually met. Illegal moves
(crafting without the ingredients, mining stone with no pickaxe) lose the game.
"""

import argparse
import os
import random

import planner_data as P
from model import Builder, HERE

PLANNER_PATH = os.path.join(HERE, "planner.pt")


def legal(state, action):
    """Would this move actually work in survival right now?"""
    inv, p = state["inv"], action.split()
    try:
        if p[0] == "eat":
            return inv.get(p[1], 0) > 0
        if p[0] in ("chop", "mine", "dig", "hunt"):
            item = "raw_beef" if p[0] == "hunt" else p[1]
            return item in P.GATHER and P.pick_tier(inv) >= P.GATHER[item][1] and int(p[2]) > 0
        if p[0] == "craft":
            out, ings, table = P.CRAFT[p[1]]
            times = -(-int(p[2]) // out)
            return ((not table or inv.get("crafting_table", 0) > 0) and
                    all(inv.get(i, 0) >= c * times for i, c in ings.items()))
        if p[0] == "smelt":
            n = int(p[2])
            fuel = inv.get("coal", 0) >= -(-n // 8) or inv.get("oak_planks", 0) >= -(-n * 2 // 3)
            return inv.get("furnace", 0) > 0 and inv.get(P.SMELT[p[1]], 0) >= n and fuel
    except (KeyError, IndexError, ValueError):
        return False
    return False


def goal_met(state):
    return all(state["inv"].get(i, 0) >= n for i, n in state["goal"]["items"])


def play(planner, state, verbose=False, max_steps=40):
    for _ in range(max_steps):
        text = P.state_text(state)
        choice = planner.build(text)
        action = P.fill_count(state, choice)
        if verbose:
            print(f"  {text}\n     planner: {choice}   ->  {action}")
        if action in ("build", "done"):
            return goal_met(state)
        if not legal(state, action):
            if verbose:
                print("     !! that move isn't possible right now")
            return False
        P.apply(state, action)
    return False


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--games", type=int, default=200)
    args = ap.parse_args()
    planner = Builder(PLANNER_PATH)

    print("Example game:")
    print("  won" if play(planner, P.random_state(), verbose=True) else "  lost")
    wins = sum(play(planner, P.random_state()) for _ in range(args.games))
    print(f"\nPlanner won {wins}/{args.games} survival games ({wins / args.games:.0%})")


if __name__ == "__main__":
    random.seed()
    main()
