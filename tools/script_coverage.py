"""Coverage of the new server's script runtime (ics/script_runtime.py + ics/script_nodes.py).

  python tools/script_coverage.py [n]     static and simulated coverage, and the n most common gaps

Static: every node / expression class in every decoded script (data/script_trees, 875 records) must have an
implementation in the runtime (a builtin by vtable, an expression, an action or a predicate).
Simulated: each champion skill (catalog skills.tsv) is used on a drone, each status effect script is applied to a drone
and each entity script (missiles, spawned objects) is started, in NullWorld for 8 s with statuses and missiles
resolved from the packs; a run is clean when no node is reported unknown and nothing raises.
"""
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
os.chdir(ROOT)

import collections  # noqa: E402
import csv  # noqa: E402
import json  # noqa: E402
import traceback  # noqa: E402

from ics import script_model as V, script_runtime as R  # noqa: E402

STRUCTURE_VTS = {V.GRAPH, V.STATE, "0x15A8F18", "0x15A9D38"}


def known(raw):
    """True when the runtime has an implementation for this tree node."""
    t, vt = raw.get("type"), raw.get("vt")
    if t == "script" or vt in STRUCTURE_VTS:
        return True
    if vt in R.BUILTIN_VT or vt in R.BUILTIN_PREDICATES or vt in R.PREDICATE_VTS or vt in R.EXPR_OPS:
        return True
    if t in R.SERVER_EXPR:
        return True
    try:
        tid = int(t, 16)
    except (TypeError, ValueError):
        return False
    return tid in R.HANDLERS or tid in R.PREDICATES


def static(trees=V.TREES):
    missing, scripts, total, bad = collections.Counter(), collections.defaultdict(set), 0, set()

    def walk(n, did):
        if not known(n):
            key = f"{n.get('type')} ({n.get('vt')})"
            missing[key] += 1
            scripts[key].add(did)
            bad.add(did)
        for c in n["children"]:
            walk(c, did)
    for f in sorted(os.listdir(trees)):
        if not f.endswith(".json"):
            continue
        total += 1
        with open(os.path.join(trees, f), encoding="utf-8") as fh:
            raw = json.load(fh)
        walk(raw, raw["id"])
    return total, bad, missing, scripts


def simulate(data):
    from ics import combat as CB
    R.SCRIPT_RESOLVER, R.STATUS_RESOLVER, R.STACKS_RESOLVER = data.entity_scripts, data.status_script, data.status_max_stacks
    R.RECORD_RESOLVER = lambda did, prop: CB.record_value(data, did, prop)
    R.FLAGS_RESOLVER = lambda did: CB.status_flags(data, did)
    rows = [r for r in csv.DictReader(open("catalog/data/skills.tsv", encoding="utf-8"), delimiter="\t") if r["script"]]
    unknown, errs = collections.Counter(), collections.Counter()
    results = {}

    def run(kind, key, fn):
        w = R.NullWorld(log=lambda t: None)
        try:
            inst = fn(w)
            w.run_until(8.0)
            u = set(map(str, getattr(inst, "unknown", set()) or set()))
            for lst in w.scripts.values():
                for i in lst:
                    u |= set(map(str, i.unknown))
            for m in w.missiles:
                for i in m.instances:
                    u |= set(map(str, i.unknown))
            for x in u:
                unknown[x] += 1
            results[(kind, key)] = not u
        except Exception as e:                      # noqa: BLE001
            results[(kind, key)] = False
            errs[f"{kind} {key}: {type(e).__name__}: {str(e)[:70]}"] += 1
            if os.environ.get("COVERAGE_TRACE"):
                traceback.print_exc()

    from ics.gamedata import Skill
    kits = collections.defaultdict(dict)          # skill set -> {slot: Skill}: the caster's whole kit (stats of other slots)
    for r in rows:
        if ":" in r["id"]:
            kits[r["id"].split(":")[0]][int(r["slot"])] = Skill(r)

    def use(w, r):
        w.kit, w.slot = kits.get(r["id"].split(":")[0], {}), int(r["slot"])
        inst = R.start_script(V.load(int(r["script"], 16)), "Batman", w, slot=int(r["slot"]))
        R.activate(inst, "Drone", (8.0, 0.0, 0.0))
        return inst
    for r in rows:
        run("skill", r["id"], lambda w, r=r: use(w, r))
    # every decoded script that is not a skill: as a status effect on a drone (its usual host), started with the
    # apply event; scripts named by entity classes run as their own objects (missiles start with their spawn event)
    skill_scripts = {int(r["script"], 16) for r in rows}
    for f in sorted(os.listdir(V.TREES)):
        did = int(f[:8], 16)
        if did in skill_scripts or did == 0x34000000:
            continue

        def as_status(w, did=did):
            inst = R.Instance(V.load(did), "Drone", w)
            inst.status = 0x48FFFFFF
            R.statuses_on(w, "Drone").setdefault(0x48FFFFFF, []).append(inst)
            R.scripts_on(w, "Drone").append(inst)
            inst.start()
            inst.event(R.EVENT_STATUS_APPLIED, {"EffectDuration": 3.0, "EffectSource": "Batman", "EffectRank": 1})
            inst.event(R.EVENT_SPAWN)
            return inst
        run("script", f"{did:#x}", as_status)
    return results, unknown, errs


def main(argv):
    top = int(argv[0]) if argv else 40
    total, bad, missing, scripts = static()
    print(f"static: {total - len(bad)} of {total} scripts have every node implemented")
    for k, v in missing.most_common(top):
        print(f"  {v:4} nodes in {len(scripts[k]):3} scripts: {k}")
    from ics import config
    from ics.gamedata import Data
    data = Data(config.load().game_dir)
    results, unknown, errs = simulate(data)
    by_kind = collections.Counter(k for k, _ in results)
    clean = collections.Counter(k for (k, _), ok in results.items() if ok)
    print("simulated (8 s in NullWorld): " + ", ".join(f"{kind} {clean[kind]} / {by_kind[kind]} clean"
                                                       for kind in sorted(by_kind)))
    print(f"crashes: {sum(errs.values())}")
    for k, v in unknown.most_common(top):
        print(f"  {v:4} {k}")
    for k, v in errs.most_common(top):
        print(f"  {v} {k}")
    return 0 if not bad and not errs else 1


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
