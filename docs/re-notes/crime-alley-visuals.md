# Crime Alley visuals: stealth brush, nook plate, lava decoration, dampener plate, base gate (2026-10-24)

Work in progress (written incrementally). Context: tester report 2026-10-24 after the 23:48 session
(`logs/traffic.log`). Tags: C = read in the data / code, P = probable, G = guessed, O = open.

## What our server sent in the 23:48 session (C, traffic.log)

- Stealth strips: 6 x class = world state `0x2E000D36` (bare world state), 0xBC `0x50F = 8`, module 0x62 1 1,
  positions from `ics/match/maps.py` "stealth"; then scriptlet Vfx_Active. Seen in our recording as a white "+".
- Base gates: Door `0x40000557` at (29.5, 77.5) / (130.5, 77.5), 0xBC `0x50F = 8`, `0x1000009C` team; Object_Closed
  ~8 s later, Object_Open at the match start, then destroyed (0x3).
- Dampeners `0x40000C88` / `0x40000C87` at (40, 77.5) / (120, 77.5).

## (a) Stealth brush records (C unless tagged)

- Two "Hotspot Object" entity classes carry the stealth brush, both in the sent pack `0xA00002E6` (also `0xA00000FC`):
  - `0x4000039D` (template `0x4900039D`): `0x7D2 = [0x1D0000D0]` (target-mark Vfx table), `0x10000623 = 1`,
    `0x7EB = 0x15`, `0x31 = (2, 1, 3)`, `0x100000EE = 7`, `0x100001ED = 0x3012C`, `0x50F = 8`, `0x149 = 0x81`,
    `0x10000AA7 = 1`, name "Hotspot Object", `0x510 = 0x2E000D36`, `0xEF = 0x3A000010`, `0x100006FB = 1`,
    `0x1000009C` (empty), **`0x100002C4 = 0x4800028C`** (the hotspot's inside status = stealth brush), `0x402` with
    `0x4BB = (-2, -1, -1)` (box min; with `0x31` as max: a 4 x 2 x 4 m box centred on x), `0x1000019D = 0x2000`,
    `0x10000017 = 1`, collision polygon `0x57A` (8 points).
  - `0x40000405` (template `0x49000405`): the same except `0x31 = (0, 1, 3)`, `0x4BB = (-4.5, -1, -1)` (a 4.5 x 2 m
    box anchored at its +x end), `0x510 = 0x2E000D40`.
- World states: `0x2E000D36` (.entity `0x2D000AFC` = Havok box (-2,-1,-1)..(2,1,3), no mesh; `0x7D2 = [0x1D000509]`,
  `0x7EB = 7`, `0x769 = 3`, `0x50F = 3`) and `0x2E000D40` (.entity `0x2D000B01`, table `0x1D00050B`, same props).
  Neither has a renderable part of its own.
- Tables `0x1D000509` / `0x1D00050B` both hold keys `0x5` and Vfx_Active. Vfx_Active = three actions: type 0x12
  particle `0x18000A57` (floats 40 / 60), type 0x21 hash `0x3A0741AD` (P sound event), type 0x26/0x27 child world
  state **`0x2E000D37`** (ctype 5, .entity `0x2D000AFD` = the hex mesh) with 0.25 x 4 floats. Differences:
  `0x1D000509`'s particle action has the extra property `0x7E6 = 1` (seen elsewhere on long-running / persistent
  actions; P = keep running), `0x1D00050B` has none; `0x1D00050B` adds -2.1 to one coordinate of both the particle and
  the child (P: x offset that centres the visual on the 4.5 m box that ends at x = 0).
- `0x2E000D37` is referenced only by these two tables (byte scan of all packs): the hex tile can only appear through
  Vfx_Active, so the original also played it.
- Our recording (frame 80 s) shows the hex tile plus tall vertical light streaks and a white "+" at each tile centre;
  the original (frames 86 / 150 s) shows only the flat hex tile. The streaks / "+" are P the particle `0x18000A57`
  kept alive by `0x7E6 = 1` in `0x1D000509`.

## (e) Base gate invisible: the wall's colour needs the side property (C)

- Door `0x40000557` / ws `0x2E000CD7` (table `0x1D000461`, base `0x1D000385`). Object_Closed (`0x1000034F`) =
  action 0x0C child `0x2E000CD8` (the wall; ctype 9, .entity `0x2D000AAA`, table `0x1D00038B`) + Vfx_Startup
  (`0x1000018E`) on it, then type-0x16 switches on **property `0x100007A2` (side)** of the door: value 3 -> child +
  Vfx_Active_Blue (`0x100007F6`), 5 -> Vfx_Active_Red (`0x100007F2`), 1 -> Vfx_Active_Purple (`0x10000D86`), each
  with its light colour (ff00beff blue, fffa3c3c red, ff805dff purple). The wall table `0x1D00038B`'s Vfx_Startup and
  Vfx_TeamColor_SetParentColor switch on `0x100007A2` too (values 1, 3, 4, 5, 6).
- traffic.log 23:48:48: the gates are sent with `0x50F = 8` and `0x1000009C` only; `World.spawn` keeps `side` on the
  entity but never sends `0x100007A2` for props (only `ics/match/units.py` sends it for structures). No branch
  matches, so the wall is created but never lit: invisible.
- Fix: gate extra prop `(0x100007A2, KIND_ENUM, 3)` for team 1 and `5` for team 2 (the layout convention, maps-complete.md;
  Tutorial 2's BaseGate actor has side 3), in the creation table, then Vfx_OnInit + Object_Closed as now.
- Recipe (P): spawn the **entity** `0x4000039D` (its template brings `0x50F = 8`, `0x100002C4 = 0x4800028C`,
  `0x1000019D = 0x2000`, `0x149 = 0x81`, the box and `0x7D2 = [0x1D0000D0]`) instead of the bare world state, with the
  movement module, then Vfx_Active (`0x100000EB`). If the streaks / "+" stay (G): use `0x40000405` (ws `0x2E000D40`,
  table `0x1D00050B` without `0x7E6`), placed 2.1 m along the tile's local +x from the wanted centre so the -2.1 offset
  lands the hex mesh on it. Keep `0x1000009C` unset (neutral brush).

## (b) Middle-camp nook plate (P)

- Statics `0x820113BB` at the nook: type-3 server-object markers `0x2E000944` + `0x2E000945` at **(80.0, 97.25,
  200.08) yaw 180**, and `0x2E001117` / `0x2E001120` at (79.96, 97.13) (C). None of the four records exists in any
  installed pack (C), so the client draws nothing there: a server object stood on the marker. The same 944 / 945 pair
  marks five objective spots in map `0xA0C122E2` (e.g. (80, 145), (44.5, 90.5), (115.5, 90.5), (80, 9), (80, 57)) (C).
- Crime Alley objective classes in the sent pack `0xA00002E6` (names from the templates, C): "Environment" superpad
  **`0x40000CB5`** (ws `0x2E001314`, ctype 8, table `0x1D0008FA`: Vfx_Active_Pad / _Health / _Speed / _Sheild / _EMP /
  _Fireball / _SurveillanceCamera / _SurveillanceTurret; PerceivedType `0x20040`; units-and-ai.md lists it for CA and
  GD), "Generator - Health Pack" `0x40000180` (ws `0x2E00054B`, spawns `0x40000182`), "Speed Emitter" `0x40000C4C`
  (ws `0x2E000E38`; spawned only by the skill script `0x34000671`, so not map scenery), "Power Relay" `0x4000089D`
  (ws `0x2E000D12`, perceived `0x80200`).
- Reading (P): the round plate with the spiral emblem and padlock = superpad `0x40000CB5` in its locked state.
  Recipe: spawn `0x40000CB5` at (80.0, 97.25), yaw 180, `0x100007A2` unset (neutral), module + `0x50F` as a prop; play
  Vfx_Active_Pad (G which key shows the idle/locked plate; try Vfx_Active_Pad first).

## (c) Lava cracks, ember craters, red rubble (O / G)

- Landblock info `0x810113BB` (map pack `0xA0C112BA` +0x4051068) is a 256 x 256 DXT1 texture `0x1300274E` (red 565
  mask); terrain `0x800113BB` names textures `0x13002742`-`0x13003426`; all are in sent packs (C). Nothing in the
  terrain / statics is missing, so the orange glow is not a missing pack (P).
- Crater world state **`0x2E0004BE`** (.entity `0x2D000375`, ctype 9, table `0x1D000155` Vfx_Active) is in the sent
  CA pack `0xA00002E5` (C). It is used as a child of ImpactPoint `0x2E001253` (table `0x1D000845`: Vfx_Active,
  Cinematic_Intro, `_CEntitySystem_EnvironmentStateChange`; Tutorial 2 beat `0x35000030`) and by the "Crater1/3"
  actors of Tutorial 2. No Crime Alley record places it (C). Substitute (G): spawn `0x2E0004BE` (0xBC `0x50F = 8`,
  module) + Vfx_Active at the frame positions (68.6, 80.5), (71.4, 79.6), (70.7, 75.7), (89.9, 80.7) and mirrors.
- The long orange cracks have no record candidate (O): P part of the original's lighting/terrain state (the original
  is also darker and blue-tinted).
- Red rubble (G): "Rock" `0x400005C9` (ws `0x2E000D22`, ctype 7, throwable: Vfx_PickUp / Vfx_OnThrown, children
  `0x2E000D13` / `0x2E000D14` with the team-colour table `0x1D00038B` -> red glow) in `0xA00002E6`; no static marker at
  (80.1, 72.8), (54.7, 82.9), (105.0, 82.7).

## (d) Dampener black octagon (P)

- ws `0x2E000E04` (.entity `0x2D000BAF`, ctype 3 -> 8 as entity): graph `0x5B5 = 0x1C0000A0`, props `0x8A5 = 1.0`,
  `0x8B2 = 12`, `0x8A3 = 2.0`, `0x83C = 1`, `0x8C1 = 1`, `0x83E = 1`, an inline shader `0x1500E9B1` (C). The ~12 m
  black octagon matches `0x8B2 = 12` (P: the field projection drawn unlit).
- Table `0x1D0005A1`: Object_Activate (`0x10000CCE`) = type-0x14 graph action + Vfx_Active; Object_Deactivate
  (`0x10000CCD`) (C). traffic.log 23:48: the dampener gets **no scriptlet at all** (the turret head gets Vfx_Startup +
  Vfx_Active_Blue). Recipe: Object_Activate then Vfx_Active on each dampener ~0.3 s after spawn (it already carries
  `0x100007A2` = 3 / 5); heading from the marker `0x2E0011A9` (40, 77.5) yaw -90 / `0x2E0011A8` (120, 77.5) yaw 90.
