# Crime Alley: the black strips beside the blue lane turret (2026-10-29, fase3-ik)

Tester report 2026-10-29 16:40 (Crime Alley v AI, match 16:34-16:36, AGL vs bot Green Lantern): black areas on the
ground in the middle of the map. Evidence: screenshots `49.webp` (match 00:29, after the 15:16 pack patch) and `46.webp`
(14:4x run, before it), `logs/server.log` and `logs/diag.log` (`--mapload`, 16:33-16:36) of that run, the installed
map pack `0xA0C112BA`, the decompiled client (`re-work/decomp`), and frame 2:36 of the original Crime Alley video
(cah/cav in the session scratchpad). Frames, textures and crops stayed in the session scratchpad. Tags: **C**
confirmed (data / code read / measured), **P** probable, **O** open. Builds on `ca-holes-pedestal-turrets.md` C1,
`map-load-holes.md`, `map-audit-all.md`, `camps-colour-bar-positions.md` 3.1 (camera model).

## 1. Where the black is (C)

- Camera: the client's own model (`camps-colour-bar-positions.md` 3.1: pitch 57, vertical FOV 45, 17.5 m along the
  view, screen x = world +x), target = AGL. At 00:29 (16:35:06 start + 29 s) AGL stands at (71.5, 75.4) (last
  move order 16:35:31, next one 16:35:41). With that target the four stealth tiles of `ics/match/maps.py` land within
  ~10 px of where they are drawn (north tiles (76-84, 81.3-83.3) -> screen x 1204-1660, y 135-212; seen 1210-1660,
  130-205); the turret at x 65 lands at its base.
- North strip (`49.webp` screen (867-1215, 142-205)): x 70.0 -> 76.2+ (it runs on under the tiles), y **81.5 -> 83.1**:
  between the north edge of the lane mesh (y 81.5) and the fence's base (fence pieces `0x2E001324` / `0x2E0012F6` /
  `0x2E0004D7` at y 83.65, boxes from y 83.25). Its west edge is not a grid line: a straight line from (70.07, 81.47)
  to (72.36, 83.11); a grey-brick wedge of ground lies west of it.
- South strip (screen (836-1222, 732-HUD)): x **70.0 -> 75.1**, y 71.7 (south edge of the lane mesh) down to 70.4
  (where the HUD starts). The debris pile `0x2E0002D0` (72.89, 69.93) is drawn inside it.
- `46.webp` (same spot, before the 15:16 patch; fitted the same way, target (72.6, 74.9)): the north strip was larger,
  its west edge the grid line x = 69.9 and black also above the fence base at x 70-71.5; the south strip x 69.8-74.9.
- What the ground there should be: the original (frame 2:36) shows grey bricks and the curb on both strips (not
  black, column medians 20-100 of 255; ours 3.5 north). The baked colour texture of the terrain shows exactly that
  (section 2.2).

## 2. How block 13BB's ground is drawn (C)

### 2.1 Only the baked patches

- `0x714280` (landscape render build; both callers pass param_5 = 1) takes `0x712310` + the far branch of `0x713DD0`
  (`0x7132D0` per patch) when byte +0x58 of the render block is set, else `0x712860` + the near batches (`0x713C10`).
  +0x58 is the first of the two bytes `0x547740` reads after the three u16 arrays.
- That byte is **1 in 13BB only** (record +0x81DC); 12BB / 14BB / 13BA / 13BC have 0 and no far patches. 13BB has 16
  far patches of 40 x 40 m (9 x 9 vertices, 128 triangles each, the second 6144-index array), material `0x140002C5`,
  three textures each `0x1300341E + 3k` .. `+2` (2048 x 2048 DXT1 colour, 1024 DXT5 normal map, 1024 DXT1), all in the
  map pack. The diag of this run agrees: every other block lists its near batches, 13BB lists none.
- So for 13BB the near batches, their palettes, blend masks and layer textures and the record's stored normals are
  never used (candidate (b) is out for this block): `0x712310` takes the positions from the heights at +0x3C (vertex
  (i, j) = (5 i, 5 j, h[i * 33 + j]), as the patch writes them) and writes constant normals (`0x711B10`).
- The patches' stored boxes: (40-80, 40-80) and (40-80, 80-120) say z >= 179.96 although (60-70, 70-80) + (75, 80) are
  at 0 m in the installed record: the bake predates the lane-turret socket (the other 14 boxes match the heights).

### 2.2 The baked textures at the strips

`0x1300342D` (patch x 40-80, y 40-80) and `0x13003439` (y 80-120): lane cobbles between curbs at y 72.0 and 82.2,
grey-brick sidewalks outside them, the turret's ring in the normal map at (65, 77.5). Nothing black at either strip.

## 3. South strip: a funnel still open (C cause, fixed)

- Installed heights (after the fase3-ih site, m): row y 75 = 200 / **0 / 0 / 0** / 200 at x 55 / 60 / 65 / 70 / 75.
- The far patch splits each cell along (x0 + 5, y0) - (x0, y0 + 5). Cell (70-75, 70-75) has the triangles
  [(70, 75), (70, 70), (75, 70)] and [(75, 70), (75, 75), (70, 75)]: **both end at (70, 75) = 0 m**, so the whole cell
  is a 200 m funnel. The lane mesh covers it only north of y 71.7; the 1.7 m south of that are the south strip's
  visible part (x 70-75 exactly = the cell's width). Before the patch the cell (70-75, 65-70) was a funnel too
  (`46.webp`: the strip went further south).
- Fix: site `crime_alley_lane_turret` now also raises **(70, 75)** (CRC `0xFD6B_E526` -> `0x3979_96D8`, 8 heights and
  24 normals). (60, 75) / (65, 75) stay at 0 m: everything around them is under the lane mesh and the turret.
  `whole_triangles` = 3 (one far triangle [(70, 75), (70, 80), (65, 80)] has all corners raised): such triangles may
  leave the record's MOPP tree (`map-audit-all.md` 9.1). Picks inside this socket already returned z 200.1 in this
  run (move orders at (60.9, 74.5) and (64.9, 74.6) at 16:35:21), so the ground pick there does not use these
  triangles (P).
- `apply` handles the redefinition in one run: a site in an unknown state whose backup bytes plus untouched installed
  bytes give its original CRC is put back first ("an earlier version of this site was flattened; restored from the
  backup first"), then patched. Checked on a copy of the installed pack: restore -> patch -> second run "already
  flattened" -> all off = md5 `35e55d3e...` (the install).

## 4. North strip: not the terrain data (C), a shadow from the turret's spot (P), O

- The cell under it (70-75, 80-85) has all four corners at 199.98 m since 15:16 (installed pack, read back through
  `icserver/rp.py`), its two far triangles are flat, the baked texture there is grey bricks and the curb, and only one
  pack holds `0x800113BB` (C). No static covers (70-76, 81.5-83.1) (statics of 13BB with their `.entity` boxes; the
  lights and markers there are type 10 / 3) and no server object stands there (C).
- The patch changed it (C, `46.webp` vs `49.webp`): the funnel's grid-line edge (x 70) and the black above the fence
  base are gone, and a wedge of grey bricks appeared. So the client draws the patched heights.
- What is left is bounded by a straight line through (70.07, 81.47) and (72.36, 83.11), slope 0.72. Extended, it
  passes within 0.4 m of the blue lane turret (65, 77.5) (6.4 / 9.3 m away), not through AGL: a ray from the turret's
  spot. The black side is the one turned away from the turret. This is the shape of a shadow cast from that point:
  the fog of war's vision circle of the turret with an occluder (`0xAAE0E0` draws each source's circle and the
  shadows of the occluder entities listed at [source entry +0x4C] + 0xC0; the fog only darkens ground materials, which fits the lane
  mesh and the debris staying lit), or the turret light's shadow (P, which one is O). The mirror sidewalk (x 84-88) is
  dim, not black (21.9 vs 3.5).
- The turret and AGL both stood on the lane-turret socket, whose centre is at 0 m (AGL's ground there: ~76 m at
  (71.5, 75.4)). Raising (70, 75) changes that too; whether the north strip goes with it is the in-game test (O).

## 5. Ruled out (C)

| Candidate | Evidence |
|---|---|
| (a) heights / normals at the north strip | flat 199.98 m, two flat far triangles; the far path writes constant normals |
| (b) layer textures, blend masks, `0x1300008C` | 13BB draws no near batch; its 48 baked textures are in the map pack and correct at both strips |
| (c) a static drawn black | no 13BB static's box covers either strip except the debris pile (drawn lit) and the two whole-map pieces `0x2E001207` (street) / `0x2E001185` (a 200 x 100 m particle volume, texture `0x1300062F` = a streak) |
| (d) our objects | stealth tiles at (76-84, 81.3-83.3) / (74.6-78.6, 71.2-73.2) are drawn over the black, not in it; the rock (80.1, 72.8) and the plate (65, 77.5) are elsewhere |
| a stale pack copy | one pack lists `0x800113BB`; no file newer than the 15:16 patch in the game folder or its user folders |

## 6. To test (tester)

1. Close the game, `python ic.py patch` (it reports "an earlier version of this site was flattened; restored from the
   backup first" and then "flattened ... (70, 75)"), start the server and Crime Alley v AI.
2. Stand where `49.webp` was taken (lane centre east of the blue turret, ~(71.5, 75.4)): the south strip under the
   south stealth field's west end should be grey bricks with the curb.
3. North strip (between the lane and the fence, west of the two north fields): if still black, walk onto it (e.g.
   (73, 82.5)) and away again; if the black moves or shrinks with the champion or the turret's state, it is the fog
   (then `python tools\diag.py --fog` in a second console); if it never changes, send a screenshot from two camera
   spots.
4. Click the ground right next to the blue turret: if the cursor ring or a ground-target skill falls through the
   floor there, `crime_alley_lane_turret` must come out of `[game] terrain_sockets` (MOPP caveat, section 3).
