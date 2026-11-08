# Server-script node and expression types: names (static analysis, 2026-10-21)

Client `InfiniteCrisis.exe` (image base 0x400000), Ghidra/REA + capstone + the Unicorn emulator of `tools/script_decoder.py`. Scratch scripts were not added to the project. Usage counts come from the 826 decoded trees in `data/script_trees` (keyed by the class vtable, so ids that collide between registries are kept apart).

## Where names could come from, and what was found

- **RTTI:** the exe has 1562 `.?AV`/`.?AU` type descriptors, all from libraries (Havok `hk*`/`hcl*`, Scaleform `G*`, CryptoPP, xerces, Lua `hks`). The game and engine classes (script nodes, DB objects, `gm*`) were built without RTTI: **no class names for any node type.**
- **Registration:** every static initializer in 0x13A0000-0x13D0000 passes only `{type, factory, size}` to the registry insert 0x45FA20 (a hash map keyed by type; no string argument). There are four registries, told apart by the getter called before the insert: node registry **0x44E410** (365 types: builtins 0x01-0x18 and actions 0x10000002-0x100001B9), expression registry **0x45FB30** (74: 0x01-0x47 and 0x10000002-0x1000000F), a value registry **0x45FAA0** (6, never used by the scripts) and the graph registry **0x44E240** (1 = graph, 2 = state). Ids collide across registries (0x10000002 is an action, an expression and a value type).
- **Vtables** (node classes): [0] destructor, [5] Unpack, [6] Pack, **[7] GetType** (`mov eax, type; ret`, one per class), [10] **client-side execute** (190 action/builtin classes have one; the other 161 use the empty 0xAB4D80 or 0x4FB4C0), [11] clone / runtime instance, [12] destructor. Expression classes: [10] evaluate. No describe/print/name method exists in any of them, and no class-name, assert or field-name strings are referenced (the only script source paths are `script/shared/scriptlet/ScriptletScriptNode.cpp`, `script/shared/exec/ExecuteScriptNode.cpp` and `script/DBScriptTable.cpp`).
- **Game data:** no pack holds node names (the 0x30 enum tables and 0x33 name tables only name scriptlet keys, graph events and variables; a scan of all 616 packs for node-like names found none).
- **What does tie classes to names (column conf = X):** (1) the client execute (vtable slot 10) of some classes sends a named client notice (`GM_UI.RecvNotice_...`, `GM_MapManager...`, `GM_Tutorial...`, `GM_Upgrade...`) or calls a named function (`gmUIStateMachine::LoadWrapperOnlyRPs`); (2) two classes run scriptlet keys whose names are the action's class name: `_HFSM_DestroyEntityAction` (0x100001E0) + `_HFSM_DestroyEntityAction_Optional` (0x10001128) in **0x10000010**, `_HFSM_BehaviorRaiseEventAction` (0x100001E3) in **0x1000004E**; the scriptlets `_HFSM_TargetHitAction_PhysicalReaction` / `_HitFlash` name the hit action (0x1000007A, by its data); (3) the expression evaluators are plain arithmetic or CRT calls (`__libm_sse2_cosf`, `pow`, `ceil` ...), so their operation is exact even without a name.
- So **no node type has its original name in the exe**. The names below are the operation (exact for expressions and for the X rows), else inferred from the decoded scripts (operand variable names, literal values, neighbours) and the client code. Confidence: **X** client string / scriptlet name / exact code, **H** high, **M** medium, **L** low, **?** no evidence (mostly classes no player script uses).

**Correction for the project:** `0x10000010` is not `Delay`. Its client execute plays `_HFSM_DestroyEntityAction` on the target and destroys it (the f32 is the delay before removal, the r1 a flag). Missiles end with `0x10000010(SELF)[0 1]`. `0x1000001D` (called ApplyEffects) is the damage node (damage, target, crit roll, slot, source, out DamageSuccess, SourceEntityDID; value 5 = damage type 1/2/3).

Fields: `sig` is the Unpack signature (B base/next node, O operand = value|source|slot, rN raw bytes, {..} helper). `ops` are the operand slots in order with the most common variable names in the scripts (SELF = 0x4DD4 source 2; ctxNN = a source-2 operand, a property of the owner); `values` are the raw fields in order with their most common values.

## Graph registry 0x44E240 (record level)

| id | vt | name | conf | Unpack | notes |
|---|---|---|---|---|---|
| 0x1 | 0x15A8218 | Graph (composite state) | H | 0x44F140 | 3 chains, optional locals, child states, transitions (Unpack 0x44EB50 per transition), link table |
| 0x2 | 0x15A7F98 | State | H | 0x44F060 | enter / update / exit chains + optional locals |

## Builtin nodes (node registry, ids 0x01-0x18)

| id | vt | size | name | conf | uses (nodes/scripts) | sig | fields seen | notes |
|---|---|---|---|---|---|---|---|---|
| 0x01 | 0x15A89C0 | 0x28 | Assign | H | 2868/591 | `B O r4` | ops: 0=TargetIID/FacingIDVariable/NeedCooldown; values: [2/23/41] | B O r4: variable = child expression (r4 = the child's expression type, read at 0x460502) |
| 0x02 | 0x15A8880 | 0x3C | StartTimer | H | 345/220 | `B O O` | ops: 0=TickTimer/BuffTimer/DelayTimer, 1=TickDuration/DelayDuration/BuffDuration | B O O: (timer variable, seconds) |
| 0x03 | 0x15A8764 | 0xC | ExpressionCondition | H | 1639/476 | `r4` | values: [34/3/27] | r4: predicate = the child expression (r4 = its type) is true |
| 0x04 | 0x15A87C4 | 0x10 | EventFilter? | L | 11/9 | `r4 r1 r1` | values: [0x10000009/0x10000002/12 ; 1/3 ; 1/0] | r4 r1 r1: [event 0x10000009 / 0x10000002 / 0x10000012, flag, flag]; 11 uses in triggers |
| 0x05 | 0x15A8B0C | 0x18 | AnyOf (OR) | H | 772/468 | `{r4}` | values: [2/3/4 ; 6/10/3 ; 6/10/0x100000b1 ; 6/0x100000b1/3 ; 6/16/0x100000b1 ; 6/0x100000b1/0x100000a4 ; 9/10 ; 10 ; 10] | {r4}: count + child types; true if any child (events, predicates) is |
| 0x06 | 0x15A8794 | 0xC | Event | H | 3318/799 | `r4` | values: [0x10000006/0x10000009/0x10000008] | r4: the event id the transition waits for (0x10000006 applied, 0x10000003 removed, 0x1000001D skill used, 0x10000002 collision ...) |
| 0x07 | 0x15A8B68 | 0x1C | IfThenElse | H | 2380/567 | `{r4} r4` | values: [3/0xad2ce65 ; 0x10000034/1/7 ; 0/7/1 ; 0/1/7 ; 3/16/9] | {r4} r4: [3, then type, else type, always type, condition type]; project LIST |
| 0x08 | 0x15A8820 | 0x20 | TimerExpired | H | 309/221 | `O` | ops: 0=Timer/BuffTimer/DelayTimer | O: (timer variable) |
| 0x09 | 0x15A8ADC | 0x18 | AllOf (AND) | H | 1006/438 | `{r4}` | values: [2/3/4 ; 0x1000003e/10/6 ; 0x10000028/10/0x1000003e ; 0x10000029/0x1000001e/0x10000028 ; 0x1000001e/0x10000052/0x10000028 ; 0x10000052/10/0x1000001c ; 10/3/0x10000052 ; 5/3/10 ; 0x100000a4/5] | {r4}: count + child types |
| 0x0A | 0x15A890C | 0xC | NodeCondition (Not?) | M | 937/399 | `r4` |  | base node: wraps a predicate node; empty in 400 transitions such as 'S2,S3 -> S1 on builtin:0xa()'; the project treats it as NOT (false when empty) - recheck |
| 0x0B | 0x15A88B4 | 0x10 | Unk_B (B r4) | ? | 0/0 | `B r4` |  | unused |
| 0x0C | 0x15A8938 | 0x10 | DebugLog | H | 10/3 | `B {{r1 r4}}` | values: [38/46/22 ; 89] | B {u32 len + chars}: text such as 'Unloading Main HUD GFX' (UI flow script) |
| 0x0D | 0x15A8B98 | 0x1C | WhileLoop | H | 197/130 | `{r4} r4` | values: [2 ; 0x10000024/0x100000c5/7 ; 0/0x10000085/7 ; 3/0x100000ef/9] | {r4} r4: [2, body type, ..., condition type] |
| 0x0E | 0x15A8964 | 0x24 | Unk_E (B O) | ? | 0/0 | `B O` |  | unused |
| 0x10 | 0x15A89F0 | 0x20 | IsTrue | H | 684/328 | `O` | ops: 0=CriticalChanceRoll/NeedCleanup/DamageSuccess | O: (bool variable) |
| 0x11 | 0x15A8A50 | 0x3C | CopyVariable | H | 303/90 | `B O O` | ops: 0=HandleEffect01/HandleEffect02/HandleEffect03, 1=HandleForMember/NumDead/HandleEffect02 | B O O: (destination, source) |
| 0x12 | 0x15A88E0 | 0x28 | LoadConstant? | L | 7/6 | `B r4 O` | ops: 0=Delay/DelayRenderGap/PhasingDuration; values: [0x10000120/0x10000121] | B r4 O: (variable)[key 0x10000120 / 0x10000121]: DelayRenderGap, PhasingDuration |
| 0x14 | 0x15A8850 | 0x20 | HasEventParameter? | L | 7/5 | `O` | ops: 0=lit | O: (#parameter hash literal) |
| 0x15 | 0x15A8BC8 | 0x40 | Switch | M | 5/5 | `{r4} {r4} O` | ops: 0=Stack1/Hits1/LaneAssignment_Top, 1=Stack2/Hits2/LaneAssignment_Mid, 2=Stack3/Hits3/LaneAssignment_Bot, 3=Stack4/CurrentHitCount/LaneAssignment, 4=NumStars/Stack5, 5=EffectStackCount; values: [5/6/7 ; 0x10000103/0x10000034/0x10000018 ; 0x10000103/0x10000034/0x10000018 ; 0x10000034/0x10000103/0 ; 0x10000103/0/0x10000034 ; 0/0x10000103/0x100000ca ; 0/3 ; 4/0 ; 5] | {r4} {r4} O: case values..., selector; one child chain per case (LaneAssignment, NumStars) |
| 0x16 | 0x15A8A80 | 0x28 | SetBool | H | 67/24 | `B O r1` | ops: 0=PerformedAction/FirstTargetWasPredator/SecondTargetWasPredator; values: [1/0] | B O r1: (variable)[0/1] |
| 0x17 | 0x15A8990 | 0x24 | ClearVariable | M | 35/20 | `B O` | ops: 0=HandleForMember/HandleEffect05/TargetIID | B O: (variable) reset to empty (handles) |
| 0x18 | 0x15A8A20 | 0x38 | AreEqual | H | 19/9 | `O O` | ops: 0=SkillSlot1/SkillSlot2/SkillSlot3, 1=SkillSlot/WarningStateSafe/CONST_ScreenLanding | O O predicate: (a, b) |

## Expression types (expression registry 0x45FB30; evaluate = vtable slot 10)

Unary classes read one child (0x469E40), binary two (0x469EE0), ternary three (0x469FE0). The parent stores each child's type id as a value (e.g. `[3 2]` = variable, constant).

| id | vt | name | conf | uses | evaluate | evidence |
|---|---|---|---|---|---|---|
| 0x1 | 0x15A9558 | abs | X | 12/12 | 0x462950 | unary; cdq/xor/sub on ints, abs on floats (0x455150) |
| 0x2 | 0x15A8F18 | Constant | X | 2968/529 | 0x462040 | literal value |
| 0x3 | 0x15A9D38 | Variable | X | 4633/590 | 0x463D30 | O: variable read |
| 0x4 | 0x15A90C0 | min | X | 28/27 | 0x463DA0 | binary, less-than select |
| 0x5 | 0x15A97F8 | cross | X | 1/1 | 0x4640B0 | vector cross product |
| 0x6 | 0x15A94E8 | divide (/) | X | 197/158 | 0x462890 | binary, 0x457530 |
| 0x7 | 0x15A95C8 | sqrt | X | 2/2 | 0x4629D0 | sqrtss / sqrtsd |
| 0x8 | 0x15A98A0 | length | X | 37/34 | 0x462BF0 | vector length (sqrtss) |
| 0x9 | 0x15A9AD0 | ToUInt64 | X | 0/0 | 0x464400 | result type 6 |
| 0xA | 0x15A9168 | bitwise and (&) | X | 5/4 | 0x462350 | 0x454AA0 |
| 0xB | 0x15A96A8 | cos | X | 2/2 | 0x462B30 | __libm_sse2_cosf |
| 0xD | 0x15A9868 | normalize | X | 9/8 | 0x463FF0 | vector / length |
| 0xE | 0x15A99F0 | ToFloat | X | 71/50 | 0x464270 | result type 3 |
| 0xF | 0x15A91D8 | bitwise xor (^) | X | 0/0 | 0x462410 | 0x454D40 |
| 0x11 | 0x15A9360 | pow | X | 2/1 | 0x462A10 | __libm_sse2_pow |
| 0x12 | 0x15A9050 | >= | X | 73/47 | 0x462210 | greater (0x44F520) or equal (0x450890) |
| 0x13 | 0x15A92F0 | logical and (&&) | M | 58/25 | 0x4625F0 | children are comparisons; 0x44F500 test |
| 0x14 | 0x15A9B78 | RandomRange | X | 12/6 | 0x462EA0 | 0x452070: rand in [a, b] |
| 0x15 | 0x15A9B08 | modulo (generic) | M | 0/0 | 0x462E40 | 0x457C30: remainder for ints and floats |
| 0x16 | 0x15A97C0 | dot | X | 0/0 | 0x462CC0 | vector dot product |
| 0x17 | 0x15A93D0 | increment (++) | X | 255/158 | 0x4626B0 | add 1 |
| 0x18 | 0x15A96E0 | tan | X | 0/0 | 0x462B70 | __libm_sse2_tanf |
| 0x19 | 0x15A9B40 | decrement (--)? | L | 8/3 | 0x462E00 | 0x457BD0 (uses the ++ helper with a negation) |
| 0x1A | 0x15A99B8 | ToInt32 (truncate) | X | 5/5 | 0x4641F0 | cvttss2si, result type 1 |
| 0x1B | 0x15A8FA8 | != | X | 243/149 | 0x4620E0 | not equal (0x450890) |
| 0x1C | 0x15A9478 | subtract (-) | X | 197/125 | 0x4627D0 | 0x4538D0 |
| 0x1D | 0x15A9280 | bitwise not (~) | X | 2/2 | 0x462310 | 0x454980 |
| 0x1E | 0x15A9130 | clamp(x, lo, hi) | X | 26/23 | 0x463E80 | ternary, two less-than tests |
| 0x1F | 0x15A9210 | shift left (<<) | X | 0/0 | 0x462470 | 0x454E90 |
| 0x20 | 0x15A91A0 | bitwise or (/) | X | 0/0 | 0x4623B0 | 0x454BF0 |
| 0x21 | 0x15A9638 | ceil | X | 3/3 | 0x462AB0 | CRT ceil |
| 0x22 | 0x15A8F70 | == | X | 703/175 | 0x462080 | 0x450890 |
| 0x23 | 0x15A9440 | add (+) | X | 211/148 | 0x462770 | 0x4532A0 |
| 0x24 | 0x15A9328 | logical not (!) | M | 48/37 | 0x462530 | unary; 0x44F500; project: 'is zero' |
| 0x25 | 0x15A9248 | shift right (>>) | X | 0/0 | 0x4624D0 | 0x454FF0 |
| 0x26 | 0x15A9A28 | ToUInt32 | X | 90/32 | 0x4642C0 | result type 2 |
| 0x27 | 0x15A9BB0 | Select (cond ? a : b) | H | 262/33 | 0x462F00 | x = condition, y = then, z = else |
| 0x28 | 0x15A9830 | MakeVector(x, y, z) | X | 75/55 | 0x464160 | builds a vector3 |
| 0x29 | 0x15A94B0 | multiply (*) | X | 386/203 | 0x462830 | 0x453F50 |
| 0x2A | 0x15A9018 | < | X | 267/160 | 0x4621B0 | 0x44F9D0 |
| 0x2B | 0x15A9A98 | ToDouble | X | 0/0 | 0x4643B0 | result type 7 |
| 0x2C | 0x15A9520 | integer modulo (%) | X | 0/0 | 0x4628F0 | 0x454650 keeps edx (the remainder) |
| 0x2D | 0x15A9590 | log | X | 0/0 | 0x462990 | __libm_sse2_logf |
| 0x2E | 0x15A9670 | sin | X | 5/5 | 0x462AF0 | __libm_sse2_sinf |
| 0x2F | 0x15A9A60 | ToInt64 | X | 0/0 | 0x464310 | result type 5 |
| 0x30 | 0x15A9088 | <= | X | 60/26 | 0x462290 | less or equal |
| 0x31 | 0x15A90F8 | max | X | 89/85 | 0x463E10 | less-than select |
| 0x32 | 0x15A9718 | atan | X | 0/0 | 0x462BB0 | __libm_sse2_atanf |
| 0x33 | 0x15A9398 | negate | M | 21/20 | 0x462670 | multiply by -1 (0x456730 + mul) |
| 0x34 | 0x15A8FE0 | > | X | 110/84 | 0x462150 | 0x44F520 |
| 0x35 | 0x15A9600 | floor/round | M | 6/6 | 0x462A70 | sign-mask + 2^23 trick (0x4552B0) |
| 0x36 | 0x15A8F44 | GameTime | X | 113/62 | 0x462060 | current time |
| 0x37 | 0x15A9C58 | vector add | X | 32/25 | 0x465270 | component-wise add |
| 0x38 | 0x15A9C20 | TransformPoint(frame, localOffset) | M | 65/51 | 0x4650F0 | rotates the offset by the frame's orientation (0x4C79A0) and adds the position |
| 0x3C | 0x15A9980 | vector.z | M | 10/4 | 0x462DC0 | component read (no code) |
| 0x3D | 0x15A9948 | vector.y | H | 38/27 | 0x462D80 | component read |
| 0x3E | 0x15A9910 | vector.x | H | 37/27 | 0x462D40 | component read |
| 0x40 | 0x15A9C90 | Heading(vector)[degrees flag] | X | 19/17 | 0x462F50 | atan2 (fpatan) of a vector, degrees if the r1 flag |
| 0x41 | 0x15A9BE8 | RotateByHeading(vector, angle)[degrees flag] | M | 37/29 | 0x4653E0 | sin/cos rotation of a vector by a heading |
| 0x42 | 0x15A98D8 | lengthSquared | X | 9/8 | 0x462C60 | x*x+y*y+z*z |
| 0x43 | 0x15A9788 | RadToDeg | M | 0/0 | 0x463F80 | angle object built from radians, read in degrees (0xAF3C20, 0xAF29B0) |
| 0x44 | 0x15A9750 | DegToRad | M | 7/6 | 0x463F10 | angle object built from degrees, read in radians (0xAF29F0); used inside sin() |
| 0x45 | 0x15A9D00 | ForwardVector(frame) | L | 1/1 | 0x4644E0 | 0x4C7760 on a frame value |
| 0x46 | 0x15A9CC8 | PositionOf(frame) | L | 12/11 | 0x4644A0 | frame -> its position (virtual +8) |
| 0x47 | 0x15FABA4 | Unk_47(a, b, c) (lerp?) | ? | 0/0 | 0x9887F0 | three children, 0x980120; unused |
| 0x10000002 | 0x15FDD28 | GetAttribute(entity)[attribute] | H | 314/148 | 0x996D10 | r4 O r4: attribute property id, entity; reads the entity's attribute |
| 0x10000003 | 0x15FABDC | ScaleByLevel(level, base, delta) | X | 4/3 | 0x97D2F0 | base + (level - 1) * delta (flag: level 0 -> base) |
| 0x10000004 | 0x15FDCFC | GetAttribute2 | L | 0/0 | 0xAB4EB0 | same layout as 0x10000002; unused |
| 0x10000008 | 0x15FAAFC | Linear(x) | X | 0/0 | 0x97D1D0 | a * x + b (two r4 constants) |
| 0x10000009 | 0x15FAA8C | Logistic(x) | X | 0/0 | 0x97D0F0 | (1 / (1 + exp(-(x - x0) * k)) + c) * scale |
| 0x1000000A | 0x15FAAC4 | Step(x) | X | 0/0 | 0x97D180 | x > threshold ? a : b |
| 0x1000000B | 0x15FAB34 | Power(x) | X | 0/0 | 0x97D220 | pow(x - x0, p) + c |
| 0x1000000C | 0x15FAB6C | Power2(x) | X | 0/0 | 0x97D280 | same evaluate as 0x1000000B (another parameter layout) |
| 0x1000000F | 0x15FAA28 | Null | M | 0/0 | 0xAB4EB0 | returns the empty value (0x453270) |
| 0xC | 0x15A9408 | decrement, x - 1 | C | - | - | registered in the client after all (script-nodes-complete.md "Fix B"; was "server-only idiv?") |
| 0x10 | (none) | (server-only) or? | L | - | - | not registered in the client; children are comparisons -> logical OR |

## Value registry 0x45FAA0

Types 0x1, 0x10000001, 0x10000002, 0x10000004, 0x10000005, 0x10000006 (vtables 0x15A8D08, 0x160A5B0, 0x15FAA10, 0x160A5C8, 0x15FAA10, 0x15FA9F8). No decoded script uses them; probably the typed argument values of the variable blocks or the client HFSM bindings. Names unknown.

## Action / predicate nodes (node registry, ids 0x100000xx)

| id | vt | size | name | conf | uses | sig | fields seen | evidence / notes |
|---|---|---|---|---|---|---|---|---|
| 0x10000002 | 0x15FA3C8 | 0xC | SkillComponentAction_0002 | ? | 5/5 | `` |  | no fields; client code calls the skill/combat component (+0x8C) 0x976B30; 5 uses on enter C10 |
| 0x10000004 | 0x15FAEB4 | 0x40 | SetPerceptionRange | L | 6/6 | `B O O r1` | ops: 0=PerceptionRange/SkillRange/BasePerceptionRange, 1=SELF; values: [0/1] | (range, entity)[flag]; PerceptionRange/SkillRange before a detection hotspot C10 |
| 0x10000005 | 0x15FD2A0 | 0x28 | SetSkillAttached | L | 12/12 | `B O r1` | ops: 0=SELF; values: [0/1] | (entity)[0/1]; paired with 0x1000000B at the start of attach/grab skills |
| 0x10000006 | 0x15FB664 | 0x3C | Unk_0006(entity, entity) | ? | 0/0 | `B O O` |  | unused; client execute exists C10 |
| 0x10000007 | 0x15FD600 | 0x58 | StartCooldown | H | 466/346 | `B O r4 O O` | ops: 0=SkillCooldownDuration/CooldownDuration/ctx0xc4, 1=SourceEntityDID, 2=UseExistingCooldown/UseRemainingCooldown; values: [0xffffffff/1/2] | (duration, SourceEntityDID, use-remaining flag)[slot]; the project already runs it |
| 0x10000008 | 0x15FE30C | 0x4C | AddAttributeModifier | H | 248/196 | `B O O {r4}` | ops: 0=SELF/EffectSource/TargetIID, 1=SELF/TargetIID/PortalStartIID, 2=False/IsExposed/BasicAttackRangeAdd, 3=AttributeHandle/IsExposedHandle/SlowHandle, 4=EffectTarget/SELF/ctx0xd0, 5=False/Stat2_CurrentValue/WillRegen, 6=DummyHandle2/TargetableHandle/Stat2_Handle, 7=SELF, 8=False/HealthRegenRate/StrikeRes, 9=HealthRegenHandle/StrikeResHandle/StrikeDamageReflectionHandle, 10=-, 11=False/HealthLock/ResurrectAAPercent | (source, target, value, out handle, ...)[count, attribute 0x10.., op 6/9/10 ...] x N; client uses the attribute component (+0x84); paired with 0x10000033 on exit C10 |
| 0x10000009 | 0x15FD240 | 0x3C | StopVitalOverTime | H | 78/60 | `B O O` | ops: 0=SELF/LastTargetIID/TargetIID, 1=DOTHandle/VitalOverTimeHandle/DoTHandle | (entity, handle) on exit; stops a 0x10000040 (DOTHandle / VitalOverTimeHandle / HoTHandle); vitals component (+0x80) C10 |
| 0x1000000A | 0x15FA8D8 | 0x10 | EndSkill | M | 263/241 | `B r1` | values: [1] | [1]; exit of the skill's cleanup state in 175 scripts; skill component (+0x8C) C10 |
| 0x1000000B | 0x15FC8CC | 0x3C | SetSkillTarget | L | 14/12 | `B O O` | ops: 0=SELF, 1=TargetIID/SELF | (SELF, target) at the start of grab/attach skills; skill component C10 |
| 0x1000000C | 0x15FB0C4 | 0x28 | Unk_000C(value)[key] | ? | 0/0 | `B r4 O` |  | unused; client code references 0x10000017 C10 |
| 0x1000000D | 0x15FAEE4 | 0x40 | SetAITarget / Taunt | L | 10/9 | `B r4 O O` | ops: 0=TargetIID/TargetPosition/EffectSource, 1=SELF/ctx0xd0; values: [0/1/2] | (target, entity)[mode 0/1/2]: EffectSource, TauntTarget, TargetPosition; next to AI move nodes |
| 0x1000000E | 0x15FA6C8 | 0xC | BeginSkill | M | 246/240 | `` |  | no fields; first node of the cast state in 239 skills; skill component (+0x8C) C10 |
| 0x10000010 | 0x15FB5A4 | 0x2C | DestroyEntity | X | 137/115 | `B O r4 r1` | ops: 0=SELF/MarkerIID/PortalStartIID; values: [0/0x3e4ccccd/0.5 ; 1/0] | (entity, delay f32, flag); client execute runs scriptlets _HFSM_DestroyEntityAction 0x100001E0 and _HFSM_DestroyEntityAction_Optional 0x10001128 on the entity, then removes it. The project calls it Delay: it is not a wait C10 |
| 0x10000011 | 0x15FB694 | 0x3C | GetPosition | H | 209/143 | `B O O` | ops: 0=SELF/TargetIID/ShooterIID, 1=TargetPosition/EntityPosition/SourcePosition | (entity, out position) C10 |
| 0x10000012 | 0x15FBF6C | 0x28 | ClearProperty / StopEffect | L | 78/51 | `B r4 O` | ops: 0=SELF/AgentIID/TargetIID; values: [0x10000866/0x100000eb/0x100004d4] | (entity)[property or scriptlet key 0x10..]; on exits after VitalOverTime ends C10 |
| 0x10000014 | 0x15FBA24 | 0x20 | IsValidPosition | H | 38/29 | `O` | ops: 0=TargetPosition/TeleportPosition/TestPosition | (position) predicate C10 |
| 0x10000015 | 0x15FA758 | 0x8 | IsServerControlled? | L | 60/52 | `` |  | no fields predicate, used inside AND lists of skill transitions (with IsAlive...); client code resolves SELF and returns a component test C10 |
| 0x10000016 | 0x15FC44C | 0xBC | SpawnGeneratorUnit | L | 2/1 | `B r4 r4 r4 r4 r4 r4 O O O O O O r1 r4` | ops: 0=-, 1=-, 2=SELF, 3=-, 4=GeneratorIID; values: [4/0 ; 0 ; 0 ; 5 ; 0 ; 2/1] | (... SELF ..., out GeneratorIID)[...]; match-rule script 0x340002CF |
| 0x10000017 | 0x15FCF18 | 0x1C | Unk_0017 | ? | 0/0 | `{r4} {r4}` |  | unused C10 |
| 0x10000018 | 0x15FD668 | 0x78 | RemoveStatus | H | 245/144 | `B O O O r4 r4 r1 O` | ops: 0=TeamMemberIID/SELF/TargetIID, 1=HandleForMember/EOStartMarkHandle/EODestinationMarkHandle, 2=-, 3=Skill1; values: [0/4/1024 ; 0/0x48000880/0x480012bb ; 0/1] | (target, handle, -, slot)[flags, status 0x48.., 0/1]; removes what ApplySkill (0x10000027) started (HandleForMember...) |
| 0x10000019 | 0x15FA248 | 0x10 | OnCastSignal | H | 456/218 | `{r4} r4` | values: [0x1000000f ; 2/3/5] | trigger [0x1000000F, code]: 5 cast point, 3 cast finished, 2 done/interrupted C10 |
| 0x1000001A | 0x15FCDCC | 0x44 | VitalThreshold | M | 52/30 | `r4 O O r1 r1 r4` | ops: 0=VitalThreshold/HealthTriggerValue/ctx0xb8, 1=SELF/TargetIID/LoopingIID; values: [2/4/5 ; 0/1 ; 0/1 ; 1/4/6] | (threshold, entity)[vital 2=health 4/5/6.., compare, ...] trigger/predicate; vitals component; HealthTriggerValue, AutoVitalThreshold C10 |
| 0x1000001B | 0x15FD1E4 | 0x24 | CancelMovement? | L | 12/10 | `B O` | ops: 0=SELF | (SELF) after attach/teleport steps |
| 0x1000001C | 0x15FCFD8 | 0x20 | IsTargetable | L | 24/14 | `O` | ops: 0=SELF/TargetIID/TempTargetIID | (entity) predicate after IsAlive/IsValid/IsKind/IsHostile C10 |
| 0x1000001D | 0x15FC8FC | 0xDC | ApplyDamage | H | 348/258 | `B O O O r1 r1 r1 r1 r4 r4 O O O O O r1` | ops: 0=Damage/SkillDamage/BonusDamage, 1=TargetIID/LoopingIID/StoredTargetIID, 2=CriticalChanceRoll/WasCrit, 3=BasicAttackSkillSlot/SkillSlot3/BasicAttack, 4=EffectSource/SELF/RealHarley, 5=DamageSuccess/Success/DamageSuccessful, 6=SourceEntityDID; values: [0/1 ; 1/0 ; 1/0 ; 0/1 ; 1/2/3 ; 0/0x4800077a ; 1/0] | (damage, target, crit roll, skill slot, source, out DamageSuccess, SourceEntityDID)[..., damage type 1/2/3 ...]; called ApplyEffects in the project |
| 0x1000001E | 0x15FCEE8 | 0x20 | IsValid | H | 249/168 | `O` | ops: 0=TargetIID/StoredTargetIID/SELF | (entity) predicate C10 |
| 0x10000020 | 0x15FADC4 | 0x68 | CheckLineOfSight? | L | 6/1 | `B O O r4 r4 r4 r1 r1 r4 O` | ops: 0=SELF, 1=TempTargetIID; values: [2 ; 8/0x14118 ; 0 ; 1 ; 1] | (SELF, target, -)[2, kind flags 8/0x14118, ...]; AI script 0x3400053A |
| 0x10000022 | 0x15FCAD0 | 0x28 | ShowMinimapTargetingRing | X | 8/7 | `B O r1` | ops: 0=LastSkillSlotUsed/UltimateSkill; values: [0/1] | (skill slot)[0/1]; client execute sends GM_MapManager.RecvNotice_ShowMiniMapTargetingRing C10 |
| 0x10000024 | 0x15FCBEC | 0x3C | GetDetectedTarget | H | 114/105 | `B O O` | ops: 0=TargetIID/LoopingIID/LoopIID, 1=DetectedTargetIndex/DetectIter/CurrentIndex | (out entity, index): element of the FindTargets result list C10 |
| 0x10000025 | 0x15FBC94 | 0x7C | FindScatterPosition | M | 24/19 | `{B O O r1 r1 r1 r1 O r4 r4} O r1` | ops: 0=TargetPosition/TeleportPosition/TargetIID, 1=SELF/TargetPosition/CurrentPosition, 2=ScatterRadius/ReattachDistance, 3=SELF/TargetIID/AttachedIID; values: [0/1 ; 0 ; 0/1 ; 1/0 ; 5/0/10 ; 10/0/4 ; 0/1] | (out pos, center, radius, entity)[...]: pathable point near a position (TeleportPosition, ScatterRadius) |
| 0x10000026 | 0x15FB7E4 | 0x40 | Cast | H | 253/247 | `B O O r1 r1` | ops: 0=TargetIID/EODestinationIID/TempEOStartIID, 1=TargetPosition; values: [0/1 ; 0/1] | (target entity, target position)[flags]; client execute references 0x1000001D/0x1000018D/0x100002F9 C10 |
| 0x10000027 | 0x15FDFDC | 0x108 | ApplySkill (start status effect) | H | 482/340 | `{B r4 O O O O O O r1} O O O O r1 r1` | ops: 0=TargetIID/SELF/LoopingIID, 1=EffectDuration/MarkDuration/BuffDuration, 2=SkillRank/PermaRank/LingerRank, 3=CriticalChanceRoll/SlowAmount/StackValue_Buff, 4=AppliedEffectDID/HitEffectDID, 5=SourceEntityDID, 6=HandleForMember/Effect1Handle/EffectHandle, 7=PassiveSkillSlot/SkillSlot/SkillSlot3, 8=Success/EffectSuccess/DamageSuccess, 9=TargetIID/SELF/ShooterIID; values: [0x48000294/0/0x48000ab0 ; 1/0 ; 0/1 ; 1/0] | (target, duration, rank, value, effect DID, SourceEntityDID, out handle, slot, out success, source)[status 0x48..] |
| 0x10000028 | 0x15FBA54 | 0x3C | CheckRelation | H | 261/192 | `r4 O O` | ops: 0=SELF/ShooterIID/EffectSource, 1=TargetIID/StoredTargetIID/SELF; values: [3/4/2] | (a, b)[3 hostile, 4 ally?, 2 ...]; project name IsHostile C10 |
| 0x10000029 | 0x15FB9F4 | 0x24 | IsKind | H | 438/283 | `r4 O` | ops: 0=TargetIID/SELF/StoredTargetIID; values: [0x10108/8/4096] | (entity)[kind flags 0x10108 units, 8 champions, 0x1000 props ...] C10 |
| 0x1000002B | 0x15FAC14 | 0x4C | SetHUDVisibility | X | 0/0 | `B O O r4 r4 r4 r1` |  | unused in the player's scripts; client execute sends GM_UI.RecvNotice_UpdateHUDVisibility C10 |
| 0x1000002C | 0x15FAF44 | 0x5C | HasStealthFlags? | L | 2/2 | `{r4} r4 r4 O O O` | ops: 0=-, 1=Defender/TempDefender; values: [0x10000020 ; 0x697159/0x210100 ; 8/0x200000] | (-, entity, -)[0x10000020, flags, flags] in stealth / reveal scripts C10 |
| 0x1000002D | 0x15FC53C | 0x58 | DestroyHotspot | H | 35/25 | `B r4 O O O` | ops: 0=-, 1=SELF/HotspotIID/VortexIID, 2=HotspotHandle/SlowHotspotHandle/MarkHotspotHandle; values: [1] | (-, hotspot entity, handle)[1] on exit; pairs with 0x10000059 / 0x10000122 |
| 0x1000002E | 0x15FD8D8 | 0x5C | ShowSkillError | X | 0/0 | `B r4 O O r1 O` |  | unused; client execute sends GM_UI.RecvNotice_ExecuteSkillError C10 |
| 0x1000002F | 0x15FD424 | 0x44 | SetGraphVariable | M | 19/16 | `B r4 O O r4` | ops: 0=AnimationSpeedMultiplier/KnockbackHeading/HeadingToTarget, 1=SELF/TargetIID; values: [0x10000936/0x100001bf/0x100001e7 ; 0x100001f4] | (value, entity)[graph variable 0x10.., 0x100001F4]: AnimationSpeedMultiplier, KnockbackHeading; client runs a scriptlet C10 |
| 0x10000030 | 0x15FBD84 | 0x40 | StartScriptOn | L | 1/1 | `B r4 O O` | ops: 0=ShooterIID; values: [0x340006ff] | (entity)[script 0x34..] C10 |
| 0x10000031 | 0x15FDE60 | 0x5C | SpendCost | H | 265/228 | `B r4 O O r1 O` | ops: 0=ctx0xb4/ctx0xc0/ctx0xbc, 1=SELF/TargetIID/AttackerIID; values: [5/2/4 ; 0/1] | (cost stat, entity, -)[vital 5 = Will?, flag]; project name Spend C10 |
| 0x10000033 | 0x15FBC64 | 0x4C | RemoveAttributeModifier | H | 200/169 | `B O O {r4}` | ops: 0=SELF/EffectSource/TargetIID, 1=SELF/TargetIID/EnemyLinkIID, 2=AttributeHandle/AttackableHandle/ExposedHandle, 3=TargetableHandle/Stat2_Handle/MovementSpeed_Handle, 4=RenderDrawHandle/VitalBarHandle/HealthRegenHandle, 5=FloatyHandle/HealthLockHandle/AttackArmorHandle, 6=TreatAsDeadHandle/MaxHealthReplaceHandle; values: [1/2/3 ; 0x100005e4/0x100006f3/0x100006fe ; 0x10000029/0x100005e4/0x10000b7a ; 0x1000072c/0x1 | (source, target, handle...)[count, attribute]; on exit (137), pairs with 0x10000008 C10 |
| 0x10000034 | 0x15FE104 | 0x54 | RunScriptlet | H | 1327/435 | `B r4 O O {r4} r1 r1` | ops: 0=SELF/TargetIID/ShooterIID, 1=-, 2=TargetIID/AnchorPosition/Scriptlet, 3=TargetSubEntity/MissileSpeed/AnchorPosition, 4=MissileSpeed/TargetIID; values: [0x100002fd/0x10000016/0x100000b8 ; 0/1/3 ; 0/0x10000030/0x1000050a ; 0/0x1000049d/0x100009eb ; 0/0x100009eb/0x100003ff] | (entity, -, argument...)[scriptlet key (0x33 table), ...] C10 |
| 0x10000035 | 0x160A610 | 0x14 | Unk_0035[r4 r4] | ? | 0/0 | `B r4 r4` |  | unused; client execute exists C10 |
| 0x10000036 | 0x15FB814 | 0x40 | Unk_0036(entity, value) | ? | 0/0 | `B O r4 O` |  | unused; client execute exists C10 |
| 0x10000039 | 0x15FC6BC | 0x34 | SendMissionEvent | L | 4/1 | `B {r4} O` | values: [1 ; 0x10000060/0x100000c9/0x10000078 ; 165] | (-)[1, event 0x10000060/0x100000C9/0x10000078, 165]; match-rule script 0x340002CF |
| 0x1000003A | 0x160A640 | 0x10 | UI_ShowMovie | M | 10/1 | `B r4` | values: [0/0x20000075/0x200000a7] | [UI movie 0x200000xx]; client UI flow script 0x34000000 C10 |
| 0x1000003B | 0x160A5E0 | 0x10 | UI_OnEvent | M | 59/1 | `{r4} r4` | values: [0x1000000a ; 18/95/42] | trigger [0x1000000A, n]; client UI flow script 0x34000000 C10 |
| 0x1000003C | 0x15FAFA4 | 0x3C | IsSameEntity / IsOwner | L | 27/8 | `O O r1` | ops: 0=SELF/EffectSource/StarroIID, 1=TempTargetIID/SELF/TargetIID; values: [0/1] | (a, b)[0/1] predicate (EffectSource, SELF) |
| 0x1000003D | 0x15FB994 | 0x24 | Unk_003D(value)[flag] | ? | 0/0 | `O r1` |  | unused predicate; client execute exists C10 |
| 0x1000003E | 0x15FCEB8 | 0x20 | IsAlive | H | 687/323 | `O` | ops: 0=TargetIID/SELF/TeamMemberIID | (entity) predicate C10 |
| 0x1000003F | 0x15FD068 | 0x5C | FaceTarget | H | 206/187 | `B O O O r1 r1 r4` | ops: 0=TargetIID/TargetPosition/WeaponIID, 1=-, 2=FacingIDVariable/LockFacingID/FacingHandle; values: [1/0 ; 0/1 ; 0/0x3e19999a/0x3d4ccccd] | (target entity or position, -, out facing handle)[...] C10 |
| 0x10000040 | 0x15FDE90 | 0xC4 | StartVitalOverTime | H | 78/62 | `{B r4 O O r1 O} O O r1 r1 r1 r4 O O` | ops: 0=VitalChange/DamagePerSec/DamageOverTime, 1=SELF/TargetIID/CurrentTargetIID, 2=MaxDamage, 3=VitalOverTimeHandle/DOTHandle/DoTHandle, 4=EffectDuration/Duration/HealDuration, 5=SourceEntityDID, 6=SkillSlotW; values: [2/5/4 ; 0/1 ; 0/1 ; 0/1 ; 0/1 ; 0/2/1] | (amount, target, max, out handle, duration, SourceEntityDID, slot)[vital 2 health / 1 / 5, ...]: DOT / HOT |
| 0x10000042 | 0x15FCE88 | 0x3C | PickUpEntity? | L | 19/19 | `B O O` | ops: 0=SELF/TargetIID/AttachedIID, 1=Success | (entity, out success) in grab/carry skills |
| 0x10000043 | 0x160A670 | 0x10 | UI_Unk_0043[flag] | ? | 1/1 | `B r1` | values: [1] | client UI flow script only C10 |
| 0x10000045 | 0x15FAC44 | 0x24 | SetHUDVisibility2 | X | 0/0 | `B O` |  | unused; client execute sends GM_UI.RecvNotice_UpdateHUDVisibility C10 |
| 0x10000046 | 0x15FA1B8 | 0x14 | Unk_0046 | ? | 0/0 | `{r4 r1 r1} r4` |  | unused; client execute exists C10 |
| 0x10000047 | 0x15FCA74 | 0xC8 | FindTargets | H | 127/107 | `B r1 r4 O O O O r4 O r4 O O r4 r1 r1 r1` | ops: 0=SkillRange/Range/RevealRange, 1=SkillRange/Range/BlastLength, 2=BoxHeight/Height/DamageHeight, 3=SkillWidth/Width/DamageWidth, 4=-, 5=NumDetectedTargets/NumDetected/DetectedTargetIndex, 6=TargetPosition/TargetIID/StartPosition; values: [1/0 ; 1/7/2 ; 0x10108/0x410109/0x610109 ; 3/2/4 ; 12/8/4 ; 0/1 ; 0/1 ; 0/1] | (range, length, height, width, -, out count, center)[shape 1/7/2, kind flags, relation 3=hostile, max 12, ...]: radius / box / cone queries C10 |
| 0x10000048 | 0x15FA008 | 0x8 | UI_Condition_0048 | ? | 2/2 | `` |  | no fields, trigger in the client UI flow script C10 |
| 0x10000049 | 0x15FA4B8 | 0x10 | OnMissionEvent | L | 4/1 | `{r4} r4` | values: [0x1000001c/0x1000007a/0x10000079 ; 165/284/314] | trigger [event, id 165/284/314]; pairs with 0x10000039 C10 |
| 0x1000004A | 0x15FA278 | 0x10 | Unk_004A[r4 r4] trigger | ? | 0/0 | `{r4} r4` |  | unused C10 |
| 0x1000004B | 0x15FB6C4 | 0x3C | GetLevel | H | 13/13 | `B O O` | ops: 0=AgentLevel/CharacterLevel/Level, 1=SELF | (out level, entity); AgentLevel, CharacterLevel C10 |
| 0x1000004D | 0x15FA9C8 | 0x10 | UI_SendStateMachineEvent | X | 35/1 | `B r4` | values: [65/68/64] | [event 64..109]; client execute sends GM_UI.RecvNotice_UIStateMachineEvent (UI flow script) C10 |
| 0x1000004E | 0x15FD128 | 0x28 | RaiseGraphEvent (BehaviorRaiseEventAction) | X | 423/228 | `B O r4` | ops: 0=SELF/TargetIID/AttachedIID; values: [0x10000002/0x100003bf/0x100003bd] | (entity)[graph event]; client execute runs scriptlet _HFSM_BehaviorRaiseEventAction 0x100001E3 with variable 0x780 = event C10 |
| 0x1000004F | 0x15FB034 | 0x88 | AIMoveTo | M | 10/5 | `B O O O O r1 O` | ops: 0=-, 1=HalfSkillRange/MoveToRange/MaxDistToFinishMove, 2=TargetIID/TempTargetPosition/EffectSource, 3=SELF, 4=AttackingMoveToHandle/MoveToHandle/MoveHandle; values: [0/1] | (-, range, target entity/position, mover, out handle)[0/1]: AI/movement order (MoveToHandle, AttackingMoveToHandle) |
| 0x10000050 | 0x15FCC4C | 0x40 | InitSkill | H | 142/135 | `B O O r4` | ops: 0=SkillRank/UltimateRank/MissileRank, 1=ShooterIID/SELF/EffectSource; values: [0xffffffff/1/0] | (out rank, owner)[slot] C10 |
| 0x10000051 | 0x15FC35C | 0x78 | Unk_0051 | ? | 0/0 | `B r4 O O r4 O r1 r4 r4 {r4}` |  | unused |
| 0x10000052 | 0x15FD008 | 0x84 | IsInRangeAndAngle | H | 187/125 | `O O O O O r1 r1` | ops: 0=EdgeMinDistance/Range45/Range35, 1=SkillRange/AuraRadius/SkillRangePlus, 2=AngleKey/AngleRange/HalfAngle, 3=TargetIID/TeamMemberIID/LoopingIID, 4=SELF/MissileFirePosition/SourcePosition; values: [1/0 ; 1/0] | (min, max range, angle, target, from)[flags]; project name IsWithinAngle C10 |
| 0x10000053 | 0x15F9FD8 | 0x10 | Unk_0053[r4 r4] trigger | ? | 0/0 | `{r4} r4` |  | unused C10 |
| 0x10000054 | 0x15FE1D8 | 0x90 | Unk_0054 (scriptlet-like) | ? | 0/0 | `{B r4 O O {r4} r1 r1} r4 O O r4 r4` |  | unused; client code references 0x10000030/0x10000046/0x100000C0/0x1000026D C10 |
| 0x10000055 | 0x15FA7E8 | 0xC | OnEntityEvent | L | 73/71 | `r4` | values: [0x10000002] | trigger [0x10000002 (collision)] in 71 missile scripts C10 |
| 0x10000056 | 0x15FC984 | 0x28 | HideMinimapTargetingRing | X | 8/7 | `B O r1` | ops: 0=LastSkillSlotUsed/UltimateSkill; values: [0/1] | (skill slot)[0/1]; client execute sends GM_MapManager.RecvNotice_ShowMiniMapTargetingRing C10 |
| 0x10000057 | 0x15FD184 | 0x24 | ReleaseFacing | H | 298/193 | `B O` | ops: 0=FacingIDVariable/LockFacingID/FacingHandle | (facing handle) from FaceTarget; 298 uses, mostly exit C10 |
| 0x10000058 | 0x15FBEA8 | 0x3C | SetVariable / CopyEventParameter | H | 972/478 | `B O O` | ops: 0=TargetIID/EffectSource/EffectDuration, 1=lit | (variable, value or #event parameter) C10 |
| 0x10000059 | 0x15FE1A8 | 0x194 | CreateHotspot | H | 13/13 | `{B O O r4 O r4 O O r4 O O r4 r4 r4 O O O O O r1 r1 r1 r1 r1}` | ops: 0=HotspotDuration/EffectDuration/GasCloudDuration, 1=SkillRank, 2=-, 3=-, 4=SecondaryFearDuration, 5=-, 6=EffectExitDuration/TailDuration, 7=HotspotRadius/SkillRange/VortexRadius, 8=SkillRange/HotspotInitLen, 9=HotspotHeight, 10=HotspotWidth, 11=-, 12=TargetPosition/SELF/HotspotPosition, 13=HotspotIID/VortexIID; values: [0x48000285/0x48000283/0x48000259 ; 0/0x48000a6b ; 0/0x480005b5/0x48000818 ; 3/4 ; 0x10108/0x | (duration, rank, ..., radius, length, height, width, position, out hotspot)[status 0x48.. x3, relation, kind flags, shape, world state 0x2E..] |
| 0x1000005A | 0x15FB544 | 0x58 | ComputeOffset | H | 114/77 | `B O O O r1` | ops: 0=SELF/StartPosition/TargetPosition, 1=TargetPosition/TargetIID/SELF, 2=PositionOffset/OffsetToTarget/FireRotationOffset; values: [0/1] | (from, to, out offset)[flag]; project name Offset C10 |
| 0x1000005B | 0x15FB2D4 | 0x48 | DisableActions | M | 18/15 | `B r4 O r1 O r4` | ops: 0=SELF/TargetIID, 1=ActionHandle/ActionFamilyHandle/KnockupHandle; values: [77/65/82 ; 1 ; 50] | (entity, out handle)[action family 65/77/82, 1, 50]: ActionHandle, KnockupHandle, crowd control |
| 0x1000005C | 0x15FC32C | 0x28 | Unk_005C(entity)[0] | ? | 1/1 | `B r4 O` | ops: 0=TargetIID | 1 use; client code references 0x100004FF C10 |
| 0x1000005D | 0x15FDC0C | 0x28 | Unk_005D | ? | 0/0 | `B O r1` |  | unused |
| 0x1000005E | 0x15FCBBC | 0xE0 | LaunchMissile | H | 73/57 | `{B r4 O O O O O O r4 O O r1 r1 r4} r1 r1` | ops: 0=MissileIID/MissileID/SELF, 1=TargetPosition/TargetIID/LoopingIID, 2=SkillRange/Range/MissileRange, 3=MissileSpeed/MissileVelocity/ActualSpeed, 4=MissileIID/MissileIID1/MissileIID2, 5=FireOffset/MissileFireOffset/MissileOffset, 6=-, 7=SuperStrengthSkillSlot; values: [0/0x4000026e/0x40000512 ; 0 ; 1/0 ; 1/0 ; 2/7 ; 0/1] | (out missile, target, range, speed, out missile, fire offset, ...)[class 0x40.., ...] |
| 0x1000005F | 0x15FCB8C | 0x114 | LaunchTetheredMissile | M | 6/4 | `{B r4 O O O O O O r4 O O r1 r1 r4} O O r4 r1 r1` | ops: 0=-, 1=TargetPosition/TargetIID, 2=SkillRange, 3=MissileSpeed, 4=MissileIID, 5=FireOffset/StartMissileOffset/MissileFireOffset, 6=-, 7=-, 8=GrabOffset/EndMissileOffset/MissileGrabOffset, 9=Width; values: [0x4000000a/0x40000990/0x40000485 ; 0 ; 1 ; 1/0 ; 2 ; 0x3f19999a/0.5/0x3f4ccccd ; 0/1 ; 1/0] | LaunchMissile + grab offset and width (hooks / grabs) |
| 0x10000060 | 0x15FC7DC | 0x124 | SetTutorialMarker? | L | 8/3 | `B r4 r4 {r1 r4 r4 {V V V V *loop} {r1}} r4 r4 r4 O O O O O O` | values: [47/52/38 ; 0/2 ; 0 ; 0 ; 0 ; 0 ; 0 ; 1/2/0] | (6 operands)[id 38..52, ...] in tutorial scripts; client execute calls many UI functions C10 |
| 0x10000061 | 0x15FDBDC | 0x24 | Unk_0061 | ? | 0/0 | `B O` |  | unused |
| 0x10000062 | 0x15FD7E8 | 0x40 | RedirectMissile | H | 6/5 | `B r1 O O` | ops: 0=NextTargetIID/SecondTarget/SELF, 1=SkillRange/KnockbackDistance; values: [1/0] | (new target, range)[flag] |
| 0x10000063 | 0x15FC65C | 0x28 | Unk_0063(-)[0x1000018B] | ? | 1/1 | `B r4 O` | values: [0x1000018b] | 1 use (0x34000598) |
| 0x10000064 | 0x15FA608 | 0xC | Unk_0064[r4] | ? | 0/0 | `r4` |  | unused |
| 0x10000065 | 0x15FC26C | 0x44 | GrantCurrency | M | 4/4 | `B O O r4 r4` | ops: 0=SELF/EffectSource, 1=CurrencyGrant/BonusCurrency/CreditBonus; values: [4/0 ; 128/8] | (entity, amount)[type 0/4, flags 8/128]: CurrencyGrant, BonusCredits |
| 0x10000067 | 0x15FA2A8 | 0x10 | Unk_0067[r4 r4] trigger | ? | 0/0 | `{r4} r4` |  | unused C10 |
| 0x10000068 | 0x15FAE24 | 0x3C | Unk_0068 | ? | 0/0 | `B O O` |  | unused |
| 0x10000069 | 0x15FA038 | 0x8 | Unk_0069 | ? | 0/0 | `` |  | unused |
| 0x1000006A | 0x15FB514 | 0x24 | HasFlagAttribute | M | 58/36 | `O r4` | ops: 0=SELF/TargetIID/NextTargetIID; values: [0x100003f3/0x100003ab/0x10000459] | (entity)[bool attribute 0x100003F3 stunned, 0x10000459, 0x100003AB ...] predicate; project name HasStatus C10 |
| 0x1000006B | 0x15FBDB4 | 0x78 | RaiseEvent | H | 263/164 | `B r4 O r4 O O O r1 r1` | ops: 0=SELF/ShooterIID/EffectSource, 1=SELF/TargetIID/PredatorIID, 2=TargetPosition/LastGoodPos, 3=CriticalRoll/ActualDamage/WasSoaring; values: [0x10000141/0x1000001d/0x10000140 ; 0/0x340005d8/0x34000164 ; 0/1 ; 0/1] | (receiver, ..., position, value)[event, script 0x34.., flags] |
| 0x1000006D | 0x15FE2DC | 0xA0 | Unk_006D | ? | 0/0 | `B O O O r1 r4 r4 r4 r4 r4 r4 r4 {r4} {r4} r1 r4 r1` |  | unused |
| 0x1000006E | 0x15FCD6C | 0x24 | Unk_006E predicate | ? | 0/0 | `r4 O` |  | unused C10 |
| 0x1000006F | 0x15FA788 | 0xC | DisableCollision | M | 102/80 | `r4` |  | no fields; physics component (+0xB8) toggle with 0; missile end state C10 |
| 0x10000070 | 0x15FA6F8 | 0xC | EnableCollision | M | 85/85 | `r4` |  | no fields; physics component toggle with 1; missile start C10 |
| 0x10000072 | 0x15FB9C4 | 0x24 | IsClass | M | 14/9 | `O r4` | ops: 0=TargetIID/LoopingIID/SELF; values: [0x40000bcf/0x40000d2c/0x40000aa6] | (entity)[entity class 0x40..] predicate C10 |
| 0x10000073 | 0x15FA338 | 0x8 | Unk_0073 | ? | 0/0 | `` |  | unused C10 |
| 0x10000075 | 0x15FD2D0 | 0x28 | SetTargetingMode? | L | 24/21 | `B O r4` | ops: 0=SELF/TargetIID; values: [0/0xffffffff/3] | (entity)[0/-1/1/3/5] after StartCooldown |
| 0x10000076 | 0x15FA488 | 0x8 | Unk_0076 | ? | 0/0 | `` |  | unused C10 |
| 0x10000078 | 0x15FBCC4 | 0x28 | SetGroundMarker? | L | 10/6 | `B r1 O` | ops: 0=CurrentPosition; values: [0/1] | (position)[0/1] C10 |
| 0x1000007A | 0x15FE210 | 0x90 | TargetHit (hit effect) | M | 448/300 | `{B r4 O O {r4} r1 r1} O O r1 r4 r4` | ops: 0=TargetIID/SELF/StoredTargetIID, 1=TargetSubEntity/RootSubEntity, 2=CriticalChanceRoll, 3=SELF/ShooterIID/EffectSource; values: [0x10000223/0x100003ea/0 ; 0 ; 0 ; 0 ; 1/0 ; 0/0x1e0000cd/0x1e000017 ; 0/0x1e0000b0/0x1e0004cc] | (target, sub-entity, crit, source)[reaction scriptlet 0x10000223, ..., status 0x1E.. x2]; the scriptlets _HFSM_TargetHitAction_PhysicalReaction / _HitFlash name the action |
| 0x1000007B | 0x15FB8A4 | 0x3C | GetTeam | H | 62/60 | `B O O` | ops: 0=SELF/EffectSource/AttackerIID, 1=MyTeam/AppliedToTeam/ThrowersTeam | (entity, out team) C10 |
| 0x1000007C | 0x15FB484 | 0x3C | Unk_007C | ? | 0/0 | `B O O` |  | unused |
| 0x1000007D | 0x15FDC6C | 0x3C | BeginTeleport? | L | 2/2 | `B O O` | ops: 0=SELF, 1=SELF | (SELF, SELF) at the start of recall / teleport |
| 0x1000007E | 0x15FBE78 | 0x3C | SetTeam | H | 4/3 | `B O O` | ops: 0=WeaponIID/ObjectIID/SELF, 1=ThrowersTeam/NeutralTeam/TeamNeutral | (entity, team): thrown objects get the thrower's team |
| 0x1000007F | 0x15FDC9C | 0x3C | EndTeleport? | L | 2/2 | `B O O` | ops: 0=SELF, 1=SELF | (SELF, SELF) at the end of recall / teleport |
| 0x10000080 | 0x15FD9CC | 0x54 | Unk_0080 | ? | 0/0 | `B O O O` |  | unused; component +0x9C C10 |
| 0x10000081 | 0x15FBD24 | 0x3C | StopAction | M | 107/79 | `B O O` | ops: 0=SELF/TargetIID/AttachedIID, 1=DashHandle/AttachHandle/KnockBackHandle | (entity, handle): ends a dash / knockback / attach / action handle |
| 0x10000082 | 0x15FB844 | 0x58 | GetTeamMember | H | 46/21 | `B O O O r4` | ops: 0=TeamMemberIID/LoopingIID/LoopIID, 1=ArrayIndex/TargetIndex/LoopIndex, 2=AppliedToTeam; values: [7/2/4] | (out member, index, team)[filter 7/2/4] C10 |
| 0x10000083 | 0x15FBC30 | 0x28 | TrackTeamEvents | M | 30/15 | `B r1 O` | ops: 0=AppliedToTeam; values: [1/0] | (team)[1 start / 0 stop]: then events 0x1000007C / 0x1000007B (member in / out) C10 |
| 0x10000084 | 0x15FE074 | 0x114 | Unk_0084 | ? | 0/0 | `{B O O O O r1 r4 O O O} O O O r4 r4 r4 r1` |  | unused C10 |
| 0x10000085 | 0x15FCA44 | 0x100 | DestructionImpulse | H | 185/147 | `B r1 r4 r4 r4 O O O O O O O O O r4 r4 r1 r1 r1` | ops: 0=DestructionRadius/SkillRange/ExplosionRadius, 1=SkillDestructionLength/SkillRange/TotalRange, 2=SkillDestructionHeight/DestructionBoxHeight/BoxHeight, 3=SkillDestructionWidth/TotalRange/SkillRange, 4=MissilePositionOnCollision/SELF/TargetPosition, 5=DestructionMagnitude/DestructionMagnitude_Cosmetic/DestructionMagnitude_Destroy, 6=-, 7=TargetIID/CollideTarget/SELF, 8=TargetSubEntity/SubEntity/CollideSubTarget; | (radius, length, height, width, position, magnitude, -, target, sub-entity)[shape, ...]: pushes destructibles C10 |
| 0x10000086 | 0x15FC5CC | 0x28 | Unk_0086 | ? | 0/0 | `B r4 O` |  | unused |
| 0x10000087 | 0x15FC2FC | 0x40 | SetUsageObject | L | 2/1 | `B O O r1` | ops: 0=SELF, 1=UsageObject; values: [0/1] | (SELF, object)[0/1] |
| 0x10000088 | 0x15FB634 | 0x24 | Unk_0088 | ? | 0/0 | `B O` |  | unused C10 |
| 0x10000089 | 0x15FDB7C | 0x5C | ChangeSkill? | L | 16/12 | `B O r4 O r1 O` | ops: 0=SELF/ShooterIID, 1=-, 2=BasicAttack; values: [0x48001533/0x4800077a/0x4800097e ; 1/0] | (entity, -, slot)[skill 0x48.., flag] |
| 0x1000008A | 0x15FC4AC | 0x28 | Unk_008A | ? | 0/0 | `B r4 O` |  | unused |
| 0x1000008B | 0x15FC29C | 0x44 | Unk_008B | ? | 0/0 | `B r4 r4 O O` |  | unused |
| 0x1000008E | 0x15FDBAC | 0x28 | SetSkillState? | L | 77/62 | `B O r4` | ops: 0=SELF; values: [0xffffffff/1/0] | (entity)[-1/0..5] on exit after cooldown |
| 0x1000008F | 0x15FB454 | 0xAC | AttachEntity | M | 25/18 | `B O O r4 O r4 r1 O r1 O O` | ops: 0=SELF/TargetIID/ShooterIID, 1=SELF/TargetIID/WeaponIID, 2=AttachmentOffset/AttachmentServerOffset/ServerOffset, 3=AttachHandle/AttachmentHandle/DummyHandle, 4=BlipSequence, 5=AttachSuccess/Success; values: [0/0x1000007b/0x100000b0 ; 0/0x10000081/0x10000082 ; 0/1 ; 0/1] | (child, parent, offset, out handle, ..., out success)[attach point keys] |
| 0x10000090 | 0x15FC05C | 0x2C | SetObjectState? | L | 11/10 | `B O r4 r1` | ops: 0=SELF/WeaponIID/TargetIID; values: [1/17/19 ; 1/0] | (entity)[17/19/1/8, flag] on thrown objects / weapons |
| 0x10000092 | 0x15FDF7C | 0x3C | RemoveTempVital | H | 15/15 | `B O O` | ops: 0=SELF, 1=TempVitalHandle/ShieldHandle/TempHealthHandle | (entity, handle) on exit; pairs with 0x10000093 C10 |
| 0x10000093 | 0x15FDE30 | 0x90 | AddTempVital (shield) | H | 16/15 | `{B r4 O O r1 O} O O r4` | ops: 0=TempHealth/ShieldAmount/TempVitalAmount, 1=SELF, 2=-, 3=TempVitalHandle/ShieldHandle/TempHealthHandle, 4=EffectDuration/ShieldDuration; values: [2 ; 0 ; 0/2] | (amount, entity, -, out handle, duration)[vital, ...] C10 |
| 0x10000097 | 0x15FD848 | 0x30 | SetSkillCooldownState? | L | 154/71 | `B r4 r1 r4 O` | ops: 0=LastSkillSlotUsed/UltimateSkill; values: [1/2/4 ; 0/1 ; 0xffffffff/1/2] | (slot)[1/2/4, 0/1, ...] on enter/exit of skill states C10 |
| 0x1000009C | 0x15FA5A8 | 0x28 | SetEnvironmentSetting? | L | 11/5 | `B r1 r4 r1 r4 r4 r4 r4` | values: [1/0 ; 0x10000016/0/2 ; 0/1 ; 0/3] | [1, 0x10000016/0x1000000A.., ...] in cinematic/match scripts C10 |
| 0x1000009E | 0x15FCB00 | 0x40 | Unk_009E | ? | 0/0 | `B O O r1` |  | unused; vitals component C10 |
| 0x1000009F | 0x15FE43C | 0x38 | LoadSkillStats | H | 710/642 | `B O {r4} r4` | ops: 0=EffectSource/ShooterIID/SELF, 1=SkillDamage/ctx0xb4/Damage, 2=SkillCooldownDuration/SkillRange/CooldownDuration, 3=SkillRange/MissileSpeed/Damage, 4=MissileSpeed/SkillRange/EffectDuration, 5=Damage/MaxCharges/MissileSpeed, 6=SkillRange/Damage/MissileSpeed, 7=MissileSpeed/SkillRange/Damage, 8=AngleRange/InterruptCooldown/StunDuration, 9=KnockbackDistance/KnockbackDuration/MiniCooldown, 10=MaxDamage/DashSpeed/Mi | (owner, out stat vars...)[count, stat ids] C10 |
| 0x100000A0 | 0x15FE0A4 | 0xA4 | SpawnEntity | H | 74/57 | `{B O O r1 r1 r1 r1 O r4 r4} r4 O O {r4}` | ops: 0=TargetPosition/StartPosition/CreatePosition, 1=TeethOneBackup/TeethTwoBackup/TeethThreeBackup, 2=ScatterRange/ScatterRadius, 3=-, 4=MissileIID/LootIID/MissileID, 5=MyTeam/MyLevel/SkillRank, 6=MyTeam/TeethOne/TeethTwo, 7=BestowalType/Level, 8=BillboardIcon, 9=SELF; values: [1/0 ; 0 ; 0/1 ; 0/1 ; 0/10/5 ; 0/1/10 ; 0x4000020b/0x4000043d/0x40000646 ; 1/0/2 ; 0x1000009c/0x10000167/1188 ; 0x1000009c/0x1000099b/0x100 | (position, ..., out entity, team, level, ...)[class 0x40..] |
| 0x100000A1 | 0x15FC02C | 0x3C | Unk_00A1(entity, entity) | ? | 2/1 | `B O O` | ops: 0=HeadIID, 1=SELF | 2 uses |
| 0x100000A3 | 0x15FC9B4 | 0x40 | ReduceCooldown | M | 31/20 | `B O r4 O` | ops: 0=SELF/EffectSource/ShooterIID, 1=CooldownReduction/CooldownBonus/PrimedCooldownDuration; values: [2/0xffffffff/3] | (entity, amount)[slot]: CooldownReduction, PrimedCooldownDuration |
| 0x100000A4 | 0x15FCF78 | 0x58 | HasStatus | H | 220/129 | `O O r4 O r4` | ops: 0=TeamMemberIID/TargetIID/SELF, 1=-, 2=HandleForMember/MarkHandle/BuffHandle; values: [0/0x48000287/0x48000943 ; 0/8192/7554] | (target, -, handle)[status 0x48.., flags] C10 |
| 0x100000A5 | 0x15FB784 | 0x24 | SetOwner / SetCreator? | L | 17/17 | `B O` | ops: 0=CreatorIID/EffectSource/ShooterIID | (entity): CreatorIID, ShooterIID, Caster C10 |
| 0x100000A6 | 0x15FD698 | 0x44 | RemoveStatusIcon | H | 183/153 | `B O O r4 r1 r1` | ops: 0=SIDHandle/StatusIconHandle/TimerSIDHandle, 1=SELF/TargetIID/EffectSource; values: [0/0x4800029a/0x48000685 ; 0 ; 1] | (icon handle, entity)[...]; pairs with 0x100000A7 |
| 0x100000A7 | 0x15FD638 | 0xF0 | AddStatusIcon | H | 176/160 | `B O O O r4 O O O O O r4 r1 O` | ops: 0=SIDHandle/StatusIconHandle/IconHandle, 1=SELF/TargetIID/EffectSource, 2=StackCount/StackCounter/ChargeCount, 3=EffectSource/SELF/SourceIID, 4=EffectDuration/Duration/BuffDuration, 5=SourceEntityDID, 6=SELF/EffectSource/EffectSourceID, 7=SIDIconDID, 8=UseRemainingCooldown; values: [0x48001151/0x48000536/0x480010a3 ; 0xffffffff/5/4 ; 0/1] | (out handle, entity, stacks, source, duration, SourceEntityDID, ...)[icon record 0x48.., ...] |
| 0x100000A8 | 0x15FD878 | 0x90 | UpdateStatusIcon | H | 74/52 | `B O O O O r1 O r4 r4` | ops: 0=SIDHandle/StatusIconHandle/TimerSIDHandle, 1=SELF/EffectSource, 2=StackCount/ChargeCount/CurrentSkillCount, 3=EffectDuration/RevTimerDuration/CombatTimerDuration, 4=SELF/EffectSource; values: [0/1 ; 0xffffffff/5/2 ; 0/0x4800029a] | (handle, entity, stacks, duration, source)[...] |
| 0x100000AA | 0x15FE3CC | 0x58 | Unk_00AA (scriptlet-like) | ? | 0/0 | `{B r4 O O {r4} r1 r1} r4` |  | unused; client code references 0x1000050A C10 |
| 0x100000AC | 0x15FA668 | 0x14 | Unk_00AC | ? | 0/0 | `B r4 r4` |  | unused |
| 0x100000AD | 0x15FBFCC | 0x28 | SuppressInput? | L | 24/9 | `B O r1` | ops: 0=SELF/TargetIID; values: [0/1] | (entity)[0/1]; next to InputSuppressed C10 |
| 0x100000AE | 0x15FA368 | 0x8 | Unk_00AE predicate | ? | 1/1 | `` |  | 1 use |
| 0x100000AF | 0x15FA5D8 | 0x10 | Unk_00AF | ? | 0/0 | `B r1` |  | unused |
| 0x100000B0 | 0x15FBF08 | 0x28 | SnapToGround? | L | 17/17 | `B O r1 r1` | ops: 0=TargetPosition/HotspotPosition/TempPosition; values: [0/1 ; 1/0] | (position)[0/1, 0/1] before CreateHotspot C10 |
| 0x100000B1 | 0x15FA188 | 0x10 | OnAttributeChanged | M | 74/55 | `{r4} r4` | values: [0x100000a2 ; 0x10000b7b/0x10000b76/0x100006fe] | trigger [0x100000A2, attribute] C10 |
| 0x100000B2 | 0x15FC7AC | 0x24 | StopMissionEvent | L | 1/1 | `B O` | ops: 0=MissionEventHandle | (handle) |
| 0x100000B3 | 0x15FC77C | 0x28 | Unk_00B3 | ? | 0/0 | `B O r4` |  | unused |
| 0x100000B8 | 0x15FB4B4 | 0x28 | SetImpactState? | L | 6/3 | `B r4 O` | ops: 0=SELF/ImpactIID; values: [5/0/3] | (entity)[0/3/5/6] C10 |
| 0x100000BA | 0x15FB4E4 | 0x40 | Unk_00BA | ? | 0/0 | `B O O r4` |  | unused |
| 0x100000BB | 0x15FBBD0 | 0x5C | PlaySound / PlayAudioEvent? | L | 17/8 | `B r4 O O O r4` | ops: 0=-, 1=SELF, 2=TargetIID; values: [0xffffffff ; 0x4aca6d64/0x92a57d8a/0x718ba2b9] | (-, entity, target)[-1, 32-bit hash]: values are hashes (Wwise event ids?) C10 |
| 0x100000BD | 0x15FB934 | 0x28 | Unk_00BD | ? | 0/0 | `B O r4` |  | unused |
| 0x100000BE | 0x15FDA2C | 0x54 | Unk_00BE | ? | 0/0 | `B O O O` |  | unused |
| 0x100000BF | 0x15FDCCC | 0x3C | Unk_00BF | ? | 0/0 | `B O O` |  | unused |
| 0x100000C0 | 0x15FA938 | 0x10 | Unk_00C0[flag] | ? | 0/0 | `B r1` |  | unused; client execute exists C10 |
| 0x100000C1 | 0x15FA0C8 | 0xC | ClearEntityList | H | 47/45 | `r4` |  | no fields (skill component list) C10 |
| 0x100000C2 | 0x15FB394 | 0x24 | AddToEntityList | H | 69/51 | `B O` | ops: 0=TeamMemberIID/TargetIID/LoopingIID | (entity) C10 |
| 0x100000C3 | 0x15FB364 | 0x24 | GetEntityListCount | H | 58/26 | `B O` | ops: 0=ArrayCount/NumTargets/ArraySize | (out count) C10 |
| 0x100000C4 | 0x15FB304 | 0x20 | IsInEntityList | H | 41/38 | `O` | ops: 0=TargetIID/TeamMemberIID/LoopIID | (entity) predicate C10 |
| 0x100000C5 | 0x15FB334 | 0x3C | GetEntityListItem | H | 59/27 | `B O O` | ops: 0=TeamMemberIID/LoopingIID/TargetIID, 1=ArrayIndex/TargetIndex/LoopIndex | (out entity, index) C10 |
| 0x100000C6 | 0x15FD038 | 0x9C | Knockback | H | 6/6 | `B O O O O O O` | ops: 0=SELF, 1=SourcePosition/Source/SelfKnockbackSource, 2=Duration/KnockBackDurationSelf, 3=Velocity/Speed, 4=Distance/KnockbackRangeSelf, 5=KnockBackHandle | (entity, source, duration, speed, distance, out handle) |
| 0x100000C7 | 0x15FC11C | 0x48 | Unk_00C7(entity, entity)[n, n, 2] | ? | 3/2 | `B O O r4 r4 r4` | ops: 0=SELF, 1=TestIID/TestTarget; values: [89/126/87 ; 9/1/5 ; 2] | 3 uses C10 |
| 0x100000C8 | 0x15FBF9C | 0x28 | SetUntargetable? | L | 17/9 | `B O r1` | ops: 0=SELF/TargetIID; values: [0/1] | (entity)[0/1] in recall / stealth |
| 0x100000CA | 0x15FD728 | 0x78 | SetStatusDuration | M | 56/38 | `B O O O r4 r4 O r1` | ops: 0=TargetIID/SELF/EOStartIID, 1=EOStartMarkHandle/EODestinationMarkHandle/StunHandle, 2=-, 3=StackDuration/EffectDuration/InfiniteDuration; values: [0 ; 0/0x48000d1f/0x48000684 ; 0/1] | (target, handle, -, duration)[status 0x48.., flag] |
| 0x100000CB | 0x15FA398 | 0x10 | UI_ShowMovie2 | M | 1/1 | `B r4` | values: [0x20000067] | [UI movie 0x20000067]; UI flow script C10 |
| 0x100000CC | 0x15FA128 | 0xC | UI_DestroyGameFront | X | 10/1 | `` |  | no fields; client execute sends GM_UI.RecvNotice_GameFrontUIDestroyedInCPP C10 |
| 0x100000CD | 0x15FB3C4 | 0x28 | RemoveFromEntityList | H | 23/23 | `B O r1` | ops: 0=TeamMemberIID/TargetIID/RemoveIID; values: [1/0] | (entity)[flag] C10 |
| 0x100000CE | 0x15FCD3C | 0x5C | GetVital | H | 56/42 | `B O O r4 r1 r1 O` | ops: 0=SELF/TargetIID/AttackerIID, 1=CurrentHealth/MaxHealth/TargetHealth, 2=TempVitalHandle/ShieldHandle; values: [2/5/6 ; 0/1 ; 0/1] | (entity, out value, handle)[vital 2/5/6, current 0 / max 1, ...] C10 |
| 0x100000D0 | 0x15FB754 | 0x24 | Unk_00D0 | ? | 0/0 | `B O` |  | unused |
| 0x100000D1 | 0x15FE36C | 0x60 | StartConversation | H | 47/7 | `B O {r4} r4 r4 r1 r1 O r1 r4` | ops: 0=-, 1=ConversationHandle1/ConversationHandle2/ConversationHandle3; values: [0 ; 441/559/558 ; 1 ; 1 ; 1/0 ; 1 ; 60] | (-, out handle)[0, conversation id, 1, 1, wait flag, 1, 60.0 s]; event 0x10000186 when it ends C10 |
| 0x100000D2 | 0x15FA848 | 0x8 | IsSkillActive? | L | 63/63 | `` |  | no-field predicate in the skill reset transition C10 |
| 0x100000D7 | 0x15FE044 | 0x108 | Unk_00D7 | ? | 0/0 | `{B O O O O r1 r4 O O O} O O O r4` |  | unused C10 |
| 0x100000D8 | 0x15FD390 | 0x2C | ShowSkillError | X | 27/25 | `B O r4 r4` | ops: 0=SELF; values: [0x10000034/0x10000059/0x1000003c ; 0xffffffff/4] | (entity)[error id, -1/4]; client execute sends GM_UI.RecvNotice_ExecuteSkillError C10 |
| 0x100000D9 | 0x15FDFAC | 0xBC | AddStacks | L | 5/4 | `{B r4 O O O O O O r1} O` | ops: 0=SELF/TargetIID, 1=StackDuration/ctx0xcc, 2=lit, 3=lit/StackValue_Buff/StackValue_Debuff, 4=lit, 5=SourceEntityDID/lit, 6=Stacks_FirstHit/MaxStackCount; values: [19924/0x480008a8/0x480008a7 ; 1/36] | (target, duration, -, value, -, SourceEntityDID, first-hit)[status 0x48..] |
| 0x100000DA | 0x15FD5A4 | 0x3C | Unk_00DA(SELF, SELF) | ? | 2/1 | `B O O` | ops: 0=SELF, 1=SELF | 2 uses |
| 0x100000DB | 0x15FBE48 | 0x48 | ResetBasicAttack? | L | 63/46 | `B O O r4 r4 r1 r1 r1` | ops: 0=SELF/ShooterIID, 1=TargetIID/AttachedIID/BasicAttackTargetIID; values: [2/6 ; 0/0xffffffff ; 0/1 ; 0/1 ; 0/1] | (entity, target)[2/6, ...] after RunScriptlet in skills |
| 0x100000DC | 0x15FB964 | 0x24 | HasState? | L | 5/4 | `O r4` | ops: 0=SELF/PredatorIID/TargetIID; values: [66/74/71] | (entity)[66/71/74] predicate C10 |
| 0x100000DD | 0x15FDF20 | 0xE4 | DestructionRaycast | M | 2/2 | `{B O O O O r1 r4 O O O} r4 O r1 r4 r4` | ops: 0=SELF, 1=StoredTargetIID/TargetIID, 2=SkillRange, 3=RaycastOffset, 4=DestructionBoxHeight, 5=DestructionBoxLength, 6=DestructionBoxWidth, 7=DestructionMagnitude; values: [1 ; 3 ; 1 ; 0 ; 0x1e000023/0 ; 0x10000223] | (SELF, target, range, offset, box h/l/w, magnitude)[... status 0x1E.., 0x10000223] C10 |
| 0x100000DE | 0x15FB2A4 | 0x3C | Unk_00DE | ? | 0/0 | `B O O` |  | unused |
| 0x100000DF | 0x15FCD9C | 0x24 | IsSkillReady? | L | 51/44 | `r4 O` | ops: 0=SourceEntityDID; values: [0xffffffff/5/1] | (SourceEntityDID)[-1/5/1] trigger C10 |
| 0x100000E1 | 0x15FCFA8 | 0x24 | IsMoving? | L | 37/25 | `O r1` | ops: 0=SELF/TargetIID; values: [0/1] | (entity)[0/1] in recall scripts |
| 0x100000E2 | 0x15FD484 | 0x28 | SetCleanupFlag | M | 629/303 | `B O r1` | ops: 0=NeedCleanup/RecallEnded; values: [0/1/7] | (NeedCleanup)[0/1] |
| 0x100000E4 | 0x15FC83C | 0x28 | SetPhysicsState? | L | 8/7 | `B r1 O` | ops: 0=SELF/TargetIID/ObjectIID; values: [0/1] | (entity)[0/1] on thrown objects |
| 0x100000E5 | 0x15FDA8C | 0x44 | Unk_00E5 | ? | 2/2 | `B O O r4 r1` | values: [1 ; 1] | 2 uses |
| 0x100000E6 | 0x15FDB4C | 0x24 | Unk_00E6 predicate | ? | 0/0 | `O r4` |  | unused; client code references 0x10000502 C10 |
| 0x100000E7 | 0x15FD758 | 0x44 | Unk_00E7 | ? | 0/0 | `B r4 r4 O O` |  | unused |
| 0x100000E8 | 0x15FB5D4 | 0x3C | GetVehicleDriver? | L | 6/5 | `B O O` | ops: 0=DriverIID/AttachIID, 1=SELF | (DriverIID / AttachIID, SELF) C10 |
| 0x100000EA | 0x15FCA14 | 0xD4 | DashToPosition | H | 33/32 | `B O O O O O O O r4 r1 O` | ops: 0=SELF, 1=TargetPosition/TargetCurrentPos/TargetIID, 2=MissileSpeed/DashVelocity/DashSpeed, 3=SkillRange/DashDistance/Range, 4=MinDashDistance, 5=DistanceFromWall, 6=DashHandle/KnockbackHandle/TempDashHandle, 7=DashStarted/DashSuccess; values: [15/0/13 ; 1/0] | (entity, target position, speed, range, min distance, wall distance, out handle, out started)[15, 1] |
| 0x100000EC | 0x15FB904 | 0x28 | SetCurrencyOption | L | 1/1 | `B O r4` | ops: 0=UseTeamwideCurrencyGains; values: [0x10000680] | (flag)[0x10000680] C10 |
| 0x100000ED | 0x15FDA5C | 0x28 | Unk_00ED | ? | 0/0 | `B r1 O` |  | unused |
| 0x100000EE | 0x15FC50C | 0x38 | Unk_00EE predicate | ? | 0/0 | `O O` |  | unused C10 |
| 0x100000EF | 0x15FBAB4 | 0x20 | EntityExists | M | 92/53 | `O` | ops: 0=TargetIID/TeamMemberIID/ctx0xd0 | (entity) predicate; loop condition C10 |
| 0x100000F1 | 0x15FB094 | 0x2C | SetMovementMode? | L | 13/6 | `B O r4 r4` | ops: 0=SELF; values: [0/1/2 ; 1/2/0] | (entity)[0/1/2, 1/2/0] |
| 0x100000F3 | 0x15FA458 | 0x8 | Unk_00F3 | ? | 0/0 | `` |  | unused |
| 0x100000F5 | 0x15FCCAC | 0x40 | SwapSkillScript | L | 4/4 | `B O O r4` | ops: 0=SuperStrengthSkillSlot/SkillSlot, 1=SELF; values: [0x34000164/0] | (slot, entity)[script 0x34000164 Super Strength] C10 |
| 0x100000F6 | 0x15FACA4 | 0x3C | Unk_00F6 | ? | 0/0 | `B O O` |  | unused C10 |
| 0x100000F7 | 0x15FAC74 | 0x40 | Unk_00F7 | ? | 0/0 | `B O O r1` |  | unused C10 |
| 0x100000F9 | 0x15FB424 | 0x3C | FindInEntityList | H | 15/15 | `B O O` | ops: 0=TeamMemberIID, 1=FoundArrayIndex | (entity, out index) C10 |
| 0x100000FA | 0x15FD0F8 | 0x9C | ShowFloatingText? | L | 59/43 | `B O r4 {r1 r4 r4 {V V V V *loop} {r1}} r4 r4 r1 r4 r4 r4 r4 ` | ops: 0=SELF/ctx0xd0; values: [0xffffffff/1/2 ; 0 ; 0/0xc5105d5/0xcf03545 ; 0/0x2b0001ab/0x2b0000bb ; 0 ; 0 ; 0 ; 0/0x662b05e/0x35c89ee ; 0/0x2b0001ab/0x2b0000bb ; 0 ...] | (entity)[..., string table 0x2B.. tokens ...] |
| 0x100000FB | 0x15FD4B4 | 0x48 | SetSkillErrorState | M | 67/33 | `B r4 r4 O r1 O` | ops: 0=SkillSlot, 1=ErrorStateHandle/ErrorHandle/ErrorState_Handle; values: [0x10000066/0x10000045/0x10000059 ; 0xffffffff/0xfffffffe/3 ; 1/0] | (slot, out handle)[error 0x10000045/0x10000066.., ...]: ErrorStateHandle |
| 0x100000FC | 0x15FD514 | 0x2C | SetSkillUsable? | L | 59/30 | `B O r4 r1 r1` | ops: 0=SELF/ShooterIID; values: [0xffffffff/4/3 ; 1/0 ; 0/1] | (entity)[slot, 0/1, 0/1] |
| 0x100000FD | 0x15FBC00 | 0x28 | Unk_00FD | ? | 0/0 | `B r1 O` |  | unused |
| 0x100000FE | 0x15FCC1C | 0x40 | GetStackCount | M | 12/8 | `B O O r4` | ops: 0=TargetIID/SELF, 1=StackCount/TargetDebuffCount/AttackerStackCount; values: [0x480007b6/0x48000a92/0x48000684] | (target, out count)[status 0x48..] |
| 0x10000100 | 0x15FC62C | 0x2C | Unk_0100 | ? | 0/0 | `B O r4 r4` |  | unused |
| 0x10000101 | 0x15FC59C | 0x28 | Unk_0101 | ? | 0/0 | `B O r4` |  | unused |
| 0x10000102 | 0x15FBF38 | 0x40 | StopScriptlet | H | 302/207 | `B O O r4` | ops: 0=SELF/TargetIID/PortalStartIID, 1=ActiveScriptHandle/ActiveHandle/ActiveFXHandle; values: [0/0x1e0000cf/0x1e0000a5] | (entity, handle)[...]; pairs with 0x10000103 C10 |
| 0x10000103 | 0x15FE16C | 0x70 | StartScriptlet | H | 312/208 | `{B r4 O O {r4} r1 r1} O r4` | ops: 0=SELF/TargetIID/PortalStartIID, 1=-, 2=ActiveScriptHandle/ActiveHandle/ActiveFXHandle, 3=ActiveScriptHandle/ActiveHandle/FXHandle, 4=FirstScriptHandle; values: [0x100003ea/0x10000223/0x100003cc ; 0/1/2 ; 0/0x100003ff/0x10000030 ; 0/0x1000044d ; 0/0x1e0000ce/0x1e0000a6 ; 0/0x1e00009c/0x1e000253 ; 0x1e0003d5] | (entity, -, out handle...)[scriptlet key, ...] C10 |
| 0x10000105 | 0x15FA908 | 0x10 | SetFlag_0105[0/1] | ? | 10/5 | `B r1` | values: [1/0] | 10 uses |
| 0x10000108 | 0x15FBAE4 | 0x40 | Unk_0108(SELF, -)[8/9] | ? | 3/2 | `B r4 O O` | ops: 0=SELF; values: [9/8] | recall script |
| 0x10000109 | 0x15FDD70 | 0x78 | FindValidPosition | M | 12/10 | `{B O O r1 r1 r1 r1 O r4 r4} O` | ops: 0=TestPosition/TargetPosition/EntityPosition, 1=-, 2=ScatterRadius, 3=TargetIID/SELF/LootIID; values: [0 ; 0/1 ; 0/1 ; 1 ; 0/5/7 ; 0/4/3] | (out position, -, radius, entity)[...] |
| 0x1000010A | 0x15FC4DC | 0x48 | SetGeneratorEntry | L | 1/1 | `B r4 r4 O r1 O` | ops: 0=Entry_Current, 1=GeneratorIID; values: [5 ; 0 ; 1] | (entry, generator)[5, 0, 1] |
| 0x1000010B | 0x15FBD54 | 0x54 | RollCritical | H | 59/57 | `B O O O` | ops: 0=CriticalChanceRoll, 1=TargetIID | (out roll, target, -) |
| 0x1000010C | 0x15FC1AC | 0x40 | Unk_010C | ? | 0/0 | `B O O r1` |  | unused |
| 0x1000010D | 0x15FD6C8 | 0x40 | SpawnWorldState? | L | 3/3 | `B O r4 O` | ops: 0=ctx0xd0, 1=SELF; values: [0/0x2e0004e6] | (-, entity)[world state 0x2E..] |
| 0x1000010E | 0x15FD300 | 0x24 | Unk_010E(-) | ? | 1/1 | `B O` |  | 1 use |
| 0x10000111 | 0x15FBED8 | 0x30 | ShowTutorialHint | X | 1/1 | `B r4 r4 O r1 r1` | values: [10 ; 0xffffffff] | (-)[hint id, -1, 0, 0]; client execute sends GM_Tutorial.RecvNotice_UI_ShowTutorialHint C10 |
| 0x10000112 | 0x15FB874 | 0x40 | Unk_0112 | ? | 0/0 | `B r4 O O` |  | unused |
| 0x10000113 | 0x15FB3F4 | 0x3C | Unk_0113 (entity list) | ? | 0/0 | `B O O` |  | unused; skill component list op C10 |
| 0x10000114 | 0x15FA878 | 0xC | SetCollisionLayer | M | 4/4 | `r4` |  | [layer]; physics component, client string 'CollisionLayer_Property' C10 |
| 0x10000115 | 0x15FA308 | 0x8 | UI_Condition_0115 | ? | 2/1 | `` |  | trigger in the UI flow script C10 |
| 0x10000116 | 0x15FD8A8 | 0x40 | SetStatusIconValue? | L | 30/23 | `B O O r4` | ops: 0=SIDHandle/StatusIconHandle, 1=SELF; values: [0/0x480008a6/0x480008a5] | (handle, entity)[0 / icon record] |
| 0x10000117 | 0x15FC14C | 0x40 | SetTracked | L | 4/2 | `B O r1 O` | ops: 0=ObjectIID/WeaponIID, 1=MadeTracked; values: [1/0] | (object, out MadeTracked)[flag] |
| 0x10000118 | 0x15FD4E4 | 0x34 | ShowFloatingNumber? | L | 11/11 | `B O r1 r4 r4 r4` | ops: 0=VaultKickDamageBoMasterMode/TotalMaxHealth/TotalHealAmount; values: [0/1 ; 0/1 ; 0/1 ; 0xfffffffe/5] | (value)[0/1, 0/1, 0/1, -2/5] |
| 0x10000119 | 0x15FC5FC | 0x24 | StopAnnouncement | M | 5/1 | `B O` | ops: 0=HandleEvent/HandleAnnouncement/HandleAnnounce | (handle) after 0x1000011A |
| 0x1000011A | 0x15FDDD0 | 0x84 | ShowAnnouncement | M | 10/1 | `B O O O r4 r4 r4 r1 {r4} {r4} r1` | ops: 0=HandleAnnounce/HandleEvent/HandleAnnouncement, 1=NeutralPlusLockDuration/NeutralizedDuration/DurationImpactTotal, 2=TeamFired; values: [1/2 ; 0/0x130029c4/0x130029ad ; 0x13000afe/0/0x130016cd ; 0/1 ; 1 ; 7 ; 0 ; 0x1cd5365/0x4df0835/0x58f21e5 ; 0x2b000098 ; 0 ...] | (out handle, duration, team)[..., image 0x13.., string tokens + table 0x2B000098 ...] |
| 0x1000011B | 0x15FA638 | 0xC | Unk_011B | ? | 0/0 | `` |  | unused |
| 0x1000011E | 0x15FC1DC | 0x44 | Unk_011E(-, source)[0/1, n] | ? | 3/1 | `B O O r1 r4` | ops: 0=-, 1=EffectSource; values: [1/0 ; 46/45/0] | 1 script |
| 0x10000120 | 0x15FB6F4 | 0x3C | GetEntityRadius | M | 12/12 | `B O O` | ops: 0=SELF/TargetIID/FirstTarget, 1=EntityRadius/DistanceFromWall/PhysicsRadius | (entity, out radius) C10 |
| 0x10000121 | 0x15FC0BC | 0x8C | UpdateObjective / MissionText? | L | 4/2 | `B r4 r4 r4 r1 r4 r4 r4 r4 O O O O` | values: [406/418/419 ; 0 ; 0 ; 0 ; 4/1 ; 2 ; 0xffffffff ; 0xffffffff] | (4 operands)[text id 393/406/418, ..., 4/1, 2, -1, -1]; tutorial power core and match scripts C10 |
| 0x10000122 | 0x15FDE00 | 0x17C | CreateAura (attached hotspot) | H | 34/25 | `{B O O r4 O r4 O O r4 O O r4 r4 r4 O O O O O r1 r1 r1 r1 r1}` | ops: 0=HotspotDuration/AuraDuration/EffectDuration, 1=-, 2=-, 3=-, 4=SecondaryFearDuration/EffectDuration, 5=-, 6=EffectLingerDuration/TailDuration/DebuffDuration, 7=AuraRadius/HotspotRadius/SkillRange, 8=HotspotLength, 9=-, 10=HotspotWidth1, 11=-, 12=SELF/HotspotIID, 13=HotspotHandle/SlowHotspotHandle/MarkHotspotHandle; values: [0x480009fa/0/0x48000294 ; 0/0x48000e60/0x48000a6b ; 0/0x480010dc/0x48000f1d ; 3/4/2 ; 0x | like CreateHotspot but on an entity: AuraRadius, out HotspotHandle |
| 0x10000134 | 0x15FD818 | 0x3C | SetMissileVelocity | M | 19/17 | `B O O` | ops: 0=SELF, 1=MissileCollisionSpeed/ReturnVelocity/CollisionVelocity | (missile, velocity) |
| 0x10000135 | 0x15FD330 | 0x24 | Unk_0135(-) | ? | 2/2 | `B O` |  | 2 uses |
| 0x10000136 | 0x15FD360 | 0x58 | TriggerSkillUsed? | L | 18/14 | `B r4 O O O` | ops: 0=TargetIID/DamageTargetIID/SELF, 1=TargetPosition, 2=SuperStrengthSkillSlot/SkillSlot; values: [0x1000001d/0x10000017] | (target, position, slot)[event 0x1000001D] |
| 0x10000137 | 0x15FD788 | 0xB8 | ResizeHotspot | M | 4/2 | `B O r4 O O O O O O` | ops: 0=HotspotIID, 1=-, 2=HotspotLength, 3=CurrentWidth/HotspotWidth, 4=HotspotHeight, 5=-, 6=FirewallHotspotHandle/MarkHotspotHandle/SlowHotspotHandle; values: [2] | (hotspot, -, length, width, height, -, handle)[2] |
| 0x10000138 | 0x15FD99C | 0x28 | Unk_0138(user)[3] | ? | 1/1 | `B O r4` | ops: 0=UserIID; values: [3] | 1 use |
| 0x10000139 | 0x15FAD34 | 0x40 | SetAIEnabled | M | 30/15 | `B O O r1` | ops: 0=SELF/TargetIID/AttachedIID, 1=AIHandle; values: [1/0] | (entity, out handle)[0 disable / 1 enable]: AIHandle |
| 0x1000013A | 0x15FE404 | 0x58 | PlayHitScriptlet? | L | 57/40 | `{B r4 O O {r4} r1 r1} r4` | ops: 0=SELF/TargetIID/EffectSource, 1=RootSubEntity, 2=IsSSInteractive/EffectSource/LanternIID, 3=VFXYaw; values: [0x100003ea/0x10000c18 ; 0/1/2 ; 0/0x100003ff/0x100007a8 ; 0/0x1000033e/1 ; 0/0x1e0000a4/0x1e000447 ; 0/0x1e000137/0x1e00013a ; 0x1e0001e8] | (entity, sub-entity, source, yaw)[0x100003EA, ..., status 0x1E..] C10 |
| 0x1000013B | 0x15FA818 | 0xC | OnEvent (filtered) | H | 339/305 | `r4` | values: [0x1000001d/0x10000023] | trigger [event 0x1000001D skill used / 0x10000023] |
| 0x1000013C | 0x15FAF14 | 0x20 | Unk_013C(SELF) trigger | ? | 1/1 | `O` | ops: 0=SELF | 1 use |
| 0x1000013D | 0x15FB0F4 | 0x40 | Unk_013D | ? | 0/0 | `B r4 O O` |  | unused |
| 0x1000013E | 0x15FCDFC | 0x90 | DashToEntity | H | 17/17 | `B O O O O r4 r1 r4 r1 O` | ops: 0=SELF/TargetIID, 1=TargetIID/SELF/TheStick, 2=DashVelocity/DashSpeed/ChargeVelocity, 3=DashHandle/TargetDashHandle, 4=DashStarted; values: [1/0/0.5 ; 0/1 ; 15/10/0 ; 0/1] | (entity, target, speed, out handle, out started)[...] |
| 0x1000013F | 0x15FE39C | 0x50 | Unk_013F | ? | 0/0 | `B r4 O O {r4}` |  | unused |
| 0x10000140 | 0x15FDABC | 0x38 | Unk_0140 predicate | ? | 0/0 | `O O` |  | unused C10 |
| 0x10000141 | 0x15FB604 | 0x28 | SetTeleportOffset? | L | 1/1 | `B O r1` | ops: 0=TeleportOffset | (offset)[0] C10 |
| 0x10000143 | 0x15FDB1C | 0x20 | IsStealthed? | L | 2/1 | `O` | ops: 0=TargetIID | (target) predicate, stealth script 0x34000304 |
| 0x10000144 | 0x15FDAEC | 0x24 | IsRevealed? | L | 2/1 | `O r1` | ops: 0=TargetIID; values: [1] | (target)[1] predicate, same script |
| 0x10000145 | 0x15FA068 | 0xC | Unk_0145 | ? | 0/0 | `` |  | unused |
| 0x10000146 | 0x15FDDA0 | 0x7C | FindValidPosition2 | L | 1/1 | `{B O O r1 r1 r1 r1 O r4 r4} O r1` | ops: 0=TargetPosition, 1=BackupPosition, 2=ScatterRadius; values: [0 ; 0 ; 0 ; 1 ; 0 ; 5] | variant of 0x10000025 |
| 0x10000147 | 0x15FAE84 | 0x3C | GetSourcePosition? | L | 1/1 | `B O O` | ops: 0=SourcePosition | (out position, -) |
| 0x10000148 | 0x15FCCDC | 0x58 | SetTargetingMode | M | 2/2 | `B O O r4 O` | ops: 0=TargetingMode/SkillTargetingMode, 1=-, 2=SkillSlot; values: [0/0xffffffff] | (mode, -, slot)[0/-1] C10 |
| 0x10000149 | 0x15FDEC0 | 0xA8 | AddDamageRedirect | M | 2/2 | `{B r4 O O r1 O} O O r4 O` | ops: 0=RedirectPercentage/DamageReflection, 1=-, 2=-, 3=RedirectHandle/VitalRedirectHandle, 4=-, 5=LinkedEntity; values: [2 ; 1 ; 5/2] | (percent, -, -, out handle, -, linked entity)[...] |
| 0x1000014A | 0x15FD270 | 0x3C | RemoveDamageRedirect | M | 2/2 | `B O O` | ops: 0=SELF, 1=RedirectHandle/VitalRedirectHandle | (entity, handle) |
| 0x1000014B | 0x15FB274 | 0x2C | SetCameraMode? | L | 16/8 | `B O r1 r4` | ops: 0=SELF/TargetIID; values: [1/0 ; 5] | (entity)[0/1, 5] recall |
| 0x1000014C | 0x15FD1B4 | 0x3C | StartAITask? | L | 7/3 | `B O O` | ops: 0=WallIID, 1=TaskHandle/ReactionHandle | (entity, out task handle) C10 |
| 0x1000014D | 0x15FC89C | 0x40 | StartAITask2? | L | 3/3 | `B O r4 O` | ops: 0=WallIID, 1=TaskHandle/ReactionHandle; values: [0x3f000003/0x3f000006/0x3f000009] | (entity, -, out handle)[task 0x3F.. record] C10 |
| 0x1000014E | 0x15FC80C | 0x90 | Unk_014E | ? | 0/0 | `B r4 r4 r4 O O O O r4 r4 r4 r4 r4 r4` |  | unused |
| 0x10000150 | 0x15FD544 | 0x40 | ShowMinimapTargetingRing2 | X | 7/3 | `B r4 O O` | ops: 0=PredatorIID/SELF/ctx0xd0; values: [1/0xffffffff/2] | (entity, -)[mode]; client execute sends GM_MapManager.RecvNotice_ShowMiniMapTargetingRing C10 |
| 0x10000151 | 0x15FA7B8 | 0xC | Unk_0151 (missile) | ? | 6/6 | `r4` |  | no fields, 6 uses |
| 0x10000152 | 0x15FC47C | 0x24 | GetMatchTime | M | 1/1 | `B O` | ops: 0=MatchTime | (out time) |
| 0x10000153 | 0x15FD454 | 0x2C | SetSkillStatOverride | L | 19/15 | `B O r4 r4` | ops: 0=ZeroCost/OriginalRange/CastRadius; values: [0xffffffff/5/1 ; 18/23/3] | (value)[slot, stat id 3 cost / 18 range / 23 radius] |
| 0x10000154 | 0x15FCB5C | 0xE8 | LaunchLobbedMissile | M | 16/13 | `{B r4 O O O O O O r4 O O r1 r1 r4} r4 r4 r1` | ops: 0=SELF/ObjectIID/LootIID, 1=TargetPosition/BestPosition/ChosenPosition, 2=StraightUpDistance, 3=MissileSpeed/Velocity/MissileVelocity, 4=TheStick, 5=MissileOffset/MissileFireOffset/FireOffset, 6=KnockBackHandle/ctx0xd8, 7=SuperStrengthSkillSlot; values: [0/0x4000020a/0x40000209 ; 0/0x34000160/0x34000299 ; 1/0 ; 1/0 ; 2/7 ; 0/90/70 ; 0/3/3.25 ; 0/1] | LaunchMissile with a ballistic path (StraightUpDistance) / thrown objects |
| 0x10000155 | 0x15FE0D4 | 0x34 | SetEntityProperty | M | 26/23 | `B O {r4}` | ops: 0=SELF/TargetIID/EffectSource, 1=HitEffectDID/IsPhasing/WarningStateCurrent, 2=BillboardIcon/IsActive/SIDIconDID, 3=UseVFX; values: [1/3/2 ; 0x10000ac2/0x10000cc0/0x10000d87 ; 0x100001fc/0x10000b94/974 ; 0x10000433/0x10000b96] | (entity, value)[count, property 0x10..] C10 |
| 0x10000157 | 0x15FC6EC | 0x44 | Unk_0157 | ? | 0/0 | `B r4 r1 O O` |  | unused |
| 0x1000015C | 0x15FBB44 | 0x3C | Unk_015C | ? | 0/0 | `B O O` |  | unused |
| 0x1000015D | 0x15FBB74 | 0x3C | Unk_015D | ? | 0/0 | `B O O` |  | unused |
| 0x1000015E | 0x15FA2D8 | 0x8 | UI_Condition_015E | ? | 2/1 | `` |  | trigger in the UI flow script C10 |
| 0x10000160 | 0x15FC17C | 0x24 | Unk_0160 | ? | 0/0 | `B O` |  | unused |
| 0x10000161 | 0x15FC74C | 0x24 | Unk_0161 | ? | 0/0 | `B O` |  | unused |
| 0x10000162 | 0x15FD7B8 | 0x44 | SetDefeatType / Invincible | L | 13/6 | `B O O r1 r4` | ops: 0=DefeatTypeHandle/DefeatTypeStateHandle/HandleInvincible, 1=SELF/TargetIID; values: [0/1 ; 0/5/100] | (out handle, entity)[0/1, 0/5/100] |
| 0x10000163 | 0x15FC23C | 0x38 | Unk_0163 predicate | ? | 0/0 | `O O` |  | unused |
| 0x10000164 | 0x15FC20C | 0x20 | Unk_0164 predicate | ? | 0/0 | `O` |  | unused |
| 0x10000165 | 0x15FCC7C | 0x54 | Unk_0165 | ? | 0/0 | `B O O O` |  | unused; client code references 0x10000089 C10 |
| 0x10000166 | 0x15FCD0C | 0x40 | Unk_0166 | ? | 0/0 | `B O r4 O` |  | unused; client code references 0x1000007C C10 |
| 0x10000167 | 0x15FD93C | 0x38 | NotifyHUDElement | X | 47/4 | `B O r4 r4 r4 r4 r1` | values: [49/51/1 ; 9/7/8 ; 0/39/45 ; 0/0x480003cb/0x40000086] | (-)[element, action 7 highlight / 8 clear / 9 / 10 ..., hint, record, 0]; client execute sends GM_UI.RecvNotice_NotifyHUDElement (tutorial) C10 |
| 0x10000168 | 0x15FE33C | 0x40 | StartAITask3? | L | 2/1 | `B r1 r4 O r4 {r4}` | ops: 0=TaskHandle, 1=lit, 2=lit, 3=lit, 4=lit, 5=lit, 6=lit; values: [1/0 ; 0x3f000007/0 ; 0x100000ed/0xffffffff ; 3/0] | (out task handle, #params...)[task 0x3F000007, ...] C10 |
| 0x10000169 | 0x15FB214 | 0x28 | SetCharges | L | 3/3 | `B O r4` | ops: 0=ChargeCount; values: [2/1/3] | (charge count)[slot] |
| 0x1000016A | 0x15FE27C | 0x68 | UpdateStatusIconStats | L | 41/32 | `B O O O r4 {r4}` | ops: 0=SIDHandle/StatusIconHandle, 1=SELF, 2=SourceEntityDID, 3=AttributeCurrentValue/Stat1_CurrentValue/CurrentBonus, 4=AttributeMaxValue/Stat1_Max/MaxBonus, 5=AttributePerTickIncrease/Stat2_CurrentValue/Bonus, 6=MaxStacks_CurrentBonus/Stat2_Max/AttackSpeed_StackBonus, 7=AttackSpeed_CurrentBonus, 8=AttackSpeed_MaxBonus; values: [0/0x480008a6/0x480008a5 ; 1/4/2 ; 1/3/5 ; 0x100007dc/0x100007de/0x10000b76 ; 3/4/1 ; 0x1 | (handle, entity, SourceEntityDID, values...)[...] |
| 0x1000016B | 0x15FB1E4 | 0x28 | GetCharges | L | 3/3 | `B O r4` | ops: 0=ChargeCount; values: [2/1/3] | (out charges)[slot] on exit |
| 0x1000016C | 0x15FDEF0 | 0x58 | Unk_016C | ? | 0/0 | `B O O O r4` |  | unused |
| 0x1000016D | 0x15FBB14 | 0x3C | Unk_016D | ? | 0/0 | `B O O` |  | unused |
| 0x1000016E | 0x15FD0C8 | 0x24 | GetCurrentRange? | L | 3/2 | `B O` | ops: 0=CurrentRange | (out range) C10 |
| 0x1000016F | 0x15FCF48 | 0x50 | IsInFront? | L | 5/4 | `O O O` | ops: 0=TargetIID, 1=-, 2=SELF | (target, -, SELF) predicate |
| 0x10000171 | 0x15FBA84 | 0x24 | Unk_0171 | ? | 0/0 | `O r1 r1 r1` |  | unused |
| 0x10000172 | 0x15FBE18 | 0x3C | Unk_0172 | ? | 1/1 | `B O O` |  | 1 use |
| 0x10000173 | 0x15FB244 | 0x24 | RandomChance | M | 4/2 | `r4 O` | values: [0.5/0x3eb33333] | (-)[probability 0.5 / 0.35] predicate C10 |
| 0x10000174 | 0x15FC9E4 | 0x4C | Unk_0174 | ? | 1/1 | `B O O {r4}` | ops: 0=-, 1=SELF; values: [1] | 1 use |
| 0x10000175 | 0x15FC3EC | 0x1C | Unk_0175 | ? | 0/0 | `B {r4}` |  | unused |
| 0x10000177 | 0x15FE248 | 0x54 | LoadStatusStats | M | 26/25 | `B O {r4} O r4 r4` | ops: 0=-, 1=AttributePerTickIncrease/StackMax/BonusPerPercentMissing, 2=MaxStacks_Bonus/StackIncrement/MaxBonus, 3=TickMax/PercentRemoveOnDeath/TempVitalAmount, 4=TickIncrement/StackDuration/ShieldHealth_Delta, 5=TickDuration/ResurrectWillPercent/StackIncrement_Tick, 6=ResurrectPAPercent/StackIncrement_BasicAttack, 7=ResurrectAAPercent; values: [3/2/1 ; 12/5/32 ; 0/7/31 ; 0/32/11 ; 0/31/14 ; 0/14/39 ; 0/40/15 ; 0/42] | (owner, out vars...)[count, stat ids]: like LoadSkillStats for status records |
| 0x10000178 | 0x15FC3BC | 0x1C | Unk_0178 | ? | 0/0 | `B {r4}` |  | unused |
| 0x10000179 | 0x15FA0F8 | 0xC | UI_SetHUDVisibility | X | 1/1 | `` |  | client execute sends GM_UI.RecvNotice_UpdateHUDVisibility C10 |
| 0x1000017A | 0x15FB064 | 0x54 | Unk_017A | ? | 0/0 | `B O O O` |  | unused |
| 0x1000017B | 0x15FC0EC | 0x20 | TutorialStep? | L | 14/7 | `B {r4} r1 r1 r1` | values: [0/1 ; 1/516/957 ; 1/0 ; 0/1] | [0/1, conversation/step id, ...] in tutorial scripts C10 |
| 0x1000017C | 0x15FAF74 | 0x20 | Unk_017C predicate | ? | 0/0 | `O` |  | unused |
| 0x1000017D | 0x15FA1E8 | 0x10 | OnTutorialEvent | L | 9/3 | `{r4} r4` | values: [0x1000017f ; 2/3/8] | trigger [0x1000017F, step] C10 |
| 0x1000017E | 0x15FDC3C | 0x34 | SetDestructibleState? | L | 2/1 | `B O {r4}` | ops: 0=SunstoneIID; values: [3 ; 0 ; 1 ; 0 ; 1/-1 ; 0 ; 0 ; 0 ; -1] | (entity)[...]; client references Destructible_OnBreak keys 0x1000051E/F C10 |
| 0x1000017F | 0x15FD574 | 0x40 | SetSkillComboState? | L | 17/4 | `B r4 O O` | ops: 0=KatanaW/KatanaQQ/KatanaQW, 1=ctx0xd0; values: [7/2/6] | (var, -)[7] Katana |
| 0x10000180 | 0x15FBCF4 | 0x24 | Unk_0180 | ? | 0/0 | `B O` |  | unused |
| 0x10000181 | 0x15FC38C | 0x1C | TutorialSetup_0181 | L | 3/2 | `B {r4}` | values: [1 ; 0/0x400004ad] | [1, 0 / class 0x400004AD]; tutorial C10 |
| 0x10000182 | 0x15FA428 | 0x10 | TutorialSetup_0182 | L | 2/2 | `B r1 r1` |  | [0, 0]; tutorial C10 |
| 0x10000183 | 0x15FC41C | 0x20 | ActivateArtifacts? | X | 1/1 | `B {r4} r1` | values: [1 ; 0x400004ad] | [1, class, 0]; client execute sends GM_Upgrade.RecvNotice_ActivatedArtifacts C10 |
| 0x10000184 | 0x15FC56C | 0x24 | Unk_0184 predicate | ? | 0/0 | `O r4` |  | unused C10 |
| 0x10000185 | 0x15FB154 | 0x58 | Unk_0185 | ? | 0/0 | `B O O O r1` |  | unused |
| 0x10000186 | 0x15FA098 | 0xC | Unk_0186 | ? | 1/1 | `` |  | 1 use |
| 0x10000187 | 0x15FB8D4 | 0x24 | GetPlayer | M | 4/4 | `B O` | ops: 0=PlayerIID | (out player) C10 |
| 0x10000188 | 0x15FB724 | 0x3C | GetAgent | M | 3/3 | `B O O` | ops: 0=AgentIID, 1=PlayerIID | (out agent, player): the player's champion C10 |
| 0x10000189 | 0x15FA968 | 0xC | Unk_0189 | ? | 1/1 | `` |  | 1 use |
| 0x1000018A | 0x15FA3F8 | 0xC | IsChampion(class) trigger | L | 1/1 | `r4` | values: [0x40000086] | [0x40000086 Gaslight Batman] C10 |
| 0x1000018C | 0x15FA728 | 0xC | Unk_018C[r4] | ? | 0/0 | `r4` |  | unused C10 |
| 0x1000018D | 0x15FA578 | 0x10 | Unk_018D | ? | 0/0 | `B r1` |  | unused |
| 0x1000018E | 0x15FB184 | 0x44 | Unk_018E | ? | 0/0 | `B O O r4 r4` |  | unused |
| 0x1000018F | 0x15FA158 | 0xC | UI_ExitWorldLoadWrapper | X | 2/1 | `` |  | client execute: gmUIStateMachine::LoadWrapperOnlyRPs C10 |
| 0x10000190 | 0x15FB574 | 0x54 | Unk_0190 | ? | 0/0 | `B O O O` |  | unused C10 |
| 0x10000191 | 0x15FC86C | 0x54 | Unk_0191(-, pos, pos) | ? | 1/1 | `B O O O` | ops: 0=-, 1=TestPosition, 2=TargetPosition | 1 use C10 |
| 0x10000193 | 0x15FA548 | 0x18 | Unk_0193 | ? | 0/0 | `B r4 r4 r4` |  | unused |
| 0x10000194 | 0x15FA698 | 0x10 | Unk_0194 | ? | 0/0 | `B r1` |  | unused |
| 0x10000195 | 0x15FD3F0 | 0x24 | SkillEcho? | L | 218/214 | `B O` |  | (-) after SkillEchoMultiplier in 214 skills |
| 0x10000197 | 0x15FAD04 | 0x28 | Unk_0197 | ? | 0/0 | `B r4 O` |  | unused |
| 0x10000198 | 0x15FBDE8 | 0x40 | Unk_0198 | ? | 0/0 | `B O O r1` |  | unused C10 |
| 0x10000199 | 0x15FE2AC | 0x34 | Unk_0199 | ? | 0/0 | `B O {r4}` |  | unused |
| 0x1000019B | 0x15FC2CC | 0x28 | BreakDestructible? | L | 1/1 | `B O r1` | ops: 0=SELF; values: [1] | (entity)[1]; client references 0x10000C1D (Dest_OnBreak... key) C10 |
| 0x1000019C | 0x15FAE54 | 0x3C | Unk_019C | ? | 0/0 | `B O O` |  | unused |
| 0x1000019D | 0x15FD90C | 0x58 | Unk_019D | ? | 0/0 | `B O O O r4` |  | unused C10 |
| 0x1000019E | 0x15FAD94 | 0x40 | Unk_019E | ? | 0/0 | `B O O r4` |  | unused |
| 0x1000019F | 0x15FB004 | 0x40 | Unk_019F | ? | 0/0 | `B O O r1` |  | unused |
| 0x100001A0 | 0x15FC71C | 0x54 | Unk_01A0 | ? | 0/0 | `B O O O` |  | unused |
| 0x100001A2 | 0x15FA4E8 | 0xC | Unk_01A2[r4] | ? | 0/0 | `r4` |  | unused C10 |
| 0x100001A3 | 0x15FD96C | 0x58 | ShowTrainingFloatyText | X | 2/1 | `B O r4 r4 r4 {r1 r4 r4 {V V V V *loop} {r1}} r1` | ops: 0=SELF; values: [4 ; 5 ; 0/-0.25 ; 0 ; 0/0xc331c8b ; 0/0x2b0001c6 ; 0 ; 0 ; 0/1] | (entity)[...]; client execute sends GM_UI.RecvNotice_UpdateTrainingFloatyText C10 |
| 0x100001A4 | 0x15FA518 | 0xC | Unk_01A4[r4] | ? | 0/0 | `r4` |  | unused C10 |
| 0x100001A5 | 0x15FB7B4 | 0x3C | SetLatencyWindow? | L | 1/1 | `B O O` | ops: 0=-, 1=LatencyWindow | (-, value) |
| 0x100001A6 | 0x15FB124 | 0x44 | Unk_01A6 | ? | 0/0 | `B O r4 r1 O` |  | unused |
| 0x100001A7 | 0x15FA8A8 | 0x10 | Unk_01A7[0/1] | ? | 2/1 | `B r1` | values: [1/0] | 1 script |
| 0x100001A9 | 0x15FC08C | 0x28 | SetHidden? | L | 6/2 | `B O r1` | ops: 0=SELF/TargetIID; values: [1/0] | (entity)[0/1] recall / stealth |
| 0x100001AA | 0x15FC68C | 0x9C | Unk_01AA | ? | 0/0 | `B {r1 r4 r4 {V V V V *loop} {r1}} O O O` |  | unused C10 |
| 0x100001AB | 0x15FD098 | 0x3C | Unk_01AB | ? | 0/0 | `O O r4` |  | unused C10 |
| 0x100001AC | 0x15FD9FC | 0x54 | Unk_01AC | ? | 0/0 | `B O O O` |  | unused C10 |
| 0x100001AD | 0x15FD3C0 | 0x40 | Unk_01AD(target, -)[14] | ? | 2/2 | `B O O r4` | ops: 0=TargetIID; values: [14] | 2 uses C10 |
| 0x100001AF | 0x15FCE58 | 0x40 | Unk_01AF(entity, -)[0] | ? | 12/12 | `B O O r4` | ops: 0=SELF | 12 uses after ApplySkill |
| 0x100001B0 | 0x15FACD4 | 0x30 | SpawnFromShooter? | L | 1/1 | `B r4 r4 r4 O` | ops: 0=ShooterIID; values: [0x40000e96 ; 1 ; 1] | (entity)[class 0x40000E96, 1, 1] |
| 0x100001B1 | 0x15FA218 | 0xC | Unk_01B1[2] predicate | ? | 1/1 | `r4` | values: [2] | 1 use C10 |
| 0x100001B2 | 0x15FADF4 | 0x40 | Unk_01B2 | ? | 0/0 | `B O O r4` |  | unused |
| 0x100001B3 | 0x15FAFD4 | 0x44 | SetLane | L | 2/1 | `B O O r1 r4` | ops: 0=SELF, 1=LaneAssignment; values: [0/1] | (entity, lane)[0/1] |
| 0x100001B4 | 0x15FB1B4 | 0x6C | Unk_01B4 | ? | 0/0 | `B O O O O` |  | unused |
| 0x100001B6 | 0x15FAD64 | 0x3C | GetLane | L | 2/1 | `B O O` | ops: 0=SELF, 1=CurrentLane | (entity, out lane) |
| 0x100001B7 | 0x15FA998 | 0x8 | UI_Condition_01B7 | ? | 1/1 | `` |  | UI flow script C10 |
| 0x100001B8 | 0x15FBFFC | 0x28 | Unk_01B8(-)[0/1] | ? | 2/1 | `B O r1` | values: [1/0] | 1 script C10 |
| 0x100001B9 | 0x15FD6F8 | 0x24 | Unk_01B9(-) | ? | 1/1 | `B O` |  | 1 use |
| 0x10000000 | - | - | (not registered in the client) | ? | 1 | - | - | 1 use; the client build has no class for it (server-only node) |
| 0x10000001 | - | - | (value-registry type, see V table) | ? | 0 | - | - | registered only in the value registry 0x45FAA0 |

`C10` = the class has a client-side execute (vtable slot 10), so the client runs it in client-side HFSMs (e.g. the UI flow script 0x34000000).

## Event ids (values of builtin 0x06 Event; inferred)

| event | listened in | meaning (inferred) |
|---|---|---|
| 0x10000006 | 490 | status applied / script started with parameters (ApplySkill) |
| 0x10000003 | 312 | status removed / duration ended |
| 0x10000008 | 367 | re-initialise skill (in every skill's listener list: rank / level / stats changed?) |
| 0x100001B3 | 334 | same listener list as 0x10000008 |
| 0x1000000C | 155 | same listener list as 0x10000008 |
| 0x10000009 | 263 | interrupt / cancel: any -> cleanup state |
| 0x1000001D | 74 | skill used (also via 0x1000013B) |
| 0x10000002 | 15 | collision (parameters Collider, SubEntity, EntityPosition) |
| 0x10000126 | 29 | basic-attack shot arrived (raised by the shot tracker) |
| 0x10000141 | 54 | raised 42 times with RaiseEvent: a hit / damage notification |
| 0x10000140 | 23 | raised 17 times with RaiseEvent |
| 0x10000186 | 26 | conversation finished (after StartConversation) |
| 0x10000060 | 13 | cinematic scene frame reached (scene timeline) |
| 0x1000007C | 15 | team member added (TrackTeamEvents) |
| 0x1000007B | 15 | team member removed (TrackTeamEvents) |
| 0x10000085 | 7 | match / encounter phase start (match-rule script 0x340002CF) |

## Coverage

Action classes: 343 registered. Confidence: X 17, H 61, M 46, L 86, ? 133. 239 of them are used by the player's decoded scripts; most "?" rows are classes no script uses (their Unpack signature is the only information).
