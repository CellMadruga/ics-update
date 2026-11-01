# Atomic Green Lantern R "Meltdown" against a moving target (2026-10-28, fase3-if investigation)

Tester report 2026-10-28 15:00 (run 14:39-15:00, Crime Alley v AI, AGL costume `0x4000080C` vs bot Atomic Wonder Woman
`0x400003EC`): a Meltdown hit should slow the enemy, but when the enemy moves after the hit the "waves" stop hitting it
and the effect is cut; every pulse should land and slow in the area even while the target moves.

Evidence: `logs/server.log`, `logs/traffic.log` of that run (the only R cast: 14:52:10.333), the script trees
(`ics.script_model`), the packs (`ics.gamedata`), the client decompilation (`re-work/decomp`, exe VA, base 0x400000),
and headless runs of the real server code (`World` + `CastWorld` + the script VM, the harness of
`tools/champion_check.py`, virtual clock). Tags: **C** confirmed (code / data / log bytes / headless run), **P**
probable, **O** open. Earlier work: `agl-e-r.md` (2026-10-25: the passive re-entry loop, fixed by
`exit_chain_reentry_guard`), `skill-second-stages.md` 5, `test-2026-10-25-1928.md` AGL-3, `test-2026-10-25-2207.md` AGL-4.

## 0. Short version

Movement itself stops nothing in ics: the status rides on the target and every pulse is centred on the target's current
position (C). What breaks Meltdown is:

1. **C - the projectile cannot land on a moving (or not adjacent) target.** The missile script re-sets its speed every
   0.3 s (speed boost 4 -> 15 m/s over 5 s); each `SetMissileVelocity` re-aims the server missile from its *launch
   point* (`Missile.pos` is never advanced), so the arrival keeps being postponed. Headless: target standing 4.5 m away
   -> hit after **4.8 s** (the object reached it at 1.2 s); target walking -> **never hit** in 9 s (chase timer 6 s).
   On screen: the orb sticks to the enemy, no waves at all.
2. **C - the status script acts for its owner (the victim) instead of its EffectSource (AGL).** `Instance.source()`
   returns the owner for status instances, so in `0x340002BF`: (a) each pulse's area damage (FindTargets, relation 3)
   hits **AGL's side** instead of the victim's allies (live: `Atomic Green Lantern takes 21.5054` at 14:52:10.712);
   (b) the pulse damage is credited to the victim itself, so AGL's passive never gets its skill-hit event: **no Rad
   stack, no Radiation Sickness, no slow**, no kill / assist / XP for AGL; (c) when the jump rule holds, the jump
   candidates are AGL's side (best = AGL, a champion gets +101), and the jump missile's shooter is the victim: its
   stats come from the victim's slot 4 (ChaseDuration 0 -> destroyed at once) and its hit event would go to the
   victim's (absent) `0x340002B4`. **Meltdown ends after one pulse.**
3. **C - in the tester's run the jump rule held at the first pulse**: AWW already had 3 Rad stacks (traffic 14:52:09.708
   / .718 / .922), two of them from **one** Scorched Earth hit, because the passive's two `TargetIID` locals (operand
   source 3 and 5, different blocks in the client VM) share one slot in ics: a skill hit also fires the charged
   basic-attack proc.
4. **C (headless) / P (order)** the passive's stack must arrive after the status' chain (queued event) or Meltdown jumps
   one pulse early and the victim never gets its Sickness (the slow) from Meltdown.
5. **C (headless)** the event loop guard (more than 4 of one event in 20 ms) drops the skill-hit events of the 5th and
   later victims of one pulse: no stack for them.
6. **C (headless) / P (VM rule)** a status that removes itself stops its chain at once in ics; Meltdown's jump pulse then
   skips `RaiseEvent 0x10000006` (PulsesRemaining - 1): 7 pulses in all after a jump instead of 6.
7. **P (systemic, another agent)** the victim's own full bundles while it walks (bots get one per motion change,
   `bot_motion_only` false) may drop the persistent target orb `0x10000889` on the client.

Also C: there is **no hotspot or aura** anywhere in the chain (`hotspot_follows_position` is irrelevant here), and the
**165-damage hits** in the log are the mid t1 turret (shots 10.939 / 11.971 / 12.982, AWW takes 165 at 11.078 /
12.085), not Meltdown (a pulse is 30 base, 22.01 on AWW).

All of 1-6 fixed as monkeypatches in a headless run (section 5): the missile lands in 1.0 s (standing) / 1.8 s
(walking), all 6 pulses land on the walking bot, AGL takes no damage, the bot gets Rad stacks, Sickness and the -40 %
slow (`0x20F0 0x100005E4 op 10 = -0.4`, bot speed 3.9 -> 2.34), and with enemy minions near the victim it jumps to the
nearest one from the victim's position with the remaining pulses. The 54-champion check with the same patches: 13 slot
verdicts better (status damage now counted for the caster), no category lower, sequence verdicts identical.

## 1. The data chain (C, script trees and records)

### 1.1 Stats (`0x480007A2:4`, catalog skills.tsv; passive `0x480007A2:5`)

| Stat | Meltdown | Passive Radiation Sickness |
|---|---|---|
| 5 Damage | 30 (+15/rank) per pulse | - |
| 14 | StartingPulseCount 6 | RadDuration 6 s |
| 19 | PulseDuration 1 s | SicknessDuration 3 s |
| 17 / 23 | PulseRange 2.25 m / JumpRange 4 m | - |
| 18 | range 6 (missile SkillRangePlus = 6 x 3.5 = 21 m) | - |
| 30 / 33 / 4 / 21 | MinSpeed 4, MaxSpeed 15, BoostLifetime 5 s, ChaseDuration 6 s | - |
| 12 | - | MaxStacks 4 |
| 9 / 1 / 15 | - | SlowAmount -0.4, DamageTotal 40 (+40/rank), proc cooldown 4 s |
| 15 | cooldown 120 s | |

Status records (read by kind, `ics.gamedata.Data.record`): `0x480007AF` {0x1000062D 8, max stacks 0x10000063 = 1,
flags 0x10000334 = 0x4010, script 0x10000242 = `0x340002BF`}; `0x480007BC` Sickness {max 10, flags 0x4010, script
`0x340002C6`}; `0x480007B6` Rad stack {0x10000600 1, max 10, flags 0xC000, script `0x340002C5`}.

### 1.2 R script `0x340002B4`
- Graph S1: S1 Cast + FaceTarget + graph event `0x1000032E` + scriptlet `0x10000894` (Vfx_Atm_Glt_Meltdown); cast point
  (code 5) -> S3: StartCooldown, SpendCost, **LaunchMissile `0x40000484`** at TargetIID with MissileVelocity,
  PulsesRemaining = int(StartingPulseCount), scriptlet `0x10000AA4` (Meltdown_Shard) on AGL; code 2 -> S2
  (RaiseGraphEvent `0x10000002`, EndSkill).
- Graph S2: `S0 -> S1 on 0x100000EE` (missile hit): MissileTarget = param 0x9A6A765, AdjustedEffectDuration =
  PulseDuration x PulsesRemaining, if > 0 **ApplySkill `0x480007AF`** (target, duration); `S0 -> S2 on 0x10000006`:
  PulsesRemaining -= 1.

### 1.3 Missile `0x40000484`, script `0x340002BE` (world state `0x2E000C08`, tables `0x1D000456` + `0x1D0003D5`)
- S0 -> S5 on spawn `0x10000049`: `LoadSkillStats($ShooterIID, SkillRangePlus, ChaseDuration, MinSpeed, BoostLifetime,
  MaxSpeed) [5 18 21 30 4 33 4]` (**slot 4 of the shooter**), SkillRangePlus x 3.5, ChaseTimer, SpeedBoostTimer
  (SpeedBoostDuration, server default block: 0.3 s, C headless), MissileStartTime.
- S3 chase. **T0 S3 -> S2** = AnyOf(AllOf(TargetIID != 0, AnyOf(NOT IsInRangeAndAngle(-, SkillRangePlus, -, Target,
  SELF)[1 1], NOT IsAlive(Target))), TimerExpired(ChaseTimer)). **T1 S3 -> S7** on TimerExpired(SpeedBoostTimer):
  NewSpeed = Min + (Max - Min) x elapsed / BoostLifetime, **SetMissileVelocity(NewSpeed)**, restart the timer while
  elapsed < BoostLifetime; S7 -> S3.
- S3 -> S4 on collision `0x10000002` (Collider), S4 -> S1 when Collider == TargetIID; **S1**: if AllOf(IsAlive(Target),
  CheckRelation(Shooter, Target)[3], IsKind(Target)[0x10108]): **RaiseEvent($ShooterIID, $TargetIID)[0x100000EE ->
  0x340002B4]**, hit FX (`0x10000223` with fx `0x1E000268`), `Vfx_OnCollision 0x10000016` {0x10000030 = Target}.
  S1 -> S2: `RunScriptlet($ShooterIID)[0x10000039]`, DestroyEntity(SELF, 0.5 s).
- Table `0x1D0003D5` body at pack `0xA0000150` @0x3413C: keys _Entity_OnEnterWorld_Default, Vfx_Active (particle
  `0x1800076F`, sounds), Vfx_OnCollision; one `18 18 1 3 100004E2` binding (an action aimed at the creator).

### 1.4 Status script `0x340002BF` (on the victim)
- Enter S1: EffectSource / EffectDuration from the 0x10000006 parameters; `LoadSkillStats($EffectSource, Damage,
  PulseRange, PulseDuration, JumpRange, MissileVelocity) [5 5 17 19 23 30 4]`; `LoadSkillStats($EffectSource,
  MaxRadStacks) [1 12 5]`; NumRemainingPulses = int(EffectDuration / PulseDuration); icon `0x480007B1` (stacks =
  pulses left); FX `0x10000223`/`0x1E000268`; **StartScriptlet(SELF) `0x10000889`** Vfx_Atm_Glt_Meltdown_Tgt_Active
  {0x10000402 = EffectSource, 0x1000050A = `0x1E000266`} (the orb on the victim).
- Update (every tick), pseudo-code (IfThenElse / While slots decoded with `script_runtime._subs_by_kind`):

```
if TimerExpired(PulseTimer):                                  # unset at entry: first pulse at once
    DamageSuccess = ApplyDamage(Damage, SELF)                 # source operand unset
    if DamageSuccess or not X(SELF):                          # X = node 0x1000016F (O; ics: IsInFront, true here)
        fx 0x10000223 / 0x1E000267 on SELF                    # the "wave"
        StartTimer(PulseTimer, PulseDuration); ClearList
        FindTargets(PulseRange)[add radius 1, shape 1, kinds 0x10108, relation 3, max 12, sort 0, self 0]
        DestructionImpulse(PulseRange)
        for each detected T: ApplyDamage(Damage, T); AddToList(T)
        NumRemainingPulses -= 1
        if NumRemainingPulses > 0:
            UpdateStatusIcon(NumRemainingPulses)
            RadStackCount = GetStackCount(SELF, 0x480007B6)
            if HasStatus(SELF, 0x480007BC) or RadStackCount == int(MaxRadStacks) - 1:        # the jump rule
                FindTargets(JumpRange) (same flags)
                best = argmax over T with NOT HasStatus(T, 0x480007BC) and
                       (GetStackCount(T, 0x480007B6) < MaxRadStacks - 1 or NOT IsInList(T)):
                       1 / max(dist(SELF, T), 0.01) (+101 if IsKind(T)[8] champion)
                if EntityExists(best): LaunchMissile(-, best, -, MissileVelocity)[0x40000484]; RemoveStatus()
            RaiseEvent(EffectSource, SELF)[0x10000006 -> 0x340002B4]                       # PulsesRemaining - 1
        else: RemoveStatus()
    else: PulseTimer = -1; RemoveStatus(); node 0x10000151
```

- Exit: RemoveStatusIcon, StopScriptlet(orb), and **if NOT IsAlive(SELF) and NumRemainingPulses > 0 and
  DamageSuccess**: the same jump search (non-sick +202, champion +101, nearest) and LaunchMissile (no RemoveStatus).
- Transitions: T1 `S0 -> S1 on 0x10000006` (applied), T0 `S1 -> S0 on 0x10000003` (removed), T2 `S1 -> S0 on
  0x10000006`.
- Design (the skill's tooltip, paraphrased): it sticks to the target and pulses once a second; each pulse damages and
  gives Radiation Sickness stacks in an area; it moves to a nearby enemy when the target dies or reaches four stacks;
  it lasts stat 14 pulses. The jump test runs **before** the pulse's own stack lands (int(MaxRadStacks) - 1 = 3): with
  stacks as queued events the 4th pulse makes the victim sick and moves Meltdown on (P, see 3.4).

### 1.5 The slow (C)
Meltdown has no slow node: the slow is the passive's Sickness. Passive `0x340002B3` graph S1 applies one stack on
`0x1000001D` (raised by its own basic-attack proc and by Shards of Will) or **`0x1000008A` (skill hit, TargetIID)**:
if NOT HasStatus(T, Sickness): (stacks + 1 < MaxStacks) ? ApplySkill(0x480007B6, RadDuration) : (RemoveStatus(stacks) +
ApplySkill(0x480007BC, SicknessDuration)). Sickness `0x340002C6`: icon `0x480007BE`, FX `0x1E000269`, StartScriptlet
`0x10000892` (Vfx_Atm_Glt_Rads_Tgt_Sickness_Active, fx `0x1E000260`), DoT StartVitalOverTime(DamageTotal /
duration), **ApplySkill(SELF) `0x48000294`** -> `0x34000134`: AddAttributeModifier `0x100005E4` (move speed) op 10 by
SlowAmount (-0.4), icon `0x48000536`, `0x100003CC` Vfx_Status_Slow_Active. So a pulse slows only through the passive,
which needs the pulse's damage to be AGL's skill damage (0x1000008A with slot 4).

### 1.6 No hotspot (C)
No CreateHotspot / CreateAura / DestroyHotspot / ResizeHotspot node in `0x340002B4`, `0x340002BE`, `0x340002BF`,
`0x340002C6`, `0x34000134` or `0x340002B3`. The pulse area is a FindTargets centred on the status owner (operand 6
unset) at each pulse.

## 2. The tester's run (C, logs)

| Time | Source | What |
|---|---|---|
| 09.698-09.720 | server.log 28441-28465 | W hits AWW (29.7); passive `S0 -> S3 (T1)` (0x1000008A, stack 1) then graph S2 `S1 -> S2 (T2)` (the proc, TargetIID aliased) -> `S0 -> S2 (T0)` (stack 2); traffic 158728 / 158765 `0x1000088E`, `0x1000088F` |
| 09.917-09.922 | 28535-28543, traffic 159157 | Shards' 0x1000001D: stack 3 (`0x10000893`) |
| 10.333 | 28591 | `casts Meltdown ... on AI: Atomic Wonder Woman` (she had Vaulted onto AGL at 10.407 / strike 10.498) |
| 10.478 | traffic 159520 | missile created, creator 0x100004E2 = `02 00 00 00 00 00 00 02` (AGL), at (63.13, 78.33) |
| 10.564-10.590 | 28667-28675 | hit (`S3 -> S4 -> S1`), status `0x340002BF S0 -> S1` (0.086 s flight: she was adjacent) |
| 10.591-10.593 | traffic 159590-159608 | icon `0x480007B1`; `0x10000889` (63 B, run 6194, {0x10000402 = AGL, 0x1000050A = 0x1E000266}) |
| 10.707 | 28685 | pulse 1: `AI: Atomic Wonder Woman takes 22.0103` |
| 10.712 | 28687 | **`Atomic Green Lantern takes 21.5054`** (the pulse's area, relation from AWW) |
| 10.714 | traffic | icon update (5 left), RadStackCount = 3 -> jump |
| 10.717 | traffic 159679 | **jump missile created at (63.45, 79.10) = AWW, creator `00 01 00 00 00 00 00 02` = AWW** |
| 10.718-10.722 | 28688-28694 | jump missile `S0 -> S5 -> S3 -> S2 (T0)` in 3 ms; `0x10000039` on AWW (traffic 159689) |
| 10.724-10.725 | 28696, traffic 159697 | status `S1 -> S0 (T0)`; stop Tgt_Active (0x8D signal 1, run 6194) |
| 11.078 / 12.085 | server.log | AWW takes 165 = turret mid t1 (its shots 10.939 / 11.971, traffic 159734 / 160045) |

No 0x480007BE (Sickness) or 0x100005E4 modifier on AWW after the hit (C, traffic): no slow.

## 3. The runtime (C code, confirmed headless)

### 3.1 The status follows the target (C)
`Region._enter` runs a state's update chain every `UPDATE_INTERVAL` (0.1 s) via `inst.after` (script_runtime.py ~1110),
independent of movement; `_find_targets` (script_nodes.py 2215) takes `center = w.position(inst.owner)` when operand 6
is unset, and `CastWorld.position` (world.py 2096) is the live `ent.pos` moved by `World.tick`. Headless "near, then
walk away 12 m and back" (current code): once the status was on, pulses at +6.2 / +7.3 / +8.4 s kept landing on the
walking bot.

### 3.2 Homing missile re-aim (C)
`Missile.fly_to` (script_runtime.py 488/493) computes `dist = math.dist(self.pos[:2], dest[:2])`; `self.pos` is set at
creation (454) and only at `arrive` / `collide`. `set_speed` (532) re-calls `fly_to` (new trip, the pending arrival
dropped). `ObjectMissile` moves the client object (`entity.follow`, world.py 1260) but never the server position.
Headless trace, bot standing 4.5 m away (current code):

```
t=0.10 trip 1  logical 5.50,78.50  object 5.00,77.50 -> 9.50,77.50  speed 4.00  eta 1.03
t=0.40 trip 2  logical 5.50,78.50  object 6.20,77.50                speed 4.66  eta 0.88
t=1.30 trip 5  logical 5.50,78.50  object 9.50,77.50 (on the bot)   speed 6.64  eta 0.62
...
t=4.60 trip 16 logical 5.50,78.50                                   speed 13.90 eta 0.30
t=4.90 ARRIVE trip 16
```

Walking bot: no arrival in 9 s (the chase timer, 6 s, ends it). 18 scripts call SetMissileVelocity; only Meltdown's
`0x340002BE` does it in a timer loop, the others once (a one-off delay).

### 3.3 Who a status script acts for (C ics, C client structure, P server rule)
- ics: `Instance.source()` (script_runtime.py 918) = a missile's shooter, else the owner. A status instance's owner is
  its victim (`apply_status`, 2663). Used for: FindTargets' relation and self exclusion (2222-2237), ApplyDamage's
  default source (743), StartVitalOverTime's source (531), LaunchMissile's shooter and start point (1200, Missile 454,
  ObjectMissile 3046 / 3056), ApplySkill's source (854), hotspots' owner (1239) and more.
- Client: FindTargets' client half `0x9CCE60` builds its query from **two** entities: SELF from the owner block
  (`0x44C5C0`, hash `[0x1854350]`), excluded when the node's byte +0xF (include self) is 0 (`0x4A9060`), stored at
  query +0x60; and the **team of the source descriptor's entity** (`0x991F60` -> `0x854050`, property 0x1000009C) at
  query +0x68, with the node's words +0x8C / +0x90 / +0x94 at +0x70 / +0x6C / +0x58 (kinds / relation mask / max, P by
  the value order). `0x991F60` fills the descriptor by context type (`ctx->vt+0x1C`): **0x10000005 -> `0x55B9C0(entity,
  the context's instance id, ...)`, a 3-byte `return 0` in the client** (3 callers; the server-only lookup of the
  running effect, P), 2 -> the skill component (`0x96E160`),
  0x10000006 -> property 0x100004FE, else the creator 0x100004E2 (+ its slot 0x100004E1) or SELF. So the relation's
  side comes from the responsible entity, not from SELF (C for the code; P that the server's status branch gives the
  status' source).
- Data: status `0x340000F0` (a mark on an enemy) deals, when it ends, ApplyDamage to every FindTargets(relation 3)
  target and then to SELF: only meaningful with the relation taken from the applier and SELF excluded. 32 of the 299
  status scripts (records' 0x10000242) call ApplyDamage; of the 21 that also read EffectSource, 19 leave the source
  operand unset and 2 (`0x340006A1`, `0x340006E3`) pass $EffectSource: the unset source must be the applier, or every
  such damage would credit its victim (C scan).
- Effects in ics (C headless, `stacked` scenario, current code): pulse 1 deals 23.1 "enemy bot -> enemy bot" and 22.0
  "enemy bot -> Atomic Green Lantern"; the jump missile is launched by "enemy bot" at "Atomic Green Lantern"; its
  `LoadSkillStats` reads the bot's slot 4 (AWW Reclaimer): {SkillRangePlus 40, **ChaseDuration 0**, MinSpeed 0,
  BoostLifetime 0, MaxSpeed 0} -> `S3 -> S2 (T0)` at once (the live 10.721 line). Kill credit, bounty, XP and
  `Match._on_hit` (assists, call for help) also see the victim as the attacker (`World.damage`, world.py 1558-1600).

### 3.4 The passive's stacks (C code, P order)
`_apply_damage` raises `0x1000008A` only when `getattr(inst, "status", None) is None` (script_nodes.py 775), and
synchronously. Status damage therefore never stacks Rads. With the event raised for status damage but synchronously,
pulse N's stack is counted by the same pulse's jump test: Meltdown jumps after 3 pulses and the victim keeps 3 stacks
(no Sickness from Meltdown). The client VM queues events (`0x96DED0` queues per instance, `0x461430` accept list);
delivered after the status' chain, the 4th pulse makes the victim sick and moves Meltdown on (headless with the queue:
Sickness 0.05 s after the pulse that jumps).

### 3.5 Variable aliasing in the passive (C)
`Instance.get / set` key variables by hash only. The client resolves an operand's block by its source
(`ctx->vfunc 0x30(n)` / `0x34(n)`, full-combat-skills.md 1.6): 1 script, 2 owner, 3 / 4 top graph / its state, 5 / 6
nested graph / its state (P for the depth meaning, from the data). Passive: graph S1's `TargetIID` is source 3 (written
on 0x1000008A / 0x1000001D), graph S2 > nested S1's `TargetIID` is source 5 (written on the basic hit `0x1000008B`,
polled by `T2 S1 -> S2`). One slot in ics: any skill hit while the proc is charged also fires the proc (exit chain
`RaiseEvent(SELF)[0x1000001D]`) = 2 stacks and a 4 s proc cooldown (live 09.703-09.720). 95 of 875 scripts use one
variable name under several local sources (C scan); a VM-wide fix needs its own validation.

### 3.6 Loop guard (C)
`Instance.event` (script_runtime.py 789-800) drops an event after 4 within 20 ms, keyed by event id only. Headless,
4 minions + the bot inside one pulse (patched): 6 x `[0x340002b3] event 0x1000008a loop cut (more than 4 in 20 ms)`.
The same cut hits direct skill AoEs on 5+ targets today.

### 3.7 Self removal (C ics, P VM rule)
`_remove_status`'s self form (script_nodes.py 914-923) removes at once; `run_nodes` (1323-1326) stops on
`inst.removed`. In the jump branch the `RaiseEvent 0x10000006` that follows (the enclosing IfThenElse's after chain)
never runs: the next target gets PulsesRemaining + 1 (headless `minions`: 3 pulses on the bot, 4 on the minion). Data:
64 self-removal nodes, 10 with nodes right after them (`0x340002BF`, `0x34000333`, `0x340004CB`, `0x340004E0`,
`0x34000543`, `0x3400058E`, `0x340005C9` ApplySkill, `0x34000649` / `0x340006C3` RaiseEvent, `0x340007E1`): written
to run after the removal (P).

### 3.8 The orb on a walking victim (P, systemic)
`0x10000889` is a persistent run (StartScriptlet with a handle; stopped by 0x8D signal 1). A full bundle re-creates the
object and drops its runs' attachments (seen for the camps' phase-in and AGL's sphere: jungle-camps-spawn.md 2,
`World._resend_looping`). Bots get full bundles on motion changes (`bot_motion_only` false, `World.motion_update`
throttle 1 s / 10 deg). In this run the status lasted 0.135 s, so no evidence either way (O). Owner: the bundle /
animation agent; a candidate fix is in 6.7.

## 4. Client facts used (C)
- `0x991F60` source descriptor (above); `0x9CCE60` FindTargets client half; ApplyDamage / ApplySkill / LaunchMissile
  have an empty client half (`0xAB4D80` at vtable +0x28 of `0x15FC8FC` / `0x15FDFDC` / `0x15FCBBC`): server-only.
- 0x100004E2 is the creator / shooter IID (agl-visuals.md 1.2); the jump missile should carry AGL there.

## 5. Headless runs (virtual clock, Crime Alley `0x40000C82`, AGL level 6 ranks 1, bot AWW 4.5 m away unless noted)

Patched = fixes 6.1-6.5 as monkeypatches (6.2 applied to `Instance.source()` for every status-script call site).

| Scenario | Current code | Patched |
|---|---|---|
| bot standing | hit +4.9 s; 4 pulses by +8.3 credited to the bot; no stack, no slow | hit +1.1 s; 6 pulses (+1.2 ... +6.7, 23.1 each, credited to AGL); Sickness +3.45; speed 3.9 -> 2.34; ends after pulse 6 |
| bot walks 12 m away and back from +0.3 s | never hit (9 s) | hit +1.8 s; 6 pulses on the walking bot; Sickness +4.15; slowed |
| bot 1.5 m, sick before the cast (jump rule true at pulse 1, as in the tester's run) | pulse 1, AGL takes 22.0, jump missile bot -> AGL dies, status removed | 6 pulses on the bot, AGL untouched, bot slowed |
| bot + 2 bot-team minions near it | as standing | pulses hit the bot and both minions; jump at pulse 3 to the nearest minion, started at the bot (9.5, 77.5); bot sick + slowed; 4 pulses on the minion (6.5 fixes it to 3) |
| bot + 4 minions in one pulse | - | 6 loop cuts of 0x1000008A (6.4) |
| `champion_check --only 0x4000047D --vs-champion --window 8` | R verdict FX (damage not credited), vs bot 130 | R DMG (903 on the minion wave, 49 hits), vs bot 183, statuses with 0x480007BC / 0x48000294 |
| `champion_check --vs-champion` (54 base variants) | BUFF 15, CHMP 11, DMG 159, FX 82, REF 3 | BUFF 15, CHMP 11, DMG 170, FX 71, REF 3; 13 slots better (AGL E/R, Arcane Zatanna R, Doomsday W/E, Gaslight Joker R, Krypto Q/W, Mecha Superman R, Shazam E, Sinestro R, Solomon Grundy R, Star Sapphire W); sequences equal |

The one vs-bot drop (Gaslight Joker's Rat Swarm 61 -> 0) is the tool, not the fix: Rat Swarm is a toggle and the
patched slot no longer gets the extra "dummy champion" cast, so the vs-bot cast switched it off (C, champion_check
cast order).

## 6. Implementation plan

Every key below goes to `ics/config.py` `[ics]` with the comment "2026-10-28 15:00 (tester: AGL's R must slow and keep
hitting a moving target; docs/re-notes/meltdown-moving-target.md)"; module flags are set in `ics/server.py` beside
`EXIT_REENTRY_GUARD` (and in `tools/champion_check.py` / the new test the same way).

### 6.1 Homing re-aim from the current position (1) - `missile_reaim_from_current = true`
`ics/script_runtime.py` `Missile.fly_to`: when `REAIM_FROM_CURRENT` and `self.trip > 0` and the target is an entity,
first move `self.pos` to where the missile is: `getattr(self, "entity", None).pos` when the client object exists
(ObjectMissile), else along the last leg (store `self._leg = (world.time, start, dest, speed)` at each `fly_to`;
`f = min(1, (now - t0) * speed / dist)`), and add the travelled part to `self.flown`. Expected: standing 4.5 m -> hit
within 1.3 s; walking bot -> hit within 2.5 s.

### 6.2 A status acts for its source (2) - `status_acts_for_source = true`
- `ics/script_runtime.py`: in `apply_status` set `current.effect_source = source` (created and refreshed instances;
  `_restack` too); new `acting_entity(inst)`: a status instance with a live `effect_source` other than its owner ->
  that entity, else `inst.source()`.
- `ics/script_nodes.py` (status instances only; skills / missiles unchanged):
  - `_find_targets`: relation with `R.acting_entity(inst)`; exclusion (`include_self` 0), the radius added (flag 0) and
    the box heading with `inst.owner` (the client's SELF, `0x9CCE60`).
  - `_apply_damage`: default source `R.acting_entity(inst)` (credit, penetration, lifesteal, K/D/A, bounty).
  - `_start_vot`: `"source": R.acting_entity(inst)` (Sickness DoT credited to AGL).
  - `_apply_skill` / `_add_stacks`: source `R.acting_entity(inst)` (nested statuses carry the real applier).
  - `_hotspot`: owner (team / relation / status source) `R.acting_entity(inst)`; position / attachment stay SELF.
  - `_launch`: shooter `R.acting_entity(inst)` and `extra["origin"] = inst.owner`; `Missile.__init__(..., origin=None)`
    starts at `position(origin)`; `ObjectMissile.start` places the client object at the origin (+1 m z), team = the
    shooter's, 0x100004E2 = the shooter. Expected: the jump missile has ShooterIID AGL (slot-4 stats, 0x100000EE to
    AGL's `0x340002B4`), flies from the old victim.
  - Leave `_face`, Begin / EndSkill, StartCooldown / SpendCost / ReduceCooldown, TrackTeam / GetTeamMember on
    `inst.source()` (14 / 8 / 2 / 13 status scripts use them; no evidence they act for the applier).

### 6.3 Status damage is a skill hit, queued (2b, 4) - `status_skill_hit_event = true`
`_apply_damage`: for a status instance with `_damage_slot(inst)` in 1-4 and `acting_entity` a champion other than
the damaged entity, raise `0x1000008A {TargetIID, 0x31D944: slot}` on the acting entity's scripts **after the current
chain** (`inst.world.after(0.0, ...)`); direct skill damage stays as it is. Expected: one Rad stack per pulse per
victim, Sickness on the 4th, then the jump.

### 6.4 Loop guard per target (5) - `event_loop_per_target = true`
`Instance.event`: the 20 ms counter key is `(ev, _key(target))` when the event's parameters carry an entity under
"TargetIID" / 0x9A6A765, else `ev` as now. A runaway on one target is still cut.

### 6.5 Self removal finishes the chain (6) - `status_self_remove_after_chain = true`
`_remove_status` self form: schedule `R.remove_status(world, owner, status, inst)` with `inst.world.after(0.0, ...)`,
mark `inst.removing = True`, return False so the rest of the chain (and the enclosing after chains) runs; the update
loop then finds the status removed before its next tick. Expected: 6 pulses in all across a jump.

### 6.6 Scoped local blocks (3) - `scoped_local_blocks = false` until validated (script VM owner)
`Instance.get / set`: operands of source 5 / 6 (nested graph / state locals) keyed `(source, hash)`; the passive then
stacks once per skill hit. Validate with `tests/test_scriptvm.py`, `tests/test_director.py` and a 54-champion
`champion_check` (95 scripts reuse a name under several sources) before turning it on.

### 6.7 For the bundle owner (7) - `resend_status_scriptlets_after_bundle = true`
Register StartScriptlet runs (`script_runtime._start_scriptlet`, a live handle) like `scriptlet_restart` keys in
`World.looping_scriptlets` (variables kept, no stop key, cleared by `signal_scriptlet` / StopScriptlet) so
`World._resend_looping` re-sends the victim's orb `0x10000889` after each of its full bundles.

### 6.8 Tests
- New `tests/test_meltdown.py` (no ports; the `test_match.FakeSession` + `World` + `pvp.start_match` harness of
  `tools/champion_check.py`, AGL `0x4000047D` vs `create_bot_champion(0x400003EC)`), checks:
  1. standing bot 4.5 m: hit <= 1.5 s after the cast; exactly 6 pulses; every pulse's `World.damage` source is AGL;
     AGL loses no health to Meltdown; `0x480007B6` applied by AGL after pulses; `0x480007BC` + `0x48000294` before the
     5th pulse; `0x20F0` label `modifier 0x100005e4 op 10 = -0.4` sent; bot `move_speed` = base x 0.6 while sick; no
     7th pulse.
  2. walking bot (walk_to 12 m away from +0.3 s, then back): hit <= 2.5 s; 6 pulses; the pulse centres move with the
     bot (> 1 m apart); slowed.
  3. the tester's case, bot alone with 3 stacks (or sick) before the cast: 6 pulses on it, no jump missile, slowed
     after pulse 1.
  4. bot with 3 stacks and a bot-team minion 2 m away: a jump missile at pulse 1, shooter AGL, launched at the bot's
     position, aimed at the minion; the minion's `0x480007AF` EffectDuration = 5 s; 6 pulses in all.
  5. bot + 5 bot-team units within 2 m: every unit gets a stack from pulse 1; no "loop cut" log line.
- `tests/test_scriptvm.py` (NullWorld): a missile whose speed is set every 0.3 s reaches a target 4.5 m away within
  1.3 s.
- `tools/champion_check.py`: optional `--bot-walk` (the bot walks 10 m away and back during each vs-bot window).
  `python tools\champion_check.py --only 0x4000047D --vs-champion --window 8`: R verdict DMG, vs bot >= 160, statuses
  with 0x480007BC / 0x48000294. Full `--vs-champion` run: no verdict category lower than BUFF 15, CHMP 11, DMG 159,
  REF 3; sequences unchanged.
- Run `tests/test_match.py`, `tests/test_ics.py` (`ICS_TEST_PORT`), `tests/test_session_flow.py`
  (`SESSION_TEST_PORT`), `tests/test_scriptvm.py`, `tests/test_director.py`.

### 6.9 For the tester (what the original does)
With an enemy minion or champion within 4 m of the victim, Meltdown moves to it once the victim gets its 4th stack
(after its first pulse when the victim already had 3, as AWW did); it stays on the victim only when nobody valid is
near. The slow is Radiation Sickness (-40 % for 3 s), on the victim and on every enemy that takes 4 pulses.

## 7. Open
- O: node `0x1000016F` (ics: IsInFront, P). Used as `X(SELF)` in Meltdown's "damage failed" branch and as a break /
  pay condition in Starro's control `0x3400052D`; harmless while the pulse damage succeeds.
- O: whether the original tick spaced pulses exactly 1.0 s (ics: 1.1 s on its 0.1 s update grid; 6 pulses still fit
  the 6 s status).
- O: the orb drop on the victim's bundles (3.8) needs a run where the status lives > 1 s on a walking bot; existing
  breakpoints `0x6279D0` (0x8D started) and `0x57BAF0` (run removed, client-scriptlets-graphs.md 1.4) would show it.
- O: AGL's own throw clip ends at `skill_to_cosmetic` 0.17 s (data/skill_hooks.tsv); the animation agent's area.

## 8. Finalizer check (2026-10-28, after the investigation; no server code changed)

Re-checked against the current files. No file the plan touches changed after 14:29, none of the 6.x keys is in
`ics/config.py` yet, and every line number cited above still matches.

1. **Cause 1 holds (C).** `Missile.fly_to` (script_runtime.py 488-507) measures from `self.pos`, which is written only
   at creation (454), `arrive` (543) and `collide` (622). `set_speed` (532-538) calls `fly_to` again, and the new
   `trip` voids the pending arrival (541). The match's per-tick hit test skips every missile that follows a target
   (`World._missile_hits`, `e.follow is None`, world.py 1345), so for a homing missile the arrival timer is the only
   way to hit: 6.1 is needed, and it is enough for the landing. `CastWorld.position(missile)` already returns the
   client object's point (world.py 2099-2100), so 6.1 can read that point and needs to interpolate only in NullWorld.
2. **Cause 2 holds (C for ics, P for the server rule).** `Instance.source()` (918-920) is the owner unless the owner is a
   Missile. `apply_status` makes the victim the owner (2690) and passes the applier only as the `EffectSource`
   parameter (2699). `_find_targets` takes its relation and self exclusion from `source()` (script_nodes.py 2222 /
   2233 / 2237), `_apply_damage` takes its default source from it (743) and raises 0x1000008A for non-status instances
   only (775). `_launch` makes `source()` the jump missile's shooter (1200), and `ObjectMissile.start` starts the
   missile at that entity and writes it as 0x100004E2 (world.py 3045-3056). Data: `0x340002BF` has no ApplySkill /
   AddStacks of `0x480007B6` / `0x480007BC`, only GetStackCount (`node_100000FE`) and HasStatus reads; the passive
   `0x340002B3` holds the only two ApplySkill. Client: `0x991F60` decompiles as 3.3 describes (ctx 0x10000005 ->
   `FUN_0055b9c0`, 3 bytes, `return 0`; 2 -> `0x96E160`; 0x10000006 -> 0x100004FE; otherwise 0x100004E2 /
   0x100004E1), and `0x9CCE60` builds its query from `0x44C5C0` (SELF) and that descriptor. Which entity the server's
   status branch returns stays P; the data argument of 3.3 supports it.
3. **Section 2 could not be re-read.** `logs/` was empty at 18:49, and no scratchpad holds a copy. Two other notes read
   the same log on their own and agree with section 2: object-update-bundles.md 5.2 (hooks at .340 / .456 / .516,
   missiles `0x40000484` at .478 and .717, `Tgt_Active` stopped on AWW at .725 by 0x8D signal 1) and
   test-2026-10-28-1439-sweep.md (bot death 4 at 14:52:16 to turret mid t1, which fits the 165 hits). The 10.712 line
   (AGL takes 21.5054) and the 10.717 creator bytes rest only on the investigator's transcription.

Gaps and contradictions:
- **The cause given in object-update-bundles.md (0.7, 5.2, table 6) and in its fase3-if CHANGELOG bullet is wrong.**
  Those say Meltdown's waves stop because the server script reaches graph hook 2 0.18 s after the cast. Hook 2 is
  the data's `skill_to_cosmetic@0.170` of `Clip_Meltdown` (data/skill_hooks.tsv, pack 0xA0000150;
  `a_MissileFireHook@0.100` is code 5), and it ends AGL's throw by design. The waves are the status' pulses on the
  victim. The status was applied after hook 2 (.590), pulsed at .707 and removed itself at .724 after the jump (2, 3.3,
  3.7). Both notes agree the cause is the server script and not a bundle. This area's CHANGELOG bullet should
  correct the cause.
- **Cause 7 / 3.8 / 6.7 have lost their premise.** object-update-bundles.md 0.1 (C) shows that a full 0x4 bundle to a
  live object rebuilds no component, scriptlet run, graph or model; it only removes the omitted network-mode 1 / 3
  ids. Cause 7 is O at most. Do not build 6.7: re-sending a run that is still alive would start a second orb (P).
- 6.2 "a live `effect_source`" must mean "still exists", not "alive". With "alive", the pulses flip back to the
  victim's side when AGL dies mid-Meltdown: relation 3 is taken from the victim, so AGL's allies near it are hit, and
  the damage is credited to the victim. For a source that no longer exists, keep the team captured at apply time.
- 6.2 origin: `_launch` retries without `**extra` on a TypeError (script_nodes.py 1199-1202). `CastWorld.launch_missile`
  (world.py 2515) and `NullWorld.launch_missile` (script_runtime.py 386) forward `**extra`, but a test world without
  it drops `origin` silently. `ObjectMissile.start` takes its start point from the shooter entity (3046), not from
  `self.pos`, so the origin must be applied there too.
- 6.3 is a design inference (P). No code site raises a skill hit for status damage (the client's ApplyDamage half is
  empty, 4); the inference rests on the tooltip and on the missing stack node. Only the 54-champion verdict categories
  check its effect on the other 0x1000008A listeners (21 scripts of 7 champions, kit-audit-1.md 1). Queueing works in
  both worlds: `CastWorld.after` schedules at >= 0.01 s (world.py 1914-1931), and NullWorld's heap runs the callback
  after the current call.
- While 6.6 stays off, the passive still adds the proc's stack to a pulse's skill hit whenever the proc is charged
  (3.5). The 6.8 checks should therefore test "Sickness by pulse 4" and "6 pulses", not an exact stack count per pulse.
- Minor: section 0 gives 4.8 s for the standing-bot hit, while 3.2 and 5 give 4.9 s (cast time vs launch time). The
  fase3-ic CHANGELOG entry "R did hit Nightwing (165 x 2)" predates this run. Here 165 is the mid t1 turret's hit on a
  champion, so that older attribution is probably the turret too (P; its log is gone). The `catalog/data/skills.tsv`
  row `0x480007A2:4` still says `data only`.

## 9. Skeptic review (2026-10-28, independent re-check; no server code changed)

**Verdict: causes 1-6 hold, and no simpler or different cause turned up. The plan is sound once the corrections
below are applied (go ahead).**

Re-checked (C):
- Every cited code line (script_runtime.py 454 / 488-507 / 532-544 / 918-920 / 2686-2706, script_nodes.py 743 / 775 /
  914-923 / 1200 / 2222-2237, world.py 1260 / 1345 / 2096-2100 / 3045-3056) and the trees of `0x340002B3` / `B4` /
  `BE` / `BF`.
- The decompilation of `0x991F60` (ctx 0x10000005 -> `FUN_0055b9c0`, 3 bytes, `return 0`; 2 -> `0x96E160`;
  0x10000006 -> 0x100004FE; else 0x100004E2 or SELF) and of `0x9CCE60` (SELF from `0x44C5C0`, excluded when byte +0xF
  is 0; the team at query +0x68 is `FUN_00854050` of the descriptor's entity).
- Headless, current code (my own scratch harness on `champion_check`'s setup):
  - Standing bot 4.5 m away: hit at +4.9 s, then 4 pulses credited "enemy bot -> enemy bot".
  - Walking bot: `S3 -> S2 (T0)` at +6.1 s and no hit.
  - Bot 1.5 m away with 3 stacks: pulse 1 also deals "enemy bot -> Atomic Green Lantern" 22.02. The jump missile goes
    `S3 -> S2` at once and the status goes `S1 -> S0`.
- The same harness with 6.1-6.5 monkeypatched (6.4 approximated by turning the loop guard off):
  - Standing: hit at +1.1 s, 6 pulses credited to AGL, AGL stays at 940/940. Sickness comes after pulse 3, because
    pulse 1 gives 2 stacks (the 3.5 aliasing).
  - Walking: hit at +2.1 s, all 6 pulses land on the walking bot, and its speed drops 3.9 -> 2.34 while sick.
  - 3 stacks, bot alone: no jump, Sickness right after pulse 1, 6 pulses.
  - 3 stacks plus a bot-team minion 2 m away: AGL's jump missile at pulse 1, the minion's status lasts 5.0 s, and
    Meltdown jumps back to the bot at pulse 5 (1.0 s). 6 pulses in all.
- Logs: no copy of the 14:39-15:00 run exists anywhere (`logs/` is empty; the temp archives `logs-0813` ...
  `logs-2330` date from 10-21 to 10-23). Section 2 stays a transcription, but the headless runs reproduce each of its
  steps.

Extra evidence:
- Cause 1, live: in test-2026-10-25-1928.md (AGL, 19:38:42-46) the missile looped `S3 -> S7` every ~0.33 s for 4.4 s on
  a siege minion and never hit. Cause 2 fits test-2026-10-25-2207.md AGL-4: Katana had no stacks, so the status
  pulsed 5 times.
- The server rule of cause 2 is now P strong, from the data:
  - GetCreator's client execute `0x993480` is one of the 8 callers of `0x991F60` (functions.tsv). `0x9CCE60` takes
    the relation team from that same descriptor.
  - Status scripts name GetCreator's output after the applier. `0x340005C9` (status `0x48000F87`) does
    `GetCreator($EffectSource)`, LoadSkillStats from it (slot 4) and RaiseEvent to its `0x34000582`. `0x34000654` and
    `0x3400074E` use `$Caster`, `0x34000543` uses `$StarroIID`.
  - ics's own `_get_creator` already returns EffectSource for a status (script_nodes.py 1413).
- 6.2 also fixes other statuses that an enemy applies and that search with relation 3:
  - Zatanna's Punish `0x340000F0` (status `0x4800021A`, from `0x3400045F`): a healing-reduction mark whose end blast
    hits relation 3 + SELF.
  - Arcane Green Lantern's R `0x340002BD` (status `0x480007AD`, spreads by ApplySkill).
  - Green Arrow's basic-attack status `0x340006E3` (status `0x48001155`).

  Protect `0x340000F1` (relation 4) is applied to allies, so 6.2 leaves it unchanged. Status scripts that search,
  aura or launch are few: FindTargets 12, CreateAura 6, LaunchMissile 1, LaunchLobbedMissile 2, SpawnEntity 2.
- 6.3 has a design basis. The game's own descriptions (pack table `0x2B000094`, tokens `0xB72A1DE` and `0x28A700E`)
  say, paraphrased: skill damage applies a stack; each pulse applies Radiation Sickness in an area; Meltdown moves on
  when the target gains its fourth stack. That supports both the skill hit and the queued order.
- The counts in 3.3 hold with the by-kind reader `Data.record`: 354 records, 299 scripts, 32 with ApplyDamage, and
  `0x340006A1` / `0x340006E3` pass `$EffectSource`. `gamedata.status_script`'s pattern search finds only 283 records /
  241 scripts.
- The 0x10000005 getter (`mov eax, 0x10000005; ret` at `0xAC5150`) is folded code shared by two vtables:
  `0x15FD2A0`+0x1C (the node SetSkillAttached) and `0x160BC20`+0x20. So the client cannot tell which class is the
  status context, and that part stays P.

Corrections to the plan:
1. **6.2 order.** Set `current.effect_source` before `current.event(EVENT_STATUS_APPLIED, ...)` (script_runtime.py
   2706), and in `_restack` before its events. The enter chain runs inside that event. Headless with the assignment
   after `apply_status` returns, the Sickness' slow `0x48000294` is still applied by the victim and its DoT is
   credited "enemy bot -> enemy bot". With the early assignment, both go to AGL.
2. **6.2 value.** Use the `source` argument of `apply_status`, never `params["EffectSource"]`. 33 ApplySkill nodes
   set EffectSource (operand 9), and 25 of them are basic attacks that put the shot tracker `0x48000AB0` on SELF with
   EffectSource = `$TargetIID` (`0x34000037`, `0x3400009D`, `0x340000ED` ...). A rule based on the parameter would
   make every shot tracker act for the enemy.
3. **6.2 liveness.** Drop "alive", "exists" and the captured team. `CastWorld.team` reads `ent.team` from the object
   (world.py 2127), and champions keep their object through death and respawn (world.py 1602, 1767; match.py 1346).
   The rule is: `effect_source` is set and is not the owner.
4. **6.2 `_launch`.** Change the shooter and origin only for a new missile (class value set, operand 0 unset). The
   knock-up statuses `0x340003E7` (`0x480009FC`) and `0x34000655` (`0x48001089`) launch SELF as a lobbed missile.
   With the applier as its owner, `Missile.start` would write ShooterIID = the applier into the victim's own scripts,
   and the flying victim (kind "missile") would collide with the other side.
5. **6.3 gate.** Raise the status skill hit only when ApplyDamage's value b (`values[1]`) is 1 ("triggers on-hit
   effects", full-combat-skills.md 825).
   - Proc damage (b = c = 0) is 12 of the 38 ApplyDamage nodes in `0x1000008A` / `0x1000008B` listener scripts,
     against 25 of 325 elsewhere. Both Meltdown nodes have b = 1.
   - `CastWorld.after` floors at 0.01 s (world.py 1914). That is below both the 20 ms event guard and the 2000
     timers/s guard, so a listener status that answers a skill hit with damage would feed itself at 100 Hz.
   - I found no such loop in the data (`0x340004BE` compares SkillSlot with a `Skill1` that is never written), so
     the gate is a guard, not a fix for a known bug.
6. **6.3 side effects.** Check these by trace in the 54-champion run; verdict categories do not show extra procs.
   - Atrocitus' rage passive `0x340004D1` (T5, on 0x1000008A) starts gaining from his Q status `0x340004E2`.
   - AWW's W status `0x3400026A` reaches her passive `0x34000265`, which acts only when SourceSkill == UltSkill, so
     no change is expected.
   - Nightwing's mark `0x48001429` is applied from slot 5, so it raises no event.
   - 10 listener status scripts: `0x3400028E`, `0x340002E8`, `0x3400036E`, `0x34000490`, `0x340004BE`, `0x340004EE`,
     `0x34000551`, `0x34000553`, `0x34000640`, `0x340006AA`.
7. **6.1.** Counting the flown legs makes `flown + dist > 1.5 x range + 1` (script_runtime.py 494) reachable during
   long chases, for ranged homing missiles that set their speed. Meltdown is not affected: its LaunchMissile leaves
   the range operand unset (max_range 0). Name this in the CHANGELOG bullet and check the other SetMissileVelocity
   scripts.
8. Section 8 stands: drop 6.7, and correct the fase3-if bullet "Object update bundles, investigation" about hook 2.
9. **6.8 additions.** Check that the Sickness DoT and `0x48000294` have AGL as their source (correction 1). Add a
   knock-up regression: `0x340003E7` still launches the victim with its own owner (correction 4).

## 10. Implementation (2026-10-29, fase3-if)

Implemented 6.1-6.5 with the skeptic's corrections; 6.6 (scoped local blocks) and 6.7 (dropped) not built. Every key
is in `ics/config.py` `[ics]` (true; false = the fase3-ie behaviour); the module flags are set by `ics/server.py` and
`tools/champion_check.py`.

| Fix | Code | Key |
|---|---|---|
| 6.1 re-aim from where the missile is | `Missile.fly_to` -> `_advance` (client object's point, else along the last leg `_leg`; nothing moves after an arrival / collision placed it) | `missile_reaim_from_current` |
| 6.2 a status acts for its applier | `script_runtime.acting_entity`; `effect_source` = `apply_status`'s `source`, set on a new instance before `start()` and on a refresh / `_restack` before their events; `_find_targets` (relation only), `_apply_damage` (unset source), `_start_vot`, `_apply_skill`, `_add_stacks`, `_hotspot` (owner; attachment / position stay SELF), `_launch` (new missile only: shooter = applier, `origin` = the owner; `Missile(origin=)`, `ObjectMissile.start`) | `status_acts_for_source` |
| 6.3 status damage is a skill hit, queued | `_apply_damage`: status, slot 1-4, value b = 1, actor a champion other than the target -> `world.after(0.0)` `0x1000008A {TargetIID, 0x31D944}` | `status_skill_hit_event` (and `skill_hit_event`) |
| 6.4 loop guard per target | `Instance.event`: key (event, target) when the parameters name TargetIID / 0x8DCD754 / 0x9A6A765; old keys pruned past 256 | `event_loop_per_target` |
| 6.5 self removal after the chain | `_remove_status` self form: `inst.removing`, `world.after(0.0, remove_status)` | `status_self_remove_after_chain` |

Found while validating (C, champion_check): with the applier's side, Solomon Grundy's Buried on Sunday hit a
RecursionError. Its plague `0x480010DC` (script `0x340006AB`) carries a mask-3 aura that applies the plague (A) and
again on exit (C); from Grundy's side the aura matched its own carrier, refreshed the carrier's own plague, took it as
its own and removed it on exit, then re-applied C: a loop through the infected's auras. CreateHotspot / CreateAura's
flag [0] ("include the owner", full-combat-skills.md) is 0 in all 52 hotspot / aura nodes, and FindTargets excludes
SELF the same way, so a status' aura whose applier is not its carrier now excludes the carrier (`hs.exclude`), and a
status A it applies to a unit that already had it is not the aura's (not removed on exit). Under the old side these
auras never matched their carrier (it is its own ally), so nothing else changes. Same key (`status_acts_for_source`).

Validation (headless, virtual clock):
- `tests/test_meltdown.py`, 32 checks, no ports, ~12 s: still bot 4.5 m (orb lands +1.1 s, 6 pulses all AGL's, no hit
  on AGL's side, Rad stacks by AGL, Sickness + slow by AGL before pulse 5, the 0x20F0 `0x100005e4 op 10 = -0.4`, DoT
  AGL's, pulses ~1.1 s apart); walking bot (lands +2.1 s, 6 pulses following it, slowed 3.9 -> 2.34); 3 stacks alone (6
  pulses, no jump, AGL untouched, Sickness after pulse 1); 3 stacks + a bot-team unit 2 m away (jump orb at pulse 1, AGL's
  with 0x100004E2 = AGL, starts at the bot, the unit gets 5 s, 6 pulses in all); 5 units (each stacked by pulse 1, no
  loop cut); AGL dead after pulse 2 (6 pulses, all AGL's, the AGL-team unit by the bot never hit). Each key off fails
  its checks: re-aim 5, side 20, skill hit 7, loop guard 2, self removal 2 (8 pulses).
- `tests/test_scriptvm.py` +13 (NullWorld): re-aim (8 m in 1.5 s; off: 5.35 s), acting entity, relation, credit, queued
  skill hit with slot 4, jump orb shooter / origin, knock-up `0x340003E7` keeps the victim as its own shooter,
  self-removal (and off), loop guard per target.
- `champion_check --only 0x4000047D --vs-champion --window 8`: R DMG (820 on the minion wave, 46 hits), vs bot 160.3,
  statuses with `0x480007BC` / `0x48000294`; `--bot-walk`: the same 160.3, one 0x480007AF (no jump).
- `champion_check --vs-champion` (54 champions, 3 s window), keys off -> on: BUFF 15 -> 16, CHMP 11 -> 11, DMG 159 ->
  178, FX 82 -> 62, REF 3 -> 3; sequence verdicts identical. Slots better: Arcane Supergirl W / E, Arcane Zatanna R, AGL
  E / R (vs bot 44.5 -> 66.2), Atomic Joker E, Doomsday W / E, Gaslight Catwoman E, Gaslight Joker R, Green Lantern W,
  Krypto Q / W, Lex Luthor W, Mecha Superman R, Mecha Wonder Woman W / E, Nightmare Batman W, Poison Ivy R, Shazam E,
  Sinestro R, Solomon Grundy R, Star Sapphire W, Stargirl W. Gaslight Joker's Rat Swarm vs bot 61 -> 0 is the tool's
  order (a toggle: the dummy-champion cast no longer runs before it); cast once from fresh it does 61 (C).
- Suites: test_match 304/304, test_ics 41/41 (port 19500), test_session_flow 81/81 (port 32500), test_director 43/43,
  test_scriptvm 78/78.

Still open: 6.6 (the passive's two `TargetIID` locals: two Rad stacks per skill hit while its proc is charged, so the
victim is sick after 3 pulses, not 4); node `0x1000016F`; the 1.1 s pulse spacing; the orb on a walking victim with its
bundles (O, a run where the status lives > 1 s on a walking bot shows it); a status' SpawnEntity still spawns for the
status' owner (Starro's parasite status `0x34000543`; not changed, no evidence yet); AGL's throw clip end (animation).
