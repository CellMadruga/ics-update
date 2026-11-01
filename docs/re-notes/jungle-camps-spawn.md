# Crime Alley jungle camps: phase-in end, attack cancel, model (2026-10-28)

Trigger: tester 13:52 (Crime Alley v AI, run 13:38-13:52; `logs/server.log`, `logs/traffic.log`): the jungle creatures
(1) stay in their yellow spawn phase-in (fase3-id `Vfx_Spawn_Alt01`) and it never ends, (2) do not have the right model,
(3) lose the effect at once and "pop" in when attacked. Sources: the client exe (decompilation in `re-work/decomp`, VA,
image base 0x400000; vtables read from the PE), pack `0xA0000161` / `0xA00002E7` of the player's install (`ics.gamedata`,
nothing copied), the logs. Tags: **C** confirmed (code / data / log read), **P** probable, **G** guessed, **O** open.
Builds on liftables-camps-animations.md 3, crime-alley-jungle.md 3-4, crime-alley-2v2-video.md 4,
client-scriptlets-graphs.md 1.4-1.6, skin-overlay-fix.md 1.

## 0. What the server sent (C, traffic.log)

| t | camp 0 / 2 heavy `0x40000CA1` |
|---|---|
| 13:41:16.668 | creation bundle (161 B) + vitals; no `_Entity_OnEnterWorld_Default` (`match_camp_skip_enter_world`) |
| +0.22 | `Vfx_Spawn_Alt01` (0x8D, one run per unit), nothing else for the run afterwards |
| +0.76 / +0.93 | `0x1000019D = 0x100`, `0x10000029`, `0x10000249` (0x6), unit flags 0x100 (0x6): targetable at once |
| 13:46:25 | vehicle 5 lands on camp 2 (damage, hit effects, slow status) |
| 13:46:26.386 | `state (111.2, 93.0) speed 3` = a **full bundle** (`Units.send_state` -> `World.update`, 192 B): the camp chases |

## 1. Why the phase-in never ends (C)

- Table `0x1D000674` (pack `0xA0000161`), entry `Vfx_Spawn_Alt01 0x10000347` @ `0xBEEE14` (Event02 `0x1000087B` @
  `0xBEEB50` the same): a type 5 container whose child is action **type 8** (render effect, factory `0x15CF5E8`,
  object vtable `0x15CEAB0`, execute `0x673CF0`). The type-8 object's word reader (`0x66D910`; property map
  `0x67CB70`; defaults `0x654C00`) reads in order `+0x34` (`0x5BF` sub-type), **`+0x38` (`0x375` bool)**, `+0x3C`
  (`0x319`), `+0x40` (`0x2C5`), `+0x44` (`0x3D4`), `+0x48` (`0x417`), `+0x61` (`0x933`), curves..., `+0x158` (`0x834`
  = the overlay mesh `0x17001445`), then the action base (probability 1.0, jitter 0, intensity 1.0, sequence).
  Alt01's words: `8 | 8 | 1 | 0.0 | 1.0 | 0.0 | 1 | 0 | ...` (Event02: `8 | 8 | 1 | 0.0 | 9.0 | 0.0 | ...`), so
  `+0x38` = **1** (the class default is also 1).
- `0x673CF0`: when `+0x38 != 0` it allocates a persistent instance (`0x654BD0`, vtable `0x15CEA68`, base `0x52A660`)
  and returns it as the action's attachment; the run keeps it in its live list (client-scriptlets-graphs.md 1.4).
  So the overlay stays **while the run lives**. The run ends only when its children end, a signal / stop arrives, or
  the object is re-created; nothing in the entry ends it by time (P: `+0x3C` / `+0x44` fade in / out = 0,
  `+0x40` = 1.0 / 9.0 an intensity or speed, not a duration; the defaults are 0.25 / 1.0 / 0.25).
- ics sent the key once and never stopped it: the overlay (and Alt01's particle `0x18000D90` and black fade) stayed
  for the whole life of the creature.
- No "phasing complete" key exists in the CA tables (`0x1D0000E2`, `E1`, `E8` + base `0x1D0004F4`, `0x1D000385`,
  `0x1D000674`; C). The original ended the phase from the server (P: a signal on the run, as for the status
  visuals' `stop ... (0x8d signal 1)`, which `World.signal_scriptlet` already sends).

## 2. Why an attack removed it at once (C log, P mechanism)

The first damage provoked the camp (`Match._on_hit` -> `camp.provoker`), it chased, and every movement state is a full
creation bundle (`match_move_message` "bundle"). A bundle re-creates the object's state and drops what its running
scriptlets attached (the same effect as AGL's shield sphere, `World._resend_looping`, fase3-ib): the phase-in vanished,
the plain model "popped" in. In the original the creatures were not attackable while phasing: "Jungle Creatures:
Phasing Complete" is the moment the minimap diamonds appear and the camps become active (crime-alley-2v2-video.md 4,
C frames); the phase-in visual shows ~3 s before (respawn 10:57 -> 11:00, G).

## 3. The model (C data, P conclusion)

| Class | Template (pack `0xA00002E7`) | World state `0x510` | Scale `0x6B4` | Tables `0x7D2` |
|---|---|---|---|---|
| `0x40000CA0` Tripod | `0x49000CA0` | `0x2E000BE2` (.entity `0x2D0009D0`, graph `0x1C000086`, ctype 7) | **0.35** | `0x1D0000E2`, `E1`, `E8`, `0x1D000385`, `0x1D000674` |
| `0x40000CA1` Heavy Tripod | `0x49000CA1` | `0x2E000BE2` | **0.7** | same |
| `0x40000CA2` Raider | `0x49000CA2` | `0x2E000F1B` (.entity `0x2D000CA6`) | 0.75 | same + its own |

- Every Tripod class of every map (CC `0x40000894` / `898` / `89A`, GD `0x40000935` / `939` / `93B`, CA `0x40000A61` /
  `A64`, `0x40000E7D` / `E7E`, `0x40000CA0` / `CA1`) uses world state `0x2E000BE2`; the heavy one is the same rig at
  twice the scale. `0x10000319` / `0x10000689` / `0x10000224` / `0x100001D9` are scaling formulas (`0x3B`), not
  costumes. There is no other CA jungle model in the data (C). The original's "one big golden spider robot + two
  small ones" is exactly `0x40000CA1` + 2 x `0x40000CA0`.
- The client merges the class template at creation (`0x54F1F0`, skin-overlay-fix.md 1), so the scale 0.35 / 0.7 needs
  no server property (P).
- So what looked like a wrong model was the stuck phase-in: the yellow wireframe overlay `0x17001445` plus Alt01's
  black fade on top of the creature for its whole life (P). O: if after this build the creatures still look wrong
  once phased in, a screenshot of a phased-in camp next to the original frame decides (colour 6 neutral comes from the
  creation bundle's `0x1000009C` = 0, targeting-and-relations.md 3).

## 4. Fix (ics/match/match.py `_spawn_camp`, `_camp_phase_in`, `_camp_phase_end`; units.py `_late_flag`)

- A camp unit whose tables hold a `match_camp_spawn_scriptlets` key phases for **`match_camp_phase_seconds`** (3.0, G):
  `invulnerable` (no damage, no provoke, not a valid AI target) and its targeting flags held (`hold_flags`:
  `World._late_flags` and `Units._late_flag` store them) (`match_camp_phase_untargetable`).
- During the phase the key sits in `World.looping_scriptlets`, so a full bundle of the unit re-sends it
  (`match_camp_phase_resend`).
- At the end: `World.signal_scriptlet` stops the run (0x8D, run's instance, signal bit 1; `match_camp_phase_stop`),
  the held flags go (0x6), then one bundle 0.1 s later (`match_camp_phase_end_bundle`; as the director's "targetable",
  and it drops whatever a stop left).
- The first camps start `match_camp_phase_seconds` before `match_camps_first_by_map` (`match_camp_phase_lead`), so the
  phase completes on the "Phasing Complete" line (671 at 45 s); respawns phase from their spawn.
- `match_camp_phase_seconds = 0` restores fase3-id (key sent once, never stopped, attackable at once).
- Tests: `tests/test_match.py` (stop before flags; invulnerable while phasing; re-send after a bundle; phase over at
  the line time).

## 5. Open

- O: exact phase length of the original (3 s from one respawn frame; the first spawn may have phased the whole 10 s
  between "Online in 10 seconds" and "Phasing Complete"). Change `match_camp_phase_seconds`.
- O: whether the client fades the overlay out on the stop (`+0x44` = 0: probably instant).
- O: why Event02 (overlay only) never showed in the earlier tests while Alt01 does.
- Diag if the overlay still stays: break `0x673CF0` (log `[ecx+0x38]`) and the run removal `0x57BAF0` after the
  `stop Vfx_Spawn_Alt01` line.
