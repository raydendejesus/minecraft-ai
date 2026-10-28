# How we built it

The steps Rayden and Claude took to build Minecraft AI, in order, including the dead ends.
Most of what's interesting is in what broke and how we fixed it.

## 1. "Can we train a very small AI model?"
The first idea was one tiny model trained from scratch on Minecraft data that you could chat
with. We didn't do that: a model small enough to train from nothing on one GPU can't hold a
conversation. Instead we split the job:
- a pretrained chat model to talk to (it already knows English)
- tiny specialist models trained from scratch for the Minecraft-specific jobs

## 2. The Builder and its request language
We designed a small request language (`house <wall> <floor> <roof> <w> <h> <d> <door side>`,
`wall`, `floor`, `box`, ...) so the chat model could hand precise jobs to a tiny model. A
"teacher" function knows the right Bedrock commands for any request and generates fresh random
examples every step, so the model learns the rules instead of memorizing.
- first run: **98-100%** exact-match on unseen requests in about 4 minutes on the RTX 3090

## 3. Choosing the chat model
- `qwen2.5:3b` worked but was **too strict**: it refused harmless things like prank ideas.
- `dolphin-phi` (2.7B, the smallest usable Dolphin) **couldn't follow the format**: broken JSON
  and made-up actions. `tinydolphin` would have been worse.
- `dolphin3` (8B, uncensored, already installed) worked: valid builds in 2-4 seconds, answers
  questions straight, handles "make it detailed" with many pieces.
- `dolphin-phi` also ran away generating whitespace in JSON mode; capping reply length fixed it.
- Photos: Dolphin can't see, so `qwen2.5vl` describes the photo and Dolphin plans from the
  description. It never chats with you.

## 4. Building safely in a real world
Bedrock Dedicated Server has no RCON, so the app owns the server process and types into its
console. Builds are anchored to an invisible-ish marker armor stand so corrections rebuild in the
same spot, and every build is saved with `/structure save` first so **undo** works.
We added a guard after Dolphin started setting "undo first" on brand-new builds, which would
have erased the previous build.

## 5. The Survival Planner
A survival simulator with real recipes (logs → planks → sticks → pickaxes, smelting, hunger)
plays as the teacher.
- first result: 87% of single moves right, but **only 25% of full games won**: one bad move
  sinks a 15-step game, and most mistakes were arithmetic ("mine 2 iron" when it needed 6)
- fix: the model chooses *what* to do and a recipe calculator decides *how many* → **68%**
- longer training → **77%**

## 6. The Redstone Lab
We copied the Bedrock server into a private lab with a flat world on its own port and wrote a
harness that builds circuits and reads lamps back with `/testforblock`.
- calibration found that a repeater's `cardinal_direction` is the side the signal comes *from*,
  torch facing is the side its support is on, and piston facing numbers are flipped
- two of our first test rigs were wrong, not the game: a redstone block doesn't power the stone
  next to it, and straight dust only powers what's at its end
- NOT/OR/NOR/NAND/AND passed on the first try; XOR needed a wire bridge (two layers) and two
  comparators in subtract mode
- **the lamp trap:** our first 1-bit RAM froze after one write. A lamp powered by a repeater
  becomes a powered block and was feeding the lock wire next to it. Moving the wire one block
  away fixed it.
- the RAM byte "failed" because the test changed data and write at the same instant. Real chips
  have the same rule (hold time); fixing the test order made it pass.
- half adder: carry = B − (B and not A) with one extra comparator, no new crossings
- full adder: two half adders + an OR, all 8 rows pass
- a misread bug: the harness stopped listening after 0.25s, so slow server replies were missed;
  it now waits for the reply that names the exact block

## 7. Reinforcement learning
The Planner plays batches of games and decisions from better-than-average games get reinforced.
- 74.8% → 77.2% → **81%**, then it **collapsed to 44%**: it over-learned from a few lucky games.
  Because it only saved on improvement, the 81% version was safe.
- fixes: half the learning rate, capped rewards, twice the games per update, and automatic
  rollback to the best version when the score drops
- Rayden's point: this is an agent that has to **judge**, not pick randomly. Exploration only
  happens while practicing; when it plays, it always takes its best judgment.

## 8. Merging redstone into the Builder
A compact parts language (`r 4 0 1 e` = repeater pointing east) lets a circuit fit in the model's
output. All 11 designs pass when rebuilt in the exact order the model writes them. We added
logic lessons too (evaluate random expressions, full truth tables) so it learns logic, not just
recall.

## 9. Moving and mining
`world_sim.py`: a voxel world with real ore depths, caves, lava and bedrock, and an agent that
knows its body (1.8 tall = 2 blocks, step up 1, safe drop 3, no digging next to fluids or
straight down, no x-ray).
- first try failed instantly: it spawned on top of a tree, and the 143-block staircase search
  was too big in one go. Fixes: spawn on the ground, dig down in 12-block legs.
- strip mining walked in circles (turning whenever blocked). Switched to real player
  technique: long straight tunnels 3 blocks apart → diamonds in **20/20 worlds**.

## 10. More building, and the Fight model
- 9 new structures (towers, cylinders, pyramids, bridges, castle walls, windowed walls, fence
  rings, farms, lamp posts) and ~30 new blocks, all checked on the lab server first
- the fight simulator grew from 6 to 28 mobs with real attack styles and effects
- the first fight teacher danced forever with creepers; we taught it hit-and-run
- Rayden asked for hiding: with a pickaxe it digs into a wall, eats so health regenerates
  (only on full hunger, like Bedrock), and waits for mobs to lose interest. It never hides from
  a warden, whose sonic boom goes through walls.

## 11. Keeping the PC usable
- **lag:** training plus Minecraft had the GPU at 100% and 23 GB of memory. We added gentle mode:
  low priority, a memory cap, a work/rest duty cycle, and pausing while Minecraft is open. It
  later became adjustable live through `gentle.json`.
- **black screens:** the screens went black for ~30 minutes during full-speed training and the
  GPU driver dropped out, which crashed the next step. We added a temperature guard (slow down
  from 82°C, pause at 90°C until 75°C), temperature logging, and checks so a missing GPU can't
  cascade into empty training data.
- **one job at a time:** `pipeline.py` queues training jobs and starts each automatically.

## 12. The final exam
Rayden set the bar: fight hordes and beat a hard-coded PvP bot "until it wins", grind iron and
build a castle, and build a redstone mini PC.
- kiting took the teacher from 21% to 63% against 5 mobs at once
- balancing the PvP bot took three tries: better stats made it **unbeatable (0%)**; giving only
  our side W-tap combos made it **a pushover (100%)**; both sides combo-ing with the bot keeping a
  small crit edge made the teacher win **60%**, a real fight
- pass marks were set **above the teacher** so the model has to out-play what it learned from
- first exam: the model already beat its teacher on the two hardest tests (70% vs 63%, 68% vs
  60%); after practice it passed 3 of 4 (100/93/76%) with the duel at 73%
- the duel then **stalled at exactly 146/200** for three rounds. Duels were only 15% of
  practice, so they barely moved the score that decides saving. Fix: focused practice on the
  failing test.
- with focused practice it **passed all 4 tests after 3 rounds**: 100% / 96% / 82% against
  hordes, and **92% against the PvP bot**, far past the teacher's 60%.

## 13. The black screens are power, not heat
Three times during training the screens went black and the GPU froze, at 78-81°C each time,
always under the temperature limit (the guard logs every 10 seconds). It's the same
power-delivery issue Rayden's PC has had since August: sudden sustained GPU load drops the
display. A temperature limit can't prevent it; reseating the GPU power cables (and/or a lower
GPU power limit) is the real fix. GPU training is paused until that's sorted.

## Still to do
See [FINAL_EXAM.md](../FINAL_EXAM.md): finish the fight exam, the castle + iron armor exam, the
redstone mini PC, the Trapper, and the final merge of everything into one Brain.
