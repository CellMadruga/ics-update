# Black ground shapes (Crime Alley dampener, Gotham Divided exits and pits, Coast City centre), 2026-10-25

Follow-up of `test-2026-10-25-1612.md` (CA-1, GD-1/2/3, CC-2) and `stubborn-visuals.md` 1. Sources: the map packs'
terrain (`0x80`) and statics (`0x82`) records parsed with throw-away scripts, the decompiled client
(`re-work/decomp`), the exe (read only) and the tester's frames (extracted from the 16:12 video, not in the repo).
Confidence: **C** confirmed (data / code read), **P** probable, **G** guess, **O** open.

## 1. Result in one paragraph

Every black shape sits exactly on a **terrain socket**: landblock terrain vertices that the map pushes far below the
ground so that a model can stand in the hole (C). Where the socket's model is present (core pedestals, the lane
turret's plate) the ground looks right; the black shapes are the sockets whose model is **missing or not drawn**, and
the hole shows through as an opaque black funnel (C for the geometry, P for why it renders black). It is not the team
tint, not the fog, and not a missing texture pack: the meshes and textures of the statics around these spots are all
in loaded packs (C, section 5). The fix is to put the missing models in the sockets (section 4).

## 2. The terrain sockets (C)

### 2.1 How the client builds the terrain

- `0x53E290` (LandBlockMesh) -> `0x53BBE0` -> `0x53BB00` / `0x53BA00`. Record `0x80 | 1 | lbx | lby` (e.g. Crime
  Alley `0x800113BB` in map pack `0xA0C112BA`): `did | 0x441 | 1089 bytes cell flags | 0x441 | 1089 u16 heights`.
- `0x53BB00`: 33 x 33 vertices, **5 m apart**: vertex (i, j) = (x = i * 5, y = j * 5, z = h[i * 33 + j] * 2000 *
  `[0x185F0FC]`), i.e. z = u16 * 2000 / 65535 m. `0x53BA00`: two triangles per 5 m cell, the split diagonal from flag
  bit `0x80` (LOD 0) / `0x01` (LOD 1). No hole flag exists in this record (C: every flag byte is 0 or 0x80 on Crime
  Alley).
- So one lowered vertex turns the triangles around it into a funnel whose opening is the ring of its neighbours:
  **one vertex = a 10 m square or diamond, two = a 10 x 15 m octagon, a 3 x 3 block = a ~20 m polygon** (the shape
  depends on the split diagonals).

### 2.2 Sockets per map (vertex heights; ground 200 m on Crime Alley, 250 m on GD / CC)

| Map | Socket vertices (x, y) -> z | What should fill it | Seen black? |
|---|---|---|---|
| Crime Alley | (40, 75), (40, 80) -> 180 (20 m deep) and the mirror (120, 75), (120, 80) -> 180 | the dampener site (marker `0x2E0011A9` / `0x2E0011A8`, type 3, world state in no installed pack) | **yes** (CA-1 octagon, x 33-45.5, y 73.5-86 in `crime-alley-video-compare.md` = the two-vertex funnel 35-45 x 70-85) |
| Crime Alley | (15-20, 75-80) and (140-145, 75-80) -> 0 | core pedestal statics `0x2E000A3B` | no |
| Crime Alley | (60-70, 70-80) + (75, 80) -> 0; (85-90, 50-65) -> 0 | lane turret t1 (server plate `0x2E000A9F`) / south scenery | no (frame 6:12: plate on normal ground) |
| Gotham Divided | (40, 150), (35, 125), (10, 120) -> 200 (50 m deep) and team 2 (150, 40), (125, 35), (120, 10) | the three base lane exits; only a debris static `0x2E000EE1` on each (C, all six) | **yes** (GD-1 at (39, 149.5), GD-2 at (35.5, 124.5)) |
| Gotham Divided | (55, 55), (105, 105) -> 0 (250 m) | the neutral sites: lid `0x2E0003F0` (z 247.5), tram `0x2E000FBE`, ctype-9 `0x2E00133D` / `133E`, light | **yes** (GD-3 diamond around the tram) |
| Gotham Divided | (15-20, 140-145) and (140-145, 15-20) -> 100 | core pedestals | no |
| Coast City | (75-85, 65-75) 3 x 3 -> 0 | the plaza statics `0x2E000AD1` + `0x2E000BE8` / `0x2E000BE7` at (80.0, 70.4) yaw 180 | **yes** (CC-2; the tester's estimate (84-94, 68-78) overlaps, position P) |
| Coast City | (80, 85) -> 200 | Doomsday Device site (`0x2E001178` / `1181` at (80, 82)) | no (device spawned there) |
| Coast City | (15-20, 60-65) and (140-145, 60-65) -> 0 | core pedestals | no |

Every socket that has its model shows normal ground; every black shape is a socket without one (C for the match
between the lists and the video, P that this is the whole story for CC, see 4.4).

### 2.3 What the black shapes are not

- **Not the team tint** (`stubborn-visuals.md` 1.3): the claim "team-2 dampener looks fine" is not in the video. The
  frames cited (4:00-4:40, 6:40) show the enemy **lane turret at 95** (target panel "Turret" 2689/3000) and the team-1
  turret at 65, never the team-2 dampener at 120; the 13:13 test saw an octagon at x 120 too (frame 110 s). Both
  dampener sockets are identical (C). `team_as_change` can stay (harmless) but does not fix this.
- **Not the gate**: the GD square stays after the gate is removed (0x3 at 16:32:25.7, C traffic) because it is the
  socket. The "small dark-red block" inside it is the debris static `0x2E000EE1`: its `.entity 0x2D000C6A` carries
  one inline mesh `0x170015FA`, 94 vertices, bbox 1.24 x 1.14 x 0.45 m (C). It is **not a gate frame** (correcting
  `map-gaps-gotham-divided.md` 2 and the gate anchor in `ics/match/maps.py`).
- **Not the fog of war**: the shapes do not move with vision, sit on fixed grid vertices and stay while the player
  stands next to them (C frames).
- **Not missing packs**: section 5.

## 3. Why a socket renders black (P)

The funnel walls are 76-89 degrees steep and 20-250 m deep; the terrain material (`0x14000209`-`20E`, textures in
the map pack, all loaded, C) is stretched over them and lit almost edge-on, and the bottom is far below the street.
In the frames the area is uniformly black with sharp straight edges (C). Whether the client also culls triangles at
height 0 is O; it does not change the fix.

## 4. What should fill each socket, and the server-side fix

### 4.1 Crime Alley dampener sites (P)

- In Crime Alley nothing fills (40 / 120, 75-80): the only statics there are the type-3 markers `0x2E0011A9` (40,
  77.5) yaw -90 and `0x2E0011A8` (120, 77.5) yaw 90, whose world states exist in no installed pack (C,
  `maps-complete.md` 0 #6). The server's dampener `0x40000C88` / `0x40000C87` (world state `0x2E000E04`, rig
  `env_pvp_dampener_a`) draws a hollow ~6 m ring with the pedestal inside (frame 0:40 zoom, C): it cannot cover a 10 x
  15 m funnel, and the pit shows even inside the ring.
- **Tutorial 2** (map pack `0xA0C112C2`, same zone / layout / variants packs as Crime Alley) has the **same 20 m
  socket** at (40, 75) / (40, 80) (C, terrain `0x800113C3`) and fills it with the static **`0x2E00119F`** at (40.0,
  77.5) ("structure socket", team -1; world state `0x2E00119F | 7 | .entity 0x2D000EB2`, props `0x50F = 6`, `0x7D2 ->
  table 0x1D000385`, `0x7EB = 7`, `0x2A4 = 1`; Havok rig entity). It lives in the layout pack **`0xA00002E6`**, which
  Crime Alley already sends (C).
- The dampener's own Vfx_Active child `0x2E000A9E` (type-0x0C node in table `0x1D00063A`, pack `0xA00002E6` at
  0x13CCB8 / 0x1A0ADC) has **`0x67C = 1`** and scale (0.75, 0.75, 0.5), so the client spawns it itself (C, field map
  of `stubborn-visuals.md` 2.1); it is not the missing cover.
- **Fix (P):** spawn the bare world state `0x2E00119F` at each dampener site, as the turret plate is spawned today:
  (40.0, 77.5, 200.0) yaw -90 and (120.0, 77.5, 200.0) yaw 90 (the markers' yaws), no team, created before the
  dampener so the dampener draws on top. Same for Clash (`0x40000E68` / `0x40000E74`, same map pack).

### 4.2 Gotham Divided lane exits (P)

- The six 50 m sockets are the three lane exits of each base, ~31-40 m from the start, each with a 1.2 m debris piece
  (C). Gotham Divided has one dampener per lane (announcer ids dampener_north / mid / south in
  `announcer_events_by_map`, C) and the dampener is an Inhibitor-type structure (PerceivedType `0x810`, C) standing
  on its socket on Crime Alley. So the sockets are the **GD dampener sites** (P); `maps.py` has the GD dampeners at
  guessed spots (56.3, 148.2), (46.8, 113.1), (11.8, 98.2) ("conf G") and the base gates on the sockets.
- **Fix (P):** GD dampeners at the socket vertices: team 1 north (40.0, 150.0), mid (35.0, 125.0), south (10.0,
  120.0); team 2 mirrored across x = y: (150.0, 40.0), (125.0, 35.0), (120.0, 10.0); each with the socket cover of
  4.1. `0x2E00119F` is **not** in GD's packs (only `0xA0000256` / `0xA00002E6`), so GD would need `0xA00002E6` (22 MB,
  a layout pack, not a zone pack) in its 0x20AF list; test that load first (a second zone pack hung the load on
  2026-10-23; a layout pack is untested, O). The gates then move a few metres toward the base along each lane (G:
  ~8 m, as Crime Alley's gate at 29.5 sits 10.5 m in front of its dampener at 40).
- Until then the squares stay even with the dampeners moved: the dampener alone does not cover a socket (4.1).

### 4.3 Gotham Divided neutral sites (55, 55) / (105, 105) (P)

- The lid static `0x2E0003F0` (`.entity 0x2D0002D7`, mesh `0x17001532`, z 247.5) is the **only static on any of
  the four maps that carries `0x2A1`**, present without a value (C: GD 2, CC / CA / GH 0). The client draws an entity
  only if `0x2A1 && 0x76A && !0x90F` (`0x61CB30`, C; defaults 1 / 1 / 0), so the lid is P hidden from the start, and a
  client static (IID top byte 1) cannot get a server property. The tram `0x2E000FBE` (no `0x2A1`) is drawn, as in
  the frame (C).
- The phase pod rig `env_pvp_phase_pod` (entrance / active / attackable / die, pack `0xA0000168`, C names) rises at
  these sites at ~10:00 (`map-gaps-gotham-divided.md`), so the pit is the pod's shaft and the lid is meant to be shown
  / hidden by the match (P).
- **Fix (P):** spawn the lid as a server object: bare world state `0x2E0003F0` at (55.0, 55.0, 247.5) and (105.0,
  105.0, 247.5), yaw 0, with `0x2A1 = true` in its property table (kind bool), removed when the pod emerges and sent
  again when the pod dies.

### 4.4 Coast City centre (80, 70) (P / O)

- The 3 x 3 socket (75-85, 65-75) lies under `0x2E000AD1` (11 mesh parts, all in loaded packs) + `0x2E000BE8` /
  `0x2E000BE7`, all at (80.0, 70.4, 250.0) yaw 180, no properties, no ruleset list (C). Why they do not cover it is O
  (not drawn, or not meant to cover the whole hole).
- **Fix (G, after the diag in 6):** the same world states as a server copy at (80.0, 70.4, 250.0) yaw 180 if the
  static is not drawn; otherwise a socket cover sized for 20 m. Coast City's mirrored side (62, 76) has no socket
  (C), which is why it looked fine.

### 4.5 Proposed [ics] keys (config.py defaults, one comment each with the 16:12 report)

```
# 2026-10-25 16:12 (tester: black octagon / squares / diamond on the ground; black-ground-shapes.md): terrain sockets
# the server must fill. map key -> [{world_state, pos [x, y, z], yaw, props {id: value}}]; [] = none.
"match_socket_covers": {
    "crime_alley": [{"world_state": 0x2E00119F, "pos": [40.0, 77.5, 200.0], "yaw": -90.0},
                    {"world_state": 0x2E00119F, "pos": [120.0, 77.5, 200.0], "yaw": 90.0}],
    "gotham_divided": [{"world_state": 0x2E0003F0, "pos": [55.0, 55.0, 247.5], "yaw": 0.0, "props": {0x2A1: True}},
                       {"world_state": 0x2E0003F0, "pos": [105.0, 105.0, 247.5], "yaw": 0.0, "props": {0x2A1: True}}],
    "coast_city": [],
},
# GD dampeners on the lane-exit sockets (true) or at the old guessed spots (false); the base gates step back
# gd_gate_setback m along the lane. Needs 0xA00002E6 in GD's 0x20AF for the socket cover (gd_extra_layout_pack).
"gd_dampeners_on_sockets": True,
"gd_gate_setback": 8.0,
"gd_extra_layout_pack": 0,          # 0xA00002E6 to test; 0 = not sent
```

`maps.py` would read `match_socket_covers` in `_spawn_scenery` (spawned like the turret plate: class = the world
state, z from the entry, no team, before the structures) and the GD dampener positions above.

## 5. Packs and textures checked (C, lead 2 ruled out)

Chains world state -> `.entity` -> model part `0x17` (binding header `did | shader 0x14 | key | 1 | material 0x16`)
-> material textures `0x13`, against the packs each match loads (0x20AF list of the session log + the start-up packs
`0xA0000039 / 38 / 11A / 37 / DF / B3 / 103 / 351 / D0`):

- GD `0x2E000EE1` (debris), `0x2E0003F0` (lid), `0x2E000FBE` (tram), `0x2E00133D` / `133E`: every record in
  `0xA00000FC` / `0xA0000168` / `0xA00000DF` / `0xA00000B3` / `0xA0000037`.
- CC `0x2E000AD1`, `0x2E000BE8`, `0x2E000BE7`, `0x2E000BD5` / `BD6`, `0x2E000871`, `0x2E0008E3`, `0x2E0005A4`: all in
  `0xA00000D2` / `0xA0C122E2` / `0xA00000DF` / `0xA0000037`.
- CA dampener `0x2E000E04` / `0x2D000BAF`, tables `0x1D0005A1` / `0x1D00063A`, graph `0x1C0000A0`: `0xA00002E6`.
- Terrain materials (`0x14000209`-`20E`, `0x140002C5`) and their textures: map pack + start-up packs.
- Side note: many `0x17` records are a 20-byte binding with the geometry elsewhere (e.g. `0x170015FA` in
  `0xA00000FC`, `0x17001532` in `0xA00000FC` / `0xA000024C`); this is normal (CA: 220 of 290 mesh references from
  statics, all drawn), so it is not a cause.

## 6. Diag to confirm before / after the fix

1. `tools/diag.py` break on `0x61CB30` return (ECX+4 = the entity; log its IID, world state `[ent+0x110]` and AL) for
   entities whose world state is `0x2E0003F0`, `0x2E000AD1`, `0x2E00119F`: AL = 0 on the GD lids confirms 4.3.
2. In game, after `match_socket_covers`: the CA octagon must be gone at both dampeners (walk to x 120 this time; the
   16:12 video never showed it) and the GD diamonds at (55, 55) / (105, 105).
3. For GD exits, first test `gd_dampeners_on_sockets` without the extra pack: the square should shrink to whatever
   the dampener does not cover (as on Crime Alley today); then `gd_extra_layout_pack = 0xA00002E6`.
