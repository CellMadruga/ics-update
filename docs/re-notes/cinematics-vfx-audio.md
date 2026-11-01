# Cinematics, VFX, animation events, audio and render state (static survey, 2026-10-21)

Scope: every piece of *presentation* data the server can trigger or has to keep consistent: all cinematic records
(`0x35`) of the install, every scriptlet table (`0x1D`) of every pack, the animation-graph event path, the audio
data (Wwise banks, lobby / match music, announcer tables, the encounter environment system) and the render-side
switches (lighting environment `0x956`, environment-state objects, fog). Read-only survey of the player's packs, the
Wwise packages in `audio\` and the client exe (capstone on `InfiniteCrisis.exe` of `C:\Infinite Crisis Server`).
Only IDs, short internal names, numbers and code addresses are recorded.

Marks: **C** = confirmed (parsed with a validating parser, or read in the client code); **P** = probable (strong
inference, not traced end to end); **?** = open. Scratch tools used (not part of the project, described in the
appendix): a strict cinematic parser, a pass of `ics.rp.script_tables` over all 616 packs, a parser of the enum
records of pack `0xA0000038`, a Wwise `AKPK` / `BKHD` / `HIRC` reader, `tools/script_decoder.py`'s `Decoder` on the
map packs' scripts (which `records()` does not find, see 1.4) and `ics.script_model` to describe them.

Related notes: `tutorial-data-inventory.md` (sections 4-5: the tutorial's cinematics and objects),
`actor-creation-and-environment.md` (how the client spawns cinematic actors, message `0x20F5`),
`targeting-and-relations.md` (team colour, `_Entity_OnSetClientRelationship`), `movement-collision-fog-map.md`
(fog of war), `maps-encounters.md` (encounter templates), `script-nodes-names.md` (script node table).

---------------------------------------------------------------------------------------------------------------------

## 0. Main findings (and corrections to earlier notes)

| # | Finding | Mark |
|---|---|---|
| 1 | **30 cinematic records exist, in 5 layout packs**: Gotham Heights `0xA000016B` (4), Coast City `0xA0000162` (3), Gotham Divided `0xA0000168` (3), Tutorial 1 `0xA0000256` (5), Crime Alley / Tutorial 2 `0xA00002E6` (15). One strict parser reads **all 30** and each record ends exactly where the next listed DID of the pack starts. | C |
| 2 | **Format correction**: a position key is not always 15 words. Its cell word carries a flag: bit `0x20` set (`0xFB`) = a quaternion follows; clear (`0xDB`) = no rotation (identity), 11 words. 11 of 581 keys have no rotation; with the fixed rule the 7 records that failed before (`0x3500000F`, `0x35000012/13`, `0x3500002A/2B/2C/30`) parse. | C |
| 3 | **The trailer "markers" are sounds**: `(frame, hash, 3)` entries of the trailer and of every actor's C list are **Wwise event ids**; all 38 resolve to an event of a bank in `audio\*.pck` (e.g. the intro's four trailer entries `0x8EAFAE21-24` are `AMB_Tutorial` events, Catwoman's cinematic ends with three `VO_Tutorial_Hero` events). The `3` is a type tag. | C |
| 4 | **Timeline events are script events, not always `0x10000060`**: 97 entries are `0x10000060` (the cinematic script's "next step" trigger), the victory cinematics raise `0x100000F2` / `0x100000F3` (which side won) and their script branches on them (`0x3400076B/C`: also `0x100000F1`). | C |
| 5 | **No client record names any cinematic** (aligned property / array scan of all 616 packs, plus the ~870 decoded scripts): the server alone decides when each of the 30 plays (message `0x20F5`). | C |
| 6 | **Wwise ids are FNV-1 32 of the lower-case name** (`Init` -> `0x50C63A23` = the `0x52000001` record's hash; `Music_Divided` -> `0x92012A6A`; `AMB_Tutorial` -> `0xFB803098`). `0x52` records = `did | bank id | len | name`. 161 named banks; the two `Audio_SB.pck` files hold 167 banks with 12 153 events. | C |
| 7 | **`CEncounterEnvironmentSystem` is the adaptive-music system**: every hash in its rule records (`0x100009D2` lists of the 6 encounter rule records named by `0x100009E7`) is an event of the map's `Music_<Map>` bank (Tutorial 1 uses `Music_Divided`, which its layout pack carries), plus one `UI` event. It is client-driven (cue ids from life-state / team counters). Earlier notes guessed "announcer / music". | C (hashes), P (music only) |
| 8 | **Script node `0x1000009C` = SetLightingEnvironment**: its client execute (vtable `0x15FA5A8` slot 10 = `0xAB4AE0`) sets (or with value 0 removes) property **`0x956`** on the local player's entity (`[0x1B6A710]`) and marks the world renderer dirty (`[0x1B73518]+0xF6 = 1`). Every cinematic script sets `0x10000016` on enter and 0 on exit; the victory scripts set `0x1000001B` (Coast City) / `0x1000001C`-style values. `0x7E35C0` (called from the render-model setup `0x7E66E8`) reads `0x956` on the local player first (default 2), then `0x5CC`, then `0x216`. | C (code), P (meaning of the values) |
| 9 | **`_CEntitySystem_EnvironmentStateChange` (`0x10000413`) is run by the client** when an entity's property `0x1000065C` / `0x1000065D` changes (listener `0xA813F0` -> `0xA7AFA0`, variable `0x1000069C` = new value); the listener is registered only on entities with bool `0x10000554`. 25 tables of the zone packs react to it. | C (code), ? (who sets the property) |
| 10 | **Script node `0x100000BB` = PlaySound(team filter, Wwise event)** with a client execute (`0xAB6820`) that compares the local player's team (`0x854050`) with the node's team value before playing. Its hashes resolve to `GlobalElements`, `UI`, `AMB_Tutorial` and `Music_Divided` events. | C (hash -> bank, team check), P (rest) |
| 11 | **Scriptlet tables: 2 083 table slots in 224 packs, 1 786 parsed (86 %), 1 323 distinct tables, 1 580 distinct keys, 6 127 key slots.** 1 576 keys are named by the scriptlet enum; 4 are small numbers (`0x1`, `0x5`, `0x14`, `0x16`). Of the 3 710 names, 2 134 are never a table key and 2 004 are used nowhere (712 of them `Vfx_Test_*`). | C (counts of what the finder finds) |
| 12 | The scriptlet name table the project calls `0x33000000` is held by the **enum record `0x30000013`** (base `0x300000EF`, 3 710 entries) of pack `0xA0000038`; the graph-event names are enum **`0x300000A4`** (base `0x30000127`, 1 298 entries). `0x33000000` / `0x33000001` are listed in the pack but their bodies are not this table. | C (record parsed), P (role of `0x33000000`) |
| 13 | The cinematic actor's two words after the actor variable are **`needs binding`** (1 = the actor stands for a player champion and is skipped when the server does not bind it; all 43 such actors are `ThePlayer` / `Player01..05` / the player's Gaslight Batman) and 0. A scriptlet entry's first flag word is 1 on 21 entries (repeated keys of the same actor). The last word of a scriptlet entry is the **scriptlet variable that receives the target actor's IID**: `0x10000030` (122) or `0x953` (15, the Tutorial 2 ranged drones). | C (layout), P (meaning) |

---------------------------------------------------------------------------------------------------------------------

## 1. Cinematics (`0x35`)

### 1.1 Format (holds for all 30 records, C)

```
did
u32 n_tracks          n_tracks x track
  track = u32 camera id (0x1000000E..0x10000017) | u32 n_keys | n_keys x key | u32 n_fov | n_fov x (u32 frame, f32 fov)
u32 n_actors          n_actors x actor
  actor = u32 len | name (padded to 4) | u32 world state (0x2E...) | u32 actor variable | u32 needs_binding | u32 0
        | property list (u32 n | n x (key | key' | value), kinds from properties.tsv)
        | u32 initial scriptlet (0 = none)
        | u32 n_keys | n_keys x key                       (path; 1 key = static)
        | u32 nA | nA x (u32 frame, u32 graph event)       (names: enum 0x300000A4)
        | u32 nC | nC x (u32 frame, u32 Wwise event, u32 3)
        | u32 nB | nB x scriptlet
  scriptlet = u32 frame | u32 key (enum 0x30000013) | u32 flag | u32 0 | property list (scriptlet variables)
            | u32 target actor variable (0 = none) | u32 variable that receives the target IID (0x10000030 / 0x953)
u32 n_cuts   | n_cuts x (u32 frame, u32 camera id)
u32 n_events | n_events x (u32 frame, u32 script event)     (raised to the cinematic's script)
u32 n_sounds | n_sounds x (u32 frame, u32 Wwise event, u32 3)
f32 duration (s)
u32 server script (0x34..., 0 = none)
key = u32 frame | u32 cell | u32 landblock x | u32 landblock y | f32 x, y, z
      | [f32 qw, qx, qy, qz  only when cell & 0x20]           (0xFB with, 0xDB without rotation)
      | u32 interpolation (0, 1, 2) | u32 (0; rarely an f32 such as 1.0) | f32 (0, -1.0, -0.6: tension?) | u32 0
```

* A frame is probably 1/30 s: the last frame used / duration is 25-31 in 22 records (intro: 1 160 / 38.5 s; `0x35000038`:
  2 200 / 72 s), 20 in the two GH core cinematics; `0x35000034` has its last VO sounds at 655-711, past its 15.75 s
  (they keep playing after the camera returns, P).
* Actor variables: `1` = the local player's champion; `0x10000001..0x10000005` = player slots (`Player01..05`);
  `0x10000015..0x1000001A` = names other actors target (e.g. the Destroyer, the enemy turret). P.
* Property lists hold the same properties as world states: `0x100007A2` side (1 PvE enemy, 3 team 1, 5 team 2),
  `0x1000009C` team, `0x954` the actor's extra scriptlet tables (element `0x462`), `0x6B3` / `0x6B4` scale,
  `0x974` / `0x975` / `0x973 = 0xFF000000` / `0x5F9` / `0x90F` on champions (`0x90F` = hidden), `0x10000CF0`
  colour override, `0x7BD` a vector scale, `0x2A1` / `0x4FD` flags. Scriptlet entries carry variables the same way
  (`Cinematic_Announcement {0x100008F6, 0x100008F7}` = the two team numbers; Batman's shot in `0x35000033`
  `{0x100002F8 FX, 0x10000126 particle, 0x10000205 world state}`).
* The client side (actor spawn, binding table, `0x20F5` mask) is in `actor-creation-and-environment.md`.

### 1.2 All cinematics

Landblock = the one most keys use (camera and actor keys). Cuts: `frame->camera` (low byte of `0x100000xx`).
Events without a name are `0x10000060`.

| Cinematic | Pack (map) | Landblock | Duration | Cameras / cuts | Actors | Timeline events (frame: event) | Pack-level sounds (frame: Wwise event -> bank) | Script |
|---|---|---|---|---|---|---|---|---|
| `0x3500000D` | `0xA000016B` (Gotham Heights) | 0x1BF3 | 10.50 s | 1 / 0->12 | 1 | - | - | none |
| `0x3500000E` | `0xA000016B` (Gotham Heights) | 0x1BF3 | 10.50 s | 1 / 0->12 | 1 | - | - | none |
| `0x3500000F` | `0xA000016B` (Gotham Heights) | 0x1BF3 | 0.00 s | 1 / 0->12 | 1 | - | - | none |
| `0x35000023` | `0xA000016B` (Gotham Heights) | 0x1BF3 | 13.00 s | 3 / 0->F, 120->E, 240->10 | 5 | 5 | - | `0x340006F2` |
| `0x35000012` | `0xA0000162` (Coast City) | 0x23E3 | 11.50 s | 3 / 0->12, 58->13, 165->14 | 6 | 225 `0x100000F2` | - | `0x3400076C` |
| `0x35000013` | `0xA0000162` (Coast City) | 0x23E3 | 11.50 s | 3 / 0->12, 58->13, 165->14 | 6 | 225 `0x100000F3` | - | `0x3400076C` |
| `0x35000020` | `0xA0000162` (Coast City) | 0x23E3 | 13.00 s | 3 / 0->F, 120->E, 240->10 | 5 | 5 | - | `0x340006F2` |
| `0x35000014` | `0xA0000168` (Gotham Divided) | 0x1BD3 | 11.50 s | 3 / 0->12, 58->13, 165->14 | 6 | 225 `0x100000F3` | - | `0x3400076B` |
| `0x35000015` | `0xA0000168` (Gotham Divided) | 0x1BD3 | 11.50 s | 3 / 0->12, 58->13, 165->14 | 6 | 225 `0x100000F2` | - | `0x3400076B` |
| `0x35000024` | `0xA0000168` (Gotham Divided) | 0x1BD3 | 13.00 s | 3 / 0->F, 120->E, 240->10 | 5 | 5 | - | `0x340006F2` |
| `0x35000025` | `0xA0000256` (Tutorial 1) | 0x14CB | 23.00 s | 1 / 0->12 | 3 | 15, 545 | 30: `0x3A8D9B09` Turrets, 170: `0x830AFF83` Turrets, 315: `0xA7E904EE` Turrets, 325: `0xF3BAE596` Turrets, 590: `0xBCDCC5EE` Turrets | `0x34000591` |
| `0x35000026` | `0xA0000256` (Tutorial 1) | 0x13CB | 38.50 s | 4 / 0->12, 200->13, 390->14, 660->15 | 26 | 10, 200, 390, 530, 655, 846 | 0: `0x8EAFAE21` AMB_Tutorial, 200: `0x8EAFAE22` AMB_Tutorial, 390: `0x8EAFAE23` AMB_Tutorial, 660: `0x8EAFAE24` AMB_Tutorial | `0x3400058A` |
| `0x35000028` | `0xA0000256` (Tutorial 1) | 0x13CB | 17.00 s | 1 / 0->12 | 5 | 15, 60, 195, 345 | 202: `0x29B4A687` GlobalElements | `0x34000595` |
| `0x35000033` | `0xA0000256` (Tutorial 1) | 0x13CB | 23.00 s | 1 / 0->12 | 4 | 14, 145, 300, 450, 580 | 202: `0x29B4A687` GlobalElements | `0x34000595` |
| `0x35000034` | `0xA0000256` (Tutorial 1) | 0x13CB | 15.75 s | 1 / 0->12 | 3 | 20, 200, 340, 653 | 143: `0xC63EC78A` chr_Catwoman_Gas, 145: `0xD0616E40` chr_Catwoman_Gas, 270: `0xDE233CE0` chr_Catwoman_Gas, 275: `0xE781618E` chr_Catwoman_Gas, 280: `0xC5046A44` chr_Catwoman_Gas, 655: `0xAD132783` VO_Tutorial_Hero, 682: `0xCC0762E5` VO_Tutorial_Hero, 711: `0x883D82A3` VO_Tutorial_Hero | `0x34000700` |
| `0x35000029` | `0xA00002E6` (Crime Alley / Tutorial 2) | 0x13C3 | 35.00 s | 3 / 0->13, 450->15, 720->14 | 7 | 15, 130, 210, 375, 475, 585, 720, 870 | 0: `0x1C343720` AMB_Tutorial | `0x340005DF` |
| `0x3500002A` | `0xA00002E6` (Crime Alley / Tutorial 2) | 0x13C3 | 52.00 s | 3 / 0->12, 335->13, 710->14, 960->13, 1225->14 | 10 | 10, 335, 450, 710, 855, 990, 1140, 1235 | - | `0x340005F4` |
| `0x3500002B` | `0xA00002E6` (Crime Alley / Tutorial 2) | 0x13C3 | 38.50 s | 3 / 0->12, 115->13, 675->14 | 11 | 10, 70, 120, 230, 320, 455, 520, 615, 685, 795, 915, 1005, 1060 | 750: `0x109A5F56` mse_Meteor, 1060: `0xEB685A04` mse_Meteor, 1100: `0xA50493D5` UI | `0x340005E5` |
| `0x3500002C` | `0xA00002E6` (Crime Alley / Tutorial 2) | 0x13C3 | 21.20 s | 2 / 0->12, 305->13 | 12 | 10, 155, 305, 475 | - | `0x34000605` |
| `0x3500002D` | `0xA00002E6` (Crime Alley / Tutorial 2) | 0x0105 | 0.00 s | 1 / 0->12 | 0 | 5 | - | `0x340006A2` |
| `0x3500002E` | `0xA00002E6` (Crime Alley / Tutorial 2) | 0x13BB | 21.00 s | 1 / 0->12 | 0 | 5 | - | `0x340006A8` |
| `0x3500002F` | `0xA00002E6` (Crime Alley / Tutorial 2) | 0x13BB | 17.00 s | 1 / 0->12, 0->12, 0->12 | 3 | 30, 60, 210 | - | `0x340006A5` |
| `0x35000030` | `0xA00002E6` (Crime Alley / Tutorial 2) | 0x13BB | 14.00 s | 1 / 0->12 | 2 | 5 | - | `0x340006A4` |
| `0x35000031` | `0xA00002E6` (Crime Alley / Tutorial 2) | 0x13BB | 12.00 s | 1 / 0->12 | 0 | 5 | - | `0x340006A3` |
| `0x35000032` | `0xA00002E6` (Crime Alley / Tutorial 2) | 0x13BB | 12.00 s | 1 / 0->12, 0->12, 0->12 | 0 | 5 | - | `0x340006A9` |
| `0x35000038` | `0xA00002E6` (Crime Alley / Tutorial 2) | 0x13BB | 72.00 s | 6 / 0->12, 58->13, 165->14, 455->15, 1200->16, 1385->17, 1590->16, 1865->15 | 12 | 195, 330, 490, 605, 660, 830, 875, 955, 1010, 1060, 1100, 1205, 1385, 1555, 1595, 1760, 1875, 1940, 2130 | 1100: `0x10780F78` AMB_Tutorial, 2070: `0xF152091A` UI | `0x34000733` |
| `0x35000039` | `0xA00002E6` (Crime Alley / Tutorial 2) | 0x13BB | 49.50 s | 3 / 0->12, 270->13, 425->14, 655->12, 810->13 | 1 | 10, 95, 150, 275, 370, 430, 545, 665, 825, 925, 1030, 1185 | 0: `0xD4797DE2` AMB_Tutorial, 265: `0xD4797DE1` AMB_Tutorial, 425: `0xD4797DE0` AMB_Tutorial, 805: `0xD4797DE7` AMB_Tutorial | `0x34000732` |
| `0x3500003A` | `0xA00002E6` (Crime Alley / Tutorial 2) | 0x13BB | 11.50 s | 3 / 0->12, 58->13, 165->14 | 3 | - | - | none |
| `0x3500003B` | `0xA00002E6` (Crime Alley / Tutorial 2) | 0x13BB | 11.50 s | 3 / 0->12, 58->13, 165->14 | 3 | - | - | none |
| `0x3500003C` | `0xA00002E6` (Crime Alley / Tutorial 2) | 0x13BB | 13.00 s | 3 / 0->F, 120->E, 240->10 | 1 | 5 | - | `0x340006F2` |

What each one is (from actors, scripts and map; P unless marked):

| Map / encounter | Cinematics | Role |
|---|---|---|
| Gotham Heights (`0x4000013E`, v AI `0x40000B6C`) | `0x35000023` | Match intro: 5 player actors (bound, `needs_binding`) start `Cinematic_Hidden` and appear one by one with `Cinematic_Intro` (frames 2, 30, 123, 155, 243); script `0x340006F2`. |
| | `0x3500000D` / `0x3500000E` | End of match per losing side: the base core (`0x2E000B47`, team 1 at (18.4, 50.1) / team 2 at (142.7, 50.3)) runs `Vfx_Startup`, `Vfx_Destruct_State0..3`, `Vfx_OnExplode`, then `Cinematic_Announcement` with the two team numbers. No script. |
| | `0x3500000F` | `Cinematic_Announcement` alone on world state `0x2E000D32` (duration 0). |
| Coast City (`0x40000270`, `0x4000039C`, v AI `0x40000B6A`) | `0x35000020` | Match intro (as `0x35000023`). |
| | `0x35000012` / `0x35000013` | Victory: the losing core (`0x2E0013EE`) `Vfx_Destruct_State0`; 5 bound players `Cinematic_Startup` + `Cinematic_Victory`; event `0x100000F2` / `0x100000F3` at 225 (script `0x3400076C`: objective text 29 with team args, or 395 on `0x100000F1`). |
| Gotham Divided (`0x40000399`, v AI `0x40000B6B`, `0x40000E62`) | `0x35000024`, `0x35000014` / `0x35000015` | Intro and the two victories (script `0x3400076B`). Core world state `0x2E000AC5` (the tutorial's power core). |
| Tutorial 1 (`0x40000991`) | `0x35000026`, `0x35000033`, `0x35000034`, `0x35000028`, `0x35000025` | See `tutorial-data-inventory.md` section 4 (corrected here: the "markers" are sounds). |
| Tutorial 2 (`0x40000A81`, landblock `0x13C3`) | `0x35000029` (spawner + drone wave to the player's core), `0x3500002A` (turrets: friendly / enemy turret and plate, 4 drones walk in and die to it, Green Lantern), `0x3500002B` (Batman by the enemy turret, meteors: `Crater1-3` `Object_Closed`, `mse_Meteor` sounds), `0x3500002C` (blue spawner, own drone wave vs enemy wave, siege drones) | Lesson cinematics; scripts `0x340005DF`, `0x340005F4`, `0x340005E5`, `0x34000605` start conversations 503-504 / 891-896, 498-543 / 888-890, 518-528 / 946-953, 513 / 519 / 944 / 945. |
| Crime Alley (`0xA0C112BA`, landblock `0x13BB`: v AI `0x40000C82`, 1vAI tutorial `0x40000CA6`, Clashes) | `0x3500003C` | Intro (one bound player). |
| | `0x3500003A` / `0x3500003B` | Victory per side (core `0x2E000AC5` + `Cinematic_Announcement`; 2 bound players). No script. |
| | `0x35000038` (72 s), `0x35000039` (49.5 s) | 1vAI tutorial opening / closing pieces: Gaslight Batman, Superman, Wonder Woman, Green Lantern, Harley Quinn, Doomsday, corrupted GasBot, turrets; scripts `0x34000733` (19 conversation starts, 910-942) and `0x34000732`. |
| | `0x3500002E`, `0x35000031`, `0x35000032` (no actors), `0x3500002F` (corrupted GasBat knocks the player down: `CbtState_Death_Induce`, `GetUp`), `0x35000030` (`ImpactPoint` + `Wall`) | Short beats of the 1vAI tutorial; scripts `0x340006A8`, `0x340006A3`, `0x340006A9`, `0x340006A5`, `0x340006A4` (conversations 320/324/366/313, 297, 359/362, 336/315, 337). |
| (none) | `0x3500002D` | Camera only, duration 0, landblock `0x0105`; script `0x340006A2` (conversation 301). |

### 1.3 Actors of every cinematic

Columns as in 1.1. `Bind` = `needs_binding`. Long scriptlet / graph lists are summarised as `name xN (first-last
frame)`. Positions are in the cinematic's landblock frame.


#### `0x3500000D` (Gotham Heights, 10.50 s)

| Actor | World state | Var | Bind | Props | Init | Path (keys: start -> end) | Graph events (frame) | Sounds (frame: event -> bank) | Scriptlets (frame: key [-> target var]) |
|---|---|---|---|---|---|---|---|---|---|
| Character_0 | `0x2E000B47` | - |  | side 3; team 1 | - | 1: 0 (18.39, 50.08, 252.50) | - | - | 2 Vfx_Startup; 63 Vfx_Destruct_State0; 75 Vfx_Destruct_State1; 90 Vfx_Destruct_State2; 98 Vfx_Destruct_State3; 120 Vfx_OnExplode; 210 Cinematic_Announcement {0x100008F6=0x1, 0x100008F7=0x2} |

#### `0x3500000E` (Gotham Heights, 10.50 s)

| Actor | World state | Var | Bind | Props | Init | Path (keys: start -> end) | Graph events (frame) | Sounds (frame: event -> bank) | Scriptlets (frame: key [-> target var]) |
|---|---|---|---|---|---|---|---|---|---|
| Character_0 | `0x2E000B47` | - |  | side 5; team 2 | - | 1: 0 (142.67, 50.33, 252.50) | - | - | 2 Vfx_Startup; 63 Vfx_Destruct_State0; 75 Vfx_Destruct_State1; 90 Vfx_Destruct_State2; 98 Vfx_Destruct_State3; 120 Vfx_OnExplode; 210 Cinematic_Announcement {0x100008F6=0x2, 0x100008F7=0x1} |

#### `0x3500000F` (Gotham Heights, 0.00 s)

| Actor | World state | Var | Bind | Props | Init | Path (keys: start -> end) | Graph events (frame) | Sounds (frame: event -> bank) | Scriptlets (frame: key [-> target var]) |
|---|---|---|---|---|---|---|---|---|---|
| Character_0 | `0x2E000D32` | - |  | - | - | 1: 0 (80.00, 112.00, 250.00) | - | - | 60 Cinematic_Announcement |

#### `0x35000023` (Gotham Heights, 13.00 s)

| Actor | World state | Var | Bind | Props | Init | Path (keys: start -> end) | Graph events (frame) | Sounds (frame: event -> bank) | Scriptlets (frame: key [-> target var]) |
|---|---|---|---|---|---|---|---|---|---|
| Chr_Center - ThePlayer | `0x2E00028B` | player | yes | `0x974` 1; `0x5F9` 1; `0x975` 1; hidden 1; `0x973` 0xFF000000 | Cinematic_Hidden | 1: 0 (80.00, 15.09, 249.94) | - | - | 243 Cinematic_Intro |
| Chr_MidLeft - Player02 | `0x2E000B86` | `0x10000002` | yes | `0x974` 1; `0x5F9` 1; `0x975` 1; hidden 1; `0x973` 0xFF000000 | Cinematic_Hidden | 1: 0 (76.54, 17.09, 249.94) | - | - | 30 Cinematic_Intro |
| Chr_Left - Player01 | `0x2E000157` | `0x10000001` | yes | `0x974` 1; `0x5F9` 1; `0x975` 1; hidden 1; `0x973` 0xFF000000 | Cinematic_Hidden | 1: 0 (73.07, 19.09, 249.94) | - | - | 2 Cinematic_Intro |
| Chr_Right - Player03 | `0x2E00096E` | `0x10000003` | yes | `0x974` 1; `0x5F9` 1; `0x975` 1; hidden 1; `0x973` 0xFF000000 | Cinematic_Hidden | 1: 0 (86.93, 21.01, 249.94) | - | - | 123 Cinematic_Intro |
| Chr_MidRight - Player04 | `0x2E0007C0` | `0x10000004` | yes | `0x974` 1; `0x5F9` 1; `0x975` 1; hidden 1; `0x973` 0xFF000000 | Cinematic_Hidden | 1: 0 (83.46, 17.09, 249.94) | - | - | 155 Cinematic_Intro |

#### `0x35000012` (Coast City, 11.50 s)

| Actor | World state | Var | Bind | Props | Init | Path (keys: start -> end) | Graph events (frame) | Sounds (frame: event -> bank) | Scriptlets (frame: key [-> target var]) |
|---|---|---|---|---|---|---|---|---|---|
| PowerCore | `0x2E0013EE` | - |  | side 5; team 2 | - | 1: 0 (143.00, 62.50, 249.98) | - | - | 0 Vfx_Destruct_State0 |
| Player01 | `0x2E00028B` | `0x10000001` | yes | `0x974` 1; `0x975` 1; `0x973` 0xFF000000 | Cinematic_Startup | 1: 0 (137.47, 60.22, 250.19) | - | - | 0 Cinematic_Victory |
| Player02 | `0x2E000B86` | `0x10000002` | yes | `0x974` 1; `0x975` 1; `0x973` 0xFF000000 | Cinematic_Startup | 1: 0 (146.88, 57.39, 250.20) | - | - | 0 Cinematic_Victory |
| Player03 | `0x2E00096E` | `0x10000003` | yes | `0x974` 1; `0x975` 1; `0x973` 0xFF000000 | Cinematic_Startup | 1: 0 (143.37, 56.42, 250.19) | - | - | 0 Cinematic_Victory |
| Player04 | `0x2E000157` | `0x10000004` | yes | `0x974` 1; `0x975` 1; `0x973` 0xFF000000 | Cinematic_Startup | 1: 0 (136.04, 63.28, 250.21) | - | - | 0 Cinematic_Victory |
| Player05 | `0x2E0007C0` | `0x10000005` | yes | `0x974` 1; `0x975` 1; `0x973` 0xFF000000 | Cinematic_Startup | 1: 0 (139.20, 67.23, 250.19) | - | - | 0 Cinematic_Victory |

#### `0x35000013` (Coast City, 11.50 s)

| Actor | World state | Var | Bind | Props | Init | Path (keys: start -> end) | Graph events (frame) | Sounds (frame: event -> bank) | Scriptlets (frame: key [-> target var]) |
|---|---|---|---|---|---|---|---|---|---|
| PowerCore | `0x2E0013EE` | - |  | side 3; team 1 | - | 1: 0 (17.00, 62.50, 249.98) | - | - | 0 Vfx_Destruct_State0 |
| Player01 | `0x2E00028B` | `0x10000001` | yes | `0x974` 1; `0x975` 1; `0x973` 0xFF000000 | Cinematic_Startup | 1: 0 (20.19, 57.44, 250.20) | - | - | 0 Cinematic_Victory |
| Player02 | `0x2E000B86` | `0x10000002` | yes | `0x974` 1; `0x975` 1; `0x973` 0xFF000000 | Cinematic_Startup | 1: 0 (13.25, 57.82, 250.20) | - | - | 0 Cinematic_Victory |
| Player03 | `0x2E00096E` | `0x10000003` | yes | `0x974` 1; `0x975` 1; `0x973` 0xFF000000 | Cinematic_Startup | 1: 0 (16.86, 56.23, 250.20) | - | - | 0 Cinematic_Victory |
| Player04 | `0x2E000157` | `0x10000004` | yes | `0x974` 1; `0x975` 1; `0x973` 0xFF000000 | Cinematic_Startup | 1: 0 (23.60, 63.11, 250.21) | - | - | 0 Cinematic_Victory |
| Player05 | `0x2E0007C0` | `0x10000005` | yes | `0x974` 1; `0x975` 1; `0x973` 0xFF000000 | Cinematic_Startup | 1: 0 (20.97, 67.40, 250.15) | - | - | 0 Cinematic_Victory |

#### `0x35000020` (Coast City, 13.00 s)

| Actor | World state | Var | Bind | Props | Init | Path (keys: start -> end) | Graph events (frame) | Sounds (frame: event -> bank) | Scriptlets (frame: key [-> target var]) |
|---|---|---|---|---|---|---|---|---|---|
| Chr_Center - ThePlayer | `0x2E00028B` | player | yes | `0x974` 1; `0x5F9` 1; `0x975` 1; hidden 1; `0x973` 0xFF000000 | Cinematic_Hidden | 1: 0 (80.00, 19.00, 249.97) | - | - | 243 Cinematic_Intro |
| Chr_MidLeft - Player02 | `0x2E000B86` | `0x10000002` | yes | `0x974` 1; `0x5F9` 1; `0x975` 1; hidden 1; `0x973` 0xFF000000 | Cinematic_Hidden | 1: 0 (76.54, 21.00, 249.97) | - | - | 30 Cinematic_Intro |
| Chr_Left - Player01 | `0x2E00096E` | `0x10000001` | yes | `0x974` 1; `0x5F9` 1; `0x975` 1; hidden 1; `0x973` 0xFF000000 | Cinematic_Hidden | 1: 0 (73.07, 23.00, 249.97) | - | - | 2 Cinematic_Intro |
| Chr_Right - Player03 | `0x2E000157` | `0x10000003` | yes | `0x974` 1; `0x5F9` 1; `0x975` 1; hidden 1; `0x973` 0xFF000000 | Cinematic_Hidden | 1: 0 (86.93, 23.00, 249.97) | - | - | 123 Cinematic_Intro |
| Chr_MidRight - Player04 | `0x2E0007C0` | `0x10000004` | yes | `0x974` 1; `0x5F9` 1; `0x975` 1; hidden 1; `0x973` 0xFF000000 | Cinematic_Hidden | 1: 0 (83.46, 21.00, 249.97) | - | - | 155 Cinematic_Intro |

#### `0x35000014` (Gotham Divided, 11.50 s)

| Actor | World state | Var | Bind | Props | Init | Path (keys: start -> end) | Graph events (frame) | Sounds (frame: event -> bank) | Scriptlets (frame: key [-> target var]) |
|---|---|---|---|---|---|---|---|---|---|
| PowerCore | `0x2E000AC5` | - |  | side 3; team 1 | - | 1: 0 (17.50, 142.50, 250.00) | - | - | 0 Vfx_Destruct_State0 |
| Player01 | `0x2E00028B` | `0x10000001` | yes | `0x974` 1; `0x975` 1; `0x973` 0xFF000000 | Cinematic_Startup | 1: 0 (19.61, 137.09, 250.22) | - | - | 0 Cinematic_Victory |
| Player02 | `0x2E000B86` | `0x10000002` | yes | `0x974` 1; `0x975` 1; `0x973` 0xFF000000 | Cinematic_Startup | 1: 0 (15.23, 136.65, 250.22) | - | - | 0 Cinematic_Victory |
| Player03 | `0x2E00096E` | `0x10000003` | yes | `0x974` 1; `0x975` 1; `0x973` 0xFF000000 | Cinematic_Startup | 1: 0 (11.80, 139.73, 250.22) | - | - | 0 Cinematic_Victory |
| Player04 | `0x2E000157` | `0x10000004` | yes | `0x974` 1; `0x975` 1; `0x973` 0xFF000000 | Cinematic_Startup | 1: 0 (23.90, 144.25, 250.22) | - | - | 0 Cinematic_Victory |
| Player05 | `0x2E0007C0` | `0x10000005` | yes | `0x974` 1; `0x975` 1; `0x973` 0xFF000000 | Cinematic_Startup | 1: 0 (20.56, 148.02, 250.17) | - | - | 0 Cinematic_Victory |

#### `0x35000015` (Gotham Divided, 11.50 s)

| Actor | World state | Var | Bind | Props | Init | Path (keys: start -> end) | Graph events (frame) | Sounds (frame: event -> bank) | Scriptlets (frame: key [-> target var]) |
|---|---|---|---|---|---|---|---|---|---|
| PowerCore | `0x2E000AC5` | - |  | side 5; team 2 | - | 1: 0 (142.50, 17.50, 250.02) | - | - | 0 Vfx_Destruct_State0 |
| Player01 | `0x2E00028B` | `0x10000001` | yes | `0x974` 1; `0x975` 1; `0x973` 0xFF000000 | Cinematic_Startup | 1: 0 (136.79, 18.28, 250.20) | - | - | 0 Cinematic_Victory |
| Player02 | `0x2E000B86` | `0x10000002` | yes | `0x974` 1; `0x975` 1; `0x973` 0xFF000000 | Cinematic_Startup | 1: 0 (139.40, 11.47, 250.05) | - | - | 0 Cinematic_Victory |
| Player03 | `0x2E00096E` | `0x10000003` | yes | `0x974` 1; `0x975` 1; `0x973` 0xFF000000 | Cinematic_Startup | 1: 0 (148.57, 20.34, 250.10) | - | - | 0 Cinematic_Victory |
| Player04 | `0x2E000157` | `0x10000004` | yes | `0x974` 1; `0x975` 1; `0x973` 0xFF000000 | Cinematic_Startup | 1: 0 (136.12, 14.48, 250.05) | - | - | 0 Cinematic_Victory |
| Player05 | `0x2E0007C0` | `0x10000005` | yes | `0x974` 1; `0x975` 1; `0x973` 0xFF000000 | Cinematic_Startup | 1: 0 (146.65, 23.33, 250.10) | - | - | 0 Cinematic_Victory |

#### `0x35000024` (Gotham Divided, 13.00 s)

| Actor | World state | Var | Bind | Props | Init | Path (keys: start -> end) | Graph events (frame) | Sounds (frame: event -> bank) | Scriptlets (frame: key [-> target var]) |
|---|---|---|---|---|---|---|---|---|---|
| Chr_Center - ThePlayer | `0x2E00028B` | player | yes | `0x974` 1; `0x5F9` 1; `0x975` 1; hidden 1; `0x973` 0xFF000000 | Cinematic_Hidden | 1: 0 (34.00, 34.00, 250.05) | - | - | 243 Cinematic_Intro |
| Chr_MidLeft - Player02 | `0x2E000B86` | `0x10000002` | yes | `0x974` 1; `0x5F9` 1; `0x975` 1; hidden 1; `0x973` 0xFF000000 | Cinematic_Hidden | 1: 0 (32.96, 37.86, 250.15) | - | - | 30 Cinematic_Intro |
| Chr_Left - Player01 | `0x2E00096E` | `0x10000001` | yes | `0x974` 1; `0x5F9` 1; `0x975` 1; hidden 1; `0x973` 0xFF000000 | Cinematic_Hidden | 1: 0 (31.93, 41.73, 250.05) | - | - | 2 Cinematic_Intro |
| Chr_Right - Player03 | `0x2E000157` | `0x10000003` | yes | `0x974` 1; `0x5F9` 1; `0x975` 1; hidden 1; `0x973` 0xFF000000 | Cinematic_Hidden | 1: 0 (41.73, 31.93, 250.05) | - | - | 123 Cinematic_Intro |
| Chr_MidRight - Player04 | `0x2E0007C0` | `0x10000004` | yes | `0x974` 1; `0x5F9` 1; `0x975` 1; hidden 1; `0x973` 0xFF000000 | Cinematic_Hidden | 1: 0 (37.86, 32.96, 250.10) | - | - | 155 Cinematic_Intro |

#### `0x35000025` (Tutorial 1, 23.00 s)

| Actor | World state | Var | Bind | Props | Init | Path (keys: start -> end) | Graph events (frame) | Sounds (frame: event -> bank) | Scriptlets (frame: key [-> target var]) |
|---|---|---|---|---|---|---|---|---|---|
| GaslightBatman | `0x2E0001B2` | - |  | `0x974` 1; `0x975` 1; `0x973` 0xFF000000 | - | 3: 0 (158.47, 30.77, 200.16) -> 175 (11.69, 32.53) lb 0x13CB | - | - | - |
| Gate | `0x2E000CD7` | - |  | side 3; scale 0.90; tables `0x1D000789` | CinematicCharacter_State00 | 1: 0 (159.86, 28.04, 200.10) lb 0x13CB | - | - | 0 CinematicCharacter_State00; 30 CinematicCharacter_State00 (flag 1) |
| PowerCore | `0x2E000AC5` | - |  | side 3; tables `0x1D00078A` | CinematicCharacter_State00 | 1: 0 (17.50, 37.50, 200.12) | - | - | 140 CinematicCharacter_State01; 293 CinematicCharacter_State02; 300 CinematicCharacter_State04; 305 CinematicCharacter_State03 |

#### `0x35000026` (Tutorial 1, 38.50 s)

| Actor | World state | Var | Bind | Props | Init | Path (keys: start -> end) | Graph events (frame) | Sounds (frame: event -> bank) | Scriptlets (frame: key [-> target var]) |
|---|---|---|---|---|---|---|---|---|---|
| 01RangedA | `0x2E001168` | - |  | side 1; `0x100007D3` (-0.12, 3.00, 0.25); `0x100007CF` 3.00; `0x10000B3B` 1 | _Entity_OnSetClientRelationship | 1: 0 (156.91, 30.75, 200.00) | - | - | 195 CinematicAttack_Ranged; 255 CinematicAttack_Ranged; 320 CinematicAttack_Ranged |
| 01MeleeA | `0x2E001167` | - |  | side 1; `0x10000B3B` 1 | _Entity_OnSetClientRelationship | 1: 0 (158.98, 28.95, 200.00) | - | - | 205 CinematicAttack_Melee; 270 CinematicAttack_Melee; 330 CinematicAttack_Melee |
| 01MeleeB | `0x2E001167` | - |  | side 1; `0x10000B3B` 1 | _Entity_OnSetClientRelationship | 1: 0 (158.99, 32.46, 200.00) | - | - | 200 CinematicAttack_Melee; 265 CinematicAttack_Melee; 325 CinematicAttack_Melee |
| 02Destroyer | `0x2E000AB5` | `0x10000015` |  | side 1; 0x450 1.50; tables `0x1D0007A4`, `0x1D000385` | _Entity_OnSetClientRelationship | 9: 0 (113.75, 123.00, 200.00) -> 635 (95.25, 125.75) | 465 Combat_Special_Attack_2 | - | 473 CinematicCharacter_State00; 636 CinematicCharacter_State01 |
| 02GaslightBatman | `0x2E0001B2` | - |  | `0x974` 1; `0x975` 1; `0x973` 0xFF000000; tables `0x1D000771` | - | 7: 0 (96.00, 122.50, 200.00) -> 700 (67.90, 106.24) | 480 CbtState_Knockdown; 500 CbtState_GetUp | - | 395 Combat_Basic_Attack_Left -> `0x10000015`; 415 Combat_Basic_Attack_Right -> `0x10000015`; 435 Combat_Basic_Attack_Left -> `0x10000015`; 455 Combat_Basic_Attack_Right -> `0x10000015` |
| 02PaddyWagonA | `0x2E00034D` | - |  | - | - | 1: 0 (101.98, 119.05, 199.98) | - | 473: `0x7B0240B1` Destruction | 473 Vfx_OnExplode |
| 02PaddyWagonB | `0x2E00034E` | - |  | - | - | 1: 0 (102.45, 126.62, 200.10) | - | - | 474 Vfx_OnExplode |
| 02MeleeA | `0x2E001167` | - |  | side 1 | _Entity_OnSetClientRelationship | 1: 0 (94.47, 132.52, 201.20) | - | - | 520 CinematicAttack_Loop; 655 CinematicAttack_Loop (flag 1) |
| 02RangedA | `0x2E001168` | - |  | side 1; `0x100007D3` (-0.40, 4.50, 0.25); `0x100007CF` 4.50 | _Entity_OnSetClientRelationship | 2: 0 (95.00, 112.17, 200.00) -> 389 (95.00, 111.88) | - | - | 470 CinematicAttack_Loop; 655 CinematicAttack_Loop (flag 1) |
| 02MeleeB | `0x2E001167` | - |  | side 1 | _Entity_OnSetClientRelationship | 1: 0 (97.64, 105.78, 199.98) | - | - | 555 CinematicAttack_Loop; 655 CinematicAttack_Loop (flag 1) |
| 02MeleeC | `0x2E001167` | - |  | side 1 | _Entity_OnSetClientRelationship | 2: 555 (79.13, 127.26, 200.00) -> 715 (92.12, 119.76) | - | - | - |
| 02RangedB | `0x2E001168` | - |  | side 1; `0x100007D3` (-0.50, 5.00, 0.25); `0x100007CF` 5.00 | _Entity_OnSetClientRelationship | 1: 0 (93.89, 104.68, 199.98) | - | - | 565 CinematicAttack_Loop; 655 CinematicAttack_Loop (flag 1) |
| 02MeleeD | `0x2E001167` | - |  | side 1 | _Entity_OnSetClientRelationship | 2: 560 (77.38, 126.09, 200.00) -> 720 (90.37, 118.59) | - | - | - |
| 03ThugA | `0x2E0012BB` | - |  | tables `0x1D000890` | - | 1: 0 (44.22, 59.02, 199.99) | 0 SpawnIdle | - | - |
| 03MeleeA | `0x2E001167` | - |  | side 1 | _Entity_OnSetClientRelationship | 2: 640 (49.36, 49.34, 200.05) -> 860 (66.62, 39.59) | - | - | - |
| 03MeleeB | `0x2E001167` | - |  | side 1 | _Entity_OnSetClientRelationship | 2: 640 (47.87, 46.76, 200.08) -> 860 (65.49, 38.99) | - | - | - |
| 03RangedA | `0x2E001168` | - |  | side 1 | _Entity_OnSetClientRelationship | 2: 640 (46.58, 50.33, 199.93) -> 857 (64.36, 41.63) | - | - | - |
| 03RangedB | `0x2E001168` | - |  | side 1 | _Entity_OnSetClientRelationship | 2: 640 (45.61, 48.59, 199.93) -> 857 (62.79, 40.62) | - | - | - |
| 03ThugB | `0x2E0012BB` | `0x10000005` |  | - | - | 3: 0 (34.92, 57.60, 199.93) -> 870 (34.92, 57.44) | - | - | CinematicAttack_Melee x11 (720-1160); targets `0x10000017`, `0x10000018` |
| 03MeleeC | `0x2E001167` | `0x10000017` |  | side 1 | _Entity_OnSetClientRelationship | 1: 0 (35.34, 56.35, 199.95) | - | - | CinematicAttack_Melee x12 (705-1150); targets `0x10000005` |
| 03MeleeD | `0x2E001167` | `0x10000018` |  | side 1; tables `0x1D0007EE` | _Entity_OnSetClientRelationship | 1: 0 (36.26, 57.69, 199.95) | - | - | 745 CinematicAttack_Melee -> `0x10000005`; 785 CinematicAttack_Melee -> `0x10000005`; 819 CinematicAttack_Melee; 820 CinematicCharacter_Die |
| 03GasJoker | `0x2E00095E` | - |  | - | - | 4: 0 (40.69, 70.92, 199.93) -> 860 (40.69, 86.89) | - | - | - |
| 03GateA | `0x2E0010F3` | - |  | - | - | 1: 0 (54.05, 44.80, 200.08) | - | - | - |
| 03GateB | `0x2E0010F3` | - |  | - | - | 1: 0 (89.87, 26.21, 200.16) | - | - | - |
| DestVehicle | `0x2E000AAB` | - |  | - | - | 1: 0 (43.66, 52.61, 199.86) | - | - | - |
| 01GateA | `0x2E000CD7` | - |  | side 3; 0x6B3 0.90 | _Entity_OnSetClientRelationship | 1: 0 (159.86, 28.04, 200.10) | - | - | Object_Closed x7 (0-351); Object_Melee_Attack x6 (205-350) |

#### `0x35000028` (Tutorial 1, 17.00 s)

| Actor | World state | Var | Bind | Props | Init | Path (keys: start -> end) | Graph events (frame) | Sounds (frame: event -> bank) | Scriptlets (frame: key [-> target var]) |
|---|---|---|---|---|---|---|---|---|---|
| Destroyer | `0x2E000AB5` | - |  | side 1; scale 0.85; tables `0x1D000774`, `0x1D000385` | Cinematic_Hidden | 1: 0 (152.75, 24.00, 200.10) | - | - | 115 _Entity_OnSetClientRelationship; 125 Cinematic_Startup |
| Melee1 | `0x2E001167` | - |  | side 1 | _Entity_OnSetClientRelationship | 3: 0 (151.72, 25.82, 200.09) -> 425 (141.68, 17.89) | - | - | 1 Cinematic_Hidden; 125 Cinematic_Intro |
| Melee2 | `0x2E001167` | - |  | side 1 | _Entity_OnSetClientRelationship | 3: 0 (153.93, 22.52, 200.13) -> 425 (143.51, 15.92) | - | - | 1 Cinematic_Hidden; 125 Cinematic_Intro |
| Ranged1 | `0x2E001168` | - |  | side 1 | _Entity_OnSetClientRelationship | 3: 0 (152.79, 26.58, 200.29) -> 445 (142.32, 18.31) | - | - | 1 Cinematic_Hidden; 125 Cinematic_Intro |
| Ranged2 | `0x2E001168` | - |  | side 1 | _Entity_OnSetClientRelationship | 3: 0 (155.20, 23.60, 200.13) -> 445 (143.97, 16.31) | - | - | 1 Cinematic_Hidden; 125 Cinematic_Intro |

#### `0x35000033` (Tutorial 1, 23.00 s)

| Actor | World state | Var | Bind | Props | Init | Path (keys: start -> end) | Graph events (frame) | Sounds (frame: event -> bank) | Scriptlets (frame: key [-> target var]) |
|---|---|---|---|---|---|---|---|---|---|
| Drone_01 | `0x2E001167` | `0x10000015` |  | side 1; tables `0x1D000774` | _Entity_OnEnterWorld_Default | 1: 0 (34.98, 56.32, 199.95) | CinematicCombatBasicAttack x5 (20-180); CbtState_Death_Induce x1 (218-218) | 231: `0x2036D52C` chr_Batman_Gas | 231 Vfx_OnExplode |
| Thug_01 | `0x2E0012BB` | - |  | - | - | 1: 0 (34.61, 57.73, 199.93) | CinematicCombatBasicAttack x6 (5-205) | - | 236 _Defeat_OnDead |
| Gaslight_Batman_01 | `0x2E0001B2` | player |  | `0x974` 1; `0x975` 1; `0x973` 0xFF000000; tables `0x1D000771` | - | 3: 0 (37.64, 58.36, 199.93) -> 530 (39.59, 58.36) | - | - | 159 Combat_Basic_Attack_Left -> `0x10000015`; 165 Vfx_Bmg_Basic_Ranged_Left -> `0x10000015` {0x100002F8=0x1E000023, 0x10000126=0x1800012A, 0x10000205=0x2E000222}; 205 Combat_Basic_Attack_Right -> `0x10000015`; 210 Vfx_Bmg_Basic_Ranged_Right -> `0x10000015` {0x100002F8=0x1E000023, 0x10000126=0x1800012A, 0x10000205=0x2E000222} |
| Thug_02 | `0x2E0012BB` | - |  | - | Vfx_SpawnIdle | 1: 0 (44.27, 58.97, 199.93) | 0 SpawnIdle | - | 400 Vfx_Spawn |

#### `0x35000034` (Tutorial 1, 15.75 s)

| Actor | World state | Var | Bind | Props | Init | Path (keys: start -> end) | Graph events (frame) | Sounds (frame: event -> bank) | Scriptlets (frame: key [-> target var]) |
|---|---|---|---|---|---|---|---|---|---|
| Gaslight_Batman | `0x2E0001B2` | player |  | `0x5F9` 1; `0x974` 1; tables `0x1D000771`; `0x975` 1; `0x973` 0xFF000000 | Fidgets_Disable | 7: 0 (40.69, 58.23, 199.98) -> 450 (42.43, 55.59) | - | - | - |
| Gaslight_Catwoman | `0x2E0007C0` | `0x10000002` |  | `0x974` 1; `0x975` 1; `0x973` 0xFF000000; tables `0x1D0008C2`, `0x1D000233` | - | 9: 0 (52.87, 44.12, 200.09) -> 390 (33.37, 63.14) | - | - | 135 Combat_Basic_Attack; 146 CinematicCharacter_State02 -> `0x10000015`; 270 Vfx_Glc_Stalking_Strike_Start; 275 Vfx_Glc_Stalking_Strike_Active |
| InvisibleTarget | `0x2E000002` | `0x10000015` |  | tables `0x1D0000E1` | - | 1: 0 (43.66, 52.61, 201.36) | - | - | - |

#### `0x35000029` (Crime Alley / Tutorial 2, 35.00 s)

| Actor | World state | Var | Bind | Props | Init | Path (keys: start -> end) | Graph events (frame) | Sounds (frame: event -> bank) | Scriptlets (frame: key [-> target var]) |
|---|---|---|---|---|---|---|---|---|---|
| 01MeleeA | `0x2E001167` | - |  | side 1 | Cinematic_Hidden | 4: 75 (71.75, 77.50, 200.00) -> 590 (20.90, 77.95) | CinematicCombatBasicAttack x9 (600-1000) | - | 60 Cinematic_Intro |
| 01MeleeB | `0x2E001167` | - |  | side 1 | Cinematic_Hidden | 7: 105 (71.75, 77.50, 200.00) -> 637 (21.15, 76.60) | CinematicCombatBasicAttack x8 (645-995) | - | 90 Cinematic_Intro |
| 01RangedA | `0x2E001168` | - |  | side 1; tables `0x1D0007EE` | Cinematic_Hidden | 7: 135 (71.75, 77.50, 200.00) -> 640 (24.39, 78.29) | - | - | 120 Cinematic_Intro; CinematicAttack_Ranged x8 (650-1000); targets `0x10000001` |
| 01RangedB | `0x2E001168` | - |  | side 1; tables `0x1D0007EE` | Cinematic_Hidden | 7: 165 (71.75, 77.50, 200.00) -> 660 (24.28, 76.63) | - | - | 151 Cinematic_Intro; CinematicAttack_Ranged x8 (670-1020); targets `0x10000001` |
| 01Spawner | `0x2E000D03` | - |  | side 1 | _Entity_OnSetClientRelationship | 1: 0 (71.75, 77.50, 200.00) | - | - | 15 Vfx_Spawner_Tier01 |
| PowerCoreTarget | `0x2E000A3F` | `0x10000001` |  | `0x2A1` | - | 1: 0 (17.59, 77.39, 200.11) | - | - | - |
| BaseGate | `0x2E000CD7` | - |  | side 3; 0x7BD (0.90, 0.90, 0.90) | Object_Closed | 1: 0 (0.00, 68.27, 200.03) | - | - | - |

#### `0x3500002A` (Crime Alley / Tutorial 2, 52.00 s)

| Actor | World state | Var | Bind | Props | Init | Path (keys: start -> end) | Graph events (frame) | Sounds (frame: event -> bank) | Scriptlets (frame: key [-> target var]) |
|---|---|---|---|---|---|---|---|---|---|
| 01TurretFriendly | `0x2E000AA0` | - |  | side 3; `0x19B` 25; tables `0x1D0007EA` | CinematicCharacter_Hide | 1: 0 (25.54, 77.44, 200.23) | - | - | 15 CinematicCharacter_Show; 180 Vfx_Status_Turret_Hardened |
| 01TurretFriendlyHead | `0x2E000AA8` | - |  | side 3; scale 0.90; tables `0x1D0007EB` | CinematicCharacter_Hide | 1: 0 (25.12, 77.46, 200.25) | - | - | 140 CinematicCharacter_Show |
| 01TurretEnemy | `0x2E000AA0` | `0x10000019` |  | side 1; tables `0x1D0007EA` | CinematicCharacter_Hide | 1: 0 (75.00, 77.50, 199.98) | - | - | 15 CinematicCharacter_Show; Vfx_Status_Turret_Hardened x3 (180-685); CinematicCharacter_State01 x10 (350-1080); CinematicAttack_Ranged x6 (365-1040); CinematicAttack_Ranged02 x5 (395-1075); targets `0x10000002`, `0x10000015`, `0x10000016`, `0x10000017`, `0x10000018` |
| 01TurretEnemyHead | `0x2E000AA8` | - |  | side 1; scale 0.90; tables `0x1D0007EB` | CinematicCharacter_Hide | 9: 0 (75.00, 77.50, 199.98) -> 635 (75.00, 77.50) | - | - | 135 CinematicCharacter_Show |
| 01TurretEnemyPlate | `0x2E000A9F` | - |  | side 1; tables `0x1D0007EC` | CinematicCharacter_Show | 1: 0 (75.00, 77.50, 199.98) | - | - | 140 CinematicCharacter_State00 |
| 02MeleeA | `0x2E000808` | `0x10000015` |  | side 3; `0x100004EC` 1; tables `0x1D0007EE` | CinematicCharacter_Hide | 3: 0 (37.00, 77.50, 200.00) -> 410 (70.80, 77.00) | - | - | 0 CinematicCharacter_Hide (flag 1); 410 Cinematic_Hidden; 730 Cinematic_Hidden |
| 02MeleeB | `0x2E000808` | `0x10000016` |  | side 3; `0x100004EC` 1; tables `0x1D0007EE` | CinematicCharacter_Hide | 3: 0 (35.50, 78.50, 200.00) -> 460 (73.50, 77.75) | - | - | 0 CinematicCharacter_Hide (flag 1); 460 Robot_Minion_Melee_Attack; 545 Cinematic_Hidden; 730 Cinematic_Hidden |
| 02RangedA | `0x2E000840` | `0x10000017` |  | side 3; `0x100004EC` 1; tables `0x1D0007EE` | CinematicCharacter_Hide | 4: 0 (34.00, 76.50, 200.00) -> 465 (71.00, 76.50) | - | - | 0 CinematicCharacter_Hide (flag 1); 465 CinematicAttack_Ranged -> `0x10000019`; 510 CinematicAttack_Ranged -> `0x10000019`; 555 Robot_Minion_Ranged_Attack -> `0x10000019`; 635 Cinematic_Hidden; 730 Cinematic_Hidden |
| 02RangedB | `0x2E000840` | `0x10000018` |  | side 3; `0x100004EC` 1; tables `0x1D0007EE` | CinematicCharacter_Hide | 4: 0 (31.50, 78.00, 200.00) -> 475 (71.00, 78.00) | - | - | 0 CinematicCharacter_Hide (flag 1); 475 CinematicAttack_Ranged -> `0x10000019`; 520 CinematicAttack_Ranged -> `0x10000019`; 565 CinematicAttack_Ranged -> `0x10000019`; 565 Robot_Minion_Ranged_Attack; 610 CinematicAttack_Ranged -> `0x10000019`; 655 Robot_Minion_Ranged_Attack -> `0x10000019`; 730 Cinematic_Hidden |
| GreenLantern | `0x2E000156` | `0x10000002` |  | `0x974` 1; `0x975` 1; `0x973` 0xFF000000; tables `0x1D0008E9` | Cinematic_Hidden | 5: 0 (55.27, 64.42, 199.93) -> 995 (68.71, 77.38) | - | 1080: `0xF15A2153` chr_GreenLantern | 715 CinematicCharacter_State00; 1010 Combat_Basic_Attack_Right; 1015 Vfx_Glt_Basic_Right -> `0x10000019`; 1050 Combat_Basic_Attack_Right; 1055 Vfx_Glt_Basic_Right -> `0x10000019`; 1083 CinematicCharacter_Die; 1175 CinematicCharacter_State01 |

#### `0x3500002B` (Crime Alley / Tutorial 2, 38.50 s)

| Actor | World state | Var | Bind | Props | Init | Path (keys: start -> end) | Graph events (frame) | Sounds (frame: event -> bank) | Scriptlets (frame: key [-> target var]) |
|---|---|---|---|---|---|---|---|---|---|
| Turret | `0x2E000AA0` | `0x10000015` |  | side 1; scale 0.90; tables `0x1D0007E9` | Cinematic_Startup | 1: 0 (75.00, 77.50, 199.98) | - | - | 10 CinematicCharacter_State00 |
| GaslightBatman | `0x2E0001B2` | `0x10000001` | yes | `0x974` 1; `0x975` 1; `0x973` 0xFF000000 | - | 9: 0 (67.92, 77.21, 199.93) -> 955 (37.84, 76.87) | 15 Emote_Joke; 445 CommitFidget | - | - |
| Foundry | `0x2E001037` | - |  | side 3 | _Entity_OnSetClientRelationship | 1: 0 (1.26, 77.05, 201.82) | - | - | - |
| Melee01 | `0x2E001167` | - |  | side 3; tables `0x1D0007EE` | _Entity_OnSetClientRelationship | 7: 0 (46.15, 60.72, 200.18) -> 955 (51.90, 74.69) | - | - | 0 Cinematic_Hidden; 510 Cinematic_Intro; 950 CinematicCharacter_Die; 955 _Defeat_OnDead; 959 CinematicCharacter_Hide |
| Melee02 | `0x2E001167` | - |  | side 3; tables `0x1D0007EE` | _Entity_OnSetClientRelationship | 3: 0 (47.76, 64.60, 199.95) -> 805 (59.06, 78.57) | - | - | 0 Cinematic_Hidden; 510 Cinematic_Intro; 895 _Defeat_OnDead; 898 CinematicCharacter_Die; 905 CinematicCharacter_Hide |
| Ranged01 | `0x2E001168` | - |  | side 3 | _Entity_OnSetClientRelationship | 7: 0 (41.02, 60.84, 200.16) -> 995 (42.12, 73.99) | - | - | 0 Cinematic_Hidden; 510 Cinematic_Intro |
| Ranged02 | `0x2E001168` | - |  | side 3 | _Entity_OnSetClientRelationship | 11: 0 (42.76, 63.99, 200.16) -> 1015 (42.15, 81.19) | - | - | 0 Cinematic_Hidden; 510 Cinematic_Intro |
| Crater1 | `0x2E0004BE` | - |  | `0x4FD`; tables `0x1D0008CC` | - | 1: 0 (59.64, 78.57, 200.02) | - | - | 815 Object_Closed |
| Crater 2 | `0x2E0004BE` | - |  | `0x4FD`; tables `0x1D0008CC` | - | 1: 0 (52.62, 75.04, 200.05) | - | - | 870 Object_Closed |
| Crater3 | `0x2E0004BE` | - |  | `0x4FD`; tables `0x1D0008CC` | - | 1: 0 (69.81, 77.87, 200.09) | - | - | 770 Object_Closed |
| TurretBasePlate | `0x2E000A9F` | - |  | - | - | 1: 0 (75.00, 77.50, 199.99) | - | - | - |

#### `0x3500002C` (Crime Alley / Tutorial 2, 21.20 s)

| Actor | World state | Var | Bind | Props | Init | Path (keys: start -> end) | Graph events (frame) | Sounds (frame: event -> bank) | Scriptlets (frame: key [-> target var]) |
|---|---|---|---|---|---|---|---|---|---|
| 01BlueSpawner | `0x2E000D03` | - |  | side 3 | _Entity_OnSetClientRelationship | 1: 0 (21.75, 77.50, 200.12) | - | - | 30 Vfx_Spawner_Team01_Tier01 |
| 01MeleeDrone | `0x2E000808` | `0x10000001` |  | side 3; tables `0x1D0007EE` | CinematicCharacter_Hide | 5: 75 (22.31, 77.22, 200.27) -> 556 (47.57, 77.26) | - | - | 60 CinematicCharacter_Show; 200 CinematicCharacter_State02 -> `0x10000001`; 380 CinematicAttack_Melee -> `0x10000015`; 430 CinematicAttack_Melee -> `0x10000015`; 480 CinematicAttack_Melee -> `0x10000015`; 530 CinematicAttack_Melee -> `0x10000015`; 580 CinematicCharacter_Die |
| 02MeleeDrone | `0x2E000808` | `0x10000002` |  | side 3; tables `0x1D0007EE` | CinematicCharacter_Hide | 8: 105 (22.31, 77.22, 200.23) -> 665 (49.87, 78.20) | - | - | 90 CinematicCharacter_Show; 200 CinematicCharacter_State02 -> `0x10000002`; 415 CinematicAttack_Melee -> `0x10000015`; 470 CinematicAttack_Melee -> `0x10000015`; 520 CinematicAttack_Melee -> `0x10000015`; 570 CinematicAttack_Melee -> `0x10000016`; 620 CinematicAttack_Melee -> `0x10000016` |
| 01RangedDrone | `0x2E000840` | `0x10000003` |  | side 3; tables `0x1D0007EE` | CinematicCharacter_Hide | 5: 135 (22.31, 77.22, 200.30) -> 665 (46.21, 77.22) | - | - | 120 CinematicCharacter_Show; 225 CinematicCharacter_State02 -> `0x10000003`; 420 CinematicAttack_Ranged -> `0x10000015`; 470 CinematicAttack_Ranged -> `0x10000015`; 520 CinematicAttack_Ranged -> `0x10000015`; 570 CinematicAttack_Ranged -> `0x10000016`; 620 CinematicAttack_Ranged -> `0x10000016`; 670 CinematicCharacter_Die |
| 02RangedDrone | `0x2E000840` | `0x10000004` |  | side 3; tables `0x1D0007EE` | CinematicCharacter_Hide | 7: 165 (22.31, 77.22, 200.30) -> 665 (46.34, 78.14) | - | - | 150 CinematicCharacter_Show; 225 CinematicCharacter_State02 -> `0x10000004`; 435 CinematicAttack_Ranged -> `0x10000016`; 485 CinematicAttack_Ranged -> `0x10000016`; 535 CinematicAttack_Ranged -> `0x10000016`; 585 CinematicAttack_Ranged -> `0x10000016` |
| 01SiegeDrone | `0x2E000E21` | `0x10000005` |  | side 3; tables `0x1D0007EE` | CinematicCharacter_Hide | 5: 190 (21.75, 77.22, 200.18) -> 665 (44.33, 77.22) | - | - | 175 CinematicCharacter_Show; 255 CinematicCharacter_State02 -> `0x10000005`; 434 CinematicCharacter_State00 -> `0x10000015`; 495 CinematicCharacter_State00 -> `0x10000015`; 555 CinematicCharacter_State00 -> `0x10000016`; 615 CinematicCharacter_State00 -> `0x10000016` |
| 01EnemyMelee | `0x2E000808` | `0x10000015` |  | side 1; tables `0x1D0007EE` | CinematicCharacter_Hide | 3: 310 (71.49, 77.40, 200.05) -> 375 (48.57, 77.40) | - | - | 300 CinematicCharacter_Show; 384 CinematicAttack_Melee -> `0x10000001`; 434 CinematicAttack_Melee -> `0x10000001`; 484 CinematicAttack_Melee -> `0x10000001`; 534 CinematicAttack_Melee -> `0x10000001`; 545 CinematicCharacter_Die |
| 02EnemyMelee | `0x2E000808` | `0x10000016` |  | side 1; tables `0x1D0007EE` | CinematicCharacter_Hide | 4: 335 (53.15, 77.54, 199.94) -> 405 (48.56, 78.57) | - | - | 300 CinematicCharacter_Show; 420 CinematicAttack_Melee -> `0x10000002`; 470 CinematicAttack_Melee -> `0x10000002`; 520 CinematicAttack_Melee -> `0x10000002`; 570 CinematicAttack_Melee -> `0x10000002`; 620 CinematicAttack_Melee -> `0x10000002`; 625 CinematicCharacter_Die |
| 01EnemyRanged | `0x2E000840` | `0x10000017` |  | side 1; tables `0x1D0007EE` | CinematicCharacter_Hide | 2: 335 (55.06, 77.22, 200.05) -> 405 (51.36, 77.22) | - | - | 300 CinematicCharacter_Show; 425 CinematicAttack_Ranged -> `0x10000001`; 475 CinematicAttack_Ranged -> `0x10000001`; 525 Robot_Minion_Ranged_Attack -> `0x10000001`; 575 Robot_Minion_Ranged_Attack -> `0x10000001`; 625 CinematicAttack_Ranged -> `0x10000002`; 675 CinematicCharacter_Die |
| 02EnemyRanged | `0x2E000840` | `0x10000018` |  | side 1; tables `0x1D0007EE` | CinematicCharacter_Hide | 5: 335 (57.13, 77.29, 199.99) -> 425 (51.37, 78.11) | - | - | 300 CinematicCharacter_Show; 440 CinematicAttack_Ranged -> `0x10000002`; 490 CinematicAttack_Ranged -> `0x10000002`; 540 CinematicAttack_Ranged -> `0x10000002`; 590 CinematicAttack_Ranged -> `0x10000002`; 640 CinematicAttack_Ranged -> `0x10000002` |
| 01EnemySiege | `0x2E000E21` | `0x10000019` |  | side 1; tables `0x1D0007EE` | CinematicCharacter_Hide | 5: 300 (71.89, 77.33, 200.05) -> 420 (53.88, 77.33) | - | - | 300 CinematicCharacter_Show; 445 CinematicCharacter_State00 -> `0x10000001`; 505 CinematicCharacter_State00 -> `0x10000001`; 565 CinematicCharacter_State00 -> `0x10000001`; 620 CinematicCharacter_State00 -> `0x10000002` |
| GaslightBatman | `0x2E0001B2` | player | yes | `0x974` 1; `0x975` 1; `0x973` 0xFF000000 | - | 2: 0 (25.32, 75.39, 200.23) -> 30 (28.34, 75.48) | 260 CommitFidget | - | - |

#### `0x3500002F` (Crime Alley / Tutorial 2, 17.00 s)

| Actor | World state | Var | Bind | Props | Init | Path (keys: start -> end) | Graph events (frame) | Sounds (frame: event -> bank) | Scriptlets (frame: key [-> target var]) |
|---|---|---|---|---|---|---|---|---|---|
| Corrupted_Gasbat | `0x2E0011C1` | - |  | - | - | 7: 0 (98.45, 77.17, 199.98) -> 485 (107.02, 77.17) | 170 Batman_Gaslight_Batflight; 215 Emote_Taunt | 0: `0xB0FED627` chr_Batman_Gas; 170: `0x7D594DFF` chr_Batman_Gas | 170 Vfx_Bmg_Spawn |
| Player_Gasbat | `0x2E0001B2` | player | yes | - | - | 2: 0 (72.65, 77.39, 200.05) -> 20 (75.52, 77.39) | 26 CbtState_Death_Induce; 475 CbtState_GetUp | 24: `0xC69F4023` chr_Batman_Gas | - |
| Bat_Scream_Bat | `0x2E0002B0` | - |  | - | - | 2: 0 (99.26, 77.35, 201.84) -> 40 (63.29, 77.35) | - | 0: `0xEF1B46D3` chr_Batman_Gas | - |

#### `0x35000030` (Crime Alley / Tutorial 2, 14.00 s)

| Actor | World state | Var | Bind | Props | Init | Path (keys: start -> end) | Graph events (frame) | Sounds (frame: event -> bank) | Scriptlets (frame: key [-> target var]) |
|---|---|---|---|---|---|---|---|---|---|
| ImpactPoint | `0x2E001253` | - |  | - | Cinematic_Startup | 1: 0 (82.12, 77.34, 199.90) | - | - | 30 Cinematic_Intro |
| Wall | `0x2E001254` | - |  | - | Cinematic_Startup | 1: 0 (82.12, 77.34, 199.90) | - | - | 103 CinematicCharacter_State00 |

#### `0x35000038` (Crime Alley / Tutorial 2, 72.00 s)

| Actor | World state | Var | Bind | Props | Init | Path (keys: start -> end) | Graph events (frame) | Sounds (frame: event -> bank) | Scriptlets (frame: key [-> target var]) |
|---|---|---|---|---|---|---|---|---|---|
| PowerCore | `0x2E000AC5` | - |  | `0x10000CF0` 1; team 2 | - | 2: 0 (142.50, 77.75, 200.10) -> 365 (142.50, 77.75) | - | - | 10 Vfx_Destruct_State0 |
| GasBat | `0x2E0001B2` | `0x10000001` |  | `0x974` 1; `0x975` 1; `0x973` 0xFF000000 | Cinematic_Victory | 16: 0 (137.68, 77.47, 200.31) -> 1865 (17.18, 86.76) | 655 Batman_Gaslight_Batflight | 655: `0x7D594DFF` chr_Batman_Gas; 660: `0x02186CB9` chr_Batman_Gas | - |
| WonderWoman | `0x2E000652` | - |  | `0x974` 1; tables `0x1D0008FF`; `0x975` 1; 0x6B3 1.05; `0x973` 0xFF000000 | Cinematic_Hidden | 2: 0 (14.47, 88.83, 199.99) -> 1865 (13.21, 86.19) | - | - | 460 Cinematic_Startup |
| Superman | `0x2E0000DD` | - |  | `0x974` 1; `0x975` 1; `0x973` 0xFF000000; tables `0x1D000900` | Cinematic_Hidden | 2: 0 (12.71, 85.68, 200.22) -> 1865 (14.77, 86.96) | - | - | 555 Cinematic_Startup |
| GreenLantern | `0x2E000156` | - |  | `0x974` 1; `0x975` 1; `0x973` 0xFF000000; tables `0x1D0008E9` | Vfx_Active | 9: 2 (12.87, 89.52, 207.41) -> 1865 (11.17, 86.11) | - | - | 0 Fidgets_Disable |
| BlueTurretBody | `0x2E000AA0` | - |  | side 3; tables `0x1D0007EA` | CinematicCharacter_Show | 1: 0 (65.00, 77.50, 199.98) | - | - | 1 _Entity_OnSetClientRelationship |
| BlueTurretHead | `0x2E000AA8` | - |  | `0x974` 1; tables `0x1D0007EB`; `0x975` 1; side 3; `0x973` 0xFF000000 | CinematicCharacter_Show | 1: 0 (64.80, 77.54, 199.49) | - | - | - |
| RedTurretBody | `0x2E000AA0` | - |  | side 1; tables `0x1D0007EA` | CinematicCharacter_Show | 1: 0 (95.00, 77.50, 199.98) | - | - | - |
| RedTurretHead | `0x2E000AA8` | - |  | `0x974` 1; tables `0x1D0007EB`; `0x975` 1; side 1; `0x973` 0xFF000000 | CinematicCharacter_Show | 1: 0 (95.00, 77.50, 199.71) | - | - | - |
| CorruptedGasBot | `0x2E0011C1` | `0x10000015` |  | `0x974` 1; `0x975` 1; `0x973` 0xFF000000; tables `0x1D000771` | - | 8: 0 (77.54, 64.78, 200.14) -> 1630 (83.12, 77.51) | 1817 CbtState_KnockUp | - | Combat_Basic_Attack_Right x4 (1429-1760); Combat_Basic_Attack_Left x5 (1465-1795); targets `0x10000002`, `0x10000003` |
| HarleyQuinn | `0x2E000BE5` | `0x10000003` |  | `0x974` 1; `0x975` 1; `0x973` 0xFF000000; tables `0x1D0008FE` | - | 4: 0 (76.41, 65.79, 199.93) -> 1900 (9.45, 85.50) | 1590 Combat_Locomotion; 1800 HarleyQuinn_PuddinTime; 1830 Emote_Laugh; 2015 CbtState_Laugh | - | 1640 Combat_Basic_Attack -> `0x10000015`; 1680 Combat_Basic_Attack -> `0x10000015`; 1720 Combat_Basic_Attack -> `0x10000015`; 1760 Combat_Basic_Attack -> `0x10000015`; 1800 Vfx_Har_PuddinTime_Start -> `0x10000015`; 1806 Vfx_Har_PuddinTime_Active -> `0x10000015`; 1812 Vfx_Har_PuddinTime_Stop -> `0x10000015` |
| Doomsday | `0x2E000157` | `0x10000002` |  | `0x974` 1; `0x975` 1; `0x973` 0xFF000000; tables `0x1D0008FD` | - | 9: 0 (75.82, 65.00, 200.02) -> 1900 (20.04, 87.05) | 1385 Combat_Locomotion | - | 1420 Doomsday_Berserk; 1455 Combat_Basic_Attack_Left -> `0x10000015`; 1490 Combat_Basic_Attack_Left -> `0x10000015`; 1525 Combat_Basic_Attack_Left -> `0x10000015` |

#### `0x35000039` (Crime Alley / Tutorial 2, 49.50 s)

| Actor | World state | Var | Bind | Props | Init | Path (keys: start -> end) | Graph events (frame) | Sounds (frame: event -> bank) | Scriptlets (frame: key [-> target var]) |
|---|---|---|---|---|---|---|---|---|---|
| GasBot | `0x2E0011C1` | - |  | `0x974` 1; `0x975` 1; `0x973` 0xFF000000; tables `0x1D000771`, `0x1D0007E4` | Cinematic_Hidden | 1: 0 (148.34, 77.17, 200.37) | - | - | 1300 _Entity_OnSetClientRelationship; 1304 Cinematic_Hidden (flag 1); 1305 CinematicCharacter_State00; 1400 CinematicCharacter_State02 |

#### `0x3500003A` (Crime Alley / Tutorial 2, 11.50 s)

| Actor | World state | Var | Bind | Props | Init | Path (keys: start -> end) | Graph events (frame) | Sounds (frame: event -> bank) | Scriptlets (frame: key [-> target var]) |
|---|---|---|---|---|---|---|---|---|---|
| PowerCore | `0x2E000AC5` | - |  | side 5; team 2 | - | 1: 0 (142.50, 77.75, 200.10) | - | - | 0 Vfx_Destruct_State0; 225 Cinematic_Announcement {0x100008F6=0x2, 0x100008F7=0x1} |
| Player01 | `0x2E00028B` | `0x10000001` | yes | `0x974` 1; `0x975` 1; `0x973` 0xFF000000 | Cinematic_Startup | 1: 0 (137.68, 77.47, 200.31) | - | - | 0 Cinematic_Victory |
| Player02 | `0x2E000E54` | `0x10000002` | yes | `0x974` 1; `0x975` 1; `0x973` 0xFF000000 | Cinematic_Startup | 1: 0 (140.50, 83.50, 200.15) | - | - | 0 Cinematic_Victory |

#### `0x3500003B` (Crime Alley / Tutorial 2, 11.50 s)

| Actor | World state | Var | Bind | Props | Init | Path (keys: start -> end) | Graph events (frame) | Sounds (frame: event -> bank) | Scriptlets (frame: key [-> target var]) |
|---|---|---|---|---|---|---|---|---|---|
| PowerCore | `0x2E000AC5` | - |  | side 3; team 1 | - | 1: 0 (17.50, 77.15, 200.10) | - | - | 0 Vfx_Destruct_State0; 225 Cinematic_Announcement {0x100008F6=0x1, 0x100008F7=0x2} |
| Player01 | `0x2E00028B` | `0x10000001` | yes | `0x974` 1; `0x975` 1; `0x973` 0xFF000000 | Cinematic_Startup | 1: 0 (22.55, 77.48, 200.23) | - | - | 0 Cinematic_Victory |
| Player02 | `0x2E000E54` | `0x10000002` | yes | `0x974` 1; `0x975` 1; `0x973` 0xFF000000 | Cinematic_Startup | 1: 0 (15.50, 83.50, 200.15) | - | - | 0 Cinematic_Victory |

#### `0x3500003C` (Crime Alley / Tutorial 2, 13.00 s)

| Actor | World state | Var | Bind | Props | Init | Path (keys: start -> end) | Graph events (frame) | Sounds (frame: event -> bank) | Scriptlets (frame: key [-> target var]) |
|---|---|---|---|---|---|---|---|---|---|
| Chr_Center - ThePlayer | `0x2E00028B` | player | yes | `0x974` 1; `0x5F9` 1; `0x975` 1; hidden 1; `0x973` 0xFF000000 | Cinematic_Hidden | 1: 0 (52.39, 77.81, 200.04) | - | - | 243 Cinematic_Intro |

### 1.4 The cinematics' server scripts (C: decoded with the client's own Unpack; P: node meanings)

`tools/script_decoder.py records()` only accepts headers `did | n | 1 | 0 | 0 | 0`; the 15 map-pack scripts of the
cinematics start `did | 1 | 1 | <first node>` and are skipped by `python tools\script_decoder.py all` (they are not
in `data/script_trees/`). Decoding them at the DID with the same `Decoder` gives status ok for all 15.

| Script | Used by | Shape |
|---|---|---|
| `0x340006F2` | the four match intros | `S0 -> S1` on `0x10000060`; node `0x1000019D` with values 1 (enter S1), 3 and 2 (exit). `0x1000019D` appears in no other script (P: HUD / camera mode for the intro). |
| `0x3400076B` / `0x3400076C` | GD / CC victories | enter: `0x1000009C [1, 0x1000001B]` (lighting); `S0 -> S1/S2/S3` on `0x100000F2` / `0x100000F3` / `0x100000F1`: `0x10000121` objective text 29 (args team 1 / 2) or 395. |
| `0x3400058A`, `0x34000591`, `0x34000595`, `0x34000700` | Tutorial 1 | `tutorial-data-inventory.md` 4. |
| `0x340005DF`, `0x340005F4`, `0x340005E5`, `0x34000605` | Tutorial 2 | `0x1000009C [1, 0x10000016]` on enter, `[1, 0]` on exit; `0x1000017B [0,1,1,0]`; a chain of `StartConversation` (`0x100000D1`) states advanced by `0x10000060`; `0x340005DF` and `0x34000732` also `PlaySound(-1, 0x3EB822F0)` (`AMB_Tutorial`), `0x340005DF` also `0x10000012(agent)[0x10000210]`; `0x340005E5` `RunScriptlet(agent, Cinematic_FadeToBlack 0x10000E59)`, `0x10000167 [36 1 0 0 0]` (HUD notice), objective text 393. |
| `0x340006A2..A5`, `0x340006A8`, `0x340006A9`, `0x34000733`, `0x34000732` | Crime Alley 1vAI beats | Same pattern; `0x340006A8/A9` advance on `0x1000017C` (conversation finished, P) after the first `0x10000060`. |

Every cinematic script brackets its run with `0x1000009C [1, 0x10000016]` / `[1, 0]` (16 + 12 uses of the 31 in
all scripts), i.e. the cinematic lighting environment (section 5.1).

---------------------------------------------------------------------------------------------------------------------

## 2. Scriptlet tables (`0x1D`) of all packs

### 2.1 Method and coverage

`ics.rp.script_tables(pack)` on all 616 packs (224 list `0x1D` records). Format and finder as in `ics/rp.py`. The
finder anchors on table bodies between DID-anchored records, so a table whose body it cannot recognise is dropped
(297 of 2 083 listed slots, mostly in champion packs with large unanchored runs, e.g. `0xA0000332` 3 of 18,
`0xA0000303` 6 of 16, `0xA000011F` 2 of 10, `0xA000039F` 3 of 10). The counts below are of what it parses.

Per pack: `pack listed / parsed / key slots` (key slots include the same table in several packs):

```
0xA0000037   5/  4/  10   0xA000006F  11/ 11/  63   0xA0000075   2/  0/   0   0xA0000076   2/  2/   9   0xA000009A 170/165/ 566
0xA000009B   1/  0/   0   0xA00000A2   2/  1/   1   0xA00000A3   3/  3/   6   0xA00000B3  35/ 33/ 152   0xA00000B4   2/  2/  15
0xA00000C9   1/  1/   5   0xA00000CC   1/  1/   1   0xA00000D2 130/130/ 577   0xA00000D7   3/  1/   3   0xA00000D9   1/  1/   2
0xA00000DD   2/  2/  12   0xA00000DF  11/ 10/ 138   0xA00000E0   1/  1/   1   0xA00000E5   2/  2/  13   0xA00000EB   1/  1/   1
0xA00000F3   2/  1/   1   0xA00000F7   6/  5/  23   0xA00000FA   1/  1/   1   0xA00000FC  71/ 71/ 366   0xA0000100   2/  2/  16
0xA000010A   3/  3/   7   0xA000010B  11/  9/  47   0xA000010C   2/  2/   9   0xA0000111  17/ 10/  25   0xA0000112  18/ 17/  70
0xA0000113  17/ 16/  61   0xA0000114  10/  8/  31   0xA0000115  22/ 18/  66   0xA0000116  11/  9/  38   0xA000011B  20/ 19/  63
0xA000011C   8/  5/  13   0xA000011D  10/  7/  31   0xA000011E  11/ 10/  52   0xA000011F  10/  2/  16   0xA0000120  16/ 11/  44
0xA0000121  10/  9/  55   0xA0000122  12/ 11/  40   0xA0000123   1/  0/   0   0xA0000124   9/  6/  24   0xA000012C  12/  9/  46
0xA000012D   1/  1/   4   0xA0000144   2/  2/  10   0xA0000145  14/ 10/  65   0xA0000150  17/ 12/  37   0xA0000151   1/  0/   0
0xA0000154   1/  1/   5   0xA0000156   1/  1/   2   0xA0000157  14/ 10/  30   0xA0000161  48/ 36/ 208   0xA0000162  45/ 41/ 247
0xA0000164   1/  1/   9   0xA0000168  52/ 46/ 285   0xA000016B  30/ 24/ 116   0xA000016E  50/ 44/ 275   0xA0000175   1/  1/   4
0xA0000176  10/  8/  41   0xA0000179  15/ 13/  80   0xA0000180   2/  2/  12   0xA0000183   2/  2/   9   0xA0000186  12/  9/  27
0xA0000187   1/  1/  23   0xA000018D  14/ 13/  51   0xA000018E   1/  1/   3   0xA0000191  13/ 12/  46   0xA0000192   2/  2/  16
0xA00001D1   1/  0/   0   0xA00001D2  29/ 27/ 110   0xA00001D8   2/  2/  13   0xA00001DC   1/  1/   1   0xA00001DF   1/  1/  16
0xA00001E5   2/  1/  11   0xA00001E8  13/ 12/  70   0xA00001E9   3/  2/  12   0xA00001EC   6/  6/  32   0xA00001EF   1/  1/   1
0xA00001F2   1/  0/   0   0xA00001F3  28/ 22/  91   0xA00001F6   2/  2/  15   0xA00001F9   1/  1/  14   0xA00001FA  22/ 18/  57
0xA00001FE   1/  1/   1   0xA0000201   2/  2/  38   0xA0000202  20/ 18/  65   0xA0000205   3/  3/  12   0xA0000208   1/  1/   9
0xA000020E  15/  7/  27   0xA000020F   4/  2/   8   0xA0000212   2/  1/   7   0xA0000215   1/  1/  23   0xA0000218   1/  1/   4
0xA000021B   1/  0/   0   0xA000021E   1/  1/  23   0xA0000221   9/  3/  12   0xA0000222   2/  2/  21   0xA0000225   1/  1/   2
0xA000022B   3/  3/   7   0xA000022E  11/  9/  43   0xA000022F   1/  1/   4   0xA0000232   2/  2/  21   0xA0000235   1/  1/   3
0xA0000238   2/  2/  10   0xA000023B   1/  0/   0   0xA000023E  10/  8/  51   0xA000023F   1/  1/   1   0xA0000244   1/  1/   4
0xA0000247   1/  0/   0   0xA000024A  23/ 22/  89   0xA000024B   1/  1/   3   0xA000024C  73/ 71/ 228   0xA0000251   2/  2/  15
0xA0000254   2/  2/  20   0xA0000256  50/ 49/ 214   0xA0000257  24/ 20/ 123   0xA000025C   3/  3/  16   0xA000025F   2/  2/  15
0xA0000262   1/  1/   4   0xA000026A   1/  1/   1   0xA000026D   2/  2/   9   0xA000026E  15/ 10/  46   0xA0000272   2/  1/   2
0xA0000275   1/  0/   0   0xA0000278   2/  1/   2   0xA000027B   2/  0/   0   0xA000027C   3/  3/  18   0xA0000281  17/ 16/  82
0xA0000282   2/  2/  13   0xA00002AA   3/  2/   3   0xA00002AD   1/  0/   0   0xA00002B1  16/ 15/  85   0xA00002B2   3/  2/  17
0xA00002B4  11/  5/  11   0xA00002B5   2/  2/  21   0xA00002BB   2/  1/   5   0xA00002BE   3/  3/  25   0xA00002C1   3/  1/  13
0xA00002C4   1/  0/   0   0xA00002C7   3/  2/  12   0xA00002CA   1/  1/   4   0xA00002CE   2/  2/   9   0xA00002CF  16/ 15/  73
0xA00002D2   1/  1/   8   0xA00002D5   2/  2/  21   0xA00002DA   2/  2/  21   0xA00002DE  20/ 18/  85   0xA00002E3  20/ 19/  87
0xA00002E4   2/  2/  16   0xA00002E5 109/104/ 304   0xA00002E6  72/ 67/ 397   0xA00002E7  45/ 34/ 177   0xA00002EA   2/  2/  16
0xA00002ED   2/  2/  13   0xA00002F0   2/  1/   8   0xA00002F3   2/  2/   9   0xA00002F7  13/ 12/  51   0xA00002F8   1/  1/   4
0xA00002F9   1/  1/   9   0xA00002FE   4/  4/  29   0xA0000303  16/  6/  51   0xA0000304   1/  1/   3   0xA0000307   1/  0/   0
0xA000030A   2/  1/   8   0xA000030E  11/ 10/  45   0xA000030F   1/  1/   6   0xA0000312   1/  1/   2   0xA0000313   1/  1/   1
0xA000031F   2/  2/  15   0xA0000322   2/  2/  13   0xA0000327   1/  1/   6   0xA0000328  10/  9/  48   0xA000032B   1/  0/   0
0xA000032E   1/  1/   5   0xA0000332  18/  3/  28   0xA0000333   1/  0/   0   0xA0000337  15/ 13/  57   0xA0000338   1/  1/   3
0xA000033B   2/  1/   1   0xA000033F  12/  9/  59   0xA0000340   1/  0/   0   0xA0000343   1/  1/   4   0xA0000344   1/  1/   3
0xA0000349   1/  1/   3   0xA000034C   2/  2/  38   0xA000034F   6/  3/   7   0xA0000354   1/  0/   0   0xA0000357   2/  2/  19
0xA000035A   1/  1/   4   0xA000035D   3/  3/  18   0xA0000361  14/ 13/  62   0xA0000362   1/  0/   0   0xA0000365   1/  1/   3
0xA0000368   1/  1/   2   0xA000036C   1/  0/   0   0xA000036D  12/ 11/  47   0xA0000371   3/  3/  25   0xA0000378  10/  8/  61
0xA0000379   1/  0/   0   0xA000037C   3/  3/  19   0xA000037F   2/  1/  23   0xA0000384  10/  8/  53   0xA0000387   1/  1/   7
0xA000038A   1/  1/  10   0xA000038D   2/  1/   3   0xA0000399   1/  0/   0   0xA000039A  10/  9/  36   0xA000039E   1/  0/   0
0xA000039F  10/  3/  19   0xA00003A6   1/  1/   3   0xA00003A9   1/  0/   0   0xA00003AC   3/  2/   6   0xA00003B0   4/  3/  26
0xA00003B3   1/  1/   1   0xA00003B6   1/  1/   4   0xA00003BA   3/  2/  17   0xA00003BD   2/  2/  21   0xA00003C0   2/  1/  15
0xA00003C3   1/  1/   7   0xA00003C6   1/  1/   3   0xA00003D0   1/  0/   0   0xA00003D3   4/  3/  26
```

Totals: 2 083 listed, 1 786 parsed, **1 323 distinct tables** (463 parsed copies are the same table in another
pack), **1 580 distinct keys**, 6 127 key slots over the distinct tables, no empty table.

### 2.2 The key-name table (enum `0x30000013`, the project's "`0x33000000`")

* 3 710 names. Used as table keys: 1 576 (+ 4 unnamed small keys). Used by `RunScriptlet` in the ~870 decoded
  scripts: 678 keys (1 351 uses; 128 of them in no parsed table). Used by cinematics: 50 keys (2 not in a parsed
  table: `Vfx_Destruct_State3`, `Vfx_Spawner_Team01_Tier01`). Union of all uses: 1 710 keys (1 706 named).
* Names never used as a table key: 2 134 (2 004 used nowhere: no table, script or cinematic), 712 of them
  `Vfx_Test_*`; families with the lowest use (used / named): `Vfx_Test` 7 / 712, `Dest*` 17 /
  124, `Vfx_Status` 16 / 108, `Vfx_Det` 9 / 81, `Vfx_Cbt` 6 / 29, `Vfx_Jst` 4 / 33.
* Champion families (3-letter codes after `Vfx_`): `Arc` 72 / 101 used, `Kta` 53 / 58, `Nit` 48 / 61, `Gar` 45 /
  51, `Ssr` 36 / 37, `Atm` 33 / 65, `Aqm` 30 / 32, `Stg` 29 / 32, `WW` 26 / 40, `Fla` 27 / 39, `Bmg` 15 / 27 ...
* The 4 unnamed keys (`0x5` x157 tables, `0x16` x33, `0x1`, `0x14`) are small "slot" keys (wagons: `0x5` = idle
  particle; meteor fragments `0x1D000916-918` = key `0x5` only). P.

Most used keys (number of distinct tables):

| Tables | Key | Name | | Tables | Key | Name |
|---|---|---|---|---|---|---|
| 308 | `0x100000EB` | Vfx_Active | | 47 | `0x1000061C` / `0x1000061E` | Vfx_Status_Bleed_Stop / _Active |
| 157 | `0x5` | (unnamed) | | 47 | `0x1000048C` | Destructible_OnCollision_Metal |
| 112 | `0x100002F5` | _Entity_OnEnterWorld_Default | | 46 | `0x1000064C` | _Missile_OnExpired |
| 98 | `0x10000209` | _HFSM_TargetHitAction_PhysicalReaction | | 44 | `0x10000016` | Vfx_OnCollision |
| 96 | `0x100003A9` | Destructible_OnBreak | | 43 | `0x10000644` | Vfx_Chr_Emote_Laugh |
| 91 | `0x10000079` | Vfx_OnExplode | | 39 | `0x100003A6` | _Entity_OnSetClientRelationship |
| 89 | `0x100009EC` | Cinematic_Intro | | 37 | `0x100001FA` | _Defeat_OnDead |
| 88 | `0x10000078` | Vfx_OnInit | | 37 | `0x1000087C` | Vfx_Spawn_Event01 |
| 82 | `0x100003A8` | Destructible_OnCollision | | 35 | `0x100005CB` / `CC` | Vfx_Death_A / _B |
| 76 / 71 / 37 / 27 | `0x1000005D` / `6B` / `77` / `85` | Vfx_Active_State0..3 | | 34 | `0x1000087B` | Vfx_Spawn_Event02 |
| 73 | `0x10000130` | Vfx_Stop | | 31 | `0x10000063` | Destructible_AdvanceState |
| 65 / 63 / 51 | `0x10000643` / `41` / `42` | Vfx_Chr_Emote_Joke / Dance / Taunt | | 30 | `0x1000018E` | Vfx_Startup |
| 60 | `0x100009EB` | Cinematic_Hidden | | 25 | `0x10000413` | _CEntitySystem_EnvironmentStateChange |
| 55 / 54 / 52 / 50 | `0x100005C4..C7` | Vfx_Fidget_A..D | | 23 | `0x100003AF` / `B0` | Footstep_Right / Left |
| 54 | `0x10000032` | Vfx_Spawn | | 23 | `0x1000006A` | Vfx_Fade_Out |
| 54 | `0x10000290` | Destructible_OnCompletelyDestroyed | | 19 | `0x100001FE` | _Defeat_OnFade |
| 52 | `0x100001E0` | _HFSM_DestroyEntityAction | | 16 | `0x10000809` | _Entity_OnSwap |
| 47 | `0x10000622` / `23` | Vfx_Cbt_Hit_Blood_Crit / _Blood | | 15 | `0x1000040D` | Vfx_Death |

### 2.3 Scriptlets per gameplay state: who triggers them

"Client hook" = the key is an immediate in the client code at the listed address (the client runs it itself on a
state change; C that the constant is there, P that the site is the trigger). "Server" = nothing in the client runs
it: the original server sent it (`0x8D`, or `0x2050` / `0x2056`), or a server script's `RunScriptlet` did.

| State | Keys (tables using it) | Trigger |
|---|---|---|
| Spawn / enter world | `_Entity_OnEnterWorld_Default 0x100002F5` (112; minions: -> `Vfx_Spawn`), `Vfx_Spawn 0x10000032` (54), `Vfx_Startup 0x1000018E` (30), `Vfx_Spawn_Event01..05` (37/34/26/5/4), `Vfx_SpawnIdle 0x1000087D`, `Vfx_Spawn_Streak 0x100005B8` (23) | `_Entity_OnEnterWorld_Default`: not in the code (server, or run from the entity's creation data, ?). `Vfx_Spawn`: constant at `0x85AB01`, `0x975DF8` (P client). |
| Respawn | `_Defeat_OnRespawn 0x100001FC` (6) | client hook `0x9CE559`, `0x9CE6DD`, `0xA4A1B2`, `0xA5D4C4`, `0xAB3080`, `0xAB33C6` |
| Death | `_Defeat_OnDead 0x100001FA` (37; minions -> `Vfx_OnExplode`), `_Defeat_OnFade 0x100001FE` (19), `_Defeat_OnIncapacitated 0x100001FB`, `_Defeat_StartupIncapacitated 0x100001F9`, `_Defeat_OnRevive 0x100001FD`, `Vfx_Death(_A/_B/_C)`, `_HFSM_DestroyEntityAction 0x100001E0` (52) | `_Defeat_*`: **not in the code -> server** (the tutorial already sends `0x100001FA` on drone deaths). `_HFSM_DestroyEntityAction`: client `0x9B575F` (HFSM). `Vfx_Death 0x1000040D`: client `0x876EF1`, `0xAB78DC`; also 5 scripts. `_CDefeatSystem_DeathOverlay 0x10000843`: client `0x41B2E8`, `0xA8EEBB`. |
| Hit | `_HFSM_TargetHitAction_PhysicalReaction 0x10000209` (98), `VFX_CBT_Hit_Shared 0x10000223` and `_ClientOnly 0x100002A4` / `_GameReplicate 0x1000042F` / `_ReplicateOnly 0x1000032E`, `Vfx_Cbt_Hit_Blood(_Crit)` (47) | `0x10000209`: client `0x96BD0F`, `0xAB7963` + 5 scripts; `0x10000223`: server scripts (`HitEffect` node `0x1000007A`). Blood: from the hit effect templates (P). |
| Low health | `_gmCVitalComponent_LowHealthNotice 0x1000040A` (table `0x1D000166`, pack `0xA0000037`) | client `0xAB107F` (vitals) |
| Level up / ultimate | `_Advancement_LevelUp 0x10000201` (`0x1D0000EF`, `0x1D0001F6`) | not in the code -> server. (`0x1000065D` `_Advancement_UltimateUnlocked` shares its number with property `0x1000065D`: the code hits are the property.) |
| Team colour / relation | `_Entity_OnSetClientRelationship 0x100003A6` (39), `Vfx_TeamColor_SetNull 0x10000B0D`, `_SetContention 0x100008C4`, `_SetParentColor 0x100008C5` (base `0x1D000385`), `_Team_SetTeamIndicator 0x100001FF` (`0x1D0000EF`, `0x1D00065A`) | `0x100003A6`: client `0xA7B0E5`, `0xA7B201` on every PVP team change (C, targeting notes). `0x100001FF`: client `0xA807FB`, `0xA80950`, `0xA8113F`, `0xA81399`. SetContention / SetNull: not in the code (server or the capture point's own logic). |
| Capture point | `_CapturePoint_OnTeamBiasChanged 0x100003A7` (`0x1D000385`), `Vfx_CapturePoint_BeingCaptured 0x1000032F`, `_Captured 0x100002A9`, `_Lost 0x100002A8` (`0x1D0002FE` CC, `0x1D0004A1` GH), `Robot_Minion_Capture_Attack 0x10000835`, `Vfx_Min_Capture 0x10000837` | `0x100003A7`: client `0x9677A3..0x968E8F`, `0xA79441`, `0xA7952E`; `_Captured` / `_Lost`: client `0xA28ED0` / `0xA28F28`; `_BeingCaptured`: not in the code (server, P). |
| Destruction phases | Turrets / cores: `Vfx_Destruct_State0..3 0x100000EA / F5 / 101 / 10E` (`0x1D00035D/35F/360/49E/98A`), template damage states `0x1000022F` -> `Object_Phase1..4 0x100002C3..C6`, `Vfx_OnExplode 0x10000079` (91); props: `Destructible_AdvanceState 0x10000063` (31), `Destructible_OnBreak*` (96 + per-part `_T0/_T1`), `Destructible_OnCollision_<material>`, `Destructible_OnCompletelyDestroyed 0x10000290` (54) | `Vfx_Destruct_State0/1/2`, `Destructible_AdvanceState`, `Target_Acquired/Lost`, `Vfx_Targeting`: one client site each in the `0x97Cxxx` block + a table at `0x13C4xxx` (P: the client maps damage states to keys itself). `Vfx_OnExplode`: client `0xAD832C` + 42 script uses. `Destructible_OnBreak*`: not in the code (P: the destruction component calls them by the per-part names in data). |
| Doors / gates | `Object_Closed 0x1000034F` (7), `Object_Open 0x10000353` (6), `Object_Melee_Attack`, `Object_Ranged_Attack 0x100002E0` | server (no code site) |
| Guide arrows / pings | `Vfx_GuideArrow 0x10000F80` (`0x1D00034B`, `0x1D0006E2`), `Vfx_GuideArrow_Ping 0x10000F86` (`0x1D00034B`), `Vfx_Cbt_Tgt_Mark_Player_Alert/Retreat_*` (`0x1D0000D0`), `_Ping_Alert(_Friendly/_Enemy) 0x100004C6/CA/C7`, `_Ping_Retreat(...) 0x100004C9/C8/CB` | Guide arrows: server script `0x34000600` (`RunScriptlet`). Pings: not in the code (server; P: relayed player pings). |
| Selection | `_Selection_SoftSelection_Valid 0x100001E4`, `_Invalid 0x100001E6`, `_UsableTarget 0x100001E5`, `_Usage_Locked 0x10000653` | client (`0xA1CDBA`, `0xA9E4A2`, `0xAA012A`, `0xAA24C3`) |
| Announcements | `Cinematic_Announcement 0x10000A50` (`0x1D000360`, `0x1D0004C7`, `0x1D00098A`: cores; variables `0x100008F6` / `0x100008F7` = teams) | cinematics only (`0x3500000D/E/F`, `0x3500003A/B`) |
| Cinematic states | `Cinematic_Hidden 0x100009EB` (60), `Cinematic_Intro 0x100009EC` (89), `Cinematic_Startup 0x100007EB` (11), `Cinematic_Victory 0x10000A9E` (5), `CinematicCharacter_Show/Hide 0x100001BD/BE`, `CinematicCharacter_State00..04 0x10000E5B..5F`, `CinematicCharacter_Die 0x10000ECE`, `CinematicAttack_* 0x10000E28..E2F, 0x10000ECD`, `Cinematic_FadeToBlack(_Stop) 0x10000E59/58` | cinematic data (no code site; `CinematicCharacter_Hide` `0x9CEA1F` is likely a coincidence). `Cinematic_FadeToBlack`: also script `0x340005E5`. |
| Environment | `_CEntitySystem_EnvironmentStateChange 0x10000413` (25 tables: `0x1D00008E/8F/92/A4/A5/AC/B6/C7-CB/162` ... in zone packs `0xA000009A`, `0xA000024C`, `0xA00000FC`, `0xA00000D2`, `0xA00002E5`) | client (section 5.2) |
| Visual progression / upgrades | `_VisualProgression_Start/Active/Interrupt/Stop 0x10000AD3/AD5/AD4/AD2` (`0x1D00046A`), `_SUpgradeSystem_OnCurrencyGained 0x10000805`, `_Upgrade_Loot 0x10000962`, `_TurretWarning_WarningState 0x1000103D` (`0x1D000923`) | client (`0xA8C744`, `0xA163D7`, `0xA163F8`, `0x857EE9`, `0xA0C9A8`, `0xA85363`) |
| Locomotion / scripts | `_Combat_GoToLocomotion 0x100002FD` (169 script uses), `_Missile_OnExpired 0x1000064C` (36), `_Hotspot_Fizzle 0x100002F4`, `_ExecuteScriptlet 0x100003EA` / `_StopScriptlet 0x100003EB` (vehicle `0x1D000199`) | scripts; `_ExecuteScriptlet` client `0x876D85`, `0x9CA9B0`, `0x9CAA30`, `0xA8559E` |

**Minimum set the server sends itself** (no client hook; P from the above): `_Defeat_OnDead` / `_Defeat_OnFade`
/ `_Defeat_OnIncapacitated` / `_Defeat_OnRevive` on deaths and revives, `_Entity_OnEnterWorld_Default` (or
`Vfx_Spawn`) on spawns, `_Advancement_LevelUp`, `Object_Closed` / `Object_Open` on doors, `Vfx_GuideArrow(_Ping)`
through the guide script, `Vfx_CapturePoint_BeingCaptured` / `Vfx_TeamColor_SetContention` on contested points,
`Destructible_OnBreak*` / `Vfx_OnExplode` on destroyed props, and whatever the champions' skill scripts
`RunScriptlet`. Team colour, respawn, low health, selection and capture results are client hooks driven by
properties (`0x1000009C`, life state `0x100000FA`, vitals).

---------------------------------------------------------------------------------------------------------------------

## 3. Animation-graph events

### 3.1 Mechanism (C)

* Names: enum `0x300000A4` (1 298 entries, base `0x30000127` = `Footfall` / `Invalid`), pack `0xA0000038`.
  Per-graph enums (`0x1A` behaviour graphs, `0x1C` small graphs) map them to the graph's own events
  (`catalog/data/animation_graphs.tsv`).
* A server script raises one with node **`0x1000004E` RaiseGraphEvent(entity)[event]**; its client execute runs
  scriptlet **`_HFSM_BehaviorRaiseEventAction 0x100001E3`** on the entity with scriptlet variable **`0x780`** =
  the event (enum kind 8). `0x100001E3` is an immediate at `0x9CE27B` (client HFSM) and is in 2 tables (the
  champions' shared ones). `ics/script_runtime.py _raise_graph_event` and `icserver/tutorial1.py raise_events` /
  `icserver/finale.py` already send exactly this (`0x8D` with variable `0x780`).
* Cinematics do not use the scriptlet: their A lists name graph events directly and the client raises them on the
  actor (C for the data; the cinematic player's code is in `actor-creation-and-environment.md`).

### 3.2 Events the data raises

* **Scripts** (the 826 trees of `data/script_trees/` plus 46 more decoded from the map packs, among them the 15
  cinematic scripts; 8 of the 54 extra trees duplicate project trees, so use counts can be 1 too high): 241
  distinct events.
  Most used: `skill_to_locomotion 0x10000002` (30 uses / 28 scripts), `Wildcard_RSkill 0x100003BF` (19),
  `Wildcard_QSkill 0x100003BD` (17), `Wildcard_WSkill 0x100003C0` (17), `Wildcard_ESkill 0x100003C2` (15),
  `CbtState_KnockBack 0x1000005E` (13), `CbtState_EnableHit 0x100003AE` / `CbtState_DisableHit 0x100003AF` (9),
  `Skill_Dash_End 0x100003C3` (8), `UnSheath_Blade 0x100004C7` (8), `CbtState_Cower_Recover 0x10000178` (7),
  `CbtState_GetUp 0x1000009D` (7), `Empowered_Attack 0x100002F8` (5), `CbtState_Cower_Instant 0x100002BA`,
  `Fidget_Abort 0x1000001D`, `Global_Locomotion_Melee 0x10000468` (4), `Emote_Abort 0x100001F2`,
  `Recall_Start / _End / _Abort 0x100005BA / BB / CF`, `CbtState_Stasis(_Recover) 0x1000046C / 6B`,
  `CbtState_Death_Induce 0x100000AD`, `CbtState_Knockdown 0x100002F5`, `Death 0x100001C0`, `Land 0x100000C8`;
  the other ~200 are one per champion skill (`<Champion>_<Skill>(_Start/_End)`).
* **Cinematics** (A lists): `CinematicCombatBasicAttack 0x1000010F`, `CbtState_Death_Induce 0x100000AD`,
  `CbtState_Knockdown 0x100002F5`, `CbtState_GetUp 0x1000009D`, `CbtState_KnockUp 0x10000020`, `SpawnIdle
  0x10000183`, `Combat_Special_Attack_2 0x100000EB`, `Combat_Locomotion 0x1000024D`, `CommitFidget 0x10000132`,
  `Emote_Joke 0x1000022E`, `Emote_Taunt 0x1000022C`, `Emote_Laugh 0x1000022D`, `CbtState_Laugh 0x100001C8`,
  `Batman_Gaslight_Batflight 0x100000E2`, `HarleyQuinn_PuddinTime 0x1000036F`.
* **Server (ours)**: `CarPickup 0x10000246` (lift), `CbtState_Knockdown 0x100002F5`, `CbtState_Dead 0x1000010B`,
  `CbtState_GetUp 0x1000009D` (tutorial knockdown), optional `state_to_locomotion 0x100000BB` after a throw.
  What the server must raise in a full match: every `RaiseGraphEvent` of the skill / status scripts it runs (the
  script runtime does it), knock-back / knock-up / stun states from the status scripts (`CbtState_KnockBack`,
  `CbtState_Stasis`, `CbtState_Cower*`), `Recall_*` for the recall channel, `CbtState_Death_Induce` / `GetUp`
  when a champion dies / revives if `_Defeat_*` is not used (P).
* Beware of the collisions between the two tables (examples: `0x100000BB` is `state_to_locomotion` as a graph event
  and the PlaySound node id; `0x100002F5` is `CbtState_Knockdown` and `_Entity_OnEnterWorld_Default`;
  `0x100000EB` is `Combat_Special_Attack_2` and `Vfx_Active`).

---------------------------------------------------------------------------------------------------------------------

## 4. Audio

### 4.1 Packaging (C)

* `audio\Audio_SB.pck` (41 banks, `sfx`) and `audio\<language>\Audio_SB.pck` (126 banks for English); `Audio_Str.pck`
  = streamed media. `AKPK` header: `size | version 1 | language map size | bank table size | stream table size |
  external table size`, then the language map, then `n | n x (bank id, block size, size, start block, language)`.
  Banks are standard `BKHD` / `DIDX` / `DATA` / `HIRC`; HIRC object type 4 = event.
* `0x52` records (`did | bank id | len | name`) name 161 banks; every one is in a `.pck`; 6 `.pck` banks have no
  `0x52` record. Bank id = event id rule = FNV-1 32 of the lower-case name (C on three names).
* Which pack carries a bank decides when it is loaded: champion packs carry `chr_<Champion>`, `chr_<Champion>_VO`,
  `FE_chr_<Champion>` (front end: champion select); map layout packs carry `Announcer_<Map>`, `Announcer_General`,
  `AMB_<Map>`, `Music_<Map>`, `Destruction`, `Turrets`, `mse_<event>` (map events); `0xA00000D0` carries `UI`,
  `Announcer_LOBBY`, `Announcer_Wrapper`, `Announcer_Store_and_Advancement`; `0xA00000B3` `GlobalElements`;
  `0xA0000037` `Init`; lobby music packs `0xA0000188/189/18A` carry `FE_Music_Lobby_<Map>`.

| Group | Banks (`0x52` DID: name) |
|---|---|
| Global | `01` Init, `07` UI, `0A` GlobalElements, `0B` Announcer_LOBBY, `0C` Announcer_Wrapper, `4E` Announcer_Store_and_Advancement, `8E` VO_Coaching, `84` VO_Tutorial_Lobby |
| Lobby music | `2C` FE_Music_Lobby_CoastCity (`0xA0000188`), `65` FE_Music_Lobby_GothamHeights (`0xA0000189`), `5C` FE_Music_Lobby_Divided (`0xA000018A`) |
| Map music | `14` Music_CoastCity, `66` Music_GothamHeights, `5B` Music_Divided (GD, Tutorial 1, Crime Alley) |
| Ambience | `03` AMB_CoastCity, `64` AMB_GothamHeights (GH, Tutorial 1), `63` AMB_GothamDivided (GD, Crime Alley), `67` AMB_Tutorial (Tutorial 1, Crime Alley) |
| Announcer | `10` Announcer_General, `11` Announcer_CoastCity, `12` Announcer_GothamHeights, `15` Announcer_GothamDivided (the last three also in `0xA00002E6`) |
| Map objects / events | `04` Destruction, `06` Turrets, `05` mse_DoomsDayDevice, `0D` mse_EarthQuake, `0E` mse_Meteor, `2D` mse_MeteorStorm |
| Tutorial VO | `8F` VO_Tutorial_Hero (Tut 1, Crime Alley, `0xA0000316`), `7C` VO_Tutorial_Intermediate, `83` VO_Tutorial_Advanced (`0xA00002E6`) |
| Minions | `09` chr_min_pvp, `6D` chr_Min_DDD_Guardian, `6E` chr_Min_Leviathan, `6F` chr_robovender, `70` chr_Min_Raider |
| Champions | `chr_*` (in game), `chr_*_VO` (voice), `FE_chr_*` (champion select): the other 120 records |

### 4.2 Music

* **Lobby music: template property `0x10000897`** (C, all 21 encounter templates in `0xA00000B3`):
  `0xA0000188` (Coast City, Crisis Labs CC, CC v AI, Doomsday Device Defense), `0xA0000189` (Gotham Heights, GH v
  AI), `0xA000018A` (everything else: tutorials, Gotham Divided and its variants, Crime Alley, Clashes, challenges,
  Apokolips). The client loads that pack in the lobby (P: no message needed).
* **In-match music = the encounter environment system** (section 4.4): rule record per encounter (property
  `0x100009E7`): `0x48000F28` Tutorial 1, `0x48000FF0` Tutorial 2, `0x48000ABD` Gotham Heights (+ v AI),
  `0x48000ABE` Coast City family, `0x48000E7D` Gotham Divided family, `0x4800128B` Crime Alley family (v AI, 1vAI
  tutorial, Clashes, Apokolips, turret / multibot challenges). Their hashes are `Music_<Map>` events (Crime Alley
  and the tutorials reuse `Music_Divided`).

### 4.3 Announcer

* **`0x10000802` = the encounter's announcer set** (an entity of the layout pack; its template `0x49......` holds
  `0x1000080A` = list of `0x1000080C` tables): `0x4000047E` GH, `0x40000534` CC (also the test / surrogate
  encounters), `0x40000554` GD (also Metropolis Skyway), `0x40000D4C` Crime Alley family, `0x40000D70` (GD jungle
  challenge), `0x40000B69` Tutorial 1 (its template `0x49000B69` has **0 properties**: no announcer lines in Tut 1),
  `0x4000047A` Tutorial 2 (the shared set, also every map's `0x10000803`). C.
* Each `0x1000080C` entry: `0x10000806` = match-event enum (GH uses 0xA-0x11 and 0x36; CC / GD / CA 0x1F-0x42;
  the shared set 0x8, 0x12-0x1E, 0x34) -> `0x10000895`, `0x10000829`, `0x1000082A`, `0x10000894`, `0x10000805`
  (enums, values 0x96-0x2D7) and bool `0x1000088E`. The values are **line ids, not Wwise hashes** (no value
  resolves to an event), most likely announcer dialogue lines chosen per context (own team / enemy / neutral /
  spectator, P) and played by the dialog element message **`0x2039`** (`protocol-server-to-client.md`). The same
  value range appears in the environment rules' `0x100009F2` groups (`0x100009F3` ids per `0x100009F5` group 3 /
  6). P.
* Strings: `0x2B000093` (announcer, 32 lines in Tutorial 1's packs). The announcer's audio is in the
  `Announcer_*` banks.

### 4.4 `CEncounterEnvironmentSystem` (music cues)

Rule record (DB type `0x29`, a `0x48` record): `0x100009D2` = list of `0x100009D4` rules; optional `0x100009F2`
(groups of announcer line ids). A rule: `0x100009E5` cue id, `0x100009D9` Wwise event (start), `0x100009EE` /
`0x100009DE` more events (stop / alternative, P), `0x100009E4` = list of `0x100009E6 {0x100009E0 event,
0x100009E5 cue}` (what to play when another cue fires while this one runs, P), `0x100009D6` (3 / 4 / 5: a
priority or slot class, P), `0x100009D5` (team or count: 1-3, 0xA, 0x64), `0x100009DF` flags (0x10, 0x1A, 0x28,
0x60, 0x68), `0x100009DB` (3 / 4), `0x100009D7` f32 (3.0 s), `0x10000A01`. Every event hash is in the map's
`Music_<Map>` bank (C); one rule per record plays a `UI` event (`0x9C068F88`).

Tutorial 1 (`0x48000F28`): cues 4, 1, 2, 0x18, 0x1F, 0x1E, 0x19, 0xF, 0x11, 0x12, 0x1A, 0xE, 0xD, 0x13, 9, 3.
The cue ids are raised client-side (`protocol-server-to-client.md` 2: life-state changes per team -> cues 0xD /
0xE / 0x13 / 9; `0xA59C80` -> 0xF / 0x11 / 0x12 / 9; game events 3 and 6 -> 0x19; champion in danger -> 0x1B /
0x1C). So **the server drives the music only through state**: life state `0x100000FA` and team of units, game
events, match start / end (P: cue 4 / 3 = match start / end with `0x100009D5 = 0xA`). No message plays a music
cue directly (C: no path from the 336 handlers, earlier note).

### 4.5 Sounds the server triggers directly

* **Cinematics**: their sounds play with them (section 1). C.
* **Scriptlets**: sound actions inside `0x1D` tables (`1 | 0x19...` cue records; e.g. door `Object_Open` sound
  `0x19000A61`, light wall `0x19001299`); every `0x8D` the server sends can carry sound. C (data), P (cue format).
* **Script node `0x100000BB` PlaySound(team, event)**: 13 hashes in the data: `GlobalElements` (`0x4ACA6D64`,
  `0xFDDB39B6`, `0xC40A26C9`, `0xAE992E25`), `UI` (`0x92A57D8A`, `0x718BA2B9`), `AMB_Tutorial` (`0x3EB822F0`,
  Tutorial 2 / Crime Alley cinematic scripts), `Music_Divided` (6 events). Client execute `0xAB6820` checks the
  local player's team against the node's team value (-1 = everyone). Whether the server can make the client run
  it (it is a server script node) is open: a script runtime that runs this node would need a message that plays a
  Wwise event, and none is known (?).

---------------------------------------------------------------------------------------------------------------------

## 5. Other render-side state the server affects

### 5.1 Lighting environment (`0x956`)

* Node `0x1000009C` (11 scripts, 31 uses): `[1, value, 0, 0, 0, 0, 0]`. Client execute `0xAB4AE0`: if the first
  byte is set, take the local player's entity (`0x6351D0` -> IID at `[0x1B6A710]`); value 0 -> `0x58B4C0(entity,
  0x956, 0)` (remove), else `0x54FC60(entity, 0x956, &value, 0)` (set); then `[[0x1B73518]+0xF6] = 1` (world
  render: re-evaluate lighting). C.
* Values used: `0x10000016` (every cinematic, on enter), 0 (exit), `0x1000001B` (CC victory), `0x1000001C`,
  `0x1000000A`, `0x1000000B`, `0x1000000D` (match / victory scripts), 2 (two scripts; = the default of the
  reader). Last pattern `[0, 0, 1, 3]` once. P: the values name lighting setups of the map's environment records
  (zone records `0x08000003` / `0x08000016`, tutorial inventory 3.4).
* Reader `0x7E35C0` (only caller `0x7E66E8`, the render-model setup, result stored at model `+0x11C`): property
  `0x956` of the local player, default 2; if 2 / absent -> property `0x5CC`; then `0x216`; then the model owner's
  `0x216`. So the lighting environment is a **local-player property** the server can set too (send `0x956` on the
  player object with `0x6` / `0xBC`; P) to reproduce the cinematic look; our server does not send it.
* The patched exe already speeds lighting re-evaluation (patch at `0x11DB16C`, 2.5 s -> 0.2 s).

### 5.2 Environment-state objects

* `_CEntitySystem_EnvironmentStateChange 0x10000413` runs on an entity when its property **`0x1000065C` or
  `0x1000065D`** changes (`0xA813F0`: ids `0x1000065C..0x1000065D` -> `0xA7AFA0`, which runs the scriptlet with
  variable `0x1000069C` = the new value; registered by `0xA5A7E0` only when the entity has bool `0x10000554`). C.
* 25 tables carry it (zone packs; Tutorial 1's `0x1D00008E/8F` on the environment objects `0x2E0002AB/AC`:
  `Vfx_Active` with particles `0x1800010A/B`). These are the map's switchable ambience (lamps, sparks, smoke) and
  the closest thing to "weather" in the data. Who set `0x1000065C/D` in the original (server property update or
  the environment system) is open (?). Test: send `0x1000065D = n` with `0x10000554 = 1` on such a static's IID.
* No weather / lightning / rain record or string exists in the exe or the tutorial packs (C, earlier notes);
  meteors are props + scriptlets (`tutorial-data-inventory.md` 5.6).

### 5.3 Fog

* Fog of war is client-side, driven by the local team, vision sources and `0x2179` revealed cells; the server hides
  unseen enemies with `0x90F` (`movement-collision-fog-map.md` 2). World fog draws only when the renderer's
  `EnableFog` / `EnableMaskFog` bytes are set (same note); no server message toggles them (C for the bytes'
  location, ? for any setter).

### 5.4 Team colour and relation

* Client-computed from PVP team `0x1000009C` on every change, then `_Entity_OnSetClientRelationship` runs
  (`targeting-and-relations.md` 3). `0x10000CF0` overrides the colour (seen on the power core actor of
  `0x35000038`). C.

---------------------------------------------------------------------------------------------------------------------

## 6. What the server should do with this (P)

1. Cinematics: play them with `0x20F5` (mask 1 + DID); bind player actors (`needs_binding` = 1) through bit 2 with
   the actor variable (`1`, `0x10000001..5`) as key -> the player's champion IID, or they are skipped. Match intros
   `0x35000023/20/24/3C`, victories `0x35000012/13`, `0x35000014/15`, `0x3500003A/3B` (send the event to match the
   winner: the record carries `0x100000F2` / `0x100000F3`), GH end `0x3500000D/0E`.
2. Run the cinematic's script (`ics/script_runtime.py`) when one has one: they start the conversations, set the
   lighting environment and end with `0x10000060` chains.
3. Send the `_Defeat_*` / spawn / door / guide / capture-contention scriptlets listed in 2.3; leave the client hooks
   (team colour, respawn, capture result, low health) to property updates.
4. Graph events only through `0x100001E3` + variable `0x780` (already done).
5. Music and announcer need no messages beyond correct state (life state, teams, game events) and `0x2039` for
   announcer lines; lobby music comes from the template.
6. Optional: `0x956` on the local player for cinematic lighting outside a cinematic; `0x1000065C/D` to switch
   environment objects (test first).

## 7. Open points

* The camera key tail words (interpolation 0/1/2, the f32 -1.0 / -0.6) and the scriptlet entry flag.
* `0x3500002D` (landblock `0x0105`, duration 0): placeholder or a "camera-less conversation" cinematic.
* Names of the `0x956` values (`0x10000016`, `0x1000001B` ...) and of node `0x1000019D` (match intros).
* Who sets `0x1000065C/D`; the meaning of the environment rule fields `0x100009D5/D6/DB/DF`.
* Announcer line ids (`0x10000895` ...): which string / Wwise event they select.
* The 297 table slots `rp.script_tables` misses (champion packs); a DID-free table finder would close them.
* `records()` in `tools/script_decoder.py` skips scripts with the `did | 1 | 1 | <node>` header (15 map-pack
  cinematic scripts at least): `python tools\script_decoder.py all` should accept them (project change, not made
  here).

## Appendix: method (scratch, not committed)

* Cinematic parser: section 1.1 as code; a record is accepted only if every count is sane and it ends exactly at
  the next listed DID (true for 30 / 30).
* Enums: `did | base | kind | n | n x (key, len, name padded)` for the `0x30` records of `0xA0000038` (12 parse
  this way, among them `0x30000013` and `0x300000A4`).
* Wwise: `AKPK` header as in 4.1 (note the 6th header word: external table size), then each bank's `HIRC` objects
  (`u8 type | u32 size | u32 id`), type 4 = event.
* Script decoding: `tools/script_decoder.Decoder(exe).decode(did, data[k:])` at offsets whose header is `did | 1 |
  1`; described with `ics.script_model.describe` (trees in the scratch folder, not in `data/`).
* Code: capstone over the mapped image of `C:\Infinite Crisis Server\InfiniteCrisis.exe`; immediates of scriptlet
  keys searched in `.text` (a hit is a candidate hook, not proof).
