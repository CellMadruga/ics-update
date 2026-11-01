# Atomic Green Lantern's Grab: why champions were never pulled, and what the arm is (2026-10-29)

Tester report 2026-10-29 11:00 (run 10:44-11:02, Crime Alley v AI, AGL 0x4000047D vs the bot Robin 0x4000052D; 14
Grab casts from 10:48:27): Grab pulls minions but never the enemy champion; the arm "does the animation" (stretch, grab,
bring back) and only a projectile-like effect shows. Sources: `logs/server.log`, `logs/traffic.log` of that run,
the script trees (`ics.script_model`), pack 0xA0000150 (AGL's behaviour graph, clips, 0x3F record), the decompiled
client (`re-work/decomp/c/00970000.c`, `00440000.c`, `00960000.c`), `data/skill_graphs.json`. Tags: **C** confirmed
(code / data / log read), **P** probable, **O** open. Follows `grab-beam.md`, `grab-arm-carry.md`, `agl-visuals.md`.

## 1. Summary

- Robin was never hit by a Grab missile: no `0x340002C1 S3 -> S4` (the collision state) with him in the whole run; all
  three hits (10:51:12, 10:51:32, 10:56:05) were minions; the other 11 casts flew to the end of their range (C log).
  At 10:52:15 Robin stood 2.3 m in front of AGL, 0.5 m off the Grab's line (traffic positions), and was not hit (C).
- Cause 1 (C): **DisableCollision 0x1000006F made the entity unhittable for good.** Robin's Vault Kick 0x3400030D runs
  EnableCollision at the dash and DisableCollision at its end (S2 / S5); the server kept one flag per entity, so after
  his first Vault Kick (10:49:33) `CastWorld.collides` refused him to every missile for the rest of the match. The
  client keeps a **holder list** instead (section 2.1): a run's Disable only removes that run's own Enable.
- Cause 2 (C): every Grab hit ran the missile script's DisableCollision **on AGL** (`inst.source()` = the shooter for
  a missile script); the client's node acts on the script's own context entity, the missile.
- Cause 3 (P): Grab pulls only when **NOT IsMoving(target)[0]** (T0 S4 -> S1); otherwise T3 S4 -> S11 (damage, no
  pull). ics read r1 = 0 as "walking", so a walking champion would have taken the damage branch even once hit.
- The arm (section 3): AGL's clips do not stretch anything; the stretched arm is the client beam of the missile's
  Vfx_Active (particle line from the flying hand back to AGL's arm attach point) with AGL's construct hand hidden while
  it is out. The server already sends every phase's message; one extra was wrong (Vfx_Active replayed after each turn
  bundle, stacking beams). Whether the beam draws at all is still the open runtime check of `grab-beam.md` 5.

## 2. Decode of Grab (C unless marked)

### 2.1 Collision toggles in the client

- `0x97D860` (DisableCollision) / `0x97D720` (EnableCollision): `0x44C5C0(run)` reads the run's context entity
  (script variable slot 2 of `DAT_01854350` = SELF, i.e. the missile for a missile script), finds it (`[0x1B67258]
  vt+0x58`), its physics component (`0xAA10B0`), and calls `0x976990(key, 0|1)` with `key = run->vt+0x14(0)` (a
  16-byte run key).
- `0x976990`: enable = add the key if absent (`0x56F4D0` == -1, `0x571260`), then re-insert the body (`0x971F30`);
  disable = remove the key (`0x96EB00`, swap-remove from a 16-byte array) and take the body out (`0x972110`) **only
  when the component's three holder lists are empty** (`[+0x20]`, `[+0x50]`, `[+0x10]`). P: champions / units /
  structures hold collision through their template (they collide without any script ever enabling it).
- Robin's Vault Kick (0x3400030D): S1 `EnableCollision` with the dash (its T8 waits for the dash's collision event
  0x10000002), S2 / S5 `DisableCollision` at the end. Same pattern in the Grab missile: S5 Enable at spawn, S1 / S6 /
  S11 Disable.

### 2.2 The skill script 0x340002B5 (AGL)

S1 (press): BeginSkill, Cast, FaceTarget, graph event **AtomicGreenLantern_Grab_Start 0x1000032F**, scriptlets
Grab_Start 0x10000899 / Grab_Active 0x1000089A. Cast code 5 (`a_MissileFireHook` @0.14 s of the start clip) -> S3:
cooldown, cost, **LaunchTetheredMissile 0x40000485** (range stat 18, speed stat 30, factor 0.5). S3 -> S2 on
0x10000005 (raised by the missile when it turns back with nothing, or when it is back / destroyed): ReleaseFacing,
graph event 0x10000002 (skill_to_locomotion), scriptlet **Grab_Stop 0x10000890**, cleanup event 0x10000067 to the
missile.

### 2.3 The missile script 0x340002C1

S5 (spawn): LoadSkillStats(Shooter: damage 5, stun 14), EnableCollision, AddReactionHandler 0x3F000003. S3 flying.
Collision 0x10000002 -> S4: TargetIID = the collider; then

| T | to | condition | does |
|---|---|---|---|
| T0 | S1 | alive, CheckRelation(Shooter, T) 3, IsKind 0x10108, valid, IsInRangeAndAngle(90Degrees), **NOT IsMoving(T)[0]** | ApplyDamage, hit FX, OnCollision 0x10000016 (var 0x10000030 = T), DisableCollision, remove handler, stun 0x48000293, SetMissileVelocity(Return), SetSkillAttached -> 0x10000022 -> **S9**: AttachEntity(SELF, T) + graph **Grab_Hit 0x10000331** on AGL + graph 0x100002BA on T + Vfx_Event1 0x10000076 |
| T3 | S11 | the same without the IsMoving test | damage + FX only, then S10 -> S6 (return, no pull) |
| T5 | S3 | otherwise | flies on |

S9 / S1 -> S2 on 0x10000005 (back at AGL): StopAction (detach), place the target in front of AGL (node 0x10000025 with
ScatterRadius), stun duration, graph 0x10000178 on T -> S7 DestroyEntity + 0x10000005 to AGL. S3 -> S10 -> S6 on
0x10000106 (end of range): 0x10000005 to AGL at once (the skill ends while the hand flies back), Vfx_Event1.

IsMoving 0x100000E1 is server-only (no client execute). Uses with r1 = 0: recall 0x3400000A cancels on `NOT alive OR
IsMoving(SELF)[0] OR moved > 0.25 m` (walking is the distance test's job), get-up 0x34000131 waits for `NOT
IsMoving(SELF)[0]` (the knock flight), Grab pulls only `NOT IsMoving(T)[0]`. So r1 = 0 = forced movement only (P);
r1 = 1 (0x3400041E, 0x3400017D) = any movement.

### 2.4 The reaction handler 0x3F000003 (pack 0xA0000150 @0x34FC4)

Variable block (names EntityPosition, SourceIID, Collider, SubEntity, Position, BlipSequence, **90Degrees = f32 90**,
IsEthereal), then one chain: node 0x100000A5(SourceIID), node 0x10000135, and the same six-test condition as T0
(IsAlive / CheckRelation 3 / IsKind 0x10108 / IsValid / NOT IsMoving[0] / IsInRangeAndAngle(90Degrees)). P: the
client-side / physics-side twin of the S4 test (which collisions count); it does not move anything. The script's
`<0xABEB783 src 5>` operand (90Degrees) reads this record's variable. Not run by ics; not needed for the pull.

### 2.5 The pull in ics

`Missile.collide` (World._missile_hits) delivers the collision; the tether then returns (`Missile._return`) and drags
the hit target along the line every 0.05 s (`tether_drag`), stopping 1.5 m in front of AGL; S9's AttachEntity of a
missile attaches nothing (`attach_missile_itself`). O: the drag also runs after the S11 branch (damage only); with
cause 3 fixed S11 is only taken for a target in a forced movement.

## 3. The arm

### 3.1 AGL's graph (C, `data/skill_graphs.json`)

State 112 "Grab" (entered on Grab_Start 0x1000032F; `a_SkillStartHook` 1, exit `a_SkillEndHook` 2) holds SM_Grab:
Grab_Start = `skill_grab_start` clip (MissileFireHook code 5 @0.14, state_to_state @0.225) then `skill_grab_loop`
(looping) until **AtomicGreenLantern_Grab_Hit 0x10000331** -> Grab_End = `skill_grab_end` (state_to_state @0.066) then
`skill_grab_end_loop` (looping); the state leaves only on skill_to_locomotion 0x10000002. No variable binding (no
length, no target IID) besides the turn sliders.

### 3.2 No clip stretches the arm (C data scan)

All 67 skeletal clips of pack 0xA0000150 (82 tracks; `uesrv/havok_anim.py`): no bone has a scale track away from 1
(max |s - 1| < 0.05), and the arm chain (RArm_Socket, RShoulder, RElbow, RWrist, Construct_*) moves at most ~0.5 m
except in the enter-world clip 0x1A00081C (the construct rings fly in from ~26 m and the arm from 6 m: the arm
assembling) and one 6.5 s emote. The construct arm mesh (`..._Atomic_Green_Lantern_Arm`) is skinned to that chain.
So the Grab clips only raise / hold / pull the arm; no skeletal "stretch". (Which 0x1A DID is which Grab clip is O: the
clip table does not follow the name list; `diag.py --anims` gives it.)

### 3.3 What draws the stretch, grab and return (C data, P look)

- Grab_Start 0x10000899 (AGL): at 0.24 s particle 0x18000754 + **ArmFade_RemoveHand** (type 8 render effect: hides
  the construct hand). Grab_Active 0x1000089A: placeholder.
- Missile 0x40000485 (ws 0x2E000C4C, `.entity` 0x2D000A33 = an empty 1 m mover with attach points): **Vfx_Active**
  0x100000EB at 0.1 s = the **type 2 beam** from the missile's attach 0x10000039 to its creator's (0x100004E2 = AGL)
  attach **0x1000007C** (AGL's arm), particle 0x18000752 along the line (70 / s per 5 m), head speed 200 m/s
  (grab-beam.md 2) + Vfx_Streak_Right. That line between the flying hand and AGL's arm is the stretched arm; it is as
  long as the missile is far.
- Hit: 0x10000016 OnCollision (missile, target var), Vfx_Event1 0x10000076, Grab_Hit on AGL (pull pose), 0x100002BA
  on the target. Return: the missile flies back with the target; the beam shortens with it. Back: 0x3 (the beam ends
  with the missile's run), Grab_Stop 0x10000890 (AGL): ArmFade_AddHand + particle 0x18000755.

### 3.4 What the server sends (traffic 10:51:12, a hit on a minion; C)

| t | message |
|---|---|
| 12.504 | AGL stops to cast (bundle) |
| 12.651 | AGL graph event (0x100001E3 + var) Grab_Start, scriptlets 0x10000899, 0x1000089A |
| 12.674 | missile 0x40000485 created (134 bytes, 0x100004E2 = AGL, tables 0x1D000456 + 0x1D0003D2) |
| 12.683 | missile Vfx_Active |
| 12.903 | missile 0x10000016 (hit) |
| 12.948 | missile 0x10000076 (Vfx_Event1) |
| 12.963, 13.101 | **missile Vfx_Active again** (after each turn bundle: `missile_rebundle_scriptlets`) |
| 13.085 | AGL graph event Grab_Hit |
| 13.174 | missile gone (0x3) |
| 13.318 | AGL graph skill_to_locomotion + Grab_Stop |

Every phase of 3.3 is there. The replays are wrong: a bundle drops no running scriptlet (object-update-bundles.md 3 /
6.1, C), so each one started another beam + streak on the same missile (the "projectile" look, P). Removed
(`missile_rebundle_scriptlets` []).

## 4. Changes (config `[ics]`, all true = new)

| key | default | what |
|---|---|---|
| `collision_toggle_own_entity` | true | Disable / EnableCollision act on the script's own entity (the missile), not the shooter |
| `collision_holders` | true | per-run holders; champions / units / structures / props stay in collision by template |
| `is_moving_flag_walks` | true | IsMoving r1 = 0: forced movement only; r1 = 1: walking too |
| `missile_rebundle_scriptlets` | [] | no Vfx_Active replay after a missile's turn bundle (was ["Vfx_Active"]) |

Tests: `tests/test_meltdown.py` (AGL harness) gains `grab`: a still bot, a walking bot and a bot that ran a dash's
Enable / DisableCollision are each hit, take S4 -> S1 (not S11), end < 2.6 m from AGL, stay in collision, and AGL stays
in collision (with the old keys: 8 of these fail). `test_match.py` 310/310, `test_ics.py` 40/40, `test_scriptvm.py`
78/78; `champion_check.py --vs-champion --window 5` summary identical to the old keys (no regression; its bot never
dashes first, so it never showed cause 1).

## 5. Expected in game / open

- Expected: Grab on Robin (walking, after his Vault Kick) hits, stuns and pulls him in front of AGL; AGL keeps taking
  missile hits after his own Grabs; one beam / streak per Grab instead of three.
- O: whether the beam (the stretched arm) draws at all. If it still shows only the flying effect, run
  `python tools\diag.py --brazo` for one Grab: the per-frame end checks of grab-beam.md 5 (0x349845 render model,
  0x349865 model active, 0x34CC05 draw pass) say which end fails.
- O: S11 (damage-only branch) still drags its target in ics; the 0x3F handlers are not run; which 0x1A clip is which
  Grab clip.
