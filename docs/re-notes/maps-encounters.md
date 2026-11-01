# Maps, encounters and game modes (static survey, 2026-10-21)

Raw notes from a read-only survey of the player's packs (`rp\*.rp`) and the client exe (REA / Ghidra). Nothing
here comes from the game files beyond IDs, short internal names, numbers and positions. **C** = confirmed (read
from the data / exe), **G** = guessed (an interpretation that fits the data but has not been checked in the game).

How the data was read: records are `did | hdr | count | entries` (encounter templates 0x49..., settings 0x48...:
`hdr` 2 or 0); entries `key | key | value`, `key | key|0x40000000` = present without a value; kinds from
`catalog/data/properties.tsv` plus two found here: **kind 0x01 = ASCII string** (`u32 len | bytes`, padded to 4;
the encounter's internal name 0x1000062B) and **kind 0x06 = vector of 3 f32** (0x1000001F). Kind 0x14 (the map
pack 0x10000406) takes 8 bytes (`DID | 0`). Texts were resolved with `icserver.gamedata.Game.texts()` (English);
only names are quoted below.

## 1. The encounters

### 1.1 Where they are

- **All 28 encounter templates are in pack 0xA00000B3** (the game-data pack), DIDs 0x49xxxxxx, record header
  `did | 2 | count` (Gotham Heights v AI: 61 entries). The entity 0x40xxxxxx of the same low bits carries no
  gameplay data (C).
- **Master encounter list: record 0x48000001** (pack 0xA00000B3), one property **0x1000025D** = array of 27
  elements 0x100001D3 (encounter DID), in this order: 14B, 13E, 270, 39C, 399, E6D, E68, E74, EC0, C28, C82, B6C,
  B6A, B6B, E62, 168, 533, 9B4, 933, D63, D71, E61, E65, E5A, 991, A81, CA6 (all encounters except the "All
  Encounters Surrogate" 0x4000094C) (C). It has no flags: enabled / featured / queue type come from the server
  (0x2024, section 1.4).
- **Map groups: record 0x480010F6** property 0x10000BDE (C): 0x10000C79 = 7 groups (0x10000C78), each a list of
  encounters (0x10000DA2 / 0x10000BE5) plus a long list 0x10000BFC of 0x10000BE1 records (0x48001xxx, 2..159 per
  group; probably missions / daily quests, G):
  `{Coast City, Coast City v AI}`, `{Gotham Heights, Gotham Heights v AI}`, `{Gotham Divided, Gotham Divided v AI,
  PVP Event Test}`, `{Crime Alley Clash 1v1, Clash 2v2, Crime Alley v AI}`, `{Tutorial Intermediate}`,
  `{Crime Alley 1vAI Tutorial}`, `{Metropolis Skyway}`. Same record: 0x10000CAE = 7 entries (0x10000C7A enum 1, 8,
  0xC, 0xD, 0xE, 9, 0x10 -> 0x10000C7B 240 / 360 s), 0x10000CA0 = 10, 0x10000C76 = 40, 0x10000C7B = 300 (timers of
  that mission system, G).
- **Record 0x48001490** (0x10000D6D): 9 PvP / vs-AI encounters -> an entity 0x40000E9D..0x40000EA6 (0x10000C6B)
  each, in 0xA00000B3 (per-map stat / achievement trackers, G).

### 1.2 Template properties (meaning)

| Property | Kind | Meaning | |
|---|---|---|---|
| 0x10000047 | string | Display name | C |
| 0x1000062B | ascii | Internal map/ruleset name (`pvp_5v5_got_dom_team1` ...) | C |
| 0x10000B6B | string | Internal encounter name (`pvp_5v5_got_heights_bots` ...) | C |
| 0x10000D0B | enum | **Encounter category**: 1 vs AI, 2 challenge, 3 PvP, 4 tutorial, 5 test, 6 surrogate (catalog said "tutorial flag": it is the category; the end page skips the scoreboard for 4) | C values, G names |
| 0x1000028A | enum | Ruleset read by the loader 0xA99E20: 0x10000009 normal, 0x1000000B 1vAI tutorial, 0x1000000C Clash (1v1 / 2v2 tournament), 0x1000000D 5v5 vs AI | C values, G meaning |
| 0x1000054E | enum | Map id: 1 Crime Alley lane (vs AI, challenges), 2 Crime Alley / Apokolips Clash, 3 Gotham Heights, 4 Gotham Divided, 5 Coast City, 6 Metropolis Skyway, 7 Tutorial 1, 8 Tutorial 2, 9 Tutorial 3, 0xB / 0xC test maps | C values, G meaning |
| 0x10000406 | 0x14 | Map pack (category 1 / 17), lists the encounter's packs | C |
| 0x10000BCB | int | Players per team (5, 2, 1) | C (fits every row) |
| 0x10000BCC | int | Human players in total (10, 4, 2, 1; 5 in the 5vAI intermediate) | G |
| 0x10000B3C | int | 10 (2 for the Clashes and Crime Alley v AI): max slots? | G |
| 0x100002E9 | array | Teams 0, 1, 2 (0x100000CC: 0x10000314 team record 0x48..., 0x100001F4 index). Team records: 0x1000014E name ("Unnamed Team", "Team 1", "Team 2"), 0x10000258 a 0x21 colour/icon | C |
| 0x10000A5A | did | The local player's default team record (= team 1) | G |
| 0x100001D2 | did | Map info for the UI (0x48...): 0x10000391 name, 0x10000392 description, 0x10000C6D duration text, 0x10000C70 / 0x10000C71 team sizes, 0x10000C73, 0x10000383 / 0x100008D0 / 0x10000B8F images, 0x10000463 per-team 500 (GH), 0x10000464 1250 / 750 | C |
| 0x10000287 | did | Minimap settings (0x100002A8 256, 0x10000363 image, 0x1000063C, 0x100000C8, 0x1000009E/9F ...) | G |
| 0x10000897 | did | Lobby music pack (0xA0000188 Coast City, 0xA0000189 Gotham Heights, 0xA000018A Divided / default) | C |
| 0x10000C45 | string | Map overview movie (`map_<Map>Overview.bik`) | C |
| 0x10000C1B | string | Post-match movie (`vig_<Champion>Vignette.bik`) | C |
| 0x10000B66 / 0x10000B68 | did | Next / prerequisite encounter | C |
| 0x10000AE7 (0x10000AE6) | array | Required champions (tutorials: Gaslight Batman 0x40000086) | C |
| 0x10000B3E (0x10000B3D) | array | **Bot champion pool** (14 champions; 1 in Crime Alley v AI) | C |
| 0x10000B41 | did | Bot script 0x340007E2 (levels the bots' skills: CurrentLevel, Skill1Rank..SkillUltRank) | C |
| 0x10000B3F / 0x10000B40 | bool | Set on vs-AI encounters only | C |
| 0x100007F7 | array | 4..6 tables 0x100007F9 (0x100007F5 enum 8 or 0x1B, 0x100007FA 1..5): slot / lobby layout of the team | G |
| 0x10000CE0 | array | 2 lists (one per team) of 5 enums 0x10000CDE (0xB/8, 7, 6, 9, 0xA): bot roles / positions per slot | G |
| 0x100007BB | array | Coast City v AI: enums 2, 7, 5 | ? |
| 0x10000BB7 | int | 1 Crime Alley, 2 Coast City, 3 Gotham Divided (absent in Gotham Heights): **number of lanes** | G |
| 0x1000021C | f32 | 600 (300 tutorials) s | G (surrender / AFK limit) |
| 0x100004A1 | f32 | 60 (10 tutorials, 20 test, 75 1vAI tutorial) s | G (champion select time) |
| 0x10000802 | did | The map's own entity in its layout pack (0x4000047E GH, 0x40000554 GD, 0x40000534 CC, 0x40000D4C CA, 0x40000B69 Tut1); 0x10000803 = 0x4000047A (shared). Template 0x1000080A = list of 0x1000080C (0x10000806 event enum -> 0x10000895 / 0x10000829 / 0x1000082A / 0x10000894 / 0x10000805 sound ids) | G: announcer VO tables (map / general), matches 0x52 `Announcer_<Map>` / `Announcer_General` |
| 0x10000B21 | did | Tutorials / test: a scripted entity (Tut1 0x40000CB7, Tut2 0x40000CBC, Tut3 0x40000CE3) | G |
| 0x1000081E | did | Shop: 0x480007B0 / 0x48000EAA / 0x48000EA9 / 0x4800118B (18 stat categories + 210 item entities 0x10000693) | C |
| 0x10000A73, 0x10000B2C, 0x10000B53, 0x10000AB2 | did | Stats panel / scoreboard column lists (0x10000CEF stat ids; 0x48000FB0 "General", per-map "Offense / Defense / Advancement / Sector Objectives") | C |
| 0x100009E7 | did | Match-event rules (0x100009D2 list: enum 0x100009D6, hashes, 0x100009E5 ids; 0x100009F2 sound-id groups) | G: announcer triggers |
| 0x1000054F, 0x10000ADC | did | Small 0x48 records (0x10000531 present; 0x10000AD8 hash) | ? |
| 0x1000021D | array | 0x100005ED / 0x1000001F vector (1, n, m): differs per encounter | ? |

### 1.3 All 28 encounters

`map ok` = the map pack exists in this install. Players = 0x10000BCB per team / 0x10000BCC in total.

| Encounter | Name | Internal (0x1000062B / 0x10000B6B) | Cat. | 28A | Map id | Map pack | map ok | Players | Bots | Notes |
|---|---|---|---|---|---|---|---|---|---|---|
| 0x4000013E | Gotham Heights | pvp_5v5_got_dom_team1 / pvp_5v5_got_heights | PvP | 9 | 3 | 0xA0C11AF2 | yes | 5 / 10 | - | Domination |
| 0x40000270 | Coast City | pvp_5v5_cst_ons_team1 / pvp_5v5_cst_coastcity | PvP | 9 | 5 | 0xA0C122E2 | yes | 5 / 10 | - | Onslaught, 2 lanes |
| 0x4000039C | Crisis Labs: Coast City Variant | ..cst_ons_team1 / pvp_5v5_cst_coastcity_v2 | PvP | 9 | 5 | 0xA0C122E2 | yes | 5 / 10 | - | same map |
| 0x40000399 | Gotham Divided | pvp_5v5_got_rift_team1 / pvp_5v5_got_divided | PvP | 9 | 4 | 0xA0C11AD2 | yes | 5 / 10 | - | 3 lanes; FeaturedMap_PVP |
| 0x40000E6D | New Gotham Divided [test] | pvp_5v5_got_rift2_team1 / ..divided_v2 | PvP | 9 | 4 | 0xA0C11ACA | **no** | 5 / 10 | - | not in 0x2024 |
| 0x40000C28 | Metropolis Skyway | pvp_5v5_mch_aram_team1 / pvp_5v5_met_skyway | PvP | 9 | 6 | 0xA0C12AF2 | **no** | 5 / 10 | - | ARAM |
| 0x40000E68 | Crime Alley Clash: 1v1 | pvp_1v1_gas_lane_team1_a / ..1v1_gas_lane_tournament | PvP | C | 2 | 0xA0C112BA | yes | 1 / 2 | - | 1 lane |
| 0x40000E74 | Crime Alley Clash: 2v2 | same / pvp_2v2_gas_lane_tournament | PvP | C | 2 | 0xA0C112BA | yes | 2 / 4 | - | |
| 0x40000EC0 | Apokolips Causeway Clash: 1v1 | pvp_apo_lane_team1_a / ..1v1_apo_lane_tournament | PvP | C | 2 | 0xA0C10AE2 | **no** | 1 / 2 | - | |
| 0x40000B6C | Gotham Heights v AI | ..got_dom_team1 / pvp_5v5_got_heights_bots | vs AI | D | 3 | 0xA0C11AF2 | yes | 5 / 10 | 14 | |
| 0x40000B6A | Coast City v AI | ..cst_ons_team1 / pvp_5v5_cst_coastcity_bots | vs AI | D | 5 | 0xA0C122E2 | yes | 5 / 10 | 14 | FeaturedMap_BOTS |
| 0x40000B6B | Gotham Divided v AI | ..got_rift_team1 / ..divided_bots_beginner | vs AI | D | 4 | 0xA0C11AD2 | yes | 5 / 10 | 14 | prereq Tut 2 |
| 0x40000E62 | Gotham Divided - Intermediate - 5vAI [test] | same / ..divided_bots_intermediate | vs AI | D | 4 | 0xA0C11AD2 | yes | 5 / 5 | 14 | not in 0x2024 |
| 0x40000C82 | Crime Alley v AI | pvp_1v1_gas_lane_team1_a / pvp_1v1_gas_lane_bots | vs AI | 9 | 1 | 0xA0C112BA | yes | 1 / 1 | 1 | next GD v AI |
| 0x40000991 | Tutorial -- Basic | pve_tutorial_basic | tutorial | 9 | 7 | 0xA0C112CA | yes | 1 / 1 | - | implemented |
| 0x40000A81 | Tutorial -- Intermediate | pve_tutorial_intermediate | tutorial | 9 | 8 | 0xA0C112C2 | yes | 1 / 1 | - | Crime Alley's packs |
| 0x40000CA6 | Crime Alley: 1vAI Tutorial | pvp_1v1_gas_lane_team1_a / ..gas_lane_tutorial | tutorial | B | 9 | 0xA0C112BA | yes | 1 / 1 | 1 | next GD v AI |
| 0x40000D63 | Challenge: Gotham Divided Jungle [test] | pve_chl_got_rift_team1 / ..jungle1 | challenge | 9 | 4 | 0xA0C11ABA | **no** | 1 / 1 | - | |
| 0x40000D71, 0x40000E61 | Challenge: Crime Alley Defend Turret [test] | pve_chl_gas_lane_team1 / ..turret1, ..turret2 | challenge | 9 | 1 | 0xA0C112B2 | **no** | 1 / 1 | 1 | |
| 0x40000E65 | Challenge: Multi-bot Push [test] | same / ..multibot1 | challenge | 9 | 1 | 0xA0C112B2 | **no** | 5 / 1 | 15 | |
| 0x40000E5A | Challenge: Doomsday Device Defense [test] | pve_chl_cst_ons_team1 / ..dd1 | challenge | 9 | 5 | 0xA0C122DA | **no** | 1 / 1 | - | |
| 0x4000014B | PVP Event Test [test] | pve_test_simple / pvp_test_simple | test | 9 | 3 | 0xA0C10800 | **no** | 5 / 10 | - | in the GD map group |
| 0x4000094C | All Encounters Surrogate | pve_test_simple / pvp_all_encounters | surrogate | 9 | C | 0xA0C10800 | **no** | | - | not in 0x48000001 |
| 0x40000168, 0x40000533, 0x40000933, 0x400009B4 | Test (Gotham / Coast City / Divided) Destruction, Destruction Preview [test] | test_*destructibles* | test | 9 | B/C | 0xA0C102F2 / 2EA / 2E2 / 2D2 | **no** | 5 / 10 | - | |

Names marked [test] carry the untranslated-string marker in the data. **Playable in this install (map data
present): 15 encounters**, exactly the 15 `ics/messages.py ENCOUNTERS` lists minus Metropolis Skyway and Apokolips
Causeway (no map pack), plus Gotham Divided - Intermediate (pack present, test). Metropolis Skyway and Apokolips
Causeway Clash should be dropped from 0x2024 or the client will try to load packs it does not have (C: the pack
files are absent; the client's reaction is untested).

### 1.4 0x2024 Deliver Encounter Info (exe, handler 0xA733B0)

`u8 0 | list<u32> encounters | list<u32> flags | {u32 n x (cint, u8)} | list<u32> | u32 | {u32 n x (cint, u8)} |
u8 | wstr | wstr | u64`. The handler stores, in the encounter manager `[0xA12D50() + 0x68]` (C):
list 1 -> +0x04 (encounter DIDs), list 2 -> +0x14 (per-encounter flags, same order), map -> +0x34, list 3 -> +0x24,
u32 -> +0x70, the second map -> `[0xA12D50()+0x54] + 0x18C`, u8 -> `[0x1B77138] + 0xAF`, the two wstr -> +0x1FC /
+0x200, u64 -> +0x208; then 0xA9B210 (state bit 4) and 0x916280 raises `GM_Encounter.RecvNotice_MasterEncounterListReceived`
to the UI.
- The flags are the queue keys the UI joins with: the client's 0x20EB join-queue sends `encounter | 0x200000 | ...`
  (protocol-client-to-server.md), and the server's 0x20C0 / 0x2028 / 0x204C echo `did | qflags`. The server sends
  `(1<<21) | (1<<17)` for every non-tutorial encounter and 0 for tutorials, and that works (C, tested); which bit
  means "featured", "ranked" or "co-op vs AI" was not traced (the consumers of +0x14 sit in the Flash UI glue).
- Featured maps come from the account game settings (0x218B): `FeaturedMap_PVP` = 0x40000399, `FeaturedMap_BOTS` =
  0x40000B6A (C, ics/messages.py).
- Progression (unlocks): 0x214B Completed encounters + last map played; the templates' 0x10000B68 prerequisite /
  0x10000B66 next drive the tutorial chain 991 -> A81 -> CA6 -> B6B (GD v AI), and Crime Alley v AI -> GD v AI (C).

## 2. The maps

### 2.1 Packs per map (map pack 0x10000406 -> its pack list; `ics.gamedata.Data.map_packs`)

| Map pack | Cat. | Used by | Zone (0xD) | Layout (0xF) | Variants (0xE) | Other | Landblocks |
|---|---|---|---|---|---|---|---|
| 0xA0C112CA (1.3 MB) | 1 | Tutorial 1 | 0xA000024C | 0xA0000256 | 0xA0000257 | 0xA00002D6, 0xA00002D7 (7) | 0x13CB.. |
| 0xA0C112BA (80 MB) | 17 | Crime Alley v AI, 1vAI tutorial, Clash 1v1 / 2v2 | 0xA00002E5 | 0xA00002E6 | 0xA00002E7 | | 0x13BB.. (3x3) |
| 0xA0C112C2 (80 MB) | 17 | Tutorial 2 | 0xA00002E5 | 0xA00002E6 | 0xA00002E7 | | 0x13C3.. (same zone, own terrain) |
| 0xA0C11AF2 (80 MB) | 17 | Gotham Heights (+ v AI) | 0xA000009A | 0xA000016B | 0xA0000179 | | 0x1AF2-0x1CF4 |
| 0xA0C11AD2 (91 MB) | 17 | Gotham Divided (+ v AI, 5vAI) | 0xA00000FC | 0xA0000168 | 0xA000016E | | 0x1BD3.. |
| 0xA0C122E2 (147 MB) | 17 | Coast City, Crisis Labs CC, CC v AI | 0xA00000D2 | 0xA0000162 | 0xA0000161 | | 0x22E3.. |

Unlisted map-related packs: 0xA000006F (variants, category 14: Trooper / Soldier Drone 0x4000012D / 0x4000012E,
shared minions), 0xA0000164 (category 16: Meteor Fragment 0x400006F1, `mse_MeteorStorm`). Always-loaded:
0xA0000037 (generic world states 0x2E000000 / 0x2E000011).

**Map pack contents** (all category-17 maps, C): textures 0x13 (`did | 2 | .. | w | h | fourcc | size`), terrain
0x80 / 0x81 / 0x82 per landblock (3 x 3), **0x90 x 3 = navigation meshes** (Autodesk/Kynapse `BlobAggFile` /
`NavMesh`, one per agent size: radius 0.525 / 1.1 / 2.1, height 2.1 / 4.0) and **0x85 = the nav index** (3 entries
0x10000001..3 with the same radii); 0x85 / 0x90 records carry no DID of their own (they follow the pack's record
list order). A server can path its units on these meshes.

### 2.2 What the data does and does not hold

- **Entity classes** (turrets, cores, pads, minions, jungle units) are all in the layout and variants packs, with
  their team (0x1000009C), side (0x100007A2: 3 = team 1, 5 = team 2, 1 = the PvE enemy), name (0x3CE), creation
  type (0x50F), world state (0x510), attack skill (0x100008E3 block: script 0x10000328, stats) and server scripts
  (0x8E) (C).
- **Placements of the PvP gameplay objects are not in the client data** (C, searched every pack for every turret /
  core / control point class and world state): no layout record places them on Gotham Heights, Gotham Divided or
  Coast City. Only Crime Alley's layout pack 0xA00002E6 (shared with Tutorial 2) has named placements (63), like
  Tutorial 1. The original server held the PvP placements; a preservation server must author them (positions below
  are the available anchors).
- **Anchors that are in the data** (C, positions in landblock-local metres, z in the map's frame):
  - map pack 0x82 **type-21 points** (world state 0, `flags | 0x15 | index | iid | 0 | xyz | quaternion`, flag 0x80 =
    has properties): **lane waypoints and markers**; markers carry 0x100003E7 = 0x10000188 (G: spawn / objective
    marker);
  - map pack 0x82 type-3 team world states (Gotham Heights: 20, pairs of team 1 / team 2 variants at 10 sites);
  - **victory / defeat cinematics** (0x35) that place the PowerCore and five Player01..05 actors next to it (the
    end-of-match camera on each base).
- **Minion waves**: the unit classes and their attack scripts are in the data; wave composition, timing and
  spawner positions are not (only Tutorial 2 / Crime Alley's 0x2E000D03 `01Spawner` / `01BlueSpawner` placements
  and the `01MeleeA/B`, `01RangedA/B`, `01SiegeDrone` groups that leave it) (C / G).

### 2.3 Gotham Heights (domination) — 0xA0C11AF2, layout 0xA000016B, variants 0xA0000179

| What | DIDs | |
|---|---|---|
| Control Point | 0x4000013B (ws 0x2E000B22, has a basic attack) | C |
| Base | Base Team 01 0x4000041F (ws 0x2E000A35, team 1) | C |
| Turrets | 0x40000170 (team 1) / 0x4000016F (team 2), ws 0x2E001037 (the "Foundry" artifact turret); generic, in every PvP layout pack | C |
| Unnamed classes | 0x400005C9 (ws 0x2E000D22, scripts 0x34000167, 0x34000347, a mobile object), 0x40000511 (ws 0x2E000D12 = GD's control point world state), 0x40000621, 0x4000039D, 0x400003AB, 0x400003F2, 0x40000132, 0x40000180, 0x40000269 / 26B / 26D / 287 / 289 | C / ? |
| Minions | Destroyer Drone 0x40000EAA, Trooper Drone 0x4000012D, Soldier Drone 0x4000012E (attack 0x3400027E / 0x340004A1) | C |
| Capture logic | script 0x340002CF (variables LockTimer, NeutralizedTimer, LockDuration, NeutralizedDuration, Entry_Team01..02_Tier01..04, GeneratorIID ...), referenced by status record 0x480007C2 (0x10000539) | C names, G role |
| Match variables | 0x3A000029: BrushCounter, MatchTeamLost, MatchTeamWon, CapturePoint_Total_Team1, CapturePoint_Total_Team2 | C |
| Other scripts | 0x340001CF stealth brush (IsHidden, BrushIID), 0x34000138 speed buff, 0x3400012B regen (VitalPercentChangePerSec), 0x3400012D usage object, 0x340000D5 / 0x34000014 / 0x340005F7 turret attack and missile | C |
| Sounds | 0x52000012 Announcer_GothamHeights, 0x52000064 AMB_GothamHeights, 0x52000066 Music_GothamHeights | C |
| Cinematics | 0x3500000E / 0x3500000F (Character_0 at (18.4, 50.1)), 0x35000023 (team line-up: Chr_Center / ThePlayer / Chr_Left ...), 0x3500000D | C |
| Sites | type-3 team world states 0x2E00041F-0x2E000432 (parent 0x2E000006, 0x1000009C team, 0x1000005D id), pairs at (12.5, 91.5) / (14.5, 97.5) west, (147.5, 91.5) / (145.5, 97.5) east, (76.5 / 83.5, 141.5) north, (36.5, 16.5) / (42, 12.5) south-west, (118, 12.5) / (123.5, 16.5) south-east | C positions, G role (team-coloured spawn pads or capture-point decals) |
| Markers | 0x10000188 markers at (48.5, 27.5), (111.5, 27.5), (27, 90), (133, 90.2), (80, 127.8): five symmetric sites | C positions, G: the capture points |
| Paths | ~100 type-21 points: two mirrored loops (x 12..148, y 11..141) through the five sites | C / G |

Win condition (G): capture-point score (CapturePoint_Total_TeamN) until MatchTeamWon / MatchTeamLost; the UI side is
the objective tracker (section 3).

### 2.4 Gotham Divided (3 lanes) — 0xA0C11AD2, layout 0xA0000168, variants 0xA000016E

| What | DIDs | |
|---|---|---|
| Turrets | 0x400003BA, 3BB, 3BC, 3BF (team 1), 0x400003BD, 3BE, 3C0, 3C1 (team 2); ws 0x2E000AA0 (0x3BA / 0x3C1: 0x2E000AC4); script 0x34000838 (under-attack ping), attack 0x34000014; 14 damage stages 0x1000022F | C |
| Dampeners | 0x40000C61 (team 1), 0x40000C60 (team 2), ws 0x2E000E04 (inhibitor-like, G) | C |
| Power Cores | 0x40000A7E (team 1), 0x40000A7B (team 2), ws 0x2E000AC5 | C |
| Base | 0x40000C7F (ws 0x2E000A35); base scripts 0x340006C1 (CharacterIsInBase, regen, CanShop), 0x340006C0 (TempDefender speed) | C |
| Control Point | 0x400003AF (ws 0x2E000D12) | C |
| Neutral objects | Regen Pad 0x400008CF, Haste Pad 0x400008D7, Pulse Emitter 0x40000951 / 0x400009B6, Phase Pod 0x40000A79, Surveillance Drone 0x40000A83, Surveillance Tower 0x400007FD, Regen Pack 0x40000A86, Haste Pack 0x40000A87; deployable scripts 0x340004F6..0x3400050F (DeployedEntity, Team, ScatterRadius), 0x34000514 regen, 0x34000513 / 0x34000734 haste, 0x340004AB stealth reveal | C |
| Minions | Soldier Drone 0x4000010A, Trooper Drone 0x4000010B, Cannon Drone 0x4000010D, Elite Trooper 0x40000941, Elite Soldier 0x40000942, Destroyer Drone 0x40000E5F | C |
| Jungle (neutral camps) | Tripod 0x40000935 / 93B, Scrapper 0x40000936, Raider 0x40000938, Mauler 0x4000093A, Heavy Tripod 0x40000939, Heavy Scrapper 0x4000093C, Heavy Mauler 0x4000093E (script 0x3400007D: KillerIID, Team = on-kill team reward), Haste Destroyer 0x4000093D (0x3400051B), Regen Destroyer 0x40000940 (0x3400051A), Surveillance Destroyer 0x4000093F | C classes, G roles |
| Lanes | type-21 paths, one per lane and direction: top (148, 49) -> (142, 106) -> (86, 148) -> (26, 134) and back (49, 148) -> (148, 86) -> (145, 29); middle (118, 42) -> (88, 72) -> (34, 124) and back (42, 118) -> (134, 26); bottom (12, 111) -> (18, 54) -> (120, 13) and back (15, 131) -> (54, 18) -> (111, 12) | C points, G lane assignment |
| Bases / spawns | Power cores at (17.5, 142.5) team 1 and (142.5, 17.5) team 2 (cinematics 0x35000014 / 0x35000015); five spawn-like points around each base (15-25, 135-146) and (135-146, 15-24); 0x10000188 markers (145.7, 21) / (139, 15) and (20.7, 145.7) / (14, 139.1) | C positions, G roles |
| Sounds | Announcer_GothamDivided 0x52000015, Music_Divided 0x5200005B, AMB_GothamDivided 0x52000063 | C |

Win condition (G): destroy the enemy Power Core (the cinematics frame it).

### 2.5 Coast City (onslaught, 2 lanes) — 0xA0C122E2, layout 0xA0000162, variants 0xA0000161

| What | DIDs | |
|---|---|---|
| Turrets | 0x400003FA, 3FD, 3FE, 400 (team 1), 0x400003F9, 3FB, 3FC, 3FF (team 2); ws 0x2E000AA0 / 0x2E000AC4 | C |
| Power Cores | 0x40000C24 (team 1), 0x40000C23 (team 2), ws 0x2E0013EE; at (17, 62.5) / (143, 62.5) (cinematics 0x35000013 / 0x35000012) | C |
| Objective | Doomsday Device 0x400001F0 (ws 0x2E0008FD), Firing Trigger 0x4000054F; sounds mse_DoomsDayDevice 0x52000005, mse_EarthQuake 0x5200000D | C classes, G: the Onslaught objective that fires at a core |
| Base | 0x40000C7F, scripts 0x340006C1 / 0x340006C0 | C |
| Minions / jungle | Trooper / Soldier / Cannon Drone, Elite Trooper / Soldier, Raider (Drone), Destroyer (Drone) 0x40000D5C / D62 / 893, Surveillance Drone 0x40000892, Tripod / Heavy Tripod, Scrapper / Heavy Scrapper, Mauler / Heavy Mauler (0x40000894..0x4000089A), `chr_Min_DDD_Guardian` 0x5200006D | C |
| Paths | type-21 patrol loops (camps) e.g. (70, 24) <-> (90, 24), (80, 58) -> (65, 50), (22, 60) cluster west, (140, 66) cluster east | C points, G roles |

### 2.6 Crime Alley (1 lane) — 0xA0C112BA / Tutorial 2 0xA0C112C2, layout 0xA00002E6, variants 0xA00002E7

| What | DIDs | |
|---|---|---|
| Structures | Turrets 0x40000C86, C8B, C8D, C93, C97 (team 2), C8C, C8E, C8F, C92, C94 (team 1), 0x40000E86; Dampeners C87 / C95 (team 2), C88 / C91 (team 1); Power Cores C89 / C98 (team 2), C8A / C90 / C96 (team 1); Base 0x40000C7F / 0x4000041F; Regen Pad / Pack. Several per side: tutorial and Clash variants (scripts 0x340007EC turret warning + LessonsEnabled, 0x34000600) | C |
| Minions | Soldier / Trooper / Cannon Drone (several sets), Elite Trooper / Soldier, Raider (0x34000670), Tripod / Heavy Tripod, Regen Destroyer, Surveillance Drone, Watcher Drone 0x40000EB5 | C |
| Placements (named, 63) | lane along y = 77.5: power cores at (17.5, 77.2) team 1 and (142.5, 77.8) team 2 (cinematics 0x3500003B / 0x3500003A); BlueTurretBody (65, 77.5), RedTurretBody (95, 77.5); 01TurretFriendlyHead (25.1, 77.5), 01TurretEnemyHead (75, 77.5); spawner 0x2E000D03 at (71.8, 77.5); `01..02 Melee / Ranged / Siege` minion groups with paths; BaseGate 0x2E000CD7 (0, 68.3), PowerCoreTarget (17.6, 77.4); the Tutorial 2 cinematics' actors | C |
| Lane / spawns | type-21 path (23, 78) -> (106, 78) and back; 0x10000188 markers at (21.8, 77.5) and (138.2, 77.5) = one per team | C points, G: respawn points |

### 2.7 Tutorial 1 — see reverse-engineering.md section 12 and "Layout placement properties" (implemented).

## 3. What a server must do per map (generalising Tutorial 1)

1. **Login**: list only encounters whose map pack exists (`Data.encounter(did)["map_pack"]` file present) in 0x2024,
   with the queue flags the UI expects ((1<<21)|(1<<17), 0 for tutorials); featured maps in 0x218B; progression in
   0x214B (C, current server).
2. **Lobby**: team size / player count from 0x10000BCB / 0x10000BCC, lobby music 0x10000897, champion select timer
   0x100004A1 (G); for vs-AI fill the other slots from 0x10000B3E (bots).
3. **Enter match (0x20AF)**: the encounter DID, every champion in the match (players and bots, their packs follow
   from the DIDs) and the pack list = map pack + `map_packs(map pack)` (zone, layout, variants, extra) (C: the client
   loads exactly what is named; Tutorial 1 works this way). Set player property 0x100001D3 = encounter (minimap).
4. **World**: the client places the map pack's 0x82 statics itself; the server creates every gameplay object as an
   entity of the layout / variants classes (team 0x1000009C, side 0x100007A2, world state 0x510, creation type
   6 / 8 for "unique", scripts 0x8E, scriptlet templates 0x7D2). For Crime Alley / Tutorials positions come from the
   layout placements; for Gotham Heights / Gotham Divided / Coast City they must be authored (anchors in 2.3-2.5:
   lane waypoints, base cinematics, markers) and kept in a server-side table (catalog), not in code.
5. **Units**: minions follow the type-21 lane waypoints (or the 0x90 navmesh); attacks from the variant's skill
   block (script 0x10000328 + stats) as for the tutorial drones; jungle units on their patrol loops; on-kill scripts
   0x3400007D / 0x3400051A / 0x3400051B give team rewards (G).
6. **Structures**: turrets / dampeners / cores attack with their basic-attack script (0x34000014 + 0x340005F7
   missile) and ping when hit (0x34000838); base area scripts 0x340006C1 (regen, shop) / 0x340006C0.
7. **Objectives and HUD**: GM_Encounter UI notices (protocol-server-to-client.md): 0x2034 / 0x2009 / 0x2023
   objectives and categories, 0x2075 tracker enabled, 0x2069 tracker status, 0x100004FB / 0x10000134 team health
   (cores), 0x10000109 SetMatchTime, 0x10000455 / 0x10000456 surrender, timeline banners 0x10000424 / 0x100002AB ...,
   UpdateHasBaseAccess / UpdateHasVendorAccess (shop), end-of-match stats (scoreboard columns from 0x10000AB2 /
   0x10000B2C / 0x10000A73) and 0x1000000E match ended.
8. **Win**: Power Core destroyed (GD, CC, Crime Alley), capture-point score (GH), then the core's cinematic
   (0x35000012..15, 0x3500003A / 3B) and the post-match movie 0x10000C1B.

## 4. Open questions

- Queue-flag bits of 0x2024 (+0x14) beyond the working value; the other 0x2024 fields (maps, list 3, wstrs).
- 0x1000028A / 0x1000054E / 0x100007F7 / 0x10000CE0 exact meanings; 0x1000021C and 0x100004A1 timers.
- Gotham Heights' unnamed classes (0x400005C9, 0x40000511, ...) and how many capture points the mode used.
- Wave timing and composition (not in the data); the jungle camp positions on GD / CC (patrol loops are candidates).
- The 0x10000188 marker kind (property 0x100003E7) and the type-3 / type-10 statics' roles.
