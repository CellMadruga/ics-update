# Hover highlight and the units' character body: what the client needs, what ics sends (2026-10-30)

Tester report 2026-10-30 15:30 (run 16:36-17:02, Crime Alley v AI, AGL): "the minions are better now (separation), but
when I pass the cursor over them they are not highlighted, ally or enemy; the one under the pointer should be
highlighted so I can select it to attack it, or see its stats with a left click". Same for champions earlier; the
turret warning ring also never triggers. Evidence: the run's `server.log` / `traffic.log` (no `diag.log` this time),
the decompiled client (`re-work/decomp`, static VA; diag RVA = VA - 0x400000), capstone / byte reads of
`InfiniteCrisis.exe`. Tags: **C** confirmed, **P** probable, **O** open. Follows `unit-separation-pick-body.md` 2,
`vitals-crash-hover-picks.md` 2, `ca-fog-stealth-hover.md` 3, `ca-ring-bodies-strip-layers.md` 1.

## 1. What the run shows (C, traffic)

- 1 336 orders 0x20EE: 1 020 moves with no target, and **orders the client aimed itself**: attack orders (command 2)
  on enemy minions 0x18E-0x27A and the enemy champion 0x100 (193 logged "attack X" without click assist), move orders
  on our champion (36), the allied core 0x101 (30) and allied minions. Only 15 attacks came from `click_assist`.
- So the client's own pick (`0xA81B30`) finds enemy and allied units at a right click (slot 0, `0xA86A00` ->
  `0xA81B30(champion, 0, 1)` -> `0xA168F0` writes 0x3CB). The cursor pick works; what the tester misses is the
  outline, which follows the champion's 0x3CB.

## 2. The character body: every server-side input checked (C code)

### 2.1 Build path
- Movement module 1 attach `0x60BAC0` -> `0x60A340` -> `0x5D1600` (ecx = the physics manager **`0x1B683A0`**) creates
  the character `0x5C6030` {+0x10 entity, +0x14 physics shape, +0x28 the shape's box, **+0x44 its Position**}, gives it
  the manager's world `[0x1B683A0+0x38]` and calls `0x5C9DD0`.
- `0x5C9DD0`: world set and no body yet -> `0x5C9B20(+0x44, +0x28)` (the landblock test) -> `0x5C6320` builds the
  type 0x200 body.
- **`0x5C9DD0` runs for every character on every physics step**: PhysicsWorldManager `0x5D3650` -> `0x5CA0C0` (or
  `0x5CAF30`) per character, first call `0x5C9DD0`. A missing body is retried each step with the character's last
  Position (+0x44). That Position is written only by `0x5C9E90` (snap): at attach when the replay has a state, and by
  the replay step `0x60B5F0` on a newer seq A / B or a jump > 2 m. The module starts with seq bytes = the sentinel
  `[0x1B697F8]`, so its first sampled state (ics: seq A 1) snaps and +0x44 becomes valid (C).
- So, statically: **no body = `0x5C9B20` refuses the character's position on every step** (or the manager has no
  world at all). Nothing else gates it.

### 2.2 The Position ics sends is the client's own form (C)
- `0x5C9B20` -> `0x5BECB0` / `0x5BE910` need region != 0, landblock x / y != 0xFF, cell != 0xFFFF (`[0x185F8A8]`).
- **Cell 0 is the "outdoor" cell**: `0x13AA138` sets `[0x1B682DC]` = `[0x185F8A8]` + 1 = 0 and `0x13A7118` sets
  `[0x1B58998]` the same way; the Position reader `0x47C610` puts `[0x1B58998]` (= 0) into +0xA when the flags carry
  0x80 ("special cell"). The client's own order positions use flags 0xFB / 0xDB (0x80 set: cell 0). ics sends flags
  0x5B with an explicit u16 cell 0 (`ics/wire.py build_position`; `spawn_point` gives cell 0): **the same value**.
  With cell 0, `0x5BE910` takes the outdoor branch: every landblock the position + shape box covers.
- Instance (+0xC, Position flag 4): neither ics nor the client's own orders send it; both 0.
- Region 1 and the landblock are the map's (Crime Alley 0x13BB): the same as the client's orders.

### 2.3 What the test then needs (C structure, O runtime)
For each covered landblock `0x5C86D0`: `0x5C2690` = the block (region, x, y, instance) is in the manager's list
+0x94 (count +0x9C), built by `0x5CE0C0` / `0x5D0E90` as every block within +-120 m of the world centre +0x3C; the
world follows the entity `[0x1B6A710]` (`0x7D2640` -> `0x5D2C20`: shifted beyond 10 m, rebuilt beyond 400 m), so
the blocks around the local player are always in it (P). Then two services (interfaces `0x15BD8C4` vt+0x50 = a
block object for the position, `0x15BDA0C` vt+0x24 = ready): not identified (O).

**Conclusion (P)**: nothing in the creation / movement bundles of ics differs from what the client itself uses for the
position; the position fields are not the cause. Whether the body is built at runtime is O and is what
`diag --bodytest` answers (section 4).

## 3. Hover vs right click (C code, P cause)

- The selection tick `0xA88700` calls `0xA81B30(champion, slot, 1)` with slot = `[[0xA12D50()]+0x90]+0xEC`, **-1**
  while no ability is armed (the object `0xA0AD00` starts with +0x90 = 0); the right click uses slot **0**. Both write
  0x3CB through `0xA168F0`, so a right click also sets 0x3CB, and the next tick overwrites it with its own pick.
- Scores when the validator `0x9D01D0` refuses (C, `0xA16A60`): a unit the champion can attack (`0x9D0490` = 0)
  gets 10 + 0x1000034C / 100 with either slot; an ally (relation 4, unit flags & 0x94918) gets 1 + 0x1C3 / 100 only
  with slot 0 (the `param_3 == 0` branch), with slot -1 0 unless it has 0x10000AA7 and 0x100006C2 (then 0.0001). So
  an ally the validator refuses is found by a right click and not by the hover (C code; whether the validator refuses
  at runtime is O: `HOVER: candidate` scores).
- The outline (`0xA4EDD0`, colour `0xA1D020`) is drawn for the 0x3CB unit when its LifeState is 4; then property
  0x993 is cleared (C).
- The left-click selection's path was not traced (O); the order function `0xA86A00` with its fourth argument set reads
  the hovered unit (0x3CB) instead of picking, so an empty hover also empties those orders (C for that branch).

## 4. Diag (`tools\diag.py`)

| Flag | RVA | Line | Reading |
|---|---|---|---|
| `--hover` | 0x6168F0 | `HOVER: 0x3CB write` | each change of the hovered unit (0 = nothing) |
| `--hover` | 0x64EDEC | `HOVER: outline colour` | alpha 0x3f800000 = outline drawn for that IID, 0 = refused |
| `--bodytest` | 0x1C9EF9 | `HOVER: body position set` | the character's region / landblock-cell / instance / world / body slots at each snap |
| `--bodytest` | 0x1C9DF7, 0x1C9E1B | `HOVER: body build gate` | al 0 = the landblock test refused this unit this step |
| `--bodytest` | 0x1C9B58 | `HOVER: cell test landblocks` | al 0 = position refused; count = blocks covered |
| `--bodytest` | 0x1C9BCB | `HOVER: cell test one block` | al 0 = this block refused (not loaded in the physics world / no block object / not ready) |
| `--bodytest` | 0x1C3290 | `HOVER: body removal` | a body dropped |
| `--bodytest` | 0x1D1600, 0x1C6320 | `HOVER: character object created` / `body built` | as `--ring` |

Steps: `python tools\diag.py --hover` for a whole match (hover an enemy minion, an allied minion, the enemy champion,
then left-click one); then, in a second match or later in the same one, `python tools\diag.py --bodytest` for only
20-30 s with minions on screen (it traps every physics step of every bodiless character), Ctrl+C, send `diag.log`.
Readings: `0x3CB write` lines naming the unit and `outline colour` alpha 0x3f800000 while no outline shows = the draw
itself (render side); `0x3CB write new_iid=0` while hovering = the tick's pick (section 3; the `HOVER: candidate`
lines give the scores); `body build gate al=0` with `cell test one block al=0` = the landblock services of 2.3;
`body built` lines for the units = they have the body, and the ring's missing overlap is a filter / layer matter.

## 5. Changes in this build
None to the server's behaviour (no config key): no server-side input was found that the client's body or outline
lacks. Diag probes above.
