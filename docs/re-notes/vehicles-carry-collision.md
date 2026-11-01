# Carried vehicles and parked-vehicle collision (2026-10-28)

Trigger: tester 13:38-13:52 (Crime Alley v AI, Atomic Green Lantern; `logs/server.log`, `logs/traffic.log`):
(1) the vehicles have no collision (champions and minions walk through them; in the original they block);
(2) a vehicle lifted with Super Strength sits merged with / around the champion's body, centred on him at ground
level, instead of held over his head; (3) while the champion walks the carried vehicle disappears, when he stops it
shows again. Sources: the client exe (Ghidra decompilation in `re-work/decomp`, VA, image base 0x400000; vtables read
from the PE), the vehicle / rock carry scripts (`ics.script_model` + `ics.script_runtime` defaults, nothing copied),
the logs, the server code. Tags: **C** confirmed (code / data / log read), **P** probable, **O** open. Builds on
liftables-camps-animations.md 1, grab-arm-carry.md 2.4, destructible-vehicles.md, client-movement.md 0.

## 1. The carried vehicle

### 1.1 What the original does (C, script 0x34000161)

S7 (toss): `LaunchLobbedMissile(object -> the champion's position + MissileOffset)` with TossDuration 0.3 s: the
vehicle flies onto the champion by ordinary movement; S8 catch (CatchDuration 0.35 s); S9:
`AttachEntity(SELF, object, $AttachmentOffset, $AttachHandle) [0x100000B0 0 1 1]` with **AttachmentOffset = (0, 0,
2.5)** (the script's server-only default block, read by `Instance._defaults`). The rock script 0x34000177 attaches with
**(0, 1.4, 1.4)**. So the original keeps the vehicle 2.5 m straight above the champion's attach point.

### 1.2 What the client's containment attach can carry (C)

- 0xB0 flag 0x04 -> `0x6113E0` -> `0x634C70` -> `0x58A220` -> `0x55F930(child, mode, extra)`. The mode-0x10 extra
  block read from the wire (`0x55E290`) is **u32 attach point, u8, bool** only; `0x55E6B0` copies it into a 0x30-byte
  object whose words +0x10..+0x28 (seven floats = a position + quaternion, the 0x1C-byte local transform) are never
  filled from the wire. No other reader of the record's extra block positions the child (`0x55E0A0`, its only caller
  `0x677910`, is a script query that lists children attached at a point with u8 == 1).
- So the server cannot send AttachEntity's offset through the containment: the child sits at the parent with an
  identity local transform -> **at the champion's feet, centred on him** (C reader, P effect = the tester's report).
- Notifications: `0x560010` (containment vt+0x60, add) / `0x55E5E0` (vt+0x68, change) call `0x55E4E0` -> `0x55DBF0`,
  which tells the child's listener components (case 2 = attached at a point, mode 0x10). Children are walked again on
  every parent frame change: `0x577EE0` / `0x577F30` (location component vt+0x9C / +0xA4, vtable `0x15B7968`) ->
  `0x575B90` -> each child's component +0x38 vt+0x50.

### 1.3 Why it vanished while walking (C server code, P client effect)

`Liftables._carry` copied the champion's destination into the carried object (`obj.dest = ch.dest`). `World.tick`
moves every entity that has a destination, so while the champion walked the vehicle was **walked by the server on its
own** (its prop move speed 4.5 m/s, its z set to the destination's ground height on arrival) and appeared in
`changed`: `Session` sent it a **full bundle every tick** (unlabelled, so not in traffic.log). Each of those bundles
carried the attach block again plus the vehicle's own world position. A destructible draws only its pieces; its
render variant's frame-changed method (`0x15C9534` = `0x61F500` -> `0x61EC50` -> `0x62C730`) moves every piece body to
the new entity frame (C), while the pieces' render instances were built under the champion's render node by the 0x8B
sent after the attach (`0x630FC0` contained branch). P: the world frame applied under the parent puts them far off
or re-registers them every tick; when the champion stopped, the bundles stopped and the containment walk (`0x575B90`)
put the child back on the champion, so it showed again, merged with him. The rocks (attached too) got the same
per-tick bundles.

### 1.4 Fix

- **No containment for vehicles** (`[ics] liftable_attach_kinds` = ["rock"]): the vehicle is carried by its own
  movement bundles (as Tutorial 1's car and the original's toss), at **champion + `liftable_carry_offset`**
  (vehicle [0, 0, 2.5] = the script's AttachmentOffset; [right, forward, up] in the champion's frame), with the
  champion's heading and speed, so the client dead-reckons it beside him (client-movement.md 1.2: velocity from
  heading / speed). Moving a destructible by bundles moves its pieces (render vt+0x64 above, C path).
- **No destination of its own** for a carried or thrown object (`liftable_no_dest`): `World.tick` no longer walks it,
  so there is no per-tick bundle; an attached rock gets none at all while held.
- A carry bundle goes when the champion's course changes (turn > `liftable_carry_turn` 0.1 rad, speed change) and
  every `liftable_carry_resend` 0.5 s while walking (was: every 0.3 m, plus the per-tick ones).
- The 0x8B piece rebuild after the vehicle is put over the head stays (`liftable_attach_rebuild`), as after the
  detach; the throw starts from the held point (+0.5 m forward).
- Revert: `liftable_attach_kinds = ["rock", "vehicle"]`, `liftable_no_dest = false`.

O: the rock is still attached (no report); its script's offset (0, 1.4, 1.4) cannot reach the client either, so it
probably sits at the champion's origin too. If so: `liftable_attach_kinds = []` and `liftable_carry_offset.rock =
[0, 1.4, 1.4]` (P: forward = local y).

## 2. Parked-vehicle collision

- The server is authoritative for every character's movement, the local champion included; the client has no
  movement prediction (client-movement.md 0, C). So collision is a server pathing matter: nothing on the client
  stops a champion walking through a prop, and no property makes the client collide its own champion.
- The vehicles are not in the navmesh (C: they are server-spawned, liftable_props_by_map). `World.set_blocking` only
  knew the Tutorial's street vehicle and the gates (`prop_blockers`).
- Fix: `Liftables._block` makes each parked vehicle's footprint unwalkable on the match's navmesh copy
  (`NavGrid.block`, key ("liftable", eid)) at spawn / respawn, and walkable again when it is lifted, consumed or gone.
  Every server path goes round it: the champion's `walk_to`, the bots', the minions' lane legs (`units.py`: legs that
  are not `line_clear` are pathed). Sizes per world state in `[ics] liftable_blockers` ([half length, half width]
  along the vehicle's heading: the SUV's yaw 245 = heading -25 deg = its long axis tilted down to the east, as the
  frames show), + `liftable_blocker_margin` 0.35 m (a walker's radius). Sizes are **G** from the frames.
- O: units chasing a target (`ent.follow`) and dashes / knockbacks move in straight lines and can still cross a
  vehicle.

## 3. Confidence

| Issue | Cause | Fix (key) | Confidence |
|---|---|---|---|
| Vehicle merged at the champion's feet | containment child at the parent's origin; the 0x1C local transform is not on the wire, AttachmentOffset (0, 0, 2.5) is server-side | carried by bundles at +2.5 m (`liftable_attach_kinds`, `liftable_carry_offset`) | C reader / script, P effect |
| Vehicle vanishes while walking | the carried object got the champion's destination: walked by World.tick, a full bundle (with the attach block) every tick fighting the containment | `liftable_no_dest`, `liftable_carry_resend`, `liftable_carry_turn` | C server code, P client effect |
| Walk through parked vehicles | not in the navmesh, no server obstacle; client has no prediction | navmesh footprint per vehicle (`liftable_blockers`, `liftable_blocker_margin`) | C (paths), G sizes |
