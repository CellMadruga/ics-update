# Gotham Divided v AI: what the original map has that our server does not create or send

Encounters 0x40000B6B (v AI beginner), 0x40000399 (PvP), 0x40000E62 (5vAI intermediate); map pack 0xA0C11AD2,
layout 0xA0000168, env/region 0xA00000FC, variants 0xA000016E; landblock 0x1BD3; 3 lanes; team 2 = (y, x) of team 1.
Confidence: C = read in the data / logs, P = probable, G = guessed. Written incrementally (2026-10-25).

## 1. What our server did in the 08:59:15 match (logs/server.log, logs/traffic.log)

Queue 08:59:15 (9 bots, 5 per team), champion select, `enter match (0x20AF)` with packs 0xA0000168 0xA00000FC
0xA000016E ..., load complete 08:59:54, intro cinematic 0x35000024 (0x20F5) 08:59:59 -> state 4 at 09:00:06, clock set
42 s before the start, `match: started` 09:00:48, player killed by the mid t2 turret 09:00:54, client left 09:01:06.

Objects spawned (traffic.log `spawn ...`), each with vitals 0x42, unit flags / PerceivedType 0x1000019D, 0x10000029 /
0x10000249 = 1, vision:
| Object | Class t1 / t2 | Extra parts / scriptlets sent |
|---|---|---|
| core | 0x40000A7E / 0x40000A7B (4000 hp) | none (no team-state scriptlet, no pedestal) |
| core_turret | 0x400003BA / 0x400003C1 (3000) | none (no head, as decided in fase3-hm for CA) |
| dampener north/mid/south | 0x40000C61 / 0x40000C60 (2700) | Object_Activate, Vfx_Active |
| turret north | 0x400003BB / 0x400003C0 (2700) | head 0x2E000AA8 (Vfx_Startup, Vfx_Active_Blue/Red), plate 0x2E000A9F |
| turret mid | 0x400003BF / 0x400003BE (2550) | head + plate as above; t2 fired (Target_Acquired 0x1000002C, 0x1000014A, 0x1000029D, 0x100002E0) |
| turret south | 0x400003BC / 0x400003BD (2550) | head + plate |
| foundry | 0x40000170 / 0x4000016F (300) | none |
| beacon 1 / 2 | 0x400003AF at (55, 55) / (105, 105) | tracker 0x2069 owner 0 |
| champion + player | Nightmare Batman 0x40000D1C | the only champion in the world |

Messages besides spawns: 0x2031 loading (bots 100), timeline start 0x100002AF / 0x100002B1, match clock 0x10000109,
scoreboard 0x1000005B (10 rows), dialog notice 0x10000205, encounter on player 0x100001D3, announcer lines (0x2001)
0xBB (-30 s), 0x97 (-10 s), 0xAE (0), 0xAD (+2), 0xE7 (= 231, wave -30 s); 0x2039 event 18 (first blood) on the
death; kill feed 0x217A; credits ticks; inventory 0x20E2; recommended 0x2078.

NOT created / sent in that match (code: ics/match/maps.py `_gotham_divided`, match.py):
- **no bot champions in the world**: the 9 lobby bots are scoreboard rows only (lobby `as_player()` has no agent; no bot
  AI exists in ics/). On a "v AI" map this is the largest gap.
- no base gates, no base auras, no stealth tiles (the GD spec has no `gates` / `auras` / `stealth` keys);
- no minion waves yet (first wave at +45 s; the client left at +18 s) and no jungle camps (first at +60 s); the GD
  camps are G positions;
- no music / ambience / announcer pack events specific to GD; no lighting other than key 0x1000001C;
- no team-coloured core state, no core turret head.

## 2. Map statics (record 0x82011BD3 of 0xA0C11AD2, 568 entries, parsed in full; C)

Entry format correction to maps-complete.md 2.2: `flags | type | [index | IID if flags & 0x04] | [ws if flags & 0x08] |
xyz | quaternion | [0 | n | props if flags & 0x80]` (the type-21 waypoints have flags 0x1A: no index / IID).

| Type / ws | n | Where | Reading |
|---|---|---|---|
| 16 (start) | 12 | (7.5, 152.5) + 5, (152.5, 7.5) + 5 | used (ics maps.py) |
| 21 waypoints `0x2E000000` | 124 | lanes, core rings, markers | used for lanes |
| 3 `0x2E000AF4`-`AF9` | 6 | lane mouths, team in `0x100002E6.0x1000009C` | used as wave mouths |
| 3 `0x2E000626` / `6B3` / `6B4` | 17 + 17 + 17 | spread over the jungle (e.g. 626 at (74.3, 77.9), (50.3, 59.8), (40.2, 94.2) ...), z 249.97, random yaw, flags 0x1E | ws in no installed pack: client cannot draw them; the same triple is on every 5v5 map (x17), so a generic thing (G: ambient sound emitters or AI cover / jungle-wander points). Server need: none known |
| 7 `0x2E000A3B` | 2 | core pedestals (17.5, 142.5) yaw 45 side 1, (142.5, 17.5) yaw -135 side 2 | client static |
| 7 `0x2E000CA5` + `0x2E001352` | 2 + 2 | on the start centres (7.5, 152.5) / (152.7, 7.3) and (6.9, 153.2) / (153.2, 6.8) | client statics (spawn platform; `0x2E001352` names 0x400002A4 / 0x40000078 and a second ws 0x2E001355) |
| 7 `0x2E000EE1` | 4 | (39.0, 149.5) yaw -90, (35.5, 124.5) yaw -135, (10.5, 121.0) yaw 180 (team 1's three base exits: the base's walkable fan ends 31-40 m from the start), (121.0, 10.5) yaw 90 (team 2 south exit only) | client static frame (mesh 0x170015FA); best anchor for the base gates (P) |
| 7 `0x2E0003F0` + `0x2E000FBE` (scale 0.6) + `0x2E00133D` / `133E` (ctype 9) | 1 each per site | (55, 55) and (105, 105) | the two neutral sites (used as beacons today) |
| 7 at the map centre (80, 80) | 12 | `0x2E000D60`/`D61`/`D64` (z 247), `0x2E000B42`, `F57`, `11EE`, `11F0`, `1336`, `1338`-`133B`, `0x2E000FA7` (79, 81, z 246) | a sunken centre set-piece under the mid lane (client statics) |
| 7 `0x2E001396` (scale 0x6B4 2-7) | 12 | team-2 half only (62-146, 32-124) | client static (smoke / fire decals, G) |
| 10 lights `0x2E000011` | 6 | | client |
No static places a gameplay unit, camp, stealth tile, pad or gate (C), as on the other maps: all of them were
server-placed.

## 3. Announcer: GD's own set 0x40000554 (template 0x49000554, layout pack 0xA0000168; C)

`0x10000802` = 0x40000554 (not Crime Alley's 0x40000D4C that ics/match/announcer.py LINES was built from);
`0x10000803` = 0x4000047A only on the PvP template (the v AI template 0x40000B6B has none: the shared set events 8,
18-30, 52 may then be silent on v AI, P). Event -> columns `0x10000829` (bad news for the listener's team) /
`0x1000082A` (good news) / `0x10000895` / `0x10000894` (spectator forms naming the team), captions in tables
0x2B0000A2 / 0x2B0000A9 (meaning paraphrased here, no game text):
| Event | 829 / 82A | Meaning | ics today |
|---|---|---|---|
| 31 / 35 / 34 | 303 / -, 291 / -, 305 / - | top / middle / bottom turret under attack | never sent ("turret under attack" not voiced) |
| 36 / 37 / 33 | 315 / 312, 302 / 304, 307 / 309 | top / middle / bottom turret destroyed | `turret_north`/`turret_south` have no id in [ics] announcer_events; mid uses 33 (= **bottom** per data; config names 31/32/33 bot/top/mid by ear conflict with the data) |
| 32 | 292 / - | power core under attack | not sent |
| 56 / 55 | 433 / -, 428 / 431 | core turret under attack / destroyed | config `core_turret` = 40 (wrong on GD: 40 is a dampener line) |
| 47 / 41 / 39 | 379, 382, 378 | top / middle / bottom dampener under attack | not sent |
| 38 / 40 / 48 | 367 / 366, 384 / 380, 361 / 371 | top / middle / bottom dampener **deactivated** | config `dampener` = 34 (a turret line on GD) |
| 64 | 721 / 719 | a dampener reactivates in 30 s | config 52 (shared-set event) |
| 63 | 725 / 718 | dampener reactivated | config 50 (CA-only event, absent here) |
| 60 | 666 / 667 | Leviathan defeated (enemy / us) | no Leviathan |
| 61 | - / 697 (+700 / 702) | Raider defeated | config `raider_defeated` 49 (CA event) |
GD's set has no core 75/50/25 % events (10/15/17 are Crime Alley's). Lane naming (P): top = north lane (via (124, 124)),
bottom = south lane (via (36, 36)), from team 1 at the top-left and the minimap rotation -45 deg (0x10000077 of
0x48000690 / 0x4800068F).
Recipe (C ids, P lane mapping): per-map `announcer_events` (keyed by encounter set) {turret_attack_{top,mid,bot}: 31/35/34,
turret_{top,mid,bot}: 36/37/33, core_attack: 32, core_turret_attack: 56, core_turret: 55, dampener_attack_{...}:
47/41/39, dampener_{top,mid,bot}: 38/40/48, dampener_reactivating: 64, dampener_reactivated: 63, leviathan: 60,
raider: 61}, sent by 0x2039 on channel 2 (or 0x2001 with the 829 / 82A key); "under attack" throttled (G: once per
10 s per structure, the 0x34000838 ping's moment).
Countdown keys 0x9C / 0xBB / 0x97 / 0xAE / 0xAD are in GD's pack too (shared table of 0x4000047A, C). The wave
lines 231 / 247 / 233 were not found with the same line-entry pattern in 0xA0000168 / 0xA00000FC / 0xA000016E (nor in
0xA00002E6, so the pattern may simply not cover them): unverified whether 0xE7 plays on GD (O).

## 4. Classes the GD packs hold (template scan of 0xA0000168 / 0xA000016E; C) and what ics uses

- Minions 0x4000010A / 10B / 10D / 0x40000941 / 942 / 0x40000E5F: **one class for both teams** (no team variant,
  no 0x1000009C in the template): ics is right to reuse them; team colour comes from the team property (C).
- Jungle (team 0x10000C6E = neutral ref; camp kind 0x10000C56): small Tripod 0x40000935 / 0x4000093B, Scrapper
  0x40000936, Mauler 0x4000093A; heavy (kind 4, drop pickup 0x400005E1 via 0x3400007D) Heavy Tripod 0x40000939,
  Heavy Scrapper 0x4000093C, Heavy Mauler 0x4000093E; buff destroyers (kind 7) Haste 0x4000093D (0x3400051B),
  Regen 0x40000940 (0x3400051A), Surveillance 0x4000093F; big (kind 6) **Raider 0x40000938** (ws 0x2E000F1B, HP
  2200+240) and **Leviathan 0x40000937** (ws 0x2E000FA5, table 0x1D0006E6 with `Leviathan_Spawn` 0x10000E57 /
  `Leviathan_Respawn` 0x10000E56, base 0x1D0006EA ground-pound VFX; HP 5000+215, AD 220, range 15, kill buff
  0x48000E4C). ics: 4 camps of 939+93B and 93E+93A only.
- **Phase Pod 0x40000A79** (ws 0x2E000FC7, table 0x1D0006AC: Vfx_Spawn, Vfx_SpawnIdle, Object_Activate /
  Deactivate, Vfx_Spawn_Hit, Vfx_Fade_Out, Vfx_Event1 / 10; graph 0x1A000E0B with pod entrance, `raider_open`,
  `leviathan_begin` / `leviathan_thump` / `leviathan_inactive_idle`, destruction). Public descriptions of the map
  (PC Gamer preview, DC "MOBA 101") say two pods crash into the jungle mid-match: the first opened releases a
  Raider, once the Raider is down the second releases the Leviathan. So the pods are the map event, and the
  two neutral sites (55, 55) / (105, 105) (sunk `0x2E0003F0` + `0x2E000FBE` + ctype-9 `0x2E00133D` / `133E`) are their
  landing pits (P). ics spawns the CC relay-like control point 0x400003AF there as "beacons" (G, probably wrong).
- Tracker (template 0x100007F5 = 29 x 4, 0x100007FA = 1-4, icons 0x100007FC = 0x1300256D / 0x1300256A; map-note
  category 29 = BEACON, decoration `BeaconAlert`): best reading (P) = pod / boss alerts, not capture points.
- Deployables / pickups (flags 0x20040, kind 3): drop pods (regen 0x400008CF, haste 0x400008D7, 0x400008D0 / D6,
  ws 0x2E000E38), superpads 0x40000CB4 / CB5 / CB8-CBB / CBE, surveillance drone 0x40000A83, surveillance tower
  0x400007FD (ws 0x2E000FE5), pulse emitter 0x40000951 (0x2E000FAB) / 0x400009B6, packs 0x40000A86 / A87, colliders
  0x40000C7A / C7B / CDC-CE1: the "deployable powers" camps give (public text: meteor strike, EMP, agility). None used.
- Base pieces in 0xA0000168 (sent in 0x20AF): Door **0x40000557** (ws 0x2E000CD7, flags 0x2000), Base aura
  **0x40000C7F** (ws 0x2E000A35), spawner 0x400005C8 (ws 0x2E000D03, `Vfx_Spawner_Team0N_Tier0M`), stealth
  hotspot **0x4000039D** (ws 0x2E000D36) is in GD's own zone pack 0xA00000FC. ics creates none of them on GD.
- Turrets: lane class ws 0x2E000AA0, core turret ws 0x2E000AC4, dampener ws 0x2E000E04, cores no ws of their own
  (0x2E000AC5 in cinematics); sides 0x100007A2 = 3 / 5 on every team-1 / team-2 structure template (C).

## 5. Gaps ranked (recipe; confidence)

1. **Bot champions absent** (C, logs + code): v AI with 9 bots in the scoreboard only. Spawn each lobby bot as a
   champion agent at its type-16 slot with a lane AI (push with the wave, retreat under 30 % HP, use skill 1-4 on the
   nearest enemy champion in range); template 0x10000B41 = bot level script 0x340007E2.
2. **Pods, Raider, Leviathan** (P): at ~ (G) 8-10 min, phase pods 0x40000A79 at (55, 55) and (105, 105) (z 250, start
   Vfx_Spawn then Vfx_SpawnIdle; tracker 0x2069 slot 1 / 2 as BEACON 29); first pod hit by a champion -> Object_Activate,
   Raider 0x40000938 at the pod; Raider dead -> event 61 (0x2039 ch 2), the other pod opens -> Leviathan 0x40000937
   with `Leviathan_Spawn`; dead -> event 60, kill status 0x48000E4C on the killer's team, `Leviathan_Respawn` later (G
   timer 6 min). Replaces the two 0x400003AF "beacons".
3. **Announcer set of GD** (C ids): section 3 table; today turret / dampener / core-turret voices use Crime Alley ids
   that mean other lines here, and no "under attack" voice exists.
4. **Dampener rule** (C lines, P rule): dampeners are *deactivated*, not destroyed, and come back (line 64 at -30 s,
   63 at reactivation): keep the body (LifeState / Object_Deactivate then Object_Activate), do not remove it.
5. **Base gates and auras** (C classes, P positions): Door 0x40000557 / 0x2E000CD7 with side 0x100007A2 3 / 5 at
   team 1's three exits, at the `0x2E000EE1` frames: (39.0, 149.5) yaw -90, (35.5,
   124.5) yaw -135, (10.5, 121.0) yaw 180; team 2 = (y, x) with yaw mirrored (the mid exit is 30+ m wide at r 38: one
   door may not cover it, G); Base 0x40000C7F / 0x2E000A35 at (7.5, 152.5) / (152.5, 7.5), radius 6 (0x100002AA; the
   GD base fan is ~35 m, so P a larger radius).
6. **Jungle composition** (C classes, G positions): one camp per class family, e.g. per half: Heavy Tripod+2 Tripod,
   Heavy Scrapper 0x4000093C + 2 Scrapper 0x40000936, Heavy Mauler + 2 Mauler, and the three buff destroyers alone
   (Haste 0x4000093D, Regen 0x40000940, Surveillance 0x4000093F) with their kill statuses; positions G in the four
   jungle quarters (the 626/6B3/6B4 markers are evenly spaced 7-19 m and not mirrored: not camp anchors).
7. **Deployable pickups** (C classes, O rule): heavy creatures drop 0x400005E1 (team of the killer); pads 0x400008CF /
   8D7 / superpads as the deployable rewards.
8. **Stealth hotspots** (C class in the GD zone pack, G positions): 0x4000039D / 0x2E000D36 tiles at lane-side bushes;
   no anchor in the statics.
9. Minor: core-health voices 10/15/17 do not exist on GD (harmless); music is client-driven from 0x10000ADC =
   0x48000E6B (C) and needs only team / LifeState; lighting key 0x1000001C already sent; intro 0x35000024 and end
   0x35000014 / 15 already wired; 0x1000021C = 600 s and PvP-only 0x100004A1 = 60 s (O meaning).

Sources (public, for the pod / Raider / Leviathan rule only): https://www.pcgamer.com/uk/infinite-crisis-preview-turbine-adds-a-tri-lane-map ,
https://www.dc.com/blog/2014/03/20/moba-101-making-the-most-of-maps
