# Map audit, every map the server runs: terrain sockets, missing assets, placed elements; the permanent terrain fix (2026-10-28)

Tester 2026-10-28 14:39-15:00 (Crime Alley v AI, AGL vs bot AWW, `diag --mapa --mapa-rellenar`): the black socket at
x 40 / 120 went away when the diag raised four terrain vertices in client memory (confirmed in game); the diag also
reported terrain layer texture `0x1300008C` missing on blocks 12BA, 12BC, 13BA, 13BC, 14BA, 14BC. Asked: a new
analysis of every map's load with all its elements in place, and a permanent fix.

Scope: Crime Alley `0x40000C82` (also 1vAI Tutorial `0x40000CA6`, Clash `0x40000E68` / `0x40000E74`: same map pack
`0xA0C112BA`), Gotham Divided `0x40000399` (`0xA0C11AD2`), Coast City `0x40000270` (`0xA0C122E2`), Gotham Heights
`0x4000013E` (`0xA0C11AF2`), Tutorial 1 `0x40000991` (`0xA0C112CA`) and, as reference, Tutorial 2 `0x40000A81`
(`0xA0C112C2`). Builds on `map-load-holes.md` (resolver, record format, section 5 byte spec), `black-ground-shapes.md`,
`map-object-census.md`, `deep-scan-maps.md`, `maps-complete.md`, `crime-alley-structures.md`, `map-manifests.md`.
Tags: **C** confirmed (code / data / log bytes), **P** probable, **O** open. Method: the decompiled client
(`re-work/decomp`), capstone on `InfiniteCrisis.exe` (read only), throw-away scripts in the session scratchpad over the
packs (terrain, statics, batches, navmesh, a DID index of all 616 packs). Nothing of the game is copied here: IDs,
offsets, numbers and short asset names only.

## 0. Short answer

| # | Finding | Tag |
|---|---|---|
| 1 | Socket scan of all 54 landblock terrain records (6 map packs): the sockets that render black and have nothing over them are Crime Alley's dampener pair (x 40 / 120), Gotham Divided's six base lane exits and two pits, and Coast City's 3 x 3 centre. Every other socket has a drawn static over it (core pedestals, street meshes) or lies outside the play area (section 2) | C data, P visibility |
| 2 | **Permanent fix implemented** (`icserver/terrainfix.py`, run by `python ic.py patch`): the map packs are single zlib streams of *stored* deflate blocks, so the socket heights and the normals around them are rewritten in place with the stream's Adler-32; verified (record, counts, CRC-32 original / patched), backed up, idempotent, revertible from `[game] terrain_sockets`; `python ic.py patch --dry-run` reports; `tests/test_terrainfix.py` 12 checks (section 6) | C (tested on copies of the three packs) |
| 3 | `0x1300008C` is the developer grid texture of terrain types 0 "DO NOT USE - Bottom_Layer_Grid", 1 "TEST - Worldbuilder - Grid" and 0xB "ter_test_grid" (table record `0x07000000`). It exists only in Tutorial 1's zone pack `0xA000024C`, which Crime Alley does not load (and must not: it hung the load, `[ics] match_extra_packs` 2026-10-25 23:03). The six outer Crime Alley blocks are unpainted (one grid layer) and lie outside the play area: same in the original install. No substitute needed | C data, P not visible |
| 4 | New: **Gotham Divided's own asphalt layer textures are not in its packs** (types 0xE / 0xF: `0x130007AC` / `AB` / `AA` / `A9`, only in the CA / GH / CC zone packs), nor is type 0xC's (`0x13001FC9` / `C8`, nowhere). The street meshes cover most of it; where the terrain shows (the **team-2** lane-exit openings; "team-1" here was wrong, see 10.1), the flattened ground will be drawn with unbound textures | C data, O look (diag recipe 7.3) |
| 5 | Several outer blocks (CA 12BA / 12BC, GD 1AD3 / 1AD4 / 1BD2 / 1BD4 / 1CD2 / 1CD4) have batches whose layer index is past the end of the block's palette; the reader `0x53F4A0` reads exactly `count` entries, so the client takes the descriptor from heap memory past the array (the diag's "type 0x1" / "type 0x2" on 12BA / 12BC) | C code + data |
| 6 | Every drawn static (types 2 / 7 / 10 / 21) of every map has its world state in the packs that map loads; only type-3 markers are not installed (never instantiated) | C |
| 7 | Server placements vs the data's anchors: starts, lane mouths, dampeners, lane turrets, CC camps / device and GD lane mouths match their markers. Differences: Crime Alley's cores take the pedestal's yaw (90 / -90), the markers and the end cinematic say -90 / 90; the side camps have one marker (west, `0x2E001118`); the middle camp stands on the nook markers the tester says must stay empty; stealth fields, SUV, gates, auras, foundries, GD / CC turrets have no data anchor (section 4) | C data, G where noted |

---------------------------------------------------------------------------------------------------------------------

## 1. The terrain record and the pack stream (what the patch relies on)

### 1.1 Record `0x80 | 01 | lbx | lby` (db type 0x0E, create `0x545BF0`, unpack `0x9D8160` -> `0x5490D0`) (C)

`0x5490D0` (this = the 0x1D0-byte object) reads, in order: DID (`0x43D210`); +0x30 flags (`0x53D6B0`: u32 0x441 + 1089
bytes, split diagonal bit 0x80); +0x3C heights (`0x53D630`: u32 0x441 + 1089 u16); +0x48 render block (`0x547740`:
palette `0x53F4A0`, two `0x544340` arrays (batches, and P the far patches), three u16 arrays (P: the 6144 indices,
`u32 0x1800 | u16 x 6144`, is one of them), 2 bytes, 4 u32); +0xC4 normals (`0x4DF920`: u32 0x441 + 1089 x 3 f32); f32 +0xD0 / +0xD4 (z max / min: 13BB 199.98 / 0.0); +0xD8
an embedded Havok packfile (`0x5DBBF0`; "hk_2012.2.1-r1", class `hkpMoppCode`, 0x35AC bytes on 13BB); one byte = LOD 1
present (then +0xE0 heights, +0xEC block, +0x168 normals, 2 f32, +0x17C Havok); +0x184 / +0x194 / +0x1A4 (the map's pack
list `3 | 0xA00002E5 | E6 | E7` is one of them); u32 +0x1B0 = the statics record DID (`0x820113BB`, used by `0x549330`);
4 f32, 2 u32, 3 flag bytes.

| Record | Pack | Decompressed offset | Heights | Normals | LOD 1 |
|---|---|---|---|---|---|
| `0x800113BB` (CA) | `0xA0C112BA` | `0x38E1A44` | +0x450 | +0x81F8 | absent (no second 0x441 array; diag fill touched only +0x3C) |
| `0x80011BD3` (GD) | `0xA0C11AD2` | `0x5950C` | +0x450 | +0x800C | - |
| `0x800123E3` (CC) | `0xA0C122E2` | `0x57BAF54` | +0x450 | +0x8C9C | - |
| `0x800113C3` (T2) | `0xA0C112C2` | `0x472D570` | +0x450 | +0x80FC | - |

Vertex (x, y) = index `(x / 5) * 33 + y / 5`; z = u16 * 2000 / 65535 (`0x712860`: inner loop over x, `*(u16 *)(heights +
x * 0x42 + y * 2) * 2000 * [0x1864238]`; normals copied from +0xC4 with the same index when the vertex format has bit
0x10). No hole flag and no special case for height 0 exists in `0x712860` (C): a 0 m vertex is a 200-250 m funnel.

Batch (in the +0x48 block, after `u32 n | n palette type ids | u32 batches`): `n | n x palette index | first index |
triangles | first vertex | vertices | 6 f32 bbox | mask DID | material DID | 15 words` (C, re-parsed on every map; the
earlier "16 floats" was one word too many).

The stored normals are not a formula of the stored heights (central differences, area- or unit-weighted face sums with
either diagonal: p95 error 0.17-0.36 on four maps; exact only where no 0 m vertex is near, e.g. (35, 75)): the editor
computed them from its own data (P). The patch therefore writes central differences only where the result is plain
street, and keeps the record's normal where another drop is next to the vertex (section 6.2).

### 1.2 Collision, bounds, MOPP (P)

The collision mesh (`0x53E290` -> `0x53BBE0` -> `0x53BB00`) is built from the same +0x3C heights, so the patch reaches
render and collision together, exactly like the diag fill (which wrote the object's arrays before both builds). The
embedded MOPP code and the f32 z bounds were computed for the sunk vertices; every raised triangle lies inside its
original triangle's box (its z range shrinks to the ring's level, which was already a corner of it), so the MOPP tree
and bounds stay conservative (P from the MOPP principle; the tester's in-memory test had the same state).

### 1.3 The stream (C)

All six map packs start their stream with `78 01 00 FB FF 04 00`: a zlib header and *stored* deflate blocks of 0xFFFB
bytes (CA 2433 blocks, GD 2781, CC 4496; all stored, walked by the patch; `0xA0000038` is stored too,
`countdown-keymap-gaps.md` 2.3). The decompressed bytes lie
verbatim in the file: payload offset q -> file offset `0x400 + (q / 0x1FFFC) * 0x20000 + q % 0x1FFFC` (the last 4 bytes
of each 0x20000 block are a length trailer, not a checksum); the only integrity value is the zlib Adler-32 after the
last block (big-endian), which inflate checks. The default-keymap patch of `0xA0000038` (fase3-hp, same method) has
been loaded by the client since 2026-10-25 00:30 (file date; `0x12B769` = 02, Adler `c7bdb6fc`): the client accepts
an in-place edit with a recomputed Adler-32 (C by use). The server install and the Steam copy hold the same map packs
(md5 of `0xa0c112ba.rp` 35e55d3e..., both).

## 2. (a) Terrain sockets on every map

### 2.1 Rule

Per landblock, a vertex is "sunk" when it lies 3 m or more below the highest vertex of its 5 x 5 window; sunk vertices
are grouped (8-neighbour); a group is a socket when every vertex around it is at least 3 m higher than the group's
highest vertex and it has at most 40 vertices (the 180 m "covered" level under the buildings, 407 vertices on CA 13BB,
is not a socket). The outer edge rows at z 0 (y = 160 of the north blocks, x = 160 of the east blocks, all six maps)
are the world's border, outside every map. Statics are the `0x82` entries within the socket's box + 5 m (parser:
`map-object-census.md` 0.1 plus the light shape `0x576`: `1 | radius` or `7 | 13 words`; every record parses to its
count).

### 2.2 Table

| Map / record | Vertices -> z (ring) | Opening | What stands on it | Seen | Action |
|---|---|---|---|---|---|
| CA `0x800113BB` | (40, 75), (40, 80) -> 179.96 (199.98) | x 35-45, y 70-85 | marker `0x2E0011A9` only (not installed); lane-edge props | **black** (CA-1, every test); fixed by the diag fill 2026-10-28 14:40 | site `crime_alley_dampeners` |
| same | (120, 75), (120, 80) -> 179.96 | x 115-125, y 70-85 | marker `0x2E0011A8` only | **black** (13:13 test, frame 110 s) | same site |
| same | (15-20, 75-80) and (140-145, 75-80) -> 0 | 10 x 10 m | core pedestal `0x2E000A3B` + street pieces `0x2E001207` / `11B7` / `11B8` / `1185` / `1402` | no | keep |
| same | (60-70, 70-80) + (75, 80) -> 0 (198.5-199.98) | x 55-80, y 65-85 | marker `0x2E0011AD`; the street meshes cover it | no (frame 6:12) | keep (P: street mesh) |
| same | (80, 65), (85, 50-65), (90, 55-60) -> 0-195 | south alcove | `0x2E000B59` (77.1, 61.1, 197.24), `0x2E00128C`, `0x2E00073D` ... | no | keep |
| same | (160, 0-10) -> 179.96 | block corner | - | outside | keep |
| T1 `0x800113CB` | (85, 150), (90, 150) -> 190.2-191.6 (197.2-199.98) | 6-9 m dip | 20 statics around (88.3, 147.1) (steps / building) | no | keep |
| T1 `0x800114CB` | (15-20, 35-40) -> 0 | core | pedestal `0x2E000A3B` | no | keep |
| T2 `0x800113C3` | (40, 75), (40, 80) -> 179.96 | as CA | **`0x2E00119F`** (40.0, 77.5) yaw -90 (T2 only) | no | keep |
| GD `0x80011BD3` | (40, 150), (35, 125), (10, 120) -> 199.98 (249.97) | 10 x 10 m each | debris `0x2E000EE1` (1.2 m) | **black** (GD-1 / GD-2) | site `gotham_divided_lane_exits` |
| same | (150, 40), (125, 35), (120, 10) -> 199.98 | same | debris `0x2E000EE1` | (mirror, not filmed) | same site |
| same | (55, 55), (105, 105) -> 0 (249.97) | 10 x 10 m | lid `0x2E0003F0` (z 247.47, `0x2A1` without value: hidden, P), tram `0x2E000FBE`, `0x2E00133D` / `133E` | **black** (GD-3) | site `gotham_divided_pits` (off by default) |
| same | (15-20, 140-145), (140-145, 15-20) -> 99.98 | core | pedestal `0x2E000A3B` | no | keep |
| CC `0x800123E3` | (75-85, 65-75) 3 x 3 -> 0 (249.97) | x 70-90, y 60-80 | plaza set `0x2E000AD1` / `BE8` / `BE7` at (80.0, 70.4) (meshes in the south plaza, census 3.1) | **black** (CC-2) | site `coast_city_centre` |
| same | (80, 85) -> 199.98 | 10 x 10 m | device pad `0x2E000C57` (80, 85, 249.75), the device | no | keep |
| same | cores (15-20, 60-65), (140-145, 60-65) -> 0 | core | pedestals | no | keep |
| GH `0x80011BF3` | diagonal (115, 10) .. (125, 25) -> 0 between the 249.9 street and the 200 m covered level (not enclosed) | crack | ramp / props `0x2E000861`, `0x2E0007AD` / `7AE`, `0x2E00012C`, lights | no | keep |

Crime Alley's lane-turret socket and cores are hidden by the street meshes and pedestals: those statics have openings
only at the two dampener sites, which their own (missing) platform model filled (P, `crime-alley-structures.md` 3).

### 2.3 Values the patch writes (C, computed from the records)

| Site | Heights | Normals written / kept |
|---|---|---|
| `crime_alley_dampeners` | 4 x 0x1709 (179.96) -> 0x1999 (199.98) | 24 written, all (0, 0, 1) |
| `gotham_divided_lane_exits` | 6 x 0x1999 (199.98) -> 0x1FFF (249.97) | 50 written (street tilt <= 0.003); kept (115, 5), (155, 35-45) (next to the 0 m block edge / another drop) |
| `gotham_divided_pits` | 2 x 0 -> 0x1FFF | 18 written |
| `coast_city_centre` | 9 x 0 -> 0x1FFF | 24 written; kept (80, 80) (next to the 50 m device socket at (80, 85)) |

Target = median of the vertices around each connected group; a normal is the central difference of the raised grid
unless one of its four axis neighbours differs by 3 m or more (then the record's own normal stays).

## 3. (b) Assets the maps reference, against the install

### 3.1 Statics (C)
Every type 2 / 7 / 8 / 10 / 21 static of the nine blocks of every map has its world state in the map pack, its three
packs or the start-up packs (`0xA0000039 / 38 / 11A / 37 / DF / B3 / 103 / 351 / D0`): CA 317 type 7, GD 383, CC 511,
GH 422, T1 782, T2 296, 0 missing. Uninstalled: type-3 markers only (CA 17 world states: `0x2E000944` / `945`, `AF8` /
`AF9`, `110F`, `1110`, `1117`, `1118`, `111B`, `1120`, `1121`, `11A6`-`11A9`, `11AC` / `11AD`; GD / CC / GH:
`0x2E000626` / `6B3` / `6B4` and the lane-mouth markers; type 3 is never instantiated, `map-object-census.md` 0.2).
Model / material / texture closure of the statics: `black-ground-shapes.md` 5 and `map-load-holes.md` 2 (no gap).

### 3.2 Terrain layers: the type table `0x07000000` (C)

Record `0x07000000` (db type 0x2A, unpack `0x9D8430` -> `0x4DC790`) in `0xA0000038`, decompressed `0xDBBE8`-`0xDCE5C`:
`did | 1 | 42 | 42 x (type id | name length | name | 0 | u32 | tex A | tex B | uv floats ... | projection 3 | ... |
tex C | colour | f32 tiling)`. A = the layer's colour texture (descriptor +0x10, the diag's "A"), C = the second one
(+0x58). The ones that matter:

| Type | Name | A | C | Installed in |
|---|---|---|---|---|
| 0x00 | DO NOT USE - Bottom_Layer_Grid | `0x1300008C` | - | `0xA000024C` only (T1 zone) |
| 0x01 | TEST - Worldbuilder - Grid | `0x1300008C` | - | same |
| 0x02 | ter_gas_cobblestone | `0x1300008D` | `0x1300008E` | `0xA000009A`, `0xA000024C`, `0xA00002E5` |
| 0x0B | ter_test_grid | `0x1300008C` | - | `0xA000024C` |
| 0x0C | ter_gas_street | `0x13001FC9` | `0x13001FC8` | **nowhere** |
| 0x0D | ter_gas_cobblestone_c | `0x130023B4` | `0x130023B3` | `0xA00000FC` (GD zone) |
| 0x0E | ter_got_asphalt | `0x130007AC` | `0x130007AB` | `0xA000009A`, `0xA00000D2`, `0xA00002E5` (**not GD**) |
| 0x0F | ter_got_asphalt_worn | `0x130007AA` | `0x130007A9` | same + `0xA000016B` (A only) (**not GD**) |
| 0x25-0x28 | ter_gas_tut_* | `0x13003389` / `8F` / `92` / `8C` | `...88` / `8E` / `91` / `8B` | `0xA000024C`, `0xA00002E5` |

Per map (batches of all nine blocks, textures checked against the map's packs + start-up packs):

| Map | Missing layer textures | Where |
|---|---|---|
| CA | `0x1300008C` (types 0 / 1) | 12BA, 12BC, 13BA, 13BC, 14BA, 14BC: one grid layer over the whole block (bbox z 180-200 / 0-180), the diag's six blocks exactly |
| GD | `0x130007AC` / `AB` / `AA` / `A9` (0xE / 0xF), `0x13001FC9` / `C8` (0xC), `0x1300008C` | 1BD3 batches 0, 1, 3-7 (asphalt over most of the block; under the street meshes), 1AD2 |
| CC | `0x1300008C` | 23E4 batches 2-4 (2-4 triangles at the north edge) |
| GH, T1 | none | - |
| T2 | `0x1300008C` | 13C3 batches 1 / 2 / 6 / 8 / 9 (its east half, P unused by the tutorial) and its outer blocks |

Materials (`0x14000209` / `20A` / `20C` / `20E`) and blend masks of every batch are installed (C).

### 3.3 `0x1300008C`: what it is, and no substitute needed (C / P)
- It is the editor's grid ("DO NOT USE", "TEST", "ter_test_grid"): the base layer of terrain nobody painted. Crime
  Alley's six outer blocks are exactly that: one grid layer, outside the lane block, at the 180 m covered level under
  the building ring (bbox z 180-200 / 0-180). The original install is this install, so the original client had the
  same unbound slot (P: never visible).
- In 12BA / 12BC the batch's layer index is 1 with a one-entry palette (finding 5): the descriptor comes from memory
  past the palette, which is why the diag logged "type 0x1" and "type 0x2" there.
- Substitute if it ever shows: patch type 0 / 1's A in `0x07000000` (`0xA0000038` decompressed `0xDBC98` and `0xDBD80`,
  same-length + Adler, as the keymap) to `0x1300008D` (cobblestone, in CA's zone pack). Global table: Tutorial 1, which
  has the grid, would change too. Not recommended. Do not add `0xA000024C` to Crime Alley's `0x20AF`: it hung the load
  at 10 % (2026-10-25 23:03, `[ics] match_extra_packs` comment).

### 3.4 Gotham Divided's asphalt (C data, O look)
**Correction (10.1, re-checked in 11): the two sides below are swapped.** The render index buffer holds y_i * 33 + x_i;
team 1's exits are in batch 2 (installed 0x7 / 0xD), team 2's in batch 1 (asphalt 0xE / 0xF, not installed).
GD's terrain names types 0xE / 0xF / 0xC, whose textures are in no GD pack. Where the street meshes cover the terrain
it does not matter; at the openings it does: the team-1 lane exits (40, 150), (35, 125), (10, 120) sit in batch 1
(layers 0xE, 0xF, mask `0x13001191`, material `0x1400020A`), the team-2 exits and both pits in batch 2 (0x7 dirt, 0xD
cobblestone: installed). After the flattening the team-2 exits and pits get real ground; the team-1 exits get flat
ground with unbound textures (P: dark). The pack that has the four textures and is loaded by another map: CA's zone
`0xA00002E5` (132 MB), GH's `0xA000009A`, CC's `0xA00000D2` (recipe 7.3).

### 3.5 The diag's resolver lines (P)
The 14:40 run logged the missing textures only through the batch breakpoints (`0x313852` eax = 0); no `MAP NOT FOUND`
line and no summary appeared (diag closed without Ctrl+C, and the texture getter's failure does not pass `0x43CF15`, P:
a DID listed in no loaded pack is refused before the resolver's load path). The batch lines are the reliable signal.

## 4. (c) Server placements against the data's own anchors

| Map | Element | Server (ics/match/maps.py, ics/config.py) | Data anchor | Verdict |
|---|---|---|---|---|
| all | starts | 5 / 6 per team | type-16 entries (same xy) | C match |
| CA | cores | (17.5, 77.5) / (142.5, 77.5), yaw 90 / -90 (pedestal `0x2E000A3B`'s yaw) | markers `0x2E0011A7` (17.5, 77.15) yaw -90, `0x2E0011A6` (142.5, 77.75) yaw 90; end cinematic actor PowerCore `0x2E000AC5` (142.5, 77.75) yaw 90 | position C; **yaw opposite** to the markers and the cinematic (P: they give the core's facing; the pedestal is symmetric) |
| CA | dampeners | (40, 77.5) / (120, 77.5), heading to the enemy core | markers `0x2E0011A9` / `A8`, yaw -90 / 90 (= the same heading) | C match |
| CA | lane turrets | (65, 77.5) / (95, 77.5) | markers `0x2E0011AD` / `AC`; cinematic actors Blue / RedTurretBody `0x2E000AA0` | C match |
| CA | core turrets | (25.5, 77.5) / mirror | none on CA; Tutorial 2's layout (same packs) has its friendly turret head at (25.12, 77.46) | P (0.4 m) |
| CA | lane mouths | (21.8, 77.5) / (138.2, 77.5) | `0x2E000AF9` (21.75, 77.5), `0x2E000AF8` (138.3, 77.5) | C match |
| CA | camps | middle (80.0, 97.66), west (48.75, 93.0), east (111.25, 93.0) | nook: `0x2E000944` / `945` (80.0, 97.25) yaw 180 + `0x2E001117` / `1120` (79.96, 97.13); west: `0x2E001118` (48.75, 93.0); **no east marker**; `0x2E001121` (80.0, 119.0) | west C, east G mirror; the tester wants no middle camp (the nook markers' role is O) |
| CA | stealth fields | 8 tiles `0x2E000D36`, G | none (no static, no layout entry names `0x2E000D36`) | G; navmesh edges below |
| CA | SUV / van | (102.3, 93.6) yaw 245 / (57.7, 93.6) yaw 115, G | none | G; navmesh edge below |
| GD | lane mouths | north (26.0, 142.5), mid (23.5, 136.5), south (17.5, 134.0) | `0x2E000AF7` / `AF9` / `AF5` (same) | C match |
| GD | dampeners | `[ics] match_dampener_sockets` -> the lane-exit sockets | sockets (section 2) | P |
| GD | beacons / pods | (55, 55) / (105, 105) | lid `0x2E0003F0`, tram `0x2E000FBE` at the same points | C |
| CC | camps | (80, 145), (44.5, 90.5), (115.5, 90.5), (80, 9), (80, 57) | `0x2E000942` / `944` / `945` triples at the same points (yaws 180 / -74 / 80 / 180 / 180) | C match (yaws not used by the server) |
| CC | device | (80, 82) | `0x2E001178` / `1181` (80.0, 82.02) yaw 180 | C match |
| CC | lane mouths | (20.8, 67.0) / (22.5, 60.5) | `0x2E000AF7` (20.75, 67.0), `0x2E000AF5` (22.5, 60.5) | C match |
| GH | capture points | 5 points | lights `0x2E00041F`-`432` in pairs ~13 m beyond each point | P |
| all | gates, auras, foundries, GD / CC turrets, CC relays | G / P values | no data anchor | unchanged |

**Navmesh edges for the placements the tester asked about (C, `ics.navmesh` grid of `0x90` records, 0.25 m raster):**
- Left jungle mouth: the corridor from the lane (y 82.5) north is walkable for x 47.25-52.35 at y 83.0-85.5; its east
  (fence-side) edge is vertical at **x = 52.35** up to the corner **(52.6, 86.0)**, then runs diagonally north-east to
  (57.75, 89.0) (**30 deg**). The fence pieces on that corner: `0x2E0012F5` (53.30, 83.66) yaw -90, (53.36, 85.65) yaw 0,
  `0x2E0012FF` (53.62, 83.66), `0x2E0004D6` (53.34, 85.63) yaw 180 (the corner pillar).
- Right jungle mouth (mirror within 0.15 m): west edge **x = 107.5** for y 83.5-85.5, corner (107.25, 86.0), diagonal to
  (102.25, 89.0); fence pieces `0x2E0008F6` (106.85, 83.46), `0x2E000595` (106.95, 83.37), `0x2E0008F5` (106.85, 85.46)
  and (104.06, 86.65) yaw 67.
- North of the SUV: the walkable edge falls from (99, 96.3) to (107, 92.5) (25.4 deg, the SUV's own tilt): at the SUV's
  x 102.3 it is y = 94.7. With the blocker half-width 1.05 (`[ics] liftable_blockers`) the SUV already touches the
  navmesh edge; the wall the tester sees lies beyond it (navmesh edges are inset by the agent radius), so "closer to the
  wall" = up to ~1 m north along +y (G).
- Original frame 47 (left mouth, 02:26): the four yellow drones stand on the upper sidewalk 3-6 m north and 0-4.5 m
  west of the field's top, i.e. about **(46-51, 89.5-92.5)**, around the west marker `0x2E001118` (48.75, 93.0) (G from
  the frame, ~45 px/m); mirror (109-114, 89.5-92.5).

## 5. Other findings
- The terrain records of every map have no LOD-1 arrays (C for the four patched records; the diag fill found none at
  +0xE0).
- Gotham Heights' east side has a diagonal 0 m crack (115, 10)-(125, 25) under a ramp of props; its west side is flat
  (asymmetric terrain, not reported).
- Crime Alley's terrain is asymmetric too: the lane-turret socket exists only on the team-1 side (60-75, 70-80).

## 6. The permanent fix (implemented in this build)

### 6.1 Files
- `icserver/terrainfix.py` (new): `SITES` (pack, record DID, decompressed record offset, normals offset, vertices, CRC-32
  of the bytes it rewrites before / after), `Stream` (the stored stream mapped to file offsets, Adler-32), `site_spots`,
  `site_state`, `apply(rp_dir, enabled, dry_run=False, sites=None)`.
- `ic.py`: `cmd_patch` runs `terrainfix.apply` after the keymap pack patch; `python ic.py patch --dry-run` prints the
  exe's patch count and what each site would do, writing nothing.
- `icserver/config.py` `[game] terrain_sockets` = `["crime_alley_dampeners", "gotham_divided_lane_exits",
  "coast_city_centre"]` (dated comment). `gotham_divided_pits` is off: the pods rise there and the server lids sit there.
- `tests/test_terrainfix.py`: 12 checks (synthetic pack whose patched bytes straddle deflate and file blocks: dry run
  writes nothing, patch inflates with a valid Adler-32, only the site's bytes change, backup written, second run keeps
  it, restore is byte-identical, unexpected bytes / bad Adler / compressed stream refused; then a read-only dry run of
  the four built-in sites against the configured install).

### 6.2 Behaviour
For each pack: parse the stream (all blocks must be stored), check its Adler-32; per site check `did | 0x441` at the
record offset and the 0x441 counts before the heights and the normals; compute the spots; CRC-32 of the current bytes =
original (`0x7DB4EFBF` CA, `0xF4006371` GD exits, `0xABA7B767` GD pits, `0x2E6B93F3` CC) -> write; = patched (`0x8BB7F049`,
`0x20839B64`, `0x1D494C5E`, `0x50EEBE42`) -> keep; else "unexpected bytes", untouched. The new bytes' CRC must equal the
patched value (self-check). Before writing, the original bytes go to `rp\<pack>.rp.terrainfix.json` (`{site: [[offset,
hex], ...]}`); the pack is rewritten through `<pack>.rp.tmp` + replace (run it with the game closed: a pack the game
holds open makes the replace fail and nothing changes, P).
A site removed from the list is restored from the backup on the next `python ic.py patch`; the backup goes away when no
site is left. Dry run against the install (2026-10-28): CA / GD exits / CC "would flatten", GD pits "off". Tested on
copies of the three packs: apply all, re-apply, restore -> md5 identical to the installed files; the server's own reader
(`ics/rp.py`, zlib) loads the patched packs.

### 6.3 What the tester does
`python ic.py patch` (game closed), then play Crime Alley: the street must be continuous at both dampeners **without**
the diag. `--mapa-rellenar` is no longer needed (on a patched pack it finds nothing to raise). To go back:
`terrain_sockets = []` under `[game]` in config.toml, then `python ic.py patch`.

## 7. Implementation plan (for the other areas; status of every item in section 11.4)

1. **GD lids vs the raised ground** (`ics/config.py` `[ics] match_socket_covers.gotham_divided`): drop the six lane-exit
   entries (40, 150), (35, 125), (10, 120), (150, 40), (125, 35), (120, 10) at z 247.47: the lid's top (249.97) is now
   the ground's height (z-fighting). Keep the two pit lids while `gotham_divided_pits` is off. Comment: tester report
   2026-10-28 15:00 / map-audit-all.md 7.1. Test: `tests/test_match.py` check that GD spawns only two socket covers.
2. **Crime Alley cores' yaw** (`ics/match/maps.py` `_crime_alley` core `"yaw": {T1: 90.0, T2: -90.0}`): the markers
   and the end cinematic say {T1: -90, T2: 90}. Change only after a frame of the original shows the core's front (G
   which side is the front). Key-less (data table); add a `[ics] ca_core_yaw_from_markers` switch if changed.
3. **Gotham Divided textures** (runtime check first): `python tools\diag.py --mapa` on a GD match; expected `MAP TERRAIN
   PROBLEM block 1bd3 batch 0/1/3-7 ... 0x130007ac MISSING`. If the team-1 lane exits stay dark after the patch, try
   `[ics] match_extra_packs.gotham_divided = [0xA00002E5]` (CA's zone pack has all four) in a test build; a second zone
   pack hung Crime Alley's load once (with `0xA000024C`), so watch the 10 % mark.
4. **CA camps** (`ics/match/maps.py` `_crime_alley` "camps"): tester: no middle camp -> remove the `"middle": True` entry
   (80.0, 97.66) (or `[ics] match_camp_overrides`); side camps around (46-51, 89.5-92.5) and (109-114, 89.5-92.5) (G,
   frame 47; west marker `0x2E001118` (48.75, 93.0) C). Test: test_match camp count 2 on CA.
5. **Stealth fields** (`ics/match/maps.py` "stealth"): the vertical field back to its previous yaw (tester), placed
   against the fence-side collision edge x = 52.35 (left) / 107.5 (right), y 82.5-86.0, the diagonal leg along 30 deg
   from (52.6, 86.0) / (107.25, 86.0). The tile's footprint convention (which side is 4 m at which yaw) is in
   `crime-alley-still-missing.md` 2.
6. **SUV** (`ics/config.py` `liftable_props_by_map.crime_alley` SUV `pos`): y + 1.0 (G) at the same yaw; navmesh edge
   y = 94.7 at x 102.3.
7. Docs only: `tools/diag.py --mapa-rellenar` help can say "obsolete after python ic.py patch" (not changed here:
   shared file).

## 8. Open
- The GD look of the missing asphalt (3.4) and whether the team-1 exits stay dark after the patch.
- The role of Crime Alley's nook markers `0x2E000944` / `945` / `0x2E001117` / `1120` (the tester says no camp there).
- Coast City's centre occupant (census 3.1); the patch makes it street until it is known.
- Whether the client's texture getter skips the resolver for a DID in no loaded pack (3.5).

## 9. Finalizer check (2026-10-28 ~18:50, read-only spot checks; no server code changed)

Confirmed (C):
- **1.3 stream and offsets.** For the three map packs, an independent `zlib.decompress` (`icserver/rp.py`) matches
  `terrainfix.Stream.read` over 0x9000 bytes from each site's record offset. Each `did | 0x441` header occurs exactly
  once, at the listed offset. The stored Adler-32 equals both the computed one and zlib's. Map-pack headers hold no
  checksum (`10PR`, 0x11, 1, payload size, count; the rest of the 0x400 bytes are zero). The bytes after the Adler-32,
  up to the payload size, are zero padding. The block trailers are lengths (first block 0x1FE74 = 0x1FFFC - 4 x 98
  DIDs). The precedent `0xA0000038` has the same layout: one stored stream, Adler-32 at payload 0x12D909 = file
  0x12DD2D = `c7bdb6fc`, byte 0x12B769 = 02, file date 2026-10-25 00:30.
- **2.2 / 2.3 values.** CA's four vertices are 0x1709 (179.96 m) with the ring at 199.98. GD's exits are 0x1999 with
  the ring at 249.94-249.97. GD's pits and CC's 3 x 3 are 0, with the ring at 249.97. The z max / min after the
  normals are 199.98 / 0 on CA and 249.97 / 0 on GD and CC.
- **The patch writes the state the tester saw working.** On CA the 28 spots (4 heights + 24 normals) have the same
  offsets and the same values as `tools/diag.py` `ml_fill`, the 14:40 in-memory fill. The only difference is the sign
  of zero in the normals' x and y (+0.0 here, -0.0 in the diag).
- **Tested on copies of the three real packs.** Applying all four sites: each pack inflates with zlib and the site
  heights are at street level. A second run reports "already flattened". `apply(..., [])` restores the packs
  md5-identical, removes the backups and leaves no `.tmp`. `python ic.py patch --dry-run`: CA, GD exits and CC "would
  flatten"; GD pits "off (as installed)". `tests/test_terrainfix.py`: 12/12.
- `logs\` was empty at 18:49, so the 14:40 diag lines could not be re-read. The CA confirmation rests on the tester's
  report (CHANGELOG fase3-if).

Gaps and contradictions:
1. **1.2 does not hold for `coast_city_centre`.** It holds for CA and GD: no cell has three or four raised corners, so
   every triangle keeps a ring vertex. In CC's 3 x 3, however, the four cells x 75-85, y 65-75 have all four corners
   raised. Their 8 triangles move from z 0 to 249.97, outside the region the record's MOPP code was built for.
   - The collision object does use the record's Havok objects. At 0x53BCB2 (`mov ecx, [edi]; push record + 0xD8;
     call 0x539D90`) it stores record +0xD8 [0] / [1] at its own +8 / +0xC (add-ref 0xF97590). The mesh itself is
     rebuilt from the heights (0x53BB00 vertices, 0x53BA00 triangles). (C)
   - At these call sites the MOPP is optional: 0x53E290 passes param_4 = 0, so a null +0xD8 does not raise
     0x80004005. (C)
   - Which query walks the MOPP (picking, ground probes, projectiles) was not traced. (O)
   - Impact: nobody walks there. The server navmesh (champion agent 0x10000003) is not walkable over x 72.75-87.0,
     y 60.25-77.5. A ground pick, a ground-target skill or a projectile over that square may miss the raised
     triangles. (P)
   - Recipe: after `python ic.py patch`, on Coast City hover, right-click and ground-target the centre square. If the
     cursor or the target ring drops through, set `terrain_sockets = ["crime_alley_dampeners",
     "gotham_divided_lane_exits"]` under `[game]` and run `python ic.py patch`; that restores CC byte for byte.
2. **The defaults conflict on Gotham Divided.** `[game] terrain_sockets` flattens the six lane exits by default.
   `[ics] match_socket_covers.gotham_divided` (`ics/config.py` 1215-1216) still puts the 10 x 10 x 2.5 m lid
   `0x2E0003F0` at z 247.47 on them. Its top (249.97) is now the street, so the faces are coplanar (z-fighting, P
   look). Plan item 7.1 must ship in the same build; otherwise leave `gotham_divided_lane_exits` out until it does.
3. **New: the navmesh hole over CC's centre.** The hole is x 72.75-87.0, y 60.25-77.5. That is narrower than the
   funnel's steep cells (x 70-90, y 60-80), so the navmesh was not baked against the 0 m funnel. Something at street
   level stood over the socket in the original: an occupant about 14 x 17 m including the agent inset (P, section 8
   item 3). After the patch the square looks like street but stays blocked, as before.
4. `catalog/index.html` (14:31) is older than the new `packs_notes.tsv` rows (15:43). `python ic.py catalog` has not
   been run yet (CLAUDE.md rule 3).
5. Section 7 status at 18:50: nothing is in the code yet.
   - 7.1: the GD lids are at 247.47.
   - 7.2: the core yaw is `{T1: 90.0, T2: -90.0}` (`ics/match/maps.py` 54).
   - 7.4: `"middle": True` is still set at 80.
   - 7.5: the stealth tiles are still at 105 / 108.
   - 7.6: the SUV is still at `[102.3, 93.6, 0.0]` (`ics/config.py` 1236).
6. Minor: an `OSError` from `Stream.save()` (game running) leaves `terrainfix.apply` and skips the packs after it.
   `cmd_patch` prints "Terrain sockets not patched". A rerun with the game closed completes the job (idempotent; the
   backup written before the failed save holds the original bytes).

## 10. Skeptic review (2026-10-28 ~19:30, read-only; no code changed)

**Verdict: partly confirmed.** The fix itself (sections 1, 2.3, 6) is sound and safe for Crime Alley. Three statements
are wrong, and the Gotham Divided and stealth-field plan items change with them.

Re-checked, holds (C):
- **Packs.** Each patched terrain DID is in exactly one of the 616 packs' DID lists, so no other pack can shadow the
  edited copy. Every block trailer of the three map packs is 0x1FFFC, except the first block's (0x1FFFC - 4 x count),
  so the trailers are lengths. Map-pack headers are version 0x11 with nothing after +0x14. The precedent `0xA0000038`
  is a version-10 pack: its extra header fields are a small table that its patch left unchanged, and the payload layout
  is the same.
- **In-memory apply.** Applying all four sites in memory (`terrainfix.Stream`, nothing written) changes only the site
  bytes and the Adler-32: 223 / 589 / 223 file bytes on CA / GD / CC, no header or trailer byte. zlib inflates the
  result, and the heights land at 199.98 / 249.97.
- **Nothing else holds a copy.** The client keeps no copy of pack data (`AppData\Local\InfiniteCrisis` is empty).
  `tests/test_terrainfix.py` passes 12/12.
- **Decomp.** 0x53BB00 and 0x712860 both build vertex (x = i x 5, y = j x 5) from heights[i x 33 + j], and 0x712860
  reads the normal at the same index. Neither has a hole case or a zero case. 0x53BBE0 = 0x53BB00 + 0x53BA00
  (0x800 triangles) + record +0xD8 through 0x539D90.
- **Server.** ics never reads terrain heights (it uses the navmesh and constants), so the patch changes nothing on the
  server side.
- Not re-checked: the core yaw and the camps in 4 (plan 7.2 / 7.4 already wait for a frame or follow the tester).

Corrections:
1. **The Gotham Divided sides are swapped in 3.4, in 0 #4 and in plan 7.3.**
   - The render index buffer holds vertex-buffer indices y_i x 33 + x_i (0x712860 writes vertex
     `local_28 * 33 + uVar10`, x = uVar10 x 5), not the heights' order.
   - Read that way, each batch's x / y range equals its stored bbox in 53 of 53 batches (CA 12, GD 8, CC 33). The
     transposed reading matches 1 of 53.
   - Team 1 (40, 150), (35, 125), (10, 120), which includes the filmed GD-1 / GD-2: batch 2. Its types are 0x7 and
     0xD (textures `0x13000097` / `98` and `0x130023B4` / `B3`), all in `0xA00000FC`, so they are installed. Their
     black was the funnel, as on Crime Alley, and flattening fixes them.
   - Team 2 (150, 40), (125, 35), (120, 10): batch 1, asphalt 0xE / 0xF, which is in none of `0xA0000168` / `FC` /
     `16E`. The client runs D3D11 (`UserPreferences.ini`: `GraphicsCore = D3D11`), where an unbound texture samples
     0, so P: these exits become flat dark squares.
   - The pits lie on the diagonal and are in batch 2 under either reading.
2. **9.1 is C, not P.** I decoded each record's `hkpMoppCode`.
   - Code info: offset -0.05; scale 83195.48 on CA (a 24-bit cube of 201.7 m) and 66565.06 on GD / CC (252.0 m).
   - Commands: split, single split, split-jump, double cut, rescale and reoffset are read as Havok's VM reads them. The
     key is 2 x (yc x 32 + xc) + t, as 0x53BA00 builds the triangles.
   - Validation: on all three maps all 2048 keys are reached. Of about 33,000 path constraints per map, none misses its
     own triangle; the other rescale order misses thousands.
   - After the patch: CA's 32 triangles and GD's 48 + 16 around the raised vertices stay inside their path's z
     interval. On CC, exactly the 8 inner triangles (keys 862-865, 926-929) have leaf z -0.05..0.13 and move to
     249.97.
   - Effect: AABB queries and short rays at street level over x 75-85, y 65-75 miss these triangles. A ray long
     enough to reach z 0.13 still tests them (O: how long the pick ray is).
   - The square is not walkable (navmesh boundary x 72.8-87.2, y 60.0-77.6). Keep the 9.1 recipe.
3. **Section 4 / plan 7.5: the diagonal navmesh edges at the jungle mouths.** Boundary edges for the champion agent
   `0x10000003` (radius 0.525):
   - Left: x = 52.2 for y 83.2-85.6, then a 45 deg chamfer to (53.0, 86.4), then (53.8, 86.8) -> (59.0, 89.0) at
     **22.9 deg**.
   - Right: x = 107.6 for y 83.2-85.8, then a chamfer to (107.0, 86.4), then on to (100.8, 89.0) at -22.8 deg.
   - The note's "(57.75, 89.0)", "(102.25, 89.0)" and "30 deg" come from the 1.1 m agent `0x10000002` (its edge at
     y 89 is x 57.7), mixed with the champion agent's vertical edge.
   - So the diagonal field leg runs at about 23 deg, parallel to the vehicles' 24-25 deg. The raster's 52.35 / 107.5
     are cell centres.

Caveats and missing cases:
4. **GD lids.** Plan 7.1 must ship with the GD exits site (9.2). But dropping the three team-2 lids exposes the ground
   of correction 1. Safer: split the site per team (team 1 on; team 2 off and its lids kept) until the asphalt is
   bound. Two ways to bind it:
   - a same-length edit of 1BD3's palette (record +0xCD4: 8 type ids, 0xE / 0xF at indices 6 / 7) to an installed
     GD type (the look is G);
   - a zone pack (a second zone pack hung Crime Alley's load twice).
5. **SUV (7.6).** The boundary north of it runs (102.2, 94.8) -> (107.2, 92.6) at -23.7 deg. The SUV's north face
   (half-width 1.05) already lies on it (94.55 at x 102.74). The 0.525 m inset puts the wall line 0.57 m further in
   +y, so +0.6 m is flush and +1.0 m overlaps the wall by about 0.4 m (G). The van at (57.7, 93.6) sits 0.1 m from its
   own edge, the same relation.
6. **Tutorial 2** (`0x40000A81`, listed in `ics/messages.py` ENCOUNTERS) has Crime Alley's socket, on the team-1 side
   only. Record `0x800113C3` at 0x472D570: (40, 75) and (40, 80) at 179.96 inside a 199.98 ring, normals count at
   +0x80F8. Its only occupant, `0x2E00119F`, has no geometry. If ics runs T2, the octagon shows; a
   `tutorial_2_dampener` site would be the same patch.
7. **First load.** The tester's next run is the client's first load of an edited version-0x11 pack. To roll back: set
   `terrain_sockets = []`, then run `python ic.py patch`.

go_ahead: yes, with 1-4 applied. Crime Alley as is; the GD exits per team, together with 7.1; Coast City on, with the
9.1 recipe.

## 11. Implemented (fase3-if: 2026-10-28 evening and 2026-10-29)

The skeptic's corrections 1-4 and 6 are in the code; nothing it refuted was implemented.

### 11.1 Decisive fact re-checked before keeping the per-team split (C)
Batch membership was re-read with the installed records (scratch `batchcheck.py`, read only). On every batch of CA 13BB
(12), GD 1BD3 (8) and CC 23E3 (33), the vertex range of its triangles equals its stored bbox only when an index k is
read as x = (k % 33) * 5, y = (k / 33) * 5 (12 / 8 / 33 of 12 / 8 / 33; the heights' order matches 0 / 0 / 1). With
that reading:
- GD team 1's exits (40, 150), (35, 125), (10, 120) are drawn only by batch 2 (layer types 0x7 / 0xD, installed);
- team 2's (150, 40), (125, 35), (120, 10) only by batch 1 (0xE / 0xF, asphalt, not in GD's packs);
- both pits are in batch 2.

### 11.2 What the code does
- **Sites** (`icserver/terrainfix.py` `SITES`; heights raised to the median of the ring, normals as section 2.3):

  | Site | Default | Heights | Normals | Whole triangles | CRC-32 original -> patched |
  |---|---|---|---|---|---|
  | `crime_alley_dampeners` | on | 4 x 0x1709 -> 0x1999 (199.98) | 24 | 0 | `0x7DB4EFBF` -> `0x8BB7F049` |
  | `gotham_divided_lane_exits_team1` | on | 3 x 0x1999 -> 0x1FFF (249.97) | 27 | 0 | `0x54929DF6` -> `0xA5E17FE7` |
  | `gotham_divided_lane_exits_team2` | off (unbound asphalt, 10.1) | 3, same | 23 | 0 | `0xBF41DA05` -> `0x6F0E1927` |
  | `gotham_divided_pits` | off (pods and lids) | 2 x 0 -> 0x1FFF | 18 | 0 | `0xABA7B767` -> `0x1D494C5E` |
  | `coast_city_centre` | on (10.2: not walkable) | 9 x 0 -> 0x1FFF | 24 | **8** | `0x2E6B93F3` -> `0x50EEBE42` |
  | `tutorial_2_dampener` | off (ics runs no Tutorial 2) | 2 x 0x1709 -> 0x1999 | 12 | 0 | `0xB6972663` -> `0xE0583DCF` |

  `ALIASES`: the first fase3-if name `gotham_divided_lane_exits` still means both GD team sites. The backup
  (`rp\<pack>.rp.terrainfix.json`) is read by decompressed offset, so the entry of a combined site restores whichever
  half is taken out; the entry is dropped once every byte of it belongs to a current site in a known state.
- **`[game] terrain_sockets`** (`icserver/config.py`, dated comment) =
  `["crime_alley_dampeners", "gotham_divided_lane_exits_team1", "coast_city_centre"]`.
- **The lids** (plan 7.1, done without deleting entries): each `[ics] match_socket_covers.gotham_divided` lid names the
  site under it (`"terrain_site"`). With `[ics] match_socket_covers_skip_flat` (true) `Match._spawn_socket_covers`
  leaves out a lid whose site `terrainfix.installed_state` reads as patched. That probe reads only the block headers and
  the record's arrays of the installed pack (a lazy `Stream`), cached per pack path, size and mtime, so the server needs
  no setting of its own. After `python ic.py patch` GD has 5 lids (team 2's exits, the pits); an unpatched install
  keeps all 8.
- **Report**: `python ic.py patch --dry-run` prints each site's state. A site that raises whole triangles (`whole_triangles`:
  2 per cell whose four corners are raised, up to 1 with three) carries the 9.1 MOPP caveat in its line: only
  `coast_city_centre`.
- `tools/diag.py --mapload-fill` / `--mapa-rellenar`: the help text says it is obsolete after `python ic.py patch` (on
  a patched pack it finds nothing to raise).
- `python ic.py doctor` (`icserver/doctor.py`): a WARN line names every site of `[game] terrain_sockets` that is not
  flattened in its pack yet, with the fix "python ic.py patch". The game runs either way.

Dry run against the install (2026-10-29 01:3x): CA, GD team 1 and CC "would flatten"; GD team 2, GD pits and T2 "off
(as installed)". The tester has not run the patch yet.

### 11.3 Checks
- `tests/test_terrainfix.py` 29 checks plus 3 more with `--real`:
  - synthetic pack: dry run, apply, Adler-32, only the site's bytes, backup, idempotent, restore, unknown bytes, bad
    Adler, compressed stream;
  - a split site over a combined patch, the lazy probe, a locked pack, the alias;
  - whole triangles (only CC, 8) and the MOPP caveat in the report;
  - the defaults: CA / GD team 1 / CC on, the rest off;
  - every `match_socket_covers` lid on a site's vertex names that site, and `match_socket_covers_skip_flat` is on;
  - the install: every site recognised, the probe reads each one;
  - **CA = the diag fill**: `crime_alley_dampeners` writes the same 28 spots (4 heights, 24 normals; sign of zero
    aside) as `tools/diag.py`'s 14:40 fill rule replayed on the installed heights;
  - `--real`: all six sites applied to copies of the four installed packs (each inflates, Adler-32 valid), a second run
    changes nothing, taking them all out leaves every pack md5-identical, with no backup or `.tmp` left (about 7 s).
- `tests/test_match.py`, 4 GD lid checks:
  - every lid names a site;
  - lids follow the install's state;
  - team 1 flattened leaves 5 lids, none on team 1's exits;
  - `match_socket_covers_skip_flat = false` gives all 8.

### 11.4 Section 7 status
| Item | Status |
|---|---|
| 7.1 GD lids | done as above (team 1's left out once flattened; team 2's and the pits' stay) |
| 7.2 CA core yaw | not changed: the markers / cinematic say -90 / 90, the pedestal 90 / -90; no frame of the original shows the core's front (P). Recipe: if a frame shows it, swap `"yaw": {T1: 90.0, T2: -90.0}` in `ics/match/maps.py` `_crime_alley` core behind a new `[ics]` switch |
| 7.3 GD textures | team 2's exits keep their lids (site off). Runtime check: `python tools\diag.py --mapa` on a GD match, expected `MAP TERRAIN PROBLEM block 1bd3 batch 1 ... 0x130007ac MISSING` (batch 1 = team 2's exits). Binding options (G look, not done): a same-length edit of 1BD3's palette (count at record +0xCD4, entries 6 / 7 = 0xE / 0xF, read by batches 0, 1 and 3-7) to installed types, then turn `gotham_divided_lane_exits_team2` on; or `[ics] match_extra_packs.gotham_divided = [0xA00002E5]` (a second zone pack hung CA's load) |
| 7.4 CA camps | done by the camps work (camps-colour-bar-positions.md 8.3: no centre camp, the original's slots) |
| 7.5 stealth fields | done by the stealth work with the champion-agent faces (stealth-alignment.md: 22.93 / 157.25 deg, not the 30 deg of section 4) |
| 7.6 SUV | done by the vehicles work (vehicle-lift-and-position.md 1: +0.33 m along the wall normal, same yaw; not the +1.0 m of section 4, which overlaps the wall, 10.5) |
| 7.7 diag help | done |

### 11.5 What the tester does and sees
- `python ic.py patch` with the game closed, once. It prints one line per site and per written pack; a pack the game
  holds open is reported "not written" and left as it was (run it again with the game closed).
- **Crime Alley** (also 1vAI Tutorial and Clash): the street is continuous at both dampeners without the diag.
- **Gotham Divided** (not tested since the 2026-10-25 video): team 1's three base lane exits are flat street; team 2's
  keep their lids; the pits are as before.
- **Coast City**: the centre square looks like street and is still not walkable. If the cursor or a ground-target ring
  drops through there, set `terrain_sockets = ["crime_alley_dampeners", "gotham_divided_lane_exits_team1"]` under
  `[game]` in config.toml and run `python ic.py patch` (9.1).
- To undo everything: `terrain_sockets = []`, then `python ic.py patch`. That writes the installed bytes back from the
  backup, byte for byte.
- Server side nothing else changes. ics reads no terrain heights; it probes the GD sites (a few KB) when a GD match
  places its lids. The map packs' `data/cache/tables_<pack>.json` entries are stamped by size and mtime, so they are
  rebuilt the next time something reads them (map packs hold no scriptlet tables).

### 11.6 Still open
- Coast City: which client queries walk the MOPP tree (9.1 / 10.2), and what stood over the centre (9.3).
- Gotham Divided: how team 2's unbound asphalt looks at runtime (7.3).
- Crime Alley: which side is the core's front (7.2), and the role of the nook markers `0x2E000944` / `945` /
  `0x2E001117` / `1120`.
- Whether the client's texture getter skips the resolver for a DID that is in no loaded pack (3.5).

## 12. Review fix (fase3-if, 2026-10-29): a site past the end of a pack's stream

A confirmed review finding (reproduced on synthetic 10PR packs): `terrainfix.Stream._dspans` had no bounds check, so a
site whose record lies past the end of a shorter stream (another version of the pack), or across its end, indexed past
the block list. The IndexError escaped every handler: `python ic.py patch` stopped with a traceback after the exe step
(later packs untouched), `--dry-run` crashed, and `installed_state` never cached its failure (each lid re-read the pack's
block headers). `_dspans` now raises ValueError for bytes outside the stream; `apply` reports the site as "not
touched" and goes on, `installed_state` caches "unknown", `ic.py`'s dry run catches OSError / ValueError as the real
run does. The installed packs are far from it (0x4C48A4 to 0x5681C0C bytes past each site). Test:
tests/test_terrainfix.py +1 (a site past and one across the end of a 0x100-byte stream: reported in the dry and the real
run, the pack untouched, "unknown" cached).
