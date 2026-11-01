# Basic-attack projectiles (turrets, ranged minions, Gaslight Batman): what the client needs to home them

Static analysis of `InfiniteCrisis.exe` (Ghidra via REA, image base 0x400000, VA addresses) plus raw reads of the
scriptlet tables in the packs (`ics.rp` / `ics.gamedata`), 2026-10-23. Confidence: **C** = read in code or data,
**P** = probable, **O** = open.

Tester report (2026-10-23, Crime Alley): turret shots drawn as a straight line in one direction; Gaslight Batman's
basic-attack projectiles fly straight to a fixed distance and vanish; ranged minions' projectiles fly off in
various directions.

## 1. Answer in one paragraph

The basic-attack projectiles are **client-side visuals played by the shot scriptlet itself** (no server missile
object, no 0xB0 movement). The scriptlet's projectile action reads its **target from scriptlet variable
`0x10000030` (IID)** and its **speed from scriptlet variable `0x100009EB` (f32)**, the two variables the server
scripts' `RunScriptlet` nodes pass. The server sends only `0x108` (`[ics] scriptlet_variables = false`), so the
action has no target: the data's *no-target* branch plays a straight shot along the facing (Batman, minions) or the
projectile gets no destination (turret). Fix: send `0x10000030` (kind 0x07 IID) and `0x100009EB` (kind 0x09 f32) in
the 0x8D variable table of these shot scriptlets.

## 2. Evidence

### 2.1 Projectile scriptlet action = action type 2 (C)

* Action factory registry `0x669CE0` (slot = type * 4): type 2 factory vtable `0x15CF598` -> create `0x667CD0`
  (0x160-byte definition, constructor `0x666260`, definition vtable **`0x15CF890`**), execute (vtable +0x28)
  **`0x673280`**, field serializer (vtable +0x0C) `0x67A980`.
* Fields of the type 2 definition (`0x67A980`, property id -> offset): 0x316 colour, 0x782 position, 0x153 / 0x611
  / 0x39 model parts (defaults 0x17000001 / 0x17000003 / 0x17000000, the words seen in the data), **0xFA f32 @+0xA4
  (default 10)**, **0x372 f32 @+0xB0 (default 10)**, 0xF9, 0xFB, 0xFC, 0x38 / 0x513 vector3, 0x8E3-0x8E5 frames, ...
  (the property descriptors are in `properties-complete.tsv`, group 0x2A).
* Execute `0x673280`: source = the scriptlet's owner (`0x514D20`, IID at +0x100); **target = `0x51EF90(0x18)` (the
  action's target field 0x18) resolved by `0x51D590` -> `0x517D10`** (a target-selector object, vtable +0x2C) into a
  u64 IID (+ sub-entity) that goes with the speed fields into the projectile created by `0x74AE80`; the persistent
  instance (vtable `0x15CE6A0`) keeps it until it ends. No target -> IID 0.

### 2.2 The data binds those fields to the RunScriptlet variables (C)

Raw words of the scriptlet bodies (format in `client-scriptlets-graphs.md` 1.5; `6 6 n 1 <type>` starts a child):

| Scriptlet (table, pack) | Projectile action (type 2) | Target field 0x18 | Speed |
|---|---|---|---|
| Turret `Object_Ranged_Attack 0x100002E0` (`0x1D00035D`, 0xA0000162) | first action is **type 0x17 "run key on targets" with key `0x1000029D`**, then a type 0x1A sub-run | - | - |
| Turret `Vfx_Basic_Ranged 0x1000029D` (base `0x1D000372`, @0x127FC4) | spawns world states `0x2E000B70/71/73/74`, `0x2E0013AC` (team variants) | `1 18 18 1 3 10000030` (mode 3 = variable 0x10000030) | `2  fa 100009eb  372 100009eb` |
| Ranged minion `0x10000326` (`0x1D0002F6`, 0xA000006F @0x2B7BF0) | world state `0x2E000B68`, inside a type 0x24 container on `0x100007A2` | the same `18 18 1 3 10000030` on its type 0x17 child (impact on the target) | `fa / 372 <- 100009eb` |
| Gaslight Batman `0x10000188` / `0x10000189` (pack 0xA0000122 @0x1C8584; 0x189 runs 0x188) | world state `0x2E000222`; props `0x479 = 10` (10 runs at once), `0x7E6 = 1` | `18 18 1 4 ...` | (bound further down) |
| Trooper / cinematic attacks (`0x1D00076F`) | `0x2E000B66/68/6E`, `0x2E0013B0` | `18 18 1 3 10000030` | `fa / 372 <- 100009eb` |

**Two branches:** Batman's `0x10000188` and the minion / turret tables put the homing projectile inside a type 0x22
container whose condition is on **`0x10000030`** (`22 ... 10000030 0 2 5 1 25d ...`); Batman's second action is a
type 0x22 container on property `0x1CE` with a *second* type 2 projectile that has no target binding. Without
`0x10000030` only that fallback plays: a straight shot to its fixed range (the tester's symptom). (C for the words,
P for the exact condition semantics.)

The projectile world states carry their own visuals: `0x2E000B74` -> table `0x1D000387` with `Vfx_OnInit
0x10000078`, `Vfx_OnCollision 0x10000016`, `_HFSM_DestroyEntityAction 0x100001E0`; children of type 9 wait on
events `0x10000002` (collision) / `0x10000007` and play the impact FX, then the projectile ends (C data, P order).

### 2.3 The server scripts pass exactly these variables (C)

* Turret attack `0x34000014` S3: `RunScriptlet 0x100002E0` with `0x10000030` = target, `0x100009EB` = speed.
* Gaslight Batman basic attack `0x34000037` (`data/script_trees/34000037.json`): `RunScriptlet 0x10000188` /
  `0x10000189` / `0x1000017E` with variable ids `0x10000030` (268435504) and `0x100009EB` (268437995).
* `script-nodes-names.md`: RunScriptlet `0x10000034` operands 2 / 3 / 4 = TargetIID -> `0x10000030`,
  MissileSpeed -> `0x100009EB`.
* Client side: the 0x8D variable table is the run context's table (ctx+0x18, `0x6279D0` -> `0x517240`); an action
  binding whose descriptor is "variable" reads it with `0x44AEC0` (client-scriptlets-graphs.md 1.4).

## 3. What the server does today (C, code)

* `ics/match/units.py` `_direct_attack`: `CastWorld.run_scriptlet(ent, key, target, variables=[(0x10000030,
  target), (0x100009EB, speed)])`, then for structures also `0x1000029D` (`match_turret_shot_extra`).
* `ics/world.py` `ObjectWorld/CastWorld.run_scriptlet` (line ~1423): the variables are **dropped unless
  `[ics] scriptlet_variables`** (default **False**, `ics/config.py` 213, set 2026-10-21 when animations were
  missing, a test confounded with the champion-bundle timing fixed in fase3-ft); then only `0x108 = target`.
* The script runtime's `RunScriptlet` (Batman's attack) goes through the same `run_scriptlet`.

## 4. Minimal server changes, by confidence

1. **(High)** Send the shot variables: in `run_scriptlet`, when the key is a shot scriptlet (or always), emit
   `0x10000030` kind 0x07 = target IID and `0x100009EB` kind 0x09 = speed (f32), **and keep `0x108` = target IID**
   in the same table (harmless, and covers whatever the 2026-10-21 animations read). A new switch, e.g.
   `[ics] shot_scriptlet_variables = [0x100002E0, 0x1000029D, 0x10000326, 0x10000188, 0x10000189, 0x1000017E]`,
   avoids re-enabling `scriptlet_variables` for every scriptlet.
2. **(High)** Speed = the script's own value (turret `0x34000014`, Batman's MissileSpeed stat 30 = 18); the
   `match_shot_speed` 20 fallback only for `_direct_attack`. The type 2 defaults are 10 m/s when unset.
3. **(Medium)** Drop `match_turret_shot_extra` (`0x1000029D`): `0x100002E0`'s first action already runs
   `0x1000029D` (type 0x17), so once the target arrives the server's extra copy draws a second projectile.
4. **(Medium)** Keep the damage delay = distance / speed (already done); the client destroys the visual on
   collision / arrival itself, nothing to send at impact.
5. **(Low / O)** Whether the type 2 projectile re-aims at a moving target or flies to the target's position at
   launch: it stores the IID (C), the per-frame update in `0x74AE80`'s object was not traced. If shots miss moving
   targets after (1), trace that object's update.

Not needed: a missile object, 0xB0 movement, the 0x8D entry's second-IID field (mask 0x20), or a target property on
the shooter.
