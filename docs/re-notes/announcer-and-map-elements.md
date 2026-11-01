# Announcer sets per map and map elements ics never spawns

Data analysis 2026-10-25 (no exe disassembly; packs in `C:\Infinite Crisis Server\rp`, decoded with
`icserver/gamedata.py` / `ics/gamedata.py`). Tags: [C] confirmed in data, [P] probable, [G] guess, [O] open.
Captions are paraphrased to a few words (identifiers only, no game text). Written incrementally.

Prior notes this builds on: countdown-keymap-gaps.md (3.2 event -> caption decode), map-gaps-gotham-divided.md (3),
map-gaps-coast-city.md (2.3), map-gaps-gotham-heights.md (2.1), crime-alley-2v2-video.md.

## 0. Method [C]

- Set records: template `0x1000080A` array of `0x1000080C` rows `{0x10000806 event, 0x10000829, 0x1000082A,
  0x10000895, 0x10000894, 0x10000808, 0x10000805 line keys, 0x1000088E bool}` read with `Game.record`.
- Line entries: every pack scanned for `f32 1.0 | f32 x | u32 key | u32 Wwise hash | u8 0 | u32 token | u32 table
  0x2B......`; 274 keys found; caption = English (table, token). Plus a looser scan (no leading 1.0) for keys 166 / 215 / 229.
- Which set each encounter names (template props): `0x10000802` = map set, `0x10000803` = shared set 0x4000047A.

| Encounter | 0x10000802 | 0x10000803 | layout pack (holds the set and its lines) |
|---|---|---|---|
| CA v AI 0x40000C82 / Clash 0x40000E68 / E74 | 0x40000D4C | only on E68 / E74 | 0xA00002E6 |
| GD v AI 0x40000B6B / 0x40000E62, PvP 0x40000399 | 0x40000554 | only on 0x399 | 0xA0000168 |
| CC v AI 0x40000B6A, PvP 0x40000270 / 0x39C | 0x40000534 | only on PvP | 0xA0000162 |
| GH v AI 0x40000B6C, PvP 0x4000013E | 0x4000047E | only on PvP | 0xA000016B |
| Tutorial Advanced 0x40000CA6 | none | none | (own script 0x34000628) |

The shared set record 0x4900047A is copied into all four layout packs (C). The v AI templates lack 0x10000803; the
tester nevertheless heard the shared events on Crime Alley v AI (2026-10-23 test), so channel 1 resolves anyway (P).

**Line keys exist only in the layout pack that carries them** (each pack holds its own copy of the tables it
needs). A 0x2001 key not in the current map's layout pack has no line on that map (P strong: 231 / 247 / 233
"Drones in 30 / 10 s / operational" exist only in Coast City's 0xA0000162; Crime Alley and Gotham Divided have
their own copies 672 / 670 / 668 in table 0x2B0000A2; Gotham Heights has none).

### 0.1 Column semantics [C from captions + the 2026-10-23 test]

`0x1000082A` = the line for a listener on the **acting** team (0x1000081D: destroyer, capturer, killer, winner);
`0x10000829` = the line for the other team (the one that suffers). Evidence: event 40 829 = "Ally Middle Dampener
deactivated", 82A = "Enemy ..."; event 29 829 = Defeat, 82A = Victory; event 33 829 = "Our Bottom Turret
destroyed", 82A = "The enemy's ...". "Under attack" events (31, 32, 34, 35, 41, 47, 39, 56) have **only** 829: the
acting team is the attacker, only the victim team hears them; sending them with the listener on the acting team
is silent (this is why 6 events "said nothing" in the 2026-10-23 test, see 2). 0x895 / 0x894 = spectator forms
naming a team ("{}"), 0x808 / 0x805 = extra forms on kill / shutdown events (O who hears them).

**Bug in ics/match/announcer.py (2001 / "both" modes only):** `LINES = {event: (829, 82A)}` labelled
(ally, enemy) and `line(event, own_team=True)` returns 829, i.e. the *bad-news* form for the acting team (own
victory plays "Defeat", own turret kill plays "Our ... destroyed"). Fix: `line()` must return 82A when the
listener is on the acting team. With the default `announcer_mode = "2039"` the client picks the column itself
and this does not matter. `LINES` is also Crime Alley's set only; on GD / CC / GH the same event ids map to other
keys (2039 mode is unaffected; the /anunciador fallback test is).

## 1. Complete announcer tables [C ids / keys / hashes; trigger P unless noted]

"Snd": every line entry below carries a non-zero Wwise event hash except 395 Tie (hash 0, caption only). Lines are
listed 829 / 82A (see 0.1). "ics" = what ics/match sends today (grep of ics/match/*.py + logs/traffic.log 2026-10-25).

### 1.1 Shared set 0x4000047A (every map, dialog channel 1; 0x2039)

| Ev | 829 / 82A | Label | Trigger | ics |
|---|---|---|---|---|
| 8 | 160 / 201 | team annihilated (ace) | last living enemy champion dies (team = killer's) | yes (`annihilated`) |
| 18 | 169 / 177 | First Blood | first champion kill of the match | yes |
| 19 | 158 / 192 | Relentless | killer streak 3 (P) | yes |
| 20 | 164 / 198 | Ferocious (config `furious`) | streak 4 | yes |
| 21 | 167 / 200 | Dominating | streak 5 | yes |
| 22 | 171 / 202 | Unstoppable | streak 6 | yes |
| 25 | 175 / 150 | Invincible | streak 7+ | yes |
| 23 / 26 / 27 / 28 | 205/181, 199/196, 195/180, 185/154 | Double / Triple / Quadra / Penta kill | multi-kill window | yes |
| 24 | 388 / 389 (808: 386) | "killer shutdown victim" | victim had a streak >= 3 | yes (`shutdown`) |
| 52 | 390 / 387 | "victim was shutdown" | same moment, P the victim-centred form | no |
| 30 | 191 / 186 (808: 179, 805: 166) | "killer defeated victim" | every champion kill with no other voice | no (config name `enemy_defeated` = 30 exists, never called) |
| 29 | 392 / 393 | Defeat / Victory | match end, team = winner | yes |

### 1.2 Crime Alley set 0x40000D4C (channel 2; layout 0xA00002E6)

| Ev | 829 / 82A | Label | Trigger | ics |
|---|---|---|---|---|
| 15 / 17 / 10 | 220/206, 226/213, 218/228 | core at 75 / 50 / 25 % | core HP thresholds, team = attacker | yes |
| 31 / 35 / 34 | 303, 291, 305 (829 only) | our top / mid / bottom turret under attack | structure hit, team = attacker | no |
| 32 | 292 (829 only) | our Power Core under attack | core hit | no |
| 56 | 433 (829 only) | our core turret under attack | core turret hit | no |
| 41 | 382 (829 only) | our middle dampener under attack | dampener hit | no |
| 36 / 37 / 33 | 315/312, 302/304, 307/309 | top / mid / bottom turret destroyed | turret death, team = destroyer | sent as 33 (wrong: bottom) |
| 40 | 384 / 380 | middle dampener deactivated | dampener down | sent as 34 (wrong: bottom turret under attack, silent) |
| 55 | 428 / 431 | core turret destroyed | core turret death | sent as 40 (wrong: dampener) |
| 64 / 63 | 721/719, 725/718 | dampener reactivating in 30 s / reactivated | respawn -30 s / respawn, team = owner | sent as 52 / 50 (wrong) |
| 61 | 82A only 697 (+ 0x2001 701 for the other team) | Raider defeated | Raider kill | config 49 (wrong); no Raider spawned on CA (Part B) |
| 49 / 50 / 58 | 436/437, 251/275, 447/448 | relays unlocked / relay captured / unlock in 10 s | no relay on CA (P: leftovers of the CC copy) | n/a |

### 1.3 Gotham Divided set 0x40000554 (channel 2; layout 0xA0000168)

Turrets 31 / 35 / 34 (attack), 36 / 37 / 33 (destroyed), 32 core attack, 56 / 55 core turret, as CA. Dampeners:
47 / 41 / 39 top / mid / bottom under attack (379, 382, 378), 38 / 40 / 48 deactivated (367/366, 384/380, 361/371),
64 / 63 reactivating / reactivated (721/719, 725/718), 60 Leviathan defeated (666 / 667), 61 Raider (697). No core %
events. ics: the by-map turret / dampener / core-turret / reactivate ids are right; missing: every "under attack",
60, 61 (the default 49 is not in this set).

### 1.4 Coast City set 0x40000534 (channel 2; layout 0xA0000162)

31-37 / 55 / 56 turrets and core as CA; 49 relays unlocked (436/437, team = relays' owner); 50 relay captured (251 /
275); 57 relay being captured (443 / 444); 58 relays unlock in 10 s (447 / 448); 59 relay neutralized (459 / 460,
team = former owner); 65 relays reactivated (743 / 742); 66 relays deactivated, unlock in 60 s (738 / 736); 51
Doomsday Device taken (240 / 279); 61 Raider (697); 62 Doomsday Guardian defeated (714 / 715). No core % and no
dampener events. ics by-map errors: `relays_unlocked` = 58 (that is "unlock in 10 s"; unlocked = 49),
`relays_unlock_soon` = 66 (that is "deactivated, unlock in 60 s"; soon = 58). Missing: 57, 51, 62, 65, 66 (as the
reset), turret_north / turret_south (no id: fall back to nothing), under attack. core_75/50/25 send 15/17/10, not in
this set (silent, harmless).

### 1.5 Gotham Heights set 0x4000047E (channel 2; layout 0xA000016B)

13 Wayne Tower, 11 the Bridge, 16 the Subway, 14 the Townhouses, 12 the Gas Station captured (225/211, 224/207,
222/212, 223/210, 209/217); 54 Orbital Cannon fired (412 / 409); 15 / 17 / 10 core 75 / 50 / 25 %. ics sends
`capture_captured_<slot>` / `capture_captured` but GH has no by-map entry: all capture voices are silent, and core %
never plays (no core unit is hit: team health drains, map-gaps-gotham-heights.md). No turret, wave or kill-free lines.

### 1.6 Lines with no event (0x2001 only; key -> layout packs that hold it)

| Keys | Label | Maps | Trigger | ics |
|---|---|---|---|---|
| 156 / 187 / 151 / 174 / 173 | match begins in 60 / 30 / 10 s, initiating, begun | all four | countdown | yes (60 s never reached: the intro ends at -42) |
| 215 | map title line (GD 0x2B0000A9, GH 0x2B000095; CC caption empty; absent on CA) | GD, GH, CC | intro / load (P) | no |
| 672 / 670 / 668 | drones in 30 / 10 s / operational (0x2B0000A2) | CA, GD, CC | first wave -30 / -10 / 0 | no (ics sends 231 / 247 / 233) |
| 231 / 247 / 233 | same, table 0x2B0000A1 | CC only | CC first wave | sent on every map (silent off CC, P) |
| 673 / 669 / 671 | jungle creatures online in 30 / 10 s, phasing complete | CA, GD, CC | first camp spawn -30 / -10 / 0 | no |
| 696 / 699 / 698 | Raider online in 30 / 10 s, phasing complete | CA, GD, CC | Raider spawn | no |
| 701 | the enemy defeated the Raider | CA, GD, CC | Raider killed, listener not on the killer's team | no |
| 685 / 683 / 684 / 681 | phase pods incoming / arrival 30 / 10 s / touched down | GD | pod drop | no |
| 686 / 690 / 688 / 689 | upper pod seismic mode in 30 / 10 s / initializing / engaged | GD | pod 1 | no |
| 691 / 687 / 692 / 693 | lower pod, same four | GD | pod 2 | no |
| 660 / 653 / 662 / 652 | seismic anomaly / creature detected / identified / Leviathan emerged | GD | Leviathan arrival | no |
| 658 / 659 / 663 | Leviathan resurfacing in 60 / 30 / 10 s | GD | Leviathan respawn timer | no |
| 674 / 677, 676 / 675, 679 / 678, 680 | Regen, Speed, Pulse beacon activated / upgraded; Vision beacon upgraded | GD | beacon state (Part B) | no |
| 368 / 381 / 383, 290 / 295 / 317 / 296 / 432 | the enemy's dampener / turret / core / core turret under attack | CA, GD, CC | attacker-side form (G: probably unused) | no |
| 241 / 248, 257, 704 / 705 / 256 | relays operational in 30 / 10 s, unaligned relays operational, new relay in 30 / 10 s / now | CC (704/705/256 also CA) | relay schedule | no |
| 237, 238 / 442 / 244, 234, 440, 441 | Device detected, activation in 60 / 30 / 10 s, activated, auto-fire in 10 s, destroy its defenses | CC | Device schedule | no |
| 734 / 735 | elite drones in both / top lane | CC | elites unlocked | no |
| 396-400 | we lost Townhouses / Gas Station / Bridge / Subway / Wayne Tower (one shared hash) | GH | point lost by the listener's team | no |
| 406 / 419 / 418 | cannon signature detected / charge online / massive charge | GH | cannon schedule (script 0x340002CF) | no |
| 229 / 230 | meteor storm warning / incoming (pack 0xA0000164, table 0x2B0000A0) | GD, CC (ics adds the pack) | meteor storm | no |
| 395 | Tie (hash 0) | all | draw | no |

Script evidence (C, data/script_trees): node `0x10000121` (labelled UpdateObjective in ics/script_nodes.py) carries
`[line key, event, 0, 0, a, b, team, other team]`: GD / CC victory scripts 0x3400076B / 76C play `[0, 29, .., 1, 2]` /
`[0, 29, .., 2, 1]` (event 29 by team) or `[395 ..]` (Tie); GH's 0x340002CF plays 406 / 418 / 419; tutorial
scripts play 393. So 0x10000121 is the server-side announce node (an event of a set or a bare line, with teams)
[P strong]; StartConversation 0x100000D1 carries the tutorial's dialogue keys (0x34000628).

## 2. The by-ear `announcer_events` (2026-10-23 13:14 test) vs the captions [C]

The test played `announcer.EVENTS` in order (8, 10, 15, 17, 18-30, 31, 32, 33, 34, 35, 36, 37, 40, 41, 49, 50, 52, 55,
56, 58, 61, 63, 64). From 31 on, the six "under attack" events (31, 32, 34, 35, 41, 56) are silent for the acting
team (0.1). The heard sequence was therefore: bottom turret destroyed (33), top destroyed (36), mid destroyed (37),
mid dampener (40), relays unlocked (49), relay captured (50), "was shutdown" (52), core turret destroyed (55), unlock
in 10 s (58), Raider (61), dampener reactivated (63), reactivating (64) = 12 lines, which the tester assigned to the
first 12 ids 31 ... 52, leaving 55, 56, 58, 61, 63, 64 "silent". This explains every mismatch exactly, including the
note "37 said Shutdown too" (the 7th heard line was 52) and "event 33 said the enemy's Middle Turret" (that was 37).

Corrected Crime Alley mapping (`[ics] announcer_events`; 8, 10, 15, 17, 18-30 were right):

| Name | by ear | correct | Name | by ear | correct |
|---|---|---|---|---|---|
| turret_bot | 31 | 33 | relays_unlock_soon | 41 | 58 |
| turret_top | 32 | 36 | raider_defeated | 49 | 61 |
| turret_mid | 33 | 37 | dampener_reactivated | 50 | 63 |
| dampener | 34 | 40 | dampener_reactivating | 52 | 64 |
| relays_unlocked | 35 | 49 | core_turret | 40 | 55 |
| relay_captured | 36 | 50 | (new) was_shutdown | - | 52 |

New names to add: `turret_attack_top` 31, `turret_attack_mid` 35, `turret_attack_bot` 34, `core_attack` 32,
`core_turret_attack` 56, `dampener_attack_mid` 41 (GD: `dampener_attack_north/mid/south` 47 / 41 / 39),
`champion_kill` 30, `leviathan_defeated` 60 (GD), CC `relay_capturing` 57, `device_taken` 51, `guardian_defeated` 62,
`relays_reactivated` 65, `relays_deactivated` 66; CC fixes `relays_unlocked` 49, `relays_unlock_soon` 58,
`turret_north` 36, `turret_south` 33 (P: top = north as on GD; CC's inner turrets have no own line, G: same lane id).
GH by-map: `capture_captured_<slot>` -> 13 / 11 / 16 / 14 / 12 (slot -> name order O, see map-gaps-gotham-heights.md
3), `cannon_fired` 54. The lane names `turret_mid` etc. are used directly by match.py (`turret_<lane>`), so
`turret_north` / `turret_south` must exist for CC and GD (GD has them).

## 3. Missing announcer lines, ranked by how often they would play

| # | What | Path | Exact server trigger |
|---|---|---|---|
| 1 | champion kill "X defeated Y" | 0x2039 ev 30, ch 1 | `_kill_voices`: when `names` is empty (no first blood / shutdown / multi / streak), append `champion_kill` (P: the original said it for every plain kill) |
| 2 | structure under attack (turret 31/35/34, core 32, core turret 56, dampener 41 or 47/41/39) | 0x2039 ch 2, team = attacker | in `_on_hit` for a structure of the local team hit by any enemy (champion or minion): `<role>_attack_<lane>`, at most once per structure per 15 s (G; also skip while it is the local champion's own lane fight? no: original pinged always, G) |
| 3 | wave lines on CA / GD | 0x2001 672 / 670 / 668 | per-map `match_wave_lines` (CA, GD: {-30: 672, -10: 670, 0: 668}; CC: 231 / 247 / 233; GH: none). Today 231 / 247 / 233 go to every map |
| 4 | corrected structure / dampener / core-turret ids on CA | 0x2039 | config only (section 2) |
| 5 | jungle online | 0x2001 673 / 669 / 671 | at `match_camps.first` -30 / -10 / 0 (CA video: 10 s line at match 0:36, complete at 0:46 = camps at +45 s, so `first` 45 on CA) |
| 6 | "was shutdown" | 0x2039 ev 52 | P alternative to 24 for the victim's team; G: send 24 to the killer's side only: keep 24 |
| 7 | GH captures + lost | 0x2039 13/11/16/14/12; 0x2001 396-400 | `on_objective` new owner -> event per point; old owner == local team -> the matching 396-400 key |
| 8 | CC relay flow | 0x2039 57 on capture start, 50 captured, 59 neutralized, 49 unlocked, 58 at -10 s, 66 / 65 reset; 0x2001 241 / 248 / 257 / 704 / 705 / 256 | objectives.py relay timers (map-gaps-coast-city.md 2.4) |
| 9 | Raider | 0x2001 696 / 699 / 698 before spawn; 0x2039 61 on kill (killer's team), 0x2001 701 to the other | when a Raider exists (CA 0x40000A71, CC 0x40000D60 already spawned as a "big" camp, GD 0x40000938) |
| 10 | CC Device / elites | 0x2001 237, 238 / 442 / 244, 234, 440, 441, 734 / 735; 0x2039 51 / 62 | device schedule; elite lanes when an inner turret falls (G) |
| 11 | GD pods / Leviathan / beacons | 0x2001 685 / 683 / 684 / 681, 686-693, 660 / 653 / 662 / 652, 658 / 659 / 663, 674-680; 0x2039 60 | Part B |
| 12 | GH cannon | 0x2001 406 / 419 / 418; 0x2039 54 | cannon capture / unlock (map-gaps-gotham-heights.md) |
| 13 | meteor storm | 0x2001 229 or 230 | at each `_meteor_storm` start (GD / CC: pack 0xA0000164 is sent; CA lacks it: G which key) |
| 14 | map title | 0x2001 215 | at the intro start on GD / GH (P) |
| 15 | Tie | 0x10000121 / 0x2001 395 (no sound) | never (no draw rule) |

## 4. Part B: map elements the v AI maps name that ics never spawns

Sector tracker per template (`0x100007F5` category / `0x100007FA` HUD slot / `0x100007F7` count; C):
CA v AI 0x40000C82 and 0x40000CA6 = **[26] / [1] (one SMALL_CAPTURABLE)**, CA Clash 0x40000E68 / E74 = none;
GD = [29 x 4, 0x10000A9B x 2] / [1-4] (count 6); CC = [26, 26, 26, 28] / [1, 2, 3, 1]; GH = [8 x 5, 27] / [1-5, 1].

### 4.1 Crime Alley v AI (0x40000C82; packs 0xA00002E6 layout, 0xA00002E7 variants)

ics spawns: core / core turret / dampener / turret per team, foundry, 3 camps of `0x40000CA1` + 2 `0x40000CA0`, gate,
aura, stealth tiles. Named by the data, never spawned (classes C, templates read here; positions G unless said):

| Class | ws | What (template) | Recipe |
|---|---|---|---|
| `0x40000CA2` (vAI family CA0 / CA1 / CA2, P); twins `0x40000A71` (same stats 0x480010D2), `0x40000C6C` (750 HP flat, P Clash) | `0x2E000F1B` (Raider model, in 0xA00002E7) | **Raider**, neutral 0x10000C6E, camp kind 0x10000C56 = 6 (big), HP 1500+75, attack script 0x34000512, death script 0x34000670 spawns pickup `0x40000C49` (ws `0x2E00104E`) | the CA pack holds the Raider lines 696 / 699 / 698 / 701 and set event 61, so CA v AI had a Raider (P strong). Spawn one Raider at the centre nook (80.0, 97.25) yaw 180 (type-3 markers 0x2E000944 / 945, crime-alley-visuals.md) in place of that small camp, at a G time (~5 min, 0x2001 696 -30 s, 699 -10 s, 698 on spawn); on kill 0x2039 61 to the killer's team, 0x2001 701 otherwise, then spawn `0x40000C49` at its position for the killer's team; respawn G 5 min |
| `0x40000CDA` / `0x40000E83` | `0x2E0010A7` | Regen Destroyer, kind 7 (buff), HP 1425+95, script 0x34000088 | G: alone at one of the side camps (52, 90) / (113, 90) instead of a tripod trio; kill status from its template (0x100008CE = 0x100008CF on every CA neutral, O meaning) |
| `0x40000A61` / `0x40000E7D` (heavy, kind 4), `0x40000A64` / `0x40000E7E` (small) | `0x2E000BE2` | other Tripod sets (A6x older, E7x P Clash) | none needed (ics uses CA1 / CA0) |
| `0x4000089D` | `0x2E000D12` (relay model) | **Power Relay** (perceived 0x80200), in the CA layout pack | P: the v AI tracker's single SMALL_CAPTURABLE (category 26 slot 1); the CA pack also carries relay events 49 / 50 / 58 and lines 704 / 705 / 256 ("new relay operational in 30 / 10 s / now", absent from GD / GH). Recipe: objective role "relay", slot 1, position O (G: the nook (80, 97.25), shared with the superpad reading of crime-alley-visuals.md; or the jungle centre), unlock schedule with 704 / 705 / 256, capture 0x2039 50, neutralize 59 is not in the CA set (silent) |
| `0x40000CB5` | `0x2E001314` | superpad (flags 0x20040) | already in crime-alley-visuals.md (b) |
| `0x400008CF` | `0x2E000E38` | drop pod / regen pad (flags 0x20040) | reward of a camp (O) |
| `0x40000180` -> `0x40000182` | `0x2E00054B` | health-pack generator | O position |
| `0x400005C9` | `0x2E000D22` | throwable rock (neutral, flags 0x22) | O |
| `0x40000E86` | - | turret without team | unused (P test object) |

The timeline of the original v AI (crime-alley-2v2-video.md, the Clash video) shows jungle at +45 s; ics `match_camps.first`
is 60 s.

### 4.2 Gotham Divided v AI (0x40000B6B)

Confirms map-gaps-gotham-divided.md 4 / 5 and adds, from the GD line tables (C keys, P rules):
- **The four tracker slots are four typed beacons: Regen, Speed, Pulse, Vision** (lines 674 / 677, 676 / 675, 679 /
  678, 680: "<type> Beacon activated / upgraded"; no "Vision activated" line exists). Two tiers per beacon (activated,
  upgraded). Candidate classes in 0xA000016E / 0xA0000168 (C classes, P pairing): Regen Destroyer `0x40000940`
  (-> Regen), Haste Destroyer `0x4000093D` (-> Speed), Pulse Emitter `0x40000951` / `0x400009B6` (-> Pulse),
  Surveillance `0x4000093F` / Surveillance Tower `0x400007FD` (-> Vision). Recipe (G rule): killing a buff destroyer
  activates (then, second kill, upgrades) that team's beacon: tracker 0x2069 slot 1-4 owner = killer's team, 0x2001
  activated / upgraded key to the killer's team. This replaces the two 0x400003AF "beacons" (slots 1-2).
- **Two phase pods named Upper and Lower** with a "seismic mode" (686 / 690 / 688 / 689 and 691 / 687 / 692 / 693)
  and a drop sequence 685 -> 683 (-30 s) -> 684 (-10 s) -> 681 (touched down). Recipe: Phase Pod `0x40000A79`
  (ws `0x2E000FC7`) at the two sunken sites (105, 105) = upper, (55, 55) = lower (P: "upper" = north half on the
  rotated minimap); after landing, each pod counts 30 / 10 s to seismic mode (line, then graph event) and engages.
- **Leviathan arrival / respawn lines** 660 -> 653 -> 662 -> 652 (emerged), respawn 658 / 659 / 663 (60 / 30 / 10 s),
  kill 0x2039 60. Raider lines 696 / 699 / 698, kill 61 / 701 (GD Raider `0x40000938`).
- Wave lines on GD are 672 / 670 / 668 (ics sends 231 / 247 / 233, absent from 0xA0000168).

### 4.3 Coast City v AI (0x40000B6A)

Confirms map-gaps-coast-city.md. Corrections / additions: the "big" camps ics spawns at (80, 145) `0x400007C1` and
(80, 9) `0x40000D60` are **Raiders** (ws 0x2E000F1B, C) and the "boss" `0x40000430` at (80, 57) is the Doomsday
Guardian: they are spawned, but their voices are not (Raider 696 / 699 / 698 / 61 / 701; Guardian kill 0x2039 62;
441 "destroy the Device's defenses" before the Device unlocks). by-map ids 58 / 66 are swapped meanings (1.4).

### 4.4 Gotham Heights v AI (0x40000B6C)

Confirms map-gaps-gotham-heights.md (cannon `0x40000511` = tracker category 27 slot 1, not spawned; 5 points
spawned). Additions: GH's layout pack holds no wave, jungle, turret or Raider line, so only the shared set, the
capture / lost lines (11-14, 16 / 396-400), the cannon (54, 406 / 418 / 419), core % (15 / 17 / 10) and the map title
215 can play on GH.
