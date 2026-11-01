# Combat and skill system of the client: full spec for the server (static analysis, 2026-10-22)

Source: the full Ghidra decompilation of `InfiniteCrisis.exe` (`re-work/decomp`, VAs with image base 0x400000), node
vtables read straight from the exe (slot 5 = Unpack, slot 9 = run, slot 10 = client execute / evaluate), capstone /
REA for the functions Ghidra did not split, the 826 decoded trees in `data/script_trees`, the packs through
`ics/gamedata.py`, and the earlier notes (`script-nodes-names.md`, `script-nodes-complete.md`,
`client-status-effects.md`, `client-scriptlets-graphs.md`, `targeting-and-relations.md`, `protocol-*.md`,
`properties-complete.*`). No game text is quoted; ids, short names and numbers only.

**Confidence:** **C** = read in the client code or exact data; **P** = probable (inferred from data, variable
names, neighbours); **?** = open. Every node spec gives the Unpack layout in **stream order** (the order
`ics/script_model.py` prints operands), the client execute (or "server-only" when slot 10 is the empty `0xAB4D80`
for actions / `0x4FB4C0` for predicates), and what the SERVER must do, with the messages it must send.

This note complements, and in places corrects, `script-nodes-names.md` / `script-nodes-complete.md` (names in
**bold** in the node headings are corrections).

## 0. Summary

### 0.1 The model in one paragraph (C unless marked)

The client never casts on its own: input -> CanActivate `0x8709E0` (13 checks: client-side cost / cooldown / range /
lock tests, errors shown locally) -> order `0x20EE` (`cmd | slot | target IID | position | u8`). Everything visible
comes back from the server: scriptlets `0x8D` (animation / FX), graph events, cooldown `0x20F8` (f64 end time),
cast bar `0x2077` / `0x20CE` / `0x2096`, disable conditions `0x20A0`, usable override `0x207B`, skill errors
`0x20DC`, script events `0x20C9`, effects `0x200F` / `0x200C`, vitals `0x42`, attribute modifiers `0x20F0` / `0x20E8`
/ `0x20E7`. Script instances exist on the client only when the server creates them (status effects `0x200F`, kept
in the HFSM component at `entity+0x8C`); the client then runs only the slot-10 half of each node (attribute
modifiers, scriptlet stop, GetVital, HasStatus, collision toggles, destruction FX ...). **Every node with an empty
slot 10 is server-only**: the server produces the whole effect and replicates it through objects, properties,
movement blocks, scriptlets and events. Missiles are ordinary class-0x40 objects moved by 0xB0 movement blocks (no
client missile code); hotspots / auras are server volumes plus an optional visible object; damage floaties are made
by the client from vital changes (section 2, B).

### 0.2 Corrections to the project found here (C unless marked)

- VM: an action used inside a condition list runs and returns its chain's result (true at the end); AnyOf / AllOf in
  an action chain are selector / sequence; While stops after 1025 iterations; **a timer never started (0.0) counts
  as expired**; expression 0xC is x - 1 (ics evaluates it as `/`); vt `0x15A88E0` is builtin 0x12 = post an event
  after a delay (ics treats it as `>=`); expression 0x41 *sets* the heading (5.1, 5.3).
- `CheckRelation` (0x10000028) takes a bit mask: 2 enemy, 3 enemy or neutral, 4 ally, 7 all (ics accepts only 3)
  (4.2). Hotspot shapes: 1 sphere, 2 box, 6 own bounding box, 7 cylinder (`0x9805B0`).
- Renamed: 0x10000015 HoldsActionLock (0x1000000E / 0x1000000A take and release the lock); 0x100000D2
  IsSlotSkillScript; 0x100000DF IsSkillOffCooldown; 0x100000FB SetSkillDisableCondition; 0x100000FC
  SetSkillUsableOverride; 0x10000097 UpdateSkillUIOverlay (notice 0x1000015A); 0x1000008E ClearSkillStatOverride;
  0x10000089 SetSlotSkill; 0x100000DB QueueOrder; 0x1000000B AddSkillTarget; 0x10000136 ActivateSlotSkill;
  0x10000148 GetSkillTargetingType; 0x10000155 GetEntityProperties (reads, does not set); 0x100000A5 GetCreator;
  0x10000141 GetCameraHeading; 0x100000AD LockInput; 0x100000F5 GetSkillSlotOfScript; 0x1000002C
  OnCombatEventByKind (trigger on event 0x10000020); 0x10000012 StopScriptletKey; 0x1000013A RunFxScriptlet;
  0x10000116 RefreshStatusIcon; 0x10000004 GetVisionRange; 0x10000173 IsOnScreen; 0x10000002 EndThisScript;
  builtin 0x04 IsEventPending (not a filter).
- Wire: vitals in `0x42` are a 15-bit varint per value; masking with 0x7FFF (as ics does) breaks values above 16383
  (2, B.1). The destruction events 0x8A / 0x1 / 0x8 are FX impulses, not movement updates (4.6).
- Runtime gaps besides missing nodes: ApplySkill never writes its handle / success outputs; the RemoveStatus "this
  instance" form (48 uses) and the handle / flag-mask forms of HasStatus are missing; LaunchMissile ignores the
  existing-entity, out-IID and script-override fields; ApplyDamage ignores its flags and outputs (2 C, 3.7, 4.1).

### 0.3 Implementation order for `ics` (P, from the coverage counts)

1. VM semantics of 0.2 and the 27 missing expressions (one table-driven evaluator, 5.3).
2. Attribute modifiers 0x10000008 / 0x10000033 with the stacking formula `0x96D460` and messages 0x20F0 / 0x20E8
   (2, A.2-A.3); OnAttributeChanged raised as event 0x100000A2 {attribute}.
3. Status identity (GUID handles), RemoveStatus / SetStatusDuration / stacks / LoadStatusStats, status icons as
   message emitters (3.7-3.8).
4. The action lock (0x1000000E / 0x1000000A / 0x10000015), per-agent cooldown / disable / override / stat-override
   tables with their messages (1.8-1.9), IsInRangeAndAngle for real.
5. SpawnEntity, hotspots / auras, dashes, lobbed / tethered missiles (4.1-4.4).
6. Entity lists, teams, predicates, AI hooks (5.4-5.7); logging no-ops for the single-script unknowns (5.9).

### 0.4 Index: every class `tools/script_coverage.py` still reports (run of 2026-10-22)

`skills hit` = skills whose simulation stops on the class (of 325 skills with a script: 130 run clean, 4 crash, see
5.10). `ab4d80` (actions) / `4fb4c0` (predicates) in the last column = no client half, server-only.

| id | kind | skills hit | old name | spec in section | unpack / client exec (slot 10) |
|---|---|---|---|---|---|
| 0x10000008 | node | 33 | AddAttributeModifier | 2 | `9cb460` / `992a70` |
| 0x100000A7 | node | 30 | AddStatusIcon | 3 | `9b2290` / `ab4d80` |
| 0x10000015 | predicate | 28 | IsServerControlled? | 1 | `97bd30` / `97d7f0` |
| 0x100000A0 | node | 22 | SpawnEntity | 4 | `9cb5a0` / `ab4d80` |
| 0x10000102 | node | 21 | StopScriptlet | 3 | `982850` / `993cf0` |
| 0x100000FA | node | 20 | ShowFloatingText? | 2 | `9afe30` / `ab4d80` |
| 0x1000007B | node | 18 | GetTeam | 4, 5 | `9839e0` / `993690` |
| 0x10000085 | node | 18 | DestructionImpulse | 4 | `9ac1e0` / `ab70c0` |
| 0x100000EA | node | 17 | DashToPosition | 4 | `985fa0` / `ab4d80` |
| 0x100000FC | node | 14 | SetSkillUsable? | 1 | `987690` / `ab4d80` |
| 0x100000EF | predicate | 14 | EntityExists | 5 | `984230` / `9939d0` |
| 0x1000013B | predicate | 13 | OnEvent (filtered) | 1 | `45b6d0` / `4fb4c0` |
| 0x10000033 | node | 12 | RemoveAttributeModifier | 2 | `9cb9c0` / `993b10` |
| 0x100000A6 | node | 12 | RemoveStatusIcon | 3 | `9b2890` / `ab4d80` |
| 0x10000019 | predicate | 11 | OnCastSignal | 1 | `97dc80` / `9c21d0` |
| 0x10000018 | node | 11 | RemoveStatus | 3 | `9b2600` / `ab4d80` |
| 0x100000DB | node | 9 | ResetBasicAttack? | 1 | `984680` / `ab4d80` |
| 0x10000075 | node | 9 | SetTargetingMode? | 1 | `988080` / `ab4d80` |
| 0x10000122 | node | 8 | CreateAura (attached hotspot) | 4 | `9be060` / `ab4d80` |
| 0x1000001A | predicate | 8 | VitalThreshold | 2 | `986700` / `994ec0` |
| 0x100000CE | node | 8 | GetVital | 2 | `9864f0` / `994bd0` |
| 0x10000081 | node | 8 | StopAction | 3 | `9839e0` / `ab4d80` |
| 0x1000008E | node | 7 | SetSkillState? | 1 | `988080` / `ab4d80` |
| 0x10000154 | node | 7 | LaunchLobbedMissile | 4 | `9ad190` / `ab4d80` |
| 0x100001AF | node | 7 | Unk_01AF(entity, -)[0] | 5 | `982850` / `ab4d80` |
| 0x100000E1 | predicate | 6 | IsMoving? | 4 | `988220` / `4fb4c0` |
| 0x10000040 | node | 6 | StartVitalOverTime | 2 | `98e0a0` / `ab4d80` |
| 0x100000C1 | node | 6 | ClearEntityList | 4, 5 | `45fe70` / `97d410` |
| 0x10000118 | node | 6 | ShowFloatingNumber? | 2 | `987530` / `ab4d80` |
| 0x40 | expr | 5 | Heading(vector)[degrees flag] | 5.3 | `46a1e0` / `462f50` |
| 0x46 | expr | 5 | PositionOf(frame) | 5.3 | `46a260` / `4644a0` |
| 0x100000B1 | predicate | 5 | OnAttributeChanged | 1 | `97dc80` / `9c2060` |
| 0x37 | expr | 5 | vector add | 5.3 | `469ee0` / `465270` |
| 0x1000014B | node | 4 | SetCameraMode? | 4 | `983580` / `ab4d80` |
| 0x10000012 | node | 4 | ClearProperty / StopEffect | 3 | `985580` / `993db0` |
| 0x1000005F | node | 4 | LaunchTetheredMissile | 4 | `9ad410` / `ab4d80` |
| 0x10000105 | node | 4 | SetFlag_0105[0/1] | 1 | `987950` / `ab4d80` |
| 0x100000A3 | node | 4 | ReduceCooldown | 1 | `983e80` / `ab4d80` |
| 0x1000002F | node | 3 | SetGraphVariable | 5 | `9871a0` / `9ceac0` |
| 0x1000005B | node | 3 | DisableActions | 3 | `9837d0` / `ab4d80` |
| 0x100000A5 | node | 3 | SetOwner / SetCreator? | 4 | `985d30` / `993480` |
| 0x10000153 | node | 3 | SetSkillStatOverride | 1 | `987290` / `ab4d80` |
| 0x100000DF | predicate | 3 | IsSkillReady? | 1 | `986650` / `994dc0` |
| 0x1000002D | node | 3 | DestroyHotspot | 4 | `985720` / `ab4d80` |
| 0x10000059 | node | 3 | CreateHotspot | 4 | `9cc620` / `ab4d80` |
| 0x100000C3 | node | 3 | GetEntityListCount | 4, 5 | `985d30` / `992da0` |
| 0x10000139 | node | 2 | SetAIEnabled | 5 | `9863c0` / `ab4d80` |
| 0x10000089 | node | 2 | ChangeSkill? | 1 | `9b4b70` / `ab4d80` |
| 0x100000FE | node | 2 | GetStackCount | 3 | `982850` / `ab4d80` |
| 0x100000A8 | node | 2 | UpdateStatusIcon | 3 | `9b3830` / `ab4d80` |
| 0x27 | expr | 2 | Select (cond ? a : b) | 5.3 | `469fe0` / `462f00` |
| 0x1E | expr | 2 | clamp(x, lo, hi) | 5.3 | `469fe0` / `463e80` |
| 0x100000C2 | node | 2 | AddToEntityList | 5 | `985d30` / `9803d0` |
| 0x0D | expr | 2 | normalize | 5.3 | `469e40` / `463ff0` |
| 0x10000009 | node | 2 | StopVitalOverTime | 2 | `9839e0` / `9960b0` |
| 0x44 | expr | 2 | DegToRad | 5.3 | `469e40` / `463f10` |
| 0x2E | expr | 2 | sin | 5.3 | `469e40` / `462af0` |
| 0x10000082 | node | 2 | GetTeamMember | 5 | `983ec0` / `9934f0` |
| 0x1000017F | node | 2 | SetSkillComboState? | 1 | `984250` / `ab4d80` |
| 0x100000FB | node | 2 | SetSkillErrorState | 1 | `987400` / `ab4d80` |
| 0x10000120 | node | 2 | GetEntityRadius | 4 | `9839e0` / `993330` |
| 0x1000000B | node | 2 | SetSkillTarget | 1 | `9839e0` / `9c4c20` |
| 0x10000162 | node | 2 | SetDefeatType / Invincible | 2 | `987b90` / `ab4d80` |
| 0x10000093 | node | 2 | AddTempVital (shield) | 2 | `98dff0` / `9b66a0` |
| 0x1000013A | node | 1 | PlayHitScriptlet? | 3 | `9cbc20` / `ab7620` |
| 0x10000134 | node | 1 | SetMissileVelocity | 4 | `9839e0` / `ab4d80` |
| 0x1000016A | node | 1 | UpdateStatusIconStats | 3 | `9cdd90` / `ab4d80` |
| 0x16 | node | 1 | SetBool | 5 | `983d70` / `45c6b0` |
| 0x04 | predicate | 1 | EventFilter? | 5 | `45beb0` / `45afe0` |
| 0x01 | predicate | 1 | Assign | 5 | `4604e0` / `45bbe0` |
| 0x17 | node | 1 | ClearVariable | 5 | `985d30` / `45c320` |
| 0x100000F1 | node | 1 | SetMovementMode? | 4 | `982fe0` / `ab4d80` |
| 0x100000DD | node | 1 | DestructionRaycast | 4 | `9ac650` / `ab6440` |
| 0x100000C4 | predicate | 1 | IsInEntityList | 4, 5 | `984230` / `980320` |
| 0x10000078 | node | 1 | SetGroundMarker? | 4 | `984580` / `ab56d0` |
| 0x0A | expr | 1 | bitwise and (&) | 5.3 | `469ee0` / `462350` |
| 0x100000B0 | node | 1 | SnapToGround? | 4 | `984960` / `9b6470` |
| 0x10000146 | node | 1 | FindValidPosition2 | 4 | `9845d0` / `ab4d80` |
| 0x10000042 | node | 1 | PickUpEntity? | 4 | `9839e0` / `ab4d80` |
| 0x1000017E | node | 1 | SetDestructibleState? | 4 | `9c7650` / `996b00` |
| 0x1000014D | node | 1 | StartAITask2? | 5 | `9aab70` / `994500` |
| 0x05 | node | 1 | AnyOf (OR) | 5 | `45ff10` / `55b9c0` |
| 0x11 | expr | 1 | pow | 5.3 | `469ee0` / `462a10` |
| 0x07 | expr | 1 | sqrt | 5.3 | `469e40` / `4629d0` |
| 0x10000151 | node | 1 | Unk_0151 (missile) | 4 | `45fe70` / `ab4d80` |
| 0x1000000D | node | 1 | SetAITarget / Taunt | 5 | `983140` / `ab4d80` |
| 0x10000005 | node | 1 | SetSkillAttached | 1, 4 | `983d70` / `ab4d80` |
| 0x3C | expr | 1 | vector.z | 5.3 | `469e40` / `462dc0` |
| 0x35 | expr | 1 | floor/round | 5.3 | `469e40` / `462a70` |
| 0x10000150 | node | 1 | ShowMinimapTargetingRing2 | 4 | `987790` / `ab4d90` |
| 0x1000016F | predicate | 1 | IsInFront? | 4 | `9869f0` / `4fb4c0` |
| 0x10000072 | predicate | 1 | IsClass | 5 | `983bc0` / `993780` |
| 0x10000092 | node | 1 | RemoveTempVital | 2 | `9839e0` / `995fe0` |
| 0x1000004B | node | 1 | GetLevel | 2 | `9839e0` / `9932a0` |
| 0x100000CA | node | 1 | SetStatusDuration | 3 | `9b2d00` / `ab4d80` |
| 0x100000D8 | node | 1 | ShowSkillError | 1 | `987000` / `ab4cc0` |
| 0x1000013E | node | 1 | DashToEntity | 4 | `986860` / `ab4d80` |
| 0x1000001B | node | 1 | CancelMovement? | 4 | `985d30` / `ab4d80` |
| 0x10000083 | node | 1 | TrackTeamEvents | 5 | `984580` / `993a40` |
| 0x100000AD | node | 1 | SuppressInput? | 3 | `983d70` / `ab4890` |

## 1. Skill / cast pipeline (client side) and the client script VM

Exe `InfiniteCrisis.exe`, VAs (image base 0x400000). **C** = read in the decompiled code, **P** = probable (code +
data, not tested in game). Error names come from the client enum `gmErrorTypeList` (ui-complete.md, C).

### 1.1 Overview (who does what)

```
key / click ──► 0xa85da0 skill input (slot) ──► CanActivate 0x8709e0 ──(error)──► HUD error 0xa2f870 (no message)
                     │ ok
                     ▼ targeting type (skill prop 0x1000003D, read by 0x85f6f0)
          instant (5/7)  │  enter targeting mode 0xa26420 (1/11/13/14/16) ── 2nd click 0xa75d20 / 0xa76320
                     ▼
        order API 0xa70030(agent, cmd 2, slot, target) ──► local checks 0x9cfaf0 / 0x8686c0 (buffer)
                     │      also stores the order target locally: props 0x1000018D (IID), 0x100002F9 (position)
                     ▼
        0x20EE  u32 cmd | u32 slot | u64 target IID | Position | u8          (sender 0x88b030)
                     ▼  SERVER: validate again, run the skill's 0x34 script (event 0x1000001D TargetIID / TargetPosition)
        S->C: scriptlets 0x8D (animation, FX), graph events, 0x20F8 cooldown, Usage 0x2077/0x20CE/0x2096 (cast bar),
              0x20C9 (raise the same event on the client copy of the skill script), 0x200F effects, vitals 0x42 ...
```

The client never casts locally: the only C->S message is the order `0x20EE`; everything visible (animation,
cooldown sweep, cast bar, damage) comes back from the server (C for the send path; P that nothing else predicts the
cast, see 1.6).

### 1.2 Input and targeting type (C)

- Skill slots: the agent's skill DIDs live in table properties indexed by slot, table at VA `0x15EDA28`:
  slot 0 `0x100008E3` (basic), 1 `0x100008E8` (Q), 2 `0x100008EA` (W), 3 `0x100008EC` (E), 4 `0x100008E6` (R),
  5 `0x100008EF` (passive), 6 `0x100008E4`, 7 `0x100008F0`, 8 `0x100008F1`, 9 `0x100008F2`, 10 `0x100008E5`,
  11 `0x100008E7`, 12 `0x100008E9`, 13 `0x100008EB`, 14 `0x100008ED`, 15 `0x100008EE` (C). A skill property is
  read with `0x85ee30(agent, slot, propId, out)` (slot < 0x10) -> the skill record's value (vtable +0x10C) (C).
  Slots 10-15 have their own cooldown store (`0x86ec50`: component `0xaa1fd0`, artifacts/items P).
- `0xa85da0(agent, slot, pressed, released?, ...)` (C): walks to the controlled agent (`0x85d1f0`/`0x860d60`),
  calls CanActivate; on an error in {NoCharges, InvalidTarget, Rooted, Crippled, Silenced, NotUsable,
  NoValidTargets, PathBlocked, NoResources, InCooldown} shows the error (`0xa2f870`, HUD only, nothing sent) and
  drops any pending targeting; Stunned with skill bool `0x10000A46`? (`0x861880`) and NoMutex do not abort.
- Targeting type = skill enum property `0x1000003D` (`0x85f6f0`, C). Values in the catalog data (skills.tsv column
  `targeting`) and the client branch (`0xa85da0` switch, `0xa75d20` second click, `0xa70600`):

| value | catalog count | client behaviour (C) | order sent |
|---|---|---|---|
| 1 | 46 | ground point: cursor picked on the navmesh (`0xa25d80`); `0xa70600` param 1 | `0x20EE(2, slot, target 0, point)` |
| 5 | 36 | instant: no targeting mode, cast on key press | `0x20EE(2, slot, 0, null position)` (P for the exact null) |
| 7 | 30 | instant (as 5; skipped by the "enter targeting mode" test) | as 5 |
| 9 | 54 | basic attack (slot 0): handled by the attack / right-click path (targeting-and-relations.md) | `0x20EE(2 or 9, 0, target, pos)` |
| 10 | 0 | skillshot to max range: point = caster + dir(cursor) * (skill stat `0x17` via `0x874990` + caster radius `0x5897a0`) | point |
| 11 | 1 | ground point clamped (`0xa25d80(...,1)`), or the hovered entity's position | point (target 0) |
| 13 | 61 | direction: the picked point projected from the caster (`0x96efa0`) | point (target 0) |
| 14 | 44 | unit target: hovered entity validated by `0x9d01d0(caster, target, slot)`; with `UseSelfCast` (`0x1b7591c`) and no target, the caster itself; else error `0x1b99d812` text | `0x20EE(2, slot, target IID, its position)` |
| 16 | 1 | two-point / vector targeting (`0xa1e1f0`, `0xa6d870`, Lex Luthor R) | point |

- Smartcast option (`SkillSmartcastOption`, user setting) makes `param_4` true -> no targeting mode, cast at the
  cursor at once (C for the flag path in `0xa85da0`).

### 1.3 CanActivate `0x8709e0(agent, slot)` -> ErrorType (C)

Order of the tests (first failure returns); "cond X" = an entry X in the skill-disable-condition list of the local
player (`0xa235f0(agent, slot, X)` -> `0xa11fe0`, entries added/removed by S->C `0x20A0`, see 1.5):

| # | test | returns |
|---|---|---|
| 1 | skill bool `0x10000B4D` false AND not "may act" (`0x9cfaf0`: LifeState `0x100000FA` == 4 and attribute `0x10000B2D` false) | `0x10000054` Skill_UserNotAlive |
| 2 | slot listed in champion array `0x10000B1D` (or -2 = all) (`0x85ed00`), or cond `0x10000066` | `0x10000066` Skill_NotUsable |
| 3 | cond `0x1000003C` | `0x1000003C` Skill_InvalidTarget |
| 4 | slot not 0 and not 6, and rank (`0x863ce0`: champion array `0x100000AF`[slot], or level `0x10000167` for slots >5, slot remapped by skill enum `0x10000A16`) < 1 | `0x10000053` Skill_NotRanked |
| 5 | slot != 6, skill bool `0x10000BC3` (ignore cooldown) false, cooldown left (`0x86ecf0` = stored end time - now) > 0.0002 s | `0x10000033` Skill_InCooldown |
| 6 | slot not in the "usable override" list (`0xa1d580`, see 0x100000FC), skill bool `0x10000A6A` (cost-exempt) false, and the per-slot cost `0x1b75968[slot]` != 0: resource = agent vital kind (`0x85d320`: `[vitals+0x1C]`, default 2 = Will) current value (`0x9700c0`) < abs(cost) | `0x10000055` Skill_NoResources |
| 7 | cond `0x10000045` | `0x10000045` Skill_NoCharges |
| 8 | cond `0x10000059` | `0x10000059` Skill_NoValidTargets |
| 9 | cond `0x10000034` | `0x10000034` Skill_PathBlocked |
| 10 | unless the override flag: attribute `0x100003F3` (Stunned) true, or slot != 0 and the HUD stun flag (`0xa1d5d0`) | `0x10000051` Skill_Stunned |
| 11 | movement skill (skill bool `0x100007FD`): attribute `0x100007FE` Rooted / `0x10000B39` Crippled | `0x10000050` Skill_Rooted / `0x1000006B` Skill_Crippled |
| 12 | slot != 0 and attribute `0x100005A3` Silenced (unless the override flag) | `0x1000003B` Skill_Silenced |
| 13 | another slot is the HUD's active cast (`[hud+0x90]+0xC0`, `0xa1d5b0`) and this skill does not allow queuing (skill bool `0x10000704`, default true = allowed) | `0x10000056` Skill_NoMutex |
| - | otherwise | 0 (ok) |

- Cost per slot `0x1b75968[slot]` is computed **client-side** from the skill record (stat 3 at the current rank) by
  the HUD refresh `0xa7c640` -> `0xa6de10` -> `0xa5dc90` (C for the write, P that the value is stat 3). Attributes
  are read through the attribute component (`obj+0x84`, `0x974940` -> `0x973730`, base value + modifiers) (C).
- Cooldown store: slots 0-9: per-agent map read by `0x86ec50` (component `0xaa1a60` = entity `+0x8C`, value = f64
  end time); written by S->C `0x20F8` (`0xa0e320` -> `0x86eb80`, also the HUD sweep `0x8a6bc0`) (C).
- **Server consequence**: the client refuses on its own (no message) for every error above, so the server only sees
  orders that passed the client's view. The server must keep the same state in sync: cooldown end times (0x20F8),
  disable conditions (0x20A0), stun / silence / root attributes (attribute modifiers or property sets), ranks
  (`0x100000AF`), Will (vitals). It must still validate itself (cheating, latency).

### 1.4 Order message and local gates (C)

`0xa70030(agent, cmd, slot, &target, pos..., flags)`:
1. skill bool `0x10000B4D` false -> `0x9cfaf0` must pass, else return 0 (nothing sent);
2. for cmd 3/4 (move; 3 = attack-move, marker `0x10000F52`; 4 = move, marker `0x1000005C`) and cmd 2/9 with skill
   bool `0x10000708`: navmesh check of the point (`0x4fb400`, `0x868bf0`) and the move-marker FX;
3. `0x8686c0`: cmd 2/9 -> `0x863860`: **buffers** the order (returns non-zero, nothing sent) when the slot is not
   overridden and the agent is stunned and not in a "can queue" state (cases on the agent class 0x40-0x4F), or an
   action lock (`[+0x70]`) is held; cmd 3/4 buffered while a lock is held; the buffer is re-issued when the lock
   clears (listener `0x85ec10` clears it on Stun/0x10000B2D);
4. bookkeeping: `[+0xE8]` last cmd, `[+0x108]` time, hold flag `0x20AB(0)` (`0xa0abf0`), for skills `[+0x16C]`
   last slot and `[+0x170]` time (double-cast filter 0.5 s in `0xa70600`);
5. send `0x20EE` with `0x88b030(cmd, slot, target.lo, target.hi)` + position; cmd 2 with slot 6 also clears the
   targeting state (slot 6 = recall / special, P).

The point / entity of a skill order is also written into the local agent's properties `0x100002F9` (position,
`0xa12140`) and `0x1000018D` (target IID, `0x57fc40`) (C, `0xa75d20`); the client copy of the skill script reads
them back in `Cast` (1.6).

### 1.5 What the server sends back (S->C), and the handlers (C unless noted)

All are "event" messages addressed to the local player IID (layouts in protocol-server-to-client.md, handlers
verified here):

| msg | body | handler | effect on the client |
|---|---|---|---|
| `0x20F8` | `u8 0 \| u64 agent \| u32 slot \| f64 end time` (absolute game clock, same base as `time.time()` in ics) | `0xa0e320` | slot -1/-2 ignored; remaining = end - now (>= 0) -> cooldown store `0x86eb80` + HUD sweep `0x8a6bc0`. To end a cooldown early send end = now (ics does) |
| `0x20A0` | `u8 0 \| u32 slot (-2 = every slot) \| u32 ErrorType \| Handle (16 bytes) \| u8 add` | `0xa6dd10` | adds / removes a disable condition {ErrorType, handle}; CanActivate then fails with that ErrorType. Adding `0x1000006C` (QueueBlocked) also clears queued casts (`0x85ece0`) |
| `0x207B` | `u8 0 \| u64 agent \| u32 slot \| u8 enable \| u8 flag` | `0xa26570` -> `0x870540` | enable: add {slot, flag} to the "usable override" list `[skills+0x60]` (`0x86f0f0`), else remove (`0x860780`); see 0x100000FC |
| `0x2187` | `u8 0 \| u32` | `0xa39f90` | enable skill button (variant, P) |
| `0x20DC` | `u8 0 \| u32 slot \| u32 ErrorType` | `0xa0e3e0` -> `0x8a2ae0` | Flash `GM_UI.RecvNotice_ExecuteSkillError(slot, error, cursor x, y)` (the generic error popup) |
| `0x2092` | `u8 0 \| u32 slot \| u32 kind` | `0xa2a190` -> `0xa2a090` | out-of-resource popup: kind 2 -> Skill_OutOfHealth `0x10000009`, else Skill_OutOfEnergy `0x10000016`; slot -1 / 5 ignored |
| `0x20F9` | `u8 0 \| u64 agent \| u32 slot \| u8 on` | `0xa2a1b0` | raises script event `0x100000B6` (off) / `0x100000B7` (on) with parameter `SkillSlot` (hash 0x31D944) on the agent's script instances |
| `0x20C9` | `u8 0 \| u64 agent \| u32 slot \| ScriptEvent` | `0xa1d400` -> `0xa16e60` | raises the event on the client instance of the slot's skill script (by script DID, `0x96ded0`); events 0x10000009 (interrupt), 0x1000001D (skill used), 0x100000B7 are dropped when the client's slot map (`0x186dd8c`) says another slot; 0x10000023 updates that map |
| `0x20C2` / `0x2084` | `u64 entity \| PropValue` / `u64 entity \| u32 prop` | `0xa0e480` / `0xa0e430` | set / remove a property (skill DIDs per slot, ranks `0x100000AF`, flags) |
| `0x1000015A` (notice) / `0x2091` | `u32 slot \| u32 overlay \| u8 on` / `u64 \| u64 \| u32 \| u32` | `0x8bc9b0` / `0xa5d0a0` | Flash `GM_Skill.RecvNotice_UpdateSkillUIOverlay` (button overlay: primed / charged / combo, P) |
| `0x2077` | `u8 0 \| u64 agent \| u64 ? \| u32 elapsed (f32)` | `0xaa2570` | Usage component `[obj+0x9C]`: induction (cast bar) percent = elapsed / f32 property `0x100004FD` of the agent (cast duration) -> `0x8c1bb0`, Flash `Usage.RecvNotice_UpdateInductionPercent` |
| `0x20CE` | `u8 0 \| u64 agent \| u64` | `0xa9e590` -> `0x8c1820` | induction complete |
| `0x2096` | `u8 0 \| u64 agent \| u64` | `0xaa2620` | induction cancelled (resets `[usage+0x50]`, `0x8c1090`) |
| `0x2082` / `0x20B2` | `u64` / `u64 \| u8 interrupted` | `0xaaf400` / `0xaa4670` | channel started / stopped (channel bar) |
| `0x209F` / `0x217F` / `0x2180` | `u32 \| u64` ... | `0xa5da40` ... | minimap targeting ring (0x10000022 / 0x10000150 nodes) |
| `0x8D` | scriptlets | `0x6279d0` | animation graph + FX of the cast (client-scriptlets-graphs.md) |

The cast animation itself is never a separate "cast" message: it is the scriptlets / graph events the skill script
runs (`RunScriptlet 0x10000034`, `StartScriptlet 0x10000103`, `RaiseGraphEvent 0x1000004E`) (C for the node
classes; P that the original server sent nothing else).

### 1.6 The client script VM: who runs 0x34 scripts on the client

- **Host**: the agent's effects component `entity+0x8C` (getter `0xaa1a60`; list `+0x20`, count `+0x28`) holds
  generic script instances (size 0x1EC, ctor `0x44bd00`) created **only by the server** with `0x200F` / `0x2062`
  (one) and `0x200C` / `0x2043` (list), removed with `0x202B` / `0x2037` (client-status-effects.md, C). Any 0x34
  record can be hosted: status scripts and (P) the skill scripts of the slots (the 0x20C9 path posts events to
  instances by the slot's script DID `0x10000328`, `0xa16e60` -> `0x861580` -> `0x96ded0`, C).
- **Events into client instances** (C): `0x96ded0(event, scriptDID)` queues the event on each instance whose DID
  matches (`0x461430`; an instance only accepts events its graph listens to, sorted list `+0xD8`). Sources:
  `0x2008` (`0xaa1bf0`, u64 agent, u32 event, u32 script DID), `0x2063` / `0x2157` (`0xaa1c90`, list of events),
  `0x204E` (all instances of the agent), `0x202C` (one instance by GUID), `0x20C9` (skill slot), `0x20F9`
  (0x100000B6/B7), attribute changes `0x9723d0` (event `0x10000066` with parameters 0xC58BA9B and
  `MissileFireOffset`(0xA2103E4) - P for the meaning), and nodes (`0x992970` posts `0x10000017` to the slot script
  of an entity).
- **Execution**: a node's client half is vtable slot 10 (`+0x28`); triggers / predicates return a bool from the
  same slot (C: `0x9c21d0`, `0x9c2060`, `0x994dc0`, `0x995310`). 161 classes have an empty slot 10 (`0xab4d80`
  `ret`, or `0x4fb4c0` = `return false` for predicates), i.e. **server-only**; a client instance passing through
  them does nothing (and a predicate with `0x4fb4c0` is false on the client, so client-side transitions guarded
  by it never fire). The client half exists for presentation and local mirrors: attribute modifiers
  (`0x992a70` / `0x993b10`), ShowSkillError (`0xab4cc0`), UI overlay (`0xab63b0`), minimap rings, local-player HUD
  notices, Cast's target copy (`0x9b5a30`), Spend (`0x9b6860`, local Will prediction via vitals vtable +0x5C).
  The instance ticking (enter/update/exit, timers) runs in the effects component update (not traced, P).
- **Authority**: the server runs the full script; the client copy only renders. Values the client copy computes
  (TargetIID etc.) are not sent back. So a server **must** do every server-only node, and should also send the
  message equivalent of the client-half nodes when it does not replicate the instance to the client (ics does not
  replicate skill instances today) (P, design consequence).
- **Script context interface** used by node code (C, from the callers): `ctx->vfunc 0x24/0x20` = runtime (`+0xB4`
  = current event: `+8` id, `+0xC` parameter bag with a hash -> offset table at `+8`/`+0x18`); `ctx->vfunc 0x2C(2)`
  = owner block (`0x44c5c0` reads SELF IID by hash `[0x1854350]`); `ctx->vfunc 0x30(n)` / `0x34(n)` = variable
  block n (sources 1-6 of an operand), value at `[block+8] + slot`; `ctx->vfunc 0x18` = the script's DID;
  `ctx->vfunc 0x14` = the instance GUID (16 bytes, compared with `0x96c650`).
- **Operand resolution** (C): `0x992280(ctx, &operand, &iid)` reads an entity operand (u64 IID); `0x992470` an
  entity-or-position operand (position object + entity); `0x9921e0(ctx, &slot)`: slot -1 = "the slot of this
  script" = the slot whose skill script DID equals the context's DID (`0x85eed0`), fallback the skill record
  passed in `0x991f60`.

### 1.7 Triggers and events (C unless noted)

- Builtin `0x06` Event (Unpack `0x45b6d0`: r4 event id at `+8`): test `0x45af80` = current event id == r4 (an
  instance with no current event only matches r4 = -1).
- Builtin `0x04` (`r4 r1 r1`, test `0x45afe0`): true if an event with id r4 is in the instance's **pending** queue
  (`+0x10`, flag 1) and / or its **in-flight** list (`+0x60`, flag 2) - "HasPendingEvent", not an event filter.
- `0x10000019` "OnCastSignal" (Unpack `0x97dc80` = Event + r4 value at `+0xC`; test `0x9c21d0`): Event(r4 id,
  in practice `0x1000000F`) AND the event's parameter with hash `[0x186a6a0]` == value (2 / 3 / 5 = chain result
  codes). Used as a predicate inside lists too (11 coverage hits): same test against the current event.
- `0x100000B1` OnAttributeChanged (Unpack `0x97dc80`; test `0x9c2060`): Event(r4 = `0x100000A2`) AND (value 0, or
  the event parameter hash `[0x186a664]` (attribute id) == value, or == the value remapped by `0x96f4f0`
  (aliases: `0x10000200`/`0x10000482`/`0x10000483`/`0x10000573`/`0x100007A3` -> `0x10000484`, and
  `0x10000485..0x10000487`/`0x10000574`/`0x100007A4` -> `0x10000432`, when the owner's vitals kind matches)).
  Server: raise event `0x100000A2` with the attribute id parameter on the owner's scripts whenever an attribute
  value changes (modifier added / removed, base set).
- `0x1000013B` OnEvent (Unpack `0x45b6d0` = Event; slot 10 `0x4fb4c0` = always false on the client): a
  **server-only** event trigger; in data r4 = `0x1000001D` (skill used) or `0x10000023`. As a predicate inside
  AnyOf / AllOf it must evaluate like Event (current event id == r4) (P for the server meaning; C that the client
  never fires it).
- `0x10000055` OnEntityEvent (r4 `0x10000002` collision) - implemented in ics.
- Event `0x1000001D` (skill used) parameters: `TargetIID` (hash 0x8DCD754), `TargetPosition` (0xE2D648E) (C:
  `Cast` client half `0x9b5a30` reads them from the current event; without that event it reads the order props
  `0x1000018D` / `0x100002F9`).
- `0x100000B6` / `0x100000B7`: skill unavailable / available, parameter `SkillSlot` (0x31D944) (C, `0xa2a1b0`).
- Re-init family (in every skill's listener list): `0x10000008`, `0x1000000C`, `0x100000A9`, `0x100001B3`
  together with `0x100000D2` (see below) - rank / level / stat change (P).

### 1.8 Node specs: skill-state nodes

Format: id, vtable, **Unpack** field order (B next, O operand value|source|slot, rN raw), **client** slot 10, then
what the **server** must do. Examples are from `data/script_trees` (`ex.py`). "slot r4" uses -1 = the slot of the
running skill script (resolved like `0x9921e0`), -2 = every slot (C for -1/-2 in `0xa6dd10` and `0x9921e0`).

#### 0x10000015 "IsServerControlled?" -> **HoldsActionLock** (vt 0x15FA758, predicate, no fields)
- Client `0x97d7f0` (C): owner entity's effects component (`+0x8C`) exists and `0x96c650(component, ctx GUID)`:
  true if the component's **action-owner GUID** (`+0x44..+0x50`) is null or equals this instance's GUID.
- Pairs with BeginSkill / EndSkill below (they set / clear that GUID). Used in 64 transitions together with
  IsAlive / IsValid / Relation: "still the skill that owns the champion's action".
- Server: per agent keep `action_owner` (instance or None); predicate = `owner is None or owner is this
  instance`. 28 coverage hits (C semantics).

#### 0x1000000E BeginSkill (vt 0x15FA6C8, no fields; ics: no-op stub)
- Client `0x97d6b0` -> `0x96de00` (C): if the agent's action owner is null or this instance, and the instance is
  running (`[inst+0x1E8] == 2`), set the owner = this instance's GUID (acquire the action lock).
- Server: `action_owner = this instance` if free (else nothing). The lock is what `0x10000015` tests; the client's
  order buffering (`0x8686c0`) uses a separate lock (`[+0x70]`) which the server does not drive directly (P).

#### 0x1000000A EndSkill (vt 0x15FA8D8, `B r1`; ics: no-op stub)
- Client `0xab4b50` -> `0x96c5d0` (C): if the owner GUID is this instance, clear it. r1 (0/1) not read by the client
  half (P: "notify skill complete").
- Server: release `action_owner` if it is this instance; then the champion may take the next order / resume
  basic attacks (P).

#### 0x100000D2 "IsSkillActive?" -> **IsSlotSkillScript** (vt 0x15FA848, predicate, Unpack `0x654ea0` no fields)
- Client `0x97d8d0` (C): true iff the running script's DID is the script (`0x10000328`) of one of the owner's 16
  skill slots (`0x85eed0` != -1).
- Use: the re-init transition `AllOf(AnyOf(Event 0x10000008, 0x1000000C, 0x100000A9, 0x100001B3), 0x100000D2)`:
  reload stats only when the instance is a slot skill (not a status). Server: same lookup.

#### 0x100000DF "IsSkillReady?" -> **IsSkillOffCooldown** (vt 0x15FCD9C, predicate `r4 O`)
- Unpack `0x986650`: r4 slot (`+8`), O skill operand (`+0xC`).
- Client `0x994dc0` (C): slot = r4; if the operand is set, its value is a **skill DID** mapped to a slot
  (`0x85c2e0`); if r4 is -1, the script's own slot. True when the cooldown left (`0x86ecf0`) <= 0.
- Example `0x34000014`: `S2 -> S0 on IsSkillOffCooldown(-)[-1]` (the basic attack waits for its own cooldown).
- Server: `cooldown_end[agent][slot] <= now`. 43 coverage hits.

#### 0x100000D8 ShowSkillError (vt 0x15FD390, `B O r4 r4`)
- Unpack `0x987000`: O entity (`+0x14..`, usually SELF / -), r4 ErrorType (`+0xC`), r4 slot (`+0x10`, -1 own).
- Client `0xab4cc0` (C): if the local player has an agent: `GM_UI.RecvNotice_ExecuteSkillError(slot, ErrorType,
  cursor)` (`0x8a2ae0`).
- Examples: `[0x10000034 PathBlocked, -1]` (leap with no path, 0x34000038), `[0x10000059 NoValidTargets, 4]`.
- Server: send **`0x20DC`** `u32 slot | u32 ErrorType` to the owner's player (same function on the client) (C for the
  message equivalence). No gameplay effect.

#### 0x100000FB SetSkillErrorState -> **SetSkillDisableCondition** (vt 0x15FD4B4, `B r4 r4 O r1 O`)
- Unpack `0x987400` (field order): r4 ErrorType, r4 slot (-1 own, -2 all, n), O entity (always `-` = SELF in data,
  P), r1 add (1) / remove (0), O handle variable (`$ErrorStateHandle`: out on add, in on remove).
- Client: none (`0xab4d80`).
- Examples: silence status `0x340001C1`: `[0x1000003B Silenced, -2, add]` on enter, `[.., remove]` on exit;
  `0x3400019D`: `[0x10000045 NoCharges, -1, add]`; also `0x10000066` NotUsable, `0x10000059` NoValidTargets.
- Server: keep the condition set per agent {ErrorType, handle}; refuse the skill with that error; send **`0x20A0`**
  `u32 slot | u32 ErrorType | Handle(16) | u8 add` to the owner (handle = the same 16 bytes on add and remove; the
  client removes by {ErrorType, handle} match, `0xa19560`) (C for the client match, P for the handle layout =
  u32 + pad + u64 as in protocol notes).

#### 0x100000FC "SetSkillUsable?" -> **SetSkillUsableOverride** (vt 0x15FD514, `B O r4 r1 r1`)
- Unpack `0x987690`: O entity (agent), r4 slot (-1 own / n), r1 enable, r1 flag.
- Client: none.
- The client list it feeds (`[skills+0x60]`, entries {slot, flag}) is read by CanActivate: a listed slot skips the
  cost test; its flag also skips Stunned / Silenced / NoMutex and the stun order buffer (`0x863860`) (C for the
  reads). Examples: `[-1, 1, 1]` on a shooter (allow while stunned), `[4, 1, 1]` / `[4, 0, 1]` (0x34000217, the R
  slot), `[-1, 0, 0]` remove.
- Server: send **`0x207B`** `u64 agent | u32 slot | u8 enable | u8 flag`; mirror the same bypass in the server's
  own validation (P: semantic name; C: message <-> list).

#### 0x10000097 "SetSkillCooldownState?" -> **UpdateSkillUIOverlay** (vt 0x15FD848, `B r4 r1 r4 O`; ics: no-op)
- Unpack `0x987d20` (C): r4 overlay id (`+0x10`), r1 on/off (`+0x14`, must be 0/1), r4 slot (`+0xC`, -1 = the HUD's
  current slot `0xa1cd20`), O slot operand (overrides when set).
- Client `0xab63b0` (C): for the local player agent `0x8bc9b0(agent, slot, overlay, on)` =
  `GM_Skill.RecvNotice_UpdateSkillUIOverlay`.
- Examples `0x3400003A`: `[1, 0, -1]`, `[1, 1, -1]` (overlay 1 on / off on the own slot: primed / empowered look).
- Server: send notice **`0x1000015A`** `u32 slot | u32 overlay | u8 on` (or event `0x2091`) to the owner (P for which
  of the two the original used). Cosmetic.

#### 0x10000153 SetSkillStatOverride (vt 0x15FD454, `B O r4 r4`)
- Unpack `0x987290`: O value, r4 slot (-1 own / n), r4 skill stat id.
- Client: none.
- Examples: `0x340001FD` (a buff that makes Q/W/E free): `($ZeroCost = 0)[1, 3]`, `[2, 3]`, `[3, 3]` (stat 3 =
  cost); `0x34000248`: `($RevealRadius)[-1, 18]` (stat 18 = range).
- Server: store `stat_override[agent][slot][stat] = value`; LoadSkillStats (0x1000009F) / cost / range read the
  override first. The client computes costs itself (1.3), so to show / allow a free cast the server must also make
  the client's check pass: send the slot as usable override (`0x207B`, skips the cost test) or adjust nothing and
  rely on server validation (P).

#### 0x1000008E "SetSkillState?" -> **ClearSkillStatOverride** (vt 0x15FDBAC, `B O r4`)
- Unpack `0x988080`: O entity (- = SELF), r4 slot (-1 own / n).
- Client: none. Example `0x340001FD` exit: `[1]`, `[2]`, `[3]` right after the overrides above end; most skills
  call it with `[-1]` when re-initialising.
- Server: drop the stat overrides of that slot and recompute its stats (P, from the pairing).

#### 0x10000089 "ChangeSkill?" -> **SetSlotSkill** (vt 0x15FDB7C, `B O r4 O r1 O`)
- Unpack `0x9b4b70`: O entity, r4 skill DID (`0x48...`), O (-), r1 flag, O (-).
- Client: none. Examples: `(SELF)[0x4800077A, 0]` (0x3400028E), `[0x48000A95..A97, 0]` (0x34000451/454/455: form
  swaps).
- Server: replace the skill in the given slot (operand / slot from context, P) - set the slot table property
  (`0x100008E3`...) of the agent with `0x20C2` / event 0x6, (re)start the new skill's script, keep the rank;
  raise `0x10000023` (slot map) on the client copy (P).

#### 0x1000017F "SetSkillComboState?" (vt 0x15FD574, `B r4 O O`)
- Unpack `0x984250`: r4 (always 7 in data), O value (`$KatanaQ`, `$KatanaQW` ... state bools), O (-).
- Client: none. Only Katana (`0x340005B9`) and a few units. Meaning P: sets combo stage `r4=7` of the champion's
  slot overlay / animation set. Server: store the value; candidate effect = slot override `0x207C`
  (`u32, u8, u32` per slot) (P, low).

#### 0x100000A3 ReduceCooldown (vt 0x15FC9B4, `B O r4 O`)
- Unpack `0x983e80`: O entity, r4 slot (-1 own, -2 all, -3 = all but the own slot? P), O seconds.
- Client: none. Examples: `(SELF, $PrimedCooldownDuration)[-1]`, `(SELF, $CooldownReduction)[-2]`,
  `($EffectSource, $WWCooldownReduction)[-3]`.
- Server: `end = max(now, end - seconds)` for the selected slots, then send `0x20F8` with the new end time (C for
  the message; P for -3).

#### 0x100000DB "ResetBasicAttack?" -> **QueueOrder** (vt 0x15FBE48, `B O O r4 r4 r1 r1 r1`)
- Unpack `0x984680`: O entity (SELF), O target (or -), r4 command (always 2 = use skill, same codes as 0x20EE),
  r4 slot (always 0 = basic attack), r1 x3 flags (`[0 0 1 0]`, `[0 0 0 1]`, `[0 1 0 0]` variants: P = clear queue /
  only if idle / attack-move).
- Client: none. Seen at the end of leaps / dashes (`0x34000038`, `0x340000C6`, `0x34000185`).
- Server: after the skill, issue the order "basic attack target" for the champion (resume auto-attack on the
  skill's target) (P).

#### 0x10000075 "SetTargetingMode?" (vt 0x15FD2D0, `B O r4`)
- Unpack `0x988080` (same reader as 0x1000008E): O entity, r4 (always 0).
- Client: none. In basic attacks and pick-up / carry scripts (`0x34000014`, `0x34000164`, `0x34000219`). P: clear
  the champion's pending order / attack target (slot 0). Server: cancel the queued order (P, low).

#### 0x1000000B SetSkillTarget -> **AddSkillTarget** (vt 0x15FC8CC, `B O O`)
- Unpack `0x9839e0`: O entity (SELF), O target.
- Client `0x9c4c20` (C): if the entity has an effects component, append the target IID to its u64 array
  `+0x64` (count `+0x6C`, `0x9c3770`).
- Server: remember the target in the agent's "current skill targets" (used by later queries, e.g. 0x10000024 /
  AI) (P for the consumer).

#### 0x10000005 SetSkillAttached (vt 0x15FD2A0, `B O r1`)
- Unpack `0x983d70`: O entity, r1 on/off. Client: none. Pairs in the basic attack (`0x340000C6` `[1]`) and the
  attach skill (`0x340000E0` `[0]`). P: mark the champion as channeling / attached (blocks other orders). Server:
  per-agent flag; stop the champion's movement while 1 (P, low).

#### 0x10000105 "SetFlag_0105" (vt 0x15FA908, `B r1`)
- Unpack `0x987950`: r1 0/1. Client: none. Only in two "primed" skills (`0x3400003A`, `0x34000095`) around the
  primed state (with UpdateSkillUIOverlay 1). P: "skill primed" flag of the instance (next basic attack empowered).
  Server: store; no message known.

#### 0x10000195 "SkillEcho?" (vt 0x15FD3F0, `B O`; ics: no-op)
- Unpack `0x985d30`: O entity (- = SELF). Client: none. In 221 skill scripts, right after the cast point.
  P: notify "skill used" to the owner's listeners (Stolen Powers / passives that trigger on any skill use: raise
  event `0x1000001D`-like on other scripts, or the HUD "last skill" stat). Keep as no-op until a listener needs it.

#### 0x10000136 "TriggerSkillUsed?" -> **ActivateSlotSkill** (vt 0x15FD360, `B r4 O O O`)
- Unpack `0x986f40`: r4 event (`0x1000001D`), O target IID, O position, O slot.
- Client: none. Examples: Super Strength (`0x34000161`, `0x34000177`): `(-, -, $SuperStrengthSkillSlot)
  [0x1000001D]`.
- Server: raise the event (skill used, with `TargetIID` / `TargetPosition`) on the script of the given slot of the
  owner - i.e. cast another skill from script (P, high).

#### 0x10000148 SetTargetingMode -> **GetSkillTargetingType** (vt 0x15FCCDC, `B O O r4 O`)
- Unpack `0x986420`: O out variable, O entity, r4 slot (-1 own), O slot operand.
- Client `0x994ab0` (C): writes the slot's targeting enum (`0x1000003D`, `0x85f6f0`) into the out variable, typed
  as enum table `0x10000034`.
- Server: same read from the skill record (values as in 1.2).

#### 0x10000052 IsInRangeAndAngle (vt 0x15FD008, predicate `O O O O O r1 r1`; ics: stub true)
- Unpack `0x986a30`: O min distance (`+0x8`), O max range (`+0x20`), O half-angle in degrees (`+0x38`), O target
  (entity or position, `+0x50`), O source (`+0x68`, unset = SELF), r1 add source radius (`+0x80`), r1 add target
  radius (`+0x81`).
- Client `0x995310` (C): d2 = squared 2-D distance source -> target; false if min set and d2 < min^2; r = max
  (+ source radius `0x5897a0` if flag) (+ target radius if flag); false if r > 0 and d2 > r^2; if the angle is set
  and not 0 / 360: false if the angle between the source's facing and the direction to the target exceeds it
  (with a radius correction when the target-radius flag is set). Else true.
- Example: `IsInRangeAndAngle(-, $Range, -, $TargetIID, -)[1 1]` = "target within range + both radii".
- Server: implement exactly (needed for basic attacks and melee skills: today every target is in range).

#### 0x10000057 ReleaseFacing (vt 0x15FD184, `B O`; ics: no-op)
- Unpack `0x985d30`: O facing handle (`$FacingIDVariable`, from FaceTarget 0x1000003F).
- Client `0x995e80` (C): reads the handle, calls an empty function (`0xab4b40`) - nothing.
- Server: drop the facing lock created by FaceTarget so movement steers the champion again.

### 1.9 What ics must add for a complete cast (summary, P)

1. Validate orders with the CanActivate list (1.3) using server state; on failure send `0x20DC(slot, error)`.
2. Per agent: cooldown ends (0x20F8 on start / reduce / reset), disable conditions (0x20A0), usable overrides
   (0x207B), stat overrides, the action lock (BeginSkill / EndSkill / 0x10000015), facing locks.
3. Run the slot's script with event 0x1000001D {TargetIID, TargetPosition} from the 0x20EE fields; cast time:
   Usage 0x2077 (elapsed) / 0x20CE / 0x2096 with property `0x100004FD` = cast duration on the agent.
4. Raise `0x100000A2` {attribute} on attribute changes, `0x100000B6/B7` {SkillSlot} on availability changes.
5. Implement IsInRangeAndAngle for real (range stat + radii).

Open: the hash behind `[0x186a6a0]` (OnCastSignal parameter) and `[0x186a664]` (attribute id parameter) is set at
run time (no static writer found); the original server's use of `0x2091` vs notice `0x1000015A`; which of the
skill-state nodes with an empty client half (0x10000075, 0x10000005, 0x10000105, 0x1000017F, 0x10000195) had any
client-visible effect.

## 2. Attributes, stats, damage, vitals and floaties

Client `InfiniteCrisis.exe` (VA, image base 0x400000), Ghidra decompilation in `re-work/decomp`, data from the
packs (ics/gamedata.py) and the decoded trees (`data/script_trees`). **C** = read in the client code or exact data,
**P** = probable (inferred), **?** = open. Node operand order is the serialization order (= `ics/script_model.py`
`Node.operands`); "values" are the raw r1/r4 fields in order.

### A.1 What an attribute is (C)

- An **attribute** is an ordinary property descriptor of **group 0x3F** (`properties-complete.tsv`, column `grp`):
  146 descriptors, almost all `net=1` (NetSharedVisually) in the object table `[ent+0x38]`. Kinds: f32 (stats),
  bool (state flags such as Stunned `0x100003F3`, Silenced `0x100005A3`, Rooted `0x100007FE`, Exposed `0x100006F3`,
  Targetable tags `0x10000029` / `0x10000249`), int, u32, one IID (`0x1000099A`).
- The **base value** is the property value on the entity (what the server sends at creation or later with the
  set-property event `0x6`). Every read goes through the **attribute component** `[ent+0x84]` (getter `0xAA0DC0`):
  `0x974940(ent, &viewerIID, &attr, default)` (bool) / `0x9735D0` (float) / `0x973890` (int) / `0x973730` (raw),
  all built the same way (C):
  1. `0x96F4F0` **aliases** resource-specific ids to the generic ones when the entity's resource type matches:
     `0x10000200`(1) `0x10000482`(4) `0x10000483`(5) `0x10000573`(3) `0x100007A3`(6) -> **`0x10000484` resource
     regen**; `0x10000487`(1) `0x10000485`(4) `0x10000486`(5) `0x10000574`(3) `0x100007A4`(6) -> **`0x10000432`
     resource max**; the number is the resource (vital) type, compared with the vitals component `[ent+0x80]+0x1C`
     by `0x96E5D0` (type 2 = health always matches). When the type does not match, the read returns "no value".
     So the champion stat block uses the generic ids (Batman: `0x10000432` 100, `0x10000484` 5) and items use the
     specific ones (Will items: `0x10000486` / `0x10000483` = resource type 5).
  2. base = component vtable `+0x60(attr)`; then the **modifier list** of that attribute: first the component's
     own hash (`+0x10` bucket count, `+0x14` used, `+0x1C` buckets; node `+4` attr, list at node `+0x10`), else the
     **per-team table** `[+0x30][team]` (`+0x38` count; team = `0x854050(ent)`), then `0x96D460` applies them.
  3. `0x973410(out, &viewerIID, attr, mode)` is the variant used by expression **`0x10000002` GetAttribute**: mode
     **0 = current (base + modifiers)**, **2 = `+0x54` value (unmodified base)**, **1 = current - base (the bonus)**.
- The expression `0x10000002` (vtable `0x15FDD28`, unpack `0x9888D0`, evaluate `0x996D10` -> `0x9748A0` ->
  `0x973410`) has fields `attr | entity operand (hash, source, slot) | mode` (C). In the 875 scripts: mode 0
  (`Stunned 0x100003F3` x168, attack speed `0x100006FE` x66, Health `0x10000426`, AD `0x10000B76`, MS, armors,
  lifesteals) and mode 1 (bonus Will `0x10000486`, bonus Power Armor `0x10000B7A`, bonus Power Damage `0x10000B75`,
  bonus Health). Unset entity = the script owner.

### A.2 Modifiers: storage, ops and the stacking formula (C)

**Modifier entry** (0x40 bytes, list per attribute, kept sorted):
`+0x00 u64 source IID | +0x08 Handle {u32 type, u64 id} | +0x18 u32 op | +0x20 Value (16-byte variant) | +0x34 u32
stack group | +0x38 scaling object (vtable +4 = multiplier) `. Only source, handle, op and value travel on the wire
(serializer `0x973380`), so network modifiers have group 0 and no scaling.

**Sort order** (comparator `0x96C420`, insertion/intro sort `0x976330`): by op rank, then by group:
op 0 (rank 1) < 4 (2) < 6 (3) < 7 = 9 (4) < 1 (5) < 10 (6) < 2 (7) < 3 (8) < 8 (9) < 5 (10).

**Evaluation** `0x96D460(attr, list, base, viewer)`, by the attribute's kind (`0x4FB670`):
- f32 (kind 9) and int (kind 0x10, converted to float, result rounded half up):
  - op **7** = op 9 with the value negated (subtract).
  - value `v` (times the scaling object's multiplier if any).
  - op **0 / 5 / 6 = set** (`x = v`); with the sort order, 0 and 6 set *before* the additions, 5 sets at the very end.
  - op **2 = divide** (`x = x / v`).
  - ops **9 (add), 1 (add |sum|), 10 (add percent)** accumulate per run of equal (op, source IID, group): positives
    `P` (sum) / `Pmax`, negatives `N` / `Nmin`. At the end of a run: `pos = f(attr, op, group, +) * (P - Pmax) + Pmax`,
    `neg = f(attr, op, group, -) * (N - Nmin) + Nmin`, where **f** = stacking factor from the attribute rules
    (`0x855BE0` -> `0x8537C0`; **default 1.0** = plain sum; 0 = only the strongest counts). Then op 9: `x += pos + neg`;
    op 1: `x += |pos + neg|`; op 10: `pct += pos + neg`, and when the next entry has another (op, source) `x *= 1 + pct`.
    So **percent modifiers from one source add, from different sources multiply**; percent applies after the flat adds.
  - ops 3, 4, 8 on numbers accumulate but are never applied (no effect).
  - After the list, if any modifier other than op 0 was seen: **soft caps** `0x855670` (per-attribute piecewise-linear
    table `{threshold, slope, pivot flag}` from the rules: above each threshold `x = (x - t) * slope + t`; below the pivot
    the same downwards).
- bool (kind 0x16): op 0/5/6 set, **op 3 = OR**, **op 8 = AND** (Stunned and the other CC flags use op 6 = set true).
- double/timer (7) and enum (8): the last op 0/5/6 modifier wins (`8` default `DAT_01B74F24`).
- vector (0xF) `0x96CDE0`, qword (0x13) `0x96CD60`: per-op component updates (not used by the scripts).

**Ops in the data** (0x10000008, 248 nodes): 6 (90, bool flags), 9 (85), 10 (56), 3 (7), 7 (4), 5 (4); item stat
bonuses (`0x1000068B`, enum `0x3000000A` = the same op enum as `0x10000AE0` in the rules): 9 and 10. The op enum's
names are not in the packs we index (record `0x3000000A` not found).

**Attribute rules record** (C for the reader, ? for the data): `0x85B370` builds a singleton from property
`0x10000032` (`0x4FED80(0x10000032, 0xF)`): array `0x10000616` (attributes shown in the character panel), array
`0x1000045D` of tables keyed by `0x1000045B` (attribute id, kind 0x0A), read by `0x8587B0`: `0x1000045A` /
`0x10000B42` / `0x10000614` / `0x1000061C` / `0x10000659` strings (name, tooltip ...), `0x10000621`, `0x1000046B`,
`0x10000B98`, `0x10000CB9` bools, `0x10000BA8` int, `0x1000048A` category (1 Attack, 2 Defense, 3 Power, 4 Utility),
`0x10000497` f32, `0x10000615` icon DID, `0x10000712` f32 display scale (default 1), `0x10000714` int precision,
**`0x100004BE` soft caps** (`0x100004C0` pivot bool, `0x100004C1` / `0x100004BF` f32), **`0x10000ADF` stacking
factors** (`0x10000AE0` op, `0x10000ADD` group enum `0x30000292`, `0x10000ADE` positive bool, `0x10000AE1` factor).
A key scan of the 604 small packs found no record holding `0x1000045D` / `0x10000ADF` / `0x100004BE` with the usual
key echo: **the rules data is not located** (P: a global config record of another layout). Consequence for the server:
use factor 1 and no soft caps until it is found (the client shows the same numbers then).

### A.3 Attribute messages the server sends (C for formats; protocol rows 0x20E7 / 0x20E8 / 0x20F0)

| msg | handler -> method | body | effect |
|---|---|---|---|
| `0x20F0` add | `0xAA0EC0` -> `0x97A830` | `u8 0 \| u32 attr \| u64 source IID \| Handle{u32,u64} \| u32 op \| Value \| u32 team` | team = -1: the entity's own list (`0x97A230`: insert `0x975F40` or replace same handle `0x8383F0`, then sort); else the per-team table of that team index |
| `0x20E8` remove | `0xAA0EF0` -> `0x979D90` | `u8 0 \| u32 attr \| Handle{u32,u64}` | removes by handle (own list, then every team table) |
| `0x20E7` sync | `0xAA0F20` -> `0x97A300` | `u8 0 \| own map {attr -> list} \| per-team maps` (+ 2 flag bytes) | replaces everything |

`Value` = `u32 type | payload` (`0x456CE0`): 0 bool (u8), 1 int32, 2 uint32, 3 f32, 4 DID, 5 int64, 6 uint64,
7 double, 8 IID, 9 vector, 0xA position, 0xC/0xD/0xE/0xF/0x11 others; an unknown type is a stream error. So a
"+30 attack damage" item is `attr 0x10000B76, op 9, Value {3, 30.0}`; Stunned is `attr 0x100003F3, op 6, {0, 1}`.
**Server rule (P):** keep base stats as properties (level formula below) and send every buff / item / status as a
`0x20F0` modifier with a unique handle; remove with `0x20E8`. The HUD, the stats panel, CanActivate (Stunned,
Silenced, Rooted, Crippled, `0x10000B2D`), the attack validator (Targetable tags) and the fog (`0x10000642`,
`0x100007C0`) all read through the component, so they follow.

### A.4 Stat ids (C ids; names from item_stats.tsv / champion stats / scripts)

| attr | stat | base source | notes |
|---|---|---|---|
| `0x10000426` | Health (max) | champion stats / unit stat block | items op 9 |
| `0x10000140` | Health regen /s | champion stats | stats panel shows it via `0x9735D0` |
| `0x10000432` | Resource max (generic) | champion stats | alias target (A.1) |
| `0x10000484` | Resource regen (generic) | champion stats | alias target |
| `0x10000486` / `0x10000483` | Will max / Will regen (resource 5) | items | op 9 / op 10 |
| `0x10000B76` / `0x10000B75` | Attack Damage / Power Damage | stats / items | |
| `0x10000B84` / `0x10000B7A` | Attack Armor / Power Armor | stats / items | |
| `0x10000B83` / `0x10000B7E` | Attack / Power penetration, flat | items (10-20) | |
| `0x10000B7D` / `0x10000B82` | Attack / Power penetration, percent | (no item) | P |
| `0x10000B7C` / `0x10000B7F` | Attack / Power lifesteal (fraction) | items 0.03-0.3 | statuses add with op 9 (`0x340000C6`) |
| `0x10000B46` | Critical chance (fraction) | items 0.15-0.25 | |
| `0x10000B80` | Critical damage multiplier | unit stat blocks: 2.0 | P (item_stats lists it as "Critical Chance") |
| `0x10000B7B` | Cooldown reduction | items 0.05-0.15 | the panel shows `value - 1` when > 0 (`0xAAD2B0`), so the stored value may be 1 + CDR (P); skills read it as `CooldownReduction` and do `CooldownDuration - CooldownReduction` (0x3400000C) |
| `0x100006FE` | Attack speed (attacks/s) | champion stats (0.6 + 0.023/lvl) | items op 10 (+%) |
| `0x100005FE` | attacks per second used by the basic attack | not a descriptor | basic attack cooldown = 1 / max(x, 0.1) (P: derived from `0x100006FE`) |
| `0x100005E4` | Move speed | champion stats 3.9 | items op 9 (+0.05..0.2) |
| `0x100004AA` | Resilience (CC reduction, P) | items 0.15 / 0.3 | |
| `0x10000642` | vision radius bonus | unit blocks 2.0 | fog |

**Level scaling (C data, P exact rule):** champion stats record (`0x100008E2` -> array `0x100008E0` of {`0x10000100`
stat, `0x100008DF` at level 1, `0x100008DE` per level}) = `ScaleByLevel(Level, base, delta)` = `base + (Level - 1) x
delta` (expression `0x10000003`, vtable `0x15FABDC`, evaluate `0x97D2F0`; 4th field = flag byte +0x14 (unpack
`0x988860`): when set and the level child is zero the base is returned). Units: stat block `0x10000165` with 0x3B
formulas over the unit level `clamp(floor((Time + 90) / 90), 1, 100)` (units-and-ai.md 3.3). Level property
`0x10000167` (node `0x1000004B` reads it).

### A.5 Damage types, mitigation, crit, lifesteal (P unless marked)

- **Damage type** = the 5th value of ApplyDamage (`0x1000001D`): **1 = Attack (physical)**, **2 = Power**,
  **3 = True** (C data: every basic attack (65/65) uses 1; skills mix 1/2; 3 is rare: 0x34000456, 0x3400020A,
  0x34000202). Skill property `0x10000706` (enum `0x300001F7`, the same enum as `0x1000069B` and the script
  variables `IncomingDamageType` / `TriggeringDamageType`) is the skill's damage type shown by the HUD.
- **Mitigation is server-only**: no client function computes it (the client only shows armor values). Use the
  usual MOBA form until evidence appears: `eff = max(0, armor x (1 - penPct) - penFlat)`,
  `dealt = raw x 100 / (100 + eff)` with Attack Armor / Attack pen for type 1, Power Armor / Power pen for type 2,
  no mitigation for 3. (P / assumption.)
- **Crit**: `RollCritical 0x1000010B (out roll, target, -)` runs at cast time and the roll goes to ApplyDamage's
  3rd operand (`CriticalChanceRoll`, 58 basic attacks and 5 skills). Server: `roll = random() < CritChance(caster
  0x10000B46)`; ApplyDamage multiplies by `0x10000B80` (default 2.0) when the roll is true and marks the floaty as a
  crit. `0x34000640` reads it back as `WasCrit`.
- **Lifesteal**: after mitigation heal the source by `dealt x 0x10000B7C` (type 1) or `x 0x10000B7F` (type 2).
- **Attack speed / CDR**: the basic attack reads its cooldown from `GetAttribute(0x100005FE)`; skill scripts compute
  their cooldowns themselves from `CooldownReduction` (stat 15 = cooldown).
- **Will / resources**: cost = stat 3 (negative), spent by `SpendCost 0x10000031`; `VitalThreshold` with the negate flag
  is the "enough resource" check (B.2).

### B.1 Vitals (C)

Vitals component `[ent+0x80]` (getter `0xAA05A0`). Vital list `[+0x18]`: **index 0 = Health (vital id 2), index 1 =
the entity's resource** (vital id == `+0x1C`, the resource type); `0x96E620(vitalId)` maps the id (and follows
`+0x10`, a parent entity whose vitals are shared). Each entry is `{f32 current, f32 max}` (`0x9700C0` current,
`0x970100` max). Vital ids seen in scripts: 2 Health, 1 "Energy", 5 "Mana" (= Will, resource 5), 4 (`DeathFuryCarryOver`:
a fury/rage resource), 6 (`RevValue`), 7.

**0x42 Vitals** (`0x846FC0`, handler `0xAB2880` -> `0xAB1BD0`):
`u8 0 | cint n | n x {Vit cur, Vit max} | cint n | n x {Vit, Vit} | cint m | m x VOT | u8 bool`.
`Vit` (`0x96D3F0`) = u16; bit 15 clear: a 15-bit signed integer; bit 15 set: a second u16 follows (31-bit form).
**ics masks with 0x7FFF**, so values >= 16384 are read as negative: use the long form above 16383.
`VOT` (`0x975E70`, 0x1C bytes): `u8 vital | u8 id | u8 bool | cint k | k x {u8, Vit}`: the active vital-over-time
effects; the client sums the k amounts per tick (`0xAB1BD0`) to predict regen / DoT locally and to make the
`GM_Vitals.RecvNotice_DOTUpdate / VOTUpdate` notices. The second list: ics found the HUD reading the first one
(VITALS_FIRST_LIST); the two lists are added for display (P: base vs temp/shield).
The client's floaty numbers for damage and heals come from these vital changes (`User.ShowFloatyDamage / Heal /
Ally` options, `0xA6B2D0`); there is no separate damage-number message (C for the absence among 0x40-0x21xx).

**Server per hit (P):** apply shields first (temp vitals), then health; send 0x42 to every client that sees the
entity (only entities with a vitals component: variants / champions; else the client crashes, C from tests).

### B.2 Floaties and status texts (C formats, P use)

| msg | target | body | client |
|---|---|---|---|
| `0x44` | floaty component `[ent+0x90]` | `u8 0 \| Handle \| u32 \| u32` | `0xAAF7C0` -> `0xAADCD0`: add a status floaty |
| `0x43` | `[ent+0x90]` | `u8 0 \| Handle` | remove it |
| `0x201D` | `[ent+0x90]` | `u8 0 \| list {u32, Handle}` | replace the list |
| `0x208D` / `0x20BD` | skill HUD | `u8` / `u8 0 \| u64 \| u32` | `GM_Vitals.RecvNotice_DisplayFloatyStatus` (`0x8C2790`: entity `IID_0x...`, status number to Flash) |
| `0x2172` / `0x2173` | UI / encounter | training floaty text | tutorial only |

Currency floaties: `GM_Upgrade.RecvNotice_DisplayFloatyCurrencyChanged / Denied / ShowFloatyCurrencyOverEntity`.

### C. Node specs

#### 0x10000008 AddAttributeModifier (vt `0x15FE30C`, unpack `0x9CB460`, client execute `0x992A70`) - C layout
Sig `B O O {r4}`; ops: **op0 source IID** (+0xC; unset = script owner), **op1 target entity** (+0x24); list (+0x3C,
count +0x44, element 0x54 bytes, `0x9896A0`): `r4 attr | O value | r4 op | O out handle | O viewer/team | r4 (0)`.
So operands per element come in threes: (value, handle, viewer). Values: `[count, (attr, op, 0) x count]`.
Client execute (runs in client-side effect instances): resolves both, builds the effect context `0x991F60`
(owner, owning skill/status from properties `0x100004E2` / `0x100004E1` / `0x1000063B` / `0x1000069B`), then per
element: component `+0x5C(&source, &attr)` (accept test), `+0x4C(outHandle, &source, &targetIID, &value, op, ctx,
&viewerIID, teamIndex, r4)` and writes the handle to the handle variable. The viewer operand: an IID (type 8) =
modifier visible only when read "as seen by" that entity; an int (type 1) = team index (per-team table). C for the
calls, P for the names.
**Server:** for each element evaluate value, create a modifier {source, new handle, op, Value of the attribute's
kind}, store it on the target, store the handle in the variable, recompute the attribute (A.2), and send `0x20F0`
(team = -1, or the team index when the viewer operand is an int). Examples: Stun `0x34000130` (Stunned, op 6, true),
`0x340000C6` lifesteal (op 9), `0x340000EE` 3 at once (`CanUseObjects 0x10000643` op 6, Power Armor op 5, Attack
Armor op 5). Most used attributes: MS `0x100005E4` (45), Exposed `0x100006F3` (22), AS `0x100006FE` (14), AD (13),
Targetable `0x10000029` (13), Power Damage (12), Power Armor (11), `0x10000B00` (10), `0x100007BF` (9).

#### 0x10000033 RemoveAttributeModifier (vt `0x15FBC64`, unpack `0x9CB9C0`, execute `0x993B10`) - C
Same sig; elements (0x20 bytes, `0x9C6620`): `r4 attr | O handle`. ops: source, target, then one handle per
element; values `[count, attr x count]`. Client: for each handle != null calls component `+0x50(&source,
&targetIID, &attr, handle)` and clears the variable. **Server:** remove the modifier with that handle from the
target, recompute, send `0x20E8 (attr, handle)`, set the variable to 0. Must also happen implicitly when a status
ends (the scripts do it in their exit chains: 137 of 217 uses are in exit slots).

#### 0x100000CE GetVital (vt `0x15FCD3C`, unpack `0x9864F0`, execute `0x994BD0`) - C
Sig `B O O r4 r1 r1 O`: op0 entity (+0xC), op1 out variable (+0x24), r4 vital id (+0x3C), r1 **temp** (+0x40),
r1 **max** (+0x41), op2 temp-vital handle (+0x44). temp=0: current (max=0) or max (max=1) of the vital; temp=1:
the shield amount - of the given handle (component `+0x4C(&handle)` / `+0x54(&handle)` for max) or the total
(`+0x50(vital)` / `+0x58()`). **Server:** same, from its own vitals. Examples: `0x340002D7` current and max health,
`0x340000F1` `TempHealthRemaining` of `TempVitalHandle`, `0x34000265` vital 6.

#### 0x1000001A VitalThreshold (predicate; vt `0x15FCDCC`, unpack `0x986700`, evaluate `0x994EC0`) - C
Sig `r4 O O r1 r1 r4`: r4 vital id (+8), op0 threshold (+0xC), op1 entity (+0x24, unset = owner), r1 **percent**
(+0x40: threshold x max), r1 **negate** (+0x41: threshold x -1, used for costs), r4 **compare** (+0x3C):
1/other `cur >= t`, 2 `cur != t`, 3 `cur == t`, 4 `cur < t`, 5 `cur <= t`, 6 `cur > t`. When negate and compare 1
fail (not enough), the client shows the skill error `0x10000016` (`0x10000009` for health) through `0xAB4CA0` ->
`0xA2A090`. Data: `[4 0 1 1]` VerifyVitalTest (cost check), `[2 1 0 1]` TriggerPercentage (health %).
**Server:** evaluate on its vitals; on a failed cost check send the skill error (0x2092 / 0x20DC execute-skill error).

#### 0x10000093 AddTempVital - shield (vt `0x15FDE30`, unpack `0x98DFF0`, execute `0x9B66A0`) - C calls, P names
Sig `{B r4 O O r1 O} O O r4` (the `{B r4 O O r1 O}` prefix is shared with 0x10000040 and 0x10000149: r4 vital id
+0xC, op amount +0x10, op source +0x28, r1 percent +0x40, op target +0x44). Then op +0x5C (u32 read as input), op
+0x74 out handle, r4 +0x8C. Data: `($TempHealth, SELF, -, $TempVitalHandle, -) [2 0 0]` (vital 2, absolute).
Client: amount `0x9945D0` (absolute or percent of max), vitals component `+0x68(sourceEnt, handle, vital, amount,
r4, input, 1)`, handle written back. **Server:** add a shield entry {handle, vital, amount, source}; damage consumes
shields before the vital; report it in the 0x42 second list (P); `GetVital` temp=1 reads it.

#### 0x10000092 RemoveTempVital (vt `0x15FDF7C`, unpack `0x9839E0`, execute `0x995FE0`) - C
`B O O`: op0 entity, op1 handle variable. Client: component `+0x6C(handle)`, variable cleared. Server: drop the
shield, resend vitals.

#### 0x10000040 StartVitalOverTime (vt `0x15FDE90`, unpack `0x98E0A0`, server-only) - C layout, P meaning
Sig `{B r4 O O r1 O} O O r1 r1 r1 r4 O O`; ops: amount (per second), target (SELF), -, **out handle**, -, -, -.
Values `[vital, percent, r1 a, r1 b, r1 c, r4 kind]`: `DamageOverTime [2 0 1 1 0 2]`, health regen `[2 0 0 0 0 0]`,
`VitalPercentChangePerSec [2|1|5, 1, 0 0 0 0]`. P: a/b = "is damage / show floaty", kind = damage type (0 none,
1 attack, 2 power, 3 true) so DoTs go through mitigation. **Server:** register an over-time effect {handle, vital,
rate (absolute or % of max per s), damage type, source}; tick it (the client predicts with the 0x42 VOT list, so
list it there); negative = damage (shields, death), positive = heal.

#### 0x10000009 StopVitalOverTime (vt `0x15FD240`, execute `0x9960B0`) - C
`B O O`: entity, handle. Client: component `+0x64(handle)`. Server: remove the over-time effect and its VOT entry.

#### 0x10000149 AddDamageRedirect / 0x1000014A RemoveDamageRedirect (server-only) - P
`{B r4 O O r1 O} O O r4 O`: `($RedirectPercentage, -, -, $RedirectHandle, -, -) [2 1 5]` (`0x340003C6`) and
`($DamageReflection, ..., $LinkedEntity) [2 1 2]` (`0x340006C5`): a fraction (percent flag 1) of the health damage
of type mask/kind (5 / 2) taken by the target is redirected to (or reflected on) the linked entity; out handle.
Remove: `B O O` (entity, handle). Server: hook in the damage pipeline.

#### 0x1000001D ApplyDamage (vt `0x15FC8FC`, unpack `0x9AAFD0`, server-only) - C layout
Sig `B O O O r1 r1 r1 r1 r4 r4 O O O O O r1`. ops: **0 amount, 1 target, 2 crit roll, 3 skill slot, 4 source
(unset = owner / the missile's owner), 5 out DamageSuccess, 6 SourceEntityDID, 7 -**. Values `[a, b, c, d,
damage type, DID, e]`. Patterns (348 nodes): skills/basics `[0 1 1 0 t 0 1]`; areas, missiles and collision damage
`[1 1 1 0 ...]` (`AoEDamage`, `BlastDamage`, `CollisionModifiedDamage`); bonus / proc damage `[x 0 0 0 ...]`
(`BonusDamage`, `FMABonusDamage`, `PowerDamageBonus`). P: a = area hit, b / c = triggers on-hit effects and
lifesteal (off for procs, so they do not recurse), d = 1 with the basic-attack / ultimate slot given, e = (almost
always 1) show/allow kill.
**Gaps in `ics/script_runtime.py` `_damage`:** no damage type / mitigation, no crit (the roll is ignored and
`_roll_critical` always writes 0), no lifesteal, no shields, no source from op4, no `SourceEntityDID`, no on-hit /
damage events to the target's statuses (`IncomingDamageType`, `TriggeringDamageType` variables), no death handling
beyond health 0, `DamageSuccess` true only when amount > 0.

#### 0x1000010B RollCritical (vt `0x15FBD54`, unpack `0x985CF0`, server-only) - C layout
`B O O O`: out roll, target, -. Server: `roll = rand() < GetAttribute(caster, 0x10000B46)`; write a bool.

#### 0x1000004B GetLevel (vt `0x15FB6C4`, execute `0x9932A0`) - C
`B O O`: op0 out variable, op1 entity (unset = owner). Reads property `0x10000167` (Level). 14 uses
(`AgentLevel`, `CharacterLevel`). Server: same.

#### 0x10000162 SetDefeatType / death guard (server-only) - P
`B O O r1 r4`: op0 out handle, op1 entity; values `[enable, type]`: `[1 0]` / `[0 0]` (`DefeatTypeHandle`,
0x3400041C, 0x340004DE), `[x 5]` (0x340004A4), `[0 0x64]` with `HandleInvincible` (0x34000598). P: pushes / pops a
defeat override on the entity (type 0 = cannot be defeated while held, 5 = a special defeat, 100 = invincible);
the server's death check must honour the stack.

#### 0x100000FA ShowFloatyStatus (server-only, unpack `0x9AFE30`) - P
`B O r4 {StringInfo} r4 r4 r1 r4 r4 r4 r4 ...`: op0 entity, a StringInfo (token / table `0x2B0001AB`), then a kind
(v14: 0, 5, 0xD, 0xE) and flags. Server: send the status floaty (`0x44` to the entity's floaty component, or
`0x20BD (u64 entity, u32 kind)`).

#### 0x10000118 ShowFloatingNumber (server-only, unpack `0x987530`) - P
`B O r1 r4 r4 r4`: op0 number (`TotalHealAmount`, `TotalMaxHealth`, `MaxHPIncreased`, `PowerDamageBonus`), values
`[r1, r4, r4 (1 = +max-health style), r4 -2]`. Server: a number floaty over the owner (no dedicated message found:
P a status floaty `0x44` with the number, or nothing).

#### Expressions
- `0x10000002` GetAttribute: A.1 (C).
- `0x10000003` ScaleByLevel: A.4 (C).

### D. Open

- The attribute rules record (stacking factors, soft caps, panel list) is not located in the packs.
- Mitigation, crit damage and lifesteal formulas are server-only (no client code): the A.5 forms are assumptions.
- The attribute component's own class / vtable (`+0x4C`, `+0x50`, `+0x54`, `+0x5C`, `+0x60`) was not identified
  (reached only through `[ent+0x84]`); the same for the vitals component methods `+0x4C..+0x6C`.
- Exact meaning of ApplyDamage's flags a..e and of the second 0x42 list.

## 3. Status effects, crowd control, death / respawn, Stolen Powers and items

Sources: decompilation in `re-work/decomp` (VAs, base 0x400000), the exe vtables read directly, the 826 decoded trees
(`data/script_trees`, dumped with `ics.script_model.describe`), the status / icon records read through
`ics.gamedata.Data.record`, and the earlier notes `client-status-effects.md`, `script-nodes-names.md`,
`shop-items-inventory.md`, `progression-meta.md`, `protocol-server-to-client.md`, `ui-complete.md`.
Confidence: **C** = read in code or exact data; **P** = probable (inferred from data / names / neighbours).
Operand notation as in `script-nodes-names.md`: `O` operand (value | source | slot), `rN` raw field, `-` unset.

### S3.0 Two facts that shape every node below

1. **An unset entity operand means the script's owner** (C). The client operand reader `0x992280(ctx, operand, out
   u64)`: when the operand has no source/slot it returns the context owner (`0x44c5c0`); `SELF` is the same thing
   written explicitly. So `node(-, ...)` acts on the entity the script runs on (the status carrier for a status
   script, the caster for a skill).
2. **The client runs status scripts itself** (C). The effect component at `entity+0x8C` (getter `0xaa1a60`) is the
   **`gmHFSMComponent`** (literal at `0x977b30`). Every frame (`0x977b30`, guarded by the global game time
   `0x1b77a90`) it re-sorts its instance list (`0x976400`, when dirty bit 0 of `+0x30`), ticks each instance
   (`0x449150`) and removes those whose `+0x1E8` field is 1 (`0x977aa0`: release, swap-remove, dirty). The instances
   arrive with `0x200F/0x2062` (one) or `0x200C/0x2043` (list) and are removed with `0x202B/0x2037` (layouts in
   `client-status-effects.md` §3). While an instance is on the client, every node of its script with a client
   execute (vtable slot 10) runs there; nodes whose slot 10 is the empty `0xab4d80` (`ret`) or `0x4fb4c0`
   (`return 0`) do nothing client-side. **This is why ~half of the status nodes are "server-only": the client mirror
   only performs the visual / local-prediction half** (C for the mechanism; P that the original server always sent
   the instance, but nothing else would run those client nodes). The u8 written to `+0x1E8` by the 0x200F reader is
   therefore "already finished" (send 0) (C for the removal test, P for the name).

Consequence for the server (P, recommended): keep the authoritative status instance in `ics` (as
`apply_status` does) **and** mirror it to the carrier's clients with `0x200F` (script DID = the status's
`0x10000242`, a fresh GUID that is also the script's "effect handle", empty variable store) on apply and `0x202B`
(same GUID) on removal. Everything the client must *see* but that runs only on the server (icons, attribute values,
life state, movement locks) is sent with the dedicated messages listed per node.

### S3.1 Status effect records (`0x48......`, DB type 0x1E "status effect", 1134 records)

Survey of the 218 status-like `0x48` records referenced by the decoded scripts (C, data):

| Property | Kind | Count | Meaning |
|---|---|---|---|
| `0x10000242` | DID | 169 | the status's server script (`0x34......`); `ics.gamedata.status_script` (C) |
| `0x10000063` | int | | max stacks: 1 = refresh, 5 / 10 / 99 = independent instances up to N (C data; runtime `STACKS_RESOLVER`) |
| `0x10000334` | u32 | 218 | **status flag bits** (C data, meanings P): `0x8` (89 records, plain buffs/marks), `0x4000` (75; stun / knock / slows: "negative / debuff"), `0x100` (14: stun `0x48000293`, knockdown `0x48000295`, knockup `0x48000296`: **hard CC**), `0x10`, `0x20`, `0x200`, `0x400`, `0x2000`, `0x8000`, `0x80000`; `0x1/0x2/0x4/0x800/0x1000` rare |
| `0x1000072D` | int | 192 | small enum 8 (most), 12 (CC / hard debuffs), 4, 2 (P: display category / dispel class) |
| `0x100008A6` | DID | 108 | link to the status's **icon record** (e.g. `0x480008A8` -> `0x480008AB`) (C data) |
| `0x100008A2/A3/A4`, `0x1000089E` | | 72-90 | icon / tooltip options (P) |
| `0x1000096E` | int | 10 | knock type 4 (knockdown) / 0xB (knockup) (C data) |
| `0x100009C8`, `0x10000AF2` | bool | | ? |

**Icon records** are also `0x48......` (DB type `0x29` when read by the icon handler, `0x5dfba0(did, 0x29)` in
`0xab2d30`, C): they carry the display strings `0x100004F9` / `0x10000509` / `0x10000520` (StringInfo), `0x100004F7`,
`0x100004F6`, `0x1000046F` and `0x100007BC` (bool; when true the add handler also calls `0xa9fc60` = show it on the
agent's portrait / nameplate, P). The values `AddStatusIcon` / `UpdateStatusIconStats` take as their r4 are these icon
records (`0x48000944`, `0x48000D20`, ...), not the status records (C data).

Status flags are what the "by flags" variants of `HasStatus` / `RemoveStatus` test (their second r4: 4, 1024, 8192,
...; P: `(record 0x10000334 & mask) != 0`).

### S3.2 How CC reaches the client (summary + additions)

Base facts are in `client-status-effects.md` §1 (C): CC is a set of **bool attributes** read through the attribute
component `entity+0x84` (`0x974940`): Stunned `0x100003F3`, Rooted `0x100007FE`, Crippled `0x10000B39`, Silenced
`0x100005A3`, cannot-act `0x10000B2D`, LifeState `0x100000FA`; slow = f32 `0x100006FE` / move speed `0x100005E4`.
Status scripts set them with `AddAttributeModifier 0x10000008` (client execute `0x992a70`, so the client mirror
applies the modifier locally too) and clear them with `0x10000033` (`0x993b10`). Most used attributes in the 276
`AddAttributeModifier` nodes (C, data; attribute, op): `0x100005E4` (move speed, op 10 / 9), `0x100006F3` (op 6),
`0x100006FE` (op 10), `0x10000B75` / `0x10000B76` (power / attack damage bonus, op 9), `0x10000B00`, `0x10000249`
and `0x10000029` (targetable flags, op 6), `0x10000426` (health), `0x100003F3` (stunned, op 6), `0x100005A3`
(silenced), `0x10000A23` (can shop), `0x10000459` (at base / in shop area, see S3.6). (Attribute ops and formulas: section 2.)

**New (C): the client's input lock counter.** The local player controller (`0xa1a410()` = `[0xa12d50()+0x90]`) has a
lock counter at `+0x70`; `0x85ebd0(bool)` increments it (true) or decrements it (false, not below 0).
`0x863860(champion, cmd)` (the order filter) returns "buffer this order" when, among others, the champion is not
Stunned and `[ctrl+0x70] != 0`, or when the champion's current action code (`[[obj+0x54]+0x2C]`, `0x550120`) is one
of `0x40, 0x41, 0x47, 0x48, 0x4A, 0x4B, 0x4D, 0x4E, 0x4F`. A listener `0xa0aad0` also bumps the same counter while
that code is in `{0x41, 0x47, 0x48, 0x4A, 0x4B, 0x4D, 0x4F}`. Two writers of the counter matter here:
- node `0x100000AD` (client execute `0xab4890`, S3.7) = **lock / unlock the local player's orders**;
- the action code: **`DisableActions 0x1000005B` uses exactly these family values** - 77 = `0x4D` (stun, knockdown,
  knockup), 65 = `0x41` (self-disables), 82 = `0x52` (sync movement, not in the lock set). P: the original server's
  DisableActions put the entity into that action code, replicated into `obj+0x54`, and the client then refused /
  buffered orders. The `+0x54` object (action state) and its network source were not traced; the reliable channel
  today is still `0x10000B2D` + `0x100003F3` as in the knockdown recipe.

### S3.3 Status icons (HUD element 31 `StatusIconDisplay`, Flash `GM_StatusIcon`)

All icon nodes are server-only (slot 10 = `0xab4d80`, C); the server must send the StatusIcon group events to the
**object whose icon row changes** (the agent; the local player's HUD shows its controlled agent's row, the target
frame shows the target's) (C for handlers, P for the field mapping, which follows the Flash argument lists in
`ui-complete.md` §GM_StatusIcon):

| Event | Reader / handler | Layout | Flash call |
|---|---|---|---|
| `0x20C8` add | ser `0x840390` / h `0xab2d30` | `u8 0 \| u64 agent \| u32 didIcon \| Handle{u32 nGameHandleID, u64 iidStatusIconGameHandle} \| u32 \| u32 \| StringInfo \| u64 iidSource \| u64 \| u32 \| u64 \| Tooltip{StringInfo u32 u32 {u32 {u8 u8 u8 u32}}} \| u32` | `AddStatusIcon(iid, didIcon, siDescription, siTitle, siHeading, nPriority, nGameHandleID, iidStatusIconGameHandle, nCount, ttEndTime, fDuration, didTooltipIcon, siPlayerName, siAgentName)` |
| `0x20A2` add (list form) | ser `0x847d30` / h `0xab37b0` | lists of the same fields | same / `BatchAddStatusIcon` |
| `0x20A8` update | ser `0x840580` / h `0xab3250` | `u8 0 \| u64 agent \| Handle \| u32 \| u32 \| StringInfo \| u64 \| u64 \| u32 \| u64 \| Tooltip \| u32` | `UpdateStatusIcon(iid, nGameHandleID, iidStatusIconGameHandle, siDescription, nCount, ttEndTime, fDuration, didTooltipIcon, siPlayerName, siAgentName)` |
| `0x20E9` remove | ser `0x8402e0` / h `0xab38d0` | `u8 0 \| u64 agent \| Handle \| u8 (0/1 only, else stream error)` | `RemoveStatusIcon(iid, nGameHandleID, iidStatusIconGameHandle)` (+ remove stack-count string) |
| `0x20D0` tooltip | ser `0x849300` / h `0xab1500` | `u8 0 \| u64 \| Handle \| u32 \| {u8 cint {u32 u32}} \| {u8 cint {u32 u32}}` | `UpdateStatusIconTooltip` |
| `0x2127` tooltip refresh | ser `0x83f4d0` / h `0xab15d0` | `u8 0 \| u64 \| Handle` | `UpdateStatusIconTooltip` |

In `0xab2d30` (C): the icon record is resolved as DB type 0x29 (no record -> message dropped); the u64 at message
`+0x70` (`iidSource`) is looked up (`0x588e90`) to fill the player / agent names; the stack string goes through
`0x5a7bc0`; if the agent is the local champion and the source u64 at `+0x88` is set, `0x47fa70` may suppress the
popup; the record's `0x100007BC` bool triggers `0xa9fc60`. The `Handle` is the identity used by update / remove: the
server chooses `nGameHandleID` (unique u32 per agent) and `iidStatusIconGameHandle` (P: the carrier's IID), and
stores it in the script's handle variable (`SIDHandle`, `StatusIconHandle`, `TimerSIDHandle`).

### S3.4 Death and respawn

Client side (C):
- **LifeState `0x100000FA`** (`LifeStateList`: 1 DeadAndFaded, 2 Dead, 3 Incapacitated, 4 Alive, 5 Respawning) is a
  plain property; set it with the single-property events (`0x6` / `0x86`). Listeners: `0x968f30` (2 Dead -> agent
  added to the global dead list `0x186d91c` (entries 0x18 bytes) by `0xa3fe60`, and if it is the local champion the
  death view `0xa30e70`; 4 Alive -> removed by `0xa336b0`, camera re-centred (`0x8870f0` with 1.0)); `0x96c780`
  (shop button: available when dead, or when `0x10000459` / `0x10000A23` say so); `0x85ec10` (clear the queued
  cast); `0xa8dfb0`, `0xab00a0`, `0xa1dc10` (HUD "can act"); `0x9cfaf0` refuses every order unless LifeState == 4.
- **Defeat timers** (network notices inside event 0x2, `protocol-server-to-client.md`): `0x10000090`
  DefeatStatusUpdated `(u32 state, u64 iid)` -> Flash `(iidPlayer, state, tsTimeOfNextState)` (3 Incapacitated panel,
  2 Dead timer panel, 4 Alive = respawned); `0x100000BC` ...ForEntity `(u64 iidPlayer, u32 eKillerPerceivedType,
  u32 state, f64 timeOfNextState)` for scoreboard / portraits; `0x100000BA` pause an entity's timer `(u64, u32)`.
- **Animation**: the defeat scriptlets of the champion's table (`client-scriptlets-graphs.md` §1.5):
  `_Defeat_OnIncapacitated 0x100001FB` (graph event `0x100000AD` CbtState_Death_Induce), `_Defeat_OnDead 0x100001FA`,
  `_Defeat_StartupIncapacitated 0x100001F9` (`0x1000010B` CbtState_Dead), `_Defeat_OnRevive 0x100001FD`
  (`0x1000009D` CbtState_GetUp, `0x100000AA`); type-0x22 containers in `CbtState_KnockUp`, `CbtState_GetUp`,
  `_Combat_GoToLocomotion` watch LifeState / `0x10000B2D` / Stunned themselves (P that they fire on a pure property
  change; C that they watch those properties).
- **Kill feed**: notice `0x100002EB` ShowAnnouncement `(StringInfo, u32 billboard type, u32 source icon, u32 target
  icon, i32 source team, i32 target team, u8)` (HUD 37 `KillDisplay`); `0x100000CA` / `0x100000CD` `(u64, u64)` P:
  killer / victim pair; `0x1000021C` / `0x100002B2` big list layouts (P).
- **Rewards**: gold = f32 property `0x1000035E` (HUD watcher `0xa93c50`), XP = `0x10000142`, level `0x10000167`,
  skill points `0x100001AF` (C, `progression-meta.md`); the floaties come from property deltas client-side (P).
  The XP curve, kill gold / XP and respawn durations are **not in the client** (server rule).

Server sequence on a kill (P, assembled from the above; the scripts' side is `VitalThreshold` / `IsAlive` and the
status `PercentRemoveOnDeath`-style stats):
1. health 0 -> stop the victim (cancel path, clear orders), remove statuses that do not survive death (their scripts
   receive `0x10000003` with `ExplicitlyRemoved`), raise the death events the scripts listen to;
2. LifeState 3 (Incapacitated, if the mode uses it) then 2 (Dead): property `0x100000FA`; scriptlet
   `0x100001FB` / `0x100001FA` (0x8D or `0x2050`) on the victim; `0x10000090` to the victim's player
   `(2, iid)` with the respawn time; `0x100000BC` to everyone;
3. rewards: killer `0x1000035E` / `0x10000142` (+ assists), kill feed `0x100002EB`, score (match data);
4. at respawn time: teleport to the team's spawn point (map data, `maps-complete.md`), restore vitals, LifeState 5
   then 4, `0x10000090 (4, iid)`, re-apply permanent statuses (item passives, champion passive), scriptlet
   `0x100001FD` if the mode revives in place.

### S3.5 Stolen Powers and items as skills

- **Slots** (C, `reverse-engineering.md`): 16 slot properties, table `0x15EDA28` (read by `0x85d1c0` and by node
  `0x100000F5`): 0 basic `0x100008E3`, 1-4 Q/W/E/R, 5 passive, 6 recall `0x100008E4`, **7 D `0x100008F0`, 8 F
  `0x100008F1`** (Stolen Powers), 9 bonus `0x100008F2`, **10-15 items `0x100008E5/E7/E9/EB/ED/EE`**. Each is a
  property collection (kind 0x0B) holding the whole skill definition: script `0x10000328` (or `0x10000850`),
  targeting `0x1000003D`, stats `0x100004B4`, icon `0x10000302`, ...
- **Stolen Powers**: catalog `0x480003CD` (12 groups); the base power's block `0x1000003F` with the champion
  version's block merged on top (`ics.gamedata._skill_from_block`). The script is a normal skill script; D/F orders
  arrive as `0x20EE` cmd 2/9 with ability 7 / 8. 65 power records, 17 targeting 1 (ground), 30 targeting 14
  (entity), 14 type 5, 4 type 7 (C data, `stolen_powers.tsv`).
- **Items**: an artifact's active ability `0x100008E1` -> record -> skill block `0x100008E5` (script `0x10000328`,
  stats `0x100004B4`), installed in the first free item slot; passives `0x100004EA` -> `0x1000037D` = **status
  records** with scripts, applied for as long as the item is owned (`shop-items-inventory.md` §7-8). HUD order of
  item slots `0x212C`; inventory `0x20E2`.
- **Charges** (C data, `0x34000384` / `0x340004BC` / `0x340004BD`, the consumable actives): the script keeps
  `ChargeCount`, shows it as the stack count of icon `0x48000944` (`AddStatusIcon` / `UpdateStatusIcon` with
  `$ChargeCount`), spends one per use, refills to `MaxCharges` (stat 32) when the attribute `0x10000459` turns true
  (`OnAttributeChanged [0x100000A2, 0x10000459]` + `HasFlagAttribute(SELF)[0x10000459]`: at base), sets the skill
  error `0x10000045` (`SetSkillErrorState 0x100000FB`) while it is 0, and persists the count across script restarts
  with `GetCharges 0x1000016B` (graph start) / `SetCharges 0x10000169` (on event `0x1000014A`, P: "script about to
  be unloaded / item moved").
- **Cooldowns, CanActivate, error states** for these slots: section 1; the per-slot cooldown event is
  `0x20F8`.

### S3.6 Attribute `0x10000459` (C data + C code)

Bool, kind 0x16. Read by the shop availability listener `0x96c780` together with LifeState and `0x10000A23`; item
scripts refill charges when it becomes true. P: "inside the team's base / fountain area" (set by the base aura).

---

### S3.7 Node specifications

Columns: id, vt, Unpack, client execute (slot 10). "server-only" = slot 10 is `0xab4d80` / `0x4fb4c0`.

#### 0x10000027 ApplySkill / ApplyStatus (vt `0x15FDFDC`, unpack `0x9c0b30`, server-only) - runtime: partial

Layout `{B r4 status | O target | O duration | O rank | O value | O effectDID | O sourceDID | r1} O handle | O slot |
O success | O source | r1 r1`. Values seen `[status, 1, 0, 1]` (the three r1, meanings ?). Examples:
`ApplySkill(SELF, $EffectDuration, -, $CriticalChanceRoll, -, -, -, -, -, $TargetIID)[0x48000AB0]` (Batman basic
attack shot tracker), `ApplySkill(SELF, $StackDuration, -, $StackValue_Buff, -, $SourceEntityDID, ...)[0x48000D1F]`,
`ApplySkill(-, -, $PermaRank, -, -, -, $Effect1Handle, ...)[0x48001417]` (permanent, rank only, handle kept),
`ApplySkill(-, -, -, $ShieldAmount, -, -, $ShieldHandle, ...)[0x480014FA]`.
Server (C data / P semantics): start the status record's script on target (default owner) with the parameters as
event `0x10000006` parameters (EffectDuration, EffectRank / StackCount, value, SourceEntityDID, EffectSource);
duration 0 / unset = permanent until removed; stacking by `0x10000063`; **write the new instance's handle (the
effect GUID, the same one sent in `0x200F`) to op `handle`, and 1 / 0 to op `success`** (0 when the target is dead
or immune). Mirror with `0x200F`.
**Runtime gaps:** `handle` and `success` are not written (so `HasStatus` / `RemoveStatus` / `SetStatusDuration` by
handle cannot work and `IfThenElse($Success)` takes the else branch); `slot` (op 7, the skill slot that applied it)
is not stored; no client mirror (`0x200F`/`0x202B`); refresh of a non-stacking status keeps the old timer and adds a
second one (old timer is invalidated by `expires` - fine) but does not reset `EffectStartTime`-style variables (the
script does that on `0x10000006`).

#### 0x100000A4 HasStatus (vt `0x15FCF78`, unpack `0x9af2c0`, **client execute `0x995180`**) - runtime: by DID only

Unpack (C): `O target (+0x08) | O statusVar (+0x20) | r4 status (+0x38) | O handle (+0x3C) | r4 flags (+0x54)`.
Client logic (C): resolve target (unset = owner); component `[target+0x90]` (getter `0xaa1560`, only caller);
`status = value(op statusVar)` if set else r4 `+0x38`; if status != null DID -> `comp->vt[0x50](status)`; else if
flags != 0 -> `comp->vt[0x4C](flags)`; else read op handle as a 16-byte handle (`0x988b70` -> `0x853c40`) ->
`comp->vt[0x54](handle)`. So three tests: **by status DID, by status-flag mask (P: record `0x10000334`), by effect
handle (GUID)**. Data: 55 of 57 uses are by DID; one by handle (`$HasteHandle`).
Server: same three tests on the target's running statuses. **Gap:** handle and mask variants.

#### 0x10000018 RemoveStatus (vt `0x15FD668`, unpack `0x9b2600`, server-only) - runtime: missing

Layout `B | O target | O handle | O - | r4 flags | r4 status | r1 | O slot`. Uses: `RemoveStatus(-, -, -, -)[0 0 0]`
48x = **the running status removes itself** (inside status scripts, e.g. after `VitalExpiredHandle`, `0x100000ED`);
`(SELF/$TargetIID)[4 0 0]` 7x and `(-)[1024 0 0]` 3x = remove every status whose flags match the mask (P: cleanse /
stealth break; `0x34000304` stealth, `0x340000C6`, `0x34000480`); `(SELF, $SlowHandle)` / `($EOStartIID,
$EOStartMarkHandle)` = by handle; `(SELF)[0 0x48000880 0]` = by DID.
Server: pick instances by handle, else DID, else flag mask, else "this instance"; remove each (script gets
`0x10000003` with `ExplicitlyRemoved = 1`, exit chain runs), send `0x202B`. The r1 (0/1) is P "all stacks / one".

#### 0x100000CA SetStatusDuration (vt `0x15FD728`, unpack `0x9b2d00`, server-only) - missing

Layout `B | O target | O handle | O - | r4 0 | r4 status | O duration | r1 add`. Uses: `(SELF, -, -, $StackDuration)
[0 0x48000D1F 0]` (reset a stacking buff's timer on a new stack), `(SELF, -, -, $OnHitDurationExtend)[0 0x4800036E 1]`,
`(-, -, -, $AdjustedDurationDelta)[0 0 1]` (this instance), `($EOStartIID, $EOStartMarkHandle, -, $PortalDuration)`.
Server (P, names): r1 = 0 -> remaining duration := value; 1 -> remaining += value; target selection as RemoveStatus
(handle, else DID, else the running instance). Update the expiry timer and any icon showing it (`0x20A8` with the new
`ttEndTime`).

#### 0x100000D9 AddStacks (vt `0x15FDFAC`, unpack `0x9c0620`, server-only) - missing

Layout `{B r4 status | O target | O duration | O - | O value | O - | O sourceDID | r1} O count`. Uses:
`AddStacks(SELF, $StackDuration, -, $StackValue_Buff, -, $SourceEntityDID, $Stacks_FirstHit)[0x480008A8 1]`,
`(-, ctx, ..., $MaxStackCount)[0x480012F9 1]`. Server (P): ApplySkill repeated `count` times (bounded by
`0x10000063`), i.e. jump straight to N stacks.

#### 0x100000FE GetStackCount (vt `0x15FCC1C`, unpack `0x982850`, server-only) - missing

Layout `B | O target | O out | r4 status`. Writes the number of running instances of `status` on target (stacking
statuses run one instance per stack) (P). Uses: `($TargetIID, $TargetDebuffCount)[0x48000684]`, `(SELF,
$AttackerStackCount)[0x480008A8]`.

#### 0x10000177 LoadStatusStats (vt `0x15FE248`, unpack `0x9ccbe0`, server-only) - missing

Unpack (C): `B (0x45fe70) | O source | {vars} (0x9c6830) | O | r4 | r4`; values `[count, stat ids...]` then two r4
(always 0). Every use is preceded by `SetVariable($SourceEntityDID, #SourceEntityDID)` (the apply parameter), so
(P) it is LoadSkillStats for a status: read stats `ids` from the stats array `0x100004B4` of the record named by the
variable **SourceEntityDID** (the skill / item / Stolen Power record that applied the status, passed by ApplySkill
op 5) at rank **EffectRank** (default 1), into the listed variables. Stat ids are the same table as skills (14 =
duration, 15 = cooldown, 12, 31, 32 = max / increment, 33 = cap ...). Example: `[5 12 7 32 31 14]` ->
AttributePerTickIncrease, MaxStacks_Bonus, TickMax, TickIncrement, TickDuration. Implement by reusing
`world.skill_stat(record, stat, rank)` with the record from SourceEntityDID.

#### 0x1000005B DisableActions (vt `0x15FB2D4`, unpack `0x9837d0`, server-only) - missing

Layout `B | r4 family | O entity | r1 | O out handle | r4 priority`. Values `[77 1 50]` (stun, knockdown, knockup,
Starro self-disable), `[65 1 50]` (self disables), `[82 1 50]` (`$SyncMovementHandle`). Server (P): put the entity
into a blocking action of that family with that priority: stop its current action / path / channel, refuse new
orders (skills and movement) until the handle is released by `StopAction 0x10000081` (every stun exit does
`StopAction(SELF, $ActionHandle)`). Client side: family 0x4D / 0x41 are in the client's order-lock set (S3.2), so
replicating the action code (if found) would lock input; meanwhile send `0x10000B2D` = 1 (+ Stunned) while held.

#### 0x10000081 StopAction (vt `0x15FBD24`, unpack `0x9839e0`, server-only) - missing

Layout `B | O entity | O handle`. Handles from `DisableActions`, `DashToPosition` / `DashToEntity` (`$DashHandle`),
`Knockback` (`$KnockBackHandle`), `AttachEntity` (`$AttachHandle`). Server: end that action (release the lock,
stop the dash / knockback motion, detach); unknown or already-ended handle = no-op. Clears `0x10000B2D` when no lock
is left.

#### 0x100000AD LockInput (was "SuppressInput?") (vt `0x15FBFCC`, unpack `0x983d70`, **client execute `0xab4890`**) - missing

Layout `B | O entity | r1 on`. Client (C): if the operand resolves, `0x85ebd0(on)` on the **local player
controller** (`0xa1a410`): counter `+0x70` ++ / --; non-zero -> move / stop orders are buffered by `0x863860`
(not sent). Note it does not check that the entity is the local champion: any script instance the client runs that
executes this locks the local player's input (P: only the controlled champion's own scripts use it). Uses
`(SELF)[1]` ... `(SELF)[0]` pairs around channels. Server: if the entity is a player's champion, ignore its move
orders while the counter is > 0 (the client mirror does the rest if the status / skill instance is mirrored);
otherwise no-op.

#### 0x100000C8 SetUntargetable (vt `0x15FBF9C`, unpack `0x983d70`, server-only) - missing

Layout `B | O entity | r1 flag`. `(SELF)[1]` ... `[0]` in recall / stealth / phase scripts. Server (P): flag 1 ->
untargetable (target validators and `FindTargets` skip it, missiles pass through); client: set the targetable
attributes `0x10000029` / `0x10000249` to false (same channel as fase3-gf) while set.

#### 0x10000143 IsStealthed / 0x10000144 IsRevealed (vt `0x15FDB1C` / `0x15FDAEC`, server-only predicates `0x4fb4c0`) - missing

`0x10000143(O target)`, `0x10000144(O target, r1 1)`. Only in the stealth script `0x34000304` (SP), next to
`HasFlagAttribute($TargetIID)[0x10000B4A]` (P: the stealth attribute). Server (P): stealthed = has a status with
stealth flags / attribute `0x10000B4A`; revealed = stealthed but currently visible to the querying team (detector,
recent damage). Without a vision model: IsStealthed = attribute test, IsRevealed = false.

#### 0x1000002C OnCombatEventByKind (was "HasStealthFlags?") (vt `0x15FAF44`, unpack `0x982c30`, **client execute `0x9927d0`**) - trigger, missing

Unpack sig `{r4} r4 r4 O O O`. Client (C): the current event (`ctx->vt[0x24]()`) must carry an event object of type
`0x10000002` (two-entity event: `+0x10` IID A, `+0x18` IID B, `+0x20` u32 value) whose event id (`[obj+8]`) equals
the node's id (`+0x08`, data: `0x10000020`); then `kind(A) & mask1 (+0x0C)` and `kind(B) & mask2 (+0x10)` must be
non-zero (`0x9cfbf0` = attribute component `+0xA4` or property `0x1000019D`, the entity kind flags `IsKind` tests);
on success it writes A to op 1 (`+0x14`), B to op 2 (`+0x2C`) and the value to op 3 (`+0x44`) and fires.
Data: `[0x10000020 0x697159 8]` -> `(-, $Defender, -)`, `[0x10000020 0x210100 0x200000]` -> `$TempDefender`.
Server: a trigger on event `0x10000020` (P: "hit / damage dealt", A = attacker, B = defender) filtered by both kind
masks; set the three outputs. The runtime's event parameters must carry the two IIDs and the value.

#### 0x100000A7 AddStatusIcon (vt `0x15FD638`, unpack `0x9b2290`, server-only) - missing

Layout `B | O out handle | O entity | O stacks | O source | r4 icon | O duration | O sourceDID | O source2 | O iconVar
| O useRemainingCooldown | r4 | r1 | O`. Values `[icon 0x48......, 0xFFFFFFFF / 5 / 4 / 1, 0 / 1]`. Examples:
`($SIDHandle, SELF, -, $SourceIID, $Duration, $SourceEntityDID, $SourceIID)[0x480008D6 5 0]`,
`($SIDHandle, -, $ChargeCount)[0x48000944 0xFFFFFFFF 0]` (charges), `($TimerSIDHandle, -, -, -,
$RevTimerDuration)[0x4800083E]`. Server: allocate a handle `{u32 id, u64 carrier IID}`, store it in op 0, send
`0x20C8` to the carrier's observers: `didIcon` = iconVar if set else r4, `nCount` = stacks (0 = none),
`fDuration` = duration and `ttEndTime` = now + duration (0 = no timer), `iidSource` = source (names in the tooltip),
`didTooltipIcon` = P sourceDID's icon. The second r4 (`0xFFFFFFFF`, 5, 4, 1) is P `nPriority` (sort order; -1 =
default). Remember it so `0x100000A8` / `0x100000A6` / `0x1000016A` can address it.

#### 0x100000A8 UpdateStatusIcon (vt `0x15FD878`, unpack `0x9b3830`, server-only) - missing

Layout `B | O handle | O entity | O stacks | O duration | r1 | O source | r4 | r4`; values `[0, 0xFFFFFFFF / 5 / 2,
0]`. Uses: `($SIDHandle, SELF, $StackCount, $EffectDuration, $EffectSource)`, `($SIDHandle, -, $ChargeCount)`.
Server: send `0x20A8` for that handle with the new count / end time (unset operands keep the old values).

#### 0x100000A6 RemoveStatusIcon (vt `0x15FD698`, unpack `0x9b2890`, server-only) - missing

Layout `B | O handle | O entity | r4 0 | r1 0 | r1 1`. 211 uses, always `[0 0 1]`, mostly in exit chains.
Server: send `0x20E9 (agent, handle, u8 1)` (P: the u8 is the last r1) and forget the handle; unknown handle = no-op.

#### 0x1000016A UpdateStatusIconStats (vt `0x15FE27C`, unpack `0x9cdd90`, server-only) - missing

Layout `B | O handle | O entity | O sourceDID | r4 icon | {r4 count, count x (r4 arg index, r4 attribute)}` with one
value operand per pair. Example: `($StatusIconHandle, SELF, -, $AttackSpeed_Change, $MovementSpeed_Change)
[0 2 3 0x100006FE 4 0x100005E4]` = tooltip argument 3 <- AttackSpeed_Change (attribute `0x100006FE`), argument 4 <-
MovementSpeed_Change (`0x100005E4`); `(-, SELF, -, $CurrentBonus, $MaxBonus, $Bonus)[0x480008A6 3 1 0x10000B84 3
0x10000B84 5 0x10000B84]` (no handle: addressed by icon DID). Server (P): send `0x20D0 (agent, handle, u32 icon,
list (index, attribute), list (index, value bits))` - the two `{u32 u32}` lists match the pairs.

#### 0x10000116 RefreshStatusIcon (was "SetStatusIconValue?") (vt `0x15FD8A8`, unpack `0x982850`, server-only) - missing

Layout `B | O handle | O entity | r4 icon`. `($SIDHandle, SELF)[0]` or `(-, SELF)[0x48000D20]`. P: tooltip refresh
of that icon = `0x2127 (agent, handle)` (the only StatusIcon event carrying just a handle).

#### 0x10000102 StopScriptlet (vt `0x15FBF38`, unpack `0x982850`, **client execute `0x993cf0`**) - missing

Layout `B | O entity | O handle | r4 fx`. Client (C): resolve entity and the handle variable (16 bytes) ->
`0x876cb0(entity, handle, fx)`: find the run in the entity's scriptlet list (entries 0x68 bytes, `0x85d480`); if
`fx` is not the null DID and the run accepts it (`vt[0x14]`), run scriptlet **`0x100003EA` (_ExecuteScriptlet)** on
the entity with variable **`0x1000050A` = fx** (an FX record `0x1E......`, e.g. `0x1E0000CF`); then signal / stop the
run (`0x588a80(entity, key, entry+0x50)` -> `0x57c4b0`), swap-remove it; when none is left, release the list
(`0x86c220`, `0x58bba0`, `0x588d60`). Server: send the stop of the scriptlet run that `StartScriptlet 0x10000103`
created (0x8D signal / stop by instance, P) and, if `fx` is set, `0x8D` key `0x100003EA` with variable `0x1000050A =
fx`. 362 uses; most `[0]`.

#### 0x10000012 StopScriptletKey (was "ClearProperty / StopEffect") (vt `0x15FBF6C`, unpack `0x985580`, **client execute `0x993db0`**) - missing

Layout `B | r4 key | O entity`. Client (C): `0x588a80(entity, key, all instances 0x186a7b4, 0)` -> `0x57c4b0(key,
signal 1, ...)`: signals every run of that scriptlet **key** on the entity to end. Values are scriptlet keys
(`0x100000EB`, `0x1000006B` Vfx_Active_State1, `0x10000223` VFX_CBT_Hit_Shared, `0x10000D19`). Server: end every run
of that key on the entity (P: `0x8D` signal by key; the client mirror already does it if the instance is mirrored).

#### 0x1000013A RunFxScriptlet (was "PlayHitScriptlet?") (vt `0x15FE404`, unpack `0x9cbc20`, **client execute `0xab7620`**) - missing

Layout `{B r4 key | O entity | O - | {r4 var ids} | r1 | r1} r4 fx` (the RunScriptlet layout plus a trailing FX DID).
Client (C): if the entity operand is set, push variable `0x1000050A = fx` (`+0x54`) and run the RunScriptlet
execute `0x9ce050` (key on entity with the listed variables). Data: key always `0x100003EA` (_ExecuteScriptlet), fx
`0x1E0000A4`, `0x1E000447`, `0x1E000524/525`, `0x1E0005EB`, extra variables `0x10000050` (VectorToTarget),
`0x100003FF` (LanternIID). Server: `0x8D` on the entity: key `0x100003EA`, variables `{0x1000050A: fx, ...}`.

#### 0x100000F5 GetSkillSlotOfScript (was "SwapSkillScript") (vt `0x15FCCAC`, unpack `0x9ade60`, **client execute `0x994a00`**) - missing

Layout `B | O out slot (+0x1C) | O entity (+0x28) | r4 script (+0x24)`. Client (C): script = r4, or the running
script's own DID when r4 is null (`ctx->vt[0x18]`); `0x85eed0(entity, &script)` walks the 16 slot properties of
`0x15EDA28` and returns the first slot whose skill collection has `0x10000328` (or `0x10000850`) == script, else
`0xFFFFFFFF`; the slot is written to op 0. Data: `($SuperStrengthSkillSlot, SELF)[0x34000164]` (find the slot,
D or F, holding Super Strength), `($SkillSlot, -)[0]` (own slot). Server: the same lookup over the champion's slot
table.

#### 0x10000169 SetCharges / 0x1000016B GetCharges (vt `0x15FB214` / `0x15FB1E4`, unpack `0x983430`, server-only) - missing

Layout `B | O value | r4 key` (key 1 / 2 / 3, one per consumable family). P: a per-champion persistent integer store
keyed by `key`, surviving the item script's restart; Get with no stored value leaves the variable unchanged (the
script then sets `MaxCharges`). See S3.5.

#### 0x10000065 GrantCurrency (vt `0x15FC26C`, unpack `0x984f40`, server-only) - missing

Layout `B | O entity | O amount | r4 type | r4 flags`. Uses `(SELF, $BonusCurrency)[0 128]`, `(-, $CurrencyGrant)[4 8]`
(camera kill), `(-, $BonusCredits)[4 128]`, `($EffectSource, $CreditBonus)[4 128]`. Server (P): add `amount` to the
in-match gold `0x1000035E` of the entity's controlling champion (type 4 = P: also/only its team when the
`UseTeamwideCurrencyGains` option of `0x100000EC` is on); flags 8 / 128 = P reason for the gold floaty. Send the
property update.

---

### S3.8 Runtime checklist for this section (what `ics/script_runtime.py` needs)

1. Status instance identity: a GUID per instance, written to ApplySkill's handle operand, used by HasStatus /
   RemoveStatus / SetStatusDuration / StopAction and sent in `0x200F` / `0x202B`.
2. `RemoveStatus` "this instance" form (48 uses) - many status scripts end themselves only that way.
3. Status flags (`0x10000334`) in the resolver, for the mask forms.
4. `LoadStatusStats` = `LoadSkillStats` on the SourceEntityDID record at EffectRank.
5. Icon nodes as message emitters (`0x20C8` / `0x20A8` / `0x20E9` / `0x20D0` / `0x2127`) with a per-agent handle
   table; in `NullWorld` they can be no-ops that still write the handle.
6. `DisableActions` / `StopAction` as an action-lock table driving order refusal and `0x10000B2D`.
7. Scriptlet stop by handle / by key, `RunFxScriptlet` (key `0x100003EA`, var `0x1000050A`).
8. Trigger `0x1000002C` on event `0x10000020` with attacker / defender kind masks.

### S3.9 Open

- `obj+0x54` (action state, `+0x2C` code) and how the server set it; the exact meaning of the three r1 of ApplySkill
  and of `0x1000072D`.
- The `[entity+0x90]` component that `HasStatus` queries (vt `+0x4C/+0x50/+0x54`): not located (only caller is
  `0x995180`).
- The 0x8D form that stops a run by instance (needed by StopScriptlet).
- Icon message fields after the StringInfo (`u64 | u32 | u64`) - order of `ttEndTime` / `fDuration` / priority is P.

## 4. World effects: missiles, hotspots and auras, spawned entities, forced movement, destruction

Sources: client exe (VAs, image base 0x400000), node vtables (slot 5 = Unpack, slot 10 = client execute), the
decoded trees in `data/script_trees` (operand variable names, raw values), `ics/script_runtime.py` / `ics/world.py`
as of 2026-10-22. **C** = confirmed by client code or exact data, **P** = probable (inferred from data / names).
"Server-only" = vtable slot 10 is the empty `0xAB4D80` / `0x4FB4C0`: the client never runs the node, the server
must produce the whole effect and tell the client through objects, properties, movement blocks, scriptlets or
events. Counts `n/m` = nodes / scripts; `cov k` = skills that stop on it in `tools/script_coverage.py` today.

Shared helpers seen in every client execute below (C):

| VA | what |
|---|---|
| `0x992280(script, operand, out u64)` | resolve an entity operand to an IID (SELF / variable); false when 0 |
| `[0x1B67258]` vtbl+0x58 `(iid lo, hi)` | object by IID |
| `0x991F60(script, 0, out)` | the script's **context/source entity**: owner IID, then the props `0x100004FE` (iid, only for script type 0x10000006), `0x100004E2` (iid, NetSharedVisually), `0x100004E1` / `0x1000063B` / `0x1000069B`; falls back to the script's own context |
| `0x58B320(ent, prop, out)` | generic property read (container picked by the property definition byte +0x12: 4 object table, 3, 8, 7 computed) |
| `0x99F4D0(script, operand, value)` | write a value into the variable an operand names |
| `0x5897A0(ent)` | collision radius: `template[+0x74] * scale(0x5690F0) + 0.05` |
| `0x853380(teamA, teamB)` | relation: same team 4 (ally, also self), either team 0 -> 1 (neutral), else 2 (enemy) |
| `0x9D0180(ent, flags)` | kind test (flags 0x10108 units, 8 champions, 0x1000 props, ...; see `targeting-and-relations.md`) |

**Relation operands are bit masks (C, CheckRelation evaluate `0x993860`):** `(relation(teamA, teamB) & mask) != 0`.
So the values seen in nodes mean: **2 = enemies, 3 = enemies + neutral ("hostile"), 4 = allies incl. self,
7 = everyone, 1 = neutral only**. The operands may be a team number (int) or an entity (its PVP_Team 0x1000009C).
The same masks are used by FindTargets, CreateHotspot and CreateAura (field "relation"). `ics/script_runtime.py`
`_hostile` treats only 3 as hostile; it must implement the mask (P for 1 being used anywhere).

**Shape enum (C, shape builder `0x9805B0`, used by FindTargets `0x9CCE60`; the same numbers appear in
CreateHotspot / CreateAura / DestructionImpulse):**

| id | shape | dimensions |
|---|---|---|
| 1 | sphere | radius (= range field, plus the caster's radius when the "add own radius" byte +0xD is set) |
| 2 | box | x half = `dimA/2`, y from 0 to `length` along the facing (or -L/2..L/2 when the "centered" byte is set), z from 0 to `dimB`; in FindTargets dimA = the 3rd operand, dimB = the 4th (the designers' names call them Height / Width: their box axes are swapped relative to the names, keep the code order) |
| 6 | box from the caster's own bounding box (0x570520) |
| 7 | vertical cylinder/capsule: radius = range, from z -0.5 to `height + 0.5` |

FindTargets byte +0xE = sort the results by distance (C: 0x9C6BC0 sort), +0xF = do not exclude self (P),
`+0x8C` = kind flags, `+0x90` relation mask, `+0x94` max count (C, copied into the query object).

---

### 4.1 Missiles (projectiles)

**Records and classes (C, data).** Skill projectiles are objects of class `0x40......` with object flags 0x20
("destructible" template, developer name placeholder) and their own visual scriptlet table (property 0x8E); the
93 champion projectiles are listed in `units-and-ai.md` 1.3. Their HFSM program is a 0x34 script reached from the
class (runtime `missile_scripts(cls)`; e.g. 0x40000090 -> 0x3400003F). Missile collision snippets exist as 0x3F
records (0x3F000003/6/9, a variable block + one 0x34 node chain). The 0x3A blackboard `0x3A000001` (SELF,
BrushCounter) is shared by 187 projectiles/effects.

**How the client sees a missile (C for the mechanism, P that the original did exactly this).** There is no
missile message, no missile component and no "projectile" string in the game code (only Havok's
`maxProjectiles`). A missile is an ordinary network object: created with its class (it gets its model and 0x8E
visuals), then moved by **0xB0 movement blocks** exactly like a unit (`client-movement.md`): the client keeps a
9-state history, samples it 0.1 s late and dead-reckons `pos = state.pos + v * dt` (C 0x552130); velocity =
heading/speed/pitch from the motion bits (bit 4 heading, 0x20 speed, 0x40 pitch; C 0x57DA90). Consequences:
- straight missile: one state at launch (position = shooter + fire offset, heading, speed) is enough; send a new
  state on every redirect (bounce/ricochet, homing correction) and a stop/removal at the end;
- homing on a moving target: re-send heading every 0.1-0.2 s (dead reckoning has no target field);
- **lobbed** (0x10000154): dead reckoning is linear, there is no gravity in the replay -> send states along the
  arc (e.g. every 0.1 s, with pitch so the velocity has the right z) or a straight line with the right flight time
  (P: the client draws what the states say);
- an error > 2 m between the replay and the new state snaps (C 0x60B5F0), so frequent small corrections are fine;
- end: the script's `DestroyEntity(SELF)[0 1]` plays `_HFSM_DestroyEntityAction` then removes the object
  (already in `ics`).

**Collision is server-side (C: no client path).** The server must test the missile against units each tick:
collision radius = target `0x5897A0` radius (+ the missile's own); kind / relation filtering is done by the
missile script itself (its collision state checks IsKind / CheckRelation / HasStatus marker 0x100003AB).

**Missile script events (C from the trees, P for the exact parameter set):**

| event | when | parameters (names in the trees) |
|---|---|---|
| `0x10000049` | the missile was created (start) | - |
| `0x10000002` | it touched an entity (unit, prop, or destructible sub-entity) | `Collider` (iid), `SubEntity` (int), `EntityPosition` (vec3), `EtherealCollision` (hash 0xAE98CBC, bool: pass-through hit) |
| `0x10000035` | out of range / lifetime over | - |
| `0x10000126` | a tracked basic-attack shot reached its target | (status 0x34000470 tracker) |
| `0x10000005` | (shooter side) after LaunchTetheredMissile / AttachEntity / LaunchMissile: the tether/attached projectile finished or came back (P) | - |
| `0x10000140`, `0x10000141` | raised by the missile script on the shooter with RaiseEvent (hit notifications) | as RaiseEvent params |

Shooter scripts also wait on `0x1000001D` (skill used) and `0x10000009` (interrupt) around the launch.

**Runtime state today.** `_missile` launches with class, target, range, speed; ObjectMissile creates the object,
follows / flies to a point, extends point shots to full range, hits the first hostile unit within 1 m. Missing
(each P from the operand names, C for the field order):
- op0 = an **existing entity to launch** (e.g. `0x3400003A`: the entity a SpawnEntity made, class field 0) ->
  coverage gap "LaunchMissile of a spawned entity": move that entity as the missile and run its own scripts;
- op4 = **out missile IID** (MissileIID / MissileIID1/2): write the new object's IID into the variable;
- r4 after op5 = **script override** (`0x34000160` in 0x34000161): the missile runs this 0x34 script instead of
  its class's;
- op5 = fire offset (vec3 in the shooter's frame) -> spawn position; op7 = skill slot (SuperStrengthSkillSlot);
- r1, r1 (1 1) and r4 (2): P "home on target" / "collide with units" and a collision mode; the trailing r1 r1
  (0 0) P "ignore terrain", "pierce".

---

### 4.2 Hotspots and auras (area effects)

There is no client hotspot code (no string, no component; the nodes are server-only). A hotspot is a server
volume that applies **status records 0x48......** to the entities inside; the visible part is a separate object:
CreateHotspot's world-state field `0x2E......` (or an object class `0x40......`, e.g. 0x4000081E, 0x40000CB2,
0x40000A94, 0x40000ECC) is created at the position so the client shows the ground effect (C data, P mechanism).

**Field layout of CreateHotspot 0x10000059 and CreateAura 0x10000122** (C order from the Unpack helpers
`0x9AE7D0` / `0x9BE060` + `0x9CC620`; meanings P from 50 examples):

| # | field | meaning |
|---|---|---|
| op0 | f32 | lifetime of the hotspot = duration of status A (HotspotDuration / EffectDuration / AuraDuration / GasCloudDuration / VortexLifetime / Hangtime); unset = until destroyed |
| op1 | int | rank passed to the statuses (SkillRank) |
| r4 A | 0x48.. | status applied **while inside** (removed on exit or when the hotspot ends) |
| op2 | - | (always unset) status A extra parameter |
| r4 B | 0x48.. | status applied **once on entry** (not removed on exit); e.g. fear 0x48000A6B, marks 0x48000E60 |
| op3 | - | (unset) |
| op4 | f32 | status B duration (SecondaryFearDuration / EffectDuration) |
| r4 C | 0x48.. | status applied **on exit** (and to those inside when it ends): slows that linger, 0x480005B5, 0x48000818, 0x480012F3; often equal to A |
| op5 | - | (unset) |
| op6 | f32 | status C duration (EffectExitDuration / TailDuration / EffectLingerDuration / DebuffDuration) |
| r4 | mask | relation mask (3 hostile, 4 allies, 2 enemies, 7 all) |
| r4 | flags | kind flags (0x10108 units, 0x611108 / 0x610109 / 0x210108 / 0x410109 variants incl. champions and props, 8 champions, 0x100008, 0x30128, 32) |
| r4 | shape | 7 cylinder (radius), 2 box (length/width/height) |
| op7 | f32 | radius (HotspotRadius / SkillRange / AuraRadius / PerceptionRange / RevealRadius) |
| op8 | f32 | box length (SkillRange / HotspotInitLen / HotspotLength) |
| op9 | f32 | box height |
| op10 | f32 | box width (HotspotWidth / HotspotWidth1) |
| op11 | - | (unset) |
| r1 x5 | flags | typical `0 1 1 1 0`; P: [0] include the owner, [1] re-evaluate every tick (enter/exit), [2] apply to entities already inside, [3] remove A on exit, [4] stack per hotspot |
| op12 | vec3 / iid | **CreateHotspot: position** (TargetPosition / HotspotPosition / StartPosition / SELF = owner's position); **CreateAura: the entity it is attached to** (SELF or unset = owner; or a hotspot/missile IID) |
| op13 | iid / handle | out: CreateHotspot = the hotspot's IID (HotspotIID / VortexIID); CreateAura = a handle (HotspotHandle / SlowHotspotHandle / MarkHotspotHandle / RevealHandle) |
| r4 | 0x2E.. / 0x40.. | (CreateHotspot only) the world state or class of the visible object |
| r1 x3, r4 | | (CreateHotspot only) trailing flags, usually 0 (`0x340007DD`: 0 0 1 0) |

**Server semantics (P, strong):** each server tick (0.1 s) per hotspot: query the shape at its position (aura:
the attached entity's position and facing) with the relation mask relative to the hotspot's owner and the kind
flags; for entities that entered: apply A (duration op0 or "while inside") and B (duration op4); for entities
that left: remove A, apply C (duration op6). At the end of the lifetime or on DestroyHotspot: remove A from those
inside, apply C, remove the visible object. The statuses do the real work (slow, damage over time, reveal, fear):
their scripts receive the usual `0x10000006` start event with EffectSource = hotspot owner. Scripts that own a
hotspot also listen to `0x10000003`, `0x10000006`, `0x10000007`, `0x1000001D` (C trees) - P: the hotspot raises
`0x10000006`/`0x10000003` on its owner script when someone enters / leaves (aura "enemy detection" handles such as
`EnemyDetectionHotspotHandle`, `NearbyEnemyRange`).

**DestroyHotspot 0x1000002D** `B r4 O O O` (35/25, cov 3): r4 = 1; op1 = hotspot entity (HotspotIID / VortexIID /
SELF), op2 = aura handle. Server: end that hotspot/aura as above (either operand may be set). Server-only.

**ResizeHotspot 0x10000137** `B O r4 O O O O O O` (4/2): op0 hotspot IID, r4 = 2 (shape box), op2 length,
op3 width, op4 height, op6 aura handle (FirewallHotspotHandle ...). Server: change the box dimensions (growing
walls); re-evaluate occupancy next tick; resize the visible object if it scales (P: send its scale property).
Server-only.

---

### 4.3 Spawned entities, ownership, attachment

**SpawnEntity 0x100000A0** `{B O O r1 r1 r1 r1 O r4 r4} r4 O O {r4 O}` (94/73, cov 22; server-only, Unpack
`0x9CB5A0`). C field order, P meanings:
- helper (same as FindScatterPosition): op0 position (TargetPosition / CreatePosition / StartPosition), op1 backup
  position, r1 x4 flags (`1 0 0 0` = use the position as is; `0 0 0 1` = find a free pathable point), op2
  scatter radius, r4 tries (10), r4 (1);
- r4 class `0x40......` (turrets, pets, clones, loot, teeth, punching bag ...);
- op3 (unset; P owner override), op4 **out entity IID** (MissileIID / LootIID / PunchingBagIID / TeethOne);
- `{r4 O}` list: initial **properties** of the new object, property id + value operand: `0x1000009C` PVP_Team
  (MyTeam), `0x10000167` level (MyLevel), `0x1000099B` (tooth number), `0x10000xxx` others.
Server: create the object of that class (world `spawn`), team defaults to the owner's, creator = owner (so
GetCreator 0x100000A5 and relation tests work), set the listed properties (send them in the object bundle), start
its scripts (property 0xEF blackboard + class scripts), write its IID. Scripts after a spawn wait on `0x10000009`
and `0x1000001D` (C trees).

**GetEntityProperties 0x10000155** `B O {r4 O}` (27/24) - **correction: it reads, it does not set (C, client
execute `0x9B5920`)**: for each entry (stride 0x1C, count at +0x2C) it reads property `entry+0x18` of the entity
(op0) with `0x58B320` and writes it into the entry's variable with `0x99F4D0`. Examples: (SELF -> HitEffectDID)
[0x10000AC2], (TargetIID -> IsPhasing) [0x10000CC0], (SELF -> GeneratorOwnerIID) [0x1000030F], (-> IsFuse) [1188].
Server: read the entity's current property (runtime value, else the template / world-state default, else 0) into
the variable. This is the client node with an execute; the server must do the same for its own scripts.

**GetCreator 0x100000A5** `B O` (24/24, cov 3) - **correction: it is a getter (C, execute `0x993480`)**: writes the
script's context/source entity (`0x991F60`: owner, then creator props 0x100004FE / 0x100004E2 ...) into op0
(CreatorIID / ShooterIID / CasterIID / EffectSource / JokerIID / StarroIID). Server: the creator of a spawned
object / shooter of a missile / source of a status; the owner itself for a champion script.

**AttachEntity 0x1000008F** `B O O r4 O r4 r1 O r1 O O` (27/20; server-only, Unpack `0x983A10`): op0 child,
op1 parent, r4 parent attach point key (0x10000075, 0x1000007F, 0x10000072, 0x1000006E, 0x1000007B, 0x100000B0 =
P hand / hardpoint keys), op2 local offset (AttachmentOffset / AttachmentServerOffset), r4 child attach point
(0x10000081 / 0), op3 out handle, r1 (1), op4 (BlipSequence), r1 (0/1), op5 out success, op6. Server: glue the
child to the parent's point (move it every tick with the parent, mode with no replay: the client skips its own
replay when entity flags +0x118 & 0x40 and not 8, C 0x609240); release on StopAction(handle) / RemoveAttachment.
The wire form of "attached" is not traced (gap): best guess = movement mode 0x41 / 0x4C rows (remote module 9 =
`SetEntityFrame`, C 0x60B0F0) with frames sent by the server each tick. Events after it: 0x10000141, 0x10000005,
0x10000067, 0x10000119 (C trees).

**PickUpEntity? 0x10000042** `B O O` (19/19, cov 1; server-only): op0 entity (TargetIID / AttachedIID / SELF),
op1 out Success. Used by grab / carry skills with AttachEntity; P: "claim" the entity for carrying (fails when it
is already carried or not carriable); server: success = entity exists, alive, not attached.

**GetEntityRadius 0x10000120** `B O O` (12/12, cov 2; C execute `0x993330`): op1 = `0x5897A0(op0)` =
template radius x scale + 0.05 (EntityRadius, PhysicsRadius, DistanceFromWall, MissileRadius).

**IsMoving? 0x100000E1** `O r1` (45/29, cov 6; predicate, server-only): op0 entity, r1 0/1. True when the
entity has a non-zero velocity / an active move order (recall 0x3400000A is cancelled by it together with
"moved more than 0.25 m"); r1 = 1 P "count forced movement too". 

**IsInFront? 0x1000016F** `O O O` (6/5, server-only): (TargetIID, -, SELF): P true when op0 is inside the
front half-space (or a cone) of op2's facing.

---

### 4.4 Forced movement: dashes, knockbacks, teleports

All server-only. The client shows them only through 0xB0 movement blocks (C, `client-movement.md`): send the
entity's states with heading + speed (and pitch for airborne parts), one every 0.1 s is safe, and a final state
with speed 0; a **teleport** = new position + speed 0 + seq A (0x800 byte) incremented (hard snap, C). While a
forced movement runs the client must not accept orders: the client already buffers skills when the movement
mode is one of 0x40/0x41/0x47/0x48/0x4A/0x4B/0x4D/0x4E/0x4F (C), so these modes are the forced-movement rows of
record 0x48000002 (P: which one is dash / knockback / knockup is not traced); move orders are never blocked by
the client, so the server ignores 0x20EE during them. The animation comes from scriptlets the skill runs.

**DashToPosition 0x100000EA** `B O O O O O O O r4 r1 O` (36/35, cov 17): op0 entity (SELF), op1 target
position (or an IID: TargetCurrentPos / TargetIID), op2 speed (MissileSpeed / DashVelocity / DashSpeed /
ChargeVelocity / MoveSpeed), op3 max distance (SkillRange / DashDistance), op4 min distance (MinDashDistance:
a closer click is pushed out to it), op5 stop distance from walls (DistanceFromWall), op6 out handle (DashHandle /
KnockbackHandle), r4 15 or 0 (P: timeout in s, or a movement priority), r1 1 (P: stop at units / write the
started flag), op7 out DashStarted (bool).

**DashToEntity 0x1000013E** `B O O O O r4 r1 r4 r1 O` (17/17, cov 1): op0 entity, op1 target entity, op2 speed,
op3 out handle, r4 f32 1.0 / 1.9 (P: stop distance in radii / range factor), r1 0, r4 f32 15.0 (P: timeout s),
r1 0/1, op4 out DashStarted. Follows the target (re-aim each tick).

Events the dash raises on the owning script (C trees, 0x34000038 / 0x3400039D; meanings P, strong):

| event | meaning | what the scripts do |
|---|---|---|
| `0x100000C4` | dash started (also DashStarted = true) | go to the "dashing" state |
| `0x100000C1` | arrived (reached the point / touched the target) | apply the hit (damage, statuses) |
| `0x100000C3` | could not start (no path, rooted, invalid point) | show skill error 0x100000D8, clean up |
| `0x100000C5` | interrupted (stunned, target lost, blocked, timed out) | clean up |
| `0x10000002` | touched a unit on the way (Collider ...) | charge-through hits (0x34000038 S4->S5) |

Server: clamp the destination to [min, max] distance along the line, snap to the navmesh, path straight (stop
at walls minus op5), move at op2, raise C4 at start, 0x10000002 per unit crossed, C1 on arrival, C5 when
interrupted (StopAction on the handle, CC with DisableActions movement families, death), C3 when it cannot start.

**Knockback 0x100000C6** `B O O O O O O` (6/6): op0 entity, op1 source (position or entity: push away from it),
op2 duration, op3 speed, op4 distance, op5 out handle. Any two of duration / speed / distance define the third
(the examples give two). Server: move away from the source along the line, stopping at walls; scripts then wait
on `0x100000A6` (P: knockback finished). The knockdown / knockup statuses (0x48000295 / 0x48000296) do the
animation and stun.

**CancelMovement? 0x1000001B** `B O` (14/12, cov 1): op0 entity (SELF). P: stop the current move/path
(server: clear the destination, send a speed-0 state). Used after attach / teleport steps.

**SetMovementMode? 0x100000F1** `B O r4 r4` (14/7, cov 1): op0 entity, r4 0/1/2, r4 1/2/0. P: push/pop a
movement mode (e.g. flying / ground / rooted) with a priority; server: record it, change the wire mode byte only
if a matching row exists (gap: values not mapped to rows).

**SnapToGround 0x100000B0** `B O r1 r1` (18/18, cov 1) - **C (client execute 0x9B6470, disassembled)**: reads the
position variable op0; if the second r1 (+0x25) is set and the script's entity cannot stand there (navmesh test
`0x4FB3B0` with the entity's agent) z = the entity's own z, else z = the ground height under the point
(`0x855CF0`); if the first r1 (+0x24) is set the orientation is reset to identity; writes the position back.
Server: z = navmesh / terrain height at (x, y) (or the owner's z per flag). Used before CreateHotspot.

**FindScatterPosition 0x10000025** `{B O O r1 r1 r1 r1 O r4 r4} O r1` (31/25) - server-only; op0 in/out
position (TargetPosition / TeleportPosition / HomePosition), op1 center/fallback, r1 x4 flags, op2 radius
(ScatterRadius 5), r4 tries (10), r4 (0/1/4), op3 entity (SELF / TargetIID / AttachedIID), **trailing r1 = 1:
also teleport op3 there** (P, strong: recall 0x3400000A S4 has no other teleport node; 0x34000111 too).
Server: nearest pathable point within the radius of the center for that entity's agent size, random scatter when
the radius is > 0; with the flag move the entity there (teleport block, seq A++).

**FindValidPosition 0x10000109** `{helper} O` (15/12, cov 0) and **FindValidPosition2 0x10000146** `{helper} O r1`
(1/1, cov 1): same helper; op0 position (TestPosition / ChampionPosition / TargetPosition), op1 backup, op2 scatter
radius, op3 entity; writes the nearest valid point into op0 (0x10000146 with BackupPosition used when none is
found). Server-only.

**BeginTeleport? 0x1000007D / EndTeleport? 0x1000007F** `B O O` (2/2 each; SELF, SELF; recall 0x3400000A
enter / exit). P: start/stop the teleport effects of an entity. The client has a matching message pair:
`0x218A` (u8 0 | u64 IID; handler 0xA846D0 increments a per-IID counter and runs 0xA29020, which calls
`GM_MapManager.RecvNotice_UI_StartTeleportEffects` 0x8B9DA0) and `0x2189` (handler 0xA73E80 -> 0xA6A870, the
decrement; 0xA29020 calls `...StopTeleportEffects` 0x8BA0E0 when the counter is 0) (C for the handlers, P for
start = 0x218A). Server: send 0x218A at Begin, 0x2189 at End.

**GetCameraHeading 0x10000141** `B O r1` (1/1) - **C (client execute 0xAB60E0)**: only when a camera exists
([0x1B73518]+0xE4): writes the camera yaw into op0 (f32 variable) or the vector (-sin yaw, cos yaw, 0) (vec3
variable); r1 adds 180 degrees. A server has no camera: use the champion's facing (P), or the last order's
direction.

**CenterCameraOn? 0x10000078** `B r1 O` (10/6, cov 1) - client execute 0xAB56D0 (C): only for the local player's
entity (0x863040); takes the position op0 (CurrentPosition) and calls 0x910830(player view, r1, position) - P: snap
/ recentre the camera (end of recall) or show the ground marker. Server: nothing to do unless the client does not
run the script; then P: the camera follows the champion anyway after a teleport.

**SetCameraMode? 0x1000014B** `B O r1 r4` (18/9, cov 4; server-only): (SELF/TargetIID)[1|0, 5] around recall and
channels. P: enter/leave a channel state 5 for the entity (UI channel bar / camera lock). Server: no visible
effect known; no-op is safe (gap).

---

### 4.5 Collision toggles

**DisableCollision 0x1000006F / EnableCollision 0x10000070** (109/82 and 89/87; no fields besides the next node,
C from the trees) - client executes `0x97D860` / `0x97D720` (C): take the script's entity, its physics component
(`0xAA10B0`), and call `0x976990(filter, 0|1)`: 0 removes the entity from collision (if nothing else holds it:
`0x972110`), 1 restores it (`0x971F30` with a collision-filter struct, vtable 0x15F92A8). Server: an entity with
collision off does not block units and is not hit by missiles / FindTargets that require physics (missiles'
end state turns it off, their start turns it on).

**SetCollisionLayer 0x10000114** (4/4; no fields; client execute `0x97D950` -> `0x971F30` with the layer struct
from the script, the client string `CollisionLayer_Property` names it): P restore the entity's collision layer to
its template value. Server: no-op.

**Unk_0151 0x10000151** (8/8, cov 1; no fields; server-only): appears in a missile's death state next to
ClearEntityList, between two LaunchTetheredMissile calls, and before an ApplyEffects in a status (0x340005EF). P:
"new damage instance" / reset the per-cast hit bookkeeping. Server: no-op is safe today.

---

### 4.6 Destruction (props that break)

**The client has three server->client events that apply a destruction impulse (C)** - the protocol notes call
them "movement update" (wrong):

| event | client handler | wire (after the object IID) | effect |
|---|---|---|---|
| `0x8A` | 0x632590 -> **0x632370** | `u8 0 | Position | f32 radius | f32 magnitude | u32 level | u32 hit scriptlet key | u32 FX record | u8 flag` | sphere impulse |
| `0x1` | 0x632560 -> **0x6322F0** | `u8 0 | Position (frame) | vec3 half extents | f32 magnitude | u32 level | u32 key | u32 FX | u8` | box impulse |
| `0x8` | 0x6325C0 -> 0x62C990 + **0x6323F0** | `u8 0 | {ray: GUID/u64/Position/vec3 vec3 u32 ...} | u32 x4 | u8` | raycast impulse |

All three call `0x630E80(frame, magnitude, level)` then a shape query (`0x631C50` sphere / `0x631D00` box /
`0x631DA0` ray) over the Havok destructibles, then `0x631FA0` with the hit scriptlet key and FX record (the
hit effect on the broken pieces). The serializers exist in the client (`0x445C90` 0x8A, `0x445A30` 0x1,
`0x445B60` 0x8), the usual sign of a server->client message (P that the original server sent them).

**DestructionImpulse 0x10000085** `B r1 r4 r4 r4 O O O O O O O O O r4 r4 r1 r1 r1` (193/154; coverage 18) - client
execute `0xAB70C0` (C): the same computation run locally. Fields (C offsets): r1 +0xC "box starts at the origin"
(0 = the box is moved forward by half its length), r4 **+0x10 shape (1 sphere, 2 box)**, r4 +0x14 **level 1/2/3**
(cosmetic / damage / destroy, P), r4 +0x18 default magnitude; op0 radius (DestructionRadius / ExplosionRadius),
op1 box length, op2 box dimension x, op3 box dimension z (names: Height / Width), op4 world position
(MissilePositionOnCollision; default the entity's frame), op5 magnitude (DestructionMagnitude[_Cosmetic /
_Destroy]), op6 (unset), op7 target entity + op8 sub-entity (TargetIID + TargetSubEntity: break that one
destructible piece directly, `0x631650`); r4 +0xDC FX record `0x1E......` (0x1E00001B, 0x1E000023, 0x1E0000B5), r4
+0xE0 hit scriptlet key (`0x10000223` VFX hit), r1 +0xE4/+0xE5/+0xE6 (the last is passed as the u8 flag).
**Server:** compute nothing physical (props' gameplay state is the server's own), broadcast `0x8A` (shape 1) or
`0x1` (shape 2) to every client in range with the fields above in that order (radius/magnitude as f32 taken from
the ops; level, key and FX from the r4 fields). Destructible gameplay objects (e.g. Sunstone 0x40000646, rocks)
still need their own scripts / damage. Cheap fallback: no-op (only cosmetic debris is lost).

**DestructionRaycast 0x100000DD** `{B O O O O r1 r4 O O O} r4 O r1 r4 r4` (2/2, cov 1) - client execute
`0xAB6440` -> `0x995A30` builds the ray from the script, then `0x62C990` + `0x6323F0` (C): op0 SELF, op1 target,
op2 range, op3 ray offset, op4..op6 box height / length / width, op7 magnitude; r4 FX `0x1E000023`, r4
`0x10000223`. Server: broadcast event `0x8` (ray from the entity toward the target, length = range) or no-op.

**SetDestructibleState? 0x1000017E** `B O {r4 ...}` (2/1, Sunstone 0x340003F1) - client execute `0x996B00` (C):
reads property lists `0x1000051F` / `0x1000051E` (the Destructible_OnBreak keys) of the entity op0 and applies the
node's list entries (type 6 vector / type 0xC entries; values `3 0 1.0 0 +-1.0 0 0 0 -1.0 0`). P: set the
break-state / impulse direction of a destructible. Server: set the corresponding properties (gap: exact effect).

---

### 4.7 Minimap rings (UI)

**ShowMinimapTargetingRing 0x10000022 / Hide 0x10000056** `B O r1` (8/7 each) - client executes `0xAB6330` /
`0xAB62D0` (C): op0 = skill slot (LastSkillSlotUsed / UltimateSkill); show calls `0xA4F0C0(slot, script type ==
0x10000009, r1, 0)`, hide `0xA5DAB0(slot, r1)` -> the `GM_MapManager.RecvNotice_ShowMiniMapTargetingRing` UI
notice. **ShowMinimapTargetingRing2 0x10000150** `B r4 O O` (7/3, cov 1; execute `0xAB4D90`, C): op0 entity
(PredatorIID / SELF), r4 mode (1/2/4/-1) -> `0xA4F060(mode, iid)`: a ring around that entity on the minimap.
Server: these run in the client when the client runs the script; for server-run skill scripts there is no
message that triggers them (gap: P the original client ran the champion's skill script copy for such UI nodes;
see the VM section). No-op on the server.

---

### 4.8 Node table (this section's classes): what the server must do

| id | name (corrected) | n/m | client exec | server action | conf |
|---|---|---|---|---|---|
| 0x1000005E | LaunchMissile | 77/59 | - | create/move object; op0 existing entity, op4 out IID, r4 script override (missing in ics) | C order, P extras |
| 0x10000154 | LaunchLobbedMissile | 17/14 | - | as 0x5E + arc: op2 StraightUpDistance, r4 launch angle deg (70/90, 0 default), r4 3.0/3.25 (P gravity factor / flight time), r1; send arc states | P |
| 0x1000005F | LaunchTetheredMissile | 6/4 | - | as 0x5E + op8 grab offset (end of the tether on the target), op9 Width, r4 tether factor 0.5-0.8 (f32), r1 r1; goes out and comes back; owner gets 0x10000005 | P |
| 0x10000134 | SetMissileVelocity | 20/18 | - | op0 missile (SELF/unset = the script's missile), op1 new speed (CollisionVelocity / ReturnVelocity / NewSpeed): change speed, re-send a state | P strong |
| 0x10000062 | RedirectMissile | 6/5 | - | implemented; r1 1 = keep homing; op1 range limit | C order |
| 0x10000151 | Unk (no fields) | 8/8 | - | no-op | ? |
| 0x10000059 | CreateHotspot | 15/13 | - | server volume + visible object, statuses A/B/C | C order, P meaning |
| 0x10000122 | CreateAura | 37/28 | - | volume attached to an entity, out handle | C order, P meaning |
| 0x1000002D | DestroyHotspot | 37/27 | - | end hotspot / aura | P strong |
| 0x10000137 | ResizeHotspot | 4/2 | - | change box size | P |
| 0x100000A0 | SpawnEntity | 94/73 | - | create object + properties, out IID | C order, P meaning |
| 0x10000155 | **GetEntityProperties** | 27/24 | 0x9B5920 | read properties into variables | C |
| 0x100000A5 | **GetCreator** | 24/24 | 0x993480 | write creator / shooter / source IID | C |
| 0x1000008F | AttachEntity | 27/20 | - | attach child to parent point, out handle/success | P |
| 0x10000042 | PickUpEntity? | 19/19 | - | out success | P |
| 0x100000EA | DashToPosition | 36/35 | - | dash + events C4/C1/C3/C5 | P strong |
| 0x1000013E | DashToEntity | 17/17 | - | dash following a target | P strong |
| 0x100000C6 | Knockback | 6/6 | - | push away; event 0x100000A6 at the end | P |
| 0x1000001B | CancelMovement? | 14/12 | - | stop path, speed-0 state | P |
| 0x100000F1 | SetMovementMode? | 14/7 | - | record mode | P weak |
| 0x100000B0 | SnapToGround | 18/18 | 0x9B6470 | z = ground height | C |
| 0x10000109 | FindValidPosition | 15/12 | - | nearest valid point | P |
| 0x10000146 | FindValidPosition2 | 1/1 | - | same, backup point | P |
| 0x10000025 | FindScatterPosition (+teleport) | 31/25 | - | point near; flag = teleport | P strong |
| 0x10000085 | DestructionImpulse | 193/154 | 0xAB70C0 | broadcast 0x8A / 0x1 (or no-op) | C |
| 0x100000DD | DestructionRaycast | 2/2 | 0xAB6440 | broadcast 0x8 (or no-op) | C |
| 0x1000017E | SetDestructibleState? | 2/1 | 0x996B00 | set break props | P |
| 0x100000E1 | IsMoving? | 45/29 | - | velocity != 0 | P |
| 0x1000016F | IsInFront? | 6/5 | - | facing half-space test | P |
| 0x10000120 | GetEntityRadius | 12/12 | 0x993330 | radius x scale + 0.05 | C |
| 0x1000014B | SetCameraMode? / channel | 18/9 | - | no-op | ? |
| 0x10000078 | CenterCameraOn? | 10/6 | 0xAB56D0 | no-op | P |
| 0x10000150 | ShowMinimapTargetingRing2 | 7/3 | 0xAB4D90 | no-op (client UI) | C |
| 0x10000022 | ShowMinimapTargetingRing | 8/7 | 0xAB6330 | no-op (client UI) | C |
| 0x10000056 | HideMinimapTargetingRing | 8/7 | 0xAB62D0 | no-op (client UI) | C |
| 0x1000007D | BeginTeleport? | 2/2 | - | send 0x218A (u64 IID) | P |
| 0x1000007F | EndTeleport? | 2/2 | - | send 0x2189 | P |
| 0x10000141 | **GetCameraHeading** | 1/1 | 0xAB60E0 | use the champion's facing | C |
| 0x1000006F | DisableCollision | 109/82 | 0x97D860 | entity stops colliding | C |
| 0x10000070 | EnableCollision | 89/87 | 0x97D720 | entity collides again | C |
| 0x10000114 | SetCollisionLayer (restore) | 4/4 | 0x97D950 | no-op | P |

### 4.9 Gaps in this area

- Wire form of attachment (carried objects, grabs) and which movement-mode byte (0x40-0x52 rows) is dash,
  knockback, knockup, carried; trace `0x608FC0` callers with the mode values in a live session (diag).
- Lobbed and tethered missile extra fields (r4 angle / factor values) are inferred from names only.
- Hotspot r1 flag meanings and the events a hotspot raises on its owner (0x10000006 / 0x10000003 per entrant?)
  are inferred; a status script that reads `EffectSource` of a hotspot status would confirm.
- Dash r4 15 / 15.0 and DashToEntity r4 1.0-1.9 not confirmed.
- Whether the original server broadcast destruction events 0x8A / 0x1 / 0x8 is inferred from the serializers.

## 5. VM conventions, builtins, expressions, entity lists, teams, predicates, AI hooks and the unknown node classes

Static analysis of `InfiniteCrisis.exe` (VA, base 0x400000) with the Ghidra decompilation (`re-work/decomp`), capstone
disassembly of functions Ghidra did not split, and the decoded trees in `data/script_trees`. **C** = confirmed by the
client code (or exact decode), **P** = probable (data, variable names, neighbours). Example records are 0x34 DIDs;
skill names come from `catalog/data/skills.tsv`. "exec" = vtable slot 10 of the node class; "Unpack" = slot 5.

### 5.1 VM conventions every node below relies on (C)

- **Two run methods.** Slot 9 (`vfunc +0x24`, "run") is what the VM calls; slot 10 (`+0x28`) is the class's own work.
  - Actions: slot 9 = `0x45AED0`: call slot 10, then `return next ? next.run() : true`. So **an action chain used as a
    condition returns the result of its last node** (true when it ends with an action).
  - Predicates: slot 9 = `0x45AEC0`: tail-jump to slot 10 (the boolean). Predicates have no `next` (their operands start
    at +8 instead of +0xC).
  - `0x05` AnyOf slot 9 `0x45B830`: run children in order, return true at the first true (no `next`). `0x09` AllOf
    `0x45B7F0`: stop at the first false. **Inside an action chain they are a selector / sequence**, each child being a
    whole chain (its actions run, its last node gives the result).
  - `0x0A` NodeCondition slot 9 `0x45B070`: `return !child.run()` (the child is the node unpacked as its "next").
  - `0x07` IfThenElse slot 9 `0x45B870`: `cond` = node at +0x18; children array at +8 = [then, else, after];
    run then or else, then `return after ? after.run() : true`.
  - `0x0D` While slot 9 `0x45B8D0`: `while cond.run(): body.run()` with a hard cap of **1025 iterations** (`edi > 0x400`
    breaks), then `return after ? after.run() : true`.
  - `0x15` Switch slot 9 `0x45B940`: see 5.2.
- **Operand** (Unpack `0x453160`) = 0x18 bytes: a 16-byte typed value (+0 payload / pointer, +8 type), +0x10 source,
  +0x14 slot. `source` selects a variable block through the context (`ctx->vfunc+0x30(source)` for writes, `+0x34` for
  reads); `slot = -1` = no variable (the literal/defaults `0x1B57F3C` (-1 int), `0x1B57F40` (0), `0x1B57F90` (null IID)).
  Source 0 = the current event's parameter block, source 2 = the owner block (SELF = hash 0x4DD4 there).
- **Entity operands** go through `0x992280(ctx, op, out IID)`: an unset operand (source or slot = -1 and no literal)
  means **SELF** (`0x44C5C0` reads SELF's IID from the source-2 block). Then `DAT_01B67258->vfunc+0x58(IID)` = entity
  lookup. Nothing happens when the IID is null or unknown.
- **Unpack order is not memory order.** Most classes unpack their operands in field order, but several do not, and the
  decoded trees list operands in *stream* order. Checked here: `0x10000004` (stream: out @+0x24, entity @+0xC),
  `0x10000082` (out @+0xC, index @+0x3C, team @+0x24), `0x1000000D` (r4 @+0xC, target @+0x28, unit @+0x10),
  `0x1000004F` (+0xC, +0x24, +0x54, +0x3C, r1 @+0x84, +0x6C), `0x1000002F` (r4 @+0x24 first, then +0xC, +0x28, r4 @+0x40).
  The meanings below are given in **stream order** (the order `ics/script_model.py` prints).
- **Value types** (the typed value's +8, from the ClearVariable switch `0x45C320` and the arithmetic helpers): 0 bool,
  1 int32, 2 uint32, 3 float, 4 a 4-byte id (default `0x1B587D0`), 5 int64, 6 uint64 (IIDs), 7 double (timers, game
  time), 8 8-byte id, 9 vector3 (heap), 0xA **frame** (location + orientation, class vtable `0x15A7DE0`, 0x2C bytes:
  +0x10 location, orientation after it), 0xC string-like, 0xD/0xE/0xF flag sets (bitwise & works on 2, 6, 0xE, 0xF),
  0x10, 0x11. Arithmetic is typed: mixing types falls into the "invalid" result (`0x1B58008`, type -1).
- **Game time** `DAT_01B77A90` (double, .bss) is the clock every timer compares against.
- **Timers:** `0x02` StartTimer `0x45C270`: `var = duration < 0 ? -1.0 : now + duration`. `0x08` TimerExpired
  `0x45C210`: `false if var == -1.0, else var < now` (strict). **A timer variable that was never started holds 0.0 and is
  therefore already expired** (C). `ics/script_runtime.py` `_timer_expired` returns false for an unset timer: wrong
  for scripts that rely on "expired until started" (combat-idle timers, e.g. `0x34000357`).

### 5.2 Builtin node classes still missing in `ics` (node registry ids 0x01-0x18)

| id | vt | Unpack (stream) | exec | meaning | conf |
|---|---|---|---|---|---|
| 0x04 | 0x15A87C4 | `r4 @+8` event id, `r1 @+0xC`, `r1 @+0xD` (0x45BEB0) | `0x45AFE0` | **IsEventPending(id)[inList1, inList2]**: predicate; looks the id up in the running graph's two event lists (`0x460C50` scans list +0x10, `0x460C80` list +0x60) and ORs the results of the enabled checks | C code / P names of the two lists (received this tick / queued) |
| 0x0C | 0x15A8938 | `B {r1 len, r4...}` text | none (slot 10 is a clone) | **DebugLog(text)**: strings in `0x34000000` (UI flow); no effect | C |
| 0x12 | 0x15A88E0 | `B r4 @+0xC event id, O @+0x10 delay` (0x985580) | `0x45D0B0` | **PostEventDelayed(delay)[event]**: creates an event object with id r4 (`0x4607A0`, vt `0x15A8D08`) and schedules it at `now + delay` on the instance's queue (`ctx->vfunc+0x20`, `0x460CB0`). Ids seen: `0x10000120`, `0x10000121` | C (queue owner P) |
| 0x14 | 0x15A8850 | `O` (value = parameter-name hash) | `0x45CD50` | **HasEventParameter(name)**: true when the current event's parameter block (source 0) has a variable with that hash (`0x44A910`); e.g. `#0x9F942E2`, `#0xCC58914`, `#0x9A6A765` | C |
| 0x15 | 0x15A8BC8 | `{children} @+8` (0x45FBC0), `{case operands} @+0x18` (0x45F3F0, 0x18 each), `O selector @+0x28` | run = slot 9 `0x45B940` | **Switch(cases..., selector)**: compares the selector with each case value in order (`0x450890` typed equality); on the first match runs child[i], **falling through to the next non-null child** when child[i] is empty; with no match runs child[count-2] (default); then always runs child[count-1] (the "after" chain) and returns its result | C |
| 0x16 | 0x15A8A80 | `B O @+0xC var, r1 @+0x24` | `0x45C6B0` | **SetBool(var)[value]**: writes the byte | C |
| 0x17 | 0x15A8990 | `B O @+0xC var` | `0x45C320` | **ClearVariable(var)**: resets it to the default of its declared type (0, false, null IID, zero vector, empty frame / list) | C |
| 0x18 | 0x15A8A20 | `O @+8, O @+0x20` | `0x45B730` | **AreEqual(a, b)**: typed equality of the two operand values (both sources must resolve) | C |

Data: `0x16`/`0x17` are the "PerformedAction" flags and handle cleanup of the team-wide effects (`0x34000107`,
`0x340002AF`); `0x15` picks a stack VFX by stack count (`0x3400074C` Stack1..5 / EffectStackCount), hit-count marks
(`0x340007B6`), lane statuses (`0x340007D6`), star scriptlets (`0x3400056D`).

**Server:** implement 0x04 against the instance's event queue, 0x12 as `inst.after(delay, raise(event))`,
0x14 as "the current event carries this parameter", 0x15/0x16/0x17/0x18 exactly as above. **Fix** the runtime's
treatment of vt `0x15A88E0` as `>=` (the missile `0x3400003F` case): it is PostEventDelayed (C).

### 5.3 Expressions (evaluate = slot 10; all C unless marked)

Evaluate signature: `value eval(out, ctx)`; children at +8, +0xC, +0x10; extra raw flag after them.

| id | vt | evaluate | exact semantics |
|---|---|---|---|
| 0x01 abs | 0x15A9558 | `0x462950` -> `0x455150` | int32, float, int64, double, vector (component-wise); other types invalid |
| 0x04 min(a, b) | 0x15A90C0 | `0x463DA0` | `b < a ? b : a` (typed `less` `0x44F9D0`, `this < arg`) |
| 0x05 cross(a, b) | 0x15A97F8 | `0x4640B0` | a x b (right-handed): (ay bz - az by, az bx - ax bz, ax by - ay bx) |
| 0x07 sqrt | 0x15A95C8 | `0x4629D0` -> `0x4556A0` | float / double |
| 0x0A a & b | 0x15A9168 | `0x462350` -> `0x454AA0` | uint32 (2), uint64 (6), flag sets 0xE / 0xF; both the same type. Used as `(GetAttribute[0x100007BF] & Flags) != None` (stealth / visibility flags) |
| 0x0B cos | 0x15A96A8 | `0x462B30` | radians; float or double |
| 0x0C x - 1 | 0x15A9408 | `0x462710` | `x - one(type)`; **the runtime's `server-expr:0xc` = `/` is wrong** |
| 0x0D normalize | 0x15A9868 | `0x463FF0` | v / |v|; zero vector when |v| <= 1e-6 |
| 0x10 a \|\| b | 0x15A92B8 | `0x462570` | short-circuit: returns a if a is a true bool, else evaluates and returns b |
| 0x11 pow(a, b) | 0x15A9360 | `0x462A10` -> `0x455600` | both float or both double |
| 0x13 a && b | 0x15A92F0 | `0x4625F0` | short-circuit: if a "is false" (`0x44F500`: type bool and byte 0) return a; else evaluate and return b |
| 0x14 Random(a, b) | 0x15A9B78 | `0x462EA0` -> `0x455480` | uniform random between a and b in their type (int32, uint32, float, int64, uint64, double with min/max ordering); e.g. `Random(0, 360)` VFX yaw, `Random(Min, Max)` retarget interval |
| 0x19 round | 0x15A9B40 | `0x462E00` -> `0x457BD0` | `floor(x + one/2)` (P on the half: `0x457530` of `one`) |
| 0x1A ToInt32 | 0x15A99B8 | `0x4641F0` | int/uint/int64/uint64 bits kept (low word), float and double truncated toward 0, others 0; result type 1 |
| 0x1E clamp(x, lo, hi) | 0x15A9130 | `0x463E80` | `min(max(x, lo), hi)` (operand order x, lo, hi) |
| 0x21 ceil | 0x15A9638 | `0x462AB0` -> `0x4553E0` | float / double |
| 0x24 !a | 0x15A9328 | `0x462530` | bool result = `a is a false bool`; **a non-bool operand gives false** |
| 0x27 Select(c, a, b) | 0x15A9BB0 | `0x462F00` | evaluates c; first byte != 0 -> evaluate a, else evaluate b (lazy) |
| 0x2E sin | 0x15A9670 | `0x462AF0` -> `0x4557B0` | radians |
| 0x33 negate | 0x15A9398 | `0x462670` | `0 - x` typed (runtime has it) |
| 0x35 floor | 0x15A9600 | `0x462A70` -> `0x4552B0` | float / double floor |
| 0x37 frame + vector | 0x15A9C58 | `0x465270` | copies the frame (a), adds vector b to its location, orientation kept; result type frame |
| 0x38 frame (+) local offset | 0x15A9C20 | `0x4650F0` | rotates b by a's orientation (`0x4C79A0`, matrix from `0xAF2BF0`) and adds it to a's location; result frame (runtime has a vector version) |
| 0x3C z | 0x15A9980 | `0x462DC0` | float = vector.z |
| 0x40 Heading(frame)[deg] | 0x15A9C90 | `0x462F50` | yaw of the frame's orientation, negated and wrapped to [0, 360) (`0x4C5F20`, `0xAF3C20`); flag @+0xC: **1 = degrees, 0 = radians** |
| 0x41 WithHeading(frame, angle)[deg] | 0x15A9BE8 | `0x4653E0` | copy of the frame whose yaw is **replaced** by `angle` (pitch/roll and location kept, `0x4C7790`); flag @+0x10: 1 = angle in degrees, 0 = radians. The runtime's "position moved by an offset" is wrong (it returns a when b is a number, which keeps only the location) |
| 0x44 DegToRad (wrapped) | 0x15A9750 | `0x463F10` | `radians(fmod(x, 360)` wrapped to [0, 360)); input degrees |
| 0x45 Forward(frame) | 0x15A9D00 | `0x4644E0` | direction vector of the frame's orientation (`0x4C7760` -> `0xAF2BF0`; which matrix row is forward: P) |
| 0x46 LocationOf(frame) | 0x15A9CC8 | `0x4644A0` | the frame's location as a vector (value `vfunc+8`) |
| 0x47 Lerp(a, b, t) | 0x15FABA4 | `0x9887F0` -> `0x980120` | `a + (b - a) * t` for float, double and vector (t converted to float) |
| 0x10000003 ScaleByLevel(level, base, delta)[zeroIfLevel0] | 0x15FABDC | `0x97D2F0` | `base + (level - 1) * delta`; flag @+0x14: when set and level == 0 return zero of base's type |

Consequence for `ics`: the VM works on **frames** (location + yaw), not bare points. `GetPosition` (0x10000011) and
the position variables (TargetPosition, CurrentPosition ...) are frames; 0x40 / 0x41 / 0x45 / 0x38 need the yaw.
A server-side frame = `(x, y, z, yaw_degrees)` is enough (pitch/roll stay 0 on the ground). Usage: 0x40 [flag 1] for
knockback heading (`0x34000360`), "HeadingInDegrees" (`0x340002C8`), original facing (`0x340003E7`); Zatanna's pet
`0x34000652`: `Forward(WithHeading(TestPosition, Heading(TestPosition) + ChosenAngle))` = a direction rotated by an
angle; 0x2E/0x0B with 0x44 build cone / circle offsets (`0x340002C8`, `0x340005B5`, `0x34000278`).

### 5.4 Entity lists (per-script value lists) (C)

Storage: the **script component** of SELF (`entity+0x8C`, `0xAA1A60`), array at +0x74 (count +0x7C) of 0x20-byte
entries; each entry is keyed by the **16-byte key of the running script instance** (`ctx->vfunc+0x14`), and holds a
dynamic array of 16-byte typed values (+0x10 data, +0x18 count). So each script instance on an entity has exactly
**one list** (no list id in the nodes); the elements are typed values (IIDs in practice); all elements must have the
type of the first one (an add of another type is ignored).

| id | vt | Unpack | exec | semantics |
|---|---|---|---|---|
| 0x100000C1 | 0x15FA0C8 | (only `next`) | `0x97D410` -> `0x976CF0` | **ClearList()**: removes this instance's list entry |
| 0x100000C2 | 0x15FB394 | `B O value` | `0x9803D0` -> `0x979FF0` | **AddToList(value)**: appends (duplicates allowed); creates the list on first use |
| 0x100000C3 | 0x15FB364 | `B O out` | `0x992DA0` -> `0x974110` | **ListCount(out int)**: 0 when no list |
| 0x100000C4 | 0x15FB304 | `O value` (predicate) | `0x980320` -> `0x96EAC0` | **IsInList(value)** |
| 0x100000C5 | 0x15FB334 | `B O out, O index` | `0x992CF0` -> `0x973F60` | **ListItem(out, index)**: no bounds check in the client (index must be < count); no list -> null value |
| 0x100000CD | 0x15FB3C4 | `B O value, r1 ordered` | `0x980460` -> `0x973E80` | **RemoveFromList(value)[ordered]**: removes the first equal element; r1 = 1 keeps the order (`0x971340`, shift down), 0 swaps with the last (`0x9712C0`) |
| 0x100000F9 | 0x15FB424 | `B O value, O out index` | `0x988920` -> `0x974030` | **FindInList(value, out index)**: index of the first equal element, else -1 |

Typical use: `FindTargetsInRadius` + `GetDetectedTarget` loop, then `AddToList(TargetIID)` / `IsInList` to hit each
target once (`0x3400000B`, `0x34000043`, `0x340001B8`, `0x34000218`); team-wide effects iterate a list with
`ListItem(TeamMemberIID, ArrayIndex)` while `ArrayIndex < ListCount` (`0x34000107`, `0x340002AF`, `0x340002D1`).
**Server:** keep `inst.lists = []` per script instance (cleared when the instance ends); exact semantics above.

### 5.5 Teams (C unless marked)

- **Team of an entity** (`0x854050`): the attribute component's int at +0x4C (`0xAA0DC0` component), else property
  **`0x1000009C`** (PVP team); when -1, the team of the entity's owner (`0x8631A0`). Relation of two team ids
  (`0x853380`): same id = 4 (friendly), either is 0 = 1 (neutral), otherwise 2 (hostile); -1 on either side = 2.
- `0x1000007B` **GetTeam(entity, out int)** (vt 0x15FB8A4, exec `0x993690`): writes the team id above. 62 nodes,
  e.g. `GetTeam(SELF, MyTeam)`, `GetTeam(SELF, ThrowersTeam)` before `SetTeam`.
- `0x1000007E` **SetTeam(entity, team)** (vt 0x15FBE78, no exec): server only; thrown props and weapons take the
  thrower's team (`0x34000161`, `0x34000177`), environmental objects go back to the neutral team (`0x340003F6`).
  **Server:** set the entity's team (property `0x1000009C` and the server's own relation table) and send the property.
- `0x10000082` **GetTeamMember(out IID, index, team)[relation mask]** (vt 0x15FB844, Unpack `0x983EC0`, exec
  `0x9934F0` -> `0x97D470`): the roster manager (`game+0x68`, `0xA1BA20`) has per (entity kind, team) member lists.
  With `team = -1` the teams are walked in order and the index counts across all teams whose relation to SELF's team
  is in the mask (r4: 4 friendly, 2 hostile, 1 neutral; data 7 = all, 2 = enemies). Returns the index-th member or a
  null IID. Kind = SELF's entity kind (`(def+0x7C)+0xC` u16), so champions enumerate champions (P for "kind").
  Data: `GetTeamMember(TeamMemberIID, ArrayIndex, AppliedToTeam)[7]` (`0x34000107`), `(LoopingIID, LoopIndex, -)[2]`
  (`0x340001C6`, `0x34000253`: all enemy champions).
- `0x10000083` **TrackTeam(team)[subscribe]** (vt 0x15FBC30, Unpack `B r1 @+0xC, O @+0x10`, exec `0x993A40`):
  r1 = 1 calls `roster->vfunc+0xC(SELF, team)`, 0 calls `+0x10` (unsubscribe). P: SELF gets the roster events of that
  team (a member joined / left / died), used by the team-aura scripts (`0x34000107` family) to re-apply their effect
  to new members. **Server:** keep a subscription set; raise the team events on the subscribed instances (event ids:
  open, see the transitions of `0x34000107`).

### 5.6 Predicates

| id | vt | Unpack | exec | semantics | conf |
|---|---|---|---|---|---|
| 0x100000EF | 0x15FBAB4 | `O entity @+8` | `0x9939D0` | **EntityExists(e)**: the IID resolves and `entity+0x118` flags are not "0x40 without 0x8" (0x40 = being removed / dead object, 0x8 overrides) | C |
| 0x10000072 | 0x15FB9C4 | `O e, r4 @+0x20 class` | `0x993780` | **IsClass(e)[DID]**: `entity->def(+0x108)->did(+8) == r4` (0x40 template DID, e.g. `0x40000208`, `0x40000AA6`) | C |
| 0x1000001C | 0x15FCFD8 | `O e` | `0x995290` | **IsTargetable(e)**: flag attribute **`0x10000029`** of e (default true, `0x974940` -> `0x973730`) | C |
| 0x100000DC | 0x15FB964 | `O e, r4 mode` | `0x993710` | **IsInControllerMode(e)[mode]**: `entity+0x54` (the active physical/locomotion controller) exists and its type `+0x2C == r4`; values 66, 71, 74; **74 = attached / carried** (the same object `0x100000E8` reads) | C code / P names |
| 0x1000003C | 0x15FAFA4 | `O a @+8, O b @+0x20, r1 @+0x38` | none (`0x4FB4C0`) | server only: **CanSee(observer, target)[flag]** (P): `OR(CanSee(SELF, T), CanSee(StarroIID, T))` gates target choice in `0x3400053A`, `if CanSee(SELF, Target) then AIMoveTo...`; also `AND(IsValid, IsAlive, CanSee(SELF, T)[1])` | P |
| 0x10000020 | 0x15FADC4 | `B O O r4 r4 r4 r1 r1 r4 O` | none | server only: **GetBestPerceivedTarget(unit, out IID, -)[2, kind mask, 0, 1, 1, 0]** (masks 8, 0x14118); see `units-and-ai.md` 5.3. Despite its `B` it is used both as an action and as an IfThenElse condition: as a condition it must return "found" | P |
| 0x10000173 | 0x15FB244 | `r4 @+0x20 fraction, O e @+8` | `0xAB40B0` | **IsOnScreen(e)[fraction]**: client camera test (projects the entity with the view matrix `0x1B724C0..`, compares with `fraction * viewport size` `0x7AFE40/0x7AFE50`); values 0.5, 0.35. Not "RandomChance". Client-only meaning: a server can answer true (the only users, `0x3400053C` and `0x34000600`, are not player skills) | C |
| 0x1000003D | 0x15FB994 | `O e, r1 viaOwner` | `0xAB47C0` | **IsLocalPlayer(e)[viaOwner]**: r1 = 1: e's controller is the local player (`0x864D60`); 0: e or its owner chain is the local player (`0x863040`). Server equivalent: "e is controlled by the player this script runs for" (P) | C client / P server |
| 0x100000AE | 0x15FA368 | (no fields) | none | server only; `T7: S0,S5 -> S3 on AND(Event 0x10000035, 0x100000AE())` in a missile script (`0x34000167`): P "the missile has no target / target lost" | P |
| 0x100000F3 | 0x15FA458 | (no fields) | none | server only, 1 use (C1); no evidence | ? |

### 5.7 AI and handler nodes (server only unless an exec is listed)

- `0x1000004F` **AIMoveTo(position, range, target, unit, out handle)[flag]** (no exec; Unpack `0x982EC0`, stream
  +0xC, +0x24, +0x54, +0x3C, r1 @+0x84, +0x6C): path the unit to `target` (or `position` when target is null) until
  within `range`; the handle is released with `0x10000081` StopAction (exit chains: `0x10000081(SELF,
  AttackingMoveToHandle)`). C layout, P meaning (see `units-and-ai.md` 5.3).
- `0x1000000D` **SetAITarget(target, unit)[mode]** (Unpack `0x983140`: r4 @+0xC, target @+0x28, unit @+0x10): mode 1
  then 0 starts auto-attacking (`0x3400053A`), mode 0 alone = taunt / force target (`0x3400035D` TauntTarget,
  `0x3400017F` EffectSource). P.
- `0x10000139` **SetAIEnabled(unit, handle)[enable]**: crowd-control status scripts suspend the AI (`[0]` on enter,
  `[1]` on exit with the same `AIHandle`: `0x340000C6`, `0x340000E0`, `0x340000EE`). Server: a per-unit counter of
  suppressions keyed by handle. P.
- `0x10000004` **GetVisionRange(out f32, entity)[addBonus]** (vt 0x15FAEB4, Unpack `0x982B30` stream out @+0x24,
  entity @+0xC, r1 @+0x3C; exec `0x992740` -> `0x9CFC40` / `0x9CFCA0`): attribute component float +0x8C, else property
  **`0x10000133`** (vision radius, default -1); r1 = 1 adds attribute `0x10000642` (vision bonus, P). Not a setter (C).
  Data: `(PerceptionRange, SELF)[0]` before vision-shrink effects (`0x340006E9`, `0x340002BD`).
- `0x1000014D` **AddReactionHandler(entity, out handle)[0x3F DID]** (vt 0x15FC89C, Unpack `0x9AAB70` B, entity @+0x10,
  r4 @+0xC, out @+0x28; exec `0x994500` -> `0x9754A0` on the entity's handler component `entity+0xB8`
  (`0xAA10B0`)): registers a **0x3F record** (variable block + one node chain, an event-handler snippet: `0x3F000003`,
  `0x3F000006`, `0x3F000009` missile-collision handlers, `0x3F000007` damage reduction) and returns its handle. Used on a
  spawned wall (`0x340003F1`: `SpawnEntity(... WallIID)` then `AddReactionHandler(WallIID, ReactionHandle)[0x3F000006]`)
  and on missiles (`0x340002C1`, `0x34000743`). C (mechanism) / P (when the handler fires: on the event its chain
  handles, e.g. a missile collision with the owner).
- `0x1000014C` **RemoveReactionHandler(entity, handle)** (vt 0x15FD1B4, exec `0x995F10` -> `0x9755F0`): removes by
  handle and zeroes the handle variable. C.
- `0x10000168` **AttachHandlerScript(out handle, params...)[start, 0x3F DID, event id, count]** (vt 0x15FE33C, Unpack
  `0x9CB7D0`: r1 @+0xC, r4 @+0x10, O @+0x18, r4 @+0x14, list of 0x30-byte (var, value) pairs @+0x30; exec `0x9C76C0`):
  r1 = 1 starts the 0x3F record on SELF's script component with the event id (`0x100000ED`) and the listed variables
  copied in (`0x975850`), writing the handle; r1 = 0 stops the handle (`0x96F9C0`) and zeroes it. Only `0x340005D5`
  (`[1 0x3F000007 0x100000ED 3]` with the DamageReduction stats). C mechanism / P event meaning ("about to take damage").
- `0x10000002` (node, no fields; vt 0x15FA3C8, exec `0x988A60` -> `0x976B30`) **EndThisScript()**: finds the running
  instance (key = `ctx->vfunc+0x14`) in SELF's script component and, if it is running (state 2), delivers event
  `0x10000009` when the script listens to `0x10000007` (cleanup), then removes it (`0x96C5D0`, `0x96EB00`). C (P on the
  two event ids' names). Users `0x3400053C`, `0x340006FF`, `0x3400072D`, `0x340007EC`, `0x34000838`.

**Server:** 0x1000014D/14C/168 need "handler" instances: a 0x3F record runs like a tiny script whose chain is run when
its event is raised on the entity it is attached to. Implement after the missile collision path.

### 5.8 Animation-graph variable

`0x1000002F` **SetGraphVariable(value, entity)[graph var id, notify]** (vt 0x15FD424, Unpack `0x9871A0`: r4 @+0x24
first, value @+0xC, entity @+0x28, r4 @+0x40; exec `0x9CEAC0`): when the entity's animation graph (entity+4) is
active (`vfunc+0x50`), sets Havok-behavior variable r4 (`0x10000936` AnimationSpeed f32 default 1, `0x100001BF`
TargetHeading f32) to the value (`vfunc+0x5C`); when the second r4 is non-zero (`0x100001F4`, an int property default
-1) it also builds a graph-event message (`0x10000232` record) and sends it through `0x588A00` (P: replicate to the
other clients). C for the set; P for the second part. 19 nodes, e.g. animation speed scaled by attack speed in basic
attacks (`0x34000131`, `0x340000DF`). **Server:** the client runs this itself when it runs the scriptlet; a server must
send the same graph variable to every client (the properties `0x10000936` / `0x100001BF` are object-table f32 with
net = 0, so most likely via a scriptlet / graph event; open).

### 5.9 The unknown node classes

Stream-order fields; "uses" = nodes / scripts in the 875 trees.

| id | vt | Unpack | exec | best reading | conf |
|---|---|---|---|---|---|
| 0x100001AF | 0x15FCE58 | `B O entity, O -, r4 @+0x3C` (0x982850) | none | **ResetSkillCooldown(entity)[slot]** with slot 0 (basic attack): it follows the self-buff ApplySkill of every "empowered next basic attack" skill (Wonder Woman Protection, Superman Kryptonian Might, Hawkgirl Haymaker, Zod Shield Breaker, Atrocitus Crimson Slash, Gaslight Joker Fetid Cleaver, Atomic Wonder Woman Smite, Deadshot One Shot One Kill, Supergirl Worldbreaker, Nightmare Robin Impale, Nightmare Batman Bat Swarm, Deathstroke Healing Factor), 14 / 13 | P |
| 0x1000011E | 0x15FC1DC | `B O O r1 r4` (0x982DD0) | none | `(-, EffectSource)[1 46] / [1 45] / [0 0]` in one status (`0x34000363`), next to a `HiddenHandle` modifier on `0x100007BF` (visibility flags): P **reveal / hide SELF to EffectSource's team** (r1 on/off, r4 a reason id) | P |
| 0x100000E5 | 0x15FDA8C | `B O O r4 @+0x3C r1` (0x988140) | none | `(-, -)[1 1]` after a trigger cooldown timer (Green Arrow Bullseye `0x3400040C`) and after `0x10000042` (`0x340004A4`): P "usable object / trigger re-armed" | P |
| 0x1000005C | 0x15FC32C | `B r4 @+0xC value, O entity @+0x10` (0x985580) | `0x993EB0` | **SetProperty_100004FF(entity)[value]**: sets enum property **`0x100004FF`** (net shared, enum table `0x30000153`) through `0x54FC60`; used `[0]` on a thrown target (`0x340001BF`). Server: set the property and send it | C (meaning of 0x100004FF ?) |
| 0x100000C7 | 0x15FC11C | `B O entity, O other, r4 a, r4 b, r4 c` (0x984D60; a @+0x3C, b @+0x40, c @+0x44) | `0x993E20` | **UINotify(entity, other)[a, b, c]**: calls the GM_UI object (`game+0x1C`, `0xA1B320`) `vfunc+4(entity, &other, c, b, a)`; values `[126 1 2]` (`0x340000E6` mark), `[87 5 2]`, `[89 9 2]` (recall `0x3400000A`). Client-local HUD effect; a server has nothing to do unless the UI call maps to a message (open) | C call / P meaning |
| 0x100001B8 | 0x15FBFFC | `B O entity, r1 @+0x24` (0x983D70) | `0xAB48E0` | **PushRootCounter(entity)[on]**: if the entity resolves, increments (1) or decrements (0) the counter at `root(+0x90)+0x74` (`0x85EBF0`). Same effect as message **0x2198** (handler `0xA1A540`), sibling of 0x2044. Used with `0x100001A9` SetHidden in one Stolen Power (`0x34000304`). Server: send 0x2198 `(IID, u8 on)` to the affected player | C |
| 0x10000108 | 0x15FBAE4 | `B r4 @+0xC, O entity @+0x10, O @+0x28` (0x984250) | none | `(SELF, -)[9]` at recall start, `[8]` at recall end (`0x3400000A`), after a Stolen Power camera spawn (`0x3400019D`): P **RecordPlayerAction / statistic(entity)[action id]** | P |
| 0x10000174 | 0x15FC9E4 | `B O O {r4}` (0x9C4250) | none | 1 use (`0x34000543`): `(obj, SELF)[1 0]` | ? |
| 0x100000A1 | 0x15FC02C | `B O a, O b` | none | Atomic Joker The Punch Line (`0x340004DE`): `(HeadIID, SELF)` after spawning the head; exit `(-, SELF)` if not smitten: P **SetOwner/link(a, b)** or **DestroyLinked** | P |
| 0x10000172 | 0x15FBE18 | `B O O` | none | 1 use (`0x34000543`) with 0x1000010D / 0x10000155 | ? |
| 0x100001B9 | 0x15FD6F8 | `B O` | none | Solomon Grundy Born on a Monday (`0x34000662`), after "treat as dead" modifiers and `0x10000042`: P **BeginFakeDeath / hide vital bar** | P |
| 0x100000DA | 0x15FD5A4 | `B O O` | none | `(SELF, SELF)` before an AoE punch (`0x340001D6`): ? | ? |
| 0x100001AD | 0x15FD3C0 | `B O entity @+0x10, O @+0x28, r4 status @+0xC` (0x9870F0) | `0xAB4D30` -> `0xA0F050` -> `0x8C2790` | **DisplayFloatyStatus(entity)[status id]** (`GM_Vitals.RecvNotice_DisplayFloatyStatus`), id 14 (Wonder Woman Blocking Bracers, Nightmare Superman Condemn); not in spectator. Same path as messages **0x44** / **0x20BD** (u64 IID, u32 id). Server: send 0x20BD `(target IID, 14)` | C |
| 0x10000135 | 0x15FD330 | `B O` | none | in a returning missile before its damage (`0x340002C1`, `0x34000743`): P "missile returned to its owner" notify | ? |
| 0x1000010E | 0x15FD300 | `B O` | none | 1 use in a status exit (`0x340000EE`) after `0x100000C8(-)[0]`: P "end untargetable" pair | ? |
| 0x10000191 | 0x15FC86C | `B O entity, O position, O out` (0x985CF0) | `0x9B65B0` | **PositionQuery(entity, position, out)**: resolves the position (`0x992470`), calls `0x4FB400(entity, frame, out, 0, 1.0f)` and stores the result (`0x48D0F0`); Zatanna's pet (`0x34000652`) uses it on a candidate position. P: snap / validate a position for the entity (navmesh) | C call / P meaning |
| 0x1000009E | 0x15FCB00 | `B O entity, O IID, r1 @+0x3C` (0x9863C0) | `0x9946F0` | calls the component at `entity+0x80` (`0xAA05A0`) `vfunc+0x60(&IID, flag)`; 1 use (C1). P: link / unlink entity and IID | C call |
| 0x100001A7 | 0x15FA8A8 | `B r1 @+0xC` | none | Raven Blessing of Darkness (`0x34000680`): `[1]` on graph enter, `[0]` on exit, a lifesteal graph: P **EnableLifestealTracking[on]** (damage events carry AmountLifeStolen) | P |
| 0x100001B3 / 0x100001B6 | 0x15FAFD4 / 0x15FAD64 | `B O O r1 r4` / `B O O` | none | **SetLane(entity, lane)[flag, 0]** / **GetLane(entity, out)**: lane assignment statuses (`0x340007D6`, Top / Mid / Bot) | P |
| 0x10000152 | 0x15FC47C | `B O out` | none | **GetMatchTime(out)** in an update chain (`0x340007BE`) | P |
| 0x10000087 | 0x15FC2FC | `B O O r1` | none | **SetUsageObject(user, object)[on]** (`0x3400012D`) | P |
| 0x10000090 | 0x15FC05C | `B O entity, r4 @+0x24, r1` (0x984A50) | none | **SetObjectState(entity)[state, flag]** on pickup / throw props (`0x34000116`, `0x34000161`, `0x34000162`, `0x3400016C`): values 8, 17, 19 | P |
| 0x100000E4 | 0x15FC83C | `B r1 @+0x24, O entity @+0xC` (0x9880C0) | none | **SetPhysicsEnabled(entity)[on]**, same props and the lift / throw scripts (`0x340001BF`, `0x340001C4`) | P |
| 0x1000010D | 0x15FD6C8 | `B O entity, r4 @+0x24, O @+0x28` (0x983E80) | none | `(-, -)[0x2E0004E6]` (a world state DID) in `0x340000EE`; `(obj, SELF)[0]` in `0x34000543`, `0x34000778` (Arcane Harley Glamour): P **SetWorldState(entity)[0x2E DID]** | P |
| 0x10000063 | 0x15FC65C | `B r4 @+0xC, O @+0x10` | none | `(-)[0x1000018B]` after a HealthLock modifier in a heal-over-time (`0x34000598`); `0x1000018B` is an enum property (table `0x30000028`): P **SetEnumProperty(entity)[property]** | P |
| 0x100001A5 | 0x15FB7B4 | `B O O` | none | **GetLatencyWindow(entity, out f32)** (Arcane Supergirl Breath of Rao `0x3400054E`: `now - LatencyWindow - TriggerTime` for charge time): the caster's network latency; server: 0 or the measured RTT/2 | P |
| 0x10000186 / 0x10000189 | 0x15FA098 / 0x15FA968 | (no fields) | none | one script (`0x340007E2`): 0x189 after GetLevel before re-initialising the skill ranks, 0x186 in a second graph: P level-up bookkeeping | ? |

### 5.10 The `tools/script_coverage.py` entries explained

- **`predicate builtin:0x1`**: an Assign sits inside a condition list (AllOf / AnyOf / IfThenElse condition). In the
  client that is legal: slot 9 of an action runs it and returns its `next` chain's result, or **true** (5.1). The
  runtime's `predicate()` must accept any action: `execute(n)` then `return run(next) if next else True`.
- **`predicate builtin:0x4`**: EventFilter / IsEventPending (5.2), not implemented.
- **`builtin:0x5`**: an AnyOf used as a chain node (selector over its child chains, 5.1); `execute()` must run it as
  `any(run_chain(c) for c in children)` (stopping at the first true). Same for `builtin:0x9` (sequence).
- **`LaunchMissile of a spawned entity (SpawnEntity)`**: `_missile` finds no `0x40` class in the node's values (the
  missile is an entity created earlier by SpawnEntity and passed as an operand); this needs SpawnEntity (another
  section 4), not a new node.
- **3 FileNotFoundError**: `0x3400077A` (Arcane Harley Quinn basic attack, skill `0x480012F2:0`), `0x34000777` (Arcane
  Harley Quinn Spiteful Sprite, `0x480012F2:5`) and `0x340007A2` (Arcane Zatanna Mage Hunter, `0x48001000:5`) have no
  tree in `data/script_trees`: the decoder's record finder rejects their headers (fix A of
  `script-nodes-complete.md`; `0x340007A2` also starts with `3 | 1 | 0 | 0 | 0x1000002D`).
- **1 RecursionError**: Atomic Poison Ivy Toxic Growth `0x34000357` (`0x48000883:5`). `Region.enter -> finished ->
  check -> enter` recurses through completion transitions (`S0 -> S1` on `AND(TimerExpired(CombatIdleTimer),
  IsAlive(SELF))`, `S1 -> S2` on `IsTrue(ShieldDown)`, `S2 -> S0` immediately) in the same tick; the 500-step guard
  is reached after Python's 1000-frame limit (4 frames per step). Two fixes: (1) evaluate completion / predicate
  transitions **once per state per update** (defer `finished` to the next tick or iterate instead of recursing);
  (2) TimerExpired semantics (5.1) so that the loop behaves as in the client.

### 5.11 What to implement first in `ics` (from the counts in the coverage run)

1. VM semantics (5.1): action-in-condition = run + next result, AnyOf/AllOf as chain nodes, While cap 1025,
   TimerExpired of an unset timer = true, `0x0C` expression = x - 1, `0x15A88E0` = PostEventDelayed, frames with yaw.
2. Expressions 0x27, 0x13, 0x10, 0x04, 0x1E, 0x37, 0x40, 0x46, 0x41, 0x0D, 0x44, 0x2E, 0x0B, 0x35, 0x1A, 0x14, 0x01,
   0x0A, 0x11, 0x07, 0x3C, 0x19, 0x21, 0x05, 0x45, 0x47, 0x10000003 (all exact, 5.3; one table-driven evaluator).
3. Entity lists (7 nodes, 5.4) and team nodes 0x1000007B / 0x10000082 / 0x1000007E (5.5).
4. Predicates 0x100000EF, 0x1000001C (attribute 0x10000029), 0x10000072, 0x100000DC, builtins 0x14 / 0x18 / 0x15 /
   0x16 / 0x17 / 0x04.
5. Message-backed nodes: 0x100001AD -> 0x20BD, 0x100001B8 -> 0x2198, 0x1000005C -> property 0x100004FF.
6. AI and handler nodes (0x1000004F, 0x1000000D, 0x10000139, 0x10000020, 0x1000003C, 0x1000014C/14D/168,
   0x10000002) together with the minion brain of `units-and-ai.md`.
7. The `?` rows of 5.9 are single-script nodes (C1-C3): stub as no-ops that log, until a tester sees the effect.

## 6. Main gaps (all sections)

- **Server-only formulas:** mitigation, crit damage and lifesteal have no client code; the attribute-rules record
  (stacking factors, soft caps, panel list) was not located in the packs. The forms in 2 A.5 are assumptions.
- **Runtime hashes:** the event-parameter hashes behind OnCastSignal (`[0x186A6A0]`) and the attribute-id parameter
  (`[0x186A664]`) are set at run time; a breakpoint with `tools/diag.py` would read them.
- **Component classes not identified:** the attribute component behind `[ent+0x84]` (vfuncs +0x4C..+0x60), the
  vitals methods +0x4C..+0x6C and the `[entity+0x90]` component that HasStatus queries.
- **Movement wire details:** which movement-mode byte means dash / knockback / knockup / carried, the wire form of
  attachment, the extra fields of lobbed and tethered missiles, the hotspot flag bytes.
- **Status details:** the three r1 of ApplySkill, the `0x8D` form that stops one scriptlet run by instance, the order
  of the icon message fields after the StringInfo.
- **Single-script unknowns** (0x10000174, 0x10000172, 0x100000DA, 0x10000186, 0x10000189, 0x100000F3, 0x10000135,
  0x1000010E; weak readings of 0x1000011E, 0x10000108, 0x10000075, 0x10000005, 0x10000105, 0x1000017F, 0x10000195):
  implement as logging no-ops until a tester sees the effect.
- **Records without a tree:** 0x3400077A, 0x34000777, 0x340007A2 (decoder fix A of `script-nodes-complete.md`); the
  Toxic Growth recursion (0x34000357) needs the transition fix of 5.10.
