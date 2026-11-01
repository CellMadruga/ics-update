# Crime Alley: the black strip belongs to the statics' draw; which one, and the floating nook pad (2026-10-30)

Tester report 2026-10-30 13:18 (build fase3-ir + later; run 13:05-13:18, Crime Alley v AI, AGL vs AI Zod). Evidence:
the run's `server.log` / `traffic.log` / `diag.log` (`diag --layers`, three passes 12:59-13:10), the tester's words
"the black strip DISAPPEARED during step 2/12: DrawStaticEntities (WorldRender +0x3b) OFF for 5 s, and only then" and
"the pad where the Raider appears looks separated from the ground, floating", the decompiled client
(`re-work/decomp`, VA = static address; file offset = VA - 0x400C00 in .text), capstone reads of `InfiniteCrisis.exe`,
the installed packs (`0xA0C112BA`, `0xA00002E5/E6/E7`, read only). Tags: **C** confirmed, **P** probable, **O** open.
Builds on `ca-ring-bodies-strip-layers.md` (the strip's rectangle, the `--layers` experiment), `ca-black-strips.md`,
`ca-street-occluder-ring.md`.

## 1. What the `--layers` answer says (C log, P reading)

- Step 2 (DrawStaticEntities off, 13:09:59) removed the strip; step 4 (DrawOpaqueEntities off) and step 5
  (DrawTranslucentEntities off) did **not**, nor did landscape, frills, cell meshes, floor, the three fogs (tester).
- A static **surface** drawn black would be opaque or translucent and would have gone in step 4 or 5. So the black is
  P not a static's own mesh but something the statics feed into another pass: their **shadows** (the shadow-casters
  pass `0x761320` "RenderShadowCasters" draws nodes with flag 0x400; the opaque toggle does not reach it), a
  depth-based term (**SSAO**, `Render.EnableSSAO`), **reflections**, **decals** or **lights** owned by statics.
- The shape fits a directional shadow (P): a parallelogram whose two side edges are parallel (36-47 deg), top on the
  fence base y 83.4, bottom cut by the lane mesh y 81.8; both lighting environments in the pack carry the same
  angles 200 / 140 at +0x20 / +0x24 (`0x08000003`, `0x08000016`; P sun heading / pitch, i.e. ~40 deg elevation,
  which gives the >= 2.6 m reach of a 2.2 m fence). The mirror side by the chain-link fence is dim, not black
  (`ca-ring-bodies-strip-layers.md` 2.1): a see-through caster.
- Against it (C data): no map static near the strip has the **cast-shadows property 0x4A8**: RenderComponent's
  property switch `0x624500`, case 0x4A8 -> component flag 0x20 (`0x6249F8`) -> node flag **0x400** (`0x624A2F`
  `push 0x400; call 0x77DF70`), the flag the shadow casters pass needs (`0x761320`: `(node+0x220 & 2) == 0 &&
  (node+0x220 & 0x400)`). In block 13BB only the 11 point lights `0x2E000011` list it; the fences `0x2E001324`,
  `0x2E0012F6`, `0x2E0004D7`, `0x2E00097C` and the lamp `0x2E001219` do not. The server's **stealth tiles** do
  (`0x2E000D36` / `0x2E000D37`: `0x4A8 = 1`), as do the nook pad `0x2E000D12` and the gate `0x2E000CD7`. Whether a
  missing 0x4A8 means "no shadow" or keeps a default on is O (the component's initial flags were not read).
- Ruled out by data (C): no static's box other than the whole-map pieces covers the strip's interior.
  `0x2E001207` (the "street") has no render geometry: its `.entity 0x2D000F0F` names gfx `0x1100077A` = param set
  `0x19001160` only; its shape `0x10001649` (pack `0xA00002E5`) is a 228-vertex / 444-triangle collision mesh
  (+ MOPP) whose only faces near the strip are the 4 m block north of y 83.4 (top 203.97 m). `0x2E001185` (whole
  map, z 190.1-200.1) is a skeleton plus gfx `0x1100076C` without geometry (rain particles, texture `0x1300062F`).
  The four fence pieces' boxes reach only y 83.24-83.37 (the strip's top 0.15 m).

## 2. The experiment (`tools\diag.py --strip`, Spanish `--franja`; running memory only)

How the client hides one object (C code): a model node attaches through `0x781640`, which calls RenderComponent
`0x6226E0` at **`0x78165C`** with ecx = the component (node +0x264) and esi = the node; the component keeps it at
**+0xA0**, its entity at +4 (IID q[ent+0x100], world state [ent+0x110]). The visibility path (`0x624D1E`: 0x2A1 /
0x76A / 0x90F) sets node **+0x220 bit 0x800** through `0x77DF70` (`0x624D67`); the draw / list passes skip such
a node (e.g. the render list builder that jumps to `0x7560AD`). The diag records every 13BB static's component while the map loads and,
in the match, flips that bit itself.

Graphics settings: registered by `0x7C55E0` as globals (static VA): `Render.ShadowMapQuality` **0x1865744** (u32; the
shadow pass `0x794280` tests it at `0x7942B5` and skips with 0), `EnableSSAO` 0x1865778, `SurfaceReflections`
0x18656D8, `EnableDecals` 0x186575A, `EnableNonGlobalLights` 0x1865758, `EnableUniqueLights` 0x1865759,
`MinSizeToHaveShadows` 0x1865748 (f32), `DeferredRenderer` 0x18656BC (shadows need it). The tester's
`UserPreferences.ini` has ShadowMapQuality=2, EnableSSAO=True, SurfaceReflections=UltraHigh, EnableDecals=True.

Steps (5 s each, from 10 s after the first match frame; the cycle repeats every ~2.5 min; each one logged as
`STRIP cycle n step k/26`):

| Steps | What is off / hidden | If the strip goes |
|---|---|---|
| 1-6 | ShadowMapQuality 0, SSAO, reflections, decals, non-global lights, unique lights | that effect draws it |
| 7 | every 13BB static (control: must look like DrawStaticEntities off) | it is a 13BB static (if not: a server object or another block) |
| 8-12 | the 4 fence pieces together, then `#0x24C`, `#0x246`, `#0x243`, `#0xD7` alone | that fence (its shadow, P) |
| 13-15 | street collision piece `#0xB8`, rain volume `#0xBB`, lamp `#0x11E` | that piece |
| 16 | the server's 16 stealth tiles (cast shadows, 0x4A8 = 1) | the tiles' shadow |
| 17-26 | "bit b": the 13BB statics whose entry index has bit b set (b = 0..9) | the culprit's index = sum of 2^b over the bits whose step cleared the strip (one culprit) |

## 3. The nook pad floated (C, fixed)

- The pad is the Power Relay `0x4000089D` (world state `0x2E000D12`, `.entity 0x2D000ADC` in `0xA00002E6`): its
  box is (-3.42, -3.70, **0**) .. (3.43, 3.28, **0.092**): a 9.2 cm plate whose model starts at its origin.
- `_spawn_nook` sent it at the map's z **200.3** (`maps.py` "z"). The terrain at (80, 95-100) is **199.98 m** flat
  (`0x800113BB`), no static floor there (the street collision mesh has no face over the nook), the navmesh is
  200.08, the markers `0x2E000944` / `945` are at 200.085. So the plate floated 0.32 m over the ground.
- Fix: `[ics] match_nook_pad_z = 199.98` (the plate's top at 200.07 = the walk height); 0 = the map's z as before.

## 4. Tests

`tests/test_match.py` `strip_static_shadow_pad` (5 checks): the attach call / 0x800 / 0x400 / shadow-quality bytes in
the installed exe, diag `--strip` probes and steps, no 0x4A8 on the fences and the lamp but on the stealth tiles, the
terrain and the pad's box at the nook, the pad spawned at 199.98.

## 5. Tester (no `python ic.py patch`: nothing in the exe or the packs changed)

1. Game in the menu (before Launch), second console: `python tools\diag.py --strip` (or `--franja`).
2. Crime Alley v AI; stand where the strip shows (between the lane and the fence, x ~78, y ~82.5), do not move the
   camera; record the screen for one full cycle (~2.5 minutes from the first STRIP step line).
3. Send the recording (or the times at which the strip disappeared) and `logs\diag.log`, `server.log`.
4. Look at the Raider's pad: it should lie on the ground now.

Next (O): with the answer, the fix is either a pack patch that drops the static's entry (statics record
`0x820113BB`, entry type 7 -> 3, the loader `0x548550` creates only types 7 / 8 / 0x15; a terrainfix-style site with
backup and CRC) if it is a map static drawn by its own pass, the 0x4A8 / shadow handling if it is a shadow, or the
server's own object if it is a stealth tile.
