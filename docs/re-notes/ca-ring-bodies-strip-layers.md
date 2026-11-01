# Crime Alley: what the turret ring's phantom can see, the strip is not a terrain hole (2026-10-30)

Tester report 2026-10-30 12:05 (build fase3-ir; run 11:59-12:05, Crime Alley v AI, AGL vs AI Deadshot). Evidence: the
run's `server.log` / `traffic.log` / `diag.log` (`diag --ring --fogpoly` 12:00:14-12:02:25, image base 0x2E0000, then a
second match with `diag --nofog` 12:03:16-12:05:01), screenshot `87.webp` (second match, `--nofog` active: AGL at the
north gate, the black strip still there), the tester's words "when I approached the enemy tower the indicator did not
appear", the decompiled client (`re-work/decomp`, static VA = RVA + 0x400000; file offset = VA - 0x400C00 in .text),
capstone reads of `InfiniteCrisis.exe`, the installed map pack `0xA0C112BA`. Tags: **C** confirmed, **P** probable,
**O** open. Builds on `ca-ring-phantom-strip.md`, `ca-street-occluder-ring.md`, `ca-black-strips.md`.

## 1. The ring (item 2 of the report)

### 1.1 What the 12:00 diag shows (C)
- The four enemy structures (iids 0x102 core t2 / 0x105 / 0x108 / 0x10B) pass every registration gate (allied 0,
  range 10 / 9), "registered", and the physics service builds each phantom: `create_fn` = 0x518CA0 at run time =
  **static `0x638CA0`** (0x518CA0 - 0x2E0000 + 0x400000; vtable `0x15CBBF0` slot +0x18), returns a non-null handle
  (the handle is a hash of the turret IID and key `0x8894382`, `0x596B00`), "phantom built al=1".
- The draw path runs (effect `0x48001239`, ring objects, state 6 = hidden) for the four turrets.
- **AGL entered the enemy lane turret's phantom**: FOGPOLY puts our champion (0x2) at (88.63, 78.98) at 12:02:12 and
  (84.97, 77.90) at 12:02:16, 6.4 m from the turret at (95, 77.5) (box half size 9 + 5.5 = 14.5 m), and the tester
  confirms the walk. Still **not one filter line** (0x452220 / 0x45227A / 0x45228E never hit).
- Only one "unit perception phantom created" line, at 12:00:50: **iid 0x138 = the Grab missile 0x40000485** that the
  server created at 12:00:50.016 (traffic "missile 0x40000485 created"; AGL cast Grab at 12:00:49.537). No line for
  AGL (entity added 12:00:30), the structures, or the minions 0x141-0x148 (12:02:13-18).

### 1.2 Units' collision bodies exist only while a script holds collision (C)
- The component with vtables `0x15F9500` / `0x1609520` (entity +0xB8, getter `0xAA10B0`) builds its body in
  `0x9793F0` (vt+0x50; key `0x4934AE2`, shape = the entity box `0x588360`, base filter `0x5BCDC0`). The body is
  created at exactly two places (the only code that compares the component's +0x38 handle with the null id
  `0x1B67EE0` and then calls vt+0x50; byte scan of every reference to 0x1B67EE0): **`0x976990`** (a script run's
  collision hold: EnableCollision `0x97D720` / DisableCollision `0x97D860`, holder list +0x8, count +0x10) and
  **`0x9754A0`** (holder list +0x18, count +0x20, from the node handler `0x994500`, a class no catalogued node uses).
  It is destroyed (`0x972110`) when the lists +0x10, +0x20 and +0x50 are all empty. Nothing builds it at spawn.
- The client runs a script on an entity it hosts (a missile's class scripts: hence 0x138 at 12:00:50); a champion
  class lists none (`entity_scripts` of every AGL class = []), and the client hosts no cast-script instances
  (`reverse-engineering.md`, client skill instances). So with ics no champion, minion or structure ever has that body.

### 1.3 What the ring's phantom accepts (C)
- The ring's filter is `0x8528F0(1)` -> preset **`0x5BB8A0`: own kind +0x54 = 0x10000, kind mask +0xC = 0xA08**.
  Siblings: `0x5BB880` (1, 0xA08), `0x5BB890` (0x100, 8), `0x5BB8B0` (0x1000000, 0x1000B).
- The service's overlap-add `0x6385D0` (and the filter re-run `0x637EA0`) reads the candidate collidable's Havok
  properties (`0x573050`: key 1 = owner, key 0 = **world-object type**, key 5 = IID, key 6) and drops it without
  calling the filter when `type & mask == 0` (`test [ebp-0x18], eax` at **0x638636**), else calls filter vt+0x28 =
  `0x852210`.
- World-object types (`0x5B1E60` names): 0 None, 1 Landscape, 2 Ceiling, 4 Virtual, **8 Shadow solid entity**, 0x20
  Shadow mobile phantom, **0x200 / 0x400 Rigid body character**, **0x800 Rigid body sub entity**, 0x10000 Cell
  entity, 0x20000 Cell phantom, Monitor (shadow), Cell portal. So the ring pairs with a unit's **character body or
  sub entity (or shadow solid entity)**, P not with the hold body of 1.2.
- So zero filter calls with AGL inside the box means: no collidable of AGL with type 8 / 0x200 / 0x800 overlaps the
  phantom (P strong: the champion has no rigid-body character in the client's world, or it sits in another world).
  Which body the original's champion had, and which server data makes the client build it, is **O**.

### 1.4 Diag for the next run (`tools\diag.py --ring`, new probes)
| RVA | Line | Reading |
|---|---|---|
| 0x238636 | `overlap candidate` | kind / mask / body IID / phantom for every collidable a service phantom starts to overlap. Mask 0xa08 lines = the ring's phantom: which kinds and IIDs it meets (none = it meets nothing at all) |
| 0x576990 | `collision hold` | enable 1 / 0 and the entity of every script hold (the missile's at a cast; none for the champion) |

No server-side fix: nothing ics can send was found that makes the client build a character body (O). Not a config
change in this build.

## 2. The strip by the fence (item 1)

### 2.1 Where (C, `87.webp`)
AGL at (78.0, 82.5) (FOGPOLY 12:02:24, same spot in the second match). Black pixels (RGB sum < 25) fill a
parallelogram: bottom edge straight along the lane mesh's north edge (y ~81.8), top along the fence base (y ~83.4),
**both side edges slanted the same way** (the west one is the known (70.05, 81.87) - (72.14, 83.41) line, 36 deg from
+x; the east one ends ~1.2 m further east at the fence than at the lane, x ~84 -> ~85.5, partly under the east tile).
The black continues under both north stealth tiles (seen between their hexes). Same place and shape as `49.webp` /
`83.webp` with other champions and spots: fixed in the world, and **not the fog** (`--nofog` set EnableFog 0 at
12:03:38: still black).

### 2.2 What it is not (C)
- **Not an index hole**: record `0x800113BB` (pack offset 0x38E1A44) has two u16 index arrays of 6144 (count at +0x19D0
  / +0x49D4): the near grid (index y * 33 + x) and the 16 far patches (9 x 9 vertices each, index patch * 81 + row * 9
  + column); both draw two triangles in every one of the 1024 cells, none degenerate.
- **Not the heights**: (70-85, 80-85) is flat 199.98 m since the lane-turret site (`ca-black-strips.md` 4).
- **Not the baked colour**: `0x13003439` (far patch x 40-80, y 80-120) shows curb and grey bricks at the strip;
  `0x1300343B` (its third texture) is one flat dark red value (no baked shadow in it).
- **Not a missing pack**: the statics there and `0x2E0011FE` (the jungle-hole piece at (80, 80, 188.48), scale 3,
  `0x7EB = 7`, `.entity 0x2D000F07` = a Havok shape, no mesh) are in `0xA00002E5`.
- **Not the fog occluder pass** (exe patch "fog occluder pass", 0x6AD624): useless for the strip; see 2.4.

### 2.3 Lead (P / O)
A parallelogram whose two side edges are parallel is the footprint of something projected along one direction:
a shadow (light from the north-east) cast by the fence pieces x ~72-86 onto ground that has no ambient term, or a
projected decal; or the terrain not drawn there at all (the scene's clear colour). The client has its own draw
toggles for each layer (WorldRender, registered by `0x7F1310`, byte fields): +0x2E AllowOutdoorMultiPassShadows,
+0x2F DrawLandscapeWater, **+0x30 DrawLandscape**, +0x31 DrawCeiling, +0x32 DrawFloor, +0x33 DrawSky, +0x34
DrawParticles, +0x35 DrawFrills, +0x36 EnableFog, +0x37 EnableDistanceFog, +0x38 EnableGroundFog, +0x39
EnableMaskFog, +0x3A DrawDynamicEntities, +0x3B DrawStaticEntities, +0x3C DrawOpaqueEntities, +0x3D
DrawTranslucentEntities, +0x3E DrawCellMeshes, +0x3F DrawLightCoronas. `--nofog` only cleared +0x36: ground and mask
fog (+0x38 / +0x39) stayed on.

`tools\diag.py --layers` (EXPERIMENT, running memory only) switches twelve of them off one at a time, 5 s each, and
logs each step: the step that changes the strip names its layer (DrawLandscape off and the brick wedge west of the
diagonal turns black = that wedge is terrain and the strip is something over / shading it; the strip vanishes with
AllowOutdoorMultiPassShadows or a fog toggle = a shadow / fog layer; nothing changes = the terrain is not drawn
there).

### 2.4 The "fog occluder pass" exe patch
It did not change the strip (fase3-ip and this run). It is harmless (allied vision only; the server's own fog still
hides enemies behind walls) and possibly what removed the black wedge by a lifted vehicle (`57.webp`). Keep it until
the tester confirms that wedge does not come back with `[game] exe_patch_skip = ["fog occluder pass"]` (needs
`python ic.py patch`); then it can go.

## 3. Tests
`tests/test_match.py` `ring_bodies_strip_layers` (4 checks): the filter preset / overlap-add test / hold entry /
DrawLandscape bytes in the installed exe, both 13BB index arrays cover every cell, no AGL class lists an entity script,
diag has the new probes and `--layers`.

## 4. Tester (no `python ic.py patch`; nothing in the exe or the packs changed)
1. Game in the menu, second console: `python tools\diag.py --ring`. Crime Alley v AI; walk into the enemy lane
   turret's range (x ~88) and stay 5 s, once alone and once with our wave. Send `diag.log`, `server.log`,
   `traffic.log`.
2. Then (diag stopped with Ctrl+C, game open): stand where `87.webp` was taken, `python tools\diag.py --layers`
   (Spanish `--capas`), do not move the camera for 70 s, record the screen or take one screenshot per 5 s step.
   Send the recording / screenshots and `diag.log` (the LAYERS lines give the time of each step).
