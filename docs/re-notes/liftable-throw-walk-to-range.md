# The vehicle throw beyond its range: walk into range, then throw at the aimed point (2026-10-30)

Tester report 2026-10-30 15:30 (translated): "The vehicle must be thrown at the zone one chooses while carrying it; if
the chosen zone is outside the range, the champion must walk until that point is within reach and then throw the
vehicle. Currently, if the zone is out of range, he throws it straight ahead toward wherever he is facing, regardless of
the chosen zone." Logs: the run 16:36-17:00 (`logs/server.log`, `logs/traffic.log`, Crime Alley, Atomic Green
Lantern). Tags: **C** confirmed (log / code read), **P** probable, **O** open. Builds on
`liftable-carry-throw-press.md` 1.2 (the client's press path) and `liftable-softlock.md` 4 (the unanswered press).

## 1. What happened (C traffic, C code)

Four vehicle carries (vehicle 8 at 16:38:41 and 16:40:28, vehicle 6 at 16:50:29, vehicle 10 at 16:57:35). In each one
the lift order came (0x20EE command 2, slot 7, target the vehicle), the carry walked (0x20EE command 4 move orders), then
**one 0x20EA press of slot 7 (`07 00 00 00 01 00 00 00 23 00 00 10 00`) and no 0x20EE at all**: 16:38:45.886,
16:40:32.873, 16:50:34.256, 16:57:36.382. 0.33 s later `liftable_throw_on_press` (fase3-ip, 1 unanswered press) threw
toward the facing: `throw(ch, None)` puts the point 6 m ahead. No throw of the run came from a client order. The 0x20EA
carries no point (no other client message carries the cursor: the run's C->S types are 0x20EE, 0x20EA, 0x20D1, 0x2136,
0x9F, 0x20BE, ...).

Why the client sent no order, `0xa25d80` (the point checks between the targeting and `0x8686c0` / 0x20EE; C decomp):

- `0x861810` = skill bool `0x100006AB`, `0x861830` = skill bool `0x100006D5`, both through `0x860550` ->
  `0x85ee30(agent, slot, prop)`: the champion's slot-table property (`0x15EDA28[slot]`, slot 7 = `0x100008F0`), a
  property table (kind 0xB) looked up by its vtable +0x10C. That table is the one ics sends while carrying
  (`Liftables._throw_button`: the throw sub-skill's block), so the client reads these flags from the server's table.
- With `0x100006AB` false: the point is snapped to the navmesh within 2.5 m (`0x4fb400(.., 0x40200000)`); then, when
  `0x100006D5` is true and the slot is valid, `range = 0x875f30` (+0.5) and if the squared distance (`0x486db0`) is
  larger: `0xa0a380`, `0x8a2ae0(slot, 0x1000003C Skill_InvalidTarget, ..)` (the HUD error) and **return 0: no order**.
- `0x875f30` -> `0x8749c0` by targeting type (`0x1000003D`): types 1 / 11 / 16 = stat 23 (0x17), 320 m if none; type 10 =
  stat 23 + stat 18; any other type (13, the rubble line) = stat 18; types 13 / 14 add the caster's radius unless the
  skill's flags say not.
- The vehicle throw sub-skill `0x480003C9` (C data, `Data.stolen_power`): `0x100006D5` = 1, `0x1000003D` = 1 (ground
  area), stat 23 = 9.0 m, stat 18 = 2.5 m (its impact area). So the client refuses any point beyond **9.5 m**: the
  tester's "out of range" press. The rubble throw `0x480004A2` has no `0x100006D5` (type 13, stat 18 = 8.5 m): its point
  is always sent and the rock flies its range along the line (C ics, unchanged).
- With `0x100006AB` true the other branch clamps the point to stat 23 (`0x874990`, `0x861a80`) when `0x100006D5` is
  false. Not used by either throw skill.

So in the original the client itself refused an out-of-range vehicle throw (P: the original then showed "invalid
target"; nothing in the client walks into range for a ground-target skill, the server pathing does the walking for
every order, `movement-collision-fog-map.md`).

## 2. Fix

- `[ics] liftable_throw_far_order` (true): `_throw_button` writes `0x100006D5` = 0 (KIND_BOOL) into the throw table it
  puts in the carry slot, so the client sends the order with the far point (P until the next run's traffic shows a
  0x20EE with a point beyond 9.5 m). false = the data's 1.
- `[ics] liftable_throw_walk` (["vehicle"]): `Liftables.throw` with a point farther than the kind's range (`KINDS`
  9.0 m, the client's stat 23) walks the carrier there (`World.walk_to`: navmesh path, the carry speed
  `liftable_carry_speed` 3.5 m/s) and keeps `ch.carry_walk`. Every match tick `_walk_step` (from `Liftables.tick`,
  before `World.tick` moves him):
  - within range -> `throw(.., walked=True)` at the aimed point (no clamp: the vehicle lands on it);
  - the champion no longer heads for the walk's goal (a move order's new path, a stop, a skill order of another slot =
    destination cleared with the path left over, an attack target) -> the walk ends, the carry goes on;
  - the path ended out of range (within 0.75 m of its goal), or `liftable_throw_walk_timeout` (8 s) -> thrown toward
    the point, clamped to the range; no path (`walk_to` false) -> the same at once.
  [] = thrown at once, clamped to the range along the line (as before). A new throw order replaces the walk; `_release`
  / `lift` clear it, so the soft-lock watchdog (`liftable-softlock.md` 5) is unchanged (the walk stays in the "ready"
  phase; an object gone or a dead carrier still ends the carry).
- `[ics] liftable_press_aim` (true): the unanswered-press throw (`liftable_throw_on_press`) goes at `ch.carry_aim`, the
  last point a throw order of this carry named (set by `throw`), walking into range if needed; the facing only when no
  order named a point. The cursor itself is never sent with the press (C, section 1).

## 3. Checks

`tests/test_match.py` `throw_walk_to_range_1530` (11): the slot's `0x100006D5` = 0 while carrying; a point 5 m away is
thrown at once onto the point; a point 15 m away walks ~6 m at carry speed and throws within 9 m onto the point; a move
order cancels the walk and keeps the carry; the unanswered press goes for the aimed point (walking, then throwing on it);
a cleared destination (another skill's order) cancels; `liftable_throw_walk = []` throws at once clamped to 9 m.

## 4. Open

- O: that the client sends the far point with `0x100006D5` = 0 (the next run: a 0x20EE command 2 slot 7 with a point
  beyond 9.5 m, `skill order: slot 7 ...` then "walks into range, then throws" in `server.log`).
- O: the client may keep its own targeting ring on screen during the walk (the indicator stays on until the throw).
- The "robotic" carry (`vehicle-lift-old-vs-ics.md` 3.2) is not touched here; its suggested in-game A/B is still
  `liftable_carry_snap = []` with `liftable_carry_resend = 0.033` in `config.toml` (defaults unchanged).
