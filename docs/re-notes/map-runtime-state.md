# Match-wide runtime state per v AI map: what the client expects from the server (2026-10-25)

Scope: the state that belongs to the **match / the map as a whole** once the map has loaded and while the match runs
(HUD bar pieces, sector tracker, timeline, team health, lighting / music / environment, map scripts and the events
they wait for), on the four v AI maps: Crime Alley 0x40000C82 (CA), Gotham Divided 0x40000B6B (GD), Coast City
0x40000B6A (CC), Gotham Heights 0x40000B6C (GH). Not covered here (other notes / agents): the per-map static object
census, the 10 % -> 100 % load sequence, per-unit combat.

Sources: exe decompilation `re-work/decomp/c` (read only; VAs, base 0x400000) + capstone on the read-only exe; Flash AS2
`re-work/ui-as2` (`gameplay/match/*`, `gameplay/minimap/*`); packs via `ics.gamedata` (template / record reads, a scan
of every 0x34 reference in the 12 map packs); `ics.script_model` on data/script_trees; ics tree of 2026-10-25;
logs/traffic.log + server.log of 2026-10-25 17:46 (CA match 17:47:11 - 17:51:47, GH match started 17:52:35, ended
during load). Builds on full-match-mechanics.md, map-objectives-recipes.md, announcer-and-map-elements.md,
full-maps-world.md, cinematics-vfx-audio.md, sweep-s2c-match.md, sweep-property-listeners.md, client-skill-instances.md.
Tags: **C** = read in code / data / log, **P** = probable, **G** = guess (becomes a config default), **O** = open.

---------------------------------------------------------------------------------------------------------------

## 0. New findings (summary)

| # | Finding | Tag |
|---|---|---|
| 1 | **Sector tracker entries flagged 0x10000A9B are spectator-only.** The template reader `0x859970` (callers `0xA28980`, `0xA49BA0`) walks array `0x100007F7`; an entry whose bool `0x10000A9B` is true is **skipped unless `[0x1B77138]+0xAC` is set** (`0xABEE50`; `0x1B77138` is the spectator system object created by `0xAC42A0`, the same flag that gates the "you are here" note). So Gotham Divided's 6-entry tracker shows the player **two** beacon pips (category 29, slots 1 / 2, icons `0x1300256D` / `0x1300256A`); entries 3 / 4 (A9B = 1) are the spectator copies and 5 / 6 have no category. ics sends beacon tiers for slots 3 / 4 (pulse, vision): they never show for a player | C |
| 2 | **TeamUsageLock 3 draws a padlock on the pip.** Flash `SectorObjective.UpdateDisplay`: `m_mcLocked._visible` when `eLockedToTeam == 3 (AllTeams)` or equals the viewer's team (1 / 2); 0 = no lock. The lock field is ignored only for BEACON (29). ics `objectives.py` sends `LOCK_ALL = 3` on every GH point, CC relay and the Device: **every pip shows a lock all match** | C |
| 3 | **The client instantiates every entity's 0x8E script list itself** (component init `0x9798E0` -> `0x44C620` reads property 0x8E -> `0x9789C0(did)` per script). Every structure template (turrets, dampeners, cores, core turrets of all four maps) lists **0x34000838**: on `0x10000088` it keeps running only on an allied structure (ClientRelationship `0x10000425` = friend), on **`0x100000E7`** it runs node `0x100000B8 [5]` for `UnderAttackPingDuration` (5 s) then `[0]`. Node `0x100000B8`'s client half `0xAB4700` writes the map-note **decoration** in MapManager (`0xA4C1F0`, note field +0x58) = the blinking "under attack" ping on the minimap. Nothing in the client raises `0x100000E7` (no constant use besides the node registration `0x13C...`), so the original server delivered it to the client copy, the one path being event **0x2008** (`u8 0 | u64 entity | u32 event | u32 script DID`, handler `0xAA1BF0` on the entity's effects component, where the 0x8E instances live). ics never sends 0x2008: **no "under attack" minimap ping on any map** | C mechanism, P delivery path |
| 4 | **Node 0x1000009C (lighting key 0x956) is client-executed** (`0xAB4AE0`, vtable `0x15FA5A8`, factory `0x981710` registered for id `0x1000009C` at `0x13C44D0`): the client's own script instances (cinematic scene scripts) set / clear the local player's 0x956. During a match only **GH's server script 0x340002CF** changes it (`0x1000000D` at the start, `0x1000000B` at the 4th charge, `0x1000000A` after the 4th impact); CA / GD / CC have no in-match lighting change (C: no other map-hosted script has the node). Property 0x956 is `net=0` (local), so a mid-match change must go through the player bundle (ics re-sends it with `_objects`) | C (code, data), P (bundle path) |
| 5 | **Victory / defeat voice on GD and CC is played by the end cinematic's own script**: `0x3400076B` (GD cinematics `0x35000014` / `15`) and `0x3400076C` (CC `0x35000012` / `13`) wait for the timeline events `0x100000F2` / `0x100000F3` / `0x100000F1` and run node `0x10000121 [0, 29, .., team, other]` (or `[395 ..]` tie), whose client half `0x9CE360` builds the announcer call (`0x100003BD` line, `0x10000806` event). They also set lighting `0x1000001C` / `0x1000001B`. CA's end cinematics `0x3500003A` / `3B` and GH's `0x3500000D` / `0E` carry no script. ics also sends event 29 at the end on every map: **GD / CC may hear Victory / Defeat twice** | C (data, client half), P (double play) |
| 6 | **The client's "current encounter" `[root+0x68]+0x6C`** (read by the music system `0xA8F890`, the HUD controller `0xA85BF0`, the lobby audio) is written only by **0x20C0 JoinedQueue** (`0x8BA780` -> `0xA37C70`, the QueueKey DID) and **0x20DA** (`0xA7F0B0`, first of 3 values). ics sends 0x20C0 with the encounter (traffic 17:46:44 `0x40000c82`, 17:52:02 `0x40000b6c`): OK | C |
| 7 | **SetMatchTime with isPreStart = 0 is the music / match-start trigger**: `0xA902F0` calls `0xA8F7D0` on the encounter-environment system (flag +0x14C, a timer at start + 120 s, per-entity cue setup), sets the HUD's start time (+0x148) and runs the one-shot `0xA3CB70`. ics sends it at `_begin` (17:48:15.183): OK | C |
| 8 | The Wwise-hash properties of the encounter templates (`0x100008FD`-`0x10000905`, `0x10000AC7`-`0x10000AD2`, `0x100009FE`, `0x10000C86`) are read by accessors `0x857E90`-`0x8581E0`, called from the lobby class (vtable `0x160ADC8`) and front-end notices (`0x8B8E40`, `0x8B9150`) and the PvP-encounter list query `0xA68030`: champion-select / front-end audio, **not match state** | C readers, P use |
| 9 | No script hosted on a map static or environment object waits for a server event, except throwables (`0x3400015F` / `0x34000160` / `0x34000118`: picked / thrown / landed, not match-wide) (C, scan of all 0x34 references in the 12 map packs). The only map-controller script is GH's `0x340002CF` (host record `0x480007C2`, property `0x10000539`). Ambient creatures, weather, doors other than the base gates: nothing in data (C) | C |
| 10 | **0x10000206**: no property descriptor, no exe reference (hex or decimal), no catalog entry: nothing reads it (C absence). Its neighbours are notices (0x10000204 client "entered the match", 0x10000205 dialog enable, 0x10000207 load complete) | C |

---------------------------------------------------------------------------------------------------------------

## 1. Encounter template properties: what the client builds by itself (no server message)

Values of the four v AI templates (`ics.gamedata.template_properties`; the parse of arrays is approximate, the tracker
entries are the exact parse of map-objectives-recipes.md 4 / 5.1). "Reader" = client accessor (C).

| Property | CA / GD / CC / GH | Reader / effect | Server part |
|---|---|---|---|
| 0x1000054E encounter type | 1 / 4 / 5 / 3 | `0x857Cxx`; Flash `MatchManager.OnLoadComplete` picks the HUD pieces (GH: team health + timeline + tracker; others: timeline + tracker) | none |
| 0x100007F7 tracker entries {0x10000A9B spectator-only, 0x100007FA HUD position, 0x100007F5 category, 0x100007FC icon} | CA (26, slot 1); GD (29 / 1 / 0x1300256D), (29 / 2 / 0x1300256A), (29 / 3, A9B), (29 / 4, A9B), (- / 5), (- / 6); CC (26 / 1-3), (28 / 1); GH (8 / 1-5), (27 / 1) | `0x859970` -> Flash `SectorObjectiveTracker.SetupSectorObjectives` builds empty pips (owner neutral) | **0x2069 per pip** (section 2.2) |
| 0x10000287 minimap record | 0x48000E36 / 0x4800067C / 0x48000563 / 0x4800014C | LoadMap `0xA4C2C0` on the player's 0x100001D3 | 0x100001D3 (sent) |
| 0x1000028A ruleset | 9 / 0xD / 0xD / 0xD | statics filter | none |
| 0x10000802 announcer set | 0x40000D4C / 0x40000554 / 0x40000534 / 0x4000047E | dialog channel 2 | 0x2039 events / lines (announcer-and-map-elements.md) |
| 0x10000ADC music record, 0x100009E7 music rule records | CA 0x4800128C, GD 0x48000E6B; CC / GH none (rules 0x48000ABE / 0x48000ABD) | `CEncounterEnvironmentSystem 0xA8F890` (adaptive music from per-team life-state counters) | SetMatchTime isPreStart 0 (sent), LifeState / team on entities (sent) |
| 0x100001D2 UI record | 0x4800111B / 0x48000F50 / 0x48000F54 / 0x48000F52 | 0x10000463 team health start (GH 500 / 500), 0x10000464 target time | 0x100004FB / 0x10000134 (GH, sent), 0x1000000E target time (sent) |
| 0x1000021C | 600.0 on all | O (G: earliest surrender) | ics uses it as earliest surrender |
| 0x10000B41 bot levelling script | - / 0x340007E2 x3 | O (bot level-ups; server) | not run by ics (bots level by XP) |
| 0x10000897 lobby music pack; 0x100008FD-905 / 0x10000AC7-AD2 / 0x100009FE / 0x10000C86 Wwise hashes | per map | lobby / front-end audio (finding 8) | none in the match |
| 0x10000B3E bot pool, 0x10000BCB / BCC players | 1 / 14 / 14 / 14; 1, 5, 5, 5 / 1, 10, 10, 10 | lobby | lobby (sent) |

---------------------------------------------------------------------------------------------------------------

## 2. Match-wide server messages the client listens for

### 2.1 Encounter / match HUD listener (vtable `0x1605930`, full-match-mechanics.md 0 #4) and ics status

| Message | Client effect | When the original sent it (P unless C) | ics (log 17:47-17:52) |
|---|---|---|---|
| notice 0x10000109 SetMatchTime (f64 start, f64 end, u8 preStart) | HUD clock; isPreStart 0 starts music system + HUD start time (finding 7) | at entry (pre-start), again at 0 | OK: 17:47:14 pre, 17:47:33 after intro (start moved to -42 s), 17:48:15 start |
| notices 0x100002AF / 0x100002B1 StartTimeline | the timeline bar | answer to client 0x100002AD | OK (17:47:14, 17:47:17) |
| notice 0x100002AB AddTimelineEvent / 0x100002AE batch | future map-event icons | each scheduled map event | MISSING on all maps except the GD / CC meteor storm (no Raider, pods, Leviathan respawn, relays, Device, cannon icons) |
| notice 0x10000424 AddTimelineBanner | centre announcement with countdown | GH: script 0x340002CF ShowAnnouncement (C) | MISSING (GH cannon banners; section 4.1) |
| notice 0x100002AC remove banner / event | | when a banner ends | MISSING (builder exists, never called) |
| event 0x2069 tracker status | pips + minimap note colour | at HUD ready and on every owner / contender / lock / decoration change | CA none; CC / GH sent, lock WRONG (2.2); GD only at beacon kills, slots 3 / 4 invisible |
| notices 0x100004FB / 0x10000134 team health | GH bar | at HUD ready, on change, answer to 0x10000137 | OK on GH |
| notice 0x1000005B roster | scoreboard, portraits | on K/D/A/level/money change | OK (40 sends on CA) |
| event 0x217A kill feed, notice 0x1000021C kill card | | each champion kill | OK (ics sends both) |
| notice 0x100002EB billboards, 0x100002BC stop | | kills, structures, result | OK |
| notice 0x1000000E match ended | | after the end cinematic | OK |
| event 0x215C dampener counts | spectator bar only | dampener death | OK (GD / CA) |
| event 0x2008 script event to an entity's client instance | structure under-attack minimap ping (finding 3) | each hit on an allied structure (the client copy throttles to one ping per 5 s) | **MISSING** (no builder) |

Client notices of the match seen in the log (C): 0x10000207 load complete, 0x100002AD timeline ready, 0x100000D2 HUD
ready, 0x1000015E, 0x10000204 "entered the match" (unhandled, harmless), 0x10000117 cinematic state. The client did not
send 0x10000137 on CA (no team-health bar there): as expected.

### 2.2 Sector tracker semantics (Flash `SectorObjectiveTracker` / `SectorObjective`, C)

- Pip lookup: by `(category, HUD position)`; an unknown pair -> `ReportError` only. The minimap copy
  (`MinimappyThing.RecvNotice_UI_UpdateTrackerStatus`) looks the note up by **entity IID**: a fake IID (ics beacons
  `0x0200000000000D00 + slot`) only logs an error, the pip still updates.
- Fields: owner (0 neutral, 1, 2) -> colour; contention team -> "inductor" animation **only if it is 1 or 2 and differs
  from the owner** (`ALIGNMENT_VALUE_UNKNOWN` = -1); ics sends 3 for "both teams on the point", which matches no case
  (no animation; P harmless, better: send -1 or keep the last capturer); lock: 0 none, 1 / 2 team-locked (padlock for
  that team), **3 padlock for everyone**; decoration 9 BeaconAlert plays its alert clip (again on every update with the
  same decoration); 9th word = obscured.
- Recipe per map (owner, contender, lock):
  - GH points: `0, 0, 0` at start (capturable), owner on capture, lock 0 always (P: no point lock rule in data).
  - GH cannon (27 / 1): lock **3** while 0x340002CF holds it locked (start until 0x10000085, the 120 s LockTimer,
    after the 4th impact), 0 while capturable, owner = firing team during the 65 s neutralized phase. ics: matches
    (lock 3 when state != unlocked, 0 otherwise) (C ics bosses.py `_cannon_tracker`).
  - CC relays (26 / 1-3): lock 0 when open, 3 while the relay schedule keeps them dark (P, lines 66 / 49); Device
    (28 / 1): lock 3 until unlock, 0 while capturable, 3 again after a fire (relock); decoration 2
    DOOMSDAY_REVENGE_OVERLAY while held (ics sends 2 when held, C ics).
  - GD beacons (29 / 1-2): lock ignored by Flash; owner = the team holding the buff, decoration 9 on change.
  - CA (26 / 1): one SMALL_CAPTURABLE pip; ics has no object for it (relay P, announcer-and-map-elements.md 4.1).

---------------------------------------------------------------------------------------------------------------

## 3. Properties the client reads on the PLAYER object (listeners on the local player, C scan of `0x58BA40` call sites in functions that resolve the local player)

| Property | Listener | What it drives | ics | Without it |
|---|---|---|---|---|
| 0x100001D3 encounter DID (component, net 8) | `0xA0CBC0`, `0xA5B120`, `0xA85BF0` (the latter only when spectating), map manager `0xA6A8E0` | LoadMap (minimap, fog textures), shop catalogue, HUD setup; needs a CHANGE | OK (late change, patched caves) | no minimap / fog / shop |
| 0x100002EB (did of a 0x48 record, net 1) | `0xA85BF0` (`0xA567F0` treats it like 0x100001D3: `0xA337B0`, `0xA12930`, `0xA40190`); reader `0x856xxx` reads a property from that record, default enum `0x10000002` | P: a UI / HUD record override of the encounter; the default is used when absent | not sent | nothing visible (default record) (P) |
| 0x956 lighting key (enum 0x30000092, net 0, local) | polled by `0x7E35C0` (every frame / 2.5 s; patched faster) | environment record (sky, key light, fog colours) | OK per map (`[ics] lighting_env`), constant all match | black / wrong look (fixed) |
| 0x100000FA / 0x10000B2D / 0x10000C5B / 0x10000C66 | `0xA7CA20` -> `0xA8DFB0` per team member (portrait list by IID `0xA17A60`) | team portraits: dead / cannot-act dim (FA, B2D), C5B bool and C66 iid (O: AFK / controller) | FA / B2D yes, C5B / C66 no | O |
| 0x100001AF / 0x1000035E / 0x10000C85 / 0x10000CD6 | `0xA8C770` | skill points, gold, shop flag, item count | yes except 0x10000C85 (O) | - |
| 0x100004FF | `0xAA42A0` | nameplate / minimap class | yes | - |

There is no "phase" or "mode" property on the player or an encounter object: the match phase reaches the client only
through SetMatchTime's isPreStart, the match-ended notice and the HUD notices above (C: no other listener on the local
player). Script event `0x10000085` ("phase start") exists only inside server scripts (GH 0x340002CF) (C).

---------------------------------------------------------------------------------------------------------------

## 4. Map environment during the match

| Item | Data / code | CA | GD | CC | GH |
|---|---|---|---|---|---|
| Lighting key 0x956 at start | env records via region table 0x04000000 | 0x10000002 OK | 0x1000001C OK (P value) | 0x1000001B OK (P value) | 0x1000000D OK (C, 0x340002CF S0 exit) |
| Lighting change in match | node 0x1000009C in a server script | none (C) | none (C) | none (C) | **MISSING**: 0x1000000B when the 4th charge starts (graph 1, before the 31 s Impact4Delay), 0x1000000A after the 4th impact (C, 0x340002CF graph 1) |
| Lighting at match end | end cinematic scripts | none | 0x1000001C by 0x3400076B (client) | 0x1000001B by 0x3400076C (client) | none |
| Music | 0x10000ADC record; start on SetMatchTime(0) | OK | OK | no record (C) | no record (C) |
| Weather / day cycle | none in data or exe (C, cinematics-vfx-audio.md 5.2) | - | - | - | - |
| Ambient env-state objects | `_CEntitySystem_EnvironmentStateChange 0x10000413` runs when 0x1000065C (component, net 8) / 0x1000065D (net 0) change on an entity with bool 0x10000554 (`0xA813F0`); 25 tables in zone packs 0xA000009A (GH), 0xA00000FC (GD), 0xA00000D2 (CC), 0xA00002E5 (CA) | O who set it; the statics keep their default state | same | same | same |
| Team lights | GH: ten 0x2E000006 around (80, 74.5) (Vfx_Active_Blue / _Red / _Yellow, ids 0x1000005D 105-107); CC: 0x2E000940 / 941 lane mouths, 0x2E000942 camp sites | - | - | O mechanism (static census) | O mechanism (P: tied to the cannon / point owners) |
| Base gates | Object_Closed / Object_Open (server objects) | OK | OK | NO (map-manifests.md 3) | none on GH |

### 4.1 GH cannon controller 0x340002CF: what the client should see (C script, run in the VM in map-objectives-recipes.md 1)

ics replaces the script with the native `bosses.py` cannon. Compared with the script:

| Script step (C) | Client message | ics |
|---|---|---|
| S0 exit on 0x10000085: lighting 0x1000000D, UpdateObjective line 406, hint 10, unlock 0x10000060 -> id 165 | 0x956 (bundle), 0x2039 line 406, tracker lock 0 | 406 OK (`detected`), lighting constant (= OK), unlock OK |
| S1 pre-fire ShowAnnouncement by ImpactCounter (tokens of 0x2B000098, icon 0x13000AFE) | 0x10000424 banner | **MISSING** |
| capture -> S2 / S3 -> S7: banner icons 0x130029AD / 0x130016CD with NeutralizedDuration (65 s) countdown for the firing team; second banner icon 0x130029C4 "available in" NeutralPlusLockDuration (185 s) | two 0x10000424 with countdowns (ttCountdown = now + 65 / 185) | **MISSING** (0x2039 event 54 is sent) |
| graph 1: per strike node 0x100000B8 [3] on the impact (decoration 3 Meteor_Devastation_Zone on its map note), DestructionImpulse at the impact | map note with decoration 3 on the impact entity; 0x8A sphere | ics sends a static 0x20D2 marker only (no decoration) |
| 4th: lighting 0x1000000B, 31 s delay, banner DurationImpactTotal (61 s); after: lighting 0x1000000A | 0x956 x2, banner | **MISSING** |
| S4 unlock lines 419 / 418 | 0x2039 lines | OK |

---------------------------------------------------------------------------------------------------------------

## 5. Map scripts that wait for events (scan of every 0x34 reference in the map packs; hosts = the record holding it)

Who runs a script: the server runs what a template lists in 0x10000328 (attack / behaviour) and 0x10000539 (GH
controller); **the client also instantiates the 0x8E list** (finding 3) and cinematic scene scripts (P), and runs only
the client halves of their nodes.

| Script | Host (maps) | Waits for | Who must raise it | ics |
|---|---|---|---|---|
| **0x34000838** structure ping | 0x8E of every turret / dampener / core / core turret (all four maps; foundry and GH Power Core excluded) | 0x10000088 (init), **0x100000E7** (damaged) | 0x10000088: the client itself (`0x96E030` broadcasts it to the component's instances, P); 0x100000E7: the server, by 0x2008 to the structure's IID | server copy gets 0x100000E7 (script_nodes.py 665); **client copy never** -> no minimap ping |
| 0x340007EC turret warning (training floaty text, node 0x100001A3, LessonsEnabled 0x10000A87, WarningStateCurrent 0x10000D87, attackable flag 0x10000249) | 0x8E of CA turrets 0x40000C86 / C8B (tutorial-family classes) | 0x10000088, 0x10000120, 0x10000162 | client (coaching only) | n/a (v AI turrets 0x40000C8C / C86: C86 is team 2's turret on CA v AI and carries it; lessons off unless 0x10000A87) |
| 0x34000600 objective arrow / alert ping (RunScriptlet arrow on the player's agent when near) | 0x8E of CA turrets C86 / C89 / C8B, table 0x1D000923 | 0x10000088, 0x1000005F, 0x10000060, 0x10000193 + polled range | client | n/a |
| 0x34000014 structure attack | 0x10000328 of all structures and foundries | 0x10000088, 0x1000001D, 0x10000008 / 09, 0x10000126, 0x10000171 | server (ics units.py, init event 0x10000088) | OK |
| 0x340002CF GH cannon controller | 0x10000539 of 0x480007C2 / Power Core 0x400003F2 | 0x10000085 (start), mission events 0x1000007A / 0x10000079 [165], 0x1000001C [284 / 314], 0x10000083, 0x10000107 (self), 0x10000110 | server | replaced by bosses.py (section 4.1 gaps) |
| 0x340000D5 point / Device attack | 0x10000328 of GH points 0x4000013B, CC Device 0x400001F0, GD control point 0x400003AF | 0x10000008 / 09 / 0C, 0x1000001D, 0x10000118, 0x10000126 | server, once owned | OK (`match_point_attack`) |
| 0x34000670 / 0x3400007D / 0x3400051A / 0x3400051B drops | CA Raider 0x40000CA2 / A71 (8E), heavy creatures, GD buff destroyers | 0x10000149 (spawned), 0x10000007 {KillerIID} | server | OK (`run_jungle_scripts`) |
| 0x34000512 / 0x3400057B / 0x34000541 / 0x34000442 / 0x3400057A boss attacks | Raiders, Leviathan, Doomsday Guardian | init / attack events, 0x100000E7 / 0x100000EA (Guardian) | server | OK (units) |
| 0x3400076B / 0x3400076C victory | GD 0x35000014 / 15, CC 0x35000012 / 13 | 0x100000F1 / F2 / F3 (cinematic timeline) | client (cinematic) | n/a; double voice risk (finding 5) |
| 0x340006F2 intro | 0x3500003C (CA), 0x35000024 (GD), 0x35000020 (CC), GH none | 0x10000060 (timeline) | client | n/a |
| 0x3400015F / 0x34000160 / 0x34000118 throwables | CA / GD / CC / GH throwable props (0x49000454 / 459 / 81A ..., 0x2E000EFE, 0x2E0006E3) | 0x10000049 / 0x10000124 / 0x10000035 | server (lift / throw) | not match-wide |
| 0x340005DF, 0x340005E5, 0x340005F4, 0x34000605, 0x340006A2-A9, 0x34000732 / 733 | CA pack: Tutorial / 1vAI conversations and cinematics | 0x10000060 / 8 | tutorial director | not v AI |
| Status / hotspot scripts (0x3400012B / 12D / 130 / 138 regen / speed pads, 0x340001CF stealth, 0x340006C0 / C1 base aura, 0x340004AB, 0x34000513-517, 0x34000523) | 0x48 statuses of pads / auras | 0x10000003 / 06 apply / remove | server | OK where ics applies them |

No environment / static object script waits for a server or mission event (C), so no "map animation" (doors,
lights, platforms) is gated on a server event on these four maps; everything time-driven is C++ rule (O schedule,
map-objectives-recipes.md 0).

---------------------------------------------------------------------------------------------------------------

## 6. Per map: MISSING / WRONG / OK

### 6.1 Crime Alley v AI (0x40000C82)

| State | Status | Exact message / when | Evidence | Conf |
|---|---|---|---|---|
| Clock, timeline start, scoreboard, kill feed, billboards, match end | OK | - | log 17:47:14 - 17:51:44 | C |
| Lighting 0x956 = 0x10000002 | OK | bundle | config | C/P |
| Music start | OK | 0x10000109 preStart 0 at 0 | `0xA902F0` | C |
| Tracker pip (26 / 1) | MISSING | 0x2069 `{iid of the slot-1 object, owner, contender, lock 0, icon 0, pos 1, cat 26, deco 0}` at HUD ready and on capture | template 0x100007F7 entry 1; no 0x2069 in the CA log | C (pip), P (object = relay) |
| Structure under-attack ping | MISSING | 0x2008 `{structure iid, 0x100000E7, 0x34000838}` to the defending team on each hit (>= 5 s apart) | finding 3 | P |
| Timeline icons: Raider (at 300 s), jungle (45 / 60 s) | MISSING | 0x100002AB `{handle, severity 2, icon, team 0, ttEventTime}` ~60 s before; 0x100002AC when it happens | Flash EventTimerV2; no data icon | G |
| Raider + drop | OK (scheduled at 300 s; not reached in the 3.5 min test) | | config match_raider | P |
| Victory voice | OK (no cinematic script on CA) | 0x2039 29 | finding 5 | C |
| Countdown / wave / jungle lines | OK | 0x2039 0x100003BD lines | log 17:47:45 - 17:49:15 | C |

### 6.2 Gotham Divided v AI (0x40000B6B)

| State | Status | Exact message / when | Evidence | Conf |
|---|---|---|---|---|
| Clock, timeline, scoreboard, music 0x48000E6B, lighting 0x1000001C | OK | | | C/P |
| Beacon pips at start | MISSING | 0x2069 for (29 / 1) and (29 / 2), owner 0, at HUD ready (ics sends them only at the first kill) | finding 1 | C |
| Beacon slots 3 / 4 (pulse, vision) | WRONG | spectator-only pips: a player never sees them; either drop them or map those two beacons onto slots 1 / 2 | `0x859970` A9B skip | C |
| Under-attack ping (turrets, dampeners, core, core turret) | MISSING | 0x2008 as CA | finding 3 | P |
| Timeline icons: pods at 600 s, Leviathan respawn, meteor storm | PARTIAL | meteor storm sent (event + banner); pods / Leviathan none | objectives.py events_tick | C (ics), G (schedule) |
| Victory voice | WRONG (P) | the cinematic script plays event 29; skip ics's own (or keep and accept a double) | finding 5 | P |
| Pod / Leviathan / Raider flow | OK (authored) | | bosses.py | G |

### 6.3 Coast City v AI (0x40000B6A)

| State | Status | Exact message / when | Evidence | Conf |
|---|---|---|---|---|
| Clock, timeline, scoreboard, lighting 0x1000001B; music none | OK | | | C/P |
| Relay pips (26 / 1-3), Device pip (28 / 1) | WRONG lock | 0x2069 lock 0 while capturable (3 only while locked); today 3 always -> padlock on all four pips | finding 2 | C |
| Device decoration | OK | 2 while held | objectives.py | C |
| Under-attack ping | MISSING | 0x2008 | finding 3 | P |
| Timeline icons: relays open, Device unlock / auto-fire, meteor | PARTIAL | meteor only; Device / relays need 0x100002AB + 0x10000424 with countdown at the -60 s line | G |
| Victory voice | WRONG (P) | as GD (0x3400076C) | finding 5 | P |
| Base gates | MISSING | (static census / map-manifests.md) | | P |

### 6.4 Gotham Heights v AI (0x40000B6C)

| State | Status | Exact message / when | Evidence | Conf |
|---|---|---|---|---|
| Team health bar | OK | 0x100004FB at start / HUD ready, 0x10000134 on change | log 17:52:36 | C |
| Point pips (8 / 1-5) | WRONG lock | lock 0 instead of 3 | finding 2, log 17:52:36 (`tracker capture N`) | C |
| Cannon pip (27 / 1) | OK | lock 3 / 0 by state | bosses.py | C |
| Cannon banners | MISSING | 0x10000424 with the script's tokens (table 0x2B000098) and countdowns 65 / 185 / 61 s | section 4.1 | C (script), P (banner = node 0x1000011A) |
| Lighting steps | MISSING | 0x956 = 0x1000000B at the 4th charge, 0x1000000A after it (player bundle re-send) | 0x340002CF graph 1 | C |
| Impact decoration | MISSING | the impact as an entity with decoration 3 (or a 0x20D2 note whose decoration is set) | node 0x100000B8 [3] | P |
| Point attack, capture ring | OK / MISSING | ring: CaptureBuffer vital (map-objectives-recipes.md 2, O slot) | | P |
| Music | none in data | - | | C |
| Victory voice | OK (no cinematic script) | | | C |

---------------------------------------------------------------------------------------------------------------

## 7. Ranked fix list

| # | Fix | Maps | Effort | Conf |
|---|---|---|---|---|
| 1 | **Tracker lock**: `objectives._tracker` sends lock 0 for capturable points / relays / the open Device, 3 only while locked (Device before unlock / after a fire, relays while dark); contested = last capturing team, not 3 | GH, CC | one line + states | C |
| 2 | **GD beacon pips**: send both player pips (29 / 1, 29 / 2) owner 0 at HUD ready; put every beacon kind the rule keeps on slots 1 / 2 (the spectator copies 3 / 4 may mirror them) | GD | small | C |
| 3 | **Structure under-attack ping**: new builder `script_event(entity, event, script)` = event 0x2008 `u8 0 \| u64 \| u32 \| u32`; on a hit of a structure send `{eid, 0x100000E7, 0x34000838}` to its team (the client copy throttles 5 s; ics may throttle too) | all | small + one test | P |
| 4 | **CA tracker pip**: give the CA slot-1 SMALL_CAPTURABLE an object (relay 0x4000089D, map-objectives-recipes.md 4) or at least send 0x2069 owner 0 so the pip has an IID | CA | small | P |
| 5 | **GH cannon banners and lighting**: in bosses.py send 0x10000424 at the fire (65 s for the firing team, 185 s "available in"), the 4th-charge banner (61 s), 0x956 0x1000000B / 0x1000000A by re-sending the player bundle with `M.LIGHTING_ENV[0]` changed; remove banners with 0x100002AC | GH | medium | C (data), P (path) |
| 6 | **Victory voice on GD / CC**: do not send event 29 when the end cinematic carries 0x3400076B / 76C (or after a test shows a double) | GD, CC | one line | P |
| 7 | **Timeline icons for scheduled objectives** (Raider, pods, Leviathan respawn, relays, Device unlock / auto-fire, cannon unlock): 0x100002AB ~60 s ahead + 0x100002AC when due, from the same schedule bosses.py / objectives.py already keep | all | medium | G (icons O) |
| 8 | GH impact decoration 3 on the impact's map note (entity with a map-note category, or decoration on the 0x20D2 note) | GH | small | P |
| 9 | Open: who sets 0x1000065C / D on the zone-pack ambience objects; 0x10000C5B / C66 on team portraits; 0x100002EB | all | test | O |

### 7.1 Proposed [ics] config keys (defaults; each with the reason when implemented)

- `match_tracker_lock`: `{"open": 0, "locked": 3}` (fix 1; 0x2069 lock field, Flash `SectorObjective` padlock rule).
- `match_tracker_contested`: `"last"` (fix 1; "both" = the old 3).
- `match_tracker_initial`: `true` - every template pip gets a 0x2069 at HUD ready, objects or not (fixes 2 / 4).
- `match_beacons.<map>.player_slots`: `[1, 2]` (fix 2; template 0x100007F7 entries with 0x10000A9B are spectator-only).
- `match_structure_ping`: `{"enabled": true, "event": "0x100000E7", "script": "0x34000838", "gap": 5.0}` (fix 3).
- `match_cannon.<map>.banners`: `{"fired": 65, "available": 185, "final": 61}` and `match_cannon.<map>.lighting`:
  `{"final_charge": "0x1000000B", "after_final": "0x1000000A"}` (fix 5; 0x340002CF values, C).
- `match_victory_voice_skip`: `["gotham_divided", "coast_city"]` (fix 6; the end cinematic's script plays event 29).
- `match_timeline_icons`: `{event name: {"lead": 60, "icon": "0x...", "severity": 2}}` (fix 7; icons O, 0 = none).
- `match_impact_decoration`: `3` (fix 8; node 0x100000B8 [3]).
