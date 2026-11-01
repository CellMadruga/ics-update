# How the client loads and runs a map, end to end (decompilation survey, 2026-10-22)

Goal: load every map with all its elements, rules and gameplay, then rebuild PvP. This note follows a map from the
match-entry message to a running match, from the full Ghidra decompilation of InfiniteCrisis.exe
(`re-work/decomp`, VAs, image base 0x400000) plus REA xrefs. It builds on, and does not repeat in full:
`maps-complete.md` (the data of the six maps: packs, statics, start points, lanes, classes, proposed placements),
`movement-collision-fog-map.md` (movement block, navmesh, fog component, BlockEntities),
`actor-creation-and-environment.md` (cinematic actors vs network objects, why props were invisible),
`install-inventory.md`, `client-movement.md`, `master-plan.md`.

**C** = read in the code (or the data); **P** = probable (strong inference); **G** = guess; **O** = open.
Only IDs, short names, numbers and addresses are recorded.

---------------------------------------------------------------------------------------------------------------

## 0. The short version

| Layer | Who does it | Server's part |
|---|---|---|
| Packs (terrain, statics, navmesh, zone / layout / variants, environment records) | client, from the list the server names in **0x20AF** | name every pack (section 1) |
| Encounter-level setup (ruleset, map pack, minimap, shop, music, announcer) | client, from the encounter template, triggered by 0x20AF and by **0x100001D3 on the player object** | send both (sections 1, 7) |
| Landblocks: terrain, water, impassable border, render meshes, lights, scenery entities, waypoints | client, from the map pack's 0x80 / 0x81 / 0x82 / 0x85 / 0x90 records, **filtered by the encounter's ruleset** | send a valid Position (region 1, landblock, cell) for the player and every object (section 2) |
| Environment (sky, key light, fog colours, time of day) and ambient audio | client, from region record 0x01000000 + env records 0x08...... + world-state sound lists | name the packs that hold the env records; optional 0x956 lighting override (section 5) |
| Gameplay objects (structures, capture points, Doomsday Device, pickups, wards, minions, jungle, bots) | **server only**: none is a client static; the client only draws what it is sent | create, place (0xB0 with module), give properties, vitals, scriptlets, notices (sections 3, 4, 8) |
| Navigation and collision for units | **server** (the original server ran Kynapse on the same 0x90 navmeshes) | path on the fixed navmesh, block structures dynamically (section 6) |
| Fog of war | client darkens the ground; **server hides enemies** (0x2A1 / 0x90F) | team + sight radius on allies; visibility filtering (section 7.3) |
| Minimap image and entity icons | client, from the minimap record and per-entity 0x100004DA | properties on entities; 0x20D2 for sites without an entity (section 7) |
| Rules, win, score, timers, waves, AI | **server only** (the client reads none of 0x1000021D, 0x10000BB7, 0x1000021C, 0x100004A1: no reader in the exe, C by absence) | everything (section 8) |

---------------------------------------------------------------------------------------------------------------

## 1. Match entry: pack selection and load order (C unless marked)

1. **0x20AF** (handler **0xA99F00**; wire `u8 0 | u32 | list<u32> | list<u32> | u32`):
   stores the u32 at [0x1B763C0]+0x74, copies the two lists (0xADB230, a plain array copy), stores the last u32
   (encounter DID) at +0xC4, sets [0x1B77068]+0x4CB = 1 and flag bit 2 of +0x70; when the other two gates
   ([0x1B77068]+0x4CA / +0x4C8 clear) hold it sets bit 4 and runs **0xA99E20**.
2. **0xA99E20** (once: flags & 7 == 7 and bit 8 clear): 0xA960E0 resets the world (entity factory +0x54 clears
   objects, 0x742120 / 0x740BB0, landscape 0x7E27C0); 0x8535D0(encounter) loads the encounter template;
   - **0x1000028A (ruleset enum)** -> **[[0x1B73518]+0xA4]+0x24** (read back by 0x634CC0); this is the value the
     landblock statics are filtered with (section 2.4);
   - **0x10000406 (map pack)** -> [0x1B763C0]+0xA0;
   - **0xA99370 `gmConnectionManager::LoadParentRPs`**: for each DID of the list at +0xA4 (count +0xAC) the pack
     that holds it is looked up (0x866480, hash DID -> pack index) and de-duplicated, then 0xA09E50 queues the
     loads (callback LAB_0xA99EF0 when done). Earlier notes: the client loads **exactly** the packs the server
     names plus the packs of the named DIDs; it does not derive a map's pack list from the map pack.
3. When the packs are in, the client reports progress (0x20D5 -> lobby 0x2031) and **0xCC level loaded**
   (0xA097A0). Then the server creates the player object and the world (protocol notes).
4. **Property 0x100001D3** (encounter DID) on the player object starts the map-level managers (section 7.1): the
   MapManager (minimap, fog textures), the shop (0xA908F0 reads 0x1000081E), HUD resets (0xA4C570 / 0xA567F0),
   and 0xA80CD0 sends the empty client event **0x201A** (0x886CB0) (C; what the server should answer: O, the old
   server ignores it).
5. Landblocks load when something needs them (section 2.2); network objects that arrive for a landblock not yet
   loaded are queued per landblock (0x64D8A0 -> **0x64C310**, hash keyed by the landblock) and created when it is.

**Packs to name per map** (data from `maps-complete.md` 2.1 / 6, environment records from the env survey):

| Map | Map pack (0x10000406) | Its own list | Add (P) | Env record pack (0x08......) |
|---|---|---|---|---|
| Tutorial 1 | 0xA0C112CA | 0xA000024C, 0xA0000256, 0xA0000257, 0xA00002D6, 0xA00002D7 | 0xA00000B3, 0xA00000DF, 0xA000009A, 0xA00000D2 | 0xA000024C (0x08000003 / 0x08000016) |
| Tutorial 2 | 0xA0C112C2 | 0xA00002E5, 0xA00002E6, 0xA00002E7 | 0xA00000B3, 0xA00000DF, 0xA000009A, 0xA00000D2 | 0xA00002E5 (0x08000003 via key 0x10000002; map-loading-deep-scan.md) |
| Crime Alley (v AI, 1vAI tutorial, Clash) | 0xA0C112BA | 0xA00002E5, 0xA00002E6, 0xA00002E7 | 0xA00000B3, 0xA00000DF, 0xA000009A, 0xA00000D2 | 0xA00002E5: 0x08000003 via 0x956 = 0x10000002 (C, map-loading-deep-scan.md; fase3-hp) |
| Gotham Heights | 0xA0C11AF2 | 0xA000009A, 0xA000016B, 0xA0000179 | 0xA00000B3, 0xA00000DF, 0xA0000161 (ring table) | 0xA000009A / 0xA000016B (0x08000006-0A) |
| Gotham Divided | 0xA0C11AD2 | 0xA0000168, 0xA00000FC, 0xA000016E | 0xA00000B3, 0xA00000DF | 0xA00000FC (0x08000014 / 1C) |
| Coast City | 0xA0C122E2 | 0xA00000D2, 0xA0000161, 0xA0000162 | 0xA00000B3, 0xA00000DF, 0xA000009A | 0xA00000D2 (0x0800000B ...) |

Always loaded by the exe: the core packs (0xA0000037 / 38 / 39 ...; region record 0x01000000 is in 0xA0000038).
Plus every champion's model pack (the server already appends them).

---------------------------------------------------------------------------------------------------------------

## 2. Region, landblocks, terrain, statics

### 2.1 Addressing (C)
- **Position** (reader **0x47C610**): flags byte; bit 1 region (bit 0x40 = implicit region 1, else a u8) -> +4;
  bit 2 landblock x, y (u8, u8) -> +8 / +9; bit 4 u16 -> +0xC (block **instance**, P from the teleport command's
  "instance number"); bit 8 u16 cell -> +0xA (bit 0x80 = special cell); bit 0x10 the frame (xyz + rotation).
- **DID of a landblock record** (**0x50BE20**(dbType, position, &did)): `prefix | region << 16 | lbx << 8 | lby`
  (needs region != 0, lbx / lby != 0xFF, cell != invalid). Region is always **1** on every installed map:
  0x800113CB = terrain of block (0x13, 0xCB). DB types: **0x0E = 0x80 terrain**, **0x24 = 0x81 landblock info**,
  **0x23 = 0x82 statics**, **0x0C = 0x85 nav index**, **0x3B = 0x90 / 0x91 / 0x92 navmeshes** (one per agent
  class), 0x21 = 0x83 property collection (none installed).
- **Region**: 0x50C8B0(regionId) caches region objects; record DB type **0x46 = 0x01000000** (one region, pack
  0xA0000038, unpack 0x50C350). Accessors 0x50CAA0 (bounds / size, used by the debug teleport 0x47DEE0),
  0x50CAF0 (+0x48 environment table), 0x50CB10, 0x50CB30. A landblock is 160 m; a navmesh cell 1/8 landblock.

### 2.2 Landblock load (C structure; streaming radius O)
- Block manager (vtable around 0x15C21E0..0x15C22C0): **0x548F30** creates the block object through its factory
  (+0x90 = **0x5EC3E0**, size 0xE0, ctor 0x5EC240, client-landblock vtable **0x15C2340**), stamps the time, runs
  the block's init and registers it with the scene [0x1BA1288].
- Client landblock init (**0x5EC890**, vtable +0x54) -> **0x549510**:
  1. location -> terrain record 0x80 (DB 0x0E); missing -> "Failed to load LandBlockData for %s";
  2. terrain +0x1B0 = the **statics record 0x82** DID (DB 0x23); missing -> "Could not load LBI for block";
  3. property bags: +0x94 (0x5921E0, from the landblock info) and +0x90 (0x592130: region + the statics record's
     own bag 0x58FEE0) - the position-qualified environment properties (section 5);
  4. if the block is active (+0x28 == 1): 0x981 option, then **0x85 nav index** (0x50BE20(0xC)) -> 0x64E740
     (Kynapse world; 0x4FA020 loads the 0x90 navmesh per agent class via 0x4F9DE0 / 0x4F9F30);
  5. 0x586B00 (terrain physics / heights, DB 0x0E again), **0x53E290** (LandBlockMesh: terrain mesh of the
     block and, when 0x53D9B0 finds the 0x81 record, the second LOD / colour mesh);
  6. 0x546860 + **0x549330** build the block's static-object set: **0x548550** walks the 0x82 entries (0x70 bytes
     each, list at +0x50, count +0x58) and registers types **7, 8, 0x15 (21)** as block entities (0x544A50:
     reads 0x24E / 0x55C lists and the ruleset filter 0x53B4F0); later **0x547B50 / BlockEntities 0x53DA40**
     creates them as entities (IID from the cell 0x4DB130, parent = the landblock, flag 0x10, SetEntityFrame).
  7. then (+0xA0 == 1) **0x5EC4F0** creates the render-only objects: entries of type **2** (single mesh,
     0x6E06F0, 0x120 bytes) and type **10** (point light, 0x5F0F30, 0x140 bytes), each also behind the ruleset
     filter, and 0x5EAEC0 (P: commit to the scene).
- Per-block extras (**0x53F8A0**, via 0x5EB7B0): if terrain +0x1CC is set, a **water entity** (world state
  terrain +0x1C8, height +0x1C0, flag 0x10, mode 2, SetEntityFrame); unless +0x1CD is set, an **impassable border
  entity** (class from 0x439E00(8, 0xF), checked against the block's height range +0xD0 / +0xD4: "Impassable
  Error: Min and max height ...") (C). These are client-only collision / visuals.
- Terrain record layout pieces read elsewhere (C offsets, P meaning): +0x3C a 33 x 33 u16 height grid
  (x 2000 x scale), +0x1A4 a 17 x 17 table of surface DIDs used by the frill (grass / decal) engine 0x548920.
- **Which blocks load** (O): blocks are created on demand by the block manager (entity placement, the local
  player's position); a world preloader method **0x7DEBD0** (vtable slot 0x15E5AF0) preloads the 0x80 / 0x81 /
  0x83 records of the target block, or of three block lists (+0x70 / +0x80 / +0x90, P: rings by distance). The
  draw distance is the console setting `Render.LandscapeDrawDistance`. On all six maps every gameplay position
  lies in the spawn landblock; the eight neighbours hold only scenery (C, maps-complete 0 #5), so placing the
  player there and letting the client stream is enough.

### 2.3 What each static type becomes (C for the dispatch; type meanings from maps-complete 2.2)
| Type | Client path | Result |
|---|---|---|
| 2 single mesh | 0x5EC4F0 -> 0x6E06F0 | render object, no entity, no collision entity |
| 10 point light | 0x5EC4F0 -> 0x5F0F30 | render light |
| 7 scenery / objects, 8 | 0x548550 -> 0x544A50 -> BlockEntities 0x53DA40 | client entity (IID top byte 1), Havok collision from its world state, scriptlets of its world state |
| 21 waypoint (0x2E000000) | same path as 7 | invisible client entity (P: kept for the server's AI; the client never paths with them) |
| 3 emitter / marker | no handler in these loops (P) | nothing, or its world state's own emitters; 44+ of these world states are not installed anyway |
| 16 start point | no handler (P) | server data only |

### 2.4 Ruleset filter (C path, P semantics)
Property **0x55B** on a static (array of ruleset enum values) is tested by **0x53B4F0 -> 0x53A490** against the
encounter's 0x1000028A (stored by 0xA99E20). A static whose list does not contain the current ruleset is not
created (also in the render-batch builders 0x63BC10 / 0x63F7C0). So the client itself shows the right core
pedestal on Crime Alley (`[9, C]` normal / Clash vs `[B]` 1vAI tutorial; maps-complete 0 #3): **the server must not
spawn its own pedestal**, only the core entity on it.

### 2.5 Pending objects
0x64D8A0 (network create) checks whether the object's landblock is loaded; if not, 0x64C310 queues the creation
(per-landblock hash, 0x64AC30) and it runs when the block arrives (C code, P effect). Objects with an invalid
landblock never appear (needs region != 0, lb != 0xFF, cell valid: 0xFB works, maps-complete / fase3-fw).

---------------------------------------------------------------------------------------------------------------

## 3. Static scenery vs network objects (what the client places vs what the server must create)

- **Client places by itself**: every 0x82 entry of types 2 / 7 / 8 / 10 / 21 of every loaded landblock, after the
  ruleset filter; the per-block water and impassable entities; cinematic actors (0x20F5); local ping entities.
- **Server must create**: every layout placement (0x1D records of the layout pack, units of the variants pack),
  every structure, capture point, relay, device, pickup, ward, jungle creature, minion, bot, champion, and any
  prop the original created at runtime (doors, vehicles). Classes: entity 0x40... (its 0x510 world state) or a bare
  world state 0x2E... (needs 0x50F = 8 to get a movement component, see actor-creation-and-environment.md).
- Creation recipe for anything the server places (C from earlier notes): batch 0x4 to the object IID with 0xF2
  (class, parent IID may be 0), 0xBC property table, **0xB0 with the module part** (`0x62 | seq 1 | type 1`, f64
  time, Position, u16, motion bytes) so the movement component's module calls SetEntityFrame 0x588290; then 0x42
  vitals, scriptlets 0x2050 / 0x2056.
- The PvP layout packs carry **no** structure placements (only cinematic actors and unit / prop classes):
  structure positions come from the statics markers and the cinematics (maps-complete 4).

---------------------------------------------------------------------------------------------------------------

## 4. Gameplay objects and their components (client side; full table in section 8 per map)

The client has **no gameplay logic** for structures, capture points, the Doomsday Device or pickups, and no
"capture / pick up / use" message exists client -> server (a click is 0x20EE) (C). Everything it shows comes from
properties, vitals (0x42), scriptlets and a few notices:

| Property | Client use (reader) |
|---|---|
| 0x1000009C team | relation (0x853380 / 0x854A90: same 4, either 0 -> 1, else 2), team colour scriptlet 0x100003A6, fog, tracker |
| 0x1000019D PerceivedType bits | Character 8, Loot 4, Turret 0x10, Inhibitor (dampener) 0x800, Destructible 0x1000, Base 0x4000, Minion 0x10000, Device 0x20000, Doomsday 0x40000, CapturePoint 0x80000; attackable = & 0x555959 (capture points never) |
| 0x100000FA LifeState | 4 = alive: needed for notes, targeting, team ring (0x100001FF via 0x1000072C) |
| 0x1000022F damage stages | client runs the stage scriptlet when health falls below each fraction (0x96E6A0) |
| 0x10000456 | capture owner team: on change scriptlet 0x100003A7 `_CapturePoint_OnTeamBiasChanged` (0xA79410) (P meaning) |
| 0x100004DA / 0x10000083 | minimap / tracker category and icon (section 7.2) |
| 0x100007D8 / 0x10000A95 | objective tracker entry (0xA4B150) |
| 0x10000133 | fog sight radius of allied entities |
| 0x100005A6 / 0x100007D5 | overhead billboard / usable-target marker (0xAA00D0) |

Client-derived for free: team colours, minimap icons with health, turret "under attack" pings (0xA0D860, allied
turrets, 3 s), damage-stage FX, turret warning ring (0xA84FB0, scriptlet 0x1000103D), spectator turret / dampener
counts. Server-ordered scriptlets found in the tables: turret hits / events, relays 0x10000AED-AF5 / 0x10000B1E,
capture BeingCaptured 0x1000032F / Captured 0x100002A9 / Lost 0x100002A8, Doomsday 0x10001096 / 0x10001097,
surveillance 0x10001053 / 0x1000107F, pickup 0x1000023A, spawners 0x10000B16-B19. HUD notices: team health
0x100004FB / 0x10000134 (answer to client 0x10000137), match time 0x10000109, match end 0x1000000E, banners
0x100002AF / 0x100002B1 / 0x10000424, billboards 0x100002EB, announcer 0x2039, objectives 0x2034 / 0x2009 / 0x2023
/ 0x2075 / tracker 0x2069. The match variables of 0x3A000029 are server-script variables (no HUD reader, P).
Capture progress: probably a vital of type 3 (CaptureBuffer) in 0x42, or 0x100006B6 (O).

---------------------------------------------------------------------------------------------------------------

## 5. Environment, lighting, sky, time of day, audio (client-driven)

- Each frame **0x7F3390** -> **0x7E6280(camera position)** re-reads the position's environment properties (every
  2.5 s or on region / block / cell change) through 0x58C2D0: block bag +0x94, then +0x90, else region. Read:
  0x386, 0x6DB, 0x425, 0x2D6 (default 1000), 0x47D (default 2000) (P: fog colour / near / far) and the **lighting
  key**: local player **0x956**, else 0x5CC, else 0x216 (player), else block / region 0x216, default 2 (C).
- **0x7F2AA0 -> 0x7EF240** (`EWorldRender__UpdateWorldLighting`): env DID = 0x5A3570(region +0x48 table, override
  0x28D, key) -> record **prefix 0x08 (DB 0x2E)** = the sky / environment description (P strong; db-types.md calls
  it "lens flare"), cross-faded over its +0x40 seconds (default 8 s). Evaluated by time of day: sky objects
  0x7ED100, key light 0x64F050, distance fog 0x64E4E0 (far 10000 default), ambient / sun colours 0x6509A0.
- **Time of day**: local GameTime [0x1B58ABC] (0x4C5B00, calendar 0xF7000000), ticks by itself, raises 0x28D /
  0x75A; console-only setters; **no network path** (P). **No weather system** (no strings / classes; P).
- Render switches (EnableFog / EnableMaskFog [[0x1B73518]+0xDC]+0x38 / +0x39 ..., ctor 0x7F1310): local settings.
- **Audio**: world-state sound lists 0x7A3 / 0x5E5 start the map's emitters (entity setup 0x61B540) once their
  packs are in; map music: **CEncounterEnvironmentSystem 0xA8F890** reads template 0x10000ADC (music record; Wwise
  hash 0x10000AD8; tutorials 0x48000F0A, Crime Alley 0x4800128C, GD 0x48000E6B; **GH and CC have none**) and the
  rule record (0x100009D2 lists) that drives adaptive cues from per-team counters (needs team + LifeState on
  entities). Announcer / VO sets from 0x10000802 / 0x10000803 / 0x10000B21 (0xA35DC0); lines play only on server
  triggers (0x2039, conversations). Lobby music pack 0x10000897 (0xA000018A / 189 GH / 188 CC).
- **Server's part**: name the env-record packs (table in section 1); valid Positions; optionally **0x956** on the
  player object where a server-run script would execute node 0x1000009C (cinematic / victory lighting; 0 to
  clear); team / LifeState for the music cues.

---------------------------------------------------------------------------------------------------------------

## 6. Physics, collision, navmesh

- Client collision = Havok rigid bodies of the client statics (world-state physics), terrain, per-block impassable
  borders and water (0x53F8A0). Server-driven entities are **replayed** (movement module key 1, see
  movement-collision-fog-map.md 1.2): client collision never moves them, so it does not matter for gameplay (C
  for the module, P for the effect).
- **Navmesh**: the client loads the 0x85 index and the 0x90 / 0x91 / 0x92 blobs per active block (0x549510 step 4)
  and uses them only to snap move clicks (0xA70030 -> 0x4FB400 -> 0x4FA870, agent class of the champion) and for
  its local Kynapse bots (GotoActionModule, unused while the champion is remote). **No path message exists**: the
  server paths (C). Kynapse debug commands are labelled "Server only": the original server pathed on the same
  meshes (P strong).
- Server rules (data, maps-complete 2.3 / 2.4): use agent class 0x10000003 (0.525 m) for champions / minions,
  0x10000002 (1.1 m) for big units / structure clearance; apply the two `ics/navmesh.py` fixes (cell count at
  blob +0x98, big-endian blobs on Gotham Divided); structures are **not** cut out of the mesh: block their
  footprint dynamically (NavGrid.block) when spawned and unblock on destruction.

---------------------------------------------------------------------------------------------------------------

## 7. Minimap, map notes, fog of war

### 7.1 Map load trigger (C)
MapManager = **[0x1B758F4]** (the "map info" the fog draw tests). Its listener **0xA6A8E0** on the local player:
`0x100001D3` -> **0xA4C2C0 LoadMap**: encounter 0x40... -> twin template 0x49... (DB 0x29) -> **0x10000287**
(minimap record) -> 0xA28D50 fills MM+0x68.. -> 0xA22A60 -> **0x89F4C0 DeliverMapData**(image) to Flash; if the
encounter flag [0x1B77138]+0xAC is set, 0xA4C090 adds the local home note.

### 7.2 Minimap record and entity notes (C; values read from the packs)
- Minimap record: 0x10000363 image (MM+0x70), 0x1000063C second texture (+0x74), 0x1000009F = 1.6 px / m,
  0x100001CA / 0x1000009E / 0x100000C8 = region 1 + the **spawn landblock**, 0x100002A8 / 0x10000015 = 256 x 256 px,
  0x1000087D diamond flag (Tutorial 1, GD; P). Records: Tut 1 0x48000D3E, Tut 2 0x48000E37, Crime Alley
  0x48000E36, GH 0x4800014C, GD 0x4800067C, CC 0x48000563. The server sends nothing for the image.
- Entity notes are client-local (0xA5B190 -> 0xA4BD80): an entity with **0x100004DA** != 0 / != 0x1D, **0x2A1**
  true and alive (LifeState 4, not 0x10000B2D) gets an icon (0x10000083, or table 0x1000059B by 0x10000587),
  decoration 0x10000548, team colour. Categories: 2 champion, 3 TURRET, 5 HEALTH_PICKUP, 6 BASE, 7 agent,
  8 CAPTURE_POINT, 9 MINION, 12 STORMSHIELD, 13 SPEED, 15 GENERIC_PICKUP, 16 CAMERA, 23 STATIC, 26 / 27
  capturable, 28 LARGE_MAPOBJECTIVE, 29 BEACON, 30 POWERCORE, 31 DEVICE.
- Server events (handlers C): **0x20D2** `u64 IID | Position | u32 icon` = static note (category 0x17) for a site
  with no entity; **0x2137** = ping echo of client 0x2136 (`u64 pinger | f32 x, f32 y, u64 target, u32 type`);
  **0x218A / 0x2189** start / stop the teleport effect on a note; **0x2179** a minimap polyline (pixel pairs +
  colour flag; 0x7EC = its RGBA colour, not a fog rect); 0x2069 tracker status. Corrections to
  `protocol-complete.md`: 0x2006 / 0x200E are handle-tracked effects (P), 0x209F / 0x217F / 0x2180 belong to the
  skill HUD, 0x20DA is unrelated to maps (P).

### 7.3 Fog (C; complements movement-collision-fog-map.md 2)
The draw 0xAAE5B0 needs MM and its two textures (both from the minimap record, i.e. from 0x100001D3) and the
terrain layer 0x10000002. Sources: allied entities with 0x10000133 > 0, team 0x1000009C, 0x2A1 true, alive. The
client fog never hides network objects: the server must stop sending / mark hidden (0x2A1 false also removes the
minimap note) enemies outside its allies' sight. Never give a champion attribute 0x100007C0.

---------------------------------------------------------------------------------------------------------------

## 8. Per map: what the server must spawn and send

Common to every map (C requirements unless marked):
1. 0x20AF with the encounter DID and the full pack list of section 1; answer the loading flow (0x2031 / 0x206D);
   wait for 0xCC before creating units.
2. Player object: **0x100001D3** = encounter DID, team 0x1000009C, 0x100000CF = champion IID; champion with a
   Position in the spawn landblock (region 1, cell valid), LifeState 4, 0x10000133 sight.
3. Do **not** create anything the statics already place (pedestals, lane-mouth markers, scenery, lights, path
   nodes, sound emitters): the client does it, filtered by the ruleset.
4. Every server object: class, 0xBC (team, side 0x100007A2, LifeState 4, 0x100004DA / 0x10000083 if the class lacks
   them, scale 0x6B3 / 0x6B4 where the placement has it), 0xB0 with module, 0x42 vitals; block its navmesh
   footprint if it is a structure.
5. Intro line-up cinematic (13.0 s, script 0x340006F2) with 0x20F5 at match start (P), end cinematic of the losing
   core's team at match end (P which), then 0x1000000E / billboard / scorecard.
6. Visibility: allies see by sight radius; hide enemy units out of sight (server).

Positions below are (x, y) in the spawn landblock, from `maps-complete.md` (C = in the data, P / G = derived
there; see its section 4 for the derivations).

### 8.1 Tutorial 1 (0x40000991, map pack 0xA0C112CA, LB 0x13CB, ruleset 9) - implemented
Start point (18.5, 59.9, 200.0) (C). Server content: the layout pack 0xA0000256 placements (drones, thugs, doors
0x40000B0F, power core 0x40000C90, vehicles via carrier / 0x50F) and the variants 0xA0000257; objective list
0x48000D3F, conversations 0x40000CB7, cinematics 0x35000026 / 0x35000034; scripts in the 0x1D layout records
(0x3400058A, 0x34000591, 0x34000595, 0x34000700). Environment 0x08000003 / 0x08000016 (0xA000024C); music
0x48000F0A; minimap 0x48000D3E. Remaining map gaps: packs 0xA00000B3 / 0xA00000DF (+ zone packs) for missing
scenery; 44 type-3 world states not installed (unfixable).

### 8.2 Tutorial 2 (0x40000A81, 0xA0C112C2, LB 0x13C3)
- Start (5.0, 77.5, 200.3) (C). Client statics give the pedestal (17.5, 77.5), socket (40, 77.5), lane mouths,
  markers (C).
- Spawn (P): team 1 core on the pedestal (17.5, 77.5) (class from the Crime Alley tutorial family 0x40000C90 /
  C8A), friendly turret at (25.1, 77.5) (`01TurretFriendlyHead` 0x2E000AA8 / turret 0x2E000AA0), enemy turret at
  (75.0, 77.5) side 1, Foundry 0x2E001037 at (1.3, 77.1, 201.8) side 3, base gate (0.0, 68.3), spawners
  0x2E000D03 at (22.3, 77.2) team 1 and (71.8, 77.5) side 1, drone waves (melee 0x2E001167 / ranged 0x2E001168 /
  siege 0x2E000E21) on the lane waypoints y = 77.5 (C positions from the cinematics).
- Objectives 0x48000E3B (29, scripts 0x34000601-604), conversations 0x40000CBC; cinematics 0x35000029-0x35000032;
  minimap 0x48000E37; music 0x48000F0A; env record: none in its packs (O).

### 8.3 Crime Alley (0x40000C82 v AI, 0x40000CA6 1vAI tutorial, 0x40000E68 / E74 Clash; 0xA0C112BA, LB 0x13BB; 1 lane)
| Object | Team 1 | Team 2 | Class (Clash / tutorial-vAI family) | Conf. |
|---|---|---|---|---|
| Player starts | (5.0, 77.5) + 4 slots | (155.0, 77.5) + 4 | - | C pos |
| Power core (on the client pedestal) | (17.5, 77.5) yaw 90 | (142.5, 77.5) yaw -90 | 0x40000C96 / C8A; 0x40000C98 / C89 (1vAI: side 1) | C |
| Inner structure (dampener) | (40.0, 77.5) | (120.0, 77.5) | 0x40000C91 / C88; 0x40000C95 / C87 | C pos, P role |
| Outer turret | (65.0, 77.5) | (95.0, 77.5) | 0x40000C92 / C8C; 0x40000C93 / C86 | C pos, P class |
| Core turret | (25.5, 77.5) | (134.5, 77.5) | 0x40000C8F / C94; 0x40000C97 | G |
| Foundry | (1.3, 77.1, 201.8) | (158.7, 77.1, 201.8) | 0x40000170 / 0x4000016F | G |
| Wave spawn | (21.8, 77.5) | (138.2, 77.5) | minions 0xA00002E7 (Soldier / Trooper / Cannon sets) | P |
| Jungle camp | (80.0, 95.5) loop | shared | Tripod / Raider / Regen Destroyer (0xA00002E7) | P |
Rules: core destruction (damage stages 0x1000022F); Clash tickets 0x10000463 200 / 300 (G meaning); 1vAI tutorial:
script 0x34000628 + objectives 0x48001150 + opponent 0x40000CBD (pack 0xA0000116, G). Cinematics: intro
0x3500003C, ends 0x3500003A (team 2) / 0x3500003B (team 1), 0x3500002F / 38 / 39 tutorial. Minimap 0x48000E36;
music 0x4800128C; announcer 0x40000D4C. Env record: none in its packs (O).

### 8.4 Gotham Heights (0x4000013E, 0x40000B6C v AI; 0xA0C11AF2, LB 0x1BF3; domination)
| Object | Position | Class | Conf. |
|---|---|---|---|
| Player starts | team 1 (6.0, 47.0) + 4; team 2 (154.0, 47.0) + 4 | - | C pos |
| Capture points x5 | SW (48.5, 27.5), SE (111.5, 27.5), W (27.0, 90.0), E (133.0, 90.2), N (80.0, 127.8) | 0x4000013B (ws 0x2E000B22, sight 4.25), category 8, PerceivedType 0x80000 | P |
| Bases / Foundry | ~(18.4, 50.1) team 1, ~(142.7, 50.3) team 2 | 0x40000170 / 0x4000016F, base 0x4000041F | G |
| Generator / centre | (80, 74) ring of ten 0x2E000006 statics (client) | generator logic = script 0x340002CF (layout 0xA000016B) | G |
| Minions | two waypoint rings through the points | Trooper 0x4000012D, Soldier 0x4000012E, Destroyer 0x40000EAA | P |
Rules (P): capture by presence (server), owner in **0x10000456**, scriptlets BeingCaptured / Captured / Lost,
score 500 per team (0x10000463), totals as match variables (0x3A000029) and HUD via 0x100004FB / 0x10000134 or
scorecard (O which); generator 0x340002CF strikes the losing team (events 0x1000007A / 0x10000079). Intro
0x35000023; minimap 0x4800014C; env 0x08000006-0A; **no music record** (0x10000ADC absent); announcer 0x4000047E.

### 8.5 Gotham Divided (0x40000399, 0x40000B6B, 0x40000E62; 0xA0C11AD2, LB 0x1BD3; 3 lanes; team 2 = (y, x))
| Object | Team 1 | Team 2 | Class | Conf. |
|---|---|---|---|---|
| Player starts | (7.5, 152.5) + 5 | (152.5, 7.5) + 5 | - | C pos |
| Power core | (17.5, 142.5) yaw 45 | (142.5, 17.5) yaw -135 | 0x40000A7E / 0x40000A7B | C |
| Core turret | (21.8, 136.9) | (136.9, 21.8) | 0x400003BA / 0x400003C1 | G |
| North: dampener / outer turret | (56.3, 148.2) / (103.3, 144.7) | (148.2, 56.6) / (144.5, 103.5) | 0x40000C61 / C60; 0x400003BB / 3C0 | G |
| Mid: dampener / outer turret | (46.8, 113.1) / (67.3, 92.2) | (113.1, 46.8) / (92.2, 67.3) | dampeners; 0x400003BF / 3BE | G |
| South: dampener / outer turret | (11.8, 98.2) / (16.8, 55.2) | (98.2, 11.8) / (55.2, 16.8) | dampeners; 0x400003BC / 3BD | G |
| Wave spawn | N (26.0, 142.5), M (23.5, 136.5), S (17.5, 134.0) | mirrored | minions 0x4000010A-10D, 0x40000941 / 942 | P |
| Neutral sites | (55, 55), (105, 105) | shared | control point 0x400003AF; pads / superpads / packs (classes in maps-complete 3.5) | G |
| Jungle | no anchor | | 0x40000935-0x40000940 | G |
Rules: core destruction; cinematics 0x35000014 / 15 (cores), intro 0x35000024; minimap 0x4800067C (diamond);
env 0x08000014 / 1C (0xA00000FC); music 0x48000E6B; announcer 0x40000554. Navmesh blobs are big-endian.

### 8.6 Coast City (0x40000270, 0x4000039C Crisis Labs, 0x40000B6A; 0xA0C122E2, LB 0x23E3; 2 lanes; team 2 = 160 - x)
| Object | Team 1 | Team 2 | Class | Conf. |
|---|---|---|---|---|
| Player starts | (4.7, 59.2) + 4 | (155.4, 59.1) + 4 | - | C pos |
| Power core | (17.0, 62.5) yaw 105 | (143.0, 62.5) yaw 255 | 0x40000C24 / 0x40000C23 | C |
| Core turret | (21.5, 64.0) | (138.5, 64.0) | 0x40000400 / 0x400003FF | G |
| North inner / outer turret | (30.9, 96.5) / (55.2, 123.5) | (129.1, 96.5) / (104.8, 123.5) | 0x400003FA / 3F9; 0x400003FD / 3FC | G |
| South inner / outer turret | (40.7, 46.0) / (64.8, 28.0) | (119.3, 46.0) / (95.2, 28.0) | 0x400003FE / 3FB; 3FD / 3FC | G |
| Doomsday Device + trigger | (80.0, 82.0) | shared | 0x400001F0 (ws 0x2E0008FD), 0x4000054F | P |
| Wave spawn | N (20.8, 67.0), S (22.5, 60.5) | (139.2, 67.0), (137.5, 60.5) | minions 0x400002D4 / 2D5, 0x40000441-443 ... | P |
| Jungle camps | (80, 145), (44.5, 90.5), (115.5, 90.5), (80, 9), (80, 57) | shared | 0x40000893-0x4000089A, guardian 0x40000430 | P |
Rules: core destruction helped by the Doomsday Device (G: captured, fires at the enemy core; scriptlets
0x10001096 / 0x10001097, note decoration DOOMSDAY_REVENGE_OVERLAY); barricades 0x2E000A26-A28 are client statics.
Cinematics 0x35000012 / 13, intro 0x35000020; minimap 0x48000563; env 0x0800000B... (0xA00000D2); **no music
record**; announcer 0x40000534. 2.1 m navmesh is empty.

---------------------------------------------------------------------------------------------------------------

## 9. Gaps (O)
1. Landblock streaming policy (which blocks, radius; 0x548F30 callers through the block-manager vtable, preloader
   0x7DEBD0 lists) - low risk: all gameplay is in the spawn block.
2. The region record 0x01000000 fields and the records that carry the position environment properties 0x216 /
   0x2D6 / 0x47D; the env record Crime Alley and Tutorial 2 use (none in their packs).
3. What the server should answer to client 0x201A (sent when 0x100001D3 changes).
4. Static type 3 / 16 have no client handler in the walked loops (P): confirm no other path (e.g. emitters
   created from the world state).
5. Structure layout of GD / CC (turret count per lane, Foundry, jungle on GD): no anchor in the data.
6. Capture progress transport (vital type 3 vs 0x100006B6), score notices for GH, meaning of 0x100006BD / BC /
   0x100004FF / 0x10000548 / 0x10000D0A.
7. Music on GH / CC (no 0x10000ADC), the 0x10000AD6 / ADA / ADB fields.
8. Which end cinematic plays for the winner.
