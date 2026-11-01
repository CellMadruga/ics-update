"""The game side of the script VM (icserver/scriptvm_runtime.py) inside Tutorial 1.

TutorialWorld turns the script actions into what the tutorial already sends: scriptlet orders (event 0x8D),
the champion bundle when Batman turns, the skill cooldown (0x20F8), damage through the tutorial's own rules
(skill_hit for drones that only take a skill). Missiles are simulated on the server: they fly straight at
their target at the script's speed and raise the collision event on their own scripts.

Entry point: batarang(ctx, target, now) -> messages, used by Tutorial.batarang when [scriptvm] batarang = true.
"""
import csv
import math
import os
import re
import time

from . import messages as M
from . import scriptvm as V
from . import scriptvm_runtime as R
from .wire import KIND_IID

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SKILLS_TSV = os.path.join(ROOT, "catalog", "data", "skills.tsv")
Q_SCRIPT = 0x3400003B
Q_SLOT = 1


class Champion:
    """The player's champion as a script entity."""
    eid = M.CHAMPION_AGENT_ID
    name = "Batman"

    def __init__(self, match):
        self.match = match

    @property
    def pos(self):
        return self.match.mover.pos

    def __repr__(self):
        return "Batman"


def skill_stats(script_did):
    """{stat: (base, per rank)} of the skill whose script is script_did (catalog/data/skills.tsv)."""
    with open(SKILLS_TSV, encoding="utf-8") as f:
        for row in csv.DictReader(f, delimiter="\t"):
            if row.get("script", "").lower() == f"0x{script_did:08x}":
                out = {}
                for m in re.finditer(r"(\d+)=(-?[\d.]+)(?:\(([+-]?[\d.]+)/rank\))?", row.get("stats", "")):
                    out[int(m.group(1))] = (float(m.group(2)), float(m.group(3) or 0.0))
                return out
    return {}


def _key_list(value):
    return [int(str(v), 0) for v in (value or [])]


class TutorialWorld:
    def __init__(self, ctx, script_did):
        self.ctx = ctx
        self.m = ctx.match
        self.cfg = self.m.cfg["scriptvm"]
        self.champion = Champion(self.m)
        self.stats = skill_stats(script_did)
        self.out = []
        self.time = time.time()

    # --- plumbing
    def log(self, text):
        if self.cfg.get("trace", True):
            self.ctx.log(f"scriptvm {text}")

    def drain(self):
        out, self.out = self.out, []
        return out

    def after(self, seconds, fn):
        def run():
            self.time = time.time()
            fn()
            return self.drain()
        self.ctx.schedule(max(0.0, seconds), run)

    # --- data
    def skill_stat(self, owner, stat, rank):
        base, per = self.stats.get(stat, (0.0, 0.0))
        return base + per * max(0, int(rank) - 1)

    def skill_rank(self, owner):
        return max(1, (getattr(self.m, "skill_ranks", 0) >> (4 * Q_SLOT)) & 0xF)

    def cast_time(self, owner):
        return float(self.cfg.get("cast_point", 0.25))

    # --- entities
    def _ent(self, e):
        if e == M.CHAMPION_AGENT_ID or e is self.champion:
            return self.champion
        return e

    def position(self, ent):
        if isinstance(ent, tuple):
            return ent
        ent = self._ent(ent)
        return tuple(ent.pos) if ent is not None and hasattr(ent, "pos") else (0.0, 0.0, 0.0)

    def alive(self, ent):
        ent = self._ent(ent)
        return ent is self.champion or bool(getattr(ent, "alive", False))

    def hostile(self, a, b):
        a, b = self._ent(a), self._ent(b)
        if a is self.champion:
            return b is not self.champion and bool(getattr(b, "attackable", False))
        return b is self.champion

    def kind_matches(self, ent, flags):
        ent = self._ent(ent)
        if flags & 0x100:                   # units (0x10108): drones, champions
            return ent is self.champion or getattr(ent, "health", None) is not None
        return False                        # 0x1000 = destructible props: not handled by this path

    def find_targets(self, center, radius, flags):
        out = []
        for e in self.m.entities.values():
            if e.alive and e.attackable and math.dist(e.pos[:2], center[:2]) <= radius:
                out.append(e)
        return sorted(out, key=lambda e: math.dist(e.pos[:2], center[:2]))

    def has_status(self, ent, status):
        return False

    # --- actions
    def face(self, owner, target):
        p = self.position(target)
        bx, by = self.m.mover.pos[0], self.m.mover.pos[1]
        if abs(p[0] - bx) + abs(p[1] - by) > 1e-3:
            self.m.mover.heading = math.atan2(p[1] - by, p[0] - bx)
        from . import batman
        batman.root(self.ctx, time.time(), reason="Sonic Batarang (scriptvm)")
        self.m.sequence += 1
        self.out.append(("Batman faces the target (scriptvm)", self.m.champion_bundle(time.time())))

    def run_scriptlet(self, ent, key, target=None):
        ent = self._ent(ent)
        target = self._ent(target)
        variables = [(M.PROP_SCRIPT_TARGET, KIND_IID, target.eid)] if getattr(target, "eid", None) else None
        self.ctx.run_scripts(ent.eid, (key,), f"scriptvm scriptlet {key:#x}", variables)

    def start_cooldown(self, owner, seconds):
        from . import abilities
        now = time.time()
        self.ctx.batarang_ready = now + seconds
        self.out.append((f"Q cooldown {seconds:g} s (scriptvm, 0x20f8)", abilities.skill_cooldown(Q_SLOT, now + seconds)))
        self.ctx.schedule(seconds + 0.05, lambda: [("Q ready (0x20f8, 0 s)", abilities.skill_cooldown(Q_SLOT, time.time()))])

    def spend(self, owner, amount):
        self.log(f"spend {amount:g} Will (not tracked)")

    def damage(self, source, target, amount):
        e = self._ent(target)
        if e is self.champion or not getattr(e, "alive", False):
            return
        amount = int(round(amount))
        self.log(f"{e.name} takes {amount}")
        keys = _key_list(self.cfg.get("hit_keys"))
        if keys:
            self.ctx.run_scripts(e.eid, keys, f"scriptvm hit on {e.name}",
                                 [(M.PROP_SCRIPT_TARGET, KIND_IID, M.CHAMPION_AGENT_ID)])
        if getattr(e, "only_slot", None) or getattr(e, "group", None):
            self.out.extend(self.ctx.skill_hit(e, amount, Q_SLOT) or [])
        else:
            self.ctx.damage(e, amount)

    def launch_missile(self, owner, missile_class, target, speed, max_range, scripts):
        if not scripts:
            self.log(f"missile {missile_class:#x}: no decoded script")
            return
        keys = _key_list((self.cfg.get("missile_vfx") or {}).get(f"0x{missile_class:08X}")
                         or (self.cfg.get("missile_vfx") or {}).get(f"{missile_class:#x}"))
        for k in keys:
            self.run_scriptlet(self.champion, k, target)
        missile = TutorialMissile(self, owner, missile_class, target, speed, max_range, scripts)
        missile.start()

    def missile_moved(self, missile, target):
        self.log(f"missile -> {getattr(self._ent(target), 'name', target)}")


class TutorialMissile(R.Missile):
    def end(self, trip):
        was = self.alive
        super().end(trip)
        if was and not self.alive:
            w = self.world
            cfg = w.cfg.get("missile_stop_vfx") or {}
            for k in _key_list(cfg.get(f"0x{self.cls:08X}") or cfg.get(f"{self.cls:#x}")):
                w.run_scriptlet(w.champion, k)


def available():
    try:
        V.load(Q_SCRIPT)
        V.load(0x3400003F)
        return True
    except OSError:
        return False


def batarang(ctx, target, now):
    """Q from the original scripts. Returns the messages to send now."""
    world = TutorialWorld(ctx, Q_SCRIPT)
    script = V.load(Q_SCRIPT)
    inst = R.use_skill(script, world.champion, world, target=target)
    if inst.unknown:
        world.log("not implemented: " + ", ".join(sorted(map(str, inst.unknown))))
    return world.drain()
