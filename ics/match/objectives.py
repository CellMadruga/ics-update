"""Capturable objectives (Gotham Heights capture points, Coast City power relays, Gotham Divided beacons), the Doomsday
Device, and the map events (meteor storm) on an authored schedule.

The client has no capture logic and no "capture" message (full-maps-world.md 4): the server decides by presence and
tells the client through the owner property 0x10000456 (its change runs `_CapturePoint_OnTeamBiasChanged`), the
scriptlets BeingCaptured 0x1000032F / Captured 0x100002A9 / Lost 0x100002A8, and the sector tracker event 0x2069
(slot = map-note category + HUD position from the encounter template 0x100007F5 / 0x100007FA). Rates, radii and the
Device rule are not in the data: [ics] match_capture / match_device (authored, see ics/config.py).
"""
import math

from .. import messages as M
from ..wire import KIND_F32, KIND_INT
from . import maps
from .units import PROP_OWNER, PROP_TEAM, PROP_VISION

SC_BEING_CAPTURED, SC_CAPTURED, SC_LOST = 0x1000032F, 0x100002A9, 0x100002A8
SC_DEVICE_CHARGE, SC_DEVICE_FIRE = 0x10001096, 0x10001097
DECORATION_DOOMSDAY = 2
LOCK_ALL = 3


class Capturable:
    def __init__(self, mu, spec):
        self.mu, self.spec = mu, spec
        self.role = spec["role"]
        self.slot = int(spec.get("slot", 1))
        self.owner = 0
        self.control = 0.0              # -1 team 2 .. +1 team 1
        self.contender = 0
        self.icon = 0


class Objectives:
    def __init__(self, match):
        self.m = match
        self.ic = match.ic
        self.points = []
        self.device = None
        self.charge = {maps.T1: 0.0, maps.T2: 0.0}
        self.events = []                # (time, kind, stage)
        self._handles = 100

    # ---- spawning ------------------------------------------------------------------------------------------------
    def spawn(self):
        by_kills = bool(((self.ic.get("match_beacons") or {}).get(self.m.map.get("key", "")) or {}).get("by_class"))
        for spec in self.m.map.get("objectives", ()):
            if spec["role"] == "beacon" and by_kills:
                continue        # 2026-10-25 (map-objectives-recipes.md 5.3): beacons are won by kills, not captured
            pos = spec["pos"]
            if spec.get("pad") and self.ic.get("match_capture_on_pads", True):
                # 2026-10-29 (tester report 2026-10-29 15:30: GH, the point under the champion is "a few degrees to the
                # left" of where it should be; gh-ca-floor-spawn.md 3, C data): on the map's own pad static
                # (0x2E0008D5 on GH) instead of the waypoint markers' centre (up to 1.4 m apart); false = markers
                pos = spec["pad"]
            mu = self.m.units.spawn(spec["cls"], pos, 0, spec["role"], name=f"{spec['role']} {spec.get('slot', 1)}")
            if spec["role"] == "device":
                self.device = Capturable(mu, spec)
                self.pad = None
                if spec.get("trigger"):
                    self.pad = self.m.units.spawn(spec["trigger"], spec["pos"], 0, "device", name="device trigger")
                # 2026-10-25 (map-gaps-coast-city.md 1, C): the device's own table (0x1D0002FE) is Vfx_Active /
                # Vfx_Locked / Vfx_Unlocked / CapturePoint states / Vfx_OnFire; the pad's (0x1D000924) Start / Active
                self._fx(mu, ["Vfx_Active", "Vfx_Locked"], 0.4)
                if self.pad is not None:
                    self._fx(self.pad, [0x10001125], 0.4)
                continue
            cap = Capturable(mu, spec)
            self.points.append(cap)
        self.send_trackers()

    def _fx(self, mu, keys, delay=0.0):
        """Scriptlets (names or keys) on an objective's object; keys its tables do not hold are not sent."""
        w = self.m.world
        for k, key in enumerate(keys):
            self.m.later(delay + 0.2 * k, lambda key=key: w.scriptlet(mu.ent, key, f"{mu.ent.name}: {key} (0x8d)")
                         if mu.ent.eid in w.entities else None)

    def _state_fx(self, cap, state):
        """2026-10-25 (map-gaps-gotham-heights.md 3 / map-gaps-coast-city.md 2, C): Gotham Heights' points and Coast
        City's relays take no BeingCaptured / Captured / Lost; they show contention by Vfx_TeamColor_SetContention
        0x100008C4 and go neutral by Vfx_TeamColor_SetNull 0x10000B0D (the owner property drives the team colour).
        [ics] match_capture_scriptlets: role -> {state: [scriptlets]}."""
        table = (self.ic.get("match_capture_scriptlets") or {}).get(cap.role)
        if table is None:
            default = {"contest": [SC_BEING_CAPTURED], "captured": [SC_CAPTURED], "lost": [SC_LOST]}
            table = default
        for key in table.get(state, []):
            key = int(str(key), 0) if isinstance(key, str) and key.startswith("0x") else key
            self.m.world.scriptlet(cap.mu.ent, key, f"{cap.role} {cap.slot}: {state} {key} (0x8d)")

    def category(self, cap):
        return maps.MINIMAP.get(cap.role, 8)

    def send_trackers(self):
        # 2026-10-25 (map-runtime-state.md 4, C template: Crime Alley's encounter has one tracker entry, category 26
        # slot 1, that no object of ours fills): an initial neutral status for such pips ([ics] match_tracker_initial)
        for i, t in enumerate((self.ic.get("match_tracker_initial") or {}).get(self.m.map.get("key"), ())):
            self.m.send(f"tracker slot {t['slot']}: initial (0x2069)",
                        M.pvp_tracker_status(0x0200000000000C00 + i, 0, 0, 0, int(str(t.get("icon", 0)), 0),
                                             int(t["slot"]), int(t["category"]), 0))
        for cap in self.points:
            self._tracker(cap)
        if self.device is not None:
            self._tracker(self.device, decoration=DECORATION_DOOMSDAY if max(self.charge.values()) >= 100 else 0)

    def _tracker(self, cap, decoration=0):
        """2026-10-25 (map-runtime-state.md 1, C: Flash SectorObjective shows a padlock when the lock field is 3 or the
        player's team): 0 while capturable, 3 only while locked (the Device between its unlocks) ([ics]
        match_tracker_lock = false: always 3, as before)."""
        ent = cap.mu.ent
        locked = getattr(cap, "state", "open") == "locked" if cap.role == "device" else False
        lock = LOCK_ALL if (locked or not self.ic.get("match_tracker_lock", True)) else 0
        contender = cap.contender
        if contender == 3 and self.ic.get("match_tracker_contested", True):
            contender = getattr(cap, "last_capturer", 0)   # "both" matches no animation case: the last capturing team
        self.m.send(f"tracker {cap.role} {cap.slot}: owner {cap.owner} lock {lock} (0x2069)",
                    M.pvp_tracker_status(ent.eid, cap.owner, contender, lock, cap.icon, cap.slot,
                                         self.category(cap), decoration))

    # ---- capture by presence -------------------------------------------------------------------------------------
    def tick(self, dt):
        cfg = self.ic.get("match_capture") or {}
        seconds = float(cfg.get("seconds", 10.0)) or 10.0
        for cap in self.points:
            radius = float(cfg.get("radius", 0) or 0) or max(cap.mu.vision, 3.0)
            here = {maps.T1: 0, maps.T2: 0}
            for c in self.m.champions():
                if c.alive and c.team in here and c.distance_to(cap.mu.ent) <= radius:
                    here[c.team] += 1
            if here[maps.T1] and here[maps.T2]:
                self._contend(cap, -1)
                continue
            team = maps.T1 if here[maps.T1] else maps.T2 if here[maps.T2] else 0
            if not team:
                self._contend(cap, 0)
                continue
            sign = 1.0 if team == maps.T1 else -1.0
            if cap.owner == team:
                self._contend(cap, 0)
                continue
            # more champions capture faster (up to [ics] match_capture.max_bonus of them)
            n = min(here[team], int(cfg.get("max_bonus", 3)))
            before = cap.control
            cap.control = max(-1.0, min(1.0, cap.control + sign * dt * n / seconds))
            self._contend(cap, team)
            if cap.owner and before * cap.control <= 0 and before != 0 and cap.control * sign >= 0:
                self._lose(cap)
            if abs(cap.control) >= 1.0 and cap.owner != team:
                self._capture(cap, team)
        if self.device is not None:
            if str((self.ic.get("match_device") or {}).get("mode", "relays")) == "capture":
                self._device_capture_tick(dt)
            else:
                self._device_tick(dt)

    def _contend(self, cap, team):
        if team == -1:
            team = 3                # both teams on the point: the tracker shows it contested
        if team != cap.contender:
            cap.contender = team
            if team in (maps.T1, maps.T2):
                cap.last_capturer = team
                self._state_fx(cap, "contest")
                self.m.voice(f"{cap.role}_capturing", team=team)     # Coast City event 57 (announcer_events_by_map)
            self._tracker(cap)

    def _lose(self, cap):
        old = cap.owner
        cap.owner = 0
        self._state_fx(cap, "lost")
        self._relay_beam(cap, old, False)
        self._set_owner(cap)
        self.m.on_objective(cap, old, 0)

    def _capture(self, cap, team):
        old = cap.owner
        cap.owner = team
        self._state_fx(cap, "captured")
        if old:
            self._relay_beam(cap, old, False)
        self._relay_beam(cap, team, True)
        self._set_owner(cap)
        self.m.on_objective(cap, old, team)

    def _set_owner(self, cap):
        units = self.m.units
        units.set_property(cap.mu, PROP_OWNER, KIND_INT, cap.owner, f"{cap.role} {cap.slot}: owner {cap.owner} (0x10000456)")
        if cap.role == "capture":
            cap.mu.team = cap.mu.ent.team = cap.owner      # the owner's point shoots its enemies (Units.think)
        if cap.role == "beacon":
            # a held beacon is the owner's vision source (0x10000133 + team: full-maps-world.md 7.3)
            cap.mu.team = cap.mu.ent.team = cap.owner
            units.set_property(cap.mu, PROP_TEAM, KIND_INT, cap.owner)
            units.set_property(cap.mu, PROP_VISION, KIND_F32,
                               float((self.ic.get("match_capture") or {}).get("beacon_vision", 12.0)))
        self._tracker(cap)

    def _relay_beam(self, cap, team, on):
        """2026-10-25 (map-gaps-coast-city.md 2, C visuals, P rule): a held relay shows its beam on the owning team's
        core (core world state 0x2E0013EE: Vfx_Relay_01..03 Start / Active / Stop) ([ics] match_relay_beams)."""
        if cap.role != "relay" or team not in (maps.T1, maps.T2) or not self.ic.get("match_relay_beams", True):
            return
        core = self.m.core(team)
        if core is None or not core.ent.alive:
            return
        names = [f"Vfx_Relay_0{cap.slot}_Start", f"Vfx_Relay_0{cap.slot}_Active"] if on else [f"Vfx_Relay_0{cap.slot}_Stop"]
        self._fx(core, names)

    def owned(self, team, role=None):
        return sum(1 for c in self.points if c.owner == team and (role is None or c.role == role))

    # ---- the Doomsday Device (Coast City) -------------------------------------------------------------------------
    def schedule_device(self):
        """mode "capture": the unlock lines, then the Device opens (map-objectives-recipes.md 3.2)."""
        cfg = self.ic.get("match_device") or {}
        if self.device is None or str(cfg.get("mode", "relays")) != "capture":
            return
        self.device.state = "locked"
        self._device_cycle(float(cfg.get("unlock", 180.0)))

    def _device_cycle(self, at):
        cfg = self.ic.get("match_device") or {}
        m = self.m
        for off, key in (cfg.get("warn") or {}).items():
            t = at + float(off)
            if t >= m.t:
                m.later(t - m.t, lambda k=int(str(key), 0): m.line(k))
        m.later(max(0.0, at - m.t), self._device_unlock)

    def _device_unlock(self):
        cfg = self.ic.get("match_device") or {}
        if self.m.over:
            return
        self.device.state = "open"
        self.device.control = 0.0
        self._fx(self.device.mu, ["Vfx_Unlocked"])
        if getattr(self, "pad", None) is not None:
            self._fx(self.pad, [SC_DEVICE_CHARGE])
        if cfg.get("unlocked_line"):
            self.m.line(int(cfg["unlocked_line"]))
        self._tracker(self.device)

    def _device_capture_tick(self, dt):
        cfg = self.ic.get("match_device") or {}
        dev = self.device
        if getattr(dev, "state", "") != "open":
            return
        radius = float(cfg.get("radius", 5.0))
        here = {t: sum(1 for c in self.m.champions() if c.alive and c.team == t and c.distance_to(dev.mu.ent) <= radius)
                for t in (maps.T1, maps.T2)}
        if bool(here[maps.T1]) == bool(here[maps.T2]):
            return
        team = maps.T1 if here[maps.T1] else maps.T2
        dev.control = max(-1.0, min(1.0, dev.control + dt / float(cfg.get("seconds", 10.0)) * (1 if team == 1 else -1)))
        if abs(dev.control) < 1.0:
            return
        dev.state, dev.owner = "held", team
        dev.mu.team = dev.mu.ent.team = team
        self._fx(dev.mu, [SC_CAPTURED])
        self.m.units.set_property(dev.mu, PROP_OWNER, KIND_INT, team, f"device: owner {team} (0x10000456)")
        self._tracker(dev, DECORATION_DOOMSDAY)
        from .match import announcer_msgs
        ch = self.m.world.champion
        iid = ch.eid if ch is not None else 0
        self.m.voice_out(announcer_msgs(self.ic, int(cfg.get("captured_event", 51)), iid, iid, team,
                                        team == self.m.local_team()), event=int(cfg.get("captured_event", 51)))
        after = float(cfg.get("fire_after", 10.0))
        if cfg.get("fire_line"):
            self.m.later(max(0.0, after - 10.0), lambda: self.m.line(int(cfg["fire_line"])))
        self.m.later(after, lambda t=team: self._strike(t))

    def _strike(self, team):
        """The pad strike 0x340001FA at the enemy core: 0x4000035D there (Vfx_OnFire), damage by the Device level."""
        cfg = self.ic.get("match_device") or {}
        m, w = self.m, self.m.world
        if m.over:
            return
        enemy = maps.T2 if team == maps.T1 else maps.T1
        core = m.core(enemy)
        self._fx(self.device.mu, ["Vfx_OnFire"])
        if core is not None:
            level = 1 + int(max(0.0, m.t) // 90)
            pos = list(core.ent.pos)
            cls = int(str(cfg.get("strike_class", "0x4000035D")), 0)
            try:
                fx = w.spawn(cls, pos, 0.0, name="doomsday strike", start=False)
                fx.team = team
                w.update(fx, "spawn doomsday strike")
                m.later(0.3, lambda e=fx: w.scriptlet(e, "Vfx_OnFire", "doomsday strike: Vfx_OnFire (0x8d)"))
                m.later(6.0, lambda e=fx: w.remove(e, "doomsday strike gone (0x3)") if e.eid in w.entities else None)
            except Exception as e:                 # noqa: BLE001
                m.log(f"doomsday strike object not created ({e!r})")
            champ = cfg.get("champion_damage") or [100.0, 60.0]
            build = cfg.get("building_damage") or [750.0, 100.0]
            radius = float(cfg.get("strike_radius", 7.5))

            def hit():
                for e in list(w.entities.values()) + [w.champion]:
                    if e is None or not e.alive or e.health is None or e.team != enemy:
                        continue
                    if math.hypot(e.pos[0] - pos[0], e.pos[1] - pos[1]) > radius + (2.0 if e.kind == "structure" else 0):
                        continue
                    mu = getattr(e, "match_unit", None)
                    if e.kind == "structure":
                        if mu is not None and (mu.invulnerable or m.protected(mu)) and mu.role != "core":
                            continue
                        amount = float(build[0]) + float(build[1]) * level
                        if mu is not None and mu.role == "core" and not cfg.get("can_kill", False):
                            amount = min(amount, max(0.0, (e.health or 0) - 1))
                    else:
                        amount = float(champ[0]) + float(champ[1]) * level
                    if amount > 0:
                        w.damage(self.device.mu.ent, e, amount)
            m.later(1.0, hit)
            m.announce(2, source_team=team, target_team=enemy)
        self.device.owner, self.device.state = 0, "locked"
        self.device.mu.team = self.device.mu.ent.team = 0
        self.m.units.set_property(self.device.mu, PROP_OWNER, KIND_INT, 0, "device: neutral (0x10000456)")
        self._fx(self.device.mu, ["Vfx_Locked"])
        self._tracker(self.device)
        self._device_cycle(m.t + float(cfg.get("relock", 60.0)))

    def _device_tick(self, dt):
        cfg = self.ic.get("match_device") or {}
        rate = float(cfg.get("charge_per_relay", 1.0))
        for team in (maps.T1, maps.T2):
            relays = self.owned(team, "relay")
            if not relays:
                continue
            before = self.charge[team]
            self.charge[team] = min(100.0, before + rate * relays * dt)
            if before < 100.0 <= self.charge[team]:
                # 2026-10-25 (map-gaps-coast-city.md 1): 0x10001096 is the PAD's Active, not the device's
                self._fx(self.device.mu, ["Vfx_Unlocked", SC_CAPTURED])
                if getattr(self, "pad", None) is not None:
                    self._fx(self.pad, [SC_DEVICE_CHARGE])
                self.device.owner = team
                self._tracker(self.device, DECORATION_DOOMSDAY)
                self.m.later(float(cfg.get("fire_delay", 5.0)), lambda t=team: self._fire(t))

    def _fire(self, team):
        cfg = self.ic.get("match_device") or {}
        if self.m.over:
            return
        enemy = maps.T2 if team == maps.T1 else maps.T1
        core = self.m.core(enemy)
        self._fx(self.device.mu, ["Vfx_OnFire", "Vfx_Locked"])
        self.charge[team] = 0.0
        self.device.owner = 0
        self._tracker(self.device)
        if core is None or not core.ent.alive:
            return
        amount = float(cfg.get("damage_fraction", 0.25)) * float(core.ent.max_health or 0)
        if not cfg.get("can_kill", False):
            amount = min(amount, max(0.0, (core.ent.health or 0) - 1))
        if amount > 0:
            self.m.announce(2, source_team=team, target_team=enemy)
            self.m.world.damage(self.device.mu.ent, core.ent, amount)

    # ---- map events (meteor storm: full-match-mechanics.md 9.2) ----------------------------------------------------
    def schedule_events(self):
        table = self.ic.get("match_events") or {}
        for kind in self.m.map.get("events", ()):
            ev = table.get(kind)
            if not ev or not ev.get("enabled", True):
                continue
            t = float(ev.get("first", 600.0))
            end = float(ev.get("until", 3600.0))
            while t <= end:
                self.events.append([t, kind, "pending"])
                t += float(ev.get("every", 360.0)) or end + 1
        self.events.sort()

    def upcoming(self, now_t):
        return [e for e in self.events if e[0] >= now_t and e[2] == "pending"]

    def events_tick(self, t):
        table = self.ic.get("match_events") or {}
        for ev in self.events:
            at, kind, stage = ev[:3]
            cfg = table.get(kind) or {}
            warn = float(cfg.get("warning", 60.0))
            if stage == "pending" and t >= at - warn:
                ev[2] = "warned"
                self._handles += 1
                ev.append(self._handles)
                self.m.timeline_event(self._handles, at, severity=2, title=cfg.get("title", ""))
                self.m.timeline_banner(self._handles + 1000, at, severity=2, title=cfg.get("title", ""))
            elif stage == "warned" and t >= at:
                ev[2] = "done"
                self._meteor_storm(cfg)

    def _meteor_storm(self, cfg):
        """Impact zones on the minimap and a Meteor Fragment (0x400006F1, pack 0xA0000164) at each impact."""
        m = self.m
        nav = m.world.nav
        rng = m.units.rng
        n = int(cfg.get("impacts", 4))
        sites = [tuple(c["pos"]) for c in m.map.get("camps", ())] or [(80.0, 80.0)]
        for i in range(n):
            cx, cy = sites[i % len(sites)]
            x, y = cx + rng.uniform(-8, 8), cy + rng.uniform(-8, 8)
            if nav is not None:
                near = nav.nearest(x, y, max_r=10.0)
                if near:
                    x, y = near
            m.send(f"meteor impact {i} at ({x:.1f}, {y:.1f}) (0x20d2)",
                   M.pvp_map_marker(0x0200000000000E00 + i, (1, m.map["landblock"][0], m.map["landblock"][1], 0,
                                                             x, y, m.map["z"]), int(cfg.get("icon", 0))))
            dmg = float(cfg.get("damage", 0.0))
            if dmg > 0:
                for c in m.champions():
                    if c.alive and math.hypot(c.pos[0] - x, c.pos[1] - y) <= float(cfg.get("radius", 5.0)):
                        m.world.damage(None, c, dmg)
            pickup = int(cfg.get("pickup", 0) or 0)
            if pickup:
                m.add_pickup(pickup, (x, y), float(cfg.get("pickup_credits", 0.0)))
