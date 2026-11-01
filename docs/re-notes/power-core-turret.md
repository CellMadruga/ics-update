# Power Core Turret, core shield ring, elites while it is down, more parked vehicles (2026-10-29)

Tester report 2026-10-29 from a video of the ORIGINAL game on Crime Alley v AI (frames 64-70, not in the repo):
(1) a third turret per side before the core; (2) parked vehicles missing (police car by the red base, a red vehicle on
the south curb, an old truck next to the blue middle turret, "another one at the bottom between the turrets"); (3) a
rotating ring round the core; (4) the third turret's death animation (two rings fall) and its remains (base with the
team's dot); (5) the ring goes when that turret falls; (6) super minions until it respawns.

Tags: **C** confirmed (data read), **P** probable, **G** guess (frames), **O** open. Scripts in the session scratchpad
(`pct/`), nothing of the game copied. Builds on `crime-alley-structures.md`, `crime-alley-still-missing.md` 3-4,
`stubborn-visuals.md` 4, `crime-alley-props.md` A, `vehicle-lift-and-position.md` 1.

## 1. The third turret is the Power Core Turret (C)

- Frame 70: "The enemy's Power Core Turret has been destroyed!" = announcer event 55 (`countdown-keymap-gaps.md` 3.2;
  56 = "our Power Core Turret is under attack"), on Crime Alley v AI. Frame 66 shows a health bar under the prow
  hologram: it is a structure of its own, not the core's child.
- So `crime-alley-structures.md` 1-2 (core turret = an extra tower, removed 2026-10-28) was wrong for v AI: the
  minimaps it read hide the icon under the core blob / the player's ring (frame 66: player ring at x ~26).
- Classes (C, v AI family in `0xA00002E6`): team 1 `0x40000C8F` (ws `0x2E000AC4`, entity `0x2D0008D4`, graph
  `0x1C000069`, table `0x1D00035F` + base `0x1D000374`), health `0x10000426` = 3500, `0x10000B84` = 35, `0x10000B76` =
  185; team 2 `0x40000C8D` (ws `0x2E000AA0`), 3000, 15, 175. Both: range `0x10000133` 9, `0x10000C5D` 1, credits
  formula `0x10000689` `0x3B000282` (tier `0x1000068A` 3), attack `0x34000014`. Twins `0x40000C8E` / `0x40000C86` (ws
  AA0, 3500 / 3000) are P the other CA encounters'.
- No placement data (C): an all-pack scan finds `0x2E000AC4`, `0x40000C8F` / `C8D` only in their own records / id
  lists; no layout or static places them (the map's type-3 markers skip `0x2E0011AA` / `AB`, G: the dropped pair).

## 2. Position (G)

Frames 66 / 67 / 70 at the in-game camera's scale (57 px/m across, ~47 px/m up the screen, calibrated on frame 68:
turret plate 6.26 m, the rock (54.7, 82.9), the jungle-mouth tile (51.9, 85.2)): the turret stands ~9.5 m east of the
core, where the prow leaves the round platform (frame 67: dx 510 px; 66: 550 px; 70 red side: ~550-600 px). Frame 66's
minimap: player ring at x ~26. **(27.0, 77.5) / (133.0, 77.5)**, +-1 m (`[ics] match_structure_pos`; navmesh there
y 69.6-85.1). The prow piece itself is still not in our build (O, `stubborn-visuals.md` 4).

## 3. Core shield ring (C keys, P look)

Core table `0x1D00098A` (pack `0xA0000162`):
- `Vfx_Indestructible 0x1000008E`: one type-35 action, child world state **`0x2E000A3A`** (entity `0x2D000863`, ctype 7,
  table `0x1D00037A`; the core pedestal is `0x2E000A3B` / `0x2D000864`).
- `Vfx_Indestructible_Stop 0x1000013D`: type 23 stop of `0x1000008E`, then type 34 particles switched on side
  `0x100007A2` 3 / 5.
- Neither key is in the turret tables. The name and frames 66 / 67 / 70 (ring while the turret stands, none round the
  red core after it fell) fit "core invulnerable while its turret stands". `[ics] match_core_shield`.

## 4. Death and remains (C table, P look)

`0x1D00035F` `_Defeat_OnDead 0x100001FA` (3 actions): type 23 stop Vfx_OnExplode `0x10000079`; **type 20 graph event
Death `0x100001C0`**; a type 9 branch (`0x1000000B`, `0x1000096F` ...), then Vfx_Destruct_State0 `0x100000EA`
(particles `0x18000B50`, side switch). The lane turret table `0x1D00035D` holds the same. The client never runs
_Defeat_OnDead on its own (as for the drones, `unit-death-slide-levelup.md` 1), and ics removed dead structures after
corpse_seconds: no fall, no remains. Now: `match_structure_death_scriptlets` {"core_turret": ["_Defeat_OnDead"]} and
`match_keep_body_roles` ["core_turret"] (the body with its side keeps the team's dot). Whether the lane turrets should do
the same is O (not asked; same table key).

## 5. Elites while it is down (C classes, P rule, G timer)

- No Destroyer Drone (ws `0x2E000AB5`) class is in Crime Alley's packs `0xA00002E5`-`E7` (C).
- The v AI minion family `0x40000C9A`-`C9E` (between the v AI structures `C86`-`C98` and jungle `CA0`-`CA2`, pack
  `0xA00002E7`) holds Elite Trooper `0x40000C9B` (ws `0x2E000E43`) and Elite Soldier `0x40000C9C` (ws `0x2E000E3E`),
  flags `0x410000` (the `0x400000` bit also on GD's Destroyer `0x40000E5F` and elites) (C).
- `[ics] match_core_turret_supers` {"crime_alley": {"melee": C9C, "ranged": C9B}}: while a team's Power Core Turret is
  down, the enemy's waves bring them in place of the melee / ranged pairs (as GD's dampener rule).
- Respawn: no time in the template (dampener vs core turret property diff: no timer) or a script (C), and no "Power
  Core Turret reactivated" line exists (only the dampener's 63 / 64). `[ics] match_core_turret_respawn` = 300 s (G, =
  match_dampener_respawn); the respawn removes the kept body, spawns a new one and plays the shield again.

## 6. Parked vehicles (C: none placed by data; G positions)

`crime-alley-props.md` A.1 holds: no Crime Alley static / layout / marker places a vehicle. Frames, same calibration:

| Frame | Vehicle | Class / ws | Position, yaw | Basis |
|---|---|---|---|---|
| 64 / 70 | police car, nose west | `0x40000459` / `0x2E0008B8` | (124.5, 81.9), 90 | 64: (125.3, 82.3) from the x 120 plate; 70: (123.5, 81.9) from the turret; north navmesh edge y 82.6 -> long side 0.23 m off the curb |
| 68 / 69 | gaslight pickup (flatbed, round lamps), nose east | `0x4000081A` / `0x2E000F03` | (52.4, 72.8), 270 | x 52.1-52.8 from the x 65 plate; south edge y 72.1 |
| 65 | red modern vehicle (P: the sports-car class, the only modern one not placed) | `0x40000454` / `0x2E000559` | (107.4, 72.8), 90 | (107.1, 71-72) from the rock (105, 82.7) and the x 120 plate; the pickup's mirror (107.6) |
| none | blue-base mirror of the police car | `0x4000081C` / `0x2E000F05` | (35.5, 81.9), 270 | G only, `"enabled": false` |

yaw = nose heading - 90 (the model's +y is its nose, `vehicle-lift-and-position.md` 1.2). The fourth phrase ("between
the turrets at the bottom") is read as the red vehicle of frame 65 (south curb between the red turrets); 69 is the same
frame as 68, so no other bottom vehicle is placed (O: a frame of it would settle it). `[ics]
liftable_props_added_by_map`.

## 7. Open

- The core's own Vfx_AI_Active also spawns `0x2E000AC3` (the turret head) at its origin (`stubborn-visuals.md` 4): with
  the Power Core Turret back, the tester may see a second hologram over the core; then drop Vfx_AI_Active from
  `match_structure_scriptlets["core"]`.
- Team 2's class uses the lane-turret body `0x2E000AA0` (data); if the red one looks unlike the blue one, try
  `0x40000C8F` for both teams.
- The core's client attack lock `0x100007D9` stays true after the turret respawns (the server blocks damage again).

## 8. Tester report 2026-10-29 21:10 (build fase3-in; run 21:03-21:10, AGL vs bot Catwoman in the log)

Screenshots: 71 (ours, blue base), 72 / 76 / 77 (original video), 64-70 (earlier original frames). Logs: this run's
server / traffic / diag (`--fog --ring --throwpress --destruction`). No structure fell in the run (the red lane turret at
95 was still standing at 21:09:53), so the supers rule and the red side were not seen in game.

### 8.1 Power Core Turret: no body under the hologram (C data, P cause)

- Frame 71: on the blue prow only the translucent "flag" hologram stands (= the PCT's own Vfx_AI_Active child
  `0x2E000AC3`, the same shape as the original's head in 66 / 67); the original also shows an opaque blue cylinder under
  it. Traffic 21:04:46-58: the class `0x40000C8F` was spawned, Vfx_Active + Vfx_AI_Active played, team set, as the lane
  turret, whose body draws.
- Tables (C): the PCT base table `0x1D000374` holds **Vfx_Fade_In `0x10000033`** (type-5 group: a type-35 render action
  with no child, then a type-23 stop of Vfx_Fade_Out `0x1000006A`); the lane turret base `0x1D000372` and the dampener
  `0x1D00063A` have no Vfx_Fade_In. Other differences: AC4 is creation type 8, the lane turret body `0x2E000AA0` 7; same
  graph `0x1C000069`; the red PCT `0x40000C8D` uses `0x2E000AA0`; twin `0x40000C8E` = C8F's stats on `0x2E000AA0`.
- Fix (P): `match_structure_scriptlets["core_turret"]` = Vfx_Fade_In, Vfx_Active, Vfx_AI_Active. If the body still does
  not show: (a) showroom items 91 (`0x2E000A9A`, the PCT's Vfx_Active child), 96 (`AC3`), 97 (`AC4`) tell which model
  is the cylinder; (b) `[ics] match_structure_classes`-style fallback is NOT implemented: the `0x40000C8E` twin would draw
  the lane-turret body but lose the AC3 head of frames 66 / 67.
- The prow platform itself is still missing (stubborn-visuals.md 4): neither AC4 nor the core pedestal `0x2E000A3B`
  (21.2 x 19.8 m) explains it (O).

### 8.2 The x 40 / 120 turret: ring pedestal and its head (C frames + data)

- Frames 72 (00:02, blue, ~10 m east of the prow tip) and 77 / 76 (red, x ~120): a round grey ring pedestal (not the
  gear plate of the x 65 turret, frame 68), a dark body with radial legs, the stacked ring hologram, firing. Frame 64 (6:22):
  the x 120 one already down (dark base, red dot) while the red PCT on the prow stands; frame 70 (6:51) "Power Core
  Turret destroyed" with the remains on the red prow. So the original has three per side: x 65 lane turret (gear plate),
  x 40 / 120 ring-pedestal turret, PCT on the prow; the PCT's place was right.
- The ring-pedestal turret is the **dampener class** `0x40000C88` / `0x40000C87` (C: world state `0x2E000E04`, rig
  `env_pvp_dampener_a` = ring, body, six legs; attack `0x34000014`, 3000 HP, 0x10000B84 25; table `0x1D00063A`:
  Vfx_Active child `0x2E000A9E` at +1.65 m, Vfx_AI_Active head `0x2E000AA8` scale 0.75 at -1.4 m). The 2026-10-28 swap to a
  lane turret came while the socket under it was a black hole (now flattened by the terrain patch `crime_alley_dampeners`).
- Fix: `match_role_swaps` = {} (the dampener at x 40 / 120, its own head, no gear plate, no server head).
- Tester's numbering (inferred): from the lane centre, 1st = x 65, 2nd = x 40 / 120, 3rd = PCT.

### 8.3 Vehicle by the blue base (G)

Frame 72: a dark gaslight truck on the north curb, centre ~4.6 m west of the x 40 ring (66 / 67: x 34-36.7). Placed:
`0x4000081B` / `0x2E000F04` (the left camp's truck, G) at (35.5, 81.85) yaw 270 (nose east, G), long side 0.7 m inside
the north edge 82.55 (navmesh), replacing the disabled police-car mirror.

### 8.4 The red car on the south curb (G)

Frames 65 / 76: red body, white top, chrome nose west, on the south curb at x ~105-107. Our sports car `0x2E000559` there
draws white (tester). The Crime Alley packs hold only seven vehicle world states (559, 8B8, 795, EFE, F03, F04, F05; the
red-looking siblings `0x2E0008A6` / `8B9` / `797` of classes `0x40000453` / `458` / `45E` are only in GD / CC packs, and
extra packs hung the load on 2026-10-25). Placed: the gaslight convertible `0x4000081C` / `0x2E000F05` (G: red with a white
soft top), same spot (107.4, 72.8) yaw 90. If it is not red, the arrow cart `0x40000C40` / `0x2E000EFE` is the last
untried one.

### 8.5 Police car (C: it is there)

`0x40000459` was spawned at (124.5, 81.9) (traffic 21:04:49.331 "spawn liftable vehicle 7"), rebuilt by 0x8B three
times and dressed like the others; diag `--destruction`: iid `0x200000000000138` built its 7 intact pieces on each 0x8B
(the other four 5 / 5 / 5 / 6). Navmesh height there 200.08, inside the north edge (82.55); our fog never hides props.
P: the camera never went there (the run stayed west of the red lane turret at 95, which still stood at 21:09:53).
Unchanged; the tester should check it at the red base's north curb (or `tour`).

### 8.6 Supers on the second structure

Server log: no structure died in this run (no "structure down"), so the fase3-in rule (elites while the enemy PCT is down)
never fired here; the tester's rule comes from the original. Now `[ics] match_supers_on_structure_down`
{"crime_alley": {"roles": ["dampener", "inner_turret"], ...}}: while the enemy's x 40 / 120 structure on the lane is
down, the waves bring Elite Soldier / Trooper; they stop when it respawns (`match_dampener_respawn` 300 s, with its
"reactivating" line). `match_core_turret_supers` = {} (kept as a switch).

### 8.7 Head opacity (C tables, P effect)

- The original's turret head is the body's Vfx_AI_Active child: its type-12 spawn action carries 0x325 = Vfx_Startup
  `0x1000018E` (scale 0.9 lane turret / 0.75 dampener / PCT 0.9 with AC3; 0x67C = 1), nothing else. Head tables:
  `0x1D00035C` (Vfx_Startup: type-34 overlay mesh `0x1700132C` coloured by side 0x100007A2 (5 red 0x3FF6B6B, 3 blue
  0x79DEFF, 6 yellow, 1 purple), Vfx_Targeting: graph events 0x1000009C, later 0x1000013D) + base `0x1D00038B`
  (Vfx_Startup: appearance 0x19000A61 group 0x10000004 by side; Vfx_Active_Red / _Blue / _Purple: appearance
  `0x19001299` group 0x10000002 = 0x10000002 / 1 / 3 -> materials 0x16002113 / 0x16002112 / 0x16002289).
- Ours sent Vfx_Active_Blue / _Red to the server-made heads at spawn and at every target loss (traffic: 23 + 7 times in
  this run), which the original never ran. P: that material set is the faint one.
- `[ics] match_turret_head_team_keys` false: the server heads get Vfx_Startup only; "active" in
  `match_turret_lost_head` is skipped. If the heads turn white or the targeting look sticks, set it back to true.
