# Vehicle lift animation and the SUV against the wall (2026-10-28)

Trigger: tester report 2026-10-28 15:00 (match 14:39-15:00, Crime Alley v AI, Atomic Green Lantern vs bot Atomic Wonder
Woman): (1) "without turning that vehicle, just move it a little closer to the wall" (our frames 43 / 45: a strip of
ground between the SUV and the raised wall north of it; the original, frames 35 / 37: the SUV touches it); (2) "the
vehicle lift animation does not play whole: it starts lifting, then cuts to already holding it". Sources:
`logs/server.log` + `logs/traffic.log` (lifts 14:41:43 vehicle 6 = truck, 14:47:45 vehicle 5 = SUV), the Crime Alley
navmesh (map pack `0xA0C112BA`, three agent blobs), the vehicles' `.entity` records, AGL's behaviour graph (pack
`0xA0000150`, `data/skill_graphs.json` + the raw clip generators / transition effects read with `tools/skill_graphs.py`'s
reader), the scripts `0x34000161` / `0x34000162` / `0x34000164` (`ics.script_model`, defaults via
`script_runtime.Instance._defaults` layout), the shared champion scriptlet table `0x1D0000EF` (pack `0xA00000DF`), the
Ghidra decompilation (`re-work/decomp`, VA, base 0x400000) and the PE for vtables, `ics/graph.py` (the server's copy of
the graph) driven offline with both timelines. Throw-away scripts in the session scratchpad; nothing of the game copied.
Tags: **C** confirmed (data / code / log bytes), **P** probable, **G** guess, **O** open. Builds on
`vehicles-carry-collision.md`, `liftables-camps-animations.md`, `grab-arm-carry.md` 2, `crime-alley-props.md` A.3,
`destructible-vehicles.md`, `client-movement.md`, `client-scriptlets-graphs.md`, `skill-execution-model.md`.

## 0. Short answer

- **SUV**: the wall north of it runs at -23.96 deg (the SUV's long axis is at -25 deg, so they are parallel within 1 deg).
  Its long side is **0.54 / 0.59 / 0.64 m** (rear / middle / front) from the wall today. Moving the SUV
  **0.33 m along the wall normal (0.406, 0.914)**, from (102.3, 93.6) to **(102.43, 93.90)**, with the same yaw 245,
  leaves a gap of **0.21 / 0.26 / 0.32 m** (C geometry, P wall offset +-0.05). The SUV's footprint is a **2.0 x 5.0 m box
  centred 0.177 m forward of its origin** (C, `.entity` `0x2D00061C`). The navmesh blocker should use that box.
- **Lift**: three causes, all visible in the 14:41:43 / 14:47:45 bytes.
  - (a) **The vehicle is put over the head in ONE bundle, 0.095 s into the lift.** That is a jump of 3.40 m (truck) or
    4.18 m (SUV), and the client snaps any jump of more than 2 m (C). So the car pops onto the champion while his pickup
    clip is only starting.
  - (b) **PickupObject `0x100007A1` (graph event SuperStrength_PickupCar) goes in the same tick.** The champion's graph
    is then in `SuperStrength_Car_Pickup`, which has no transition for that event, so it is dropped (C data, C server
    graph copy, P client). `SuperStrength_Car_Catch` therefore never plays. In the original, PickupObject comes at the
    catch (0x34000161 S9), when the graph is in Hold.
  - (c) **CarPickup comes 0.094-0.112 s after the lift, through an Instant transition.** The bend-and-grab part of
    the clip (Pickup_Start, 0 -> 0.45 s) is cut off and the clip jumps to the 0.45 s frame (a pop).
  - **Fix: replay 0x34000161's own timeline.**
    - CarPickup when Pickup_Start reaches Car_Pickup's start frame (0.45 s; this plays the whole clip; the data's
      Vfx_Event9 sends it at 0.05 s, which can be set from config).
    - At Car_Pickup's grab hook (code 3), the vehicle is **tossed in an arc** from where it stood onto the champion. The
      flight lasts TossDuration 0.3 + CatchDuration 0.35 s (C defaults), in hops shorter than 2 m.
    - At the catch: DisableHit, PickupObject on both (graph PickupCar -> **Car_Catch**), the vehicle at +2.5 m, and 0x8B.
    - Ready to throw AttachmentDuration 0.1 s later.
- **Implemented in fase3-if** (section 8), with the skeptic's corrections (section 7): CarPickup at the original's
  0.05 s by default (`[ics] liftable_car_pickup_at`; `"graph"` = the whole bend, 0.45 s), the graph read from
  `ics.graph.data()`, found by structure in all 56 graphs.

## 1. The SUV against the wall

### 1.1 The wall line (C, navmesh)

Boundary edges (edges used by one triangle) near the SUV, in local metres (landblock 0x13BB origin). The edges come
from the three agent blobs of `0xA0C112BA`, read with `ics.navmesh.parse_blob`:

| Agent (radius) | North edge of the strip the SUV stands on | South edge (fence) |
|---|---|---|
| `0x10000003` (0.525, champions) | (99.0, 96.2) -> (100.0, 95.8) -> (100.4, 95.6) -> (102.2, 94.8) -> **(107.2, 92.6)** (-23.75 deg) -> (107.8, 92.6) -> (110.2, 93.6) (camp pocket) | (95.6, 91.2) -> (99.4, 89.6); (100.8, 89.0) -> (107.0, 86.4) |
| `0x10000002` (1.1) | same x, y - 0.6 | same x, y + 1.0 |
| `0x10000001` (2.1) | same x, y - 1.6 | same x, y + 2.0 |

- The three edges are the same wall eroded by each agent's radius. Their perpendicular offsets relative to agent 3,
  -0.548 and -1.462 m, fit `offset = 0.48 - 0.93 r`. So the obstacle (the raised wall face) lies **0.48-0.55 m beyond
  the agent-3 edge** (C data, P that the erosion equals the radius within the 0.2 m vertex grid). Below, wall =
  agent-3 edge + 0.525 m, cross-checked with agent-2 edge + 1.1 m (they agree within 0.03 m).
- Nothing north of the edge is walkable (raster: rows above y 96.6 for x < 98.6 are blocked), and the whole strip is
  flat at z 200.1. This is the raised rubble block of frames 37 / 45.

### 1.2 The SUV's footprint (C, `.entity` box)

Every vehicle world state's `.entity` record starts with a box:
`did | 0 | 0 | 1 | half x, y, z | centre x, y, z | 1.0 | 0 | 0 | 0 | 1 | 0 | 1 | 0 | bbox min xyz | bbox max xyz`.
The bbox equals the centre +- half (C words, P meaning: the collision / bounds box).

| World state | `.entity` (pack @offset) | Half extents x / y / z | Centre y | Notes |
|---|---|---|---|---|
| `0x2E000795` SUV | `0x2D00061C` (`0xA000009A` @0x1A28AD4) | 1.000 / 2.500 / 1.116 | **+0.177** | bbox (-1.0, -2.323, -0.005)-(1.0, 2.677, 2.227) |
| `0x2E000F04` gaslight truck | `0x2D000C8F` (`0xA00002E5` @0x68E5E0C) | 1.000 / 2.500 / 1.160 | 0 | |
| `0x2E000559` sports car | `0x2D0003FC` | 1.000 / 2.500 / 0.752 | +0.202 | |
| `0x2E0008B8` police car | `0x2D000724` | 1.000 / 2.500 / 0.750 | +0.122 | |
| `0x2E000EFE` / `F03` / `F05` gaslight | `0x2D000C89` / `C8E` / `C90` | 1.000 / 2.500 / 1.029, 0.802, 0.655 | 0 | |

- The model's +y is the long axis. World heading = placement yaw + 90 deg (`units.heading_from_yaw`), i.e. the model's
  +y. So the SUV's box centre is its origin + 0.177 m along the heading (C arithmetic, P axis convention). It agrees
  with frame 45, where the hood is at the east-south-east end, the heading's direction.
- `[ics] liftable_blockers` today: SUV [2.5, 1.05] and truck [2.8, 1.15] (G, from frames). The data box is [2.5, 1.0],
  centred +0.177 m for the SUV.

### 1.3 Gap now and the new position (C geometry)

For each probe on the box's long side (rear end, middle, front end), a ray goes along the left normal of the heading
(north here) to the first agent-3 boundary edge. Gap = hit + 0.525 - 1.0.

| Placement | Rear (WNW) | Middle | Front (ESE) |
|---|---|---|---|
| SUV now (102.3, 93.6), yaw 245 | 0.539 | 0.587 | 0.642 |
| (102.42, 93.87) | 0.244 | 0.292 | 0.346 |
| **(102.43, 93.90) proposed** | **0.212** | **0.260** | **0.315** |
| (102.44, 93.92) | 0.190 | 0.238 | 0.292 |

- The proposed position moves the SUV 0.33 m along the wall normal n = (0.406, 0.914), i.e. +0.13 x, +0.30 y. The yaw
  is unchanged, as the tester asked. The rear end stays closer to the wall because the wall is 1 deg less steep than
  the SUV.
- The frames agree (G). In 45 a dark strip shows between the SUV's roof edge and the rubble; in 37 (the original) the
  roof meets it. A real gap of ~0.6 m, less the roof's parallax, fits what 45 shows.
- The champion's corridor south of the SUV keeps ~3.7 m between the blocker and the fence's agent-3 edge (C). The SUV's
  front end stays 2.5 m west of the camp pocket (x >= 107.8).
- The truck is not part of the report. It is the mirror case (left wall (52.6, 92.6) -> (59.0, 95.4), +23.63 deg), with
  a gap of **0.62 / 0.65 / 0.71 m** at (57.7, 93.6) and 0.33-0.42 m at (57.58, 93.87). It is O whether to move it too.

### 1.4 Blocker

`Liftables._block` blocks `[half length, half width (, angle offset)]` + 0.35 m margin, centred on `ent.pos`. To match
the box: centre = pos + fwd * (cos h, sin h) with a new 4th element `fwd`; SUV `[2.5, 1.0, 0.0, 0.177]` (C). Moving the
SUV moves the blocker with it (it is built from `ent.pos` at spawn / respawn).
`tests/test_match.py`'s "a path along a parked vehicle goes round it" still finds walkable end points 0.5 m north of the
axis at +-3.5 m: (99.46, 95.80) and (105.80, 92.84) are both inside the agent-3 strip (C). Its path must now go round
the south side.

## 2. The lift animation

### 2.1 What the server sent (C, traffic.log / server.log)

| t (s) after "lifts" | 14:41:43.483 truck (vehicle 6) | 14:47:45.180 SUV (vehicle 5) |
|---|---|---|
| -0.017 / -0.004 | "stops to cast" (1531 B) and "faces ... (throw skill in its slot)" (1442 B): full champion bundles, **before** the clip (ok) | same (1533 / 1444 B) |
| +0.001 | AGL `0x100007A2` InitObjectPickup (0x8D, var 0x108 = vehicle); vehicle `0x100007A2`; `0x20C9` event 0x1000001D slot 7 | same |
| +0.095 / +0.113 | AGL `0x100001E3` + 0x780 = **0x10000246 CarPickup** | same |
| +0.096 / +0.114 | AGL + vehicle **`0x100007A1` PickupObject** | same |
| +0.096 / +0.115 | **"carried over the head"** (130 B): pos (59.925, 92.975, 202.580), heading 2.868, speed 0, from (57.7, 93.6, 200.1): **2.31 m + 2.50 m up = 3.40 m in one state** | (105.027, 91.664, 202.580), heading 2.524, from (102.3, 93.6): **3.34 m + 2.50 m = 4.18 m** |
| +0.097 / +0.115 | AGL graph event 0x100003AF CbtState_DisableHit | same |
| +0.110 | server graph copy: "graph hook 3 (SuperStrength_Car_Pickup)", posted to AGL's scripts 0x340002B2 / B4 / B5 / B6 | same (+0.128) |
| +0.174 / +0.175 | vehicle 0x8B "rebuild pieces, over the head" | same |
| +0.563 / +0.546 | "carried over the head" again (`hold()`, carry_ready) | same |
| +0.72..1.02 | "move refused (crowd control)": 0x34000164 S4 holds input until `raise_event_follow` 0x100000BB at 1.2 s | |
| +1.215 | 0x34000164 S4 -> S3, "slot 7 kept ready while carrying (0x20F8)" | |

No champion bundle goes between the facing bundle and the throw (`liftable_hold_champion_bundles` works, C). The
throw at 45.866 matches the clip: ThrowObject on both, release +0.188, EnableHit +0.219, locomotion key +0.856. It
was not reported.

### 2.2 The champion's graph (C data)

`SM_SuperStrength_Car` (machine 8 of `chr_atomic_green_lantern_behavior.hkb`, start state 4), entered from
SM_Main_Machine's wildcard `SuperStrength_InitCarPickup` (flags 0xC00, effect **".1s_Ignore_ContinueBlend"**):

| State | Clip (car_*.hkx) cropStart / cropEnd / startTime / speed / mode | Triggers (clip-local s) | Out (effect) |
|---|---|---|---|
| 4 Pickup_Start | pickup, 0 / **0.783** / 0 / 1.0 / single | none | SuperStrength_CarPickup -> 1 (**"Instant_Ignore_ContinueBlend"**) |
| 1 Car_Pickup | pickup, 0 / 0 / **0.45** / **0.8** / single | a_SkillHook code 3 @0.46, state_to_state @0.75 | state_to_state -> 0 (".2s") |
| 0 Car_Hold | car_run_fwd_50 blend on Propel, looping | footsteps | **SuperStrength_PickupCar -> 3** (".075s") |
| 3 Car_Catch | catch, cropStart 0.122 | state_to_state @end-0.2 | state_to_state -> 0 (".075s") |
| 2 Car_Throw (wildcard ThrowCar) | throw | MissileFire 5 @0.2, SkillEnd 2 @0.22, to locomotion @end-0.1 | |

- The raw clip-generator fields are hkbClipGenerator (hk 2012.2): name +96, cropStart +108, cropEnd +112, startTime
  +116, speed +120, mode +134. The transition effect is a pointer at +32 of the 60-byte transition (C reads).
- In Car_Pickup the grab hook fires (0.46-0.45)/0.8 = **0.0125 s** after CarPickup, and Hold comes (0.75-0.45)/0.8 =
  **0.375 s** after it (+0.2 s blend).
- **Pickup_Start plays the clip from 0 to (D - 0.783).** In AGL's, Gaslight Batman's, AWW's and Flash's packs the clip
  tables (`uesrv.havok_anim.clip_table`) hold a **1.233 s** clip, and 1.233 - 0.783 = **0.45 = Car_Pickup's
  startTime**. So the clip is 1.233 s long (P), and Pickup_Start ends exactly on the frame where Car_Pickup starts: 0 ->
  0.45 is the bend-and-grab, which holds there until CarPickup; 0.45 -> 0.75 at 0.8x is the lift.
  - This matches icserver's Tutorial 1 notes. At 19:00, without CarPickup, "Batman bent down, grabbed the car and
    STAYED crouched". CarPickup "takes him from the crouch to the lift and the hands-up hold".
- **PickupCar has a transition only out of Hold.** Car_Pickup, Pickup_Start and the main machine's wildcards have none.
- 46 of 54 graphs have this same machine (19 identical to AGL's). The others differ:
  - Joker: speed 1.0.
  - chr_batman / Catwoman: Car_Pickup start 0.4103, hook 0.57.
  - AWW / Flash / Catwoman: hooks inside Pickup_Start too.
  - Arcane Green Lantern / Hawkgirl / Raven: hooks 0.25-0.6 in Car_Throw.
  - So the times must come from the champion's own graph.

### 2.3 What the original did (C scripts / scriptlets)

- **Super Strength `0x34000164`**: S4 = RaiseEvent(target, 0x10000037), node_100000AD(SELF)[1] (input hold). It waits
  for 0x100000BB (-> S3, the throw targeting) or 0x10000009 (end).
- **The vehicle's script `0x34000162`** S8, on 0x10000037: RunScriptlet(SELF, `0x100007A2`), so InitObjectPickup on
  the vehicle is original (ics' `on_object` is right). Then RaiseEvent(user, SELF, 0x10000085 -> `0x34000161`): this
  starts the sub-skill with the object IID.
- **Sub-skill `0x34000161`** graph S3. The defaults are its server-only blocks (C words):
  - **S6** pickup: RunScriptlet(SELF, `0x100000E9` Vfx_Event9), RunScriptlet(SELF, `0x100007A2`), face the object,
    object untargetable (0x10000029), input suppressed. **S6 -> S7 on OnCastSignal 3** (Car_Pickup's grab hook).
  - **S7** toss: team, SetObjectState[19], `LaunchLobbedMissile(object -> champion position + 1.1 m offset)` [script
    0x34000160, launch angle 70.0], RunScriptlet(object, `0x10000223` VFX_CBT_Hit_Shared, var 0x100002F8 =
    ObjectPickupScriptlet `0x1E0000BE`), DropObject = 1, RaiseEvent 0x100000BB -> 0x34000164.
    **TossDuration = 0.3** (block @4044: `0x3E99999A`).
  - **S8** catch: face, **CatchDuration = 0.35** (`0x3EB33333`). S8 / S7 -> S9 also on 0x10000002, the lob's landing
    through 0x34000160.
  - **S9**: RaiseGraphEvent `0x100003AF` (DisableHit), AttachEntity(offset (0, 0, 2.5), point 0x100000B0),
    **RunScriptlet(SELF and object, `0x100007A1` PickupObject)**, **AttachmentDuration = 0.1** (`0x3DCCCCCD`) -> S4
    (input back).
- **Scriptlet entries** in `0x1D0000EF` (pack `0xA00000DF`):
  - `0x100000E9` Vfx_Event9 @0x14863A0: props {0x7E6: 1}, 3 actions: [type 0x23 sequence: group `6 | 0.05 | 6 | 1` ->
    type 0x14 event `0x10000246` CarPickup], [type 0x14 `0x10000246`], [type 0x14 `0x10000176` InitCarPickup].
  - `0x100007A2` @0x1485F64: [type 0x14 `0x10000176`], [type 0x23: group 0.55 s -> type 4: 0.2 / 0.1 / 3 / 0.15, P
    camera shake; object vtable 0x15CE6E0, create 0x663D10].
  - `0x100007A1` @0x1485C68: [type 0x14 `0x10000175` PickupCar], [type 4: 0.2 / 0.1 / 3 / 0.03].
  - `0x100007A0` @0x1485BB4: [type 9 ...], [type 0x14 `0x10000174` ThrowCar].
- **Type 0x23 = timed sequence (C code)**: factory vtable 0x15CF4F8 (create 0x6633D0 / runtime 0x663450, object
  vtable 0x15B0D08), execute 0x52F760, update **0x52F940(now)**. A group fires once
  `now > group_time / rate + start` (group time = f32 at entry +0x14; callers 0x52FAB0 / 0x533A30 = runtime vt+0x34
  / +0x40). So Vfx_Event9 raises CarPickup, then InitCarPickup, at once, and CarPickup again 0.05 s later. The first
  CarPickup reaches Locomotion and is dropped. **The original's CarPickup therefore landed 0.05 s after the init** (C
  data, P runtime order), cutting the bend (0.05 -> 0.45 jump, inside the 0.1 s blend from locomotion).
- Original timeline (CarPickup at 0.05): Car_Pickup 0.05, toss 0.0625, Hold 0.425 (+0.2 blend), catch / PickupObject
  0.7125 -> **Car_Catch**, input back 0.8125.

### 2.4 Both timelines through the server's graph copy (C, `ics.graph.GraphInstance`, AGL)

| Timeline | States | PickupCar |
|---|---|---|
| ics fase3-ie (init 0, CarPickup 0.094, PickupObject 0.095) | Pickup_Start 0 -> Car_Pickup 0.094 (hook 3 at 0.1065) -> Hold 0.469 | **dropped (0.095, in Car_Pickup)**: no Car_Catch |
| original (Vfx_Event9 + init 0, CarPickup 0.05, S9 0.7125) | Pickup_Start 0 -> Car_Pickup 0.05 (hook 0.0625) -> Hold 0.425 -> **Car_Catch 0.7125** -> Hold | taken |
| proposed, CarPickup at 0.45 | Pickup_Start 0 -> Car_Pickup 0.45 (hook 0.4625) -> Hold 0.825 -> **Car_Catch 1.1125** -> Hold | taken |
| proposed, CarPickup at 0.05 | as the original | taken |

### 2.5 Why it reads as "starts lifting, then cuts to already holding it"

1. **The car teleports onto the head 0.095 s in (C bytes; C client rule, P for the vehicle's module).**
   `client-movement.md` 1.3, `0x60B5F0`: a new state more than 2 m away is a hard snap (`0x5C9E90`); under 2 m the body
   is steered. The single "carried over the head" state is 3.40 / 4.18 m away and turns the car 40 / 170 deg, so it
   pops over the champion while his clip is still in the bend. The 0x8B 0.08 s later rebuilds the pieces there.
2. **No catch (C graph data + server graph copy; P client, by the same Havok rule: an event with no transition is
   dropped).** PickupCar lands in Car_Pickup. The clip goes Car_Pickup -> Hold with the car already overhead, and
   Car_Catch (the car landing in his hands, with PickupObject's camera shake) never plays.
3. **The bend is cut (C data).** CarPickup at 0.094-0.112 s, through the Instant transition, jumps the clip from that
   frame to 0.45. By then the 0.1 s blend from locomotion is almost done, so the dip shows and then pops (P).

## 3. Implementation plan

### 3.1 SUV position and blocker (ics/config.py, ics/match/liftables.py)

- `ics/config.py` `liftable_props_by_map["crime_alley"]` SUV entry: `"pos": [102.43, 93.90, 0.0]`, `"yaw": 245.0`
  (unchanged). Comment: "2026-10-28 15:00 (tester report: move it closer to the wall without turning it;
  vehicle-lift-and-position.md 1): 0.33 m along the wall normal, long side 0.21-0.32 m from the wall north of it
  (navmesh edge + agent radius; .entity box half width 1.0)". The old value goes in the comment so it can be reverted.
- `ics/config.py` `liftable_blockers`: the C boxes, same comment date. Values: `"0x2E000795": [2.5, 1.0, 0.0, 0.177]`,
  `"0x2E000F04": [2.5, 1.0]`, `"0x2E000559": [2.5, 1.0, 0.0, 0.202]`, `"0x2E0008B8": [2.5, 1.0, 0.0, 0.122]`,
  `"0x2E000EFE" / "F03" / "F05": [2.5, 1.0]`. At least the SUV's; the truck's old [2.8, 1.15] can stay if wanted.
- `ics/match/liftables.py` `_block`: a 4th element = forward offset of the box centre along the heading.
  `fwd = float(size[3]) if len(size) > 3 else 0.0`; `cx = ent.pos[0] + fwd * cos(h)`, `cy = ent.pos[1] + fwd * sin(h)`
  with `h = ent.heading + angle offset`. Docstring updated.
- Optional, not asked: truck `[57.58, 93.87, 0.0]` (gap 0.33-0.42 m) if the tester wants both sides alike.

### 3.2 Vehicle lift = 0x34000161's timeline (ics/match/liftables.py)

1. `KINDS["vehicle"]`: add `"toss": True` (the rock keeps its attach-at-grab flow, 0x34000177 S3). Keep
   `"grab"` / `"hold"` for the `liftable_vehicle_toss = false` path.
2. New `Liftables._graph_times(ch)`, cached per graph name. From `self.w.graph_for(ch).g` (GraphDef), find the machine
   named `SM_SuperStrength_Car`, its states `SuperStrength_Car_Pickup_Start` and `SuperStrength_Car_Pickup` (clips[0]),
   and return:
   - `car_pickup` = Car_Pickup.start / Pickup_Start.speed (AGL 0.45);
   - `hook` = (Car_Pickup's a_SkillHook code-3 trigger t - Car_Pickup.start) / Car_Pickup.speed (AGL 0.0125);
   - `hold` = (Car_Pickup's state_to_state t - start) / speed (AGL 0.375).
   Fallbacks with no graph: 0.45 / 0.0125 / 0.375.
3. `lift()` for a kind with `"toss"` when `[ics] liftable_vehicle_toss` is true:
   - t 0: as now (facing bundle with the throw skill, InitObjectPickup on the champion and on the vehicle: original,
     0x34000162 S8). Do **not** send PickupObject, the carry bundle, the 0x8B or DisableHit here.
   - `car_at = [ics] liftable_car_pickup_at` (null = `_graph_times(ch)["car_pickup"]`; the
     `super_strength_cast_signals["vehicle_car_pickup"]` override also accepted): graph event CarPickup through
     `RAISE_EVENT_KEY` / `RAISE_EVENT_VAR` (the existing lambda, its 0.1 replaced by `car_at`).
   - `toss_at = car_at + hook`: `self._toss(ch, obj, flight)` with
     `flight = [ics] liftable_toss_seconds` (0.65 = TossDuration 0.3 + CatchDuration 0.35, C).
   - `catch_at = toss_at + flight`: new inner `catch()`. If `ch.carrying is obj`: `self._graph(ch, HIT_OFF, ...)`
     (S9 order); `info["pickup"]` (0x100007A1) on the champion and the vehicle; `self._carry(ch, obj, force=True)`
     (label "carried over the head", unchanged for the tests); `self._rebuild(obj, "liftable_attach_rebuild",
     "over the head")`.
   - `hold_at = catch_at + [ics] liftable_attach_seconds` (0.1, AttachmentDuration C): the existing `hold()`.
   - AGL totals: CarPickup 0.45, toss 0.4625, catch 1.1125, ready 1.2125. With `liftable_car_pickup_at = 0.05`:
     0.05 / 0.0625 / 0.7125 / 0.8125.
4. New `Liftables._toss(ch, obj, flight)`, modelled on `_fly`:
   - `steps = [ics] liftable_toss_steps` (12) hops over `flight`. From the parked position (s) to
     `self._hold_point(ch, obj)` (e, recomputed each hop): `p(f) = s + (e - s) f`, plus `liftable_toss_arc *
     sin(pi f)` on z (1.5 m G, which makes the car come down into the hands: dz/df(1) = 2.5 - 1.5 pi < 0).
   - Heading: shortest-arc interpolation from the parked heading to `ch.heading`. `speed = 0`, `dest = None`,
     `path = []`. Label the first hop "{obj} tossed onto {ch}", the rest None.
   - Each hop checks `getattr(ch, "carrying", None) is obj` and `obj.eid in w.entities`. If `not ch.alive`:
     `self._drop(ch, obj)` and stop.
   - At the first hop, the S7 scriptlet on the vehicle: `[ics] liftable_toss_scriptlet` =
     `{"key": "0x10000223", "vars": {"0x100002F8": "0x1E0000BE"}}` (P effect; {} = none). Pass the variable as
     `(0x100002F8, KIND_DID, 0x1E0000BE)` (property 0x100002F8 is kind DID, catalog).
   - Every hop is under 2 m (lift reach 4.5 m + 2.5 m up + arc: < 0.6 m per hop at 12 steps), so the client steers the
     car instead of snapping it.
5. Leave `tick()` / `_carry()` as they are: before carry_ready nothing else moves the vehicle.
6. Optional (P): `[ics] liftable_throw_queue = true`. A throw press before carry_ready (now up to 1.21 s) is stored
   and thrown at `hold()`; it is dropped today ("still lifting").
7. Leave `raise_event_follow {0x10000037: [0x100000BB, 1.2]}`. With the 0.45 timeline, input comes back at 1.2 s, the
   ready time (1.21). With 0.05 it could be 0.85 (the original's S4 at 0.81), but that key also drives the rock: O.

### 3.3 ics/config.py keys (each with "2026-10-28 15:00 tester report" and why)

```python
"liftable_vehicle_toss": True,      # false = fase3-ie (over the head + PickupObject at the grab frame)
"liftable_car_pickup_at": None,     # s after InitObjectPickup for CarPickup; None = from the graph (0.45: the whole
                                    # bend-and-grab, Pickup_Start's cropped end); 0.05 = the original's Vfx_Event9
"liftable_toss_seconds": 0.65,      # 0x34000161 TossDuration 0.3 + CatchDuration 0.35 (C)
"liftable_toss_arc": 1.5,           # m above the straight line (G)
"liftable_toss_steps": 12,          # hops (< 2 m each: client steering, not a snap)
"liftable_attach_seconds": 0.1,     # AttachmentDuration (C): catch -> ready to throw
"liftable_toss_scriptlet": {"key": "0x10000223", "vars": {"0x100002F8": "0x1E0000BE"}},   # 0x34000161 S7 (P)
```

### 3.4 Tests (tests/test_match.py, liftables block; no ports)

The test champion is Gaslight Batman, whose graph has the same SM_SuperStrength_Car as AGL. Use
`run(s, m, t, step=0.05)` for timing.

- Existing: `run(s, m, 1.0)` after the lift -> **1.5** (the catch is at 1.11 s). "rides 2.5 m over the champion" and
  "rebuilt after it is put over the head" then hold unchanged.
- New checks:
  1. At 0.40 s: no "graph event CarPickup" yet. At 0.50 s it is sent (CarPickup = Pickup_Start's cropped end, from the
     graph).
  2. At 0.50-1.05 s: no "SuperStrength_PickupObject" label, and no "carried over the head" before the catch.
  3. Toss: the vehicle's positions sampled every 0.05 s from 0.45 to 1.15 s are all < 2 m apart, z rises above the
     ground, and xy moves from the parked spot toward the champion.
  4. At 1.15 s: PickupObject sent to the champion **and** the vehicle, after DisableHit. The vehicle is at
     `ch.pos + (0, 0, 2.5)`. `w.graph_for(ch).events` contains `("SuperStrength_PickupCar", True)` and
     `state_names()` held `SuperStrength_Car_Catch` (the server's graph copy took the catch).
  5. At 1.25 s: `ch.carry_ready`. A `throw()` at 0.9 s is refused (or queued, if 3.2.6 is done).
  6. Champion dies mid-toss (kill at 0.8 s): the vehicle is dropped / explodes (`_drop`), `ch.carrying is None`.
  7. `liftable_vehicle_toss = False`: the fase3-ie order (PickupObject and "carried over the head" within 0.15 s).
  8. SUV placement:
     - The SUV (world state 0x2E000795) has yaw 245.
     - Gaps: take the boundary edges of `navmesh.parse_blob(<0xA0C112BA data>, <agent 0x10000003 blob>)` (edges used
       by one triangle, minus the landblock origin 0x13 * 160, 0xBB * 160). Cast rays from pos + 0.177 u + a u, for
       a in (-2.5, 0, 2.5), along the north normal. The gap `hit + 0.525 - 1.0` must be in **[0.15, 0.35]** for all
       three (0.21 / 0.26 / 0.32 expected).
     - The rasterised `NavGrid` overstates the gap by ~0.1 m, so use the edges, not `walkable()`.
  9. The SUV's blocker covers the box: `not nav.walkable(c - 1.25 n)` and `nav.walkable(c - 1.5 n)` on the south side
     (box 1.0 + margin 0.35), with c = the box centre.
- Rerun `python tests/test_match.py`, `tests/test_ics.py` and `tests/test_session_flow.py`, with this area's ports.

### 3.5 Docs (rule 3, by the implementer)

- `catalog/data/world_objects.tsv` row `0x2E000795`: position (102.43, 93.90) yaw 245, `.entity` box 2.0 x 5.0 x 2.23
  m, centre +0.177.
- `catalog/data/scriptlets*.tsv`: `0x100000E9` Vfx_Event9 on champions = CarPickup at 0 / +0.05 + InitCarPickup.
  `0x100007A2`: the 0.55 s camera shake.
- `docs/reverse-engineering.md`: type 0x23 timing (0x52F940); the SuperStrength_Car crop arithmetic; the vehicle
  timeline.
- `docs/CHANGELOG.md` `## fase3-if` bullets. Then `python ic.py catalog`.

### 3.6 Runtime check (optional, no new diag mode needed)

`python tools\diag.py --grafo` during a lift logs each graph event reaching AGL's graph
(`0x2729A9 GRAPH event about to reach the graph`, `0x15BD9F delivered`). Expected: 0x10000176 at the lift, 0x10000246
at +0.45, 0x10000175 at +1.11. `--anims` gives car_pickup's real duration (expected 1.233 s).

## 4. Confidence

| Issue | Cause | Fix (keys) | Confidence |
|---|---|---|---|
| Gap SUV - wall | the wall is 1.13-1.24 m from the box's long side axis (0.54-0.64 m gap) | pos (102.43, 93.90), C box blocker (`liftable_props_by_map`, `liftable_blockers`) | C navmesh / box, P wall = edge + radius (+-0.05) |
| Car pops onto the head | one 3.4-4.2 m state at +0.095 s; client snaps > 2 m | toss in < 2 m hops over 0.65 s (`liftable_vehicle_toss`, `liftable_toss_*`) | C bytes, C client rule, P for the vehicle's module |
| No catch, "already holding it" | PickupObject (PickupCar) sent while the graph is in Car_Pickup | PickupObject at the catch (S9) | C data + server graph copy, P client |
| Pop at the start | CarPickup 0.094-0.112 s, Instant transition to frame 0.45 | CarPickup at Pickup_Start's end (`liftable_car_pickup_at`) | C data, P clip length 1.233 |
| Original's own CarPickup time | Vfx_Event9 type-0x23 group 0.05 s | 0.05 available by config | C words + C code (0x52F940), P event order |

## 5. Open

- O: how long the original's lob flew. LaunchLobbedMissile at 70 deg is driven by the client, and S9 also fires on the
  landing event. 0.65 s (the S7 + S8 timers) is the upper bound used.
- O: what the tester prefers. The data's 0.05 s (a quick dip) or the whole bend (0.45 s, recommended because of the
  report). It is one key.
- O: VFX_CBT_Hit_Shared with 0x100002F8 = 0x1E0000BE on the vehicle (S7): what it shows (dust / sound, P).
- O: during the carry the original made the vehicle untargetable (AddAttributeModifier 0x10000029 false, S6 -> S3);
  ics does not. No report.
- O: whether to move the truck too (same 0.62-0.71 m gap on the mirrored side).

## 6. Finalizer check (2026-10-28, spot checks before implementation; no server code changed)

Re-checked (C):
- **Server order (code)**: `ics/match/liftables.py:259-262` sends CarPickup through `later(0.1)`. `grab()` (`:264-279`,
  scheduled `:292` at KINDS grab 0.11) sends PickupObject `0x100007A1` on both, ONE `_carry(force=True)` state at
  +2.5 m, the 0x8B (+0.05 s) and DisableHit. `hold()` runs at 0.57 s. This is the order of table 2.1.
- **Graph (data/skill_graphs.json, raw clip generators of pack 0xA0000150)**: AGL and Gaslight Batman (the test
  champion 0x40000086) have identical machines. PickupCar `0x10000175` is taken only by Hold -> Catch. CarPickup
  `0x10000246` takes Pickup_Start -> Car_Pickup. Car_Pickup: start 0.45, speed 0.8, hook 3 @0.46, state_to_state @0.75.
  Pickup_Start: cropEnd 0.783, mode 0. Car_Catch: cropStart 0.122.
- **Server graph copy** (`ics.graph.GraphInstance`, offline driver, Gaslight Batman):
  - fase3-ie timeline: PickupCar at 0.095 is **not taken**.
  - Proposed timeline: Car_Pickup 0.45, hook 3 0.4625, Hold 0.825, **Car_Catch 1.115**, Hold 1.415.
- **0x34000161** (`script_model` + `Instance._defaults`). Transitions:
  - T12 S6 -> S7 on OnCastSignal 3.
  - T6 S7 -> S8 on TossTimer; T5 S8 -> S9 on CatchTimer; T8 S7, S8 -> S9 on 0x10000002.
  - T2 S9 -> S4 on AttachmentTimer.

  States:
  - S7: lob script 0x34000160, angle 0x428C0000 = 70.0; RaiseEvent 0x100000BB.
  - S9: DisableHit, AttachEntity, then PickupObject on SELF and on the object.

  Defaults: TossDuration 0.3, CatchDuration 0.35, AttachmentDuration 0.1, AttachmentOffset (0, 0, 2.5),
  ObjectPickupScriptlet 0x1E0000BE.
- **SUV**: world state 0x2E000795 -> `.entity` 0x2D00061C (pack 0xA000009A @0x3BAB75C). Box (@0x1A28AD4): half (1.0,
  2.5, 1.116), centre (0, 0.177, 1.111), identity rotation. The truck 0x2E000F04 -> 0x2D000C8F has centre 0.
  - The gaps reproduce: 0.539 / 0.587 / 0.642 now; 0.212 / 0.260 / 0.315 at (102.43, 93.90). Measured from the
    agent-2 edge instead: 0.240 / 0.286 / 0.340.
  - Hand check: box centre (102.590, 93.825) is 0.735 m from the edge (102.2, 94.8)-(107.2, 92.6), so the gap is 0.26.

Gaps and contradictions:
1. **The logs are gone.** `logs/` has been empty since 18:49 (server / traffic / unhandled / diag), and no copy is in
   the repository or the scratchpads. Table 2.1's bytes could not be re-read; they agree with the code path above.
2. **`_graph_times` must not look states up by name.** Joker's graphs (`chr_joker`, `chr_joker_skin_arkham`) name the
   start state 4 "SuperStrength_Car_Pickup" and the clip state 1 "Clip_SuperStrength_Car_Pickup".
   - Find the states by structure: Pickup_Start = the machine's `start`; Car_Pickup = the target of its
     `SuperStrength_CarPickup` out-transition; Hold = the target of Car_Pickup's `state_to_state`.
   - Census: 50 of 56 graphs have the machine, 42 of them with AGL's timings (3.2's "46 of 54" counts differently).
   - No machine (use the fallbacks): doomsday, gaslight_catwoman, vampire_batman, poison_ivy, wonder_woman, zatanna.
3. **`Car_Pickup.start / Pickup_Start.speed` is Pickup_Start's end only where cropEnd = D - Car_Pickup.start.**
   - It holds for AGL, AWW and Flash (0.783 and 0.45) and for chr_batman (0.823 and 0.41), if D = 1.233.
   - Not for Supergirl: cropEnd 0.783 but start 0.41, so CarPickup would come about 0.04 s early. Harmless.
   - skill_graphs.json has no cropEnd field.
4. **Code-3 hooks inside Pickup_Start**: AWW and Catwoman at 0.4103, chr_batman at 0.427, Flash at 0.40.
   - With CarPickup at 0.45, the server's graph copy delivers an early hook 3 for AWW and Flash. In the original
     (CarPickup at 0.05) these hooks were never reached.
   - Check that no champion script reacts to that hook.
   - AWW's Car_Pickup also differs: mode 1 (looping), hook at +0.15 s, Hold at +0.4375 s.
5. **The toss target is an approximation (G).** S7 aims the lob at the champion + 1.1 m horizontally toward the object
   (`normalize(xy) * 0x3F8CCCCD`, MissileOffset 0). The +2.5 m comes only from S9's AttachEntity. The plan ends the
   toss at `_hold_point` (+2.5 m) so there is no jump at the catch.
6. **Hops are larger than 3.2.4 says.** At 4.5 m reach the first hops are about 0.7 m, not < 0.6 m: dz/df(0) = 2.5 +
   1.5 pi gives 0.6 m up per 1/12, plus 0.375 m across. That is still under the 2 m snap. That vehicles replay
   through the rigid-body module (vtable 0x15C6360 / 0x60B5F0) is P strong (0xB0 module byte 0x62,
   destructible-vehicles.md 4).
7. **Test 9's thresholds fall inside one 0.25 m cell.** `NavGrid.block` (`ics/navmesh.py:164-181`) tests cell
   centres. Use about c - 1.1 n for blocked and c - 1.75 n for walkable, not 1.25 / 1.5.
8. **Cause (c) is not a departure from the original.** Vfx_Event9 put the original's CarPickup at 0.05 s, which cuts
   the bend more than fase3-ie's 0.1 s.
   - The 0.45 default goes beyond the original. Tutorial 1 supports it: `icserver/finale.py:375-381` with `lift_step`
     0.5 sent CarPickup about 0.6 s after the init, so the whole bend played.
   - Keep `liftable_car_pickup_at = 0.05` as the "as the original" switch.
9. **Test timing**:
   - `run()` defaults to step 0.25 (`tests/test_match.py:77`), so the timing checks need step <= 0.05.
   - Take the expected times from `_graph_times(ch)` instead of literals; `config.load()` reads config.toml.
   - With the toss, `run(s, m, 1.0)` after the lift must become >= 1.25.
10. **0x100000BB timing.** The original raised it at S7 (the toss start). ics's `raise_event_follow` at 1.2 s stands
    in for 0x34000161's own input hold (S6 node_100000AD [1] ... S4 [0]), which ics does not run.
    - With the 0.45 timeline, ready comes at 1.2125. A throw pressed in that 12.5 ms window is refused ("still
      lifting") unless 3.2.6's queue is done.

## 7. Skeptic review (2026-10-28, independent re-check; no server code changed)

**Verdict.** None of the four causes is refuted, and the plan can go ahead with the corrections below. Every check
was rerun with my own throw-away scripts (scratchpad `skeptic_vehicles/`), not the earlier ones.

Re-checked (C unless marked):
- **Navmesh** (`0xA0C112BA`, all three blobs): agent 3 has (100.4, 95.6) -> (102.2, 94.8) at -23.96 deg and (102.2,
  94.8) -> (107.2, 92.6) at -23.75 deg. Agents 2 and 1 have the **same vertices shifted by exactly -0.6 / -1.6 m in y**.
  The horizontal corridor walls step the same way (y 91.4 / 92.0 / 93.0 and 96.6 / 96.0 / 95.0). At (102.43, 93.90)
  the box centre is 0.735 m from the edge. Corners by hand: rear-left 0.212 m, front-left 0.315 m from the wall.
- **Box**: `0x2D00061C` @0x1A28AD4 has half (1.0, 2.5, 1.1162) and centre (0, 0.1768, 1.1113). World state header
  @0x3BAB75C: `0x2E000795 | 7 | 0x2D00061C`. Truck `0x2D000C8F` @0x68E5E0C: centre 0.
- **Clip generators** (pack 0xA0000150):
  - Pickup_Start: cropEnd (+112) 0.7833. Car_Pickup: startTime 0.45, speed 0.8. Car_Catch: cropStart (+108) 0.122.
  - The offsets fit hk2012: +132 = binding index 0xFFFF, +134 = mode.
- **Transition effects** (pointer at +32 of each transition):
  - InitCarPickup: `.1s_Ignore_ContinueBlend`, flags 0xC00 (no 0x200, so no self-transition).
  - CarPickup: `Instant_Ignore_ContinueBlend`. Car_Pickup -> Hold: `.2s`. Hold -> Catch on PickupCar: `.075s`.
  - Nothing else in AGL's graph takes `SuperStrength_PickupCar`.
- **`ics.graph` driven offline** (my driver):
  - fase3-ie: PickupCar at 0.095 is **not taken**.
  - Original: CarPickup at 0 (dropped), Init at 0, CarPickup at 0.05, PickupCar at 0.7125 -> Car_Catch at 0.7125.
  - Proposed 0.45 timeline: Car_Catch at 1.1125.
- **Scriptlet words** (pack 0xA00000DF):
  - `0x100000E9` @0x14863A0 has 3 actions: [0x23: `0x3D8 | 1` group (6, 0.05, 6, 1) -> 0x14 `0x10000246`],
    [0x14 `0x10000246`], [0x14 `0x10000176`].
  - `0x100007A2` @0x1485F64: [0x14 `0x10000176`], [0x23: `0x205 | 1` group (6, 0.55, 6, 1) -> type 4].
  - `0x52F940` fires a group once `now > t / rate + start`. The rate is vt+0x4C = `0x515960`, which returns
    def[+0x50] * def[+0x4C] (P: the action's two 1.0 words). So the delayed CarPickup comes after 0.05 s.
- **`0x60B5F0`**: it steers only when dx^2 + dy^2 + dz^2 <= 4.0 and otherwise snaps through `0x5C9E90`, but only when
  the module has a body (+0x1C != 0). Whether a vehicle takes this path stays P. Hops under 2 m beat one 3.4-4.2 m jump
  either way: steered, or snapped at 18 Hz.
- **`0x34000161`** (`script_model` + `Instance._defaults`): as section 2.3.
  - Defaults: TossDuration 0.3, CatchDuration 0.35, AttachmentDuration 0.1, AttachmentOffset (0, 0, 2.5),
    ObjectPickupScriptlet 0x1E0000BE, MissileVelocity 15.0 (the throw's, S2).
  - Also **MaxRange 1.0**: S10 -> S6 (IsInRangeAndAngle flags [1 1] = plus both radii). Otherwise T7 goes S10 -> S3
    and ends the sub-skill.
- **fase3-ie order from the code** (tests/test_match.py harness, 0.01 s steps; the logs are gone). Times after the lift:

  | t (s) | Sent |
  |---|---|
  | 0 | init |
  | +0.10 | CarPickup |
  | +0.11 | PickupObject on both, "carried over the head", DisableHit |
  | +0.17 | 0x8B |
  | +0.57 | hold bundle |

  This is table 2.1's order. `tests/test_match.py`: 208 / 208 before any change.
- **Bots never lift**: `bot_skip_scripts` holds 0x34000164 (`ics/match/bots.py:257-258`). So the AWW / Flash graph
  differences matter only to a player using those champions.

Corrections:
1. **Make `liftable_car_pickup_at` default to 0.05, the original's own Vfx_Event9 timing, not the graph's 0.45.**
   - The scriptlet sends CarPickup at 0 and again at +0.05 just to skip Pickup_Start. With MaxRange 1.0 + radii, the
     original also lobbed the car from metres away, so a full bend would grab air.
   - 0.45 costs more:
     - 0.4 s more of the lift (ready at 1.21 s, not 0.81 s);
     - the code-3 hooks inside Pickup_Start of AWW / Flash / Catwoman / chr_batman, which the original never reached;
     - a longer wait in the existing test.
   - At 0.05, cause (c)'s pop falls inside the locomotion blend, which is still running (0.1 s): P, smaller pop.
   - The report ("cuts to already holding it") is causes (a) + (b). Keep 0.45 / null as the switch if the tester still
     misses the bend.
2. **`_graph_times` must read `ics.graph.data().for_variant(ch.class_id)`, not `self.w.graph_for(ch).g`.**
   graph_for returns None while `script_runtime.GRAPH_RUNTIME` is off. tests/test_match.py never sets it (my harness
   got None), so the tests would only exercise the fallbacks.
3. **Section 1.2's "C footprint" is too strong.** All seven vehicle `.entity` boxes are exactly 1.0 / 2.5 in x / y,
   the sports car included; only z and the centre vary. It is a uniform proxy (C data, P footprint). The gap does not
   include the mesh's real width.
4. **The wall offset is 0.48-0.60 m beyond the agent-3 edge, not +-0.05.** The erosion steps are quantised (exactly
   0.6 / 1.6 m on every wall).
   - Gaps at (102.43, 93.90), in m:

     | Probe | Gap |
     |---|---|
     | Rear | 0.17-0.29 |
     | Middle | 0.22-0.34 |
     | Front | 0.27-0.39 |

   - The SUV cannot overlap the wall, but a strip may still show. If it does, the next step is (102.49, 94.04), which
     is +0.15 m along n.
5. **Orientation (G, frames).** In the original the SUV faces the other way.
   - Frames 35 (the yellow phase-in) and 37 show the hood + windshield at the WNW end, and the flat tailgate with a
     red tail light at the ESE end, by the jungle mouth. Ours (43 / 45) has the hood at the ESE end.
   - Section 1.2's "agrees with frame 45" holds only for ours. Yaw 245 is about 180 deg off: the original is about 65.
   - The tester said not to turn it, so keep 245 for this build and tell him.
   - With yaw 65 the gap changes by < 0.01 m, and the box centre moves 0.354 m WNW.
6. **Death before the first toss hop.** `tick()` skips the dead-carrier check until carry_ready
   (`liftables.py:379`). So a carrier killed before the toss keeps the car until the first hop's alive check.
   `catch()` / `hold()` should also drop the car on `not ch.alive`.
7. **Test 9.** At the new position, blocked at 1.25 / walkable at 1.5 passes, but at the old position 1.35 is already
   walkable. Use 1.1 / 1.75 (finalizer 7). The path test's north end points stay walkable at the new position:
   (99.47, 95.83) and (105.81, 92.87).

Still open: the truck's mirrored gap (0.62-0.71 m). Also `raise_event_follow` 1.2 s: with 0.05 the champion stands
still 0.39 s after ready, while the original released 0x34000164 at S7.

## 8. Implemented (fase3-if, 2026-10-29)

The plan of section 3 with the skeptic's corrections 1, 2, 6 and 7 (CarPickup at the original's 0.05 s, the graph read
from `ics.graph.data()`, a dead carrier drops the car before the catch too, test 9 at 1.1 / 1.75 m). Every behaviour
change is an `[ics]` key with the 2026-10-28 15:00 comment in `ics/config.py`.

**SUV** (`ics/config.py`, `ics/match/liftables.py` `_block`):
- `liftable_props_by_map["crime_alley"]` SUV `"pos": [102.43, 93.90, 0.0]`, `"yaw": 245.0` (was [102.3, 93.6, 0.0];
  same yaw as asked, although the original's faces the other way, ~65, correction 5). Long side 0.21 / 0.26 / 0.32 m
  from the wall (0.17-0.39 m with the quantised wall offset, correction 4); next step if a strip still shows: (102.49,
  94.04).
- `liftable_blockers["0x2E000795"] = [2.5, 1.0, 0.0, 0.177]` (was [2.5, 1.05]): the `.entity` box, centred 0.177 m
  forward. `_block` takes an optional 4th element, the box centre's offset along heading + angle offset. The truck and
  the other vehicles keep their G sizes.

**Lift** (`ics/match/liftables.py`):
- `KINDS["vehicle"]["toss"] = True`; `lift()` takes the toss path when `[ics] liftable_vehicle_toss` (true) and returns
  before the fase3-ie `grab()` (kept for `false`, as are KINDS grab 0.11 / hold 0.57).
- `_graph_times(ch)`: SM_SuperStrength_Car of `ics.graph.data().for_variant(ch.class_id)`, found by structure (the
  start state's `SuperStrength_CarPickup` out-transition -> Car_Pickup's first clip: car_pickup = its start / the
  start state's clip speed, hook = its code-3 trigger, hold = its `state_to_state`, end-relative triggers skipped),
  cached per graph, `CAR_TIMES` (AGL's) when nothing is found.
  - **Census by structure (C, all 156 variants, 56 graphs): every graph has the machine.** The six "no machine"
    graphs of 6.2 (doomsday, gaslight_catwoman, poison_ivy, vampire_batman, wonder_woman, zatanna) name it
    `SM_SuperStrength_Car_Throw` (Doomsday's states `Clip_Doomsday_Car_Pickup00` / `Clip_Doomsday_Car_Pickup`) with
    AGL's timings. Timings (car_pickup / hook / hold, s): 49 graphs 0.45 / 0.0125 / 0.375 (AGL, Gaslight Batman);
    chr_batman, Catwoman 0.4103 / 0.1597 / 0.3897; Nightmare Superman, Supergirl 0.4103 / 0.0497 / 0.3397; Joker and
    its Arkham skin 0.45 / 0.01 / 0.3; AWW 0.45 / 0.15 / 0.4375. No variant uses the fallback.
- `_toss_timeline(ch)`: CarPickup at `[ics] liftable_car_pickup_at` (0.05; `"graph"` or < 0 = the graph's
  car_pickup), toss at + hook, catch at toss + `liftable_toss_seconds` (0.65) but never before Hold + 0.05 s, ready
  `liftable_attach_seconds` (0.1) after the catch.
- `_toss(ch, obj, t0, t1)`: from t0 the S7 scriptlet `liftable_toss_scriptlet` (0x10000223 VFX_CBT_Hit_Shared, variable
  0x100002F8 = 0x1E0000BE; both vehicles' tables hold the key, C) on the vehicle, then `liftable_toss_steps` - 1 (11)
  states every (t1 - t0) / 12 s: p(f) = parked spot + (hold point - parked spot) f, z + `liftable_toss_arc` (1.5) sin(pi
  f), the hold point recomputed each state, heading turned by the shortest arc to the champion's, speed 0, no
  destination. It stops when the carry ends; a dead carrier drops the car where it is.
- `_catch` (S9): DisableHit, the vehicle's state on the hold point (label "carried over the head"), PickupObject
  0x100007A1 on the champion and on the vehicle, the 0x8B rebuild 0.05 s later (`liftable_attach_rebuild`).
- `_hold` (ready, the old inner `hold()`): also drops the car when the carrier is dead (correction 6).
- AGL / Gaslight Batman with the defaults: init 0, CarPickup +0.05, S7 scriptlet +0.0625, toss states +0.117 ..
  +0.658 (0.054 s apart; the first hop is the longest, 0.7 m from 4.5 m away, 0.8 m at the 6 m reach), Hold +0.425 (+0.2
  blend), catch +0.7125 (PickupCar taken by Hold -> Car_Catch), 0x8B +0.7625, ready +0.8125. With `"graph"`: CarPickup
  0.45, toss 0.4625, catch 1.1125, ready 1.2125.
- Bundles: the toss's states are ordinary `World.update`s; in the object-update "delta" mode
  (object-update-bundles.md) they go as motion-only 0xB0 states; nothing in the toss needs a full bundle.

**Tests** (`tests/test_match.py`, liftables block, 0.05 s steps): SUV yaw 245 and its three gaps in [0.15, 0.35] from
the champion navmesh's rim + agent radius; the blocker (blocked 1.1 m south of the box centre, walkable at 1.75 m);
`_graph_times` for Gaslight Batman, Joker, chr_batman, Wonder Woman, Doomsday and no graph; the `"graph"` timeline;
CarPickup once at `liftable_car_pickup_at`; the toss (11 states < 2 m apart, closing on the champion, above the hold
height, no PickupObject / over-the-head state before the catch); the catch order (DisableHit, over the head,
PickupObject on both) and ready time; the server's graph copy replaying the champion's feed enters Car_Catch; a throw
pressed mid-toss refused; `liftable_vehicle_toss = false` = the fase3-ie order; a carrier killed mid-toss drops the
car. The existing carry / throw / blast / respawn checks are unchanged.

**Not done**: `liftable_throw_queue` (with 0.05 the ready time, 0.81 s, comes before `raise_event_follow`'s 1.2 s, so no
press is refused in practice); the truck (not reported, its gap 0.62-0.71 m); `raise_event_follow` stays 1.2 s for the
vehicle and the rock (the champion stands 0.39 s after ready; the original's input came back at S9 -> S4, 0.81 s).
Runtime confirmation if needed: `python tools\diag.py --grafo` during a lift: 0x10000176 at the lift, 0x10000246 +0.05,
0x10000175 about +0.71 s, delivered to the graph.

## 9. Review fix (fase3-if, 2026-10-29): `liftable_attach_kinds` at the catch

A confirmed review finding: with `liftable_vehicle_toss` on (default) `lift()` returns before the old `grab()` is
scheduled, and `_catch` always carried the vehicle by its own states, so `[ics] liftable_attach_kinds = ["rock",
"vehicle"]`, documented as the way back to the containment attach, did nothing unless the toss was also off. `_catch`
now asks `_attached_kind` as `grab()` does: such a vehicle is put on the hold point and attached to the champion
(`_attach`, the 0xB0 parent block), the 0x8B rebuild says "attached", `_hold` then sends no carry state and the throw
detaches it as before. Default (`["rock"]`): unchanged. Tests: test_match +2 (tossed, then attached at the catch and
ready after it; the throw detaches it).
