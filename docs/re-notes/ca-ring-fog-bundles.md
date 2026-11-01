# Crime Alley: turret ring and fog attribute wiped by full bundles, sight line through objects, jungle-mouth fields toward the lane (2026-10-29, fase3-in)

Tester report 2026-10-29 19:55 (build fase3-im, Crime Alley v AI, AGL vs bot Arcane Supergirl, server run 19:46-19:55).
Evidence: `logs/traffic.log`, `logs/server.log`, `logs/diag.log` (`--skills --hover` only: no `--fog` / `--ring` lines
in this run), screenshot `63.webp` (west jungle mouth, match 04:52) and the earlier `56` / `57` / `59` / `62.webp`, the
decompiled client (`re-work/decomp`, image base 0x400000), capstone reads of `InfiniteCrisis.exe` and the installed map
pack `0xA0C112BA` (heights read back through `icserver/terrainfix.py`). Tags: **C** confirmed, **P** probable, **O** open.
Builds on `ca-fog-stealth-hover.md`, `ca-fog-ring-announcer.md`, `ca-black-strips.md`, `object-update-bundles.md` 0.3.

## 0. The common cause (C)

`[ics] object_update_mode` is `"bundle"` (the default). Every update of a moving champion, bot or minion is then a full
bundle (0xF2 + 0xB0 + 0xBC), and the 0xBC is a diff that **removes every own id of network mode 1 / 3 that it leaves
out**, or sets it back to the template value (`0x62AFD0`, object-update-bundles.md 0.3, C). fase3-il / -im set two
such ids by event 0x6 only:

| Id | Net mode | Template value | Set by | First full bundle after it (traffic) |
|---|---|---|---|---|
| `0x1000019D` = 0x200008 (Character + Player) on AGL | 1 | 8 (champion templates) | `vital_notices_on` 19:48:32.161 | 19:48:39.968 "credits 0, 1 items" (1532 bytes, no 0x1000019D) |
| `0x100008CE` = true on AGL | 1 | none | `see_through_blockers` 19:48:32.161 | the same bundle; then every tick AGL moves |
| `0x100008CE` = true on allied minions | 1 | none | `Units._late_vision` | their next per-tick bundle |

`vital_notices_on` is re-run after full bundles only in delta mode, and in this run only at 19:48:32, 19:51:28,
19:52:11 and 19:53:59 (respawns). So the Player bit and the fog attribute each lived a few seconds at most. The allied
structures are not re-bundled after 19:48:33 (none in traffic), so theirs stayed.

## 1. Turret warning ring (item 5)

- Registration works (fase3-il diag --ring: the enemy turrets 0x106 / 0x10C and the core registered; this run's
  bundles carry 0x10000C5D, 0x10000C5B, 0x10000133 = 9.0 and 0x1000019D = 0x210, C traffic 19:48:22.333).
- The ring stays in state 6 until entry +0x4C is set (0xA84FB0, C). Only the phantom callback **0xA3A5F0** writes it:
  for a unit entering r + 5.5 m it tests `0x9D0180(ent, 0x10000)` (Minion: unit list), else
  `0x9D0180(ent, 0x200000)` (Player, at 0xA3A695) and the local champion's IID (0x85D6D0), then `[entry+0x4C] = inside`
  (0xA3A6C5) (C, disassembly). The phantom's own filter (0xA2A710) stores team `0x854050(turret)`, relation 2 and the
  PerceivedType mask **0x210000** (Minion | Player) (C).
- With the Player bit gone from the second bundle on (section 0), the champion never counts as "inside": no ring in any
  colour (P strong; the runtime proof is the new diag line, below). The option byte `0x186CE4F` (TurretWarningEnabled)
  is 1 in the exe's .data (C); the user's options can still turn it off.
- Fix: `[ics] champion_flags_in_bundle` (true): `vital_notices_on` also stores the flags in the champion's
  `extra_props`, so every later bundle carries 0x200008 (an equal value notifies nothing and the cache keeps it).
- `tools\diag.py --ring` now also logs the phantom callback: `HOT RING phantom: unit enters / leaves` (entity, IID,
  inside), `... Player bit 0x200000 (al 0 = missing)` and `... our champion inside (ring may show)`.

## 2. The black strip by the fence (item 2): fog, not missing ground

### 2.1 Not terrain / geometry (C)
- Installed heights (block 13BB, m): every vertex of x 40-105, y 55-100 is at 199-200 except (60, 75) / (65, 75) at
  0 m (under the lane mesh and the turret) and the south alcove (85-90, 55-60). The strip x 70-76, y 81.5-83.1 lies in
  cells (70-80, 80-85), all four corners 199.98 / 199.0: two flat far triangles. A funnel wall around (60-65, 75)
  projects only to screen rows below its rim (the camera looks north and down 57 deg), i.e. under the lane mesh, never
  north of the lane at y 81.5 (C geometry).
- The baked colour texture `0x13003439` has the curb (y ~82.2), grey bricks and the garden there (C, read).
- No static covers it (`ca-black-strips.md` 4), and the champion navmesh is walkable up to y 82.6 over x 60-90 (C).
- The black is pure (RGB 0-3 in `59.webp` at rows 330-370) with straight, pixel-sharp edges, exactly like the
  `57.webp` wedge between AGL and the SUV (RGB 1, 2, 0), which has its apex on the vision source. That figure is the
  fog occluder pass (0xAAE0E0, `ca-fog-ring-announcer.md` 1), not a hole in the ground.

### 2.2 Why fase3-im's attribute did not hold (C)
- The attribute read is `0x974940 -> [ent+0x84] -> 0x973730`: base value from component vt+0x60, then the modifiers.
  Vtable `0x1609B78` (read from the exe): slot +0x5C = 0x970B80 (bool getter), **slot +0x60 = 0xA9DC90** =
  `0x58B320(entity, id, &variant)`, the entity's own property in container 4 `[ent+0x38]` (correction of
  `ca-fog-stealth-hover.md` 1, which named 0x970B80; the conclusion stands: no base value = default false).
- 0x100008CE is net 1 with no template value on champions / minions, so the first full bundle after the 0x6 removed it
  (section 0): from 19:48:39.968 on AGL's circle ran the occluder pass again, and every moving allied minion's too.
- Fix: `[ics] vision_through_blockers_in_bundle` (true): `see_through_blockers` also keeps `0x100008CE = true` in the
  object's `extra_props`, so its bundles carry it. It follows `vision_through_blockers_property` (off with it).
- O: whether the strip is AGL's circle or the turret's (the turret's attribute was not wiped). `tools\diag.py --fog`
  now logs per source `HOT fog: occluder pass (skip al 1 = 0x100008CE true)` (rva 0x6AE209: source IID, al, radius)
  and each body kept as an occluder `HOT fog: occluder body` (rva 0x6AE32E: source, body type 0x800 = drawn static,
  body IID: top byte 1 = map static, 2 = a server object). If the strip stays: run it and stand east of the blue turret.
- Not a cause (C): the stealth tiles. World states `0x2E000D36` / `0x2E000D37` carry 0x7EB = 7, the static occluder
  value, but a server object (IID top byte 2) occludes only with 0x10000623 (0xA4B920), which they lack.

## 3. Enemy champion not drawn inside our vision (item 3)

- Traffic (labelled bot bundles carry 0x90F): Arcane Supergirl was hidden (0x90F = 1) at 19:51:19-19:51:45 at
  (78.1-81.6, 77.2-77.5) while AGL stood 12.6 m away and then in base, and at 19:53:29-47 near the enemy turret; she
  became visible when she came within AGL's 12 m (19:51:55). Fog flips by 0x6 are not labelled, so the exact moment of
  the tester's case is not in the log (C limits).
- Server rule (`World.fog`): within `fog_vision_radius` 12 m of AGL (allied minions 3 m, structures 9 / 10 / 13.5 m by
  range) **and** a clear line on the match navmesh. That navmesh is a copy where every structure blocks a square
  (`match_structure_radius` 1.6 m half size for lane turrets: 3.2 m in the middle of the lane), every liftable vehicle
  its box and closed gates their footprint (`NavGrid.block`, value 2). A line from AGL behind (west of) our lane turret
  to an enemy 5-11 m further east crosses that square, so the enemy stayed hidden on lit ground; the client's fog does
  not stop at turrets (C code, test).
- Fix: `[ics] fog_line_through_objects` (true): `NavGrid.line_clear(a, b, through_objects=True)` treats object-blocked
  cells as clear; only the navmesh's own holes stop the sight line. Not changed: the 3 m minion vision
  (`match_minion_vision` "min", the tester's 2026-10-25 wish) and the 12 m champion radius.

## 4. Structures' vision (item 4, answer)

Yes. Server: allied structures are fog sources by range only (`fog_structure_by_range`, fase3-ik): lane / inner turrets
9 m, core 10 m, foundry 13.5 m (template 0x10000133, largest value). Client: the same radii were sent as changes at
19:48:33.24 (`turret mid t1: vision 9`, ...), and the fase3-il diag listed the allied turret's circle (9.5 m on the
client). With section 0 the allied structures also keep 0x100008CE.

## 5. Jungle-mouth fields toward the lane (item 1)

- Camera (`stealth-alignment.md` 4.1, yaw 0, pitch 57.5, vertical FOV 46.1 deg; f = 1147 px for the 977 px frame of
  `63.webp`): screen down = -y (C, as the earlier "move the base down" = -y). In 63 (west mouth, AGL's "+" of the
  vertical tile at row 520 = y 85.2): the field's near edge at row ~627 (y ~83.5), the top of the curb at row ~660
  (y ~83.0), the curb's lane edge at row ~733 (y ~82.0) (P +-0.3 m).
- Fix: the two vertical tiles carry `"lane_dir": (0, -1)` in `maps.py`; `[ics] match_stealth_lane_shift` = 1.0 m moves
  them along it before any `match_stealth_overrides`: centre y 85.2 -> **84.2** (west (51.9, 84.2), east (107.95,
  84.2)), south end 83.2 -> 82.2, on the curb's lane edge; the wall edges (x 52.90 / 106.95) stay. The diagonal tiles
  stay (moving them -y would push them into the garden fences); the L stays joined at the inner corner (the vertical's
  top edge y 86.2 still meets the diagonal's corner (52.75, 85.80)). The hide area follows (`inside_strip`). 0 = as
  fase3-im.

## 6. Tests

`tests/test_match.py` `ring_fog_bundles` (4 checks: the champion's bundle carries 0x200008 and 0x100008CE, allied
structures keep 0x100008CE in their bundle properties, both keys off = 0x6 only, an enemy 11 m away behind our lane
turret is seen / hidden with `fog_line_through_objects` true / false) and the stealth block (the lane shift moves only
the two vertical tiles by -1.0 m in y and keeps their wall edge; the earlier layout checks run with the shift at 0).

## 7. Tester should see

1. The turret ring near an enemy turret (yellow / green with our minions under it, red when it shoots us). If not:
   `python tools\diag.py --ring` and send diag.log (the "phantom" lines).
2. No black strip by the fence east of the blue turret, no black wedge between AGL and a vehicle. If it stays:
   `python tools\diag.py --fog` and stand there (the "occluder pass" / "occluder body" lines name the source and body).
3. An enemy champion standing near our lane turret is drawn whenever it is within 12 m of AGL.
4. Both jungle-mouth vertical fields reach 1 m further toward the lane (to the curb).
