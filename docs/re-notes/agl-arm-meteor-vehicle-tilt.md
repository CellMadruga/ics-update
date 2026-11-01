# AGL's Grab arm, the held meteorite and the thrown vehicle's tilt (2026-10-29)

Tester report 2026-10-29 17:45 (Crime Alley v AI, AGL, run 17:32-17:42; `logs/server.log`, `logs/traffic.log`,
`logs/diag.log` from `diag.py --fog --brazo --ring`): (1) the Grab arm line; (2) "the meteorite must go higher, like in
the palm of AGL's hand; usually it has an animation spinning in the palm, and the throw animation"; (3) "the vehicle
falls lying flat, not as the correct animation where the front tilts down to hit and explode". Sources: the logs, pack
0xA0000150 (AGL's clips), 0xA0000151 (AGL `.entity` 0x2D0009A9), 0xA0000162 (rock table 0x1D0004FB), the exe
(capstone, VA, base 0x400000), `re-work/decomp/c/00740000.c`. Tags: **C** confirmed, **P** probable, **O** open.
Follows `grab-beam.md`, `agl-grab-arm.md`, `agl-qer-lift.md`, `throw-padlock-coredeath.md`.

## 1. Grab arm: the beam resolves missile -> AGL and draws (C)

- The six Grab casts of the run created missiles with IIDs 0x136, 0x149, 0x169, 0x16F, 0x117, 0x143 (traffic: the
  0x4 header of "missile 0x40000485 created" at 17:34:07.526, 17:35:59.633, 17:37:10.499, 17:37:32.970, 17:39:03.938,
  17:41:20.200). Each has its `ARM:` group in the diag with **src = that missile, dst = AGL 0x...02**, every check ok
  and **DRAWN** (diag lines 7320, 25372, 30739, 32462, 36133, 37299). So the beam's source end is the missile, not
  AGL, and the draw pass (0x74CC05) is reached (C).
- The `src=dst=0x200000000000002` groups (17:33:54, 17:38:50 with `active(ok=0x0)` on both ends, 17:39:00 drawn) come
  6-8 s after each load complete (17:33:47.5 / 17:38:42), with no Grab cast and no missile: a type 2 action run **on
  AGL** whose target 0x100004E2 (creator) is AGL itself (GetCreator = the owner for a champion, full-combat-skills.md).
  AGL's model is not "active" (0x747DD0) while the intro hides him. P: AGL's passive Vfx_Atm_Glt_Rads_Active
  0x10000887 (sent at 17:33:40.914 / 17:38:36.779); in any case it is not the Grab beam.
- `model(ok=0x0)` on a Grab missile (17:34:08, 17:37:11, 17:37:33, 17:39:04) follows the missile's 0x3 or precedes its
  first frame (the render model not built yet / gone), C timing from traffic; the beam ends with the missile's run
  (grab-beam.md 2.4).
- So no server cause was found for "both ends = AGL": **no code change for the arm.** If the tester still sees no line
  from the flying hand to AGL, what is left is the particle emission itself (`0x7480A0`, C): it spawns only when the
  drawn segment is > 0.1 m, beam+0x44 == 0, beam+0x40 > 0.0002, the particle record is loaded
  (`[[beam+0x298]+4]+0xF0 != 0` at 0x7481A9 and `**([..]+0xE8) != 0` at 0x7481B6, else jump 0x74845F) and the count
  `round(rate * dt * length / beam+0xBC)` at 0x748226 is > 0 (spawn loop 0x748231 -> `0x7423F0` at 0x748313). O: a
  diag probe at 0x748231 (count in eax, beam in esi, source IID q[esi+68]) during a Grab would close it.

## 2. The held meteorite

### 2.1 The rock's own scriptlets (C, table 0x1D0004FB, pack 0xA0000162 @~0x97C2E4)

- Vfx_PickUp 0x1000023A = one type 0x17 action on Vfx_Active 0x100000EB with flag 1 (P: stop): the floating rock's idle
  effect stops when it is picked up. Vfx_Active, Fade_In / Fade_Out, StateChange_Hide are type 8 render effects
  (overlay / fade; jungle-camps-spawn.md 1). No entry of the table turns or moves the rock (P: no type 8 field is a
  rotation; none of the keys names a spin).
- SuperStrength_Rubble_Active 0x10000775 (0x34000177 S3 StartScriptlet on the champion, "loop while held") is in none
  of AGL's tables (grab-arm-carry.md 2.2, C): the client drops it for AGL. So whatever spun the rock in the original
  for AGL is not a scriptlet ics can send (P: the hand attachment following the hold clip; O).

### 2.2 Where AGL's palm is (C data, P clip names)

- AttachEntity's parent point **0x100000B0** in AGL's `.entity` (pack 0xA0000151 @0x11B6BC): `key key | bone 0x1F |
  position (0, 0, 0) | scale 1 | quaternion (0.717, 0.142, -0.662, -0.163)` -> bone 31
  `chr_atomic_green_lantern_main_RWeapon` (RWrist < RElbow < RShoulder < RArm_Socket ...) (C).
- Forward kinematics of that bone over AGL's 73 clips (skeleton MainSkeleton, 82 bones; `uesrv/havok*`): the six clips
  0x1A001131-0x1A001136 (one 2.00 s + five 0.83 s = the Hold blend's idle + walk / run set of SM_SuperStrength_Rubble,
  P by count) hold the hand at right 0.5-0.85 m, forward 0.1-1.0 m, **up 2.2-2.6 m** (idle 0x1A001136: (0.73, 0.13,
  2.27)) (C numbers, model frame x = right, y = forward, z = up). The old carry offset (0, 1.4 forward, 1.4 up) put
  the rock ~1 m under the palm.
- The script's AttachmentOffset (0, 1.4, 1.4) is in the attach frame (bone x attach quaternion), which the client
  cannot be sent (vehicles-carry-collision.md 1.2); through that frame it lands 2.4-3.8 m up and ~1.8 m to the
  right in these clips (C arithmetic, P that it is meant this way), so it is not used as such.

### 2.3 Change

- `[ics] liftable_carry_offset` rock **[0.7, 0.4, 2.75]** (right, forward, up): on the palm (hand + ~0.45 m, G: the
  rock's half height). The throw starts from there too (release = hold point + 0.5 m forward). `[0.0, 1.4, 1.4]` =
  fase3-ik.
- `[ics] liftable_hold_spin` rock **[180 deg/s, 0.1 s]**: while held the rock turns about its vertical axis through
  its facing offset (`World.tilt` -> `facing_offset` of the 0xB0 block; heading and velocity untouched), one movement
  state per 0.1 s; it keeps turning in its throw. P: a server stand-in for the spin the tester remembers (2.1). `{}` =
  none.
- Throw clip: unchanged; the throw key SuperStrength_ThrowRubble 0x100004CC (graph Rubble_Throw) goes 0.13 s after
  the facing bundle (17:35:21.145 -> .256, C traffic), as fase3-ij.

## 3. The thrown vehicle's tilt

### 3.1 What the movement state can carry (C, client-movement.md 1.2 / movement-collision-fog-map.md 1.1)

Motion bytes `u8 m | (m & 0x80) u8`: the reader (0x57E530) takes, after the s16 facing yaw (bit 8), **bit 0x400 s16
facing pitch** and **bit 0x4000 s16 roll** (rad * 10000), then the sequence bytes. 0x60AFA0 builds the orientation
from (yaw, pitch, roll) * 0.0001 (0xAF2D00). ics sent 0xAC 0x18 (heading, speed, yaw, seq A / B): pitch 0 = flat.
P: no node of 0x3400015F / 0x34000161 turns the vehicle (their decodes in crime-alley-props.md A.3 list only
LaunchLobbedMissile and the landing keys; the trees were not re-read for this note).

### 3.2 Change

- `ics/messages.py` `movement_block(..., pitch=None, roll=None)`: the second motion byte gets 0x04 / 0x40 and the s16
  values follow the facing yaw; None = the bytes as before (checked: 46 -> 48 bytes, `ac 1c ... 2cd6 90e8`).
  `World.tilt(ent)` passes an entity's `pitch` / `roll` / `facing_offset` to every movement state (bundle, motion
  state, delta, resync); `motion_key` includes them.
- `Liftables._fly`: each flight state of a vehicle carries the curve's slope as pitch
  (`atan2(dz/df, dist)`, nose up at the launch, down at the end, clamped to `max`) and the last state `land`.
  `[ics] liftable_throw_pitch` vehicle **{"sign": 1.0, "max": 0.9, "land": -0.6}**; `{}` = flat. The states already
  snap (`liftable_throw_snap`), so each pitch is applied as sent.

### 3.3 Open

- O: the sign of the client's pitch (P: positive = nose up, as for velocity `sin p`); if the tester sees the nose rise
  at the landing, set `sign = -1.0`. O: the vehicle's model forward axis vs its heading (it is carried and thrown with
  the champion's heading; a vehicle carried sideways would roll instead of pitch: then use `roll`).
- O: the original's exact landing angle (no client data names one); -0.6 rad (~34 deg) is G.

## 4. What the tester should see

- Grab: as before (the beam is drawn by the client: section 1); if the arm line is still missing, run
  `python tools\diag.py --brazo` once more after the 0x748231 probe is added (O).
- Meteorite: held on AGL's raised palm (~2.75 m up, a little right and forward), turning slowly; it leaves from there.
- Vehicle: thrown nose up, tilting forward along the arc, lands nose-first, then the explosion.

## 5. Validation

`tests/test_match.py` 349/349, `tests/test_meltdown.py` 50/50, `tests/test_ics.py` 40/40 (ICS_TEST_PORT=21400),
`tests/test_catalog.py` OK.
