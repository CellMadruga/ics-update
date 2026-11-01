# Atomic Wonder Woman kit: the Rev charges (2026-10-24 tester report)

Tester: passive = after 2 skills the third is empowered (Q may jump twice, W hits harder, E does the circular slash).
On our server: W does not empower her next basic attack; E ALWAYS does the circular slash; Q can be recast at once.

Variant `0x400003EC` (champion `0x480006D5`). Kit (`Data.kit`): basic `0x34000257`, Q Vault `0x34000256`, W Smite
`0x34000255`, E Savage Sweep `0x34000254`, R Reclaimer `0x34000253`, passive Rev `0x34000265`.
Confidence: C confirmed, P probable, O open.

## 1. The charge counter is vital 6 ("Rev"), not a status stack (C for the scripts)

Passive `0x34000265`:
- graph S0: `LoadSkillStats(-, RevTimerDuration, <0x8caa6f4 src 2 slot 0xd4>, HasteBase, CooldownBonus) [4 14 12 4 1]`.
  The third output is a **source-2 operand** = the owner block (full-combat-skills.md 5.1): a variable shared by every
  script of the champion, at owner-block slot 0xD4 (hash 0x08CAA6F4, name unknown; it is the Rev threshold, P = 2).
- graph S1: event `0x1000008A` (S0 -> S3, `SourceSkill = #0x31d944` event parameter) or `0x1000001D` raised on the
  passive by a skill (`any -> S4`, `SourceSkill = BasicSkill`) -> S1: `SpendCost(VitalChangeUlt | VitalChangeNormal,
  SELF)[6 0]` = **Rev gain** (a negative cost on vital 6), status icon `0x4800083E` with the timer; S2 (Rev timer ran
  out) spends `RevChange` and removes the icon; S5 refreshes the icon count from `GetVital(SELF)[6]`.
- graph S2: on vital 6 change / events `0x100000F0` / `0x100000EF` -> S1: `IfThenElse(VitalThreshold(Tier2Rev,
  SELF)[6 0 0 1])` = Rev >= Tier2Rev: run scriptlet `0x100007D7` (the empowered glow), `0x100000FA(SELF)[slot 1/2/3,
  TFX 0x1300148F/90/91]` (empowered skill FX override for Q/W/E), `ReduceCooldown(SELF, CooldownBonus)[1..4]`;
  else `StopScriptletKey 0x100007D7`, `ClearSkillStatOverride[1/2/3]`, `RemoveAttributeModifier`.

E `0x34000254` S1: `IfThenElse(VitalThreshold(<0x8caa6f4 src 2 slot 0xd4>, SELF)[6 0 0 1])` -> `RevvedUp = 1`,
graph event `0x100002E4`, scriptlet `0x100007D5` (circular sweep) else `RevvedUp = 0`, `0x100002E0`, `0x100007CC`
(cone). S3 hits; when RevvedUp: `SpendCost(-threshold)[6]` (spends the Rev) ... ; else raises `0x1000001D` on the
passive when it hit something (a charge).

W `0x34000255` only applies status `0x480006FD` (script `0x3400026A`) and resets the basic attack. The status sets
owner-block flags: `ctx 0xD8` (Smite active) = 1, `ctx 0xD9` = Rev >= threshold (then spends the Rev, scriptlets
`0x1000083E` / `0x1000084B`, else `0x100007DF` / `0x100007DD`), +BasicAttackRangeAdd. The basic attack `0x34000257`
S3 reads `ctx 0xD8` -> sets `ctx 0xDA` = 1, scriptlet `0x100007EC`, `StartCooldown(SmiteCooldown)[2]`. The status'
inner graph waits for **event `0x1000008B`** (TargetIID parameter) with `ctx 0xDA`: ApplyDamage(`ctx 0xD0` empowered
40 | `ctx 0xCC` 30, values W loaded into the owner block), raises `0x1000001D` on the passive (+1 Rev),
`RemoveStatus 0x480006FD` -> exit `StartCooldown[2]`.

Q `0x34000256` S3: `IfThenElse(AllOf(VitalThreshold(ctx 0xD4)[6 0 0 1], !SecondTriggerActive))` -> spend the Rev,
`SecondTriggerActive = 1`, `StartCooldown(MiniCooldown 0.2)` (second jump within 4 s, icon `0x480007B4`), else
`StartCooldown(SkillCooldownDuration 18)`. A hit without Rev raises `0x1000001D` on the passive (+1).

Values (passive instance): VitalChangeNormal 1, VitalChangeUlt 100, RevChange -1, RevTimerDuration 6, Tier2Rev 2,
CooldownBonus -0.25, UltSkill 4, ctx 0xD4 = 2. AWW's champion stats record: 0x10000432 (resource max) = 2, no
0x10000484 (regen); her twin record's **0x1000000C (secondary vital type) = 6** (43 champions 5; Huntress 6;
Atrocitus / Dex-Starr / Doomsday / Nightmare Robin 4; Batman / Nightmare Batman / Shazam 1; Katana 7).

## 2. Why ics behaves as reported (C, simulated)

Scratch driver on the champion_check harness (casts, then Rev / cooldowns / statuses / vars). As is: Rev stays 0,
`ctx 0xD4` exists only in the passive's own vars (2.0), Q/W/E read it as 0 -> `VitalThreshold(0)` = `0 >= 0` = true.

1. **Owner-block (source 2) operands are per instance** (`script_runtime.Instance.get` / `set`): every source-2
   variable other than SELF is stored in the instance's `vars`. Q/E/status read the threshold as 0 -> always
   empowered (E always circular; Q always gets its second jump, MiniCooldown 0.2 instead of 18 s). The basic attack
   never sees `ctx 0xD8` -> normal hit (scriptlet 0x10000128), the status never sees `ctx 0xDA`.
   332 of 875 scripts use source-2 variables (Cyborg's basic attack `0x34000237` `ctx 0xD4/0xD9` the same pattern).
2. **`script_runtime._spend` ignores the vital and the sign**: `world.spend(-amount)` -> `Will -= abs(amount)`;
   `SpendCost(+1)[6]` (a Rev gain) drains her bar instead.
3. **The resource vital is hard-wired to 1/5** (`world.CastWorld.vital` / `set_vital`, and `create_champion`
   sends `[ics] champion_secondary_vital` = 5 for everybody): her bar (max 2) is vital 6; the base aura's VOTs on
   vitals 1 / 5 (status 0x48001109) and the default `[ics] will_regen 2.0` (no regen stat) refill it; it starts full.
4. **Event 0x1000008B is never raised** (champion-kits-status.md 6): W's Smite damage, charge and removal never run.

With fixes 1-4 patched in the driver: W+basic = 80 (50+30), consumes the status, +1 Rev, W cooldown 8 s; at 2 Rev
W+basic = 90 and spends 2; E with < 2 Rev = cone `0x100007CC` (+1), with 2 = circular `0x100007D5` (spends 2);
Q with < 2 Rev = one jump + 18 s cooldown, with 2 = second jump then 18 s. Rev decays 1 per 6 s.

Open: events `0x100000F0` / `0x100000EF` (passive graph S2: empowered glow `0x100007D7`, TFX overrides, -0.25 s
cooldowns) and `0x1000008A` (R gives +100 = full Rev; `SourceSkill` = event parameter `0x31D944`) are not raised.

## 3. Fixes (verified in the driver, not applied)

1. `script_runtime.Instance.set`: a source-2 operand that is not SELF also goes to a per-entity owner block
   (e.g. `combat.of(owner).owner_vars[hash]`); `Instance.get`: own `vars` first, else that block. (Own copy first keeps
   the generic per-skill slots such as `0x2F044A4 @0xB4` (cost, 57 scripts) from colliding between skills.)
2. `script_runtime._spend`: `vital = n.values[0]`, entity = `ops[1]` (unset = SELF/source):
   `set_vital(ent, vital, vital(ent, vital) + amount)` + `vitals_changed` (cost stat 3 is negative, so Will costs
   keep working).
3. `world.create_champion`: `ent.resource_vital` = twin record's 0x1000000C (fallback `[ics]
   champion_secondary_vital`), sent as that property; `CastWorld.vital` / `set_vital` map only `ent.resource_vital`
   to `ent.will`; the world tick's regen uses `[ics] will_regen` only when resource_vital == 5 (else the stat or 0);
   resource 6 starts at 0 (P).
4. Raise `0x1000008B` {TargetIID} on the attacker's scripts when its basic attack (`ApplyDamage` from a slot-0
   instance) deals damage.
