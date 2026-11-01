# Gotham Heights move freeze, map holes (GH / Crime Alley), drone picking (2026-10-29, fase3-ii)

Tester report 2026-10-29 14:40 (Crime Alley v AI 14:19-14:34, Gotham Heights 0x40000B6C 5v5 domination with 9 bots
14:35-14:37; earlier GH runs 10:26-10:28 and 11:01-11:02). Evidence: `logs/server.log`, `logs/traffic.log`,
`logs/diag.log` of those runs, screenshot `46.webp` (Crime Alley centre), the installed packs (read only), the
decompiled client (`re-work/decomp`, capstone on `InfiniteCrisis.exe`, VAs, image base 0x400000). Throw-away scripts
in the session scratchpad only; nothing of the game is copied here. Tags: **C** confirmed, **P** probable, **O** open.

## F. Gotham Heights: the champion stops taking move orders

### F0. Facts (C, logs)
- 14:35 run: the client sent exactly **one** move (0x20EE command 4) at 14:35:54.462, 2.6 s after the intro ended,
  to (8.7, 48.2) (2.7 m from the start (6.0, 47.0)). From then to the exit (14:36:59) it sent skill orders (command 2,
  Grab at 14:36:11 / 36 / 54), skill events 0x20EA and two selection changes 0x20D1 (it selected the ally bot
  Nightmare Batman 0x0200000000000102 at 14:36:14), but **no move**. The match started at 14:36:33; the server logged
  no refusal (no move reached it).
- 11:01 run (Atomic Wonder Woman, no skill cast): the same pattern, one move at 11:01:56.791 (to (7.9, 46.2)), 1.8 s
  after the intro, then nothing for 11 s. The 10:28 run (CHANGELOG fase3-ig): moves in the countdown, none after.
- Same session, Crime Alley (14:21) and Gotham Divided (12:41: 706 moves) are normal. So it is Gotham Heights only and
  independent of the champion and of a cast.

### F1. Where the client drops a right click (C, code)
Order API `0xA70030(champ, cmd, ability, &target, Position...)` (this = input controller):
1. `0x9CFAF0` (LifeState 4, no `0x10000B2D`) unless the skill has `0x10000B4D`: fails -> no order. **Not it**: skill
   orders went out, and they pass the same gate.
2. controller `+0xCC != 0` -> no order of any kind. **Not it** (skills sent).
3. cmd 3 / 4 (and attacks with skill bool `0x10000708`): `0x4FB400(champ, clickPos, out, 0, 2.5)` snaps the clicked
   Position onto the champion's navmesh (agent shape from `0x4F2E40`; `0x4FA6E0` = on-mesh test in the click's
   landblock section, `0x4FA870` = search within 2.5 m). Fails -> `return 0` at `0xA700FA`, nothing sent.
4. `0x8686C0` (buffer at controller +0x48): a move is held while `[+0x70] | [+0x74]` (u64) != 0 or `[+0x8C]` != -1.
   `[+0x8C]` is written only by the listener `0x8614D0` (vtables 0x15EDD30 / 0x16035E0, a skill-start notice:
   slot, expiry now + 0.24 s) and cleared by `0x861520` and by the expiry check in `0x8686C0` itself, so it is
   transient. Skill orders are held by `0x863860` when `[+0x70]` != 0; they were sent, so `[+0x70]` was 0. A
   permanent hold would need `[+0x74]` alone (P: no).
=> the move is lost at step 3: **the clicked point is not on (or within 2.5 m of) the navmesh** (P strong).

### F2. Why only on Gotham Heights (P)
- The ground point of a right click is the pick of the world's collision under the cursor. Every map's base gates are
  closed walls until the start; on Crime Alley / Gotham Divided / Coast City `ics` removes them
  `base_gate_remove_after` (1.5) s after Object_Open because the client keeps the door's collision (2026-10-23 19:22:
  "the champion's clicks stopped at x 28.6").
- Gotham Heights' gates are the layout pack's two **Door** classes `0x4000026B` / `0x40000269` (ws `0x2E00084A` /
  `0x2E000845`, 20 x 37 m, **11 m tall** frames, ramps in the mesh; `test-2026-10-25-1928.md` GH-2), placed at a
  **guessed** spot (26, 54) yaw 180 (team 2 mirrored) and marked `"keep": True` in `ics/match/maps.py`, so they stayed
  all match. With yaw 180 the box spans about x 19.4-39.9, y 35-72, right in front of the spawn (6, 47) on the way to
  both rings (lane mouth (18, 47) -> (31, 47)). A click toward the lanes hits the door's frames / ramps metres above
  the 250.1 m navmesh, the 2.5 m snap fails and the order is dropped; a click next to the champion on bare ground
  works (the single moves at 2.7 m and 1.8 m from the start).
- Not the cause (C): GH's terrain on the team-1 side is flat 249.97 m (H1), the base aura `0x4000041F` only gets the
  in-base status (same code path as the other maps), the delta / bundle mode (bundle already since fase3-ig).

### F3. Fix and test
- `[ics] base_gate_keep_after_open` = **false** (`ics/config.py`, dated comment): a gate marked "keep" goes like every
  other gate `base_gate_remove_after` s after Object_Open. GH's ramps / doors are seen only during the countdown.
  true = fase3-ih. `tests/test_match.py`: "GH: the base doors go after the start".
- `tools/diag.py --moves` (`--movimientos`): one line per step of a right click (0xA8A140 right click, 0xA86A47 hover
  pick entity, 0xA70030 command / `[ecx+0xCC]`, 0xA70072 may act, **0xA700F8 snap result + the click Position**,
  0xA70224 buffer hold + `[+0x70] [+0x74] [+0x8C]`, 0x88B030 sent). If GH moves still fail, this says which step.
- O: the doors' real spot (no record places them); before the start a click on the door is still dropped (as on the
  other maps' closed gates). If the player must keep the ramps visible, a collision-less copy would be needed (no
  known property turns a world state's collision off client-side).

## H. Holes

### H1. Gotham Heights terrain (C, record `0x80011BF3`, pack `0xA0C11AF2`; neighbours 1AF3 / 1CF3 / 1BF2 / 1BF4)
- x 0-110 at 249.97 m everywhere (no sunk vertex); `0x80011AF3` (x < 0) flat 250. East of x 115-145 the whole
  terrain sits at the 200 m covered level (team 2's base floors are statics, `test-2026-10-25-1928.md` GH-2).
- The 0 m diagonal (115, 10)-(125, 25) (map-audit-all.md 2.2 "not enclosed") is a **designed fissure**: statics in
  it at 242-247.7 m (`0x2E000861` x2 at 242.3, lava overlay `0x2E0005D6` at 245.2, point lights `0x2E000011` at
  246.2-247.7), bridge pieces `0x2E0007AD` / `0x2E0007AE` at 250.1 m across it at (113.8, 16.5) / (121.3, 21.6). The
  navmesh walks over it at 250 (the bridges). Flattening it would bury the lava: **keep**, no site.
- Navmesh vs terrain (ics grid, 5 m samples): every walkable cell west of x 125 is on terrain; east of x 127 the mesh
  is 50 m above the terrain (statics floors). Nothing on GH qualifies as a socket site.
- What the tester calls "zones that do not load" on GH is, from the evidence, the base front: the Door's guessed
  placement (ramps / frames, F2). O: a GH screenshot (and `tools\diag.py --mapa` for NOT FOUND statics in blocks
  1BF3 / 1CF3) is needed if black ground remains after the door goes.

### H2. Crime Alley centre around the stealth tiles (C heights, screenshot 46.webp)
- Scale from the turret disc (65, 77.5) and ~45 px/m: the north black strip is x ~73-80, y ~81-84 (quads touching
  (70, 80) / (75, 80) at 0 m): the existing site `crime_alley_lane_turret`, **not yet applied** (`ic.py patch
  --dry-run`: "would flatten").
- The south band under the south stealth field, x ~79-87, y ~66-70, is not that site: it is the rim of the south
  alcove (heights: (85, 50-65) and (90, 55-60) at 0 m, (80, 65) at 195 m, the rest 199.98). Vertex (85, 65) opens
  the sidewalk quads x 80-90, y 65-70. Props there stand at street level (`0x2E00026D` (82.31, 68.60, 199.98),
  `0x2E000481` (87.14, 69.62, 200.93), `0x2E0006E1` (90.80, 61.24, 199.98), `0x2E00128C` (86.91, 66.00, 201.22)).
- New site `crime_alley_south_alcove_rim`: (85, 65) -> 199.98 m (0x1999, the ring median), upright normal at it and
  central-difference normals at (85, 70) / (90, 70) (3 normals); whole_triangles 0; CRC 0xBD45_DDC9 -> 0xF230_ADFD.
  The alcove's inside and (80, 65) stay (`0x2E000B59` stands at 197.24 m in (80, 65)'s quad). In `[game]
  terrain_sockets` by default.
- North mirror: rows y 85-110 at x 60-95 are 200 m (no socket). Nothing else in x 70-90, y 60-95.

## P. Drone picking ("the click area of the drones is very small")

### P1. How the client picks the unit under the cursor (C, `0xA81B30`)
- Two candidate sources, both along the cursor ray (camera -> 10 000 m):
  1. render pick `0x75D150` with filter `0xA0E120` (render object type +0x218 == 2 with the entity at +0x260, or
     0x200; flags +0x220 & 0x8000 / 0x800 clear; visible view layer; +0x210 > 0.0002): candidates get flags 1,
     priority 3;
  2. a **swept box of +-0.8 m** (`0x5B27B0` start / end / half extents -0.8..0.8, detail 3 `0x5B22C0`, query
     `0x5BCD30` -> `0x598080`) against the objects' collision parts: candidates get flag 2 and a priority from the
     hit part type (+0x88: 0/2/6/8 -> 1, 1/3/5/7 -> 2, 4 -> 3).
- Each candidate: property `0x100004A4` (if present) must be a subset of its flags; only candidates with priority >=
  the current best's are scored (`0xA16A60`; > 0 needs `0x2A1` != 0 and the attack validator `0x9D01D0` slot 0, or an
  interact / tiny score); the highest score wins, ties by distance. The candidates come from a hash walk, so the order
  is arbitrary: once a priority-3 candidate is taken, lower-priority ones are not looked at (C).
- So a unit is easy to click when it has a collision part the box sweep reaches (1.6 m wide), and only as wide as its
  mesh when it is picked by the render ray alone (P: what the tester sees on the thin drones).
- Validator step 6 (`[target+0x88]` vt+0x5C): if that is the fog component (vtables 0x16098E8 / 0x16099D8), the slot
  is `0x5534A0` = return 1, i.e. never refuses (P on the component).

### P2. Status (O)
- No difference between our lane drones / camp units and what the client needs was proven statically: they get the
  template's targeting properties (`0x1000019D` late, `0x10000AA7`, `0x100001C3`, `0x1000034C`) and `0x2A1`. Open
  candidates: the drones' collision parts do not reach the box sweep (movement module / creation type), an ally or a
  prop with a higher pick priority taken first (hash order), the late unit flags on a fresh wave.
- To decide: `tools\diag.py --moves --target` on Crime Alley, right-click a drone several times: "MOVE: hover pick"
  shows entity 0 (the pick missed: collision / render) or another entity (an ally / prop stole it), "HOT target"
  shows a validator refusal. No behaviour change in this build for picking.
