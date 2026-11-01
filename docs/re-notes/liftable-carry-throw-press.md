# Carry smoothness, the meteorite that could not be thrown, the vehicle that still does not explode (2026-10-29, fase3-in)

Tester report 2026-10-29 19:55 (Crime Alley v AI, Atomic Green Lantern; server run 19:46-19:55, `logs/server.log`,
`logs/traffic.log`; vehicle 6 = the truck `0x4000081B`, lifted 19:49:43.186, thrown 47.561, landed 48.875; rock 1
lifted 19:52:22.881, thrown 19:52:48.458). Tags: **C** confirmed (code / data / log read), **P** probable, **O** open.
Exe `InfiniteCrisis.exe`, base 0x400000, decomp `re-work/decomp/c`. Builds on `liftable-throw-destruction.md`,
`throw-padlock-coredeath.md`, `client-movement.md`, `full-combat-skills.md` 1.4.

## 1. "I lifted a meteorite but could not throw it; only after a Q could I throw it"

### 1.1 What the run shows (C traffic)

| Time | Message |
|---|---|
| 22.860 / 22.880 | "stops to cast", "faces rock 1 (throw skill in its slot)" (full champion bundles), 0x20C9 0x1000001D slot 7 |
| 22.985 / 23.218 | pick-up 0x8D, rock over the head, CbtState_DisableHit |
| **23.369** | `0x2180(7)` and `0x20F9(7, 0)`: the throw indicator (the rock is ready 0.30 s into its clip) |
| **24.096** | `0x20F8(7, now)` "kept ready while carrying" (Super Strength 0x34000164 S4 -> S3 at 1.2 s, its StartCooldown) |
| 29.131 .. 44.831 | **13 client 0x20EA (slot 7, 0x10000023)**, none followed by a 0x20EE |
| 46.357 / 46.393 | 0x20EA + 0x20EE for slot 1: Grab is cast |
| 48.422 / 48.456 | 0x20EA slot 7, then the throw order 0x20EE 34 ms later: the rock is thrown |

The vehicle carry of the same run threw at the first press (0x20EA + 0x20EE in the same ms, 19:49:47.559). Its order
was the reverse: the "kept ready" 0x20F8 (44.401) before the indicator (44.569), since a vehicle is ready only 1.21 s
into the lift, after Super Strength's cast. No AGL message went between 24.1 and 46.4 except vitals and the level-up
0x8D; attack orders (0x20EE, 43.140) did go, so the block was slot 7's alone (C).

### 1.2 The client's press path (C code, P which step failed)

- 0x20EA is sent by `0xa26420` (targeting start: only when controller `+0x110` == 0 and `+0xF0` == -1; it sets `+0xEC`
  = slot) and by the cancel branches of the dispatcher `0xa85da0` (`0xa23510`). Every 0x20EA of the run was a
  targeting start, so `0x8709e0` (CanActivate) passed (an error returns before `0xa26420`).
- The cast itself goes on the release (quick cast, the tester's mode: `0xa0e500` = per-skill `0x10000937` else the
  global setting) through `0xa76320` / the dispatcher's switch on the targeting type (`0x1000003D`: 1 vehicle ground
  area, **13 rubble line**). Type 13 asks the cursor pick `0xa19e50(out, 1, 0, flags)`, which returns 0 when the
  champion's position block has no valid cell (`+4` == 0, `+8` / `+9` == -1, `+10` == invalid); type 1 takes
  `0xa19e50(.., 0, 1, flags)` whose first branch (`0xa15210`) needs no cell. Then `0xa70030` -> `0xa70600` ->
  `0xa25d80` (point checks: `0x100006AB` navmesh snap within 2.5 m, `0x100006D5` range clamp (vehicle only), a
  minimum distance, `0x53a480`) -> `0x8686c0` -> `0x863860` (held: the slot in the controller's disabled list,
  condition `0x1000006C`, Stunned `0x100003F3`, action code 0x40-0x4F, lock counter `+0x70`, or the buffer's
  current-action slot `+0x78` (written only by S->C **0x2083**, never sent) that is another slot while the skill has
  `0x10000704`) -> 0x20EE.
- The dispatcher also ignores a press when the champion's property `0x100006B4` equals the slot and the skill lacks
  `0x100006B3` (`0x85d450`, `0x861930`); ics never sets 0x100006B4 and the press got past it (0x20EA came).
- Graph data (C, `data/skill_graphs.json`): AGL's `SuperStrength_Rubble_Pickup` clip carries a code-2 trigger with
  did 0x34000177 (the rubble throw's own script) at 0.37 s, i.e. a SkillEnd of the throw sub-skill at the end of the
  pickup; `SuperStrength_Car_Pickup` has none. P: one more client-side difference between the two carries.

Which of these refused the 13 presses is **O** (no breakpoint ran on that path; `diag.log` of the run is hover only).
`tools/diag.py --throwpress` (alias `--lanzar`) now logs each step (dispatcher, targeting start, quick cast, order
API, point check, buffer, hold check) for the next run.

### 1.3 Fix (P)

- `[ics] liftable_indicator_after_cooldown` (1.5 s): the throw indicator waits for the slot's "kept ready" 0x20F8
  (`World` on_cooldown emits "carry_cooldown"), as in the vehicle carry that threw normally; at most 1.5 s after the
  hold. 0 = `liftable_throw_indicator_delay` after the hold (fase3-ij .. fase3-im).
- `[ics] liftable_throw_on_press` (2) / `liftable_throw_press_window` (0.35 s): `World.raise_skill_event` emits
  "skill_press"; a press of the carry slot that no throw order follows within the window is unanswered, and the
  second unanswered press in a row throws toward the champion's facing (`Liftables._press` -> `throw(ch, None)`: a rock
  flies to its 8.5 m range, a vehicle lands 6 m ahead). Every working throw sent its 0x20EE 0-34 ms after the 0x20EA,
  so an answered press never reaches the count. 0 = only the client's order throws.

## 2. "The carry, walking with it and the throw are still not smooth"

- C (server code): the champion's own state goes every tick (30 Hz, a full bundle in the live `object_update_mode`
  "bundle"); the carried object only when the champion's course changed or every `liftable_carry_resend` 0.5 s, and
  each such state lay within 2 m of the client's replayed point.
- C (`client-movement.md` 1.3, `0x60B5F0`): a state within 2 m with no newer sequence byte is **steered**: the
  character body gets a velocity toward the target (`0x5C9FE0`); `throw-padlock-coredeath.md` 1.3 found that steering
  drops the vertical part of an object held off the ground (the flight drew flat until each state was snapped). The
  carried truck sits 2.5 m over AGL's feet, the rock 2.75 m: between states it sank and was pulled back (P: the
  "not smooth" carry).
- Fix: `[ics] liftable_carry_snap` (["vehicle", "rock"]): each carry state carries a newer teleport sequence
  (`World.teleport`), and `liftable_carry_resend` 0.05 s while walking (was 0.5). [] / 0.5 = as before.
- The lift timeline (CarPickup 0.45 s, toss 0.4625, catch 1.1125, ready 1.2125), the throw (turn, ThrowObject +0.13 s,
  launch at the clip's MissileFire 0.2 s = 47.897 / hook 5 at 47.898, EnableHit, locomotion 0.94 s, slot table back
  1.24 s) all ran on the fase3-im timings (C log); nothing in them changed here.

## 3. "On impact the vehicle does not do its exploding animation"

### 3.1 What went (C traffic)

48.879 `0x8B` rebuild at the landing, `Vfx_OnExplode`, `Destructible_IgnoreAOI`; 48.937 `0x8A` (4.0 m, 10, level 3);
49.031 `_HFSM_DestroyEntityAction_Optional`; 49.109 `0x8A` again; removal 10.5 s later. Every fase3-im landing step,
in its order, to the right IID (the truck's tables hold all those keys, C `Data.scriptlets(0x4000081B, 0x2E000F04)`).

### 3.2 What the impulse needs (C code)

- `0x632370`: `0x630E80` stores the wire's magnitude **raw** at impulse+0x48 (the 0x8A reader `0x445c90` copies 4
  bytes, no conversion); `0x62BC00` subtracts it as an int from the piece health (+0x44): 10.0f = 0x41200000 breaks
  any piece it reaches. So the magnitude is not the problem (C).
- `0x631C50` -> physics sphere query `0x5CEA30`, then `0x631B00` (piece bodies) and `0x631940` (entities with an
  active piece whose def +0x46C is set); **both skip an owner whose position block has no valid cell** (`+4` != 0,
  `+8` / `+9` != -1, `+10` != `DAT_01862850`). `0x631FA0` runs only with hits (`+0x34`), then `0x62F290` ->
  `0x62BEF0` (skips a piece whose flags +0x194 bit 0 is set) -> `0x62BC00`; a piece at <= 0 breaks and the client
  plays its break key (Destructible_OnBreak_*_T1, Destructible_OnCompletelyDestroyed: truck table 0x1D000612, SUV
  0x1D0001FD; Vfx_OnExplode / Vfx_Stp_Detonate_Matter_Explosion_Hit are in 0x1D00034B).
- P: the query found nothing (no break key ever showed in three builds). O: which check (cell of the landed truck,
  the bodies the 0x8B made 0.05 s earlier, the def flags).

### 3.3 Fix (P)

`[ics] liftable_land_break_keys` (vehicle: Destructible_OnBreak_Front / Back / Left / Right / Middle_T1,
Destructible_OnCompletelyDestroyed; a name the object's tables lack is not sent: the truck has no Middle) to the
landed object `liftable_land_break_after` (0.2 s) after the landing (`Liftables._break_keys`). {} = none. P: doubled
if the impulse also breaks the pieces. `tools/diag.py --destruction` now also logs 0x632370 (radius / magnitude
bits), the two scans, 0x631FA0 (hits) and 0x62BC00 (piece, health, amount).

## 4. Checks

`tests/test_match.py` `carry_press_facing`: the rock's indicator only after the kept-ready 0x20F8 and in that order;
a walking carry state with a newer teleport sequence; one unanswered press keeps the carry, the second throws; a press
the order follows throws once; `liftable_throw_on_press = 0` never throws; the landed vehicle's break keys (only names
its tables hold); the minion facing checks of `minion-attack-facing.md`.

## 5. Open

- O: the exact client gate of 1.2 (run `python tools\diag.py --throwpress` while carrying a meteorite).
- O: why 0x8A breaks nothing (`--destruction`: does 0x631FA0 run? what health does 0x62BC00 see?).
- P: that the original showed the throw ring through 0x2180 at all (`throw-padlock-coredeath.md` 1.2).
