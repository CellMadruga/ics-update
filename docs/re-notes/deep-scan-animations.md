# Deep scan: what the client's animation side needs from the server, vs what ics sends (2026-10-26)

Sources: the full decompilation (`re-work/decomp/c/*.c`, `functions.tsv`) and capstone disassembly of
`InfiniteCrisis.exe` (VA, base 0x400000; read-only, Ghidra/REA not needed), the 54 base champions' behaviour graphs and
Lua (parent packs, read with `ics.rp.Pack` + `uesrv.havok.Packfile`), the scriptlet tables (`ics.gamedata.Data`), the
server scripts (`ics.script_model`), `data/skill_hooks.tsv` + `ics/script_runtime.load_graph_hooks`, and the tester's
`logs/traffic.log` / `logs/server.log` of 2026-10-26 (fase3-hz, Gaslight Batman v AI: Zod / Mecha Wonder Woman /
Solomon Grundy, plus an AGL session at 17:21). Scratch scripts: scratchpad `ds_anim/` (`deathscan.py`, `loc.py`,
`st.py`, `lua.py`, `sdump.py`, `tabs.py`, `gev.py`, `gated.py`, `msg.py`, `va.py`). No game text is copied: only
state / event / variable names, ids and numbers.

Tags: **C** = read in code, data or log; **P** = probable (strong inference); **G** = guess.

Builds on: animation-deep-scan.md, champion-animation-matrix.md, client-scriptlets-graphs.md, client-movement.md,
skill-second-stages.md, grab-arm-carry.md, sweep-property-listeners.md, full-entities-engine.md.

---------------------------------------------------------------------------------------------------------------------

## 0. Summary (ranked fixes are in section 7)

1. **The respawn get-up event ics sends, `CbtState_Death_Recover 0x10000034`, exists in no champion's main state
   machine** (51 / 54 graphs do not even list the name; Gaslight Batman, The Joker and Poison Ivy list it but have no
   transition on it). The client maps it to local index -1 and drops it silently (C). The enter-world scriptlet sent
   with it (`_Entity_OnEnterWorld_Default 0x100002F5`) is in no champion table except Deathstroke's, so the client
   rejects it too (C). Nothing takes the bot out of the `Death` state, whose clips hold the lying pose whatever the
   replayed velocity: it slides back to the lane lying down. The authored respawn is **`_Defeat_OnRespawn
   0x100001FC`** (in every champion's tables, C), whose only graph action is a type 0x14 raise of
   **`Global_Locomotion 0x100000AA`**, a wildcard to `Locomotion` in all 54 main machines (C).
2. **Zod's R (Kneel Before Zod) is aborted 0.51 s after every cast** (C, log + script + graph): GRAPH_HOOKS times code
   3 / 2 from clip triggers that belong to the *last* sub-state of a staged state, so code 2 arrives during the channel,
   the script's T4 (S1 -> S2 on code 2) cancels the skill and raises `skill_to_locomotion`. 13 more staged states get a
   timed code 2 the same way (section 5.2).
3. **Basic attacks: hook times are never scaled by attack speed** (C): the client plays the basic-attack clips at
   `playbackSpeed = Attribute_AttackSpeed = 0x100006FE` (C, binding + Lua), but `_graph_cast` signals at the tsv times
   (1x or the clip's static 0.85). Gaslight Batman at AS 1.627: the batarang hook is at 0.147 s in the client, ics fires
   it at 0.41 s. 20 multi-state basic scripts (Zod's among them) are not in GRAPH_HOOKS at all and use 0.25 / 0.40.
4. **0x100006FE on bots does not match their attack cadence** (C log: AI: Zod sent 1.076 = level-20 base, attacked every
   0.69 s = ~1.45 / s) and the bundle carries 0x100006FE twice (C).
5. **Bots: no stop state before casts and a 0.13 s hook offset that only the local champion's deferred scriptlets
   justify** (C code): bot skill states see Propel > 0 (glide / early-out) and their hooks fire 0.13 s late.
6. The graph-event **drop rule** (`[entity+0x118] & 0x40` without `& 8`) does not apply to server-created champions
   (C code path, C diag fase3-hk); it is not the respawn cause. Re-creating the object is not needed.

---------------------------------------------------------------------------------------------------------------------

## 1. How a graph event reaches the graph, and when it is lost (C unless marked)

| Step | Address | Rule |
|---|---|---|
| server form | 0x8D scriptlet `0x100001E3` + script variable `0x780` = event (or a scriptlet key whose action list has type 0x14 events) | key must be in the object's tables (`0x5235C0`), else `0x80070057` (client-scriptlets-graphs.md 1.2) |
| action 0x14 | `0x672930` | event = literal field 0x97 or variable 0x780 (kind 8 / 0x0A); target = the 0x8D's object; `(entity+4)->vt+0x58` |
| raise | `vt+0x58` = **`0x55BD30`** (class `0x15C6D30`, base `0x15B4FE0`) | **drop** if `[ent+0x118] & 0x40` and not `& 8` (`0x55BD3F..0x55BD45`); else if `vt+0x50` (`0x55B970`: graph instance `[mgr+0x30]` exists and its byte `+0x112` is set) is false, **queue** in the array at `mgr+0xA4` (count `+0xAC`), delivered later in order |
| deliver | `0x55AF70` | `0x5590E0(global)` = the 0x1C wrapper's global -> local map (`[mgr+0x40]+0x80..+0x8C`); **-1 = not in this graph: dropped, no error** (`0x55AF83 cmp eax,-1`); else `[mgr+0x30]->vt+0x18(local)` + `vt+0xB0` update request; in both cases the event is also passed to the listener list at `mgr+0xA0` (`0x55ABC0`, P: attached graphs / sound hooks) |
| in the graph | Havok state machine | the event must be a transition of the active state, of a parent machine's wildcard list, or handled by a Lua callback; otherwise nothing happens |

### 1.1 The 0x40 / 8 flags (C for the writes found, O for who sets 0x40)

* `+0x118` is initialised at construction step 2 (`0x54F0B0`: `ent+0x118 = [[creation info+4]+4]`), i.e. from the
  creation info's own flag word. No `|= 0x40` exists in the client's code (all `0x118` writes checked: `|1`, `|8`,
  `|0x200`, `&~8`).
* Bit 8 ("in the scene") is set by the create path for server objects (event 0x4 / 0x87 -> `0x64BD30`, `0x64D8A0`) when
  the factory's scene flag `+0x11C` is up, and cleared only by remove 0x3 (`0x64DDE0`) or the detach `0x603F40`.
* Bit 0x40 objects are handled specially in remove (`0x64DDE0`: children with 0x40 are re-placed) and detach
  (`0x603F40`): P = client-only / contained objects (cinematic actors, attached FX), not network champions.
* So a bot champion created by bundle and never removed has 8 set: its events are never dropped by this rule; they are
  only queued while its graph is inactive (diag fase3-hk: 100 delivered, 4 queued, 0 dropped). **Not the cause of the
  lying respawn (C path, P that 0x40 is never set on a server champion).**

### 1.2 What a full bundle does to the graph (C, champion-animation-matrix.md 1)

A 0x4 bundle for an existing IID of the same class rebuilds nothing (`0x64D8A0`); its 0xBC table is a full property
replace, so every bound graph variable (0x100006FE) is re-pushed, but **the state machine is not reset**. Re-creating
the object (0x3 then 0x4) would restart the graph in its start state, at the price of the nameplate / HUD / minimap
links: not needed for any fix below.

---------------------------------------------------------------------------------------------------------------------

## 2. Death and respawn (C)

### 2.1 What each graph takes (scan of all 54 champion main machines; `deathscan.py`)

| Event | Id | Main-machine wildcard in | Target state |
|---|---|---|---|
| CbtState_Death_Induce | `0x100000AD` | 54 / 54 (flags 0xC00) | `Death` (SM_Death: FaceUp / FaceDown / Ragdoll by `Death_Selection`; clips end in the lying pose; **no outgoing transition of its own**) |
| CbtState_Dead | `0x1000010B` | 54 / 54 (0xE00) | `Dead` (held prone pose) |
| **CbtState_Death_Recover** | **`0x10000034`** | **0 / 54**; name absent from 51 graphs, listed without a transition in Gaslight Batman / The Joker / Poison Ivy | none: dropped |
| CbtState_GetUp | `0x1000009D` | 54 / 54 (0xC00) | `Get_Up` (FaceDown / FaceUp by `Knockup_Selection`, clip `playbackSpeed <- AnimationSpeedMultiplier`), self `state_to_locomotion` at 0.40 s |
| **Global_Locomotion** | **`0x100000AA`** | 54 / 54 (0xC00; Wonder Woman 0x800, local wildcard of `Logic_Behavior`) | `Locomotion` (state 0) |
| Combat_Locomotion | `0x1000024D` | 54 / 54 | `Locomotion` |
| SpawnIdle | | 54 / 54 (0x800) | `SpawnIdle` / `Spawn00` |

Main machine name: `SM_Main_Machine`, except Doomsday, Poison Ivy, Wonder Woman (`Logic_Behavior`).

### 2.2 The authored defeat scriptlets (pack 0xA00000DF table 0x1D0000E8, merged with the audio table 0x1D0001F6 of pack 0xA00000B3; every champion has both, `haskeys.py` / `tabs.py`)

| Key | Name | Graph action (type 0x14) | Other |
|---|---|---|---|
| `0x100001FA` | _Defeat_OnDead | `0x100000AD` Death_Induce | 0x1D0001F6: a type 9 (P: the death vocal) |
| `0x100001FB` | _Defeat_OnIncapacitated | `0x100000AD` | type 0x17 with `Vfx_Stop 0x10000130` (P: stops looping FX on the body) |
| **`0x100001FC`** | **_Defeat_OnRespawn** | **`0x100000AA` Global_Locomotion** (the only action in 0x1D0000E8) | 0x1D0001F6: a type 9 (P: the respawn vocal) |
| `0x100001FD` | _Defeat_OnRevive | `0x1000009D` GetUp, then `0x100000AA` | |
| `0x100001F9` | _Defeat_StartupIncapacitated | `0x1000010B` Dead | props `{0x7E6}` |
| `0x100002FD` | _Combat_GoToLocomotion | **none**: two type 0x22 containers on LifeState `0x100000FA` (value 4) and `0x10000B2D` | run by 173 server scripts at the end of CC statuses (C); P: a property-conditioned container, it raises nothing by itself |

None of `0x100001F9..FD` is referenced by any 0x34 script (only `_Defeat_OnDead` once) nor by client code: they are
the original server's messages (C for the absence, P for the use).

### 2.3 What ics sent (traffic 19:44-19:52, AI: Zod, C)

```
death:   bundle (stop where it falls) | LifeState 2 (0x6) | graph 0x100000AD           -> Death state, lying pose
respawn: LifeState 4 (0x6) | 0x100000BC alive | full bundle with tele_seq + 1 (snap at base)
         +0.17 s graph 0x10000034 (dropped: not in Zod's graph) | _Entity_OnEnterWorld_Default (rejected: not in Zod's tables)
fase3-ia adds: 0x10000034 again at 0.6 / 1.5 s + _Combat_GoToLocomotion (in the tables, raises no graph event)
```

Why the pose persists: the `Death` state has no transition of its own; the only ways out are main-machine wildcards
(locomotion, GetUp, skill starts, CC). None arrives until the bot's first basic attack (`Combat_Basic_Attack` -> its
own table's type 0x14 `Basic_Attack 0x1000006E`, C) or skill start. Meanwhile the replayed walk only changes
`Property_Slider_Propel`, which the Death clips do not read: the lying body slides along the path (C mechanism; matches
the tester's report). The local champion is not affected because ics never raises Death_Induce on it
(`death_as_property` false: no fall event, C).

### 2.4 The fix (C data, P that it is what the original did)

* Respawn, every champion (bot and local): after the respawn bundle (same tick or the next), **0x8D `_Defeat_OnRespawn`
  `0x100001FC`** on the champion (plays the respawn vocal too), or equivalently `0x100001E3` + `0x780 = 0x100000AA`.
  `Global_Locomotion` has flags 0xC00 (no self-transition): a repeat while already in `Locomotion` is a no-op, so one
  resend at +0.6 s is safe. Drop `0x10000034` and `_Entity_OnEnterWorld_Default` for champions.
  Config: `respawn_graph_events = []`, `respawn_scriptlets = ["_Defeat_OnRespawn"]`, `bot_getup_scriptlets =
  ["_Defeat_OnRespawn"]`, `bot_getup_delays = [0.0, 0.6]` (date / tester report 2026-10-26 19:51).
* Death: `_Defeat_OnDead 0x100001FA` instead of the bare graph event (same 0x100000AD plus the vocal) (P, minor).
* A revive / get-up from a knockdown in place: `_Defeat_OnRevive 0x100001FD` (GetUp then Locomotion) or graph
  `0x1000009D` alone (its clip returns to locomotion by itself at 0.40 s).
* Bots: give them `scriptlet_keys` = `Data.scriptlets(class)` so keys outside their tables are not sent
  (`World.scriptlet` filters only when `scriptlet_keys` is not None, C), cutting rejected 0x8D traffic.

---------------------------------------------------------------------------------------------------------------------

## 3. Movement side: locomotion versus a pose for a remote champion (C)

* Locomotion is a **graph state**, not a movement flag: the clip shown is the active state's; velocity only feeds graph
  inputs. A pose state (`Death`, `Dead`, `KnockDown`, `Stasis`, `Cower`, skill states without a Propel blend) ignores
  movement completely; only an event takes the graph back to `Locomotion` (2.1).
* Inputs written by the replay step `0x60B5F0` -> **`0x6097E0`** (only on the smooth branch: no newer seq A / B, error
  <= 2 m): `0x501` = side speed, **`0x300` = `Property_Slider_Propel` = forward speed clamped to [0, movement
  component `+0x2D0`]** (`0x6098F6`), `0x1F1` = `Property_Slider_Turn` = per-step yaw delta x -1/180 clamped to
  [-1, 1]. On the snap branch (teleport seq, > 2 m) the inputs keep their previous values.
* **`+0x2D0` is property `0x7EC`** (watcher `0x550160` writes `[comp+8+0x2C8]`), and `0x7EC` is set from
  **`0x100005E4` move speed** by the listener at `0x974522` (`0x56F2D0(ent, 0x7EC, value)`, f32 only). So the run
  cycle can never show more than the champion's `0x100005E4` value: if the server moves a hasted champion faster than
  the value the client holds, the legs run at the cap while the body moves faster (skating) (C clamp; P whether the
  client applies the 0x20F0 modifiers it receives, e.g. `0x100005E4 op 10 = 0.45`, to that property).
* Inside `Locomotion`: Lua `onMoving` fires `Stop_From_Moving` when Propel == 0 (exactly 0: a speed-0 state is
  needed for idle); idle / walk / run clips are blended on Propel (Zod: 0, 1.25, 2.5, 3.7, 5, 9 m/s clips); footstep
  sounds only above 0.5 m/s.
* Early-outs that read the same inputs (all champions, same Lua): `onSkillEarlyOut` / `onCosmeticEarlyOut` /
  `onHandleEventCosmeticEnabled` -> `Global_Locomotion` on Propel > 0 (>= 1 in tails) or Turn != 0;
  `onBasicAttackEarlyOut` -> `Combat_Locomotion` on Propel >= 1; `onEmoting` -> `Emote_Abort` on Propel > 0 or
  Turn != 0 once `EmoteDelayEnded`.
* Consequences for the server: a stop state (speed 0) before any cast / emote; no facing turn inside a
  cosmetic-enabled state; for a respawn, the snap (seq A + 1) plus `Global_Locomotion`; the first walk state after it
  gives Propel on the next smooth step.

---------------------------------------------------------------------------------------------------------------------

## 4. Which graph inputs and events the server drives vs the client's own script copies

| Area | Server must send | Client copies / graph do themselves | ics today |
|---|---|---|---|
| Cast start | the start event (0x100001E3 + 0x780, or the champion table key that raises it, e.g. `Combat_Basic_Attack_Right/Left 0x10000195/96`, Zod `Combat_Basic_Attack 0x10000128` -> `Basic_Attack 0x1000006E`) | nothing: the client never raises skill starts (only 0x20EE orders go up) | sent (C) |
| Cast signals (OnCastSignal 1/3/5/6/2 for the server script) | the server times them from the graph clip triggers (the original evaluated the hooks server-side, P) | the clip triggers fire client-side but no reader turns them into script signals (`turbineEventHookPayload` has no reader, C) | GRAPH_HOOKS; errors in 5 |
| Stage / end events (Kneel_End, Grab_Hit, Skill_Dash_*...) | raised by the server scripts (RaiseGraphEvent) when their branch runs | - | only when ics runs the branch (5.2) |
| `skill_to_cosmetic`, `skill_to_locomotion` inside clips, `state_to_state`, Rubble_End | - | clip triggers (self-raised) | the script-raised `skill_to_locomotion` can cut tails (`keep_cosmetic_tail` 0.8 s) |
| Attack speed | **`0x100006FE` (net 1)** = attacks per second, bound to `Property_Attribute_AttackSpeed` -> Lua `onSetBasicAttackSpeed` -> `Attribute_AttackSpeed` -> basic clips' `playbackSpeed` (111 graphs) | - | sent = stats value, not the cadence (6) |
| Propel / Turn | the replicated motion (speed, heading, facing) | `0x6097E0` | full bundles; bots no cast stop (5.4) |
| Move-speed cap | `0x100005E4` | `0x7EC` -> `+0x2D0` | base value (3) |
| TargetHeading `0x100001BF`, AnimationSpeedMultiplier `0x10000936`, TurnSpeed `0x100003B0`, ToggleFidget `0x1000044E` | nothing (net 0) | client script copies (SetGraphVariable `0x1000002F`) and status FX | - |
| Death / respawn | `_Defeat_OnDead`, `_Defeat_OnRespawn` (2) | - | wrong respawn id (2.3) |
| Stun | status script: `Vfx_Status_Stun_Active`, bool `0x100003F3`, exit `RaiseGraphEvent 0x100000AA` (0x34000130, C) | client holds orders on 0x100003F3 | script runs (C) |
| Knockdown / knockup | statuses 0x48000295 / 296 (0x34000131 / 132): FX record via `_ExecuteScriptlet 0x100003EA` (the fall clip), get-up via scriptlet `0x10000355` / graph `0x1000009D`, end `_Combat_GoToLocomotion` | `Get_Up` self-ends | sent by the scripts (C log: `0x100003ea` with a variable) |
| Hit flinch disable | `CbtState_DisableHit 0x100003AF` / `EnableHit 0x100003AE` (Lua `onHandleEventGlobal` sets `GetHitEnabled`) | - | only for Super Strength |
| Carry | parent block of the carried object's 0xB0 (flag 0x04: parent IID, mode, extra `{u32, u8, u8 0/1}`); a mode of 0 attaches nothing (`0x55F930`: `if (mode != 0)`) | the Hold blends on Propel | `liftable_attach` mode 0x10, point 0x100000B0 (P values) |
| Channels | the script's own end event (`Tempest_to_Locomotion`, `*_End`), no timed code 2 | loop clips | timed 2 in some (5.2) |
| Emotes | `Emote_Joke 0x1000022E`, `_Taunt 0x1000022C`, `_Laugh 0x1000022D`, `_Dance 0x100001F1`: **local transitions** (not main-machine wildcards) in all 54 graphs, i.e. taken only from the locomotion / idle sub-machine; aborted by Propel > 0 / Turn != 0 | `Emote_Abort` by Lua | needs a stop state first (P) |
| Recall | `Recall_Start 0x100005BA` is a wildcard only in Zod's graph; dropped (-1) in the 53 others (C) | | sent to all (harmless) |

---------------------------------------------------------------------------------------------------------------------

## 5. GRAPH_HOOKS and cast timing errors (C unless marked)

`load_graph_hooks` reads 257 scripts from data/skill_hooks.tsv and keeps 173: a script whose states differ is dropped
(fixed 0.25 / 0.40 s fallback); a state's codes and exit are the minimum trigger times over **all** its clips,
including those of nested sub-states that are entered later.

### 5.1 Attack speed not applied (56 speed-bound scripts, 36 of them in GRAPH_HOOKS)

The tsv time is `local_time / static_playbackSpeed`; at run time the bound `playbackSpeed` is the 0x100006FE value, so
**real time = tsv_time x static_speed / AS**. Examples (C data + C log values):

| Champion | Script | tsv hooks | static | AS sent | client real | ics sends (+0.13 offset) |
|---|---|---|---|---|---|---|
| Gaslight Batman (local, 19:41) | `0x34000037` | 6 @0.059, 5 / exit @0.282 | x0.85 | 1.627 | 6 @0.031, 5 @0.147 | 6 @0.19, 5 @0.41, 2 @0.42 |
| Mecha Wonder Woman (bot) | `0x340002CC` | 6 @0.05, 5 @0.24 | x1.00 | ~1.0-1.3 | 5 @0.18-0.24 | 5 @0.37 |
| Solomon Grundy (bot) | `0x3400066C` | 6 @0.05, 3 @0.24 | x1.00 | | 3 @0.24 / AS | 3 @0.37 |
| Zod (bot, level 20) | `0x3400074D` | not loaded (6 different states) | x1.00 | 1.076 | 3 @0.223 (`Basic_Melee_Large`), 3 @0.056 (`_Rush`) | fallback 5+3 @0.25, 2 @0.40 |

So the projectile / VFX of a fast-attacking champion leaves 0.2-0.3 s after the throw motion, and at level 1 (AS
0.58-0.69) slightly before it. 20 multi-state speed-bound scripts are on the fallback (`0x3400000C 0x340000C8
0x3400011C 0x340001F6 0x34000200 0x34000238 0x34000257 0x3400030E 0x34000457 0x34000481 0x340004B9 0x340004CC
0x3400056A 0x34000579 0x340005BB 0x34000637 0x3400070F 0x34000725 0x3400074D 0x34000799`): their states are the
basic / critical / empowered / rush variants, chosen in the client by the start event the server raised.

### 5.2 Staged states get a timed code 2 that ends the skill (C for Zod, P per case)

`gated.py`: 41 skill states contain nested machines whose transitions wait for an event that no clip of the state
raises (the script raises it). For those, a hook time taken from a later sub-state's clip is not measured from the cast
start. Zod R `0x3400074B` (`Kneel_Before_Zod`: start -> channel, waits `Wildcard_SkillR_Secondary 0x100005D0` -> jump ->
pose, waits `Zod_Kneel_End 0x10000580` -> end clip with `a_SkillHook` 3 @0.200 and `skill_to_locomotion` @0.356):
GRAPH_HOOKS = {3: 0.2, exit 0.356}; ics sends 3 at 0.33 and 2 at 0.49 s; the script's `T4: S3,S1,S4,S5 -> S2 on
OnCastSignal 2` takes S1 (the channel) to S2: `skill_to_locomotion` at 0.51 s, cancel cooldown, no leap, no damage.
Log 19:31:20.244 Wildcard_RSkill -> 20.750 stop Vfx_Zod_Kneel_Rocks -> 20.751 `0x10000002`; the same on all 25 R casts in the
log, never followed by `Wildcard_SkillR_Secondary` or `Zod_Kneel_End` (C).

Staged states that also get a timed exit (same risk; P until each script's T on code 2 is checked):

| Champion | Script | State | Gate events | ics exit (s) |
|---|---|---|---|---|
| Superman (skin flight) | `0x340003D5` | SpeedingBullet | Windup_to_Start, Start_to_Loop, Loop_to_End | 0.11 |
| Wonder Woman | `0x3400017D` | BlockingBracers | `WonderWoman_BlockingBracers_End` | 0.30 |
| Wonder Woman | `0x34000185` | LassoGrab | `_LassoGrab_Dash`, `_LassoGrab_Hit` | 0.05 (< its code 5 @0.128) |
| Batman | `0x34000248` | Dark_Knight | `Wildcard_RSkill_Alt`, `_End` | 0.10 |
| Shazam | `0x34000756` | Speed_Of_Mercury | `_End` | 0.18 |
| Atomic Wonder Woman | `0x34000256` / `0x34000253` | StormingSmash / Reclaimer | `_End` | 0.12 / 0.276 |
| Supergirl | `0x3400047F` | BoundingBlow | `Skill_Dash_End` | 0.05 |
| Hawkgirl | `0x34000574` | Dash_Q | `Skill_Dash_End` | 0.20 |
| Krypto | `0x340005EE` | The_Stick_Dash | `Skill_Dash_End` | 0.23 |
| Deathstroke | `0x340007DD` | Dash_R | `Skill_Dash_End` | 0.20 |
| Huntress | `0x3400070A` | Grapple Bolt | `Skill_Dash_Start/_End` | 0.12 |
| Zod | `0x3400074B` | Kneel_Before_Zod | above | 0.356 |

Staged states with exit None already wait for the script (AGL Grab, Superman HeatVision, Flash SpeedStorm, Atrocitus
Overwhelming Rage, Green Arrow Bullseye, Batman Martial_Arts, Nightmare Catwoman Rip & Tear) but their code 3 / 5 may
still be timed from a later clip (P).

Also: enter / exit hooks of **nested** states are not in the tsv (only clip triggers): Gaslight Batman R Batflight
`0x34000038` has its code 2 as the `Recover` sub-state's enter hook (~0.61 s, animation-deep-scan.md 2), ics sends 2
at `graph_exit_fallback` 3.0 s (C for the tsv content, P effect: the script's end comes 2.4 s late).

### 5.3 Hook offset on bots (C code)

`_graph_cast` adds `GRAPH_HOOK_OFFSET` (0.13) for `kind == "champion"`, which includes bots (`create_bot_champion`:
kind "champion"), but `CastWorld.run_scriptlet` defers only `ent is self.w.champion`. Bot hooks are 0.13 s late
against their graph event (log: Zod's face bundle and its 0x8D in the same millisecond).

### 5.4 Bots get no cast stop state (C code)

`World.cast` sends the "stops to cast" bundle only for `ent is self.champion`: a bot casting while walking keeps its
replayed velocity (Propel > 0), so skill states with a Propel blend pick their moving variant, cosmetic-enabled states
early-out to `Global_Locomotion`, and the body glides on (champion-animation-matrix.md 3.1, now for bots).

### 5.5 0x100006FE on bots (C log)

AI: Zod at 19:52:10-20: bundle 0x100006FE = 1.076 (= 0.62 + 0.024 x 19, the level stats without items / buffs) while
the server's attack cooldown gave one basic every 0.68-0.70 s (~1.45 / s; `World.attribute(0x100005FE)` = base +
modifiers). The client clip (hit 0.223 s, tail to ~0.93 s at 1.076x) is restarted at 73 % each time (`Basic_Attack`
flags 0xE00 allow the self-transition). The local champion matched (1.627 sent, 0.615 s cadence). The bot bundle also
carries 0x100006FE twice (`bot_properties` appends it after `stat_properties`), harmless (the second wins).

---------------------------------------------------------------------------------------------------------------------

## 6. Super Strength carry / throw and Grab's arm (C log 17:21, P effects)

* Vehicle lift at 17:21:22 (AGL): InitObjectPickup on both at 0, CarPickup at 0.10, **PickupObject `0x100007A1` on AGL
  and the vehicle at 0.10** (its graph event `SuperStrength_PickupCar 0x10000175` is only a transition from `Hold`,
  which the machine reaches at ~0.57 s: dropped at 0.10; it only belongs to a toss / catch, grab-arm-carry.md 2.6),
  attach bundle at 0.10, DisableHit at 0.10; throw at 46.766 (ThrowObject + a full facing bundle), **detach at 0.148
  s** (the `Car_Throw` release hook is code 5 @0.200, `super_strength_cast_signals` says 0.20), EnableHit 0.19,
  `_Combat_GoToLocomotion` 0.8 s. Repeated haste modifiers `0x100005E4 op 10 = 0.45` every ~2 s during the carry
  (section 3: the walk-cycle cap).
* Remaining unknowns: the attach mode / extra block meaning (only "mode != 0 attaches" is C, `0x55F930`), and the
  arm beam's target resolution (grab-arm-carry.md 1.4 step 5). Diag probes in 8.

---------------------------------------------------------------------------------------------------------------------

## 7. Ranked server fixes

| # | Fix | Exact form | Confidence |
|---|---|---|---|
| 1 | **Respawn leaves the death machine** | after the respawn bundle: 0x8D `_Defeat_OnRespawn 0x100001FC` on the champion (graph action `Global_Locomotion 0x100000AA`), optional resend +0.6 s; drop `0x10000034` and `_Entity_OnEnterWorld_Default` for champions; `_Combat_GoToLocomotion` is not a get-up. Keys: `respawn_graph_events = []`, `respawn_scriptlets = ["_Defeat_OnRespawn"]`, `bot_getup_scriptlets = ["_Defeat_OnRespawn"]`, `bot_getup_delays = [0.0, 0.6]` (and `World.get_up` must send the scriptlets on the first delay too) | C (graphs, tables, drop path, log); P that the visual is then right |
| 2 | **Staged states: no timed code 2; codes timed from the gate event** | in `load_graph_hooks`, mark states whose nested transitions wait for script-raised events (the `gated.py` rule) as `exit None`; keep only codes of clips in the entry chain; when the script raises a gate event on its owner (`_raise_graph_event`), start that sub-state's codes / exit from then (Zod: on `0x10000580` -> 3 at +0.20, 2 at +0.366). Key e.g. `graph_hooks_gated = true` | C for Zod (log + script + graph); P for the 13 others |
| 3 | **Scale speed-bound hooks by attack speed** | for rows with `binding = speed-bound`: t = tsv_t x static_speed / AS, AS = the 0x100006FE value last sent for that entity (default 1.0); apply to codes and exit. Key `graph_hooks_attack_speed = true` | C data / binding; P visual |
| 4 | **Multi-state basic scripts by start event** | build GRAPH_HOOKS per (script, start event): the state each start event enters (`Basic_Attack`, `Basic_Attack_Critical`, `Empowered_Attack`, `*_Rush`), choose by the event the server raises for that attack (20 scripts) | C data; P effect |
| 5 | **0x100006FE = the cadence's attacks per second** | send `World.attribute(ent, 0x100005FE)` (base + item + buff modifiers) as 0x100006FE in bundles and as a 0x6 change whenever it changes (> 1 %), for champions, bots and units; drop the duplicate in `bot_properties` | C mismatch; P effect |
| 6 | **Bots: stop state before casts, consistent offset** | apply `cast_stop_state` to bot champions (`World.cast`), and either defer their cast 0x8D by `champion_scriptlet_delay` like the local champion or use offset 0 for them in `_graph_cast` | C code; P effect |
| 7 | **Move-speed cap** | keep the champion's `0x100005E4` property equal to the speed the server moves it at (0x6 change on haste / slow) unless diag shows the client folds the 0x20F0 modifiers into it | C clamp; P need |
| 8 | **Super Strength vehicle** | do not send PickupObject at the pickup (only for a toss / catch from Hold); detach at the `Car_Throw` code 5 (0.20 s); keep DisableHit / EnableHit | C log / graph; P visual |
| 9 | Death with vocal | `_Defeat_OnDead 0x100001FA` instead of the bare `0x100000AD` | C data; P |
| 10 | Batflight end | read nested enter hooks (code 2 of `Recover`) into the tsv (tools/graph_hooks.py) | C data; P |
| 11 | Traffic hygiene | bots' `scriptlet_keys` from their tables; skip `Recall_Start` / `Emote_Abort` / `CbtState_Trigger_Start` on graphs that lack them (dropped anyway) | C; low value |
| 12 | Emotes | stop state before the emote event; no facing bundle during it | C Lua; P |

---------------------------------------------------------------------------------------------------------------------

## 8. diag.py probes to confirm the uncertain points (rva = VA - 0x400000; not added to tools/)

| Name | rva | Log | Confirms |
|---|---|---|---|
| graph-in | `0x15AF70` (`0x55AF70`) | `ecx` manager, `[ecx+4]+0x100` entity IID, `[esp+4]` global event | every event that reaches delivery, per entity |
| graph-local | `0x15AF83` (after `call 0x5590E0`) | `eax` local index (-1 = not in graph) with the event from the entry probe | `0x10000034` -> -1 and `0x100000AA` -> index on AI: Zod at respawn (fix 1) |
| graph-gate | `0x15BD36` (`0x55BD36`) | `[[esi+4]+0x118]` flags; and `0x15BD4E` `al` (graph ready) | no drops (0x40 without 8) / queueing for remote champions |
| propel-cap | `0x2098F6` (`0x6098F6`) | `[ebx+0x100]` entity IID, `[eax+0x2D0]` cap, `[ebp-0xC]` forward speed before the clamp | a hasted champion's speed above the cap (fix 7) |
| speed-prop | `0x150184` (`0x550184`) | `[edi+4]` f32 = new 0x7EC; `esi-8` component | which move speed the client holds, after 0x20F0 modifiers |
| attack-speed | `0x159F7F` / `0x159F87` (in `0x559F50`) | property id / variable index; value `[edi+4]` | 0x100006FE values reaching `Property_Attribute_AttackSpeed` (fix 5) |
| attach | `0x15F930` (`0x55F930`) | `[esp+4]` child entity, `[esp+8]` mode, `[esp+0xC]` extra block (u32, u8, bool) | the carried object's attach values (fix 8) |
| arm beam | `0x27338E` (`0x67338E`) | `[ebp-0x28]` u64 target | the Grab missile's beam target (grab-arm-carry.md 1.4) |

Expected after fix 1: at the bot's respawn, graph-local shows `0x100000AA` with a valid index, and the bot walks
upright from the base.
