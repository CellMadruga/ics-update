# Minions attack without turning toward their target (2026-10-29, fase3-in)

Tester report 2026-10-29 19:55 (Crime Alley v AI, Atomic Green Lantern): "the minions don't turn to attack me: they
attack me but always without changing their orientation toward me". Tags: **C** confirmed, **P** probable, **O** open.

## 1. Cause (C code, C traffic)

- `ics/match/units.py` `Units.act`, target in reach: when the unit was walking, `stop()` sent its stop state **with the
  walking heading**; the heading toward the target was set right after it and never sent. A unit already standing
  turned (server side) every tick toward a moving target and none of those turns was sent either: the next state went
  only when it walked again (or `match_move_refresh` 1 s while walking).
- The client draws a unit's facing from its movement state only (bit 8 facing / heading, `client-movement.md` 2; no
  client-side facing logic for server units, C). The minions' attack script (`0x340004A0`, ranged) dealt no damage in
  ics and the units fall back to `_direct_attack` after 3 swings ("attack script ... deals no damage here; direct
  damage", C log 19:52:36.427): no FaceTarget node runs then either.
- Bots and the champion are not affected: `World._attack_step` sets the heading and their basic attack scripts run
  FaceTarget (`CastWorld.face` sends the turn, `face_min_turn_degrees`). Structures have move speed 0 (their head is a
  separate object driven by the targeting key).

## 2. Fix

`[ics] match_attack_face_turn` (0.15 rad): in reach, the stop state at the end of a walk carries the facing toward the
target, and a standing unit sends one stop state with the new facing when it differs by more than 0.15 rad from the
facing the client was last sent (`MatchUnit.sent_heading`, set by `send_state`). Units with move speed 0 keep
theirs. 0 = never, as before.

## 3. Checks

`tests/test_match.py` `carry_press_facing`: a minion with its target 90 degrees off its last facing sends one state
facing it; none while the facing holds; none with `match_attack_face_turn = 0`.
