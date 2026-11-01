# Movement / collision, fog of war, missing map statics (static analysis, 2026-10-21)

Read-only analysis of InfiniteCrisis.exe (sha256 463adfff..., Ghidra via REA + capstone, image base 0x400000; all
addresses are VA) and of the installed packs (`ics/gamedata.py`, `ics/rp.py`). C = confirmed in code/data,
P = probable (strong inference), O = open. Tester report: Tutorial 1 (encounter 0x40000991, map pack 0xA0C112CA,
spawn landblock 0x13CB), server `ics`.

---------------------------------------------------------------------------------------------------------------

## 1. Movement, pathing and collision

### 1.1 The 0xB0 movement block, corrected (C)
- Module part (0x57E410, flag 0x20 of the leading byte): `u8 seq | [seq != sentinel: u8 mode | (flag 0x01 of the
  leading byte) u64 controller IID]`. The u64 goes to P+8/P+0xC (0xB0FE50 reads 8 bytes) and ends in the movement
  component at **C+0x2C8/0x2CC**. Today the server sends `0x62` (bit 0 clear): no controller IID.
- Movement block (0x57E530, flag 0x40): `u8 subflags | [1: f64 time] | [8: Position (0x47C610)] else [2: vec3]
  [4: vec3, vec3] | u16 | (flag 0x02) motion bytes`. Motion: `u8 m (| 0x80 -> second u8)`; bits 1: 2 x u16,
  2: u16, 4: u32 (heading), 0x20: u32 (speed), 0x40: u32, 8: u16 (facing), 0x400: u16, 0x4000: u16,
  0x800: u8, 0x1000: u8, 0x2000: u8. **There is no destination, waypoint or path field** (C).

### 1.2 The movement-mode byte is a row of record 0x48000002 (C)
- 0x553E70 (C vtable path, called from the 0xB0 listeners 0x60AED0 / 0x60AFA0 with `(P+4 mode, P+8, P+0xC, P+0
  seq)`): if the seq is newer (u8 wrap compare) and the mode changed, calls C vtable +0x58 = **0x608FC0(mode,
  &controllerKey, &moduleKey)**, stores the IID at C+0x2C8, writes property 0x57A = mode on the entity, then
  0x553A40(controllerKey) and 0x553960(moduleKey) build the two objects.
- 0x608FC0 -> 0x5527E0: loads the movement-mode table (0x43A9E0(9, 0xF, 0x29, 1) = record **0x48000002**, pack
  0xA0000038), property **0x38B** = list of 0x57B structs `{0x273, 0x21E, 0x3E2, 0x57A = mode id, 0x4C}`; picks the
  row whose 0x57A = mode.
- **Local test C+0x4C = 0x608D20**: `C+0x2C8 == local player id` (0x635230 -> [0x1B6A710], set by event 0xEB through
  0x635250). Local: controller = row.0x21E, module = row.0x3E2. Remote: no controller, module = row.0x4C.
- Rows (`0x273 / 0x21E / 0x3E2 / mode / 0x4C`):

| mode | 0x273 | 0x21E (local controller) | 0x3E2 (local module) | 0x4C (remote module) |
|---|---|---|---|---|
| 1 | 3 | 3 | - | 1 |
| 2 | 3 | 1 | - | 1 |
| 0x42 | 0x1000000D | 0x10000004 | - | 1 |
| 0x50 | 0x1000000D | 0x1000000D | - | 1 |
| 0x43 | 0x1000000D | 0x10000003 | - | 1 |
| 0x4C | 0xA | - | - | 9 |
| 0x51 | 0x10000004 | - | - | 1 |
| 0x46 | 0x10000004 | - | 1 | 1 |
| 0x47 / 0x4F / 0x48 | 3 | 0x10000001 / 0x1000000C / 0x10000005 | - | 1 |
| 0x49 | 0x1000000D | - | - | 1 |
| 0x4A | 0x10000006 | - | 0x10000005 | 0x10000005 |
| 0x4B | 0x10000009 | 0x10000008 | 1 | 1 |
| 0x52 | 0x1000000E | - | 1 | 1 |
| 0x40 / 0x4E | 3 | 0x10000009 / 0x1000000B | 1 | 1 |
| 0x41 | 0xA | - | 9 | 9 |
| 0x4D | 0xA | - | 1 | 1 |

  0x273 is not read by the client (probably the server-side controller, P).
- Classes registered in the client (registry [0x1B67310], 0x553CA0; key -> CLSID -> factory -> object vtable):
  - map A (controllers, C+0x1C): **3 -> GotoActionModule** (factory 0x15B4010, ctor 0x5536D0, vtable 0x15B4240;
    event handler 0x5532A0: event 4 = steering from the Kynapse path follower 0x551070 into animation-graph
    variables (0x5518E0), event 0xC = root motion into the rigid body (0x5513B0)); 2 -> vtable 0x15C6028;
    0x10000004 -> vtable 0x15F95E8; 0x1000000D -> vtable 0x15F9680. Keys 1, 0x10000001/3/5/8/9/B/C have no client
    class (server-only controllers, P).
  - map B (modules, C+0x20): **1 -> vtable 0x15C6360** (ctor 0x60BC60, +0x68 = 0x60BB00), **9 -> vtable 0x15C62A8**
    (+0x68 = 0x60B0F0 -> 0x60A830 -> SetEntityFrame), 0x10000005 -> vtable 0x1609708 (ctor 0xAA0800). The name
    "ClientRigidBodyCharacterReplayMovementModule" is used by 0x60B5F0 (event 0xE handler, near both). Correction
    to `actor-creation-and-environment.md`: vtable 0x15C62A8 is module key 9, not 1 (C); what the wire mode 1 gives a
    remote entity is module key 1 (vtable 0x15C6360) (C).
- So today (mode 1, no IID): the champion is a remote entity replayed from the server's positions (C). Sending the
  local player id would turn it into GotoActionModule with **no replay module**: client-steered with Havok physics,
  but the client would then report its own state (event 0x00DA from 0x628BF0, P) and how the goal is given to the
  Kynapse bot is not traced (O). Not recommended as the first step.

### 1.3 Who paths (C / P)
- The client links Kynapse (Autodesk Gameware Navigation): "TurbineKynEntity" (vtable 0x15B4034, part of the
  movement component), PathFinder bot created by 0x554790 ("PathFinder::ComputePath" / "FollowPath") when property
  0x83C == 3 or the entity is not a static (0x554AD0), registered in the client's Kynapse world by 0x552C30. Its
  debug commands are labelled "kynapse - Server only" (0x185EBE8): **the original server pathed on the same
  navmesh** (P, strong).
- On a move click the client only snaps the point onto the navmesh: 0xA70030 -> 0x4FB400 -> 0x4FA870 (nearest
  navmesh point for the champion's agent class within 2.5 x 6 m, else the order is dropped), then sends 0x20EE
  (0x88B030). **No path or waypoint message exists** in either direction (C). The server must path and replay.

### 1.4 The navmesh data (C layout, P semantics)
Map pack 0xA0C112CA, records 0x900113CB / 0x901113CB / 0x902113CB (bodies start at data offsets 0xC3500, 0xC7B94,
0xD6984 of the unpacked pack; no DID inside: they follow the record-list order) and index 0x850113CB:
- `u32 1 | f32 radius | f32 height | u32 agent class | 0 | 0 | u32 blob size | "BlobAggFile" | 3 | "NavMesh" ...`
  - 0x900113CB: radius 0.525, height 2.1, class 0x10000003, blob 0x4678 bytes;
  - 0x901113CB: 1.1 / 2.1 / 0x10000002, 0x45AC; 0x902113CB: 2.1 / 4.0 / 0x10000001, 0x9EC.
- NavMesh header (offsets from "BlobAggFile" - 0x20): +0x4C 0x13 = number of NavCells, +0x74..+0x80 = cell box
  (x 0x97..0xA0, y 0x657..0x660, i.e. 10 x 10 cells), +0x84/+0x88 = 10 x 10, +0x8C f32 0.0015625 (integer
  precision), +0x90 = 100 (pixels per cell), +0xA0..+0xAC radius / height / 0.59 / 46.0 (step height / slope, P),
  then 19 `(size, offset)` pairs to the NavCell blobs. Cell index 151..160 / 1623..1632 = landblock x*8, y*8, so
  a cell is 1/8 landblock (20 m if a landblock is 160 m) and a pixel 0.2 m (P). NavCell blobs hold altitudes
  (f32, ~200.0 = the map's z) and packed u8/u16 vertex coordinates in 0..100 pixel units (bytes "QRdd" = 81, 82,
  100, 100) (P).
- Champions use agent class 0x10000003 (radius 0.525) (P: the smallest; Batman's capsule).

### 1.5 Recommendation (least work)
1. Parse the 0x900113CB NavMesh blob once at server start (new `ics/navmesh.py`), rasterise its floor polygons into
   a walkable grid (0.25 m cells) per map, and run A* + string pulling on the grid for every 0x20EE move (champion
   and drones). Keep sending the same 0xB0 replay updates (mode 1, remote), one segment at a time (heading +
   speed per segment). Fallback until the parser works: the old server's hand-authored obstacle polygons
   (`icserver` `[combat] obstacles`, `finale_obstacles`) rasterised into the same grid.
2. Snap targets that fall outside the grid to the nearest walkable cell (the client already snaps clicks to the
   navmesh, so most targets are valid).
3. Do not switch to the local mode (controller IID) until the 0xDA client-authority path is traced.

---------------------------------------------------------------------------------------------------------------

## 2. Fog of war

Component CFogOfWarComponent (vtable 0x16098E8; update +0x68 = **0xAB3520**). Its "owner" (vt +0x7C, 0xA9DE00 ->
0x85D620) = the entity named by **property 0x100000CF** (controlled agent) on the component's entity: the player
object -> the champion (C). The update runs when the owner has a valid position and the game state != 7 (C), then:
- 0xAB12C0 (every 0.4 s): for each candidate IID in +0x170 (count +0x178), checks entity flags +0x118, the filter
  vt +0x70 = 0xA9DE10, property **0x2A1** (bool, default true), alive (0x9CFAF0), vision radius vt +0x78 > 0, then
  subscribes to 0x100000FA (LifeState), 0x10000B2D, **0x1000009C (team)** and adds a vision source
  (**0xAB0C60**, 0x60-byte entries at +0x180, count +0x188; IID at +0x10, radius at +0x50) (C).
- Filter 0xA9DE10: the owner itself is always accepted; otherwise, if the owner has attribute 0x100007C0
  (entity+0x84 attribute component, 0x974940 -> 0x973730), the entity must have attribute 0x100006F3; without
  0x100007C0 every candidate passes (C).
- Radius 0xA0D0D0(owner, entity): relation 0x854A90 (same entity or same team = 4, either team 0 = 1, else 2; team
  = property **0x1000009C**, or the owner's via 0x8631A0) (C). Ally (4): **property 0x10000133** (f32, default -1)
  + attribute 0x10000642 (0x9CFCA0) (C). Not ally: property 0x100006F9 only if the entity has attribute 0x100006FC
  ("revealed", P). Gaslight Batman's world state 0x2E0001B2 carries 0x10000133 = 12.0 (C, pack 0xA0000076).
- 0xAADF70 refreshes the sources (drops entities that died, lost position, or whose radius became <= 0).
- Vision circles are drawn by 0xAAE0E0 (radius at entry+0x50, occluders at entry+0x4C list) (C).
- Draw 0xAAE5B0 ("RenderFogScene"): only when the fog texture exists and the current map info [0x1B758F4] is set
  (its +0x70 / +0x74 DIDs are two map textures, +0xAC.. its position) (C). **Darken flag = NOT
  attribute(champion, 0x100007C0)** (C): a champion without that attribute gets darkness. Per texel the base
  darkness is `1 - sample` of terrain layer **0x10000002** at that point (0x586140; layer id at +0x4C of the cell's
  layer list) (C code, P meaning). Finally the fog is composed only if world render bytes [[0x1B73518]+0xDC]+0x36
  and +0x39 are set (WorldRender.EnableFog / EnableMaskFog, P) (C).

What the server must send (P unless marked):
- On the player object: 0x100000CF = champion IID (already sent) and team 0x1000009C.
- On the champion and every ally that should see: the same team 0x1000009C (C requirement), LifeState 0x100000FA
  = 4, no 0x2A1 = false, and a sight radius: 0x10000133 comes from the class data (12 m for Batman), but send it
  explicitly in 0xBC (`0x10000133 f32`) to be safe; cameras / wards the same way.
- Never give the champion attribute 0x100007C0 (it turns darkening off).
- Enemies get no vision radius (relation 2 without 0x100006FC); the server keeps hiding enemy units out of sight
  with 0x90F (the client's fog only darkens the ground, it does not hide network objects by itself: no 0x90F
  writer was found in the fog code, P).
- The darkening also depends on the map info [0x1B758F4] being loaded (the fase3-cc patch path) and on the
  terrain layer 0x10000002; whether Tutorial 1's terrain has that layer is open (O). Next test: `tools/diag.py
  --fog` breakpoints at 0xAB0C60 (sources added?), 0xAAE5B0 (draw entered?) and the darken flag (0xAAE7C9).

---------------------------------------------------------------------------------------------------------------

## 3. Landblock statics and missing scenery

### 3.1 How the client creates them (C)
- Landblock object method 0x5483D0 -> **0x547B50** (only when the landblock has its data at +0x9C): first
  re-places mobility-2 entities of the block, then (load) walks the block's static list and calls
  **BlockEntities 0x53DA40** for each one whose class resolves (0x53BFD0); failures are dropped (0x5460F0).
- 0x53DA40: builds the desc (IID 0x4DB130 from the cell, parent for top byte 1 / 0x4DAF50 IDs, flag 0x10, class =
  the record's world state), creates it (factory +0x24). If the class cannot be built it logs "BlockEntities.cpp"
  line 0x20D with the world state and gives up. Then SetEntityFrame(entity, xyz + quaternion, 5); if that fails
  it logs "Couldn't place dynamic entity %s at %s" (0x15B25C8) or "...placed in a different block ... will be
  destroyed" (0x15B2490) and destroys it (vt +0x50(.., 3)).
- Which landblocks load (streaming radius, cells) was not traced (O); the map has 3 x 3 landblocks with terrain and
  statics in 0x13CB (857), 0x14CB (136), 0x13CA (3), 0x12CB (1).

### 3.2 Pack check of every static (data, C for the parse, P for the reference scan)
Statics of 0xA0C112CA: 997 parsed (types 7: 781, 2: 80, 3: 91, 10: 20, 21: 25). Packs sent today in 0x20AF:
0xA000024C, 0xA0000256, 0xA0000257, 0xA00002D6, 0xA00002D7 + champion packs; 0xA0000037 is always loaded (the
player class comes from it).
- Every world state of types 7 / 2 is in a sent pack (C); the 20 lights (0x2E000011) and 25 path nodes
  (0x2E000000) are only in 0xA0000037 (C).
- **91 type-3 emitters**: their 44 world states are in no installed pack (C): they can never load.
- **17 placements of 0x2E0005D6** (street, bridge and base: (47.3, 59.6), (42.5, 43.8), (29.6, 64.4) ... (157.9,
  29.5)) use .entity **0x2D0002E4, which exists only in 0xA00000B3** (C): these are certainly missing today.
- A scan of the DIDs each world state / .entity references (textures 0x13, 0x14, 0x16, meshes 0x17, 0x18, 0x19,
  0x1C, 0x1D, 0x2D, 0x2E) finds **76 world states / 295 placements** that reference DIDs not in any sent pack (P:
  the scan reads every u32 that matches an existing DID). Covering packs (greedy, number of missing DIDs, size):
  0xA000009A (Gotham Heights zone, 108, 134 MB), 0xA00000FC (Gotham Divided zone, 17, 158 MB), **0xA00000DF**
  (category 21, 13, 20 MB), 0xA00000D2 (Coast City zone, 9, 154 MB), **0xA00000B3** (category 20, 8, 30 MB),
  0xA0000116 (3, 3 MB), 0xA0000073 (1), 0xA000022E (1). Largest users: 0x2E001219 (35 placements, needs
  0xA00000FC), 0x2E0002D0 (20, 0xA00000DF), 0x2E0005D6 (17, 0xA000009A + 0xA00000B3), 0x2E00121A (16,
  0xA00000FC), 0x2E000247 (13, 0xA00000B3), the statics 0x2E000375 (10, 0xA000009A; a roof, not a crater: fase3-gg), the bank holes
  0x2E001144-46 (8 each, 0xA00000B3 + 0xA00000DF).

### 3.3 Recommendation
- Add **0xA00000B3** and **0xA00000DF** (shared packs, categories 20 / 21, 50 MB) to the 0x20AF list (new config
  key with the list of extra packs). They are already known to be needed (unit scriptlet tables 0x1D0000E1/E2/E8,
  the shockwave rig).
- Then test adding 0xA00000FC and 0xA000009A (big zone packs) one at a time to see whether the remaining scenery
  (the 35 + 16 placements of 0x2E001219 / 0x2E00121A, craters, street props) appears; the original server's pack
  list for this encounter is unknown (O), so the minimal set must be found by testing.
- Nothing can be done for the 91 emitters (their world states are not installed).
