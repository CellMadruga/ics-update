"""Skill hook timings from the champions' animation graphs (docs/re-notes/animation-deep-scan.md).

2026-10-25 (tester: skills start their animation and never finish it): each champion's Havok behaviour graph (0x1A
packfile in its parent pack) notifies, on entering a skill state and from its clip triggers, a turbineEventHookPayload
{skill script DID, code}: 1 start, 2 state exit, 3 hit (a_SkillHook), 5 missile out (a_MissileFireHook), 6 hold. These
codes are the scripts' OnCastSignal [0x1000000F code]; the original server timed them from the graph. This tool dumps,
per skill script DID, the graph state, its trigger times and how the state is left, into data/skill_hooks.tsv, which
ics reads at start ([ics] graph_cast_timing). Run it once per install:

    python tools/graph_hooks.py
"""
import glob
import os
import struct
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
from ics.rp import Pack                                  # noqa: E402
from uesrv.havok import Packfile, find_packfiles         # noqa: E402


def strarr(pf, field):
    a, n = pf.array(field)
    return [pf.string(a + 4 * i) for i in range(n)] if a is not None else []


def graphs(path):
    p = Pack(path)
    for off in find_packfiles(p.data):
        try: pf = Packfile(p.data, off)
        except Exception: continue
        if pf.of_class("hkbBehaviorGraph") and pf.of_class("hkbBehaviorGraphStringData"): yield pf
def analyse(pf, out, tag):
    cls = dict(pf.objects); offs = sorted(cls)
    sd = pf.of_class("hkbBehaviorGraphStringData")[0]; EV = strarr(pf, sd+8)
    gname = pf.string(pf.of_class("hkbBehaviorGraph")[0]+32)
    i32 = lambda o: struct.unpack_from("<i", pf.data, pf.base+o)[0]
    f32 = lambda o: struct.unpack_from("<f", pf.data, pf.base+o)[0]
    def size(o):
        i = offs.index(o); return (offs[i+1] if i+1 < len(offs) else o+256) - o
    def kids(o):
        r=[]
        for f in range(12, size(o), 4):
            t = pf.ptr.get(o+f)
            if t is None or f == 8: continue
            if t in cls: r.append(t)
            else:
                n = pf.u32(o+f+4)
                if 0 < n < 500 and pf.ptr.get(t) in cls:
                    r += [pf.ptr[t+4*i] for i in range(n) if pf.ptr.get(t+4*i) in cls]
        return r
    def ev(i): return EV[i] if 0 <= i < len(EV) else "?"
    def payload(p): return (pf.u32(p+20), pf.u32(p+24)) if p in cls and cls[p] == "turbineEventHookPayload" else None
    for st in pf.of_class("hkbStateMachineStateInfo"):
        en = pf.ptr.get(st+40); ex = pf.ptr.get(st+44)
        start = None
        for arr in (en,):
            if not arr: continue
            a,n = pf.array(arr+8)
            for i in range(n):
                pl = payload(pf.ptr.get(a+8*i+4))
                if pl and pl[1] == 1: start = pl[0]
        if not start: continue
        name = pf.string(st+56)
        # transitions out of the state
        tr = pf.ptr.get(st+48); leaves = []
        if tr:
            a,n = pf.array(tr+8)
            leaves = [ev(i32(a+60*i+40)) for i in range(n)]
        # clip triggers in the subtree (DFS order), with clip start time and speed
        seen=set(); trig=[]; speedbind=set()
        def walk(o):
            if o in seen: return
            seen.add(o)
            c = cls[o]
            if c == "hkbStateMachineStateInfo" and o != st:
                pass
            if c == "hkbClipGenerator":
                stt, spd = f32(o+116), f32(o+120)
                b = pf.ptr.get(o+8)
                if b in cls: speedbind.add("bound")
                t = pf.ptr.get(o+100) if False else None
                for k in kids(o):
                    if cls[k] == "hkbClipTriggerArray":
                        a,n = pf.array(k+8)
                        for i in range(n):
                            e=a+16*i; lt=f32(e); pl=payload(pf.ptr.get(e+8)); nm=ev(i32(e+4))
                            rel = pf.data[pf.base+e+12]
                            if pl or nm in ("skill_to_cosmetic","skill_to_locomotion","state_to_state","Global_Locomotion"):
                                trig.append((pf.string(o+32)[:28], nm, ("end%+.2f" % lt) if rel else "%.3f" % ((lt-stt)/spd if spd else lt), pl[1] if pl else "", "x%.2f" % spd))
            for k in kids(o): walk(k)
        walk(pf.ptr.get(st+52))
        out.append((tag, gname, hex(start), name, ",".join(leaves), "; ".join("%s:%s@%s%s" % (c[0], c[1], c[2], ("[code %s]" % c[3]) if c[3] != "" else "") for c in trig), " ".join(sorted(set(c[4] for c in trig))) , "speed-bound" if speedbind else ""))


def main():
    sys.path.insert(0, ROOT)
    from ics import config
    rp_dir = os.path.join(config.load().game_dir, "rp")
    out = []
    for f in sorted(glob.glob(os.path.join(rp_dir, "*.rp"))):
        try:
            for pf in graphs(f):
                analyse(pf, out, os.path.basename(f)[:-3])
        except Exception as e:                           # noqa: BLE001
            print(f, e, file=sys.stderr)
    seen = set()
    path = os.path.join(ROOT, "data", "skill_hooks.tsv")
    with open(path, "w", encoding="utf-8") as fo:
        fo.write("\t".join(["pack", "graph", "script", "state", "leaves_on", "triggers", "speeds", "binding"]) + "\n")
        for r in out:
            if (r[2], r[3]) in seen:
                continue
            seen.add((r[2], r[3]))
            fo.write("\t".join(r) + "\n")
    print(f"{len(seen)} skill states -> {path}")


if __name__ == "__main__":
    main()
