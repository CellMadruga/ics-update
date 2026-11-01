# Basic attack on a fleeing champion: the chase that never stops (2026-10-29, fase3-im)

Tester report 2026-10-29 18:31 (Crime Alley v AI, Atomic Green Lantern vs AI Batman): "sometimes, even with the enemy
champion inside the basic-attack area, if I attack it and it runs away, my champion runs after it and does not stop to
attack while it is in attack range". Tags: **C** confirmed, **P** probable, **O** open.

## 1. Cause

- `World._attack_step` (ics/world.py) chases while `distance > reach` and stops and swings once it is <= reach,
  every tick, on the current positions (C code). `reach` was the basic attack's stat 18, **centre to centre** (plus
  `match_unit.radius - 0.5` for structures only, `attack_reach_to_edge`).
- Stat 18 of the basic attacks (catalog `skills.tsv`, slot 0): **1.0 m for 26 of 54 champions** (melee, AGL included,
  basic `0x480007A2:0`, script 0x340002B6), 5-5.35 m for the ranged ones (C data).
- The client's attack validator **`0x9D01D0` step 11**: distance <= skill range (`0x874930`) **+ both collision radii**
  (`0x5897A0` = template radius x scale + 0.05) (`targeting-and-relations.md` 1b, C); the range ring (`0xA39360`) adds
  the caster's radius (`reverse-engineering.md`, range decals, C). The basic attack's own script 0x340002B6 has no range
  check (C tree: InitSkill / LoadSkillStats / Cast / FaceTarget / ApplyDamage on OnCastSignal 3): the reach is the
  server's order logic alone.
- Champion bodies: the champion navmesh agent class 0x10000003 has radius 0.525 (`maps-complete.md`, C); P that the
  template radius is the same, so a champion's `0x5897A0` is ~0.575.
- So a melee champion needed the target's centre within 1.0 m, less than two bodies (~1.1 m): a standing target is
  reached only because the server lets bodies overlap; a target walking away at the same speed keeps its gap (the chase
  aims at 0.8 x reach from it) and is never within 1.0 m, while it is well inside the client's 2.15 m ring. Ranged
  champions lost ~1.15 m the same way (C arithmetic; matches the report).

## 2. Fix

`[ics] attack_range_radii` (true): a champion's basic-attack reach = stat 18 + its radius + the target's
(`World._attack_radius`: a structure's / minion's `match_unit.radius`, else `[ics] attack_body_radius` by kind:
champion 0.575, unit 0.5); it replaces `attack_reach_to_edge` for champions (the structure's whole radius now, as the
client). In range the chase path is cleared too; out of range the chase starts again on the next tick. Units keep
their own reach (`units._reach`). false = as before.

## 3. Checks

`tests/test_match.py` `chase_range`: a bot walking away at the champion's speed, stat 18 + 0.69 m away: the champion
stops and swings on the first tick; when the bot leaves the range it chases again; with `attack_range_radii = false`
it chases for 0.5 s and never swings.

## 4. Open

- P: the champion template radius (0x5897A0 reads `[entity]+0x74`; the property behind it was not traced). 0.575 is
  the agent radius + 0.05.
- O: whether the original kept a swing going when the target left the range during its wind-up (not changed here).
