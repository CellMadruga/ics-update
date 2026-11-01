# Kit audit 2 (2026-10-25): Flash .. Nightmare Robin (18 base variants)

Champions: Flash 0x40000396, Gaslight Batman 0x40000086, Gaslight Catwoman 0x40000262, Gaslight Joker 0x4000038D,
Green Arrow 0x400006F9, Green Lantern 0x4000034D, Harley Quinn 0x4000054A, Hawkgirl 0x40000AE2, Huntress 0x40000CD3,
John Stewart 0x40000E57, Katana 0x40000BA6, Krypto 0x40000BE4, Lex Luthor 0x40000B70, Mecha Superman 0x4000063D,
Mecha Wonder Woman 0x40000483, Nightmare Batman 0x40000009, Nightmare Catwoman 0x40000CEA, Nightmare Robin 0x4000091B.

Method: `python tools\champion_check.py --only <variant> [--trace <slot>]` (headless Crime Alley v AI, current ics
with the fase3-hk..ho fixes on), `python -m ics.script_model <script>` for the trees, plus a scratch static scan of
every kit script (and the statuses / missiles / spawned objects it names) for: events its transitions wait for vs the
events ics raises, nodes the VM logs as no-op, scriptlet keys vs the entity's tables. Findings are appended per
champion, then grouped by root cause at the end. Confidence: C confirmed (simulated / read in the tree), P probable,
O open.

The scriptlet-key check was dropped: `Data.script_table` cannot parse several champion tables (Gaslight Batman's
0x1D0000E1 / 0x1D0001A1 / 0x1D000064 return None, yet Bat Scream 0x10000162 plays in game), so "key not in the
champion's tables" is a parser artefact; the champion is not filtered by `World.scriptlet` anyway.

Simulator verdicts (current ics, `champion_check.py --only`, 3 s window):

| Champion | S0 | Q | W | E | R |
|---|---|---|---|---|---|
| Flash | DMG | DMG | FX | FX | DMG |
| Gaslight Batman | DMG | DMG | DMG | DMG | DMG |
| Gaslight Catwoman | DMG | DMG | DMG | FX | DMG |
| Gaslight Joker | DMG | BUFF | DMG | FX | FX |
| Green Arrow | DMG | FX | FX | FX | FX |
| Green Lantern | DMG | DMG | FX | DMG | FX |
| Harley Quinn | DMG | CHMP | DMG | FX | DMG |
| Hawkgirl | DMG | DMG | FX | BUFF | CHMP |
| Huntress | DMG | FX | DMG | FX | FX |
| John Stewart | DMG | FX | FX | FX | FX |
| Katana | DMG | DMG | FX | REF | DMG |
| Krypto | DMG | FX | FX | FX | DMG |
| Lex Luthor | DMG | FX | FX | CHMP | FX |
| Mecha Superman | DMG | DMG | FX | FX | FX |
| Mecha Wonder Woman | DMG | DMG | FX | FX | FX |
| Nightmare Batman | DMG | DMG | FX | FX | CHMP |
| Nightmare Catwoman | DMG | DMG | DMG | DMG | FX |
| Nightmare Robin | DMG | DMG | BUFF | DMG | FX |

No exception and no "not implemented" node in any cast. Scratch tools (scratchpad, not in the repo): `kitscan.py`
(static scan), `seq.py` (cast sequences with state dumps), `evwho.py` (which scripts wait for an event).

## Per champion (RCn = root cause n below)

### Flash 0x40000396 (basic 0x3400021A, Q 0x3400021B, W 0x34000219, E 0x34000218, R 0x34000217, passive 0x34000216)
- Passive Speed Force never stacks (C, `seq.py` Q,W,E,Q,W,E: status 0x48000695 never applied). It gains a stack on
  **0x10000196** (`G1 T2 S0->S1`, never raised; RC1) or on 0x1000001D raised by E / R hits only. Its stack status
  0x3400022C waits for **0x100000D7** {StackCount} / **0x100000A8** {EffectDuration} (RC5); the decay state S2 calls
  AddStacks 0x100000D9 with the decremented count, which ics turns into more instances (RC5). Stacks are cleared on
  **0x10000012** (RC4).
- E Hyper Vibration: slows on its body collision (0x10000002; ics raises no champion-body collision, P), on a basic
  hit (0x1000008B, OK) or on a skill hit **0x1000008A** (RC2). E status 0x3400028F waits 0x100000A8 (RC5).
- R waits client event 0x10000023 (press / release, comes by 0x20EA in game; not simulated).

### Gaslight Batman 0x40000086
- All slots DMG. Passive Reverb 0x34000048 (stacks on 0x10000107 raised by the skills: OK) uses status 0x3400045A,
  which waits 0x100000D7 / 0x100000A8 (RC5); cleared on 0x10000012 (RC4). Basic logs 0x100000DD DestructionRaycast,
  R logs 0x10000078 (camera): no-ops.

### Gaslight Catwoman 0x40000262
- The kit has no passive script (slot 5 = 0).
- E 0x340001C6: the spawned 0x40000545 has no script (template unreadable, RC9); its reveal stage `G2 T3 S2,S0->S3`
  waits 0x1000008A / 0x1000008B (RC2 for the skill-hit half); 0x100000BA never raised (O).

### Gaslight Joker 0x4000038D
- E Snack Time 0x34000202 is a spell shield (attribute 0x10000627 ShouldBlockNextAttackerSkill); its payoff state S2
  (haste 0x4800082E + health back) waits **0x100000B3** "enemy skill blocked" (RC12: never raised, no block rule).
- R 0x34000201 ends on 0x10000007 (RC4); passive 0x34000203 clears on 0x10000012 (RC4); 0x100000D8 / 0x1000000E (O).

### Green Arrow 0x400006F9
- Q/W/E are quiver modes (owner block 0xCC = active quiver, read by the basic attack 0x34000411): FX and no
  cooldown are by design. R 0x3400040C is held (0x10000023 press / release from the client); its sub-scripts
  0x34000438 / 0x3400019E and the passive 0x34000412 wait **0x100000B6 / 0x100000B7** slot unavailable / available
  {SkillSlot} (RC11). R logs 0x10000022 / 0x10000056 (minimap ring) and 0x100000E5. Q's empowered graph waits
  0x100000ED / 0x10000145 (RC13).

### Green Lantern 0x4000034D
- **R spawns 0x40000359 with no script** (RC9): no damage. E's construct 0x40000350 spawns 0x40000CC8 with no script.
- Passive 0x340001E5: Will on kill waits **0x10000097 / 0x10000098** {0x9A6A765 = victim} (RC3); its CDR graph waits
  0x10000196 (RC1); its empowered-basic graph arms on 0x10000141 (raised by his missiles: OK) or 0x10000012 (RC4) and
  re-arms on 0x10000016 (O).

### Harley Quinn 0x4000054A
- Q champion-only (150 on the dummy), E ally / self target: by design v AI. Passive 0x34000340 waits 0x100000AF (O).

### Hawkgirl 0x40000AE2
- W 0x34000575 graph S2 waits 0x10000097 / 0x10000098 (RC3). R champion-only (375 on the dummy); R statuses 0x3400013B
  (ends on 0x10000007, RC4) and 0x340007D2 (waits 0x1000008C, O).

### Huntress 0x40000CD3 (resource vital 6 = bolts, max 3)
- **Q Snap Shot never damages** (C): `SpawnEntity 0x40000D1E` + `LaunchMissile($MissileIID, $BestTarget)`; the missile
  reaches the target but `R.Missile.arrive` raises the collision only on `self.instances`, never on the carried
  entity's scripts (0x34000739 waits 0x10000002 in S3) -> "missile gone" (RC7).
- E: bolt 0x3400073B `G0 T2` uses predicate 0x10000048 (always false in ics, O).
- Passive 0x34000709: skill-use gate waits 0x10000196 {Slot} (RC1); bolt FX wait **0x100000EF / 0x100000F0**
  {NewValue} (vital changed, RC10).

### John Stewart 0x40000E57
- Placeholder kit (unreleased; four identical scripts: cooldown + spend, no effect). Nothing to fix.

### Katana 0x40000BA6
- E REF by design (Soultaker 0x340005B9 holds disable 0x10000066 until its hit events). The passive resets on
  0x10000017 / 0x10000007 (RC4), waits 0x100000B6 (RC11) and has 8 SetSlotSkill (form swap; `CastWorld.set_slot_skill`
  not mapped). W status 0x340005D5 waits 0x100000D7 (RC5). R logs 0x10000151.

### Krypto 0x40000BE4
- Q is two-stage (throw the stick 0x40000BF2, recast = fetch + 65 dmg, C). The stick has no 0x8E list by design and
  the RaiseEvent target 0x3400060C exists in no pack (references only). W / E: statuses (FX by design); E status
  0x3400061D ends on 0x10000007 (RC4).

### Lex Luthor 0x40000B70
- W damages over time (11 / tick; the probe does not credit it): OK. E champion-only.
- **R Orbital Remediation: no damage** (C). The satellite 0x40000BE5 (0x340005ED) runs
  `LoadSkillStats($ShooterIID, ...)` on spawn, but `CastWorld.spawn_entity` sets ShooterIID only at launch
  (`Missile.start`): damage and hotspot time are 0. Its S6 exit chain `LaunchMissile(SELF)` raises 0x10000049 while
  the region is still leaving S6; the polled timer transition fires again -> 23 missiles at once (RC8).
- Q drone 0x40000BCF: no 0x8E by design (run by 0x340005D8); it waits 0x100000CC (O) and 0x100000ED (RC13).

### Mecha Superman 0x4000063D
- **E wall 0x40000647 has no script** (RC9), and Superman's `RaiseEvent [0x1000005F 0x340001C5]` names a script that
  exists in no pack. Sunstones 0x40000646 (0x34000167) wait 0x1000001D from Superman (OK). R ends on 0x10000007 (RC4);
  passive waits 0x1000011E (O). E logs 0x1000017E.

### Mecha Wonder Woman 0x40000483
- R Tempest: hotspot status 0x48000829 (0x34000318: VOT inside a cone) was never applied in the window (O); its reveal
  branch waits 0x10000145 (RC13). Q's thrown object 0x340002F7 waits 0x100000B2 (O). Passive status 0x34000303 waits
  0x100000D7 (RC5). W 0x340002CA flips S0 <-> S3 every tick while idle (a never-started timer counts as expired;
  no chain there, harmless).

### Nightmare Batman 0x40000009
- R champion-only (112 on the dummy). E 0x340000C9 ends on 0x10000012 (RC4). Q missile 0x3400000B: apex state S7 waits
  **0x10000106** (RC14).

### Nightmare Catwoman 0x40000CEA
- **R spawns 0x40000D2B with no script** (RC9): no damage.
- Passive 0x34000727 (empowered basic + slow 0x48001299) arms only on 0x10000196 (RC1); slow status 0x34000742 waits
  0x100000D7 / 0x100000A8 (RC5).
- Q whip 0x34000743: the return hit (S10 / S11, ApplyDamage) waits **0x10000106** (RC14), 0x10000119 (O).

### Nightmare Robin 0x4000091B
- **R Feed the Beast ends at once** (C, also on the dummy champion): S7 `AddSkillTarget(SELF, SELF)` +
  `SetSkillAttached(SELF)[0]`; `_attached_skill` drops the entity itself from the targets -> 0x10000014 -> S2 (RC6).
- Q spawns 0x40000CA4 with no script (RC9); its missile 0x340004E3 waits 0x10000106 (RC14).

## Root causes (ranked by how many of these 18 champions they touch; "global" = scripts in all 875)

Event meanings below are inferred from the trees (P) unless marked C; none of these events is raised by any script
(RaiseEvent / PostEventDelayed), so the server engine must raise them.

| RC | Problem | Champions here | Global | Fix (file:function) |
|---|---|---|---|---|
| 4 | 0x10000012 (P "owner died": clear stacks / end buffs) and 0x10000007 (P "status ended by death / cleanse") never raised; `World.damage` says "its statuses run out on their own" | Flash, G.Batman, G.Joker, GL, NM Batman, Hawkgirl, Katana, Krypto, M.Superman (9) | 19 + 46 scripts | `ics/world.py World.damage` at death: `raise_event(ch, 0x10000012)`, then 0x10000007 on each status instance of the dead entity and remove them |
| 5 | Status stacking: ics keeps one instance per stack and re-raises 0x10000006 on refresh; the scripts keep one instance and wait 0x100000D7 {StackCount} (stacks changed) / 0x100000A8 {EffectDuration} (refreshed); AddStacks 0x100000D9 gets the absolute count (Flash S2 passes the decremented count, ics adds that many instances) | Flash, G.Batman, G.Joker, NM Catwoman, MWW, Katana (6) | 9 / 10 scripts | `ics/script_runtime.py apply_status`: one instance per DID; a re-apply raises 0x100000D7 {StackCount: n} (n capped at max stacks) or 0x100000A8 {EffectDuration}; `ics/script_nodes.py _add_stacks`: set the count |
| 9 | Spawned skill objects with no server script: their 0x49 template has no 0x8E list (checked to the pack end) and `Data.record` cannot read them: GL R 0x40000359, GL E 0x40000CC8, G.Catwoman E 0x40000545, M.Superman E 0x40000647 (+ RaiseEvent target 0x340001C5, in no pack), NM Catwoman R 0x40000D2B, NM Robin Q 0x40000CA4 | GL, G.Catwoman, M.Superman, NM Catwoman, NM Robin (5) | + the 18 in champion-kits-status.md 2 | O: RE where these classes get their behaviour (class record 0x40 / another property); until then nothing to wire |
| 1 | 0x10000196 {Slot} "a skill was used" broadcast to the caster's scripts (C from Huntress 0x34000709 S2 `SetVariable(SkillSlot, #Slot)`) | Flash (stacks), GL (CDR), Huntress (passive gate), NM Catwoman (empowered basic + slow) (4) | 13 scripts (Shazam, Blue Beetle, Arcane Supergirl passives, Zod E) | `ics/script_runtime.py activate` (after 0x1000001D) or `World.cast`: for slots 1-4 `raise_event(world, owner, 0x10000196, {"Slot": slot})` |
| 14 | 0x10000106: a returning (tethered) missile reached its apex (C from NM Catwoman Q 0x34000743 T17 -> S10 MissileReturning = 1 -> return hit) | NM Batman, NM Catwoman, NM Robin (3) | 4 | `ics/script_runtime.py Missile` (fly_to / expire of a tether): raise 0x10000106 on its instances when it turns back |
| 13 | 0x100000ED / 0x10000145 (P "about to take damage" / "took damage from a champion") never raised | Green Arrow, Lex (drone), MWW (3) | 33 / 8 | `ics/script_nodes.py deal_damage`: raise on the target before / after `world.damage` |
| 2 | 0x1000008A {TargetIID, SourceSkill} "a skill hit" (the 0x1000008B twin for slots 1-4) | Flash E, G.Catwoman E (2) | 21 (AWW, Catwoman, AGL, Blue Beetle, Atrocitus, Atomic Joker, Dex-Starr, Nightwing passives) | `ics/script_nodes.py _apply_damage`: when `_damage_slot(inst)` in 1..4 and dealt, `raise_event(w, src, 0x1000008A, {"TargetIID": target, "SourceSkill": slot})` |
| 3 | Kill events: 0x10000098 {0x9A6A765 = victim} "you killed it" (C: Lex drone 0x340005D8 raises it on its killer) and 0x10000097 (P champion takedown / assist) | GL passive (Will), Hawkgirl W (2) | 12 / 10 (Batman W, Doomsday, Joker, Nightwing, Sinestro) | `World.damage` at death: raise 0x10000098 on the killer's scripts (missile owner resolved as now), 0x10000097 for champion kills (P) |
| 11 | 0x100000B6 / 0x100000B7 {SkillSlot} slot unavailable / available (C, client 0xa2a1b0 raises them from 0x20F9) | Green Arrow, Katana (2) | 7 / 12 | raise them on the server's own scripts wherever a slot is disabled / enabled (SetDisableCondition 0x100000FB, silence, cooldown end) |
| 6 | `_attached_skill` excludes the entity itself: `AddSkillTarget(SELF, SELF)` + `SetSkillAttached(SELF)` always gets 0x10000014; `skill_targets` is never cleared | NM Robin R (1) | same S7 pattern: AWW R, Atrocitus E, Doomsday E, Zatanna R | `ics/script_nodes.py _attached_skill`: count SELF as a valid target; clear `skill_targets` after raising |
| 7 | `Missile.arrive` raises the collision only on `self.instances`; a carried entity (SpawnEntity + LaunchMissile at a unit) never gets it (C) | Huntress Q (1) | Blue Beetle E, 0x34000486 | `ics/script_runtime.py Missile.arrive`: as `collide()`, `raise_event(world, carried, EVENT_COLLISION, hit)` when carried and no instances |
| 8 | Spawned entities get ShooterIID only at launch; and events raised from an exit chain re-fire the state being left (C) | Lex R (1) | any spawned entity reading $ShooterIID on 0x10000049 | `ics/world.py CastWorld.spawn_entity`: `inst.vars_by_name("ShooterIID", owner)` before `start_script`; `ics/script_runtime.py Region`: ignore transitions of a state while its exit chain runs |
| 10 | 0x100000EF / 0x100000F0 {NewValue} vital changed (resource vital) | Huntress (1) | 2 (+AWW passive) | `ics/world.py CastWorld.set_vital` / `spend_by_vital`: raise on the owner (P: F0 up, EF down) |
| 12 | Spell shield attribute 0x10000627 (block the next enemy skill) has no rule; payoff event 0x100000B3 never raised | G.Joker E (1) | 4 | `deal_damage`: an enemy skill hit on a target with 0x10000627 > 0 is cancelled and 0x100000B3 raised on it |

Not problems: re-init family 0x1000000C / 0x100000A9 / 0x100001B3 / 0x10000192 / 0x10000197 (0x10000008 is raised);
0x10000023 (client 0x20EA); logged no-ops 0x10000195 (every skill), 0x10000057, 0x10000075, 0x100000DD, 0x10000151,
0x10000114, 0x1000017E, 0x10000078, 0x100000E5, 0x10000135, minimap rings (cosmetic or client-side). Open singles:
0x100000AF (Harley passive), 0x100000BA (G.Catwoman E), 0x100000D8 / 0x1000000E (G.Joker), 0x10000016 (GL passive),
0x1000008C (Hawkgirl R status), 0x100000CC (Lex Q), 0x100000B2 (MWW Q), 0x1000011E (M.Superman passive),
0x10000119 (NM Catwoman Q), predicate 0x10000048 (Huntress E bolt, always false), MWW R hotspot status not applied.

