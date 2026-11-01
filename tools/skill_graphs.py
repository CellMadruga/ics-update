"""Champion behaviour graphs as data for the server-side graph runtime (ics/graph.py) -> data/skill_graphs.json.

2026-10-27 (docs/re-notes/skill-execution-model.md 6.2): the original server ran every champion's Havok behaviour
graph and got the skill scripts' cast signals (event 0x1000000F, code = turbineEventHookPayload type) from it. This
tool dumps, per champion graph (0x1A packfile in the champion's packs):

  * every state machine: start state, wildcard transitions (event id, target, condition, flags), states;
  * every state: enter / exit notify events (with their hook payload {DID, code, missile offset}), out transitions,
    its generator body reduced to the clips that play (start time, static speed, bound speed variable, loop mode,
    triggers in clip-local time or end-relative, with payloads), nested machines and Lua callbacks;
  * the events the champion's scriptlet keys raise (type 0x14 actions of the scriptlet table entries in its packs,
    plus the shared pack 0xA00000DF): what ics sends as 0x8D also drives the server's copy of the graph;
  * per hooked skill state, the gate events (nested transitions no clip of the state raises) and who raises them
    (RaiseGraphEvent in which scripts, or which scriptlet keys run by which scripts).

Only ids, names of states / events / variables / clips and numbers are written (no game text, no binary).
data/skill_hooks.tsv (tools/graph_hooks.py) is kept for diffing.

    python tools/skill_graphs.py              # all champions (about a minute)
    python tools/skill_graphs.py --only Zod   # one champion (by name)
"""
import argparse
import collections
import glob
import json
import os
import re
import struct
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
from ics import config, gamedata, rp                          # noqa: E402
from ics import script_model as V                             # noqa: E402
from uesrv.havok import Packfile, find_packfiles              # noqa: E402

OUT = os.path.join(ROOT, "data", "skill_graphs.json")
SHARED_PACKS = (0xA00000DF,)
NAME_PACK = 0xA0000038
ONE = 0x3F800000
SELF_EVENTS = {"state_to_state", "next_animation", "skill_to_cosmetic", "skill_to_locomotion",
               "basicattack_to_basicattack", "state_to_locomotion"}
SKIP_CLASSES = {"hkbBehaviorGraphData", "hkbBehaviorGraphStringData", "hkbVariableValueSet",
                "hkbStateMachineStateInfo"}
EARLY_OUT_LUA = ("onCosmeticEarlyOut", "onBasicAttackEarlyOut", "onSkillEarlyOut")
RAISE_GRAPH_EVENT, RUN_SCRIPTLET = 0x1000004E, 0x10000034


def strarr(pf, field):
    a, n = pf.array(field)
    return [pf.string(a + 4 * i) for i in range(n)] if a is not None and n < 5000 else []


class Graph:
    """Reader of one hkbBehaviorGraph packfile (hk_2012.2, 4-byte pointers). Offsets: docs/re-notes/
    skill-execution-model.md 2-3 (state info +40 enter / +44 exit / +48 transitions / +52 generator / +56 name / +60
    id; machine +32 name / +108 start state (P) / +144 states / +156 wildcards; transition 60 bytes: +36 condition,
    +40 event, +44 target, +58 flags; clip +96 animation, +116 start time, +120 playback speed, +124 enforced
    duration, +134 mode (1 = looping); trigger 16 bytes: local time, event, payload, end-relative byte)."""

    def __init__(self, pf, lua):
        self.pf = pf
        self.cls = dict(pf.objects)
        self.offs = sorted(self.cls)
        self._index = {o: i for i, o in enumerate(self.offs)}
        sd = pf.of_class("hkbBehaviorGraphStringData")[0]
        self.EV = strarr(pf, sd + 8)
        self.VA = strarr(pf, sd + 32)
        self.name = pf.string(pf.of_class("hkbBehaviorGraph")[0] + 32)
        self.funcs = {}
        parts = re.split(r"(?m)^\s*function\s+(\w+)\s*\(\s*\)", lua)
        for i in range(1, len(parts), 2):
            self.funcs[parts[i]] = parts[i + 1]
        self.sm_states = {}
        for sm in pf.of_class("hkbStateMachine"):
            states = {}
            a, n = pf.array(sm + 144)
            for i in range(n if a is not None else 0):
                st = pf.ptr.get(a + 4 * i)
                if st in self.cls:
                    states[self.i32(st + 60)] = st
            self.sm_states[sm] = states

    def i32(self, o):
        return struct.unpack_from("<i", self.pf.data, self.pf.base + o)[0]

    def f32(self, o):
        return struct.unpack_from("<f", self.pf.data, self.pf.base + o)[0]

    def u8(self, o):
        return self.pf.data[self.pf.base + o]

    def ev(self, i):
        return self.EV[i] if 0 <= i < len(self.EV) else None

    def size(self, o):
        i = self._index[o]
        return (self.offs[i + 1] if i + 1 < len(self.offs) else o + 256) - o

    def kids(self, o):
        pf, r = self.pf, []
        for f in range(12, self.size(o), 4):
            t = pf.ptr.get(o + f)
            if t is None:
                continue
            if t in self.cls:
                r.append(t)
            else:
                n = pf.u32(o + f + 4)
                if 0 < n < 500 and pf.ptr.get(t) in self.cls:
                    r += [pf.ptr[t + 4 * i] for i in range(n) if pf.ptr.get(t + 4 * i) in self.cls]
        return r

    def trans(self, arr):
        pf, out = self.pf, []
        a, n = pf.array(arr + 8)
        for i in range(n if a is not None else 0):
            e = a + 60 * i
            cond = pf.ptr.get(e + 36)
            cs = pf.string(cond + 8) if self.cls.get(cond) == "hkbExpressionCondition" else ""
            fl = struct.unpack_from("<H", pf.data, pf.base + e + 58)[0]
            out.append({"n": self.ev(self.i32(e + 40)), "to": self.i32(e + 44), "c": cs, "f": fl})
        return out

    def bindings(self, o):
        pf = self.pf
        b = pf.ptr.get(o + 8)
        if b is None or self.cls.get(b) != "hkbVariableBindingSet":
            return []
        a, n = pf.array(b + 8)
        out = []
        for i in range(n if a is not None else 0):
            e = a + 32 * i
            vi = self.i32(e + 20)
            out.append((pf.string(e), self.VA[vi] if 0 <= vi < len(self.VA) else str(vi)))
        return out

    def payload(self, p):
        if self.cls.get(p) != "turbineEventHookPayload":
            return None
        off = [round(self.f32(p + 32 + 4 * k), 3) for k in range(3)]
        return {"did": self.pf.u32(p + 20), "code": self.pf.u32(p + 24), "off": off if any(off) else None}

    def notify(self, arr):
        out = []
        if not arr:
            return out
        a, n = self.pf.array(arr + 8)
        for i in range(n if a is not None else 0):
            out.append(self.event_entry(self.ev(self.i32(a + 8 * i)), self.payload(self.pf.ptr.get(a + 8 * i + 4))))
        return out

    @staticmethod
    def event_entry(name, pl):
        e = {"n": name}
        if pl:
            e.update({"code": pl["code"], "did": pl["did"]})
            if pl["off"]:
                e["off"] = pl["off"]
        return e

    def child_gen(self, child):
        """The generator of a hkbBlenderGeneratorChild (its first pointer to a generator class)."""
        return next((k for k in self.kids(child) if "Generator" in self.cls[k] or self.cls[k] == "hkbStateMachine"), None)

    # --- reduced generator tree
    def body(self, o, machines):
        res = {"clips": [], "sm": [], "lua": [], "binds": []}
        seen = set()

        def has_hooks(g, depth=0):
            """Weight of a blend child: hook payloads count most, then self-ending events (skill_to_*), then any
            trigger (footsteps): Huntress' Snap_Shot blends a locomotion clip with footsteps and the shot clip."""
            if depth > 12 or g not in self.cls:
                return 0
            c = self.cls[g]
            if c == "hkbClipGenerator":
                w = 0
                for k in self.kids(g):
                    if self.cls[k] != "hkbClipTriggerArray":
                        continue
                    a, n = self.pf.array(k + 8)
                    for i in range(n if a is not None else 0):
                        e = a + 16 * i
                        if self.payload(self.pf.ptr.get(e + 8)):
                            w += 100
                        elif self.ev(self.i32(e + 4)) in SELF_EVENTS:
                            w += 10
                        else:
                            w += 1
                return w
            if c in SKIP_CLASSES or c == "hkbStateMachine":
                return 0
            return sum(has_hooks(k, depth + 1) for k in self.kids(g))

        def has_sm(g, depth=0):
            if depth > 12 or g not in self.cls:
                return False
            c = self.cls[g]
            if c == "hkbStateMachine":
                return True
            if c in SKIP_CLASSES or c == "hkbClipGenerator":
                return False
            return any(has_sm(k, depth + 1) for k in self.kids(g))

        def walk(g):
            if g in seen or g not in self.cls:
                return
            seen.add(g)
            c = self.cls[g]
            if c in SKIP_CLASSES:
                return
            for b in self.bindings(g):
                res["binds"].append("%s<-%s" % b)
            if c == "hkbStateMachine":
                res["sm"].append(machines(g))
                return
            if c == "hkbClipGenerator":
                res["clips"].append(self.clip(g))
                return
            if c == "hkbScriptGenerator":
                for k in (96, 100, 104, 108, 112):
                    s = self.pf.string(g + k)
                    if s:
                        res["lua"].append(s.split("(")[0])
            if c == "hkbBlenderGenerator":
                # the blend children play together; their clips are variants of one motion (idle / walk / run,
                # left / right): one child is kept, the first whose clips carry triggers, else the first
                kids = [self.child_gen(k) for k in self.kids(g) if self.cls[k] == "hkbBlenderGeneratorChild"]
                kids = [k for k in kids if k in self.cls]
                layers = [k for k in kids if has_sm(k)]          # state machines in a blend are layers: all run
                rest = [k for k in kids if k not in layers]
                pick = max(rest, key=lambda k: (has_hooks(k), -rest.index(k))) if rest else None
                for k in layers + ([pick] if pick is not None else []):
                    walk(k)
                return
            for k in self.kids(g):
                if self.cls[k] == "hkbBlenderGeneratorChild":
                    k2 = self.child_gen(k)
                    if k2 in self.cls:
                        walk(k2)
                    continue
                walk(k)
        walk(o)
        return res

    def clip(self, o):
        pf = self.pf
        stt, spd, enf = self.f32(o + 116), self.f32(o + 120), self.f32(o + 124)
        bound = next((v for f, v in self.bindings(o) if f == "playbackSpeed"), None)
        trig = []
        for k in self.kids(o):
            if self.cls[k] != "hkbClipTriggerArray":
                continue
            a, n = pf.array(k + 8)
            for i in range(n if a is not None else 0):
                e = a + 16 * i
                t = self.event_entry(self.ev(self.i32(e + 4)), self.payload(pf.ptr.get(e + 8)))
                t["t"] = round(self.f32(e), 4)
                if self.u8(e + 12):
                    t["rel"] = 1
                trig.append(t)
        out = {"anim": pf.string(o + 96), "start": round(stt, 4), "speed": round(spd, 4),
               "loop": 1 if self.u8(o + 134) == 1 else 0, "trig": trig}
        if bound:
            out["bound"] = bound
        if enf > 0:
            out["dur"] = round(enf, 4)
        return out

    def dump(self):
        machines, order = {}, []

        def machine(sm):
            if sm in machines:
                return machines[sm]["id"]
            m = {"id": len(order), "name": self.pf.string(sm + 32), "start": self.i32(sm + 108)}
            machines[sm] = m
            order.append(m)
            w = self.pf.ptr.get(sm + 156)
            m["wild"] = self.trans(w) if w else []
            m["states"] = {}
            for sid, st in sorted(self.sm_states.get(sm, {}).items()):
                tr = self.pf.ptr.get(st + 48)
                s = {"name": self.pf.string(st + 56),
                     "enter": self.notify(self.pf.ptr.get(st + 40)), "exit": self.notify(self.pf.ptr.get(st + 44)),
                     "out": self.trans(tr) if tr else []}
                g = self.pf.ptr.get(st + 52)
                s["body"] = self.body(g, machine) if g in self.cls else {"clips": [], "sm": [], "lua": [], "binds": []}
                m["states"][str(sid)] = s
            return m["id"]
        # the top machines: reachable from the graph's root generator without passing through a state
        roots, seen = [], set()

        def walk(g):
            if g in seen or g not in self.cls:
                return
            seen.add(g)
            c = self.cls[g]
            if c in SKIP_CLASSES:
                return
            if c == "hkbStateMachine":
                roots.append(machine(g))
                return
            for k in self.kids(g):
                walk(k)
        walk(self.pf.of_class("hkbBehaviorGraph")[0])
        lua = {}
        for fn, body in self.funcs.items():
            evs = sorted(set(re.findall(r'hkbFireEvent\s*\(\s*"(\w+)"', body)))
            if evs and fn in EARLY_OUT_LUA:
                lua[fn] = evs
        return {"roots": roots, "machines": order, "lua_fire": lua}


def graphs_in(pack_path):
    try:
        d = rp.Pack(pack_path).data
    except OSError:
        return []
    if b"hkbBehaviorGraph" not in d:
        return []
    lua = ""
    for m in re.finditer(rb"[\t\r\n\x20-\x7e]{200,}", d):
        if b"function " in m.group(0) and b"hkb" in m.group(0):
            lua += m.group(0).decode().replace("\r", "") + "\n"
    out = []
    for off in find_packfiles(d):
        try:
            pf = Packfile(d, off)
        except Exception:                                      # noqa: BLE001
            continue
        if pf.of_class("hkbBehaviorGraph") and pf.of_class("hkbBehaviorGraphStringData"):
            g = Graph(pf, lua)
            if g.name.startswith("chr_"):
                out.append(g)
    return out


def scriptlet_events(pack_path, keys):
    """{scriptlet key: [graph event ids]} from the type 0x14 actions (raise animation-graph event, client-scriptlets-
    graphs.md 1.5 / 2) of the scriptlet entries in a pack: "0x14 | n bindings | n x 4 words | 0 | 0 | 1 | f32 1.0 |
    jitter | intensity | time | event", owned by the nearest entry start "key | 0 | n props | props | n actions"."""
    try:
        d = rp.Pack(pack_path).data
    except OSError:
        return {}
    out = collections.defaultdict(list)
    for a in range(4):
        n = (len(d) - a) // 4
        if n <= 0:
            continue
        w = struct.unpack_from("<%dI" % n, d, a)
        i = -1
        while True:
            try:
                i = w.index(0x14, i + 1)
            except ValueError:
                break
            if i + 12 >= n or w[i + 1] > 4:
                continue
            j = i + 2 + 4 * w[i + 1]
            if j + 8 >= n or w[j] != 0 or w[j + 1] != 0 or w[j + 2] != 1 or w[j + 3] != ONE:
                continue
            ev = w[j + 7]
            for k in range(i - 1, max(0, i - 400), -1):
                if w[k] in keys and rp._is_scriptlet(w, k, n):
                    if ev and ev not in out[w[k]]:
                        out[w[k]].append(ev)
                    break
    return dict(out)


def script_raisers():
    """{graph event: [scripts raising it]} (RaiseGraphEvent) and {scriptlet key: [scripts running it]}."""
    raise_by, run_by = collections.defaultdict(set), collections.defaultdict(set)

    def walk(node, did):
        t = node.type_id
        if node.values and isinstance(node.values[0], int):
            if t == RAISE_GRAPH_EVENT:
                raise_by[node.values[0]].add(did)
            elif t == RUN_SCRIPTLET:
                run_by[node.values[0]].add(did)
        for c in node.children:
            walk(c, did)

    def state(s, did):
        for c in s.chains:
            walk(c, did)
        for x in s.states:
            state(x, did)
    for f in glob.glob(os.path.join(V.TREES, "*.json")):
        try:
            did = int(os.path.basename(f)[:-5], 16)
            for g in V.load(did).graphs:
                state(g, did)
        except (ValueError, OSError, KeyError):
            continue
    return raise_by, run_by


def gates(gdump, ev_id, raise_by, run_by, key_events):
    """Per hooked skill state: nested-transition events no trigger / notify of the state raises (the script must)."""
    ms = gdump["machines"]
    by_key_event = collections.defaultdict(set)
    for k, evs in key_events.items():
        for e in evs:
            by_key_event[e].add(k)
    out = []

    def sub(st, acc_raised, acc_gates):
        for e in st["enter"] + st["exit"]:
            acc_raised.add(e["n"])
        for c in st["body"]["clips"]:
            for t in c["trig"]:
                acc_raised.add(t["n"])
        for mid in st["body"]["sm"]:
            m = ms[mid]
            for w in m["wild"]:
                acc_gates.add(w["n"])
            for x in m["states"].values():
                for o in x["out"]:
                    acc_gates.add(o["n"])
                sub(x, acc_raised, acc_gates)
    for m in ms:
        for sid, st in m["states"].items():
            dids = {e["did"] for e in st["enter"] if e.get("code") == 1}
            if not dids:
                continue
            raised, gs = set(), set()
            sub(st, raised, gs)
            for e in sorted(x for x in gs if x and x not in raised and x not in SELF_EVENTS):
                i = ev_id.get(e)
                rb = sorted(raise_by.get(i, ())) if i else []
                keys = sorted(by_key_event.get(i, ())) if i else []
                via = sorted({d for k in keys for d in run_by.get(k, ())})
                out.append({"script": "0x%08X" % min(dids), "machine": m["id"], "state": int(sid), "event": e,
                            "id": i, "raised_by": ["0x%08X" % d for d in rb],
                            "keys": ["0x%08X" % k for k in keys], "keys_run_by": ["0x%08X" % d for d in via]})
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--only", help="one champion (name)")
    ap.add_argument("--out", default=OUT)
    a = ap.parse_args()
    cfg = config.load()
    rp_dir = os.path.join(cfg.game_dir, "rp")
    data = gamedata.Data(cfg.game_dir)
    roster = json.load(open(os.path.join(ROOT, "data", "champions.json"), encoding="utf-8"))
    names = rp.name_tables(rp.Pack(os.path.join(rp_dir, "0x%08x.rp" % NAME_PACK)))
    # the graph-event name table 0x300000A4 comes out of name_tables in several runs (C: Batman_Gaslight_Bat_Scream
    # 0x100000E7 and Basic_Attack_Left 0x100000F4 sit in a run of their own); every run but the scriptlet-key table
    # 0x33000000 is taken, the one holding Global_Locomotion first
    skeys = data.scriptlet_names()
    ev_id = {}
    for r in sorted((r for r in names if r is not skeys and r != skeys),
                    key=lambda r: 0 if "Global_Locomotion" in r.values() else 1):
        for k, v in r.items():
            ev_id.setdefault(v, k)
    keys = set(data.scriptlet_names())
    path = lambda p: os.path.join(rp_dir, "0x%08x.rp" % p)          # noqa: E731
    shared = {}
    for p in SHARED_PACKS:
        for k, v in scriptlet_events(path(p), keys).items():
            shared.setdefault(k, v)
    raise_by, run_by = script_raisers()
    cache, graphs, variants = {}, {}, {}

    def pack_graphs(p):
        if p not in cache:
            cache[p] = graphs_in(path(p)) if p else []
        return cache[p]
    for c in roster:
        if a.only and c["name"].lower() != a.only.lower():
            continue
        kit_scripts = {sk.script for sk in data.kit(c["variant"]).values() if sk.script}
        entries = [(c["variant"], [c.get("heavy_pack"), c.get("light_pack"), c.get("parent_pack")])]
        entries += [(s["variant"], [s.get("heavy_pack"), s.get("light_pack"), c.get("parent_pack")])
                    for s in c.get("costume_info", [])]
        for variant, packs in entries:
            best = None
            for rank, p in enumerate(packs):
                for g in pack_graphs(p):
                    hooked = {g.pf.u32(o + 20) for o in g.pf.of_class("turbineEventHookPayload")}
                    score = (len(hooked & kit_scripts), -rank, len(g.pf.objects))
                    if best is None or score > best[0]:
                        best = (score, g, p)
            if best is None:
                print(f"{c['name']} {variant:#x}: no graph", file=sys.stderr)
                continue
            _s, g, p = best
            variants["0x%08X" % variant] = g.name
            if g.name not in graphs:
                gd = g.dump()
                ids = {}
                for m in gd["machines"]:
                    for lst in [m["wild"]] + [s["out"] for s in m["states"].values()]:
                        for t in lst:
                            ids[t["n"]] = ev_id.get(t["n"])
                    for s in m["states"].values():
                        for e in s["enter"] + s["exit"] + [t for cl in s["body"]["clips"] for t in cl["trig"]]:
                            ids[e["n"]] = ev_id.get(e["n"])
                for fn, evs in gd["lua_fire"].items():
                    for e in evs:
                        ids[e] = ev_id.get(e)
                gd["events"] = {n: i for n, i in ids.items() if n and i}
                gd["pack"] = "0x%08X" % p
                gd["champion"] = c["name"]
                own = {}
                for q in {c.get("heavy_pack"), c.get("light_pack"), c.get("parent_pack")} - {None, 0}:
                    for k, v in scriptlet_events(path(q), keys).items():
                        own.setdefault(k, [])
                        own[k] += [e for e in v if e not in own[k]]
                gd["scriptlets"] = {"0x%08X" % k: v for k, v in sorted(own.items())}
                gd["gates"] = gates(gd, ev_id, raise_by, run_by, {**shared, **own})
                graphs[g.name] = gd
                print(f"{c['name']}: {g.name} ({len(gd['machines'])} machines, {len(own)} scriptlet keys, "
                      f"{len(gd['gates'])} gates)")
    out = {"version": 1, "source": "tools/skill_graphs.py",
           "shared_scriptlets": {"0x%08X" % k: v for k, v in sorted(shared.items())},
           "variants": variants, "graphs": graphs}
    if a.only and os.path.exists(a.out):
        try:
            old = json.load(open(a.out, encoding="utf-8"))
            old["graphs"].update(graphs)
            old["variants"].update(variants)
            out = old
        except (OSError, ValueError, KeyError):
            pass
    with open(a.out, "w", encoding="utf-8") as f:
        json.dump(out, f, separators=(",", ":"))
    print(f"{len(out['graphs'])} graphs, {len(out['variants'])} variants -> {a.out}")


if __name__ == "__main__":
    main()
