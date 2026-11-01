# Crime Alley: scenery the match lacks (base gates, base aura, hex strips) — static survey 2026-10-23

Context: tester report 2026-10-23 (Crime Alley vs AI, encounter `0x40000C82`, map `0xA0C112BA`, 0x20AF packs
`0xA00002E5/E6/E7` + `0xA0000116`, `0xA0000073`, `0xA000022E` + champion packs): the blue gate at the start, the
"white zones" of the base and other scenery do not appear. Tags: C = read in the data, P = probable, G = guessed
(frames / geometry), O = open.

Method: statics `0x820113BB` / `0x820112BB` / `0x820114BB` of `0xA0C112BA` parsed (format `maps-complete.md` 2.2;
330 entries in 0x13BB), layout `0xA00002E6` read with `Data.layout`, pack membership of every DID from the pack id
lists of all `rp\*.rp`, records dumped raw, scripts with `ics.script_model`, the champion navmesh with
`ics.match.maps.navgrid`, and the original-game frames (`video\f00..f22`, minimap scale: core 17.5 -> 60 px,
enemy core 142.5 -> 465 px, 3.24 px/m).

## 1. What the client already places (statics) vs what the server must create

- **Statics are complete.** Every world state in the three Crime Alley landblocks resolves, three reference levels
  deep, inside the sent or resident packs (`0xA00002E5/E6/E7`, `0xA0C112BA`, resident `0xA00000B3/DF`); the only
  unresolvable ones are type-3 editor markers that exist in no installed pack (`0x2E0011A6`-`AD` structure markers,
  `0x2E000AF8/AF9` lane mouths, `0x2E000944/945/1117/1120` jungle, `0x2E00110F/1110/1118/111B/1121` emitters) (C).
  One leftover: `0x2E000FF3` (157.6, 84.6) names `0x50000029`, only in `0xA000024C` (C, cosmetic).
- Base statics already placed by the client (C): spawn platform `0x2E000CA5` at (5.5, 77.5) yaw -90 and
  (154.5, 77.5) yaw 90 (ctype 3, `.entity 0x2D000A82`, Havok plate about 18 x 18 m; the same world state sits on
  every map's spawn: GH (4.0, 46.2), GD (7.5, 152.5)); core pedestal `0x2E000A3B` (17.5, 77.5) / (142.5, 77.5);
  core-area pieces `0x2E001207`, `0x2E0011B7/B8`, `0x2E001185`, `0x2E001402` (17.5, 77.5) and `0x2E001297`,
  `0x2E001228`, `0x2E0012D2` (142.5, 77.5).
- **Not statics, not in any layout placement for Crime Alley: the base gates, the base aura and the hex strips.**
  All their records are in the sent pack `0xA00002E6` (base table `0x1D000385` in resident `0xA00000B3`), so no
  pack change is needed (C).

### 1.1 Base gate (the tall blue light wall)

| Item | Value | Tag |
|---|---|---|
| Class | Door `0x40000557` (template `0x49000557`: `0x7D2 = [0x1D0000D0]`, `0x10000AA7 = 1`, `0x50F = 8`, `0x8C1 = 6`, `0x1000019D = 0x2000`, `0x149 = 0x08000000`, `0x510 = 0x2E000CD7`, then a collision polygon) | C |
| World state | `0x2E000CD7` (`.entity 0x2D000AA9`, ctype 9, table `0x1D000461`: Object_Closed, Object_Melee_Attack, Object_Open, testfx; base `0x1D000385` team colour) | C |
| Visible wall | child `0x2E000CD8` (`.entity 0x2D000AAA`, table `0x1D00038B`: Vfx_Startup, Vfx_Active_Red / Purple / Blue, Vfx_TeamColor_SetParentColor), spawned by Object_Closed | C |
| Model box | `0x2D000AA9` bounds (-10.92, -0.14, 0) .. (10.92, 15.0, 3.24): ~21.8 m wide, 15 m on one axis; layout scale `0x7BD` = 0.9 (`world.spawn` only reads `0x6B3` / `0x6B4`) | C values, P axes |
| Data position | "BaseGate" in Tutorial 2 cinematic `0x35000029`: (0.0, 68.27, 200.03) yaw -90, side 3, LB 0x13C3. Tutorial 1's `01GateA` (159.86, 28.04) LB 0x13CB has the **same offset from its core** (-17.6, -9.4): a base-prefab position, outside Crime Alley's walkable base (navmesh row y 68 starts at x 4) | C (T2), G (as CA's) |
| Crime Alley position | **the base's lane mouth**: navmesh corridor starts at x 29.0-29.5, open y 72.25-82.75 (10.5 m); team 1 (29.5, 77.5), team 2 (130.5, 77.5), wall across the lane (along y) | C (navmesh), P (frame f02: wall just east of the core platform) |
| Timing | frame f01 (video 46 s) timer 00:34, f02 (69 s) 00:11 with the wall up, f03 (92 s) 00:12 with the champion already at the x 65 turret: the timer counts down the pre-game, the wall stands during it and is gone after 0:00 | P (strong) |

### 1.2 Base aura (the base / fountain zone)

| Item | Value | Tag |
|---|---|---|
| Class | Base `0x40000C7F` (template `0x49000C7F`): `0x1000009C = 1` (team 1 fixed), `0x100002AA = 6.0` (P radius), `0x100002C4 = 0x48001109`, `0x10000213 = 0x48001107`, `0x510 = 0x2E000A35`, `0x50F = 8`, `0xEF = 0x3A000001`. GH's `0x4000041F` is the older one (`0x100002C4 = 0x4800028B`, regen script `0x3400012B`) | C |
| World state | `0x2E000A35` (ctype 9, tables `0x1D000385` + `0x1D0003DE`: Hotspot_Activate, Hotspot_Deactivate, Vfx_Active_State0 / State1) = the visible zone | C keys, P look |
| Status inside | `0x48001109` (stacks 1, flags `0x8000`) -> script `0x340006C1`: StartVitalOverTime health / energy / mana (`VitalPercentChangePerSec`), AddAttributeModifier `0x10000459` (in base) + `0x10000A23` (may shop), move speed `0x100005E4` (`IncreasedMovement`), status icon `0x480006A3`, scriptlet `0x10000343` (Vfx) on the champion; all removed on exit | C |
| Status on leaving | `0x48001107` (flags 8) -> script `0x340006C0` "TempDefender": speed buff + icon `0x480006A3` for `EffectDuration`, ends on damage / attack (T3 conditions) | C tree, P reading |
| Mechanism | hotspots are server volumes (`full-combat-skills.md` 4.2: status A while inside, C on exit); no client code | C |
| Invulnerability | **no invulnerability status, attribute or script in the base data** (the base's two statuses, the spawn platform and the Foundry were read). The base's defence in data is the Foundry turret `0x40000170` / `0x4000016F` (already spawned). The tester's "invulnerable white zone" is P the aura zone `0x2E000A35` with the regen | C (absence), O |

### 1.3 Purple hexagon strips

| Item | Value | Tag |
|---|---|---|
| Look | flat purple hex fields on the lane edges near the map centre; champions walk into them (f04: the player's bar inside one); f06 / f08 / f12 | C (frames) |
| Reading | stealth brush: status `0x4800028C` (flags `0x8000`) -> script `0x340001CF` (IsHidden `0x100007BF`, BrushIID, StealthRevealed, scriptlets `0x10000648` / `0x10000649` / `0x10000647`); visual P world state `0x2E000D36` (ctype 3, table `0x1D000509` Vfx_Active, box (-2, -1, -1)..(2, 1, 3): a 4 x 2 m tile); generic class `0x4000039D` "Hotspot Object" | C records, P link |
| Positions | not in any Crime Alley record (statics, layout, cinematics); from the frames with the minimap scale: north edge x 75-85, y ~81.5; south edge x 71-77 and 83-89, y ~73.5 (gap at 80) | G |

### 1.4 Other differences in the frames

- **Three jungle camps** (white minimap dots after "Jungle Creatures online", f06+): x ~50, ~80, ~111 on the jungle
  arc, i.e. the two jungle passages (48-56 / 106-114, y 83-96) and the nook (80, 97-100); `maps.py` has one (C frame, G pos).
- **No structure at x 25.5**: the original minimap shows four blue icons (Foundry 1.4, core 17.5, 40, 65) and four
  red; no Crime Alley marker exists at 25.5 either. The spec's `core_turret` (G) is probably wrong for this map (P).
- The ring turret with a blue hologram (f03 / f06) is the lane turret at 65 with its head `0x2E000AA8` (already sent).

## 2. Packs

`0xA000009A` (GH zone, category 13) is not needed: nothing above, and no Crime Alley static, depends on a DID only
there (C, depth-3 scan). The earlier load hang at 15 % when it was named is consistent with a second zone-category
pack in 0x20AF (P). Do not name it; no other pack is missing.

## 3. Server changes, by confidence

1. **Base gates** (C classes, P position / timing): spawn Door `0x40000557` (ws `0x2E000CD7`) per team at (29.5, 77.5)
   / (130.5, 77.5), wall along y, team `0x1000009C`; play Vfx_OnInit + Object_Closed (as `prop_initial_scriptlets`);
   block the navmesh across y 72.25-82.75 (the `prop_blockers` box for `0x2E000CD7` is [7.0, 0.5] and must lie
   along y here); at the match start (end of `match_pre_start`) play Object_Open and unblock. Config list with
   positions so the Tutorial 2 position (0.0, 68.27) can be tried.
2. **Base aura** (C data, P radius / values): spawn `0x40000C7F` at (5.0, 77.5) / (155.0, 77.5) (team 2 with
   `0x1000009C = 2`), play Hotspot_Activate / Vfx_Active_State1; server volume radius 6 m (config): allies inside get
   `0x48001109`, leaving gives `0x48001107` (`script_runtime.apply_status` / `remove_status`); script values
   `VitalPercentChangePerSec`, `EffectDuration`, `IncreasedMovement` are not in records (O: config). Then
   `shop_anywhere` can default to false. Optional damage immunity in the zone only behind a config (G).
3. **Stealth strips** (P): `0x4800028C` while inside 4 x 2 m boxes at the G positions, visuals `0x2E000D36`,
   enemy vision hidden while IsHidden.
4. **Jungle**: three camps; drop or verify the x 25.5 core turret (P).
