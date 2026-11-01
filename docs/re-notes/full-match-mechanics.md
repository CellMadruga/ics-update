# Match mechanics and game modes (decompilation survey, 2026-10-22)

What the Infinite Crisis client (exe decompilation `re-work/decomp`, Flash AS2 `re-work/ui-as2`) and the game data
(`rp\*.rp`, read with `ics.gamedata`) hold about **how a PvP match runs**, and what a preservation server has to author.
Builds on `maps-complete.md` (positions, classes, packs), `units-and-ai.md` (unit stats, formulas, AI),
`progression-meta.md`, `ui-complete.md`, `protocol-complete.md`, `cinematics-vfx-audio.md`; their facts are only
summarised here, with a pointer. Only IDs, internal names and numbers are quoted (no game texts).

**C** = confirmed (code or data read), **P** = probable (strong inference), **G** = guessed / proposed, **O** = open.
Addresses are exe VAs (base 0x400000). "Flash `X.Y`" = AS2 class in `ui-as2/c_a00000d0_02189b08/scripts/__Packages`.

---------------------------------------------------------------------------------------------------------------

## 0. New findings in this survey (summary)

| # | Finding | |
|---|---|---|
| 1 | **Notice `0x1000005B` is the match roster / scoreboard snapshot.** Element reader `0x867bf0` fills exactly the 0x60-byte row that the scorecard builder `0xa4a4f0` reads (`+0x30` agent IID, `+0x38` player IID, `+0x40` champion DID, `+0x44` team, `+0x48` f32 money, `+0x4c` level, `+0x50` kills, `+0x54` deaths, `+0x58` assists, `+0x5c` bot). Its listener `0xa901f0` (vtable `0x1605930` slot `+0x98`) stores the list (`0xa32200`) and then builds `UI_UpdateMatchScorecard` (`0xa4a4f0` -> Flash deliver `0x8e7d90`), the participant/team-portrait list `AddParticipant` (`0xa4a030` -> `0x8dce70`) and the spectator team totals (`0xac49a0` -> `ViewMatchScoreboardData`). So the in-match Tab scoreboard, the team portraits and the KDA come from **one server notice** | C |
| 2 | **Event `0x217A` is the kill feed** (`NotifyPlayerDied`): exec `0x8ab2e0` passes its fields to `0xa67110`, which queues a delayed item that `0xa66fe0` later delivers to Flash `GM_Character.RecvNotice_NotifyPlayerDied` (`0x8cc830`). Layout `u64 victim | u32 victim icon DID | u32 victim team | u64 killer | u32 killer team | list<u32> killer+assists` | C |
| 3 | **Notice `0x1000021C` is the kill card** (listener vtable `0x1604908` slot `+0x60` = `0xa61260` -> `UI_ShowKillCard` deliver `0x8d1e70`); `0x100002B2` (same layout + leading u64) is the spectator / per-entity variant (slot `+0x64`) | P (vtable base inferred from slot alignment) |
| 4 | **Encounter-listener vtable `0x1605930`** (match HUD controller) maps every Encounter notice to its handler: `+0x38` `0x10000424` -> `0xa488d0` AddTimelineBanner; `+0x3c` `0x100002AB` -> `0xa786f0` AddTimelineEvent; `+0x40` `0x100002AE` -> `0xa72340` BatchAddTimelineEvent; `+0x44` `0x100002AF` / `+0x4c` `0x100002B1` -> `0xa68000` / `0xa5a240` StartTimeline; `+0x48` `0x100002AC` -> `0xa48a50` remove banner / event; `+0x50` `0x1000000E` -> `0xa809e0` match ended; `+0x7c` `0x10000109` -> `0xa902f0` SetMatchTime; `+0x98` `0x1000005B` -> `0xa901f0`; `+0x5c` / `+0x60` (`0x100000CA` / `0x100000CD`) are empty stubs (`0xa0b5a0`) in this class | C |
| 5 | **Surrender wire layout** (reader `0x90b3d0`, deliver `0x8ea0b0`): `0x10000455` = `u32 n | n x u8 vote | u32 expected votes | u8 can vote | f32 time remaining | f32 total time`; the vote is **started** by the start-menu button sending `SurrenderResponse(true)` (`0x10000454`) | C |
| 6 | **Team health = the Dominion / Clash ticket bar.** Flash `TeamHealthDisplay` (default start 500, low warning < 25) is added only for `Got_Dominion` (Gotham Heights) and `Gas_Lane_Tournament` (Clash); the UI record's `0x10000463` holds exactly 500 / 500 (GH), 200 / 200 (Clash 1v1), 300 / 300 (Clash 2v2). So `0x10000463` = starting team health, sent with `0x100004FB` | C (UI), P (link) |
| 7 | **Sector-objective tracker setup is in the encounter template**: `0x100007F5` = MapNoteCategory per tracker slot, `0x100007FA` = HUD position, `0x100007FC` = icon. Coast City `[26, 26, 26, 28]` / `[1, 2, 3, 1]` = 3 small capturables + 1 large map objective (exactly the Flash test layout of `SectorObjectiveTracker`), Gotham Divided `[29 x 4 ...]` / `[1, 2, 3, 4]` = 4 beacons, Gotham Heights category 8 (capture point) x 5 | C data, P roles |
| 8 | **Match clock semantics** (Flash `MatchManager` / `MatchTimer`): `SetMatchTime(start, end, isPreStart)`; while `isPreStart` the clock counts down to `start`, afterwards it counts up from `start`; `end` must be > 0 for the timer to run. All `tt*` / `ts*` values (respawn, surrender, timeline) are absolute game-clock seconds (`GameplaySystem.GetTime`) | C |
| 9 | **Encounter type enum** (Flash `EncounterIdentifierTypeList` = template `0x1000054E`): 1 Gas_Lane (Crime Alley), 2 Gas_Lane_Tournament (Clash), 3 Got_Dominion (GH), 4 Got_Rift (GD), 5 Cst_Onslaught (CC), 6 Mch_Aram (Metropolis), 7/8/9 Tutorial Basic / Intermediate / Advanced, 10 Test, 11 Destruction, 12 Unknown; it selects the HUD pieces of each mode (section 1.2) | C |
| 10 | Enumerations recovered from Flash: LifeState, MapNoteCategory (meteor / health / stormshield / speed pickups, capture points, beacons, power core, device), MapNoteDecoration (meteor impact / devastation zones, Doomsday revenge overlay, locked / disabled), PerceivedType (Turret 16, **Inhibitor 2048** = dampener, CapturePoint, DoomsdayDevice, Device, Siege, Lieutenant, Boss ...), ObjectiveState / CategoryState, MissionEventNotificationSeverity, BillboardUpdateType, TeamUsageLock (section 13) | C |

---------------------------------------------------------------------------------------------------------------

## 1. Game modes

### 1.1 Modes and their templates

Template data: `maps-complete.md` 1.1 (all 28 templates). Here the mode-level view.

| Mode (encounter type) | Encounters | Players | Win condition | Client HUD (Flash `MatchManager.OnLoadComplete`) | Tag |
|---|---|---|---|---|---|
| **Gotham Divided** (4, `Got_Rift`, internal `rift`) | `0x40000399` PvP, `0x40000B6B` v AI, `0x40000E62` 5vAI intermediate, `0x40000E6D` new-GD test | 5v5 | destroy the enemy power core; 3 lanes, turrets + dampeners, jungle + Leviathan, 4 beacons | event timeline, sector tracker (4 beacons) | C HUD, P rule |
| **Coast City** (5, `Cst_Onslaught`) | `0x40000270`, `0x4000039C` Crisis Labs, `0x40000B6A` v AI | 5v5 | destroy the enemy core; 2 lanes + 3 small capturables + 1 large map objective (the Doomsday Device) | event timeline, sector tracker (3 small + 1 large) | C HUD, P rule |
| **Gotham Heights** (3, `Got_Dominion`) | `0x4000013E`, `0x40000B6C` v AI | 5v5 | team health (500 each) drained by holding capture points; 5 points, no lanes | **team health bar**, event timeline, sector tracker (5 capture points) | C HUD, P rule |
| **Crime Alley** (1, `Gas_Lane`) | `0x40000C82` v AI (1v1 vs bot) | 1v1 | destroy the enemy core; 1 lane | event timeline, sector tracker | C |
| **Crime Alley Clash** (2, `Gas_Lane_Tournament`) | `0x40000E68` 1v1, `0x40000E74` 2v2; `0x40000EC0` Apokolips Clash (not installed) | 1v1 / 2v2 | **team health** (200 / 300) or core (O which first) | **team health bar**, event timeline, **no** sector tracker | C HUD, P rule |
| **Metropolis Skyway** (6, `Mch_Aram`) | `0x40000C28` (map not installed) | 5v5 | O (ARAM) | event timeline only | C HUD |
| **Tutorials** (7 / 8 / 9) | `0x40000991` Basic (T1), `0x40000A81` Intermediate (T2), `0x40000CA6` Advanced (Crime Alley 1vAI) | 1 | objective lists + scripts; T3 = core destruction (`0x34000628`) | Advanced: event timeline + sector tracker; Basic / Intermediate: no match bar elements in this switch | C |
| Challenges / tests | `0x40000D63` jungle, `0x40000D71` / `0x40000E61` defend turret, `0x40000E65` multi-bot push, `0x40000E5A` Doomsday defence, destruction tests | 1 | O (maps not installed except Crime Alley's lane `0xA0C112B2` no) | | C list |

Mode-independent per template (C, `maps-complete.md` 1.1): category `0x10000D0B` (1 vs AI, 3 PvP, 4 tutorial ...),
ruleset `0x1000028A` (9 normal, B 1vAI tutorial, C Clash, D 5v5 vs AI; filters statics by `0x55B`), players
`0x10000BCB` / `0x10000BCC`, bots `0x10000B3E` pool / `0x10000B41` levelling script, shop `0x1000081E`, announcer
`0x10000802` / `0x10000803`, music rules `0x100009E7`, lobby music `0x10000897`, minimap `0x10000287`,
UI/objective record `0x100001D2`, sector tracker `0x100007F5` / `0x100007FA` / `0x100007FC` (this note, 7.1).
Draft / blind pick / all random: `EncounterLobbyRules` 1 / 2 / 3 (C, Flash enum).

### 1.2 HUD pieces per mode (Flash `gameplay.match.MatchManager`, C)

Always: team displays (portraits + respawn timers, `TeamDisplayContainer`), personal score (KDA), match timer.
Then by encounter type: GH -> `TeamHealthDisplay` + `EventTimerV2` + `SectorObjectiveTracker`; CC, GD, Crime Alley,
Tutorial Advanced -> `EventTimerV2` + `SectorObjectiveTracker`; Clash -> `TeamHealthDisplay` + `EventTimerV2`;
Metropolis -> `EventTimerV2`; any other type reports an error and builds nothing (so Tutorial 1 / 2 have no match bar
pieces). The surrender panel (`SurrenderPanel`, HUD element `SurrenderPanel_UIHUDElementID`) is always created;
the start menu hides its Surrender button in tutorials and in spectator mode (Flash `StartMenuDialog.SetupButtons`).

---------------------------------------------------------------------------------------------------------------

## 2. Match clock, phases and start

| Item | Evidence | Server action | Tag |
|---|---|---|---|
| Match clock | Flash `MatchManager.StartMatchTimer`: first from query `InqMatchTimes` (`0x100001B8`, local), then on notice **`0x10000109` SetMatchTime** `(f64 start, f64 end, u8 isPreStart)` (reader `0x941d60`, deliver `0x9173c0`, C++ handler `0xa902f0`). `isPreStart = 1`: countdown to `start`; `0`: counts up from `start`. `0xa902f0` stores start/end at `this+0x34/+0x3c` and, when `isPreStart = 0`, pushes the start time into the HUD objects (`+0x148` of the minimap/timeline object) | send `0x10000109` with `isPreStart = 1` during the intro / pre-start, then `isPreStart = 0` at match start; `end` = any value > start (e.g. start + 3600) | C |
| HUD ready | client notice `0x100000D2` (`0x88baf0`, from `0xa0cbc0`) after the match HUD is set up | answer with `0x10000109` (and the timeline start) | C sender, P meaning |
| Clock sync | `0x10000076 TimerClockSync (u32 server clock)` (`0x8c4a00` / `0x8bf4f0`); the game clock itself comes from the connection time packet `0x1000000` | not needed if the time packet is right | C |
| Pre-start / intro | intro line-up cinematic per map (13 s, script `0x340006F2`: CA `0x3500003C`, GH `0x35000023`, GD `0x35000024`, CC `0x35000020`) | play it, then start the clock | C data |
| Unit level by time | formula `0x3B00000D` etc.: `clamp(floor((Time + 90) / 90), 1, 100)`: minions, jungle and structures gain a level every 90 s | `Time` = seconds since `start` | C (formula), P (time base) |
| Template timers | `0x1000021C` = 600 s (300 tutorials), `0x100004A1` = 60 s (10 tutorials, 75 CA 1vAI, 20 tests); no match-length field | G: `0x1000021C` = earliest surrender / AFK limit, `0x100004A1` = pick / pre-start time | G |
| `0x10000464` (UI record) | GH 1250, CC 1000, GD 750, Clash 1v1 1000 / 2v2 750, CA v AI 1000, T2 1500, CA 1vAI 1000 | G: the par / target match time in seconds sent as `fTargetTime` of `NotifyMatchEnded` (used for the end-of-match tier) | G |
| Match variables | `0x3A000029` (GH layout): BrushCounter, MatchTeamLost, MatchTeamWon, CapturePoint_Total_Team1/2 | names of the server's own counters | C names |
| Script hooks | node `0x10000152` GetMatchTime; event `0x10000085` "match / encounter phase start" starts GH's generator script `0x340002CF` | raise `0x10000085` on match start for map scripts | C nodes, P event |

---------------------------------------------------------------------------------------------------------------

## 3. Death, defeat flow and respawn

### 3.1 State and messages (C)

- **Life state** = champion property `0x100000FA` (enum `0x300000E2`, net mode 1): 1 DeadAndFaded, 2 Dead,
  3 Incapacitated, 4 Alive, 5 Respawning (Flash `LifeStateList`). The client reacts to the property itself
  (`0xa80cd0`, property-change switch: `0x100000FA` -> `0xa807b0` (minimap / overhead update) and, for state 2 on the
  local player, `0xa0a600` (a client-side respawn hint)); the music system uses life-state changes per team as cues
  (`cinematics-vfx-audio.md` 4.4).
- **`0x10000090` DefeatStatusUpdated** `(u32 state, f64 time of next state)` to the player's object: Flash
  `DefeatManager.OnStateChange`: 3 Incapacitated -> panel `Incapacitated2` with countdown; 2 Dead -> panel `DeadTimer`
  on the character panel counting down to `ttNextState` (`DefeatStatus.SetupTimer` -> `StartCountdownTimerNow`); 4 Alive
  -> "just respawned" (the kill card hides when the player leaves the base: `UI_UpdateHasBaseAccess(false)`).
- **`0x100000BC` DefeatStatusUpdatedForEntity** `(u64 entity, u32 perceived type, u32 state, f64 time)`: the team
  portraits' respawn timers (MatchData / `MatchTeamDisplay`, which first sends `UI_ReadyForDefeatStatus` `0x100003E6`,
  local). **`0x100000BA`** pauses an entity's timer `(u64, u32 current state)`.
- **Kill card** (`0x1000021C`, to the victim; section 0 #3): attackers (IIDs, icons, teams), killer name override,
  per-attacker total damage and 4 skill-slot columns (damage, slot type, damage type, icon, source artifact / mod,
  name / tooltip overrides), damage-type totals and percentages (Attack / Power). Flash `DefeatManager.RecvNotice_UI_ShowKillCard`;
  the kill-card button appears after the first one. `HideKillCard` is local.
- **Death recommendations panel** (`DefeatRecommendationsPanel`) shows while the player has vendor access
  (`UI_UpdateHasVendorAccess`, from the base aura attribute `0x10000A23`; `progression-meta.md` 1.4) and uses
  `0x2078` recommended upgrade (already sent by `ics`).
- **Kill feed** = event **`0x217A`** (section 0 #2) to every player; Flash `KillDisplayManager`: 4 rows, 5 s each.
  The client delays the item by a configured time (`0x10000001` timer value) before showing it.
- **Billboard** for kills / structure kills: `0x100002EB` ShowAnnouncement type 2 (generic: text + source icon +
  target icon + team colour) (section 10).

### 3.2 What the server must author

| Rule | Data | Proposal / evidence | Tag |
|---|---|---|---|
| Respawn duration | none in the client (no property / formula / string) | per-level table, server config; the original shipped values are unknown | O |
| Incapacitated phase | state 3 exists with its own panel | P: a short downed state before Dead (some champions / modes); safe default: skip it (Alive -> Dead) | P |
| Respawn position | type-16 start points per team (`maps-complete.md` 0 #1) | respawn at the team's start slots; send `0x100000FA` = 5 then 4, `0x10000090` state 4 | P |
| Death XP / gold | formulas `0x3B000003` (champion kill XP), `0x3B0000B7` (bounty: base 400, +20 % per consecutive kill up to 900, down to 75 on death streaks, ramped by victim level) | evaluate the 0x3B tree (`units-and-ai.md` 3.3) | C formulas |
| Assist window, last-hit rules | `LastHit` / `DamagedByTypes` inputs of the credit formulas | server tracks damage contributors (also needed for the kill card) | C inputs, O window |

---------------------------------------------------------------------------------------------------------------

## 4. Scoring and the scoreboard

| Item | Evidence | Tag |
|---|---|---|
| In-match scoreboard (Tab) + team portraits | **notice `0x1000005B`** = `u32 n | n x {StringInfo name, u64 (unknown, P account), u64 agent IID, u64 player IID, u32 champion DID, u32 team, f32 money earned, u32 level, u32 kills, u32 deaths, u32 assists, u8 is bot}` -> `0xa901f0` -> `UI_UpdateMatchScorecard(IIDs, playerIIDs, DIDs, names, isBot, isIgnored, levels, teams, kills, deaths, assists, money, yourIID, yourTeam)` + `AddParticipant` + `ViewMatchScoreboardData`. Flash asks for it with `RequestMatchScorecard` (`0x10000098`, local -> C++ slot `+0x70` `0xa5a550`, which rebuilds from the cached roster). **Send the full roster on every K/D/A/level/money change** (or periodically) | C |
| Team totals (spectator) | built by `0xac49a0` from the same roster; `ViewMatchKDATotal` / `GoldTotal` (`0x100002D3` / `D4`) have no listener | C |
| Personal score | Flash `PersonalScore` (KDA of the controlled agent) from MatchData | C |
| Score formula | `0x3B000038` = `Saves x 40 + Kills x 50 + Money x 5 - Deaths x 250` (end-of-match "score" column, P) | C formula, P use |
| Team health (GH / Clash) | `0x100004FB` InitialTeamHealthUpdate `(list teams, list start health, list health)`, `0x10000134` UpdateTeamHealth `(list teams, list health)` as answer to client `0x10000137` RequestCurrentTeamHealth and on change; values rounded up, a sound under 25 | C |
| Structure counts (spectator top bar) | GD: turrets + dampeners (`ViewMatchTopDivided`), CC: turrets (`ViewMatchTopCoastCity`); dampener counts = event `0x215C` (list per team); turret counts are counted by the client (`0xabf1c0` / `0xabf2a0`, no network source found) after `RequestMatchStartCounts` (`0x10000490`, local) | C |

---------------------------------------------------------------------------------------------------------------

## 5. Structures

Classes, HP, positions: `maps-complete.md` 3-4, `units-and-ai.md` 1.4. Summary:

| Structure | Classes (team 1 / team 2) | Data | Client side | Server must author |
|---|---|---|---|---|
| **Turret** (PerceivedType Turret 16, map note TURRET 3) | GD `0x400003BB`/`BC`/`BF` + core turret `0x400003BA` (and `3C0`/`3BD`/`3BE`/`3C1`); CC `0x400003FA`/`FD`/`FE` + `0x40000400` core turret (and `3F9`/`3FC`/`3FB`/`3FF`); CA tutorial / Clash families (`0x40000C86`.., `0x40000C92`..) | HP 2550-3000 (`0x3B000051`-`54`), damage `175..200 + 4 x Level`, sight `0x10000133`, attack `0x34000014` (range 9 m), tier stat `0x10000B84` (GD 45/55/60, CC 35/45/55/100), XP `0x3B000016`, credits 100/N, **team bounty** 90..350 (`0x10000362`), script `0x34000838` ("under attack" map ping, `MapManager.MapNote_UnderAttack`) | "Turret warning indicators" option (string `0x16043f4`, `0xa891a0`) | placement on GD / CC (only CA is anchored), protection order (outer before inner, P), targeting priority (champion attacking an ally first, P from Starro script `0x3400053A`) |
| **Dampener** (= LoL inhibitor: PerceivedType **Inhibitor 2048**) | GD `0x40000C61` / `C60`; CA `0x40000C88`/`C87`, Clash `0x40000C91`/`C95`; **none on CC** (C: no class; CC spectator bar has no dampener count) | 3000 HP (CA), sight 7.5, XP 200 (`0x3B00000E`), team bounty, also shoots (`0x34000014`) | spectator dampener count `0x215C` | what it unlocks (P: its lane's enemy waves get stronger / the core becomes vulnerable); no respawn data (O) |
| **Power core** (map note POWERCORE 30) | GD `0x40000A7E`/`A7B`, CC `0x40000C24`/`C23`, CA `0x40000C8A`/`C89`, Clash `0x40000C96`/`C98` | 4000 HP (GD, CA), 6000 (CC); damage states `0x1000022F` Phase1-4; CC / some CA cores shoot (`0x34000014`, range 9) | end cinematic per team (CA `0x3500003A`/`3B`, GD `0x35000014`/`15`, CC `0x35000012`/`13`) | vulnerability gate (P: after the core turret / dampeners), win on destruction |
| **Foundry** (base turret / shop) | `0x40000170` / `0x4000016F` (ws `0x2E001037`) on every PvP map | shoots enemies in base (stat `0x48000070`) | base access / vendor access notices | placement at the base (G positions in `maps-complete.md` 4) |
| **Base** | `0x4000041F`, `0x40000C7F` (team only) | base aura: shop attribute `0x10000A23`, regen (P) | `UI_UpdateHasBaseAccess` | aura radius (O) |

Structure death: send the destruction (scriptlets / damage states, `reverse-engineering.md`), a ShowAnnouncement
type 2 billboard, the bounty (team-wide gold through `0x1000035E`, floaty `0x100004D6`), and for the core the
match end (section 12).

---------------------------------------------------------------------------------------------------------------

## 6. Minion waves

| Item | In the data / client | Tag |
|---|---|---|
| Classes | GD Soldier `0x4000010A`, Trooper `0x4000010B`, Cannon `0x4000010D`, Elite Trooper / Soldier `0x40000941` / `942`, Destroyer Drone `0x40000E5F`; CC `0x400002D4`/`2D5`, `0x40000C45`-`C48`, Cannon `0x40000441`, Elites `0x40000442`/`443`, Raider Drone `0x40000D23`, Destroyer `0x40000D5C`; GH Trooper `0x4000012D`, Soldier `0x4000012E`, Destroyer `0x40000EAA`; CA several sets (`units-and-ai.md` 1.4) | C |
| Stats | e.g. GD Soldier `0x48000D10`: HP 500 + 10 / level, AD 11.25 + 0.9, armour 5 + 1, attack speed 1.0, **move speed 4.2 m/s**, range stat 18 (m), attack script `0x34000088` (melee) / `0x34000087` (ranged); Cannon AS 0.75, MS 4.18; Destroyer attack `0x340007AF` | C |
| Level | unit level from match time (+1 per 90 s) | C |
| Rewards | kill XP / credit formulas per class (`0x10000224`, `0x10000689`): e.g. `Linear(KilledLevel, Base, Delta) / NumReceivers`, last-hit vs share percentages | C |
| Spawn point | lane mouths `0x2E000AF4`-`AF9` (1 per lane per team; CA 1, CC 2, GD 3) | C positions, P role |
| Lane paths | type-21 waypoint polylines per lane (`maps-complete.md` 3.3-3.6), navmesh 0x90 | C |
| Spawner visuals | spawner world state `0x2E000D03` with `Vfx_Spawner_Tier01/02`, `Vfx_Spawner_Team01/02_Tier01/02` (`0x10000B16`-`B19`), generator scriptlets `_Generator_Self_PreWaveStart` `0x10000205`, `_WaveStart` `0x10000204`, `_OnObjectSpawned` `0x100003AB`, `_OnCleared` `0x10000336` | C keys, P use (fire PreWaveStart a few seconds before, WaveStart on spawn) |
| Wave shape | Tutorial 2 cinematic `0x3500002C`: 2 melee + 2 ranged + 1 siege per side | P |
| Minimap | MapNoteCategory MINION 9 | C |
| Interval, first wave, siege cadence, dampener buffs, tier upgrades | **not in the client** | O -> author |

Authoring proposal (G): first wave at clock 0:45-1:00 (after the intro), every 30 s, 2 melee (Soldier) + 2 ranged
(Trooper) per wave, Cannon every 3rd wave, Elites replace the base pair on a lane whose enemy dampener is down,
Destroyer Drones as a late super-minion tier (`Vfx_Spawner_Tier02`); AI per `units-and-ai.md` 5.3 (retarget 0.5-0.8 s
from `0x3A000026`, vision `0x10000133`). The user's LoL-style prototype (`sistema_suiditos_moba.py`: 30 s waves,
cannon every 3rd, 700 / 1200 aggro / leash, 0.5 s AI tick) fits this skeleton, but its numbers must be replaced by the
data's: HP / damage / speed / range from the stat blocks (metres, not LoL units: speed 4.2 m/s, ranges ~1.5-9 m),
gold / XP from the 0x3B formulas.

---------------------------------------------------------------------------------------------------------------

## 7. Objectives: capture points, beacons, the Doomsday Device

### 7.1 Sector objective tracker (C)

- **Setup** (query `UI_InqSectorObjectives`, answered from the encounter template, P): `0x100007F5` = list of
  MapNoteCategory per slot, `0x100007FA` = HUD position per slot, `0x100007FC` = icon per slot (`0x13...` or a
  property reference). Values: CC `[26, 26, 26, 28]` / `[1, 2, 3, 1]`; GD `[29, 29, 29, 29, 0x10000A9B, 0x10000A9B]` /
  `[1, 2, 3, 4]` (icons `0x1300256D`, `0x1300256A`); GH `0x100007F5` = 8 (capture point; 5 slots in Flash's test).
  Flash builds small pips for CAPTURE_POINT 8 / SMALL_CAPTURABLE 26 / BEACON 29 and large pips for
  LARGE_CAPTURABLE 27 / LARGE_MAPOBJECTIVE 28 (`SectorObjectiveTracker.AttachSectorObjective`).
- **Status**: event **`0x2069`** (handler `0xa5a680` -> `UI_UpdateTrackerStatus` `0x1000037E`) =
  `u64 entity | current team | contention-responsible team | locked-to team (TeamUsageLock 1/2/3) | icon DID | HUD
  position | map-note category | decoration | obscured ...`. A slot is matched by (category, HUD position). The pip
  shows the owner, the team currently capturing ("inductor": shown when the contending team differs from the owner)
  and a lock. The minimap (`MinimappyThing`) listens to the same notice; batch form `UI_BatchUpdateTrackerStatus`
  (Flash asks with `UI_RequestBatchUpdateTrackerStatus`, local; the minimap with `RequestSectorObjectiveState`
  `0x1000041D`).
- **Objective list** (tutorials and anything with objectives): `0x2034` list + categories, `0x2009` one objective,
  `0x2023` category state, `0x2075` tracker on (states: ObjectiveState 1 Failed, 2 Completed, 4 NearCompletion,
  5 Team02Won, 6 Team01Won; category 3/4 team won, 5 completed, 6 failed, 7 remove, 8 show, 9 hide). C.

### 7.2 Per map

| Map | Objects | Data | Rule (to author) | Tag |
|---|---|---|---|---|
| Gotham Heights | 5 capture points `0x4000013B` (ws `0x2E000B22`, has an attack, sight 4.25) at (48.5, 27.5), (111.5, 27.5), (27, 90), (133, 90.2), (80, 127.8) | team health 500 / 500; generator script `0x340002CF` (events `0x1000007A` / `0x10000079` = team 1 / team 2 fired, `ImpactCounter` 1-4 tiers, `Entry_Team0N_Tier0M`, LockTimer, NeutralizedTimer, `DurationImpactTotal` 61 s, announcements via node `0x1000011A`); centre ring of 5 sockets x 2 teams at (80, 74) | P: owning points charges the team's generator; each charge fires an impact that removes enemy team health; capture = stand in radius, contention when both teams; lock / neutralised timers from the script variables | C data, P/G rule |
| Coast City | 3 small capturables (relays `0x4000089D`, `0x40000D25`, `0x40000511` family, ws `0x2E000D12`) + Doomsday Device `0x400001F0` (ws `0x2E0008FD`, sight 10) + firing trigger `0x4000054F` at (80, 82) + Doomsday Guardian `0x40000430` | no scripts on these classes (server logic); decoration `DOOMSDAY_REVENGE_OVERLAY` 2; map note DEVICE 31; PerceivedType DoomsdayDevice; banks `mse_DoomsDayDevice`, `mse_EarthQuake` | P: holding relays charges / unlocks the Device; the Device fires at the enemy core (damage per shot O) | C objects, P rule |
| Gotham Divided | 4 beacons (tracker), control point `0x400003AF` (relay ws), neutral sites `0x2E0003F0` at (55, 55) / (105, 105), Leviathan `0x40000937` | map note BEACON 29, decoration `BeaconAlert` 9 | O: beacon rule (P: capturable vision / buff points) | C slots, O rule |
| Crime Alley / Clash | tracker on CA (no template list read), Clash none | | core only (+ team health on Clash) | P |

---------------------------------------------------------------------------------------------------------------

## 8. Jungle, neutral camps, pickups, pads

| Item | Data | Tag |
|---|---|---|
| Camp units | GD 13 classes (`0x40000935`-`0x40000940`), CC 12 (`0x40000893`-`89A`, `0x400007C1`, `D60`, `D62`), CA 9; flag `0x1000055A` = 1 on camp units (P: leash / return home); team `0x1000046E` (neutral) | C |
| Bosses | Leviathan `0x40000937` (GD; attack `0x3400057B`, range 15, credits 4 x killer level per receiver, **kill buff** `0x10000AC2` = `0x48000E4C`; scriptlets `Leviathan_Spawn` / `Leviathan_Respawn` `0x10000E57` / `E56`); Doomsday Guardian `0x40000430` (CC; ability loop `0x3400057A`, kill buff `0x48000273`); Raiders (`0x40000938`, `0x400007C1`, `0x40000D60`) | C |
| Drops | heavy creatures run `0x3400007D` on death: spawn pickup `0x400005E1` (map note / pickup kind `0x100006F1` = 6, perceived `0x80000`) with the killer's team; CA Raiders `0x34000670` -> `0x40000C49` | C |
| Pickups shown on the minimap | MapNoteCategory METEOR_PICKUP 4, HEALTH_PICKUP 5, STORMSHIELD_PICKUP 12, SPEED_PICKUP 13, GENERIC_PICKUP 15 | C |
| Health / haste packs, pads | GD `0x40000A86` / `A87` (health / haste), drop pods (regen / haste pads, ws `0x2E000E38`) `0x400008CF`.., superpads `0x40000CB4`.., phase pod `0x40000A79`, surveillance tower `0x400007FD`, pulse emitter `0x40000951`; GH regen `0x3400012B`, speed `0x34000138`, stealth brush `0x340001CF` | C classes, server-side effects mostly O |
| Camp positions | CC 5 camps with patrol loops; CA 1 camp (80, 95.5); GD none anchored | C/P (`maps-complete.md` 3.3-3.6) |
| Respawn times, boss first spawn | none | O -> author (proposal G: small camps 60-90 s, bosses first at 5-8 min, 5 min respawn) |

---------------------------------------------------------------------------------------------------------------

## 9. Map events and the event timeline

### 9.1 Timeline messages (C)

Flash `EventTimerV2` asks `UI_ReadyForTimelineData` (`0x100002AD`) on load. Then (C++ listener vtable `0x1605930`):

| Notice | Handler | Flash | Fields (Flash order) |
|---|---|---|---|
| `0x100002AF` / `0x100002B1` (u64) | `0xa68000` / `0xa5a240` -> `0xa5a0f0` | `UI_MissionEvent_StartTimeline(ttCurrentTime)` | starts the timeline at the current game time |
| `0x10000424` (banner desc + f64) | `0xa488d0` | `AddTimelineBanner(iidHandle, handleId, severity, message, ttCountdown, ttCurrentTime)` | the centre announcement; `ttCountdown < 0` = no countdown; severity 1 High / 2 Medium / 3 Low picks colour and sound |
| `0x100002AB` (desc + list + f64) | `0xa786f0` | `AddTimelineEvent(iidHandle, handleId, severity, timelineIcon, examinationIcon, tintIcon, owningTeam, title, description, ttEventTime, ttCurrentTime)` | an icon on the timeline at `ttEventTime` (future events = upcoming map events) |
| `0x100002AE` (list + list + f64) | `0xa72340` -> `0xa480e0` | `BatchAddTimelineEvent(arrays ...)` | |
| `0x100002AC` (Handle) | `0xa48a50` | `RemoveTimelineBanner` / `RemoveTimelineEvent` | by handle {u32, u64} |

Wire detail of the descriptor: `{Handle{u32 id, u64 iid} u32 severity u32 icon u32 icon2 u8 tint u32 team u64 time u8
{u32 n {StringInfo title StringInfo description u32}}}` (`protocol-complete.md` 3). Scripts drive them through nodes
`0x10000039` SendMissionEvent / `0x10000049` OnMissionEvent / `0x100000B2` StopMissionEvent and
`0x1000011A` ShowAnnouncement / `0x10000119` StopAnnouncement (GH generator). The Flash test functions use meteor
strikes as the example event (no data). C.

### 9.2 Map events (data)

| Event | Evidence | Tag |
|---|---|---|
| **Meteor strikes / Meteor Storm** | banks `mse_Meteor` / `mse_MeteorStorm` (referenced from GD `0xA0000168` / `0xA000016E`, CC `0xA0000161`, T1); event pack `0xA0000164` (Meteor Fragment `0x400006F1`, unreferenced: the server must list it in `0x20AF`); map-note decorations `Meteor_Impact_Zone` 1 / `Meteor_Devastation_Zone` 3; pickup category METEOR_PICKUP 4; UI sounds `AS_UI_VO_MSE_METEOR_ALERTVIDEO1-3`; Tutorial 2 cinematic `0x3500002B` meteors at frames 750 / 1060 | C assets, P: a timed map event (timeline icon -> banner countdown -> impact zones on the minimap -> fragments to pick up) |
| **Doomsday Device** (CC) | classes above, bank `mse_DoomsDayDevice` + `mse_EarthQuake`, `DOOMSDAY_REVENGE_OVERLAY` | C assets, P rule |
| **Generator impacts** (GH) | script `0x340002CF` (4 tiers, 61 s total impact phase) | C script |
| Map note pings | `0x2006` add / `0x200E` remove / `0x2137` remove map note; player ping `0x2136` (C->S); categories PING / ALERT / RETREAT (+ in-game variants) | C |
| Event schedule (times, which event when) | **not in the client** | O -> author |

---------------------------------------------------------------------------------------------------------------

## 10. Announcements, billboards, announcer, music

- **`0x100002EB` ShowAnnouncement** `(StringInfo text, u32 type, u32 source icon, u32 target icon, i32 source team,
  i32 target team, u8 use target colour)`; types: 2 GenericText (kill / structure messages with two icons and team
  colour), 6 Location (GH / CC location billboards; CA / Clash / GD use the GH style), 7 Tie, 8 Loss, 9 Win, 10 Team2
  Victory, 11 Team1 Victory (8 s). After the match is over only the result types are shown (Flash
  `BillboardManager`). `0x100002EC` clears, `0x100002BC` stops new billboards. C.
- `UI_PlayerJoined` / `UI_PlayerLeft` (`0x100000CB` / `0x100000CE`): join / leave billboards. C.
- **Announcer**: template `0x10000802` -> set of `0x1000080C` entries (`0x10000806` match-event enum -> line ids);
  played through the dialog element `0x2039`; texts `0x2B000093`; banks `Announcer_<Map>` (`cinematics-vfx-audio.md`
  4.3). Which match event id = first blood / turret lost / etc. is not named in the client (O).
- **Music** follows state only (life states, teams, match start / end; `cinematics-vfx-audio.md` 4.4). C.

---------------------------------------------------------------------------------------------------------------

## 11. Gold, XP, bounty hooks

Champion properties (C, `progression-meta.md` 1.1): `Level 0x10000167`, `XP 0x10000142`, `SkillPoints 0x100001AF`,
gold `Upgrade_Currency 0x1000035E` (f32), items `0x10000CD6`. Floaties: currency `0x100004D6` (u64 entity, f32),
XP `XPGained 0x100004F9` (local, from the property). Rewards from the 0x3B formulas (C): champion kill XP
`0x3B000003`, bounty `0x3B0000B7`, structure XP `0x3B000016`, unit XP / credits per class, team bounty `0x10000362`,
script grants `0x10000065` GrantCurrency (+ `UseTeamwideCurrencyGains` `0x100000EC`). **Not in the client** (O):
passive gold per second, starting gold, XP curve (only `InqXPForLevel` from the server's WLib), level cap (P 20).

---------------------------------------------------------------------------------------------------------------

## 12. Surrender and match end

### 12.1 Surrender (C)

1. A player opens the start menu and presses Surrender -> client sends **`0x10000454` SurrenderResponse(u8 1)**
   (`0x886de0`). The same message carries each vote (yes = 1, no = 0) from the surrender panel.
2. Server starts a vote and sends **`0x10000455`** to every member of that team: `u32 n | n x u8 vote | u32
   expected votes | u8 can vote | f32 time remaining | f32 total time`. The panel shows one pip per team member
   (`MatchData.GetNumberOfPlayersOnMyTeam`), pips at index >= expected votes show "disconnected", the first `n` pips
   show yes / no in order; Yes / No buttons only if `can vote`; a bar counts `time remaining` of `total time`.
   Re-send on every vote.
3. **`0x10000456`** (empty) ends the vote: buttons disabled, panel closes after 2 s.
4. If it passed: match end with the other team as winner (12.2).
To author (O): threshold (P: unanimous in 5v5 below some time, else 4 of 5), vote length, cooldown, earliest time
(G: `0x1000021C` = 600 s).

### 12.2 Match end (C, `client-cinematics-matchend.md`)

Order: the end cinematic of the losing core (`0x3500003A`/`3B` CA, `0x35000014`/`15` GD, `0x35000012`/`13` CC) ->
`0x100002EB` type 9 / 8 (or 11 / 10) -> **`0x1000000E` NotifyMatchEnded** `(u32 winning team, u32 player team, f32
duration s, u32 tier, f32 target time)` (C++ `0xa809e0` -> `0xa795e0` end-of-match flow; Flash hides the HUD) ->
`0x2038` + objectives cleared / tracker off -> scorecard `0x2045` and the reward chain (`progression-meta.md` 4).

---------------------------------------------------------------------------------------------------------------

## 13. Enumerations (Flash `emp_gen`, C)

- LifeState: 1 DeadAndFaded, 2 Dead, 3 Incapacitated, 4 Alive, 5 Respawning.
- MapNoteCategory: 1 PING, 2 CHARACTER, 3 TURRET, 4 METEOR_PICKUP, 5 HEALTH_PICKUP, 6 BASE, 7 AGENT, 8 CAPTURE_POINT,
  9 MINION, 11 BLANK, 12 STORMSHIELD_PICKUP, 13 SPEED_PICKUP, 14 SKILL_BAT_SCREAM, 15 GENERIC_PICKUP, 16 CAMERA,
  17 ALERT_PING, 18 ALERT_PING_INGAME, 19 PING_INGAME, 21 RETREAT_PING_INGAME, 22 RETREAT_PING, 23 STATIC,
  26 SMALL_CAPTURABLE, 27 LARGE_CAPTURABLE, 28 LARGE_MAPOBJECTIVE, 29 BEACON, 30 POWERCORE, 31 DEVICE.
- MapNoteDecoration: 1 Meteor_Impact_Zone, 2 DOOMSDAY_REVENGE_OVERLAY, 3 Meteor_Devastation_Zone, 5 RetreatPingTarget,
  6 AlertPingTarget, 7 Locked, 8 Disabled, 9 BeaconAlert, 10 Highlight, 11 WonderWoman_Reclaimer.
- PerceivedType bits: Boss 1, SmallEnv 2, Loot 4, Character 8, Turret 16, Missile 32, CharacterInteractive 64,
  LargeEnv 128, Creature 256, Objective 512, Siege 1024, **Inhibitor 2048**, Destructible 4096, Deco 8192, Base 16384,
  AutomatedPlayer 32768, Minion 65536, Device 131072, DoomsdayDevice 262144, CapturePoint 524288, Pet 1048576,
  Player 2097152, Lieutenant 4194304; masks Structures 542736, DefaultBasicAttackTarget 5593433, DefaultCombatTarget
  4522249, HasMapNote 589848, PersistAfterDeath 2064.
- ObjectiveState 1 Failed, 2 Completed, 4 NearCompletion, 5 Team02Won, 6 Team01Won; ObjectiveCategoryState 3
  Team02Won, 4 Team01Won, 5 Completed, 6 Failed, 7 Remove, 8 Show, 9 Hide.
- MissionEventNotificationSeverity 1 High, 2 Medium, 3 Low. TeamUsageLock 1 Team1, 2 Team2, 3 AllTeams.
- BillboardUpdateType 2, 6, 7, 8, 9, 10, 11 (section 10). Relationship 1 Neutral, 2 Enemy, 4 Friend.
- EncounterIdentifierType 1-12 (section 0 #9). EncounterLobbyRules 1 BlindPick, 2 Draft, 3 AllRandom.

---------------------------------------------------------------------------------------------------------------

## 14. Server -> client messages of a match (one table)

"ics" = what `protocol-complete.md` records as already sent.

| Purpose | Id | Layout | Target | ics |
|---|---|---|---|---|
| Match clock | notice `0x10000109` | f64 start, f64 end, u8 preStart | player | no |
| Roster / scoreboard / portraits | notice `0x1000005B` | list of 0x60 rows (section 4) | player | no |
| Life state | property `0x100000FA` | enum | champion | yes |
| Own death / respawn timer | notice `0x10000090` | u32 state, f64 next | player | yes |
| Others' respawn timers | notice `0x100000BC` / pause `0x100000BA` | u64, u32 type, u32 state, f64 / u64, u32 | player | sent / no |
| Kill feed | event `0x217A` | u64, u32, u32, u64, u32, list<u32> | each player | no |
| Kill card | notice `0x1000021C` (`0x100002B2` spectator) | big list layout (section 3.1) | victim | no |
| Billboards | notice `0x100002EB` / `0x100002EC` / `0x100002BC` | section 10 | player | built |
| Join / leave | notice `0x100000CB` / `0x100000CE` | u64, u64, StringInfo, u32 icon, u32 team | player | no |
| Team health | notices `0x100004FB`, `0x10000134` | lists | player | no |
| Sector tracker | event `0x2069` | u64 + 11 u32 | player | no |
| Objectives | events `0x2034`, `0x2009`, `0x2023`, `0x2075` | flag-driven records | player | tutorial |
| Timeline | notices `0x100002AF`, `0x100002B1`, `0x10000424`, `0x100002AB`, `0x100002AE`, `0x100002AC` | section 9.1 | player | built (T1) |
| Map notes | events `0x2006`, `0x200E`, `0x2137`, `0x20DA` | | player | no |
| Spectator dampener count | event `0x215C` | list<u32> per team | spectator | no |
| Surrender | notices `0x10000455`, `0x10000456` | section 12.1 | team | no |
| Match end | notice `0x1000000E` + `0x2038`, `0x2045` ... | section 12.2 | player | yes |
| Gold / XP | properties `0x1000035E`, `0x10000142`, `0x10000167`, `0x100001AF`; floaty `0x100004D6` | | champion | yes |
| Recommended buy | event `0x2078` | list<u32> | champion | yes |

Client -> server: `0x100000D2` HUD ready, `0x100002AD` timeline ready, `0x10000137` team health request,
`0x10000454` surrender, `0x2136` ping, `0x2138` objective forward (`protocol-complete.md` 2).

---------------------------------------------------------------------------------------------------------------

## 15. What the server must author (with the best evidence)

| Rule | Best evidence | Tag |
|---|---|---|
| Structure placement on GD / CC | Crime Alley anchors + 31.3 % / 74.2 % lane rule (`maps-complete.md` 4) | G |
| Structure order / vulnerability, dampener effect | PerceivedType Inhibitor, dampener counts in the spectator bar, CC has no dampeners | P |
| Wave timing / composition | Tutorial 2 wave (2/2/1), generator scriptlets with tiers, classes per map | G |
| Jungle positions (GD), respawns, boss timers | CC camp markers + loops; Leviathan respawn scriptlet exists | G |
| Respawn duration per level | none | O |
| Capture rules (GH points, CC relays / Device, GD beacons) | tracker layout from the template, GH generator script variables, team health 500 | P |
| Map event schedule (meteors, Device) | assets, timeline protocol, decorations | G |
| Passive gold, start gold, XP curve, level cap | none (formulas only for rewards) | O |
| Surrender thresholds | panel layout only | O |
| Bot difficulty | two encounters with the same data (`units-and-ai.md` 6) | O |

---------------------------------------------------------------------------------------------------------------

## 16. Open questions

- The first u64 of the `0x1000005B` row (account IID? never read by the scorecard builder).
- How the client answers `UI_InqSectorObjectives` (template `0x100007F5` read site not located; the link is by value).
- What `0x100000CA` / `0x100000CD` (u64, u64) and `0x10000205` (empty, slot `+0x68` -> `0xa8ea40`, not decompiled as
  a function) do.
- GH: how points translate into team-health loss (rate per point vs generator impacts).
- GD beacons and the Leviathan buff; CC relay -> Device charge rule; the Crime Alley tracker slots (template
  `0x40000C82` not dumped).
- Which announcer match-event ids (`0x10000806` values) mean which event.
- `0x10000464`, `0x1000021C`, `0x100004A1` meanings (G above).
