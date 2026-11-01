"""Combat state shared by the script runtime and the match world: attributes and their modifiers, cooldowns and the
skill-state tables, action locks, shields, vital-over-time effects, hotspots / auras and forced movement.

Everything here follows docs/re-notes/full-combat-skills.md (the spec from the client's decompilation; C = read in the
client, P = probable). The client never computes gameplay: it shows what the server sends, so this module keeps the
authoritative values and calls the world's hooks for the messages:

  world.on_modifier(ent, attr, mod, added)        0x20F0 / 0x20E8 (+ event 0x6 for the CC flags)
  world.on_attribute(ent, attr, old, new)         movement stop, order lock, script event 0x100000A2
  world.on_cooldown(ent, slot, end)               0x20F8
  world.on_condition(ent, slot, error, h, add)    0x20A0
  world.on_usable(ent, slot, enable, flag)        0x207B
  world.vitals_changed(ent)                       0x42
NullWorld (ics/script_runtime.py) logs them; CastWorld (ics/world.py) sends them.
"""
import itertools
import math
import struct

_ids = itertools.count(1)

# ---- attribute ids (full-combat-skills.md 2 A.4, client-status-effects.md 1) -----------------------------------
ATTR_STUNNED = 0x100003F3
BOX_CENTERED = True                 # [ics] hotspot_box_centered (set by ics/server.py)
ATTR_ROOTED = 0x100007FE
ATTR_CRIPPLED = 0x10000B39
ATTR_SILENCED = 0x100005A3
ATTR_CANNOT_ACT = 0x10000B2D
ATTR_TARGETABLE = 0x10000029
ATTR_TARGETABLE_C = 0x10000249
ATTR_MOVE_SPEED = 0x100005E4
ATTR_ATTACK_SPEED = 0x100006FE
ATTR_ATTACK_DAMAGE, ATTR_POWER_DAMAGE = 0x10000B76, 0x10000B75
ATTR_ATTACK_ARMOR, ATTR_POWER_ARMOR = 0x10000B84, 0x10000B7A
ATTR_ATTACK_PEN, ATTR_POWER_PEN = 0x10000B83, 0x10000B7E
ATTR_ATTACK_PEN_PCT, ATTR_POWER_PEN_PCT = 0x10000B7D, 0x10000B82
ATTR_ATTACK_LIFESTEAL, ATTR_POWER_LIFESTEAL = 0x10000B7C, 0x10000B7F
ATTR_CRIT_CHANCE, ATTR_CRIT_DAMAGE = 0x10000B46, 0x10000B80
ATTR_HEALTH = 0x10000426
ATTR_STEALTH = 0x10000B4A
PROP_LIFE_STATE = 0x100000FA
PROP_LEVEL = 0x10000167
PROP_TEAM = 0x1000009C

# bool attributes the server also sets as a property with event 0x6 (the client's order gate and HUD read the
# attribute component, which sees a base value set this way; client-status-effects.md 1)
CC_FLAGS = (ATTR_STUNNED, ATTR_CANNOT_ACT, ATTR_SILENCED, ATTR_ROOTED, ATTR_CRIPPLED)
BOOL_DEFAULT_TRUE = {ATTR_TARGETABLE, ATTR_TARGETABLE_C}

# resource-specific ids -> the generic ones (0x96F4F0, A.1); the number is the resource (vital) type
ALIASES = {0x10000200: (1, 0x10000484), 0x10000482: (4, 0x10000484), 0x10000483: (5, 0x10000484),
           0x10000573: (3, 0x10000484), 0x100007A3: (6, 0x10000484),
           0x10000487: (1, 0x10000432), 0x10000485: (4, 0x10000432), 0x10000486: (5, 0x10000432),
           0x10000574: (3, 0x10000432), 0x100007A4: (6, 0x10000432)}

# property kinds (ics/wire.py)
KIND_BOOL, KIND_F32, KIND_INT, KIND_ENUM, KIND_IID, KIND_DID, KIND_U32 = 0x16, 9, 0x10, 8, 7, 0x15, 0x13

# modifier op -> sort rank (comparator 0x96C420)
OP_RANK = {0: 1, 4: 2, 6: 3, 7: 4, 9: 4, 1: 5, 10: 6, 2: 7, 3: 8, 8: 9, 5: 10}

# skill error types (gmErrorTypeList)
ERR_NOT_ALIVE, ERR_NOT_USABLE, ERR_INVALID_TARGET = 0x10000054, 0x10000066, 0x1000003C
ERR_COOLDOWN, ERR_NO_RESOURCES, ERR_NO_CHARGES = 0x10000033, 0x10000055, 0x10000045
ERR_NO_TARGETS, ERR_PATH_BLOCKED, ERR_STUNNED = 0x10000059, 0x10000034, 0x10000051
ERR_ROOTED, ERR_CRIPPLED, ERR_SILENCED = 0x10000050, 0x1000006B, 0x1000003B


class Handle:
    """A handle written into a script variable (modifier, shield, VOT, action, icon, hotspot ...). The wire form
    is Handle{u32, u64}: the number and the IID of the entity it belongs to."""
    __slots__ = ("n", "kind", "owner")

    def __init__(self, kind, owner=None):
        self.n, self.kind, self.owner = next(_ids), kind, owner

    def __bool__(self):
        return True

    def __eq__(self, other):
        return isinstance(other, Handle) and other.n == self.n

    def __hash__(self):
        return self.n

    def __repr__(self):
        return f"<{self.kind} handle {self.n}>"


class Modifier:
    __slots__ = ("handle", "source", "attr", "op", "value", "team", "group")

    def __init__(self, handle, source, attr, op, value, team=-1, group=0):
        self.handle, self.source, self.attr, self.op = handle, source, attr, op
        self.value, self.team, self.group = value, team, group


def _skey(ent):
    return id(ent) if not isinstance(ent, (str, int, tuple)) else ent


def evaluate_modifiers(kind, base, mods):
    """The client's stacking formula 0x96D460 (full-combat-skills.md 2 A.2) with the default rules (stacking factor
    1.0 = plain sum, no soft caps: the rules record is not located in the packs)."""
    if not mods:
        return base
    ordered = sorted(mods, key=lambda m: (OP_RANK.get(m.op, 11), m.group, str(_skey(m.source))))
    if kind == KIND_BOOL:
        x = bool(base)
        for m in ordered:
            v = bool(m.value)
            if m.op in (0, 5, 6):
                x = v
            elif m.op == 3:
                x = x or v
            elif m.op == 8:
                x = x and v
        return x
    if kind not in (KIND_F32, KIND_INT, KIND_U32):
        x = base                                   # double / enum / IID: the last set wins
        for m in ordered:
            if m.op in (0, 5, 6):
                x = m.value
        return x
    x = float(base or 0.0)
    runs, cur = [], None
    for m in ordered:
        op = 9 if m.op == 7 else m.op
        v = float(m.value or 0.0) * (-1.0 if m.op == 7 else 1.0)
        k = (op, _skey(m.source), m.group)
        if cur is None or cur[0] != k:
            cur = [k, []]
            runs.append(cur)
        cur[1].append(v)
    for (op, _src, _grp), vals in runs:
        if op in (0, 5, 6):
            x = vals[-1]
        elif op == 2:
            for v in vals:
                x = x / v if v else x
        elif op == 9:
            x += sum(vals)
        elif op == 1:
            x += abs(sum(vals))
        elif op == 10:
            x *= 1.0 + sum(vals)
        # ops 3, 4, 8 on numbers accumulate but are never applied (C)
    if kind in (KIND_INT, KIND_U32):
        return float(math.floor(x + 0.5))
    return x


def relation(team_a, team_b):
    """0x853380: same team 4 (friendly, also self), either team 0 -> 1 (neutral), else 2 (hostile); -1 = hostile."""
    if team_a is None or team_b is None or team_a == -1 or team_b == -1:
        return 2
    if team_a == team_b:
        return 4
    if team_a == 0 or team_b == 0:
        return 1
    return 2


class State:
    """Per-entity combat state."""

    def __init__(self):
        self.mods = {}                 # attr -> [Modifier]
        self.base = {}                 # attr -> base value set by scripts / the server
        self.cooldowns = {}            # slot -> end time
        self.conditions = []           # [(slot, error, handle)]
        self.overrides = {}            # slot -> flag (usable override 0x207B)
        self.stat_overrides = {}       # slot -> {stat: value}
        self.action_owner = None       # instance holding the action lock (BeginSkill)
        self.locks = {}                # DisableActions handle -> (family, priority)
        self.input_locks = 0           # LockInput counter
        self.shields = {}              # handle -> [vital, amount, max, source]
        self.vots = {}                 # handle -> dict
        self.vitals = {}               # vital id -> [current, max] for vitals other than health / the resource
        self.defeat_guards = {}        # handle -> type
        self.untargetable = 0
        self.ai_off = set()
        self.charges = {}
        self.icons = {}                # handle -> icon info
        self.redirects = {}            # handle -> (fraction, linked entity, kind)
        self.motion = None             # current forced movement
        self.skill_targets = []
        self.flags = {}                # misc per-entity flags set by single-use nodes
        self.movement_modes = {}
        self.creator = None
        self.hidden = 0


class Combat:
    """The combat state of a match (or of a simulation)."""

    def __init__(self, world):
        self.world = world
        self.states = {}
        self.hotspots = {}             # handle -> Hotspot
        self.status_flags = None       # callable(status DID) -> flags (record 0x10000334)

    def of(self, ent):
        if ent is None:
            return State()
        k = _skey(ent)
        st = self.states.get(k)
        if st is None:
            st = self.states[k] = State()
        return st

    # ---- attributes ----------------------------------------------------------------------------------
    def kind(self, attr):
        k = self.world.property_kind(attr) if hasattr(self.world, "property_kind") else None
        if k is None:
            if attr in CC_FLAGS or attr in BOOL_DEFAULT_TRUE or attr in (ATTR_STEALTH, 0x10000459, 0x10000A23,
                                                                         0x10000643, 0x100006F3, 0x100003AB):
                return KIND_BOOL
            return KIND_F32
        return k

    def base_value(self, ent, attr):
        st = self.of(ent)
        if attr in st.base:
            return st.base[attr]
        v = self.world.base_attribute(ent, attr) if hasattr(self.world, "base_attribute") else None
        if v is not None:
            return v
        if self.kind(attr) == KIND_BOOL:
            return attr in BOOL_DEFAULT_TRUE
        return 0.0

    def attribute(self, ent, attr, mode=0):
        """GetAttribute 0x10000002: mode 0 current (base + modifiers), 1 bonus (current - base), 2 base."""
        if attr in ALIASES:
            attr = ALIASES[attr][1]           # the resource type test passes for the generic champion resource
        kind = self.kind(attr)
        base = self.base_value(ent, attr)
        # 2026-10-26 (tester: Bat Scream's damage scaling is off; measured: its 0.9 x bonus attack damage was always 0):
        # the item bonuses are folded into the stats the base reads, so they belong to the bonus, not to the base
        items = self.world.item_part(ent, attr) if hasattr(self.world, "item_part") and kind != KIND_BOOL else 0.0
        if items:
            base = float(base or 0.0) - items
        if mode == 2:
            return base
        mods = [m for m in self.of(ent).mods.get(attr, ()) if m.team == -1]
        cur = evaluate_modifiers(kind, base + items if items else base, mods)
        if mode == 1:
            if kind == KIND_BOOL:
                return bool(cur) and not bool(base)
            return float(cur) - float(base or 0.0)
        return cur

    def flag(self, ent, attr):
        return bool(self.attribute(ent, attr))

    def add_modifier(self, ent, attr, op, value, source=None, team=-1):
        if attr in ALIASES:
            attr = ALIASES[attr][1]
        kind = self.kind(attr)
        if kind == KIND_BOOL:
            value = bool(value) if not isinstance(value, bool) else value
        elif kind in (KIND_F32, KIND_INT, KIND_U32):
            value = _num(value)
        old = self.attribute(ent, attr)
        h = Handle("modifier", ent)
        mod = Modifier(h, source, attr, int(op), value, team)
        self.of(ent).mods.setdefault(attr, []).append(mod)
        self._changed(ent, attr, old, mod, True)
        return h

    def remove_modifier(self, ent, handle, attr=None):
        st = self.of(ent)
        for a, lst in list(st.mods.items()):
            if attr is not None and a != attr and ALIASES.get(attr, (0, attr))[1] != a:
                continue
            for m in list(lst):
                if m.handle == handle:
                    old = self.attribute(ent, a)
                    lst.remove(m)
                    if not lst:
                        del st.mods[a]
                    self._changed(ent, a, old, m, False)
                    return True
        return False

    def set_base(self, ent, attr, value):
        old = self.attribute(ent, attr)
        self.of(ent).base[attr] = value
        new = self.attribute(ent, attr)
        if new != old and hasattr(self.world, "on_attribute"):
            self.world.on_attribute(ent, attr, old, new)

    def _changed(self, ent, attr, old, mod, added):
        new = self.attribute(ent, attr)
        if hasattr(self.world, "on_modifier"):
            self.world.on_modifier(ent, attr, mod, added, new)
        if new != old and hasattr(self.world, "on_attribute"):
            self.world.on_attribute(ent, attr, old, new)

    # ---- crowd control ---------------------------------------------------------------------------------
    def stunned(self, ent):
        st = self.of(ent)
        return bool(st.locks) or self.flag(ent, ATTR_STUNNED) or self.flag(ent, ATTR_CANNOT_ACT)

    def can_move(self, ent):
        st = self.of(ent)
        return not (self.stunned(ent) or self.flag(ent, ATTR_ROOTED) or st.input_locks > 0 or st.motion is not None)

    def can_act(self, ent):
        return not self.stunned(ent) and self.of(ent).motion is None

    # ---- skills -----------------------------------------------------------------------------------------
    def cooldown_left(self, ent, slot, now):
        return max(0.0, self.of(ent).cooldowns.get(slot, 0.0) - now)

    def set_cooldown(self, ent, slot, end):
        self.of(ent).cooldowns[slot] = end
        if hasattr(self.world, "on_cooldown"):
            self.world.on_cooldown(ent, slot, end)

    def can_activate(self, ent, slot, cost=0.0, resource=None, movement_skill=False, now=0.0, ignore_cooldown=False):
        """CanActivate 0x8709E0 with the server's state (1.3): 0 = ok, else the ErrorType."""
        st = self.of(ent)
        alive = self.world.alive(ent) if hasattr(self.world, "alive") else True
        if not alive or self.flag(ent, ATTR_CANNOT_ACT):
            return ERR_NOT_ALIVE if not alive else ERR_STUNNED
        flag = st.overrides.get(slot)
        for s, err, _h in st.conditions:
            if s in (slot, -2) and err in (ERR_NOT_USABLE, ERR_INVALID_TARGET):
                return err
        if slot != 6 and not ignore_cooldown and self.cooldown_left(ent, slot, now) > 0.0002:
            return ERR_COOLDOWN
        if flag is None and cost and resource is not None and resource < abs(cost):
            return ERR_NO_RESOURCES
        for s, err, _h in st.conditions:
            if s in (slot, -2) and err in (ERR_NO_CHARGES, ERR_NO_TARGETS, ERR_PATH_BLOCKED):
                return err
        if not flag and (self.flag(ent, ATTR_STUNNED) or st.locks):
            return ERR_STUNNED
        if movement_skill and self.flag(ent, ATTR_ROOTED):
            return ERR_ROOTED
        if movement_skill and self.flag(ent, ATTR_CRIPPLED):
            return ERR_CRIPPLED
        if slot != 0 and not flag and self.flag(ent, ATTR_SILENCED):
            return ERR_SILENCED
        for s, err, _h in st.conditions:
            if s in (slot, -2) and err not in (ERR_NOT_USABLE, ERR_INVALID_TARGET, ERR_NO_CHARGES, ERR_NO_TARGETS,
                                               ERR_PATH_BLOCKED):
                return err
        return 0

    # ---- vitals ---------------------------------------------------------------------------------------------
    def shield_total(self, ent, vital=2):
        return sum(s[1] for s in self.of(ent).shields.values() if s[0] == vital)

    def absorb(self, ent, amount, vital=2):
        """Shields (temp vitals) take damage first; returns what is left for the vital."""
        st = self.of(ent)
        for h, s in list(st.shields.items()):
            if amount <= 0:
                break
            if s[0] != vital:
                continue
            take = min(s[1], amount)
            s[1] -= take
            amount -= take
        return amount

    def guarded(self, ent):
        """Defeat overrides (0x10000162): 100 = invincible, 0 = cannot be defeated while held."""
        types = set(self.of(ent).defeat_guards.values())
        return types

    # ---- hotspots ---------------------------------------------------------------------------------------
    def add_hotspot(self, hs):
        self.hotspots[hs.handle] = hs
        return hs.handle


def _num(v):
    if isinstance(v, bool):
        return float(v)
    if isinstance(v, int) and v > 0xFFFFF:
        return struct.unpack("<f", struct.pack("<I", v & 0xFFFFFFFF))[0]
    if isinstance(v, (int, float)):
        return float(v)
    return 0.0


class Hotspot:
    """A server volume applying status effects to the entities inside (full-combat-skills.md 4.2)."""

    def __init__(self, owner, shape, radius, length, height, width, mask, kinds, statuses, durations, rank,
                 position=None, attached=None, lifetime=0.0):
        self.handle = Handle("hotspot", owner)
        self.owner, self.shape = owner, shape
        self.radius, self.length, self.height, self.width = radius, length, height, width
        self.mask, self.kinds = mask, kinds
        self.a, self.b, self.c = statuses
        self.dur_a, self.dur_b, self.dur_c = durations
        self.rank = rank
        self.position, self.attached = position, attached
        self.lifetime = lifetime
        self.inside = {}                # entity key -> (entity, status-A instance)
        self.alive = True
        self.visual = None              # the visible object (an IID in the world)

    def center(self, world):
        if self.attached is not None:
            return world.position(self.attached)
        return self.position

    def heading(self, world):
        src = self.attached if self.attached is not None else self.position
        return world.heading(src) if hasattr(world, "heading") else 0.0

    def contains(self, world, ent):
        c = self.center(world)
        if c is None:
            return False
        p = world.position(ent)
        dx, dy = p[0] - c[0], p[1] - c[1]
        r = world.radius(ent) if hasattr(world, "radius") else 0.5
        if self.shape in (1, 7, 6) or not self.length:
            return math.hypot(dx, dy) <= max(self.radius, 0.0) + r
        # box: x half = width / 2 across, 0..length along the facing
        h = self.heading(world)
        fwd = dx * math.cos(h) + dy * math.sin(h)
        side = -dx * math.sin(h) + dy * math.cos(h)
        if BOX_CENTERED:
            # 2026-10-28 (tester: "the champions' R do no damage to the enemy champion"; champion_check: Mecha Wonder Woman's
            # Tempest 0x340002C8 places its box at SkillRange * 0.5 ahead, as do her W 0x340002CA and the beams of
            # 0x340005AB (start + length * 0.5): the box is centred on its position, -length / 2 .. length / 2;
            # [ics] hotspot_box_centered)
            return abs(fwd) <= self.length / 2 + r and abs(side) <= (self.width or self.radius) / 2 + r
        return -r <= fwd <= self.length + r and abs(side) <= (self.width or self.radius) / 2 + r


def status_flags(data, did):
    """Property 0x10000334 of a status record (status flag bits: 0x4000 debuff, 0x100 hard CC ...), 0 if absent."""
    cache = data.__dict__.setdefault("_status_flags", {})
    if did not in cache:
        out = 0
        rec = data._record(did)
        if rec:
            buf, start, end = rec
            k = buf.find(struct.pack("<II", 0x10000334, 0x10000334), start, end)
            if k >= 0:
                out = struct.unpack_from("<I", buf, k + 8)[0]
        if not out:
            v = record_value(data, did, 0x10000334)
            out = v if isinstance(v, int) else 0
        cache[did] = out
    return cache[did]


def record_value(data, did, prop):
    """One property of a record read by kind (ics.gamedata Data.record), or None."""
    cache = data.__dict__.setdefault("_record_values", {})
    key = (did, prop)
    if key not in cache:
        out = None
        try:
            for k, _kind, v in data.record(did) or ():
                if k == prop:
                    out = v
                    break
        except Exception:                          # noqa: BLE001 - a record the reader does not understand
            out = None
        cache[key] = out
    return cache[key]
