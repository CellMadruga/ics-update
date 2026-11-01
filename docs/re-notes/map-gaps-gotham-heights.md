# Gotham Heights (domination) - gap analysis

Encounters `0x4000013E` (PvP) and `0x40000B6C` (v AI); map pack `0xA0C11AF2`, packs `0xA000009A` (zone),
`0xA000016B` (layout), `0xA0000179` (variants); LB `0x1BF3`, z 250.1, team 2 = 160 - x.
Confidence: C = read in data / logs, P = probable, G = guessed. Written incrementally (2026-10-25).

## 1. What our server did on 2026-10-25 08:56 (encounter 0x40000b6c, logs/server.log + traffic.log)

Timeline: lobby 08:56:07, enter match (0x20AF) 08:56:34, mode layer 08:56:39, load complete 08:56:46, intro
`0x35000023` over 08:56:59 ("42 s to the start"), the tester left at 08:57:14 **before the match start** (08:57:41), so
no wave, no capture tick and no domination drain ran. C.

Objects spawned (C):
- `foundry t1` `0x40000170` at (18.4, 50.1), `foundry t2` `0x4000016F` at (142.7, 50.3); vitals 300/300; flags
  0x1000019D = 0x4000, 0x10000029 = 1, 0x10000249 = 1; vision 13.5 on t1.
- `capture 1..5` `0x4000013B` at the 5 markers; 0x1000019D = 0x80200; tracker 0x2069 owner 0 for each.
- champion + player (Atomic Green Lantern 0x4000080c), missile 0x40000485.
- **No bot champion objects** in the window (9 bots listed in champion select only), no minions, no gate, no base
  aura, no stealth tiles, no camps, no team-site statics, no generator / centre ring object.

Messages sent (C): 0x20AF pack list (zone/layout/variants + common packs), 0x2016, 0x206D, 0x2031 loading %, 0x20F8
cooldowns, match clock 0x10000109 (pre-start), **team health 0x100004FB** (and 0x10000134 later), timeline start
0x100002AF / 0x100002B1, scoreboard 0x1000005B (10 rows), HUD elements 0x213D (2, 4-25, 27-33, 35-38, 41, 44, 45),
0x2078, 0x20E2, dialog notice 0x10000205, cinematic 0x20F5 `0x35000023`, credits ticks, announcer line **0xBB**
(0x2001) once, 0x2021 exit lobby.

The match never reached its start, but the code path (ics/match/match.py, objectives.py, maps.py `_gotham_heights`)
shows what would follow: waves on two "lanes" (the waypoint rings) with Soldier 0x4000012E / Trooper 0x4000012D /
Destroyer 0x40000EAA, capture by presence (radius = vision 4.25, 10 s), owner 0x10000456 + scriptlets BeingCaptured /
Captured / Lost, a continuous drain of the losing team's health (`[ics] match_domination.drain_per_point` 1/s per
point of difference). No bots are created as world objects on any map (traffic.log: no "spawn ... Bot"), a general gap.

## 2. Findings in the data (2026-10-25)

### 2.1 The mode is "Orbital Cannon vs Power Core" (C lines, P rule)

GH's announcer set `0x4900047E` (layout pack 0xA000016B, `0x1000080A`, 9 entries; columns 0x10000895 / 0x10000829
(team that suffers) / 0x1000082A (team that acts) / 0x10000894), captions read from table 0x2B000095 (C):

| Event | 0x895 | 0x829 | 0x82A | 0x894 | Meaning (short) |
|---|---|---|---|---|---|
| 13 | 407 | 225 | 211 | 405 | point "Wayne Tower" captured |
| 11 | 417 | 224 | 207 | 415 | point "the Bridge" captured |
| 16 | 411 | 222 | 212 | 416 | point "the Subway" captured |
| 14 | 403 | 223 | 210 | 413 | point "the Townhouses" captured |
| 12 | 414 | 209 | 217 | 408 | point "the Gas Station" captured |
| 54 | 402 | 412 | 409 | 404 | Orbital Cannon fired (we / the enemy / {name}) |
| 15 | 221 | 220 | 206 | 208 | Power Core at 75 % |
| 17 | 227 | 226 | 213 | 214 | Power Core at 50 % |
| 10 | 219 | 218 | 228 | 216 | Power Core at 25 % |

Also lines 406 "Orbital Cannon power signature detected", 419 "Orbital Cannon: Charge Online", 418 "...: Massive
Charge Online" (table 0x2B000095), started by script 0x340002CF itself (node 0x10000121 [406 / 418 / 419]).
Events 10 / 15 / 17 have the same lines as Crime Alley's core_25 / core_75 / core_50 (tester-named 2026-10-23).
So team health (500 / 500) is the **Power Core's health**; capture points charge an **Orbital Cannon** that strikes the
enemy Power Core in up to 4 tiers (75 / 50 / 25 / destroyed). P (strong).

### 2.2 Script 0x340002CF = the Orbital Cannon controller (C tree, data/script_trees/340002cf.json)

- Runs on class `0x400003F2` (template 0x490003F2: `0x10000539 = 0x340002CF`, world state `0x2E000B47`
  `env_pvp_core_a`, PerceivedType 0x2000, team 2, `0x1000052E = 5`, `0x100001EB = 0xDB`).
- Graph 0: start on event 0x10000085 (exit of S0 also sets lighting 0x1000000D via node 0x1000009C, plays line 406);
  event 0x1000007A = team 1 fired (team 2 damaged), 0x10000079 = team 2 fired; ImpactCounter++ (max ImpactCounterMax);
  timeline announcements (node 0x1000011A, icons 0x130029AD / 0x130016CD / 0x130029C4, tokens of 0x2B000098 - table
  not found in the English streams, O) with NeutralizedDuration + LockDuration countdowns; lines 418 (tier 3) / 419.
- Graph 1: GeneratorIID = entity found by node 0x10000016; node 0x1000010A(Entry_TeamNN_TierMM, generator) creates
  the impact; lighting 0x1000000B + RunScriptlet 0x10000925 on the impact entity (charge FX) for Phase1 = 20 s, reveal
  it in fog (0x100006FC) for Phase2 = 10 s, then DestructionImpulse large + small (cosmetic and destroy radii) at its
  position, LoopMax impacts; ImpactCounter 4 = final (Impact4Delay, then lighting 0x1000000A). Total 61 s.
- Lighting keys -> env (map-loading-deep-scan.md 1): 0x1000000D -> 0x0800000A (match), 0x1000000B -> 0x08000007
  (final charge), 0x1000000A -> 0x08000008 (after the final strike). ics sends 0x1000000A from the start (config
  `lighting_env`): P the match should use **0x1000000D**.

### 2.3 Power Cores and end cinematics (C)

- Cinematics `0x3500000D` (10.5 s, Character_0 = `0x2E000B47`, side 3, team 1, at **(18.39, 50.08, 252.50) yaw 15**)
  and `0x3500000E` (team 2, side 5, **(142.67, 50.33, 252.50) yaw -20**): Vfx_Startup, Vfx_Destruct_State0..3
  (frames 63-98), Vfx_OnExplode (120), Cinematic_Announcement (210) = **the Power Core destruction (defeat) shots**.
  `maps.py` has `end_cinematic: {}` and puts the **Foundry at the core's spot** (18.4, 50.1) / (142.7, 50.3).
- Recipe: spawn `0x400003F2` (ws 0x2E000B47) per team at those positions/yaws with team 0x1000009C and side
  0x100007A2 3 / 5, Vfx_Startup; on each strike tier play Vfx_Destruct_State(N-1); at 0 health Vfx_OnExplode and
  the losing team's cinematic (team 1 loses -> 0x3500000D). Foundry moved (G: behind the spawn platform
  0x2E000CA5 at (4.0, 46.2), e.g. (1.5, 47.0) / (158.5, 47.0)).

### 2.4 Capture points 0x4000013B (C data, P use)

- Template 0x4900013B (layout pack): ws `0x2E000B22` (`env_pvp_capture_point_c`, ctype 8, graph `0x1C000073`),
  PerceivedType 0x80200, vision 0x10000133 = 4.25 and 0x10000504 = 4.25 (P: capture radius), minimap category
  0x100004DA = 8, stats 0x10000165 = 0x48000148, vitals list 0x1000031A (4 entries 0x3B000095 / 96 / 9C / 9D) and
  0x100001D9 = 0x3B00009E, and **a basic attack** (slot 0x100008E3: script 0x340000D5, the turret attack; stat 18 =
  4.0, stat 30 = 12.0): an owned point shoots enemies (P). ics: points never attack (`units.think` returns).
- Scriptlet tables accept only Vfx_TeamColor_SetNull 0x10000B0D, `_CapturePoint_OnTeamBiasChanged` 0x100003A7,
  `_Entity_OnSetClientRelationship` 0x100003A6, **Vfx_TeamColor_SetContention 0x100008C4**, fades. **Not**
  BeingCaptured 0x1000032F / Captured 0x100002A9 / Lost 0x100002A8, which ics sends (no effect on GH).
- The graph reads `Property_Vital_CaptureBuffer_Percent` (strings in 0xA000016B; animation `env_pvp_capture_point_c_
  grow`): the ring grows with **vital type 3 = CaptureBuffer** (ui-complete.md VitalTypeList). ics sends no 0x42 to
  points (`client_vitals = False`). Recipe (P): give the point its vitals component and send 0x42 with the capture
  progress in the CaptureBuffer slot (which of the 4 vitals is type 3: O, try each in a test build); owner change =
  0x10000456 (the client runs 0x100003A7 itself); contested = 0x100008C4, neutral again = 0x10000B0D.
- Names (C, announcer captions): Wayne Tower (event 13), the Bridge (11), the Subway (16), the Townhouses (14), the
  Gas Station (12). Which marker is which: O (no record ties a name to a position). G: N (80, 127.8) = Wayne Tower
  (the single point; the map's skyline end), W/E and SW/SE pairs share no name, so the mirror pairs are
  Bridge/Subway and Townhouses/Gas Station in some order. On capture send 0x2039 with that event (or 0x2001 with
  the 0x82A line to the capturing team, 0x829 to the other).
- Minions (0x4000012D / 12E / EAA) all accept scriptlet **Robot_Minion_Capture_Attack** and the variants pack holds
  a `Capture` clip: GH minions capture points (P). ics minions only walk the rings.

### 2.5 Encounter template 0x49000B6C extras (C)

- Sector tracker 0x100007F7: 5 x (category 8, slots 1-5) **plus (category 27, slot 1)**: a sixth tracker = the
  Orbital Cannon (P; CC uses 26 relay / 28 device). ics sends only the five category-8 entries (0x2069).
- UI record 0x48000F52: 0x10000463 = 500 / 500 (team health), 0x10000464 = 1250, 0x10000C70 / C71 / C73 = 5.
- 0x100002E9: encounter statuses 0x48000073 (all), 0x4800014E (team 1), 0x4800014F (team 2) (G: per-team buff
  status, 0x10000258 = 0x21000021 / 0x2100000A). ics applies none.
- Music: lobby pack 0xA0000189 (0x10000897), environment rules 0x48000ABD (0x100009E7); banks 0x52000012
  Announcer_GothamHeights, 0x52000064 AMB_GothamHeights, 0x52000066 Music_GothamHeights (client-driven by state).

### 2.6 The Orbital Cannon is a large capturable: class 0x40000511 (C data, P flow)

- Template 0x49000511 (layout pack 0xA000016B; header `did | 3 | count`): ws `0x2E000D12` (the relay / control-point
  world state, ctype 8, graph 0x1C00008E), PerceivedType 0x80200, **minimap category 0x100004DA = 27
  LARGE_CAPTURABLE** (= the encounter's sixth tracker entry), tracker HUD 0x100007FB = 1, scale 0x6B4 = 1.4,
  capture radius 0x10000504 = 4.1, **id 0x100001EB = 0xA5 (165)**, stats 0x480006CE, 0x10000432 = 100.
- Script 0x340002CF addresses entity id 165 (node 0x10000039 [1, event, 165] sends it events; node 0x10000049
  [0x1000007A / 0x10000079, 165] waits for its "team 1 / team 2 fired" events). Reading (P strong): S0 -> unlock
  (0x10000060) and line 406; a team captures the cannon -> it raises 0x1000007A (team 1) / 0x10000079 (team 2) ->
  ImpactCounter++, timeline countdown, strike on the enemy (graph 1) -> NeutralizedTimer -> reset to neutral
  (0x10000078) -> LockTimer: locked (0x100000C9) -> unlock (0x10000060) with line 419 "Charge Online" (418 "Massive
  Charge Online" before tier 4) -> capturable again. The Power Core lines (15 / 17 / 10) follow each strike tier.
- Position (P): the map centre (80.0, 74.0): ring of ten `0x2E000006` sockets (ids 0x82-0x8B, 5 per team, radius ~6)
  (centre (80, 74)); `0x2E0005D6` at (80.0, 73.6, z 255.9) is only one of ~20 ambient **sound emitters** (0x1000049A =
  Wwise event hash, also at (80, 143.6), (66.4, 90) ...; client statics, ambience needs nothing). The sockets are P the
  cannon's charge / owner lights (type-3 statics, ws 0x2E000006 in resident pack 0xA0000161: client-drawn, but their
  team lights are G server-driven, mechanism O).
- The script runs on Power Core class 0x400003F2 (its 0x10000539; id 0x100001EB = 0xDB). In the original the server
  ran it; ics has no generic encounter-script host for it. Recipe: either run 0x340002CF through ics' script VM on the
  spawned cores (check node coverage: 0x1000010A, 0x10000016, 0x1000011A, DestructionImpulse, node 0x10000121) or
  author it: on cannon capture -> 0x2039 event 54 (fired) to both teams, timeline banner 0x100002AF with the 20 + 10 s
  countdown, lighting 0x956 = 0x1000000B on the final charge, after 30 s damage the enemy core one tier (125 team
  health), scriptlet Vfx_Destruct_State(N-1) on the enemy core, event 15 / 17 / 10, then neutral + locked for a lock
  time ([ics] authored, O) and unlock with line 419.
- How the five small points interact with the cannon (charge, requirement, drain): O. G: each held small point
  drains the enemy Power Core (today's drain) and the cannon is the big swing; the ring's 5 sockets per team show how
  many small points the team holds.

### 2.7 Other GH objects in the layout pack that ics never creates (C presence, G positions)

Present as records in the sent layout pack 0xA000016B (record starts): base aura `0x4000041F` (ws 0x2E000A35, team 1,
in-base status 0x100002C4 = 0x4800028B -> regen script 0x3400012B); stealth tile ws `0x2E000D36` + Hotspot Object
`0x4000039D` + brush status `0x4800028C` (script 0x340001CF; match variable BrushCounter); Health Pack generator
`0x40000180` (ws 0x2E00054B; spawns 0x40000182) and pickup class 0x400000A4 (ws 0x2E000FBB, PerceivedType 4 loot,
minimap 5 HEALTH_PICKUP; model `vfx_env_pvp_health_pack_a` in this pack); speed buff script 0x34000138; usage-object
script 0x3400012D. **Not** in GH's packs: the Crime Alley base gate Door 0x40000557 / 0x2E000CD7 (home 0xA0000162,
not sent) - P GH had no light-wall gate.
- No record places any of these on GH (as on Crime Alley). Candidate anchors: the 51 type-3 markers `0x2E000626` /
  `0x2E0006B3` / `0x2E0006B4` (17 each, in no installed pack, same triple on every 5v5 map) - G one marker kind per
  pickup / brush type; and the 20 team-tagged statics `0x2E00041F`-`0x2E000432` (2 sites x 2 teams per point, ~14 m
  outside each point, ids 0x1000005D 43-62, emitter list 0x7A3 with cue 0x19000147) - G team pads or the points'
  outer team banners (client statics, already drawn).
- Base aura recipe (C class, P pos): `0x4000041F` per team at the spawn platform `0x2E000CA5` (4.0, 46.2) /
  (156.0, 46.2), team 0x1000009C, Hotspot_Activate; inside -> status 0x4800028B (as `maps.py` "auras" for CA).

### 2.8 Smaller items

- Meteor storm: GH's zone pack holds `vfx_env_event_meteor_impact` and its variants pack the meteor fragment spawn
  animation, so GH had the meteor event too (P). `maps.py` GH has no `events` (CA / GD have "meteor_storm"); adding
  it also adds pack 0xA0000164 (Meteor Fragment 0x400006F1) through `maps.extra_packs`.
- An animated subway train (`env_got_vehicle_subway_train_a`, clips entrance / move) is in the zone pack: P a
  client-animated static (no record names a server event for it), O.
- Ambience: ~20 sound-emitter statics `0x2E0005D6` (0x1000049A Wwise hashes): client-placed, nothing to do (C).
- Power Core voice lines: ics plays core_75 / 50 / 25 only when a "core" unit is hit; GH's team health drains with no
  core unit, so events 15 / 17 / 10 never play. Point-capture lines (events 11-14, 16) and cannon line (54) are
  never sent either (on_objective sends a generic billboard only).
- `0x3500000F` (0 s, Character_0 0x2E000D32 at (80, 112), Cinematic_Announcement at frame 60): P an announcement
  helper shot, no known trigger (O).

## 3. Recipes ranked by impact (for ics; nothing applied here)

1. Power Cores `0x400003F2` / ws 0x2E000B47 at (18.39, 50.08, 252.5) yaw 15 and (142.67, 50.33, 252.5) yaw -20,
   team + side 3 / 5; move the Foundry off that spot (G (1.5, 47) / (158.5, 47)); `end_cinematic` {T1: 0x3500000D,
   T2: 0x3500000E}; Vfx_Destruct_State0-3 at 75 / 50 / 25 / 0 % team health, Vfx_OnExplode at 0. C pos, P link.
2. Orbital Cannon `0x40000511` at (80, 74) as a capturable (role "cannon", tracker category 27 slot 1), flow of 2.6
   (capture -> event 54 -> 30 s charge with lighting 0x1000000B -> one tier of damage to the enemy core -> neutral
   + locked -> unlock with line 419). P flow, G numbers.
3. Capture visuals: 0x10000456 owner (kept), Vfx_TeamColor_SetContention / SetNull instead of BeingCaptured /
   Captured / Lost; CaptureBuffer vital (type 3) via 0x42 for the ring; points shoot with 0x340000D5 (range from
   stat 18 = 4 or 30 = 12, O). P.
4. Announcer: capture events 13 / 11 / 16 / 14 / 12 (names O per point), cannon 54, Power Core 15 / 17 / 10 from the
   team-health thresholds (channel 2, set 0x4000047E). C lines.
5. Lighting 0x956 = 0x1000000D for the match (env 0x0800000A), 0x1000000B during the final charge, 0x1000000A after
   it. P.
6. Minions capture points (Robot_Minion_Capture_Attack). P.
7. Base aura 0x4000041F at the spawn platforms; health packs (0x40000180 -> 0x40000182 / 0x400000A4), stealth tiles
   0x2E000D36: classes C, positions G (marker triples 0x2E000626 / 6B3 / 6B4 are the only anchors).
8. Meteor storm on GH (P); per-team encounter statuses 0x4800014E / 14F (G); bots as world objects (all maps).
