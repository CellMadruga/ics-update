# Map load holes: what Crime Alley loads, what is missing, why the sockets are black (2026-10-28)

Tester's request (2026-10-28): find what the Crime Alley map (encounter `0x40000C82`, map pack `0xA0C112BA`, landblock
`0x13BB`, z ~200.3) tries to load (terrain, cells, statics, environment pieces, textures / materials, decals) and at
what positions, to explain the "hollow" black sections, above all the ~10 x 15 m socket around the second tower at
(40, 77.5) / (120, 77.5), where the original game shows continuous cobblestones.

Tags: **C** confirmed (code / data read), **P** probable, **O** open. Builds on and does not repeat
`crime-alley-structures.md` (3: no installed piece fills the socket), `black-ground-shapes.md` (2: terrain sockets),
`deep-scan-maps.md`, `map-object-census.md` (0.1 / 0.2: statics format and rules), `crime-alley-still-missing.md`,
`crime-alley-missing-elements.md`, `maps-complete.md`, `actor-creation-and-environment.md`, `full-maps-world.md` 2,
`map-loading-deep-scan.md`. Method: decompiled client (`re-work/decomp`), capstone on the exe (read only), throw-away
scripts in the session scratchpad (statics parser, reference closure, terrain batch / index / normal decoding). Nothing
of the game is copied here: only IDs, offsets and numbers.

## 0. Short answer

| # | Finding | Tag |
|---|---|---|
| 1 | Every record goes through one resolver, `0x43CE00` (via the wrapper `0x43A1E0`, handle `{db type, DID}`). A missing DID makes it return 0, nothing else: no placeholder, no log; each caller decides. Terrain-render batches abort the whole block's terrain on a missing material or layer type; missing textures are left unbound; missing statics' world states drop the static silently | C |
| 2 | Crime Alley's landblock records, statics, statics' world states, terrain materials, blend masks, far-LOD baked textures and the layer palette are all installed and in packs the match loads. The only DIDs the map names that exist nowhere are the **type-3 markers** (incl. `0x2E0011A9` / `0x2E0011A8` exactly at the socket centres), type-16 start points (no DID), the type-21 waypoint world state `0x2E000000`, and the `0x83` property collections (none installed on any map) | C (data), P (closure scan is heuristic) |
| 3 | The dampener sockets are **terrain**: vertices (40, 75), (40, 80), (120, 75), (120, 80) at 179.96 m, every neighbour at 199.98 m. 180 m is the level of the whole off-lane terrain that buildings cover (407 of 1089 vertices). The record's own stored normals there are tilted into the hole (e.g. (40, 75) -> (0, 0.61, 0.80)) | C |
| 4 | The triangles of the socket at x 40 are drawn by terrain batch "mask `0x13002E06`, material `0x1400020A`, layers 0x25 / 0x26", at x 120 by "mask `0x13002E06`, `0x1400020A`, layers 0x0E / 0x0F". The same batches draw most of the visible lane (x 2-68 / 82-158) correctly, and the blend masks have full weight at the sockets: the black is **not** a missing texture / material (P strong; the new diag confirms in game) | C (mapping), P (conclusion) |
| 5 | The server cannot reshape terrain (no message carries heights; terrain comes only from the `0x80` record). What the server can do is cover the hole (tried: `0x2E00119F`, `0x2E0000E3`, `0x2E000A3B`, all rejected by the tester). New route: **flatten the four vertices in the client** (diag experiment now, then an exe patch or a local pack patch) | C (no protocol), P (fix) |
| 6 | New runtime mode `tools/diag.py --mapload` (`--mapa`): logs every failed resolver lookup with its caller and the static / landblock being built, dropped statics with their positions, and per terrain batch its material / mask / layer textures (ok / MISSING). `--mapload-fill` (`--mapa-rellenar`) is the flattening experiment | - |

---------------------------------------------------------------------------------------------------------------------

## 1. The load path, end to end, and what a missing DID does (C unless tagged)

### 1.1 The resolver

- `0x5DFBA0` builds a handle `{db type, DID}` on the caller's stack (`ret 8`); with db type 0 it takes the type object
  from the prefix table `[0x1B68B30 + (DID >> 24) * 4]` (`[0x1B68F34]` vtable `0x15A75A0` +0xC = `0x5DFBF0`).
- `0x43A1E0(handle, flags)` (227 callers) -> `[[0x1B57E64]+4]` vt+4 = **`0x43CE00(mode 3, handle, flags)`**. The
  asynchronous path (`0x441CA0` / `0x441B60` requests, completion `0x43C770`) calls the same vt+4, so it is the only
  door to the data.
- `0x43CE00`: DID == `[0x1B57E6C]` (no DID) -> 0; vt+0x44 (collection of the type) == 0 -> 0; vt+0xA0 (cache) hit
  -> object; else the in-flight table (`0x43B7E0` on mgr+0x44, nodes keyed +0x30 type / +0x34 DID): a request that is
  not ready and not synchronous -> **0 at `0x43CEB4`**; else type vt+0x24 (loadable?) -> mgr vt+0x98 = `0x43A500`
  (create + read from the packs) -> **`0x43CEE2`** (eax = object or 0); then the finaliser (obj vt+0x30, flag +0x1D);
  failure of either -> **`0x43CF15`** (esi = 0 not found, esi != 0 finaliser failed) -> 0.
- No message, placeholder or default object is produced by the resolver. Strings that look like "missing" messages
  (`Failed to load LandBlockData ...`) are formatted by a few callers only (`0x53E290`, `0x549510`, `0x50C8B0`);
  whether they reach any log file in the retail build is O (none was seen in the tester's logs).

### 1.2 Per stage

| Stage | Function | Record (db type) | If missing |
|---|---|---|---|
| Enter match | `0xA99F00` (0x20AF) -> `0xA99E20` | encounter, pack list | earlier notes (`map-loading-deep-scan.md` 4) |
| Region | `0x50C8B0` -> `0x50C350` | `0x01000000` (0x46): 12 sub-record DIDs `0x02..0x07000000` ...; +0x64 = the terrain-type table used by `0x4DB370` | "Region.cpp" tag, region null -> no terrain layers anywhere |
| Landblock init | `0x5EC890` -> `0x549510` | `0x80` terrain (0x0E), `0x82` statics (0x23), `0x85` nav (0x0C) -> `0x90` (0x3B) | no block / no statics / no navmesh, silently |
| Collision mesh | `0x53E290` LandBlockMesh -> `0x53BBE0` -> `0x53BB00` (vertices from heights +0x3C, LOD 1 +0xE0) / `0x53BA00` (indices) | `0x80`; `0x81` (0x24) for LOD 1 (`0x53D9B0`) | returns 0 (no mesh) |
| Statics | `0x548550` (types 7 / 8 / 21) -> `0x54AF70` (world state + `0x50F` creation type) -> block filter vt+0x18 -> `0x544A50` | world state 0x2E (its `.entity`, tables) | static dropped silently (al = 0 at `0x54864E`) |
| Render-only statics | `0x5EC4F0` (types 2 / 10) | mesh / light | not created (Crime Alley 13BB has no type 2) |
| Landscape render block | `0x714280` -> near `0x712860` (vertices: heights +0x3C, normals +0xC4, LOD 1 +0xE0 / +0x168) or far `0x712310` -> `0x713DD0` | `0x80` | returns 0: block not drawn |
| Near batch material | `0x713C10`: material (`[batch+0x68]`, db 0x4A = 0x14) | `0x1400020x` | **returns 0 -> `0x713DD0` fails -> the whole block's terrain is dropped** |
| Near blend mask | `0x713C10`: `[batch+0x64]` (db 9 = 0x13), shader slot 0xBCE | `0x130027xx` / `0x13002Exx` | left unbound |
| Near layers | `0x4DB370(region table, type id)` per layer, palette in the `0x80` record | terrain-type descriptor | **returns 0 -> whole block dropped** |
| Layer textures | `0x7137B0`: descriptor +0x10 (slots 0xBEA+n), +0x14 (0xBEF+n), +0x58 (0xBF4+n), db 9; projection axis +0x38 (1 / 2 / 3), uv transform +0x18..+0x34 | 0x13 | left unbound (P: black / default sampler) |
| Far patches | `0x7132D0`: material `0x140002C5` (`0x43A9E0(0x156, 0x14, 0x4A, 2)`), three textures per patch via `0x712030` (slots 3000 / 0xBC3 / 0xBE6), fourth slot 0xBCA with a named default (`0x43A9E0(0x146, 0x14, 9, 1)`) | `0x1300341E`-`0x1300344D` | left unbound; only slot 0xBCA has a fallback |
| Lighting | `0x7EF240` (`map-loading-deep-scan.md` 1) | env 0x08 (0x2E) | returns before any light is set: unlit scene |

## 2. What Crime Alley references, checked against the install (C)

- Map pack `0xA0C112BA` holds the nine blocks' `0x80` / `0x81` / `0x82` records, `0x850113BB`, `0x900113BB` /
  `0x901113BB` / `0x902113BB` and 48 + 22 terrain textures. No other pack lists any `0x80 / 0x81 / 0x82` DID (no
  override copy of the terrain). No `0x83` record exists for any block of any map (the world preloader `0x7DEBD0` asks
  for it: expect NOT FOUND lines for `0x830113BB` etc. in the diag; harmless, P).
- Statics: 13BB 362 entries (type 7: 291, 21: 32, 3: 18, 10: 11, 16: 10), 12BB 17, 14BB 9 (format of
  `map-object-census.md` 0.1, re-parsed). Every type-7 / 10 world state is in a loaded pack (`0xA00002E5/E6/E7`, the
  resident packs). `0x2E001235` (10.3, 77.6) and `0x2E00132F` (11.6, 77.6) are **derived** world states
  (`did | 7 | base 0x2E000024 | 0 | 5`, pack `0xA00002E6`), not missing.
- Not installed anywhere (complete list for the three blocks):

| DID | Type | Position (x, y, z), yaw | Note |
|---|---|---|---|
| `0x2E0011A7` / `0x2E0011A6` | 3 | (17.5, 77.15, 200.1) -90 / (142.5, 77.75, 200.1) 90 | core markers |
| **`0x2E0011A9` / `0x2E0011A8`** | 3 | **(40.0, 77.5, 200.0) -90 / (120.0, 77.5, 200.0) 90** | dampener markers, centre of the black sockets |
| `0x2E0011AD` / `0x2E0011AC` | 3 | (65.0, 77.5, 200.0) -90 / (95.0, 77.5, 200.0) 90 | lane turret markers |
| `0x2E000AF9` / `0x2E000AF8` | 3 | (21.75, 77.5) -90 / (138.3, 77.5) 90 | lane mouths, prop `0x100002E6` team table |
| `0x2E00110F` x2, `0x2E001110` | 3 | (80.0, 77.5), (110.5, 78.5) 180, (80.0, 77.5) | emitters |
| `0x2E00111B` | 3 | (61.5, 77.5) | emitter |
| `0x2E001117`, `0x2E001120` | 3 | (79.96, 97.13) | nook |
| `0x2E001118`, `0x2E001121` | 3 | (48.75, 93.0), (80.0, 119.0) | emitters |
| `0x2E000944`, `0x2E000945` | 3 | (80.0, 97.25) 180 | nook |
| (none) | 16 | (5.0 / 6.0 / 7.0, 73.5-81.5) -90; (153-155, 73.5-81.5) 90 | start points |
| `0x2E000000` | 21 | 32 lane waypoints | world state not installed -> dropped by `0x54AF70` (expected) |

- Reference closure (every DID-looking word in the records reachable from the blocks, depth 8, prefixes
  0x08 / 0x13-0x1F / 0x2D / 0x2E; texture, shader and Havok bodies skipped): 1 809 records resolved; every remaining
  "absent" hit checked by hand was a byte pattern inside compressed vertex / table data, not a reference (P: the scan
  is heuristic; the runtime diag is the real test).

## 3. Terrain rendering data of a block (C, new)

The `0x80` record: `did | 0x441 | 1089 flag bytes | pad | 0x441 | 1089 u16 heights | 9 | palette 0x00, 0x09, 0x0A,
0x0E, 0x0F, 0x25, 0x26, 0x27, 0x28 | 12 batches | ... | far patches | 6144 u16 indices (at record +0x19D4) | ... |
0x441 | 1089 x 3 f32 normals (at record +0x81F8) | ...`. Vertex (x, y) = index `(x / 5) * 33 + y / 5` for heights,
normals and the render vertex buffer; the index buffer is sorted by batch.

Near batches of 13BB (`n | layer indices | first index | triangles | first vertex | vertices | bbox | mask | material |
uv floats`):

| Batch | Mask | Material | Layers (palette value) | Triangles | Area (x, y) |
|---|---|---|---|---|---|
| 0 | `0x13002742` | `0x14000209` | 0x26 | 656 | 2-83, 2-158 |
| 1 | `0x13002743` | `0x1400020A` | 0x0E, 0x26 | 126 | 72-158, 2-158 |
| 2 | `0x13002742` | `0x14000209` | 0x0E | 772 | 82-158, 2-158 |
| 3 | `0x13002E06` | `0x1400020A` | 0x25, 0x26 | 106 | 2-68, 12-98 |
| 4 | `0x13002E06` | `0x1400020A` | 0x0E, 0x0F | 142 | 82-158, 32-88 |
| 5 | `0x13002742` | `0x1400020E` | 0x09, 0x25, 0x26, 0x28 | 32 | 2-73, 37-93 |
| 6 | `0x13002E09` | `0x1400020E` | 0x25, 0x26, 0x27, 0x28 | 150 | 2-73, 42-98 |
| 7 | `0x13002E13` | `0x1400020E` | 0x0E, 0x25, 0x26, 0x27 | 16 | 72-88, 67-98 |
| 8 | `0x13002743` | `0x1400020E` | 0x09, 0x25, 0x26, 0x27 | 14 | 57-83, 82-93 |
| 9 | `0x13002F93` | `0x1400020E` | 0x09, 0x0E, 0x25, 0x26 | 2 | 77-78, 82-83 |
| 10 | `0x13002E09` | `0x1400020C` | 0x09, 0x0E, 0x0F | 30 | 77-108, 82-93 |
| 11 | `0x13002E06` | `0x1400020E` | 0x09, 0x0E, 0x26, 0x27 | 2 | 87-88, 92-93 |

Masks: 256 x 256 DXT1 in the map pack (R / G / B = layer weights). Materials `0x14000209` / `20A` / `20C` / `20E`:
pack `0xA0000037` (resident), 3 / 6 / 8 / 10 slots. Far LOD: 16 patches of 40 x 40 m, material `0x140002C5`
(`0xA00000B3`, resident), three textures each (`0x1300341E`-`0x1300344D`: 2048 x 2048 DXT1 colour, 1024 x 1024 DXT5,
1024 x 1024 DXT1), all in the map pack. Layer descriptors (type id -> textures) live in the region's terrain-type table
(region +0x64, hash at +0x20 / +0x2C, `0x4DB370`); its record was not located statically (the region pack
`0xA0000038` stores records unaligned), so the layer textures' DIDs come from the diag (O until then).

## 4. The sockets (C data, P reading)

| Site | Vertices | z | Normals stored | Batch(es) drawing the triangles with a low vertex | Seen black |
|---|---|---|---|---|---|
| dampener t1 | (40, 75), (40, 80) | 179.96 | tilted into the hole (0, 0.61, 0.80) / (0, -0.52, 0.86); rim (35, 75) (0.35, 0.15, 0.93) | 3 (7 tris), 6 (1) | yes |
| dampener t2 | (120, 75), (120, 80) | 179.96 | (-0.10, 0.61, 0.79) ... | 4 (9), 2 (1) | yes |
| lane turret t1 | (60-70, 70-80) + (75, 80) | 0 | flat (0, 0, 1) at (65, 75) | 6 (16), 7 (2), 8 (6) | no (earlier frames) |
| cores | (15-20, 75-80), (140-145, 75-80) | 0 | tilted (0.45, 0.71, 0.55) at (15, 75) | 0, 3, 6 / 2, 4 | no (pedestal statics on top) |
| south scenery | (85-90, 55-65) | 0 | - | 1, 2, 4 | outside the lane |

- Batches 3 and 4 also draw most of the lane's street on each side, and the masks read full weight at the socket
  texels (e.g. `0x13002E06` at x 40 (82, 165, 0) / (230, 20, 0) depending on orientation, never 0). So the
  materials, masks and layer textures of the socket triangles are the street's own: the black is the shape (two
  vertices 20 m down, 76-89 degree walls, normals tilted away from the light), not a missing asset (P strong).
- 180 m is the "covered" level: the whole off-lane terrain under the buildings sits there (407 vertices). The two
  lowered vertices per side, exactly under the type-3 markers `0x2E0011A9` / `0x2E0011A8`, say the designers expected
  something standing over (40 / 120, 77.5) to cover a 10 x 15 m footprint (P). No installed world state of that size
  exists in the map's packs (`crime-alley-structures.md` 3, C); the marker world states are not installed (C). So the
  original cover was either server-side content absent from this install or a different terrain build (O).
- The z = 0 sockets differ: the turret socket's normals are flat (0, 0, 1) (unlike the 180 m ones), and earlier frames
  show normal street there with only the 6.26 m plate on it; why a 200 m funnel does not show is O (P: far below the
  near plane / fog, or culled; the diag's fill experiment does not touch it).
- Tutorial 2's terrain (`0x800113C3`) has the same 179.96 m pair at (40, 75) / (40, 80).

## 5. Recipes

1. **Confirm nothing is missing at runtime** (no code change): `--mapload` on a Crime Alley match. Expected: no
   `MAP TERRAIN PROBLEM` line for block 13bb; `NOT FOUND` only for `0x83......` records, `0x2E000000` waypoints and
   `0x2E0011..` markers are not even asked (type 3 is never instantiated). Any other `NOT FOUND` with a caller in
   the landscape / statics is a real hole: report it with its DID.
2. **Flattening experiment** (`--mapload-fill`): raises the four socket vertices to 199.98 m (median of their
   neighbours) and recomputes the 3 x 3 normals around each, in the running client only, before the terrain meshes
   are built. If the octagons become street at x 40 and x 120, the cause is confirmed (C then).
3. **Permanent fix, if 2 works** (choose one; neither needs the server):
   - exe patch in `icserver/patcher.py`: a cave at the entry of `0x712860` (render, `[esp+4]` = terrain object) and
     `0x53BB00` (collision, `[esp+8]`) that, for an object whose height array (+0x3C, count +0x40 = 0x441) holds
     0x170A at index 279 / 280 / 807 / 808 with 0x1999 at index +/-33, writes 0x1999 there and (0, 0, 1) to the
     normals (+0xC4, 12 bytes each) of indices i*33+j for i in 7..9 / 23..25, j in 14..17; repeat for the LOD 1
     arrays (+0xE0 / +0x168) when their count is 0x441. Original-byte checks as the other patches; config switch
     `[patch] crime_alley_socket_fill` (default on, comment with the tester's report).
   - local pack patch (an `ic.py` command, never distributed): in the `0x800113BB` record of `0xA0C112BA` change the
     u16 at record +1104 + 2 * {279, 280, 807, 808} from 0x170A to 0x1999 and the normals at record +0x81F8 + 12 * idx
     (same 3 x 4 neighbourhoods) to (0, 0, 1); recompress the pack's stream (format in `ics/rp.py`). Same for Tutorial
     2's `0x800113C3` if it is ever used.
4. Server side: keep `match_socket_covers.crime_alley = []` (every cover tried was rejected); the dampener stays at
   (40 / 120, 77.5) with the marker yaws.
5. Other black shapes (`black-ground-shapes.md` 2.2): Gotham Divided's lane exits are 50 m deep (vertices at 200 m,
   street 250 m) and Coast City's centre is a 3 x 3 block at 0 m: same method, but `FILL_SPOTS` and the 15-25 m depth
   window in `diag.py` are Crime Alley's; extend them per map after the Crime Alley result.

## 6. Running the new diag

1. Open the game with `python ic.py play`, stay in the menu.
2. Second console: `python tools\diag.py --mapa` (add `--mapa-todo` for the full list of loaded records in
   `logs\mapload.tsv`, slower; add `--mapa-rellenar` for the flattening experiment).
3. Launch Crime Alley, walk to both dampeners (x 40 and x 120), take screenshots, Ctrl+C in the diag console.
4. Send `logs\diag.log` (and `logs\mapload.tsv` with `--mapa-todo`). Lines start with `MAP`; the summary at the end
   lists every failed DID with its count, caller and context.

Breakpoints (VA): resolver failures `0x43CF15`, pending `0x43CEB4`, every load `0x43CEE2` (`--mapload-all`);
blocks `0x53E290`, `0x714280`; statics `0x548645`, `0x54864E`, `0x548695`, `0x5486AB`; terrain batches `0x713C3C`,
`0x713CCC`, `0x713D3E`, `0x713852`, `0x7138BD`, `0x713928`, `0x713D97`, `0x713DB5`; fill `0x712860`, `0x53BB00`.
The three resolver breakpoints retire themselves after 50 000-300 000 hits so a long session does not crawl.

## 7. Open

- The region's terrain-type table record (layer id -> textures): read it from the diag's batch lines.
- Why the 0 m sockets (turret, cores) do not render black (section 4).
- What the original placed over (40 / 120, 77.5): the marker world states `0x2E0011A8` / `A9` are not in this install.
