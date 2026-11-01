# Units pass through each other; which collision body the client gives a unit (2026-10-30)

Tester report 2026-10-30 13:18 (run 13:05-13:18, Crime Alley v AI): "the minions pass through each other, i.e. they
have no collisions defined, and maybe that's why no indicator (hover outline) shows when the mouse pointer passes over
them". Evidence: the decompiled client (`re-work/decomp`, static VA; diag RVA = VA - 0x400000), capstone reads of
`InfiniteCrisis.exe`, `ics/match/units.py`, a headless Crime Alley match. Tags: **C** confirmed, **P** probable,
**O** open. Builds on `client-movement.md`, `movement-collision-fog-map.md` 1.2, `ca-ring-bodies-strip-layers.md` 1,
`ca-fog-stealth-hover.md` 3, `basic-attack-chase-range.md`.

## 1. Units overlapping: a server matter (C)

- Every remote unit (ics sends wire mode 1 -> remote module 1, `ClientRigidBodyCharacterReplayMovementModule`) is
  placed by the client from the server's states: the sampler `0x609240` / `0x552130` takes the newest state <= t - 0.1 s
  and extrapolates `pos + velocity * dt` (`client-movement.md` 1.3). Nothing in that path resolves contacts between
  two units, so two units the server puts on one spot are drawn on one spot. Separation has to be the server's.
- ics had none: the wave spawns 0.8 m to each side of the lane (`waves.py` `offset`), but chases end on the same point
  and nothing pushed one minion out of another (headless Crime Alley, 100 s after the first wave: 1 894 of 32 832
  minion pairs sampled closer than 0.7 m).

### Fix: `Units.separate` (ics/match/units.py), `[ics] match_unit_separation` (true)
- Every tick, after the AI moved the units, each unit of `match_separation_roles` (minion, camp) is pushed out of every
  body it overlaps. Bodies: other units (half the overlap each), champions / bots and structures (all of it on the
  unit); objectives (capture, relay, beacon, device) are not bodies. A uniform grid (cell = 2 x the largest unit
  radius; a body is entered in every cell from which a unit can touch it) makes it O(n).
- Radii = the attack radii (`World._attack_radius`: a structure's / minion's `match_unit.radius`, champions `[ics]
  attack_body_radius` 0.575 = navmesh agent 0.525 + the client's 0.05), so bodies touch where the reach is counted.
  The client's own radius is `0x5897A0` = model setup radius (CModelComponent `entity+0x18` -> `+0x10` -> f32 `+0xB0`)
  x physics scale (`+0x74` = property 0x6B4 x 0x450, set by `0x571950`) + 0.05 (C code); the model setup's `+0xB0`
  comes from the `.entity` asset, which ics does not parse (O), hence the attack radii.
- Against its own target (and a unit targeting it) the distance kept is at most the reach - 0.05: a unit is never
  pushed out of range, so it never walks back in (no oscillation).
- A **walking** unit is moved aside at most `match_separation_push` (0.75) x its step; a push against its walk becomes
  the same amount sideways (a sidestep, to the side it leans to); a state is sent only when the client's dead
  reckoning from the last state is more than `match_separation_resync` (0.4) m off. A **standing** unit at least
  `match_separation_shuffle_min` (0.15) m deep slides to its free spot at its move speed: one start state, one stop
  state facing its target, the slide clamped within its reach of the target; it keeps swinging meanwhile. A camp
  resting at its home spot is not pushed (its data placement). No push ends on an unwalkable navmesh cell (a unit
  already off the mesh may move). Overlaps under `match_separation_slack` (0.05) m are left.
- Headless Crime Alley, same 100 s: 59 of 33 225 pairs under 0.7 m (32 x fewer), 990 movement states against 801 (+24 %),
  the tick took less time (fewer overlapping attackers on one spot).

## 2. Which collision body the client builds for a unit (C code, O runtime)

### 2.1 The movement module builds it (C)
- Module key 1 (replay, vtable `0x15C6360`) attach = vt+0x24 `0x60BAC0` -> `0x60A340` -> **`0x5D1600(entity, physics
  shape)`**: a 0xC0-byte character object (`0x5C6030`, a `hkpContactListener`), stored at module +0x18 / +0x1C. Module
  `0x10000005` (vtable `0x1609708`, attach `0xAAD210`) does the same. Property **0x991** (bool) read there: character
  +0x22 = !0x991.
- When the character has a world (`+0x40`, from the manager's `+0x38` in `0x5D1600` / `0x5C9DD0`) and passes the cell
  test `0x5C9B20`, **`0x5C6320`** builds its rigid body: `0x5C3330` or `0x5C3550` (by +0x23) set world-object type
  **0x200 "Rigid body character"** (mass 100.0) and, when +0x22, a second body of type **0x400** (`0x5C6320` tail).
- Module 9 (vtable `0x15C62A8`, modes 0x41 / 0x4C, `SetEntityFrame`) builds its own type 0x200 body in **`0x60A620`**
  (attach vt+0x24 `0x60B060`; `FUN_0056F230(physics, 0x200)`), unless the entity's destruction component (+0x58) is set
  or the template flag `[phys]+0x64 & 0x400`.
- So a unit's character body depends on the movement module of its 0xB0 block, not on a script: ics already gives every
  unit and champion module 1 (wire mode 1), the same as the local champion. The script collision hold (`0x976990`,
  EnableCollision `0x97D720`, `ca-ring-bodies-strip-layers.md` 1.2) is another body (component +0xB8, key
  `0x4934AE2`), used by missiles; no unit, champion or structure class lists an entity script that would hold it.
- No property, message or script the server could send was found that adds a body a module-1 unit lacks (C for the
  module paths above; O whether `0x5C6320` actually runs for ics's units: the world / cell test is runtime state).

### 2.2 What it means for the hover pick and the turret ring (P)
- The ring's phantom accepts types 8 / 0x200 / 0x800 (mask 0xA08). A module-1 character body is type 0x200, so if the
  champion had it inside the box the overlap-add `0x6385D0` would have logged candidates; in the 12:00 run it logged
  none (`ca-ring-bodies-strip-layers.md` 1.1). P: `0x5C6320` never ran for the champion / units (no world on the
  character, or `0x5C9B20` refused the cell), or the body lives in another physics world than the phantom. The same
  missing body would explain picks by the thin render mesh only (the +-0.8 m box sweep finds no collision part;
  `ca-fog-stealth-hover.md` 3, `gh-freeze-holes-picking.md` P1) and a ring that never meets the champion.
- So the overlapping of minions on screen and the missing outline are two separate things: the first is the server's
  movement (fixed above); the second is the client's body / pick (P: the same body the ring is missing).
- Not changed in this build: no server-side switch was found (no config key).

### 2.3 Diag (`tools\diag.py --ring`, two new probes)
| RVA | Line | Reading |
|---|---|---|
| 0x1D1600 | `character object created (movement module)` | entity IID and the manager's world (`[ecx+0x38]`, 0 = none yet) for every entity whose movement module made a character |
| 0x1C6320 | `character body built (type 0x200)` | entity IID and `flags` (byte 2 set = also a type 0x400 body) when its character rigid body is built |

A "character object" line with no "character body" line for the same IID = that unit never got the body the ring and
the pick sweep would see; then the world / cell test (`0x5C9DD0` / `0x5C9B20`) is the next thing to read.

## 3. Tests
`tests/test_match.py` `unit_separation` (10 checks): five minions spawned on one spot spread to about two radii on the
walkable mesh and then settle (no more states, standing); a five-minion wave on one enemy all reach it, keep apart
around it, hit it, and do not oscillate; minions step off a champion standing on them; `match_unit_separation = false`
leaves them stacked.

### 3.1 Regression after the Power Core Turret parts / platform (2026-10-30, fixed)
"Around the target they keep apart" (gap 0.44) and "no oscillation" (33 states) failed once `match_structure_parts` /
`match_structure_platforms` spawned their props: no new body (props are not separation bodies), but every later entity
id moved by two, and the stacked spread starts from id-seeded directions (golden angle on `eid`). Sweeping an id offset
of -3..+11 on the old code failed in most offsets: the 514/514 run was a lucky id draw. Two real faults:
- the target was shoved by its attackers (half of each overlap, five attackers): it slid away 3 m in 6 s, the wave
  walked after it, states every tick. Now a unit is not pushed by a unit that attacks it (that attacker takes the whole
  overlap; mutual targets half each): `[ics] match_separation_target_holds` (true).
- a minion pinned in a radial line (target in front, a minion behind held at its reach limit) got cancelling pushes
  below `match_separation_shuffle_min` while overlapping both (gap 0.54-0.62). Such a standing unit now steps sideways,
  the deepest single push's size: `[ics] match_separation_unpin` (true).
With both, every offset -3..+11 gives 0 states and gaps 0.70-0.89 (the dead zone itself allows 2 r - 2 x shuffle_min,
so the test's 2 r - 0.3 bound is the design's own floor). false / false = the 13:18 behaviour.

## 4. Open
- O: the `.entity` field behind the model setup radius (`+0xB0`); per-class radii would replace the attack radii.
- O: whether ics's units get the type 0x200 body at all (diag `--ring` probes above), and if not, why (world / cell).
  2026-10-30 15:30: the Position ics sends (cell 0 = the client's own outdoor cell) is ruled out and the build gate
  runs every physics step; see `unit-pick-body-cell-test.md` and `diag --bodytest`.
- O: champions and bots are not pushed (the champion is moved by its own orders; a bot by `bots.py`): only units step
  aside around them.
