"""Atomic Green Lantern's R Meltdown against a standing, walking or stacked enemy (python tests/test_meltdown.py; no ports).

docs/re-notes/meltdown-moving-target.md (tester report 2026-10-28 15:00: a Meltdown hit must slow the enemy and keep
hitting it while it moves). The real match world as tools/champion_check.py runs it (tests/test_match.py's FakeSession +
World + pvp.start_match on a virtual clock, time.time = the session's clock): AGL 0x4000047D, level 6, casts Meltdown
(slot 4, script 0x340002B4) at a bot Atomic Wonder Woman 0x400003EC. A pulse is an ApplyDamage(SELF) of the status
script 0x340002BF (status 0x480007AF).
"""
import math
import os
import sys
import time

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
sys.path.insert(0, os.path.join(ROOT, "tests"))

from ics import config                                   # noqa: E402
from ics import script_runtime as R                       # noqa: E402
from ics import world as W                                # noqa: E402
from ics.gamedata import Data                            # noqa: E402
import test_match as T                                   # noqa: E402

ENCOUNTER = 0x40000C82                                   # Crime Alley
AGL, AWW = 0x4000047D, 0x400003EC
MELTDOWN, MISSILE, STATUS_SCRIPT = 0x480007AF, 0x40000484, 0x340002BF
RAD, SICK, SLOW = 0x480007B6, 0x480007BC, 0x48000294
STEP = 0.05
CHECKS = []
_real_time = time.time
_clock = {"s": None}


def check(name, ok, detail=""):
    CHECKS.append((name, bool(ok)))
    print(("ok   " if ok else "FAIL ") + name + (f"  ({detail})" if detail and not ok else ""))


def _virtual_time():
    s = _clock["s"]
    return s.clock if s is not None else _real_time()


def setup(cfg, data):
    """The server's runtime settings (ics/server.py), as tools/champion_check.py sets them."""
    data.class_scripts = {int(str(k), 0): [int(str(x), 0) for x in v]
                          for k, v in (cfg["ics"].get("spawned_class_scripts") or {}).items()}
    R.SCRIPT_RESOLVER = data.entity_scripts
    R.STATUS_RESOLVER, R.STACKS_RESOLVER = data.status_script, data.status_max_stacks
    R.STATUS_STACK_MODEL = bool(cfg["ics"].get("status_stack_model", True))
    R.POLL_ONCE_PER_TICK = bool(cfg["ics"].get("script_poll_once_per_tick", True))
    R.LOCAL_Y_FORWARD = bool(cfg["ics"].get("local_y_forward", True))
    R.RESET_LOCALS = bool(cfg["ics"].get("reset_state_locals", True))
    R.EXIT_REENTRY_GUARD = bool(cfg["ics"].get("exit_chain_reentry_guard", True))
    R.REAIM_FROM_CURRENT = R.STATUS_ACTS_FOR_SOURCE = R.EVENT_LOOP_PER_TARGET = True     # the defaults under test
    if cfg["ics"].get("graph_cast_timing", True):
        R.GRAPH_EXIT_FALLBACK = float(cfg["ics"].get("graph_exit_fallback", 3.0) or 3.0)
        R.load_graph_hooks(os.path.join(ROOT, "data", "skill_hooks.tsv"))
    R.GRAPH_RUNTIME = bool(cfg["ics"].get("graph_runtime", True))
    R.ACCEPT_FILTER = bool(cfg["ics"].get("script_accept_filter", True))
    R.GRAPH_START_GRACE = float(cfg["ics"].get("graph_start_grace", 0.15) or 0.0)
    R.GRAPH_COSMETIC_TAIL = bool(cfg["ics"].get("graph_cosmetic_tail", True))
    R.GRAPH_MISSILE_RELEASE = float(cfg["ics"].get("graph_missile_release", 0.5) or 0.0)
    from ics import graph as GR
    GR.CLIP_SECONDS = float(cfg["ics"].get("graph_clip_seconds", 0.5) or 0.5)
    GR.COSMETIC_HOLD = float(cfg["ics"].get("graph_cosmetic_hold", 0.8) or 0.0)
    GR.STATE_TIMEOUT = float(cfg["ics"].get("graph_state_timeout", 5.0) or 0.0)
    GR.SELF_DEBOUNCE = float(cfg["ics"].get("graph_self_debounce", 0.05) or 0.0)


class Probe:
    """What one scene did: pulses (ApplyDamage(SELF) of 0x340002BF), the targets of every status pulse damage, World.damage
    calls, statuses applied, missiles launched, the bot's speed while it is slowed and its DoT sources."""

    def __init__(self):
        self.t0 = None
        self.pulses = []                 # (t, owner, acting entity, owner position)
        self.status_hits = []            # (t, target) of every ApplyDamage of 0x340002BF
        self.damage = []                 # (t, source, target, amount)
        self.statuses = []               # (t, status, source, target, EffectDuration)
        self.missiles = []               # (t, owner, class, target, missile)
        self.vot_sources = set()
        self.slowed_speeds = []
        self.timed = []                  # (t since the cast, label) of every message sent
        self.killed_at = None            # when kill_target_after killed the cast's target

    def t(self):
        return round(_clock["s"].clock - self.t0, 3) if self.t0 is not None else -1.0


PROBE = {"p": None}


def install_probes():
    orig_damage_node = R.HANDLERS[0x1000001D]

    def apply_damage(inst, n, ops, chain):
        p = PROBE["p"]
        if p is not None and getattr(inst.script, "did", 0) == STATUS_SCRIPT:
            target = inst.owner if len(ops) > 1 and ops[1].is_self() else inst.get(ops[1]) if len(ops) > 1 else None
            if len(ops) > 1 and ops[1].is_self():
                p.pulses.append((p.t(), inst.owner, R.acting_entity(inst), tuple(inst.world.position(inst.owner))))
            p.status_hits.append((p.t(), target))
        return orig_damage_node(inst, n, ops, chain)
    R.HANDLERS[0x1000001D] = apply_damage

    orig_apply = R.apply_status

    def apply_status(world, source, target, status, params, skill_world=None, count=None):
        p = PROBE["p"]
        if p is not None and status in (MELTDOWN, RAD, SICK, SLOW):
            p.statuses.append((p.t(), status, source, target, round(float(R.num(params.get("EffectDuration", 0))), 2)))
        return orig_apply(world, source, target, status, params, skill_world, count)
    R.apply_status = apply_status

    orig_launch = W.CastWorld.launch_missile

    def launch(self, owner, cls, target, speed, rng, scripts, **extra):
        m = orig_launch(self, owner, cls, target, speed, rng, scripts, **extra)
        p = PROBE["p"]
        if p is not None:
            p.missiles.append((p.t(), self._ent(owner), cls, self._ent(target), m))
        return m
    W.CastWorld.launch_missile = launch
    return orig_damage_node, orig_apply, orig_launch


def scene(cfg, data, dist=4.5, stacks=0, walk=False, units=0, unit_dist=2.0, ally_unit=False, kill_after=0,
          seconds=9.0, slot=4, dashed=False, at_unit=False, kill_target_after=0, target_health=None):
    """One cast of Meltdown at the bot. stacks: Rad stacks put on the bot first; walk: the bot walks 12 m away from +0.3 s
    and back from +3.4 s; units: bot-team units around the bot (unit_dist m away); ally_unit: an AGL-team unit 1.5 m from
    the bot; kill_after: AGL counts as dead after that many pulses; kill_target_after: the cast's target is killed by AGL
    (World.damage, its death events) after that many pulses on it; target_health: the target's health at the cast (a low
    one: the first pulse itself kills it)."""
    p = Probe()
    logs = []
    s = T.FakeSession()
    _clock["s"] = s
    plain_send = s.send

    def timed_send(label, data):
        p.timed.append((s.clock - (p.t0 or s.clock), label or ""))
        plain_send(label, data)
    s.send = timed_send
    spawn = T.pvp.spawn_point(ENCOUNTER, 1)
    w = T.World(data, cfg, ENCOUNTER, spawn, send=s.send, schedule=s.schedule, log=logs.append)
    nav = T.pvp.navgrid(data, ENCOUNTER, spawn[1:3])
    w.nav = nav.copy() if nav else None
    w.ground_z = spawn[6]
    ch = w.create_champion(AGL, spawn)
    w.in_world = True
    m = T.pvp.start_match(w, s, ENCOUNTER)
    T.run(s, m, 3.0)
    ch.level = 6
    for sl in range(0, 5):
        if sl in ch.kit:
            ch.ranks[sl] = max(1, ch.ranks.get(sl, 0))
    w.recompute_stats(ch, refill=True)
    bot = w.create_bot_champion(AWW, 2 if ch.team != 2 else 1, "enemy bot", 0, pos=[ch.pos[0] + dist, ch.pos[1], ch.pos[2]])
    ch.heading = 0.0
    base_speed = bot.move_speed
    if not walk:
        bot.move_speed = 0.0
    others = []
    for i in range(units):
        a = math.pi / 2 + i * 2 * math.pi / max(units, 1)
        u = W.Entity(w.new_id(), f"bot-team unit {i}", bot.class_id,
                     [bot.pos[0] + unit_dist * math.cos(a), bot.pos[1] + unit_dist * math.sin(a), bot.pos[2]],
                     team=bot.team, kind="unit")
        u.health = u.max_health = 1000.0
        w.add(u)
        others.append(u)
    ally = None
    if ally_unit:
        ally = W.Entity(w.new_id(), "AGL-team unit", ch.class_id, [bot.pos[0], bot.pos[1] + 1.5, bot.pos[2]],
                        team=ch.team, kind="unit")
        ally.health = ally.max_health = 1000.0
        w.add(ally)

    def tick(n):
        for _ in range(n):
            s.clock += STEP
            w.tick(STEP, s.clock)
            s.run_due()
            bot.attack_target = None                     # the bot does not fight back (only its walk moves it)
            for v in list(w.combat.of(bot).vots.values()):
                p.vot_sources.add(v.get("source"))
            if R.statuses_on(w.combat.world, bot).get(SLOW):
                p.slowed_speeds.append(bot.move_speed)
            if kill_after and len(p.pulses) >= kill_after and ch.alive:
                ch.alive = False                         # AGL counts as dead (Entity kept, as World.damage does)
            if (kill_target_after and aim.alive and aim.health
                    and sum(1 for _t, o, _a, _pos in p.pulses if o is aim) >= kill_target_after):
                p.killed_at = p.t()
                w.damage(ch, aim, aim.health + 1.0)      # the target dies mid-Meltdown

    aim = others[0] if at_unit and others else bot
    if target_health is not None:
        aim.health = float(target_health)
    tick(int(0.5 / STEP))
    for _ in range(stacks):
        R.apply_status(w.combat.world, ch, bot, RAD, {"EffectDuration": 6.0})
    orig_damage = w.damage

    def damage(source, target, amount):
        p.damage.append((p.t(), source, target, float(amount or 0)))
        return orig_damage(source, target, amount)
    w.damage = damage
    PROBE["p"] = p
    mark, sent0 = len(logs), len(s.sent)
    p.t0 = s.clock
    if dashed:
        # Robin's Vault Kick 0x3400030D: EnableCollision at the dash, DisableCollision at its end, on the bot itself
        # (agl-grab-arm.md 2): the bot must stay hittable by missiles afterwards
        class _Run:
            guid = 987654

            def source(self):
                return self.owner
        run_ = _Run()
        run_.owner, run_.world = bot, w.combat.world
        R.HANDLERS[0x10000070](run_, None, [], None)
        R.HANDLERS[0x1000006F](run_, None, [], None)
    ok = w.cast(ch, slot, aim if slot != 1 else None, tuple(aim.pos))
    if walk:
        w.walk_to(bot, [bot.pos[0] + 12.0, bot.pos[1], bot.pos[2]])
        s.schedule(3.4, lambda: w.walk_to(bot, [bot.pos[0] - 12.0, bot.pos[1], bot.pos[2]]))
    tick(int(seconds / STEP))
    PROBE["p"] = None
    w.damage = orig_damage
    return {"p": p, "ok": ok, "ch": ch, "bot": bot, "units": others, "ally": ally, "w": w, "s": s,
            "logs": logs[mark:], "labels": s.labels(sent0), "base_speed": base_speed}


# 2026-10-29 ([ics] status_timer_first_wait, agl-qer-lift.md 3): the first pulse waits PulseDuration, so EffectDuration /
# PulseDuration = 5 pulses (as the original video: 62-66 s); 6 with the old "unset timer = expired" first pulse
PULSES = 5 if 0x340002BF in R.STATUS_TIMER_FIRST_WAIT else 6


def first(seq, pred, default=None):
    return next((x for x in seq if pred(x)), default)


def standing(cfg, data):
    print("Meltdown at a still bot 4.5 m away (meltdown-moving-target.md 6.8 case 1)")
    r = scene(cfg, data)
    p, ch, bot = r["p"], r["ch"], r["bot"]
    check("cast accepted", r["ok"])
    hit = first(p.statuses, lambda e: e[1] == MELTDOWN and e[3] is bot)
    check("the orb lands within 1.5 s (missile_reaim_from_current; was 4.9 s)", hit is not None and hit[0] <= 1.5, hit)
    check(f"{PULSES} pulses on the bot", len(p.pulses) == PULSES and all(o is bot for _t, o, _a, _pos in p.pulses),
          [(t, getattr(o, "name", o)) for t, o, _a, _pos in p.pulses])
    check("every pulse acts for AGL (status_acts_for_source)", all(a is ch for _t, _o, a, _pos in p.pulses))
    check("no damage credited to the bot itself", not any(src is bot and tgt is bot for _t, src, tgt, _a in p.damage))
    check("the pulses never hit AGL's side", not any(getattr(tgt, "team", None) == ch.team for _t, tgt in p.status_hits))
    check("Rad stacks 0x480007B6 applied by AGL (status_skill_hit_event)",
          any(st == RAD and src is ch and tgt is bot for _t, st, src, tgt, _d in p.statuses))
    sick = first(p.statuses, lambda e: e[1] == SICK and e[3] is bot)
    slow = first(p.statuses, lambda e: e[1] == SLOW and e[3] is bot)
    fifth = p.pulses[4][0] if len(p.pulses) >= 5 else 99.0
    check("Radiation Sickness 0x480007BC and its slow 0x48000294 by AGL before the 5th pulse",
          sick is not None and slow is not None and sick[2] is ch and slow[2] is ch and sick[0] < fifth,
          (sick and sick[:3], slow and slow[:3], fifth))
    check("the slow is sent (0x20F0 modifier 0x100005e4 op 10 = -0.4)",
          any("modifier 0x100005e4 op 10 = -0.4" in lbl and "enemy bot" in lbl for lbl in r["labels"]))
    check("Radiation Sickness' DoT is AGL's", p.vot_sources == {ch}, p.vot_sources)
    check("AGL loses no health to Meltdown", ch.health == ch.max_health, (ch.health, ch.max_health))
    spacing = [round(b[0] - a[0], 2) for a, b in zip(p.pulses, p.pulses[1:])]
    check("pulses about 1 s apart (PulseDuration 1 s on the 0.1 s update grid)", all(0.9 <= d <= 1.25 for d in spacing),
          spacing)


def walking(cfg, data):
    print("Meltdown at a bot that walks away and back (case 2)")
    r = scene(cfg, data, walk=True)
    p, ch, bot = r["p"], r["ch"], r["bot"]
    hit = first(p.statuses, lambda e: e[1] == MELTDOWN and e[3] is bot)
    check("the orb lands on the walking bot within 2.5 s (was never)", hit is not None and hit[0] <= 2.5, hit)
    check(f"{PULSES} pulses on the walking bot", len(p.pulses) == PULSES and all(o is bot for _t, o, _a, _pos in p.pulses),
          len(p.pulses))
    pos = [q for _t, _o, _a, q in p.pulses]
    spread = max((math.dist(a[:2], b[:2]) for a in pos for b in pos), default=0.0)
    check("the pulses follow the bot (centres more than 1 m apart)", spread > 1.0, round(spread, 2))
    check("every pulse acts for AGL", all(a is ch for _t, _o, a, _pos in p.pulses))
    want = r["base_speed"] * 0.6
    check("the walking bot is slowed by 40 % while sick",
          bool(p.slowed_speeds) and abs(min(p.slowed_speeds) - want) < 0.05,
          (r["base_speed"], min(p.slowed_speeds) if p.slowed_speeds else None))


def stacked(cfg, data):
    print("The tester's case: the bot already has 3 Rad stacks, nobody else near (case 3)")
    r = scene(cfg, data, dist=1.5, stacks=3)
    p, ch, bot = r["p"], r["ch"], r["bot"]
    check(f"{PULSES} pulses on the bot (no jump: no other enemy near)", len(p.pulses) == PULSES
          and all(o is bot for _t, o, _a, _pos in p.pulses), len(p.pulses))
    check("no jump missile (one 0x40000484)", sum(1 for e in p.missiles if e[2] == MISSILE) == 1,
          [(t, getattr(o, "name", o)) for t, o, c, _tg, _m in p.missiles if c == MISSILE])
    check("AGL is never hit by the pulses (was 21.5 at the first one)", not any(tgt is ch for _t, tgt in p.status_hits))
    sick = first(p.statuses, lambda e: e[1] == SICK and e[3] is bot)
    second = p.pulses[1][0] if len(p.pulses) >= 2 else 99.0
    check("slowed after the first pulse (4th stack -> Radiation Sickness)", sick is not None
          and p.pulses[0][0] <= sick[0] < second, (sick and sick[0], [x[0] for x in p.pulses[:2]]))


def jump(cfg, data):
    print("3 Rad stacks and a bot-team unit 2 m away: the jump (case 4)")
    r = scene(cfg, data, dist=1.5, stacks=3, units=1)
    p, ch, bot = r["p"], r["ch"], r["bot"]
    unit = r["units"][0]
    jumps = [e for e in p.missiles if e[2] == MISSILE][1:]
    j = jumps[0] if jumps else None
    check("a jump missile at the first pulse", j is not None and p.pulses and abs(j[0] - p.pulses[0][0]) < 0.11,
          (j and j[0], p.pulses and p.pulses[0][0]))
    if j is None:
        return
    mis = j[4]
    check("the jump missile is AGL's (shooter, 0x100004E2)", j[1] is ch and getattr(mis, "owner", None) is ch and any(
        k == 0x100004E2 and v == ch.eid for k, _kind, v in getattr(getattr(mis, "entity", None), "extra_props", [])),
        getattr(j[1], "name", j[1]))
    start = getattr(mis, "origin", None)
    check("it starts at the bot, aimed at the unit", start is bot and j[3] is unit, (getattr(start, "name", start),
                                                                                     getattr(j[3], "name", j[3])))
    on_unit = first(p.statuses, lambda e: e[1] == MELTDOWN and e[3] is unit)
    check("the unit gets Meltdown for the 5 pulses left (EffectDuration 5 s)", on_unit is not None and on_unit[4] == 5.0,
          on_unit)
    check(f"{PULSES} pulses in all", len(p.pulses) == PULSES, [(t, getattr(o, "name", o)) for t, o, _a, _pos in p.pulses])


def crowd(cfg, data):
    print("5 bot-team units within 2 m: every one gets its stack (case 5)")
    r = scene(cfg, data, dist=4.5, units=5, unit_dist=1.6)
    p, ch, bot = r["p"], r["ch"], r["bot"]
    t1 = p.pulses[0][0] if p.pulses else 99.0
    stacked_units = {id(tgt) for t, st, src, tgt, _d in p.statuses if st == RAD and src is ch and t1 <= t <= t1 + 0.3}
    check("pulse 1 stacks every unit hit (event_loop_per_target)", all(id(u) in stacked_units for u in r["units"]),
          f"{len([u for u in r['units'] if id(u) in stacked_units])}/{len(r['units'])}")
    check("no event loop cut", not any("loop cut" in ln for ln in r["logs"]),
          [ln[:120] for ln in r["logs"] if "loop cut" in ln][:2])


def impact_and_target(cfg, data):
    """2026-10-30 tester report 15:30 (docs/re-notes/agl-r-impact-q-e.md 3): the orb shows from its creation and stays
    0.5 s after its impact (its script's DestroyEntity(SELF, 0.5 s)); R is refused on a non-champion target."""
    print("Meltdown's orb: effect at once, impact kept 0.5 s; R on a minion refused (case 7)")
    r = scene(cfg, data, dist=4.5, seconds=3.0)
    t = r["p"].timed
    made = first(t, lambda e: "missile 0x40000484 created" in e[1])
    act = first(t, lambda e: "missile 0x40000484: Vfx_Active" in e[1])
    hit = first(t, lambda e: "missile 0x40000484: scriptlet 0x10000016" in e[1])
    gone = first(t, lambda e: "missile 0x40000484 gone" in e[1])
    check("the orb's Vfx_Active goes within 0.06 s of its creation (spawned_effect_delays_by_class)",
          made is not None and act is not None and act[0] - made[0] <= 0.06, (made, act))
    check("the orb stays 0.4-0.7 s after its impact (missile_destroy_delay_scripts; was 0.02 s)",
          hit is not None and gone is not None and 0.4 <= gone[0] - hit[0] <= 0.7, (hit, gone))
    # 2026-10-30 (tester, later): Meltdown may target minions (default cast_target_kind_mask {}); the mask still works
    r = scene(cfg, data, dist=4.5, units=1, unit_dist=1.5, at_unit=True, seconds=1.5)
    check("R at a minion is accepted by default (cast_target_kind_mask {})", r["ok"]
          and any(e[2] == MISSILE for e in r["p"].missiles), r["ok"])
    cfg["ics"]["cast_target_kind_mask"] = {"0x480007A2:4": 8}
    r = scene(cfg, data, dist=4.5, units=1, unit_dist=1.5, at_unit=True, seconds=1.5)
    cfg["ics"]["cast_target_kind_mask"] = {}
    check("with cast_target_kind_mask {R: 8} an R at a minion is refused and no orb is launched", not r["ok"]
          and any("0x1000003c (0x20dc)" in lbl for lbl in r["labels"])
          and not any(e[2] == MISSILE for e in r["p"].missiles), r["ok"])


def target_dies(cfg, data):
    """2026-10-30 (tester): Meltdown may be cast on minions too, and when its target (minion or champion) dies the rest of
    its pulses go on the nearest enemy (agl-r-impact-q-e.md 3.5). The status' exit chain does it (0x340002BF,
    meltdown-moving-target.md 1.4: if NOT IsAlive(SELF) and NumRemainingPulses > 0 and DamageSuccess, the jump search
    within JumpRange 4 m and LaunchMissile 0x40000484); the orb's hit applies PulseDuration x PulsesRemaining."""
    cases = (("a minion (the bot 1.5 m from it), killed by a hit after pulse 1",
              {"units": 1, "unit_dist": 1.5, "at_unit": True, "kill_target_after": 1}, "bot"),
             ("the champion (a bot-team unit 2 m away), killed by a hit after pulse 1",
              {"units": 1, "unit_dist": 2.0, "kill_target_after": 1}, "unit"),
             ("a minion (the bot 1.5 m from it), killed by pulse 1 itself",
              {"units": 1, "unit_dist": 1.5, "at_unit": True, "target_health": 5.0}, "bot"),
             ("the champion (a bot-team unit 2 m away), killed by pulse 1 itself",
              {"units": 1, "unit_dist": 2.0, "target_health": 5.0}, "unit"))
    for label, kw, other in cases:
        print(f"Meltdown on {label} (case 8)")
        r = scene(cfg, data, dist=4.5, **kw)
        p, ch = r["p"], r["ch"]
        aim = r["units"][0] if kw.get("at_unit") else r["bot"]
        nxt = r["bot"] if other == "bot" else r["units"][0]
        on_aim = [x for x in p.pulses if x[1] is aim]
        on_next = [x for x in p.pulses if x[1] is nxt]
        died = p.killed_at if p.killed_at is not None else (on_aim[0][0] if on_aim else None)
        check(f"{label}: one pulse on the target, then it is dead", len(on_aim) == 1 and not aim.alive, (len(on_aim), aim.alive))
        jumps = [e for e in p.missiles if e[2] == MISSILE][1:]
        j = jumps[0] if jumps else None
        check(f"{label}: an AGL orb from the dead target to the nearest enemy at its death", j is not None and j[1] is ch
              and getattr(j[4], "origin", None) is aim and j[3] is nxt and died is not None and abs(j[0] - died) < 0.11,
              (j and (j[0], getattr(j[3], "name", j[3])), died))
        cast = first(p.statuses, lambda e: e[1] == MELTDOWN and e[3] is aim)
        moved = first(p.statuses, lambda e: e[1] == MELTDOWN and e[3] is nxt)
        check(f"{label}: the next enemy gets Meltdown for the pulses left (EffectDuration one pulse less)",
              cast is not None and moved is not None and moved[4] == cast[4] - 1.0, (cast and cast[4], moved))
        check(f"{label}: the remaining pulses hit it ({PULSES} in all, all AGL's)", len(on_next) == PULSES - 1
              and len(p.pulses) == PULSES and all(a is ch for _t, _o, a, _pos in p.pulses),
              [(t, getattr(o, "name", o)) for t, o, _a, _pos in p.pulses])
    for label, kw in (("alone", {}), ("with a bot-team unit 6 m away (beyond JumpRange 4 m)", {"units": 1, "unit_dist": 6.0}),
                      ("alone, killed by pulse 1 itself", {"target_health": 5.0, "kill_target_after": 0})):
        print(f"Meltdown on the bot {label}; it dies after the 1st pulse (case 8)")
        kw = dict({"kill_target_after": 1}, **kw)
        r = scene(cfg, data, dist=4.5, **kw)
        p, bot = r["p"], r["bot"]
        check(f"{label}: no orb after the death, no more pulses", not bot.alive
              and sum(1 for e in p.missiles if e[2] == MISSILE) == 1 and len(p.pulses) == 1, (len(p.pulses), len(p.missiles)))
        check(f"{label}: Meltdown ended cleanly (no status left on the dead bot, no script error)",
              not R.statuses_on(r["w"].combat.world, bot).get(MELTDOWN)
              and not any("Traceback" in ln or "failed" in ln for ln in r["logs"]),
              [ln[:120] for ln in r["logs"] if "Traceback" in ln or "failed" in ln][:2])
    # [ics] death_status_end_after_chain off: a pulse that kills its target ends the status inside its own chain, before
    # its PulsesRemaining - 1, and the next target gets one pulse too many (the fase3-ir behaviour)
    cfg["ics"]["death_status_end_after_chain"] = False
    r = scene(cfg, data, dist=4.5, units=1, unit_dist=2.0, target_health=5.0)
    cfg["ics"]["death_status_end_after_chain"] = True
    check("with death_status_end_after_chain off the pulse-kill gives one pulse too many (the key matters)",
          len(r["p"].pulses) == PULSES + 1, len(r["p"].pulses))


def caster_dead(cfg, data):
    print("AGL dies after the 2nd pulse; an AGL-team unit stands by the bot (case 6)")
    r = scene(cfg, data, dist=4.5, ally_unit=True, kill_after=2)
    p, ch, bot, ally = r["p"], r["ch"], r["bot"], r["ally"]
    check("the pulses go on after AGL's death", len(p.pulses) == PULSES, len(p.pulses))
    check("they still act for AGL (dead or alive)", all(a is ch for _t, _o, a, _pos in p.pulses))
    check("the AGL-team unit is never hit", not any(tgt is ally for _t, tgt in p.status_hits))
    check("no pulse damage credited to the bot", not any(src is bot for _t, src, _tg, _a in p.damage))


def grab(cfg, data):
    """AGL's Q Grab (0x340002B5, missile 0x40000485 with script 0x340002C1) at the enemy bot champion (tester report
    2026-10-29 11:00: Grab pulls minions but never the champion; docs/re-notes/agl-grab-arm.md 2)."""
    for label, kw in (("a still bot 5 m away", {}), ("a bot walking away", {"walk": True}),
                      ("a bot that ran Vault Kick's Enable / DisableCollision first", {"dashed": True})):
        print("Grab at " + label)
        # 2026-10-29 ([ics] graph_feed_at_send, skill-animations-vs-original.md 2.1): the hand now leaves at the client's
        # code 5 (0.13 s later than before); a bot walking straight away from 5 m is then out of Grab's 7 m range when the
        # hand gets there, a borderline shot this check is not about (collision / IsMoving): it walks from 4 m
        r = scene(cfg, data, dist=4.0 if kw.get("walk") else 5.0, slot=1, seconds=2.5, **kw)
        ch, bot, logs = r["ch"], r["bot"], r["logs"]
        check("Grab: cast accepted", r["ok"])
        hit = any("0x340002c1 S3 -> S4" in ln for ln in logs)
        check(f"Grab ({label}): the missile hits the bot (0x340002C1 S3 -> S4)", hit)
        pulled = any("0x340002c1 S4 -> S1" in ln for ln in logs) and not any("0x340002c1 S4 -> S11" in ln for ln in logs)
        check(f"Grab ({label}): the pull branch S4 -> S1 (NOT IsMoving[0]), not S11", pulled,
              [ln[-40:] for ln in logs if "0x340002c1 S4" in ln][:2])
        d = math.dist(ch.pos[:2], bot.pos[:2])
        check(f"Grab ({label}): the bot ends in front of AGL (< 2.6 m)", d < 2.6, round(d, 2))
        st = w_flags = r["w"].combat.of(bot).flags
        check(f"Grab ({label}): the bot is still in collision", not st.get("collision_off"), w_flags)
        check(f"Grab ({label}): AGL is still in collision (the missile's DisableCollision is the missile's)",
              not r["w"].combat.of(ch).flags.get("collision_off"))


def main():
    cfg = config.load()
    cfg["ics"]["trace_scripts"] = True                   # the "loop cut" line goes through the script trace
    cfg["ics"]["match_waves"]["stagger"] = 0.0
    cfg["ics"]["match_waves"]["first"] = 1.0
    cfg["ics"]["match_pre_start"] = 13.0                   # no intro cinematic here: the short wait
    cfg["ics"]["liftable_gallery"] = False
    for key in ("missile_reaim_from_current", "status_acts_for_source", "status_skill_hit_event",
                "event_loop_per_target", "status_self_remove_after_chain", "skill_hit_event"):
        cfg["ics"][key] = True                             # the defaults under test (a tester's config.toml may differ)
    data = Data(cfg.game_dir)
    setup(cfg, data)
    saved = install_probes()
    time.time = _virtual_time
    try:
        for fn in (standing, walking, stacked, jump, crowd, caster_dead, impact_and_target, target_dies, grab):
            fn(cfg, data)
    finally:
        time.time = _real_time
        _clock["s"] = None
        R.HANDLERS[0x1000001D], R.apply_status, W.CastWorld.launch_missile = saved
    bad = [name for name, ok in CHECKS if not ok]
    print(f"{len(CHECKS) - len(bad)}/{len(CHECKS)} Meltdown / Grab checks")
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main())
