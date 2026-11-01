# Non-champion units and AI (static survey, 2026-10-22)

Read-only survey of the player's packs (`rp\*.rp`, 616 packs) and the client exe. Only IDs, short internal names and
numbers are quoted. **C** = confirmed (read from the data or the exe code), **P** = probable (fits all the data, not
checked in game), **?** = unknown.

Map abbreviations (by the packs a class lives in; `ics.gamedata.Data.map_packs`): **T1** Tutorial 1 (0xA000024C /
256 / 257 / 2D6 / 2D7), **CA** Crime Alley + Tutorial 2 + Clashes (0xA00002E5 / 2E6 / 2E7), **GH** Gotham Heights
(0xA000009A / 16B / 179), **GD** Gotham Divided (0xA00000FC / 168 / 16E), **CC** Coast City (0xA00000D2 / 161 / 162).
A pack id in that column means a champion pack (the class belongs to a champion's kit) or the game-data pack 0xA00000B3.

## 0. Summary: what the server can and cannot take from the data

| Topic | In the data? | Where |
|---|---|---|
| Unit classes, model, team, unit flags | yes (C) | template 0x49.. of each 0x40 class (section 1) |
| Base stats and their growth with the unit's level | yes (C) | stat block `0x10000165` -> 0x48 record: fixed f32 stats + `0x1000031A` list of {stat `0x10000100`, formula `0x10000319`} |
| Unit level over match time | yes (C) | `0x100001D9` -> 0x3B: `clamp(floor((Time + 90) / 90), 1, 100)`, i.e. +1 level every 90 s of match time |
| Basic attack | yes (C) | `0x100008E3` table: script `0x10000328` (0x34), stats `0x100004B4` (18 range, 5 damage = formula x attack damage) |
| XP / credits / team bounty on death | yes (C) | `0x10000224` XP, `0x10000689` credits, `0x10000362` team bounty (structures, champions); 0x3B formulas (section 3) |
| On-death extras | yes (C) | `0x8E` scripts (`0x3400007D` drops a pickup for the killer's team, `0x34000670` spawns a collider), `0x10000AC2` kill buff (P) |
| Per-entity script variables | yes (C) | `0xEF` -> 0x3A record (variable declarations only, section 4) |
| **AI parameters** | a few (C) | 0x3A000026 (every minion / jungle unit / structure): `GetBestPerceivedTargetInterval_Min` 0.5 s, `_Max` 0.8 s, `AIActive`; vision radius `0x10000133`; detection list `0x10000A3C` |
| **AI decision logic (target choice, chase, leash, lane walking)** | **no**, for minions / jungle / turrets / bots (C) | it was server engine code. A complete scripted version of the same logic exists (Starro's parasite `0x3400053A`, section 5.3) and is the template to copy |
| Pet / summon AI | yes (C) | their own 0x34 scripts with AIMoveTo / SetAITarget (`0x34000652` Zatanna's Merels, `0x3400053A`) |
| Bot champions | pool + skill levelling only (C) | encounter `0x10000B3E` / `0x10000B41` = `0x340007E2`; champion loadout `0x10000CEB` (skill order, item build); no difficulty data |
| Minion waves, spawn timers, jungle respawn, camp positions | **no** (C) | only client visuals (spawner world state `0x2E000D03`, `_Generator_*` scriptlet keys); must be authored |
| Lane paths | partly (C) | map pack 0x82 type-21 points (maps-encounters.md 2.2); navmesh 0x90 |

## 1. Unit classes

### 1.1 How they were found (C)

Every one of the 2015 entity classes 0x40.. in the packs has a template 0x49.. (same low bits). Templates were read
with `ics.records` plus two reader fixes this survey needed (afterwards 0 failures on the 356 unit templates; 313 of
all 2015 templates still fail on other unknown kinds):

- **String kind 0x0E has a literal form**: `u32 1 | u32 n | n UTF-16 chars padded to 4 bytes | u32 0 | u32 0` (the usual
  form is `u32 0 | token | table | 0 | 0`). Unit names stored this way are developer labels (`Door`, `Rock`, and
  `ERROR - Unnamed Destructible` on every skill projectile).
- **`key | 0x50000000 + (key & 0x0FFFFFFF)`** is an entry without a value (like `key | 0x40000000`).
  `ics.records.Reader.entries` raises "bad key echo" on it today (`Data.unit_stats` skips it by hand). It is common in
  stat blocks and templates (empty formula slots).
- `Data.unit_stats` also stops at the stat block's `0x1000031A` table, so it misses every level-scaled stat (most
  minions' Health, Attack Damage, Attack Armor are only there).

A class is listed when its template has any of `0x10000165` (stat block), `0x1000019D` (unit flags), `0x100008E3`
(basic attack) or `0x10000224` (XP reward) and it is not a champion variant (champions.tsv + roster): **356 classes**.
Groups below come from the unit flags; names are the template's `0x3CE`.

### 1.2 Template properties of units

| Property | Meaning | Values | |
|---|---|---|---|
| `0x510` / `0x50F` | world state / creation type | 7 for every unit | C |
| `0xEF` | per-entity script variables (0x3A) | 0x3A000026 minions, jungle, structures, pads; 0x3A000001 projectiles; 0x3A000010 doors / rocks; champions their own (section 4) | C |
| `0x1000019D` | unit flags (bitfield) | 0x10000 lane / tutorial minion; 0x400 siege (Cannon, Raider Drone, Destroyer Drone); 0x400000 elite / special minion; 0x100 neutral creature (jungle); 0x200 large (with 0x100: Raider, Leviathan, Guardian; with 0x10: turret; with 0x80000: capture point); 0x10 objective structure (0x210 turret, 0x810 dampener, 0x4010 core); 0x4000 core / old foundry turret; 0x80000 capture objective; 0x40000 boss (Guardian); 0x100000 summon / clone (0x110000 pets, 0x120040 deployed sentries); 0x20000 deployable / pad / trap; 0x40 ward-like (surveillance, emitters); 0x20 skill projectile; 0x1000 / 0x1080 destructible prop; 0x2000 door / blocker; 0x4 pickup / collider; 0x2 rock; 0x1 GH Destroyer Drone | C values, P names |
| `0x1000009C` / `0x100007A2` | team / side: 1/3 team 1, 2/5 team 2, 2/1 = team 2 played by the PvE side (tutorial copies) | only on structures; minions and jungle have none (the spawner gives it) | C |
| `0x100006F1` | entity kind | 1 unit / misc, 2 champion, 6 neutral creature, 7 structure / objective | C values, P name |
| `0x10000831` | size / threat class | 1 small jungle and some T1 drones, 2 cannon / elite, 3 soldier / trooper, 4 Joker's head, 5 heavy jungle / destroyer / raider, 6 boss, 7 turret / dampener (6 cores) | C values, P meaning (turret target priority or reward size) |
| `0x10000975` | ? | 100 jungle and CC / GH minions, 40 GD minions, 1 tutorial units, 1..25 per turret | C values |
| `0x10000225` / `0x1000068A` | `RewardTier` input of the XP / credit formula | 3 units, 2 structures, 1 champions | P |
| `0x10000133` | vision (fog) radius | 6 soldier, 7 trooper, 8-9 cannon, 12 watcher, 9 turret, 10-15 core, 6 jungle, 12 champions | C |
| `0x10000A3C` | list of one table {`0x10000133` 3.0, `0x1000019D` 8}: a 3 m detection radius against units with flag 8 | every lane minion | C values, P meaning (reveal range for stealthed units) |
| `0x1000055A` | 1 on every jungle creature and the T1 drones `0x40000B23` / `B24` | camp-bound unit (returns home) | P |
| `0x10000C56` | jungle camp kind: 4 heavy creature, 6 big (Raider, Leviathan, Guardian), 7 buff destroyer; 3 on deployables | | C values, P name |
| `0x100003B0` | 900 units and jungle, 1260 champions, 60 Guardian | ? (a time in s or a squared distance) | C values |
| `0x10000642` | 2.0 melee minions, 4.0 GD trooper / destroyers / raiders, 0.5 turrets, 8 / 26 cores | ? | C values |
| `0x83C` | 2 on every mobile entity (champions too) | movement / path-agent mode (the client creates its Kynapse PathFinder when it is 3; movement-collision-fog-map.md 1.3) | C values, P |
| `0x6B4` | model scale (0.35 Tripod .. 1.0 minion) | | C |
| `0x10000934`, `0x1000025E`, `0x10000419` (0.25), `0x100002D0` (0x10108), `0x10000B4A`, `0x149`, `0x57A`, `0x7EB` | constant per group | ? | C values |
| `0x100004DA` | minimap category: 9 minion, 3 turret / dampener, 30 core, 31 ward-like, 26-28 objectives | | C |
| `0x100001FC`, `0x10000083` | icons (0x13..) | | C |
| `0x1000022F` | 14 damage stages {`0x10000254` health fraction 0.93 .. 0.09, `0x10000174` scriptlet key} on turrets / dampeners, 4 on cores | | C |
| `0x100009BC` | turrets: a status record (0x48000ED4: max stacks 5, flags 0x8000, script `0x340005AB`) | | C refs, P role (turret shot / damage ramp) |
| `0x10000AC2` | big creatures (Leviathan `0x48000E4C`, Raider `0x48000E4B` / `0x48000CCF`, Guardian `0x48000A73`) and the Firing Trigger: a status (max stacks 1, `0x100008A6` -> another 0x48) | | C refs, P role (buff for the killer's team) |
| `0x1000030E`, `0x100009BD`, `0x10000C2A` | pads / emitters / environment: the class they spawn (pickup), the status they apply, their collider | | C refs, P roles |

### 1.3 The units, by group

Columns: stat block and stats at unit level 1 with their per-level growth (`base+delta` = `Base + (Level - 1) x
Delta`, section 3); attack = script, range (stat 18), damage stat 5 (`1x0x3b0002ea` = 1.0 x the unit's attack damage);
XP / credits = formula DID and `Base+Delta/lvl` of the killed unit's level; `grp1.4` = x1.4 when more than one
receiver shares it, then divided by the receivers; `tur/chr/lh` = share when the damage came from a turret / a
champion without the last hit / the last hitter. HP AD AS MS AAr PAr = Health `0x10000426`, Attack Damage `0x10000B76`,
Attack Speed `0x100006FE`, Move Speed `0x100005E4`, Attack Armor `0x10000B84`, Power Armor `0x10000B7A`.
Regenerate: read every 0x49 template with the reader fixes of 1.1, keep the classes above, read the stat block and
evaluate the formulas as in section 3.

#### minion (54)

| Class | Name | Maps / packs | World state | Flags | Team/side | Stat block: level-1 (+per level) | Attack (script, range, damage) | XP `0x10000224` | Credits `0x10000689` | Level `0x100001D9` | Scripts `0x8E` |
|---|---|---|---|---|---|---|---|---|---|---|---|
| `0x4000010a` | Soldier Drone | GD | `0x2e000808` | `0x10000` |  | `0x48000d10`: HP 500+10 AD 11.25+0.9 AS 1 MS 4.2 AAr 5+1 | `0x34000088` r1.5 dmg=1x`0x3b0002ea` | `0x3b000292` 53+5.3/lvl grp1.4 | `0x3b000293` 25+0.5/lvl tur0.25/chr0.5/lh1 | `0x3b00022e` lvl=1+t/90s max 100 |  |
| `0x4000010b` | Trooper Drone | GD | `0x2e000840` | `0x10000` |  | `0x48000d0e`: HP 250+5 AD 18+1.125 AS 1 MS 4.2 AAr 5+1 PAr 5 | `0x34000087` r5 dmg=1x`0x3b0002ea` | `0x3b00028e` 48+4.8/lvl grp1.4 | `0x3b00028f` 20+0.5/lvl tur0.25/chr0.5/lh1 | `0x3b00022e` lvl=1+t/90s max 100 |  |
| `0x4000010d` | Cannon Drone | GD | `0x2e000e21` | `0x10400` |  | `0x48000d0c`: HP 500+10 AD 22.5+1.5 AS 0.75 MS 4.18 AAr 25+2 PAr 10 | `0x34000087` r7.5 dmg=1x`0x3b0002ea` | `0x3b00028a` 65+6.5/lvl grp1.4 | `0x3b00028b` 60+1/lvl tur0.25/chr0.5/lh1 | `0x3b00022e` lvl=1+t/90s max 100 |  |
| `0x4000012d` | Trooper Drone | GH | `0x2e000840` | `0x10000` |  | `0x48001493`: HP 175+2.11 AD 20+1.63 AS 0.45 MS 2.8 AAr 0+1 PAr 10 | `0x340004a0` r4 dmg=1x`0x3b0002ea` | `0x3b0003a0` 35+3.5/lvl grp1.4 | `0x3b0003a2` 30+2/lvl tur0.5/chr0.8/lh1 | `0x3b0003a3` lvl=1+t/90s max 100 |  |
| `0x4000012e` | Soldier Drone | GH | `0x2e000808` | `0x10000` |  | `0x48001494`: HP 325+3.2 AD 22+1.29 AS 0.83 MS 2.8 AAr 0+1 PAr 10 | `0x340004a1` r1.5 dmg=1x`0x3b0002ea` | `0x3b0003a1` 50+5/lvl grp1.4 | `0x3b00039f` 40+2/lvl tur0.5/chr0.8/lh1 | `0x3b0003a3` lvl=1+t/90s max 100 |  |
| `0x400002d4` | Trooper Drone | CC | `0x2e000840` | `0x10000` |  | `0x4800073d`: HP 350+10 AD 20+1.75 AS 0.5 MS 4.2 AAr 0+1 | `0x340004a0` r5 dmg=1x`0x3b0002ea` | `0x3b0001ed` 45+6.75/lvl grp1.4 | `0x3b0001e1` 15+0.9/lvl tur0.35/chr0.7/lh1 | `0x3b0001e9` lvl=1+t/90s max 100 |  |
| `0x400002d5` | Soldier Drone | CC | `0x2e000808` | `0x10000` |  | `0x4800073f`: HP 455+16.5 AD 12+1.25 AS 1 MS 4.2 AAr 0+1 | `0x340004a1` r1.5 dmg=1x`0x3b0002ea` | `0x3b0001ee` 60+9/lvl grp1.4 | `0x3b0001df` 25+1.5/lvl tur0.35/chr0.7/lh1 | `0x3b0001e9` lvl=1+t/90s max 100 |  |
| `0x40000441` | Cannon Drone | CC | `0x2e000e21` | `0x10400` |  | `0x48000776`: HP 650+20 AD 35+3 AS 0.75 MS 4.2 AAr 15+1 | `0x340004a0` r7 dmg=1x`0x3b0002ea` | `0x3b00020c` 65+9.75/lvl grp1.4 | `0x3b00020d` 55+3.3/lvl tur0.35/chr0.7/lh1 | `0x3b0001e9` lvl=1+t/90s max 100 |  |
| `0x40000442` | Elite Trooper | CC | `0x2e000e43` | `0x410000` |  | `0x48000778`: HP 350+40 AD 20+2.5 AS 0.5 MS 4.2 AAr 0+1.5 | `0x340004a0` r5 dmg=1x`0x3b0002ea` | `0x3b0001ed` 45+6.75/lvl grp1.4 | `0x3b0001e1` 15+0.9/lvl tur0.35/chr0.7/lh1 | `0x3b0001e9` lvl=1+t/90s max 100 |  |
| `0x40000443` | Elite Soldier | CC | `0x2e000e3e` | `0x410000` |  | `0x48000779`: HP 455+60 AD 12+2 AS 1 MS 4.2 AAr 0+1.5 | `0x340004a1` r1.5 dmg=1x`0x3b0002ea` | `0x3b0001ee` 60+9/lvl grp1.4 | `0x3b0001df` 25+1.5/lvl tur0.35/chr0.7/lh1 | `0x3b0001e9` lvl=1+t/90s max 100 |  |
| `0x40000941` | Elite Trooper | GD | `0x2e000e43` | `0x410000` |  | `0x48000d0d`: HP 327.5+15 AD 26+2.25 AS 1 MS 4.2 AAr 5+1 PAr 20 | `0x34000087` r5 dmg=1x`0x3b0002ea` | `0x3b00028e` 48+4.8/lvl grp1.4 | `0x3b00028f` 20+0.5/lvl tur0.25/chr0.5/lh1 | `0x3b00022e` lvl=1+t/90s max 100 |  |
| `0x40000942` | Elite Soldier | GD | `0x2e000e3e` | `0x410000` |  | `0x48000d0f`: HP 655+20 AD 18+1.8 AS 1 MS 4.2 AAr 5+1 | `0x34000088` r1.5 dmg=1x`0x3b0002ea` | `0x3b000292` 53+5.3/lvl grp1.4 | `0x3b000293` 25+0.5/lvl tur0.25/chr0.5/lh1 | `0x3b00022e` lvl=1+t/90s max 100 |  |
| `0x40000a5c` | Soldier Drone | T1 | `0x2e000808` | `0x10000` |  | `0x48000e85`: HP 170 AD 6 AS 1 MS 3 | `0x34000088` r1.5 dmg=1x`0x3b0002ea` | `0x3b0002d6` 115+0/lvl (flat) |  |  |  |
| `0x40000a5d` | Trooper Drone | T1 | `0x2e000840` | `0x10000` |  | `0x48000e84`: HP 140 AD 8 AS 0.5 MS 3 | `0x34000087` r5 dmg=1x`0x3b0002ea` | `0x3b0002d7` 100+0/lvl (flat) |  |  |  |
| `0x40000b23` | Trooper Drone | T1 | `0x2e000840` | `0x10000` |  | `0x48000f70`: HP 150 AD 10 AS 0.5 MS 3 | `0x34000087` r5 dmg=1x`0x3b0002ea` | `0x3b0002d7` 100+0/lvl (flat) | `0x3b0000ce` 4*KillerLvl/N | `0x3b000287` lvl=1+t/90s max 100 |  |
| `0x40000b24` | Soldier Drone | T1 | `0x2e000808` | `0x10000` |  | `0x48000f71`: HP 170 AD 8 AS 1 MS 3 | `0x34000088` r1.5 dmg=1x`0x3b0002ea` | `0x3b0002d6` 115+0/lvl (flat) | `0x3b0000ce` 4*KillerLvl/N | `0x3b000287` lvl=1+t/90s max 100 |  |
| `0x40000ba9` | Practice Target | T1 | `0x2e001298` | `0x10000` |  | `0x48000f6f`: HP 1 |  | `0x3b00033c` 0+0/lvl (flat) |  |  | `0x34000600` |
| `0x40000bc1` | Trooper Drone | CA | `0x2e000840` | `0x10000` |  | `0x48000f76`: HP 350 AD 20 AS 0.5 MS 2.5 | `0x34000087` r5 dmg=1x`0x3b0002ea` | `0x3b0002d7` 100+0/lvl (flat) |  |  |  |
| `0x40000bc2` | Soldier Drone | CA | `0x2e000808` | `0x10000` |  | `0x48000f86`: HP 155 AD 3 AS 1 MS 3 | `0x34000088` r1.5 dmg=1x`0x3b0002ea` | `0x3b0002d6` 115+0/lvl (flat) | `0x3b0001df` 25+1.5/lvl tur0.35/chr0.7/lh1 |  |  |
| `0x40000bc3` | Cannon Drone | CA | `0x2e000e21` | `0x10000` |  | `0x48000f84`: HP 185 AD 6 AS 0.6 MS 3 | `0x34000087` r7.5 dmg=1x`0x3b0002ea` | `0x3b0002d6` 115+0/lvl (flat) | `0x3b00020d` 55+3.3/lvl tur0.35/chr0.7/lh1 |  |  |
| `0x40000bc4` | Trooper Drone | CA | `0x2e000840` | `0x10000` |  | `0x48000f76`: HP 350 AD 20 AS 0.5 MS 2.5 | `0x34000087` r5 dmg=1x`0x3b0002ea` | `0x3b0002d7` 100+0/lvl (flat) | `0x3b0001e1` 15+0.9/lvl tur0.35/chr0.7/lh1 |  |  |
| `0x40000bc5` | Soldier Drone | CA | `0x2e000808` | `0x10000` |  | `0x48000f77`: HP 455 AD 12 AS 1 MS 2.5 | `0x34000088` r1.5 dmg=1x`0x3b0002ea` | `0x3b0002d6` 115+0/lvl (flat) |  |  |  |
| `0x40000bc6` | Cannon Drone | CA | `0x2e000e21` | `0x10000` |  | `0x48000f79`: HP 500 AD 30 AS 0.6 MS 2.5 AAr 25 | `0x34000087` r7.5 dmg=1x`0x3b0002ea` | `0x3b0002d6` 115+0/lvl (flat) |  |  |  |
| `0x40000bc7` | Soldier Drone | CA | `0x2e000808` | `0x10000` |  | `0x48000f77`: HP 455 AD 12 AS 1 MS 2.5 | `0x34000088` r1.5 dmg=1x`0x3b0002ea` | `0x3b0002d6` 115+0/lvl (flat) | `0x3b0001df` 25+1.5/lvl tur0.35/chr0.7/lh1 |  |  |
| `0x40000bc8` | Cannon Drone | CA | `0x2e000e21` | `0x10000` |  | `0x48000f79`: HP 500 AD 30 AS 0.6 MS 2.5 AAr 25 | `0x34000087` r7.5 dmg=1x`0x3b0002ea` | `0x3b0002d6` 115+0/lvl (flat) | `0x3b00020d` 55+3.3/lvl tur0.35/chr0.7/lh1 |  |  |
| `0x40000bc9` | Trooper Drone | CA | `0x2e000840` | `0x10000` |  | `0x48000f85`: HP 135 AD 4 AS 0.8 MS 3 | `0x34000087` r5 dmg=1x`0x3b0002ea` | `0x3b0002d7` 100+0/lvl (flat) | `0x3b0001e1` 15+0.9/lvl tur0.35/chr0.7/lh1 |  |  |
| `0x40000bf8` | Soldier Drone | CA | `0x2e000808` | `0x10000` |  | `0x4800073f`: HP 455+16.5 AD 12+1.25 AS 1 MS 4.2 AAr 0+1 | `0x340004a1` r1.5 dmg=1x`0x3b0002ea` | `0x3b0001ee` 60+9/lvl grp1.4 | `0x3b0001df` 25+1.5/lvl tur0.35/chr0.7/lh1 | `0x3b0001e9` lvl=1+t/90s max 100 |  |
| `0x40000bf9` | Cannon Drone | CA | `0x2e000e21` | `0x10400` |  | `0x48000776`: HP 650+20 AD 35+3 AS 0.75 MS 4.2 AAr 15+1 | `0x340004a0` r7 dmg=1x`0x3b0002ea` | `0x3b00020c` 65+9.75/lvl grp1.4 | `0x3b00020d` 55+3.3/lvl tur0.35/chr0.7/lh1 | `0x3b0001e9` lvl=1+t/90s max 100 |  |
| `0x40000bfa` | Trooper Drone | CA | `0x2e000840` | `0x10000` |  | `0x4800073d`: HP 350+10 AD 20+1.75 AS 0.5 MS 4.2 AAr 0+1 | `0x340004a0` r5 dmg=1x`0x3b0002ea` | `0x3b0001ed` 45+6.75/lvl grp1.4 | `0x3b0001e1` 15+0.9/lvl tur0.35/chr0.7/lh1 | `0x3b0001e9` lvl=1+t/90s max 100 |  |
| `0x40000c45` | Trooper Drone | CC | `0x2e000840` | `0x10000` |  | `0x4800073d`: HP 350+10 AD 20+1.75 AS 0.5 MS 4.2 AAr 0+1 | `0x340004a0` r5 dmg=1x`0x3b0002ea` | `0x3b0001ed` 45+6.75/lvl grp1.4 | `0x3b0001e1` 15+0.9/lvl tur0.35/chr0.7/lh1 | `0x3b0001e9` lvl=1+t/90s max 100 |  |
| `0x40000c46` | Soldier Drone | CC | `0x2e000808` | `0x10000` |  | `0x4800073f`: HP 455+16.5 AD 12+1.25 AS 1 MS 4.2 AAr 0+1 | `0x340004a1` r1.5 dmg=1x`0x3b0002ea` | `0x3b0001ee` 60+9/lvl grp1.4 | `0x3b0001df` 25+1.5/lvl tur0.35/chr0.7/lh1 | `0x3b0001e9` lvl=1+t/90s max 100 |  |
| `0x40000c47` | Trooper Drone | CC | `0x2e000840` | `0x10000` |  | `0x4800073d`: HP 350+10 AD 20+1.75 AS 0.5 MS 4.2 AAr 0+1 | `0x340004a0` r5 dmg=1x`0x3b0002ea` | `0x3b0001ed` 45+6.75/lvl grp1.4 | `0x3b0001e1` 15+0.9/lvl tur0.35/chr0.7/lh1 | `0x3b0001e9` lvl=1+t/90s max 100 |  |
| `0x40000c48` | Soldier Drone | CC | `0x2e000808` | `0x10000` |  | `0x4800073f`: HP 455+16.5 AD 12+1.25 AS 1 MS 4.2 AAr 0+1 | `0x340004a1` r1.5 dmg=1x`0x3b0002ea` | `0x3b0001ee` 60+9/lvl grp1.4 | `0x3b0001df` 25+1.5/lvl tur0.35/chr0.7/lh1 | `0x3b0001e9` lvl=1+t/90s max 100 |  |
| `0x40000c71` | Stabber | T1 | `0x2e0012bb` | `0x10000` |  | `0x480010ea`: HP 200 AD 10 AS 1 MS 3 | `0x340004a1` r1.5 dmg=1x`0x3b0002ea` | `0x3b0002d6` 115+0/lvl (flat) |  |  |  |
| `0x40000c72` | Soldier Drone | T1 | `0x2e001167` | `0x10000` |  | `0x480010ea`: HP 200 AD 10 AS 1 MS 3 | `0x340004a1` r1.5 dmg=1x`0x3b0002ea` | `0x3b0002d6` 115+0/lvl (flat) |  |  |  |
| `0x40000c9a` | Soldier Drone | CA | `0x2e000808` | `0x10000` |  | `0x4800073f`: HP 455+16.5 AD 12+1.25 AS 1 MS 4.2 AAr 0+1 | `0x340004a1` r1.5 dmg=1x`0x3b0002ea` | `0x3b0001ee` 60+9/lvl grp1.4 | `0x3b0001df` 25+1.5/lvl tur0.35/chr0.7/lh1 | `0x3b0001e9` lvl=1+t/90s max 100 |  |
| `0x40000c9b` | Elite Trooper | CA | `0x2e000e43` | `0x410000` |  | `0x48000778`: HP 350+40 AD 20+2.5 AS 0.5 MS 4.2 AAr 0+1.5 | `0x340004a0` r5 dmg=1x`0x3b0002ea` | `0x3b0001ed` 45+6.75/lvl grp1.4 | `0x3b0001e1` 15+0.9/lvl tur0.35/chr0.7/lh1 | `0x3b0001e9` lvl=1+t/90s max 100 |  |
| `0x40000c9c` | Elite Soldier | CA | `0x2e000e3e` | `0x410000` |  | `0x48000779`: HP 455+60 AD 12+2 AS 1 MS 4.2 AAr 0+1.5 | `0x340004a1` r1.5 dmg=1x`0x3b0002ea` | `0x3b0001ee` 60+9/lvl grp1.4 | `0x3b0001df` 25+1.5/lvl tur0.35/chr0.7/lh1 | `0x3b0001e9` lvl=1+t/90s max 100 |  |
| `0x40000c9d` | Trooper Drone | CA | `0x2e000840` | `0x10000` |  | `0x4800073d`: HP 350+10 AD 20+1.75 AS 0.5 MS 4.2 AAr 0+1 | `0x340004a0` r5 dmg=1x`0x3b0002ea` | `0x3b0001ed` 45+6.75/lvl grp1.4 | `0x3b0001e1` 15+0.9/lvl tur0.35/chr0.7/lh1 | `0x3b0001e9` lvl=1+t/90s max 100 |  |
| `0x40000c9e` | Cannon Drone | CA | `0x2e000e21` | `0x10400` |  | `0x48000776`: HP 650+20 AD 35+3 AS 0.75 MS 4.2 AAr 15+1 | `0x340004a0` r7 dmg=1x`0x3b0002ea` | `0x3b00020c` 65+9.75/lvl grp1.4 | `0x3b00020d` 55+3.3/lvl tur0.35/chr0.7/lh1 | `0x3b0001e9` lvl=1+t/90s max 100 |  |
| `0x40000d23` | Raider Drone | CC | `0x2e000f1b` | `0x10400` |  | `0x4800129a`: HP 2000+150 AD 60+6 AS 1 MS 2 AAr 20 PAr 20 | `0x34000512` r10 dmg=1x`0x3b0002ea` | `0x3b000359` 500+0/lvl grp1 | `0x3b00035a` 250+10/lvl tur0.25/chr0.5/lh1 | `0x3b0001e9` lvl=1+t/90s max 100 |  |
| `0x40000d5c` | Destroyer Drone | CC | `0x2e000ab5` | `0x10400` |  | `0x48001304`: HP 1500+120 AD 40+2 AS 0.59 MS 2 AAr 20 PAr 15 | `0x340004a1` r1.5 dmg=1x`0x3b0002ea` | `0x3b000369` 200+16/lvl grp1.4 | `0x3b00036a` 150+3.75/lvl tur0.25/chr0.5/lh1 | `0x3b0001e9` lvl=1+t/90s max 100 |  |
| `0x40000e5f` | Destroyer Drone | GD | `0x2e000ab5` | `0x410000` |  | `0x48001419`: HP 1425+95 AD 40+3 AS 1 MS 4.2 | `0x340007af` r3 dmg=1x`0x3b0002ea` | `0x3b00028a` 65+6.5/lvl grp1.4 | `0x3b00028b` 60+1/lvl tur0.25/chr0.5/lh1 | `0x3b00022e` lvl=1+t/90s max 100 |  |
| `0x40000e63` | Elite Trooper | CA | `0x2e000e43` | `0x410000` |  | `0x48000778`: HP 350+40 AD 20+2.5 AS 0.5 MS 4.2 AAr 0+1.5 | `0x340004a0` r5 dmg=1x`0x3b0002ea` | `0x3b0001ed` 45+6.75/lvl grp1.4 | `0x3b0001e1` 15+0.9/lvl tur0.35/chr0.7/lh1 | `0x3b0001e9` lvl=1+t/90s max 100 |  |
| `0x40000e64` | Elite Soldier | CA | `0x2e000e3e` | `0x410000` |  | `0x48000779`: HP 455+60 AD 12+2 AS 1 MS 4.2 AAr 0+1.5 | `0x340004a1` r1.5 dmg=1x`0x3b0002ea` | `0x3b0001ee` 60+9/lvl grp1.4 | `0x3b0001df` 25+1.5/lvl tur0.35/chr0.7/lh1 | `0x3b0001e9` lvl=1+t/90s max 100 |  |
| `0x40000e79` | Soldier Drone | CA | `0x2e000808` | `0x10000` |  | `0x4800073f`: HP 455+16.5 AD 12+1.25 AS 1 MS 4.2 AAr 0+1 | `0x340004a1` r1.5 dmg=1x`0x3b0002ea` | `0x3b0001ee` 60+9/lvl grp1.4 | `0x3b000399` 50+0.5/lvl tur0.25/chr0.5/lh1 | `0x3b0001e9` lvl=1+t/90s max 100 |  |
| `0x40000e7a` | Trooper Drone | CA | `0x2e000840` | `0x10000` |  | `0x4800073d`: HP 350+10 AD 20+1.75 AS 0.5 MS 4.2 AAr 0+1 | `0x340004a0` r5 dmg=1x`0x3b0002ea` | `0x3b0001ed` 45+6.75/lvl grp1.4 | `0x3b000398` 50+0.5/lvl tur0.25/chr0.5/lh1 | `0x3b0001e9` lvl=1+t/90s max 100 |  |
| `0x40000e7c` | Elite Trooper | CA | `0x2e000e43` | `0x410000` |  | `0x48000778`: HP 350+40 AD 20+2.5 AS 0.5 MS 4.2 AAr 0+1.5 | `0x340004a0` r5 dmg=1x`0x3b0002ea` | `0x3b0001ed` 45+6.75/lvl grp1.4 | `0x3b000398` 50+0.5/lvl tur0.25/chr0.5/lh1 | `0x3b0001e9` lvl=1+t/90s max 100 |  |
| `0x40000e7f` | Cannon Drone | CA | `0x2e000e21` | `0x10400` |  | `0x48000776`: HP 650+20 AD 35+3 AS 0.75 MS 4.2 AAr 15+1 | `0x340004a0` r7 dmg=1x`0x3b0002ea` | `0x3b00020c` 65+9.75/lvl grp1.4 | `0x3b00039a` 100+0.5/lvl tur0.25/chr0.5/lh1 | `0x3b0001e9` lvl=1+t/90s max 100 |  |
| `0x40000e81` | Elite Soldier | CA | `0x2e000e3e` | `0x410000` |  | `0x48000779`: HP 455+60 AD 12+2 AS 1 MS 4.2 AAr 0+1.5 | `0x340004a1` r1.5 dmg=1x`0x3b0002ea` | `0x3b0001ee` 60+9/lvl grp1.4 | `0x3b000399` 50+0.5/lvl tur0.25/chr0.5/lh1 | `0x3b0001e9` lvl=1+t/90s max 100 |  |
| `0x40000eaa` | Destroyer Drone | GH | `0x2e000ab5` | `0x10001` |  | `0x48001495`: HP 1500+52.632 AD 60+2.1053 AS 0.59 MS 3.25 AAr 20+1.0526 PAr 15 | `0x340004a1` r1.5 dmg=1x`0x3b0002ea` | `0x3b0003a1` 50+5/lvl grp1.4 | `0x3b00039f` 40+2/lvl tur0.5/chr0.8/lh1 | `0x3b0003a3` lvl=1+t/90s max 100 |  |
| `0x40000eb2` | Destroyer Drone | T1 | `0x2e000ab5` | `0x10000` |  | `0x480014b4`: HP 1500 AD 45 AS 0.59 MS 3 AAr 2 | `0x3400058f` r1.5 dmg=1x`0x3b0002ea` | `0x3b0002d6` 115+0/lvl (flat) |  |  |  |
| `0x40000eb4` | Soldier Drone | T1 | `0x2e000808` | `0x10000` |  | `0x48000e85`: HP 170 AD 6 AS 1 MS 3 | `0x34000088` r1.5 dmg=1x`0x3b0002ea` | `0x3b0002d6` 115+0/lvl (flat) |  |  | `0x34000600` |
| `0x40000eb5` | Watcher Drone | CA | `0x2e001298` | `0x10000` |  | `0x480014b7`: HP 2 AS 0.75 MS 3 |  | `0x3b00033c` 0+0/lvl (flat) |  |  | `0x34000600` |

#### jungle (35)

| Class | Name | Maps / packs | World state | Flags | Team/side | Stat block: level-1 (+per level) | Attack (script, range, damage) | XP `0x10000224` | Credits `0x10000689` | Level `0x100001D9` | Scripts `0x8E` |
|---|---|---|---|---|---|---|---|---|---|---|---|
| `0x40000430` | Doomsday Guardian | CC | `0x2e0010b1` | `0x40301` |  | `0x48000740`: HP 1750+500 AD 80+8 AS 0.6 AAr 45 PAr 45 | `0x34000442` r9 dmg=1x`0x3b0002ea` | `0x3b0001f0` 800+0/lvl grp1 | `0x3b0001ef` 100+45/lvl clamped | `0x3b0001e8` lvl=1+t/90s max 100 |  |
| `0x400007c1` | Raider | CC | `0x2e000f1b` | `0x300` |  | `0x48000a45`: HP 2000+150 AD 60+6 AS 1 MS 3.25 AAr 20 PAr 20 | `0x34000512` r5 dmg=1x`0x3b0002ea` | `0x3b000253` 500+0/lvl grp1 | `0x3b000254` 0+45/lvl clamped | `0x3b0001e8` lvl=1+t/90s max 100 |  |
| `0x40000893` | Destroyer | CC | `0x2e000ab5` | `0x100` |  | `0x48000c7a`: HP 1225+90 AD 40+2 AS 0.59 MS 3.25 AAr 20 PAr 15 | `0x340004a1` r1.5 dmg=1x`0x3b0002ea` | `0x3b00027d` 150+18/lvl grp1.4 | `0x3b00027e` 150+12/lvl | `0x3b0001e8` lvl=1+t/90s max 100 | `0x3400007d` |
| `0x40000894` | Heavy Tripod | CC | `0x2e000be2` | `0x100` |  | `0x48000c75`: HP 725+20 AD 20+0.5 AS 0.65 MS 3 AAr 15 PAr 10 | `0x340004a0` r5 dmg=1x`0x3b0002ea` | `0x3b000269` 85+10.2/lvl grp1.4 | `0x3b00026a` 20+1.6/lvl | `0x3b0001e8` lvl=1+t/90s max 100 | `0x3400007d` |
| `0x40000895` | Heavy Scrapper | CC | `0x2e000e57` | `0x100` |  | `0x48000c77`: HP 700+27 AD 20+0.5 AS 0.83 MS 3.25 AAr 9 PAr 5 | `0x340004a1` r1.5 dmg=1x`0x3b0002ea` | `0x3b000271` 100+12/lvl grp1.4 | `0x3b000272` 25+2/lvl | `0x3b0001e8` lvl=1+t/90s max 100 | `0x3400007d` |
| `0x40000896` | Heavy Mauler | CC | `0x2e000e20` | `0x100` |  | `0x48000c79`: HP 825+47 AD 25+0.75 AS 0.83 MS 2.75 AAr 12 PAr -10 | `0x340004a1` r1.5 dmg=1x`0x3b0002ea` | `0x3b000279` 110+13.2/lvl grp1.4 | `0x3b00027a` 35+2.8/lvl | `0x3b0001e8` lvl=1+t/90s max 100 | `0x3400007d` |
| `0x40000897` | Mauler | CC | `0x2e000e20` | `0x100` |  | `0x48000c78`: HP 225+22 AD 15+0.5 AS 0.83 MS 2.75 AAr 12 PAr -10 | `0x340004a1` r1.5 dmg=1x`0x3b0002ea` | `0x3b000275` 11+1.32/lvl grp1.4 | `0x3b000276` 8+0.64/lvl | `0x3b0001e8` lvl=1+t/90s max 100 |  |
| `0x40000898` | Tripod | CC | `0x2e000be2` | `0x100` |  | `0x48000c74`: HP 200+12 AD 15+0.66 AS 0.65 MS 3 AAr 8 PAr 5 | `0x340004a0` r5 dmg=1x`0x3b0002ea` | `0x3b000265` 20+2.4/lvl grp1.4 | `0x3b000266` 6+0.48/lvl | `0x3b0001e8` lvl=1+t/90s max 100 |  |
| `0x40000899` | Scrapper | CC | `0x2e000e57` | `0x100` |  | `0x48000c76`: HP 175+18 AD 10+0.33 AS 0.83 MS 3.25 AAr 6 PAr 5 | `0x340004a1` r1.5 dmg=1x`0x3b0002ea` | `0x3b00026d` 10+1.2/lvl grp1.4 | `0x3b00026e` 5+0.4/lvl | `0x3b0001e8` lvl=1+t/90s max 100 |  |
| `0x4000089a` | Tripod | CC | `0x2e000be2` | `0x100` |  | `0x48000c73`: HP 150+13 AD 7.5+0.33 AS 0.65 MS 3.25 AAr 5 PAr 5 | `0x340004a0` r5 dmg=1x`0x3b0002ea` | `0x3b000261` 8+0.96/lvl grp1.4 | `0x3b000262` 3+0.24/lvl | `0x3b0001e8` lvl=1+t/90s max 100 |  |
| `0x40000935` | Tripod | GD | `0x2e000be2` | `0x100` |  | `0x48000d11`: HP 150+13 AD 8+0.5 AS 0.65 MS 3 AAr 5 PAr 5 | `0x34000087` r5 dmg=1x`0x3b0002ea` | `0x3b000294` 9+1.5/lvl grp1.4 | `0x3b000295` 3+1/lvl tur0.25/chr0.5/lh1 | `0x3b00022f` lvl=1+t/90s max 100 |  |
| `0x40000936` | Scrapper | GD | `0x2e000e57` | `0x100` |  | `0x48000d14`: HP 175+18 AD 10+0.5 AS 0.83 MS 3 AAr 6 PAr 5 | `0x34000088` r1.5 dmg=1x`0x3b0002ea` | `0x3b0002a0` 10+2/lvl grp1.4 | `0x3b0002a1` 5+1/lvl tur0.25/chr0.5/lh1 | `0x3b00022f` lvl=1+t/90s max 100 |  |
| `0x40000937` | Leviathan | GD | `0x2e000fa5` | `0x300` |  | `0x48000d1a`: HP 5000+215 AD 220 AS 0.83 MS 3 AAr 110 PAr 50 | `0x3400057b` r15 dmg=1x`0x3b0002ea` | `0x3b0002b5` 2000+20/lvl grp1.4 | `0x3b0000ce` 4*KillerLvl/N | `0x3b00000d` lvl=1+t/90s max 100 |  |
| `0x40000938` | Raider | GD | `0x2e000f1b` | `0x300` |  | `0x48000d17`: HP 2200+240 AD 185 AS 0.65 MS 3 AAr 20 PAr 30 | `0x34000512` r15 dmg=1x`0x3b0002ea` | `0x3b0002a8` 600+15/lvl grp1.4 | `0x3b0002a9` 85+10/lvl tur0.5/chr1/lh1 clamped | `0x3b00000d` lvl=1+t/90s max 100 |  |
| `0x40000939` | Heavy Tripod | GD | `0x2e000be2` | `0x100` |  | `0x48000d13`: HP 725+20 AD 20+1 AS 0.65 MS 3 AAr 15 PAr 10 | `0x34000087` r5 dmg=1x`0x3b0002ea` | `0x3b00029c` 90+3.5/lvl grp1.4 | `0x3b00029d` 16+1.5/lvl tur0.25/chr0.5/lh1 | `0x3b00022f` lvl=1+t/90s max 100 | `0x3400007d` |
| `0x4000093a` | Mauler | GD | `0x2e000e20` | `0x100` |  | `0x48000d18`: HP 225+22 AD 18+1 AS 0.83 MS 3 AAr 12 PAr -10 | `0x34000088` r1.5 dmg=1x`0x3b0002ea` | `0x3b0002ad` 25+5/lvl grp1.4 | `0x3b0002ae` 8+1/lvl tur0.25/chr0.5/lh1 | `0x3b00022f` lvl=1+t/90s max 100 |  |
| `0x4000093b` | Tripod | GD | `0x2e000be2` | `0x100` |  | `0x48000d12`: HP 200+12 AD 16+1 AS 0.65 MS 3 AAr 8 PAr 5 | `0x34000087` r5 dmg=1x`0x3b0002ea` | `0x3b000298` 13.5+2/lvl grp1.4 | `0x3b000299` 6+1/lvl tur0.25/chr0.5/lh1 | `0x3b00022f` lvl=1+t/90s max 100 |  |
| `0x4000093c` | Heavy Scrapper | GD | `0x2e000e57` | `0x100` |  | `0x48000d15`: HP 800+40 AD 25+3 AS 0.83 MS 3 AAr 9 PAr 5 | `0x34000088` r1.5 dmg=1x`0x3b0002ea` | `0x3b0002a4` 100+4.5/lvl grp1.4 | `0x3b0002a5` 20+1.5/lvl tur0.25/chr0.5/lh1 | `0x3b00022f` lvl=1+t/90s max 100 | `0x3400007d` |
| `0x4000093d` | Haste Destroyer | GD | `0x2e001092` | `0x100` |  | `0x48000d1b`: HP 1425+95 AD 35+4.5 AS 0.41 MS 3 AAr 20 PAr 15 | `0x34000088` r1.5 dmg=1x`0x3b0002ea` | `0x3b0002b9` 180+9/lvl grp1.4 | `0x3b0002c3` 80+1.5/lvl tur0.25/chr0.5/lh1 | `0x3b00022f` lvl=1+t/90s max 100 | `0x3400051b` |
| `0x4000093e` | Heavy Mauler | GD | `0x2e000e20` | `0x100` |  | `0x48000d19`: HP 950+50 AD 35+1.5 AS 0.83 MS 3 AAr 12 PAr -10 | `0x34000088` r1.5 dmg=1x`0x3b0002ea` | `0x3b0002b1` 125+5/lvl grp1.4 | `0x3b0002b2` 24+1.5/lvl tur0.25/chr0.5/lh1 | `0x3b00022f` lvl=1+t/90s max 100 | `0x3400007d` |
| `0x4000093f` | Surveillance Destroyer | GD | `0x2e000ab5` | `0x400100` |  | `0x48000d1d`: HP 1425+95 AD 40+3 AS 0.59 MS 3 AAr 15 PAr 10 | `0x340004a1` r2.5 dmg=1x`0x3b0002ea` | `0x3b0002bf` 110+4/lvl grp1.4 | `0x3b0002c0` 40+1/lvl tur0.25/chr0.5/lh1 | `0x3b00022f` lvl=1+t/90s max 100 |  |
| `0x40000940` | Regen Destroyer | GD | `0x2e0010a7` | `0x100` |  | `0x48000d1c`: HP 1425+95 AD 28+5.5 AS 0.59 MS 3 AAr 15 PAr 10 | `0x34000088` r1.5 dmg=1x`0x3b0002ea` | `0x3b0002bc` 180+9/lvl grp1.4 | `0x3b0002c4` 80+1.5/lvl tur0.25/chr0.5/lh1 | `0x3b00022f` lvl=1+t/90s max 100 | `0x3400051a` |
| `0x40000a61` | Heavy Tripod | CA | `0x2e000be2` | `0x100` |  | `0x48000d13`: HP 725+20 AD 20+1 AS 0.65 MS 3 AAr 15 PAr 10 | `0x34000087` r5 dmg=1x`0x3b0002ea` | `0x3b00029c` 90+3.5/lvl grp1.4 | `0x3b00029d` 16+1.5/lvl tur0.25/chr0.5/lh1 | `0x3b00022f` lvl=1+t/90s max 100 | `0x3400007d` |
| `0x40000a64` | Tripod | CA | `0x2e000be2` | `0x100` |  | `0x480010d0`: HP 150+13 AD 5+0.33 AS 0.65 MS 3.25 AAr 5 PAr 5 | `0x34000087` r5 dmg=1x`0x3b0002ea` | `0x3b000294` 9+1.5/lvl grp1.4 | `0x3b000295` 3+1/lvl tur0.25/chr0.5/lh1 | `0x3b00022f` lvl=1+t/90s max 100 |  |
| `0x40000a71` | Raider | CA | `0x2e000f1b` | `0x100` |  | `0x480010d2`: HP 1500+75 AD 40+3 AS 1 MS 3.25 AAr 20 PAr 20 | `0x34000512` r5 dmg=1x`0x3b0002ea` | `0x3b000253` 500+0/lvl grp1 | `0x3b000254` 0+45/lvl clamped | `0x3b0001e8` lvl=1+t/90s max 100 | `0x34000670` |
| `0x40000c6c` | Raider | CA | `0x2e000f1b` | `0x100` |  | `0x480010cf`: HP 750 AD 25 AS 1 MS 3.25 AAr 20 PAr 20 | `0x34000512` r5 dmg=1x`0x3b0002ea` | `0x3b000253` 500+0/lvl grp1 | `0x3b000254` 0+45/lvl clamped | `0x3b0001e8` lvl=1+t/90s max 100 | `0x34000670` |
| `0x40000ca0` | Tripod | CA | `0x2e000be2` | `0x100` |  | `0x48000c73`: HP 150+13 AD 7.5+0.33 AS 0.65 MS 3.25 AAr 5 PAr 5 | `0x340004a0` r5 dmg=1x`0x3b0002ea` | `0x3b000261` 8+0.96/lvl grp1.4 | `0x3b000262` 3+0.24/lvl | `0x3b0001e8` lvl=1+t/90s max 100 |  |
| `0x40000ca1` | Heavy Tripod | CA | `0x2e000be2` | `0x100` |  | `0x48000c75`: HP 725+20 AD 20+0.5 AS 0.65 MS 3 AAr 15 PAr 10 | `0x340004a0` r5 dmg=1x`0x3b0002ea` | `0x3b000269` 85+10.2/lvl grp1.4 | `0x3b00026a` 20+1.6/lvl | `0x3b0001e8` lvl=1+t/90s max 100 | `0x3400007d` |
| `0x40000ca2` | Raider | CA | `0x2e000f1b` | `0x100` |  | `0x480010d2`: HP 1500+75 AD 40+3 AS 1 MS 3.25 AAr 20 PAr 20 | `0x34000512` r5 dmg=1x`0x3b0002ea` | `0x3b000253` 500+0/lvl grp1 | `0x3b000254` 0+45/lvl clamped | `0x3b0001e8` lvl=1+t/90s max 100 | `0x34000670` |
| `0x40000cda` | Regen Destroyer | CA | `0x2e0010a7` | `0x100` |  | `0x48000d1c`: HP 1425+95 AD 28+5.5 AS 0.59 MS 3 AAr 15 PAr 10 | `0x34000088` r1.5 dmg=1x`0x3b0002ea` | `0x3b0002bc` 180+9/lvl grp1.4 | `0x3b0002c4` 80+1.5/lvl tur0.25/chr0.5/lh1 | `0x3b00022f` lvl=1+t/90s max 100 |  |
| `0x40000d60` | Raider | CC | `0x2e000f1b` | `0x300` |  | `0x48000a45`: HP 2000+150 AD 60+6 AS 1 MS 3.25 AAr 20 PAr 20 | `0x34000512` r5 dmg=1x`0x3b0002ea` | `0x3b000253` 500+0/lvl grp1 | `0x3b000254` 0+45/lvl clamped | `0x3b0001e8` lvl=1+t/90s max 100 |  |
| `0x40000d62` | Destroyer | CC | `0x2e000ab5` | `0x100` |  | `0x48000c7a`: HP 1225+90 AD 40+2 AS 0.59 MS 3.25 AAr 20 PAr 15 | `0x340004a1` r1.5 dmg=1x`0x3b0002ea` | `0x3b00027d` 150+18/lvl grp1.4 | `0x3b00027e` 150+12/lvl | `0x3b0001e8` lvl=1+t/90s max 100 |  |
| `0x40000e7d` | Heavy Tripod | CA | `0x2e000be2` | `0x100` |  | `0x48000d13`: HP 725+20 AD 20+1 AS 0.65 MS 3 AAr 15 PAr 10 | `0x34000087` r5 dmg=1x`0x3b0002ea` | `0x3b00029c` 90+3.5/lvl grp1.4 | `0x3b000397` 50+10/lvl tur0.25/chr0.5/lh1 | `0x3b00022f` lvl=1+t/90s max 100 | `0x3400007d` |
| `0x40000e7e` | Tripod | CA | `0x2e000be2` | `0x100` |  | `0x480010d0`: HP 150+13 AD 5+0.33 AS 0.65 MS 3.25 AAr 5 PAr 5 | `0x34000087` r5 dmg=1x`0x3b0002ea` | `0x3b000294` 9+1.5/lvl grp1.4 | `0x3b000396` 25+5/lvl tur0.25/chr0.5/lh1 | `0x3b00022f` lvl=1+t/90s max 100 |  |
| `0x40000e83` | Regen Destroyer | CA | `0x2e0010a7` | `0x100` |  | `0x48000d1c`: HP 1425+95 AD 28+5.5 AS 0.59 MS 3 AAr 15 PAr 10 | `0x34000088` r1.5 dmg=1x`0x3b0002ea` | `0x3b0002bc` 180+9/lvl grp1.4 | `0x3b000395` 200+5/lvl tur0.25/chr0.5/lh1 | `0x3b00022f` lvl=1+t/90s max 100 |  |

#### turret (29)

| Class | Name | Maps / packs | World state | Flags | Team/side | Stat block: level-1 (+per level) | Attack (script, range, damage) | XP `0x10000224` | Credits `0x10000689` | Level `0x100001D9` | Scripts `0x8E` |
|---|---|---|---|---|---|---|---|---|---|---|---|
| `0x4000016f` | Turret | CA,CC,GD,GH,T1 | `0x2e001037` | `0x4000` | 2/5 | `0x480001b0`: HP 1 AD 1000 AAr 150 PAr 10 | `0x34000014` | `0x3b000016` 5*KilledLvl*ramp/N |  |  |  |
| `0x40000170` | Turret | CA,CC,GD,GH,T1 | `0x2e001037` | `0x4000` | 1/3 | `0x480001b0`: HP 1 AD 1000 AAr 150 PAr 10 | `0x34000014` | `0x3b000016` 5*KilledLvl*ramp/N |  |  |  |
| `0x400003ba` | Turret | GD | `0x2e000ac4` | `0x210` | 1/3 | `0x480006b6`: HP 3000 AD 200+4 AAr 60 PAr 5 | `0x34000014` r9 | `0x3b000016` 5*KilledLvl*ramp/N | `0x3b00025c` 100/N | `0x3b000177` lvl=1+t/90s max 100 | `0x34000838` |
| `0x400003bb` | Turret | GD | `0x2e000aa0` | `0x210` | 1/3 | `0x480006ba`: HP 2700 AD 195+4 AAr 45 PAr 5 | `0x34000014` r9 | `0x3b000016` 5*KilledLvl*ramp/N | `0x3b00025c` 100/N | `0x3b000177` lvl=1+t/90s max 100 | `0x34000838` |
| `0x400003bc` | Turret | GD | `0x2e000aa0` | `0x210` | 1/3 | `0x480006b8`: HP 2550 AD 185+4 AAr 60 PAr 5 | `0x34000014` r9 | `0x3b000016` 5*KilledLvl*ramp/N | `0x3b00025c` 100/N | `0x3b000177` lvl=1+t/90s max 100 | `0x34000838` |
| `0x400003bd` | Turret | GD | `0x2e000aa0` | `0x210` | 2/5 | `0x480006b8`: HP 2550 AD 185+4 AAr 60 PAr 5 | `0x34000014` r9 | `0x3b000016` 5*KilledLvl*ramp/N | `0x3b00025c` 100/N | `0x3b000177` lvl=1+t/90s max 100 | `0x34000838` |
| `0x400003be` | Turret | GD | `0x2e000aa0` | `0x210` | 2/5 | `0x480006b9`: HP 2550 AD 175+4 AAr 55 PAr 5 | `0x34000014` r9 | `0x3b000016` 5*KilledLvl*ramp/N | `0x3b00025c` 100/N | `0x3b000177` lvl=1+t/90s max 100 | `0x34000838` |
| `0x400003bf` | Turret | GD | `0x2e000aa0` | `0x210` | 1/3 | `0x480006b9`: HP 2550 AD 175+4 AAr 55 PAr 5 | `0x34000014` r9 | `0x3b000016` 5*KilledLvl*ramp/N | `0x3b00025c` 100/N | `0x3b000177` lvl=1+t/90s max 100 | `0x34000838` |
| `0x400003c0` | Turret | GD | `0x2e000aa0` | `0x210` | 2/5 | `0x480006ba`: HP 2700 AD 195+4 AAr 45 PAr 5 | `0x34000014` r9 | `0x3b000016` 5*KilledLvl*ramp/N | `0x3b00025c` 100/N | `0x3b000177` lvl=1+t/90s max 100 | `0x34000838` |
| `0x400003c1` | Turret | GD | `0x2e000ac4` | `0x210` | 2/5 | `0x480006b6`: HP 3000 AD 200+4 AAr 60 PAr 5 | `0x34000014` r9 | `0x3b000016` 5*KilledLvl*ramp/N | `0x3b00025c` 100/N | `0x3b000177` lvl=1+t/90s max 100 | `0x34000838` |
| `0x400003f9` | Turret | CC | `0x2e000aa0` | `0x210` | 2/5 | `0x480008a1`: HP 3500 AD 190+6.5 AAr 55 | `0x34000014` r9 | `0x3b000016` 5*KilledLvl*ramp/N | `0x3b000282` 100 | `0x3b0001ea` lvl=1+t/90s max 100 | `0x34000838` |
| `0x400003fa` | Turret | CC | `0x2e000aa0` | `0x210` | 1/3 | `0x480008a1`: HP 3500 AD 190+6.5 AAr 55 | `0x34000014` r9 | `0x3b000016` 5*KilledLvl*ramp/N | `0x3b000282` 100 | `0x3b0001ea` lvl=1+t/90s max 100 | `0x34000838` |
| `0x400003fb` | Turret | CC | `0x2e000aa0` | `0x210` | 2/5 | `0x48000702`: HP 3250 AD 185+6 AAr 45 | `0x34000014` r9 | `0x3b000016` 5*KilledLvl*ramp/N | `0x3b000282` 100 | `0x3b0001ea` lvl=1+t/90s max 100 | `0x34000838` |
| `0x400003fc` | Turret | CC | `0x2e000aa0` | `0x210` | 2/5 | `0x48000703`: HP 3000 AD 185+5.5 AAr 35 | `0x34000014` r9 | `0x3b000016` 5*KilledLvl*ramp/N | `0x3b000282` 100 | `0x3b0001ea` lvl=1+t/90s max 100 | `0x34000838` |
| `0x400003fd` | Turret | CC | `0x2e000aa0` | `0x210` | 1/3 | `0x48000703`: HP 3000 AD 185+5.5 AAr 35 | `0x34000014` r9 | `0x3b000016` 5*KilledLvl*ramp/N | `0x3b000282` 100 | `0x3b0001ea` lvl=1+t/90s max 100 | `0x34000838` |
| `0x400003fe` | Turret | CC | `0x2e000aa0` | `0x210` | 1/3 | `0x48000702`: HP 3250 AD 185+6 AAr 45 | `0x34000014` r9 | `0x3b000016` 5*KilledLvl*ramp/N | `0x3b000282` 100 | `0x3b0001ea` lvl=1+t/90s max 100 | `0x34000838` |
| `0x400003ff` | Turret | CC | `0x2e000ac4` | `0x210` | 2/5 | `0x48000701`: HP 5000 AD 195+7.5 AAr 100 | `0x34000014` r9 | `0x3b000016` 5*KilledLvl*ramp/N | `0x3b000282` 100 | `0x3b0001ea` lvl=1+t/90s max 100 | `0x34000838` |
| `0x40000400` | Turret | CC | `0x2e000ac4` | `0x210` | 1/3 | `0x48000701`: HP 5000 AD 195+7.5 AAr 100 | `0x34000014` r9 | `0x3b000016` 5*KilledLvl*ramp/N | `0x3b000282` 100 | `0x3b0001ea` lvl=1+t/90s max 100 | `0x34000838` |
| `0x40000c86` | Turret | CA | `0x2e000aa0` | `0x210` | 2/1 | `0x48001122`: HP 3000 AD 185 AAr 5 | `0x34000014` r9 | `0x3b000016` 5*KilledLvl*ramp/N | `0x3b000282` 100 | `0x3b0001ea` lvl=1+t/90s max 100 | `0x34000838` `0x340007ec` `0x34000600` |
| `0x40000c8b` | Turret | CA | `0x2e000aa0` | `0x210` | 2/1 | `0x48001129`: HP 2500 AD 165 AAr 5 | `0x34000014` r9 | `0x3b000016` 5*KilledLvl*ramp/N | `0x3b000282` 100 | `0x3b0001ea` lvl=1+t/90s max 100 | `0x34000838` `0x340007ec` `0x34000600` |
| `0x40000c8c` | Turret | CA | `0x2e000aa0` | `0x210` | 1/3 | `0x48001129`: HP 2500 AD 165 AAr 5 | `0x34000014` r9 | `0x3b000016` 5*KilledLvl*ramp/N | `0x3b000282` 100 | `0x3b0001ea` lvl=1+t/90s max 100 | `0x34000838` |
| `0x40000c8d` | Turret | CA | `0x2e000aa0` | `0x210` | 2/1 | `0x48001126`: HP 3000 AD 175 AAr 15 | `0x34000014` r9 | `0x3b000016` 5*KilledLvl*ramp/N | `0x3b000282` 100 | `0x3b0001ea` lvl=1+t/90s max 100 | `0x34000838` `0x340007ec` `0x34000600` |
| `0x40000c8e` | Turret | CA | `0x2e000aa0` | `0x210` | 1/3 | `0x48001127`: HP 3500 AD 185 AAr 35 | `0x34000014` r9 | `0x3b000016` 5*KilledLvl*ramp/N | `0x3b000282` 100 | `0x3b0001ea` lvl=1+t/90s max 100 | `0x34000838` |
| `0x40000c8f` | Turret | CA | `0x2e000ac4` | `0x210` | 1/3 | `0x48001127`: HP 3500 AD 185 AAr 35 | `0x34000014` r9 | `0x3b000016` 5*KilledLvl*ramp/N | `0x3b000282` 100 | `0x3b0001ea` lvl=1+t/90s max 100 | `0x34000838` |
| `0x40000c92` | Turret | CA | `0x2e000aa0` | `0x210` | 1/3 | `0x4800112c`: HP 3000 AD 175+4 AAr 25 PAr 10 | `0x34000014` r9 | `0x3b000016` 5*KilledLvl*ramp/N | `0x3b000351` 100 | `0x3b00034e` lvl=1+t/90s max 100 | `0x34000838` |
| `0x40000c93` | Turret | CA | `0x2e000aa0` | `0x210` | 2/5 | `0x4800112c`: HP 3000 AD 175+4 AAr 25 PAr 10 | `0x34000014` r9 | `0x3b000016` 5*KilledLvl*ramp/N | `0x3b000351` 100 | `0x3b00034e` lvl=1+t/90s max 100 | `0x34000838` |
| `0x40000c94` | Turret | CA | `0x2e000aa0` | `0x210` | 1/3 | `0x4800112b`: HP 2500 AD 165+2.5 AAr 5 | `0x34000014` r9 | `0x3b000016` 5*KilledLvl*ramp/N | `0x3b000351` 100 | `0x3b00034e` lvl=1+t/90s max 100 | `0x34000838` |
| `0x40000c97` | Turret | CA | `0x2e000aa0` | `0x210` | 2/5 | `0x4800112b`: HP 2500 AD 165+2.5 AAr 5 | `0x34000014` r9 | `0x3b000016` 5*KilledLvl*ramp/N | `0x3b000351` 100 | `0x3b00034e` lvl=1+t/90s max 100 | `0x34000838` |
| `0x40000e86` | Turret | CA | `0x2e000aa0` | `0x210` |  | `0x48001471`: HP 2550 AD 175+4 AAr 55 PAr 5 | `0x34000014` r9 | `0x3b000016` 5*KilledLvl*ramp/N | `0x3b000351` 100 | `0x3b00034e` lvl=1+t/90s max 100 | `0x34000838` |

#### dampener (6)

| Class | Name | Maps / packs | World state | Flags | Team/side | Stat block: level-1 (+per level) | Attack (script, range, damage) | XP `0x10000224` | Credits `0x10000689` | Level `0x100001D9` | Scripts `0x8E` |
|---|---|---|---|---|---|---|---|---|---|---|---|
| `0x40000c60` | Dampener | GD | `0x2e000e04` | `0x810` | 2/5 | `0x480010ba`: HP 2700 AD 195+4 AAr 60 PAr 5 | `0x34000014` r7.5 | `0x3b00000e` 200 |  | `0x3b000177` lvl=1+t/90s max 100 | `0x34000838` |
| `0x40000c61` | Dampener | GD | `0x2e000e04` | `0x810` | 1/3 | `0x480010ba`: HP 2700 AD 195+4 AAr 60 PAr 5 | `0x34000014` r7.5 | `0x3b00000e` 200 |  | `0x3b000177` lvl=1+t/90s max 100 | `0x34000838` |
| `0x40000c87` | Dampener | CA | `0x2e000e04` | `0x810` | 2/1 | `0x48001125`: HP 3000 AD 175 AAr 25 | `0x34000014` r9 | `0x3b00000e` 200 |  | `0x3b000177` lvl=1+t/90s max 100 | `0x34000838` `0x340007ec` `0x34000600` |
| `0x40000c88` | Dampener | CA | `0x2e000e04` | `0x810` | 1/3 | `0x48001125`: HP 3000 AD 175 AAr 25 | `0x34000014` r9 | `0x3b00000e` 200 |  | `0x3b000177` lvl=1+t/90s max 100 | `0x34000838` |
| `0x40000c91` | Dampener | CA | `0x2e000e04` | `0x810` | 1/3 | `0x4800112e`: HP 3250 AD 165+3 AAr 15 PAr 5 | `0x34000014` r9 | `0x3b00000e` 200 |  | `0x3b00034e` lvl=1+t/90s max 100 | `0x34000838` |
| `0x40000c95` | Dampener | CA | `0x2e000e04` | `0x810` | 2/5 | `0x4800112e`: HP 3250 AD 165+3 AAr 15 PAr 5 | `0x34000014` r9 | `0x3b00000e` 200 |  | `0x3b00034e` lvl=1+t/90s max 100 | `0x34000838` |

#### core (9)

| Class | Name | Maps / packs | World state | Flags | Team/side | Stat block: level-1 (+per level) | Attack (script, range, damage) | XP `0x10000224` | Credits `0x10000689` | Level `0x100001D9` | Scripts `0x8E` |
|---|---|---|---|---|---|---|---|---|---|---|---|
| `0x40000a7b` | Power Core | GD | `0x2e000ac5` | `0x4010` | 2/5 | `0x48000e34`: HP 4000 |  | `0x3b00000e` 200 |  | `0x3b00000d` lvl=1+t/90s max 100 | `0x34000838` |
| `0x40000a7e` | Power Core | GD | `0x2e000ac5` | `0x4010` | 1/3 | `0x48000e34`: HP 4000 |  | `0x3b00000e` 200 |  | `0x3b00000d` lvl=1+t/90s max 100 | `0x34000838` |
| `0x40000c23` | Power Core | CC | `0x2e0013ee` | `0x4010` | 2/5 | `0x4800105a`: HP 6000 AD 195+7.5 AAr 120 | `0x34000014` r9 | `0x3b00000e` 200 |  | `0x3b0001ea` lvl=1+t/90s max 100 | `0x34000838` |
| `0x40000c24` | Power Core | CC | `0x2e0013ee` | `0x4010` | 1/3 | `0x4800105a`: HP 6000 AD 195+7.5 AAr 120 | `0x34000014` r9 | `0x3b00000e` 200 |  | `0x3b0001ea` lvl=1+t/90s max 100 | `0x34000838` |
| `0x40000c89` | Power Core | CA | `0x2e0013ee` | `0x4010` | 2/1 | `0x48001124`: HP 4000 AD 185 AAr 25 | `0x34000014` r9 | `0x3b00000e` 200 |  | `0x3b00000d` lvl=1+t/90s max 100 | `0x34000838` `0x34000600` |
| `0x40000c8a` | Power Core | CA | `0x2e0013ee` | `0x4010` | 1/3 | `0x48001123`: HP 4000 AD 185 AAr 25 | `0x34000014` r9 | `0x3b00000e` 200 |  | `0x3b00000d` lvl=1+t/90s max 100 | `0x34000838` |
| `0x40000c90` | Power Core | CA,T1 | `0x2e000ac5` | `0x4010` | 1/3 | `0x48001128`: HP 4000 |  | `0x3b00000e` 200 |  | `0x3b00000d` lvl=1+t/90s max 100 | `0x34000838` |
| `0x40000c96` | Power Core | CA | `0x2e0013ee` | `0x4010` | 1/3 | `0x4800112d`: HP 4000 AD 185+4 AAr 35 | `0x34000014` r9 | `0x3b00000e` 200 |  | `0x3b00034e` lvl=1+t/90s max 100 | `0x34000838` |
| `0x40000c98` | Power Core | CA | `0x2e0013ee` | `0x4010` | 2/5 | `0x4800112d`: HP 4000 AD 185+4 AAr 35 | `0x34000014` r9 | `0x3b00000e` 200 |  | `0x3b00034e` lvl=1+t/90s max 100 | `0x34000838` |

#### objective (6)

| Class | Name | Maps / packs | World state | Flags | Team/side | Stat block: level-1 (+per level) | Attack (script, range, damage) | XP `0x10000224` | Credits `0x10000689` | Level `0x100001D9` | Scripts `0x8E` |
|---|---|---|---|---|---|---|---|---|---|---|---|
| `0x4000013b` | Control Point | GH | `0x2e000b22` | `0x80200` |  | `0x48000148`: HP 1 AD 90+4 | `0x340000d5` r4 | `0x3b00000e` 200 |  | `0x3b00009e` lvl=1+t/90s max 100 |  |
| `0x400001f0` | Doomsday Device | CC | `0x2e0008fd` | `0x80010` |  | `0x4800023b`: HP 1 AD 90+4 | `0x340000d5` r4 |  |  | `0x3b0001e7` lvl=1+t/90s max 100 |  |
| `0x400003af` | Control Point | GD | `0x2e000d12` | `0x80000` |  | `0x48000148`: HP 1 AD 90+4 | `0x340000d5` r4 | `0x3b00000e` 200 |  | `0x3b00009e` lvl=1+t/90s max 100 |  |
| `0x40000511` | Orbital Cannon | GH | `0x2e000d12` | `0x80200` |  | `0x480006ce`: HP 1 |  |  |  |  |  |
| `0x4000089d` | Power Relay | CA,CC | `0x2e000d12` | `0x80200` |  | `0x480006ce`: HP 1 |  |  |  | `0x3b0001ea` lvl=1+t/90s max 100 |  |
| `0x40000d25` | Power Relay | CC | `0x2e000d12` | `0x80200` |  | `0x480006ce`: HP 1 |  |  |  |  |  |

#### summon (14)

| Class | Name | Maps / packs | World state | Flags | Team/side | Stat block: level-1 (+per level) | Attack (script, range, damage) | XP `0x10000224` | Credits `0x10000689` | Level `0x100001D9` | Scripts `0x8E` |
|---|---|---|---|---|---|---|---|---|---|---|---|
| `0x40000392` | Billy Batson[n] | 0xa0000120 | `0x2e000923` | `0x100` |  | `0x48000661`: HP 364+70 AD 38+2.2 MS 9 AAr 5 |  | `0x3b000003` 250+100/lvl grp1.4 | `0x3b000135` (see 0x3B section) |  |  |
| `0x400005d2` | The Predator | 0xa00001d2 | `0x2e000cf1` | `0x110000` |  | `0x48000949`: HP 5 AD 5 AS 0.75 MS 3.9 AAr 5 PAr 5 | `0x34000391` r1.5 | `0x3b000016` 5*KilledLvl*ramp/N |  |  | `0x340001a6` |
| `0x40000a68` | Atomic Joker's Head | 0xa000024a | `0x2e000f08` | `0x110000` |  | `0x48000e14`: HP 1 AS 0.75 MS 3.6 |  | `0x3b000016` 5*KilledLvl*ramp/N |  |  |  |
| `0x40000aa6` | Trooper Drone | 0xa000026e | `0x2e0010e0` | `0x110000` |  | HP 1 |  |  |  |  |  |
| `0x40000aa8` | ERROR - Unnamed Destructible | 0xa000026e | `0x2e00107a` | `0x110000` |  | `0x48000f56`: HP 1 |  |  |  |  | `0x34000538` |
| `0x40000bae` | Atomic Joker's Head | 0xa000027c | `0x2e001356` | `0x110000` |  | `0x48000e14`: HP 1 AS 0.75 MS 3.6 |  | `0x3b000016` 5*KilledLvl*ramp/N |  |  |  |
| `0x40000bcb` | Husk | 0xa00002cf | `0x2e001171` | `0x120040` |  | `0x48000f98`: HP 1 |  |  |  |  |  |
| `0x40000bcf` | LexCorp Sentry | 0xa00002de | `0x2e00118a` | `0x120040` |  | `0x48001023`: HP 1 |  |  |  |  |  |
| `0x40000bfc` | ERROR - Unnamed Destructible | 0xa00002c7 | `0x2e00121e` | `0x110000` |  | `0x48000f56`: HP 1 |  |  |  |  | `0x34000538` |
| `0x40000ca5` | Raven's Astral Projection | 0xa0000332 | `0x2e00129f` | `0x110000` |  | `0x4800114d`: HP 1 |  | `0x3b000016` 5*KilledLvl*ramp/N |  |  |  |
| `0x40000d22` | ERROR - Unnamed Destructible | 0xa000035d | `0x2e001333` | `0x110000` |  | `0x48000f56`: HP 1 |  |  |  |  | `0x34000538` |
| `0x40000d2c` | LexCorp Sentry | 0xa0000344 | `0x2e00133f` | `0x120040` |  | `0x48001023`: HP 1 |  |  |  |  |  |
| `0x40000d4e` | Atomic Joker's Head | 0xa000037c | `0x2e001357` | `0x110000` |  | `0x48000e14`: HP 1 AS 0.75 MS 3.6 |  | `0x3b000016` 5*KilledLvl*ramp/N |  |  |  |
| `0x40000d5f` |  | 0xa0000384 | `0x2e001296` | `0x110000` |  | `0x4800092d`: HP 1 | `0x3400077a` r1 dmg=1x`0x3b0002ea` |  |  |  |  |

#### deployable (39)

| Class | Name | Maps / packs | World state | Flags | Team/side | Stat block: level-1 (+per level) | Attack (script, range, damage) | XP `0x10000224` | Credits `0x10000689` | Level `0x100001D9` | Scripts `0x8E` |
|---|---|---|---|---|---|---|---|---|---|---|---|
| `0x4000020b` | Chattering Teeth | 0xa000011b | `0x2e00062d` | `0x20000` |  | `0x480002ae`: HP 1 MS 3 | `0x34000116` r1 |  |  |  |  |
| `0x40000265` | Surveillance Camera | 0xa00000b3 | `0x2e000e6c` | `0x20040` |  | `0x48000516`: HP 3 |  | `0x3b000016` 5*KilledLvl*ramp/N |  |  |  |
| `0x4000045f` | Arcane Lantern | 0xa0000145 | `0x2e000c02` | `0x20020` |  | `0x48000534`: HP 1 |  |  |  |  | `0x340002af` |
| `0x40000482` | Trap | 0xa00000b3 | `0x2e000c92` | `0x20000` |  | `0x48000560`: HP 1 |  | `0x3b000016` 5*KilledLvl*ramp/N |  |  |  |
| `0x40000612` | Time Anchor | 0xa00000b3 | `0x2e000d5d` | `0x20000` |  | `0x48000560`: HP 1 |  | `0x3b000016` 5*KilledLvl*ramp/N |  |  |  |
| `0x40000614` | Bleed Tunnel | 0xa00000b3 | `0x2e000d3c` | `0x20000` |  | `0x480009a9`: HP 1 |  | `0x3b000016` 5*KilledLvl*ramp/N |  |  |  |
| `0x40000615` | Bleed Tunnel | 0xa00000b3 | `0x2e000d3c` | `0x20000` |  | `0x480009a9`: HP 1 |  | `0x3b000016` 5*KilledLvl*ramp/N |  |  |  |
| `0x400007fd` | Surveillance Tower | GD | `0x2e000fe5` | `0x20040` |  | `0x48000a9e`: HP 1 |  |  |  |  |  |
| `0x4000081e` | Hotspot Object | 0xa000011f | `0x2e000ae9` | `0x20000` |  | `0x48000836`: HP 3 |  |  |  |  |  |
| `0x40000892` | Surveillance Drone | CA,CC | `0x2e000d67` | `0x20040` |  | `0x48000c72`: HP 3 AS 0.75 MS 2 | `0x340004a0` r5 dmg=1x`0x3b0002ea` | `0x3b00039b` 60+6/lvl grp1.4 | `0x3b000260` flat 50/N |  |  |
| `0x400008cf` | Regen Pad | CA,GD | `0x2e000e38` | `0x20040` |  | `0x48001028`: HP 3 |  |  |  |  |  |
| `0x400008d0` | Health Emitter | GD | `0x2e000e38` | `0x20040` |  | `0x48001028`: HP 3 |  |  |  |  |  |
| `0x400008d6` | Speed Emitter | GD | `0x2e000e38` | `0x20040` |  | `0x48001028`: HP 3 |  |  |  |  |  |
| `0x400008d7` | Haste Pad | GD | `0x2e000e38` | `0x20040` |  | `0x48001028`: HP 3 |  |  |  |  |  |
| `0x40000951` | Pulse Emitter | GD | `0x2e000fab` | `0x20040` |  | `0x48000d29`: HP 3 |  |  |  |  |  |
| `0x400009b6` | Pulse Emitter | GD | `0x2e000e38` | `0x20040` |  | `0x48001028`: HP 3 |  |  |  |  |  |
| `0x40000a6c` | Generator - Pulse Pack | GD | `0x2e000e38` | `0x20000` |  |  |  |  |  |  |  |
| `0x40000a83` | Surveillance Drone | GD | `0x2e000e6c` | `0x20040` |  | `0x48000a6d`: HP 3 |  | `0x3b000016` 5*KilledLvl*ramp/N |  |  |  |
| `0x40000a94` | Hotspot Object | 0xa000020e | `0x2e00106c` | `0x20000` | 1/ | `0x48000168`: HP 1 |  |  |  |  |  |
| `0x40000bf2` | The Stick | 0xa00002f7 | `0x2e0011c9` | `0x20020` |  | `0x48000534`: HP 1 |  |  |  |  |  |
| `0x40000c20` | VFX Item | 0xa0000303 | `0x2e001246` | `0x20000` | 1/ | `0x4800077e`: HP 1 |  |  |  |  |  |
| `0x40000c25` | Merels | 0xa0000303 | `0x2e001201` | `0x20020` |  | `0x48000534`: HP 1 |  |  |  |  | `0x34000652` |
| `0x40000c4c` | Speed Emitter | CA | `0x2e000e38` | `0x20040` |  | `0x48001028`: HP 3 |  |  |  |  |  |
| `0x40000c80` | VFX Item | 0xa0000337 | `0x2e000002` | `0x20000` | 1/ | `0x4800077e`: HP 1 |  |  |  |  |  |
| `0x40000ca4` | VFX Item | 0xa000022e | `0x2e00107f` | `0x20000` | 1/ | `0x4800077e`: HP 1 |  |  |  |  |  |
| `0x40000cb2` | Hotspot Object | 0xa00001d2 | `0x2e0012da` | `0x20000` | 1/ | `0x48000168`: HP 1 |  |  |  |  |  |
| `0x40000cb4` | Environment | GD | `0x2e001314` | `0x20040` |  | `0x480006ce`: HP 1 |  |  |  |  |  |
| `0x40000cb5` | Environment | CA,GD | `0x2e001314` | `0x20040` |  | `0x480006ce`: HP 1 |  |  |  |  |  |
| `0x40000cb8` | Environment | GD | `0x2e001314` | `0x20040` |  | `0x480006ce`: HP 1 |  |  |  |  |  |
| `0x40000cb9` | Environment | GD | `0x2e001314` | `0x20040` |  | `0x480006ce`: HP 1 |  |  |  |  |  |
| `0x40000cba` | Environment | GD | `0x2e001314` | `0x20040` |  | `0x480006ce`: HP 1 |  |  |  |  |  |
| `0x40000cbb` | Environment | GD | `0x2e001314` | `0x20040` |  | `0x480006ce`: HP 1 |  |  |  |  |  |
| `0x40000cbe` | Environment | GD | `0x2e001314` | `0x20040` |  | `0x480006ce`: HP 1 |  |  |  |  |  |
| `0x40000ceb` |  | 0xa000033f | `0x2e0012d1` | `0x20000` |  |  |  | `0x3b000016` 5*KilledLvl*ramp/N |  |  |  |
| `0x40000d61` | VFX Item | 0xa0000384 | `0x2e0003fe` | `0x20000` | 1/ | `0x4800077e`: HP 1 |  |  |  |  |  |
| `0x40000ea7` | Merels | 0xa0000349 | `0x2e00135a` | `0x20020` |  | `0x48000534`: HP 1 |  |  |  |  | `0x34000652` |
| `0x40000ebd` | Merels | 0xa00003a6 | `0x2e001412` | `0x20020` |  | `0x48000534`: HP 1 |  |  |  |  | `0x34000652` |
| `0x40000ecc` | Hotspot Object | 0xa000030e | `0x2e00141e` | `0x20000` | 1/ | `0x48000168`: HP 1 |  |  |  |  |  |
| `0x40000eed` | Environment | CC | `0x2e001314` | `0x20040` |  | `0x480006ce`: HP 1 |  |  |  |  |  |


#### other classes with unit properties (71)

Doors, colliders, pickups and destructible props carry unit flags so the attack check and the scripts can treat them;
none attacks or moves (C).

- 0x2000 doors: `0x40000269` `0x4000026B` (GH), `0x40000557` (CA, CC, GD, T1), `0x40000B0F` (CA, T1), `0x40000C2A` (CA),
  `0x40000C6E` `0x40000CAB` (T1); blockers `0x400003F2` (GH), `0x40000621` (all PvP maps); ECM Burst `0x40000BD2`.
- 0x4 pickups / colliders: Regen Pack `0x40000A86` (CA, GD), Haste Pack `0x40000A87` (GD); colliders `0x400000A4`,
  `0x400003F3`, `0x40000551`, `0x400005E1` (the pickup the heavy jungle creatures drop, script `0x3400007D`),
  `0x400006F3`, `0x40000C7A`, `0x40000C7B`, `0x40000CDC`..`0x40000CE1` (GD), `0x4000043D` (0x44).
- 0x1000 / 0x1080 destructible props: T1 `0x400001BD`, `0x400001C5`..`0x400001CA`, `0x40000CAF`; CC `0x40000540`..`544`,
  `0x40000C1F`, `0x40000455`, `0x40000456`, `0x4000045A`, `0x4000045B`, `0x40000461`, `0x40000555`, `0x40000556`; shared
  `0x40000453`, `0x40000454`, `0x40000458`, `0x40000459`, `0x4000045D`, `0x4000045E`, `0x4000081A`..`81C`, `0x40000C40`.
- 0x22 rocks: `0x4000044F`, `0x400005C9` (all PvP maps), Sunstone `0x40000646`.
- flags 0: Firing Trigger `0x4000054F` (CC), Phase Pod `0x40000A79` (GD), Hotspot Objects `0x40000637`, `0x40000AAC`
  (GD), `0x40000BEF`, `0x4000050D` / `0x4000050E` (GH), `0x40000C49` (CA; spawned by the Raider's `0x34000670`),
  Environment `0x40000C21`, Obstacle `0x40000647`; `0x40000208` (0x40).
- `0x40000C14` (T1, 0x10000): the ambient rat critter (world state `0x2E00033A`, attack `0x34000088`, no rewards).

#### skill projectiles (93; flags 0x20, developer name "ERROR - Unnamed Destructible")

Missiles and ground effects of champion skills, each in its champion's pack, with their own `0x8E` scripts (C):
`0x4000000A` `0x40000090` `0x40000092` `0x40000093` `0x40000146` `0x400001E7` `0x40000207` `0x40000209` `0x4000020A`
`0x40000263` `0x4000026E` `0x40000350` `0x40000359` `0x4000039A` `0x400003CA` `0x400003EB` `0x4000046D` `0x40000484`
`0x40000485` `0x40000487` `0x40000512` `0x40000545` `0x4000059D` `0x400005D3` `0x40000616` `0x40000634` `0x40000635`
`0x400007EF`..`0x400007F2` `0x400007F6` `0x400007F7` `0x400007FC` `0x400007FE` `0x400007FF` `0x40000800` `0x40000811`
`0x40000815` `0x40000817` `0x40000819` `0x400008BF` (0x20020) `0x400008C4` `0x40000990` `0x40000994` `0x400009B3`
`0x400009B5` `0x400009B7` `0x40000A5A` `0x40000A8E` `0x40000ABD` `0x40000ADE` `0x40000ADF` `0x40000AE5` `0x40000B17`
`0x40000B18` `0x40000B1A` `0x40000B1C` `0x40000B21` `0x40000BAA` `0x40000BAF` `0x40000BB8` `0x40000BCA` `0x40000BCD`
`0x40000BD4` `0x40000BDB` `0x40000BE5` `0x40000C0D` `0x40000C1C` `0x40000C22` `0x40000C6B` `0x40000C70` `0x40000C73`
`0x40000CA7` `0x40000CA9` `0x40000CC8` `0x40000CD6` `0x40000CD7` `0x40000CD8` `0x40000CEC` `0x40000D1D` `0x40000D1E`
`0x40000D20` `0x40000D24` `0x40000D2D` `0x40000D55` `0x40000E6F` `0x40000EA8` `0x40000EAC` `0x40000ECD` `0x40000ED1`
`0x40000ED2` `0x40000EE5`.

### 1.4 Notes on the groups

- **Minions per map** (C): GD `0x4000010A` Soldier, `0x4000010B` Trooper, `0x4000010D` Cannon, `0x40000941` /
  `0x40000942` Elite Trooper / Soldier, `0x40000E5F` Destroyer Drone; CC `0x400002D4` / `0x400002D5`, second set
  `0x40000C45`..`C48`, `0x40000441` Cannon, `0x40000442` / `443` Elites, `0x40000D23` Raider Drone, `0x40000D5C`
  Destroyer Drone; GH `0x4000012D` / `0x4000012E`, `0x40000EAA` Destroyer Drone. CA has several sets: Tutorial 2 drones
  `0x40000BC1`..`0x40000BC9` (flat XP, some without credits), a set with CC stats `0x40000BF8`..`0x40000BFA`, a set with
  GD-like stats and CA's own credit formulas `0x40000C9A`..`C9E` + `0x40000E79`..`E81`, the Watcher Drone `0x40000EB5`.
  Which set each Crime Alley mode used (Tutorial 2, 1v1 vs AI, Clash) is not in the data (P: the encounter's flow
  chose it). T1: `0x40000C72` / `C71` / `A5C` / `A5D` / `B23` / `B24` / `EB2` / `EB4` / `BA9`.
- **Jungle per map** (C): GD 13 classes, CC 12, CA 9. Bosses: Leviathan `0x40000937` (GD; attack `0x3400057B`, range
  15; credits 4 x killer level per receiver; kill buff `0x48000E4C`), Doomsday Guardian `0x40000430` (CC; attack
  `0x34000442`, ability script `0x3400057A`), Raiders (`0x40000938` GD with 0x200, `0x400007C1` / `0x40000D60` CC).
  Heavy creatures carry `0x3400007D`: on death (event `0x10000007`) it spawns collider `0x400005E1` with the killer's
  team (`0x1000009C`) = a pickup. Regen / Haste Destroyer `0x3400051A` / `0x3400051B` only store `KillerIID` (the buff
  itself is the kill status, P). Raiders in CA carry `0x34000670`: on death it spawns `0x40000C49`.
- **Structures**: turret HP / damage come from flat stats or `Level`-only formulas (`0x3B000051`..`54`: 2550 / 2700 /
  3000 HP, damage `175..200 + 4 x Level`), levelled with match time like the units. Cores have 4000 (GD, CA) / 6000 (CC)
  HP; the CC and some CA cores also shoot (`0x34000014`, range 9). Turret XP is `0x3B000016` (shared kill XP),
  credits 100 / N for the nearby receivers (`0x10000689`) plus a team bounty 90..350 (`0x10000362`, flat per turret).
  `0x34000838` on every structure is the "under attack" ping; CA copies add `0x340007EC` (tutorial warning) and
  `0x34000600` (map ping).
- **Summons** are champions' pets and clones (Joker's head, Predator, Raven's projection, LexCorp Sentries, Husk,
  Billy Batson); their behaviour is in their champion's skill scripts.

## 2. Unit stat blocks (C)

`0x10000165` names a 0x48 record: `did | 0 | n | entries`, each `stat | stat | f32` (fixed value), `stat | 0x5..`
(empty) or `0x1000031A` = array of `0x100002B4` tables {`0x10000319` formula 0x3B, `0x10000100` stat id (kind 0x0A)}.
Example GD Soldier `0x48000D10`: AS 1.0, MS 4.2, Crit `0x10000B80` 2.0, `0x10000642` 2.0, `0x10000934` 5, and
`0x1000031A` = {`0x3B00005F` -> Health (500 + 10/lvl), `0x3B000061` -> Attack Damage (11.25 + 0.9), `0x3B000060` ->
Attack Armor (5 + 1)}. The template itself may also hold stats (it overrides / adds: `0x10000426`, `0x10000B76` ...).
The formula's `Level` is the unit's level from `0x100001D9`, so lane minions and jungle creatures get stronger every
90 s of match time (C data, P that `Time` is seconds since the match start: its default value is 300 and the champions'
level formula `0x3B00000D` is the same).

## 3. Formula records 0x3B (C)

### 3.1 Format

DB type 8, create `0x463490` (0x28-byte object, vtable `0x15A8D90`), unpack `0x9D8880` -> vtable slot 27 =
`0x46A140`:
1. `0x44AD60` (the 0x3A unpack, section 4): DB header `0x43D210` (DID), then the variable block (`0x44A370` ->
   `0x45AA30`, object +0x20): `u8 1 | u8 1 | u32 n | n x u32 type | defaults (server-only, 1..3 words each) | u8 1 | u8 0
   | u8 n | n x (u32 ELF hash, u32 slot offset) | u32 n | n x (u8 len, chars padded to 4)`.
   Every u8 takes 4 bytes in the packs. Types: 0 bool, 1 int32, 2 uint32, 3 float, 4 DataID, 5 int64, 6 uint64,
   7 double / timer, 8 IID, 9 vector, 0xA position, 0xD enum (default = enum table 0x30.. + value), 0xE bitfield.
   The defaults are in slot order. Names are matched by ELF hash (`Base` 0x48895, `Time` 0x5B035, `Rank` 0x5884B,
   `Mod` 0x5454, `SELF` 0x4DD4 are not spelled out in the name table, only hashed).
2. `u32` expression type, then the expression object from the expression registry (`0x45FB30` / `0x45E450`), unpacked
   with its vtable slot 5. It is the same expression family as in the 0x34 scripts.

`tools\script_decoder.py`'s emulator decodes them by calling create `0x463490` and unpack `0x9D8880` instead of the
script ones (276 of 277 0x3B records decode, `0x3B0000B7` stops at the server-only expression 0xC; the 52 0x3A, 4 0x3F
and 2 of 11 0x3C decode too, the 9 others are not present in the packs).

### 3.2 Evaluating (expression classes, vtable slot 10 `+0x28` = evaluate into a 16-byte variant)

| Id (vtable) | Evaluate | Meaning | |
|---|---|---|---|
| 0x02 (`0x15A8F18`) | | constant: fields `type | value` (type 3 float, 1 int, 0xE bitfield `enum table | mask`) | C |
| 0x03 (`0x15A9D38`) | | variable: `hash | source | slot` (source 0 = the record's variables) | C |
| 0x23 / 0x1C / 0x29 / 0x06 | | + - x / | C (reverse-engineering.md) |
| 0x22 / 0x1B / 0x2A | | == != < | C |
| `0x10000003` (`0x15FABDC`) | `0x97D2F0` | **Linear(Level, Base, Delta)**: `Base + (Level - 1) x Delta`; with its flag byte (+0x14, the 4th field = 1) and Level == 0 the result is Base | C |
| 0x1E (`0x15A9130`) | `0x463E80` | **clamp(x, lo, hi)** = `min(hi, max(x, lo))` | C |
| 0x27 (`0x15A9BB0`) | `0x462F00` | **select(cond, a, b)** | C |
| 0x34 (`0x15A8FE0`) | `0x462150` -> `0x44F520` (setg) | a > b | C |
| 0x0A (`0x15A9168`) | `0x462350` -> `0x454AA0` | binary op on bitfields: `(DamagedByTypes op mask) != 0` | P: bitwise AND |
| 0x1A (`0x15A99B8`) | `0x4641F0` | to int32 (truncate floats) | C |
| 0x35 (`0x15A9600`) | `0x462A70` -> `0x4552B0` (CRT call `0x134D3E1`) | floor | P |
| 0x13 (`0x15A92F0`) | `0x4625F0` | logical and (returns a when a is zero) | P |
| 0x33 / 0x0E | `0x462670` / `0x464270` | number conversions | P |
| `0x10000002` (`0x15FDD28`) | | GetAttribute(SELF)[attribute, mode]: fields `attr | 0x4DD4 | 0 | 0 | mode` (mode 0 / 1 / 2; P: base / current / bonus) | C structure |
| server-only 0xC | | not in the client (only in `0x3B0000B7`) | ? |

### 3.3 The formula families

- **Linear stat curves** (`Level`, `Base`, `Delta`, 122 records): unit stats, skill rank values.
- **Level by time** (`Time`, `TimeToLevel` 90, `MaxLevel` 100; 12 records): `clamp(int(floor((Time + TimeToLevel) /
  TimeToLevel)), 1, MaxLevel)`.
- **Kill XP** (37): inputs `KillerLevel, KilledLevel, NumReceivers, RewardTier, BaseXP, DeltaXP, GroupBonus, IsKiller`.
  Units: `Linear(KilledLevel, BaseXP, DeltaXP) x (NumReceivers > 1 ? GroupBonus : 1) / NumReceivers`. Tutorial units:
  `BaseXP` flat. Champions `0x3B000003`: `Linear(KilledLevel, 250, 100) x 0.5 (PercentLevelToGain) x clamp(1 + 0.25 x
  (KilledLevel - KillerLevel), 0.25, 2) x group bonus / NumReceivers`. Structures `0x3B000016`: `5 x KilledLevel x
  clamp(1 + 0.25 x (KilledLevel - KillerLevel), 0.25, 2) / NumReceivers`.
- **Kill credits** (42): inputs add `DamagedByTypes` (bitfield, enum table 0x30000009), `BaseValue, DeltaValue,
  TurretValue_RewardPercent, CharacterValue_RewardPercent, LastHitValue_RewardPercent, MinionOnlyValue_RewardPercent,
  GroupBonusMultiplier, LastHit`. Typical (`0x3B0001DF`): `clamp(GroupBonusMultiplier, 1, 1.2) x Linear(KilledLevel,
  Base, Delta) / NumReceivers x ((DamagedByTypes & 0x80010) != 0 ? TurretPercent : (LastHit ? LastHitPercent :
  CharacterPercent))`. Bosses clamp the result (`0x3B0001EF`: 400..800, `0x3B000254`: 300..700, `0x3B0002A9`: 150..300).
  Champions: `0x10000689` = `0x3B000135` (always 0) and the bounty `0x10000362` = `0x3B0000B7` (`Bounty_Base` 400,
  +20 % per consecutive kill up to 900, down to 75 on death streaks, ramped by the victim's level 2..6 from x0.6 to x1).
- **Flat**: structures' team bounty (90..350), dampener / core XP 200 (`0x3B00000E`), turret credits 100 / N.
- **Attribute formulas** (24): `GetAttribute(SELF)[stat] x Mod`, used by skill stats (`0x100004D7`): e.g. a unit's
  attack damage stat 5 = `0x3B0002EA` = AttackDamage(mode 1) x 1.0.
- **Other**: `0x3B000038` match score `Saves x 40 + Kills x 50 + Money x 5 - Deaths x 250`; `0x3B00015F` missing-Will
  scaling; `0x3B000364` (empty, a variable holder).

Evaluating in Python is ~40 lines: walk the decoded tree with the table above, variables from the defaults, overridden
by the caller (Level, KilledLevel, NumReceivers, ...).

### 3.4 All 0x3B records by family (`Base+Delta` or `BaseXP/DeltaXP`)

**xp** (37): `0x3B000003` 250/100; `0x3B0001ED` 45/6.75; `0x3B0001EE` 60/9; `0x3B0001F0` 800/0; `0x3B00020C` 65/9.75; `0x3B000253` 500/0; `0x3B000261` 8/0.96; `0x3B000265` 20/2.4; `0x3B000269` 85/10.2; `0x3B00026D` 10/1.2; `0x3B000271` 100/12; `0x3B000275` 11/1.32; `0x3B000279` 110/13.2; `0x3B00027D` 150/18; `0x3B00028A` 65/6.5; `0x3B00028E` 48/4.8; `0x3B000292` 53/5.3; `0x3B000294` 9/1.5; `0x3B000298` 13.5/2; `0x3B00029C` 90/3.5; `0x3B0002A0` 10/2; `0x3B0002A4` 100/4.5; `0x3B0002A8` 600/15; `0x3B0002AD` 25/5; `0x3B0002B1` 125/5; `0x3B0002B5` 2000/20; `0x3B0002B9` 180/9; `0x3B0002BC` 180/9; `0x3B0002BF` 110/4; `0x3B0002D6` 115/0 flat; `0x3B0002D7` 100/0 flat; `0x3B00033C` 0/0 flat; `0x3B000359` 500/0; `0x3B000369` 200/16; `0x3B00039B` 60/6; `0x3B0003A0` 35/3.5; `0x3B0003A1` 50/5

**level** (12): `0x3B00000D` (TimeToLevel 90, MaxLevel 100); `0x3B00009E` (TimeToLevel 90, MaxLevel 100); `0x3B000177` (TimeToLevel 90, MaxLevel 100); `0x3B0001E7` (TimeToLevel 90, MaxLevel 100); `0x3B0001E8` (TimeToLevel 90, MaxLevel 100); `0x3B0001E9` (TimeToLevel 90, MaxLevel 100); `0x3B0001EA` (TimeToLevel 90, MaxLevel 100); `0x3B00022E` (TimeToLevel 90, MaxLevel 100); `0x3B00022F` (TimeToLevel 90, MaxLevel 100); `0x3B000287` (TimeToLevel 90, MaxLevel 100); `0x3B00034E` (TimeToLevel 90, MaxLevel 100); `0x3B0003A3` (TimeToLevel 90, MaxLevel 100)

**kill-other** (17): `0x3B00000E` = 200; `0x3B000016` = (((5 * $KilledLevel) * builtin:0x1e[35 2 2](((0.25 * ($KilledLevel - $KillerLevel)) + 1), ; `0x3B0000CE` = ((4 * $KillerLevel) / $NumReceivers); `0x3B000135` = ((0 * builtin:0x1e[35 2 2](((0x3dcccccd * ($KilledLevel - $KillerLevel)) + 1), 0.5, 1.5)) ; `0x3B00025C` = (100 / $NumReceivers); `0x3B000282` = 100; `0x3B0002C8` = 200; `0x3B0002CB` = 195; `0x3B0002CC` = 90; `0x3B0002CD` = 150; `0x3B0002D1` = 350; `0x3B0002D2` = 200; `0x3B0002D3` = 150; `0x3B0002D4` = 100; `0x3B000347` = 200; `0x3B00034A` = 350; `0x3B000351` = 100

**other** (5): `0x3B000038` vars ['Kills', 'Deaths', 'Assists', 'Saves', 'Money'] = ((($Saves * #2 40) + (($Kills * #2 50) + ($Money * #2 5))) - ($Deaths * #2 250)); `0x3B0000CA` vars ['0x5884b', '0x48895', 'Delta'] = 0x10000003[3 3 3 1]($0x5884b, $0x48895, $Delta); `0x3B0002DE` vars ['0x5884b', '0x48895', 'Delta'] = 0x10000003[3 3 3 0]($0x5884b, $0x48895, $Delta); `0x3B00032F` vars ['SecondaryCurrent', '0x5454'] = ($SecondaryCurrent * $0x5454); `0x3B000364` vars ['ChosenPosition', 'TestPosition', 'OriginPosition', 'MissileOffset', 'PositionOffset', 'BestowalType', 'RadiusBestowalType', 'TeamBestowalType'] = #1 0

**level-const** (18): `0x3B000051` = ((0 * $Level) + 2550); `0x3B000052` = ((0 * $Level) + 2550); `0x3B000053` = ((0 * $Level) + 2700); `0x3B000054` = ((0 * $Level) + 3000); `0x3B000095` = 100; `0x3B000096` = 1; `0x3B00009C` = ((4 * $Level) + 90); `0x3B000107` = ((20 * $Level) + 100); `0x3B00012F` = 3; `0x3B000183` = ((4 * $Level) + 195); `0x3B000184` = ((4 * $Level) + 185); `0x3B000185` = ((4 * $Level) + 175); `0x3B000186` = ((4 * $Level) + 200); `0x3B0002CF` = ((0 * $Level) + 4000); `0x3B0002F5` = ((0 * $Level) + 6000); `0x3B00031D` = ((0 * $Level) + 2700); `0x3B00034D` = ((0 * $Level) + 4000); `0x3B000394` = ((4 * $Level) + 175)

**linear** `Base+Delta` (stat curves) (122): `0x3B00005F` 500+10; `0x3B000060` 5+1; `0x3B000061` 11.25+0.9; `0x3B000062` 250+5; `0x3B000063` 5+1; `0x3B000064` 18+1.125; `0x3B000065` 500+10; `0x3B000066` 22.5+1.5; `0x3B000067` 25+2; `0x3B00008C` 175+2.11; `0x3B00008D` 0+1; `0x3B00008E` 20+1.63; `0x3B00008F` 325+3.2; `0x3B000090` 0+1; `0x3B000091` 22+1.29; `0x3B00009D` 20+2.75; `0x3B00012C` 0+0; `0x3B00018D` 455+16.5; `0x3B00018E` 0+1; `0x3B00018F` 12+1.25; `0x3B000193` 350+10; `0x3B000194` 0+1; `0x3B000195` 20+1.75; `0x3B00019A` 0.1+0.1; `0x3B0001B4` 3250+0; `0x3B0001B5` 185+6; `0x3B0001B6` 3000+0; `0x3B0001B7` 185+5.5; `0x3B0001B8` 5000+0; `0x3B0001B9` 195+7.5; `0x3B000201` 1750+500; `0x3B000202` 80+8; `0x3B00020E` 650+20; `0x3B00020F` 15+1; `0x3B000210` 35+3; `0x3B000211` 350+40; `0x3B000212` 0+1.5; `0x3B000213` 20+2.5; `0x3B000214` 455+60; `0x3B000215` 0+1.5; `0x3B000216` 12+2; `0x3B000217` 0.1+0.05; `0x3B000243` 3500+0; `0x3B000244` 190+6.5; `0x3B000245` 364+70; `0x3B000246` 335+45; `0x3B000249` 5+0; `0x3B00024A` 5+0; `0x3B00024B` 5+0; `0x3B00024C` 5+0; `0x3B00024D` 5+0; `0x3B00024E` 5+0; `0x3B000255` 2000+150; `0x3B000256` 60+6; `0x3B000263` 150+13; `0x3B000264` 7.5+0.33; `0x3B000267` 200+12; `0x3B000268` 15+0.66; `0x3B00026B` 725+20; `0x3B00026C` 20+0.5; `0x3B00026F` 175+18; `0x3B000270` 10+0.33; `0x3B000273` 700+27; `0x3B000274` 20+0.5; `0x3B000277` 225+22; `0x3B000278` 15+0.5; `0x3B00027B` 825+47; `0x3B00027C` 25+0.75; `0x3B00027F` 1225+90; `0x3B000280` 40+2; `0x3B00028C` 327.5+15; `0x3B00028D` 26+2.25; `0x3B000290` 655+20; `0x3B000291` 18+1.8; `0x3B000296` 150+13; `0x3B000297` 8+0.5; `0x3B00029A` 200+12; `0x3B00029B` 16+1; `0x3B00029E` 725+20; `0x3B00029F` 20+1; `0x3B0002A2` 175+18; `0x3B0002A3` 10+0.5; `0x3B0002A6` 800+40; `0x3B0002A7` 25+3; `0x3B0002AA` 2200+240; `0x3B0002AC` 185+0; `0x3B0002AF` 225+22; `0x3B0002B0` 18+1; `0x3B0002B3` 950+50; `0x3B0002B4` 35+1.5; `0x3B0002B7` 5000+215; `0x3B0002B8` 220+0; `0x3B0002BA` 1425+95; `0x3B0002BB` 35+4.5; `0x3B0002BD` 1425+95; `0x3B0002BE` 28+5.5; `0x3B0002C1` 1425+95; `0x3B0002C2` 40+3; `0x3B0002C6` 5+1; `0x3B0002C7` 5+1; `0x3B0002D8` 0.1+0.05; `0x3B0002F3` 5+0; `0x3B0002F4` 38+2.2; `0x3B0002F6` 195+7.5; `0x3B000322` 150+13; `0x3B000323` 5+0.33; `0x3B00032A` 1500+75; `0x3B00032B` 40+3; `0x3B000345` 3250+0; `0x3B000346` 165+3; `0x3B000348` 2500+0; `0x3B000349` 165+2.5; `0x3B00034B` 3000+0; `0x3B00034C` 175+4; `0x3B00035B` 2000+150; `0x3B00035C` 60+6; `0x3B00036B` 1500+120; `0x3B00036C` 40+2; `0x3B00039C` 1500+52.632; `0x3B00039D` 20+1.0526; `0x3B00039E` 60+2.1053; `0x3B0003D1` 185+4

**credits** (42): `0x3B0000B7` bounty; `0x3B0001DF` 25/1.5; `0x3B0001E1` 15/0.9; `0x3B0001EF` 100/45; `0x3B00020D` 55/3.3; `0x3B000254` 0/45; `0x3B000260` 50/4; `0x3B000262` 3/0.24; `0x3B000266` 6/0.48; `0x3B00026A` 20/1.6; `0x3B00026E` 5/0.4; `0x3B000272` 25/2; `0x3B000276` 8/0.64; `0x3B00027A` 35/2.8; `0x3B00027E` 150/12; `0x3B00028B` 60/1; `0x3B00028F` 20/0.5; `0x3B000293` 25/0.5; `0x3B000295` 3/1; `0x3B000299` 6/1; `0x3B00029D` 16/1.5; `0x3B0002A1` 5/1; `0x3B0002A5` 20/1.5; `0x3B0002A9` 85/10; `0x3B0002AE` 8/1; `0x3B0002B2` 24/1.5; `0x3B0002C0` 40/1; `0x3B0002C3` 80/1.5; `0x3B0002C4` 80/1.5; `0x3B00035A` 250/10; `0x3B000363` 5/0; `0x3B000365` 15/0; `0x3B000366` 10/0; `0x3B00036A` 150/3.75; `0x3B000395` 200/5; `0x3B000396` 25/5; `0x3B000397` 50/10; `0x3B000398` 50/0.5; `0x3B000399` 50/0.5; `0x3B00039A` 100/0.5; `0x3B00039F` 40/2; `0x3B0003A2` 30/2

**attribute** (24): `0x3B00010A` = 0x10000002[0x10000b7b 19924 0 0 0](); `0x3B00010B` = (0x10000002[0x10000426 19924 0 0 1]() * $0x5454); `0x3B000149` = (0x10000002[0x10000432 19924 0 0 1]() * $0x5454); `0x3B00015F` = ((100 * builtin:0x27[19 6 2](builtin:0x13[27 27](($0x4dd4 != #8 '\x00\x00\x00\x00\x00\x00\x00\x00'), (0x10000002[0x10000432 19924 0 0 0]() != 0)), ((0x10000002[0x10000432 19924 0 0 0]() - $SecondaryCurrent) / 0x10000002[0x10000432 19924 0 0 0]()), 0)) * 0x10000003[3 3 3 1]($0x5884b, $0x48895, $Delta)); `0x3B000163` = (0x10000002[0x100005e4 19924 0 0 0]() * 100); `0x3B000176` = (0x10000002[0x100005e4 19924 0 0 1]() * 100); `0x3B000203` = (0x10000002[0x10000426 19924 0 0 0]() * $0x5454); `0x3B000226` = (2 - 0x10000002[0x10000b7b 19924 0 0 0]()); `0x3B0002CE` = (0x10000002[0x10000a9f 19924 0 0 0]() * $0x5454); `0x3B0002D0` = builtin:0x33[41]((0x10000002[0x10000432 19924 0 0 1]() * $0x5454)); `0x3B0002D5` = (0x10000002[0x10000b00 19924 0 0 0]() * $0x5454); `0x3B0002E6` = (0x10000002[0x10000b75 19924 0 0 1]() * $0x5454); `0x3B0002E7` = 0x10000002[0x10000b75 19924 0 0 2](); `0x3B0002E8` = 0x10000002[0x10000b76 19924 0 0 0](); `0x3B0002E9` = builtin:0x33[41]((0x10000002[0x10000b76 19924 0 0 1]() * $0x5454)); `0x3B0002EA` = (0x10000002[0x10000b76 19924 0 0 1]() * $0x5454); `0x3B0002EB` = (0x10000002[0x10000b76 19924 0 0 2]() * $0x5454); `0x3B0002EC` = 0x10000002[0x10000b76 19924 0 0 2](); `0x3B0002EE` = (0x10000002[0x10000b75 19924 0 0 1]() * 0x10000003[3 3 3 1]($0x5884b, $0x5454, $Delta)); `0x3B0002EF` = 0x10000002[0x10000b84 19924 0 0 2](); `0x3B0002F0` = (0x10000002[0x10000b84 19924 0 0 1]() * $0x5454); `0x3B000357` = (0x10000002[0x10000c6e 19924 0 0 0]() * $0x5454); `0x3B000360` = (0x10000002[0x10000b76 19924 0 0 0]() * 0x10000003[3 3 3 1]($0x5884b, $0x5454, $Delta)); `0x3B00036D` = (0x10000002[0x100006fe 19924 0 0 0]() * $0x5454)

## 4. HFSM records 0x3A (and 0x3C, 0x3F) (C)

- **0x3A (DB type 0x3F, create `0x450720`, unpack `0x9D8680` -> `0x44AD60`) is only a variable block**: DB header +
  the variable declarations of 3.1. No states, no transitions, no logic. It is the per-entity blackboard that the
  entity's 0x34 scripts share (source-1 "instance" variables such as the cooldown timers). An entity names it with
  template property **`0xEF`** (52 records; table below).
- The client's `gmHFSMComponent` (string `0x15F958C`, only referenced from the profiling scope in `0x977B30`) updates
  the HFSM instances of an entity; the HFSM programs are the 0x34 scripts, not the 0x3A records.
- **0x3C** (11 DIDs, 2 in the packs: `0x3C000000`, `0x3C000005`, empty) are variable declarations too. **0x3F** (4:
  `0x3F000003`, `0x3F000006`, `0x3F000009` collision handlers of missiles; `0x3F000007` a damage-reduction handler) =
  variable block + one 0x34 node chain (an event handler snippet).
- **0x1C** records (176) are Havok Behavior animation graphs (`*_behavior.hkb`, template / world state property
  `0x5B5`), i.e. animation state machines, not AI.
- No other AI / brain record type exists: the remaining record types (0x37, 0x3E, 0x50, 0x31, 0x39) hold animation,
  zone and enum data (C, by content).

| 0x3A | Used by (`0xEF`) | Variables |
|---|---|---|
| `0x3A000001` | 187 projectiles / effects | SELF, BrushCounter |
| `0x3A000010` | 23 doors, rocks, triggers | SELF, BrushCounter |
| `0x3A000012` | 7 VFX items / environment | + UserIID |
| `0x3A000026` | **145 units**: every minion, jungle creature, structure, pad | the common champion block (cooldown timers for Basic / Passive / Recall / Skill1-3 / Secondary1-2 / Ultimate / Bonus / Item1-6, AutoAttackTimer, ExecuteSkillNWaitTimer, skill costs, BasicAttackMiniCooldownDuration, UltimateActivated, EmpowerActive) + **GetBestPerceivedTargetInterval_Min = 0.5, _Max = 0.8, AIActive** |
| `0x3A00001D` | 45 (42 champions + some objects) | the common champion block |
| `0x3A000017`..`0x3A000056` (38 records) | the champions (one per kit; e.g. `0x3A000052` Gaslight Batman: + SonicShellIID) | common block + the kit's own variables |
| `0x3A00004D` | Merels pets `0x40000C25` / `EA7` / `EBD` | + Attached |
| `0x3A000029` | GH layout | MatchTeamLost, MatchTeamWon, CapturePoint_Total_Team1/2 |
| `0x3A000011`, `13`, `14`, `28`, `34`, `39`, `43` | event parameter blocks (iidSource, damage event: DirectSourceIID, TargetIID, SkillSlot, Damage, IsDOT, IsAOE, IsCrit ...) | |

## 5. AI

### 5.1 What is in the client (C)

- No AI strings in the exe ("Aggro", "Leash", "Minion", "Jungle", "Spawner", "Respawn", "Bot" except a UI name, "Lane":
  none). The client has no AI code; Kynapse's debug commands are labelled "Server only".
- Node classes that belong to AI are registered in the client only to read scripts (data-only, no execute): `0x1000004F`
  AIMoveTo (5 scripts), `0x1000000D` SetAITarget (9 scripts), `0x10000020` GetBestPerceivedTarget (1 script; the catalog
  called it CheckLineOfSight?), `0x100000F1` SetMovementMode (6), `0x1000001B` CancelMovement (10), and the `AIHandle`
  variable of 17 crowd-control status scripts (`0x340000C6`, `0x340000E0`, `0x34000130`..`132` ...: fear / taunt /
  stun override the AI).
- The minion, jungle and turret attack scripts (`0x34000087`, `0x34000088`, `0x340004A0`, `0x340004A1`, `0x34000014`,
  `0x3400027E`, `0x34000512`, `0x3400058F`) are basic-attack skills: they start on the skill-used event `0x1000001D`
  (trigger `0x1000013B`) with a target already chosen. Nothing in them looks for targets or moves.

### 5.2 Where the AI was (C / P)

The original server ran an engine AI for every entity whose 0x3A has `AIActive` (P): every
`GetBestPerceivedTargetInterval` (random 0.5..0.8 s) pick the best perceived enemy (vision `0x10000133`, detection list
`0x10000A3C`), move into range (`AIMoveTo`, half the attack range), and use the slot-0 skill on it (`SetAITarget`
mode 1 / 0). Structures do the same without moving. Leash / home return for camp units (`0x1000055A`) has no data
except the flag (P).

### 5.3 A complete AI written in script: `0x3400053A` (Starro's parasite) (C)

Starro's parasite (a minion taken over by Starro, script with StarroIID, Lifetime, ParasiteDetectRadius) runs the minion
logic in data, and is the best model for a server brain:
- graph S1 / S0 (targeting): every `random(GetBestPerceivedTargetInterval_Min, _Max)` (expression 0x14 with Min, Max: P a random value in the range)
  call `GetBestPerceivedTarget` `0x10000020(SELF, out TempTargetIID)[2, mask 8, ...]`, then again with mask `0x14118`;
  a hit sets `TargetIID` and `TargetPriority` (0, 1, 2, 5 by state: champion attacking a friend, unit, structure ...).
  With no target: `FindTargetsInRadius(FriendlyDetectRadius)` and `AIMoveTo(FollowDistance, FollowTarget)` = follow
  the owner.
- graph S4 (attack): `LoadSkillStats` range (stat 18), `AIMoveTo(HalfSkillRange, TargetIID, AttackingMoveToHandle)`
  and face the target (`0x1000003C`) while out of range; in range (`0x10000052` distance check) -> `SetAITarget(Target,
  SELF)[1]`, `[0]`, `CurrentlyAttacking = 1` (start auto-attacking); re-target when the timer ends or a higher priority
  appears (`5 > TargetPriority`).
- Zatanna's Merels `0x34000652` (pet): attach / detach to its owner, wander with `AIMoveTo` within
  MaxDistFromZatanna, reattach after a timer: the pet pattern.
- Doomsday Guardian `0x3400057A`: a boss ability loop (periodic ground pound on its AI target, `FindTargetsInRadius`
  knockdown) driven by the target the engine AI gives it (`0x1000000D` mode 1 in S2's update).

**For `ics`** (P): run a minion as `0x3400053A`'s graphs do, with these constants from the data: retarget 0.5..0.8 s
(`0x3A000026`), vision radius `0x10000133`, attack range stat 18 and attack script `0x100008E3`, move speed
`0x100005E4`, path on the map's navmesh (`ics.navmesh`) or the type-21 lane points. Implementing nodes 0x10000020,
0x1000004F, 0x1000000D, 0x1000003C in `ics/script_runtime.py` would also run the pets and the parasite unchanged.

## 6. Bots (AI champions)

- **Pools** (C): encounter template `0x10000B3E` (elements `0x10000B3D` = champion variant). Gotham Heights / Coast
  City / Gotham Divided v AI and GD Intermediate: 14 variants (Gaslight Batman `0x40000086` `0x40000549` `0x400003C7`,
  Gaslight Joker `0x4000038D` `0x40000610` `0x400007F3`, Superman `0x4000002B` `0x4000092D` `0x40000806`, Green Lantern
  `0x4000034D` `0x400006EB`, Atomic Wonder Woman `0x400003EC` `0x40000802`, Zatanna `0x4000015B`); Crime Alley v AI,
  the 1vAI tutorial and the two Defend Turret challenges: `0x40000BD3` (a Gaslight Batman costume variant: same
  template as `0x40000086` except model / icon / world state, no bot-only property); Multi-bot Push: both (15).
- **`0x10000B3F`** = 1 on every encounter with bots; **`0x10000B40`** = 1 only on the 5v5 vs AI ones (P: bots also fill
  the players' own team); `0x10000B3C` 10 / 2 (bot slots? P).
- **`0x10000CE0`** (C values, P meaning): one list per team of 5 enums `0x10000CDE` (team 1: 0xB, 7, 6, 9, 0xA;
  team 2: 8, 7, 6, 9, 0xA; Multi-bot Push has a third list): the role / lane of each bot slot.
- **Levelling script `0x10000B41` = `0x340007E2`** (C, decoded): variables CurrentLevel, Skill1Rank, Skill2Rank,
  Skill3Rank, SkillUltRank. Graph 0: on events `0x1000000C` / `0x10000088` (P: level up) it enters S1: GetLevel
  `0x1000004B`(CurrentLevel), node `0x10000189` (no operands, server-only: P "choose skill ranks for this level"), and
  on exit `InitSkill(rank, SELF)[slot 1..4]` for the four skills. Graph 1: while HasFlagAttribute `0x10000A23` (may
  shop: in base) run node `0x10000186` (no operands, server-only: P "bot shopping"). So the data gives the trigger
  points; the choices come from the champion's **default loadout** `0x10000CEB` (`Data.loadout`: `skill_order`
  `0x1000034B` = slot per level, recommended artifacts `0x10000478` in order, Stolen Power pair `0x1000064E`).
- **Difficulty**: no property, record or variable for it (C: searched templates, encounters, name tables). The two
  vs-AI tiers are separate encounters (GD v AI "beginner" `0x40000B6B` and "intermediate" `0x40000E62`) with the same
  pool and data (C), so the difference was server-side (P).
- **What `ics` needs to field a bot**: a champion object as for a player (variant, kit, stats `0x100008E2`), a brain
  (5.3 applied to a champion: target choice, skills by cooldown, retreat at low health / recall, lane from
  `0x10000CE0`), the levelling script `0x340007E2` with skill choices from `skill_order`, and shopping from the loadout
  when in base.

## 7. Spawners, waves and respawn

- **No wave, spawner or respawn data** (C): no record or property for wave composition, interval, spawn positions,
  jungle respawn time or camp positions in any pack; the map packs place no gameplay unit (searched the four PvP map
  packs for every unit world state: only random hits inside texture data).
- **What exists** (C): the spawner world state `0x2E000D03` (creation type 8, scriptlet tables `0x1D000385`,
  `0x1D000491` with `Vfx_Spawner_Tier01/02`) in the GH, CC, GD, T1 and CA packs; scriptlet keys in table 0x33000000:
  `_Generator_Self_PreWaveStart` `0x10000205`, `_Generator_Self_WaveStart` `0x10000204`, `_Generator_Self_OnObjectSpawned`
  `0x100003AB`, `_Generator_Self_OnCleared` `0x10000336`, `_Generator_Self_OnActivated` / `OnDeactivated` `0x10000B49` /
  `0x10000B48`, `_Generator_Self_OnPositionSetActivated` / `Deactivated` `0x10000B0F` / `0x10000B0E`,
  `_Generator_Target_OnUnsummoned` `0x10000202`, `Vfx_Spawner_Team01_Tier01`..`Team02_Tier02` `0x10000B16`..`B19`,
  `Leviathan_Spawn` / `Leviathan_Respawn` `0x10000E57` / `0x10000E56` (table `0x1D0006E6`). So the original server had a
  "Generator" object that spawned waves and told the client (P), with tiers (P: waves upgrade over time).
- **Crime Alley / Tutorial 2 layout `0xA00002E6`** (C) has the only placements: `01Spawner` / `01BlueSpawner`
  (`0x2E000D03` at (71.8, 77.5)) and groups `01MeleeA/B`, `01RangedA/B`, `01SiegeDrone`, `0nEnemyMelee/Ranged/Siege`
  with a path of 2..7 points each along y = 77.5; these are the Tutorial 2 cinematic actors (records `0x1D0007EE`,
  `0x3500002C`), not a wave definition. They do show a wave shape: 2 melee, 2 ranged, 1 siege per side (P).
- **Lanes**: type-21 points of the map pack (maps-encounters.md 2.3-2.6) and the navmesh (`ics.navmesh`).
- **To author** (server table, not code; P values from the original game's design are not in the data): wave interval,
  composition per lane and per wave tier (siege every N waves), spawn point per team and lane, jungle camp positions
  and respawn times, the boss respawn.

## 8. Open questions

- Meaning of `0x100003B0`, `0x10000642`, `0x10000975`, `0x10000934`, `0x1000025E`; the exact roles of `0x10000831` and
  `0x10000CE0`.
- GetAttribute modes 0 / 1 / 2; expression 0x0A (bitwise and?) and 0x35 (floor?) checked only by their call targets.
- Server-only nodes `0x10000186` / `0x10000189` (bot shopping / skill choice) and expression 0xC.
- Whether minions used `0x10000020`'s masks 8 / `0x14118` as their target filters (unit flags of champions and units).
