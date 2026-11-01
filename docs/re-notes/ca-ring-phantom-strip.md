# Crime Alley: the turret ring's phantom never reports a body; the fence strip is not the occluder pass (2026-10-30)

Tester report 2026-10-30 11:23 (build fase3-ip, `python ic.py patch --dry-run`: 38 / 38 exe patches in place, among them
"perception filter" 0x451544 and "fog occluder pass" 0x6AD624; terrain patches flattened). Run 11:05-11:23, Crime Alley v
AI with AGL vs AI Catwoman. (1) "The turrets' indicator ring (green / yellow / red) still doesn't show." (2) "The hole in
the middle is still there" (the black area by the fence between the north stealth fields; no new screenshot, `83.webp`
is the fase3-io one). Evidence: `server.log`, `traffic.log`, `diag.log` (`diag --ring`, 17 breakpoints, image base
0xE00000), the decompiled client (`re-work/decomp`), capstone reads of `InfiniteCrisis.exe` (image base 0x400000; file
offset = VA - 0x400C00 in .text), the installed packs. Tags: **C** confirmed, **P** probable, **O** open. Builds on
`ca-street-occluder-ring.md`, `ca-fog-minimap-ring.md`, `ca-fog-ring-announcer.md`, `fog-vision-runtime.md`.

## 1. The ring (item 1)

### 1.1 What the 11:05 diag shows (C)
- Diag attached 11:07:25. The structures' creation bundles went at **11:06:21** (traffic: core t1 .012, core_turret t1
  .186, turret mid t1 .530, t2 .659), i.e. while the client loaded the match; fase3-io's diag (attached before the match)
  saw the registrations 4 s after the bundles (21:04:46 -> 21:04:50). So this run's registrations of the structures were
  **before the attach** and are not in the log.
- The 346 "RING entity added" lines are the camps (iid 0x138-0x13F, 11:08:14-15, traffic "spawn camp ...") and the
  minion waves (0x140 on, from 11:08:17). "Turret bit" logs the whole eax: 0x100 / 0x10000 have **al = 0** = not a
  turret, which is right for them (the function returns a bool in al; the upper bytes are left-overs).
- **No line from 0x452220** (the instruction right after the filter `0x852210`'s first call, reached on every call):
  the filter class `0x15ECA98` (slot +0x28) was not called once in 16 minutes, neither by the ring's phantom nor by the
  other users of that class (0x9C24C0, 0x9CCE60, 0xA93470). No phantom callback (0x63A5F0), so no draw / state lines
  (`0xA84FB0` stops at state 6 while entry +0x4C = 0). The probes sit on instruction starts (checked by test_match).

### 1.2 The blocker (P: the phantom never pairs; O: why)
The ring needs the phantom built by `0xA2A710` (box of half size r + 5.5, filter `0x15ECA98`, listener `0x1602318`) to
pair with a unit's collidable; the broadphase calls the filter before the listener. Zero filter calls = no pair was
ever produced: either the phantom is not created (the service's create returns the null id; `0xA7CBF4` "phantom built"
al 0), or it is created and the units have nothing it overlaps (their own perception phantom `0x9793F0`, key
`0x4934AE2`, shape = the entity's box `0x588360`, base filter `0x5BCDC0`, not built or on a layer the ring's phantom does
not see). The service is reached through interface `{a8736401-f95c-4314-bc1d-2ac35a6a393c}` (`0x1601B70`,
`0xAFDE60`); its create is vt+0x18, found only at run time. Not settled statically.

### 1.3 Diag (`tools\diag.py --ring`, new probes)
| RVA | Line | Reading |
|---|---|---|
| 0x62AAF6 | `phantom create call` | create_fn = the implementation VA (decompile it next), turret IID |
| 0x62AAF8 | `phantom create result` | h0..h3 equal to null0 / null2 = refused |
| 0x57978F | `unit perception phantom created` | per unit: h = null = the unit has no phantom for the ring to see |

**The diag must be started in the menu, before Launch** (the usage text says so now).

## 2. The strip by the fence (item 2)

### 2.1 The occluder pass is not the cause (C for the pass, P for the strip)
- `InfiniteCrisis_patched.exe` holds `e9 41 01 00 00 90 ..` at 0x6AD624 (read back): every source jumps to 0xAAE36A.
  `0xAAE0E0` then only resets the collector (`0xAA97B0` -> `0xAA5170`: an **octagon** of the radius, 8 vertices with
  flag 1) and stores it: no source's polygon is clipped by any body. The strip is still black.
- Already in fase3-io AGL's own pass was skipped (al 1 from 21:05:00) and the strip stayed, while Batman (`83.webp`,
  ~7 m away, radius 12, octagon inner radius 11.1 m) covers it. So the region is not a missing or clipped circle.
- The fog occluder patch did nothing for the strip. It is harmless (the server's own fog still hides enemies behind
  walls); `[game] exe_patch_skip = ["fog occluder pass"]` restores the original bytes (then the ground behind walls is
  dark again). Kept: whether it is what removed the black wedge between AGL and a lifted vehicle (`57.webp`) is O.

### 2.2 The fog's base bake is uniform (C, data + code)
`RenderFogScene 0xAAE5B0` bakes per texel `[comp+0xDC] * (1 - R)` where R = `0x586140(pos, 0x10000002)`: the hash
`0x1B67B90` (filled at landblock load by `0x586B00` from property **0x84A** of the landblock's statics record) gives the
block's terrain maps; each entry: `0x847` origin, `0x848` extents, `0x846` layer id, `0x849` image DID (`0x5851B0`
samples it: format 0x1C A8, 0x15 / 0x16 A8R8G8B8 via `0x584FC0`, R = bits 16-23; texel (u * w, (h - 1) - v * (h - 1))).
13BB (`0x820113BB`): three maps over (0, 0, 200) + 160 x 160 x 160: `0x10000002` -> **`0x3E00000D`** (64 x 64), 
`0x10000001` -> `0x3E000010` (256 x 256), `0x10000003` -> `0x3E000012` (128 x 128), all in `0xA00002E5`.
`0x3E00000D` has **R = G = B = 0 in all 4096 texels** (A 220-255): v = 1 everywhere, nothing is baked dark.
The landblock info `0x810113BB` (256 x 256 DXT1) is red in all texels (14 at 246 instead of 255): not a mask either.

### 2.3 What is left (P / O)
- The compose: `RenderFogEntities 0xAAB3B0` clears to white `0x18706E8` and draws each source as a fan from its centre
  with vertex colours `0x18706C8` (0, 1, 0, 1) for vertices on the circle and `0x18706D8` (1, 0, 0, 1) for clipped
  ones; with the patch every vertex is on the circle.
- The strip's west edge is a ray from the lane turret's spot (~40 deg, `ca-black-strips.md` 4); the octagon's vertex
  rays are at 0, 45, 90 ... deg, so it may be the turret's 0-45 deg fan triangle (P weak: 5 deg off, and Batman's fan
  covers the same ground). Other candidates: a light at the turret casting a shadow with almost no ambient light
  (the match lighting key `0x956` is the cinematic one, `map-loading-deep-scan.md` 4), or a geometry hole.
- `tools\diag.py --nofog` (EXPERIMENT, running memory only) sets WorldRender +0x36 EnableFog = 0 and the fog clear
  colour `0x1B76958` (4 f32, zero in .bss) to (0, 1, 0, 1) on the first fog render: the fog texture becomes one flat
  value. Strip still black = not the fog. `--fogpoly` prints every source's polygon in metres (centre, vertices, `c` =
  clipped) once per 4 s.

## 3. Tests
`tests/test_match.py` `ring_phantom_strip` (4 checks): 0x820113BB's map for layer 0x10000002 is 0x3E00000D, its red
channel is 0 everywhere, the new probes sit on instruction starts of the installed exe, diag has them.

## 4. Tester (no `python ic.py patch` needed; nothing in the exe changed)
1. Open the game and stay in the menu. Second console: `python tools\diag.py --ring --fogpoly`. Then Crime Alley v
   AI. Walk to the enemy lane turret (x 95) once with our wave under it and once alone. Send `logs\diag.log`,
   `server.log`, `traffic.log`.
2. Then (game still open, after the first diag is stopped with Ctrl+C): `python tools\diag.py --nofog`, stand where
   `83.webp` was taken (east of our lane turret, between the lane and the fence), screenshot. Strip still black = not
   the fog; send the screenshot.
