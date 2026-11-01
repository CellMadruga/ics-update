"""Map bosses and scheduled objectives (docs/re-notes/map-objectives-recipes.md).

The spawn schedule of every boss, pod and the Gotham Heights cannon was C++ match rule on the original server, not data
(C: no script names them). What the data fixes is used as is: classes, capture radii, kill buffs (template 0x10000AC2),
announcer line keys and events, the cannon controller's timings (0x340002CF: 65 s neutral, 120 s lock, 4 impacts).
Times not in the data are config defaults ([ics] match_raider / match_pods / match_cannon, G).

- Crime Alley: the Raider 0x40000CA2 at the nook (its own script 0x34000670 drops the pad 0x40000C49 on death).
- Gotham Divided: two phase pods 0x40000A79; the Raider 0x40000938 comes out of one; capturing both pods (seismic mode)
  raises the Leviathan 0x40000937, which respawns.
- Gotham Heights: the Orbital Cannon 0x40000511, captured by presence; each firing takes team health from the enemy
  (4 x 125 = the 500 start), then 65 s neutral and 120 s locked.
- Any camp / boss with a kill buff (0x10000AC2) gives it to every champion of the killer's team.
"""
import math

from .. import messages as M
from .. import script_runtime as R
from ..world import CastWorld
from ..wire import KIND_INT
from . import maps
from .units import PROP_OWNER, heading_from_yaw

KILL_BUFF_PROPERTY = 0x10000AC2


def _did(v):
    return int(str(v), 0) if v not in (None, "") else 0


class BossCamp:
    """What Units / Match expect of a camp (provoker, members) for a single scheduled boss."""

    def __init__(self, name, home):
        self.spec = {"boss": True, "pos": tuple(home[:2]), "units": [], "kind": "boss", "name": name}
        self.index = -1
        self.members = []
        self.provoker = None


class Bosses:
    def __init__(self, match):
        self.m, self.ic = match, match.ic
        self.key = match.map.get("key", "")
        self.pods = []
        self.cannon = None
        self.leviathan_due = None

    # ---- helpers -------------------------------------------------------------------------------------------------
    def cfg(self, name):
        return ((self.ic.get(name) or {}).get(self.key)) or {}

    def at(self, t, fn):
        """Run fn at match time t (now if it is past)."""
        self.m.later(max(0.0, float(t) - self.m.t), fn)

    def lines_before(self, t, table):
        for off, key in (table or {}).items():
            self.at(float(t) + float(off), lambda k=int(str(key), 0): self.m.line(k))

    def event_voice(self, ev, team):
        """An announcer event (0x2039) for a team (its own / the other team's line by the set's columns)."""
        if not ev:
            return
        from .match import announcer_msgs
        ch = self.m.world.champion
        iid = ch.eid if ch is not None else 0
        self.m.voice_out(announcer_msgs(self.ic, int(ev), iid, iid, team, team == self.m.local_team()), event=int(ev))

    def spawn_boss(self, cls, pos, yaw, name, scriptlets=()):
        m = self.m
        neutral = int(self.ic.get("match_neutral_team", 3))
        heading = heading_from_yaw(float(yaw)) if yaw is not None else 0.0
        mu = m.units.spawn(int(cls), tuple(pos[:2]), neutral, "camp", heading=heading, name=name)
        camp = BossCamp(name, mu.ent.pos)
        mu.home = list(mu.ent.pos)
        mu.camp = camp
        camp.members.append(mu)
        mu.boss = name
        for k, key in enumerate(scriptlets):
            m.later(0.4 + 0.6 * k, lambda e=mu.ent, n=key: m.world.scriptlet(e, n, f"{e.name}: {n} (0x8d)")
                    if e.eid in m.world.entities else None)
        m.log(f"boss {name} ({int(cls):#x}) at ({pos[0]:.1f}, {pos[1]:.1f})")
        return mu

    def kill_buff(self, cls, killer):
        """The class's kill buff (template 0x10000AC2, C) on every champion of the killer's team (duration G)."""
        team = getattr(killer, "team", 0)
        owner = getattr(getattr(killer, "missile", None), "owner", None)
        if team not in (maps.T1, maps.T2) and owner is not None:
            team = getattr(owner, "team", 0)
        buff = int(self.m.ud.first(cls, KILL_BUFF_PROPERTY, 0) or 0)
        if not buff or team not in (maps.T1, maps.T2) or not self.ic.get("match_kill_buffs", True):
            return team
        seconds = float(self.ic.get("match_kill_buff_seconds", 120.0))
        w = self.m.world
        for c in self.m.champions():
            if c.team == team and c.alive:
                try:
                    R.apply_status(CastWorld(w, c, None), killer, c, buff, {"EffectDuration": seconds})
                except Exception as e:                 # noqa: BLE001 - a buff must never stop the match
                    self.m.log(f"kill buff {buff:#x} on {c.name} failed ({e!r})")
        self.m.log(f"kill buff {buff:#x} to team {team} for {seconds:g} s")
        return team

    # ---- start ---------------------------------------------------------------------------------------------------
    def beacon_trackers(self):
        """The beacon pips at the match start (neutral): the client shows nothing for them until a first status."""
        c = self.cfg("match_beacons")
        shown = set()
        for b in (c.get("by_class") or {}).values():
            slot = int((c.get("player_slots") or {}).get(str(b.get("slot", 1)), b.get("slot", 1)))
            if slot in shown:
                continue
            shown.add(slot)
            self.m.send(f"beacon slot {slot}: neutral (0x2069)",
                        M.pvp_tracker_status(0x0200000000000D00 + slot, 0, 0, 0, _did(b.get("icon", 0)), slot,
                                             int(c.get("category", 29)), 0))

    def start(self):
        if self.cfg("match_beacons").get("by_class"):
            self.beacon_trackers()
        if self.cfg("match_raider"):
            self._schedule_raider(self.cfg("match_raider"), float(self.cfg("match_raider").get("at", 300.0)))
        if self.cfg("match_pods"):
            c = self.cfg("match_pods")
            at = float(c.get("at", 600.0))
            self.lines_before(at, c.get("warn"))
            self.at(at, self._spawn_pods)
        if self.cfg("match_cannon"):
            self.at(float(self.cfg("match_cannon").get("at", 0.0)), self._spawn_cannon)

    # ---- Raider --------------------------------------------------------------------------------------------------
    def _schedule_raider(self, c, at, pos=None):
        if self.ic.get("raider_warn_when_free", True):
            # 2026-10-28 15:00 (tester report; test-2026-10-28-1439-sweep.md S10: the warnings 696 / 699 played at 270 /
            # 290 s while the middle camp held the Raider's pad, and no Raider came for the rest of the match): the first
            # warning waits until the pad is free, then the warnings and the spawn keep their lead times from then
            # ([ics] raider_warn_when_free; false = the fase3-ie schedule)
            lead = self._raider_lead(c)
            self.at(at - lead, lambda: self._raider_due(c, pos, lead))
            return
        self.lines_before(at, c.get("warn"))
        self.at(at, lambda: self._spawn_raider(c, pos))

    @staticmethod
    def _raider_lead(c):
        """s from the Raider's first warning to its spawn (its "warn" offsets: -30 / -10 -> 30)."""
        return max([0.0] + [-float(k) for k in (c.get("warn") or {})])

    def _raider_pad_taken(self):
        """The middle camp on the Raider's pad lives (crime-alley-jungle.md 6, G; Crime Alley with [ics]
        match_camp_centre only)."""
        middle = next((cp for cp in self.m.camps if cp.spec.get("middle")), None)
        return middle is not None and any(x.ent.alive for x in middle.members)

    def _raider_due(self, c, pos, lead):
        """[ics] raider_warn_when_free: the Raider's warnings and spawn start once its pad is free (polled every s)."""
        if self.m.over:
            return
        if self._raider_pad_taken():
            if not getattr(self, "_raider_waiting", False):
                self._raider_waiting = True
                self.m.log("raider: its pad is taken (the middle camp lives); the warnings wait until it is cleared")
            self.m.later(1.0, lambda: self._raider_due(c, pos, lead))
            return
        if getattr(self, "_raider_waiting", False):
            self._raider_waiting = False
            self.m.log(f"raider: its pad is free; warnings now, the Raider in {lead:g} s")
        at = self.m.t + lead
        self.lines_before(at, c.get("warn"))
        self.at(at, lambda: self._spawn_raider(c, pos))

    def _spawn_raider(self, c, pos=None):
        if self.m.over:
            return
        if self._raider_pad_taken():
            if self.ic.get("raider_warn_when_free", True):
                # the middle camp came back during the warnings (S10): they play again once the pad is free
                self._raider_due(c, pos, self._raider_lead(c))
                return
            # crime-alley-jungle.md 6 (G): the Raider takes the pad once the middle camp on it is cleared
            self.m.later(5.0, lambda: self._spawn_raider(c, pos))
            return
        mu = self.spawn_boss(_did(c["cls"]), pos or c.get("pos", (80.0, 80.0)), c.get("yaw"), "raider",
                             c.get("scriptlets", ["Vfx_Spawn_Event01", "Vfx_Spawn_PhasingComplete", "Vfx_Active"]))
        mu.boss_cfg = c
        if hasattr(self.m, "unlock_nook"):
            self.m.unlock_nook()                  # the relay's padlock goes with the Raider's arrival (deep-scan-maps.md)
        if c.get("spawned"):
            self.m.later(1.5, lambda: self.m.line(int(c["spawned"])))

    # ---- Gotham Divided pods and the Leviathan -------------------------------------------------------------------
    def _spawn_pods(self):
        c = self.cfg("match_pods")
        w = self.m.world
        self.pods = []
        for i, p in enumerate(c.get("pods", ())):
            self.m.remove_cover_at(p)                      # the pit's lid (black-ground-shapes.md 4.3)
            mu = self.m.units.spawn(_did(c.get("cls", 0x40000A79)), tuple(p[:2]), 0, "capture", name=f"pod {i}")
            mu.invulnerable = True
            pod = {"mu": mu, "name": ("upper", "lower")[i % 2], "control": 0.0, "owner": 0, "engaged": False,
                   "seismic": False}
            self.pods.append(pod)
            for k, key in enumerate(("Vfx_Spawn", "Vfx_SpawnIdle", "Vfx_TeamColor_SetNull")):
                self.m.later(0.4 + 0.8 * k, lambda e=mu.ent, n=key: w.scriptlet(e, n, f"{e.name}: {n} (0x8d)"))
        if c.get("landed"):
            self.m.line(int(c["landed"]))
        r = c.get("raider")
        if r and self.pods:
            pod = self.pods[0]["mu"].ent
            at = self.m.t + float(r.get("after", 60.0))
            self._schedule_raider(r, at, (pod.pos[0] + 3.0, pod.pos[1]))
            self.at(at, lambda e=pod: w.scriptlet(e, "Object_Activate", f"{e.name}: Object_Activate (0x8d)"))
        else:
            self._seismic_on()

    def _seismic_on(self):
        for pod in self.pods:
            pod["seismic"] = True
        self.m.log("pods: seismic mode (capturable)")

    def _pods_tick(self, dt):
        c = self.cfg("match_pods")
        radius = float(c.get("capture_radius", 6.0))
        seconds = float(c.get("capture_seconds", 10.0)) or 10.0
        for pod in self.pods:
            if not pod["seismic"] or pod["engaged"]:
                continue
            ent = pod["mu"].ent
            here = {t: sum(1 for ch in self.m.champions() if ch.alive and ch.team == t and ch.distance_to(ent) <= radius)
                    for t in (maps.T1, maps.T2)}
            if bool(here[maps.T1]) == bool(here[maps.T2]):
                continue
            team = maps.T1 if here[maps.T1] else maps.T2
            pod["control"] += dt / seconds * (1 if team == maps.T1 else -1)
            pod["control"] = max(-1.0, min(1.0, pod["control"]))
            if abs(pod["control"]) >= 1.0 and not pod["owner"]:
                pod["owner"] = team
                self._engage(pod, team)

    def _engage(self, pod, team):
        c = self.cfg("match_pods")
        m, w = self.m, self.m.world
        mu = pod["mu"]
        m.units.set_property(mu, PROP_OWNER, KIND_INT, team, f"pod {pod['name']}: owner {team} (0x10000456)")
        lines = (c.get("seismic") or {}).get(pod["name"]) or []
        # "in 30 s" at the capture, "-10 s", "initializing", "engaged" (C keys, times G)
        for at, key in zip((0.0, 20.0, 28.0, 30.0), lines):
            m.later(at, lambda k=int(key): m.line(k))
        m.later(30.0, lambda: self._engaged(pod))
        m.log(f"pod {pod['name']} captured by team {team}")

    def _engaged(self, pod):
        pod["engaged"] = True
        if self.pods and all(p["engaged"] for p in self.pods):
            lev = self.cfg("match_pods").get("leviathan") or {}
            if lev:
                lines = lev.get("lines") or []
                for k, key in enumerate(lines[:3]):
                    self.m.later(3.0 * k, lambda kk=int(key): self.m.line(kk))
                self.m.later(9.0, lambda: self._spawn_leviathan(lev, lines[3] if len(lines) > 3 else 0, "Leviathan_Spawn"))
                for p in self.pods:
                    self.m.world.scriptlet(p["mu"].ent, "Object_Deactivate", f"pod {p['name']}: Object_Deactivate (0x8d)")

    def _spawn_leviathan(self, lev, line, scriptlet):
        if self.m.over:
            return
        mu = self.spawn_boss(_did(lev.get("cls", 0x40000937)), lev.get("pos", (80.0, 80.0)), lev.get("yaw"), "leviathan",
                             [scriptlet, "Vfx_Active_State1"])
        mu.boss_cfg = lev
        if line:
            self.m.later(2.0, lambda: self.m.line(int(line)))

    # ---- Gotham Heights: the Orbital Cannon (0x340002CF timings, C) ----------------------------------------------
    def _spawn_cannon(self):
        c = self.cfg("match_cannon")
        mu = self.m.units.spawn(_did(c.get("cls", 0x40000511)), tuple(c.get("pos", (80.0, 74.0))), 0, "capture",
                                name="orbital cannon")
        mu.invulnerable = True
        self.cannon = {"mu": mu, "state": "unlocked", "control": 0.0, "owner": 0, "impacts": 0}
        self.m.world.scriptlet(mu.ent, "Vfx_TeamColor_SetNull", "cannon: Vfx_TeamColor_SetNull (0x8d)")
        if c.get("detected"):
            self.m.line(int(c["detected"]))
        self._cannon_tracker()

    def _cannon_tracker(self):
        cn = self.cannon
        c = self.cfg("match_cannon")
        self.m.send(f"tracker cannon: owner {cn['owner']} (0x2069)",
                    M.pvp_tracker_status(cn["mu"].ent.eid, cn["owner"], 0, 3 if cn["state"] != "unlocked" else 0, 0,
                                         int(c.get("tracker_slot", 1)), int(c.get("tracker_category", 27)), 0))

    def _cannon_tick(self, dt):
        cn = self.cannon
        if cn is None or cn["state"] != "unlocked":
            return
        c = self.cfg("match_cannon")
        ent = cn["mu"].ent
        radius = float(c.get("radius", 4.1))
        here = {t: sum(1 for ch in self.m.champions() if ch.alive and ch.team == t and ch.distance_to(ent) <= radius)
                for t in (maps.T1, maps.T2)}
        if bool(here[maps.T1]) == bool(here[maps.T2]):
            return
        team = maps.T1 if here[maps.T1] else maps.T2
        cn["control"] = max(-1.0, min(1.0, cn["control"] + dt / float(c.get("seconds", 10.0)) * (1 if team == 1 else -1)))
        if abs(cn["control"]) >= 1.0:
            self._cannon_fire(team)

    def _cannon_fire(self, team):
        cn, c, m = self.cannon, self.cfg("match_cannon"), self.m
        cn["state"], cn["owner"], cn["control"] = "fired", team, 0.0
        cn["impacts"] += 1
        enemy = 3 - team
        m.units.set_property(cn["mu"], PROP_OWNER, KIND_INT, team, f"cannon: owner {team} (0x10000456)")
        self._cannon_tracker()
        self.event_voice(c.get("fired_event", 54), team)
        tier = cn["impacts"]
        last = tier >= int(c.get("impacts", 4))
        strikes = 1 if last else tier
        delay = float(c.get("strike_delay", 5.0)) + (float(c.get("final_delay", 31.0)) if last else 0.0)
        for k in range(strikes):
            m.later(delay + 5.0 * k, lambda last_one=(k == strikes - 1): self._strike(enemy, last, last_one))
        m.log(f"cannon fired by team {team}: impact {tier}")
        m.later(float(c.get("neutral", 65.0)), self._cannon_neutral)

    def _strike(self, team, large, last_one):
        """One impact at the damaged team's base: units inside the destroy radius take the strike damage; the team's
        health loses its share once per firing ([ics] match_cannon tier_team_health, G: 4 x 125 = 500)."""
        c, m = self.cfg("match_cannon"), self.m
        core = m.core(team)
        if core is None:
            return
        cx, cy = core.ent.pos[:2]
        rng = m.units.rng
        if not large:
            a, d = rng.uniform(0, 2 * math.pi), rng.uniform(4.0, 8.0)
            cx, cy = cx + d * math.cos(a), cy + d * math.sin(a)
        radius = float(c.get("large_radius" if large else "small_radius", 13.1 if large else 4.5))
        dmg = float(c.get("strike_damage", 400.0))
        m.send(f"cannon strike at ({cx:.1f}, {cy:.1f}) (0x20d2)",
               M.pvp_map_marker(0x0200000000000F00 + int(rng.uniform(0, 255)),
                                (1, m.map["landblock"][0], m.map["landblock"][1], 0, cx, cy, m.map["z"]),
                                int(c.get("marker_icon", 0))))
        for e in list(m.world.entities.values()) + [m.world.champion]:
            if e is None or not e.alive or e.health is None or e.team != team or e.kind == "structure":
                continue
            if math.hypot(e.pos[0] - cx, e.pos[1] - cy) <= radius:
                m.world.damage(None, e, dmg)
        if last_one and m.mode == "domination":
            m.hurt_team(team, float(c.get("tier_team_health", 125.0)))

    def _cannon_neutral(self):
        cn, c, m = self.cannon, self.cfg("match_cannon"), self.m
        if m.over or cn is None:
            return
        cn["owner"], cn["state"] = 0, "locked"
        m.units.set_property(cn["mu"], PROP_OWNER, KIND_INT, 0, "cannon: neutral (0x10000456)")
        m.world.scriptlet(cn["mu"].ent, "Vfx_TeamColor_SetNull", "cannon: Vfx_TeamColor_SetNull (0x8d)")
        self._cannon_tracker()
        if cn["impacts"] >= int(c.get("impacts", 4)):
            return                                   # after the 4th: locked for good
        m.later(float(c.get("lock", 120.0)), self._cannon_unlock)

    def _cannon_unlock(self):
        cn, c, m = self.cannon, self.cfg("match_cannon"), self.m
        if m.over:
            return
        cn["state"] = "unlocked"
        self._cannon_tracker()
        key = c.get("massive" if cn["impacts"] == int(c.get("impacts", 4)) - 1 else "online")
        if key:
            m.line(int(key))

    # ---- deaths --------------------------------------------------------------------------------------------------
    def on_killed(self, mu, killer):
        """A boss / camp unit died: its kill buff, the boss's announcer event, respawns."""
        team = self.kill_buff(mu.cls, killer)
        self._beacon_kill(mu.cls, team)
        boss = getattr(mu, "boss", None)
        if not boss:
            ev = (self.ic.get("match_boss_kill_events") or {}).get(f"0x{mu.cls:08X}")
            if ev and team in (maps.T1, maps.T2) and mu.camp is not None and                     all(not x.ent.alive for x in mu.camp.members):
                self.event_voice(ev, team)
            return
        c = getattr(mu, "boss_cfg", {}) or {}
        if team in (maps.T1, maps.T2):
            local = self.m.local_team()
            if not self.ic.get("match_boss_kill_voice_by_team", True):
                self.event_voice(c.get("killed_event"), team)
                if c.get("other_line"):
                    self.m.line(int(c["other_line"]))
            elif team == local or not c.get("other_line"):
                # 2026-10-29 (tester report 23:03: "when I killed the Raider the announcer said the enemy had also
                # killed it"; traffic 22:49:46.463 event 61 then 22:49:49.383 line 0x2BD = 701 to the same player;
                # turret-heads-coredeath.md 3, C sets): event 61 has only its acting-team line (697) and 701 is the
                # other team's form, so the killer's team hears 61 and the other team 701, never both. false = both
                self.event_voice(c.get("killed_event"), team)
            else:
                self.m.line(int(c["other_line"]))
        if boss == "raider":
            if self.pods and not any(p["seismic"] for p in self.pods):
                self._seismic_on()
            elif c.get("respawn"):
                self._schedule_raider(c, self.m.t + float(c["respawn"]), list(mu.home[:2]))
        elif boss == "leviathan" and c.get("respawn"):
            at = self.m.t + float(c["respawn"])
            self.lines_before(at, c.get("respawn_warn"))
            self.at(at, lambda: self._spawn_leviathan(c, 0, "Leviathan_Respawn"))

    # ---- Gotham Divided beacons (map-objectives-recipes.md 5.3: lines C, rule P) -----------------------------------
    def camp_units(self, index, units):
        """The camp's units with this map's buff destroyer leader ([ics] match_beacons camp_leaders, G placement)."""
        lead = (self.cfg("match_beacons").get("camp_leaders") or {}).get(str(index))
        return [_did(lead)] + list(units[1:]) if lead and units else units

    def _beacon_kill(self, cls, team):
        c = self.cfg("match_beacons")
        b = (c.get("by_class") or {}).get(f"0x{cls:08X}")
        if not b or team not in (maps.T1, maps.T2):
            return
        held = self.__dict__.setdefault("beacons", {})
        key = (b["name"], team)
        tier = min(2, held.get(key, 0) + 1)
        held[key] = tier
        m = self.m
        lines = b.get("lines") or []
        line = lines[min(tier, len(lines)) - 1] if lines else 0
        if line and (team == m.local_team() or c.get("lines_to_both", False)):
            m.line(int(line))
        icon = _did(b.get("icon", 0))
        slot = int(b.get("slot", 1))
        # 2026-10-25 (map-runtime-state.md 2, C: the tracker reader 0x859970 skips the template entries with 0x10000A9B,
        # slots 3 / 4, unless spectating): a player sees slots 1 / 2 only ([ics] match_beacons.player_slots)
        slot = int((c.get("player_slots") or {}).get(str(slot), slot))
        m.send(f"beacon {b['name']} tier {tier} to team {team} (0x2069)",
               M.pvp_tracker_status(0x0200000000000D00 + slot, team, 0, 0, icon, slot, int(c.get("category", 29)),
                                    int(c.get("decoration", 9))))
        status = _did(b.get("status", 0))
        seconds = float(c.get("seconds", 180.0))
        w = m.world
        if status:
            for ch in m.champions():
                if ch.team == team and ch.alive:
                    try:
                        R.apply_status(CastWorld(w, ch, None), ch, ch, status, {"EffectDuration": seconds})
                    except Exception as e:     # noqa: BLE001
                        m.log(f"beacon status {status:#x} on {ch.name} failed ({e!r})")
        m.log(f"beacon {b['name']} tier {tier} -> team {team} for {seconds:g} s")
        m.later(seconds, lambda k=key, t=tier: self._beacon_expire(k, t, slot, icon))

    def _beacon_expire(self, key, tier, slot, icon):
        held = self.__dict__.setdefault("beacons", {})
        if held.get(key) != tier:
            return                                   # renewed / upgraded since
        held.pop(key, None)
        c = self.cfg("match_beacons")
        self.m.send(f"beacon {key[0]} ends for team {key[1]} (0x2069)",
                    M.pvp_tracker_status(0x0200000000000D00 + slot, 0, 0, 0, icon, slot, int(c.get("category", 29)), 0))

    def tick(self, dt):
        if self.pods:
            self._pods_tick(dt)
        if self.cannon is not None:
            self._cannon_tick(dt)
