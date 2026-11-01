# Crime Alley stealth tiles: alignment with the jungle-mouth corners (2026-10-28, second pass)

Context: tester report 2026-10-28 15:00 (session 14:39-15:00, build fase3-ie, Crime Alley v AI, AGL vs bot AWW): "both
side stealth fields are off; put the vertical zone back as it was; the idea is that it lines up with the collision edge
of that corner". Screenshots 43 (ours, east mouth, 00:37) and 44 (ours, west mouth, 02:00): the hex field crosses the
fence corner diagonally. 47 (original, match 02:26): the field runs straight down from the fence-corner pillar along
the fence. This pass replaces the 15:39 version of this note: the original's layout is now **measured** in calibrated
frames of the original video (section 4), which moves the vertical tiles' centre to y 85.2 and keeps the east side
mirrored.

Sources: the Crime Alley map pack `0xA0C112BA` (navmesh blobs, statics `0x820113BB`), packs `0xA000024C` /
`0xA000009A` / `0xA00000FC` (world states, `.entity` records), `ics/match/maps.py`, `ics/match/match.py`, the tester's
frames 32-47, the original Clash 2v2 video the tester plays (`Downloads\videoplayback.mp4`, 1280 x 720, match clock
= video time - 2:37) and the tester's recording of our build (`Videos\2026-10-27 13-22-10.mp4`). Frames were read with
OpenCV into the session scratchpad only (nothing of the game copied into the repository). `logs\` was empty when this
pass ran (cleared by 18:49), so the 14:40 spawn bytes are taken from the 15:39 pass and re-derived from the code
(section 1). Tags: **C** confirmed (code, data, bytes), **P** probable (calibrated frames, about +-0.15 m), **O** open.
Positions are metres in landblock `0x13BB` (the coordinates `ics` uses); yaw is counter-clockwise from +x and a tile's
4 m side lies along (cos yaw, sin yaw). Skeptic correction (section 9): the vertical tile's centre is about +-0.25 m
in y, not +-0.15 (the camera pitch dominates); 85.2 stays and 84.0 stays excluded. **Implemented 2026-10-29: section
10.**

## 0. Answer in short

- **Collision edge (C).** A champion's body stops on the champion navmesh's rim moved out by the agent radius 0.525 m
  (section 2). West mouth: the garden's side face **x = 52.725** (y 83.2-85.6), its lane face **y = 83.125** (corner
  **(52.725, 83.125)**), the garden-fence face **22.93 deg** through (54.005, 86.316), meeting the side face at
  **P = (52.725, 85.775)**. East mouth: side face **x = 107.075**, lane face y = 83.125, fence face **157.25 deg** through
  (106.797, 85.916), **P' = (107.075, 85.799)**. The east corner is 0.2 m west of a mirror of the west one (C).
  map-audit-all.md 4's "x 52.35 / 107.5, corner 30 deg" came from the 0.25 m raster (walkable cell centres plus the
  45 deg chamfer at the top pillar); the exact rim is x 52.2 / 107.6 and the fence 22.93 / 157.25 deg (C, correction).
- **The original (P, calibrated frames, section 4).** Each jungle mouth is an **L of two tiles**: a vertical tile (yaw 90)
  centred at **(51.7, 85.2)** / **(108.3, 85.2)**, whose inner long edge runs along the side face and whose south end
  starts at the garden corner, and a diagonal tile along the garden fence on the jungle-path side, joined at the top.
  The west tile's "+" maps to (51.71, 85.14) and (51.70, 85.16) in two frames with independently fitted cameras; the
  outer edges measure x 50.64-50.87 (west) and 109.27-109.34 (east): the original is **mirror-symmetric** (51.7 / 108.3),
  so its east tile stands 0.225 m off the east side face, as ours did "as it was".
- **What went wrong (C geometry).** 12:5x / 13:5x turned the vertical tiles 8 deg off the side face; the diagonal tiles
  (yaw 50 / 130, fase3-hz "G numbers") run 27 deg off the 23 deg fence: the west one's long edge lies 0.63-0.72 m past
  the top pillar's chamfer face and its corner (53.18, 84.83) is 0.46 m inside the garden, the east one's corner
  (106.82, 84.83) 0.26 m inside (frames 43 / 44). The 10:3x move (y 85.5 -> 84.0) put the vertical tiles 1.2 m south of
  the original: in frame 05:06 the original's "+" is 60 px above where a tile at y 84.0 would put it (section 4.3).
- **Recipe** (all long edges within 0.23 m of their face, all on the walkable side; section 5): blue vertical
  **(51.7, 85.2) yaw 90**, red vertical **(108.3, 85.2) yaw 90**, blue diagonal **(54.2, 87.5) yaw 23**, red diagonal
  **(105.8, 87.5) yaw 157** (= x -> 160 - x). Implementation plan in section 8 (maps.py, a `match_stealth_overrides`
  switch-back key, the override in `_spawn_stealth`, four test_match checks validated against the old and new layouts).
  No runtime diag is needed.

## 1. What our server sent (C: code; bytes as read by the 15:39 pass, traffic.log 14:40:24.972-.974)

`Match._spawn_stealth` (`ics/match/match.py` 626-676) spawns world state `0x2E000D36` per `maps.py` "stealth" entry at
the navmesh height + 0.03 m (200.11 here; the navmesh is flat at z 200.08 over x 47-60 / 100-113, y 81-90, C) with
heading = yaw + 90 deg (`ics/match/units.py` 38 `heading_from_yaw`), plus the hex mesh `0x2E000D37` and Vfx_Active.

| Strip | x (f32 bytes) | y | heading (f32 bytes) | yaw |
|---|---|---|---|---|
| 4 west vertical | 51.7 `cd cc 4e 42` | 84.0 `00 00 a8 42` | 3.2812 `7e ff 51 40` | 98 |
| 5 east vertical | 108.3 `9a 99 d8 42` | 84.0 | 3.0020 `37 20 40 40` | 82 |
| 6 west diagonal | 53.7 `cd cc 56 42` | 87.0 `00 00 ae 42` | 2.4435 `aa 61 1c 40` | 50 |
| 7 east diagonal | 106.3 `9a 99 d4 42` | 87.0 | 3.8397 `0b be 75 40` | 130 |

Tile frame (C): long (4 m) side along (cos yaw, sin yaw), short side across; `inside_strip` (match.py 678-687) tests
that rotated rectangle + `stealth_margin` 0.5 m. Confirmed again on our recording: the four centre tiles (yaw 0) show
their 4 m side along x (section 4.1).

## 2. The collision a champion meets: the champion navmesh's rim + 0.525 m (C)

- The client only snaps a click onto the navmesh of the champion's agent class and sends 0x20EE; the original server
  pathed on the same mesh (movement-collision-fog-map.md 1.3). Our server paths on the agent `0x10000003` blob
  (`maps.navgrid(..., agent_class=0x10000003)`, `ics/navmesh.py`), so the rim is where a champion's centre stops and
  rim + radius is where its body stops.
- Blobs in `0xA0C112BA` (header `u32 1 | f32 radius | f32 height | u32 agent | 0 | 0 | u32 size` before
  "BlobAggFile"; `navmesh.find_blobs` / `parse_blob`; index DIDs `0x900113BB` / `0x901113BB` / `0x902113BB`):

| Agent | Radius | Height | "BlobAggFile" at | Size | Triangles | Extent |
|---|---|---|---|---|---|---|
| `0x10000003` (champions) | 0.525 | 2.1 | +0x2A4E6FC | 0x810C | 176 | x 0.8-159.0, y 63.6-100.6 |
| `0x10000002` | 1.1 | 2.1 | +0x2A3C6DC | 0x77DC | 158 | x 1.4-158.4, y 64.2-100.0 |
| `0x10000001` | 2.1 | 4.0 | +0xD75EC4 | 0x69D4 | 149 | x 2.4-157.4, y 65.2-99.0 |

- Rim = triangle edges used once (none of these lie on a 20 m cell seam). The three agents' rims at each corner are
  the same face moved by their radius on the 0.2 m vertex grid (side face: rims 50.6 / 51.6 / 52.2 -> face
  52.7 / 52.7 / 52.725 west; 109.2 / 108.2 / 107.6 -> 107.1 / 107.1 / 107.075 east; the fence rims are parallel at
  22.93 deg for all three), so rim + radius is the obstacle face (C).
- Champion-agent rim at the west mouth: `(52.8, 82.6)-(60.0, 82.6)` lane edge, `(52.2, 83.2)-(52.8, 82.6)` chamfer,
  **`(52.2, 83.2)-(52.2, 85.6)`** side, `(52.2, 85.6)-(53.0, 86.4)` 45 deg chamfer (top pillar), `(53.0, 86.4)-(53.8, 86.8)`
  26.57 deg, **`(53.8, 86.8)-(59.0, 89.0)`** fence 22.93 deg, `(59.0, 89.0)-(60.0, 89.4)`, `(60.0, 89.4)-(64.2, 91.2)`;
  the passage's far side is x 47.0 (y 83.2-92.0). East: `(100.0, 82.6)-(107.0, 82.6)`, `(107.0, 82.6)-(107.6, 83.2)`,
  **`(107.6, 83.2)-(107.6, 85.8)`**, `(107.0, 86.4)-(107.6, 85.8)`, **`(100.8, 89.0)-(107.0, 86.4)`** 157.25 deg; far side
  `(112.4, 92.4)-(112.8, 83.2)`.
- Faces (rim moved 0.525 m away from its walkable triangle): west side x 52.725, lane y 83.125, fence through
  (54.005, 86.316) direction (0.92097, 0.38964); corners (52.725, 83.125) and P (52.725, 85.775). East side x 107.075,
  lane y 83.125, fence through (106.797, 85.916) direction (-0.92221, 0.38674); corners (107.075, 83.125) and
  P' (107.075, 85.799). Mirror of the west: side 107.275 (east is 0.2 m west of it), fence line 0.06 m north of the east
  one at x 106.

## 3. The objects at the corners (C: statics `0x820113BB`, `.entity` records)

Statics record `0x820113BB` at `0xA0C112BA` +0x471B490: `did | 0 | 0x112 | 0 | 362 | entries`, entry
`flags | type | [index | IID 0x01113BB0 if flags & 4] | [world state if & 8] | xyz | quaternion w x y z |
[0 | n | props if & 0x80]` (map-object-census.md 0.1); a piece's local +y points along (-sin yaw, cos yaw).

| Index | World state -> `.entity` (pack, offset) | Position | Yaw | Shape (local) | Role |
|---|---|---|---|---|---|
| 580 | `0x2E0012F5` -> `0x2D000FDA` (`0xA000024C` +0x6B8510C) | (53.30, 83.66, 199.98) | -90 | bbox x +-0.40, y +-0.397, z -0.121..2.194 | brick corner pillar (cap top z 202.17) |
| 536, 581 | `0x2E0012F5` | (53.36, 85.65) | 0 | same | top pillar (side face meets the garden fence) |
| 576 | `0x2E0004D6` -> `0x2D00038B` (+0x6641288) | (53.34, 85.63) | 180 | x +-0.416, y -0.416..3.0 | side-face fence, runs to -y |
| 598 | `0x2E0012FF` -> `0x2D000FE1` | (53.62, 83.66) | -90 | x +-0.40, y -0.397..2.796 | lane fence from the corner, runs to +x |
| 589 / 597 | `0x2E001324` / `0x2E0012F7` | (59.53, 83.66) / (62.39, 83.67) | -90 | as 598 | lane-fence pillars (calibration targets) |
| 584 / 592 / 587 / 595 | `0x2E0012F6` / `0x2E001325` / `0x2E001323` / `0x2E0012F7` | (56.91, 87.37) / (59.66, 88.56) / (62.39, 89.79) / (65.14, 91.01) | 113.1-114.3 | y to 3.921 / 2.796 | garden fence (23.1-24.3 deg) |
| 472 | `0x2E0008F6` -> `0x2D00074E` (`0xA000009A` +0x2671C20) | (106.85, 83.46) | 0 | box half (0.1, 1, 1) at (0, 1, 1) | chain-link side panel (face x 106.95) |
| 467 / 466 / 465 | `0x2E0008F5` -> `0x2D00074D` (+0x2671918) | (106.85, 85.46) / (104.06, 86.65) / (101.28, 87.83) | 67 | half (0.1, 1.5, 1) at (0, 1.5, 1) | chain-link garden fence, 3 m panels toward 157 deg |
| 474 / 473 | `0x2E0008F6` | (98.49, 89.01) / (96.65, 89.79) | 67 | 2 m panels | |
| 475 | `0x2E0008F4` -> `0x2D00074C` (+0x26715E0) | (102.86, 83.46) | -90 | half (0.1, 2, 1) at (0, 2, 1) | lane panel |
| 486 | `0x2E000595` -> `0x2D0000C9` | (106.95, 83.37) | -92 | (record not resolved) | post at the lane corner |
| 461 / 458 | `0x2E000820` / `0x2E000800` | (56.07, 84.99) / (101.75, 84.76) | 26.5 / 21.5 | | garden trees (they hide the diagonal leg in the frames; indices corrected 2026-10-29, the entries' index field) |

The east garden is chain link, the west one brick with pillars: the mouths are not mirror-built (C). Render faces
vs navmesh faces: west side 52.90 (pillar) vs 52.725; east side 106.95 (panel) vs 107.075; west fence centre line
23.9 deg (least squares through the four pillars) vs the 22.93 deg face 0.25-0.35 m north of it. The champion stops on
the navmesh faces, whatever the render shape.

## 4. Measuring the original's layout (P)

### 4.1 Our camera, calibrated on known tiles (C-strong)
Tester recording of fase3-ia/ib (`2026-10-27 13-22-10.mp4`, desktop capture, game viewport y 14-688), frames 05:00
and 08:00: the white "+" of the four centre tiles at their known spawn points (78 / 82, 82.3), (76.6, 72.2),
(83.6, 72.3), z 200.11. Pinhole model, yaw 0, roll 0, principal point at the viewport centre (640, 351), joint fit:
**pitch 57.5 deg, f 791 px (674 px viewport: vertical FOV 46.1 deg), camera 14.35 m above the ground**, rms 0.6 px over
14 residuals (both frames give the same height: one zoom). The "+" is drawn at ground level at the tile's spawn point.
Hex mask check on the same frames (smoothed "blue minus mean(red, green)" > 30): the near edge of a tile lands within
0.03 m of its box and the lateral edges within 0.1 m; the far edge reads up to 0.8 m long (glow), so far edges are
not used below.

### 4.2 The original's camera (P-strong)
`videoplayback.mp4` frames 05:02.0, 05:02.5, 05:06.0 (match 02:24-02:28, west mouth), features = pillar cap tops of
580 / 536 / 589 / 597 (z 199.98 + 2.194) read on 3-5x gridded crops, shared pitch / f / height, own position per frame:
**pitch 58.7 deg, f 848 px (720 px: vertical FOV 46.0 deg), camera 14.72 m above the ground**, rms 1.5 px over 24
residuals; cameras at (54.83, 79.20), (54.85, 75.94), (59.85, 73.76). Same client camera as ours (f 791 x 720 / 674 =
845 px). East frame 07:21.0 (match 04:43): six chain-link post tops (106.85, 85.46) ... (94.81, 90.57) at z 201.98-202.15,
pitch and f fixed: camera (103.23, 82.46), height 14.59-14.76 m (same zoom), rms 1.0 px.

### 4.3 What the frames give
- West vertical tile centre: its "+" at (470.7, 499.4) in 05:06 -> **(51.71, 85.14)**; at (340, 561.7) in 09:31
  (match 06:53, camera fitted on the same caps, rms 5 px) -> **(51.70, 85.16)**. Joint fits with the pitch forced to
  55-60 deg move it over y 85.07-85.37, x 51.67-51.74. A tile at (51.7, 84.0) would put the "+" at (463.8, 559.3) in
  05:06 (60 px lower), one at (51.7, 85.5) at (472.5, 480.9) (18 px higher).
- Outer edge of the vertical legs (lateral edges, mask threshold 30 / 18, median over 100-140 rows): west x 50.77 /
  50.65 (05:06), 50.87 / 50.78 (05:02.5), 50.73 / 50.64 (05:02.0); east x 109.27 / 109.34 (07:21). Tiles at 51.7-51.8
  and 108.2-108.3: their centres sum to 160.0 +- 0.05, i.e. **mirrored about x 80**; the east is not shifted onto its
  own side face (108.1).
- South (near) end of the west vertical leg: y 83.55 / 83.28, 83.69 / 83.50, 83.66 / 83.51: the field starts at the
  garden corner (lane face 83.125, fence face 83.26), not in the lane.
- The bend and the diagonal leg: the unprojected mask (scratchpad plots of 05:02.0 / 05:02.5 / 05:06.0) shows the
  vertical leg x 50.6-52.2 (the pillars hide the rest), y 83.3-87.3, and from (52.0, 87.6) a leg along the fence on the
  path side whose north edge passes (54, 88.6) (tile (54.2, 87.5) yaw 23: 88.50); its south half is hidden by the fence
  and the tree. East 07:21.0: the leg's north edge at x 105 / 106 / 107 = 88.65 / 88.3 / 87.9 (tile (105.8, 87.5) yaw
  157: 88.92 / 88.50 / 88.08), its far end dim at x 103.3-105.0 depending on the threshold (tile end 103.6-104.4). The
  outer corner of the bend shows the notch between the vertical tile's top-left corner (50.7, 87.2) and the diagonal
  tile's north-west corner (51.97, 87.64).
- Frames 34 / 36 / 47 (VLC captures of the same video) show the same L; 35 / 37 the east one (chain-link corner,
  diagonal leg on the path side, vertical leg along the side panel).

So: **two tiles per mouth, the vertical one from the garden corner north (y 83.2-87.2) against the side face, the
diagonal one from the corner along the fence on the path side; left and right mirrored** (P, +-0.15 m).

The tester's 10:3x request ("move the vertical fields a little lower", then at y 85.5) fits this: 85.5 was 0.3 m north
of the original; the change applied was 1.5 m.

## 5. Placements against the faces (C geometry)

Obstacle-side long edge vs the nearest face along it (+ = past the face, inside the obstacle):

| Layout | Tile | Centre | Yaw | Edge vs face | Angle |
|---|---|---|---|---|---|
| 13:5x (sent 14:40) | 4 west vertical | (51.7, 84.0) | 98 | -0.24..+0.07 | 8.0 |
| | 5 east vertical | (108.3, 84.0) | 82 | -0.44..-0.13 | 8.0 |
| | 6 west diagonal | (53.7, 87.0) | 50 | +0.63..+0.72 past the 45 deg chamfer face | 5.0 |
| | 7 east diagonal | (106.3, 87.0) | 130 | no face within 15 deg (fence at 157.25) | 27 |
| **recommended** | 4 west vertical | **(51.7, 85.2)** | **90** | -0.025 (side face); south-east corner (52.7, 83.2) 0.08 m from the garden corner | 0 |
| | 5 east vertical | **(108.3, 85.2)** | **90** | -0.225 (the original's gap) | 0 |
| | 6 west diagonal | **(54.2, 87.5)** | **23** | -0.016..-0.013 (fence face); back corner on P | 0.07 |
| | 7 east diagonal | **(105.8, 87.5)** | **157** | -0.084..-0.069 | 0.25 |
| per-side flush (option) | 5 / 7 | (108.1, 85.2) / (105.62, 87.50) | 90 / 157.25 | -0.025 / -0.006 | 0 |

Exact flush values: diagonal = P + 2u + n = (54.177, 87.475) yaw 22.93 (west), (105.617, 87.495) yaw 157.25 (east). The
centre tiles 0-3 already lie on the lane faces (0.175 / 0.175 / 0.275 / 0.175 m, 0 deg) and stay. The diagonal tile
ends 0.08 m short of the first brick fence pillar (56.91, 87.37) on the west.

## 6. Hide area (`Match.inside_strip`, unchanged: rotated tile + `stealth_margin` 0.5 m)

With the recommended layout (harness run of section 8 step 4 on a real Crime Alley match): hidden at (52.1, 84.0),
(107.9, 84.0), (52.1, 86.5), (55.0, 87.3) and (105.0, 87.3) (against the corners and the fences); not hidden in the
passage (49.5, 85.0), on the lane in front of the mouths (51.7, 82.0) / (108.3, 82.0) (hidden by the 84.0 layout) or
0.6 m north of the diagonal's north edge (53.57, 88.97). A champion in the bend's overlap belonged to the vertical tile
only (`strip_of` returns the first index), so an enemy in the diagonal tile a metre away did not see it. How the
original treated overlapping hotspots is **O** (correction of the first version, which claimed P: with two overlapping
hotspots a champion in the bend is inside both). Implemented 2026-10-29: `Match.visible_to` compares every strip that
holds the champion with the viewer's (`[ics] match_stealth_any_shared`, true; false = the first-index rule).

## 7. Open

1. O (decision): the tester's literal "as it was" may mean y 84.0 (the 10:3x placement). The data says 85.2 (the
   original's "+" and near edge; the 84.0 tile hangs 1.2 m into the lane past the corner). The plan ships 85.2 with
   the 84.0 override written in the config comment.
2. P: the diagonal tile's position along the fence (+-0.3 m): its north edge and the bend's notch match a start at the
   corner P; its far end is under the tree (west) or dim (east).
3. P: the east mouth keeps the original's mirror (0.225 m off its side face, 0.35 m off the chain-link panel); the
   per-side flush option (108.1 / (105.62, 87.50) yaw 157.25) is one override away if the tester wants the gap closed.
4. O: the hex mesh `0x2E000D37` has an all-zero bbox and no box; its footprint equals the 4 x 2 m tile within 0.1 m
   laterally on our frames (4.1), the particle `0x18000A57`'s emitter size was not decoded.
5. P: the original's camera and ours agree (pitch 58.7 / 57.5 deg, vertical FOV 46 deg, height 14.7 / 14.4 m), so the
   calibration in 4.1-4.2 can measure any other placement from frames of either video (method: cap / post tops or
   tile "+" marks as anchors, yaw 0, principal point at the viewport centre).

## 8. Implementation plan

1. `ics/match/maps.py` `_crime_alley()` "stealth" (lines 98-108): keep tiles 0-3 and every dated comment. Before line
   105 insert
   ```python
                    # 2026-10-28 15:00 (tester: both side fields are off; the vertical one back as it was, lined up with
                    # the collision edge of that corner; stealth-alignment.md): each jungle mouth is the original's L.
                    # Vertical tile yaw 90, its inner edge on the garden's side face and its south end on the garden
                    # corner (navmesh rim + 0.525 m: x 52.725, y 83.125, C); y 85.2 = the original's tile centre (its
                    # "+" in two calibrated frames, P: the 10:3x "a little lower" was 0.3 m, not 1.5). Diagonal tile
                    # along the garden fence on the path side, its edge on the fence face (22.93 deg, C), from the
                    # corner. East = mirror, as in the original (its side face is 0.2 m west of a mirror, so its tile
                    # stays 0.225 m off it). "flush": checked by test_match; [ics] match_stealth_overrides switches back
   ```
   then replace line 105 `{"pos": (51.7, 84.0), "yaw": 98.0}, {"pos": (108.3, 84.0), "yaw": 82.0},` with
   ```python
                    {"pos": (51.7, 85.2), "yaw": 90.0, "flush": True},
                    {"pos": (108.3, 85.2), "yaw": 90.0, "flush": True},
   ```
   and line 108 `{"pos": (53.7, 87.0), "yaw": 50.0}, {"pos": (106.3, 87.0), "yaw": 130.0}],` with
   ```python
                    {"pos": (54.2, 87.5), "yaw": 23.0, "flush": True},
                    {"pos": (105.8, 87.5), "yaw": 157.0, "flush": True}],
   ```
   (order unchanged: 4 / 5 vertical west / east, 6 / 7 diagonal west / east; `"flush"` is ignored by `_spawn_stealth`).
2. `ics/config.py`, after `"match_stealth_size": [4.0, 2.0],` (line ~910):
   ```python
        # 2026-10-28 15:00 (tester: the side stealth fields are off; the vertical one back as it was, lined up with the
        # corner's collision edge; stealth-alignment.md): per map key and tile index {"pos": [x, y], "yaw": deg} over
        # maps.py "stealth" ({} = the map's list: the original's L at each jungle mouth). The tester's 10:3x placement:
        # {"crime_alley": {"4": {"pos": [51.7, 84.0]}, "5": {"pos": [108.3, 84.0]}}}; the 13:5x layout (fase3-ie):
        # {"crime_alley": {"4": {"pos": [51.7, 84.0], "yaw": 98.0}, "5": {"pos": [108.3, 84.0], "yaw": 82.0},
        #  "6": {"pos": [53.7, 87.0], "yaw": 50.0}, "7": {"pos": [106.3, 87.0], "yaw": 130.0}}}
        "match_stealth_overrides": {},
   ```
3. `ics/match/match.py` `_spawn_stealth` (lines 638-640), same shape as `match_camp_overrides` (line 1435):
   ```python
        over_map = (self.ic.get("match_stealth_overrides") or {}).get(self.map.get("key")) or {}
        for i, spec in enumerate(self.map.get("stealth", ())):
            over = over_map.get(str(i)) or {}
            if over:                                   # 2026-10-28 15:00: [ics] match_stealth_overrides
                spec = dict(spec, **{k: (tuple(v) if k == "pos" else v) for k, v in over.items()})
            x, y = spec["pos"]
   ```
   `inside_strip` / `strip_of` / `visible_to` need no change (they use each tile's own rotated rectangle `ent.tile`).
4. `tests/test_match.py`, after the stealth shimmer checks (line 561; `m` is the Crime Alley match of line 414, `data`,
   `maps`, `navmesh`, `math`, `check` are in scope). Validated in the scratchpad with this exact code on a real match:
   the 13:5x layout fails checks 1, 3, 4; the recommended one passes all four; the 84.0 variant passes 1-2 and fails 3-4.
   ```python
    # ---- stealth tiles on the jungle-mouth corners' collision faces (stealth-alignment.md; tester 2026-10-28 15:00) ----
    ca, _mode = maps.map_for(0x40000C82)
    buf = data.packs.pack(ca["map_pack"]).data
    _cls, agent_r, blob = next(b for b in navmesh.find_blobs(buf) if b[0] == 0x10000003)
    ox, oy = ca["landblock"][0] * navmesh.LANDBLOCK, ca["landblock"][1] * navmesh.LANDBLOCK
    owner = {}
    for t in navmesh.parse_blob(buf, blob):
        p = [(round(x - ox, 3), round(y - oy, 3)) for x, y, _z in t]
        for k in range(3):
            owner.setdefault(tuple(sorted((p[k], p[(k + 1) % 3]))), []).append(p[(k + 2) % 3])
    faces = []                                          # rim + agent radius = where a champion's body stops
    for (a, b), opp in owner.items():
        if len(opp) == 1:
            seg = math.hypot(b[0] - a[0], b[1] - a[1])
            d = ((b[0] - a[0]) / seg, (b[1] - a[1]) / seg)
            ob = (-d[1], d[0]) if (opp[0][0] - a[0]) * d[1] - (opp[0][1] - a[1]) * d[0] > 0 else (d[1], -d[0])
            faces.append(((a[0] + agent_r * ob[0], a[1] + agent_r * ob[1]), d, ob, seg))

    def against_face(ent):
        """(worst |offset| m, angle deg) of the tile's long edge lying along a collision face, or None"""
        yaw, half_long, half_short = ent.tile
        u, best = (math.cos(yaw), math.sin(yaw)), None
        for side in (1.0, -1.0):
            nrm = (-u[1] * side, u[0] * side)
            mx, my = ent.pos[0] + half_short * nrm[0], ent.pos[1] + half_short * nrm[1]
            for (ax, ay), d, ob, seg in faces:
                ang = math.degrees(math.acos(min(1.0, abs(u[0] * d[0] + u[1] * d[1]))))
                if seg < 1.0 or nrm[0] * ob[0] + nrm[1] * ob[1] < 0.9 or ang > 3.0:
                    continue
                offs = [((mx + s * u[0] - ax) * ob[0] + (my + s * u[1] - ay) * ob[1])
                        for s in (half_long * (k / 4.0 - 1.0) for k in range(9))
                        if -0.05 <= (mx + s * u[0] - ax) * d[0] + (my + s * u[1] - ay) * d[1] <= seg + 0.05]
                if len(offs) >= 3 and abs(offs[len(offs) // 2]) < 1.5:
                    worst = max(abs(o) for o in offs)
                    best = min(best or (9.9, 0.0), (round(worst, 3), round(ang, 2)))
        return best

    flush = [i for i, sp in enumerate(ca["stealth"]) if sp.get("flush")]
    fits = {i: against_face(m.stealth[i]) for i in flush}
    check("stealth: the 4 jungle-mouth tiles lie along their corner's collision faces (navmesh rim + 0.525 m; long "
          "edge <= 0.3 m, <= 3 deg)", len(flush) == 4 and all(f and f[0] <= 0.3 for f in fits.values()), fits)
    check("stealth: left / right mouths mirrored (x -> 160 - x)", all(
        abs(m.stealth[a].pos[0] + m.stealth[b].pos[0] - 160.0) < 0.01 and abs(m.stealth[a].pos[1] - m.stealth[b].pos[1]) < 0.01
        for a, b in ((flush[0], flush[1]), (flush[2], flush[3]))))
    v_w = m.stealth[flush[0]]
    corner = (v_w.pos[0] + v_w.tile[2], v_w.pos[1] - v_w.tile[1])   # the west vertical tile's south-east corner
    check("stealth: the west vertical tile starts at the garden corner (side face x 52.725 / lane face y 83.125)",
          math.hypot(corner[0] - 52.725, corner[1] - 83.125) < 0.3, corner)
    check("stealth: a champion in either corner or along the fence is hidden; one in the passage, on the lane in "
          "front of the mouth or past the diagonal is not",
          all(m.strip_of(p) is not None for p in ((52.1, 84.0), (107.9, 84.0), (52.1, 86.5), (55.0, 87.3), (105.0, 87.3)))
          and all(m.strip_of(p) is None for p in ((49.5, 85.0), (51.7, 82.0), (108.3, 82.0), (53.57, 88.97))))
   ```
   Run `python tests\test_match.py` (no ports). If the 84.0 placement is chosen instead (section 7 item 1), drop checks
   3 and 4's lane points.
5. Records (CLAUDE.md rule 3). Done with this note: `docs/CHANGELOG.md` fase3-if bullet "Side stealth fields,
   investigation"; `docs/reverse-engineering.md` section "Crime Alley stealth fields: corner collision faces and the
   original's layout"; `catalog/data/records.tsv` row `0x900113BB` (Crime Alley navmesh); `catalog/data/world_objects.tsv`
   row `0x2E000D36` corrected (8 tiles, long side along x at yaw 0, status partial) and rows `0x2E0012F5` (brick
   pillar) / `0x2E0008F5` (chain-link panels). When the layout ships: `0x2E000D36` server_status "implemented", used_in
   "... each jungle mouth an L (vertical (51.7 / 108.3, 85.2) yaw 90 + along the fence yaw 23 / 157)"; a CHANGELOG
   fase3-if bullet "Side stealth fields: the original's L at each jungle mouth ...; `[ics] match_stealth_overrides`
   ({} = this layout; the comment lists the 10:3x and 13:5x ones)"; then `python ic.py catalog` (not run in this pass:
   it also refreshes shared TSVs from sources).
6. Tester check (no diag mode needed): walk into each mouth's corner; the field's inner edge runs along the pillars /
   the chain link, its south end at the corner pillar (not in the lane), the diagonal leg along the fence on the path
   side as in frames 34 / 36 / 47; `/tour` stops on every tile.

## 9. Skeptic review (2026-10-29, independent re-check; no code changed)

**Verdict: confirmed, with corrections; the plan is sound to implement.**

Re-checked independently (scratchpad only):
- **Navmesh faces (C).** `ics.navmesh` on `0xA0C112BA`: agent `0x10000003` radius 0.525, blob +0x2A4E6FC, 176 triangles;
  the rim edges at both mouths are exactly those of section 2. Agent `0x10000002` (1.1 m) gives the same faces
  (52.7 / 107.1 / lane 83.1) on the 0.2 m vertex grid.
- **Yaw convention (C).** `World.placements` sends heading = quaternion yaw + 90 deg, the same rule as `heading_from_yaw`.
  Hex masks of frames 43 / 44 show the 13:5x diagonals as sent: west yaw 50 rises to the right over the top pillar,
  east yaw 130 rises to the left. A mirrored (clockwise) client rotation is ruled out.
- **The original's vertical tile (P-strong).** I fitted my own pinhole cameras on VLC frames 47 (match 02:26) and 36
  (match 06:54), using the video area x 148-1770 / y 55-967 and the caps of 536 / 580 / 589 / 597 (plus 592 in 36).
  - At pitch 57-58 deg and vertical FOV 45-46 deg (the camps pass's camera record), the "+" maps to
    (51.69-51.72, 85.14-85.23). For any pitch from 52 to 62 deg it maps to y 84.96-85.45.
  - A tile at 84.0 would show its "+" 62-89 screen px (49-70 video px) below the observed one in both frames.
  - Overlaying the planned L on frame 36 matches the hex. The vertical leg reaches about y 87.2 above the corner
    pillar; an 84.0 tile ends at 86.0 and would leave that band empty. The diagonal hexes lie inside the yaw-23 tile,
    on the path side of the fence.
- **Section 8 step 4 checks.** I ran them on a real Crime Alley match, with each layout patched in memory through
  `maps._BUILDERS`. The results are as claimed:

  | Layout | Result | Long-edge fits (m) |
  |---|---|---|
  | 13:5x | fails checks 1, 3 and 4 | |
  | Plan | passes all four | 0.025 / 0.225 / 0.016 / 0.084 |
  | 84.0 | fails checks 3 and 4 | |
  | Per-side flush | fails check 2 (mirror) | |

Corrections:
1. **Line numbers have moved** (other agents' edits). `_spawn_stealth` is at `ics/match/match.py:652` (loop at line
   664), and `match_camp_overrides` is applied at line 1465. `match_stealth_size` is at `ics/config.py:941`. Add the
   test after the shimmer checks at `tests/test_match.py:680-696`; `m` there is still the CA match from line 414.
   maps.py lines 105 and 108 have not moved.
2. **Precision.** The "+-0.15 m" claimed for the vertical centre is optimistic. The pitch dominates the error, about
   +-0.25 m. Even so, 85.2 is still right and 84.0 is still excluded.
3. **Test robustness.** test_match reads config.toml through `config.load()`, so a tester override of
   `match_stealth_overrides` or `stealth_margin` would fail checks 2-4.
   - Pin `cfg["ics"]["match_stealth_overrides"] = {}` and `cfg["ics"]["stealth_margin"] = 0.5` at the top of `main()`,
     next to the existing pins.
   - Optional: check 1 accepts a long edge up to 0.3 m inside a fence. Requiring a signed offset <= +0.05 (walkable
     side only) would close that gap.
4. **Section 6 overlap claim is O, not P.** The text says an enemy in the diagonal tile does not see the champion,
   "as two separate hotspots would in the original". With two overlapping hotspots, a champion in the bend is inside
   both, so the comparison does not hold. `strip_of` returns the first index, so a champion in the bend (tile 4) is
   hidden from an enemy in tile 6 a metre away. If that matters, `visible_to` could test whether the viewer is inside
   any strip that holds the target, behind its own switch (rule 4). This does not block the plan.
5. **Section 3 indices.** The garden trees are statics 461 (`0x2E000820`, (56.07, 84.99)) and 458 (`0x2E000800`,
   (101.75, 84.76)), not 205 / 202.
6. **Conflict with the "maps" pass.** Its plan item for these fields (x 52.35 / 107.5, 30 deg from (52.6, 86.0) /
   (107.25, 86.0)) uses the raster approximation this note corrects. Implement only this note's layout.
7. **Running `python ic.py catalog`.** It rewrites shared TSVs through `build_catalog.write_tsv` (champions,
   stolen_powers, scriptlets, hud_elements, exe_patches). Run it once at the end, when no other agent is editing
   catalog/data.

Extra evidence (P, reading of the reports):
- The 12:5x request ("the blue side's to the right, the red side's to the left") fits turning the diagonal legs onto
  the fences: west 50 -> 23 is clockwise, east 130 -> 157 is counter-clockwise. The 15:00 report ("the vertical one
  back as it was, lined up with the corner's collision edge") then describes the plan: vertical tiles at yaw 90,
  diagonal tiles on the fence faces.
- The 10:3x overshoot explains the rotation requests that followed. At y 84.0 the tile hangs 1.2 m past the corner
  into the lane and looks misaligned. 85.2 is 0.3 m below the old 85.5, which is the "a little lower" that was asked.
- Bots and the local champion share `inside_strip` / `visible_to`. Only Crime Alley's vai and clash builders have a
  "stealth" list, so no other map changes. The camps pass's new side-camp slots (x 47.2-51.0 / 108.5-112.2, y
  90.2-91.9) fall outside every hide box.
- The reply to the tester should state both open choices: 85.2 instead of the literal "as it was" (84.0), and the
  east tile's 0.225 m gap. Each one is a single `match_stealth_overrides` entry away.

## 10. Implemented (2026-10-29, fase3-if)

Section 8 with the skeptic's corrections; the maps pass's raster item for these fields (section 9 item 6) was not used.
- `ics/match/maps.py` `_crime_alley()` "stealth": tiles 4 / 5 `(51.7, 85.2)` / `(108.3, 85.2)` yaw 90, tiles 6 / 7
  `(54.2, 87.5)` yaw 23 / `(105.8, 87.5)` yaw 157, all `"flush": True` (order unchanged, every dated comment kept, one
  2026-10-28 15:00 comment per pair).
- `ics/config.py`: `match_stealth_overrides` `{}` after `match_stealth_size` (the comment lists the y 84.0 vertical
  tiles, the whole 13:5x layout and the per-side flush east L); `match_stealth_any_shared` `True` after
  `match_stealth_hides` (section 6).
- `ics/match/match.py`: `_spawn_stealth` merges `match_stealth_overrides[map key][str(index)]` over the spec (pos as a
  tuple) and logs it; `visible_to` with `match_stealth_any_shared` = any strip holding both the champion and the viewer.
  `inside_strip` / `strip_of` unchanged.
- `tests/test_match.py`: pins `match_stealth_overrides = {}` / `stealth_margin = 0.5` in `main()`; the section 8 step 4
  checks after the shimmer checks with three tightenings: the long edge must also stay on the walkable side (deepest
  signed offset <= +0.05 m), the mirror check includes the yaw (yaw -> 180 - yaw, modulo the tile's 180 deg symmetry),
  and both vertical tiles are checked against their own garden corner (west 0.079 m, east 0.237 m); the hide points
  are mirrored on the east and the fence points moved to y 87.6 (clearly on the walkable side); plus a bend check
  ((52.6, 87.0) in tiles 4 + 6 and (55.5, 88.3) in tile 6 see each other, (51.7, 83.5) in tile 4 only stays hidden
  from tile 6; false = the first-index rule) and an override check (a second match with tiles 4 / 5 at y 84.0).
  Results on a real Crime Alley match (scratchpad harness, the same code): the shipped layout passes all; 13:5x fails
  the face, corner and hide checks; y 84.0 fails the corner and hide checks; the per-side flush east L fails the mirror
  check; tiles pushed 0.275 m into the gardens fail the walkable-side test.
- Also in test_match: the shimmer checks before them ran on a dead champion (the vehicles pass's mid-toss kill at
  level 2 waits 8 s, the test advanced 6 s), which failed 2 checks; they now wait out that death's respawn time first.
- Records: CHANGELOG fase3-if bullet "Side stealth fields: the original's L at each jungle mouth";
  reverse-engineering.md "Crime Alley stealth fields: the L in ics, flush with the corner faces";
  `catalog/data/world_objects.tsv` `0x2E000D36` implemented.
- Tester check (no diag needed): in each mouth the field's inner edge runs along the pillars / the chain link and its
  south end sits at the corner pillar; the diagonal leg runs along the garden fence on the path side (frames 34 / 36 /
  47). Open choices, each one override away: the literal y 84.0 (`{"4": {"pos": [51.7, 84.0]}, "5": {"pos": [108.3,
  84.0]}}`) and the east L flush with its own corner (`{"5": {"pos": [108.1, 85.2]}, "7": {"pos": [105.62, 87.5],
  "yaw": 157.25}}`), both under `[ics] match_stealth_overrides` -> `crime_alley`.
