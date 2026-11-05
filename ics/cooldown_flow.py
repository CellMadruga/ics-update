"""Which StartCooldown durations come from a saved cooldown (PR #4 review, 2026-11-05, finding 1).

StartCooldown with an explicit slot is an ordinary cooldown in 26 of the game's 32 such nodes (Superman's basic attack,
Robin's R, Green Arrow's SharedCooldown, ...): it takes cooldown reduction and 0 does nothing. Only Blue Beetle's form
swaps (0x34000451 / 454 / 455) feed it a time read back from the owner block's cooldown slots (0x20 + 8 x slot: the
engine writes them, no script does) to put back the other form's remaining cooldown. This module reads that from the
script itself: a variable is "a cooldown read" when a copy (builtin 0x11) or an assignment (builtin 0x1) takes a
cooldown slot or another such variable (Blue Beetle: slot 0x28 -> TempTimerHolding -> TimeRemaining, 0x28 -> 0xD0).
"""

SLOT_FIRST, SLOT_LAST = 0x20, 0x48        # slots 0-5 (basic attack, Q, W, E, R, the sixth): the range the game reads

_CACHE = {}


def is_cooldown_slot(op):
    """An owner-block operand at a cooldown slot (source 2, offset 0x20 + 8 x slot, slots 0-5)."""
    return (op is not None and op.source == 2 and isinstance(op.slot, int)
            and SLOT_FIRST <= op.slot <= SLOT_LAST and op.slot % 8 == 0)


def _walk(n):
    yield n
    for c in getattr(n, "children", ()):
        yield from _walk(c)


def _reads(n):
    for x in _walk(n):
        yield from getattr(x, "operands", ())


def cooldown_vars(script):
    """The variable hashes of `script` that hold a cooldown read (fixed point over its copies and assignments)."""
    did = getattr(script, "did", None)
    if did in _CACHE:
        return _CACHE[did]
    from . import script_model as V
    raw = getattr(script, "raw", None)
    nodes = list(_walk(V.Node(raw))) if raw is not None else []
    moves = []
    for n in nodes:
        if n.type == "builtin:0x11" and len(n.operands) >= 2:
            moves.append((n.operands[0], [n.operands[1]]))
        elif n.type == "builtin:0x1" and n.operands:
            moves.append((n.operands[0], [o for c in n.children if c.role != "next" for o in _reads(c)]))
    marked, changed = set(), True
    while changed:
        changed = False
        for dst, srcs in moves:
            if dst.value not in marked and any(is_cooldown_slot(o) or o.value in marked for o in srcs):
                marked.add(dst.value)
                changed = True
    _CACHE[did] = frozenset(marked)
    return _CACHE[did]


def is_restore(script, duration_op):
    """True when a StartCooldown's duration operand is a cooldown read (the node puts a saved cooldown back)."""
    if duration_op is None or duration_op.is_unset():
        return False
    return is_cooldown_slot(duration_op) or duration_op.value in cooldown_vars(script)
