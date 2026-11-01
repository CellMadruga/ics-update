# Gotham Heights base door / moves / capture pads / intro bindings; Crime Alley black sections (2026-10-29, fase3-ij)

Tester report 2026-10-29 15:30 (runs 15:17 Crime Alley v AI 0x40000C82, 15:21 Gotham Heights v AI 0x40000B6C).
Evidence: `logs/server.log`, `logs/traffic.log`, `logs/diag.log` (`--brazo --movimientos --target`, 15:17-15:26),
screenshot 47.webp (GH 00:54), 46.webp (CA before the patch), the installed packs (read only), the decompiled client
(`re-work/decomp`, VAs, image base 0x400000). Throw-away scripts in the session scratchpad. Tags: **C** confirmed,
**P** probable, **O** open.

## 1. GH: no move until the start (C timing, C mechanism data, P mechanism code)

### 1.1 Facts (C)
- The diag's MOVE lines were muted after 100 hits during the Crime Alley run (15:18:44, `tracer.py` budget), so the
  GH run has none. The `--target` ORDER lines (0xA86B11 / 0xA86BB8) did log GH right clicks: 15:22:28, :54, :59,
  15:23:07 x3 (hover on an entity -> interact 0x1000001A, attack no -> falls to the ground order).
- Moves received: one in the countdown (15:22:27.958 to (6.3, 49.6), 0.3 m from the start), none until the start,
  then continuous from **15:23:08.627** to the end (champion walked to (125, 110), the N point, etc.).
- `traffic.log`: Object_Open 15:23:06.866, **"base gate t1 gone (0x3)" 15:23:08.397**: the first move came 0.23 s
  after the door left. In fase3-ih (door kept) no move came even after Object_Open. So the door's presence, not its
  closed state, drops the clicks.
- The ground point of a right click is not a collision pick: 0xA86A00 -> 0xA12510 -> 0xA12280 builds the camera ray
  and 0xA12590 intersects it with the horizontal plane at the champion's height (C). So fase3-ii's "the click lands
  on the door's frames" is wrong.

### 1.2 The door's obstruction box (C data, C reader)
- World state `0x2E00084A` (team 1) / `0x2E000845` (team 2): 0x83C = 1, 0x8C1 = 2, table 0x8AA {0x858 (-30, -30, 0),
  0x857 (30, 7.93, 4) / (30, 1.8, 4)}, 0x856 = 248.41 / 110.39.
- 0x6063C0 (component builder 0x606400): 0x83C == 1 -> AIObstructionComponent (vtable 0x15C65A8, init 0x5561D0).
  0x555E20 reads 0x8C1: 2 -> 0x554EB0 reads 0x8AA's 0x858 / 0x857 (min / max), adds 0x85C, rotates by 0x856 degrees,
  scales by the entity scale: a 60 x 38 x 4 m Kynapse obstruction box.
- With ics's placement (26, 54), yaw 180 (heading 270), box yaw 180 + 248.41: the box covers both base exits (north
  x 22-30 / y 62-70, south y 34-40), the core platform and the lane mouths, and stops exactly at the base pocket's
  east edge (x 2-12 stays free; scratch `ghbox3.py`). P: this is the original's pre-start seal and the placement is
  right; a click outside the pocket fails the 2.5 m navmesh snap of 0xA70030 (0x4FB400 / 0x4FA870) and is never sent;
  a click in the pocket works (the one countdown move, 2.7 / 1.8 m moves of 14:35 / 11:01).
- 0x83C: 1 obstruction, 2 / 3 physics object (0x552D10 / 0x54FD00). Network mode 0 for 0x83C / 0x8C1 / 0x8AA / 0x856
  (MasterProperty), like 0x100007A2 which the client takes from our bundles.

### 1.3 Fix
- Countdown: unchanged (the seal; P original behaviour). Clicks inside the base pocket move.
- Start: the door goes after base_gate_remove_after (1.5 s) as in fase3-ii (moves come back at once, C), and 0.1 s
  before, `Match._gate_floor_copy` creates a copy of the same class / world state at the same spot with bundle
  properties 0x83C = 0 and 0x8C1 = 0 (enum) and runs Vfx_OnInit + Object_Open on it: the ramps / floor stay, with no
  obstruction (P: that a bundle value wins over the world state's for these two reads). `[ics] base_gate_floor_copy`
  = {"props": {"0x83C": 0, "0x8C1": 0}, "scriptlets": [...], "same_class": true}; {} = fase3-ii (door just goes).
- `tools/tracer.py`: MOVE lines get a 6000-hit budget (they were muted after the first map).
- If moves die again after the start with the copy, the override is not read: set `base_gate_floor_copy = {}` and
  run `tools\diag.py --moves` (O: next try a carrier class or 0x8C1 = 1 with a zero-radius prism 0x8B1).

## 2. GH: hole at the core's exit, ramps gone (C cause)
- What vanished is the door itself (fase3-ii removes it): its mesh is the base front's floor and the two ramps
  (test-2026-10-25-1928.md GH-2). Fixed by the floor copy (1.3). The tester's view of the countdown (ramps in place)
  and the box fit (1.2) both support the (26, 54) yaw 180 placement (P).

## 3. GH: the point "a few degrees to the left" (C data, O meaning)
- At 00:54 (15:24:00) the champion stood at (80.1, 128.1) (last move 15:23:56): the N point. Its marker cluster
  (waypoints idx 0x1F2A / 0x1F93-95 at (80.0, 127.75), 0x4 / 0x13F at +-1.5 m) and the pad static **0x2E0008D5**
  (idx 0x182D, (80.0, 127.93), yaw 180) agree; GH is mirror-symmetric about x = 80, so the N pad is at the top centre.
  The minimap ring (scaled 278 px / 55 m) puts relays 5 / 2 / 4 / 3 exactly at our W / E / SW / SE angles.
- The five pad statics: SW (49.45, 26.5), SE (111.72, 26.99), W (26.91, 90.47), N (80.0, 127.93), E (133.1, 90.1).
  Our points used the markers' centres: SW 1.4 m off, others <= 0.55 m. `[ics] match_capture_on_pads` (true) puts
  the points on the pads.
- O: nothing in the data puts the N point elsewhere. Needed: a screenshot with the camera centred on the champion
  standing in the middle of the N pad, plus (if known) where the original's top point was relative to the lamp posts
  0x2E000011 at (61-66, 130-134) / (94-99, 130-134), which are symmetric about x = 80.

## 4. GH: only the player's champion plays the intro animation (C)
- Intro 0x35000023: five "needs binding" actors, ThePlayer (key 1, centre) and Player01..04 (actor variables
  0x10000001..4), all start Cinematic_Hidden and appear with Cinematic_Intro at frames 2 / 30 / 123 / 155 / 243.
  ics bound only {0, champion}; an unbound actor is skipped.
- 0xA9C610 with flags bit 1 and A = 0 (no bit-10 field) rewrites only the entry equal to the local champion (key 1);
  the other entries keep the key sent (C). Fix: the allied champions (same team, lobby order, up to 4) go out as
  {0x10000001 + k, bot IID} (`[ics] cinematic_bind_allies`, false = champion only). A bound actor copies the bot's
  visual component; the real bots are hidden during the scene (hide mask 8).

## 5. Crime Alley: "the sections still do not load" (O)
- The patch is in the installed pack (C, `0xa0c112ba.rp` heights read back): every vertex of crime_alley_dampeners,
  crime_alley_lane_turret and crime_alley_south_alcove_rim is at street level. Remaining terrain vertices below the
  street near walkable navmesh: only the two core sockets (15-20, 75-80) / (140-145, 75-80) (under the core pedestals)
  and the lane-turret socket's centre row (60-70, 75), kept at 0 m under the lane cover by design (C heights).
  CA's 13BB batches use no missing texture (map-audit-all.md 3.2).
- The recording 2026-10-29 12-09-37.mp4 is no longer in Videos (moved / deleted), so no frame comparison was possible.
- Needed: a screenshot at the spot of 46.webp (champion between the turret and the stealth fields, x ~76) after the
  patch, and one of every other black area with the minimap visible; ideally run `tools\diag.py --mapload` from the
  menu (it logs per batch MISSING textures and dropped statics).
