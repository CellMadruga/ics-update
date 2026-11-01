"""Server-side behaviour-graph emulator (BGE): the champions' cast signals from their own Havok graphs.

2026-10-27 (docs/re-notes/skill-execution-model.md 2 / 6, C for the client pipeline and the data, P that the original
server ran the same engine code): every skill state of a champion graph carries turbineEventHookPayload {DID, code};
the engine turns each one into event 0x1000000F with parameter 0xC58BA9B = code (1 SkillStart = state enter, 2
SkillEnd = state exit, 3 Skill, 4 MissileInit, 5 MissileFire, 6 SkillHold = never delivered), posted to the script
instances whose DID is the payload's (every instance when it is 0). ics used to synthesize these with timers
(script_runtime.start_cast / _graph_cast); this module runs a reduced interpreter of the graph instead, fed with the
graph events ics already raises (RaiseGraphEvent, scriptlet 0x100001E3 + variable 0x780, scriptlet keys whose table
entries raise graph events, death / respawn / CC scriptlets).

Model (6.3 of the note):
  * active = for every top machine, its current state, and down through nested machines' current states;
  * raise(event): outermost machine first, the current state's own transitions then the machine's wildcards (flag
    0x20 = disabled; a wildcard into the current state only with flag 0x200); the first match transitions;
  * transition: exit notify events / hooks of the left states (innermost first; code 2 here, whatever the cause),
    then enter notify events / hooks of the entered state and of its nested start states (outermost first), then
    the entered states' clip triggers on the clock (scaled by attack speed where playbackSpeed is bound to it);
  * a trigger / notify event with a name is also raised in the graph (that is how states end themselves);
  * clip durations are not in the data (6.4): an end-relative trigger is timed from an estimate ([ics]
    graph_clip_seconds) and an event the current state cannot take yet but could after such a pending, estimated
    self-transition completes that transition first (the BGE never drops a script's gate for a guessed length).

data/skill_graphs.json comes from tools/skill_graphs.py.
"""
import json
import os

EVENT_CAST_SIGNAL = 0x1000000F
RAISE_EVENT_SCRIPTLET, RAISE_EVENT_VAR = 0x100001E3, 0x780
F_DISABLED, F_ALLOW_SELF = 0x20, 0x200
SELF_EVENTS = {"state_to_state", "next_animation", "skill_to_cosmetic", "skill_to_locomotion",
               "basicattack_to_basicattack", "state_to_locomotion"}
PATH = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "data", "skill_graphs.json")

# settings (ics/server.py sets them from [ics]; see ics/config.py for the reasons)
CLIP_SECONDS = 0.5           # [ics] graph_clip_seconds: assumed clip length (local s) for end-relative triggers
STATE_TIMEOUT = 5.0          # [ics] graph_state_timeout: a hooked skill state with no transition / trigger inside it
                             # for this long goes back to its machine's start state (0 = never)
FAST_FORWARD = True          # [ics] graph_fast_forward: complete an estimated self-transition for a pending gate
EARLY_OUT = True             # [ics] graph_lua_early_out: Lua early-outs (onCosmeticEarlyOut ...) when moving
SELF_DEBOUNCE = 0.05         # [ics] graph_self_debounce: s in which a repeat of the event that entered a state is no
                             # self-transition (a script raising its start event and running a scriptlet raising it too)
COSMETIC_HOLD = 0.8          # [ics] graph_cosmetic_hold: s a _Cosmetic tail (entered by skill_to_cosmetic, clip length
                             # unknown) is kept from the script's own skill_to_locomotion (0 = off; tester report
                             # 2026-10-29 12:45, docs/re-notes/skill-animations-vs-original.md 2.2)
TRACE = bool(os.environ.get("ICS_GRAPH_TRACE"))   # log every transition (debugging)
MAX_CHAIN = 64               # events handled in one burst before the rest is dropped (a loop in the data)


class GraphDef:
    """One champion graph from data/skill_graphs.json."""

    def __init__(self, name, raw, shared_scriptlets):
        self.name, self.raw = name, raw
        self.machines = raw["machines"]
        self.roots = raw["roots"]
        self.events = dict(raw.get("events") or {})                 # name -> global id
        self.by_id = {}
        for n, i in self.events.items():
            self.by_id.setdefault(int(i), n)
        self.lua_fire = raw.get("lua_fire") or {}
        self.key_events = {}
        for src in (shared_scriptlets or {}, raw.get("scriptlets") or {}):
            for k, evs in src.items():
                self.key_events[int(str(k), 0)] = [int(e) for e in evs]
        # script DID -> [(machine id, state id)] of the states whose enter hook names it (code 1)
        self.hooked = {}
        names = set()
        for m in self.machines:
            for sid, st in m["states"].items():
                for lst in (st["out"], ):
                    names.update(t["n"] for t in lst if t["n"])
                for e in st["enter"]:
                    if e.get("code") == 1 and e.get("did"):
                        self.hooked.setdefault(int(e["did"]), []).append((m["id"], int(sid)))
            names.update(t["n"] for t in m["wild"] if t["n"])
        self.taken = names                                          # events some transition waits for

    def state(self, mid, sid):
        return self.machines[mid]["states"].get(str(sid))


class GraphData:
    def __init__(self, path=PATH):
        self.graphs, self.variants, self.shared = {}, {}, {}
        try:
            with open(path, encoding="utf-8") as f:
                raw = json.load(f)
        except (OSError, ValueError):
            return
        self.shared = raw.get("shared_scriptlets") or {}
        self._raw = raw.get("graphs") or {}
        self.variants = {int(k, 16): v for k, v in (raw.get("variants") or {}).items()}

    def __len__(self):
        return len(self.variants)

    def for_variant(self, variant):
        name = self.variants.get(int(variant or 0))
        if not name or name not in self._raw:
            return None
        if name not in self.graphs:
            self.graphs[name] = GraphDef(name, self._raw[name], self.shared)
        return self.graphs[name]


_DATA = None


def data():
    global _DATA
    if _DATA is None:
        _DATA = GraphData()
    return _DATA


def _cond_true(cond, variables):
    """hkbExpressionCondition strings of the champion graphs are "Variable == number" (C, survey of 4 graphs)."""
    if not cond:
        return True
    try:
        for op in ("==", "!=", ">=", "<=", ">", "<"):
            if op in cond:
                a, b = (x.strip() for x in cond.split(op, 1))
                x, y = float(variables.get(a, 0.0)), float(b)
                return {"==": x == y, "!=": x != y, ">=": x >= y, "<=": x <= y, ">": x > y, "<": x < y}[op]
    except ValueError:
        return True
    return True


class GraphInstance:
    """One entity's running graph.

    after(seconds, fn): the world's scheduler; now(): its clock; deliver(code, did, offset, state name): a hook;
    speed(): the attack speed (attacks per second) for clips bound to Property_Attribute_AttackSpeed (or None)."""

    def __init__(self, gdef, after, now, deliver, speed=None, log=None, label=""):
        self.g, self.after, self.now, self.deliver = gdef, after, now, deliver
        self.speed = speed or (lambda: None)
        self.log = log or (lambda text: None)
        self.label = label
        self.cur = {}                     # machine id -> current state id (active machines only)
        self.entered_at = {}              # machine id -> time its current state was entered
        self.entered_by = {}              # machine id -> the event that entered its current state
        self.activity = {}                # machine id -> last transition / trigger inside its current state
        self.visit = {}                   # machine id -> visit counter (stale timers check it)
        self.pending = {}                 # machine id -> {event name: (fire time, estimated)} self-raised, not yet fired
        self.variables = {}
        self.trace = []                   # [(time, code, did, state name)] every hook fired
        self.events = []                  # [(time, event name, taken)] every event raised in the graph
        self.last_enter = {}              # script DID -> time its hooked state was last entered
        self._queue, self._busy = [], False
        self._sent = None
        self.moving = False
        for mid in self.g.roots:
            self._enter(mid, self.g.machines[mid]["start"], quiet=True)

    # --- inspection
    def active(self):
        """[(machine id, state id)] outermost first."""
        out = []

        def walk(mid):
            sid = self.cur.get(mid)
            if sid is None:
                return
            out.append((mid, sid))
            st = self.g.state(mid, sid)
            for sub in (st["body"]["sm"] if st else ()):
                walk(sub)
        for mid in self.g.roots:
            walk(mid)
        return out

    def state_names(self):
        return [self.g.state(m, s)["name"] for m, s in self.active() if self.g.state(m, s)]

    def in_state_of(self, did):
        hooked = set(self.g.hooked.get(int(did), ()))
        return any(a in hooked for a in self.active())

    def hooks_script(self, did):
        return int(did) in self.g.hooked

    # --- input
    def raise_id(self, ev):
        name = self.g.by_id.get(int(ev))
        if name is None:
            return False                  # not an event of this graph: dropped (the client's -1 rule)
        return self.raise_name(name)

    def raise_name(self, name):
        self._queue.append(name)
        if self._busy:
            return True
        self._busy = True
        try:
            n = 0
            while self._queue and n < MAX_CHAIN:
                n += 1
                self._handle(self._queue.pop(0))
            if self._queue:
                self.log(f"graph {self.label}: event loop cut ({len(self._queue)} left)")
                self._queue.clear()
        finally:
            self._busy = False
        return True

    def scriptlet(self, key, variables=None):
        """A 0x8D scriptlet on the entity: 0x100001E3 raises its 0x780 variable, other keys their 0x14 actions."""
        if key == RAISE_EVENT_SCRIPTLET:
            for v in variables or ():
                prop, value = v[0], v[-1]
                if prop == RAISE_EVENT_VAR and isinstance(value, (int, float)):
                    self.raise_id(int(value))
            return
        for ev in self.g.key_events.get(int(key), ()):
            self.raise_id(ev)

    def set_moving(self, moving):
        """Propel >= 1: the Lua early-outs of the active states fire (onCosmeticEarlyOut -> Global_Locomotion ...)."""
        moving = bool(moving)
        if moving == self.moving:
            return
        self.moving = moving
        if not (moving and EARLY_OUT):
            return
        for mid, sid in self.active():
            st = self.g.state(mid, sid)
            for fn in (st["body"]["lua"] if st else ()):
                for ev in self.g.lua_fire.get(fn, ()):
                    self.raise_name(ev)

    # --- machinery
    def _match(self, mid, name):
        sid = self.cur.get(mid)
        m = self.g.machines[mid]
        st = m["states"].get(str(sid))
        for t in (st["out"] if st else []):
            if t["n"] == name and not t["f"] & F_DISABLED and str(t["to"]) in m["states"] \
                    and _cond_true(t["c"], self.variables):
                return t
        for t in m["wild"]:
            if t["n"] != name or t["f"] & F_DISABLED or str(t["to"]) not in m["states"]:
                continue
            if t["to"] == sid and not t["f"] & F_ALLOW_SELF:
                continue
            if t["to"] == sid and SELF_DEBOUNCE and self.entered_by.get(mid) == name                     and self.now() - self.entered_at.get(mid, -1e9) < SELF_DEBOUNCE:
                return None                # the same start event twice in one tick: one entry
            if _cond_true(t["c"], self.variables):
                return t
        return None

    def _handle(self, name):
        for mid, _sid in self.active():
            t = self._match(mid, name)
            if t is not None:
                self.events.append((self.now(), name, True))
                if TRACE:
                    self.log(f"graph {self.label}: {name} -> {self.g.machines[mid]['name']} state {t['to']}")
                # the exit hook (code 2) is delivered inside the transition: the script's reaction must already see
                # the tail as playing
                self._to_cosmetic = name == "skill_to_cosmetic" and bool(COSMETIC_HOLD)
                try:
                    self._transition(mid, t["to"], name)
                finally:
                    self._to_cosmetic = False
                self.entered_by[mid] = name
                if name == "skill_to_cosmetic" and COSMETIC_HOLD:
                    self._mark_cosmetic(mid, t["to"])
                self._touch()
                return True
        if FAST_FORWARD and self._fast_forward(name):
            self.events.append((self.now(), name, True))
            return True
        self.events.append((self.now(), name, False))
        return False

    def _mark_cosmetic(self, mid, sid):
        """The skill state handed over to its _Cosmetic state (the rest of the same clip, no hooks): how long that tail
        plays (known clip length - start + the end-relative exit trigger, else COSMETIC_HOLD s)."""
        st = self.g.state(mid, sid)
        tail = COSMETIC_HOLD
        for clip in (st["body"]["clips"] if st else ()):
            if clip.get("dur"):
                speed = float(clip.get("speed") or 1.0) or 1.0
                rel = min((float(t["t"]) for t in clip["trig"] if t.get("rel")), default=0.0)
                tail = max(0.0, (float(clip["dur"]) + rel - float(clip.get("start") or 0.0)) / speed)
                break
        self.cosmetic = (mid, self.visit.get(mid), self.now() + tail)

    def in_cosmetic(self):
        """True while a _Cosmetic tail entered by skill_to_cosmetic is still playing (same visit, inside its time)."""
        if getattr(self, "_to_cosmetic", False):
            return True
        c = getattr(self, "cosmetic", None)
        if not c:
            return False
        mid, visit, until = c
        return self.visit.get(mid) == visit and self.now() < until

    def _fast_forward(self, name):
        """The event fits a state reached by an estimated (clip-length unknown) self-transition still pending."""
        for mid, _sid in self.active():
            for pend, (_t, estimated) in list(self.pending.get(mid, {}).items()):
                if not estimated:
                    continue
                t = self._match(mid, pend)
                if t is None:
                    continue
                m = self.g.machines[mid]
                nxt = m["states"].get(str(t["to"]))
                if nxt and (any(o["n"] == name for o in nxt["out"]) or any(w["n"] == name for w in m["wild"])):
                    self.log(f"graph {self.label}: {name} completes {pend} early (clip length estimated)")
                    self._transition(mid, t["to"], pend)
                    t2 = self._match(mid, name)
                    if t2 is not None:
                        self._transition(mid, t2["to"], name)
                    return True
        return False

    def _subtree(self, mid):
        """Machines active under (and including) mid, innermost first."""
        out = []

        def walk(m):
            sid = self.cur.get(m)
            st = self.g.state(m, sid) if sid is not None else None
            for sub in (st["body"]["sm"] if st else ()):
                walk(sub)
            out.append(m)
        walk(mid)
        return out

    def _transition(self, mid, to, why=""):
        # one transition delivers each (code, DID) once: a nested end state and its skill state both carry the exit
        # hook (Zod R: "end" and Kneel_Before_Zod), the script must see one code 2
        outer = self._sent is None
        if outer:
            self._sent = set()
        try:
            self._transition2(mid, to)
        finally:
            if outer:
                self._sent = None

    def _transition2(self, mid, to):
        for m in self._subtree(mid):
            sid = self.cur.pop(m, None)
            self.visit[m] = self.visit.get(m, 0) + 1
            self.pending.pop(m, None)
            st = self.g.state(m, sid) if sid is not None else None
            if st:
                self._notify(st["exit"], st["name"])
        self._enter(mid, to)

    def _touch(self):
        now = self.now()
        for m, _s in self.active():
            self.activity[m] = now

    def _enter(self, mid, sid, quiet=False):
        m = self.g.machines[mid]
        st = m["states"].get(str(sid))
        if st is None:
            return
        self.activity[mid] = self.now()
        self.cur[mid] = int(sid)
        self.entered_at[mid] = self.now()
        self.visit[mid] = visit = self.visit.get(mid, 0) + 1
        self.pending[mid] = {}
        if not quiet:
            self._notify(st["enter"], st["name"])
        for e in st["enter"]:
            if e.get("code") == 1 and e.get("did"):
                self.last_enter[int(e["did"])] = self.now()
                if STATE_TIMEOUT:
                    self.after(STATE_TIMEOUT, lambda: self._timeout(mid, visit))
        self._clips(mid, st, visit)
        for sub in st["body"]["sm"]:
            if self.cur.get(sub) is None:
                self._enter(sub, self.g.machines[sub]["start"], quiet)

    def release(self, did, why=""):
        """Leave the state hooked to this script (back to its machine's start state): the exit hook (code 2) fires."""
        hooked = set(self.g.hooked.get(int(did), ()))
        for mid, sid in self.active():
            if (mid, sid) in hooked:
                self.log(f"graph {self.label}: {self.g.state(mid, sid)['name']} ends ({why})")
                busy, self._busy = self._busy, True
                try:
                    self._transition(mid, self.g.machines[mid]["start"], "release")
                    while self._queue and not busy:
                        self._handle(self._queue.pop(0))
                finally:
                    self._busy = busy
                return True
        return False

    def _timeout(self, mid, visit):
        if self.visit.get(mid) != visit or mid not in self.cur:
            return
        idle = self.now() - self.activity.get(mid, -1e9)
        if idle < STATE_TIMEOUT - 1e-6:
            self.after(STATE_TIMEOUT - idle, lambda: self._timeout(mid, visit))
            return
        st = self.g.state(mid, self.cur[mid])
        self.log(f"graph {self.label}: {st['name'] if st else '?'} held {STATE_TIMEOUT:.0f} s, back to locomotion")
        start = self.g.machines[mid]["start"]
        if start != self.cur[mid]:
            self._transition(mid, start, "timeout")

    def _clips(self, mid, st, visit):
        aps = None
        for clip in st["body"]["clips"]:
            speed = float(clip.get("speed") or 1.0) or 1.0
            if "AttackSpeed" in (clip.get("bound") or ""):
                if aps is None:
                    try:
                        aps = float(self.speed() or 0.0)
                    except (TypeError, ValueError):
                        aps = 0.0
                if aps > 0.05:
                    speed = aps
            start = float(clip.get("start") or 0.0)
            known = clip.get("dur")
            absolute = [float(t["t"]) for t in clip["trig"] if not t.get("rel")]
            # an unknown clip length: CLIP_SECONDS of play after the clip's start time, or past its last absolute trigger
            length = float(known) if known else max(start + CLIP_SECONDS * speed, max(absolute, default=0.0) + 0.05)
            for trig in clip["trig"]:
                local = length + float(trig["t"]) if trig.get("rel") else float(trig["t"])
                if local < start - 1e-6:
                    continue
                delay = max(0.0, (local - start) / speed)
                estimated = bool(trig.get("rel")) and not known
                if trig.get("n"):
                    self.pending.setdefault(mid, {})[trig["n"]] = (self.now() + delay, estimated)
                if delay <= 0.0:
                    self._fire_trigger(mid, visit, trig, st["name"])
                else:
                    self.after(delay, lambda tr=trig: self._fire_trigger(mid, visit, tr, st["name"]))

    def _fire_trigger(self, mid, visit, trig, state_name):
        if self.visit.get(mid) != visit:
            return                        # the state was left: its clip stopped
        self.pending.get(mid, {}).pop(trig.get("n"), None)
        self._touch()
        self._notify([trig], state_name)

    def _notify(self, entries, state_name):
        for e in entries:
            code = e.get("code")
            if code and self._sent is not None:
                key = (code, int(e.get("did") or 0))
                if key in self._sent:
                    code = None
                else:
                    self._sent.add(key)
            if code:
                self.trace.append((self.now(), code, int(e.get("did") or 0), state_name))
                if code != 6:                         # SkillHold is never registered (0x9798E0, C)
                    try:
                        self.deliver(code, int(e.get("did") or 0), e.get("off"), state_name)
                    except Exception as ex:          # noqa: BLE001
                        self.log(f"graph {self.label}: hook {code} delivery failed: {ex!r}")
            if e.get("n") and e["n"] in self.g.taken:
                self.raise_name(e["n"])
