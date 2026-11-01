# Crime Alley jungle camps: colour, overhead bar, positions, no centre camp (2026-10-28)

Tester report 2026-10-28 15:00 (run 14:39-15:00, build fase3-ie, Crime Alley v AI, Atomic Green Lantern vs bot Atomic
Wonder Woman; screenshots 43-46 ours, 47 the original): (1) the jungle drones (Tripod `0x40000CA0`, Heavy Tripod
`0x40000CA1`, world state `0x2E000BE2`) are grey / metallic, the original's are yellow; (2) no overhead health bar
(selecting one shows "Tripod 202/202" in the portrait only); (3) there must be no camp in the centre; (4) both side
camps stand in the wrong place (original: four drones on the upper sidewalk north-west of the west jungle mouth's
stealth field, mirror on the east).

Sources: the client exe (`re-work/decomp`, base 0x400000, VA addresses; bytes read from `InfiniteCrisis.exe`, the
patched exe is identical at every address used below), the Flash AS2 sources (`re-work/ui-as2/c_a00000d0_02189b08`),
the player's packs read with the server's readers (`ics.gamedata`, `ics.rp`; nothing copied), the original gameplay
video `Downloads\videoplayback.mp4` (Crime Alley Clash 2v2, 1280x720; frames sampled into the scratchpad only), the
tester's recording `Videos\2026-10-27 13-22-10.mp4` (ours), screenshots 24 / 38 / 43-47. `logs\` was empty when this
ran (the directory was emptied at 18:49:58), so the run's traffic bytes could not be re-read: what the server sent is
taken from the code (C) and from the excerpts in test-2026-10-28-1439-sweep.md 2 and jungle-camps-spawn.md 0.
Tags: **C** confirmed (code, data, frames), **P** probable, **O** open.

## 0. Answer in short

| # | Symptom | Cause | Tag |
|---|---|---|---|
| 1 | grey Tripods | The server sends PVP_Team **3** (`[ics] match_neutral_team`) to the client. The client tints only teams 0..2 (`0xA7B0D0`: `cmp edi, 2; ja` at `0xA7B143`): team 3 -> colour index **0** -> `_Entity_OnSetClientRelationship` case 0 -> TeamColor **Null** (`0x10000127`). A neutral creature is **team 0**: colour **6** -> `0x1000011F` -> material `0x16000E7B` RGBA (0.937, 0.710, 0.051) = **yellow**. The team is also never sent as a change for camps (only structures get `late_team`), and every bundle re-sends `0x100007A2 = 0` (`PROP_SIDE`). | C (code + data), P (which of "never ran" / "ran with 3") |
| 2 | no overhead bar | The bar is pushed to Flash **once** per object, with the PerceivedType read from the unit component's change-only cache (`0x9CFBF0` -> `[comp+0xA4]`); with 0 the Flash bar never attaches (`OverheadVitalsBase`). fase3-ie holds `0x1000019D` for the whole phase-in (3.1 s), so a camp seen while phasing gets PerceivedType 0. The camps had no bar before fase3-ie too (frame 24, 2026-10-26), so a second gate is open (team 3 in the status-tag check, or a push before the 0.8 s flags): `diag --camps` decides. The display-type gate itself passes (template `0x10000831` = 1 / 5). | C (gates), P (cause), O (second gate) |
| 3 | centre camp | `maps.py` camp 0 at (80.0, 97.66) ("middle"). The original (Clash video, 00:47 "Phasing Complete") shows the nook's locked pad with no creatures. Without a "middle" camp `Bosses._spawn_raider` spawns the Raider at 300 s (no wait). | C (frame, code) |
| 4 | positions | Today a 2 m ring around (48.75, 93.0) / (111.25, 93.0): 1.1-3 m north of the original. The original (4 frames georeferenced with the client's own camera model, rms <= 3 px): **1 Heavy Tripod + 3 Tripods** per camp, west heavy (48.82, 91.87), Tripods (51.04, 91.91) E, (47.20, 90.33) SW, (49.60, 90.24) SSE; east heavy (110.58, 91.83), Tripods (108.50, 91.82) W, (112.20, 90.31) SE, (109.95, 90.15) SSW = the mirror shifted 0.45-0.6 m west (the exact mirror's SE slot is off the navmesh). | P (+-0.3 m) |

## 1. The colour (C)

### 1.1 Who tints an object: `0xA7B0D0` (C, decompiled + disassembled)

Run by the world-UI manager's listener `0xA813F0` when `0x1000009C` is notified (registered at entity add by
`0xA5A7E0` with notify = 1; a change by 0x6 or a bundle diff notifies; targeting-and-relations.md 3).

```
0xA7B0F4  team  = 0x854050(ent)            ; unit component [comp+0x4C] (watcher, change-only), else property 0x1000009C
0xA7B107  local = 0x854050(local player)   ; 1 in view-match (0xABEE50)
0xA7B120  relation = 0x853380(team, local) -> property 0x10000425      (equal 4, either 0 -> 1 neutral, else 2)
0xA7B13C  colour = 0
0xA7B143  if team <= 2 (unsigned):  colour = 0x10000CF0 if set, else 0xA95AB0(team, local):
              relative (byte 0x186DE9C, default 1, not spectating): 0x8533C0(relation): 1 -> 6, 2 -> 5, 4 -> 3
              absolute: 0x853450(team): 0 -> 6, 1 -> 3, 2 -> 5
0xA7B17D  0x54FC60(ent, 0x100007A2, colour); variables 0x100004A8 = relation, 0x100007A9 = colour;
          runs scriptlet 0x100003A6 _Entity_OnSetClientRelationship
```

So team 3 (or -1) always gives **colour 0** (C, `cmp edi, 2 / ja 0xA7B171`).

### 1.2 What colour 0 / 6 do on the Tripod (C, data)

- The Tripod's tables: class `0x7D2` = `0x1D0000E2`, `E1`, `E8`, **`0x1D000385`**, `0x1D000674`; world state
  `0x1D00042D` (base `0x1D0003E3`, whose `Vfx_Min_Tripod_Active` `0x100008C3` / `_Ranged` `0x100008C2` are empty type 5
  containers). Only `0x1D000385` has `_Entity_OnSetClientRelationship`.
- `0x1D000385` (pack `0xA00000B3`, body +0x410830), entry `0x100003A6` at +0x410B10: props `{0x211 = 1}`, one action
  type **0x22** (persistent container) on property **`0x100007A2`** with 5 children, each `5 | 1 | condition | 0 | 3 | 5
  | 0 | 0 | 1 | 1 | 0x19000A61 | 0x10000004 | value`:

  | condition (`0x100007A2`) | value set on appearance `0x19000A61`, group `0x10000004` |
  |---|---|
  | `== 5` (enemy) | `0x1000011E` |
  | `== 3` (ally) | `0x1000011D` |
  | `== 6` (neutral) | **`0x1000011F`** |
  | `0x500007A2` (no value: 0 / any other) | **`0x10000127`** (the value `Vfx_TeamColor_SetNull 0x10000B0D` also sets) |
  | `== 1` (override 1) | `0x10000128` |

- Appearance parameter set **`0x19000A61`** (pack `0xA00000B3` +0x176459C, 2988 bytes): groups `0x1000006B`,
  `0x1000006C`, `0x10000004`, `0x10000068`, `0x10000069`; the Tripod's `.entity 0x2D0009D0` binds `0x1000006B` (+0xA8)
  and `0x10000069` (+0x588). Group `0x10000004`, value -> material instances (layout `did | 1 | 0x7D0 | 0x7D0 | f32 R G
  B A | 0 | 0`):

  | value | material | RGBA |
  |---|---|---|
  | `0x1000011B` | `0x16000EAB` | 0.502 0.502 0.502 0.5 (grey) |
  | `0x1000011C` | `0x16000E84` | 0 1 0 0.5 (green) |
  | `0x1000011D` | `0x16000E7C` / `E7F` | 0 0.745 1 0.75 (blue) |
  | `0x1000011E` | `0x16000E7D` / `E80` | 1 0 0 0.75 (red) |
  | **`0x1000011F`** | **`0x16000E7B`** / `E7E` / `0x1600142C` | **0.937 0.710 0.051 0.75 / 1 0.745 0 0.75 (yellow)** |
  | `0x10000127` | `0x1600158E` | no colour record (`1 | 0x4A3 | 0x3E8 | 1 ...`): Null |
  | `0x10000128` | `0x160018B4` / `B7` | 0.502 0.376 1 0.75 (purple) |

- Cross-check (C): our lane minions are purple in the tester's recording (2026-10-27, frames 975 s / 1275 s): their
  template `0x49000BF8` carries `0x10000CF0 = 1` -> colour 1 -> `0x10000128` -> `0x160018B4` purple. The tutorial's
  purple drones (fase3-gd) are the same path.
- The overhead bar is tinted by Flash, not by this (C, `utils/TeamUtils.as`): observed team **0** -> `IFF_TINT_NEUTRAL`
  13421619 = **0xCCCC33 (yellow)** in both colourings; own team 0x5AB6F8; any other 0xCC0000 (red); OBJ colouring of
  team >= 3: 0xCCCCCC. Frame 47 / video 304 s: the original's drones have **yellow bars**: the original server sent
  PVP_Team **0** to them (C, only team 0 gives that tint). Our selection panel bar for the Tripod is red (46): team 3.

### 1.3 What our server sends a camp unit (C, code)

- `Units.spawn` (`ics/match/units.py:103`): `ent.team = 3` (`[ics] match_neutral_team`), `ent.side = 0` (line 109);
  `World.properties` (`ics/world.py:276`) -> `creature_properties(ent.team)`: **`0x1000009C = 3`** in the creation
  bundle and in every later full bundle (camp movement states are full bundles, `match_move_message` "bundle"; the
  phase end sends one); `Units._properties` adds **`0x100007A2 = 0`** (`PROP_SIDE`) to every bundle.
- The team is never sent as a change for a camp: `late_team` (units.py:293) runs for structures of team 1 / 2 only.
- So `0xA7B0D0` either never ran for a camp or ran with team 3; both give no tint (colour 0, Null). Even if it ran
  once with team 0, the next bundle's `0x100007A2 = 0` would reach the persistent 0x22 container (bundle diffs notify
  as a 0x6, object-update-bundles.md) and switch it back to Null (P: `0x100007A2` is a local-mode property; if the
  client ignores it from the network nothing happens, so sending 6 is safe either way).
- Server-side uses of team 3 (fog `by_range`, AI, rewards, script VM relations) are right as they are; only the value
  the client sees must change (P: a separate "wire" team keeps the server untouched).

## 2. The overhead bar (C for the gates, P for the cause)

### 2.1 Registration (once, at entity add) (C)

World-UI manager vtable `0x1602D1C` = `0xA50770` (entity removed) / **`0x1602D20` = `0xA3A900`** (entity added)
(the slot names are P; what each function does is C; `0xA3A900` has no direct caller):

```
0xA3A900(iid):  ent = 0x588E90(iid)   ; exists, flags +0x118 (not 0x40 without 8), not a client IID (top byte 0x81),
                                      ; [ent+0x30] != 0
                if 0xA0EFC0(ent): 0xA3A840(ent)
0xA0EFC0(ent):  0x580160(ctype [ent+0x114]) == 2        ; creation type 7 / 8
                if !0x9D0180(ent, 8):  0x10000831 != 0  ; a non-character needs a VitalDisplayType
                if 0x9D0180(ent, 0x80000): no           ; CannotBeCombatTargeted / capture point
                if [this+0x1A] and ent == the controlled agent: no
                return 0xAA05A0(ent) != 0               ; has a life component
0xA3A840(ent):  append (iid, state 0) to this+0x24 / +0x28 (count +0x1C); watch 0x100000FA (notify 1) and 0x10000B2D
```

### 2.2 The push to Flash (once per entry) (C)

`FloatyManagerSystem` tick `0xA5ED60` -> **`0xA50A70(0)`**, per entry: `visible = 0x635160(ent)` (render object
state); **`perceived = 0x9CFBF0(ent)`** = `[unit comp+0xA4]` when the unit component exists (cached only when
`0x1000019D` changes: fog-vision-runtime.md 3, fase3-gd diag), else property `0x1000019D`; a character also needs
relation / alpha; status tags `0x16016AC` = {`0x1000072C`, `0x10000B2D`} must not be set (`0x974940` -> `0x973730`,
which also reads the entity's team through `0x854050`); alive (`0x96E9C0` == 4). A pending entry that passes is pushed
at `0xA50D31` with display type `0x10000831` (`[ebp-0x88]`), attach `0x10000B92`, offset `0x10000B93`, through
`0x904440` ("GM_UI.RecvNotice_UpdateFloatyVitalArray", six arrays) and becomes state 1: it is never pushed again
until it is removed. Fades go through `0x8BED90` (FadeFloatyVitals, queue `0xA23870`).

### 2.3 Flash (C, `gameplay/floaty/FloatyVitalsManager.as`, `gameplay/vitals/OverheadVitals*.as`)

- Character or display type 4 -> `OverheadVitalsDeluxe`; else display type 6-9 -> `OverheadVitalsSimpleLarge`, other
  -> `OverheadVitalsSimple`, created with `{m_iidAttachEntity, m_ePerceivedType, m_eVitalType: Health, m_eVitalDisplayType}`.
- `OverheadVitalsBase`: `m_bHasEntityAndType = m_ePerceivedType != 0 && IID valid`; `SetAttachedEntity` returns on
  PerceivedType 0; `SetupForNewEntity` returns early unless it has entity + type (and, for Simple, vital + display
  type): **no `Turbine.Floaty.CreateFloatyDesc`, nothing drawn**, and nothing retries.
- `VitalDisplayTypeList` (C): 1 Expanded (dividers), 2 SimpleElite, 3 Simple, 4 Champion, 5 ExpandedElite (dividers +
  "boss" rank star), 6 ExpandedLargeElite, 7 ExpandedLarge, 8 SimpleLargeElite, 9 SimpleLarge; 0 Invalid.
  `PerceivedTypeList` (C): 8 Character, 0x10 Turret, **0x100 Creature**, 0x10000 Minion, 0x80000 CapturePoint /
  CannotBeCombatTargeted, `CreateGameComponents` 0x7F59FB, `FogOfWar_MustFadeOut` 0x130128.

### 2.4 Data (C)

| Template (pack `0xA00002E7`) | `0x10000831` | `0x1000019D` | others |
|---|---|---|---|
| `0x49000CA0` Tripod | **1** Expanded | `0x100` Creature | `0x10000AA7` 1, `0x100001C3` 30, `0x1000034C` 30, `0x100006F1` 6, `0x1000055A` 1, `0x6B4` 0.35; `0x1000009C`, `0x10000029`, `0x10000249` without value |
| `0x49000CA1` Heavy Tripod | **5** ExpandedElite | `0x100` | `0x10000C56` 4, `0x6B4` 0.7 |
| `0x49000BF8` CA minion (cmp.) | 3 Simple | `0x10000` | `0x10000CF0` 1 |

The client merges this template at creation (C: `0x54F1F0` -> `0x478880` builds `0x49000000 + (class & 0xFFFFFF)`
from DB type 0x29; the minions' purple and the cannon's star in our recording prove template ids reach it). The
original's heavy bar has the star and dividers, the small ones dividers (frames 47 / 305 s / 593.8 s): exactly 5 and 1
(C). units-and-ai.md 1.2 read `0x10000831` as a "size / threat class": it is the VitalDisplayType.

### 2.5 Why no bar (P) and what is open (O)

- fase3-ie: `_spawn_camp` sets `hold_flags` (match.py:1460) for the 3.0 s phase, so `0x1000019D` reaches the unit
  component 3.1 s after the bundle (log: camps spawned 14:42:16.357, "phasing complete" 14:42:19.526,
  test-2026-10-28-1439-sweep.md 2). A camp in view while phasing (the east one spawned 5 s after frame 43, GL at the
  east mouth) is pushed with PerceivedType 0 and never gets a bar (P).
- Before fase3-ie the flags came 0.8 s after the bundle (jungle-camps-spawn.md 0: `0x1000019D = 0x100` at +0.76 s) and
  frame 24 (2026-10-26) shows no bar either, while our minions (same 0.8 s path) do have bars. So a second gate exists
  (O): the status-tag check with team 3 (`0x973730` looks the entity's team up through `0x854050`), or the camp's push
  coming before 0.8 s. Both are answered by `python tools\diag.py --campamentos` (section 6).
- The original (C, video 589.8-594.4 s, east respawn): the wireframe phase-in starts at ~590.4 s, **no bars while
  phasing** (593.5 s), all four bars at 593.6-593.8 s (phase ~3.2 s), i.e. the original released a gate at "phasing
  complete". `0x10000B2D` fits that gate (P): the bar manager watches it (`0xA3A840`), the bar push skips tagged
  objects (`0x16016AC`), the attack validator's target check and "may act" `0x9CFAF0` reject it (`0x15FE67C`), the
  selection drops a target when it is set (`0xA33C90`), and ics already sets it as a property (knockdown, fase3-gl).

## 3. Positions (P) and the centre (C)

### 3.1 Method: the client's own camera

- The encounter's camera record (deep-scan-maps.md 1 row 10): `0x4800114E` -> `0x10000258` = **`0x2100001E`** (pack
  `0xA00000B3` +0x1797A6C); its words at +0x94..+0xA8 = **10.0, 17.0, 45.0, -57.0, 0.0, 17.0** (P: min / max distance,
  vertical FOV, pitch, yaw, distance); Tutorial 1's `0x48000690` -> `0x2100000A` has yaw **45** there (the diagonal
  view of pvp-camera-yaw.md) and `0x10000077 = -45` (C words).
- Model: camera = T + d (0, -cos 57, sin 57), f = (H / 2) / tan 22.5. Per frame T (and d) fitted on landmarks of known
  height: the brick pillar caps of the west mouth (statics `0x820113BB`: `0x2E0012F5` (53.30, 83.66) / (53.36, 85.65),
  `0x2E001324` (59.53, 83.66), `0x2E0012F7` (62.39, 83.67); cap 2.194 m) and the east chain-link post tops (2.0 m:
  (94.81, 90.57), (96.65, 89.79), (98.49, 89.01), (101.28, 87.83), (104.06, 86.65); stealth-alignment.md 3).
- Fits: rms 0.95-3 px; d = 17.5-17.7 m in all four frames (data 17); with the pitch free it converges to 57.6-58.4
  (data 57) in the two frames whose landmarks spread in depth (305 s, 440 s); 304 s (three caps on one line) leaves it
  loose. The stealth area fitted the same camera independently (reverse-engineering.md, stealth fields: pitch
  57.5-58.7, FOV 46, 14.4-14.7 m high = 17.3-17.5 m along the view). Checks not used in the fits: the cart lamp at screen (520, 178) of 305 s -> (52.05, 93.41), static cart
  `0x2E001219` at (52.28, 93.18); the stealth tile's "+" -> (51.75, 85.21) (our tile x 51.7); our frame 24 (two caps)
  puts our heavy Tripod 0.7 m from its server position (48.75, 93.0). Error budget: +-0.3 m (foot picks +-10 px).

### 3.2 The original's camps (Clash 2v2 video; frames sampled in the scratchpad)

| Camp / unit | video 304.0 s (02:26) | 305.0 s (02:27) | mean |
|---|---|---|---|
| west heavy `0x40000CA1` | (48.85, 91.82) | (48.79, 91.91) | **(48.82, 91.87)** |
| west Tripod E | (51.06, 91.82) | (51.02, 92.00) | **(51.04, 91.91)** |
| west Tripod SW | (47.08, 90.28) | (47.31, 90.38) | **(47.20, 90.33)** |
| west Tripod SSE | (49.57, 90.22) | (49.63, 90.25) | **(49.60, 90.24)** |

| Camp / unit | 440.0 s (04:42, idle) | 593.5 s (07:15, phasing in at spawn) | mean |
|---|---|---|---|
| east heavy | (110.61, 91.87) | (110.55, 91.79) | **(110.58, 91.83)** |
| east Tripod W | (108.48, 91.85) | (108.51, 91.79) | **(108.50, 91.82)** |
| east Tripod SSW | (109.97, 90.12) | (109.92, 90.17) | **(109.95, 90.15)** |
| east Tripod SE | (out of frame) | (112.20, 90.31) | **(112.20, 90.31)** |

- Composition (C, frames 47 / 593.8 s): four bars per camp, one with the elite star = 1 Heavy Tripod + **3** Tripods
  (crime-alley-jungle.md read two small ones from the earlier frames).
- The layout is not a ring: Tripods at 1.8-2.2 m from the heavy, to the E, SW and SSE (west) and W, SE, SSW (east).
  The east camp is the west's mirror moved 0.45-0.6 m west (both east frames agree within 0.1 m); the exact mirror of
  the west SW Tripod (112.80, 90.33) is off the champion navmesh (nearest walkable (112.43, 90.23)); every measured
  slot is walkable (navgrid of `0x40000C82`, z 200.08). The east passage is narrower than a mirror
  (stealth-alignment.md 0: faces at 107.075 vs 107.275).
- Today (`maps.py` + `_spawn_camp` ring r 2 m): west heavy (48.75, 93.0) is 1.1 m north of the original's, one Tripod
  (47.75, 94.73) stands 3 m north of the original heavy, in the planter behind the sidewalk; east heavy (111.25, 93.0)
  is 1.2 m north and 0.7 m east of the original's. Overlays of
  both sets on frames 305 s / 440 s: scratchpad `camps/ov305.png`, `camps/ov440.png`.
- Facing (P): the line through the heavy's two front feet runs at +21..+26 deg (world) in the west frames and -19..-21
  deg in the east ones (a mirror image); our heavy at yaw 180 (frame 24) shows +27.5 deg. With yaw counter-clockwise
  (the tester's 180 -> 90 = clockwise turn), the west is ~yaw 176 (keep 180) and the east ~yaw 133-136 (**135**).
  The Tripod is near three-fold symmetric, so this is barely visible (G for the head's direction).

### 3.3 No centre camp (C frame, C code)

- Video 205 s (match 00:47, "Jungle Creatures: Phasing Complete"): the camera on the nook shows the round pad
  `0x2E00101D` with its yellow padlock and no creature (Clash). crime-alley-jungle.md 2 read a middle diamond on the v
  AI video's minimap (O: what that diamond was); the tester's instruction decides.
- `Bosses._spawn_raider` (bosses.py:141-145) waits only for a camp with `"middle": True`; `Match._on_killed`
  (match.py:1019) likewise. With no such camp the Raider spawns at `match_raider.crime_alley.at` (300 s) on the pad,
  `unlock_nook` runs and line 698 plays (also ends test-2026-10-28-1439-sweep.md S10, warnings without a Raider).

## 4. Other findings

- The phase-in length of the original: ~3.2 s (video 590.4 -> 593.6-593.8 s, C frames); `match_camp_phase_seconds` 3.0
  is right.
- Our camps send no minimap category (`Units._properties` skips `0x100004DA` for role "camp", and the templates have
  none); the original's minimap diamonds appear at "Phasing Complete" (crime-alley-jungle.md 2) (O, not done here).
- Cross-area (stealth): the original's vertical west tile's "+" lies at (51.75, 85.2) in two frames (P), the y the
  first video survey gave (85.5), not the 84.0 kept "as it was" (stealth-alignment.md 8 O2).

## 5. Implementation plan (fase3-if)

Every new key goes in `ics/config.py` `[ics]` with the comment `# 2026-10-28 15:00 (tester report: ...;
camps-colour-bar-positions.md N)`. Server team stays 3 (`match_neutral_team`); only what the client sees changes.

1. **Wire team 0 for camps** (C):
   - `ics/match/units.py` `Units.spawn`, after line 109 (`ent.side = ...`):
     ```python
     wire = self.ic.get("match_camp_wire_team")
     if role == "camp" and wire is not None:
         # 2026-10-28 15:00 (tester report: the jungle drones are grey, the original's yellow; camps-colour-bar-positions.md
         # 1, C): the client tints teams 0..2 only (0xA7B0D0), team 3 gives colour 0 = TeamColor Null. Team 0 = neutral:
         # colour 6 -> 0x1000011F -> material 0x16000E7B (yellow) and the bar's neutral tint 0xCCCC33. Server keeps team 3.
         ent.wire_team = int(wire)
         ent.side = int(self.ic.get("match_camp_side", 6))       # 0x100007A2 = the colour the client computes for team 0
     ```
   - `ics/world.py` `World.properties` line 276: `wire = getattr(ent, "wire_team", None)` and
     `props = M.creature_properties(ent.team if wire is None else wire, ent.alive)`.
   - `ics/match/units.py` `Units._properties`, after the structures' `team_as_change` block (line ~300): for
     `mu.role == "camp"` with a `wire_team` and `[ics] match_camp_team_as_change`, `self.m.later(unit_flags_delay +
     0.1, lambda e=ent: self.late_wire_team(e))`; new `late_wire_team(ent)`: 0x6 `0x1000009C = ent.team` (3), then 0x6
     `0x1000009C = ent.wire_team` (0) (a change, so `0xA813F0` -> `0xA7B0D0` runs with team 0 whatever the creation
     notify did; every later bundle carries 0 and side 6, so no diff undoes it).
   - Keys: `"match_camp_wire_team": 0` (None = fase3-ie: the server team 3), `"match_camp_side": 6`,
     `"match_camp_team_as_change": True`.
2. **Bar: release the phase with a tag, not by holding the unit flags** (P; the diag confirms):
   - `ics/match/units.py` `Units.spawn`, before `self._properties(mu)` (line 150): if `role == "camp"`, the tag key is
     set and `self.m._camp_phase(cls) > 0`, append `(int(tag, 0), KIND_BOOL, 1)` to `ent.extra_props` (so the creation
     bundle carries `0x10000B2D = true`: untargetable, unselectable, no bar push while phasing).
   - `ics/match/match.py` `_spawn_camp` line 1459: `mu.ent.hold_flags = True` only when
     `match_camp_phase_untargetable` is true; its default becomes **False** (`0x1000019D` then reaches the unit
     component at the usual 0.8-1.0 s, long before the phase ends).
   - `_camp_phase_end` (line 1499), before the phase-end bundle: 0x6 `0x10000B2D = false` and replace it in
     `ent.extra_props` (the bundle 0.1 s later carries false; a bundle omitting it would remove it anyway).
   - Keys: `"match_camp_phase_tag": "0x10000B2D"` ("" = none), `"match_camp_phase_untargetable": False` (was True:
     the fase3-ie hold of the targeting flags, the switch-back).
   - If the diag shows the push still made with PerceivedType 0 (push before the flags), add
     `"match_camp_flags_delay"` (camps' `unit_flags_delay`, try 0.3) and keep the tag until the flags are sent.
3. **Positions and composition** (P):
   - `ics/match/maps.py` `_crime_alley()` "camps" (line 79): replace the three camps (keep the history comments) with
     ```python
     # 2026-10-28 15:00 (tester report: no camp in the centre; the side camps stand on the upper sidewalk by each
     # jungle mouth; camps-colour-bar-positions.md 3, P +-0.3 m: the original video georeferenced with the client
     # camera 0x2100001E): 1 Heavy Tripod + 3 Tripods per camp on the original's slots (first = the heavy); the east
     # camp is the original's own (the west's mirror 0.5 m further west: the east passage is narrower)
     "camps": [{"pos": (48.82, 91.87), "yaw": 180.0, "kind": "small",
                "units": [0x40000CA1, 0x40000CA0, 0x40000CA0, 0x40000CA0],
                "slots": [(48.82, 91.87), (51.04, 91.91), (47.20, 90.33), (49.60, 90.24)]},
               {"pos": (110.58, 91.83), "yaw": 135.0, "kind": "small",
                "units": [0x40000CA1, 0x40000CA0, 0x40000CA0, 0x40000CA0],
                "slots": [(110.58, 91.83), (108.50, 91.82), (112.20, 90.31), (109.95, 90.15)]}],
     ```
   - `ics/match/match.py` `_spawn_camp` (line 1442 loop): when `camp.spec.get("slots")` and `[ics] match_camp_slots`,
     unit i stands at `slots[i % len(slots)]` moved by `pos - slots[0]` (so `match_camp_overrides` "pos" still moves
     the whole camp); else today's ring. Key `"match_camp_slots": True` (False = the fase3-ie ring of 2 m).
   - Exact mirror instead (the tester's first wording): `match_camp_overrides = {"1": {"pos": [111.18, 91.87],
     "yaw": 180.0}}` plus slots mirrored (x -> 160 - x); its SE slot is snapped 0.38 m onto the navmesh.
4. **No centre camp** (C): the "middle" camp goes with item 3. Nothing else changes: the Raider spawns at 300 s, the
   nook relay pad keeps its lock until then, the timeline's jungle mark stays (two camps), the meteor storm uses the
   two camps' positions.
5. **Records** (CLAUDE.md rule 3, done in this step for the findings): `catalog/data/properties.tsv` (`0x10000831`,
   `0x10000B92`, `0x10000B93`, `0x100007A2`, `0x1000009C`), `catalog/data/records.tsv` (`0x19000A61`, `0x16000E7B`,
   `0x2100001E`), `catalog/data/world_objects.tsv` (`0x40000CA0` / `CA1`), `docs/reverse-engineering.md`,
   `docs/CHANGELOG.md` fase3-if. The implementer updates the world_objects rows' "used_in" when maps.py changes.

### Tests to add / change (`tests/test_match.py`, no ports)

In the "bosses" block (line 584 on), which today takes the middle camp:
1. Replace `middle = next(...)` / "CA: the middle camp stands on the Raider pad" with: "CA: no camp in the centre
   (tester 2026-10-28 15:00)": `len(m.camps) == 2 and not any(c.spec.get("middle") for c in m.camps) and
   min(abs(c.spec["pos"][0] - 80.0) for c in m.camps) > 25`.
2. "CA: each camp = 1 Heavy Tripod + 3 Tripods on the original's slots": for both camps, `[mu.cls for mu in
   c.members] == [0x40000CA1, 0x40000CA0, 0x40000CA0, 0x40000CA0]` and every member within 0.05 m of its slot.
3. "CA: the east camp is the west's mirror within 0.8 m" (slot by slot, x -> 160 - x).
4. "camps: the client sees team 0 / colour 6, the server keeps team 3": for a camp unit `e`,
   `(0x1000009C, KIND_INT, 0) in w.properties(e)` and `(0x100007A2, KIND_ENUM, 6) in w.properties(e)` and
   `e.match_unit.team == 3`; a minion still sends its own team.
5. "camps: PVP_Team goes as a change (3 then 0) after creation": the labels `"<camp> team 3 (0x6)"` before
   `"<camp> team 0 (0x6)"`.
6. "camps: `0x1000019D` is sent while phasing, `0x10000B2D` is true in the creation bundle and cleared at phasing
   complete": label order flags < "0x10000b2d = false" < "phasing complete (bundle)"; the old "no targeting flags while
   phasing" check (line 610) flips to "unit flags while phasing".
7. "CA: the Raider spawns at 300 s with no camp to clear": drop the loop that kills the middle camp (line 620) and
   keep "CA: the Raider spawns on schedule".
8. "camps: phasing units ...": `len(cm) == 4` (was 3).
Run `python tests\test_match.py`, `python tests\test_ics.py` (ICS_TEST_PORT) and `python tests\test_session_flow.py`
(SESSION_TEST_PORT).

## 6. Runtime check for the tester

`python tools\diag.py --campamentos` (alias of `--camps`, added in this step) in a second console during a Crime Alley
v AI match; walk to a camp before it phases in (0:42) and stay a few seconds; send `logs\diag.log` and
`logs\server.log`. Lines:
- `CAMPS team colour`: per object `team`, `local_team`, `relation`, `colour` (expect 6 for camp IIDs after the fix;
  today 0 or no line at all).
- `CAMPS bar register: VitalDisplayType` (expect 1 / 5 for camp IIDs) and `bar register: accepted` (low byte 1).
- `CAMPS bar push to Flash`: `add`, `perceived` (0 = no bar ever; expect 0x100), `display` (1 / 5).
- `CAMPS bar fade`: fades of the camps' bars.
Breakpoints (RVA): `0x67B171`, `0x60F012`, `0x63A925`, `0x650D31`, `0x4BED90` (same bytes in the patched exe).

## 7. Open

1. O: the second bar gate before fase3-ie (section 2.5): the diag answers it.
2. O: whether the creation bundle's team already notifies `0xA813F0` (sweep-property-listeners.md says notify = 1
   fires at registration); item 1's change makes it irrelevant. P: the unit component's watcher runs before the HUD's
   (registered earlier), so `0xA7B0D0` reads the new team; the diag's `team` field shows it.
3. O: the v AI original's centre (crime-alley-jungle.md 2 middle diamond); the tester's call stands.
4. O: the camps' minimap diamonds (no `0x100004DA` sent).
5. O: skills whose relation mask `0x10000448` excludes neutral (1) will refuse camps once they are team 0 on the
   client, as in the original (P); the basic attack's default mask 3 accepts them.
6. P: the facing values (180 / 135); G for the head's direction.

## 8. Skeptic review (2026-10-29, independent re-check)

**Verdict: partly confirmed. Colour, centre camp, positions and composition hold. The overhead-bar cause and fix
(section 2.5, plan item 2) are wrong: the bar's push gate is the FloatyVitals attribute `0x1000072C`, which no camp
has ever had. Go-ahead: yes, with 8.3 instead of plan item 2.**

### 8.1 Re-checked and confirmed
- `0xA7B0D0` (capstone): `cmp edi, 2 / ja 0xA7B171` at `0xA7B143`, relation at `[ebp-8]`, colour at `[ebp-4]`.
  `0x853380`, `0x8533C0`, `0x853450` and `0xA95AB0` decompile as section 1.1 says: team 0 gives colour 6 in both
  modes, and team 3 or -1 gives 0. Flash `TeamUtils`: observed team 0 gives 13421619 (0xCCCC33), -1 gives 0xCCCCCC
  and an enemy gives 0xCC0000 (the red selection bar in frame 46). C.
- Flash: `FloatyVitalsManager.UpdateFloatyVitals` ignores a second "add" for an IID whose clip is still in use. Only
  a "remove" frees it, so a bar pushed with PerceivedType 0 stays blank until the C++ side removes it. C.
- Navmesh (`pvp.navgrid(0x40000C82)`): all eight proposed slots are walkable. The exact mirror's SE slot
  (112.80, 90.33) is not (nearest walkable (112.43, 90.22), 0.39 m). Today's ring puts one Tripod per camp off the mesh
  (snapped 1.3-1.6 m). Overlays `ov305` / `ov440` land on the original drones. map-audit-all.md's independent
  estimate, (46-51, 89.5-92.5), agrees. `0x2E001118`, the source of today's (48.75, 93.0), is an ambient emitter
  (crime-alley-props.md, crime-alley-missing-elements.md), not a camp anchor. Frame 47 shows four bars, one of them
  starred, so 1 + 3 is right. P as stated.
- Only `Bosses._spawn_raider` and `Match._on_killed` read `"middle"`, so with no middle camp the Raider spawns at
  300 s. C.

### 8.2 Refuted or corrected
1. **The push gate (C, disassembly).** `0xA50A70` checks `0x974940(ent, &ownIID, 0x16016AC, 1)` at
   `0xA50C3B-0xA50C5E`. `0x16016AC` is one tag (`0x96F4F0` reads a single dword): **`0x1000072C`**, default 1.
   `jne` / `mov [ebp-1], al` clears "visible" when the tag is false. `0x10000B2D` (`0x16016B0`) is not read there.
   Only the bar manager's listener `0xA1DC10` uses it, to queue fades on a change of LifeState or `0x10000B2D` (it is
   registered with notify 0). So "tags {`0x1000072C`, `0x10000B2D`} must not be set" is wrong, and a `0x10000B2D` tag
   in the creation bundle neither delays the push nor hides a bar.
2. **`0x1000072C` is FloatyVitals (C, script data).** Its modifier handles are named VitalBarHandle (`0x34000248`),
   FloatyVitalHandle (`0x340003D1`), FloatyVitalsHandle (`0x3400074B`), HideVitalsHandle (`0x340005B6`) and
   Att_FloatyVitals_Handle (`0x340005D8`). `0x340005D8`, a champion object that phases in, sets `0x1000072C`,
   Targetable `0x10000029` and Attackable `0x10000249` together when it leaves its phase (`$PhasingComplete`).
3. **The persistent blocker (C data, P effect).** Every jungle creature template declares `0x1000072C`, `0x10000029`,
   `0x10000249` and `0x1000009C` with no value (`key | 0x5000xxxx`, the values the original server filled in):
   - CA: `0x49000CA0`, `CA1`, `CA2`.
   - GD: `0x49000939`, `93A`, `93B`, `93E`.
   - CC: `0x490007C1`, `894`, `898`, `D60`, `430`.
   - The tutorial drone `0x49000C72` declares the first three the same way.

   The lane minions (`0x49000BF8`, `BF9`, `BFA`), the generic drone `0x49000A5C` and the CA structures (`0x49000C87`
   to `C8F`) carry `0x1000072C = 1`. A tag declared with no value evaluates **false** in `0x973730`. fase3-gf showed
   this at runtime: the tutorial drone failed check B on `0x10000029` until ics sent it as 1. The descriptor is the
   same (bool 0x16, container 4, net 1, group 0x3F). ics sends `0x10000029` and `0x10000249` (`unit_targetable_tags`)
   but never `0x1000072C`. So no camp has ever been pushed a bar (2026-10-26 frame 24; frames 44-46, minutes after the
   phase), while the minions have bars. This replaces both the fase3-ie-hold cause and the open "second gate" (2.5).
4. **The push is re-armed (C, `0xA50C93-0xA50CBF`).** If an added entry (state 1) loses visibility or FloatyVitals,
   it is pushed as a remove and goes back to pending. When it shows again it is pushed with the PerceivedType it has
   then. So "never pushed again until it is removed" is wrong. The hold theory predicts a bar on a camp seen again
   after a fog hide (`0x90F`). The west camp spawned while GL was at the east mouth, so it started hidden, yet frame 44
   (02:00) shows no bar there. P.
5. **Plan item 2 would break the Raider (C code).** `Bosses.spawn_boss` spawns with role "camp" (bosses.py:74), and
   `_camp_phase(0x40000CA2)` = 3.0 because its tables hold `Vfx_Spawn_Alt01 0x10000347`. The creation tag would
   therefore be set on the Raider, but only `_spawn_camp` schedules `_camp_phase_end`. `0x10000B2D` would stay true
   (the order lock and the validator's alive check), and the client could never attack the Raider.
6. **Keep the fase3-ie hold.** With `match_camp_phase_untargetable` = false, camps become targetable and attackable
   0.8 s into the phase, unlike the original (jungle-camps-spawn.md 2), and the bar is still not fixed.
7. **The minion cross-check (1.2, C) is only P.** Minions never get a team change, and `[comp+0x4C]` is the same
   watched-field helper (vtable `0x15F97F0`, registered by `0x977490` with notify 1) as the PerceivedType (`+0xA4`)
   and vision (`+0x8C`) caches, which the runtime showed miss their creation values (fase3-gd,
   fog-vision-runtime.md). For the same reason the 3 -> 0 change is **necessary**, not optional: keep
   `match_camp_team_as_change` on by default.
8. **Listener order (7.2) is P strong.** Watchers are appended (`0x573460` -> `0x508D80`) and notified from index 0
   upward (`0x509220`). The unit component registers when it attaches (`0x977490`), before the HUD's entity-added
   `0xA5A7E0`, so `0xA7B0D0` reads the new team.
9. **`0x100007A2` from bundles is applied (P strong, not "uncertain").** It is net 0, like `0x90F`, and `0x90F`
   delivered in bundles does hide units. So side 6 is needed.

### 8.3 Corrected plan (replaces item 2 of section 5; items 1, 3, 4 and 5 stand)
- **Bar.** Add a new key `[ics] match_camp_vitals_tags = ["0x1000072C"]` ([] = fase3-ie). Every role-"camp" unit,
  bosses included, gets bool `0x1000072C = 1` by 0x6 **after** its `0x1000019D`, through the same hold and release
  as `0x10000029` / `0x10000249`:
  - `World._late_flags` / `pending_flags`: at `unit_flags_delay` for bosses, and at `_camp_phase_end` (after the
    flags) for phasing camps.
  - Keep it in `extra_props`: a bundle that omits it removes it (object-update-bundles.md 0.3).
  - Never put it in the creation bundle: the first push would carry PerceivedType 0, and Flash keeps that blank clip.

  Keep `match_camp_phase_untargetable` = true. Drop `match_camp_phase_tag` and the `0x10000B2D` edits. This also
  matches the original: no bar while phasing, bars at "Phasing Complete".
- **Colour.** Plan item 1 as written. It also covers bosses (their templates declare `0x1000009C`); test the Raider's
  tint. Optional: `World.floaty_key` uses the wire team, since the 0x42 key is `(team & 7) << 4`.
- **Tests.** Replace plan test 6 with three checks:
  - Each camp unit gets `0x1000072C = 1` after `0x1000019D`, and after "stop Vfx_Spawn_Alt01".
  - The value is in `extra_props` and not in the creation bundle.
  - The Raider gets `0x1000072C` and never `0x10000B2D`.

  Keep "no targeting flags while phasing".
- **Diag.** Add a breakpoint at RVA `0x650C59` (`0xA50C59`: `al` = the FloatyVitals verdict, `esi` = the entity; the
  bytes are the same in the patched exe) to `--camps`. Today it should show `al = 0` for camp IIDs and no `0x650D31`
  line.
- **Stale anchors.** The plan's line numbers are out of date. Today: `_spawn_camp` hold at match.py:1489,
  `_camp_phase_end` at 1529, the "middle" respawn check at 1049, `match_camp_phase_untargetable` at config.py:932,
  the camp block at tests/test_match.py:723-760. Anchor on the text.
- **Accepted side effects.**
  - The meteor storm's impact sites now alternate west and east (objectives.py:394 cycles the map's camps).
  - Skills with an explicit relation mask 6 (enemy or ally; 5 entries in the packs, and none has mask 2) refuse
    neutral camps, as in the original.
- **Open.** The tutorial drones (`0x49000C72`) have no overhead bar for the same reason. Not this area.

## 9. Implemented (fase3-if, 2026-10-29)

Section 5 items 1, 3, 4 and 5 with 8.3 instead of item 2. Re-checked before coding (C): the bytes at `0xA50C39-0xA50C60`
(`push 1 / push 0x16016AC / ... / call 0x974940 / test al, al / jne / mov [ebp-1], al`; dword `0x16016AC` =
`0x1000072C`, `0x16016B0` = `0x10000B2D`; same bytes in `InfiniteCrisis_patched.exe`); the decompiled `0xA50A70`
(`if (FUN_00974940(ent, &iid, &DAT_016016ac, 1) == 0) visible = 0`); the templates: `0x49000CA0` / `CA1` / `CA2` declare
`0x1000072C`, `0x10000029`, `0x10000249`, `0x1000009C`, `0x10000B2D` with no value, `0x49000BF8` / `0x49000A5C` carry
`0x1000072C = 1`, and so do all 54 champion templates, the CA structures `0x40000C87..C8F`, relay `0x4000089D`, the
vehicles `0x4000045D` / `0x4000081B` and pad `0x40000C49`; every proposed slot is walkable on `pvp.navgrid(0x40000C82)`,
the exact mirror's (112.80, 90.33) is not (nearest (112.425, 90.225)).

| Item | Code | Key (default; switch-back) |
|---|---|---|
| Wire team 0 for every role-"camp" unit (bosses too), colour index 6 in every bundle | `Units.spawn` (`ent.wire_team`, `ent.side`), `World.properties`, `World.floaty_key` | `match_camp_wire_team` (0; None), `match_camp_side` (6; 0) |
| The team as a change: 3, then 0, by 0x6 at `unit_flags_delay + 0.1` s | `Units._properties` -> `Units.late_wire_team` | `match_camp_team_as_change` (true; false) |
| FloatyVitals `0x1000072C = 1` by 0x6 at `unit_flags_delay + 0.25` s, held while phasing and released in `_camp_phase_end` after the flags; kept in `extra_props`; never in a creation bundle | `Units.late_vitals`, `Match._camp_phase_end` (`pending_vitals`) | `match_camp_vitals_tags` (["0x1000072C"]; []) |
| Two camps with the original's slots, 1 Heavy Tripod + 3 Tripods, west yaw 180, east 135 | `maps.py` "camps" / "slots", `Match._spawn_camp` | `match_camp_slots` (true; false = the 2 m ring); `match_camp_overrides` per camp |
| No centre camp (the Raider at 300 s) | `maps.py` "camps_centre", camp list in `Match` start | `match_camp_centre` (false; true = fase3-ie's middle camp, first) |
| Diag | `tools/diag.py --camps`: `0x650C60` (bar held back: FloatyVitals false) | |

- `match_camp_phase_untargetable` stays true; no `0x10000B2D` edit (8.2.5). The diag breakpoint is `0xA50C60`, not
  `0xA50C59`: the instruction after the call runs for every bar entry every frame (champions, minions, structures); the
  `mov [ebp-1], al` runs only for a false verdict, i.e. in a CA match only for camp units while they phase in and the
  Raider in its first second.
- Correction to 8.3 "accepted side effects": Crime Alley has no meteor storm (maps.py "events" only on Gotham Divided
  and Coast City), so its impact sites do not change.
- Exact mirror instead of the original's east (the tester's first wording): `match_camp_overrides = {"1": {"pos":
  [111.18, 91.87], "yaw": 180.0, "slots": [[111.18, 91.87], [108.96, 91.91], [112.8, 90.33], [110.4, 90.24]]}}`.
- Tests (`tests/test_match.py`, "bosses" block): no centre camp; 1 + 3 per camp within 0.05 m of the slots; east =
  mirror within 0.8 m; team 0 / colour 6 / floaty key 0 on the wire and team 3 on the server (a minion keeps its team);
  the 3 -> 0 change after the creation bundle; per unit FloatyVitals after the phase-in stop and the unit flags; kept in
  `extra_props`, carried by the phase-end bundle, absent from every creation bundle; no FloatyVitals while phasing; the
  switch-backs (middle camp first, ring, team 3, no change, no FloatyVitals); the Raider at 300 s with team 0, colour 6
  and FloatyVitals after its flags, never `0x10000B2D`.
- Runtime check for the tester: `python tools\diag.py --campamentos` in a second console, walk to a camp before 0:42:
  expect `CAMPS team colour` with team 0 / colour 6 for the camp IIDs, `bar held back` lines for them only until
  "Phasing Complete", then one `bar push to Flash` each with `add` 1 and `perceived` 0x100 (display 1 / 5).
- Still open: the camps' minimap diamonds (no `0x100004DA`, 7.4); the facing's head direction (G); the tutorial drones'
  bar (`0x49000C72`, same cause, not this area).
