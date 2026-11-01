"""Runs the original server's scripts (records 0x34) from their decoded model (icserver/scriptvm.py).

Execution model (from the decoded structure; see docs/reverse-engineering.md, "Script VM object model"):
  - a script's top-level graphs run in parallel; a graph is a state machine whose states run their action
    chain 0 when entered (chain 1 looks like the exit chain);
  - a chain runs its nodes in order; a node may be latent (it waits, e.g. a cast or a delay), which suspends
    the chain until the node finishes;
  - when a state's chain ends it reports a result code; transitions fire on that code (trigger 0x10000019,
    "chain result N"), on an event (0x1000013B / 0x10000055 / event nodes / event lists), on a condition, or
    immediately (no trigger). Transitions with no source states apply from any state.
  - structural nodes: assignment (var = expression), "if" lists (items run when the condition holds), loops
    (while the condition holds), all/any condition lists, expression conditions, node predicates.
What each action node does is our reading of the data (variable names, scriptlet keys, stats) and of the client's
code. The result codes (5 = cast point reached, 3 = cast finished, 2 = done or interrupted) are an inference from
600+ transitions and have to be confirmed in game.

The game side is a World object (NullWorld documents the interface). The tutorial provides the real one
(icserver/scriptvm_world.py); NullWorld logs everything for the command-line simulation:

    python -m icserver.scriptvm_runtime 0x3400003B      simulate one Sonic Batarang (skill + its missile)
"""
import heapq
import math
import struct

from . import scriptvm as V

# result codes reported by a finished chain (trigger 0x10000019 with enum 0x1000000F)
RESULT_DONE, RESULT_CAST_DONE, RESULT_CAST_POINT = 2, 3, 5
EVENT_ACTIVATE = 0x1000001D          # skill used (trigger 0x1000013B in the skill's main graph)
EVENT_SPAWN = 0x10000049             # a missile was created (missile script: start)
EVENT_COLLISION = 0x10000002         # a missile reached an entity (trigger 0x10000055)
EVENT_EXPIRED = 0x10000035           # a missile ran out of range / time
MARKER_HIT = 0x100003AB              # "already hit by this missile" marker (0x1000006A)

# words taken by a variable's default value, by variable type (server-only block in the packs)
DEFAULT_WORDS = {7: 2, 8: 2, 9: 3, 0xA: 3, 0xD: 2, 0xE: 2}

# structural classes (decoder vtables)
VT_ASSIGN, VT_LIST, VT_LOOP, VT_ALL, VT_ANY = "0x15A89C0", "0x15A8B68", "0x15A8B98", "0x15A8ADC", "0x15A8B0C"
VT_COND, VT_NODECOND, VT_EVENT = "0x15A8764", "0x15A890C", "0x15A8794"
EXPR_OPS = dict(V.EXPR)
EXPR_OPS.update({"0x15A9050": ">=", "0x15A9328": "bool", "0x15A9088": "<=", "0x15A8FE0": ">", "0x15A9C20": "vec+"})
SERVER_EXPR = {"server-expr:0x10": "or", "server-expr:0xc": "/"}


def f32(v):
    if isinstance(v, float):
        return v
    if isinstance(v, int):
        return struct.unpack("<f", struct.pack("<I", v & 0xFFFFFFFF))[0]
    return 0.0


def num(v):
    """A variable value as a number (raw u32 floats from literals are converted)."""
    if isinstance(v, bool):
        return float(v)
    if isinstance(v, (int,)) and v > 0xFFFFF:
        return f32(v)
    if isinstance(v, (int, float)):
        return float(v)
    return 0.0


class NullWorld:
    """World interface, logging only (simulation)."""

    def __init__(self, log=print):
        self.log = log
        self.time = 0.0
        self.timers = []
        self.seq = 0
        self.entities = {"Batman": (0.0, 0.0, 0.0), "Drone": (8.0, 0.0, 0.0), "Drone2": (10.0, 3.0, 0.0)}
        self.health = {"Drone": 300.0, "Drone2": 300.0}
        self.missiles = []

    # time
    def after(self, seconds, fn):
        self.seq += 1
        heapq.heappush(self.timers, (self.time + seconds, self.seq, fn))

    def run_until(self, until):
        while self.timers and self.timers[0][0] <= until:
            t, _, fn = heapq.heappop(self.timers)
            self.time = max(self.time, t)
            fn()
        self.time = max(self.time, until)

    # data
    def skill_stat(self, owner, stat, rank):
        base = {3: -40.0, 5: 60.0, 15: 5.0, 18: 9.0, 30: 14.0, 17: 4.0, 22: 1.25, 2: 1.0}.get(stat, 0.0)
        per = {5: 25.0, 2: 1.0, 3: -10.0}.get(stat, 0.0)
        return base + per * (rank - 1)

    def skill_rank(self, owner):
        return 1

    # entities
    def position(self, ent):
        return self.entities.get(ent, (0.0, 0.0, 0.0)) if not isinstance(ent, tuple) else ent

    def alive(self, ent):
        return ent in self.entities and self.health.get(ent, 1.0) > 0

    def hostile(self, a, b):
        return a != b and (a == "Batman") != (b == "Batman")

    def kind_matches(self, ent, flags):
        return flags & 0x100 != 0 and ent != "Batman"       # 0x10108: champions + minions

    def find_targets(self, center, radius, flags):
        c = self.position(center)
        return [e for e in self.entities if e != "Batman" and self.alive(e)
                and math.dist(self.position(e)[:2], c[:2]) <= radius]

    def has_status(self, ent, status):
        return False

    # actions
    def face(self, owner, target):
        self.log(f"[{self.time:6.2f}]   face {target}")

    def run_scriptlet(self, ent, key, target=None):
        self.log(f"[{self.time:6.2f}]   scriptlet {key:#x} on {ent}" + (f" (target {target})" if target else ""))

    def start_cooldown(self, owner, seconds):
        self.log(f"[{self.time:6.2f}]   cooldown {seconds:g} s")

    def spend(self, owner, amount):
        self.log(f"[{self.time:6.2f}]   spend {amount:g} Will")

    def damage(self, source, target, amount):
        self.health[target] = self.health.get(target, 0.0) - amount
        self.log(f"[{self.time:6.2f}]   damage {amount:g} to {target} (health {self.health[target]:g})")

    def cast_time(self, owner):
        return 0.25

    def launch_missile(self, owner, missile_class, target, speed, max_range, scripts):
        m = Missile(self, owner, missile_class, target, speed, max_range, scripts)
        self.missiles.append(m)
        m.start()

    def missile_moved(self, missile, target):
        self.log(f"[{self.time:6.2f}]   missile -> {target}")


class Missile:
    """A missile simulated on the server: it flies straight to its target and raises collision events
    on its scripts; it expires when the target is gone or out of range."""

    def __init__(self, world, owner, missile_class, target, speed, max_range, scripts):
        self.world, self.owner, self.cls = world, owner, missile_class
        self.speed = max(speed, 1.0)
        self.max_range = max_range
        self.pos = world.position(owner)
        self.flown = 0.0
        self.alive = True
        self.instances = [Instance(s, self, world, {"ShooterIID": owner}) for s in scripts]
        self.target = target
        self.trip = 0

    def start(self):
        for inst in self.instances:
            inst.start()
            inst.event(EVENT_SPAWN)
        self.fly_to(self.target)

    def fly_to(self, target):
        self.target = target
        self.trip += 1
        trip = self.trip
        dest = self.world.position(target)
        dist = math.dist(self.pos[:2], dest[:2])
        if self.max_range and self.flown + dist > self.max_range * 1.5 + 1.0:
            self.world.after(max(0.05, (self.max_range - self.flown) / self.speed), lambda: self.expire(trip))
            return
        self.world.after(dist / self.speed, lambda: self.arrive(trip, target, dist))

    def arrive(self, trip, target, dist):
        if not self.alive or trip != self.trip:
            return
        self.pos = self.world.position(target)
        self.flown += dist
        if isinstance(target, tuple) or not self.world.alive(target):
            self.expire(trip)
            return
        for inst in self.instances:
            inst.event(EVENT_COLLISION, {"Collider": target, "SubEntity": 0, "EntityPosition": self.pos,
                                         0xAE98CBC: 0})          # 0xAE98CBC -> EtherealCollision: a solid hit
        # nothing redirected the missile: it is done
        if self.trip == trip and self.alive:
            self.world.after(0.0, lambda: self.end(trip))

    def expire(self, trip):
        if self.alive and trip == self.trip:
            for inst in self.instances:
                inst.event(EVENT_EXPIRED)
            self.end(trip)

    def end(self, trip):
        if self.alive and trip == self.trip:
            self.alive = False
            self.world.log(f"[{self.world.time:6.2f}]   missile {self.cls:#x} gone")

    def redirect(self, target):
        if self.alive and target:
            self.world.missile_moved(self, target)
            self.fly_to(target)

    def __repr__(self):
        return f"missile {self.cls:#x}"


class Instance:
    """One running script on one entity."""

    def __init__(self, script, owner, world, request=None):
        self.script, self.owner, self.world = script, owner, world
        self.vars = {}
        self.request = dict(request or {})
        self.markers = set()
        self.detected = []
        self.current_event = None
        self.params = {}
        self.unknown = set()
        self._defaults()
        for name, value in self.request.items():
            self.vars_by_name(name, value)
        self.regions = [Region(self, g) for g in script.graphs]

    def _defaults(self):
        """Default values from the server-only blocks, matched to each variable block by offset."""
        blocks = []
        for node in [self.script.raw] + list(_walk(self.script.raw)):
            pairs = [(f[0], f[3], node["fields"][i + 1][3]) for i, f in enumerate(node["fields"])
                     if f[2] == V.VAR_HASH and i + 1 < len(node["fields"])]
            if pairs:
                blocks.append(pairs)
        for d in self.script.raw.get("defaults", []):
            block = min((b for b in blocks if b[0][0] > d["offset"]), key=lambda b: b[0][0] - d["offset"], default=None)
            if not block:
                continue
            ordered = sorted((slot, h) for _o, h, slot in block)
            words, k = d["words"], 0
            for (slot, h), typ in zip(ordered, d["types"]):
                n = DEFAULT_WORDS.get(typ, 1)
                w = words[k:k + n]
                k += n
                if typ == 3:
                    self.vars.setdefault(h, f32(w[0]) if w else 0.0)
                elif typ == 9:
                    self.vars.setdefault(h, tuple(f32(x) for x in w))
                elif typ == 0xD:
                    self.vars.setdefault(h, w[-1] if w else 0)
                elif typ in (1, 2, 0):
                    self.vars.setdefault(h, w[0] if w else 0)
                else:
                    self.vars.setdefault(h, 0)

    # --- lifecycle
    def start(self):
        for r in self.regions:
            r.start()

    def event(self, ev, params=None):
        """Deliver an event; params (name -> value) are what SetVariable(var, #name) reads."""
        self.params = {V.elf_hash(k) if isinstance(k, str) else k: v for k, v in (params or {}).items()}
        try:
            for r in self.regions:              # each top-level graph sees the event
                self.current_event = ev
                r.event(ev)
        finally:
            self.current_event = None

    def after(self, seconds, fn):
        self.world.after(seconds, fn)

    # --- values
    def name(self, h):
        return self.script.names.get(h, f"{h:#x}")

    def vars_by_name(self, name, value):
        self.vars[V.elf_hash(name)] = value

    def var_by_name(self, name, default=None):
        return self.vars.get(V.elf_hash(name), default)

    def get(self, op):
        if op is None:
            return None
        if op.is_self():
            return self.owner
        if op.source == V.UNSET:
            return None if op.value == 0 else op.value
        if op.value in self.vars:
            return self.vars[op.value]
        if op.source == 1 and op.slot == 0 and op.value not in self.script.names:
            return op.value                 # literal held in a "value | 1 | 0" operand
        return 0

    def set(self, op, value):
        if op is not None and not op.is_unset():
            self.vars[op.value] = value

    def evaluate(self, n):
        op = SERVER_EXPR.get(n.type) or EXPR_OPS.get(n.vt)
        kids = [c for c in n.children if c.role != "next"]
        if op == "var":
            return self.get(n.operands[0]) if n.operands else 0
        if op == "const":
            v = n.values[-1] if n.values else 0
            if isinstance(v, str):
                return 0
            return v
        if n.vt == VT_COND:
            return bool(self.truth(self.evaluate(kids[0]))) if kids else False
        vals = [self.evaluate(c) for c in kids]
        a = vals[0] if vals else 0
        b = vals[1] if len(vals) > 1 else 0
        if op in ("+", "-", "*", "/", "max", "<", ">", "<=", ">="):
            x, y = num(a), num(b)
            if op == "+":
                return x + y
            if op == "-":
                return x - y
            if op == "*":
                return x * y
            if op == "/":
                return x / y if y else 0.0
            if op == "max":
                return max(x, y)
            return {"<": x < y, ">": x > y, "<=": x <= y, ">=": x >= y}[op]
        if op == "++":
            return num(a) + 1
        if op == "==":
            return _same(a, b)
        if op == "!=":
            return not _same(a, b)
        if op == "not":
            return not self.truth(a)
        if op == "bool":                            # 0x24: "is zero" (0x44f500), i.e. logical not
            return not self.truth(a)
        if op == "or":
            return self.truth(a) or self.truth(b)
        if op == "vec3":
            return tuple(num(x) for x in vals[:3])
        if op == "vec+":
            return tuple(p + q for p, q in zip(_vec(a), _vec(b)))
        if op == "length":
            return math.sqrt(sum(x * x for x in _vec(a)))
        self.unknown.add(f"expr {n.type}")
        return a

    def truth(self, v):
        if isinstance(v, tuple):
            return any(v)
        return bool(v)

    def condition(self, n):
        """Evaluate a condition node: all / any lists, expression conditions, node predicates, events."""
        if n is None:
            return True
        kids = [c for c in n.children if c.role != "next"]
        if n.vt == VT_ALL:
            return all(self.condition(c) for c in kids)
        if n.vt == VT_ANY:
            return any(self.condition(c) for c in kids)
        if n.vt == VT_COND:
            return self.evaluate(n)
        if n.vt == VT_EVENT:
            return self.current_event is not None and n.values and self.current_event == n.values[-1]
        if n.vt == VT_NODECOND:                     # NOT(node predicate); no node -> false
            return (not self.predicate(n.next)) if n.next is not None else False
        return self.predicate(n)

    def predicate(self, n):
        t = n.type_id
        h = PREDICATES.get(t)
        if h:
            return bool(h(self, n, n.operands))
        if n.vt in (VT_ALL, VT_ANY, VT_COND, VT_NODECOND, VT_EVENT):
            return self.condition(n)
        if n.vt == "0x15A89F0":             # builtin 0x10: meaning unknown; the missile's "NOT(it) -> end" says true
            return True
        self.unknown.add(f"predicate {n.name()}")
        return False


def _applies_damage(state):
    def walk(n):
        if n.type_id == 0x1000001D:
            return True
        return any(walk(c) for c in n.children)
    return any(walk(n) for ch in state.chains for n in ch.chain())


def _walk(raw):
    for c in raw["children"]:
        yield c
        yield from _walk(c)


def _vec(v):
    if isinstance(v, tuple):
        return v
    return (num(v), 0.0, 0.0)


def _same(a, b):
    if a in (None, 0) and b in (None, 0):
        return True
    return a == b


class Region:
    """A graph (state machine) running inside an instance."""

    def __init__(self, inst, graph, parent=None):
        self.inst, self.graph, self.parent = inst, graph, parent
        self.state = None
        self.child = None
        self.steps = 0

    def start(self):
        self.enter(0)

    def log(self, text):
        w = self.inst.world
        w.log(f"[{w.time:6.2f}] {self.inst.script.did:#x} {text}")

    def enter(self, index):
        inst = self.inst
        if (isinstance(inst.owner, Missile) and self.state is not None and self.state < len(self.graph.states)
                and _applies_damage(self.graph.states[self.state])):
            # assumption (2026-10-20): a target hit counts as a collision, so MaxCollisions limits the
            # ricochets and the damage falloff (1 - NumCollisions x reduction) applies
            inst.vars_by_name("NumCollisions", num(inst.var_by_name("NumCollisions", 0)) + 1)
        self.steps += 1
        if self.steps > 500:                # runaway guard
            self.log("too many transitions, stopped")
            return
        self.state = index
        st = self.graph.states[index] if index < len(self.graph.states) else None
        self.log(f"enter S{index}")
        self.child = None
        if st is None:
            return
        if st.is_graph:
            self.child = Region(inst, st, self)
            self.child.start()
        if st.chains:
            Chain(inst, st.chains[0], lambda code: self.finished(index, code)).run()
        else:
            self.finished(index, RESULT_DONE)

    def finished(self, index, code):
        if self.state != index:
            return
        self.check(code=code)

    def check(self, code=None, use_event=False):
        """Fire the first transition that matches. An event can fire one transition only: it is consumed
        before the target state runs, so a state entered because of it does not see it again."""
        inst = self.inst
        saved = inst.current_event
        if not use_event:
            inst.current_event = None
        fired = None
        for i, t in enumerate(self.graph.transitions):
            if t.sources and self.state not in t.sources:
                continue
            if self.matches(t, code):
                fired = (i, t)
                break
        if fired is None:
            inst.current_event = saved
            return False
        i, t = fired
        self.log(f"S{self.state} -> S{t.target} (T{i})")
        inst.current_event = None if use_event else saved
        if use_event:
            inst.event_consumed = True
        self.enter(t.target)
        if not use_event:
            inst.current_event = saved
        return True

    def matches(self, t, code):
        inst, trig = self.inst, t.trigger
        if trig is None:
            return code is not None
        typ = trig.type_id
        if typ == 0x10000019:
            return code is not None and trig.values and code == trig.values[-1]
        if typ in (0x1000013B, 0x10000055):
            return inst.current_event is not None and trig.values and inst.current_event == trig.values[-1]
        if trig.vt == VT_EVENT:
            return inst.current_event is not None and trig.values and inst.current_event == trig.values[-1]
        if trig.vt in (VT_ALL, VT_ANY, VT_COND, VT_NODECOND):
            return inst.condition(trig)
        return False

    def event(self, ev):
        if self.child and self.child.event(ev):
            return True
        return self.check(use_event=True)


class Chain:
    """Runs a node chain; latent nodes call resume() later."""

    def __init__(self, inst, first, done):
        self.inst, self.done = inst, done
        self.nodes = list(first.chain())
        self.i = 0
        self.result = RESULT_DONE
        self.delay = 0.0                    # the result is reported this much later (cast point)

    def run(self):
        while self.i < len(self.nodes):
            n = self.nodes[self.i]
            self.i += 1
            if execute(self.inst, n, self):
                return
        if self.delay > 0:
            self.inst.after(self.delay, lambda: self.done(self.result))
        else:
            self.done(self.result)

    def resume(self):
        self.run()


def run_nodes(inst, first, chain):
    """Run a nested chain (items of a list, a loop body) synchronously; latent nodes inside are not waited."""
    n = first
    while n is not None:
        execute(inst, n, chain)
        n = n.next


def execute(inst, n, chain):
    """Run one node. Returns True when the node finishes later (latent)."""
    t = n.type_id
    if n.vt == VT_ASSIGN:
        value = next((c for c in n.children if c.role == "value"), None)
        inst.set(n.operands[0] if n.operands else None, inst.evaluate(value) if value else 0)
        return False
    if n.vt == VT_LIST:
        # three fixed slots and a condition: values = [3, type then, type else, type always, type condition]
        cond = next((c for c in n.children if c.raw_via == "0x46001A"), None)
        subs = [c for c in n.children if c.raw_via == "0x45FC62"]
        kinds = [v for v in n.values[1:4]] if len(n.values) >= 4 else [1, 0, 0]
        slots, k = [None, None, None], 0
        for i, kind in enumerate(kinds):
            if kind and k < len(subs):
                slots[i] = subs[k]
                k += 1
        ok = cond is None or inst.condition(cond)
        if ok and slots[0] is not None:
            run_nodes(inst, slots[0], chain)
        if not ok and slots[1] is not None:
            run_nodes(inst, slots[1], chain)
        if slots[2] is not None:
            run_nodes(inst, slots[2], chain)
        return False
    if n.vt == VT_LOOP:
        cond = next((c for c in n.children if c.raw_via == "0x46001A"), None)
        body = next((c for c in n.children if c.raw_via == "0x45FC62"), None)
        guard = 0
        while body is not None and inst.condition(cond) and guard < 256:
            run_nodes(inst, body, chain)
            guard += 1
        return False
    if n.vt in EXPR_OPS or n.type in SERVER_EXPR:
        inst.evaluate(n)
        return False
    h = HANDLERS.get(t) if t is not None else None
    if h:
        return h(inst, n, n.operands, chain)
    if t in PREDICATES:
        PREDICATES[t](inst, n, n.operands)
        return False
    inst.unknown.add(n.name())
    return False


# --- action nodes -----------------------------------------------------------------------------------

def _subs(inst, n, chain):
    for c in n.children:
        if c.role == "sub":
            run_nodes(inst, c, chain)


def _init_skill(inst, n, ops, chain):            # 0x10000050: InitSkill(SkillRank[, owner])
    owner = inst.get(ops[1]) if len(ops) > 1 else inst.owner
    inst.set(ops[0] if ops else None, inst.world.skill_rank(owner if owner else inst.owner))
    _subs(inst, n, chain)
    return False


def _load_stats(inst, n, ops, chain):            # 0x1000009F: LoadSkillStats(owner, vars...); values = count, stats
    vals = [v for v in n.values if isinstance(v, int)]
    if not vals:
        return False
    count = vals[0]
    stats = vals[1:1 + count]
    owner = inst.get(ops[0]) if ops and not ops[0].is_unset() else None
    if isinstance(inst.owner, Missile):
        owner = inst.owner.owner
    owner = owner or inst.owner
    rank = inst.var_by_name("SkillRank", None) or inst.world.skill_rank(owner)
    for stat, op in zip(stats, ops[1:1 + count]):
        inst.set(op, inst.world.skill_stat(owner, stat, int(rank) if isinstance(rank, (int, float)) else 1))
    return False


def _face(inst, n, ops, chain):                  # 0x1000003F: FaceTarget(target, -, FacingIDVariable)
    target = inst.get(ops[0]) if ops else None
    if target:
        inst.world.face(inst.owner, target)
    return False


def _scriptlet(inst, n, ops, chain):             # 0x10000034: RunScriptlet(entity) [key]
    key = next((v for v in n.values if isinstance(v, int) and v >= 0x10000000), None)
    ent = inst.get(ops[0]) if ops else inst.owner
    if isinstance(ent, Missile):
        return False                        # the missile is server-side only: no client object to play on
    if key:
        inst.world.run_scriptlet(ent if ent is not None else inst.owner, key, target=inst.var_by_name("TargetIID"))
    return False


def _set_value(inst, n, ops, chain):             # 0x100000E2: Set(var, value) [value]
    if ops:
        inst.set(ops[0], n.values[-1] if n.values else 1)
    _subs(inst, n, chain)
    return False


def _cast(inst, n, ops, chain):                  # 0x10000026: Cast(TargetIID, TargetPosition)
    """Fills the targets from the skill use. The chain goes on at once (face the target, play the cast
    animation); when it ends, its result is the cast point (5), reported cast_time() seconds later."""
    for name, op in zip(("TargetIID", "TargetPosition"), ops):
        if name in inst.request:
            inst.set(op, inst.request[name])
    _subs(inst, n, chain)
    chain.result = RESULT_CAST_POINT
    chain.delay = max(chain.delay, inst.world.cast_time(inst.owner))
    return False


def _missile(inst, n, ops, chain):               # 0x1000005E: LaunchMissile(-, target, range, speed, -, offset)
    cls = next((v for v in n.values if isinstance(v, int) and v >> 24 == 0x40), None)
    target = inst.get(ops[1]) if len(ops) > 1 else None
    rng = num(inst.get(ops[2])) if len(ops) > 2 else 0.0
    speed = num(inst.get(ops[3])) if len(ops) > 3 else 0.0
    if target:
        inst.world.launch_missile(inst.owner, cls, target, speed, rng, missile_scripts(cls))
    return False


def _cooldown(inst, n, ops, chain):              # 0x10000007: StartCooldown(duration)
    inst.world.start_cooldown(inst.owner, num(inst.get(ops[0])) if ops else 0.0)
    _subs(inst, n, chain)
    return False


def _spend(inst, n, ops, chain):                 # 0x10000031: Spend(amount, entity) [resource]
    amount = num(inst.get(ops[0])) if ops else 0.0
    inst.world.spend(inst.owner, -amount)
    _subs(inst, n, chain)
    return False


def _delay(inst, n, ops, chain):                 # 0x10000010: Delay(entity, seconds)
    secs = num(n.operands[1].value) if len(ops) > 1 and ops[1].source in (1, V.UNSET) else 0.0
    inst.after(max(0.0, secs), chain.resume)
    return True


def _damage(inst, n, ops, chain):                # 0x1000001D: ApplyEffects(magnitude, target, ...)
    amount = num(inst.get(ops[0])) if ops else 0.0
    target = inst.get(ops[1]) if len(ops) > 1 else None
    source = inst.owner.owner if isinstance(inst.owner, Missile) else inst.owner
    if target and amount > 0:
        inst.world.damage(source, target, amount)
    return False


def _mark(inst, n, ops, chain):                  # 0x1000006A: Mark(target, marker): "hit by this missile"
    target = inst.get(ops[0]) if ops else None
    if target:
        inst.markers.add(target)
    return False


def _find_targets(inst, n, ops, chain):          # 0x10000047: FindTargetsInRadius(radius, ..., count) [flags]
    radius = num(inst.get(ops[0])) if ops else 0.0
    flags = next((v for v in n.values if isinstance(v, int) and v > 0xFF), 0)
    center = inst.owner.pos if isinstance(inst.owner, Missile) else inst.world.position(inst.owner)
    found = [e for e in inst.world.find_targets(center, radius, flags)]
    inst.detected = found
    count_op = next((o for o in reversed(ops) if not o.is_unset()), None)
    if count_op is not None and count_op is not ops[0]:
        inst.set(count_op, len(found))
    return False


def _detected(inst, n, ops, chain):              # 0x10000024: GetDetected(out entity, index)
    idx = int(num(inst.get(ops[1]))) if len(ops) > 1 else 0
    inst.set(ops[0] if ops else None, inst.detected[idx] if 0 <= idx < len(inst.detected) else 0)
    return False


def _offset(inst, n, ops, chain):                # 0x1000005A: Offset(from, to, out vector)
    a = inst.get(ops[0]) if ops else None
    b = inst.get(ops[1]) if len(ops) > 1 else None
    pa = inst.owner.pos if isinstance(a, Missile) else inst.world.position(a)
    pb = inst.world.position(b)
    if len(ops) > 2:
        inst.set(ops[2], tuple(q - p for p, q in zip(pa, pb)))
    return False


def _redirect(inst, n, ops, chain):              # 0x10000062: RedirectMissile(target, ...)
    target = inst.get(ops[0]) if ops else None
    if isinstance(inst.owner, Missile) and target:
        inst.owner.redirect(target)
    return False


def _set_variable(inst, n, ops, chain):          # 0x10000058: SetVariable(var, value | #event parameter)
    if not ops:
        return False
    src = ops[1] if len(ops) > 1 else None
    if src is not None and src.source == V.UNSET and src.value in inst.params:
        inst.set(ops[0], inst.params[src.value])
    elif src is not None and src.source == V.UNSET and src.value in inst.script.names:
        inst.set(ops[0], 0)                 # an event parameter this event does not carry
    else:
        inst.set(ops[0], inst.get(src) if src is not None else 0)
    return False


def _noop(inst, n, ops, chain):
    _subs(inst, n, chain)
    return False


HANDLERS = {
    0x10000050: _init_skill, 0x1000009F: _load_stats, 0x1000003F: _face, 0x10000034: _scriptlet,
    0x100000E2: _set_value, 0x10000026: _cast, 0x1000005E: _missile, 0x10000007: _cooldown,
    0x10000031: _spend, 0x10000010: _delay, 0x1000001D: _damage, 0x1000006A: _mark,
    0x10000058: _set_variable, 0x10000047: _find_targets, 0x10000024: _detected, 0x1000005A: _offset, 0x10000062: _redirect,
    0x1000000E: _noop,      # no fields; starts the cast state
    0x1000006F: _noop,      # missile end state, before its Delay
    0x10000070: _noop,      # after the missile stats are loaded
    0x10000114: _noop,      # after a redirect
    0x10000195: _noop, 0x10000057: _noop, 0x10000097: _noop, 0x1000000A: _noop,
}


# --- predicates (used as conditions) -----------------------------------------------------------------

def _alive(inst, n, ops):                        # 0x1000003E: IsAlive(entity)
    e = inst.get(ops[0]) if ops else None
    return bool(e) and inst.world.alive(e)


def _valid(inst, n, ops):                        # 0x1000001E: IsValid(entity)
    return bool(inst.get(ops[0])) if ops else False


def _kind(inst, n, ops):                         # 0x10000029: IsKind(entity) [flags: 0x10108 units, 0x1000 props]
    e = inst.get(ops[0]) if ops else None
    flags = next((v for v in n.values if isinstance(v, int)), 0)
    return bool(e) and inst.world.kind_matches(e, flags)


def _hostile(inst, n, ops):                      # 0x10000028: Relation(a, b) [3 = hostile]
    a = inst.get(ops[0]) if ops else None
    b = inst.get(ops[1]) if len(ops) > 1 else None
    if isinstance(a, Missile):
        a = a.owner
    return bool(a) and bool(b) and inst.world.hostile(a, b)


def _valid_position(p):                          # 0x10000014: IsValidPosition(point): a ground-targeted use
    return isinstance(p, tuple) and any(abs(x) > 1e-6 for x in p)


def _angle(inst, n, ops):                        # 0x10000052: AngleTest(...): accepted
    return True


def _has_marker(inst, n, ops):                   # 0x1000006A: HasStatus(entity, 0x100003AB): bonus damage mark
    e = inst.get(ops[0]) if ops else None
    status = next((v for v in n.values if isinstance(v, int)), 0)
    return bool(e) and inst.world.has_status(e, status)


PREDICATES = {
    0x1000003E: _alive, 0x1000001E: _valid, 0x10000029: _kind, 0x10000028: _hostile, 0x10000052: _angle,
    0x1000006A: _has_marker,
    0x10000014: lambda inst, n, ops: _valid_position(inst.get(ops[0]) if ops else None),
}


# --- missile classes -> scripts (the class's twin record 0x49 lists them) ---------------------------

MISSILE_SCRIPTS = {0x40000090: (0x3400003F,)}     # Sonic Batarang (0x340001A6 = props' destruction impulse)


def missile_scripts(cls):
    out = []
    for did in MISSILE_SCRIPTS.get(cls, ()):
        try:
            out.append(V.load(did))
        except OSError:
            pass
    return out


def use_skill(script, owner, world, target=None, point=None):
    """Start a skill script on its owner and send it the 'skill used' event."""
    request = {}
    if target is not None:
        request["TargetIID"] = target
    if point is not None:
        request["TargetPosition"] = point
    inst = Instance(script, owner, world, request)
    inst.start()
    inst.event(EVENT_ACTIVATE)
    return inst


if __name__ == "__main__":
    import sys
    did = int(sys.argv[1], 16) if len(sys.argv) > 1 else 0x3400003B
    w = NullWorld()
    inst = use_skill(V.load(did), "Batman", w, target="Drone")
    w.run_until(5.0)
    unknown = set(inst.unknown)
    for m in w.missiles:
        for i in m.instances:
            unknown |= i.unknown
    if unknown:
        w.log("not implemented: " + ", ".join(sorted(map(str, unknown))))
