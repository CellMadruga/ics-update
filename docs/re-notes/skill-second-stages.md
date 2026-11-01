# Skill "second stages" missing (Atomic Green Lantern, 2026-10-23 tester report)

Static analysis of the AGL kit scripts (`python -m ics.script_model 0x340002B5 0x340002C1 0x340002B2 0x340002B1
0x340002B4 0x340002BE 0x340002BF 0x340002C3`), `logs/server.log` (AGL match, 23:03-23:11), `logs/traffic.log`,
`logs/diag.log` (--graph). Confidence: C confirmed, P probable, O open.

## 1. Common cause: the cast "done" signal (code 2) arrives 0.15 s after the cast point (C for ics, P for the effect)

`ics/script_runtime.py start_cast` (line ~1663): cast point (5 and 3) after `CastWorld.cast_time()` = fixed 0.25 s
(`ics/world.py:1321`), then code 2 `CAST_RECOVERY` = 0.15 s later. Every AGL skill graph has
`T0: S1,S3 -> S2 on OnCastSignal [0x1000000F 2]`, and S2 is the skill's end:

| Skill | S2 runs (0.15 s after the cast point) | effect |
|---|---|---|
| Grab 0x340002B5 | `RaiseGraphEvent(SELF)[0x10000002]` (= `skill_to_locomotion`, animations.tsv), `RunScriptlet 0x10000890` (Vfx_Atm_Glt_Grab_Stop), `EndSkill`, and `RaiseEvent(MissileIID)[0x10000067]` if the missile still exists | the arm goes back to locomotion and the grab VFX stops while the tethered missile is still flying; S3 was meant to last until `T5: S3 -> S2 on 0x10000005` (missile came back) |
| Meltdown 0x340002B4 | `RaiseGraphEvent(SELF)[0x10000002]` | throw animation cut |
| Scorched Earth 0x340002B2 | `StopScriptletKey(SELF)[0x100008AB]` (Vfx_Atm_Glt_Smash_Active) | see 3 |

Log evidence: Grab 23:05:51.927 S1->S3 (launch), 23:05:52.066 S3->S2 (T0), traffic 52.145 graph event 0x10000002 +
scriptlet 0x10000890; diag 23:03:49 shows 0x10000002 delivered to AGL's graph (index 0xF).
The real cast end comes from the action/animation (no client message reports it: the client sent only 0x20EE).

## 2. Grab: the missile never reaches its attach state S9 (C for the chain, O for the event source)

Missile script 0x340002C1: S3 -> S4 on collision 0x10000002 -> S1 (damage, `RunScriptlet SELF 0x10000016` with
0x10000030 = target, stun 0x48000293, `SetMissileVelocity(ReturnVelocity)`, `SetSkillTarget(SELF,Target)`,
`SetSkillTarget(SELF,SELF)`, `SetSkillAttached(SELF)[0]`). Then it waits for **event 0x10000022** (T12 -> S9) or
0x10000014 / 0x10000067 / 0x10000119 (-> S8 drop). S9 = `AttachEntity(SELF, Target)[0x1000007B 0x10000081]`,
`RaiseGraphEvent(Target)[0x100002BA]` (CbtState_Cower_Instant), **`RaiseGraphEvent(Shooter)[0x10000331]`** (AGL's
pull), `RunScriptlet(SELF)[0x10000076]` (Vfx_Event1 on the missile). Nobody raises 0x10000022 in ics (same gap as
champion-kits-status.md 6: AWW R, Atrocitus E, Doomsday E, Nightmare Batman/Robin R, Zatanna R). P: the engine raises
0x10000022 on the missile when the attach/skill-target set by SetSkillTarget + SetSkillAttached succeeds,
0x10000014 when it fails. RE target: client SetSkillTarget exec `0x9C4C20`, SetSkillAttached unpack `0x983D70`.
Also `T6: S9,S1 -> S2 on 0x10000005` must reach the missile's own script when it is back (ics raises 0x10000005 only
on the owner, `script_runtime.py Missile.end`).

`LaunchTetheredMissile [0x40000485 0 1 0 2 0x3F000000 1 1]`: 0x3F000000 is the f32 0.5 tether factor, not a 0x3F DID.

## 3. Scorched Earth: the ground circle stays forever (C for ics, P for the wire form)

The circle is `Vfx_Atm_Glt_Smash_Active 0x100008AB` run on AGL in S1 (traffic 23:06:39.577). Its only end is S2's
`StopScriptletKey(SELF)[0x100008AB]` (node 0x10000012, client exec `0x993DB0` -> `0x588A80(entity, key, all, 0)` ->
`0x57C4B0(key, signal 1)`). `ics/world.py CastWorld.stop_scriptlet` (line ~1645) only logs ("stop scriptlet
0x100008ab", 23:06:39.921). The 0x8D path signals a live run when the entry carries the **same instance number**
(`0x6279D0` step 4, `0x57B510` -> `0x534BF0` / `0x534290`, client-scriptlets-graphs.md 1.2); `messages.scriptlet_entry`
always writes an empty signal bit set. Fix: remember (entity, key) -> instance numbers in `run_scriptlet`; for
StopScriptletKey / StopScriptlet send 0x8D (key, same instance, signal bit set with bit 1) (P which bit).
Crater: `SpawnEntity [... 0x40000487 1 0x1000009C]` was sent (23:06:39.802, `world.spawn` as a bare class). Like the
tutorial crater 0x400004FD (CHANGELOG fase3-cx/cz), a 0x40 class with no model built directly is not drawn; the
visible part comes from its world state / scriptlet tables (O: its tables are not readable by `Data.record_tables`,
which returns the generic 0x1D000456 for 0x40000484/5/7 and 0x40000090).

## 4. Shards of Will (P/O)

Status 0x480007B5 -> script 0x340002C3 sends `Vfx_Atm_Glt_Shards_Start 0x1000088C` / `_Active 0x10000886` with
variable 0x1000033E (ShieldPercentage) = 0.0 (`(ShieldAmount - Base) idiv Base`, 0 with no target; ics' idiv is
integer) and `_Stop 0x1000088B` 5 s later. Everything the scripts name is sent. Open: whether the sphere's action
binds 0x1000033E (scale / intensity; 0 would hide it) - parse the action list of 0x10000886 in table 0x1D0003D7
(pack 0xA0000150). `Data.script_table` cannot parse AGL's own tables 0x1D0003CE/CF/D0, 0x1D0005FC (bodies None).

## 5. Meltdown (P)

Missile 0x40000484 (script 0x340002BE) is created and flies (1.3 s), hits, raises 0x100000EE on 0x340002B4,
status 0x480007AF -> 0x340002BF sends `Vfx_Atm_Glt_Meltdown_Tgt_Active 0x10000889` (0x10000402 = AGL, 0x1000050A =
0x1E000266). The flying marker is the missile object itself plus `Vfx_Atm_Glt_Meltdown_Shard 0x10000AA4` on AGL;
the throw is cut by 1. Whether the missile object is drawn is open (same class-built creation as the crater).

## 6. 0x3F reaction handlers

`AddReactionHandler 0x1000014D (entity, out handle)[0x3F000003]` (exec `0x994500` -> `0x9754A0`, handler component
entity+0xB8) in the missile's S5; removed by `RemoveReactionHandler 0x1000014C` in S1/S6/S11. A 0x3F record is a
variable block + one node chain run when its event hits the entity (missile collision snippets 0x3F000003/6/9). It
handles collisions while flying (P: ignore / react to the owner); it has no scriptlet or graph event of its own, so
running it would not produce these visuals.
