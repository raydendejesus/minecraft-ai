"""Combat simulator with Bedrock Edition numbers, for the Fight model.

Player: 20 health. Bedrock has NO attack cooldown, so you can swing every tick (0.5s here).
    Weapon damage (Bedrock): fist 1, wooden/golden sword 5, stone 6, iron 7, diamond 8, netherite 9,
                             wooden axe 4, stone 5, iron 6, diamond 7
    Critical hit (attack while falling from a jump): 1.5x damage, but only lands about half the time
    Armor: every armor point blocks 4% of damage (max 20 points = 80%)
        leather set 7, chainmail 12, iron 15, diamond 20
    Shield (sneak to raise): blocks melee, arrows, fireballs and blasts from the front,
        but you move slowly and can't attack. The warden's sonic boom goes straight through.
    Bow: 1s to fully draw, ~9 damage. Endermen teleport away from arrows.
    Health only regenerates while your hunger is full (1 health every 4s on Bedrock).
    Eating takes 1.6s and fills hunger (+4 health here as a stand-in).
    Hiding: with a pickaxe or shovel you can dig 2 blocks into a wall and seal yourself in
        (takes 1.5s). Melee mobs can't reach you, arrows can't hit you, creeper blasts are mostly
        absorbed. Mobs lose interest after ~12s. Hiding does nothing against a warden.
"""

import math
import random

TICK = 0.5
WEAPONS = {"fist": 1, "wooden_sword": 5, "stone_sword": 6, "iron_sword": 7, "diamond_sword": 8,
           "netherite_sword": 9, "wooden_axe": 4, "stone_axe": 5, "iron_axe": 6, "diamond_axe": 7}
ARMOR = {"none": 0, "leather": 7, "chainmail": 12, "iron": 15, "diamond": 20}
REACH = 3.0

# style: melee | ranged (keeps its distance) | explode | swoop (flies in, hits, flies off)
#        | flyer (stays out of sword reach and shoots)
# keep=(min, max) distance for ranged mobs. effect: poison | wither | slow | hunger
M = lambda hp, speed, dmg, cd, style="melee", reach=1.5, keep=None, neutral=False, effect=None, \
    w=4, blockable=True, arrows=True, info="": dict(hp=hp, speed=speed, dmg=dmg, cd=cd, style=style,
                                                    reach=reach, keep=keep, neutral=neutral, effect=effect,
                                                    w=w, blockable=blockable, arrows=arrows, info=info)
MOBS = {
    "zombie": M(20, 2.3, 3, 1.0, w=10, info="walks straight at you and punches, slow, comes in groups at night, burns in daylight"),
    "husk": M(20, 2.3, 3, 1.0, effect="hunger", w=3, info="desert zombie that does not burn in sunlight, its hits make you hungry"),
    "drowned": M(20, 2.0, 3, 1.5, style="ranged", keep=(3, 8), w=3, info="underwater zombie, the ones holding tridents throw them from range"),
    "zombie_villager": M(20, 2.3, 3, 1.0, w=2, info="zombie villager, fights like a zombie, can be cured with a splash of weakness and a golden apple"),
    "spider": M(16, 3.0, 2, 1.0, w=7, info="fast, jumps at you and climbs walls, neutral in daylight"),
    "cave_spider": M(12, 3.0, 2, 1.0, effect="poison", w=3, info="small blue spider from mineshafts, its bite poisons you, fits through 1 block gaps"),
    "silverfish": M(8, 2.5, 1, 1.0, w=2, info="tiny bug from infested stone, weak but calls others when hit"),
    "endermite": M(8, 2.5, 2, 1.0, w=1, info="tiny purple bug that sometimes appears from ender pearls"),
    "skeleton": M(20, 2.0, 3, 2.0, style="ranged", keep=(6, 10), w=9, info="keeps its distance and shoots arrows, strafe side to side to make it miss, rush it or out shoot it"),
    "stray": M(20, 2.0, 3, 2.0, style="ranged", keep=(6, 10), effect="slow", w=2, info="snowy skeleton, its arrows give slowness"),
    "pillager": M(24, 2.5, 4, 2.0, style="ranged", keep=(5, 9), w=3, info="crossbow raider, shoots hard bolts from mid range, shields block them"),
    "vindicator": M(24, 3.5, 13, 1.0, w=2, info="axe raider that rushes you and hits very hard, block with a shield or kill it fast"),
    "evoker": M(24, 2.0, 6, 3.0, style="ranged", keep=(4, 10), w=1, info="summons fangs from the ground and vexes, drops a totem of undying, rush it"),
    "witch": M(26, 2.0, 6, 3.0, style="ranged", keep=(3, 8), effect="poison", w=3, info="throws harming and poison potions and drinks healing ones, rush it so it cannot keep distance"),
    "creeper": M(20, 2.5, 22, 0, style="explode", reach=3.0, w=8, info="sneaks up, hisses for 1.5 seconds and explodes, back away to cancel the fuse, hit and run, or block with a shield"),
    "enderman": M(40, 4.0, 7, 1.0, neutral=True, reach=2.0, arrows=False, w=3, info="neutral until you look at it or hit it, then teleports and hits hard, arrows do not work, stand under a 2 block ceiling or fight in water"),
    "zombified_piglin": M(20, 3.0, 8, 1.0, neutral=True, w=2, info="neutral in the nether, but hitting one makes the whole group attack you"),
    "piglin": M(16, 3.0, 5, 1.0, neutral=True, w=2, info="neutral if you wear gold armor, otherwise attacks with a sword or crossbow"),
    "iron_golem": M(100, 2.5, 15, 1.5, neutral=True, reach=2.0, w=1, info="protects villages, neutral unless you hurt it or villagers, throws you into the air, avoid fighting it"),
    "wither_skeleton": M(20, 2.5, 8, 1.0, effect="wither", w=2, info="tall black skeleton in nether fortresses, its sword gives the wither effect, drops wither skulls"),
    "blaze": M(20, 2.0, 5, 3.0, style="ranged", keep=(5, 12), w=2, info="floats and shoots 3 fireballs in a row, shields block fireballs, snowballs hurt it"),
    "ghast": M(10, 2.0, 6, 3.0, style="flyer", keep=(12, 20), w=1, info="huge floating nether mob, shoots exploding fireballs, hit a fireball back at it or use a bow"),
    "guardian": M(30, 2.0, 6, 3.0, style="ranged", keep=(4, 14), w=1, info="ocean monument fish that charges a laser beam, break line of sight or rush it"),
    "phantom": M(20, 5.0, 6, 4.0, style="swoop", w=2, info="appears if you have not slept, swoops down to bite then flies off, hit it as it swoops or shoot it, sleep to stop them"),
    "slime": M(16, 2.0, 4, 1.0, w=2, info="big slimes split into smaller ones when killed, only big and medium ones hurt"),
    "magma_cube": M(16, 2.0, 6, 1.0, w=1, info="nether slime that splits too and hits harder, takes less damage"),
    "hoglin": M(40, 3.0, 6, 1.5, w=1, info="nether beast that charges and throws you up, scared of warped fungus"),
    "ravager": M(100, 2.5, 12, 2.0, reach=2.0, w=1, info="raid beast with 100 health that rams you, roars to knock you back, use a shield or avoid it"),
    "warden": M(500, 3.0, 30, 1.5, reach=2.0, blockable=False, w=1, info="blind deep dark monster that hunts by sound, 30 damage hits and a sonic boom that goes through shields and walls, never fight it, sneak away"),
    # hard-coded PvP opponent, only used in duels (w=0 keeps it out of normal fights)
    "pvp_bot": M(20, 5.6, 8, 0.5, style="bot", reach=3.0, w=0, info="an expert player bot with a diamond sword, iron armor, shield, bow and golden apples, it strafes, crits, blocks your arrows and heals"),
}
HORDE_MOBS = ["zombie", "husk", "skeleton", "stray", "spider", "cave_spider", "creeper", "drowned",
              "pillager", "witch", "zombie_villager", "slime"]


def armor_cut(dmg, armor_points):
    return dmg * (1 - min(20, armor_points) * 0.04)


class Mob:
    def __init__(self, kind, dist, rng, hp=None):
        self.kind, self.s = kind, MOBS[kind]
        self.hp = hp if hp is not None else self.s["hp"]
        self.dist = dist
        self.cool = rng.uniform(0, self.s["cd"])
        self.fuse = None
        self.angry = not self.s["neutral"]
        self.split = kind in ("slime", "magma_cube") and hp is None
        self.swoop_t = rng.uniform(0, self.s["cd"])
        # pvp bot only
        self.shielding, self.apples, self.arrows, self.drawn = False, 2, 16, 0.0
        self.sprint_ready = True


class Fight:
    """One encounter. Distances are along one line (the mobs are in front of you).

    scenario None   random gear, 1-3 random mobs (normal training)
             horde  good gear vs n_mobs common hostile mobs at once
             duel   1v1 against the hard-coded pvp_bot, both in the same gear
    """

    def __init__(self, rng=None, n_mobs=None, scenario=None):
        self.rng = r = rng or random.Random()
        self.scenario = scenario
        self.hp = float(r.choice([20, 20, 20, 16, 12, 8, 6, 4]))
        self.weapon = r.choice(list(WEAPONS))
        self.armor = r.choice(list(ARMOR))
        self.shield = r.random() < 0.4
        self.bow = r.random() < 0.4
        self.arrows = r.randint(4, 32) if self.bow else 0
        self.food = r.choice([0, 0, 1, 2, 4])
        self.dig = r.random() < 0.6               # has a pickaxe or shovel
        self.full = r.random() < 0.6              # hunger full -> health regenerates
        kinds = list(MOBS)
        weights = [MOBS[k]["w"] for k in kinds]
        n = n_mobs or r.choice([1, 1, 1, 2, 2, 3])
        if scenario in ("horde", "duel"):
            self.hp, self.armor, self.shield, self.bow, self.arrows = 20.0, "iron", True, True, 16
            self.weapon = "diamond_sword" if scenario == "duel" else "iron_sword"
            self.food, self.full, self.dig = (2, True, False) if scenario == "duel" else (3, True, True)
        if scenario == "duel":
            self.mobs = [Mob("pvp_bot", r.uniform(8, 14), r)]
        elif scenario == "horde":
            self.mobs = [Mob(r.choice(HORDE_MOBS), r.uniform(4, 16), r) for _ in range(n)]
        else:
            self.mobs = [Mob(k, r.uniform(3, 16), r) for k in r.choices(kinds, weights, k=n)]
        self.time = 0.0
        self.drawn = 0.0
        self.escaped = False
        self.hidden = 0.0                          # seconds spent sealed in a wall
        self.digging = 0                           # ticks left digging in
        self.effects = {}                          # effect -> seconds left
        self.regen = 0.0
        self.sprint_ready = True                   # a sprint hit (combo) knocks the target back

    # ---- what the Fight model reads
    def state_text(self):
        gear = f"{self.weapon} armor {self.armor}"
        if self.shield:
            gear += " shield"
        if self.bow:
            gear += f" bow {self.arrows}"
        if self.dig:
            gear += " pickaxe"
        status = f"hp {self.hp:.0f} food {self.food} hunger {'full' if self.full else 'low'}"
        if self.sprint_ready:
            status += " sprint"
        if self.hidden:
            status += " hidden"
        elif self.digging:
            status += " digging"
        for e in self.effects:
            status += f" {e}"
        mobs = " | ".join(
            f"{m.kind} {m.dist:.0f} hp{max(0, m.hp):.0f}" + (" fuse" if m.fuse is not None else "")
            + ("" if m.angry else " calm") + (" shield" if m.shielding else "")
            + (" drawing" if m.drawn else "")
            for m in sorted(self.alive(), key=lambda m: m.dist)[:3])
        return f"{status} | {gear} | {mobs}"

    def alive(self):
        return [m for m in self.mobs if m.hp > 0]

    def threats(self):
        return [m for m in self.alive() if m.angry]

    def over(self):
        return self.hp <= 0 or self.escaped or not self.threats() or self.time > 90

    def won(self):
        return self.hp > 0 and not self.escaped and not self.threats() and any(m.hp <= 0 for m in self.mobs)

    def survived(self):
        """Lived through it without killing everything (ran or hid until they gave up)."""
        return self.hp > 0 and (self.escaped or (not self.threats() and not self.won()))

    # ---- one tick: the player acts, then every mob acts
    def step(self, action):
        p = action.split()
        verb, target = p[0], (p[1] if len(p) > 1 else None)
        r = self.rng
        alive = sorted(self.alive(), key=lambda m: m.dist)
        tgt = next((m for m in alive if m.kind == target), alive[0] if alive else None)
        speed, shielding, strafing = 0.0, False, False
        if verb != "shoot":
            self.drawn = 0.0
        if self.hidden and verb not in ("unhide", "eat", "wait"):
            verb = "wait"                          # sealed in: can only eat, wait or dig out

        sprint_ready = self.sprint_ready
        self.sprint_ready = verb != "combo"        # W-tap: you have to re-sprint after a sprint hit
        if self.digging:
            self.digging -= 1
            if self.digging == 0:
                self.hidden = TICK
        elif verb == "combo" and tgt and tgt.dist <= REACH and self._reachable(tgt):
            # sprint hit: normal damage plus knockback, so it has to walk back in instead of hitting
            self._damage(tgt, WEAPONS[self.weapon])
            if sprint_ready and tgt.kind not in ("warden", "iron_golem", "ravager"):
                tgt.dist += 2.5
        elif verb in ("attack", "crit") and tgt and tgt.dist <= REACH and self._reachable(tgt):
            dmg = WEAPONS[self.weapon] * (1.5 if verb == "crit" else 1.0)
            if verb == "crit" and r.random() < 0.5:
                dmg = 0.0
            if tgt.kind == "magma_cube":
                dmg *= 0.7
            self._damage(tgt, dmg)
        elif verb in ("attack", "crit", "approach", "combo") and tgt:
            speed = -4.3
        elif verb == "retreat":
            speed = 4.3
        elif verb == "flee":
            speed = 5.6
        elif verb == "strafe":
            strafing = True
        elif verb == "shield" and self.shield:
            shielding, speed = True, 0.6
        elif verb == "shoot" and self.bow and self.arrows > 0 and tgt:
            self.drawn += TICK
            if self.drawn >= 1.0:
                self.arrows -= 1
                self.drawn = 0.0
                aim = max(0.2, 0.95 - tgt.dist * 0.03) * (0.7 if tgt.kind == "pvp_bot" else 1.0)
                if tgt.s["arrows"] and r.random() < aim:
                    self._damage(tgt, 9)
                elif not tgt.s["arrows"]:
                    tgt.angry = True               # endermen dodge arrows and come for you
        elif verb == "eat" and self.food > 0:
            self.food -= 1
            self.full = True
            self.hp = min(20, self.hp + (6 if self.scenario == "duel" else 4))   # duel: golden apples
            self.time += 1.1
        elif verb == "hide" and self.dig and not self.hidden:
            self.digging = 3
        elif verb == "unhide" and self.hidden:
            self.hidden = 0.0

        if "slow" in self.effects:
            speed *= 0.5
        for m in self.alive():
            if m.s["style"] != "flyer":
                m.dist = max(0.5, m.dist + speed * TICK)

        for m in self.alive():
            if m.angry:
                self._mob_turn(m, shielding, strafing)

        # effects and regeneration
        for e in list(self.effects):
            self.effects[e] -= TICK
            if e == "poison":
                self.hp = max(1.0, self.hp - 0.5)
            elif e == "wither":
                self.hp -= 0.25
            if self.effects[e] <= 0:
                del self.effects[e]
        if self.full and self.hp < 20:
            self.regen += TICK
            if self.regen >= 4:
                self.regen = 0.0
                self.hp = min(20, self.hp + 1)

        if self.hidden:
            self.hidden += TICK
            if self.hidden > 12:                   # they lose interest and wander off
                for m in self.threats():
                    if m.kind != "warden":
                        m.angry = False
        self.time += TICK
        if self.threats() and min(m.dist for m in self.threats()) > 24:
            self.escaped = True

    def _reachable(self, m):
        if m.s["style"] == "flyer":
            return False
        if m.s["style"] == "swoop":
            return m.swoop_t <= TICK               # only while it swoops down
        return True

    def _damage(self, m, dmg):
        if m.kind == "pvp_bot":
            if m.shielding and self.rng.random() < 0.9:
                return                             # blocked by its shield
            dmg = armor_cut(dmg, ARMOR["iron"])
        m.hp -= dmg
        m.angry = True
        if m.kind == "zombified_piglin":
            for o in self.alive():
                if o.kind == "zombified_piglin":
                    o.angry = True
        if m.hp <= 0 and m.split:
            for _ in range(2):
                self.mobs.append(Mob(m.kind, m.dist + 0.5, self.rng, hp=4))
                self.mobs[-1].s = dict(self.mobs[-1].s, dmg=self.mobs[-1].s["dmg"] / 2)

    def _mob_turn(self, m, shielding, strafing):
        s, r = m.s, self.rng
        m.cool = max(0.0, m.cool - TICK)
        sealed = bool(self.hidden)
        if s["style"] == "bot":
            self._bot_turn(m, shielding, strafing)
            return
        if m.kind == "warden" and m.dist > s["reach"] and m.cool == 0 and m.dist <= 15:
            m.cool = 5.0                           # sonic boom: through shields and walls
            self.hp -= 10
            return
        if s["style"] == "explode":
            if m.fuse is None and m.dist <= s["reach"]:
                m.fuse = 1.5
            elif m.fuse is not None:
                if m.dist > 7:
                    m.fuse = None
                else:
                    m.fuse -= TICK
                    if m.fuse <= 0:
                        blast = s["dmg"] * max(0.0, 1 - m.dist / 6)
                        if sealed:
                            blast *= 0.3
                        self._hurt(blast, shielding, True)
                        m.hp = 0
                        return
            if m.fuse is None and not sealed:
                m.dist = max(1.0, m.dist - s["speed"] * TICK)
            return
        if s["style"] in ("ranged", "flyer"):
            lo, hi = s["keep"]
            if m.dist < lo:
                m.dist += s["speed"] * TICK * 0.5
            elif m.dist > hi:
                m.dist -= s["speed"] * TICK
            if m.cool == 0 and m.dist < 20 and not sealed:
                m.cool = s["cd"]
                hit = 0.75 - (0.45 if strafing else 0) - m.dist * 0.02
                if r.random() < hit:
                    self._hurt(s["dmg"], shielding, s["blockable"], s["effect"])
            return
        if s["style"] == "swoop":
            m.swoop_t -= TICK
            m.dist = 1.0 if m.swoop_t <= TICK else 8.0
            if m.swoop_t <= 0:
                m.swoop_t = s["cd"]
                if not sealed:
                    self._hurt(s["dmg"], shielding, True)
            return
        # melee
        if m.dist > s["reach"]:
            m.dist = max(1.0, m.dist - s["speed"] * TICK)
        elif m.cool == 0 and not sealed:
            m.cool = s["cd"]
            self._hurt(s["dmg"], shielding, s["blockable"], s["effect"])

    def _bot_turn(self, m, shielding, strafing):
        """The hard-coded PvP opponent: rules an experienced player follows."""
        r = self.rng
        m.shielding = False
        if m.hp <= 8 and m.apples:                 # golden apple
            m.apples -= 1
            m.hp = min(20, m.hp + 6)
            m.drawn = 0.0
            return
        if self.drawn > 0 and m.dist > REACH:      # you're drawing a bow: block and walk in
            m.shielding = True
            m.dist = max(1.0, m.dist - 1.3 * TICK)
            return
        if m.dist > 7 and m.arrows:                # trade arrows from range
            m.drawn += TICK
            if m.drawn >= 1.0:
                m.drawn, m.arrows = 0.0, m.arrows - 1
                if r.random() < (0.35 if strafing else 0.7) - m.dist * 0.02:
                    self._hurt(9, shielding, True)
            return
        m.drawn = 0.0
        if m.dist > REACH:                         # sprint in, strafing
            m.dist = max(1.0, m.dist - 5.6 * TICK)
            return
        if shielding and r.random() < 0.5:         # you're blocking: wait it out behind its own shield
            m.shielding = True
            return
        dmg = 8 * (1.5 if r.random() < 0.2 else 1.0)   # lucky crits: slightly out-damages plain swings
        hp_before = self.hp
        self._hurt(dmg, shielding, True)
        # it W-taps too: every other hit is a sprint hit that knocks you back
        if m.sprint_ready and self.hp < hp_before:
            m.dist += 2.5
        m.sprint_ready = not m.sprint_ready

    def _hurt(self, dmg, shielding, blockable, effect=None):
        if shielding and blockable and self.rng.random() < 0.9:
            return
        self.hp -= armor_cut(dmg, ARMOR[self.armor])
        if effect == "hunger":
            self.full = False
        elif effect:
            self.effects[effect] = {"poison": 3.0, "wither": 5.0, "slow": 3.0}[effect]


# ---- fight math and mob knowledge the model also learns

def hits_to_kill(weapon, mob, crit=False):
    return math.ceil(MOBS[mob]["hp"] / (WEAPONS[weapon] * (1.5 if crit else 1)))


def danger(f):
    """Rough estimate of the damage we'd take killing every threat with melee."""
    total, t = 0.0, 0.0
    for m in sorted(f.threats(), key=lambda m: m.dist):
        s = m.s
        if m.kind == "warden":
            return 999.0
        kill_time = math.ceil(m.hp / WEAPONS[f.weapon]) * TICK
        approach = max(0.0, m.dist - REACH) / 4.3
        if s["style"] == "flyer" and not f.bow:
            return 999.0                          # can't reach it at all
        t += kill_time + approach
        per_hit = armor_cut(s["dmg"], ARMOR[f.armor])
        if s["style"] == "explode":
            total += 0 if f.shield else armor_cut(8, ARMOR[f.armor])
        elif s["style"] in ("ranged", "flyer"):
            total += per_hit * 0.5 * (t / s["cd"])
        else:
            # kiting strings melee mobs out, so each one mostly hits only while we fight it
            total += per_hit * ((kill_time + 0.5) / s["cd"])
    return total
