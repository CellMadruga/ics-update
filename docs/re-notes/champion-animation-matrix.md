# Champion skill animation matrix: what each skill state needs and what ics gives it (2026-10-25)

Static analysis of the 54 base champions' Havok behaviour graphs (hk_2012 packfiles, all 264 graphs of the install
indexed; the champion's graph = the one whose `turbineEventHookPayload`s name most of its kit script DIDs), their Lua
callbacks, `InfiniteCrisis.exe` (Ghidra via REA, VA, base 0x400000) and a simulated cast of every slot with
`tools/champion_check.py` (Crime Alley, level 6, enemy minion 2 m away, 3 s window), traced for: graph events ics
raises on the champion (scriptlet 0x100001E3 + variable 0x780), cast signals sent to the slot's script, champion
bundles. Builds on animation-deep-scan.md, sweep-property-listeners.md, client-movement.md, skill-second-stages.md.
Confidence: **C** = read in code or data, **P** = probable, **O** = open. Helper scripts (scratchpad, not in the
repo): `gindex.py` (graph index), `gmat.py` (state analysis), `trace.py` (simulator trace), `matrix.py` (this table).

## 1. Client facts verified for this note (C)

* **Propel / Turn come only from the replayed movement.** `0x6097E0` is the only writer of graph inputs `0x501`,
  `0x300` (`Property_Slider_Propel`) and `0x1F1` (`Property_Slider_Turn`) (ids at `0x15C5D74` = 0x1F1, `0x15C5D78` =
  0x300, `0x15C5D7C` = 0x501; written through `0x58F3D0`). It takes the step's displacement toward the dead-reckoned
  target in the entity's local frame: 0x501 = side, **0x300 = forward speed (m/s, clamped to [0, max speed
  `+0x2D0`])**, 0x1F1 = orientation change of the step x -1/180, clamped to [-1, 1]. Its only caller is the replay
  step `0x60B5F0`, and **only on the smooth branch** (no newer seq A/B, error <= 2 m). On the snap branch (teleport
  seq, > 2 m, no state) the three inputs keep their previous values.
* **No client-side stop.** A move state keeps being dead-reckoned until a newer state arrives
  (client-movement.md 1.3). While it is replayed, Propel = the walk speed.
* **The Lua early-outs (AGL, the same text in every champion graph):** `onHandleEventCosmeticEnabled` fires
  `Global_Locomotion` when `Propel > 0 or Turn ~= 0` at the CosmeticEnabled event; `onSkillEarlyOut` (inside the
  skill states once CosmeticEnabled is true) and `onCosmeticEarlyOut` (cosmetic tails) fire it when Propel > 0 (>= 1
  for the tail) or Turn ~= 0; `onBasicAttackEarlyOut` fires `Combat_Locomotion` at Propel >= 1. A one-step facing snap
  makes Turn non-zero for one step: that is enough.
* **A full 0x4 bundle to an existing object does not re-create it.** Create handler `0x64D8A0`: when the IID exists
  (`0x64A3A0`) and the class is the same, nothing is rebuilt (a different class goes to `[0x1B67258] vt+0x28`). The
  0xBC table of the bundle is a **full property replace** (`0x62AFD0`: every id removed through `vt+0x54`, then every
  sent id set through `vt+0x50`), so each bundle fires remove + set on every listener, the graph binder included
  (AttackSpeed is re-pushed with the same value). The graph state machine is not reset by a same-class bundle (C);
  the old comment in `CastWorld.run_scriptlet` ("a champion bundle re-creates the object") is not what the code does.
* **Graph variable defaults** (hkbVariableValueSet of every chr_ graph): Property_Attribute_AttackSpeed 1.0 (111
  graphs), Attribute_AttackSpeed 1.0, AnimationSpeedMultiplier 1.0, TurnSpeed 2160 deg/s, CosmeticEnabled false.

* **Turn is the per-step yaw delta.** `0xAF3910` / `0xAF29C0` normalise (new yaw - old yaw) to (-180, 180] degrees;
  x -1/180 -> Turn. A 45 degree facing snap = Turn -0.25 for exactly one replay step, 0 afterwards (C).

## 2. Simulator totals (all 54 base champions, 216 Q/W/E/R casts + 54 basic + 54 passive)

| What | Count | Meaning |
|---|---|---|
| Q/W/E/R casts with no stop state at the cast (no FaceTarget bundle) | 114 / 216 | ics zeroes the champion's speed on the skill order (session.py `CMD_SKILL`) but sends nothing; the client goes on replaying the last walk state |
| ... of which the state blends on Propel or has a cosmetic tail | 80 | these play the moving / upper-body variant or abort (section 3.1) |
| skill states with a cosmetic tail (`skill_to_cosmetic` -> `*_Cosmetic` with `onCosmeticEarlyOut`) | 120 | ended by Propel >= 1 or Turn != 0 |
| skill states that read Propel (blend `blendParameter <- Property_Slider_Propel`) | 81 | |
| states that bind TargetHeading / UsToTargetHeading | 1 / 1 | **not** a common cause (ruled out) |
| start through a scriptlet key (no 0x100001E3 from the script; the champion's table action 0x14 raises it) | 94 | works on the client (Gaslight Batman Q/W/E seen in the game) |
| start event raised but absent from the champion graph's transitions | 9 | section 3.5 |
| ics raises skill_to_locomotion inside a cosmetic tail / before the cast end | 3 / 2 (sim) ; 29 scripts with a tail raise it somewhere | section 3.2 |
| skill states that wait for an event ics never raised in the window | 40 (incl. locomotion fidget noise) | section 3.4 |
| states with no self-ending trigger | 20 | end by a script event (or graph_exit_fallback) |

Not common causes (checked): the bundle does not reset the graph (1); variable `0x10000400` is a scriptlet
variable (VFX fields), not a graph input; TargetHeading is bound in 1 champion state; events before the graph is
ready are queued (`0x55BD30`, diag fase3-hk: 100 delivered, 4 queued, none dropped).

## 3. Common causes, ranked

### 3.1 No stop state when a skill is cast while walking (C code path, P visual effect; 80+ skills)
`ev_order` CMD_SKILL sets `ch.dest, ch.speed = None, 0.0` and calls `World.cast`; nothing goes to the client unless
the script's FaceTarget sends a bundle (`CastWorld.face` -> `World.update`). The client keeps dead-reckoning the walk
(1), so Propel stays at the walk speed through the cast: `onHandleEventCosmeticEnabled` / `onSkillEarlyOut` /
`onCosmeticEarlyOut` fire `Global_Locomotion` (the clip is replaced by the run cycle after the wind-up), the 81 blend
states pick their moving variant, and the champion glides on, then snaps back (> 2 m) when the next state comes.
Instant / self casts (Shards of Will, Berserk, Kryptonian Rage, Speed Storm, buffs) never send one. Basic attacks are
fine (`_attack_step` returns `moving` -> the tick's bundle).

### 3.2 Script-raised skill_to_locomotion cuts the cosmetic tail (C sim, 29 scripts)
`_graph_cast` now sends 2 at the state's exit trigger (+0.01 s), and the scripts' S2 answers 2 with
`RaiseGraphEvent(SELF)[0x10000002]` at once: the tail (`*_Cosmetic`, which self-ends at clip end - 0.20 s) starts and
is ended 0.01-0.05 s later. Seen: AGL Meltdown, Huntress Grapple Bolt, Nightwing Rolling Thunder, Dex-Starr Shred The
World, Green Arrow Superfoam; 29 scripts that own a tail state raise 0x10000002. animation-deep-scan.md 5 step 2
(`keep_cosmetic_tail`) was never implemented.

### 3.3 Facing snap lands inside the skill state (C timing, P effect)
FaceTarget's bundle is sent at t, the graph event at t + 0.06 (`champion_scriptlet_delay`); the client applies a
movement state 0.1 s after its time stamp, the 0x8D at once. So the turn (Turn != 0 for one step) and, when walking,
the stop happen ~0.04 s **after** the skill state began. Harmless for a full-body state with CosmeticEnabled false;
it aborts a state that is already cosmetic-enabled or a re-cast during a tail, and 0.04 s of Propel > 0 picks the
moving branch of blend states at entry.

### 3.4 Stage / end events never raised (C data, P per case: some may come through scriptlet keys)
Doomsday Charge `_Grab/_End`, Supergirl Worldbreaker/Comet `_Grab/_End`, Superman Speeding Bullet
`_Windup_to_Start/_Start_to_Loop/_Loop_to_End`, Wonder Woman Lasso `_Dash/_Hit`, Protection `_Other_Teleport`,
Blocking Bracers `_End`, Green Arrow Bullseye `_Fire/_Superfoam`, Atrocitus Overwhelming Rage `_Combo/_End`, AWW
Reclaimer `_End`, Arcane GL Deny the Black `_End`, Deadshot / Batman R `Wildcard_RSkill_End/_Alt`, Zod Kneel
`_End` + `Wildcard_SkillR_Secondary`, Zod basic `Zod_Rush_Loop_To_End`, Flash `Flash_SpeedStorm_End` (ics raises
`SpeedStorm_End`, another name), NMR Feed the Beast `_End`, N. Catwoman `Rip&Tear_Hit`, Blue Beetle
`Stick_And_Move_Left/Right`, every dash `Skill_Dash_Start/_End` (Deathstroke R, Dex-Starr W, Huntress E, Krypto W,
Raven R), John Stewart Q/W/R and Stargirl R / Arcane Zatanna R `skill_to_locomotion` (no timed end).

### 3.5 Start events the champion graph does not take (C data)
Deathstroke Q `Wildcard_QSkill` (graph uses Dash_Q), Gaslight Batman R `CbtState_Trigger_Start` x3 on himself,
Gaslight Catwoman E `Gaslight_Catwoman_StalkStart`, Hawkgirl E `DeactivateSoar`, Katana basic `UnSheath_Blade`,
Nightmare Batman E/R `Vampire_Batman_Savagery*`, Robin W `Robin_BoMaster_Start`, Grundy E `ActivateMarch`: names in
the global table but in no transition of the chosen graph (O: an event-driven modifier, a weapon / attached
object's graph, or the wrong target entity).

### 3.6 Attack speed sent as attacks per second (P)
`stat_properties` sends 0x100006FE = the stats record's value (0.56-0.71 at level 1) on the champion; the graph
variable it feeds (`Property_Attribute_AttackSpeed` -> `Attribute_AttackSpeed` -> basic clip `playbackSpeed`)
defaults to 1.0 in all 111 graphs, so P: basic attack clips run at ~0.6x while ics times their hooks at 1x
(3 @ 0.25 s vs the clip's 0.24 / 0.6 = 0.40 s).

### 3.7 Arcane Green Lantern: 10 Hz champion bundles (C sim)
His passive 0x34000292 `AttachEntity(SELF, lantern, offset, handle)` makes `_attach` move the CHAMPION onto the
lantern every 0.1 s with a full bundle (399 in one run). Same argument-order question as fase3-hr's Grab fix.

## 4. Server-side fixes, ranked (confidence of the fix doing what it says)

1. **Stop state on every champion cast (C path / P effect).** In `World.cast` for the champion (before
   `R.activate`): if it was moving or `ch.speed` was > 0, send one movement state (current position, speed 0, the
   heading; `M.pvp_movement_state` or a bundle) and only then the cast's scriptlets. Config e.g.
   `[ics] cast_stop_state = true`.
2. **Graph events after the client has applied that state (P).** Raise `champion_scriptlet_delay` from 0.06 to ~0.13 s
   (0.1 s replay delay + one step) for the champion's cast start, so the stop and the FaceTarget turn (Turn != 0 for
   one step) happen before the skill state is entered; shift the cast signal timers by the same delay so the hooks
   stay aligned with the clip. Config: the existing key.
3. **Keep cosmetic tails (C data).** When a script raises `skill_to_locomotion` (0x10000002) on its own champion
   while the cast's graph state left on `skill_to_cosmetic`, drop it (the tail self-ends at clip end - 0.20 s, or the
   player's move ends it by Propel). Table from data/skill_hooks.tsv (leaves_on contains skill_to_cosmetic). Config
   `[ics] keep_cosmetic_tail = true` (animation-deep-scan.md 5.2).
4. **Stage events (C data, P source).** Make the script branches that raise the 3.4 names run (attach success event
   0x10000022 family, dash start / end around forced motion, channel ends); `Flash_SpeedStorm_End` vs
   `SpeedStorm_End` naming check.
5. **Attack speed as a multiplier (G/P).** Send 0x100006FE = current attacks per second / base attacks per second
   (1.0 at base) on champions and units, and scale the basic attack hook times by 1 / that value. Confirm first with
   the diag probe below (what the original data expect is O).
6. **Arcane GL attach (P).** Swap child / parent in `_attach` for 0x34000292 (lantern follows the champion) or skip
   the follow loop when the child is the champion.
7. **3.5 start events (O).** Find the receiver of `Gaslight_Catwoman_StalkStart`, `Robin_BoMaster_Start`,
   `Vampire_Batman_Savagery*`, `ActivateMarch`, `UnSheath_Blade` (attached weapon / effect objects?).

## 5. diag.py probes (rva = VA - 0x400000)

| rva | log | confirms |
|---|---|---|
| `0x18F3D0` (`0x58F3D0`) | `[esp+4]` entity, `[[esp+8]]` id, `[[esp+0xC]]` f32 | ids 0x300 / 0x1F1 on the champion: Propel > 0 / Turn != 0 between a 0x8D graph start and the next 0x300 = 0 (3.1, 3.3) |
| `0x15AF70` | `[esp+4]` global event | order and times of start / stage events vs the Propel writes |
| `0x1C9E90` (`0x5C9E90`, snap) inside `0x60B5F0` | caller = replay snap | snaps of the champion after casts (the glide-and-snap of 3.1) |
| `0x22AFD0` (`0x62AFD0`) | count per second | full property replaces (30 Hz while walking) |
| `0x159F7F` / `0x159F87` | property id / variable index | 0x100006FE value reaching `Property_Attribute_AttackSpeed` (3.6) |
| `0x272930` | scriptlet action 0x14 (`esi` event) | the 94 scriptlet-started skills really raise their start event |

## 6. The matrix

Per champion (graph = the one whose skill hooks name its kit scripts). Columns: **ics raises** = graph events ics
sent on the champion during the first cast of the slot (0x100001E3 + 0x780, seconds after the cast; "none" = the
start goes through a scriptlet key of the champion's tables, or the slot raises nothing); **state -> tail** = the
state each event enters (wildcard transition of the main machine unless noted) and its cosmetic tail with its Lua
early-out; for "none" rows the states whose enter hook names the script ("(scriptlet?)"); **hooks** = clip trigger
payload codes at real seconds; **leaves on** = the state's own transitions; **needs** = events in the state's or its
nested machines' transitions that no clip trigger / Lua of the state raises; **never raised** = those ics did not
send in the window (P: a scriptlet key may raise some); **ics signals** = OnCastSignal codes ics sent to the slot's
script; **graph inputs** = Property_* variables bound in the state (Slider_Turn mostly drives
turbineRotateCharacterModifier; Slider_Propel = blend); **movement** = "no stop" (no stop / face state at the cast),
"bundle@" = champion bundles during the window, cuts by ics' skill_to_locomotion. Emote_* / Fidget_* / CbtState_*
entries in "needs" come from the Locomotion state entered by skill_to_locomotion (noise).

### Aquaman (0x400005c6, graph chr_aquaman_behavior.hkb, pack 0xA0000191, 5 kit scripts in its hooks)

| slot | skill / script | ics raises (event@s) | state -> cosmetic tail | hooks code@s | leaves on | needs (external) | never raised | ics signals code@s | graph inputs | movement |
|---|---|---|---|---|---|---|---|---|---|---|
| basic | Basic Attack 0x34000374 | none | Critical_Attack; Basic_Attack | 3@0.240,6@0.050; 3@0.240,6@0.050 | basicattack_to_basicattack; basicattack_to_basicattack | - | - | 6@0.05,3@0.25,2@0.3 | Slider_Turn | - |
| Q | Trident of the King 0x34000394 | Aquaman_Trident@0 | Trident -> Trident_Cosmetic onCosmeticEarlyOut | 2@0.267,5@0.122 | skill_to_cosmetic | - | - | 5@0.15,2@0.3 | Slider_Turn,TurnSpeed | - |
| W | Stagger 0x34000396 | Aquaman_Stagger@0 | Stagger -> Stagger_Cosmetic onCosmeticEarlyOut | 3@0.090 | skill_to_cosmetic | - | - | 3@0.1,2@0.25 | Slider_Turn,TurnSpeed | - |
| E | Undertow 0x3400037A | Aquaman_Undertow@0; skill_to_locomotion@0.15 | Undertow | - | skill_to_locomotion | skill_to_locomotion | - | 5@0.3,3@0.3,2@0.45 | Slider_Turn,TurnSpeed | no stop skill_to_locomotion@0.15 ends the state (authored end) bundle@0.05,0.1,0.15,0.15 |
| R | Might of Atlantis 0x34000397 | none | - | - |  | - | - | - | - | no stop bundle@1 |
| passive | Rising Tide 0x34000395 | none | - | - |  | - | - | - | - | - |

### Arcane Green Lantern (0x4000043b, graph chr_arcane_green_lantern_behavior.hkb, pack 0xA0000144, 5 kit scripts in its hooks)

| slot | skill / script | ics raises (event@s) | state -> cosmetic tail | hooks code@s | leaves on | needs (external) | never raised | ics signals code@s | graph inputs | movement |
|---|---|---|---|---|---|---|---|---|---|---|
| basic | Basic Attack 0x34000295 | none | Critical_Attack; Basic_Attack | 3@0.240,6@0.050; 3@0.240,6@0.050 | basicattack_to_basicattack; basicattack_to_basicattack | - | - | 6@0.05,3@0.25,2@0.3 | Slider_Turn | bundle@0.1,0.2,0.3,0.4 |
| Q | Construct Champion 0x34000293 | ArcaneGreenLantern_ConstructChampion@0 | ConstructChampion -> ConstructChampion_Cosmetic onCosmeticEarlyOut | 5@0.080 | skill_to_cosmetic | - | - | 5@0.1,2@0.25 | Slider_Turn,TurnSpeed | bundle@0.1,0.2,0.3,0.4 |
| W | Shackles 0x34000294 | none | Shackles | 3@0.200 | skill_to_locomotion | - | - | - | Slider_Propel,Slider_Turn,TurnSpeed | no stop bundle@0.1,0.2,0.3,0.4 |
| E | Emerald Lantern 0x34000290 | ArcaneGreenLantern_EmeraldLantern@0; ArcaneGreenLantern_NoLantern@0.05 | EmeraldLantern -> EmeraldLantern_Cosmetic onCosmeticEarlyOut | 5@0.050 | skill_to_cosmetic | - | - | 5@0.05,2@0.2 | Slider_Turn,TurnSpeed | bundle@0.1,0.2,0.3,0.4 |
| R | Deny the Black 0x34000291 | none | DenyTheBlack_Teleport; DenyTheBlack_Cast | 3@0.190 | ArcaneGreenLantern_DenyTheBlack_End; skill_to_locomotion | ArcaneGreenLantern_DenyTheBlack_End | ArcaneGreenLantern_DenyTheBlack_End | 3@0.2,2@0.25 | - | no stop bundle@0.1,0.2,0.3,0.4 |
| passive | Emerald Light 0x34000292 | none | - | - |  | - | - | - | - | - |

### Arcane Harley Quinn (0x40000d51, graph chr_arcane_harley_quinn_behavior.hkb, pack 0xA0000384, 4 kit scripts in its hooks)

| slot | skill / script | ics raises (event@s) | state -> cosmetic tail | hooks code@s | leaves on | needs (external) | never raised | ics signals code@s | graph inputs | movement |
|---|---|---|---|---|---|---|---|---|---|---|
| basic | Basic Attack 0x3400077A | none | Crit_Melee_Large; Basic_Melee_Large; Empower_Melee | 0@0.160,3@0.200; 0@0.160,3@0.200; 0@0.160,3@0.200 | basicattack_to_basicattack; basicattack_to_basicattack; basicattack_to_basicattack | - | - | 3@0.25,2@0.25 | Slider_Turn | - |
| Q | Pirouette 0x34000776 | Wildcard_QSkill@0 | StandardSkill_Q | 3@0.090 | skill_to_locomotion | - | - | 3@0.1,2@0.45 | Slider_Propel,Slider_Turn,TurnSpeed | no stop |
| W | Flit 0x34000775 | Wildcard_WSkill@0; skill_to_locomotion@0.15 | Dash_W | - | skill_to_locomotion | skill_to_locomotion | - | 5@0.3,3@0.3,2@0.45 | Slider_Turn,TurnSpeed | no stop skill_to_locomotion@0.15 ends the state (authored end) bundle@0.05,0.1,0.15,0.15 |
| E | Glamour 0x34000778 | none | - | - |  | - | - | 5@0.3,3@0.3,2@0.45 | - | no stop |
| R | Delirium 0x3400077B | Wildcard_RSkill@0 | Selfbuff_R | - | skill_to_locomotion | - | - | 5@0.3,3@0.3,2@0.45 | Slider_Propel,Slider_Turn,TurnSpeed | - |
| passive | Spiteful Sprite 0x34000777 | none | - | - |  | - | - | - | - | - |

### Arcane Supergirl (0x40000ab3, graph chr_arcane_supergirl_behavior.hkb, pack 0xA0000281, 5 kit scripts in its hooks)

| slot | skill / script | ics raises (event@s) | state -> cosmetic tail | hooks code@s | leaves on | needs (external) | never raised | ics signals code@s | graph inputs | movement |
|---|---|---|---|---|---|---|---|---|---|---|
| basic | Basic Attack 0x3400054A | none | Critical_Attack; Basic_Attack_Right; Basic_Attack_Left | 5@0.240,6@0.050; 5@0.240,6@0.050; 5@0.240,6@0.050 | basicattack_to_basicattack; basicattack_to_basicattack; basicattack_to_basicattack | - | - | 6@0.05,5@0.25,2@0.3 | Slider_Turn | - |
| Q | Breath of Rao 0x3400054E | Wildcard_QSkill@0 | BreathofRao -> BreathofRao_Cosmetic  | 3@0.160 | skill_to_cosmetic | - | - | 3@0.2,2@0.25 | Slider_Propel,Slider_Turn,TurnSpeed | no stop |
| W | Firewall 0x3400054C | Wildcard_WSkill@0 | Firewall -> Firewall_Cosmetic onCosmeticEarlyOut | 3@0.060 | skill_to_cosmetic | - | - | 3@0.1,2@0.25 | Slider_Turn,TurnSpeed | bundle@1 |
| E | Pyrolyze 0x3400054B | Wildcard_ESkill@0 | Pyrolyze -> Pyrolyze_Cosmetic onCosmeticEarlyOut | 5@0.100 | skill_to_cosmetic | - | - | 5@0.1,2@0.2 | Slider_Turn,TurnSpeed | - |
| R | Rao's Wrath 0x3400054D | none | RaosWrath -> RaosWrath_Cosmetic  | 3@0.080 | skill_to_cosmetic | - | - | - | Slider_Turn,TurnSpeed | no stop |
| passive | Daughter of Rao 0x34000550 | none | - | - |  | - | - | - | - | - |

### Arcane Zatanna (0x40000bf5, graph chr_arcane_zatanna_behavior.hkb, pack 0xA0000303, 5 kit scripts in its hooks)

| slot | skill / script | ics raises (event@s) | state -> cosmetic tail | hooks code@s | leaves on | needs (external) | never raised | ics signals code@s | graph inputs | movement |
|---|---|---|---|---|---|---|---|---|---|---|
| basic | Basic Attack 0x34000615 | none | Melee_Passive; Basic_Melee_Large; Crit_Melee_Small | 3@0.240,6@0.050; 3@0.240,6@0.050; 3@0.240,6@0.050 | basicattack_to_basicattack; basicattack_to_basicattack; basicattack_to_basicattack | - | - | 6@0.05,3@0.25,2@0.3 | Slider_Turn | bundle@0.1,0.2,0.3,0.4 |
| Q | Spectral Slash 0x3400061A | Wildcard_QSkill@0 | Spectral Slash -> Spectral Slash_Cosm onCosmeticEarlyOut | 3@0.050 | skill_to_cosmetic | - | - | 3@0.05,2@0.2 | Slider_Turn,TurnSpeed | bundle@0.1,0.2,0.3,0.4 |
| W | Runic Gate 0x340007A1 | Wildcard_WSkill@0 | Runic Gate | - | skill_to_locomotion | - | - | 5@0.3,3@0.3,2@0.45 | Slider_Propel,Slider_Turn,TurnSpeed | no stop bundle@0.1,0.2,0.3,0.4 |
| E | Mystic Feedback 0x34000618 | Wildcard_ESkill@0 | Mystic Feedback | - | skill_to_locomotion | - | - | - | Slider_Propel,Slider_Turn,TurnSpeed | no stop bundle@0.1,0.2,0.3,0.4 |
| R | Silent Sorceress 0x34000617 | none | Silent Sorceress -> SS_End_Cosm onCosmeticEarlyOut | 3@0.050 | skill_to_cosmetic,skill_to_locomotion | skill_to_locomotion | skill_to_locomotion | - | - | no stop bundle@0.1,0.2,0.3,0.4 |
| passive | Mage Hunter 0x340007A2 | none | - | - |  | - | - | - | - | - |

### Atomic Green Lantern (0x4000047d, graph chr_atomic_green_lantern_behavior.hkb, pack 0xA0000150, 4 kit scripts in its hooks)

| slot | skill / script | ics raises (event@s) | state -> cosmetic tail | hooks code@s | leaves on | needs (external) | never raised | ics signals code@s | graph inputs | movement |
|---|---|---|---|---|---|---|---|---|---|---|
| basic | Basic Attack 0x340002B6 | none | Critical_Attack; Basic_Attack | 3@0.240,6@0.050; 3@0.240,6@0.050 | basicattack_to_basicattack; basicattack_to_basicattack | - | - | 6@0.05,3@0.25,2@0.3 | Slider_Turn | - |
| Q | Grab 0x340002B5 | AtomicGreenLantern_Grab_Start@0; AtomicGreenLantern_Grab_Hit@0.3; skill_to_locomotion@0.45 | Grab; Grab_End | 5@0.140 | skill_to_locomotion; (none) | AtomicGreenLantern_Grab_Hit,skill_to_locomotion | - | 5@0.15 | Slider_Turn,TurnSpeed | skill_to_locomotion@0.45 bundle@0.5,0.55,0.6,0.65 |
| W | Scorched Earth 0x340002B2 | AtomicGreenLantern_ScorchedEarth_Start@0 | Scorched Earth -> Scorched Earth_Cosmetic onCosmeticEarlyOut | 3@0.110 | skill_to_cosmetic | - | - | 3@0.15,2@0.2 | Slider_Turn,TurnSpeed | - |
| E | Shards of Will 0x340002B1 | AtomicGreenLantern_ShardsofWill_Start@0 | Shards of Will | - | skill_to_locomotion | - | - | - | Slider_Propel,Slider_Turn,TurnSpeed | no stop |
| R | Meltdown 0x340002B4 | AtomicGreenLantern_Meltdown_Start@0; skill_to_locomotion@0.2 | Meltdown -> Meltdown_Cosmetic onCosmeticEarlyOut | 5@0.100 | skill_to_cosmetic | - | - | 5@0.1,2@0.2 | Slider_Turn,TurnSpeed | skill_to_locomotion@0.2 cuts tail 0.03s after it began |
| passive | Radiation Sickness 0x340002B3 | none | - | - |  | - | - | - | - | - |

### Atomic Joker (0x40000962, graph chr_atomic_joker_behavior.hkb, pack 0xA000024A, 4 kit scripts in its hooks)

| slot | skill / script | ics raises (event@s) | state -> cosmetic tail | hooks code@s | leaves on | needs (external) | never raised | ics signals code@s | graph inputs | movement |
|---|---|---|---|---|---|---|---|---|---|---|
| basic | Basic Attack 0x340004DF | none | Critical_Attack; Basic_Attack; Empowered_Attack | 5@0.240,6@0.050; 5@0.240,6@0.050; 5@0.240,6@0.050 | basicattack_to_basicattack; basicattack_to_basicattack; basicattack_to_basicattack | - | - | 6@0.05,5@0.25,2@0.3 | Slider_Turn | - |
| Q | Hot Potato 0x340004DD | Wildcard_QSkill@0 | Hot Potato -> Hot Potato_Cosmetic onCosmeticEarlyOut | 5@0.100 | skill_to_cosmetic | - | - | 5@0.1,2@0.2 | Slider_Turn,TurnSpeed | - |
| W | Plutonium Peel 0x340004DC | Wildcard_WSkill@0 | PlutoniumPeel -> PlutoniumPeel_Cosmetic onCosmeticEarlyOut | 5@0.100 | skill_to_cosmetic | - | - | 5@0.1,2@0.2 | Slider_Turn,TurnSpeed | - |
| E | Acid Balloon 0x340004DB | Wildcard_ESkill@0 | AcidBalloon -> AcidBalloon_Cosmetic onCosmeticEarlyOut | 5@0.135 | skill_to_cosmetic | - | - | 5@0.15,2@0.25 | Slider_Turn,TurnSpeed | - |
| R | Jack in the Box 0x340004DA | UltActive_Start@0 | Ult_Start | - | UltActive | - | - | - | - | no stop |
| passive | The Punch Line 0x340004DE | none | - | - |  | - | - | - | - | - |

### Atomic Poison Ivy (0x40000553, graph chr_atomic_poison_ivy_behavior.hkb, pack 0xA000018D, 5 kit scripts in its hooks)

| slot | skill / script | ics raises (event@s) | state -> cosmetic tail | hooks code@s | leaves on | needs (external) | never raised | ics signals code@s | graph inputs | movement |
|---|---|---|---|---|---|---|---|---|---|---|
| basic | Basic Attack 0x34000352 | none | Critical_Attack; Basic_Attack | 3@0.240,6@0.050; 3@0.240,6@0.050 | basicattack_to_basicattack; basicattack_to_basicattack | - | - | 6@0.05,3@0.25,2@0.3 | Slider_Turn | - |
| Q | Poisoned Earth 0x34000354 | PoisonedEarth_Start@0 | Poisoned Earth | 3@0.200 | skill_to_locomotion | - | - | 3@0.25,2@0.3 | Slider_Propel,Slider_Turn,TurnSpeed | no stop |
| W | Bramble Rapture 0x34000353 | BrambleRapture_Start@0 | Bramble Rapture -> Bramble Rapture_Cosmetic onCosmeticEarlyOut | 5@0.080 | skill_to_cosmetic | - | - | 5@0.1,2@0.25 | Slider_Turn,TurnSpeed | - |
| E | Wall of Thorns 0x34000356 | WallofThorns_Start@0 | Wall of Thorns | 3@0.170 | skill_to_locomotion | - | - | 3@0.2,2@0.25 | Slider_Turn,TurnSpeed | - |
| R | Secrets of the Forest 0x34000355 | SecretsoftheForest_Start@0 | Secrets of the Forest | 3@0.170 | skill_to_locomotion | - | - | 3@0.2,2@0.25 | Slider_Propel,Slider_Turn,TurnSpeed | no stop |
| passive | Toxic Growth 0x34000357 | none | - | - |  | - | - | - | - | - |

### Atomic Wonder Woman (0x400003ec, graph chr_atomic_wonder_woman_behavior.hkb, pack 0xA0000124, 4 kit scripts in its hooks)

| slot | skill / script | ics raises (event@s) | state -> cosmetic tail | hooks code@s | leaves on | needs (external) | never raised | ics signals code@s | graph inputs | movement |
|---|---|---|---|---|---|---|---|---|---|---|
| basic | Basic Attack 0x34000257 | none | Critical_Attack; Basic_Attack; SmitingStrike | 3@0.240,6@0.050; 3@0.240,6@0.050; 3@0.050,6@0.050 | basicattack_to_basicattack; basicattack_to_basicattack; basicattack_to_basicattack | - | - | 5@0.3,3@0.3,2@0.45 | Slider_Turn,TurnSpeed | - |
| Q | Vault 0x34000256 | AtomicWonderWoman_StormingSmash@0; AtomicWonderWoman_StormingSmash_End@0.15 | StormingSmash -> StormingSmash_Strike_Cosmetic onCosmeticEarlyOut; StormingSmash_Strike | 3@0.068; 3@0.068 | skill_to_cosmetic; (none) | AtomicWonderWoman_StormingSmash_End | - | 3@0.1,2@0.15 | Slider_Turn,TurnSpeed | no stop bundle@0.05,0.1,0.15,0.15 |
| W | Smite 0x34000255 | none | - | - |  | - | - | - | - | no stop |
| E | Savage Sweep 0x34000254 | AtomicWonderWoman_SavageSweep_Revved@0 | SavageSweep_Revved -> SavageSweep_Revved_Cosmetic onCosmeticEarlyOut | 3@0.040 | skill_to_cosmetic | - | - | 5@0.3,3@0.3,2@0.45 | Slider_Turn,TurnSpeed | - |
| R | Reclaimer 0x34000253 | none | Reclaimer | 3@0.020 | skill_to_locomotion | AtomicWonderWoman_Reclaimer_End | AtomicWonderWoman_Reclaimer_End | 3@0.05,2@0.3 | Slider_Propel,Slider_Turn,TurnSpeed | no stop |
| passive | Rev 0x34000265 | none | - | - |  | - | - | - | - | - |

### Atrocitus (0x40000932, graph chr_atrocitus_behavior.hkb, pack 0xA000023E, 4 kit scripts in its hooks)

| slot | skill / script | ics raises (event@s) | state -> cosmetic tail | hooks code@s | leaves on | needs (external) | never raised | ics signals code@s | graph inputs | movement |
|---|---|---|---|---|---|---|---|---|---|---|
| basic | Basic Attack 0x340004CC | none | Critical_Attack; Basic_Attack; Empowered_Attack | 3@0.240,6@0.050; 3@0.240,6@0.050; 3@0.130,6@0.050 | basicattack_to_basicattack; basicattack_to_basicattack; basicattack_to_basicattack | - | - | 5@0.3,3@0.3,2@0.45 | Slider_Turn | - |
| Q | Crimson Slash 0x340004CD | none | - | - |  | - | - | - | - | no stop |
| W | Come At Me 0x340004CE | Atrocitus_Come_At_Me@0 | Come_At_Me | - | skill_to_locomotion | - | - | - | Slider_Propel,Slider_Turn,TurnSpeed | no stop bundle@1 |
| E | Overwhelming Rage 0x340004CF | none | Overwhelming_Rage | 3@0.250,3@0.500,3@0.750,3@1.000 | Overwhelming_Rage_End | Overwhelming_Rage_Combo,Overwhelming_Rage_End,state_to_state | Overwhelming_Rage_Combo,Overwhelming_Rage_End,state_to_state | 3@0.3 | Slider_Turn,TurnSpeed | no stop |
| R | Plasma Wave 0x340004D0 | Atrocitus_Plasma_Wave@0 | Plasma_Wave -> Plasma_Wave_Cosmetic onCosmeticEarlyOut | 3@0.100 | skill_to_cosmetic | - | - | 3@0.1,2@0.4 | Slider_Turn,TurnSpeed | - |
| passive | Red Lantern's Rage 0x340004D1 | none | - | - |  | - | - | - | - | - |

### Batman (0x40000280, graph chr_batman_behavior.hkb, pack 0xA000011F, 5 kit scripts in its hooks)

| slot | skill / script | ics raises (event@s) | state -> cosmetic tail | hooks code@s | leaves on | needs (external) | never raised | ics signals code@s | graph inputs | movement |
|---|---|---|---|---|---|---|---|---|---|---|
| basic | Basic Attack 0x34000178 | none | Critical_Attack; Basic_Attack | 3@0.240,6@0.050; 3@0.240,6@0.050 | basicattack_to_basicattack; basicattack_to_basicattack | - | - | 6@0.05,3@0.25,2@0.3 | Slider_Turn | - |
| Q | Batarang 0x34000244 | Batarang_Start@0 | Batarang -> Batarang_Cosmetic onCosmeticEarlyOut | 5@0.075 | skill_to_cosmetic | - | - | 5@0.1,2@0.25 | Slider_Turn | - |
| W | Martial Arts 0x34000243 | Martial_Arts_Start@0; Martial_Arts_End@0.1 | Martial_Arts; Martial_Arts_End | 2@0.095; 2@0.095 | skill_to_locomotion; (none) | Martial_Arts_End | - | 5@0.3,3@0.3,2@0.45 | - | no stop bundle@0.05,0.1,0.1 |
| E | Cape Sweep 0x34000242 | Batman_Cape_Sweep@0 | Cape_Sweep -> Cape_Sweep_Cosmetic  | 3@0.090 | skill_to_cosmetic | - | - | 3@0.1,2@0.25 | Slider_Propel,Slider_Turn,TurnSpeed | no stop |
| R | The Dark Knight 0x34000248 | Dark_Knight_Start@0 | Dark_Knight | 3@0.017,3@0.467,4@0.420,5@0.200 | skill_to_locomotion | Wildcard_RSkill_Alt,Wildcard_RSkill_End | Wildcard_RSkill_Alt,Wildcard_RSkill_End | 3@0.05,5@0.25,2@0.25 | Slider_Turn,TurnSpeed | no stop bundle@1 |
| passive | Watching, Waiting 0x340002AE | none | - | - |  | - | - | - | - | - |

### Blue Beetle (0x400007fa, graph chr_blue_beetle_behavior.hkb, pack 0xA0000202, 4 kit scripts in its hooks)

| slot | skill / script | ics raises (event@s) | state -> cosmetic tail | hooks code@s | leaves on | needs (external) | never raised | ics signals code@s | graph inputs | movement |
|---|---|---|---|---|---|---|---|---|---|---|
| basic | Basic Attack 0x34000457 | none | Ranged_Critical; Ranged_Basic_Left; Ranged_Basic_Right; Critical_Attack01; Basic_Attack_Melee | 5@0.240,6@0.050; 5@0.240,6@0.050; 5@0.240,6@0.050; 3@0.240,6@0.050; 3@0.240,6@0.050 | basicattack_to_basicattack; basicattack_to_basicattack; basicattack_to_basicattack; basicattack_to_basicattack; basicattack_to_basicattack | - | - | 5@0.3,3@0.3,2@0.45 | Slider_Turn | - |
| Q | Energy Cannon 0x34000451 | Energy_Cannon@0 | Energy_Cannon -> Energy_Cannon_Cosmetic onCosmeticEarlyOut | 5@0.150 | skill_to_cosmetic | - | - | 5@0.2,2@0.3 | Slider_Turn,TurnSpeed | - |
| W | Scarab Scanner 0x34000454 | Scarab_Scanner@0 | Scarab_Scanner | - | skill_to_locomotion | - | - | 5@0.3,3@0.3,2@0.45 | Slider_Turn,TurnSpeed | - |
| E | Stick And Move 0x34000455 | Stick_And_Move@0 | Stick_And_Move | - | skill_to_locomotion | Stick_And_Move_Left,Stick_And_Move_Right,skill_to_locomotion | Stick_And_Move_Left,Stick_And_Move_Right,skill_to_locomotion | 5@0.3,3@0.3,2@0.45 | Slider_Turn,TurnSpeed | bundle@0.05,0.1,0.15,0.2 |
| R | Infiltrator Mode 0x3400044F | Infiltrator_Activate@0 | Main_Machine_Melee | 2@0.220,2@0.280,2@0.296,3@0.013,3@0.100,3@0.140,3@0.216,3@0.240,5@0.200,5@0.260,6@0.050 | Infiltraitor_Deactivate | Basic_Attack,Basic_Attack_Critical,CbtState_Cower,CbtState_Cower_Instant,CbtState_Cower_Recover,CbtState_Dead,CbtState_Death_Induce,CbtState_GetHit,CbtState_GetUp,CbtState_KnockBack,CbtState_KnockDown,CbtState_KnockUp,CbtState_Laugh,CbtState_Laugh_Recover,CbtState_Stasis,CbtState_Stasis_Recover,Emote_Dance,Emote_Joke,Emote_Laugh,Emote_Taunt,Fidget_A,Fidget_B,Fidget_C,Hypersonics,InductionUsage_End,InductionUsage_Start,Infiltraitor_Deactivate,Leathal_Measures,Lethal_Measures_Hit,Mandible_Taser,SuperStrength_CarPickup,SuperStrength_InitCarPickup,SuperStrength_PickupCar,SuperStrength_Rubble_Pickup,SuperStrength_Rubble_Throw,SuperStrength_ThrowCar | Basic_Attack,Basic_Attack_Critical,CbtState_Cower,CbtState_Cower_Instant,CbtState_Cower_Recover,CbtState_Dead,CbtState_Death_Induce,CbtState_GetHit,CbtState_GetUp,CbtState_KnockBack,CbtState_KnockDown,CbtState_KnockUp,CbtState_Laugh,CbtState_Laugh_Recover,CbtState_Stasis,CbtState_Stasis_Recover,Emote_Dance,Emote_Joke,Emote_Laugh,Emote_Taunt,Fidget_A,Fidget_B,Fidget_C,Hypersonics,InductionUsage_End,InductionUsage_Start,Infiltraitor_Deactivate,Leathal_Measures,Lethal_Measures_Hit,Mandible_Taser,SuperStrength_CarPickup,SuperStrength_InitCarPickup,SuperStrength_PickupCar,SuperStrength_Rubble_Pickup,SuperStrength_Rubble_Throw,SuperStrength_ThrowCar | - | AnimationSpeedMultiplier,Slider_Propel,Slider_Turn,TargetHeading,TurnSpeed,cond:GetHitEnabled == 1,cond:ToggleFidget == 1 | no stop |
| passive | Reach Directive: Disru 0x34000456 | none | - | - |  | - | - | - | - | - |

### Catwoman (0x4000041c, graph chr_catwoman_behavior.hkb, pack 0xA000012C, 4 kit scripts in its hooks)

| slot | skill / script | ics raises (event@s) | state -> cosmetic tail | hooks code@s | leaves on | needs (external) | never raised | ics signals code@s | graph inputs | movement |
|---|---|---|---|---|---|---|---|---|---|---|
| basic | Basic Attack 0x34000279 | none | Critical_Attack; Basic_Attack_Claw; Basic_Attack_Kick | 3@0.240,6@0.050; 3@0.240,6@0.050; 3@0.240,6@0.050 | basicattack_to_basicattack; basicattack_to_basicattack; basicattack_to_basicattack | - | - | 6@0.05,3@0.25,2@0.3 | Slider_Turn | - |
| Q | Whip Strike 0x34000276 | Catwoman_WhipStrike_PB_Start@0 | WhipStrike PB -> WhipStrike PB_Cosmetic onCosmeticEarlyOut | 3@0.170 | skill_to_cosmetic | - | - | 3@0.2,2@0.25 | Slider_Turn,TurnSpeed | - |
| W | Cat's Paw 0x34000277 | Catwoman_CatsPaw_Start@0 | Cats Paw -> Cats Paw_Cosmetic onCosmeticEarlyOut | 3@0.125 | skill_to_cosmetic | - | - | 3@0.15,2@0.25 | Slider_Turn,TurnSpeed | - |
| E | Acrobat 0x3400027B | Catwoman_Acrobat_Start@0 | Acrobat | - | Acrobat_to_Loc | - | - | 5@0.3,3@0.3,2@0.45 | - | - |
| R | Bad Kitty 0x3400027A | Catwoman_BadKitty_Start@0 | Bad Kitty | - | (none) | - | - | - | Slider_Propel,Slider_Turn | no stop |
| passive | Cat Burglar 0x34000278 | none | - | - |  | - | - | - | - | - |

### Cyborg (0x400003b2, graph chr_cyborg_behavior.hkb, pack 0xA0000112, 5 kit scripts in its hooks)

| slot | skill / script | ics raises (event@s) | state -> cosmetic tail | hooks code@s | leaves on | needs (external) | never raised | ics signals code@s | graph inputs | movement |
|---|---|---|---|---|---|---|---|---|---|---|
| basic | Basic Attack 0x34000238 | none | Critical_Attack; Basic_Attack; Critical_Attack_PlasmaCannon; Basic_Attack_PlasmaCannon | 5@0.240,6@0.050; 5@4.800,6@1.000; 5@0.240,6@0.050; 5@0.240,6@0.050 | basicattack_to_basicattack; basicattack_to_basicattack; basicattack_to_basicattack; basicattack_to_basicattack | - | - | 5@0.3,3@0.3,2@0.45 | Slider_Turn | - |
| Q | Tracer Shot 0x34000236 | Cyborg_TracerShot@0 | Tracer Shot -> Tracer Shot_Cosmetic onCosmeticEarlyOut | 5@0.080 | skill_to_cosmetic | - | - | 5@0.1,2@0.15 | Slider_Turn,TurnSpeed | - |
| W | Charged Burst 0x34000235 | Cyborg_ParalyzingShock@0 | Paralyzing Shock -> Paralyzing Shock_Cosmetic onCosmeticEarlyOut | 3@0.140 | skill_to_cosmetic | - | - | 3@0.15,2@0.25 | Slider_Propel,Slider_Turn,TurnSpeed | no stop |
| E | Cascade 0x34000234 | Cyborg_Cascade@0 | Cascade | - | skill_to_locomotion | - | - | - | Slider_Propel,Slider_Turn,TurnSpeed | no stop |
| R | Plasma Cannon 0x34000233 | Cyborg_PlasmaCannon@0; Cyborg_UltStart@0.45 | Plasma Cannon -> Plasma Cannon_Cosmetic onCosmeticEarlyOut | 3@0.310 | skill_to_cosmetic | - | - | 3@0.35,2@0.5 | Slider_Turn,TurnSpeed | - |
| passive | Cybernetic Targeting 0x34000237 | none | - | - |  | - | - | - | - | - |

### Deadshot (0x40000c68, graph chr_deadshot_behavior.hkb, pack 0xA0000337, 5 kit scripts in its hooks)

| slot | skill / script | ics raises (event@s) | state -> cosmetic tail | hooks code@s | leaves on | needs (external) | never raised | ics signals code@s | graph inputs | movement |
|---|---|---|---|---|---|---|---|---|---|---|
| basic | Basic Attack 0x34000697 | none | Crit_Wrist; Basic_Rifle; Crit_Rifle; Basic_Wrist_Left; Basic_Wrist_Right | 5@0.240,6@0.050; 5@0.240,6@0.050; 5@0.240,6@0.050; 5@0.240,6@0.050; 5@0.240,6@0.050 | basicattack_to_basicattack; basicattack_to_basicattack; basicattack_to_basicattack; basicattack_to_basicattack; basicattack_to_basicattack | - | - | 6@0.05,5@0.25,2@0.3 | Slider_Turn | - |
| Q | Called Shot 0x34000696 | Wildcard_QSkill@0 | Called Shot - Wrist -> Called_Shot_Wrist_Cosm onCosmeticEarlyOut; Called Shot - Rifle -> Called_Shot_Rifle_Cosm onCosmeticEarlyOut | 3@0.100; 3@0.100 | skill_to_cosmetic; skill_to_cosmetic | - | - | 3@0.1,2@0.25 | Slider_Turn,TurnSpeed | - |
| W | Sniper's Eye 0x34000692 | Rifle_Activate@0 | Snipers Eye - Wrist | - | skill_to_locomotion | - | - | - | Slider_Propel,Slider_Turn,TurnSpeed | no stop |
| E | Cover To Cover 0x34000695 | Wildcard_ESkill@0 | Cover to Cover - Wrist; Cover to Cover - Rifle | - | skill_to_locomotion; skill_to_locomotion | - | - | - | Slider_Propel,Slider_Turn,TurnSpeed | no stop |
| R | One Shot, One Kill 0x34000694 | none | One Shot One Kill Wrist | - | skill_to_locomotion | Wildcard_RSkill_End | Wildcard_RSkill_End | - | Slider_Turn,TurnSpeed | no stop |
| passive | Shadowy Employers 0x34000693 | none | - | - |  | - | - | - | - | - |

### Deathstroke (0x40000c19, graph chr_deathstroke_behavior.hkb, pack 0xA000030E, 5 kit scripts in its hooks)

| slot | skill / script | ics raises (event@s) | state -> cosmetic tail | hooks code@s | leaves on | needs (external) | never raised | ics signals code@s | graph inputs | movement |
|---|---|---|---|---|---|---|---|---|---|---|
| basic | Basic Attack 0x34000637 | none | Crit_Melee_Large; Basic_Melee_Large; MercilessAttack | 3@0.200,6@0.050; 3@0.200,6@0.050; 3@0.100,6@0.050 | basicattack_to_basicattack; basicattack_to_basicattack; basicattack_to_basicattack | - | - | 5@0.3,3@0.3,2@0.45 | Slider_Turn | - |
| Q | Blade Rush 0x340007DB | 0x100003bd@0; skill_to_locomotion@0.15 | hook only: Dash_Q | - |  | - | - | 5@0.3,3@0.3,2@0.45 | - | no stop bundle@0.05,0.1,0.15,0.15 |
| W | Healing Factor 0x340007DF | Wildcard_WSkill@0; skill_to_locomotion@0 | Healing_Factor | - | skill_to_locomotion | skill_to_locomotion | - | - | Slider_Propel,Slider_Turn,TurnSpeed | no stop skill_to_locomotion@0 ends the state (authored end) bundle@1 |
| E | Explosive Rounds 0x340007DE | Wildcard_ESkill@0 | Skillshot_E -> StandardSkill_E_Cosmetic onCosmeticEarlyOut | 5@0.060 | skill_to_cosmetic | - | - | 5@0.1,2@0.2 | Slider_Turn,TurnSpeed | - |
| R | Bullet Rain 0x340007DD | Wildcard_RSkill@0 | Dash_R -> Dash_R_Cosmetic onCosmeticEarlyOut; Dash_Q -> Dash_Q_Cosmetic onCosmeticEarlyOut | 3@0.200 | skill_to_cosmetic,skill_to_locomotion; skill_to_cosmetic,skill_to_locomotion | Skill_Dash_End,skill_to_locomotion; Skill_Dash_End,skill_to_locomotion | Skill_Dash_End,skill_to_locomotion; Skill_Dash_End,skill_to_locomotion | 3@0.25,2@0.25 | Slider_Turn,TurnSpeed | no stop bundle@0.05,0.1,0.15,0.15 |
| passive | Battle Fury 0x340007DC | none | - | - |  | - | - | - | - | - |

### Dex-Starr (0x40000c75, graph chr_dexstarr_behavior.hkb, pack 0xA000033F, 4 kit scripts in its hooks)

| slot | skill / script | ics raises (event@s) | state -> cosmetic tail | hooks code@s | leaves on | needs (external) | never raised | ics signals code@s | graph inputs | movement |
|---|---|---|---|---|---|---|---|---|---|---|
| basic | Basic Attack 0x340006BA | none | Basic_Melee_Large; Crit_Melee_Small | 3@0.200,6@0.050; 3@0.200,6@0.050 | basicattack_to_basicattack; basicattack_to_basicattack | - | - | 6@0.05,3@0.25,2@0.25 | Slider_Turn | - |
| Q | Lacerate 0x340006B9 | Wildcard_QSkill@0 | StandardSkill_Q -> StandardSkill_Q_Cosm onCosmeticEarlyOut | 3@0.090 | skill_to_cosmetic,skill_to_locomotion | skill_to_locomotion | skill_to_locomotion | 3@0.1,2@0.35 | Slider_Propel,Slider_Turn,TurnSpeed | no stop |
| W | Pounce 0x340006B7 | Wildcard_WSkill@0; skill_to_locomotion@0 | Dash_W | - | skill_to_locomotion | Skill_Dash_End,Skill_Dash_Start,skill_to_locomotion | Skill_Dash_End,Skill_Dash_Start | - | Slider_Propel,Slider_Turn,TurnSpeed | no stop skill_to_locomotion@0 ends the state (authored end) |
| E | Caustic Flood 0x340006B6 | Wildcard_ESkill@0 | CausticFlood | - | skill_to_locomotion | skill_to_locomotion | skill_to_locomotion | 5@0.3,3@0.3,2@0.45 | Slider_Propel,Slider_Turn,UsToTargetHeading | no stop |
| R | Shred The World 0x340006B5 | Wildcard_RSkill@0; skill_to_locomotion@0.1; skill_to_locomotion@0.1 | Skillshot_R -> Skillshot_R_Cosm onCosmeticEarlyOut | 5@0.100 | skill_to_cosmetic,skill_to_locomotion | skill_to_locomotion | - | 5@0.1,2@0.15 | Slider_Turn,TurnSpeed | skill_to_locomotion@0.1 cuts the skill state before its cast end |
| passive | Vengeful Rage 0x340006B8 | none | - | - |  | - | - | - | - | - |

### Doomsday (0x4000015a, graph chr_doomsday_behavior.hkb, pack 0xA000011C, 5 kit scripts in its hooks)

| slot | skill / script | ics raises (event@s) | state -> cosmetic tail | hooks code@s | leaves on | needs (external) | never raised | ics signals code@s | graph inputs | movement |
|---|---|---|---|---|---|---|---|---|---|---|
| basic | Basic Attack 0x340000A9 | none | Standing_Critical_Attack; Standing_Basic_Attack | 3@0.240,6@0.050; 3@0.240,6@0.050 | basicattack_to_basicattack; basicattack_to_basicattack | - | - | 6@0.05,3@0.25,2@0.3 | Slider_Turn,TurnSpeed | - |
| Q | Pummeling Assault 0x340000DF | none | Doomsday_Pummelling_Assault -> Doomsday_Pummelling_Assault_Cosmetic onCosmeticEarlyOut | 3@0.771 | skill_to_cosmetic | - | - | 3@0.8,2@0.85 | AnimationSpeedMultiplier,Slider_Turn,TurnSpeed | no stop bundle@0.05,0.1,0.15,0.2 |
| W | Berserk 0x3400015D | none | Doomsday_Berserk | 2@0.200,3@0.050 | skill_to_locomotion | - | - | - | Slider_Propel,Slider_Turn,TurnSpeed | no stop |
| E | Charge 0x340000E0 | none | Doomsday_Charge -> Charge_End_Cosmetic onCosmeticEarlyOut | - | skill_to_cosmetic | Doomsday_Charge_End,Doomsday_Charge_Grab | Doomsday_Charge_End,Doomsday_Charge_Grab | 5@0.3,3@0.3,2@0.45 | - | no stop |
| R | Kryptonian Rage 0x340000E1 | none | Doomsday_Kryptonian_Rage | 2@0.200 | skill_to_locomotion | - | - | - | Slider_Propel | no stop |
| passive | Revenge 0x340000E6 | none | - | - |  | - | - | - | - | - |

### Flash (0x40000396, graph chr_flash_behavior.hkb, pack 0xA0000121, 5 kit scripts in its hooks)

| slot | skill / script | ics raises (event@s) | state -> cosmetic tail | hooks code@s | leaves on | needs (external) | never raised | ics signals code@s | graph inputs | movement |
|---|---|---|---|---|---|---|---|---|---|---|
| basic | Basic Attack 0x3400021A | none | Critical_Attack; Basic_Attack | 3@0.240,6@0.050; 3@0.240,6@0.050 | basicattack_to_basicattack; basicattack_to_basicattack | - | - | 6@0.05,3@0.25,2@0.3 | Slider_Turn | - |
| Q | Flash Attack 0x3400021B | FlashAttack_Start@0; FlashAttack_End@0.15 | FlashAttack; Locomotion | - | FlashAttack_End; (none) | FlashAttack_End; Emote_Dance,Emote_Joke,Emote_Laugh,Emote_Taunt,Fidget_A,Fidget_B,Fidget_C,Fidget_D | Emote_Dance,Emote_Joke,Emote_Laugh,Emote_Taunt,Fidget_A,Fidget_B,Fidget_C,Fidget_D | 5@0.3,3@0.3,2@0.45 | Slider_Propel,Slider_Turn,TurnSpeed,cond:ToggleFidget == 1 | no stop bundle@0.05,0.1,0.15,0.15 |
| W | F=MA 0x34000219 | FMA_Start@0 | FMA | - | (none) | - | - | - | Slider_Propel,Slider_Turn | no stop |
| E | Hyper Vibration 0x34000218 | HyperVibration_Start@0 | HyperVibration | - | (none) | - | - | - | Slider_Propel,Slider_Turn | no stop |
| R | Speed Storm 0x34000217 | SpeedStorm_Start@0; SpeedStorm_End@2.75 | SpeedStorm; SpeedStorm_End | 3@0.600 | Flash_SpeedStorm_End; (none) | Flash_SpeedStorm_End,SpeedStorm_End | Flash_SpeedStorm_End | 3@0.65 | - | no stop |
| passive | Speed Force 0x34000216 | none | - | - |  | - | - | - | - | - |

### Gaslight Batman (0x40000086, graph chr_batman_gaslight_behavior.hkb, pack 0xA0000122, 5 kit scripts in its hooks)

| slot | skill / script | ics raises (event@s) | state -> cosmetic tail | hooks code@s | leaves on | needs (external) | never raised | ics signals code@s | graph inputs | movement |
|---|---|---|---|---|---|---|---|---|---|---|
| basic | Basic Attack 0x34000037 | none | Standing Critical Attack; Basic_Attack_Left; Basic_Attack_Right | 5@0.282,6@0.059; 5@0.282,6@0.059; 5@0.282,6@0.059 | basicattack_to_basicattack; basicattack_to_basicattack; basicattack_to_basicattack | - | - | 6@0.1,5@0.3,2@0.3 | Slider_Turn,TurnSpeed | - |
| Q | Sonic Batarang 0x3400003B | none | Batarang -> Batarang_Cosmetic onCosmeticEarlyOut | 5@0.128 | skill_to_cosmetic | - | - | 5@0.15,2@0.2 | Slider_Turn,TurnSpeed | - |
| W | Sonic Shell 0x3400003A | none | Sonic_Shell -> Sonic_Shell_Cosmetic onCosmeticEarlyOut | 5@0.080 | skill_to_cosmetic | - | - | 5@0.1,2@0.15 | Slider_Turn,TurnSpeed | - |
| E | Bat Flight 0x34000038 | none | BatFlight | 3@0.082 | skill_to_locomotion | - | - | 3@0.1 | Slider_Propel,Slider_Turn,TurnSpeed | no stop bundle@0.05,0.1,0.15,0.2 |
| R | Bat Scream 0x34000039 | CbtState_Trigger_Start@0.85; CbtState_Trigger_Start@0.95; CbtState_Trigger_Start@1.05 | hook only: Bat_Scream | - |  | - | - | 5@0.85,2@1.15 | - | bundle@0.95 |
| passive | Echoes 0x34000048 | none | - | - |  | - | - | - | - | - |

### Gaslight Catwoman (0x40000262, graph chr_gaslight_catwoman_behavior.hkb, pack 0xA000010B, 4 kit scripts in its hooks)

| slot | skill / script | ics raises (event@s) | state -> cosmetic tail | hooks code@s | leaves on | needs (external) | never raised | ics signals code@s | graph inputs | movement |
|---|---|---|---|---|---|---|---|---|---|---|
| basic | Basic Attack 0x3400018E | none | Standing_Critical_Attack; Standing_Basic_Attack | 3@0.240,6@0.050; 3@0.240,6@0.050 | basicattack_to_basicattack; basicattack_to_basicattack | - | - | 6@0.05,3@0.25,2@0.3 | Slider_Turn | - |
| Q | Steampowered Claws 0x340001B7 | none | SteamClaws -> SteamClaws_Cosmetic onCosmeticEarlyOut | 5@0.064 | skill_to_cosmetic | - | - | 5@0.1,2@0.15 | Slider_Turn,TurnSpeed | - |
| W | Shred 0x3400034C | Gaslight_Catwoman_Shred@0 | Shred -> Shred_Cosmetic onCosmeticEarlyOut | 3@0.090 | skill_to_cosmetic | - | - | 3@0.1,2@0.2 | Slider_Turn,TurnSpeed | - |
| E | Blood Hunt 0x340001C6 | Gaslight_Catwoman_StalkStart@0.1 | - | - |  | - | - | - | - | no stop |
| R | Predator's Grace 0x340001CE | none | PredatorsGrace | 2@0.210 | skill_to_locomotion | - | - | - | - | bundle@0.05,0.1,0.15,0.2 |
| passive | Sharpened Claws  | none | - | - |  | - | - | - | - | - |

### Gaslight Joker (0x4000038d, graph chr_gaslight_joker_behavior.hkb, pack 0xA0000114, 4 kit scripts in its hooks)

| slot | skill / script | ics raises (event@s) | state -> cosmetic tail | hooks code@s | leaves on | needs (external) | never raised | ics signals code@s | graph inputs | movement |
|---|---|---|---|---|---|---|---|---|---|---|
| basic | Basic Attack 0x34000200 | none | Critical_Attack; Basic_Attack_Right; Basic_Attack_Left; Fetid Cleaver Basic | 3@0.240,6@0.050; 3@0.240,6@0.050; 3@0.200,6@0.050; 3@0.053 | basicattack_to_basicattack; basicattack_to_basicattack; basicattack_to_basicattack; basicattack_to_basicattack | - | - | 5@0.3,3@0.3,2@0.45 | Slider_Turn | - |
| Q | Fetid Cleaver 0x34000205 | none | - | - |  | - | - | - | - | no stop |
| W | Ham Toss 0x3400020A | Gaslight_Joker_ShowerOfFilth@0 | Shower of Filth -> Shower of Filth_Cosmetic onCosmeticEarlyOut | 5@0.160 | skill_to_cosmetic | - | - | 5@0.2,2@0.3 | Slider_Turn,TurnSpeed | bundle@1 |
| E | Snack Time! 0x34000202 | Gaslight_Joker_HamSnack@0 | Ham Snack | 3@0.253 | skill_to_locomotion | - | - | - | Slider_Propel,Slider_Turn,TurnSpeed | no stop |
| R | Rat Swarm 0x34000201 | Gaslight_Joker_RatSwarm@0 | Rat Swarm | 3@0.436 | skill_to_locomotion | - | - | - | Slider_Propel,Slider_Turn,TurnSpeed | no stop |
| passive | Blood Money 0x34000203 | none | - | - |  | - | - | - | - | - |

### Green Arrow (0x400006f9, graph chr_green_arrow_behavior.hkb, pack 0xA00001F3, 3 kit scripts in its hooks)

| slot | skill / script | ics raises (event@s) | state -> cosmetic tail | hooks code@s | leaves on | needs (external) | never raised | ics signals code@s | graph inputs | movement |
|---|---|---|---|---|---|---|---|---|---|---|
| basic | Basic Attack 0x34000411 | Basic_Attack@0 | Basic_Attack_Ballistic | 5@0.240,6@0.050 | basicattack_to_basicattack | - | - | 6@0.05,5@0.25,2@0.3 | Slider_Turn | - |
| Q | Superfoam Arrows 0x3400040E | SetQuiverSuperfoam@0; Wildcard_QSkill@0; Fidget_Abort@0; GreenArrow_Bullseye_End@0.2 | Superfoam -> Superfoam_Cosmetic ; Idling; Locomotion | 2@0.280 | skill_to_cosmetic; CommitFidget; (none) | Emote_Dance,Emote_Joke,Emote_Laugh,Emote_Taunt,Fidget_A,Fidget_B,Fidget_C,Fidget_D | Emote_Dance,Emote_Joke,Emote_Laugh,Emote_Taunt,Fidget_A,Fidget_B,Fidget_C,Fidget_D | 2@0.3 | Slider_Propel,Slider_Turn,TurnSpeed,cond:ToggleFidget == 1 | skill_to_locomotion@0.2 cuts the skill state before its cast end bundle@0.05,0.1,0.15,0.2 |
| W | Ballistic Arrows 0x3400040D | SetQuiverBallistic@0; Fidget_Abort@0 | Idling | - | CommitFidget | - | - | - | Slider_Propel | no stop bundle@1 |
| E | Thermite Arrows 0x34000410 | SetQuiverThermite@0; Fidget_Abort@0 | Idling | - | CommitFidget | - | - | - | Slider_Propel | no stop |
| R | Bullseye 0x3400040C | Wildcard_RSkill@0 | Bullseye | 2@0.280 | GreenArrow_Bullseye_End | GreenArrow_BullseyeSuperfoam,GreenArrow_Bullseye_Fire | GreenArrow_BullseyeSuperfoam,GreenArrow_Bullseye_Fire | - | Slider_Propel,Slider_Turn,TurnSpeed | no stop |
| passive | Adaptable Ammo 0x34000412 | none | - | - |  | - | - | - | - | - |

### Green Lantern (0x4000034d, graph chr_green_lantern_behavior.hkb, pack 0xA0000115, 5 kit scripts in its hooks)

| slot | skill / script | ics raises (event@s) | state -> cosmetic tail | hooks code@s | leaves on | needs (external) | never raised | ics signals code@s | graph inputs | movement |
|---|---|---|---|---|---|---|---|---|---|---|
| basic | Basic Attack 0x340001E7 | none | Standing Critical Attack; Basic_Attack_Left; Basic_Attack_Right | 5@0.282,6@0.059; 5@0.282,6@0.059; 5@0.282,6@0.059 | basicattack_to_basicattack; basicattack_to_basicattack; basicattack_to_basicattack | - | - | 6@0.1,5@0.3,2@0.3 | Slider_Turn,TurnSpeed | - |
| Q | Slam 0x340001E6 | Green_Lantern_Slam@0 | Slam -> Slam_Cosmetic  | - | skill_to_cosmetic | - | - | 5@0.3,3@0.3,2@0.45 | Slider_Turn,TurnSpeed | - |
| W | Constrict 0x340001E4 | Green_Lantern_Constrict@0 | Constrict -> Constrict_Cosmetic onCosmeticEarlyOut | 5@0.020 | skill_to_cosmetic | - | - | 5@0.05,2@0.15 | Slider_Turn,TurnSpeed | - |
| E | Missile Barrage 0x340001E3 | Green_Lantern_Missile_Barrage_1@0 | Missile Barrage 1 -> Missile Barrage_Cosmetic onCosmeticEarlyOut | 5@0.100 | skill_to_cosmetic | - | - | 5@0.1,2@0.15 | Slider_Propel,Slider_Turn,TurnSpeed | - |
| R | Green Lantern's Light 0x340001E2 | Green_Lantern_Green_Lanterns_Light@0 | Green Lantern's Light -> Green Lantern's Light Cosmetic onCosmeticEarlyOut | 3@0.060 | skill_to_cosmetic | - | - | 3@0.1,2@0.25 | Slider_Turn,TurnSpeed | - |
| passive | Indomitable Will 0x340001E5 | none | - | - |  | - | - | - | - | - |

### Harley Quinn (0x4000054a, graph chr_harley_quinn_behavior.hkb, pack 0xA0000186, 5 kit scripts in its hooks)

| slot | skill / script | ics raises (event@s) | state -> cosmetic tail | hooks code@s | leaves on | needs (external) | never raised | ics signals code@s | graph inputs | movement |
|---|---|---|---|---|---|---|---|---|---|---|
| basic | Basic Attack 0x34000343 | none | Critical_Attack; Basic_Attack | 3@0.200,5@0.240; 3@0.200,5@0.240 | basicattack_to_basicattack; basicattack_to_basicattack | - | - | 3@0.25,5@0.25,2@0.3 | Slider_Turn | - |
| Q | Pies! 0x34000342 | none | Pies -> Pies_Cosmetic  | 3@0.100 | skill_to_cosmetic | - | - | - | Slider_Propel,Slider_Turn,TurnSpeed | no stop |
| W | Back Off 0x34000341 | HarleyQuinn_BackOff@0 | Back Off -> Back Off_Cosmetic onCosmeticEarlyOut | 3@0.060,5@0.070 | skill_to_cosmetic | - | - | 3@0.1,5@0.1,2@0.25 | Slider_Turn,TurnSpeed | bundle@1 |
| E | Best Medicine 0x3400033F | none | Best Medicine -> Best Medicine_Cosmetic  | - | skill_to_cosmetic | - | - | 5@0.3,3@0.3,2@0.45 | Slider_Propel,Slider_Turn,TurnSpeed | no stop |
| R | Puddin' Time! 0x3400033E | HarleyQuinn_PuddinTime@0 | Puddin Time -> Puddin Time_Cosmetic onCosmeticEarlyOut | 3@0.280 | skill_to_cosmetic | - | - | 3@0.3,2@0.5 | Slider_Turn,TurnSpeed | bundle@0.3,1.55 |
| passive | BFFs 0x34000340 | none | - | - |  | - | - | - | - | - |

### Hawkgirl (0x40000ae2, graph chr_hawkgirl_behavior.hkb, pack 0xA00002B4, 4 kit scripts in its hooks)

| slot | skill / script | ics raises (event@s) | state -> cosmetic tail | hooks code@s | leaves on | needs (external) | never raised | ics signals code@s | graph inputs | movement |
|---|---|---|---|---|---|---|---|---|---|---|
| basic | Basic Attack 0x34000579 | none | Crit_Melee_Large; Basic_Melee_Large; Empower_Melee | 3@0.240,6@0.050; 3@0.200,3@0.240,6@0.050; 3@0.130,6@0.050 | basicattack_to_basicattack; basicattack_to_basicattack; basicattack_to_basicattack | - | - | 5@0.3,3@0.3,2@0.45 | Slider_Turn | - |
| Q | Mace Throw 0x34000574 | Wildcard_QSkill@0 | Skillshot_Q -> Skillshot_Q_Cosmetic onCosmeticEarlyOut | 5@0.110 | skill_to_cosmetic | - | - | 5@0.15,2@0.25 | Slider_Turn,TurnSpeed | - |
| W | Soar 0x34000575 | ActivateSoar@0; Wildcard_WSkill@0 | Selfbuff_W; SuperStrength_Car; SuperStrength_Rubble | 2@0.600,3@0.013,5@0.250; 2@0.296,2@0.345,3@0.216,5@0.260 | skill_to_locomotion; Wildcard_WSkill,skill_to_locomotion; SuperStrength_Rubble_End,Wildcard_WSkill | SuperStrength_CarPickup,SuperStrength_PickupCar,SuperStrength_ThrowCar,Wildcard_WSkill; SuperStrength_Rubble_Throw,Wildcard_WSkill | SuperStrength_CarPickup,SuperStrength_PickupCar,SuperStrength_ThrowCar; SuperStrength_Rubble_Throw | - | Slider_Propel,Slider_Turn,TurnSpeed | no stop |
| E | Haymaker 0x34000576 | DeactivateSoar@2.05 | - | - |  | - | - | - | - | no stop |
| R | Howling Eye 0x34000577 | none | StandardSkill_R -> StandardSkill_R_Cosmetic onCosmeticEarlyOut | 3@0.125,5@0.200 | skill_to_cosmetic | - | - | 3@0.15,5@0.25,2@0.45 | Slider_Turn,TurnSpeed | no stop |
| passive | Thrill of Battle 0x34000578 | none | - | - |  | - | - | - | - | - |

### Huntress (0x40000cd3, graph chr_huntress_behavior.hkb, pack 0xA0000362, 5 kit scripts in its hooks)

| slot | skill / script | ics raises (event@s) | state -> cosmetic tail | hooks code@s | leaves on | needs (external) | never raised | ics signals code@s | graph inputs | movement |
|---|---|---|---|---|---|---|---|---|---|---|
| basic | Basic Attack 0x3400070F | none | Empower_Ranged; Basic_Ranged_Left; Basic_Ranged_Right; Basic_Crit_Left; Basic_Crit_Right | 5@0.240,6@0.050; 5@0.270,6@0.050; 5@0.270,6@0.050; 5@0.270,6@0.050; 5@0.270,6@0.050 | basicattack_to_basicattack; basicattack_to_basicattack; basicattack_to_basicattack; basicattack_to_basicattack; basicattack_to_basicattack | - | - | 5@0.3,3@0.3,2@0.45 | Slider_Turn,UsToTargetHeading | - |
| Q | Snap Shot 0x3400070C | Wildcard_QSkill@0 | Snap_Shot -> Snap_Shot_Cosm  | - | skill_to_cosmetic | - | - | - | Slider_Propel,Slider_Turn,TurnSpeed,UsToTargetHeading | no stop |
| W | Hunter's Quarrel 0x3400070B | Wildcard_WSkill@0 | Hunters Quarrel -> Hunters Quarrel_cosm onCosmeticEarlyOut | 5@0.125 | skill_to_cosmetic | - | - | 5@0.15,2@0.2 | Slider_Turn,TurnSpeed | - |
| E | Grapple Bolt 0x3400070A | Wildcard_ESkill@0; skill_to_locomotion@0.15 | Grapple Bolt -> Dash_E_End_Cosm onCosmeticEarlyOut | 5@0.100 | skill_to_cosmetic,skill_to_locomotion | Skill_Dash_End,Skill_Dash_Start,skill_to_locomotion | Skill_Dash_End,Skill_Dash_Start | 5@0.1,2@0.15 | Slider_Propel,Slider_Turn,TurnSpeed | skill_to_locomotion@0.15 cuts tail 0.03s after it began |
| R | Rapid Deployment 0x3400070D | Wildcard_RSkill@0 | Rapid Reload | - | skill_to_locomotion | - | - | - | Slider_Propel,Slider_Turn,TurnSpeed | no stop |
| passive | Tech Bolts 0x34000709 | none | - | - |  | - | - | - | - | - |

### John Stewart (0x40000e57, graph chr_john_stewart_behavior.hkb, pack 0xA000039F, 5 kit scripts in its hooks)

| slot | skill / script | ics raises (event@s) | state -> cosmetic tail | hooks code@s | leaves on | needs (external) | never raised | ics signals code@s | graph inputs | movement |
|---|---|---|---|---|---|---|---|---|---|---|
| basic | Basic Attack 0x340007A6 | none | Basic_Ranged_Small; Crit_Ranged_Small | 0@0.050,5@0.240; 0@0.050,5@0.240 | basicattack_to_basicattack; basicattack_to_basicattack | - | - | 5@0.25,2@0.3 | Slider_Turn | - |
| Q | full_auto 0x340007A7 | none | StandardSkill_Q -> StandardSkill_Q_Cosm onCosmeticEarlyOut | 3@0.203 | skill_to_cosmetic,skill_to_locomotion | skill_to_locomotion | skill_to_locomotion | 3@0.25,2@0.45 | Slider_Turn,TurnSpeed | - |
| W | claymore_mine 0x340007A8 | none | StandardSkill_W -> StandardSkill_W_Cosm onCosmeticEarlyOut | 3@0.203 | skill_to_cosmetic,skill_to_locomotion | skill_to_locomotion | skill_to_locomotion | 3@0.25,2@0.45 | Slider_Turn,TurnSpeed | bundle@1 |
| E | forward_base 0x340007A9 | none | Selfbuff_E | - | skill_to_locomotion | - | - | 5@0.3,3@0.3,2@0.45 | Slider_Propel,Slider_Turn,TurnSpeed | - |
| R | omni_turret 0x340007AA | none | StandardSkill_R -> StandardSkill_R_Cosm onCosmeticEarlyOut | 3@0.203 | skill_to_cosmetic,skill_to_locomotion | skill_to_locomotion | skill_to_locomotion | 3@0.25,2@0.45 | Slider_Turn,TurnSpeed | - |
| passive | architects_will 0x340007AB | none | - | - |  | - | - | - | - | - |

### Katana (0x40000ba6, graph chr_katana_behavior.hkb, pack 0xA00002E3, 5 kit scripts in its hooks)

| slot | skill / script | ics raises (event@s) | state -> cosmetic tail | hooks code@s | leaves on | needs (external) | never raised | ics signals code@s | graph inputs | movement |
|---|---|---|---|---|---|---|---|---|---|---|
| basic | Basic Attack 0x340005BB | UnSheath_Blade@0 | hook only: Crit_Melee_Large,Basic_Melee_Large,Vendetta,Basic_Quick_Draw | - |  | - | - | 5@0.3,3@0.3,2@0.45 | - | - |
| Q | Slash 0x340005B8 | Katana_Slash@0; UnSheath_Blade@0 | Slash -> Slash_Cosmetic onCosmeticEarlyOut | 3@0.010 | skill_to_cosmetic | - | - | 3@0.05,2@0.15 | Slider_Turn,TurnSpeed | - |
| W | Cross Step 0x340005B7 | Katana_Cross_Step@0; UnSheath_Blade@0; skill_to_locomotion@0.15 | Cross_Step | - | skill_to_locomotion | skill_to_locomotion | - | 5@0.3,3@0.3,2@0.45 | Slider_Turn,TurnSpeed | no stop skill_to_locomotion@0.15 ends the state (authored end) bundle@0.05,0.1,0.15,0.15 |
| E | Kendo 0x340005BA | none | - | - |  | - | - | - | - | no stop |
| R | Thousand Cuts 0x340005B6 | Katana_Thousand_Cuts_Start@0; UnSheath_Blade@0.3; Katana_Thousand_Cuts_1@0.5; skill_to_locomotion@0.9 | Thousand_Cuts_Start; Thousand_Cuts_1 | 3@end-0.01; 3@0.167 | skill_to_locomotion; skill_to_locomotion | skill_to_locomotion; skill_to_locomotion | - | 5@0.3,3@0.3,2@0.45 | - | no stop skill_to_locomotion@0.9 bundle@0.4 |
| passive | Soultaker 0x340005B9 | none | - | - |  | - | - | - | - | - |

### Krypto (0x40000be4, graph chr_krypto_behavior.hkb, pack 0xA00002F7, 5 kit scripts in its hooks)

| slot | skill / script | ics raises (event@s) | state -> cosmetic tail | hooks code@s | leaves on | needs (external) | never raised | ics signals code@s | graph inputs | movement |
|---|---|---|---|---|---|---|---|---|---|---|
| basic | Basic Attack 0x340005F5 | none | Crit_Melee_Large; Basic_Melee_Large | 3@0.240,6@0.050; 3@0.240,6@0.050 | basicattack_to_basicattack; basicattack_to_basicattack | - | - | 6@0.05,3@0.25,2@0.3 | Slider_Turn | - |
| Q | Fetch! 0x340005EE | Wildcard_QSkill@0 | The_Stick -> The_Stick_Cosmetic  | 5@0.100 | skill_to_cosmetic | - | - | 5@0.1,2@0.25 | Slider_Propel,Slider_Turn,TurnSpeed | - |
| W | Man's Best Friend 0x340005F2 | Wildcard_WSkill@0; skill_to_locomotion@0.1 | Vigilance | - | skill_to_locomotion | Skill_Dash_End | Skill_Dash_End | 5@0.3,3@0.3,2@0.45 | Slider_Turn,TurnSpeed | no stop skill_to_locomotion@0.1 bundle@0.05,0.1,0.1,1 |
| E | On The Hunt 0x340005F0 | none | On_The_Hunt | - | skill_to_locomotion | - | - | - | Slider_Propel,Slider_Turn,TurnSpeed | no stop |
| R | Piercing Howl 0x340005F1 | Wildcard_RSkill@0 | Piercing_Howl -> Piercing_Howl_Cosmetic onCosmeticEarlyOut | 3@0.190 | skill_to_cosmetic | - | - | 3@0.2,2@0.3 | Slider_Turn,TurnSpeed | bundle@0.2,0.55 |
| passive | Vigilance 0x340005EF | none | - | - |  | - | - | - | - | - |

### Lex Luthor (0x40000b70, graph chr_lex_luthor_behavior.hkb, pack 0xA00002DE, 5 kit scripts in its hooks)

| slot | skill / script | ics raises (event@s) | state -> cosmetic tail | hooks code@s | leaves on | needs (external) | never raised | ics signals code@s | graph inputs | movement |
|---|---|---|---|---|---|---|---|---|---|---|
| basic | Basic Attack 0x340005AD | none | Basic_Ranged_Small; Crit_Ranged_Small; Empower | 5@0.240,6@0.050,6@0.200; 5@0.240,6@0.050; 5@0.240,6@0.050 | basicattack_to_basicattack; basicattack_to_basicattack; basicattack_to_basicattack | - | - | 6@0.05,5@0.25,2@0.3 | Slider_Turn | - |
| Q | LexCorp Sentry 0x340005AB | Wildcard_QSkill@0 | Skillshot_Q | - | skill_to_locomotion | - | - | 5@0.3,3@0.3,2@0.45 | Slider_Propel,Slider_Turn,TurnSpeed | no stop |
| W | Tactical Disruption 0x340005A9 | Wildcard_WSkill@0 | StandardSkill_W -> StandardSkill_W_Cosm onCosmeticEarlyOut | 3@0.100 | skill_to_cosmetic | - | - | 3@0.1,2@0.25 | Slider_Turn,TurnSpeed | bundle@1 |
| E | Critical Mass 0x340007CB | Wildcard_ESkill@0 | StandardSkill_E -> StandardSkill_W_Node_Cosm onCosmeticEarlyOut | 3@0.100 | skill_to_cosmetic | - | - | 3@0.1,2@0.25 | Slider_Turn,TurnSpeed | - |
| R | Orbital Remediation 0x340005A8 | Wildcard_RSkill@0 | StandardSkill_R -> StandardSkill_R_Cosm onCosmeticEarlyOut | 3@0.203 | skill_to_cosmetic | - | - | 3@0.25,2@0.25 | Slider_Turn,TurnSpeed | bundle@1.4 |
| passive | Neural Networking 0x340005AC | none | - | - |  | - | - | - | - | - |

### Mecha Superman (0x4000063d, graph chr_mecha_superman_behavior.hkb, pack 0xA00001E8, 5 kit scripts in its hooks)

| slot | skill / script | ics raises (event@s) | state -> cosmetic tail | hooks code@s | leaves on | needs (external) | never raised | ics signals code@s | graph inputs | movement |
|---|---|---|---|---|---|---|---|---|---|---|
| basic | Basic Attack 0x340003ED | none | Critical_Attack; Basic_Attack | 3@0.240,6@0.050; 3@0.240,3@0.246,6@0.050 | basicattack_to_basicattack; basicattack_to_basicattack | - | - | 6@0.05,3@0.25,2@0.3 | Slider_Turn | - |
| Q | Drill Attack 0x340003F0 | Drill_Attack@0 | Drill_Attack -> Drill_Attack_Cosmetic onCosmeticEarlyOut | 3@0.100 | skill_to_cosmetic | - | - | 3@0.1,2@0.2 | Slider_Turn,TurnSpeed | - |
| W | Sunstone Eruption 0x340003EF | Sunstone_Eruption@0 | Sunstone_Erruption -> Sunstone_Erruption_Cosmetic onCosmeticEarlyOut | 3@0.100 | skill_to_cosmetic | - | - | 3@0.1,2@0.2 | Slider_Turn,TurnSpeed | - |
| E | Fissure 0x340003F1 | Fissure@0 | Fissure -> Fissure_Cosmetic onCosmeticEarlyOut | 3@0.100 | skill_to_cosmetic | - | - | 3@0.1,2@0.2 | Slider_Turn,TurnSpeed | - |
| R | Terraformer 0x340003F2 | Terraformer@0; Terraformer_Activate@0; AgentOfHope_Activate@0; AgentOfHope_Deactivate@0 | Terraformer | - | skill_to_locomotion | - | - | - | Slider_Propel,Slider_Turn,TurnSpeed | no stop |
| passive | Agent of Hope 0x340003E6 | none | - | - |  | - | - | - | - | - |

### Mecha Wonder Woman (0x40000483, graph chr_mecha_wonder_woman_behavior.hkb, pack 0xA0000157, 5 kit scripts in its hooks)

| slot | skill / script | ics raises (event@s) | state -> cosmetic tail | hooks code@s | leaves on | needs (external) | never raised | ics signals code@s | graph inputs | movement |
|---|---|---|---|---|---|---|---|---|---|---|
| basic | Basic Attack 0x340002CC | none | Critical_Attack; Basic_Attack | 5@0.240,6@0.050; 5@0.240,6@0.050 | basicattack_to_basicattack; basicattack_to_basicattack | - | - | 6@0.05,5@0.25,2@0.3 | Slider_Turn | - |
| Q | Glaive Storm 0x340002CB | MechaWonderWoman_GlaiveStorm@0 | GlaiveStorm -> GlaiveStorm_Cosmetic onCosmeticEarlyOut | 5@0.020 | skill_to_cosmetic | - | - | 5@0.05,2@0.15 | Slider_Turn,TurnSpeed | - |
| W | Afterburn 0x340002CA | MechaWonderWoman_Afterburn@0; MechaWonderWoman_Afterburn_End@0.15 | Afterburn; Locomotion | - | MechaWonderWoman_Afterburn_End; (none) | MechaWonderWoman_Afterburn_End; Emote_Dance,Emote_Joke,Emote_Laugh,Emote_Taunt,Fidget_A,Fidget_B,Fidget_C,Fidget_D | Emote_Dance,Emote_Joke,Emote_Laugh,Emote_Taunt,Fidget_A,Fidget_B,Fidget_C,Fidget_D | 5@0.3,3@0.3,2@0.45 | Slider_Propel,Slider_Turn,TurnSpeed,cond:ToggleFidget == 1 | no stop bundle@0.05,0.1,0.15,0.15 |
| E | Celerity 0x340002C9 | MechaWonderWoman_Celerity@0 | Celerity | - | skill_to_locomotion | - | - | - | Slider_Propel,Slider_Turn,TurnSpeed | no stop |
| R | Tempest 0x340002C8 | MechaWonderWoman_Tempest@0; Tempest_to_Locomotion@2.35 | Tempest; Locomotion | 3@0.200 | Tempest_to_Locomotion; (none) | Tempest_to_Locomotion; Emote_Dance,Emote_Joke,Emote_Laugh,Emote_Taunt,Fidget_A,Fidget_B,Fidget_C,Fidget_D | Emote_Dance,Emote_Joke,Emote_Laugh,Emote_Taunt,Fidget_A,Fidget_B,Fidget_C,Fidget_D | 3@0.25 | Slider_Propel,Slider_Turn,TurnSpeed,cond:ToggleFidget == 1 | - |
| passive | Implacable Judgement 0x340002C7 | none | - | - |  | - | - | - | - | - |

### Nightmare Batman (0x40000009, graph chr_vampire_batman_behavior.hkb, pack 0xA0000116, 4 kit scripts in its hooks)

| slot | skill / script | ics raises (event@s) | state -> cosmetic tail | hooks code@s | leaves on | needs (external) | never raised | ics signals code@s | graph inputs | movement |
|---|---|---|---|---|---|---|---|---|---|---|
| basic | Basic Attack 0x340000C8 | none | Standing_Critical_Attack; Standing_Basic_Attack; Batswarm_Empower | 3@0.240,6@0.050; 3@0.240,6@0.050; 3@0.130,6@0.050 | basicattack_to_basicattack; basicattack_to_basicattack; basicattack_to_basicattack | - | - | 5@0.3,3@0.3,2@0.45 | Slider_Turn | - |
| Q | Silver Batarang 0x340000C4 | none | Batarang -> Batman Batarang_Stage2 onCosmeticEarlyOut | 5@0.080 | skill_to_cosmetic | - | - | 5@0.1,2@0.45 | Slider_Turn | - |
| W | Bat Swarm 0x340000C5 | none | Batswarm -> Batman_Batswarm_Cosmetic onCosmeticEarlyOut | - | skill_to_cosmetic | fidgetwing | fidgetwing | - | Slider_Propel,Slider_Turn | no stop |
| E | Savagery 0x340000C9 | Vampire_Batman_SavageryStart@0 | - | - |  | - | - | - | - | no stop |
| R | Feral Embrace 0x340000C6 | Vampire_Batman_SavageryEnd@0.05 | hook only: Feral Embrace | - |  | - | - | 3@0.1,2@0.1 | - | no stop |
| passive | Eternal Hunger 0x340000C7 | none | - | - |  | - | - | - | - | - |

### Nightmare Catwoman (0x40000cea, graph chr_nightmare_catwoman_behavior.hkb, pack 0xA000036D, 5 kit scripts in its hooks)

| slot | skill / script | ics raises (event@s) | state -> cosmetic tail | hooks code@s | leaves on | needs (external) | never raised | ics signals code@s | graph inputs | movement |
|---|---|---|---|---|---|---|---|---|---|---|
| basic | Basic Attack 0x34000725 | Basic_Attack@0 | Basic_Melee_Large | 0@0.050,3@0.200 | basicattack_to_basicattack | - | - | 5@0.3,3@0.3,2@0.45 | Slider_Turn | - |
| Q | Rip & Tear 0x34000728 | Wildcard_QSkill@0; skill_to_locomotion@0.3 | Rip_&_Tear | 5@0.182 | skill_to_locomotion | Nightmare_Catwoman_Rip&Tear_Hit | Nightmare_Catwoman_Rip&Tear_Hit | 5@0.2 | Slider_Turn,TurnSpeed | skill_to_locomotion@0.3 |
| W | Soul Siphon 0x3400072A | Wildcard_WSkill@0 | Soul_Siphon | 3@0.203 | skill_to_locomotion | - | - | 3@0.25,2@0.45 | Slider_Turn,TurnSpeed | - |
| E | Scar the Land 0x34000726 | Wildcard_ESkill@0 | Scar_the_Land | 5@0.200 | skill_to_locomotion | - | - | 5@0.25,2@0.45 | Slider_Turn,TurnSpeed | - |
| R | Inevitability 0x34000729 | Wildcard_RSkill@0 | Inevitability | 3@0.203 | skill_to_locomotion | - | - | 3@0.25,2@0.45 | Slider_Turn,TurnSpeed | bundle@1 |
| passive | Mangle 0x34000727 | none | - | - |  | - | - | - | - | - |

### Nightmare Robin (0x4000091b, graph chr_nightmare_robin_behavior.hkb, pack 0xA000022E, 3 kit scripts in its hooks)

| slot | skill / script | ics raises (event@s) | state -> cosmetic tail | hooks code@s | leaves on | needs (external) | never raised | ics signals code@s | graph inputs | movement |
|---|---|---|---|---|---|---|---|---|---|---|
| basic | Basic Attack 0x340004B9 | none | Critical_Attack; Basic_Attack; Backstab; Basic_Attack_Bloodlust; Critical_Attack_Bloodlust | 3@0.240,6@0.050; 3@0.240,6@0.050; 3@0.130,6@0.050; 3@0.240,6@0.050; 3@0.240,6@0.050 | basicattack_to_basicattack; basicattack_to_basicattack; basicattack_to_basicattack; basicattack_to_basicattack; basicattack_to_basicattack | - | - | 5@0.3,3@0.3,2@0.45 | Slider_Turn | - |
| Q | Arcing Blades 0x340004B7 | NMR_Arcing_Blades@0 | Arcing_Blades -> Arcing_Blades_Cosmetic onCosmeticEarlyOut | 5@0.060 | skill_to_cosmetic | - | - | 5@0.1,2@0.4 | Slider_Turn,TurnSpeed | - |
| W | Impale 0x340004B6 | none | - | - |  | - | - | - | - | no stop |
| E | Unnatural Reflexes 0x340004B5 | Fidget_Abort@0; Emote_Abort@0 | Idling | - | CommitFidget | - | - | - | Slider_Propel | no stop bundle@0.05,0.1,0.15,0.2 |
| R | Feed the Beast 0x340004B4 | NMR_Feed_the_Beast@0.05 | Feed_the_Beast -> FeedtheBeast_End_Cosmetic onCosmeticEarlyOut | - | skill_to_cosmetic | NMR_FeedtheBeast_End | NMR_FeedtheBeast_End | 5@0.3,3@0.3,2@0.45 | Slider_Turn,TurnSpeed | no stop bundle@0.1,0.15,0.15 |
| passive | The Hunger 0x340004B8 | none | - | - |  | - | - | - | - | - |

### Nightmare Superman (0x400007c0, graph chr_nightmare_superman_behavior.hkb, pack 0xA00001FA, 5 kit scripts in its hooks)

| slot | skill / script | ics raises (event@s) | state -> cosmetic tail | hooks code@s | leaves on | needs (external) | never raised | ics signals code@s | graph inputs | movement |
|---|---|---|---|---|---|---|---|---|---|---|
| basic | Basic Attack 0x3400041F | none | Critical_Attack; Basic_Attack | 5@0.240,6@0.050; 5@0.240,6@0.050 | basicattack_to_basicattack; basicattack_to_basicattack | - | - | 6@0.05,5@0.25,2@0.3 | Slider_Turn | - |
| Q | Phantom Collector 0x3400041B | Start_PhantomCollector@0 | PhantomCollector -> PhantomCollector_Cosmetic onCosmeticEarlyOut | 3@0.060 | skill_to_cosmetic | - | - | 3@0.1,2@0.2 | Slider_Turn,TurnSpeed | - |
| W | Vortex 0x3400041A | Start_Vortex@0 | Vortex -> Vortex_Cosmetic onCosmeticEarlyOut | 3@0.050 | skill_to_cosmetic | - | - | 3@0.05,2@0.2 | Slider_Turn,TurnSpeed | bundle@1 |
| E | Siphon/Infuse 0x3400041D | Start_Siphon_Infuse@0 | Siphon_Infuse -> Siphon_Infuse_Cosmetic onCosmeticEarlyOut | 5@0.100 | skill_to_cosmetic | - | - | 5@0.1,2@0.2 | Slider_Turn,TurnSpeed | - |
| R | Condemn 0x3400041E | Start_Banish@0 | Banish -> Banish_Cosmetic onCosmeticEarlyOut | 3@0.120 | skill_to_cosmetic | - | - | 3@0.15,2@0.25 | Slider_Turn,TurnSpeed | - |
| passive | Possession 0x3400041C | none | - | - |  | - | - | - | - | - |

### Nightwing (0x40000dee, graph chr_nightwing_behavior.hkb, pack 0xA000039A, 4 kit scripts in its hooks)

| slot | skill / script | ics raises (event@s) | state -> cosmetic tail | hooks code@s | leaves on | needs (external) | never raised | ics signals code@s | graph inputs | movement |
|---|---|---|---|---|---|---|---|---|---|---|
| basic | Basic Attack 0x34000799 | none | Crit_Melee_Large; Basic_Melee_Large; Empower_Melee | 3@0.200,3@0.240,6@0.050; 3@0.240,6@0.050; 3@0.139,3@0.142,3@0.160,3@0.161,3@0.240,6@0.050 | basicattack_to_basicattack; basicattack_to_basicattack; basicattack_to_basicattack | - | - | 5@0.3,3@0.3,2@0.45 | Slider_Turn | - |
| Q | Eskrima 0x34000795 | none | - | - |  | - | - | - | - | no stop |
| W | Thunderbolt 0x34000793 | Wildcard_WSkill@0; Skill_Dash_End@0.3; skill_to_locomotion@0.3 | Thunderbolt; Dash_W_End | - | skill_to_locomotion; (none) | Skill_Dash_End | - | 5@0.3,3@0.3,2@0.45 | Slider_Turn,TurnSpeed | no stop skill_to_locomotion@0.3 bundle@0.05,0.1,0.15,0.2 |
| E | Rolling Thunder 0x34000797 | Wildcard_ESkill@0; skill_to_locomotion@0.45 | Rolling_Thunder -> StandardSkill_E_Cosm onCosmeticEarlyOut | 3@0.203 | skill_to_cosmetic | - | - | 3@0.25,2@0.45 | Slider_Turn,TurnSpeed | skill_to_locomotion@0.45 cuts tail 0.05s after it began |
| R | Let's Ride 0x34000794 | Wildcard_RSkill@0; Wildcard_RSkill_Alt@0 | Lets_Ride_Buff; Lets_Ride -> StandardSkill_R_Cosm onCosmeticEarlyOut | 3@2.902; 3@0.217 | skill_to_locomotion; skill_to_cosmetic | - | - | - | Slider_Propel,Slider_Turn,TurnSpeed | no stop |
| passive | Static Burn 0x34000796 | none | - | - |  | - | - | - | - | - |

### Poison Ivy (0x40000145, graph chr_poison_ivy_behavior.hkb, pack 0xA0000111, 5 kit scripts in its hooks)

| slot | skill / script | ics raises (event@s) | state -> cosmetic tail | hooks code@s | leaves on | needs (external) | never raised | ics signals code@s | graph inputs | movement |
|---|---|---|---|---|---|---|---|---|---|---|
| basic | Basic Attack 0x3400009D | none | Standing Critical Attack; Standing Basic Attack | 5@0.282,6@0.059; 5@0.282,6@0.059 | basicattack_to_basicattack; basicattack_to_basicattack | - | - | 6@0.1,5@0.3,2@0.3 | Slider_Turn,TurnSpeed | - |
| Q | Root Strike 0x34000095 | none | Root Strike -> Root Strike_Cosmetic onCosmeticEarlyOut | 5@0.125 | skill_to_cosmetic | - | - | 5@0.15,2@0.25 | Slider_Turn,TurnSpeed | - |
| W | Blow Kiss 0x34000099 | none | Blow Kiss -> Blow Kiss_Cosmetic onCosmeticEarlyOut | 5@0.200 | skill_to_cosmetic | - | - | 5@0.25,2@0.25 | Slider_Turn,TurnSpeed | - |
| E | Thorn Shield 0x34000158 | none | Rampant Growth; Thorn Shield | 2@0.300,3@0.241; 2@0.200,3@0.010 | state_to_locomotion; state_to_locomotion | - | - | 5@0.3,3@0.3,2@0.45 | Slider_Propel,Slider_Turn,TurnSpeed | no stop |
| R | Deadly Flora 0x34000097 | none | Deadly Flora -> Deadly Flora_Cosmetic onCosmeticEarlyOut | 3@0.125 | skill_to_cosmetic | - | - | 3@0.15,2@0.25 | Slider_Turn,TurnSpeed | no stop |
| passive | Healthy Glow 0x34000098 | none | - | - |  | - | - | - | - | - |

### Raven (0x40000c4f, graph chr_raven_behavior.hkb, pack 0xA0000332, 5 kit scripts in its hooks)

| slot | skill / script | ics raises (event@s) | state -> cosmetic tail | hooks code@s | leaves on | needs (external) | never raised | ics signals code@s | graph inputs | movement |
|---|---|---|---|---|---|---|---|---|---|---|
| basic | Basic Attack 0x34000681 | none | Basic_Attack_Right; Crit_Ranged_Small; Basic_Attack_Left | 5@0.240,6@0.050; 5@0.240,6@0.050; 5@0.240,6@0.050 | basicattack_to_basicattack; basicattack_to_basicattack; basicattack_to_basicattack | - | - | 6@0.05,5@0.25,2@0.3 | Slider_Turn | - |
| Q | Gloom 0x3400067F | Wildcard_QSkill@0 | Gloom | 5@0.200 | skill_to_locomotion | - | - | 5@0.25,2@0.45 | Slider_Propel,Slider_Turn,TurnSpeed | no stop |
| W | Empathic Link 0x3400067E | Wildcard_WSkill@0 | Empathic Link | 3@0.203 | skill_to_locomotion | - | - | 3@0.25,2@0.45 | Slider_Propel,Slider_Turn,TurnSpeed | no stop |
| E | Isolation 0x3400067D | Wildcard_ESkill@0 | Isolation | 5@0.200 | skill_to_locomotion | - | - | 5@0.25,2@0.45 | Slider_Turn,TurnSpeed | - |
| R | Astral Projection 0x3400067C | Wildcard_RSkill@0 | Astral Projection | - | skill_to_locomotion | Skill_Dash_End | Skill_Dash_End | 5@0.3,3@0.3,2@0.45 | Slider_Turn,TurnSpeed | - |
| passive | Blessing of Darkness 0x34000680 | none | - | - |  | - | - | - | - | - |

### Robin (0x4000052d, graph chr_robin_behavior.hkb, pack 0xA0000176, 4 kit scripts in its hooks)

| slot | skill / script | ics raises (event@s) | state -> cosmetic tail | hooks code@s | leaves on | needs (external) | never raised | ics signals code@s | graph inputs | movement |
|---|---|---|---|---|---|---|---|---|---|---|
| basic | Basic Attack 0x3400030E | none | Critical_Attack; Basic_Attack; Critical_Attack_BoMaster; Basic_Attack_BoMaster; Basic_Attack_Punch | 3@0.240,6@0.050; 3@0.240,6@0.050; 3@0.240,6@0.050; 3@0.240,6@0.050; 3@0.200,6@0.050 | basicattack_to_basicattack; basicattack_to_basicattack; basicattack_to_basicattack; basicattack_to_basicattack; basicattack_to_basicattack | - | - | 5@0.3,3@0.3,2@0.45 | Slider_Turn | - |
| Q | Vault Kick 0x3400030D | Robin_VaultKick_Start@0; Robin_VaultKick_End@0.15; Robin_VaultKick_End_Loc@0.55 | Vault Kick; chr robin skill vault kick end.hkx00; Locomotion | - | Robin_VaultKick_End_Loc; (none); (none) | Robin_VaultKick_End,Robin_VaultKick_End_Loc; Emote_Dance,Emote_Joke,Emote_Laugh,Emote_Taunt,Fidget_A,Fidget_B,Fidget_C,Fidget_D | Emote_Dance,Emote_Joke,Emote_Laugh,Emote_Taunt,Fidget_A,Fidget_B,Fidget_C,Fidget_D | 5@0.3,3@0.3,2@0.45 | Slider_Propel,Slider_Turn,TurnSpeed,cond:ToggleFidget == 1 | bundle@0.05,0.1,0.15,0.15 |
| W | Bo Master 0x3400030C | Robin_BoMaster_Start@0 | - | - |  | - | - | - | - | no stop |
| E | Dynamic Duo 0x3400030B | Robin_DynamicDuo_Start@0; Robin_BoMaster_End@1.05 | Dynamic Duo -> Dynamic Duo_Cosmetic  | - | skill_to_cosmetic | - | - | 5@0.3,3@0.3,2@0.45 | Slider_Propel,Slider_Turn | no stop |
| R | Emergent Leader 0x3400030A | Robin_EmergentLeader_Start@0 | Emergent Leader_Cosmetic -> Emergent Leader Cosmetic onCosmeticEarlyOut | 3@0.120 | skill_to_cosmetic | - | - | 3@0.15,2@0.2 | Slider_Turn,TurnSpeed | no stop |
| passive | This Guy! 0x34000309 | none | - | - |  | - | - | - | - | - |

### Shazam (0x40000358, graph chr_shazam_behavior.hkb, pack 0xA0000120, 5 kit scripts in its hooks)

| slot | skill / script | ics raises (event@s) | state -> cosmetic tail | hooks code@s | leaves on | needs (external) | never raised | ics signals code@s | graph inputs | movement |
|---|---|---|---|---|---|---|---|---|---|---|
| basic | Basic Attack 0x340001F6 | none | Critical_Attack; Basic_Attack | 3@0.200,3@0.240,6@0.050; 3@0.240,6@0.050 | basicattack_to_basicattack; basicattack_to_basicattack | - | - | 5@0.3,3@0.3,2@0.45 | Slider_Turn | - |
| Q | Mystic Power 0x34000756 | SpeedOfMercury_Cast@0 | SpeedOfMercury_Cast -> SpeedOfMercury_Cast_Cosmetic onCosmeticEarlyOut | 5@0.060 | skill_to_cosmetic | - | - | 5@0.1,2@0.2 | Slider_Turn,TurnSpeed | - |
| W | Mystic Defense 0x34000757 | Mystic_Defense_Start@0 | Mystic_Defense | - | (none) | - | - | - | Slider_Propel,Slider_Turn | no stop |
| E | Lightning Field 0x340001F5 | Lightning_Field_Start@0 | Lightning_Field | - | (none) | - | - | - | Slider_Propel,Slider_Turn | no stop |
| R | SHAZAM! 0x340001F8 | Ultimate_Shazam_Start@0; Ultimate_Shazam_End@0.15 | Ultimate_Shazam; chr shazam skill ultimate shazam end.hkx | - | (none); (none) | Ultimate_Shazam_End | - | 5@0.3,3@0.3,2@0.45 | - | no stop bundle@0.05,0.1,0.15,0.15 |
| passive | Power of Zeus 0x340001FD | none | - | - |  | - | - | - | - | - |

### Sinestro (0x40000805, graph chr_sinestro_behavior.hkb, pack 0xA000020F, 5 kit scripts in its hooks)

| slot | skill / script | ics raises (event@s) | state -> cosmetic tail | hooks code@s | leaves on | needs (external) | never raised | ics signals code@s | graph inputs | movement |
|---|---|---|---|---|---|---|---|---|---|---|
| basic | Basic Attack 0x3400046F | none | Critical_Attack; Basic_Attack_Left; Basic_Attack_Right | 5@0.240,6@0.050; 5@0.240,6@0.050; 5@0.240,6@0.050 | basicattack_to_basicattack; basicattack_to_basicattack; basicattack_to_basicattack | - | - | 6@0.05,5@0.25,2@0.3 | Slider_Turn | - |
| Q | Saw-blade 0x3400046C | Sinesto_SawBlade@0 | SawBlade -> SawBlade_Cosmetic onCosmeticEarlyOut | 5@0.050 | skill_to_cosmetic | - | - | 5@0.05,2@0.2 | Slider_Turn,TurnSpeed | - |
| W | Dread Scythe 0x3400046A | Sinestro_InstillFear@0 | InstillFear -> InstillFear_Cosmetic onCosmeticEarlyOut | 3@0.075,5@0.180 | skill_to_cosmetic | - | - | 3@0.1,5@0.2,2@0.25 | Slider_Turn,TurnSpeed | - |
| E | Cull the Weak 0x3400046E | Sinestro_CullTheWeak@0; Sinestro_CulltheWeak_End@0.1 | CullTheWeak -> CulltheWeak_End_Cosmetic ; CulltheWeak_End | - | skill_to_cosmetic; (none) | Sinestro_CulltheWeak_End | - | 5@0.3,3@0.3,2@0.45 | Slider_Propel,Slider_Turn,TurnSpeed | no stop bundle@0.05,0.1,0.1 |
| R | Fear Incarnate 0x3400046B | Sinestro_FearIncarnate@0 | FearIncarnate -> FearIncarnate_Cosmetic onCosmeticEarlyOut | 5@0.070 | skill_to_cosmetic | - | - | 5@0.1,2@0.2 | Slider_Turn,TurnSpeed | bundle@1 |
| passive | Yellow Impurity 0x3400046D | none | - | - |  | - | - | - | - | - |

### Solomon Grundy (0x40000c44, graph chr_solomon_grundy_behavior.hkb, pack 0xA0000328, 5 kit scripts in its hooks)

| slot | skill / script | ics raises (event@s) | state -> cosmetic tail | hooks code@s | leaves on | needs (external) | never raised | ics signals code@s | graph inputs | movement |
|---|---|---|---|---|---|---|---|---|---|---|
| basic | Basic Attack 0x3400066C | none | Crit_Melee_Large; Basic_Melee_Large | 3@0.240,6@0.050; 3@0.240,6@0.050 | basicattack_to_basicattack; basicattack_to_basicattack | - | - | 6@0.05,3@0.25,2@0.3 | Slider_Turn | - |
| Q | Clobber 0x34000666 | Wildcard_QSkill@0; Wildcard_QSkill_End@0.2 | Clobber; Locomotion | - | Wildcard_QSkill_End; (none) | Wildcard_QSkill_End; Emote_Dance,Emote_Joke,Emote_Laugh,Emote_Taunt,Fidget_A,Fidget_B,Fidget_C,Fidget_D | Emote_Dance,Emote_Joke,Emote_Laugh,Emote_Taunt,Fidget_A,Fidget_B,Fidget_C,Fidget_D | 5@0.05,2@0.25 | Slider_Propel,Slider_Turn,TurnSpeed,cond:ToggleFidget == 1 | bundle@0.05,0.1,0.15,0.2 |
| W | Crush 0x34000665 | Wildcard_WSkill@0 | Slam -> Slam_Cosmetic onCosmeticEarlyOut | 3@0.125 | skill_to_cosmetic | - | - | 5@0.3,3@0.3,2@0.45 | Slider_Turn,TurnSpeed | no stop |
| E | The March 0x34000664 | ActivateMarch@0 | hook only: TheMarch_Grab | - |  | - | - | - | - | no stop |
| R | Buried on Sunday 0x34000663 | Wildcard_RSkill@0; DeactivateMarch@0.1 | Buried_On_Sunday | - | skill_to_locomotion | - | - | - | Slider_Propel,Slider_Turn,TurnSpeed | no stop |
| passive | Born on a Monday 0x34000662 | none | - | - |  | - | - | - | - | - |

### Star Sapphire (0x400005d1, graph chr_star_sapphire_behavior.hkb, pack 0xA00001D1, 5 kit scripts in its hooks)

| slot | skill / script | ics raises (event@s) | state -> cosmetic tail | hooks code@s | leaves on | needs (external) | never raised | ics signals code@s | graph inputs | movement |
|---|---|---|---|---|---|---|---|---|---|---|
| basic | Basic Attack 0x34000390 | none | Critical_Attack; Basic_Attack | 5@0.240,6@0.050; 5@0.240,6@0.050 | basicattack_to_basicattack; basicattack_to_basicattack | - | - | 6@0.05,5@0.25,2@0.3 | Slider_Turn | - |
| Q | Crystal Bomb 0x3400038D | StarSapphire_CrystalBomb@0 | Crystal Bomb -> Crystal Bomb_Cosmetic onCosmeticEarlyOut | 3@0.050 | skill_to_cosmetic | - | - | 3@0.05,2@0.2 | Slider_Turn,TurnSpeed | - |
| W | Violet Harvest 0x3400038A | StarSapphire_VioletHarvest@0 | Violet Harvest -> Violet Harvest Cosmetic onCosmeticEarlyOut | - | skill_to_cosmetic | - | - | - | Slider_Propel | no stop bundle@1 |
| E | Bonds of Love 0x3400038E | StarSapphire_BondsOfLove@0 | Bonds of Love -> Bonds of Love Cosmetic onCosmeticEarlyOut | 5@0.100 | skill_to_cosmetic | - | - | 5@0.1,2@0.25 | Slider_Turn,TurnSpeed | - |
| R | Manifest 0x3400038B | StarSapphire_Manifestation@0 | Manifestation -> Manifestation_Cosmetic onCosmeticEarlyOut | - | skill_to_cosmetic | - | - | - | Slider_Propel | no stop |
| passive | Glimpse of the Predato 0x3400038C | none | - | - |  | - | - | - | - | - |

### Stargirl (0x40000aea, graph chr_stargirl_behavior.hkb, pack 0xA00002B1, 5 kit scripts in its hooks)

| slot | skill / script | ics raises (event@s) | state -> cosmetic tail | hooks code@s | leaves on | needs (external) | never raised | ics signals code@s | graph inputs | movement |
|---|---|---|---|---|---|---|---|---|---|---|
| basic | Basic Attack 0x3400056A | none | Crit_Ranged_Small; Basic_Ranged_Small; Melee | 5@0.240,6@0.050; 5@0.240,6@0.050,6@0.200; 3@0.240,6@0.050 | basicattack_to_basicattack; basicattack_to_basicattack; basicattack_to_basicattack | - | - | 5@0.3,3@0.3,2@0.45 | Slider_Turn | - |
| Q | Cosmic Blast 0x3400056E | Wildcard_QSkill@0 | Cosmic_Blast -> Cosmic_Blast_Cosmetic onCosmeticEarlyOut | 5@0.570 | skill_to_cosmetic | - | - | 5@0.6,2@0.65 | Slider_Turn,TurnSpeed | - |
| W | Shooting Stars 0x3400056D | Wildcard_WSkill@0 | Shooting_Stars -> Shooting_Stars_Cosmetic onCosmeticEarlyOut | 3@0.050 | skill_to_cosmetic | - | - | 3@0.05,2@0.2 | Slider_Turn,TurnSpeed | - |
| E | Gravity Well 0x3400056C | Wildcard_ESkill@0 | Gravity_Well -> Gravity_Well_Cosmetic onCosmeticEarlyOut | 5@0.060 | skill_to_cosmetic | - | - | 5@0.1,2@0.2 | Slider_Turn,TurnSpeed | - |
| R | Energy Conversion 0x3400056B | Wildcard_RSkill@0 | energy_conversion | - | skill_to_locomotion | skill_to_locomotion | skill_to_locomotion | 5@0.3,3@0.3,2@0.45 | Slider_Propel,Slider_Turn,TurnSpeed | no stop |
| passive | Family Heirlooms 0x3400056F | none | - | - |  | - | - | - | - | - |

### Starro (0x40000a96, graph chr_starro_behavior.hkb, pack 0xA000026E, 3 kit scripts in its hooks)

| slot | skill / script | ics raises (event@s) | state -> cosmetic tail | hooks code@s | leaves on | needs (external) | never raised | ics signals code@s | graph inputs | movement |
|---|---|---|---|---|---|---|---|---|---|---|
| basic | Basic Attack 0x3400052B | none | Critical_Attack; Basic_Attack_Left; Basic_Attack_Right | 5@0.240,6@0.050; 5@0.240,6@0.050; 5@0.240,6@0.050 | basicattack_to_basicattack; basicattack_to_basicattack; basicattack_to_basicattack | - | - | 6@0.05,5@0.25,2@0.3 | Slider_Turn | - |
| Q | Star Shot 0x34000530 | Wildcard_QSkill@0 | Star_Shot -> Star_Shot_Cosmetic onCosmeticEarlyOut | 5@0.100 | skill_to_cosmetic | - | - | 5@0.1,2@0.2 | Slider_Turn,TurnSpeed | - |
| W | Parasite 0x34000531 | Wildcard_WSkill@0 | Parasite -> Parasite_Cosmetic onCosmeticEarlyOut | 5@0.060 | skill_to_cosmetic | - | - | 5@0.1,2@0.2 | Slider_Turn,TurnSpeed | - |
| E | Telepathic Warlord 0x3400052E | none | - | - |  | - | - | - | - | no stop |
| R | Mind Control 0x3400052D | none | - | - |  | - | - | 5@0.3,3@0.3,2@0.45 | - | no stop |
| passive | The Conqueror Comes 0x34000532 | none | - | - |  | - | - | - | - | - |

### Supergirl (0x40000810, graph chr_supergirl_behavior.hkb, pack 0xA0000221, 5 kit scripts in its hooks)

| slot | skill / script | ics raises (event@s) | state -> cosmetic tail | hooks code@s | leaves on | needs (external) | never raised | ics signals code@s | graph inputs | movement |
|---|---|---|---|---|---|---|---|---|---|---|
| basic | Basic Attack 0x34000481 | none | Critical_Attack; Basic_Attack; Worldbreaker | 3@0.240,6@0.050; 3@0.240,6@0.050; 3@0.130,6@0.010 | basicattack_to_basicattack; basicattack_to_basicattack; basicattack_to_basicattack | - | - | 5@0.3,3@0.3,2@0.45 | Slider_Turn | - |
| Q | Worldbreaker 0x34000483 | none | Ultimate -> Ultimate_End_Cosmetic onCosmeticEarlyOut | - | skill_to_cosmetic,skill_to_locomotion | Supergirl_Comet_End,Supergirl_Comet_Grab,skill_to_locomotion | Supergirl_Comet_End,Supergirl_Comet_Grab,skill_to_locomotion | - | - | no stop |
| W | Bounding Strike 0x3400047F | Wildcard_WSkill@0; Skill_Dash_End@0.15 | BoundingBlow -> Dash End_Cosmetic onCosmeticEarlyOut; Dash End | 3@0.010; 3@0.010 | skill_to_cosmetic,skill_to_locomotion; (none) | Skill_Dash_End,skill_to_locomotion | skill_to_locomotion | 3@0.05,2@0.1 | Slider_Turn,TurnSpeed | no stop bundle@0.05,0.1,0.15,0.15 |
| E | Determination 0x34000482 | Wildcard_ESkill@0 | SolarFurnace -> SolarFurnace_Cosmetic onCosmeticEarlyOut | - | skill_to_cosmetic | - | - | - | Slider_Propel,Slider_Turn,TurnSpeed | no stop |
| R | Comet 0x34000480 | none | - | - |  | - | - | 5@0.3,3@0.3,2@0.45 | - | no stop |
| passive | Solar Furnace 0x3400047E | none | SolarFurnace -> SolarFurnace_Cosmetic onCosmeticEarlyOut | - | skill_to_cosmetic | - | - | - | Slider_Propel,Slider_Turn,TurnSpeed | - |

### Superman (0x4000002b, graph chr_superman_skin_flight_behavior.hkb, pack 0xA0000075, 4 kit scripts in its hooks)

| slot | skill / script | ics raises (event@s) | state -> cosmetic tail | hooks code@s | leaves on | needs (external) | never raised | ics signals code@s | graph inputs | movement |
|---|---|---|---|---|---|---|---|---|---|---|
| basic | Basic Attack 0x3400000C | none | Critical_Attack; Basic_Attack; Mighty_Blow | 3@0.240,6@0.050; 3@0.240,6@0.050; 3@0.100,6@-0.090 | basicattack_to_basicattack; basicattack_to_basicattack; basicattack_to_basicattack | - | - | 5@0.3,3@0.3,2@0.45 | Attribute_AttackSpeed,Slider_Turn,TurnSpeed | - |
| Q | Kryptonian Might 0x340003D7 | none | - | - |  | - | - | - | - | no stop |
| W | Frost Breath 0x340000F7 | Superman_FrostBreath@0; ManofSteel_Deactivate@0.35 | FrostBreath -> FrostBreath_Cosmetic onCosmeticEarlyOut | 3@0.100 | skill_to_cosmetic | - | - | 3@0.1,2@0.25 | Slider_Turn,TurnSpeed | bundle@1 |
| E | Heat Vision 0x340003D6 | Superman_HeatVision_Initial@0; skill_to_locomotion@0.1; ManofSteel_Activate@0.1 | HeatVision_Initial | 3@0.060 | skill_to_locomotion | skill_to_locomotion | - | 3@0.1 | - | skill_to_locomotion@0.1 ends the state (authored end) |
| R | Speeding Bullet 0x340003D5 | none | SpeedingBullet -> SpeedingBullet_End_Cosmetic onCosmeticEarlyOut | 3@0.010 | skill_to_cosmetic | SpeedingBullet_Loop_to_End,SpeedingBullet_Start_to_Loop,SpeedingBullet_Windup_to_Start | SpeedingBullet_Loop_to_End,SpeedingBullet_Start_to_Loop,SpeedingBullet_Windup_to_Start | 3@0.05,2@0.15 | Slider_Turn,TurnSpeed | no stop |
| passive | Man of Steel 0x340000F8 | none | - | - |  | - | - | - | - | - |

### Swamp Thing (0x40000b16, graph chr_swamp_thing_behavior.hkb, pack 0xA00002CF, 5 kit scripts in its hooks)

| slot | skill / script | ics raises (event@s) | state -> cosmetic tail | hooks code@s | leaves on | needs (external) | never raised | ics signals code@s | graph inputs | movement |
|---|---|---|---|---|---|---|---|---|---|---|
| basic | Basic Attack 0x3400057F | none | Basic_Melee_Large; Crit_Melee_Small; WarriorKing_Basic_Melee_Large; WarriorKing_Crit_Melee_Small | 3@0.240,6@0.050; 3@0.240,6@0.050; 3@0.240,6@0.050; 3@0.240,6@0.050 | basicattack_to_basicattack; basicattack_to_basicattack; basicattack_to_basicattack; basicattack_to_basicattack | - | - | 6@0.05,3@0.25,2@0.3 | Slider_Turn | - |
| Q | Vine Leash 0x34000582 | SwampThing_Leash@0 | Leash -> Leash_Cosmetic onCosmeticEarlyOut | 5@0.100 | skill_to_cosmetic | - | - | 5@0.1,2@0.25 | Slider_Propel,Slider_Turn,TurnSpeed | - |
| W | Husk 0x34000581 | SwampThing_Husk@0 | Husk_Cast -> Husk_Cast_Cosmetic onCosmeticEarlyOut | 5@0.100 | skill_to_cosmetic | - | - | 5@0.1,2@0.2 | Slider_Turn,TurnSpeed | bundle@1 |
| E | Earth Strike 0x34000584 | SwampThing_Earth_Strike@0 | Earth_Strike -> Earth_Strike_Cosmetic onCosmeticEarlyOut | 5@0.030 | skill_to_cosmetic | - | - | 5@0.05,2@0.15 | Slider_Turn,TurnSpeed | - |
| R | Warrior King 0x34000580 | SwampThing_WarriorKing@0; WarriorKing_Activate@0; Emote_Abort@0 | Warrior_King; Idling | - | skill_to_locomotion; CommitFidget | - | - | - | Slider_Propel,Slider_Turn,TurnSpeed | no stop |
| passive | Bio-regenerative Formu 0x34000583 | none | - | - |  | - | - | - | - | - |

### The Joker (0x40000213, graph chr_joker_behavior.hkb, pack 0xA00000B4, 5 kit scripts in its hooks)

| slot | skill / script | ics raises (event@s) | state -> cosmetic tail | hooks code@s | leaves on | needs (external) | never raised | ics signals code@s | graph inputs | movement |
|---|---|---|---|---|---|---|---|---|---|---|
| basic | Basic Attack 0x3400011C | none | Standing Critical Attack; Standing_Basic_Attack | 5@0.282,6@0.059; 5@0.240,5@0.282,6@0.050,6@0.059 | basicattack_to_basicattack; basicattack_to_basicattack | - | - | 5@0.3,3@0.3,2@0.45 | Slider_Turn,TurnSpeed | - |
| Q | Mr. Punchy 0x3400010A | none | MrPunchy -> MrPunchy_Cosmetic onCosmeticEarlyOut | 5@0.200 | skill_to_cosmetic | - | - | 5@0.25,2@0.25 | Slider_Turn,TurnSpeed | - |
| W | Surprise! 0x34000114 | none | Surprise -> Surprise_Cosmetic onCosmeticEarlyOut | 5@0.120 | skill_to_cosmetic | - | - | 5@0.15,2@0.2 | Slider_Turn,TurnSpeed | - |
| E | Vanish 0x34000111 | Joker_Vanish@0 | Vanish -> Vanish_Cosmetic onCosmeticEarlyOut | 3@0.040 | skill_to_cosmetic | - | - | 3@0.05,2@0.1 | Slider_Turn,TurnSpeed | no stop bundle@0.05 |
| R | Last Laugh 0x3400011B | none | LastLaugh -> LastLaugh_Cosmetic onCosmeticEarlyOut | 5@0.010 | skill_to_cosmetic | - | - | 5@0.05,2@0.25 | Slider_Turn,TurnSpeed | - |
| passive | Sadist 0x34000110 | none | - | - |  | - | - | - | - | - |

### Wonder Woman (0x40000260, graph chr_wonder_woman_behavior.hkb, pack 0xA000011E, 5 kit scripts in its hooks)

| slot | skill / script | ics raises (event@s) | state -> cosmetic tail | hooks code@s | leaves on | needs (external) | never raised | ics signals code@s | graph inputs | movement |
|---|---|---|---|---|---|---|---|---|---|---|
| basic | Basic Attack 0x3400017E | none | Standing_Critical_Attack; Standing_Basic_Attack | 3@0.240,6@0.050; 3@0.240,6@0.050 | basicattack_to_basicattack; basicattack_to_basicattack | - | - | 6@0.05,3@0.25,2@0.3 | Slider_Turn,TurnSpeed | - |
| Q | Lasso Grab 0x34000185 | none | LassoGrab -> LassoGrab_Hit_Cosmetic onCosmeticEarlyOut | 5@0.128 | skill_to_cosmetic | WonderWoman_LassoGrab_Dash,WonderWoman_LassoGrab_Hit | WonderWoman_LassoGrab_Dash,WonderWoman_LassoGrab_Hit | 5@0.15,2@0.15 | Slider_Propel,Slider_Turn,TurnSpeed | - |
| W | Protection 0x34000192 | none | Protection_Self; Protection_Other -> Protection_Other_End_Cosmetic onCosmeticEarlyOut | - | skill_to_locomotion; skill_to_cosmetic | WonderWoman_Protection_Other_Teleport | WonderWoman_Protection_Other_Teleport | 5@0.3,3@0.3,2@0.45 | Slider_Propel,Slider_Turn,TurnSpeed | no stop bundle@1 |
| E | Amazonian Prowess 0x3400018C | WonderWoman_AmazonianProwess_Start@0 | Amazonian_Prowess -> Amazonian_Prowess_Cosmetic onCosmeticEarlyOut | 3@0.080 | skill_to_cosmetic | - | - | 3@0.1,2@0.2 | Slider_Propel,Slider_Turn,TurnSpeed | no stop |
| R | Blocking Bracers 0x3400017D | WonderWoman_BlockingBracers@0; WonderWoman_BlockingBracers_Interrupt@0 | BlockingBracers -> BlockingBracers_End_Cosmetic onCosmeticEarlyOut; Locomotion | 3@0.210 | WonderWoman_BlockingBracers_Interrupt,skill_to_cosmetic; (none) | CbtState_GetHit,WonderWoman_BlockingBracers_End,WonderWoman_BlockingBracers_Interrupt; Emote_Dance,Emote_Joke,Emote_Laugh,Emote_Taunt,Fidget_A,Fidget_B,Fidget_C,Fidget_D | CbtState_GetHit,WonderWoman_BlockingBracers_End; Emote_Dance,Emote_Joke,Emote_Laugh,Emote_Taunt,Fidget_A,Fidget_B,Fidget_C,Fidget_D | - | Slider_Propel,Slider_Turn,TurnSpeed,cond:ToggleFidget == 1 | no stop |
| passive | Child of Olympus 0x34000189 | none | - | - |  | - | - | - | - | - |

### Zatanna (0x4000015b, graph chr_zatanna_behavior.hkb, pack 0xA0000113, 5 kit scripts in its hooks)

| slot | skill / script | ics raises (event@s) | state -> cosmetic tail | hooks code@s | leaves on | needs (external) | never raised | ics signals code@s | graph inputs | movement |
|---|---|---|---|---|---|---|---|---|---|---|
| basic | Basic Attack 0x340000ED | none | Standing_Critical_Attack; Standing_Basic_Attack | 5@0.240,6@0.050; 5@0.240,6@0.050 | basicattack_to_basicattack; basicattack_to_basicattack | - | - | 6@0.05,5@0.25,2@0.3 | Slider_Turn | - |
| Q | Skewer 0x340000E9 | none | Skewer -> Zatanna_Skewer_Stage2 onCosmeticEarlyOut | 3@0.010 | skill_to_cosmetic | - | - | 3@0.05,2@0.2 | Slider_Turn | - |
| W | Dash / Dazzle 0x340000EC | none | DashDazzle -> DashDazzle_Cosmetic  | 3@0.010 | skill_to_cosmetic | - | - | 3@0.05,2@0.15 | Slider_Propel,Slider_Turn | no stop bundle@1 |
| E | Protect / Punish 0x340000EB | none | ProtectPunish -> ProtectPunish_Cosmetic onCosmeticEarlyOut | 5@0.120 | skill_to_cosmetic | - | - | 5@0.15 | Slider_Turn | - |
| R | Be a Rabbit 0x340000EA | none | BeARabbit -> BeARabbit_Cosmetic onCosmeticEarlyOut | - | skill_to_cosmetic | - | - | 5@0.3,3@0.3,2@0.45 | Slider_Turn | no stop |
| passive | Stage Presence 0x34000107 | none | - | - |  | - | - | - | - | - |

### Zod (0x40000d29, graph chr_zod_behavior.hkb, pack 0xA0000378, 4 kit scripts in its hooks)

| slot | skill / script | ics raises (event@s) | state -> cosmetic tail | hooks code@s | leaves on | needs (external) | never raised | ics signals code@s | graph inputs | movement |
|---|---|---|---|---|---|---|---|---|---|---|
| basic | Basic Attack 0x3400074D | none | Crit_Melee_Large; Basic_Melee_Large; Empower_Melee; Basic_Melee_Large_Rush; Empower_Melee_Rush; Crit_Melee_Large_Rush | 3@0.240,6@0.050; 3@0.240,6@0.050; 3@0.240,6@0.160; 3@0.060,3@0.140; 3@0.060; 3@0.190 | basicattack_to_basicattack; basicattack_to_basicattack; basicattack_to_basicattack; basicattack_to_basicattack; basicattack_to_basicattack; basicattack_to_basicattack | Zod_Rush_Loop_To_End; Zod_Rush_Loop_To_End; Zod_Rush_Loop_To_End | Zod_Rush_Loop_To_End; Zod_Rush_Loop_To_End; Zod_Rush_Loop_To_End | 5@0.3,3@0.3,2@0.45 | Slider_Turn | - |
| Q | Shield Breaker 0x34000749 | none | - | - |  | - | - | - | - | no stop |
| W | Relentless 0x3400074A | Wildcard_WSkill@0 | Relentless -> Relentless_Cosmetic onCosmeticEarlyOut | - | skill_to_cosmetic | - | - | - | Slider_Propel,Slider_Turn,TurnSpeed | no stop bundle@1 |
| E | Solar Surge 0x34000748 | none | Solar_Surge -> Solar_Surge_Cosm onCosmeticEarlyOut | 3@0.100 | skill_to_cosmetic | - | - | - | Slider_Turn,TurnSpeed | no stop |
| R | Kneel Before Zod 0x3400074B | Wildcard_RSkill@0; skill_to_locomotion@0.4 | Kneel_Before_Zod | 3@0.200 | skill_to_locomotion | Wildcard_SkillR_Secondary,Zod_Kneel_End | Wildcard_SkillR_Secondary,Zod_Kneel_End | 3@0.25,2@0.4 | Slider_Turn,TurnSpeed | skill_to_locomotion@0.4 |
| passive | Born in Battle 0x3400074C | none | - | - |  | - | - | - | - | - |
