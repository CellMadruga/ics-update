"""The server-side behaviour-graph runtime (ics/graph.py, docs/re-notes/skill-execution-model.md 6).

Needs data/skill_graphs.json (python tools/skill_graphs.py) and data/script_trees.

    python tests\\test_graph.py
"""
import contextlib
import heapq
import io
import itertools
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
from ics import graph as G                                      # noqa: E402
from ics import script_model as V                               # noqa: E402
from ics import script_runtime as R                             # noqa: E402
import ics.script_nodes                                         # noqa: E402,F401  (registers the nodes)

ZOD, KATANA, GASLIGHT, AGL = 0x40000D29, 0x40000BA6, 0x40000086, 0x4000047D
ZOD_R, THOUSAND_CUTS, BATFLIGHT, BAT_SCREAM, GRAB = 0x3400074B, 0x340005B6, 0x34000038, 0x34000039, 0x340002B5

passed = failed = 0


def check(name, ok, detail=""):
    global passed, failed
    if ok:
        passed += 1
        print(f"ok   {name}")
    else:
        failed += 1
        print(f"FAIL {name} {detail}")


class Clock:
    def __init__(self):
        self.t, self.q, self.n = 0.0, [], itertools.count()

    def after(self, d, fn):
        heapq.heappush(self.q, (self.t + d, next(self.n), fn))

    def run(self, until):
        while self.q and self.q[0][0] <= until + 1e-9:
            t, _, fn = heapq.heappop(self.q)
            self.t = t
            fn()
        self.t = until


def make(variant, aps=1.0):
    c = Clock()
    got = []
    g = G.data().for_variant(variant)
    gi = G.GraphInstance(g, c.after, lambda: c.t, lambda code, did, off, st: got.append((round(c.t, 3), code, did)),
                         speed=lambda: aps)
    return c, gi, got


def ev(gi, name):
    return gi.g.events[name]


def codes(got, did=None):
    return [(t, c) for t, c, d in got if did is None or d in (did, 0)]


def test_data():
    d = G.data()
    check("skill_graphs.json: champion variants", len(d) >= 150, len(d))
    g = d.for_variant(ZOD)
    check("Zod graph hooks Kneel Before Zod", g is not None and ZOD_R in g.hooked)
    gb = d.for_variant(GASLIGHT)
    check("Gaslight Batman: scriptlet keys raise graph events (Combat_Basic_Attack_Left -> Basic_Attack_Left)",
          gb is not None and gb.events.get("Basic_Attack_Left") in gb.key_events.get(0x10000196, ()))


def test_zod_r():
    c, gi, got = make(ZOD)
    gi.raise_id(ev(gi, "Wildcard_RSkill"))
    check("Zod R: code 1 at the start", codes(got, ZOD_R) == [(0.0, 1)], got)
    c.run(3.0)
    check("Zod R: nothing during the channel (no code 2 mid-channel)", codes(got, ZOD_R) == [(0.0, 1)], got)
    gi.raise_id(ev(gi, "Wildcard_SkillR_Secondary"))
    c.run(4.5)
    check("Zod R: nothing during the jump", codes(got, ZOD_R) == [(0.0, 1)], got)
    gi.raise_id(ev(gi, "Zod_Kneel_End"))
    c.run(6.0)
    seq = codes(got, ZOD_R)
    check("Zod R: landing code 3 at +0.200 then one code 2 at +0.356",
          seq == [(0.0, 1), (4.7, 3), (4.856, 2)], seq)
    check("Zod R: back in locomotion", "Locomotion" in gi.state_names(), gi.state_names())


def test_zod_r_script():
    """The real script 0x3400074B on a NullWorld owner with Zod's graph: the channel is not cut, the second stage
    (jump -> landing damage state S3 / S4) runs and code 2 comes only at the end."""
    R.GRAPH_RUNTIME = True
    try:
        lines = []
        w = R.NullWorld(log=lines.append)
        got = []
        gdef = G.data().for_variant(ZOD)
        gi = G.GraphInstance(gdef, w.after, w.now,
                             lambda code, did, off, st: (got.append((round(w.time, 3), code, did)),
                                                         R.deliver_hook(w, "Batman", code, did, off, st)))
        w.graphs = {"Batman": gi}
        with contextlib.redirect_stdout(io.StringIO()):
            inst = R.use_skill(V.load(ZOD_R), "Batman", w, point=(5.0, 0.0, 0.0))
            w.run_until(12.0)
        seq = [(t, cd) for t, cd, d in got if d in (ZOD_R, 0)]
        entered = [ln for ln in lines if f"{ZOD_R:#x} enter S" in ln]
        states = [int(ln.rsplit("enter S", 1)[1]) for ln in entered]
        check("Zod R script: second stage (S5 jump, then S3 landing) runs", 5 in states and 3 in states, entered)
        first2 = next((t for t, cd in seq if cd == 2), None)
        first3 = next((t for t, cd in seq if cd == 3), None)
        check("Zod R script: code 2 only after the landing's code 3", first2 is not None and first3 is not None
              and first2 >= first3, seq)
        check("Zod R script: one code 2", sum(1 for _t, cd in seq if cd == 2) == 1, seq)
        check("Zod R script: not casting at the end", not inst.casting, inst.casting)
    finally:
        R.GRAPH_RUNTIME = False


def test_thousand_cuts():
    c, gi, got = make(KATANA)
    gi.raise_id(ev(gi, "Katana_Thousand_Cuts_Start"))
    c.run(1.0)
    seq = codes(got, THOUSAND_CUTS)
    check("Thousand Cuts: start stage 1 then its (estimated) code 3", [cd for _t, cd in seq] == [1, 3], seq)
    gi.raise_id(ev(gi, "Katana_Thousand_Cuts_1"))
    seq = codes(got, THOUSAND_CUTS)
    check("Thousand Cuts: next stage = previous exit 2 then enter 1, same instant",
          [cd for _t, cd in seq[-2:]] == [2, 1] and seq[-1][0] == seq[-2][0] == 1.0, seq)
    c.run(2.0)
    seq = codes(got, THOUSAND_CUTS)
    check("Thousand Cuts: stage 1 code 3 at 0.25 / 1.5 s", (round(1.0 + 0.25 / 1.5, 3), 3) in seq, seq)
    for k in range(2, 6):
        gi.raise_id(ev(gi, f"Katana_Thousand_Cuts_{k}"))
        c.run(2.0 + k)
    seq = codes(got, THOUSAND_CUTS)
    check("Thousand Cuts: six stages, six code 3", sum(1 for _t, cd in seq if cd == 3) == 6, seq)
    check("Thousand Cuts: still in the last stage until the script ends it", gi.in_state_of(THOUSAND_CUTS))
    gi.raise_id(ev(gi, "skill_to_locomotion"))
    check("Thousand Cuts: skill_to_locomotion -> code 2", codes(got, THOUSAND_CUTS)[-1][1] == 2)


def test_basic_attack_speed():
    times = []
    for aps in (1.0, 2.0):
        c, gi, got = make(GASLIGHT, aps)
        gi.scriptlet(0x10000196)                       # Combat_Basic_Attack_Left -> Basic_Attack_Left
        c.run(2.0)
        t5 = [t for t, cd, d in got if cd == 5]
        times.append(t5[0] if t5 else None)
        check(f"basic attack at {aps} attacks/s: codes 1, 5 and 2", {1, 5, 2} <= {cd for _t, cd, _d in got}, got)
    check("basic attack: code 5 twice as early at twice the attack speed",
          None not in times and abs(times[0] - 2 * times[1]) < 0.01, times)


def test_batflight():
    c, gi, got = make(GASLIGHT)
    gi.raise_id(ev(gi, "Batman_Gaslight_Batflight"))
    c.run(3.0)
    seq = codes(got, BATFLIGHT)
    check("Batflight: 1, 3, Recover's 1, then 2", [cd for _t, cd in seq] == [1, 3, 1, 2], seq)
    t3 = next(t for t, cd in seq if cd == 3)
    t2 = seq[-1][0]
    clip = next(st for m in gi.g.machines for st in m["states"].values() if st["name"] == "Batflight_Attack")["body"]["clips"][0]
    want = (0.3256 - clip["start"]) / clip["speed"]
    check("Batflight: code 3 at its trigger time (local 0.3256 from the clip start, x 0.85)", abs(t3 - want) < 0.002,
          (t3, want))
    check("Batflight: code 2 at the Recover's skill_to_locomotion (well before the old 3 s fallback)",
          0.7 < t2 < 1.6, t2)


def test_grab():
    c, gi, got = make(AGL)
    gi.raise_id(ev(gi, "AtomicGreenLantern_Grab_Start"))
    c.run(3.0)
    seq = codes(got, GRAB)
    check("Grab: code 1 then code 5 at 0.14 s, no code 2 while the arm is out",
          seq == [(0.0, 1), (0.14, 5)], seq)
    gi.raise_id(ev(gi, "AtomicGreenLantern_Grab_Hit"))
    c.run(4.0)
    check("Grab: Grab_Hit (missile S9) ends the loop, still no code 2", codes(got, GRAB) == [(0.0, 1), (0.14, 5)],
          codes(got, GRAB))
    check("Grab: graph in Grab_End", "Grab_End" in gi.state_names(), gi.state_names())
    gi.raise_id(ev(gi, "skill_to_locomotion"))
    check("Grab: the script's skill_to_locomotion -> code 2", codes(got, GRAB)[-1] == (4.0, 2), codes(got, GRAB))


def test_stun_mid_cast():
    c, gi, got = make(GASLIGHT)
    gi.raise_id(ev(gi, "Batman_Gaslight_Bat_Scream"))
    c.run(0.4)
    gi.raise_id(ev(gi, "CbtState_KnockUp"))
    c.run(2.0)
    seq = codes(got, BAT_SCREAM)
    check("stun mid Bat Scream: code 2 at the stun, no code 5 after", seq == [(0.0, 1), (0.4, 2)], seq)
    check("stun mid Bat Scream: graph in the KnockUp state", any("Knock" in n for n in gi.state_names()),
          gi.state_names())


def test_new_skill_cancels():
    c, gi, got = make(GASLIGHT)
    gi.raise_id(ev(gi, "Batman_Gaslight_Bat_Scream"))
    c.run(0.3)
    gi.raise_id(ev(gi, "Batman_Gaslight_Batflight"))
    seq = codes(got)
    check("another skill's start: code 2 to the old script before code 1 to the new one",
          [(cd, d) for _t, cd, d in got[-2:]] == [(2, BAT_SCREAM), (1, BATFLIGHT)], got)


def test_accept_filter():
    R.ACCEPT_FILTER = True
    try:
        w = R.NullWorld(log=lambda text: None)
        with contextlib.redirect_stdout(io.StringIO()):
            inst = R.start_script(V.load(ZOD_R), "Batman", w, slot=4)
        acc = R.accepted_events(inst.script)
        check("accept list read from the record (0x1000000F, 0x1000001D)", {0x1000000F, 0x1000001D} <= set(acc), acc)
        seen = []
        orig = inst.regions[0].event
        inst.regions[0].event = lambda e: (seen.append(e), orig(e))[1]
        inst.event(0x10000023)
        inst.event(0x1000001D)
        check("accept filter: 0x10000023 dropped, 0x1000001D delivered", seen == [0x1000001D], seen)
    finally:
        R.ACCEPT_FILTER = False


def test_str_owner_side_bug():
    """python -m ics.script_runtime crashed in _graph_cast on the NullWorld's str owner (skill-execution-model.md 6.6)."""
    path = os.path.join(ROOT, "data", "skill_hooks.tsv")
    n = R.load_graph_hooks(path)
    try:
        with contextlib.redirect_stdout(io.StringIO()):
            R._main(["0x3400003B"])
        check("python -m ics.script_runtime with graph hooks loaded (str owner)", n > 0, n)
    except Exception as e:                                          # noqa: BLE001
        check("python -m ics.script_runtime with graph hooks loaded (str owner)", False, repr(e))
    finally:
        R.GRAPH_HOOKS.clear()


def main():
    for t in (test_data, test_zod_r, test_zod_r_script, test_thousand_cuts, test_basic_attack_speed, test_batflight,
              test_grab, test_stun_mid_cast, test_new_skill_cancels, test_accept_filter, test_str_owner_side_bug):
        try:
            t()
        except Exception as e:                                      # noqa: BLE001
            import traceback
            traceback.print_exc()
            check(t.__name__, False, repr(e))
    print(f"\n{passed} passed, {failed} failed")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
