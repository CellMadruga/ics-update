# Tutorial 1 data inventory (static survey of the packs, 2026-10-21)

Scope: everything Tutorial 1 (encounter `0x40000991`) is made of in the player's packs, plus a short comparison
with a regular map (Gotham Heights v AI, `0x40000B6C`). Read-only survey; only IDs, short names and numbers are
recorded. Scratch tools used for it (not part of the project): a record segmenter (longest increasing chain of DID
occurrences in pack-list order), a typed property reader (kinds from `catalog/data/properties.tsv`), a scriptlet
table finder, a cinematic parser and `python -m ics.script_model`.

Coordinates below are in the frame of landblock `0x13CB` (cell `0xFB`) unless noted. **A landblock is 160 m**
(terrain cell `0x80…` = `0x441` = 33 x 33 vertices; Batman walks from (158.5, 30.8) in `0x13CB` to (11.7, 32.5) in
`0x14CB` in 175 frames = 13 m), so a position `(x, y)` in landblock `0x14CB` is `(x + 160, y)` here.

---------------------------------------------------------------------------------------------------------------------

## 0. The most useful findings (and corrections to earlier notes)

| # | Finding | Evidence |
|---|---|---|
| 1 | **The "layout placements" are cinematic actors.** Every named placement (`03GateA`, `DestVehicle`, `02PaddyWagonA`, `Melee1`, `PowerCore`, `InvisibleTarget` …) lives inside a `0x35` cinematic record of pack `0xA0000256`; there is no separate layout record. `rp.layout_entries` attributed them to `0x1D` records because the pack's record list was read with `record_starts()` (wrong starts). | Name strings at 9 266 480–9 274 496 (= record `0x35000026`), 9 274 496+ (`0x35000028`), 9 288 140+ (`0x35000033`), 9 639 044+ (`0x35000034`), 9 265 360+ (`0x35000025`); see section 4. |
| 2 | **The "scene" records do not exist.** What `Data.scene()` reads as "scene 0x1D… with events, variables and a script" is the **trailer of the cinematic itself** (camera cuts, `0x10000060` timeline events, frame markers, duration, server script). The `0x954` array of an actor is just its scriptlet tables (same role as `0x7D2` on objects). | `0x35000025` ends `… 0 10000012 | 2 x (frame, 0x10000060) | 5 markers | 23.0 | 0x34000591` right before `0x35000026` starts. Section 4. |
| 3 | **Objective table of the tutorial: record `0x48000D3F`** (template property `0x100001D2`), 29 objectives in play order with id, counter target and key binding. | Section 6.1. |
| 4 | **Conversation catalogue of the tutorial: entity `0x40000CB7`** (template property `0x10000B21`, strings in table `0x2B0001EE`), 96 conversations listed **in play order** with their line counts (intro `0x1B9, 0x22F, 0x22E, 0x22D, 0x22C`, then `0x1BA, 0x193, 0x19C, 0x1AC …`). | Section 6.2. |
| 5 | **No encounter script ships for Tutorial 1.** An encounter template names its server script in property `0x10000B5A` (`0x49000CA6` → `0x34000628`, a staged script with 28 conversations and stage events `0x10000186`); `0x49000991` has no `0x10000B5A`. No script in the install starts any of the tutorial's in-game conversations: only the cinematic scripts start conversations (441, 559, 558, 557, 556, 444, 463, 431, 856, 855). Waves, triggers and phase order were original-server logic. | `describe()` over all 826 decoded scripts; section 6. |
| 6 | **The meteor strike is a scriptlet sequence of the crater entity `0x40000CAB`** (template `0x49000CAB` "Door", world state `0x2E0004BE`, tables `[0x1D0000D0, 0x1D0008B6]`): `Vfx_Spawn_Event01` (0x1000087C) spawns the rock `0x2E000BB3`; `Vfx_Spawn_Event02` (0x1000087B) spawns dust cloud `0x2E0007D4` + shockwaves `0x2E0004ED`, `0x2E0006DE` and runs `Vfx_Active`; `Vfx_Active` (0x100000EB) plays particle effects `0x1800024B`, `0x18000E6A`, `0x180002D1` (the burning crater: fire/smoke candidates). The crater world state's own table `0x1D000155` (`Vfx_Active`) attaches the crater meshes `0x2E001060` + `0x2E001061`. `0x1D0008B6` is a scriptlet table, not a property set (the `0x8A5 = 5.0 …` values sent in fase3-db came from the entity template). | Section 5.6. |
| 7 | **Door / gate visuals are spawned by the door's own scriptlet**: `0x2E0010F3` (entity `0x40000B0F`) table `0x1D00073F` = `Object_Closed` (spawns child world state `0x2E0010F4`, the light wall) / `Object_Open`; `01GateA` `0x2E000CD7` table `0x1D000461` = `Object_Closed` (spawns `0x2E000CD8`) / `Object_Melee_Attack` / `Object_Open` / `testfx`. Both inherit base table `0x1D000385` (team colour). | Section 5.3. |
| 8 | **Guide arrow / objective ping script `0x34000600`** (on the practice target `0x40000BA9`, soldier `0x40000EB4`, destructible `0x40000C40`): event `0x10000060` on the entity sets IsActive → `RunScriptlet(SELF, Vfx_GuideArrow_Ping 0x10000F86)` and `RunScriptlet(agent, Vfx_GuideArrow 0x10000F80, target position)`; event `0x1000005F` clears it, `0x10000193` = left the world. | Section 6.4. |
| 9 | **Unit stats are in the templates** (base values copied from a `0x48` stat block named by `0x10000165`): tutorial Soldier Drone `0x40000C72` and Stabber `0x40000C71` 200 health, 10 attack damage, 1.0 attack speed, 3.0 move; Destroyer `0x40000EB2` 1500 health, 45 damage, 0.59 attacks/s, 2 attack armor, scale 0.8. XP reward formulas `0x10000224` (BaseXP 115 / 100), level-by-time formula `0x100001D9`. | Section 7. |
| 10 | **Packs the actors and objects need beyond the map list**: scriptlet tables `0x1D000199` (vehicle) in `0xA0000037`; `0x1D0000E1/E2/E8` (every unit) in `0xA00000DF`; `0x1D0000D0`, `0x1D000385`, the shockwave rig `0x2D000397` (used by `0x2E0004ED`, which is in the tutorial packs), world states `0x2E0006DE` and `0x2E00135E-60` in `0xA00000B3`; cinematic actors `0x2E0001B2` (Batman) `0xA0000076`, `0x2E0007C0` (Catwoman) `0xA00000CC`, `0x2E00095E` (`03GasJoker`) `0xA00000EB`. | Multi-pack index of all installed packs. |

---------------------------------------------------------------------------------------------------------------------

## 1. Load chain

| Step | Record | What it holds (evidence: parsed property list) |
|---|---|---|
| Encounter | `0x40000991` (pack `0xA00000B3`) | Header `did | 2 | 0 0 0 | …` (binary, not a property list). |
| Template | `0x49000991` (pack `0xA00000B3`, header `did | 2 | 0x2E`) | `0x10000406` = `0xA0C112CA` (map pack; kind `0x14`, 8 bytes: DID + 0); `0x1000021D` = `[0x100005ED {0x1000001F = (1, 0x13, 0xCB)}]` = **default landblock 0x13CB** (Gotham Heights: `(1, 0x1B, 0xF3)` = its landblock `0x1BF3`); `0x1000021C` = 300.0 (GH: 600.0); `0x1000062B` = `pve_tutorial_basic`; `0x100001D2` = `0x48000D3F` **objectives**; `0x10000B21` = `0x40000CB7` **conversation catalogue** (strings `0x2B0001EE`); `0x10000802` = `0x40000B69` (announcer set, strings `0x2B000093`); `0x10000287` = `0x48000D3E` (map settings: minimap images `0x130029B5` / `0x130029B4`, `0x1000009E` = 0x13, `0x100000C8` = 0xCB, `0x1000009F` = 1.6); `0x100002E9` = 3 x `{0x10000314 = 0x48000E71, 0x100001F4 = team 0/1/2}`; `0x10000A73` = `0x48000D48` (empty); `0x100009E7` = `0x48000F28` (16 hashed stat-tracking entries); `0x1000081E` = `0x48000EA9` (attribute display list: names of 0x10000B76 …, see section 7); `0x10000AB2` = `0x48000E29` (`[0x20, 0x11, 0x32, 0x2A, 0x7]`); `0x10000B2C` = `0x48000F06` and `0x10000B53` = `0x48000FB0` (lists of small ints, UI); `0x10000897` lobby music `0xA000018A`; `0x10000B66` next encounter `0x40000A81`; `0x10000AE7` = [`0x40000086`]. **No `0x10000B5A` (encounter script), no `0x8E`.** |
| Map pack | `0xA0C112CA` (category 1) | Pack list `0xA000024C` (zone, 13), `0xA0000256` (layout, 15), `0xA0000257` (variants, 14), `0xA00002D6`, `0xA00002D7` (category 7: 7 and 9 textures, nothing else). |

Other encounter template, for comparison: `0x49000CA6` (`pvp_1v1_gas_lane_team1_a`) has `0x10000B5A = 0x34000628`
and `0x10000B89 = 0x40000CBD`; objective list `0x48000E3B` elements carry a per-objective script `0x10000B44`
(`0x34000601`, `0x34000603`). Tutorial 1's objectives have none.

---------------------------------------------------------------------------------------------------------------------

## 2. Record formats

### 2.1 Pack payload
* Records follow the pack's DID list **in order**. Most start with their DID; a longest-increasing-chain over all DID
  occurrences finds them (`0xA0000256`: 685 of 812 anchored, `0xA0000257`: 213 / 324, `0xA000024C`: 3 638 / 3 711,
  map pack 44 / 48).
* **Some records carry no DID at all**; their bodies sit in their list slot after the previous record: all `0x1D`
  scriptlet tables, `0x1E`, `0x1C`, most `0x1A`, `0x11`, `0x2B` (string tables: the payload slot is empty, the texts
  are in the string streams), and the map's `0x85` / `0x90`. A `0x462 | DID` element (arrays `0x7D2` / `0x954`) is
  only a reference; nothing follows it inline.
* World-state records are preceded in the stream by the word `0x8B` (e.g. `… 0x8B | 0x2E000CD7 | 7 | 0x2D000AA9 …`).

### 2.2 Property lists
`u32 count | count x (u32 key | u32 key' | value)`; `key' = key | 0x40000000` means "present, no value" (bools set
to true). Value sizes by kind code (checked on the tutorial records): `0x08 0x09 0x10 0x11 0x13 0x15 0x16` 4 bytes
(note: `0x11` "int64" is stored as 4 bytes: colours such as `0x973 = 0xFF000000`, `0x47F`); `0x06` 3 x f32;
`0x07`, `0x14` 8 bytes; `0x0E` string = `u32 0 | token | table | 0 | 0` or `u32 1 | len | UTF-16 (padded) | 0 | 0`
(literal, e.g. template name `Door`); `0x01` = `u32 len | bytes (padded)` (e.g. `pve_tutorial_basic`); `0x0B` table =
`u32 0 | property list`; `0x0C` array = `u32 n | n x (element key | element value)`. Kind `0x03` (`0x576`, on lights)
is a larger struct (not decoded).

### 2.3 Headers by record type
| Prefix | Header | Notes |
|---|---|---|
| `0x2E` world state | `did | flags | base | 0 | props` | flags 7 (most), 2 (static meshes), 3 (derived), 0x15 (`0x2E000000`). `base` = `.entity` `0x2D…`, or a **parent world state** (`0x2E000006` for GH's type-3 statics; `0x2E000013` for the zone's type-2 meshes). |
| `0x49` template | `did | 0 or 3 | n | props [+ binary tail]` | 3 on units / objects with stats; the tail (graph list `0x1A…`, bounds) follows (`0x49000B0F`: 11 props + 14 KB tail). |
| `0x40` entity | `did | 2 | …` binary | Not a property list (component data). |
| `0x48` | `did | 0 | n | props` | Stat blocks, statuses (`0x10000242` script), settings. |
| `0x34` script | `did | 1 | 1 | …` | Decoded by `ics.script_model`. |
| `0x35` cinematic | section 4 | |
| `0x1D` scriptlet table | (no DID) `n_bases | n_bases x 0x1D DID | 1 | n | n x scriptlet` | Two tables in `0xA0000257` do start with their DID: `0x1D000767 | 1 | 5 | …`, `0x1D0003BB | 1 | 8 | …`. Scriptlet = `key | 0 | props | n_actions | actions`. |
| `0x52` sound bank | `did | hash | len | name` | Names in section 3. |
| `0x3B` formula | `did | 1 | 1 | …` + variable names | e.g. `Level`, `Time`, `TimeToLevel`, `MaxLevel`, `BaseXP`, `DeltaXP`, `KillerLevel`, `RewardTier`. |
| `0x80` terrain | `did | 0x441 | …` | 33 x 33 vertices. |
| `0x81` landblock info | `did | 0xC | 0 | 0 | 0x0400001B` | 20 bytes. |
| `0x82` statics | `did | 0 | a | 0 | b | entries` | Section 3.1. |

### 2.4 Scriptlet actions (inside `0x1D` tables)
Action type words seen before referenced DIDs: `0x0C` = **spawn / attach a child world state** (door → light wall,
crater → rock, dust, shockwaves); `0x11` = **particle effect** `0x18…` (always followed by `1 | 40.0 | 60.0 …`);
`0x17 | 1 | 0 | key` = **run another scriptlet of the table**; `0x1000050A | 0x1E… | 0x100002A4` and `0x18 | 0x1E…` =
play an FX template `0x1E…`; `1 | 0x19…` = sound cue; `0x21` / `3F800000 | 0x17…` = mesh `0x17…`. Small keys
(`0x5`, `0x1`, `0x3`) exist as scriptlet keys (wagon table: `0x5` + `Vfx_OnExplode`, as diag reported).

---------------------------------------------------------------------------------------------------------------------

## 3. Pack inventories

### 3.1 Map pack `0xA0C112CA` (48 records)
| Type | Count | What | Evidence |
|---|---|---|---|
| `0x13` | 17 | Textures (terrain / minimap), DXT | `13 | 2 | 3 | 1 | 3 | 0x100 …` + `DXT1` |
| `0x80` | 9 | Terrain cells of landblocks `0x12..0x14 x 0xCA..0xCC` | header `0x441` |
| `0x81` | 9 | Landblock info (20 bytes) | |
| `0x82` | 9 | Landblock statics: 997 entries (`0x820113CB` 857, `0x820114CB` 136, `0x820113CA` 3, `0x820112CB` 1) | below |
| `0x85` | 1 | `0x850113CB`: `4 | 1 | 0x16B | hash | 3 agent classes (radius, height, class)`: (0.525, 2.1, `0x10000003`), (1.1, 2.1, `0x10000002`), (2.1, 4.0, `0x10000001`) | 0x16B = number of statics of `0x820113CB` |
| `0x90` | 3 | Navigation meshes, one per agent class (`0x900113CB`, `0x901113CB`, `0x902113CB`): `1 | radius | height | class | 0 0 | len | "BlobAggFile" "NavMesh"` | bodies at 800 000 / 818 068 / 878 980 |

**Statics entry:** `flags | type | index | IID (0x01…) | world state | xyz | quaternion | [if flags & 0x80: 0 | props]`.

| Type | Count | World states | Meaning (evidence) |
|---|---|---|---|
| 7 | 781 | 125 mesh / entity world states (`0x2E00036D` x51 …) | Scenery. Includes the base landblock `0x14CB` objects with props: `0x2E000A35` "Base Team 01" (5.5, 37.5) `50F=6 2A4=1 team 1 side 3`; `0x2E000A3B` (17.5, 37.5) `team -1 side 3` (the power-core pedestal; table `[0x1D000385, 0x1D0003FD]`); `0x2E001185` (17.5, 37.5) `50F=5`; health packs `0x2E000D03` (21.75 / 71.75, 37.5) teams 1 / 2; turret plate `0x2E000A9F` (75, 37.5). **~80 client-placed destructibles** (section 5.4), the bank "holes" `0x2E001144/45/46` (8 spots), statics `0x2E000375` (10; a roof, not a crater: fase3-gg). |
| 2 | 80 | `0x2E000962` x26, `0x2E000963` x19, `0x2E00032B` x13 … | Single-mesh world states (`flags 2`, base `0x2E000013`, `0x1EB` = mesh) placed with per-instance scale `0x3B4` (vec3) and tint `0xD8`. Not volumes. |
| 3 | 91 | `0x2E00110F-0x2E001140` (one each), `0x2E000628` x14, `0x2E000625` x12, `0x2E0010D2` x8, `0x2E00113A`, `0x2E001139` | **Point emitters whose world states are in no installed pack.** In Gotham Heights the same type uses `0x2E000420-432` (`flags 3`, parent `0x2E000006`, sound binding `0x7A3 = {0xC3 = 0x19000047 …}`, team in `0x100002E6`): ambient emitters. Tutorial ones lie along the path: around the spawn (16-26, 57-62; six with `0x1000059C = 60` and `0x100002E6 = {0x10000B3B = 1, 0x100005B3 = 15, 0x100005B2 = 15}`), the street (32-54), under the bridge (z 187), the road to the base (95-148, 11-25), the base gate (152.8, 24.0). Probably the burning-street ambience (fire / smoke / sound); the client cannot build them. |
| 10 | 20 | `0x2E000011` | Point lights (colour `0x47F`, struct `0x576`, radius `0x480` = 15). |
| 21 | 25 | `0x2E000000` | Path nodes (GH has 114 of them along its lanes, some with `0x100003E7`). Tutorial: 5 at the spawn/street start (22.6-37.9, 56.2-62.7; one with `0x6A6 = 0x40000047`), 4 at the vehicle (41.8-46.6, 49.1-54.7), 6 at the bridge start (56-65, 39.8-45), 8 at the bridge end (75.5-82.6, 29-34.3), 1 at the Destroyer (152.77, 24.0). |

No trigger volumes, regions or spawn-wave records exist in the map pack.

### 3.2 Layout pack `0xA0000256` (812 records, category 15)
| Type | Count | What | Evidence / tutorial members |
|---|---|---|---|
| `0x35` | 5 | **Cinematics** (actors = all named placements) | `0x35000025/26/28/33/34`, section 4 |
| `0x34` | 11 | Server scripts | `0x3400058A`, `0x34000591`, `0x34000595`, `0x34000700` (cinematics); `0x34000838` (power core); `0x34000598`, `0x340005F7` (statuses); `0x34000014` (turret attack); `0x34000088` (soldier attack); `0x3400012B`, `0x340001CF` (hotspot statuses) |
| `0x2E` | 51 | World states | gates `0x2E0010F3/F4`, `0x2E000CD7/D8`, `0x2E0012B7`; power core `0x2E000AC5` and its children (`0x2E00103B` iris, `0x2E000A3A/3D/3E`, `0x2E000B70-74`, `0x2E000C5E`, `0x2E000CF4`, `0x2E000D1E`, `0x2E0013AC`); dust cloud `0x2E0007D4`; shockwave `0x2E0004ED`; base objects `0x2E000A35`, `0x2E000A3B`, `0x2E000D03`, `0x2E000A9F`; turret `0x2E001037`; rat `0x2E00033A` |
| `0x40` / `0x49` | 14 / 14 | Entities and templates | Door `0x40000B0F` (ws `0x2E0010F3`), Door `0x40000557` (`0x2E000CD7`), Door `0x40000C6E` (`0x2E0012B7`), Power Core `0x40000C90` (`0x2E000AC5`), Turret `0x4000016F` (team 2) / `0x40000170` (team 1) (`0x2E001037`), Base Team 01 `0x4000041F` (`0x2E000A35`), Hotspot Object `0x4000039D` (`0x2E000D36`) / `0x40000405` (`0x2E000D40`), Environment `0x40000B0A` (`0x2E000FC7`, phase pod), "Soldier Drone" `0x40000C14` (`0x2E00033A`, rat rig), `0x40000CB7` conversation catalogue, `0x40000B69` announcer set, `0x40000047` |
| `0x48` | 11 | Stat blocks / statuses | `0x48001128` (core), `0x480001B0` (turret), `0x48001024` (rat), `0x48000F5B` → `0x34000598`, `0x48000FDD` → `0x340005F7` (max stacks 99), `0x4800028B` → `0x3400012B`, `0x4800028C` → `0x340001CF`, `0x480000FB/FC`, `0x48000546/547` (`0x303` links) |
| `0x1D` | 50 | Scriptlet tables (no DID) | 46 placed exactly; section 5 / appendix |
| `0x1C` | 6 | Havok behaviour projects (no DID) | `0x1C00006C` powercore_a_core, `0x1C000046` meteor_dust_ring, `0x1C0000B5` phase_pod, `0x1C0000BA` alien_base_iris, `0x1C0000CA` artifact_foundry, `0x1C000022` deco_rat |
| `0x1E` | 23 | FX templates (probable; played by scriptlets / StartScriptlet) | `0x1E000201-210`, `0x1E0005F8/F9`, `0x1E00035F` (power core `Cinematic_Announcement`) … |
| `0x2B` | 5 | String tables | `0x2B0001EE` (135 tutorial dialogue strings), `0x2B000093` (announcer, 32), `0x2B0000A4` (object names: Base Team 01/02, Turret, Control Point …), `0x2B000009`, `0x2B00000B` (skill names) |
| `0x52` | 7 | Wwise banks | `Destruction`, `Turrets`, `Announcer_General`, `Music_Divided`, `AMB_GothamHeights`, `AMB_Tutorial`, `VO_Tutorial_Hero` |
| `0x3B` | 3 | Formulas | `0x3B0002CF` (`Level`: core health), `0x3B00000D` (`Time`, `TimeToLevel`, `MaxLevel`), `0x3B00000E` (kill-streak reward) |
| `0x2D` | 37 | `.entity` skeletons | e.g. `0x2D000DB0` env_pvp_alien_base_iris, `0x2D000E7F` phase_pod, `0x2D00023A` deco_rat |
| `0x13 0x14 0x15 0x16 0x17 0x18 0x19 0x1A 0x10 0x11 0x1F 0x30` | 90, 5, 149, 60, 40, 107, 43, 28, 37, 14, 1, 1 | Textures, shader templates (`AmbientLightCube`, `DiffuseMap0`), compiled shaders (DXBC), materials, meshes, particle effects, sound cues, Havok packfiles, model groups, Havok data, behaviour Lua (`Fidget_Delay`), enum table | |

### 3.3 Variants pack `0xA0000257` (324 records, category 14)
| Type | Count | Members |
|---|---|---|
| `0x40` / `0x49` | 10 / 10 | Practice Target `0x40000BA9`, Stabber `0x40000C71`, Soldier Drone `0x40000C72`, Destroyer Drone `0x40000EB2`, Soldier Drone `0x40000EB4` / `0x40000A5C` / `0x40000B24`, Trooper Drone `0x40000A5D` / `0x40000B23`, `0x40000AA7` |
| `0x48` | 8 | Stat blocks `0x480010EA` (tutorial drone / stabber), `0x48000E84/E85`, `0x48000F6F/70/71`, `0x480014B4` (Destroyer), status `0x48000FDD` |
| `0x34` | 5 | `0x340004A1` (tutorial melee attack), `0x3400058F` (Destroyer attack), `0x34000087` (trooper ranged), `0x34000088` (soldier melee), `0x340005F7` (shot tracker) |
| `0x2E` | 15 | Unit world states `0x2E001167` (melee), `0x2E001168` (ranged), `0x2E0012BB` (thug), `0x2E000AB5` (Destroyer), `0x2E001298` (practice target), `0x2E000808`, `0x2E000840`, plus projectile / FX children `0x2E000B66/67/68/6E`, `0x2E0013B0`, `0x2E0009A5`, `0x2E000E59`, `0x2E00118F` |
| `0x1D` | 24 | Unit tables `0x1D0002F6-2FA`, `0x1D000582`, `0x1D000674`, `0x1D00076F/770`, `0x1D000862`, `0x1D000890`, `0x1D0007A3/7A4` … |
| `0x1C` | 5 | `0x1C000056` alien_a_melee / `0x1C000057` alien_a_ranged, `0x1C0000CD` minion_thug, `0x1C0000E3` target_drone, `0x1C00007C` totem_guard_a_melee (Destroyer) |
| `0x3B` | 5 | `0x3B0002D6` (BaseXP 115), `0x3B0002D7` (BaseXP 100), `0x3B00033C` (practice target XP), `0x3B000287` (level by time), `0x3B0000CE` (kill reward) |
| `0x36` | 5 | Havok ragdolls |
| `0x52` | 2 | `chr_Min_DDD_Guardian`, `chr_min_pvp` |
| others | | `0x1A` 65 animation packfiles, `0x18` 47, `0x13` 39, `0x16` 17, `0x1E` 17, `0x19` 13, `0x17` 12, `0x10` 11, `0x2D` 9, `0x1F` 4 (behaviour Lua), `0x2B` 1 |

### 3.4 Zone pack `0xA000024C` (3 711 records, category 13)
Mostly the city: `0x10` 683, `0x15` 513, `0x13` 506, `0x16` 374, `0x2E` 373, `0x19` 331, `0x2D` 323, `0x17` 217,
`0x11` 133, `0x1D` 73, `0x18` 59, `0x50` 51, `0x14` 20, `0x40`/`0x49` 14, `0x1A` 9, `0x48` 5, `0x1C` 4, `0x34` 3,
`0x08` 2 (environment settings), `0x3E` 2 (large textures 64^2 / 512^2), `0x52` 2. Tutorial-relevant members:

| Record | What |
|---|---|
| `0x2E000AAB` | Street vehicle (`DestVehicle`), `.entity 0x2D0008BC` (collision only), `50F = 5`, `7EB = 0x11`, table `0x1D000199` (pack `0xA0000037`: `_ExecuteScriptlet`, `_StopScriptlet` only). |
| `0x2E00034D` / `0x2E00034E` | Paddy wagons (rig `0x2D000238` env_gas_deco_vehicle_a), `50F = 5`, `0x100003F2` = `0x10000117` / `0x10000116` (graph states IdleState01 / IdleState02), graph `0x1C000021`, tables `0x1D0000BB` / `0x1D0000BA`. |
| `0x2E000BB3` | Meteor rock (rig `0x2D00048D`), table `0x1D0003B5`, graph `0x1C000036` (env_event_meteor_a: `_impact` clip), bounds `0x24E` = (-100,-100,-2)…(100,100,50), sound binding `0x7A3 = {0x6F3 = 1, 0xD = 0x10000001, 0xC3 = 0x190005D1}`. |
| `0x2E00131C` | Meteor fragment (rig `0x2D00044D`, graph `0x1C000035` env_event_meteor_fragment), table `0x1D0008EA`. |
| `0x2E0004BE` | Crater (`.entity 0x2D000375`), table `0x1D000155`; entity `0x40000CAB` (template `0x49000CAB`, tables `[0x1D0000D0, 0x1D0008B6]`). |
| `0x2E0007D4` | Dust cloud (also in `0xA0000256`), table `0x1D00020B`, graph `0x1C000046`, sound `0x190006D8`. |
| `0x2E0004ED` | Shockwave (rig `0x2D000397` vfx_env_event_meteor_shockwave, pack `0xA00000B3`), table `0x1D000124`, graph `0x1C00002A`. |
| `0x2E001060` / `0x2E001061` | Crater meshes attached by `0x1D000155` (`0x1EE` / `0x1ED` set). |
| `0x2E000EFE`, `0x2E000F03-05` | Liftable / throwable destructibles (entities `0x40000C40`, `0x40000CAF`, `0x4000081B/C`, name "ERROR - Unnamed Destructible"): tables `[0x1D00060D, 0x1D00034B, 0x1D000111]`, scripts `0x3400015F` + `0x34000160` (+ `0x34000600` on `0x40000C40`), fracture data `0x800 = 0x500001EE-1F1`. Not placed anywhere. |
| `0x2E00061D-623` | Breakables (entities `0x400001BD`, `0x400001C5-1CA`), table `0x1D000168` (base `0x1D0005F0`), script `0x3400072D` (DestructionImpulse), `0x800 = 0x50000028-2E`. Not placed. |
| `0x2E0002AB` / `0x2E0002AC` | Environment-state objects (table `0x1D00008E/8F`: `_CEntitySystem_EnvironmentStateChange`, `Vfx_Active` with particle `0x1800010A/B`); 4 statics (111.2, 31.0), (125.2, 32.1), (62.7, 22.6), (110.0, 42.9). |
| `0x52` | `mse_Meteor`, `mse_MeteorStorm` |
| `0x50` | 51 fracture / physics shape records named by world states' `0x800` (convex hull vertices; contain keys such as `Destructible_OnCollision_ConcreteRock`, `Destructible_State3`). |

---------------------------------------------------------------------------------------------------------------------

## 4. Cinematics (pack `0xA0000256`)

**Format.** `did | n_camera_tracks | n_camera_tracks x (track id 0x10000012.. | n | n x key15 | n_fov | (frame, fov))`
`| n_actors | actors | trailer`. key15 = `frame | cell | lb x | lb y | x y z | quaternion (w x y z) | flag | 0 0 0`.
Actor = `len | name (padded) | world state | actor variable | 0 | 0 | props | initial scriptlet | n | key15s`
`| nA | (frame, graph event)… | nC | (frame, sound hash, 3)… | nB | B…`; B = `frame | scriptlet key | 0 | 0 | props |`
`target actor variable | target slot (0x10000030)`. Actor variable `0x1` = the player's own champion (Batman in
`0x35000033/34`); `0x10000005/15/17/18/02` are names other actors target. Trailer = `n_cuts | (frame, camera track)…`
`| n_events | (frame, 0x10000060)… | n_markers | (frame, hash, 3)… | f32 duration | server script`.

Graph-event ids in the A lists are in the per-graph enum tables of pack `0xA0000038`: `0x1000010F`
CinematicCombatBasicAttack, `0x100000AD` CbtState_Death_Induce, `0x100002F5` CbtState_Knockdown, `0x1000009D`
CbtState_GetUp, `0x10000183` SpawnIdle, `0x100000EB` Combat_Special_Attack_2 (scriptlet names come from table
`0x33000000`, same pack).

| Cinematic | Duration | Camera tracks / cuts | Timeline events `0x10000060` (frame) | Script | Conversations started (in event order) |
|---|---|---|---|---|---|
| `0x35000026` intro | 38.5 s | 4 tracks, cuts at 0 / 200 / 390 / 660 | 10, 200, 390, 530, 655, 846 | `0x3400058A` | 441 (0x1B9), 559 (0x22F), 558 (0x22E), 557 (0x22D), 556 (0x22C); event 8 → end state (`0x1000017B`, `0x10000012(agent)[0x10000210]`, `0x100000BB`) |
| `0x35000033` drone vs thug | 23.0 s | 1 | 14, 145, 300, 450, 580 | `0x34000595` | 463 (0x1CF) |
| `0x35000034` Catwoman | 15.75 s | 1 | 20, 200, 340, 653 | `0x34000700` | 431 (0x1AF), 856 (0x358), 855 (0x357) |
| `0x35000028` Destroyer | 17.0 s | 1 | 15, 60, 195, 345 | `0x34000595` | 463 (0x1CF) |
| `0x35000025` power core / end | 23.0 s | 1 | 15, 545 | `0x34000591` | 444 (0x1BC); then node `0x10000121` [393] |

All cinematic scripts set node `0x1000009C [1, 0x10000016 …]` on enter and `[1, 0 or 2 …]` on exit (environment /
cinematic state), `0x3400058A` reads the player and agent (`0x10000187` / `0x10000188`) and toggles fidgets on the
agent (`0x10000320` / `0x10000321`); `0x34000591` starts with `0x10000167 [36 1 0 0 0]`.

### 4.1 `0x35000026` intro (26 actors)
| Actor | World state | Start → end (frame: x, y) | Props | Scriptlets / events |
|---|---|---|---|---|
| 01RangedA | `0x2E001168` | 0: 156.91, 30.75 | side 1, `0x100007D3` = (-0.125, 3.0, 0.25), `0x100007CF` 3.0, `0x10000B3B` | CinematicAttack_Ranged at 195, 255, 320 |
| 01MeleeA / B | `0x2E001167` | 0: 158.98, 28.95 / 158.99, 32.46 | side 1, `0x10000B3B` | CinematicAttack_Melee x3 (200-330) |
| 01GateA | `0x2E000CD7` | 0: 159.86, 28.04 (yaw -1.57) | side 3, `0x6B3` 0.9 | Object_Closed ↔ Object_Melee_Attack alternating 0-351 (the gate taking hits) |
| 02Destroyer | `0x2E000AB5` (var `0x10000015`) | 0: 113.75, 123.0 → 635: 95.25, 125.75 (9 keys) | side 1, `0x450` 1.5, tables `[0x1D0007A4, 0x1D000385]` | graph event 465 Combat_Special_Attack_2; 473 CinematicCharacter_State00; 636 State01 |
| 02GaslightBatman | `0x2E0001B2` | 0: 96.0, 122.5 → 700: 67.90, 106.24 (7 keys) | table `0x1D000771` | basic attacks at the Destroyer (var `0x10000015`) 395-455; 480 CbtState_Knockdown, 500 CbtState_GetUp |
| 02PaddyWagonA / B | `0x2E00034D` / `0x2E00034E` | 101.98, 119.05 / 102.45, 126.62 | | Vfx_OnExplode at 473 / 474 (A also sound `0x7B0240B1` at 473) |
| 02MeleeA-D, 02RangedA/B | `0x2E001167` / `0x2E001168` | 94.5, 132.5; 97.6, 105.8; C 79.1, 127.3 → 92.1, 119.8; D 77.4, 126.1 → 90.4, 118.6; RangedA 95.0, 112.2; RangedB 93.9, 104.7 | side 1 | CinematicAttack_Loop 470-655 |
| 03ThugA | `0x2E0012BB` | 44.22, 59.02 | table `0x1D000890` | graph event 0 SpawnIdle |
| 03ThugB (var `0x10000005`) | `0x2E0012BB` | 34.92, 57.60 | | CinematicAttack_Melee on 03MeleeD (720-800) then 03MeleeC (875-1160) |
| 03MeleeC (var `0x10000017`) / 03MeleeD (var `0x10000018`) | `0x2E001167` | 35.34, 56.35 / 36.26, 57.69 | D: table `0x1D0007EE` | attack the thug from 705 / 745; D: 820 CinematicCharacter_Die |
| 03MeleeA/B, 03RangedA/B | `0x2E001167` / `0x2E001168` | 640: (45.6-49.4, 46.8-50.3) → 857-860: (62.8-66.6, 39.0-41.6) | side 1 | (walk onto the bridge) |
| 03GasJoker | `0x2E00095E` | 40.69, 70.92 → 860: 40.69, 86.89 | | (walks away north) |
| 03GateA / 03GateB | `0x2E0010F3` | 54.05, 44.80 / 89.87, 26.21 (yaw -2.043) | | |
| DestVehicle | `0x2E000AAB` | 43.66, 52.61 (yaw -2.513) | | |

### 4.2 The other cinematics
| Cinematic | Actor | World state | Path | Scriptlets / events |
|---|---|---|---|---|
| `0x35000033` | Drone_01 (var `0x10000015`) | `0x2E001167`, table `0x1D000774` | 34.98, 56.32 | init `_Entity_OnEnterWorld_Default`; graph events CinematicCombatBasicAttack 20-180, CbtState_Death_Induce 218; sound `0x2036D52C` + Vfx_OnExplode at 231 |
| | Thug_01 | `0x2E0012BB` | 34.61, 57.73 | CinematicCombatBasicAttack 5-205; `_Defeat_OnDead` 236 |
| | Gaslight_Batman_01 (player, var 1) | `0x2E0001B2`, `0x1D000771` | 37.64, 58.36 → 530: 39.59, 58.36 | Combat_Basic_Attack_Left 159 + Vfx_Bmg_Basic_Ranged_Left 165 `{0x100002F8 = 0x1E000023, 0x10000126 = 0x1800012A, 0x10000205 = 0x2E000222}` (the shot), Right 205 / 210 |
| | Thug_02 | `0x2E0012BB` | 44.27, 58.97 | init Vfx_SpawnIdle; Vfx_Spawn 400 |
| `0x35000034` | Gaslight_Batman (player, var 1) | `0x2E0001B2`, `0x5F9` 1 | 40.69, 58.23 → 450: 42.43, 55.59 | init Fidgets_Disable |
| | Gaslight_Catwoman (var `0x10000002`) | `0x2E0007C0`, tables `[0x1D0008C2, 0x1D000233]` | 52.87, 44.12 → 390: 33.37, 63.14 (9 keys) | Combat_Basic_Attack 135; **CinematicCharacter_State02 on InvisibleTarget at 146** (table `0x1D0008C2` State02 spawns `0x2E00135E`, `0x2E00135F`, `0x2E001360` + particles `0x180004BF`, `0x18000694`: the vehicle's break effect); Vfx_Glc_Stalking_Strike_Start / Active 270 / 275 |
| | InvisibleTarget (var `0x10000015`) | `0x2E000002`, table `0x1D0000E1` | 43.66, 52.61, z 201.36 (= the vehicle) | |
| `0x35000028` | Destroyer | `0x2E000AB5`, scale `0x6B4` 0.85, tables `[0x1D000774, 0x1D000385]` | 152.75, 24.0 | init Cinematic_Hidden; 115 `_Entity_OnSetClientRelationship`; 125 Cinematic_Startup (particles `0x18000B56`, `0x18000B58`, `0x18000032`, mesh `0x1700142A`, FX `0x1E000204-210`) |
| | Melee1/2, Ranged1/2 | `0x2E001167` / `0x2E001168` | (151.7-155.2, 22.5-26.6) → 425-445: (141.7-144.0, 15.9-18.3) | 1 Cinematic_Hidden; 125 Cinematic_Intro (spawn-in) |
| `0x35000025` | GaslightBatman | `0x2E0001B2` | 158.47, 30.77 → 175: 171.69, 32.53 | |
| | Gate | `0x2E000CD7`, side 3, scale 0.9, table `0x1D000789` | 159.86, 28.04 | State00 at 0 / 30 (`0x1D000789` State00 attaches `0x2E000CD8`) |
| | PowerCore | `0x2E000AC5`, side 3, table `0x1D00078A` | **177.5, 37.5** (landblock `0x14CB` (17.5, 37.5), on pedestal static `0x2E000A3B`) | 140 State01 (→ FX_Spawn_End: spawns `0x2E000C5E` x2, `0x2E000A3E`), 293 State02, 300 **State04 (spawns `0x2E00103B`, the iris that opens)**, 305 State03 |

Nothing in the client data refers to the cinematics (no `0x35` DID in any aligned non-asset record of the tutorial
packs): the server picks when to play them.

---------------------------------------------------------------------------------------------------------------------

## 5. Objects and effects

### 5.1 Street vehicle `0x2E000AAB`
* World state (zone pack): `50F = 5` (landblock static), `7EB = 0x11`, `2A4 = 1`, table `0x1D000199`
  (`_ExecuteScriptlet`, `_StopScriptlet`; pack `0xA0000037`), `.entity 0x2D0008BC` (autobone + MOPP collision). No
  entity template names it, no destruction (`0x800`) data, no damage-state scriptlets.
* Placed only as the intro actor `DestVehicle` (43.66, 52.61, yaw -2.513).
* Its "break" in `0x35000034` is done by **Catwoman's** scriptlet `CinematicCharacter_State02` (table `0x1D0008C2`)
  aimed at `InvisibleTarget` (world state `0x2E000002`) standing on the vehicle; that scriptlet spawns
  `0x2E00135E/5F/60` (pack `0xA00000B3`, `.entity 0x2D000767`, tables `0x1D000916-918` = key `0x5`) and particles.
* The objective "Place your cursor on the vehicle … lift it" (id `0x46`, key `0x10000087`) and the paddy wagons'
  super-strength use belong to the wagons (5.2), not to this vehicle.

### 5.2 Paddy wagons `0x2E00034D` / `0x2E00034E`
* Rig `0x2D000238` (bones of env_gas_deco_vehicle_a: chassis, body, upper/rear parts, pipe), graph `0x1C000021`
  (paddy_wagon_behavior: Idle01 / Idle02 with crash clips, an exploding clip), `0x100003F2` = IdleState01 / 02,
  `50F = 5`.
* Tables `0x1D0000BB` / `0x1D0000BA` (zone pack): key `0x5` (particle `0x180000FD` / `0x18000153`) and
  **Vfx_OnExplode `0x10000079`** = a timeline of particle effects `0x18000150`, `0x18000151`, `0x18000152`,
  `0x18000153`, `0x180000FD` (frames 0xB9-0xF7 at attach points `0x10000023`, `0x10000029`, `0x10000031`). This is the fire / explosion the server can trigger with `Vfx_OnExplode` once the wagon has its
  `0x7D2` + `0x5B5`.
* In the intro both explode at frames 473 / 474 (the Destroyer's special attack at 465).
* No super-strength scriptlets in their tables. The liftable objects of the data are the destructibles of 5.4
  (`0x1D00034B`: `SuperStrength_InitObjectPickup 0x100007A2`, `SuperStrength_PickupObject 0x100007A1`,
  `SuperStrength_ThrowObject 0x100007A0`, `Vfx_OnThrown 0x1000087A` (particle `0x180002F8`), `Vfx_OnExplode`,
  `Destructible_OnCollision_Metal / _Rubber`, guide arrow keys) with scripts `0x3400015F` (explosion: ExplosionRange,
  FindTargetsInRadius hostile, RunScriptlet `0x10000078` / `0x10000079`, DestructionImpulse, delay 10.5 s) and
  `0x34000160` (on event `0x10000035`: RaiseEvent `0x10000002` with `0x34000161` to the shooter).

### 5.3 Doors and gates
| World state | Entity | Tables | Scriptlets (actions) | Placement |
|---|---|---|---|---|
| `0x2E0010F3` (`.entity 0x2D000E51`, `50F = 3`) | `0x40000B0F` "Door" (template: no `0x10000AA7`, `0x1000019D = 0x2000`, `0x149 = 0x08000000`, `0x50F = 8`, `0x7D2 = [0x1D0000D0]`) | `0x1D00073F` (base `0x1D000385`) | **Object_Closed: spawn child `0x2E0010F4`** (+ meshes `0x17000000/01`, `0x17001341`); Object_Open: sound `0x19000A61`, run Object_Closed (stop) | 03GateA (54.05, 44.80), 03GateB (89.87, 26.21), yaw -2.043 |
| `0x2E0010F4` light wall (`.entity 0x2D000E52`) | | `0x1D00038B` | Vfx_Startup, Vfx_Active_Red / Purple / Blue (sound `0x19001299`), Vfx_TeamColor_SetParentColor | child of the door |
| `0x2E000CD7` (`.entity 0x2D000AA9`, `50F = 9`) | `0x40000557` "Door" | `0x1D000461` (base `0x1D000385`) | Object_Closed (spawns `0x2E000CD8`), Object_Melee_Attack (spawns `0x2E000CD8`, hit), Object_Open, testfx (`0x1000002B`) | 01GateA (159.86, 28.04) intro; "Gate" in `0x35000025` (table `0x1D000789` State00 → `0x2E000CD8`) |
| `0x2E000CD8` gate wall (`.entity 0x2D000AAA`) | | `0x1D00038B` | as the light wall | child |
| `0x2E0012B7` | `0x40000C6E` "Door" | `0x1D00088E` (base `0x1D000385`) | Object_Closed (spawns `0x2E000CD8`), Object_Open | not placed |
| (entity table) | all three doors | `0x1D0000D0` (pack `0xA00000B3`) | Vfx_Cbt_Tgt_Mark_Player_Retreat/Alert_Stop/Active, `_Selection_UsableTarget` | |
| base table | | `0x1D000385` (pack `0xA00000B3`) | Vfx_TeamColor_SetNull, `_CapturePoint_OnTeamBiasChanged`, `_Entity_OnSetClientRelationship`, Vfx_TeamColor_SetContention (sound `0x19000A61`) | |

So a gate is shown by creating the door with its world state (and the tables) and playing `Object_Closed`;
`Object_Open` opens it. The light wall need not be sent separately.

### 5.4 Crates, debris and holes
* **Client-placed breakables (statics, ~80):** world states with fracture data `0x800`, `0x1000019D = 0x1000`, tables
  with base `0x1D0005F0` (18 `Destructible_OnCollision_<material>` keys) + `Destructible_OnBreak 0x100003A9`
  (particles `0x180012C7` / `0x180004C3`): `0x2E0012EC` (6), `0x2E0012EE` (8), `0x2E0012EF` (5), `0x2E0012F0` (5),
  `0x2E0012F7` (8), `0x2E001323` (6), `0x2E001324` (9), `0x2E001325` (11), `0x2E00081F` (8, table `0x1D00022D`:
  OnBreak_T1 / T2), `0x2E000820/821`, `0x2E000883-88E` (6 at 143-146, 11-13), `0x2E000929/92C`, `0x2E0012E5/F6`,
  `0x2E00130B`, `0x2E001335`, `0x2E001394`. Clusters: the street (12-56, 49-71) and the road to the base
  (100-158, 1-39). They are statics: the client builds them; whether it breaks them itself is untested.
* **Server-side destructibles (not placed):** `0x2E000EFE`, `0x2E000F03-05` (5.2) and `0x2E00061D-623`
  (`Destructible_OnBreak` spawns `0x2E0006DE`, `Vfx_Spawn_Sequence` spawns the meteor fragment `0x2E00131C`; script
  `0x3400072D` = DestructionImpulse on event `0x1000000F`).
* **Holes:** the bank "lava crater" statics `0x2E001144/45/46` (3 parts per spot) at (2.84, 25.49) and (38.31,
  66.99) … 8 spots (section 3.1); statics `0x2E000375` (10, rig with MOPP collision; a roof, not a crater: fase3-gg). No script data.

### 5.5 Power core `0x2E000AC5` / entity `0x40000C90`
* Template `0x49000C90` ("Power Core"): team 1, side 3, stat block `0x48001128` (health regeneration 10, health by
  formula `0x1000031A = {0x10000100 = 0x10000426 (Health), 0x10000319 = 0x3B0002CF (Level)}`), **damage states
  `0x1000022F` = [0.75 → Object_Phase1 `0x100002C3`, 0.5 → Phase2 `0x100002C4`, 0.25 → Phase3 `0x100002C5`, 0 →
  Phase4 `0x100002C6`]**, `0x8E = [0x34000838]` (under-attack ping script), `0x100001D9 = 0x3B00000D`,
  `0x10000224 = 0x3B00000E`, unit flags `0x4010`, `0x10000133` 15.0, tables `[0x1D0000E2, 0x1D0000E1, 0x1D0000E8]`.
* World state: rig `0x2D0008D5` (env_pvp_powercore_a: Head, Nugget, Hoses A-I, Plugs A-I), graph `0x1C00006C`
  (spawn_a / idle_a / die_a clips), `0x8B1 = [3.75, 12, 3.0]`, tables `[0x1D000360, 0x1D000385]`.
* `0x1D000360` (25 scriptlets): Vfx_Active (spawns the iris `0x2E00103B`), **Vfx_OnExplode** (children `0x2E000CF4`,
  `0x2E000D1E`, particles `0x180009A2`, `0x18000930`, `0x180009A3`, `0x18000931`, `0x18001454/55`, `0x18000993`),
  Vfx_Relay_01/02/03_Start / Active / Stop, Vfx_Relay_All_Stop, Vfx_Destruct_State0/1, Vfx_Indestructible(_Stop)
  (spawns `0x2E000A3A`), Cinematic_Announcement (FX `0x1E00035F`), Target_Acquired / Lost, Vfx_Targeting,
  Object_Ranged_Attack / Vfx_Basic_Ranged (children `0x2E000B70/71/73/74`), Vfx_Status_Turret_Hardened,
  Vfx_Status_Armor_Attack_Debuff, `_Entity_OnSetClientRelationship` (children `0x2E000A3D`, `0x2E000A3E`).
* Cinematic actor table `0x1D00078A`: State00 (sound), State01 (→ FX_Spawn_End), State04 (spawns `0x2E00103B`),
  FX_Spawn_End (spawns `0x2E000C5E`, `0x2E000A3E`).
* Where: `0x35000025` puts it at (177.5, 37.5), the base pedestal. The data does not show it falling at the
  Destroyer's spot; its graph's `spawn_a` clip (played by State01) is the drop-in. The Destroyer's own entrance is
  `Cinematic_Startup` in `0x35000028` (5.6 / 7).
* `0x34000838`: on `0x100000E7` → under-attack ping (node `0x100000B8`) with a timer; on `0x10000088` → done.

### 5.6 Meteors, crater, dust, shockwave
| Record | Role | Scriptlets (actions) |
|---|---|---|
| Entity `0x40000CAB` / ws `0x2E0004BE` | **The strike** | `0x1D0008B6`: Vfx_Active (particles `0x1800024B`, `0x18000E6A`, `0x180002D1`); Vfx_Spawn_Event01 (spawn `0x2E000BB3`); Vfx_Spawn_Event02 (spawn `0x2E0007D4`, `0x2E0004ED`, `0x2E0006DE`, then run Vfx_Active; meshes `0x170001D0-D2`). `0x1D000155` (ws): Vfx_Active (attach `0x2E001060`, `0x2E001061`). `0x1D0000D0` (target marks). |
| `0x2E000BB3` rock | falls | `0x1D0003B5`: Vfx_Spawn_Alt01 (→ Event3), Vfx_Event2 (particle `0x18000710`: trail), Vfx_Event1 / Event3 (sound `0x19000502`), Vfx_Spawn (→ Event1). Graph `0x1C000036` has the impact clip. |
| `0x2E0007D4` dust cloud | impact | `0x1D00020B`: Vfx_Event1 (particle `0x18000405`, child `0x2E00070F`), Vfx_Spawn_Alt01 / Vfx_Startup (→ Event1). |
| `0x2E0004ED`, `0x2E0006DE` shockwaves | impact | `0x1D000124` (Vfx_Event1, Vfx_Startup), `0x1D0001BD` (same keys); rig `0x2D000397`. |
| `0x2E00131C` fragment | debris | `0x1D0008EA`: Vfx_Spawn (particle `0x180001E5`), Vfx_Spawn_Event02 (mesh `0x17000490`), Vfx_Spawn_Sequence, Vfx_SpawnIdle. |
| Sound | | banks `mse_Meteor` `0x5200000E`, `mse_MeteorStorm` `0x5200002D` |

`vfx_env_event_meteor_warning` / `_impact` (graphs `0x1A000217` / `0x1A00021F`) are only in `0xA000009A`; the
tutorial's own sequence above does not need them. A crater with fire and smoke = entity `0x40000CAB` + `Vfx_Active`
(and the ws table's `Vfx_Active` for the meshes). What triggers a strike in the original is not in the data.

### 5.7 Lightning, environment, explosions
* No lightning record in the tutorial packs (no names, no scriptlet keys of that kind in any tutorial table).
  Candidates for sky effects: environment-state objects `0x2E0002AB/AC` (react to
  `_CEntitySystem_EnvironmentStateChange 0x10000413`), driven by node `0x1000009C` in the cinematic scripts;
  records `0x08000003` / `0x08000016` (environment settings) and `0x3E00000D/E` (large textures) of the zone pack.
* Explosions: wagons (5.2), power core `Vfx_OnExplode` (5.5), destructibles `0x1D00034B` / `0x3400015F`, drones
  `_Defeat_OnDead` → `Vfx_OnExplode` (tables `0x1D0002F8/F9`, `0x1D000862`), Destroyer `CinematicCharacter_Die` →
  Vfx_OnExplode (`0x1D000774`).

---------------------------------------------------------------------------------------------------------------------

## 6. What orders the tutorial's phases

Searched: types `0x1C`, `0x1E`, `0x3B`, `0x52`, `0x2B`, `0x17`, `0x18`, `0x19`, `0x1A` in the tutorial packs (all
assets, see section 3), the map pack's `0x80 0x81 0x82 0x85 0x90` (no volumes / triggers), every `0x34` script. The
ordering data that does exist:

### 6.1 Objectives `0x48000D3F` (pack `0xA00000B3`)
Array `0x1000019F` of `0x10000211`: `0x1000030B` id, `0x10000352` type (4 = all), `0x10000C15` / `0x1000032D` text
token (table `0x2B0000ED`, tokens `0x…bf934`), `0x10000283` counter target, `0x10000B20` key-binding action (fills the
`'{}'` in the text), `0x100004E4` = 1 on two camera objectives, `0x10000B71` on one. Also `0x10000391` title token,
`0x10000C6F` subtitle, `0x10000B34` / `0x10000B4B` end texts, `0x100004EF` (objective panel heading), icons
`0x13003078`, `0x13002F5D`, `0x130033EC`.

| # | id | Count | Key | Subject (paraphrase) |
|---|---|---|---|---|
| 0 | `0x2` | | | move to the marked location (guide arrows) |
| 1 | `0x1` | | | move to the marked location |
| 2 | `0x6` | | | basic-attack the drone |
| 3 | `0x5` | 2 | | defeat the drones with basic attacks |
| 4 | `0x4` | | | unlock Sonic Batarang |
| 5 | `0x3` | | `0x10000025` | destroy a target with Q |
| 6 | `0xA` | 2 | `0x10000025` | defeat drones with basic attacks + Q |
| 7 | `0x9` | | | unlock Sonic Shell |
| 8 | `0x8` | | `0x1000002A` | destroy a target with W |
| 9 | `0x7` | 3 | | defeat the drones with skills |
| 10 | `0x1B` | | | upgrade Q or W |
| 11 | `0x1C` | 3 | | defeat the drones |
| 12 | `0x1D` | | `0x10000088` | use the Stolen Power on the marked location |
| 13 | `0x1E` | 4 | | defeat the drones |
| 14 | `0x1F` | | | unlock Bat Flight |
| 15 | `0x20` | | `0x10000031` | destroy a target with E |
| 16 | `0x22` | 4 | | defeat the drones |
| 17 | `0x23` | | | upgrade the passive |
| 18 | `0x24` | 4 | | defeat the drones |
| 19 | `0x21` | | | unlock the ultimate |
| 20 | `0x25` | | `0x10000065` | unlock the camera |
| 21 | `0x26` | | | pan the camera to the highlighted location |
| 22 | `0x27` | 3 | `0x10000035` | Bat Scream the drones |
| 23 | `0x28` | | `0x10000064` | centre the camera on Batman |
| 24 | `0x29` | | `0x10000065` | lock the camera |
| 25 | `0x46` | | `0x10000087` | lift the vehicle |
| 26 | `0x48` | | | throw the vehicle at the drones |
| 27 | `0x4B` | | | reach the Destroyer |
| 28 | `0x4D` | | | defeat the Destroyer |

### 6.2 Conversation catalogue `0x40000CB7` (pack `0xA0000256`)
Entity record `did | 2 | 1 | 0x19 | 0x2B0001EE | …` (9 340 bytes, byte-packed); entries `id | 1 | n_lines | 1 | …`
(line tokens in `0x2B0001EE`). The 96 ids in record order (line counts in brackets):

`1B9[2] 22F[3] 22E[2] 22D[3] 22C[1]` (intro cinematic) · `1BA[2] 193 19C[3] 1AC 1B8 38C 1E1 1E0[2] 1DF 1D4 1BE 19B 1AB`
`1B7[2] 19A[2] 1E3` · `1AF 358 357` (Catwoman cinematic) · `1C9 1E5 1E4 1C2 1B1 192 191[2] 199 1D9 1D3 1CC 38D 22B[3]`
`22A 196 1BD[2] 1D2 1C6 1D1 190 1AA 1AE 1A1 18F 1E2[2] 1CB 1DC 1A0 1C8 1B6 1B0 1CA 1B5 1D8[2] 1D0 3AC 1A5[3] 1AD 1A8`
`19F 1C5[4] 1C1 1C0 1B4` · `1CF[5]` (Destroyer cinematic) · `1D7 1C7` · `1BC[6]` (end cinematic) · then situational
lines `1CE 1B3 1CD 1DB 1BB 1BF 1C4 1B2 195 1A4 19E 1A3 1A7 1DE 1D5 1D6 1DA 1DD 198 19D 1A2 1A6 194 197`.

This order matches `catalog/data/conversations.tsv` and is the best data-backed phase order: the server can walk
it, using the objective table (6.1) for the gameplay steps between conversations.

### 6.3 Cinematic timelines
Section 4: each cinematic raises `0x10000060` at its event frames, which advances its own script's conversation
states. Frame markers (hash, frame) are probably camera-cut / sync names.

### 6.4 Guide arrows and pings: `0x34000600`
Graphs: S1 = arrow / ping control (RunScriptlet `0x10000F86` on SELF with handle, `0x10000F80` on the player's agent
with the target position; stop within NearbyRange of the agent, node `0x10000052`), S3/S4 = find the player
(`0x10000187`, `0x10000188`, retry timer); state flags IsActive (`0x10000060` → 1, `0x1000005F` → 0), IsAllowed,
IsInWorld (`0x10000193` → 0), IsDestructible (unit flag 4096). The tutorial's marker entity `0x40000A9C` (ping set
`0x1D0007A9`: `0x8E = [0x3400053C, 0x34000600]`) and the practice targets carry it: **the original server raised
`0x10000060` on the marker / target to show the arrow.**

### 6.5 Hints
Hint table `0x4800070C` (already in `reverse-engineering.md` §12) maps hint ids 16-40 to records `0x40000D30-D48`;
nothing in the tutorial packs says when to show them.

### 6.6 What is not in the data
No spawn waves, trigger volumes, position triggers, timers, objective transitions or in-game (non-cinematic)
conversation starts. The only encounter-level script property (`0x10000B5A`) is absent for Tutorial 1.

---------------------------------------------------------------------------------------------------------------------

## 7. Units

Attribute names: item stats / display list `0x48000EA9` (`0x10000426` Health, `0x10000140` Health Regeneration,
`0x10000B76` Attack Damage, `0x10000B83` / `0x10000B7D` Attack Penetration, `0x100006FE` Attack Speed, `0x10000B7C`
Attack Lifesteal, `0x10000B46` / `0x10000B80` Critical Chance (the second is 1.75 / 2.0 everywhere: probably the
critical multiplier), `0x10000B84` Attack Armor, `0x10000B7A` Power Armor, `0x100004AA` Resilience, `0x10000B75` Power
Damage, `0x10000B7E` / `0x10000B82` Power Penetration, `0x10000B7F` Power Lifesteal, `0x10000486` Will, `0x10000483`
Will Regeneration, `0x100005E4` Move Speed, `0x10000B7B` Cooldown Reduction, `0x10000852` Credits).

Attack = template table `0x100008E3` (slot 0 skill): `0x10000328` script, `0x100004B4` stats (`0x100004B6` stat id,
`0x100004B7` base, `0x100004D7` scaling formula), `0x1000003D` targeting 9. Stat ids: 18 range, 5 damage (1.0 x
formula `0x3B0002EC`), 30 missile speed, 0x1E/0x2C/0x11/0x1/0xE on the ranged units.

| Variant | Name | World state (rig, graph) | Used by | Health | Attack dmg | Atk speed | Move | Attack script (stats) | Other |
|---|---|---|---|---|---|---|---|---|---|
| `0x40000C72` | Soldier Drone | `0x2E001167` (alien_a_melee `0x2D00068A`, `0x1C000056`) | all `*Melee*`, Drone_01 | 200 | 10 | 1.0 | 3.0 | `0x340004A1` (18 = 1.5, 5 = 1.0) | stat block `0x480010EA`; XP `0x3B0002D6`; tables `[0x1D0000E2, 0x1D0000E1, 0x1D0000E8]` + ws `[0x1D0002F8, 0x1D000770, 0x1D000385]` |
| `0x40000C71` | Stabber | `0x2E0012BB` (minion_thug `0x2D000DF4`, `0x1C0000CD`) | 03ThugA/B, Thug_01/02 | 200 | 10 | 1.0 | 3.0 | `0x340004A1` | ws tables `[0x1D000766, 0x1D000890]` |
| (none) | ranged tutorial drone | `0x2E001168` (alien_a_ranged `0x2D0006BD`, `0x1C000057`) | all `*Ranged*` | | | | | | No template names it; nearest: Trooper Drone `0x40000A5D` / `0x40000B23` (ws `0x2E000840`). ws tables `[0x1D0002F9, 0x1D00076F, 0x1D000385]`, `0x357 = 0x1700030F` |
| `0x40000EB2` | Destroyer Drone | `0x2E000AB5` (totem_guard_a_melee `0x2D0008C6`, `0x1C00007C`) | 02Destroyer, Destroyer | 1500 | 45 | 0.59 | 3.0 | `0x3400058F` (18 = 1.5; RunScriptlet `0x1000018C` + `0x10000124`) | scale `0x6B4` 0.8, attack armor 2, crit 0.4; stat block `0x480014B4`; tables + `0x1D000385`, `0x1D0007A4`; ws table `0x1D0003BA` (base `0x1D0003BB`, minion keys) |
| `0x40000BA9` | Practice Target | `0x2E001298` (target_drone `0x2D000F92`, `0x1C0000E3`) | 03TargetA/B (server-placed) | 1.0 (block `0x48000F6F`) | | | | none | `0x8E = [0x34000600]`, XP `0x3B00033C`, ws table `0x1D000862` |
| `0x40000A5C` / `0x40000EB4` / `0x40000B24` | Soldier Drone (generic) | `0x2E000808` | | 170 | 6 / 6 / 8 | 1.0 | 3.0 | `0x34000088` | `0x40000EB4` has `0x8E = [0x34000600]`; `0x40000B24` team set, level formula `0x3B000287` |
| `0x40000A5D` / `0x40000B23` | Trooper Drone | `0x2E000840` | | 140 / 150 | 8 / 10 | 0.5 | 3.0 | `0x34000087` (18 = 5.0, 30 = 6.0 missile speed; ApplySkill `0x48000FDD` shot tracker) | XP `0x3B0002D7` |
| `0x4000016F` / `0x40000170` | Turret | `0x2E001037` (artifact_foundry rig, `0x1C0000CA`, scale 2.1) | (not placed in T1) | 1.0 x | 1000 | | | `0x34000014` (stats 0x11, 1, 0x1E = 12, 0xE) | block `0x480001B0`: attack pen. 500, attack armor 150, power armor 10 |
| `0x40000C14` | "Soldier Drone" | `0x2E00033A` (deco_rat `0x2D00023A`, `0x1C000022`) | (not placed) | 1.0 | | 1.0 | 4.0 | `0x34000088` | ambient rat critter |

Unit world-state props (`0x2E001167`): `0x7EB = 0xF`, `0x137 = 0.6`, `0x7EC = 2.8`, `0x50F = 7`, `0x100001DE = 2`,
`0x300`, `0x5B5` graph. Template props common to units and probably AI-related (meaning unknown): `0x10000934` (5 on
units, 2 on core / turret / destructibles), `0x1000025E` (2-4), `0x10000642` (2.0 units, 0.5 turret, 8.0 core),
`0x100004DA` minimap category (9 units, 6 turret, 0x1E core), `0x100001C3 = 0x1E`, `0x1000034C = 0x1E`,
`0x10000419 = 0.25`, `0x10000133` (15 core, 13.5 turret), `0x1000019D` unit flags (`0x10000` units, `0x4000` turret,
`0x4010` core, `0x2000` doors, `0x1000/0x1080` destructibles), `0x10000083` / `0x100001FC` icons. No aggro, leash or
sight-range property was identified; the AI itself was server logic (the client scripts are attack skills only).

---------------------------------------------------------------------------------------------------------------------

## 8. Server scripts (`0x34`) of the tutorial packs

| Script | Pack | Owner (evidence) | What |
|---|---|---|---|
| `0x3400058A` | 256 | trailer of `0x35000026` | intro conversations (section 4) |
| `0x34000591` | 256 | trailer of `0x35000025` | conversation 444, node `0x10000121` [393] |
| `0x34000595` | 256 | trailers of `0x35000028`, `0x35000033` | conversation 463 |
| `0x34000700` | 256 | trailer of `0x35000034` | conversations 431, 856, 855 |
| `0x34000838` | 256 | `0x49000C90` `0x8E` | power core under-attack ping |
| `0x34000598` | 256 | status `0x48000F5B` `0x10000242` | vitals regeneration over time (heal / will VFX `0x1E00007B`, `0x1E0002C7`) |
| `0x340005F7` | 256, 257 | status `0x48000FDD` | shot tracker (raises `0x10000126` on arrival) |
| `0x34000014` | 256 | turret templates `0x10000328` | turret attack |
| `0x34000088` | 256, 257 | generic soldier `0x10000328` | melee attack (RunScriptlet `0x10000C16` / `0x10000124`) |
| `0x3400012B` / `0x340001CF` | 256 | statuses `0x4800028B` / `0x4800028C` (`0x100002C4` of Base Team 01 / hotspots) | vital % per second while applied / (not decoded: tree missing) |
| `0x340004A1` | 257 | `0x40000C71`, `0x40000C72` | melee attack (cast results 3 / 2, ApplyEffects) |
| `0x3400058F` | 257 | `0x40000EB2` | Destroyer attack |
| `0x34000087` | 257 | trooper templates | ranged attack (missile `0x100000D4` / `0x10000326`) |
| `0x3400015F`, `0x34000160` | 24C | throwable destructibles | explosion / super-strength hand-off |
| `0x3400072D` | 24C | breakables `0x400001BD`, `0x400001C5-CA` | DestructionImpulse |
| `0x34000600`, `0x3400053C` | 0xB3 / DF | marker ping set, practice target | guide arrow / ping (6.4) |

---------------------------------------------------------------------------------------------------------------------

## 9. Gotham Heights v AI (`0x40000B6C`) in brief
* Template `0x49000B6C`: map pack `0xA0C11AF2` (66 textures, 9 `0x80`/`0x81`/`0x82`, 1 `0x85`, 3 `0x90`: the same
  layout as the tutorial), packs `0xA000009A` (zone, 6 674 records), `0xA000016B` (layout, 832), `0xA0000179`
  (variants, 234). Default landblock `(1, 0x1B, 0xF3)`, time 600 s, `0x10000802 = 0x4000047E`,
  `0x10000803 = 0x4000047A`, objectives `0x48000F52`, map settings `0x4800014C`, team records `0x48000073`,
  `0x4800014E/14F`, intro movie `map_GothamHeightsOverview.bik`. **No `0x10000B5A` script either.**
* Its 4 cinematics (`0x3500000D/E/F`, `0x35000023`) are 1-actor base fly-overs with no script (trailer
  `… 10.5 s | 0`). It has no named placements at all.
* Its map statics: 422 type 7, 114 type 21 (lane path nodes), 81 type 3 (sound emitters on `0x2E000006`-derived world
  states, teams in `0x100002E6`), 41 lights. Turrets / bases / control points exist as templates in `0xA000016B`
  (`0x4000016F/170` Turret, `0x4000041F` Base Team 01, `0x4000013B` Control Point, `0x40000511` Orbital Cannon,
  `0x40000180` Health Pack generator, doors `0x40000269/26B` …) but nothing in the data places them: placement was
  server-side for regular maps too.

---------------------------------------------------------------------------------------------------------------------

## 10. Open points
* Meaning of the template props listed at the end of section 7; of `0x10000121` [393] and `0x10000167` [36 …].
* Where the original placed the server objects that no cinematic shows (practice targets, waves, the bridge middle
  gate): not in the data.
* The type-3 tutorial emitters reference world states missing from the install (`0x2E00110F-40`, `0x2E000625/628`,
  `0x2E0010D2`, `0x2E00113A/39`).
* `0x1D0000E1`, `0x1D000233`, `0x1D000766`, `0x1D0001CA`, `0x1D0000B9` bodies were not located (header search
  found none in their slots).

## Appendix: scriptlet tables used by the tutorial's objects (keys in table order)
| Table | Pack | Bases | Scriptlets |
|---|---|---|---|
| `0x1D0000E2` | DF | | `_HFSM_BehaviorRaiseEventAction`, Engagement_SideStep_Left / Right, SetBehaviorVariable_Float |
| `0x1D0000E8` | DF | `0x1D0004F4` | Vfx_Fade_In / Out(_Instant / _ClientOnly), `_SUpgradeSystem_OnCurrencyGained`, `_Combat_GoToLocomotion`, CbtState_Laugh / Cower / KnockUp / Aggro / GetUp (+ Recover / Active), `_ExecuteScriptlet`, `_Defeat_StartupIncapacitated / OnDead / OnIncapacitated / OnRespawn / OnRevive / OnFade`, `_Selection_SoftSelection_Valid / Invalid` |
| `0x1D0002F8` | 257 | `0x1D0002FA`, `0x1D0002F7` | Robot_Minion_Capture_Attack, Robot_Minion_Melee_Attack, `_HFSM_DestroyEntityAction`, `_Entity_OnEnterWorld_Default` (→ Vfx_Spawn), `_Defeat_OnDead` (→ Vfx_OnExplode), Footstep_Right / Left, `_Defeat_OnFade` |
| `0x1D0002F9` | 257 | `0x1D0002FA`, `0x1D0002F6` | Robot_Minion_Ranged_Attack, then as `0x1D0002F8` |
| `0x1D0002FA` | 257 | | Vfx_Min_Basic_Melee, Vfx_Min_Basic_Ranged, Vfx_OnExplode |
| `0x1D000770` | 257 | | VFX_CBT_Hit_Shared_ClientOnly, Cinematic_Hidden, Cinematic_Intro (spawn-in particles `0x18000B56/B58`, `0x18000032`, `0x18001419`), CinematicAttack_EventHook, CinematicAttack_Melee (FX `0x1E0000B1`), CinematicAttack_Loop, Vfx_Min_OutOfCombat, Vfx_Spawn |
| `0x1D00076F` | 257 | | Cinematic_Hidden, Cinematic_Intro, CinematicAttack_MissileFiredHook (projectiles `0x2E0009A5`, `0x2E000B68`), CinematicAttack_Ranged, CinematicAttack_Loop, Vfx_Min_OutOfCombat |
| `0x1D000890` | 257 | | VFX_CBT_Hit_Shared_ClientOnly, Cinematic_Hidden, Cinematic_Intro, Vfx_SpawnIdle, CinematicAttack_EventHook, CinematicAttack_Melee, CinematicAttack_Loop, `_Defeat_OnDead`, Vfx_Event1, `_Defeat_OnFade`, Vfx_Min_OutOfCombat |
| `0x1D000862` | 257 | `0x1D000582` | Robot_Minion_Ranged_Attack, `_Entity_OnHibernate`, `_HFSM_DestroyEntityAction`, `_Entity_OnEnterWorld_Default`, `_Defeat_OnDead`, `_Defeat_OnFade` |
| `0x1D0007A4` | 256, 257 | | Combat_Special_Attack_2 (particle `0x18000F5D`), Destructible_State6, VFX_CBT_Hit_Shared_ClientOnly, Cinematic_Hidden, CinematicCharacter_State00 / 01, Footstep_Right / Left, Cinematic_Startup |
| `0x1D000774` | 256 | | VFX_CBT_Hit_Shared_ClientOnly, Cinematic_Hidden, CinematicCharacter_Die (→ Vfx_OnExplode), CinematicCharacter_State00, Cinematic_Startup |
| `0x1D000771` | 256 | | Batman's cinematic set: VFX_CBT_Hit_Shared_ClientOnly, Vfx_Bmg_Crit(_Stop), Combat_Basic_Attack_Right / Left, CinematicCharacter_State00 / 02, Fidgets_Disable / Enable, Vfx_Bmg_Basic_Stop, Vfx_Bmg_Basic_Ranged_Right / Left |
| `0x1D0007EE` | 256 | | CinematicCharacter_Show / Hide / Die / State00-02, VFX_CBT_Hit_Shared_ClientOnly, Cinematic_Hidden, CinematicAttack_MissileFiredHook / EventHook / Ranged / Melee, Footstep_Right / Left |
| `0x1D0008C2` | 256 | | CinematicCharacter_Hide, State01 (particles `0x1800052C/2D`), State02 (spawns `0x2E00135E/5F/60`) |
| `0x1D000789` / `0x1D00078A` / `0x1D00078B` / `0x1D00078E` / `0x1D0008C1` | 256 | | cinematic Gate / PowerCore / others: CinematicCharacter_State00-04, Cinematic_Hidden / Intro, FX_Spawn_End, Vfx_Startup |
| `0x1D000124`, `0x1D00020B`, `0x1D0003B5`, `0x1D0008EA`, `0x1D0008B6`, `0x1D000155` | | | section 5.6 |
| `0x1D00073F`, `0x1D000461`, `0x1D00088E`, `0x1D00038B`, `0x1D000385`, `0x1D0000D0` | | | section 5.3 |
| `0x1D000360`, `0x1D00078A` | | | section 5.5 |
| `0x1D0000BA`, `0x1D0000BB`, `0x1D00034B`, `0x1D00060D`, `0x1D000111`, `0x1D000168`, `0x1D0005F0`, `0x1D0008D2/D3/E3/E4/E5`, `0x1D000219`, `0x1D00022D` | | | sections 5.2, 5.4 |
| `0x1D000199` | 0037 | | `_ExecuteScriptlet`, `_StopScriptlet` (vehicle, InvisibleTarget world state `0x2E000002`) |
| `0x1D0007A9` | 0xB3 | | Vfx_Event1 (map ping set) |
| `0x1D000909` / `0x1D000710` | 256 | `0x1D000909` | turret: Vfx_Stop, Vfx_Fidget_A-C, Vfx_Active(_State0-6), Vfx_Startup, Vfx_Targeting, Vfx_Basic_Ranged (children `0x2E000B70-74`), Vfx_Death, Destructible_State3 / `_Entity_OnSetClientRelationship`, Object_Ranged_Attack, Target_Acquired / Lost |
| `0x1D000491` | 256 | | health pack `0x2E000D03`: Vfx_Stop, Vfx_Spawner_Tier01 / 02, Vfx_Active_State0 / 1 |
