# Crime Alley: fence strip from our structures' circles, the ring phantom's filter, minimap visibility, camp icons (2026-10-29, fase3-io)

Tester report 2026-10-29 21:10 (build fase3-in, Crime Alley v AI, AGL vs AI Catwoman, server run 21:03:56-21:10).
Evidence: `logs/server.log`, `logs/traffic.log`, `logs/diag.log` (21:04:11-21:10:53: `diag --fog --ring --throwpress
--destruction`, 45 breakpoints), screenshot `78.png` (the original's minimap), the decompiled client (`re-work/decomp`),
capstone reads of `InfiniteCrisis.exe` (image base 0x400000), the Flash HUD (`re-work/ui-as2`, MapNote.as,
TeamUtils.as) and the installed packs. Tags: **C** confirmed, **P** probable, **G** guessed, **O** open.
Builds on `ca-ring-fog-bundles.md`.

## 0. fase3-in's bundle fixes held (C traffic)

Every AGL bundle from 21:05:05 on (126 bundles of 1.4-1.7 KB) carries `0x1000019D = 0x200008` and `0x100008CE = true`.
The diag `occluder pass` line for AGL (source `0x...02`, radius 12) reads al 0 until 21:05:00 and **al 1** from then on.

## 1. The black strip by the fence: our structures' circles (item 1)

### 1.1 Who still runs the occluder pass (C diag)
`HOT fog: occluder pass` per source, 21:04:52-21:07:19 (the line is capped at 3000):

| Source | What | Radius | al (skip) |
|---|---|---|---|
| `0x...02` | AGL | 12 | 0 until 21:05:00, then 1 |
| `0x...111` | foundry t1 (template holds 0x100008CE = 1) | 14 | 1 always |
| `0x...101` | core t1 | 18 | **0 always** (430) |
| `0x...103` | core_turret t1 | 9.5 | **0 always** |
| `0x...105` | inner_turret mid t1 | 9.5 | **0 always** |
| `0x...10B` | turret mid t1 (65, 77.5) | 9.5 | **0 always** |
| `0x...144`-`0x...153` | allied minions (per-tick bundles carry it) | 5 | 1, 0 only for a moment |

`HOT fog: occluder body` names one body for every source: `0x01113BB0000000B8`, body type 8 = the map static #0xB8 of
landblock 0x13BB (a map static, top byte 1). The strip x 70-76, y 81.5-83 lies 6-12 m from the lane turret (65, 77.5),
inside its 9.5 m circle; one circle's black region is not cleared by another source's light, so AGL's skip alone did
not help (P strong, as 57.webp's wedge).

### 1.2 Why the structures' attribute did not take (C traffic, P mechanism)
The structures got `0x100008CE = true` by 0x6 (and the op-6 modifier) at 21:04:58.065-.073 and were never
re-bundled (only scriptlets, targets, vitals and 0x6 changes after their 21:04:46 creation bundles), yet the read
stayed false. Their templates (`0x49000C8B / C8C / C8A / C8F`) declare `0x100008CE` without a value (`ce080010
ce080050`), as the minion and champion templates do; the foundry's has the value (`ce080010 ce080010 01`). Why the 0x6
base value was not read on these objects is O; what is C is that a template-level value works (foundry) and that a
creation bundle's 0xBC is merged into the creation desc before construction (0x64CA10 -> 0x502B00,
`actor-creation-and-environment.md`), i.e. it lands where the template value does.

### 1.3 Fix
`[ics] vision_through_blockers_at_creation` (true): an allied structure's creation bundle carries `0x100008CE = true`
(`Units._properties`); the 0x6 and the modifier still follow. false = by 0x6 only (fase3-in).
If the strip stays: `python tools\diag.py --fog` again; the structures' lines must read al 1.

## 2. Turret warning ring: the phantom's filter refuses every ics unit (item 2)

### 2.1 Runtime (C diag)
Registration (0xA7CA20): the enemy structures `0x...102` (core, range 10), `0x...104` (core turret, 9), `0x...108`
(inner, 9), `0x...10E` (lane turret, 9) registered at 21:04:50. **Not one `HOT RING phantom` line** (rva 0x63A5F0, the
callback's entry) in six minutes with minions under every turret: the phantom never reported a body.

### 2.2 The filter (C, disassembly)
- 0xA2A710 builds the ring's phantom: a box of half size r + 5.5 at the turret, listener object vtable `0x1602318`
  (slot 9 `0xA5E270` enter / slot 10 `0xA5E2A0` leave -> 0xA3A5F0), filter object class **`0x15ECA98`** (ctor
  0x8528F0, size 0x78): team = `0x854050(turret)` at that moment, relation mask 2, PerceivedType mask 0x210000.
- Filter slot +0x28 = **0x852210**: `0x852110(body)` first, then `0x9D0180(ent, 0x210000)`, then the team relation
  (0x853380: -1 on either side = 2, so a turret whose team cache was still -1 accepts every unit).
- **0x852110**: entity of the body (0x5B1D00); then **`0x4DAF10(body IID)` = top byte 2 -> return 1 (refused)** at
  `0x852144 test al, al / 0x852146 jne 0x852128`; then 0x403 (bool, refused when true, if +0x58 bit 1 is clear) and the
  base filter 0x5BC020.
- Top byte 2 is a **player** object in this client: 0x8631A0 walks a unit's owner chain ([unit comp +0x68]) to the first
  top-byte-2 entity (the owning player); 0x854050 falls back to that player's team; 0xA16730 sets the vital-notices flag
  itself only for a champion whose IID is not top byte 2 (`skill-button-will.md`). So the original server's units had
  another top byte (O which; pool 3 for top byte 3 is the likely one, `full-entities-engine.md`). ics gives every
  object top byte 2 (`ENTITY_BASE_ID 0x0200000000000100`), so the filter refused every minion and champion.
- The same filter class is used by 0x9C24C0, 0x9CCE60 and 0xA93470 (client-side perception queries, O what for).

### 2.3 Fix (exe patch)
`icserver/patcher.py`: file offset `0x451544` `84 c0 75 e0 f6 46 58 01` -> `84 c0 90 90 f6 46 58 01` (the jne at va
0x852146 becomes two nops). Player objects have no physics body, so the filter only ever sees units. The user must run
`python ic.py patch`. `[game] exe_patch_skip = ["perception filter"]` keeps the original bytes (fase3-in).
Renumbering every ics object to another top byte would be the faithful fix (O: it touches the vital notices, the
player / champion links and every hard-coded id).
`tools\diag.py --ring` adds `HOT RING phantom built (al 1 = yes)` (rva 0x67CBF4) and `HOT RING filter: body IID top
byte 2` (rva 0x452144). Still O: the turret's team cache at entity add (-1 = the ring also counts its own minions).

## 3. Minimap: enemies only inside our vision, super minions always (item 3)

**Superseded (2026-10-30, `ca-fog-minimap-category.md` 1):** it did not work in game. 0x2A1 is client-local and the
client's evaluator 0xAAA670 rewrites it to true about every 0.4 s; the lever is now the note category 0x100004DA
(`[ics] fog_minimap_lever`).

- Map notes (C, 0xA4BD80 / 0xA5B190): a note is added only while `0x2A1` is true (plus category, alive), and the map
  manager's entity hook 0xA5B190 watches 0x2A1, 0x100004DA, LifeState, 0x10000B2D, 0x10000548. `0x90F` (what
  `World.fog` sent) hides only the model (0x61CB30), so every enemy minion and the bot stayed on our minimap.
- Super minions: `0x40000C9C` / `0x40000C9B` carry unit flags `0x8, 0x410000` (elite 0x400000), lane minions `0x10000`
  (C data). 78.png: the original's minimap shows no lane minion outside vision (C frame).
- Fix: `[ics] fog_hide_minimap` (true): an enemy (team 1 / 2) unit or champion out of sight also gets `0x2A1 = false` in
  its bundle (`World.fog`, `World._fog_off_minimap`); a unit with a bit of `[ics] fog_minimap_always_flags` (0x400000)
  in its unit flags (bundle or template) keeps 0x2A1 true (hidden model, minimap icon). Neutral camps unchanged. The
  bot's 0x2A1 comes from its extra_props once fog set it (no duplicate id).

## 4. Camp icons and the yellow circle at the centre (item 4)

- 78.png (zoomed): three small white diamonds above the lane at the west camp, the nook and the east camp; the big
  yellow ring with a portrait on the lane is the **local player's** note (`YouAreHereEffect`, MapNote.as) with the
  camera box, not an objective (C frame).
- Ours: the camps sent no `0x100004DA` (template none, `Units._properties` skipped camps): no camp icon. The nook pad
  `0x4000089D` template has `0x100004DA = 26` SMALL_CAPTURABLE, `0x100007D8 = 1` and no icon; Flash
  `UpdateForPerceivedType` draws the capture-point border's default art, tinted neutral yellow (0xCCCC33): the "big
  yellow circle and dot" at our minimap centre (C code + data; P that this is what the tester means).
- No camp-marker icon or class exists in the data (scan of every 0x49 template's 0x100004DA / 0x10000083, the marker
  world states 0x2E000944 / 945 / 1118 / 1117 / 1120): G for the original's diamond. The minion icon `0x13000141` is a
  4 x 4 px grey dot in a 32 x 32 ARGB texture (read from the pack, not kept).
- Fix: `[ics] match_camp_map_notes` `{"0x40000CA1": [9, "0x13000141"]}`: the camp's Heavy Tripod carries category 9 with
  the minion icon (one icon per camp, tinted by its wire team 0 = yellow; gone with the heavy); `[ics]
  match_nook_pad_map_note` false: the pad's bundle carries `0x100004DA = 0` (no note). O: the original's white diamond
  (Flash unknown tint 0xCCCCCC = team -1 / >= 3?) and whether v AI had a centre camp (the tester asked for none on
  2026-10-28; `match_camp_centre` stays false).

## 5. Tests
`tests/test_match.py` `fog_minimap_ring` (8 checks): allied structures' creation bundles carry 0x100008CE (not the
enemy's), off = as fase3-in; a far enemy minion and the bot are hidden with 0x2A1 = 0, a super minion hidden with 0x2A1 =
1, back in sight 0x2A1 = 1, fog_hide_minimap false = 0x90F only; the heavy's note and the pad's 0; the patch entry and
its bytes in the installed exe.

## 6. Tester should see (after `python ic.py patch`)
1. No black strip by the fence east of our lane turret.
2. The ring around an enemy turret (yellow / green with our minions, red when it shoots us). If not: `diag --ring`
   (`phantom built`, `filter` and `phantom: unit enters` lines).
3. Enemy minions and the enemy champion on the minimap only while one of ours sees them; super minions always.
4. One small icon per jungle camp while its heavy lives; no yellow circle at the centre.
