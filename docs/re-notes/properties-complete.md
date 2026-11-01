# The complete property dictionary (static analysis, 2026-10-22)

Client `InfiniteCrisis.exe` (sha256 463adfff...), install `C:\Infinite Crisis Server`. Machine-readable table:
`docs/re-notes/properties-complete.tsv` (3 822 rows, one per descriptor; columns `id, name, kind_code, kind,
container, default, flags, readers, meaning, confidence`). C = confirmed (read from code / data), P = probable.

## 1. Where the descriptors come from (C)

- **There is no registration code.** The client registers no property in C++: every descriptor is read from the
  single **MasterProperty** record **`0x32000000`** (DB type 0x1E, tag "MasterProperty", source file
  `engine/shared/property/MasterProperty.cpp`), in core pack **`0xA0000039`**, 97 784 bytes. Error strings in the
  exe call this file "the .mpr".
- **Unpack `0x502750`**: `u32 DID`, then a list of `u8 tag` + descriptor until tag 0. `0x4FF020(tag)` allocates the
  descriptor class: tag `1` / `2` / `3` (vtables `0x15AF078` / `0x15AF0F0` / `0x15AF168`) and `0x81` / `0x82` /
  `0x83` (vtables `0x15AF328` / `0x15AF3A8` / `0x15AF420`, the same three with default values); each one's
  vtable slot `+0x6C` reads its body (`0x4FDFE0`, `0x4FFDA0`, `0x4FE250`, `0x509C40`, `0x509D00`, `0x509DD0`).
  Descriptors go into the manager's hash map (`0x502090`; lookup **`0x4FEE60(id)`**: buckets at `+0x2C`,
  node `+4` next, `+8` id). The table is resized to the descriptor count (`0x5019E0`).
- **Archive rule** (C, the whole record parses to its exact end with it): in this record **every read
  occupies a multiple of 4 bytes** (a `u8` read takes a whole word); enum, int and u32 values are one word.
- **Descriptor body** (all tags), and the in-memory descriptor:

| stream | descriptor field | meaning |
|---|---|---|
| `u32 w0` | `+0x08` id = `w0 & 0xFF00FFFF`; `+0x0C` kind = `(w0 >> 16) & 0xFF` | id and value kind (C) |
| `u32 w1` | `+0x10` u16 "grp" (raw), `+0x12` u8 **container**, `+0x13` u8 (0 or 0x10, raw) | container selects the storage (C, section 2) |
| `u32 w2` | `+0x14`; byte `+0x16` = **network mode** | replication (C, section 3) |
| `u32 w3` | `+0x18` flags (bits below) | |
| tag 2 / 0x82: `u32` | `+0x1C` reference | kind 8 / 0x13 / 0x0D / 0x0F: **EnumMapper `0x30......`** of the value names (C: 603 of them); kind 0x0A: `0x32000000` or `0x31000007/08/14` (P: enum of another table) |
| tag 3 / 0x83: `u8, u8` | `+0x1C` DB type, `+0x1D` flags | only kind 0x15 DIDs: the **DB type the DID must point to** (e.g. 0x29 = property collection 0x48.., 0x09 Texture, 0x40 entity class, 0x2C model part); see `db-types.md` (C) |
| tags 0x8x only | `+0x1C/+0x20/+0x24` (shifted by 4 for 0x82/0x83) | if flags bit `0x800` the **default**, bit `0x1000` the **minimum**, bit `0x2000` the **maximum**, each read by the kind's value reader **`0x507D60`** (simple kinds) / **`0x507590`** (complex kinds) (C: e.g. f32 `0x81` default 0.1, min 0, max 1) |
| tags 0x8x, flags bit `0x200000` | a member set (`0x503BD0` -> `0x5031A0`): `u8 size class, compact count, count x u32 id` | for kind 0x0B tables the **allowed member properties**, for 0x0C arrays the **element property** (C: 2 082 of 2 089 ids are descriptors themselves; e.g. `0x10000564` array -> elements `0x10000696`, the skill slot tables `0x100008E8..F2` -> 57 skill keys) |

  Tags `1/2/3` with flag `0x800` carry no stored default (zero value, P).
- Counts: 3 822 descriptors (tags: 1 816 x `1`, 939 x `0x81`, 589 x `2`, 408 x `3`, 61 x `0x82`, 9 x `0x83`);
  1 747 engine ids `< 0x10000` and 2 075 game ids `0x10000001-0x10000DE3`. `tools\diag.py --props` dumped the same
  3 800+ descriptors from memory; the kinds agree with the catalog for every id.

### Accessors of a descriptor (C)

`0x4FB670` kind (`+0x0C`), `0x4FB680` `+0x10` word masked `0xFF00FFFF`, `0x4FB6A0` container (`+0x12`),
`0x4FCE30` id; flag predicates: `0x4FB600` `+0x18` bit 1, `0x4FB630` bit 2 (on set, extra notify `0x575B90`),
`0x4FB650` bit 3, `0x4FB620` `+0x1A` bit 0 (= flags `0x10000`: the set is routed to a registered handler
`0x4FFE90(id)` instead of the table, `0x578DE0`), `0x4FB4E0` flags `0x80000`, `0x4FB500` flags `0x100000`;
network predicates on `+0x16` (section 3). A script binding block at `0x6B85F0..` (functions `0x490700..0x490B60`,
script ids `0x2900xx`) exposes these predicates to the script VM. The mask `0x14F8DA` marks the kinds held by
reference (1, 3, 4, 6, 7, 0x0B-0x0F, 0x12, 0x14).

## 2. Containers (byte `+0x12`) (C)

The entity dispatcher **`0x58B320`** (get), **`0x58BA40`** (register a change listener; container via `0x4FEEF0`),
`0x58BCA0` (unregister) and `0x62B450` (local set) pick the storage by the container byte:

| container | count | storage | notes |
|---|---|---|---|
| 4 | 3 559 | object property table **`[ent+0x38]`** (vtbl `+0x4C` get, `+0x6C` listen) | what the server's object-creation / property-update messages fill. `0x588820` (minimap) reads only this one |
| 3 | 135 | component **`[[ent+0x40]+8]`** (vtbl `+0x2C`, listen via `0x573B60` + `+0x4C`) | component-held properties; network modes 5-8 only occur here |
| 8 | 2 | **`[ent+0x3C]`** (`0x1000006E`, `0x100002B7`) | |
| 7 | 24 | computed provider (`0x58AA80` source, `+0x28` get, `+0x34` listen) | values derived by the client; never send them |
| 6 | 102 | **not handled** by `0x58B320` / `0x58BA40` (P: volume / surface / attachment property sources, `MonitorVolumePropertySource.cpp`, `SurfacePropertyProvider.cpp`) | entity reads return "not found" |

The container is a property of the id, not of where a value comes from: data records (0x48 skills, 0x49
templates, world states) store any id in their own property collections (`0x44AEC0` lookup); the container
only matters when the value sits on an entity.

## 3. Network mode (byte `+0x16`) and what the server may set (C for 1-4, P for 5-9)

Strings in `0x62B450` (local set): *"Attempting to set a NetSharedVisually or NetSharedPrivately property ... on
the client. This is not allowed, because these are server-authorative"* (modes 1, 2) and *"... NetPredicted
SharedPrivately property ... on something other than the player"* (mode 4). Predicates: `0x4FB520` {1,3}
(visually), `0x4FB560` {2,4} (privately), `0x4FB580` {3,4} (predicted), `0x4FB5C0` {5,6}, `0x4FB5A0` {7,8},
`0x4FB5E0` {6,8}, `0x4FB540` {9}.

| mode | count | name | meaning for the server |
|---|---|---|---|
| 0 | 3 478 | local / not replicated | the original server did not replicate it; the client computes it (e.g. relation `0x10000425`, team colour `0x100007A2`) or it only lives in data records. The network reader (`0x509740`, by kind) still accepts any id (P) |
| 1 | 213 | NetSharedVisually | **server-authoritative, sent to everyone** (PVP_Team `0x1000009C`, Level `0x10000167`, XP `0x10000142`, `0x100000CF`, `0x100005E4`, Name `0x3CE`, ...) |
| 2 | 15 | NetSharedPrivately | server-authoritative, sent to the owner only |
| 3 | 19 | NetPredictedSharedVisually | client may set it locally (prediction), server confirms |
| 4 | 5 | NetPredictedSharedPrivately | as 3, owner only; client refuses on non-player entities |
| 5 / 6 | 49 / 31 | component Net(Shared) Visually / Privately (P, by the predicate pairs) | component container (3) |
| 7 / 8 | 3 / 6 | component predicted variants (P) | component container (3) |
| 9 | 3 | kept across a full refresh (P: `0x62B1C0` saves mode-9 values before replacing the whole table and puts them back) | `0x100001AF` SkillPoints, `0x100006B4`, `0x10000D88` |

The full id list per mode is in the TSV (`flags` column, `net=`). Ids with mode 1/2/5/6 are exactly the ones a
server is expected to send; the client never produces them itself.

## 4. Kinds (C)

| code | kind | value in this archive / reader |
|---|---|---|
| 0x01 | ascii | `u32 len, bytes padded to 4` (`0x4FEAC0`) |
| 0x02 | ? | 3 descriptors (`0x2A`, `0x278`, `0x71E`), no default stored |
| 0x03 | frame | `u8 type`; type 1: `u32` (cell); else 11 x u32 + u32 + u8 (`0x4D1B80`) |
| 0x04 | time | 8-byte double, relative to the game clock unless flags bit 0x10 (`0x505CE0`) |
| 0x05 | byte | 1 byte (`0x4FD900`) |
| 0x06 | vector3 | 3 x f32 |
| 0x07 | iid | 8 bytes |
| 0x08 / 0x0A | enum | 1 word here (`0x4FEB20`: top byte + compact int on the wire); EnumMapper in `+0x1C` |
| 0x09 | f32 | 4 bytes |
| 0x0B | table | `u8 size class, compact count, entries` (`0x503330`) |
| 0x0C | array | `u32 count, (u32 key, value)...` (`0x501290` -> `0x509740`) |
| 0x0D | bit field | compact bit count + bytes (`0x500750`) |
| 0x0E | string | StringInfo (`0x5A9580`) |
| 0x0F | qword | 8 bytes |
| 0x10 | int | compact int on the wire (`0x421430`), 1 word here |
| 0x11 | **colour** | u32 ARGB, unpacked to 4 floats (`0xAF3B00`) |
| 0x12 | position | Position (`0x47C610`) |
| 0x13 | u32 | 4 bytes (bit flags, 62 of them with an EnumMapper of flag names) |
| 0x14 | did64 | 8 bytes |
| 0x15 | did | 4 bytes; tag 3 gives the target DB type |
| 0x16 | bool | 1 byte (`0x449520`) |

## 5. Names (C)

The client ships **almost no property names**. The only id -> name table is the Scaleform UI's constant classes
(`emp_gen.gmCharacterPropertyList`, `gmAdvancementPropertyList`, `gmPVPPropertyList`, `gmUpgradePropertyList`,
`gmPerceptionPropertyList`, movie `0x20` in pack `0xA00000D0`): **37 names** (36 ids + `Invalid_Property` = 0),
plus `Name_Property` `0x3CE`. The exe names three more in log strings only (`CollisionLayer_Property`,
`PhysObj_Property`, `InMatchTraining_Type_Property`), with no id next to them. The pack name tables
(enum `0x30000013` with 3 710 names and five smaller ones in `0xA0000038`, one in `0xA00000B3`) are **scriptlet
keys and graph events**: 1 712 of their ids collide numerically with property ids but name different things
(e.g. `0x10000433` is `Character_Name_Property` and also scriptlet `Vfx_Jkr_Death_A`). No other source of names
exists in the install, so the `name` column is empty for 3 784 rows; the `meaning` column carries the catalog's
own description where it has one.

| id | name | kind | net |
|---|---|---|---|
| 0x000003CE | Name_Property | string | 1 |
| 0x10000064 | Character_ControllableAgentToPlayer_InstanceID_Property | iid | 1 |
| 0x1000009C | PVP_Team_Property | int | 1 |
| 0x100000CF | Character_PlayerToControllableAgent_InstanceID_Property | iid | 1 |
| 0x10000142 | XP_Property | int | 1 |
| 0x10000167 | Level_Property | int | 1 |
| 0x1000019D | PerceivedType_Property | u32 | 1 |
| 0x100001AF | SkillPoints_Property | int | 9 |
| 0x100001FC | Character_Billboard_Icon_Property | did | 1 |
| 0x10000337 | Character_LargeIcon_Property | did | 0 |
| 0x10000338 | Character_ConsoleVitals_Portrait_Property | did | 0 |
| 0x1000035E | Upgrade_Currency_Property | f32 | 0 |
| 0x10000384 | Character_SmallIcon_Property | did | 0 |
| 0x10000433 | Character_Name_Property | string | 0 |
| 0x10000434 | Character_Description_Property | string | 0 |
| 0x10000575 | Character_CharSelectVO_Property | enum | 0 |
| 0x100005B0 | Character_WallpaperImage_Property | did | 0 |
| 0x100005E8 | Character_ActiveAgent_InstanceID_Property | iid | 1 |
| 0x100005EE | Character_Role_Description_Property | string | 0 |
| 0x100005F2 | Character_Role_Name_Property | string | 0 |
| 0x10000778 | Character_About_Property | string | 0 |
| 0x10000779 | Character_Powerset_PlayStyle_Property | string | 0 |
| 0x1000077A | Character_Alignment_Property | string | 0 |
| 0x1000077B | Character_Multiverse_Property | string | 0 |
| 0x1000077C | Character_Powerset_PowerBar_Property | int | 0 |
| 0x1000077D | Character_Powerset_HealthBar_Property | int | 0 |
| 0x1000077E | Character_Powerset_DifficultyBar_Property | int | 0 |
| 0x1000077F | Character_Skin_Name_Property | string | 0 |
| 0x10000780 | Character_Powerset_AttackBar_Property | int | 0 |
| 0x10000799 | Character_MiniWallpaperImage_Property | did | 0 |
| 0x10000C58 | Character_Turntable_Movie_Property | string | 0 |
| 0x10000C87 | Character_Portrait_Audio_Stop_Property | enum | 0 |
| 0x10000C88 | Character_Portrait_Audio_Property | enum | 0 |
| 0x10000CA2 | Character_Superbanner_Audio_Property | enum | 0 |
| 0x10000CD6 | Upgrade_CurrentItemCount_Property | int | 0 |
| 0x10000D40 | Upgrade_Facade_Property | iid | 1 |

The `Character_*` ones are read with `InqPropertyDID` from the champion **record**, not from an
entity; the server does not send them.

## 6. Who listens: HUD, world UI and Flash (C)

### 6.1 Exe listeners (`0x58BA40(ent, id, watcher, notify)`)

All 126 call sites were decoded (argument 2 = id); 107 pass an immediate, the rest come from tables (the unit
component `0x977490` table: `0x1000009C`, `0x10000715`, `0x10000133`, `0x1000019D`, `0x1000063E`, see
`targeting-and-relations.md`). Function = containing function (heuristic start). Net = mode; Cont = container.
Rows marked **S** are server-authoritative (mode 1/2/5/6) or predicted (3/4/7/8) and are listened by UI code
(0x85xxxx-0xACxxxx): **the server must send them and send every change**.

| id | kind | net | cont | listening functions | |
|---|---|---|---|---|---|
| 0x00000021 | bool | 1 | 4 | 0x60D410 | S |
| 0x000003CA | u32 | 1 | 4 | 0x560010 | S |
| 0x0000044D | bool | 3 | 4 | 0x559980 | S |
| 0x000005E5 | array | 1 | 4 | 0x623540 | S |
| 0x000002A1, 0x000003CB, 0x000006AD, 0x0000070B, 0x00000765, 0x00000766, 0x000007A3, 0x000007BB, 0x000007EC | - | 0 | 4 | 0xA5B190, 0xA16730, 0x60D410, 0x623540, 0x552D10 | engine-side, local |
| 0x10000029 | bool | 1 | 4 | 0xA4EF00, 0xA5D250 | S |
| 0x10000083 | did | 1 | 4 | 0xA4B150 | S |
| 0x1000009C PVP_Team | int | 1 | 4 | 0xA4B150, 0xA5A7E0, 0xAB12C0, 0x977490 | S |
| 0x100000AF | array | 3 | 4 | 0xA824E0 | S |
| 0x100000CE | bool | 0 | 4 | 0xAA6270 | |
| 0x100000CF | iid | 1 | 4 | 0x8764C0, 0xA256F0 | S |
| 0x100000FA | enum | 1 | 4 | 18 UI functions (0x85EA30, 0x968DA0, 0x96C6B0, 0xA0EB20, 0xA16730, 0xA168F0, 0xA174F0, 0xA3A840, 0xA4B150, 0xA5B190, 0xA5D120, 0xA5D250, 0xA7CA20, 0xA8C0B0, 0xAB01D0, 0xAB12C0, 0xAC0DC0, 0xAC4600) | S (most-watched) |
| 0x1000011E | f32 | 3 | 4 | 0x968DA0 | S |
| 0x10000133 | f32 | 0 | 4 | 0x977490 (attack range) | data |
| 0x10000167 Level | int | 1 | 4 | 0x977490, 0xA824E0 | S |
| 0x1000019D PerceivedType | u32 | 1 | 4 | 0xAAA5C0, 0x977490 | S |
| 0x100001AF SkillPoints | int | 9 | 4 | 0xA8C770 | S |
| 0x100001D3 | did | 8 | 3 | 0xA0CBC0, 0xA0F0F0, 0xA5AAA0, 0xA85BF0 | S |
| 0x100002B7 | enum | 1 | 8 | 0xA5A7E0 | S |
| 0x100002EB | did | 1 | 4 | 0xA85BF0 | S |
| 0x1000035E Upgrade_Currency | f32 | 0 | 4 | 0xA8C770 | (P: still server data) |
| 0x100003A7 | f32 | 3 | 4 | 0x9678C0, 0x968DA0 | S |
| 0x100003F3 | bool | 1 | 4 | 0x85EA30 | S |
| 0x10000456 | int | 1 | 4 | 0xAA43A0 | S |
| 0x10000459 | bool | 1 | 4 | 0x96C6B0 | S |
| 0x1000047B | f32 | 0 | 4 | 0xAA43A0 | |
| 0x10000484 | f32 | 1 | 4 | 0xAA6D60 | S |
| 0x100004DA | enum | 1 | 4 | 0xA5B190 | S |
| 0x100004E2 | iid | 1 | 4 | 0x8531B0 | S |
| 0x100004FF | enum | 1 | 4 | 0x96E4E0, 0xA4B150, 0xAA42A0 | S |
| 0x10000548 | enum | 1 | 4 | 0xA4B150, 0xA5B190 | S |
| 0x10000556 | enum | 3 | 4 | 0xA5A7E0 | S |
| 0x10000587 | int | 1 | 4 | 0xA5B190 | S |
| 0x100005E4 | f32 | 1 | 4 | 0x977490 | S |
| 0x100005E8 | iid | 1 | 4 | 0xA256F0 | S |
| 0x1000063E | bool | 0 | 4 | 0x977490 | |
| 0x1000065C | enum | 8 | 3 | 0xA5A7E0 | S |
| 0x1000065D | enum | 0 | 4 | 0xA5A7E0 | |
| 0x100006B6 | int | 1 | 4 | 0xA4B150 | S |
| 0x100006BC / 0x100006BD | bool | 1 | 4 | 0xA4B150, 0xAA43A0 | S |
| 0x10000715 | iid | 1 | 4 | 0x977490 | S |
| 0x1000072C | bool | 1 | 4 | 0xA4B150 | S |
| 0x100007C7 | bool | 1 | 4 | 0xAA43A0 | S |
| 0x100008C9 | enum | 1 | 4 | 0x8531B0 | S |
| 0x100008E3 | table | 0 | 4 | 0xA404D0 | |
| 0x10000A23 | bool | 1 | 4 | 0x96C6B0 | S |
| 0x10000B0C | array | 8 | 3 | 0xA824E0 | S |
| 0x10000B2D | bool | 1 | 4 | 9 UI functions (0x85EA30, 0xA0EB20, 0xA16730, 0xA174F0, 0xA3A840, 0xA5B190, 0xA7CA20, 0xAB01D0, 0xAB12C0) | S |
| 0x10000B52 / 0x10000B55 | array / bool | 0 | 4 | 0xA0F1D0 | |
| 0x10000C13 | bool | 1 | 4 | 0xA0EB20, 0xA174F0 | S |
| 0x10000C1D | bool | 0 | 4 | 0xA0EB20, 0xA174F0 | |
| 0x10000C5B / 0x10000C66 | bool / iid | 1 | 4 | 0xA7CA20 | S |
| 0x10000C85 | bool | 1 | 4 | 0xA8C770, 0xAB01D0 | S |
| 0x10000CD6 Upgrade_CurrentItemCount | int | 0 | 4 | 0xA8C770 | (P: still server data) |
| 0x10000D0A | bool | 1 | 4 | 0xA5B190 | S |

Register-passed listeners whose id is not an immediate: `0x52A660`, `0x530880`, `0x5561D0`, `0x559150`, `0x5648B0`,
`0x567850`, `0x85D130`, `0x972940`, `0xA07370`, `0xA9ECF0`, `0xAA2790`, `0xAA6D60` (id from a member or a table).

### 6.2 Flash (Scaleform) listeners

The UI uses `PropertySystem.RegisterForPropertyChange / UnregisterForPropertyChange / InqProperty /
InqPropertyDID` (exe side `Turbine.RegisterProperty`, `Turbine.InqProperty`, `Turbine.InqPropertyDID`,
`Turbine.SetProperty`, callbacks `PropertySystem.OnPropertyChanged / Added / Removed`). Observer classes
`gameplay.properties.PropertyObserver`, `EntityPropertyObserver`, `vitals.vitalobservers.VitalPropertyObserver`
call `InitializePropertyObservation(id, name)` which registers and then inquires. Ids used by the movies (all
through the named constants; no numeric property id is passed directly):

- **Registered for change** (`InitializePropertyObservation`): `0x3CE` Name, `0x1000009C` PVP_Team,
  `0x10000142` XP, `0x10000167` Level; compared in `OnPropertyChanged` handlers: also `0x10000064`, `0x100001AF`
  SkillPoints, `0x1000035E` Upgrade_Currency.
- **Read once** (`InqProperty` on an entity): `0x3CE`, `0x10000064`, `0x1000009C`, `0x10000142`, `0x10000167`,
  `0x1000019D`, `0x100001AF`, `0x10000338`, `0x1000035E`, `0x10000D40`.
- **Read from a record** (`InqPropertyDID`): `0x10000384`, `0x10000433`, `0x100005B0`, `0x10000778`, `0x1000077F`,
  `0x10000799`, `0x10000C87`, `0x10000C88`, `0x10000CA2`.
- Health / Will come through `InquireVital` (vitals, not properties).

### 6.3 What the server must keep updated (summary)

On the **player and champion objects**: `0x1000009C` (team), `0x10000167` (level), `0x10000142` (XP),
`0x100001AF` (skill points), `0x1000035E` / `0x10000CD6` / `0x10000D40` (upgrade shop), `0x3CE` (name),
`0x100000CF` / `0x10000064` / `0x100005E8` (player <-> agent links), `0x100005E4`, `0x10000715`. On **every unit
the HUD shows**: `0x1000009C`, `0x1000019D`, `0x100000FA` (watched by 18 UI functions), `0x10000B2D` (9),
`0x100004FF`, `0x10000548`, `0x100006B6`, `0x100006BC/BD`, `0x1000072C`, `0x10000083`, `0x100002B7` (container
8), `0x10000556`, `0x1000065C` (component), `0x100001D3` (component), `0x10000B0C` (component). The others in the
table above as needed by the feature (ping, cooldown bars, objectives). Never send container-7 ids (computed),
and the client computes `0x10000425` / `0x100007A2` from the team itself.

## 7. Readers seen (exe) (C for API calls, P for bare immediates)

The `readers` column of the TSV comes from a scan of the whole `.text` for 4-byte immediates equal to a game
property id (`>= 0x10000000`; 2 296 references) classified by the function they are passed to (depth-2 call
graph), plus an argument-exact decode of every call to the entity API:

- `listen@<sites>` / `unlisten xN`: `0x58BA40` / `0x58BCA0` (argument-exact, includes engine ids).
- `ent.get xN`: `0x58B320` (argument-exact) and its wrappers (`0x513A90` enum, `0x54FB40`, `0x54FBD0`,
  `0x556470`, `0x57FB70`, `0x61C990`, `0x85EE30`, `0x860550`, `0x860620`, `0x58D2D0`, ...).
- `rec.get xN`: typed getters on a property collection (`0x44AEC0` lookup; `0x4A95E0` bool, `0x4A97B0` f32,
  `0x4A9B60`, `0x4AA520`, `0x4A9AC0`, `0x4AA5C0`, `0x4A9A20`, `0x4AA020`, `0x4A9680`, `0x4AA470`, `0x4A9BF0`,
  `0x4AA0C0`): the id is read from a **data record** or class template, not from an entity.
- `desc xN`: code that builds a value holder or looks the descriptor up (`0x505ED0`, `0x4C07F0`, `0x4C03A0`,
  `0x58B1C0`, ...), typically before a set or a send.
- `imm xN`: an immediate passed elsewhere (P: may be a scriptlet key or graph event with the same number;
  references passed to the scriptlet runners `0x588A00` / `0x588A80`, to the string-variable builder `0x5A4E80`
  and to static initialisers `0x44E410` were excluded).
- `flash:` uses by the UI movies (section 6.2).

1 047 of the 3 822 properties have at least one reader. Engine ids (`< 0x10000`) are only listed for the
argument-exact entity calls (a bare small immediate is not attributable).

## 8. Comparison with `catalog/data/properties.tsv`

- **Coverage:** the catalog has 3 823 rows = the 3 822 descriptors + `0x100005FE`, which is **not a property
  descriptor** (it is a character attribute id read through GetAttribute; keep it, but mark it as an attribute).
  No descriptor is missing from the catalog.
- **Kind codes:** all 3 822 kind codes agree with the descriptors.
- **Kind names wrong or missing:** `0x11` is named `int64` (45 rows) but is a **32-bit ARGB colour** (`0xAF3B00`
  unpacks 4 bytes to 4 floats; `0x2A0` default `0xFFFFFFFF`). Unnamed kinds: `0x01` ascii, `0x02` ?, `0x03`
  frame, `0x04` time (double), `0x05` byte, `0x06` vector3, `0x0F` qword, `0x12` position, `0x14` did64.
- **Missing information** (now in `properties-complete.tsv`): container (all rows), network mode (all), default
  / min / max (493 descriptors store values; 1 172 rows have a default, a min/max or the "flagged, zero" default), EnumMapper of the 603 enum / flag properties, target DB type of
  the 417 typed DID properties, member / element sets of 516 tables and arrays, the 38 names, readers.
- **owner / meaning:** only 149 rows have one. They were not re-verified here; a few owner labels name a
  record where the id was seen, not its container (e.g. `0x8E` "property set / ping", container 4 in the
  descriptor; `0x300` "graph variable" is an engine property of container 4).
- **Reader impact** (`ics/records.py` takes one word for unknown kinds): in this archive kinds `0x04`, `0x07`,
  `0x0F`, `0x14` are 8 bytes and `0x03`, `0x0D`, `0x12` are variable; if a data record ever holds one of the
  kinds 0x03 / 0x04 / 0x0D / 0x0F / 0x12, a one-word read would desynchronise it (P: not seen in the records
  read so far).

## 9. Method and limits

- Descriptors: the `0x32000000` record parsed with the client's own Unpack rules (all 97 784 bytes consumed,
  ending on tag 0). Evidence functions: `0x502750`, `0x4FF020`, `0x4FDFE0`, `0x4FFDA0`, `0x4FE250`, `0x509C40`,
  `0x509D00`, `0x509DD0`, `0x507D60`, `0x507590`, `0x503BD0`, `0x5031A0`.
- Meaning of flag bits other than `0x800/0x1000/0x2000/0x200000/0x10000` and of the `grp` / `b13` bytes is not
  known; they are kept raw in the TSV. Network-mode names 5-9 are inferred from the predicate pairs (P).
- Names: only what the client ships (section 5); nothing was guessed.
