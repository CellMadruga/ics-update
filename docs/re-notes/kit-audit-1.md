# Kit audit 1 (2026-10-24): Aquaman .. Doomsday (18 base variants)

Method: `python tools\champion_check.py --only <variant> --trace <slot>` (headless Crime Alley v AI, current ics with
the fase3-hk..ho fixes on), `python -m ics.script_model <script>` for the trees. Findings are appended per champion,
then grouped by root cause at the end. Confidence: C confirmed (simulated / read in the tree), P probable, O open.

Run: current ics (fase3-ho defaults: owner block, spend_by_vital, resource vital from data, basic_hit_event,
raise_event_script_target, missile_scripts_past_starts, range_angle_needs_max, champion_init_event,
polled_any_no_reenter, attached_skill_events). Scratch: every slot traced (all casts), plus a static pass over each
kit's script closure (slots 0-5 + statuses 0x48 -> property 0x10000242 + spawned / missile classes -> 0x8E) listing
the events its transitions wait for (`builtin:0x6 [ev]`) that neither ics raises natively nor any RaiseEvent node in
the 875 trees raises.

Notes on the tool: `will_spent` reads 0 for Will champions because the base aura's VOT (+15 per tick) refills Will
inside the 3 s window; SpendCost itself works (set_vital traced: Aquaman 346 -> 335). Scriptlet keys run on the
champion that `Data.scriptlets` does not list (e.g. Aquaman Q 0x100009C9) come from table 0x1D00048C (pack
0xA0000191), which `rp.script_tables` cannot parse (`Data.script_table` -> None); the champion is not filtered, so
the client still gets them (only a server-side gap; it would matter for objects filtered by `scriptlet_keys`).

## Per champion (sim verdicts Basic Q W E R)

| Champion | Verdicts | Findings |
|---|---|---|
| Aquaman 0x400005C6 | DMG DMG DMG DMG REF | R `0x34000397` disabled (0x10000066) at 0x10000008 and only re-enabled by **0x100000A9** {0x17AF14 = new ult HFSM}; W `0x34000396` / E `0x3400037A` / Q missile `0x34000393` call **SetSlotSkill** `[0x48000959 / 0x4800097E / 0x48000956, 1]` (Data.item_skill -> scripts 0x3400039F / 0x340003A4 / 0x3400039D: the ult becomes the empowered copy of the last skill that hit). `CastWorld.set_slot_skill` returns False -> R never usable. Passive `0x34000395` waits 0x100000AF (never raised). |
| Arcane Green Lantern 0x4000043B | DMG CHMP FX CHMP FX | Q / E only hit the dummy champion (construct targets); W Shackles: no state change (needs Lantern near enemies; prior audit); R ally-champion only. Lantern `0x340002AF` waits 0x1000007B / 0x1000007C (TrackTeamEvents 0x10000083; never raised); status 0x4800078B script `0x340002A6` waits **0x100000ED**; R status `0x340002BA` waits 0x1000008C. |
| Arcane Harley Quinn 0x40000D51 | DMG DMG BUFF FX FX | E Glamour `0x34000778` SetSlotSkill `[0x48001308, 1]` (record has no script: P "revert/hint"), SetWorldState 0x1000010D logged no-op; stat 5 = 0.4 (ratio, P). R `0x3400077B` waits **0x100000ED**. |
| Arcane Supergirl 0x40000AB3 | DMG FX FX FX FX | **Q Breath of Rao misses every time**: TargetPosition = CreatePosition 0x38 vec3(0, Range, 0), CreatePosition = 0x41(pos, 0x40($TargetPosition)); ics heading of a plain point = atan2 of the absolute coordinates (32 deg) and 0x38 rotates with local +X forward -> missile flies ~77 deg off (traced: aim (117.7, 89.5) from (125.1, 77.6), enemy at (126.6, 79.0)). R `0x3400054D` needs charges (by design) and waits 0x10000196. W / E: ground zone / DoT, no hit in 3 s. |
| Arcane Zatanna 0x40000BF5 | DMG DMG FX FX FX | E `0x34000618` waits 0x100000B3; R missile `0x340007C9` waits 0x10000196; passive object `0x34000652` waits 0x1000009D. W cd 0 (gate). |
| Atomic Green Lantern 0x4000047D | DMG DMG DMG FX FX | Passive `0x340002B3` waits **0x1000008A**; Grab missile `0x340002C1` waits 0x10000106 / 0x10000119; status scripts 0x340002C6 (0x1000008C), 0x340002C5 (0x100000D7). Otherwise as skill-second-stages.md. |
| Atomic Joker 0x40000962 | DMG DMG FX CHMP DMG | **Q Hot Potato deals 0.5 / 1.25**: its missile `0x340004FE` loads stat 5 = 0.5 (+0.1) and stat 1 = 1.25 as Damage / BounceDamage (ratios, P: of attack damage) and ApplyDamage uses them raw. W `0x340004DC` charges (MaxBananas) and banana `0x340004F7` waits 0x10000124; E `0x340004DB` waits **0x1000008A**; passive `0x340004DE` waits 0x10000016 / 0x1000011B; W/E use 0x38 frames. |
| Atomic Poison Ivy 0x40000553 | DMG DMG DMG FX FX | R `0x34000355` waits **0x100000ED** / 0x10000145; its status `0x34000363`: reveal 0x1000011E + PlaySound 0x100000BB no-ops, waits 0x1000008C. |
| Atomic Wonder Woman 0x400003EC | DMG DMG BUFF DMG FX | fase3-ho fixes confirmed (W + basic = 90). **R Reclaimer never starts vs a champion**: S6 = `AddSkillTarget(SELF, SELF)` + SetSkillAttached; `_attached_skill` ignores a target equal to the entity -> raises 0x10000014 -> S0 (needs 0x10000022 + HoldsActionLock, T9). Passive `0x34000265` waits **0x1000008A** (R +100 Rev), 0x100000EF / 0x100000F0; R waits 0x1000009D. |
| Atrocitus 0x40000932 | DMG BUFF FX FX FX | E works on the dummy champion (champion only). Passive `0x340004D1` (rage) waits **0x1000008A**, **0x100000ED**, 0x10000145; W `0x340004CE` waits 0x100000E7 / 0x100000EA. |
| Batman 0x40000280 | DMG DMG DMG DMG FX | **R The Dark Knight loses its second stage**: S1 Cast -> S3 on code 3 (airborne, recast T7 -> S5 dive), but the cast end code 2 comes 0.15 s later and T2 `S1,S3,S4 -> S2` ends the skill. W charges (cd 0 by design); W graph S3 refund on 0x10000097 / 0x10000098 (takedowns, never raised). Passive waits 0x10000140 / 0x10000141 (raised by other scripts only). |
| Blue Beetle 0x400007FA | DMG DMG FX BUFF FX | R `0x3400044F` toggles owner flag 0xE8 (Infiltrator); Q/W/E graph S2 then **SetSlotSkill** own slot `[0x48000A97 / A95 / A96, 0]` -> scripts 0x34000453 / 452 / 450 (dash forms): not applied, R does nothing visible; revert path open (exit only restores cooldowns). Passive `0x34000456` waits **0x1000008A** (bonus damage vs missing health) and 0x10000196. |
| Catwoman 0x4000041C | DMG DMG DMG FX FX | Passive loot works on basics (0x1000008B); not on skills (**0x1000008A**). Lob missile script 0x34000299 is absent from the install (cut content). Passive graph S2 waits 0x100000D8 (loot picked up: -cooldowns, never raised; loot pickup not implemented); SetCurrencyOption 0x100000EC no-op. R status `0x3400028E` SetSlotSkill(SELF) `[0x4800077A, 0]` (E Acrobat 0x3400027B) + RaiseEvent 0x100000A9: not applied; waits **0x1000008A**. |
| Cyborg 0x400003B2 | DMG DMG DMG FX CHMP | R Plasma Cannon: FindTargets box (kinds 0x410109) missed the minion 2 m in front, hit the dummy champion (P: kind mask). Basic DestructionRaycast no-op; W status `0x34000655` waits 0x10000007; R waits 0x10000012. |
| Deadshot 0x40000C68 | DMG DMG FX FX FX | R by design only from W scope; Q waits 0x100000E2 / 0x100000EB; R waits 0x10000023 (client 0x20EA, OK in game). |
| Deathstroke 0x40000C19 | DMG CHMP FX DMG FX | Q champion-only (design). W `0x340007DF` waits 0x100000E7; E missile `0x340007E9` waits 0x100000A7. |
| Dex-Starr 0x40000C75 | DMG DMG FX DMG DMG | **W Pounce ends at once**: S1 (aim, BeginSkill, no Cast) has `T4 S1,S3 -> S2 on OnCastSignal 2`; `Region.finished` delivers the chain's own result 2 when no cast runs -> S2 before the recast (T8 S1 -> S3 dash). Passive `0x340006B8` (rage) waits **0x100000ED**, **0x1000008A**, 0x100000D7. E/R use 0x38 frames. |
| Doomsday 0x4000015A | DMG DMG FX CHMP FX | E champion-only (works on dummy). Passive `0x340000E6` marks attackers on **0x100000ED** {0xC89C7B4 attacker}, waits 0x10000097 / 0x10000098; R `0x340000E1` waits 0x10000012 / 0x10000016; E waits 0x10000108 / 0x10000119. |

## Root causes, ranked by champions fixed (of these 18)

1. **Event 0x100000ED "owner was damaged" never raised** (29 scripts game-wide; here AGL-Arcane, Arcane Harley R, Atomic
   Poison Ivy R, Atrocitus, Dex-Starr, Doomsday = 6). Parameter 0xC89C7B4 = the attacker (Doomsday's passive marks it;
   P). Fix: `ics/script_nodes.py deal_damage`, after `world.damage`, `R.raise_event(world, target, 0x100000ED,
   {0xC89C7B4: source, "DamageAmount": dealt})` when `left > 0` and source is another entity (config key).
2. **Event 0x1000008A "skill hit" never raised** (21 scripts; AWW R +100 Rev, Atomic GL, Atomic Joker E, Atrocitus,
   Blue Beetle, Catwoman, Dex-Starr = 7). Twin of 0x1000008B: same listeners use `TargetIID`; AWW reads `SourceSkill`
   (hash 0x31D944 = SkillSlot). Fix: `_apply_damage`, when `_damage_slot(inst)` is 1-4 (skill, its missile or status)
   raise 0x1000008A {TargetIID, 0x31D944: slot} on the source's scripts (once per target per cast, P).
3. **Frames: local +Y is forward, ics uses +X; a client point has no yaw** (59 scripts use 0x38; Arcane Supergirl Q
   broken, Dex-Starr E/R, Atomic Joker W/E, Batman R, Blue Beetle E, Arcane Supergirl R at risk = 5-6). Evidence:
   vec3(0, $SkillRange / $KnockbackDistance / $BeamLength*0.5, 0) offsets, Batarang's vec3(0, -0.5, 0) "behind",
   WallWidth on X. Fix: `ics/script_runtime.py _transform` (and `_with_heading` on vectors, `_forward`) rotate with
   forward = local +Y: `world = ox*(sin r, -cos r) + oy*(cos r, sin r)`; `activate()` stores `TargetPosition` as
   `Frame(point, degrees(atan2(dy, dx)))` from the caster so `0x40($TargetPosition)` is the aim heading.
4. **SetSlotSkill 0x10000089 not applied + 0x100000A9 never raised** (17 nodes; Aquaman R, Blue Beetle R forms,
   Catwoman R -> E, Arcane Harley E, also Katana / Doomsday basic = 4 here). `Data.item_skill(did)` already resolves
   the records to scripts + stats. Fix: `ics/world.py CastWorld.set_slot_skill`: slot = 4 when flag 1 else the
   caller's slot (P); stop the slot's instance, put the item skill in `ent.kit[slot]` (keep rank), start it, send the
   slot table property (0x100008E3.., full-combat-skills.md) and raise 0x100000A9 {0x17AF14: new script DID} on the
   owner's scripts; keep the original to restore when a later SetSlotSkill names the base record. Revert rule open.
5. **Cast end (code 2) delivered too early or synthesized** (Batman R, Dex-Starr W = 2; static scan: only these two
   states game-wide). `script_runtime.Region.finished` calls `check(code=2)` for a state with no running cast (Pounce
   S1 has a recast exit); `start_cast.cast_end` sends 2 0.15 s after the point even when the point moved the graph
   to a state with its own recast / timer exit (Batman S3). Fix: do not synthesize 2 when the state has an
   OnEvent(0x1000001D) or timer transition; in `cast_end`, skip 2 if the state entered on 3/5 has such exits.
6. **`_attached_skill` drops a self skill target** (AWW R = 1; also Nightmare Batman / Robin R per the old S7 pattern).
   `ics/script_nodes.py _attached_skill`: count `_real(t) is ent` as a valid target (AWW R adds only SELF).
7. **Ratio damage stats used raw** (Atomic Joker Q 0.5 / 1.25 = 1). Stat 5 < 5 on 18 skills (Hot Potato, Glamour,
   Huntress R, Atrocitus W...). Needs RE of what ApplyDamage / the record scales them by (P: attack damage).

Smaller / open: takedown events 0x10000097 / 0x10000098 (Batman W refund, Doomsday) only matter with enemy
champions; loot pickup event 0x100000D8 (Catwoman); TrackTeamEvents 0x1000007B / 0x1000007C (AGL Lantern);
0x1000008C (statuses), 0x10000196, 0x100000D7, 0x10000145, 0x100000E7, 0x10000012 / 0x10000016, 0x1000009D: never
raised, meaning not derived. Re-init family variants 0x100000A4 / 0x10000192 / 0x10000197 are harmless (0x10000008 is
raised). Cyborg R box missed a minion (kind mask 0x410109, P). Champion-only skills (Atrocitus E, Doomsday E,
Deathstroke Q, AWW R, AGL Q/E/R) need bot champions v AI (champion-kits-status.md 7).
