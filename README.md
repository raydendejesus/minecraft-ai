# Minecraft AI

Small AI models, trained from scratch on one RTX 3090, that play Minecraft Bedrock Edition:
they build, design redstone circuits, plan survival, mine, and fight. You talk to them through
a chat model, correct them when they're wrong, and they keep learning from those corrections.

> Built by Rayden De Jesus with Claude (Anthropic), October 2026.
> The full story of how it was built, including everything that broke along the way, is in
> [docs/JOURNEY.md](docs/JOURNEY.md). What's left to do is in [FINAL_EXAM.md](FINAL_EXAM.md).

## How it fits together

```
 you ──chat──▶ Dolphin (dolphin3, 8B, local via Ollama)
  ▲              │  understands what you want, plans, takes corrections
  │              ▼
  │      short request lines, e.g. "house cobblestone oak_planks spruce_planks 7 4 7 south"
  │              │
  │   ┌──────────┼──────────────┬───────────────────┐
  │   ▼          ▼              ▼                   ▼
  │ Builder   Redstone       Survival Planner    Fight model
  │ (build)   (circuits)     (what to do next)   (fight, kite, block, hide, flee)
  │   │          │              │                   │
  │   └──────────┴──── Bedrock commands / moves ────┘
  │                         │
  └──── your Bedrock server ◀┘    photos: qwen2.5vl only describes them for Dolphin
```

Dolphin is a pretrained general model. **Everything else is a tiny model (about 5 million
parameters, roughly 1/1600 the size of Dolphin) trained from nothing on this PC.** Each one is
a specialist that knows one job very well.

## The models and how well they do

| Model | Job | Trained by | Result |
|---|---|---|---|
| **Builder** | request line → Bedrock `/fill` and `/setblock` commands (houses, towers, castle walls, roofs, bridges, farms...) | a hand-written "teacher" that generates endless examples | **100%** exact-match on requests it has never seen |
| **Redstone** | logic gates, adders, latches, RAM, written in a compact parts language | designs that first passed on a real Bedrock server | **11 circuits pass** in the real game, up to a full adder and a byte of RAM |
| **Survival Planner** | reads goal + inventory + hunger, picks the next move (chop, mine, craft, smelt, hunt, eat, build) | teacher, then reinforcement learning (RL) in a survival simulator | **81%** of simulated survival games won (started at 25%) |
| **Fight model** | reads health, gear and nearby mobs, picks a move (attack, W-tap combo, shoot, shield, kite, eat, dig in and hide, flee) | teacher, then RL in a combat simulator | beats hordes of 2/3/5 mobs **100% / 93% / 76%**; **73%** vs a hard-coded PvP bot (teacher: 100/97/63/60%) |
| **Miner** | moves and mines through a voxel world with real body rules | A* pathfinding + mining strategy (not a trained model yet) | found diamonds in **20 of 20** worlds, about 11 min game time each |

## Pick your brains

Each trained model is a separate download on the
[Releases page](https://github.com/raydendejesus/minecraft-ai/releases), so you only download what
you want. Put the `.pt` files in the project folder next to the code.

| Brain | File | Size | Needs |
|---|---|---|---|
| Builder (buildings + redstone circuits) | `builder.pt` | ~19 MB | the code; Dolphin via Ollama if you want to chat instead of typing request lines |
| Survival Planner | `planner.pt` | ~19 MB | the code |
| Fight model | `fight.pt` | ~19 MB | the code |
| Brain (all of them in one, coming after the final exam) | `brain.pt` | ~56 MB | the code |

Every brain is about 5 million parameters and runs on any NVIDIA GPU, or slowly on CPU.

### Combinations: what each setup is good and bad at

| Setup | Good at | Weak at / missing |
|---|---|---|
| **Builder only** | The most complete piece today: chat "build me a castle wall" and it builds on a real Bedrock server. Houses, towers, roofs, bridges, farms, redstone gates/adders/RAM, undo, and learning from your fixes. Smallest download. | Builds instantly with commands (creative style). It doesn't gather resources, survive or fight. Chatting needs Dolphin (8B) on top. |
| **Planner only** | Survival decisions: what to gather, craft, smelt and eat next, toward any goal. 81% of simulated games won. Tiny and fast. | Decides only: it outputs moves like "mine raw_iron", it doesn't move a character itself yet. Tested in the simulator, not in a live world. |
| **Fight only** | Combat judgment against 28 mob types: when to fight, kite, block, combo, shoot, eat, hide or run. Beats hordes of 2/3/5 at 100/93/76%. | Decides only, like the Planner. Simulator-tested. The PvP duel exam isn't passed yet. |
| **Builder + Planner** | Plan what a build needs, then build it. The base for the "gather the materials, then build the castle" exam. | Nothing defends it, and the Planner still has no real-world body. |
| **Builder + Fight** | Builds, and knows how to handle mobs that show up while it works. | No survival planning: it can't work out gathering or crafting. |
| **Planner + Fight** | A full survival mind: gather, craft and eat, and switch to combat when attacked. The core of a survival bot. | Can't design buildings or circuits. Both decide only (no in-game body yet). |
| **All three** | Everything: build, plan and fight, each at its best quality. | Three downloads (~57 MB) and three models loaded. |
| **Brain** (when released) | All three skills in one model, one download, one file to load. | Slightly larger, and a merged model can be a little less sharp at each single job than the dedicated specialist; that's checked against the specialists before release. |

## How each part works

### The Builder
Dolphin writes short lines in a small request language (`tower stone_bricks 4 6`,
`windows oak_planks 10 4 x`, `redstone ram 8`, ...). The Builder reads one character at a time
and writes the commands. It learned from a teacher function that knows the right answer for any
request, generating fresh random examples every training step, so it learned the *rules*
instead of memorizing answers. Every block name and command shape was checked against a real
Bedrock server first (Bedrock spells some blocks its own way: `brick_block`, `hardened_clay`).

### Redstone and the Redstone Lab
`lab_server/` is a private copy of Bedrock Dedicated Server running a flat test world on its own
port, so testing never touches your real world. `lab.py` drives it through its console.
`test_lab.py` builds each circuit, flips its inputs, and reads the output lamps back with
`/testforblock`, checking the **whole truth table** (or, for memory, a step-by-step sequence).

Things the lab taught us that you'd get wrong on paper:
- a repeater's `cardinal_direction` is the side the signal comes *from*, and Bedrock's piston
  facing numbers are flipped compared to what you'd expect
- **a lamp powered by a repeater becomes a powered block** and feeds the wire next to it; our
  first RAM froze itself forever because of this
- RAM needs "hold time": switch write off *before* changing the data, like real chips

### The Survival Planner (+ calculator)
The Planner decides *what* to do ("mine raw_iron"), and a recipe calculator fills in *how many*.
Tiny models are bad at arithmetic, and splitting the job took full-game wins from 25% to 68%.

### Reinforcement learning
After learning from the teacher, the Planner and Fight models practice in simulators. During
practice they sometimes try other moves (exploring); games that go better than average make
those decisions stronger. **When actually playing they always use their best judgment, nothing
random.** Safeguards: rewards are capped, a model is only saved when its score on a fixed test
set improves, and it rolls back automatically if practice starts making it worse.

### The fight simulator
28 mobs with their real Bedrock attack styles: zombies rush, skeletons keep distance and shoot,
creepers fuse (1.5s, cancel at 7 blocks), phantoms swoop, slimes split, endermen dodge arrows,
the warden's sonic boom goes through shields and walls. Real numbers: Bedrock weapon damage, 4%
per armor point, no attack cooldown, crits, shields, golden apples, health regenerating only on
a full hunger bar. Skills it learned include kiting a swarm, W-tap combos, hit-and-run on
creepers, and digging into a wall with a pickaxe to recover health.

### The miner and voxel world
`world_sim.py` generates worlds with real ore heights, caves, lava pools and bedrock. The agent
knows its body: 1.8 blocks tall (2-block tunnels), step up 1, safe drop 3, never digs straight
down or next to lava/water, and has no x-ray: it only knows blocks it has actually seen. A*
pathfinding counts mining time as cost, so it digs through a hill when that's faster than going
around.

### Keeping the PC usable
- `gentle.py` + `gentle.json`: CPU priority, GPU memory cap, how hard the GPU works, and an
  optional pause while Minecraft is open, all changeable while training runs
- **temperature guard**: slows down from 82°C, pauses at 90°C until the GPU cools to 75°C,
  logs temperature to `gpu_temp_log.csv`
- `pipeline.py` runs queued training jobs one at a time, automatically
- `learner.py` retrains in the background when you've added corrections

## Running it

**You need:** Windows, an NVIDIA GPU, Python 3.12 with PyTorch (CUDA), [Ollama](https://ollama.com)
with `dolphin3` (and `qwen2.5vl:7b` for photos), and
[Bedrock Dedicated Server](https://www.minecraft.net/en-us/download/server/bedrock) (free from Mojang,
not included here because its license doesn't allow redistribution).

1. `python -m venv --system-site-packages venv` (reuses an existing PyTorch install), and
   download the brains you want from Releases into this folder (see "Pick your brains")
2. Point `bds_exe` / `bds_dir` in `config.json` at your Bedrock server (with `allow-cheats=true`)
3. `START.bat`, then open http://localhost:8840
4. Type your Minecraft name, start the server, join it, click **Build here**, and chat

In game you can also type `!mc build a stone tower`, `!mc here`, `!mc undo`, `!mc good`.

**Teaching it:** if Dolphin misunderstood, just tell it in chat; hit 👍 when it's right. If the
Builder wrote bad commands, edit them and hit **Fix & rebuild**; the fix is saved and learned on
the next retrain.

**Redstone Lab (optional):** copy the Bedrock server to `lab_server/`, set
`level-name=redstone_lab`, `server-port=19140`, `allow-cheats=true`, then `python test_lab.py`.

## Main files

| File | What it is |
|---|---|
| `app.py`, `index.html` | chat app + web UI, talks to Ollama and the Bedrock server |
| `model.py` | the tiny GPT (char-level transformer) |
| `train.py` | trains any of the models (`--task builder/planner/fight/brain`) |
| `data.py` | Builder request language, teacher, redstone/logic tasks |
| `redstone_lib.py`, `lab.py`, `test_lab.py` | verified redstone designs and the lab tester |
| `planner_data.py`, `rl_planner.py`, `plan.py` | Survival Planner, its RL, and its game test |
| `fight_sim.py`, `fight_data.py`, `rl_fight.py`, `exam_fight.py`, `exam_loop.py` | combat simulator, teacher, RL, exam |
| `world_sim.py`, `demo_world.py` | voxel world + pathfinding miner |
| `distill.py`, `brain_data.py` | the final merge of every model into one "Brain" |
| `gentle.py`, `pipeline.py`, `learner.py` | keeping the PC usable, job queue, background learning |
| `builder.pt`, `planner.pt`, `fight.pt` | the trained models (download from Releases) |

## Honest limits
- The tiny models are specialists, not chatbots; Dolphin does the talking.
- The planner, fight and mining results are measured in simulators. The chat app and Builder run
  on a real Bedrock server, but end-to-end play in a real world hasn't been tested yet.
- The miner uses an algorithm (A*) for paths; the learned part is the decisions on top.
