# Grab's arm (AGL Q) and Super Strength's carry / throw animation (2026-10-25/26)

Sources: `logs/server.log` + `logs/traffic.log` (sessions 22:07 and 23:08-23:22), the frames already cut from the
19:28 and 22:07 videos (scratchpad `frames/qc1.jpg`, `qc4.jpg`, `video2207/grab3_zoom.jpg`), the packs (via
`ics.gamedata`), AGL's behaviour graph (gmat.py from the animation-matrix work), `InfiniteCrisis.exe` (Ghidra via REA,
VA, base 0x400000). Tags: **C** confirmed (code / data / log read), **P** probable, **G** guess. Scratch scripts:
scratchpad `grab/` (dump.py, findall.py, g1-g3.py, t1-t4.py).

## 1. Grab (0x340002B5, missile 0x40000485 / ws 0x2E000C4C, missile script 0x340002C1)

### 1.1 It is not a regression (C)

- Frames of the 19:28 video at the "clean" hit (19:30:31.4-32.5, `qc4.jpg`) and of the 22:07 video (`grab3_zoom.jpg`)
  show **the same thing**: AGL's construct arm swings forward to its normal length, a green particle streak runs to
  the target, a green puff comes back. No stretched arm in either. test-2026-10-25-1928.md AGL-1's "the arm
  stretches" describes that streak.
- The server's messages for a hit are the same in hw and hx/hy: missile created (134 bytes, identical layout),
  Vfx_Active 0.1-0.2 s later, 0x10000016 (66 bytes) at the hit, 0x10000076 (52 bytes), gone 0.05-0.17 s after the
  hit, then AGL 0x10000331 / Grab_Stop. "stops to cast" / "faces the target" bundles were already sent in hw
  (19:29:36.297, 19:36:40.996). Grab was not cast twice at 19:28 (one `skill order: slot 1` per cast; the doubled
  casts were R / W).
- The creation bundle does carry **0x100004E2 = AGL** (23:10:02.627 hex: `e2 04 00 10 44 e2 | 02 00 00 00 00 00 00 02`
  = 0x0200000000000002, AGL's IID; `0x7D2` = [0x1D000456, 0x1D0003D2]).

### 1.2 What draws the arm (C data, P meaning)

- AGL's own keys (table at pack 0xA0000150 @0x29C3C, 3 keys): **Grab_Start 0x10000899** = group at 0.24 s
  {particle 0x18000754, run ArmFade_RemoveHand 0x10000911}, run Grab_Active; **Grab_Active 0x1000089A** = one empty
  type 5 action (a placeholder run, no visual); **Grab_Stop 0x10000890** = group at 0.06 s {run ArmFade_AddHand
  0x1000093D, particle 0x18000755}, stop Grab_Active. ArmFade_RemoveHand / AddHand (@0x1F2C4 / @0x1F25C) are type 8
  render effects on AGL (hide / show the construct hand). No action of AGL's binds a target, 0x108 or the missile IID.
- The missile's model `.entity 0x2D000A33` is an empty mover: a 1 m box plus attach points (0x10000040, 0x1000004B,
  0x10000058, **0x10000039** ...), no mesh (C, pack 0xA0000150 @0x39B8C4). So the flying "hand" and the arm are
  scriptlet visuals: the missile's **Vfx_Active** (table 0x1D0003D2, @0x29220): group at **0.1 s** with a **type 2**
  action (projectile / beam, exec 0x673280) whose words name attach points `0x10000039` (missile) and `0x1000007C`
  (P: AGL's hand) and whose target field 0x18 is bound to the missile's own **0x100004E2** (= AGL), particle
  0x18000752; plus Vfx_Streak_Right 0x10000617 (type 0x21 random-time pieces, mesh 0x17000F18, green 0xFF0D2900),
  run by the data itself after 0.7 s.
- 0x673280 builds the effect whatever the target (target IID 0 when the binding gives nothing), pushes it into the
  beam list (0x74AE80) and keeps it as an attachment of the run: **the beam lives only as long as the missile's
  Vfx_Active run, i.e. the missile object** (C for the attachment; P that the beam draws missile -> AGL).

### 1.3 Why it is not seen: the missile dies before / as the beam starts (C log + code)

| | t (s after creation) |
|---|---|
| server Vfx_Active (spawned_effects, 0.1 s step) | 0.11 |
| the type 2 inside Vfx_Active starts (its own 0.1 s group) | ~0.21 |
| range end (range 7 m / speed 16 m/s), or hit | 0.27-0.42 |
| missile removed (0x3) | 0.05-0.17 after the hit / range end |

The return leg never flies: `Missile._return` -> `fly_to(owner)`, and `Missile.fly_to` (ics/script_runtime.py)
expires a missile when `flown + dist > max_range * 1.5 + 1`: after 7 m out the 7 m back gives 14 > 11.5, so it
expires after `max(0.05, (7 - 7) / 16)` = **0.05 s**. Log 23:10:03.048 `S3 -> S10` (retract), 03.111 `S6 -> S7`,
`missile gone` (C). Same for a hit (22:11:38.583 hit, .682 gone). So the arm (beam) can exist for 0.1-0.2 s at
most, and never comes back; `tether_retract` (fase3-hy) is a no-op in practice.

### 1.4 Recipe (no code changed here)

1. **Return leg not range-limited** (C): in `Missile.fly_to`, skip the `max_range * 1.5 + 1` expiry when
   `self.returning` (the target is the shooter); the return ends at the shooter (`arrive` -> `end` -> 0x10000005).
   New key `[ics] tether_return_unlimited = true` (2026-10-26, report 23:10: retract died after 0.06 s).
2. **Return speed**: MissileSpeed (stat 30 = 16 m/s) or the script's ReturnVelocity when SetMissileVelocity gave
   one; keep sending the missile's bundles while it returns (they already go every tick as `changed`).
3. **Vfx_Active in the creation tick** (P): play the missile's Vfx_Active right after `missile created` (delay 0;
   `spawned_effects` steps 0.1 s per key: put Vfx_Active first / `spawned_effect_delays = {"Vfx_Active": 0}`), so
   the beam starts ~0.1 s after creation, not 0.21 s.
4. Expected wire for a miss (7 m): t 0 Grab graph event + Grab_Start + Grab_Active (as now); t ~0.28 (cast point)
   missile created + Vfx_Active; ~0.72 at range end 0x10000106 / the script's retract state; ~1.16 back at AGL:
   0x10000005 on the missile script and AGL's (S3 -> S2: graph 0x10000002, Grab_Stop -> AddHand), then the 0x3.
   For a hit: the target dragged with the missile (as now, `tether_drag`), same end at AGL.
5. If the arm still does not show with a 0.9 s missile: **diag** (P): breakpoint after `0x51D590` in 0x673280
   (at `0x67338E`, the resolved target u64 is the local at `ebp-0x28`) on the missile's Vfx_Active run: IID 0 means
   the 0x100004E2 binding does not resolve (then send it again in a 0x6 property change after creation); AGL's IID
   means the beam is built and the problem is its parts / attach points.

Confidence: cause of "never seen / no retract" **C** (log + code); that a 0.9 s missile shows the stretched arm **P**.

## 2. Super Strength carry / throw (0x480003CB, script 0x34000164; rock sub-skill 0x34000177)

### 2.1 What the champion's graph wants (C, AGL graph chr_atomic_green_lantern_behavior.hkb, pack 0xA0000150)

Graph event ids (name table 0xA0000038): SuperStrength_Rubble_Pickup **0x100001E3**, SuperStrength_Rubble_Throw
**0x100001E4**, SuperStrength_Rubble_End **0x100004C6**, SuperStrength_InitCarPickup **0x10000176**,
SuperStrength_CarPickup **0x10000246**, SuperStrength_PickupCar **0x10000175**, SuperStrength_ThrowCar **0x10000174**,
CbtState_DisableHit **0x100003AF**, CbtState_EnableHit **0x100003AE**.

- **Rubble_Pickup** (wildcard, flags 0xE00) -> state SuperStrength_Rubble (exit hook code 2 for 0x34000177):
  sub-machine Pickup clip (`a_EventHook` code **3 @0.216 s** = grab frame, `state_to_state` code 2 @0.296 -> **Hold**),
  Hold = blend on Property_Slider_Propel over rubble idle / walk 1.25 / 2.5 / run 3.7 / 5 / 9 clips (the carry walk);
  **Rubble_Throw** (wildcard) -> Throw clip: CosmeticEnabled + `a_MissileFireHook` 5 **@0.260**, `a_SkillEndHook` 2
  @0.280, **self-raised SuperStrength_Rubble_End at end-0.20** -> Locomotion. Lua `onSkillEarlyOut`: after
  CosmeticEnabled, Propel > 0 or Turn != 0 -> Global_Locomotion.
- **InitCarPickup** (wildcard 0xC00) -> SuperStrength_Car: Pickup_Start -(CarPickup)-> Car_Pickup (clip x0.8 from
  0.45, `a_SkillHook` 3 @0.013, `state_to_state` @0.375 -> Hold), Hold -(PickupCar)-> Car_Catch (end-0.20 -> Hold),
  any -(ThrowCar)-> Car_Throw (5 @0.200, 2 @0.220, skill_to_locomotion end-0.10). Hold blends car-hold idle / walk /
  run clips on Propel. (Start state of SM_SuperStrength_Car read as 0 = Hold at an unverified field offset: **P**.)

### 2.2 The scriptlets already raise those events (C)

AGL's tables reach the shared table **0x1D0000EF** (pack 0xA00000DF): SuperStrength_PickupRubble 0x100004CD = type
0x14 graph event 0x100001E3 + sound; ThrowRubble 0x100004CC = graph 0x100001E4 + sound; InitObjectPickup 0x100007A2 =
graph 0x10000176 (+ a 0.55 s type 4); PickupObject 0x100007A1 = graph 0x10000175; ThrowObject 0x100007A0 = type 9 +
graph 0x10000174. **SuperStrength_Rubble_Active 0x10000775 is in none of AGL's tables** (only in the Superman-type
champions' 0x1D0002C8 / 0x1D0003C1 / ...): the client drops it (harmless). So the 23:10:48 sequence did put AGL into
the rubble pickup / hold / throw states (ics sends 0x100004CD at the cast and 0x100004CC at the throw).

### 2.3 What we actually sent (23:10:48, C) and what looks wrong (P)

```
48.867 stops to cast / 48.871 faces rock 1 (bundles)      48.872 PickupRubble (graph Rubble_Pickup)
49.383 rock: Vfx_PickUp   49.384 Rubble_Active (dropped by the client)   49.396 rock 1 carried (bundle at +2.1 m)
... rock bundles only when AGL moved > 0.3 m (with AGL's speed / dest: dead-reckoned on its own)
51.104 AGL throws (bundle, new heading)  51.106 stop Rubble_Active, ThrowRubble (graph Rubble_Throw)
51.352 rock: Vfx_OnThrown, then 8 bundle hops over 0.55 s   51.917 Fade_Out   51.947 _Combat_GoToLocomotion   52.522 0x3
```

1. **The rock is not in the hands** (main cause, P): it is a separate object put 2.1 m above AGL's feet by bundles.
   It appears 0.5 s after the pickup clip starts (the hands close at 0.216 s), it is centred on the body instead of
   at the hold bone, and while walking it is re-sent only every 0.3 m and dead-reckoned with AGL's destination, so it
   trails / jitters against the hold-walk clip. The C script attaches it: `AttachEntity(SELF, WeaponIID, offset,
   handle)[0x100000B0 0 1 1]` at the grab frame (S3).
2. **Lift from up to 6 m** (`liftable_reach` 6.0; 23:13 / 23:14 lifts at ~3-5 m): the rock jumps onto AGL. The
   script's S8 `IsInRangeAndAngle(MaxRange)` ends the skill (S7) when out of range.
3. No CbtState_DisableHit 0x100003AF at the grab / EnableHit 0x100003AE at the end: hit flinches play over the
   hold pose (P, minor).
4. `_Combat_GoToLocomotion` 0.85 s after the throw is not in the rubble script (only in the vehicle script
   0x34000161); the throw clip ends itself with Rubble_End (P: harmless if the clip is shorter than 0.85 s).

### 2.4 How the client attaches an object (C, exe)

The 0xB0 movement payload reader **0x57EE90** reads, in order: flags byte; 0x20 module (`u8 seq`, `u8 type`);
**0x04 attach** (`0x57E310`: `u64 parent IID`; if non-zero `u32 mode`; if `mode == 0x10` an extra block
`0x55E290`: `u32`, `u8`, `u8 bool (0/1)`); 0x10 byte; 0x08 block; 0x40 movement block; `u16`; 0x02 motion; 0x80.
The listener `0x6113E0` (containment component, slot 7) calls `0x634C70(child, block)` when the IID is non-zero:
looks the parent up (`[0x1B67258] vt+0x58`) and `0x58A220(parent, child, mode, &extra)` -> `0x55F930` attaches
(`0x588330(child, 5)`, a containment record with mode at +0x10, the extra block through `0x55EC30`); a zero IID
detaches (`0x64B330`). There is no separate attach message (C). Mode values other than 0x10 and the meaning of the
extra block's fields are not decoded (P: `u32` = attach point id, the two bytes = AttachEntity's literals `0 1` /
`1 1`).

Consequence (P): every 0xB0 of the carried object must carry the 0x04 block (a bundle without it reaches the
listener with IID 0 = detach), or the server sends no bundle for it while it is attached.

### 2.5 Recipe — rock (0x400005C9), times from the press

| t (s) | to | what |
|---|---|---|
| 0 | - | refuse (end 0x34000164 with 0x10000009) if the rock is farther than the script's MaxRange (P: ~2.5-3 m; `liftable_reach` 3.0), else stop + face bundles (as now) |
| 0 | AGL | 0x8D SuperStrength_PickupRubble 0x100004CD (graph Rubble_Pickup); variable **0x100003FF** = rock (what the script passes; the scriptlet ignores it, kept for fidelity) |
| 0.22 | rock | bundle with **0xB0 flags \| 0x04: parent = AGL IID, mode 0x10, {u32 0x100000B0, u8 0, u8 1}**; then Vfx_PickUp 0x1000023A on the rock; team = AGL's |
| 0.22 | AGL | graph event 0x100003AF (0x100001E3 + var 0x780) |
| 0.30 | - | ready to throw (`carry_ready`, slot shows the 0x480004A2 throw skill as now); **no rock bundles while attached** (or only with the 0x04 block); AGL walks normally (Hold blends on Propel; `liftable_carry_speed` stays) |
| throw press | AGL | face bundle, then 0x8D SuperStrength_ThrowRubble 0x100004CC (graph Rubble_Throw) |
| +0.26 | rock | bundle with flag 0x04 and **IID 0** (detach) at the hand (AGL pos + 2.1 m z, P), then the straight flight (15.5 m/s, 8.5 m, as now) + 0x1000008D on the rock (the script's S6), damage on the first hit as now |
| +0.28 | AGL | graph event 0x100003AE; do **not** send _Combat_GoToLocomotion; the clip raises Rubble_End itself (fallback: graph 0x100004C6 at +1.2 s if the tester sees AGL stuck in the pose) |

Config keys (new, `[ics]`): `liftable_attach = {"mode": 16, "point": "0x100000B0", "b1": 0, "b2": 1}` (null = old
bundles), `liftable_reach = 3.0`, `super_strength_cast_signals = {"pickup": 0.22, "hold": 0.30, "release": 0.26,
"end": 0.28}`, `liftable_hit_events = true` (0x100003AF / AE), `liftable_rock_locomotion_key = false`.

### 2.6 Recipe — vehicle (0x40000454 / 0x4000081B; not lifted in these sessions)

| t | to | what |
|---|---|---|
| 0 | AGL | 0x8D InitObjectPickup 0x100007A2 (graph InitCarPickup -> SuperStrength_Car); on the vehicle too (its table 0x1D00034B) |
| ~0.1 | AGL | graph CarPickup 0x10000246 (only taken from Pickup_Start; P: the machine starts there) |
| ~0.11 | vehicle | attach bundle (0x04, AGL, mode 0x10, point 0x100000B0) - Car_Pickup's `a_SkillHook` 3 @0.013 x0.8 |
| ~0.57 | - | Hold (state_to_state @0.375 / 0.8); PickupObject 0x100007A1 on AGL + vehicle only if the toss / catch is played (Car_Catch); graph 0x100003AF |
| throw press | AGL + vehicle | ThrowObject 0x100007A0 (graph ThrowCar) |
| +0.20 | vehicle | detach bundle (IID 0) and the lob (as now) |
| +0.22 | AGL | graph 0x100003AE; _Combat_GoToLocomotion 0x100002FD after the clip (the vehicle script does send it, S3) |

Confidence: graph states / events / hook times **C**; that the scriptlets reach AGL's graph **C** (tables) and that
the states ran at 23:10 **P** (no diag of the graph); the attach wire format **C** (reader), its mode / extra values
**P**; that the hand attachment is what looked "weird" **P** (no video of 23:08).
