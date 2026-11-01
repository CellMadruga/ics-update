"""Script VM check (python tests/test_scriptvm.py): the new server's runtime (ics/script_runtime.py, ics/script_nodes.py,
ics/combat.py) on the original server scripts.

  - VM semantics of the client (docs/re-notes/full-combat-skills.md 5.1-5.3) on small hand-built trees;
  - the attribute stacking formula 0x96D460, CanActivate, the relation masks, the damage pipeline;
  - champions' skills end to end (cast -> damage / statuses / modifiers -> the messages a match would send):
    Gaslight Batman Q / E / R / basic attack, Wonder Woman's basic attack, Green Lantern W, Atomic Poison Ivy Q,
    the stun and silence statuses.

Needs the decoded trees (python tools\\script_decoder.py all); skipped without them.
Simulated with NullWorld: Batman (team 1) at the origin, a drone 8 m ahead and a second drone 3.6 m from it (team 2).
"""
import csv
import os
import struct
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from ics import combat as CB, script_model as V, script_runtime as R  # noqa: E402

CHECKS = []


def check(name, ok, detail=""):
    CHECKS.append((name, bool(ok)))
    print(("ok   " if ok else "FAIL ") + name + (f"  ({detail})" if detail and not ok else ""))


# ---- hand-built trees ------------------------------------------------------------------------------------

def const(value, typ=3, via="0x460502"):
    raw = struct.unpack("<I", struct.pack("<f", value))[0] if typ == 3 else value
    return {"type": "builtin:0x2", "vt": "0x15A8F18", "via": via, "fields": [[0, 4, "0x456CF3", typ],
                                                                              [4, 4, "0x443C7D", raw]],
            "children": []}


def var(h, via="0x460502"):
    return {"type": "builtin:0x3", "vt": "0x15A9D38", "via": via,
            "fields": [[0, 4, "0x453173", h], [4, 4, "0x453185", 3], [8, 4, "0x453197", 0]], "children": []}


def expr(vt, *kids, flag=None):
    roles = ("0x469EF9", "0x469F46") if len(kids) == 2 else (("0x469E59",) if len(kids) == 1 else
                                                             ("0x469FF9", "0x46A046", "0x46A093"))
    children = [dict(k, via=r) for k, r in zip(kids, roles)]
    fields = [[0, 4, r, 3] for r in roles]
    if flag is not None:
        fields.append([0, 1, "0x46A1F9", flag])
    return {"type": "expr", "vt": vt, "via": "0x460502", "fields": fields, "children": children}


def node(raw):
    return V.Node(raw)


def vm_checks():
    w = R.NullWorld(log=lambda t: None)
    script = V.Script({"id": "0x34FFFFFF", "type": "script", "fields": [], "children": []})
    inst = R.Instance(script, "Batman", w)
    ev = inst.evaluate
    check("expression 0xC is x - 1 (not a division)", ev(node(expr("0x15A9408", const(5, 1)))) == 4)
    check("expression 0x10 is a short-circuit or", ev(node(expr("0x15A92B8", const(1, 0), const(0, 0)))) is not False)
    check("expression 0x27 Select is lazy (c ? a : b)",
          ev(node(expr("0x15A9BB0", const(0, 0), const(1.0), const(2.0)))) == 2.0)
    check("expression 0x1E clamp(x, lo, hi)", ev(node(expr("0x15A9130", const(9.0), const(0.0), const(5.0)))) == 5.0)
    check("expression 0x24 !a is false for a non-bool", ev(node(expr("0x15A9328", const(1.5)))) is False)
    f = R.Frame((1.0, 2.0, 0.0), 90.0)
    inst.vars[0x1234] = f
    check("expression 0x40 Heading(frame) in degrees", abs(ev(node(expr("0x15A9C90", var(0x1234), flag=1))) - 90.0) < 1e-6)
    fwd = ev(node(expr("0x15A9D00", var(0x1234))))
    check("expression 0x45 Forward(frame)", abs(fwd[0]) < 1e-6 and abs(fwd[1] - 1.0) < 1e-6, str(fwd))
    dbl = {"type": "builtin:0x2", "vt": "0x15A8F18", "via": "0x460502",
           "fields": [[0, 4, "0x456CF3", 7], [4, 8, "0x443C7D", struct.pack("<d", -1.0).decode("latin1")]],
           "children": []}
    check("an 8-byte double constant (-1.0, a stopped timer)", ev(node(dbl)) == -1.0)
    # timers (5.1): a timer never started counts as expired, -1 never expires
    tnode = node({"type": "builtin:0x8", "vt": "0x15A8820", "via": "0x46001A",
                  "fields": [[0, 4, "0x453173", 0x777], [4, 4, "0x453185", 3], [8, 4, "0x453197", 0]], "children": []})
    check("TimerExpired: a timer never started is expired", inst.condition(tnode) is True)
    inst.vars[0x777] = -1.0
    check("TimerExpired: -1 (stopped) never expires", inst.condition(tnode) is False)
    inst.vars[0x777] = ("timer", w.time + 5.0)
    check("TimerExpired: a running timer is not expired", inst.condition(tnode) is False)
    # PostEventDelayed (builtin 0x12) and IsEventPending (builtin 0x04)
    inst.post(0x10000120, 1.0)
    pend = node({"type": "builtin:0x4", "vt": "0x15A87C4", "via": "0x46001A",
                 "fields": [[0, 4, "0x45BEC9", 0x10000120], [4, 1, "0x45BEDB", 1], [5, 1, "0x45BF04", 1]],
                 "children": []})
    check("PostEventDelayed: the event is pending", inst.condition(pend) is True)
    w.run_until(1.5)
    check("PostEventDelayed: delivered after the delay", inst.condition(pend) is False)
    # an action used as a condition runs and gives true (5.1)
    assign = node({"type": "builtin:0x1", "vt": "0x15A89C0", "via": "0x46001A",
                   "fields": [[0, 4, "0x45FE89", 0], [4, 4, "0x453173", 0x888], [8, 4, "0x453185", 3],
                              [12, 4, "0x453197", 0], [16, 4, "0x460502", 2]],
                   "children": [const(3.0)]})
    check("an action in a condition list runs and is true", R.run_condition(inst, assign) is True
          and inst.vars.get(0x888) == 3.0)


# ---- combat formulas -------------------------------------------------------------------------------------

def combat_checks():
    M = CB.Modifier
    mods = [M(None, "a", 1, 9, 20.0), M(None, "a", 1, 10, 0.5), M(None, "b", 1, 10, 0.5), M(None, "a", 1, 9, 10.0)]
    v = CB.evaluate_modifiers(CB.KIND_F32, 100.0, mods)
    check("modifiers: flat adds, then percents (one source adds, two sources multiply)", abs(v - 130 * 1.5 * 1.5) < 1e-6,
          str(v))
    v = CB.evaluate_modifiers(CB.KIND_F32, 100.0, [M(None, "a", 1, 7, 30.0), M(None, "a", 1, 5, 7.0)])
    check("modifiers: op 7 subtracts, op 5 sets last", v == 7.0, str(v))
    v = CB.evaluate_modifiers(CB.KIND_BOOL, False, [M(None, "a", 1, 6, True)])
    check("modifiers: a CC flag set by op 6", v is True)
    v = CB.evaluate_modifiers(CB.KIND_INT, 10, [M(None, "a", 1, 10, 0.25)])
    check("modifiers: int attributes round half up", v == 13.0, str(v))
    check("relation masks: 2 enemy, 4 ally / self, 1 neutral",
          CB.relation(1, 2) == 2 and CB.relation(1, 1) == 4 and CB.relation(0, 2) == 1 and CB.relation(-1, 1) == 2)

    w = R.NullWorld(log=lambda t: None)
    c = w.combat
    h = c.add_modifier("Drone", CB.ATTR_STUNNED, 6, True, source="Batman")
    check("CanActivate: stunned -> Skill_Stunned", c.can_activate("Drone", 1) == CB.ERR_STUNNED)
    check("crowd control stops movement", not c.can_move("Drone"))
    c.remove_modifier("Drone", h)
    check("CanActivate: ok after the stun", c.can_activate("Drone", 1) == 0)
    c.add_modifier("Drone", CB.ATTR_SILENCED, 6, True)
    check("CanActivate: silenced -> Skill_Silenced (not the basic attack)",
          c.can_activate("Drone", 2) == CB.ERR_SILENCED and c.can_activate("Drone", 0) == 0)
    c.set_cooldown("Batman", 3, 5.0)
    check("CanActivate: cooldown -> Skill_InCooldown", c.can_activate("Batman", 3, now=1.0) == CB.ERR_COOLDOWN)
    check("CanActivate: not enough Will -> Skill_NoResources",
          c.can_activate("Batman", 2, cost=-50, resource=10.0) == CB.ERR_NO_RESOURCES)
    check("a cooldown is reported to the world (0x20F8 hook)", any(k == "cooldown" for k, _ in w.sent))

    # damage pipeline (2 A.5): armor, crit, shields, lifesteal
    from ics import script_nodes as N
    w = R.NullWorld(log=lambda t: None)
    w.combat.add_modifier("Drone", CB.ATTR_ATTACK_ARMOR, 9, 100.0)
    N.deal_damage(w, "Batman", "Drone", 100.0, 1)
    check("damage: 100 armor halves attack damage", w.health["Drone"] == 250.0, str(w.health["Drone"]))
    N.deal_damage(w, "Batman", "Drone", 50.0, 3)
    check("damage: true damage ignores armor", w.health["Drone"] == 200.0, str(w.health["Drone"]))
    w.combat.add_modifier("Batman", CB.ATTR_CRIT_DAMAGE, 0, 2.0)
    N.deal_damage(w, "Batman", "Drone", 20.0, 3, crit=True)
    check("damage: a critical hit doubles", w.health["Drone"] == 160.0, str(w.health["Drone"]))
    w.combat.of("Drone").shields[CB.Handle("shield", "Drone")] = [2, 30.0, 30.0, None]
    N.deal_damage(w, "Batman", "Drone", 50.0, 3)
    check("damage: a shield absorbs first", w.health["Drone"] == 140.0 and w.combat.shield_total("Drone") == 0,
          str(w.health["Drone"]))
    w.health["Batman"] = 500.0
    w.combat.add_modifier("Batman", CB.ATTR_ATTACK_LIFESTEAL, 9, 0.1)
    N.deal_damage(w, "Batman", "Drone2", 100.0, 1)
    check("damage: lifesteal heals the source", w.health["Batman"] == 510.0, str(w.health["Batman"]))


# ---- skills end to end -----------------------------------------------------------------------------------

def kit(rows, prefix):
    from ics.gamedata import Skill
    return {int(r["slot"]): Skill(r) for r in rows if r["id"].split(":")[0] == prefix}


def run_skill(rows, prefix, slot, target="Drone", point=(8.0, 0.0, 0.0), until=4.0, setup=None):
    lines = []
    w = R.NullWorld(log=lines.append)
    w.kit, w.slot = kit(rows, prefix), slot
    if setup:
        setup(w)
    sk = w.kit[slot]
    inst = R.start_script(V.load(sk.script), "Batman", w, slot=slot)
    w.run_until(0.2)
    R.activate(inst, target, point)
    w.run_until(until)
    unknown = set().union(*[i.unknown for lst in w.scripts.values() for i in lst] or [set()]) | inst.unknown
    for m in w.missiles:
        for i in m.instances:
            unknown |= i.unknown
    return w, "\n".join(lines), unknown


def skill_checks(data):
    rows = [r for r in csv.DictReader(open(os.path.join(ROOT, "catalog", "data", "skills.tsv"), encoding="utf-8"),
                                      delimiter="\t") if r["script"]]
    sent = lambda w, kind: [d for k, d in w.sent if k == kind]          # noqa: E731

    w, text, unknown = run_skill(rows, "0x48000615", 1)                  # Gaslight Batman Q: Sonic Batarang
    check("Batman Q: aimed at a point, hits the drone on the way (stat 5 = 60)", w.health["Drone"] == 240.0)
    check("Batman Q: cooldown on slot 1 = stat 15 (5 s)", any(d["slot"] == 1 for d in sent(w, "cooldown")))
    check("Batman Q: no unknown node", not unknown, str(unknown))

    w, text, unknown = run_skill(rows, "0x48000615", 3)                  # E: Bat Flight (a dash)
    check("Batman E: dashes to the point (forced movement)", sent(w, "move") and w.entities["Batman"][0] > 7.0)
    # 2026-10-25 (kit-audit-3.md 1): HasFlagAttribute 0x1000006A is a predicate; Bat Flight marks its target with
    # 0x100003AB after the hit, so the first hit is the plain 40 (the echo x1.1 needs an earlier mark; the old 256
    # came from the predicate running as an action, always true)
    check("Batman E: hits the drone it touches (40, no echo mark yet)",
          abs(w.health["Drone"] - 260.0) < 0.01, str(w.health["Drone"]))
    check("Batman E: no unknown node", not unknown, str(unknown))

    w, text, unknown = run_skill(rows, "0x48000615", 4)                  # R: Bat Scream
    check("Batman R: the scream's missile does stat 5 (225)", w.health["Drone"] == 75.0, str(w.health["Drone"]))

    w, text, unknown = run_skill(rows, "0x48000615", 0)                  # basic attack
    check("Batman basic attack: shot tracked by its status, damage on arrival", w.health["Drone"] < 300.0)

    w, text, unknown = run_skill(rows, "0x48000615", 5)                  # passive: Echoes
    check("Batman passive: runs with no unknown node", not unknown, str(unknown))

    w, text, unknown = run_skill(rows, "0x48000624", 0)                  # Wonder Woman's basic attack
    check("Wonder Woman basic attack: stats loaded by the re-init event, then damage", w.health["Drone"] < 300.0)

    w, text, unknown = run_skill(rows, "0x4800062E", 2)                  # Green Lantern W: Constrict
    mods = [d for d in sent(w, "modifier") if d["attr"] == f"{CB.ATTR_MOVE_SPEED:#x}"]
    check("Green Lantern W: the homing missile slows (move speed op 10 -0.7)", mods and mods[0]["value"] == -0.7)
    check("Green Lantern W: the root's damage over time (stat 5 = 50 in 1 s)", w.health["Drone"] == 250.0,
          str(w.health["Drone"]))
    check("Green Lantern W: the slow ends with its status (modifier removed, icon removed)",
          sent(w, "modifier removed") and sent(w, "icon_remove"))

    def near(w):
        w.entities["Drone"] = (2.0, 0.0, 0.0)
    w, text, unknown = run_skill(rows, "0x48000883", 1, target=None, point=None, setup=near)   # Atomic Poison Ivy Q
    check("Poison Ivy Q (no Cast node): the instant cast reaches its effect state", w.health["Drone"] == 260.0,
          str(w.health["Drone"]))
    check("Poison Ivy Q: the mark status (no script) exists", w.statuses.get("Drone", {}).get(0x480008AC))

    # crowd control: the game's own stun status (0x48000293 -> script 0x34000130)
    w = R.NullWorld(log=lambda t: None)
    R.apply_status(w, "Batman", "Drone", 0x48000293, {"EffectDuration": 1.5})
    w.run_until(0.5)
    st = w.combat.of("Drone")
    check("stun: Stunned modifier (0x20F0) + action lock (DisableActions 77)",
          w.combat.flag("Drone", CB.ATTR_STUNNED) and any(v[0] == 77 for v in st.locks.values()))
    check("stun: status icon added", sent(w, "icon_add"))
    w.run_until(2.0)
    check("stun: everything undone when it ends (modifier, lock, icon)",
          not w.combat.stunned("Drone") and sent(w, "modifier removed") and sent(w, "icon_remove"))

    # silence as a status script: the skill disable condition on every slot
    w = R.NullWorld(log=lambda t: None)
    inst = R.Instance(V.load(0x340001C1), "Batman", w)
    inst.status = 0x48FFFFFF
    R.statuses_on(w, "Batman").setdefault(0x48FFFFFF, []).append(inst)
    R.scripts_on(w, "Batman").append(inst)
    inst.start()
    inst.event(R.EVENT_STATUS_APPLIED, {"EffectDuration": 1.0, "EffectSource": "Drone"})
    conds = sent(w, "disable_condition")
    check("silence: disable condition Skill_Silenced on every slot (0x20A0)",
          conds and conds[0]["error"] == CB.ERR_SILENCED and conds[0]["slot"] == -2 and conds[0]["add"])
    check("silence: CanActivate refuses Q", w.combat.can_activate("Batman", 1) == CB.ERR_SILENCED)
    w.run_until(1.5)
    R.remove_status(w, "Batman", 0x48FFFFFF, inst, True)
    check("silence: the condition is removed with the status", len(sent(w, "disable_condition")) >= 2
          and not w.combat.of("Batman").conditions)


# ---- Meltdown's runtime rules (docs/re-notes/meltdown-moving-target.md 6) -----------------------------------

def _nodes(script, type_id):
    """Every node of a type in a script (states' chains, nested states)."""
    out = []

    def walk(n):
        if n.type_id == type_id:
            out.append(n)
        for c in n.children:
            walk(c)

    def wstate(st):
        for ch in st.chains:
            walk(ch)
        for c in st.states:
            wstate(c)
    for g in script.graphs:
        wstate(g)
    return out


def meltdown_checks():
    """2026-10-28 15:00 (tester report 2026-10-28 15:00: AGL's R must slow and keep hitting a moving target): the rules
    behind it on NullWorld, with Batman as the applier and Drone as the status' owner (Drone2, his ally, 3.6 m away)."""
    from ics import script_nodes as S
    h = V.elf_hash

    def arrival(reaim):
        # Meltdown's missile 0x340002BE sets its speed every 0.3 s (4 -> 15 m/s over 5 s), each time re-aimed
        R.REAIM_FROM_CURRENT = reaim
        w = R.NullWorld(log=lambda t: None)
        m = w.launch_missile("Batman", 0x40000484, "Drone", 4.0, 0.0, [])
        for k in range(1, 17):
            w.after(0.3 * k, lambda k=k: m.set_speed(4.0 + 11.0 * min(1.0, 0.3 * k / 5.0)))
        t = 0.0
        while m.alive and t < 9.0:
            t += 0.05
            w.run_until(t)
        return t
    try:
        fixed, old = arrival(True), arrival(False)
    finally:
        R.REAIM_FROM_CURRENT = True
    check("a missile re-aimed every 0.3 s flies on from where it is (8 m in about 1.5 s)", fixed <= 1.8, fixed)
    check("missile_reaim_from_current off: each re-aim restarted from the launch point (late)", old >= 4.5, old)

    md = V.load(0x340002BF)                            # Meltdown's status script (status 0x480007AF)
    w = R.NullWorld(log=lambda t: None)
    inst = R.Instance(md, "Drone", w)
    inst.status, inst.effect_source, inst.status_slot = 0x480007AF, "Batman", 4
    check("a status acts for its applier (acting_entity)", R.acting_entity(inst) == "Batman")
    own = R.Instance(md, "Drone", w)
    own.status, own.effect_source = 0x480007AF, "Drone"
    check("a status its owner applied acts for its owner", R.acting_entity(own) == "Drone")
    ft = next(n for n in _nodes(md, 0x10000047) if n.operands and n.operands[0].value == h("PulseRange"))
    inst.vars[h("PulseRange")] = 5.0
    S._find_targets(inst, ft, ft.operands, None)
    found = list(inst.detected)
    R.STATUS_ACTS_FOR_SOURCE = False
    try:
        off = R.acting_entity(inst)
        S._find_targets(inst, ft, ft.operands, None)
        found_off = list(inst.detected)
    finally:
        R.STATUS_ACTS_FOR_SOURCE = True
    check("a status' FindTargets (relation 3) takes the applier's side: the owner's ally, not SELF",
          found == ["Drone2"], found)
    check("status_acts_for_source off: the owner's side again", off == "Drone" and found_off == [], (off, found_off))

    hits, raised = [], []
    w.damage = lambda src, tgt, amount: hits.append((src, tgt, amount))
    orig_raise = R.raise_event

    def raise_event(world, ent, ev, params=None):
        if ev == 0x1000008A:
            raised.append((ent, dict(params or {})))
        return orig_raise(world, ent, ev, params)
    R.raise_event = raise_event
    try:
        ad = next(n for n in _nodes(md, 0x1000001D) if len(n.operands) > 1 and n.operands[1].is_self())
        inst.vars[h("Damage")] = 30.0
        S._apply_damage(inst, ad, ad.operands, None)
        now = list(raised)
        w.run_until(w.time + 0.05)
    finally:
        R.raise_event = orig_raise
    check("a status' ApplyDamage with no source is its applier's", hits and hits[0][0] == "Batman" and hits[0][1] == "Drone",
          hits)
    check("its skill hit 0x1000008A goes to the applier after the chain (queued), with the skill slot",
          not now and raised == [("Batman", {"TargetIID": "Drone", 0x31D944: 4})], (now, raised))

    lm = next(n for n in _nodes(md, 0x1000005E) if n.values and n.values[0] == 0x40000484)
    inst.vars[h("BestJumpTarget")], inst.vars[h("MissileVelocity")] = "Drone2", 4.0
    m = S._launch(inst, lm, lm.operands)
    check("a new missile a status launches is its applier's, from the status' owner (Meltdown's jump)",
          m is not None and m.owner == "Batman" and m.origin == "Drone" and tuple(m.pos[:2]) == (8.0, 0.0),
          m and (m.owner, m.origin, m.pos))
    ku = V.load(0x340003E7)                            # a knock-up status launches SELF (skeptic review 4)
    k = R.Instance(ku, "Drone", w)
    k.status, k.effect_source = 0x480009FC, "Batman"
    ll = next(n for n in _nodes(ku, 0x10000154) if n.operands and n.operands[0].is_self())
    k.vars[ll.operands[1].value] = (12.0, 0.0, 0.0)
    m2 = S._launch(k, ll, ll.operands, "lobbed")
    check("a status that launches its own owner (knock-up 0x340003E7) keeps it as the shooter",
          m2 is not None and m2.owner == "Drone" and m2.carried == "Drone" and m2.origin is None,
          m2 and (m2.owner, m2.carried, m2.origin))

    def self_remove(after_chain):
        # RemoveStatus(-, -, -, -)[0 0 0] then x = 7
        ops = [f for _ in range(4) for f in ([0, 4, "0x453173", 0], [4, 4, "0x453185", 0xFFFFFFFF],
                                             [8, 4, "0x453197", 0])]
        assign = {"type": "builtin:0x1", "vt": "0x15A89C0", "via": "0x45FE89",
                  "fields": [[0, 4, "0x45FE89", 0], [4, 4, "0x453173", 0x999], [8, 4, "0x453185", 3],
                             [12, 4, "0x453197", 0], [16, 4, "0x460502", 2]], "children": [const(7.0)]}
        rm = node({"type": "0x10000018", "vt": "0x0", "via": "0x44EE99",
                   "fields": [[0, 4, "0x45FE89", 1]] + ops + [[0, 4, "0x999999", 0]] * 3, "children": [assign]})
        ww = R.NullWorld(log=lambda t: None)
        ww.ic = {"status_self_remove_after_chain": after_chain}
        st = R.Instance(V.Script({"id": "0x34FFFFFE", "type": "script", "fields": [], "children": []}), "Drone", ww)
        st.status = 0x48FFFFF0
        R.statuses_on(ww, "Drone").setdefault(0x48FFFFF0, []).append(st)
        R.scripts_on(ww, "Drone").append(st)
        R.run_nodes(st, rm, None)
        ran, gone_at_once = st.vars.get(0x999) == 7.0, st.removed
        ww.run_until(0.05)
        return ran, gone_at_once, st.removed and not R.statuses_on(ww, "Drone").get(0x48FFFFF0)
    ran, at_once, gone = self_remove(True)
    check("a status that removes itself runs the rest of its chain, then goes (Meltdown's jump: 6 pulses)",
          ran and not at_once and gone, (ran, at_once, gone))
    ran, at_once, gone = self_remove(False)
    check("status_self_remove_after_chain off: it stops at once", not ran and at_once and gone, (ran, at_once, gone))

    lines = []
    w2 = R.NullWorld(log=lines.append)
    g = R.Instance(V.Script({"id": "0x34FFFFFD", "type": "script", "fields": [], "children": []}), "Batman", w2)
    for i in range(6):
        g.event(0x1000008A, {"TargetIID": f"Unit{i}"})
    per_target = not any("loop cut" in ln for ln in lines)
    for _ in range(6):
        g.event(0x1000008A, {"TargetIID": "Unit0"})
    check("the event loop guard counts per target (6 units hit at once: no cut) and still cuts a loop on one",
          per_target and any("loop cut" in ln for ln in lines), lines)


def main():
    try:
        q = V.load(0x3400003B)
        V.load(0x3400003F)
    except OSError:
        print("skipped: no data/script_trees (python tools\\script_decoder.py all)")
        return 0
    from ics import config
    from ics.gamedata import Data
    data = Data(config.load().game_dir)        # statuses and missile classes name their scripts in the packs
    R.SCRIPT_RESOLVER, R.STATUS_RESOLVER, R.STACKS_RESOLVER = data.entity_scripts, data.status_script, data.status_max_stacks
    R.RECORD_RESOLVER = lambda did, prop: CB.record_value(data, did, prop)
    R.FLAGS_RESOLVER = lambda did: CB.status_flags(data, did)
    vm_checks()
    combat_checks()

    lines = []
    w = R.NullWorld(log=lines.append)
    inst = R.use_skill(q, "Batman", w, target="Drone")
    w.run_until(5.0)
    text = "\n".join(lines)
    check("Sonic Batarang: faces the target", "face Drone" in text)
    check("Sonic Batarang: plays the cast scriptlet 0x10000164", "scriptlet 0x10000164 on Batman" in text)
    check("Sonic Batarang: cooldown = stat 15 (5 s)", "cooldown 5 s" in text)
    check("Sonic Batarang: first hit stat 5 at rank 1 (60)", "damage 60 to Drone " in text)
    check("Sonic Batarang: ricochet to the nearest other drone", "missile -> Drone2" in text)
    # 2026-10-22: the second hit is 80 % (SkillPerHitDiminish_Base 0.2, a default the decoder now reads right)
    check("Sonic Batarang: second hit (x 0.8 falloff)", "damage 48 to Drone2" in text)
    check("Sonic Batarang: missile ends after MaxCollisions", "missile 0x40000090 gone" in text)
    check("Sonic Batarang: skill graph back to idle", inst.regions[1].state == 0)
    lines.clear()
    w = R.NullWorld(log=lines.append)
    R.use_skill(V.load(0x34000037), "Batman", w, target="Drone")
    w.run_until(3.0)
    text = "\n".join(lines)
    # no critical hits (no crit chance): the normal wind-up / shot (left or right), not the critical 0x100000b8 / 0x1000017e
    check("basic attack: wind-up scriptlet (0x10000195 / 0x10000196)",
          "scriptlet 0x10000195 on Batman" in text or "scriptlet 0x10000196 on Batman" in text)
    check("basic attack: the shot at the cast point (0x10000188 / 0x10000189)",
          "[  0.25]   scriptlet 0x10000188" in text or "[  0.25]   scriptlet 0x10000189" in text)
    check("basic attack: shot tracked by status 0x48000ab0 (script 0x34000470)", "0x34000470 enter S1" in text)
    check("basic attack: damage when the shot arrives (event 0x10000126)", "damage 60 to Drone" in text)
    check("basic attack: hit reaction status 0x48000286 on the target", "0x34000128 enter" in text)

    skill_checks(data)
    meltdown_checks()
    bad = [name for name, ok in CHECKS if not ok]
    print(f"{len(CHECKS) - len(bad)}/{len(CHECKS)} script VM checks")
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main())
