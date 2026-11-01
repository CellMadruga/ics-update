# Stubborn visuals: dampener octagon, gate rectangles, Shards sphere, stealth tile, rubble / prow (2026-10-25)

Static analysis of InfiniteCrisis.exe (Ghidra via REA, base 0x400000) and the packs, after the fase3-hr test
(test-2026-10-25-1313.md). Confidence: C confirmed (code/data read), P probable, G guess, O open.

## 1. Dampener octagon / Gotham Divided gate rectangles

### 1.1 What 0x8B1 / 0x8B2 / 0x8A3 / 0x8A5 are (C): the Kynapse obstruction prism, not a renderer

- `0x5561D0` (AIObstructionComponent init, vtable 0x15C65A8) -> `0x555E20` reads **`0x8C1` = obstruction shape**:
  1 regular prism `0x555240`, 2 `0x554EB0`, 5 `0x555820`, 6 from the physics mesh `0x588360`. The prism reads table
  `0x8B1`: **`0x8B2` = number of sides (< 13)**, `0x8A3` -> +0x4C, `0x8A5` -> +0x48 (radius / height), optional
  `0x85C` (offset) and `0x856` (yaw, degrees). `0x83C == 1` creates the component.
- The lane turret (ws `0x2E000AA0`: 12 sides, 2.0 / 0.7), core turret `0x2E000AC4` and core `0x2E0013EE` (12, 3.0 /
  3.75) carry the same group and show no octagon, so the group is **not** the cause (C). Sending `0x8B2 = 0` etc.
  would only change pathing.

### 1.2 What differs (C data)

- The dampener body `0x2E000E04` (.entity `0x2D000BAF`, rig `env_pvp_dampener_a`, graph `0x1C0000A0`) has no
  `0x357` and draws its own rig; the turret body is dressed by server-spawned parts (plate `0x2E000A9F`, head
  `0x2E000AA8`) that get Vfx_Startup + Vfx_Active_Blue/Red. The dampener gets nothing coloured.
- Its tables: class `0x7D2` = `0x1D0000E2`, `0x1D0000E1`, `0x1D0000E8`, **`0x1D000385`** (team colour base) and ws
  `0x1D0005A1` (bases `0x1D00063A`, `0x1D000600` damage phases). In `0x1D00063A`: Vfx_Active spawns child
  **`0x2E000A9E`** (type 0x0C, scale 0.75 / 0.75 / 0.5, Vfx_Startup on it) + particles switched on `0x100007A2`;
  **Vfx_AI_Active spawns the turret head hologram `0x2E000AA8`** (the original vs-AI dampener's "stacked blue
  hologram"); `_Entity_OnSetClientRelationship` runs Vfx_Active.
- Base `0x1D000385` `_Entity_OnSetClientRelationship` (0x100003A6) switches on `0x100007A2` and runs `0x10000004`
  with the team-colour keys `0x1000011D` / `0x1000011E` / `0x1000011F` / `0x10000127` / `0x10000128`. The door
  `0x40000557` (ws `0x2E000CD7`, no model, `0x8C1 = 6`, table `0x1D000461` + base `0x1D000385`) has the same path.

### 1.3 Who runs _Entity_OnSetClientRelationship (C)

- **`0xA7B0D0`** (called from the property-change listener **`0xA813F0` when `0x1000009C` (team) changes**, and
  from `0xA84370` by IID): relation = `0x853380(team, my team)` -> writes **`0x10000425`**; for team < 3 writes
  **`0x100007A2`** itself (`0x10000CF0` or `0xA95AB0(team, my team)`); then runs 0x100003A6 on the entity with
  variables `0x100004A8` = relation (u32) and `0x100007A9` = side. The client never runs it otherwise.
- We send `0x1000009C` only inside the creation bundle (units.py `_properties`), never as a change, so (P, same
  mechanism as 0x10000133 / 0x1000019D) the listener never fires: no relation, no team colour on the rig ->
  the team-tinted parts (dampener ring/field, door frame pieces) stay black.

### 1.4 Fix (P) and tests

1. For every structure / door / team-coloured prop: after creation send by 0x6 `0x1000009C = 0`, then `= team`
   (like `_late_vision`), config `team_as_change` default True. Expected: the octagon becomes the grey/blue ring,
   the GD rectangles go.
2. Fallback (G): send 0x8D `_Entity_OnSetClientRelationship` with the variable table {`0x100004A8` (u32) relation,
   `0x100007A9` (enum) side 3 ally / 5 enemy}.
3. vs-AI: add `Vfx_AI_Active` to `match_structure_scriptlets["dampener"]` (spawns 0x2E000AA8) (P).
4. Diag: break `0xA7B0D0` (arg = entity; log its IID) during the spawn and after the 0x6; break `0xA813F0` (log
   `0x4FCE30()` = property id). No hit for the dampener = cause confirmed.

## 2. Shards of Will sphere (0x2E000C89)

### 2.1 The type 0x0C action ("spawn child world state") - fields (C)

Field visitor `0x67E650` (vtable 0x15CEC20 slot +0x0C) maps the definition's properties to object offsets, in the
same order the pack stores them positionally after the node header:

| off | prop | kind | Shards_Active shell 1 (pack 0xA0000150 @0x35244) |
|---|---|---|---|
| +0x34 | 0x37E | did | 0x2E000C89 (world state to spawn) |
| +0x38 | 0x104 | bool | 1 |
| +0x39 | 0x931 | bool | 0 |
| +0x3A | 0x56E | bool | 0 |
| +0x3C..+0x48 | 0x25F / 0x103 / 0x56D / 0x61A | f32 | 0 / 0.5 / 0 / 0.1 |
| +0x4C | 0x160 | enum | 0x10000081 (attach point / bone, P) |
| +0x50 | 0x989 | bool | 0 |
| +0x54 / +0x60 | 0x988 / 0x44 | vec3 | 0 / 0 (offset, rotation P) |
| +0x6C.. | 0x8D0 0x8CF 0x8CE, 0x37D 0x43 0x102, 0x8DD 0x8E0 0x8DC 0x8DF 0x8DB 0x8DE 0x8E1 | pairs / f32 | (1,0) x3, 0 x3, (1,0) x7 |
| +0x118 | 0x15F | bool | 1 |
| +0x11C | 0x56C | enum | 0 |
| +0x120 | 0x325 | enum | **0x10000431** (scriptlet run on the child: Vfx_Active_State4; shells 2-4: 0x1000006B / 0x10000077 / 0x10000085) |
| +0x124 | 0x67C | bool | **1** |
| +0x125 | 0x41D | bool | 0 |
| +0x126 | 0x7E1 | bool | 1 |
| +0x128 | 0x37C | vec3 | 1.15 (scale; shells 2-4 1.0 / 1.05 / 1.1) |
| +0x134 | 0x8E2 | enum | 1 |

Execute `0x6852B0`: returns at once when the DID is null, or when **0x67C is false and the context entity has flag
0x40** at `+0x50` (a networked / server-owned owner: then the server is expected to spawn the child). Otherwise it
builds a spawn request (vtable 0x15CF8EC, `0x683AF0`: reads the owner's position/world, asks the world manager
`DAT_01B67258` vt+0x24 (or +0x30 when `DAT_01B6AB48`) to create the object) and, with 0x67C set, keeps a
persistent instance (`0x655360`) that owns the child for the scriptlet's lifetime. Shards' four shells have 0x67C
= 1: **the client spawns them itself; no server object is needed (C).**

### 2.2 The type 0x24 container is a SWITCH, not a gate (C)

- Fields (visitor `0x530400`): `0x321` (+0x34) = the property / variable switched on (here 0x1000033E), `0x5C7` (+0x3C)
  bool (adds a time offset to the watcher in `0x527580`). Then the branch list.
- Instance start `0x527580`: storage of the property (`0x505B70`) == 6 (a variable) -> value from the scriptlet's
  variable table (`0x44AEC0`; missing -> default value of the property) -> evaluator `0x521CA0` (vtable 0x15B0F24,
  slot +8 = `0x5304D0`) picks the branch once. Any other storage -> a property watcher (`0x515E30`, re-picks on
  change).
- Branch pick `0x51FBC0` (container vt+0x60): branches in order; type 6 = default (remembered), type 0x17 = case
  `{+0x24 literal (variant: property + value), +0x2C operand variable (0 = use literal), +0x30 op}`; the **first
  matching 0x17 wins**, else the default. Ops (C from the int path): 4 `<`, 1 `<=`, 6 `>`, 2 `>=`, 5 `==`, 3 `!=`.
- Shards_Active `0x10000886` = one 0x24 on 0x1000033E with 4 branches: **default -> shell scale 1.15 + State4
  (0x10000431)**; `< 0.125` -> shell 1.0 + State1 (0x1000006B); `< 0.25` -> 1.05 + State2 (0x10000077); `< 0.375`
  -> 1.1 + State3 (0x10000085). Branch layout in the pack: `tag | [0x17: prop, value, operand var, op] | tag 0 0 |
  child count | children`.
- So **every value (0.0, 0.01, missing) selects a shell**; the 0x1000033E floor is not the cause and can go (C). The
  sphere is lost after the pick: in the spawn itself, in the container instance ending at once (`0x530310` calls the
  instance's vt+0x40 when it has neither watcher +0x58 nor children +0x38 -> a 0x67C child owned by the
  scriptlet's lifetime would be removed with it, P), or in the shell drawing nothing without Vfx_Fade_In
  (0x10000033) (G).

### 2.3 Diag breakpoints (new `diag.py` mode, describe only)

| addr | when | log |
|---|---|---|
| `0x51FBC0` ret | branch pick | EAX = branch node; `[EAX]+0xC` type (0x17 / 6), `[EAX]+0x30` op; arg 4 (value variant) |
| `0x6852B0` | 0x0C execute | ECX+0x34 (ws DID), byte ECX+0x124 (0x67C); `[[esp+8]]+0x50` flags |
| `0x683AF0` | spawn request | `DAT_01B6AB48` (sync/async), owner IID ECX+0x20/+0x24 after the call |
| `0x655360` | persistent child instance | hit = 0x67C path taken |
| world manager `[DAT_01B67258]` vt+0x24 / +0x30 | create | return value (0 = creation failed) |
| instance vt+0x40 called from `0x530310` | container ended at once | hit right after 0x51FBC0 = P cause above |

Fix order: (1) drop the 0.01 floor (no effect either way); (2) run the diag; if the child is created then
destroyed in the same tick, send Shards_Active **without** the chained Start copy (the second 0x886 run replaces
the first and drops its child, P) and with the variable table, once; (3) if never created, look at the world
manager return (G).

## 3. Stealth hotspot: the white "+" and light streaks

- Correction (C): `0x7E6` is not an action field. Both tables' Vfx_Active entries are
  `0x100000EB | 0 | n | 0x737 | [0x7E6 = 1 only in 0x1D000509] | children`: it is an **entry property**. Reader
  `0x51EFE0`, used by the scriptlet start `0x57CFD0`: when the start parameters have flag 4 (`+0x38 & 4`, meaning O)
  and 0x7E6 is false, the start is refused. It does not keep the particle alive.
- Both Vfx_Active entries play the same three things: particle `0x18000A57`, sound, child `0x2E000D37` (the hex
  mesh; `0x1D00050B` with a -2.1 offset). The only visual besides the tile is the particle, so the "+" and streaks
  are `0x18000A57` (P); there is no relation / team switch around it (C: no 0x22 / 0x24 container in the entry).
- Fix (P): do not send Vfx_Active to the hotspots; spawn `0x2E000D37` as a plain prop (ctype 5) at each tile with the
  tile's yaw (config switch `stealth_tile_direct`, default True; False = Vfx_Active as now). The tables have no
  stop key for the particle, so this is the only way to keep the tile without it. If the purple rim is missing
  afterwards, it came from the particle (G).

## 4. Red-orb rubble and the core "prow"

- Rubble (G, unchanged): "Rock" class `0x400005C9`, ws `0x2E000D22` (.entity `0x2D000AEB`, ctype 7, `0x93D = 1`,
  `0x2A4`, no table of its own; children `0x2E000D13` / `0x2E000D14` carry the team-colour table). Spawn as a prop
  with `0x1000009C = 2` sent as a change (section 1.3) so its children turn red, then Vfx_OnInit.
- Prow (O): the core's Vfx_AI_Active (`0x1D00098A` @0x14A9F4) spawns `0x2E000AC3` at offset 0 (no 0x988 / 0x44
  offset), so it is not the arrow piece 4-11 m east of the core. No record found; probably a map-build difference
  (crime-alley-still-missing.md 8).
