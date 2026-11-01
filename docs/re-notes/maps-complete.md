# Maps and encounters, complete data (static survey, 2026-10-21)

Read-only survey of the player's packs (`C:\Infinite Crisis Server\rp`), building on `maps-encounters.md`,
`movement-collision-fog-map.md` and `tutorial-data-inventory.md`. Only IDs, short internal names, numbers and
positions are recorded. **C** = confirmed (read from the data), **P** = probable (strong inference from the data),
**G** = guessed / proposed (fits the data, untested in the game).

Conventions: positions are `(x, y)` in metres, local to the encounter's **spawn landblock** (template property
`0x1000021D`, see 1.2); a landblock is 160 m, so a point in the landblock east of it is `x + 160`. `z` is the
map's own frame (Tutorial / Crime Alley maps ~200, Gotham / Coast City maps ~250). Yaw in degrees.

How it was read (scratch tools, not in the project): the encounter templates with `ics.records` (header 2, and
header **1** for the 7 test / ARAM templates that `Data.record` misses); a record segmenter (longest increasing
chain of DID occurrences in pack-list order, numpy-accelerated, same idea as `rp._placed_starts`); a statics
(`0x82`) parser (format in 2.2); a cinematic actor scanner (names may contain spaces and dashes); a navmesh
parser derived from `ics/navmesh.py` with the two fixes of 2.4; a reference scanner over every installed pack
(616 packs) for section 4; `ics.script_model` for the scripts.

---------------------------------------------------------------------------------------------------------------

## 0. New findings and corrections (summary)

| # | Finding | |
|---|---|---|
| 1 | **Static type 16 = player start points.** Entries of type 16 carry no world state (statics flag `0x08` clear). Every map has them: 1 per team "centre" + 5 per team "slots" on the 5v5 maps, 1 + 4 per team on Crime Alley, a single one on each tutorial (Tutorial 1 at (18.5, 59.9): the spawn `ics` already uses, (18.7, 60.4), found by hand). | C positions, P role (strong) |
| 2 | **Statics entry format corrected:** `flags | type | index | IID | [world state if flags & 0x08] | xyz | quaternion | [0 | n | props if flags & 0x80]`. With it, every `0x82` record parses to its header count (Tutorial 1 858/858, Crime Alley 362/362, GH 629/629, CC 792/792, GD 567/568). | C |
| 3 | **Statics can be filtered by ruleset:** property `0x55B` = array of `0x605` = values of the template's ruleset enum `0x1000028A`. Crime Alley has two team-2 core pedestals at (142.5, 77.5): one with `[0x10000009, 0x1000000C]` (normal, Clash; side 5), one with `[0x1000000B]` (1vAI tutorial; side 1 = PvE enemy). | C data, P meaning |
| 4 | **`ics/navmesh.py` reads the wrong cell count and cannot read big-endian blobs.** The real NavCell count is the `count | offset` pair at blob `+0x98` (the `+0x2C` word, 19, is something else). Gotham Divided's three blobs are **big-endian** (blob `+0x0C` = 1): every u32/u16/f32 is swapped and the half-edge start vertex is the **first** u16. Today the server loads 558 of 1579 triangles on GH, 547 of 1690 on CC, 0 on GD; fixed: all type-21 waypoints of every map fall on the mesh. Section 2.4. | C |
| 5 | Every playable area lies inside the spawn landblock (0..160 m); the other 8 landblocks only hold scenery. | C (navmesh bounds) |
| 6 | **Structure sites on Crime Alley are marked by type-3 statics** `0x2E0011A6`-`0x2E0011AD` (world states in no installed pack) at exactly the cores (17.5 / 142.5), the turrets of cinematic `0x35000038` (65 / 95) and a second structure (40 / 120). The same `0x2E0011AD` / `0x2E0011AC` mark Tutorial 2's turrets (25.5 / 75, = its cinematic turrets 25.1 / 75.0). | C positions, P roles |
| 7 | **Lane mouths:** team-tagged type-3 statics `0x2E000AF4`-`0x2E000AF9` (property `0x100002E6 = {0x1000009C = team}`) sit one per lane per team where the lane leaves the base: 1 per team on Crime Alley, 2 on Coast City, 3 on Gotham Divided. Tutorial 2's `01BlueSpawner` drones leave from that point (22.3 vs 21.8): **minion waves spawn there**. | C positions, P role |
| 8 | Core pedestals `0x2E000A3B` are client statics (team 1 / 2) on GD, CC and Crime Alley: the core positions are in the map data, not only in the cinematics. | C |
| 9 | Corrections: Tutorial 2 (`0x40000A81`)'s objective list is **`0x48000E3B`** and carries the per-objective scripts (`0x34000601` / `602` / `603` / `604`); the Crime Alley 1vAI tutorial (`0x40000CA6`) has objective list **`0x48001150`** (15 objectives, no scripts) and the encounter script `0x34000628` (`tutorial-data-inventory.md` 1 put `0x48000E3B` on `0x49000CA6`). Script `0x340002CF` is not a capture script: it is a "generator" that fires impacts at a team (4 tiers), in Gotham Heights' layout pack only (section 5.2). | C |
| 10 | Gotham Heights: 5 capture-point markers (`0x10000188`), a team-tagged 5-socket ring of `0x2E000006` at the map centre (80, 74) and two team-variant statics near each point. | C positions, P/G roles |

---------------------------------------------------------------------------------------------------------------

## 1. The 28 encounter templates

### 1.1 Table

All templates are in pack `0xA00000B3`. Columns: category `0x10000D0B` (1 vs AI, 2 challenge, 3 PvP, 4 tutorial,
5 test, 6 surrogate); ruleset `0x1000028A` (low digit: 9 normal, B 1vAI tutorial, C Clash, D 5v5 vs AI); map id
`0x1000054E`; spawn landblock `0x1000021D` (`0x100005ED.0x1000001F = (1, lb x, lb y)`); `21C` = `0x1000021C` (s),
`4A1` = `0x100004A1` (s); players `0x10000BCB` per team / `0x10000BCC` total; lanes `0x10000BB7`; UI / objective
record `0x100001D2`; minimap `0x10000287`.

| Encounter | Internal (`0x1000062B`) | Cat | Rule | Map | Map pack | Inst. | Spawn LB | 21C | 4A1 | Players | Lanes | `0x100001D2` | Minimap | Shop `0x1000081E` | Announcer `0x10000802` | Other |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| 0x4000013E Gotham Heights | pvp_5v5_got_dom_team1 | 3 | 9 | 3 | 0xA0C11AF2 | yes | 0x1BF3 | 600 | 60 | 5/10 | - | 0x4800014D | 0x4800014C | 0x480007B0 | 0x4000047E | events 0x48000ABD |
| 0x40000270 Coast City | pvp_5v5_cst_ons_team1 | 3 | 9 | 5 | 0xA0C122E2 | yes | 0x23E3 | 600 | 60 | 5/10 | - | 0x48000562 | 0x48000563 | 0x48000EAA | 0x40000534 | 0x100007BB [2,7,5] |
| 0x4000039C Crisis Labs: CC | same | 3 | 9 | 5 | 0xA0C122E2 | yes | 0x23E3 | 600 | 60 | 5/10 | - | 0x4800068A | 0x48000563 | 0x48000EAA | 0x40000534 | |
| 0x40000399 Gotham Divided | pvp_5v5_got_rift_team1 | 3 | 9 | 4 | 0xA0C11AD2 | yes | 0x1BD3 | 600 | 60 | 5/10 | - | 0x4800067F | 0x4800067C | 0x48000EA9 | 0x40000554 | events 0x48000E7D |
| 0x40000E6D New GD [test] | pvp_5v5_got_rift2_team1 | 3 | 9 | 4 | 0xA0C11ACA | no | 0x1BCB | 600 | 60 | 5/10 | - | 0x4800145C | 0x4800145E | 0x48000EA9 | 0x40000554 | |
| 0x40000C28 Metropolis Skyway | pvp_5v5_mch_aram_team1 | 3 | 9 | 6 | 0xA0C12AF2 | no | 0x2BF3 | 600 | 60 | 5/10 | - | 0x48001073 | 0x48001079 | 0x4800118B | 0x40000554 | header 1 |
| 0x40000E68 Crime Alley Clash 1v1 | pvp_1v1_gas_lane_team1_a | 3 | C | 2 | 0xA0C112BA | yes | 0x13BB | 600 | 60 | 1/2 | 1 | 0x4800144B | 0x48000E36 | 0x48000EA9 | 0x40000D4C | events 0x4800128B |
| 0x40000E74 Crime Alley Clash 2v2 | same | 3 | C | 2 | 0xA0C112BA | yes | 0x13BB | 600 | 60 | 2/4 | 1 | 0x4800146A | 0x48000E36 | 0x48000EA9 | 0x40000D4C | |
| 0x40000EC0 Apokolips Clash 1v1 | pvp_apo_lane_team1_a | 3 | C | 2 | 0xA0C10AE2 | no | 0x0BE3 | 600 | 60 | 1/2 | 1 | 0x480014D6 | 0x480014D5 | 0x48000EA9 | 0x40000D4C | |
| 0x40000B6C Gotham Heights v AI | pvp_5v5_got_dom_team1 | 1 | D | 3 | 0xA0C11AF2 | yes | 0x1BF3 | 600 | 60 | 5/10 | - | 0x48000F52 | 0x4800014C | 0x480007B0 | 0x4000047E | bots 0x340007E2 |
| 0x40000B6A Coast City v AI | pvp_5v5_cst_ons_team1 | 1 | D | 5 | 0xA0C122E2 | yes | 0x23E3 | 600 | 60 | 5/10 | 2 | 0x48000F54 | 0x48000563 | 0x48000EAA | 0x40000534 | bots |
| 0x40000B6B Gotham Divided v AI | pvp_5v5_got_rift_team1 | 1 | D | 4 | 0xA0C11AD2 | yes | 0x1BD3 | 600 | 60 | 5/10 | 3 | 0x48000F50 | 0x4800067C | 0x48000EA9 | 0x40000554 | prereq 0x40000A81 |
| 0x40000E62 GD Intermediate 5vAI [test] | same | 1 | D | 4 | 0xA0C11AD2 | yes | 0x1BD3 | 600 | 60 | 5/5 | 3 | 0x48001422 | 0x4800067C | 0x48000EA9 | 0x40000554 | `0x10000D08` = 1 |
| 0x40000C82 Crime Alley v AI | pvp_1v1_gas_lane_team1_a | 1 | 9 | 1 | 0xA0C112BA | yes | 0x13BB | 600 | 60 | 1/1 | 1 | 0x4800111B | 0x48000E36 | 0x48000EA9 | 0x40000D4C | next 0x40000B6B, prereq 0x40000A81 |
| 0x40000991 Tutorial Basic | pve_tutorial_basic | 4 | 9 | 7 | 0xA0C112CA | yes | 0x13CB | 300 | 10 | 1/1 | - | 0x48000D3F | 0x48000D3E | 0x48000EA9 | 0x40000B69 | conv. 0x40000CB7, next 0x40000A81 |
| 0x40000A81 Tutorial Intermediate | pve_tutorial_intermediate | 4 | 9 | 8 | 0xA0C112C2 | yes | 0x13C3 | 300 | 10 | 1/1 | - | **0x48000E3B** | 0x48000E37 | 0x48000EA9 | 0x4000047A | conv. 0x40000CBC, next 0x40000CA6 |
| 0x40000CA6 Crime Alley 1vAI Tutorial | pvp_1v1_gas_lane_team1_a | 4 | B | 9 | 0xA0C112BA | yes | 0x13BB | 600 | 75 | 1/1 | 1 | **0x48001150** | 0x48000E36 | 0x48000EA9 | - | **script 0x34000628**, conv. 0x40000CE3, `0x10000B89` 0x40000CBD, `0x10000B87` 0xA0000116, `0x10000C8D` 6 |
| 0x40000D63 Chl. GD Jungle [test] | pve_chl_got_rift_team1 | 2 | 9 | 4 | 0xA0C11ABA | no | 0x1BBB | 600 | 60 | 1/1 | - | 0x4800131A | 0x48001318 | 0x48000EA9 | 0x40000D70 | |
| 0x40000D71 / 0x40000E61 Chl. Defend Turret [test] | pve_chl_gas_lane_team1 | 2 | 9 | 1 | 0xA0C112B2 | no | 0x13B3 | 600 | 60 | 1/1 | 1 | 0x48001325 / 0x4800141E | 0x48001326 | 0x48000EA9 | 0x40000D4C | |
| 0x40000E65 Chl. Multi-bot Push [test] | same | 2 | 9 | 1 | 0xA0C112B2 | no | 0x13B3 | 600 | 60 | 5/1 | 1 | 0x48001436 | 0x48001326 | 0x48000EA9 | 0x40000D4C | |
| 0x40000E5A Chl. Doomsday Device [test] | pve_chl_cst_ons_team1 | 2 | 9 | 5 | 0xA0C122DA | no | 0x23DB | 600 | 60 | 1/1 | - | 0x480013FD | 0x480013FE | 0x48000EAA | 0x40000534 | |
| 0x4000014B PVP Event Test | pve_test_simple | 5 | 9 | 3 | 0xA0C10800 | no | 0x0901 | 600 | 20 | 5/10 | - | 0x4800015C | 0x48000058 | 0x48000163 | 0x40000534 | header 1, `0x10000B21` 0x40000AE7 |
| 0x4000094C All Encounters Surrogate | pve_test_simple | 6 | 9 | C | 0xA0C10800 | no | 0x0901 | 600 | 20 | 5/10 | - | 0x4800015C | 0x48000058 | 0x48000163 | 0x40000534 | header 1 |
| 0x40000168 / 0x40000533 / 0x40000933 / 0x400009B4 Destruction tests | test_*destructibles* | 5 | 9 | B/C | 0xA0C102F2 / 2EA / 2E2 / 2D2 | no | 0x03F3 / 03EB / 03E3 / 03D3 | 600 | 60 | 5/10 | - | 0x480001AA / 0x48000827 / 0x48000D02 / 0x48000D6E | 0x48000058 | 0x48000163 | - | header 1 |

Notes (C unless marked):
- The spawn landblock of `0x1000021D` is always the centre of the map pack's 3 x 3 terrain block and the only
  landblock with gameplay content (navmesh, waypoints, start points).
- No encounter template carries a numeric match length. `0x1000021C` (600 / 300) and `0x100004A1` (60 / 10 / 75 / 20)
  are the only timers (meanings G: surrender / AFK limit and champion select). The UI record `0x100001D2` holds a
  duration **text** (`0x10000C6D`, string token only).
- `0x10000B87` (only on `0x40000CA6`) = `0xA0000116`, a category-8 pack (champion-type pack: 3 entities, 13 scripts);
  `0x10000B89` = `0x40000CBD` (in pack `0xA0000316`, category 8): G, the tutorial opponent's champion and its pack
  (the cinematics call it `GasBot` / `Corrupted_Gasbat`, world state `0x2E0011C1` = a Gaslight Batman rig, pack
  `0xA00002F3`).
- Only `0x40000CA6` names an encounter script (`0x10000B5A`); no other template has one (C, all 28 read).

### 1.2 The UI / objective record (`0x100001D2`)
| Record | `0x10000C73` | `0x10000463` per team | `0x10000464` | `0x10000C70 / C71` | Objectives `0x1000019F` |
|---|---|---|---|---|---|
| 0x4800014D GH | 5 | 500 / 500 | 1250 | - / 5 | none |
| 0x48000F52 GH v AI | 5 | 500 / 500 | 1250 | 5 / 5 | none |
| 0x48000562 CC, 0x4800068A Crisis Labs, 0x48000F54 CC v AI | 5 | - | 1000 | - or 5 / 5 | none |
| 0x4800067F GD, 0x48000F50 GD v AI, 0x48001422 GD 5vAI | 5 | - | 750 | - or 5 / 5 | none |
| 0x4800144B Clash 1v1 | 1 | 200 / 200 | 1000 | - / 1 | none |
| 0x4800146A Clash 2v2 | 2 | 300 / 300 | 750 | - / 2 | none |
| 0x4800111B Crime Alley v AI | 1 | - | 1000 | 1 / 1 | none |
| 0x48000E3B Tutorial 2 | 1 | - | 1500 | - | 29 (section 5.4) |
| 0x48001150 CA 1vAI tutorial | 1 | - | 1000 | 1 / 1 | 15 (section 5.3) |
| 0x48000D3F Tutorial 1 | | | | | 29 (tutorial-data-inventory.md 6.1) |

`0x10000463` (team 1, team 2 values) exists only on Gotham Heights and the Clashes: G, the score / ticket total of the
mode's scoreboard (GH's 500 per team matches the capture-point totals `CapturePoint_Total_TeamN` of match-variable
record `0x3A000029`). `0x10000464` meaning unknown (O). `0x10000429` 3 on GH, 1 elsewhere (O).

---------------------------------------------------------------------------------------------------------------

## 2. The map packs

### 2.1 Pack lists, landblocks, statics (installed maps, C)

| Map pack | Used by | Pack list (category) | Terrain landblocks | Spawn LB | Statics per landblock (parsed / header) | Statics by type |
|---|---|---|---|---|---|---|
| 0xA0C112CA (1.3 MB, cat. 1) | Tutorial 1 | 0xA000024C (13 zone), 0xA0000256 (15 layout), 0xA0000257 (14 variants), 0xA00002D6, 0xA00002D7 (7) | 0x12CA-0x14CC | 0x13CB | 13CB 858/858, 14CB 136/137, 13CA 3, 12CB 1 | 7: 781, 3: 91, 2: 80, 21: 25, 10: 20, 16: 1 |
| 0xA0C112BA (80 MB, 17) | Crime Alley v AI, 1vAI tutorial, Clash 1v1 / 2v2 | 0xA00002E5 (13), 0xA00002E6 (15), 0xA00002E7 (14) | 0x12BA-0x14BC | 0x13BB | 13BB 362/362, 12BB 17, 14BB 9 | 7: 317, 21: 32, 3: 18, 10: 11, 16: 10 |
| 0xA0C112C2 (80 MB, 17) | Tutorial 2 | 0xA00002E5, 0xA00002E6, 0xA00002E7 (same as Crime Alley) | 0x12C2-0x14C4 | 0x13C3 | 13C3 214, 12C3 26 (header layout differs: `did | 2 | a | 1 | 1 | 2 | refs`) | 7: 165, 3: 24, 2: 21, 21: 17, 10: 12, 16: 1 |
| 0xA0C11AF2 (80 MB, 17) | Gotham Heights (+ v AI) | 0xA000009A (13), 0xA000016B (15), 0xA0000179 (14) | 0x1AF2-0x1CF4 | 0x1BF3 | 1BF3 629/629, 1AF3 26, 1CF3 8, 1BF2 7 | 7: 422, 21: 114, 3: 81, 10: 41, 16: 12 |
| 0xA0C11AD2 (91 MB, 17) | Gotham Divided (+ v AI, 5vAI) | 0xA0000168 (15), 0xA00000FC (13), 0xA000016E (14) | 0x1AD2-0x1CD4 | 0x1BD3 | 1BD3 567/568, 1CD3 13, 1BD4 5, 1AD3 4, 1CD2 1 | 7: 383, 21: 123, 3: 57, 10: 15, 16: 12 |
| 0xA0C122E2 (147 MB, 17) | Coast City, Crisis Labs, CC v AI | 0xA00000D2 (13), 0xA0000161 (14), 0xA0000162 (15) | 0x22E2-0x24E4 | 0x23E3 | 23E3 792/792, 24E3 3, 22E3 2, 23E4 1 | 7: 511, 21: 150, 3: 76, 2: 28, 10: 21, 16: 12 |

Every category-17 map pack holds: textures `0x13` (66-73), 9 terrain `0x80`, 9 landblock infos `0x81`, 9 statics
`0x82`, 3 navmeshes `0x90` and the nav index `0x85` (C). Not installed (map pack missing): 0xA0C11ACA (New GD),
0xA0C12AF2 (Metropolis Skyway), 0xA0C10AE2 (Apokolips), 0xA0C11ABA (GD jungle challenge), 0xA0C112B2 (Crime Alley
challenges), 0xA0C122DA (Doomsday Device challenge), 0xA0C10800 (tests), 0xA0C102F2 / 2EA / 2E2 / 2D2 (destruction
tests). For these, only the template data of 1.1 exists (C).

### 2.2 Statics (`0x82`) format (C)
`did | 0 | a | 0 | count | entries`; entry = `u32 flags | u32 type | u32 index | u32 IID (0x01llllc0) | [u32 world
state if flags & 0x08] | f32 x, y, z | f32 quaternion w, x, y, z | [u32 0 | u32 n | n properties if flags & 0x80]`.
Property values follow the property kinds (`ics.records`); kind `0x03` (`0x576`, on lights) is a struct the reader
cannot size, so the scan resyncs on the next entry. Types: **2** single-mesh, **3** emitter / marker (world state
often in no installed pack), **7** scenery / objects, **10** point light (`0x2E000011`), **16 start point (no world
state)**, **21** waypoint (`0x2E000000`; `0x100003E7 = 0x10000188` = marker). Two "type 40" hits in GH 0x1AF3 are
scan artefacts.

### 2.3 Navmeshes (`0x90`, parsed with the fixed reader of 2.4)
Agent classes: `0x10000003` radius 0.525 / height 2.1 (champions), `0x10000002` 1.1 / 2.1, `0x10000001` 2.1 / 4.0.
Walkable = rasterised at 0.5 m. "Comp." = 4-connected components (the extra ones are single 0.25 m^2 cells).

| Map | Agent | Endian | Cells | Floors | Triangles (`ics.navmesh` today) | Walkable m^2 | Comp. | Bounds x / y / z | Type-21 points on mesh |
|---|---|---|---|---|---|---|---|---|---|
| Tutorial 1 | 0x10000003 | LE | 17 | 18 | 175 (175) | 944 | 1 | 16.2-155.6 / 11.4-64.2 / 200.0-200.2 | 25/25 |
| | 0x10000002 | LE | 17 | 20 | 188 (188) | 738 | 1 | 16.8-155.0 / 12.0-63.6 | 21/25 |
| | 0x10000001 | LE | 4 | 4 | 15 (15) | 51 | 1 | 17.8-31.0 / 57.8-62.6 | 1/25 |
| Crime Alley | 0x10000003 | LE | 18 | 20 | 176 (176) | 2762 | 1 | 0.8-159.0 / 63.6-100.6 / 200.1-200.3 | 32/32 |
| | 0x10000002 | LE | 16 | 18 | 158 (158) | 2481 | 1 | 1.4-158.4 / 64.2-100.0 | 32/32 |
| | 0x10000001 | LE | 16 | 18 | 149 (149) | 2013 | 1 | 2.4-157.4 / 65.2-99.0 | 32/32 |
| Tutorial 2 | 0x10000003 | LE | 8 | 8 | 72 (72) | 1220 | 1 | 0.8-79.2 / 63.6-93.6 | 17/17 |
| | 0x10000002 | LE | 8 | 8 | 66 (66) | 1097 | 1 | 1.4-78.6 / 64.2-93.0 | 17/17 |
| | 0x10000001 | - | 0 | 0 | 0 (empty blob) | - | - | - | - |
| Gotham Heights | 0x10000003 | LE | 52 | 55 | **1579 (558)** | 9386 | 1 | 0.8-159.2 / 8.0-143.2 / 249.9-250.5 | 114/114 |
| | 0x10000002 | LE | 52 | 60 | 1585 (555) | 8181 | 1 | 1.4-158.6 / 8.6-142.6 | 114/114 |
| | 0x10000001 | LE | 52 | 60 | 1509 (531) | 6086 | 9 | 2.4-157.6 / 9.6-141.6 | 109/114 |
| Gotham Divided | 0x10000003 | **BE** | 58 | 74 | **1574 (0)** | 14766 | 1 | 1.0-158.4 / 1.0-158.2 / 249.9-250.2 | 123/123 |
| | 0x10000002 | BE | 58 | 76 | 1533 (0) | 13198 | 1 | 1.6-157.8 / 1.6-157.6 | 123/123 |
| | 0x10000001 | BE | 58 | 82 | 1507 (0) | 10431 | 5 | 2.6-156.8 / 2.6-156.6 | 123/123 |
| Coast City | 0x10000003 | LE | 54 | 60 | **1690 (547)** | 10504 | 1 | 1.0-159.0 / 2.8-148.0 / 250.0-250.2 | 150/150 |
| | 0x10000002 | LE | 52 | 60 | 1689 (622) | 9207 | 1 | 1.6-158.4 / 3.4-147.4 | 150/150 |
| | 0x10000001 | - | 0 | 0 | 0 (empty blob) | - | - | - | - |

The nav index `0x85` (no DID, after the last statics record): `4 | 1 | n statics | hash | 3 x (radius, height,
class)` (C). Structures (cores, pedestals) are **not** cut out of the mesh (the core pedestal points are walkable):
the server must block them dynamically (`NavGrid.block`) (C for the mesh, P for the need).

### 2.4 Fix for `ics/navmesh.py` (not applied: this survey does not edit source)
1. Cell list: `cells, at = _arr(data, blob + 0x98)` instead of `u32 at +0x2C` with the list at `+0xB0` (the `+0x98`
   pair is `count | 0x14`, so the list still starts at `+0xB0`). Tutorial 1 has 17 cells (the old comment "17 of 19").
2. Endianness: `be = u32(blob + 0x0C) == 1` (LE blobs have 0 there and 3 at `+0x10`; GD has `00000001 03000000`).
   Read every u32 / u16 / f32 of the blob with `">"` when `be`; vertex bytes (u8 x, u8 y) are unchanged; the
   half-edge's start vertex is `HH[0]` in BE (`HH[1]` in LE), i.e. the high half of the u32 in both cases.
3. Optional: the 1.1 m mesh (`0x10000002`) for structures / big units; the 2.1 m mesh is empty on Tutorial 2 and
   Coast City.

---------------------------------------------------------------------------------------------------------------

## 3. Per map

Classes (entity `0x40` / template `0x49`) were read from the layout and variants packs: `ws` = `0x510` world state,
team `0x1000009C`, side `0x100007A2` (3 team 1, 5 team 2, 1 PvE enemy), stat block `0x10000165`, scripts `0x8E`,
sight `0x10000133`, rig names from the world state's `.entity`.

Common structure world states: `0x2E000AA0` turret (`env_pvp_turret_powercore_a`), `0x2E000AC4` core turret body
(`env_pvp_powercore_turret_a_body`), `0x2E000AC5` / `0x2E0013EE` power core (`env_pvp_powercore_a`), `0x2E000E04`
dampener (`env_pvp_dampener_a`), `0x2E001037` Foundry (`env_pvp_artifact_foundry`, the base turret, classes
`0x40000170` team 1 / `0x4000016F` team 2, in every PvP layout pack), `0x2E000A3B` core pedestal, `0x2E000A35` Base
Team 01, `0x2E000D12` control point / power relay (`env_pvp_power_relay_a`), `0x2E000B22` GH capture point
(`env_pvp_capture_point_c`), `0x2E000E38` drop pod (regen / haste pads), `0x2E001314` superpad, `0x2E000FBB` health
pack, `0x2E000FE5` surveillance tower, `0x2E000FC7` phase pod, `0x2E0008FD` Doomsday Device, `0x2E0010B1` Doomsday
guardian, `0x2E000D67` / `0x2E000E6C` mobile ward. (C)

### 3.1 Tutorial 1 (0x40000991, LB 0x13CB)
Implemented; see `tutorial-data-inventory.md` and `movement-collision-fog-map.md`. New here: start point (type 16) at
(18.5, 59.9, 200.0) (C); 25 type-21 points (C, listed in tutorial-data-inventory 3.1).

### 3.2 Tutorial 2 (0x40000A81, LB 0x13C3; shares Crime Alley's zone / layout / variants packs)
- Map: the west half of a Crime Alley-like lane (navmesh x 0.8-79.2, y 63.6-93.6). Start point (5.0, 77.5, 200.3) (C).
- Statics (C): core pedestal `0x2E000A3B` (17.5, 77.5) team 1 side 3; `0x2E00119F` (40.0, 77.5) team -1 (structure
  socket, P); team lane-mouth statics `0x2E000AF9` / `0x2E000AF7` (21.8, 77.5) team 1, `0x2E000AF8` (71.8, 77.5) and
  `0x2E000AF6` (54.2, 77.5) team 2; structure markers `0x2E0011AD` (25.5, 77.5) and `0x2E0011AC` (75.0, 77.5);
  `0x2E00101D` (80.0, 97.7) `50F = 5`.
- Waypoints (C): lane points 21.8 (marker), 23.5, 33.5, 39, 47, 52.5, 54.2 (marker, yaw 90), 60, 70.5, 71.8 (marker)
  on y = 77.5, both directions; (49.5, 88.5) north.
- Cinematics (pack `0xA00002E6`, positions in LB 0x13C3, C):

| Cinematic | Dur. | Script | Actors (world state; start -> end) |
|---|---|---|---|
| 0x35000029 | 35.0 | 0x340005DF | 01MeleeA/B `0x2E001167`, 01RangedA/B `0x2E001168` (71.8 -> 21-24, 77.5), **01Spawner** `0x2E000D03` (71.8, 77.5) side 1, **PowerCoreTarget** `0x2E000A3F` (17.6, 77.4) `0x2A1 = 0`, **BaseGate** `0x2E000CD7` (0.0, 68.3) side 3 |
| 0x3500002A | 52.0 | 0x340005F4 | 01TurretFriendly `0x2E000AA0` side 3; **01TurretFriendlyHead** `0x2E000AA8` (25.1, 77.5) side 3; 01TurretEnemy / **01TurretEnemyHead** (75.0, 77.5) side 1 / 01TurretEnemyPlate `0x2E000A9F`; 02MeleeA/B `0x2E000808`, 02RangedA/B `0x2E000840` (31-37 -> 70-73) side 3; GreenLantern `0x2E000156` (55.3, 64.4 -> 68.7, 77.4) |
| 0x3500002B | 38.5 | 0x340005E5 | Turret `0x2E000AA0` side 1; GaslightBatman (67.9 -> 37.8, 77); **Foundry** `0x2E001037` (1.3, 77.1, 201.8) side 3; Melee01/02, Ranged01/02 side 3 (41-59, 61-78); Crater1 (59.6 -> 52.6), Crater3 (69.8, 77.9) `0x2E0004BE`; TurretBasePlate `0x2E000A9F` |
| 0x3500002C | 21.2 | 0x34000605 | **01BlueSpawner** `0x2E000D03` side 3; 01/02MeleeDrone, 01/02RangedDrone, 01SiegeDrone `0x2E000E21` from **(22.3, 77.2)** to 44-50; 01/02EnemyMelee, 01/02EnemyRanged, 01EnemySiege from 53-72 to 48-54 side 1; GaslightBatman (25.3 -> 28.3, 55.4) |
| 0x3500002D / 2E / 31 / 32 | 0 / 21 / 12 / 12 | 0x340006A2 / 6A8 / 6A3 / 6A9 | no actors (camera only) |
| 0x35000030 | 14.0 | 0x340006A4 | ImpactPoint `0x2E001253`, Wall `0x2E001254` (`env_gas_tut_sidewalk_wall`), no keys |

### 3.3 Crime Alley (0x40000C82 v AI, 0x40000CA6 1vAI tutorial, 0x40000E68 / E74 Clash; LB 0x13BB)
- Start points (type 16, C pos / P role): team 1 centre **(5.0, 77.5, 200.3)**, slots (6.0, 79.5), (6.0, 75.5),
  (7.0, 73.5), (7.0, 81.5); team 2 centre **(155.0, 77.5)**, slots (154.0, 79.5), (153.0, 81.5), (154.0, 75.5),
  (153.0, 73.5).
- Core pedestals (C): `0x2E000A3B` (17.5, 77.5) yaw 90 team 1 side 3; (142.5, 77.5) yaw -90 team 2 side 5 rulesets
  `[9, C]`; (142.5, 77.5) yaw -90 team 2 **side 1** ruleset `[B]` (`0x10000CF0` present).
- Structure markers (type 3, C pos): `0x2E0011A7` (17.5, 77.2) and `0x2E0011A6` (142.5, 77.8) = cores;
  `0x2E0011A9` (40.0) / `0x2E0011A8` (120.0); `0x2E0011AD` (65.0) / `0x2E0011AC` (95.0) = turrets (cinematic
  `0x35000038` puts BlueTurretBody / Head at (65.0, 77.5) side 3 and RedTurretBody / Head at (95.0, 77.5) side 1).
- Lane mouths (C pos): marker `0x10000188` + `0x2E000AF9` team 1 at (21.8, 77.5); marker + `0x2E000AF8` team 2 at
  (138.2, 77.5).
- Waypoints (C): lane team 1 -> 2 (idx 0x134-0x13D): 23.2, 35.5, 50, 60, 76, 93, 106, 117.5, 132.5, 138.2 (y 77.5);
  team 2 -> 1 (0x13E-0x147): 136.8, 124.5, 110, 100, 84, 67, 54, 42.5, 27.5, 21.8. Jungle loop (0x28C-0x297):
  (80, 95.5), (87, 94.8), (96, 93.8), (108.5, 88.8) and back, (73, 94.8), (64, 93.8), (51.5, 88.8). Jungle markers
  type 3 `0x2E000944` / `0x2E000945` / `0x2E001120` / `0x2E001117` at (80.0, 97.1-97.2) (P: the camp).
- Other statics: `0x2E001253` ImpactPoint (82.1, 77.3) `0x10000B5B = 0x100`; `0x2E00101D` (-7.2, 64.0) in 0x12BB
  team 2; ambient emitters `0x2E00110F` (80, 77.5), (110.5, 78.5), `0x2E001110` (80, 77.5), `0x2E001121` (80, 119),
  `0x2E001118` (48.8, 93), `0x2E00111B` (61.5, 77.5).
- Cinematics (pack `0xA00002E6`, C):

| Cinematic | Dur. | Script | Actors |
|---|---|---|---|
| 0x3500002F | 17.0 | 0x340006A5 | Corrupted_Gasbat `0x2E0011C1` (98.4 -> 107.0, 77.2), Player_Gasbat `0x2E0001B2` (72.6 -> 75.5), Bat_Scream_Bat `0x2E0002B0` (99.3 -> 63.3, z 201.8) |
| 0x35000038 | 72.0 | 0x34000733 | PowerCore `0x2E000AC5` (142.5, 77.8) team 2 (sinks to z 100.1); GasBat (137.7 -> 17.2, 86.8); WonderWoman, Superman, GreenLantern at (11-15, 85-90); Blue/RedTurretBody `0x2E000AA0` + Head `0x2E000AA8` at 65 / 95; CorruptedGasBot (77.5, 64.8 -> 83.1, 77.5); HarleyQuinn, Doomsday (76, 65 -> 9-20, 85-87) |
| 0x35000039 | 49.5 | 0x34000732 | GasBot `0x2E0011C1` (148.3, 77.2) |
| 0x3500003A | - | - | **team 2 end**: PowerCore (142.5, 77.8) side 5 team 2; Player01 `0x2E00028B` (137.7, 77.5), Player02 `0x2E000E54` (140.5, 83.5) |
| 0x3500003B | - | - | **team 1 end**: PowerCore (17.5, 77.2) side 3 team 1; Player01 (22.5, 77.5), Player02 (15.5, 83.5) |
| 0x3500003C | 13.0 | 0x340006F2 | match intro line-up: `Chr_Center - ThePlayer` `0x2E00028B` (52.4, 77.8) |

- Classes (layout `0xA00002E6`, C; families by stat block, P): tutorial / vs-AI family with explicit health
  (`0x10000426`): turrets `0x40000C86` (team 2 side 1, 3000, scripts `0x34000838`, `0x340007EC`, `0x34000600`),
  `0x40000C8B` (team 2 side 1, 2500), `0x40000C8D` (team 2 side 1, 3000), `0x40000C8C` (team 1, 2500),
  `0x40000C8E` (team 1, 3500), `0x40000C8F` (team 1, core turret ws `0x2E000AC4`, 3500); dampeners `0x40000C87`
  (team 2 side 1) / `0x40000C88` (team 1), 3000; cores `0x40000C89` (team 2 side 1, 4000) / `0x40000C8A` (team 1,
  4000). Clash family (formula stats `0x4800112B`-`2E`): turrets `0x40000C92` (team 1) / `0x40000C93` (team 2)
  (`0x4800112C`), `0x40000C97` (team 2, `0x4800112B`), `0x40000C94` (no data read); dampeners `0x40000C91` /
  `0x40000C95`; cores `0x40000C96` / `0x40000C98` (`0x2E0013EE`); `0x40000C90` (team 1 core, `0x2E000AC5`, the
  tutorial's). `0x40000E86` turret, no team. Base `0x4000041F` / `0x40000C7F`. Minions / jungle in `0xA00002E7`
  (Soldier / Trooper / Cannon sets `0x40000BC1`-`BC9`, `0x40000BF8`-`BFA`, `0x40000C9A`-`C9E`, `0x40000E79`-`E7F`;
  Tripod `0x40000A61` / `A64` / `CA0` / `CA1` / `E7E` (`0x3400007D` on kill); Raider `0x40000A71` / `C6C` / `CA2`
  (`0x34000670`); Regen Destroyer `0x40000CDA` / `E83`; Surveillance Drone `0x40000892`; Watcher Drone `0x40000EB5`
  (`0x34000600`).

### 3.4 Gotham Heights (0x4000013E, 0x40000B6C; LB 0x1BF3; domination)
- Start points (C pos): team 1 centre **(6.0, 47.0, 250.1)**, slots (5.7, 44.8), (5.4, 42.6), (4.4, 48.6),
  (2.8, 50.1); team 2 centre **(154.0, 47.0)**, slots (154.3, 44.8), (154.6, 42.6), (155.6, 48.6), (157.2, 50.1).
  Team sides from cinematics `0x3500000D` (Character_0 `0x2E000B47` `env_pvp_core_a`, team 1 side 3, (18.4, 50.1,
  252.5)) and `0x3500000E` (team 2 side 5, (142.7, 50.3)) (C).
- Capture points (P): markers `0x100003E7 = 0x10000188` (2-4 coincident per site): **SW (48.5, 27.5), SE
  (111.5, 27.5), W (27.0, 90.0), E (133.0, 90.2), N (80.0, 127.8)**. Next to each, two team-variant type-3 statics
  (pairs team 1 / team 2 world states, C): W (12.5, 91.5) `0x41F/0x420` and (14.5, 97.5) `0x421/0x422`; SW
  (36.5, 16.5) `0x423/0x424`, (42.0, 12.5) `0x425/0x426`; SE (118.0, 12.5) `0x427/0x428`, (123.5, 16.5)
  `0x429/0x42A`; E (147.5, 91.5) `0x42B/0x42C`, (145.5, 97.5) `0x42D/0x42E`; N (76.5, 141.5) `0x42F/0x430`,
  (83.5, 141.5) `0x431/0x432` (world states `0x2E00041F`-`0x2E000432`, parent `0x2E000006`).
- Centre ring (C pos, G role): ten `0x2E000006` statics with `0x1000005D` id and team: (86.0, 75.0) ids 0x8B (t1) /
  0x82 (t2), (74.0, 75.0) 0x85 / 0x86, (80.0, 80.0) 0x83 / 0x84, (83.8, 68.0) 0x89 / 0x8A, (76.2, 68.0) 0x87 / 0x88:
  five sockets x two teams around (80, 74), one per capture point (G: the generator's charge lights).
- Waypoints (C): ~68 points of two mirrored rings through the five points (idx 0x4-0x208, e.g. (72.5, 18) - (60, 21) -
  (51.5, 25.5) - (48.5, 27.5) - (38.5, 35.5) - (31, 47) - (26, 60.5) - (24.5, 75.5) - (26.5, 88) - (27, 90) - (32.5,
  103) - (40, 112) - (50, 119.5) - (65.5, 126) - (78.5, 127.8) ...); 10 points near the capture points (0x1156-0x115F:
  (71, 139.5), (89, 139.5), (16.5, 80.5), (24.5, 104.5), (33.5, 23.5), (50, 12.5), (126.5, 23.5), (110, 12.5),
  (135.5, 104.5), (143.5, 80.5)); 30 yawed points in the centre (0x1F13-0x1F41, e.g. (75.2, 66.5), (84.8, 66.5),
  (80, 81.5), (80, 92)).
- Cinematics: 0x3500000D / 0x3500000E (above, no duration / script: static camera poses), 0x3500000F
  (Character_0 `0x2E000D32`, no keys), **0x35000023 match intro** (13.0 s, `0x340006F2`): `Chr_Center - ThePlayer`
  `0x2E00028B` (80.0, 15.1), `Chr_MidLeft - Player02` (76.5, 17.1), `Chr_Left - Player01` (73.1, 19.1),
  `Chr_Right - Player03` (86.9, 21.0), `Chr_MidRight - Player04` (83.5, 17.1) (C).
- Classes (`0xA000016B` / `0xA0000179`, C): capture point `0x4000013B` (ws `0x2E000B22`, stat `0x48000148`, sight
  4.25), relay `0x40000511` (`0x2E000D12`, `0x480006CE`), Foundry `0x40000170` / `0x4000016F`, Base `0x4000041F`,
  `0x400005C9` (`0x2E000D22`, scripts `0x34000167` collision / destruction projectile, `0x34000347` phasing), props
  `0x40000132`, `0x400003AB`, `0x4000039D`, `0x40000269` / `26B` / `26D` / `287` / `289`, `0x400003F2` (`0x2E000B47`,
  the core actor of the cinematics), `0x40000621`. Minions (`0xA0000179`): Trooper `0x4000012D`, Soldier
  `0x4000012E`, Destroyer `0x40000EAA` (scripts `0x3400027E`, `0x340004A0`, `0x340004A1`).

### 3.5 Gotham Divided (0x40000399, 0x40000B6B, 0x40000E62; LB 0x1BD3; 3 lanes)
Symmetric under `(x, y) -> (y, x)` (team 1 top-left, team 2 bottom-right) (C).
- Start points (C pos): team 1 centre **(7.5, 152.5, 250.2)**, slots (9.0, 151.0), (10.5, 152.5), (12.0, 154.0),
  (7.5, 149.5), (6.0, 148.0); team 2 centre **(152.5, 7.5)**, slots (151.0, 9.0), (152.5, 10.5), (154.0, 12.0),
  (149.5, 7.5), (148.0, 6.0).
- Cores (C): pedestals `0x2E000A3B` (17.5, 142.5) yaw 45 team 1 and (142.5, 17.5) yaw -135 team 2; cinematics
  0x35000014 / 0x35000015 put the PowerCore there.
- Lane mouths (C pos, P role: wave spawn): team 1 `0x2E000AF5` (17.5, 134.0) south, `0x2E000AF9` (23.5, 136.5) mid,
  `0x2E000AF7` (26.0, 142.5) north; team 2 `0x2E000AF4` (134.0, 17.5), `0x2E000AF8` (136.5, 23.5), `0x2E000AF6`
  (142.5, 26.0). Markers `0x10000188`: (20.7, 145.7), (14.0, 139.1) team 1; (145.7, 21.0), (139.0, 15.0) team 2.
- Lanes (C points; direction team 1 -> team 2):
  - north: (26.3, 134.4) (37, 146) (49, 148.2) (61, 148.2) (72.5, 148.2) (86, 148.2) (99.8, 148.2) (106.5, 141.5)
    (115, 133) (124, 124) (133, 115) (141.5, 106.5) (148.2, 99.8) (148.2, 86) (148.2, 72.5) (148.2, 61) (148.2, 49)
    (147, 40) (144.6, 29.3) / (134, 26); length 225.7 m, midpoint (123.9, 124.1);
  - mid: (31, 127.5) (42.5, 117.5) (50, 109.8) (57, 102.8) (63.5, 95.5) (72, 88) (80, 80) (88, 72) (95.5, 63.5)
    (102.8, 57) (109.8, 50) (117.5, 42.5) (123.8, 33.8) (127.5, 31); 136.6 m, midpoint (80, 80);
  - south: (14.9, 130.8) (13, 120) (11.8, 111) (11.8, 99) (11.8, 87.5) (11.8, 74) (11.8, 60.2) (18.5, 53.5) (27, 45)
    (36, 36) (45, 27) (53.5, 18.5) (60.2, 11.8) (74, 11.8) (87.5, 11.8) (99, 11.8) (111, 11.8) (120 / 123, 13)
    (130.7, 15.4); 210.1 m, midpoint (36, 36).
  - Core rings (0x692-0x6A5): 10 yawed points per core at r = 7-9 m, e.g. team 1 (29.4, 144.1), (24.2, 144.6),
    (24.5, 142.8), (24.3, 141.0), (23.4, 138.7), (22.7, 137.8), (21.8, 136.9), (19.0, 135.7), (17.2, 135.5),
    (15.4, 135.8) (P: attack slots around the core).
- Neutral sites (C pos, G role): `0x2E0003F0` (`0x7EB = 6`, `0x2A1`) + `0x2E000FBE` (scale 0.6) + `0x2E00133D` /
  `0x2E00133E` at **(55, 55)** and **(105, 105)**, the two jungle centres off the mid lane.
- Cinematics (`0xA0000168`, C): 0x35000014 (11.5 s, `0x3400076B`): PowerCore (17.5, 142.5) team 1, Player01
  (19.6, 137.1), Player02 (15.2, 136.7), Player03 (11.8, 139.7), Player04 (23.9, 144.3), Player05 (20.6, 148.0);
  0x35000015 the same around (142.5, 17.5); **0x35000024 intro** (13.0 s, `0x340006F2`): line-up at (34.0, 34.0),
  (33.0, 37.9), (31.9, 41.7), (41.7, 31.9), (37.9, 33.0).
- Classes (`0xA0000168`, C): turrets team 1 `0x400003BA` (core turret, ws `0x2E000AC4`, stat `0x480006B6`),
  `0x400003BB` (`0x480006BA`), `0x400003BC` (`0x480006B8`), `0x400003BF` (`0x480006B9`); team 2 `0x400003C1`
  (core turret, `0x480006B6`), `0x400003C0` (`BA`), `0x400003BD` (`B8`), `0x400003BE` (`B9`); all scripts
  `0x34000838`, sight 9. Stat families: `0x10000B84` = 45 (`BA`), 55 (`B9`), 60 (`B8`, `B6`) (P: tier order outer <
  inner < base < core). Dampeners `0x40000C61` / `0x40000C60` (`0x2E000E04`, `0x480010BA`, sight 7.5); cores
  `0x40000A7E` / `0x40000A7B` (`0x48000E34`, sight 15); control point `0x400003AF` (`0x2E000D12`); base `0x40000C7F`;
  pads (drop pods `0x2E000E38`): `0x400008CF`, `8D0`, `8D6`, `8D7`, `0x400009B6`, `0x40000A6C`; superpads
  `0x40000CB4`, `CB5`, `CB8`-`CBB`, `CBE` (`0x2E001314`); surveillance tower `0x400007FD`; pulse emitter `0x40000951`;
  phase pod `0x40000A79`; surveillance drone `0x40000A83`; health / haste packs `0x40000A86` / `A87`; `0x40000AAC`
  (team 1, meteor rig). Variants `0xA000016E`: minions `0x4000010A`-`10D`, `0x40000941` / `942`, `0x40000E5F`;
  jungle `0x40000935`-`0x40000940` (on-kill scripts `0x3400007D`, `0x3400051A`, `0x3400051B`).

### 3.6 Coast City (0x40000270, 0x4000039C, 0x40000B6A; LB 0x23E3; 2 lanes, onslaught)
Symmetric under `x -> 160 - x` (team 1 west) (C).
- Start points (C pos): team 1 centre **(4.7, 59.2, 250.2)**, slots (2.7, 62.8), (3.7, 61.0), (4.7, 57.1),
  (4.8, 55.0); team 2 centre **(155.4, 59.1)**, slots (155.3, 55.0), (155.3, 57.1), (156.4, 60.9), (157.4, 62.7).
- Cores (C): pedestals `0x2E000A3B` (17.0, 62.5) yaw 105 team 1, (143.0, 62.5) yaw 255 team 2; cinematics
  0x35000013 / 0x35000012 (PowerCore `0x2E0013EE`).
- Lane mouths (C pos, P role): team 1 `0x2E000AF5` (22.5, 60.5) south lane, `0x2E000AF7` (20.8, 67.0) north lane;
  team 2 `0x2E000AF4` (137.5, 60.5), `0x2E000AF6` (139.2, 67.0); type-3 `0x2E000941` / `0x2E000940` at the same
  four points.
- Lanes (C points; team 1 -> 2): north (21.5, 68) (24.5, 80) (30.5, 95.5) (36.5, 110.5) (41, 120.8) (46.5, 123.5)
  (64, 123.5) (80, 123.5) (96, 123.5) (113.5, 123.5) (119, 120.8) (123.5, 110.5) (129.5, 95.5) (135.5, 80)
  (138.5, 68): 192 m; south (23.8, 60) (33.5, 51.5) (60.5, 31) (77.5, 19) (82.5, 19) (99.5, 31) (126.5, 51.5)
  (136.2, 60): 140.2 m. Six base-ring points per core (0x479-0x484: (21.5, 60), (15.8, 67.5), (12.5, 64.5),
  (19.8, 66.5), (14.2, 58.2), (18.5, 57) and mirror).
- Camps (P): type-3 markers `0x2E000942` / `0x2E000944` / `0x2E000945` at **(80, 145), (44.5, 90.5),
  (115.5, 90.5), (80, 9), (80, 57)**, each with a type-21 patrol loop: (56.5-103.5, 135.5-145) and (72.5-88.5,
  127.5-144.5); (38-58, 93.5-104) and (102-122, 93.5-104); (44-116, 4.2-28) and (65-95, 4.5-21); (65-95, 50.5-59);
  (47-113, 75.5-102.5).
- Centre (C pos, P role): type-3 `0x2E001178` + `0x2E001181` at **(80.0, 82.0, 250.3)**: the Doomsday Device site.
- Statics with props (C): barricade rows `0x2E000A26` / `A27` / `A28` (`0x2A4 = 1`) at y = 117 (x 65-95) and along
  (136-159, 66-127); sound emitters `0x2E000A5C`-`A5F`, `0x2E000876` (props `0x5E5`).
- Cinematics (`0xA0000162`, C): 0x35000012 (11.5 s, `0x3400076C`): PowerCore `0x2E0013EE` (143.0, 62.5) team 2 side
  5, Player01 (137.5, 60.2), Player02 (146.9, 57.4), Player03 (no key), Player04 (136.0, 63.3), Player05
  (139.2, 67.2); 0x35000013 team 1 at (17.0, 62.5) with players (20.2, 57.4), (13.2, 57.8), (23.6, 63.1),
  (21.0, 67.4); **0x35000020 intro** (13.0 s, `0x340006F2`): (80.0, 19.0), (76.5, 21.0), (73.1, 23.0),
  (86.9, 23.0), (83.5, 21.0).
- Classes (`0xA0000162`, C): turrets team 1 `0x400003FA` (`0x480008A1`, B84 55), `0x400003FD` (`0x48000703`, 35),
  `0x400003FE` (`0x48000702`, 45), `0x40000400` (core turret `0x2E000AC4`, `0x48000701`, 100); team 2 `0x400003F9`
  (`8A1`), `0x400003FC` (`703`), `0x400003FB` (`702`), `0x400003FF` (`701`, core turret); cores `0x40000C24` /
  `0x40000C23` (`0x4800105A`); Doomsday Device `0x400001F0` (`0x2E0008FD`, `0x4800023B`), firing trigger
  `0x4000054F` (`0x2E00104E`); relays `0x4000089D`, `0x40000D25` (`0x2E000D12`); superpad `0x40000EED`; base
  `0x40000C7F`, `0x4000059E` (team 1, `0x2E000CD9`). Variants `0xA0000161`: minions `0x400002D4` / `2D5`,
  `0x40000441`-`443`, `0x40000C45`-`C48`, `0x40000D23`, `0x40000D5C`; jungle `0x40000893`-`0x4000089A`, `0x400007C1`,
  `0x40000D60`, `0x40000D62`; Doomsday guardian `0x40000430` (`0x2E0010B1`); surveillance drone `0x40000892`.

---------------------------------------------------------------------------------------------------------------

## 4. Proposed structure placements (PvP maps)

Only Crime Alley's structures are anchored in the data. The rule below is taken from Crime Alley and applied to
every lane: **on Crime Alley the two lane structures of a team stand at 31.3 % and 74.2 % of the arc length from
its lane mouth to the lane midpoint** (mouth 21.8 -> midpoint 80: 40.0 and 65.0). The same rule on Crime Alley's
own waypoint polyline returns exactly (40.0, 77.5) / (65.0, 77.5) / (120.0, 77.5) / (95.0, 77.5) (C check). Every
proposed point below was computed on the data's own waypoint polylines (section 3) and is walkable on the fixed
navmesh (1.1 m agent). Structures must also block the grid (they are not cut out of the mesh).

### 4.1 Crime Alley (z 200.1)
| Object (class, Clash / tutorial family) | Team 1 | Team 2 | Derivation | |
|---|---|---|---|---|
| Power core (`0x40000C96` / `C8A`; `0x40000C98` / `C89`) | (17.5, 77.5) yaw 90 | (142.5, 77.5) yaw -90 | pedestal static + cinematics 0x3500003B / 3A + type-3 `0x2E0011A7` / `A6` | C |
| Outer turret (`0x40000C92` / `C8C`; `0x40000C93` / `C86`) | (65.0, 77.5) | (95.0, 77.5) | cinematic 0x35000038 + `0x2E0011AD` / `AC` | C pos, P class |
| Second structure, dampener (`0x40000C91` / `C88`; `0x40000C95` / `C87`) | (40.0, 77.5) | (120.0, 77.5) | `0x2E0011A9` / `A8`; Tutorial 2 socket `0x2E00119F` at (40.0, 77.5) | C pos, P role |
| Core turret (`0x40000C8F` / `C94`; `0x40000C97`) | (25.5, 77.5) | (134.5, 77.5) | Tutorial 2's friendly turret marker `0x2E0011AD` (25.5) / cinematic head (25.1) on the same lane; mirrored | G |
| Foundry (`0x40000170` / `0x4000016F`) | (1.3, 77.1, 201.8) | (158.7, 77.1, 201.8) | Tutorial 2 cinematic 0x3500002B (same lane, same layout pack); mirrored | G |
| Wave spawn (lane mouth) | (21.8, 77.5) | (138.2, 77.5) | `0x2E000AF9` / `AF8` + marker; Tutorial 2 drones leave from 22.3 | P |
| Player starts | (5.0, 77.5) + 4 slots | (155.0, 77.5) + 4 slots | type 16 | P |
| Jungle camp | (80.0, 95.5), loop of 3.3 | | type-21 loop + `0x2E000944` / `945` | P |
| 1vAI tutorial | team 2 uses the side-1 classes and the side-1 pedestal (ruleset `0x1000000B`) | | `0x55B` | C |

### 4.2 Gotham Divided (z 250.0; team 2 = team 1 with x and y swapped)
| Object | Team 1 | Team 2 | Derivation | |
|---|---|---|---|---|
| Power core (`0x40000A7E` / `A7B`) | (17.5, 142.5) yaw 45 | (142.5, 17.5) yaw -135 | pedestals + cinematics | C |
| Core turret (`0x400003BA` / `3C1`, ws `0x2E000AC4`) | (23.5, 136.5) side of the mid mouth, i.e. on the core ring (21.8, 136.9) | (136.9, 21.8) | core ring point facing the mid lane; one core-turret class per team | G |
| North lane, base-side structure (dampener `0x40000C61` / `C60`) | (56.3, 148.2) | (148.2, 56.6) | 31.3 % rule | G |
| North lane, outer turret (`0x400003BB` / `3C0`, tier 45) | (103.3, 144.7) | (144.5, 103.5) | 74.2 % rule | G |
| Mid lane, base-side structure (dampener) | (46.8, 113.1) | (113.1, 46.8) | 31.3 % | G |
| Mid lane, outer turret (`0x400003BF` / `3BE`, tier 55) | (67.3, 92.2) | (92.2, 67.3) | 74.2 % | G |
| South lane, base-side structure (dampener) | (11.8, 98.2) | (98.2, 11.8) | 31.3 % | G |
| South lane, outer turret (`0x400003BC` / `3BD`, tier 60) | (16.8, 55.2) | (55.2, 16.8) | 74.2 % | G |
| Wave spawn per lane | north (26.0, 142.5), mid (23.5, 136.5), south (17.5, 134.0) | (142.5, 26.0), (136.5, 23.5), (134.0, 17.5) | `0x2E000AF4`-`AF9` | P |
| Player starts | (7.5, 152.5) + 5 | (152.5, 7.5) + 5 | type 16 | P |
| Foundry | near the start points, e.g. (7.5, 152.5) offset 3 m toward the corner | mirrored | no anchor (Crime Alley's sits 3.7 m behind the start centre) | G |
| Control point / neutral objective (`0x400003AF`) | (55, 55) and (105, 105) | shared | symmetric `0x2E0003F0` sites | G |
| Jungle camps (`0x40000935`-`940`) | no anchor; candidates the four jungle quarters between the lanes, e.g. (45, 80), (80, 115) / mirrored (80, 45), (115, 80) | | none in the data | G |

Notes: GD has 4 turret classes per team but 3 lanes; the assignment of tier classes to lanes above is arbitrary
(G). If the original used two turrets per lane, use the dampener point for the inner turret and put the dampener
at the lane mouth + 8 m.

### 4.3 Coast City (z 250.0; team 2 = team 1 mirrored `x -> 160 - x`)
| Object | Team 1 | Team 2 | Derivation | |
|---|---|---|---|---|
| Power core (`0x40000C24` / `C23`) | (17.0, 62.5) yaw 105 | (143.0, 62.5) yaw 255 | pedestals + cinematics | C |
| Core turret (`0x40000400` / `3FF`, tier 100) | between the mouths, (21.5, 64.0) | (138.5, 64.0) | midpoint of the two mouths | G |
| North lane inner turret (`0x400003FA` / `3F9`, tier 55) | (30.9, 96.5) | (129.1, 96.5) | 31.3 % | G |
| North lane outer turret (`0x400003FD` / `3FC`, tier 35) | (55.2, 123.5) | (104.8, 123.5) | 74.2 % | G |
| South lane inner turret (`0x400003FE` / `3FB`, tier 45) | (40.7, 46.0) | (119.3, 46.0) | 31.3 % | G |
| South lane outer turret (`0x400003FD` / `3FC` reused) | (64.8, 28.0) | (95.2, 28.0) | 74.2 % | G |
| Doomsday Device (`0x400001F0`) + firing trigger (`0x4000054F`) | (80.0, 82.0) | shared | type-3 `0x2E001178` / `1181` at the map centre | P |
| Wave spawn | north (20.8, 67.0), south (22.5, 60.5) | (139.2, 67.0), (137.5, 60.5) | `0x2E000AF4`-`AF7` | P |
| Player starts | (4.7, 59.2) + 4 | (155.4, 59.1) + 4 | type 16 | P |
| Jungle camps (`0x40000893`-`89A`, guardian `0x40000430`) | (80, 145), (44.5, 90.5), (115.5, 90.5), (80, 9), (80, 57) | shared | type-3 camp markers + loops | P |

### 4.4 Gotham Heights (z 250.0)
| Object | Position | Derivation | |
|---|---|---|---|
| Capture points (`0x4000013B`, ws `0x2E000B22`) | (48.5, 27.5), (111.5, 27.5), (27.0, 90.0), (133.0, 90.2), (80.0, 127.8) | markers `0x10000188` | P |
| Team indicators per point | the team-variant pairs of 3.4 | `0x2E00041F`-`432` | C pos, G role |
| Generator / centre ring | (80, 74), sockets of 3.4 | `0x2E000006` ring | G |
| Player starts / bases | team 1 (6.0, 47.0) + 4, team 2 (154.0, 47.0) + 4 | type 16; core actors (18.4, 50.1) / (142.7, 50.3) | P |
| Foundry | team 1 ~(18.4, 50.1), team 2 ~(142.7, 50.3) | the cinematics' Character_0 core spots | G |
| Minion routes | the two waypoint rings (3.4) | type 21 | P |

---------------------------------------------------------------------------------------------------------------

## 5. Win conditions, timers, scoring, encounter scripts

### 5.1 Per map (summary)
| Map | Win (data) | Timers / scoring in the data | |
|---|---|---|---|
| Crime Alley, GD, CC | Destroy the enemy power core: each core has damage states `0x1000022F` (Phase1-4) and an end cinematic per team (CA 0x3500003A / 3B, GD 0x35000014 / 15, CC 0x35000012 / 13) | no match timer; `0x10000463` 200 / 300 per team on the Clashes | C for the data, P for the rule |
| Coast City (onslaught) | Core destruction, helped by the Doomsday Device (G: captured, then fires at the enemy core; impact counter as in 5.2) | camps, guardian | G |
| Gotham Heights | Capture points (`CapturePoint_Total_Team1/2`, `MatchTeamWon` / `MatchTeamLost`, record `0x3A000029`); 500 per team (`0x10000463`) | generator script `0x340002CF` (5.2) | P |
| Tutorials | Objective lists + conversations; Crime Alley tutorial: core destruction + script `0x34000628` | `0x1000021C` 300 | C |

Common: intro line-up cinematic per map (13.0 s, script `0x340006F2`: CA 0x3500003C, GH 0x35000023, GD 0x35000024,
CC 0x35000020); bot levelling script `0x340007E2` (`0x10000B41`) on every vs-AI encounter; the map-group timers
`0x10000C7B` 240 / 360 / 300 s of record `0x480010F6` belong to the mission system (maps-encounters.md 1.1). The
cinematic scripts `0x340006F2`, `0x3400076B`, `0x3400076C`, `0x340005DF`, `0x340005E5`, `0x340005F4`, `0x34000605`,
`0x340006A2`-`6A9`, `0x34000732`, `0x34000733` have no decoded tree in `data/script_trees` (O).

### 5.2 Script `0x340002CF` (Gotham Heights layout pack `0xA000016B` only; status record `0x480007C2`, C)
Two graphs. Variables: TeamFired, TeamDamaged, ImpactCounter, ImpactCounterMax, ImpactPending, Entry_Current,
Entry_Invalid, MissionEventHandle; graph 0 locals LockTimer, LockDuration, NeutralizedTimer, NeutralizedDuration,
NeutralPlusLockDuration, HandleEvent, HandleAnnounce; graph 1 locals GeneratorIID, ImpactIID, Timer, LoopIndex,
LoopMax, DurationImpactPhase1 / 2, DurationImpactTotal (= 61), Duration05sec, Duration10sec, Impact4Delay,
destruction radii and magnitudes. Flow (C): starts on event `0x10000085`; announcements (`0x1000011A`, strings
`0x2B000098`) chosen by ImpactCounter 1-3; on event `0x1000007A` -> team 1 fired / team 2 damaged, `0x10000079` ->
the opposite; ImpactCounter++; state S7 picks the mission entry `Entry_Team0N_Tier0M` (M = ImpactCounter 1-4) and
starts NeutralizedTimer; then LockTimer; graph 1 resolves the generator (`0x10000016` -> GeneratorIID), runs
`0x10000925` on the impact entity, reveals it in fog (`0x100006FC`), applies `DestructionImpulse` (large / small
cosmetic radii) at the impact position, loops LoopMax impacts; impact 4 has its own delay. The script itself has
no capture logic (no point counting): capture totals live in match variables `0x3A000029` (C names, P role).
Interpretation (G): GH's capture points charge a central generator that strikes the losing team up to 4 times.

### 5.3 Crime Alley 1vAI tutorial (0x40000CA6): script `0x34000628`, objectives `0x48001150`
- Objective list `0x48001150` (C): 15 entries (id / kind `0x10000352` / count `0x10000283`): 2, 1, 6, 5, 4 (kind 4),
  79, 80, 81, 82, 83 (kind 3), 84 (count 2), 85 (count 4), 86, 87 (count 1), 78 (count 1); no per-objective scripts;
  tracker `0x100004EF` = (2 -> kind 4), (1 -> kind 3).
- `0x34000628` (C structure): variables StageComplete, RemindTimer / RemindDuration, ConversationHandle1-5. Node
  meanings (P): `0x100000D1 [0, conv, ...]` start conversation, `0x1000017B` stop it, `0x10000167 [a, cmd, n, did]`
  tutorial UI command (a = 48-58, cmd 1-16, n = tip / objective number 40-52), `0x100000BB [-1, hash]` play a
  sound / VO hash, event `0x10000186` = conversation finished, `0x1000017D [0x1000017F, n]` = stage event n from the
  server. Root order: S0 (UI 51 cmd 3) -> **stage 4** -> conversation 553 -> 190 -> sub-graph A (247, 202, 204; UI
  51/45) -> B (253, 261, 167, 174; requires champion `0x40000086` via `0x1000018A`; reminders 372, 974, 973) -> C
  (197, 388) -> D (214, 222, 230, 239, 173; reminders 375, 373, 371; stage events 8 / 7 / 5 advance) -> E (166, 200,
  189, 389; reminder 374; stage 6) -> conversation 552 -> UI 49 cmd 16. **Stage 9 or 10 at any time -> end** (stop
  conversation). 28 conversations in all (0xA6-0x3CE range). What raises stage events 4-10 is server logic (O).

### 5.4 Tutorial 2 (0x40000A81): objective list `0x48000E3B` with per-objective scripts
29 objectives (id, kind `0x10000352`, key `0x10000B20`, script `0x10000B44`, `0x10000B71`, `0x10000B45`), C:
2 (kind 3), 1, 6, **50** (key `0x10000068`, script **`0x34000603`**, B71 1), 52 (`0x1000030A` = `0x130002D1`), 51,
42, **43** (script **`0x34000602`**, B45 1), 44, **45** (script **`0x34000601`**), 47 (key `0x10000068`, B71 2),
**48** (script **`0x34000604`**), 49, 8, 7, 27, 28 (key `0x10000087`), 29, 30, 31 (key `0x10000024`), 32, 34, 35,
36, 33 (key `0x10000068`), 37, 38 (key `0x1000007B`), 39, 40. Tracker `0x100004EF` = (1 -> kind 4), (2 -> kind 3).
- `0x34000601` (C): on start conversation 956; on its end -> conversation 541, objective nodes `0x10000060 [45, ..1]`
  and `[47, ..2]`, UI `[1, 5]`, `[24, 9, 39]`; RemindTimer loop repeats conversation 516; **stage event 2** ->
  stop 516, objective `[47, 2, .., 1]`, UI `[24, 10, 33]`.
- `0x34000603` (C): reads player / agent (`0x10000187` / `0x10000188`); stage 1 sub-graph: conversation 525 +
  objective `[52 .. 2]`, then 536, 508 + objective `[52 .. 1]`, `[42 .. 2]`, attribute `0x400004AD` set / cleared,
  reminders 957; stage 2 sub-graph: conversation 497, reminders 964, on **stage event 3** objective `[50, 2, .., 1]`,
  UI `[16, 10, 39]`, StageComplete.
- `0x34000602`, `0x34000604`: no decoded tree (O).
- So `0x10000060 [objective id, a, ..., state]` sets an objective's state (1 / 2) (P), and the stage events
  `0x1000017F n` are raised by the server when the player does the step (O: which actions).

---------------------------------------------------------------------------------------------------------------

## 6. Packs each encounter needs for its statics (0x20AF)

Method (as in movement-collision-fog-map.md 3.2): every world state of the map's statics; its home pack; then a
reference scan (two levels: the world state's record and its `.entity` / child world states; u32 values that are
existing DIDs of types 0x13, 0x14, 0x16-0x1A, 0x1C, 0x1D, 0x2D, 0x2E, 0x50; DIDs whose low 12 bits are 0 dropped as
noise). "Sent" = map pack + its list + `0xA0000037`. World-state counts are C; the reference counts are P (the scan
can match stray numbers; leftovers such as `0x1A001052`, `0x18001052`, `0x19001052`, `0x13001012` look like noise).

| Map | Statics with ws (unique) | ws in no installed pack (never loadable) | ws installed but unsent | Referenced DIDs unsent (ws / placements) | After + `0xA00000B3`, `0xA00000DF` | + `0xA000009A` | + `0xA00000D2` |
|---|---|---|---|---|---|---|---|
| Tutorial 1 | 997 (259) | 44 ws / 91 (type-3 emitters) | 0 | 49 (31 / 151) | 44 (25 / 142) | 32 (11 / 66) | 20 (9 / 26) |
| Crime Alley | 378 (192) | 17 / 18 (`0x2E0011A6`-`AD`, `0x2E000AF8` / `AF9`, `0x2E000944` / `945`, `0x2E00110F`...) | 0 | 51 (49 / 101) | 44 (46 / 96) | 26 (14 / 25) | 13 (11 / 16) |
| Tutorial 2 | 239 (108) | 20 / 24 | 0 | 30 (20 / 48) | 26 (17 / 44) | 20 (11 / 21) | 7 (8 / 12) |
| Gotham Heights | 658 (157) | 3 / 51 (`0x2E000626`, `6B3`, `6B4`) | 0 | 18 (16 / 89) | 10 (10 / 23) | 10 (10 / 23) | 7 (7 / 18) |
| Gotham Divided | 578 (121) | 9 / 57 (`626`, `6B3`, `6B4`, `AF4`-`AF9`) | 0 | 28 (25 / 164) | 21 (18 / 40) | 14 (13 / 13) | 13 (12 / 12) |
| Coast City | 786 (214) | 11 / 67 (`626`, `6B3`, `6B4`, `944`, `945`, `AF4`-`AF7`, `1178`, `1181`) | 0 | 40 (41 / 183) | 33 (35 / 176) | 11 (10 / 17) | 11 (10 / 17) |

Largest users (P): Tutorial 1 `0x2E001219` x35 (mesh `0x170012AC`: `0xA00000D2` / `0xA00000FC`), `0x2E0005D6` x17
(`0x2D0002E4` in `0xA00000B3`, meshes in `0xA000009A`), statics `0x2E000375` x10 (`0xA000009A`; a roof: fase3-gg); Crime Alley /
Tutorial 2 `0x2E0005D6` x30 / x18 (same), `0x2E001219`, `0x2E001324` (texture `0x130027D7`, `0xA00000D0`); GH
`0x2E0005D6` x21, `0x2E00062A` x17 / `0x2E00062B` x14 (`0x2D0004B9`, `0xA00000B3`), `0x2E001396` x12 (`0x2D000823`,
`0xA00000DF`), the ring `0x2E000006` x10 (table `0x1D0005F1`, `0xA0000161` / `0xA000016E`); GD `0x2E001029` x100 and
`0x2E000FBE` (mesh `0x1700006C`, `0xA00000DF`), `0x2E001396` x17, `0x2E000A3B` (table `0x1D000385`, `0xA00000B3`);
CC `0x2E000835` x18, `0x2E00094C` x14, `0x2E000653` x13, `0x2E00059D`, `0x2E0005A6` (meshes in `0xA000009A`).

**Recommendation per encounter (packs to add to the map list in 0x20AF):**
- Every map: **`0xA00000B3`** (30 MB, the game-data pack: `0x2D0002E4`, `0x2D0004B9`, base table `0x1D000385`, the
  encounter templates) and **`0xA00000DF`** (20 MB: unit scriptlet tables `0x1D0000E1` / `E2` / `E8`, `0x2D000823`,
  `0x1700006C`) (P).
- Crime Alley, Tutorial 2, Coast City, Tutorial 1: also **`0xA000009A`** (GH zone, 134 MB: the shared street meshes
  `0x1700075B`, `0x170004AF`, `0x17000568`, `0x1700052B` ...) (P).
- Tutorial 1, Crime Alley, Tutorial 2: also **`0xA00000D2`** (CC zone, 154 MB; `0x170012AC`, `0x17000D58`,
  `0x17000D5C`, `0x1700086B`) (P). GD: `0xA00000D2` adds one texture only.
- Gotham Heights: `0xA0000161` or `0xA000016E` for table `0x1D0005F1` of the centre ring (P); `0xA00000D0` (54 MB)
  for three textures (P, low value).
- The remaining single DIDs (`0xA0000116`, `0xA00000D0`, `0xA000024C`, small packs) are each 1-3 placements (P).
- Nothing can make the type-3 world states of "ws in no installed pack" appear (C).
The original server's list per encounter is unknown (O); test one map at a time, as for Tutorial 1.

---------------------------------------------------------------------------------------------------------------

## 7. Open questions
- What the type-3 world states not installed were (`0x2E0011A6`-`AD` structure sites, `0x2E000AF4`-`AF9` lane
  mouths, `0x2E000626` / `6B3` / `6B4` x17 on every 5v5 map, `0x2E000942` / `944` / `945` camps): sound / VFX
  emitters is the best guess; their positions are what matters.
- GD / CC turret count per lane and the jungle camp positions on GD (no anchor in the data).
- `0x10000463`, `0x10000464`, `0x10000429` of the UI record; match length (only a text).
- Which client or server events raise the stage events `0x1000017F n` of the tutorial scripts; trees of
  `0x34000602`, `0x34000604` and the cinematic scripts.
- Which of the two end cinematics plays for the winner (each places the core of one team with that team's players).
