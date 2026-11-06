"""Which killers a type-0 defeat guard answers on a non-script hit (PR #4 review, 2026-11-05, finding 3).

[ics] defeat_guard_all_damage makes a type-0 guard (0x10000162) stop the lethal hits of turrets, minions, bosses and
objectives too and raise 0x1000011B {KillerIID 0x032C3FD4}, as script damage does. Nightmare Superman's Possession
0x3400041C copies KillerIID into TargetIID and possesses it only if IsKind(TargetIID)[8] (a champion); with any other
killer its exit takes the failed branch, SpendCost(-100 %)[2, 1], which empties the bar. ics does not apply that flag
on this branch (it comes with The Punch Line's PR), so the guard came back at once and a turret could never kill him.
A guard whose script reads the killer this way therefore holds a non-script hit only when the killer is a champion:
any other killer kills him, as the script's own failed branch would (P: from the data).
"""
from . import script_model as V

KILLER = 0x032C3FD4           # the 0x1000011B parameter KillerIID
CHAMPION_KIND = 8             # IsKind value of a champion
SET_VARIABLE, IS_KIND = 0x10000058, 0x10000029

_CACHE = {}


def _walk(n):
    yield n
    for c in n.children:
        yield from _walk(c)


def champion_killer_only(script):
    """True when the script copies KillerIID into a variable that it then requires to be a champion."""
    did = getattr(script, "did", None)
    if did not in _CACHE:
        raw = getattr(script, "raw", None)
        nodes = list(_walk(V.Node(raw))) if raw is not None else []
        holders = {n.operands[0].value for n in nodes
                   if n.type_id == SET_VARIABLE and len(n.operands) > 1 and n.operands[1].value == KILLER}
        _CACHE[did] = any(n.type_id == IS_KIND and n.operands and n.operands[0].value in holders
                          and n.values and n.values[0] == CHAMPION_KIND for n in nodes)
    return _CACHE[did]


def holds(scripts, killer):
    """Whether a type-0 guard stops a non-script lethal hit from `killer`, given the target's running scripts."""
    if getattr(killer, "kind", None) == "champion":
        return True
    return not any(champion_killer_only(getattr(i, "script", None)) for i in scripts
                   if getattr(i, "status", None) is None and not getattr(i, "removed", False))
