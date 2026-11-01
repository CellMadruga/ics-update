# Database record types: DID prefix -> DB type -> class (static analysis, 2026-10-21)

Client `InfiniteCrisis.exe`. The table was rebuilt by emulating the client's own code (Unicorn, the emulator of `tools/script_decoder.py`); scratch scripts were not added to the project.

## How it was built

- **Prefix -> DB type:** `0x5E0360` clears the 256-entry table `0x1B68B30` (u32 per DID top byte), then for every DB type registers a range descriptor (`0x5E0290(&type, &desc)`: `desc+0` low DID, `+4` high DID, more fields) in the hash map at `0x1B68F58` and stores the type in `0x1B68B30[prefix]`. Emulated with `0x5E0290` stubbed: 78 ranges, 112 prefixes. Ranges cover a whole top byte except `0x80` (`0x80000000-0x800FFFFF`) and the singletons `0xF7000000`, `0xFC000000`, `0xFA000000`, `0xF9000000`, `0xFE000000`, `0xFFBADA55` and type 6 (`0x00000000`).
- **DB type -> class:** `0x9E0260` allocates one 0x80-byte registry entry per type (`0x9E5DA0(&{create, unpack, third}, type)`, vtable `0x15A7958`) and appends it to the array `0x18542A8` (count `0x18542B0`); `0x9DB020` sorts it. 73 types (0x02-0x57). `create` allocates the object (TLS allocator `alloc(self, size, did, tag, flags)`) and runs the constructor; `unpack(obj, stream)` is a thin wrapper that calls the class Unpack directly or through the vtable; `third` is the third callback (probably the release / reload hook).
- **Class names:** there is **no RTTI** for engine or game classes (the exe's 1562 RTTI descriptors are all library classes) and no DB-type name table. Names below come from the allocator **memory tag** (the tag index passed to the allocator, name = string table `0x18546B8[tag + 9]`: e.g. `0x3F` -> "StringTable", `0x41` -> "Textures", `0x56` -> "HFSM"), from source-file paths reached from the class code (`__FILE__` strings such as `DBScriptTable.cpp`, `PSDesc.cpp`, `EnumMapper.cpp`, `Font.cpp`, `RenderMesh.cpp`, `MaterialInstance.cpp`, `LayerStage.cpp`, `MaterialProperty.cpp`) and from what the records contain. Exact source-file names are marked in the evidence column.
- Four DB types have a prefix but **no class** in `0x9E0260`: 0x27 (prefix 0x0B), 0x28 (0x0A), 0x3C (0x84), 0x45 (0x38); no pack holds records of those prefixes. Type 0x06 is registered for the range 0x00000000 only (prefix 0 stays 0 in the table). The registry also has no class for types 0x06, 0x11, 0x26, 0x35, 0x37, 0x4C, 0x4F, 0x54, 0x55 (gaps in the numbering).
- The low prefixes 0x01-0x07, 0x0C, 0x0F, 0x1B, 0x23, 0x2A, 0x32, 0x39 and the singletons 0xF7/0xFC/0xFE/0xFFBADA55 are one global record each, all in the core packs 0xA0000037 / 0xA0000038 / 0xA0000039 (engine / world configuration; most have the memory tag "Region").

## Table (every prefix the client maps)

`records` = DIDs of that prefix listed in the player's 616 packs / number of packs. `create` / `size` / `tag` / `vtable` from emulating the create function; `unpack` = registered wrapper -> the class's Unpack.

| prefix | records (packs) | DB type | class (inferred) | create | size | tag | vtable | unpack | evidence | meaning |
|---|---|---|---|---|---|---|---|---|---|---|
| 0x01 | 1 (1) | 0x46 | Region data 0x01 | 0x50C1D0 | 0x68 | Region | 0x15AFE98 | 0x9D8720 -> 0x50C350 | tag Region | 0x01 (1 record) |
| 0x02 | 1 (1) | 0x42 | Region data 0x02 | 0x5120E0 | 0x30 | Region | 0x15AFFE8 | 0x9D86E0 -> 0x513330 | tag Region | 0x02 (1 record) |
| 0x03 | 1 (1) | 0x18 | Region data 0x03 | 0x5AD490 | 0x34 | Region | 0x15BB810 | 0x9D8280 -> 0x5AD680 | tag Region | 0x03 (1 record) |
| 0x04 | 1 (1) | 0x33 | Region data 0x04 | 0x5A3990 | 0x48 | Region | 0x15BB3E0 | 0x9D8550 -> 0x5A4080 | tag Region | 0x04 (1 record) |
| 0x05 | 1 (1) | 0x14 | Region data 0x05 | 0x5B18C0 | 0x3C | Region | 0x15BBB40 | 0x9D8200 -> 0x5B1C90 | tag Region | 0x05 (1 record) |
| 0x06 | 1 (1) | 0x1B | Region data 0x06 | 0x50B560 | 0x34 | Region | 0x15AFDC8 | 0x9D5350 -> 0x50B7C0 | tag Region; Unpack = vtable[22] 0x50B7C0 | 0x06 (1 record) |
| 0x07 | 1 (1) | 0x2A | Cell data 0x07 | 0x4DC120 | 0x34 | Cell | 0x15AC570 | 0x9D8430 -> 0x4DC790 | tag Cell | 0x07 (1 record) |
| 0x08 | 17 (7) | 0x2E | Lens flare 0x08 | 0x653580 | 0x44 | Region | 0x15CDD50 | 0x9D84B0 -> 0x653660 | tag Region; LensFlareEffect.cpp reached from its methods | 0x08 (17 records) |
| 0x09 | 0 | 0x3A | Region data 0x09 | 0x6A7CE0 | 0x30 | Region | 0x15D2790 | 0x9D85F0 -> 0x6A7EA0 | tag Region | 0x09 (none) |
| 0x0A | 0 | 0x28 | (no class registered) | - | - | - | - | - | - | - |
| 0x0B | 0 | 0x27 | (no class registered) | - | - | - | - | - | - | - |
| 0x0C | 1 (1) | 0x30 | DB object 0x0C | 0x626630 | 0x34 | Database | 0x15C93A8 | 0x9D84F0 -> 0x627230 | tag Database | 0x0C (1 record) |
| 0x0F | 1 (1) | 0x2F | Region data 0x0F | 0x5134A0 | 0x3C | Region | 0x15B0040 | 0x9D84D0 -> 0x513960 | tag Region | 0x0F (1 record) |
| 0x10 | 10010 (225) | 0x2B | RenderMesh | 0x72BFB0 | 0xCC | Render | 0x15D6C90 | 0x9D8450 -> 0x72ACB0 | tag Render; source RenderMesh.cpp; Unpack 0x72ACB0 reads vertex formats | prefix 0x10 is mapped to it, but the packs' 10 010 0x10 entries carry no data (they are key names); unused for them |
| 0x11 | 704 (11) | 0x0D | Mesh resource 0x11 | 0x4DEC30 | 0x24 | Mesh | 0x15ACCD0 | 0x9D8140 -> 0x4E0CF0 | tag Mesh | 0x11 records (704 in 11 packs): mesh data |
| 0x12 | 0 | 0x4B | Mesh 0x12 | 0x648E60 | 0x74 | Mesh | 0x15CD600 | 0x9D87C0 -> 0x648FE0 | tag Mesh | 0x12 (none in the packs) |
| 0x13 | 10460 (607) | 0x09 | Texture | 0x70F990 | 0xB8 | Textures | 0x15D5C30 | 0x9D80C0 -> 0x70D570 | tag Textures | 0x13 images / textures |
| 0x14 | 487 (29) | 0x4A | Material template (layer stages) | 0x7204E0 | 0xB4 | RenderMaterial | 0x15D6550 | 0x9D87A0 -> 0x7219D0 | tag RenderMaterial; source LayerStage.cpp | 0x14 shader / material templates (DXBC) |
| 0x15 | 8091 (27) | 0x39 | Shader / file resource | 0x6D6230 | 0x88 | RenderShaders | 0x15D43A0 | 0x9D85D0 -> 0x6D3B60 | tag RenderShaders | 0x15 file resources (shader sources, text, data) |
| 0x16 | 4031 (228) | 0x1C | Material instance | 0x71E280 | 0x30 | Render | 0x15D64F0 | 0x9D82E0 -> 0x721500 | tag Render; MaterialProperty.cpp | 0x16 material instances (texture refs + parameters) |
| 0x17 | 2973 (226) | 0x2C | MaterialInstance / model part | 0x7213E0 | 0xAC | Render | 0x15D65B0 | 0x9D8470 -> 0x71B0D0 | tag Render; source MaterialInstance.cpp | 0x17 model parts (shader 0x14 + material 0x16 + geometry) |
| 0x18 | 4212 (167) | 0x1A | PSDesc (particle system) | 0x686A00 | 0x7C | Particles | 0x15CFF50 | 0x9D82C0 -> 0x687080 | tag Particles; source engine/shared/script/fx/particle/PSDesc.cpp in its Unpack | 0x18 particle system descriptions (the catalog calls them Havok packfiles; the class is the particle desc) |
| 0x19 | 2995 (225) | 0x49 | Appearance parameter set | 0x4EBE50 | 0x34 | Appearance | 0x15AD358 | 0x9D8780 -> 0x4EC570 | tag Appearance | 0x19 parameter sets (material / appearance parameters) |
| 0x1A | 5745 (96) | 0x0F | Animation clip / behaviour graph | 0x559A60 | 0x48 | Animation | 0x15B4EB0 | 0x9D8180 -> 0x55D120 | tag Animation | 0x1A Havok packfiles (behaviour graph .hkb / animation clips) |
| 0x1B | 1 (1) | 0x36 | DB object 0x1B | 0x6111A0 | 0x34 | Database | 0x15C6E08 | 0x9D8590 -> 0x6113B0 | tag Database; Unpack 0x6113B0 | 0x1B (1 record) |
| 0x1C | 264 (96) | 0x1F | Object behaviour graph | 0x55CE60 | 0xE0 | Animation | 0x15B50B8 | 0x9D8340 -> 0x55D8E0 | tag Animation | 0x1C object behaviour graphs |
| 0x1D | 2083 (224) | 0x22 | DBScriptTable (template / script table) | 0x529D40 | 0x5C | Script | 0x15B1100 | 0x9D8380 -> 0x537080 | tag Script; source engine/shared/script/DBScriptTable.cpp | 0x1D templates: scriptlet tables of classes (property 0x7D2), layout records, cinematic scenes (end with the scene script 0x34..) |
| 0x1E | 1134 (77) | 0x15 | Status effect / FX script | 0x51EB70 | 0x3C | Scriptlet | 0x15B0AD8 | 0x9D8220 -> 0x535F70 | tag Scriptlet | 0x1E records (catalog: status effect; the tag says scriptlet/FX) |
| 0x1F | 114 (79) | 0x50 | Havok behaviour Lua | 0x556CE0 | 0x24 | Animation | 0x15B4D00 | 0x9D8820 -> 0x556ED0 | tag Animation | 0x1F behaviour scripts (Lua) / graphs |
| 0x20 | 89 (1) | 0x31 | UI Flash movie | 0x9DA7B0 | 0x6C | Database | 0x15FF098 | 0x9D8510 -> 0xA04A30 | tag Database; 0x20000056 is the skill panel movie | 0x20 Scaleform movies (89, pack 0xA00000D0) |
| 0x21 | 11 (2) | 0x10 | Camera definition 0x21 | 0x7D4390 | 0x58 | Camera | 0x15E4D28 | 0x9D81A0 -> 0x7DC510 | tag Camera | 0x21 camera records (11) |
| 0x22 | 5 (1) | 0x25 | DB object 0x22 | 0x5FF6C0 | 0x88 | Database | 0x15C3EA8 | 0x9D83E0 -> 0x603CE0 | tag Database | 0x22 (5 records) |
| 0x23 | 1 (1) | 0x20 | DB object 0x23 | 0x5EA7F0 | 0x60 | Database | 0x15C1CA0 | 0x9D8360 -> 0x5EA930 | tag Database | 0x23 (1 record) |
| 0x24 | 3 (2) | 0x47 | Font | 0x812440 | 0x60 | Font | 0x15E8B38 | 0x9D8740 -> 0x710770 | tag Font; source Font.cpp | 0x24 font glyph tables |
| 0x25 | 0 | 0x0A | Movie | 0x6C3EF0 | 0x2C | Movies | 0x15D3920 | 0x9D80E0 -> 0x6C4650 | tag Movies | 0x25 video (Bink?) records; none in the player's packs |
| 0x26 | 0 | 0x38 | DB object 0x26 | 0x753B10 | 0x4C | Database | 0x15D8610 | 0x9D85B0 -> 0x754450 | tag Database | 0x26 (none) |
| 0x27 | 3 (2) | 0x1D | UI layout 0x27 | 0x7F9450 | 0x50 | UI | - | 0x9D8300 -> 0x7FB600 | tag UI | 0x27 UI layout / element descriptions (3) |
| 0x2A | 1 (1) | 0x13 | DB object 0x2A | 0x4E7C20 | 0x34 | Database | 0x15AD238 | 0x9D81E0 -> 0x4E82B0 | tag Database | 0x2A (1 record) |
| 0x2B | 311 (126) | 0x19 | StringTable | 0x5A6F40 | 0x34 | StringTable | 0x15BB620 | 0x9D82A0 -> 0x5A90A0 | tag StringTable; source StringTable.cpp | 0x2B string tables |
| 0x2D | 2472 (224) | 0x0B | Setup (.entity) | 0x632880 | 0xD0 | Setup | 0x15CA858 | 0x9D8100 -> 0x632A20 | tag Setup (Turbine's 'Setup' = model setup) | 0x2D .entity: skeleton, model parts, appearance |
| 0x2E | 2937 (228) | 0x2D | World state (entity description) | 0x50E0A0 | 0x70 | Entity | 0x15AFF80 | 0x9D8490 -> 0x581210 | tag Entity; Unpack 0x581210 | 0x2E world states: what is placed in the world; WorldEntityFactory 0x54F1F0 accepts it as a class |
| 0x2F | 0 | 0x17 | DB object 0x2F | 0x541DF0 | 0x40 | Database | 0x15B29C0 | 0x9D8260 -> 0x584840 | tag Database | 0x2F (none in the packs) |
| 0x30 | 147 (17) | 0x48 | EnumMapper | 0x4C31D0 | 0x64 | Enum | 0x15AB500 | 0x9D8760 -> 0x4C34C0 | tag Enum; source engine/shared/emp/map/EnumMapper.cpp | 0x30 enum / name tables (graph events 0x300000A4, variable names ...) |
| 0x31 | 19 (1) | 0x44 | Enum table 0x31 | 0x443280 | 0x48 | Enum | 0x15A79B0 | 0x9D8700 -> 0x443850 | tag Enum; Unpack 0x443850 | 0x31 (19 records, one pack) |
| 0x32 | 1 (1) | 0x1E | Master property table 0x32 | 0x501C30 | 0x34 | MasterProperty | 0x15AF870 | 0x9D8320 -> 0x502750 | tag MasterProperty | 0x32 (1 record): the property definitions (names / kinds of the 0x10 keys?) |
| 0x33 | 2 (1) | 0x02 | NameTable (0x33) | 0x9D6BA0 | 0x54 | Database | 0x15FEE90 | 0x9DA5F0 -> 0x9D6D70 | tag Database; 0x33000000/1 in pack 0xA0000038 | key/name tables: 0x33000000 scriptlet/event key names (u32 key, u32 len, chars) |
| 0x34 | 987 (75) | 0x07 | Server script (ScriptNode graph) | 0x44B960 | 0x60 | HFSM | 0x15A80C8 | 0x9D80A0 -> 0x44ECE0 | tag HFSM; create 0x44B960 -> 0x60-byte object; Unpack 0x44ECE0 (DID, node array, optional locals, trailer) | 0x34 server scripts (HFSM node graphs; also the encounter / cinematic scene scripts) |
| 0x35 | 30 (5) | 0x3E | Cinematic | 0x6A4C50 | 0x88 | Camera | 0x15D2420 | 0x9D8650 -> 0x6A6300 | tag Camera; the class references 'CinematicSystem' | 0x35 cinematics (scene list; scenes are 0x1D records) |
| 0x36 | 197 (161) | 0x03 | Havok animation resource | 0x556F90 | 0x38 | Animation | 0x15B4D58 | 0x9D8040 -> 0x557030 | tag Animation | 0x36 Havok packfile (ragdoll / skeleton) |
| 0x37 | 185 (111) | 0x3D | Entity data 0x37 | 0x9D3AE0 | 0x48 | Entity | 0x15FEDE0 | 0x9D8630 -> 0x6DA6F0 | tag Entity; Unpack 0x6DA6F0 | 0x37 (185 records in 111 packs, next to champion / unit packs) |
| 0x38 | 0 | 0x45 | (no class registered) | - | - | - | - | - | - | - |
| 0x39 | 1 (1) | 0x32 | WLib object 0x39 | 0x47A350 | 0x38 | WLib | 0x15AA430 | 0x9D8530 -> 0x478900 | tag WLib | 0x39 (1 record) |
| 0x3A | 58 (47) | 0x3F | HFSM definition | 0x450720 | 0x24 | HFSM | 0x15A84B0 | 0x9D8680 -> 0x44AD60 | tag HFSM; Unpack 0x44AD60 (only variable blocks decode) | 0x3A HFSMs (e.g. Batman 0x3A000052: the champion's skill timer / cost variables) |
| 0x3B | 439 (66) | 0x08 | Expression / scaling formula | 0x463490 | 0x28 | HFSM | 0x15A8D90 | 0x9D8880 -> 0x46A140 | tag HFSM; Unpack = vtable[27] 0x46A140; expression classes 0x10000003-0x1000000F (Linear, Logistic, Step, Power, ScaleByLevel) evaluate curves | 0x3B scaling formulas (skill tooltips and stats) |
| 0x3C | 11 (1) | 0x4D | HFSM variable declaration | 0x4606D0 | 0x24 | HFSM | 0x15A8CB0 | 0x9D87E0 -> 0x461DB0 | tag HFSM; Unpack 0x461DB0 (decodes to one variable block, e.g. ConversationHandle) | 0x3C (11 records, pack 0xA00000B3) |
| 0x3D | 0 | 0x51 | HFSM object 0x3D | 0x44BA30 | 0x30 | HFSM | 0x15A8138 | 0x9D8840 -> 0x44DE40 | tag HFSM; Unpack 0x44DE40 | 0x3D (none in the packs) |
| 0x3E | 17 (5) | 0x52 | DB object 0x3E | 0x585320 | 0x3C | Database | 0x15B9320 | 0x9D8860 -> 0x586230 | tag Database | 0x3E (17 records, 5 packs) |
| 0x3F | 4 (4) | 0x53 | HFSM object 0x3F | 0x45B380 | 0x28 | HFSM | 0x15A8630 | 0x9D8880 -> 0x45FDD0 | tag HFSM; Unpack = vtable[27] 0x45FDD0 | 0x3F (4 records) |
| 0x40-0x47 | 2101 (233) | 0x40 | Entity class (weenie) | 0x47A2A0 | 0x5C | WState | 0x15AA3D0 | 0x9D86A0 -> 0x47B080 | tag WState; Unpack 0x47B080 | 0x40-0x47 entity classes / items (what the server sends as an object's class) |
| 0x48-0x4F | 4559 (676) | 0x29 | Property collection (data record) | 0x5057B0 | 0x38 | Properties | 0x15AF8D0 | 0x9D8400 -> 0x509B90 | tag Properties; Unpack 0x509B90 (also DB type 0x21) | 0x48-0x4F data records: skills, skill sets, champions, statuses, configs; 0x49 = templates of the 0x40 classes |
| 0x50 | 591 (5) | 0x4E | Entity data 0x50 | 0x4E4030 | 0x484 | Entity | 0x15AD190 | 0x9D8800 -> 0x4E42E0 | tag Entity; object 0x484 bytes | 0x50 (591 records, 5 packs) |
| 0x52 | 198 (127) | 0x56 | Sound bank | 0x826DD0 | 0x28 | Audio | - | 0x9D88A0 -> 0x826E50 | tag Audio | 0x52 Wwise sound banks |
| 0x80 | 54 (6) | 0x0E | Landblock terrain cell 0x80 | 0x545BF0 | 0x1D0 | Cell | 0x15B2A30 | 0x9D8160 -> 0x5490D0 | tag Cell | 0x80 terrain cells named by landblock (map packs) |
| 0x81 | 54 (6) | 0x24 | Landblock cell 0x81 | 0x540A60 | 0x40 | Cell | 0x15B2968 | 0x9D83C0 -> 0x542560 | tag Cell | 0x81 cell / environment data of a landblock |
| 0x82 | 54 (6) | 0x23 | Landblock statics 0x82 | 0x9D39A0 | 0xBC | Cell | 0x15FED88 | 0x9D83A0 -> 0x54A1A0 | tag Cell; Unpack 0x54A1A0 | 0x82 landblock static objects (flags / 7 / index / cell / world state / xyz / quat / props), placed by the client (BlockEntities 0x547B50) |
| 0x83 | 0 | 0x21 | Property collection 0x83 | 0x53A950 | 0x38 | Properties | 0x15B2390 | 0x9D8400 -> 0x509B90 | tag Properties; shares Unpack 0x509B90 with the 0x48 records | 0x83 (none in the packs) |
| 0x84 | 0 | 0x3C | (no class registered) | - | - | - | - | - | - | - |
| 0x85 | 6 (6) | 0x0C | Landblock info 0x85 | 0x4F95C0 | 0x40 | Database | 0x15AE448 | 0x9D8120 -> 0x4F88B0 | tag Database | 0x85 per-landblock data (6 records) |
| 0x90-0x9F | 18 (6) | 0x3B | Terrain data 0x90-0x9F | 0x829280 | 0x74 | Database | 0x15EACC8 | 0x9D8610 -> 0x829470 | tag Database; Unpack = vtable[24] 0x829470 | 0x90-0x9F landblock terrain records (map packs) |
| 0xA0 | 0 | 0x12 | Pack (RP) descriptor | 0x5873C0 | 0x34 | Setup | 0x15B9428 | 0x9D81C0 -> 0x5875C0 | tag Setup; range 0xA0000000-0xA0FFFFFF | 0xA0 pack ids: a pack is a DB object (its record = the pack's own list, e.g. a map pack lists the encounter's packs) |
| 0xA1 | 0 | 0x34 | Pack descriptor 0xA1 | 0x5872E0 | 0x34 | Setup | 0x15B93C8 | 0x9D8570 -> 0x587570 | tag Setup | 0xA1 (none in the packs) |
| 0xF7 | 1 (1) | 0x04 | Singleton 0xF7 | 0x4C5A30 | 0x3C | Database | 0x15AB848 | 0x9D8060 -> 0x4C5CC0 | tag Database; range is the single DID 0xF7000000 | one global record (1 in the packs) |
| 0xF9 | 0 | 0x43 | File DB object 0xF9 | 0x5DC830 | 0x48 | FileDB | 0x15C11D0 | 0x9D5350 -> 0x5DC940 | tag FileDB; Unpack = vtable[22] 0x5DC940 | single DID 0xF9000000 (none in the packs) |
| 0xFA | 0 | 0x16 | Singleton 0xFA | 0x6A9660 | 0x34 | Database | 0x15D3558 | 0x9D8240 -> 0x4F1900 | tag Database | single DID 0xFA000000 (none in the packs) |
| 0xFC | 1 (1) | 0x05 | Singleton 0xFC | 0x6349D0 | 0x40 | Database | 0x15CB120 | 0x9D8080 -> 0x634C40 | tag Database; single DID 0xFC000000 | one global record |
| 0xFE | 1 (1) | 0x41 | Singleton 0xFE | 0x4DCD00 | 0x64 | Database | 0x15AC5C8 | 0x9D86C0 -> 0x4DD010 | tag Database | single DID 0xFE000000 |
| 0xFF | 1 (1) | 0x57 | Singleton 0xFFBADA55 | 0x5ABAE0 | 0x44 | Database | 0x15BB7A8 | 0x9D88C0 -> 0x5AC1F0 | tag Database; range is the single DID 0xFFBADA55 | a debug / placeholder record (prefix 0xFF, 1 record) |

Every prefix that occurs in the packs has a DB type. Unmapped prefixes: 0x00, 0x0D, 0x0E, 0x28, 0x29, 0x2C, 0x51, 0x53-0x7F, 0x86-0x8F, 0xA2-0xF6, 0xF8, 0xFB, 0xFD.

## Types that matter for maps and encounters

- **0xA0 packs (type 0x12):** a pack is itself a DB object; the map pack of an encounter (`0x10000406` of the encounter template) lists the encounter's packs (zone 0xD, layout 0xF, variants 0xE, textures 0x7). The client loads exactly the packs the server names (0x20AF, `gmConnectionManager::LoadParentRPs`).
- **0x80 / 0x81 / 0x82 / 0x90-0x9F (types 0x0E, 0x24, 0x23, 0x3B):** landblock terrain cells, cell data, landblock statics (the only objects the client places by itself) and terrain data, all in the map pack.
- **0x2E world states (type 0x2D, tag Entity)** and **0x40-0x47 entity classes (type 0x40, tag WState):** what the layout places; `WorldEntityFactory 0x54F1F0` accepts both. **0x2D .entity (type 0x0B, tag Setup)**: model setup. **0x49 templates (type 0x29)**: class properties (script list 0x8E, world state 0x510, creation type 0x50F, encounter settings 0x10000406 / 0x10000AE6 ...).
- **0x1D (type 0x22 DBScriptTable):** layout records, scriptlet tables, cinematic scenes with their scene scripts (0x34); **0x34 (type 0x07)** the server scripts; **0x3B (type 0x08)** the scaling formulas (expression trees); **0x35 (type 0x3E)** cinematics; **0x3A / 0x3C (types 0x3F / 0x4D)** HFSM variable declarations.
- **0x48 (type 0x29 property collection):** encounter settings, skills, statuses, stat sheets, configs. **0x1E (type 0x15, tag Scriptlet)**, **0x18 (type 0x1A PSDesc)**, **0x1C (type 0x1F)** behaviour graphs and **0x1A (type 0x0F)** animation: effects and animation the scripts trigger.

## Range descriptor fields (desc, 0x70 bytes)

`+0` low DID, `+4` high DID, `+0x28` a small number per type (2-0x36: possibly the cache class / file id), `+0x38` a pointer `0x1874AA0`, `+0x3C` flags (0x41, 0x53, 0x55, 0x59, 0x72-0x79, 0xD3, 0x174, 0x253, 0x273), then two cache sizes (e.g. 0x40 / 0x100, 0x800 / 0x1000 for 0x1E, 0x180 / 0x400 for 0x48 and 0x50) and a byte budget (0x200000-0xA00000). Not needed by the server.
