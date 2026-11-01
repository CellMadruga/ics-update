# Kit audit 3 (2026-10-24): Nightmare Superman .. Zod (18 base variants)

Method: `python tools\champion_check.py --only <variant> --trace <slot>` (headless Crime Alley v AI, current ics with
the fase3-hk..ho fixes on), `python -m ics.script_model <script>` for the trees. Findings are appended per champion,
then grouped by root cause at the end. Confidence: C confirmed (simulated / read in the tree), P probable, O open.

Tools (scratchpad, not in the repo): a static pass over every script reachable from the kit (skill scripts, the
champion's own 0x8E scripts, status scripts of ApplySkill / CreateHotspot DIDs, missile / spawned class scripts):
events a transition waits for vs. what ics raises (`script_runtime` / `script_nodes` / `world` / `match.units`) and
what any of the 875 scripts raises with RaiseEvent; logged no-op nodes; scriptlet keys. Events ics raises today:
0x1000001D 0x10000049 0x10000002 0x10000035 0x100000EE 0x10000009 0x10000008 0x100000A2 0x10000020 0x10000006
0x10000003 0x100000C1/C3/C4/C5 0x100000A6 0x10000005 0x10000022/14 0x1000008B 0x10000088 (+ client 0x20EA, off).
Notes: the simulator's "damage" counts ApplyDamage only; vital-over-time damage (StartVitalOverTime) shows as FX
(e.g. Poison Ivy R ticks 27.5 per 0.5 s on 4 minions). `script_model` does not print the `next` node of a NOT
(builtin 0xA) trigger (Nightwing Q `S1 -> S0 on builtin:0xa()` is `NOT HasStatus(0x48001438)`).
Re-init family events 0x1000000C / 0x100000A9 / 0x100001B3 / 0x10000192 / 0x1000000E / 0x100000EA (stat reload) are
never raised by ics; they only re-run LoadSkillStats and are ignored below unless a slot depends on them.

## Nightmare Superman 0x400007C0 (basic 0x3400041F, Q 0x3400041B, W 0x3400041A, E 0x3400041D, R 0x3400041E, P 0x3400041C)

Sim: S0 DMG 49, Q FX (spawn only), W DMG after its 3 s lifetime (the "BUFF" is the delayed vortex blast), E DMG 60,
R FX (prison 0x48000A7D -> 0x34000444, slow on release: CC ult by design).
- Q Phantom Collector (C): S3 only `SpawnEntity [.. 0x400007F6 1 0x1000009C]`; 0x400007F6 has no 0x8E list and no
  0x10000328 (template: stat block 0x48000534, world state 0x2E000E48 / table 0x1D00058A). No damage, no
  collect logic anywhere in the kit -> O: the phantom's behaviour must come from its world-state table / client; on
  ics the Q is a visual at most.
- W Vortex recast (P): `T10: S4 -> S5 on 0x1000001D` (detonate early). After S3 the skill is on a
  `StartCooldown(SecondActivationDelay)[2]` + `SetSkillUsableOverride[2 1 1]`; check World.cast accepts the second
  press while the usable override is set (not covered by the simulator).
- Passive Possession (C, severe): graph S1 S0 `SetDefeatType(handle)[1 0]` (0x10000162) and `S0 -> S2 on
  0x1000011B` (reads event param KillerIID 0x032C3FD4). ics stores the guard and `deal_damage` clamps health to 1
  while type 0 is held, but never raises 0x1000011B: **Nightmare Superman cannot die** and never possesses.
  Keys `Vfx_Nit_Sup_Possess_Start/Stop/Success` (0x10000B6C/68, 0x10000CB3) are not in his table list (O).
- ReleaseFacing 0x10000057 logged no-op in every skill (harmless).

## Nightwing 0x40000DEE (0x34000799 / Q 0x34000795 / W 0x34000793 / E 0x34000797 / R 0x34000794 / P 0x34000796)

Sim: S0 51, Q status 0x48001438 (by design: ends after N basic attacks counted on 0x1000008B, then the cooldown
starts in S1's exit), W dash (damage only on the dummy champion: scene / IsKind), E 40, R 660.
- Passive Static Burn (C): `S0 -> S1 on 0x1000008A` {TargetIID, SkillSlot} (a skill hit) marks a champion
  (0x48001429); `S0 -> S2 on 0x10000097 / 0x10000098` {0x09A6A765} (takedown family) gives haste 0x4800082E.
  0x1000008A and 0x10000097 are never raised -> passive dead.
- Basic-attack helper 0x340007B6 waits 0x100000ED (damage-taken family, see root causes).

## Poison Ivy 0x40000145 (0x3400009D / Q 0x34000095 / W 0x34000099 / E 0x34000158 / R 0x34000097 / P 0x34000098)

Sim: S0 48, Q 100, W 60, E shield on self (0x480003C8 -> 0x3400015A), R hotspot 0x48000285 (VOT 27.5 / tick, OK).
- E Thorn Shield (C): status 0x3400015A waits `0x100000ED` {SourceIID 0x0C89C7B4, SkillSlot} to slow basic
  attackers, and `0x1000008C` {VitalExpiredHandle 0x09E49315} (its AddTempVital broken) to remove itself. Neither
  is raised (`combat.absorb` drains shields silently): no slow, the status lasts its full time.
- Passive Healthy Glow (C): `S0 -> S1 on 0x100000AF` {Slot 0x0005A364} counts skills (every Nth -> heal hotspot
  0x48000283). Never raised -> passive dead.

## Raven 0x40000C4F (0x34000681 / Q 0x3400067F / W 0x3400067E / E 0x3400067D / R 0x3400067C / P 0x34000680)

Sim: S0 48, Q 120, W links an enemy (0x4800110E) and the ally in owner-block 0x02CCCE34, E Isolation hits only
champions (IsKind 8, by design; 65 on the dummy), R runs S1 -> S7 -> S3 -> S6 (projection 0x40000CA5 spawned, dash).
- Passive Blessing of Darkness (C): flag node 0x100001A7 (lifesteal tracking) then `S0 -> S1 on 0x100001A6`
  {Amount 0x04846C54, DamageType}: SpendCost(-Amount) on the linked ally + scriptlet 0x10000293. `deal_damage`
  heals the attacker's lifesteal but raises nothing -> passive dead.
- R: `node_1000009E(AstralProjectionIID, SELF)[1]` (vitals link) is a logged no-op: the projection does not share
  Raven's health (P: damage to it should hit her).

## Robin 0x4000052D (0x3400030E / Q 0x3400030D / W 0x3400030C / E 0x3400030B / R 0x3400030A / P 0x34000309)

Sim: every slot works (S0 56, Q 70 + dash, W self status, E link statuses, R 350).
- Basic-attack slow 0x4800084B -> 0x34000330 stacks: inner graph waits `0x100000D7` {StackCount} (stacks changed)
  and `0x100000A8` {EffectDuration} (duration refreshed); neither is raised (re-applying only re-sends 0x10000006),
  so the slow does not grow with stacks (P).
- Status scripts 0x3400032E / 0x34000331 / 0x3400013B / 0x3400032A end on `0x10000003 or 0x10000007`; 0x10000007
  (P: owner defeated / cleanup) never raised; 0x10000003 covers the normal end.

## Shazam 0x40000358 (0x340001F6 / Q 0x34000756 / W 0x34000757 / E 0x340001F5 / R 0x340001F8 / P 0x340001FD)

Sim: S0 55, Q 90, W self status, E aura 0x48000653 (VOT 13.75 / tick on 4 minions, OK), R 800.
- Passive Power of Zeus (C): `S0 -> S1 on 0x10000196` {Slot 0x0005A364} counts Q/W/E uses; at ActivationCount
  -> S2: status 0x480012BB + `SetSkillStatOverride [1..3 3]` (free skills). `S0 -> S4 on 0x10000012` resets.
  0x10000196 is never raised -> passive dead. (Zod's Solar Surge waits for the same event.)
- W 0x34000757 uses HasFlagAttribute 0x1000006A (stunned 0x100003F3) in a condition: see root cause 1.

## Star Sapphire 0x400005D1 (0x34000390 / Q 0x3400038D / W 0x3400038A / E 0x3400038E / R 0x3400038B / P 0x3400038C)

Sim: S0 46, Q FX (crystal 0x40000634 only), W FX (0x40000CB2 only), E 140, R nothing.
- The kit is built around the Predator pet (C): passive graph S1 `on 0x10000088 -> SpawnEntity 0x400005D2` into
  owner-block 0x0901E674 (ics raises 0x10000088 since fase3-hk, so it spawns). Q raises `RaiseEvent(Predator,
  Crystal)[0x10000141 0x340003D1]`, R `[0x10000053 / 0x100000CB 0x340003D1]`, passive `[0x10000107 0x340003D1]`:
  every order goes to script **0x340003D1** on the pet. The pet's template 0x490005D2 only names its basic attack
  0x34000391 (property 0x10000328) and AI record 0x130019F6 (0x100001FC); 0x340003D1 is in no 0x8E list
  (`entity_scripts(0x400005D2)` = [0x340001A6]) -> nobody runs it: Q / R / passive do nothing. The pet also never
  attacks (its 0x10000328 skill is not started for spawned entities, root cause 7). O: where the client binds
  0x340003D1 (the 0x130019F6 AI record, or the spawn flag 0x1000009C).
- R also does `SetSlotSkill [0x480009E1 1]` (second stage) -> not applied (root cause 6). 0x340003D1 waits
  0x1000011B / 0x1000009D (never raised).

## Sinestro 0x40000805 (0x3400046F / Q 0x3400046C / W 0x3400046A / E 0x3400046E / R 0x3400046B / P 0x3400046D)

Sim: all slots deal damage (S0 47, Q 74, W 100, E 170, R statuses + 75 / 47 from the construct's statuses).
- E Cull the Weak graph S2: `S0 -> S1 on 0x10000098` {0x09A6A765 = defeated unit; IsKind 8}: mini-cooldown +
  half Will refund on a champion takedown. 0x10000098 is raised only by script 0x340005D8 (another kit); ics raises
  no takedown events on kills (root cause 5). PvP only.

## Solomon Grundy 0x40000C44 (0x3400066C / Q 0x34000666 / W 0x34000665 / E 0x34000664 / R 0x34000663 / P 0x34000662)

Sim: S0 60, Q 110, W 160, E self status + grab (0x4800123C on the dummy champion), R VOT 2.5 / tick (OK).
- Passive Born on a Monday (C, severe): same pattern as Nightmare Superman: `SetDefeatType [1 0]` in S0, revival
  on `0x1000011B` (S0 -> S1: fake death 0x100001B9 (logged no-op), channel, undead S3), `S2 -> S0 on 0x10000016`
  (P: respawned). 0x1000011B never raised -> **Grundy cannot die** on ics.
- E The March (C): `SetSlotSkill [0x480010D6 1]` / `[0x480010DA 1]` (grab -> throw second stage) are not applied
  (`CastWorld.set_slot_skill` returns False). Uses 0x10000150 / 0x10000057 logged no-ops.
- R status 0x340006AA regen per champion hit counts `0x1000008A or 0x1000008B`; only 0x1000008B (basic) is raised.

## Stargirl 0x40000AEA (0x3400056A / Q 0x3400056E / W 0x3400056D / E 0x3400056C / R 0x3400056B / P 0x3400056F)

Sim: S0 50, Q 180, W big star only, E statuses (well 0x2E001153), R 183.
- W Shooting Stars (C): after the big star hits, graph S3 fires small stars every SmallStarTimer inside
  `IfThenElse(CanSee(-, TargetIID))`; `_can_see` (script_nodes.py) returns False for an unset observer operand, so
  the else branch runs (scriptlet 0x1000103B) and no 0x40000B18 is launched. Only 2 scripts use an unset observer
  (0x3400056D, 0x34000455). Fix: unset observer = the script's source / owner.
- W inner graph `S0 -> S2 on AnyOf(OnCastSignal 2, event 0x10000009)`, `S2 -> S0 immediately`: loops ~1000 times
  at the same instant (the result code 2 stays current while the plain transition re-enters) (C, VM: see 3).
- R Energy Conversion status 0x3400056B waits 0x1000008C (shield broken); passive Family Heirlooms 0x3400056F waits
  0x100000ED / 0x10000145 (damage family) and 0x10000007 (P: owner defeated) -> passive dead.

## Starro 0x40000A96 (0x3400052B / Q 0x34000530 / W 0x34000531 / E 0x3400052E / R 0x3400052D / P 0x34000532)

Sim: S0 51, Q 130, W Parasite status 0x48000E99, E REF 0x10000059 (NoTargets: needs Parasites, by design), R nothing.
- **Scriptlet flood still there** (C): 630-770 scriptlets (0x10000D93 / 0x10000D94) in every 3 s window. W 0x34000531
  graph S4 `any -> S1..S3 when SkillCharges == n` ([1, 0] plain transitions). The fase3-hk guard
  (`Region.check`, ANY_NO_REENTER) only skips when `code is None`, but the re-entry comes from `Region.finished` ->
  `check(code=COMPLETE)` / `check(code=RESULT_DONE)` after the re-entered state's chain ends. Verified: guarding
  every non-event check (`not t.sources and t.target == self.state and not use_event`) -> 0-5 scriptlets per window,
  same damage.
- R Mind Control (C): `S3 -> S1` needs `NOT AnyOf(HasFlagAttribute(target)[0x100009A3], [0x100007D9])`; 0x1000006A
  runs as the action `_mark` (always true in a condition) -> R never starts. With the fix (root cause 1) it marks and
  parasites the dummy champion (0x48001527, 0x48000E99).
- Parasite status 0x34000543: SetWorldState 0x1000010D, 0x10000172 / 0x10000174 logged no-ops; waits 0x100000ED,
  0x10000012; spawns 0x40000AA6 (no scripts).

## Supergirl 0x40000810 (0x34000481 / Q 0x34000483 / W 0x3400047F / E 0x34000482 / R 0x34000480 / P 0x3400047E)

Sim: S0 55, Q empowers the next basic (280), W 395, E self buff + cooldown, R champion-only (455 on the dummy).
- R waits `0x10000119` (S7,S8 -> S3; P: the carried target lost) besides the 0x10000022/14 pair ics raises.
- Basic-attack status 0x340004BE waits 0x1000008A (skill hit). Knockdown / knockup statuses 0x34000131 / 0x34000132
  use HasFlagAttribute (root cause 1).

## Superman 0x4000002B (0x3400000C / Q 0x340003D7 / W 0x340000F7 / E 0x340003D6 / R 0x340003D5 / P 0x340000F8)

Sim: S0 53, Q next basic 73, W 80, E 25, R nothing on minions (champion only), on the dummy only 0x4800083B.
- R Speeding Bullet (C): S1 is a wind-up (`S1 -> S6 on WindupTimer`) but `S1 -> S8 on OnCastSignal 2` wins: the
  cast's code 2 comes 0.15 s after the 0.25 s cast point (`start_cast`, CAST_RECOVERY) -> S8 = InterruptCooldown,
  the dash / carry never happens (root cause 3).
- E Heat Vision: `S3 -> S4 on HasFlagAttribute(target)[0x100007D9]` is always taken (root cause 1).
- Passive status 0x340003EE waits 0x1000008C (shield broken).

## Swamp Thing 0x40000B16 (0x3400057F / Q 0x34000582 / W 0x34000581 / E 0x34000584 / R 0x34000580 / P 0x34000583)

Sim: S0 62, Q missile 0x40000BB8 expires without a hit at 2 m (P: fire offset vs the close target), W spawn only,
E spawn only, R empowers the basic (122).
- E Earth Strike (C): S3 only `SpawnEntity 0x40000BCA` (template: stat block 0x48000534, world state 0x2E001170,
  no 0x8E list). Its gameplay script exists: **0x340005CB** (`S0 -> S2 on 0x10000049`, DelayTimer, FindTargets,
  damage, knockup / slow), referenced by no DID anywhere (only its own record). The class record 0x40000BCA itself
  (pack 0xA00002CF @0x24A86C, 936 bytes) is HFSM-shaped (variable MyTeam, nodes 0x1000000E / 0x10000026 /
  0x10000014): O, decode the 0x40 class records — ics only reads the 0x49 templates (`Data.entity_scripts`).
- W Husk (C): spawns 0x40000BCB (no scripts) and references 0x340005CD, which is not in data/script_trees (not
  decoded). The W graph waits 0x100000EB / 0x100000E2 (never raised).
- Passive Bio-regenerative Formula (C): `S3 -> S1 on 0x100000E7` {HealthDelta 0x004AC3A1, DamageType,
  ResponsibleIID 0x0335FDC4} (damage received) -> never raised -> passive dead.
- R uses SetCameraMode? 0x1000014B (logged no-op).

## The Joker 0x40000213 (0x3400011C / Q 0x3400010A / W 0x34000114 / E 0x34000111 / R 0x3400011B / P 0x34000110)

Sim: S0 50, Q 70, W / R missiles explode after their DelayTimer (damage lands after the window: OK), E statuses.
- W Surprise! (C): the shell spawns 4 chattering teeth 0x4000020B; their attack is template property 0x10000328 =
  0x34000116, never started for a spawned entity (only 0x8E scripts are) and no AI drives them -> teeth idle.
- Passive Sadist (C): `any -> S2 on 0x10000028 / 0x10000097 / 0x10000098` {0x09A6A765 defeated unit} (nearby
  defeat / kill / assist) -> buff 0x48000254 + cooldown cut: never raised (root cause 5).

## Wonder Woman 0x40000260 (0x3400017E / Q 0x34000185 / W 0x34000192 / E 0x3400018C / R 0x3400017D / P 0x34000189)

Sim: S0 58, Q stun on minions, 75 on the dummy champion (P: by design), W ally / self shield, E 200, R taunts
(0x480004BD) but no blast.
- R Blocking Bracers (C): S2 (taunt, `TauntTimer`) has `S2 -> S4 on TauntTimer` and `S3,S2,S4 -> S1 on
  OnCastSignal 2 [2, 1]`; S2's enter chain has no Cast, its plain end is reported by `Region.finished` as result
  code 2 (RESULT_DONE == the cast-done code) -> S2 ends at once, the blast S5 never runs. Verified: not delivering
  RESULT_DONE as a code -> S2 -> S4 (1.3 s) -> S5 -> S1 (root cause 3).
- W Protection status 0x34000191 waits 0x1000008C (shield broken). Q / W use HasFlagAttribute (root cause 1).
- Passive Child of Olympus waits 0x10000012 (O) besides the re-init family.

## Zatanna 0x4000015B (0x340000ED / Q 0x340000E9 / W 0x340000EC / E 0x340000EB / R 0x340000EA / P 0x34000107)

Sim: S0 46, Q spawn only, W champions only (by design), E 92, R nothing (also on the dummy).
- R Be a Rabbit (C): `S2 -> S4 on AnyOf(HasFlagAttribute(target)[0x100007D9], [0x100009A3])` always taken (root
  cause 1) -> fail path. Verified with the fix: the dummy champion gets 0x48000215 (CHMP). The rabbit status
  0x340000EE then needs SetWorldState 0x1000010D (logged no-op: no rabbit model) and SetSlotSkill
  [0x48001533] (rabbit basic attack, not applied).
- Q Skewer (C): only `SpawnEntity 0x400001E7` (no 0x8E list): same orphan-class case as Swamp Thing E.
- E shield status 0x340000F1 waits 0x1000008C; punish status 0x340000F0 waits 0x100000ED.
- Passive Stage Presence (C): TrackTeam 0x10000083 then `any -> S2 on 0x1000007C` / `S4 on 0x1000007B`
  {TeamMemberIID} (team member joined / left) to apply the aura; `_track_team` only stores a flag, no roster
  events -> passive dead. Also `any -> S1 on 0x10000007` (owner defeated) / back on 0x10000026 / 0x10000016.

## Zod 0x40000D29 (0x3400074D / Q 0x34000749 / W 0x3400074A / E 0x34000748 / R 0x3400074B / P 0x3400074C)

Sim: S0 54, Q next basic 94, W self statuses, E REF until RequiredBasicAttackCount basics (by design, counted on
0x1000008B), R nothing on minions, 0x480012F7 on the dummy.
- E Solar Surge (C): after the charge, inner graph S3 `S0 -> S1 on 0x10000196` {Slot} sets SkillExecuted and
  re-locks; 0x10000196 never raised -> once charged, E stays usable forever.
- W Relentless (C): `S0 -> S1 on 0x100001A4` {EffectCategory 0x008AABA3} (P: a CC applied to Zod) cuts W's
  cooldown; never raised.
- R Kneel Before Zod (C): `S3,S1,S4,S5 -> S2 on OnCastSignal 2` vs `S1 -> S5 on ChannelTimer` / `S5 -> S3 on
  FuseTimer`: the cast's code 2 at 0.4 s ends the channel (root cause 3). Spawns 0x40000E56 (FuseEntity; its
  template lists Zod's kit scripts in 0x10000328, no 0x8E).

## Already fixed in the working tree by the parallel audits (2026-10-25, not re-verified here)

0x100000ED on the damaged entity (no SkillSlot 0x31D944 param yet: Thorn Shield compares it with the basic slot),
0x1000008A {TargetIID, SkillSlot} on a Q/W/E/R hit (Nightwing P, Grundy R status, Supergirl), 0x10000196 {Slot}
skill-used broadcast (Shazam P, Zod E re-lock), death events 0x10000012 / 0x10000007 / 0x10000098 to the killer
(Sinestro E, Joker P partly, Robin / Zatanna cleanup).

## Root causes still open (ranked by champions of this set)

1. **HasFlagAttribute 0x1000006A runs as an action** (C, verified) - `script_runtime.HANDLERS[0x1000006A] = _mark`
   shadows the predicate `_has_marker`: `is_action` is true, so `run_condition` executes it and returns True in
   every condition (AnyOf / NOT / transition trigger). 40 scripts; 14 of these 18 champions reach it (shared stun /
   knockdown / knockup statuses 0x34000130/131/132: the stand-up graph event 0x100000AA after a stun is never
   sent). Breaks Starro R, Zatanna R (fail path), Superman E (always the S4 branch). Fix: remove 0x1000006A from
   HANDLERS (MARKER_HIT stays in `_has_marker`), or test PREDICATES before `is_action` in `run_condition`.
2. **Damage-pipeline events** (`script_nodes.deal_damage`, `combat.absorb`) - 0x1000011B {KillerIID 0x032C3FD4}
   when a type-0 defeat guard (0x10000162 [1 0]) stops lethal damage: Nightmare Superman and Solomon Grundy can
   never die and never trigger Possession / revival; 0x1000008C {VitalExpiredHandle 0x09E49315 = the temp-vital
   handle} when a shield is drained (Poison Ivy E, Superman P, Wonder Woman W, Zatanna E, Stargirl R);
   0x100000E7 {0x004AC3A1 health delta, DamageType, ResponsibleIID 0x0335FDC4} on the victim (Swamp Thing P);
   0x100001A6 {Amount 0x04846C54, DamageType} on a lifesteal heal (Raven P). 9 champions.
3. **Result code 2** (`script_runtime.Region.finished`, `start_cast`) - (a) a plain chain end is delivered as
   `check(code=RESULT_DONE)` = OnCastSignal 2, synchronously: Wonder Woman R taunt state ends at once (blast never
   runs; verified), Stargirl W inner graph loops ~1000x in one instant; but Nightwing R S1 (mount, RaiseGraphEvent)
   needs a code 2, so the fix is: deliver it once, after a delay, only for states that started an action
   (Cast / RaiseGraphEvent), never re-delivered to the states it leads to; (b) CAST_RECOVERY 0.15 s ends wind-ups /
   channels: Superman R (S1 -> S8 interrupt), Zod R. 4 champions.
4. **Spawned skill objects without behaviour** (`gamedata.entity_scripts`, `world.spawn_entity`) - classes with no
   0x8E list: NMS Q 0x400007F6, Swamp Thing E 0x40000BCA / W 0x40000BCB, Zatanna Q 0x400001E7, Star Sapphire Q / W;
   their scripts exist but nothing names them (0x340005CB Earth Strike, 0x34000448 for phantom missile 0x400007F7,
   0x340003D1 the Predator's brain). O: decode the 0x40 class records (HFSM-shaped). Also template property
   0x10000328 (unit attack) of spawned pets is never started and no AI drives it (Joker teeth 0x34000116, Predator
   0x34000391). 5 champions.
5. **Other events never raised** - 0x100000AF {Slot} (Poison Ivy P), 0x100001A4 {EffectCategory} (Zod W),
   0x10000097 / 0x10000028 kill / nearby defeat (Joker P, Nightwing P), 0x1000007B / 0x1000007C {TeamMemberIID}
   from TrackTeam (Zatanna P; `_track_team`), 0x100000D7 {StackCount} / 0x100000A8 {EffectDuration} on re-apply
   (Robin, Nightwing, Stargirl, Swamp Thing), 0x10000016 / 0x10000026 respawn (Grundy, Zatanna). 7 champions.
6. **SetSlotSkill 0x10000089** (`CastWorld.set_slot_skill` returns False): Grundy E, Star Sapphire R, rabbit basic
   0x48001533 (Zatanna R). 3.
7. **ANY_NO_REENTER guard** (`Region.check`, `code is None`) misses COMPLETE / RESULT_DONE re-checks: Starro flood
   (verified fix: drop `code is None`). 1 here, 17 scripts overall.
8. Logged no-ops that matter: SetWorldState 0x1000010D / 0x1000010E (rabbit model, Starro parasite), vitals link
   0x1000009E (Raven R). `_can_see` with an unset observer (Stargirl W small stars; fix: unset = owner).

## Status per champion (root-cause numbers above)

| Champion | Status |
|---|---|
| Nightmare Superman | Q (4), P unkillable (2); W/E/R OK |
| Nightwing | P partly (5: 0x10000097); R depends on 3's fix shape; rest OK |
| Poison Ivy | E shield never breaks (2), P (5: 0x100000AF); rest OK |
| Raven | P (2: 0x100001A6), R vitals link (8); rest OK |
| Robin | OK (slow stacks 5) |
| Shazam | OK if the 0x10000196 broadcast works; W touches 1 |
| Sinestro | OK |
| Solomon Grundy | P unkillable (2), E second stage (6); rest OK |
| Star Sapphire | Q, R, P (pet brain 0x340003D1, 4), W (4), R stage 2 (6); basic / E OK |
| Stargirl | W small stars (8 CanSee, 3 loop), R shield (2), P (5); rest OK |
| Starro | R (1), scriptlet flood in every slot (7); E by design |
| Supergirl | OK (R champion-only) |
| Superman | R (3b), E branch (1), P shield (2); rest OK |
| Swamp Thing | E, W (4), P (2: 0x100000E7); Q miss at 2 m (P, scene) |
| The Joker | W teeth idle (4), P partly (5) |
| Wonder Woman | R blast (3a), W shield (2); rest OK |
| Zatanna | R (1, then 6 / 8), Q (4), P (5), E shield (2) |
| Zod | R (3b), W (5: 0x100001A4); E fixed by the 0x10000196 broadcast |
