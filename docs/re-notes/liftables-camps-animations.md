# Super Strength carry / throw and the jungle camps' spawn-in (2026-10-28)

Trigger: tester 12:56 (Crime Alley v AI, Atomic Green Lantern; `logs/server.log`, `logs/traffic.log`): (1) the jungle
creatures appear with no spawn animation (original: a sparkling yellow translucent wireframe); (2) the meteorite's
lift / throw has no proper animation; (3) a lifted vehicle vanishes (invisible over the champion) and its throw does
no damage. Sources: the client exe (Ghidra decompilation in `re-work/decomp`, VA, image base 0x400000; vtables read
from the PE), the packs of the player's install (`ics.gamedata`, nothing copied), the logs. Tags: **C** confirmed
(code / data / log read), **P** probable, **O** open. Builds on grab-arm-carry.md 2, destructible-vehicles.md,
crime-alley-props.md A.3, crime-alley-jungle.md 3, client-scriptlets-graphs.md.

## 0. What the server sent (C, traffic.log)

| t | Rock 4 (12:24:54) | Vehicle 6 (12:28:30) |
|---|---|---|
| 0 | facing bundle (1501 B), PickupRubble 0x100004CD | stops-to-cast + facing bundles (1502 B), InitObjectPickup on both |
| +0.07..0.1 | | graph CarPickup, PickupObject on both, **attach** (0xB0 flag 0x04), DisableHit |
| +0.08..0.2 | Vfx_PickUp on the rock, **attach**, DisableHit | |
| +0.27 / +0.55 | **full champion bundle "throw skill while carrying" (1395 / 1414 B)** | same |
| carry | "credits" / "XP" / "level" full champion bundles every few s (e.g. 58.683 during the rock's throw) | 40.76 level + credits bundles |
| throw | facing bundle, ThrowRubble; detach +0.26; EnableHit; **"Super Strength again" full bundle +0.29** | facing bundle, ThrowObject on both; detach +0.21; EnableHit; "Super Strength again" +0.23 |
| land | Fade_Out (no hit) | Vfx_OnExplode, "lands: nothing hit" |

No bundle of the carried object went while it was attached (C), so the containment was never broken by an object
bundle without the 0x04 block.

## 1. A lifted vehicle vanishes

### 1.1 How the client attaches (C)

0xB0 flag 0x04 -> listener `0x6113E0` -> `0x634C70` (parent lookup) -> `0x58A220` -> `0x55F930(child, mode, extra)`:
`0x588330(child, 5)` -> `0x570BF0(5)` (location state 5: the object is unregistered and re-registered, its render
re-parented through the render component's attach method), a containment record (`0x55E360`; +0x10 mode, +0x14 the
child, +0x18 the mode-0x10 extra block copied by `0x55E6B0`: u32, u8, a 0x1C-byte local transform left at its
defaults, bool) added to the parent (`vt+0x60`). The parent is entity+0x1C (containment component) +0x58
(`0x587A50`; `0x55DCE0` walks the chain). There is no bone / hardpoint field on the wire besides the u32 (P: the
attach point 0x100000B0).

### 1.2 Why a destructible disappears (C path, P result)

- A vehicle (world state with 0x800) has the destruction render variant, which draws only its pieces
  (destructible-vehicles.md). The pieces and their render instances (`piece+0x15C`) are built by 0x8B, in the world.
- On attach the render variant's attach method (vt+0x68 = `0x6239A0`) calls `0x630BF0(parent render, ...)`, which
  builds instances **only for pieces without one** (`piece+0x15C == 0`): the world-space instances 0x8B made are left
  as they were, so nothing of the vehicle is drawn under the champion (P: the re-registration of `0x570BF0` drops the
  old ones from the scene; the tester sees the vehicle vanish).
- 0x8B's handler `0x631050` clears and rebuilds the pieces and ends in `0x630FC0`, whose **first branch is the
  contained case**: `0x587A50(entity)` -> parent; `0x630BF0(parent+0x14 -> +0xA0, ...)` -> `0x7602A0(piece, parent
  render, 0x200, flags, 0, 0, 0, 0, arg)` per piece. So an 0x8B sent after the attach builds the pieces under the
  champion's render node (C path), and one after the detach builds them in the world again for the flight (C path).
- O: where exactly the pieces sit under the parent (the zeros of `0x7602A0` look like "no bone"; the pieces' local
  frames come from the entity frame at the rebuild). If the vehicle shows at the champion's feet, the next step is the
  extra block's u32 / transform (diag on `0x55E6B0`) or carrying the vehicle with plain bundles over the head (no
  attach for vehicles: `liftable_attach` stays global, `liftable_attach_rebuild` = {} reverts this fix).

### 1.3 No damage (C log)

The throw point (73.7, 78.3) was 1.8 m from AGL at (72.1, 79.1); the units within 2.5 m of it were AGL's own minions
(t1 w6 / w7 states at 12:28:41.2-41.4). `tests/test_match.py` shows the blast hurting a hostile in range. No change.
What makes a thrown vehicle fly and explode on the client is server-driven (C, crime-alley-props.md A.3): the
movement bundles of the lob, then Vfx_OnFire / Vfx_OnThrown and Vfx_OnExplode scriptlets; the client has no physics
of its own for it.

## 2. The lift / throw animation

### 2.1 What drives it (C, unchanged)

The champion's graph does the pose: the scriptlets SuperStrength_PickupRubble / ThrowRubble / InitObjectPickup /
PickupObject / ThrowObject raise graph events (type 0x14 action, raised on the 0x8D's own object; the 0x108 target
variable does not redirect it, `0x672930`), and CarPickup goes through `0x100001E3` + 0x780. The object only rides the
containment. Nothing in the client's own Super Strength slot script (a targeting indicator, client-skill-instances.md
2) moves the object.

### 2.2 What was wrong (C log, P effect)

Full champion bundles (0x4 with the 0xBC table) landed inside the clips: the throw skill's slot table 0.27 s into the
rock pickup (before the Hold state at 0.30) and 0.55 s into the vehicle pickup; credits / XP / level bundles during
the carry; Super Strength's slot table 0.29 s into the throw (the rock leaves the hand at 0.26). A full bundle
replaces the object's 0x7D2 tables and drops what its running scriptlets hold (fase3-ib, grab-beam.md 6; the Shards
sphere). P: it also cuts the pickup / throw scriptlet runs and their graph effects.

### 2.3 Fix

- The throw skill's slot table rides in the lift's facing bundle, sent before the pickup key
  (`liftable_throw_skill_at_lift`).
- While carrying, the champion's other full bundles wait (`liftable_hold_champion_bundles`; `World.update(force=True)`
  for the carry's own facing bundles).
- Super Strength's slot table (with whatever was held) and then the slot cooldown go 0.9 s after the throw's end
  (`liftable_slot_restore_delay`).

## 3. The camps' spawn-in

### 3.1 Data (C, pack 0xA0000161, table 0x1D000674 on 0x40000CA0 / CA1 / CA2)

| Key | Content |
|---|---|
| Vfx_Spawn_Event02 0x1000087B | type 5 group: type 8 render effect, overlay mesh 0x17001445, colour 0xFFF5EC04, fade keys (100, 0.5, 0, 0.25) |
| Vfx_Spawn_Event03 / Event04 | the same overlay with longer fades (0.75 / 0.5; 1.0 / 0.75) |
| Vfx_Spawn_Alt01 0x10000347 | the same overlay **plus** particle 0x18000D90 (type 0x11, 40 / 60) and a black fade |
| Vfx_Spawn_Alt02 0x10000346 | particle 0x18000B6E |

The sparkles of the original's phase-in are a particle; only Alt01 has one with the yellow overlay (P).

### 3.2 Client side (C)

- Render effect action type 8: factory vtable `0x15CF5E8` (create `0x663F00`), object vtable `0x15CEAB0`, execute
  **`0x673CF0`**: needs the render component (entity+0x14), is skipped when its byte +0x38 is 0 and the run flags
  (ctx+0x50 = the 0x8D entry's run flags, 0 from ics) have 0x40, then render vt+0x50 (`0x623920`) queues the effect
  (`0x623480`) and applies it when the render instance (+0xA0) exists. So timing against the model load is not the
  blocker (C), and a 0x8D with run flags 0 is not filtered (C).
- O: why Event02's overlay never showed in three tests (fog, model, fade too short). Alt01's particle does not depend
  on the overlay.

### 3.3 Fix

`match_camp_spawn_scriptlets` = ["Vfx_Spawn_Alt01"], `match_camp_spawn_delay` = 0.1 s (the drones' spawn-in timing,
which shows; was Event02 at 0.4). If still nothing: Event01 (0x1000087C) as the chain's entry, or the three
Event02 -> 03 -> 04 steps 0.25 s apart.

## 4. Confidence

| Issue | Cause | Fix (key) | Confidence |
|---|---|---|---|
| Vehicle vanishes when lifted | pieces' render instances not rebuilt under the parent | 0x8B after attach / detach (`liftable_attach_rebuild`, `liftable_detach_rebuild`) | C path, P result |
| Thrown vehicle no damage | no hostile within 2.5 m of the landing point | none | C (log) |
| Rock lift / throw animation | full champion bundles inside the clips | `liftable_throw_skill_at_lift`, `liftable_hold_champion_bundles`, `liftable_slot_restore_delay` | C log, P effect |
| Camps without spawn-in | Event02 = overlay only; never seen | Alt01 at 0.1 s (`match_camp_spawn_scriptlets`, `match_camp_spawn_delay`) | C data, P effect |
