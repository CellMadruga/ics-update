# Object update bundles: what a 0x4 does to an object that already exists, and a correct update (2026-10-28)

Trigger: tester report 2026-10-28 14:39-15:00 (fase3-ie, Crime Alley v AI, Atomic Green Lantern vs bot Atomic Wonder
Woman; `logs/server.log`, `logs/traffic.log`, screenshots 42-47). Several animation bugs (Shards sphere, Grab arm, camp
phase-in, vehicle carry / lift clip, Meltdown on a moving target, death) were blamed on one belief: "a full object
bundle re-creates the object on the client and drops what its running scriptlets attached". This note reverses the
client's handling of event 0x4 for a live object end to end and replaces that belief.

Sources: the Ghidra decompilation (`re-work/decomp/c`, `functions.tsv`) and capstone disassembly of
`InfiniteCrisis.exe` (VA, image base 0x400000; the bytes at every address below are identical in
`InfiniteCrisis_patched.exe`), the property descriptors (`properties-complete.tsv`), the logs above (decoded with a
scratch parser: every labelled 0x4 batch, its 0xF2 / 0xB0 / 0xBC, every 0x6), the server code. Nothing of the game is
copied. Tags: **C** = confirmed (code, data or log bytes read), **P** = probable, **O** = open.

Builds on: client-movement.md (0xB0 layout, replay), full-entities-engine.md 4-5 (factory, property system),
skin-overlay-fix.md 1-3 (create handler, world-state override), champion-animation-matrix.md 1 (corrected here),
deep-scan-animations.md 1.2 (corrected here), bot-champions.md 3.5, grab-beam.md, jungle-camps-spawn.md 2,
stubborn-visuals.md 2, client-scriptlets-graphs.md 1.

---------------------------------------------------------------------------------------------------------------------

## 0. Answers

1. **A full 0x4 bundle to a live object re-creates nothing** (C). Its 0xF2 does nothing while its trailing u32 equals
   `entity+0x110` (0 since creation, and ics sends 0). Its 0xBC is a *diff* of the property table, applied through the
   same per-property setter as event 0x6. Its 0xB0 is one more movement state. No component, scriptlet run, graph
   instance or model is rebuilt by any of the three (sections 1-4).
2. **Re-setting 0x7D2 (scriptlet tables) or 0x5B5 (graph) with the same value does nothing** (C): an equal value fires
   no notification (arrays are compared element by element, `0x4FF770`), 0x7D2 is read only when the script component
   is constructed (no watcher exists on it), and 0x5B5 is never sent (network mode 0, not in any ics bundle).
3. What a bundle **does** change on a live object (C):
   - every sent id whose value differs is set and notified ("changed" / "added"), exactly as a 0x6 would do;
   - **every id of the object's own table with network mode 1 or 3 that the table omits is REMOVED** (`0x62AFD0`),
     notified as "removed", or as "changed" back to the template value when the class has one. In ics this removes the
     ids it sent by 0x6 and leaves out of the bundle: unit flags `0x1000019D`, targeting tags `0x10000029` /
     `0x10000249` (bot, champion), the order lock `0x10000B2D` and Stunned `0x100003F3` (CC), `0x10000C66` (turret);
     the scriptlets' type 0x22 containers watch exactly LifeState `0x100000FA`, `0x10000B2D` and `0x100003F3`;
   - the 0xB0 re-sends position, heading, speed and facing: a changed facing makes the graph input Turn non-zero for
     one replay step and a changed speed moves Propel, which end skill and cosmetic states through the Lua early-outs
     (champion-animation-matrix.md 1). This is the same for a 0xB0-only update: it is the content, not the bundle.
4. **The one bundle field that really rebuilds a live object** is the 0xF2 world-state override: a u32 different from
   `entity+0x110` calls ChangeWorldState `0x54D5C0` (detach and rebuild the components). It must stay 0 (C;
   `[ics] descriptor_world_state_zero` = true, fase3-hs).
5. **The 0xB0-only update works** (C path, P strong for the old test): a 0x4 batch with only 0xB0, or a standalone 0xB0
   event, reaches the same listener `0x60AFA0`. The fase3-hy report it was blamed on ("a dead bot slides until it
   respawns, walks back lying down, is invisible until it attacks") shows the motion *was* applied (it slid and
   walked); what never arrived was the fog flag `0x90F`, which ics delivers only inside a full bundle's 0xBC
   (`World.fog` -> `extra_props`), so the bot stayed hidden until its first attack's full bundle.
6. **A correct update** = the 0xB0 block alone when the motion changes, plus one 0x6 per property that changed and one
   0x86 per property the server wants gone; a full bundle only to create (or to retry a creation). Section 7.
7. The specific bugs (section 6): Meltdown's stop is the server script (graph hook 2 at +0.18 s, C log); the Shards
   sphere left with the basic attack's `Combat_Basic_Attack 0x10000128` even when no bundle was sent (C, fase3-ic log
   note), so its cause is **O**, as are the camp phase-in loss and Grab's arm: the new `diag.py --bundles` mode logs
   who ends those attachments, with the call stack.

---------------------------------------------------------------------------------------------------------------------

## 1. The path of event 0x4 to a live object (C)

| Step | Address | What |
|---|---|---|
| reader | `0x447770` | `u8 base | cint n | n x (cint event | u32 len | body)`; each sub-event is built by its factory (`0xB0ED90`) and read |
| batch exec | `0x5D9FF0` | returns 1: the batch is a "service" event, handled by the object manager |
| object manager | `0x64E070` (vtable `0x15CDC90` +0x1C) | target IID must be a server IID (`0x4DAF90`); event 4 -> `0x64AB70` (a new batch object `0x64A660` with the same sub-event list, P) -> `0x64BD30`; event 0x87 -> `0x64BD30`; 0xF2 -> landblock checks (`0x635230`, `0x47FA70`, `0x6351D0`) -> `0x64D8A0`; 3 -> remove `0x64DDE0`; any other event for an IID that does not exist yet is deferred (vt+0x28), else the generic dispatch `0xB0D9C0` runs its exec |
| batch dispatch | `0x64BD30` | (a) IID waiting for its landblock (set `this+0x180`): the whole batch is deferred; (b) IID in the set `this+0xE0` (P: objects removed by 0x3 and not yet freed, 30 s): taken out of it and **re-shown** (`ent+0x118 |= 8`, `0x69BD00`) when the scene flag `this+0x11C` is up; (c) every sub-event is dispatched **in wire order**; an 0xF2 gets a pointer to its batch at +0x2C (its creation reads the 0xB0 / 0xBC siblings from it) |
| 0xF2 | `0x64D8A0` | section 2 |
| 0xB0 | exec `0x698CD0` | entity by IID (`0x445070`; none -> 0x80004002) -> `0x6298D0(entity, block)`: every listener of `[ent+0x60]`, section 4 |
| 0xBC | exec `0x699330` | entity by IID -> `0x635440(entity, table)`: `[ent+0x38]` (slot 14, EntityPropertyProvider, vtable `0x15C9E38`) vt+0x10 lock, **vt+0xA4 = `0x62AFD0`**, vt+0x14 unlock; section 3 |
| 0x13D | (same family) | vt+0xA8 = `0x62B1C0`: the same diff for the network-mode-9 ids only (`0x4FB540`) |
| 0x6 | exec `0x699450` | `0x635360` -> vt+0x50 = `0x629970` -> **`0x578DE0`** (set one) |
| 0x86 | exec `0x699210`, reader `0x839500` (`u8 base | u32 id`) | `0x6353B0` -> vt+0x54 = `0x629980` -> **`0x577E10`** (remove one) |

Event factories registered in `0x690000.c` (`0xB0EC50(id, factory)`): 0xBC `0x6913C0` (object vtable `0x15D1890`, 0x38
bytes, table at +0x20), 0x13D `0x691460`, 6 `0x691500`, 7 `0x6915A0`, 0x13B `0x691640`, 0x86 `0x6912A0`, 0x129
`0x691210`, 0x13C `0x691330`, 0xB0 `0x69AC20` (vtable `0x15D1E54`, exec `0x698CD0`), 3 `0x690CB0`, 0x8D `0x69A340`.

---------------------------------------------------------------------------------------------------------------------

## 2. 0xF2 for a live IID (C)

`0x64D8A0(iid_lo, iid_hi, f2)`: `0x64A3A0(iid)` finds the live entity (or `0x53BFD0` a creation job still running for
it). Then only: `if f2+0x28 != entity+0x110`: (0 == `[0x1B6AB20]` -> the class's own world state by `0x54CAF0`) and
`[0x1B67258]->vt+0x28` (`0x603E70` -> vt+0xD4 = ChangeWorldState `0x54D5C0`: detach, rebuild the components from the
world state, `entity+0x110` = the new value or "none"). Equal -> `return 1`; nothing else is read from the batch.

- `[0x1B67260]` ("none", the value construction writes to `entity+0x110`, `00540000.c:9253`) and `[0x1B6AB20]` lie in
  the zero-filled part of `.data` (raw data ends at 0x1757800): 20 and 2 references in `.text`, **all reads**, no store
  and no address taken -> both are **0** at run time.
- ics sends `struct "<IQI"` = class, parent IID 0, **0** (`DESCRIPTOR_WS_ZERO`, fase3-hs): equal -> no-op. Before
  fase3-hs the counter 1, 2, 3 ... asked for a world-state change on every bundle (the load of DID n failed, P harmless).
- The class DID (desc +8) is not compared for a live object: a bundle with another class changes nothing either.

---------------------------------------------------------------------------------------------------------------------

## 3. 0xBC on a live object: a diff, not a replace (C; corrects champion-animation-matrix.md 1, deep-scan-animations.md 1.2)

`0x62AFD0(table)`, ECX = the property component (its owner entity at +4):

```
0x62AFE1  L = new collection (0x5044E0)
0x62AFED  for each entry of the component's own table (+0x1C, iterator 0x63A210):
0x62B006      if 0x4FB520(descriptor): descriptor+0x16 (network mode) is 1 or 3 -> L.insert(id)
0x62B05F  0x503C60(L, table): delete from L every id the incoming table holds
0x62B0B7  for each id left in L:   component vt+0x54 (remove, 0x577E10)        <- id in eax at 0x62B0C7
0x62B160  for each incoming entry: component vt+0x50 (set, 0x578DE0)
0x62B1A5  destroy L (0x504120)
```

**Set `0x578DE0`** (the same function a 0x6 reaches): old value = vt+0x4C (`0x62A4E0`: client override hash, own
table, then the two class property sources); store it (`0x4BFB00`; a descriptor with flags 0x10000 goes to its
registered handler `0x4FFE90(id)` instead); new value = vt+0x4C again; then
- no old value -> vt+0x98 `0x577EE0` **added**;
- old and new and `!0x4FDC30(old, new)` -> vt+0x9C `0x577F30` **changed**;
- equal -> **nothing**.

`0x4FDC30` = same descriptor and `0x4FC020(value, kind)`: kinds 2, 5, 8, 0x0A, 0x10, 0x11, 0x13, 0x15, 0x16 compare the
word, kind 9 the float, the others the value object's vt+0x24: array `0x4FF770` (same count, each element equal by
`0x4FC1F0`), table `0x5004B0` (same ids, equal values), IID `0x4FB960` (both halves), string `0x4FBCA0` (content, P).
The 18 handler-routed descriptors (flags 0x10000: 0x22, 0x7C, 0xF0, 0x1FF, 0x2AF, 0x35A, 0x3CD, 0x406, 0x461, 0x50D,
0x50E, 0x55E, 0x657, 0x664, 0x6B3, 0x76C, 0x776, 0x7BD) are all engine-local; ics sends none of them, so no handler
runs on a re-sent value.

**Remove `0x577E10`**: had = vt+0x90; erase; still has = vt+0x90; `had && !has` -> vt+0xA0 `0x577F90`: if the class
sources still give a value (vt+0x58) it notifies **changed** to the template value (`0x5777C0` / `0x509220`), else
**removed** (`0x5778F0` / `0x509360`).

**Notifications**: `0x577EE0` / `0x577F30` call the registered watchers (`0x58BA40`: HUD, targeting, graph-variable
binder, the scriptlets' persistent attachments, registered by their base `0x52A660` and re-applying a bound field on a
change, `0x523070`, P for the slot meaning) and, for a
descriptor with flag bit 2 (`0x4FB630`), push the value into every contained child (`0x575B90` -> child
`[+0x38]` vt+0x50).

Consequences:
- A bundle identical to the previous one fires no property notification at all.
- Ids **not** in the table survive when their network mode is 0, 2, 4-9 (0x90F hidden, 0x956, 0x10000133 ... stay as
  last set); ids with mode 1 / 3 are removed. 232 descriptors have mode 1 / 3 (properties-complete.tsv).
- The scriptlet tables `0x7D2` (array, container 4, **net 1**, flags 0x620000) are read by the script component only
  at construction: the component gate `0x58CB60` (0x7D2 or 0x954 present) and the table read `0x58EDD0` (from vt+0x70
  `0x627270` -> `0x57A8E0`; construction vt+0x24 `0x57D8E0`). These are the only code sites of the id besides an
  unrelated `0x41BA15`: no watcher. A bundle *without* 0x7D2 would remove it (net 1) but nothing reacts; a bundle
  with the same list changes nothing. `0x5B5` (graph, did, **net 0**) is read only by the animation component's
  (re)initialisation `0x556D70` / `0x556DC0` (from `0x60D690` / `0x60D6C0`; the only code sites of the id), not on a
  property change, and it is never in an ics bundle (C log: the 60 ids sent are listed in 5.1).

---------------------------------------------------------------------------------------------------------------------

## 4. 0xB0 on a live object (C; extends client-movement.md 1.2)

Listeners at `[ent+0x60]` called by `0x6298D0` (vt+8 of each):
- **Movement component** (listener sub-object at C+0x10, vtable slots `0x15C5F54` = `0x60AED0` first block,
  `0x15C5F64` = `0x60AFA0` updates). `0x60AFA0`: returns at `0x60AFB4` unless the first block was applied (`C+0x318`);
  `0x57DA90` merges the block field by field (nothing when it has no sub-flags and no motion flags); `0x57E0E0` /
  `0x57DD70` build the state; if it carries time / position (`0x57D990`) -> `0x609C70` pushes it (result in al at
  `0x60B00B`: older states and duplicates are dropped); if it carries the module (`0x57DEF0`) -> `0x553E70`: **the
  same module sequence byte is a no-op** (`comp+0xB5 == seq` -> return 1), a newer one switches the movement mode
  (property 0x57A, vt+0x58 / +0x74 / +0x78, listeners); then the module's vt+0x68 `0x60BB00` (seq C newer -> history
  flush `0x60A040`).
- **Containment** (`0x6113E0`, vtables `0x15B52C0` / `0x15B5370`): parent IID at block+0x10; non-zero -> attach
  (`0x634C70` -> `0x58A220` -> `0x55F930`) or queue it until the parent exists (`0x64DDA0`); **zero -> `0x64B330`,
  which only erases a queued attach**: an attached child is not detached by a parent IID of 0 (O for how ics' detach
  works; liftables area).

So the 0xB0 of a bundle to a standing object whose state did not change (same position within 0.05 m, both at rest,
same seqs) is dropped as a duplicate; to a moving one it is one more dead-reckoning anchor. What the graph sees is
only the replayed motion (Propel / Turn, `0x6097E0`), and a facing change is a one-step Turn.

---------------------------------------------------------------------------------------------------------------------

## 5. What the logs show (C, traffic.log 14:39-15:17)

### 5.1 Bundles
- 6 173 labelled 0x4 batches, **every one F2 + B0 + BC**, F2 world-state u32 = 0; the per-tick bundles of
  `Session._tick` have label None and are not logged.
- Ids sent in 0xBC (60): `0x2A1 0x3CE 0x50F 0x7D2 0x90F 0x956 0x1000000C 0x10000029 0x10000064 0x10000083 0x1000009C
  0x100000AF 0x100000CF 0x100000FA 0x1000011E 0x10000133 0x10000140 0x10000142 0x10000167 0x1000019D 0x100001AF
  0x100001C3 0x100001D3 0x10000249 0x10000337 0x10000338 0x1000034C 0x1000035E 0x10000384 0x10000426 0x10000432
  0x10000433 0x10000484 0x100004DA 0x100004E2 0x100004FF 0x100005E4 0x100005E8 0x10000637 0x100006BC 0x100006BD
  0x100006C1 0x100006FE 0x100007A2 0x100007D9 0x100008E4 0x100008F0 0x100008F1 0x10000A23 0x10000AA7 0x10000B75
  0x10000B76 0x10000B7A 0x10000B7B 0x10000B7E 0x10000B83 0x10000B84 0x10000C5B 0x10000C5D 0x10000CD6`.
- Values that differ between consecutive labelled bundles of one object (notified as changes): credits `0x1000035E`
  232, LifeState 210, rank flags `0x100006C1` 207, hidden `0x90F` 181, XP 48, move speed 34, stats 12-15 each.
- **Removals** (first labelled bundle after a 0x6 of a net-1/3 id the bundle lacks; unlabelled tick bundles and the
  5 s idle resend remove them earlier):

```
14:40:37.488 credits 510                              removes 0x1000019d               (0x6 at 14:40:32.471, champion)
14:41:32.504 bot AI: Atomic Wonder Woman (in world)   removes 0x1000019d 0x10000029 0x10000249 (0x6 at 14:40:33.285)
14:42:07.381 AI: Atomic Wonder Woman stops to cast    removes 0x1000019d 0x10000029 0x10000249 (0x6 at 14:41:33.354)
14:45:13.533 mid ranged 3 t2 w6: state (84.7, 77.2)  removes 0x100003f3               (0x6 at 14:45:12.925)
14:50:39.542 AI: Atomic Wonder Woman stops where it falls  removes 0x1000019d 0x10000029 0x10000249
14:53:28.472 turret mid t1 dead                       removes 0x10000c66               (0x6 at 14:53:22.511)
```
  The champion's `0x10000B2D` (`World.on_cc`, 0x6 only) goes the same way at the next champion bundle while a CC lasts
  (C code: `properties()` never lists it).

### 5.2 Timelines of the reported bugs
- **Meltdown** 14:52:10.333 on AWW: script `0x340002B4` hook 1 (.340), hook 5 (.456, S1 -> S3), **hook 2 (.516, S3 ->
  S2: ReleaseFacing, S2 -> S0)**: the channel ends 0.18 s after the cast; two waves (missiles `0x40000484` .478, .717);
  the server stops `Vfx_Atm_Glt_Meltdown_Tgt_Active` on AWW at .725 (0x8D signal 1). AWW's bundles in the window
  (.409 "stops to cast", .424 "forced movement ended") have speed 0. Cause: the timed graph hook (deep-scan-animations.md
  0 #2), not a bundle.
- **Lift** 14:41:43: AGL "stops to cast" .466 (facing 17682), "faces vehicle 6" .479 (facing 12970, a 27 deg turn,
  applied by the client ~.58), graph event CarPickup .578, SuperStrength_PickupObject .579, **vehicle "carried over
  the head" .579: z 200.08 -> 202.58 at once** (no parent block, a 2.5 m jump = a snap), 0x8B rebuild .657. The
  vehicle is shown at the held point before the lift clip has raised it (P: the "cut to already lifted"); the AGL turn
  lands 0 ms from the pickup's first frame.
- **Death**: a bot's "stops where it falls" bundle carries LifeState 2 (the change is notified with the bundle), then
  0x6 LifeState 2 (no change) and `0x100000AD` 1 ms later; the local champion's "dead (LifeState 2)" bundle has no
  graph event at all (death-animation.md). Not a bundle effect.

---------------------------------------------------------------------------------------------------------------------

## 6. The reported symptoms against these facts

| Symptom | Bundle-caused? | Evidence | Status |
|---|---|---|---|
| Shards sphere vanishes while attacking | **no** | fase3-ic config note (12:27 log): it went with each basic attack's `Combat_Basic_Attack 0x10000128` after the facing bundle had been suppressed; section 2-4 | **O**: what ends the 0x0C child (`0x666B40`) -> diag `--bundles` |
| Grab's arm missing | no | the beam lives as long as its run (grab-beam.md 2); a bundle neither ends the run nor the missile | **O** (`0x659B00` end, the per-frame end resolution of grab-beam.md 3) |
| Camp phase-in lost when attacked | no | the chase bundle cannot end the type 8 run (sections 3-4); the hit / status scriptlets can (P) | **O** (`0x65CA30` end) |
| Lift cut to the held pose | indirectly | the vehicle's own bundle snaps it 2.5 m up at the pickup (0xB0 content) | P (liftables) |
| Meltdown waves stop on a moving target | no | server script hook 2 at +0.18 s (5.2) | C (Meltdown / graph hooks area) |
| Stun / knock-up / CC animation cut by the next update | **yes** | removal of `0x100003F3` / `0x10000B2D` (5.1) watched by `CbtState_GetUp`, `_Combat_GoToLocomotion`, `CbtState_KnockUp` (client-scriptlets-graphs.md 1.5) | C mechanism, P visual |
| Skill clip cut when the champion turns | yes, by any 0xB0 | Turn != 0 one step; the Lua early-outs | C (champion-animation-matrix.md 1) |
| Bot invisible / not updated with 0xB0-only states | the opposite | 0x90F only in full bundles | C code |

### 6.1 The current workarounds, re-read

| Key (all `[ics]`) | What it really does | With the update path of section 7 |
|---|---|---|
| `resend_looping_after_bundle` (+ `resend_looping_delay`) | after every full bundle, a **new** run (new instance) of each looping key: a second sphere set beside the first (the first was not dropped) | only after full bundles (creation / retries): inert for updates |
| `resend_looping_after_scriptlet` (0.35) | same, after any other scriptlet on the object; the only workaround that matches the 12:27 evidence | keep until `--bundles` shows the sphere's end; then target the real cause |
| `face_min_turn_degrees` (20) | fewer facing snaps (fewer Turn steps) | keep: the Turn effect is real |
| `missile_bundle_on_turn` / `missile_turn_radians` | fewer missile states | keep the throttle; the states become 0xB0-only |
| `missile_rebundle_scriptlets` (["Vfx_Active"]) | a **second** Vfx_Active run (second beam) after each turn bundle | off in the update path |
| `liftable_hold_champion_bundles` | holds whole champion updates during a carry (facing included) | keep (it holds Turn steps), revisit after a test |
| `match_camp_phase_resend` | a second phase-in run after each full bundle | inert for updates (resends only after full bundles) |
| `bot_motion_only` (false) | full bundles for bots because of the 0x90F gap | superseded: bots use the update path |
| `champion_scriptlet_delay` (0.13) | the champion's 0x8D go 0.13 s after its bundle | keep: a movement state is applied 0.1 s after its stamp (`0x60B5F0`) and an 0x8D at once, so the stop / face lands before the skill's graph event (C mechanism) |
| `descriptor_world_state_zero` (true) | keeps the 0xF2 a no-op | **must stay true** |

---------------------------------------------------------------------------------------------------------------------

## 7. What a correct update is (C for the client side, P for the visible result)

- **Create** (and retry a creation the client may have dropped): the full 0x4 (0xF2 + 0xB0 + 0xBC), as today.
- **Move / stop / face / teleport / attach**: a 0x4 batch with **only the 0xB0** (`M.pvp_movement_state`; the batch form
  is deferred with a pending creation and re-shows an object removed less than 30 s ago, `0x64BD30`). Send it when the
  motion changes (start, stop, corner, facing, speed, seq A / B, parent) plus a refresh while moving; an unchanged
  state is dropped by the client anyway.
- **A property that changed**: one 0x6 (`M.set_property`) per id; it fires exactly the notification the bundle's set
  fired for that id, and nothing else.
- **A property the server drops** (recall block, sold item block ...): one 0x86 (`u8 0 | u32 id`) for that id.
- **Never** a 0xBC after creation unless it lists every net-1/3 id the server ever set on the object.
- Stop / facing states that must land before a graph event sent in the same tick can carry a time stamp up to 0.1 s
  in the past (the replay applies the newest state with time <= now - 0.1, `0x552130`), never older than the object's
  last state (older states are dropped, `0x5525A0`) (P).

---------------------------------------------------------------------------------------------------------------------

## 8. Runtime check: `python tools\diag.py --bundles` (Spanish `--paquetes`)

Added 2026-10-28 (only breakpoints, the game's memory is not changed). Run it in a second console with the game open
(menu or match), play AGL: E (Shards) then basic attacks, Grab a minion, attack a jungle camp while it phases in;
Ctrl+C and send `logs\diag.log`.

| rva | log line | reads |
|---|---|---|
| `0x22AFD0` | `HOT BUNDLE 0xBC table` | object IID, number of ids sent |
| `0x22B0C7` | `HOT BUNDLE 0xBC REMOVES an omitted property` | id (eax), object |
| `0x20AFB4` | `HOT BUNDLE 0xB0 dropped (movement not created yet)` | object |
| `0x20B00B` | `HOT BUNDLE 0xB0 state` | pushed (low byte of eax), object |
| `0x266B40` | `STACK BUNDLE scriptlet child END` | owner IID, request, **call stack** |
| `0x25CA30` | `STACK BUNDLE scriptlet render effect END` | owner IID, effect, **call stack** |
| `0x259B00` | `STACK BUNDLE scriptlet beam END` | owner IID, beam, **call stack** |

Reading the stacks (rva): `0x22AFD0..0x22B1A0`, `0x178DE0`, `0x177E10..0x177F90` = a property change (bundle or 0x6);
`0x2298D0`, `0x20AFA0` = a movement state; `0x2279D0`, `0x134BF0` = an 0x8D start / signal; anything else = the
client's own logic (graph, run end). Expected with today's server: REMOVES lines for 0x1000019D / 0x10000029 /
0x10000249 on the bot; the sphere's END with an 0x8D or a run-end stack, not a 0x22AFD0 one.

---------------------------------------------------------------------------------------------------------------------

## 9. Open

- O: what ends the Shards shells, the camp phase-in effect and Grab's beam (section 8).
- O: how a carried object is detached (a parent IID of 0 only clears a queued attach, section 4).
- O: carrier-class props (exe patch cave X writes the world state into the creation info): whether their
  `entity+0x110` is then non-zero, in which case every later 0xF2 (u32 0) would rebuild them; the update path below
  avoids 0xF2 for them entirely.

---------------------------------------------------------------------------------------------------------------------

## 10. Implementation plan (not applied in this step)

All new keys in `ics/config.py` `[ics]` with the comment "2026-10-28 (tester report 2026-10-28 15:00;
docs/re-notes/object-update-bundles.md ...)" and the old behaviour one setting away.

### 10.1 Config
| Key | Default | Meaning / revert |
|---|---|---|
| `object_update_mode` | `"delta"` | `"delta"`: after the creation bundle, motion as 0xB0-only states and properties as 0x6 / 0x86; `"bundle"`: a full 0x4 per update, as before |
| `delta_motion_refresh` | `{"champion": 0.5, "default": 1.0}` | s between motion states while moving (0 = only on change) |
| `delta_remove_missing` | `true` | 0x86 for ids that left the server's property list (false = leave them, like a 0x4 for net-0 ids) |
| `delta_player_object` | `false` | the player object's bundle with every champion update (true = as before) |
| `delta_vitals_with_motion` | `false` | 0x42 with every champion update (true = as before; vitals already go on every change) |
| `motion_state_backdate` | `0.0` | s subtracted from a stop / face state's stamp (never before the last state + 0.001); P value 0.1 to land a turn before a same-tick graph event |

### 10.2 `ics/messages.py`
- `remove_property(object_id, prop)` = `build_message(object_id, 0x86, b"\x00" + struct.pack("<I", prop))`.
- `pvp_movement_state(..., parent=None)`: the parent block exactly as `create_object` builds it (flag 0x04, u64 IID,
  u32 mode, mode 0x10 extra `{u32 point, u8, u8}`), so attached objects move with 0xB0-only states.

### 10.3 `ics/world.py`
- `Entity.__init__`: `client_props = None` (id -> (kind, value) last sent; None = not created on the client),
  `client_motion = None` (last motion key and its time).
- `World.bundle()`: after building, `ent.client_props = {id: (kind, value)}` of the table, `ent.client_motion` = its
  motion key (position rounded to 0.01 m, heading / facing rounded to 0.001 rad, speed, tele_seq, second_seq, module,
  parent, time).
- New `World.delta(ent, label)`: (1) motion key changed, or moving and `now - last >= refresh` -> `M.pvp_movement_state`
  (time = now, or `max(last + 0.001, now - backdate)` when the new speed is 0 or only the facing changed);
  (2) `props = self.properties(ent)`: every (id, kind, value) different from `client_props` -> `M.set_property`;
  with `delta_remove_missing`, every id of `client_props` no longer listed -> `M.remove_property`; update
  `client_props`. One `self.send(label, b"".join(messages))`, motion first (the bundle's order); nothing when empty.
- `World.update(ent, label=None, force=False, full=False)`: keep `bundle_hold`; in delta mode with
  `ent.client_props is not None` and not `full` -> `self.delta(ent, label)` and **no** `_resend_looping`; else the
  full bundle and `_resend_looping` as today.
- `full=True` at the creation retries: `liftables.py` "again" (`liftable_resend`), `tour.py` "again", and wherever
  an object is re-created after `remove` (`World.remove` clears `client_props` / `client_motion`, so a re-add is a
  full bundle by itself).
- `World.send_entity()`: delta mode -> `self.update(ent, label)` for bots too (`bot_motion_only` only in bundle mode).
- Optional: a helper `World.set_prop(ent, pid, kind, value, label)` (0x6 + record in `client_props`) for the direct
  0x6 sends (`_late_flags` 1087, `bot_late_properties` 365-373, `vital_notices_on`, `Combat.on_cc` 2910, the death /
  respawn LifeState, `match.py` 339, `units._late_flag`), so the delta does not repeat them.

### 10.4 `ics/session.py`
- `_tick()`: delta mode -> `w.update(ent, None)` for every changed entity (champion included; no `_objects()` per
  tick, no player-object bundle, no 0x42 unless `delta_vitals_with_motion`); missiles through `_missile_motion`, which
  in delta mode sends `w.update(ent, None)` on a turn / stop and skips `missile_rebundle_scriptlets`.
- Idle resend (`[timing] idle_resend`): bundle mode only; delta mode sends nothing for an unchanged champion.
- `_objects(link)` stays the champion's creation / link / load-complete message; afterwards set `w.champion.client_props`
  / `client_motion` from what it sent.

### 10.5 Tests to add
- `tests/test_match.py` (no ports, `FakeSession`, decode the frames as in this note):
  1. delta mode: a spawned unit's first message is a 0x4 with F2 + B0 + BC; after a step of movement `w.update` sends a
     0x4 whose batch is exactly `[0xB0]` with speed > 0; a second `w.update` with no change sends nothing;
  2. a fog flip (`w.fog()`) on an enemy bot sends a 0x6 for `0x90F` and no 0x4 (the fase3-hy gap);
  3. an id removed from `extra_props` sends one 0x86 with that id; a changed credits value sends one 0x6;
  4. a teleport (`w.teleport`) sends a 0xB0 with the new seq A; an attached rock's state carries the 0x04 parent block;
  5. `object_update_mode = "bundle"`: every update is the same full 0x4 bytes as today;
  6. `w.remove` then a re-add sends a full 0x4 again; a missile turn in delta mode sends 0xB0 only and no Vfx_Active.
- `tests/test_session_flow.py` (`SESSION_TEST_PORT`): after the link, the champion's tick messages carry no 0xF2 for
  the champion and no 0x4 to the player object `0x0200000000000001`.
- `tests/test_ics.py` (`ICS_TEST_PORT`): the Tutorial's objects are still created (full 0x4), the champion's walk gives
  0xB0-only batches.

### 10.6 What the tester should see
- Same creation, movement and visibility; fewer messages (no full bundle per tick).
- Enemy bot, minions, camps keep their targeting flags, tags and CC locks: a stun / knock-up is no longer ended on the
  client by the next movement update; an enemy bot leaving the fog shows at once.
- No change expected from this alone for the Shards sphere, Grab's arm, the camp phase-in (not bundle-caused, O) nor
  for Meltdown (server script) or the death fall (death-animation.md); `diag.py --bundles` tells what ends the first
  three.

---------------------------------------------------------------------------------------------------------------------

## 11. Finalizer check (2026-10-28, spot checks after the investigation; nothing re-investigated)

Re-verified (C, decompilation + capstone on `InfiniteCrisis.exe`; every range below is byte-identical in
`InfiniteCrisis_patched.exe`):
- 0xBC diff `0x62AFD0`: own-table ids whose descriptor+0x16 is 1 or 3 (`0x4FB520`) go to a list, `0x503C60` takes out
  the incoming ids, vt+0x54 per id left (`push eax` 0x62B0C7, `call [ebx+0x54]` 0x62B0CB, `[ebp-4]` = the component),
  then vt+0x50 per incoming entry. Set `0x578DE0`: "added" (vt+0x98) with no old value, "changed" (vt+0x9C) only when
  `!0x4FDC30(old, new)`, an equal value fires nothing. Remove `0x577E10`: vt+0xA0 only when had && !has.
- 0xF2 `0x64D8A0`, live IID (or a creation job with +0x10 set): only `f2+0x28 != entity+0x110` -> `[0x1B67258]`
  vt+0x28, then `return 1`.
- 0x6: exec `0x699450` -> `0x635360(entity, event+0x20)` (lock, vt+0x50, unlock). It has no network-mode filter, so a
  net-0 id (0x90F) goes through the same setter as in a bundle. 0x86: factory `0x6912A0`, vtable `0x15D1850` (+4 exec
  `0x699210` -> `0x6353B0(entity, u32 [event+0x20])` -> vt+0x54; +0x1C serializer `0x839500` = base u8 `0xB0D380` +
  u32). Its event flags word is 0x300400, the same as 0x6 / 0xBC / 0xB0 / 0x3, which ics already sends.
- Descriptors (properties-complete.tsv): 0x1000019D, 0x10000029, 0x10000249, 0x100003F3, 0x10000B2D, 0x10000C66,
  0x100000FA, 0x7D2 have net 1; 0x90F, 0x1000035E, 0x10000133, 0x956, 0x5B5 have net 0.
- Immediates in `.text`: 0x7D2 only at 0x41BA2D (unrelated cmp), 0x58CB6F (gate `0x58CB60`), 0x58EDE1 (table read
  `0x58EDD0`); 0x5B5 only at 0x556D93 / 0x556DE0 (plus two unrelated `imul` constants, 0x11510F8 / 0x115117A). A
  watcher registered through a data table would not show in this scan (P).
- Server code: no update path exists yet (no `object_update_mode`, 0x86 builder or `client_props` in `ics/` or
  `tests/`). `M.set_property` uses the same `pack_property` as the bundle's table, so arrays and tables can go by 0x6.
  `M.pvp_movement_state` has no parent block. The keys of 6.1 exist with the defaults stated there.

Gaps and contradictions:
1. **Logs gone**: `logs/` is empty (since 18:49) and no copy of the 14:39-15:00 logs survives. Sections 5.1 / 5.2 were
   not re-read. The removal mechanism they show agrees with the code: `vital_notices_on` sets 0x1000019D by 0x6
   (world.py:571-572) and the champion's `properties()` never lists it; the same holds for units (`_late_flags`
   world.py:1086-1087, units.py:311-334).
2. **Claim 5 has direct runtime evidence the note does not cite**: test-2026-10-25-2207.md BOT-1. In fase3-hx the death
   stop went as `stops where it falls (0xB0)` (0xB0-only), and that note says "no slide while dead in this build ... The
   fase3-hx stop state works". The fase3-hy switch to full bundles rested on "the bot stood up only at the next full
   bundle". The same note shows the server sent no movement at all between the respawn and the first attack, so that
   was never evidence against 0xB0-only. "Invisible until it attacks" was not reproduced there. The 0x90F gap is real
   in the code (`_tick` sends `w.motion_update()` for a bot that only `fog()` changed, and it returns None for an
   unchanged motion key; session.py:1139-1146) but is not the documented cause. The lying-down walk has its own fix
   (`bot_getup_delays` / `bot_getup_scriptlets`, 2026-10-26 19:51).
3. **Not explained by sections 3-4**: world.py:1049-1050 / 1081-1082 record two `diag --target` runs (2026-10-21
   23:30, 2026-10-22 08:13). Unit flags sent in a second full bundle never reached the unit component's cache (+0xA4);
   the same value by 0x6 did. By section 3 both reach `0x578DE0` with the same notification. Likewise `death_as_property`
   (config.py:816-818, 2026-10-23 11:28): LifeState 2 alone by 0x6 brought no grey death screen, while the full bundle
   did. P reconciliation: all three runs predate fase3-hs, so every bundle's 0xF2 carried the sequence counter, and
   `0x64D8A0` called ChangeWorldState before the 0xBC was applied (wire order). Then section 2's "P harmless" is
   doubtful, and the counter is the likely origin of the "a bundle re-creates the object" belief. Consequences: keep
   `descriptor_world_state_zero` true and no 0xF2 in any update. The delta path's 0x6 is the runtime-proven form for
   flags, but the champion's death (world.py:1648) and respawn (`send_champion`, world.py:1791) should stay full
   bundles until a test shows the grey screen and the base snap with the delta form.
4. **Plan 10.4 misses the champion's labelled path**: every `w.send_champion()` goes through `champion_sender` ->
   `Session._objects()` (session.py:833: champion bundle + 0x42 + player-object bundle), and so does the stop order
   (session.py:1445). In delta mode they go to `World.delta`. `_objects()` stays for create (870), link (1095), in
   world (1186), after the cinematic (1243) and `player_rebind` (1279). The map-load property 0x100001D3 reaches the
   player object with the link (its second bundle), so dropping the idle resend does not touch the load.
5. `send_champion()` runs `vital_notices_on()` after every champion send (0x100000CE, vision 0 -> r, unit flags 0 -> 8,
   all by 0x6). Those toggles are needed only because each bundle removes 0x1000019D. In delta mode run it after a full
   bundle only, otherwise every labelled update flips the champion's kind to 0 and back.
6. **`delta_remove_missing` is unsafe as planned**: `client_props` must mark the ids sent by 0x6 outside `properties()`
   as server-owned: late unit flags and tags, CC attributes (world.py:2877), the order lock (2910), LifeState
   (world.py:1615, match.py:1363), 0x10000C66 (units.py:217), unit team / vision toggles. Otherwise the 0x86 pass
   re-creates the removal bug. The `World.set_prop` helper of 10.3 is required, or the 0x86 pass covers only ids that
   came from `properties()`.
7. 0x86 has never been sent by this server: the path is C, the runtime result P. Check it in the first test (after a
   recall or a sale, the block's button goes away).
8. Documentation: session.py:1158-1159 calls the per-tick missile bundle dropping Grab's beam "grab-beam.md, C", but
   grab-beam.md 23-26 ranks it only as a P suspect (and its "replaces ... its 0x7D2 tables" is corrected by section 3).
   `docs/re-notes/full-index.md` does not list this note.

---------------------------------------------------------------------------------------------------------------------

## 12. Skeptic review (2026-10-28, independent re-check; no code changed)

Verdict: **partly confirmed**. The core holds, re-derived with capstone on `InfiniteCrisis.exe` rather than from the
sections above: a bundle to a live object rebuilds nothing; its 0xBC is a diff that removes the own-table net-1/3 ids
it omits; 0x6 / 0x86 reach the same setter / remover. The plan of section 10 is sound with the amendments of 12.3.
Death / respawn stay full bundles (11.3).

### 12.1 Re-verified independently (C)
- **Same storage.** `0x578DE0` stores through `0x4BFB00` with ECX = component+0x18, which hashes at +0x1C
  (`0x4BFB16`). `0x62AFD0` iterates `[component+0x1C]` (`0x62AFEA`). `0x577E10` erases at component+8+0x14
  (`0x577E3E`). So an id set by 0x6 sits in the table the diff walks.
- **"has" lookup.** "has" (vt+0x90 `0x62A460`) reads the client override hash (component+0x90 / +0x9C) first, and the
  own table (`0x576110`) only when the id has no override. A removal therefore notifies for every id the server set.
- **0x86.** Factory `0x6912A0`: id 0x86 (`0x69130F`), flags 0x300400, vtable `0x15D1850`. Serializer `0x839500` = base
  u8 + u32 at +0x20. Exec `0x699210` -> `0x6353B0(entity, u32)` (`0x69927B`) -> vt+0x54.
- **0x6 reader.** The serializer `0x445530` reads its value with the generic property reader (`0x5015F0` ->
  `0x500CC0`).
- **0xF2.** The compare is `cmp eax,[esi+0x110]` at `0x64DA6B`.
- **The 60 bundle ids.** None is handler-routed (flags 0x10000). 39 have net 1/3. `0x100001D3` is container 3.

### 12.2 Corrections
1. **Dispatch vtable (section 1).** `0x64E070` is slot +0x3C of vtable `0x15CDC70`, which `0x64B8BD` stores at
   object-manager+0x10. `0x64BD30` sends every sub-event through slot +0x18 `0xB0C730`, which routes by routing+0x28
   (type 1 -> +0x3C = `0x64E070`). "vtable 0x15CDC90 +0x1C" names the same slot (0x15CDCAC) from a wrong base.
2. **Deferral (sections 1 and 7).** An event for an IID that is not live is deferred only when the routing u64 at +8
   is non-zero (`0x64E206`-`0x64E22D`). Otherwise the exec runs and returns 0x80004002, so the event is dropped. The
   same holds for each sub-event of a 0x4 batch. A whole batch is deferred only while its IID waits for its landblock
   (`0x649720`), not during an ordinary async creation job. What fills the routing word for server messages is O.
3. **Who loses what (0.3, 5.1, 10.6, 11.1).** Units keep 0x1000019D and the tags: tutorial drones, minions, camps and
   structures. `World._late_flags` (world.py:1080) and `Units._late_flag` (units.py:333) also store the flags in
   `ent.extra_props`, which is why those ids appear among the 60. `refresh_flags`, `late_team` and `_late_vision`
   re-send ids that `properties()` already carries. 11.1's "the same holds for units" is therefore wrong, and 10.6's
   "minions, camps keep their targeting flags" is not a change. Today these ids are sent only by 0x6, so the next
   bundle removes them:
   - champion: 0x1000019D (world.py:571-572);
   - bot: 0x1000019D, 0x10000029, 0x10000249 (world.py:365-368);
   - the champion and the client_vitals entities (bots, minions, structures): the CC flags 0x100003F3, 0x100007FE,
     0x10000B39 and 0x100005A3, all net 1 (world.py:2875-2878), and 0x10000B2D (2910);
   - the tutorial's knockdown flags (director.py:480-482);
   - the turret target 0x10000C66 (units.py:215-217).

   The champion gets no tags.
4. **Stronger CC evidence (C, code).** `on_attribute` sends the CC flag by 0x6 and then calls `on_cc`. For a moving
   target `on_cc` sends `w.update(e, "stopped (crowd control)")` (world.py:2903), a full bundle in the same burst. So a
   moving unit's stun is set and removed back to back, before any later update. A knock-up (forced motion) loses it at
   the next per-tick bundle. Expected in the delta build: stuns on moving minions and bots show.
5. **Visible effect of a removal.** `0x577F90` notifies "changed" to the class value when vt+0x58 finds one. The CC
   bools really end. The unit flags and tags may fall back to a class value, so their visual effect is P. 0.3 and the
   RE summary state it as fact.
6. **Open item 9 (carrier props) closes, C from the decompilation.** Only `0x54AA50` (init "none",
   00540000.c:9253) and ChangeWorldState `0x54D5C0` (11873 / 11876) write entity+0x110. Caves X / Y / Z only change
   the class and world-state lookup. A carrier prop's 0xF2 with u32 0 is a no-op, as for any object.
7. **11.3's reconciliation is unlikely (P).** `0x54D5C0` builds the key {DB type 0x2D, DID n} (`0x5DFBA0`) and
   returns 0x80004005 at the null load, before the detach `0x54D410`. Type-0x2D records are the 0x2E...... world
   states, so a bare counter n most likely never loaded. The three old observations stay O.
   - A copy of the 2026-10-22 08:13 run survives at
     `C:\Users\Krizalid\AppData\Local\Temp\claude\C--Infinite-Crisis-Server-server\logs-0813`. It holds 03MeleeC's
     creation at 08:13:10.891 (5 ids, 0xF2 u32 1) and the "unit flags 0x10000" bundle at 08:13:11.693 (adds
     0x1000019D, u32 10). The diag's flags breakpoint `0x5D0323` has no hit after 08:12:54, so that log does not show
     the flags "still 0 after a second bundle".
   - The 11:28 "grey screen" is P the fog (death section of the RE doc). Its source check `0xAB12C0` reads the unit
     cache and `0x9CFAF0`, so it is no clean bundle-vs-0x6 test either.

### 12.3 Plan amendments (section 10)
a. **Motion key.** With the position in the key, every tick of a moving object differs, so `delta_motion_refresh`
   never applies. Use the velocity key of `World.motion_update` (destination, speed, heading threshold). For the
   first test, today's cadence can be kept on purpose: a 0xB0-only state on every tick the entity changed. That test
   then changes only the 0xF2 / 0xBC.
b. **`delta_remove_missing`.** Send 0x86 only for net-1/3 ids, which is what a full bundle removes today.
   - Net-0 ids that `properties()` drops stay on the client today: bonus 0x100008F2 after `clear_bonus`, a sold
     item's 0x100008E5-ED, 0x90F. Removing them is a new HUD path, so it needs its own key, default off.
   - The server needs each id's network mode (MasterProperty 0x32000000 or properties-complete.tsv).
c. **No repair path.** A per-tick bundle or the idle resend used to overwrite any lost state; a delta is never
   repeated. A 0x6 or 0xB0 sent while the object's creation job runs can be dropped (12.2.2). Mitigations:
   - send deltas only after load complete and a short delay after the object's creation bundle; send full bundles
     before that, while no 0x6-only id exists yet;
   - replace the idle resend with an idempotent resync: re-send the motion state at rest (an unchanged state is
     dropped by the client) and every `properties()` id by 0x6 every few seconds (equal values notify nothing,
     `0x578DE0`). Never send a 0xBC.
d. **0x6 with array / table values is new.** ics has never sent one (`set_property(..., KIND_TABLE / KIND_ARRAY)`
   does not occur in ics/). The plan would send by 0x6 the rank array 0x100000AF, 0x7D2, the item blocks, the Stolen
   Power tables 0x100008F0 / F1 and the bonus table 0x100008F2. The reader is generic (12.1), so this is P. Test it:
   rank a skill (pips and "+"), buy and sell an item, use a pad.
e. **Toggles after full bundles only.** Run `vital_notices_on` and `bot_late_properties` only after a full bundle of
   that object: the toggles exist only because bundles remove the ids. Optional: quantize credits before comparing
   (`ch.gold` changes every tick).
f. **Unchanged.**
   - Death, respawn and creation retries stay full bundles.
   - `descriptor_world_state_zero` stays true.
   - `liftable_hold_champion_bundles` is kept.
   - Without the idle resend, the 2 s time sync still keeps the connection alive (full-protocol.md 2.3).

### 12.4 Screenshots
Screenshots 42-47 (46 viewed): the SHOP page, the stealth fields, the SUV gap and the grey camp Tripods without an
overhead bar. None of them is explained by the 0xBC diff or the 0xB0: the camps' flags and LifeState are in their
bundles.

**Go-ahead: yes, with 12.3 a-e.**

---------------------------------------------------------------------------------------------------------------------

## 13. Implemented (fase3-if, 2026-10-29)

Section 10's plan with 12.3 a-f applied. Every key is in `ics/config.py` `[ics]` with the comment "tester report
2026-10-28 15:00"; `object_update_mode = "bundle"` puts back the fase3-ie messages exactly (byte-identical builders).

### 13.1 Network modes from the install (C)
`Data.network_mode(prop)` (`ics/gamedata.py`) reads the client's own MasterProperty record `0x32000000` (pack
`0xA0000039`, 97 784 bytes) once: unpack `0x502750`, whole words only (u32 tag 1 / 2 / 3 / 0x81 / 0x82 / 0x83, then
`w0` = id | kind << 16, `w1`, `w2` with the network mode in byte +2, `w3` flags; tag 2 / 0x82 + a u32 EnumMapper, tag
3 / 0x83 + two words; tags 0x8x + a default / minimum / maximum for flags 0x800 / 0x1000 / 0x2000 and a member set for
0x200000). On this install it parses **3 822 descriptors to the record's exact end (offset 105 440) with every network
mode equal to properties-complete.tsv** (0 mismatches; modes 0: 3 478, 1: 213, 2: 15, 3: 19, 4: 5, 5: 49, 6: 31, 7: 3,
8: 6, 9: 3), in 0.09 s; no default of a complex kind occurs. A record that does not parse gives no modes, and then no
0x86 is ever sent.

### 13.2 The update path (`ics/world.py`, `ics/session.py`, `ics/messages.py`)
- What the client was told, per object: `client_props` (id -> the packed entry), `client_motion` (wire position to
  0.01 m, heading 0.001 rad, speed, seq A / B, module, attach block) and its stamp, `client_created_at`,
  `client_full_in_world`. `World.bundle` and `Session._objects` (the champion) record them; `World.remove` clears them
  (an object added again is created by a full bundle).
- `World.update(ent, label, force, full, motion, toggles)`: the carry hold as before; in delta mode `World.delta`
  unless a full bundle is needed: `full` (creation retries `liftable_resend` / `carrier_resend` "again"; a champion's
  death / respawn while `delta_full_on_life_change`), no `client_props`, within `delta_create_window` (0.5 s, real
  time) of the creation, the first update in the world of an object last sent while loading (`delta_full_after_load`),
  or an array / table that changed (`delta_complex_as_bundle`). A full champion bundle in delta mode is followed by
  `vital_notices_on` (12.3 e).
- `World.delta`: in the bundle's order, one 0x4 batch with only the 0xB0 (`pvp_movement_state`, now with the 0x04
  attach block; `movement_block` builds both, byte-identical to the fase3-ie builders for 72 argument sets) when the
  motion key changed (motion None), when the caller's throttle says so (True) or never (False); one 0x6 per id whose
  packed entry differs; one 0x86 (`remove_property`, `u8 0 | u32 id`) per id of network mode 1 / 3 that left the list
  (`delta_remove_missing`; net 0 only with `delta_remove_net0`). One send, labelled `<label> [delta: 0xb0, 0x6 xN,
  0x86 ids]`; nothing when nothing changed (server.log says so for a labelled one).
- `Session._tick` (delta mode), at the cadence each path had (12.3 a): the champion `w.update(ch, None, force=True)`
  every tick it changed (no player-object bundle or 0x42: `delta_player_object`, `delta_vitals_with_motion`); a bot
  `w.update(bot, None, motion=w.motion_due(bot))`, so a standing bot's fog flip `0x90F` goes by 0x6 (5's gap); a
  missile's turn `w.update` and no `missile_rebundle_scriptlets` replay; anything else `w.update(ent, None)`. The idle
  `_objects(True)` becomes `World.resync` every `delta_resync_seconds` (5 s): the movement state and the scalar
  properties by 0x6, never a 0xBC (12.3 c). The stop order is an update; the cinematic's `_objects(True)` is followed
  by `vital_notices_on`, and so is a `[ics] player_rebind` "bundle" / "recreate" one (`Session._encounter_property`).
- `World.send_champion(label, full)`: a delta (a script teleport = an 0xB0 with the new seq A) unless full (the
  respawn); `vital_notices_on` only after a full one. The bots' `bot_late_properties` already follow full bundles only
  (creation, "(in world)", respawn).

### 13.3 Still full bundles in delta mode
Creation; the creation retries; `_objects` (create, link, in world, after a cinematic, player rebind, a full
`send_champion`); a champion's death and respawn (the local one, the bots' stop where it falls and respawn); 0.5 s
after a creation; the first update in the world after loading; an update with a changed array / table (a rank-up, a
purchase or sale, a pad's skill, the Stolen Power table swap at a lift and after a throw, the recall block). The
workarounds `resend_looping_after_bundle` and `match_camp_phase_resend` run only after those (nearly inert);
`bot_motion_only` is read in bundle mode only; `face_min_turn_degrees`, `champion_scriptlet_delay`,
`liftable_hold_champion_bundles`, `resend_looping_after_scriptlet` and `descriptor_world_state_zero` are unchanged.

### 13.4 Re-checked here
- Arrays / tables by 0x6 (12.3 d) use the bundle's own reader (C, decompilation + capstone): the 0xBC table reader
  `0x503330` -> `0x5025D0` reads per entry a u32 key, then `0x509740` (packed id `0x4FC420` + value by kind
  `0x507D60`); the 0x6 serializer `0x445530` (vtable `0x15D18D0` +0x1C, set by factory `0x691500` with id 6 and flags
  0x300400) is base u8 `0xB0D380` + the same `0x509740`. Kept behind `delta_complex_as_bundle` (true) until a test:
  ics never sent one.
- **Open (O):** that read path has no u32 before the packed id, yet ics's 0x6 (`u8 0 | u32 id | packed id | value`, a
  table entry) works in the game: 2026-10-23 15:00 (fase3-gz, diag --target) the structures were accepted after a
  `0 -> flags` toggle by 0x6, while one 0x6 with the template's own value (no change, no notification) had left the
  cache at 0. What reads the u32 is not found. 0x86 follows its own serializer (`u8 0 | u32 id`, `0x839500`); if the
  same unknown applies to it, a 0x86 is dropped and the id just stays (as with `delta_remove_missing` = false) (P).

### 13.5 Tests
`tests/test_match.py` `object_updates` (25 checks): the 0x86 bytes; 0xB0 of a state = a bundle's (attach block too);
the network modes; a minion created by one full bundle, then 0xB0-only walking states; no message for no change; a
standing bot's fog flip = one 0x6; added ids by 0x6, a net-1 id removed by one 0x86, a net-0 one kept
(`delta_remove_net0` removes it); the champion's credits / facing with no 0xBC / 0x86; a teleport and a
`send_champion` teleport = 0xB0 with the new seq A (no toggles); attach / detach blocks; remove + add = a full bundle;
the creation window; the after-load full bundle (second_seq 1); a missile turn with no Vfx_Active replay; a rank-up =
a full bundle + the toggles (by 0x6 with `delta_complex_as_bundle` false); the resync; a walking minion's stun (0x6
Stunned, then a 0xB0-only stop); the local death full (and a delta with `delta_full_on_life_change` false);
`Session._tick` on a stub session (the champion's walk 0xB0-only every tick, a walking bot's one state at its throttle
then its fog flip by 0x6); a `player_rebind` "bundle" followed by the unit-flag toggles; "bundle" mode = full bundles. `tests/test_ics.py` (+1): the walk is 0xB0-only, nothing to
the player object.
`tests/test_session_flow.py` (+1): once linked and in the world, the champion's ticks are 0xB0-only, no full or
player-object bundle. The camps check "a full bundle while phasing re-sends the phase-in run" passes `full=True`.

### 13.6 What the next test should show (P unless marked)
- The ids ics sets by 0x6 stay: a stun / knock-up / root on a moving minion, a bot or the champion keeps its CC flags
  and order lock until the status ends (they were removed by the next movement update, 12.2.4), so the CC poses play
  through; the champion's and the bots' unit flags / tags stay set (no "changed back to the template" between the
  vital-notice toggles); the turret's target id stays.
- An enemy bot standing in sight appears at once (its 0x90F goes by 0x6, not only with its next movement).
- Much less traffic: a walk sends ~70-byte 0xB0 states, not the champion + player bundles and a 0x42 every tick.
- Unchanged by this alone: the Shards sphere, Grab's arm and the camp phase-in (not bundle-caused, O: `diag.py
  --bundles`), Meltdown (server script), the death fall (death area); a facing state still turns the champion (Turn).
- To check: rank a skill (pips, "+"), buy / sell an item, use a pad, lift / throw a vehicle, recall: as before (those
  are still full bundles). With `diag.py --bundles`, "HOT BUNDLE 0xBC REMOVES" should appear only after deaths,
  respawns and those full updates. A regression: `[ics] object_update_mode = "bundle"` in config.toml.
