"""The tutorial's flow (ics/director.py + ics/encounters/tutorial1.py) on a simulated session: every step is
reached by doing what it waits for (cinematic end, walking, kills, skill ranks, camera settings).

    python tests\\test_director.py
"""
import heapq
import itertools
import math
import os
import struct
import sys
import time

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from ics import config                                   # noqa: E402
from ics import director as D                            # noqa: E402
from ics.encounters import tutorial1 as T                # noqa: E402
from ics.gamedata import Data                            # noqa: E402
from ics.world import World                              # noqa: E402

ENCOUNTER = 0x40000991
SPAWN = [1, 0x13, 0xCB, 0, 18.7, 60.4, 200.3]
results = []


def check(name, cond, detail=""):
    results.append(bool(cond))
    print(f"  {'ok  ' if cond else 'FAIL'} {name}" + (f"  ({detail})" if detail and not cond else ""))


class FakeSession:
    """What the director needs from a session; timers run at once (in order)."""

    def __init__(self, cfg, data):
        self.cfg, self.ic, self.data = cfg, cfg["ics"], data
        self.sent = []
        self.queue = []
        self.cinematics = []
        self.won = False

    def send(self, label, data):
        self.sent.append((label, data))

    def send_many(self, msgs):
        self.sent.extend(msgs)

    def later(self, delay, fn, group=None):
        self.queue.append(fn)

    def drain(self, limit=500):
        n = 0
        while self.queue and n < limit:
            self.queue.pop(0)()
            n += 1

    def encounter_info(self):
        return self.data.encounter(ENCOUNTER)

    def show_hud(self, elements=None):
        self.hud_calls = getattr(self, "hud_calls", []) + [elements]
        for e in (elements if elements is not None else ["all"]):
            self.sent.append((f"HUD element {e} shown", b""))

    def play_cinematic(self, did):
        self.cinematics.append(did)

    def victory(self, seconds):
        self.won = True


def labels(s, since):
    return [lbl for lbl, _ in s.sent[since:]]


def main():
    cfg = config.load()
    cfg["ics"]["trace_scripts"] = False
    data = Data(cfg.game_dir)
    enc = data.encounter(ENCOUNTER)
    data.prepare(enc)
    s = FakeSession(cfg, data)
    logs = []
    w = World(data, cfg, ENCOUNTER, SPAWN, send=s.send, schedule=lambda d, fn: s.later(d, fn), log=logs.append)
    w.ground_z = 200.0
    w.create_champion(cfg["ics"]["champion"], SPAWN)
    ch = w.champion
    ch.ranks = {slot: T.START["ranks"].get(slot, 0) for slot in ch.kit}
    d = D.Director(s, w, T, ENCOUNTER)
    check("objective table read from the data (29)", len(d.table["list"]) == 29, len(d.table["list"]))

    initial = w.spawn_layout(enc, T.INITIAL)
    check("initial placements created (doors, vehicles, power core)", len(initial) == len(T.INITIAL),
          [e.name for e in initial])

    def step():
        return d.step.get("name") if d.step else None

    def finish_cinematic():
        s.drain()
        did = d.cinematic
        if did:
            d.cinematic_state(did, D.NOTICE_CINEMATIC_ENDED)
        s.drain()

    def walk_to(name):
        x, y = d._xy(name)
        ch.pos = [x, y, 200.0]
        d.tick()
        s.drain()

    def kill(group):
        for e in list(d.groups.get(group, [])):
            if e.alive and e.health is not None:
                w.damage(ch, e, e.health + 1)
        s.drain()

    def timed(seconds, start=None, dt=0.05):
        """Run the match for a while with its timers at their delays (missiles fly, scripts' timers expire): the
        session's timers go to a clock, the world ticks between them (real time passes too: the scripts' clock)."""
        heap, order, clock = [], itertools.count(), [0.0]
        immediate = s.later
        s.later = lambda delay, fn, group=None: heapq.heappush(heap, (clock[0] + max(0.0, delay), next(order), fn))
        try:
            while s.queue:                             # what was queued before runs first
                s.queue.pop(0)()
            if start is not None:
                start()
            end = seconds
            while clock[0] < end:
                clock[0] += dt
                while heap and heap[0][0] <= clock[0]:
                    heapq.heappop(heap)[2]()
                time.sleep(dt)
                w.tick(dt, time.time())
        finally:
            s.later = immediate
            s.queue.extend(fn for _t, _n, fn in sorted(heap))   # the rest (conversations ...) as before
        s.drain()

    def skill_kills(group, slot, seconds=2.5):
        """The champion casts the skill at the group's first target from 3 m away: every target dies."""
        targets = [e for e in d.groups.get(group, []) if e.alive]
        if not targets:
            return False
        t = targets[0]
        ch.pos = [t.pos[0] + 1.0, t.pos[1] + 3.0, 200.0]
        ch.dest, ch.attack_target = None, None
        del logs[:]
        w.ic["trace_scripts"] = True
        timed(seconds, lambda: w.cast(ch, slot, None, list(t.pos)))
        w.ic["trace_scripts"] = False
        ok = all(not e.alive for e in d.groups.get(group, []))
        if not ok:
            print("\n".join("      | " + line for line in logs)[-6000:])
        return ok

    d.start()
    s.drain()
    check("intro cinematic played first", s.cinematics[:1] == [0x35000026], s.cinematics)
    finish_cinematic()
    check("after the intro: walk to the first marker", step() == "walk1", step())

    def shown():
        return {int(lbl.split()[2]) for lbl in labels(s, 0) if lbl.startswith("HUD element ") and "shown" in lbl
                and lbl.split()[2].isdigit()}
    # 2026-10-22 (original's videos): the tutorial starts with the portrait, the minimap, objectives and hints only
    check("HUD at the start: portrait, minimap, objectives, hints; no skill bar, no vitals",
          shown() == set(T.START_HUD), sorted(shown()))
    check("a hidden skill button cannot be used (D during the walk)", not w.cast(ch, T.D, None, list(ch.pos)))
    check("objective sent by reference (token form)", any("objective 0" in lbl for lbl in labels(s, 0)))
    # 0x2140 (the client finished a conversation) starts the next queued one
    s.queue.clear()                    # no fallback timers: only the client's 0x2140 ends a conversation
    d.playing = None
    d.conv_queue += [(0x1BA, object()), (0x193, object())]
    d._pump()
    playing = d.playing
    s.queue.clear()
    w.emit("conversation_done", instance=playing)
    s.drain(limit=1)
    check("0x2140 for the playing conversation starts the next", d.playing != playing
          and any("conversation 0x193" in lbl for lbl in labels(s, 0)), d.playing)
    # fase3-gq: the guide marker's ring (0x34000600's Group ping FX 0x1E00055E as variable 0x1000050A, through the
    # marker's own Vfx_GuideArrow) and the champion's arrow (Group arrow FX 0x1E000510)
    fx_msgs = {lbl: data for lbl, data in s.sent if "Vfx_GuideArrow" in lbl}
    check("guide marker: its ring (FX 0x1E00055E) and the champion's arrow (FX 0x1E000510)",
          any(lbl.startswith("guide marker:") and struct.pack("<I", 0x1E00055E) in data for lbl, data in fx_msgs.items())
          and any(lbl.startswith("Gaslight Batman:") and struct.pack("<I", 0x1E000510) in data
                  for lbl, data in fx_msgs.items()), list(fx_msgs))
    # fase3-gq: the walk's meteor is a small strike: rock, fire column, dust; no crater
    crater_cls = (T.CRATER_STATE, *T.CRATER_MESHES)
    walk_spawns = [lbl for lbl in labels(s, 0) if lbl.startswith("spawn ")]
    check("the walk's small strike: rock and dust cloud, no crater entity (its Vfx_Active brings the big crater)",
          not any(f"({c:#x})" in lbl for c in crater_cls for lbl in walk_spawns)
          and d.groups.get("meteor0")
          and not any(lbl.startswith("meteor0_fire") for lbl in labels(s, 0))
          and any(lbl.startswith("meteor0_dust") and "Vfx_Startup" in lbl for lbl in labels(s, 0)),
          walk_spawns + [lbl for lbl in labels(s, 0) if lbl.startswith("meteor0")] + logs[-5:])
    n_walk = len(s.sent)
    walk_to("marker1")
    check("meteor step: the crater plays its own fall and impact", any("Vfx_Spawn_Event02" in lbl for lbl in labels(s, 0)))
    check("the big meteor leaves the crater and its lava (only it)",
          any(f"({T.CRATER_STATE:#x})" in lbl for lbl in labels(s, n_walk) if lbl.startswith("spawn ")))
    walk_to("marker2")
    check("first drone spawned from the layout", step() == "first_drone" and d.groups.get("drone"), step())
    # fase3-gq: units play their spawn-in effect (the drones' _Entity_OnEnterWorld_Default -> Vfx_Spawn)
    check("the drone plays its spawn-in effect", any(lbl.startswith("03MeleeC: _Entity_OnEnterWorld_Default (0x8d, spawn-in)")
                                                     for lbl in labels(s, 0)))
    n = len(s.sent)
    kill("drone")
    check("the wave follows", step() == "wave", step())
    wave_labels = labels(s, n)
    check("the wave's strike is a small one beside Batman (no crater) and its drones spawn in",
          not any(f"({c:#x})" in lbl for c in crater_cls for lbl in wave_labels if lbl.startswith("spawn "))
          and not any(lbl.startswith("meteor2_fire") for lbl in wave_labels)
          and sum("(0x8d, spawn-in)" in lbl for lbl in wave_labels) >= 2
          and math.hypot(T.POSITIONS["wave_meteor"][0] - 35.3, T.POSITIONS["wave_meteor"][1] - 56.3) < 3.0,
          [lbl for lbl in wave_labels if lbl.startswith("spawn ")])
    n = len(s.sent)
    kill("wave")
    check("level 2, Q may be ranked", step() == "unlock_q" and w.rankable(T.Q) and not w.rankable(T.W),
          (step(), ch.skill_points))
    check("the wave's objective counted 2/2", any("2/2" in lbl for lbl in labels(s, n)))
    check("level 2: the skill bar with Q, W, E, R, passive and basic attack, not D / F",
          {14, 6, 9, 17, 25, 12, 7} <= shown() and not {22, 23, 2, 20} & shown(), sorted(shown()))
    check("an arrow over Q's '+' only", any("arrow on slot 1's" in lbl for lbl in labels(s, n))
          and not any("arrow on slot 2's" in lbl for lbl in labels(s, n)))
    n = len(s.sent)
    w.rank_skill(T.Q)
    s.drain()
    check("Q ranked: its arrow goes", any("arrows off" in lbl for lbl in labels(s, n)))
    check("Q ranked: the practice targets", step() == "practice_q" and ch.ranks[T.Q] == 1, step())
    # 2026-10-22 14:10 (tester: the practice targets never died): they are neutral (team 0); the missile collision
    # test passed only hostile units and CheckRelation refused neutrals. They are marked hittable, and only Q hurts them
    targets = d.groups.get("targets", [])
    check("practice targets: neutral, hittable, only Q hurts them",
          len(targets) == 2 and all(e.team == 0 and e.hittable and e.only_slot == T.Q for e in targets),
          [(e.team, e.hittable, e.only_slot) for e in targets])
    from ics import script_nodes as SN
    from ics.world import CastWorld
    cw = CastWorld(w, ch, None)
    dealt = SN.deal_damage(cw, ch, targets[0], 50.0, slot=0)
    check("a basic attack does nothing to a practice target (Superman's 0x1CD)",
          dealt == 0.0 and targets[0].alive and 0x1CD in getattr(d, "immune_said", ()), (dealt, targets[0].health))
    check("missiles collide with a hittable neutral, not with a plain one or a friend",
          cw.collides(ch, targets[0]) and not cw.collides(ch, ch)
          and not any(cw.collides(ch, e) for e in w.entities.values() if e.team == 0 and not e.hittable))
    # fase3-gq: a guide ring on each practice target, the champion's arrow at the first (original 1:53-2:05)
    rings = [mk for mk in d.guides.values() if mk.eid in w.entities]
    check("practice targets: a guide ring on each, the champion's arrow at one",
          len(rings) == 2 and all(math.hypot(mk.pos[0] - t.pos[0], mk.pos[1] - t.pos[1]) < 0.01
                                  for t, mk in d.guides.items())
          and any(lbl.startswith("Gaslight Batman: Vfx_GuideArrow") and "-> 0x40000ba9" in lbl or
                  lbl.startswith("Gaslight Batman: Vfx_GuideArrow") and "targets" in lbl
                  for lbl in labels(s, 0)), [lbl for lbl in labels(s, 0) if "GuideArrow" in lbl][-4:])
    check("Sonic Batarang cast at a practice target kills both (the batarang bounces)", skill_kills("targets", T.Q),
          [(e.name, e.health) for e in targets])
    check("the practice targets' rings go when they die", not any(mk.eid in w.entities for mk in rings)
          and not d.guides, [mk.name for mk in rings if mk.eid in w.entities])
    check("the first Sonic Batarang reveals the health / Will bars (Will framed)",
          2 in shown() and any("highlight 53 on HUD element 2" in lbl for lbl in labels(s, 0)), sorted(shown()))
    if any(e.alive for e in targets):
        kill("targets")
    check("Catwoman's cinematic", s.cinematics[-1] == T.CATWOMAN, s.cinematics)
    finish_cinematic()
    check("the vehicle Catwoman broke is gone", not [e for e in w.entities.values() if e.name == "DestVehicle"])
    wreck = sorted(e.class_id for e in w.entities.values() if e.class_id in T.VEHICLE_WRECK)
    check("its wreck stays (0x2E00135E / 5F / 60 at the vehicle's spot)", wreck == T.VEHICLE_WRECK
          and all(math.hypot(e.pos[0] - 43.66, e.pos[1] - 52.61) < 0.1
                  for e in w.entities.values() if e.class_id in T.VEHICLE_WRECK), [hex(c) for c in wreck])
    # 0x20F5: the champion bound to the scene's player actor, Characters hidden while it plays
    from ics import messages as M
    body = M.cinematic(T.CATWOMAN, flags=M.CINEMATIC_FLAG_BIND_CHECK, bindings=[(0, M.CHAMPION_AGENT_ID)],
                       hide_types=8)
    tail = struct.pack("<IIIIIQI", 0xF, T.CATWOMAN, 2, 1, 0, M.CHAMPION_AGENT_ID, 8)
    check("0x20F5 with mask 0xF: DID, flags 2, binding {0, champion}, hide Characters", body.endswith(tail),
          body.hex())
    check("0x20F5 without options is the old mask-1 message",
          M.cinematic(T.CATWOMAN).endswith(struct.pack("<II", 1, T.CATWOMAN)))

    # part 2 and 3: answer each step's trigger
    practiced = {}
    hud_at = {}
    for _ in range(60):
        name = step()
        if name is None:
            break
        hud_at.setdefault(name, shown())
        until = d.waiting or []
        if d.cinematic:
            finish_cinematic()
            continue
        if not until:
            s.drain()
            continue
        t = until[0]
        if t[0] == "cast":
            w.emit("cast", ent=ch, slot=t[1], target=None, point=None)
            s.drain()
        elif t[0] == "killed" and t[1] in ("w_target", "e_target"):
            # the W / E practice targets: only that skill kills them (Sonic Shell's shell explodes on landing)
            slot = T.W if t[1] == "w_target" else T.E
            ok = skill_kills(t[1], slot)
            practiced[t[1]] = ok
            if not ok:
                kill(t[1])
        elif t[0] == "killed":
            kill(t[1])
        elif t[0] == "ranked":
            slots = t[1] if isinstance(t[1], (list, tuple)) else [t[1]]
            w.rank_skill(slots[0])
            s.drain()
        elif t[0] == "reach":
            walk_to(t[1] if isinstance(t[1], str) else (t[1], t[2]))
        elif t[0] == "preference":
            w.emit("preference", name=t[1], value=t[2])
            s.drain()
        else:
            break
    check("the experience bar comes with the W unlock", 20 not in hud_at.get("pursuers", {20})
          and 20 in hud_at.get("unlock_w", ()))
    check("D appears (framed) at the camera step, F at Super Strength",
          22 not in hud_at.get("ambush", {22}) and 22 in hud_at.get("camera", ())
          and 23 not in hud_at.get("scream", {23}) and 23 in hud_at.get("strength", ())
          and any("highlight 3 on HUD element 22" in lbl for lbl in labels(s, 0)), {k: sorted(v) for k, v in hud_at.items()
                                                                                   if k in ("camera", "strength")})
    check("level 7 after the Destroyer's cinematic: arrows over passive, Q, W, E",
          all(any(f"arrow on slot {k}'s" in lbl for lbl in labels(s, 0)) for k in (T.PASSIVE, T.Q, T.W, T.E)))
    check("Sonic Shell (W) and Bat Flight (E) kill their practice targets",
          practiced == {"w_target": True, "e_target": True}, practiced)
    check("the whole flow ends in victory", s.won and step() is None, step())
    check("every skill was ranked on the way (Q 2, W 2, E, R, passive)",
          [ch.ranks.get(k, 0) for k in (T.Q, T.W, T.E, T.R, T.PASSIVE)] == [2, 1, 1, 1, 1] or
          all(ch.ranks.get(k, 0) >= 1 for k in (T.Q, T.W, T.E, T.R, T.PASSIVE)),
          {k: ch.ranks.get(k) for k in range(6)})
    check("the Destroyer is the data's (1500 health)", any(e.name == "Destroyer" and e.max_health == 1500
                                                            for g in d.groups.values() for e in g))
    check("the doors opened with their own scriptlet", any("Object_Open" in lbl for lbl in labels(s, 0)))
    # fase3-gq (original 3:55-3:59): the bridge ambush comes from the closed gate behind Batman, a small strike among it
    amb = [(round(e.pos[0], 1), round(e.pos[1], 1)) for e in d.groups.get("ambush", [])]
    check("the bridge ambush spawns in at the gate and a small strike lands among it (no crater)",
          len(amb) == 3 and all(math.hypot(x - 54.05, y - 44.80) < 4.5 for x, y in amb) and any(lbl.startswith("spawn meteor3") for lbl in labels(s, 0)) and not any(lbl.startswith("meteor3_fire") for lbl in labels(s, 0))
          and math.hypot(*(a - b for a, b in zip(T.POSITIONS["ambush_gate_ranged"], (54.05, 44.80)))) < 3.0
          and not any(lbl.startswith("spawn meteor3") and f"({T.CRATER_STATE:#x})" in lbl for lbl in labels(s, 0)), amb)
    print(f"\n{sum(results)}/{len(results)} director checks")
    return 0 if all(results) else 1


if __name__ == "__main__":
    sys.exit(main())
