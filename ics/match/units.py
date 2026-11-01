"""The match's own units on a World: structures, lane minions, neutral camps and objectives, their movement and AI.

The original server's AI is not in the data (units-and-ai.md 5); this follows its scripted twin, Starro's parasite
0x3400053A, and the user's MOBA prototype (sistema_suiditos_moba.py: WaveManager / MinionAI target priorities,
leash): every GetBestPerceivedTargetInterval (0.5-0.8 s, record 0x3A000026) pick the best enemy within the unit's
vision (template 0x10000133), walk into range (its attack's stat 18) and use its slot-0 attack script.

World ownership (ics/world.py belongs to the combat engineer): a match unit keeps its attack in `ent.match_kit` and an
empty `ent.kit`, so World's own champion-only unit AI and chase step leave it alone; the attack still runs through
World.cast (the kit is put back for the call). Structures are kind "structure" (not hidden by World.fog, no
creature properties: their team / LifeState / minimap properties are in extra_props). Movement does not use
ent.dest (World.tick would re-send the unit every tick): MatchUnit.step moves it and sends one state per corner,
start and stop (client-movement.md 1.4 / 2: the client dead-reckons from the last state).
"""
import math
import struct
import random
import time

from .. import messages as M
from ..world import CastWorld
from ..wire import KIND_BOOL, KIND_DID, KIND_ENUM, KIND_F32, KIND_IID, KIND_INT, KIND_U32
from . import maps
from .unitdata import (PROP_CREDITS_FORMULA, PROP_TEAM_BOUNTY, PROP_XP_FORMULA, STAT_ATTACK_DAMAGE, STAT_ATTACK_SPEED,
                       STAT_HEALTH, STAT_MOVE_SPEED)

PROP_TEAM, PROP_LIFE, PROP_MAP_CATEGORY, PROP_ON_MAP = 0x1000009C, 0x100000FA, 0x100004DA, 0x2A1
PROP_VISION, PROP_SIDE, PROP_FLAGS, PROP_OWNER = 0x10000133, 0x100007A2, 0x1000019D, 0x10000456
PROP_COLOUR_OVERRIDE, PROP_HIDDEN = 0x10000CF0, 0x90F
STRUCTURES = ("core", "core_turret", "turret", "inner_turret", "dampener", "foundry")
SHOOTERS = ("core_turret", "turret", "inner_turret", "dampener", "foundry", "core")
# The attack scripts load their range, source position and damage stats in graph S1 on event 0x10000088 (level
# up / init, units-and-ai.md 7: 0x1000000C / 0x10000088); without it IsInRangeAndAngle fails and no shot is fired.
EVENT_UNIT_INIT = 0x10000088
VAR_SHOT_TARGET, VAR_SHOT_SPEED = 0x10000030, 0x100009EB


def heading_from_yaw(deg):
    """A placement yaw (degrees, the statics' / cinematics' frame) -> World heading (World.placements: yaw + pi/2)."""
    return math.radians(deg) + math.pi / 2


class MatchUnit:
    """One unit the match owns, wrapped around its World entity."""

    def __init__(self, ent, role, team, cls):
        self.ent, self.role, self.team, self.cls = ent, role, team, cls
        self.lane = None
        self.lane_points = []          # the whole lane, mouth to enemy base
        self.lane_i = 0                # next lane point
        self.path = []                 # points still to walk (lane or chase)
        self.target = None
        self.next_think = 0.0
        self.next_attack = 0.0
        self.repath_at = 0.0
        self.range = 1.5
        self.vision = 6.0
        self.radius = 0.5              # body radius: melee reach is counted to the target's edge
        self.home = None               # camps: where they go back to
        self.camp = None
        self.moving = False
        self.state_at = -1e9           # last movement state sent (game clock)
        self.level = 1
        self.invulnerable = False
        self.requires = []             # structures that must fall before this one can be damaged
        self.casts_without_hit = 0
        self.direct_damage = False     # its attack script never dealt damage: the AI deals it ([ics] fallback)
        self.offset = 0.0              # sideways offset on the lane (minions of a wave do not stack)
        self.leash_from = None         # minions: where it left its lane to chase ([ics] match_leash_rules)
        self.returning_until = 0.0     # minions: walking back to the lane after a leash break (no new target)
        self.ignore = {}               # minions: target eid -> game time it is ignored until (a leash break)
        self.shuffle = None            # separation: (x, y) a standing unit is sliding to (Units.separate)
        self.sent_pos = None           # the last movement state sent: position and speed (its dead reckoning)
        self.sent_speed = 0.0

    @property
    def alive(self):
        return self.ent.alive

    def __repr__(self):
        return f"{self.role}:{self.ent.name}"


class Units:
    """Spawning and running the match's units (owned by ics.match.Match)."""

    def __init__(self, match):
        self.m = match
        self.w = match.world
        self.ic = match.ic
        self.ud = match.ud
        self.by_eid = {}
        self.rng = random.Random(int(match.encounter))
        lo, hi = self.ic.get("match_retarget_interval") or (0.5, 0.8)
        self.retarget = (float(lo), float(hi))

    # ---- spawning ------------------------------------------------------------------------------------------------
    def _place(self, pos):
        """(x, y, z) on the walkable mesh near pos (structures and units placed on a G position)."""
        x, y = float(pos[0]), float(pos[1])
        z = float(pos[2]) if len(pos) > 2 else float(self.m.map["z"])
        nav = self.w.nav
        if nav is not None and self.ic.get("match_snap_to_navmesh", True):
            near = nav.nearest(x, y, max_r=6.0)
            if near and math.hypot(near[0] - x, near[1] - y) > 0.01 and (len(pos) <= 2):
                x, y = near
        return [x, y, z]

    def spawn(self, cls, pos, team, role, heading=0.0, name=None):
        w, ud = self.w, self.ud
        ent = w.spawn(cls, self._place(pos), heading, side=1, name=name or f"{role} {cls:#x} t{team}")
        mu = MatchUnit(ent, role, team, cls)
        ent.match_unit = mu
        ent.team = team
        ent.side = 3 if team == maps.T1 else 5 if team == maps.T2 else 0
        wire = self.ic.get("match_camp_wire_team")
        if role == "camp" and wire is not None:
            # 2026-10-28 15:00 (tester report 2026-10-28 15:00: grey jungle drones, the original's are yellow;
            # camps-colour-bar-positions.md 1, C): the client sees a camp unit (a boss too) as team [ics]
            # match_camp_wire_team (0 = neutral, the yellow tint; World.properties) with colour index match_camp_side;
            # `team` stays the server's (match_neutral_team) for fog, AI, rewards and script relations
            ent.wire_team = int(wire)
            ent.side = int(self.ic.get("match_camp_side", 6))
        if not self.ic.get("match_colour_override", False):
            # the tutorial's purple drones (0x10000CF0 = 1); PvP units keep the client's team colours
            ent.extra_props = [p for p in ent.extra_props if p[0] != PROP_COLOUR_OVERRIDE]
        # the attack: kept out of ent.kit (World's own unit AI / chase run only for units with a kit)
        mu.attack = ent.kit.get(0)
        ent.match_kit = dict(ent.kit)
        ent.kit = {}
        mu.vision = ud.vision(cls, 6.0)
        if mu.role in ("minion", "camp") and str(self.ic.get("match_minion_vision", "min")) == "min":
            # 2026-10-25 09:00 (tester: the fog of war shows now, but the minions see too far): a minion template carries
            # two 0x10000133 values (3.0 and 6 / 7 / 8 by type); the smaller one ("max" = the earlier choice)
            vals = [v for v in (ud.template(cls).get(PROP_VISION) or []) if isinstance(v, (int, float))]
            vals = [struct.unpack("<f", struct.pack("<I", int(v)))[0] if isinstance(v, int) else float(v) for v in vals]
            vals = [v for v in vals if 0 < v < 100]
            if vals:
                mu.vision = min(vals)
        mu.level = ud.level_at(cls, max(0.0, self.m.t))
        self.apply_stats(mu, refill=True)
        reach = mu.attack.stat(18, 1) if mu.attack else 0.0
        if role in SHOOTERS:
            # turret attack 0x34000014: range 9 m (units-and-ai.md 1.3); its parsed stat 18 is not the range
            reach = reach if 3.0 <= reach <= 20.0 else (mu.vision if mu.vision >= 3.0 else 9.0)
        mu.range = reach if reach > 0 else 1.5
        if role in tuple(self.ic.get("match_unarmed_roles") or ()):
            # 2026-10-30 (tester report 15:30: "the core must not attack, it must not have that invisible turret on
            # top"; core-door-regen.md 2): the data gives the core the turret attack 0x34000014; [ics] match_unarmed_roles
            # never target or shoot (think) and carry no warning ring (_properties)
            mu.attack = None
            mu.unarmed = True
        if role in STRUCTURES:
            ent.kind = "structure"
            ent.move_speed = 0.0
            if role == "dampener" and self.ic.get("match_dampener_keep_body", True):
                # 2026-10-25 (map-objectives-recipes.md 5.4, C keys: a destroyed dampener stays, deactivated, until it
                # comes back): its body is kept (Object_Deactivate) and removed when the new one spawns
                ent.keep_body = True
            ent.client_vitals = bool(self.ic.get("match_structure_vitals", True))
            mu.radius = float((self.ic.get("match_structure_radius") or {}).get(role, 1.5))
            if role == "foundry":
                mu.invulnerable = True          # the base turret: "HP 1" in its stat block, never meant to fall
        elif role in ("capture", "relay", "beacon", "device"):
            ent.kind = "structure"
            ent.move_speed = 0.0
            ent.client_vitals = False
            mu.invulnerable = True
            mu.radius = 1.5
        self._properties(mu)
        self.by_eid[ent.eid] = mu
        if role in STRUCTURES and w.nav is not None:
            r = mu.radius
            if r > 0:
                w.nav.block(ent.eid, ent.pos[0], ent.pos[1], r, r, 0.0)
        self.w.send(f"spawn {ent.name} ({cls:#x})", w.bundle(ent))
        w.vitals(ent)
        if role not in STRUCTURES and ent.kind == "unit" and not (role == "camp" and self.ic.get("match_camp_skip_enter_world", True)):
            # the minions' spawn-in effect (World.spawn_in). 2026-10-25 23:11 (tester: the camps appear with no transparent
            # vortex): a camp's own phase-in (match_camp_spawn_scriptlets) came 3 ms after this one and did not show
            w.spawn_in(ent)
        self._init_scripts(mu)
        if role in tuple(self.ic.get("run_jungle_scripts_roles") or ()) and self.ic.get("run_jungle_scripts", True):
            # 2026-10-25 (map-objectives-recipes.md 4, C: the Raider / heavy / buff destroyer entity scripts 0x34000670,
            # 0x3400007D, 0x3400051A / 51B drop their pad or reward from data on 0x10000007 {KillerIID}, after
            # 0x10000149 at the spawn): their own scripts run, 0x10000149 a moment after the bundle
            w.start_unit_scripts(ent, force=True)
            self.m.later(0.3, lambda e=ent: self.w.raise_event(e, 0x10000149) if e.alive else None)
        if role in STRUCTURES:
            self._spawn_head(mu)
        return mu

    def _spawn_head(self, mu):
        """2026-10-23 (tester: turret shots unseen and silent): a turret is two objects in the layout (body world state
        0x2E000AA0, head 0x2E000AA8 at the same spot, pack 0xA00002E6); the head is created with it, started
        (Vfx_Startup) and coloured by team ([ics] match_turret_heads: role -> head world state; {} = none)."""
        ent = mu.ent
        plate = int((self.ic.get("match_turret_plates") or {}).get(mu.role, 0) or 0)
        if plate:
            # 2026-10-23 15:40 (tester: the turrets lack their base): the cinematics place TurretBasePlate
            # 0x2E000A9F under each turret (maps-complete.md, 0x3500002A / 2B); it stays when the turret falls
            base = self.w.spawn(plate, list(ent.pos), ent.heading, name=f"{ent.name} plate")
            base.team = mu.team
            self.w.update(base, f"spawn {base.name} ({plate:#x})")
        self._spawn_platform(mu)
        names = list((self.ic.get("match_structure_scriptlets") or {}).get(mu.role) or [])
        ally = mu.team == self.m.local_team()
        names = [("Vfx_Active_Blue" if ally else "Vfx_Active_Red") if n == "active" else n for n in names]
        for k, name in enumerate(names):
            # 2026-10-25 (tester: the dampener stands on a flat black octagon; crime-alley-visuals.md d, P): it got no
            # scriptlet at all; its activation keys light its field
            self.m.later(0.3 + 0.2 * k, lambda n=name, e=ent: self.w.scriptlet(e, n, f"{e.name}: {n} (0x8d)")
                         if e.eid in self.w.entities else None)
        mu.parts = []
        for entry in (self.ic.get("match_structure_parts") or {}).get(mu.role) or ():
            # 2026-10-30 tester report 13:00 (the blue Power Core Turret showed only a ghost cylinder; turret-pct-
            # composite.md): world states the server spawns with the body as objects of their own (the PCT's cylinder
            # 0x2E000A9A over the lane body), each with the body's side / team and its Vfx_Startup. Entry = world state
            # or [world state, dz]
            pws, dz = (entry, 0.0) if not isinstance(entry, (list, tuple)) else (entry[0], entry[1] if len(entry) > 1 else 0.0)
            pws = int(str(pws), 0)
            if pws:
                mu.parts.append(self._spawn_part(mu, pws, float(dz or 0.0), "part"))
        ws = int((self.ic.get("match_turret_heads") or {}).get(mu.role, 0) or 0)
        if ws and self.ic.get("match_turret_head_skip_own_child", True) and "Vfx_AI_Active" in names and \
                (ent.scriptlet_keys is None or self.w.data.scriptlet_key("Vfx_AI_Active") in ent.scriptlet_keys):
            # 2026-10-29 (tester report 23:03: "the turrets appear with 2 heads; the white one is wrong, only the blue
            # one"; turret-heads-coredeath.md 1, C table 0x1D000372): the body's own Vfx_AI_Active makes the client
            # spawn the head 0x2E000AA8 (scale 0.9, Vfx_Startup, the body's colour); the server-made head was a second,
            # white copy. false = the server head as well (fase3-io)
            ws = 0
        if not ws:
            return
        head = self.w.spawn(ws, list(ent.pos), ent.heading, name=f"{ent.name} head")
        head.team = mu.team
        head.extra_props.append((PROP_TEAM, KIND_INT, mu.team))
        if self.ic.get("match_turret_head_side", True) and mu.team in (maps.T1, maps.T2):
            # 2026-10-29 (tester report 2026-10-29 12:45: "the firing head does not look right"; recording 13:00, white
            # hologram over the turret only while it fires; ca-holes-pedestal-turrets.md O2): the head's Vfx_Startup /
            # Vfx_Active_* (base table 0x1D00038B) pick the colour on side 0x100007A2 (appearance 0x19000A61, as the
            # camps' colour); the head had no side and no team change, so it took the Null (white) colour. It gets the
            # body's side in its bundle and the team as a change (0, then the team), as the structures
            head.side = ent.side
            head.extra_props.append((PROP_SIDE, KIND_ENUM, int(ent.side or 0)))
            if self.ic.get("team_as_change", True):
                self.m.later(float(self.ic.get("unit_flags_delay", 0.8) or 0.8) + 0.1,
                             lambda h=head, t=mu.team: self.late_team(h, t))
        self.w.update(head, f"spawn {head.name} ({ws:#x})")
        mu.head = head
        ally = mu.team == self.m.local_team()
        names = ["Vfx_Startup", "Vfx_Active_Blue" if ally else "Vfx_Active_Red"]
        if not self.ic.get("match_turret_head_team_keys", False):
            # 2026-10-29 (tester report 21:10: the heads look almost transparent; power-core-turret.md 8.7): as the
            # original's own head (the body's Vfx_AI_Active child runs Vfx_Startup only), no Vfx_Active_Blue / _Red
            names = names[:1]
        for k, name in enumerate(names):
            self.m.later(0.3 + 0.2 * k, lambda n=name, h=head: self.w.scriptlet(h, n, f"{h.name}: {n} (0x8d)")
                         if h.eid in self.w.entities else None)

    def _spawn_platform(self, mu):
        """2026-10-30 (tester report 14:51 video: "the turret next to the core still lacks its platform"; original frames
        66 / 67 / 70: the Power Core Turret stands on a pointed prow that leaves the core platform toward the lane;
        agl-floor-raider-pad-pct-prow.md 3): [ics] match_structure_platforms {map key: {role: {"world_state", "forward"
        (m along the team's lane direction, team 2 mirrored), "dz", "yaw" (deg added to the lane heading)}}}: a static
        piece under the structure, the team's, made once per match (it stays when the structure falls, as the plate)."""
        spec = ((self.ic.get("match_structure_platforms") or {}).get(self.m.map.get("key")) or {}).get(mu.role)
        if not spec:
            return
        ws = int(str(spec.get("world_state", 0) or 0), 0)
        if not ws:
            return
        made = self.__dict__.setdefault("_platforms", {})
        key = (mu.role, mu.team)
        old = made.get(key)
        if old is not None and old.eid in self.w.entities:
            return
        ent = mu.ent
        lane = 0.0 if mu.team != maps.T2 else math.pi        # Crime Alley: team 1's lane runs east, team 2's west
        fwd = float(spec.get("forward", 0.0) or 0.0)
        pos = [ent.pos[0] + math.cos(lane) * fwd, ent.pos[1] + math.sin(lane) * fwd,
               ent.pos[2] + float(spec.get("dz", 0.0) or 0.0)]
        plat = self.w.spawn(ws, pos, lane + math.radians(float(spec.get("yaw", 0.0) or 0.0)),
                            name=f"{ent.name} platform")
        plat.team = mu.team
        if spec.get("side", True) and mu.team in (maps.T1, maps.T2):
            plat.side = ent.side
            plat.extra_props.append((PROP_SIDE, KIND_ENUM, int(ent.side or 0)))
        self.w.update(plat, f"spawn {plat.name} ({ws:#x})")
        made[key] = plat
        for k, name in enumerate(spec.get("scriptlets") or ()):
            self.m.later(0.3 + 0.2 * k, lambda n=name, p=plat: self.w.scriptlet(p, n, f"{p.name}: {n} (0x8d)")
                         if p.eid in self.w.entities else None)

    def _spawn_part(self, mu, ws, dz, label):
        """A structure's extra server-made piece (match_structure_parts): the body's side and team, Vfx_Startup."""
        ent = mu.ent
        pos = list(ent.pos)
        if dz and len(pos) > 2:
            pos[2] += dz
        part = self.w.spawn(ws, pos, ent.heading, name=f"{ent.name} {label} {ws:#x}")
        part.team = mu.team
        part.extra_props.append((PROP_TEAM, KIND_INT, mu.team))
        if mu.team in (maps.T1, maps.T2):
            part.side = ent.side
            part.extra_props.append((PROP_SIDE, KIND_ENUM, int(ent.side or 0)))
            if self.ic.get("team_as_change", True):
                self.m.later(float(self.ic.get("unit_flags_delay", 0.8) or 0.8) + 0.1,
                             lambda p=part, t=mu.team: self.late_team(p, t))
        self.w.update(part, f"spawn {part.name}")
        self.m.later(0.3, lambda p=part: self.w.scriptlet(p, "Vfx_Startup", f"{p.name}: Vfx_Startup (0x8d)")
                     if p.eid in self.w.entities else None)
        return part

    def _turret_target(self, mu, t):
        """Target_Acquired 0x1000014A (target variable) / Target_Lost 0x1000002C on the body, Vfx_Targeting on the
        head: the turret's own visuals, and probably the client's turret warning (0xa84fb0)."""
        ent = mu.ent
        if self.ic.get("turret_warning", True) and ent.eid in self.w.entities and \
                (getattr(t, "eid", 0) if t is not None else 0) != getattr(mu, "warn_target", 0):
            # 2026-10-25 (crime-alley-props.md C, listener 0xA8DFB0): the warning ring turns solid red when the turret's
            # target IID 0x10000C66 is the local champion; 0 when it drops the target
            mu.warn_target = getattr(t, "eid", 0) if t is not None else 0
            self.w.send(f"{ent.name}: target {mu.warn_target:#x} (0x10000C66, 0x6)",
                        M.set_property(ent.eid, 0x10000C66, KIND_IID, mu.warn_target))
        if t is None and mu.target is not None:
            self._head_rearm_later(mu)
        if not self.ic.get("match_turret_target_scriptlets", True):
            return
        if self.ic.get("match_turret_own_head_no_target_keys", True) and getattr(mu, "head", None) is None and \
                "Vfx_AI_Active" in ((self.ic.get("match_structure_scriptlets") or {}).get(mu.role) or ()):
            # 2026-10-30 (tester report 12:05: "when the enemy tower targeted me, the tower's head disappeared"; also
            # 11:23; turret-head-pct-look.md 1): the head is the client's own child of the body's Vfx_AI_Active. The
            # body's Target_Acquired / Target_Lost run Vfx_Targeting client-side (type 0x17, no instance), which the
            # client forwards to that child (0x57B9D0, the spawn's wired keys); the turret's own attack script
            # 0x34000014 never runs either key (C), and the head first vanished in the build that made it the client
            # child. The 0x10000C66 target (warning ring) and the shots still go. false = Target_Acquired / _Lost as before
            return
        if t is not None:
            CastWorld(self.w, ent, None).run_scriptlet(ent, 0x1000014A, target=t, variables=[(VAR_SHOT_TARGET, t)])
            head = getattr(mu, "head", None)
            if head is not None and head.eid in self.w.entities:
                self.w.scriptlet(head, "Vfx_Targeting", f"{head.name}: Vfx_Targeting (0x8d)")
        elif mu.target is not None:
            CastWorld(self.w, ent, None).run_scriptlet(ent, 0x1000002C)
            # 2026-10-23 23:10 (tester: the targeting line stays on the champion): Vfx_Targeting loops on the head and
            # no 0x8D form stops one run, so the head goes back to its idle state ([ics] match_turret_lost_head:
            # head scriptlets in order; "active" = its team's Vfx_Active_Blue / _Red)
            head = getattr(mu, "head", None)
            if head is not None and head.eid in self.w.entities:
                ally = mu.team == self.m.local_team()
                for name in self.ic.get("match_turret_lost_head", ["Vfx_Stop", "active"]) or []:
                    if name == "active" and not self.ic.get("match_turret_head_team_keys", False):
                        continue            # 2026-10-29 (power-core-turret.md 8.7): no team keys on the heads
                    if name == "active":
                        name = "Vfx_Active_Blue" if ally else "Vfx_Active_Red"
                    self.w.scriptlet(head, name, f"{head.name}: {name} (0x8d, target lost)")

    def _own_head_key(self, mu):
        """The body's Vfx_AI_Active key when the structure's head is the client's own child of it (no server head,
        the role plays Vfx_AI_Active and the body's tables hold it), else 0."""
        if getattr(mu, "head", None) is not None:
            return 0
        if "Vfx_AI_Active" not in ((self.ic.get("match_structure_scriptlets") or {}).get(mu.role) or ()):
            return 0
        key = self.w.data.scriptlet_key("Vfx_AI_Active")
        keys = mu.ent.scriptlet_keys
        return key if key and (keys is None or key in keys) else 0

    def _head_rearm_later(self, mu):
        """2026-10-30 tester report 18:12 ("the heads of the towers got lost" again; turret-death-head-rearm.md 1): after
        a fight ([ics] match_turret_head_rearm "after" s with no new target) the body's Vfx_AI_Active runs are stopped
        (0x11F, every run of the key) and a new run makes the client head again; once per "min_gap" s."""
        cfg = self.ic.get("match_turret_head_rearm") or {}
        key = self._own_head_key(mu) if cfg else 0
        if not key:
            return
        ent = mu.ent
        gap = float(cfg.get("min_gap", 20.0) or 0.0)

        def start():
            if ent.eid in self.w.entities and ent.alive:
                self.w.scriptlet(ent, key, f"{ent.name}: Vfx_AI_Active (0x8d, head re-arm)")

        def go():
            if ent.eid not in self.w.entities or not ent.alive or mu.target is not None:
                return
            if self.m.t - getattr(mu, "head_rearmed_at", -1e9) < gap:
                return
            mu.head_rearmed_at = self.m.t
            self.w.live_scriptlets.pop((ent.eid, key), None)
            self.w.send(f"{ent.name}: stop Vfx_AI_Active (0x11f, head re-arm)", M.stop_scriptlet(ent.eid, key, 0xFFFFFFFF))
            self.m.later(float(cfg.get("gap", 0.2) or 0.0), start)
        self.m.later(float(cfg.get("after", 3.0) or 0.0), go)

    def _drop_target(self, mu):
        """2026-10-23 23:10 (tester's screenshot: the turret's targeting line stays on a champion until it dies or the
        turret falls): a turret that loses its target out of range dropped it here without Target_Lost, so the client
        kept the line; every drop of a shooter's target now goes through _turret_target(None)."""
        if mu.role in SHOOTERS and mu.target is not None and self.ic.get("match_turret_lost_on_drop", True):
            self._turret_target(mu, None)
        mu.target = None

    def _init_scripts(self, mu):
        """2026-10-23 09:45 (tester: no turret shots seen, yet health lost): raise the attack script's init event
        so it loads its range / stats and fires its visible shot (turret 0x34000014 S3 RunScriptlet 0x100002E0)."""
        ev = int(self.ic.get("match_unit_init_event", EVENT_UNIT_INIT) or 0)
        if ev:
            self.w.raise_event(mu.ent, ev)

    def _properties(self, mu):
        ent, ud = mu.ent, self.ud
        tpl = ud.template(mu.cls)
        role = "minion" if mu.role in ("minion", "camp") else mu.role
        props = {p[0]: p for p in ent.extra_props}
        if ent.kind != "unit":
            # a unit gets team and LifeState from World.properties (creature_properties)
            props[PROP_TEAM] = (PROP_TEAM, KIND_INT, mu.team)
        props[PROP_SIDE] = (PROP_SIDE, KIND_ENUM, ent.side)
        props[PROP_ON_MAP] = (PROP_ON_MAP, KIND_BOOL, 1)
        category = ud.first(mu.cls, PROP_MAP_CATEGORY) or maps.MINIMAP.get(role)
        if category and mu.role != "camp":
            props[PROP_MAP_CATEGORY] = (PROP_MAP_CATEGORY, KIND_ENUM, int(category))
        if ent.kind == "unit" and mu.team in (maps.T1, maps.T2) and self.ic.get("match_unit_vision", True):
            # 2026-10-23 10:11 (tester: the minions have no field of vision): fog-of-war vision source radius
            props[PROP_VISION] = (PROP_VISION, KIND_F32, float(mu.vision))
        if ent.kind == "unit" and self.ic.get("unit_attack_speed_property", True):
            # 2026-10-25 (sweep-property-listeners.md, C binding): 0x100006FE is the only animation-graph variable the
            # server feeds (Attribute_AttackSpeed, bound in 111 graphs: the attack clips' speed)
            props[0x100006FE] = (0x100006FE, KIND_F32, float(ent.stats.get(0x100006FE) or 1.0) or 1.0)
        if ent.kind == "structure":
            props[PROP_LIFE] = (PROP_LIFE, KIND_ENUM, M.LIFE_ALIVE)
            if self.ic.get("turret_warning", True):
                # 2026-10-25 (tester's screenshots: the green / yellow / red ring around an enemy turret;
                # crime-alley-props.md C, decompiled 0xA7CA20): the client registers a structure for its warning ring
                # only at entity add, when it has bool 0x10000C5D; 0x10000C5B = armed (false = always green)
                props[0x10000C5D] = (0x10000C5D, KIND_BOOL, 1)
                props[0x10000C5B] = (0x10000C5B, KIND_BOOL, 1 if self.ic.get("turret_warning_armed_at_start", True)
                                     else 0)
            if getattr(mu, "unarmed", False):
                # an unarmed structure (match_unarmed_roles, 2026-10-30): its template's 0x10000C5D = 1 would register
                # the warning ring (0xA7CA20 gate 0xA7CA81); false in the creation bundle, never armed
                props[0x10000C5D] = (0x10000C5D, KIND_BOOL, 0)
                props[0x10000C5B] = (0x10000C5B, KIND_BOOL, 0)
            if mu.team in (maps.T1, maps.T2):
                # allied structures are fog-of-war vision sources (full-maps-world.md 7.3)
                props[PROP_VISION] = (PROP_VISION, KIND_F32, float(mu.vision))
            if mu.team == self.m.local_team() and self.ic.get("vision_through_blockers", True) and \
                    self.ic.get("vision_through_blockers_property", True) and \
                    self.ic.get("vision_through_blockers_at_creation", True):
                # tester report 2026-10-29 21:10 (the fence strip still black; ca-fog-minimap-ring.md 1, C diag --fog):
                # our turrets / core ran the fog occluder pass all match although 0x100008CE came by 0x6; the foundry,
                # whose template holds it, did not. The value rides in the creation bundle ([ics]
                # vision_through_blockers_at_creation)
                props[0x100008CE] = (0x100008CE, KIND_BOOL, 1)
        if mu.role == "camp" and self.ic.get("match_camp_map_note", True):
            notes = {int(str(k), 0): v for k, v in (self.ic.get("match_camp_map_notes") or {}).items()}
            note = notes.get(mu.cls)
            if note:
                # tester report 2026-10-29 21:10 (78.png: the original v AI minimap marks each living camp with one
                # icon; ours had none; ca-fog-minimap-ring.md 4): the camp's heavy creature carries a minimap note
                # ([ics] match_camp_map_notes: class -> [category, icon]; the note goes with the creature's death)
                props[PROP_MAP_CATEGORY] = (PROP_MAP_CATEGORY, KIND_ENUM, int(str(note[0]), 0))
                if len(note) > 1 and int(str(note[1]), 0):
                    props[0x10000083] = (0x10000083, KIND_DID, int(str(note[1]), 0))
        flags = [v for v in tpl.get(PROP_FLAGS, []) if v != 8] or ([maps.PERCEIVED[mu.role]] if mu.role in maps.PERCEIVED
                                                                   else [])
        ring = (ent.kind == "structure" and flags and self.ic.get("turret_warning", True)
                and self.ic.get("turret_warning_flags_in_bundle", True))
        if ring:
            # tester report 2026-10-29 15:30 (no green / yellow / red ring around the enemy turrets; decompiled 0xA7CA20,
            # C): the ring manager registers a structure ONCE, at entity add (vtable 0x1605074 slot 1, no other caller;
            # listener 0xA8DFB0 only updates registered entries), and only if 0x9D0180(ent, 0x10) sees the Turret bit
            # (unit component [comp+0xA4], else property 0x1000019D) and the range 0x9CFC40 ([comp+0x8C], else
            # 0x10000133) gives (r + 1)^2 > 0. Our creation bundle had no 0x1000019D (it came as a change 6-10 s later,
            # traffic 15:17:47 / 15:17:53 / 15:17:57), so the turret was never registered. The unit flags now ride in
            # the creation bundle (the watcher 0x977490 registers with notify 1, P: seeded from the store) and go again
            # as a change (0, then the value) for the caches ([ics] turret_warning_flags_in_bundle)
            props[PROP_FLAGS] = (PROP_FLAGS, KIND_U32, int(flags[-1]))
            self.m.later(float(self.ic.get("unit_flags_delay", 0.8) or 0.8) + 0.2, lambda m=mu: self.refresh_flags(m))
            if PROP_VISION in props and mu.team != self.m.local_team() and self.ic.get("vision_as_change", True):
                # the ring's range is the same 0x10000133 cache: an enemy structure's radius as a change too
                self.m.later(float(self.ic.get("unit_flags_delay", 0.8) or 0.8) + 0.3,
                             lambda e=ent, r=float(mu.vision): self._late_vision(e, r))
        ent.extra_props = list(props.values())
        if PROP_VISION in props and mu.team == self.m.local_team() and self.ic.get("vision_as_change", True):
            # 2026-10-23 17:40 (fog-vision-runtime.md: the client stores 0x10000133 at unit component +0x8C only on a
            # change, so the creation bundle's value stays -1): 0, then the radius, by 0x6
            self.m.later(float(self.ic.get("unit_flags_delay", 0.8) or 0.8) + 0.3,
                         lambda e=ent, r=float(mu.vision): self._late_vision(e, r))
        if ent.kind == "structure" and mu.team in (maps.T1, maps.T2) and self.ic.get("team_as_change", True):
            # 2026-10-25 (stubborn-visuals.md 1: the dampener rig and the doors get their team colour only from
            # _Entity_OnSetClientRelationship 0x100003A6, run by the client's 0x1000009C listener 0xA813F0 on a CHANGE;
            # the creation bundle never fires it, so the tinted parts stayed black): 0, then the team, by 0x6
            self.m.later(float(self.ic.get("unit_flags_delay", 0.8) or 0.8) + 0.1,
                         lambda e=ent, t=mu.team: self.late_team(e, t))
        if flags and PROP_FLAGS not in props:
            # unit flags (PerceivedType) only register as a CHANGE (World._late_flags, fase3-gd): sent shortly after
            self.m.later(float(self.ic.get("unit_flags_delay", 0.8) or 0.8) + 0.2,
                         lambda e=ent, f=flags[-1]: self._late_flag(e, f))
        if getattr(ent, "wire_team", None) is not None and self.ic.get("match_camp_team_as_change", True):
            # 2026-10-28 15:00 (tester report 2026-10-28 15:00: grey jungle drones; camps-colour-bar-positions.md 1.3 /
            # 8.2.7): the client's team as a CHANGE too (the server's team, then the wire team), so 0xA813F0 tints it
            self.m.later(float(self.ic.get("unit_flags_delay", 0.8) or 0.8) + 0.1, lambda e=ent: self.late_wire_team(e))
        tags = [int(str(t), 0) for t in (self.ic.get("match_camp_vitals_tags") or ())] if mu.role == "camp" else []
        if tags:
            # 2026-10-28 15:00 (tester report 2026-10-28 15:00: no overhead bar over the camps; camps-colour-bar-
            # positions.md 8.3): FloatyVitals after the unit flags (+0.2 above), held while the camp phases in
            # (Match._camp_phase_end releases it after the flags); never in the creation bundle
            self.m.later(float(self.ic.get("unit_flags_delay", 0.8) or 0.8) + 0.25,
                         lambda e=ent, t=tags: self.late_vitals(e, t))

    def late_wire_team(self, ent):
        """A camp unit's client team as a change (camps-colour-bar-positions.md 1.3): the server's team (or any other
        value), then the wire team, by 0x6. Every bundle carries the wire team already, so no diff undoes it."""
        wire = getattr(ent, "wire_team", None)
        if wire is None or ent.eid not in self.w.entities or not ent.alive:
            return
        before = ent.team if ent.team != wire else (3 if wire != 3 else 0)
        self.w.send(f"{ent.name}: team {before} (0x6)", M.set_property(ent.eid, PROP_TEAM, KIND_INT, before))
        self.w.send(f"{ent.name}: team {wire} (0x6, the client's team)",
                    M.set_property(ent.eid, PROP_TEAM, KIND_INT, wire))

    def late_vitals(self, ent, tags):
        """FloatyVitals (camps-colour-bar-positions.md 8.3): the overhead bar's push gate 0x1000072C = 1 by 0x6, after
        the unit flags, and kept in extra_props (every later bundle carries it); a phasing camp unit gets it when its
        phase ends (Match._camp_phase_end), after its held flags."""
        if ent.eid not in self.w.entities or not ent.alive:
            return
        if getattr(ent, "hold_flags", False):
            ent.pending_vitals = list(tags)
            return
        ids = set(tags)
        ent.extra_props = [p for p in ent.extra_props if p[0] not in ids] + [(t, KIND_BOOL, 1) for t in tags]
        for t in tags:
            self.w.send(f"{ent.name}: FloatyVitals {t:#x} = 1 (0x6)", M.set_property(ent.eid, t, KIND_BOOL, 1))

    def refresh_flags(self, mu):
        """The unit flags again as a CHANGE: 0, then the value (the client caches them only when they change; diag
        --target 2026-10-23 14:49: the dampener, core turret and core were refused with cached flags 0)."""
        ent = mu.ent
        flags = next((p[2] for p in ent.extra_props if p[0] == PROP_FLAGS), 0)
        if not flags or ent.eid not in self.w.entities or not ent.alive:
            return
        self.w.send(f"{ent.name}: unit flags cleared (0x6)", M.set_property(ent.eid, PROP_FLAGS, KIND_U32, 0))
        self.w.send(f"{ent.name}: unit flags {flags:#x} again (0x6)", M.set_property(ent.eid, PROP_FLAGS, KIND_U32, flags))

    def late_team(self, ent, team):
        if ent.eid not in self.w.entities:
            return
        self.w.send(f"{ent.name}: team 0 (0x6)", M.set_property(ent.eid, PROP_TEAM, KIND_INT, 0))
        self.w.send(f"{ent.name}: team {team} (0x6)", M.set_property(ent.eid, PROP_TEAM, KIND_INT, team))

    def _late_vision(self, ent, radius):
        if ent.eid not in self.w.entities or not ent.alive:
            return
        self.w.send(f"{ent.name}: vision 0 (0x6)", M.set_property(ent.eid, PROP_VISION, KIND_F32, 0.0))
        self.w.send(f"{ent.name}: vision {radius:g} (0x6)", M.set_property(ent.eid, PROP_VISION, KIND_F32, radius))
        if ent.team == self.m.local_team():
            self.w.see_through_blockers(ent)          # ca-fog-ring-announcer.md 1

    def _late_flag(self, ent, flags):
        if ent.eid not in self.w.entities or not ent.alive:
            return
        if getattr(ent, "hold_flags", False):
            # 2026-10-28 13:52 (jungle-camps-spawn.md 3): a phasing camp unit gets its flags when the phase ends
            ent.pending_unit_flag = flags
            return
        ent.extra_props = [p for p in ent.extra_props if p[0] != PROP_FLAGS] + [(PROP_FLAGS, KIND_U32, flags)]
        self.w.send(f"{ent.name}: unit flags {flags:#x} (0x6)", M.set_property(ent.eid, PROP_FLAGS, KIND_U32, flags))

    def apply_stats(self, mu, refill=False):
        """The class's stats at its level (stat block + level formulas); health keeps its share."""
        ent = mu.ent
        stats = self.ud.stats_at(mu.cls, mu.level)
        if not stats:
            return
        ent.stats.update(stats)
        hp = stats.get(STAT_HEALTH)
        if hp and hp > 0:
            share = 1.0 if refill or not ent.max_health else (ent.health or 0) / ent.max_health
            ent.max_health = int(round(hp))
            ent.health = max(1, int(round(ent.max_health * share)))
        ms = stats.get(STAT_MOVE_SPEED)
        if ms:
            ent.move_speed = float(ms)

    def set_property(self, mu, prop, kind, value, label=None):
        ent = mu.ent
        ent.extra_props = [p for p in ent.extra_props if p[0] != prop] + [(prop, kind, value)]
        if ent.eid in self.w.entities:
            self.w.send(label or f"{ent.name}: {prop:#x} = {value} (0x6)", M.set_property(ent.eid, prop, kind, value))

    def remove(self, mu):
        if getattr(mu, "aggro_on", False):
            (self.w.__dict__.get("looping_scriptlets") or {}).pop((mu.ent.eid, self.w._config_key("CbtState_Aggro_Active")), None)
            mu.aggro_on = False
        self.by_eid.pop(mu.ent.eid, None)
        head = getattr(mu, "head", None)
        if head is not None and head.eid in self.w.entities:
            self.w.remove(head, f"{head.name} gone (0x3)")
        for part in getattr(mu, "parts", None) or ():
            if part.eid in self.w.entities:
                self.w.remove(part, f"{part.name} gone (0x3)")
        if self.w.nav is not None:
            self.w.nav.unblock(mu.ent.eid)

    # ---- queries -------------------------------------------------------------------------------------------------
    def champions(self):
        return [c for c in self.m.champions() if c.alive]

    def hostile(self, mu, other):
        team = other.team
        return team and team != mu.team and other.alive and other.health is not None

    def attackable(self, other):
        mu = getattr(other, "match_unit", None)
        if mu is None:
            return True
        return not mu.invulnerable and not self.m.protected(mu)

    def enemies_near(self, mu, radius, kinds=None):
        out = []
        p = mu.ent.pos
        # 2026-10-30 (tester report 15:30: "the enemy minions cannot attack my core"; core-door-regen.md 3): a structure
        # counts from its edge (its blocked footprint keeps a unit at least its radius from the centre; a melee minion's
        # 3 m sight never reached the core's centre from its 3 m rim). [ics] match_structure_sight_to_edge
        edge = bool(self.ic.get("match_structure_sight_to_edge", True))
        for other in list(self.by_eid.values()):
            e = other.ent
            if other is mu or not e.alive or not self.hostile(mu, e) or (kinds and other.role not in kinds):
                continue
            d = math.hypot(e.pos[0] - p[0], e.pos[1] - p[1])
            if edge and other.role in STRUCTURES:
                d -= float(other.radius or 0.0)
            if d <= radius:
                out.append(e)
        if kinds is None or "champion" in kinds:
            for c in self.champions():
                if not self.m.visible_to(c, mu.ent):
                    continue
                if self.hostile(mu, c) and math.hypot(c.pos[0] - p[0], c.pos[1] - p[1]) <= radius:
                    out.append(c)
        return sorted(out, key=lambda e: math.hypot(e.pos[0] - p[0], e.pos[1] - p[1]))

    def _reach(self, mu, target):
        tmu = getattr(target, "match_unit", None)
        return mu.range + (tmu.radius if tmu else 0.5)

    # ---- AI ------------------------------------------------------------------------------------------------------
    def think(self, mu, now):
        """Pick the target (priorities of the prototype and the parasite script 0x3400053A)."""
        role = mu.role
        if role in ("capture", "relay", "beacon", "device"):
            if role in ("capture", "device") and mu.team in (maps.T1, maps.T2) and mu.attack                     and self.ic.get("match_point_attack", True):
                # 2026-10-25 (map-objectives-recipes.md 2, C defaults of 0x340000D5: SkillRange 9, cooldown 0.6 s): an
                # owned Gotham Heights point / the held Doomsday Device shoots enemies in range with its attack
                reach = float(self.ic.get("match_point_attack_range", 9.0))
                mu.range = reach
                t = mu.target
                if t is not None and (not t.alive or not self.hostile(mu, t) or mu.ent.distance_to(t) > reach + 0.5):
                    t = None
                if t is None:
                    cands = [e for e in self.enemies_near(mu, reach) if self.attackable(e)]
                    t = cands[0] if cands else None
                mu.target = t
            elif mu.target is not None:
                mu.target = None
            mu.next_think = now + self.rng.uniform(*self.retarget)
            return
        if getattr(mu, "unarmed", False):
            if mu.target is not None:
                if role in SHOOTERS:
                    self._turret_target(mu, None)
                mu.target = None
            mu.next_think = now + self.rng.uniform(*self.retarget)
            return
        sight = max(mu.vision, mu.range + 1.0)
        aggressor = self.m.champion_aggressor(mu.team, mu.ent.pos, sight)
        t = mu.target
        if t is not None and not self._valid(mu, t):
            t = None
        if role in SHOOTERS:
            # a structure: an enemy champion hitting an allied champion first, else the closest minion, else champion
            if aggressor is not None and mu.ent.distance_to(aggressor) <= self._reach(mu, aggressor):
                t = aggressor
            elif t is None:
                cands = [e for e in self.enemies_near(mu, mu.range + 1.0) if self.attackable(e)]
                if self.ic.get("match_turret_pick_in_reach", True):
                    # 2026-10-30 tester report 11:23 ("the turrets' top part disappears when they are attacked";
                    # scorecard-panel-turret-head.md 2, C traffic): a candidate between its reach (range + its radius,
                    # what act() checks) and range + 1 m was picked here and dropped by act() in the same tick, so the
                    # body got Target_Acquired + Target_Lost 1 ms apart, ~1.4 times a second (127 pairs in the run);
                    # each pair starts and stops Vfx_Targeting on the turret and its client-made head. Only targets
                    # within the reach act() keeps (false = the fase3-ip pick)
                    cands = [e for e in cands if mu.ent.distance_to(e) <= self._reach(mu, e)]
                minions = [e for e in cands if getattr(e, "match_unit", None) and e.match_unit.role in ("minion", "camp")]
                t = (minions or cands or [None])[0]
        elif role == "camp":
            if t is None and mu.camp is not None and mu.camp.provoker is not None and self._valid(mu, mu.camp.provoker):
                t = mu.camp.provoker
        else:   # minion
            leash = self._leash_on(mu)
            if leash and t is not None and self._leash_broken(mu, t, sight, now):
                t = None
            if leash and now < mu.returning_until:
                t = None                         # walking back to its lane: no new target until it is there
            elif aggressor is not None and not (leash and self._ignored(mu, aggressor, now)):
                t = aggressor
            elif t is None or getattr(t, "match_unit", None) is None or t.match_unit.role in STRUCTURES:
                order = (("minion",), ("champion",), STRUCTURES)
                for kinds in order:
                    cands = [e for e in self.enemies_near(mu, sight, kinds) if self.attackable(e)
                             and not (leash and self._ignored(mu, e, now))]
                    if cands:
                        t = cands[0]
                        break
            if leash and t is not None and mu.leash_from is None and not (
                    getattr(t, "match_unit", None) is not None and t.match_unit.role in STRUCTURES):
                # where it leaves its lane (a minion already off its lane measures from the nearest lane point)
                mu.leash_from = self._lane_point_near(mu)
        if t is not mu.target:
            if role in SHOOTERS:
                self._turret_target(mu, t)
            mu.target = t
            mu.path = []
        mu.next_think = now + self.rng.uniform(*self.retarget)

    # ---- leash (minions) -------------------------------------------------------------------------------------------
    # 2026-10-29 (tester report 2026-10-29 15:30: "in Crime Alley I can pull a wave around and bring it behind my
    # tower"): the AI data has no leash / chase / aggro distance (units-and-ai.md 5.1, C: 0x3A000026 holds only
    # GetBestPerceivedTargetInterval 0.5 / 0.8 and AIActive; the decision logic was server code). A lane minion keeps a
    # target only while it is within its acquisition range (its vision 0x10000133, at least its attack reach + 1) +
    # match_minion_chase_margin, and only while it is within match_minion_leash_anchor m of the point where it left
    # its lane; past either it drops the target, ignores it for match_minion_leash_ignore s and walks back to its lane
    # taking no new target until it is within match_minion_lane_rejoin m of the lane (at most match_minion_return_max
    # s). Structures as targets are never leashed (the lane leads to them). [ics] match_leash_rules = false: as before.
    def _leash_on(self, mu):
        return mu.role == "minion" and bool(mu.lane_points) and bool(self.ic.get("match_leash_rules", True))

    def _ignored(self, mu, e, now):
        until = mu.ignore.get(getattr(e, "eid", 0))
        return until is not None and now < until

    def lane_distance(self, mu, pos=None):
        """Distance from a point (default: the unit) to its lane polyline."""
        p = pos or mu.ent.pos
        pts = mu.lane_points
        if not pts:
            return 0.0
        if len(pts) == 1:
            return math.hypot(pts[0][0] - p[0], pts[0][1] - p[1])
        best = 1e9
        for a, b in zip(pts, pts[1:]):
            dx, dy = b[0] - a[0], b[1] - a[1]
            ll = dx * dx + dy * dy
            u = 0.0 if ll <= 0 else max(0.0, min(1.0, ((p[0] - a[0]) * dx + (p[1] - a[1]) * dy) / ll))
            best = min(best, math.hypot(a[0] + u * dx - p[0], a[1] + u * dy - p[1]))
        return best

    def _leash_broken(self, mu, t, sight, now):
        """True when the minion must drop t (out of its acquisition range, or too far from where it left the lane);
        it then ignores t for a while and walks back to its lane."""
        tmu = getattr(t, "match_unit", None)
        if tmu is not None and tmu.role in STRUCTURES:
            return False
        chase = sight + float(self.ic.get("match_minion_chase_margin", 1.5))
        anchor = float(self.ic.get("match_minion_leash_anchor", 8.0))
        far = mu.ent.distance_to(t) > chase
        p = mu.ent.pos
        strayed = mu.leash_from is not None and math.hypot(p[0] - mu.leash_from[0], p[1] - mu.leash_from[1]) > anchor
        if not far and not strayed:
            return False
        mu.ignore[getattr(t, "eid", 0)] = now + float(self.ic.get("match_minion_leash_ignore", 4.0))
        mu.returning_until = now + float(self.ic.get("match_minion_return_max", 6.0))
        mu.leash_from = None
        self.m.log(f"{mu.ent.name}: leash, drops {getattr(t, 'name', t)} ("
                   + ("out of its range" if far else f"more than {anchor:g} m from its lane") + "), back to its lane")
        return True

    def _lane_point_near(self, mu):
        """The point of the lane polyline nearest to the unit."""
        p = mu.ent.pos
        pts = mu.lane_points
        best, out = 1e9, (p[0], p[1])
        for a, b in zip(pts, pts[1:] or pts):
            dx, dy = b[0] - a[0], b[1] - a[1]
            ll = dx * dx + dy * dy
            u = 0.0 if ll <= 0 else max(0.0, min(1.0, ((p[0] - a[0]) * dx + (p[1] - a[1]) * dy) / ll))
            q = (a[0] + u * dx, a[1] + u * dy)
            d = math.hypot(q[0] - p[0], q[1] - p[1])
            if d < best:
                best, out = d, q
        return out

    def _leash_tick(self, mu, now):
        """While returning: the return ends once the minion is back by its lane (or after match_minion_return_max s)."""
        if mu.returning_until and (now >= mu.returning_until
                                   or self.lane_distance(mu) <= float(self.ic.get("match_minion_lane_rejoin", 2.0))):
            mu.returning_until = 0.0
        if mu.target is None and mu.leash_from is not None and mu.returning_until == 0.0 \
                and self.lane_distance(mu) <= float(self.ic.get("match_minion_lane_rejoin", 2.0)):
            mu.leash_from = None
        if mu.ignore:
            mu.ignore = {k: v for k, v in mu.ignore.items() if v > now}

    def _valid(self, mu, t):
        if not t.alive or t.health is None or not self.attackable(t):
            return False
        if t is not self.w.champion and t.eid not in self.w.entities:
            return False
        if mu.role in SHOOTERS:
            return mu.ent.distance_to(t) <= self._reach(mu, t) + 0.5
        if self._leash_on(mu):
            return True                      # the minion's leash and chase range (_leash_broken) decide
        leash = float(self.ic.get("match_camp_leash" if mu.role == "camp" else "match_minion_leash", 12.0))
        anchor = mu.home if mu.role == "camp" else None
        if anchor is not None and math.hypot(mu.ent.pos[0] - anchor[0], mu.ent.pos[1] - anchor[1]) > leash:
            return False
        return mu.ent.distance_to(t) <= max(leash, mu.vision + 2.0)

    def act(self, mu, dt, now):
        """Move or attack this tick."""
        ent = mu.ent
        t = mu.target
        if t is not None and (not t.alive or (t is not self.w.champion and t.eid not in self.w.entities)):
            self._drop_target(mu)
            t = None
        if mu.shuffle is not None:
            if t is not None and ent.distance_to(t) <= self._reach(mu, t):
                self.attack(mu, t, now)        # sliding aside (separation): it faces its target when it stops
                return
            idle = t is None and ((mu.role == "camp" and (mu.home is None or ent.distance_to(mu.home) <= 0.75))
                                  or (mu.role == "minion" and not mu.path and not mu.lane_points))
            if idle:
                return                         # nowhere to walk: the slide ends by itself
            self._end_shuffle(mu, now)         # it walks on: the step sends its own start state
        if t is not None:
            if ent.distance_to(t) > self._reach(mu, t):
                if ent.move_speed <= 0:
                    self._drop_target(mu)
                    return
                if not mu.path or now >= mu.repath_at:
                    mu.repath_at = now + 0.5
                    self._route(mu, t.pos)
                self.step(mu, dt, now)
                return
            face = math.atan2(t.pos[1] - ent.pos[1], t.pos[0] - ent.pos[0])
            turn = float(self.ic.get("match_attack_face_turn", 0.15) or 0.0)
            if mu.moving:
                mu.path = []
                if turn > 0:
                    ent.heading = face        # the stop state carries the turn toward the target
                self.stop(mu, now)
            elif turn > 0 and ent.move_speed > 0 and abs(math.remainder(face - getattr(mu, "sent_heading", ent.heading),
                                                                        math.tau)) > turn:
                # 2026-10-29 tester report 19:55 ("the minions attack me but never turn toward me"; minion-attack-
                # facing.md, C code: the stop state went with the walking heading, the turn toward the target was set
                # after it and never sent, and a standing minion's turns as its target moved were never sent either):
                # one stop state with the new facing when it is more than [ics] match_attack_face_turn rad from the
                # facing the client was last sent (0 = never, as before). Structures (move speed 0) keep theirs.
                ent.heading = face
                self.send_state(mu, now)
            ent.heading = face
            self.attack(mu, t, now)
            return
        # no target
        if mu.role == "minion":
            if not mu.path:
                self.resume_lane(mu)
            self.step(mu, dt, now)
        elif mu.role == "camp" and mu.home is not None:
            if mu.camp is not None and mu.camp.provoker is not None and not self._valid(mu, mu.camp.provoker):
                mu.camp.provoker = None              # the champion left (leash): the camp resets
            if ent.distance_to(mu.home) > 0.75:
                if not mu.path:
                    self._route(mu, mu.home)
                self.step(mu, dt, now)
            else:
                mu.path = []                         # home (a last corner within 0.75 m stayed and blocked the heal)
                if mu.moving:
                    self.stop(mu, now)
            if not mu.path and (mu.camp is None or mu.camp.provoker is None) and (ent.health or 0) < (ent.max_health or 0):
                ent.health = ent.max_health          # back home and unprovoked: a camp heals (leash reset)
                self.w.vitals(ent)
        elif mu.moving:
            self.stop(mu, now)

    def attack(self, mu, target, now):
        ent = mu.ent
        if now < mu.next_attack or now < ent.ready_at.get(0, 0.0):
            return
        speed = float(ent.stats.get(STAT_ATTACK_SPEED) or 1.0) or 1.0
        mu.next_attack = now + max(0.3, 1.0 / speed)
        if mu.direct_damage or not mu.attack or not ent.match_kit:
            amount = float(ent.stats.get(STAT_ATTACK_DAMAGE) or self.ic.get("unit_attack_damage", 10))
            self._direct_attack(mu, target, amount)
            return
        mu.casts_without_hit += 1
        if mu.casts_without_hit > int(self.ic.get("match_attack_fallback_after", 3) or 0) > 0:
            # 2026-10-22: the attack script dealt no damage in 3 swings (a node the runtime lacks): the AI deals the
            # unit's Attack Damage itself from now on ([ics] match_attack_fallback_after, 0 = never)
            mu.direct_damage = True
            self.m.log(f"{ent.name}: attack script {mu.attack.script:#x} deals no damage here; direct damage")
        ent.kit = ent.match_kit
        try:
            self.w.cast(ent, 0, target, None)
        finally:
            ent.kit = {}

    def _direct_attack(self, mu, target, amount):
        """The fallback attack: the shot's scriptlet for the client to see (turret 0x100002E0 Object_Ranged_Attack,
        ranged minion 0x10000326, with 0x10000030 = target and 0x100009EB = speed), the damage when it arrives.
        2026-10-23 09:45 (tester: health lost with no shot seen): the damage alone showed nothing."""
        ent, w = mu.ent, self.w
        keys = self.ic.get("match_attack_scriptlets") or {}
        key = int(keys.get(mu.role, keys.get("ranged" if mu.range > 3.0 else "melee", 0)) or 0)
        speed = float(self.ic.get("match_shot_speed", 20.0) or 0.0)
        delay = 0.0
        if key:
            variables = [(VAR_SHOT_TARGET, target)]
            if speed > 0 and mu.range > 3.0:
                variables.append((VAR_SHOT_SPEED, speed))
                delay = ent.distance_to(target) / speed
            # 2026-10-23 10:15 (tester: still no turret shot): sent the way the scripts send theirs (Batman's show),
            # the variable table typed by each property's kind
            CastWorld(w, ent, None).run_scriptlet(ent, key, target=target, variables=variables)
            if mu.role in SHOOTERS:
                # 2026-10-23 14:09 (tester's screenshot: the turret's targeting line shows, no projectile): the body's
                # Vfx_Basic_Ranged 0x1000029D too ([ics] match_turret_shot_extra)
                for extra in self.ic.get("match_turret_shot_extra") or ():
                    CastWorld(w, ent, None).run_scriptlet(ent, int(str(extra), 0), target=target, variables=variables)
        if delay <= 0:
            w.damage(ent, target, amount)
        else:
            self.m.later(delay, lambda: w.damage(ent, target, amount) if ent.alive and target.alive else None)

    def on_hit(self, source):
        mu = getattr(source, "match_unit", None)
        if mu is not None:
            mu.casts_without_hit = 0

    # ---- movement ------------------------------------------------------------------------------------------------
    def set_lane(self, mu, lane, points):
        mu.lane = lane
        mu.lane_points = [tuple(p) for p in points]
        mu.lane_i = 0
        mu.path = []
        self.resume_lane(mu)

    def resume_lane(self, mu):
        """Back onto the lane: the nearest lane point not behind the unit, then the rest of the lane."""
        pts = mu.lane_points
        if not pts:
            return
        p = mu.ent.pos
        best = min(range(mu.lane_i, len(pts)), key=lambda i: math.hypot(pts[i][0] - p[0], pts[i][1] - p[1]),
                   default=len(pts) - 1)
        # skip a point the unit has already passed (the next one is nearer than the segment between them)
        if best + 1 < len(pts):
            a, b = pts[best], pts[best + 1]
            if math.hypot(b[0] - p[0], b[1] - p[1]) < math.hypot(b[0] - a[0], b[1] - a[1]):
                best += 1
        mu.lane_i = best
        rest = [self._offset(mu, pts, i) for i in range(best, len(pts))]
        nav = self.w.nav
        if rest and nav is not None and not self.ic.get("match_lane_pathing", True):
            if not nav.line_clear(p, rest[0]):
                lead = nav.path(p[:2], rest[0]) or []
                rest = [tuple(q) for q in lead[:-1]] + rest
        elif rest and nav is not None:
            # 2026-10-23 16:20 (tester: the minions walk through the turrets): the lane points run along the lane's
            # centre, through the structures' blocked footprints; every leg that is not clear goes round on the mesh
            out, prev = [], p[:2]
            for q in rest:
                if not nav.line_clear(prev, q):
                    out += [tuple(v) for v in (nav.path(prev, q) or [q])]
                else:
                    out.append(q)
                prev = out[-1][:2]
            rest = out
        mu.path = rest

    def _offset(self, mu, pts, i):
        """Lane point i moved sideways by the unit's offset (perpendicular to the lane there)."""
        x, y = pts[i][:2]
        if not mu.offset:
            return (x, y)
        a = pts[max(0, i - 1)]
        b = pts[min(len(pts) - 1, i + 1)]
        dx, dy = b[0] - a[0], b[1] - a[1]
        d = math.hypot(dx, dy) or 1.0
        q = (x - dy / d * mu.offset, y + dx / d * mu.offset)
        nav = self.w.nav
        return q if nav is None or nav.walkable(*q) else (x, y)

    def _route(self, mu, goal):
        p = mu.ent.pos
        nav = self.w.nav
        if nav is None or nav.line_clear(p, goal):
            mu.path = [(goal[0], goal[1])]
            return
        pts = nav.path(p[:2], goal[:2])
        mu.path = [tuple(q) for q in pts] if pts else [(goal[0], goal[1])]

    def step(self, mu, dt, now):
        ent = mu.ent
        if not mu.path or ent.move_speed <= 0:
            if mu.moving:
                self.stop(mu, now)
            return
        left = ent.move_speed * dt
        corner = not mu.moving
        while left > 0 and mu.path:
            tx, ty = mu.path[0][:2]
            dx, dy = tx - ent.pos[0], ty - ent.pos[1]
            d = math.hypot(dx, dy)
            if d <= left:
                ent.pos = [tx, ty, ent.pos[2]]
                left -= d
                mu.path.pop(0)
                if mu.lane_points and mu.lane_i < len(mu.lane_points):
                    lp = mu.lane_points[mu.lane_i]
                    if math.hypot(lp[0] - tx, lp[1] - ty) < 1.5:
                        mu.lane_i += 1
                corner = True
            else:
                ent.pos = [ent.pos[0] + dx / d * left, ent.pos[1] + dy / d * left, ent.pos[2]]
                left = 0
        if not mu.path:
            self.stop(mu, now)
            return
        nx, ny = mu.path[0][:2]
        heading = math.atan2(ny - ent.pos[1], nx - ent.pos[0])
        turn = abs((heading - ent.heading + math.pi) % (2 * math.pi) - math.pi)
        corner = corner or turn > 0.26          # a chase that turns: the client extrapolates the old heading
        ent.heading = heading
        ent.speed = ent.move_speed
        mu.moving = True
        refresh = float(self.ic.get("match_move_refresh", 1.0) or 0)
        if corner or (refresh > 0 and now - mu.state_at >= refresh):
            self.send_state(mu, now)

    def stop(self, mu, now):
        mu.moving = False
        mu.ent.speed = 0.0
        self.send_state(mu, now)

    def send_state(self, mu, now):
        """One movement state (client-movement.md 1.4): position, heading, speed at the game clock."""
        mu.state_at = now
        ent = mu.ent
        if ent.eid not in self.w.entities:
            return
        mu.sent_heading = ent.heading
        mu.sent_pos = (ent.pos[0], ent.pos[1])
        mu.sent_speed = float(ent.speed or 0.0)
        if str(self.ic.get("match_move_message", "bundle")) == "b0":
            self.w.send(None, M.pvp_movement_state(ent.eid, time.time(), self.w.wire_position(ent), ent.heading,
                                                   ent.speed, module=ent.module, second_seq=1 if self.w.in_world else 0))
        else:
            self.w.update(ent, f"{ent.name}: state ({ent.pos[0]:.1f}, {ent.pos[1]:.1f}) speed {ent.speed:g}")

    # ---- the tick ------------------------------------------------------------------------------------------------
    def tick(self, dt, now):
        for mu in list(self.by_eid.values()):
            if not mu.ent.alive:
                continue
            if mu.role == "minion" and (mu.returning_until or mu.leash_from is not None or mu.ignore):
                self._leash_tick(mu, now)
            if now >= mu.next_think:
                self.think(mu, now)
            self.act(mu, dt, now)
            self.aggro_indicator(mu)
        if self.ic.get("match_unit_separation", True):
            self.separate(dt, now)

    # ---- separation (crowd) --------------------------------------------------------------------------------------
    # 2026-10-30 tester report 13:18 ("the minions pass through each other, they have no collisions"; unit-separation-
    # pick-body.md 1): the client does not push one replayed unit out of another (client-movement.md 1.3: a remote
    # unit is placed from the server's states), so the server keeps them apart. Every tick, after the AI moved them,
    # each unit of [ics] match_separation_roles is pushed out of every body it overlaps, found through a uniform grid
    # (cell = 2 x the largest radius, O(n)): other units (half each), champions, bots and structures (all of it on the
    # unit). Radii are the attack radii (World._attack_radius: a structure's / minion's match_unit.radius, champions
    # [ics] attack_body_radius), so bodies touch where the reach is counted. Against its own target the distance kept
    # is at most its reach - 0.05 (never pushed out of range: no walk-back oscillation). A walking unit is moved aside
    # at most match_separation_push x its step (a push against its walk becomes a sidestep) and gets a new state only
    # when the client's dead reckoning is match_separation_resync m off; a standing unit at least
    # match_separation_shuffle_min m deep slides to its free spot (one start state, one stop state facing its target),
    # kept within its reach of the target. A push never ends on an unwalkable cell. false = bodies overlap (as before).
    # 2026-10-30 (test_match "around the target" regressed when the turret parts / platform shifted every entity id:
    # the old balance hung on the id-seeded spread directions; unit-separation-pick-body.md 4): a unit is not shoved by
    # the units attacking it (match_separation_target_holds: the attacker takes the whole overlap; mutual targets half
    # each), so a crowd no longer pushes its target along and chases it; a standing unit pinned between two bodies
    # (opposite pushes cancel below shuffle_min while one alone is deeper) steps sideways (match_separation_unpin).
    def _body_radius(self, ent):
        r = self.w._attack_radius(ent) if hasattr(self.w, "_attack_radius") else 0.0
        return float(r or 0.5)

    def separate(self, dt, now):
        ic, w = self.ic, self.w
        roles = set(ic.get("match_separation_roles") or ("minion", "camp"))
        for mu in list(self.by_eid.values()):
            if mu.shuffle is not None:
                self._shuffle_step(mu, dt, now)
        movers = [mu for mu in self.by_eid.values() if mu.role in roles and mu.ent.alive and mu.ent.kind == "unit"
                  and mu.ent.move_speed > 0 and mu.ent.eid in w.entities]
        if not movers:
            return
        skip = ("capture", "relay", "beacon", "device")
        ents = list(w.entities.values())
        if w.champion is not None and w.champion.eid not in w.entities:
            ents.append(w.champion)
        bodies = []
        for e in ents:
            if not e.alive or e.kind not in ("unit", "champion", "structure"):
                continue
            emu = getattr(e, "match_unit", None)
            if emu is not None and emu.role in skip:
                continue
            bodies.append((e, self._body_radius(e)))
        small = max([r for e, r in bodies if e.kind == "unit"] or [0.5])
        cell = max(1.0, 2.0 * small)
        grid = {}
        for e, r in bodies:
            # a body goes into every cell from which a unit can touch it: the unit's own cell finds every overlap
            reach = r + small
            i0, i1 = int(math.floor((e.pos[0] - reach) / cell)), int(math.floor((e.pos[0] + reach) / cell))
            j0, j1 = int(math.floor((e.pos[1] - reach) / cell)), int(math.floor((e.pos[1] + reach) / cell))
            for i in range(i0, i1 + 1):
                for j in range(j0, j1 + 1):
                    grid.setdefault((i, j), []).append((e, r))
        mover_ids = {mu.ent.eid for mu in movers}
        slack = float(ic.get("match_separation_slack", 0.05))
        holds = bool(ic.get("match_separation_target_holds", True))
        unpin = bool(ic.get("match_separation_unpin", True))
        shuffle_min = float(ic.get("match_separation_shuffle_min", 0.15))
        for mu in movers:
            ent = mu.ent
            if mu.shuffle is not None or (mu.role == "camp" and mu.target is None and not mu.moving):
                continue                     # a camp resting at its home spot keeps its data placement
            x, y = ent.pos[0], ent.pos[1]
            r0 = self._body_radius(ent)
            px = py = 0.0
            big = (0.0, 0.0, 0.0)            # the deepest single push (size, x, y)
            for e, r in grid.get((int(math.floor(x / cell)), int(math.floor(y / cell))), ()):
                if e is ent:
                    continue
                need = r0 + r
                if e is mu.target:
                    need = min(need, self._reach(mu, e) - 0.05)
                emu = getattr(e, "match_unit", None)
                if emu is not None and emu.target is ent and emu.role in roles:
                    need = min(need, self._reach(emu, ent) - 0.05)
                dx, dy = x - e.pos[0], y - e.pos[1]
                d = math.hypot(dx, dy)
                if need <= 0 or d >= need - slack:
                    continue
                share = 0.5 if e.eid in mover_ids else 1.0
                if holds and share == 0.5:
                    # a unit is not shoved by the units attacking it (it holds its ground, the attacker takes the whole
                    # overlap) unless it attacks that unit too (half each): see the 2026-10-30 note in the block comment
                    mine = mu.target is e
                    theirs = emu is not None and emu.target is ent
                    if theirs and not mine:
                        continue
                    if mine and not theirs:
                        share = 1.0
                if d < 1e-4:
                    a = (ent.eid % 9973) * 2.399963      # the same spot: a fixed direction per unit (golden angle)
                    dx, dy, d = math.cos(a), math.sin(a), 1.0
                    k = need * share
                else:
                    k = (need - d) * share / d
                px += dx * k
                py += dy * k
                if abs(k) * d > big[0]:
                    big = (abs(k) * d, dx * k, dy * k)
            if px == 0.0 and py == 0.0:
                continue
            if mu.moving:
                self._push_walking(mu, px, py, dt, now)
            elif unpin and math.hypot(px, py) < shuffle_min <= big[0]:
                # pinned: pushed about as hard from opposite sides (a minion between its target and the one behind
                # it), so the pushes cancel while it overlaps both; it steps sideways out of the line, the deepest
                # push's size, to the side the pushes lean it to (a fixed side per unit on an exact tie)
                bx, by = big[1] / big[0], big[2] / big[0]
                side = -by * px + bx * py
                sgn = 1.0 if side > 1e-6 or (abs(side) <= 1e-6 and ent.eid % 2) else -1.0
                self._push_standing(mu, -by * sgn * big[0], bx * sgn * big[0], now)
            else:
                self._push_standing(mu, px, py, now)

    def _free(self, a, b):
        """A push may end at b: walkable, or the unit already stands off the mesh (it is never trapped)."""
        nav = self.w.nav
        return nav is None or nav.walkable(b[0], b[1]) or not nav.walkable(a[0], a[1])

    def _push_walking(self, mu, px, py, dt, now):
        ent = mu.ent
        cap = max(0.02, ent.move_speed * dt * float(self.ic.get("match_separation_push", 0.75)))
        fx, fy = math.cos(ent.heading), math.sin(ent.heading)
        along = px * fx + py * fy
        if along < 0:
            # pushed back against its walk (a body in the way): the same amount sideways, to the side it leans to
            side = -fy * px + fx * py
            sgn = 1.0 if side > 0 or (side == 0 and ent.eid % 2) else -1.0
            px, py = px - along * fx - sgn * along * -fy, py - along * fy - sgn * along * fx
        m = math.hypot(px, py)
        if m > cap:
            px, py = px / m * cap, py / m * cap
        q = (ent.pos[0] + px, ent.pos[1] + py)
        if not self._free(ent.pos, q):
            return
        ent.pos = [q[0], q[1], ent.pos[2]]
        if mu.sent_pos is not None:
            t = max(0.0, now - mu.state_at)
            sh = getattr(mu, "sent_heading", ent.heading)
            ex = mu.sent_pos[0] + math.cos(sh) * mu.sent_speed * t
            ey = mu.sent_pos[1] + math.sin(sh) * mu.sent_speed * t
            if math.hypot(ex - q[0], ey - q[1]) > float(self.ic.get("match_separation_resync", 0.4)):
                self.send_state(mu, now)

    def _push_standing(self, mu, px, py, now):
        ent = mu.ent
        if math.hypot(px, py) < float(self.ic.get("match_separation_shuffle_min", 0.15)):
            return False
        m = math.hypot(px, py)
        most = 2.0 * self._body_radius(ent)
        if m > most:
            px, py = px / m * most, py / m * most        # a pile on one spot: at most one body width per slide
        gx, gy = ent.pos[0] + px, ent.pos[1] + py
        t = mu.target
        if t is not None:
            lim = self._reach(mu, t) - 0.1
            dx, dy = gx - t.pos[0], gy - t.pos[1]
            d = math.hypot(dx, dy)
            if lim > 0 and d > lim:
                gx, gy = t.pos[0] + dx / d * lim, t.pos[1] + dy / d * lim
        if math.hypot(gx - ent.pos[0], gy - ent.pos[1]) < 0.05 or not self._free(ent.pos, (gx, gy)):
            return False
        mu.shuffle = (gx, gy)
        mu.path = []
        ent.heading = math.atan2(gy - ent.pos[1], gx - ent.pos[0])
        ent.speed = ent.move_speed
        self.send_state(mu, now)
        return True

    def _shuffle_step(self, mu, dt, now):
        ent = mu.ent
        if not ent.alive or ent.eid not in self.w.entities:
            mu.shuffle = None
            return
        gx, gy = mu.shuffle
        dx, dy = gx - ent.pos[0], gy - ent.pos[1]
        d = math.hypot(dx, dy)
        step = ent.move_speed * dt
        if d > step:
            ent.pos = [ent.pos[0] + dx / d * step, ent.pos[1] + dy / d * step, ent.pos[2]]
            return
        ent.pos = [gx, gy, ent.pos[2]]
        self._end_shuffle(mu, now)

    def _end_shuffle(self, mu, now):
        """The slide is over (or the unit walks on): a stop state, facing its target."""
        mu.shuffle = None
        ent, t = mu.ent, mu.target
        if t is not None and t.alive:
            ent.heading = math.atan2(t.pos[1] - ent.pos[1], t.pos[0] - ent.pos[0])
        mu.moving = False
        ent.speed = 0.0
        self.send_state(mu, now)

    # ---- aggro indicator -----------------------------------------------------------------------------------------
    # 2026-10-29 (tester report 21:10, screenshot of the original: enemy minions that turn on the player after he hits
    # an enemy champion show golden chevrons over their heads; docs/re-notes/aggro-recall-scorepanel.md 1, C for the
    # data): every unit's common table 0x1D0000E8 holds CbtState_Aggro 0x10000D61 (onset: a 0.5 s type-8 overlay,
    # mesh 0x170011FB) and CbtState_Aggro_Active 0x10000D62 (while it lasts: type-8 overlay mesh 0x17001A92 in gold
    # 0xFF783A04 for an enemy unit, blue for an ally, plus two type-0x2E colour actions), both inside 0x22 containers on
    # 0x100000CE == 1 (P: the case word order is read like CbtState_KnockUp's LifeState == 4) and on the team colour
    # 0x100007A2 (5 enemy / 3 ally). 0x100000CE is the client's vitals-notify flag of the controlled agent (listener 0xAAFCD0: its
    # vitals then feed the HUD), so by default it rides as a variable of the two runs ([ics] match_aggro_flag_mode
    # "variable"; "property" = a 0x6 on the unit, which may feed the HUD with the minion's vitals; "none"). While a unit
    # of [ics] match_aggro_roles targets the local champion: the onset key, then the active key (held as a looping
    # key, re-sent after its bundles); when it drops him both keys are stopped by 0x11F (every run).
    def aggro_indicator(self, mu, force_off=False):
        roles = self.ic.get("match_aggro_roles", ["minion"]) or ()
        champ = self.w.champion
        want = (not force_off and mu.role in roles and mu.ent.alive and champ is not None and mu.target is champ
                and mu.ent.eid in self.w.entities)
        if bool(want) == bool(getattr(mu, "aggro_on", False)):
            return
        mu.aggro_on = bool(want)
        ent, w = mu.ent, self.w
        flag = int(str(self.ic.get("match_aggro_flag", "0x100000CE") or 0), 0)
        mode = str(self.ic.get("match_aggro_flag_mode", "variable") or "none")
        keys = [w._config_key(k) for k in (self.ic.get("match_aggro_scriptlets")
                                           or ["CbtState_Aggro", "CbtState_Aggro_Active"])]
        variables = [(flag, KIND_BOOL, True)] if flag and mode == "variable" else None
        if want:
            self.m.log(f"{ent.name}: aggro on {champ.name} (indicator)")
            if flag and mode == "property":
                self.set_property(mu, flag, KIND_BOOL, True, f"{ent.name}: aggro flag {flag:#x} = True (0x6)")
            for k in keys:
                name = w.data.scriptlet_names().get(k, f"{k:#x}") if k else ""
                if k and w.scriptlet(ent, k, f"{ent.name}: {name} (0x8d)", variables=variables)                         and k == keys[-1] and len(keys) > 1:
                    loops = w.__dict__.setdefault("looping_scriptlets", {})
                    loops[(ent.eid, k)] = (variables, time.time(), time.time() + 3600.0, 0)
            return
        if ent.eid not in w.entities:
            return
        self.m.log(f"{ent.name}: aggro off (indicator)")
        loops = w.__dict__.get("looping_scriptlets") or {}
        for k in reversed(keys):
            if not k:
                continue
            # a 0x8D signal stops nothing by itself (messages.stop_scriptlet): 0x11F ends every run of the key
            loops.pop((ent.eid, k), None)
            w.live_scriptlets.pop((ent.eid, k), None)
            w.send(f"{ent.name}: stop {w.data.scriptlet_names().get(k, hex(k))} (0x11f, aggro off)",
                   M.stop_scriptlet(ent.eid, k, 0xFFFFFFFF))
        if flag and mode == "property":
            self.set_property(mu, flag, KIND_BOOL, False, f"{ent.name}: aggro flag {flag:#x} = False (0x6)")

    def level_up(self, t):
        """Units and structures gain a level every 90 s of match time (their 0x100001D9 formula)."""
        for mu in list(self.by_eid.values()):
            if not mu.ent.alive:
                continue
            lv = self.ud.level_at(mu.cls, max(0.0, t))
            if lv != mu.level:
                mu.level = lv
                self.apply_stats(mu)
                self._init_scripts(mu)          # the same event re-reads the stats at the new level

    # ---- rewards (formulas of the killed unit's template, units-and-ai.md 3.3) ------------------------------------
    def rewards(self, victim_cls, victim_level, killer_level, receivers, last_hit=True, by_turret=False):
        n = max(1, receivers)
        xp = self.ud.reward(victim_cls, PROP_XP_FORMULA, KilledLevel=victim_level, KillerLevel=killer_level,
                            NumReceivers=n) or 0.0
        cr = self.ud.reward(victim_cls, PROP_CREDITS_FORMULA, KilledLevel=victim_level, KillerLevel=killer_level,
                            NumReceivers=n, LastHit=last_hit, DamagedByTurret=by_turret) or 0.0
        bounty = self.ud.reward(victim_cls, PROP_TEAM_BOUNTY) or 0.0
        return xp, cr, bounty
