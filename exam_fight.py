"""The fight final exam.

    python exam_fight.py              the trained Fight model takes the exam
    python exam_fight.py --teacher    the hand-written teacher takes it (for comparison)

Tests (each 200 fights, same fights every time so results are comparable):
    horde of 2 mobs at once   pass at 90% wins
    horde of 3 mobs at once   pass at 85% wins
    horde of 5 mobs at once   pass at 75% wins
    1v1 vs the PvP bot        pass at 75% wins   (hard-coded expert that W-taps, same gear)
"""

import argparse
import random

import fight_data as D
import fight_sim as S

# pass marks sit above what the hand-written teacher manages (100/97/63/60%), so the
# trained model has to genuinely out-play its teacher to pass
TESTS = [("horde of 2", "horde", 2, 0.90), ("horde of 3", "horde", 3, 0.85),
         ("horde of 5", "horde", 5, 0.75), ("1v1 vs PvP bot", "duel", 1, 0.75)]
N = 200


def run_test(policy, scenario, n, seed0):
    fights = [S.Fight(random.Random(seed0 + i), n_mobs=n, scenario=scenario) for i in range(N)]
    for _ in range(240):
        live = [f for f in fights if not f.over()]
        if not live:
            break
        for f, a in zip(live, policy([f for f in live])):
            f.step(a)
    won = sum(f.won() for f in fights)
    died = sum(f.hp <= 0 for f in fights)
    return won, died


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--teacher", action="store_true")
    args = ap.parse_args()
    if args.teacher:
        policy, who = (lambda fs: [D.teacher(f) for f in fs]), "teacher"
    else:
        import torch
        import rl_fight
        from model import TinyGPT
        ck = torch.load("fight.pt", map_location="cuda")
        model = TinyGPT(**ck["config"]).cuda().eval()
        model.load_state_dict(ck["model"])
        policy, who = (lambda fs: rl_fight.choose(model, [f.state_text() for f in fs], greedy=True)), "Fight model"

    print(f"Fight exam, taken by the {who}:")
    passed = 0
    for i, (name, scenario, n, need) in enumerate(TESTS):
        won, died = run_test(policy, scenario, n, 50000 + i * 1000)
        ok = won / N >= need
        passed += ok
        print(f"  {name:16s} won {won:3d}/{N} ({won / N:.0%}, need {need:.0%})  died {died:3d}  "
              f"{'PASS' if ok else 'not yet'}")
    print(f"{passed}/{len(TESTS)} tests passed")
    return passed == len(TESTS)


if __name__ == "__main__":
    main()
