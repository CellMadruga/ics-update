"""Contacts of a champion that holds collision (2026-11-07, tester report: Nightwing's bike never exploded on enemies).

EnableCollision 0x10000070 adds a run's collision hold on the script's own entity (C: client 0x97D720 -> 0x976990, the
hold is what builds the body); the script then waits for OnEntityEvent 0x10000002 {TargetIID 0x632FE62,
CollisionPosition 0x33016EE} (Nightwing's Let's Ride 0x34000794 graph S1 / S5 sub-graph T3). ics raised that event
for missiles, dashes and thrown objects only, never for a champion walking with a hold. Here a champion with a hold
gets 0x10000002 when it starts touching another unit, champion or structure (bodies' radii) while it walks on its own
(a forced movement raises its own); the script filters by
kind and relation itself (P: how the original server produced these contacts is not known; [ics]
held_collision_contacts).
"""
EVENT_COLLISION = 0x10000002
TARGET, POSITION = 0x632FE62, 0x33016EE
KINDS = ("unit", "champion", "structure")


def _radius(ent):
    mu = getattr(ent, "match_unit", None)
    return max(0.5, float(getattr(mu, "radius", 0.5) or 0.5)) if mu is not None else 0.5


def tick(world):
    """Raise 0x10000002 on each champion that holds collision, once per new contact."""
    if not world.ic.get("held_collision_contacts", True):
        return
    c = world.__dict__.get("_combat")
    if c is None:
        return
    from . import script_runtime as R
    everyone = [e for e in list(world.entities.values()) + ([world.champion] if world.champion else []) if e is not None]
    for ent in everyone:
        if ent.kind != "champion" or not ent.alive or R._key(ent) not in c.states:
            continue
        st = c.of(ent)
        holds = st.flags.get("collision_holds")
        if st.motion is not None:
            continue                       # a dash / knockback raises its own contacts (script_nodes._start_motion)
        touching = ent.__dict__.setdefault("collision_contacts", set())
        if not holds:
            touching.clear()
            continue
        now = set()
        for e in everyone:
            if (e is ent or e.kind not in KINDS or not getattr(e, "alive", False) or e.health is None
                    or ent.distance_to(e) > _radius(ent) + _radius(e)):
                continue
            now.add(e.eid)
            if e.eid not in touching:
                world.raise_event(ent, EVENT_COLLISION, {TARGET: e, POSITION: tuple(ent.pos)})
        touching.intersection_update(now)
        touching.update(now)
