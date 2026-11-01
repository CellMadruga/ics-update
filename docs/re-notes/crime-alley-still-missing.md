# Crime Alley: what is still missing or wrong after fase3-hr (2026-10-25)

Work in progress (written incrementally). Sources: our recording `2026-10-25 11-27-25.mp4` (Crime Alley 0-225 s,
then Gotham Heights), the original `crime_alley_map_video.mp4` and the Clash 2v2 `videoplayback.mp4`; frames in the
scratchpad only. Tags: C = read in data / logs / clearly on frames, P = probable, G = guessed, O = open.
Previous notes: crime-alley-video-compare.md, crime-alley-visuals.md, crime-alley-2v2-video.md.

## 1. Stealth tiles: orientation is inverted (C frames + traffic.log)

- traffic.log 11:27:05: strips 0-3 (centre, map yaw 90) sent with heading `db 0f 49 40` = pi, strips 4-5 (jungle
  mouths, yaw 0) with heading pi/2 (`heading_from_yaw` = yaw + pi/2).
- Our frame 130 s (clock 01:23): the four centre tiles stand with their long side along **y** (screen vertical),
  2 m apart, with vertical light streaks above them. Frame 90 s (camera at the west jungle mouth, minimap x ~49):
  the mouth tile is long along **x** (about 4 m across the opening).
- So the hex mesh does follow the entity heading, but heading pi/2 puts its 4 m side along x. The earlier
  "yaw 0 = long side along y" (fase3-hn, heading 0) is consistent: 0 and pi give the same rectangle.
- Fix (P, high): swap the yaws in `maps.py` "stealth": centre tiles yaw 0 (heading pi/2), mouth tiles yaw 90
  (heading pi); also swap the `ent.half` rule in `match._spawn_stealth` (long side along x when sin(yaw) is ~0).
  Then the north pair (78, 82.3) + (82, 82.3) meets end to end like the original's single 7.2 m strip.
- The vertical streaks / white "+" are still there (particle `0x18000A57` kept by `0x7E6 = 1` in table
  `0x1D000509`); the original shows only the flat tile with a soft purple rim. Recipe (G): class `0x40000405`
  (ws `0x2E000D40`, table `0x1D00050B`, no `0x7E6`), its centre 2.1 m along the tile's local +x from the wanted one.

## 2. Dampener: black octagon still there (C frames 50 s, 110 s)

- traffic.log: Object_Activate at 11:27:12.560 and Vfx_Active at 12.735 were sent to both dampeners; the ~12 m
  black octagon around the x 40 dampener is unchanged (frame 50 s, clock 00:03; frame 110 s at x 120 side).
  So the scriptlets are not the cause.
- Original (frame 82 s): grey segmented ring (~6 m), dark pedestal with red trim, stacked blue hologram, ember
  craters around it, no dark disc at all.
- ws `0x2E000E04` carries the same property group as the crater templates (`0x83C`, `0x8A3`, `0x8A5`, `0x8B1`,
  `0x8B2 = 12`, `0x8C1`; properties.tsv: "sending these hid the crater"), so the octagon is P a 12 m ground
  projector / decal of the dampener drawn without its material. The tester's client has `EnableDecals=True`,
  `DecalPriorityLevel=5` (Documents\InfiniteCrisis\UserPreferences.ini, C), so it is not a quality setting.
  Open: which state/material makes it render (graph `0x1C0000A0`, shader `0x1500E9B1`); test (G) sending
  Object_Deactivate, or Vfx_Stop, to see whether the disc goes; else a config switch to send the dampener with a
  world state whose `.entity` lacks the `0x8B1` group (none found yet).

## 3. Core: no team-colour cylinder (C frames, C traffic)

- Original (Clash intro 1:46, frame 2:30, and vs-AI frame 64 s): a tall blue holographic circuit-pattern cylinder
  around the core and a hologram above it; red for team 2. Ours (frames 12 s of 10-34-37.mp4, 40 s of 11-27-25.mp4):
  bare core model, no cylinder.
- traffic.log: the cores (`0x40000C8A` / `0x40000C89`, ws `0x2E0013EE`) and the core turrets get **no scriptlet**.
  Core table `0x1D00098A` (+ base `0x1D000385`): Vfx_Active (child `0x2E00103B`, `.entity 0x2D000DB0`, team-colour
  table `0x1D00038B`, with `0x7E6 = 1`), Vfx_Startup (switches on `0x100007A2` 1/3/5/6 with particles), Vfx_Active_Blue /
  _Red / _Purple (children `0x2E000CF4`, light colours), Vfx_AI_Active (child `0x2E000AC3`, table `0x1D00035E` =
  a turret-head-like object with Vfx_Startup / Vfx_Targeting), Vfx_Relay_0N_*, Vfx_Indestructible(_Stop).
- Recipe (P): `match_structure_scriptlets["core"] = ["Vfx_Startup", "Vfx_Active", "Vfx_Active_Blue|Red by side"]`
  (as the lane turret head gets), plus `Vfx_AI_Active` on the vs-AI encounters (G). Core turret (ws `0x2E000AC4`,
  table `0x1D00035F`): Vfx_Fade_In + Vfx_Active (G, nothing visible expected).

## 4. Core platform "prow" missing (C frames, O source)

- vs-AI original (frame 64 s): a long arrow-shaped platform piece runs east from the core ring to the gate (x ~22-29,
  y ~75-80) with the core-turret hologram on it. Clash (2v2 video 2:30) has neither prow nor core turret.
  Ours (vs AI): the hologram tower stands on the ring's edge, cobbles between ring and gate.
- No static in the three lists covers it (core statics `0x2E000A3B`, `0x2E001207`, `0x2E0011B7/B8`, `0x2E001185`,
  `0x2E001402`, `0x2E001235`, `0x2E00132F`, marker `0x2E000AF9` (21.75, 77.5) yaw -90). P: it belongs to the vs-AI
  core turret (a model / child the server should spawn); candidates to try: the core's Vfx_AI_Active child
  `0x2E000AC3` (G) or a plain prop of `0x2E000AC3` at the marker `0x2E000AF9` (21.75, 77.5) yaw -90 (G).

## 5. Lighting: now matches (C)

- Ground mean BGR at the map centre: original 150 s (70, 57, 56), ours 130 s (69, 55, 53); same blue-grey night.
  Lighting key `0x10000002` (fase3-hp) did it. Nothing left here.

## 6. Dampener octagon is our bug (C)

- The Clash dampeners `0x40000C91` / `0x40000C95` use the same ws `0x2E000E04`; the Clash video (2:30, x 40 ring at
  the right edge) shows no dark disc. So the original drew the same object without it.
- The `0x8A5 / 0x8A3 / 0x8B2` group is also on the Tutorial 1 crater template `0x1D0008B6`; fase3-db/dc sent it with
  the crater and the crater vanished and the minimap pings stopped (CHANGELOG): the group touches the fog / minimap
  layer (P). Reading (P): the 12 m octagon is a fog / vision field of the dampener drawn for the wrong relation.
  Tests (G, one at a time): `0x6` set property on the dampener `0x8B2 = 0`, or `0x8A5 = 0.0`; send
  `_Entity_OnSetClientRelationship`; Object_Deactivate.

## 7. Red-orb rubble rocks (C frames, G positions, P identity)

- Not in ours anywhere (frames 60-220 s). Positions differ by mode, so the original server spawned them:
  vs AI: (80.1, 72.8), (54.7, 82.9), (105.0, 82.7); Clash: ~(69.3, 72.7) east of the x 65 turret (2v2 15:56),
  P mirror (90.7, 72.7), and ~(84, 93.5) beside the nook pad (2v2 7:17). About 1.5 m, rubble with a glowing red orb.
- Candidate (G): "Rock" `0x400005C9` (ws `0x2E000D22`, pack `0xA0000162`, team-colour children `0x2E000D13/14`),
  a throwable for Super Strength. Spawn as a prop with `0x100007A2 = 5` (red) + Vfx_OnInit.

## 8. Lava cracks, ember craters, prow: probably another build of the map (P)

- The Clash 2v2 video (same map) shows **no** lava cracks, no ember craters and no prow (2v2 2:30 gate area, 15:56
  turret, 7:17 nook), exactly like ours; only the vs-AI video has them. Our statics / terrain match the Clash look.
  So the cracks / craters / prow are most likely art of a different client build or mode set-up, not something our
  server forgets. Substitute only if wanted: crater ws `0x2E0004BE` (the Tutorial 1 lava crater, renders in our
  client; CA Tutorial-2 layout has "Crater1" (59.64, 78.57) and "Crater3" (69.81, 77.87)) + Vfx_Active at the
  vs-AI frame spots (68.6, 80.5), (71.4, 79.6), (70.7, 75.7), (89.9, 80.7) and mirrors.

## 9. Jungle-mouth stealth shape (C frames, G numbers)

- Clash 2v2 2:43 (same camera as our 90 s frame): the mouth field runs along the curved curb, long axis ~50 deg
  from +x toward the north-east, centre about 2 m east of ours (~(53.7, 85.5)), with a second leg going south out
  of view (the "L"). The vs-AI video shows the leg along y at x 50.5-53.0 from the fence (y 83.7) north.
  Recipe: mouth tile long along y at (51.7, 85.7) (after the yaw fix: heading pi), plus optional second tile at
  ~(53.7, 87.0) rotated ~50 deg (G).

## 10. Checked and fine now

- Base gate: tall blue wall at x 29.5 during the countdown, removed at 0 (our 20-40 s frames vs Clash 2:30). C.
- Lane turret 65 / 95: gear plate + pedestal + blue / red hologram head, as the original. C.
- Base aura: enter/leave logged; nothing visible to compare. Spawn platform static present. C.
- Lighting / fog: matches (section 5). C.
- Nook pad: not filmed in either of our recordings (O). Our Gotham Heights frames (11-27-25 340-380 s) show the
  superpad family as a round plate with a spiral and corner arrows, the same art as the original's locked nook
  plate (2v2 7:17, plus padlock icon on hover) -> class choice P-good; the padlock / locked look is O.
