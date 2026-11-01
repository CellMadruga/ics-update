# Crime Alley structures: which structure stands where, and the extra tower (2026-10-28)

Tester reports (2026-10-28): (1) "the tower that has no floor / base around it is not the correct one that should
load there"; (2) "each side shows 3 towers, the original had only 2; the third one, closest to the core, belongs at
the second tower's spot (the socket at x 40 / 120) and the structure we put there should not exist".

Tags: **C** confirmed (data / code / frames read), **P** probable, **G** guess, **O** open. Builds on
`map-object-census.md` 1, `deep-scan-maps.md` 1.5 / 2.2-2.3, `crime-alley-video-compare.md`, `crime-alley-2v2-video.md` 3,
`crime-alley-still-missing.md` 2-6, `stubborn-visuals.md` 1.2, `maps-complete.md` 3.2. Scripts in the session
scratchpad (`castruct/`), nothing of the game copied.

## 1. Structure count per side in the original data (C)

Crime Alley's statics (LB `0x13BB`) carry exactly **three type-3 structure markers per side**, nothing else:

| Marker (t1 / t2) | Position t1 / t2, yaw | Role | Evidence |
|---|---|---|---|
| `0x2E0011A7` / `0x2E0011A6` | (17.5, 77.15) -90 / (142.5, 77.75) 90 | core | core pedestal statics; layout "PowerCore" `0x2E000AC5` at the same spots (C) |
| `0x2E0011A9` / `0x2E0011A8` | (40.0, 77.5) -90 / (120.0, 77.5) 90 | dampener (second structure) | section 2 |
| `0x2E0011AD` / `0x2E0011AC` | (65.0, 77.5) -90 / (95.0, 77.5) 90 | lane turret | layout `0xA00002E6` cinematic actors "BlueTurretBody" `0x2E000AA0` at (65.0, 77.5, 199.98) yaw -90 and "RedTurretBody" at (95.0, 77.5) yaw 90 = the markers to the centimetre; Tutorial 2 uses the same two DIDs for its friendly / enemy turrets (25.5 / 75) (C) |

- **No marker for a core turret.** The marker ids skip `0x2E0011AA` / `0x2E0011AB` (no static of any map pack uses
  them); G: a dropped pair (e.g. a core-turret site removed from this build).
- **The original minimap shows two structures per side plus the core** (C, two independent sources):
  2v2 Clash video (`crime-alley-2v2-video.md` 3): blue core, blue dot x ~42 (40), blue dot ~67 (65), red ~97 (95),
  red ~121 (120), red core; vs-AI video (`crime-alley-video-compare.md`, minimap calibration): **our** minimap has
  an extra blue icon at x ~24 (the core turret), "the original shows none apart from the core blob".
- ics (`ics/match/maps.py _crime_alley`) spawns **four** per side: core (17.5), **core_turret (25.5, conf G, no
  marker)**, dampener (40), turret (65). The core turret is the extra tower (C: no marker, absent from both original
  minimaps). Its 25.5 position was borrowed from Tutorial 2's friendly turret (marker `0x2E0011AD` sits at 25.5 in
  T2 because T2's map is only half a lane), not from Crime Alley data.

## 2. What stands at x 40 / 120 (P, strong)

- Original frames: vs-AI frame 82 s: grey segmented ring (~6 m), dark pedestal with red trim, stacked blue hologram;
  Clash 2:30: the same ring at x 40 (C frames). Clash has no core turret at all (C frames).
- The dampener class (`0x40000C88` / `C87` v AI, `0x40000C91` / `C95` Clash) = world state `0x2E000E04`, rig
  `env_pvp_dampener_a` (ring, body, six legs, `Ground` bone), and its table `0x1D00063A` spawns on **Vfx_Active** the
  child `0x2E000A9E` (scale 0.75 / 0.75 / 0.5) and on **Vfx_AI_Active** the hologram head `0x2E000AA8` (C tables,
  `stubborn-visuals.md` 1.2). Ring + pedestal + hologram on vs-AI = exactly the original picture; ring only on Clash =
  the Clash frame. So the x 40 structure is the dampener, as ics has it (P strong: no data names the class at the
  marker; visuals and tables agree).
- The core turret (v AI `0x40000C8F` ws `0x2E000AC4`, team 2 `0x40000C8D` ws `0x2E000AA0`) uses the **same graph
  `0x1C000069` as the lane turret** `0x2E000AA0`: it is a lane-turret body (and in ics gets the gear plate). Moving it to
  x 40 would put a turret, not the original ring, there (C graph, P look).
- Role mapping is **not swapped**: turret 65 / 95 is C (cinematic actors on the markers), dampener 40 / 120 is P.
- The vs-AI "core-turret hologram on the core's prow" (`crime-alley-still-missing.md` 4) is P the **core's own**
  Vfx_AI_Active child `0x2E000AC3` (table `0x1D00035E`, a turret-head-like object), not a separate structure: it
  belongs to the core and has no minimap icon (consistent with the original minimap).

So the tester's count is right (one tower too many per side) but the extra one is the core turret at 25.5, not the
x 40 structure. The x 40 dampener looks "wrong" because of the black socket around it (section 3), not because of its
class.

## 3. Socket at x 40 / 120: no structure fills it (C bboxes, P render models)

| World state | Use | Box (from `.entity`) | Fills 10 x 15 m? |
|---|---|---|---|
| `0x2E000E04` dampener | rig entity `0x2D000BAF` | rig within ~2 m of origin (deep-scan-maps 1.5) | no |
| `0x2E000AA0` lane turret / `0x2E000AC4` core turret | rig entities `0x2D0008B7` / `0x2D0008D4` | collision box 1.4 x 1.4 x 2.4 / 1.4 x 1.4 x 2.5 | no |
| `0x2E000A9F` gear plate | `0x2D0008B6` | 6.26 x 6.26 x 0.18 | no |
| `0x2E000A9E` dampener child | `0x2D0008B5` | zero box (particles / no mesh) | no |
| `0x2E0013EE` core | `0x2D00109C` | zero box header (rig) | no |
| `0x2E00119F` "structure socket" | `0x2D000EB2` | zero box, one bone | no |
| `0x2E0000E3` pit slab | `0x2D00007B` | 10 x 20 x 2 | yes (pale, untextured; tester 19:28) |
| `0x2E000A3B` core pedestal | `0x2D000864` | 21.2 x 19.8 x 0.4 | yes (textured round platform) |

- The core turret's model / base does **not** fill the socket (C box); neither does any Crime Alley structure (vai,
  clash, Tutorial 2). The only flat pieces large enough are `0x2E0000E3` and the core pedestal `0x2E000A3B`
  (`deep-scan-maps.md` 2.3, C list). The render-mesh link of rig entities was not resolved (O), but the original
  Clash frame shows the ring on cobbles, so whatever the original drew there was flat street, not a structure base.
- Tutorial 2 (same terrain socket at (40, 75) / (40, 80)) places only `0x2E00119F` there (team -1) and **no
  structure** (C statics): T2's structures are the turrets at 25.5 / 75 and the core; its lesson cinematics name
  nothing at 40.

## 4. Encounter data (C)

`0x40000C82` (v AI) and `0x40000E74` (Clash) templates name no structure class, placement table or slot list
(`deep-scan-maps.md` 1.8): tracker `0x100007F5 = [26]`, `0x100007FA = [1]` only. The layout pack `0xA00002E6` names
turrets (cinematics, 65 / 95) and cores, nothing at 25.5 or 40 on LB `0x13BB`. Class roles come from the class
families in `0xA00002E6` (vai team 1: `C8A` core, `C88` dampener, `C8C` turret 2500, `C8E` ws AA0 3500, `C8F` ws AC4
3500; team 2: `C89`, `C87`, `C8B` 2500, `C86` ws AA0 3000, `C8D` ws AA0 3000; Clash: `C96/C98` core, `C91/C95`
dampener, `C92/C93` turret, `C94/C97` ws AA0). The spare turret classes (`C8E/C8F`, `C86/C8D`, `C94/C97`) are P for
the other Crime Alley encounters (1vAI tutorial `0x40000CA6`, the "Defend Turret" challenges `0x40000D71` /
`0x40000E61`), not proof of a third tower in v AI.

## 5. Corrected per-side list (recipe)

| Role | Class t1 / t2 (vai) | Class t1 / t2 (clash) | Position t1 / t2 | Yaw t1 / t2 | Extras | Conf |
|---|---|---|---|---|---|---|
| core | `0x40000C8A` / `0x40000C89` | `0x40000C96` / `0x40000C98` | (17.5, 77.5) / (142.5, 77.5) | 90 / -90 (as today) | Vfx_Active, Vfx_AI_Active (v AI: the prow hologram) | C |
| dampener | `0x40000C88` / `0x40000C87` | `0x40000C91` / `0x40000C95` | (40.0, 77.5) / (120.0, 77.5) | -90 / 90 (marker yaw) | Object_Activate, Vfx_Active, Vfx_AI_Active (v AI only); socket floor below | P |
| lane turret | `0x40000C8C` / `0x40000C8B` | `0x40000C92` / `0x40000C93` | (65.0, 77.5) / (95.0, 77.5) | -90 / 90 | head `0x2E000AA8` + gear plate `0x2E000A9F` (as today) | C |
| ~~core turret~~ | remove (`0x40000C8F` / `C8D`) | remove (`0x40000C94` / `C97`) | ~~(25.5) / (134.5)~~ | - | - | C (no marker, no original minimap icon) |

Server consequences (for the implementer; no code changed here):
- Drop the `core_turret` entry from `_crime_alley` behind a config switch (e.g. `crime_alley_core_turret = false`,
  default false, comment 2026-10-28 tester). With no core turret, `Match` structure order (`match.py` ~281) already
  falls back to "core requires any dampener", which matches turret -> dampener -> core. Bots' target lists
  (`bots.py`) need no change.
- Keep the dampener at 40 / 120. The black socket stays until a floor is sent: `0x2E0000E3` at (40.0, 77.5, 198.0) /
  (120.0, 77.5, 198.0) yaw 0 (tested: closes it, pale), or try the textured core pedestal `0x2E000A3B` at (40.0,
  77.5, 200.12) yaw 90 / (120.0, 77.5, 200.12) yaw -90 (G look: a round 21 x 20 m platform, bigger than the
  original's ring) (`deep-scan-maps.md` 3.1 row 1).
- O: the original's ground at x 40 (continuous cobbles) means either a different terrain build without the socket or
  a street piece not in this install; no installed data explains it.
