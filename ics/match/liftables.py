"""Liftable map props: the meteorites and vehicles Super Strength lifts, carries and throws (crime-alley-props.md A).

No client data places them (C): the server spawns them at match start ([ics] liftable_props_by_map). Super Strength
0x34000164 raises 0x10000037 on its target; the original server's native code then started a sub-skill (0x480003C9
lob for a vehicle, 0x480004A2 rubble for a rock) that nothing in the data starts. ics plays that sub-skill's visible
sequence itself (the scriptlets and timings of 0x34000161 / 0x34000177, as icserver/finale.py did in Tutorial 1):
lift, carry over the head, throw on the next press (World.cast "throw"), then the blast (vehicle) or the hit (rock)
with the sub-skill's damage and status, and a respawn after [ics] liftable_respawn_seconds.
"""
import math
import time

from .. import graph as GR
from .. import messages as M
from .. import script_runtime as R
from ..script_nodes import deal_damage
from ..world import CastWorld
from ..wire import KIND_BOOL, KIND_DID, KIND_ENUM, KIND_INT, KIND_U32
from .units import heading_from_yaw

EVENT_PICKUP = 0x10000037          # raised by Super Strength 0x34000164 on its target
EVENT_END = 0x10000009             # ends 0x34000164 (the sub-skill raised it at its end)
EVENT_INPUT_BACK = 0x100000BB      # 0x34000164's input back (S4 -> S3, StartCooldown); the sub-skill raised it
PRESS_EVENT = 0x10000023           # the client's 0x20EA event of a skill button press (Session.ev_skill_events)
RANGE_REFUSE = 0x100006D5          # skill bool: the client refuses an order point beyond range + 0.5 m (0xa25d80)
RAISE_EVENT_KEY, RAISE_EVENT_VAR = 0x100001E3, 0x780     # _HFSM_BehaviorRaiseEventAction + its event variable

# per kind: the sub-skill's scriptlets and stats (crime-alley-props.md A.3, C scripts and stats)
# 2026-10-26 (grab-arm-carry.md 2, C graph clips): grab = the pickup clip's grab frame (code 3), hold = Hold state,
# release = the throw clip's launch (code 5), end = its end (code 2); "on_object" = the init key also on the object;
# "locomotion" = _Combat_GoToLocomotion after the throw (only the vehicle's script sends it); Rubble_Active 0x10000775 is
# in none of the champions' tables (dropped)
# 2026-10-28 15:00 (tester: the vehicle lift starts, then cuts to already holding it; vehicle-lift-and-position.md 2):
# "toss" = the vehicle is lobbed from where it stands onto the champion and caught, 0x34000161 S6-S9's order
# ([ics] liftable_vehicle_toss); grab / hold are the old order's (put over the head at the grab frame)
KINDS = {
    "vehicle": {"flags": 0x1080, "init": 0x100007A2, "pickup": 0x100007A1, "graph": 0x10000246, "loop": 0,
                "throw": 0x100007A0, "thrown": (0x1000013E, 0x1000087A), "lifted": (), "on_object": True, "toss": True,
                "grab": 0.11, "hold": 0.57, "release": 0.20, "end": 0.22, "locomotion": True,
                "range": 9.0, "radius": 2.5, "damage": 75.0, "per_rank": 20.0,
                "status": 0x48000294, "seconds": 2.0, "lob": True, "speed": 16.0, "remove_after": 10.5},
    "rock": {"flags": 0x22, "init": 0x100004CD, "pickup": 0, "graph": 0, "loop": 0,
             "throw": 0x100004CC, "thrown": (0x1000087A, 0x1000008D), "lifted": (0x1000023A,), "on_object": False,
             "grab": 0.22, "hold": 0.30, "release": 0.26, "end": 0.28, "locomotion": False,
             "range": 8.5, "radius": 1.25, "damage": 50.0, "per_rank": 12.5,
             "status": 0x48000295, "seconds": 1.5, "lob": False, "speed": 15.5, "remove_after": 0.3},
}
HIT_OFF, HIT_ON = 0x100003AF, 0x100003AE        # CbtState_DisableHit / EnableHit (graph events)
PROP_TEAM, PROP_COLOUR_OVERRIDE = 0x1000009C, 0x10000CF0   # PVP_Team; the team colour override 0xA7B0D0 reads first
LOCOMOTION_KEY = 0x100002FD        # _Combat_GoToLocomotion
EXPLODE_KEY, COLLISION_KEY, FADE_OUT_KEY = 0x10000079, 0x10000016, 0x1000006A
# SM_SuperStrength_Car's timings when a value is not in the champion's graph (AGL's / Gaslight Batman's, C graph data,
# vehicle-lift-and-position.md 2.2): car_pickup = Car_Pickup's start frame (s into Pickup_Start), hook = Car_Pickup's
# code-3 grab hook and hold = its state_to_state to Hold (s after CarPickup)
CAR_TIMES = {"car_pickup": 0.45, "hook": 0.0125, "hold": 0.375}
_CAR_TIMES_BY_GRAPH = {}


def _did(v):
    return int(str(v), 0) if v not in (None, "") else 0


class Liftables:
    def __init__(self, match):
        self.m = match
        self.w = match.world
        self.ic = match.ic
        self.props = []
        self.bases = {}             # spec index -> the crater / base entity under it (Liftables._base)
        self.carriers = set()       # champions with a carry in progress (Liftables._watch)

    # ---- spawn -------------------------------------------------------------------------------------------------------
    def start(self):
        if not self.ic.get("liftable_props", True):
            return
        self.w.listeners.append(self._on_event)
        specs = list((self.ic.get("liftable_props_by_map") or {}).get(self.m.map.get("key")) or ())
        # 2026-10-29 (tester report from the original-game video; power-core-turret.md 6): the parked vehicles seen
        # by the bases and along the south curb ([ics] liftable_props_added_by_map; entries with "enabled": false skipped)
        specs += [s for s in (self.ic.get("liftable_props_added_by_map") or {}).get(self.m.map.get("key")) or ()
                  if s.get("enabled", True)]
        if self.ic.get("liftable_gallery", False):
            # test aid: every vehicle class in a row behind the blue base, so the tester can name the SUV and the truck
            for i, (cls, ws) in enumerate(self.ic.get("liftable_gallery_classes") or ()):
                specs.append({"kind": "vehicle", "class": cls, "world_state": ws, "pos": [8.0, 66.0 + 3.5 * i, 0.0],
                              "yaw": 90.0, "respawn": False})
        for i, spec in enumerate(specs):
            self._base(spec, i)
            self._spawn(dict(spec, index=i), respawn=False)

    def _base(self, spec, i):
        """2026-10-25 22:07 (tester: the meteorites have no crater under them): the original vs-AI map shows each in a
        lava crater that nothing places (crime-alley-still-missing.md 8); the Tutorial's lava crater world state stands
        in ([ics] liftable_bases: kind -> {world_state, scriptlets}), and stays when the rock is thrown."""
        base = (self.ic.get("liftable_bases") or {}).get(spec.get("kind"))
        if not base:
            return
        w = self.w
        x, y, z = (list(spec["pos"]) + [0.0, 0.0])[:3]
        z = z or (w.nav.height(x, y) if w.nav is not None else None) or self.m.map["z"]
        z += float(base.get("z_offset", 0.0) or 0.0)     # the base stays on the ground under a raised meteorite
        ox, oy = (list(base.get("offset") or ()) + [0.0, 0.0])[:2]
        x, y = x + float(ox), y + float(oy)
        try:
            ent = w.spawn(_did(base["world_state"]), [x, y, z], 0.0, name=f"{spec.get('kind')} {i} crater", start=False)
        except Exception as e:                      # noqa: BLE001
            self.m.log(f"liftable base {i} not created ({e!r})")
            return
        ent.kind, ent.health, ent.max_health = "prop", None, None
        ent.pos[2] = float(z)
        self.bases[i] = ent
        w.update(ent, f"spawn {ent.name} ({_did(base['world_state']):#x})")
        for k, name in enumerate(base.get("scriptlets") or ()):
            self.m.later(0.3 + 0.3 * k, lambda e=ent, n=name: w.scriptlet(e, n, f"{e.name}: {n} (0x8d)")
                         if e.eid in w.entities else None)

    def _spawn(self, spec, respawn):
        w = self.w
        kind = spec.get("kind", "rock")
        info = KINDS.get(kind)
        if info is None:
            return None
        x, y, z = (list(spec["pos"]) + [0.0, 0.0])[:3]
        if not z and w.nav is not None:
            z = w.nav.height(x, y) or self.m.map["z"]
        try:
            cls = _did(spec["class"])
            mode = (self.ic.get("liftable_class_mode") or {}).get(kind)
            if mode == "world_state" and spec.get("world_state"):
                # 2026-10-26 12:51 (tester's /tour: no vehicle at its stop, the gallery's neither): as a bare world state
                cls = _did(spec["world_state"])
            elif mode == "carrier" and spec.get("world_state"):
                # 2026-10-26 13:40 (tester's vitrina: none of the seven vehicle world states drew, entity or bare): the
                # exe patch's carrier class 0x4A + the world state's low bits (icserver/patcher.py "props": a bare world
                # state builds its model but is never placed; the carrier is placed with the world state's own model),
                # as Tutorial 1's street vehicle showed
                cls = 0x4A000000 | (_did(spec["world_state"]) & 0xFFFFFF)
            ent = w.spawn(cls, [x, y, z or self.m.map["z"]], heading_from_yaw(float(spec.get("yaw", 0.0))),
                          name=f"{kind} {spec.get('index', 0)}", world_state=_did(spec.get("world_state")), start=False)
        except Exception as e:                      # noqa: BLE001
            self.m.log(f"liftable {kind} {spec.get('index', 0)} not created ({e!r})")
            return None
        ent.kind, ent.health, ent.max_health = "prop", None, None
        ent.kit, ent.liftable, ent.lift_spec, ent.team = {}, kind, spec, 0
        if ent.class_id >> 24 in range(0x4A, 0x50):
            w.dress_spawned(ent)        # the carrier gets its world state's tables (0x7D2) and scriptlet keys
        ent.pos[2] = float(z or self.m.map["z"])
        ent.extra_props = [p for p in ent.extra_props if p[0] != 0x100000FA] + [(0x100000FA, KIND_ENUM, 4)]
        ctype = (self.ic.get("liftable_creation_type") or {}).get(kind)
        if ctype:
            # 2026-10-25 23:40 (tester: none of the seven gallery vehicles was seen; the meteorites, creation type 7,
            # are): the vehicles' world states have creation type 8; they go as 7 ([ics] liftable_creation_type)
            ent.extra_props = [p for p in ent.extra_props if p[0] != 0x50F] + [(0x50F, KIND_ENUM, int(ctype))]
        w.update(ent, f"spawn liftable {ent.name} ({ent.class_id:#x})")
        cell = (self.ic.get("liftable_cell") or {}).get(kind)
        if cell is not None:
            ent.cell = int(cell)
        rec = w.data.record_u32(ent.world_state or _did(spec.get("world_state")), 0x800)
        if rec and self.ic.get("destruction_reset_event", True):
            # 2026-10-26 (destructible-vehicles.md: a world state with a destruction record 0x800 is drawn only through
            # its pieces, which the client builds itself only for creation types 6 / 9; the vehicles are 8): 0x8B
            # rebuilds the intact pieces, sent while the vehicle is still whole ([ics] destruction_reset_delays)
            for at in self.ic.get("destruction_reset_delays") or [0.3, 1.0, 3.0]:
                self.m.later(float(at), lambda e=ent: w.send(f"{e.name}: rebuild intact (0x8b)", M.destruction_reset(e.eid))
                             if e.eid in w.entities and getattr(e, "carried_by", None) is None
                             and not getattr(e, "flying", False) and not getattr(e, "broken", False) else None)
        for again in (self.ic.get("liftable_resend") or {}).get(kind) or ():
            # the client sometimes builds a vehicle only on an update (Tutorial 1's DestVehicle, catalog): sent again
            # 2026-10-28 15:00 (tester report 2026-10-28 15:00; object-update-bundles.md 10.3): a creation retry, so a full
            # bundle also in delta mode ([ics] object_update_mode)
            self.m.later(float(again), lambda e=ent: w.update(e, f"{e.name} again", full=True) if e.eid in w.entities
                         and getattr(e, "carried_by", None) is None and not getattr(e, "flying", False) else None)
        self.props.append(ent)
        # Super Strength's target check (0x9d01d0, C): unit flags sharing a bit with 0x82, targetable 0x10000AA7 and
        # the status tag 0x10000029; the client caches them only as CHANGES (World._late_flags)
        extra = {**{str(k): v for k, v in ((self.ic.get("liftable_props_extra") or {}).get("all") or {}).items()},
                 **{str(k): v for k, v in ((self.ic.get("liftable_props_extra") or {}).get(kind) or {}).items()}}
        flags = [(0x1000019D, KIND_U32, int(extra.pop("0x1000019D", info["flags"])))]
        ent.kind_flags = flags[0][2]
        ent.on_destroy = lambda e=ent: self._consumed(e)
        flags += [(_did(k), KIND_BOOL, 1 if v else 0) for k, v in extra.items()]
        delay = float(self.ic.get("unit_flags_delay", 0.8) or 0.8)
        self.m.later(delay, lambda e=ent, f=flags: w._late_flags(e, f))
        names = (self.ic.get("liftable_respawn_scriptlets" if respawn else "liftable_spawn_scriptlets") or {}).get(kind)
        for k, name in enumerate(names or ()):
            self.m.later(0.4 + 0.3 * k, lambda e=ent, n=name: w.scriptlet(e, n, f"{e.name}: {n} (0x8d)")
                         if e.eid in w.entities else None)
        self.m.later(delay + 0.2, lambda e=ent: self._aura(e, True) if e.eid in w.entities
                     and getattr(e, "carried_by", None) is None and not getattr(e, "flying", False) else None)
        self._block(ent, True)
        return ent

    def _aura(self, ent, on):
        """2026-10-29 tester report 21:10 ("the meteorites lack a red aura", screenshot 73 of the original: the rubble
        with red glowing cracks and a red orb; liftable-aura-lift-throw-break.md 1). The rock's world state 0x2E000D22
        uses table 0x1D000385, whose _Entity_OnSetClientRelationship 0x100003A6 is a 0x22 container on colour index
        0x100007A2 setting appearance set 0x19000A61 group 0x10000004 (5 -> 0x1000011E, material 0x16000E7D = RGBA 1 0 0
        0.75, red); its children 0x2E000D13 / D14 (table 0x1D00038B) tint the same group by the same index (Vfx_Startup).
        The client runs that key only on a PVP_Team CHANGE (0xA7B0D0 from listener 0xA813F0, C) and takes colour override
        0x10000CF0 first for teams 0..2; the rock never got a team change, so it stayed untinted (C path, P that the red
        is this tint). On the ground: override = [ics] liftable_aura[kind].colour, then team 3 -> 0 by 0x6 (the change);
        lifted (the sub-skill set the object's team to the thrower's, C 0x34000161 S7 / 0x34000177 S3): team 3 = colour
        0 = TeamColor Null; a respawned object starts tinted again. "base_on" / "base_off": the crater's own keys (its
        table 0x1D0004AA holds only Vfx_Active_State1-3 / Vfx_Stop) at the same moments. {} = none (as before)."""
        spec = (self.ic.get("liftable_aura") or {}).get(getattr(ent, "liftable", None))
        if not spec or ent.eid not in self.w.entities:
            return
        w = self.w
        colour = int(spec.get("colour", 0) or 0)
        if colour:
            if on:
                ent.extra_props = [p for p in ent.extra_props if p[0] != PROP_COLOUR_OVERRIDE] +                     [(PROP_COLOUR_OVERRIDE, KIND_ENUM, colour)]
                w.send(f"{ent.name}: colour override {colour} (0x6)",
                       M.set_property(ent.eid, PROP_COLOUR_OVERRIDE, KIND_ENUM, colour))
                w.send(f"{ent.name}: team 3 (0x6)", M.set_property(ent.eid, PROP_TEAM, KIND_INT, 3))
                w.send(f"{ent.name}: team 0, aura on (0x6)", M.set_property(ent.eid, PROP_TEAM, KIND_INT, 0))
            elif getattr(ent, "aura_on", False):
                w.send(f"{ent.name}: team 3, aura off (0x6)", M.set_property(ent.eid, PROP_TEAM, KIND_INT, 3))
        if on or getattr(ent, "aura_on", False):
            base = self.bases.get((getattr(ent, "lift_spec", None) or {}).get("index"))
            if base is not None and base.eid in w.entities:
                for k, name in enumerate(spec.get("base_on" if on else "base_off") or ()):
                    self.m.later(0.1 * k, lambda b=base, n=name: w.scriptlet(b, n, f"{b.name}: {n} (0x8d)")
                                 if b.eid in w.entities else None)
        if on and not getattr(ent, "aura_probed", False):
            ent.aura_probed = True
            for k, step in enumerate(self.ic.get("liftable_aura_probe") or ()):
                if str(step.get("kind", "rock")) == getattr(ent, "liftable", None):
                    self.m.later(float(step.get("at", 0.0)), lambda e=ent, s=step, i=k: self._probe_step(e, s, i))
        ent.aura_on = bool(on)

    def _probe_step(self, ent, step, index):
        """2026-10-29 tester report 23:03 ("the meteorites' red aura is not the correct one", screenshots 73 / 83;
        scorecard-accolades-meteor-aura.md 2): one step of [ics] liftable_aura_probe on a lying object, logged so a
        screenshot's time names what shows. step = {"at": s after the aura is on, "kind", "target": "object" | "base",
        "key": scriptlet name, "force": send it even when the target's tables lack it (e.g. the team-hologram table
        0x1D00038B's Vfx_Active_Red), "colour": team-colour override (0 = Null) re-applied by a team change}."""
        w = self.w
        if ent.eid not in w.entities or getattr(ent, "carried_by", None) is not None or getattr(ent, "flying", False):
            return
        tgt = ent
        if step.get("target") == "base":
            tgt = self.bases.get((getattr(ent, "lift_spec", None) or {}).get("index"))
            if tgt is None or tgt.eid not in w.entities:
                return
        if "colour" in step:
            colour = int(step.get("colour") or 0)
            w.send(f"aura probe {index}: {tgt.name} colour {colour} (0x6 override, team 3 -> 0)",
                   M.set_property(tgt.eid, PROP_COLOUR_OVERRIDE, KIND_ENUM, colour))
            w.send(f"aura probe {index}: {tgt.name} team 3 (0x6)", M.set_property(tgt.eid, PROP_TEAM, KIND_INT, 3))
            w.send(f"aura probe {index}: {tgt.name} team 0 (0x6)", M.set_property(tgt.eid, PROP_TEAM, KIND_INT, 0))
        name = step.get("key")
        if not name:
            return
        key = w.data.scriptlet_key(str(name)) if not str(name).startswith("0x") else int(str(name), 16)
        label = f"aura probe {index}: {tgt.name}: {name} (0x8d)"
        if w.scriptlet(tgt, key, label):
            return
        if step.get("force") and key:
            w.scriptlet_runs += 1
            w.send(label + " forced (not in its tables)", M.start_scriptlets(tgt.eid, [(key, w.scriptlet_runs)], 0))
        else:
            w.log(f"aura probe {index}: {tgt.name}: {name} not in its tables, not sent")

    def _block(self, ent, on):
        """2026-10-28 13:52 (tester: champions and minions walk through the parked vehicles; in the original they block):
        a parked liftable's footprint is unwalkable on the match's navmesh, so every server path (the champion's
        walk_to, the bots', the minions' lane legs) goes round it; lifted, consumed or gone = walkable again. The client
        does not move the local champion itself (client-movement.md 0: no prediction), so nothing more is needed on its
        side ([ics] liftable_blockers: world state -> [half length, half width, angle offset, forward offset], the
        length along the vehicle's heading; liftable_blocker_margin: m added to both, a walker's radius; {} = off).
        2026-10-28 15:00 (vehicle-lift-and-position.md 1.2 / 1.4, C .entity box): the optional 4th element moves the box
        centre along its length from the vehicle's origin (the SUV's box 0x2D00061C is centred 0.177 m forward)."""
        nav = self.w.nav
        if nav is None:
            return
        key = ("liftable", ent.eid)
        if not on:
            nav.unblock(key)
            return
        size = (self.ic.get("liftable_blockers") or {}).get(f"0x{(ent.world_state or _did(ent.lift_spec.get('world_state'))):08X}")
        if not size:
            return
        margin = float(self.ic.get("liftable_blocker_margin", 0.0) or 0.0)
        angle = ent.heading + (float(size[2]) if len(size) > 2 else 0.0)
        fwd = float(size[3]) if len(size) > 3 else 0.0
        nav.block(key, ent.pos[0] + fwd * math.cos(angle), ent.pos[1] + fwd * math.sin(angle),
                  float(size[0]) + margin, float(size[1]) + margin, angle)

    def _consumed(self, ent):
        """DestroyEntity from a script (Consume 0x340001C4 on a rock / vehicle): it can no longer be lifted, fades
        out and respawns like a thrown one."""
        if ent not in self.props or getattr(ent, "carried_by", None) is not None:
            return
        ent.broken = True
        self.props.remove(ent)
        self._block(ent, False)
        self.m.log(f"{ent.name} consumed")
        # 2026-10-29 10:23 (tester: the consumed vehicle / meteorite vanished about a second after the animation, not
        # with it): the destroy action already started with DestroyEntity (World.destroy); the object goes at the
        # script's own delay plus [ics] liftable_consume_remove_after s (0.6 before)
        self._key(ent, FADE_OUT_KEY, f"{ent.name}: Vfx_Fade_Out (0x8d)")
        if self.ic.get("liftable_consume_destroy_action", True):
            # 2026-10-29 tester report of 18:31 (liftable-throw-destruction.md 4): DestroyEntity's client execute also
            # plays _HFSM_DestroyEntityAction_Optional, the only one the vehicles' tables hold (World.destroy sent
            # _HFSM_DestroyEntityAction alone, which they lack); [ics] liftable_destroy_actions
            for name in self.ic.get("liftable_destroy_actions") or ():
                if name != "_HFSM_DestroyEntityAction":
                    self.w.scriptlet(ent, name, f"{ent.name}: {name} (0x8d, DestroyEntity)")
        after = float(self.ic.get("liftable_consume_remove_after", 0.0) or 0.0)
        if after > 0:
            self.m.later(after, lambda: self._gone(ent))
        else:
            self._gone(ent)

    def _gone(self, ent):
        w = self.w
        self._block(ent, False)
        if ent.eid in w.entities:
            w.remove(ent, f"{ent.name} gone (0x3)")
        if ent in self.props:
            self.props.remove(ent)
        spec = ent.lift_spec
        secs = float(self.ic.get("liftable_respawn_seconds", 60.0) or 0)
        if secs > 0 and spec.get("respawn", True) and not self.m.over:
            self.m.later(secs, lambda: self._spawn(spec, respawn=True))

    # ---- events ------------------------------------------------------------------------------------------------------
    def _on_event(self, event, **d):
        if event == "lift":
            self.lift(d.get("ent"), d.get("obj"), d.get("inst"))
        elif event == "throw":
            self.throw(d.get("ent"), d.get("point"), d.get("target"))
        elif event == "carry_cooldown":
            ch = d.get("ent")
            obj = getattr(ch, "carry_indicator_pending", None)
            if obj is not None:
                self._pending_indicator(ch, obj)
        elif event == "skill_press":
            self._press(d.get("ent"), d.get("slot"), d.get("key"))

    def _press(self, ch, slot, event):
        """2026-10-29 tester report 19:55 (the meteorite could not be thrown; liftable-carry-throw-press.md 1, C traffic
        19:52:29.131-44.831: 13 presses of slot 7 reached the server as 0x20EA 0x10000023 and no 0x20EE throw order
        followed any of them, while every working throw (the vehicle at 19:49:47.559, the rock at 19:52:48.422) sent
        its 0x20EE 0-34 ms after the 0x20EA): a press of the carry slot that no throw order follows within [ics]
        liftable_throw_press_window s counts as unanswered; at the [ics] liftable_throw_on_press-th one in a row the
        server throws toward the champion's facing (the rock flies to its range; a vehicle 6 m ahead, at most its range).
        0 = never (only the client's order throws, as before)."""
        need = int(self.ic.get("liftable_throw_on_press", 2) or 0)
        if (need <= 0 or ch is None or ch is not self.w.champion or event != PRESS_EVENT
                or getattr(ch, "carrying", None) is None or not getattr(ch, "carry_ready", False)
                or slot != getattr(ch, "carry_slot", None)):
            return
        obj = ch.carrying
        stamp = time.time()
        ch.carry_press_at = stamp

        def check():
            if (getattr(ch, "carrying", None) is not obj or not getattr(ch, "carry_ready", False)
                    or getattr(ch, "carry_press_at", None) != stamp):
                return
            ch.carry_unanswered = int(getattr(ch, "carry_unanswered", 0) or 0) + 1
            self.m.log(f"{ch.name}: slot {slot} pressed while carrying {obj.name}, no throw order came "
                       f"({ch.carry_unanswered} of {need})")
            if ch.carry_unanswered >= need:
                ch.carry_unanswered = 0
                aim = getattr(ch, "carry_aim", None) if self.ic.get("liftable_press_aim", True) else None
                self.m.log(f"{ch.name}: throws {obj.name} on the press (liftable_throw_on_press), "
                           + (f"at the aimed ({aim[0]:.1f}, {aim[1]:.1f})" if aim else "toward the facing"))
                self.throw(ch, aim)
        self.m.later(max(0.05, float(self.ic.get("liftable_throw_press_window", 0.35) or 0.35)), check)

    def _key(self, ent, key, label, target=None, variables=None):
        if ent is not None and (ent is self.w.champion or ent.eid in self.w.entities):
            self.w.scriptlet(ent, key, label, target=target, variables=variables)

    def _refused(self, ch, obj, inst, why):
        """A lift Super Strength's script asked for that cannot be: logged, and 0x34000164 ended (0x10000009) so its S4
        input hold never outlives the request (liftable-softlock.md 2)."""
        self.m.log(f"{ch.name}: does not lift {obj.name}: {why}")
        if inst is not None and not inst.removed:
            inst.post(EVENT_END, 0.0)

    @staticmethod
    def _stale_target(obj, inst):
        """The order had no target of its own (target 0x0): the script's TargetIID is the last one the VM kept
        (script_runtime.activate leaves it when an order has none). False when there is no order record."""
        req = getattr(inst, "request", None)
        if not isinstance(req, dict):
            return False
        t = req.get("TargetIID")
        return not (t is obj or (t is not None and getattr(t, "eid", t) == obj.eid))

    def lift(self, ch, obj, inst=None):
        w = self.w
        if ch is None or obj is None or getattr(ch, "carrying", None) is not None:
            return
        if self.ic.get("liftable_lift_guard", True):
            # 2026-10-30 tester report 11:23 (liftable-softlock.md 2): only a lying object that is the order's target
            why = None
            if obj not in self.props or obj.eid not in w.entities:
                why = "it is gone"
            elif getattr(obj, "flying", False) or getattr(obj, "broken", False) or getattr(obj, "tossing", False):
                why = "it is in flight or landed"
            elif getattr(obj, "carried_by", None) is not None:
                why = "it is carried"
            elif self._stale_target(obj, inst):
                why = "the order had no target (a stale TargetIID)"
            if why:
                self._refused(ch, obj, inst, why)
                return
        elif obj not in self.props or getattr(obj, "carried_by", None) is not None:
            return
        info = KINDS[obj.liftable]
        reach = float(self.ic.get("liftable_reach", 6.0) or 6.0)
        if ch.distance_to(obj) > reach:
            self.m.log(f"{ch.name}: {obj.name} out of reach ({ch.distance_to(obj):.1f} m)")
            if inst is not None and not inst.removed:
                inst.post(EVENT_END, 0.1)
            return
        obj.carried_by, ch.carrying, ch.carry_inst = ch, obj, inst
        ch.carry_queued_throw = None
        ch.carry_aim, ch.carry_walk = None, None
        # 2026-10-30 tester report 11:23 (liftable-softlock.md 1): the input back is due once per lift, not once per
        # script instance (the slot's instance lives for the whole match) ([ics] liftable_input_back_per_lift)
        ch.carry_input_back_sent = False
        ch.carry_phase, ch.carry_phase_at = "lift", self.m.t
        self.carriers.add(ch)
        ch.carry_slot = getattr(inst, "slot", None)
        ch.carry_ready = False
        ch.dest, ch.path, ch.speed = None, [], 0.0
        ch.heading = math.atan2(obj.pos[1] - ch.pos[1], obj.pos[0] - ch.pos[0])
        early = bool(self.ic.get("liftable_throw_skill_at_lift", True))
        if early:
            # 2026-10-28 12:56 (tester: the lift has no proper animation; liftables-camps-animations.md 2): the throw
            # skill's slot table rides in this facing bundle, before the pickup key, not in a second full bundle in
            # the middle of the pickup clip (it went 0.27 s / 0.55 s into the rock / vehicle clip)
            self._throw_button(ch, obj, True, send=False)
        if self.ic.get("liftable_hold_champion_bundles", True) and ch is w.champion:
            ch.bundle_hold, ch.bundle_held = True, None
        w.update(ch, f"{ch.name} faces {obj.name}" + (" (throw skill in its slot)" if early else ""), force=True)
        w.set_blocking(obj, False)
        self._block(obj, False)
        self.m.log(f"{ch.name} lifts {obj.name}")
        lead = float(self.ic.get("liftable_face_lead", 0.0) or 0.0)
        if lead > 0:
            # 2026-10-29 tester report 2026-10-29 14:40 (the lift looks as if animations were skipped; agl-qer-lift.md 4,
            # C traffic 14:21:34.997): the facing bundle's turn is applied 0.1 s after it, the pickup 0x8D at once, so
            # the turn cut into the pickup clip; the pickup key and its timeline wait [ics] liftable_face_lead s
            def go():
                if getattr(ch, "carrying", None) is not obj:
                    return
                if not ch.alive:
                    self._drop(ch, obj)
                    return
                self._lift_keys(ch, obj, info)
            self.m.later(lead, go)
            return
        self._lift_keys(ch, obj, info)

    def _lift_keys(self, ch, obj, info):
        """The pickup key on the champion (and the object) and the clip-timed grab / toss / catch / hold."""
        # 2026-10-26 (grab-arm-carry.md 2, C clips): the pickup key at once (rock: graph Rubble_Pickup; vehicle: InitCarPickup
        # on both), the object attached to the hand at the clip's grab frame, ready to throw at its Hold state
        self._key(ch, info["init"], f"{ch.name}: pick up {obj.name} (0x8d)", target=obj)
        if info["on_object"]:
            self._key(obj, info["init"], f"{obj.name}: picked up (0x8d)", target=ch)
        toss = bool(info.get("toss")) and bool(self.ic.get("liftable_vehicle_toss", True))
        car_at = 0.1
        if toss:
            car_at, toss_at, catch_at, ready_at = self._toss_timeline(ch)
        if info["graph"]:
            self.m.later(car_at, lambda: self._key(ch, RAISE_EVENT_KEY, f"{ch.name}: graph event CarPickup",
                                                   variables=[(RAISE_EVENT_VAR, KIND_ENUM, info["graph"])])
                         if getattr(ch, "carrying", None) is obj else None)
        if toss:
            # 2026-10-28 15:00 (tester: the vehicle lift starts, then cuts to already holding it; vehicle-lift-and-
            # position.md 2): 0x34000161's own order instead of the vehicle over the head + PickupObject at the grab
            # frame: CarPickup, the toss at Car_Pickup's grab hook, the catch (S9) in Hold, ready AttachmentDuration later
            self.m.log(f"{ch.name}: {obj.name} CarPickup +{car_at:.3f} s, toss +{toss_at:.3f}, catch +{catch_at:.3f}, "
                       f"ready +{ready_at:.3f}")
            self._toss(ch, obj, toss_at, catch_at)
            self.m.later(catch_at, lambda: self._catch(ch, obj, info))
            self.m.later(ready_at, lambda: self._hold(ch, obj))
            return

        def grab():
            if getattr(ch, "carrying", None) is not obj:
                return
            self._input_back(ch)
            self._aura(obj, False)
            if info["pickup"]:
                self._key(ch, info["pickup"], f"{ch.name}: SuperStrength_PickupObject (0x8d)", target=obj)
                self._key(obj, info["pickup"], f"{obj.name}: SuperStrength_PickupObject (0x8d)", target=ch)
            for key in info["lifted"]:
                self._key(obj, key, f"{obj.name}: picked up (0x8d)")
            if self._attached_kind(obj):
                self._attach(ch, obj, True)
                self._rebuild(obj, "liftable_attach_rebuild", "attached")
            else:
                # vehicles-carry-collision.md 1: over the head by its own movement bundles (no containment)
                self._carry(ch, obj, force=True)
                if not self.ic.get("liftable_attach_rebuild_attached_only", True):
                    self._rebuild(obj, "liftable_attach_rebuild", "over the head")
            self._graph(ch, HIT_OFF, "CbtState_DisableHit")
        sig = self.ic.get("super_strength_cast_signals") or {}
        self.m.later(float(sig.get(obj.liftable + "_grab", info["grab"])), grab)
        self.m.later(float(sig.get(obj.liftable + "_hold", info["hold"])), lambda: self._hold(ch, obj))

    def _input_back(self, ch):
        """2026-10-29 tester report 21:10 ("lifting still looks a bit slow"; liftable-aura-lift-throw-break.md 2, C
        scripts): Super Strength 0x34000164 waits in S4 for 0x100000BB, which the sub-skill raised when the object left
        the ground: the vehicle's 0x34000161 at S7 (the toss, 0.46 s into AGL's lift), the rock's 0x34000177 at S3 (the
        grab frame, 0.22 s); ics posted it 1.2 s after the pickup for both ([ics] raise_event_follow), so the slot's
        "kept ready" 0x20F8, and the throw indicator that waits for it, came 0.7-1.0 s late. Posted here now
        ([ics] liftable_input_back; false = raise_event_follow's fixed delay, script_nodes.py)."""
        inst = getattr(ch, "carry_inst", None)
        if not self.ic.get("liftable_input_back", True) or inst is None or inst.removed:
            return
        if self.ic.get("liftable_input_back_per_lift", True):
            if getattr(ch, "carry_input_back_sent", False):
                return
            ch.carry_input_back_sent = True
        else:
            if getattr(inst, "_input_back_sent", False):
                return
            inst._input_back_sent = True
        inst.post(EVENT_INPUT_BACK, 0.0)

    def _hold(self, ch, obj):
        """Ready to throw (the pickup clip's Hold state; a tossed vehicle: AttachmentDuration after the catch): the
        carry walk speed, the throw skill in the slot, one carry bundle.
        2026-10-28 15:00 (vehicle-lift-and-position.md 7.6): a carrier that died before this drops the object now
        (tick() checks only ready carries)."""
        if getattr(ch, "carrying", None) is not obj:
            return
        if not ch.alive:
            self._drop(ch, obj)
            return
        if not hasattr(ch, "carry_saved_speed"):
            ch.carry_saved_speed = ch.move_speed
        ch.move_speed = min(ch.move_speed, float(self.ic.get("liftable_carry_speed", 3.5) or ch.move_speed))
        ch.carry_ready = True
        ch.carry_phase, ch.carry_phase_at = "ready", self.m.t
        queued = getattr(ch, "carry_queued_throw", None)
        if queued is not None:
            ch.carry_queued_throw = None
            self._carry(ch, obj, force=getattr(obj, "attach_parent", None) is None)
            self.throw(ch, queued[0], queued[1])
            return
        if getattr(ch, "carry_base_block", None) is None:
            self._throw_button(ch, obj, True)
        self._carry(ch, obj, force=getattr(obj, "attach_parent", None) is None)
        wait = float(self.ic.get("liftable_indicator_after_cooldown", 1.5) or 0.0)
        if wait > 0 and ch is self.w.champion and getattr(ch, "carry_cooldown_end", None) is None:
            # 2026-10-29 tester report 19:55 ("I lifted a meteorite but could not throw it; only after casting a Q";
            # liftable-carry-throw-press.md 1, C traffic 19:52:23.369 / 24.096): the rock is ready 0.30 s into the
            # lift, while Super Strength's own cast (0x34000164 S4) runs until 1.2 s; its indicator (0x2180 / 0x20F9)
            # went 0.7 s BEFORE the slot's "kept ready" 0x20F8, the reverse of the vehicle carry that threw normally.
            # The indicator now waits for that 0x20F8 (World on_cooldown -> "carry_cooldown"), at most this many s
            # ([ics] liftable_indicator_after_cooldown; 0 = liftable_throw_indicator_delay after the hold, as before)
            ch.carry_indicator_pending = obj
            self.m.later(wait, lambda: self._pending_indicator(ch, obj))
            return
        self._schedule_indicator(ch, obj)

    def _schedule_indicator(self, ch, obj):
        delay = float(self.ic.get("liftable_throw_indicator_delay", 0.05) or 0.0)
        self.m.later(delay, lambda: self._indicator(ch, True) if getattr(ch, "carrying", None) is obj
                     and getattr(ch, "carry_ready", False) else None)

    def _pending_indicator(self, ch, obj):
        """The throw indicator held by _hold until the slot's "kept ready" cooldown notice went (or its wait ran out)."""
        if getattr(ch, "carry_indicator_pending", None) is not obj:
            return
        ch.carry_indicator_pending = None
        if getattr(ch, "carrying", None) is obj and getattr(ch, "carry_ready", False):
            self._schedule_indicator(ch, obj)

    def _indicator(self, ch, on):
        """2026-10-29 12:45 (tester report 2026-10-29 12:45: the throw range and the target area are not shown;
        throw-truck-padlock.md 1, C client script / code): both throw sub-skills (0x480003C9 / 0x480004A2) name the
        client slot script 0x340001A3 (0x1000063A), which ignores the button's own 0x10000023 and shows the slot's
        indicator only on ScriptEvent 0x100000B6 (S0 -> S1: node 0x10000056 -> 0xa5dab0 -> 0xa39360) and hides it on
        0x100000B7: the original showed it for the whole carry. 0x20F9(slot, 0) once ready to throw, 0x20F9(slot, 1) at
        the throw / drop ([ics] liftable_throw_indicator; false = none, as before)."""
        slot = getattr(ch, "carry_slot", None)
        if ch is not self.w.champion or slot is None or not self.ic.get("liftable_throw_indicator", True):
            return
        if bool(getattr(ch, "carry_indicator", False)) == bool(on):
            return
        ch.carry_indicator = bool(on)
        # tester report 2026-10-29 15:30 (throw-padlock-coredeath.md 1.2, C 0xa5dab0 / 0xa6d800): the 0x20F9 path draws
        # only while the client already targets the slot; 0x2180 / 0x217F start / end it with no gate
        # ([ics] liftable_throw_indicator_messages)
        msgs = [str(x).lower() for x in (self.ic.get("liftable_throw_indicator_messages") or ["0x20f9"])]
        if "0x2180" in msgs:
            self.w.send(f"slot {slot}: throw indicator {'on (0x2180)' if on else 'off (0x217f)'}",
                        M.slot_indicator_start(slot) if on else M.slot_indicator_end(slot))
        if "0x20f9" in msgs:
            self.w.send(f"slot {slot}: throw indicator {'on' if on else 'off'} (0x20f9 {0 if on else 1})",
                        M.skill_availability(ch.eid, slot, not on))

    # ---- a vehicle's toss and catch (0x34000161 S6-S9) -------------------------------------------------------------
    def _graph_times(self, ch):
        """2026-10-28 15:00 (vehicle-lift-and-position.md 2.2 / 6.2, C graph data): the champion's own
        SM_SuperStrength_Car timings from data/skill_graphs.json (ics.graph's data: read even while [ics] graph_runtime
        is off). The machine is found by its structure, not by names (Joker's and six other graphs rename the machine
        or its states): its start state (Pickup_Start) leaves on SuperStrength_CarPickup to Car_Pickup, whose first clip
        gives car_pickup = its start frame / Pickup_Start's speed (when Pickup_Start's cropped clip reaches that frame:
        the whole bend-and-grab), hook = its code-3 grab hook and hold = its state_to_state (both s after CarPickup).
        CAR_TIMES for a value the graph does not give."""
        gdef = GR.data().for_variant(getattr(ch, "class_id", 0) or 0)
        name = gdef.name if gdef is not None else None
        if name in _CAR_TIMES_BY_GRAPH:
            return _CAR_TIMES_BY_GRAPH[name]
        out = dict(CAR_TIMES)
        for mach in (gdef.machines if gdef is not None else ()):
            start = mach["states"].get(str(mach["start"]))
            go = next((t for t in (start["out"] if start else ()) if t["n"] == "SuperStrength_CarPickup"), None)
            pick = mach["states"].get(str(go["to"])) if go is not None else None
            if not pick or not start["body"]["clips"] or not pick["body"]["clips"]:
                continue
            c0, c1 = start["body"]["clips"][0], pick["body"]["clips"][0]
            first = float(c1.get("start") or 0.0)
            speed = float(c1.get("speed") or 1.0) or 1.0
            out["car_pickup"] = first / (float(c0.get("speed") or 1.0) or 1.0)
            for key, want in (("hook", lambda tr: tr.get("code") == 3),
                              ("hold", lambda tr: tr.get("n") == "state_to_state")):
                t = next((float(tr["t"]) for tr in c1["trig"] if want(tr) and not tr.get("rel")), None)
                if t is not None:
                    out[key] = max(0.0, t - first) / speed
            break
        _CAR_TIMES_BY_GRAPH[name] = out
        return out

    def _toss_timeline(self, ch):
        """(CarPickup, toss, catch, ready) in s after the lift of a tossed vehicle (vehicle-lift-and-position.md 2.3 /
        3.2): CarPickup at [ics] liftable_car_pickup_at ("graph" or < 0 = the graph's car_pickup); the toss at
        Car_Pickup's grab hook (0x34000161 S6 -> S7 on cast signal 3); the catch [ics] liftable_toss_seconds later, but
        never before the graph has reached Hold (+0.05 s), the only state that takes the catch's PickupCar; ready to
        throw [ics] liftable_attach_seconds after the catch (S9 -> S4)."""
        g = self._graph_times(ch)
        car_at = self.ic.get("liftable_car_pickup_at", 0.05)
        if car_at is None or isinstance(car_at, str) or float(car_at) < 0:
            car_at = g["car_pickup"]
        car_at = float(car_at)
        toss_at = car_at + g["hook"]
        flight = max(0.0, float(self.ic.get("liftable_toss_seconds", 0.65) or 0.0))
        catch_at = max(toss_at + flight, car_at + g["hold"] + 0.05)
        return car_at, toss_at, catch_at, catch_at + max(0.0, float(self.ic.get("liftable_attach_seconds", 0.1) or 0.0))

    def _toss(self, ch, obj, t0, t1):
        """2026-10-28 15:00 (tester: the vehicle lift starts, then cuts to already holding it; vehicle-lift-and-position.md
        2.5, C bytes / C client rule): fase3-ie put the vehicle over the head in ONE state 3.4-4.2 m from where it stood,
        0.1 s into the lift, and the client places a state more than 2 m away at once (0x60B5F0 -> 0x5C9E90; a nearer one
        is steered to). 0x34000161 S7 lobs it from where it stands onto the champion at Car_Pickup's grab hook and S9
        catches it TossDuration 0.3 + CatchDuration 0.35 s later (C defaults). Here it flies from t0 to t1 (s after the
        lift) in [ics] liftable_toss_steps states, each well under 2 m: on the line from its spot to the hold point (the
        champion + liftable_carry_offset, recomputed each state) plus [ics] liftable_toss_arc m * sin(pi f) up, its
        heading turned toward the champion's; S7's scriptlet on it at t0 ([ics] liftable_toss_scriptlet). The catch at
        t1 puts it on the hold point. A carrier that dies meanwhile drops it where it is."""
        w = self.w
        steps = max(2, int(self.ic.get("liftable_toss_steps", 12) or 12))
        arc = float(self.ic.get("liftable_toss_arc", 1.5) or 0.0)
        s0, h0 = list(obj.pos), float(obj.heading)

        def holding():
            if getattr(ch, "carrying", None) is not obj or obj.eid not in w.entities:
                return False
            if not ch.alive:
                self._toss_end(obj)
                self._drop(ch, obj)
                return False
            return True

        def start():
            if not holding():
                return
            obj.tossing = True
            self._input_back(ch)
            self._aura(obj, False)
            spec = self.ic.get("liftable_toss_scriptlet") or {}
            key = _did(spec.get("key"))
            if key:
                variables = [(_did(p), w.data.property_kind(_did(p)) or KIND_DID, _did(v))
                             for p, v in (spec.get("vars") or {}).items()]
                name = w.data.scriptlet_names().get(key, f"{key:#x}")
                self._key(obj, key, f"{obj.name}: tossed onto {ch.name}, {name} (0x8d)", variables=variables or None)

        def hop(i):
            if not getattr(obj, "tossing", False) or not holding():
                return
            f = i / steps
            e = self._hold_point(ch, obj)
            p = [s0[k] + (e[k] - s0[k]) * f for k in range(3)]
            p[2] += arc * math.sin(math.pi * f)
            obj.pos, obj.heading = p, h0 + math.remainder(ch.heading - h0, math.tau) * f
            obj.speed, obj.dest, obj.path = 0.0, None, []
            w.update(obj, f"{obj.name} tossed onto {ch.name} ({i}/{steps})")
        if self.ic.get("liftable_toss_timed", True):
            # 2026-10-30 tester report 11:23 (liftable-softlock.md 6): one state per liftable_throw_step_seconds at the
            # curve's own send time (the fixed fractions went two to a match tick and hopped)
            step_s = max(0.02, float(self.ic.get("liftable_throw_step_seconds", 0.033) or 0.033))
            span = max(1e-3, t1 - t0)
            clock = {"t0": None, "n": 0}
            # 2026-10-30 tester report 12:05 ("the vehicle lift animation still looks weird"; liftable-lift-throw-
            # wreck.md 1, C traffic 12:01:35.114-.424): the toss states went with speed 0 and no newer teleport sequence,
            # ~63 ms apart: the client steered the body toward a target that stood still between states (0x60B5F0, a
            # state within 2 m), 0.1 s behind, and the steering drops the vertical part of a body off the ground
            # (throw-padlock-coredeath.md 1.3), so the lob crept along and popped up to the head at the catch's snap.
            # Now each toss state is snapped and carries the curve's 3D velocity (heading, speed, motion pitch 0x40), as
            # the throw flight (_fly_timed), from f = 0 on, with the facing turned by its offset ([ics]
            # liftable_toss_velocity: kinds; [] = steered states at speed 0, as before)
            velocity = obj.liftable in (self.ic.get("liftable_toss_velocity") or ())

            def place(f):
                e = self._hold_point(ch, obj)
                p = [s0[k] + (e[k] - s0[k]) * f for k in range(3)]
                p[2] += arc * math.sin(math.pi * f)
                face = h0 + math.remainder(ch.heading - h0, math.tau) * f
                obj.dest, obj.path = None, []
                if velocity:
                    vx, vy = (e[0] - s0[0]) / span, (e[1] - s0[1]) / span
                    vz = ((e[2] - s0[2]) + arc * math.pi * math.cos(math.pi * f)) / span
                    vh = math.hypot(vx, vy)
                    head = math.atan2(vy, vx) if vh > 1e-6 else face
                    obj.pos, obj.heading = p, head
                    obj.speed, obj.vel_pitch = math.hypot(vh, vz), math.atan2(vz, vh)
                    obj.facing_offset = math.remainder(face - head, math.tau)
                    w.teleport(obj)
                else:
                    obj.pos, obj.heading, obj.speed = p, face, 0.0

            def timed():
                if not getattr(obj, "tossing", False) or not holding():
                    return
                f = (self.m.t - clock["t0"]) / span
                if f >= 1.0 - 1e-6:
                    return              # the catch puts it on the hold point
                clock["n"] += 1
                place(f)
                w.update(obj, f"{obj.name} tossed onto {ch.name} (f {f:.2f})")
                self.m.later(min(step_s, max(0.0, clock["t0"] + span - self.m.t)), timed)

            def go():
                start()
                if getattr(obj, "tossing", False):
                    clock["t0"] = self.m.t
                    if velocity:
                        # the lob leaves the ground now: the client dead-reckons it from this state on
                        place(0.0)
                        w.update(obj, f"{obj.name} tossed onto {ch.name} (f 0.00)")
                    self.m.later(min(step_s, span), timed)
            self.m.later(t0, go)
            return
        self.m.later(t0, start)
        for i in range(1, steps):
            self.m.later(t0 + (t1 - t0) * i / steps, lambda i=i: hop(i))

    @staticmethod
    def _toss_end(obj):
        """The toss is over (caught, dropped, aborted): its velocity pitch and facing offset (liftable_toss_velocity)
        leave the object's movement state."""
        if getattr(obj, "tossing", False) and getattr(obj, "liftable", None) != "rock":
            obj.vel_pitch, obj.facing_offset = None, None
        obj.tossing = False

    def _catch(self, ch, obj, info):
        """2026-10-28 15:00 (vehicle-lift-and-position.md 2.2 / 2.3, C graph data + script): 0x34000161 S9 = DisableHit,
        AttachEntity at AttachmentOffset (0, 0, 2.5) (here the vehicle's own state on the hold point), then PickupObject
        0x100007A1 on the champion and on the vehicle. Its graph event SuperStrength_PickupCar is taken only by
        SuperStrength_Car_Hold (-> Car_Catch: the car lands in the hands); fase3-ie sent it with CarPickup, while the
        graph was still in Car_Pickup, which dropped it, so the catch never played.
        2026-10-29 (fase3-if review): a kind in [ics] liftable_attach_kinds is caught by the containment attach, as
        grab() does (the documented ["rock", "vehicle"] switch-back did nothing while the toss is on)."""
        self._toss_end(obj)
        if getattr(ch, "carrying", None) is not obj or obj.eid not in self.w.entities:
            return
        if not ch.alive:
            self._drop(ch, obj)
            return
        self._graph(ch, HIT_OFF, "CbtState_DisableHit")
        attached = self._attached_kind(obj)
        if attached:
            obj.pos, obj.heading, obj.speed = self._hold_point(ch, obj), ch.heading, 0.0
            self._attach(ch, obj, True)
        else:
            self._carry(ch, obj, force=True)
        if info["pickup"]:
            self._key(ch, info["pickup"], f"{ch.name}: SuperStrength_PickupObject (0x8d)", target=obj)
            self._key(obj, info["pickup"], f"{obj.name}: SuperStrength_PickupObject (0x8d)", target=ch)
        if attached or not self.ic.get("liftable_attach_rebuild_attached_only", True):
            # 2026-10-30 (old-vs-ics comparison, docs/re-notes/vehicle-lift-old-vs-ics.md 3.1): 0x8B clears the pieces
            # and builds them again (0x631050, C); it is needed only to move an ATTACHED object's pieces under the
            # champion's render node. A vehicle carried by its own states moves its pieces with its frame (C,
            # vehicles-carry-collision.md 1.4), so the rebuild only re-made the vehicle in the middle of the catch
            # ([ics] liftable_attach_rebuild_attached_only; false = always, as before)
            self._rebuild(obj, "liftable_attach_rebuild", "attached" if attached else "over the head")

    def _rebuild(self, obj, key, why):
        """2026-10-28 12:56 (tester: a lifted vehicle vanishes over the champion; liftables-camps-animations.md 1, C
        code / P result): a destructible vehicle draws only its pieces (destructible-vehicles.md), and their render
        instances are built once, in the world, by 0x8B. Event 0x8B again after the attach rebuilds them through the
        contained branch of 0x630FC0 (the parent's render node, 0x630BF0 -> 0x7602A0), and after the detach in the
        world again for the flight ([ics] liftable_attach_rebuild / liftable_detach_rebuild: kind -> delays in s)."""
        if getattr(obj, "lift_spec", None) is None or not self.ic.get("destruction_reset_event", True):
            return
        if not self.w.data.record_u32(obj.world_state or _did(obj.lift_spec.get("world_state")), 0x800):
            return
        for at in (self.ic.get(key) or {}).get(obj.liftable) or ():
            self.m.later(float(at), lambda: self.w.send(f"{obj.name}: rebuild pieces, {why} (0x8b)",
                                                        M.destruction_reset(obj.eid))
                         if obj.eid in self.w.entities and not getattr(obj, "broken", False) else None)

    def _graph(self, ent, event, name):
        if self.ic.get("liftable_hit_events", True):
            self.w.graph_event(ent, event, f"{ent.name}: graph event {name} ({event:#x})")

    def _attach(self, ch, obj, on):
        """2026-10-26 (grab-arm-carry.md 2, C reader 0x57EE90): the object rides the champion's hand through the parent
        block of its own movement state ([ics] liftable_attach: mode, attach point, two bytes; {} = bundles over the
        head as before); off = parent IID 0 (detach), then no block."""
        spec = self.ic.get("liftable_attach") or {}
        if not spec:
            return
        if on:
            obj.attach_parent = (ch.eid, int(spec.get("mode", 0x10)), _did(spec.get("point", "0x100000B0")),
                                 int(spec.get("b1", 0)), int(spec.get("b2", 1)))
            self.w.update(obj, f"{obj.name} attached to {ch.name}")
        elif getattr(obj, "attach_parent", None) is not None:
            obj.attach_parent = (0,)
            self.w.update(obj, f"{obj.name} detached")
            obj.attach_parent = None

    def _attached_kind(self, obj):
        """2026-10-28 13:52 (tester: a lifted vehicle sits merged with the champion at ground level and vanishes while
        he walks; vehicles-carry-collision.md 1): the containment attach (0xB0 flag 0x04) puts the child at the parent's
        origin (the mode-0x10 block's local transform is not on the wire; the script's AttachmentOffset is), so only the
        kinds in [ics] liftable_attach_kinds ride it; the others are carried by their own bundles."""
        return bool(self.ic.get("liftable_attach")) and obj.liftable in (self.ic.get("liftable_attach_kinds") or ())

    def _hold_point(self, ch, obj):
        """Where the carried object sits: the champion's position + [ics] liftable_carry_offset[kind] = [right, forward,
        up] in the champion's frame (vehicle 0x34000161's AttachmentOffset is (0, 0, 2.5), C script default)."""
        off = (self.ic.get("liftable_carry_offset") or {}).get(obj.liftable)
        if not off:
            off = (0.0, 0.0, float(self.ic.get("liftable_carry_height", 2.1)))
        rx, fy, uz = (list(off) + [0.0, 0.0, 0.0])[:3]
        c, s = math.cos(ch.heading), math.sin(ch.heading)
        return [ch.pos[0] + fy * c + rx * s, ch.pos[1] + fy * s - rx * c, ch.pos[2] + uz]

    def _carry(self, ch, obj, force=False, lead=0.0):
        """2026-10-28 13:52 (vehicles-carry-collision.md 1.3, C server code): the carried object never gets a
        destination of its own: with the champion's it was walked by World.tick and sent as a full bundle every tick
        (with the attach block when attached), fighting the containment. Carried by bundles it gets the champion's
        heading and speed (the client dead-reckons it beside him) and a bundle only when that course changes, or every
        [ics] liftable_carry_resend s while walking; attached, none at all. lead = s the champion is about to walk this
        tick (the match layer ticks before World.tick moves him and sends his bundle)."""
        pos = self._hold_point(ch, obj)
        if lead > 0 and ch.dest is not None and getattr(ch, "speed", 0.0):
            dx, dy = ch.dest[0] - ch.pos[0], ch.dest[1] - ch.pos[1]
            d = math.hypot(dx, dy)
            step = min(d, ch.move_speed * min(lead, 0.25))
            if d > 1e-6:
                pos[0] += dx / d * step
                pos[1] += dy / d * step
        speed = float(getattr(ch, "speed", 0.0) or 0.0)
        obj.pos, obj.heading, obj.speed, obj.path = pos, ch.heading, speed, []
        obj.dest = None if self.ic.get("liftable_no_dest", True) else (list(ch.dest) if ch.dest is not None else None)
        if getattr(obj, "attach_parent", None) is not None:
            return                  # it rides the champion on the client: a plain bundle would detach it
        last = getattr(obj, "_carry_sent", None)
        now = time.time()
        turn = float(self.ic.get("liftable_carry_turn", 0.1) or 0.1)
        changed = last is None or abs(speed - last[2]) > 0.01 or abs(math.remainder(ch.heading - last[3], math.tau)) > turn
        stale = speed > 0 and now - (last[4] if last else 0.0) >= float(self.ic.get("liftable_carry_resend", 0.5) or 0.5)
        if force or changed or stale:
            obj._carry_sent = (pos[0], pos[1], speed, ch.heading, now)
            if obj.liftable in (self.ic.get("liftable_carry_snap") or ()):
                # 2026-10-29 tester report 19:55 ("the carry and walking with the vehicle are still not smooth";
                # liftable-carry-throw-press.md 2, C 0x60B5F0): a state within 2 m of the replayed point is only
                # steered by the character body's velocity, which drops the 2.5 m height over the head (as it did for
                # the flight, throw-padlock-coredeath.md 1.3); each carry state now carries a newer teleport sequence
                # so the client places it exactly ([ics] liftable_carry_snap: kinds; [] = steered, as before)
                self.w.teleport(obj)
            self.w.update(obj, f"{obj.name} carried over the head" if force else None)

    def _abort(self, ch, why):
        """End a carry whatever its state (liftable-softlock.md 5): the object, if it still exists and is not flying,
        is put down where it is and lands (no throw); _release frees the champion's carry state, speed, slot table and
        Super Strength's script."""
        obj = getattr(ch, "carrying", None)
        self.m.log(f"{ch.name}: carry of {getattr(obj, 'name', '?')} ended ({why})")
        if obj is not None and getattr(obj, "attach_parent", None) is not None:
            self._attach(ch, obj, False)
        self._release(ch)
        if obj is not None and getattr(obj, "carried_by", None) is ch:
            obj.carried_by = None
            self._toss_end(obj)
            if obj.eid in self.w.entities and obj in self.props and not getattr(obj, "flying", False):
                if self.w.nav is not None:
                    obj.pos[2] = self.w.nav.height(obj.pos[0], obj.pos[1]) or obj.pos[2]
                obj.speed, obj.dest, obj.path = 0.0, None, []
                self.w.update(obj, f"{obj.name} put down")
                self._land(ch, obj, hit=None)

    def _watch(self):
        """2026-10-30 tester report 11:23 (the Super Strength soft-lock; liftable-softlock.md 5): nothing may keep a
        champion carrying or Super Strength's slot on the throw skill ([ics] liftable_watchdog and its timeouts)."""
        if not self.ic.get("liftable_watchdog", True):
            return
        now, w = self.m.t, self.w
        for ch in list(self.carriers):
            obj = getattr(ch, "carrying", None)
            if obj is None:
                self.carriers.discard(ch)
                continue
            phase = getattr(ch, "carry_phase", None)
            age = now - float(getattr(ch, "carry_phase_at", now) or now)
            if phase != "throw" and (obj.eid not in w.entities or obj not in self.props):
                self._abort(ch, "the object is gone")
            elif not ch.alive and phase != "throw":
                self._drop(ch, obj)
            elif phase == "lift" and age > float(self.ic.get("liftable_lift_timeout", 3.0) or 1e9):
                self.m.log(f"{ch.name}: the lift of {obj.name} never got ready, ready now (liftable_lift_timeout)")
                self._toss_end(obj)
                self._carry(ch, obj, force=True)
                self._hold(ch, obj)
                if getattr(ch, "carrying", None) is obj and not getattr(ch, "carry_ready", False):
                    self._abort(ch, "the lift never got ready")
            elif phase == "throw" and age > float(self.ic.get("liftable_throw_timeout", 3.0) or 1e9):
                self._abort(ch, "the throw never ended (liftable_throw_timeout)")
            elif phase == "ready" and float(self.ic.get("liftable_carry_timeout", 0.0) or 0.0) > 0 \
                    and age > float(self.ic.get("liftable_carry_timeout")):
                if str(self.ic.get("liftable_carry_timeout_action", "throw")) == "drop":
                    self._abort(ch, "carried too long, put down (liftable_carry_timeout)")
                else:
                    self.m.log(f"{ch.name}: carried {obj.name} too long, thrown (liftable_carry_timeout)")
                    self.throw(ch, None)
        ch = w.champion
        due = getattr(ch, "carry_restore_due", None) if ch is not None else None
        if (due is not None and getattr(ch, "carrying", None) is None and getattr(ch, "carry_base_block", None) is not None
                and now > due + float(self.ic.get("liftable_restore_timeout", 2.5) or 0.0)):
            self.m.log(f"{ch.name}: slot {getattr(ch, 'carry_slot', None)} still held the throw skill, Super Strength "
                       f"back (liftable_restore_timeout)")
            ch.bundle_hold, ch.bundle_held = False, None
            self._throw_button(ch, None, False)
            ch.carry_restore_due = None

    # ---- the walk into range (liftable-throw-walk-to-range.md) ---------------------------------------------------
    @staticmethod
    def _walk_end(ch):
        """Where the champion is heading now: his path's last corner, his destination, a move held by a cast; None when
        he stands (a skill order stops him with path left over: World.tick walks only with a destination)."""
        if ch.dest is not None:
            return ch.path[-1] if ch.path else ch.dest
        return getattr(ch, "pending_move", None)

    def _walk_to_throw(self, ch, obj, point, target):
        """2026-10-30 tester report 15:30 ("if the chosen zone is out of range, the champion must walk until it is
        within reach and then throw"): a throw order beyond the range walks the carrier (his carry speed, a navmesh
        path) toward the point; _walk_step throws once it is within range ([ics] liftable_throw_walk). False when he
        cannot walk there (no path, crowd control): the caller throws at once, clamped to the range."""
        if not self.w.walk_to(ch, point):
            self.m.log(f"{ch.name}: cannot walk toward ({point[0]:.1f}, {point[1]:.1f}), throws {obj.name} from here")
            return False
        goal = self._walk_end(ch)
        if goal is None:
            return False
        ch.carry_walk = {"obj": obj, "point": tuple(point), "target": target, "goal": tuple(goal), "at": self.m.t}
        dist = math.hypot(point[0] - ch.pos[0], point[1] - ch.pos[1])
        self.m.log(f"{ch.name}: ({point[0]:.1f}, {point[1]:.1f}) is {dist:.1f} m away, beyond {obj.name}'s range "
                   f"{KINDS[obj.liftable]['range']:.1f} m: walks into range, then throws")
        return True

    def _walk_step(self, ch):
        """One match tick of a walk into range: in range -> the throw at the aimed point; another order (move, stop,
        attack, another skill: the champion no longer heads for the walk's goal) -> the walk ends, the carry goes on;
        the goal reached but still out of range (the path ends short) or [ics] liftable_throw_walk_timeout -> the
        throw toward the point, clamped to the range."""
        cw = getattr(ch, "carry_walk", None)
        if not cw:
            return
        obj = cw["obj"]
        if getattr(ch, "carrying", None) is not obj or not getattr(ch, "carry_ready", False) or not ch.alive:
            ch.carry_walk = None
            return
        point, goal = cw["point"], cw["goal"]
        if math.hypot(point[0] - ch.pos[0], point[1] - ch.pos[1]) <= KINDS[obj.liftable]["range"]:
            self.m.log(f"{ch.name}: in range of ({point[0]:.1f}, {point[1]:.1f}), throws {obj.name}")
            self.throw(ch, point, cw["target"], walked=True)
            return
        end = self._walk_end(ch)
        if ch.attack_target is not None or end is None or math.hypot(end[0] - goal[0], end[1] - goal[1]) > 0.05:
            if end is None and ch.attack_target is None and math.hypot(ch.pos[0] - goal[0], ch.pos[1] - goal[1]) < 0.75:
                self.m.log(f"{ch.name}: the path ended out of range, throws {obj.name} toward the point")
                self.throw(ch, point, cw["target"], walked=True)
                return
            ch.carry_walk = None
            self.m.log(f"{ch.name}: walk to throw {obj.name} cancelled (another order), still carrying")
            return
        if self.m.t - cw["at"] > float(self.ic.get("liftable_throw_walk_timeout", 8.0) or 1e9):
            self.m.log(f"{ch.name}: walk to throw {obj.name} too long (liftable_throw_walk_timeout), throws toward the point")
            self.throw(ch, point, cw["target"], walked=True)

    def tick(self, dt):
        self._watch()
        for ch in list(self.carriers):
            self._walk_step(ch)
        for obj in list(self.props):
            ch = getattr(obj, "carried_by", None)
            if ch is None or not getattr(ch, "carry_ready", False) or getattr(obj, "flying", False):
                continue
            if not ch.alive:
                self._drop(ch, obj)
                continue
            self._carry(ch, obj, lead=dt)
            self._spin(obj)

    def _spin(self, obj):
        """2026-10-29 tester report 2026-10-29 17:45 ("usually it has an animation spinning in the palm";
        agl-arm-meteor-vehicle-tilt.md 2, P: no rock scriptlet turns it, AGL's tables lack SuperStrength_Rubble_Active):
        a held rock turns about its vertical axis by its facing offset, one movement state every step s ([ics]
        liftable_hold_spin: kind -> [deg/s, step s]; {} = no spin as before). Attached objects are left alone."""
        spec = (self.ic.get("liftable_hold_spin") or {}).get(obj.liftable)
        if not spec or getattr(obj, "attach_parent", None) is not None:
            return
        rate, step = (list(spec) + [180.0, 0.1])[:2]
        now = time.time()
        if now - float(getattr(obj, "_spin_sent", 0.0) or 0.0) < float(step):
            return
        start = getattr(obj, "_spin_start", None)
        if start is None:
            start = obj._spin_start = now
        obj._spin_sent = now
        obj.facing_offset = math.radians(float(rate)) * (now - start)
        self.w.update(obj, None)

    def _face(self, ch, label):
        """The throw's turn toward the point. 2026-10-29 tester report of 18:31 ("picking up and throwing the vehicle
        looks as if animations were skipped"; liftable-throw-destruction.md 2, C traffic 18:33:34.340: the "throws"
        update went as a FULL champion bundle, 1432 bytes, 0.13 s before ThrowObject, in the middle of the Hold state,
        because a slot table had changed during the carry; a full bundle replaces the champion's 0x7D2 tables and drops
        what its running scriptlets hold, liftables-camps-animations.md 2.2): in delta mode the turn goes as the
        movement state alone; the changed tables follow with the slot restore after the throw clip
        ([ics] liftable_throw_face_motion_only; false = World.update, as before)."""
        w = self.w
        if (self.ic.get("liftable_throw_face_motion_only", True) and w.delta_mode()
                and getattr(ch, "client_props", None) is not None and not w._full_needed(ch)):
            msg = w.motion_state(ch)
            ch.client_motion, ch.client_motion_at = w.motion_key(ch), time.time()
            w.send(f"{label} (movement state only)", msg)
            return
        if (not w.delta_mode() and self.ic.get("liftable_throw_face_motion_bundle", True)
                and getattr(ch, "sequence", 0) > 0 and w.in_world):
            # 2026-10-30 tester report 11:23 (liftable-softlock.md 6): bundle mode too; the champion's tables changed
            # during the carry go with the slot restore after the throw clip (Liftables._release)
            w.send(f"{label} (movement state only)", w.motion_state(ch))
            return
        w.update(ch, label, force=True)

    def _throw_button(self, ch, obj, on, send=True):
        """2026-10-25 22:07 (tester: the object can be lifted but not thrown; the client never sent a second press:
        its copy of 0x34000164 waits in a ground-target mode the server does not drive): while carrying, the slot's
        skill table on the client is the sub-skill's (0x480003C9 lob / 0x480004A2 rubble: ground target, its range
        ring), name and icon kept, as icserver/finale.py's throw skill did in Tutorial 1 ([ics] liftable_throw_skills)."""
        slot = getattr(ch, "carry_slot", None)
        w = self.w
        if ch is not w.champion or slot not in (getattr(ch, "stolen", None) or {}):
            return
        if not on:
            base = getattr(ch, "carry_base_block", None)
            if base is not None:
                ch.stolen[slot] = base
                ch.carry_base_block = None
                if send:
                    w.refresh_champion(f"slot {slot}: Super Strength again", force=True)
            return
        did = _did((self.ic.get("liftable_throw_skills") or {}).get(obj.liftable))
        block = w.data.stolen_power(did)[0] if did else None
        if not block:
            return
        base = ch.stolen[slot]
        if getattr(ch, "carry_base_block", None) is not None and self.ic.get("liftable_keep_base_block", True):
            # 2026-10-30 tester report 11:23 (liftable-softlock.md 3): the previous carry's restore is still pending
            # (liftable_slot_restore_delay): the slot holds the throw table, the real one is the kept base
            base = ch.carry_base_block
        keep = {k: (k, kind, v) for k, kind, v in base if k in (0x100001C0, 0x10000302)}
        if self.ic.get("liftable_throw_far_order", True):
            # 2026-10-30 tester report 15:30 (liftable-throw-walk-to-range.md 1, C 0xa25d80 / 0x861830 / 0x85ee30: the
            # client reads skill bool 0x100006D5 from this slot table and with it refuses a point beyond the range +
            # 0.5 m, Skill_InvalidTarget, no order): 0 here, so the far point reaches the server, which walks into range
            keep[RANGE_REFUSE] = (RANGE_REFUSE, KIND_BOOL, 0)
        ch.carry_base_block = base
        ch.stolen[slot] = [keep.get(k, (k, kind, v)) for k, kind, v in block]
        if send:
            w.refresh_champion(f"slot {slot}: throw skill {did:#x} while carrying", force=True)

    def _release(self, ch):
        obj = ch.carrying
        self._indicator(ch, False)
        ch.carrying, ch.carry_ready = None, False
        ch.carry_phase, ch.carry_phase_at = None, self.m.t
        ch.carry_queued_throw, ch.carry_indicator_pending = None, None
        ch.carry_aim, ch.carry_walk = None, None
        self.carriers.discard(ch)
        delay = float(self.ic.get("liftable_slot_restore_delay", 0.0) or 0.0) if ch.alive else 0.0
        ch.carry_restore_due = self.m.t + delay

        end = getattr(ch, "carry_cooldown_end", None) if ch is self.w.champion else None
        ch.carry_cooldown_end = None
        slot = getattr(ch, "carry_slot", None)

        def restore():
            # 2026-10-28 12:56 (liftables-camps-animations.md 2): the Super Strength slot table and any champion bundle
            # held during the carry go in one bundle after the throw clip ([ics] liftable_slot_restore_delay), then
            # the slot's cooldown (a full bundle carries the slot table again)
            if getattr(ch, "carrying", None) is not None:
                return
            held = getattr(ch, "bundle_held", None)
            ch.bundle_hold, ch.bundle_held = False, None
            if obj is not None and getattr(ch, "carry_base_block", None) is not None:
                self._throw_button(ch, obj, False)
            elif held and ch is self.w.champion:
                self.w.refresh_champion(f"{held} (held during the carry)")
            if end is not None and end > time.time():
                self.w.send(f"slot {slot} cooldown {end - time.time():.1f} s after the throw (0x20f8)",
                            M.skill_cooldown(slot, end))
        if delay > 0:
            self.m.later(delay, restore)
        else:
            restore()
        if hasattr(ch, "carry_saved_speed"):
            ch.move_speed = ch.carry_saved_speed
            del ch.carry_saved_speed
        inst = getattr(ch, "carry_inst", None)
        ch.carry_inst = None
        if inst is not None and not inst.removed:
            inst.post(EVENT_END, 0.0)

    def _drop(self, ch, obj):
        """The carrier died: the object explodes / falls where it is (0x34000161 S3, interrupted carry)."""
        self._attach(ch, obj, False)
        self._release(ch)
        obj.carried_by = None
        obj.pos[2] = self.w.nav.height(obj.pos[0], obj.pos[1]) or obj.pos[2] if self.w.nav is not None else obj.pos[2]
        obj.speed, obj.dest = 0.0, None
        self.w.update(obj, f"{obj.name} dropped")
        self._land(ch, obj, hit=None)

    def throw(self, ch, point, target=None, walked=False):
        w = self.w
        obj = getattr(ch, "carrying", None)
        if obj is None:
            return
        ch.carry_walk = None        # a new throw order replaces a walk into range
        if not getattr(ch, "carry_ready", False):
            if self.ic.get("liftable_throw_early_queue", True) and not getattr(obj, "flying", False):
                # 2026-10-29 tester report 21:10 (C traffic 21:10:08.328: a throw order 0.35 s into the vehicle's lift
                # was dropped, the client counted it as cast and the next press sent no order, so the throw came only
                # from liftable_throw_on_press 9 s later): an order during the lift is kept and thrown when the carry
                # is ready ([ics] liftable_throw_early_queue; false = dropped, as before)
                ch.carry_queued_throw = (point, target)
                self.m.log(f"{ch.name}: still lifting {obj.name}, the throw waits for the carry")
                return
            self.m.log(f"{ch.name}: still lifting {obj.name}")
            return
        ch.carry_queued_throw = None
        ch.carry_press_at, ch.carry_unanswered = None, 0
        if obj.eid not in w.entities and self.ic.get("liftable_watchdog", True):
            # 2026-10-30 tester report 11:23 (liftable-softlock.md 2): nothing left to throw: the carry just ends
            self._abort(ch, "the object is gone")
            return
        info = KINDS[obj.liftable]
        if point is None and target is not None:
            point = tuple(target.pos)
        if point is not None:
            ch.carry_aim = tuple(point)
            if (not walked and obj.liftable in (self.ic.get("liftable_throw_walk") or ())
                    and math.hypot(point[0] - ch.pos[0], point[1] - ch.pos[1]) > info["range"]
                    and self._walk_to_throw(ch, obj, point, target)):
                return
        ch.carry_phase, ch.carry_phase_at = "throw", self.m.t
        if point is None:
            point = (ch.pos[0] + math.cos(ch.heading) * 6.0, ch.pos[1] + math.sin(ch.heading) * 6.0, ch.pos[2])
        dx, dy = point[0] - ch.pos[0], point[1] - ch.pos[1]
        dist = math.hypot(dx, dy) or 1e-6
        rng = info["range"]
        if dist > rng or not info["lob"]:
            # a rock flies straight to the end of its range; a vehicle lands at the point (at most its range away)
            k = rng / dist if (dist > rng or not info["lob"]) else 1.0
            point = (ch.pos[0] + dx * k, ch.pos[1] + dy * k, point[2] if len(point) > 2 else ch.pos[2])
            dist = math.hypot(point[0] - ch.pos[0], point[1] - ch.pos[1])
        ch.heading = math.atan2(dy, dx)
        ch.dest, ch.path, ch.speed = None, [], 0.0
        self._face(ch, f"{ch.name} throws {obj.name}")
        if self.ic.get("liftable_throw_turn_object", True) and getattr(obj, "attach_parent", None) is None:
            # 2026-10-30 tester report 12:05 ("the throw also looks weird"; liftable-lift-throw-wreck.md 1.3, C server
            # code): the champion stopped and turned toward the point here, while the carried object kept its last carry
            # state (the old heading and, when he threw while walking, his walking speed: the client dead-reckoned it
            # away from his hands) until the first flight state, face_lead + the launch frame (0.33 s) later. Now it
            # turns and stops with him, on the hold point ([ics] liftable_throw_turn_object; false = as before)
            self._carry(ch, obj, force=True)
        self.m.log(f"{ch.name} throws {obj.name} at ({point[0]:.1f}, {point[1]:.1f})")
        self._indicator(ch, False)
        sig = self.ic.get("super_strength_cast_signals") or {}
        # 2026-10-29 tester report 2026-10-29 14:40 (agl-qer-lift.md 4, C traffic 14:21:39.093 / .096): the throw key
        # and its release / end wait [ics] liftable_face_lead s after the "throws" facing bundle, so the turn is applied
        # before the throw clip starts; the carry stops at once (no second throw, no carry bundles meanwhile)
        lead = max(0.0, float(self.ic.get("liftable_face_lead", 0.0) or 0.0))
        ch.carry_ready = False

        def keys():
            self._key(ch, info["throw"], f"{ch.name}: throw {obj.name} (0x8d)", target=obj)
            if info["on_object"]:
                self._key(obj, info["throw"], f"{obj.name}: SuperStrength_ThrowObject (0x8d)", target=ch)
        if lead > 0:
            self.m.later(lead, keys)
        else:
            keys()
        windup = lead + float(sig.get(obj.liftable + "_release", info["release"]))
        end = lead + float(sig.get(obj.liftable + "_end", info["end"]))
        obj.flying = True

        def done():
            if getattr(ch, "carrying", None) is not obj:
                return              # already released (the watchdog's throw timeout)
            self._graph(ch, HIT_ON, "CbtState_EnableHit")
            if info["locomotion"]:
                self.m.later(float(sig.get("locomotion_after", 0.6)),
                             lambda: self._key(ch, LOCOMOTION_KEY, f"{ch.name}: back to locomotion (0x8d)"))
            self._release(ch)

        def release():
            # the launch frame: the object leaves the hands where it was held, 0.5 m forward
            hp = self._hold_point(ch, obj)
            obj.pos = [hp[0] + math.cos(ch.heading) * 0.5, hp[1] + math.sin(ch.heading) * 0.5, hp[2]]
            obj.dest, obj.path = None, []
            attached = getattr(obj, "attach_parent", None) is not None
            self._attach(ch, obj, False)
            if attached or not self.ic.get("liftable_detach_rebuild_attached_only", True):
                # 2026-10-29 tester report of 18:31 (liftable-throw-destruction.md 3, C 0x631050: 0x8B clears the
                # pieces and builds them again): the rebuild moves the pieces out of the champion's containment; a
                # vehicle carried by its own states (liftable_attach_kinds []) was never contained, and the rebuild
                # only re-made its pieces in mid-air at the launch frame ([ics] liftable_detach_rebuild_attached_only;
                # false = always, as before)
                self._rebuild(obj, "liftable_detach_rebuild", "detached")
            self._fly(ch, obj, point, dist, info)
        self.m.later(windup, release)
        self.m.later(max(end, windup + 0.01), done)

    def _fly(self, ch, obj, point, dist, info):
        w = self.w
        if obj.eid not in w.entities:
            return
        obj.carried_by = None
        obj.team = getattr(ch, "team", 0)
        for key in info["thrown"]:
            self._key(obj, key, f"{obj.name}: thrown (0x8d)")
        # 2026-10-29 12:45 (tester report 2026-10-29 12:45: the throw looks as if thrown straight; throw-truck-padlock.md
        # 2, C script 0x34000161 S2 + client replay, G frames): the vehicle flew 0.4 s in 8 states and exploded at the
        # last one, while the client still drew it ~0.1 s behind, near hand height: the lob was never seen. Now
        # [ics] liftable_throw_speed (m/s, 0x34000161 MissileVelocity 15.0), liftable_throw_min_seconds (the shortest
        # flight), a state every liftable_throw_step_seconds, a ballistic curve (liftable_throw_arc m over the line) and
        # the landing liftable_land_delay s after the last state (the client's replay lag)
        speed = float((self.ic.get("liftable_throw_speed") or {}).get(obj.liftable, info["speed"]) or info["speed"])
        flight = max(0.3, float((self.ic.get("liftable_throw_min_seconds") or {}).get(obj.liftable, 0.0) or 0.0),
                     dist / speed)
        steps = max(2, int(self.ic.get("liftable_throw_steps", 8) or 8))
        step_s = float(self.ic.get("liftable_throw_step_seconds", 0.0) or 0.0)
        if step_s > 0:
            steps = max(steps, int(math.ceil(flight / step_s)))
        land_delay = float((self.ic.get("liftable_land_delay") or {}).get(obj.liftable, 0.0) or 0.0)
        sx, sy, sz = obj.pos
        gz = (w.nav.height(point[0], point[1]) if w.nav is not None else None) or self.m.map["z"]
        arc = float(self.ic.get("liftable_throw_arc", 3.0)) if info["lob"] else 0.0
        heading = math.atan2(point[1] - sy, point[0] - sx)
        cw = CastWorld(w, ch, None)
        # 2026-10-29 tester report 2026-10-29 17:45 ("the vehicle falls lying flat, not with the front tilting down to hit
        # and explode"; agl-arm-meteor-vehicle-tilt.md 3, C motion bit 0x400 of the 0xB0 block): each flight state
        # carries a facing pitch along the curve (nose up at the launch, down at the end) and the last one the landing
        # pitch ([ics] liftable_throw_pitch: kind -> {sign, max, land} in rad; {} = flat as before)
        tilt = (self.ic.get("liftable_throw_pitch") or {}).get(obj.liftable)
        if obj.liftable in (self.ic.get("liftable_throw_velocity") or ()):
            self._fly_timed(ch, obj, info, cw, (sx, sy, sz), point, gz, dist, flight, arc, heading, tilt, land_delay)
            return
        for i in range(1, steps + 1):
            f = i / steps
            p = [sx + (point[0] - sx) * f, sy + (point[1] - sy) * f,
                 sz + (gz - sz) * f + arc * 4.0 * f * (1.0 - f)]
            pitch = None
            if tilt:
                slope = math.atan2((gz - sz) + arc * 4.0 * (1.0 - 2.0 * f), max(dist, 0.1))
                cap = float(tilt.get("max", 1.2))
                pitch = max(-cap, min(cap, slope))
                if i == steps and tilt.get("land") is not None:
                    pitch = float(tilt["land"])
                pitch *= float(tilt.get("sign", 1.0))

            def step(p=p, last=(i == steps), pitch=pitch):
                if obj.eid not in w.entities or not getattr(obj, "flying", False):
                    return
                obj.pos, obj.heading = p, heading
                if pitch is not None:
                    obj.pitch = pitch
                spin = (self.ic.get("liftable_hold_spin") or {}).get(obj.liftable)
                if spin and getattr(obj, "_spin_start", None) is not None:
                    # the held rock keeps turning in its flight (each flight state is sent anyway)
                    obj.facing_offset = math.radians(float(list(spin)[0])) * (time.time() - obj._spin_start)
                obj.speed, obj.dest = (0.0, None) if last else (dist / flight, [point[0], point[1], gz])
                if self.ic.get("liftable_no_dest", True):
                    obj.dest = None         # the steps place it; World.tick must not walk it as well
                if obj.liftable in (self.ic.get("liftable_throw_snap") or ()):
                    # tester report 2026-10-29 15:30 (throw-padlock-coredeath.md 1.3, C 0x60B5F0): a newer teleport
                    # sequence places each state exactly (a state within 2 m is only steered) ([ics] liftable_throw_snap)
                    w.teleport(obj)
                w.update(obj, None)
                if not info["lob"]:
                    hit = self._targets(cw, ch, obj, info["radius"])
                    if hit:
                        obj.flying = False
                        self._land(ch, obj, hit=hit[:1])
                        return
                if last:
                    obj.flying = False
                    if land_delay > 0:
                        self.m.later(land_delay, lambda: self._land(ch, obj, hit=None) if obj.eid in w.entities else None)
                    else:
                        self._land(ch, obj, hit=None)
            self.m.later(flight * f, step)

    def _fly_timed(self, ch, obj, info, cw, start, point, gz, dist, flight, arc, heading, tilt, land_delay):
        """2026-10-29 tester report 21:10 ("the throw also looks slow, like frame by frame"; liftable-aura-lift-throw-
        break.md 3, C client replay 0x552130 / 0x57DA90, C traffic 21:08:26.713-27.747): the flight went as states
        precomputed for 0.05 s steps but sent on the 30 Hz server tick (33 / 66 ms apart, each stamped with its send
        time), every one a teleport snap with only the horizontal speed, so the client drew the lob as a stair of jumps.
        LaunchLobbedMissile has no client half (C, node 0x10000154's execute is the empty 0xab4d80): the original server
        sent the arc as states. Now each state is the curve at its own send time (f = elapsed / flight, so the position
        matches the state's time stamp), with the curve's 3D velocity (heading, speed = |v|, motion pitch bit 0x40 =
        the velocity's pitch, C 0x57DA90), so the client dead-reckons along the tangent between states, one state per
        [ics] liftable_throw_step_seconds (0.033 = every tick). [ics] liftable_throw_velocity: kinds ([] = the fixed
        steps above, as before)."""
        w = self.w
        sx, sy, sz = start
        step_s = max(0.02, float(self.ic.get("liftable_throw_step_seconds", 0.033) or 0.033))
        t0 = self.m.t                # match time: m.later's clock (the wall clock in a live match)
        snap = obj.liftable in (self.ic.get("liftable_throw_snap") or ())
        state = {"last": False}

        def curve(f):
            f = max(0.0, min(1.0, f))
            p = [sx + (point[0] - sx) * f, sy + (point[1] - sy) * f,
                 sz + (gz - sz) * f + arc * 4.0 * f * (1.0 - f)]
            vh = dist / flight
            vz = ((gz - sz) + arc * 4.0 * (1.0 - 2.0 * f)) / flight
            return p, vh, vz

        def step():
            if state["last"] or obj.eid not in w.entities or not getattr(obj, "flying", False):
                return
            f = (self.m.t - t0) / flight
            last = f >= 1.0 - 1e-6
            p, vh, vz = curve(f)
            obj.pos, obj.heading = p, heading
            if tilt:
                cap = float(tilt.get("max", 1.2))
                pitch = max(-cap, min(cap, math.atan2(vz * flight, max(dist, 0.1))))
                if last and tilt.get("land") is not None:
                    pitch = float(tilt["land"])
                obj.pitch = pitch * float(tilt.get("sign", 1.0))
            spin = (self.ic.get("liftable_hold_spin") or {}).get(obj.liftable)
            if spin and getattr(obj, "_spin_start", None) is not None:
                obj.facing_offset = math.radians(float(list(spin)[0])) * (time.time() - obj._spin_start)
            if last:
                obj.speed, obj.vel_pitch = 0.0, None
            else:
                obj.speed, obj.vel_pitch = math.hypot(vh, vz), math.atan2(vz, vh)
            obj.dest, obj.path = None, []
            if snap:
                w.teleport(obj)
            w.update(obj, None)
            if not info["lob"]:
                hit = self._targets(cw, ch, obj, info["radius"])
                if hit:
                    obj.flying, obj.vel_pitch = False, None
                    state["last"] = True
                    self._land(ch, obj, hit=hit[:1])
                    return
            if last:
                state["last"] = True
                obj.flying = False
                if land_delay > 0:
                    self.m.later(land_delay, lambda: self._land(ch, obj, hit=None) if obj.eid in w.entities else None)
                else:
                    self._land(ch, obj, hit=None)
                return
            nxt = min(step_s, max(0.0, t0 + flight - self.m.t))
            self.m.later(nxt, step)
        step()

    def _targets(self, cw, ch, obj, radius):
        w = self.w
        return sorted((e for e in list(w.entities.values()) + [w.champion]
                       if e is not None and e is not obj and e is not ch and e.alive and e.health is not None
                       and math.hypot(e.pos[0] - obj.pos[0], e.pos[1] - obj.pos[1]) <= radius
                       and cw.collides(ch, e)), key=lambda e: e.distance_to(obj))

    def _impulse(self, obj):
        """0x3400015F's DestructionImpulse (sphere, its DestructionRange / DestructionMagnitude, level 3) on the landed
        object, as 0x8A to it, now and [ics] liftable_land_impulse "again" s later (its S4 before DestroyEntity)."""
        spec = (self.ic.get("liftable_land_impulse") or {}).get(obj.liftable)
        if not spec:
            return
        w = self.w

        def send():
            if obj.eid not in w.entities:
                return
            pos = w.wire_position(obj)
            w.send(f"{obj.name}: destruction impulse (0x8a)",
                   M.destruction_sphere(obj.eid, pos, float(spec.get("radius", 4.0)), float(spec.get("magnitude", 10.0)),
                                        int(spec.get("level", 3)), 0, 0))
        send()
        again = float(spec.get("again", 0.0) or 0.0)
        if again > 0:
            self.m.later(again, send)

    def _land_rebuild(self, obj):
        """2026-10-29 tester report of 18:31 ("the vehicle's destruction animation is not generated";
        liftable-throw-destruction.md 3, C 0x632370 / 0x631C50 / 0x631FA0 / 0x630FC0): the 0x8A impulse breaks the
        pieces its sphere query finds around the landing point, and a mobile destructible's piece bodies are made
        (0x62DBA0) at the entity's frame when 0x8B builds them: the last build was at the launch (or over the head), so
        the pieces are rebuilt on the landing frame first ([ics] liftable_land_rebuild: kinds; [] = none, as before).
        The impulse follows liftable_land_impulse "after_rebuild" s later."""
        w = self.w
        if obj.eid not in w.entities or not self.ic.get("destruction_reset_event", True):
            return False
        if not w.data.record_u32(obj.world_state or _did(obj.lift_spec.get("world_state")), 0x800):
            return False
        w.send(f"{obj.name}: rebuild pieces at the landing (0x8b)", M.destruction_reset(obj.eid))
        return True

    def _destroy_action(self, obj):
        """2026-10-29 tester report of 18:31 (liftable-throw-destruction.md 4, C script 0x3400015F S4 + script-nodes-
        names.md 0x10000010): S4, DestructionDelayDuration (0.15 s) after the landing, ends with DestroyEntity(SELF)[10.5,
        1], whose client execute plays _HFSM_DestroyEntityAction and _HFSM_DestroyEntityAction_Optional on the object
        (the vehicles' Super Strength table 0x1D00034B holds the Optional one) before the removal 10.5 s later; ics
        played neither ([ics] liftable_land_destroy_after: kind -> s after the landing; liftable_destroy_actions: the
        keys, a key the object's tables lack is not sent; {} = none, as before)."""
        after = (self.ic.get("liftable_land_destroy_after") or {}).get(obj.liftable)
        if after is None:
            return
        w = self.w

        def go():
            if obj.eid not in w.entities:
                return
            for name in self.ic.get("liftable_destroy_actions") or ():
                w.scriptlet(obj, name, f"{obj.name}: {name} (0x8d, DestroyEntity)")
        if float(after) > 0:
            self.m.later(float(after), go)
        else:
            go()

    def _break_keys(self, obj):
        """2026-10-29 tester report 19:55 ("on impact the vehicle does not do its exploding animation", the third report
        since fase3-ij; liftable-carry-throw-press.md 3): the landing's 0x8B / Vfx_OnExplode / 0x8A / DestroyEntity keys
        all went in order (C traffic 19:49:48.879-49.109) and nothing showed. The client plays its pieces' break keys
        (the truck's / SUV's table 0x1D000612 / 0x1D0001FD: Destructible_OnBreak_*_T1, Destructible_OnCompletelyDestroyed)
        only when 0x8A's sphere query finds and breaks a piece (0x632370 -> 0x631C50 -> 0x631FA0 -> 0x62BC00, C), which
        needs the entity's and the pieces' client positions on a valid cell (0x631940 / 0x631B00 checks, C) and was never
        seen to happen (P). Those keys now go to the landed object [ics] liftable_land_break_after s after the landing,
        whatever the impulse did ([ics] liftable_land_break_keys: kind -> names, a name its tables lack is not sent;
        {} = none, as before). P: a doubled effect if the impulse did break the pieces."""
        names = (self.ic.get("liftable_land_break_keys") or {}).get(obj.liftable)
        if not names:
            return
        w = self.w

        def go():
            if obj.eid not in w.entities:
                return
            for name in names:
                w.scriptlet(obj, name, f"{obj.name}: {name} (0x8d, break)")
        after = float(self.ic.get("liftable_land_break_after", 0.2) or 0.0)
        if after > 0:
            self.m.later(after, go)
        else:
            go()

    def _explode_late(self, obj):
        """2026-10-29 tester report 21:10 ("when the vehicles impact they disappear and you hear the explosion";
        liftable-aura-lift-throw-break.md 4, C 0x530FA0 / 0x65C7D0 / 0x62ED00 / 0x62EBF0): the vehicles' Vfx_OnExplode
        (table 0x1D00034B) is an action 0x29 over the destruction component's pieces (0x4F5C20(0x801), group field
        0x10000002) with a child 0x28 that calls CDestructionComponent vfunc +0x4C = 0x62ED00 -> 0x62EBF0 on each: the
        piece's render instance (+0x15C) and physics body (+0x188) are destroyed and it leaves the active list, and a
        destructible vehicle is drawn only through its active pieces (destructible-vehicles.md). So the landing's
        Vfx_OnExplode made the vehicle vanish at once, and took the piece bodies away before the 0x8A sphere query looked
        for them (diag 21:08:27 / 21:10:18: piece bodies 0, entities 0, both impulses). It is no longer a landing key
        ([ics] liftable_land_scriptlets); [ics] liftable_land_explode: kind -> s after the landing to send it anyway (after
        the impulse; {} = never).
        2026-10-30 tester report 12:05 ("the explosion sounds, then the wreck stays a few seconds"; liftable-lift-throw-
        wreck.md 2): vehicle 0.75 s, after the break keys (+0.2 s) played on the intact pieces; the wreck goes with the
        explosion and the client runs the record's "all pieces gone" key itself (0x62EBF0, C; P OnCompletelyDestroyed)."""
        after = (self.ic.get("liftable_land_explode") or {}).get(obj.liftable)
        if after is None:
            return
        w = self.w
        self.m.later(float(after), lambda: w.scriptlet(obj, "Vfx_OnExplode", f"{obj.name}: Vfx_OnExplode (0x8d, late)")
                     if obj.eid in w.entities else None)

    def _land(self, ch, obj, hit):
        w = self.w
        info = KINDS[obj.liftable]
        cw = CastWorld(w, ch, None)
        if hit is None and info["lob"]:
            hit = self._targets(cw, ch, obj, info["radius"])
        rank = max(1, int((getattr(ch, "ranks", {}) or {}).get(getattr(ch, "carry_slot", None) or 8, 1) or 1))
        amount = info["damage"] + info["per_rank"] * (rank - 1)
        for e in hit or ():
            deal_damage(cw, ch, e, amount, dtype=1)
            if info["status"] and e.alive:
                R.apply_status(cw, ch, e, info["status"], {"EffectDuration": info["seconds"]})
        self.m.log(f"{obj.name} lands: " + (", ".join(e.name for e in hit) if hit else "nothing hit"))
        obj.broken = True
        land_keys = (self.ic.get("liftable_land_scriptlets") or {}).get(obj.liftable)
        if info["lob"] and land_keys:
            # tester report 2026-10-29 15:30 (the vehicle does not explode; throw-padlock-coredeath.md 1.4, C script
            # 0x3400015F S2 / S4): the original's landing keys and its DestructionImpulse (0x8A to the vehicle), now and
            # DestructionDelayDuration later ([ics] liftable_land_scriptlets / liftable_land_impulse)
            rebuilt = obj.liftable in (self.ic.get("liftable_land_rebuild") or ()) and self._land_rebuild(obj)
            for name in land_keys:
                self.w.scriptlet(obj, name, f"{obj.name}: {name} (0x8d)")
            spec = (self.ic.get("liftable_land_impulse") or {}).get(obj.liftable) or {}
            lag = float(spec.get("after_rebuild", 0.0) or 0.0) if rebuilt else 0.0
            if lag > 0:
                self.m.later(lag, lambda: self._impulse(obj))
            else:
                self._impulse(obj)
            self._destroy_action(obj)
            self._break_keys(obj)
            self._explode_late(obj)
        elif info["lob"]:
            self._key(obj, EXPLODE_KEY, f"{obj.name}: Vfx_OnExplode (0x8d)")
        elif hit:
            self._key(obj, COLLISION_KEY, f"{obj.name}: Vfx_OnCollision (0x8d)")
        else:
            self._key(obj, FADE_OUT_KEY, f"{obj.name}: Vfx_Fade_Out (0x8d)")
        self.m.later(info["remove_after"] if (info["lob"] or hit) else 0.6, lambda: self._gone(obj))
