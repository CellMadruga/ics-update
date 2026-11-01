# AGL off the floor, the Raider pad half sunk, the Power Core Turret's platform (2026-10-30, tester report 14:51)

Tester run 14:48-15:11 (Crime Alley v AI, Atomic Green Lantern vs AI Cyborg; `diag --layers` twice, then
`--strip`), recording `2026-10-30 14-51-59.mp4` (11:11, 30 fps; video time t = wall clock 14:51:59 + t). Logs:
server / traffic / diag of that run (unhandled empty). Frames were extracted every 2 s (plus crops) into the session
scratchpad only (`v1451/`); nothing of the game is in the repo. Tags: **C** confirmed (logs, data, tests), **P**
probable, **G** from the frames, **O** open.

## 1. "AGL is very far off the floor" (C traffic, P path, fix by test)

### 1.1 What the server sent (C)
The player's champion goes to the client only in its full champion + player bundles (credits / XP / level / cast /
teleport; the per-tick deltas are not logged). Its 0xB0 position in those bundles (traffic, 123 bundles):
- 14:50:44 - 14:53:51: z = the navmesh's (200.08 on the lane, 200.12-200.28 on the base platform).
- From 14:53:57 (6 s after Cyborg's Charged Burst teleported AGL, 14:53:51.145): 200.13, 200.23, 200.43 (14:54:53),
  then after the recall 200.65 / 200.70 (14:55:2x on the lane, navmesh 200.08), 200.85 (14:57:15), 201.00 (14:59:39),
  201.32 - **201.52** (15:01:28 - 15:01:54, blue base, navmesh 200.15). Each value is the client's last move-order
  height (`move -> (x, y, z)` in server.log, 200.1 -> 200.5 by 14:55 and higher later): the client picks the clicked
  point on a plane at its champion's drawn height, so a champion drawn too high makes every next click higher (the
  "floating Batman" creep of fase3-hd). The recall / respawn teleports went at the spawn z 200.3 (navmesh 200.28).
- The client applies the bundle's position to its own champion: 0.6 - 1.4 m over the ground from ~14:55 (video 3:00)
  to the end; frames 6:28 - 9:44 at the blue base.

### 1.2 Why the server kept the click height (P)
`World.snap_to_ground` puts walkers on the navmesh at every walking step and in `World.bundle` / `World.delta`; a
simulated match (cast every AGL slot, Cyborg's slots on AGL, 400 ticks of re-clicks at 200.65) never left the
navmesh. Not found: which path left the click height in `ch.pos` in the real session (candidates: a script teleport /
forced-movement end that keeps a point's z, `CastWorld.motion_end`, and the session's champion + player bundle
`Session._objects`, which never snapped). Not the carry: the Super Strength lift / throw was at 14:51:27-30, the drift
began at 14:53:57.

### 1.3 Fix (C by test)
- `[ics] ground_path_from_navmesh` (true): `World.walk_to` gives every path corner the navmesh's height, never the
  clicked point's (champion and units).
- `[ics] ground_snap_standing_champion` (true): `World.tick` puts a standing champion back on the navmesh each tick
  (the per-tick state carries it).
- `[ics] champion_bundle_snap` (true): `Session._objects` snaps the champion before its bundle.
- Each correction is logged at most every 5 s: `<name>: z A off the navmesh (B) at (x, y), put back (standing |
  bundle)`. The next run's server.log names the moment (and so the path) that lifted it.
- `tests/test_match.py` `agl_floor_pad_platform`: walking under creeping clicks, a champion left at 201.52, the path
  corners.

## 2. The Raider pad: "half of it disappeared" (G frames, C data, P height)

- Frames 5:44 / 5:46 / 5:48 (14:57:43-47, AGL on the pad): the pad's south two thirds lie on the gravel; its north
  third (~2.4 m of 7 m) is cut by a straight east-west edge at y ~98.4 and hidden under the paved floor north of the
  nook. The cut stays put when the camera moves (geometry, not a screen effect).
- Data (C): terrain flat 199.98 m at (65-95, 85-100) (`0x800113BB`); navmesh 200.08 over the whole nook; no static with
  a box over the nook besides the decal `0x2E0011AF` (DXT5 texture only) and the whole-map pieces; markers
  `0x2E000944` / `945` (80.0, 97.25, 200.08) and **`0x2E001117` / `0x2E001120` (79.96, 97.13, 200.20 / 200.22)**.
- At 200.3 (fase3-is) the plate showed whole but floated over the gravel; at 199.98 (top 200.07) the paved floor
  covers it. So that floor's top is between 200.07 and ~200.3.
- Fix: `[ics] match_nook_pad_z` = **200.2** (the 1117 / 1120 markers' height, P the original's placement; top
  200.29). O: if a sliver still sinks, 200.25 - 200.3; if it looks afloat, 200.15.

## 3. The Power Core Turret's platform (P identification)

- The video has no tour / showroom: the showroom list was only prefetched (14:51:30, 148 items) and no
  "showroom Vitrina" line exists in this or the earlier copied runs. Frames 7:14 - 9:44: our PCT (white translucent
  cylinder + flag head) stands on the round core platform's edge, no prow under it.
- Candidates (showroom.txt, pack `0xA00002E6`, unlabelled): most are already known children (A3D / A3E core
  children, C5E / CF4 / D1E / 13AC core / turret effects, D13 / D14 / D15 meteorite orb parts, D40 stealth piece,
  E38 drop pod, FAB pulse emitter, 1037 Foundry, 103B core iris, 104E Raider drop, 1314 superpad).
- **`0x2E000A8E`** (`.entity 0x2D0008A6`, ctype 8): the only unplaced piece of the base-statics family. Table
  `0x1D000385` = the core pedestal `0x2E000A3B`, the base pedestal `0x2E000A36` and the gear plate `0x2E000A9F`;
  `0x303 = 0x480000FC`, `0x57A = 0x41` as that plate; its id lies between the core's pieces (A35-A3E) and the
  turret's (A9A-AA8, AC3-AC5). No static, cinematic or table of any installed pack names it (raw scan of every `.rp`:
  only its own record in 0162 / 0168 / 0256 / 02E6; the plate A9F is placed 18 / 21 times in 024C / 02E5). P: the PCT's
  prow / socket platform. Not confirmed by its mesh (the `.entity` -> render-mesh link is unresolved, as for AC4).
  Other unplaced, unexplained ones: `0x2E001349` (table `0x1D00090A`), `0x2E000C5C` / `C5D` (no table).
- `[ics] match_structure_platforms` = {"crime_alley": {"core_turret": {"world_state": 0x2E000A8E, "forward": 0, "yaw":
  0, "dz": 0}}}: `Units._spawn_platform` places it under each Power Core Turret, team 1 facing east, team 2 west, with
  the team and side, once per match (stays when the turret falls, as the plate). The turret composite is unchanged.
- O: the model's front and origin. If the point faces the core, `yaw` 180; sideways, 90 / 270; if it is off the
  socket, `forward` (m toward the lane); if it is not the prow at all, `{}` and show `0x2E001349` with the showroom.

## 4. Other things in the video
- 0:04 - 1:44: the `--layers` diag (consoles over the game); the camera parked at the fence strip.
- 1:46 - 1:58 (14:53:45-57): AGL loses ~600 HP in 6 s to Cyborg + the red wave while in the lane (bot balance, not a bug
  as such).
- 4:00 - 4:10 and 6:14 - 6:26: the grey death view (AGL died twice; traffic LifeState 2).
- 9:44 - 9:56 (15:01:43-55): the tester's surrender passed at 15:01:45 ("match over: team 2 wins"), the blue core blew
  up, DEFEAT; but Cyborg kept casting on AGL until 15:01:54 and AGL was "defeated" 9 s after the match was over (the
  bot AI / combat keeps running in the end sequence).
- 10:00 - 10:50: the post-encounter comic video; 10:56 on: the Scorecard (another agent's area).
