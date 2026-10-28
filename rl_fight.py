"""Reinforcement learning for the Fight model, in the combat simulator.

Rewards per fight:
    won       1.0 + up to 0.5 for health left (a clean win beats a scrappy one)
    escaped   0.25 + a little for health left (walking away from a fight you'd lose is smart)
    died     -1.0
    stalemate -0.2
Scored on a fixed set of 400 fights so progress is measured fairly. Saves only on a new
best, and rolls back to the best version if it starts getting worse.

    python rl_fight.py --updates 300
"""

import argparse
import os
import random
import time

import torch
import torch.nn.functional as F

import fight_data as D
import gentle
import fight_sim as S
from model import HERE, TinyGPT
from rl_planner import seq_logprobs
from train import make_batch

PATH = os.path.join(HERE, "fight.pt")
LOG = os.path.join(HERE, "rl_fight_log.txt")
GENERAL = ["retreat", "flee", "strafe", "shield", "eat", "hide", "unhide", "wait"]


def candidates(text):
    """Every move that makes sense to consider: general moves + each verb on each mob present."""
    kinds = {part.split()[0] for part in text.split("|")[2:] if part.strip()}
    return GENERAL + [f"{v} {k}" for k in sorted(kinds)
                      for v in ("attack", "combo", "crit", "shoot", "approach")]


def reward(f):
    if f.won():
        return 1.0 + 0.5 * f.hp / 20 - 0.005 * f.time
    if f.hp <= 0:
        return -1.0
    if f.survived():
        if f.scenario in ("horde", "duel"):
            return -0.3                   # exam fights: running away doesn't count
        return 0.25 + 0.2 * f.hp / 20     # ran or hid until they gave up
    return -0.2


@torch.no_grad()
def choose(model, texts, greedy):
    opts = [candidates(t) for t in texts]
    prompts = [t for t, o in zip(texts, opts) for _ in o]
    answers = [a for o in opts for a in o]
    scores = torch.cat([seq_logprobs(model, prompts[i:i + 240], answers[i:i + 240])
                        for i in range(0, len(prompts), 240)])
    picks, i = [], 0
    for o in opts:
        s = scores[i:i + len(o)]
        i += len(o)
        k = s.argmax().item() if greedy else torch.multinomial(F.softmax(s, 0), 1).item()
        picks.append(o[k])
    return picks


FOCUS = {"duel": lambda s: dict(scenario="duel"),
         "horde": lambda s: dict(scenario="horde", n_mobs=(3, 5)[s % 2])}


def scenario(s, focus):
    """With a focus, 60% of fights are that kind; the rest stay the normal mix."""
    if focus and s % 10 < 6:
        return FOCUS[focus](s)
    return D.scenario_for(s)


def play(model, seeds, greedy=False, max_steps=160, focus=None):
    fights = [S.Fight(random.Random(s), **scenario(s, focus)) for s in seeds]
    trail = []
    for _ in range(max_steps):
        live = [i for i, f in enumerate(fights) if not f.over()]
        if not live:
            break
        texts = [fights[i].state_text() for i in live]
        for i, t, a in zip(live, texts, choose(model, texts, greedy)):
            trail.append((t, a, i))
            fights[i].step(a)
    return [reward(f) for f in fights], fights, trail


def evaluate(model, focus=None):
    """Score on 400 fixed mixed fights; with a focus, half the score is 200 fixed focus fights,
    so progress on the weak spot counts but forgetting everything else still costs."""
    model.eval()
    rewards, fights = [], []
    for k in range(0, 400, 100):
        r, f, _ = play(model, range(10000 + k, 10100 + k), greedy=True)
        rewards += r
        fights += f
    score = sum(rewards) / len(rewards)
    won = sum(f.won() for f in fights)
    died = sum(f.hp <= 0 for f in fights)
    if focus:
        fr, ff = [], []
        for k in range(0, 200, 100):
            seeds = range(20000 + k, 20100 + k)
            fights2 = [S.Fight(random.Random(s), **FOCUS[focus](s)) for s in seeds]
            r, f, _ = play_fights(model, fights2)
            fr += r
            ff += f
        score = 0.5 * score + 0.5 * sum(fr) / len(fr)
        won = sum(f.won() for f in ff)       # report the focus wins out of 200
        died = sum(f.hp <= 0 for f in ff)
    return score, won, died


def play_fights(model, fights, max_steps=160):
    for _ in range(max_steps):
        live = [f for f in fights if not f.over()]
        if not live:
            break
        for f, a in zip(live, choose(model, [f.state_text() for f in live], True)):
            f.step(a)
    return [reward(f) for f in fights], fights, []


def log(msg):
    print(msg, flush=True)
    with open(LOG, "a", encoding="utf-8") as f:
        f.write(msg + "\n")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--updates", type=int, default=300)
    ap.add_argument("--games", type=int, default=32)
    ap.add_argument("--focus", choices=list(FOCUS), default=None,
                    help="spend most practice on one kind of fight (the one failing its exam)")
    args = ap.parse_args()

    gentle.setup()
    ck = torch.load(PATH, map_location="cuda")
    model = TinyGPT(**ck["config"]).cuda()
    model.load_state_dict(ck["model"])
    opt = torch.optim.AdamW(model.parameters(), lr=1e-5, weight_decay=0.0)
    best_state = {k: v.clone() for k, v in model.state_dict().items()}
    corrections = D.load_corrections()

    out_of = 200 if args.focus else 400
    what = f"{args.focus} " if args.focus else ""
    best, won, died = evaluate(model, args.focus)
    log(f"RL start{' (focus: ' + args.focus + ')' if args.focus else ''}: score {best:.3f}  "
        f"{what}won {won}/{out_of}  died {died}/{out_of}")
    t0 = time.time()
    for u in range(1, args.updates + 1):
        t_up = time.time()
        model.eval()
        rewards, _, trail = play(model, [random.randrange(10 ** 9) for _ in range(args.games)],
                                 focus=args.focus)
        base = sum(rewards) / len(rewards)
        adv = [max(-0.5, min(0.5, r - base)) for r in rewards]
        model.train()
        steps = [(t, a, adv[i]) for t, a, i in trail if abs(adv[i]) > 1e-6]
        loss = torch.zeros((), device="cuda")
        if steps:
            texts, acts, w = zip(*steps)
            w = torch.tensor(w, device="cuda")
            for i in range(0, len(texts), 256):
                lp = seq_logprobs(model, texts[i:i + 256], acts[i:i + 256], grad=True)
                loss = loss - (w[i:i + 256] * lp).sum() / len(texts)
        x, y = make_batch(D, 64, corrections, ck["config"]["ctx"], "cuda")
        with torch.autocast("cuda", dtype=torch.bfloat16):
            logits = model(x).float()
        sup = F.cross_entropy(logits.view(-1, logits.size(-1)), y.view(-1), ignore_index=-100)
        opt.zero_grad(set_to_none=True)
        (loss + 0.5 * sup).backward()
        torch.nn.utils.clip_grad_norm_(model.parameters(), 1.0)
        opt.step()
        gentle.step(time.time() - t_up)

        if u % 10 == 0:
            log(f"update {u}/{args.updates}  avg reward {base:.3f}  {time.time() - t0:.0f}s")
        if u % 50 == 0 or u == args.updates:
            score, won, died = evaluate(model, args.focus)
            if score > best:
                best = score
                best_state = {k: v.clone() for k, v in model.state_dict().items()}
                torch.save({"config": ck["config"], "model": model.state_dict()}, PATH)
                log(f"  >> score {score:.3f}  {what}won {won}/{out_of}  died {died}/{out_of}  NEW BEST, saved fight.pt")
            elif score < best - 0.05:
                model.load_state_dict(best_state)
                opt = torch.optim.AdamW(model.parameters(), lr=1e-5, weight_decay=0.0)
                log(f"  >> score {score:.3f}  dropped too far, rolled back to best ({best:.3f})")
            else:
                log(f"  >> score {score:.3f}  {what}won {won}/{out_of}  died {died}/{out_of}  (best {best:.3f})")
    log(f"RL done. best score {best:.3f}")


if __name__ == "__main__":
    random.seed()
    main()
