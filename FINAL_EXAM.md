# Final Exam

Every part of the AI has to pass its exam before the final merge into the Brain.
Each exam is a loop: test, learn from what failed, retrain, and test again until it passes.

## 1. Fight (`exam_fight.py`, loop: `exam_loop.py`) - PASSED 4/4
Same 200 fights per test every time, so results can be compared.

| Test | Teacher | Pass mark | Fight model |
|---|---|---|---|
| Horde of 2 mobs at once | 100% | 90% | 100% |
| Horde of 3 mobs at once | 97% | 85% | 96% |
| Horde of 5 mobs at once | 63% | 75% | 82% |
| 1v1 vs the hard-coded PvP bot | 60% | 75% | 92% |

The PvP bot (`fight_sim.py`, `_bot_turn`) is not trained. It plays by fixed expert rules:
diamond sword, iron armor, shield up against bows, strafing, W-tap combos, lucky crits, a bow at
range and 2 golden apples. Pass marks are set above the teacher, so the model has to out-play the
rules it learned from.

## 2. Castle + resources (in the voxel world, `castle_exam.py`) - PASSED 10/10
The trained Survival Planner passed all 10 worlds on its own decisions (18-51 minutes of game
time). Still simulated: hunting is a stand-in (the world has no animals yet), and the castle's
block count is paid for and timed rather than placed block by block in the voxel world.

Starting from nothing in a fresh world:
- mine and smelt 24 iron and craft a full iron armor set (helmet 5, chestplate 8, leggings 7, boots 4)
- mine enough cobblestone and gather enough wood for the castle
- build a castle (4 towers, castle walls, gate) using only gathered blocks
Pass: armor equipped and the castle fully built, in at least 8 of 10 worlds.

## 4. The Trapper (after the exams above) - to do
A new model that uses its redstone knowledge to design traps: pressure plates, tripwires,
observers, sticky pistons, trapdoors, sand/gravel drops, hidden pits, water/lava channels, TNT.
Every trap is built and fired on the lab server to prove the mechanism works.

Its challenge: trap "victim" bots that try hard not to get caught. Difficulty is set to **hard**,
not impossible:
- they look for tripwire and pressure plates and step around them
- they notice odd blocks (lone pistons, observers facing paths, holes) and avoid them
- they won't walk into 1-wide corridors or fall gaps they can see
- they can still be fooled by hidden triggers, bait (items, a fake door), observer-based
  triggers with no visible plate, and traps that fire behind them
Pass: catch the hard victim bot in most attempts with traps that are mechanically sound.

Training stays broad: many trap families (pits, pushers, launchers, droppers, arrow chambers,
cages, water/lava, suffocation, door locks, and combinations). Variety is rewarded so no single
trap takes over, and the victim slowly learns traps it keeps falling for, forcing new ideas.

Rayden's showcase list. These are NOT training targets: training never aims at them. At the end
we just check that each one shows up and works at least once:
- **Slime launcher:** sticky pistons + slime blocks fling the victim into an obvious trap it
  can't escape mid-air (pit, cage, lava moat). Proved on the lab server with an armor stand
  or mob standing in for the victim.
- **Loophole thinking:** the victim's rules are explicit, and the Trapper finds what they don't
  forbid. Example: "won't fit 1-wide halls, 2-wide is too obvious, so 3-wide, doors close behind
  it, lava pours, I trigger it myself with an observer, no rule broken." Found by search + RL
  against the victim simulator, then the model learns to write out which rule each part of the
  trap gets around, so it explains its reasoning like that.
- **Inspired by real Minecraft structures (at least once):**
  - *Jungle temple arrow trap, upgraded:* tripwire -> a fast observer clock -> dispensers firing
    arrows and tipped poison arrows like a machine gun, with sticky pistons shoving the victim
    into the firing chamber and sealing it in.
  - *Chase pit:* the Trapper's bot gets the victim to chase it across a fake floor, flips a lever
    at the right moment, and the floor drops away (sticky pistons pull it, or trapdoors open).
    Uses the fight/movement skills plus timing plus redstone.
  - Bedrock redstone differs from Java (no quasi-connectivity, some blocks can't be pushed),
    so every trap is built and fired on the lab server before it counts.

## 3. Redstone mini PC (on the lab server, `lab.py`) - in progress
**The AI has to do the building.** Everything counts only when model output is what gets placed and
tested (`test_ai_builds.py`, `test_ai_machines.py`).

Built by the AI from its own answers, on the lab server:

| Machine | Result |
|---|---|
| 11 small circuits, up to a full adder and a RAM byte | 11 of 11 work |
| 4-bit counter | 18 of 18, reset works |
| 4-bit adder | 16 of 16 |
| 4-bit address decoder | 16 of 16 |
| 4-bit ALU | 16 of 16 |
| 16-byte RAM | 32 of 32 reads |
| 64-byte RAM | 48 of 48 reads |
| 128-byte RAM, 80,318 parts | 48 of 48 reads |

Limit: it learned these from Claude's designs, so it reproduces machines. It hasn't designed its own.
Still to do by the AI: the CPU's control, a clock, storage, a mini GPU and a screen. None exist yet.
The list below is the plan; "done" there means Claude's lesson design exists.

Built in stages; each stage has to pass its lab test before the next:
1. RAM sticks - DONE for one stick: **128 bytes**, 80,000+ parts, about 104 x 775 blocks. All 48
   reads correct on 24 words spread across the stick (`test_ram.py 7 8`), and the 16-byte stick
   passes on every word. A second stick is the same design again; the two aren't wired together yet.
   1 KB would be about 500,000 parts per stick at this design's ~66 parts per bit, so it needs a
   much denser cell.
2. 4-bit ALU (add/subtract) - DONE: 1,035 parts, 16 of 16 test sums, every 2-bit case passes
   (`test_alu.py`)
3. 4-bit CPU: program counter DONE (`test_counter.py`: 18 of 18, reset works); clock, instruction
   decode and registers still to do
4. "Hard drive": storage that keeps its data (ROM / locked latches)
5. "GPU": drives a lamp screen (7-segment digits, then a small pixel grid)
6. Power supply: a clock and power distribution
The wire router (`router.py`) is built. The model plans modules and wiring; a tiler stamps out
repeated cells.
