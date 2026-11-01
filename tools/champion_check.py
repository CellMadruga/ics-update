"""Headless kit check: every champion casts its basic attack and Q W E R vs AI in Crime Alley (0x40000C82).

For each champion variant (the base variants; --all adds the costumes; --only <did> one variant) the tool builds a
World + PvP match on a simulated session (as tests/test_match.py), creates the variant as the local champion, levels
it to 6 with slots 0-4 at rank 1, waits for the first minion wave, then for each slot puts an enemy minion 2 m away
and casts the skill the way the client orders it for the skill's targeting type (full-combat-skills.md, the
0x1000003D table: 14 / 9 = unit target, 1 / 10 / 11 / 13 / 16 = point, 5 / 7 = instant) and runs ~3 s of game time.

Recorded per slot: cast accepted (World.cast), damage the champion (or what it created) dealt, statuses applied,
missiles launched, entities spawned, scriptlets sent for the champion, cooldown / Will spent, script errors,
"not implemented" nodes, refused / not decoded / failed log lines, exceptions. A slot with no visible effect is
cast a second time with both a target and a point (the "retry" column), which separates targeting problems from
script problems.

The script timers compare against time.time(); the tool runs on a virtual clock (time.time is the simulated
session's clock while it runs), so ~3 s of game time take a fraction of a second.

    python tools\\champion_check.py                 # base variants
    python tools\\champion_check.py --all           # with the costumes
    python tools\\champion_check.py --only 0x400005C6
    python tools\\champion_check.py --out <file.json>
    python tools\\champion_check.py --vs-champion --window 5 --press-event --recast 1
        (the cast at the bot champion as the client makes it: 0x20EA 0x10000023 first for non-instant slots, and a
        second press at the bot 1 s later when the script waits for one: Bullseye's release, Batman's dive)
    python tools\\champion_check.py --only 0x4000047D --vs-champion --window 8 --bot-walk
        (the bot champion walks 10 m away during the cast's window and back: Meltdown on a moving target)

With --vs-champion an instant slot that still waits for a second use after the earlier casts (a toggle left on, such
as Gaslight Joker's Rat Swarm) is pressed once more before the cast at the bot, so that cast starts from idle; the
slot's JSON row then has "vs_bot_toggle_reset" (--keep-toggles: no extra press, the tool before 2026-10-29).
"""
import argparse
import json
import math
import os
import sys
import tempfile
import time
import traceback

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
sys.path.insert(0, os.path.join(ROOT, "tests"))

ENCOUNTER = 0x40000C82
UNIT_TARGET = {9, 14}
POINT_TARGET = {1, 10, 11, 13, 16}
INSTANT = {5, 7}
BAD = ("not implemented", "refused", "not decoded", "error", "failed", "not started", "not running",
       "no skill", "Traceback", "unknown", "dropped")

_real_time = time.time
TRACE = {}
INIT_EVENTS = []
_clock = {"s": None}


def _virtual_time():
    s = _clock["s"]
    return s.clock if s is not None else _real_time()


class Probe:
    """Counts what a cast did, by hooks on the World / CastWorld / runtime."""

    def __init__(self):
        self.reset()

    def reset(self):
        self.damage = 0.0
        self.damage_hits = 0
        self.self_damage = 0.0
        self.statuses = []
        self.missiles = []
        self.spawned = []
        self.scriptlets = []
        self.moves = 0
        self.heals = 0.0
        self.signals = []                 # [(t, code)] cast signals delivered to the watched script (sequence check)
        self.raised = []                  # times the watched script raised a graph event (RaiseGraphEvent)


def owned_by(cw_world, ent, ch, depth=0):
    """ent is the champion, or something the champion created (a spawned entity, a missile)."""
    if ent is None or depth > 4:
        return False
    if ent is ch:
        return True
    owner = getattr(ent, "owner", None)
    if owner is not None and owner is not ent and owned_by(cw_world, owner, ch, depth + 1):
        return True
    try:
        st = cw_world.combat.states.get(cw_world_key(ent))
        creator = getattr(st, "creator", None) if st is not None else None
    except Exception:                                      # noqa: BLE001
        creator = None
    return creator is not None and owned_by(cw_world, creator, ch, depth + 1)


def cw_world_key(ent):
    from ics import script_runtime as R
    return R._key(ent)


VS_BOT = {"on": False, "bot": None}


def install_hooks(T, R, W, probe):
    """Class / module level hooks (once): missiles, spawns, scriptlets, statuses, moves."""
    CW = W.CastWorld

    orig_launch = CW.launch_missile

    def launch(self, owner, missile_class, target, speed, max_range, scripts, **extra):
        m = orig_launch(self, owner, missile_class, target, speed, max_range, scripts, **extra)
        if self.w is probe.world and owned_by(self.w, self._ent(owner), self.w.champion):
            probe.missiles.append((missile_class, m))
        return m
    CW.launch_missile = launch

    orig_spawn = CW.spawn_entity

    def spawn(self, owner, cls, pos, props=None, visual=False):
        ent = orig_spawn(self, owner, cls, pos, props, visual)
        if self.w is probe.world:
            probe.spawned.append(cls)
        return ent
    CW.spawn_entity = spawn

    orig_scriptlet = CW.run_scriptlet

    def scriptlet(self, ent, key, target=None, variables=None):
        if self.w is probe.world and self._ent(ent) is self.w.champion:
            probe.scriptlets.append(key)
        return orig_scriptlet(self, ent, key, target, variables)
    CW.run_scriptlet = scriptlet

    orig_move = CW.move

    def move(self, ent, pos, speed=0.0, teleport=False, quiet=False):
        if self.w is probe.world and self._ent(ent) is self.w.champion:
            probe.moves += 1
        return orig_move(self, ent, pos, speed, teleport, quiet)
    CW.move = move

    orig_apply = R.apply_status

    def apply_status(world, source, target, status, params, skill_world=None, **kw):
        cur = orig_apply(world, source, target, status, params, skill_world, **kw)
        w = getattr(world, "w", None)
        if w is probe.world:
            src = world._ent(source) if hasattr(world, "_ent") else source
            tgt = world._ent(target) if hasattr(world, "_ent") else target
            if owned_by(w, src, w.champion):
                who = "self" if tgt is w.champion else ("enemy" if getattr(tgt, "team", 0) not in (0, w.champion.team)
                                                         else "other")
                probe.statuses.append((status, who))
        return cur
    R.apply_status = apply_status

    orig_signal = R.Instance.signal

    def signal(self, code):
        if probe.world is not None and getattr(self.script, "did", None) == getattr(probe, "watch", None)                 and _clock["s"] is not None:
            probe.signals.append((round(_clock["s"].clock, 3), code))
        return orig_signal(self, code)
    R.Instance.signal = signal

    orig_rge = R.HANDLERS[0x1000004E]

    def raise_graph_event(inst, n, ops, chain):
        if probe.world is not None and _clock["s"] is not None and getattr(inst.script, "did", None) == probe.watch:
            probe.raised.append(round(_clock["s"].clock, 3))
        return orig_rge(inst, n, ops, chain)
    R.HANDLERS[0x1000004E] = raise_graph_event


def instance_hooks(w, probe):
    orig_damage = w.damage

    def damage(source, target, amount):
        ch = w.champion
        if target is ch:
            probe.self_damage += float(amount or 0)
        elif owned_by(w, source, ch) and getattr(target, "team", 0) != ch.team and amount:
            probe.damage += float(amount)
            probe.damage_hits += 1
        return orig_damage(source, target, amount)
    w.damage = damage

    orig_heal = w.heal

    def heal(source, target, amount):
        if target is w.champion and amount:
            probe.heals += float(amount)
        return orig_heal(source, target, amount)
    w.heal = heal


def unknown_nodes(w, probe):
    out = set()
    for lst in w.scripts.values():
        for inst in lst:
            out |= set(map(str, getattr(inst, "unknown", ()) or ()))
    for _cls, m in probe.missiles:
        for inst in getattr(m, "instances", ()):
            out |= set(map(str, getattr(inst, "unknown", ()) or ()))
    return out


def pack_info(data, variant, entry):
    def has(p):
        return bool(p) and os.path.isfile(os.path.join(data.rp_dir, f"0x{p:08x}.rp"))
    model = data.champion_pack(variant)
    shared = data.champion_shared_packs(variant)
    info = {"model_pack": f"0x{model:08X}" if model else "", "model_pack_ok": has(model),
            "shared_packs": [f"0x{p:08X}" for p in shared], "shared_packs_ok": all(has(p) for p in shared)}
    for k in ("light_pack", "skills_pack"):
        p = entry.get(k, 0)
        info[k] = f"0x{p:08X}" if p else ""
        info[k + "_ok"] = has(p)
    return info


def patch_entity_scripts(data):
    """Experiment (--fix-missile-scripts), the fix proposed for ics/gamedata.py Data.entity_scripts: the pack's
    record-start list (rp.Pack.record_starts) also "starts" records at interior words of a template (e.g. the world
    state DID after property 0x510 in 0x490003EB, or inside the 0x8E list of 0x49000146), so the template window ends
    before its 0x8E script list. When the window gives no list, search on up to the next template header
    (0x49xxxxxx | 3) or 4 KB."""
    import struct as _st
    from ics import gamedata as G
    orig = data.entity_scripts

    def entity_scripts(class_did):
        out = orig(class_did)
        if out:
            return out
        rec = data._record(0x49000000 | (class_did & 0xFFFFFF))
        if not rec:
            return out
        buf, start, end = rec
        limit = min(len(buf), end + 0x1000)
        for k in range(start + 4, limit - 8, 4):
            # the next template record header "0x49xxxxxx | 3 | count" ends the search
            if buf[k + 3] == 0x49 and _st.unpack_from("<I", buf, k + 4)[0] == 3:
                limit = k
                break
        for m in G._SCRIPT_LIST.finditer(buf, start, limit):
            n = _st.unpack("<I", m.group(1))[0]
            items = [_st.unpack_from("<I", m.group(2), 8 * j + 4)[0] for j in range(len(m.group(2)) // 8)]
            if n == len(items):
                data._scripts[class_did] = items
                return items
        return out
    data.entity_scripts = entity_scripts


def patch_range_angle():
    """Experiment (--fix-range-angle), the fix proposed for ics/script_nodes.py _in_range_and_angle: with the max
    range operand unset (cone checks such as Katana's Slash 0x340005B8: IsInRangeAndAngle(-, -, $Angle, target,
    SELF) [1 1]) the radius flags alone made a range of ~1 m, so every target 2 m away failed. Only a set max range
    limits the distance."""
    from ics import script_nodes as N
    from ics import script_runtime as R
    orig = N._in_range_and_angle

    def in_range_and_angle(inst, n, ops):
        if len(ops) > 1 and not ops[1].is_unset():
            return orig(inst, n, ops)
        values = list(n.values)
        try:
            n.values = [0, 0] + values[2:]
            return orig(inst, n, ops)
        finally:
            n.values = values
    for table in (R.PREDICATES, R.HANDLERS, getattr(N, "PREDICATE_NODES", {})):
        if isinstance(table, dict):
            for k, v in list(table.items()):
                if v is orig:
                    table[k] = in_range_and_angle


def patch_raise_event():
    """Experiment (--fix-raise-event), the fix proposed for ics/script_nodes.py _raise_event_node: RaiseEvent's
    second value is the script the event is for (Cyborg's basic attack 0x34000238: RaiseEvent(SELF)
    [0x1000001D 0x34000237] = "skill used" for his passive 0x34000237 only). Sent to every script on the entity,
    it activated all of Cyborg's skills on each basic attack. With a script DID, only that script's instances get it."""
    from ics import script_nodes as N
    from ics import script_runtime as R
    orig = N._raise_event_node

    def raise_event_node(inst, n, ops, chain):
        vals = list(n.values)
        did = vals[1] if len(vals) > 1 and isinstance(vals[1], int) and vals[1] >> 24 == 0x34 else 0
        if not did:
            return orig(inst, n, ops, chain)
        ev = vals[0] if isinstance(vals[0], int) else 0
        ent = inst.ent(ops[0]) if ops else inst.owner
        if ev and ent is not None and not inst.removed:
            params = R._params(inst, ops, R.RAISE_PARAMS)
            for other in list(R.scripts_on(inst.world, ent)):
                if getattr(getattr(other, "script", None), "did", None) == did:
                    other.event(ev, params)
            if ev == R.EVENT_IMPACT and inst.status is not None:
                R.remove_status(inst.world, inst.owner, inst.status, inst)
        return False
    for table in (R.HANDLERS, getattr(N, "ACTIONS", {})):
        for k, v in list(table.items()):
            if v is orig:
                table[k] = raise_event_node


def check_variant(T, R, V, cfg, data, probe, variant, name, entry, step=0.05, window=3.0, warmup=17.0):
    from ics import world as W
    res = {"variant": f"0x{variant:08X}", "name": name, "slots": {}, "errors": []}
    res.update(pack_info(data, variant, entry))
    logs = []
    s = T.FakeSession()
    _clock["s"] = s
    spawn = T.pvp.spawn_point(ENCOUNTER, 1)
    w = T.World(data, cfg, ENCOUNTER, spawn, send=s.send, schedule=s.schedule, log=logs.append)
    probe.world = w
    nav = T.pvp.navgrid(data, ENCOUNTER, spawn[1:3])
    w.nav = nav.copy() if nav else None
    w.ground_z = spawn[6]
    try:
        ch = w.create_champion(variant, spawn)
    except Exception:                                      # noqa: BLE001
        res["errors"].append("create_champion: " + traceback.format_exc().strip().splitlines()[-1])
        res["create_log"] = [ln[:300] for ln in logs if any(b in ln for b in BAD)]
        return res
    res["kit"] = {str(sl): {"key": sk.key, "name": sk.name, "script": f"0x{sk.script:08X}" if sk.script else "",
                            "targeting": sk.targeting} for sl, sk in sorted(ch.kit.items())}
    res["create_log"] = [ln[:300] for ln in logs if any(b in ln for b in BAD)]
    instance_hooks(w, probe)
    w.in_world = True
    m = T.pvp.start_match(w, s, ENCOUNTER)
    T.run(s, m, warmup)
    ch.level = 6
    for sl in range(0, 5):
        if sl in ch.kit:
            ch.ranks[sl] = max(1, ch.ranks.get(sl, 0))
    w.recompute_stats(ch, refill=True)
    for ev in INIT_EVENTS:
        # experiment (--init-events): events the champion's scripts wait for and the server never raises (e.g.
        # 0x10000088: Arcane Green Lantern's passive spawns its Lantern on it)
        try:
            w.raise_event(ch, ev)
        except Exception:                                  # noqa: BLE001
            res["errors"].append(f"init event {ev:#x}: " + traceback.format_exc().strip().splitlines()[-1])
    if INIT_EVENTS:
        T.run(s, m, 1.0)
    # the minions stand still from now on (a dash / melee skill aimed at a walking minion misses at random); forced
    # movement (knockbacks, pulls) does not use move_speed
    for mu in m.waves.minions:
        mu.ent.move_speed = 0.0
        mu.ent.dest, mu.ent.path, mu.ent.speed = None, [], 0.0

    def pick_enemy():
        alive = [mu for mu in m.waves.minions if mu.team != ch.team and mu.ent.alive and mu.ent.health]
        return min(alive, key=lambda mu: math.hypot(mu.ent.pos[0] - ch.pos[0], mu.ent.pos[1] - ch.pos[1]),
                   default=None)

    def fresh():
        """Full health / Will, no cooldown, lock or forced movement before a cast."""
        ch.alive = True
        ch.health, ch.will = ch.max_health, ch.max_will
        ch.ready_at.clear()
        try:
            st = w.combat.of(ch)
            st.motion, st.input_locks = None, 0
            st.locks.clear()
            st.cooldowns.clear()
        except Exception:                                  # noqa: BLE001
            pass

    def place_near(e, dist=2.0):
        """The champion dist m from e on a walkable spot with a clear line to it (a dash from off the navmesh is
        clipped to nothing), facing it."""
        best = None
        for k in range(16):
            a = math.pi + k * math.pi / 8
            x, y = e.pos[0] + math.cos(a) * dist, e.pos[1] + math.sin(a) * dist
            if w.nav is None or (w.nav.walkable(x, y) and w.nav.line_clear((x, y), e.pos[:2])
                                 and w.nav.line_clear((x, y), (x + (x - e.pos[0]) * 2, y + (y - e.pos[1]) * 2))):
                best = (x, y)
                break
        if best is None:
            best = (e.pos[0] - dist, e.pos[1])
        ch.pos = [best[0], best[1], ch.pos[2]]
        ch.dest, ch.path, ch.speed, ch.attack_target = None, [], 0.0, None
        ch.heading = math.atan2(e.pos[1] - best[1], e.pos[0] - best[0])

    def run_window(seconds):
        n = int(round(seconds / step))
        for _ in range(n):
            s.clock += step
            w.tick(step, s.clock)
            s.run_due()

    def one_cast(sl, sk, target, point, recast_after=None, press=False, recast_target=None):
        probe.reset()
        probe.watch = sk.script
        t_cast = s.clock
        mark = len(logs)
        will0, cd0 = ch.will, ch.ready_at.get(sl, 0.0)
        before_unknown = unknown_nodes(w, probe)
        exc = None
        try:
            if press and sl and sk.targeting not in INSTANT:
                # --press-event: the client enters targeting first and sends 0x20EA {slot, 0x10000023 "targeting begun"}
                # (skill-execution-model.md 1.2; 6 ms before the 0x20EE order with smart cast)
                w.raise_skill_event(ch, sl, 0x10000023)
            ok = w.cast(ch, sl, target, point)
        except Exception:                                  # noqa: BLE001
            ok, exc = False, traceback.format_exc().strip().splitlines()[-1]
        recast = False
        try:
            if recast_after and ok and recast_after < window:
                # --recast: the player presses the key again while the script waits for a second 'skill used'
                # (Bullseye's release, a dash's second stage), as the client sends it
                run_window(recast_after)
                if waits_second_use(R, ch.skill_insts.get(sl)):
                    # the second press aims at the cursor's unit and point (a second stage such as Batman's dive takes
                    # a target even when the first stage is instant)
                    rt = target if target is not None else recast_target
                    tp = point
                    if rt is not None and getattr(rt, "pos", None) is not None:
                        tp = (rt.pos[0], rt.pos[1], point[2] if point else rt.pos[2])
                    recast = bool(w.cast(ch, sl, rt, tp))
                run_window(window - recast_after)
            else:
                run_window(window)
        except Exception:                                  # noqa: BLE001
            exc = (exc or "") + " | run: " + traceback.format_exc().strip().splitlines()[-1]
        lines = logs[mark:]
        if TRACE.get("slot") == sl:
            print(f"---- trace slot {sl} ({sk.name}, script {sk.script:#x}, target {target}, point {point})")
            for ln in lines[:TRACE.get("lines", 400)]:
                print("   ", ln[:240])
        bad = [ln[:300] for ln in lines if any(b in ln for b in BAD)]
        seq = sequence_verdict(R, w, ch, sk.script, probe.signals, probe.raised)
        return {
            "signals": [(round(t - t_cast, 3), c) for t, c in probe.signals], "seq": seq,
            "accepted": bool(ok), "damage": round(probe.damage, 1), "hits": probe.damage_hits,
            "statuses": [f"0x{st:08X}:{who}" for st, who in probe.statuses],
            "missiles": [f"0x{c:08X}" for c, _m in probe.missiles], "spawned": [f"0x{c:08X}" for c in probe.spawned],
            "scriptlets": [f"0x{k:08X}" if isinstance(k, int) else str(k) for k in probe.scriptlets],
            "moves": probe.moves, "heals": round(probe.heals, 1),
            "cooldown": round(max(0.0, ch.ready_at.get(sl, 0.0) - s.clock), 2) if ch.ready_at.get(sl, 0.0) != cd0 else 0.0,
            "will_spent": round(max(0.0, will0 - ch.will), 1),
            "unknown": sorted(unknown_nodes(w, probe) - before_unknown), "log": bad[:12], "exception": exc,
            "recast": recast,
        }

    for sl in range(0, 5):
        sk = ch.kit.get(sl)
        if sk is None:
            res["slots"][str(sl)] = {"missing": True}
            continue
        fresh()
        enemy = pick_enemy()
        if enemy is None:
            T.run(s, m, 31.0)                              # the next wave
            enemy = pick_enemy()
        if enemy is None:
            res["slots"][str(sl)] = {"no_enemy": True}
            continue
        e = enemy.ent
        place_near(e)
        point = (e.pos[0], e.pos[1], ch.pos[2])
        tt = sk.targeting
        if tt in UNIT_TARGET:
            target, pt = e, point
        elif tt in POINT_TARGET:
            target, pt = None, point
        else:
            target, pt = None, None
        r = one_cast(sl, sk, target, pt)
        r["targeting"] = tt
        r["target_hp"] = [e.health, e.max_health]
        effect = r["damage"] or r["statuses"] or r["missiles"] or r["spawned"] or r["scriptlets"] or r["moves"] \
            or r["cooldown"] or r["will_spent"] or r["heals"]
        r["effect"] = bool(effect)
        base = (res["slots"].get("0") or {}).get("damage", 0.0)
        if sl and not r["damage"] and r["accepted"] and base:
            # an "empowered next attack" skill: a basic attack right after it (compared with slot 0's own hit)
            enemy = pick_enemy()
            if enemy is not None:
                e2 = enemy.ent
                place_near(e2)
                fresh()
                ch.next_attack = 0.0
                r0 = one_cast(0, ch.kit[0], e2, (e2.pos[0], e2.pos[1], ch.pos[2]))
                r["next_basic_damage"] = r0["damage"]
                r["next_basic_boosted"] = bool(r0["damage"] > base * 1.15)
        if sl and not r["damage"] and r["accepted"]:
            # the skill may only accept an enemy champion (IsKind flag 8): a dummy enemy champion, cast on it
            dummy = W.Entity(w.new_id(), "dummy enemy champion", ch.class_id, [ch.pos[0] + 2.5 * math.cos(ch.heading),
                                                                          ch.pos[1] + 2.5 * math.sin(ch.heading), ch.pos[2]],
                             team=2 if ch.team != 2 else 1, kind="champion")
            dummy.health = dummy.max_health = 3000
            dummy.client_vitals = False
            w.add(dummy)
            fresh()
            if tt in UNIT_TARGET:
                tgt, ptt = dummy, tuple(dummy.pos)
            elif tt in POINT_TARGET:
                tgt, ptt = None, tuple(dummy.pos)
            else:
                tgt, ptt = None, None
            r3 = one_cast(sl, sk, tgt, ptt)
            r["vs_champion"] = {k: r3[k] for k in ("accepted", "damage", "statuses", "missiles", "scriptlets",
                                                   "cooldown", "will_spent", "moves", "log")}
            if dummy.eid in w.entities:
                w.remove(dummy)
        if not effect and r["accepted"] and tt in UNIT_TARGET:
            # an ally / self target skill (Best Medicine, Protection, Thorn Shield): cast on the champion itself
            fresh()
            r4 = one_cast(sl, sk, ch, tuple(ch.pos))
            r["vs_self"] = {k: r4[k] for k in ("accepted", "damage", "statuses", "missiles", "scriptlets", "cooldown",
                                               "will_spent", "heals", "log")}
        if not effect and r["accepted"]:
            fresh()
            enemy = pick_enemy()
            if enemy is not None:
                e = enemy.ent
                place_near(e)
                r2 = one_cast(sl, sk, e, (e.pos[0], e.pos[1], ch.pos[2]))
                r["retry"] = {k: r2[k] for k in ("accepted", "damage", "statuses", "missiles", "scriptlets", "cooldown",
                                                 "will_spent", "unknown", "log", "exception")}
                r["retry"]["effect"] = bool(r2["damage"] or r2["statuses"] or r2["missiles"] or r2["scriptlets"]
                                            or r2["cooldown"] or r2["will_spent"] or r2["moves"])
        if VS_BOT.get("on"):
            # 2026-10-28 (tester: "the champions' R do no damage to the enemy champion"): every slot is also cast at a real
            # enemy bot champion (World.create_bot_champion: stats, kit, scripts) standing 2 m away
            bot = VS_BOT.get("bot")
            if bot is None or not bot.alive or bot.eid not in w.entities:
                bot = w.create_bot_champion(variant, 2 if ch.team != 2 else 1, "enemy bot", 0,
                                            pos=[ch.pos[0] + 2.0, ch.pos[1], ch.pos[2]])
                VS_BOT["bot"] = bot
                VS_BOT["speed"] = bot.move_speed
            bot.move_speed = 0.0
            run_window(8.0)                 # the earlier casts of this slot (channels, dashes) end first
            if VS_BOT.get("reset_toggles", True) and sl and sk.targeting in INSTANT \
                    and waits_second_use(R, ch.skill_insts.get(sl)):
                # 2026-10-29 (fase3-if check: Gaslight Joker's Rat Swarm 0x34000201 is a toggle; its first cast now deals
                # damage, so the dummy-champion cast that used to switch it back off is skipped, and the vs-bot cast
                # switched it off: 3.1 instead of 109.8): an instant slot still waiting for a second use is pressed once
                # more, so the vs-bot cast starts from its idle state (--keep-toggles: as before)
                fresh()
                try:
                    w.cast(ch, sl, None, None)
                except Exception:                          # noqa: BLE001
                    pass
                run_window(2.0)
                r["vs_bot_toggle_reset"] = True
            bot.alive, bot.health = True, bot.max_health
            fresh()
            place_near(bot)
            tgt, ptt = (bot, tuple(bot.pos)) if tt in UNIT_TARGET else ((None, tuple(bot.pos)) if tt in POINT_TARGET
                                                                          else (None, None))
            hp0 = bot.health
            if VS_BOT.get("walk"):
                # --bot-walk (2026-10-28 15:00, tester report 2026-10-28 15:00; meltdown-moving-target.md 6.8): the bot
                # walks 10 m away from the champion from 0.3 s after the cast, and back from half the window
                bot.move_speed = VS_BOT.get("speed") or 3.9
                home = list(bot.pos)
                d = math.hypot(bot.pos[0] - ch.pos[0], bot.pos[1] - ch.pos[1]) or 1.0
                away = [bot.pos[0] + (bot.pos[0] - ch.pos[0]) / d * 10.0, bot.pos[1] + (bot.pos[1] - ch.pos[1]) / d * 10.0,
                        bot.pos[2]]
                s.schedule(0.3, lambda: w.walk_to(bot, away))
                s.schedule(max(0.6, window / 2), lambda: w.walk_to(bot, home))
            r5 = one_cast(sl, sk, tgt, ptt, recast_after=VS_BOT.get("recast"), press=VS_BOT.get("press"),
                          recast_target=bot)
            if VS_BOT.get("walk"):
                bot.move_speed = 0.0
                bot.dest, bot.path, bot.speed = None, [], 0.0
            r["vs_bot"] = {"accepted": r5["accepted"], "damage": round(max(0.0, hp0 - (bot.health or 0)), 1),
                           "statuses": r5["statuses"], "log": r5["log"][:4], "exception": r5["exception"],
                           "recast": r5["recast"]}
        res["slots"][str(sl)] = r
    VS_BOT["bot"] = None
    probe.world = None
    _clock["s"] = None
    return res


def waits_second_use(R, inst, ev=0x1000001D):
    """--recast: is a graph of the instance (any top-level one, any depth) out of its idle S0 with a transition from its
    current state that waits for 'skill used'? (R.recast_window only looks below the first top-level graph.)"""
    if inst is None or inst.removed:
        return False

    def values(n):
        out = [v for v in n.values if isinstance(v, int)]
        for c in n.children:
            out += values(c)
        return out

    def waits(region):
        if region is None or region.state is None:
            return False
        if region.state != 0:
            for t in region.graph.transitions:
                if not t.sources or region.state not in t.sources:
                    continue
                if t.trigger is not None and R._event_trigger(t.trigger) and ev in values(t.trigger):
                    return True
        return waits(region.child)
    return any(waits(r) for r in inst.regions)


def expected_codes(variant, did):
    """Cast-signal codes (3 / 4 / 5) the champion's graph has in the states hooked to the script (any sub-state)."""
    from ics import graph as GR
    g = GR.data().for_variant(variant)
    if g is None or did not in g.hooked:
        return None
    out = set()

    def walk(mid, sid, depth=0):
        st = g.state(mid, sid)
        if st is None or depth > 6:
            return
        for c in st["body"]["clips"]:
            for t in c["trig"]:
                if t.get("code") in (3, 4, 5) and (not t.get("did") or t["did"] == did):
                    out.add(t["code"])
        for sub in st["body"]["sm"]:
            for sid2 in g.machines[sub]["states"]:
                walk(sub, int(sid2), depth + 1)
    for mid, sid in g.hooked[did]:
        walk(mid, sid)
    return out


def sequence_verdict(R, w, ch, did, signals, raised=()):
    """2026-10-27 (skill-execution-model.md 6.6.2): the codes the slot's script got vs its graph's. HANG = still
    casting (or the graph still in its state) after the window; EARLY2 = code 2 before any expected 3 / 5; SIG = an
    expected 3 / 5 never came, or a 3 / 5 the graph does not have; OK; n/a = the graph does not hook the script."""
    exp = expected_codes(ch.class_id, did)
    if exp is None:
        return "n/a"
    insts = [i for i in R.scripts_on(w, ch) if getattr(i.script, "did", 0) == did and not i.removed]
    g = ch.__dict__.get("graph_rt") or None
    if any(getattr(i, "casting", 0) > 0 for i in insts):
        return "HANG"
    acc = R.accepted_events(insts[0].script) if insts else ()
    if acc and R.EVENT_CAST_SIGNAL not in acc:
        return "n/a"                                       # the script does not wait for cast signals
    if g is not None and g.in_state_of(did):
        return "HANG"
    codes = [c for _t, c in signals]
    if 2 in codes and exp & {3, 5}:
        first2 = codes.index(2)
        t2 = signals[first2][0]
        # a code 2 in the tick the script raised a graph event itself is the script ending its own skill (Blocking
        # Bracers' interrupt, a dash's end), not an early exit
        # (2026-10-29, [ics] graph_feed_at_send: the graph gets the raised event when the 0x8D leaves, up to
        # champion_scriptlet_delay + a tick later)
        lag = float(w.ic.get("champion_scriptlet_delay", 0.0) or 0.0) + 0.06 if w.ic.get("graph_feed_at_send") else 1e-6
        if not any(c in (3, 5) for c in codes[:first2]) and not any(0 <= t2 - t < lag for t in raised):
            return "EARLY2"
    got = {c for c in codes if c in (3, 4, 5)}
    if (exp & {3, 5}) - got or got - exp:
        return "SIG"
    return "OK"


def verdict(r):
    if not r or r.get("missing"):
        return "--"
    if r.get("no_enemy"):
        return "noE"
    if r.get("exception"):
        return "EXC"
    if not r.get("accepted"):
        return "REF"
    if r.get("damage"):
        return "DMG"
    if (r.get("vs_champion") or {}).get("damage"):
        return "CHMP"
    if r.get("next_basic_boosted"):
        return "BUFF"
    if r.get("statuses") or r.get("heals") or r.get("moves") or r.get("missiles") or r.get("spawned"):
        return "FX"
    if r.get("scriptlets") or r.get("cooldown") or r.get("will_spent"):
        return "anim"
    if r.get("retry", {}).get("effect"):
        return "TGT"
    return "NONE"


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--all", action="store_true", help="costume variants too")
    ap.add_argument("--only", help="one variant DID (hex)")
    ap.add_argument("--out", help="JSON summary path")
    ap.add_argument("--trace", type=int, help="print every log line of this slot's cast window (with --only)")
    ap.add_argument("--trace-lines", type=int, default=400)
    ap.add_argument("--fix-missile-scripts", action="store_true",
                    help="experiment: missile scripts read past false record starts (see patch_entity_scripts)")
    ap.add_argument("--init-events", default="", help="experiment: comma-separated events raised on the champion's "
                    "scripts after it is levelled (e.g. 0x10000088,0x1000000C)")
    ap.add_argument("--fix-range-angle", action="store_true",
                    help="experiment: IsInRangeAndAngle without a max range ignores the radius flags (patch_range_angle)")
    ap.add_argument("--fix-raise-event", action="store_true",
                    help="experiment: RaiseEvent [event, script] only reaches that script (patch_raise_event)")
    ap.add_argument("--fixes", action="store_true", help="all the experiments above (missile scripts, range-angle, "
                    "raise-event)")
    ap.add_argument("--window", type=float, default=3.0, help="game seconds after each cast")
    ap.add_argument("--vs-champion", action="store_true", help="also cast every slot at an enemy bot champion and "
                    "report the damage it took (column 'vs bot' in the summary)")
    ap.add_argument("--recast", type=float, default=0.0, help="with --vs-champion: s after the cast at the bot "
                    "champion to press the key again when the script waits for a second 'skill used' (0 = never)")
    ap.add_argument("--press-event", action="store_true", help="with --vs-champion: the cast at the bot champion is "
                    "preceded by the client's 0x20EA 'targeting begun' (0x10000023) for non-instant slots")
    ap.add_argument("--bot-walk", action="store_true", help="with --vs-champion: the bot champion walks 10 m away from "
                    "the champion from 0.3 s after the cast and back from half the window (a moving target)")
    ap.add_argument("--keep-toggles", action="store_true", help="with --vs-champion: do not switch an instant slot "
                    "that still waits for a second use (a toggle left on by the earlier casts) back off before the cast "
                    "at the bot champion (the tool before 2026-10-29)")
    ap.add_argument("--graph-runtime", choices=("on", "off", "config"), default="config",
                    help="[ics] graph_runtime for this run (cast signals from the champion's graph, ics/graph.py)")
    ap.add_argument("--accept-filter", choices=("on", "off", "config"), default="config",
                    help="[ics] script_accept_filter for this run")
    args = ap.parse_args(argv)

    from ics import config
    from ics import script_model as V
    from ics import script_runtime as R
    from ics import world as W
    from ics.gamedata import Data
    import test_match as T

    INIT_EVENTS[:] = [int(x, 16) for x in args.init_events.split(",") if x.strip()]
    if args.trace is not None:
        TRACE.update(slot=args.trace, lines=args.trace_lines)
    cfg = config.load()
    cfg["ics"]["trace_scripts"] = True
    cfg["ics"]["match_waves"]["stagger"] = 0.0
    cfg["ics"]["match_waves"]["first"] = 1.0
    cfg["ics"]["match_pre_start"] = 13.0                   # no intro cinematic here: the short wait
    data = Data(cfg.game_dir)
    if args.fixes:
        args.fix_missile_scripts = args.fix_range_angle = args.fix_raise_event = True
    if args.fix_raise_event:
        patch_raise_event()
    if args.fix_range_angle:
        patch_range_angle()
    if args.fix_missile_scripts:
        patch_entity_scripts(data)
    data.class_scripts = {int(str(k), 0): [int(str(x), 0) for x in v]
                          for k, v in (cfg["ics"].get("spawned_class_scripts") or {}).items()}
    R.SCRIPT_RESOLVER = data.entity_scripts
    # the server's status resolvers (ics/server.py; skill-mechanics-recipes.md 0: without them every status was max 1)
    R.STATUS_RESOLVER, R.STACKS_RESOLVER = data.status_script, data.status_max_stacks
    R.STATUS_STACK_MODEL = bool(cfg["ics"].get("status_stack_model", True))
    R.POLL_ONCE_PER_TICK = bool(cfg["ics"].get("script_poll_once_per_tick", True))
    R.LOCAL_Y_FORWARD = bool(cfg["ics"].get("local_y_forward", True))
    R.RESET_LOCALS = bool(cfg["ics"].get("reset_state_locals", True))
    R.EXIT_REENTRY_GUARD = bool(cfg["ics"].get("exit_chain_reentry_guard", True))
    # 2026-10-28 15:00 (meltdown-moving-target.md 6): the server's flags (ics/server.py)
    R.REAIM_FROM_CURRENT = bool(cfg["ics"].get("missile_reaim_from_current", True))
    R.STATUS_ACTS_FOR_SOURCE = bool(cfg["ics"].get("status_acts_for_source", True))
    R.EVENT_LOOP_PER_TARGET = bool(cfg["ics"].get("event_loop_per_target", True))
    if cfg["ics"].get("graph_cast_timing", True):
        R.GRAPH_EXIT_FALLBACK = float(cfg["ics"].get("graph_exit_fallback", 3.0) or 3.0)
        R.load_graph_hooks(os.path.join(ROOT, "data", "skill_hooks.tsv"))   # the server's graph cast timings
    def flag(opt, key, default):
        return {"on": True, "off": False}.get(opt, bool(cfg["ics"].get(key, default)))
    R.GRAPH_RUNTIME = flag(args.graph_runtime, "graph_runtime", False)
    R.ACCEPT_FILTER = flag(args.accept_filter, "script_accept_filter", True)
    R.GRAPH_START_GRACE = float(cfg["ics"].get("graph_start_grace", 0.15) or 0.0)
    R.GRAPH_COSMETIC_TAIL = bool(cfg["ics"].get("graph_cosmetic_tail", True))
    R.GRAPH_MISSILE_RELEASE = float(cfg["ics"].get("graph_missile_release", 0.5) or 0.0)
    from ics import graph as GR
    GR.CLIP_SECONDS = float(cfg["ics"].get("graph_clip_seconds", 0.5) or 0.5)
    GR.COSMETIC_HOLD = float(cfg["ics"].get("graph_cosmetic_hold", 0.8) or 0.0)
    GR.STATE_TIMEOUT = float(cfg["ics"].get("graph_state_timeout", 5.0) or 0.0)
    GR.SELF_DEBOUNCE = float(cfg["ics"].get("graph_self_debounce", 0.05) or 0.0)
    print(f"graph_runtime {R.GRAPH_RUNTIME}, script_accept_filter {R.ACCEPT_FILTER}")
    time.time = _virtual_time

    variants = []
    for c in data.roster:
        variants.append((c["variant"], c["name"], c))
    if args.all:
        for c in data.roster:
            for ci in c.get("costume_info", []):
                variants.append((ci["variant"], f"{c['name']} ({ci.get('skin', 'costume')})", {**c, **ci}))
    if args.only:
        want = int(args.only, 16)
        variants = [v for v in variants if v[0] == want] or [
            (want, data.champion_name(want)[0], next((c for c in data.roster if c["variant"] == want), {}))]

    VS_BOT["on"] = bool(args.vs_champion)
    VS_BOT["recast"] = float(args.recast or 0.0)
    VS_BOT["press"] = bool(args.press_event)
    VS_BOT["walk"] = bool(args.bot_walk)
    VS_BOT["reset_toggles"] = not args.keep_toggles
    probe = Probe()
    install_hooks(T, R, W, probe)
    results = []
    t0 = time.perf_counter()
    print(f"{'variant':10} {'champion':30} {'S0':>4} {'Q':>4} {'W':>4} {'E':>4} {'R':>4}  notes")
    for variant, name, entry in variants:
        t1 = time.perf_counter()
        try:
            res = check_variant(T, R, V, cfg, data, probe, variant, name, entry, window=args.window)
        except Exception:                                  # noqa: BLE001
            res = {"variant": f"0x{variant:08X}", "name": name, "slots": {},
                   "errors": [traceback.format_exc().strip().splitlines()[-1]]}
            _clock["s"] = None
        res["seconds"] = round(time.perf_counter() - t1, 1)
        results.append(res)
        cols = [verdict(res["slots"].get(str(sl))) for sl in range(5)]
        notes = []
        if res.get("errors"):
            notes.append(res["errors"][0][:60])
        if not res.get("model_pack_ok", True):
            notes.append("model pack missing")
        unk = sorted({u for r in res["slots"].values() if isinstance(r, dict) for u in r.get("unknown", ())})
        if unk:
            notes.append("unknown: " + ", ".join(unk)[:60])
        sq = [str((res["slots"].get(str(sl)) or {}).get("seq") or "-") for sl in range(5)]
        notes.insert(0, "seq " + "/".join(sq))
        print(f"{res['variant']:10} {name[:30]:30} " + " ".join(f"{c:>4}" for c in cols) + "  " + "; ".join(notes),
              flush=True)
        if VS_BOT.get("on"):
            vb = [(res["slots"].get(str(sl)) or {}).get("vs_bot") or {} for sl in range(5)]
            print(f"{'':10} {'  vs bot champion (damage)':30} " + " ".join(f"{int(v.get('damage', 0)):>4}" for v in vb),
                  flush=True)

    totals, seqs = {}, {}
    for res in results:
        for sl in range(5):
            v = verdict(res["slots"].get(str(sl)))
            totals[v] = totals.get(v, 0) + 1
            q = (res["slots"].get(str(sl)) or {}).get("seq")
            if q:
                seqs[q] = seqs.get(q, 0) + 1
    print(f"\n{len(results)} variants in {time.perf_counter() - t0:.0f} s; slot verdicts: " +
          ", ".join(f"{k} {v}" for k, v in sorted(totals.items())))
    print("sequence verdicts: " + ", ".join(f"{k} {v}" for k, v in sorted(seqs.items())))
    print("DMG = damage dealt, CHMP = damage only on an enemy champion (dummy), BUFF = the next basic attack hits harder, FX = status / missile / spawn / move / heal, anim = only scriptlets / cooldown / Will,"
          " TGT = nothing until cast with target + point, NONE = no effect, REF = refused, EXC = exception")
    out = args.out or os.path.join(tempfile.gettempdir(), "champion_check.json")
    with open(out, "w", encoding="utf-8") as f:
        json.dump({"encounter": f"0x{ENCOUNTER:08X}", "graph_runtime": R.GRAPH_RUNTIME,
                   "accept_filter": R.ACCEPT_FILTER, "totals": totals, "sequences": seqs, "results": results}, f, indent=1)
    print("summary:", out)
    time.time = _real_time
    return 0


if __name__ == "__main__":
    sys.exit(main())
