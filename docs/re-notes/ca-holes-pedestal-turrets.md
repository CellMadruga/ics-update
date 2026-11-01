# Crime Alley: black sections, base hologram pedestal, lane turret heads (2026-10-29, fase3-ih)

Tester report 2026-10-29 12:45 (Crime Alley v AI, run 12:12-12:24, AGL vs bot Harley Quinn). Evidence: logs of that
run, our recording `2026-10-29 12-09-37.mp4` (match 3:30-14:45), the original Crime Alley video
`crime_alley_map_video.mp4` (Cyborg, v AI), the tester's frame of the original (Cyborg's base at 00:28) and
`agl_video.mp4` (that one is Gotham Heights / Coast City: no Crime Alley turret in it). Frames were extracted to the
session scratchpad only. Tags: **C** confirmed, **P** probable, **O** open. Builds on `map-load-holes.md`,
`map-audit-all.md`, `crime-alley-structures.md`, `stubborn-visuals.md`. No diag ran during this match (diag.log covers
10:44-11:02 and 12:41, other maps).

## C1. Black sections in the centre (C cause, fix in the pack)

- Where: our frames 6:30, 7:00, 10:00, 12:15, 13:00 (turret at x 65 as the scale anchor, ~45 px/m): black strips on
  the north sidewalk x 70-75, y ~80-85 and on the south one x 70-76, y ~65-70. The original at 2:36 (same camera
  spot) draws ground there.
- Why: terrain record `0x800113BB` (C, heights read from the installed pack, metres):

  | y \ x | 55 | 60 | 65 | 70 | 75 | 80 | 85 |
  |---|---|---|---|---|---|---|---|
  | 85 | 200 | 200 | 200 | 200 | 200 | 200 | 200 |
  | 80 | 200 | **0** | **0** | **0** | **0** | 198.5 | 200 |
  | 75 | 200 | **0** | **0** | **0** | 200 | 198.6 | 200 |
  | 70 | 200 | **0** | **0** | **0** | 200 | 200 | 200 |
  | 65 | 200 | 200 | 200 | 200 | 200 | 195 | **0** |

  The street statics cover the socket's middle (the lane) and the sidewalks west of x 70; the quads at x 70-80 that
  touch (70 / 75, 80) and (70, 70) are bare 200 m funnels, drawn black. `map-audit-all.md` 2.2 kept this socket
  ("not seen, frame 6:12"): wrong for the sidewalks.
- Not the cause: missing statics (every world state of blocks 12BB / 13BB / 14BB has its record in a loaded pack:
  map pack, `0xA00002E5/E6/E7`, the resident packs; re-checked), layer textures (the grid `0x1300008C` of the six
  outer blocks lies outside the play area), unloaded border blocks (the `0x82` records of 12BA / 12BC / 13BA / 13BC
  are empty).
- Fix: `icserver/terrainfix.py` site `crime_alley_lane_turret`: vertices (60, 70), (65, 70), (70, 70), (60, 80),
  (65, 80), (70, 80), (75, 80) -> 199.98 m (median of their rings); 22 normals: central differences around them and
  (0, 0, 1) at the raised vertices themselves (new site option `raised_normals_up`; their stored normals lean into the
  pit, e.g. (0.79, -0.26, 0.55)). The y 75 row stays at 0 m under the lane cover, so no triangle gets three raised
  corners (`whole_triangles` 0): collision stays inside the record's MOPP tree. CRC 0xF375_46A7 -> 0x7534_9554.
  `[game] terrain_sockets` default includes it; `python ic.py patch` writes it (backup in
  `0xa0c112ba.rp.terrainfix.json`).
- Open (O): the south alcove (85, 50-65) / (90, 55-60) / (80, 65) is also at 0-195 m, behind the south buildings
  (statics at z 196-197 there, e.g. `0x2E000B59`, `0x2E000B53`): not seen black, not touched. If a black patch
  remains south of the lane at x 78-90 after the patch, that is the next site.

## P1. Base hologram pedestal (C data, P look)

- Original (tester's frame, 00:28): the champion hologram stands on a stone plinth with a glowing disc at the west
  rim of the gear-shaped spawn platform. Ours (3:45): the hologram floats over bare sidewalk.
- Tutorial 1's statics (same base kit): block `0x14CB` platform `0x2E000A35` (5.5, 37.5) yaw -90, core pedestal
  `0x2E000A3B` (17.5, 37.5); block `0x13CB` (its west neighbour) **`0x2E000A36` at (159.2 -> -0.8, 37.5, 200.24)
  yaw 90**, next to `0x2E00121A` (-4.51, 34.57) and `0x2E00081F` (-4.81, 38.59). Crime Alley's block `0x12BB` has
  exactly those two neighbours at (-4.51, 74.57) / (-4.9, 78.48) but **no `0x2E000A36`**; no other static and no
  scriptlet table of any pack names it (scan of every pack).
- `0x2E000A36`: `.entity 0x2D00085F`, creation type 8 (a placed object the client accepts from the server), mesh
  `0x1700142A` (vertex format not decoded by uesrv), material `0x140002C1`, tables `0x1D000385` and the team-colour
  `0x1D00038B`, a side map on `0x100007A2`.
- Fix: `[ics] match_map_objects` crime_alley: pedestal at (-0.8, 77.5, 200.21) yaw 90 (team 1, side 3) and
  (160.8, 77.5, 200.21) yaw -90 (team 2, side 5), Vfx_Startup + Vfx_Active_Blue / _Red. Positions = Tutorial 1's
  offset applied to Crime Alley's platforms `0x2E000CA5` (5.5 / 154.5, 77.5).
- Open (O): what draws the hologram itself (no static at the spot; P part of the server's base aura `0x2E000A35` at
  (5.0, 77.5), 0.5 m east of Tutorial 1's). If the hologram does not stand on the disc, move the pedestal by 0.5 m
  (x -1.3 / 161.3) or the aura to 5.5 / 154.5.

## O2. Lane turrets (C data, P cause)

- Original (CA video 1:24 at x 40, 2:36 at x 65): gear plate, dark body with a glowing team-colour column, and a tall
  cyan hologram on top with blades turning around it, visible all the time.
- Ours (13:00, 7:00, 10:00): plate, body, cyan column; the tall hologram with its turning rings appears **only while
  the turret fires, and white**. The models are the right ones (body `0x2E000AA0`, classes `0x40000C8C` / `C8B`,
  head `0x2E000AA8`, plate `0x2E000A9F`); the colour is not.
- Data: head table `0x1D00035C` = Vfx_Startup, Vfx_Targeting, base `0x1D00038B` (Vfx_Startup, Vfx_Active_Red /
  Purple / Blue, Vfx_TeamColor_SetParentColor). Its Vfx_Startup picks appearance `0x19000A61` by side `0x100007A2`
  (the appearance of the camps' colour fix: no side = Null colour). The server head was created with the team only,
  no side and no team change -> Null, white (P strong). Body table `0x1D000372`: Vfx_Active = damage-phase child
  `0x2E000A9E` + team particles `0x180006CD` / `CE` / `CB` / `0x18001432` chosen on the side; Vfx_AI_Active = child
  head `0x2E000AA8` spawned by the client itself (0x67C = 1, scale 0.9, Vfx_Startup).
- Fix: `[ics] match_turret_head_side` (default true): the head gets the body's side (3 / 5) in its bundle and the
  team as a change (0, then the team, unit_flags_delay + 0.1 s), so its colour keys and the client's relationship
  handler tint it.
- Open (O): (a) whether the hologram also stays visible when idle once tinted; (b) the outer turret also gets the
  body's Vfx_AI_Active, so the client may draw a second head (scale 0.9) inside the server's: if the tester sees a
  doubled head, set `match_turret_heads` to {} for "turret" (the client child stays) or drop Vfx_AI_Active from
  `match_structure_scriptlets["turret"]`; (c) the inner turret (x 40 / 120) gets no body scriptlets at all (no
  "inner_turret" key in `match_structure_scriptlets`): if it lacks what the outer one shows, add
  `"inner_turret": ["Vfx_Active", "Vfx_AI_Active"]`.

## Tester checklist

1. Close the game, `python ic.py patch` (prints "crime_alley_lane_turret ... flattened").
2. Crime Alley v AI: the sidewalks east of the blue lane turret (x 70-75) show ground, not black.
3. Each base: a stone plinth with a disc under / next to the champion hologram, west of the gear platform.
4. Lane turrets: the hologram on top is blue (ours) / red (enemy), not white; note whether it shows while idle and
   whether it looks doubled.
