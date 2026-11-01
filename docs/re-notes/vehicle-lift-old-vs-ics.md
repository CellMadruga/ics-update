# The vehicle lift in the old server (Tutorial 1) against ics (2026-10-30)

Question (user, 2026-10-30): "in the old project we had already fixed the whole vehicle-lift animation; is that true
and what is different?" The old, hand-written server is `icserver/finale.py` (Tutorial 1 part 3, Gaslight Batman lifts
the street wagon); the new one is `ics/match/liftables.py` (Crime Alley, any champion with Super Strength), which the
tester still calls "robotic, in parts, as if animations were skipped" (reports 2026-10-30 11:23 and 12:05).
Tags: **C** confirmed (code / data / headless message stream), **P** probable, **O** open.

Method: both servers run headless and every message they send for one lift -> 1 s walk -> throw -> landing was logged
with its simulated time (session scratchpad scripts, nothing kept in the repo):

- old: `icserver.finale.Finale.lift / carry_tick / throw / update` with a stub tutorial (`schedule`, `run_scripts`
  with the session's `champion_defer` 0.06 s, `champion_bundle`, `entity_bundle`, `move_entity`) and the defaults of
  `icserver/config.py` `[tutorial]`. `tests/test_e2e.py` no longer reaches the finale (it fails at the tutorial start
  on this build's timings), so it was not used.
- ics: `tests/test_match.py`'s `make` / `run` on Crime Alley, Gaslight Batman with Super Strength in slot 7, the
  shipped `[ics]` defaults (`liftable_face_lead` 0.13 included), 30 Hz ticks.

## 1. Was the old lift complete? (C changelog, C code)

No, but nobody complained about it after its last fixes. Its history (docs/CHANGELOG.md):

- fase3-ed / fase3-eg: InitObjectPickup + PickupObject (then only PickupObject), the car rising over 0.8 s.
- fase3-et (17:36): back to InitObjectPickup, PickupObject 0.5 s later; the car straight up to `carry_height`.
- fase3-eu (19:21): Batman "bent down and stayed crouched": CarPickup `0x10000246` raised through
  `_HFSM_BehaviorRaiseEventAction` 0.05 s after PickupObject; `lift_lock`.
- fase3-ev (20:22): the carried car got Batman's speed and heading in every movement update (it trailed behind).
- fase3-fh / fl / fm: slower carry walk (3.0 m/s, "he slid"), throw lock ("kept walking after a throw"), car centred
  and lower ("hangs to one side and above his hands"), a 4 m arc and half a turn of tumble ("flew in a straight line").
- After fase3-fm (2026-10-16) the changelog has no further lift / throw report before the move to ics (fase3-fo).

What it never had: the toss of the car onto the champion, the Car_Catch clip, the throw clip's real timing, any
destruction of the car (it just vanished `wreck_seconds` after an Vfx_OnCollision 0x5 / Vfx_OnExplode). The car
popped onto the head in one jump (> 2 m: the client snaps it) while Batman was still bent, and the PickupObject it
sent 0.5 s into the lift was dropped by the graph (Pickup_Start has no PickupCar transition, `vehicle-lift-and-
position.md` 2). So "fixed" = accepted by the tester at the time, not complete.

## 2. The two message streams (C, headless)

Times in s after the lift order / the throw order. Champion = AGL / Gaslight Batman, car = the lifted vehicle.

### 2.1 Lift

| t | old (`icserver/finale.py`) | ics (`liftables.py`, defaults) |
|---|---|---|
| 0 | champion full bundle (stop, face the car) | champion full bundle (stop, face, throw sub-skill already in the slot table) |
| 0.11 / 0.13 | 0x8D InitObjectPickup `0x100007A2` on the champion only; var 0x108 = car **and the 2nd-IID field (mask 0x20) = car** | 0x8D InitObjectPickup on the champion **and on the car** (target var 0x108 only, no 2nd IID) |
| 0.61 | 0x8D PickupObject `0x100007A1` on the champion (graph PickupCar: dropped in Pickup_Start) | - |
| 0.60 | - | CarPickup (`0x100001E3` + 0x780 = `0x10000246`), at the graph's Car_Pickup start frame (0.45 s after the init) |
| 0.60 | - | toss start: VFX_CBT_Hit_Shared `0x10000223` on the car, Super Strength's input back (0x100000BB, moves allowed again) |
| 0.65-0.70 | car: ONE bundle 2.1 m over the champion (a > 2 m jump: snapped), speed 0 | car: 13 toss states, one per tick, each a teleport snap with the lob's 3D velocity (heading, speed, motion pitch) |
| 0.71 | CarPickup (`0x100001E3` + 0x780) -> Car_Pickup -> Hold (no catch) | - |
| 0.73 | champion **full bundle** with the throw skill in slot F (mid Car_Pickup) | - |
| 1.03 | - | catch: CbtState_DisableHit (`0x100001E3` + `0x100003AF`), car state on the hold point (snap), PickupObject on the champion and the car (graph PickupCar -> Car_Catch) |
| 1.10 | - | **0x8B: the car's pieces cleared and rebuilt "over the head"** (removed by default from 2026-10-30, 3.1) |
| 1.13 | - | ready: car state (snap), throw indicator after the slot's 0x20F8 |

On the vehicle, InitObjectPickup / PickupObject / ThrowObject are each ONE type-0x2C action (a sound: `0x4B5922BC`,
`0x4B5922BC`, `0xA48BF2F5`) in the shared vehicle table `0x1D00034B` (C, table bytes in pack `0xA000009A`); they do not
move or attach anything.

### 2.2 Carry (walking)

| | old | ics |
|---|---|---|
| champion | full bundle every movement tick (`Session._move_tick`) | full bundle every tick in `object_update_mode` "bundle" (`Session` tick, not held by the carry) |
| car | a bundle in the SAME tick, right after the champion's, with his speed and heading; never a newer teleport sequence (steered) | a state every `liftable_carry_resend` 0.05 s or on a course change, from `Liftables.tick` (before `World.tick` moves the champion, with a one-tick lead), each one a **teleport snap** (`liftable_carry_snap`) |
| height | 2.1 m, held (tester 12:18: "above his hands") | 2.5 m (0x34000161's AttachmentOffset) |

### 2.3 Throw and landing

| t | old | ics |
|---|---|---|
| 0 | champion full bundle (stop, face the target) | champion movement state only (68 B, `liftable_throw_face_motion_bundle`); car state turned and stopped on the hold point (snap) |
| 0.07 / 0.13 | ThrowObject `0x100007A0` on the champion (var 0x108 + 2nd IID = car) | ThrowObject on the champion and the car |
| 0.20 / 0.33 | the car leaves: 10 fixed states over dist / 16 m/s, speed 16 along a tumbling heading, no snap, 4 m arc | launch: Vfx_OnThrown on the car, one state per tick (snap, 3D velocity, facing pitch), 0.5 s minimum flight, 3 m arc; EnableHit raised on the champion ~0.03 s later |
| landing | Vfx_OnCollision `0x5`, the dust prop, Vfx_OnExplode 0.2 s later, removal after `wreck_seconds` | 0x8B on the landing frame, Destructible_IgnoreAOI, 0x8A x2, the Optional destroy action, the break keys (+0.2), Vfx_OnExplode (+0.75), removal at 10.5 s |
| 0.96 / 0.95 | `_Combat_GoToLocomotion` | `_Combat_GoToLocomotion` |
| 0.96 / 1.25 | champion full bundle (Super Strength back in F) | champion full bundle (slot table back, `liftable_slot_restore_delay` 0.9 after the clip's end) |

## 3. The differences that can make ics look "robotic"

### 3.1 The catch's 0x8B rebuild (C code, P visible) - changed

`Liftables._catch` sent 0x8B to the vehicle 0.05 s after the catch, whether or not it was attached. 0x8B's handler
`0x631050` clears the destruction pieces and builds them again (`liftables-camps-animations.md` 1.2, C). That is needed
only for an ATTACHED object (its pieces must move under the champion's render node, `0x630FC0`'s contained branch); a
vehicle carried by its own states (`liftable_attach_kinds` [] since 2026-10-28 13:52) moves its pieces with its frame
(render vt+0x64, `vehicles-carry-collision.md` 1.4, C). So the rebuild only re-made the vehicle in mid-air while the
champion's Car_Catch clip played. The old server never sent one. The launch's twin was already dropped for the same
reason (`liftable_detach_rebuild_attached_only`, fase3-im).

Change: `[ics] liftable_attach_rebuild_attached_only` (true): the catch's / grab's 0x8B only for an attached object;
false = as before. The landing's own rebuild (`liftable_land_rebuild`) is untouched.

### 3.2 Snapped object states every tick (C code, P visible) - not changed

Old: the carried car was steered (no newer teleport sequence), sent in the same tick as the champion with his
velocity, so both were replayed the same way. ics: every toss, carry and flight state is a teleport snap
(`liftable_toss_velocity`, `liftable_carry_snap`, `liftable_throw_snap`), at 20-30 Hz. A snap places the body exactly
and zeroes its velocity for one physics step (`0x60A270(.., 1)`, `client-movement.md`), while the champion is steered:
a 20-30 Hz judder of the object against a smooth champion is the most likely "robotic / frame by frame" (the tester's
words since the snaps came in: fase3-ij 15:30 flight snap, 21:10 "the throw looks frame by frame", 11:23 "robotic").
The snaps were added because steering seemed to drop the height of an object held off the ground (P,
`throw-padlock-coredeath.md` 1.3); the old car, steered at 2.1 m, kept its height (tester 12:18), but it was a carrier
class `0x4A000AAB`, not a template vehicle with pieces, so that is not proof for ics. Not changed without a test in
the game. A/B in `config.toml` (no code needed):

```toml
[ics]
liftable_carry_snap = []        # carry steered like the old server (the toss / flight keep their snaps)
liftable_carry_resend = 0.033   # one carry state per tick while walking
```

If the vehicle then sinks while carried, the snaps are needed; if it walks smoothly, try `liftable_throw_snap = ["rock"]`
for the flight (it keeps its 3D velocity).

### 3.3 The catch timing (C data, P original) - not changed

ics catches at max(toss + `liftable_toss_seconds` 0.3, Hold + 0.05) = 1.03 s, so Car_Catch (entered at its 0.122 s
frame) starts 0.05 s into Hold, inside Hold's blend: Car_Pickup -> Hold -> Car_Catch -> Hold in ~0.5 s. 0x34000161's
timers allow up to TossDuration 0.3 + CatchDuration 0.35 = 0.65 s after the toss (the 21:10 report "lifting a bit slow"
moved it to 0.3). `liftable_toss_seconds = 0.65` gives the catch ~0.29 s into Hold (the original's upper bound). O: the
lob's real flight time (S7 / S8 -> S9 on 0x10000002, the lob's landing).

### 3.4 Smaller differences (C, effect O)

- 2nd-IID field: the old server put the car in the 0x8D's mask-0x20 field (`scriptlet_entry(second=...)`, read into
  the run context +0x28 by `0x6837E0`) as well as var 0x108; ics sends var 0x108 only. Who reads +0x28 is O.
- ics raises CbtState_DisableHit / EnableHit on the champion at the catch / launch; AGL's graph has no transition on
  them (C, `data/skill_graphs.json`), so they should be inert.
- ics sends the three pickup / throw keys to the vehicle too (sounds only, 2.1).
- ics allows moves from the toss on (Super Strength's input back, as 0x34000161 S7); the old server locked Batman for
  `lift_lock` 1.35 s. A move during the toss / catch walks the champion in the pickup pose (P).
- ics's lift is longer (CarPickup at the graph's 0.45 s, the whole bend) and the throw keys wait `liftable_face_lead`
  0.13 s (the turn is applied 0.1 s after its state); the old server's champion keys went `champion_defer` 0.06 s after
  its bundle.

## 4. Tests

`tests/test_match.py`: the liftable block's check now expects no "rebuild pieces, over the head" at the lift; the
`lift_throw_wreck_1205` switch-back lift checks it again with `liftable_attach_rebuild_attached_only` false. test_match
524/524, test_meltdown 50/50, test_ics 40/40 (ICS_TEST_PORT 21530).

## 5. Next in the game

1. The default build (3.1): watch the catch (the moment the vehicle lands in the hands).
2. The A/B of 3.2 (`liftable_carry_snap = []`, `liftable_carry_resend = 0.033`) for the walk with the vehicle.
3. If the catch still looks hurried: `liftable_toss_seconds = 0.65` (3.3).
