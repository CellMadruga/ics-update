# Champion skill animations: the Havok behaviour graph and what it needs (deep scan, 2026-10-25)

Static analysis of the champions' Havok behaviour graphs (hk_2012.2.1-r1 packfiles inside the parent packs, read with
`ics.rp.Pack` + `uesrv.havok.Packfile`) and of `InfiniteCrisis.exe` (VA, image base 0x400000). Confidence: **C** = read
in data or code, **P** = probable, **O** = open. Helper scripts (scratchpad, not in the repo): `hkbload.py`,
`hkbtree.py` (graph tree dumper), `lua.py` (graph Lua functions). No game text is copied here: only state / event /
variable names and numbers.

## 1. Where the graph is and how to read it (C)

* Atomic Green Lantern: `chr_atomic_green_lantern_behavior.hkb` = record `0x1A000821` in parent pack `0xA0000150`
  (packfile at decompressed offset 0x32DB00, 97084 bytes). The `0x5B5` property's `0x1C000077` is the object-side
  wrapper; the behaviour itself is the 0x1A packfile. Gaslight Batman: `0x1A0002E7`, pack `0xA0000122`.
* Classes used (AGL): hkbBehaviorGraph, 24 hkbStateMachine, 86 hkbStateMachineStateInfo, 32 **hkbScriptGenerator**
  (Lua callbacks), 87 hkbClipGenerator, 47 hkbClipTriggerArray, 29 hkbStateMachineEventPropertyArray (enter / exit
  notify events), 14 **turbineEventHookPayload**, turbineRotateCharacterModifier, turbineDampingModifier,
  hkbExpressionCondition, hkbEvaluateExpressionModifier, hkbDelayedModifier, hkbTimerModifier.
* Layouts found (32-bit, hk 2012): hkbNode name ptr +32; hkbBindable variableBindingSet +8.
  hkbStateMachine: states hkArray +144, wildcardTransitions ptr +156. StateInfo: enterNotifyEvents +40,
  exitNotifyEvents +44, transitions +48, generator +52, name +56, stateId +60. TransitionInfoArray: hkArray +8 of
  60-byte entries: triggerInterval +0, initiateInterval +16, transition +32, condition +36, **eventId +40, toStateId
  +44**, priority +56, flags +58 (0x400 global wildcard, 0x800 local wildcard, 0x200 allow self transition).
  ClipGenerator: animationName +96, startTime +116 (cosmetic clips start at the cast point), playbackSpeed +120;
  ClipTriggerArray: 16-byte entries (localTime f32, event id, payload ptr, flags; negative time = relative to end).
  ScriptGenerator: child +92, onActivate +96, onPreUpdate +100, onGenerate +104, onHandleEvent +108, onDeactivate
  +112 (strings naming Lua functions). VariableBindingSet: hkArray +8 of 32-byte bindings (memberPath +0,
  variableIndex +20).
* String data (hkbBehaviorGraphStringData): eventNames +8, variableNames +32. Graph event ids in transitions /
  triggers are **indices into the graph's own event-name list** (AGL: 101 events, 21 variables).
* The Lua (one text block per graph in the parent pack; AGL at 0x326990) defines the callbacks
  (`onSkillEarlyOut`, `onCosmeticEarlyOut`, `onMoving`, ...), using hkbGetVariable / hkbSetVariable / hkbFireEvent.

## 2. AGL graph, skill part (C)

Graph variables bound to the entity (name prefix `Property_`): `Property_Slider_Propel` (forward speed),
`Property_Slider_Turn` (turn rate), `Property_BehaviorParams_TurnSpeed`, `_TargetHeading`, `_ToggleFidget`,
`_AnimationSpeedMultiplier`, `Property_Attribute_AttackSpeed`, `Property_BehaviorVariable_IsDeadlyCatch`; graph-only:
`CosmeticEnabled`, `GetHitEnabled`, `Attribute_AttackSpeed`, `Next_Basic_Attack`, selections.

`SM_Main_Machine` wildcard transitions (from any state): skill start events (flags 0xE00 = may restart itself)
`AtomicGreenLantern_ShardsofWill_Start -> 110`, `_Meltdown_Start -> 111`, `_Grab_Start -> 112`,
`_ScorchedEarth_Start -> 113`, `Basic_Attack -> 104`, `Basic_Attack_Critical -> 103`; and (0xC00)
**`Global_Locomotion -> 0`**, `Combat_Locomotion -> 0`, CbtState_* (Cower, Death_Induce, Dead, GetUp, Laugh, KnockDown,
KnockBack, KnockUp, Stasis, ...).

| State | Enter / exit notify (payload) | Inside | Leaves on |
|---|---|---|---|
| 110 Shards of Will | - | blend on `Property_Slider_Propel`: full-body clip at 0, upper-body clip over locomotion when moving (bone weights) | clip trigger end-0.10 s `skill_to_locomotion` (self-raised) |
| 111 Meltdown | enter `a_SkillStartHook` (0x340002B4, 1), exit `a_SkillEndHook` (0x340002B4, 2) | clip meltdown; triggers 0.10 `a_MissileFireHook` (payload), 0.17 `skill_to_cosmetic` | **only `skill_to_cosmetic` -> 120** (no `skill_to_locomotion` transition) |
| 120 Meltdown_Cosmetic | - | same clip from 0.17; `pre = onCosmeticEarlyOut` | end-0.20 `skill_to_locomotion`; **early out: Propel >= 1 or Turn != 0 -> Global_Locomotion** |
| 112 Grab | enter / exit hooks (0x340002B5, 1 / 2) | SM_Grab: `Grab_Start` (start clip, 0.14 `a_MissileFireHook`, 0.22 `state_to_state` -> loop clip, **looping until `AtomicGreenLantern_Grab_Hit`**) -> `Grab_End` (end clip, 0.07 -> end loop) | **`skill_to_locomotion` -> 0** (any time) |
| 113 Scorched Earth | hooks (0x340002B2, 1 / 2) | ground smash clip; 0.11 `a_SkillHook` (payload), 0.15 `skill_to_cosmetic` | only `skill_to_cosmetic` -> 119 |
| 119 Scorched Earth_Cosmetic | - | clip from 0.15, `onCosmeticEarlyOut` | end-0.20 `skill_to_locomotion`; early out on move / turn |
| 104 / 103 Basic / Critical | enter `a_SkillStartHook`, exit `a_EventHook` / `a_SkillEndHook` | left / right variants by `Next_Basic_Attack`; speed from `Attribute_AttackSpeed` | `basicattack_to_basicattack` -> cosmetic 105 / 106 (`onBasicAttackEarlyOut`: Propel >= 1 -> Combat_Locomotion) |

turbineEventHookPayload words (+8..): `0, 1.0f, 0, <0x34 skill script DID>, <code>, ...`: code 1 on enter
(`a_SkillStartHook`), 2 on exit (`a_SkillEndHook`). These are the graph's **notifications to the skill script**: the
animation itself says when the cast starts, when the missile leaves / the hit lands (`a_MissileFireHook` /
`a_SkillHook`) and when the skill is over. (Section 3: what the client does with them.)

Payload codes found in every graph: **1** = state enter (`a_SkillStartHook`), **2** = state exit (`a_SkillEndHook`,
sometimes an `a_EventHook` trigger, e.g. Bat Scream at 1.133 s), **3** = `a_SkillHook` / basic-attack hit,
**5** = `a_MissileFireHook` / `a_EventHook` (missile out), **6** = `a_SkillHold`. These are exactly the
`OnCastSignal [0x1000000F code]` values the skill scripts wait for (AGL Grab `0x340002B5`: `T3 S1 -> S3 on 5`
(launch), `T0 S1,S3 -> S2 on 2` (end); Meltdown the same). **So the cast point and the cast end are authored in the
animation graph (C for the data match; P that the original server evaluated these hooks itself, see 3).**

Gaslight Batman (graph `0x1A0002E7`, start events `Batman_Gaslight_Batarang 0x100000E5 -> 80`,
`_Sonic_Shell 0x100000E4 -> 81`, `_Bat_Scream 0x100000E7 -> 82`, `_Batflight 0x100000E2 -> 88`):

| Skill script | State | Hooks (real time = local / playbackSpeed) | Leaves on |
|---|---|---|---|
| Q Batarang `0x3400003B` | 80 Batarang (clip x1.25) | 5 @0.128 s, exit (code 2) @0.144 s (self-raised `skill_to_cosmetic`) | `skill_to_cosmetic` -> 110 cosmetic |
| W Sonic Shell `0x3400003A` | 81 (x1.25) | 5 @0.080, 2 @0.136 | `skill_to_cosmetic` -> 111 |
| E Bat Scream `0x34000039` | 82 (blend on `BatScreamMovement`, rooted clip) | 5 @0.843, 2 @1.133 (a_EventHook) + self `skill_to_locomotion` @1.133 | `skill_to_locomotion` |
| R Batflight `0x34000038` | 88 -> SM_Batflight: Attack (x0.85) 3 @0.082, `state_to_state` @0.611 -> Recover (enter hook 2), end-0.20 `skill_to_locomotion` | `skill_to_locomotion` |
| basic `0x34000037` | Basic_Attack_Left/Right (x0.85, playbackSpeed bound to `Attribute_AttackSpeed`) | 6 @0.059, 5 + `basicattack_to_basicattack` @0.282 (/ attack speed) | -> cosmetic 104 / 103 |

AGL hook times (all x1.0): Meltdown 5 @0.10, exit 2 @0.17 (`skill_to_cosmetic`); Grab: start clip 5 @0.14,
`state_to_state` @0.225 -> loop until `Grab_Hit`, then end clip -> end loop, exit only on `skill_to_locomotion`;
Scorched Earth 3 @0.11, exit 2 @0.15; Shards of Will: no hooks (driven by its status), self `skill_to_locomotion`
at clip end - 0.10; basic attack 6 @0.05, 3 @0.24 (/ attack speed).

Global ids (name table in pack `0xA0000038`; the graph-local -> global map is in the champion's `0x1C` wrapper
record, AGL at decompressed 0x34CBC4: 101 ids in local order, then (global, local) pairs): skill_to_locomotion
`0x10000002`, skill_to_cosmetic `0x10000550`, CosmeticEnabled `0x10000540`, Global_Locomotion `0x100000AA`,
Combat_Locomotion `0x1000024D`, a_SkillStartHook `0x10000133`, a_SkillEndHook `0x10000134`, a_SkillHook `0x1000014C`,
a_MissileFireHook `0x10000146`, a_SkillHold `0x10000424`, a_EventHook `0x10000008`; AGL ShardsofWill_Start
`0x1000032C`, ScorchedEarth_Start `0x1000032D`, Meltdown_Start `0x1000032E`, Grab_Start `0x1000032F`,
**Grab_Hit `0x10000331`** (= the missile S9's `RaiseGraphEvent(Shooter)[0x10000331]`).

### 2.1 Whole install (C, `hooks.py` / `stages.py`, output `skill_hooks_all.tsv` in the scratchpad)

389 skill states (257 skill scripts) carry an enter hook with their script DID. Codes: 3 in 193 states, 6 in 143,
5 in 124, an explicit code-2 trigger in 10; 133 states leave on `skill_to_cosmetic` (self-raised by a clip trigger;
the skill state's exit = code 2, then a cosmetic tail with `onCosmeticEarlyOut`). About 36 states have **no
self-ending trigger** and wait for an event the scripts raise: `skill_to_locomotion` (AGL Grab, Superman
HeatVision, Aquaman Undertow, Blue Beetle Stick_And_Move, Stargirl energy_conversion, Swamp Thing Husk_Channel, Katana
Cross / Shadow_Step / Thousand_Cuts, Deathstroke Healing_Factor, Dex-Starr / Arcane Harley Dash_W, ...) or a named
end (`FlashAttack_End`, `Flash_SpeedStorm_End`, `Acrobat_to_Loc`, `ArcaneGreenLantern_DenyTheBlack_End`,
`MechaWonderWoman_Afterburn_End`, `Tempest_to_Locomotion`, `Robin_VaultKick_End_Loc`, `Overwhelming_Rage_End`,
`Wildcard_ESkill_End`).

**Second stages inside a skill state** (nested state machines waiting for an event: the "starts but never
finishes" cases): AGL Grab `Grab_Hit 0x10000331`; WW LassoGrab `_Dash 0x1000044B`, `_Hit 0x100001F5`; Doomsday Charge
`_Grab 0x10000163`, `_End 0x10000164`; Supergirl Comet `_Grab 0x100004ED`, `_End 0x100004EE`; Superman SpeedingBullet
`0x100003CB / 0x100003C9 / 0x100003C5`, HeatVision `_Loop_to_End 0x100003CA`; Green Arrow Bullseye `_Loop 0x100003F1`,
`_Fire 0x100003F2`, `Superfoam 0x10000416`; Zod Kneel `_End 0x10000580`, `Wildcard_SkillR_Secondary 0x100005D0`,
Rush `_Loop_To_End 0x10000595`; Nightmare Catwoman Rip&Tear `_Hit 0x10000577`; Mecha WW Tempest `_Loop 0x1000039D`;
Lethal Measures `_Hit 0x10000412`; Blue Beetle `Stick_And_Move_Left / Right 0x10000404 / 0x100003FE`; every dash
`Skill_Dash_Start 0x10000564` / `Skill_Dash_End 0x100003C3`; ends: WW BlockingBracers `0x100002DD`, AWW StormingSmash
`0x100002DE` / Reclaimer `0x100002DF`, Aquaman Surge / Wrath `0x10000396 / 0x1000039B`, Sinestro CullTheWeak
`0x10000455`, Feed_the_Beast `0x10000449`, Ultimate_Shazam `0x1000028E`, SpeedStorm `0x100002C5`, Speed_Of_Mercury
`0x10000289`, Martial_Arts `0x100002CE`, `Wildcard_RSkill_End 0x100004DA` / `_Alt 0x100005C6`. These ids are raised
by the champions' own scripts (RaiseGraphEvent), so they reach the client only when ics runs that script branch.

## 3. Client side (C unless marked)

* Graph component (`entity+4`, base class "AnimationManager" vtable `0x15B4FE0`, character subclass `0x15C6D30`):
  vt+0x58 `0x55BD30` raise event (dropped when `[entity+0x118]` has 0x40 without 8, queued while not ready) ->
  `0x55AF70` -> `0x5590E0` (global -> local index from the 0x1C wrapper's map; -1 = unknown) -> the Havok graph
  (`[mgr+0x30]->vt+0x18(local, 0, 0)`), then vt+0xB0 (update request).
* Graph variables come from **entity properties**: vt+0x5C `0x55A830` -> `0x559F50(property value)`: id via
  `0x4FCE30`, map **`0x5594C0`** (hash at `[mgr+0x40]+0xBC/+0xC8`: property id -> variable index, -1 = not bound),
  typed write into the graph's variable value set (`[[mgr+0x30]+0xA8]+8`). `0x58F340(id*, value*)` is the raw f32
  form (callers `0xA88532` / `0xA88674` / `0xA8868E` at entity spawn, `0x6774A9` = a scriptlet action that sets a
  graph variable). Script node SetGraphVariable `0x1000002F` (`0x9CEAC0`) also uses vt+0x5C with property ids
  (`0x10000936` AnimationSpeedMultiplier, `0x100001BF` TargetHeading). Which property ids the `Property_*` variable
  names map to is **O** (the names are in neither the exe nor the name tables; read the map at runtime, section 6).
  P: `Property_Slider_Propel / _Turn` are the entity's locomotion speed / turn rate computed by the client from the
  replicated movement; `Property_Attribute_AttackSpeed` the attack-speed attribute.
* The client never raises `Global_Locomotion` / `Combat_Locomotion` / `skill_to_*` by itself (no code immediate):
  they come from the graph (clip triggers, Lua `hkbFireEvent`) or from the server (0x8D `0x100001E3`).
* The payload class `turbineEventHookPayload` (hkClass `0x1D09950`, vtable `0x1805B20`) has no reader in the exe
  besides its registration (`0x1542EC0`, `0x1172D80`, getClassType `0x11731B0`): the client does not turn hooks
  into script signals. With "the client never sends cast messages" (only 0x20EE), the hooks were evaluated **by the
  original server** (P: Turbine's server ran the same behaviour graphs or tables baked from them).

## 4. Why a delivered graph event shows only the wind-up (C for the graph rules, P for each case)

1. **The server's code 2 is early and is not the graph's exit.** ics signals 5 + 3 at 0.25 s and 2 at 0.40 s
   (`script_runtime.start_cast`, `world.cast_time`). Code 2 makes the scripts' S2 raise `skill_to_locomotion`; in
   states that leave only on it (Grab and the ~36 above) that cuts the animation; in the 133 cosmetic states it
   arrives during the cosmetic tail and cuts it (Batman survives because his states self-advance at 0.13-0.14 s).
2. **Missing stage events** (2.1 list): the graph sits in a loop clip (Grab_Start loop) until e.g. `0x10000331`;
   ics never runs the missile's S9 (no `0x10000022`, skill-second-stages.md 2), so the pull never plays.
3. **Cosmetic early-out**: in a cosmetic state `onCosmeticEarlyOut` fires `Global_Locomotion` as soon as
   `Property_Slider_Propel >= 1` or `Property_Slider_Turn != 0`; a server move or a facing turn (FaceTarget /
   ReleaseFacing, path corrections) right after the cast point ends the tail. Basic-attack cosmetic: Propel >= 1.
4. **Start events are never refused by the graph**: wildcard skill transitions have flags 0xE00 (global + local
   wildcard, self transition allowed); only the `[entity+0x118]` 0x40 drop and an unknown id (-1) refuse.
5. **Speed**: clips whose playbackSpeed is bound to `Attribute_AttackSpeed` / `AnimationSpeedMultiplier` play at
   that rate; real hook times scale by 1 / speed (O: the default when the property is never set).

## 5. Server recipe (ics), in order

1. **Graph-timed cast signals (C data, P effect).** Build at start, from each champion's parent-pack graph, a table
   script DID -> {enter: 1, hooks: [(code, t / playbackSpeed)], exit: time of the self-raised `skill_to_cosmetic` /
   `skill_to_locomotion` / code-2 trigger, or None}. In `start_cast`: signal 1 at once, each hook code at its time
   (scaled by attack speed for basic attacks), and **2 only at the graph exit**; when exit is None, do not send a
   timed 2 (the script itself ends the state: tether back, channel end, dash end). Keep 0.25 / 0.40 as fallback for
   scripts with no graph state. Config key e.g. `[ics] graph_cast_timing = true`.
2. **Do not cut cosmetic tails (P).** When the script's S2 raises `skill_to_locomotion` and the graph state leaves on
   `skill_to_cosmetic`, skip sending it (the cosmetic ends on its own trigger at clip end - 0.20 s), or delay it to
   that time. Config key `[ics] keep_cosmetic_tail`.
3. **Stage events.** Make the script branches that raise the 2.1 events run: Grab -> missile event `0x10000022`
   on attach success (S9 raises `0x10000331` on AGL); same family for LassoGrab / Charge / Comet / Rip&Tear.
4. **No movement or facing change during a cosmetic tail** unless the player orders a move (that is the authored
   early-out); keep FaceTarget turns before the cast point.
5. Leave `Global_Locomotion` (`0x100000AA`) as the server's interrupt for knock-backs / stuns only.

## 6. diag.py probe list (rva = VA - 0x400000)

| rva | log |
|---|---|
| `0x15AF70` | `[esp+4]` global event, `ecx` manager (= every event that reaches the graph) |
| `0x15AF83` (after `call 0x5590E0`) | `eax` local index (-1 unknown); print the graph event name from the local table |
| `0x159F7F` (after `call 0x4FCE30`) | `eax` = property id being pushed into the graph |
| `0x159F87` (after `call 0x5594C0`) | `esi` = variable index (-1 = not bound); with the previous line gives the `Property_*` -> property id map |
| `0x18F340` | `[[esp+4]]` property id, `[[esp+8]]` f32 value (raw graph variable sets) |
| `0x1CEAC0` | SetGraphVariable node (client copy) |
| `0x272930` / `0x2729A9` | scriptlet action 0x14 raise graph event (event in `esi`), as client-skill-instances.md 4 |

Expected: Propel / Turn ids and values during a cast (non-zero Turn at the cosmetic start = case 4.3).
