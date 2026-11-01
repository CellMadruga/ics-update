# Crime Alley core: yaw, no attack, minions and the bot on it; the decor door; dampener regen; turret heads; recall streaks (2026-10-30, tester report 15:30)

Tester run 16:36-16:58 (Crime Alley v AI, Atomic Green Lantern vs bot Poison Ivy `0x40000AAE`; surrender 16:58:43).
Logs: that run's `server.log` / `traffic.log` (copied to the session scratchpad `logs1530map/`). The screenshot with the
red rectangle (the door's spot) did not reach the session (newest images 92-95 are score / level-up / store screens).
Tags: **C** confirmed (logs, data words, decompiled exe `re-work/decomp`, tests), **P** probable, **G** guess, **O** open.
Scripts in the session scratchpad (`m1530/`); nothing of the game copied.

## 1. "The blue core must be rotated 170 degrees to the right"

- The core's yaw is the map spec's `{T1: 90, T2: -90}` (`ics/match/maps.py`, the pedestal `0x2E000A3B`'s yaw); the data's
  core markers `0x2E0011A7` / `A6` say -90 / 90 (`map-audit-all.md` 7.2, C).
- Yaw is counter-clockwise seen from above; the game camera has +y up on screen (the 2026-10-24 camp turn 180 -> 90
  was a clockwise turn on screen), so "right" = clockwise = -170: blue 90 -> **-80**. The tester's figure is within
  10 deg of the markers' -90 (P: the markers are the core's front; if -80 looks 10 deg off, -180 gives -90).
- `[ics] match_structure_yaw_add` = {"crime_alley": {"core": {"1": -170.0}}} (map -> role -> team -> deg added to the
  spec's yaw); {} = as before. The red core is unchanged (not asked; its marker says 90, the mirror of -90).

## 2. "The core must not attack (no invisible turret on top)" (C data, C traffic)

- Core templates `0x40000C8A` / `C89`: `0x10000328 = 0x34000014` (the turret attack), `0x10000B76` 185, `0x10000B84`
  25, `0x10000133` 10, `0x10000C5D = 1` (warning ring), flags `0x1000019D = 0x4010` (the Turret bit 0x10 set) (C).
  ics read the attack like a turret's (`SHOOTERS` includes "core"), so the core shot everything in 10 m: traffic 16:53:54
  - 16:58: `core t1: target ...`, `scriptlet 0x10000326` / `0x1000029D` once a second; server.log "AI: Poison Ivy takes
  185" (16:55:02 - 16:55:33, the bot died at 16:55:40) and the red minions w32-w36 killed at the core.
- `[ics] match_unarmed_roles` = ["core"]: `Units.spawn` drops the attack, `Units.think` never gives such a unit a
  target, `_properties` sends `0x10000C5D` / `0x10000C5B` = false in the creation bundle (no ring for a structure that
  does not shoot). [] = as before.

## 3. "Enemy minions cannot attack my core" / "the enemy champion cannot either" (C traffic, C sim)

What the run shows (C):
- `structure down: core_turret t1` at 16:55:15.964, then `core t1: attackable (0x100007d9 = true)`, its modifiers, the
  bundle and `Vfx_Indestructible_Stop`: the core was unlocked and unshielded, server and client.
- From then to the surrender: **no "core t1 takes"** line. The red minions near the base (w32 at x 23-29, 16:55:16-23)
  shot the blue wave w33 that had just spawned at the lane mouth (21.8, 77.5) (decoded shot targets: `0x...273` = a w33
  unit; Poison Ivy's basic attacks at 16:55:20 also `0x...273`) and died to the core's 185-damage shots; the bot,
  at 14 % health from the core, recalled and died. No damage was blocked: `World.damage` was never called on the core.
- So the shared cause is item 2 (the core killed or chased off everything that came near it) plus the target order
  (minion, champion, structure: fresh blue minions spawn right at the core every 30 s).
- A second, smaller cause (C, sim): a melee minion's sight is its smaller vision 3.0 (`match_minion_vision` "min"),
  measured to the target's centre; the core's footprint blocks 3 m round it, so a melee minion that walked to the core's
  rim (17.4, 74.5) stood there idle with no target.
- Fix: item 2, and `[ics] match_structure_sight_to_edge` (true): `Units.enemies_near` counts a structure's distance to
  its edge (centre - `match_structure_radius`). The bot needs no change (its sight 9 m reaches the core's centre; with
  the core unarmed it no longer backs off / dies there; `bots.py` is another agent's file).
- Sim (`tests/test_match.py core_door_regen_1530`, scratch `m1530/probe2.py`): blue lane opened, blue minions removed,
  the red waves take the core from 4000 to 0 in ~70 s; a red melee minion placed 0.2 m off the rim takes the core.

## 4. "An activated blue door, always, near the blue base exit next to the fence" (C absence, G position)

- No Crime Alley static, layout entry or marker places a door (`map-object-census.md` 1.1; the session's
  `ca_statics.json` has no door world state between x 22 and 45), and the original's frames in the notes describe only
  the countdown base gate (`crime-alley-2v2-video.md` "Base gate", `crime-alley-video-compare.md`) (C).
- Door candidates (C, catalog): the base gate `0x2E000CD7` (child wall `0x2E000CD8` lit by side 3 / 5 / 1 through
  Object_Closed, `crime-alley-visuals.md` e: the blue wall the countdown gate already draws in Crime Alley), the Tutorial
  1 bridge gate `0x2E0010F3` (its light wall `0x2E0010F4` stays white), `0x2E0012B7` / `0x40000C6E` (show nothing).
- `[ics] match_decor_doors` (`Match._spawn_decor_doors`): per map a list of {world_state, pos, yaw, team, side, scale
  (0x6B4), scriptlets}; Crime Alley: `0x2E000CD7` as a bare world state (no class `0x40000557`: no collision polygon,
  P), team 1 side 3 at **(33.0, 83.2)** and team 2 side 5 at **(127.0, 83.2)**, yaw 0 (a wall along x on the north
  curb just past the base exit), scale 0.4 (the model is 21.8 m wide), Vfx_OnInit + Object_Closed, team again as a
  change; never opened. Position / size / orientation G: the tester's screenshot did not arrive. The tester gives the
  spot ("move it N m", "turn it 90", "smaller") or `{}` removes them.

## 5. "My dampener does not regenerate even though time passes" (C logs; G rate)

- Respawn (C): the dampener fell at 16:52:43.514, line 64 ("reactivating") at 16:57:13.489, `old body gone` + a new
  object (new IID `0x...29B`), Object_Activate / Vfx_Active / Vfx_AI_Active and line 63 at 16:57:43.5: exactly
  `match_dampener_respawn` 300 s. The red wave (elites, `match_supers_on_structure_down`) and the bot destroyed it again
  at 16:58:03 (20 s later), so it may have looked like it never came back.
- Health (C): before that, it sat at 504 / 3000 from 16:50:20 to 16:52:20 with nobody hitting it: ics never heals a
  structure. No regen value in the dampener template (`0x40000C88` has no `0x10000140`; the core 10, the PCT 50, meaning
  unknown, C).
- `[ics] match_structure_regen` = {"dampener": {"per_second": 15.0, "after": 10.0}} (G): a damaged structure of a listed
  role that no hit reached for `after` s heals `per_second` HP a second (`Match._structure_regen_tick`, vitals at most
  once a second; the protection snapshot `shield_hp` follows). {} = no regen.

## 6. Turret heads still lost (C rules, O cause; diag added)

- This run, the turrets got only: `0x10000C66` target changes, the shots `0x100002E0` (Object_Ranged_Attack) and
  `0x1000029D` (Vfx_Basic_Ranged, our `match_turret_shot_extra`), hit fx `0x10000223` from AGL, and at spawn / unlock the
  flags / team / vision changes (traffic, C). No Target_Acquired / Lost (fase3-iw).
- Data (C): body `0x1D00035D` Object_Ranged_Attack = a type-23 run of Vfx_Basic_Ranged (so ours is a duplicate network
  run) + a type-26 group; Vfx_Basic_Ranged (`0x1D000372`) = the side-switched beam meshes; Vfx_AI_Active = type 12
  spawn of `0x2E000AA8` at attach `0x100000FE`, Vfx_Startup, scale 0.9; the head's tables (`0x1D00035C` + `0x1D00038B`)
  hold only Vfx_Startup / Vfx_Targeting / colours. Vfx_Stop (four type-23 stops incl. Vfx_AI_Active) is run by nothing
  we send. `_Entity_OnSetClientRelationship` re-runs Vfx_Active (not AI_Active) on team changes.
- Client rule (C, `client-scriptlets-graphs.md` 1.4): no run replaces another; a run ends by its children ending, a
  signal / stop (same instance number) or its object's removal. None of our messages to the bodies reuses the
  Vfx_AI_Active run number, so the cause is not decidable from the logs (the tester gave no time).
- No behaviour change. **`python tools\diag.py --heads`** (alias `--cabezas`): with the call stack, every end of a
  spawned child (`0x666b40`, owner IID), of a render effect (`0x65ca30`), every run removal (`0x57baf0`) and every server
  0x8D start / signal (`0x6279d0`, did / instance). Steps: start the match, run the diag in a second console, walk into
  an enemy turret's range until its head goes, Ctrl+C, send diag.log + server.log + traffic.log. The END line whose owner
  is the turret's IID (server.log `spawn turret mid t2`) and the frames under it name the trigger.

## 7. Recall: the six converging lights (C traffic, C client rule, P cause)

- Traffic 16:39:25.962: the fx `0x10000223` (fx `0x1E00009C`, 8 s) with Fidgets_Disable and Recall_Start, then
  "again after its bundle" four times **with the same run number** (+0.03, +0.28, +0.31, +5.36 s), the stop at
  16:39:34.042. A live run's own number is a signal to it (list-2 handlers run) (C, client-scriptlets-graphs.md 1.4).
- The streaks are the fx's type-3 spawn (aggro-recall-scorepanel.md 2.2). Its property set is the client's timed
  indicator object: `0xA847E0` (C, decompiled) builds a local object from a record (+0x10 elapsed / +0x14 duration ->
  `0x10000945`, `0x10000944` = 1.0, `0x450`, `0x655`; DIDs `0x10000942` / `940` / `941` / `943` from +0x30 / +0x38 /
  +0x2C / +0x34), gated on `0x588ce0` and a non-null DID `0x10000099`; callers `0xA884A0` (`0x100008D5`, then key
  `0x10000381`) and `0xA88590` (`0x100008D8` elapsed, `0x100008D7` duration, `0x1000093F`, then key `0x10000380`). P: the
  streak object's start / loop / end fx follow its run's signals, so the re-sends ended it while the glow (a light
  container) lived on.
- `[ics] start_scriptlet_hold_mode` = "defer" (`CastWorld.run_scriptlet`): the held key goes once,
  `start_scriptlet_hold_defer` 0.12 s after the scriptlets of its own tick, is not a looping key and is never re-sent;
  the StopScriptlet ends it as before. "resend" = the fase3-ij hold. O: if the glow is lost with "defer", what ended
  the first run before fase3-ij is not the re-sends' business: `diag --heads` during a recall (owner = the champion)
  names it.

## Tests
`tests/test_match.py core_door_regen_1530` (10 checks): the blue core's heading, the unarmed cores and their ring flags,
no core shot / target at a minion on its rim, a red melee minion on the rim takes and hits the exposed core (and the
centre rule with the switch off), the data attack kept with `match_unarmed_roles` [], the two lit decor doors after the
start, the dampener's regen after 10 s and none with {}, the recall fx sent once. `leash_turret_ring_camp_drop` checks
the "resend" hold with the mode set.
