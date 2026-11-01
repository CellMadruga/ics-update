# Entities, components and the engine architecture of the client (static analysis, 2026-10-22)

Client `InfiniteCrisis.exe` (sha256 463adfff...), image base 0x400000, all addresses are VAs. Sources: the full Ghidra
decompilation (`re-work/decomp/c/*.c`, `functions.tsv`, `strings.tsv`), capstone on the exe bytes for functions
Ghidra did not cut (e.g. `0x54F540`), and the earlier notes (`actor-creation-and-environment.md`,
`properties-complete.md`, `db-types.md`, `client-movement.md`, `client-scriptlets-graphs.md`,
`cinematics-vfx-audio.md`, `ui-complete.md`). Scratch scripts were not added to the project.
Marks: **C** = read in code / data, **P** = probable (inferred from code shape, names, neighbours), **O** = open.
"Server" = what our server must provide; "local" = the client computes / owns it.

## 0. Main findings

| # | Finding | Mark |
|---|---|---|
| 1 | The engine is Turbine's "hendrix" engine (`D:/build/hendrix/hendrix_pre/src/{engine,game}/{shared,client}/...`). **No game class has RTTI**: the 1 446 `.?AV` descriptors are all libraries (Scaleform GFx 3 `GAS*`/`G*` 515, Havok 2012.2 `hk*`/`hcl*` 728+88, CryptoPP 14, xerces 3). Engine / game classes are named by `__FILE__` strings, profiling-scope strings and allocator memory tags (sections 1, 2). | C |
| 2 | **An entity is a plain 0x120-byte struct with no vtable: 64 component pointers** (`+0x00..+0xFC`, slot = offset / 4), IID at `+0x100`, creation desc at `+0x108`, class DID at `+0x110`, flags at `+0x118`. Slots 0-24 are engine components, 0x20-0x3F game (`gm`) components. Every "`obj+0xNN` component" in the earlier notes is slot `NN/4` (section 3). | C |
| 3 | Components are created in **ConstructStep3** = factory vtable `+0xB8` = **`0xA9D7A0`** (game) which first calls **`0x606400`** (engine). 22 engine and 13 game creators; each one's condition is decoded (section 4.2). | C |
| 4 | **The game components depend on the unit flags `0x1000019D` (PerceivedType) at creation**: vitals (`+0x80`), floaty (`+0x90`), status icons (`+0xC0`) are created only if `PerceivedType & 0x7F59FB` (the client's own flag set **`CreateGameComponents` = 8346107**), the upgrade component (`+0xA4`) only for `Character` (8). Doors (`Deco` 0x2000), pickups (`Loot` 4), objectives (0x200), siege (0x400) get none: **this is why vitals `0x42` to a door crashed the client** (2026-10-21). All game components need a class of DB type 0x40 (entity class). | C |
| 5 | Engine components with a gate: movement (`+0x54`) **and the 0xB0 listener list (`+0x60`)** only for creation-type mobility 2 (creation types 7, 8), behaviour graph (`+0x04`) + script component (`+0x10`) only if the object has scriptlet tables `0x7D2` or cinematic templates `0x954`, AI obstruction (`+0x08`, Kynapse) only if `0x83C == 1`, destruction (`+0x58`) and the "destructible" render / effects variants only if property `0x800` (a DID of a 0x50 record) exists, GameComponent (`+0x30`) only for entity classes. | C |
| 6 | Many components (and services) are created through a **COM-like class registry**: `0xAFDE60` (registry singleton `[0x1B77A70]`), `0xAFDBF0(guid, factory)` registers (134 classes), `0xAFD830(clsid, iid)` = CreateInstance (factory vtable `+0x18`). The GUIDs are per-TU copies in `.rdata`; the factory vtable resolves which class a GUID is (section 2.3). | C |
| 7 | Raising a graph event (`(entity+4)->vt+0x58` = **`0x55BD30`**) is **dropped** when entity flags `+0x118` have bit `0x40` and not bit `8`; it is **queued** (array at component `+0xA4`) while the graph is not ready (`vt+0x50` false) and delivered later (`0x55AF70`). | C (code), O (who sets 0x40) |
| 8 | All 73 registered DB types have a DID prefix (`db-types.md` is complete in that sense); the third per-type callback is an **in-place constructor** for bulk / arena loading (e.g. `0x9D96D0`). The DB cache is `0x43CE00` (load mode 4 = do not wait for the record to be ready). | C |
| 9 | The creation "mode" (IID top byte -> 2/3/4, `0x54B940`) is the **allocator pool** of the entity and its components (third argument of the TLS allocator `alloc(self, size, pool, tag, flags)`), not a behaviour switch. | C (use), P (meaning) |
| 10 | The client's frame clock is the f64 `[0x1B77A90]` (seconds), updated once per frame by `0xAFE080` from the clock object `[0x1B77A88]`; the simulation runs **fixed steps** (`0x409F10` -> `UpdateSimulation 0x5AFEE0`, tick groups of 0x48 bytes with their own period and listeners). | C |

---------------------------------------------------------------------------------------------------------------------

## 1. Libraries and engine modules (C)

| Library | Evidence | Used for |
|---|---|---|
| Havok 2012.2 (Physics `hkp*` 288 RTTI, Behavior `hkb*` 220, Animation `hka*` 30, Cloth `hcl*` 88, Scene `hkx*` 37, Havok Script `hks` / LuaPlus inside `hkbInternal`) | compat chain `hkCompat_hk700r1 ... hk201220r1_Current.cpp`, build path `Y:\Build\20121203_205832_StandardPackages` | physics world, character rigid bodies, behaviour graphs (`.hkb` in 0x1A / 0x1C records), animation clips (spline / predictive / quantized compressed), skeleton mappers, foot IK (`TtFootIkController`), cloth, behaviour Lua scripts (0x1F records) |
| Scaleform GFx 3 (AS2: `GASMovieClipObject`, `GASExternalInterface` ...) | 515 RTTI | all UI (0x20 movies, `GM_*.RecvNotice_*`) |
| Kynapse (Autodesk) | `kypathdata`, `kyruntime` paths, `KynapseManager 0x4F8050`, `TurbineKynEntity`, `kynworldslice(distributed)` | navigation mesh / path finding, AI obstruction |
| Wwise | `AK::SoundEngine::*` (Ghidra FID names at `0xFE4000-0x1060000`), `.pck` / `AKPK` banks | audio (section 9) |
| CryptoPP, OpenSSL, libcurl, CEF3 (`WebBrowserCEFHandler.cpp`), xerces 3.1, DirectInput / XInput, zlib | strings / RTTI | login crypto, web store browser, XML config, input |

Engine source files named by `__FILE__` strings (the only class names the exe gives): `database/DBCache.cpp`,
`interp/{ReferenceTable,DBResolver,property/PropertyObject}.cpp`, `emp/map/EnumMapper.cpp`,
`gametime/GameTime.cpp`, `property/MasterProperty.cpp`, `region/Region.cpp`, `script/DBScriptTable.cpp`,
`script/shared/{scriptlet/ScriptletScriptNode,exec/ExecuteScriptNode}.cpp`, `script/fx/particle/PSDesc.cpp`,
`cell/BlockEntities.cpp`, `entity/WorldEntityFactory.cpp`, `entity/desc/EntityDesc.cpp`,
`entity/component/{aiobstruction/AIObstructionComponent,game/GameComponent,model/ModelComponent}.cpp`,
`entity/component/property/{entity/EntityPropertyProvider,entity/ClassPropertyCollectionPropertySource,
volume/monitor/MonitorVolumePropertySource,surface/SurfacePropertyProvider}.cpp`, `stringtable/StringTable.cpp`,
`taboo/TabooTableAdaptor.cpp`, `pparser/*` (XML); client: `ccell/CEnvCell.cpp`, `cinputmap/CInputManager.cpp`,
`entity/appearance/{AppearanceResource,EntityAppearance}.cpp`, `entity/component/{model/CModelComponent,
render/RenderComponent}.cpp`, `movie/MovieTheatre.cpp`, `render/{font,landscape,material,mesh,streak,beam,flare,
ui,scene}/...`, `smartbox/worldrender/WorldLandscape.cpp`, `ui/uielement/...`; game:
`game/shared/system/propertymonitor/PropertyMonitorCallback.cpp`, `game/shared/net/compatibility/
gmCompatibilityVersion.H`.

Memory tags (allocator tag index -> name, table `0x18546B8[tag + 9]`, C): 0 Unspecified, 1 CoreDatabase, 3 CoreNet,
8 Animation, 9 Audio, 0xA Cell, 0xF Database, 0x13 **Entity**, 0x15 FileDB, 0x17 **GameSystems**, 0x1B Havok,
0x1C Input, 0x1D WSL, 0x1E WLib, 0x1F WState, 0x21 Kynapse, 0x28 Particles, 0x2A Physics, 0x2B Properties, 0x2C
PropertyChange, 0x2D MasterProperty, 0x2E Region, 0x2F Render, 0x37 Script, 0x38 ScriptNode, 0x3C Scriptlet, 0x3D
Camera, 0x3E WorldRender, 0x3F StringTable, 0x44 UI, 0x45 UIGFx, 0x47 UIElement, 0x4C Enum, 0x4D Appearance, 0x4E
Setup, 0x52 RP_System, 0x55 Variable, 0x56 HFSM, 0x58 GameplaySurface, 0x59 WebBrowser, 0x5A SocialMedia (90 names).

---------------------------------------------------------------------------------------------------------------------

## 2. Managers, singletons, registries

### 2.1 Singletons and global tables (C unless marked)

| Global | What | Main functions |
|---|---|---|
| TLS slot `[0x1878D0C]` | per-thread allocator, `alloc(self, size, pool, tag, flags)` (vtable slot 0) | used everywhere |
| `[0x1B67258]` | **WorldEntityFactory** (vtable `0x15A32D0`): IID -> entity (`+0x58`), create (`+0x24`, `+0xB0`), template merge (`+0xE4` `0x54F1F0`) | section 4 |
| `[0x1B57E64]` | **database manager** (`vt+4 +4`: get by `{type, did}`); DB cache `0x43CE00` | section 10 |
| `[0x1B68F34]` | DID -> DB type registry (`vt+0xC`, wrapper **`0x5DFB80(did)`**; table `0x1B68B30` by top byte) | `db-types.md` |
| `0x18542A8` / count `0x18542B0` | DB type -> class registry (73 entries of `{create, unpack, construct-in-place}`) built by `0x9E0260` | section 10 |
| `0x4FEE60(id)` | property descriptor lookup (MasterProperty `0x32000000`) | section 5 |
| `[0x1B77A70]` | COM-like class registry (2.3) | `0xAFDE60`, `0xAFDBF0`, `0xAFD830` |
| `0xB0EC50` / `0x483240` | network event registry (336 events) / notice registry (464 notices) | `protocol-server-to-client.md` |
| `0x1B6AB70` (count `0x1B6AB78`) | scriptlet action factories (0x31 types, `0x669CE0`) | `client-scriptlets-graphs.md` |
| `[0x1B6A710]` | local player IID (getter `0x635230`; entity via `0x6351D0`) | |
| `[0x1B77A88]` / `[0x1B77A90]` / `[0x1B77A98]` | game clock object / frame time f64 / second time value | section 12 |
| `[0x1B68040]` | physics world manager (0x70 bytes, tag Physics, created lazily by `0x409810`, ctor `0x5AEC90`; `PhysicsWorldManager` strings at `0x5CDED0`, `0x5D3650`) | |
| `[0x1B73518]` | world renderer (`+0xF6` "re-evaluate lighting", `+0xDC` camera component) | `cinematics-vfx-audio.md` 5.1 |
| `0x18546B8` | memory tag names | section 1 |

### 2.2 Systems ticked per frame (profiling-scope names, C for the name / address, P for the role)

Engine: `AnimationManager 0x55C040` (per graph `updateBehaviorGraph` / `updateAttachmentManager` in `0x55B500`),
`PhysicsWorldManager`, `UpdateSimulation 0x5AFEE0`, `KynapseManager 0x4F8050`, `ScriptTriggerManager 0x525AE0`,
`CinematicSystem 0x6A61E0`, `UpdatePresentation 0x68A7B0`, scene render `0x7635A0..0x763630`
(`SceneRender__{UpdateAndCullScene,UpdateScene,RenderScene,Render}`), `WorldRender__Render 0x7F0567`,
`SmartBox_Render 0x7D2C40`, streak / beam / particle renderers. Game (`gm` / `C` prefix, ticked from `0xA5EBA0`
and siblings): `gmCameraSystem 0xA56850`, `gmTargetFXManager 0xA56B70`, `FloatyManagerSystem 0xA5ED60`,
`MapNoteManager 0xA6A7C0`, `CEncounterEnvironmentSystem 0xA801F0`, `gmCEncounterManagementSystem 0xA855E0`,
`CDialogSystem 0xA89C40`, `CKnowledgePingSystem 0xA8BDC0`, `gmCTrainingSystem 0xA93470`,
`gmConnectionManager 0xA9AF20` (`::LoadParentRPs 0xA99370`, `::LoadMatchData_ 0xA99460`), `gmHFSMComponent
0x977B30`, `ScaleformWebBrowserManager 0x9FF4B0`. Components are **not** ticked through the entity: each manager
iterates the components it registered (e.g. AnimationManager's array at `+4`, count `+0xC`) (P for the general rule,
C for AnimationManager).

### 2.3 COM-like class registry (C)

- `0xAFDE60` returns the registry `[0x1B77A70]` (0x14 bytes, hash map of `{GUID, factory}` nodes; lookup
  `0x645360` compares the 16 GUID bytes).
- Registration: a static initialiser allocates a 0xC-byte factory (`vtable, 0x15AB378 (IUnknown part), refcount 1`)
  and calls **`0xAFDBF0(registry, &guid, factory)`**. 134 initialisers call it.
- Creation: **`0xAFD830(out, &clsid, &iid, outer, &obj)`**: find the factory, QI it for the class-factory interface
  (`0x1616310`), call its `+0x18` CreateInstance(iid). The engine uses it ~770 times (components, services,
  network-event destinations: the "QI for an interface GUID" in every network-event exec, `protocol-server-to-
  client.md` 1).
- Components created this way (GUID -> registration function, factory vtable, CreateInstance) are listed in
  section 4.3.

---------------------------------------------------------------------------------------------------------------------

## 3. The entity (C)

Allocated by ConstructStep1 (`0x54B9A0`): `alloc(0x120, pool, tag 0x13 Entity)`, cleared by `0x54AA50`.

| Offset | Field |
|---|---|
| `+0x00..+0xFC` | **component slots 0..0x3F** (`entity[slot]`); a component's own `vt+0x3C` returns its slot; `0x54A2B0` attaches (`vt+0x10` AddRef, store, `vt+0x30` OnAttach); `0x54E2D0` detaches all (`vt+0x34`, `vt+0x14`) |
| `+0x100` / `+0x104` | IID (u64, low / high) |
| `+0x108` | creation desc (refcounted, `0x54A980`) |
| `+0x10C` | cleared with the desc |
| `+0x110` | class DID (init `[0x1B67260]` = none) |
| `+0x118` | flags: `1` finalized (Step6 `0x54A6C6`), `8` in the world / scene (set `0x64BDF4`, `0x64DC31`, cleared `0x64BEA0`, `0x64BF80`), `0x40` (O; with 8 clear, graph events are dropped and `0x64BEA0` does not unlink), `0x100` has a serialized component-state stream (`0x54F651`), `0x200` (set by `0x54E70B`, `0x63CED0`, `0x63D316`, `0x63E1C8`, `0x63F560`; O) |

IID top byte (C for the values, P for the names): `0x01` landblock statics placed by the client (`BlockEntities`,
IID from the cell `0x4DB130`), `0x02` server-created world objects (`0x0200000000000001` = the local player),
`0x06` player system (`0x0600000000000403`), `0x81` client-local objects (cinematic actors, `0x4DAD00`). Pool from
the top byte (`0x54B940` / `0x6297D0`): desc `+0x30` if set, else 1 / 4 / 5 -> 2, 2 -> 4, 3 -> 3, other -> 0.

---------------------------------------------------------------------------------------------------------------------

## 4. Object creation

### 4.1 From the network bundle to the factory (C; details in `actor-creation-and-environment.md`)

1. Event `0x4` = a batch of sub-events: **`0xF2`** (reader `0x54BD00`: `u32 class` -> desc `+8`, `u64 parent IID`
   -> desc `+0x38`), **`0xB0`** (position / movement module, reader `0x57EE90`), **`0xBC`** (property table merged
   into the desc's property set before construction, `0x64CA10` -> `0x502B00`). Remove = event `0x3`.
2. Create handler `0x64D8A0` (IID top byte 2: waits for the landblock, `0x64C310` / `0x64CA10`) ->
   factory `+0x40` `0x54B790` -> `+0x3C` BuildCreationInfoFromEntityDesc `0x54AD90` -> `0x54F1F0`.
3. **`0x54F1F0` WorldEntityFactory template merge**: class -> world state -> `.entity`, recursive, stops at a DB-type
   0x0B (`.entity`, 0x2D) DID. Class kinds accepted (DB type of the DID, `0x5DFB80`):
   - **0x40 entity class** (prefix 0x40-0x47; its template is the 0x49 record of the same low bits): loads the world
     state named by property **`0x510`** (mode 1, `0x54A860`) and coerces a non-"unique" creation type `0x50F` to
     6 or 8 (log `0x15B34C8`: "must be UniqueDynamicMobile, UniqueDynamicImmobile or UniqueClientOnlyImmobile").
   - **0x2D world state** (prefix 0x2E): used bare, no coercion.
   - error `0x15B3570` "wstate is missing a parent .entity (in PhysObj_Property)" when the chain has no 0x2D DID.
4. **`0x54F540` (factory `+0xB0`) = construction**, six steps (C, strings `0x15B3830..0x15B3670`):

| Step | Function | What |
|---|---|---|
| 1 | `0x54B9A0` | IID check (factory `+0x58`: already exists -> fail `0x80004005`), allocate the entity (3), copy IID, attach desc |
| 2 | `0x54F0B0` | register the entity in the factory |
| (2b) | `0x502D90`, `0x54C1D0` | the desc's property set; if a component-state stream is passed (the "pos" argument of earlier diag), flag `0x100` and deserialize it |
| 3 | factory `+0xB8` = **`0xA9D7A0`** | component creation (4.2); failure -> `0x54E2D0` detach all |
| 4 | factory `+0xBC` = `0x54C7C0` | message registration (the entity's event sinks) |
| 5 | factory `+0xC4` = **`0xA9D1A0`** | OnEntityConstruction: engine components in the fixed order of table `0x15B2EF8` (`0x54A640`: slots 11, 17, 18, 24, 7, 21, 12, 14, 15, 16, 0, 10, 9, 1, 3, 5, 4, 20, 6, 8, 13, 19, 22, 2, 23), then game slots 0x20..0x3F in order; each `vt+0x24(entity, arg)` |
| 6 | `0x54A6A0` (`0x54E420` on failure) | finalize, flags `|= 1` |

### 4.2 Which components an object gets (C)

Engine (`0x606400`; the creation type `0x50F` is read by `0x54EF40` from the desc, else the class):

| Slot (offset) | Creator wrapper -> creator | Condition |
|---|---|---|
| 24 (`+0x60`) | `0x6045A0` -> `0x6297D0` | creation-type mobility (`0x580160`) == 2 (creation types 7, 8) |
| 15 (`+0x3C`) | `0x604610` -> `0x5748F0` | `0x5801B0(0x50F)` == 3 (creation types 1, 7) |
| 14 (`+0x38`) | `0x604680` -> `0x62AD30` | always |
| 16 (`+0x40`) | `0x6046F0` -> `0x62A340` | always |
| 6 (`+0x18`) | `0x604760` -> `0x619B80` | always |
| 0 (`+0x00`) | `0x6047D0` -> `0x61C580` | always |
| 7 (`+0x1C`) | `0x604840` -> `0x55FF50` | always |
| 9 (`+0x24`) | `0x6048B0` -> `0x61BBF0` | always |
| 5 (`+0x14`) | `0x604920` -> `0x626FC0` / `0x604990` -> `0x626DC0` | always; first variant if property `0x800` exists |
| 3 (`+0x0C`) | `0x604A00` -> `0x617C40` / `0x604A70` -> `0x618250` | always; first variant if `0x800` exists |
| 20 (`+0x50`) | `0x604AE0` -> `0x627F30` | always |
| 1 (`+0x04`) | `0x604B50` -> `0x60EC00` | object has `0x7D2` (scriptlet tables) or `0x954` (cinematic templates) (`0x58CB60`) |
| 4 (`+0x10`) | `0x604BC0` -> `0x628510` | same condition |
| 8 (`+0x20`) | `0x604C30` -> `0x57F9B0` | always |
| 13 (`+0x34`) | `0x604CA0` -> `0x56EFF0` | always |
| 11 (`+0x2C`) | `0x604D10` -> `0x618620` | always |
| 21 (`+0x54`) | `0x604D80` -> `0x60AE40` | mobility == 2 (`0x603D80`; creation types 7, 8) |
| 12 (`+0x30`) | `0x604DF0` -> `0x60CD40` | class is a 0x40 entity class (`0x603DA0`) and `[0x1B779A4] != 0x80000011` |
| 22 (`+0x58`) | `0x604E60` -> `0x62E310` | property `0x800` exists (`0x57FF30`) |
| 2 (`+0x08`) | `0x604ED0` -> `0x60C480` | property `0x83C` == 1 (`0x6063C0`) |

Note: slot 24 (the 0xB0 listener list) and slot 21 (movement) both need mobility 2, so an object of creation type
1-6 / 9 has **no 0xB0 listener at all**: this completes the explanation of "bare world states are never placed"
(`actor-creation-and-environment.md`): both the listener list and the movement component are missing (C). Slots 10,
17, 18, 19, 23 are in the construction order but nothing in the factory creates them (O: created later by other
systems, or unused).

Game (`0xA9D7A0`, after the engine step):

| Slot (offset) | Wrapper -> creator | Condition |
|---|---|---|
| 43 (`+0xAC`) | `0xA9D1F0` -> `0xAB3D20` | mobility == 2 (any class) |
| 35 (`+0x8C`) | `0xA9D260` -> `0xAA5CF0` | class is DB type 0x40 (all rows below need it) |
| 46 (`+0xB8`) | `0xA9D2D0` -> `0xAA4BD0` | always |
| 39 (`+0x9C`) | `0xA9D340` -> `0xAA6130` | property `0x100005A6` (enum `0x300001EF`) != 0 |
| 47 (`+0xBC`) | `0xA9D3B0` -> `0xAA61D0` | bool `0x100008DA` set |
| 32 (`+0x80`) | `0xA9D420` -> `0xAA6360` | `PerceivedType 0x1000019D & 0x7F59FB` (CreateGameComponents) |
| 36 (`+0x90`) | `0xA9D490` -> `0xAA4E40` | same |
| 48 (`+0xC0`) | `0xA9D500` -> `0xAA4D10` | same |
| 41 (`+0xA4`) | `0xA9D570` -> `0xAA6090` | same and `PerceivedType & 8` (Character) |
| 44 (`+0xB0`) | `0xA9D5E0` -> `0xAA4C70` | same and `0x1000076A` (DID of a 0x40 class) differs from the default |
| 33 (`+0x84`) | `0xA9D650` -> `0xAA4950` | always |
| 42 (`+0xA8`) | `0xA9D6C0` -> `0xAA5E50` | `PerceivedType != 0` |
| 34 (`+0x88`) | `0xA9D730` -> `0xAB0370` | IID top byte 2 (server objects, `0x4DAF10`) |

`PerceivedType` is read at construction through `0x9CFBF0`: the unit component (`0xAA0DC0`) `+0xA4` if present,
else the entity property `0x1000019D` (template value or the creation bundle's `0xBC` value). Flag names
(`gmPerceptionPropertyList`, `ui-complete.md`): Boss 1, SmallEnvironmentalObject 2, Loot 4, Character 8, Turret
0x10, Missile 0x20, CharacterInteractive 0x40, LargeEnvironmentalObject 0x80, Creature 0x100, Objective 0x200,
Siege 0x400, Inhibitor 0x800, Destructible 0x1000, Deco 0x2000, Base 0x4000, AutomatedPlayer 0x8000, Minion
0x10000, Device 0x20000, DoomsdayDevice 0x40000, CapturePoint 0x80000, Pet 0x100000, Player 0x200000, Lieutenant
0x400000. `CreateGameComponents` = all except Loot, Objective, Siege, Deco, AutomatedPlayer.

### 4.3 Component catalogue

Size / tag / vtable come from the creator (or the class factory's CreateInstance for registry-created ones); the
slot is the vtable's `+0x3C` constant. Names: C when a `__FILE__` / profiling string is in the component's own
methods, P otherwise.

| Slot | Name | Size, tag | Main vtable(s) | Creation | Properties / messages that drive it | Server? |
|---|---|---|---|---|---|---|
| 0 | **PhysicsComponent** (C: "PhysicsComponent: Scale...", "SetPosition: entities in the engine cannot lie outside...", "Any entity that is mobile must have a convex physics shape") | 0x148 Entity | `0x15C8948` (base `0x15B6FE0`) | direct, ctor `0x61BE70` | `.entity` physics shape, scale, `CollisionLayer_Property`; mobility from `0x5801B0` | local (data) |
| 1 | **Behaviour graph / animation component** (C: `hkbBehaviorGraph::generate` strings; graph events `vt+0x58 = 0x55BD30`) | registry, CreateInstance `0x610200` | `0x15C6D30` (base `0x15B4FE0`) | GUID `08aa097e-...`, reg `0x60DB70`, factory `0x15C6C64` | 0x1A / 0x1C graphs of the `.entity`; events via scriptlet `0x100001E3` + `0x780`, cinematics | server raises events (scriptlets) |
| 2 | **AIObstructionComponent** (C: Kynapse obstruction strings) | 0x7C Kynapse | `0x15C65A8` / `0x15C64F8` | GUID `bb7d3642-...`, reg `0x60C3E0`, create `0x60C780` | `0x83C == 1`, obstruction shape (prism / physics mesh) | local |
| 3 | **EffectsComponent** (C: string `EffectsComponent 0x6179C0`; particle "holding location" / "bone type" checks in `vt+0x48`) | 0x90 / 0xA8 Entity | `0x15C7968` / `0x15C79E0` (base `0x15C78E0`) | direct | particle systems 0x18 attached by scriptlets, holding locations of the `.entity` | server starts them via scriptlets |
| 4 | **Script (scriptlet) component** (C: `obj+0x10` in the 0x8D handler `0x634F20`) | 0x98 Script | `0x15C9818` (base `0x15B8660`) | direct, ctor `0x628060` | tables `0x7D2` / `0x954`, event 0x8D / 0x2050 / 0x2056 / 0x2073 | server (0x8D) |
| 5 | **RenderComponent** (C: `RenderComponent.cpp`, "RenderComponent: Scale...") | 0x140 / 0x158 Entity | `0x15C94D0` / `0x15C9440` (base `0x15C9240`) | direct, ctors `0x6266D0` / `0x626920` | position from the entity frame, scale `0x450`, team colour, lighting `0x956` (model `+0x11C`) | local (follows the movement / frame) |
| 6 | **CModelComponent** (appearance; C: `CModelComponent.cpp`) | 0x138 Entity | `0x15C82D8` (base `0x15B6078`) | GUID `85233f68-...`, reg `0x619A50`, create `0x61B800` | `.entity` model setup, appearance events 0x8B / 0xB8 / 0xF5 / 0x106 / 0x10D / 0x115 / 0x124 / 0x138 | server only for appearance changes |
| 7 | **Containment / attachment component** (C: "Contained entity IID"; the 0xB0 flag 0x04 listener `0x15B5378` `+0x18 = 0x6113E0` attaches to an IID) | 0x88 Entity | `0x15B53A8` (base `0x15B52F8`) | direct, ctor `0x55FB40` | 0xB0 flag 0x04 `u64` parent IID | server (attach) |
| 8 | ? (small) | 0x24 Entity | `0x15B8A30` | direct `0x57F9B0` | O | O |
| 9 | **ModelComponent** (shared; C: `ModelComponent.cpp` in `0x569430`; model lookup `0x5693A0 -> 0x54CB80`) | 0x70 Entity | `0x15C84D0` (base `0x15B65B0`) | direct | class -> world state -> `.entity` | local |
| 11 | entity message component (P: "Failed to allocate message ... cross server message" in `vt+0x1C`) | 0x38 Entity | `0x15C7BF0` (base `0x15B5D90`) | GUID `99e7254d-...`, reg `0x618580`, create `0x6186C0` | first in the construction order | local |
| 12 | **GameComponent** (C: `GameComponent.cpp` `0x5629E0`) | 0x6C Entity | `0x15C6770` (base `0x15B5BE8`) | GUID `4ea75f74-...`, reg `0x60CBC0`, create `0x60CDE0` | bridge to the game layer (P) | local |
| 13 | ? | 0x18 Entity | `0x15B6760` | direct `0x56EFF0` | O | O |
| 14 | **EntityPropertyProvider** (C: `EntityPropertyProvider.cpp`, `ClassPropertyCollectionPropertySource.cpp`) | 0xB0 Entity | `0x15C9E38` (base `0x15B7968`) | direct, ctor `0x62A960` | container 4 properties (section 5) | **server** (0xBC, 0x6, 0x7, 0x13B ...) |
| 15 | property source, container 8 (`[ent+0x3C]`) | 0x68 Entity | `0x15B7B80` | direct `0x5748F0` | `0x1000006E`, `0x100002B7` | P |
| 16 | component-property container (container 3, `[[ent+0x40]+8]`) | 0x70 Entity | `0x15C9D28` (base `0x15B7D30`) | direct, QIs IID `8ff10fc4-...` | network modes 5-8 | server (component-held ids) |
| 20 | ? (tag Script) | 0x24 Script | `0x15C98A0` | GUID `ba6aff4e-...`, reg `0x627480`, create `0x629360` | O | O |
| 21 | **Movement component** ("C" in earlier notes; `ClientRigidBodyCharacterReplayMovementModule`) | 0x3AC Entity | `0x15C6180` / `0x15C5F80` (base `0x15B4178`) | direct, ctor `0x60A9B0` | 0xB0 movement blocks + module type, `0x100005E4` speed cap | **server** (0xB0) |
| 22 | **CDestructionComponent** (C: string `0x15CA6E4` in `0x6305A0`) | 0x84 Entity | `0x15CA670` (base `0x15B8DA8`) | GUID `4d12a164-...`, reg `0x62C310`, create `0x6302F0` | property `0x800` (0x50 destruction record), damage states (`Object_Phase1..4`) | server (state / scriptlets) |
| 24 | **0xB0 listener list** (`entity+0x60`, `0x57EAD0` registers) | 0x20 Entity | `0x15C9A58` (base `0x15B8860`) | direct | every 0xB0 | (container) |
| 32 | **Vitals** (`+0x80`, `0xAA05A0` group; LifeState `0x100000FA` at `+0x2C`) | 0xBC GameSystems | `0x1609C10` (base `0x15F9780`) | GUID `65bb0db1-...`, reg `0xAA1250`, create `0xAB0B40` | **0x42 vitals**, LifeState, health / Will stats | **server** |
| 33 | **Unit component** (`+0x84`, `0xAA0DC0`; ctor `0x979170`, derived `0xAAFD50`) | 0x134 GameSystems | `0x1609B78` (base `0x15F9858`) | GUID `d8e2ca0e-...`, reg `0xAA0D20`, create `0xAB0840` | team cache (`+0x4C`), PerceivedType cache (`+0xA4`), relation | server (team, flags) |
| 34 | server-object client component (`+0x88`; its update calls profiling scopes `CDialogComponent` `+0x94` and `gmCUsageComponent` `+0xAC`; `vt+0x5C(caster, 1)` is the target-visibility test of `targeting-and-relations.md`) | 0x1AC GameSystems | `0x16099D8` (base `0x15F9328`) | direct `0xAB0370`, ctor `0xAAF7F0` | dialog / usage UI of the object, visibility (P) | P |
| 35 | **gmHFSMComponent** (`+0x8C`: skill / effect / status scripts; script events 0x204E / 0x2008) | 0xC4 GameSystems | `0x16090F8` (base `0x15F9728`) | GUID `f6e52c86-...`, reg `0xAA1900`, create `0xAA9DD0` | 0x34 scripts, effect instances, cooldowns | **server** (effects, events) |
| 36 | **Floaty / combat text** (`+0x90`) | 0x20 GameSystems | `0x1609780` (base `0x15F92D0`) | GUID `0ef9eb24-...`, reg `0xAA14A0`, create `0xAA70D0` | floaty events | server |
| 39 | **Usage component** (`+0x9C`, usage / channel bars) | 0x7C GameSystems | `0x16093E8` (base `0x15F93C8`) | GUID `44876b31-...`, reg `0xAA2160`, create `0xAAA1C0` | `0x100005A6` | server (usage events) |
| 41 | **Upgrade component** (`+0xA4`, inventory / artifacts; ctor `0x978A50`) | 0x114 GameSystems | `0x1609290` (base `0x15F94A8`, second vtable `0x15F9490`) | GUID `d28b3138-...`, reg `0xAA1F30`, create `0xAAA090` | 0x212B, `0x10000A23`, `0x10000CD6`, currency | server (Character only) |
| 42 | ? (`+0xA8`) | 0x5C GameSystems | `0x1609810` (base `0x15F98C0`) | GUID `cb96bcd2-...`, reg `0xAA1D00`, create `0xAA9ED0` | PerceivedType != 0 | O |
| 43 | **CFogOfWarComponent** (P: string `0x15C6218` used at `0xAB3520`, next to its factory; also queried by the movement component `0x60B860`) | 0x20 System | `0x1609D88` (base `0x15ED4D0`) | GUID `d6c67e09-...`, reg `0xAB3A60`, create `0xAB3DC0` | vision radius `0x10000133`, team | server (radius, team) |
| 44 | ? (`+0xB0`) | 0x78 GameSystems | `0x1608F58` | GUID `c330b728-...`, reg `0xAA11B0`, create `0xAB0A40` | `0x1000076A` (a 0x40 class DID: P a pet / summon / vehicle class) | O |
| 46 | **Game physics / missile** (`+0xB8`; script nodes toggle it at missile start / end) | 0xA8 GameSystems | `0x1609520` (base `0x15F9500`) | GUID `f17b64c1-...`, reg `0xAA0F50`, create `0xAB0940` | missile flight | server (missile scripts) |
| 47 | **Agent component** (`+0xBC`, AI / pathing agent; 0x2022 / 0x2074) | 0x24 GameSystems | `0x1609448` (base `0x15F9428`) | GUID `4fd84f21-...`, reg `0xAA29A0`, create `0xAAA2C0` | `0x100008DA` | server (agent events) |
| 48 | **Status icon component** (`+0xC0`) | 0x24 GameSystems | `0x1608FA8` (base `0x15F9910`) | GUID `5ac3782c-...`, reg `0xAA12F0`, create `0xAA6FD0` | status icon events | server |

Component vtable (base `0x15B8860`, C for the slots used above): `+0x10` AddRef, `+0x14` Release, `+0x24`
OnEntityConstruction (Step 5), `+0x30` OnAttach, `+0x34` OnDetach, `+0x3C` slot id. The 0x40-byte component header:
`+4` owner entity (`comp+4`, checked by many handlers), `+0x14` u16 `0x113` (P: version / flags).

Conflict to resolve: `protocol-server-to-client.md` 1 lists `+0x58` as "appearance"; by this analysis `+0x58` is
the destruction component and appearance is slot 6 (`+0x18`). The handler that reads `+0x58` should be rechecked
(O).

---------------------------------------------------------------------------------------------------------------------

## 5. The property system

Descriptors, kinds, containers and network modes: `properties-complete.md` (C). What this pass adds:

- **Lookup order on an entity** (container 4, C): entity `0x58B320` -> slot 14 `vt+0x4C` = `0x62A4E0`: (1) the
  client override hash at component `+0x90..+0x9C` (local / predicted values; an entry with a value returns it,
  an entry without one falls through to the sources), (2) the entity's own table (`0x576070` -> `0x44AEC0`), (3)
  `vt+0x58` = `0x573340`: two **class property sources** at `+0x30` and `+0x34`
  (`ClassPropertyCollectionPropertySource`: the class record / world state chain; P which is which). So a value the
  server does not send is read from the template; sending it overrides the template for this object only.
- Descriptors with flags `0x10000` route `get` / `set` to a registered handler (`0x4FFE90(id)`), not the table.
- Writes: network `0x6` / `0x7` / `0x13B` set one id (slot 14 `vt+0x50` -> `0x578DE0`), `0x86` / `0x129` / `0x13C`
  remove (`vt+0x54`), `0xBC` / `0x13D` set a table (`vt+0xA4` `0x62AFD0` / `vt+0xA8` `0x62B1C0`; `0x62B1C0` keeps
  mode-9 values across a full replace). Local writes go through `0x62B450` (refuses modes 1, 2 and mode 4 on
  non-player entities).
- Listeners: `0x58BA40` (register, by container), `0x58BCA0` (unregister); component listeners via `0x573B60` +
  `vt+0x4C`; change notification extra `0x575B90` for descriptors with flag bit 2. Game code wraps them in
  `PropertyMonitorCallback` (`game/shared/system/propertymonitor`).
- Data records use the same ids in their own collections (0x48 / 0x49 / world states / 0x1D tables) through
  `0x44AEC0`; the scriptlet VM binds action fields either to the scriptlet's variable table or to the target entity's
  property (`0x51CD90`).

### 5.1 What the server must send per object kind

All: event `0x4` with `0xF2` (class DID; parent IID 0), `0xB0`, `0xBC`. "Template" = the value comes from the class
/ world state and need not be sent unless it changes. Ids in **bold** are server-authoritative (network mode 1 / 2)
or decide which components exist at creation (they must be right in the first bundle).

| Kind | Class sent | `0xB0` | Properties in `0xBC` (first bundle) | Later | Components that exist |
|---|---|---|---|---|---|
| **Champion** (player's agent) | variant `0x40......` (its 0x49 template, 0x510 world state, creation type 7) | movement module (mobile) | **`0x1000009C`** team, **`0x100000FA`** LifeState (4 alive), **`0x10000167`** level, **`0x10000142`** XP, `0x100001AF` skill points, `0x1000035E` currency, `0x3CE` / `0x10000433` name, icons `0x10000384` / `0x10000337` / `0x10000338`, `0x10000064` controlling player IID, `0x100005E4` move speed (else the walk cap is 0), `0x100000AF` rank array, stat f32s, `0x100008F0/F1` stolen-power tables, `0x10000A23` may shop, `0x10000CD6` item count, `0x10000133` vision radius; PerceivedType is `Character|Player` from the template | 0x42 vitals, property updates, 0x8D, 0x212B, effects | all engine + game 32-36, 39?, 41, 42, 43, 46, 47?, 48 |
| Local player object (`0x0200000000000001`) | player class | none | `0x956` lighting, `0x100000CF` controlled agent; `0x100001D3` encounter (only as a change) | | (player system) |
| **Unit / minion / creature** | entity class `0x40......` (template gives PerceivedType `Minion` 0x10000 / `Creature`, creation type 7) | movement module | **team, LifeState 4**; `0x1000019D` only if the template lacks it (it decides the game components); `0x100007A2` side for layout units; `0x100005E4` from the world state | 0x42, 0xB0 moves, 0x8D (`_Entity_OnEnterWorld_Default`, `_Defeat_*`) | vitals, floaty, status icons, unit, HFSM, fog (mobile), agent if `0x100008DA` |
| **Structure** (turret, core, dampener, foundry) | entity class (template: PerceivedType `Turret` / `Base` / `Inhibitor`, creation type 8) | module `0x62 | 1 | 1` with a valid Position (else never placed) | team, LifeState | 0x42 (they have vitals), destruction phases (scriptlets / `Object_Phase*`) | vitals etc.; destruction (slot 22) if the class has `0x800` |
| **Prop / door / gate / environment object** | entity class when there is one (door `0x40000B0F`, power core), else bare world state with `0x50F = 8` in `0xBC` | module **required** (only mobility-2 objects have a movement component; nothing else places a network object) | none required; doors are `Deco` (0x2000): **no vitals component, never send 0x42** | 0x8D (`Object_Open` / `Object_Closed`, `Vfx_*`), `0x1000065C/D` environment state (P) | engine only (+ unit / HFSM / physics game comps if class 0x40) |
| **Missile** | its entity class (PerceivedType `Missile` 0x20) | module, moves | team (relation / hit), owner (P) | 0xB0 path, 0x3 at the end, `_Missile_OnExpired` | game components (Missile is in CreateGameComponents) |
| **Pickup / loot** | entity class (PerceivedType `Loot` 4) | module | team if any | 0x3 when taken | engine + unit / HFSM / physics game only: **no vitals / floaty / status** |
| **Marker / capture point / objective** | world state or class (`CapturePoint` 0x80000 has game components; `Objective` 0x200 does not) | module | team / bias properties of the objective (`_CapturePoint_OnTeamBiasChanged`) | scriptlets | as per flags |
| Cinematic actors | none (client creates them from the 0x35 record) | | | 0x20F5 (+ bindings) | client-local |
| Landblock statics | none (client places them from 0x82 records) | | | 0x8D by IID (top byte 1) possible | client-local |

Never send: container 7 (computed) ids, mode-0 ids the client computes itself (relation `0x10000425`, team colour
`0x100007A2`-derived colours ...), properties of components an object does not have (a message to a missing
component crashes or is dropped).

---------------------------------------------------------------------------------------------------------------------

## 6. Animation, behaviour graphs and Havok

- **Component**: slot 1 (`entity+4`), class factory GUID `08aa097e-4f382d29-cc070e9d-8aca0d7a`, CreateInstance
  `0x610200`, vtable `0x15C6D30`. Exists only with scriptlet / cinematic tables (4.2). `vt+0x58` raise event
  `0x55BD30` (queue `+0xA4..+0xAC` until `vt+0x50` says ready; deliver `0x55AF70`); drop rule in 0 #7. (C)
- **Data**: 0x1A Havok packfiles (type 0x0F, behaviour graphs / clips), 0x1C object behaviour graphs (type 0x1F),
  0x1F behaviour Lua (type 0x50, Havok Script), 0x36 skeleton / ragdoll packfiles (type 0x03), enum `0x300000A4`
  for the global event names, per-graph enums map them to graph events. Packfile reader: `hkBinaryPackfileReader`,
  versioning `hkVersionPatchManager`. (C)
- **Update**: `AnimationManager 0x55C040` walks its graphs every frame, accumulates dt at graph `+0x38`, and when the
  frame stamp `[0x1B77A90]` changed calls `0x55B500` (behaviour generate `hkbBehaviorGraph::generate`, attachment
  manager). (C)
- **Physics**: slot 0 PhysicsComponent (Havok rigid body / character; mobile objects need a convex shape), the
  physics world manager `[0x1B68040]`, simulation `0x409F10` / `0x5AFEE0` (section 12), Havok continuous /
  multithreaded simulation and MOPP / BV compressed mesh shapes for the level. Cloth (`hcl*`) for capes. (C names)
- Server: only graph events (scriptlet `0x100001E3` + `0x780`, or data scriptlets that raise literal events) and
  the movement state; everything else is local.

## 7. VFX, particles, attachments

- **EffectsComponent** (slot 3): attaches particle systems (0x18 PSDesc, type 0x1A) to holding locations / bones of
  the model; two variants (with / without destruction data `0x800`). Persistent scriptlet actions (type 0x11
  particle, meshes, child scriptlets) are its attachments; they live until the scriptlet run ends or the object is
  destroyed (`client-scriptlets-graphs.md` 1.4). (C / P)
- Render-side effect managers: `StreakEffectManager.cpp`, `BeamEffect.cpp`, `LensFlareEffect.cpp` (0x08 records),
  decals (`DecalsRendered`), `gmTargetFXManager 0xA56B70` (target / click effects, e.g. move marker effects
  `0x1000005C`, `0x10000F52`), floaties (slot 36), `AfterEffect.cpp` (post effects). (C names)
- Attachment of whole entities: slot 7 (0xB0 flag 0x04 parent IID) and the cinematic's appearance copy. (C)
- Server: scriptlets (0x8D) and status effects; never particles directly.

## 8. Camera and input (local, C for names)

- Camera records 0x21 (type 0x10, tag Camera), camera component at `[0x1B73518]+0xDC`, `gmCameraSystem 0xA56850`
  (follows the controlled agent; places its camera entity with `SetEntityFrame 0x588290`), isometric camera
  options (`IsometricCamera.TargetPositionLerpScalar`, CameraLocked / ScrollSpeed / ScrollDamper / Shift While
  Locked, shake), flight / debug camera (`FlightCamera.*`). Cinematics take the camera over (`0x20F5`). Server
  influence: notices `GM_Camera.RecvNotice_CameraLocked(Preference)` (local), the controlled agent (`0x100000CF`),
  cinematics.
- Input: `CInputManager.cpp` (`0x603450`), DirectInput + XInput, key map `%s\infinitecrisis.keymap` (devices,
  meta keys, bindings, activation types; the format is documented in the exe's own comment block `0x15C3250`),
  input contexts suppressed by notice `EM_UI.RecvNotice_Suppress_InputMap`. Orders go out as 0x20EE etc.
  (`client-movement.md`).

## 9. Audio (Wwise)

- Wwise is statically linked (`AK::SoundEngine::{LoadBank, PostEvent, SetRTPCValue, SetState, SetSwitch,
  RegisterGameObj, SetPosition, SetListenerPosition, RenderAudio}` at `0xFE4000-0xFEA100`; Ghidra's FID also puts
  `AK::MemoryMgr::*` names on hundreds of unrelated helpers, ignore those). (C for the SDK functions' callers, P for
  names)
- Game audio layer `0x824000-0x82A000`: per-entity game objects (`RegisterGameObj` via `0x825E80`, unregister
  `0x8252A0`), positions (`0x8257B0`, `0x825EE0`), listener + render (`0x825730`), switches `0x825350`, banks
  `0x825160` (load) / DB type 0x56 sound bank records (prefix 0x52, create `0x826DD0`), entity properties read for
  sound parameters (`0x825F30`, `0x826110` via `0x58B320`), two registry classes (`0x824E20`, `0x825C60`).
- Ids are FNV-1 32 of lower-case names; banks load with the packs that carry them; music is the client's
  `CEncounterEnvironmentSystem` (`cinematics-vfx-audio.md` 4). Server: correct state (life state, teams, game
  events), scriptlets with sound actions, cinematics, announcer `0x2039`. No raw "play sound" message is known.

## 10. The DB / resource system (completes `db-types.md`)

- **Packs**: `10PR` files (`rp\0xA0......rp`), zlib, id list + data; a pack is itself a DB object (type 0x12 / 0x34,
  prefix 0xA0 / 0xA1); `gmConnectionManager::LoadParentRPs 0xA99370` loads what the server names (0x20AF).
- **DID -> type**: `[0x1B68F34]` `vt+0xC` (wrapper `0x5DFB80`), built by `0x5E0360` (78 ranges, 112 prefixes).
- **Type -> class**: `0x9E0260` registers 73 `{create, unpack, construct-in-place}` triples (`0x9E5DA0`); all 73 are
  reachable from a prefix (checked against the prefix table: no orphan type). The third callback constructs the
  object in a pre-reserved arena (`param+0x30` bump pointer; e.g. `0x9D96D0` for type 2) (C).
- **Cache / loader**: `0x43CE00(mode, {type, did}, arg)`: type object `vt+0x44`, cached instance `vt+0xA0`, else
  async loader state (`0x43B7E0`; `+0xB4` flags 2 = may create, 4 = done) and create + load (`vt+0x98`), refcount
  (`vt+0x10`); `mode == 4` returns without waiting for `vt+0x30` "ready". Errors are logged with `DBCache.cpp` and
  lines 0x232 / 0x23E (`0x43E0E0`). `DBResolver.cpp` / `ReferenceTable.cpp` resolve DID references inside records
  (P).
- **Record headers** (C, project): world state `did | 7 | .entity | 0 | count | entries`; others `did | 0 | count |
  entries`; property values by the descriptor's kind (`0x509740`).

| Group | Prefixes (DB type) | Loader / unpack | Server relevance |
|---|---|---|---|
| Entities | 0x40-0x47 (0x40 entity class), 0x49 (0x29 templates), 0x2E (0x2D world states), 0x2D (0x0B `.entity`), 0x37 (0x3D), 0x50 (0x4E destruction / entity data, `0x800`) | `0x47B080`, `0x509B90`, `0x581210`, `0x632A20`, `0x6DA6F0`, `0x4E42E0` | class ids the server sends |
| Data records | 0x48-0x4F (0x29 property collections), 0x83 (0x21) | `0x509B90` | skills, statuses, configs (server reads) |
| Scripts | 0x34 (0x07), 0x3A (0x3F), 0x3B (0x08), 0x3C (0x4D), 0x3D (0x51), 0x3F (0x53), 0x1D (0x22 DBScriptTable), 0x1E (0x15) | `0x44ECE0`, `0x44AD60`, `0x46A140`, `0x461DB0`, `0x537080`, `0x535F70` | server runs 0x34; client runs scriptlets |
| Names | 0x30 (0x48 EnumMapper), 0x31 (0x44), 0x32 (0x1E MasterProperty), 0x33 (0x02), 0x2B (0x19 StringTable) | `0x4C34C0`, `0x443850`, `0x502750`, `0x9D6D70`, `0x5A90A0` | |
| Animation | 0x1A (0x0F), 0x1C (0x1F), 0x1F (0x50), 0x36 (0x03) | `0x55D120`, `0x55D8E0`, `0x556ED0`, `0x557030` | |
| Render | 0x10-0x17, 0x19, 0x24, 0x25, 0x08 | see `db-types.md` | |
| World | 0x80-0x82, 0x85, 0x90-0x9F, 0x01-0x07, 0x0F, 0x23, 0x39, 0xF7-0xFF | | map packs |
| UI / audio / cinematics | 0x20 (0x31), 0x27 (0x1D), 0x52 (0x56), 0x35 (0x3E), 0x21 (0x10) | | |

## 11. Network objects vs client-local objects (summary)

| Created by | How | IID | Placed by |
|---|---|---|---|
| Server bundle (0x4) | `0x64D8A0` -> factory | top byte 2 (server) | movement component (slot 21) on 0xB0 with module, else never |
| Landblock statics | `BlockEntities 0x53DA40` from 0x82 records | top byte 1 (`0x4DB130`) | `SetEntityFrame` directly |
| Cinematic actors | `0x6A5AE0` | `0x81000000_00000000 | n` | render position + flag `0x40` |
| Client script nodes / FX | various (`0x683E38`, `0x750820`, `0x752BDD`, `0x7EAE57`) | local | render position |

## 12. Time and tick (C unless marked)

- Frame: `0x410B30` = one frame: clock update `0xAFE080` (`[0x1B77A90]` f64 seconds, `[0x1B77A98]` second value
  from the clock object `[0x1B77A88] + 0x18 / 0x1A`), `UpdateSystem__UseTime` (input / systems), physics manager
  creation `0x409810`, **fixed-step simulation `0x409F10`**, rendering (`Graphics` / `Frame` scopes, `0x7D2B40`,
  `0x7A6B60`, `0x7D2C40`, `0x7A6CE0`), presentation / late updates (`0x4134F0`, `0x68B8B0`, `0x633370`).
- Fixed step (`0x409F10`, object fields): `+8` step length, `+0xC` max frame delta, `+0x10` / `+0x18` previous / next
  step time, `+0x28` interpolation alpha 0..1, `+0x2C` "inside a step"; runs `UpdateSimulation` once per step,
  resets after long stalls (`0x5AD770`), `OnTickBefore/AfterUpdateSimulation` hooks (`0x5B0010`, `0x5B0090`).
- `UpdateSimulation 0x5AFEE0`: tick groups at `+0x34` (count `+0x3C`, stride 0x48): period in steps (`[3]`), next
  step (`[4]`), dt (`[5]`), accumulated time (`[8]`), listeners (`[0xE]`, count `[0x10]`) called `vt+8(group id,
  dt)`, cost in ms (`[0xC]`).
- `GameTime.cpp`: console commands `GameTime.SetTemporalDilation`, `GameTime.SetTimeOfDay` (`0x4C4E80`,
  `0x4C4FA0`, `0x632DE0`).
- Network time: message `0x1000000` (BE f64) both ways (server every 2 s, or the client drops the game connection
  after 60 s); time properties (kind 4) and 0xB0 state times are on the game clock (`client-movement.md`).
  `0x10000076` TimerClockSync and `0x10000109` SetMatchTime drive the HUD clock (P).

## 13. Open points

- Slots 8, 13, 20, 42, 44: names and roles; slots 10, 17, 18, 19, 23: who creates them (not the factory).
- Entity flag `+0x118` bit `0x40`: who sets it (graph events are dropped while it is set and bit 8 is clear).
- `+0x58` "appearance" in the protocol note vs slot 22 = CDestruction.
- The two class property sources (`+0x30` / `+0x34` of the provider): which one is the class template and which
  the world state.
- The creation-type enum `0x30000037` names (the exe names three: UniqueDynamicMobile, UniqueDynamicImmobile,
  UniqueClientOnlyImmobile); the enum record was not found in the core packs' first 8 000 ids.
