# Crime Alley: the centre strip is the street piece's fog occluder, the ring's remaining gates (2026-10-29, fase3-ip)

Tester report 2026-10-29 23:03 (build fase3-io, exe re-patched 22:36 with the perception-filter patch; Crime Alley v AI,
Gaslight Batman vs AI Sinestro, match 22:39:35-22:51:49): (1) "the middle zone still has the hole" (`83.webp`, match
01:41); (2) "the turret marks (green, yellow, red) still don't show". Evidence: `server.log` / `traffic.log` of that run
(no diag.log), `83.webp`, the installed map pack `0xA0C112BA`, the patched exe (read only), the decompiled client
(`re-work/decomp`, image base 0x400000; file offset = VA - 0x400C00 in .text), capstone reads, and the fase3-io diag
(`ca-fog-minimap-ring.md` 1.1). Tags: **C** confirmed, **P** probable, **O** open. Builds on `ca-black-strips.md`,
`ca-fog-ring-announcer.md` 1, `ca-ring-fog-bundles.md`, `ca-fog-minimap-ring.md`.

## 1. The black strip in the centre (item 1)

### 1.1 Where (C, camera fit)
Camera model of `stealth-alignment.md` 4.1 (yaw 0, pitch 57.5, vertical FOV 46.1 deg, 14.35 m above z 200.11; f = 1183
px for the 1007 px frame), translation fitted on the south-west stealth tile's "+" (screen (1195, 770) = (76.6, 72.2)):
the blue turret lands at (377, 421) (seen ~(380, 430)), the north tiles' near edge at row 245. The black (pixels with
RGB sum < 20) is rows 162-225, from screen x 748 (row 225) / 874 (row 163) to the tiles at 1110: ground **x 70.05 ->
76.3, y 81.8 -> 83.4**, west edge from (70.05, 81.87) to (72.14, 83.41), slope 0.74. That is the same strip and the same
edge as `49.webp` (fase3-ik: (70.07, 81.47) - (72.36, 83.11), slope 0.72) with another champion (Batman, not AGL) at
another spot (~(73.6, 76.3)): it is fixed in the world. Extended, the edge passes 0.6 m from our lane turret (65, 77.5)
and the wrong way for Batman. A second, smaller black patch on the south curb (x 78.8-79.7, y ~72) sits in the gap
between the two south tiles.

### 1.2 What it is not (C)
- Terrain: `crime_alley_lane_turret` reads "patched" in the installed pack (`terrainfix.installed_state`); the cell
  (70-75, 80-85) is flat at 199.98 m (`ca-black-strips.md` 4).
- Missing statics: every 13BB static near (62-92, 78-88) was listed again from `0x820113BB` (entries with the index /
  IID pair): fence pieces `0x2E001324` (71.48, 83.65), `0x2E0012F6` (74.48, 83.65), `0x2E0004D7` (78.68, 83.66),
  `0x2E00097C` (83.88, 83.46), chain link `0x2E0008F5` (87.88 / 90.88), the curb piece `0x2E001219` (64.5, 83.2), garden
  pieces north of y 84.98; all resolve to a loaded pack (`map-object-census.md` 0.2). None covers the strip; none is a
  decal. Their 0x7EB: the fences 11 / 17 (not vision blockers).

### 1.3 What it is (C mechanism, C data, P that the turret is the source)
- The fase3-io diag (`--fog`, 21:04-21:07) named **one occluder body for every source: `0x01113BB0000000B8`**, i.e. map
  static #0xB8 of 13BB. In `0x820113BB` that entry is **world state `0x2E001207` at (17, 77.5, 199.78)**, the whole-lane
  piece (bbox 172 x 52 m) that has no render geometry (`deep-scan-maps.md` 11), and its world state carries
  **`0x7EB = 7`**: a vision blocker for `0xA4B920` (map static, 0x7EB 7 / 8). So the street's collision is the occluder.
- The pass (`0xAAE0E0`): per source with radius > 0, unless `0x974940(source, 0x100008CE)` is true, a query box of
  (r, r, 0.001) at the source + 0.25 m z (`0x3A83126F` = 0.001, C) runs every overlapping occluder body's shape into the
  fog collector (`0xE600D0`, ctx +0x100, radius ctx +0x114). This client fills the region **between** the source and the
  blocker (57.webp's wedge with its apex on AGL, `ca-fog-ring-announcer.md` 1.2), here the polygon from the turret to the
  street piece's edge along the fence; the lane mesh is drawn over its south part, so only y 81.8-83.4 stays black.
- Who runs it: in fase3-io the champion read al 1 (skip) from its bundles on, the foundry always 1, **core t1, core
  turret, inner and lane turret t1 al 0 all match**. In this run the lane turret's creation bundle carried
  `0x100008CE = true` (traffic 22:39:24.155: `ce 08 00 10 48 ce 01`) and the strip stayed: the creation-bundle value
  did not take either (P; no diag to read al). The strip's edge is a ray from the lane turret (P, 0.6 m off).

### 1.4 Fix (exe patch)
`icserver/patcher.py` "fog occluder pass": file offset **`0x6AD624`** `80 7d ff 00 0f 85 3c 01 00 00` (cmp byte
[ebp-1], 0 / jne 0xaae36a) -> `e9 41 01 00 00 90 90 90 90 90` (jmp 0xaae36a). Every source takes the skip branch, which
is what `[ics] vision_through_blockers` meant for every allied source; the server's own fog still hides enemies behind
walls (navmesh line). `[game] exe_patch_skip = ["fog occluder pass"]` restores the bytes. **`python ic.py patch`**
needed (game closed). The `--fog` probe at 0x6AE209 still fires (before the patched jump); its al no longer matters.

## 2. The turret ring (item 2)

### 2.1 The patch is in place (C)
`InfiniteCrisis_patched.exe` at 0x451544: `84 c0 90 90 f6 46 58 01` (original `84 c0 75 e0 ...`).

### 2.2 The rest of the chain, read again (C code)
- Registration `0xA7CA20` (entity added): Turret bit of the cached unit flags, `0x10000C5D`, not allied, radius
  `0x9CFC40` (unit comp +0x8C, -1 until a change) -> entry +0 IID, +8 `0x10000C5B`, +9 dead, +0x10 `0x10000C66`, +0x20 r,
  +0x24 r^2, +0x28 r + 5.5, +0x2C (r + 5.5)^2, +0x30 (r + 1)^2, +0x34 difference; `(r + 1)^2 <= 0` = not registered;
  then `0xA2A710` builds the phantom (box half size r + 5.5) and listens to 0x10000C5B / C66 / B2D / 0xFA. fase3-io's diag
  saw the four enemy structures registered.
- Filter `0x852210` (class `0x15ECA98`, ctor `0x8528F0`: +0x58 = 0, +0x68 team -1, +0x6C 0, +0x70 0x7FFFFF, +0x74 0;
  `0xA2A710` then sets +0x68 = `0x854050(turret)`, +0x6C = 2, +0x70 = 0x210000): `0x852110` (entity of the body; IID top
  byte 2 refused unless patched; `0x403` true refused; base filter `0x5BC020` with empty lists passes), then
  PerceivedType & 0x210000, then `0x853380(turret team, body team) & 2`. `0x854050` reads the **unit component's team
  cache +0x4C** (ctor `0x979170`: -1; watcher vtable `0x15F97F0` slots 2 / 3 store it only on a notify of kind 0x10),
  falling back to the owner chain: -1 on either side gives 2 (passes), so the relation does not block an ics unit (P:
  both caches are -1 or the real teams).
- Callback `0xA3A5F0`: Minion 0x10000 -> unit list; else Player 0x200000 and IID == local champion (`0x85D6D0`) ->
  entry +0x4C. The champion's unit flags change `8 | 0x200000` was sent at 22:39:35.418 (traffic), and its bundles keep
  it (fase3-in).
- Draw `0xA84FB0` per frame (`0xA8C960`): state 6 unless +9 == 0 and +0x4C != 0; option byte `0x186CE4F` (1 in .data);
  first non-hidden state: ring effect DID from `0x439E00(&out, 0x100000E4, 0xF)` (null = nothing), object
  `0xA12E50` -> `0xA33F40` into +0x1C; on a state change `_TurretWarning_WarningState 0x1000103D` on the turret.
- What the server sends for it is complete (bundle 0x10000C5D / C5B / 0x133 / 0x1000019D, flags changes, C66 on target).
  **O**: whether the Havok phantom ever reports the local champion's (or a minion's) body; the filter's entry is
  reached only for bodies the broadphase pairs with the phantom. No static read can settle that.

### 2.3 New probes (`tools\diag.py --ring`)
| RVA | Line | Reading |
|---|---|---|
| 0x452144 | `filter: body IID top byte 2` (existing) | al 1 with the patch = the body reached the filter |
| **0x452220** | `filter: base checks` | eax != 0 = refused by 0x852110 (no entity / 0x403 / base filter) |
| **0x45227A** | `filter: PerceivedType` | al 0 = refused (mask 0x210000) |
| **0x45228E** | `filter: relation` | rel & 2 = 0 refused; turret_team / body_team (-1 = not cached) |
| 0x63A5F0 / 0x63A69D / 0x63A6C5 | `phantom: ...` (existing) | the callback, Player bit, champion inside |
| **0x685294** | `draw: effect DID from 0x100000E4` | did == null_did = nothing drawn; option byte |
| **0x6852F5** | `draw: ring object` | 0 = not created |
| **0x68535A** | `state change` | new / old state (1, 2, 3, 5, 6), option byte |

Reading: no `filter` line naming the champion's IID (`body_lo=0x2`) while walking into r + 5.5 of the enemy lane turret
= the phantom never pairs with our champion's body (next: the champion's physics / collision layer); a `filter` line
refused at one gate names it; `phantom: our champion inside` without `draw` lines = the option byte or the 0x100000E4
lookup; `draw` lines without a ring on screen = the effect.

## 3. Tests
`tests/test_match.py` `street_occluder_ring` (4 checks): the patch's jmp lands on the jne's own skip target 0xaae36a, the
installed exe holds the original or patched bytes, static #0xB8 of 13BB is 0x2E001207 with 0x7EB = 7, the new diag
probes are listed.

## 4. Tester
1. Close the game, `python ic.py patch` (prints "applied: fog occluder pass ..."), Crime Alley v AI.
2. Stand east of the blue lane turret (as `83.webp`): the sidewalk between the lane and the fence shows bricks and the
   curb, no black strip; no black wedge by a vehicle either.
3. Ring: in a second console `python tools\diag.py --ring`, then walk from our turret toward the enemy lane turret
   (x 95) once with our wave under it and once alone until it shoots; send `logs\diag.log`, `server.log`, `traffic.log`.
