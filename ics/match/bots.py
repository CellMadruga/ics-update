"""Bot champions' brains (docs/re-notes/bot-champions.md 2 / 3.3).

The data gives the triggers and choices only (C, units-and-ai.md 5.1): the levelling script 0x340007E2 (ranks by the
loadout's skill_order), the shopping node 0x10000186 (the loadout's recommended artifacts in order) and the retarget
interval 0.5 - 0.8 s (0x3A000026). The decisions themselves (lane, push, fight, retreat) are server code, here:

- lane: [ics] bot_lanes {map key: [lane per slot]}, else the map's lanes by slot (5v5: north, north, mid, south, south)
- push: walk the lane behind the most advanced allied minion of the lane, else wait by the farthest allied turret
- fight: within [ics] bot_sight m an enemy champion weaker than itself (or one that hit an ally), else the lowest-health
  minion, else a structure only while an allied minion is near it (tower rule); skills by Skill.targeting
- retreat: health below [ics] bot_retreat_health, or under an enemy turret with no allied minion: back to base, where the
  base aura heals; it shops there and goes back at full health
- evade (2026-10-28 15:00, test-2026-10-28-1439-sweep.md S6): an enemy turret shoots the bot -> it walks back along its
  lane out of that turret's range and stays out 2 s ([ics] bot_turret_aggro_retreat); it chases an enemy champion under
  an enemy turret only at [ics] bot_dive_health or more
- shop (2026-10-30, tester report 15:30; docs/re-notes/bot-shop-towers-end.md 1): only inside its base aura (the original
  script 0x340007E2 shops only while HasFlagAttribute 0x10000A23), spending as much as it can along its loadout's
  recommended list in order, saving for the first step it cannot pay; it goes home to shop when it can pay
  [ics] bot_shop_recall_value credits of purchases
- towers (same report, 2): [ics] bot_tower_awareness - no minion / structure whose attack point an enemy shooter covers
  unless the shooter is busy with the bot's minions (bot_tower_min_tanks of them in range); an enemy champion there only
  for a near-certain kill; a bot standing in an unsafe range walks out before it is targeted
- tower tactics (2026-10-30, tester report 18:12; bot-shop-towers-end.md 4): [ics] bot_tower_tactics - its minions hold
  an enemy shooter while it is not on the bot, the bot hit no champion in the last 2 s and its minions in range can take
  another shot (holds); then the bot sieges that structure, leaves the moment the shooter turns on it and comes back
  when the shooter is on a minion again; a champion near a shooter only from out of its range, in a timed short trade
  (bot_trade_*) or for a near-certain kill; near a shooter it re-decides every bot_tower_react s
- match over (same report, 3): BotManager.freeze stops every bot ([ics] match_end_freeze_combat)
"""
import math
import random
import time
from types import SimpleNamespace

from .. import messages as M
from ..shop import CAN_BUY, TOO_EXPENSIVE, Shop
from ..world import STAT_ATTACK_DAMAGE, STAT_ATTACK_SPEED
from . import maps

UNIT_TARGET = {9, 14}                       # cast on an entity (tools/champion_check.py, C table)
POINT_TARGET = {1, 10, 11, 13, 16}          # cast at a point
SELF_TARGET = {5, 7}                        # no target: around the caster
SKILL_ORDER = (4, 1, 2, 3, 7, 8)            # which skill a bot tries first (R, Q, W, E, D, F)
LANES_5V5 = ("north", "north", "mid", "south", "south")
TOWERS = ("turret", "core_turret", "inner_turret", "foundry")    # the enemy shooters a bot keeps out of
EVADE_SECONDS = 2.0                         # S6: out of a turret's range until it has not targeted the bot this long


class BotBrain:
    def __init__(self, manager, ent, slot):
        self.mg, self.ent, self.slot = manager, ent, slot
        m = manager.m
        self.lane = manager.lane_for(ent.team, slot)
        self.route = maps.lane_path(m.map, self.lane, ent.team) if self.lane else []
        self.state = "base"                 # base -> push <-> fight -> retreat -> base
        self.next_decision = 0.0
        self.goal = None                    # the point it walks to now
        self.target = None
        self.bought_at = -1e9

    # ---- helpers ---------------------------------------------------------------------------------------------------
    @property
    def w(self):
        return self.mg.m.world

    def share(self):
        e = self.ent
        return (e.health or 0) / e.max_health if e.max_health else 1.0

    def home(self):
        start = maps.spawn_point(self.mg.m.encounter, self.ent.team, self.slot)
        return [start[4], start[5], start[6]] if start else list(self.ent.pos)

    def walk(self, point):
        """Walk to a point; a new path only when the goal moved more than 2 m (no re-plan every decision)."""
        if point is None:
            return
        p = [point[0], point[1], point[2] if len(point) > 2 else self.ent.pos[2]]
        if self.goal is not None and math.hypot(p[0] - self.goal[0], p[1] - self.goal[1]) < 2.0 and \
                (self.ent.dest is not None or self.ent.distance_to(p) < 1.0):
            return
        self.goal = p
        if self.ent.distance_to(p) < 0.8:
            return
        self.ent.attack_target = None
        if not self.w.walk_to(self.ent, p):
            # 2026-10-25 16:12 (tester: bots stay stuck somewhere): no straight line through the walls; the nearest
            # walkable point instead (else stay)
            nav = self.w.nav
            near = nav.nearest(p[0], p[1], max_r=6.0) if nav is not None else None
            if near is None or not self.w.walk_to(self.ent, [near[0], near[1], p[2]]):
                self.goal = None

    def unstick(self, now):
        """2026-10-25 16:12 (tester: bots stay stuck without moving): a bot that wants to go somewhere but has moved
        less than 0.5 m in [ics] bot_stuck_seconds gets a fresh path through a walkable point beside it."""
        e = self.ent
        last = getattr(self, "_moved", None)
        if last is None or math.hypot(e.pos[0] - last[0][0], e.pos[1] - last[0][1]) > 0.5:
            self._moved = (list(e.pos), now)
            return
        if self.goal is None or e.distance_to(self.goal) < 2.0 or e.attack_target is not None:
            self._moved = (list(e.pos), now)
            return
        if now - last[1] < float(self.mg.ic.get("bot_stuck_seconds", 3.0)):
            return
        self._moved = (list(e.pos), now)
        nav = self.w.nav
        a = random.uniform(0, 2 * math.pi)
        side = nav.nearest(e.pos[0] + 3 * math.cos(a), e.pos[1] + 3 * math.sin(a), max_r=4.0) if nav else None
        goal, self.goal = self.goal, None
        self.mg.m.log(f"bot {e.name}: stuck at ({e.pos[0]:.1f}, {e.pos[1]:.1f}), re-routing")
        if side is not None:
            self.w.walk_to(e, [side[0], side[1], e.pos[2]])
            e.path = (e.path or []) + [list(goal)]

    def progress(self, pos):
        """How far along its lane route (index of the nearest route point) a position is."""
        if not self.route:
            return 0
        return min(range(len(self.route)), key=lambda i: math.hypot(self.route[i][0] - pos[0], self.route[i][1] - pos[1]))

    # ---- what is around -------------------------------------------------------------------------------------------
    def hostile(self, e):
        return e is not None and e.alive and e.health is not None and e.team and e.team != self.ent.team

    def enemy_champions(self, radius):
        m = self.mg.m
        return [c for c in m.champions() if c is not self.ent and self.hostile(c) and m.visible_to(c, self.ent)
                and self.ent.distance_to(c) <= radius]

    def units(self, radius, roles, mine=False):
        out = []
        for mu in list(self.mg.m.units.by_eid.values()):
            e = mu.ent
            if mu.role not in roles or not e.alive or e.health is None:
                continue
            if (e.team == self.ent.team) != mine or (not mine and not self.hostile(e)):
                continue
            if self.ent.distance_to(e) <= radius:
                out.append(mu)
        return out

    def turret_danger(self, pos, minion_cover=True):
        """An enemy shooter (turret / core turret / foundry) whose range covers pos with no allied minion near it
        (minion_cover=False: any enemy shooter whose range covers pos)."""
        units = self.mg.m.units
        for mu in units.by_eid.values():
            if mu.role not in TOWERS or not mu.ent.alive:
                continue
            if mu.team == self.ent.team or not mu.team:
                continue
            if math.hypot(mu.ent.pos[0] - pos[0], mu.ent.pos[1] - pos[1]) > mu.range + 1.5:
                continue
            if not minion_cover:
                return mu
            cover = [o for o in units.by_eid.values() if o.role == "minion" and o.team == self.ent.team and o.ent.alive
                     and o.ent.distance_to(mu.ent) <= mu.range + 0.5]
            if not cover:
                return mu
        return None

    def turret_aggro(self):
        """S6 (test-2026-10-28-1439-sweep.md): an enemy shooter whose current target is this bot, within its range +
        1.5 m (the bots.py docstring's rule; BotBrain.decide never looked at its own position before)."""
        e = self.ent
        for mu in self.mg.m.units.by_eid.values():
            if mu.role not in TOWERS or not mu.ent.alive or mu.team == e.team or not mu.team:
                continue
            if mu.target is e and e.distance_to(mu.ent) <= mu.range + 1.5:
                return mu
        return None

    def evade_point(self, shooter):
        """Back along its own lane to the first route point out of the shooter's range (+ 3 m), else home."""
        e = self.ent
        safe = shooter.range + 3.0
        if self.route:
            for j in range(self.progress(e.pos), -1, -1):
                p = self.route[j]
                if math.hypot(p[0] - shooter.ent.pos[0], p[1] - shooter.ent.pos[1]) > safe:
                    return [p[0], p[1], e.pos[2]]
        return self.home()

    def evade(self, now):
        """2026-10-28 15:00 (tester report; test-2026-10-28-1439-sweep.md S6: all four bot deaths under GL's turret, 5-7
        shots each, the only exit was bot_retreat_health 0.3 when one shot is ~15 % of its health): a bot an enemy
        turret targets drops its target and walks out of that turret's range, and stays out until no turret has
        targeted it for EVADE_SECONDS ([ics] bot_turret_aggro_retreat). True = this decision is taken."""
        if not self.mg.ic.get("bot_turret_aggro_retreat", True):
            return False
        e = self.ent
        shooter = self.turret_aggro()
        if shooter is not None:
            if self.state != "evade":
                self.mg.m.log(f"bot {e.name}: backs off from {shooter.ent.name} (it targets the bot, "
                              f"{self.share():.0%} health)")
            self.state, self.target = "evade", None
            self.evade_from, self.evade_until = shooter, now + EVADE_SECONDS
        if self.state != "evade":
            return False
        src = getattr(self, "evade_from", None)
        if now >= getattr(self, "evade_until", 0.0) or src is None or not src.ent.alive:
            self.state, self.evade_from = "push", None
            return False
        if self.tactics() and self.holds(src):
            # 2026-10-30 (tester report 18:12): the shooter dropped the bot and is on its minions again: back in now
            self.mg.m.log(f"bot {e.name}: {src.ent.name} is on its minions again, goes back in")
            self.state, self.evade_from = "push", None
            return False
        e.attack_target = None
        self.walk(self.evade_point(src))
        return True

    # ---- tower awareness (2026-10-30, tester report 15:30: "they dive into the towers chasing minions") -------------
    def aware(self):
        return bool(self.mg.ic.get("bot_tower_awareness", True))

    def shooters_covering(self, pos):
        """The enemy shooters whose range + [ics] bot_tower_margin covers pos."""
        margin = float(self.mg.ic.get("bot_tower_margin", 1.5))
        out = []
        for mu in self.mg.m.units.by_eid.values():
            if mu.role not in TOWERS or not mu.ent.alive or not mu.team or mu.team == self.ent.team:
                continue
            if math.hypot(mu.ent.pos[0] - pos[0], mu.ent.pos[1] - pos[1]) <= mu.range + margin:
                out.append(mu)
        return out

    def tanks(self, shooter):
        """The bot's allied minions standing in the shooter's range."""
        return [o for o in self.mg.m.units.by_eid.values() if o.role == "minion" and o.team == self.ent.team
                and o.ent.alive and o.ent.distance_to(shooter.ent) <= shooter.range + 0.5]

    def unsafe(self, pos):
        """The first enemy shooter covering pos that the bot's minions do not hold, else None. With [ics]
        bot_tower_tactics: holds() (2026-10-30 18:12); else busy with one of them and at least bot_tower_min_tanks of
        them in its range (the 15:30 rule)."""
        if self.tactics():
            for mu in self.shooters_covering(pos):
                if not self.holds(mu):
                    return mu
            return None
        need = int(self.mg.ic.get("bot_tower_min_tanks", 2) or 1)
        for mu in self.shooters_covering(pos):
            if not (self.tower_busy(mu) and len(self.tanks(mu)) >= need):
                return mu
        return None

    # ---- tower tactics (2026-10-30, tester report 18:12: "now it doesn't go in to attack the tower"; play it as a
    # player: siege behind its minions, leave when targeted, come back when the tower is on a minion again, trade with
    # the champion only when it gets out before the tower shoots it; docs/re-notes/bot-shop-towers-end.md 4) ----------
    def tactics(self):
        return self.aware() and bool(self.mg.ic.get("bot_tower_tactics", True))

    def clock(self):
        """The clock the units' attack timers run on (Match.tick's now); the last decision's."""
        return getattr(self, "_now", None) if getattr(self, "_now", None) is not None else self.mg.m.t

    def aggressor_now(self):
        """The bot hit an enemy champion in the last [ics] match_call_for_help s: every enemy shooter whose reach holds
        the bot takes it at once (Units.think: champion_aggressor first; match_call_for_help_now re-thinks at the hit)."""
        m = self.mg.m
        rec = m.aggressors.get(self.ent.eid)
        return rec is not None and rec[1] != self.ent.team and \
            m.t - rec[0] <= float(self.mg.ic.get("match_call_for_help", 2.0))

    def holds(self, shooter):
        """The bot's minions hold this enemy shooter: it is not on the bot, the bot is no champion aggressor, at least
        [ics] bot_siege_min_tanks of the bot's minions stand in its range and their health together outlasts
        bot_siege_tank_shots of its shots. The shooter's own pick (Units.think) is the closest minion in reach before
        any champion, so a moment with no target (a minion just died, 0.1-0.6 s in the 18:12 traffic) still holds while
        tanks remain - the 15:30 rule (tower_busy) sent the bot out at each of those gaps."""
        ic = self.mg.ic
        if shooter.target is self.ent or self.aggressor_now():
            return False
        tanks = self.tanks(shooter)
        if len(tanks) < max(1, int(ic.get("bot_siege_min_tanks", 1) or 1)):
            return False
        shot = float((shooter.ent.stats or {}).get(STAT_ATTACK_DAMAGE, 0.0) or 0.0)
        need = shot * (float(ic.get("bot_siege_tank_shots", 1.0) or 0.0) + self.escape_shots(shooter))
        return not (need > 0 and sum(float(o.ent.health or 0.0) for o in tanks) <= need)

    def escape_shots(self, shooter):
        """The shooter's shots (its attack interval, Units.attack) while the bot walks out of the range it keeps a
        target in (range + 1 m) from the deeper of where it stands and where it would hit the shooter from (a melee
        bot sieges ~3 m from the turret's centre: ~2 s out; one turret shot was 36 % of a level-1 bot's health in the
        2026-10-30 lane check). [ics] bot_siege_escape false = 0."""
        if not self.mg.ic.get("bot_siege_escape", True):
            return 0.0
        e = self.ent
        sp = shooter.ent.pos
        ap = self.attack_point(shooter.ent)
        dist = min(math.hypot(e.pos[0] - sp[0], e.pos[1] - sp[1]), math.hypot(ap[0] - sp[0], ap[1] - sp[1]))
        depth = max(0.0, shooter.range + 1.0 - dist)
        speed = max(1.0, float(getattr(e, "move_speed", 4.5) or 4.5))
        rate = float((shooter.ent.stats or {}).get(STAT_ATTACK_SPEED) or 1.0) or 1.0
        return depth / speed * rate

    def siege_target(self, sight):
        """An enemy structure (a shooter first, then the nearest) the bot can hit from a point no enemy shooter it does
        not hold covers, within max(bot_sight, [ics] bot_siege_sight) m; the protection order decides what is
        attackable (Match.protected)."""
        m = self.mg.m
        radius = max(sight, float(self.mg.ic.get("bot_siege_sight", 14.0)))
        cands = [mu for mu in self.units(radius, ("turret", "core_turret", "inner_turret", "dampener", "core", "foundry"))
                 if m.units.attackable(mu.ent) and self.safe_to_hit(mu.ent)]
        if not cands:
            return None
        best = min(cands, key=lambda mu: (mu.role not in TOWERS, self.ent.distance_to(mu.ent)))
        return best.ent

    def champion_ok(self, champ):
        """An enemy champion the bot may hit near enemy shooters (tactics): a near-certain kill; or no enemy shooter
        covers the point it hits from (the shooter's aggro test is the hitter's distance, not the victim's); or a short
        trade - every shooter covering that point is held by its minions, the bot has [ics] bot_trade_health, the point
        is at most bot_trade_depth m inside the range the shooter keeps a target in (range + 1 m) and, when the hit
        lands now, the shooter's next shot is later than bot_trade_windup s + the walk out of that range."""
        if self.sure_kill(champ):
            return True
        ap = self.attack_point(champ)
        cover = self.shooters_covering(ap)
        if not cover:
            return True
        ic = self.mg.ic
        if self.share() < float(ic.get("bot_trade_health", 0.5)):
            return False
        lands = self.ent.distance_to(champ) <= self.reach(champ)
        speed = max(1.0, float(getattr(self.ent, "move_speed", 4.5) or 4.5))
        for mu in cover:
            if not self.holds(mu):
                return False
            depth = mu.range + 1.0 - math.hypot(ap[0] - mu.ent.pos[0], ap[1] - mu.ent.pos[1])
            if depth > float(ic.get("bot_trade_depth", 2.0)):
                return False
            if lands:
                escape = float(ic.get("bot_trade_windup", 0.4)) + max(0.0, depth) / speed
                if float(getattr(mu, "next_attack", 0.0) or 0.0) - self.clock() < escape:
                    return False
        return True

    def near_shooter(self):
        """Within an enemy shooter's range + bot_tower_margin + 3 m (decisions every [ics] bot_tower_react s there)."""
        e = self.ent
        margin = float(self.mg.ic.get("bot_tower_margin", 1.5)) + 3.0
        for mu in self.mg.m.units.by_eid.values():
            if mu.role in TOWERS and mu.ent.alive and mu.team and mu.team != e.team and \
                    e.distance_to(mu.ent) <= mu.range + margin:
                return True
        return False

    def reach(self, target=None):
        """The bot's basic-attack reach (World._attack_step's: skill range 18, else basic_attack_range, + radii)."""
        e, w = self.ent, self.w
        basic = e.kit.get(0)
        r = basic.stat(18, 1) if basic and basic.stat(18, 1) > 0 else float(w.ic.get("basic_attack_range", 2.0))
        if w.ic.get("attack_range_radii", True):
            r += w._attack_radius(e) + (w._attack_radius(target) if target is not None else 0.0)
        return r

    def attack_point(self, target):
        """Where the bot would stand to hit target with its basic attack: here when in reach, else on the line to it."""
        e = self.ent
        d = e.distance_to(target)
        r = self.reach(target)
        if d <= r or d <= 0.01:
            return list(e.pos)
        k = (d - r * 0.8) / d
        return [e.pos[0] + (target.pos[0] - e.pos[0]) * k, e.pos[1] + (target.pos[1] - e.pos[1]) * k, e.pos[2]]

    def safe_to_hit(self, target):
        """A minion / structure the bot can hit without standing in an enemy shooter's range its minions do not hold
        (a minion: neither the attack point nor the minion itself; a structure: the attack point)."""
        if self.unsafe(self.attack_point(target)) is not None:
            return False
        role = getattr(getattr(target, "match_unit", None), "role", None)
        return role in TOWERS or self.unsafe(target.pos) is None

    def sure_kill(self, champ):
        """An enemy champion near death that the bot, healthy enough, reaches at once (the only dive allowed)."""
        ic = self.mg.ic
        share = (champ.health or 0) / max(1.0, float(champ.max_health or 1))
        hits = float(ic.get("bot_dive_kill_hits", 2.0))
        dmg = float((self.ent.stats or {}).get(STAT_ATTACK_DAMAGE, 0.0) or 0.0)
        return (share <= float(ic.get("bot_dive_kill_share", 0.2)) and (champ.health or 0) <= dmg * hits
                and self.share() >= float(ic.get("bot_dive_health", 0.7))
                and self.ent.distance_to(champ) <= self.reach(champ) + 2.0)

    def dive_ok(self, champ):
        """An enemy champion the bot may take: no enemy shooter covers it or the bot's attack point, or every one that
        does is busy with the bot's minions and the bot has bot_dive_health, or the kill is near-certain."""
        covering = {id(mu): mu for mu in self.shooters_covering(champ.pos) + self.shooters_covering(self.attack_point(champ))}
        if not covering or self.sure_kill(champ):
            return True
        return all(self.tower_busy(mu) for mu in covering.values()) and             self.share() >= float(self.mg.ic.get("bot_dive_health", 0.7))

    def step_out(self, now):
        """Standing where an enemy shooter its minions do not hold covers the bot (not targeted yet): it walks out
        before the shooter fires. True = this decision is taken."""
        if not self.aware():
            return False
        cur = self.target
        if getattr(cur, "kind", None) == "champion" and cur.alive and self.sure_kill(cur):
            return False
        shooter = self.unsafe(self.ent.pos)
        if shooter is None:
            return False
        if self.state != "evade":
            self.mg.m.log(f"bot {self.ent.name}: steps out of {shooter.ent.name}'s range (its minions do not hold it)")
        self.state, self.target = "evade", None
        self.evade_from, self.evade_until = shooter, now + 0.5
        self.ent.attack_target = None
        self.walk(self.evade_point(shooter))
        return True

    # ---- decisions -------------------------------------------------------------------------------------------------
    def decide(self, now):
        e, ic = self.ent, self.mg.ic
        self._now = now
        if not e.alive:
            self.state, self.target, self.goal = "dead", None, None
            self.shop()                     # the original lets a dead champion shop (shop-items-inventory.md 3.2)
            return
        if self.state == "recall":
            if e.distance_to(self.home()) < 4.0:
                self.state = "base"
            elif now > getattr(self, "recall_until", 0.0):
                self.state = "retreat"      # the recall was cut (a hit, a Grab): walk home or recall again
            else:
                return                      # channelling (moving would cancel it)
        if self.state == "dead":
            self.state = "base"
        self.rank_up()
        retreat = float(ic.get("bot_retreat_health", 0.3))
        if self.state in ("push", "fight", "evade") and self.share() < retreat:
            self.state = "retreat"
            self.mg.m.log(f"bot {e.name}: retreats ({self.share():.0%} health)")
        if self.state in ("push", "fight", "evade") and self.evade(now):
            return                          # [ics] bot_turret_aggro_retreat (S6)
        if self.state in ("push", "fight") and self.step_out(now):
            return                          # [ics] bot_tower_awareness (2026-10-30)
        if self.state in ("push", "fight") and self.wants_to_shop(now):
            self.state, self.target = "retreat", None
            e.attack_target = None
        if self.state == "retreat":
            home = self.home()
            if e.distance_to(home) < 4.0:
                self.state = "base"
            elif (6 in e.kit and e.distance_to(home) > float(ic.get("bot_recall_distance", 25.0))
                  and not self.enemy_champions(10.0) and not self.units(8.0, ("minion", "camp"))
                  and e.ready_at.get(6, 0.0) <= time.time()):
                e.dest, e.path, e.speed, e.attack_target = None, [], 0.0, None
                if self.w.cast(e, 6, None, None):
                    self.state = "recall"
                    self.recall_until = now + float(ic.get("recall_seconds", 8.0)) + 2.0
                    self.mg.m.log(f"bot {e.name}: recalls")
                    return
                self.walk(home)
                return
            else:
                self.walk(home)
                return
        if self.state == "base":
            self.shop()
            self.base_left_at = now
            if self.share() >= 0.95 and (e.max_will is None or not e.max_will or e.will >= e.max_will * 0.9
                                          or getattr(e, "resource_vital", 5) != 5):
                self.state = "push"
            else:
                self.walk(self.home())
                return
        target = self.pick_target()
        if target is not None:
            self.note_chase(target)
            self.state, self.target = "fight", target
            self.fight(target, now)
            return
        self.state, self.target = "push", None
        self.walk(self.push_point())

    def pick_target(self):
        e, ic = self.ent, self.mg.ic
        sight = float(ic.get("bot_sight", 9.0))
        aggr = float(ic.get("bot_aggression", 1.0))
        m = self.mg.m
        tac = self.tactics()
        if tac:
            # 2026-10-30 (tester report 18:12): champion_ok - out of the shooters' range, a timed short trade while its
            # minions hold them, or a near-certain kill
            champs = [c for c in self.enemy_champions(sight) if self.champion_ok(c)]
        elif self.aware():
            # 2026-10-30 (tester report 15:30): an enemy champion an enemy shooter covers only for a near-certain kill
            # (hitting a champion turns that shooter on the bot: Match.champion_aggressor)
            champs = [c for c in self.enemy_champions(sight) if self.dive_ok(c)]
        else:
            champs = [c for c in self.enemy_champions(sight) if not self.turret_danger(c.pos)]
        if ic.get("bot_turret_aggro_retreat", True) and self.share() < float(ic.get("bot_dive_health", 0.7)) \
                and not self.aware():
            # 2026-10-28 15:00 (tester report; test-2026-10-28-1439-sweep.md S6): an enemy champion under an enemy turret
            # is chased only with bot_dive_health or more of the bot's health, allied minions there or not (hitting it
            # there turns the turret on the bot)
            champs = [c for c in champs if self.turret_danger(c.pos, minion_cover=False) is None]
        champs = self.leash_filter(champs)
        for c in sorted(champs, key=lambda c: (c.health or 0)):
            hit_ally = m.aggressors.get(c.eid, (-1e9, 0))
            weaker = (c.health or 0) / max(1, c.max_health or 1) <= self.share() * aggr
            if weaker or (m.t - hit_ally[0] < 3.0 and hit_ally[1] == e.team):
                return c
        aware = self.aware()
        if tac and ic.get("bot_siege_first", True):
            # 2026-10-30 (tester report 18:12: "if it can go under the tower because there are minions, it should do it
            # and attack the tower"): the structure its minions hold before the minions around it
            s = self.siege_target(sight)
            if s is not None:
                return s
        minions = [mu.ent for mu in self.units(sight, ("minion", "camp")) if m.units.attackable(mu.ent)
                   and mu.role == "minion" and (self.safe_to_hit(mu.ent) if aware else not self.turret_danger(mu.ent.pos))]
        if minions:
            return min(minions, key=lambda x: x.health or 0)
        for mu in self.units(sight, ("turret", "core_turret", "inner_turret", "dampener", "core", "foundry")):
            if not m.units.attackable(mu.ent):
                continue
            if self.safe_to_hit(mu.ent) if aware else self.turret_danger(mu.ent.pos) is None:
                return mu.ent
        return None

    def tower_busy(self, shooter):
        """The enemy shooter's current target is one of this bot's allied minions (it is not free to shoot the bot)."""
        t = shooter.target
        mu = getattr(t, "match_unit", None) if t is not None else None
        return mu is not None and mu.role == "minion" and t.alive and t.team == self.ent.team

    def leash_filter(self, champs):
        """2026-10-29 (tester report 2026-10-29 15:30: "the AI champions should not follow me completely behind my
        tower"): no leash / chase distance in the AI data (units-and-ai.md 5.1, C). With [ics] bot_leash_rules a bot
        (a) never takes an enemy champion that stands in an enemy shooter's range + 1.5 m unless that shooter is busy
        with one of the bot's minions (bot_dive_needs_tank), (b) drops a champion once the bot is more than bot_leash m
        from where that chase began, or the champion is more than bot_sight + bot_chase_margin m away, and then ignores
        it for bot_leash_ignore s (it goes back to its lane: push)."""
        ic = self.mg.ic
        if not ic.get("bot_leash_rules", True):
            return champs
        now = self.mg.m.t
        e = self.ent
        ignore = self.__dict__.setdefault("ignore", {})
        for k in [k for k, v in ignore.items() if v <= now]:
            ignore.pop(k, None)
        out = []
        for c in champs:
            if c.eid in ignore:
                continue
            if ic.get("bot_dive_needs_tank", True) and self.tactics():
                # 2026-10-30 (tester report 18:12): champion_ok decides - the victim under the turret does not draw it,
                # the hitter in its range does
                if not self.champion_ok(c):
                    continue
            elif ic.get("bot_dive_needs_tank", True):
                tower = self.turret_danger(c.pos, minion_cover=False)
                if tower is not None and not self.tower_busy(tower) and not (self.aware() and self.sure_kill(c)):
                    continue
            out.append(c)
        cur = self.target if getattr(self.target, "kind", None) == "champion" else None
        if cur is not None:
            anchor = getattr(self, "chase_from", None)
            chase = float(ic.get("bot_sight", 9.0)) + float(ic.get("bot_chase_margin", 2.0))
            strayed = anchor is not None and math.hypot(e.pos[0] - anchor[0], e.pos[1] - anchor[1]) > \
                float(ic.get("bot_leash", 10.0))
            if cur not in out or strayed or e.distance_to(cur) > chase:
                if strayed or cur.alive:
                    ignore[cur.eid] = now + float(ic.get("bot_leash_ignore", 3.0))
                    self.mg.m.log(f"bot {e.name}: leash, stops chasing {cur.name}"
                                  + (" (too far from where the chase began)" if strayed else ""))
                out = [c for c in out if c is not cur]
                self.chase_from = None
        return out

    def note_chase(self, target):
        """The point where a chase of an enemy champion began (bot leash anchor)."""
        if getattr(target, "kind", None) != "champion":
            self.chase_from = None
        elif self.target is not target or getattr(self, "chase_from", None) is None:
            self.chase_from = (self.ent.pos[0], self.ent.pos[1])

    def push_point(self):
        """Behind the most advanced allied minion of its lane, else by its farthest allied turret, else the mouth."""
        if not self.route:
            return self.home()
        mine = [mu for mu in self.mg.m.units.by_eid.values() if mu.role == "minion" and mu.team == self.ent.team
                and mu.ent.alive and (mu.lane == self.lane or len(self.mg.m.map["lanes"]) == 1)]
        if mine:
            lead = max(mine, key=lambda mu: self.progress(mu.ent.pos))
            i = self.progress(lead.ent.pos)
            back = self.route[max(0, i - 1)]
            dx, dy = back[0] - lead.ent.pos[0], back[1] - lead.ent.pos[1]
            d = math.hypot(dx, dy) or 1.0
            gap = float(self.mg.ic.get("bot_behind_minions", 3.0))
            p = [lead.ent.pos[0] + dx / d * gap, lead.ent.pos[1] + dy / d * gap, self.ent.pos[2]]
            shooter = self.unsafe(p) if self.aware() else None
            if shooter is not None:
                # 2026-10-30 (tester report 15:30): the wave is under an enemy shooter it does not hold: wait out of range
                safe = shooter.range + float(self.mg.ic.get("bot_tower_margin", 1.5)) + 1.0
                for j in range(i, -1, -1):
                    q = self.route[j]
                    if math.hypot(q[0] - shooter.ent.pos[0], q[1] - shooter.ent.pos[1]) > safe:
                        return [q[0], q[1], self.ent.pos[2]]
                return self.home()
            return p
        towers = [mu for mu in self.mg.m.units.by_eid.values() if mu.role in ("turret", "inner_turret")
                  and mu.team == self.ent.team and mu.ent.alive]
        if towers:
            t = max(towers, key=lambda mu: self.progress(mu.ent.pos))
            i = self.progress(t.ent.pos)
            p = self.route[max(0, i - 1)]
            return [p[0], p[1], self.ent.pos[2]]
        p = self.route[min(1, len(self.route) - 1)]
        return [p[0], p[1], self.ent.pos[2]]

    def basic_in_cast(self):
        """2026-10-28 15:00 (tester report; test-2026-10-28-1439-sweep.md S4: the bot's Vault cut its empowered basic
        attack SmitingStrike): its basic attack (slot 0) is in its cast, for at most [ics] bot_skill_waits_basic s after
        it started (World.casting_skill leaves slot 0 out; a basic state that never ends must not stop the skills)."""
        cap = float(self.mg.ic.get("bot_skill_waits_basic", 1.5) or 0.0)
        inst = (getattr(self.ent, "skill_insts", None) or {}).get(0)
        if cap <= 0 or inst is None or getattr(inst, "removed", False) or getattr(inst, "casting", 0) <= 0:
            return False
        return time.time() - float(self.ent.__dict__.get("basic_cast_at", 0.0)) < cap

    def busy(self):
        """No new skill now: one of its skills is in its cast ([ics] bot_skill_waits_cast: in a simulated check the AI
        AWW cast Vault 0.5 s into Savage Sweep's 1 s cast), or its basic attack is (basic_in_cast)."""
        if self.mg.ic.get("bot_skill_waits_cast", True) and self.w.casting_skill(self.ent):
            return True
        return self.basic_in_cast()

    def fight(self, target, now):
        e, ic = self.ent, self.mg.ic
        is_champ = target.kind == "champion"
        if random.random() <= float(ic.get("bot_skill_chance", 1.0)) and not self.busy():
            for slot in SKILL_ORDER:
                if self.try_skill(slot, target, is_champ, now):
                    return
        if e.attack_target is not target:
            e.attack_target = target
            self.goal = None

    def try_skill(self, slot, target, is_champ, now):
        e = self.ent
        sk = e.kit.get(slot)
        if sk is None or not sk.script or e.ranks.get(slot, 0) <= 0:
            return False
        if f"0x{sk.script:08X}" in {str(s).upper().replace("0X", "0x") for s in self.mg.ic.get("bot_skip_scripts") or ()}:
            return False                    # skills that need a map object (Super Strength), not an enemy
        if e.ready_at.get(slot, 0.0) > time.time():
            return False
        if e.__dict__.get("skill_backoff", {}).get(slot, 0.0) > time.time():
            return False                    # [ics] bot_untaken_skill_backoff (S5): its last use did nothing
        rank = max(1, e.ranks.get(slot, 1))
        cost = abs(sk.stat(3, rank))
        if e.max_will and cost > (e.will or 0):
            return False                    # Will, or another resource (charges, Rage) counted in the same vital
        area = sk.stat(22, rank)
        if not is_champ and (area <= 0 or (e.max_will and (e.will or 0) < e.max_will * 0.5)):
            return False
        reach = sk.stat(18, rank)
        reach = reach if reach > 0 else 6.0
        d = e.distance_to(target)
        tt = sk.targeting
        if tt in SELF_TARGET:
            if d > (area if area > 0 else 4.0):
                return False
            target_ent, point = None, None
        elif tt in UNIT_TARGET:
            if d > reach:
                return False
            target_ent, point = target, None
        elif tt in POINT_TARGET:
            if d > reach:
                return False
            speed = sk.stat(30, rank)
            lead = (d / speed) if speed > 0 else 0.0
            p = list(target.pos)
            if lead and target.dest is not None and target.speed:
                h = target.heading
                p = [p[0] + math.cos(h) * target.speed * lead, p[1] + math.sin(h) * target.speed * lead, p[2]]
            target_ent, point = None, p
        else:
            return False
        e.heading = math.atan2(target.pos[1] - e.pos[1], target.pos[0] - e.pos[0])
        prev = e.attack_target
        if self.mg.ic.get("bot_cast_clears_attack", True):
            # 2026-10-28 15:00 (tester report; test-2026-10-28-1439-sweep.md S4): the attack target goes before the cast,
            # as the player's skill order clears it (session.ev_order), so World._attack_step does not start a basic
            # attack inside the cast; fight() sets it again at the next decision ([ics] bot_cast_clears_attack)
            e.attack_target = None
        ok = self.w.cast(e, slot, target_ent, point)
        if ok:
            self.mg.m.log(f"bot {e.name}: casts {sk.name} on {target.name}")
        elif e.attack_target is None:
            e.attack_target = prev          # a refused cast leaves the attack as it was
        return ok

    # ---- levelling and shopping (0x340007E2 / node 0x10000186) ----------------------------------------------------
    def rank_up(self):
        e, w = self.ent, self.w
        if e.skill_points <= 0:
            return
        order = [int(x) for x in (w.data.loadout(e.class_id).get("skill_order") or ())]
        if self.mg.ic.get("bot_rank_order_all_slots", True):
            # 2026-10-28 15:00 (tester report; test-2026-10-28-1439-sweep.md S7: AWW's order [3, 1, 2, 3, 5, 4, ...] holds
            # the trait (slot 5), which the count over slots 1-4 left out: slot 5 ranked at levels 5, 6 and 7, the R only
            # at 8): the k-th entry of a slot wants its rank k; the first entry not reached yet that the rank gates
            # allow goes (a gated entry is retried at the next level instead of being skipped)
            seen, wish = {}, []
            for s in order:
                seen[s] = seen.get(s, 0) + 1
                if e.ranks.get(s, 0) < seen[s]:
                    wish.append(s)
            wish += [4, 1, 2, 3]
        else:
            spent = sum(e.ranks.get(s, 0) for s in (1, 2, 3, 4))
            wish = order[spent:] + [4, 1, 2, 3]
        for slot in wish:
            if self.rankable(slot):
                e.ranks[slot] = e.ranks.get(slot, 0) + 1
                e.skill_points -= 1
                w.log(f"bot {e.name}: slot {slot} rank {e.ranks[slot]}")
                return

    def rankable(self, slot):
        e, w = self.ent, self.w
        if slot not in e.kit or e.ranks.get(slot, 0) >= w.max_rank(slot):
            return False
        return e.level >= w.rank_level_needed(e, slot, e.ranks.get(slot, 0) + 1)   # the player's rule (2026-10-30)

    def shop_visit(self):
        """One shop visit by plan(): only inside its base aura ([ics] bot_shop_when_dead: also while dead), every buy
        of the plan at once, one 0x20E2 for them."""
        e = self.ent
        ic = self.mg.ic
        in_base = bool(getattr(e, "in_base_aura", True))
        if not in_base and not (not e.alive and ic.get("bot_shop_when_dead", False)):
            return
        self.bought_at = time.time()
        bought = 0
        for did, _price in self.plan():
            if not self.mg.shop.buy(e, did):
                break
            bought += 1
            self.mg.m.log(f"bot {e.name}: buys {did:#x} ({e.gold:.0f} credits left)")
        if bought:
            self.send_inventory()

    def send_inventory(self):
        """2026-10-25 17:47 (tester: the bots still buy nothing; the log shows their buys, but 0x20E2 went to the
        player's champion only): the bot's item slots to its own object (its upgrade component), as for the player
        ([ics] bot_inventory_messages)."""
        if self.mg.ic.get("bot_inventory_messages", True):
            e = self.ent
            self.w.send(f"{e.name}: inventory (0x20e2)", M.inventory(e.eid, e.inventory))

    def owned_lines(self, inventory):
        """Every artifact an inventory holds or has passed through (an owned item's "prev" chain counts as owned)."""
        owned = set()
        for did in inventory:
            seen = 0
            while did and did not in owned and seen < 8:
                owned.add(did)
                did, seen = (self.w.data.artifact(did) or {}).get("prev", 0), seen + 1
        return owned

    def plan(self, gold=None):
        """2026-10-30 (tester report 15:30: "when they reach the base they buy or upgrade the item they can afford,
        otherwise wait to have gold to upgrade the one they have bought, and do it in order"): the purchases one shop
        visit makes, [(did, price)], on a copy of the inventory: the loadout's recommended list 0x10000478 in order (its
        lines tier by tier), the next tier of a line the bot already holds before a new line when
        [ics] bot_shop_upgrades_first; a step the shop can never sell it now (not offered, slots full) is passed over,
        the first step it cannot pay ends the visit (it saves for it)."""
        e, shop, data = self.ent, self.mg.shop, self.w.data
        # alive=False: the shop's own where-to-shop rule (shop_anywhere) is not the bot's; shop_visit decides that
        sim = SimpleNamespace(inventory=list(e.inventory), gold=float(e.gold if gold is None else gold), alive=False)
        order = list(data.loadout(e.class_id).get("artifacts") or ())
        out = []
        for _ in range(len(order) + 1):
            owned = self.owned_lines(sim.inventory)
            todo = [d for d in order if d not in owned]
            if self.mg.ic.get("bot_shop_upgrades_first", True):
                # an upgrade of a held line first (in list order), then the rest in list order
                todo = [d for d in todo if shop.lower_tier_slot(sim, d) is not None] + \
                       [d for d in todo if shop.lower_tier_slot(sim, d) is None]
            step = None
            for did in todo:
                r = shop.can_buy(sim, did)
                if r in (CAN_BUY, TOO_EXPENSIVE):      # the step to take, or the one to save for
                    step = (did, r)
                    break
                # NOT_ALLOWED / SLOTS_FULL / NO_RECORD: never now; the next one
            if step is None or step[1] != CAN_BUY:
                break
            did = step[0]
            price, slot = shop.price(sim, did)
            if slot is None:
                slot = sim.inventory.index(0)
            sim.inventory[slot] = did
            sim.gold -= price
            out.append((did, price))
        return out

    def wants_to_shop(self, now):
        """2026-10-30 (tester report 15:30): go home to shop when the visit would buy [ics] bot_shop_recall_value credits
        or more, no enemy champion is within bot_shop_recall_safe m, and the last base visit is bot_shop_recall_gap s
        old (the retreat walks or Recalls home; the base state shops and returns at full health)."""
        ic = self.mg.ic
        value = float(ic.get("bot_shop_recall_value", 1250.0) or 0.0)
        if value <= 0 or not ic.get("bot_shopping", True) or not ic.get("bot_shop_plan", True):
            return False
        if now - getattr(self, "base_left_at", -1e9) < float(ic.get("bot_shop_recall_gap", 45.0)):
            return False
        if getattr(self, "plan_checked_at", -1e9) > now - 2.0:
            return False                                # the plan at most every 2 s
        self.plan_checked_at = now
        if self.enemy_champions(float(ic.get("bot_shop_recall_safe", 12.0))):
            return False
        spend = sum(p for _d, p in self.plan())
        if spend >= value:
            self.mg.m.log(f"bot {self.ent.name}: goes home to shop ({spend:.0f} of {self.ent.gold:.0f} credits to spend)")
            self.base_left_at = now                     # one trip per gap
            return True
        return False

    def shop(self):
        e = self.ent
        if not self.mg.ic.get("bot_shopping", True) or time.time() - self.bought_at < 1.0:
            return
        if self.mg.ic.get("bot_shop_plan", True):
            self.shop_visit()
            return
        if e.alive and not getattr(e, "in_base_aura", True) and self.mg.ic.get("bot_shop_in_base_only", True):
            # 2026-10-25 22:07 (test-2026-10-25-2207.md 4: a bot whose recall was cut by a Grab bought in mid lane):
            # alive, it shops only inside its base aura (dead it may, as the original's dead champions)
            return
        self.bought_at = time.time()
        # 2026-10-25 22:07 (tester: a bot bought Modular Health Vial (1) again after upgrading it to (2)): an item counts
        # as owned when an owned item upgrades from it (artifact "prev" chain)
        owned = set()
        for did in e.inventory:
            seen = 0
            while did and did not in owned and seen < 8:
                owned.add(did)
                did, seen = (self.w.data.artifact(did) or {}).get("prev", 0), seen + 1
        for did in self.w.data.loadout(e.class_id).get("artifacts") or ():
            if did in owned:
                continue
            if self.mg.shop.can_buy(e, did) == 2:
                if self.mg.shop.buy(e, did):
                    self.mg.m.log(f"bot {e.name}: buys {did:#x} ({e.gold:.0f} credits left)")
                    self.send_inventory()
                return
            # the next one in the list waits until this one is affordable (the recommended order)
            if (self.w.data.artifact(did) or {}).get("cost", 0) > e.gold:
                return


class BotManager:
    """One BotBrain per bot champion agent, ticked by Match.tick."""

    def freeze(self):
        """2026-10-30 (tester report 15:30, video: after the surrender passed the bot kept casting and attacking ~9 s and
        "killed" the player): the match is over, every bot stops where it is: no target, no path, a stop state
        ([ics] match_end_freeze_combat; Match.tick no longer ticks the brains once the match is over)."""
        if not self.ic.get("match_end_freeze_combat", True):
            return
        w = self.m.world
        for b in self.brains:
            e = b.ent
            b.state, b.target, b.goal = "over", None, None
            moving = e.dest is not None or bool(e.path)
            e.attack_target, e.dest, e.path, e.speed = None, None, [], 0.0
            if hasattr(e, "pending_move"):
                e.pending_move = None
            if moving and e.alive:
                try:
                    w.update(e, f"bot {e.name}: stops (match over)")
                except Exception as ex:          # noqa: BLE001
                    self.m.log(f"bot {e.name}: stop state failed {ex!r}")
            self.m.log(f"bot {e.name}: frozen (match over)")

    def __init__(self, match):
        self.m, self.ic = match, match.ic
        self.brains = []
        self._shop = None

    @property
    def shop(self):
        if self._shop is None:
            self._shop = Shop(self.m.world, self.m.encounter)
        return self._shop

    def lane_for(self, team, slot):
        lanes = list((self.m.map.get("lanes") or {}).keys())
        if not lanes:
            return None
        table = (self.ic.get("bot_lanes") or {}).get(self.m.map.get("key", ""))
        if table:
            lane = table[slot % len(table)]
            if lane in lanes:
                return lane
        if len(lanes) == 1:
            return lanes[0]
        if set(LANES_5V5) <= set(lanes):
            return LANES_5V5[slot % len(LANES_5V5)]
        return lanes[slot % len(lanes)]

    def attach(self, agents):
        if not self.ic.get("bot_brains", True):
            return
        for ent in agents:
            p = self.m.score.by_agent(ent)
            brain = BotBrain(self, ent, p.slot if p is not None else len(self.brains))
            self.brains.append(brain)
            # 2026-10-25 16:12 (tester: the bots buy no items): they start with the player's credits too
            ent.gold = max(float(ent.gold or 0.0), float(self.ic.get("start_credits", 0) or 0))
            self.m.log(f"bot {ent.name}: lane {brain.lane}")
        if self.brains:
            # the ids the client stores only on a change (unit flags, tags, allied vision), once the client has them
            delay = float(self.ic.get("unit_flags_delay", 0.8) or 0.8)
            for b in self.brains:
                self.m.later(delay, lambda e=b.ent: self.m.world.bot_late_properties(e))
        self._resent = False

    def respawned(self, ent):
        for b in self.brains:
            if b.ent is ent:
                b.state, b.goal, b.target = "base", None, None
                self.m.later(float(self.ic.get("unit_flags_delay", 0.8) or 0.8),
                             lambda e=ent: self.m.world.bot_late_properties(e))

    def tick(self, dt, now):
        if not self.brains:
            return
        w = self.m.world
        if not getattr(self, "_resent", True) and w.in_world:
            # the bundles sent while the client was loading: again once it is in the world (second_seq 1)
            self._resent = True
            for b in self.brains:
                w.update(b.ent, f"bot {b.ent.name} (in world)")
                w.vitals(b.ent)
                if any(b.ent.inventory):
                    b.send_inventory()
                self.m.later(float(self.ic.get("unit_flags_delay", 0.8) or 0.8),
                             lambda e=b.ent: w.bot_late_properties(e))
        rate = float(self.ic.get("credits_per_second", 0) or 0)
        lo, hi = (self.ic.get("bot_decision_interval") or [0.5, 0.8])[:2]
        react = float(self.ic.get("bot_reaction", 1.0) or 1.0)
        for b in self.brains:
            if rate > 0:
                b.ent.gold += rate * dt
            if b.ent.alive and b.state != "recall":
                b.unstick(now)
            if now >= b.next_decision:
                b.next_decision = now + random.uniform(float(lo), float(hi)) * react
                try:
                    b.decide(now)
                    fast = float(self.ic.get("bot_tower_react", 0.2) or 0.0)
                    if fast > 0 and b.ent.alive and b.state in ("push", "fight", "evade") and b.tactics() \
                            and b.near_shooter():
                        # 2026-10-30 (tester report 18:12): near an enemy shooter it re-decides every bot_tower_react s
                        # (out the moment the tower turns on it, out of a trade before the next shot)
                        b.next_decision = min(b.next_decision, now + fast)
                except Exception as e:             # noqa: BLE001 - a bot must never stop the match
                    self.m.log(f"bot {b.ent.name}: decision error {e!r}")
                if self.ic.get("bot_trace", False):
                    # 2026-10-28 15:00 (test-2026-10-28-1439-sweep.md S6: which branch kept the bot under the turret was
                    # not logged): one line per decision ([ics] bot_trace)
                    be = b.ent
                    at = be.attack_target
                    self.m.log(f"bot {be.name}: {b.state} at ({be.pos[0]:.1f}, {be.pos[1]:.1f}) {b.share():.0%} health"
                               f", target {getattr(b.target, 'name', None)}, attacking {getattr(at, 'name', None)}"
                               + (f", goal ({b.goal[0]:.1f}, {b.goal[1]:.1f})" if b.goal else "")
                               + (f", aggro {b.turret_aggro().ent.name}" if b.turret_aggro() is not None else ""))
