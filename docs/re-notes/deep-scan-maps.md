# Deep scan of map content the server still does not place or drive (2026-10-26)

Scope: Crime Alley (first), Gotham Divided, Gotham Heights, Coast City, Tutorial 1 (Tutorial 2 as the reference for
Crime Alley's lane). Builds on, and does not repeat: `map-object-census.md`, `map-manifests.md`,
`crime-alley-still-missing.md`, `crime-alley-missing-elements.md`, `black-ground-shapes.md`, `full-maps-world.md`,
`destructible-vehicles.md`, `crime-alley-props.md`, `crime-alley-jungle.md`, `map-gaps-*.md`,
`map-objectives-recipes.md`. Tags: **C** confirmed (data / code read), **P** probable, **G** guessed, **O** open.

Method (throw-away scripts in the session scratchpad `ds_maps`, nothing of the game copied): a reference scan of
**all 617 installed packs** (header ids + decompressed stream) for every marker / socket / cover DID below; statics
of the five map packs (census pickle + a new parse of Tutorial 1's `0xA0C112CA`); world-state property lists, `.entity`
bounding boxes and destruction records of every world state in the five maps' zone / layout / variants packs;
scriptlet tables re-parsed per pack (not only the pack `Data.index()` names); Havok behaviour graphs and clips of the
dampener and the relay (`uesrv.havok`, `uesrv.havok_anim`); the decompiled client (`re-work/decomp`, VA, base
0x400000). REA / Ghidra was not needed (the local decompilation answered every code question).

---------------------------------------------------------------------------------------------------------------------

## 0. Short answer

| # | Finding | Tag |
|---|---|---|
| 1 | The Crime Alley **padlocked plate** is the **Power Relay** `0x4000089D` (ws `0x2E000D12`), not a pad: it is the only class in Crime Alley's packs with minimap category `0x100004DA = 26` (SMALL_CAPTURABLE), the category of the v AI tracker's single pip; its world-state tables `0x1D0004A0` / `0x1D0004A1` hold **`_Selection_Usage_Locked`** and **`Vfx_Locked`** (the padlock particles `0x18000703` / `0x180006FB` / `0x180007DF`), `Vfx_Unlocked`, `Vfx_Fade_Loop`, the CapturePoint keys | C class / pip / keys, P position (nook) |
| 2 | The client draws the padlock itself from two per-team bools on a usable object: **`0x100006BD`** (team 1) / **`0x100006BC`** (team 2) (`0x96CA10`, `0xAA23C0` start / stop `_Selection_Usage_Locked` 0x10000653 for the local team); the minimap note carries a mask built from the same bools when `0x100004FF` != 0 (`0xA0CAB0`) | C code, P polarity |
| 3 | **ics drops those keys**: `Data.script_table(0x1D0004A0)` / `(0x1D0004A1)` return None (the index names `0xA0000162`, whose table parse misses them; they parse in `0xA000016B`), so `World.scriptlet` refuses every relay key except the four team-colour ones on Coast City's relays, Gotham Heights' Orbital Cannon and any Crime Alley relay. Same gap for the Destroyer drone's table `0x1D0003BA` / `0x1D0003BB` (Vfx_Spawn, Vfx_Despawn, Vfx_OnExplode, Vfx_Min_Capture) and `0x1D000687` | C |
| 4 | Every destructible (`0x800`) **client static** on the five maps has creation type 6 or 9 (the client builds its pieces itself): no static needs event 0x8B. The 22 destructible world states of creation type **8** (server-spawned) are Crime Alley's 7 vehicles plus **2 Gotham Divided and 13 Coast City** vehicles / props: each needs 0x8B after creation, as Crime Alley's do now | C |
| 5 | The dampener's own model **cannot** fill its socket: rig `env_pvp_dampener_a` (40 bones, legs reach 1.5 m, `Ground` bone static at 0), clips activate / deactivate 1.0 s (body z -0.27 <-> 1.33), graph start state "Activate". Its `0x8B1` group (`0x8B2 = 12`, `0x8A3`, `0x8A5`) is a **picking-volume shape** (`0x555240`, selected by `0x8C1 = 1`), not a decal: that theory is closed | C |
| 6 | The dampener's death / respawn pose needs **graph events**: `Death` `0x100001C0` (wildcard -> Deactivate -> Deactive Idle) and `Respawn` `0x100003FD` (Deactive Idle -> Activate); ics sends only the scriptlet Object_Deactivate | C graph, P need |
| 7 | **Minion spawner** `0x2E000D03` (ctype 8; GD class `0x400005C8`) belongs on every lane-mouth marker: Tutorial 2's layout places "01Spawner" exactly on its mouth marker `0x2E000AF8` (71.75, 77.5) and the cinematic `0x3500002C` "01BlueSpawner" on `0x2E000AF9`. ics creates none | C (T2), P (PvP maps) |
| 8 | No record in any installed pack references the nook markers `0x2E000944` / `945` / `1117` / `1120`, the structure markers `0x2E0011A6`-`AD`, the emitters `0x2E00110F` / `1110` / `1118` / `111B` / `1121` or the triples `0x2E000626` / `6B3` / `6B4`: their only references are the map packs' statics (Tutorial 1 and 2 reuse the emitter ids). There is no layout / encounter list that names objects at those spots | C |
| 9 | Ruleset filter: on all five maps the only statics with a `0x55B` list are Crime Alley's two team-2 core pedestals. No vs-AI-only (or Clash-only) scenery exists in the statics; the vs-AI video's lava cracks / prow are not a ruleset effect | C |
| 10 | Encounter templates hold **no object arrays** (only tracker entries, team / camera records `0x4800114E` / `0x48000690` ..., UI, shop, minimap, music). The Clash 2v2 template `0x40000E74` has **no tracker entry** (the v AI one has category 26 slot 1) | C |
| 12 | Crime Alley's team-2 lane turret should be `0x40000C8B` (mirror of the team-1 `0x40000C8C`, has the turret-warning table), not `0x40000C86` (3000 HP variant without it) (3.1 row 6) | C data, P role |
| 11 | Crime Alley dampener floor: the only fitting cover in the loaded packs is `0x2E0000E3` (it renders, closes the hole, but pale); no textured flat piece of >= 10 x 13 m is unplaced in Crime Alley's packs (full list 2.3). The street is the terrain itself (`0x2E001207`-`120B` carry no geometry) | C list, O look |

---------------------------------------------------------------------------------------------------------------------

## 1. Cross-map findings with evidence

### 1.1 The padlock: who draws it (C code)

- `0x96CA10(local champion)`: team 1 -> reads bool **`0x100006BD`**, team 2 -> **`0x100006BC`** on the usable object
  (`in_ECX + 4`), returns it.
- `0xAA23C0` (refresh of a usable target; callers `0xAA43A0` property listener on 0x100004FF / 0x100006BD / BC /
  0x10000456 / 0x100007C7 / 0x1000047B, `0xAA42A0` / `0xAA4340` local-player changes): if the bool is false ->
  `0x588A80(obj, 0x10000653, ...)` (`0x57C4B0`, the signal / stop path), else `0x588A00(obj, 0x10000653, ...)`
  (`0x57D8B0`, start). `0x10000653` = `_Selection_Usage_Locked` (scriptlet names table). So **true = locked for that
  team** (P: start / stop reading of 0x57D8B0 / 0x57C4B0 from `world.signal_scriptlet`'s note).
- `0xA0CAB0` (minimap note field +0x24, built in `0xA4B150` and refreshed in `0xA807B0`): `0x100004FF == 0` -> 3,
  else `(BD ? 1 : 0) | (BC ? 2 : 0)`; P: the per-team lock mask the note's padlock icon follows.
- Usage type `0x100005A6` (3 = capturable / billboard 0x100007D5, 4 = pad; `0x96CAE0`), charges / restriction
  `0x100004FF` (`0x96CAB0`), range `0x1000034C`, relation mask `0x10000506` (`0xA0A430`). Kinds (properties.tsv):
  0x100006BD / BC bool 0x16, 0x100004FF / 0x100005A6 / 0x1000034C enum 0x08.

### 1.2 The relay is the Crime Alley objective (C data)

| Item | Value |
|---|---|
| Class / template | `0x4000089D` / `0x4900089D` in the Crime Alley layout pack **`0xA00002E6`** (also CC `0xA0000162`) |
| Template values (raw) | `0x100005A6 = 3`, `0x100004DA = 0x1A` (26), `0x100007D8 = 1` (tracker entry), `0x1000019D = 0x80200`, `0x10000504 = 3.0` (P capture radius), `0x1000034C = 30`, `0x10000506 = 3`, `0x10000501 = 1`, `0x100004A4 = 1`, `0x1000060F = 3`; `0x100004FF` and `0x10000456` present **without value** (`0x5000xxxx` form) |
| Only category-26 class on the map | byte scan of `0xA00002E5/E6/E7`, `0xA00000B3/DF` for `0x100004DA = 26`: only `0x4900089D` (CC's pack adds `0x49000D25`) |
| Tracker | v AI `0x40000C82`: `0x100007F5 = [26]`, `0x100007FA = [1]`; Clash `0x40000E74`: no 0x100007F7 at all |
| World state | `0x2E000D12` (ctype 8), `.entity 0x2D000ADC` plate bbox (-3.42, -3.70, 0) .. (3.43, 3.28, 0.09) (~7 m) |
| Tables | `0x1D0004A0` (base `0x1D0004A1`): `_Selection_Usage_Locked` (`0x40000737`, particles `0x18000703`, `0x180006FB` x3), `_Defeat_OnDead`, `_Defeat_OnFade`, `Object_Reset`; base: Vfx_Stop, Vfx_Active, Vfx_Fade_In, **Vfx_Fade_Loop** (children `0x2E000D13` / `D14` / `D15`, particles `0x18000A8B` / `A8C`), Vfx_CapturePoint_BeingCaptured / _Captured (`0x18000AD7` / `AD8`) / _Lost, **Vfx_Locked** (`0x18000703`, `0x180006FB`, `0x180007DF`), **Vfx_Unlocked**, _Entity_OnEnterWorld_Default, Vfx_Object_Reset, _Entity_OnSetClientRelationship |
| Graph | `env_pvp_capture_point_c_behavior`: one "grow" state whose clip time follows `Property_Vital_CaptureBuffer_Percent` (C names): the relay column rises with its CaptureBuffer vital (P) |
| Lines | Crime Alley's announcer pack holds relay lines 704 / 705 / 256 ("new relay operational in 30 / 10 s / now") and events 49 / 50 / 58 (announcer-and-map-elements.md) |
| Frames | Clash 2v2: minimap padlock at ~(80, 98) from the first frame, hover padlock, never unlocked in 5 matches (crime-alley-2v2-video.md 3-4); v AI video: no padlock icon before 0:45 (crime-alley-jungle.md 2) |

Reading (P): both modes have one relay; on Clash it sits locked at the nook from the start; on v AI it becomes
operational later (the three relay lines; tracker pip 1). The steel pad with the padlock the tester saw is this
relay's plate in its locked state, not `0x2E00101D` (that one is the **Raider capsule**: Tutorial 2 places it at the
same nook (80, 97.66) yaw 179 and Coast City under its Raider camp (80, 8.55); bbox 10.4 x 5.7 x 3.85 m, C).

### 1.3 Scriptlet tables ics cannot see (C)

`Data.script_table` reads a table only from the pack `Data.index()` names first; in 5 of the 543 tables of the five
maps' packs that pack's parse misses it while another pack has it:

| Table | Index pack (parse misses) | Parses in | Used by | Keys lost today |
|---|---|---|---|---|
| `0x1D0004A0`, `0x1D0004A1` | `0xA0000162` | `0xA000016B` | relay / control point / cannon world state `0x2E000D12` (CA / CC relays `0x4000089D`, `0x40000D25`; GH cannon `0x40000511`; GD control point `0x400003AF`) | Vfx_Locked, Vfx_Unlocked, Vfx_Fade_In / _Loop, CapturePoint_*, _Selection_Usage_Locked, Object_Reset |
| `0x1D0003BA`, `0x1D0003BB` | `0xA0000161` | `0xA000016E` | Destroyer drone world state `0x2E000AB5` (GH super minion `0x40000EAA`, Tutorial 1 Destroyer) | Vfx_Spawn, Vfx_Despawn, **Vfx_OnExplode**, Vfx_Min_Capture, Robot_Minion_Capture_Attack |
| `0x1D000687` | `0xA0000168` | `0xA00002E7` | `0x2E000FAB` | _Defeat_OnDead |

`World.scriptlet` refuses a key missing from `ent.scriptlet_keys` (`ics/world.py` 640), so these are never sent.
`map-manifests.md` 0 ("relays: only SetNull / SetContention / ...") was this parse gap, not the data. Fix (code, not
done here): in `Data.script_table`, when the index pack has no entry, try the other packs that list the DID.

### 1.4 Destructible objects and event 0x8B (C)

- Client statics with `0x800` (all types 7): Crime Alley 46 world states, Tutorial 2 15, Gotham Heights 60, Gotham
  Divided 53, Coast City 93. **All creation type 6 or 9** (fences, crates, barricades, bins...), which the client
  builds itself (`0x630FC0` / `0x630BF0` gate, destructible-vehicles.md 1). Nothing to send.
- World states with `0x800` and creation type 8 in the five maps' packs (each needs `destruction_reset_event` 0x8B
  after its create bundle, as the Crime Alley vehicles):

| Map / pack | Class -> world state (destruction record) |
|---|---|
| Crime Alley `0xA00002E5` (done) | `0x40000454` -> `0x2E000559`, `0x40000459` -> `0x2E0008B8`, `0x4000045D` -> `0x2E000795`, `0x40000C40` -> `0x2E000EFE`, `0x4000081A`-`81C` -> `0x2E000F03`-`F05` |
| Gotham Divided `0xA00000FC` | **`0x40000453` -> `0x2E0008A6`** (`0x500000E0`), **`0x40000458` -> `0x2E0008B9`** (`0x500000E2`); plus the shared `0x454` / `0x459` / `0x45D` |
| Coast City `0xA00000D2` (vehicles: Vfx_Spawn_Event01-04 / Alt01-02 + Super Strength keys) | `0x4000045E` -> `0x2E000797`, `0x4000045A` -> `0x2E000B64`, `0x40000455` -> `0x2E000B8B`, `0x40000456` -> `0x2E000B8E`, `0x40000461` -> `0x2E000C32`, `0x4000045B` -> `0x2E000C34`, `0x40000555` -> `0x2E000CDF`, `0x40000556` -> `0x2E000CE0` |
| Coast City `0xA00000D2` (props: Destructible_* only, no spawn keys) | `0x40000543` -> `0x2E000B23`, `0x40000540` -> `0x2E000B24`, `0x40000542` -> `0x2E000BB7`, `0x40000544` -> `0x2E000C83`, `0x40000541` -> `0x2E000F31` |
| Gotham Heights `0xA000009A` | carries `0x40000454` / `0x4000045D` (same as Crime Alley) |

No layout pack of any map names any of these (`Data.layout` of `0xA0000162`, `0xA0000168`, `0xA000016B`,
`0xA00002E6`, `0xA0000256`: 0 hits), so positions are authored (G), as on Crime Alley.

### 1.5 Dampener model, graph and the `0x8B1` group (C)

- Graph record `0x1A000B15` (pack `0xA00002E6`, packfile at stream 0x123115C): events `triggerstart` `0x10000035`,
  `triggerstop` `0x1000006F`, **`Death` `0x100001C0`**, **`Respawn` `0x100003FD`**, `State_to_State` `0x10000050`
  (ids from the graph-event name table `0x300000A4`); state machine "Animation": 0 Activate -(State_to_State)-> 1
  Active Idle; 2 Deactivate -(State_to_State)-> 3 Deactive Idle -(Respawn)-> 0; wildcard Death -> 2; start state 0.
  Variables `Property_BehaviorParams_UsToTargetHeading` (head aim) and `Property_Vital_CaptureBuffer_Percent`
  (indicator height clip).
- Skeleton (40 bones, stream 0x2E3AB4): Parent, Root (z 1.24), Body (1.33), Neck_Ring (2.92), six legs A-F
  (hip 1.43, toe -0.01, reach 1.5 m), Shield, Indicator_Height, Head_Aim, Ground (0, static in every clip). Clips by
  duration: activate 1.0 s (Body -0.27 -> 1.33), deactivate 1.0 s (1.33 -> -0.27), inactive idle 0.1 s (-0.27),
  active idle 7.5 s / 8.33 s. The whole model lies within ~2 m of its origin: it covers no 10 x 15 m opening.
- `0x555E20` reads `0x8C1` (shape kind: 1 -> `0x555240` reads struct `0x8B1` {`0x8B2` enum < 13, `0x8A3`, `0x8A5`,
  `0x85C`, `0x856` deg}; 2, 5, 6 other shapes); `0x555EE0` tests a point / ray against it: a **selection / hit
  volume** (P picking). Dampener: `0x8C1 = 1`, `0x8B2 = 12`, `0x8A3 = 2.0`, `0x8A5 = 1.0`.

### 1.6 Markers and derived world states (C)

- Reference scan of 617 packs: every aligned hit of the marker DIDs outside the map packs is texture / mesh noise
  (checked by context). Map packs: Crime Alley `0xA0C112BA`, Tutorial 2 `0xA0C112C2`, Tutorial 1 `0xA0C112CA`
  (emitter ids `0x2E00110F`-`0x2E001140`, 44 distinct type-3 ids), Coast City `0xA0C122E2` (944 / 945 at its five
  camps), GD / CC / GH (the triples).
- Triples `0x2E000626` / `6B3` / `6B4`: 17 each on GD, CC and GH, flags 0x1E, random yaw, spread evenly over the
  whole map (nearest neighbour 6-20 m, no symmetry about the map's mirror): P ambient emitters / decals of the zone
  art; no record, nothing a server can send (none on Crime Alley).
- Installed derived type-3 records (`did | 3 | base | 0 | n | props`): GH `0x2E000006` x10 (centre ring) and
  `0x2E00041F`-`432` x20 (beside the points), CC `0x2E000940` / `941` (lane mouths) and `0x2E000942` (five camps).
  Base table `0x1D0003E4`: Vfx_Active_Blue -> particle `0x180013BB`, _Red -> `0x180013BA`, _Yellow -> `0x18000792`
  (+ refs). Never created by the client (census 0.2); ics creates none (`match_marker_statics` not implemented).

### 1.7 Minion spawner `0x2E000D03` (C data, P use)

World state ctype 8, `.entity 0x2D000ACE` with a zero box (no model: particles only), tables `0x1D000385` (team
colour) + `0x1D000491` (Vfx_Stop, Vfx_Active_State0 / 1, Vfx_Spawner_Tier01 / 02); packs `0xA00002E6` (CA),
`0xA0000168` (GD, class `0x400005C8`), `0xA0000162` (CC), `0xA000009A` (GH), `0xA0000256` (T1). Tutorial 2 layout
`0x1D0007EE` "01Spawner" (71.75, 77.5) side 1 = its team-2 mouth marker; cinematic `0x3500002C` "01BlueSpawner" side 3
(team 1, on `0x2E000AF9` (21.75, 77.5), cinematics-vfx-audio.md). The keys
`Vfx_Spawner_Team0N_Tier0M` (`0x10000B16`-`B19`) are **not** in its tables; the generator keys `_Generator_Self_*`
neither (they live on the generator script side): send only what `0x1D000491` has.

### 1.8 Encounter templates (C)

Read with `Data.template_properties`: CA v AI `0x40000C82` (ruleset `0x10000009`, tracker [26] / [1], minimap
`0x48000E36`, music `0x4800128C`, UI `0x4800111B`, shop `0x48000EA9`, team records `0x10000314 = [0x4800114E] x3`),
CA Clash 2v2 `0x40000E74` (ruleset `0x1000000C`, no tracker, team records `0x48001448` / `4A` / `49`, encounter-wide
script `0x10000242 = 0x340001B5` = a StealthRevealed attribute toggle, not an object list), GD `0x40000B6B`, CC
`0x40000B6A`, GH `0x40000B6C` (tracker entries as map-runtime-state.md), T1 `0x40000991`. The `0x4800xxxx` team records
hold `0x1000014E` (string), `0x10000077` (camera yaw, GD -45), `0x10000258` (`0x2100xxxx`). No property of any template
names a world state, a class list or a placement table.

---------------------------------------------------------------------------------------------------------------------

## 2. Terrain sockets and what fills them

### 2.1 Table (all five maps; heights from the `0x80` records, 5 m grid)

| Map | Socket | Occupant in data | Seen | Status |
|---|---|---|---|---|
| CA | (15-20, 75-80) / (140-145, 75-80) -> 0 | core pedestal `0x2E000A3B` (client) | ok | OK |
| CA | **(40, 75) / (40, 80) -> 180** and mirror (120, ...) | marker `0x2E0011A9` / `A8` only (no record) | black octagon | **open** (2.2) |
| CA | (60-70, 70-80) 3x3 + (75, 80) -> 0 | nothing (Tutorial 2 has no socket there: its terrain is 200) | not black | OK (P: height-0 cells are not drawn as a funnel; O why) |
| T2 | (40, 75) / (40, 80) -> 180 (same as CA) | static `0x2E00119F` (one-bone attach point, no geometry) | - | reference |
| GD | six lane-exit sockets (one vertex each, 50 m) + pits (55, 55) / (105, 105) | `0x2E0003F0` copies (ics `match_socket_covers`, 8 entries) | black before | sent since fase3-hw; tester result **O** |
| CC | (75-85, 65-75) 3x3 -> 0 | none found | black polygon | open (2.4) |
| CC | (80, 85) -> 200 | device platform `0x2E000C57` (client) | ok | OK |
| GH | (115-125, 10-25) -> 0 | subway entrance `0x2E000F60` / `F61` (client) | not visited | OK (P) |
| T1 | river / bank cells (187.5, 180) over x 40-95 | the river and crater statics (client) | ok | OK (not a socket) |

### 2.2 Crime Alley dampener sockets: what is settled

- C: the octagon is the two-vertex 180 m funnel; `0x2E0000E3` (`.entity 0x2D00007B`, box -5..5 x -10..10 x 0..2)
  renders and closes it (tester 19:28: "the black octagon is gone"; team 2's cover "a pale strip about 10 m wide
  across the whole street, 20 m in y" = exactly its box) but shows pale and untextured (19:28, 22:07).
- C: the street around it is the terrain (cobbles = terrain material); `0x2E001207`-`120B` (the census' "street
  meshes") have no geometry after their properties (`0x8B` separator follows at once), so nothing in the statics was
  ever meant to cover the funnel. `0x2E001185` carries curb geometry south of the lane (local y -18.8 .. -4.7).
- C: the dampener's model is small and its `Ground` bone static (1.5): the original's dampener did not cover it.
- C: no static, layout placement, cinematic actor or encounter record of any pack names anything at (40, 77.5) or
  (120, 77.5) other than the type-3 markers (reference scan + `Data.layout` of every map layout pack).
- So the original either drew a server object there whose record is not in this install, or its build had no socket
  (the vs-AI video is another build: lava cracks, prow; crime-alley-still-missing.md 8) (P / O).

### 2.3 Flat cover candidates in the packs Crime Alley loads (C list)

World states of `0xA00002E5/E6/E7`, `0xA00000B3/DF`, `0xA0000037/38/39` whose `.entity` box is >= 8 x 13 m and <= 4 m high:

| World state | Box (local) | ctype | Placed on | Note |
|---|---|---|---|---|
| `0x2E0000E3` | -5..5 x -10..10 x 0..2 | 3 | nothing | the pale slab; only candidate that fits the opening |
| `0x2E000A3B` | -10.6..10.6 x -10.5..9.4 x -0.26..0.12 | 9 | every core | the core pedestal (round platform) |
| `0x2E000CA5` | -9.0..9.0 x -7.1..11.3 x -1.15..0.2 | 3 | every spawn | the spawn platform |
| `0x2E000CD7` | -10.9..10.9 x -0.1..15 x 0..3.2 | 9 | nothing | the base gate (wall) |
| `0x2E000333` | 92 x 93 m | 5 | CA 12BB, T1 | backdrop |
| `0x2E001329` | x 50.4..63.7, y -6.8..5.7, z 0..0.35 (offset 57 m from its origin) | 3 | T2 only, at (17.5, 77.5) -> footprint x 67.9-81.2, y 70.7-83.2 | end-of-lane set of Tutorial 2 (its parts include a ~3.7 m tall piece): not a floor (G) |

Nothing textured and flat fits; the pit pieces `0x2E0003EE` (10 x 20 x 2.5) / `0x2E0003E3` (15 x 20 x 5) are only
in `0xA000009A` (a second zone pack: the 2026-10-23 load hang).

### 2.4 Coast City centre (75-85, 65-75)

Unchanged from map-object-census.md 3.1 (occupant O). The same 10 x 20 / 15 x 20 pit pieces are in `0xA000009A`
only, which Coast City does not load (`Data.map_packs(0xA0C122E2)` = `0xA00000D2`, `0xA0000161`, `0xA0000162`).

---------------------------------------------------------------------------------------------------------------------

## 3. Per-map tables: missing element -> evidence -> server recipe (ranked by visibility)

"ics" = what `ics/match/maps.py`, `match.py`, `objectives.py`, `bosses.py`, `liftables.py` and `[ics]` do today.

### 3.1 Crime Alley v AI `0x40000C82` (LB 0x13BB, z 200)

| # | Missing / wrong | Evidence | Recipe (class / ws, pos, yaw, props, scriptlets, events) | ics | Tag |
|---|---|---|---|---|---|
| 1 | Dampener floor (black octagon x 40 / 120) | 2.2, 2.3 | Options, test one at a time: (a) `0x2E0000E3` at (40.0, 77.5, **199.6**) / (120.0, 77.5, 199.6) yaw 0 (top 0.4 m under the street: only the funnel's inside shows the slab, the rim keeps its cobbles); (b) the core pedestal `0x2E000A3B` (textured, 21 x 20 m) at (40.0, 77.5, 200.12) yaw 90 / (120.0, 77.5, 200.12) yaw -90 under the dampener (looks like a structure platform); (c) leave open. `match_socket_covers.crime_alley` already takes either | `[]` | C mechanism, G look |
| 2 | Relay (tracker pip 1), padlocked plate | 1.2 | `0x4000089D` (ws `0x2E000D12`), neutral (`0x1000009C` = template enum `0x10000C6E`, i.e. omit), **pos (80.0, 97.25) yaw 180** (markers 944 / 945; P), bundle props **`0x100004FF = 2`** (kind 0x08), **`0x100006BD = true`, `0x100006BC = true`** (kind 0x16, locked for both; P polarity, 1.1), LifeState 4; scriptlets `_Entity_OnEnterWorld_Default`, `Vfx_Fade_In`, `Vfx_Locked`; tracker 0x2069 slot 1 category 26 lock 3 (`match_tracker_lock`). Unlock (v AI, G time): 0x2001 704 at -30 s, 705 at -10 s, 256 at 0, then bools false + `Vfx_Unlocked` + lock 0; capture as Coast City's relays (`0x10000456`, CaptureBuffer vital type 3 drives the "grow" clip). Clash: keep it locked all match. **Needs the 1.3 parse fix first** (else every relay key is dropped). If the Raider shares the nook (`match_raider` at 300 s), put the relay on the Raider's death instead (G) | not spawned (`match_nook_pad` {}) | C class / keys, P pos / props, G times |
| 3 | Raider capsule at the nook (v AI) | `0x2E00101D` = Tutorial 2's static at (80.0, 97.66, 200.06) yaw 179, CC's under its Raider (1.2) | bare ws `0x2E00101D`, (80.0, 97.66) yaw 180, no team, `0x50F = 8` (automatic); from the Raider's spawn until its death (G); the tester's vitrina 121 drew it | `match_nook_pad` {} | C object / pos, P role |
| 4 | Lane spawners (2) | 1.7 | ws `0x2E000D03` at the mouth markers: team 1 (21.75, 77.5, 200.23) yaw -90, team 2 (138.3, 77.5, 200.41) yaw 90; `0x1000009C` team, `0x100007A2` 3 / 5; `Vfx_Active_State0` at spawn, `Vfx_Spawner_Tier01` (Tier02 once the enemy dampener is down, G) | none | C keys / T2 pos, P PvP |
| 5 | Dampener death pose | 1.5 | on death (with `match_dampener_keep_body`): graph event **Death `0x100001C0`** (scriptlet `0x100001E3` + var `0x780`, `World.graph_event`) after Object_Deactivate; on respawn **Respawn `0x100003FD`** on the kept body instead of a new object (G: or new object, start state Activate plays by itself) | Object_Deactivate only | C graph, P need |
| 6 | Team-2 lane turret class | the v AI team-2 classes with the turret-warning table `0x1D000923` (`_TurretWarning_WarningState`) are dampener `0x40000C87`, core turret `0x40000C8D` and lane turret **`0x40000C8B`**; ics uses **`0x40000C86`**, which lacks the table and differs from the team-1 turret `0x40000C8C` (health `0x10000426` 3000 vs 2500, `0x10000934` 2 vs 5, extra `0x10000B5B = 1`, `0x10000B76` 185 vs 165); `0x40000C8B` matches `0x40000C8C` value for value (tester's target panel "Turret 2689/3000" = C86) | `_crime_alley("vai")["turret"]` = (`0x40000C8C`, **`0x40000C8B`**) behind a config switch; C86 is P the 1vAI tutorial's turret | C86 | C data, P role |
| 7 | Ambient emitters `0x2E00110F` / `1110` / `1118` / `111B` / `1121` | 1.6: no record anywhere | none possible | - | C |
| 8 | Health-pack generator | `0x40000180` (ws `0x2E00054B`) and pickups `0x400000A4` / `0x40000A86` (ws `0x2E000FBB`, minimap 5) in `0xA00002E6` | positions O (no marker); skip until a frame shows one | none | C class, O use |

### 3.2 Gotham Divided v AI `0x40000B6B` (LB 0x1BD3, z 250)

| # | Missing / wrong | Evidence | Recipe | ics | Tag |
|---|---|---|---|---|---|
| 1 | Socket covers | census 2 | already sent (8 x `0x2E0003F0`); ask the tester (O) | sent | P |
| 2 | Lane spawners (6) | 1.7, class `0x400005C8` | `0x400005C8` / `0x2E000D03` at team 1 (17.5, 134.0) yaw 180, (26.0, 142.5) yaw -90, (23.5, 136.5) yaw -135; team 2 (134.0, 17.5) 90, (142.5, 26.0) 0, (136.5, 23.5) 45 (markers `0x2E000AF4`-`AF9`); as CA 4 | none | C pos, P use |
| 3 | Vehicles | 1.4 | `0x40000453` / `0x2E0008A6`, `0x40000458` / `0x2E0008B9` (+ 454 / 459 / 45D) as liftables with 0x8B, Vfx_Spawn_Event01; positions G (streets near the jungle quarters) | CA only | C classes, G pos |
| 4 | Dampener death pose | 1.5 | as CA 5 (GD dampeners `0x40000C61` / `C60` use the same graph: ws `0x2E000E04`) | Object_Deactivate | C |
| 5 | Control point `0x400003AF` keys | 1.3 | after the parse fix its Vfx_Locked / CapturePoint keys reach the client | dropped | C |
| 6 | Triples 626 / 6B3 / 6B4 | 1.6 | none possible | - | C |

### 3.3 Coast City v AI `0x40000B6A` (LB 0x23E3, z 250)

| # | Missing / wrong | Evidence | Recipe | ics | Tag |
|---|---|---|---|---|---|
| 1 | Relay visuals (locked / unlocked / capture / grow) | 1.2, 1.3 | parse fix; then at spawn `Vfx_Fade_In` + `Vfx_Locked` with `0x100004FF = 2`, `0x100006BD` / `BC` true; at unlock (lines 241 / 248 / 257) false + `Vfx_Unlocked`; capture: `Vfx_CapturePoint_BeingCaptured` / `_Captured` / `_Lost` and the CaptureBuffer vital (0x42 type 3) for the grow clip | team colour only | C keys, P props |
| 2 | Centre hole (75-85, 65-75) | 2.4 | open; no fitting piece in CC's packs (C) | open | O |
| 3 | Team lights (derived type 3) | 1.6 | bare `0x2E000940` (137.5, 60.5) yaw -249, (139.25, 67.0) yaw 40 team 2; `0x2E000941` (22.5, 60.5) yaw -108, (20.75, 67.0) yaw -36 team 1; `Vfx_Active_Blue` (team 1) / `_Red` (team 2); `0x2E000942` at the five camps with `Vfx_Active_Yellow` | none | C data, P need |
| 4 | Lane spawners (4) | 1.7 | `0x2E000D03` on `0x2E000AF4`-`AF7`: team 1 (22.5, 60.5) yaw -108, (20.75, 67.0) yaw -36; team 2 (137.5, 60.5) yaw -249, (139.25, 67.0) yaw 40 | none | P |
| 5 | Vehicles and destructible props | 1.4 | 8 vehicle classes + 5 prop classes of `0xA00000D2` with 0x8B; positions G | none | C classes, G pos |

### 3.4 Gotham Heights v AI `0x40000B6C` (LB 0x1BF3, z 250)

| # | Missing / wrong | Evidence | Recipe | ics | Tag |
|---|---|---|---|---|---|
| 1 | Orbital Cannon visuals | 1.3: ws `0x2E000D12` = the relay's | parse fix; Vfx_Locked until `lock` ends (`match_cannon`), Vfx_Unlocked, capture keys, CaptureBuffer vital | team colour only | C |
| 2 | Destroyer super minion spawn / death effects | 1.3 (`0x1D0003BA` / `BB`) | parse fix; then `Vfx_Spawn` at creation, `Vfx_OnExplode` / `Vfx_Despawn` at death | dropped | C |
| 3 | Centre ring and point lights (30 derived type 3) | 1.6 | census 6 `match_marker_statics` (positions from the statics, colour by owner) | none | C data, P need |
| 4 | Vehicles | 1.4 | `0x40000454` / `0x4000045D` from `0xA000009A` (G positions) | none | G |

### 3.5 Tutorial 1 `0x40000991` (LB 0x13CB / 0x14CB)

| # | Missing / wrong | Evidence | Recipe | ics | Tag |
|---|---|---|---|---|---|
| 1 | Destroyer's explosion / spawn effects | 1.3: the Destroyer's ws `0x2E000AB5` tables are invisible to ics | parse fix; `Vfx_OnExplode` at its death (the finale) | dropped | C |
| 2 | Layout placements never used | `0xA0000256`: `03GasJoker` (ws `0x2E00095E`, (40.69, 70.92), 3 path points), `02Destroyer` ((113.75, 123.0), scale `0x450 = 1.5`, cinematic `0x35000026`), `02PaddyWagonB` ((102.45, 126.62)) | cinematic actors (P): none needed for the flow | - | C pos, P role |
| 3 | 44 type-3 markers (`0x2E001110`-`0x2E001140`, `0x2E000625` / `628`, `0x2E0010D2`) | no record (1.6) | none possible | - | C |

---------------------------------------------------------------------------------------------------------------------

## 4. Proposed `[ics]` keys (not applied; each needs a `config.py` default with the date and this note)

```
# deep-scan-maps.md 1.3 (C): tables the index pack misses are read from the other packs that list them
"script_table_fallback_packs": True,
# deep-scan-maps.md 1.2 (C class / keys, P position): Crime Alley's relay (tracker pip 1)
"match_relays": {"crime_alley": [{"cls": "0x4000089D", "pos": [80.0, 97.25], "yaw": 180.0, "slot": 1,
                                  "locked": True, "unlock_at": 0.0, "lines": {"-30": 704, "-10": 705, "0": 256}}]},
"relay_lock_props": {"0x100004FF": 2, "lock_team1": "0x100006BD", "lock_team2": "0x100006BC"},
# deep-scan-maps.md 1.7 (C T2 placement, P PvP): spawner on every lane-mouth marker
"match_spawners": True, "match_spawner_world_state": "0x2E000D03",
"match_spawner_scriptlets": {"start": ["Vfx_Active_State0", "Vfx_Spawner_Tier01"], "super": ["Vfx_Spawner_Tier02"]},
# deep-scan-maps.md 1.5 (C graph): dampener pose on death / respawn
"dampener_graph_events": {"death": "0x100001C0", "respawn": "0x100003FD"},
# deep-scan-maps.md 3.1 row 6 (C data): Crime Alley v AI team-2 lane turret = the team-1 turret's mirror class
"crime_alley_vai_turret_t2": "0x40000C8B",          # "0x40000C86" = today's class
```

Coast City / Gotham Divided vehicles: extend `liftable_props_by_map` once positions are chosen (the 0x8B path is
already generic).

---------------------------------------------------------------------------------------------------------------------

## 5. Tests to ask for (one run each)

1. Crime Alley: relay at the nook, locked: padlock hologram on the plate, padlock on hover, minimap padlock (after
   the parse fix). If the padlock shows only when unlocked, the polarity of 1.1 is inverted: swap true / false.
2. Crime Alley: dampener cover option (a) (z 199.6) and, separately, (b) (core pedestal); a screenshot from above.
3. Kill a dampener: it should fold into the ground (Death) and rise on respawn (Respawn).
4. Spawners: a portal effect at each mouth; minions appear from it.
5. Gotham Heights: the Destroyer explodes on death; the cannon shows a padlock while locked.

---------------------------------------------------------------------------------------------------------------------

## 6. Evidence index

Code: `0x96CA10` (per-team lock bool), `0xAA23C0` (usable refresh; `_Selection_Usage_Locked` start `0x588A00` ->
`0x57D8B0` / stop `0x588A80` -> `0x57C4B0`), `0xAA00D0` (usage-type 3 billboard `0x100007D5`), `0xA0CAB0` (note lock
mask), `0xA4B150` (objective note: 0x100006B6 / BD / BC / 0x100004FF listeners), `0xAA43A0` (property listener),
`0xA0A430` (use check: 0x1000034C, 0x10000506), `0x96CAE0` / `0x96CAB0` / `0x96CB10` (0x100005A6 / 0x100004FF /
0x1000060F), `0x555E20` / `0x555240` / `0x555EE0` (shape 0x8C1 / 0x8B1), `0x5722F0` / `0x572390` (physics component
reads 0x7EB / 0x990 / 0x2A4 / 0x6B4), `0x54CB80` / `0x5693A0` (model lookup class -> ws -> Setup 0x2D).
Records: relay `0x4900089D`, `0x2E000D12`, `0x2D000ADC`, `0x1D0004A0` / `A1`; Destroyer `0x2E000AB5`, `0x1D0003BA` /
`BB`; dampener `0x2E000E04`, `0x2D000BAF`, graph `0x1A000B15`, tables `0x1D0005A1` / `0x1D00063A`; spawner
`0x2E000D03`, `0x1D000491`, `0x400005C8`; pad `0x2E00104E` / `0x1D000924` (Raider drop `0x40000C49`, CC trigger
`0x4000054F`, `0x40000C7A`); Raider capsule `0x2E00101D` / `0x2D000D92`; cover `0x2E0000E3` / `0x2D00007B`;
`0x2E001329` / `0x2D001008`; graph-event table `0x300000A4` (pack `0xA0000038`); encounter templates
`0x49000C82` / `0x49000E74` / `0x49000B6B` / `0x49000B6A` / `0x49000B6C` / `0x49000991`; terrain `0x800113BB`,
`0x800113C3`, `0x800113CB`; statics `0x820113BB`, `0x820113C3`, `0x820113CB` / `14CB`, `0x82011BD3`, `0x820123E3`,
`0x82011BF3`.
