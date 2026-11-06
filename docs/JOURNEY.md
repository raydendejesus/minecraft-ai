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

## 13. Chasing the black screens
The screens went black or the GPU dropped out four times during training, at 78-81°C, always
under the temperature limit, so heat wasn't the trigger.
- we first blamed the power-delivery problem the PC has had since August, but the cables were
  fine, and a crash still happened with the GPU capped at 290 W
- the logs then showed something more useful: **all four failures happened inside
  `rl_planner.py`**. The fight RL and exam loop ran 23+ minutes at the same temperatures and
  power, and normal training never crashed. Why that one job triggers it isn't proven yet.
- the 290 W limit also didn't stick: the card was back at 300 W days later, even though the
  startup task ran successfully, so something else on the PC is probably resetting it

## 14. The castle exam
The goal: start with nothing, end with full iron armor (24 iron) and a castle (483 cobblestone)
made only from what it gathered. The Planner decides, the voxel-world miner does the work.
- the teacher got stuck at first: iron was too rare, and the miner kept re-walking one finished
  level. Fixes: realistic ore amounts and moving to a new level after each sweep.
- giving the miner real 4.5-block reach let it mine the block under its own feet, leaving it
  on air with no legal moves. Fixes: it won't dig straight down, and it falls properly now.
- with those fixed, the teacher passed 10/10. The trained Planner then scored **0/10**:
  - round 1: it said "build" too early, because goals this big looked nothing like practice
  - round 2: it built after one helmet. Digging for iron had brought up 688 cobblestone by
    accident, and in practice "plenty of stone" had always meant the game was nearly over
  - round 3: the practice simulator now gives stone and coal along the way, like real tunnels.
    **10/10.**
- we did not add a rule blocking a bad "build". That would have hidden the problem instead of
  teaching the model, and the exam would no longer be testing its judgment.
- the lesson: when a model fails after doing fine in practice, look at how practice differs
  from the real task. Both failures were gaps in the training data, not weak judgment.

## 15. The wire router and the 4-bit adder
Chaining adders by hand kept running wires into each other, so we built a router (`router.py`): a
search that finds a dust path obeying the rules the lab taught us, climbing over other wires when
it has to.
- first try: 12 of 16 sums right, and every failure involved a carry
- reading the signal block by block showed two separate problems: the circuit needed more time
  than the test gave it, and the wire left the adder at strength 7 and died before its first
  repeater
- fix: repeaters on the adder's carry output and input, so wires start and arrive at full
  strength (the second half adder moved over 2 blocks to make room)
- result: the 2-bit adder got 16 of 16 (every combination) and the **4-bit adder 16 of 16 test
  sums** on a real server, including 15 + 1 rippling through every bit. 709 parts, carry wires
  laid by the router.

## 16. Addressable RAM
- **4-bit address decoder:** exactly one of 16 lines on for each address, 1,724 parts. Getting
  there took three fixes found by reading signals in the game: rows 3 apart linked up with the
  taps beside them (dust climbs one block), address lines died before the far rows, and big
  builds outran the server, so tests now wait for it to catch up.
- **RAM cell:** a locking repeater stores the bit, and a comparator in subtract mode lets it
  reach the output wires only when that word is addressed.
- a 4-word test read all zeros. The cell was fine; the test was reading the wrong blocks (height
  and depth swapped), and the "not selected" wire was too weak to reach the later bits.
- **16-byte stick:** 8,489 parts, 32 of 32 reads correct on the first full-size run. That test only
  used values up to 76, so the top bit was checked again with values that use all 8 bits.
- the old estimate for 1 KB (~200k parts) was too low: at this design's ~66 parts per bit it's
  about 500k per stick.

## 17. The upgraded Builder
Rayden watched it train in the Neural Viewer and worried it was spamming random block names. The
check showed it was only 8% through its lessons, and the odd names (`nhjt_doohb`) were deliberate:
made-up blocks teach it to copy any name instead of memorizing a list. Accuracy went 13% → 62% →
87% → 98% as it trained. Final test: 97.6% of 500 new requests, and all 18 circuits written
block for block. Its weak spot is full truth tables (44%), which take real multi-step logic.

## 18. The 128-byte test
The first run read 8 of 48 correctly, and the pattern gave it away: words came back in groups of
32, so only the top 2 of the 7 address bits worked. Decoder rows were 42 blocks long with one
repeater, so the low bits died on the way. Smaller versions were short enough to hide it.
With a repeater every 12 blocks, the retest read **48 of 48 correct**: 24 words across the whole
stick, then again after rewriting one word to prove the others stayed untouched. It's over 80,000
parts, 104 by 775 blocks, placed in about 22 minutes with `/fill`, on Bedrock 1.26.61.

## 19. Updating the servers
Rayden couldn't join the lab, which took three fixes: Store Minecraft is blocked from reaching its
own PC until it gets a loopback exemption, the server was older than the game, and the new version
requires `transport=nethernet`. The main server was backed up first, then updated, keeping its world
and add-on. All 11 circuits still passed on the new version.

## 20. The ALU
A - B is A + (NOT B) + 1, so each B input goes through an XOR driven by one SUB lever, and SUB also
feeds the first carry-in. Getting there was the same lesson three times: signals arriving weak. B
reached the adder at strength 3, so it got a repeater; SUB reached the first XOR at 3, so that got
one too. A separate bug: failed test runs left lab servers running, and they fought over the world.
The 4-bit ALU then scored 16 of 16, including wrap-arounds like 3 - 5 = 14.

## 21. The program counter
Each bit is a flip-flop: two locking repeaters working like an airlock, so it flips once per clock
pulse. On the way to a working 4-bit counter:
- it woke up with random values, so it got a RESET line
- the reset wire touched the stone in the clock's inverter, which jammed the clock on (the lamp
  trap again: anything a repeater powers will feed the dust beside it). Repeaters fixed it.
- all the lamps looked dead because a branching wire stops pointing at its lamp, which made a
  working counter look broken
- hand-laid wires shorted one bit's output into the next bit's clock, so the router took over
Result: 18 of 18 counts, wrapping from 15 to 0, and RESET clears 15 back to 0.

## 22. "You no build, our AI builds"
Rayden caught the project drifting: Claude had been designing the ALU, counter, decoder and RAM
itself, and nothing the AI wrote had ever been placed in the game. The goal is an AI that can
build, so those hand-made designs are lessons for the model, not results for it.
- first real test (`test_ai_builds.py`): the Builder wrote 11 circuits, only its blocks were placed,
  and **11 of 11 worked in the game**, up to a full adder and a byte of RAM
- limit: it learned those designs by example, so this shows it can reproduce circuits, not invent
  them. Designing its own is the next goal.

## 23. The AI builds the machines
Rayden's call: have the AI build everything Claude built, and expand its memory if needed.
- answers were too long, so straight lines became runs, and the context grew from 1,280 to 6,144
  characters, keeping everything the model already knew
- for RAM, growing the context was never going to work (276,820 characters for 128 bytes). Rayden
  asked for more memory or a smaller stick, and it turned out neither was needed: a repeat
  shorthand ("this part, 128 times, every 6 blocks") shrank 128 bytes to 3,489 characters
- it ran unattended overnight: the AI wrote all 19 machines exactly, then built each one on the lab
  server from its own answers, with none of Claude's parts placed. Counter, adder, decoder, ALU and
  RAM sticks of 16, 64 and 128 bytes all passed

## 24. The designer: inventing circuits, not copying them
Reproducing lessons isn't designing, so a bigger model (14.8M parameters, `designer.pt`) got a new
kind of problem: "design 0110..." gives what a lamp should do for all 16 combinations of four
levers, and it has to write a logic formula that does exactly that. A design counts when it
works, not when it matches the teacher.
- all 65,536 possible goals exist; 1 in 10 is locked away and never shown in training, and the
  exam uses only those
- the easiest goals were barely practised (1 lesson in 1,000), so it scored 0% and 56% on them;
  half its practice now gives every difficulty level an equal share
- it keeps its whole old lesson mix, so it stays a general Minecraft model: after practice it
  still wrote all 19 machines exactly
- result: **99.4% on goals it has never seen, every difficulty level 95% or higher**
- Claude tried "natural selection" (5 attempts, keep the best). Rayden stopped it: that only works
  for one narrow task, and this is a general agent. It was removed.

## 25. From its own formula to its own redstone
Next, the designer turns its formula into blocks: "redstone circuit <formula>". The lessons come
from a teacher that Claude wrote (`circuit.py`). It places one lab-tested gate per and / or / xor /
not, and a router lays every wire. Rayden asked that every block a wire crosses costs something,
so the wire takes the shortest route rather than wandering. The router is an A* search: 1 per
block, more for turns and climbs.
- before teaching anything, the teacher's own circuits had to pass the lab on all 16 rows.
  The first try passed 16 of 24 because of:
  - deep circuits needing 7 s to settle
  - a wire's own support block cutting its stair step
  - a branch touching its own wire across a repeater, which latched the signal on forever
  - after the fixes: 23 of 23, plus a 7-gate circuit 124 blocks long once the lab area grew
- the test (`test_ai_circuits.py`): for locked goals, the AI designs, then writes the blocks for
  ITS OWN formula, and only what it wrote is placed in the lab
- first lesson format (every block sorted by type and position): after 2 rounds it never wrote a
  circuit right, because the very first line depended on the whole finished layout
- build-order format: inputs, then each gate where it chose to put it, then each wire block by
  block. After 1 round on it:
  - every gate's blocks were right (193 of 193)
  - about 93% of the gate positions matched the teacher's layout
  - about half the wires matched
  - in the lab, **1 of 15 AI-built circuits worked on all 16 rows**; most got 8 to 14 rows right.
    Wires are the weak part: its own routes are often shorter but run into another wire
- 3 more rounds on build order:
  - offline, its circuit matched the teacher's exactly for 6, then 8, then 10 of 22 goals
  - in the lab, **9 of 15 AI-designed, AI-built circuits worked on all 16 rows**, up from 1
  - every goal up to 4 gates passed; the misses were 5 to 7 gates, with 8 to 11 rows right
  - it still writes all 19 machines from memory
  - design exam: 98% or better on every level except one: the 9 one-gate goals swing between
    67% and 89%, where they used to be at 95% or higher
- practice continues, with a lab test every 2 rounds, until 13 of 15 work or it stops improving
  - 2 rounds later: 7 of 15 in the lab. 15 circuits is a small test, so 9 and 7 are about the
    same level. Its wires got better (65% now match the teacher, up from about half), but one miss
    was the simplest goal of all: it designed "b" correctly, then built "b and c". Circuits with no
    gates are only a handful of its 16,000 circuit lessons
  - 2 rounds after that: **10 of 15**, the best so far. Everything up to 4 gates passed (including
    "b" this time), 1 of 2 at 5 gates (the other got 14 of 16 rows); the 6- and 7-gate circuits
    got 6 to 14 rows
  - the last 2 rounds: 9 of 15. It levelled off at 9 to 10: everything small works, and the
    big ones fail
- why the big ones fail: a quick check with no lab (`circuit.shorts`) looks for wires of two
  different signals touching. It matched the lab on all 15 circuits. Every one that failed had a
  short, every one that passed had none, and the teacher's circuits have none. So it knows its
  gates and can lay a wire, but it doesn't yet keep clear of the wires it already laid, mostly
  near the levers where many signals leave side by side
- next: homework marking (`circuit_corrections.py`). It writes circuits for practice formulas
  (never exam goals), the ones with shorts or unreadable blocks are marked, and the correct circuit
  for each goes back into its practice more often, inside the full lesson mix. Nothing is picked
  from several tries: it just practises its own mistakes more
  - two blocks of homework: 9 of 15, then 8 of 15 in the lab. The circuits with no gates were
    fixed (6 of 15 clean, then 15 of 15), but the big ones didn't move (6 gates: 4, 2, 1 of 15)
  - the last block: **10 of 15** again, the best so far. Every goal up to 5 gates passed this
    time; the misses were one 6-gate and two 7-gate circuits (8 to 14 rows right). It still
    writes all 19 machines from memory
- where the shorts are: 76% right next to the levers, where 8 input signals fan out to every gate;
  83% between two input wires; 82% on routes the AI chose itself, a block off the teacher's
- next: a design rule real circuit boards use too, clearance. The teacher keeps a block of air
  between different signals' wires, so one slip no longer touches. On the teacher's own
  circuits the spots where one slip would short went from 36 to 6 per circuit, for 2% more
  parts. It has to pass the lab before it teaches anything (`overnight_circuits2.py`)
  - the new teacher passed the lab, 24 of 24. First lab test after 2 rounds on its lessons: 7 of 15.
    The bigger circuits got closer (5 to 7 gates: 6 to 14 rows right), but the smallest broke: for
    "b" it built a two-gate circuit instead of one wire to the lamp. The lesson bank has only 7
    circuits with no gates against about 3,000 of each big size, and the homework fixes that had
    patched this came from the old teacher. Same cure as design practice once needed: every
    circuit size now gets an equal share half the time
  - next lab test: 7 of 15 again. "b" had the right shape now, but its wire had a 9-block gap:
    it put the repeater at the wrong spot and skipped the run after it. No short, so the homework
    had called it clean. A second check (`circuit.breaks`) now marks gaps too: every wire must be
    one connected piece, reach its gate, and start from its own signal. On the teacher's lessons
    it finds nothing (0 of 300). On the AI's last 15 lab circuits, shorts + gaps agreed with the
    lab on 14: every one with either failed, every one with neither passed but one
  - after 2 more rounds with homework marking gaps too: **8 of 15**. Every goal up to 4 gates
    passed, "b" included; the 7 misses were the 5- to 7-gate circuits (6 to 13 rows right). The
    homework checks agree: clean big circuits went from about 7 in 15 to 7–10 in 15, while the
    old lessons' best is still 10 of 15. More rounds are running
  - 2 rounds later: **9 of 15**. Up to 4 gates still all pass; the 6 misses are 5 to 7 gates, but
    closer than before (6 to 14 rows right, four of them 11 or more). In between, the design exam
    dipped on the tiniest goals (0 gates: 0 of 1, 1 gate: 6 of 9), then came back to 100% the next
    round. Only 10 small goals are locked away, and the AI has to work them out from 60 practice
    ones (it practises "a", "c", "d", "not b" but never "b" itself), so one slip moves the score a
    lot. For "b" it now writes a longer formula that still works
  - last block of that run: **9 of 15** again (7, 8, 9, 9 over four lab tests), and it still
    writes all 19 machines exactly. Of the 6 misses, 4 had shorts and 2 had gaps, all deep into
    long circuits (300 to 500 lines). The sixth had neither: its wires were fine, but it brought
    "a" to a gate input that needed "b". A third check (`circuit.logic`) works out what the
    wiring computes from its labels: which gate sits where, and which signal goes to which
    input. It agrees with the teacher on 182 of 182 lessons, and shorts + gaps + logic now agree
    with the lab on all 15. Homework marks all three, and marks 240 circuits instead of 120 so
    the corrections cover more formulas (`overnight_circuits4.py`, up to 8 more rounds)
  - first lab test of that run: **9 of 15** again, but a different 9. The 7-gate circuit
    "a xor not ((a xor (c and not d)) and (b xor (c xor d)))" worked for the first time, and
    the other big misses were closer (8 to 14 rows right). "b" broke again: it wrote the lamp
    and the one wire it needs, then didn't stop, and carried on with wires and a gate from some
    other circuit. "b" on its own is a locked-away exam goal, so it is never in its lessons or
    its homework (the bare inputs it does practise, like "a" and "not c", were 30 of 30 clean);
    it has to work out from those that "b" is the same kind of circuit, and 3 lab tests in 5 it
    did. The three checks agreed with the lab on 14 of 15; the odd one was a touch between two
    wires that shorts() calls a short, but that worked in the lab
  - next lab test: **8 of 15**. "b" broke the same way and ran on into unreadable lines. A
    3-gate circuit that had always worked failed too, and none of the three checks saw why:
    it put a repeater one block early on a raised wire, so the run after it was 16 blocks, one
    more than redstone carries. A fourth check (`circuit.weak`) follows each signal's strength,
    15 at its source, one less per block of dust, back to 15 at a repeater. It calls none of
    287 teacher lessons weak, and on these 15 it found that one plus a 6-gate miss the other
    checks had also passed. All four together agree with the lab on all 15. Homework marks it
    from the next block on
  - last lab test of that run: **9 of 15**, no better than its best for two tests, so it
    stopped (19 of 19 machines still exact). Over the last seven lab tests: 7, 8, 9, 9, 9, 8, 9.
    Everything up to 4 gates works except "b"; most of the 6- and 7-gate circuits are close
    (8 to 15 rows right) but not there, and the mistakes come late, in the last wires it lays
    near the levers, where the most wires already are. Another run with all four checks in the
    homework is going (`overnight_circuits5.py`); if it stays stuck, the next idea is a tidier
    teacher: every signal gets its own lane, so where a wire goes follows a simple rule instead of
    depending on everything laid before it

## 26. Faster, without getting dumber
Rayden: Minecraft can't wait 5 seconds between actions, but don't lose smarts for speed. The
weights never change, and every fast answer is checked letter for letter against the plain one.
Measured on an idle GPU:
- sending commands was never the slow part: the game places them as they arrive
- the models write about 300 characters a second, and their "thinking" is inside every
  character, there's no separate thinking step
- a key/value cache (it stops re-reading its whole answer for every new letter) writes a whole
  6-gate circuit in 8.8 s instead of 16.8 s, the same circuit. It's used for long answers
- for moves from a list (PvP), the model rates every legal move in one pass and plays its top
  pick: 8.5 ms instead of 27 ms, the same move 150 times out of 150
- a CUDA-graph writer gave the same answers but was slower everywhere, so it isn't used

## 27. The PvP model
Rayden wanted a model for player-vs-player only: no mobs, no hordes, lots of fights.
- a new duel simulator (`pvp_sim.py`) built from the Minecraft Wiki's Bedrock numbers. It covers:
  - hit immunity, where only a bigger hit deals the difference
  - reach from the eyes to the nearest point of a 0.6 x 1.8 hitbox, so the higher player has to
    be closer
  - armor with toughness, Protection, and Bedrock's Sharpness and Strength
  - shields raised by sneaking: 0.25 s to come up, hitting one knocks the attacker back, and an
    axe disables it
  - W-tap knockback, crits, bows, golden apples, potions, pearls and hunger
  - 8 kits, flat ground or hills, and 11 opponent styles at random skill levels. The few
    numbers the wiki doesn't give (knockback distances) are marked as estimates
- a bug first: whoever moved first got their hit in first, so the same bot beat itself 98% of
  the time. Now both moves land at once, and the mirror match is 43% / 44%
- the teacher plans ahead: before every move it plays each option 4 seconds forward 6 times. It
  won 93% of 45,000 duels, which became 1.9 million lessons
- `pvp.pt` (4.8M parameters) after one training run, on 480 fixed exam duels it never saw:
  - **won 98%, lost 0%**: 100% against 9 of the 11 styles, 82% against potters (the rest
    draws), 95% against the rulebook expert
  - **5 ms per move**, against a quarter-second game tick
- that exam got too easy to show progress, so there's a harder one now: duels against the
  look-ahead teacher itself. The student won 48%, lost 28%, drew 25%
- homework rounds: it plays, the teacher marks every move it reaches, and its mistakes get
  practice. It agreed with the teacher on only 42% of moves (many moves are close calls), so
  each round adds about 7,500 corrections
  - against the teacher, won 57%, then 62%, then 52% over the three rounds (40 duels each, so
    about ±8%): better than the first 48%, then no clear gain after round 1
- the math / geometry / hitbox stage, on top of its PvP lessons: 232 of 300 fresh questions
  exactly right
  - all the PvP geometry is right: can I reach them from here at this height (51/51), how far away
    can I hit (28/28), where to aim (43/43), hitbox sizes (32/32), and the facts (no headshot
    bonus, high ground, hit immunity, shields, W-tap)
  - the plain math isn't there yet: Pythagoras 41 of 81, the distance between two 3D points 0 of
    28. Exact decimals, one character at a time, are hard for a model this size
- `pvp.pt` now: easy exam 98%, against the teacher 58% won / 28% lost, 6 ms a move

## Still to do
See [FINAL_EXAM.md](../FINAL_EXAM.md): finish the fight exam, the castle + iron armor exam, the
redstone mini PC, the Trapper, and the final merge of everything into one Brain.
