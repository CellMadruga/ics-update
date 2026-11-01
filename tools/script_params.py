"""Which operand slot of ApplySkill (0x10000027) / RaiseEvent (0x1000006B) carries which event parameter.

  python tools/script_params.py apply|raise

Counts, over every decoded script, the slots a caller fills against the parameters the receiving script reads
(SetVariable(var, #parameter) in the states entered on the event). Results: ics/script_runtime.py APPLY_PARAMS /
RAISE_PARAMS.
"""
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
os.chdir(ROOT)

import collections
from ics import script_model as V
from ics import config
from ics.gamedata import Data

d = Data(config.load().game_dir)
scripts = {}
for f in os.listdir("data/script_trees"):
    try:
        scripts[int(f[:8], 16)] = V.load(int(f[:8], 16))
    except Exception:
        pass

def nodes(state_or_node):
    out = []
    def walk(n):
        out.append(n)
        for c in n.children:
            walk(c)
    for ch in getattr(state_or_node, "chains", []):
        walk(ch)
    return out

def all_states(g, out):
    out.append(g)
    for s in g.states:
        all_states(s, out)
    return out

def reads_on(script, event):
    """Hashes read by SetVariable(#x) in states entered on `event` (and in their sub-states)."""
    hs = set()
    for g in script.graphs:
        for gr in all_states(g, []):
            for t in gr.transitions:
                tr = t.trigger
                if tr is None or not tr.values or tr.values[-1] != event:
                    continue
                if t.target < len(gr.states):
                    for st in all_states(gr.states[t.target], []):
                        for n in nodes(st):
                            if n.type_id == 0x10000058 and len(n.operands) > 1 and n.operands[1].source == V.UNSET:
                                hs.add(n.operands[1].value)
    return hs

kind = sys.argv[1] if len(sys.argv) > 1 else "apply"
pair, slot_n = collections.Counter(), collections.Counter()
for did, s in scripts.items():
    for g in s.graphs:
        for st in all_states(g, []):
            for n in nodes(st):
                if kind == "apply" and n.type_id == 0x10000027 and n.values:
                    status = n.values[0]
                    sd = d.status_script(status)
                    if not sd or sd not in scripts:
                        continue
                    hs = reads_on(scripts[sd], 0x10000006)
                elif kind == "raise" and n.type_id == 0x1000006B and n.values:
                    ev = n.values[0]
                    hs = set()
                    for s2 in scripts.values():
                        hs |= reads_on(s2, ev)
                else:
                    continue
                filled = [i for i, op in enumerate(n.operands) if not op.is_unset()]
                for i in filled:
                    slot_n[i] += 1
                    for h in hs:
                        pair[(i, h)] += 1
names = {}
for s in scripts.values():
    names.update(s.names)
for i in sorted(slot_n):
    best = sorted(((c, h) for (j, h), c in pair.items() if j == i), reverse=True)[:4]
    print(f"slot {i} (filled {slot_n[i]}x): " + ", ".join(f"{names.get(h, hex(h))} {c}" for c, h in best))
