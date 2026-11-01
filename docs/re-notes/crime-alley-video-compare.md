# Crime Alley: original video vs our server (tester recording 2026-10-24) — work in progress

Sources: original game `crime_alley_map_video.mp4` (554 s, 1276x720) and our server's recording
`2026-10-24 22-54-44.mp4` (490 s, 1280x720). Frames sampled with cv2 into the scratchpad only (never in the repo).
Tags: C = read in the data, P = probable, G = guessed (frames), O = open. Earlier survey:
`crime-alley-missing-elements.md`.

## Log

### Method
- Frames every 10 s from both videos, contact sheets, then full-res frames at matching moments (both clocks 01:09:
  original 150 s, ours 80 s).
- Screen -> world: in our frame the 8 stealth tiles sit at known positions (`maps.py`: x 75/79/83/85 y 81.5,
  x 73/75/85/87 y 73.5), their centre crosses give a ground homography G (fit error < 0.06 m). Original frame ->
  our frame: SIFT on the ground (cracks), RANSAC homography H (35 inliers, overlay checked by eye). An original
  pixel goes through H then G to world metres.

### Stealth zones in the original (first pass, the map-centre set) — G (frames), position error ~0.3 m
- Our tiles are drawn with their 4 m side along **y** (yaw 0 as spawned): each shows 3 hexes across x, 5-6 rows
  along y, and they sit 8 m apart across the lane centre. The original's strips lie **along the lane (long side
  along x)**, flat, two hex rows deep, and hug the lane edges (fence / curb).
- Original set at the map centre (frame 150 s), bbox incl. glow:
  - North: one strip x 76.4-83.6, y 81.3-83.4, centre (80.0, 82.3), ~7.2 x 2 m = two 4 x 2 tiles end to end
    (P: (78, 82.3) and (82, 82.3) at yaw 90) or one stretched object.
  - South: two strips, x 74.5-78.5 and 81.7-85.6, y 71.3-73.2, centres (76.6, 72.2) and (83.6, 72.3), ~4 x 2 m
    each = one tile each at yaw 90; the 3 m gap between them is centred on x 80.
  - A red glowing object in the gap at (80.1, 72.8) (not in ours) — see below.
- Ours (for comparison): y 81.5 / 73.5 (1 m nearer the centre line than the original's 82.3 / 72.2), wrong yaw,
  4 north + 4 south tiles.

### Data check: no stealth placements in the map data (C)
- Statics `0x820113BB` (362 entries), `0x820112BB` (17), `0x820114BB` (9) of `0xA0C112BA` parsed again: no entry with
  world state `0x2E000D36`; byte scan of every `rp\*.rp` for `0x2E000D36` / `0x4000039D` / `0x4800028C`: only the
  records themselves and their table-of-contents references (packs `0xA00000FC`, `0xA0000162`, `0xA000016B`,
  `0xA0000256`, `0xA00002E6`); the 7 hits of `0x4000039D` in `0xA0000351` are a database record field
  (`0x10000C0A = 0x4000039D`), not placements; the 2 hits of `0x4800028C` in `0xA0C122E2` fall inside texture data.
  The original server placed the strips from its own data, so positions can only come from the video.

### Minimap calibration (original, 1276x720 frame, minimap crop x 1110-1276, y 560-720)
- At 4x zoom of that crop: x_world = 65 + (px - 287) / 4.2 (blue icons 180 = 40, 287 = 65; red 413 = 95, 518 = 120).
  Jungle-camp diamonds at x 48.3 / 80.5 / 112.1, ~14 m north of the lane (y ~92 / ~98 / ~92).

### More stealth zones: the jungle passage mouths (original) — G
- Frame 86 s (camera at the x 40 dampener, minimap player x 41.4): a hex field **oriented along y** in the opening
  of the north fence, x 50.5-53.0, y 83.7 to beyond the top of the screen (> 88), centre about (51.7, 86): i.e.
  inside the west jungle passage (48-56, y 83-96; waypoint `0x2E000000` at (51.5, 88.75)). Frame 392 s (camera at
  the x 120 dampener): the mirror one at the top left, about x 105-108 (P mirror (108.3, 86)).

### Red glowing rubble piles (original only) — G positions, O identity
- A small rubble heap with a dark orb on top and a red glow (about 1.5 m). Seen at (80.1, 72.8) (south lane edge,
  in the gap between the two south strips), (54.7, 82.9) (west jungle mouth, beside the fence opening) and the
  mirror near (105, 83). No static near any of them (statics checked within 3.5 m): server-spawned in the original.

### Jungle-mouth fields, refined (original) — G
- West: frames 82 / 86 s; east: frames 340-400 s and 382 s (anchored on the destroyed x 95 turret plate). Both are
  clipped by the top of the screen in every frame (the camera never shows their north end). Visible part: west
  x 50.5-53.0, east x 106.6-109.5, both starting at the fence line y ~83.5 (fence statics at y 83.46-83.66) and
  running north (> 3 m visible). Width ~2.5 m incl. glow = a 4 x 2 tile at **yaw 0** (2 m along x, 4 m along y),
  P centres (51.7, 85.5) and (108.3, 85.5), mirror-symmetric about x 80.
- Red rubble beside each mouth: (54.7, 82.9) and (105.0, 82.7) (mirror pair, +-0.3 m).

### Our recording: minimap calibration
- Our 1280x720 capture (game window under a title bar): minimap crop x 1115-1280, y 560-650 at 4x:
  x_world = 65 + (px - 278) / 4.23 (blue 170 = 40, 278 = 65; red 405 = 95, 515 = 120). Our minimap shows a blue icon
  at ~105 (x ~24, the G core turret), the original shows none apart from the core blob.

### Structures: original vs ours (frames 40-92 s original, 25-40 s and 180 s ours)
- **Dampener (x 40 / 120).** Original: a round ring plate (~6-7 m, light grey, segmented rim; NOT the gear plate)
  with a dark pedestal (red trim) and a stacked blue hologram tower. Ours: the gear plate `0x2E000A9F` plus the
  hologram, and a **flat black octagon about 12 m across** centred near (40, ~79) (x ~33-45.5, y ~73.5-86), seen in
  frames 35, 37, 40, 180 s. The turret at 65 with the same plate has no octagon, so it comes with the dampener
  (class `0x40000C88` / `0x40000C87` / Clash `0x40000C91`, world state `0x2E000E04`, entity `0x2D000BAF`, in the sent
  pack `0xA00002E6`). P: the octagon is the dampener's own base piece drawn without its material / team colour
  (an unstarted Vfx or base state), and the gear plate under the dampener is extra.
- **Lane turret (65 / 95).** Original: the gear-rimmed plate (= `0x2E000A9F`; it stays after the turret dies, frame
  382 s at 95) with a dark pedestal and a standing hologram. Ours: plate present; the head reads as a tilted "C"
  hologram with little pedestal visible (camera-dependent; O).
- **Core turret.** Original: a hologram turret standing on the core platform's eastern prow (a static core piece),
  no separate plate, directly west of the gate wall (frames 56-80 s). Ours: class `0x40000C8F` (world state
  `0x2E000AC4`, not `0x2E000AA0`) at the G spot (25.5, 77.5) with the gear plate under it, at the platform's edge.
- **Base gate.** Original: tall blue light wall at the prow's end (x ~29.5, along y) from the countdown until 0:00
  (frames 56-80 s). Ours: not visible in frames 25-37 s (timer 00:14-00:26 counting up), camera over that spot.

### Ground decoration missing in ours (aligned frames 150 s / 80 s, warped overlay) — C (frames), O (source)
- Original: **glowing orange "lava" cracks** running across the street (long lines, e.g. near x ~69-70 and ~88-89
  around the centre, and all along the lane down to the x 40 dampener and the bases) and **ember craters** (dark
  scorch pits with burning embers, ~1.5 m), e.g. (68.6, 80.5), (71.4, 79.6), (70.7, 75.7), (89.9, 80.7), plus many
  around the dampeners and turrets. Present from 00:05 before any fight and at the same spots in every frame:
  static scenery. Ours: neither the orange cracks nor the craters appear anywhere (frames 40, 80, 180 s), while
  the big central cracked-paving area matches.
- No `0x82` static lies within 1.5 m of any crater (so they are not statics). Candidates (O): the landblock info
  records `0x810113BB` (map pack `0xA0C112BA` offset ~0x405462C, starts `0x0C | ... | 0x1D000000 | 0x4E270013`) or the
  terrain `0x800113BB` layer; or emitters started by the zone environment. Also the original's night lighting is
  blue-tinted and darker; ours is neutral / brighter (G: an environment / lighting setting not applied).

## Summary (ranked)
1. Stealth zones: 5 in the original, none of them where ours are (see above). Centre: north strip 2 tiles yaw 90 at
   (78, 82.3) + (82, 82.3); south 1 tile yaw 90 at (76.6, 72.2) and at (83.6, 72.3). Jungle mouths: 1 tile yaw 0 at
   (51.7, ~85.5) and (108.3, ~85.5). All G (frames), +-0.3 m centre set, +-1 m mouths.
2. Lava cracks + ember craters missing everywhere in ours (C frames, O source).
3. Dampener: black ~12 m octagon in ours, original has a round ring plate and no gear plate (C frames, P cause).
4. Red glowing rubble piles at (80.1, 72.8), (54.7, 82.9), (105.0, 82.7) missing in ours (C frames, O identity).
5. Core turret: original on the core prow with no plate; ours has a plate and class world state `0x2E000AC4` (P).
6. Base gate not seen in our recording during 00:14-00:26 (P).
