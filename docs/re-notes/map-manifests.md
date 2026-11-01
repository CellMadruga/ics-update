# Map manifests: what the original server created on each v AI map (2026-10-25)

One manifest per v AI map: every object the client cannot place itself (classes in the layout / variants packs,
type-3 markers with no record, tracker slots, objective tables, encounter references), with what ics creates today
(ics/match/maps.py + match.py / objectives.py / units.py, and logs/traffic.log of 2026-10-25 13:13 CA, 13:18 GH,
13:21 GD; CC last ran 08:57). Builds on map-gaps-gotham-divided.md, map-gaps-coast-city.md,
map-gaps-gotham-heights.md, announcer-and-map-elements.md 4, crime-alley-still-missing.md, crime-alley-visuals.md,
maps-complete.md 3-4. Tags: C = read in data / logs, P = probable, G = guessed, O = open.
"ics" column: OK = created and looks right, WRONG = created but wrong, NO = not created.

## 0. New checks done for this note (C)

- Statics re-scanned (scratch parser, format of maps-complete.md 2.2; type-3 entries listed in full per map).
- Scriptlet tables per class + its template world state (`Data.scriptlets(cls, Data.champion_world_state(cls))`):
  - The core world states `0x2E0013EE` (CA, CC) and `0x2E000AC5` (GD) hold **Vfx_Active, Vfx_AI_Active (CA only),
    Vfx_Destruct_State0/1, Vfx_OnExplode, Vfx_Indestructible(_Stop), Vfx_Relay_0N_*, Cinematic_Announcement** but
    **not Vfx_Startup / Vfx_Active_Blue / Vfx_Active_Red**. `[ics] match_structure_scriptlets.core = [Vfx_Startup,
    Vfx_Active, active]` therefore sends only Vfx_Active (traffic 13:13 / 13:21: `core t1: Vfx_Active` only; the other
    two are silently dropped by World.scriptlet). The team colour of the core must come from the side property /
    a child, not from a scriptlet on the core.
  - Core turret ws `0x2E000AC4`: Vfx_Active, Vfx_AI_Active, Destruct_State0/1, Indestructible; ics sends nothing.
  - Lane-turret body ws `0x2E000AA0`: Vfx_Active, Vfx_AI_Active; ics sends scriptlets to head / plate only.
  - Dampener ws `0x2E000E04`: Object_Activate / **Object_Deactivate**, Vfx_AI_Active, Vfx_Active, Vfx_Stop.
  - Foundry ws `0x2E001037`: **Vfx_Startup, Vfx_Active, Vfx_Active_State0-3/5, Vfx_Fidget_A-C, Vfx_Death**; ics
    sends nothing to the foundry (P: its idle / hologram never starts).
  - GH Power Core `0x400003F2` / ws `0x2E000B47`: only `0x5` and Vfx_Object_Reset. The Destruct_State / OnExplode
    keys of the GH end cinematics are cinematic-table keys: the server cannot play them on this entity (C), so
    map-gaps-gotham-heights.md 3.1's "Vfx_Destruct_State(N-1) on each tier" has no target; the tiers show only
    through the end cinematic (or O: through the cannon impact entity).
  - Relays `0x4000089D`, GD control point `0x400003AF`, GH cannon `0x40000511` (all ws `0x2E000D12`) and GH points
    `0x4000013B` (ws `0x2E000B22`): only SetNull / SetContention / OnTeamBiasChanged / OnSetClientRelationship.
  - Phase Pod `0x40000A79` / ws `0x2E000FC7`: Vfx_Spawn, Vfx_SpawnIdle, Object_Activate present (19 keys).
  - Superpad `0x40000CB5` / ws `0x2E001314`: Vfx_Active_Pad present (8 keys; no _Health / _Speed variants).
  - Doomsday pad `0x4000054F` / ws `0x2E00104E`: Vfx_Start_Pad_DoomsdayDevice, Vfx_Active_Pad_DoomsdayDevice,
    Vfx_Active_DoomsdayDevice(_Disabled), Vfx_Hidden, Vfx_Spawn_Event01-03.
- **Correction to map-gaps-coast-city.md 2.6**: Coast City *does* have a camp marker at (80.0, 57.0) yaw 180
  (`0x2E000942` / `944` / `945`, all five sites have the triple), so the Doomsday Guardian camp there is anchored (C).
- New: CC type-3 `0x2E000940` at (137.5, 60.5) / (139.2, 67.0) and `0x2E000941` at (22.5, 60.5) / (20.8, 67.0) (the
  lane mouths) and `0x2E000942` at the five camp sites are records in 0xA0000161 derived from `0x2E000006`
  (scriptlets Vfx_Active_Blue / _Red / _Yellow; ids `0x1000005D` = 107 / 106 / 105). GH's ten `0x2E000006` sit at
  five spots around (80, 74.5) (two per spot: (86, 75), (74, 75), (80, 80), (83.8, 68), (76.2, 68)). They are
  client-drawn team lights; their colour is P server-driven by id, mechanism O.
- Type-2 / 7 statics of all four maps: every world state was found as a record header in the map's three packs
  (C by byte scan, P that all draw).

## 1. Crime Alley v AI 0x40000C82 (LB 0x13BB, packs 0xA00002E5 / E6 / E7, z 200.3)

Tracker 0x100007F5 / 7FA = [26] / [1] (one SMALL_CAPTURABLE). Type-3 markers (all with no record): structures
`0x2E0011A7`/`A6` cores (17.5, 77.2) / (142.5, 77.8), `0x2E0011A9`/`A8` (40 / 120), `0x2E0011AD`/`AC` (65 / 95), lane
mouths `0x2E000AF9`/`AF8` (21.8 / 138.3, 77.5), camp `0x2E000944`/`945` (80.0, 97.2) yaw 180 + `0x2E001117`/`1120`,
ambient `0x2E00110F` (80, 77.5), (110.5, 78.5), `0x2E001110`, `0x2E001118` (48.8, 93), `0x2E00111B` (61.5, 77.5),
`0x2E001121` (80, 119). No marker for the core turret, gates, auras, stealth, side camps or the relay.

| Object | Class / ws | Pos / yaw / side | Start | ics |
|---|---|---|---|---|
| Core x2 | 0x40000C8A / C89, ws 0x2E0013EE | (17.5, 77.5) yaw 90 side 3; (142.5, 77.5) yaw -90 side 5 (C) | Vfx_Active (+ Vfx_AI_Active on v AI, P) | OK pos; WRONG start: Startup / Blue / Red dropped, Vfx_AI_Active never sent |
| Core turret x2 | 0x40000C8F / C8D, ws 0x2E000AC4 | (25.5, 77.5) / mirror (G, no marker; v AI only) | Vfx_Active, Vfx_AI_Active (P) | OK pos G; nothing sent |
| Dampener x2 | 0x40000C88 / C87, ws 0x2E000E04 | (40, 77.5) / (120, 77.5) (C) | Object_Activate, Vfx_Active | OK; black 12 m octagon still open (crime-alley-still-missing 2/6) |
| Lane turret x2 | 0x40000C8C / C86 body + head 0x2E000AA8 + plate 0x2E000A9F | (65 / 95, 77.5) (C) | head Startup + Blue/Red | OK |
| Foundry x2 | 0x40000170 / 16F, ws 0x2E001037 | (1.3, 77.1, 201.8) (G) | Vfx_Startup, Vfx_Active (P) | OK pos G; nothing sent |
| Base gate x2 | Door 0x40000557 / 0x2E000CD7, side 3/5 | (29.5, 77.5) (P) | Vfx_OnInit, Object_Closed; Object_Open at 0 | OK (tester-confirmed) |
| Base aura x2 | 0x40000C7F / 0x2E000A35 r 6 | (5, 77.5) (P) | Hotspot_Activate | OK |
| Stealth x6 | 0x4000039D / 0x2E000D36 | maps.py "stealth" (G from video) | Vfx_Active | OK-ish (streaks extra, shapes G) |
| Nook pad | 0x40000CB5 / 0x2E001314 | (80, 97.25) yaw 180 (C marker) | Vfx_Active_Pad | OK (P class) |
| Camps x3 | 0x40000CA1 + 2x CA0 | nook (80, 99.7) + (52, 90), (113, 90) (G) | Vfx_Spawn_Event01 (P) | P; side camps unanchored |
| **Relay (tracker 26/1)** | 0x4000089D / 0x2E000D12 | O (G nook or jungle centre) | SetNull | **NO** |
| **Raider** | 0x40000CA2 / 0x2E000F1B, kind 6 | nook (80, 97.25) yaw 180 (P) | Vfx_Spawn_Event01; lines 696/699/698; kill 61, drop 0x40000C49 | **NO** |
| Regen Destroyer | 0x40000CDA / 0x2E0010A7 | a side camp (G) | - | NO |
| Red-orb rocks | 0x400005C9 / 0x2E000D22 (G) | (80.1, 72.8), (54.7, 82.9), (105.0, 82.7) (G from video) | Vfx_Active (in table; Vfx_OnInit is not) | NO |
| Minions | 0x40000BF8 / BFA / BF9 | mouths (C) | - | OK |
| Bot champions | lobby bots | type-16 slots (C) | - | **NO** (scoreboard only) |

Client-drawn (not the server's job): terrain, 291 type-2/7 statics (core pedestals 0x2E000A3B, spawn platforms
0x2E000CA5, fences, buildings, lights), ambient emitters.

## 2. Gotham Divided v AI 0x40000B6B (LB 0x1BD3, packs 0xA0000168 / FC / 16E, z 250.2, team 2 = (y, x))

Tracker [29 x 4, 0x10000A9B x 2] / [1-4]. Type-3 markers: lane mouths `0x2E000AF5` (17.5, 134) yaw 180, `AF7`
(26, 142.5) yaw -90, `AF9` (23.5, 136.5) yaw -135 (team 1) and `AF4` / `AF6` / `AF8` (team 2); the triples 626 / 6B3 /
6B4 (17 each, generic, no server need known). No camp, beacon, gate or stealth marker.

| Object | Class / ws | Pos | ics |
|---|---|---|---|
| Core x2 | 0x40000A7E / A7B, ws 0x2E000AC5 | (17.5, 142.5) yaw 45 / (142.5, 17.5) yaw -135 (C) | OK; Vfx_Active sent |
| Core turret, 3 dampeners, 3 lane turrets per team | 0x400003BA/3C1, 0x40000C61/C60, 0x400003BB/C0, BF/BE, BC/BD | G (maps.py) | OK (G pos) |
| Foundry x2 | 0x40000170 / 16F | (5.4, 154.6) G | OK pos G; no start |
| Base gates x3 per team | 0x40000557 | frames 0x2E000EE1 (P) | OK (P) |
| Base aura x2 | 0x40000C7F | (7.5, 152.5) r 6 (radius P too small) | OK |
| **Beacons x4 (tracker 29, slots 1-4)** | typed Regen / Speed / Pulse / Vision (P) | O | **WRONG**: two 0x400003AF at (55, 55) / (105, 105) as slots 1-2 |
| **Phase pods Upper / Lower** | 0x40000A79 / 0x2E000FC7 | (105, 105) / (55, 55) pits (P) | **NO** |
| **Raider, Leviathan** | 0x40000938 / 0x40000937 | from the pods (P) | **NO** |
| Jungle camps | heavy+small Tripod / Scrapper / Mauler + Haste 93D / Regen 940 / Surveillance 93F | G quarters | P (2 kinds only, no buff destroyers) |
| Stealth tiles | 0x4000039D (GD zone pack) | O | NO |
| Bot champions | - | type-16 | NO |

Client-drawn: core pedestals 0x2E000A3B, spawn platforms 0x2E000CA5 / 0x2E001352, gate frames 0x2E000EE1, the
sunken neutral pits 0x2E0003F0 + 0x2E000FBE, the centre set-piece (80, 80), smoke decals 0x2E001396, lights.

## 3. Coast City v AI 0x40000B6A (LB 0x23E3, packs 0xA00000D2 / 161 / 162, z 250.2, team 2 = 160 - x)

Tracker [26, 26, 26, 28] / [1, 2, 3, 1]. Type-3 markers: camps 942 / 944 / 945 at (80, 145-146.8) yaw 180,
(44.5, 90.5) yaw 286, (115.5, 90.5) yaw -280, (80, 9) yaw 180, **(80, 57) yaw 180**; Device `0x2E001178` / `1181`
(80.0, 82.0) yaw 180; mouths `0x2E000AF4`-`AF7` + team lights 940 / 941.

| Object | Class / ws | Pos | ics |
|---|---|---|---|
| Core x2 | 0x40000C24 / C23, ws 0x2E0013EE | (17, 62.5) yaw 105 (C) | OK pos; Relay_0N beams on capture (match_relay_beams) |
| Core turret, inner + lane turrets | 0x40000400/3FF, 3FA/3F9, 3FE/3FB, 3FD/3FC | G | OK (G) |
| Foundry | 0x40000170 / 16F | (1.0, 59.2) G | OK G |
| **Base gates** | 0x40000557 / 0x2E000CD7 | necks (24.1, 79.0) heading 0 and (33.0, 51.5) heading 90 deg (G) | **NO** |
| Base aura | 0x40000C7F | (3.21, 58.8) / (156.79, 58.81) (C) | OK |
| Relays x3 | 0x4000089D | (80, 131), (62, 76), (98, 76) (G, no marker) | OK-ish G |
| Doomsday Device + pad | 0x400001F0 / 0x2E0008FD + 0x4000054F / 0x2E00104E | (80.0, 82.0) yaw 180 (C marker) | OK pos; firing rule WRONG (auto 25 % core hit instead of pad-aimed strike 0x4000035D, map-gaps-coast-city 2.5); pad never gets _Disabled while locked |
| Raiders | 0x400007C1 (80, 145), 0x40000D60 (80, 9) | C markers | OK (voices missing) |
| Small camps | 0x40000894 + 2x 898 | (44.5 / 115.5, 90.5) C | OK (marker yaw ignored) |
| Doomsday Guardian | 0x40000430 | (80, 57) yaw 180 (**C marker**) | OK |
| Stealth tiles | 0x4000039D | O | NO |
| Bot champions | - | - | NO |

Client-drawn: spawn platforms 0x2E000CA5, 536 type-2/7 statics, ~26 sound emitters 0x2E0005D6, team lights
940 / 941 / 942 (colour O).

## 4. Gotham Heights v AI 0x40000B6C (LB 0x1BF3, packs 0xA000009A / 16B / 179, z 250.1)

Tracker [8 x 5, 27] / [1-5, 1]. Type-3 markers: ten `0x2E000006` sockets around (80, 74.5); twenty team statics
`0x2E00041F`-`432` beside the points (records in 0xA000016B: client-drawn); triples 626 / 6B3 / 6B4.

| Object | Class / ws | Pos | ics |
|---|---|---|---|
| Power Core x2 | 0x400003F2 / 0x2E000B47 | (18.39, 50.08) yaw 15 / (142.67, 50.33) yaw -20 (C, cinematics) | OK (invulnerable) |
| Foundry x2 | 0x40000170 / 16F | (1.5, 47) / (158.5, 47) G | OK G |
| Base aura x2 | 0x4000041F / 0x2E000A35 | (4.0, 46.2) / mirror (P) | OK |
| Capture points x5 | 0x4000013B / 0x2E000B22 | (48.5, 27.5), (111.5, 27.5), (27, 90), (133, 90.2), (80, 127.8) (P) | OK pos; ring progress (CaptureBuffer vital) and point attack missing |
| **Orbital Cannon (tracker 27/1)** | 0x40000511 / 0x2E000D12, id 0x100001EB = 165 | (80, 74) (P) | **NO** |
| Script 0x340002CF on the cores | cannon controller | - | **NO** (no lighting 0x1000000D / 0B / 0A steps, lines 406 / 418 / 419 / 54) |
| Health-pack generators | 0x40000180 -> 0x40000182 / 0x400000A4 | O | NO |
| Stealth tiles | 0x4000039D | O | NO |
| Bot champions | - | - | NO |

Client-drawn: spawn platforms, team statics 0x2E00041F-432, sockets 0x2E000006, ~20 sound emitters, the subway
train (P client-animated).

## 5. Common to all maps

- Foundry start keys Vfx_Startup + Vfx_Active (P, C keys); core turret Vfx_Active (+ AI_Active on v AI) (P).
- Drop `Vfx_Startup` / `active` from `match_structure_scriptlets.core` (not in the core's tables, C); add
  `Vfx_AI_Active` on the CA v AI cores (P: its child 0x2E000AC3 is the turret-head-like piece; candidate for the
  missing "prow" hologram, crime-alley-still-missing 4).
- Bot champions are the largest gap on every v AI map (C).
