# Throw indicator and lob, the relay padlock, the core's end-cinematic duplicate (2026-10-29, fase3-ij)

Tester report 2026-10-29 15:30 after fase3-ii: (1) the thrown vehicle still flies straight and disappears, no curve,
no explosion, no range / target area; (2) the padlock stays when the Crime Alley Raider appears; (3) the power core's
destruction: the central part falls but a whole copy stays in its place. Logs: `logs/server.log`, `logs/traffic.log`
(runs 14:19-14:34 Crime Alley v AI with Raider 14:26:01 and a surrender end 14:33:52; 15:17-15:21 Crime Alley, one
vehicle throw 15:19:14.9, no Raider, no core death). `logs/diag.log` is from 10:44 (no probe of these runs).
C = read in code / data, P = probable, O = open. Exe `InfiniteCrisis.exe`, base 0x400000, decomp `re-work/decomp/c`.
Builds on `throw-truck-padlock.md` (fase3-ih).

## 1. Super Strength throw

### 1.1 What was sent (C traffic 15:19)

| Time | Message |
|---|---|
| 12.291 | AGL facing bundle with the throw sub-skill `0x480003C9` in slot 7 |
| 13.049 / 13.120 | vehicle 6 over the head (bundle), `SuperStrength_PickupObject`, 0x8B rebuild |
| 13.184 | `0x20F9(AGL, slot 7, 0)` "throw indicator on" (agent / slot correct: same agent as the working 0x20C9) |
| 14.896 / 14.897 | client 0x20EA (0x10000023) then 0x20EE 1 ms later (no targeting phase on the client; point 1.4 m from AGL) |
| 14.899 / 14.900 | "throws" bundle, `0x20F9(slot 7, 1)` |
| 15.255 / 15.256 | `thrown` keys, 0x8B "detached" rebuild; flight states unlogged (World.delta sends them with label None) |
| 16.254 | `Vfx_OnExplode` on the vehicle; 26.790 vehicle removed (0x3) |

### 1.2 Why no indicator (C)

- 0x20F9 -> `0xa2a1b0` -> `0xa16e60` -> `0x96ded0`: delivered to the slot's client script `0x340001A3` (S0 -> S1 on
  `0x100000B6`). S1 runs node `0x10000056` -> `0xab62d0` -> **`0xa5dab0(slot, flag)`**, flag = the node's byte +0x24
  (0 in `0x340001A3`).
- `0xa5dab0` draws only `if (slot == [[0xa12d50()]+0x90]+0xEC || flag)`: +0xEC is the HUD controller's current
  targeting slot, set only while the player is in targeting mode for that slot. During a carry it is -1, so the
  event changed the script's state and drew nothing. With a quick cast (as in this run) there is never a targeting
  phase.
- S->C **0x2180** (`u8 0 | u32 slot`, serializer `0x839500`, handler **`0xa6d800`**) does the same start with no gate:
  ends the slot shown at +0x60 (`0xa4f0c0`), frees old decals (`0xa22e20`), sets +0x60 = slot, `0xa39360(slot)` (range
  decal stat 18 + caster radius rules, stat-23 ring at +0x84, cursor area at +0x88), `0xa39820`. The per-frame
  `0xa29680` keeps the cursor area on the cursor for the slot at +0x60 (it reads +0x60, not +0xEC) (C).
- S->C **0x217F** (`u8 0 | u32 slot | u8`, serializer `0x83f690`, `0xa5d070` -> `0xa4f0c0(slot, u8, 1, 0)`) ends it.
- The original server script `0x34000164` S3 (carry) runs `node_10000148($TargetingMode)` and two
  `node_100000FA` skill-stat overrides (stat 1 = 1 or 13: ground or line targeting) plus `node_10000153(CastRadius,
  stat 23)` on the Super Strength slot itself (C tree); ics swaps the slot's table instead (fase3-ie). O: which
  message the original used to show the ring during the carry.

Fix: `Liftables._indicator` sends 0x2180(slot) when the carry is ready and 0x217F(slot) at the throw / drop, besides
the fase3-ih 0x20F9 pair (`[ics] liftable_throw_indicator_messages = ["0x2180", "0x20F9"]`; `["0x20F9"]` = fase3-ih).

### 1.3 Why the flight looks straight (C code, P effect)

- The client replays a 0xB0 state ~0.1 s late, dead-reckons it horizontally (`0x552130`) and, in
  `0x60B5F0` ("ClientRigidBodyCharacterReplayMovementModule"), steers the body by a displacement (`0x5C9FE0`) when the
  error is <= 2 m and no sequence byte is newer; only a newer seq A / B or > 2 m snaps it (`0x5C9E90` +
  `0x60A270(.., 1)`).
- Two runs (fase3-ih frames: sideways at hand height, gone after ~0.2 s; this run: "straight line") show the vehicle
  never following the states' height, while every arc state is < 2 m from the last (P: the character body's
  displacement does not carry the vertical part, or gravity / collision cancels it).
- Fix: every flight state of a kind in `[ics] liftable_throw_snap` (vehicle) carries a newer teleport sequence
  (`World.teleport`), so the client places each state exactly: the lob is drawn at 20 Hz (0.05 s states). `[]` = the
  fase3-ih steering.

### 1.4 Why no explosion (C script)

The thrown vehicle's script `0x3400015F` (S2 on `0x10000124`, defaults read with `Instance._defaults`):
`Vfx_OnInit`, `Vfx_OnExplode` [0 1 0], `Destructible_IgnoreAOI`, a timer of **DestructionDelayDuration 0.15 s**,
**DestructionImpulse(DestructionRange 4.0, DestructionMagnitude 10)** [shape 1 sphere, level 3]; S4: the impulse again
and `DestroyEntity` [10.5 s] (= ics `remove_after`). ExplosionRange 3.0. ics sent only `Vfx_OnExplode`: the vehicle's
destruction pieces (built by 0x8B, `destructible-vehicles.md`) were never hit, so nothing broke apart.
Vehicle tables (C): `0x1D00034B` has Vfx_OnExplode / Vfx_OnThrown / SuperStrength_*; `0x1D000612`
Destructible_OnBreak_*_T1 / Destructible_OnCompletelyDestroyed; `0x1D000111` Destructible_IgnoreAOI; **none has
Vfx_OnInit** (left out).

Fix: at a vehicle's landing `[ics] liftable_land_scriptlets` (Vfx_OnExplode, Destructible_IgnoreAOI) and
`[ics] liftable_land_impulse` = 0x8A destruction sphere to the vehicle at its position (radius 4.0, magnitude 10,
level 3, key 0, FX 0), again 0.15 s later (`M.destruction_sphere`, the format `[ics] destruction_events` uses).
P: that 0x8A on the vehicle's own IID breaks its pieces (C handler path in `destructible-vehicles.md` 3 / 4; not run).

### 1.5 "Disappears" (O)

The fase3-ih frames show the vehicle gone ~0.2 s into a 0.4 s flight, before the explosion key. Candidates (G):
the 0x8B "detached" rebuild at the release re-making the pieces' bodies at the replayed frame; a piece body breaking
on collision (its table has Destructible_OnCollision_Metal / _Rubber). A `diag.py` probe on `0x631050` (0x8B) and
`0x6316D0` (piece detach) during a throw would tell. `[ics] liftable_detach_rebuild {}` is the switch to try.

## 2. The relay padlock at the Raider (C traffic 14:26:01.149, C code)

Sent in one millisecond: `0x100006BD = false`, `0x100006BC = false`, 0x11F stop of `Vfx_Locked` (every run, u8 0),
`Vfx_Unlocked`. No later message touched the pad.

- Minimap note: `0xA80CD0` (property listener) recomputes the note's lock mask (`0xA0CAB0`: `0x100004FF == 0` -> 3,
  else BD | BC) on any change of 0x100006BC / BD / 0x100004FF: the bools' change clears it (C).
- In-world: two runs carry the padlock particles (`0x18000703`, `0x180006FB`): the server's `Vfx_Locked` and the
  client's own `_Selection_Usage_Locked` (`0x10000653`, table `0x1D0004A0`), which `0xAA23C0` starts while the local
  team's bool is true and stops with `0x588A80(obj, 0x10000653, all, 0)` -> **`0x57C4B0(key, mode 1, instance, ..)`**.
- 0x11F's exec calls `0x57C4B0(key, flag = the message's u8, instance)`; the mode goes on to the component's
  vt+0x7C (`0x57B920`). fase3-ih sent mode 0, the client's own key stop uses 1 (C); P that mode 0 lets the run's
  looping particles stay.

Fix: `[ics] match_nook_pad` `unlock_stop = ["Vfx_Locked", "_Selection_Usage_Locked"]`, `unlock_stop_flag = 1`,
`unlock_stop_again = [0.5, 2.0]` (the stops again after the client's own lock refresh). O: if it still shows, the next
candidates are `Vfx_Stop` (base table `0x1D0004A1`) and a `Vfx_Fade_Loop` child.

## 3. The core duplicated at the end (C data, C log)

14:33:52 surrender -> `Match.end` -> end cinematic **0x3500003B** (team 1 lost). Its actor table (cinematics-vfx-audio.md
1.3): **PowerCore `0x2E000AC5` at (17.50, 77.15, 200.10), team 1, `Vfx_Destruct_State0` at frame 0** (0x3500003A: the
team-2 core at (142.5, 77.75)). The client creates that actor and plays the core's destruction (the central part
falls), while ics's networked core (`0x40000C8A` at (17.5, 77.5)) stayed whole on the same spot: the "duplicate". The
core has no head object from ics (`match_turret_heads` covers turrets only); its prow hologram is its own
`Vfx_AI_Active` child and goes with it.

Fix: `Match.end` removes the losing core (and a head if one exists) `[ics] match_end_core_remove_delay` (0) s after
the end cinematic starts (`[ics] match_end_cinematic_removes_core`; false = kept). Applies to every map with an end
cinematic (Gotham Heights' 0x3500000D / 0E use core `0x2E000B47` the same way, P for the others).

## 4. What the tester should see

1. Lifting a vehicle: once it is over the head, the throw's ring around AGL and a circle under the cursor until the
   throw (also with quick cast).
2. The thrown vehicle rises and comes down in an arc (in visible steps if the client snaps), breaks apart and
   explodes where it lands.
3. When the Raider phases in, the padlock hologram on the central plate (and the minimap padlock) go.
4. At the end of a match the losing core is not doubled: only the cinematic's core, which falls.

## 5. Open

- O: the original's message for the carry indicator (0x2180 is P as the original's choice, C as a working path).
- O: why the vehicle vanished mid-flight (1.5); whether the snapped flight looks smooth enough.
- P: 0x8A to the vehicle breaks its pieces; P: 0x11F mode 1 removes looping particles.
