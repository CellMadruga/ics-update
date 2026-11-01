# Meteorite aura, lift timing, the stepped throw, the vanishing vehicle (2026-10-29, fase3-io)

Tester report 2026-10-29 21:10 (Crime Alley v AI, Atomic Green Lantern vs Gaslight Batman, build fase3-in; server run
21:03-21:10, `server.log`, `traffic.log`, `diag.log` with `--fog --ring --throwpress --destruction` from 21:04;
screenshot 73 of the original game). Rock 0 lifted 21:06:20.184 / thrown 24.002; vehicle 8 (gaslight van) lifted
21:08:20.120 / thrown 26.372 / landed 27.747; vehicle 6 lifted 21:10:07.978 / thrown 17.573 / landed 18.925.
Tags: **C** confirmed (code / data / log read), **P** probable, **O** open. Exe `InfiniteCrisis.exe`, base 0x400000,
decomp `re-work/decomp/c`; diag RVAs = VA - 0x400000 (this run's image base was 0x940000).
Builds on `liftable-carry-throw-press.md`, `liftable-throw-destruction.md`, `vehicle-lift-and-position.md`,
`destructible-vehicles.md`, `camps-colour-bar-positions.md`, `client-movement.md`.

## 0. Throw press (the fase3-in question)

- **The meteorite threw on the first press this time (C).** diag 21:06:20: the lift press (slot 7, quick cast type
  0xE = unit target) -> hold check passed (`lock=0`, `current=0xffffffff`); 21:06:23: one press, quick cast type **0xD**
  (rubble line), hold check passed, and the server got the order at 21:06:24.001 (`skill order: slot 7 ... throws rock 0`).
  So the fase3-in gate held: the indicator (0x2180 / 0x20F9) came after the slot's "kept ready" 0x20F8
  (`liftable_indicator_after_cooldown`), and the client's targeting for slot 7 was the rubble line. The fase3-in
  failure was the indicator arriving before 0x20F8 (P, now strongly supported: same rock, same client, only the order
  changed). `liftable_throw_on_press` did not fire for the rock.
- **Vehicle 6 (21:10):** a throw order came 0.35 s into the lift (21:10:08.328, "still lifting", dropped); the next two
  presses (12.866, 17.570) sent 0x20EA with no 0x20EE, and `liftable_throw_on_press` threw at the second (C server log).
  P: the client counted the dropped order as cast. Fix: `[ics] liftable_throw_early_queue` keeps an order that arrives
  during the lift and throws it when the carry is ready.
- The diag's ORDER / PRESS lines were muted at 21:06:06 by 100 move orders (`cmd=0x4`): `tools/tracer.py` no longer
  logs or counts ORDER / PRESS lines for slot 0 / move orders.

## 1. "The meteorites lack a red aura" (screenshot 73)

### 1.1 Data (C)

| Object | Tables | What tints |
|---|---|---|
| Meteorite `0x400005C9` / ws `0x2E000D22` | class `0x1D0004FB` (Vfx_Active, Vfx_PickUp, ...), ws `0x1D000385` | `_Entity_OnSetClientRelationship 0x100003A6`: a 0x22 container on colour index `0x100007A2` setting appearance set `0x19000A61` group `0x10000004`: 5 -> `0x1000011E` (material `0x16000E7D` RGBA 1 0 0 0.75, **red**), 3 blue, 6 yellow, 1 purple, 0 Null |
| Its children `0x2E000D13` / `0x2E000D14` (ctype 9, the orb parts) | `0x1D00038B` | `Vfx_Startup` (props {0x211 = 1}): the same container on `0x100007A2`; `Vfx_Active_Red 0x100007F2` / `_Purple 0x10000D86` / `_Blue 0x100007F6`: action type 1 on appearance set `0x19001299` group `0x10000002`; `Vfx_TeamColor_SetParentColor` |
| Base `0x2E000D25` (ctype 3) | `0x1D0004AA` | `Vfx_Active_State1` = particle `0x18000A31` + stop State0; `_State2` = `0x18000A3C` + stop State1; `_State3` = `0x18000A3D` + stop State2; `Vfx_Stop` = `0x18000A3E` + stop State3 |

- Neither rock script (`0x34000167` collision / destruction, `0x34000347` phasing) runs a tint or aura key (C, VM dump).
- The base got `[ics] liftable_bases.rock.scriptlets` = Vfx_Startup / Object_Closed / Vfx_Active: **none is in its table**,
  so `World.scriptlet` never sent them (C traffic 21:04:48: only the spawn bundles). The rock got
  `_Entity_OnEnterWorld_Default` and `Vfx_Active` (21:04:57), which hold no tint.
- The client runs `_Entity_OnSetClientRelationship` only from `0xA7B0D0` on a PVP_Team **change** (listener `0xA813F0`),
  taking colour override `0x10000CF0` first, for teams 0..2 only (team 3 -> colour 0 = Null) (C,
  `camps-colour-bar-positions.md` 1.1). The rocks never got a team change: no tint (C path).

### 1.2 Fix (P: that the original's red is this tint)

- `[ics] liftable_aura = {"rock": {"colour": 5, "base_on": [], "base_off": []}}` (`Liftables._aura`): after the unit
  flags (`unit_flags_delay` + 0.2 s) the rock gets `0x10000CF0 = 5` (0x6, also kept in its bundle properties) then
  PVP_Team 3 -> 0 (0x6) so the client tints it red; at the grab / toss (the sub-skill set the object's team to the
  thrower's, C `0x34000177` S3 / `0x34000161` S7) PVP_Team 3 = colour 0 = Null (aura off); a respawned rock starts
  tinted. base_on / base_off: the crater's keys at those moments ([] by default; the State1..Stop chain's meaning is P).
- `[ics] liftable_bases.rock.scriptlets = ["Vfx_Active_State1"]`: the base's own idle key once at spawn (P meaning).
- O: whether the orb children follow the parent's tint (their own Vfx_Startup reads their own `0x100007A2`; a child
  world state has no server IID, so 0x8D cannot reach it). If the orb stays dark, the next step is a probe on
  `0xA7B0D0` / the children's build.

## 2. "Lifting meteorites and vehicles still looks a bit slow"

### 2.1 Timeline of the run (C traffic, vehicle 8, s after the press 21:08:20.027)

| t | What |
|---|---|
| +0.074 / +0.087 | "stops to cast", facing bundle (throw skill in the slot) |
| +0.180 | pickup 0x8D (InitObjectPickup) on AGL and the van (`liftable_face_lead` 0.13 after the facing) |
| +0.647 | graph event CarPickup (0.45 s = Car_Pickup's start frame, the whole bend; `liftable_car_pickup_at` "graph") |
| +0.71 .. +1.25 | toss: 11 states over **0.65 s** (`liftable_toss_seconds`) |
| +1.302 | 0x20F8 "kept ready" (Super Strength's 0x100000BB, **posted 1.2 s after the pickup**: `raise_event_follow`) |
| +1.316 | catch (DisableHit, PickupObject); +1.47 indicator 0x2180 / 0x20F9 |

### 2.2 What the data says (C, script `0x34000161`, `0x34000177`)

- `0x34000161` S7 (the toss, entered on cast signal 3 = Car_Pickup's grab hook): **RaiseEvent 0x100000BB to
  0x34000164** at once, LaunchLobbedMissile (object -> champion + 1.1 m, angle 70, script `0x34000160`), TossTimer
  TossDuration **0.3**. T6 S7 -> S8 on TossTimer, T5 S8 -> S9 on CatchTimer (CatchDuration 0.35), and **T8 S7, S8 -> S9
  on 0x10000002**, which `0x34000160` raises on its creator when the lob ends (`0x10000035`). So the catch comes when the
  lob lands; 0.65 s is only the timers' upper bound.
- `0x34000177` S3 (the rock's grab, signal 3): RaiseEvent 0x100000BB to 0x34000164 too.
- ics posted 0x100000BB 1.2 s after the pickup for both kinds (`raise_event_follow`), and since fase3-in the throw
  indicator waits for the resulting 0x20F8: 0.7 s (vehicle) / 1.0 s (rock) of added wait.

### 2.3 Fix

- `[ics] liftable_input_back` (true): `Liftables._input_back` posts 0x100000BB to the Super Strength instance at the
  vehicle's toss start and at the rock's grab; `script_nodes._raise_event_node` skips `raise_event_follow` for a
  liftable target. false = the fixed 1.2 s.
- `[ics] liftable_toss_seconds` 0.3 (TossDuration; the lob's landing ends S7 at once) and `liftable_toss_steps` 9; the
  catch stays no earlier than the graph's Hold + 0.05 s: AGL catch 1.1125 -> **0.875 s**, ready 1.2125 -> **0.975 s**.
- Unchanged and data-backed: CarPickup at 0.45 s (an earlier one cuts the bend, fase3-im), the rock's grab 0.22 / hold
  0.30 (its clip), `liftable_face_lead` 0.13 (the client applies a movement state 0.1 s late).

## 3. "The throw also looks slow, like frame by frame"

### 3.1 What went (C traffic + server code)

- Vehicle 8: release 21:08:26.713, landing 27.747: a 0.8 s flight (`liftable_throw_min_seconds`) + 0.15 s
  (`liftable_land_delay`); the flight states are unlabelled bundles, each with a newer teleport sequence
  (`liftable_throw_snap`), positions precomputed for 0.05 s steps.
- `Match.later` fires on the 30 Hz tick, so the 0.05 s steps went 33 / 66 ms apart, each stamped with its send time
  while its position was the precomputed one; every state was a hard snap (`0x5C9E90`, velocity reset) with only the
  horizontal speed in the velocity: the client drew a stair of jumps (P: the "frame by frame").
- LaunchLobbedMissile has no client half (node `0x10000154`, client execute = the empty `0xab4d80`, C): the original
  server sent the arc as states too.

### 3.2 The velocity the client can replay (C)

- 0xB0 motion bits, reader `0x57E530` order: 4 heading f32, 0x20 speed f32, **0x40 f32** (+0x4C), 8 facing yaw s16,
  0x400 facing pitch, 0x4000 roll, 0x800 / 0x1000 sequences. `0x57DA90`: with bits 4 | 0x20 | 0x40 the state's
  velocity = (cos h cos p, sin h cos p, sin p) * speed; `0x552130` dead-reckons `pos + v * dt` from the newest state
  <= now - 0.1 s.

### 3.3 Fix

- `messages.movement_block(..., vel_pitch=)`: motion bit 0x40 + f32 after the speed (None = the old bytes);
  `World.tilt` / `motion_key` carry `ent.vel_pitch`.
- `Liftables._fly_timed` (`[ics] liftable_throw_velocity` = ["vehicle", "rock"]): each state is the curve at its own
  send time (f = match time since the launch / flight), heading toward the point, speed = |v| and vel_pitch = the 3D
  tangent's pitch, one per `liftable_throw_step_seconds` 0.033 (every tick); the last state stops it. Snapped as before
  (`liftable_throw_snap` now ["vehicle", "rock"]): a snap lands where the dead-reckoned replay already is.
- `liftable_throw_min_seconds` vehicle 0.8 -> 0.5 (MissileVelocity 15 m/s: 0.6 s at the 9 m range).
- P: between snaps the replay module steers the body (`0x5C9FE0`, a 3D displacement); whether the vertical part is
  kept there is still O (`throw-padlock-coredeath.md` 1.3). With the velocity it no longer matters much: each snap is on
  the curve at the client's own replay time.

## 4. "When the vehicles impact they disappear and you hear the explosion"

### 4.1 diag --destruction (C)

| t | Line |
|---|---|
| 21:08:27 | 0x8B reset iid 0x139 -> intact pieces built pieces=5 (the landing rebuild) |
| 21:08:27 | 0x8A impulse radius 0x40800000 (4.0) magnitude 0x41200000 (10.0) level 3 -> **piece bodies count 0, entities count 0** |
| 21:08:27 | the second 0x8A: the same, 0 / 0 |
| 21:10:18 / 19 | vehicle 6: the same (0x8B rebuild, both impulses 0 / 0) |

`0x631FA0` (applied) and `0x62BC00` (piece damage) never hit: nothing broke. Two minions and Catwoman stood inside
the 4 m (server: "vehicle 8 lands: mid melee 2 t2 w4, AI: Catwoman, ...").

### 4.2 Vfx_OnExplode deletes the vehicle (C code + data)

- Vehicle table `0x1D00034B`, key `Vfx_OnExplode 0x10000079`: props {0x211, 0x7E6}; one action **type 0x29** (fields
  0, `0x10000002`, 1) with a child **type 0x28**.
- Type 0x29 (factory vtable `0x15CF374`, create `0x662810` -> object `0x52C290`, vtable `0x15B1630`, execute
  **`0x530FA0`**): builds the list of the entity's destruction pieces (`0x4F5C20(0x801)` from the run, or the
  destruction component (`entity+0x58`) vfunc +0x5C with its field) and runs its children once per piece.
- Type 0x28 (execute **`0x65C7D0`**): `(entity+0x58)->vfunc+0x4C(ctx+0x58)`. CDestructionComponent (ctor `0x62F800`,
  vtable `0x15CA670`): +0x4C = **`0x62ED00`** (find the active piece with that id) -> **`0x62EBF0`**: destroys the
  piece's render instance (`+0x15C`, `0x7E34A0`) and physics body (`+0x188`, `0x5C5E90`), moves it to the removed list
  (+0x20) and out of the active list (+0x10 / +0x18); when none is left and record+0x70 is set, runs that scriptlet
  (`0x57D8B0`; P: the explosion sound / particle the tester hears).
- A destructible vehicle draws only its active pieces (`destructible-vehicles.md` 1). So the landing's Vfx_OnExplode
  (sent in the same millisecond as the landing 0x8B, 43 ms before the first 0x8A) made the van vanish and took the
  piece bodies away before the impulse's sphere query looked for them (the 0 / 0 above). fase3-ih .. fase3-in all sent
  it at the landing (or the last flight state) and every run reported the vehicle "gone" there.
- Also C: `Destructible_IgnoreAOI` sets property `0x8FA`; `0x62FB20` (a 0x10D / 0x138 piece state) clears every piece
  when it is set. ics sends no 0x10D, so it does not matter today.
- The break keys of fase3-in (`Destructible_OnBreak_*_T1`, `Destructible_OnCompletelyDestroyed`, truck table
  `0x1D000612`) are sounds (type 0x2C) and particles (type 0x11, `0x1800050A`-`0x1800050E`, `0x180002AA`) at the
  pieces: they hide nothing.

### 4.3 Fix (C cause, P result)

- `[ics] liftable_land_scriptlets` vehicle = ["Destructible_IgnoreAOI"] (Vfx_OnExplode out); `[ics]
  liftable_land_explode` (kind -> s after the landing, {} = never) sends it later if wanted (`Liftables._explode_late`).
- The landing keeps: 0x8B on the landing frame, the 0x8A impulse 0.05 s later and again 0.15 s after it, the break keys
  (fire / smoke particles and sounds), `_HFSM_DestroyEntityAction_Optional`, removal at 10.5 s. Expected: the van stays
  as a wreck with the break effects, and if the impulse now finds the bodies it breaks the pieces into debris.
- O: whether the impulse finds the bodies now (no Vfx_OnExplode in between). `tools/diag.py --destruction` adds
  `0x62ED00` / `0x62EBF0` (piece removed) to the 0x8A / scan / hit / piece-damage lines. If the scans still count 0,
  the next suspect is the impulse position (Position -> world `0x5C28A0`, the vehicle's cell 0xFB) or the bodies'
  collision filter (`0x5CEA30` builds the query with filter byte 8).

## 5. Checks

`tests/test_match.py` `aura_lift_throw_break`: the motion-pitch bytes; each rock's override 5 + team 3 -> 0, off at the
grab; the base's Vfx_Active_State1; 0x100000BB at the rock's grab and at the vehicle's toss, once; catch 0.875 / ready
0.975; an order during the lift kept and thrown at ready; per-tick flight states with the velocity pitched up then down
(vehicle) / down (rock); no Vfx_OnExplode at the landing (impulse and break keys still), `liftable_land_explode` sends
it late. Older checks adjusted: the catch bound by Hold + 0.05, the landing without Vfx_OnExplode.

## 6. Open

- O: the orb children's tint (1.2); the base states' meaning.
- O: the debris (4.3): does 0x8A break pieces once they are not deleted first?
- P: the 0x5C9FE0 vertical (3.3).
