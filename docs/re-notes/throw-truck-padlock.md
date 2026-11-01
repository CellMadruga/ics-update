# Super Strength throw indicator and flight, the gaslight truck, the relay padlock (2026-10-29, fase3-ih)

Tester report 2026-10-29 12:45, Crime Alley v AI run 12:12-12:24 (`logs/server.log`, `logs/traffic.log`, screen
recording `2026-10-29 12-09-37.mp4`: video time = server time - 12:09:37.6). C = read in code / data, P = probable,
O = open, G = from frames. Exe `InfiniteCrisis.exe`, base 0x400000, decomp `re-work/decomp/c`.

## 1. The throw shows no range ring and no target area

### 1.1 What the run shows (C log)

Lift 12:19:19.098 (vehicle 5, slot 7): the facing bundle carries the throw sub-skill's slot table, then a 0x20C9
`0x1000001D` for slot 7. The client sends `0x20EA` (its `0x10000023`) at 19.150 and 20.972, and the throw order
`0x20EE` 13 ms after the second one: quick cast. Nothing in the run ever starts an indicator for slot 7. In the video
(581-584 s) only Super Strength's own small ring around the champion shows.

### 1.2 Which client script draws it (C data + script)

| Sub-skill | Targeting 0x1000003D | 0x1000063A | Decals | Stats |
|---|---|---|---|---|
| `0x480003C9` vehicle | 1 (ground area) | `0x340001A3` | `0x100006D8 = 0x48000156`, `0x100006D7 = 0x48000155` | 18 = 2.5, 23 = 9.0, 0x10000ABC = 23 |
| `0x480004A2` rubble | 13 (line) | `0x340001A3` | `0x100002A3 = 0x48000154` | 18 = 8.5, 22 = 1.25, 30 = 15.5 |
| `0x480003CB` Super Strength | 14 | (none: enum default) | `0x100002A3 = 0x48000156` | 18 = 1.5 |

`0x340001A3` (decoded tree, `ics.script_model`):

    S0 -> S1 on ScriptEvent 0x100000B6   S1 enter: LastSkillSlotUsed = #SkillSlot(0x31D944); node 0x10000056(slot)
    S1 -> S0 on ScriptEvent 0x100000B7   S1 exit : node 0x10000022(slot)

Node `0x10000056` executes `0xab62d0` -> `0xa5dab0` (start the slot's indicator, draw `0xa39360`), `0x10000022`
`0xab6330` -> `0xa4f0c0` (end) (targeting-indicator-and-structures.md 1b). Unlike `0x3400019E` it does not react to
the button's `0x10000023`, so pressing the key never shows it: the indicator is meant to be on for the whole carry.

`0x100000B6 / B7` come from S->C **0x20F9** (serializer `0x839550`: `u8 0 | u64 agent | u32 slot | u8 available`;
handler `0xa2a1b0`: event id = `0x100000B6 + (available != 0)`, parameter `SkillSlot` = the slot, delivered by
`0xa16e60` to the instance whose DID is the slot skill's `0x1000063A`). 0x20C9 cannot do it: it carries no parameters,
and S1's SetVariable reads the SkillSlot parameter.

### 1.3 What `0xa39360` draws (C)

- `+0x80` range decal: texture `0x100002A3` (`0x861750`), radius stat 18 (`0x874930`), + the caster's radius
  (`0x5897a0`) for types 7 / 0xE / 9, line extras for type 0xD (`0xac9b80`).
- `+0x84`: texture `0x100006D8` (`0x861780`), radius stat 23 (`0x874990`) when > 0.
- `+0x88` cursor area: texture `0x100006D7` (`0x8617b0`), radius stat 18 if `0x85d230(type)`, half stat 22 for type
  16, else 6.0.
- stat 22 = line width (`0x873ab0(.., 0x16)`); `0x10000ABC` names the stat passed to `0x89fa80` (P: camera zoom).

So the vehicle throw draws a 9 m ring and a 2.5 m target area (C data); the rubble throw an 8.5 m range decal with its
1.25 m line. P: that these are the original's ring and area (no frame of the original throw: the AGL video,
sampled every 3 s, shows no Super Strength).

### 1.4 Fix

`Liftables._indicator`: `0x20F9(champion, slot, 0)` `liftable_throw_indicator_delay` (0.05 s) after the carry is ready
(the slot table went with the lift's facing bundle), `0x20F9(slot, 1)` at the throw press and in `_release` (drop,
death). Once each (`ch.carry_indicator`). `[ics] liftable_throw_indicator` (false = never).

## 2. The throw "looks straight"

### 2.1 Evidence (C log, G frames)

12:19:20.987 throw press; 21.202 release (0.2 s windup); 8 states in 0.41 s (dist / 16 m/s); 21.609 Vfx_OnExplode at
the last state. Video 583.9-584.1: the vehicle moves sideways at about hand height for ~0.2 s and is gone at 584.1;
it never comes down. The client replays states ~0.1 s late (C `0x552130`) with no gravity (full-combat-skills.md:
lobbed missiles need arc states), so the explosion, applied at once, cut the flight before the descent was drawn.

### 2.2 The original's flight (C script, P)

`0x34000161` S2: `LaunchLobbedMissile($ObjectIID, $TargetPosition, -, $MissileVelocity, -, $AttachmentOffset, -,
$SuperStrengthSkillSlot)` values `[0 0 1 1 2 0 0 1]`; MissileVelocity = 15.0 (script default). The toss onto the
champion (S7) uses angle 70 and override script `0x34000160`. O: the exact curve the original server computed for
angle 0 (no gravity value found); O: any spin while flying (no scriptlet in the script rotates it).

### 2.3 Fix

`_fly`: horizontal speed `[ics] liftable_throw_speed` (vehicle 15.0, rock 15.5), flight at least
`liftable_throw_min_seconds` (vehicle 0.8 s), a state every `liftable_throw_step_seconds` (0.05 s; each < 1 m),
height = line + `liftable_throw_arc` (3.0) * 4f(1-f) (parabola, apex ~4 m over the street), the landing (blast /
damage / Vfx_OnExplode) `liftable_land_delay` (vehicle 0.15 s) after the last state. The rock keeps its straight
flight (LaunchMissile), only with more states.

## 3. The gaslight truck stands away from the wall (C navmesh)

Probe rays from the box's long side (rear / middle / front, +-2.5 m along heading 205 deg) along the normal (-0.42,
0.91) to the first boundary edge of the Crime Alley navmesh; gap = hit + 0.525 - 1.0 (as vehicle-lift-and-position.md
1.3):

| Position (yaw 115) | Rear | Middle | Front |
|---|---|---|---|
| (57.7, 93.6) before | 0.622 | 0.653 | 0.713 |
| (57.58, 93.87) earlier suggestion | 0.327 | 0.358 | 0.418 |
| **(57.52, 94.01) now** | **0.175** | **0.205** | **0.265** |

Corridor south of it: 4.6-4.8 m to the next edge. Blocker: the truck's `.entity` box `0x2D000C8F` is half 1.0 x 2.5,
centre 0 (C, vehicle-lift-and-position.md 1.1): `liftable_blockers["0x2E000F04"] = [2.5, 1.0, 0.0, 0.0]` (was the G
[2.8, 1.15]); + the 0.35 margin.

## 4. The central camp's padlock stays when the Raider appears

### 4.1 Evidence (C log)

Spawn 12:12:49.857, then `_Entity_OnEnterWorld_Default`, `Vfx_Fade_In`, `Vfx_Locked` (12:12:58.443). Raider at
12:18:57.898; the same millisecond: `0x100006BD = false`, `0x100006BC = false` (0x6) and `Vfx_Unlocked` (0x8D). So the
unlock was sent, in order.

### 4.2 Cause (C keys, P effect)

The padlock hologram on the plate is `Vfx_Locked`'s particles (`0x18000703`, `0x180006FB`, `0x180007DF`; table
`0x1D0004A1`, deep-scan-maps.md 1.2). A started scriptlet run keeps its particles until it ends; `Vfx_Unlocked` only
starts another run, and the bools drive the hover lock `_Selection_Usage_Locked` (`0xAA23C0`), not this run. The
minimap tracker pip was already lock 0 (`match_tracker_initial`).

### 4.3 Fix

`Match.unlock_nook`: event `0x11F(pad, key Vfx_Locked, instance 0xFFFFFFFF, 0)` (every run of the key; exec
`0x675280` -> `0x57C4B0` -> `0x529EF0`: end list, attachments released) before the bools and `Vfx_Unlocked`
(`[ics] match_nook_pad "unlock_stop": ["Vfx_Locked"]`; [] = as before). Fallback if the hologram still stays: add
`"Vfx_Stop"` (base table) to `unlock_scriptlets` (P).

## 5. What the tester should see

1. Lifting a vehicle: once it is held over the head, a 9 m ring around AGL and a 2.5 m circle under the cursor until
   the throw; a meteorite: an 8.5 m range with the line.
2. The thrown vehicle rises in an arc (~4 m) over ~0.8 s, comes down at the point and explodes there.
3. The gaslight truck by the left jungle mouth touches the wall like the SUV on the right.
4. When the Raider phases in, the padlock hologram on the central plate goes.

## 6. Open

- O: the original's exact lob curve for angle 0 and whether the vehicle spun in flight.
- P: that the slot instance `0x340001A3` exists on the client when 0x20F9 arrives (it is created when the slot table
  changes, `0xA4F6B0`); a `python tools\diag.py` probe on `0x5789C0` (add-by-DID) during a lift would confirm it.
- P: that 0x11F stops the particles of `Vfx_Locked` (no frame yet).
