# The vehicle's toss, the throw's carried state, the wreck that stays (2026-10-30)

Tester report 2026-10-30 12:05 (Crime Alley v AI, Atomic Green Lantern; server runs 11:59:21-12:02:31 and
12:02:48-12:05:01; `server.log`, `traffic.log`; `diag.log` has no liftable probes). Translated: "the vehicle lift
animation still looks weird, and so does the throw. The vehicle simulates crashing but doesn't disappear: the explosion
sounds, then it stays there a few seconds before disappearing." Tags: **C** confirmed (log / code / data read), **P**
probable, **O** open. Exe `InfiniteCrisis.exe`, base 0x400000, decomp `re-work/decomp/c`. Builds on
`liftable-softlock.md`, `liftable-aura-lift-throw-break.md`, `liftable-carry-throw-press.md`,
`liftable-throw-destruction.md`, `client-movement.md`.

## 0. The run: one lift, no soft-lock, no watchdog (C)

Only one Super Strength use (vehicle 10, the second server run had none). Every step went through:

| Time | What |
|---|---|
| 12:01:34.395 | order slot 7, target vehicle 10; 34.461 "stops to cast" (full bundle 1538 B), 34.475 facing + throw skill (1449 B) |
| 34.550 | InitObjectPickup on AGL and the vehicle |
| 35.008 | graph event CarPickup (+0.458 after the pickup; graph 0.45) |
| 35.048 | toss start (VFX_CBT_Hit_Shared on the vehicle); 35.063 0x34000164 S4 -> S3 (input back, StartCooldown); 35.065 0x20F8 kept ready |
| 35.114 .. 35.424 | 6 toss states (f 0.16 .. 0.91), 43-79 ms apart |
| 35.449 | catch: DisableHit, carry state (snap, seq A 2), PickupObject on both; 35.519 0x8B "over the head"; 35.551 carry state (seq A 3) |
| 35.613 | indicator 0x2180 / 0x20F9 (after the 0x20F8, as designed) |
| 35.79 .. 36.06 | 4 move orders while carrying, all accepted (no "move refused") |
| 36.394 / 36.525 | press 0x20EA, then the throw order 0x20EE (answered: `liftable_throw_on_press` did not fire) |
| 36.526 | AGL turn = movement state only (68 B); 36.599 ThrowObject on both; 36.801 launch (`thrown`), 36.802 EnableHit |
| 37.475 | landing ("nothing hit"): 0x8B on the landing frame, Destructible_IgnoreAOI; 37.537 0x8A; 37.629 `_HFSM_DestroyEntityAction_Optional`; 37.676 break keys (OnBreak Front / Back / Left / Right T1, OnCompletelyDestroyed); 37.707 0x8A again |
| 37.708 / 37.709 | Super Strength's table back (1538 B, the right size), cooldown 87.4 s (0x20F8) |
| 47.996 | `vehicle 10 gone (0x3)`: 10.52 s after the landing |

No "carry of ... ended", "never got ready", "too long", "restore_timeout" or "does not lift" line: the watchdog never
had to act and the soft-lock fixes of fase3-ir held (input back at the toss, 90 s cooldown, the real slot table back).
The throw point was 2.2 m from AGL (the tester's click), so the vehicle flew the 0.5 s minimum flight with the 3 m arc
and came down just in front of him.

Note: the per-tick object states (carry while walking, the flight) are sent unlabelled and are not in traffic.log
(`ics/net.py`: label None = not logged); only the toss and the forced carry states are.

## 1. "The lift still looks weird, and the throw" (C bytes / code, P effect)

### 1.1 The toss crept along at speed 0 (C)

The six toss states (`Liftables._toss`, `liftable_toss_timed`) are full bundles whose 0xB0 block has **speed 0** and
the same sequence bytes `01 01` (no newer seq A): z 201.22 -> 201.86 -> ... (ground 200.1), then the catch's state
`5b 0c 02 01` (seq A 2) at z 202.60. With speed 0 each state's dead-reckoned point stands still, a state within 2 m
of the body is only **steered** (0x60B5F0 -> 0x5C9FE0, `client-movement.md` 1.3), the client samples 0.1 s behind, and
the steering drops the vertical part of a body held off the ground (`throw-padlock-coredeath.md` 1.3, the fase3-ih
frames of the flat flight). So the lob crept toward AGL in ~63 ms steps, low, and popped up to the head at the catch's
snap (P: the "weird" lift; the bend / Car_Pickup / catch clips themselves ran at the graph's times).

Fix: `[ics] liftable_toss_velocity` = ["vehicle"]: each toss state (now also one at f = 0, the toss frame) is snapped
(`World.teleport`) and carries the lob's 3D velocity: heading toward the hold point, speed = |v|, motion pitch 0x40 =
the velocity's pitch (up, then down along `liftable_toss_arc`), the vehicle's facing turned from its parked heading to
the champion's by `facing_offset` (facing = heading + offset in `messages.movement_block`). The client dead-reckons
along the curve between states, as for the throw flight (`liftable_throw_velocity`, fase3-io). The catch clears the
velocity pitch and the offset (`Liftables._toss_end`). [] = the old states.

### 1.2 The carry (unchanged, C evidence missing)

Walking carry states are snapped every `liftable_carry_resend` 0.05 s (`liftable_carry_snap`); each snap zeroes the
body's velocity for one physics step (0x60A270(.., 1)) while the champion is only steered: a possible hitch, but the
tester named the lift and the throw, not the carry, and the states are not in the log. Left as is (O).

Attach re-check (C, `vehicles-carry-collision.md` 1.2): the 0xB0 parent block (mode 0x10) carries only {attach point,
u8, bool}; the child's local transform (`0x55E6B0`, words +0x10..+0x28) is never filled from the wire, so an attached
vehicle sits on the champion's origin, which the 2026-10-28 13:38 run showed. No new evidence: the vehicle stays carried
by its own states (`liftable_attach_kinds` ["rock"]).

### 1.3 The throw: the carried vehicle kept its last carry state (C server code)

`Liftables.throw` stops the champion and turns him toward the point (the movement state alone), but the vehicle got no
state until the first flight state, `liftable_face_lead` + the launch frame (0.33 s) later: it kept the old heading and,
when the champion threw while walking, his walking speed, so the client dead-reckoned it out of his hands. Fix:
`[ics] liftable_throw_turn_object` (true): one carry state on the hold point with the new heading and speed 0 at the
throw. In this run AGL had stopped 0.4 s before the throw, so only the turn applied.

## 2. "Explosion sounds, then the wreck stays a few seconds" (C code, P key)

- Since fase3-io the landing sends no Vfx_OnExplode (it removed the pieces at once: the 2026-10-29 21:10 "vanishes at
  the impact with only the sound"). This run: break keys at +0.2 s on the intact pieces (the "simulated crash" and the
  sound), then nothing until the 0x3 at +10.5 s (C traffic above).
- `0x62EBF0` (a piece removed; reached from Vfx_OnExplode's 0x28 action) first calls **`0x62E6E0` with ECX =
  piece+0x50** (C, disassembly `0x62EBFE lea ecx, [ebx+0x50]`): it empties the piece's effect lists (+0x38, the
  0x14-byte entries at +0x40 whose object gets vfunc(1), +0x50), then frees the render instance (+0x15C, `0x7E34A0`) and
  the body (+0x188, `0x5C5E90`). So the effects the break keys put on a piece die with it (P: that those lists hold the
  particles), which is why Vfx_OnExplode at the landing left only the sound.
- When the active list is empty and the destruction record's **+0x70** is set, `0x62EBF0` runs that scriptlet on the
  entity (`0x57D8B0`, C). The truck's record `0x500001F0` (pack 0xA000024C) holds, besides the piece keys
  (OnBreak_*_T1, Destructible_State3, OnCollision_Metal), one key after the piece list: **0x10000290
  Destructible_OnCompletelyDestroyed** (C data scan) -> P that it is record+0x70: the original (0x3400015F S2:
  Vfx_OnExplode at the landing) made the vehicle vanish and the client played OnCompletelyDestroyed itself.

Fix: `[ics] liftable_land_explode` = {"vehicle": 0.75} (was {}): the landing keeps 0x8B, IgnoreAOI, 0x8A x2, the
destroy action and the break keys at +0.2 s on the intact wreck, and Vfx_OnExplode goes at +0.75 s (0.55 s after the
break keys): the wreck vanishes with the explosion instead of standing until the removal at 10.5 s. {} = the fase3-io ..
fase3-ir landing. P: the explosion sound may play twice (our OnCompletelyDestroyed at +0.2, the client's at +0.75); drop
`Destructible_OnCompletelyDestroyed` from `liftable_land_break_keys` if so. P: the fire of the break keys ends with the
pieces at +0.75.

## 3. Tests

`tests/test_match.py` `lift_throw_wreck_1205` (7 checks): toss states snapped with speed and an up-then-down velocity
pitch, the f 0.00 state, the catch clears pitch / offset; a throw while walking stops and turns the vehicle at once;
break keys before a Vfx_OnExplode 0.75 s after the landing; the switches back ([] / {}). With the three switches off,
4 of the 7 fail. `aura_lift_throw_break`'s landing check now allows the late Vfx_OnExplode after the break keys.

## 4. Open

- O: whether the break keys' fire survives until +0.75 s (P: removed with the pieces) and whether the client plays
  OnCompletelyDestroyed at the explosion. `python tools\diag.py --destruction` during a vehicle throw logs 0x62ED00 /
  0x62EBF0 (pieces removed) next to the 0x8A lines.
- O: the walking carry hitch (1.2), the throw clip's length (`liftable-throw-destruction.md` 6).
