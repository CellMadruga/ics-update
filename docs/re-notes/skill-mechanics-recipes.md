# Skill mechanics recipes (2026-10-25)

Implementable recipes for the general mechanics still open after fase3-hs (kit-audit-1/2/3.md, CHANGELOG
fase3-hp..hs). Each recipe: evidence (C confirmed in the trees / simulator, P probable, O open), the exact change
(file:function), and before / after results from a scratch driver that monkeypatches the change into the current
ics (scratch scripts are not in the repo). Baseline: `python tools\champion_check.py` = DMG 136, BUFF 13, CHMP 13,
FX 104, REF 4 (54 base variants).

Scratch tools used (session scratchpad): `scan.py` (all 875 trees: `wait <event>` = scripts whose transitions wait
for it, `node <type>` = every use of a node with its operands, `raise <event>` = RaiseEvent / PostEventDelayed
users), `harness.py` (champion_check's Crime Alley v AI setup with cast sequences and state dumps), one
`fix_*.py` per recipe (the monkeypatch).

## 0. Simulator gap found on the way (C)

`tools/champion_check.py` never sets `R.STATUS_RESOLVER` / `R.STACKS_RESOLVER` (ics/server.py does), so in the
simulator every status is max-1 (refresh) and its script comes only from the RECORD_RESOLVER fallback. With the
server's resolvers (`cc.py` wrapper): same totals except Huntress R FX -> BUFF. Fix: in `champion_check.main`, after
`R.SCRIPT_RESOLVER = data.entity_scripts`, add `R.STATUS_RESOLVER, R.STACKS_RESOLVER = data.status_script,
data.status_max_stacks`. Baseline with it: DMG 136, BUFF 14, CHMP 13, FX 103, REF 4 (all "after" numbers below use it).

## 1. Status stacking (C for the shape, P for the exact event params)

Evidence:
- 9 status scripts wait for 0x100000D7, 10 for 0x100000A8 (`scan.py wait`). Shape (Flash 0x3400022C, Robin
  0x34000330, Gaslight Batman 0x3400045A, Nightmare Catwoman 0x34000742): outer graph `S0 -> S1 on 0x10000006` sets
  up the modifier / icon, inner graph `S0 -> S1 on 0x100000D7` does `SetVariable(StackCount, #StackCount)`,
  modifier = Amount * StackCount, `UpdateStatusIcon(.., StackCount, ..)`; `S? -> S2 on 0x100000A8` does
  `SetVariable(EffectDuration, #EffectDuration)` + icon update. 0x34000320 (haste 0x4800082E, max 99) reads
  `#DurationDelta` on 0x100000A8. Robin's first inner state reads `#StackCount` from the 0x10000006 itself.
- **189 status scripts have `S1 -> S0 on 0x10000006`** (running -> idle; `reapply.py`), 298 `S0 -> S1`. A re-sent
  0x10000006 therefore switches a running status OFF (C, simulated: Robin slow 0x4800084B, 3rd apply leaves the
  first instance in S0 with its modifier removed). The engine never re-sends 0x10000006 to a running instance.
- The stack owners count with GetStackCount 0x100000FE and decay with AddStacks 0x100000D9 [status, 1] passing
  `--GetStackCount` (Flash passive 0x34000216 S2, Gaslight Batman 0x34000048 S2), RemoveStatus at 0: **AddStacks
  sets the absolute count** (P, strong). Max stacks = property 0x10000063 (0x48000695 = 10, 0x48000A92 = 10,
  0x4800084B = 2, 0x48001299 = 3, 0x48000FA9 = 3 ...; 49 statuses with max > 1, `stk.py`).
- Today (server resolvers): one instance per use, each runs the whole script (Flash: 5 casts = 5 instances, each
  with its own haste modifier and icon); the decay's AddStacks(count - 1) ADDS instances (Flash 5 -> 10 after 6 s).

Change (`ics/script_runtime.py`):
- `apply_status(world, source, target, status, params, skill_world=None, count=None)`: a status whose script waits
  for 0x100000D7 or 0x100000A8 ("counted", cached per script DID from its transitions), or any max-1 status, keeps
  ONE instance with `inst.stack_count`. First apply: as now, with `params["StackCount"] = 1` (or `count`).
  Re-apply: `new = count if count is not None else old + 1`, clamped to [0, max]; 0 -> `remove_status`; reset the
  expiry (`_expire_at`) when EffectDuration > 0; raise 0x100000D7 {StackCount: new, EffectDuration} if the count
  changed, then 0x100000A8 {EffectDuration, DurationDelta: new - left}; never 0x10000006. Non-counted statuses with
  max > 1 (shot trackers 0x48000AB0 / 0x34000470, 99) keep one instance per use.
- `set_status_duration`: raise 0x100000A8 {EffectDuration, DurationDelta} on counted scripts.
- `ics/script_nodes.py _add_stacks`: `apply_status(..., count=<operand 6>)` once (absolute), drop the loop;
  `_stack_count`: sum of `stack_count` of the running instances.
- Config: `[ics] status_stack_model = true` (false = one instance per use + re-sent 0x10000006, today).

Proof (`fix_stacks.py` + `t_stack.py`):

| Case | Before | After |
|---|---|---|
| Flash Q W E Q W E -> 0x48000695 | 5 instances x 1 stack; decay grows to 10 instances (haste 6.84) | 1 instance, stacks 1..5 (MaxStacks 5), decays 5 -> 4 -> 3 -> 2 over 8 s (haste 6.34 -> 6.04) |
| Gaslight Batman Q W E Q -> 0x48000A92 | 2 instances, 10 after 8 s | 1 instance x 2, gone after 8 s |
| Robin slow 0x4800084B applied x3 | 2 instances, the first switched off (S0) | 1 instance, stacks 1 -> 2 (max 2), inner S1 |
| champion_check (54) | DMG 136 BUFF 14 CHMP 13 FX 103 REF 4 | identical (no slot verdict / damage changed) |

Status -> script -> applier (checked): 0x48000695 / 0x3400022C Flash passive; 0x48000767 / 0x3400028F Flash E,
0x34000450, 0x34000654; 0x48000A92 / 0x3400045A Gaslight Batman passive; 0x4800082E / 0x34000320 haste (Gaslight
Joker E 0x34000202, Nightwing 0x34000796, 0x34000399, 0x340003BA); 0x48001299 / 0x34000742 Nightmare Catwoman
passive; 0x48000806 / 0x34000303 Mecha Wonder Woman 0x340002C7; 0x48000FA9 / 0x340005D5 and 0x48000F87 / 0x340005C9
Katana; 0x4800084B / 0x34000330 Robin basic; 0x480012F3 / 0x3400076D (applied by 0x34000587); 0x480007B6 /
0x340002C5 Atomic GL passive; 0x4800119B / 0x3400070E Dex-Starr 0x340006B9; 0x480007EF/F0 / 0x340002F3 (max 1,
refresh only). Stargirl's 0x340006C5 / 0x340006C8 have no ApplySkill caller (hotspot / aura statuses).


Baseline for sections 2 on (champion_check now sets the resolvers itself, sections 0 / 1 in the code): BUFF 14,
CHMP 12, DMG 137, FX 103, REF 4. **Lex Luthor R flips between FX and DMG from run to run** (3 baseline runs: 1 FX,
2 DMG; the satellite's timing), so a +-1 DMG / FX on Lex alone is noise. Scratch for these sections: `r2/` in the
session scratchpad (`slots.py`, `fix_slots.py`, `t_slots.py`, `t_slots2.py`, `diff.py`, ...).

## 2. SetSlotSkill 0x10000089 / its revert 0x1000008E (C for the slot and the revert, P for the flag)

Evidence (`r2/slots.py`: all 16 nodes in the 875 trees (kit-audit-1 counted 17), with the named record):
- The target slot is **property 0x100000E6 inside the record's skill block** (0x1000003F, as the kit record's slot
  blocks 0x100008E3.. / 0x100008EF carry it) (C: every record's value matches the slot its swap is meant for):
  | Caller (slot) | Record -> 0x100000E6 slot, script | Flag |
  |---|---|---|
  | Aquaman W 0x34000396 / E 0x3400037A / Q missile 0x34000393 | 0x48000959 / 0x4800097E / 0x48000956 -> 4, 0x3400039F / 0x340003A4 / 0x3400039D | 1 |
  | Blue Beetle Q / W / E 0x34000451 / 454 / 455 (graph S2, while owner flag 0xE8) | 0x48000A97 / A95 / A96 -> 1 / 2 / 3, 0x34000453 / 452 / 450 | 0 |
  | Catwoman R status 0x3400028E | 0x4800077A -> 3, 0x3400027B | 0 |
  | Katana passive 0x340005B9 (4 stances) | 0x48000F9C / FAA / FA2 / F9E -> 3, 0x340005B5 / BC / BD / BE | 1 |
  | Solomon Grundy E 0x34000664 | 0x480010D6 -> 1 (0x3400069E), 0x480010DA -> 2 (0x340006A6) | 1 |
  | Star Sapphire R 0x3400038B, Arcane Harley E 0x34000778 | 0x480009E1 / 0x48001308 -> 4 / 3, **no script** (stats 18=1 23=500) | 1 |
  | Zatanna R rabbit status 0x340000EE | 0x48001533 (no skill block), slot from operand 2 = $BasicAttack | 1 |
  The caller's own slot is right for 5 (Blue Beetle x3, Star Sapphire, Arcane Harley), wrong for 9 (Aquaman's W / E /
  Q missile set R; Katana's passive sets E; Grundy's E sets Q and W), and the 2 status callers have none.
- **0x1000008E (ics: ClearSkillStatOverride) is also the swap's revert**: every script that swaps (or is swapped in)
  calls it on the same slot: the empowered Aquaman R scripts 0x3400039D / 39F / 3A4 `node_1000008E(SELF)[4]` in a
  graph `S0 -> S1 when NOT NeedCleanup AND (SkillTimer expired OR SkillExecuted)`; Blue Beetle Q/E in graph S2's exit
  (flag 0xE8 off) [1] / [3]; Catwoman status [3]; Katana [3]; Grundy [1] [2]; Harley E S2 exit [3]; Star Sapphire [4];
  rabbit [0] (C, `scan.py node 0x1000008E`). Shazam's SetSkillStatOverride 1..3 is cleared by the same node.
- **A scriptless record keeps the slot's running HFSM** (C): Arcane Harley E S2 (glamour active) still has
  `S0 -> S1 on 0x1000001D` -> RaiseEvent(decoy)[0x10000141 0x3400077C]: the second press commands the decoy; the
  record only changes range / radius (18 / 23) and the icon.
- An empowered record carries only the stats it changes (0x48000959: 18, 30); the empowered script's
  LoadSkillStats asks for 3 / 15 / 1 / 12 / 14 too: without the base slot's stats SkillDuration = 0, its timer runs
  out at once and graph S2 reverts the slot before any cast (C, simulated). So **stats = base slot's stats updated
  with the record's** (P, the only reading that works).
- 0x100000A9 {SkillSlot, 0x17AF14 = new HFSM} is waited for by 66 scripts (`scan.py wait`); Aquaman's base R
  0x34000397 graph S1 uses it to drop its own disable condition 0x10000066 on slot 4 when the new HFSM is not the
  basic one; the others only reload stats. Flag 1 / 0: O (Blue Beetle and Catwoman, flag 0, move the cooldown
  themselves with TempTimerHolding / StartCooldown; P: 0 = the swap does not carry the slot's cooldown).

Change:
- `ics/script_nodes.py _set_slot_skill`: slot = operand 2 when set (`$BasicAttack`), else
  `records.get(blk, 0x100000E6)` of the record's 0x1000003F / 0x100008E5 block (new `Data.item_skill_slot(did)`), else
  `inst.slot`; call `CastWorld.set_slot_skill(ent, slot, did)`.
- `ics/world.py CastWorld.set_slot_skill(ent, slot, did)`: `sk = data.item_skill(did)`; remember the base
  `(ent.kit[slot], ent.skill_insts[slot])` once in `ent.slot_base[slot]` and **do not stop the base instance** (it
  keeps running and getting events: Blue Beetle's Q runs the revert in its own exit, Aquaman's base R listens for
  0x100000A9). With a script: `new = copy(sk)`, `new.slot = slot`, `new.stats = base.stats | sk.stats`,
  `ent.kit[slot] = new`, `ent.skill_insts[slot] = R.start_script(V.load(new.script), ent, CastWorld(w, ent, new),
  slot=slot)` (a later swap of the same slot stops the previous override first). Without a script: only
  `ent.kit[slot]` = the base skill with the record's stats (same instance). Then raise 0x100000A9 {"SkillSlot": slot,
  0x31D944: slot, 0x17AF14: new script} on the owner's scripts. Client: send the slot's skill record / icon (slot table
  property 0x100008E3.. by 0x6, full-combat-skills.md 0x10000089; not simulated).
- `ics/script_nodes.py _clear_stat_override`: besides the stat overrides, when `slot in ent.slot_base`, schedule
  (`CastWorld.after(0, ..)`: the caller may be the override itself) the revert: stop the override instance, restore
  kit / instance, raise 0x100000A9 with the base script. `World.cast` needs no change (it reads kit / skill_insts).
- Config: `[ics] slot_skill_swaps = true`, `slot_swap_merge_stats = true`.

Proof (`r2/fix_slots.py`, `t_slots.py` / `t_slots2.py`, casts at a minion or the dummy champion):

| Case | Before | After |
|---|---|---|
| Aquaman R, W, R, R | R refused 0x10000066 every time | R refused; W hits -> slot 4 = 0x3400039F; R dash + 58 dmg; slot reverted; next R refused (one empowered use per hit) |
| Blue Beetle R, Q, R, Q | Q = Energy Cannon both times (125, missile) | R on: Q/W/E -> 0x34000453 / 452 / 450, Q = dash form 90 dmg; R off: all three restored, Q = cannon 125 |
| Solomon Grundy E (grab the dummy), Q, E, W | Q 145, W 100 (base skills) | E sets Q -> 0x3400069E, W -> 0x340006A6: Q 160, W 75 |
| Catwoman R, E | E = 0x3400027A | E = Acrobat 0x3400027B |
| Star Sapphire R, R / Arcane Harley E, E | as before | as before (same HFSM; stats overlay only) |
| champion_check (54) | BUFF 14 CHMP 12 DMG 137 FX 103 REF 4 | BUFF 16 CHMP 12 DMG 138 FX 101 REF 3: Aquaman R REF -> DMG (75), Catwoman R FX -> BUFF, Arcane Harley R FX -> BUFF (R itself unchanged: the probe's follow-up basic, P side effect of E's overlay) |

Katana's stance swaps (passive, slot 3) were not reached in the 3 s windows (Soultaker holds 0x10000066 until its hit
events: by design). Expected gain beyond the simulator: Aquaman R usable at all, Blue Beetle's whole R, Grundy's E
second stage, Katana's E stances, Catwoman R's E.

## 3. Local frame convention: +Y forward (C for offsets, P for the lateral sign and the point yaw)

Timing first, in two lines: the VM's delays are seconds, not frames (StartTimer / PostEventDelayed take stat
durations such as 14 = 1.5; DestroyEntity's f32 0x3E4CCCCD = 0.2 s; only cinematic scene events are frame / fps, and
ics already divides them). Nothing to change there; the open "frames" item is the coordinate frame.

Evidence (`r2/frames.py`, every 0x38 transform node "frame (+) local offset" in the 875 trees):
- 41 constant offsets in 33 scripts are `vec3(0, d, 0)` with forward names: `$KnockbackDistance`, `$Distance`,
  `$SkillRange`, `$BeamLength*0.5`, Batarang's `vec3(0, -0.5, 0)` "behind" test (0x3400003F); only 2 are pure X, both
  `$WallWidth / 2 + 0.5` and its negation (0x340003F1: the wall's two ends, lateral). 3 more swap a fire offset's
  components into `vec3(y(off), x(off), z)` (0x340004DB / 4DC / 5A9). ics's `_transform` rotates with local +X
  forward, so every "d metres ahead" lands d metres to the side.
- Simulated: Arcane Supergirl Q missile flew ~77 deg off (kit-audit-1) and Swamp Thing Q's missile expired at 2 m.
- Heading of a plain point (0x40 on `$TargetPosition`): 3 scripts (0x3400054E, Swamp Thing Q 0x34000582, 0x340006B6);
  ics returns atan2 of the absolute coordinates. Giving the client point the caster -> point yaw changes nothing in
  the simulator (the harness always faces the target) but is the only meaningful value (P).

Change (`ics/script_runtime.py`):
- `_transform`: `f = (cos r, sin r)`, lateral `l = (sin r, -cos r)` (local +X = right, P: only symmetric uses);
  `p = pos + ox * l + oy * f`, z added.
- `activate(inst, target, point)`: a plain point becomes `Frame(point, degrees(atan2(point - caster)))` (caster's own
  heading when the point is the caster's position).
- `_with_heading` on a plain vector: left as is (it is used for world directions, not offsets; O).
- Config: `[ics] frame_forward_y = true`, `target_point_yaw = true`.

Proof (`r2/fix_frames.py`; FRAMES=offset / point to split the two halves):

| Case | Before | After |
|---|---|---|
| Arcane Supergirl Q (minion 3 m) | missile, 0 dmg | 70 dmg (offset half alone; point half alone: 0) |
| champion_check (54) | BUFF 14 CHMP 12 DMG 137 FX 103 REF 4 | BUFF 14 CHMP 12 DMG 139 FX 101 REF 4: Arcane Supergirl Q FX -> DMG 70, Swamp Thing Q FX -> DMG 40; Dex-Starr R 57.5 -> 107.5, Atomic Joker R 22.5 -> 29.4; no verdict lost; identical with the point half off |

## 4. Ratio damage: the stat's scaling block (C for the record layout, P for GetAttribute modes)

Evidence (`r2/statblk.py`, `r2/ratios.py` over the 54 kit records, 543 scaled stats):
- A stat entry of 0x100004B4 is `{0x100004B6 stat id, 0x100004D3 base block, 0x100004D4 scaling block}`; each block
  is `{0x100004B7 value, 0x100004D2 per rank, 0x100004D7 formula 0x3B..}`. The base block's formula is the rank curve
  0x3B0000CA (Linear(Rank, Base, Delta)); the scaling block's is an attribute formula (units-and-ai.md 3.4). Example
  Aquaman Q stat 5: base 50 (+25 / rank) + scaling 0.3 x 0x3B0002EA.
- `Data.kit` / skills.tsv / `Data.item_skill` read `0x100004D3 or 0x100004D4`: the scaling term is dropped
  everywhere, and when the base block is empty (`0x100004B7` None) **the scaling Mod is read as the flat value**:
  Atomic Joker Q stat 5 = 0.5 and stat 1 = 1.25 (formula 0x3B000360 = AttackDamage(mode 0) x Linear(Rank, Mod,
  Delta)), Dex-Starr W stat 1 = 0.7. The tooltip copies (stats 20 / 12 = 0.5 / 1.25 on the rank curve) are the raw
  ratios; the missile 0x340004FE loads 5 / 1 as Damage / BounceDamage and hands them to ApplyDamage (C).
- Formulas used by damage-like stats (count of stats): 0x3B0002E6 PowerDamage 0x10000B75 mode 1 x Mod (87 + 29 +
  ...), 0x3B0002EA AttackDamage 0x10000B76 mode 1 x Mod (74 + 23 ...), 0x3B00010B health 0x10000426 mode 1 x Mod (10
  + ...), 0x3B000149 Will 0x10000432 mode 1 x Mod, 0x3B0002E8 AttackDamage mode 0 (Gaslight Catwoman W, Huntress Q,
  Mecha Wonder Woman Q), 0x3B000203 health mode 0 x Mod (Grundy), 0x3B000360 / 0x3B0002EE mode 0 / 1 x Linear,
  0x3B0002E9 / 0x3B0002D0 negated. Cooldown (stat 15, 231 entries) has a scaling block with formula 0x3B00010A
  (attribute 0x10000B7B cooldown reduction) and no value: O (multiplicative, not added); stat 31 0x3B000226 = 2 - CDR
  (O). ics's GetAttribute modes are 0 current, 1 bonus (current - base), 2 base (combat.attribute; P): with no items
  the mode-1 terms are 0, so only the mode-0 formulas change numbers in the simulator.

Change:
- `ics/gamedata.py`: keep both blocks per stat: `Skill.scaling[stat] = (mod, per, formula)` and the base from
  0x100004D3 only (0 when its value is None) - in `Data.kit` (catalog row + the kit record's slot block, matched by
  0x100000E6), `Data.item_skill`, `Data.stolen_power`; table `SCALING_FORMULAS = {0x3B0002EA: (0x10000B76, 1, +1),
  0x3B0002E6: (0x10000B75, 1, +1), 0x3B0002E8: (0x10000B76, 0, +1), 0x3B000360: (0x10000B76, 0, +1), 0x3B0002EE:
  (0x10000B75, 1, +1), 0x3B0002E9: (0x10000B76, 1, -1), 0x3B00010B: (0x10000426, 1, +1), 0x3B000203: (0x10000426, 0,
  +1), 0x3B000149: (0x10000432, 1, +1), 0x3B0002D0: (0x10000432, 1, -1)}` (or a 0x3B expression evaluator,
  units-and-ai.md 3.4). tools/catalog_scan.py / roster: write `5=0(+0/rank)+0.5(+0.1/rank)*0x3B000360` so the
  catalog stops showing the ratio as the value.
- `ics/world.py CastWorld.skill_stat` / `slot_stat`: `value = base + per * (rank - 1) + sign * (mod + mod_per *
  (rank - 1)) * combat.attribute(caster, attr, mode)` for stats with a scaling entry (cooldown / stat 31 untouched).
- Config: `[ics] stat_scaling = true` ("flat_only" = fix only the stats with no base block).

Proof (`r2/fix_ratio.py`, `t_ratio.py`; Atomic Joker level 6, rank 1: AttackDamage 62.5 current, 0 bonus):

| Case | Before | After |
|---|---|---|
| Atomic Joker Q Hot Potato: Damage / BounceDamage | 0.5 / 1.25 (2 hits = 1.8) | 31.25 / 78.1 (109.4) |
| champion_check, RATIO=flatfix | DMG 137 ... | same verdicts; Atomic Joker Q 1.8 -> 109.4 |
| champion_check, RATIO=all | BUFF 14 CHMP 12 DMG 137 FX 103 REF 4 | same verdicts; + Gaslight Catwoman W 10 -> 60, Huntress Q 10 -> 71.5, Mecha Wonder Woman Q 10 -> 70.5, Grundy Q 55 -> 71 (the mode-0 formulas); every other skill unchanged until items add bonus AD / PD |

Expected gain in game: every skill's item scaling (the ~200 damage / shield / heal stats with a mode-1 formula) and
the 5 stats whose whole value is a ratio. The O part (cooldown reduction, stat 31) is separate.

## 5. Chains between targets (C, simulated)

Scripts that hop between targets (`r2/chains.py`, variable names): bouncing missiles 0x3400003F (Batarang:
RedirectMissile, already handled by `Missile.redirect`), 0x340004FE (Hot Potato bounce: works, 2 hits), status
jumps (0x340002BF Meltdown, Katana R 0x340005B6 JumpRange: working in the sim) and one true chain script,
**0x340006FF** (ChainDamage = stat 1, ChainLength = stat 2, ChainRange = stat 17 of slot 1), started by Shazam's Q
missile 0x34000755 with StartScriptOn + RaiseEvent [0x10000141 0x340006FF] {0x9A6A765 = first target}. Its loop: S3
FindTargets around the last target, a While over GetDetectedTarget picks the nearest not in the list, ZapDelay timer,
S1 ApplyDamage + beam scriptlet, `S1 -> S4 when NumHit >= ChainLength OR NOT DamageSuccess`, else back to S3.

It stopped after one hop for two general VM reasons (C, traced with `r2/dbg_chain*.py`):
1. **An event raised inside a chain re-checks the same instance mid-chain.** ApplyDamage -> `deal_damage` raises
   0x10000020 on the attacker; the chain script runs on the attacker (Shazam), so its S1 transitions are evaluated
   inside its own ApplyDamage, before the node writes its out `DamageSuccess` -> `NOT DamageSuccess` is true -> S4.
   Change (`ics/script_nodes.py _apply_damage`): write the out operand 5 (`ok`) before calling `deal_damage`, then
   correct it after (dealt < 0). General alternative (not tried): `Instance.event` defers an event that arrives while
   the same instance is executing a chain (`inst.depth > 0`) to after that chain.
2. **State locals keep the previous visit's values.** S3's local `DetectIter` (src 5) has no assignment; on the
   second visit it still holds the last count, so the While starts past the candidates and picks the farthest one /
   none. Change (`ics/script_runtime.py Region._enter`): before the chains, reset the entered state's locals
   (`st.locals`) to the instance's defaults snapshot (taken in `Instance._defaults`) or drop them. **Only locals whose
   hash no other block declares**: ics keys variables by hash, so a local named like another block's variable
   aliases it (Blue Beetle's basic 0x34000457 S2 local `EffectDuration` also lives in another block; resetting it
   lost Blue Beetle's E / R BUFF). Proper fix (O): store src 5 / 6 / 7 locals per state frame, not by name.
- Config: `[ics] damage_success_first = true`, `reset_state_locals = true`.

Proof (`r2/fix_chain.py`, `fix_locals.py`, `t_chain3.py`: Shazam Q at the first of 4 enemies 2 m apart):

| Case | Before | After |
|---|---|---|
| Shazam Q, 4 enemies in a line | 2 hits (60 + 30), chain ends after one hop | fix 1 only: 3 hits but hop 2 skips the nearest (DetectIter stale); fix 1 + 2: 4 hits 60 + 3 x 30 (ChainLength 3) in order |
| champion_check (54) | BUFF 14 CHMP 12 DMG 137 FX 103 REF 4 | same verdicts; Shazam Q 90 -> 150, Nightmare Superman E 60 -> 180 (3 missiles: its secondary-target search state re-entered with stale locals too, P) |
| tests/test_scriptvm.py, test_director.py (with all fixes of sections 2-5) | 65/65, 43/43 | 65/65, 43/43 |

## 6. Events scripts wait for that nobody raises (C for the counts; meanings P unless marked)

Method (`r2/events.py`, `evparams.py`, `raised_static.py`, `rec_events.py`): events in any transition trigger of the
875 trees (`scan.waits`), minus what ics raises (literals / constants inside raise_event / .event / .post calls in
ics/, plus every event delivered in a full champion_check run: 36 ids) and minus what any script raises (RaiseEvent
0x1000006B / PostEventDelayed). Params = the `SetVariable(x, #param)` reads in the target states. Result: 106 events
waited for, 32 raised by ics, 23 only by scripts, **51 never raised**. Already raised since fase3-hp/ht (not listed):
0x1000008A, 0x1000008C, 0x100000ED, 0x1000011B, 0x10000196, 0x10000012 / 0x10000007 / 0x10000098, 0x100000D7 / 0x100000A8.

| Event | Scripts | Params | Meaning (conf.) | Who should raise it (file:function) |
|---|---|---|---|---|
| 0x100001B3 | 336 | - | re-init family (C: same transition as 0x10000008, reloads stats) | `ics/world.py World.recompute_stats` (level up, item bought / sold): `R.raise_event(.., 0x100001B3)` with 0x10000008 on the champion's scripts; harmless today |
| 0x1000000C | 157 | - | re-init family (C) | same |
| 0x10000192 / 0x100000A4 / 0x1000000E | 11 / 5 / 5 | - | re-init family (C, in the same AnyOf as 0x10000008) | same |
| 0x100000E2 / 0x100000EB | 2 / 2 | - | Will / stat changed (P: Deadshot Q re-init list; Swamp Thing W `S1 -> S3 on 0x100000E2 AND NOT VitalThreshold(PositiveSkillCost)`) | `CastWorld.set_vital` / `spend_by_vital` on the Will vital |
| 0x1000007B / 0x1000007C | 15 / 15 | TeamMemberIID | team member joined / left (C from the params; TrackTeamEvents 0x10000083) | `ics/script_nodes.py _track_team`: on enable, 0x1000007B per current ally champion; `World.create_champion` / bot creation / death / leave: 7B / 7C to every tracking instance (Zatanna, Arcane GL lantern) |
| 0x10000097 | 10 | 0x9A6A765 victim | champion takedown / assist (P; 0x10000098 = killing blow, raised) | `World._death_events`: for a champion victim, 0x10000097 on the killer and on every assister (Match scoreboard's damage list) |
| 0x10000028 | 1 | 0x9A6A765 | a unit died near me (The Joker passive) (P) | `World._death_events`: on champions within the passive's radius |
| 0x10000016 / 0x10000026 | 10 / 5 | - | respawned / revived (P: Grundy `S2 -> S0`, Zatanna `S1 -> S0`) | `ics/match` respawn (bot and human): raise 0x10000016 on the champion's scripts; 0x10000026 open |
| 0x100000B6 | 7 | SkillSlot 0x31D944 | slot became unavailable (C: client 0xA2A1B0 raises B6 / B7 from 0x20F9; B7 is also raised by 1 script) | `ics/script_nodes.py _set_disable_condition` add (B6) / last remove (B7), silence / stun start / end, `World.cast` cooldown start; params {"SkillSlot", 0x31D944} |
| 0x100000D8 | 7 | CurrencyAmount, 0x89BC34 | loot picked up (P: Catwoman, Gaslight Joker) | loot pickup is not implemented; when it is: `Match` loot touch |
| 0x100000E7 | 7 | 0x4AC3A1 HealthDelta, DamageType, 0x335FDC4 ResponsibleIID, 0x7DE2855 | health changed by damage (C params; Swamp Thing P, Atrocitus W, Raven P) | `ics/script_nodes.py deal_damage` after the health change, on the victim |
| 0x100000EA | 4 | - | paired with 0x100000E7 in the same AnyOf (Atrocitus W, Swamp Thing, Raven) (P: healed / health up) | `World.heal` / `CastWorld.set_vital` health up |
| 0x10000145 | 7 | 0xC89C7B4 SourceIID, SkillSlot | damaged by a champion's skill (P; Thorn Shield-like branches, Green Arrow, Stargirl P, Atrocitus) | `deal_damage`, when the source (or the missile's owner) is a champion: {0xC89C7B4: source, 0x31D944: slot} |
| 0x100000AF | 6 | Slot 0x5A364, TargetIID, IsAOE | skill effect applied to a target (P; Poison Ivy / Harley / Aquaman passives count it) | `_apply_damage` / `apply_status` from a slot 1-4 source: {Slot, TargetIID, IsAOE = ApplyDamage flag a} once per target per cast |
| 0x100000B3 | 4 | 0x9A6A765 | an enemy skill was blocked (P; Gaslight Joker E spell shield attr 0x10000627) | `deal_damage` / `apply_status`: an enemy slot 1-4 effect on a target with 0x10000627 > 0 is cancelled, the attribute consumed, B3 raised on the target |
| 0x100001A6 | 1 | 0x4846C54 Amount, DamageType | lifesteal healed me (C params, Raven P) | `deal_damage` lifesteal branch, on the attacker |
| 0x100000EF / 0x100000F0 | 2 / 2 | 0xCCC86F5 NewValue | resource vital down / up (P; Huntress bolts, AWW Rev) | `CastWorld.set_vital` / `spend_by_vital` on the resource vital |
| 0x100001A4 | 1 | 0x8AABA3 EffectCategory | a crowd control was applied to me (P; Zod W) | `apply_status` of a status with CC flags, on the target |
| 0x1000011E | 1 | DestroyedIID | an object I own was destroyed (P; Mecha Superman sunstones) | `World.remove` of a spawned entity, on its creator |
| 0x10000106 | 4 | - | a returning (tethered) missile turned back (C, kit-audit-2 RC14) | `ics/script_runtime.py Missile` when a tether / return starts (`Missile._return`) |
| 0x10000119 | 4 | - | the carried / grabbed target was lost (P; Supergirl R `S7,S8 -> S3`, Doomsday E, AGL grab) | `World.damage` death of an attached entity / `detach`: on the carrier's scripts |
| 0x100000A7 / 0x10000108 / 0x1000009D | 1 / 1 / 3 | - | missile / dash sub-steps (O) | - |
| 0x1000014A | 5 | 0x4A8A5D4 | item / shop scripts (0x340002E9, 0x34000384, 0x340004BC/BD, 0x3400051F) (O) | - |
| 0x10000186 | 5 | - | encounter phase step (P; 0x34000601..604 and the 1 v AI encounter script 0x34000628 step S1 -> S2 -> S3 on it) | `ics/director.py` / match phase changes (O which phases) |
| 0x1000017C, 0x100000F1..F3, 0x10000171, 0x10000118, 0x10000110, 0x10000083, 0x10000148, 0x10000143, 0x10000193, 0x100001B2, 0x10000162, 0x10000068, 0x10000032 / 36, 0x100000CC, 0x100000BA, 0x100000B2 | 1-2 each | - | cinematic / map / item scripts (0x340006A8/A9, 0x3400076B/C, turret 0x34000014, Device 0x340000D5, GH cannon 0x340002CF, Teleport 0x34000304, Lex Q 0x340005AB / drone 0x340005D8, Gaslight Catwoman E, MWW Q) (O) | - |

Expected gain, ranked: 0x1000007B/7C (15 scripts, 2 passives), 0x10000097 (10, PvP passives), 0x100000E7 / EA / 0x10000145
(damage family, 4 passives), 0x100000B6 (7), 0x100000AF (6), 0x10000016 (10, respawn resets), 0x10000106 (4 missile
returns). The re-init family only matters once stats change mid-match (items, level): no simulator gain.

## 7. Scriptless spawned objects (C for the census and Swamp Thing E, P / O for the rest)

Census (`r2/orphans.py`, `spawnuse.py`): 62 classes spawned / launched by some script have no server script of
their own (`Data.entity_scripts` empty or only the generic 0x340001A6). By what their spawner does with the new IID:
- **Driven by the spawner (about 35, nothing to add)**: the spawner keeps the IID and runs scriptlets on it
  (0x10000034), damages around it (0x1000007A / FindTargets), attaches, destroys it (0x10000010) or launches it:
  markers 0x400009B7 / 0x40000BD4 / 0x40000CA7 (Atomic Joker, Arcane Supergirl), fuse / blast helpers (0x40000BD2,
  0x40000C20, 0x40000D55 / D5F / D61, 0x40000E56, 0x40000ED1 / ED2), sweeps 0x40000CD6 / CD7, Raven's projection
  0x40000CA5, portals 0x40000614 / 615, Mecha Superman's wall 0x40000647 (`$WallIID`, plus a RaiseEvent to
  0x340001C5, in no pack), Lex's sentry node 0x40000BCF (run by 0x340005D8), Krypto's stick, Star Sapphire's crystal
  0x40000634 (RaiseEvent to 0x340003D1). Crater 0x40000487 is visual (fase3-hr lifetime table).
- **Spawn and forget (the gap)**: Zatanna Q 0x400001E7, The Joker W teeth 0x4000020B, Green Lantern R 0x40000359,
  Gaslight Catwoman E 0x40000545, Star Sapphire's Predator 0x400005D2, Atomic Poison Ivy E 0x40000637, Nightmare
  Superman Q 0x400007F6, Swamp Thing E 0x40000BCA / W 0x40000BCB, Nightmare Catwoman R 0x40000D2B, Nightwing R
  0x40000E6F, Arcane Supergirl W 0x40000BEF, items / powers 0x40000CDD..CE1, 0x40000A83, 0x40000AAC, map drops.

Where their behaviour lives:
1. **An orphan script reading the shooter's stats** (`r2/match_orphans.py`): only 5 orphan scripts do
   `LoadSkillStats($ShooterIID, ..)[.., slot]`, all waiting for the spawn event 0x10000049. Matching slot + stat set
   against the spawners: **0x340005CB <-> Swamp Thing E 0x40000BCA** (slot 3, 8 stats 5 18 14 19 21 17 12 33 = all of
   E's, unique match; C by the stats, the simulator confirms); 0x340004E3 (slot 1 {5 14 18}) <-> Nightmare Robin Q
   0x40000CA4 (P: kit-audit-2 named it as Q's missile; its return hit waits 0x10000106, section 6); 0x34000448 is the
   phantom missile 0x400007F7's own template script (C, template 0x490007F7), so Nightmare Superman's collector
   0x400007F6 must launch 0x400007F7 (O: what triggers it); 0x34000562 (slot 4 {5 18}) matches 9 ultimates (O; bound
   to Green Lantern R it changes nothing). No pack references 0x340005CB except its own record (raw u32 search,
   `r2/rawref.py`), so the binding is not in the data the server reads (O: the 0x40 class records are HFSM-shaped).
2. **Template property 0x10000328 (unit attack)**: The Joker's teeth (0x34000116) and the Predator (0x34000391): the
   pets must run their attack like minions (`Data.unit_attack` + the match unit AI) (P). The Predator's brain
   0x340003D1 is referenced only by the scriptlet record 0x1E000363 (node 0x10000053 with the passive's owner-block
   slot 0x0901E674 = the Predator IID): P the client scriptlet just raises events into it; the server must start
   0x340003D1 on the Predator itself (StartScriptOn at spawn).
3. The rest (Zatanna Q, Gaslight Catwoman E, Green Lantern R, Nightmare Catwoman R, Nightwing R, Atomic Poison Ivy
   E, Arcane Supergirl W): no candidate script in the 875 decoded trees (O). Next step: decode the 0x40 class
   records (kit-audit-3 4) or the 4 scripts referenced but not decoded (0x340005CD, 0x340001C5, 0x3400060C,
   0x34000299 in no pack).

Change:
- `ics/gamedata.py Data.entity_scripts`: merge an explicit `[ics] spawned_class_scripts` table (config default
  `{"0x40000BCA": ["0x340005CB"]}`; candidates kept commented: `0x40000CA4: 0x340004E3`). `World.spawn_entity`
  already starts a class's scripts with ShooterIID (fase3-hp) and raises 0x10000049.
- `ics/world.py CastWorld.spawn_entity`: when the class template has 0x10000328 and a team, make the entity a unit
  (`kind = "unit"`, `kit = {0: Data.unit_attack(cls)}`, start it, hand it to the match unit AI with its creator's
  team; lifetime from the spawner's DestroyEntity). For 0x400005D2 also start 0x340003D1 (config
  `spawned_class_scripts`).

Proof (`r2/fix_spawn.py`, `SPAWN_ONLY=<class>`):

| Case | Before | After |
|---|---|---|
| Swamp Thing E (0x40000BCA -> 0x340005CB) | FX (spawn only) | DMG 120 (knockup + slow + damage after DelayTimer) |
| Nightmare Robin Q (0x40000CA4 -> 0x340004E3) | DMG | unchanged (its hit path waits 0x10000106) |
| Green Lantern R (0x40000359 -> 0x34000562) | FX | unchanged (not its script, O) |

## 8. All recipes together

`r2/` fixes of sections 2-5 + section 7's Swamp Thing binding, monkeypatched together: champion_check BUFF 14 ->
16, CHMP 12, DMG 137 -> 141, FX 103 -> 98, REF 4 -> 3 (Aquaman R, Arcane Supergirl Q, Swamp Thing Q and E, Catwoman
R, Arcane Harley R); damage up on Atomic Joker Q (1.8 -> 109.4) and R, Dex-Starr R, Gaslight Catwoman W, Huntress
Q, Mecha Wonder Woman Q, Nightmare Superman E, Shazam Q, Grundy Q, Swamp Thing E (0 -> 180); no verdict lost.
Tests with every fix monkeypatched in (`r2/runtest.py`): test_scriptvm 65/65, test_director 43/43, test_match
154/154, test_ics 33/33 (same as without).
