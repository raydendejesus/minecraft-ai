"""Player vs player combat simulator for the PvP model. Only player fights: no mobs, no hordes.

Two players, the same rules for both, Bedrock Edition. Numbers come from the Minecraft Wiki
(checked 2026-11-04); "estimate" marks the few the wiki doesn't give.

  time        one tick = 0.25 s (5 game ticks). Both choose a move, then both moves happen at
              once: whoever is listed first gets no head start
  cooldown    none on Bedrock: you can swing every tick
  immunity    after taking damage you're immune for 0.5 s (10 game ticks). A BIGGER hit during
              that time deals only the difference (7 then 12 = 12 in total); a smaller one does
              nothing, and nothing knocks you back while you're immune
  reach       3 blocks, from the attacker's eyes to the NEAREST point of the target's hitbox
  hitbox      0.6 wide, 1.8 tall, eyes at 1.62. Sneaking (on Bedrock that's how you raise a
              shield): 1.5 tall, eyes at 1.27
  height      on hills the players stand at different heights. If they're a block above you,
              you reach the bottom of their box at eye level, but they must reach down to the top
              of your head along a slope (the hypotenuse), so they have to be closer than you
  damage      swords: iron 7, diamond 8, netherite 9. Axes: iron 6, diamond 7, netherite 8
              Sharpness (Bedrock): +1 / +2 / +3 / +5 / +6 for levels I-V
              Strength (Bedrock): damage x 1.3 + 1 per level (iron 7 -> 10.1); the wiki marks the
              Bedrock formula as unverified
  crit        attack while falling from a jump: x1.5 (on Bedrock applied after armor), harder to
              aim. Unlike Java, Bedrock lets a crit also be a sprint hit (sources disagree)
  knockback   normal hit about 1 block, sprint hit about 2.5 (estimates: the wiki gives no block
              distances). Attacking ends your sprint, so you let go of W and press it again
              (W-tap) before the next sprint hit. Netherite armor: 10% knockback resistance per
              piece, 40% for the set. Knockback in the air is the same as on the ground (Bedrock)
  armor       reduction = min(20, max(points / 5, points - 4 x damage / (toughness + 8))) / 25
              leather 7, chainmail 12, iron 15, diamond 20 (toughness 8), netherite 20 (toughness 12)
              Protection: 1 per level per piece, at most 20, each point blocks 4% more
  shield      Bedrock: raised by sneaking, so you walk at sneak speed. Takes 0.25 s to come up.
              Blocks melee and arrows from the front. Hitting a raised shield knocks the ATTACKER
              back (Bedrock only). An axe hit on a raised shield disables it for 5 s
  bow         a full draw (1 s) is a critical shot: 6 to 11 damage, about 9 on average
  golden apple  1.6 s to eat (you can still walk, slowly): 4 absorption (stacks up to 16 on
              Bedrock), regeneration II for 5 s (1 health every 1.25 s), 4 hunger, 9.6 saturation
  potions     splash healing II +8 health at once. Strength I and speed I (20% faster) last 3
              minutes, 1.6 s to drink
  ender pearl lands where thrown (simplified): next to them when thrown far, away from them when
              thrown close. 5 damage on landing, 1 s before the next one
  hunger      health comes back 1 per 4 s while hunger is 18+ or saturation is above 0, and each
              health healed costs 6 exhaustion. Attacking, taking damage and every block sprinted
              cost 0.1. Every 4 exhaustion takes 1 saturation, then 1 hunger. Sprinting needs
              hunger above 6
  speed       sprint 5.6 blocks/s, walk 4.3, sneak 1.3
  length      at most 120 s, then it's a draw
"""

import math
import random

TICK = 0.25
REACH = 3.0
IMMUNE = 0.5
HALF_WIDTH = 0.3
STAND, SNEAK = (1.62, 1.8), (1.27, 1.5)          # (eye height, hitbox height)
SWORD = {"iron": 7, "diamond": 8, "netherite": 9}
AXE = {"iron": 6, "diamond": 7, "netherite": 8}
SHARPNESS = [0, 1, 2, 3, 5, 6]
ARMOR = {"leather": (7, 0), "chainmail": (12, 0), "iron": (15, 0), "diamond": (20, 8), "netherite": (20, 12)}
SPRINT, WALK, SNEAK_SPEED = 5.6, 4.3, 1.3
KB_NORMAL, KB_SPRINT, KB_SHIELD = 1.0, 2.5, 1.0   # blocks (estimates)
MAX_TIME = 120.0

MOVES = ["hit", "crit", "combo", "axe", "in", "back", "strafe", "block", "bow",
         "gap", "heal", "strength", "speed", "pearl", "up", "down", "wait"]
SWINGS = ("hit", "crit", "combo", "axe")

# kits: both players get the same one, like a real duel. sharp / prot = enchantment levels
KITS = {
    "sword":    dict(weapon="diamond", armor="diamond"),
    "classic":  dict(weapon="iron", armor="iron", bow=8, gap=1),
    "uhc":      dict(weapon="diamond", armor="diamond", sharp=2, prot=2, shield=True, axe=True, bow=16, gap=3),
    "nodebuff": dict(weapon="diamond", armor="diamond", sharp=3, prot=2, heal=8, strength=2, speed=2, pearl=4),
    "axe":      dict(weapon="netherite", armor="netherite", shield=True, axe=True, gap=2),
    "archer":   dict(weapon="iron", armor="chainmail", bow=32, gap=2),
    "builduhc": dict(weapon="diamond", armor="iron", prot=1, shield=True, bow=20, gap=4, pearl=2),
    "mixed":    dict(weapon="netherite", armor="diamond", sharp=1, prot=1, shield=True, axe=True, bow=12,
                     gap=2, heal=3, strength=1, pearl=2),
}


def reach_gap(dist, dy, eye=STAND[0], height=STAND[1]):
    """Distance from the attacker's eyes to the nearest point of the target's hitbox. dist: flat
    distance between their centres. dy: how far the target's feet are above the attacker's feet.
    eye: the attacker's eye height. height: the target's hitbox height."""
    flat = max(0.0, dist - HALF_WIDTH)
    e = eye - dy                                       # attacker's eyes, measured from the target's feet
    up = 0.0 if 0.0 <= e <= height else (e - height if e > height else -e)
    return math.hypot(flat, up)


def armor_cut(dmg, armor, prot=0):
    points, tough = ARMOR[armor]
    cut = min(20.0, max(points / 5, points - 4 * dmg / (tough + 8))) / 25
    epf = min(20, 4 * prot)                            # Protection on all 4 pieces
    return dmg * (1 - cut) * (1 - epf / 25)


def strength_damage(dmg, level):
    return dmg * 1.3 ** level + (1.3 ** level - 1) / 0.3 if level else dmg


class Player:
    def __init__(self, kit):
        k = KITS[kit]
        self.weapon, self.armor = k["weapon"], k["armor"]
        self.sharp, self.prot = k.get("sharp", 0), k.get("prot", 0)
        self.shield, self.has_axe = k.get("shield", False), k.get("axe", False)
        self.arrows, self.gaps, self.heals = k.get("bow", 0), k.get("gap", 0), k.get("heal", 0)
        self.strength_pots, self.speed_pots, self.pearls = k.get("strength", 0), k.get("speed", 0), k.get("pearl", 0)
        self.hp, self.absorb = 20.0, 0.0
        self.food, self.saturation, self.exhaustion = 20, 5.0, 0.0
        self.y = 0                        # height of its feet, in blocks
        self.immune, self.last_dmg = 0.0, 0.0
        self.sprint_ready = True          # W-tapped: the next hit can be a sprint hit
        self.busy, self.busy_with = 0.0, None   # eating / drinking: seconds left
        self.drawn = 0.0                  # bow draw time
        self.shield_off = 0.0             # disabled by an axe
        self.block_held = 0.0             # how long the shield has been up (it needs 0.25 s)
        self.strafing = False
        self.strength = self.speed = self.regen = self.pearl_wait = 0.0   # seconds left
        self.regen_clock = self.natural_clock = 0.0
        self.last = []                    # last moves, what the other player can see

    def copy(self):
        c = Player.__new__(Player)
        c.__dict__ = dict(self.__dict__)
        c.last = list(self.last)
        return c

    def health(self):
        return self.hp + self.absorb

    def sneaking(self):
        return self.block_held > 0

    def shield_up(self):
        return self.block_held >= 0.25 and not self.shield_off

    def pose(self):
        return SNEAK if self.sneaking() else STAND

    def can_sprint(self):
        return self.food > 6

    def tire(self, amount):
        self.exhaustion += amount
        while self.exhaustion >= 4.0:
            self.exhaustion -= 4.0
            if self.saturation > 0:
                self.saturation = max(0.0, self.saturation - 1)
            else:
                self.food = max(0, self.food - 1)


class Duel:
    def __init__(self, kit=None, rng=None, start=None):
        self.rng = rng or random.Random()
        self.kit = kit or self.rng.choice(list(KITS))
        self.p = [Player(self.kit), Player(self.kit)]
        self.dist = start if start is not None else self.rng.uniform(6, 16)
        self.hilly = self.rng.random() < 0.5      # hills: blocks to step up on, so heights differ
        self.time = 0.0

    def copy(self, rng=None):
        d = Duel.__new__(Duel)
        d.rng = rng or random.Random()
        d.kit, d.dist, d.hilly, d.time = self.kit, self.dist, self.hilly, self.time
        d.p = [q.copy() for q in self.p]
        return d

    def dy(self, i):
        """How far the other player's feet are above player i's."""
        return self.p[1 - i].y - self.p[i].y

    def in_reach(self, i):
        me, foe = self.p[i], self.p[1 - i]
        return reach_gap(self.dist, self.dy(i), me.pose()[0], foe.pose()[1]) <= REACH

    def over(self):
        return self.p[0].hp <= 0 or self.p[1].hp <= 0 or self.time >= MAX_TIME

    def winner(self):
        """0 or 1, or None for a draw / still going."""
        if self.p[1].hp <= 0 < self.p[0].hp:
            return 0
        if self.p[0].hp <= 0 < self.p[1].hp:
            return 1
        return None

    # ---- what player i sees (the PvP model reads this)
    def state_text(self, i):
        me, foe = self.p[i], self.p[1 - i]
        sword = f"{me.weapon}_sword" + (f" sharp{me.sharp}" if me.sharp else "")
        bag = [sword] + (["axe"] if me.has_axe else []) \
            + ([f"shield{' off' if me.shield_off else ''}"] if me.shield else []) \
            + [f"{n} {getattr(me, a)}" for n, a in (("bow", "arrows"), ("gap", "gaps"), ("heal", "heals"),
                                                    ("str", "strength_pots"), ("spd", "speed_pots"),
                                                    ("pearl", "pearls")) if getattr(me, a)]
        status = f"hp {me.hp:.0f}" + (f" abs {me.absorb:.0f}" if me.absorb else "") + f" food {me.food}"
        status += "".join(f" {n}" for n, on in (("sprint", me.sprint_ready and me.can_sprint()),
                                               ("immune", me.immune > 0), ("str", me.strength > 0),
                                               ("spd", me.speed > 0), ("regen", me.regen > 0),
                                               ("blocking", me.shield_up()), ("raising", me.sneaking() and not me.shield_up()),
                                               ("pearlwait", me.pearl_wait > 0)) if on)
        if me.busy:
            status += f" {me.busy_with}"
        if me.drawn:
            status += f" drawn {me.drawn:.2f}"
        dy = self.dy(i)
        height = f" up {dy}" if dy > 0 else f" down {-dy}" if dy < 0 else ""
        seen = f"foe {self.dist:.1f}{height} hp {foe.hp:.0f}" + (f" abs {foe.absorb:.0f}" if foe.absorb else "")
        seen += f" {foe.armor}" + (" shield" if foe.shield and not foe.shield_off else "")
        seen += "".join(f" {n}" for n, on in (("blocking", foe.shield_up()), ("sneaking", foe.sneaking() and not foe.shield_up()),
                                             ("drawing", foe.drawn > 0), ("immune", foe.immune > 0),
                                             ("str", foe.strength > 0), ("spd", foe.speed > 0),
                                             (foe.busy_with or "", foe.busy > 0)) if on)
        did = " ".join(foe.last[-3:]) or "nothing"
        ground = " | hills" if self.hilly else ""
        return f"{status} | {' '.join(bag)} | {seen} | foe did {did}{ground}"

    # ---- one tick
    def step(self, a0, a1):
        moves = [self._legal(0, a0), self._legal(1, a1)]
        r = self.rng
        for q, m in zip(self.p, moves):
            q.block_held = q.block_held + TICK if m == "block" else 0.0
            q.strafing = m == "strafe"
            if m != "bow":
                q.drawn = 0.0
            q.last = (q.last + [m])[-4:]
        # movement for both, then attacks for both, then knockback
        reach = [self.in_reach(0), self.in_reach(1)]
        for i, m in enumerate(moves):
            q = self.p[i]
            fast = 1.2 if q.speed > 0 else 1.0
            run = SPRINT if q.can_sprint() else WALK
            if q.busy:
                if m == "back":
                    self.dist += SNEAK_SPEED * TICK          # eating / drinking: you can only creep
            elif m == "in" or (m in SWINGS and not reach[i]):
                self.dist -= run * fast * TICK
                if run == SPRINT:
                    q.tire(0.1 * SPRINT * fast * TICK)
            elif m == "back":
                self.dist += WALK * fast * TICK
            elif m in ("up", "down"):
                if r.random() < 0.7:                          # a block to step on / off is close enough
                    q.y = max(0, min(2, q.y + (1 if m == "up" else -1)))
            if self.hilly and m in ("in", "back") and r.random() < 0.08:
                q.y = max(0, min(2, q.y + r.choice((-1, 1))))     # the ground isn't flat
        self.dist = max(HALF_WIDTH * 2, self.dist)
        reach = [self.in_reach(0), self.in_reach(1)]
        self.kb = 0.0
        for i, m in enumerate(moves):
            self._act(i, m, r, reach[i])
        self.dist = min(40.0, self.dist + self.kb)
        for q in self.p:
            self._tick_effects(q)
        self.time += TICK

    def _legal(self, i, m):
        q = self.p[i]
        if q.busy:
            return m if m == "back" else "wait"            # still eating or drinking
        ok = {"axe": q.has_axe, "block": q.shield and not q.shield_off, "bow": q.arrows > 0,
              "gap": q.gaps > 0, "heal": q.heals > 0, "strength": q.strength_pots > 0,
              "speed": q.speed_pots > 0, "pearl": q.pearls > 0 and q.pearl_wait <= 0,
              "up": self.hilly and q.y < 2, "down": self.hilly and q.y > 0}
        return m if ok.get(m, m in MOVES) else "wait"

    def _act(self, i, m, r, reach):
        me, foe = self.p[i], self.p[1 - i]
        swing = m in SWINGS
        if not swing or not reach:
            me.sprint_ready = True                  # let go of the attack / sprinting in: W-tapped
        if swing and reach:
            aim = 0.85 * (0.7 if foe.strafing else 1.0) * (0.75 if m == "crit" else 1.0)
            sprint = m in ("combo", "crit") and me.sprint_ready and me.can_sprint()
            if m in ("combo", "crit"):
                me.sprint_ready = False             # the hit ends the sprint: W-tap before the next
            if r.random() > aim:
                return                              # missed
            if foe.shield_up():
                if m == "axe":
                    foe.shield_off, foe.block_held = 5.0, 0.0     # shield knocked down, no damage
                self.kb += KB_SHIELD                 # Bedrock: hitting a shield knocks YOU back
                return
            base = (AXE if m == "axe" else SWORD)[me.weapon] + SHARPNESS[me.sharp]
            base = strength_damage(base, 1 if me.strength > 0 else 0)
            dmg = armor_cut(base, foe.armor, foe.prot) * (1.5 if m == "crit" else 1.0)
            if not self._damage(foe, dmg):
                return                              # swung into hit immunity
            me.tire(0.1)
            kb = KB_SPRINT if sprint else KB_NORMAL
            if foe.armor == "netherite":
                kb *= 0.6                           # 40% knockback resistance
            self.kb += kb
        elif m == "bow":
            me.drawn += TICK
            if me.drawn >= 1.0:
                me.drawn, me.arrows = 0.0, me.arrows - 1
                aim = max(0.15, 0.9 - self.dist * 0.03) * (0.6 if foe.strafing else 1.0)
                if r.random() < aim and not foe.shield_up():
                    self._damage(foe, armor_cut(r.randint(6, 11), foe.armor, foe.prot))
        elif m == "gap":
            me.gaps -= 1
            me.busy, me.busy_with = 1.6, "eating"
        elif m in ("strength", "speed"):
            setattr(me, f"{m}_pots", getattr(me, f"{m}_pots") - 1)
            me.busy, me.busy_with = 1.6, f"drinking {m}"
        elif m == "heal":
            me.heals -= 1
            if r.random() < 0.92:                   # a splash thrown on the run can miss
                me.hp = min(20.0, me.hp + 8)
        elif m == "pearl":
            me.pearls -= 1
            me.pearl_wait = 1.0
            self.dist = 2.0 if self.dist > 8 else self.dist + 14
            self._hurt(me, 5.0)                     # landing damage: fall damage, armor doesn't help

    def _damage(self, q, dmg):
        """Hit immunity: a bigger hit while immune deals only the difference. True if it hurt
        and isn't an immune hit (so it knocks back)."""
        if q.immune > 0:
            if dmg > q.last_dmg:
                self._hurt(q, dmg - q.last_dmg)
                q.last_dmg = dmg
            return False
        self._hurt(q, dmg)
        q.immune, q.last_dmg = IMMUNE, dmg
        return True

    def _hurt(self, q, dmg):
        take = min(q.absorb, dmg)
        q.absorb -= take
        q.hp -= dmg - take
        q.tire(0.1)

    def _tick_effects(self, q):
        for a in ("immune", "shield_off", "strength", "speed", "pearl_wait"):
            setattr(q, a, max(0.0, getattr(q, a) - TICK))
        if q.busy:
            q.busy = max(0.0, q.busy - TICK)
            if not q.busy:
                if q.busy_with == "eating":
                    q.absorb = min(16.0, q.absorb + 4.0)      # Bedrock: stacks up to 16
                    q.regen = 5.0
                    q.food, q.saturation = min(20, q.food + 4), min(20.0, q.saturation + 9.6)
                elif q.busy_with == "drinking strength":
                    q.strength = 180.0
                elif q.busy_with == "drinking speed":
                    q.speed = 180.0
                q.busy_with = None
        if q.regen > 0:
            q.regen = max(0.0, q.regen - TICK)
            q.regen_clock += TICK
            if q.regen_clock >= 1.25:
                q.regen_clock, q.hp = 0.0, min(20.0, q.hp + 1)
        q.natural_clock += TICK
        if q.natural_clock >= 4.0:
            q.natural_clock = 0.0
            if 0 < q.hp < 20 and (q.food >= 18 or q.saturation > 0):
                q.hp = min(20.0, q.hp + 1)
                q.tire(6.0)


# ---- opponents: eleven play styles, each at its own skill level. skill = how often it does what
# its style says instead of something careless
def _close(d, i):
    return d.in_reach(i)


def style_move(style, d, i, r):
    me, foe = d.p[i], d.p[1 - i]
    if me.busy:
        return "back" if _close(d, i) else "wait"
    low = me.health() <= 8
    shield_ok = me.shield and not me.shield_off
    if low and me.heals and style in ("potter", "mixed", "combo", "critter", "expert"):
        return "heal"
    if low and me.gaps and not _close(d, i):
        return "gap"
    if style == "rusher":
        return "hit" if _close(d, i) else "in"
    if style == "combo":                           # W-tap combos
        if not _close(d, i):
            return "in"
        return "combo" if me.sprint_ready else "strafe"
    if style == "critter":
        return ("crit" if foe.immune <= TICK else "strafe") if _close(d, i) else "in"
    if style == "turtle":                          # shield up, counter, axe your shield
        if shield_ok and (foe.drawn > 0 or (_close(d, i) and r.random() < 0.6)):
            return "block"
        if _close(d, i):
            return "axe" if foe.shield_up() and me.has_axe else "hit"
        return "in" if d.dist > 5 or not shield_ok else "block"
    if style == "archer":                          # keep away and shoot
        if me.arrows and d.dist < 8:
            return "pearl" if me.pearls and d.dist < 3 else "back"
        if me.arrows:
            return "bow"
        return "hit" if _close(d, i) else "in"
    if style == "potter":                          # aggressive, heals early and often
        if me.hp <= 12 and me.heals:
            return "heal"
        if me.strength_pots and me.strength <= 0 and not _close(d, i):
            return "strength"
        return "combo" if _close(d, i) and me.sprint_ready else "hit" if _close(d, i) else "in"
    if style == "strafer":                         # circles you, swings when you're open
        if not _close(d, i):
            return "in"
        return "hit" if foe.immune <= 0 and r.random() < 0.5 else "strafe"
    if style == "pearler":
        if me.pearls and d.dist > 9:
            return "pearl"
        return "combo" if _close(d, i) and me.sprint_ready else "hit" if _close(d, i) else "in"
    if style == "noob":
        return r.choice(["hit", "hit", "in", "back", "wait", "block", "bow", "crit"])
    if style == "highground":                      # climbs up whenever it can, then swings down
        if d.hilly and me.y < 2 and d.dist < 6:
            return "up"
        return "combo" if _close(d, i) and me.sprint_ready else "hit" if _close(d, i) else "in"
    if style == "mixed":                           # switches plan every few seconds
        sub = ["combo", "critter", "turtle", "strafer", "potter"][int(d.time // 6) % 5]
        return style_move(sub, d, i, r)
    if style == "expert":                          # the teacher's starting point: a solid all-rounder
        if foe.drawn > 0 and not _close(d, i) and shield_ok:
            return "block"
        if me.strength_pots and me.strength <= 0 and d.dist > 6:
            return "strength"
        if me.speed_pots and me.speed <= 0 and d.dist > 6:
            return "speed"
        if me.pearls and d.dist > 12:
            return "pearl"
        if d.hilly and me.y > foe.y and d.dist < 5:
            return "down"                          # higher up, your reach is worse than theirs
        if not _close(d, i):
            return "bow" if me.arrows and d.dist > 9 and not foe.shield_up() else "in"
        if foe.shield_up():
            return "axe" if me.has_axe else "strafe"   # hitting a shield only knocks you back
        if foe.immune > TICK:
            return "strafe"                        # don't swing into immunity
        return "combo" if me.sprint_ready else "hit"
    raise ValueError(style)


STYLES = ["rusher", "combo", "critter", "turtle", "archer", "potter", "strafer", "pearler", "noob",
          "mixed", "highground"]


def bot(style, skill):
    def move(d, i, r):
        m = style_move(style, d, i, r)
        if r.random() > skill:                     # a careless moment
            m = r.choice(["hit", "in", "back", "wait", "strafe"])
        return m
    move.style, move.skill = style, skill
    return move


def reach_table():
    """How far away (flat distance between centres) a player can hit another, for the lessons."""
    rows = []
    for dy in (-2, -1, 0, 1, 2):
        for me_pose, target_pose in ((STAND, STAND), (STAND, SNEAK), (SNEAK, STAND)):
            far = next(x / 100 for x in range(700, 0, -1)
                       if reach_gap(x / 100, dy, me_pose[0], target_pose[1]) <= REACH)
            rows.append((dy, me_pose is SNEAK, target_pose is SNEAK, far))
    return rows
