# Crime Alley jungle: camp positions, the Raider's locked pad, spawn effect (2026-10-25)

Tester report 2026-10-25 19:28 (Crime Alley v AI, encounter `0x40000C82`): the jungle camps stand in the wrong
places, the middle one has no floor, the padlocked base that waits for the Raider is missing. Extra frames from the
tester (original game, Crime Alley; Clash 2v2 and v AI) and the two local recordings were checked.

Tags: C = read in the data / clearly seen, P = probable, G = guessed (frames, minimap scale), O = open.

Sources: statics `0x820113BB` (Crime Alley), `0x820113C3` (Tutorial 2: the same lane, west half), `0x820123E3`
(Coast City) from the census pickle; layout / variants packs `0xA00002E5/E6/E7`; scriptlet tables; the original
v AI video (`crime_alley_map_video.mp4`, minimap at 00:44-00:51), the tester's 20 frames (2v2 + v AI) and our
recording `2026-10-25 19-28-07.mp4` (frames 61-109 s and 796-812 s walk the jungle). Frames were sampled into the
scratchpad only.

## 1. The Raider's locked base = world state `0x2E00101D` (C object, C position)

- Look (tester frames 13 / 14, 2v2 at 02:58): a large round steel pad (~10 m across) with a keyhole-shaped inner
  ring, yellow circuit lines and a yellow padlock hologram on its north rim, standing in the nook north of the lane
  centre, against the rubble. A lantern on it in one frame is a player's item.
- Our game (recording 99 s and 810 s): at that spot only the small superpad `0x40000CB5` (green "+" plate, ~2 m)
  that `[ics] match_nook_pad` spawns; the camp unit at (80, 99.7) stands on bare gravel behind it.
- Data: world state **`0x2E00101D`** (.entity `0x2D000D92`, ctype 3, one table `0x1D000385` = Vfx_TeamColor_SetNull /
  _CapturePoint_OnTeamBiasChanged / _Entity_OnSetClientRelationship / Vfx_TeamColor_SetContention; no `0x40` class
  names it). It is listed in the Crime Alley layout pack `0xA00002E6` (also `0xA0000162`, `0xA0000256`), so the
  client can draw it on this map. It is placed as a static (flags 158, `0x50F = 5`, `0x2A4 = 1`) at:
  - **Tutorial 2 (same lane art): (80.0, 97.66, 200.06) yaw 179** — the Crime Alley nook (C);
  - Coast City: (80.0, 8.55, 249.98) yaw 180 — the Raider camp spot (`0x40000D60` at (80, 9), map-manifests.md) (C);
  - Crime Alley 0x12BB: world (-7.2, 64.0) yaw 131, team 2, colour override `0x10000CF0 = 1` — a decoration behind
    the blue base, not at the nook (C).
  So the original server spawned `0x2E00101D` at the Crime Alley nook as the Raider's pad (P-strong: same lane, same
  object under the CC Raider). The navmesh confirms a round walkable island there: x 74.5-85.5 up to y ~100.7.
- The padlock: no table of this world state has Vfx_Locked / Vfx_Unlocked (those keys exist only in the Coast City
  Device table `0x1D0002FE`). The hologram is part of the pad model (P); what removes it when the Raider spawns is O
  (candidates: Vfx_TeamColor_SetContention vs SetNull, or the Raider standing on it). In the 2v2 video it stayed
  locked in all five matches (crime-alley-2v2-video.md 4).
- Superpad `0x40000CB5` is the wrong object for the nook (its plate is small; the "+" comes from Vfx_Active_Pad).

## 2. Camp positions (G minimap, P marker, C navmesh)

Original v AI minimap (00:45, 4x crop; x = 65 + (px4 - 287) / 4.2, 1.05 px/m both axes, lane dots at y 77.5):

| Camp | Minimap | Data | Recipe | Today |
|---|---|---|---|---|
| West | (48.6, 93.0) | type-3 marker `0x2E001118` at **(48.75, 93.00)** (C) | (48.75, 93.0) | (52, 90): 3.3 m east, 3 m south |
| Middle | (80.5, 98.5) | pad `0x2E00101D` (80.0, 97.66) | on the pad, (80.0, 97.66) | (80, 99.7): 2 m north, off the pad |
| East | (111.9, 93.0) | none; mirror of the west marker about x 80 | (111.25, 93.0) | (113, 90): not walkable (navmesh moves it to (112.4, 90.0)) |

- All three diamonds appear in the same frame at match clock 00:45 (C), as the timeline bar's green (jungle)
  marker reaches its tick. In the v AI video no padlock icon shows on the minimap before that (C); in the 2v2 Clash
  video the nook shows a padlock icon from the start and only two side camps exist (crime-alley-2v2-video.md 3-4).
  So v AI: 3 camps, the middle one on the pad; Clash: 2 camps + the locked pad (C frames).
- West camp walkable area: the marker sits 1 m inside the north edge of the walkable street (y ~94). All three
  recipe points are walkable (navgrid C).
- Facing: keep yaw 180 (south, toward the lane) as today; marker yaws are 0 (ignored, as on the other maps) (G).
- Composition (C frames 2v2, tester frame 16 v AI): one big golden spider robot + two small ones = Heavy Tripod
  `0x40000CA1` + 2 x Tripod `0x40000CA0` (as today).

## 3. Spawn / respawn effect (C colour, P key)

- Look (tester frame 11, 2v2 frames 10:57): the creature materialises as a sparkling yellow translucent wireframe.
- Data: the CA jungle classes (`0x40000CA0` / `CA1` / `CA2`) carry table **`0x1D000674`** (pack `0xA0000161`):
  Vfx_Spawn_Event01 `0x1000087C`, _Event02 `0x1000087B`, _Event03 `0x10000927`, _Event04 `0x10000926`, _Alt01
  `0x10000347`, _Alt02 `0x10000346`. In its entries **Vfx_Spawn_Event02** and **Vfx_Spawn_Alt01** apply the overlay
  mesh/material `0x17001445` with colour **0xFFF5EC04 (yellow)** and a fade (a 9.0 float and 100.0 nearby, P length /
  intensity); Event01 and Alt02 have no colour overlay (Alt02 / Alt01 also start particles `0x18000B6E` /
  `0x18000D90`). So the yellow phase-in is **Vfx_Spawn_Event02** (P-good; Alt01 the variant).
- Their base table `0x1D00042D` also has _Entity_OnEnterWorld_Default (sent today by `unit_spawn_scriptlets`).
- The CA Raider `0x40000CA2` has the same `0x1D000674` and no Vfx_Spawn_PhasingComplete (map-objectives-recipes.md 4).

## 4. Timing

| Match time | What | Tag |
|---|---|---|
| load | pad `0x2E00101D` at the nook with its padlock (v AI and Clash) | C object / P v AI look |
| 0:35 | jungle online line (`match_jungle_lines` -10 s = 669) | C (2v2 notice at 0:36) |
| **0:45** | the three camps phase in (Vfx_Spawn_Event02), minimap diamonds | C (both videos: 0:45 / 0:46) |
| cleared + 60-75 s | the camp phases in again with the same effect | P (2v2 M1: 7:30 -> 8:30, 9:45 -> 11:00) |
| 5:00 (G) | Raider `0x40000CA2` on the pad (80.0, 97.66) yaw 180, lines 696 / 699 / 698; drop `0x40000C49` (ws `0x2E00104E`) on death | G time, C classes |

`match_camps.first` is 60 s today; the videos say 45 s from "Match: Initiating" (C).

## 5. Server recipe

1. `[ics] match_nook_pad` (ics/config.py; `_spawn_nook` already spawns any class, `world.spawn` takes a `0x2E` world
   state as the class):
   `{"class": 0x2E00101D, "pos": [80.0, 97.66], "yaw": 180.0, "scriptlets": ["Vfx_TeamColor_SetNull"]}`
   (C object / position; P neutral colour key — the original's lines are yellow). Spawned at match start, kept all
   match; the old value (`0x40000CB5`, Vfx_Active_Pad) is the switch-back.
2. `maps.py` `_crime_alley["camps"]`:
   ```
   {"pos": (80.0, 97.66), "yaw": 180.0, "units": [0x40000CA1, 0x40000CA0, 0x40000CA0], "kind": "small", "loop": [...]},
   {"pos": (48.75, 93.0), "yaw": 180.0, "units": [0x40000CA1, 0x40000CA0, 0x40000CA0], "kind": "small"},
   {"pos": (111.25, 93.0), "yaw": 180.0, "units": [0x40000CA1, 0x40000CA0, 0x40000CA0], "kind": "small"},
   ```
   (or the same through `match_camp_overrides` {"0": {"pos": [80.0, 97.66]}, "1": {"pos": [48.75, 93.0]},
   "2": {"pos": [111.25, 93.0]}}). Keep the 2 m ring of small units around the big one; on the pad they all stand on
   the 10 m plate.
3. Camp spawn effect: a new key, e.g. `match_camp_spawn_scriptlets: ["Vfx_Spawn_Event02"]`, sent ~0.1 s after each
   camp unit's creation (first spawn and every respawn), instead of / after `unit_spawn_scriptlets` for role "camp";
   [] = today's behaviour. Alternative to try: "Vfx_Spawn_Alt01".
4. `match_camps.first` 45.0 (C videos); `respawn_small` 75 (P, unchanged). `match_jungle_lines` stay (-30 / -10 / 0
   around `first`).
5. Raider: `match_raider.crime_alley.pos` [80.0, 97.66] (pad centre). The middle camp and the Raider share the pad:
   G rule — from `at` (300 s) the middle camp stops respawning and the Raider takes the pad (if the camp is still
   alive at `at`, delay the Raider until it is cleared). In a Clash mode the middle camp is not spawned (2v2 video:
   two camps + locked pad).
6. Meteorite craters (tester's aside, not solved here): the red glowing rubble piles with an orb seen only in the
   original (crime-alley-video-compare.md: (80.1, 72.8), (54.7, 82.9), (105.0, 82.7); crime-alley-still-missing.md
   ~(84, 93.5)) are server-spawned (no static there, C); the pickable fragment class is `0x400006F1` (pack
   `0xA0000164`, `match_events.meteor_storm`). Which two piles the tester means and their class are O.

## 6. Open

- What hides the padlock hologram / marks the pad unlocked when the Raider appears (no Locked key on `0x2E00101D`).
- Whether the v AI Raider exists at all (the v AI video shows the middle camp diamond until its end, ~7:30 match).
- Exact durations of Vfx_Spawn_Event02 (table floats not decoded).
