# The Super Strength soft-lock, the dead slot, the throw press, the robotic lift / throw (2026-10-30)

Tester report 2026-10-30 11:23 (build fase3-ip, Crime Alley v AI, Atomic Green Lantern, server run 11:05-11:23, match
ended by surrender at 930 s; `logs/server.log`, `logs/traffic.log`, `logs/diag.log` = ring breakpoints only). Tags:
**C** confirmed (log / code read), **P** probable, **O** open. Builds on `liftable-carry-throw-press.md`,
`liftable-aura-lift-throw-break.md`, `liftable-throw-destruction.md`, `vehicle-lift-and-position.md`.

Tester, translated: (1) lifting and throwing the vehicle still looks robotic, in parts, as if animations were skipped;
(2) the vehicle crashes, the explosion sounds, the model lasts a couple of seconds before disappearing; (3) the throw
button does not work directly, "I have to click and press"; (4) after the first vehicle, a lifted car or meteorite kept
me from moving until I threw it, and it would not let me throw it: stuck; (5) after that Super Strength never worked
again: no indicator, pressing did nothing.

## 0. Every Super Strength use of the run (C, server.log + traffic.log)

| Lift | Object | 0x34000164 S4 -> S3 (input back, StartCooldown) | "move refused (crowd control)" during the carry | Throw | How |
|---|---|---|---|---|---|
| 11:07:35.994 | vehicle 10 | **36.578** (toss), 0x20F8 kept ready 36.579 | 0 (17 moves) | 42.268 | 2 unanswered presses (38.732, 41.925) -> liftable_throw_on_press |
| 11:10:20.438 | vehicle 10 | **never** | 22 | 27.565 | order 66 ms after the press |
| 11:10:48.337 | vehicle 8 | **never** (no cooldown: cast 28 s after the last) | 16 | 54.726 | order 52 ms after the press |
| 11:11:29.384 | rock 0 | **never** | - | 29.859 | order queued during the lift |
| 11:13:19.272 | rock 0 | **never** | 24 | 26.921 | 2 unanswered presses (24.694, 26.569) |
| 11:16:32.518 | rock 0 | **never** | - | 32.975 | order 0.31 s into the lift, queued |
| **11:16:33.662** | **rock 0, in flight** | never | 57 (33.9-58.5) | 58.092 (a ghost) | press 57.726 |

From 11:16:59 on, every slot-7 cast (11:20:07, 08.9, 10.9, 11.6, 16.2, 11:21:42.8, 43.4, 43.9, 11:22:55.9) had target
0x0 and went `S0 -> S2 -> S0` (T2: no valid TargetIID): nothing lifted, no indicator (C).

## 1. The input back only ever went once per match (C) -> items 4 (cannot move) and part of 5

`Liftables._input_back` (fase3-io, `liftable-aura-lift-throw-break.md` 2) marked the sent 0x100000BB on the **script
instance** (`inst._input_back_sent`). The instance is the slot's `ent.skill_insts[7]`, created once and re-activated
on every use, so the mark was never cleared: only the first lift of the match (11:07:36.578) took 0x34000164 S4 -> S3.
From the second lift on, S4 kept node 0x100000AD's input hold for the whole carry (World.walk_to: "move refused (crowd
control)" 22 / 16 / 24 / 57 times) and S3's StartCooldown never ran (no 90 s cooldown, no "kept ready" 0x20F8, so the
throw indicator waited its full 1.5 s fallback: 11:10:23.126 = lift + 2.69 s). The first carry (S3 reached) moved freely.

Fix: the mark is per lift (`ch.carry_input_back_sent`, reset in `lift`) — `[ics] liftable_input_back_per_lift`.

## 2. The thrown rock lifted again in flight, then removed in the hands (C) -> items 4 (stuck) and 5

11:16:32.828: a throw order 0.31 s into the rock's lift was queued (liftable_throw_early_queue), thrown at 32.975 when
the rock was ready; `_release` at 33.427 (S4 -> S1 -> S0, EVENT_END). **33.659**: another slot-7 order, target 0x0,
point (85.8, 78.6) (the client still showed the rubble throw skill: the Super Strength table comes back
`liftable_slot_restore_delay` 0.9 s after the throw's end). Carrying nothing, `World.cast` took it as a new Super
Strength use: no cooldown (section 1), the repeat guard's 0.4 s had passed (0.68 s). `script_runtime.activate` sets
TargetIID only when the order has a target, so 0x34000164 still held **rock 0** from 32.513; S0 -> S2 -> S4 passed
EntityExists + IsTargetable and RaiseEvent 0x10000037 reached the rock in flight. `Liftables.lift` checked only "in
props, not carried" (`_fly` clears carried_by at the launch, and a landed object stays in props until `_gone`), so it
lifted it. Then the old flight landed it (33.940 "rock 0 lands", Vfx_Fade_Out 33.941) and `_gone` removed it (34.551
"rock 0 gone (0x3)") while the champion still carried it. Nothing watched the carrier (`tick` walks `self.props`
only): carry speed, held champion bundles and S4's input hold (section 1) for 24 s, until the next slot-7 press threw
the ghost (58.092; `_fly` returned at once, the carry ended at 58.535).

Fixes: `[ics] liftable_lift_guard` — `lift` refuses an object that is gone, flying, tossing, landed (broken) or carried,
and a request whose order had no target (the order record `inst.request` lacks TargetIID: a stale one); a refused
request posts 0x10000009 to 0x34000164 so its S4 never keeps its hold. `throw` of a gone object just ends the carry.
P: the original server cleared TargetIID on a target-0x0 order; the VM (`script_runtime.activate`) still keeps it for
every skill (left as is here: outside the liftables).

## 3. The slot table lost for good (C) -> item 5

`_release` restores the Super Strength table `liftable_slot_restore_delay` s later, and `restore()` does nothing when a
new carry started meanwhile, leaving `carry_base_block` set. The 33.662 lift then ran `_throw_button(on)`, which took
the slot's **current** table (the rubble throw's) as the base and overwrote `carry_base_block` with it. At 58.535 the
"restore" put the throw table back: 11:16:59.425 "slot 7: Super Strength again" is **1432 bytes** (every earlier one
1539 / 1540). The client kept the rubble throw skill (ground / line target) in slot 7 for the rest of the match, so its
orders carried target 0x0 and the server's 0x34000164 (still Super Strength) found no target: S2 -> S0.

Fix: `[ics] liftable_keep_base_block` — a pending base is kept and the throw table is built over it.

## 4. "The throw button does not work directly" (C pattern, P cause)

0x20EA presses of slot 7 during carries (decoded `07 00 00 00 01 00 00 00 23 00 00 10 00`): at 11:07 (indicator on at
37.169) 38.732 and 41.925 had no 0x20EE; at 11:13 (indicator 21.331) 24.694 and 26.569 had none; at 11:10 the press
gave its order 52-66 ms later. As in `liftable-carry-throw-press.md` 1.2, which client step refuses an unanswered press
is **O** (no `--throwpress` diag in this run). The server fallback threw on the **second** unanswered press, i.e. the
tester pressed twice (3.2 s and 1.9 s apart) for one throw. Now `[ics] liftable_throw_on_press` = 1: the first press with
no order within `liftable_throw_press_window` (0.35 s; every answered press of every run came within 66 ms) throws
toward the champion's facing.

## 5. The watchdog (`Liftables._watch`, every match tick)

`[ics] liftable_watchdog` and its timeouts; carriers are tracked in `Liftables.carriers` (set at the lift, cleared by
`_release`), each with `carry_phase` lift / ready / throw and its start time (match clock):

- the carried object is gone (not an entity, or out of the liftables) outside the throw: the carry ends at once
  (`_abort`: detach, `_release` = indicator off, carry state, speed, Super Strength's table after the restore delay,
  0x10000009 to 0x34000164; an object still there is put down and lands);
- a dead carrier: `_drop` (as `tick` did for ready carries; now also during the lift);
- a lift not ready after `liftable_lift_timeout` (3 s): made ready (`_hold`), else aborted;
- a throw not ended after `liftable_throw_timeout` (3 s): aborted;
- a ready carry longer than `liftable_carry_timeout` (20 s; 0 = no limit): thrown toward the facing
  (`liftable_carry_timeout_action` "throw") or put down ("drop");
- the champion's slot still on the throw table `liftable_restore_timeout` (2.5 s) after the restore was due: Super
  Strength's table is put back.

## 6. "Robotic, in parts, as if animations were skipped" (C causes, P result)

- The throw's turn was a **full champion bundle** (1450 bytes, 11:07:42.267, 11:10:27.564, 11:10:54.726) 0.13 s before
  ThrowObject, in the middle of the Hold clip: fase3-im's motion-only turn (`liftable_throw_face_motion_only`) works only
  in "delta" mode, and `object_update_mode` went back to "bundle" on 2026-10-29 10:28. The client applies a 0xB0-only
  state in bundle mode too (`object-update-bundles.md` 0.5 / 11.2, C). Now `[ics] liftable_throw_face_motion_bundle`:
  the movement state alone (68 bytes in the test); the changed tables go with the slot restore after the clip.
- The vehicle's toss onto the champion: 9 states precomputed at fixed fractions, sent on the match tick (~68 ms in this
  run), two in the same tick twice (11:07:36.758 / .759, .897 / .897), so the lob hopped. Now `[ics] liftable_toss_timed`:
  one state per `liftable_throw_step_seconds` at the curve's own send time (as the throw flight since fase3-io).
- From the second carry on, the S4 input hold (section 1) froze the champion: every move refused while carrying.

## 7. "The model lasts a couple of seconds before disappearing" (O)

The landing sent, as designed in fase3-io: 0x8B on the landing frame (43.307), Destructible_IgnoreAOI, 0x8A (43.368),
`_HFSM_DestroyEntityAction_Optional` (43.478; one type-0x1F action on 0x10000623, the fog-occluder flag, not a fade),
the break keys (43.510-43.512: sounds and particles), 0x8A again (43.541), removal 10.5 s later (53.808). Nothing the
server sends hides the vehicle ~2 s after the landing, so the disappearance is client-side (P: the pieces broken by the
0x8A after all and removed as debris, or the physics of the rebuilt pieces). Not changed: a late Vfx_OnExplode
(`liftable_land_explode`) would delete the pieces at once, the 2026-10-29 21:10 complaint. Next run: `tools/diag.py
--destruction` (piece bodies found by 0x8A, 0x62ED00 / 0x62EBF0 removals) during a vehicle throw.

Follow-up 2026-10-30 12:05: `liftable-lift-throw-wreck.md` 2 (Vfx_OnExplode 0.75 s after the landing).

## 8. Other things in these logs

- Super Strength's cooldown never ran after 11:07 (section 1): 5 uses in 6 min.
- 11:16:34.396: Grab was cast while carrying the ghost (casts of other slots are not blocked during a carry; P the
  original allowed it too).
- The first lift's 0x20F8 "kept ready" went at the toss (36.579) and the indicator at the Hold (37.169): the vehicle order
  that `liftable_indicator_after_cooldown` expects; the later carries had no 0x20F8 and fell back to the 1.5 s wait.

## Tests

`tests/test_match.py` `superstrength_softlock` (14 checks, real script 0x34000164): input back at the 1st and the 2nd
lift and walking while carrying; the 11:16:33.659 order (target 0x0 after a throw) lifts nothing; a thrown object and a
stale TargetIID are refused with 0x10000009; Super Strength's table back after a lift during the pending restore; the
object removed in the hands ends the carry; lift and carry timeouts; Super Strength lifts and throws after all of it.
With the four new switches off, 11 of the 14 fail (the 11:16 soft-lock reproduced).
