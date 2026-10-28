"""Reinforcement learning for the Survival Planner.

The Planner plays batches of survival games in the simulator. At every step it picks a
move by sampling from its own preferences (so it explores), the calculator fills in the
count, and the game goes on. Each game earns a reward:

    win:   1.0 minus 0.02 per step   (faster wins are better)
    loss:  0                          (illegal move, or ran out of steps)

Moves from games that did better than the batch average are reinforced, worse ones are
discouraged (REINFORCE with a baseline). A bit of normal teacher training is mixed in so
it doesn't forget the basics while it experiments. The model is only saved when its
greedy win rate actually improves.

    python rl_planner.py --updates 300
"""

import argparse
import os
import random
import time

import torch
import torch.nn.functional as F

import gentle
import planner_data as P
from data import encode, fmt
from model import HERE, TinyGPT
from plan import goal_met, legal
from train import make_batch

PATH = os.path.join(HERE, "planner.pt")
LOG = os.path.join(HERE, "rl_log.txt")

CHOICES = (["build", "done"] + [f"eat {f}" for f in P.FOODS]
           + ["chop oak_log", "dig sand", "hunt cow"]
           + [f"mine {i}" for i in ("cobblestone", "coal", "raw_iron", "diamond")]
           + [f"craft {i}" for i in P.CRAFT] + [f"smelt {i}" for i in P.SMELT])


def seq_logprobs(model, prompts, answers, grad=False):
    """Sum of log-probs the model gives each answer after its prompt (one batch)."""
    seqs, starts = [], []
    for p, a in zip(prompts, answers):
        pre = encode(fmt(p))
        seqs.append(encode(fmt(p, a)))
        starts.append(len(pre) - 1)
    T = max(len(s) for s in seqs) - 1
    dev = next(model.parameters()).device
    x = torch.zeros(len(seqs), T, dtype=torch.long)
    y = torch.full((len(seqs), T), -100, dtype=torch.long)
    for i, s in enumerate(seqs):
        s = torch.tensor(s)
        x[i, :len(s) - 1] = s[:-1]
        y[i, starts[i]:len(s) - 1] = s[starts[i] + 1:]
    x, y = x.to(dev), y.to(dev)
    with torch.set_grad_enabled(grad), torch.autocast("cuda", dtype=torch.bfloat16):
        logits = model(x).float()
    lp = -F.cross_entropy(logits.transpose(1, 2), y, ignore_index=-100, reduction="none")
    return lp.sum(1)


@torch.no_grad()
def choose(model, texts, greedy=False, temp=1.0):
    """Score every possible move for each state; sample one (or take the best)."""
    prompts = [t for t in texts for _ in CHOICES]
    answers = CHOICES * len(texts)
    # in chunks, so it fits under the GPU memory cap in gentle.json
    scores = torch.cat([seq_logprobs(model, prompts[i:i + 240], answers[i:i + 240])
                        for i in range(0, len(prompts), 240)]).view(len(texts), len(CHOICES))
    if greedy:
        idx = scores.argmax(1)
    else:
        idx = torch.multinomial(F.softmax(scores / temp, 1), 1).squeeze(1)
    return [CHOICES[i] for i in idx.tolist()]


def play_batch(model, n, greedy=False, max_steps=40):
    """Run n games side by side. Returns rewards and every (state, move, game id)."""
    games = [P.random_state() for _ in range(n)]
    alive, steps = list(range(n)), [0] * n
    reward = [0.0] * n
    trail = []
    for _ in range(max_steps):
        if not alive:
            break
        texts = [P.state_text(games[g]) for g in alive]
        moves = choose(model, texts, greedy)
        still = []
        for g, text, move in zip(alive, texts, moves):
            trail.append((text, move, g))
            steps[g] += 1
            state = games[g]
            if move in ("build", "done"):
                reward[g] = (1.0 - 0.02 * steps[g]) if goal_met(state) else 0.0
                continue
            action = P.fill_count(state, move)
            if not legal(state, action):
                continue          # illegal move: game over, reward 0
            P.apply(state, action)
            still.append(g)
        alive = still
    return reward, trail


def win_rate(model, games=200):
    """Win rate on the SAME set of games every time (fixed random seed), so a model is only
    saved when it's genuinely better, not because it got an easy batch of test games."""
    model.eval()
    saved = random.getstate()
    random.seed(777)
    wins = 0
    for _ in range(games // 50):
        r, _ = play_batch(model, 50, greedy=True)
        wins += sum(x > 0 for x in r)
    random.setstate(saved)
    return wins / games


def log(msg):
    print(msg, flush=True)
    with open(LOG, "a", encoding="utf-8") as f:
        f.write(msg + "\n")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--updates", type=int, default=300)
    ap.add_argument("--games", type=int, default=32)
    args = ap.parse_args()

    gentle.setup()
    ck = torch.load(PATH, map_location="cuda")
    model = TinyGPT(**ck["config"]).cuda()
    model.load_state_dict(ck["model"])
    opt = torch.optim.AdamW(model.parameters(), lr=1e-5, weight_decay=0.0)
    best_state = {k: v.clone() for k, v in model.state_dict().items()}
    corrections = P.load_corrections()

    best = win_rate(model, 400)
    log(f"RL start: greedy win rate {best:.1%}")
    t0 = time.time()
    for u in range(1, args.updates + 1):
        t_up = time.time()
        model.eval()
        reward, trail = play_batch(model, args.games)
        base = sum(reward) / len(reward)
        # capped so one lucky or unlucky game can't swing the whole model
        adv = {g: max(-0.5, min(0.5, r - base)) for g, r in enumerate(reward)}
        model.train()
        # policy gradient on the moves actually taken
        texts, moves, weights = zip(*[(t, m, adv[g]) for t, m, g in trail if abs(adv[g]) > 1e-6] or [("", "", 0)])
        loss = torch.zeros((), device="cuda")
        if weights[0] or len(weights) > 1:
            w = torch.tensor(weights, device="cuda")
            for i in range(0, len(texts), 256):
                lp = seq_logprobs(model, texts[i:i + 256], moves[i:i + 256], grad=True)
                loss = loss - (w[i:i + 256] * lp).sum() / len(texts)
        # keep the teacher's lessons (and your corrections) in mind
        x, y = make_batch(P, 64, corrections, ck["config"]["ctx"], "cuda")
        with torch.autocast("cuda", dtype=torch.bfloat16):
            logits = model(x).float()
        sup = F.cross_entropy(logits.view(-1, logits.size(-1)), y.view(-1), ignore_index=-100)
        total = loss + 0.5 * sup
        opt.zero_grad(set_to_none=True)
        total.backward()
        torch.nn.utils.clip_grad_norm_(model.parameters(), 1.0)
        opt.step()
        gentle.step(time.time() - t_up)

        if u % 10 == 0:
            log(f"update {u}/{args.updates}  avg reward {base:.3f}  wins {sum(r > 0 for r in reward)}/{len(reward)}  {time.time() - t0:.0f}s")
        if u % 50 == 0 or u == args.updates:
            wr = win_rate(model, 400)
            if wr > best:
                best = wr
                best_state = {k: v.clone() for k, v in model.state_dict().items()}
                torch.save({"config": ck["config"], "model": model.state_dict()}, PATH)
                log(f"  >> greedy win rate {wr:.1%}  NEW BEST, saved planner.pt")
            elif wr < best - 0.05:
                # RL went off the rails: roll back to the best version and keep practicing
                model.load_state_dict(best_state)
                opt = torch.optim.AdamW(model.parameters(), lr=1e-5, weight_decay=0.0)
                log(f"  >> greedy win rate {wr:.1%}  dropped too far, rolled back to best ({best:.1%})")
            else:
                log(f"  >> greedy win rate {wr:.1%}  (best {best:.1%}, not saved)")
    log(f"RL done. best greedy win rate {best:.1%}")


if __name__ == "__main__":
    random.seed()
    main()
