"""One PvP match's rules on a World: the mode layer (see ics/match/__init__.py for the entry point)."""
import heapq
import itertools
import math
import struct
import time
import traceback

from .. import messages as M
from .. import records
from ..wire import KIND_BOOL, KIND_ENUM, KIND_F32
from . import maps
from .announcer import channel as announcer_channel, line as announcer_line
from .bosses import Bosses
from .bots import BotManager
from .liftables import Liftables
from .objectives import Objectives
from .scoreboard import Player, Scoreboard
from .unitdata import UnitData
from .units import PROP_LIFE, STRUCTURES, Units, heading_from_yaw
from .waves import WaveManager

NOTICE_HUD_READY, NOTICE_TIMELINE_READY = 0x100000D2, 0x100002AD
NOTICE_TEAM_HEALTH_REQUEST, NOTICE_SURRENDER = 0x10000137, 0x10000454
BILLBOARD_GENERIC, BILLBOARD_LOSS, BILLBOARD_WIN = 2, 8, 9
PROP_UI_RECORD, PROP_TEAM_HEALTH, PROP_TARGET_TIME, PROP_SURRENDER_TIME = 0x100001D2, 0x10000463, 0x10000464, 0x1000021C
PROP_TRACKER_ICONS = 0x100007FC


def announcer_msgs(ic, event, source, target, team, own=True, extra=()):
    """[ics] announcer_mode: "2039" (the event on its dialog channel), "2001" (its line as a conversation) or both.
    extra: more 0x2039 context entries (the entities' names and icons, Match._announcer_fields)."""
    mode = str(ic.get("announcer_mode", "2039"))
    out = []
    if mode in ("2039", "both"):
        ch = announcer_channel(event)
        out.append((f"announcer event {event} channel {ch} (0x2039)",
                    M.announcer(event, source=source, target=target, team=team, other_team=3 - team, channel=ch,
                                extra=extra)))
    key = announcer_line(event, own)
    if mode in ("2001", "both") and key:
        out.append((f"announcer line {key} of event {event} (0x2001)",
                    M.start_conversation(key, speaker=M.CHAMPION_AGENT_ID, instance_id=M.next_conversation_instance())))
    return out


class Camp:
    def __init__(self, spec, index):
        self.spec, self.index = spec, index
        self.members = []
        self.provoker = None


class Match:
    def __init__(self, world, session, encounter, players=None, log=None):
        self.world, self.session, self.encounter = world, session, int(encounter)
        self.map, self.mode = maps.map_for(encounter)
        if self.map is None:
            raise ValueError(f"encounter {encounter:#x} is not a PvP map this layer knows")
        self._dampeners_on_sockets(world.ic)
        # a per-match copy of [ics]: the respawn time is set per death (World.damage reads respawn_seconds after its
        # "killed" event) and World's flat kill rewards are replaced by the data's formulas
        world.ic = dict(world.ic)
        self.ic = world.ic
        if self.ic.get("match_rewards_from_data", True):
            self.ic["credits_per_kill"], self.ic["xp_per_kill"] = {}, {}
        self.log = log or world.log
        self.ud = UnitData(world.data)
        self.t = -float(self.ic.get("match_pre_start", 13.0) or 0.0)
        self.t0 = time.time() - self.t          # wall clock at match time 0 (the HUD clock's start)
        self.begun = False
        self.over = False
        self.winner = 0
        self._timers, self._seq = [], itertools.count()
        self.units = Units(self)
        self.waves = WaveManager(self)
        self.objectives = Objectives(self)
        self.score = Scoreboard(self)
        self.structures = []            # MatchUnits (both teams)
        self.camps = []
        self.pickups = []
        self.aggressors = {}            # champion eid -> (match time, team it hit)
        self.team_health, self.team_health_start = {}, {}
        self._health_sent = {}
        self.surrender = None
        self.surrender_after = {}
        self._level_step = -1
        self.players_in = players
        self.bots = BotManager(self)
        self.bosses = Bosses(self)
        self.liftables = Liftables(self)
        world.visibility = self.visible_to
        world.listeners.append(self._on_event)
        # 2026-10-28 15:00 (tester report; test-2026-10-28-1439-sweep.md S8: World.income paid the player 2 credits / s
        # through the intro and the countdown, the bots are paid only from the start): no passive income before the
        # match start ([ics] match_income_from_start; Match._begin lifts it)
        world.income_hold = bool(self.ic.get("match_income_from_start", True))

    # ---- plumbing ------------------------------------------------------------------------------------------------
    def _dampeners_on_sockets(self, ic):
        """2026-10-25 (black-ground-shapes.md 4.2, P: Gotham Divided's six base lane exits are terrain sockets 50 m deep,
        one per lane like Crime Alley's dampener socket; our gates stood on them and the dampeners at guessed spots):
        the dampeners go onto the sockets and the gates step back [ics] gd_gate_setback m towards the base
        ([ics] match_dampener_sockets: map -> {lane: [x, y]} for team 1; {} = the map's own positions)."""
        sockets = (ic.get("match_dampener_sockets") or {}).get(self.map.get("key"))
        if not sockets:
            return
        aura = (self.map.get("auras") or [{}])[0].get("pos", {}).get(maps.T1)
        back = float(ic.get("gd_gate_setback", 8.0) or 0)
        for spec in self.map["structures"]:
            if spec["role"] == "dampener" and spec.get("lane") in sockets:
                spec["pos"] = {maps.T1: tuple(sockets[spec["lane"]])}
        if aura is None or back <= 0:
            return
        for gate in self.map.get("gates", ()):
            p = gate["pos"].get(maps.T1)
            near = min(sockets.values(), key=lambda s: math.hypot(s[0] - p[0], s[1] - p[1]))
            if math.hypot(near[0] - p[0], near[1] - p[1]) > 3.0:
                continue
            dx, dy = aura[0] - near[0], aura[1] - near[1]
            d = math.hypot(dx, dy) or 1.0
            gate["pos"] = {maps.T1: (near[0] + dx / d * back, near[1] + dy / d * back)}

    def later(self, delay, fn):
        heapq.heappush(self._timers, (self.t + float(delay), next(self._seq), fn))

    def clock(self, t=None):
        """Game-clock time (time.time(), what the time packet syncs) of a match time."""
        return self.t0 + (self.t if t is None else t)

    def send(self, label, data, team=None):
        """To the players: the session's send_team / broadcast when it has one (several players), else the world's
        send (the local player), skipping a team-only message for another team."""
        s = self.session
        if team is not None and hasattr(s, "send_team"):
            return s.send_team(team, label, data)
        if hasattr(s, "broadcast"):
            return s.broadcast(label, data)
        if team is not None and self.world.champion is not None and self.world.champion.team != team:
            return None
        return self.world.send(label, data)

    def champions(self):
        w = self.world
        out = [w.champion] if w.champion is not None else []
        out += [p.agent for p in self.score.players if p.agent is not None and p.agent is not w.champion]
        return out

    def local_team(self):
        return self.world.champion.team if self.world.champion is not None else maps.T1

    # ---- start -------------------------------------------------------------------------------------------------------
    def start(self):
        m = self.map
        self.log(f"match: {m['name']} ({self.encounter:#x}), mode {self.mode}")
        self._players()
        skip = set((self.ic.get("match_skip_roles") or {}).get(m.get("key"), ()))
        swap = (self.ic.get("match_role_swaps") or {}).get(m.get("key")) or {}
        if swap:
            # 2026-10-28 (tester's screenshot: "the tower there must be the same as the one at the start of the lane"):
            # a role's spot takes another role, with that role's classes ([ics] match_role_swaps: map -> {role: [new
            # role, role whose classes it takes]})
            by_role = {sp["role"]: sp for sp in m["structures"]}
            for sp in m["structures"]:
                if sp["role"] in swap and not sp.get("swapped"):
                    new_role, cls_from = swap[sp["role"]]
                    if cls_from in by_role:
                        sp["cls"] = by_role[cls_from]["cls"]
                    sp["role"], sp["swapped"] = new_role, True
        for spec in m["structures"]:
            if spec["role"] in skip:
                # 2026-10-28 (tester: three towers a side where the original has two; crime-alley-structures.md, C: the
                # map's markers are core / x 40 / x 65 only, the core turret's 25.5 came from Tutorial 2's half lane)
                continue
            for team in (maps.T1, maps.T2):
                self._spawn_structure(spec, team)
        self._link_structures()
        self.unlock_structures()
        for team in (maps.T1, maps.T2):
            self._core_shield(team, True)
        self._spawn_scenery()
        self._spawn_stealth()
        self._spawn_nook()
        self.liftables.start()
        if self.ic.get("tour_command", True) and self.ic.get("showroom_prefetch", True):
            # started a while after the match start, so it never overlaps the load ([ics] showroom_prefetch_delay)
            from .tour import prefetch
            self.later(float(self.ic.get("showroom_prefetch_delay", 30.0) or 0), lambda: prefetch(self))
        self.objectives.spawn()
        self.objectives.schedule_events()
        self.bosses.start()
        self.objectives.schedule_device()
        first = float((self.ic.get("match_camps_first_by_map") or {}).get(m.get("key"),
                      (self.ic.get("match_camps") or {}).get("first", 60.0)))
        specs = list(m.get("camps", ()))
        if self.ic.get("match_camp_centre", False):
            # 2026-10-28 15:00 (tester report: no camp in the centre; camps-colour-bar-positions.md 3.3): only on request,
            # first as in fase3-ie
            specs = list(m.get("camps_centre", ())) + specs
        for i, spec in enumerate(specs):
            camp = Camp(spec, i)
            self.camps.append(camp)
            boss = spec.get("kind") in ("boss", "big")
            delay = float((self.ic.get("match_camps") or {}).get("first_boss", first)) if boss else first
            pre_from = float(self.ic.get("match_camp_prespawn_from", 0.0) or 0.0)
            if not boss and pre_from < 0 and self._camp_phase(spec["units"][0]) > 0:
                # 2026-10-30 (tester report 13:18; timeline-tooltip-camp-prespawn.md 2): the first camps phase in from the
                # "Online in 30 seconds" line until match_camp_prespawn_appear_before s before the jungle time
                camp.phase_until = delay - float(self.ic.get("match_camp_prespawn_appear_before", 1.0) or 0.0)
                delay = max(0.0, delay + pre_from)
            elif not boss and self.ic.get("match_camp_phase_lead", True) and self._camp_phase(spec["units"][0]) > 0:
                # 2026-10-28 13:52 (jungle-camps-spawn.md 3): the first camps phase in before "Phasing Complete" (the
                # jungle line at `first`), so they are complete at that line
                delay = max(0.0, delay - self._camp_phase(spec["units"][0]))
            self.later(max(0.0, delay - self.t) if delay > 0 else 0.0, lambda c=camp: self._spawn_camp(c))
        if self.mode in ("domination", "clash"):
            start = self._team_health_start()
            self.team_health_start = dict(start)
            self.team_health = dict(start)
        self.send_clock()
        if self.team_health:
            self.send_team_health(initial=True)
        self.send_many(M.pvp_timeline_start(self.timeline_now() if self.ic.get('timeline_start_time', True) else None))
        self.score.send(self.t)
        intro = int(m.get("intro") or 0)
        if intro and self.ic.get("match_play_intro", True) and self.t < 0 and hasattr(self.session, "play_cinematic"):
            self.session.play_cinematic(intro)
        if self.t >= 0:
            self._begin()
        return self

    def send_many(self, labelled):
        for label, data in labelled:
            self.send(label, data)

    def _players(self):
        w = self.world
        given = self.players_in or []
        if not given and w.champion is not None:
            given = [{"player": M.LOCAL_PLAYER_ID, "agent": w.champion, "name": self.ic.get("player_name", "Player"),
                      "champion": w.champion.class_id, "team": w.champion.team}]
        human_done = False
        for g in given:
            agent = g.get("agent")
            if agent is None and g.get("bot") and self.ic.get("bot_champions_in_world", True) and g.get("champion"):
                # 2026-10-25 (bot-champions.md 3.1: the bots were scoreboard rows only, no champion on the map)
                try:
                    agent = w.create_bot_champion(int(g["champion"]), int(g.get("team", maps.T2)), g.get("name", ""),
                                                  int(g.get("iid", 0) or 0), stolen=g.get("stolen") or ())
                except Exception:                      # noqa: BLE001
                    self.log(f"bot {g.get('name')} not created\n{traceback.format_exc()}")
                    agent = None
            if agent is None and not g.get("bot") and not human_done and w.champion is not None                     and self.ic.get("match_attach_human", True):
                # 2026-10-25 (bot-champions.md, C: lobby rows carry "iid", not "player" / "agent", so the human's row had
                # no agent and his kills / deaths / assists / credits never counted): the human row gets the champion
                agent = w.champion
                human_done = True
            team = int(g.get("team", agent.team if agent is not None else maps.T1))
            p = self.score.add(Player(int(g.get("player", g.get("iid", 0)) or 0), agent, g.get("name", ""), int(g.get("champion", 0)
                                      or (agent.class_id if agent is not None else 0)), team, bool(g.get("bot")),
                                      int(g.get("account", 0))))
            if agent is not None:
                agent.team = team
                start = maps.spawn_point(self.encounter, team, p.slot)
                if self.ic.get("match_place_champions", True) and start:
                    moved = math.hypot(agent.pos[0] - start[4], agent.pos[1] - start[5]) > 0.01
                    agent.pos = [start[4], start[5], start[6]]
                    agent.dest, agent.path = None, []
                    if moved and agent is w.champion and w.in_world:
                        w.refresh_champion(f"{agent.name} at team {team}'s start")
                if agent is w.champion and start:
                    w.spawn_pos = [start[4], start[5], start[6]]
                if agent.kind == "champion":
                    w.give_recall(agent)                   # home = this start point
                if getattr(agent, "bot", False):
                    w.update(agent, f"spawn bot champion {agent.name} t{team}")
                    w.vitals(agent)
        self.bots.attach([p.agent for p in self.score.players if getattr(p.agent, "bot", False)])

    def _spawn_structure(self, spec, team, keep=None):
        cls = spec["cls"][team - 1]
        # 2026-10-29 (tester report 23:03: "the turret near the core has neither the body nor the base, only the blue
        # transparent effects"; turret-heads-coredeath.md 2, C data): a role's class per map and team ([ics]
        # match_structure_classes: map -> role -> {"1" / "2": class}; {} = the map spec's)
        cls_over = (((self.ic.get("match_structure_classes") or {}).get(self.map.get("key")) or {})
                    .get(spec["role"]) or {}).get(str(team))
        if cls_over:
            cls = int(str(cls_over), 0)
        pos = maps.team_pos(self.map, spec["pos"], team)
        # 2026-10-29 (tester report from the original-game video: the Power Core Turret stands on the core platform's
        # prow; power-core-turret.md 2): a role's spot per map and team ([ics] match_structure_pos: map -> role ->
        # {"1" / "2": [x, y]}; {} = the map spec's)
        over = (((self.ic.get("match_structure_pos") or {}).get(self.map.get("key")) or {}).get(spec["role"]) or {})
        if over.get(str(team)):
            pos = tuple(float(v) for v in over[str(team)])
        yaw = (spec.get("yaw") or {}).get(team)
        # 2026-10-30 (tester report 15:30: "the blue core must be rotated 170 degrees to the right"; core-door-regen.md
        # 1): [ics] match_structure_yaw_add map -> role -> {"1" / "2": deg} (counter-clockwise from above) on the spec's
        add = (((self.ic.get("match_structure_yaw_add") or {}).get(self.map.get("key")) or {})
               .get(spec["role"]) or {}).get(str(team))
        if add is not None and yaw is not None:
            yaw = float(yaw) + float(add)
        heading = heading_from_yaw(yaw) if yaw is not None else 0.0
        if yaw is None and spec["role"] != "core":
            # turrets face the enemy base (G)
            enemy = self.structure_pos("core", 3 - team) or (80.0, 80.0)
            heading = math.atan2(enemy[1] - pos[1], enemy[0] - pos[0])
        mu = self.units.spawn(cls, pos, team, spec["role"], heading=heading,
                              name=f"{spec['role']} {spec.get('lane') or ''} t{team}".replace("  ", " "))
        mu.lane = spec.get("lane")
        mu.spec = spec
        if spec.get("invulnerable"):
            mu.invulnerable = True          # a structure the mode does not let anyone hit (Gotham Heights' cores)
        if spec["role"] in tuple(self.ic.get("match_keep_body_roles") or ()):
            # 2026-10-29 (tester report from the original-game video: a destroyed Power Core Turret leaves its fallen
            # rings on a base with the team's dot; power-core-turret.md 4): its body stays until it respawns
            mu.ent.keep_body = True
        mu.shield_hp = mu.ent.health
        if keep is not None:
            idx = self.structures.index(keep)
            self.structures[idx] = mu
        else:
            self.structures.append(mu)
        return mu

    def _link_structures(self):
        """Protection order (P: outer before inner per lane, the core turret after any inner lane structure, the
        core after the core turret; [ics] match_structure_order)."""
        for mu in self.structures:
            mu.requires = []
        if not self.ic.get("match_structure_order", True):
            return
        for team in (maps.T1, maps.T2):
            mine = [mu for mu in self.structures if mu.team == team]
            inner = []
            for lane in self.map.get("lanes", {}):
                outer = [mu for mu in mine if mu.lane == lane and mu.role == "turret"]
                inn = [mu for mu in mine if mu.lane == lane and mu.role in ("dampener", "inner_turret")]
                for mu in inn:
                    mu.requires.append(("all", outer))
                inner += inn
            ct = [mu for mu in mine if mu.role == "core_turret"]
            for mu in ct:
                if inner:
                    mu.requires.append(("any", inner))
            for mu in mine:
                if mu.role == "core":
                    if ct:
                        mu.requires.append(("all", ct))
                    elif inner:
                        mu.requires.append(("any", inner))

    def unlock_structures(self):
        """2026-10-23 10:23 (tester: only the first turret can be attacked): the client's order check 0x9d01d0 needs
        status 0x10000249 true on the target, and the dampener / core turret / core templates link it to bool
        property 0x100007D9 (default false). When a structure stops being protected it gets 0x100007D9 = true
        ([ics] match_unlock_property, 0 = never sent)."""
        prop = int(self.ic.get("match_unlock_property", 0x100007D9) or 0)
        if not prop:
            return
        for mu in self.structures:
            if not mu.ent.alive or getattr(mu, "unlocked", False) or mu.invulnerable or self.protected(mu):
                continue
            mu.unlocked = True
            self.send(f"{mu.ent.name}: attackable ({prop:#x} = true, 0x6)", M.set_property(mu.ent.eid, prop, KIND_BOOL, 1))
            if self.ic.get("match_unlock_modifiers", True):
                # 2026-10-23 17:40 (tester: only the first turret attackable; targeting-indicator-and-structures.md):
                # the order check 0x9d01d0 reads 0x10000249 / 0x10000029 as base value + modifiers; the template links
                # 0x10000249 to 0x100007D9, which apparently does not move it: a "set" modifier (op 6, 0x20F0) does
                for attr in (0x10000249, 0x10000029):
                    self.world.combat.add_modifier(mu.ent, attr, 6, True)
            if self.ic.get("match_unlock_bundle", True):
                # 2026-10-24 00:45 (tester: still only the first turret attackable; the clicks on the dampener became
                # moves): the 0x6 change and the set modifier did not move status 0x10000249, which the template links to
                # 0x100007D9; the structure's bundle again with 0x100007D9 = true among its properties (P: the link is
                # read when the object is built)
                ent = mu.ent
                ent.extra_props = [p for p in ent.extra_props if p[0] != prop] + [(prop, KIND_BOOL, 1)]
                self.world.update(ent, f"{ent.name}: bundle with {prop:#x} = true")
            if self.ic.get("match_refresh_flags", True):
                self.units.refresh_flags(mu)

    def protected(self, mu):
        for mode, deps in getattr(mu, "requires", ()):
            alive = [d.ent.alive for d in deps]
            if not alive:
                continue
            if mode == "all" and any(alive):
                return True
            if mode == "any" and all(alive):
                return True
        return False

    def _ui_record(self):
        ui = self.ud.first(self.encounter, PROP_UI_RECORD, 0)
        return self.world.data.record(ui) if ui >> 24 == 0x48 else None

    def _ui_value(self, prop):
        """A number of the encounter's UI record 0x100001D2 (e.g. 0x10000464: GH 1250, CC 1000, GD 750; G meaning: the
        target time sent with the match-ended notice), else 0."""
        v = records.get(self._ui_record(), prop)
        return float(v) if isinstance(v, (int, float)) else 0.0

    def _team_health_start(self):
        """Starting team health: the UI record's 0x10000463 (GH 500 / 500, Clash 200 or 300; C), else [ics]."""
        out = {}
        rec = self._ui_record()
        for _k, _kind, el in records.get(rec, PROP_TEAM_HEALTH) or ():
            d = records.as_dict(el) if isinstance(el, list) else {}
            if d.get(0x10000460) in (maps.T1, maps.T2) and d.get(0x1000045F):
                out[int(d[0x10000460])] = float(d[0x1000045F])
        if len(out) < 2:
            v = float(self.ic.get("match_team_health", 500))
            out = {maps.T1: out.get(maps.T1, v), maps.T2: out.get(maps.T2, v)}
        return out

    # ---- the clock -----------------------------------------------------------------------------------------------
    def _timeline_schedule(self):
        """2026-10-25 (tester's frame of the original: icons on the strip under the clock; hud-shop-timeline-kills.md
        2.3): the match start, the first drones and the jungle as timeline events at their game times ([ics]
        match_timeline: name -> {at: s or "waves" / "camps", severity}); icons 0 = the default marker in its colour."""
        if getattr(self, "_timeline_sent", False):
            return
        self._timeline_sent = True
        table = self.ic.get("match_timeline") or {}
        waves = float((self.ic.get("match_waves") or {}).get("first", 15.0))
        camps = self._camps_first()
        raider = (self.ic.get("match_raider") or {}).get(self.map.get("key")) or {}
        self._timeline_handles = []
        for k, (name, spec) in enumerate(sorted(table.items())):
            at = spec.get("at", 0)
            if at == "raider":
                # 2026-10-30 (tester report 13:18; timeline-tooltip-camp-prespawn.md 1): the Raider's time, only on a
                # map with a Raider ([ics] match_raider)
                if not raider or "at" not in raider:
                    continue
                at = float(raider["at"])
            at = waves if at == "waves" else camps if at == "camps" else float(at)
            if name == "jungle" and not self.camps:
                continue
            self._timeline_handles.append(900 + k)
            self.timeline_event(900 + k, at, severity=int(spec.get("severity", 2)), title=str(spec.get("title", "") or ""),
                                icon=self._timeline_icon(spec.get("strip_icon")),
                                examination_icon=self._timeline_icon(spec.get("icon")))

    def _timeline_icon(self, src):
        """2026-10-30 (tester report 13:18: hovering a mark of the strip shows only the countdown, the original also the
        picture of what comes; timeline-tooltip-camp-prespawn.md 1, C Flash EventTimelineTooltip.SetData ->
        m_IconContainer.SetIcon(didExaminationIcon); the original's own events (GH cannon script 0x340002CF, node
        0x1000011A) give the tooltip a unit's Character_Billboard_Icon 0x100001FC, e.g. 0x130016CD = the super drone's).
        src: an image DID ("0x13..."), or the source of one read from the game data: "melee" / "ranged" / "siege" (the
        map's drone class), "camps" (the first camp's first unit), "raider" (match_raider cls) or a class DID
        ("0x40..."). 0 when none, or [ics] match_timeline_icons is off."""
        if not src or not self.ic.get("match_timeline_icons", True):
            return 0
        src = str(src)
        cls = 0
        if src in ("melee", "ranged", "siege", "super", "elite_melee", "elite_ranged"):
            cls = int((self.map.get("minions") or {}).get(src, 0) or 0)
        elif src == "camps":
            specs = list(self.map.get("camps", ())) or [c.spec for c in self.camps]
            cls = int(str((specs[0].get("units") or [0])[0]), 0) if specs else 0
        elif src == "raider":
            cls = int(str(((self.ic.get("match_raider") or {}).get(self.map.get("key")) or {}).get("cls", 0)), 0)
        else:
            v = int(src, 0)
            if v >> 24 == 0x13:
                return v
            cls = v
        if not cls:
            return 0
        icon = int(self.ud.first(cls, 0x100001FC, 0) or 0)
        if not icon:
            # Data.template_properties misses the pair on some templates (the Raider 0x49000CA2: C, 0x13001A37)
            try:
                icon = int(self.world.data.record_u32(0x49000000 | (cls & 0xFFFFFF), 0x100001FC) or 0)
            except Exception:                    # noqa: BLE001 - a class whose pack is not on this server
                icon = 0
        return icon if icon >> 24 == 0x13 else 0

    def _camps_first(self):
        """The first camps' match time: [ics] match_camps_first_by_map[map], else match_camps first (what _spawn_camp
        uses)."""
        return float((self.ic.get("match_camps_first_by_map") or {}).get(self.map.get("key"),
                     (self.ic.get("match_camps") or {}).get("first", 60.0)))

    def timeline_now(self):
        """The 'now' of the timeline notices. 2026-10-28 13:52 (tester: the match starts and the first red mark of the
        strip comes seconds later; timeline-kda-endscreen.md 1, C: Flash places a mark at (event time - (StartTimeline
        now + its own elapsed game time)) / 5 s * 12 px): the wall clock the time packets sync. clock() lags it while
        the match time stands still during the load (13:39:27 sent a 'now' 5.35 s old). [ics] timeline_wall_now."""
        return time.time() if self.ic.get("timeline_wall_now", True) else self.clock()

    def timeline_time(self, at):
        """A match time on the strip's clock: now + (at - match time now), i.e. when the server's own timers (which run
        on the match time) will fire, so the marks meet the now-marker with the announcer lines. [ics]
        timeline_wall_now false = clock(at)."""
        if not self.ic.get("timeline_wall_now", True):
            return self.clock(at)
        return time.time() + (float(at) - self.t)

    def _timeline_rebase(self):
        """The clock's base moved (the intro's end sets the start 42 s ahead): the strip's events were placed on the old
        base; remove them (0x100002AC), restart the strip and add them again at the new times. [ics] timeline_rebase."""
        if not getattr(self, "_timeline_sent", False) or not self.ic.get("timeline_rebase", True):
            return
        for h in getattr(self, "_timeline_handles", ()):
            self.send(f"timeline event {h} removed (0x100002ac)", M.pvp_timeline_remove(h))
        self._timeline_sent = False
        self.send_many(M.pvp_timeline_start(self.timeline_now() if self.ic.get('timeline_start_time', True) else None))
        self._timeline_schedule()

    def send_clock(self):
        if self.t < 0 and self.ic.get("match_clock_prestart_countdown", True):
            # 2026-10-25 (tester: the clock showed 1:00:00 the whole pre-start; hud-shop-timeline-kills.md 3, C: Flash
            # shows (end - start) - elapsed, elapsed 0 until start): start = now, end = the match start
            self.send(f"match clock: pre-start countdown to {self.clock(0.0):.1f} (0x10000109)",
                      M.pvp_set_match_time(self.clock(), self.clock(0.0), True))
            return
        start = self.clock(0.0)
        end = start + float(self.ic.get("match_clock_length", 3600.0))
        self.send(f"match clock: start {start:.1f}, pre-start {self.t < 0} (0x10000109)",
                  M.pvp_set_match_time(start, end, self.t < 0))

    def intro_done(self):
        """2026-10-24 23:40 (tester: the blue base gate must stay until the countdown reaches zero, the announcer
        counts down; crime-alley-2v2-video.md 3: the clock shows 00:42 when control is given after the intro, notices
        at 30 and 10 s, "Match: Initiating" and the gate fades at 0): the pre-start clock is set when the intro
        cinematic ends ([ics] match_pre_start_after_intro s, 0 = keep the creation-time clock); the countdown lines
        play by [ics] announcer_events names match_starts_30 / match_starts_10 / match_start once their ids are known."""
        rest = float(self.ic.get("match_pre_start_after_intro", 42.0) or 0)
        if self.begun or rest <= 0 or getattr(self, "_intro_done", False):
            return
        self._intro_done = True
        self.t = -rest
        self.t0 = time.time() - self.t
        self.log(f"match: intro over, {rest:g} s to the start")
        self.send_clock()
        self._timeline_rebase()
        # 2026-10-25 (countdown-keymap-gaps.md 1, C: the countdown captions are announcer line keys of table 0x2B000093,
        # played only by conversation 0x2001, as the 1vAI encounter script 0x34000628 did): [ics] match_countdown_lines
        # {match time s: line key}; the first wave's lines [ics] match_wave_lines {s relative to the first wave: key}
        self._schedule_lines(self.ic.get("match_countdown_lines") or {}, 0.0)
        first = float(((self.ic.get("match_waves") or {}).get("first", 0.0)) or 0.0)
        # 2026-10-25 (announcer-and-map-elements.md A3 / A5, C: a line plays only if the map's layout pack holds it):
        # wave and jungle lines per map ([ics] match_wave_lines / match_jungle_lines: map key -> {s: key})
        key = self.map.get("key")
        waves = self.ic.get("match_wave_lines") or {}
        flat = waves and all(not isinstance(v, dict) for v in waves.values())     # the fase3-hp form: one table
        self._schedule_lines(waves if flat else waves.get(key, {}), first)
        camps_at = float(((self.ic.get("match_camps") or {}).get("first", first)) or first)
        if self.ic.get("match_jungle_lines_follow_camps", True):
            # 2026-10-28 13:52 (tester: the strip's marks and the announcer do not agree; timeline-kda-endscreen.md 1,
            # C log: "jungle online" played at 60 s while the camps spawned at 45 s on Crime Alley): the jungle lines
            # count from the camps' real first time (match_camps_first_by_map), as the camps and the strip do
            camps_at = self._camps_first()
        self._schedule_lines((self.ic.get("match_jungle_lines") or {}).get(key, {}), camps_at)

    def _schedule_lines(self, table, base):
        for at, key in table.items():
            t = base + float(at)
            if t >= self.t:
                heapq.heappush(self._timers, (t, next(self._seq), lambda k=int(str(key), 0): self.line(k)))

    def line(self, key):
        """An announcer line by its key. 2026-10-25 (tester: the countdown voice is still silent; dialog-shield-
        disconnect.md 1, C): 0x2001 plays only from an encounter's conversation catalogue (template 0x10000B21), which no
        PvP template has; 0x2039 with 0x100003BD = the key plays it from a dialog channel's set: the shared lines
        ([ics] announcer_shared_lines, set 0x4000047A) on channel 1, or on channel 3 after 0x202A loads the set where the
        template lacks 0x10000803 ([ics] announcer_load_shared_set: encounter -> set); the map's own lines on 2.
        [ics] announcer_line_mode "2001" = the old conversation form."""
        if str(self.ic.get("announcer_line_mode", "2039")) == "2001":
            self.voice_out([(f"announcer line {key:#x} (0x2001)",
                             M.start_conversation(key, speaker=M.CHAMPION_AGENT_ID,
                                                  instance_id=M.next_conversation_instance()))])
            return
        shared = {int(str(k), 0) for k in (self.ic.get("announcer_shared_lines") or ())}
        channel = 2
        if key in shared:
            loaded = (self.ic.get("announcer_load_shared_set") or {}).get(f"0x{self.encounter:08X}")
            if loaded:
                if not getattr(self, "_shared_set_loaded", False):
                    self._shared_set_loaded = True
                    did = int(str(loaded), 0)
                    self.send(f"announcer set {did:#x} into channel 3 (0x202a)", M.load_announcer_set(did))
                channel = 3
            else:
                channel = 1
        self.voice_out([(f"announcer line {key:#x} channel {channel} (0x2039 0x100003bd)", M.announcer_line(key, channel))])

    def _begin(self):
        self.begun = True
        self.world.income_hold = False          # [ics] match_income_from_start: passive credits from now on
        self.log("match: started")
        self.send_clock()
        self._open_gates()

    # ---- base gates and auras (crime-alley-missing-elements.md) --------------------------------------------------------
    def _spawn_scenery(self):
        """The base gates (closed light walls until the start) and the base auras the server creates
        ([ics] match_base_gates / match_base_auras)."""
        self.gates, self.auras = [], []
        w = self.world
        self._spawn_socket_covers()
        self._spawn_map_objects()
        self._spawn_decor_doors()
        for kind, key, store in (("gate", "gates", self.gates), ("aura", "auras", self.auras)):
            if not self.ic.get(f"match_base_{key}", True):
                continue
            for spec in self.map.get(key, ()):
                for team in (maps.T1, maps.T2):
                    pos = maps.team_pos(self.map, spec["pos"], team)
                    heading = float((spec.get("heading") or {}).get(team, 0.0))
                    cls = (spec.get("cls_by_team") or {}).get(team, spec["cls"])
                    ws = (spec.get("world_state_by_team") or {}).get(team, spec.get("world_state", 0))
                    try:
                        ent = w.spawn(cls, [pos[0], pos[1], self.map["z"]], heading,
                                      name=f"base {kind} t{team}", world_state=ws, start=False)
                    except Exception as e:             # noqa: BLE001
                        self.log(f"base {kind} t{team} not created ({e!r})")
                        continue
                    ent.team = team
                    ent.extra_props = [p for p in ent.extra_props if p[0] != 0x1000009C] + [(0x1000009C, 0x10, team)]   # team (int)
                    sides = self.ic.get("match_base_sides") or {}
                    if kind == "gate" and str(team) in sides:
                        # 2026-10-25 (tester: the blue gate is invisible during the countdown; crime-alley-visuals.md e):
                        # Object_Closed lights the wall by the door's side 0x100007A2 (3 blue, 5 red, 1 purple)
                        ent.extra_props.append((0x100007A2, KIND_ENUM, int(sides[str(team)])))
                    ent.aura_radius = float(spec.get("radius", 6.0))
                    # a gate whose mesh is also floor (GH ramps); 2026-10-29 (tester report 2026-10-29 14:40): only with
                    # [ics] base_gate_keep_after_open (its collision ate the move clicks all match long)
                    ent.keep_after_open = bool(spec.get("keep")) and bool(self.ic.get("base_gate_keep_after_open", False))
                    # 2026-10-29 (tester report 2026-10-29 15:30): a "keep" gate is replaced by its floor copy at the
                    # start (Match._gate_floor_copy; [ics] base_gate_floor_copy, {} = removed as in fase3-ii)
                    ent.floor_copy = bool(spec.get("keep")) and bool(self.ic.get("base_gate_floor_copy"))
                    w.update(ent, f"spawn base {kind} t{team} ({spec['cls']:#x})")
                    store.append(ent)
                    names = ["Vfx_OnInit", "Object_Closed"] if kind == "gate" else ["Hotspot_Activate"]
                    for k, name in enumerate(names):
                        self.later(0.3 + 0.2 * k, lambda e=ent, n=name: w.scriptlet(e, n, f"{e.name}: {n} (0x8d)")
                                   if e.eid in w.entities else None)
                    if kind == "gate":
                        w.set_blocking(ent, True)
                        if self.ic.get("team_as_change", True):
                            # 2026-10-25 (stubborn-visuals.md 1): the door's tint comes from 0x100003A6, run only on a
                            # team CHANGE (listener 0xA813F0): 0, then the team, by 0x6
                            self.later(0.25, lambda e=ent, t=team: self.units.late_team(e, t))

    def _spawn_map_objects(self):
        """2026-10-26 (deep-scan-maps.md 1.7: the lane spawners 0x2E000D03 Tutorial 2 places on its lane-mouth markers;
        C keys / T2 positions, P PvP): per-map objects with team, side and start scriptlets ([ics] match_map_objects:
        map -> [{world_state, pos [x, y, z], yaw, team, side, scriptlets}])."""
        w = self.world
        for i, spec in enumerate((self.ic.get("match_map_objects") or {}).get(self.map.get("key")) or ()):
            ws = int(str(spec["world_state"]), 0)
            x, y, z = (list(spec["pos"]) + [self.map["z"]])[:3]
            try:
                ent = w.spawn(ws, [x, y, z], heading_from_yaw(float(spec.get("yaw", 0.0))), name=f"map object {i}",
                              start=False)
            except Exception as e:                     # noqa: BLE001
                self.log(f"map object {i} ({ws:#x}) not created ({e!r})")
                continue
            ent.kind, ent.health, ent.max_health, ent.kit = "prop", None, None, {}
            ent.pos[2] = float(z)
            team = int(spec.get("team", 0) or 0)
            if team:
                ent.team = team
                ent.extra_props.append((0x1000009C, 0x10, team))
            if spec.get("side"):
                ent.extra_props.append((0x100007A2, KIND_ENUM, int(spec["side"])))
            w.update(ent, f"spawn map object {i} ({ws:#x})")
            for k, name in enumerate(spec.get("scriptlets") or ()):
                self.later(0.4 + 0.3 * k, lambda e=ent, n=name: w.scriptlet(e, n, f"{e.name}: {n} (0x8d)")
                           if e.eid in w.entities else None)
            if team:
                self.later(1.0, lambda e=ent, t=team: self.units.late_team(e, t))

    def _spawn_decor_doors(self):
        """2026-10-30 (tester report 15:30: "near the blue base exit next to the fence there should always be an
        activated blue door; aesthetic, but part of the original map"; docs/re-notes/core-door-regen.md 4): doors that
        stay lit all match and never open ([ics] match_decor_doors: map -> [{world_state, pos [x, y, z], yaw, team,
        side, scale, scriptlets}]). The bare world state (no class) carries no collision polygon; the side lights the
        wall (Object_Closed's switch on 0x100007A2, crime-alley-visuals.md e) and the team goes again as a change."""
        w = self.world
        self.decor_doors = []
        for i, spec in enumerate((self.ic.get("match_decor_doors") or {}).get(self.map.get("key")) or ()):
            if not spec.get("enabled", True):
                continue
            ws = int(str(spec["world_state"]), 0)
            x, y, z = (list(spec["pos"]) + [self.map["z"]])[:3]
            team = int(spec.get("team", 0) or 0)
            try:
                ent = w.spawn(ws, [x, y, z], heading_from_yaw(float(spec.get("yaw", 0.0))),
                              name=f"decor door {i} t{team}", start=False)
            except Exception as e:                     # noqa: BLE001
                self.log(f"decor door {i} ({ws:#x}) not created ({e!r})")
                continue
            ent.kind, ent.health, ent.max_health, ent.kit = "prop", None, None, {}
            ent.pos[2] = float(z)
            props = [p for p in ent.extra_props if p[0] not in (0x1000009C, 0x100007A2, 0x6B4)]
            if team:
                ent.team = team
                props.append((0x1000009C, 0x10, team))
            if spec.get("side"):
                ent.side = int(spec["side"])
                props.append((0x100007A2, KIND_ENUM, int(spec["side"])))
            if spec.get("scale"):
                props.append((0x6B4, KIND_F32, float(spec["scale"])))
            ent.extra_props = props
            w.update(ent, f"spawn decor door {i} ({ws:#x}) t{team}")
            self.decor_doors.append(ent)
            for k, name in enumerate(spec.get("scriptlets") or ()):
                self.later(0.4 + 0.3 * k, lambda e=ent, n=name: w.scriptlet(e, n, f"{e.name}: {n} (0x8d)")
                           if e.eid in w.entities else None)
            if team and self.ic.get("team_as_change", True):
                self.later(1.0, lambda e=ent, t=team: self.units.late_team(e, t))

    def _structure_regen_tick(self, dt):
        """2026-10-30 (tester report 15:30: "my dampener does not regenerate even though time passes";
        core-door-regen.md 5): a damaged structure of [ics] match_structure_regen roles that nobody hit for "after" s
        heals "per_second" HP a second (vitals at most once a second)."""
        rules = self.ic.get("match_structure_regen") or {}
        if not rules:
            return
        for mu in self.structures:
            rule = rules.get(mu.role)
            ent = mu.ent
            if not rule or not ent.alive or not ent.max_health or (ent.health or 0) >= ent.max_health:
                continue
            if self.t - getattr(mu, "last_hit_t", -1e9) < float(rule.get("after", 10.0)):
                continue
            ent.health = min(float(ent.max_health), float(ent.health or 0) + float(rule.get("per_second", 0.0)) * dt)
            mu.shield_hp = ent.health
            if self.t - getattr(mu, "regen_vitals_t", -1e9) >= 1.0 or ent.health >= ent.max_health:
                mu.regen_vitals_t = self.t
                self.world.vitals(ent)

    def _spawn_socket_covers(self):
        """2026-10-25 (tester's video: opaque black shapes on the ground; black-ground-shapes.md, C: each sits on a
        terrain socket, ground vertices pushed down for a model that the server must place): the cover models
        ([ics] match_socket_covers: map -> [{world_state, pos [x, y, z], yaw, props}]; team 1 positions as given)."""
        self.covers = []
        w = self.world
        for i, spec in enumerate((self.ic.get("match_socket_covers") or {}).get(self.map.get("key")) or ()):
            ws = int(str(spec["world_state"]), 0)
            x, y, z = (list(spec["pos"]) + [self.map["z"]])[:3]
            site = spec.get("terrain_site")
            if site and self.ic.get("match_socket_covers_skip_flat", True) and self._socket_flattened(site):
                # 2026-10-28 (tester report 2026-10-28 15:00; map-audit-all.md 11): python ic.py patch has raised this
                # socket to the street, so the lid would only z-fight with it
                self.log(f"socket cover {i} ({ws:#x}) at ({x}, {y}) left out: terrain site {site} is flattened")
                continue
            try:
                ent = w.spawn(ws, [x, y, z], heading_from_yaw(float(spec.get("yaw", 0.0))), name=f"socket cover {i}",
                              start=False)
            except Exception as e:                     # noqa: BLE001
                self.log(f"socket cover {i} ({ws:#x}) not created ({e!r})")
                continue
            ent.pos[2] = float(z)                       # its own height (the socket's rim), not the navmesh's
            for k, v in (spec.get("props") or {}).items():
                prop = int(str(k), 0)
                # bool, f32 (a scale such as 0x6B4 = 2.5; map-object-census.md: it went as an int) or int
                ent.extra_props.append((prop, KIND_BOOL, 1 if v else 0) if isinstance(v, bool) else
                                       (prop, KIND_F32, float(v)) if isinstance(v, float) else (prop, 0x10, int(v)))
            ent.kind, ent.health, ent.max_health = "prop", None, None   # scenery: no ground snap, no vitals, no AI
            team = int(spec.get("team", 0) or (maps.T1 if x < 80 else maps.T2) if spec.get("team_by_side", True) else 0)
            if team:
                # 2026-10-25 17:47 (tester: the octagon is still there with the cover sent): the cover's only scriptlets
                # are the team-colour ones (_Entity_OnSetClientRelationship), as the turret plate's; give it its side's
                # team and the team as a change (units.late_team)
                ent.team = team
                ent.extra_props.append((0x1000009C, 0x10, team))
                self.later(1.0, lambda e=ent, t=team: self.units.late_team(e, t))
            w.update(ent, f"spawn socket cover {i} ({ws:#x})")
            self.covers.append(ent)

    def _socket_flattened(self, site):
        """Whether `python ic.py patch` has flattened this terrain site ([game] terrain_sockets) in the installed map
        pack: a read-only probe of the pack (icserver/terrainfix.py installed_state, cached per pack file); False when
        the pack or the site cannot be read."""
        rp = getattr(getattr(self.world, "data", None), "rp_dir", None)
        if not rp:
            return False
        try:
            from icserver import terrainfix
            state = terrainfix.installed_state(rp, site)
        except Exception as e:                         # noqa: BLE001
            self.log(f"terrain site {site}: state not read ({e!r})")
            return False
        return state == "patched"

    def remove_cover_at(self, pos, radius=4.0):
        """A pod rising out of its pit takes the pit's lid away (it comes back with [ics] ... not yet: P)."""
        for ent in list(getattr(self, "covers", ())):
            if math.hypot(ent.pos[0] - pos[0], ent.pos[1] - pos[1]) <= radius and ent.eid in self.world.entities:
                self.world.remove(ent, f"{ent.name} removed for the pod (0x3)")
                self.covers.remove(ent)

    def _spawn_stealth(self):
        """2026-10-24 00:55 (tester: the zones that make a champion invisible are missing): the map's stealth strips,
        world state [ics] match_stealth_world_state (0x2E000D36, Vfx_Active) per tile; a champion inside one gets the
        brush status [ics] match_stealth_status (0x4800028C, script 0x340001CF IsHidden) and the AI does not see it."""
        self.stealth = []
        # 2026-10-25 (crime-alley-visuals.md a): the hotspot entity 0x4000039D (template: ws 0x2E000D36, status
        # 0x4800028C, the 4 x 2 m box) rather than the bare world state; its Vfx_Active adds the hex mesh 0x2E000D37
        ws = int(self.ic.get("match_stealth_class", 0) or self.ic.get("match_stealth_world_state", 0x2E000D36) or 0)
        if not ws or not self.ic.get("match_stealth", True):
            return
        w = self.world
        size = self.ic.get("match_stealth_size") or [4.0, 2.0]
        # 2026-10-28 15:00 (tester: the side fields sit off the corner; stealth-alignment.md): per-tile overrides by map
        # key and tile index ([ics] match_stealth_overrides, {} = the map's list), as match_camp_overrides
        over_map = (self.ic.get("match_stealth_overrides") or {}).get(self.map.get("key")) or {}
        for i, spec in enumerate(self.map.get("stealth", ())):
            # 2026-10-29 18:31 (tester: the side fields still stand off the edge; maps.py "render"): the tile's edge on
            # the drawn wall ([ics] match_stealth_render_faces; false = the navmesh-face "pos")
            if spec.get("render") and self.ic.get("match_stealth_render_faces", True):
                spec = dict(spec, **spec["render"])
            # tester report 2026-10-29 19:55 (screenshot 63: "at both ends move this section a little further down, toward
            # the lane"; ca-ring-fog-bundles.md 4): a tile with "lane_dir" moves that many metres along it ([ics]
            # match_stealth_lane_shift; 0 = where maps.py puts it). Before the overrides, which still set "pos" outright
            shift = float(self.ic.get("match_stealth_lane_shift", 0.0) or 0.0)
            if spec.get("lane_dir") and shift:
                (px, py), (dx, dy) = spec["pos"], spec["lane_dir"]
                spec = dict(spec, pos=(round(px + dx * shift, 3), round(py + dy * shift, 3)))
            over = over_map.get(str(i)) or over_map.get(i) or {}
            if over:
                spec = dict(spec, **{k: (tuple(v) if k == "pos" else v) for k, v in over.items()})
                self.log(f"stealth strip {i}: [ics] match_stealth_overrides {over}")
            x, y = spec["pos"]
            yaw = float(spec.get("yaw", 0.0))
            # 2026-10-26 (tester: the stealth fields should lie on the ground; at the map's base height they sank under the
            # raised sidewalks and showed only at the curbs): the navmesh height at the tile ([ics] stealth_on_ground)
            gz = (w.nav.height(x, y) if w.nav is not None and self.ic.get("stealth_on_ground", True) else None)
            z = float(gz) + float(self.ic.get("stealth_ground_lift", 0.03)) if gz is not None else self.map["z"]
            try:
                ent = w.spawn(ws, [x, y, z], heading_from_yaw(yaw), name=f"stealth strip {i}", start=False,
                              world_state=int(self.ic.get("match_stealth_world_state", 0x2E000D36) or 0))
            except Exception as e:                     # noqa: BLE001
                self.log(f"stealth strip {i} not created ({e!r})")
                continue
            # the tile's long side lies along y at yaw 0, along x at yaw 90 (crime-alley-video-compare.md 1)
            long_, short = float(spec.get("size", size)[0]) / 2, float(spec.get("size", size)[1]) / 2
            # 2026-10-25 (crime-alley-still-missing.md 2, C from the frames: our yaw-90 tiles showed their long side
            # along y): the long side lies along x at yaw 0, along y at yaw 90
            ent.half = (long_, short) if abs(math.sin(math.radians(yaw))) < 0.5 else (short, long_)
            ent.tile = (math.radians(yaw), long_, short)     # the tile's own frame (inside_strip)
            w.update(ent, f"spawn stealth strip {i} ({ws:#x})")
            self.stealth.append(ent)
            mesh = int(str(self.ic.get("stealth_tile_direct", 0) or 0), 0)
            if mesh:
                # 2026-10-25 (tester: the stealth tiles show a "+" and streaks; stubborn-visuals.md 3, P): Vfx_Active
                # plays particle 0x18000A57 (the streaks) next to the hex mesh; the mesh alone, as a prop with the
                # tile's yaw ([ics] stealth_tile_direct = mesh world state, 0 = Vfx_Active as before)
                try:
                    me = w.spawn(mesh, [x, y, z], heading_from_yaw(yaw), name=f"stealth mesh {i}",
                                 start=False)
                    me.pos[2] = z
                    w.update(me, f"spawn stealth mesh {i} ({mesh:#x})")
                except Exception as e:                 # noqa: BLE001
                    self.log(f"stealth mesh {i} not created ({e!r})")
                if not self.ic.get("stealth_tile_vfx", True):
                    continue
            # 2026-10-28 (tester's frames: the original fields are purple hexes, ours white; stealth-rendering.md 5, C):
            # the purple is the tile's Vfx_Active particle 0x18000A57, the mesh alone is grey ([ics] stealth_tile_vfx)
            self.later(0.3, lambda e=ent: w.scriptlet(e, "Vfx_Active", f"{e.name}: Vfx_Active (0x8d)")
                       if e.eid in w.entities else None)

    def inside_strip(self, pos, s):
        """2026-10-26 (tester: the champion should turn invisible over the whole field): a point inside the tile's own
        rotated rectangle (the diagonal tiles were tested as axis-aligned boxes) plus [ics] stealth_margin m, the hex
        mesh reaching past the 4 x 2 m box."""
        yaw, long_, short = getattr(s, "tile", (0.0, s.half[0], s.half[1]))
        m = float(self.ic.get("stealth_margin", 0.5) or 0.0)
        dx, dy = pos[0] - s.pos[0], pos[1] - s.pos[1]
        u = dx * math.cos(yaw) + dy * math.sin(yaw)
        v = -dx * math.sin(yaw) + dy * math.cos(yaw)
        return abs(u) <= long_ + m and abs(v) <= short + m

    def strip_of(self, pos):
        """The index of the stealth strip holding a point, or None."""
        for i, s in enumerate(getattr(self, "stealth", ())):
            if self.inside_strip(pos, s):
                return i
        return None

    def visible_to(self, ent, viewer):
        """2026-10-24 23:05 (tester: inside a stealth zone a champion is invisible to the enemy unless the enemy stands
        in the same zone, or for a moment after it attacks an enemy minion / champion): [ics] match_stealth_hides."""
        if not self.ic.get("match_stealth_hides", True) or not getattr(ent, "in_stealth", False):
            return True
        if time.time() < getattr(ent, "revealed_until", 0.0):
            return True
        mine = self.strip_of(ent.pos)
        if mine is not None and self.ic.get("match_stealth_any_shared", True):
            # 2026-10-28 15:00 (stealth-alignment.md 6): the L's two tiles overlap at the bend; any strip holding both
            return any(self.inside_strip(ent.pos, s) and self.inside_strip(viewer.pos, s)
                       for s in getattr(self, "stealth", ()))
        return mine is not None and mine == self.strip_of(viewer.pos)

    def _spawn_nook(self):
        """2026-10-25 (tester: the middle camp has no floor; crime-alley-visuals.md b, P): the statics' server markers
        0x2E000944 / 945 at (80.0, 97.25) yaw 180 had an object the original server placed; best match the superpad
        0x40000CB5 ([ics] match_nook_pad: class, pos, yaw, scriptlets; {} = none)."""
        spec = self.ic.get("match_nook_pad") or {}
        if not spec or self.map.get("key") != "crime_alley":
            return
        w = self.world
        x, y = spec.get("pos", (80.0, 97.25))
        # 2026-10-30 (tester report 13:18: the pad floated; ca-strip-static-shadow.md 3): on the terrain ([ics]
        # match_nook_pad_z; 0 = the map's z)
        z = float(self.ic.get("match_nook_pad_z", 0.0) or 0.0) or self.map["z"]
        try:
            ent = w.spawn(int(spec["class"]), [x, y, z], heading_from_yaw(float(spec.get("yaw", 180.0))),
                          name="nook pad", start=False, world_state=int(spec.get("world_state", 0) or 0))
        except Exception as e:                         # noqa: BLE001
            self.log(f"nook pad not created ({e!r})")
            return
        if ent.class_id >> 24 in range(0x4A, 0x50):
            # 2026-10-26: a carrier class (exe patch) gets its world state's tables and scriptlet keys
            ent.kind, ent.health, ent.max_health, ent.kit = "prop", None, None, {}
            w.dress_spawned(ent)
        ent.kind, ent.health, ent.max_health, ent.kit = "prop", None, None, {}
        for k, v in (spec.get("props") or {}).items():
            # bool (kind 0x16) or enum (kind 0x08) bundle properties (the relay's lock: deep-scan-maps.md 1.2)
            prop = int(str(k), 0)
            ent.extra_props.append((prop, KIND_BOOL, 1 if v else 0) if isinstance(v, bool) else (prop, KIND_ENUM, int(v)))
        if not self.ic.get("match_nook_pad_map_note", False):
            # tester report 2026-10-29 21:10 (the big yellow circle and dot at the centre of our minimap; ca-fog-minimap-
            # ring.md 4): its template's category 26 note off ([ics] match_nook_pad_map_note)
            ent.extra_props = [p for p in ent.extra_props if p[0] != 0x100004DA] + [(0x100004DA, KIND_ENUM, 0)]
        self.nook_pad = ent
        w.update(ent, f"spawn nook pad ({int(spec['class']):#x})")
        for k, name in enumerate(spec.get("scriptlets") or []):
            self.later(0.3 + 0.2 * k, lambda n=name: w.scriptlet(ent, n, f"nook pad: {n} (0x8d)")
                       if ent.eid in w.entities else None)

    def unlock_nook(self):
        """The Raider comes: the relay's padlock goes (its lock bools false by 0x6, Vfx_Unlocked; deep-scan-maps.md 1.2,
        P polarity / timing)."""
        ent = getattr(self, "nook_pad", None)
        spec = self.ic.get("match_nook_pad") or {}
        if ent is None or ent.eid not in self.world.entities or getattr(ent, "unlocked", False):
            return
        ent.unlocked = True
        w = self.world
        for k in spec.get("unlock_props") or ():
            prop = int(str(k), 0)
            ent.extra_props = [p for p in ent.extra_props if p[0] != prop] + [(prop, KIND_BOOL, 0)]
            w.send(f"nook pad: {prop:#x} = false (0x6)", M.set_property(ent.eid, prop, KIND_BOOL, 0))
        # 2026-10-29 12:45 (tester report 2026-10-29 12:45: the central camp's padlock stays when the Raider appears; the
        # 12:18:57.898 run sent both bools false + Vfx_Unlocked, throw-truck-padlock.md 4): the padlock hologram is
        # Vfx_Locked's own particles (0x18000703 / 0x180006FB / 0x180007DF), a run that nothing ended; event 0x11F stops
        # every run of the key (instance 0xFFFFFFFF: the bundle resends may have restarted it) before Vfx_Unlocked
        # ([ics] match_nook_pad "unlock_stop": names; [] = as before)
        # tester report 2026-10-29 15:30 (the padlock still stays; throw-padlock-coredeath.md 2, C 0x588A80 / 0x57C4B0):
        # the 0x11F u8 is 0x57C4B0's mode, which the client's own key stop passes as 1 (fase3-ih sent 0), and the stop
        # goes again unlock_stop_again s later, after the client's own lock refresh ([ics] match_nook_pad
        # "unlock_stop_flag" / "unlock_stop_again")
        flag = int(spec.get("unlock_stop_flag", 0) or 0)

        def stop(again=False):
            if ent.eid not in w.entities:
                return
            for name in spec.get("unlock_stop") or ():
                key = w._config_key(name)
                if not key:
                    continue
                w.live_scriptlets.pop((ent.eid, key), None)
                w.send(f"nook pad: stop {name} (0x11f, every run, mode {flag}{', again' if again else ''})",
                       M.stop_scriptlet(ent.eid, key, 0xFFFFFFFF, flag))
        stop()
        for name in spec.get("unlock_scriptlets") or ():
            w.scriptlet(ent, name, f"nook pad: {name} (0x8d)")
        for at in spec.get("unlock_stop_again") or ():
            self.later(float(at), lambda: stop(True))

    def _stealth_tick(self):
        strips = getattr(self, "stealth", ())
        if not strips:
            return
        from .. import script_runtime as R
        from ..world import CastWorld
        status = int(self.ic.get("match_stealth_status", 0x4800028C) or 0)
        for ch in [c for c in self.champions() if c.alive]:
            inside = any(self.inside_strip(ch.pos, s) for s in strips)
            if inside == getattr(ch, "in_stealth", False):
                continue
            ch.in_stealth = inside
            shimmer = int(str(self.ic.get("stealth_shimmer_key", 0) or 0), 0)
            if shimmer:
                # 2026-10-28 (tester: the stealth fields still do nothing; stealth-rendering.md 1-4, C): the owner's look
                # is the champion's Vfx_Status_Stealth_Active 0x10000648 (purple particle 0x18000504), started on entry
                # and signalled off on exit by the server itself; the brush status script reached its S2 for 3 of 6
                # entries and left it within 0.5-2 s ([ics] stealth_shimmer_key, 0 = only the status script)
                if inside:
                    self.world.scriptlet(ch, shimmer, f"{ch.name}: Vfx_Status_Stealth_Active (0x8d)")
                else:
                    self.world.signal_scriptlet(ch, shimmer)
                    if self.ic.get("stealth_stop_hard", True):
                        # 2026-10-29 14:40 (tester: the stealth look stays seconds after leaving the field; it must go at
                        # once): the signal lets the run fade; event 0x11F stops every run of the key at once
                        # ([ics] stealth_stop_hard)
                        self.world.live_scriptlets.pop((ch.eid, shimmer), None)
                        self.world.send(f"{ch.name}: stop Vfx_Status_Stealth_Active (0x11f, every run)",
                                        M.stop_scriptlet(ch.eid, shimmer, 0xFFFFFFFF))
            if status:
                cw = CastWorld(self.world, ch, None)
                try:
                    if inside:
                        R.apply_status(cw, ch, ch, status, {})
                    else:
                        R.remove_status(cw, ch, status)
                except Exception as e:                 # noqa: BLE001
                    self.log(f"stealth status error: {e!r}")
            self.log(f"{ch.name} {'enters' if inside else 'leaves'} a stealth strip")

    def _open_gates(self):
        w = self.world
        for ent in getattr(self, "gates", ()):
            if ent.eid in w.entities:
                w.scriptlet(ent, "Object_Open", f"{ent.name}: Object_Open (0x8d)")
                w.set_blocking(ent, False)
                # 2026-10-23 19:22 (tester: the wall vanishes at the start but still blocks the way; the server's
                # paths were open, the champion's clicks stopped at x 28.6): the client keeps the door's collision
                # after Object_Open, so the door goes away ([ics] base_gate_remove_after s, < 0 = keep it)
                after = float(self.ic.get("base_gate_remove_after", 1.5))
                if after >= 0 and not getattr(ent, "keep_after_open", False):
                    if getattr(ent, "floor_copy", False):
                        # the copy first, so the ramps never vanish (both meshes overlap for 0.1 s)
                        self.later(max(0.0, after - 0.1), lambda e=ent: self._gate_floor_copy(e))
                    self.later(after, lambda e=ent: w.remove(e, f"{e.name} gone (0x3)") if e.eid in w.entities else None)

    def _gate_floor_copy(self, gate):
        """2026-10-29 (tester report 2026-10-29 15:30: on Gotham Heights a hole at the power core's exit and no ramps
        to the lanes once the base door goes at the start; gh-ca-floor-spawn.md 1-2): GH's Door world states
        0x2E00084A / 0x2E000845 are the base front's floor and ramps AND carry a Kynapse obstruction box (0x83C = 1,
        0x8C1 = 2 box, 0x8AA {0x858 (-30, -30, 0) .. 0x857 (30, 7.93, 4)}, yaw 0x856; 0x554EB0) that seals both base
        exits until the start; the client drops every move click inside it (0xA70030 navmesh snap) and Object_Open
        does not lift it (fase3-ih). The door goes; a copy of the same world state is created in its place with the
        instance properties [ics] base_gate_floor_copy["props"] (0x83C / 0x8C1 = 0: no obstruction component, no box;
        P that bundle values win over the world state's) and its open scriptlets, and stays all match."""
        spec = self.ic.get("base_gate_floor_copy") or {}
        w = self.world
        if not spec or gate.eid not in w.entities:
            return
        ws = int(getattr(gate, "world_state", 0) or getattr(gate, "gate_world_state", 0) or 0)
        try:
            cls = gate.class_id if spec.get("same_class", True) else ws
            copy = w.spawn(cls, list(gate.pos), gate.heading, name=f"{gate.name} floor", world_state=ws, start=False)
        except Exception as e:                         # noqa: BLE001
            self.log(f"{gate.name}: floor copy not created ({e!r})")
            return
        copy.team = gate.team
        props = [p for p in copy.extra_props if p[0] != 0x1000009C] + [(0x1000009C, 0x10, gate.team)]
        for k, v in (spec.get("props") or {}).items():
            pid = int(str(k), 0)
            props = [p for p in props if p[0] != pid] + [(pid, KIND_ENUM, int(v))]
        copy.extra_props = props
        w.update(copy, f"spawn {copy.name} ({cls:#x}, ws {ws:#x})")
        self.gate_floors = getattr(self, "gate_floors", []) + [copy]
        for k, name in enumerate(spec.get("scriptlets") or ()):
            self.later(0.3 + 0.2 * k, lambda e=copy, n=name: w.scriptlet(e, n, f"{e.name}: {n} (0x8d)")
                       if e.eid in w.entities else None)

    def _auras_tick(self):
        """Allies inside their base aura get the in-base status 0x48001109 (regen, in-base, may shop, speed); leaving
        gives 0x48001107 (a speed buff that ends on combat); [ics] base_aura_invulnerable makes them immune inside
        (the tester: a champion inside the white zone cannot be hurt)."""
        auras = getattr(self, "auras", ())
        if not auras:
            return
        from .. import script_runtime as R
        from ..world import CastWorld
        w = self.world
        st_in = int(self.ic.get("base_aura_status", 0x48001109) or 0)
        st_out = int(self.ic.get("base_aura_leave_status", 0x48001107) or 0)
        for ch in [c for c in self.champions() if c.alive]:
            inside = any(a.team == ch.team and math.hypot(ch.pos[0] - a.pos[0], ch.pos[1] - a.pos[1]) <= a.aura_radius
                         for a in auras)
            was = getattr(ch, "in_base_aura", False)
            if inside == was:
                continue
            ch.safe_zone = inside and bool(self.ic.get("base_aura_invulnerable", True))
            ch.in_base_aura = inside
            cw = CastWorld(w, ch, None)
            try:
                if inside:
                    if st_out:
                        R.remove_status(cw, ch, st_out)
                    if st_in:
                        R.apply_status(cw, ch, ch, st_in, {})
                else:
                    if st_in:
                        R.remove_status(cw, ch, st_in)
                    if st_out:
                        R.apply_status(cw, ch, ch, st_out, {})
            except Exception as e:                     # noqa: BLE001
                self.log(f"base aura status error: {e!r}")
            self.log(f"{ch.name} {'enters' if inside else 'leaves'} the base aura")

    # ---- the tick ----------------------------------------------------------------------------------------------------
    def tick(self, dt, now=None):
        now = time.time() if now is None else now
        raw = max(0.0, float(dt))
        dt = min(raw, 1.0)                   # the parts below keep the 1 s step
        # 2026-10-28 15:00 (tester report; test-2026-10-28-1439-sweep.md S2: after a 2.77 s freeze the match time ran
        # 1.77 s behind the HUD clock and the timeline, which follow the wall clock): the clock takes the whole step, up
        # to 10 s; every timer due by then fires below ([ics] match_clock_follows_wall)
        self.t += min(raw, 10.0) if self.ic.get("match_clock_follows_wall", True) else dt
        while self._timers and self._timers[0][0] <= self.t:
            _at, _n, fn = heapq.heappop(self._timers)
            try:
                fn()
            except Exception as e:             # noqa: BLE001 - a rule must never stop the match
                self.log(f"match timer error: {e!r}")
        if self.over:
            return
        if not self.begun and self.t >= 0:
            self._begin()
        self._auras_tick()
        self._stealth_tick()
        if not self.begun:
            return
        step = int(self.t // 90)
        if step != self._level_step:
            self._level_step = step
            self.units.level_up(self.t)
        self.waves.tick(self.t)
        self.units.tick(dt, now)
        self._structure_regen_tick(dt)
        self.bots.tick(dt, now)
        self.objectives.tick(dt)
        self.bosses.tick(dt)
        self.liftables.tick(dt)
        self.objectives.events_tick(self.t)
        self._pickups_tick()
        if self.mode == "domination":
            self._domination_tick(dt)
        self._surrender_tick()
        self.score.tick(self.t)

    # ---- queries used by the parts -----------------------------------------------------------------------------------
    def core(self, team):
        return next((mu for mu in self.structures if mu.role == "core" and mu.team == team), None)

    def _remove_core(self, team):
        """The losing core (with a head the server spawned on it) leaves the client when the end cinematic, which draws
        its own core and its fall, starts (throw-padlock-coredeath.md 3)."""
        mu = self.core(team)
        if mu is None:
            return
        for ent in (getattr(mu, "head", None), mu.ent):
            if ent is not None and ent.eid in self.world.entities:
                self.world.remove(ent, f"{ent.name}: removed for the end cinematic's core (0x3)")

    def structure_pos(self, role, team):
        spec = next((s for s in self.map["structures"] if s["role"] == role), None)
        return maps.team_pos(self.map, spec["pos"], team)[:2] if spec else None

    def dampener_down(self, lane, team):
        """Is the enemy's dampener on this lane destroyed (this team's waves then bring elites)?"""
        return any(mu.role == "dampener" and mu.lane == lane and mu.team != team and not mu.ent.alive
                   for mu in self.structures)

    def champion_aggressor(self, team, pos, radius):
        """An enemy champion that hit one of this team's champions in the last [ics] match_call_for_help s, near pos."""
        window = float(self.ic.get("match_call_for_help", 2.0))
        best = None
        for c in self.champions():
            rec = self.aggressors.get(c.eid)
            if (not c.alive or c.team == team or rec is None or rec[1] != team or self.t - rec[0] > window):
                continue
            d = math.hypot(c.pos[0] - pos[0], c.pos[1] - pos[1])
            if d <= radius and (best is None or d < best[0]):
                best = (d, c)
        return best[1] if best else None

    # ---- World events ------------------------------------------------------------------------------------------------
    def _champion_of(self, ent):
        """A damage source's champion: the missile's owner, a spawned object's creator (combat state), else itself."""
        e = self.owner(ent) or ent
        for _ in range(3):
            if getattr(e, "kind", "") == "champion" or e is None:
                break
            c = self.world.__dict__.get("_combat")
            creator = c.of(e).creator if c is not None and hasattr(e, "eid") else None
            if creator is None or creator is e:
                break
            e = creator
        return e

    @staticmethod
    def owner(ent):
        """The entity behind a damage source: a missile object's owner (ics.world.ObjectMissile), else itself."""
        for _ in range(4):
            missile = getattr(ent, "missile", None)
            owner = getattr(missile, "owner", None) if missile is not None else None
            if owner is None:
                break
            ent = getattr(owner, "entity", None) if not hasattr(owner, "eid") else owner
        return ent if hasattr(ent, "eid") else None

    def _on_event(self, event, **d):
        if event == "hit":
            self._on_hit(d.get("ent"), self.owner(d.get("source")))
        elif event == "killed":
            self._on_killed(d.get("ent"), self.owner(d.get("killer")))

    def _structure_ping(self, mu):
        """2026-10-25 (map-runtime-state.md 3, C mechanism: the client runs every structure's 0x34000838 itself and
        blinks its minimap note for 5 s on 0x100000E7, which only the server delivers): 0x2008 to an allied structure's
        client script on a hit, at most every [ics] match_structure_ping s."""
        gap = float(self.ic.get("match_structure_ping", 5.0) or 0)
        if gap <= 0 or mu.role not in STRUCTURES or mu.role == "foundry" or mu.team != self.local_team():
            return
        if self.t - getattr(mu, "pinged_at", -1e9) < gap:
            return
        mu.pinged_at = self.t
        self.send(f"{mu.ent.name}: under attack (0x2008 0x100000e7)",
                  M.entity_script_event(mu.ent.eid, 0x100000E7, 0x34000838))

    def _on_hit(self, victim, source):
        if victim is None:
            return
        self.units.on_hit(source)
        if self.ic.get("score_hit_owner", True) and source is not None:
            # 2026-10-28 13:52 (tester: the K/D/A counter is wrong; timeline-kda-endscreen.md 2): a skill's missile or
            # spawned object counts for its champion (only champions were recorded, so skill damage gave no assist)
            owner = self._champion_of(source)
            if owner is not None and getattr(owner, "team", 0) != getattr(victim, "team", 0):
                self.score.hit(victim, owner, self.t)
        else:
            self.score.hit(victim, source, self.t)
        mu = getattr(victim, "match_unit", None)
        if mu is not None:
            smu = getattr(source, "match_unit", None)
            device = smu is not None and smu.role == "device"     # the Doomsday Device hits a core in any order
            if mu.invulnerable or (self.protected(mu) and not device):
                victim.health = getattr(mu, "shield_hp", None) or victim.max_health
                return
            mu.shield_hp = victim.health
            mu.last_hit_t = self.t              # match_structure_regen waits from here
            self._structure_ping(mu)
            if mu.role in STRUCTURES and mu.role != "foundry" and source is not None:
                # 2026-10-25 (announcer-and-map-elements.md A2, C lines, P throttle): "<structure> under attack", once per
                # [ics] match_under_attack_gap s per structure; the line goes to the defenders (0x10000829 column)
                gap = float(self.ic.get("match_under_attack_gap", 15.0) or 0)
                if gap and self.t >= getattr(mu, "_attack_voice_at", -1e9) + gap:
                    mu._attack_voice_at = self.t
                    attacker = getattr(source, "team", 0) or 3 - mu.team
                    lane = f"{mu.role}_{mu.lane}_attack" if mu.lane else f"{mu.role}_attack"
                    per_map = (self.ic.get("announcer_events_by_map") or {}).get(self.map.get("key")) or {}
                    known = per_map.keys() | (self.ic.get("announcer_events") or {}).keys()
                    self.voice(lane if lane in known else f"{mu.role}_attack", source, victim, attacker)
            if mu.role == "core" and victim.max_health:
                done = getattr(mu, "health_voices", set())
                for pct, name in ((0.75, "core_75"), (0.50, "core_50"), (0.25, "core_25")):
                    if victim.health <= victim.max_health * pct and name not in done:
                        done.add(name)
                        self.voice(name, source, victim, 3 - mu.team)
                mu.health_voices = done
            if mu.role == "camp" and mu.camp is not None and source is not None and source in self.champions():
                mu.camp.provoker = source
                for other in mu.camp.members:
                    if other.ent.alive and other.target is None:
                        other.target = source
        # 2026-10-28 (tester: when one attacks an enemy champion, its towers and minions must turn on the attacker): the
        # attacker behind a missile / spawned object counts too, and the victim's allied minions and structures in sight
        # re-think at once instead of at their next 0.5-0.8 s retarget ([ics] match_call_for_help_now)
        attacker = self._champion_of(source) if source is not None else None
        if attacker is not None and victim in self.champions() and attacker in self.champions()                 and attacker.team != victim.team:
            self.aggressors[attacker.eid] = (self.t, victim.team)
            if self.ic.get("match_call_for_help_now", True):
                for other in list(self.units.by_eid.values()):
                    if other.team == victim.team and other.ent.alive and other.role in ("minion", "turret", "inner_turret",
                                                                                       "core_turret", "foundry"):
                        other.next_think = 0.0

    def _on_killed(self, victim, killer):
        if victim is None:
            return
        mu = getattr(victim, "match_unit", None)
        if victim in self.champions():
            self._champion_died(victim, killer)
            return
        if mu is None:
            return
        if victim.kind == "structure":
            victim.extra_props = [p for p in victim.extra_props if p[0] != PROP_LIFE] + [(PROP_LIFE, KIND_ENUM, M.LIFE_DEAD)]
        self._count_kill(victim, mu, killer)
        self.units.remove(mu)
        self._reward(victim, mu.cls, mu.level, killer)
        if mu.role in STRUCTURES:
            self._structure_died(mu, killer)
        elif mu.role == "camp" and mu.camp is not None:
            camp = mu.camp
            self.bosses.on_killed(mu, killer)
            if camp.spec.get("boss"):
                return                                  # a scheduled boss: Bosses decides its return
            if all(not x.ent.alive for x in camp.members):
                raider = (self.ic.get("match_raider") or {}).get(self.map.get("key")) or {}
                if camp.spec.get("middle") and raider and self.t + float((self.ic.get("match_camps") or {}).get(
                        "respawn_" + camp.spec.get("kind", "small"), 90.0)) >= float(raider.get("at", 1e9)):
                    # crime-alley-jungle.md 6 (G): from the Raider's time the pad is its: the middle camp stops
                    self.log(f"camp {camp.index} cleared: the Raider takes its pad")
                    return
                kind = camp.spec.get("kind", "small")
                wait = float((self.ic.get("match_camps") or {}).get("respawn_" + kind, 90.0))
                self.log(f"camp {camp.index} cleared: back in {wait:g} s")
                self.later(wait, lambda c=camp: self._spawn_camp(c))

    # streak voices by the killer's kills without dying, and multi-kills within match_multikill_window s
    STREAK_VOICES = {3: "relentless", 4: "furious", 5: "dominated", 6: "unstoppable", 7: "invincible"}
    MULTI_VOICES = {2: "double_kill", 3: "triple_kill", 4: "quadra_kill", 5: "penta_kill"}

    def _kill_voices(self, killer, victim, kp, victim_streak):
        """2026-10-23 13:14 (tester's announcer test: the events' lines named by ear): first blood, shutdown (the
        victim was on a streak of 3+), multi-kills, then the killer's streak; the whole enemy team down = annihilated."""
        team = getattr(killer, "team", 0)
        names = []
        if not getattr(self, "_first_blood", False):
            self._first_blood = True
            names.append("first_blood")
        elif victim_streak >= 3:
            names.append("shutdown")
        window = float(self.ic.get("match_multikill_window", 10.0))
        last = getattr(killer, "_last_kill", (-1e9, 0))
        count = last[1] + 1 if self.t - last[0] <= window else 1
        killer._last_kill = (self.t, count)
        if count >= 2:
            names.append(self.MULTI_VOICES[min(count, 5)])
        streak = kp.streak if kp is not None else 0
        if streak >= 3:
            names.append(self.STREAK_VOICES[min(streak, 7)])
        enemies = [c for c in self.champions() if c.team == victim.team]
        if len(enemies) > 1 and all(not c.alive for c in enemies):
            names.append("annihilated")
        if not names:
            names.append("champion_kill")      # 2026-10-25 (announcer-and-map-elements.md A1): the plain kill, event 30
        for k, name in enumerate(names):
            self.later(2.5 * k, lambda n=name: self.voice(n, killer, victim, team))

    def _structure_died(self, mu, killer):
        team = mu.team
        self.unlock_structures()
        name = {"turret": f"turret_{mu.lane or 'mid'}", "dampener": f"dampener_{mu.lane}" if mu.lane and f"dampener_{mu.lane}"
                in ((self.ic.get("announcer_events_by_map") or {}).get(self.map.get("key")) or {}) else "dampener",
                "core_turret": "core_turret",
                "inner_turret": f"turret_{mu.lane or 'mid'}"}.get(mu.role)
        if name:
            # the line's own / enemy form follows the team given: the destroyer's (2026-10-23 test: event 33 with our
            # team said "the enemy's Middle Turret has been destroyed")
            self.voice(name, killer, mu.ent, 3 - team)
        self.log(f"structure down: {mu} (team {team})")
        icon = self.ud.first(mu.cls, 0x10000083, 0) or 0
        self.announce(BILLBOARD_GENERIC, source_icon=icon, source_team=3 - team, target_team=team)
        if self.mode == "clash":
            loss = float((self.ic.get("match_clash_health_loss") or {}).get(mu.role, 0))
            self.hurt_team(team, loss)
        if mu.role == "dampener":
            if getattr(mu.ent, "keep_body", False):
                self.later(0.5, lambda e=mu.ent: self.world.scriptlet(e, "Object_Deactivate",
                                                                      f"{e.name}: Object_Deactivate (0x8d)"))
            ev = (self.ic.get("dampener_graph_events") or {}).get("death")
            if ev:
                # 2026-10-26 (deep-scan-maps.md 1.5, C graph 0x1A000B15: the dampener folds on its Death event)
                self.later(0.3, lambda e=mu.ent, v=int(str(ev), 0): self.world.graph_event(e, v, f"{e.name}: graph Death"))
            self.send("dampener counts (0x215c)", M.pvp_dampener_counts(
                [sum(1 for s in self.structures if s.role == "dampener" and s.team == t and s.ent.alive)
                 for t in (maps.T1, maps.T2)]))
            wait = float(self.ic.get("match_dampener_respawn", 0) or 0)
            if wait > 0:
                self.later(wait, lambda old=mu: self._respawn_structure(old))
                if wait > 30:
                    self.later(wait - 30, lambda: self.voice("dampener_reactivating", target=mu.ent, team=team))
        self._structure_death_visuals(mu)
        if mu.role in tuple((self.ic.get("match_core_shield") or {}).get("roles") or ()):
            self._core_shield(team, False)
            wait = float(self.ic.get("match_core_turret_respawn", 0) or 0) if mu.role == "core_turret" else 0.0
            if wait > 0 and not self.over:
                self.later(wait, lambda old=mu: self._respawn_structure(old))
        if mu.role == "core":
            self.end(3 - team, "core destroyed")

    def _structure_death_visuals(self, mu):
        """2026-10-29 (tester report from the original-game video: the Power Core Turret's two rings fall when it is
        destroyed; power-core-turret.md 4, C table 0x1D00035F): the structure's own death scriptlets ([ics]
        match_structure_death_scriptlets: role -> names; its _Defeat_OnDead stops Vfx_OnExplode, raises graph event
        Death 0x100001C0 and plays Vfx_Destruct_State0), match_structure_death_delay s after the death bundle."""
        names = list((self.ic.get("match_structure_death_scriptlets") or {}).get(mu.role) or ())
        delay = float(self.ic.get("match_structure_death_delay", 0.3) or 0.0)
        for k, name in enumerate(names):
            self.later(delay + 0.2 * k, lambda e=mu.ent, n=name: self.world.scriptlet(e, n, f"{e.name}: {n} (0x8d, destroyed)")
                       if e.eid in self.world.entities else None)

    def _core_shield(self, team, on):
        """2026-10-29 (tester report from the original-game video: a rotating ring around the Power Core while its
        Power Core Turret stands, gone when the turret falls; power-core-turret.md 3, C table 0x1D00098A): the core's
        Vfx_Indestructible (child 0x2E000A3A) while a structure of [ics] match_core_shield roles of its team lives,
        Vfx_Indestructible_Stop when the last one falls ({} = off)."""
        cfg = self.ic.get("match_core_shield") or {}
        roles = tuple(cfg.get("roles") or ())
        if not roles:
            return
        guards = [mu for mu in self.structures if mu.team == team and mu.role in roles]
        if not guards or (on and not any(mu.ent.alive for mu in guards)) or (not on and any(mu.ent.alive for mu in guards)):
            return
        core = next((mu for mu in self.structures if mu.team == team and mu.role == "core" and mu.ent.alive), None)
        if core is None:
            return
        core.shielded = on
        delay = float(cfg.get("delay", 1.2) or 0.0) if on else 0.0
        for k, name in enumerate(cfg.get("on" if on else "off") or ()):
            self.later(delay + 0.2 * k, lambda e=core.ent, n=name: self.world.scriptlet(e, n, f"{e.name}: {n} (0x8d, shield)")
                       if e.eid in self.world.entities and e.alive else None)

    def structure_down(self, roles, team, lane=None):
        """Is a structure of one of these roles of this team (on this lane, or lane-less) destroyed and not back?"""
        return any(mu.team == team and mu.role in roles and not mu.ent.alive and (lane is None or mu.lane in (None, lane))
                   for mu in self.structures)

    def core_turret_down(self, team):
        """Is this team's Power Core Turret destroyed (and not back yet)? False on maps without one."""
        ct = [mu for mu in self.structures if mu.team == team and mu.role == "core_turret"]
        return bool(ct) and not any(mu.ent.alive for mu in ct)

    def _respawn_structure(self, old):
        if self.over:
            return
        if old.ent.eid in self.world.entities:
            self.world.remove(old.ent, f"{old.ent.name}: old body gone (0x3)")   # the kept dampener body
        mu = self._spawn_structure(old.spec, old.team, keep=old)
        self._link_structures()
        self.unlock_structures()
        self.log(f"structure back: {mu}")
        if mu.role in tuple((self.ic.get("match_core_shield") or {}).get("roles") or ()):
            self._core_shield(mu.team, True)
        if mu.role == "dampener":
            self.voice("dampener_reactivated", target=mu.ent, team=mu.team)

    # ---- rewards -----------------------------------------------------------------------------------------------------
    def _reward(self, victim, cls, level, killer):
        if not self.ic.get("match_rewards_from_data", True):
            return
        champs = self.champions()
        kteam = killer.team if killer is not None and killer.team in (maps.T1, maps.T2) else (3 - victim.team)
        if kteam not in (maps.T1, maps.T2):
            return
        radius = float(self.ic.get("match_reward_radius", 15.0))
        near = [c for c in champs if c.alive and c.team == kteam and c.distance_to(victim) <= radius]
        last = killer if killer in champs else None
        if last is not None and last not in near:
            near.append(last)
        kmu = getattr(killer, "match_unit", None)
        by_turret = kmu is not None and kmu.role in STRUCTURES
        for c in near:
            xp, cr, _b = self.units.rewards(cls, level, c.level, len(near), last_hit=c is last, by_turret=by_turret)
            if c is not last and not by_turret and last is not None:
                cr = 0.0 if victim.kind != "structure" else cr      # minion gold goes to the last hitter
            self.grant(c, victim, cr, xp)
        bounty = self.units.rewards(cls, level, 1, 1)[2]
        if bounty:
            for c in champs:
                if c.team == kteam:
                    self.grant(c, victim, bounty, 0.0)

    # the end page's kills map keys (hud-shop-timeline-kills.md 6.1, C): 0x8 champions, 0x10 turrets, 0x100 creatures,
    # 0x10000 drones, 0x40000 guardians
    KILL_KEYS = {"minion": 0x10000, "camp": 0x100, "turret": 0x10, "inner_turret": 0x10, "core_turret": 0x10}

    def _count_kill(self, victim, mu, killer):
        if not self.ic.get("match_stats_ledger", True):
            return
        champ = self._champion_of(killer)
        if getattr(champ, "kind", "") != "champion":
            return
        st = champ.__dict__.setdefault("match_stats", {})
        kills = st.setdefault("kills", {})
        if mu is None:
            key = 0x8 if victim.kind == "champion" else 0
        elif mu.cls == 0x40000430:
            key = 0x40000                                   # the Doomsday Guardian
        else:
            key = self.KILL_KEYS.get(mu.role, 0)
        if key:
            kills[key] = kills.get(key, 0) + 1
        boss = getattr(mu, "boss", None)
        if boss in ("raider", "leviathan"):
            st[boss] = st.get(boss, 0) + 1
        if mu is not None and mu.role == "dampener":
            st["dampeners"] = st.get("dampeners", 0) + 1

    def end_rows(self):
        """One 0x2045 row per player from the scoreboard and its agent's match stats (end_stats_from_ledger)."""
        out = []
        for p in self.score.players:
            a = p.agent
            st = dict(getattr(a, "match_stats", {}) or {})
            kills = dict(st.get("kills") or {})
            if p.kills:
                kills[0x8] = p.kills
            # 2026-10-26 (end-stats-2045.md, C: the stats block starts at +0x78; every index was one too high)
            reads = {6: p.deaths, 7: p.assists, 11: st.get("credits", getattr(p, "money", 0.0)),
                     26: st.get("xp", 0.0), 37: st.get("dealt", 0.0), 47: st.get("dealt_1", 0.0),
                     48: st.get("dealt_champ_1", 0.0), 51: st.get("dealt_2", 0.0), 52: st.get("dealt_champ_2", 0.0),
                     36: st.get("taken", 0.0), 45: st.get("taken_champ", 0.0), 49: st.get("taken_champ_1", 0.0),
                     55: st.get("taken_champ_2", 0.0), 38: st.get("reduced", 0.0), 39: st.get("healed", 0.0),
                     40: st.get("heal_received", 0.0), 57: st.get("credits_champions", 0.0),
                     58: st.get("credits_drones", 0.0), 59: st.get("credits_creatures", 0.0),
                     60: st.get("credits_objectives", 0.0), 61: st.get("xp_champions", 0.0),
                     62: st.get("xp_drones", 0.0), 63: st.get("xp_creatures", 0.0), 64: st.get("xp_objectives", 0.0),
                     19: st.get("raider", 0), 20: st.get("leviathan", 0), 44: st.get("dampeners", 0)}
            champion_iid = M.CHAMPION_AGENT_ID if a is self.world.champion else getattr(a, "eid", 0)
            player_iid = M.LOCAL_PLAYER_ID if a is self.world.champion else p.player_iid
            row = {"team": p.team, "name": p.name, "bot": p.bot, "kills": kills, "reads": reads, "account": 0,
                   "send_team": bool(self.ic.get("end_stats_team", True))}
            if self.ic.get("end_stats_unique_accounts", True):
                # 2026-10-28 13:52 (tester: the score screen shows no data; timeline-kda-endscreen.md 3, C): the end page
                # keys each row's upgrades / power graph by the account IID (+0x08) and Flash waits until it has one
                # per row: every row needs its own (the local player's account, a bot's player IID)
                row["account"] = int(p.account or player_iid)
            if self.ic.get("end_stats_upgrades", True):
                # same report: the row's artifact slots (entry +0x2FC), so 0xA3AC70 delivers UpdateCurrentUpgrades /
                # UpdatePowerGraphValues for it; the champion DID (+0x1C) and level (+0x20) feed the graph and portrait
                inv = list(getattr(a, "inventory", None) or [])[:6]
                inv += [0] * (6 - len(inv))
                row["upgrades"] = [(d, 1 if d else 0) for d in inv]
                row["champion"] = int(p.champion or 0)
                row["level"] = int(getattr(a, "level", 1) or 1)
            out.append((player_iid, champion_iid, row))
        return out

    def _source_kind(self, ent):
        """champions / drones / creatures / objectives: where a reward came from (end page stats)."""
        if getattr(ent, "kind", "") == "champion":
            return "champions"
        mu = getattr(ent, "match_unit", None)
        role = getattr(mu, "role", "")
        return "drones" if role == "minion" else "creatures" if role == "camp" else "objectives"

    def grant(self, champ, over, credits, xp):
        w = self.world
        if self.ic.get("match_stats_ledger", True) and getattr(champ, "kind", "") == "champion":
            st = champ.__dict__.setdefault("match_stats", {})
            src = self._source_kind(over)
            st["credits"] = st.get("credits", 0.0) + max(0.0, credits)
            st[f"credits_{src}"] = st.get(f"credits_{src}", 0.0) + max(0.0, credits)
            st["xp"] = st.get("xp", 0.0) + max(0.0, xp)
            st[f"xp_{src}"] = st.get(f"xp_{src}", 0.0) + max(0.0, xp)
        p = self.score.by_agent(champ)
        if credits > 0:
            champ.gold += credits
            if p is not None:
                p.money += credits
            if champ is w.champion:
                self.send(f"+{credits:.0f} credits over {over.name} (0x100004d6)", M.floaty_currency(over.eid, credits))
        if xp > 0:
            champ.xp += int(round(xp))
            levels = [int(x) for x in self.ic.get("xp_levels") or ()]
            level = min(1 + sum(1 for need in levels if champ.xp >= need), int(self.ic.get("level_cap", 20)))
            if level > champ.level and champ is w.champion:
                w.set_level(level)
            elif level > champ.level and getattr(champ, "bot", False):
                w.bot_level(champ, level)
            elif level > champ.level:
                champ.level = level
        if champ is w.champion and (credits > 0 or xp > 0):
            w.refresh_champion(f"{champ.name}: {champ.gold:.0f} credits, {champ.xp} XP")
        self.score.dirty = True

    def champion_bounty(self, victim_player, victim):
        """The champion kill bounty: formula 0x3B0000B7 uses a server-only expression (units-and-ai.md 3.3); its
        description: Bounty_Base 400, +20 % per consecutive kill up to 900, down to 75 on death streaks, ramped by the
        victim's level 2..6 from x0.6 to x1. The death-streak step (-20 %) is authored."""
        base = float(self.ic.get("match_bounty_base", 400.0))
        streak = victim_player.streak if victim_player else 0
        deaths = victim_player.death_streak if victim_player else 0
        value = min(900.0, base * (1 + 0.2 * streak)) if streak else max(75.0, base * (1 - 0.2 * deaths))
        ramp = 0.6 + 0.4 * min(max((victim.level - 2) / 4.0, 0.0), 1.0)
        return value * ramp

    def _kill_card(self, killer, assists, victim=None):
        """2026-10-25 (sweep-flash-hud.md 2.1, sweep-s2c-ui.md: the only gap a player sees in the normal flow): the
        death screen's "killed by" card, notice 0x1000021C to the victim: the killer and assisters (live entities),
        their icons and teams, the killer's name; per-slot damage columns empty (P) ([ics] match_kill_card)."""
        w = self.world
        killer = self._champion_of(killer) or killer
        people = [e for e in [killer] + [getattr(a, "agent", None) for a in assists] if e is not None]
        people = [e for e in people if getattr(e, "eid", None) and (e is w.champion or e.eid in w.entities)]
        if not people:
            return
        icons, teams = [], []
        for e in people:
            icon = 0
            if getattr(e, "kind", "") == "champion":
                try:
                    icon = int(w.data.champion_name(e.class_id)[1] or 0)
                except Exception:                      # noqa: BLE001
                    icon = 0
            else:
                icon = int(self.ud.first(e.class_id, 0x10000083, 0) or 0)
            icons.append(icon)
            teams.append(int(getattr(e, "team", 0) or 0))
        ledger = getattr(victim, "damage_ledger", None) or {}
        damage = [ledger.get(e.eid, {}) for e in people]
        type_totals = [0.0] * 5
        for rec in ledger.values():
            for t, v in (rec.get("by_type") or {}).items():
                if 0 < int(t) < 5:
                    type_totals[int(t)] += v
        layout = str(self.ic.get("kill_card_layout", "reader")) == "reader"
        # the killer's name comes from the client's match roster for a champion; an override for anything else
        name = "" if (layout and getattr(people[0], "kind", "") == "champion") else people[0].name
        self.send(f"kill card: {', '.join(e.name for e in people)} (notice 0x1000021c)",
                  M.kill_card([e.eid for e in people], icons, teams, name, damage, type_totals, reader_layout=layout))

    def _champion_died(self, victim, killer):
        w = self.world
        vp = self.score.by_agent(victim)
        credit = killer
        if self.ic.get("score_kill_owner", True) and killer is not None:
            # 2026-10-28 13:52 (tester: the K/D/A counter is wrong; timeline-kda-endscreen.md 2): a kill by a skill's
            # missile / spawned object is its champion's
            credit = self._champion_of(killer)
        kp = self.score.by_agent(credit) if credit is not None else None
        if (kp is None or kp.team == victim.team) and self.ic.get("score_kill_credit_last_champion", True):
            # same report: a champion finished by a turret, a minion or a creature goes to the last enemy champion who
            # hit it within match_assist_window s (as the original's scoreboard; none = no kill for anyone)
            lp = self.score.last_damager(victim, self.t)
            if lp is not None:
                kp, credit = lp, lp.agent
        assists = self.score.assisters(victim, credit, self.t)
        victim_streak = vp.streak if vp is not None else 0
        if vp is not None:
            vp.deaths += 1
            vp.death_streak += 1
            bounty = self.champion_bounty(vp, victim)
            vp.streak = 0
        else:
            bounty = 0.0
        if kp is not None and kp.team != victim.team:
            kp.kills += 1
            kp.streak += 1
            kp.death_streak = 0
            xp = self.ud.reward(victim.class_id, 0x10000224, KilledLevel=victim.level, KillerLevel=kp.agent.level,
                                NumReceivers=1 + len(assists)) or 0.0
            self.grant(kp.agent, victim, bounty, xp)
            share = float(self.ic.get("match_assist_share", 0.5)) * bounty / max(1, len(assists))
            for a in assists:
                a.assists += 1
                self.grant(a.agent, victim, share, xp)
        if self.ic.get("takedown_script_event", True):
            # 2026-10-25 (skill-mechanics-recipes.md 6, P: 10 PvP passives): 0x10000097 {victim 0x9A6A765} on the killer
            # and on every assister (0x10000098 = the killing blow, raised by World)
            for who in [credit] + [a.agent for a in assists]:
                if who is not None and getattr(who, "kind", "") == "champion" and who is not victim:
                    w.raise_event(who, 0x10000097, {0x9A6A765: victim})
        shown = killer
        if self.ic.get("kill_feed_shows_credit", True) and credit is not None and credit is not killer \
                and getattr(credit, "kind", "") == "champion" and kp is not None and kp.team != victim.team:
            # 2026-10-28 15:00 (tester report; test-2026-10-28-1439-sweep.md S9: bot deaths 3 and 4 were GL's kills, yet
            # the kill feed said "by turret mid t1" and the announcer had no portraits, its source not a champion): the
            # kill feed and the announcer name the credited champion (a missile's / spawned object's champion too); the
            # victim's kill card keeps the real killer ([ics] kill_feed_shows_credit)
            shown = credit
        self.score.kill_feed(victim, shown, assists)
        if victim is w.champion and self.ic.get("match_kill_card", True):
            self._kill_card(killer, assists, victim)
        if shown is not None and getattr(shown, "team", 0) != victim.team:
            self._kill_voices(shown, victim, kp, victim_streak)
        self.score.dirty = True
        if self.mode == "clash":
            self.hurt_team(victim.team, float((self.ic.get("match_clash_health_loss") or {}).get("champion", 0)))
        # respawn: time by level ([ics] match_respawn_seconds, authored) at the team's start point
        table = self.ic.get("match_respawn_seconds") or [5.0]
        wait = float(table[min(max(victim.level, 1), len(table)) - 1])
        start = maps.spawn_point(self.encounter, victim.team, vp.slot if vp else 0)
        if victim is w.champion:
            self.ic["respawn_seconds"] = wait          # World.damage reads it right after this event
            if start:
                w.spawn_pos = [start[4], start[5], start[6]]
        else:
            self.send(f"{victim.name}: dead for {wait:g} s (0x100000bc)",
                      M.defeat_status_entity(victim.eid, M.DEFEAT_DEAD, time.time() + wait))
            self.later(wait, lambda v=victim, s=start: self._respawn_other(v, s))

    def _respawn_other(self, ent, start):
        """A champion other than the session's own (bots, other players' agents): back at its team's start."""
        w = self.world
        ent.alive = True
        ent.health = ent.max_health
        if start:
            ent.pos = [start[4], start[5], start[6]]
        ent.dest, ent.path, ent.attack_target, ent.speed = None, [], None, 0.0
        ent.damage_ledger = {}
        if getattr(ent, "bot", False):
            # 2026-10-25 (bot-champions.md 3.2): the bot kept its object; full health and Will, a teleport (tele_seq)
            # and LifeState 4 by 0x6
            w.recompute_stats(ent, refill=True)
            ent.health = ent.max_health
            if getattr(ent, "resource_vital", 5) == 5:
                ent.will = ent.max_will
            ent.tele_seq = (getattr(ent, "tele_seq", 1) % 255) + 1
            self.send(f"{ent.name}: LifeState 4 (0x6)", M.set_property(ent.eid, 0x100000FA, KIND_ENUM, M.LIFE_ALIVE))
        if ent.eid not in w.entities:
            w.add(ent)
        self.send(f"{ent.name}: alive (0x100000bc)", M.defeat_status_entity(ent.eid, M.DEFEAT_ALIVE, time.time()))
        # 2026-10-28 15:00 (tester report 2026-10-28 15:00; object-update-bundles.md 11.3): a full bundle in delta mode too
        # while [ics] delta_full_on_life_change (the bots' late flags follow it, Bots.respawned)
        w.update(ent, f"{ent.name} respawns", full=w.life_full())
        w.vitals(ent)
        if getattr(ent, "bot", False):
            # 2026-10-26 19:51 (tester: a defeated bot still walks back from the base lying down): one get-up 0.15 s after
            # the bundle was not enough; it goes again later with _Combat_GoToLocomotion ([ics] bot_getup_delays,
            # bot_getup_scriptlets)
            for k, at in enumerate(self.ic.get("bot_getup_delays") or [0.15]):
                self.later(float(at), lambda e=ent, again=k > 0: (
                    w.get_up(e),
                    [w.scriptlet(e, n, f"{e.name}: {n} (0x8d, respawn)") for n in (self.ic.get("bot_getup_scriptlets") or ())])
                    if e.alive else None)
        w.respawn_event(ent)
        self.bots.respawned(ent)

    # ---- team health (Gotham Heights, Clash) -------------------------------------------------------------------------
    def hurt_team(self, team, amount):
        if amount <= 0 or team not in self.team_health:
            return
        self.team_health[team] = max(0.0, self.team_health[team] - amount)
        self.send_team_health()
        if self.team_health[team] <= 0:
            self.end(3 - team, "team health")

    def send_team_health(self, initial=False):
        teams = sorted(self.team_health)
        now = [math.ceil(self.team_health[t]) for t in teams]
        if initial:
            self.send("team health (0x100004fb)", M.pvp_team_health_initial(
                teams, [self.team_health_start[t] for t in teams], now))
        elif now != [self._health_sent.get(t) for t in teams]:
            self.send(f"team health {now} (0x10000134)", M.pvp_team_health(teams, now))
        self._health_sent = dict(zip(teams, now))

    def _domination_tick(self, dt):
        """Gotham Heights (P: holding more points than the enemy drains its team health; the rate is authored:
        [ics] match_domination)."""
        cfg = self.ic.get("match_domination") or {}
        rate = float(cfg.get("drain_per_point", 1.0))
        diff = self.objectives.owned(maps.T1) - self.objectives.owned(maps.T2)
        if diff:
            loser = maps.T2 if diff > 0 else maps.T1
            self.team_health[loser] = max(0.0, self.team_health[loser] - rate * abs(diff) * dt)
            self.send_team_health()
            if self.team_health[loser] <= 0:
                self.end(3 - loser, "team health")

    def on_objective(self, cap, old, new):
        icon = cap.icon or 0
        if new:
            self.announce(BILLBOARD_GENERIC, source_icon=icon, source_team=new, target_team=old or -1)
        # 2026-10-25 (map-gaps-*.md): the objective's own announcer line (names per map in announcer_events_by_map:
        # relay_captured / relay_neutralized; capture_<slot> for Gotham Heights' points once their order is known)
        if new:
            self.voice(f"{cap.role}_captured_{cap.slot}" if f"{cap.role}_captured_{cap.slot}" in (
                (self.ic.get("announcer_events_by_map") or {}).get(self.map.get("key")) or {}) else f"{cap.role}_captured",
                       team=new)
        elif old:
            self.voice(f"{cap.role}_neutralized", team=old)
        if self.mode == "domination" and new:
            kill_cost = float((self.ic.get("match_domination") or {}).get("capture_cost", 0.0))
            self.hurt_team(3 - new, kill_cost)

    # ---- camps and pickups -------------------------------------------------------------------------------------------
    def _spawn_camp(self, camp):
        if self.over:
            return
        camp.members = []
        camp.provoker = None
        over = (self.ic.get("match_camp_overrides") or {}).get(str(camp.index)) or {}
        if over:
            camp.spec = dict(camp.spec, **{k: (tuple(v) if k == "pos" else v) for k, v in over.items()})
        cx, cy = camp.spec["pos"]
        camp.spec = dict(camp.spec, units=self.bosses.camp_units(camp.index, list(camp.spec["units"])))
        n = len(camp.spec["units"])
        neutral = int(self.ic.get("match_neutral_team", 3))
        # 2026-10-28 15:00 (tester report 2026-10-28 15:00: the camps stand in the wrong places; camps-colour-bar-
        # positions.md 3): unit i on the camp's slot i, the slots moved with "pos" ([ics] match_camp_slots; else the ring)
        slots = list(camp.spec.get("slots") or ()) if self.ic.get("match_camp_slots", True) else []
        sx, sy = (float(slots[0][0]), float(slots[0][1])) if slots else (cx, cy)
        # 2026-10-30 (timeline-tooltip-camp-prespawn.md 2): the first spawn's phase lasts until camp.phase_until (match
        # time, set from match_camp_prespawn_*); respawns phase match_camp_phase_seconds
        until = camp.__dict__.pop("phase_until", None)
        for i, cls in enumerate(camp.spec["units"]):
            if slots:
                px, py = cx + float(slots[i % len(slots)][0]) - sx, cy + float(slots[i % len(slots)][1]) - sy
            else:
                a = 2 * math.pi * i / max(1, n)
                r = 0.0 if i == 0 else 2.0
                px, py = cx + r * math.cos(a), cy + r * math.sin(a)
            heading = heading_from_yaw(float(camp.spec["yaw"])) if "yaw" in camp.spec else 0.0
            mu = self.units.spawn(cls, (px, py), neutral, "camp", heading=heading, name=f"camp {camp.index} {cls:#x}")
            mu.home = list(mu.ent.pos)
            mu.camp = camp
            camp.members.append(mu)
            names = list(self.ic.get("match_camp_spawn_scriptlets") or ())
            phase = self._camp_phase(cls)
            if phase > 0 and until is not None:
                lead = float(self.ic.get("match_camp_spawn_delay", 0.4)) + 0.3 * max(0, len(names) - 1)
                phase = max(phase, until - self.t - lead)
            if phase > 0:
                # 2026-10-28 13:52 (tester: the camps stay in their phase-in; an attack drops it at once;
                # jungle-camps-spawn.md 2-3): while phasing a camp unit takes no damage, is not provoked and its
                # targeting flags are held (World._late_flags / Units._late_flag), so no movement bundle drops the effect
                mu.invulnerable = True
                mu.phasing = True
                if self.ic.get("match_camp_phase_untargetable", True):
                    mu.ent.hold_flags = True
            for k, name in enumerate(names):
                # 2026-10-25 19:28 (tester: camps respawn with an animation; crime-alley-jungle.md: table 0x1D000674's
                # Vfx_Spawn_Event02 = the yellow phase-in overlay 0x17001445, P)
                # 2026-10-28 12:56: the first key match_camp_spawn_delay s after the bundle (was 0.4)
                self.later(float(self.ic.get("match_camp_spawn_delay", 0.4)) + 0.3 * k,
                           lambda e=mu.ent, s=name, p=phase: self._camp_phase_in(e, s, p))
            if phase > 0:
                self.later(float(self.ic.get("match_camp_spawn_delay", 0.4)) + 0.3 * (len(names) - 1) + phase,
                           lambda m=mu: self._camp_phase_end(m))
        self.log(f"camp {camp.index} at ({cx}, {cy}): {n} units")

    def _camp_phase_in(self, ent, name, phase):
        """One phase-in key on a camp unit. Its render effect is persistent (field 0x375 = 1): it lasts while the run
        lives (jungle-camps-spawn.md 1). During the phase it is re-sent after any full bundle of the unit
        (World._resend_looping), which re-creates the object and drops it."""
        if ent.eid not in self.world.entities or not ent.alive:
            return
        if not self.world.scriptlet(ent, name, f"{ent.name}: {name} (0x8d)") or phase <= 0:
            return
        key = self.data_key(name)
        if key and self.ic.get("match_camp_phase_resend", True):
            loops = self.world.__dict__.setdefault("looping_scriptlets", {})
            now = time.time()
            loops[(ent.eid, key)] = (None, now, now + phase + 1.0, 0)

    def _camp_phase(self, cls):
        """Seconds a camp unit of this class phases in: match_camp_phase_seconds when its tables hold one of
        match_camp_spawn_scriptlets (the Crime Alley jungle's 0x1D000674), else 0."""
        phase = float(self.ic.get("match_camp_phase_seconds", 0.0) or 0.0)
        if phase <= 0:
            return 0.0
        data = self.world.data
        keys = set(data.scriptlets(cls, data.champion_world_state(cls)))
        return phase if any(self.data_key(n) in keys for n in self.ic.get("match_camp_spawn_scriptlets") or ()) else 0.0

    def data_key(self, name):
        return self.world.data.scriptlet_key(name) if isinstance(name, str) else int(name)

    def _camp_phase_end(self, mu):
        """2026-10-28 13:52 (tester: the camps never leave their phase-in; jungle-camps-spawn.md 1-3): phasing complete.
        The persistent phase-in run is signalled to stop ([ics] match_camp_phase_stop), the unit becomes targetable
        and attackable, and one bundle follows (as the director's "targetable"; it also drops whatever of the
        phase-in a stop left, [ics] match_camp_phase_end_bundle)."""
        ent, w = mu.ent, self.world
        mu.invulnerable = False
        mu.phasing = False
        if ent.eid not in w.entities or not ent.alive:
            return
        loops = w.__dict__.get("looping_scriptlets") or {}
        for name in self.ic.get("match_camp_spawn_scriptlets") or ():
            key = self.data_key(name)
            loops.pop((ent.eid, key), None)
            if self.ic.get("match_camp_phase_stop", True):
                w.signal_scriptlet(ent, key)
        if getattr(ent, "hold_flags", False):
            ent.hold_flags = False
            flags = ent.__dict__.pop("pending_flags", None)
            if flags:
                w._late_flags(ent, flags)
            perceived = ent.__dict__.pop("pending_unit_flag", None)
            if perceived is not None:
                self.units._late_flag(ent, perceived)
            vitals = ent.__dict__.pop("pending_vitals", None)
            if vitals:
                # 2026-10-28 15:00 (tester report: no bar over the camps; camps-colour-bar-positions.md 8.3): the bar's
                # FloatyVitals after the flags, so the push carries PerceivedType 0x100 ([ics] match_camp_vitals_tags)
                self.units.late_vitals(ent, vitals)
        if self.ic.get("match_camp_phase_end_bundle", True):
            self.later(0.1, lambda: w.update(ent, f"{ent.name}: phasing complete (bundle)")
                       if ent.eid in w.entities and ent.alive else None)

    def add_pickup(self, cls, pos, credits):
        try:
            ent = self.world.spawn(cls, [pos[0], pos[1], self.map["z"]], 0.0, name=f"pickup {cls:#x}")
        except Exception as e:                     # noqa: BLE001 - its pack may not be loaded on this server
            self.log(f"pickup {cls:#x} not created ({e!r})")
            return None
        self.send(f"spawn pickup {cls:#x}", self.world.bundle(ent))
        self.pickups.append((ent, credits))
        return ent

    def _pickups_tick(self):
        if not self.pickups:
            return
        keep = []
        for ent, credits in self.pickups:
            taker = next((c for c in self.champions() if c.alive and c.distance_to(ent) <= 1.5), None)
            if taker is None:
                keep.append((ent, credits))
                continue
            self.grant(taker, ent, credits, 0.0)
            self.world.remove(ent, f"{taker.name} picks up {ent.name} (0x3)")
        self.pickups = keep

    # ---- announcements and the timeline ------------------------------------------------------------------------------
    def announce(self, kind, text="", source_icon=0, target_icon=0, source_team=-1, target_team=-1):
        self.send(f"billboard type {kind} (0x100002eb)",
                  M.pvp_announcement(kind, text, source_icon, target_icon, source_team, target_team))

    def voice(self, name, source=None, target=None, team=0):
        """An announcer line (0x2039) for a match event named in [ics] announcer_events (ids found by ear with the
        chat command /anunciador); nothing when the name has no id yet."""
        # 2026-10-25 (map-gaps-gotham-divided.md 3 / map-gaps-coast-city.md 2, C: each map has its own announcer set,
        # the ids decoded from its line captions): [ics] announcer_events_by_map[map key] first, then announcer_events
        per_map = ((self.ic.get("announcer_events_by_map") or {}).get(self.map.get("key")) or {})
        ev = per_map[name] if name in per_map else (self.ic.get("announcer_events") or {}).get(name)
        if not ev:
            return
        team = team or self.local_team()
        src, tgt = getattr(source, "eid", 0) or 0, getattr(target, "eid", 0) or 0
        mode = str(self.ic.get("announcer_iids", "champions_real"))
        w = self.world
        # 2026-10-25 19:28 (tester: the kill voice says the same whoever kills): the killer is often a missile or a
        # skill's object, so both IIDs fell back to the local champion; the champion behind each one
        source, target = self._champion_of(source), self._champion_of(target)
        src, tgt = getattr(source, "eid", 0) or 0, getattr(target, "eid", 0) or 0
        real = (mode == "champions_real" and all(getattr(e, "kind", "") == "champion" and
                                                 (e is w.champion or e.eid in w.entities) for e in (source, target)))
        if mode not in ("real", "event") and not real:
            # 2026-10-23 14:13 (tester: the dampener's line came as an empty strip, no voice; in the test, with the
            # champion as source and target, it spoke): the local champion goes as both. 2026-10-25 16:12 (tester's
            # video: an empty strip at every kill): champions are real objects now (bots), so a kill between two of
            # them names them ("champions_real")
            ch = self.world.champion
            src = tgt = ch.eid if ch is not None else 0
        extra = self._announcer_fields(source, target) if real else ()
        self.voice_out(announcer_msgs(self.ic, int(ev), src, tgt, team, team == self.local_team(), extra), event=int(ev))

    # ---- the announcer queue (ca-fog-ring-announcer.md 3) -------------------------------------------------------------
    def voice_out(self, labelled, event=None):
        """Every announcer line / event (0x2039, 0x2001) goes through one queue ([ics] announcer_queue): the server
        sent the wave and jungle lines in the same millisecond and the tester heard them together (handler 0xA77DA0 ->
        0xA596B0 / 0xA0A960; channels 1 / 3, the shared set, and 2, the map's set, play apart; P no client-side wait). One item starts
        only after the previous one's gap ([ics] announcer_queue_gaps by group), highest priority first (kills, then
        structures / objectives, then the timeline's lines); a queued item older than announcer_queue_max_wait s is
        dropped (kills excepted)."""
        if not self.ic.get("announcer_queue", True):
            self.send_many(labelled)
            return
        kills = {int(str(e), 0) for e in (self.ic.get("announcer_queue_kill_events") or ())}
        group = "line" if event is None else ("kill" if int(event) in kills else "event")
        prio = {"kill": 0, "event": 1, "line": 2}[group]
        q = self.__dict__.setdefault("_voice_q", [])
        q.append((prio, next(self._seq), self.t, list(labelled), group))
        self._voice_pump()

    def _voice_timer(self):
        self._voice_wake = False
        self._voice_pump()

    def _voice_pump(self):
        q = self.__dict__.setdefault("_voice_q", [])
        busy = float(self.__dict__.get("_voice_busy", -1e9))
        if q and self.t < busy - 1e-6:
            if not self.__dict__.get("_voice_wake", False):
                self._voice_wake = True
                self.later(busy - self.t, self._voice_timer)
            return
        wait = float(self.ic.get("announcer_queue_max_wait", 8.0) or 0)
        dropped = [it for it in q if wait > 0 and it[4] != "kill" and self.t - it[2] > wait]
        for it in dropped:
            q.remove(it)
            self.log(f"announcer queue: dropped {it[3][0][0] if it[3] else '?'} (waited {self.t - it[2]:.1f} s)")
        if not q:
            return
        q.sort(key=lambda it: (it[0], it[1]))
        prio, _n, at, labelled, group = q.pop(0)
        if self.t - at > 0.05:
            self.log(f"announcer queue: {labelled[0][0] if labelled else '?'} after {self.t - at:.1f} s")
        self.send_many(labelled)
        gaps = self.ic.get("announcer_queue_gaps") or {}
        self._voice_busy = self.t + float(gaps.get(group, gaps.get("default", 3.0)))
        if q and not self.__dict__.get("_voice_wake", False):
            self._voice_wake = True
            self.later(self._voice_busy - self.t, self._voice_timer)

    def _announcer_fields(self, source, target):
        """2026-10-25 (tester: no "<killer> defeated <victim>" banner with both portraits; hud-shop-timeline-kills.md 4,
        C: the client raises that billboard itself while it plays the line, from the 0x2039 table, which the original's
        builder 0x9CE360 filled per entity): class DID, billboard icon (template 0x100001FC), name and the
        announcer-name id (template 0x10000593) of source (0x10000814 / 816 / 819 / 823) and target (813 / 815 / 818 /
        822). [ics] announcer_entity_fields."""
        if not self.ic.get("announcer_entity_fields", True):
            return ()
        from ..wire import KIND_DID, KIND_STRING
        out = []
        for ent, keys in ((source, (0x10000814, 0x10000816, 0x10000819, 0x10000823)),
                          (target, (0x10000813, 0x10000815, 0x10000818, 0x10000822))):
            if ent is None:
                continue
            cls = int(getattr(ent, "class_id", 0) or 0)
            icon = int(self.ud.first(cls, 0x100001FC, 0) or 0)
            voice = int(self.ud.first(cls, 0x10000593, 0) or 0)
            out += [(keys[0], KIND_DID, cls), (keys[2], KIND_STRING, str(getattr(ent, "name", "") or ""))]
            if icon:
                out.append((keys[1], KIND_DID, icon))
            if voice:
                out.append((keys[3], KIND_ENUM, voice))
        return out

    def timeline_event(self, handle, at, severity=2, title="", icon=0, examination_icon=None):
        pic = f" icon {icon:#x} / {examination_icon:#x}" if (icon or examination_icon) else ""
        self.send(f"timeline event {handle} at {at:.0f} s{pic} (0x100002ab)",
                  M.pvp_timeline_event(handle, self.timeline_time(at), self.timeline_now(), title=title, severity=severity,
                                       icon=icon, examination_icon=examination_icon))

    def timeline_banner(self, handle, at, severity=1, title=""):
        self.send(f"timeline banner {handle} (0x10000424)",
                  M.pvp_timeline_banner(handle, self.timeline_time(at), self.timeline_now(), title=title, severity=severity))

    # ---- client notices ----------------------------------------------------------------------------------------------
    def on_notice(self, notice, body=b"", player=None):
        """A client notice of the match HUD; True when handled. body = the notice's payload after its id."""
        if notice == NOTICE_HUD_READY:
            if self.ic.get("match_refresh_flags", True):
                for mu in self.structures:
                    self.units.refresh_flags(mu)
            self.send_clock()
            if self.team_health:
                self.send_team_health(initial=True)
            self.objectives.send_trackers()
            self.score.send(self.t)
            return True
        if notice == NOTICE_TIMELINE_READY:
            self.send_many(M.pvp_timeline_start(self.timeline_now() if self.ic.get('timeline_start_time', True) else None))
            self._timeline_schedule()
            return True
        if notice == NOTICE_TEAM_HEALTH_REQUEST:
            if self.team_health:
                teams = sorted(self.team_health)
                self.send("team health (0x10000134)", M.pvp_team_health(teams, [self.team_health[t] for t in teams]))
            return True
        if notice == NOTICE_SURRENDER:
            yes = bool(body[0]) if body else True
            self.vote_surrender(player, yes)
            return True
        return False

    # ---- surrender (full-match-mechanics.md 12.1; thresholds authored: [ics] match_surrender) -------------------------
    def vote_surrender(self, player=None, yes=True):
        cfg = self.ic.get("match_surrender") or {}
        p = player if isinstance(player, Player) else (self.score.by_agent(self.world.champion) if player is None
                                                       else next((q for q in self.score.players
                                                                  if q.player_iid == player), None))
        if p is None or self.over:
            return
        team = p.team
        s = self.surrender
        if s is None:
            earliest = float(cfg.get("earliest", 0) or 0) or self._surrender_earliest()
            if not yes or self.t < earliest or self.t < self.surrender_after.get(team, -1e9):
                self.log(f"surrender: not now (match time {self.t:.0f} s, earliest {earliest:.0f} s)")
                self.send("surrender: refused (0x10000456)", M.pvp_surrender_end(), team=team)
                return
            s = self.surrender = {"team": team, "votes": {}, "until": self.t + float(cfg.get("vote_seconds", 60.0))}
        if team != s["team"]:
            return
        s["votes"][p.player_iid] = bool(yes)
        self._surrender_status()
        self._surrender_check()

    def _surrender_earliest(self):
        """Template 0x1000021C (600 s on every PvP encounter; G meaning: the earliest surrender)."""
        v = self.ud.first(self.encounter, PROP_SURRENDER_TIME, 0)
        f = struct.unpack("<f", struct.pack("<I", v))[0] if v else 0.0
        return f if 0 < f < 7200 else 600.0

    def _voters(self, team):
        return [p for p in self.score.team(team) if not p.bot]

    def _surrender_status(self):
        s = self.surrender
        voters = self._voters(s["team"])
        votes = [s["votes"][p.player_iid] for p in voters if p.player_iid in s["votes"]]
        total = float((self.ic.get("match_surrender") or {}).get("vote_seconds", 60.0))
        self.send(f"surrender vote team {s['team']}: {sum(votes)} / {len(voters)} (0x10000455)",
                  M.pvp_surrender_status(votes, len(voters), True, max(0.0, s["until"] - self.t), total), team=s["team"])

    def _surrender_check(self, timeout=False):
        s = self.surrender
        cfg = self.ic.get("match_surrender") or {}
        voters = self._voters(s["team"])
        need = max(1, math.ceil(float(cfg.get("fraction", 0.8)) * len(voters)))
        yes = sum(1 for v in s["votes"].values() if v)
        no = sum(1 for v in s["votes"].values() if not v)
        if yes >= need:
            self._surrender_done(True)
        elif no > len(voters) - need or timeout:
            self._surrender_done(False)

    def _surrender_done(self, passed):
        s, self.surrender = self.surrender, None
        self.send("surrender vote over (0x10000456)", M.pvp_surrender_end(), team=s["team"])
        self.log(f"surrender team {s['team']}: {'passed' if passed else 'failed'}")
        if passed:
            self.end(3 - s["team"], "surrender")
        else:
            self.surrender_after[s["team"]] = self.t + float((self.ic.get("match_surrender") or {}).get("cooldown", 180.0))

    def _surrender_tick(self):
        if self.surrender is not None and self.t >= self.surrender["until"]:
            self._surrender_check(timeout=True)

    # ---- the end -----------------------------------------------------------------------------------------------------
    def end(self, winner, why=""):
        if self.over:
            return
        self.over, self.winner = True, winner
        seconds = max(0.0, self.t)
        self.log(f"match over: team {winner} wins ({why}) after {seconds:.0f} s")
        for mu in list(self.units.by_eid.values()):
            mu.target, mu.path = None, []
            if mu.moving:
                self.units.stop(mu, time.time())
        self.bots.freeze()                  # 2026-10-30 tester report 15:30: the bots stop too (match_end_freeze_combat)
        loser = 3 - winner
        # 2026-10-28 15:00 (tester report 2026-10-28 15:00; death-animation.md 10.3: the original's grey ended when the
        # end cinematic started): an opt-in death screen ([ics] death_overlay_scriptlets) is stopped (0x11F), and
        # (2026-10-29, fase3-if review) none starts after this, e.g. from the fall of the death that ended the match
        # ([ics] death_overlay_skip_after_end)
        self.world.match_ended = True
        self.world.death_overlay(self.world.champion, False)
        cin = (self.map.get("end_cinematic") or {}).get(loser)
        if cin and self.ic.get("match_end_cinematic", True) and hasattr(self.session, "play_cinematic"):
            self.session.play_cinematic(cin)
            if self.ic.get("match_end_cinematic_removes_core", True):
                # tester report 2026-10-29 15:30 (the core's central part falls but stays duplicated in its place;
                # throw-padlock-coredeath.md 3, C cinematic data): the cinematic's own PowerCore actor plays the fall;
                # the networked core goes ([ics] match_end_cinematic_removes_core / match_end_core_remove_delay)
                self.later(float(self.ic.get("match_end_core_remove_delay", 0.0) or 0.0),
                           lambda t=loser: self._remove_core(t))
        local = self.local_team()
        played = bool(cin and self.ic.get("match_end_cinematic", True))
        # 2026-10-29 (tester report 23:03: "the enemy core's destruction animation does not finish: when the core falls
        # into the hole VICTORY/DEFEAT appears and the animation is cut; the explosion from the hole never shows, and the
        # announcer doesn't say Victory or Defeat"; traffic 22:51:45.909 cinematic 0x3500003A, 45.910 billboard type 9,
        # 49.877 0x1000000E, which leaves the world at once; turret-heads-coredeath.md 4, C cinematic data): the end
        # cinematic is 11.5 s and its core plays Cinematic_Announcement at frame 225 (7.5 s at 30 fps; GD / CC voice
        # event 29 at the same frame, GH at 210). With an end cinematic the VICTORY / DEFEAT billboard and the victory
        # voice wait for that moment and 0x1000000E for the cinematic's end ([ics] match_end_timing: map -> {"announce",
        # "notice"} s after the core's death; {} = the fase3-io timing: billboard at once, notice match_end_hold s later)
        timing = ((self.ic.get("match_end_timing") or {}).get(self.map.get("key")) or {})             if played and hasattr(self.session, "play_cinematic") else {}
        announce_at = float(timing.get("announce", 0.0) or 0.0)

        def result():
            if self.ic.get("match_stop_billboards", True):
                # 2026-10-25 (sweep-flash-hud.md / sweep-s2c-ui.md, C): StopProcessingNewBillboards before the result,
                # so a late kill billboard cannot cover VICTORY / DEFEAT
                self.send("billboards stop (notice 0x100002bc)", M._notice(0x100002BC, b""))
            self.announce(BILLBOARD_WIN if winner == local else BILLBOARD_LOSS, source_team=winner, target_team=loser)
            if not (played and self.map.get("key") in (self.ic.get("match_victory_voice_skip") or ())):
                # 2026-10-25 (map-runtime-state.md 6, P: Gotham Divided's and Coast City's end cinematics run scripts
                # 0x3400076B / 76C that play event 29 themselves): no second victory voice there
                self.voice("victory", team=winner)
        if announce_at > 0:
            self.later(announce_at, result)
        else:
            result()
        target = self._ui_value(PROP_TARGET_TIME)

        def notify():
            self.send(f"match ended: team {winner} (0x1000000e)", M.match_ended(winner, seconds, local, 0, target))
            if hasattr(self.session, "match_over"):
                # 2026-10-25 (tester's frames of the original end page; hud-shop-timeline-kills.md 6): the 0x2045 rows
                # from the scoreboard and the match stats ([ics] end_stats_from_ledger)
                stats = {"players": self.end_rows()} if self.ic.get("end_stats_from_ledger", True) else None
                try:
                    self.session.match_over(winner, seconds, stats)
                except TypeError:
                    self.session.match_over(winner, seconds)
        hold = float(self.ic.get("match_end_hold", self.ic.get("victory_hold", 4.0)))
        if timing.get("notice"):
            # the cinematic's end (match_end_timing), never before the billboard's own hold
            hold = max(float(timing["notice"]), announce_at + hold)
        self.later(hold, notify)

    def status(self):
        """A summary for logs and tests."""
        return {"t": self.t, "mode": self.mode, "over": self.over, "winner": self.winner,
                "structures": {t: sum(1 for s in self.structures if s.team == t and s.ent.alive) for t in (1, 2)},
                "minions": sum(1 for mu in self.waves.minions if mu.ent.alive), "team_health": dict(self.team_health),
                "owned": {t: self.objectives.owned(t) for t in (1, 2)}}
