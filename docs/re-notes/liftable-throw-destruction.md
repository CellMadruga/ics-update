# Vehicle lift / throw "skipping animations" and the missing destruction (2026-10-29, fase3-im)

Tester report 2026-10-29 18:31 (Crime Alley v AI, Atomic Green Lantern; `logs/server.log`, `logs/traffic.log` of
the 18:31 run; vehicle 6 lifted 18:33:31.59 / thrown 18:33:34.34, vehicle 5 lifted 18:37:12.38 / thrown 18:37:15.00):
"picking up and throwing the vehicle looks a bit odd, as if it skipped animations, and the vehicle's destruction
animation is not generated". Tags: **C** confirmed (data / code / log read), **P** probable, **O** open. Exe
`InfiniteCrisis.exe`, base 0x400000, decomp `re-work/decomp/c`. Builds on `vehicle-lift-and-position.md`,
`throw-padlock-coredeath.md`, `agl-arm-meteor-vehicle-tilt.md`, `destructible-vehicles.md`.

## 0. What was sent (C traffic, vehicle 6)

| t (s after the lift) | Message |
|---|---|
| -0.007 | AGL facing bundle with the throw skill (full, 1433 bytes) |
| +0.073 | InitObjectPickup 0x100007A2 on AGL and on the vehicle |
| +0.152 | graph event CarPickup 0x10000246 (`liftable_car_pickup_at` 0.05 + face lead 0.08) |
| +0.15 .. +0.80 | toss: 11 states, catch (DisableHit, PickupObject on both, 0x8B "over the head"), indicator 0x2180 / 0x20F9 |
| throw +0.00 | **"AGL throws vehicle 6" = a FULL champion bundle (1432 bytes)** during the Hold state; 0x217F / 0x20F9 1 |
| throw +0.13 | ThrowObject 0x100007A0 on AGL and the vehicle |
| throw +0.33 | `thrown` keys, **0x8B "detached" (pieces rebuilt in mid-air at the launch frame)** |
| throw +0.36 / +0.99 / +1.27 | EnableHit, _Combat_GoToLocomotion, Super Strength slot table (full bundle) + cooldown |
| land +0.00 | Vfx_OnExplode, Destructible_IgnoreAOI, 0x8A sphere (4.0 m, 10, level 3); 0x8A again +0.15 |
| land +10.5 | 0x3 remove (no DestroyEntity action ever) |

## 1. The lift: CarPickup cut the bend (C graph data)

AGL's `SM_SuperStrength_Car` (data/skill_graphs.json, `chr_atomic_green_lantern_behavior.hkb` machine 8):

| State | Clip | Out |
|---|---|---|
| 4 Pickup_Start (start) | car_pickup.hkx from 0, speed 1.0, cropEnd 0.783 of a 1.233 s clip = **plays 0 -> 0.45 and holds** | SuperStrength_CarPickup -> 1, **Instant** |
| 1 Car_Pickup | the same clip **from 0.45**, speed 0.8; a_SkillHook 3 @0.46, state_to_state @0.75 | -> 0 Hold |
| 0 Hold | car_run_fwd_50 blend | PickupCar -> 3 Catch |
| 3 Car_Catch | car_catch.hkx | -> 0 |
| 2 Car_Throw (local wildcard SuperStrength_ThrowCar) | car_throw.hkx: MissileFire 5 @0.2, SkillEnd 2 @0.22, to locomotion at end - 0.1 | |

Pickup_Start's crop ends exactly on Car_Pickup's start frame (C: 1.233 - 0.783 = 0.45; AGL's clip 0x1A00082D is the
only 1.233 s clip of pack 0xA0000150's 73). With CarPickup at 0.05 s the Instant transition jumps the clip from 0.05
to 0.45 s: the bend-and-grab is skipped (the "skip" of the lift). The original's own CarPickup time is P (Vfx_Event9's
type-0x23 group at 0.05 s, `vehicle-lift-and-position.md` 2.3); the clip layout is C and only plays whole when
CarPickup arrives at its end.

Fix: `[ics] liftable_car_pickup_at = "graph"` (Car_Pickup's start frame from the champion's own graph: AGL / Gaslight
Batman 0.45, chr_batman 0.4103). Timeline AGL: CarPickup 0.45, toss 0.4625, catch 1.1125, ready 1.2125 (Super
Strength's input comes back with `raise_event_follow` 0x100000BB at 1.2 s). 0.05 = fase3-if .. fase3-il.

## 2. The throw: a full champion bundle inside the Hold state (C traffic, P effect)

The throw's turn toward the point went through `World.update(force=True)`; in delta mode `World.delta` returns False
when an array / table property changed since the last full bundle (`delta_complex_as_bundle`), and a slot table had
changed during the carry, so the turn went as a full 0x4 (1432 bytes at 18:33:34.340), 0.13 s before ThrowObject.
A full bundle replaces the champion's 0x7D2 tables and drops what its running scriptlets hold
(`liftables-camps-animations.md` 2.2, the reason the carry already holds every other champion bundle).

Fix: `Liftables._face`: in delta mode the turn is the movement state alone (`World.motion_state`, the motion key
recorded as `World.delta` does); the changed tables go with the slot restore after the throw clip
(`liftable_slot_restore_delay`). `[ics] liftable_throw_face_motion_only` (false = as before). **Delta mode only**: the
live default `object_update_mode` is "bundle" (fase3-ih, 2026-10-29 10:28), where every champion update is a full
bundle and stays so; `object-update-bundles.md` 6.1 (C) also found that a bundle drops no scriptlet run, so this
part is the weakest (P) of the three.

## 3. The destruction: the pieces were never where the impulse looked (C code, P runtime)

- 0x8A (`0x632590` -> **`0x632370`**): `0x630E80` makes the impulse object (magnitude / level at +0x48 / +0x4C,
  source = the local player's IID), **`0x631C50(position, radius)`** runs a physics sphere query (`0x5CEA30`) and
  collects (`0x631B00` piece bodies, `0x631940` entities with a destruction component and a breakable piece, def
  +0x46C); only when something was found does **`0x631FA0`** apply it: per hit entity the destruction component gets the
  key / FX (+0x78 / +0x7C) and `0x62F290` -> `0x62BEF0` -> `0x62BC00` subtracts the magnitude from each piece's
  health (+0x44) and breaks it at <= 0 (the client then runs the piece's break scriptlets: the vehicle tables'
  Destructible_OnBreak_*_T1 / Destructible_OnCompletelyDestroyed). So the impulse breaks only what is inside its sphere
  at the landing point (C).
- The piece bodies of a mobile destructible are made by 0x8B (`0x631050` -> `0x630FC0` -> `0x62DBA0`) **at the
  entity's frame at that moment** (C, `destructible-vehicles.md` 3); nothing in the component's per-frame update
  (`0x6305A0` -> `0x62E660`) moves them (C read; P that nothing else does). The last 0x8B was at the launch (mid-air,
  at the hand, or 0.05 s after the catch over the head), up to 9 m from the landing.
- The launch's 0x8B "detached" (`liftable_detach_rebuild`) exists to bring the pieces out of the champion's
  containment; since fase3-if the vehicle is carried by its own states (`liftable_attach_kinds` = []), so it only
  re-made the pieces in mid-air (also the 1.5 "vanishes mid-flight" candidate of `throw-padlock-coredeath.md`).

Fix: `[ics] liftable_land_rebuild = ["vehicle"]`: at the landing 0x8B first (pieces and bodies on the landing frame),
then the landing keys, and the 0x8A `liftable_land_impulse.after_rebuild` (0.05 s) later (and its "again" 0.15 s after
that). `[ics] liftable_detach_rebuild_attached_only`: the launch's 0x8B only for an object that rode the containment.

## 4. DestroyEntity's actions were never played (C script / data)

- `0x3400015F` S4 (after DestructionDelayDuration 0.15 s): DestructionImpulse again and **DestroyEntity(SELF)[10.5,
  1]**. Node 0x10000010's client execute plays **`_HFSM_DestroyEntityAction` 0x100001E0 and
  `_HFSM_DestroyEntityAction_Optional` 0x10001128** on the object, then removes it after the delay
  (`script-nodes-names.md`, C).
- The vehicles' tables (C, `Data.scriptlets`): truck 0x4000081B = 0x1D00067A, 0x1D000612, **0x1D00034B**, 0x1D000111;
  SUV 0x4000045D = 0x1D00067A, 0x1D0001FD, 0x1D00034B, 0x1D000111. Only **0x1D00034B** (the Super Strength vehicle
  table, with Vfx_OnExplode / SuperStrength_*) holds `_HFSM_DestroyEntityAction_Optional`; none holds
  `_HFSM_DestroyEntityAction`. Its entry (pack 0xA000009A, just before 0x100007A2's): one action of type 0x1F with
  (0x10000623, 0x50000623) (P: it clears 0x10000623, the vehicle's fog-occluder flag, `ca-fog-ring-announcer.md` 1).
- ics's thrown vehicle went at 10.5 s by a bare 0x3; a consumed vehicle got `World.destroy`'s
  `_HFSM_DestroyEntityAction`, which its tables lack (not sent).

Fix: `[ics] liftable_land_destroy_after = {"vehicle": 0.15}` and `liftable_destroy_actions` (both keys; a key the
object's tables lack is not sent): at S4 time on the landed vehicle; Consume also plays the Optional one
(`Liftables._consumed`). Removal unchanged (`remove_after` 10.5 s).

## 5. Data ruled out (C)

- The vehicle world states have no 0x5B5 graph (`destructible-vehicles.md` 2: 0x7D2, 0x93D, 0x1000060E, 0x800,
  0x7EB, 0x402, 0x2A4, 0x83C, 0x50F, 0x8C1, 0x1000019D, 0x83E): there is no destruction state to raise; the
  destruction is the pieces breaking.
- The vehicles spawn as their entity classes (`liftable_class_mode` {}), so their tables come from the client's own
  class data; no carrier templates are involved.

## 6. Open

- Tests: `tests/test_match.py` 363/363 (liftable block: CarPickup at the graph's 0.45 s, no launch 0x8B, the landing
  0x8B before the 0x8A, the Optional destroy action at S4, the delta-mode turn), `test_meltdown.py` 50/50,
  `test_ics.py` 40/40.

- O: the throw clip's length (`car_throw.hkx`; the clip table has no names). `_Combat_GoToLocomotion` goes 0.82 s after
  ThrowObject (`super_strength_cast_signals.locomotion_after`); if the clip is longer it is cut there.
- P: that the rebuilt bodies are found by 0x8A's query and break (runtime not traced). A diag probe on `0x631FA0`
  (`[esp+4]+0x34` = hit count) and `0x62BC00` during a throw would settle it.
- P: magnitude 10 is read where `0x62BC00` subtracts an int from the piece health; if the field is the f32 bits the
  damage is huge (breaks every piece), if an int, 10.
- fase3-in (tester report 19:55: still no explosion): the run's traffic shows every landing step of section 3 / 4 in
  order; follow-up in `liftable-carry-throw-press.md` 3 (magnitude is raw f32 bits, C; the impulse's owner cell checks;
  the break keys sent by the server, P).
