# Crime Alley: the fence strip's fog attribute, the jungle-mouth fields on the drawn walls, the hover pick (2026-10-29, fase3-im)

Tester report 2026-10-29 18:31 (Crime Alley v AI, AGL vs bot Batman, match 18:32-18:46): (1) "the section that is black
is still missing" (the north strip by the fence, x 70-76, y 81.5-83.1); (2) "the stealth zones at both ends are still
too far from the edge; their edge must sit against the collision of the central zone"; (3) "hovering enemy minions and
champions draws no click area, several clicks are needed to be sure it attacks". Evidence: `logs/server.log` and
`logs/traffic.log` of that run, the decompiled client (`re-work/decomp`, image base 0x400000), the exe's .data read
directly, the statics of `0x820113BB` (`stealth-alignment.md` 3). Tags: **C** confirmed (code / data / bytes), **P**
probable, **O** open. Builds on `ca-fog-ring-announcer.md` 1, `ca-black-strips.md` 4, `stealth-alignment.md`,
`gh-freeze-holes-picking.md` P.

## 1. The fence strip: the fase3-il modifier never applied (C)

- Traffic 18:32:12.181 / 18:32:13.283-.292: the 0x20F0 modifiers `0x100008CE op 6 = True` went to AGL, core t1, both
  t1 turrets and the foundry, as designed. The strip stayed black.
- The occluder pass is skipped when `0x974940(source, &IID, &0x100008CE, 0)` is true (`0xAAE0E0`; dword `0x16088E0` =
  0x100008CE, C exe). `0x974940` -> unit component `[ent+0x84]` -> **`0x973730`**: it maps the id (`0x96F4F0`), asks
  the component's vt+0x60 for the **base value**, and only if one exists (`0x450800`) walks the own modifier hash
  (`[comp+0x14]`, `[comp+0x1C]`) or the per-team table and stacks them (`0x96D460`); with no base value it returns
  the default (`param_3` = 0). vt+0x60 of the unit component vtables `0x1609B78` and its base `0x15F9858` is
  **`0x970B80`** = `0x58B1C0(entity, id)`: the entity's own property (bundle / 0x6 / template), by kind (C).
- No champion, turret, core or minion template has 0x100008CE (only the foundries `0x4000016F` / `0x40000170` and a
  few 0x49 classes; `ca-fog-ring-announcer.md` 1.1), so every read returned false and the pass ran as before (C).
  The descriptor is networked (`properties-complete.tsv`: net 1, NetSharedVisually), so a 0x6 set reaches the store
  that `0x58B1C0` reads (P-strong: the same path carries the targetable tags 0x10000029 / 0x10000249).
- Fix: `World.see_through_blockers` also sends **0x6 `0x100008CE = true`** before the modifier (`[ics]
  vision_through_blockers_property`, true). test_match `fog_ring_announcer` checks the property and its order.
- The mechanism of the black itself (the region between a source and a blocker, `ca-fog-ring-announcer.md` 1.2)
  stays P; if the strip is still black with the property, the next step is `python tools\diag.py --fog` and a break
  at `0xAAE1F0` (`local_11`, the attribute's result) (O).

## 2. Jungle-mouth fields on the drawn walls (C geometry)

- fase3-if put the L's long edges on the **navmesh faces** (champion rim + 0.525 m): west side x 52.725, east side
  x 107.075 (`stealth-alignment.md` 2). The drawn walls stand elsewhere (statics, `stealth-alignment.md` 3, C):
  west brick corner pillars 580 / 536 at x 53.30 / 53.36 with local x +-0.40 (face **x 52.90**; side fence 576
  52.92); east chain-link side panel 472 at x 106.85, box half 0.1 (face **x 106.95**); east garden panels 467 / 466 /
  465 at yaw 67 (centre line through (106.85, 85.46) at 157 deg, face 0.10 m to the path side). So the fields stood
  0.18 m (west vertical), 0.35 m (east vertical) and 0.37 m (east diagonal) off the visible wall; the west diagonal
  already lies on the brick fence's pillar line (centre line 23.9 deg + 0.40 m; its edge is 0.22 m north of the
  centre line).
- The hex visual matches the 4 x 2 m box (`stealth-alignment.md` 4.1: near edge within 0.03 m, lateral 0.1 m; the
  hex child `0x2D000AFD` is one 0.6 x 1.46 x 1.37 m hex prism, inline mesh format 0x2205102, 228 vertices, scaled by
  the Vfx_Active child action, C).
- Placement (`maps.py` "render" per tile, `[ics] match_stealth_render_faces` true): west vertical **(51.9, 85.2)**
  yaw 90 (edge x 52.90), east vertical **(107.95, 85.2)** yaw 90 (edge x 106.95), east diagonal **(105.66, 87.16)**
  yaw 157 (edge on the chain-link face), west diagonal unchanged (54.2, 87.5) yaw 23. Both vertical tiles still start
  at their garden corner (0.19 / 0.15 m from the navmesh corner). Not mirrored any more about x 80 (the two mouths
  are built differently: brick vs chain link). The hide area (`inside_strip`, +0.5 m) keeps every test point.
- false = the fase3-if positions; `maps.py` "stealth_render_faces" lists the three face lines; test_match checks the
  edges on them (<= 0.03 m), the moves (0.15-0.4 m), the corners, the hide points and the old layout with the key off.

## 3. Hover outline and the right click (C mechanism, P cause, O runtime)

### 3.1 How the outline is drawn (C)
- The selection tick **`0xA88700`** ("gmSelectionSystem") calls `0xA81B30(champion, slot, 1)` (call at `0xA8877F`)
  and `0xA168F0` writes the result's IID into the local champion's **0x3CB**. Listener `0xA5D5F0` case 0x3CB ->
  **`0xA4EDD0(target)`**: `0xA1D020` gives the colour (hover = **(0, 1, 0, 1)** at `0x186D9D8`, read from .data;
  locked / selected `0x186D9C8` / `0x186D9B8`) only when the target is alive (`0x96E9C0(t, 4) == 4`) and is the 0x3CB
  unit; then client properties 0x974 = 1 / 0x973 colour / 0x975 kind; the render listener `0x625250` case 0x974 ->
  `0x61EC00(0, 8, on)` marks every render part. No team, relation or server property gates it: **the outline shows
  exactly when the hover pick returns the unit**, and the right click uses the same pick (`0xA86A42`).
- Candidates (`0xA81B30`): the render ray (`0x75D150`, filter `0xA0E120`: not hidden 0x800 / 0x8000, drawn this
  frame, alpha > 0.0002, model flag 0x100 clear and render flag 0x400 clear, or model flag 0x80) -> flags 1, priority
  3; a +-0.8 m box swept along the ray against the collision parts -> flags 2, priority by part type (0/2/6/8 -> 1,
  1/3/5/7 -> 2, 4 -> 3). A candidate is scored (`0xA16A60`) only if its priority >= the best one so far; the
  highest score wins, ties by distance.
- Scores (`0xA16A60`, C): needs 0x2A1 and the validator; own champion **5 + 0x100001C3 / 10**; another unit 15
  (**5 when it was hit by the render ray only**, flags 1 without 2) + relation (enemy +2, enemy Character +4, ally
  Character +3, neutral +1) + 0x100001C3 / 10. Lane drone 0x1C3 = 30, champions 40: enemy drone 20 (box) / 10 (ray
  only), allied drone 18 (box) / 8, own champion 9, enemy champion 23 / 13.

### 3.2 What the client picked in the 18:31 run (C traffic)
- 0x20EE orders: 1 463 move orders (command 4): **1 356 with no pick and 107 with a pick**: our own champion
  `0x0200000000000002` (53), the allied turret 0x109 (7) and allied minions (`mid ranged 4 t1 w23`, `mid melee 2 t1
  w15`, `mid siege 5 t1 w9`, ...; 47). 463 attack orders (command 2 with a target), 159 of them on the bot Batman.
- With the scores above an allied drone (18) or our champion (9) can only beat an enemy drone that is not in the
  box sweep (ray only, 10, or not a candidate at all): the enemies are picked by their thin render mesh alone, the
  allies and our champion by the box as well (P). Why the box misses the enemies is **O** (the swept query goes
  through the service `0x1601364` vt+0x20 into a result list of 0x98-byte parts, part type at +0x88; its source of
  parts is not identified).
- Ruled out (C): the PerceivedType-gated components (`0x1000019D` is in both templates: drone 0x40000BF8 [8, 0x10000],
  Batman 0x40000280 [8], so `+0x80` / `+0x90` / `+0xA8` / `+0xC0` exist from construction); `0x100004A4` (in neither
  template); the vitals component's LifeState (constructor 4); the fog step of the validator (`0x5534A0` = 1); team /
  relation in the outline; the allied and enemy drones' creation bundles are identical but for team and side.

### 3.3 Changes
- `[ics] click_assist_radius` `{"unit": 1.0, "champion": 1.4}` (`Session._click_assist`): a move order whose pick was
  none / our champion / an ally and whose ground point lies within that radius of a visible enemy unit / champion
  (not hidden by the fog or a stealth field) attacks the nearest one; `{}` = off. This fixes the "several clicks";
  the outline still needs the client's pick (O).
- `tools\diag.py --hover` (`--raton`): breaks after the tick's pick (`0xA88784`: entity, IID) and after each
  candidate's score (`0xA82299`: IID, entity, flags, priority, best priority so far, score as f32 bits), one line per
  change (`tools/tracer.py` "HOVER:" lines). Hover an enemy drone, an allied drone and Batman: an enemy with flags 1
  only (never 2) confirms 3.2; no line for the enemy = the render filter refused it too.

## 4. Tester should see

1. No black strip by the fence east of the blue turret (with 1). If it stays: `python tools\diag.py --fog`.
2. The four jungle-mouth fields touching the pillars / chain link of the central gardens.
3. A right click within ~1 m of an enemy drone (1.4 m of the enemy champion) attacks it at the first click; the
   hover outline is unchanged until `diag --hover` shows why the box sweep misses the enemies.
