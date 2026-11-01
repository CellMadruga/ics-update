# Skill execution model: how a champion ability runs end to end (2026-10-26)

Sources: the full decompilation (`re-work/decomp/c/*.c`, `functions.tsv`, `strings.tsv`) plus capstone on
`InfiniteCrisis.exe` (VA, base 0x400000, read-only; REA / Ghidra not needed), the 54 champions' behaviour graphs
(parent packs, `uesrv.havok.Packfile`), the 875 decoded server scripts (`data/script_trees`, `ics.script_model`), the
skill records (`ics.gamedata.Data.record`), `data/skill_hooks.tsv`, ics' runtime (`ics/script_runtime.py`,
`ics/script_nodes.py`). Scratch scripts (not in the repo): scratchpad `skillexec/` (`xdis.py` disassembler,
`findptr.py`, `evscan.py` + `icsraise2.py` + `accept.py` + `table.py` = the event census, `hookprog.py` = the
prototype graph-program extractor -> `hookprog.json`, `show.py`, `gates.py`, `reflags.py`). No game text is copied:
only ids, state / event / variable names and numbers.

Tags: **C** = read in code, data or a run; **P** = probable (strong inference); **G** = guess.

Builds on (and corrects, 8): deep-scan-animations.md, animation-deep-scan.md, champion-animation-matrix.md,
skill-second-stages.md, client-skill-instances.md, full-combat-skills.md (1.x), skill-mechanics-recipes.md 6,
kit-audit-1/2/3.md, grab-arm-carry.md, crime-alley-props.md A.3, targeting-indicator-and-structures.md 1.

---------------------------------------------------------------------------------------------------------------------

## 0. The model in brief

1. **The client only asks.** Input -> CanActivate `0x8709E0` (local refusals, nothing sent) -> targeting mode
   (`0xA26420`) -> order `0x20EE` (`cmd | slot | target IID | position | u8`). While a non-instant slot enters
   targeting the client also sends **`0x20EA {slot, [0x10000023]}`**, and for the one skill flagged `0x10000A46`
   (Green Arrow R) **`0x20EA {slot, [0x10000009]}`** when that targeting is cancelled. Nothing else about a cast goes
   up: no hook, no cast end, no stage event (C).
2. **The cast signals are the behaviour graph's own hook events.** Every skill state of every champion graph
   carries `turbineEventHookPayload {didTargetHFSM, eEventHookType, vMissileOffset}`; the engine's animation-event
   handler turns each one into event **0x1000000F** with parameter **0xC58BA9B = hook type** and
   **MissileFireOffset (0xA2103E4)**, posted to the HFSM instance whose DID is in the payload (or to every instance
   when the DID is 0). Hook type = the OnCastSignal code: 1 SkillStart (state enter), **2 SkillEnd (state exit)**,
   3 Skill, 4 MissileInit, 5 MissileFire, 6 SkillHold. This whole pipeline is in the client exe (2) and its hkClass
   text says the payload is "used on the server"; the client hosts no cast-script instances, so on the client it
   reaches nothing. **The original server ran each champion's behaviour graph itself and got its cast signals from
   it** (C for the pipeline and the data, P that the server ran the same engine code).
3. **Code 2 = "the graph left the skill's state"**, by any route: its own trigger (`skill_to_cosmetic`,
   `skill_to_locomotion`), a stage chain reaching its end, or a wildcard taking the graph elsewhere (a CC
   `CbtState_*`, death, another skill's start event, `Global_Locomotion`). 388 of the 389 hooked skill states carry
   the exit hook (C). Interrupts by stun / death / a new skill therefore reach the script through the graph.
4. **Multi-state skills advance by graph events the script raises** (`RaiseGraphEvent`: 39 of 53 gates raised by the
   skill's own script, 7 by another script such as the tethered missile, 7 through scriptlets / native, 3.3); the
   hooks of a sub-state fire only once that sub-state is entered. A timer in the script (channel, fuse) decides when
   to raise the next gate; the graph only reports.
5. **Basic attacks**: the script sets its own cooldown `1 / max(attack speed, 0.1)` (C) and picks the variant
   (critical / left / right) by the scriptlet it runs; the graph plays the variant at `playbackSpeed =
   Attribute_AttackSpeed`, so the hook times scale with 1 / attack speed (C). Re-issuing the next swing while the
   attack order stands is the server's order system (P).
6. **Native server glue that no script does**: the order system (0x1000001D on the slot script with TargetIID /
   TargetPosition, queueing behind the action lock, walking into range, repeating basic attacks), the re-init /
   status / missile / dash / attach / death / damage event families (5, 57 event ids), and starting the Super
   Strength sub-skill instance. Super Strength's lift / throw timings themselves are **graph hooks**
   (`SM_SuperStrength_Car` / `_Rubble` in every champion graph), and its "lift end" 0x100000BB is raised by the
   sub-skill script, not by native code (C).
7. **Every script declares the events it accepts** (a sorted list in the record; the client VM drops anything else,
   `0x461430`) - 875 / 875 lists equal the events its triggers name (C). ics delivers every event to every instance.

### Top root causes of the current skill bugs (ranked)

| # | Cause | Effect | Conf. |
|---|---|---|---|
| 1 | Code 2 is **timed** (CAST_RECOVERY 0.15 s, the tsv exit, GRAPH_EXIT_FALLBACK 3.0 s) instead of being the **exit of the graph state** | Zod R and 13 staged states end mid-channel; Batflight ends 2.4 s late; LassoGrab's exit (0.05 s) precedes its own code 5 (0.128 s) | C (Zod log, data); P per skill |
| 2 | Hooks keyed by **script DID** and flattened over **all sub-states** of the skill state, instead of by the **graph state entered** and the **sub-state reached** | stage hooks fire from the cast start; Thousand Cuts (6 states, one script) and 20 multi-state basics fall back to fixed timings | C |
| 3 | No graph state: interrupts (stun, death, a new skill's start) never produce the code 2 the scripts rely on; ics substitutes 0x10000009 from its own code | skills keep running / end late after CC | P |
| 4 | Gate events raised by scriptlets / native code are not emulated (Doomsday Charge _Grab / _End, WW LassoGrab_Hit, NC Rip&Tear_Hit, Speed_Of_Mercury_End, CbtState_GetHit) and attach results (0x10000022 / 0x10000014) are guessed | second stages never run | C list, P sources |
| 5 | Client events dropped (`skill_client_events` false) and **no accept filter** | Green Arrow R, Deadshot R, Dex-Starr W never see the press (0x10000023); GA R never sees the cancel | C |
| 6 | Attack-speed scaling only for "speed-bound" rows and not for multi-state basics; bots' AS property out of step with their cadence | projectile leaves before / after the throw | C (deep-scan-animations.md 5) |
| 7 | Super Strength: fake `raise_event_follow {0x10000037: [0x100000BB, 1.2]}`, synthesized signals | car / rubble timing invented; the sub-skill's own 0x100000BB arrives twice when both run | C |

---------------------------------------------------------------------------------------------------------------------

## 1. Client order to server

### 1.1 Path (C unless marked; addresses VA)

```
key down / click ── 0xA85DA0 (agent, slot, pressed, released, smartcast...) ── CanActivate 0x8709E0 (13 tests,
  │                                                                               full-combat-skills.md 1.3)
  │  targeting type 0x1000003D (0x85F6F0)
  ├─ 5 / 7 (instant) ───────────────────────────────────────────────► order API 0xA70030 ─► 0x20EE
  └─ 1/10/11/13/14/16 ─► 0xA26420 enter targeting:
        +0xEC = slot, +0xF8 = now, +0xF0 = now + stat[skill prop 0x10000BF5] (auto-release, 0x874B80)
        0xA23510(agent, slot, &0x10000023, params{SkillSlot 0x31D944 = slot}) ─► 0x20EA (sent WITHOUT params)
                                                                            └─► client targeting script (local)
        second click 0xA75D20 / ground 0xA70600 / key release (0xA8A270, skills with 0x10000A33)
        / deadline (+0xF0 <= now, HUD tick 0xA8B0B0 -> 0xA76320) ─► 0xA70030 ─► 0x20EE
        cancel (another slot, Esc, death 0xA33C90, stun-like 0x10000B2D, right click):
            skill bool 0x10000A46 (0x8618A0) ? 0xA23510(.., &0x10000009) = 0x20EA + local : 0xA171D0 (local only)
```

### 1.2 0x20EA fully decoded (C)

* Body: `u32 slot | u32 count | u32 event class (1) | u32 event id | u8 has-params (0)`, the ScriptEvent form of
  0x20C9 (targeting-indicator-and-structures.md 1d). Sender `0x88B280` (event 0x20EA); the only caller is
  `0xA23510`, which builds the event (TLS alloc, `0x460750`), **sends it before attaching the parameters**
  (`0x88B280` then `0x460C10(params)`), then posts it locally with `0xA16E60` -> `0x96DED0` to the slot's
  `0x1000063A` targeting-script instance. Event constants: `0x16016B4 = 0x10000009`, `0x16016B8 = 0x10000023`.
* **Only two events exist**:
  - **0x10000023 "targeting begun"**: from `0xA26420` for every slot that enters targeting (not instant types 5 /
    7). Sent unconditionally, also by smart-cast (the 0x20EA came 6 ms before the 0x20EE in the 2026-10-23 log).
  - **0x10000009 "targeting cancelled"**: from `0xA33AC0`, `0xA33C90` (LifeState / 0x10000B2D listener),
    `0xA70030`, `0xA70600`, `0xA85DA0` (3 sites), `0xA8A270`, `0xA8B0B0`, sent **only if the skill bool 0x10000A46
    is set** (`0x8618A0` -> `0x860550(.., 0x10000A46, default 0)`); otherwise posted locally only (`0xA171D0`).
* There is no "release" or "hook" event: a release is the 0x20EE order itself.
* Skills that carry the flags (all skill records, C):

| Champion / slot | Cast script (0x10000328) | Targeting script (0x1000063A) | Type | Flags | What the server script does with 0x10000023 |
|---|---|---|---|---|---|
| Green Arrow R (0x48000A27, slot 4) | `0x3400040C` Bullseye | `0x34000438` | 13 | **0x10000A46 = 1** (cancel sent), 0x10000A33 (cast on release) | `T4 S0 -> S1 on (0x1000001D or 0x10000023) and HoldsActionLock` (start drawing on press), `T9 S0 -> S5 on 0x10000023` |
| Deadshot R (0x480010C6, slot 4) | `0x34000694` One Shot One Kill | `0x340001A8` | 13 | **0x10000BF5 = 19** (auto-release after skill stat 19) | `T6 S0 -> S8 on OnEvent 0x10000023`, `T10 S0 -> S7 on 0x10000023`, fire on 0x1000001D |
| Dex-Starr W (0x480010EF, slot 2) | `0x340006B7` Dash_W | `0x34000735` | 1 | 0x10000A33 (cast on release) | `T6 S0 -> S1 on 0x1000001D or 0x10000023` |

  Other server scripts that accept 0x10000023: `0x34000217` (Flash R: `S3 -> S4` on 0x1000001D or 0x10000023),
  `0x340003D8` (graph S1), `0x34000162` (an object script; raised by 0x34000161 / 16C / 177 RaiseEvent, not the
  client). The 5 targeting scripts `0x3400019E / 1A8 / 20B / 438 / 735` are client-side only. (C)
* **What the original server did with it (P)**: raised it on the slot's cast script; the record's accept list (6)
  drops it for every other script. ics' 2026-10-23 regression ("Batman lost animations") is not explained by
  0x10000023 itself: a NullWorld run of `0x3400003B` with three 0x10000023 deliveries gives the identical 48-line
  trace (C, `skillexec` run); the same build also changed `_missile_hits` (CHANGELOG fase3-gw).

### 1.3 What each side decides

| Decision | Client | Server (original) |
|---|---|---|
| Cooldown, cost, rank, alive, silence / stun / root, disable conditions, NoMutex | CanActivate refuses locally, shows the error, sends nothing (C) | validates again from its own state; mirrors via 0x20F8 / 0x20A0 / 0x207B / 0x20DC (C formats) |
| Range | none for unit targets; type 10 point = caster + dir x stat 0x17 + radius, type 11 clamped point (C) | moves the champion into range before raising 0x1000001D (P: no script checks the cast range; `IsInRangeAndAngle` appears only in melee / pickup branches) |
| Facing | none | `FaceTarget` / `ReleaseFacing` nodes, replicated by the movement block (C nodes, P wire) |
| Queueing the next order | buffers orders while its own lock `[+0x70]` is held or stunned (`0x863860`, C); NoMutex unless skill bool 0x10000704 (default true = may queue) | 64 transitions start only if `HoldsActionLock` (owner GUID null or this instance, BeginSkill / EndSkill) (C); the order is held and re-delivered when EndSkill frees the lock (P) |
| Second press / recast | a normal order (the slot is usable because the script set `SetSkillUsableOverride` / a micro cooldown, e.g. Zod R S1) (C) | delivers 0x1000001D to the **running** instance, whose current state has a transition on it (Zod R `T7 S1 -> S2`) (C script) |
| Cancel by movement | a move order is a 0x20EE (cmd 3 / 4) | no skill state has an early-out (388 / 389 have no Lua at all; only Batman `Martial_Arts` runs `onSkillEarlyOut`, C); moving cancels only the **cosmetic tail** after code 2 (`onCosmeticEarlyOut`: Propel >= 1 or Turn != 0). P: during the skill state the server ignored / buffered moves while the action lock was held |
| Cancel by CC / death / new skill | - | the graph leaves the state -> exit hook code 2 (3.4) (C data, P server) |
| Double-press filter | 0.5 s only for vector targeting (type 16) starts (`0xA70600`, C) | - |

---------------------------------------------------------------------------------------------------------------------

## 2. Who produces the cast signals

### 2.1 The hook payload (C)

hkClass `turbineEventHookPayload` (class `0x1D09950`, vtable `0x1805B20`, ctor `0x1173210` sets **`+8 = 0x10000001`**,
the payload kind). Members (hkClassMember table `0x1B4F938`): `pTargetHFSM` @0x10, **`didTargetHFSM` @0x14** (u32),
**`eEventHookType` @0x18** (enum), **`vMissileOffset` @0x20** (vec4). Enum items at `0x18055B0`: **Undef 0, SkillStart 1,
SkillEnd 2, Skill 3, MissileInit 4, MissileFire 5, SkillHold 6, InitCollision 0xF0001**. Member texts (hkClass
attributes, quoted short): the DID is "The filename of the HFSM to receive this event hook"; the offset is
"Optional: The offset [X,Y,Z,0] to be used on the server to fire any missile from this skill".

### 2.2 The client pipeline (C, every address checked)

| Step | Address | What |
|---|---|---|
| install | `0x408F80` -> `0x587620(obj)` at app init | the global animation-event handler object, vtable `0x15A2A60` |
| handle | `0x878680` (vt slot 1) | `0x60FE20` (probability `+0xC` vs random(0,1) `0x50B9D0`; kinds 1 / 3 = `0x60DA20` / `0x60FAF0`), then **kind `+8 == 0x10000001` -> `0x85D5B0(entity, payload)`** |
| repack | `0x85D5B0` | {type = `+0x18`, did = `+0x14`, offset = `+0x20..0x28`} -> entity hook bus `entity+0xAC` -> `0x85B750` |
| bus | `0x85B750` -> `0x877B00` | per-type listener lists (`(type-1) * 0x10`); `switch(type) 1..6 -> listener vt+4 .. +0x18` |
| listeners | `0x9798E0` (effects component init) | `0x85D550(entity, 1..5, comp+8)`: **types 1-5 only; 6 (SkillHold) is never registered** |
| | `0xA404D0` (HUD controller, agent change) | type 1 only, handler = empty (`0x16035C8` vt+4 = `0xAB4B40` `ret`) |
| effects comp. | vt `0x16090DC` (and `0x15F970C`, a second HFSM host class) slots 1-5 = `0x973C20 / 40 / 60 / 80 / A0` | `0x9723D0(type, hook)`; slot 6 = `0xAB4B40` (no-op) |
| event | `0x9723D0` | event from template `0x10000066` (`0x460BB0(.., 0xF)`), param **`0xC58BA9B` = type**, param **`0xA2103E4` (MissileFireOffset) = offset xyz**; **DID == null -> queued on every instance (`0x461430`); else `0x96DED0(event, DID)`** (instances with that script DID) |
| consumer | OnCastSignal `0x10000019` test `0x9C21D0` | event id == r4 (`0x1000000F` in all 232 scripts) **and param hash `[0x186A6A0]` == code**; `0x186A6A0` holds **0xC58BA9B** statically: the same parameter (resolves full-combat-skills.md 1.9 "Open") |

No step sends anything to the network (C). On the client the targeted DIDs (0x10000328 cast scripts) are never
instantiated (client-skill-instances.md 2), so the hooks fall on nothing; client targeting / status instances
whose DID differs ignore them. Hence (P, strong): the server had the same handler and effects component, ran the
champion's graph, and this is how its scripts got OnCastSignal. The vMissileOffset ("on the server") feeds the
event's MissileFireOffset, which LaunchMissile reads (P).

### 2.3 Delivery rules the server must reproduce (C unless marked)

* Codes reach scripts as 1, 2, 3, 4, 5; **6 never** (not registered). Scripts wait only for **2 (227 scripts), 3 (130),
  5 (87), 4 (1: Batman R `0x34000248`)**; none waits for 1 or 6 - consistent.
* The code is the payload's type, **not the event name**: e.g. `basicattack_to_basicattack` triggers carry code 3 / 5
  (263 cases), `a_SkillEndHook` carries code 1 on Batflight_Recover's enter, `a_EventHook` carries 2 / 3 / 5
  (census of all 389 programs, `hookprog.py`).
* Routing by the payload DID; **DID 0 = broadcast** to every instance of the entity that accepts 0x1000000F (the
  Super Strength car / rubble hooks, 5.3).
* Each instance accepts only its record's event list (6); a 0x1000000F to an instance in a state with no
  OnCastSignal transition is consumed with no effect.
* Order inside one graph transition: **exit hooks of the left state (code 2) before enter hooks of the new one
  (code 1)**, then clip triggers as the clips advance (Havok state-machine semantics, P for the exact order).

### 2.4 Other C2S traffic during a cast (C)

Only `0x20EE`, `0x20EA`, `0x20AB` (hold flag 0 after a stop / cast) and the move-hold re-issue every 0.125 s
(`0xA8B0B0`, `+0x104`). `0x00DA` (networked scriptlet request, sweep-c2s.md) is the client asking to run a
networked scriptlet on an object it does not own (clip-trigger `RunScript_Vfx_*` on minions): presentation, not
cast logic (P).

---------------------------------------------------------------------------------------------------------------------

## 3. Multi-state skills

### 3.1 The graph side (C, `hookprog.json`)

389 hooked skill states in 257 scripts; **154 have nested state machines**; 41 have **gates** (a nested transition
on an event that no clip of the state raises). A skill state = `enter [code 1]`, `exit [code 2]`, a generator tree
(clips with triggers in local time / playback speed or relative to the clip end, blends, nested machines with a
start state - `hkbStateMachine +108`, P for the field - and their transitions). Self-advancing transitions:
`state_to_state`, `next_animation`, `skill_to_cosmetic`, `skill_to_locomotion`, `basicattack_to_basicattack`.

### 3.2 Worked example: Zod R Kneel Before Zod (`0x3400074B`, graph state 130) (C)

```
graph  Kneel_Before_Zod (enter 1, exit 2; leaves on skill_to_locomotion)
       SM start 0 "start channel" (loop, no hook) --Wildcard_SkillR_Secondary 0x100005D0--> 5 "jump" (state_to_state end-0.01)
       --> 3 "jump pose" (loop) --Zod_Kneel_End 0x10000580--> 1 "end": a_SkillHook 3 @0.200, skill_to_locomotion @0.356 (+ exit 2)
script S1 channel: Cast, RaiseGraphEvent Wildcard_RSkill 0x100003BF, ChannelTimer = stat 14, usable override + micro cooldown
       T0 S1 -> S5 on ChannelTimer | T7 S1 -> S2 on 0x1000001D (second press = cancel, CancelCooldown) | T4 S1,S3,S4,S5 -> S2 on code 2
       S5: StartCooldown, RaiseGraphEvent 0x100005D0 (jump), untargetable, fuse entity, FuseTimer = stat 19
       T1 S5 -> S3 on FuseTimer; S3: RaiseGraphEvent 0x10000580 (land); T5 S3 -> S4 on code 3 (damage, knockdown 0x48000296)
       code 2 (state exit at 0.356 s after the landing) -> S2: skill_to_locomotion, EndSkill
```

Right signals: code 1 at the start; **nothing** during the channel and the jump; code 3 at landing + 0.200 s; code 2 at
landing + 0.356 s. ics sends 3 at 0.33 s and 2 at 0.49 s from the start (C log 2026-10-26): T4 ends the channel.

### 3.3 Gate map (C for the census, `gates.py`; who raises = RaiseGraphEvent in which script)

* Raised by the skill's own script (39): Superman HeatVision / SpeedingBullet, WW BlockingBracers_End /
  Protection_Teleport / LassoGrab_Dash, Batman Martial_Arts_End, Dark_Knight Alt / End, Ultimate_Shazam_End,
  SpeedStorm_End, AWW StormingSmash_End / Reclaimer_End, Robin VaultKick_End, Aquaman Surge / Wrath_End, GA
  Bullseye_Fire, Blue Beetle Stick_And_Move L / R / Lethal_Measures_Hit, Sinestro CullTheWeak_End, NMR
  FeedtheBeast_End, Atrocitus Rage_Combo, the dashes' Skill_Dash_Start / End (Supergirl, Hawkgirl, Krypto, Deathstroke,
  Raven, Dex-Starr, Nightwing), Deadshot Wildcard_RSkill_End, Zod Rush_Loop_To_End (3 basic states), Zod Kneel x2.
* Raised by another script (7): AGL Grab_Hit `0x10000331` <- missile `0x340002C1` S9; GA BullseyeSuperfoam <-
  `0x3400040E`; Supergirl Comet_Grab / End <- `0x34000480`; Skill_Dash_End for Krypto Vigilance, Deathstroke Dash_Q,
  Huntress Grapple Bolt (<- their dash helper scripts) (P which one).
* **No RaiseGraphEvent anywhere (7)**: Doomsday Charge_Grab `0x10000163` / Charge_End `0x10000164`, WW LassoGrab_Hit
  `0x100001F5`, Shazam Speed_Of_Mercury_End `0x10000289`, Nightmare Catwoman Rip&Tear_Hit `0x10000577`,
  CbtState_GetHit `0x100000AC` (BlockingBracers), fidgetwing (Vampire Batman). P: raised by scriptlet keys the
  scripts run (type 0x14 actions, as `Combat_Basic_Attack` -> `Basic_Attack`) in the attach / hit states, or by the
  native hit reaction (GetHit). To confirm: list the type-0x14 actions of every key those scripts run.

### 3.4 What ends and what cancels (C graph / scripts, P server)

| End / cancel | Mechanism | Detected by |
|---|---|---|
| normal end | the state's own trigger (`skill_to_cosmetic` 133 states, `skill_to_locomotion`, named ends) -> exit code 2 | graph |
| channel end | a script timer (ChannelDuration / FuseDuration) -> RaiseGraphEvent of the next gate or of the end | script |
| tether end | missile back (0x10000005) -> script S2 raises `skill_to_locomotion` -> exit code 2 | native (missile) + script + graph |
| second press | 0x20EE -> 0x1000001D on the running instance (Zod R T7, Super Strength S3 -> throw) | server order system + script |
| stun / knock / death | status script raises `CbtState_*` / `_Defeat_OnDead` -> main-machine wildcard -> exit code 2; also 0x10000009 from DisableActions / StopAction (P) | graph (and native) |
| another skill | its start event (wildcard flags 0xE00) leaves the old state -> code 2 to the old script (if the new order got past HoldsActionLock) | graph |
| move order | not in the skill state; ends the cosmetic tail only (Lua early-out) | graph (client and server copies) |
| targeting cancel | 0x20EA 0x10000009 only for GA R; else nothing reaches the server | client |

### 3.5 Chains / toggles / holds

* **Thousand Cuts** `0x340005B6`: six graph states (`Thousand_Cuts_Start`, `_1` .. `_5`), each its own start event,
  one script; each has enter 1 / exit 2, a code 3 at 0.13-0.20 s. S8 raises the stage's start event; `T9 S8 -> S3 on
  code 3 or code 2`: the previous stage's **exit code 2 arrives at the moment the next stage starts** and moves the
  script on (C data; P that this is the intended order). Keying by script DID loses all of it (ics: fixed timing).
* **20 multi-state basic scripts** (deep-scan-animations.md 5.1 list): the state is picked by the start event
  (`Basic_Attack`, `_Critical`, `Empowered_Attack`, `*_Rush`, Katana `Quick_Draw` / `Vendetta`); each has its own hooks.
* **Held skills**: press = 0x20EA 0x10000023 (draw / aim states), release / click / deadline = 0x20EE ->
  0x1000001D (fire); GA R also cancel 0x10000009 (1.2).
* **Toggles / stances** (0x10000197 form change, `SetSlotSkill`): script-driven; the graph only plays the start
  event of the new form (C scripts).

---------------------------------------------------------------------------------------------------------------------

## 4. Basic attacks (C unless marked)

* Gaslight Batman `0x34000037`: S0 exit `CooldownDuration = 1 idiv max(GetAttribute, 0.1)` (attack speed, P which
  attribute: 0x100005FE); `0x1000001D` -> S1 Cast -> S4 (target alive): BeginSkill, StartCooldown(1/AS), FaceTarget,
  **RollCritical** -> runs `0x100000B8` (critical) or `0x10000196` / `0x10000195` (Combat_Basic_Attack_Right / Left,
  chosen by `Attack_LeftRight_Toggle`): these scriptlets raise the graph start events. Code 5 (graph) -> S2: the
  projectile scriptlet (`0x1000017E` crit / `0x10000189` / `0x10000188`) and ApplySkill 0x48000AB0; code 2 -> S3:
  cooldown bookkeeping, ReleaseFacing, EndSkill, `_Combat_GoToLocomotion` if stunned / target dead. Graph S2 waits
  `0x10000126` (projectile hit, raised by the projectile status script) -> damage.
* The graph plays the clip at `playbackSpeed <- Attribute_AttackSpeed` (Lua `onSetBasicAttackSpeed` from
  `Property_Attribute_AttackSpeed` = 0x100006FE): real hook time = local time x static speed / AS
  (deep-scan-animations.md 5.1). Left / right inside the graph: `Next_Basic_Attack` toggled by Lua
  (`onSetNextStandingAttackLeft/Right`), consistent with the script's toggle.
* Cadence: the next swing is a new 0x1000001D after the cooldown, from the server's attack order (cmd 9 / 2 on slot
  0) while the target stands (P: no script loops by itself; `QueueOrder 0x100000DB` at the end of dashes re-issues
  it). `basicattack_to_basicattack` carries the code (3 or 5) that ends the swing state; the cosmetic tail ends on
  `Combat_Locomotion` when Propel >= 1 (`onBasicAttackEarlyOut`).
* Move cancel: during the wind-up the swing state has no early-out (C); a move order before code 5 must come from the
  order system as an interrupt (0x10000009 -> `T6 any -> S3`) (P).

---------------------------------------------------------------------------------------------------------------------

## 5. Server-native glue

### 5.1 Census (C)

`evscan.py`: every event in a transition trigger or chain predicate of the 875 scripts (Event builtin, IsEventPending,
OnEvent, OnEntityEvent, OnCastSignal, OnAttributeChanged, OnCombatEventByKind, the (event, id) triggers) versus every
RaiseEvent `0x1000006B` / PostEventDelayed in any script and every raise site in `ics/`. Cross-check: each script's
record accept list (6) equals the set found, for all 875 (C). Result: **115 waited events; 79 raised by no script;
53 raised neither by a script nor by ics** (my ics grep misses raises through variables, e.g. the attach pair at
`script_nodes.py:308`, so treat "-" in the ics column as "not found").

Classes: graph-hook 1 (0x1000000F), client 1 (+ the client half of 0x10000009), native 57 (+2 with a client
mirror), script 22, unknown 31. "Waiters" = scripts, "SR" = scripts raising it; samples are the first four waiters.

| Event | Waiters | SR | ics raises at | Class | Meaning (conf.) | Sample waiters |
|---|---|---|---|---|---|---|
| `0x1000001D` | 399 | 28 | script_runtime.py:2575; world.py:1405 | native | skill used {TargetIID, TargetPosition}: the order system raises it on the slot script (0x20EE) / ActivateSlotSkill (C) | 3400000A 3400000C 34000014 34000037 |
| `0x10000008` | 357 | 3 | script_runtime.py:2546 | native | re-init family: rank / level / stats changed (P) | 3400000C 34000014 34000037 34000038 |
| `0x100001B3` | 336 | 0 | - | native | re-init family (P) | 3400000C 34000037 34000038 34000039 |
| `0x10000006` | 310 | 17 | script_runtime.py:2463 | native | status applied (start of a status script) (C) | 340000EE 340000F0 340000F1 340000F8 |
| `0x10000003` | 305 | 10 | script_runtime.py:2507 | native | status removed {ExpiredByTime, ExplicitlyRemoved} (C) | 340000C9 340000EE 340000F0 340000F1 |
| `0x10000009` | 258 | 6 | script_runtime.py:1422 | native+client | interrupt / cancel: server order system, death, EndThisScript; client 0x20EA for 0x10000A46 skills (C) | 3400000A 3400000C 34000014 34000037 |
| `0x1000000F` | 232 | 0 | inst.signal(code) (GRAPH_HOOKS / fallback) | graph-hook | OnCastSignal: turbineEventHookPayload code (1 start, 2 state exit, 3 skill, 4 missile init, 5 missile fire, 6 hold) (C) | 3400000C 34000014 34000037 34000039 |
| `0x1000000C` | 157 | 0 | - | native | re-init family (P) | 3400000C 34000037 34000039 3400003A |
| `0x10000002` | 88 | 1 | script_nodes.py:1496; script_runtime.py:538 | native | collision {Collider, SubEntity, EntityPosition} (missiles, hotspots, thrown objects) (C) | 3400000B 34000038 3400003F 34000043 |
| `0x10000049` | 78 | 0 | script_runtime.py:451; script_runtime.py:462 | native | spawned / launched (missile, spawned entity start) (C) | 3400000B 3400003F 34000042 34000043 |
| `0x1000008B` | 67 | 0 | script_nodes.py:758 | native | basic attack hit {TargetIID} (P) | 340000C7 340000E1 34000147 340001C6 |
| `0x100000A9` | 66 | 1 | world.py:2603; world.py:2628 | native | slot skill changed {SkillSlot, script} (P) | 3400000C 34000037 34000087 34000088 |
| `0x10000141` | 63 | 71 | - | script | skill-to-skill event (recasts, pets) (C) | 340000E6 34000186 3400018C 340001E5 |
| `0x100000A2` | 60 | 0 | script_runtime.py:379; world.py:2675 | native | attribute changed {attribute id} (C) | 34000087 34000088 34000161 34000164 |
| `0x10000035` | 57 | 10 | script_runtime.py:625; script_runtime.py:627 | native | missile expired (range / time) (C) | 3400003F 34000042 34000043 34000096 |
| `0x10000007` | 46 | 0 | world.py:1446; world.py:1454 | native | died {KillerIID} (C) | 3400000A 3400007D 340000EE 34000107 |
| `0x100000C5` | 44 | 0 | script_nodes.py:1536 | native | dash interrupted (C) | 34000038 340000E0 34000185 34000192 |
| `0x100000C3` | 43 | 0 | script_nodes.py:1550; script_nodes.py:1583 | native | dash failed (no path) (C) | 34000038 340000DF 340000E0 34000185 |
| `0x100000C1` | 42 | 1 | script_nodes.py:1536 | native | dash arrived (C) | 34000038 340000E0 34000185 34000192 |
| `0x100000C4` | 30 | 0 | script_nodes.py:1491 | native | dash started (C) | 34000038 340000E0 34000192 340001F8 |
| `0x100000ED` | 29 | 0 | script_nodes.py:663 | native | took damage {source} (P) | 3400000A 340000E6 340000F0 3400015A |
| `0x10000126` | 29 | 3 | - | script | basic-attack projectile hit (raised by the projectile status scripts) (C) | 34000014 34000037 34000087 3400009D |
| `0x10000140` | 24 | 25 | - | script | skill-to-skill event (passives / marks) (C) | 340002AE 340003D1 34000438 340004B7 |
| `0x100000EE` | 23 | 1 | script_runtime.py:454; script_runtime.py:463 | native | missile target {TargetIID, TargetPosition} (P) | 340002AF 340002B4 340002BE 3400035C |
| `0x1000008A` | 21 | 0 | script_nodes.py:764 | native | skill hit a target {TargetIID, slot} (P) | 340001C6 34000218 34000265 34000278 |
| `0x10000060` | 21 | 2 | - | script+native | map objective unlock (scripts raise it; encounter code too) (P) | 340001FA 340003D1 3400053A 3400058A |
| `0x10000012` | 20 | 0 | script_nodes.py:2242; world.py:1443 | native | target lost / out of range (units) (P) | 34000048 340000C9 340000E1 34000189 |
| `0x10000107` | 16 | 19 | - | script | missile-to-owner event (C) | 34000048 34000096 34000185 3400022E |
| `0x10000088` | 15 | 0 | world.py:1632 | native | home position / reset (units) (P) | 3400000A 34000014 34000162 340001A6 |
| `0x1000007C` | 15 | 0 | - | native | team member left (C params) | 34000107 340002AF 340002D1 340002D5 |
| `0x1000007B` | 15 | 0 | script_nodes.py:1851 | native | team member joined {TeamMemberIID} (TrackTeamEvents) (C params) | 34000107 340002AF 340002D1 340002D5 |
| `0x1000008C` | 14 | 0 | script_nodes.py:645 | native | damage redirect handle (P) | 340000F1 3400015A 34000191 340002BA |
| `0x10000017` | 14 | 14 | - | script | skill-to-skill (slot script) (C) | 340001FA 34000308 3400033A 3400038B |
| `0x100000B7` | 12 | 1 | - | native (+client mirror) | slot available {SkillSlot} (C) | 340000E1 3400019E 340001A3 3400020B |
| `0x10000098` | 12 | 1 | world.py:1456 | native | killing blow {victim} (P) | 340000E6 34000110 340001E5 34000243 |
| `0x10000197` | 12 | 1 | - | script | form / stance change (Shazam, Blue Beetle...) (C) | 340001F5 34000438 34000451 34000454 |
| `0x10000023` | 11 | 4 | session.ev_skill_events (off: skill_client_events false) | client | slot targeting begun (0x20EA from 0xA26420 on every non-instant slot; also the client targeting scripts) (C) | 34000162 3400019E 340001A8 3400020B |
| `0x10000192` | 11 | 0 | - | native | re-init family (same AnyOf as 0x10000008) (P) | 3400018C 34000243 34000248 340002BB |
| `0x10000016` | 10 | 0 | world.py:1661 | native | respawned (P) | 340000E1 34000107 340001E5 340002E9 |
| `0x10000097` | 10 | 0 | match\match.py:1211 | native | takedown / assist {victim} (P) | 340000E6 34000110 340001E5 34000243 |
| `0x10000196` | 10 | 0 | script_runtime.py:2579 | native | (ics: slot used broadcast) (O) | 340001E5 340001FD 34000216 34000456 |
| `0x100000A8` | 10 | 0 | script_runtime.py:2416; script_runtime.py:2495 | native | status duration changed (C) | 3400022C 3400028F 340002F3 34000320 |
| `0x10000005` | 9 | 5 | script_runtime.py:637; script_runtime.py:643 | native | tethered missile back / returned (P) | 3400000B 34000185 34000290 340002B5 |
| `0x10000022` | 9 | 0 | script_nodes.py:308 (attach result, P model) | native | attach succeeded (after SetSkillTarget + SetSkillAttached) (P) | 340000C6 340000E0 34000253 340002C1 |
| `0x10000014` | 9 | 0 | script_nodes.py:308 | native | attach failed (P) | 340000C6 340000E0 34000253 340002C1 |
| `0x100000D7` | 9 | 0 | script_runtime.py:2415 | native | stack count changed (C) | 3400022C 340002C5 34000303 34000330 |
| `0x10000105` | 8 | 1 | - | script | item / buff event (C) | 340001FA 340004F3 340004FB 340004FC |
| `0x100000B6` | 7 | 0 | - | native (+client mirror) | slot unavailable {SkillSlot} (client raises it from S->C 0x20F9) (C) | 3400019E 340001A3 340001A8 34000214 |
| `0x100000D8` | 7 | 0 | - | native | loot picked up {CurrencyAmount} (P) | 34000203 34000278 340002D6 3400037F |
| `0x100000E7` | 7 | 0 | script_nodes.py:697; match\match.py:865 | native | health changed by damage {delta, type, source} (C params) | 340002FD 340004CE 3400057A 34000583 |
| `0x10000145` | 7 | 0 | script_nodes.py:700 | native | damaged by a champion skill {source, slot} (P) | 34000318 34000357 3400040E 340004D1 |
| `0x100000AF` | 6 | 0 | - | native | skill effect applied {Slot, TargetIID, IsAOE} (P) | 34000098 34000340 34000395 3400053D |
| `0x100000A4` | 5 | 0 | - | native | re-init family (Batman E/Q, Cyborg, MWW) (P) | 34000039 3400003B 340001B7 34000236 |
| `0x10000026` | 5 | 0 | - | native | revived (P) | 34000107 340002E9 340003BE 340004A4 |
| `0x10000120` | 5 | 5 | - | script | PostEventDelayed tick (C) | 34000162 340001C4 34000347 34000598 |
| `0x1000000E` | 5 | 0 | - | native | re-init family (P) | 34000189 340001E5 34000205 34000583 |
| `0x1000014A` | 5 | 0 | - | native | item / shop event (O) | 340002E9 34000384 340004BC 340004BD |
| `0x1000011B` | 5 | 0 | script_nodes.py:651 | native | status from a source {source} (P) | 340003D1 3400041C 340004A4 340004DE |
| `0x1000005F` | 5 | 3 | - | script | pet / summon event (C) | 340003D1 3400053A 34000541 3400057A |
| `0x10000186` | 5 | 0 | - | native | encounter phase step (P) | 34000601 34000602 34000603 34000604 |
| `0x10000106` | 4 | 0 | script_runtime.py:570 | native | returning missile turned back (C) | 3400000B 340002C1 340004E3 34000743 |
| `0x10000119` | 4 | 0 | - | native | carried / grabbed target lost (P) | 340000E0 340002C1 34000480 34000743 |
| `0x10000085` | 4 | 1 | - | script | sub-skill start {ObjectIID} (Super Strength: 0x34000162 -> 0x34000161) (C) | 34000161 3400016C 34000177 340002CF |
| `0x10000149` | 4 | 0 | match\units.py:168 | unknown | map / cinematic / item script (no raiser found) (O) | 34000162 3400051A 3400051B 34000670 |
| `0x100000B3` | 4 | 0 | - | native | enemy skill blocked (spell shield) (P) | 34000202 340002E9 3400051F 34000618 |
| `0x100000D4` | 4 | 2 | - | script | turret warning (C) | 3400043D 3400043E 3400043F 34000440 |
| `0x100000EA` | 4 | 0 | - | native | healed / health up (pairs with 0x100000E7) (P) | 340004CE 3400057A 34000583 34000680 |
| `0x100000C0` | 3 | 3 | - | script | script-to-script (C) | 340001D6 340003B4 34000493 |
| `0x1000009D` | 3 | 0 | director.py:488 | unknown | missile / dash sub-step (O) | 34000253 340003D1 34000652 |
| `0x10000020` | 3 | 0 | script_nodes.py:709 | native | combat event {attacker, defender, value} (C) | 34000304 340003D1 340006C0 |
| `0x00000008` | 3 | 0 | - | unknown | event id 8 (G: a decoder artefact) (O) | 3400058A 340005DF 34000732 |
| `0x1000017F` | 3 | 0 | - | unknown | encounter scripts (O) | 34000601 34000603 34000628 |
| `0x10000068` | 2 | 0 | - | unknown | turret / teleport (O) | 3400000A 34000304 |
| `0x10000124` | 2 | 1 | - | script | explode in place (Super Strength object) (C) | 3400015F 340004F7 |
| `0x100000F0` | 2 | 0 | - | native | resource vital up (P) | 34000265 34000709 |
| `0x100000EF` | 2 | 0 | - | native | resource vital down {NewValue} (P) | 34000265 34000709 |
| `0x10000067` | 2 | 2 | - | script | tether release (AGL Grab S2 -> missile) (C) | 340002C1 34000743 |
| `0x100000A6` | 2 | 0 | - | unknown | (O) | 3400030D 340003DB |
| `0x10000032` / `0x10000036` | 2 / 2 | 0 | - | unknown | (O) | 340003B4 34000493 |
| `0x100000EB` / `0x100000E2` | 2 / 2 | 0 | - | native | Will / stat changed (P) | 34000581 34000696 |
| `0x100000CC` | 2 | 0 | - | unknown | (O) | 340005AB 340005D8 |
| `0x100000E1` | 2 | 3 | - | script | script-to-script (Lex) (C) | 340005AB 340005D8 |
| `0x1000017C`, `0x100000F1` / `F2` / `F3` | 2 each | 0 | - | unknown | cinematic scripts (O) | 340006A8 340006A9 3400076B 3400076C |
| `0x1000000A`, `0x10000171`, `0x10000118`, `0x10000108`, `0x10000148`, `0x100000BA`, `0x1000007A`, `0x10000079`, `0x10000083`, `0x10000110`, `0x1000001C`, `0x100000B2`, `0x10000143`, `0x10000193`, `0x100001B2`, `0x100000A7`, `0x10000162` | 1 each | 0 | - | unknown | map / item / cinematic scripts: 0x34000000, turret 0x34000014, Device 0x340000D5, Doomsday E 0x340000E0, liftable 0x34000162, 0x340001C6, GH cannon 0x340002CF (5), 0x340002F7, 0x3400038C, 0x34000600, 0x340007E2, 0x340007E9, 0x340007EC (O) | - |
| `0x10000028` | 1 | 0 | - | native | unit died nearby (The Joker passive) (P) | 34000110 |
| `0x10000037` | 1 | 1 | config.py:135 (raise_event_follow) | script | pickup request on a liftable (0x34000164 -> object) (C) | 34000162 |
| `0x100000BB` | 1 | 3 | config.py:135 (fake follow) | script | lift done (0x34000161 / 177 / 16C -> 0x34000164) (C) | 34000164 |
| `0x10000121`, `0x100000CB`, `0x10000053`, `0x10000090` | 1 each | 1 | - | script | script-to-script (C) | 340001BF 340003D1 34000582 |
| `0x1000011E` | 1 | 0 | - | native | owned object destroyed {DestroyedIID} (P) | 340003E6 |
| `0x100001A6` | 1 | 0 | - | native | lifesteal healed {Amount, DamageType} (P) | 34000680 |
| `0x100001A4` | 1 | 0 | - | native | crowd control applied {EffectCategory} (P) | 3400074A |

The full machine-made table (114 rows, every event on its own row) is `skillexec/table.md`; meanings of the native
families are those of skill-mechanics-recipes.md 6 where it already had them.

### 5.2 What the original server did natively (summary, P unless marked)

1. **Order system**: 0x20EE -> path into range -> 0x1000001D {TargetIID, TargetPosition} on the slot's instance;
   queue behind HoldsActionLock; re-issue basic attacks at the cooldown; interrupts (0x10000009) on a new order that
   pre-empts.
2. **Graph runtime per entity** producing 0x1000000F (2) and taking every graph event the scripts / scriptlets raise
   (C for the client copy of this machinery).
3. **Event families** of 5.1 "native": re-init on rank / level / stat change; status lifecycle; missile spawn /
   collision / expiry / return / turn-back / target; dash results; attach result and carried-lost; attribute /
   combat / damage / heal / lifesteal / vital; death / respawn / revive / kills / team tracking; slot availability
   (send 0x20F9 too, the client raises 0x100000B6 / B7 itself); encounter phases.
4. **Super Strength** (5.3): only "give the caster an instance of the sub-skill script that 0x34000162 / the pickup
   path addresses" is native.

### 5.3 Super Strength corrected (C graph + scripts)

Every champion graph has `SM_SuperStrength_Car` and `SM_SuperStrength_Rubble` (Gaslight Batman, AGL checked), with
hook payloads `(DID 0, 3)`, `(DID 0, 5)`, `(0x34000161, 2)`, `(0x34000177, 2)`:

| Sub-state | Entered by | Hooks (s) | Leaves |
|---|---|---|---|
| Car_Pickup_Start | `SuperStrength_CarPickup` from the lift scriptlets | - | on CarPickup -> Pickup |
| Car_Pickup | | **3 @0.013 (DID 0)** | state_to_state @0.375 -> Hold |
| Car_Hold | | - | `SuperStrength_PickupCar` (toss / catch) |
| Car_Throw | `ThrowObject 0x100007A0` | **5 @0.200 (DID 0)**, **2 @0.220 (0x34000161)** | skill_to_locomotion end-0.10 |
| Rubble_Pickup | | **3 @0.216**, state_to_state @0.296 with **code 2** | -> Hold |
| Rubble_Throw | | **5 @0.260**, **2 @0.280** | |

These are exactly the signals `0x34000161` (S6 -> S7 on 3, S1 -> S2 on 5, S1/S2 -> S3 on 2) and `0x34000177`
(S2 -> S3 on 3, -> S4 on 2, S5 -> S6 on 5, -> S7 on 2) wait for. `0x100000BB` (the "lift clip end") is
`RaiseEvent [0x100000BB 0x34000164]` in `0x34000161` S7 / `0x34000177` S3 / `0x3400016C`: **`raise_event_follow` is a
fake and must go** (C). The pickup handshake is scripted too: `0x34000164` S4 raises `0x10000037` on the object;
the liftable script `0x34000162` takes it (`T3 S0 -> S6`), keeps the user, and in S8 raises
**`RaiseEvent($UserIID, SELF) [0x10000085 0x34000161]`** = the sub-skill's start event (C). So the only native step
left is that the caster hosts a `0x34000161` / `0x34000177` / `0x3400016C` instance when that event arrives
(crime-alley-props.md A.3 step 2 picks the sub-skill by the object's flags; P). Open: which objects run
`0x34000162` (the vehicles / rubble of Crime Alley run 0x3400015F / 0x34000167).

---------------------------------------------------------------------------------------------------------------------

## 6. Replacement design for ics: a server-side behaviour-graph emulator (BGE)

### 6.1 Principle

Run, for every champion (and any entity whose class has a hooked graph), a reduced interpreter of its Havok
behaviour state machines, fed with **the same graph events ics already sends to the client** (0x8D type-0x14
actions, `RaiseGraphEvent` / `0x100001E3 + 0x780`, `_Defeat_*`, CC scriptlets) plus the replicated motion inputs
(Propel, Turn, AttackSpeed). Its hook events become 0x1000000F {code, MissileFireOffset} routed by payload DID. All
timed fallbacks go away for entities with a graph; entities without one (turrets, minions, missiles) keep
`cast_time()`.

### 6.2 Per-skill extraction (what tools/graph_hooks.py must output: `data/skill_graphs.json`)

Per champion graph (pack, graph name, 0x1C wrapper's local -> global event map, wrapper of `gmat.gid`):

```
{"graph": "chr_zod_behavior.hkb", "pack": "0xA0000378",
 "events": {"Wildcard_RSkill": "0x100003BF", ...},                       # names -> global ids
 "variables": {"Property_Slider_Propel": ..., "Attribute_AttackSpeed": ...},
 "machines": {"SM_Main_Machine": {"start": 0,
     "wild": [{"event": "Wildcard_RSkill", "to": 130, "flags": "0xE00", "cond": ""}, ...],
     "states": {"130": {"name": "Kneel_Before_Zod",
          "enter": [{"code": 1, "did": "0x3400074B"}], "exit": [{"code": 2, "did": "0x3400074B"}],
          "out": [{"event": "skill_to_locomotion", "to": 0}],
          "lua": [],                                                        # onCosmeticEarlyOut ...
          "body": {"clips": [{"name": ..., "anim": "chr_zod_skill_r_end.hkx", "speed": 1.0, "start": 0.0,
                              "speed_var": null, "duration": 0.57,          # see 6.4
                              "loop": false,
                              "triggers": [{"t": 0.2, "end_rel": false, "event": "a_SkillHook", "code": 3, "did": "0x3400074B"},
                                           {"t": 0.356, "event": "skill_to_locomotion"}]}],
                   "machine": "Kneel_Before_Zod StateMachine"}}}},
   "Kneel_Before_Zod StateMachine": {"start": 0, "states": {...}}}}
```

i.e. the `hookprog.json` prototype (1 MB for 257 scripts) extended to every state of the graph (locomotion,
cosmetic, CC, death states too, since exits and early-outs depend on them), plus: wildcard flags, transition
conditions (`hkbExpressionCondition` strings), the Lua callbacks per state, the variable bindings (`playbackSpeed
<- Attribute_AttackSpeed` / `AnimationSpeedMultiplier`), clip loop mode and clip durations. Keep the old
`skill_hooks.tsv` for diffing.

### 6.3 Runtime algorithm (per entity)

```
GraphInstance(entity, graph):
  active = path of (machine, state) from SM_Main_Machine's start down through nested start states
  raise(event):                                  # from World.run_scriptlet type-0x14 actions / RaiseGraphEvent
      if event not in graph.events: drop          # same -1 rule as the client (0x55AF83)
      for machine in active (outermost first):   # wildcard: main-machine flags 0x400 / 0x800 / 0x200
          t = match(machine.current.out + machine.wild, event, conditions on variables)
          if t: transition(machine, t); break
  transition(machine, t):
      for st in states being left, innermost first: fire(st.exit hooks)          # code 2 here, whatever the cause
      set new state; enter nested start states; for each entered: fire(enter hooks); start its clips at local 0
  tick(dt):                                       # server tick, also called at each hook time (exact scheduling)
      for each active clip: local += dt * speed(clip)      # speed = static x bound variable (attack speed)
          for each trigger crossed (t or duration - t): if trigger.code: fire(hook); else raise(trigger.event)
      run Lua emulation for active script generators: onCosmeticEarlyOut / onSkillEarlyOut / onBasicAttackEarlyOut /
          onHandleEventCosmeticEnabled (Propel / Turn thresholds, 3.4), fidget / emote ones ignored
  fire(hook): ev 0x1000000F {0xC58BA9B: code, 0xA2103E4: offset}
      if code == 6: drop                              # never delivered (2.2)
      targets = instances on entity with script.did == hook.did, or all instances if did == 0
      for inst in targets: if 0x1000000F in inst.accept: inst.event(...)   # 6.5
```

Rules: hooks fire in the same server tick order as the transition (exit before enter); a clip that loops keeps
looping until a gate event; a state whose body never self-exits waits for its script; the main-machine wildcards
mean CC / death / another skill start produce code 2 for the running skill automatically.

What it replaces in ics: `start_cast` / `_graph_cast`, `CAST_RECOVERY`, `GRAPH_EXIT_FALLBACK`, `CAST_WAITS_TETHER`
(the graph waits by itself), `GRAPH_HOOK_OFFSET` (hooks are timed from the server's own graph event, not from the
client), `raise_event_follow`, `super_strength_cast_signals`, `keep_cosmetic_tail` (the BGE knows whether the
cosmetic state is active; whether the script's `skill_to_locomotion` after code 2 should cut it is then a single
explicit rule, P that the original did cut it, 8), and the per-script `HOOKS_ATTACK_SPEED` special case.
`inst.signal(code)` stays as the delivery primitive (fallback entities).

### 6.4 Clip durations (needed for end-relative triggers, loops, Zod's jump, Batflight Recover)

The graph names clips by `animationName` (e.g. `chr_zod_skill_r_jump.hkx`); `hkbCharacterStringData.animationNames`
is empty in the shipped data and the name table has no animation names (C), so the link name -> 0x1A clip DID ->
duration (`uesrv.havok_anim.clip_table`) is made at run time by the client loader (diag `--anims`, rva 0x899EA5).
Options, in order: (a) one `tools\diag.py --anims` session per champion (tools/anim_names.py already matches the
signatures, --write stores them in the catalog); (b) RE the loader around VA 0xC99DE0 (not in functions.tsv) to see
whether the name is hashed to the DID; (c) until then, use the trigger times that are absolute and mark end-relative
triggers "unknown" (the BGE then waits for the next event; never invents a time). Affected skill timing today:
Batflight code 2, Zod jump (fuse decides anyway), Super Strength throw tail, cosmetic tail ends.

### 6.5 Script-side changes that go with it

* **Accept filter**: `Instance.event` drops ids not in the record's list (top-level field `0x44AF56` count +
  `0x44AFBF` values in `data/script_trees`; equal to the trigger set for all 875, C). This also makes 0x20EA safe.
* Re-enable `skill_client_events`, delivering 0x10000023 / 0x10000009 from 0x20EA to the slot's cast script only.
* Second presses: deliver 0x1000001D to the running instance when its active state has a transition on it (already
  `recast_while_waiting`); refuse otherwise with the script's own cooldown, not a separate one.
* `HoldsActionLock` / `BeginSkill` / `EndSkill` as a real per-agent lock, and an order queue in `World.cast` that
  re-delivers when the lock clears (P semantics).

### 6.6 Headless validation (tools/champion_check.py)

1. **Expected sequences from the data alone**: for each (champion, slot) run the BGE without scripts, feeding the
   start event and, at each gate, the gate event the script raises (from `gates.py`: own / other script), and record
   `[(t, code, did, graph state)]`. Examples (C from the data, t from the start event):
   - Gaslight Batman Q `0x3400003B` (clip x1.25, times already real): (0, 1), (0.128, 5), (0.144, 2 = exit on
     `skill_to_cosmetic`); cosmetic state 110 after.
   - Gaslight Batman basic at AS 1.627: (0, 1), (0.031, 6 dropped), (0.147, 5), exit 2 with `basicattack_to_basicattack`.
   - Zod R: (0, 1); gate 0x100005D0 at the channel timer; gate 0x10000580 at the fuse; (+0.200, 3); (+0.356, 2).
   - AGL Grab `0x340002B5`: (0, 1), (0.14, 5), loop until `Grab_Hit` (missile S9), then end clip, 2 only on
     `skill_to_locomotion` from the script's S2.
   - Thousand Cuts: per stage (0, 2 of the previous stage), (0, 1), (0.13-0.20, 3).
   - Super Strength car: Pickup 3 @0.013 (broadcast), Throw 5 @0.200, 2 @0.220.
2. **Full run** (today's champion_check harness): log every 0x1000000F delivered (time, code, receiving script,
   script state before / after) and every graph event raised; compare with (1): same codes in the same order,
   times within one tick (0.05 s), **no code 2 before the last gate**, every gate in (1) raised, and the script
   back in its idle state with EndSkill called. New verdict columns: `SIG` (sequence mismatch), `GATE` (gate never
   raised), `HANG` (script not idle after the window), `EARLY2`.
3. Unit tests: a `tests/test_graph.py` with Zod R, Thousand Cuts, the basic attack at two attack speeds, a stun in
   the middle of Bat Scream (expects code 2 at the stun), Super Strength, and the accept filter.
4. Side finding (C, run): `python -m ics.script_runtime` with GRAPH_HOOKS loaded crashes in `_graph_cast`
   (`inst.owner.__dict__` on the NullWorld's str owner); the BGE harness must not depend on real entities.

---------------------------------------------------------------------------------------------------------------------

## 7. Implementation plan (ordered)

1. `tools/graph_hooks.py` -> `data/skill_graphs.json` (6.2) for all 54 graphs (+ costume graphs), keeping the tsv.
   Add `tools/graph_gates.py` output (gate -> raiser) into the same file. (No behaviour change.)
2. Accept filter in `Instance.event` from the record list; `[ics] script_accept_filter = true`.
3. `ics/graph.py` BGE (6.3) with a unit test file; durations unknown -> end-relative triggers off (6.4).
4. Wire it: `World` keeps a GraphInstance per champion / bot; `CastWorld.run_scriptlet` / `_raise_graph_event` feed
   it the type-0x14 events of the keys they send (the same table lookup that builds the 0x8D); movement feeds
   Propel / Turn; the 0x100006FE value feeds AttackSpeed. `start_cast` -> no timers when the owner has a graph.
   `[ics] graph_runtime = true` (false = today's GRAPH_HOOKS path).
5. Remove the fakes for graph owners: `raise_event_follow`, `super_strength_cast_signals`, GRAPH_EXIT_FALLBACK,
   CAST_RECOVERY, CAST_WAITS_TETHER, GRAPH_HOOK_OFFSET (keys stay, defaults off for graph owners).
6. `skill_client_events = true` with the filter; 0x20F9 + 0x100000B6 / B7 on availability changes.
7. Action lock + order queue (BeginSkill / EndSkill / HoldsActionLock), interrupts on pre-empting orders; bots use
   the same path (fixes deep-scan-animations.md 5.3 / 5.4).
8. Gates without a raiser (3.3 "none"): read the type-0x14 actions of every scriptlet key those scripts run; the
   rest native (attach result 0x10000022 / 14 from `SetSkillAttached` success, GetHit on damage while blocking).
9. Super Strength: create the sub-skill instance on the caster when `0x34000164` raises 0x10000037 (or when the
   object's 0x34000162 raises 0x10000085), drop the follow.
10. champion_check: sequence mode (6.6), then the tester.
11. Clip durations (6.4 a) for end-relative triggers; enable them in the BGE.

---------------------------------------------------------------------------------------------------------------------

## 8. Corrections to earlier notes

| Note | Said | Now |
|---|---|---|
| animation-deep-scan.md 3, deep-scan-animations.md 4 | "turbineEventHookPayload has no reader; the client does not turn hooks into script signals" | it does: payload kind 0x10000001 (ctor `0x1173210`) -> `0x878680` -> `0x85D5B0` -> hook bus -> `0x9723D0` -> event 0x1000000F to the instance by DID. The client simply hosts no cast-script instances (C) |
| full-combat-skills.md 1.9 | OnCastSignal parameter hash `[0x186A6A0]` set at run time | static **0xC58BA9B**, the parameter `0x9723D0` writes (C) |
| animation-deep-scan.md 2, deep-scan-animations.md 5.2 | Batflight's code 2 is Recover's enter hook (~0.61 s) | Recover's enter payload is **code 1**; code 2 is the BatFlight state's exit (`skill_to_locomotion` at Recover end-0.20) (C) |
| crime-alley-props.md A.3, ics `raise_event_follow` | the lift end 0x100000BB and the sub-skill signals are native | 0x100000BB is raised by the sub-skill scripts; the signals are graph hooks in SM_SuperStrength_*; `0x34000162` handles 0x10000037 and raises 0x10000085 for 0x34000161 (C) |
| network_events.tsv / ics session 0x20EA | "from 0xA85DA0 for skills with 0x10000A46" | 0x10000023 from `0xA26420` for every slot entering targeting; only the cancel 0x10000009 depends on 0x10000A46 (C) |
| animation-deep-scan.md 2.1 | codes from `a_SkillHook` = 3, `a_MissileFireHook` = 5 ... by name | codes come from the payload; names do not determine them (2.3) (C) |

Open (P/O): the server's exact rule for the script's own `skill_to_locomotion` after code 2 in cosmetic states (cut
or not); who held move orders during the skill state; RaiseEvent's third / fourth values (`[ev, did, 1, 0]` in 58
calls, `[ev, did, 1, 1]` in 6, `reflags.py`); `hkbStateMachine +108` as the start state id (consistent on AGL /
Batman / Zod, P); which objects run `0x34000162`.

diag probes to confirm on the client (rva = VA - 0x400000): rva `0x5723D0` (`0x9723D0`: `[esp+4]` code,
`[[esp+8]+0x10]` DID) and rva `0x45D5B0` (`0x85D5B0`: `[[esp+8]+0x14]` DID, `[[esp+8]+0x18]` type) log every hook the
client's own graph fires, with its time, for every visible champion: the reference sequences for 6.6 straight from the
game (the client runs the same graphs on the events the server sends).
