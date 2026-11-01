"""Minion waves: one spawner per lane and team at the lane mouth (statics 0x2E000AF4-AF9, maps-complete.md 0 #7).

Shape from the user's prototype (WaveManager: first wave, interval, a siege minion every Nth wave, stronger waves on a
lane whose enemy dampener is down) with the data's classes; the timing is not in the data (units-and-ai.md 7):
[ics] match_waves (authored). The spawner's client visuals are the generator scriptlets of world state 0x2E000D03
(_Generator_Self_PreWaveStart 0x10000205 a few seconds before, _WaveStart 0x10000204 at the spawn); no spawner
entity is created yet (its placement is not anchored on the PvP maps), so they are not played.
"""
from . import maps


class WaveManager:
    def __init__(self, match):
        self.m = match
        self.cfg = match.ic.get("match_waves") or {}
        self.number = 0
        self.next_at = float(self.cfg.get("first", 45.0))
        self.minions = []

    def lanes(self):
        return list(self.m.map.get("lanes", {}))

    def composition(self, lane, team):
        """[(role key, class)] of the next wave on this lane for this team."""
        mins = self.m.map["minions"]
        cfg = self.cfg
        elite = self.m.dampener_down(lane, team) and "elite_melee" in mins
        melee = mins["elite_melee"] if elite else mins["melee"]
        ranged = mins.get("elite_ranged", mins["ranged"]) if elite else mins["ranged"]
        down = (self.m.ic.get("match_supers_on_structure_down") or {}).get(self.m.map.get("key")) or {}
        if down and self.m.structure_down(tuple(down.get("roles") or ()), 3 - team, lane):
            # 2026-10-29 (tester report 21:10: "the super minions come when the second turret is destroyed, not the
            # third"; power-core-turret.md 8): while the enemy's second structure on this lane (Crime Alley: the x 40 /
            # 120 dampener, or the inner turret when match_role_swaps makes it one) is down, this team's waves bring
            # the map's elites ([ics] match_supers_on_structure_down: map -> {"roles", "melee", "ranged"}; {} = off)
            melee = int(str(down.get("melee") or melee), 0)
            ranged = int(str(down.get("ranged") or ranged), 0)
        sup = (self.m.ic.get("match_core_turret_supers") or {}).get(self.m.map.get("key")) or {}
        if sup and self.m.core_turret_down(3 - team):
            # 2026-10-29 (tester report from the original-game video: once a Power Core Turret falls, super minions come
            # until it respawns; power-core-turret.md 5): this team's waves bring the map's elite (0x400000 flag)
            # classes ([ics] match_core_turret_supers: map -> {"melee", "ranged"}; {} = off)
            melee = int(str(sup.get("melee") or melee), 0)
            ranged = int(str(sup.get("ranged") or ranged), 0)
        out = [("melee", melee)] * int(cfg.get("melee", 2)) + [("ranged", ranged)] * int(cfg.get("ranged", 2))
        every = int(cfg.get("siege_every", 3) or 0)
        if mins.get("siege") and every and self.number % every == 0:
            out.append(("siege", mins["siege"]))
        late = float(cfg.get("super_after", 0) or 0)
        if mins.get("super") and late and self.m.t >= late:
            out.append(("super", mins["super"]))
        return out

    def tick(self, t):
        warn = float(self.cfg.get("warn_before", 10.0) or 0)
        if warn and not self.m.over and getattr(self, "_warned", None) != self.number and t >= self.next_at - warn:
            self._warned = self.number
            self.m.voice("wave_soon")
        if t < self.next_at or self.m.over:
            return
        self.m.voice("wave")
        self.number += 1
        self.next_at += float(self.cfg.get("interval", 30.0))
        cap = int(self.cfg.get("max_alive", 0) or 0)
        for lane in self.lanes():
            for team in (maps.T1, maps.T2):
                self.spawn_wave(lane, team, cap)

    def spawn_wave(self, lane, team, cap=0):
        m = self.m
        alive = [mu for mu in self.minions if mu.ent.alive]
        self.minions = alive
        path = maps.lane_path(m.map, lane, team)
        mouth = maps.team_pos(m.map, m.map["lanes"][lane]["mouth"], team)
        spacing = float(self.cfg.get("spacing", 1.5))
        # the wave lines up behind the mouth, along the lane's first direction
        dx, dy = path[min(1, len(path) - 1)][0] - mouth[0], path[min(1, len(path) - 1)][1] - mouth[1]
        d = (dx * dx + dy * dy) ** 0.5 or 1.0
        stagger = float(self.cfg.get("stagger", 0.0) or 0.0)
        out = []
        number = self.number
        end = m.structure_pos("core", 3 - team)
        route = [mouth] + path + ([end] if end else [])

        def one(i, kind, cls):
            if m.over or (cap and len([x for x in self.minions if x.ent.alive]) >= cap):
                return None
            if stagger > 0:
                pos, side = mouth, 0.0          # single file: each one teleports in at the mouth
            else:
                back = spacing * (i // 2)
                side = (-0.8 if i % 2 else 0.8) if kind != "siege" else 0.0
                pos = (mouth[0] - dx / d * back - dy / d * side, mouth[1] - dy / d * back + dx / d * side)
            mu = m.units.spawn(cls, pos, team, "minion", heading=0.0, name=f"{lane} {kind} {i + 1} t{team} w{number}")
            mu.offset = side
            m.units.set_lane(mu, lane, route)
            self.minions.append(mu)
            return mu

        comp = self.composition(lane, team)
        for i, (kind, cls) in enumerate(comp):
            if stagger > 0 and i:
                m.later(stagger * i, lambda i=i, kind=kind, cls=cls: one(i, kind, cls))
                continue
            mu = one(i, kind, cls)
            if mu is None:
                break
            out.append(mu)
        m.log(f"wave {self.number}: {lane} team {team}: {len(comp)} minions" + (f", {stagger:g} s apart" if stagger > 0 else ""))
        return out
