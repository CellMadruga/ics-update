# Coast City (Onslaught) — gap analysis: original map vs our server

Encounters `0x40000270` (Coast City 5v5), `0x4000039C` (Crisis Labs: CC variant), `0x40000B6A` (Coast City v AI).
Map pack `0xA0C122E2`, landblock `0x23E3`, z ~250.2, team 1 west, team 2 = `x -> 160 - x`.
Static analysis of the installed data only (no REA / Ghidra). Confidence: C = read in the data, P = probable,
G = guessed. Written 2026-10-25; incremental.

## 1. What our server does today (run of 2026-10-25 08:57:32, encounter 0x40000B6A)

Source: `logs/server.log` lines 222-436, `logs/traffic.log` lines ~8200-12000. The tester left the match 0.6 s after
"match: started" (08:58:55.8 -> 08:58:56.4), so nothing after the countdown (waves, camps, events) was exercised.

Objects created (`ics/match/maps.py` `_coast_city`, `match.py start`):
- cores `0x40000C24` / `0x40000C23` (17.0, 62.5) yaw 105 / mirror yaw 255 (vitals 6000/6000);
- core turrets `0x40000400` / `0x400003FF` at (21.5, 64.0) / mirror (G position);
- inner turrets north `0x400003FA` / `3F9` (30.9, 96.5), south `0x400003FE` / `3FB` (40.7, 46.0) (G);
- lane turrets north / south `0x400003FD` / `3FC` (55.2, 123.5), (64.8, 28.0) (G) — each with head `0x2E000AA8`
  (Vfx_Startup, Vfx_Active_Blue/Red) and plate `0x2E000A9F` (Crime Alley's parts, reused);
- foundries `0x40000170` / `0x4000016F` at (1.0, 59.2) / mirror (G);
- 3 relays `0x4000089D` at (80, 131), (62, 76), (98, 76) (all G) with unit flags 0x80200, tracker 0x2069 cat 26 slots 1-3;
- Doomsday Device `0x400001F0` + trigger `0x4000054F` at (80, 82) (P), tracker cat 28;
- the player's champion + 9 bots (scoreboard 10 rows); no bot world objects appear in the traffic before the exit.

Messages: intro cinematic `0x35000020` (0x20F5), timeline start `0x100002AF` / `0x100002B1`, match clock 0x10000109,
dialog notice 0x10000205, HUD elements, scoreboard 0x1000005B, announcer 0x2001 lines 0xBB (187), 0x97 (151),
0xAE (174) at 08:58:25 / 45 / 55 (the countdown lines of the shared set), lighting key `0x956 = 0x1000001B`.

Not created / not sent on Coast City (the map spec has no entry): base gates, base auras, stealth hotspots,
camp nook / props, relay team visuals, the Doomsday creature, any CC-specific announcer event (relays unlock /
captured), map music / ambience changes, map events other than the generic meteor storm (whose pack 0xA0000164
is a Crime Alley-family pack).

## 2. Data findings (C unless marked)

### 2.1 Doomsday Device and its pad — our scriptlets go to the wrong object
- Device `0x400001F0` (template `0x490001F0`, pack 0xA0000162): world state `0x2E0008FD`, PerceivedType
  `0x80010`, minimap icon `0x100004DA = 0x1C` (28), sight `0x10000133 = 9`, icon `0x10000083 = 0x13001C32` (the
  same icon the encounter's tracker slot 4 names in `0x100007FC`), stat record `0x10000165 = 0x4800023B`, attack
  block `0x100008E3` with server script `0x10000328 = 0x340000D5` (our log shows `0x340000d5` running at 08:57:57).
  World-state table `0x1D0002FE` keys: Vfx_Active `0x100000EB`, Vfx_Stop `0x10000130`,
  **Vfx_CapturePoint_BeingCaptured `0x1000032F` / Captured `0x100002A9` / Lost `0x100002A8`**, **Vfx_Locked
  `0x10000757` / Vfx_Unlocked `0x10000776`**, **Vfx_OnFire `0x1000013E`**, Vfx_Object_Reset `0x100002DE`. So the
  Device itself is captured by presence and fires (P).
- Firing trigger `0x4000054F`: world state `0x2E00104E` = the generic pickup / pad state (table `0x1D000924`,
  33 keys). Its template names its own pad scriptlets: `0x10000D0E = 0x10001125` Vfx_Start_Pad_DoomsdayDevice and
  `0x10000445 = 0x10001096` Vfx_Active_Pad_DoomsdayDevice; the same table has `0x10001097`
  Vfx_Active_DoomsdayDevice and `0x10001166` Vfx_Active_DoomsdayDevice_Disabled. Status/hotspot `0x10000AC2 =
  0x4800064A`, stats `0x48000E30`, `0x1000025E = 5`.
- **Bug in `ics/match/objectives.py`**: `SC_DEVICE_CHARGE 0x10001096` / `SC_DEVICE_FIRE 0x10001097` are sent to the
  *device* entity, whose tables do not have them (they belong to the trigger pad); the device's own Vfx_OnFire /
  Locked / Unlocked / CapturePoint_* are never sent, and the pad gets no scriptlet at all (likely invisible).

### 2.2 Power relays and the Power Core's relay beams
- Relays `0x4000089D` and `0x40000D25` (both in 0xA0000162; identical except `0x10000627`): world state
  `0x2E000D12` (model env_pvp_power_relay_a, graph 0x1A0009DF with grow / head_rotate animations), PerceivedType
  `0x80200`, icon 0x1A (26), capture radius / sight `0x10000133 = 3`, tables `0x1D000385` (Vfx_TeamColor_SetNull
  `0x10000B0D`, _CapturePoint_OnTeamBiasChanged `0x100003A7`, Vfx_TeamColor_SetContention `0x100008C4`) +
  `0x1D0000E1`. The relay shows its owner through property `0x10000456` (-> `0x100003A7`) and contention through
  `0x100008C4`; our server sets 0x10000456 but never sends SetContention / SetNull.
- **The Power Core world state `0x2E0013EE` (table `0x1D00098A`) carries `Vfx_Relay_01/02/03_Start / _Active /
  _Stop` (`0x10000AED`-`0x10000AF5`), `Vfx_Relay_All_Stop 0x10000B1E`, `Vfx_Indestructible 0x1000008E` /
  `_Stop 0x1000013D`, `Vfx_Status_Turret_Hardened 0x10000DB5`, `Cinematic_Announcement 0x10000A50`** plus the team
  colour table `0x1D000385`. The core draws one beam per relay slot (P: relay N held by the core's team, or the
  enemy's link to it). Lane turrets (ws `0x2E000AA0`, table `0x1D00035D`) and the core turret (`0x2E000AC4`) have
  Vfx_Indestructible / Vfx_Status_Turret_Hardened too. Same table `0x1D000360` exists in GD / CA / Tut1 packs.

### 2.3 Announcer: the Coast City set `0x49000534` (event -> lines, line captions read from table 0x2B0000A1)
Set events: 31-37 (turret / core attacked / destroyed, as the CA set), **49** relays unlocked (436 / 437),
**50** relay captured (251 / 275), **51** Doomsday Device taken (240 enemy / 279 ours; 236 / 239 named),
55 / 56 core turret, **57** relay being captured (443 / 444), **58** relays unlock in 10 s (447 / 448), **59**
relay neutralized (459 / 460), 61 Raider defeated, 62 (714 / 715, caption not in the CC table), **65** relays
reactivated (743 / 742), **66** relays deactivated, unlock in 60 s (738 / 736). No 0x2039 event exists for these
line keys (0x2001 only, as the countdown): 241 / 248 relays operational in 30 / 10 s, 257 unaligned relays
operational, 704 / 705 / 256 a new relay operational in 30 / 10 s / now, 237 unaligned Device detected, 238 / 442
/ 244 Device activation in 60 / 30 / 10 s, 234 Device activated, 440 Device auto-fire in 10 s, 441 destroy the
Device's defenses, 231 / 247 / 233 drones in 30 / 10 s / operational, 734 / 735 elite drones in both / top lane.
The 0x2001 line keys found in the CC layout pack by the pattern `key | hash | 00 | token | 0x2B0000A1`.

### 2.4 The Onslaught rules these lines describe (P from the captions; timings C where a line names them)
1. Relays start neutral and locked; "operational in 30 / 10 s" then "unaligned relays operational" (unlock time
   not in the data, G: ~ the drone start + 60 s). Relays may come online one at a time ("new relay operational").
2. A relay is captured by presence (being captured 57 -> captured 50; neutralized 59 when the enemy turns it
   neutral first: two-step capture, P).
3. A team's relays are deactivated for **60 s** (66; then 58 at -10 s, 49 unlocked, 65 reactivated): most likely
   after that team fires the Device or loses its relays to a Device shot (G).
4. The Device appears ("unaligned Device detected"), activates after a **60 / 30 / 10 s** countdown, must be
   unlocked by destroying its defenses (441: the Doomsday Guardian `0x40000430` / its pad, P), is taken by
   presence (51), and **auto-fires 10 s** after (440) at the enemy (Vfx_OnFire; camera shake events in its
   `0x1000031A`).
5. Encounter template: tracker slots `0x100007F5` [26, 26, 26, 28] / `0x100007FA` [1, 2, 3, 1]; 2 lanes
   (`0x10000BB7 = 2`); `0x10000464 = 1000` in the match record `0x48000F54` / `0x48000562` (G: a score cap).

### 2.5 How the Device fires (C script, P reading)
The trigger `0x4000054F` is a *usable target* (table `0x1D0000D0`: `_Selection_UsableTarget 0x100001E5`) with a
ground-target skill `0x4800064A` (stat 0x12 radius 7.5, stat 0x17 range 10, stat 15 cooldown 3, ground markers
`0x48000155` / `156`, server script **`0x340001FA`**). The script: on cast at `TargetPosition` it spawns
**`0x4000035D`** (ws `0x2E000A92`, Vfx_OnFire, minimap category 4) with the caster's team at the point, damage =
base + delta x **Doomsday Device level** (the Device's level formula `0x3B0001E7` = 1 + t / 90 s) separately for
characters and buildings (node 0x10000118 x2), starts its cooldown, shows a "disabled" VFX handle while cooling,
and re-spawns a pad `0x4000054F` (state S3). So the original Device is **aimed by the holding team's champion via
the pad** (P), plus an auto-fire after 10 s (line 440); our server instead auto-hits the enemy core for 20 %.

### 2.6 Layout classes of 0xA0000162 the server never creates (C classes, G positions)
- Base gate Door `0x40000557` (ws `0x2E000CD7`: Object_Closed / Object_Open, team colour) — same class as Crime
  Alley's; base aura Base `0x40000C7F` (ws `0x2E000A35`, Hotspot_Activate, radius `0x100002AA = 6`, team 1 template);
  stealth hotspot `0x4000039D` (ws `0x2E000D36`); team-1 base FX `0x4000059E` (ws `0x2E000CD9`, Vfx_Active only).
- "Environment" objects `0x40000448` (ws `0x2E0008FB`, team colour + Vfx_Active / Vfx_OnExplode) and `0x40000621`
  (ws `0x2E000D25`, Vfx_Active_State1-3, PerceivedType 0x2000), `0x400005C9` (ws `0x2E000D22`, scripts
  `0x34000167` / `0x34000347`), `0x40000F26` (ws `0x2E0004BD`, icon 0xB), pickup `0x400000A4` (ws `0x2E000FBB`, Loot,
  icon 5; jungle drop twin `0x400005E1` in 0xA0000161), superpad `0x40000EED` (ws `0x2E001314`). Roles of the first
  four are G (0x40000448 fits "the Device's defenses").
- Statics (`0x820123E3`, 792 parsed): spawn platforms `0x2E000CA5` at (3.21, 58.8) yaw -75 team 1 / (156.79, 58.81)
  yaw 75 team 2 (client statics, C); camp markers 942 / 944 / 945 at **4** sites: (80, 145) [+942 at (80, 146.75)],
  (44.5, 90.5) yaw 286, (115.5, 90.5) yaw -280, (80, 9) yaw 180 — **no marker at (80, 57)**, where our server puts
  the Doomsday Guardian; Device site `0x2E001178` / `1181` (80.0, 82.02, 250.27) yaw 180; lane mouths
  `0x2E000AF4`-`AF7` with team; no marker for relays, gates or stealth tiles (they must be authored).
- Navmesh necks of the team-1 base (for gates, G): north exit y = 79, x 18.5-29.75 (centre (24.1, 79.0));
  south-east exit x = 33, y 45.0-58.0 (centre (33.0, 51.5)). Team 2 = 160 - x.

## 3. Gaps ranked by impact, with recipes

1. **Doomsday Device behaviour and visuals** (C data, P rule). Send device scriptlets from its own table:
   Vfx_Active at spawn, Vfx_Locked until unlocked then Vfx_Unlocked, CapturePoint_BeingCaptured / Captured / Lost
   on presence capture (radius ~ its sight 9), Vfx_OnFire when it fires. Send the pad `0x4000054F` its
   Vfx_Start_Pad_DoomsdayDevice `0x10001125` + Vfx_Active_Pad_DoomsdayDevice `0x10001096` (or
   `0x10001166` _Disabled while locked / cooling). Fire: spawn `0x4000035D` at the target with the team, Vfx_OnFire,
   then damage in radius 7.5 (characters and buildings, scaled by device level). Timers from the lines: 0x2001
   237 (detected) -> 238 / 442 / 244 at -60 / -30 / -10 s -> 234 activated; on capture 0x2039 event 51; 440 at
   -10 s before an auto-fire. Fix `SC_DEVICE_*` in objectives.py. P.
2. **Relays and the core link** (C visuals, P rule). Relays: send Vfx_TeamColor_SetNull at spawn,
   Vfx_TeamColor_SetContention when contested, owner 0x10000456 (already). On each relay owner change send the
   owning team's core `Vfx_Relay_0N_Start` then `_Active` (N = tracker slot), `_Stop` on loss, `Vfx_Relay_All_Stop`
   when that team's relays are deactivated; keep the core `Vfx_Indestructible` while it is protected and
   `Vfx_Indestructible_Stop` when it becomes attackable (G: an Onslaught core is attackable only while the enemy
   holds relays). Lines: 241 / 248 / 257 (0x2001) before relays open; 0x2039 events 57 / 50 / 59 on capture
   steps; 66 then 58 / 49 / 65 for the 60 s lockout. Positions stay G (no data marker); (80, 131) is 0.8 m off the
   navmesh. P / G.
3. **Base gates and auras** (C classes, G gate positions): add to `_coast_city` `"gates"` Door `0x40000557` /
   `0x2E000CD7` at the two necks above (north heading 0, south-east heading 90 deg) and `"auras"` Base `0x40000C7F` /
   `0x2E000A35` radius 6 at the spawn platforms (3.2, 58.8) / (156.8, 58.8). The existing match code then does the rest.
4. **Bots are never created in the world** (C, traffic: only the local champion; generic, not map-specific).
5. **Camps** (C markers, G compositions): use the 4 marker sites with their yaw; move the Doomsday Guardian
   `0x40000430` from (80, 57) to the Device (its patrol loop (47-113, 75.5-102.5) circles the centre, P); send the
   jungle units' Vfx_Spawn_Event01 on spawn (all CC jungle classes carry Vfx_Spawn_Event01-04 / Alt01-02).
6. **Lane waves** (P): 0x2001 231 / 247 / 233 at -30 / -10 / 0 of the first wave; elites `0x40000442` / `443` join a
   lane after 734 / 735 ("elite drones in top / both lanes", G: after that lane's inner turret falls); Raider
   Drone `0x40000D23` unused today.
7. **Stealth tiles** (`0x4000039D`): class present, positions unknown (needs the original video; G).
8. **Missing street meshes**: 11 static DIDs live only in the GH zone pack 0xA000009A (maps-complete.md 6); as on
   Crime Alley, find the small packs that hold them and add them to `[ics] encounters` packs (P).
9. Music / ambience: client-driven (rule `0x48000ABE`, lobby pack 0xA0000188); intro 0x35000020 and end cinematics
   0x35000012 / 13 already wired; lighting 0x1000001B sent. Nothing to add (P).

