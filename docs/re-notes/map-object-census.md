# Map object census: every placement on the v AI maps and who must bring it to the screen (2026-10-25)

Written incrementally (partial work survives). Scope: Crime Alley v AI `0x40000C82` (map pack `0xA0C112BA`),
Gotham Divided `0x40000399` / `0x40000B6B` (`0xA0C11AD2`), Coast City `0x40000270` / `0x40000B6A` (`0xA0C122E2`),
Gotham Heights `0x4000013E` / `0x40000B6C` (`0xA0C11AF2`); Tutorial 2 (`0xA0C112C2`) as the reference for Crime
Alley. Builds on `black-ground-shapes.md`, `map-manifests.md`, `map-loading-deep-scan.md`, `test-2026-10-25-1612.md`,
`full-maps-world.md` 2-3, `actor-creation-and-environment.md`. Tags: **C** confirmed (data / code read), **P**
probable, **G** guess, **O** open. Status: **MISSING** (should exist, server sends nothing), **WRONG** (sent, but
class / position / yaw / team / properties / scriptlets wrong), **HIDDEN** (client static that needs a server property
or object to show), **OK**.

Method (throw-away scripts in the session scratchpad, nothing of the game copied): every `0x82` statics record of
the nine landblocks of each map pack parsed with the corrected entry format (section 0.1); every world state resolved
to its `.entity` and bounding box through the map's three packs + the start-up packs; the spawn landblock's terrain
`0x80` heights scanned for sockets; ics' spawns read from `ics/match/*.py`, `ics/config.py` and `logs/traffic.log`
(17:47 Crime Alley, 17:52 Gotham Heights sessions).

## 0. Who brings a placement to the screen (client rules, C unless tagged)

### 0.1 Statics records (`0x82`), corrected entry format
`flags | type | [index | IID if flags & 0x04] | [world state if flags & 0x08] | xyz | quaternion w x y z |
[0 | n | props if flags & 0x80]`. The index / IID pair is **optional** (bit 0x04): Gotham Divided's first entry has
none, which is why earlier scans stopped at 567 / 568. With it every record parses to its header count: Crime Alley
388 (13BB 362, 12BB 17, 14BB 9), Tutorial 2 214 (13C3 header has 5 extra words: `did | 0x10000004 | ... | count`),
Gotham Divided 591 (1BD3 568, 1CD3 13, 1BD4 5, 1AD3 4, 1CD2 1), Coast City 798, Gotham Heights 670. Properties of
kind 3 (`0x576` light struct) do not parse (lights only).

### 0.2 What the client creates from them
- **Types 7, 8, 21 -> client entities** (`0x548550`, its loop over the 0x70-byte entries: `type == 8 || 7 || 0x15`),
  only if `0x54AF70` passes: the entry's world state is set **and its creation type (0x50F, read
  through the loaded record) is non-zero**; a type-8 entry whose mobility (`0x580160`) is 3 is skipped. Then
  `0x544A50` reads the `0x24E` / `0x55C` lists and the ruleset filter `0x53B4F0` (`0x55B` vs the encounter's
  `0x1000028A`). A world state that is in no loaded pack has no creation type -> the static is silently dropped.
- **Types 2 and 10 -> render-only** (mesh / point light) in `0x5EC4F0` (its loop tests `== 2`, then `== 10`), behind
  the same ruleset filter.
- **Types 3 and 16 are never instantiated** by any of these loops (C for the three loops read; P that no other
  walker exists: no other `* 0x70` walk of the statics list dispatches on the type). Type 16 = start points; type 3
  = server markers / derived world states (`did | 3 | base world state | 0 | n | props`, e.g. Gotham Heights
  `0x2E00041F` = base `0x2E000006` + team + id `0x1000005D`). **Correction to map-manifests.md 0/3/4**: the type-3
  team lights `0x2E000006` / `0x2E00041F`-`432` (GH) and `0x2E000940` / `941` / `942` (CC) are installed records
  but are *not* client-drawn; whatever they show only appears if the server creates them (P).
- Check of this census: on all four maps **every type 2 / 7 / 8 / 10 / 21 static's world state is in the map's
  three packs or the start-up packs** (C, resolver over `0xA00002E5/E6/E7`, `0xA0000168/FC/16E`,
  `0xA00000D2/161/162`, `0xA000009A/16B/179` + `0xA0000039/38/11A/37/DF/B3/103/351/D0`). Every unresolved world
  state belongs to a type-3 entry. So no client static is lost to a missing pack.

### 0.3 What a server object needs to be drawn
- Placement: a movement component (creation type 7 / 8, `0x580160` mobility 2) fed by the `0xB0` module part;
  bare world states of type 3 / 5 / 6 / 9 get `0x50F = 8` in the `0xBC` table (`World.spawn` does it; `0x54EF40` reads
  0x50F from the creation desc first, `0x64CA10` merges 0xBC into the desc before construction, so the override
  reaches step 3: C for the read order, P that it is enough; the turret plate is natively 8).
- Geometry: a world state draws either (a) inline mesh parts after its property list (`count | flags | n x 0x17
  DID | per part: format 0x?205102 | n vertices x 24 bytes | indices`, e.g. Coast City `0x2E000AD1`, eleven parts),
  or (b) through its `.entity` (`did | 0 | 0 | 0 | 1 | 0 | 1 | 0 | bbox min xyz, max xyz | ... Havok packfile`): a
  non-zero bounding box marks a model (turret plate `.entity 0x2D0008B6` 6.26 x 6.26 x 0.18 m, pedestal `0x2D000864`
  21 x 20 m, GD pit `0x2D0002D7` 10 x 10 x 2.5 m), or (c) children / particles from its scriptlets (the Tutorial 1
  crater `0x2E0004BE`: one-bone skeleton, no mesh, visible only through its Vfx keys).
- Visibility: `0x61CB30` returns true only if `0x2A1 && 0x76A && !0x90F` (defaults 1 / 1 / 0); its caller in the
  render component's property listener (`0x624D1E`) re-runs it on a change of `0x2A1` / `0x76A` / `0x90F` and sets
  render flag 1. Scale: render component `0x622F10` multiplies by `0x6B4` (f32) (C, fase3-cx).
- **Correction (black-ground-shapes.md 4.3, now O):** "`0x2A1` present without a value" does not prove a hidden
  object. The same no-value `0x2A1` is on the spawn platforms `0x2E000CA5` (static on CA / T2 / CC / GH, seen drawn by
  the tester) and on Gotham Heights' two ground meshes `0x2E000DEF` (176 x 160 m) / `0x2E000DF0` (C data). Either the
  no-value entry keeps the default (then the GD pit object is drawn and is not a floor), or GH's ground is hidden too
  (GH-2 "centre park near black" would fit). Only the diag of section 7 can tell.

## 1. Crime Alley v AI `0x40000C82` (LB `0x13BB`, ground 200.0, packs `0xA00002E5` / `E6` / `E7`)

Statics: 388 (13BB 362: type 7 x 317, 21 x 32, 3 x 18, 10 x 11, 16 x 10; 12BB 17 and 14BB 9 are backdrop). 175
distinct world states; the street itself is three big client meshes `0x2E001207` (origin (17, 77.5, 199.78), bbox
172 x 52 m), `0x2E001185` (200 x 100 m, z -9.7..0.3) and `0x2E000333` ((129, 52), 92 x 93 m).

### 1.1 Placements that matter (every type-3 / type-16 entry, every static with gameplay properties)

| DID / world state | What | Pos (x, y, z) / yaw | Who creates / shows it | Status | Exact server action | Conf / evidence |
|---|---|---|---|---|---|---|
| `0x2E0011A7` / `0x2E0011A6` t3 | core markers | (17.5, 77.15) -90 / (142.5, 77.75) 90 | server (not installed, t3) | OK | core `0x40000C8A` / `C89` at (17.5, 77.5) yaw 90 / (142.5, 77.5) yaw -90 | C (traffic 17:47) |
| `0x2E000A3B` t7 x3 | core pedestals | (17.5, 77.5, 200.12) 90 team 1 side 3; (142.5, 77.5) -90 team 2 side 5 with `0x55B = [0x10000009, 0x1000000C]` + a second copy `0x55B = [0x1000000B]` side 1 colour 1 | client (ruleset picks one) | OK | none | C |
| `0x2E0011A9` / `0x2E0011A8` t3 | dampener markers | (40.0, 77.5) -90 / (120.0, 77.5) 90 | server | OK body; **socket open** (1.3) | dampener `0x40000C88` / `C87` (Object_Activate, Vfx_Active, Vfx_AI_Active) + a socket cover that has geometry (section 1.3) | C markers, P cover |
| `0x2E0011AD` / `0x2E0011AC` t3 | lane-turret markers | (65.0, 77.5) -90 / (95.0, 77.5) 90 | server | OK | turret `0x40000C8C` / `C86` + head `0x2E000AA8` + plate `0x2E000A9F` (native ctype 8, no props) | C |
| (none) | core turret | (25.5, 77.5) / (134.5, 77.5) | server | OK (G pos) | `0x40000C8F` / `C8D`; the "prow" piece is still missing (crime-alley-still-missing 4) | G |
| `0x2E000AF9` / `0x2E000AF8` t3 | lane mouths, `0x100002E6 = {0x1000009C = 1 / 2}` | (21.75, 77.5) -90 / (138.3, 77.5) 90 | server data only (wave start) | OK | minions start here | C |
| `0x2E000944` + `0x2E000945` + `0x2E001117` + `0x2E001120` t3 | nook / camp markers | (80.0, 97.25) 180; (79.96, 97.13) 0 | server | OK (pad `0x40000CB5`, camp 0, Raider at 300 s) | as today | C markers, P class |
| `0x2E00110F` x2, `0x2E001110`, `0x2E00111B`, `0x2E001118`, `0x2E001121` t3 | ambient emitter markers (world states in no pack) | (80, 77.5), (110.5, 78.5) 180, (80, 77.5), (61.5, 77.5), (48.75, 93.0), (80, 119.0) | nobody can (no record) | MISSING, unfixable from data | none (substitute only, map-loading-deep-scan 5.4) | C |
| type 16 x10 | start points | team 1 (5, 77.5) / (6, 79.5) / (6, 75.5) / (7, 73.5) / (7, 81.5), team 2 mirrored | server data | OK | `maps.py` starts | C |
| `0x2E001253` t7 | ImpactPoint, `0x10000B5B = 0x100` | (82.12, 77.34, 199.71) | client | OK | none (target of cinematic `0x35000030`) | C |
| `0x2E0011FE` t7 | jungle-hole piece, scale `0x6B4 = 3.0`, `0x1EE = 1` | (80.0, 80.0, 188.48) | client | OK | none | C |
| `0x2E00101D` t7 (12BB) | creation type 5 prop, team 2, colour `0x10000CF0 = 1` | 12BB (152.77, 64.0) = world (-7.2, 64.0) yaw 131 | client | OK | none | C |
| `0x2E001242` t7 | `0x1ED = 1` | (125.5, 103.3, 184.1) 104 | client | OK | none | C |
| everything else (t7 x ~300, t10 x 11, t21 x 32) | street, fences, buildings, lights, waypoints | - | client | OK | none | C (all world states resolve) |
| server-only, no marker | base gates, base auras, foundries, stealth tiles, side camps, relay (tracker 26 / 1), red-orb rocks, bots | see map-manifests.md 1 | server | as map-manifests.md 1 (relay, rocks: MISSING) | - | - |

### 1.2 What ics sends (traffic.log 17:47:07 - 17:47:13)
0x20AF packs `0xA00002E5 E6 E7 116 73 22E 150 36D 36C 151`; spawns: core x2, core turret x2, dampener x2, lane turret
x2 (+ head, + plate each), foundry x2, socket cover x2 (`0x2E00119F`), base gate x2, base aura x2, stealth strip x6 (+
stealth mesh `0x2E000D37` x6), nook pad, camps 0-2, minion waves, the bot champion(s) of the lobby.

### 1.3 Why the socket covers `0x2E00119F` did not hide the black octagon

The octagon is the terrain socket (C): terrain `0x800113BB` lowers exactly two vertices, (40, 75) and (40, 80), to
179.96 m (ground 200.0), so the triangles around them form a 20 m deep funnel whose opening is x 35-45, y 70-85 (the
tester's 12 m octagon x 33-45.5, y 73.5-86). The mirror (120, 75) / (120, 80) is identical. The street meshes
`0x2E001207` / `0x2E001185` evidently leave this opening (the 200 m deep lane-turret socket at (60-75, 70-80) is NOT
seen, so the street covers that one: P).

The traffic.log bundle (line 3211, `spawn socket cover 0 (0x2e00119f)`, 106 bytes) decodes as: object `0x...0F`,
0xF2 class `0x2E00119F`, 0xB0 with the module (`62 01 01 0F`), Position region 1 / LB 0x13BB / x 40.0 / y 77.5 /
**z 200.0**, heading 0.0, facing -pi/2 (yaw -90), 0xBC table with **one entry: `0x50F = 8`** (the creation-type
override `World.spawn` adds because the world state's own 0x50F is 6). Cover 1: x 120.0, heading pi, facing +pi/2,
same table. So it was sent the right way (P: the override path is read in code, section 0.3, but the turret plate that
shows is natively type 8 and is sent with an empty table; the only in-game hint for the override is fase3-ga, where
the tester "walks through the first vehicle" of Tutorial 1, bare world state `0x2E000AAB` of creation type 5 sent with
`0x50F = 8`). Even if placed, it could not hide anything, because **`0x2E00119F` has nothing to draw** (C data,
P reading):

1. Its world-state record (`0xA00002E6`, 76 bytes; same in Tutorial 1's `0xA0000256`) is `did | 7 | .entity
   0x2D000EB2 | 0 | 4 | 0x50F = 6 | 0x7D2 = [0x1D000385] | 0x7EB = 7 | 0x2A4 = 1` and the next record (`0x400008CF`)
   starts right after it: **no inline mesh-part list** (compare `0x2E000AD1`: eleven 0x17 parts after its props).
2. Its `.entity 0x2D000EB2` (736 bytes) has an **all-zero bounding box** and a Havok packfile holding only one
   `hkaSkeleton` (`MainSkeleton`, one bone `autobone`); compare the turret plate's `.entity 0x2D0008B6` (bbox
   -3.13..3.13 x -3.12..3.14 x 0..0.18, drawn in game) and the pedestal's `0x2D000864` (21 x 20 m).
3. Its only scriptlet table `0x1D000385` holds the four shared team-colour keys (Vfx_TeamColor_SetNull,
   _CapturePoint_OnTeamBiasChanged, _Entity_OnSetClientRelationship, Vfx_TeamColor_SetContention), the same table the
   plate and the pedestal carry: no Vfx_Active / child that could add a model. Sending the team (the 17:47 follow-up
   `team_by_side`) cannot help.
4. In Tutorial 2 the same static (type 7, team `0x1000009C = -1`) sits in the same socket with **no structure marker
   there** (T2's markers are `0x2E0011AD` (25.5) / `0x2E0011AC` (75)); so in T2 too the socket was filled by something
   else or was never seen. The name "structure socket" fits an attach point (one bone, team colour) for the structure
   built on the site, not a floor (P).

What can fill it (ranked):
- **`0x2E0000E3`** (zone pack `0xA00002E5`, also Tutorial 1's `0xA000024C`): `.entity 0x2D00007B` bbox exactly
  **-5..5 x -10..10 x 0..2 m**, `0x50F = 3`, `0x7EB = 8`, `0x2A1` (no value); **placed by no static and no layout on
  any map** (C). It is the 10 x 20 member of a family of pit pieces with the same footprint scheme: `0x2E0003F0`
  (10 x 10 x 2.5, the GD pit box, placed by GD's statics exactly on its two one-vertex pit sockets), `0x2E0003EE` (10 x 20 x 2.5) and
  `0x2E0003E3` (15 x 20 x 5) in `0xA000009A` (C bboxes). A 10 x 20 piece centred on (40, 77.5) at yaw 0 covers the
  10 x 15 opening with 2.5 m to spare at each end (C geometry, **P** that it is the intended piece, G its look).
  Server action: bare world state `0x2E0000E3`, pos (40.0, 77.5, **198.0**) (top at 200.0) and (120.0, 77.5, 198.0),
  yaw 0, props `0x2A1 = true` (harmless if the no-value entry already means visible), `0x50F = 8` (automatic), no
  team, created before the dampener.
- Fallback (C mechanism, G look): the turret plate `0x2E000A9F` (in `0xA00002E6`, native ctype 8, drawn) with
  `0x6B4 = 2.5` (15.7 m) at (40.0, 77.5, 200.0) yaw -90 / (120.0, 77.5, 200.0) yaw 90.
- Keep `0x2E00119F` out of `match_socket_covers` (no effect; it only costs two objects).

## 2. Gotham Divided `0x40000399` / v AI `0x40000B6B` (LB `0x1BD3`, ground 249.9-250.0, packs `0xA0000168` / `FC` / `16E`; team 2 = (y, x))

Statics: 591 (1BD3 568: type 7 x 383, 21 x 124, 3 x 57, 10 x 15, 16 x 12). Ground: `0x2E000D61` ((80, 80, 250.0),
166 x 166 m), the two halves `0x2E000D60` / `0x2E000D64` ((80, 80, 247.0), 104 x 104 m each), `0x2E001327` /
`0x2E001328` (160 x 70 m strips), base shells `0x2E0010B9` / `BA` / `BB` / `0x2E001355` at (38.75, 121.5) yaw -134.5
(66 x 25 m). `0x962 = 4` sits on 168 statics (pedestal, tram, base shells; meaning O, not a visibility input).

| DID / world state | What | Pos (x, y, z) / yaw | Who | Status | Exact server action | Conf / evidence |
|---|---|---|---|---|---|---|
| `0x2E000A3B` t7 x2 | core pedestals | (17.5, 142.5, 250.05) 45 team 1; (142.5, 17.5) -135 team 2 | client | OK | none | C |
| `0x2E000CA5` + `0x2E001352` t7 x2 each | spawn platforms | (7.5, 152.5) -135, (6.87, 153.2) -135 / (152.72, 7.28) 45, (153.16, 6.83) 45 | client | OK | aura `0x40000C7F` on top (ics) | C |
| sockets (40, 150), (35, 125), (10, 120) and (150, 40), (125, 35), (120, 10): one vertex each at 199.98 (50 m deep) | **dampener sites** (each 22.5-24.7 m from its core, Crime Alley's dampener is 22.5 m from its core) | - | server | **MISSING cover** (GD-1 / GD-2 squares); dampeners: WRONG until `match_dampener_sockets` (already in config) is tested | cover: `0x2E0003F0` (10 x 10 x 2.5 m, in the sent `0xA00000FC`) at (40.0, 150.0, 247.47), (35.0, 125.0, 247.47), (10.0, 120.0, 247.47), (150.0, 40.0, 247.47), (125.0, 35.0, 247.47), (120.0, 10.0, 247.47), yaw 0, `0x2A1 = true`; dampener `0x40000C61` / `C60` on the vertex | C sockets, P role, P cover |
| `0x2E000EE1` t7 x6 | debris (1.24 x 1.14 x 0.45 m) on each lane-exit socket | (39.0, 149.5) -90, (35.5, 124.5) -135, (10.5, 121.0) 180; (149.5, 39.0) 0, (124.5, 35.5) 45, (121.0, 10.5) 90 | client | OK (it is not a gate frame) | none | C |
| `0x2E0003F0` t7 x2 | **pit box 10 x 10 x 2.5 m** (`.entity 0x2D0002D7`), static props `0x7EB = 6`, `0x2A1` (no value) | (55.0, 55.0, 247.47) 0 / (105.0, 105.0, 247.47) 0 (top at 249.98) | client | HIDDEN? (GD-3 black diamond) | server copy at both pits (`match_socket_covers`, already in config, untested); removed when a pod rises (`remove_cover_at`) | C geometry (fits the one-vertex sockets at (55, 55) / (105, 105) exactly), O why the static is not seen (section 0.3) |
| `0x2E000FBE` t7 x2 (`0x6B4 = 0.6`), `0x2E00133D` / `0x2E00133E` t7, point lights `0x2E000011` (colour `0xFFFF3F00`, radius 5) | tram and fittings in each pit | (55, 55) 103 / (105, 105) -58; (55, 55) / (105, 105) 180; z 249 | client | OK (tram seen) | none | C |
| `0x2E000AF4`-`AF9` t3 | lane mouths, team in `0x100002E6` | (17.5, 134.0) 180, (26.0, 142.5) -90, (23.5, 136.5) -135; team 2 (134.0, 17.5) 90, (142.5, 26.0) 0, (136.5, 23.5) 45 | server data | OK | minions start here | C |
| `0x2E000626` / `6B3` / `6B4` t3 x17 each | triples of generic markers (no record), e.g. (74.25, 77.88), (118.76, 118.68), (57.58, 100.70) | various | nobody (no record) | O role | none known (same triple on GH / CC: P ambient or ward spots) | C positions |
| `0x2E0013DD` t7 x15 | edge props with explicit `0x2A1 = 1`, zero bbox | map rim, e.g. (157.9, 51.56, 249.46) | client | OK | none | C |
| type 16 x12 | starts | (7.5, 152.5) centre + 5 slots / mirror | server data | OK | - | C |
| server-only, no marker | core, core turret, lane turrets, foundry, base gates, aura, pods / Raider / Leviathan, beacons (tracker 29 x4), jungle camps, bots | map-manifests.md 2 | server | as map-manifests.md 2 (beacons WRONG, pods NO before fase3-ht) | - | - |

ics today (`maps.py` + `[ics]`): dampeners on the socket vertices and gates 8 m back toward the base
(`match_dampener_sockets`, `gd_gate_setback`), pit lids `0x2E0003F0` with `0x2A1 = true` (`match_socket_covers`),
`match_extra_packs` {} (the `0xA00002E6` idea is moot: `0x2E00119F` has no geometry, 1.3).

## 3. Coast City `0x40000270` / v AI `0x40000B6A` (LB `0x23E3`, ground 250.0, packs `0xA00000D2` / `161` / `162`; team 2 = 160 - x)

Statics: 798 (23E3 792: type 7 x 511, 21 x 150, 3 x 76, 2 x 28, 10 x 21, 16 x 12). Ground: `0x2E000B87` ((80, 80,
249.98) 180 x 180 m flat, `0x7EB = 6`, `0x2A4` / `0x54F` no value, `0x7A3` appearance table), `0x2E000ABC` (160 x
160 m), `0x2E000ABB` / `ABD` (plaza plates), `0x2E000B7B` / `B7C` / `B7D` ((80, 80, 248.0) quadrant pieces).

| DID / world state | What | Pos (x, y, z) / yaw | Who | Status | Exact server action | Conf / evidence |
|---|---|---|---|---|---|---|
| `0x2E000A3B` t7 x2 | core pedestals (cover the core sockets (15-20, 60-65) / (140-145, 60-65)) | (17.0, 62.5, 250.08) 104.9 team 1 / (143.0, 62.5) 254.9 team 2 | client | OK | core `0x40000C24` / `C23` on top (ics) | C |
| `0x2E000CA5` t7 x2 | spawn platforms, team in `0x1000009C` | (3.21, 58.8) -75 / (156.79, 58.81) 75 | client | OK | aura on top (ics) | C |
| `0x2E000C57` t7 | device platform (`.entity` bbox 19.0 x 18.5 x 0.5 m) over the socket (80, 85) (one vertex at 199.98) | (80.0, 85.0, 249.75) 180 | client | OK (no black there) | none | C |
| `0x2E001178` + `0x2E001181` t3 | Doomsday Device site (no record) | (80.0, 82.02, 250.27) 180 | server | OK pos; behaviour WRONG (map-gaps-coast-city 2.5) | device `0x400001F0` + pad `0x4000054F` | C |
| `0x2E0005A4` t7 x2 | props flanking the device | (70.02, 82.15) 0 / (89.87, 81.29) 0 | client | OK | none | C |
| **socket (75-85, 65-75)**: 3 x 3 vertices at 0.0 (250 m deep), opening x 70-90, y 60-80 | the centre hole (CC-2; the tester's (84-94, 68-78) is its east half) | - | **O** | **MISSING** | see 3.1 | C socket, O occupant |
| `0x2E000AD1` + `0x2E000BE8` + `0x2E000BE7` t7 | plaza set; AD1 = 11 inline parts whose vertices span local x -63..65, y 33..79 -> world y -9..37 (the south plaza), table `0x1D000494` (`0x5`, Vfx_Active); BE8 / BE7 table `0x1D00053A` (`0x5`) | all at (80.01, 70.37, 249.97) 180 | client | OK, but **not a cover** (no part over (70-90, 60-80)) | none | C |
| `0x2E000C03` t7 | sunken fixture set (parts <= 3.5 m) | (79.61, 80.28, 246.85) 0 | client | OK | none | C |
| `0x2E000942` / `944` / `945` t3 (942 = derived record of `0x2E000006` in `0xA0000161`, the others not installed) | camp sites | (80.0, 145.0) / (80.0, 146.75) 180, (44.5, 90.5) 286, (115.5, 90.5) -280, (80.0, 9.0) 180, (80.0, 57.0) 180 | server | OK (camps, Raiders, Guardian at these) | - | C |
| `0x2E000940` / `0x2E000941` t3 (derived, installed) | team lights at the lane mouths, colour ids `0x1000005D` | (137.5, 60.5), (139.25, 67.0) / (22.5, 60.5), (20.75, 67.0) | **server** (type 3, 0.2) | MISSING (P) | bare world state at each, `0x50F = 8` (auto), team from the side, then `Vfx_Active_Blue` (team 1) / `_Red` (team 2) (table `0x1D0003E4` of base `0x2E000006`) | C record, P need |
| `0x2E000AF4`-`AF7` t3 | lane mouths, team in `0x100002E6` | as above | server data | OK | waves | C |
| `0x2E000626` / `6B3` / `6B4` t3 x17 each | generic triples (no record) | various | nobody | O | - | C |
| type 16 x12 | starts | (4.69, 59.17) centre + slots / mirror | server data | OK | - | C |
| server-only, no marker | turrets, inner turrets, core turret, foundry, base gates (two necks), aura, relays x3, Doomsday Guardian, stealth tiles, bots | map-manifests.md 3, map-gaps-coast-city.md | server | as there (gates WRONG: not solid, CC-1) | - | - |

### 3.1 What fills the Coast City hole (75-85, 65-75): open, with what was ruled out
- No static of the four lists has geometry over x 70-90, y 60-80 other than the 160 / 180 m ground meshes, which must
  have their opening there (the hole shows). The plaza set at (80.01, 70.37) has its origin there but its meshes
  lie in the south plaza (C, vertex bounds).
- The layout pack `0xA0000162` holds only the two end cinematics' actors (core, five players); the zone / variants
  packs hold no placement table naming a world state at (80, 70) (C, `Data.layout`).
- No world state of the three packs with an `.entity` box of 12-35 m and < 8 m height is unplaced except the base gate
  `0x2E000CD7` (C scan); the 10 x 20 / 15 x 20 pit pieces of section 1.3 are in other maps' packs only.
- It is symmetric about x = 80, 12 m south of the Device site (80, 82) and 3 m north of the Doomsday Guardian camp
  marker (80, 57): G, the Guardian's or the Device's pit, which the original server filled with an object of the
  encounter. Not settled.
- Server fix to try (G): a cover from the sent packs, the turret plate `0x2E000A9F` (in `0xA0000162`, native type 8)
  at (80.0, 70.0, 250.0) yaw 0 with `0x6B4 = 3.3` (20.7 m). Better first: the diag of section 7 with the client's
  own create log around (80, 70).

## 4. Gotham Heights `0x4000013E` / v AI `0x40000B6C` (LB `0x1BF3`, ground 249.9, packs `0xA000009A` / `16B` / `179`)

Statics: 670 (1BF3 629: type 7 x 422, 21 x 114, 3 x 81, 10 x 41, 16 x 12). Ground: `0x2E000DEF` ((80, 80, 249.37),
176 x 160 m) and `0x2E000DF0` (98 x 96 m), both with `0x2A1` (no value) in their world state; `0x2E0007A6` ((138.0,
91.8), 48 x 67 m). The east third of the terrain (x >= 130) lies at 200 m and is carried by statics (no black seen).

| DID / world state | What | Pos (x, y, z) / yaw | Who | Status | Exact server action | Conf / evidence |
|---|---|---|---|---|---|---|
| `0x2E000CA5` t7 x2 | spawn platforms | (4.0, 46.25, 250.02) -70 / (156.0, 46.25) 70 | client | OK | aura `0x4000041F` on top (ics) | C |
| type 21 x16 with `0x100003E7 = 0x10000188` | capture-point waypoints (3-4 per point) | (48.5, 27.5), (111.5, 27.5), (27.0, 90.0), (133.0, 90.25), (80.0, 127.75) | server data | OK (ics slots 1-5 there) | - | C |
| `0x2E000006` t3 x10 (base record, table `0x1D0003E4`: Vfx_Active_Blue / _Red / _Yellow) | centre ring, one team-1 and one team-2 entry per spot, ids `0x1000005D` 0x82-0x8B | (86.0, 75.0) -73, (74.0, 75.0) 76, (80.0, 80.0) 0, (83.75, 68.0) -144, (76.25, 68.0) -210 | **server** (type 3) | MISSING (P) | bare world state `0x2E000006` per entry (team from `0x100002E6`), colour by the Orbital Cannon's owner (Blue / Red, Yellow = neutral); G: they are the cannon's charge lights | C data, P need, G role |
| `0x2E00041F`-`0x2E000432` t3 x20 (derived from `0x2E000006`: `0x1F0 = 1`, `0x2A1` no value, team, id 43-62) | two spots per capture point, a team-1 and a team-2 record each | (12.5, 91.5) -199, (14.5, 97.5) -17 [point 3]; (36.5, 16.5) 56, (42.0, 12.5) -127 [point 1]; (118.0, 12.5) -236, (123.5, 16.5) -57 [point 2]; (147.5, 91.5) -164, (145.5, 97.5) 21 [point 4]; (76.5, 141.5) 92, (83.5, 141.5) -91 [point 5] | **server** (type 3) | MISSING (P) | create the record of the point's owner team (or both, Yellow while neutral) with Vfx_Active_Blue / _Red / _Yellow; switch on capture | C data, P need, G role |
| socket (115, 10)-(125, 25), six vertices at 0.0 | under the subway entrance statics `0x2E000F60` / `0x2E000F61` (124.37, 11.9) | - | client | OK (not seen black; tester did not go there) | none | C socket, P cover |
| `0x2E000626` / `6B3` / `6B4` t3 x17 each | generic triples (no record) | various | nobody | O | - | C |
| type 16 x12 | starts | (6.0, 47.0) centre + slots / mirror | server data | OK | - | C |
| server-only, no marker | Power Cores, foundries, base auras, capture points x5, Orbital Cannon (tracker 27 / 1, `match_cannon`), health-pack generators, stealth tiles, gates (none: GH-1), bots | map-manifests.md 4 | server | as there (no gate: MISSING, GH-1; cannon not seen spawned in the 17:52 log) | - | - |

## 5. Every terrain socket crossed with its occupant

Sockets = spawn-landblock terrain vertices >= 3 m below the map's ground, grouped 8-connected (map rims and the
plateaus outside the playable area left out). Opening = the ring of neighbour vertices.

| Map | Socket vertices -> z | Opening | Occupant (who) | Seen | Status / fix | Conf |
|---|---|---|---|---|---|---|
| CA | (15, 75), (15, 80), (20, 75), (20, 80) -> 0 | 10-25 x 70-85 | pedestal `0x2E000A3B` (client, 21 x 20 m) | ok | OK | C |
| CA | (40, 75), (40, 80) -> 180 | 35-45 x 70-85 | dampener (server) + nothing that covers (`0x2E00119F` has no geometry) | **black octagon** | MISSING: `0x2E0000E3` at (40, 77.5, 198.0) yaw 0 (P) | C socket, P fix |
| CA | (120, 75), (120, 80) -> 180 | 115-125 x 70-85 | same, team 2 | black (13:13 frame 110 s) | MISSING: `0x2E0000E3` at (120, 77.5, 198.0) yaw 0 | C / P |
| CA | (60-70, 70-80) 3 x 3 + (75, 80) -> 0 | 55-80 x 65-85 | no own model; the street mesh covers it (P) | ok | OK (nothing to do) | C socket, P cover |
| CA | (85, 50-65), (90, 55-60), (80, 65) -> 0 / 195 | outside the lane (y < 63.6) | street / `0x2E000691` (106.4, 58.4) | ok | OK | C |
| CA | (140, 75), (140, 80), (145, 75), (145, 80) -> 0 | 135-150 x 70-85 | pedestal (client) | ok | OK | C |
| T2 | (15-20, 75-80) -> 0; (40, 75 / 80) -> 180 | as CA | pedestal; socket marker `0x2E00119F` (no geometry) | - | reference only | C |
| GD | (40, 150), (35, 125), (10, 120) -> 199.98 | 10 x 10 each | debris `0x2E000EE1` only; dampener site (P) | **black squares** (GD-1 / GD-2) | MISSING: `0x2E0003F0` copy at z 247.47 yaw 0 + dampener on the vertex | C / P |
| GD | (150, 40), (125, 35), (120, 10) -> 199.98 | 10 x 10 each | same, team 2 | not visited | same, mirrored | C / P |
| GD | (55, 55), (105, 105) -> 0 | 10 x 10 each | pit box `0x2E0003F0` static (10 x 10 x 2.5) + tram | **black diamond** (GD-3) | HIDDEN?: server copy with `0x2A1 = true` (in config); pods rise here at 600 s | C geometry, O mechanism |
| GD | (15-20, 140-145) / (140-145, 15-20) -> 99.98 | 10-25 x 135-150 | pedestals (client) | ok | OK | C |
| CC | (15-20, 60-65) / (140-145, 60-65) -> 0 | 10-25 x 55-70 | pedestals (client) | ok | OK | C |
| CC | (75-85, 65-75) 3 x 3 -> 0 | 70-90 x 60-80 (20 x 20) | **nothing found** | **black polygon** (CC-2) | MISSING, occupant O (3.1); G cover plate `0x6B4 = 3.3` | C socket, O |
| CC | (80, 85) -> 199.98 | 75-85 x 80-90 | device platform `0x2E000C57` (client, 19 x 18.5 m) | ok | OK | C |
| GH | (115, 10), (115, 15), (120, 15), (120, 20), (125, 20), (125, 25) -> 0 | 110-130 x 5-30 | subway entrance `0x2E000F60` / `F61` (client) | not visited | OK (P) | C socket, P |

## 6. Ranked fix list (proposed `[ics]` keys; each a `config.py` default with the 2026-10-25 16:12 / 17:47 reports)

1. **Crime Alley dampener sockets: replace the cover.** `0x2E00119F` has no geometry (1.3, C). Proposed default
   (P, first in-game test):
   ```
   # 2026-10-25 17:47 (tester: octagon still there with 0x2E00119F sent; map-object-census.md 1.3, C: that world state
   # has no mesh, zero .entity box): the 10 x 20 m pit piece 0x2E0000E3 (zone pack 0xA00002E5) under each dampener
   "match_socket_covers": {"crime_alley": [
       {"world_state": "0x2E0000E3", "pos": [40.0, 77.5, 198.0], "yaw": 0.0, "props": {"0x2A1": True}, "team_by_side": False},
       {"world_state": "0x2E0000E3", "pos": [120.0, 77.5, 198.0], "yaw": 0.0, "props": {"0x2A1": True}, "team_by_side": False}],
     ...}
   ```
   Fallback if the piece does not show or looks wrong (C scale mechanism, G look): `0x2E000A9F` at (40.0, 77.5, 200.0)
   yaw -90 / (120.0, 77.5, 200.0) yaw 90 with `"props": {"0x6B4": 2.5}`. **Code note:** `Match._spawn_socket_covers`
   sends every non-bool prop as kind 0x10 int (`int(v)`), so a float scale would arrive as 2; floats must go as
   `KIND_F32` (0x09) for `0x6B4`.
2. **Gotham Divided lane-exit sockets: six pit boxes.** Same world state as the pits, in the sent pack `0xA00000FC`
   (P: the 10 x 10 one-vertex sockets match its 10 x 10 x 2.5 box exactly). Add to `match_socket_covers.gotham_divided`
   (absolute positions, yaw 0, z 247.47, `0x2A1 = true`, `team_by_side = False`): (40.0, 150.0), (35.0, 125.0), (10.0,
   120.0), (150.0, 40.0), (125.0, 35.0), (120.0, 10.0). Keep `match_dampener_sockets` (dampeners on the vertices: the
   22.5-24.7 m core distance matches Crime Alley's 22.5 m, P) and `gd_gate_setback` 8. Drop the `match_extra_packs`
   `0xA00002E6` idea (it only carried `0x2E00119F`).
3. **Gotham Divided pits: test what is already configured** (`0x2E0003F0` copies at (55, 55) / (105, 105) with `0x2A1 =
   true`). If the diamond stays, the static pit box is drawn and is not a floor (0.3): then cover with the fallback
   plate `0x2E000A9F` `0x6B4 = 1.7` at z 250.0 (G).
4. **Diag before more guessing** (`tools/diag.py`, new mode, not written by this survey): break on the return of
   `0x61CB30` (ECX + 4 = entity) logging `[ent + 0x110]` (world state), the IID and AL for world states `0x2E0003F0`,
   `0x2E000CA5`, `0x2E000DEF`, `0x2E0000E3`, `0x2E000A9F`; and a hit counter on `0x544A50` with the entry's world
   state (`[param_1 + 0x30]`) to list every static the client really creates around (80, 70) on Coast City. Settles
   0.3 (no-value `0x2A1`), the GD pit and the CC hole in one run.
5. **Coast City hole (75-85, 65-75):** occupant O (3.1). Until the diag: `match_socket_covers.coast_city = []`
   (default); test entry (G) `{"world_state": "0x2E000A9F", "pos": [80.0, 70.0, 250.0], "yaw": 0.0, "props": {"0x6B4":
   3.3}, "team_by_side": False}` (needs the float fix of 1).
6. **Type-3 derived world states the client never creates (0.2; P need, G look):** new key
   ```
   # 2026-10-25 (map-object-census.md 0.2, C: 0x548550 instantiates only static types 7 / 8 / 21): installed type-3
   # world states the server places (bare world state, 0x50F = 8, team from 0x100002E6, start scriptlet by side)
   "match_marker_statics": {
       "gotham_heights": {"world_states": ["0x2E000006", "0x2E00041F-0x2E000432"],
                          "scriptlets": {"1": "Vfx_Active_Blue", "2": "Vfx_Active_Red", "0": "Vfx_Active_Yellow"}},
       "coast_city": {"world_states": ["0x2E000940", "0x2E000941"],
                      "scriptlets": {"1": "Vfx_Active_Blue", "2": "Vfx_Active_Red"}}},
   ```
   placed at the statics' own positions / yaws (read from the map pack at match start, no hand-written list). Test on
   GH first (the ring around the Orbital Cannon and the point lights should light up).
7. **Remove** the two `0x2E00119F` entries (no effect, item 1) and correct catalog `world_objects.tsv` row
   `0x2E00119F` ("Structure socket cover" -> "structure socket: attach point, no geometry"), `black-ground-shapes.md`
   4.1 / 4.2 / 4.3 and `map-manifests.md` 0 / 3 / 4 (client-drawn team lights -> server) when the fixes land.
8. Unchanged from map-manifests.md 5 (not repeated here): Crime Alley relay (tracker 26 / 1) and red-orb rocks, GD
   beacons as tracker slots, Coast City gates that do not block (CC-1) and the Device's pad-aimed strike, Gotham
   Heights base gates (GH-1) and the cannon spawn (not seen in the 17:52 traffic), bot champions everywhere.

## 7. Evidence index (addresses and records used)

`0x548550` (static types 7 / 8 / 21 -> entities), `0x54AF70` (needs world state + creation type; type 8 mobility 3
skipped), `0x544A50` (`0x24E` / `0x55C`, ruleset `0x53B4F0`), `0x5EC4F0` (types 2 / 10), `0x61CB30` (visibility),
`0x624D1E` (its re-run on 0x2A1 / 0x76A / 0x90F changes), `0x54EF40` / `0x54F0B0` (creation type from the desc first,
entity +0x114), `0x53BB00` (terrain vertex (i, j) = (x 5 i, y 5 j), height index i * 33 + j), `0x622F10` (scale
`0x6B4`). Records: `0x2E00119F` / `0x2D000EB2` (`0xA00002E6`), `0x2E0000E3` / `0x2D00007B` (`0xA00002E5`),
`0x2E0003F0` / `0x2D0002D7` (`0xA00000FC`), `0x2E000A9F` / `0x2D0008B6`, `0x2E000A3B` / `0x2D000864`, `0x2E000AD1`,
`0x2E000C57` / `0x2D000A3E`, `0x2E00041F`-`432` / `0x2E000006` (`0xA000016B`), terrain `0x800113BB`, `0x800113C3`,
`0x80011BD3`, `0x800123E3`, `0x80011BF3`; statics `0x820113BB`, `0x820113C3`, `0x82011BD3`, `0x820123E3`,
`0x82011BF3`; traffic.log 17:47:12.708 (lines 3211 / 3219).
