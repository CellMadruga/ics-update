"""Model of the original server's scripts (records 0x34), built from the exact trees that
tools/script_decoder.py writes to data/script_trees/ (the client's own Unpack code, run under emulation).

A script holds graphs (hierarchical state machines). A graph has states, transitions and its own local
variables; a state has up to 3 action chains and local variables; an action chain is a linked list of nodes
(each node's "next" is serialized before its own fields). Nodes take operands (value | source | slot) and child
expressions. See docs/reverse-engineering.md, "Script VM object model".

This module only reads and describes scripts; running them is the next step.

    python -m icserver.scriptvm 0x3400003B       print a script as pseudo-code
"""
import json
import os
import re
import struct

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
TREES = os.path.join(ROOT, "data", "script_trees")

SELF = 0x4DD4
UNSET = 0xFFFFFFFF

# Readers (return addresses in the client exe) that tell what a field or a child is.
OPERAND = ("0x453173", "0x453185", "0x453197")       # value, source, slot
NEXT = "0x45FE89"                                    # base node: type of the next node in the chain
ROLE = {
    "0x45FE89": "next", "0x44E8E2": "item", "0x44EE99": "chain", "0x44EB86": "trigger",
    "0x460502": "value", "0x469EF9": "left", "0x469F46": "right", "0x469E59": "arg",
    "0x469FF9": "x", "0x46A046": "y", "0x46A093": "z", "0x45FC62": "sub", "0x46001A": "sub",
}
# transition fields (graph +0x28, Unpack 0x44eb50)
T_SOURCES_COUNT, T_SOURCE, T_TARGET, T_TRIGGER, T_A, T_B = (
    "0x44AF56", "0x44AFBF", "0x44EB74", "0x44EB86", "0x44EBD3", "0x44EBE5")
T_COUNT = "0x44BEB6"
NAME_LEN, NAME_CHARS, VAR_HASH, VAR_SLOT = "0x421444", "0x424C11", "0x55C258", "0x55C26A"

# vtables of the structural and expression classes (decoder field "vt")
GRAPH, STATE = "0x15A8218", "0x15A7F98"
EXPR = {
    "0x15A9D38": "var", "0x15A8F18": "const", "0x15A9830": "vec3", "0x15A9440": "+", "0x15A9478": "-",
    "0x15A94B0": "*", "0x15A93D0": "++", "0x15A8F70": "==", "0x15A8FA8": "!=", "0x15A9018": "<",
    "0x15A90F8": "max", "0x15A98A0": "length", "0x15A9868": "normalize", "0x15A97C0": "dot",
    "0x15A97F8": "cross", "0x15A9C58": "vadd", "0x15A9280": "not", "0x15A94E8": "idiv",
}

# Action nodes identified so far (meaning from the data and the client code; see the RE notes).
ACTIONS = {
    0x10000007: "StartCooldown", 0x10000010: "Delay", 0x10000014: "TakePosition",
    0x1000001D: "ApplyEffects", 0x10000027: "ApplySkill", 0x10000034: "RunScriptlet",
    0x1000003F: "FaceTarget", 0x10000047: "FindTargetsInRadius", 0x10000050: "InitSkill",
    0x10000058: "SetVariable", 0x1000005E: "LaunchMissile", 0x1000009F: "LoadSkillStats",
    0x100000A0: "SpawnEntity", 0x10000085: "DestructionImpulse", 0x10000223: "HitEffect",
}


def elf_hash(name):
    h = 0
    for c in name.encode():
        h = ((h << 4) + c) & 0xFFFFFFFF
        g = h & 0xF0000000
        if g:
            h ^= g >> 24
        h &= ~g & 0xFFFFFFFF
    return h


def _float(v):
    f = struct.unpack("<f", struct.pack("<I", v))[0]
    return f if v and 1e-6 < abs(f) < 1e7 and (v & 0xFFF) == 0 else None


class Operand:
    __slots__ = ("value", "source", "slot")

    def __init__(self, value, source, slot):
        self.value, self.source, self.slot = value, source, slot

    def is_self(self):
        return self.value == SELF and self.source == 2

    def is_unset(self):
        return self.source == UNSET

    def describe(self, names):
        if self.is_self():
            return "SELF"
        if self.source == UNSET:
            return "-" if self.value == 0 else f"#{self._lit(names)}"
        name = names.get(self.value)
        if name:
            return f"${name}" + ("" if self.source in (1, 3) else f"<src {self.source}>")
        if self.source == 1 and self.slot == 0:
            return f"#{self._lit(names)}"
        return f"<{self.value:#x} src {self.source} slot {self.slot:#x}>"

    def _lit(self, names):
        f = _float(self.value)
        if f is not None:
            return f"{f:g}"
        return names.get(self.value) or f"{self.value:#x}"


class Node:
    def __init__(self, raw, parent=None):
        self.type = raw.get("type")
        self.vt = raw.get("vt")
        self.role = ROLE.get(raw.get("via"), raw.get("via"))
        self.raw_via = raw.get("via")
        self.operands, self.values = [], []
        f = raw["fields"]
        i = 0
        while i < len(f):
            if f[i][2] == OPERAND[0] and i + 2 < len(f) and f[i + 1][2] == OPERAND[1]:
                self.operands.append(Operand(f[i][3], f[i + 1][3], f[i + 2][3]))
                i += 3
                continue
            if f[i][2] != NEXT:
                self.values.append(f[i][3])
            i += 1
        self.children = [Node(c, self) for c in raw["children"]]
        self.next = next((c for c in self.children if c.role == "next"), None)

    @property
    def type_id(self):
        try:
            return int(self.type, 16)
        except (TypeError, ValueError):
            return None

    def name(self):
        if self.vt in EXPR:
            return EXPR[self.vt]
        t = self.type_id
        if t is not None and t >= 0x10000000:
            return ACTIONS.get(t, f"node_{t:08X}")
        return self.type or "?"

    def chain(self):
        """This node and the nodes linked after it."""
        n = self
        while n is not None:
            yield n
            n = n.next


class Transition:
    def __init__(self, sources, target, trigger, a, b):
        self.sources, self.target, self.trigger, self.a, self.b = sources, target, trigger, a, b


class State:
    def __init__(self, raw):
        self.raw = raw
        node = Node(raw)
        self.chains = [c for c in node.children if c.role == "chain"]
        self.items = [c for c in node.children if c.role == "item"]      # child states of a graph
        self.is_graph = raw.get("vt") == GRAPH
        self.locals = _variables(raw["fields"])
        self.transitions = _transitions(raw, node) if self.is_graph else []
        self.states = [State(c) for c in raw["children"] if c.get("via") == "0x44E8E2"
                       and c.get("vt") in (GRAPH, STATE)] if self.is_graph else []


def _variables(fields):
    """Name table of a variable block: hash/slot pairs, then the names."""
    pairs, names = [], []
    for i, f in enumerate(fields):
        if f[2] == VAR_HASH and i + 1 < len(fields) and fields[i + 1][2] == VAR_SLOT:
            pairs.append((f[3], fields[i + 1][3]))
        elif f[2] == NAME_CHARS and isinstance(f[3], str):
            names.append(f[3].rstrip("\0"))
    by_hash = {elf_hash(n): n for n in names}
    return {h: (by_hash.get(h, f"var_{h:08x}"), slot) for h, slot in pairs}


def _transitions(raw, node):
    fields = raw["fields"]
    triggers = [c for c in node.children if c.role == "trigger"]
    out, i, k = [], 0, 0
    while i < len(fields):
        if fields[i][2] == T_SOURCES_COUNT:
            n = fields[i][3]
            sources = [fields[i + 1 + j][3] for j in range(n)]
            i += 1 + n
            target = fields[i][3] if fields[i][2] == T_TARGET else None
            trig_type = fields[i + 1][3] if fields[i + 1][2] == T_TRIGGER else 0
            trigger = None
            if trig_type:
                trigger = triggers[k] if k < len(triggers) else None
                k += 1
            # the two trailing u32 follow the trigger's own fields
            j = i + 2
            while j < len(fields) and fields[j][2] != T_A:
                j += 1
            a = fields[j][3] if j < len(fields) else None
            b = fields[j + 1][3] if j + 1 < len(fields) else None
            out.append(Transition(sources, target, trigger, a, b))
            i = j + 2
            continue
        i += 1
    return out


class Script:
    def __init__(self, raw):
        self.raw = raw
        self.did = int(raw["id"], 16)
        self.status = raw.get("status")
        self.graphs = [State(c) for c in raw["children"] if c.get("vt") == GRAPH]
        self.variables = _variables(raw["fields"])
        self.names = {}
        self._collect_names(raw)

    def _collect_names(self, raw):
        for f in raw["fields"]:
            if isinstance(f[3], str):
                for m in re.finditer(r"[A-Za-z_][A-Za-z0-9_]{2,}", f[3]):
                    self.names[elf_hash(m.group(0))] = m.group(0)
        for c in raw["children"]:
            self._collect_names(c)


def load(did, trees=TREES):
    path = os.path.join(trees, f"{did:08x}.json")
    with open(path, encoding="utf-8") as f:
        return Script(json.load(f))


# --- description -----------------------------------------------------------------------------------

def describe_expr(n, names):
    if n.vt == "0x15A9D38" and n.operands:
        return n.operands[0].describe(names)
    if n.vt == "0x15A8F18":
        v = n.values[-1] if n.values else 0
        if isinstance(v, int):
            f = _float(v)
            return f"{f:g}" if f is not None else str(v)
        return repr(v)
    kids = [describe_expr(c, names) for c in n.children if c.role != "next"]
    op = n.name()
    if len(kids) == 2:
        return f"({kids[0]} {op} {kids[1]})"
    return f"{op}({', '.join(kids)})"


def describe_node(n, names, depth, out):
    pad = "    " * depth
    if n.vt in EXPR:
        out.append(pad + describe_expr(n, names))
        return
    ops = ", ".join(o.describe(names) for o in n.operands)
    vals = " ".join(f"{v:#x}" if isinstance(v, int) and v > 0xFFFF else str(v) for v in n.values)
    out.append(pad + f"{n.name()}({ops})" + (f" [{vals}]" if vals else ""))
    for c in n.children:
        if c.role == "next":
            continue
        describe_node(c, names, depth + 1, out)


def describe_state(s, names, depth, out, index=None):
    pad = "    " * depth
    kind = "graph" if s.is_graph else "state"
    head = f"{pad}{kind}" + (f" S{index}" if index is not None else "")
    if s.locals:
        head += "  locals: " + ", ".join(f"{n}@{slot:#x}" for n, slot in s.locals.values())
    out.append(head)
    for k, ch in enumerate(s.chains):
        out.append(f"{pad}  chain {k}:")
        for n in ch.chain():
            describe_node(n, names, depth + 2, out)
    for i, sub in enumerate(s.states):
        describe_state(sub, names, depth + 1, out, i)
    for i, t in enumerate(s.transitions):
        src = ",".join(f"S{x}" for x in t.sources) or "any"
        trig = "immediately" if t.trigger is None else describe_trigger(t.trigger, names)
        out.append(f"{pad}  T{i}: {src} -> S{t.target} on {trig}  [{t.a}, {t.b}]")


def describe_trigger(n, names):
    lines = []
    describe_node(n, names, 0, lines)
    return " / ".join(x.strip() for x in lines)


def describe(script):
    out = [f"script {script.did:#010x} ({script.status})"]
    if script.variables:
        out.append("  variables: " + ", ".join(f"{n}@{slot:#x}" for n, slot in script.variables.values()))
    for i, g in enumerate(script.graphs):
        describe_state(g, script.names, 1, out, i)
    return "\n".join(out)


if __name__ == "__main__":
    import sys
    for a in sys.argv[1:]:
        print(describe(load(int(a, 16))))
        print()
