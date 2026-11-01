# Atomic Green Lantern visuals: Grab tether, Scorched Earth timing, Shards of Will sphere (2026-10-25)

Tester video `2026-10-25 11-27-25.mp4` (our server, fase3-hr, AGL 0x4000047D). Exe `InfiniteCrisis.exe` (VA, base
0x400000, Ghidra via REA), packs via `ics.gamedata` / `icserver.rp`. Tags: [C] confirmed, [P] probable, [G] guess.
Written incrementally.

## 0. Server log for the video (C)

- Video t = 0 is 11:27:25. Grab casts 11:27:32.5 (t 7.5), 11:28:32.8, 11:29:20.2, 11:29:36.9, 11:30:04.6 ...;
  Scorched Earth 11:29:54.0 (t 149), 11:30:14.6, 11:30:26.8, 11:30:46.0, 11:30:59.0; Shards 11:30:39.8 (t 194.8),
  11:30:57.7 (t 212.7).
- First Grab (traffic.log): 32.575 0x8D 0x10000899 / 0x1000089A on AGL (no variables, no 2nd IID); 32.957 missile
  0x40000485 created (tables 0x1D000456 + 0x1D0003D2 in 0x7D2); 33.060 missile Vfx_Active (no variables); 33.373
  missile gone (0x3), 0.42 s after creation (missile script S3 -> S7 on 0x10000005, range end, no hit); 33.446
  Grab_Stop 0x10000890.

## 1. Grab: what draws the arm / tether

### 1.1 Video (C)
Frames t 7.0-8.0 (video t = log time - 11:27:25.45 approx): t 7.15 AGL raises the arm cannon (graph event
0x1000032F + Grab_Start); t 7.50-7.75 a small trail of green particles flies off to the north-east (the missile
object's Vfx_Active particles, created 32.957); nothing connects it to AGL's hand; t 7.85-7.90 the arm drops and the
hand construct pops back (Grab_Stop 0x10000890 -> ArmFade_AddHand 0x1000093D). No stretched arm at any time.

### 1.2 The tether is a type 2 action in the missile's own Vfx_Active, aimed at property 0x100004E2 (C data, P meaning)
- Missile 0x40000485: world state **0x2E000C4C**, tables 0x1D000456 (generic) + **0x1D0003D2** (keys Vfx_Active
  0x100000EB, Vfx_Streak_Right 0x10000617, _HFSM_DestroyEntityAction 0x100001E0, Vfx_Event1 0x10000076).
- 0x1D0003D2 Vfx_Active (pack 0xA0000150 @0x29220): a type 0x23 action whose child is a **type 2** action (words
  `... 17000001 17000003 17000000 | 5.0 5.0 | 1.5 | 200 | 1.0 | 0.75 ...`, particle 0x18000752) with the binding
  **`18 18 1 3 100004E2`** = target field 0x18 <- property 0x100004E2. The same binding occurs twice more in the
  table (Vfx_Streak_Right / Vfx_Event1 children).
- Type 2 is the client's projectile / **beam** effect: execute `0x673280`: source = the scriptlet's owner entity
  (`0x514D20`, IID +0x100/+0x104), target = field 0x18 via `0x51EF90(0x18)` -> `0x51D590` -> `0x517D10` (selector
  vt+0x2C), then `0x74AE80` builds the effect; `0x74A160` loads its head / body / tail materials (+0xC8 / +0xCC /
  +0xD0, DB type 0x2C) and is the only user of the string ".../render/beam/BeamEffect.cpp" (0x15D8010).
- A binding to a property whose descriptor storage is 6 (0x10000030, 0x100009EB) reads the 0x8D variable table;
  storage 4 (object table) reads the **entity's own property** (client-scriptlets-graphs.md 1.4). 0x100004E2 is
  `iid`, storage 4, net 1, NetSharedVisually; `0x991F60` uses it as the script's context/source entity fallback
  (full-combat-skills.md) and `0x8531B0` listens to it (with enum 0x100008C9): it is the object's **creator /
  shooter IID**.
- The binding `18 18 1 3 100004E2` occurs **271 times** across the packs (e.g. 0xA00001F3 27, 0xA00002DE 18,
  0xA00001D2 17, 0xA0000150 6): it is the standard "beam back to whoever fired me" of tethers, lassos and returning
  projectiles.

### 1.3 Server state (C)
`ObjectMissile.start` builds the missile with only its tables (0x7D2) and module; **0x100004E2 is never sent** (no
code in ics / icserver writes it). So the beam has no target and draws nothing; only its particles show.

### 1.4 Fix
1. Missile and spawned skill objects: add `(0x100004E2, KIND_IID, shooter eid)` to `ent.extra_props` in
   `ObjectMissile.start` (and `World.spawn` for SpawnEntity with an owner) before `w.add(ent)`; config
   `[ics] missile_creator_property = true`. Vfx_Active (sent 0.1 s later) then finds its target.
2. Start the missile at the hand: LaunchTetheredMissile op5 StartMissileOffset (skill "Missile Firing Offset"
   vMissileOffset), not owner + 1 m z (P, cosmetic: the beam's far end is on AGL anyway).
3. Keep the missile alive the whole out-and-back (it lived 0.42 s: S3 -> S7 on 0x10000005 at range end; the arm
   lasts as long as the object).

## 2. Scorched Earth: crater vs explosion and the intended delay

### 2.1 Server and video (C)
Script 0x340002B2: S1 = graph event 0x1000032D + Smash_Active 0x100008AB on AGL; S3 (cast code **3**, graph
`a_SkillHook` at 0.11 s, data/skill_hooks.tsv) = FindTargets + ApplyDamage **at once** + per target SpawnEntity
0x40000487 at the target position (team 0x1000009C). The crater class has **no server script** and its template has
no lifetime / delay property (0x49000487: generic entity props, 0x7D2 = 0x1D000456, 0x510 = 0x2E000C01).
Traffic 11:29:54: Smash_Active .118, crater spawned .376, Vfx_OnInit .480, **Vfx_OnExplode 55.380** (server, 1.0 s,
`spawned_effect_delays`); the crater object is never removed. Video (t = log - ~25.55): 148.8-149.1 green flash at
AGL (Smash_Active), 149.1-149.7 dust, **149.8 the big green blast** (= the server's OnExplode), 150.3 on the
scorched crater ground; no second blast later (checked to 152.9).

### 2.2 The crater world state's own timeline (C words, P units = seconds)
World state **0x2E000C01** (creation type 8), table **0x1D0003D8** (pack 0xA0000150 @0x3969C):
- **Vfx_OnInit 0x10000078**: a type 0x23 sequence: at 0.0 particle **0x18000756** + child world state
  **0x2E000C99** (the crater / scorch, scale 1.75) + Vfx_Event1 ...; then the group `6 | 1.5f | 6 | 1` holding a
  **type 0x17 "run key" Vfx_OnExplode** (no target binding -> the owner itself: type 0x17 execute `0x684D10`
  uses field 6, else the scriptlet's own entity). So **OnInit runs OnExplode 1.5 s later by itself**.
- **Vfx_OnExplode 0x10000079**: particle **0x18000759** + child world state **0x2E000C90** (the blast), plus two
  bindings `18 18 1 3 100004E2` (an effect aimed at the creator AGL, needs 0x100004E2 as in 1.4).
- **_Entity_OnEnterWorld_Default 0x100002F5**: type 0x17 run Vfx_OnInit (the spawn hook, as the drones' Vfx_Spawn).
- **_Hotspot_Fizzle 0x100002F4**: run Vfx_Stop 0x10000130 (end).
- Same header for the other groups read: Grab_Start `6 | 0.24 | 6 | 2` (particle 0x18000754 + ArmFade_RemoveHand),
  Grab_Stop `6 | 0.06 | 6 | 2`, missile Vfx_Active `6 | 0.1 | 6 | 5`: the f32 is the group's start time.

So the intended order is: slam (Smash_Active on AGL, at the cast) -> crater (OnInit at spawn, code 3) -> blast
**1.5 s** after the crater. The server's own OnExplode at 1.0 s is 0.5 s early and replaces the data's chain (no
second blast appeared).

### 2.3 Fix
1. For an object whose OnInit chains OnExplode (here 0x40000487), do not schedule Vfx_OnExplode; send
   `_Entity_OnEnterWorld_Default` (or Vfx_OnInit) right after the object (`spawned_effect_scriptlets` per class, or
   `spawned_effect_delays = {"Vfx_OnExplode": -1}` = skip). If the tester still sees no blast, fall back to
   `{"Vfx_OnExplode": 1.5}` measured from OnInit (P).
2. Send 0x100004E2 = AGL on the crater too (World.spawn with owner), for OnExplode's creator-bound effect.
3. Remove the crater after its effects (e.g. 3 s: `_Hotspot_Fizzle`, then 0x3); it is never removed today.

## 3. Shards of Will: the sphere

### 3.1 Video and wire (C)
Traffic 11:30:39: Shards_Start 0x1000088C (.929) and Shards_Active 0x10000886 (40.082, +0.15 s) on AGL, both with
the variable table `{0x1000033E (f32) = 0.0}`; Shards_Stop 0x1000088B at 44.938. Video t 194.3-197.5: green shard
particles swirl around AGL (Start's sounds / particles 0x18000813 ...); **no shell / sphere mesh** at any time.

### 3.2 What draws the sphere (C data, P mechanism)
- The sphere is the client-only world state **0x2E000C89** (creation type 3; model 0x357 = 0x17000F70, graph 0x5B5 =
  0x1C000083 with animation 0x1A00090E; table 0x1D000418: Vfx_Fade_In 0x10000033, Vfx_Fade_Out 0x1000006A,
  Vfx_Active_State1..4 0x1000006B / 0x10000077 / 0x10000085 / 0x10000431). No server object, status visual, temp
  vital or extra property is involved: Shards_Active spawns it itself.
- Shards_Active (table 0x1D0003D7 @0x351E0) holds four **type 0x0C "spawn child world state" 0x2E000C89** actions
  (offsets 0x60, 0x290, 0x4C0, 0x6F0; scales 1.15 / 1.0 / 1.05 ..., each followed by its Vfx_Active_StateN key).
  The first sits in a **type 0x24 container** whose condition names **0x1000033E** with value 0 (words
  `1000033E 0 4`); the other three are gated `17 | 1000033E | 0.125 / 0.25 / 0.375 | 0 | 4`.
- 0x1000033E is storage 6 (a variable): it is read only from the 0x8D variable table. Shards_Start 0x88C's first
  action is a type 0x17 "run 0x886 on self", which starts Active **without** the variable table (P).
- Type 0x24 = container object 0x52BED0 (vtable 0x15B1500, fields 0x321 enum2 at +0x34, 0x5C7 bool at +0x3C,
  execute 0x530310, shared with 0x22). The exact comparison of the `... 4` condition was not decoded (O).
- Type 0x0C = ctor 0x655130, vtable 0x15CEC20, **execute 0x6852B0** (create 0x664120).
- The "time" word of each action header (0x12, 0x2F, 0x70, 0xB2, 0x1A9 ...) increases through a whole table: it is
  a node id, not a frame; real delays are the `6 | f32 seconds | 6 | n` group headers (section 2.2).

### 3.3 Most likely causes, in order (P)
1. The shell gate fails at ShieldPercentage 0.0 (strict compare, or the Start-chained run has no variable): all four
   shells need 0x1000033E present and > its threshold.
2. The server's later 0x886 (with the variable) is ignored while the Start-chained 0x886 run is alive (same key,
   new instance) (O).

### 3.4 Fix / test
1. Test first: `[ics] scriptlet_variable_overrides = {"0x10000886": {"0x1000033E": 0.5}, "0x1000088C": {...}}`
   (or a one-off debug key) and cast E: if the shells appear, the gate is the cause.
2. Then send ShieldPercentage as the data expects at the shell's base: a small positive floor (e.g. max(bonus,
   0.01)) for 0x886 / 0x88C, keep 0x886 0.15 s after 0x88C (`scriptlet_delays`), or send **0x886 only** with the
   variable (drop 0x88C's chained copy) - one config switch each.
3. Diag: break at **0x6852B0** (type 0x0C execute; the action's ws DID is in the definition) while casting E: hit =
   the shell is spawned (then look at scale / attach), no hit = the gate (then break 0x530310 for the container).
