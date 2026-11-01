# Crime Alley: black ground by vision blockers, the turret ring's Player gate, announcer overlap (2026-10-29, fase3-il)

Tester report 2026-10-29 17:45 (Crime Alley v AI with AGL, run 17:32-17:42; then Gotham Heights 17:38-17:41). Evidence:
`logs/server.log`, `logs/traffic.log`, `logs/diag.log` (`diag.py --fog --brazo --ring`, image base 0x850000, the
diag prints RVAs: `0x6AE0E0` = VA `0xAAE0E0`), screenshots `56.webp` (00:54) and `57.webp` (01:59), the decompiled
client (`re-work/decomp`) and capstone reads of the exe. Tags: **C** confirmed, **P** probable, **O** open.
Builds on `ca-black-strips.md` 4, `fog-vision-runtime.md`, `leash-recall-turretring-campicons.md` 3,
`crime-alley-props.md` (ring states), `dialog-shield-disconnect.md` 1.

## 1. Black ground: the fog's occluder pass

### 1.1 Mechanism (C, code)

- 0xAB0C60 (a candidate becomes a source) builds an AABB phantom `0xEB7FF0(aabb, 0x10009)` of the circle (centre at
  the entity position + 0.25 m, half height 0.025 m) and adds it to the Havok world (`0xE9EDB0`).
- 0xAAE0E0 (every update, per source with radius > 0): draws the circle, then, **unless**
  `0x974940(source, &0x100008CE)` is true (an attribute read through the unit component, `0x973730`), walks the
  phantom's overlapping collidables (`[phantom + 0xC0]`, count `+0xC4`). For each: owner = collidable + ownerOffset,
  `0x573050` reads its properties (keys 1, 0, 5, 6: type, ..., IID), `[ctx+0xB8] vt+0x28` = **0xADA050** decides skip,
  else `0xE600D0` runs a Havok query of the body's shape into the fog collector (`ctx+0x100`, radius `ctx+0x114`).
- 0xADA050 -> **0xA4B920(source entity, body entity)**: skip if `0x1000062E` (local) is true; occlude if
  **`0x10000623`** is true; for a map static (IID top byte 1 or 5, `0x4DAFF0`) occlude if **`0x7EB`** is 7 or 8; else
  skip. Server objects (IID top byte 2) occlude only with 0x10000623.
- Data (C, pack scan): `0x10000623 = 1` in 51 records, among them the liftable vehicles **0x4000045D / 0x4000081B**
  (templates also flags 0x1080). `0x100008CE = 1` in the foundries 0x4000016F / 0x40000170 (the base turrets) and a
  few other classes (0x490003F9-0x49000400, 0x4900081E, 0x49000C23, 0x490007FD; roles O). Turret, core and champion
  templates have neither.

### 1.2 What the screenshots show (C positions, P reading)

- Sources at 17:35:41 (00:54) from the `HOT fog: source` lines (radius, x, y): allied turret (9.5, 65, 77.5), turret
  (9.5, 40, 77.5), core (18, 17.5, 77.5), foundry (14, 1.3, 77.1), AGL (12, 72.7, 76.2), minions (5, ...). At 17:36:46
  (01:59) AGL is (12, 97.7, 96.5); the SUV is our liftable vehicle 5 (0x4000045D) at (101.6, 92.1) (lifted 17:36:52).
- `57.webp`: the black is a narrow wedge whose **apex is AGL** and which widens up to the SUV; the bricks beyond the
  SUV are lit. So the dark region is the one BETWEEN the source and the blocker, not the shadow behind it.
- `56.webp` / `ca-black-strips.md` 4: the strip lies between the lane and the fence (statics with 0x7EB 7 / 8 at
  y 83.65) and its west edge is a ray from the turret (65, 77.5): the same figure, source = the allied turret (and
  AGL's circle covers it too).
- So on this client the occluder pass blackens the wrong side (P; why is O: the collector / query direction, or a
  value the original sent). The black is darker than plain fog (3.5 vs 21.9), so it overrides other sources' circles
  (P: drawn after them).

### 1.3 Fix

`[ics] vision_through_blockers = true` (`World.see_through_blockers`): the champion (in `vital_notices_on`, again
after a full bundle), allied bots (`bot_late_properties`), allied structures and minions (`Units._late_vision`) get
0x20F0 `0x100008CE` op 6 (set) = true. The occluder pass is skipped for those circles. The server's own fog
(`fog_vision_radius` 12 m with its navmesh line test) still hides enemies behind walls; the ground behind walls and
vehicles is now lit inside the circle. false = as before.

### 1.4 Tester should see / open

- No black strip by the fence east of the blue turret, no black wedge between AGL and a vehicle; plain fog outside the
  allied circles as before.
- O: that 0x100008CE is honoured as an attribute set by 0x20F0 (P from 0x973730's lookup); if the black stays, run
  `python tools\diag.py --fog` and look for the circles; next would be a breakpoint at 0xAAE1F0 (`local_11`).
- O: the cause of the inverted region; with it fixed the key could go back to false and keep the walls' fog.

## 2. Turret warning ring: the Player gate

### 2.1 The diag (C)

17:33:40 (CA load): `0x101` core t1 allied (refused), **`0x102` core t2 registered** (range 10), `0x103` / `0x109`
allied turrets refused, **`0x106` / `0x10C` enemy turrets registered** (range 9). `c5d=0xddf83001` is the whole
dword: its low byte is 1 = passed. The "Turret bit al=0x10000" lines (IIDs 0x13B-0x175) are lane minions spawned
later (PerceivedType 0x10000), correctly refused. Gotham Heights (17:38) has no lane turrets. So fase3-ij's bundle
flags work; registration was not the problem.

### 2.2 Why it stays hidden (C, code)

- Each frame 0xA8C960 (manager +0x2E clear, local champion present) calls **0xA84FB0** per entry. State 6 (hidden,
  nothing drawn) unless `entry+9` (dead) is 0 **and `entry+0x4C` != 0**.
- `entry+0x4C` is 0 at registration (`0xA40660`) and is written only by **0xA3A5F0**, the callback of the ring's
  phantom (built in 0xA2A710, component 0x8894382, collision filter `0x210000`): for an entity entering / leaving,
  if its PerceivedType has Minion 0x10000 (and not Pet 0x100000) it goes into the unit list `+0x3C`; else if it has
  **Player 0x200000** and its IID is the local champion (`0x85D6D0`), `+0x4C` = inside.
- PerceivedTypeList (ui-complete.md): Player 0x200000, Pet 0x100000, AutomatedPlayer 0x8000, Character 8. Our
  champion's unit flags were 8 only, so +0x4C never became 1.
- Other client readers of the champion's type use 0x200008 (Character | Player: 0xAAA5C0, 0xAAD210, 0xAA6EC0,
  0x86FEE0) or Character alone (attack validator, fog source mask 0x1F4978): 0x200008 passes all of them.

### 2.3 Fix

`[ics] champion_player_flag = true`: the champion's unit flags change (`vital_notices_on`) is 8 | 0x200000.

### 2.4 Tester should see / open

Walking toward an enemy turret: the ring fades in from r + 5.5 m (14.5 m), yellow with one of our minions under it,
green with two or more, red when it shoots the champion (0x10000C66). Needs the option "turret warning" on (byte
0x186CE4F, User.TurretWarningEnabled). O: the minion list wants Minion 0x10000 on the allied minions too
(`unit_flags_on_allies`); if it is always red with our wave under the turret, check that.

## 3. Announcer lines over each other

### 3.1 Traffic (C)

| Time | Sent | Same moment |
|---|---|---|
| 17:35:02.746 / .749 | 0x2A0 (wave in 30 s), 0x2A1 (jungle in 30 s), channel 2 | yes |
| 17:35:22.714 / .715 | 0x29E, 0x29D | yes |
| 17:35:32.734 | 0x29C, 0x29F | yes |
| 17:39:42.817 / .818 (GH) | 0x196 channel 2, 0xAE channel 1 | yes |
| 17:34:47.753 / 49.759 | 0xAE, 0xAD | 2 s apart |
| 17:41:24-29 | event 30 (champion kill) x 3 | 2.3-2.5 s apart |

`match_wave_lines` and `match_jungle_lines` share the times -30 / -10 / 0 on CA, GD and CC. The client handler
0xA77DA0 -> 0xA596B0 -> 0xA0A960 plays each at once (P: no client-side wait found; channels 1 / 3 and 2 are separate).
No priority rule was found in the client (O).

### 3.2 Fix

`Match.voice_out` (`[ics] announcer_queue = true`): every announcer item (Match.line, Match.voice, the bosses' and
objectives' events) goes through one queue. Priority: kills (`announcer_queue_kill_events`: 18-28, 30, 52) > other
events (structures, objectives, Raider) > timeline lines (countdown, waves, jungle). The next item starts
`announcer_queue_gaps[group]` s after the previous one (kill 2.5, event 3.0, line 2.5); a non-kill item waiting more
than `announcer_queue_max_wait` (8 s) is dropped and logged ("announcer queue: dropped ..."); a delayed one is
logged with its wait. false = everything at once as before.

### 3.3 Tester should see / open

The drones and the jungle lines one after the other (2.5 s apart), no line starting over another. O: the real line
lengths (the gaps are a stand-in); whether the original interrupted a timeline line for a kill.

## Tests

`tests/test_match.py` `fog_ring_announcer` (5 checks): the champion's flags 0x200008, 0x100008CE on the champion and on
the allied structures, two lines at once -> the second after the gap, the queue off -> both at once.
