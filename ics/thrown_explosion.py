"""A launched object that explodes at the end of its flight or on an enemy champion (P; 2026-11-07).

Nightwing's Let's Ride 0x34000794: its second press (S5 -> S4 -> S3) launches the bike, missile 0x40000E6F, and goes
to S2 (clean-up); the bike's only script, 0x340001A6, does destruction impulses. No script found deals the thrown
bike's damage, yet the skill's own description (game text, seen in the client) says: "fire off the bike in targeted
direction dealing 167 Attack Damage to all in the area. Reaching the maximum distance or colliding with an enemy
Champion will cause the bike to explode". 167 = stat 5 (165 at rank 1) + 100 % of the bonus attack damage, the
formula of the ride's own explosion (S5 sub-graph S1: FindTargets(DetectionRange) + ApplyDamage(BaseDamage)).

So, probably (P): the launched bike explodes when it reaches its range or hits an enemy champion, dealing the
launcher script's damage variable to every enemy within its radius variable around the bike. Clues for the original
mechanism, still open: the missile record 0x40000E6F (a payload not read yet), or a script not found. [ics]
thrown_explosions: {missile class: {"script": launcher DID, "damage": variable, "radius": variable}}.
"""


def _cfg(world):
    w = getattr(world, "w", world)
    return (getattr(w, "ic", {}) or {}).get("thrown_explosions") or {}


def arm(inst, missile, cls):
    """Called when a script launches a missile: arm it if its class and launcher are listed."""
    spec = _cfg(inst.world).get(f"0x{cls:08X}") if isinstance(cls, int) else None
    if not spec or int(str(spec.get("script", 0)), 0) != getattr(inst.script, "did", None):
        return
    amount = float(inst.var_by_name(spec.get("damage", "BaseDamage"), 0.0) or 0.0)
    radius = float(inst.var_by_name(spec.get("radius", "DetectionRange"), 0.0) or 0.0)
    if amount <= 0 or radius <= 0:
        return
    w = inst.world
    shooter = inst.source()
    state = {"done": False}

    def explode():
        if state["done"]:
            return
        state["done"] = True
        from . import script_nodes as N
        here = w.position(missile)
        hit = [e for e in w.find_targets(here, radius, 0) if w.alive(e) and w.hostile(shooter, e)]
        if hasattr(w, "log"):
            w.log(f"thrown {cls:#x} explodes: {amount:g} within {radius:g} m on {len(hit)} target(s) (P, [ics] "
                  f"thrown_explosions)")
        for e in hit:
            N.deal_damage(w, shooter, e, amount, 1, slot=inst.slot)

    end, collide = missile.end, missile.collide

    def on_end(trip):
        if missile.alive and trip == missile.trip:
            explode()
        return end(trip)

    def on_collide(target):
        if (missile.alive and getattr(target, "kind", None) == "champion" and w.alive(target)
                and w.hostile(shooter, target)):
            explode()
            return end(missile.trip)
        return collide(target)
    missile.end, missile.collide = on_end, on_collide
