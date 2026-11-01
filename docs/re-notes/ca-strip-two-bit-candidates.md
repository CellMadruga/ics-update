# Crime Alley strip: the `--strip` answer, the two-bit candidates, `--strip2`; the blue core's yaw (2026-10-30)

Tester run 19:41-19:47 (Crime Alley v AI; logs `server.log` / `traffic.log` / `diag.log` of that run, `diag --strip`
lines 19:42:09-19:47:03), screenshot `96.webp` (the blue core at yaw -80), the tester's words: the strip went away in
"step 26/26: bit 9 (51 render nodes)" and, clarified, in one other bit step not noted; bit 9 looked "the most similar"
because a fence piece vanished too. Sources: the statics record `0x820113BB` (map pack `0xA0C112BA`, read only),
`.entity` / world-state records in `0xA000024C`, `0xA000009A`, `0xA00002E5`, the decompiled loader `0x548550`
(`re-work/decomp`). Tags: **C** confirmed, **P** probable, **O** open. Builds on `ca-strip-static-shadow.md`.

## 1. What the 19:41 run says (C log)

- The header "0 statics of block 13BB recorded" was wrong: it was logged at the first fog frame (19:42:09), before the
  map's statics attached; the steps then hid 201 render nodes (step 7, every 13BB static). Fixed (section 4).
- **`Render.ShadowMapQuality` was already 0** in this run (step 1 "was 00000000"; 02 at 18:04): dynamic shadow maps
  were off and the strip was still black. So it is **not a shadow-map shadow** (C), which retires the lead of
  `ca-strip-static-shadow.md` 1.
- Recorded nodes per named static: #0x243 (`0x2E0004D7`) 1, #0xD7 1, #0xBB 1, #0x11E 1, but **#0x24C (`0x2E001324`)
  and #0x246 (`0x2E0012F6`) none**. Both are client breakables (fracture data `0x800`, `0x1000019D = 0x1000`,
  `tutorial-data-inventory.md` 5.4); `0x2E0004D7` is not. P: a breakable's entity gets its IID after its model node
  attaches (or attaches through another path), so the 0x78165C probe skipped it (`--strip` keyed on the IID at attach
  time). `--strip2` re-reads every recorded component's IID when a cycle starts (section 4).
- The loader keeps the entry's own IID (C, `0x548550`: the 0x70-byte in-memory entry, type at +0x20, IID pair at
  +0x28 / +0x2C looked up by `0x53BFD0`), so "static index" = the entry's index field, as `--strip` assumed.

## 2. Candidates (C data)

Index = `0x200 | (1 << k)`, k = 0..8. In `0x820113BB` (header count 0x16A; entries `flags | type | [index | 0x01113BB0
if flags & 4] | [world state if flags & 8] | xyz | quaternion w x y z | [0 | n | props if flags & 0x80]`; indices are
sparse, 0x206 / 0x210 / 0x220 do not exist):

| Index | Type | World state | Position | What | Reaches the strip (x 70-85.5, y 81.8-83.4)? |
|---|---|---|---|---|---|
| 0x201 | 7 | `0x2E0012EC` (`.entity 0x2D000FD2`) | (19.04, 62.13) | breakable crate, box 2.6 x 2.2 x 1 m | no (60 m away) |
| 0x202 | 7 | `0x2E0012F0` (`0x2D000FD6`) | (26.40, 64.01) | breakable crate | no |
| 0x204 | 7 | `0x2E0012EF` (`0x2D000FD5`) | (27.40, 87.90) | breakable crate | no |
| **0x208** | 7 (flags 0x9E, prop `0x6B4` scale 1.15) | `0x2E000800` (`0x2D000682`) | (85.56, 86.54), yaw 269.5 | garden bush (breakable; mesh `0x1700049A` inline, format 0x2205102, 1737 vertices, box (-1.20, -1.50, 0) .. (1.23, 1.62, 1.05)) | **nearest**: its mesh ends at y ~84.7, 1.3 m north of the fence; not over the strip by its box |
| 0x240 | 7 | `0x2E0004D6` (`0x2D00038B`) | (53.34, 85.63), yaw 180 | west garden side fence, box x 52.9-53.8, y 82.6-86.1 | no (17 m west) |
| 0x280 | 16 | none | (153.0, 81.5) | team-2 start point; type 16 is never instantiated | no |

So **no two-bit static has bounds over the strip** (C for the boxes of the `.entity` records; P that the render
model stays inside them). The fence piece the tester saw vanish in the bit-9 step is P #0x243 (`0x2E0004D7` at
(78.68, 83.66), index bits 0, 1, 6, 9; the only lane fence piece over the strip that `--strip` recorded). Bit-9 statics
that touch the strip at all: the lane fence pieces #0x243 / #0x246 / #0x24C (top 0.15 m of the strip only) and the
garden fence #0x247; none has exactly two bits.

Reading (P): either the culprit is #0x208 (the only two-bit candidate within 4 m; a breakable bush whose drawn
geometry or effect reaches farther than its stored box), or one of the steps was misread (the strip went in a step
whose static has more bits, or the "other bit" step was a neighbour of the real one). One-at-a-time hiding settles it.

## 3. The blue core's yaw (tester 19:46, `96.webp`)

- Yaw is counter-clockwise seen from above; the camera has +y up and +x right on screen (C: the core turret at
  (25.5, 77.5) stands right of the core at (17.5, 77.5) in `96.webp`); World heading = yaw + 90 deg
  (`heading_from_yaw`).
- At yaw -80 (fase3-ix: spec 90 + `match_structure_yaw_add` -170) the core's prow, the dark ramp, points
  west-south-west on screen (direction ~-165 deg), so the prow is the model's local **-y** (-165 - (-80) = -85, P).
- The red core (spec yaw -90, unchanged) then points its prow at -180 = west = at the lane (it stands at x 142.5).
  Crime Alley is mirrored left / right (x -> 160 - x): the prow's direction -180 maps to 0 (east, at the lane from
  x 17.5), i.e. blue yaw = 0 - (-90) = **90**. Because the prow lies along the mirror axis, the reflection and the
  map's half-turn symmetry give the same value (red -90 + 180).
- Check against the tester: 90 = -80 + 170 counter-clockwise = -80 - 190 clockwise, the "about 190 degrees clockwise".
- So `[ics] match_structure_yaw_add` = {"crime_alley": {"core": {"1": 0.0}}}: blue = the spec's 90 (the pedestal
  `0x2E000A3B`'s yaw); -170 = fase3-ix. P: the 15:30 "170 to the right" and this "190 clockwise" sum to a full turn,
  so the yaw-90 core the tester saw before fase3-ix was probably not the one this build draws (O).

## 4. Diag changes (`tools\diag.py`)

- `--strip`: every attached render component is kept; when a cycle starts `strip_resolve()` reads each one's entity
  IID again and adds the 13BB ones, then logs `STRIP cycle n starts: N statics of block 13BB recorded, M render
  nodes` (the misleading header at the first fog frame is gone; the NONE warning stays, now on the real count).
- `--strip2` (Spanish `--franja2`; start it in the menu, before Launch): the same probes, its own steps, 6 s each:
  #0x208, #0x240, #0x201, #0x202, #0x204, then #0x243, #0x246, #0x24C, #0x247, #0x207, then two controls (every
  bit-9 static, every static). The cycle-start line lists each candidate's recorded node count (0 = not hideable
  even after the re-read: report it).

## 5. Fix (O until `--strip2` answers)

The pack patch stays as `ca-strip-static-shadow.md` 5 proposes: in `0x820113BB` the culprit's entry type 7 -> 3
(the loaders `0x548550` / `0x5EC4F0` instantiate neither 3 nor 16), a 4-byte same-length edit with the terrainfix
backup / CRC / Adler-32 machinery. Not written in this build: no candidate is confirmed, and dropping the wrong static
(a fence, a crate) changes the map for nothing.

## 6. Tests

`tests/test_match.py` `strip_two_bit_candidates` (2 checks: the instantiated two-bit entries are exactly 0x201 / 0x202 /
0x204 / 0x208 / 0x240, 0x280 is type 16; diag has `--strip2` / `--franja2`, the candidates in order, the re-read and
the cycle-start count); `core_door_regen_1530` now checks blue 90 / red -90 (a half turn apart, = -80 - 190).

## 7. Tester

1. Game in the menu (before Launch), second console: `python tools\diag.py --strip2` (or `--franja2`).
2. Crime Alley v AI; stand where the strip shows, do not move the camera; record one full cycle (~75 s from the first
   `STRIP cycle 1 step` line), or note the time at which the strip disappears.
3. Send the recording / times and `logs\diag.log`. Look at the blue core: its prow should point at the lane, like the
   red one's (no `python ic.py patch` needed: nothing in the exe or the packs changed).

## 8. The `--strip2` recording (21:33) and `--strip3` (2026-10-30)

Tester run 21:33-21:39 (Crime Alley v AI, `diag --strip2` lines 21:33:45-21:39:28 in `diag.log`), the tester's own
recording `2026-10-30 21-33-53.mp4` (1280 x 720, 30 fps, 349 s; frames read locally into the scratchpad, never into
the repo), the tester's words "the strip only disappears in step 11/12 (every bit-9 static, 51 render nodes)".

### 8.1 Video time -> log time (C)

The Windows taskbar clock (bottom right) changes minute at video t = 6.0-6.5 s (9:33 -> 9:34 PM), 66.0-66.5 s,
186.0-186.5 s and 246.0-246.5 s, so **log time = 21:33:53.5-54.0 + t** (the file name is the start, 21:33:53). Mean
grey of the strip area (screen x 320-540, y 340-380 with the camera parked from t ~ 60 s on): 2.9 while black,
82.2-82.8 when gone.

| Cycle | Strip gone (log time, +-0.5 s) | Steps (6 s each) |
|---|---|---|
| 1 | 21:34:55.7 - 21:35:06.7 | 11 (bit-9 control, 21:34:55) + 12 (every static, 21:35:01) |
| 2 | 21:36:22.7 - 21:36:33.7 | 11 (21:36:22) + 12 (21:36:28) |
| 3 | 21:37:49.7 - 21:38:00.7 | 11 (21:37:49) + 12 (21:37:55) |
| 4 | 21:39:16.7 - 21:39:27.7 | 11 (21:39:16) + 12 (21:39:22) |

Cycle 1 steps 1-10 ran while the camera was still moving (not readable); in cycles 2-4 the strip stayed black through
steps 1-10 (C). The earlier `--strip` runs (18:04, 19:42) are not in this recording.

- In step 11 the lane fence stays, the strip is gone, and a **red translucent band** appears in the north garden
  (screen y ~560-610 at 21:39:18, a small ring at its west end); in step 12 there is neither. So something outside
  bit 9 draws a band that a bit-9 static normally covers (C video, P reading); same family of artefact as the strip.

### 8.2 Why the single candidates said nothing (C log)

Every cycle-start line of the run: **#0x208, #0x201, #0x202, #0x204, #0x246, #0x24C, #0x247, #0x207: 0 nodes**;
#0x240 and #0x243: 1 node each. The eight are all **breakables** (world states `0x2E000800`, `0x2E0012EC/EF/F0`,
`0x2E0012F6`, `0x2E001324`, `0x2E000821`: fracture data `0x800` in their world-state records), and no breakable
passed the 0x78165C attach probe even with the IID re-read, so their steps hid nothing. They are also not among the
51 nodes of step 11. So the culprit is a **non-breakable bit-9 static** other than #0x240 / #0x243 (C).

### 8.3 The 51 (C data, P = exact membership)

Instantiated (type 7) bit-9 entries of `0x820113BB`: 80; without fracture data: **53** (the diag recorded 204 statics
in all = the 203 non-breakable type-7 entries + 1; 51 bit-9 nodes were hidden, so 2 of the 53 have no live / visible
node, which ones is O). By world state (`.entity`, render box from the box record):

| World state | Count | Indices | Nearest to the strip |
|---|---|---|---|
| `0x2E0005D6` (`.entity 0x2D0002E4`, class `0x400004FD`, colour `0x2A0 = 0xFF0000FF`, inline 40-vertex mesh; box 5 x 5 x 5 cm; per-instance `0x1000049A` Wwise-like hash) | 30 | 0x257-0x275 (no 0x266) | **#0x262 (78.01, 85.82, 201.50)**: 2.4 m north of the strip, 1.5 m up; #0x258 (62.07, 85.37, 201.50) |
| `0x2E0004D6` / `0x2E0004D7` fence pieces | 4 + 1 | 0x23F-0x242, 0x243 | 0x243 (tested alone: no) |
| `0x2E0012E8` (`0x2D000FCE`, DXBC material, box 0.5 x 0.5 x 2.3 m: lamp-like) | 7 | 0x209-0x20F | #0x209 (98.09, 83.22) |
| others, 1-2 each | 11 | 0x227 `0x2E001312`, 0x228 `0x2E001237`, 0x229 / 0x22A `0x2E00131F`, 0x22B `0x2E001313`, 0x22C `0x2E001322`, 0x23C `0x2E00132F`, 0x256 `0x2E0012FF`, 0x278 `0x2E000A3B` (core pedestal), 0x283 `0x2E00036E`, 0x284 `0x2E001402` | 0x256 (53.62, 83.66) |

Full list with positions: `tools\diag.py` `STRIP3_INFO` (nearest first). No box of the 53 covers the strip; the
prime suspect by place is **#0x262** (an `0x2E0005D6`, the "red lava overlay" world state of Tutorial 1 tests that drew
as a grey square, whose stored box is 5 cm while its mesh is larger: the case "bounds data wrong"), but the video does
not separate the 51 (P, not identified).

### 8.4 `--strip3` (`--franja3`)

Start it in the menu (before Launch), like `--strip2`; the first cycle starts 75 s after the match's first frame. When each cycle starts it re-reads the IIDs, numbers the
recorded bit-9 statics that have a live node **#1..#N** (order of `STRIP3_INFO`, nearest first; unknown indices last)
and logs one `STRIP3   #n code nnnnnn: #index world state (x, y, z)` line each. Steps, 6 s each (~6.4 min for 51):

1. control: all N (the strip must go, as in the 21:33 run);
2. 12 **code** steps: "code bit k = 1" (every #n with bit k of n set), k = 0..5, then "code bit k = 0" (bit k clear);
3. one step per static ("ONE: #n ...").

Reading: one culprit -> for every k exactly one of "bit k = 1" / "bit k = 0" clears the strip, and n = sum of 2^k over
the "= 1" steps that cleared it; the ONE step #n confirms. If for some k both or neither clear it, the strip depends on
more than one static (both: any one of them hidden removes it; neither: each alone draws it), and the ONE steps list
them. A design that halves adaptively would need the tester's answer between steps; this one is fixed, so the whole
answer is in one recording.

### 8.5 Fix (O)

Unchanged plan: once #n is known, its entry type 7 -> 3 in `0x820113BB` (same-length edit with the terrainfix backup /
CRC-32 / Adler-32 machinery, switchable from config). Not written: no static is identified yet.

### 8.6 Tests

`tests/test_match.py` `strip3_bit9_list` (2 checks): the non-breakable bit-9 type-7 entries are exactly the 53 of
`STRIP3_INFO` (world states and positions), 30 of them `0x2E0005D6`, none of the breakables; diag has `--strip3` /
`--franja3`, the per-cycle numbering, 12 code steps and the ONE steps.

### 8.7 Tester

1. Game in the menu (before Launch), second console: `python tools\diag.py --strip3` (or `--franja3`).
2. Crime Alley v AI; walk to the strip and park the camera: with `--strip3` the first cycle starts 75 s after the
   match's first frame (was 10 s: in the 21:33 run the tester got there ~60 s in and cycle 1's steps 1-10 were lost).
   Record one full cycle (~6.5 min from `STRIP cycle 1 starts`) with the taskbar clock in the picture.
3. Send the recording and `logs\diag.log`. Nothing to patch (`python ic.py patch` not needed).
