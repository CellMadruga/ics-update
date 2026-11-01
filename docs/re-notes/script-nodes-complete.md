# Server-script (0x34) nodes: complete catalogue, decoder failures, runtime gaps (2026-10-21)

Static analysis of `InfiniteCrisis.exe` (capstone; image base 0x400000) plus the Unicorn decoder of
`tools/script_decoder.py`, run from a patched scratch copy (the project's decoder was not edited). Builds on
`docs/re-notes/script-nodes-names.md` (names, Unpack signatures, client-side execute per class), which stays the
reference for each class's operands; this file adds the full usage counts over **all 875** records, the
runtime's support (`ics/script_runtime.py` as of today) and what blocks each root. Confidence: **confirmed** =
exe code or exact decode; **probable** = inferred from data.

## 1. Why 80 of the 875 records have no usable tree, and the exact fixes

State today (`data/script_trees`): 826 files, 795 `ok`, 31 `fail`; 49 records have no file. With the four fixes
below, a patched copy of the decoder decodes **875 of 875** (`ok`). 793 of the 795 previously decoded trees come
out identical (same bytes consumed, same nodes); the other 2 change for the better (fix C).

### Fix A: the record finder rejects valid headers (49 missing records; confirmed)

`records()` accepts an occurrence of the DID only when it is followed by `n | 1 | 0 | 0 | 0` (n < 64): one graph
whose three chain slots are empty. Real records also start with:
- a graph whose first chain slots are not empty: `did | 1 | 1 | 7 | 3 ...` (an IfThenElse in the enter chain),
  `did | 1 | 1 | 0x1000009F ...`, `did | 2 | 1 | 0x10000103 ...`, `did | 3 | 1 | 0x100000A5 ...`,
  `did | 1 | 1 | 0x1000009C ...` (cinematic scene scripts), `did | 1 | 1 | 0 | 0 | 0x1000017B ...`;
- a top-level **state** instead of a graph (graph-registry type 2): `did | 1 | 2 | ...` (0x34000441, 0x340007E5).

**Fix:** accept `did | n | t` with `0 < n < 64` and `t in (1, 2)`, decode every such occurrence and keep the one
that returns `ok` (largest consumption first). 46 of the 49 decode with this alone; 0x340001CF, 0x340005D8 and
0x340007B7 also need fix B. The three DIDs named in the task: 0x3400077A (pack 0xA0000384, at +271840,
`2 | 1 | 0x100000A5 ...`, 3468 bytes), 0x34000777 (same pack, +164076, 2240 bytes), 0x340007A2 (pack 0xA0000303,
+1629788, `3 | 1 | 0 | 0 | 0x1000002D`, 3136 bytes).

### Fix B: expression types 0xC and 0x10 are registered in the client after all (24 failures + 3 of the above; confirmed)

The decoder finds the static initializers with the byte pattern `C7 45 F4 imm | C7 45 F8 imm | C7 45 FC imm`
(type, factory, size). For the two expression types whose id equals their object size the compiler wrote
`mov eax, imm; mov [ebp-0xC], eax; mov [ebp-4], eax; mov [ebp-8], factory`, so the pattern misses them, they never
run, and `_server_only_expressions` fakes both with the binary `-` factory (0x468300). Scanning every
`call 0x45FA20` in 0x13A0000-0x13D0000 instead finds 447 registrations = the 445 the pattern finds + these two:

| type | initializer | factory | size | vtable | evaluate (slot 10) | meaning |
|---|---|---|---|---|---|---|
| 0x0C | 0x13A67D0 | 0x465F20 | 0xC (unary) | 0x15A9408 | 0x462710: child, then `sub` (0x4538D0) of the type's 1 (0x456520) | **decrement, x - 1** (registered right after `++` 0x17, whose evaluate is the same with `add` 0x4532A0) |
| 0x10 | 0x13A6710 | 0x465D20 | 0x10 (binary) | 0x15A92B8 | 0x462570: evaluate left; if its bool byte is set return it, else evaluate and return right | **short-circuit logical OR** (registered right after `!` 0x24 and before `&&` 0x13, whose evaluate 0x4625F0 is the AND mirror) |

So 0x10 was decoded right by luck (same layout as `-`) and 0xC was not: as a binary node it swallowed the next
node's type word as its right operand. Every record that uses 0xC failed (24: 0x34000048, 0x3400018C, 0x3400019D,
0x34000201, 0x34000216, 0x3400022E, 0x34000237, 0x34000243, 0x340002B4, 0x340002BB, 0x340002BF, 0x34000342,
0x340003BC, 0x340003D7, 0x340003E6, 0x340004DC, 0x34000531, 0x3400054D, 0x3400056D, 0x34000581, 0x340005AB,
0x340005B6, 0x34000687, 0x340006D6). The data pattern agrees: `X = 0xC(X)` guarded by `X > 0` (0x340002BF,
0x340006D6) or followed by `X == uint(Y)` (counters).

**Fix:** add 0x13A6710 and 0x13A67D0 to the initializer list (better: find initializers by their `call 0x45FA20`,
not by the store pattern), and delete `SERVER_ONLY_EXPRESSIONS` / `_server_only_expressions`. The trees then
label them `builtin:0xc` (vt 0x15A9408) and `builtin:0x10` (vt 0x15A92B8) instead of `server-expr:...`, so
`ics/script_runtime.py` must key them by vt: `0x15A92B8` = or, `0x15A9408` = x - 1. Its current
`SERVER_EXPR["server-expr:0xc"] = "/"` is wrong. The notes "0xC / 0x10 server-only" in
`docs/reverse-engineering.md` and `script-nodes-names.md` should be corrected.

### Fix C: variable default values, bool slots (6 failures + 2 silent misreads; confirmed)

Variable blocks in the packs carry server-only default values that the decoder skips by searching for the name
table `1 | 0 | n | n x (hash, slot)`. The search requires `slot % 4 == 0`, but **bool variables (type 0) take one
byte and have odd slots** (0x59, 0x2D, 0x39, 0x41, 0x75 ...). When the table is not found the fallback sizes
are used, and those are wrong for two types. Measured over all blocks (least squares, rank 12, plus the single-type
blocks): types 0, 1, 2, 3, 4 = 1 word; 7, 8, 0xD, 0xE = 2; 9 = 3; **0xA = 1 word when its first word is 0, else 3
words beginning with 0xCB**; **0xC = 5 words** (`0 | hash | 0x2B... table DID | 0 | 0`, 0x34000778).

**Fix:** drop the `% 4` test (keep `slot < 0x1000`) and use the sizes above in the fallback. Records fixed:
0x340001F8, 0x3400038E, 0x34000543, 0x3400067C, 0x34000726, 0x340007A1. It also corrects 0x34000095 and
0x340000DF, which decoded "ok" with a name table matched two words early (wrong variable names / slots; 18 words
are skipped now instead of 16).

The same size table is in `ics/script_runtime.py` (`DEFAULT_WORDS`, 0xA = 3 always, 0xC missing): every variable
after a type-0xA default whose first word is 0 gets a shifted default (probable source of wrong defaults in about
60 blocks).

### Fix D: counts of 128 or more (1 failure; confirmed)

0x34000890 has a DebugLog node (builtin 0x0C) with a 163-character text. The client's count reader 0x421430 is
compact: one byte < 0x80; `10xxxxxx` + 1 byte; `110xxxxx` + 1 byte + 2 bytes; `111xxxxx` + a u32. The packs store
the count as a whole word (0xA3), so the client reads 0xA3, then a second byte from the next word ('Y' = 0x59),
and takes 0x2359 = 9049 characters. **Fix:** when a read returns to 0x421444 and the word there is >= 0x80, hand
the client a prefix byte 0xE0 and, on the following read (return 0x421465), the word itself, advancing the stream
by one word. Only this record has such a count.

### Records recovered, and who uses them

`*` = had no tree file; letters = roots that name the script directly (C champion skill, SP Stolen Power,
I item active, ST status effect, U unit attack).

0x34000048(C,U) 0x34000153*(ST) 0x3400018C(C) 0x3400019D(SP) 0x340001CF*(ST) 0x340001F8(C) 0x340001FA*
0x34000201(C) 0x34000216(C,U) 0x3400022E(ST) 0x34000237(C,U) 0x34000243(C) 0x340002B4(C) 0x340002BB(SP)
0x340002BF(ST) 0x34000342(C) 0x34000350*(ST) 0x3400038E(C) 0x340003BC(I) 0x340003D1* 0x340003D7(C) 0x340003E6(C,U)
0x34000441*(ST) 0x34000462* 0x340004DC(C) 0x340004F6* 0x340004F8* 0x340004F9* 0x340004FA* 0x340004FB* 0x340004FC*
0x34000501* 0x34000502* 0x3400050F* 0x34000510* 0x34000523* 0x34000531(C) 0x34000538* 0x34000543(ST) 0x3400054D(C)
0x3400056D(C) 0x34000581(C) 0x340005AB(C) 0x340005B6(C) 0x340005D8* 0x340005DF* 0x340005E5* 0x340005F4* 0x34000602*
0x34000604* 0x34000605* 0x3400060A* 0x3400066E*(ST) 0x34000671* 0x3400067C(C) 0x34000687(ST) 0x340006A2* 0x340006A3*
0x340006A4* 0x340006A5* 0x340006A8* 0x340006A9* 0x340006D6 0x340006E5* 0x340006F2* 0x34000726(C) 0x34000732*
0x34000733* 0x3400076B* 0x3400076C* 0x34000777*(C,U) 0x3400077A*(C) 0x340007A1(C) 0x340007A2*(C,U) 0x340007B7*(ST)
0x340007BD*(ST) 0x340007C0*(ST) 0x340007D0*(ST) 0x340007E5*(ST) 0x34000890(ST)

Note: `ics/script_model.load` also loads today's 31 `fail` trees; they are truncated where the reader stopped, so
those scripts run with missing states / transitions.

## 2. Roots and coverage method

Roots (all decoded with the fixes):
- **C** champion skills: `catalog/data/skills.tsv` rows with a script, champion not "(Stolen ...)": 323 rows, 323 scripts.
- **SP** Stolen Powers: `stolen_powers.tsv` rows plus the "(Stolen" rows of `skills.tsv`: 65 rows, 12 scripts.
- **I** item actives: `artifacts.tsv` active_skill -> `Data.item_skill`: 32 items, 23 scripts.
- **ST** status effects: every 0x48 record with property 0x10000242 (pack scan, owner = nearest preceding
  `0x48.. | 0 | count` header): 354 records, 299 scripts.
- **U** unit attacks: every 0x49 template with property 0x10000328: 308 templates, 85 scripts.

Two measures per unimplemented class:
- **sim** = `tools/script_coverage.py`'s logic: each root run in `NullWorld` for 8 s (skills via `use_skill`,
  statuses via `apply_status`), with missiles and statuses resolved from the packs; a class counts when the run
  hits it (the runtime's `unknown`). Run with today's runtime plus two in-process patches so the new labels do not
  regress (vt 0x15A92B8 = or, 0x15A9408 = x - 1).
- **static** = the class appears anywhere in the root's closure (its script, every status 0x48 any node names
  except RemoveStatus / HasStatus, every entity class 0x40 with its template scripts, every 0x34 named). This is
  an upper bound; "sole blocker" = roots whose closure lacks only this class.

Results: sim clean (no unknown node) C 116 / 323, SP 0 / 65, I 9 / 32, ST 112 / 354, U 121 / 308; 6 crash with
RecursionError (C 0x48000883:5, 0x48000F5F:1, 0x48000E69:2; U 0x49000553, 0x4900091D, 0x49000CD4). Static clean:
C 15, SP 0, I 5, ST 7, U 9 (closures pull in many statuses). (Today's coverage tool reports 130 / 325 champion
skills clean on the old trees; the drop comes from the 80 scripts that now decode in full.)

## 3. Runtime problems found on the way (not node gaps)

- **Triggers inside condition lists:** `Region.matches` handles 0x10000019 (cast signal), 0x1000013B and
  0x10000055 (events) only as a transition's direct trigger. Inside AnyOf / AllOf / NodeCondition they reach
  `predicate()` and count as unknown (false): 0x1000013B in 46 roots (C20 SP11 I12 U3), 0x10000019 in 13 C.
- 0x100000B1 (OnAttributeChanged, trigger `[0x100000A2, attribute]`) is the only thing stopping all 65 Stolen
  Power roots in simulation (with 0x10000015 / 0x100000DF next).
- Expression `builtin:0x33` is **negate** (x * -1), not a type conversion; `builtin:0x41` is RotateByHeading
  (rotate a vector by an angle), not "position + offset" (both in `evaluate`).
- Expression 0x19 (names file: "decrement?") evaluates `floor(x + one / two)` (0x457BD0: 0x4568F0 = 2,
  0x456520 = 1, 0x457530 divide, 0x4532A0 add, 0x4552B0 floor): **round to nearest** (probable).
- `DEFAULT_WORDS` (see fix C) and `SERVER_EXPR` 0xC (see fix B).
- Builtin node 0x12 (vt 0x15A88E0, Unpack `B r4 O`) is always read as a chain / slot / sub node (7 nodes in
  0x34000162, 0x340001BF, 0x340001C4 (Consume), 0x34000347, 0x34000598, 0x340007EC), never as an expression, yet
  `evaluate` treats this vt with two values as `>=`; as a node it is unknown (SP6 ST1 U1 in sim). Recheck the
  ">=" note in `docs/reverse-engineering.md` (fase3-fp).

## 4. Every node class used by the 875 scripts

325 classes, keyed by vtable (ids collide between registries): 2 graph-registry, 268 node-registry (builtins
0x01-0x18 and actions 0x100000xx), 55 expression-registry. Columns: `sig` = Unpack signature (B next node,
O operand value|source|slot, rN raw, {..} helper), operand meanings are in `script-nodes-names.md`; `used as` =
the reader that reads the node (chain = next node of a chain, slot = first node of a state's enter / update / exit
chain, trigger = transition trigger, sub / cond = IfThenElse / loop / list children, assign / lhs / rhs / arg =
expression operands); `runtime` = `ics/script_runtime.py` today (yes / stub / no); last two columns as in part 2
(C champion, SP Stolen Power, I item, ST status, U unit). `C10` in the names file = the class has a client-side
execute (vtable slot 10); the server has to do the rest.


### Graph registry 0x44E240

| id | vt | name | conf | sig | nodes / scripts | used as | runtime | roots blocked (static) | roots hit (sim) |
|---|---|---|---|---|---|---|---|---|---|
| 0x1 | 0x15A8218 | Graph (composite state) | H | `` | 1713 / 873 | item 1713 | yes |  |  |
| 0x2 | 0x15A7F98 | State | H | `` | 5334 / 875 | item 5334 | yes |  |  |

### Node registry 0x44E410 (builtins, then actions / predicates / triggers)

| id | vt | name | conf | sig | nodes / scripts | used as | runtime | roots blocked (static) | roots hit (sim) |
|---|---|---|---|---|---|---|---|---|---|
| 0x01 | 0x15A89C0 | Assign | H | `B O r4` | 3074 / 613 | chain 1950, sub 698, slot 426 | yes |  |  |
| 0x02 | 0x15A8880 | StartTimer | H | `B O O` | 389 / 231 | chain 205, slot 114, sub 70 | yes |  |  |
| 0x03 | 0x15A8764 | ExpressionCondition | H | `r4` | 1817 / 499 | cond 1079, sub 356, chain 221 | yes |  |  |
| 0x04 | 0x15A87C4 | EventFilter? | L | `r4 r1 r1` | 14 / 11 | chain 11, trigger 2, sub 1 | no | C13 U1 | C2 |
| 0x05 | 0x15A8B0C | AnyOf (OR) | H | `{r4}` | 823 / 484 | trigger 562, sub 216, cond 30 | yes |  |  |
| 0x06 | 0x15A8794 | Event | H | `r4` | 3615 / 854 | trigger 1998, sub 1563, cond 39 | yes |  |  |
| 0x07 | 0x15A8B68 | IfThenElse | H | `{r4} r4` | 2563 / 601 | chain 1289, sub 674, slot 600 | yes |  |  |
| 0x08 | 0x15A8820 | TimerExpired | H | `O` | 353 / 245 | trigger 217, sub 96, cond 31 | yes |  |  |
| 0x09 | 0x15A8ADC | AllOf (AND) | H | `{r4}` | 1110 / 462 | trigger 582, cond 458, sub 52 | yes |  |  |
| 0x0A | 0x15A890C | NodeCondition (Not?) | M | `r4` | 1024 / 421 | sub 660, trigger 204, cond 160 | yes |  |  |
| 0x0C | 0x15A8938 | DebugLog | H | `B {{r1 r4}}` | 9 / 2 | chain 7, slot 1, sub 1 | no | ST2 |  |
| 0x0D | 0x15A8B98 | WhileLoop | H | `{r4} r4` | 214 / 139 | chain 211, sub 3 | yes |  |  |
| 0x10 | 0x15A89F0 | IsTrue | H | `O` | 751 / 344 | cond 478, chain 131, sub 91 | yes |  |  |
| 0x11 | 0x15A8A50 | CopyVariable | H | `B O O` | 321 / 95 | sub 216, chain 79, slot 26 | yes |  |  |
| 0x12 | 0x15A88E0 | LoadConstant? | L | `B r4 O` | 7 / 6 | slot 3, chain 2, sub 2 | partial: evaluate() treats vt 0x15A88E0 with two values as `>=`; not as a node | C3 SP11 ST1 U1 | SP6 ST1 U1 |
| 0x14 | 0x15A8850 | HasEventParameter? | L | `O` | 7 / 5 | cond 7 | no | C5 ST9 U3 | ST4 |
| 0x15 | 0x15A8BC8 | Switch | M | `{r4} {r4} O` | 7 / 7 | chain 3, slot 3, sub 1 | no | C8 ST7 U2 | ST2 |
| 0x16 | 0x15A8A80 | SetBool | H | `B O r1` | 73 / 27 | chain 59, sub 9, slot 5 | no | C18 ST17 U14 | C1 ST1 |
| 0x17 | 0x15A8990 | ClearVariable | M | `B O` | 44 / 21 | chain 27, sub 15, slot 2 | no | C11 ST15 U9 | C1 |
| 0x18 | 0x15A8A20 | AreEqual | H | `O O` | 19 / 9 | sub 10, chain 5, trigger 2 | no | C6 ST2 U4 |  |
| 0x10000002 | 0x15FA3C8 | SkillComponentAction_0002 | ? | `` | 5 / 5 | slot 3, chain 1, sub 1 | no | C1 |  |
| 0x10000004 | 0x15FAEB4 | SetPerceptionRange | L | `B O O r1` | 6 / 6 | chain 6 | no | C1 SP5 ST3 U41 | ST1 |
| 0x10000005 | 0x15FD2A0 | SetSkillAttached | L | `B O r1` | 16 / 14 | chain 12, sub 4 | no | C11 I3 ST8 | C1 |
| 0x10000007 | 0x15FD600 | StartCooldown | H | `B O r4 O O` | 484 / 358 | chain 229, slot 137, sub 118 | yes |  |  |
| 0x10000008 | 0x15FE30C | AddAttributeModifier | H | `B O O {r4}` | 276 / 210 | chain 202, sub 42, slot 32 | no | C153 SP21 I11 ST180 U73 | C36 I3 ST108 U18 |
| 0x10000009 | 0x15FD240 | StopVitalOverTime | H | `B O O` | 78 / 60 | slot 50, chain 19, sub 9 | no | C40 I10 ST62 U35 | C2 ST2 |
| 0x1000000A | 0x15FA8D8 | EndSkill | M | `B r1` | 272 / 248 | slot 173, chain 97, sub 2 | stub (no-op) |  |  |
| 0x1000000B | 0x15FC8CC | SetSkillTarget | L | `B O O` | 16 / 14 | chain 8, slot 7, sub 1 | no | C11 I3 ST8 | C2 |
| 0x1000000D | 0x15FAEE4 | SetAITarget / Taunt | L | `B r4 O O` | 12 / 10 | sub 11, chain 1 | no | C13 SP6 ST3 U6 | C1 |
| 0x1000000E | 0x15FA6C8 | BeginSkill | M | `` | 255 / 248 | slot 218, chain 31, sub 6 | stub (no-op) |  |  |
| 0x10000010 | 0x15FB5A4 | DestroyEntity | X | `B O r4 r1` | 158 / 123 | chain 112, sub 23, slot 23 | yes |  |  |
| 0x10000011 | 0x15FB694 | GetPosition | H | `B O O` | 227 / 152 | chain 154, sub 40, slot 33 | yes |  |  |
| 0x10000012 | 0x15FBF6C | ClearProperty / StopEffect | L | `B r4 O` | 83 / 55 | chain 62, sub 12, slot 9 | no | C50 I1 ST19 U26 | C4 ST1 U1 |
| 0x10000014 | 0x15FBA24 | IsValidPosition | H | `O` | 51 / 37 | chain 20, cond 19, trigger 11 | yes |  |  |
| 0x10000015 | 0x15FA758 | IsServerControlled? | L | `` | 64 / 56 | cond 32, sub 26, trigger 4 | no | C47 SP24 ST5 U16 | C28 SP24 ST1 U9 |
| 0x10000016 | 0x15FC44C | SpawnGeneratorUnit | L | `B r4 r4 r4 r4 r4 r4 O O O O O O r1 r4` | 2 / 1 | slot 2 | no |  |  |
| 0x10000018 | 0x15FD668 | RemoveStatus | H | `B O O O r4 r4 r1 O` | 263 / 156 | chain 128, sub 80, slot 55 | no | C127 SP5 I7 ST111 U150 | C12 I2 ST18 U6 |
| 0x10000019 | 0x15FA248 | OnCastSignal | H | `{r4} r4` | 484 / 232 | trigger 437, sub 43, chain 3 | yes (trigger) |  | C13 |
| 0x1000001A | 0x15FCDCC | VitalThreshold | M | `r4 O O r1 r1 r4` | 57 / 32 | sub 25, chain 14, cond 11 | no | C25 I10 ST16 U23 | C8 ST3 U6 |
| 0x1000001B | 0x15FD1E4 | CancelMovement? | L | `B O` | 14 / 12 | chain 7, sub 4, slot 3 | no | C9 I3 ST8 | C1 |
| 0x1000001C | 0x15FCFD8 | IsTargetable | L | `O` | 29 / 15 | sub 23, trigger 2, cond 2 | no | C16 SP12 ST4 U5 | SP6 U1 |
| 0x1000001D | 0x15FC8FC | ApplyDamage | H | `B O O O r1 r1 r1 r1 r4 r4 O O O O O r1` | 363 / 269 | sub 173, chain 151, slot 39 | yes |  |  |
| 0x1000001E | 0x15FCEE8 | IsValid | H | `O` | 264 / 174 | sub 262, cond 2 | yes |  |  |
| 0x10000020 | 0x15FADC4 | CheckLineOfSight? | L | `B O O r4 r4 r4 r1 r1 r4 O` | 12 / 2 | sub 11, chain 1 | no | C6 ST1 U3 |  |
| 0x10000022 | 0x15FCAD0 | ShowMinimapTargetingRing | X | `B O r1` | 8 / 7 | sub 4, slot 4 | no | C2 |  |
| 0x10000024 | 0x15FCBEC | GetDetectedTarget | H | `B O O` | 127 / 115 | sub 124, chain 3 | yes |  |  |
| 0x10000025 | 0x15FBC94 | FindScatterPosition | M | `{B O O r1 r1 r1 r1 O r4 r4} O r1` | 31 / 25 | chain 17, sub 12, slot 2 | no | C20 SP5 I3 ST3 U6 |  |
| 0x10000026 | 0x15FB7E4 | Cast | H | `B O O r1 r1` | 267 / 261 | slot 135, chain 131, sub 1 | yes |  |  |
| 0x10000027 | 0x15FDFDC | ApplySkill (start status effect) | H | `{B r4 O O O O O O r1} O O O O r1 r1` | 501 / 351 | chain 275, sub 186, slot 40 | yes |  |  |
| 0x10000028 | 0x15FBA54 | CheckRelation | H | `r4 O O` | 272 / 197 | sub 241, cond 26, trigger 4 | yes |  |  |
| 0x10000029 | 0x15FB9F4 | IsKind | H | `r4 O` | 482 / 303 | sub 248, cond 150, chain 54 | yes |  |  |
| 0x1000002C | 0x15FAF44 | HasStealthFlags? | L | `{r4} r4 r4 O O O` | 6 / 3 | sub 6 | no | C3 SP5 ST1 U3 | SP5 ST1 |
| 0x1000002D | 0x15FC53C | DestroyHotspot | H | `B r4 O O O` | 37 / 27 | chain 20, slot 13, sub 4 | no | C22 SP5 I1 ST13 U8 | C3 |
| 0x1000002F | 0x15FD424 | SetGraphVariable | M | `B r4 O O r4` | 19 / 16 | chain 12, sub 6, slot 1 | no | C19 ST8 U9 | C3 ST3 U7 |
| 0x10000030 | 0x15FBD84 | StartScriptOn | L | `B r4 O O` | 2 / 2 | chain 2 | no | C2 |  |
| 0x10000031 | 0x15FDE60 | SpendCost | H | `B r4 O O r1 O` | 278 / 239 | chain 199, sub 45, slot 34 | yes |  |  |
| 0x10000033 | 0x15FBC64 | RemoveAttributeModifier | H | `B O O {r4}` | 217 / 180 | slot 104, chain 87, sub 26 | no | C147 SP15 I11 ST179 U69 | C16 ST7 |
| 0x10000034 | 0x15FE104 | RunScriptlet | H | `B r4 O O {r4} r1 r1` | 1403 / 450 | chain 695, sub 560, slot 148 | yes |  |  |
| 0x10000039 | 0x15FC6BC | SendMissionEvent | L | `B {r4} O` | 4 / 1 | slot 4 | no |  |  |
| 0x1000003A | 0x160A640 | UI_ShowMovie | M | `B r4` | 10 / 1 | slot 9, sub 1 | no |  |  |
| 0x1000003B | 0x160A5E0 | UI_OnEvent | M | `{r4} r4` | 59 / 1 | trigger 34, sub 25 | no |  |  |
| 0x1000003C | 0x15FAFA4 | IsSameEntity / IsOwner | L | `O O r1` | 51 / 11 | sub 42, cond 8, chain 1 | no | C16 ST4 U6 | ST2 |
| 0x1000003D | 0x15FB994 | Unk_003D(value)[flag] | ? | `O r1` | 4 / 1 | chain 4 | no | C3 U3 |  |
| 0x1000003E | 0x15FCEB8 | IsAlive | H | `O` | 741 / 340 | sub 406, chain 249, trigger 66 | yes |  |  |
| 0x1000003F | 0x15FD068 | FaceTarget | H | `B O O O r1 r1 r4` | 214 / 194 | chain 180, sub 28, slot 6 | yes |  |  |
| 0x10000040 | 0x15FDE90 | StartVitalOverTime | H | `{B r4 O O r1 O} O O r1 r1 r1 r4 O O` | 79 / 62 | chain 63, slot 9, sub 7 | no | C40 I10 ST64 U36 | C6 ST33 U6 |
| 0x10000042 | 0x15FCE88 | PickUpEntity? | L | `B O O` | 19 / 19 | chain 14, slot 4, sub 1 | no | C19 ST15 U8 | C1 ST9 |
| 0x10000043 | 0x160A670 | UI_Unk_0043[flag] | ? | `B r1` | 1 / 1 | chain 1 | no |  |  |
| 0x10000047 | 0x15FCA74 | FindTargets | H | `B r1 r4 O O O O r4 O r4 O O r4 r1 r1 r1` | 140 / 116 | chain 122, sub 11, slot 7 | yes |  |  |
| 0x10000048 | 0x15FA008 | UI_Condition_0048 | ? | `` | 2 / 2 | trigger 2 | no | C1 |  |
| 0x10000049 | 0x15FA4B8 | OnMissionEvent | L | `{r4} r4` | 4 / 1 | trigger 2, sub 2 | no |  |  |
| 0x1000004B | 0x15FB6C4 | GetLevel | H | `B O O` | 14 / 14 | slot 7, chain 7 | no | C10 SP11 ST6 U48 | C1 ST3 U3 |
| 0x1000004D | 0x15FA9C8 | UI_SendStateMachineEvent | X | `B r4` | 35 / 1 | slot 25, chain 9, sub 1 | no |  |  |
| 0x1000004E | 0x15FD128 | RaiseGraphEvent (BehaviorRaiseEventAction) | X | `B O r4` | 451 / 237 | chain 282, sub 115, slot 54 | yes |  |  |
| 0x1000004F | 0x15FB034 | AIMoveTo | M | `B O O O O r1 O` | 17 / 7 | sub 10, chain 7 | no | C12 ST4 U6 | ST1 |
| 0x10000050 | 0x15FCC4C | InitSkill | H | `B O O r4` | 144 / 137 | slot 114, chain 30 | yes |  |  |
| 0x10000052 | 0x15FD008 | IsInRangeAndAngle | H | `O O O O O r1 r1` | 211 / 132 | sub 132, chain 46, cond 25 | stub (always true) |  |  |
| 0x10000055 | 0x15FA7E8 | OnEntityEvent | L | `r4` | 77 / 73 | trigger 77 | yes (trigger) |  |  |
| 0x10000056 | 0x15FC984 | HideMinimapTargetingRing | X | `B O r1` | 8 / 7 | chain 8 | no | C2 |  |
| 0x10000057 | 0x15FD184 | ReleaseFacing | H | `B O` | 306 / 198 | sub 162, slot 91, chain 53 | stub (no-op) |  |  |
| 0x10000058 | 0x15FBEA8 | SetVariable / CopyEventParameter | H | `B O O` | 1026 / 508 | slot 663, chain 336, sub 27 | yes |  |  |
| 0x10000059 | 0x15FE1A8 | CreateHotspot | H | `{B O O r4 O r4 O O r4 O O r4 r4 r4 O O O O O r1 r1 r1 r1 r1}` | 15 / 13 | chain 15 | no | C16 U5 | C3 |
| 0x1000005A | 0x15FB544 | ComputeOffset | H | `B O O O r1` | 123 / 80 | chain 93, sub 23, slot 7 | yes |  |  |
| 0x1000005B | 0x15FB2D4 | DisableActions | M | `B r4 O r1 O r4` | 19 / 16 | chain 14, slot 3, sub 2 | no | C35 ST15 U7 | C3 ST5 |
| 0x1000005C | 0x15FC32C | Unk_005C(entity)[0] | ? | `B r4 O` | 2 / 2 | chain 2 | no | SP5 |  |
| 0x1000005E | 0x15FCBBC | LaunchMissile | H | `{B r4 O O O O O O r4 O O r1 r1 r4} r1 r1` | 77 / 59 | chain 42, sub 20, slot 15 | yes |  |  |
| 0x1000005F | 0x15FCB8C | LaunchTetheredMissile | M | `{B r4 O O O O O O r4 O O r1 r1 r4} O O r4 r1 r1` | 6 / 4 | chain 4, sub 2 | no | C4 | C4 |
| 0x10000060 | 0x15FC7DC | SetTutorialMarker? | L | `B r4 r4 {r1 r4 r4 {V V V V *loop} {r1}} r4 r4 r4 O O O O O O` | 12 / 5 | chain 10, slot 2 | no |  |  |
| 0x10000062 | 0x15FD7E8 | RedirectMissile | H | `B r1 O O` | 6 / 5 | slot 2, chain 2, sub 2 | yes |  |  |
| 0x10000063 | 0x15FC65C | Unk_0063(-)[0x1000018B] | ? | `B r4 O` | 4 / 3 | chain 3, slot 1 | no | ST1 |  |
| 0x10000065 | 0x15FC26C | GrantCurrency | M | `B O O r4 r4` | 4 / 4 | slot 3, sub 1 | no | ST1 |  |
| 0x1000006A | 0x15FB514 | HasFlagAttribute | M | `O r4` | 65 / 40 | chain 31, sub 22, cond 10 | yes |  |  |
| 0x1000006B | 0x15FBDB4 | RaiseEvent | H | `B r4 O r4 O O O r1 r1` | 302 / 183 | chain 169, sub 86, slot 47 | yes |  |  |
| 0x1000006F | 0x15FA788 | DisableCollision | M | `r4` | 109 / 82 | slot 63, chain 44, sub 2 | stub (no-op) |  |  |
| 0x10000070 | 0x15FA6F8 | EnableCollision | M | `r4` | 89 / 87 | slot 64, chain 24, sub 1 | stub (no-op) |  |  |
| 0x10000072 | 0x15FB9C4 | IsClass | M | `O r4` | 14 / 9 | sub 12, chain 2 | no | C9 ST1 U1 | C1 |
| 0x10000075 | 0x15FD2D0 | SetTargetingMode? | L | `B O r4` | 25 / 22 | chain 19, slot 3, sub 3 | no | C21 SP6 ST15 U44 | C10 ST13 |
| 0x10000078 | 0x15FBCC4 | SetGroundMarker? | L | `B r1 O` | 10 / 6 | slot 6, chain 4 | no | C1 SP5 U1 | C1 |
| 0x1000007A | 0x15FE210 | TargetHit (hit effect) | M | `{B r4 O O {r4} r1 r1} O O r1 r4 r4` | 462 / 311 | chain 277, sub 168, slot 17 | yes |  |  |
| 0x1000007B | 0x15FB8A4 | GetTeam | H | `B O O` | 74 / 72 | chain 46, slot 23, sub 5 | no | C42 SP17 I4 ST21 U22 | C19 I4 ST7 U4 |
| 0x1000007D | 0x15FDC6C | BeginTeleport? | L | `B O O` | 2 / 2 | chain 2 | no | SP5 |  |
| 0x1000007E | 0x15FBE78 | SetTeam | H | `B O O` | 4 / 3 | chain 2, sub 1, slot 1 | no |  |  |
| 0x1000007F | 0x15FDC9C | EndTeleport? | L | `B O O` | 2 / 2 | chain 2 | no | SP5 |  |
| 0x10000081 | 0x15FBD24 | StopAction | M | `B O O` | 116 / 85 | chain 60, sub 33, slot 23 | no | C81 ST35 U20 | C9 ST1 |
| 0x10000082 | 0x15FB844 | GetTeamMember | H | `B O O O r4` | 48 / 22 | chain 39, sub 9 | no | C7 I2 ST15 U16 | C2 I1 ST6 U7 |
| 0x10000083 | 0x15FBC30 | TrackTeamEvents | M | `B r1 O` | 30 / 15 | sub 30 | no | C2 ST13 U7 | C1 ST6 U3 |
| 0x10000085 | 0x15FCA44 | DestructionImpulse | H | `B r1 r4 r4 r4 O O O O O O O O O r4 r4 r1 r1 r1` | 193 / 154 | chain 75, sub 74, slot 44 | no | C143 SP5 I2 ST24 U21 | C19 ST2 U2 |
| 0x10000086 | 0x15FC5CC | Unk_0086 | ? | `B r4 O` | 1 / 1 | slot 1 | no |  |  |
| 0x10000087 | 0x15FC2FC | SetUsageObject | L | `B O O r1` | 2 / 1 | chain 1, slot 1 | no | ST1 | ST1 |
| 0x10000089 | 0x15FDB7C | ChangeSkill? | L | `B O r4 O r1 O` | 16 / 12 | chain 11, slot 4, sub 1 | no | C16 ST2 U6 | C2 ST2 |
| 0x1000008E | 0x15FDBAC | SetSkillState? | L | `B O r4` | 89 / 72 | chain 51, slot 32, sub 6 | no | C67 SP11 I1 ST14 U30 | C7 U3 |
| 0x1000008F | 0x15FB454 | AttachEntity | M | `B O O r4 O r4 r1 O r1 O O` | 27 / 20 | chain 12, sub 10, slot 5 | no | C12 I1 ST4 U12 | I1 U1 |
| 0x10000090 | 0x15FC05C | SetObjectState? | L | `B O r4 r1` | 11 / 10 | chain 10, slot 1 | no | SP11 I1 ST2 U3 | U1 |
| 0x10000092 | 0x15FDF7C | RemoveTempVital | H | `B O O` | 15 / 15 | slot 10, chain 3, sub 2 | no | C14 I1 ST25 U9 | C1 |
| 0x10000093 | 0x15FDE30 | AddTempVital (shield) | H | `{B r4 O O r1 O} O O r4` | 16 / 15 | chain 14, sub 2 | no | C16 I1 ST26 U9 | C2 ST10 |
| 0x10000097 | 0x15FD848 | SetSkillCooldownState? | L | `B r4 r1 r4 O` | 165 / 75 | chain 126, slot 31, sub 8 | stub (no-op) |  |  |
| 0x1000009C | 0x15FA5A8 | SetEnvironmentSetting? | L | `B r1 r4 r1 r4 r4 r4 r4` | 36 / 19 | slot 21, chain 13, sub 2 | stub (no-op) |  |  |
| 0x1000009E | 0x15FCB00 | Unk_009E | ? | `B O O r1` | 1 / 1 | chain 1 | no | C1 | C1 |
| 0x1000009F | 0x15FE43C | LoadSkillStats | H | `B O {r4} r4` | 743 / 662 | slot 410, chain 313, sub 20 | yes |  |  |
| 0x100000A0 | 0x15FE0A4 | SpawnEntity | H | `{B O O r1 r1 r1 r1 O r4 r4} r4 O O {r4}` | 94 / 73 | chain 79, sub 9, slot 6 | no | C53 SP17 I5 ST7 U23 | C24 I5 U2 |
| 0x100000A1 | 0x15FC02C | Unk_00A1(entity, entity) | ? | `B O O` | 2 / 1 | chain 1, sub 1 | no | C1 U3 |  |
| 0x100000A3 | 0x15FC9B4 | ReduceCooldown | M | `B O r4 O` | 31 / 20 | chain 17, slot 8, sub 6 | no | C22 ST4 U24 | C4 U5 |
| 0x100000A4 | 0x15FCF78 | HasStatus | H | `O O r4 O r4` | 224 / 132 | cond 117, chain 62, sub 42 | yes |  |  |
| 0x100000A5 | 0x15FB784 | SetOwner / SetCreator? | L | `B O` | 24 / 24 | slot 19, chain 5 | no | C21 ST8 U13 | C3 ST4 U1 |
| 0x100000A6 | 0x15FD698 | RemoveStatusIcon | H | `B O O r4 r1 r1` | 211 / 169 | chain 133, slot 58, sub 20 | no | C150 SP10 I9 ST147 U91 | C13 I2 ST14 U2 |
| 0x100000A7 | 0x15FD638 | AddStatusIcon | H | `B O O O r4 O O O O O r4 r1 O` | 198 / 168 | chain 154, sub 25, slot 19 | no | C147 SP16 I18 ST144 U92 | C32 I14 ST79 U20 |
| 0x100000A8 | 0x15FD878 | UpdateStatusIcon | H | `B O O O O r1 O r4 r4` | 91 / 53 | chain 63, sub 25, slot 3 | no | C55 SP11 I12 ST28 U46 | C1 ST1 U3 |
| 0x100000AD | 0x15FBFCC | SuppressInput? | L | `B O r1` | 26 / 10 | chain 15, slot 7, sub 4 | no | C5 SP6 ST2 U1 | C1 |
| 0x100000AE | 0x15FA368 | Unk_00AE predicate | ? | `` | 1 / 1 | sub 1 | no | C3 |  |
| 0x100000B0 | 0x15FBF08 | SnapToGround? | L | `B O r1 r1` | 18 / 18 | chain 14, slot 3, sub 1 | no | C14 ST2 U5 | C1 ST1 |
| 0x100000B1 | 0x15FA188 | OnAttributeChanged | M | `{r4} r4` | 82 / 60 | sub 74, trigger 8 | no | C8 SP65 I10 ST17 U104 | C4 SP65 ST9 U99 |
| 0x100000B2 | 0x15FC7AC | StopMissionEvent | L | `B O` | 1 / 1 | slot 1 | no |  |  |
| 0x100000B8 | 0x15FB4B4 | SetImpactState? | L | `B r4 O` | 6 / 3 | sub 3, chain 2, slot 1 | no |  |  |
| 0x100000BB | 0x15FBBD0 | PlaySound / PlayAudioEvent? | L | `B r4 O O O r4` | 21 / 11 | chain 14, slot 7 | no | C1 I9 ST2 U1 | ST2 |
| 0x100000BD | 0x15FB934 | Unk_00BD | ? | `B O r4` | 1 / 1 | chain 1 | no |  |  |
| 0x100000C1 | 0x15FA0C8 | ClearEntityList | H | `r4` | 49 / 47 | slot 23, chain 19, sub 7 | no | C29 ST23 U13 | C7 ST13 U3 |
| 0x100000C2 | 0x15FB394 | AddToEntityList | H | `B O` | 74 / 56 | sub 39, chain 34, slot 1 | no | C41 SP11 ST22 U17 | C2 |
| 0x100000C3 | 0x15FB364 | GetEntityListCount | H | `B O` | 64 / 31 | chain 56, sub 5, slot 3 | no | C20 SP5 ST19 U14 | C3 ST6 U3 |
| 0x100000C4 | 0x15FB304 | IsInEntityList | H | `O` | 44 / 41 | chain 25, cond 19 | no | C25 SP5 ST17 U10 | C1 |
| 0x100000C5 | 0x15FB334 | GetEntityListItem | H | `B O O` | 66 / 32 | sub 66 | no | C20 SP11 ST16 U11 |  |
| 0x100000C6 | 0x15FD038 | Knockback | H | `B O O O O O O` | 6 / 6 | sub 4, chain 2 | no | C8 ST6 | ST6 |
| 0x100000C7 | 0x15FC11C | Unk_00C7(entity, entity)[n, n, 2] | ? | `B O O r4 r4 r4` | 3 / 2 | chain 2, slot 1 | no | C1 ST1 U3 |  |
| 0x100000C8 | 0x15FBF9C | SetUntargetable? | L | `B O r1` | 17 / 9 | chain 7, sub 6, slot 4 | no | C4 SP5 ST1 U1 | ST1 |
| 0x100000CA | 0x15FD728 | SetStatusDuration | M | `B O O O r4 r4 O r1` | 57 / 39 | chain 29, sub 19, slot 9 | no | C37 I1 ST25 U25 | C1 ST1 U5 |
| 0x100000CB | 0x15FA398 | UI_ShowMovie2 | M | `B r4` | 1 / 1 | slot 1 | no |  |  |
| 0x100000CC | 0x15FA128 | UI_DestroyGameFront | X | `` | 10 / 1 | slot 10 | no |  |  |
| 0x100000CD | 0x15FB3C4 | RemoveFromEntityList | H | `B O r1` | 33 / 26 | sub 17, chain 16 | no | C14 SP11 ST18 U11 |  |
| 0x100000CE | 0x15FCD3C | GetVital | H | `B O O r4 r1 r1 O` | 58 / 44 | slot 23, chain 23, sub 12 | no | C36 I2 ST36 U25 | C9 ST12 U10 |
| 0x100000D1 | 0x15FE36C | StartConversation | H | `B O {r4} r4 r4 r1 r1 O r1 r4` | 126 / 21 | slot 111, chain 15 | yes |  |  |
| 0x100000D2 | 0x15FA848 | IsSkillActive? | L | `` | 64 / 64 | sub 64 | no | C55 ST1 U88 |  |
| 0x100000D8 | 0x15FD390 | ShowSkillError | X | `B O r4 r4` | 33 / 29 | sub 25, slot 8 | no | C21 I2 ST3 U1 | C2 I1 |
| 0x100000D9 | 0x15FDFAC | AddStacks | L | `{B r4 O O O O O O r1} O` | 5 / 4 | chain 3, sub 2 | no | C11 ST2 U8 |  |
| 0x100000DA | 0x15FD5A4 | Unk_00DA(SELF, SELF) | ? | `B O O` | 2 / 1 | slot 1, chain 1 | no | C2 |  |
| 0x100000DB | 0x15FBE48 | ResetBasicAttack? | L | `B O O r4 r4 r1 r1 r1` | 69 / 50 | chain 52, sub 11, slot 6 | no | C44 SP5 I3 ST4 U1 | C10 ST2 U1 |
| 0x100000DC | 0x15FB964 | HasState? | L | `O r4` | 5 / 4 | sub 2, chain 2, cond 1 | no | C6 ST2 U4 |  |
| 0x100000DD | 0x15FDF20 | DestructionRaycast | M | `{B O O O O r1 r4 O O O} r4 O r1 r4 r4` | 2 / 2 | sub 2 | no | C2 | C1 |
| 0x100000DF | 0x15FCD9C | IsSkillReady? | L | `r4 O` | 55 / 47 | sub 33, trigger 16, chain 5 | no | C36 SP37 I9 ST18 U105 | C4 SP13 I9 ST4 U13 |
| 0x100000E1 | 0x15FCFA8 | IsMoving? | L | `O r1` | 45 / 29 | chain 34, sub 6, trigger 4 | no | C44 SP5 I3 ST29 U5 | C6 ST16 U3 |
| 0x100000E2 | 0x15FD484 | SetCleanupFlag | M | `B O r1` | 653 / 311 | chain 527, slot 82, sub 44 | yes |  |  |
| 0x100000E4 | 0x15FC83C | SetPhysicsState? | L | `B r1 O` | 8 / 7 | chain 8 | no | SP11 I1 ST2 U1 |  |
| 0x100000E5 | 0x15FDA8C | Unk_00E5 | ? | `B O O r4 r1` | 2 / 2 | chain 2 | no | C1 ST4 |  |
| 0x100000E8 | 0x15FB5D4 | GetVehicleDriver? | L | `B O O` | 6 / 5 | slot 4, chain 2 | no | C3 I1 ST3 | I1 ST2 |
| 0x100000EA | 0x15FCA14 | DashToPosition | H | `B O O O O O O O r4 r1 O` | 36 / 35 | chain 31, sub 3, slot 2 | no | C33 ST7 U4 | C17 ST5 U1 |
| 0x100000EC | 0x15FB904 | SetCurrencyOption | L | `B O r4` | 1 / 1 | chain 1 | no | C1 U3 |  |
| 0x100000EF | 0x15FBAB4 | EntityExists | M | `O` | 113 / 61 | cond 46, sub 31, chain 30 | no | C44 SP6 I1 ST20 U24 | C14 SP6 ST6 U7 |
| 0x100000F1 | 0x15FB094 | SetMovementMode? | L | `B O r4 r4` | 14 / 7 | chain 8, slot 5, sub 1 | no | C6 ST2 | C1 |
| 0x100000F3 | 0x15FA458 | Unk_00F3 | ? | `` | 1 / 1 | cond 1 | no | C1 |  |
| 0x100000F5 | 0x15FCCAC | SwapSkillScript | L | `B O O r4` | 4 / 4 | slot 2, chain 2 | no | I2 U1 |  |
| 0x100000F9 | 0x15FB424 | FindInEntityList | H | `B O O` | 15 / 15 | chain 15 | no | C2 ST13 U7 |  |
| 0x100000FA | 0x15FD0F8 | ShowFloatingText? | L | `B O r4 {r1 r4 r4 {V V V V *loop} {r1}} r4 r4 r1 r4 r4 r4 r4 ` | 63 / 46 | chain 46, slot 12, sub 5 | no | C48 SP11 I1 ST9 U21 | C22 I1 ST2 |
| 0x100000FB | 0x15FD4B4 | SetSkillErrorState | M | `B r4 r4 O r1 O` | 85 / 35 | chain 32, sub 29, slot 24 | no | C43 SP11 I12 ST29 U6 | C2 I9 ST3 U4 |
| 0x100000FC | 0x15FD514 | SetSkillUsable? | L | `B O r4 r1 r1` | 70 / 34 | chain 57, slot 8, sub 5 | no | C33 SP5 I2 ST3 U3 | C17 I2 |
| 0x100000FE | 0x15FCC1C | GetStackCount | M | `B O O r4` | 14 / 8 | slot 7, chain 5, sub 2 | no | C18 ST4 U14 | C3 U9 |
| 0x10000102 | 0x15FBF38 | StopScriptlet | H | `B O O r4` | 362 / 231 | chain 255, slot 59, sub 48 | no | C178 SP5 I14 ST155 U104 | C23 I2 ST16 U4 |
| 0x10000103 | 0x15FE16C | StartScriptlet | H | `{B r4 O O {r4} r1 r1} O r4` | 366 / 231 | chain 274, sub 67, slot 25 | yes |  |  |
| 0x10000105 | 0x15FA908 | SetFlag_0105[0/1] | ? | `B r1` | 11 / 5 | chain 11 | no | C5 | C4 |
| 0x10000108 | 0x15FBAE4 | Unk_0108(SELF, -)[8/9] | ? | `B r4 O O` | 3 / 2 | chain 3 | no | SP5 |  |
| 0x10000109 | 0x15FDD70 | FindValidPosition | M | `{B O O r1 r1 r1 r1 O r4 r4} O` | 15 / 12 | chain 14, sub 1 | no | C14 ST2 U4 | ST1 |
| 0x1000010A | 0x15FC4DC | SetGeneratorEntry | L | `B r4 r4 O r1 O` | 1 / 1 | slot 1 | no |  |  |
| 0x1000010B | 0x15FBD54 | RollCritical | H | `B O O O` | 60 / 58 | chain 57, sub 3 | yes |  |  |
| 0x1000010D | 0x15FD6C8 | SpawnWorldState? | L | `B O r4 O` | 3 / 3 | chain 3 | no | C5 ST2 | ST1 |
| 0x1000010E | 0x15FD300 | Unk_010E(-) | ? | `B O` | 1 / 1 | chain 1 | no | C1 ST1 |  |
| 0x10000111 | 0x15FBED8 | ShowTutorialHint | X | `B r4 r4 O r1 r1` | 1 / 1 | chain 1 | no |  |  |
| 0x10000114 | 0x15FA878 | SetCollisionLayer | M | `r4` | 4 / 4 | chain 3, slot 1 | stub (no-op) |  |  |
| 0x10000115 | 0x15FA308 | UI_Condition_0115 | ? | `` | 2 / 1 | trigger 1, chain 1 | no |  |  |
| 0x10000116 | 0x15FD8A8 | SetStatusIconValue? | L | `B O O r4` | 30 / 23 | chain 30 | no | C18 I2 ST38 U17 | ST11 |
| 0x10000117 | 0x15FC14C | SetTracked | L | `B O r1 O` | 4 / 2 | sub 2, chain 2 | no |  |  |
| 0x10000118 | 0x15FD4E4 | ShowFloatingNumber? | L | `B O r1 r4 r4 r4` | 19 / 14 | chain 18, sub 1 | no | C13 ST4 U17 | C6 U8 |
| 0x10000119 | 0x15FC5FC | StopAnnouncement | M | `B O` | 5 / 1 | slot 4, chain 1 | no |  |  |
| 0x1000011A | 0x15FDDD0 | ShowAnnouncement | M | `B O O O r4 r4 r4 r1 {r4} {r4} r1` | 10 / 1 | sub 8, chain 1, slot 1 | no |  |  |
| 0x1000011E | 0x15FC1DC | Unk_011E(-, source)[0/1, n] | ? | `B O O r1 r4` | 5 / 2 | chain 2, sub 2, slot 1 | no | C1 ST2 | ST2 |
| 0x10000120 | 0x15FB6F4 | GetEntityRadius | M | `B O O` | 12 / 12 | chain 11, sub 1 | no | C8 ST5 | C2 ST3 |
| 0x10000121 | 0x15FC0BC | UpdateObjective / MissionText? | L | `B r4 r4 r4 r1 r4 r4 r4 r4 O O O O` | 12 / 6 | slot 9, sub 2, chain 1 | no |  |  |
| 0x10000122 | 0x15FDE00 | CreateAura (attached hotspot) | H | `{B O O r4 O r4 O O r4 O O r4 r4 r4 O O O O O r1 r1 r1 r1 r1}` | 37 / 28 | chain 26, sub 8, slot 3 | no | C23 SP5 I1 ST14 U8 | C11 ST2 U7 |
| 0x10000134 | 0x15FD818 | SetMissileVelocity | M | `B O O` | 20 / 18 | chain 12, slot 7, sub 1 | no | C15 ST3 U1 | C1 |
| 0x10000135 | 0x15FD330 | Unk_0135(-) | ? | `B O` | 2 / 2 | slot 2 | no | C2 |  |
| 0x10000136 | 0x15FD360 | TriggerSkillUsed? | L | `B r4 O O O` | 18 / 14 | chain 16, sub 2 | no | SP43 ST1 U5 | SP5 |
| 0x10000137 | 0x15FD788 | ResizeHotspot | M | `B O r4 O O O O O O` | 4 / 2 | chain 4 | no | C1 |  |
| 0x10000138 | 0x15FD99C | Unk_0138(user)[3] | ? | `B O r4` | 1 / 1 | slot 1 | no |  |  |
| 0x10000139 | 0x15FAD34 | SetAIEnabled | M | `B O O r1` | 30 / 15 | chain 25, sub 4, slot 1 | no | C34 SP5 ST16 U2 | C2 ST9 |
| 0x1000013A | 0x15FE404 | PlayHitScriptlet? | L | `{B r4 O O {r4} r1 r1} r4` | 59 / 42 | chain 47, sub 10, slot 2 | no | C38 SP11 I7 ST38 U8 | C2 I2 ST13 |
| 0x1000013B | 0x15FA818 | OnEvent (filtered) | H | `r4` | 365 / 327 | trigger 324, sub 40, chain 1 | yes (trigger) |  | C20 SP11 I12 U3 |
| 0x1000013C | 0x15FAF14 | Unk_013C(SELF) trigger | ? | `O` | 1 / 1 | chain 1 | no |  |  |
| 0x1000013E | 0x15FCDFC | DashToEntity | H | `B O O O O r4 r1 r4 r1 O` | 17 / 17 | chain 9, slot 5, sub 3 | no | C14 ST1 | C1 |
| 0x10000141 | 0x15FB604 | SetTeleportOffset? | L | `B O r1` | 1 / 1 | chain 1 | no | C1 |  |
| 0x10000143 | 0x15FDB1C | IsStealthed? | L | `O` | 2 / 1 | chain 1, sub 1 | no | SP5 |  |
| 0x10000144 | 0x15FDAEC | IsRevealed? | L | `O r1` | 2 / 1 | sub 1, chain 1 | no | SP5 |  |
| 0x10000146 | 0x15FDDA0 | FindValidPosition2 | L | `{B O O r1 r1 r1 r1 O r4 r4} O r1` | 1 / 1 | chain 1 | no | C1 | C1 |
| 0x10000147 | 0x15FAE84 | GetSourcePosition? | L | `B O O` | 1 / 1 | slot 1 | no | U40 |  |
| 0x10000148 | 0x15FCCDC | SetTargetingMode | M | `B O O r4 O` | 2 / 2 | chain 2 | no | SP6 I1 U1 |  |
| 0x10000149 | 0x15FDEC0 | AddDamageRedirect | M | `{B r4 O O r1 O} O O r4 O` | 2 / 2 | chain 2 | no | ST2 |  |
| 0x1000014A | 0x15FD270 | RemoveDamageRedirect | M | `B O O` | 2 / 2 | slot 1, chain 1 | no | ST2 |  |
| 0x1000014B | 0x15FB274 | SetCameraMode? | L | `B O r1 r4` | 18 / 9 | chain 18 | no | C9 ST6 U8 | C4 ST1 U1 |
| 0x1000014C | 0x15FD1B4 | StartAITask? | L | `B O O` | 7 / 3 | chain 7 | no | C3 |  |
| 0x1000014D | 0x15FC89C | StartAITask2? | L | `B O r4 O` | 3 / 3 | chain 3 | no | C3 | C1 |
| 0x10000150 | 0x15FD544 | ShowMinimapTargetingRing2 | X | `B r4 O O` | 7 / 3 | chain 7 | no | C5 U3 | C1 |
| 0x10000151 | 0x15FA7B8 | Unk_0151 (missile) | ? | `r4` | 8 / 8 | chain 6, sub 1, slot 1 | no | C10 ST1 U5 | C1 |
| 0x10000152 | 0x15FC47C | GetMatchTime | M | `B O` | 1 / 1 | slot 1 | no | ST1 | ST1 |
| 0x10000153 | 0x15FD454 | SetSkillStatOverride | L | `B O r4 r4` | 19 / 15 | chain 15, sub 2, slot 2 | no | C16 SP6 ST6 U9 | C3 ST1 |
| 0x10000154 | 0x15FCB5C | LaunchLobbedMissile | M | `{B r4 O O O O O O r4 O O r1 r1 r4} r4 r4 r1` | 17 / 14 | chain 12, slot 3, sub 2 | no | C12 ST2 U9 | C7 U2 |
| 0x10000155 | 0x15FE0D4 | SetEntityProperty | M | `B O {r4}` | 27 / 24 | slot 13, chain 11, sub 3 | no | C47 I3 ST12 U93 | C1 ST4 U46 |
| 0x1000015D | 0x15FBB74 | Unk_015D | ? | `B O O` | 1 / 1 | chain 1 | no |  |  |
| 0x1000015E | 0x15FA2D8 | UI_Condition_015E | ? | `` | 2 / 1 | chain 1, trigger 1 | no |  |  |
| 0x10000162 | 0x15FD7B8 | SetDefeatType / Invincible | L | `B O O r1 r4` | 13 / 6 | sub 6, slot 5, chain 2 | no | C4 ST5 U8 | C2 ST1 U5 |
| 0x10000167 | 0x15FD93C | NotifyHUDElement | X | `B O r4 r4 r4 r4 r1` | 63 / 7 | chain 47, slot 16 | no |  |  |
| 0x10000168 | 0x15FE33C | StartAITask3? | L | `B r1 r4 O r4 {r4}` | 2 / 1 | chain 1, slot 1 | no | C1 ST1 | ST1 |
| 0x10000169 | 0x15FB214 | SetCharges | L | `B O r4` | 3 / 3 | slot 3 | no | I9 U1 |  |
| 0x1000016A | 0x15FE27C | UpdateStatusIconStats | L | `B O O O r4 {r4}` | 41 / 32 | chain 36, sub 5 | no | C18 I2 ST56 U17 | C1 ST29 |
| 0x1000016B | 0x15FB1E4 | GetCharges | L | `B O r4` | 3 / 3 | slot 3 | no | I9 U1 |  |
| 0x1000016E | 0x15FD0C8 | GetCurrentRange? | L | `B O` | 3 / 2 | sub 3 | no | C1 |  |
| 0x1000016F | 0x15FCF48 | IsInFront? | L | `O O O` | 6 / 5 | chain 4, cond 1, sub 1 | no | C4 ST1 U4 | C1 |
| 0x10000172 | 0x15FBE18 | Unk_0172 | ? | `B O O` | 1 / 1 | chain 1 | no | C3 ST1 |  |
| 0x10000173 | 0x15FB244 | RandomChance | M | `r4 O` | 4 / 2 | chain 2, trigger 1, sub 1 | no |  |  |
| 0x10000174 | 0x15FC9E4 | Unk_0174 | ? | `B O O {r4}` | 1 / 1 | chain 1 | no | C3 ST1 |  |
| 0x10000177 | 0x15FE248 | LoadStatusStats | M | `B O {r4} O r4 r4` | 28 / 26 | chain 20, slot 8 | no | ST52 | ST51 |
| 0x10000179 | 0x15FA0F8 | UI_SetHUDVisibility | X | `` | 1 / 1 | slot 1 | no |  |  |
| 0x1000017B | 0x15FC0EC | TutorialStep? | L | `B {r4} r1 r1 r1` | 29 / 21 | slot 29 | stub (no-op) |  |  |
| 0x1000017D | 0x15FA1E8 | OnTutorialEvent | L | `{r4} r4` | 9 / 3 | trigger 7, sub 2 | no |  |  |
| 0x1000017E | 0x15FDC3C | SetDestructibleState? | L | `B O {r4}` | 2 / 1 | chain 2 | no | C1 | C1 |
| 0x1000017F | 0x15FD574 | SetSkillComboState? | L | `B r4 O O` | 19 / 5 | slot 10, chain 8, sub 1 | no | C10 U7 | C2 U4 |
| 0x10000181 | 0x15FC38C | TutorialSetup_0181 | L | `B {r4}` | 7 / 4 | chain 7 | no |  |  |
| 0x10000182 | 0x15FA428 | TutorialSetup_0182 | L | `B r1 r1` | 5 / 4 | chain 3, slot 2 | no |  |  |
| 0x10000183 | 0x15FC41C | ActivateArtifacts? | X | `B {r4} r1` | 4 / 3 | chain 4 | no |  |  |
| 0x10000186 | 0x15FA098 | Unk_0186 | ? | `` | 1 / 1 | slot 1 | no |  |  |
| 0x10000187 | 0x15FB8D4 | GetPlayer | M | `B O` | 9 / 9 | chain 6, slot 3 | yes |  |  |
| 0x10000188 | 0x15FB724 | GetAgent | M | `B O O` | 8 / 8 | chain 7, sub 1 | yes |  |  |
| 0x10000189 | 0x15FA968 | Unk_0189 | ? | `` | 1 / 1 | chain 1 | no |  |  |
| 0x1000018A | 0x15FA3F8 | IsChampion(class) trigger | L | `r4` | 1 / 1 | trigger 1 | no |  |  |
| 0x1000018F | 0x15FA158 | UI_ExitWorldLoadWrapper | X | `` | 2 / 1 | chain 2 | no |  |  |
| 0x10000191 | 0x15FC86C | Unk_0191(-, pos, pos) | ? | `B O O O` | 2 / 2 | chain 2 | no | C2 ST1 U3 |  |
| 0x10000195 | 0x15FD3F0 | SkillEcho? | L | `B O` | 226 / 221 | chain 207, sub 11, slot 8 | stub (no-op) |  |  |
| 0x1000019B | 0x15FC2CC | BreakDestructible? | L | `B O r1` | 1 / 1 | sub 1 | no |  |  |
| 0x1000019D | 0x15FD90C | Unk_019D | ? | `B O O O r4` | 4 / 2 | slot 2, sub 1, chain 1 | no |  |  |
| 0x100001A2 | 0x15FA4E8 | Unk_01A2[r4] | ? | `r4` | 1 / 1 | sub 1 | no |  |  |
| 0x100001A3 | 0x15FD96C | ShowTrainingFloatyText | X | `B O r4 r4 r4 {r1 r4 r4 {V V V V *loop} {r1}} r1` | 2 / 1 | slot 2 | no |  |  |
| 0x100001A4 | 0x15FA518 | Unk_01A4[r4] | ? | `r4` | 2 / 1 | sub 2 | no |  |  |
| 0x100001A5 | 0x15FB7B4 | SetLatencyWindow? | L | `B O O` | 1 / 1 | chain 1 | no | C1 |  |
| 0x100001A7 | 0x15FA8A8 | Unk_01A7[0/1] | ? | `B r1` | 2 / 1 | slot 2 | no | C2 ST2 U2 |  |
| 0x100001A9 | 0x15FC08C | SetHidden? | L | `B O r1` | 10 / 3 | chain 10 | no | C1 SP5 |  |
| 0x100001AD | 0x15FD3C0 | Unk_01AD(target, -)[14] | ? | `B O O r4` | 2 / 2 | sub 1, slot 1 | no | C2 |  |
| 0x100001AF | 0x15FCE58 | Unk_01AF(entity, -)[0] | ? | `B O O r4` | 14 / 13 | chain 11, slot 2, sub 1 | no | C15 U3 | C7 |
| 0x100001B0 | 0x15FACD4 | SpawnFromShooter? | L | `B r4 r4 r4 O` | 1 / 1 | sub 1 | no |  |  |
| 0x100001B1 | 0x15FA218 | Unk_01B1[2] predicate | ? | `r4` | 1 / 1 | sub 1 | no |  |  |
| 0x100001B3 | 0x15FAFD4 | SetLane | L | `B O O r1 r4` | 2 / 1 | chain 1, slot 1 | no | ST3 |  |
| 0x100001B6 | 0x15FAD64 | GetLane | L | `B O O` | 2 / 1 | sub 2 | no | ST3 | ST3 |
| 0x100001B7 | 0x15FA998 | UI_Condition_01B7 | ? | `` | 1 / 1 | trigger 1 | no |  |  |
| 0x100001B8 | 0x15FBFFC | Unk_01B8(-)[0/1] | ? | `B O r1` | 2 / 1 | chain 2 | no | SP5 |  |
| 0x100001B9 | 0x15FD6F8 | Unk_01B9(-) | ? | `B O` | 1 / 1 | chain 1 | no | C1 U2 |  |

### Expression registry 0x45FB30 (evaluate = vtable slot 10)

| id | vt | name | conf | sig | nodes / scripts | used as | runtime | roots blocked (static) | roots hit (sim) |
|---|---|---|---|---|---|---|---|---|---|
| 0x1 | 0x15A9558 | abs | X | `` | 12 / 12 | assign 6, lhs 6 | no | C11 I4 ST13 U3 | I2 ST7 |
| 0x2 | 0x15A8F18 | Constant | X | `` | 3219 / 551 | assign 1580, rhs 1221, lhs 176 | yes |  |  |
| 0x3 | 0x15A9D38 | Variable | X | `` | 5036 / 612 | lhs 2248, rhs 1331, arg 1025 | yes |  |  |
| 0x4 | 0x15A90C0 | min | X | `` | 29 / 28 | assign 24, lhs 2, rhs 2 | no | C15 ST35 U64 | ST3 |
| 0x5 | 0x15A97F8 | cross | X | `` | 1 / 1 | arg 1 | no (op cross not evaluated) | ST1 | ST1 |
| 0x6 | 0x15A94E8 | divide (/) | X | `` | 205 / 164 | assign 138, lhs 27, rhs 17 | yes |  |  |
| 0x7 | 0x15A95C8 | sqrt | X | `` | 2 / 2 | lhs 2 | no | C2 ST1 | C1 ST1 |
| 0x8 | 0x15A98A0 | length | X | `` | 38 / 34 | lhs 20, assign 16, rhs 2 | yes |  |  |
| 0xA | 0x15A9168 | bitwise and (&) | X | `` | 9 / 5 | lhs 9 | no | C4 ST3 U7 | C1 ST1 U3 |
| 0xB | 0x15A96A8 | cos | X | `` | 2 / 2 | lhs 1, rhs 1 | no | C2 U3 |  |
| 0xC | 0x15A9408 | decrement (x - 1) | X | `` | 36 / 27 | assign 34, rhs 2 | WRONG: label `server-expr:0xc` is evaluated as `/`; must be x - 1 (vt 0x15A9408) | C34 SP11 I1 ST10 U13 |  |
| 0xD | 0x15A9868 | normalize | X | `` | 9 / 8 | lhs 5, assign 4 | no (op normalize not evaluated) | C6 ST3 U3 | C2 ST2 |
| 0xE | 0x15A99F0 | ToFloat | X | `` | 81 / 53 | lhs 56, rhs 17, assign 7 | yes |  |  |
| 0x10 | 0x15A92B8 | logical or (\|\|) | X | `` | 22 / 12 | arg 12, lhs 5, rhs 5 | yes only as label `server-expr:0x10` (the decoder fix renames it: map vt 0x15A92B8) | C12 I1 ST5 U11 |  |
| 0x11 | 0x15A9360 | pow | X | `` | 2 / 1 | lhs 1, assign 1 | no | C1 | C1 |
| 0x12 | 0x15A9050 | >= | X | `` | 76 / 50 | arg 42, lhs 30, x 4 | yes |  |  |
| 0x13 | 0x15A92F0 | logical and (&&) | M | `` | 59 / 26 | arg 43, rhs 15, lhs 1 | no | C10 ST17 U17 | C1 U3 |
| 0x14 | 0x15A9B78 | RandomRange | X | `` | 16 / 8 | assign 8, rhs 4, lhs 2 | no | C10 ST4 U9 | ST2 |
| 0x17 | 0x15A93D0 | increment (++) | X | `` | 291 / 173 | assign 288, lhs 2, rhs 1 | yes |  |  |
| 0x19 | 0x15A9B40 | round (floor(x + 1/2))? | L | `` | 8 / 3 | arg 7, assign 1 | no | C2 ST1 U5 | ST1 |
| 0x1A | 0x15A99B8 | ToInt32 (truncate) | X | `` | 6 / 5 | assign 6 | no | C6 I4 ST11 U1 |  |
| 0x1B | 0x15A8FA8 | != | X | `` | 271 / 159 | arg 259, lhs 6, rhs 5 | yes |  |  |
| 0x1C | 0x15A9478 | subtract (-) | X | `` | 202 / 129 | lhs 65, arg 51, assign 46 | yes |  |  |
| 0x1D | 0x15A9280 | bitwise not (~) | X | `` | 2 / 2 | assign 2 | yes |  |  |
| 0x1E | 0x15A9130 | clamp(x, lo, hi) | X | `` | 27 / 24 | assign 22, z 2, rhs 1 | no | C11 I1 ST20 | C2 ST2 |
| 0x21 | 0x15A9638 | ceil | X | `` | 3 / 3 | arg 2, x 1 | no | C3 |  |
| 0x22 | 0x15A8F70 | == | X | `` | 770 / 186 | arg 493, x 245, lhs 17 | yes |  |  |
| 0x23 | 0x15A9440 | add (+) | X | `` | 221 / 151 | assign 161, lhs 28, rhs 22 | yes |  |  |
| 0x24 | 0x15A9328 | logical not (!) | M | `` | 49 / 38 | arg 26, assign 20, rhs 2 | yes |  |  |
| 0x26 | 0x15A9A28 | ToUInt32 | X | `` | 120 / 42 | rhs 53, assign 33, lhs 24 | yes |  |  |
| 0x27 | 0x15A9BB0 | Select (cond ? a : b) | H | `` | 264 / 35 | z 190, assign 62, rhs 5 | no | C21 I4 ST28 U59 | C3 I2 ST7 U3 |
| 0x28 | 0x15A9830 | MakeVector(x, y, z) | X | `` | 85 / 62 | rhs 50, arg 32, assign 2 | yes |  |  |
| 0x29 | 0x15A94B0 | multiply (*) | X | `` | 396 / 209 | assign 256, rhs 56, lhs 55 | yes |  |  |
| 0x2A | 0x15A9018 | < | X | `` | 302 / 176 | arg 244, rhs 33, lhs 18 | yes |  |  |
| 0x2E | 0x15A9670 | sin | X | `` | 5 / 5 | rhs 3, lhs 2 | no | C4 U3 | C2 |
| 0x30 | 0x15A9088 | <= | X | `` | 65 / 28 | arg 59, x 4, lhs 1 | yes |  |  |
| 0x31 | 0x15A90F8 | max | X | `` | 91 / 86 | rhs 74, assign 14, lhs 3 | yes |  |  |
| 0x33 | 0x15A9398 | negate | M | `` | 23 / 22 | assign 14, lhs 5, y 2 | yes |  |  |
| 0x34 | 0x15A8FE0 | > | X | `` | 148 / 95 | arg 141, x 4, rhs 2 | yes |  |  |
| 0x35 | 0x15A9600 | floor/round | M | `` | 6 / 6 | arg 4, lhs 2 | no | C8 I4 ST13 U3 | C1 U2 |
| 0x36 | 0x15A8F44 | GameTime | X | `` | 117 / 64 | lhs 58, rhs 38, assign 20 | yes |  |  |
| 0x37 | 0x15A9C58 | vector add | X | `` | 32 / 25 | assign 30, lhs 2 | no (op vadd not evaluated) | C18 SP5 ST8 U7 | C5 ST4 |
| 0x38 | 0x15A9C20 | TransformPoint(frame, localOffset) | M | `` | 76 / 59 | assign 64, lhs 12 | yes |  |  |
| 0x3C | 0x15A9980 | vector.z | M | `` | 10 / 4 | z 3, lhs 2, rhs 2 | no | C2 U1 | C1 |
| 0x3D | 0x15A9948 | vector.y | H | `` | 42 / 29 | y 36, assign 4, lhs 2 | yes |  |  |
| 0x3E | 0x15A9910 | vector.x | H | `` | 38 / 28 | x 35, lhs 2, arg 1 | yes |  |  |
| 0x40 | 0x15A9C90 | Heading(vector)[degrees flag] | X | `` | 21 / 18 | rhs 9, assign 7, lhs 5 | no | C12 ST7 U3 | C6 ST3 |
| 0x41 | 0x15A9BE8 | RotateByHeading(vector, angle)[degrees flag] | M | `` | 46 / 32 | assign 28, lhs 17, arg 1 | yes |  |  |
| 0x42 | 0x15A98D8 | lengthSquared | X | `` | 9 / 8 | assign 5, lhs 4 | yes |  |  |
| 0x44 | 0x15A9750 | DegToRad | M | `` | 7 / 6 | arg 5, assign 2 | no | C5 ST1 U6 | C2 |
| 0x45 | 0x15A9D00 | ForwardVector(frame) | L | `` | 1 / 1 | lhs 1 | no | C1 ST1 U3 |  |
| 0x46 | 0x15A9CC8 | PositionOf(frame) | L | `` | 14 / 13 | assign 14 | no | C11 ST1 U3 | C5 |
| 0x47 | 0x15FABA4 | Unk_47(a, b, c) (lerp?) | ? | `` | 1 / 1 | assign 1 | no | C1 ST1 |  |
| 0x10000002 | 0x15FDD28 | GetAttribute(entity)[attribute] | H | `` | 324 / 152 | arg 173, lhs 108, assign 25 | yes |  |  |
| 0x10000003 | 0x15FABDC | ScaleByLevel(level, base, delta) | X | `` | 6 / 4 | assign 6 | no | ST9 | ST3 |



## 5. Unimplemented classes, by how many roots they stop

Ordered by roots hit in simulation, then by static presence. Includes the classes the runtime only stubs
(no-op / always true) and the triggers that fail inside lists. A root usually needs several of them: fixing the
first ten rows (0x100000B1, 0x10000008, 0x100000A7, 0x10000015, 0x10000155, 0x10000177, 0x1000013B-in-lists,
0x10000102, 0x10000040, 0x100000DF) covers most of the hits. Many top rows are bookkeeping the client only needs
as messages (status icons 0x100000A7 / 0x100000A6 / 0x1000016A / 0x100000A8, scriptlet stop 0x10000102) and can
be implemented as sends or no-ops; the gameplay ones are the attribute modifiers (0x10000008 / 0x10000033),
damage over time (0x10000040 / 0x10000009), statuses (0x10000177 / 0x10000018), vitals (0x100000CE, 0x1000001A,
0x10000093), spawns (0x100000A0, 0x10000155) and movement (0x100000EA, 0x10000154, 0x100000C6).



| # | id | name | runtime | roots hit in simulation  | roots containing it (static) | sole blocker (static) | nodes / scripts |
|---|---|---|---|---|---|---|---|
| 1 | 0x100000B1 (node) | OnAttributeChanged | no | 177 (C4 SP65 ST9 U99) | 204 (C8 SP65 I10 ST17 U104) |  | 82 / 60 |
| 2 | 0x10000008 (node) | AddAttributeModifier | no | 165 (C36 I3 ST108 U18) | 438 (C153 SP21 I11 ST180 U73) |  | 276 / 210 |
| 3 | 0x100000A7 (node) | AddStatusIcon | no | 145 (C32 I14 ST79 U20) | 417 (C147 SP16 I18 ST144 U92) |  | 198 / 168 |
| 4 | 0x10000015 (node) | IsServerControlled? | no | 62 (C28 SP24 ST1 U9) | 92 (C47 SP24 ST5 U16) |  | 64 / 56 |
| 5 | 0x10000155 (node) | SetEntityProperty | no | 51 (C1 ST4 U46) | 155 (C47 I3 ST12 U93) |  | 27 / 24 |
| 6 | 0x10000177 (node) | LoadStatusStats | no | 51 (ST51) | 52 (ST52) | ST2 | 28 / 26 |
| 7 | 0x1000013B (node) | OnEvent (filtered) | yes (trigger) | 46 (C20 SP11 I12 U3) | 0 () |  | 365 / 327 |
| 8 | 0x10000102 (node) | StopScriptlet | no | 45 (C23 I2 ST16 U4) | 456 (C178 SP5 I14 ST155 U104) | ST2 | 362 / 231 |
| 9 | 0x10000040 (node) | StartVitalOverTime | no | 45 (C6 ST33 U6) | 150 (C40 I10 ST64 U36) |  | 79 / 62 |
| 10 | 0x100000DF (node) | IsSkillReady? | no | 43 (C4 SP13 I9 ST4 U13) | 205 (C36 SP37 I9 ST18 U105) |  | 55 / 47 |
| 11 | 0x10000018 (node) | RemoveStatus | no | 38 (C12 I2 ST18 U6) | 400 (C127 SP5 I7 ST111 U150) | C1 I1 ST7 | 263 / 156 |
| 12 | 0x1000007B (node) | GetTeam | no | 34 (C19 I4 ST7 U4) | 106 (C42 SP17 I4 ST21 U22) |  | 74 / 72 |
| 13 | 0x100000EF (node) | EntityExists | no | 33 (C14 SP6 ST6 U7) | 95 (C44 SP6 I1 ST20 U24) | C1 | 113 / 61 |
| 14 | 0x100000A6 (node) | RemoveStatusIcon | no | 31 (C13 I2 ST14 U2) | 407 (C150 SP10 I9 ST147 U91) |  | 211 / 169 |
| 15 | 0x100000A0 (node) | SpawnEntity | no | 31 (C24 I5 U2) | 105 (C53 SP17 I5 ST7 U23) | I1 | 94 / 73 |
| 16 | 0x100000CE (node) | GetVital | no | 31 (C9 ST12 U10) | 99 (C36 I2 ST36 U25) | ST1 | 58 / 44 |
| 17 | 0x1000016A (node) | UpdateStatusIconStats | no | 30 (C1 ST29) | 93 (C18 I2 ST56 U17) |  | 41 / 32 |
| 18 | 0x100000FA (node) | ShowFloatingText? | no | 25 (C22 I1 ST2) | 90 (C48 SP11 I1 ST9 U21) |  | 63 / 46 |
| 19 | 0x100000E1 (node) | IsMoving? | no | 25 (C6 ST16 U3) | 86 (C44 SP5 I3 ST29 U5) |  | 45 / 29 |
| 20 | 0x10000033 (node) | RemoveAttributeModifier | no | 23 (C16 ST7) | 421 (C147 SP15 I11 ST179 U69) |  | 217 / 180 |
| 21 | 0x10000085 (node) | DestructionImpulse | no | 23 (C19 ST2 U2) | 195 (C143 SP5 I2 ST24 U21) | C1 | 193 / 154 |
| 22 | 0x10000075 (node) | SetTargetingMode? | no | 23 (C10 ST13) | 86 (C21 SP6 ST15 U44) |  | 25 / 22 |
| 23 | 0x100000C1 (node) | ClearEntityList | no | 23 (C7 ST13 U3) | 65 (C29 ST23 U13) |  | 49 / 47 |
| 24 | 0x100000EA (node) | DashToPosition | no | 23 (C17 ST5 U1) | 44 (C33 ST7 U4) |  | 36 / 35 |
| 25 | 0x10000122 (node) | CreateAura (attached hotspot) | no | 20 (C11 ST2 U7) | 51 (C23 SP5 I1 ST14 U8) |  | 37 / 28 |
| 26 | 0x100000FC (node) | SetSkillUsable? | no | 19 (C17 I2) | 46 (C33 SP5 I2 ST3 U3) |  | 70 / 34 |
| 27 | 0x100000FB (node) | SetSkillErrorState | no | 18 (C2 I9 ST3 U4) | 101 (C43 SP11 I12 ST29 U6) | C1 ST1 | 85 / 35 |
| 28 | 0x1000013A (node) | PlayHitScriptlet? | no | 17 (C2 I2 ST13) | 102 (C38 SP11 I7 ST38 U8) |  | 59 / 42 |
| 29 | 0x1000001A (node) | VitalThreshold | no | 17 (C8 ST3 U6) | 74 (C25 I10 ST16 U23) |  | 57 / 32 |
| 30 | 0x10000082 (node) | GetTeamMember | no | 16 (C2 I1 ST6 U7) | 40 (C7 I2 ST15 U16) | I1 | 48 / 22 |
| 31 | 0x27 (expr) | Select (cond ? a : b) | no | 15 (C3 I2 ST7 U3) | 112 (C21 I4 ST28 U59) |  | 264 / 35 |
| 32 | 0x10000118 (node) | ShowFloatingNumber? | no | 14 (C6 U8) | 34 (C13 ST4 U17) |  | 19 / 14 |
| 33 | 0x100000DB (node) | ResetBasicAttack? | no | 13 (C10 ST2 U1) | 57 (C44 SP5 I3 ST4 U1) |  | 69 / 50 |
| 34 | 0x1000002F (node) | SetGraphVariable | no | 13 (C3 ST3 U7) | 36 (C19 ST8 U9) |  | 19 / 16 |
| 35 | 0x10000019 (node) | OnCastSignal | yes (trigger) | 13 (C13) | 0 () |  | 484 / 232 |
| 36 | 0x100000C3 (node) | GetEntityListCount | no | 12 (C3 ST6 U3) | 58 (C20 SP5 ST19 U14) |  | 64 / 31 |
| 37 | 0x10000093 (node) | AddTempVital (shield) | no | 12 (C2 ST10) | 52 (C16 I1 ST26 U9) |  | 16 / 15 |
| 38 | 0x100000FE (node) | GetStackCount | no | 12 (C3 U9) | 36 (C18 ST4 U14) |  | 14 / 8 |
| 39 | 0x10000116 (node) | SetStatusIconValue? | no | 11 (ST11) | 75 (C18 I2 ST38 U17) |  | 30 / 23 |
| 40 | 0x10000139 (node) | SetAIEnabled | no | 11 (C2 ST9) | 57 (C34 SP5 ST16 U2) |  | 30 / 15 |
| 41 | 0x10000081 (node) | StopAction | no | 10 (C9 ST1) | 136 (C81 ST35 U20) |  | 116 / 85 |
| 42 | 0x1000008E (node) | SetSkillState? | no | 10 (C7 U3) | 123 (C67 SP11 I1 ST14 U30) |  | 89 / 72 |
| 43 | 0x10000042 (node) | PickUpEntity? | no | 10 (C1 ST9) | 42 (C19 ST15 U8) |  | 19 / 19 |
| 44 | 0x10000083 (node) | TrackTeamEvents | no | 10 (C1 ST6 U3) | 22 (C2 ST13 U7) |  | 30 / 15 |
| 45 | 0x100000A3 (node) | ReduceCooldown | no | 9 (C4 U5) | 50 (C22 ST4 U24) | ST1 | 31 / 20 |
| 46 | 0x37 (expr) | vector add | no (op vadd not evaluated) | 9 (C5 ST4) | 38 (C18 SP5 ST8 U7) |  | 32 / 25 |
| 47 | 0x1 (expr) | abs | no | 9 (I2 ST7) | 31 (C11 I4 ST13 U3) |  | 12 / 12 |
| 48 | 0x10000154 (node) | LaunchLobbedMissile | no | 9 (C7 U2) | 23 (C12 ST2 U9) |  | 17 / 14 |
| 49 | 0x40 (expr) | Heading(vector)[degrees flag] | no | 9 (C6 ST3) | 22 (C12 ST7 U3) |  | 21 / 18 |
| 50 | 0x1000005B (node) | DisableActions | no | 8 (C3 ST5) | 57 (C35 ST15 U7) |  | 19 / 16 |
| 51 | 0x100000A5 (node) | SetOwner / SetCreator? | no | 8 (C3 ST4 U1) | 42 (C21 ST8 U13) |  | 24 / 24 |
| 52 | 0x10000162 (node) | SetDefeatType / Invincible | no | 8 (C2 ST1 U5) | 17 (C4 ST5 U8) |  | 13 / 6 |
| 53 | 0x12 (node) | LoadConstant? | no | 8 (SP6 ST1 U1) | 16 (C3 SP11 ST1 U1) |  | 7 / 6 |
| 54 | 0x100000CA (node) | SetStatusDuration | no | 7 (C1 ST1 U5) | 88 (C37 I1 ST25 U25) | ST1 | 57 / 39 |
| 55 | 0x1000004B (node) | GetLevel | no | 7 (C1 ST3 U3) | 75 (C10 SP11 ST6 U48) |  | 14 / 14 |
| 56 | 0x1000001C (node) | IsTargetable | no | 7 (SP6 U1) | 37 (C16 SP12 ST4 U5) |  | 29 / 15 |
| 57 | 0x100001AF (node) | Unk_01AF(entity, -)[0] | no | 7 (C7) | 18 (C15 U3) |  | 14 / 13 |
| 58 | 0x10000012 (node) | ClearProperty / StopEffect | no | 6 (C4 ST1 U1) | 96 (C50 I1 ST19 U26) | ST1 | 83 / 55 |
| 59 | 0x1000014B (node) | SetCameraMode? | no | 6 (C4 ST1 U1) | 23 (C9 ST6 U8) |  | 18 / 9 |
| 60 | 0x1000017F (node) | SetSkillComboState? | no | 6 (C2 U4) | 17 (C10 U7) |  | 19 / 5 |
| 61 | 0x100000C6 (node) | Knockback | no | 6 (ST6) | 14 (C8 ST6) |  | 6 / 6 |
| 62 | 0x1000002C (node) | HasStealthFlags? | no | 6 (SP5 ST1) | 12 (C3 SP5 ST1 U3) |  | 6 / 3 |
| 63 | 0x100000A8 (node) | UpdateStatusIcon | no | 5 (C1 ST1 U3) | 152 (C55 SP11 I12 ST28 U46) |  | 91 / 53 |
| 64 | 0x10000136 (node) | TriggerSkillUsed? | no | 5 (SP5) | 49 (SP43 ST1 U5) |  | 18 / 14 |
| 65 | 0x46 (expr) | PositionOf(frame) | no | 5 (C5) | 15 (C11 ST1 U3) |  | 14 / 13 |
| 66 | 0xA (expr) | bitwise and (&) | no | 5 (C1 ST1 U3) | 14 (C4 ST3 U7) |  | 9 / 5 |
| 67 | 0x10000120 (node) | GetEntityRadius | no | 5 (C2 ST3) | 13 (C8 ST5) |  | 12 / 12 |
| 68 | 0x10000009 (node) | StopVitalOverTime | no | 4 (C2 ST2) | 147 (C40 I10 ST62 U35) |  | 78 / 60 |
| 69 | 0x13 (expr) | logical and (&&) | no | 4 (C1 U3) | 44 (C10 ST17 U17) |  | 59 / 26 |
| 70 | 0x10000153 (node) | SetSkillStatOverride | no | 4 (C3 ST1) | 37 (C16 SP6 ST6 U9) |  | 19 / 15 |
| 71 | 0x1E (expr) | clamp(x, lo, hi) | no | 4 (C2 ST2) | 32 (C11 I1 ST20) |  | 27 / 24 |
| 72 | 0x10000089 (node) | ChangeSkill? | no | 4 (C2 ST2) | 24 (C16 ST2 U6) |  | 16 / 12 |
| 73 | 0x14 (node) | HasEventParameter? | no | 4 (ST4) | 17 (C5 ST9 U3) |  | 7 / 5 |
| 74 | 0xD (expr) | normalize | no (op normalize not evaluated) | 4 (C2 ST2) | 12 (C6 ST3 U3) |  | 9 / 8 |
| 75 | 0x10000105 (node) | SetFlag_0105[0/1] | no | 4 (C4) | 5 (C5) |  | 11 / 5 |
| 76 | 0x1000005F (node) | LaunchTetheredMissile | no | 4 (C4) | 4 (C4) |  | 6 / 4 |
| 77 | 0x4 (expr) | min | no | 3 (ST3) | 114 (C15 ST35 U64) |  | 29 / 28 |
| 78 | 0x1000002D (node) | DestroyHotspot | no | 3 (C3) | 49 (C22 SP5 I1 ST13 U8) |  | 37 / 27 |
| 79 | 0x35 (expr) | floor/round | no | 3 (C1 U2) | 28 (C8 I4 ST13 U3) |  | 6 / 6 |
| 80 | 0x100000D8 (node) | ShowSkillError | no | 3 (C2 I1) | 27 (C21 I2 ST3 U1) |  | 33 / 29 |
| 81 | 0x10000059 (node) | CreateHotspot | no | 3 (C3) | 21 (C16 U5) |  | 15 / 13 |
| 82 | 0x10000003 (expr) | ScaleByLevel(level, base, delta) | no | 3 (ST3) | 9 (ST9) | ST4 | 6 / 4 |
| 83 | 0x100000E8 (node) | GetVehicleDriver? | no | 3 (I1 ST2) | 7 (C3 I1 ST3) |  | 6 / 5 |
| 84 | 0x100001B6 (node) | GetLane | no | 3 (ST3) | 3 (ST3) |  | 2 / 1 |
| 85 | 0x100000C2 (node) | AddToEntityList | no | 2 (C2) | 91 (C41 SP11 ST22 U17) |  | 74 / 56 |
| 86 | 0x16 (node) | SetBool | no | 2 (C1 ST1) | 49 (C18 ST17 U14) |  | 73 / 27 |
| 87 | 0x1000008F (node) | AttachEntity | no | 2 (I1 U1) | 29 (C12 I1 ST4 U12) |  | 27 / 20 |
| 88 | 0x1000003C (node) | IsSameEntity / IsOwner | no | 2 (ST2) | 26 (C16 ST4 U6) |  | 51 / 11 |
| 89 | 0x14 (expr) | RandomRange | no | 2 (ST2) | 23 (C10 ST4 U9) |  | 16 / 8 |
| 90 | 0x1000000B (node) | SetSkillTarget | no | 2 (C2) | 22 (C11 I3 ST8) |  | 16 / 14 |
| 91 | 0x100000B0 (node) | SnapToGround? | no | 2 (C1 ST1) | 21 (C14 ST2 U5) |  | 18 / 18 |
| 92 | 0x15 (node) | Switch | no | 2 (ST2) | 17 (C8 ST7 U2) |  | 7 / 7 |
| 93 | 0x04 (node) | EventFilter? | no | 2 (C2) | 14 (C13 U1) |  | 14 / 11 |
| 94 | 0x100000BB (node) | PlaySound / PlayAudioEvent? | no | 2 (ST2) | 13 (C1 I9 ST2 U1) |  | 21 / 11 |
| 95 | 0x44 (expr) | DegToRad | no | 2 (C2) | 12 (C5 ST1 U6) |  | 7 / 6 |
| 96 | 0x2E (expr) | sin | no | 2 (C2) | 7 (C4 U3) |  | 5 / 5 |
| 97 | 0x1000011E (node) | Unk_011E(-, source)[0/1, n] | no | 2 (ST2) | 3 (C1 ST2) |  | 5 / 2 |
| 98 | 0x7 (expr) | sqrt | no | 2 (C1 ST1) | 3 (C2 ST1) |  | 2 / 2 |
| 99 | 0x100000C4 (node) | IsInEntityList | no | 1 (C1) | 57 (C25 SP5 ST17 U10) |  | 44 / 41 |
| 100 | 0x10000004 (node) | SetPerceptionRange | no | 1 (ST1) | 50 (C1 SP5 ST3 U41) |  | 6 / 6 |
| 101 | 0x10000092 (node) | RemoveTempVital | no | 1 (C1) | 49 (C14 I1 ST25 U9) |  | 15 / 15 |
| 102 | 0x17 (node) | ClearVariable | no | 1 (C1) | 35 (C11 ST15 U9) |  | 44 / 21 |
| 103 | 0x1000000D (node) | SetAITarget / Taunt | no | 1 (C1) | 28 (C13 SP6 ST3 U6) |  | 12 / 10 |
| 104 | 0x10000005 (node) | SetSkillAttached | no | 1 (C1) | 22 (C11 I3 ST8) |  | 16 / 14 |
| 105 | 0x1000004F (node) | AIMoveTo | no | 1 (ST1) | 22 (C12 ST4 U6) |  | 17 / 7 |
| 106 | 0x10000109 (node) | FindValidPosition | no | 1 (ST1) | 20 (C14 ST2 U4) |  | 15 / 12 |
| 107 | 0x1000001B (node) | CancelMovement? | no | 1 (C1) | 20 (C9 I3 ST8) |  | 14 / 12 |
| 108 | 0x10000134 (node) | SetMissileVelocity | no | 1 (C1) | 19 (C15 ST3 U1) |  | 20 / 18 |
| 109 | 0x10000090 (node) | SetObjectState? | no | 1 (U1) | 17 (SP11 I1 ST2 U3) |  | 11 / 10 |
| 110 | 0x10000151 (node) | Unk_0151 (missile) | no | 1 (C1) | 16 (C10 ST1 U5) |  | 8 / 8 |
| 111 | 0x1000013E (node) | DashToEntity | no | 1 (C1) | 15 (C14 ST1) |  | 17 / 17 |
| 112 | 0x100000AD (node) | SuppressInput? | no | 1 (C1) | 14 (C5 SP6 ST2 U1) |  | 26 / 10 |
| 113 | 0x100000C8 (node) | SetUntargetable? | no | 1 (ST1) | 11 (C4 SP5 ST1 U1) |  | 17 / 9 |
| 114 | 0x10000072 (node) | IsClass | no | 1 (C1) | 11 (C9 ST1 U1) |  | 14 / 9 |
| 115 | 0x1000016F (node) | IsInFront? | no | 1 (C1) | 9 (C4 ST1 U4) |  | 6 / 5 |
| 116 | 0x10000150 (node) | ShowMinimapTargetingRing2 | no | 1 (C1) | 8 (C5 U3) |  | 7 / 3 |
| 117 | 0x100000F1 (node) | SetMovementMode? | no | 1 (C1) | 8 (C6 ST2) |  | 14 / 7 |
| 118 | 0x19 (expr) | round (floor(x + 1/2))? | no | 1 (ST1) | 8 (C2 ST1 U5) |  | 8 / 3 |
| 119 | 0x1000010D (node) | SpawnWorldState? | no | 1 (ST1) | 7 (C5 ST2) |  | 3 / 3 |
| 120 | 0x10000078 (node) | SetGroundMarker? | no | 1 (C1) | 7 (C1 SP5 U1) |  | 10 / 6 |
| 121 | 0x1000014D (node) | StartAITask2? | no | 1 (C1) | 3 (C3) |  | 3 / 3 |
| 122 | 0x3C (expr) | vector.z | no | 1 (C1) | 3 (C2 U1) |  | 10 / 4 |
| 123 | 0x10000168 (node) | StartAITask3? | no | 1 (ST1) | 2 (C1 ST1) |  | 2 / 1 |
| 124 | 0x100000DD (node) | DestructionRaycast | no | 1 (C1) | 2 (C2) |  | 2 / 2 |
| 125 | 0x10000146 (node) | FindValidPosition2 | no | 1 (C1) | 1 (C1) |  | 1 / 1 |
| 126 | 0x1000017E (node) | SetDestructibleState? | no | 1 (C1) | 1 (C1) |  | 2 / 1 |
| 127 | 0x1000009E (node) | Unk_009E | no | 1 (C1) | 1 (C1) |  | 1 / 1 |
| 128 | 0x10000152 (node) | GetMatchTime | no | 1 (ST1) | 1 (ST1) |  | 1 / 1 |
| 129 | 0x10000087 (node) | SetUsageObject | no | 1 (ST1) | 1 (ST1) | ST1 | 2 / 1 |
| 130 | 0x5 (expr) | cross | no (op cross not evaluated) | 1 (ST1) | 1 (ST1) |  | 1 / 1 |
| 131 | 0x11 (expr) | pow | no | 1 (C1) | 1 (C1) |  | 2 / 1 |
| 132 | 0x100000D2 (node) | IsSkillActive? | no | 0 () | 144 (C55 ST1 U88) | C16 | 64 / 64 |
| 133 | 0xC (expr) | decrement (x - 1) | wrong (evaluated as `/`) | 0 () | 69 (C34 SP11 I1 ST10 U13) |  | 36 / 27 |
| 134 | 0x100000C5 (node) | GetEntityListItem | no | 0 () | 58 (C20 SP11 ST16 U11) |  | 66 / 32 |
| 135 | 0x100000CD (node) | RemoveFromEntityList | no | 0 () | 54 (C14 SP11 ST18 U11) |  | 33 / 26 |
| 136 | 0x10000147 (node) | GetSourcePosition? | no | 0 () | 40 (U40) |  | 1 / 1 |
| 137 | 0x10000025 (node) | FindScatterPosition | no | 0 () | 37 (C20 SP5 I3 ST3 U6) |  | 31 / 25 |
| 138 | 0x100000F9 (node) | FindInEntityList | no | 0 () | 22 (C2 ST13 U7) |  | 15 / 15 |
| 139 | 0x1A (expr) | ToInt32 (truncate) | no | 0 () | 22 (C6 I4 ST11 U1) |  | 6 / 5 |
| 140 | 0x100000D9 (node) | AddStacks | no | 0 () | 21 (C11 ST2 U8) |  | 5 / 4 |
| 141 | 0x100000E4 (node) | SetPhysicsState? | no | 0 () | 15 (SP11 I1 ST2 U1) |  | 8 / 7 |
| 142 | 0x100000DC (node) | HasState? | no | 0 () | 12 (C6 ST2 U4) |  | 5 / 4 |
| 143 | 0x18 (node) | AreEqual | no | 0 () | 12 (C6 ST2 U4) |  | 19 / 9 |
| 144 | 0x10000169 (node) | SetCharges | no | 0 () | 10 (I9 U1) |  | 3 / 3 |
| 145 | 0x1000016B (node) | GetCharges | no | 0 () | 10 (I9 U1) |  | 3 / 3 |
| 146 | 0x10000020 (node) | CheckLineOfSight? | no | 0 () | 10 (C6 ST1 U3) |  | 12 / 2 |
| 147 | 0x10000148 (node) | SetTargetingMode | no | 0 () | 8 (SP6 I1 U1) |  | 2 / 2 |
| 148 | 0x10000191 (node) | Unk_0191(-, pos, pos) | no | 0 () | 6 (C2 ST1 U3) |  | 2 / 2 |
| 149 | 0x100001A9 (node) | SetHidden? | no | 0 () | 6 (C1 SP5) |  | 10 / 3 |
| 150 | 0x1000003D (node) | Unk_003D(value)[flag] | no | 0 () | 6 (C3 U3) |  | 4 / 1 |
| 151 | 0x100001A7 (node) | Unk_01A7[0/1] | no | 0 () | 6 (C2 ST2 U2) |  | 2 / 1 |
| 152 | 0x1000007F (node) | EndTeleport? | no | 0 () | 5 (SP5) |  | 2 / 2 |
| 153 | 0x1000007D (node) | BeginTeleport? | no | 0 () | 5 (SP5) |  | 2 / 2 |
| 154 | 0x10000143 (node) | IsStealthed? | no | 0 () | 5 (SP5) |  | 2 / 1 |
| 155 | 0x10000144 (node) | IsRevealed? | no | 0 () | 5 (SP5) |  | 2 / 1 |
| 156 | 0x100000E5 (node) | Unk_00E5 | no | 0 () | 5 (C1 ST4) |  | 2 / 2 |
| 157 | 0x1000005C (node) | Unk_005C(entity)[0] | no | 0 () | 5 (SP5) |  | 2 / 2 |
| 158 | 0x100000C7 (node) | Unk_00C7(entity, entity)[n, n, 2] | no | 0 () | 5 (C1 ST1 U3) |  | 3 / 2 |
| 159 | 0x100001B8 (node) | Unk_01B8(-)[0/1] | no | 0 () | 5 (SP5) |  | 2 / 1 |
| 160 | 0x10000108 (node) | Unk_0108(SELF, -)[8/9] | no | 0 () | 5 (SP5) |  | 3 / 2 |
| 161 | 0x45 (expr) | ForwardVector(frame) | no | 0 () | 5 (C1 ST1 U3) |  | 1 / 1 |
| 162 | 0xB (expr) | cos | no | 0 () | 5 (C2 U3) |  | 2 / 2 |
| 163 | 0x10000174 (node) | Unk_0174 | no | 0 () | 4 (C3 ST1) |  | 1 / 1 |
| 164 | 0x100000A1 (node) | Unk_00A1(entity, entity) | no | 0 () | 4 (C1 U3) |  | 2 / 1 |
| 165 | 0x10000172 (node) | Unk_0172 | no | 0 () | 4 (C3 ST1) |  | 1 / 1 |
| 166 | 0x100000EC (node) | SetCurrencyOption | no | 0 () | 4 (C1 U3) |  | 1 / 1 |
| 167 | 0x100001B9 (node) | Unk_01B9(-) | no | 0 () | 3 (C1 U2) |  | 1 / 1 |
| 168 | 0x1000014C (node) | StartAITask? | no | 0 () | 3 (C3) |  | 7 / 3 |
| 169 | 0x100000F5 (node) | SwapSkillScript | no | 0 () | 3 (I2 U1) |  | 4 / 4 |
| 170 | 0x100001B3 (node) | SetLane | no | 0 () | 3 (ST3) |  | 2 / 1 |
| 171 | 0x100000AE (node) | Unk_00AE predicate | no | 0 () | 3 (C3) |  | 1 / 1 |
| 172 | 0x21 (expr) | ceil | no | 0 () | 3 (C3) |  | 3 / 3 |
| 173 | 0x10000149 (node) | AddDamageRedirect | no | 0 () | 2 (ST2) |  | 2 / 2 |
| 174 | 0x100000DA (node) | Unk_00DA(SELF, SELF) | no | 0 () | 2 (C2) |  | 2 / 1 |
| 175 | 0x100001AD (node) | Unk_01AD(target, -)[14] | no | 0 () | 2 (C2) |  | 2 / 2 |
| 176 | 0x10000135 (node) | Unk_0135(-) | no | 0 () | 2 (C2) |  | 2 / 2 |
| 177 | 0x1000010E (node) | Unk_010E(-) | no | 0 () | 2 (C1 ST1) |  | 1 / 1 |
| 178 | 0x1000014A (node) | RemoveDamageRedirect | no | 0 () | 2 (ST2) |  | 2 / 2 |
| 179 | 0x10000022 (node) | ShowMinimapTargetingRing | no | 0 () | 2 (C2) |  | 8 / 7 |
| 180 | 0x10000056 (node) | HideMinimapTargetingRing | no | 0 () | 2 (C2) |  | 8 / 7 |
| 181 | 0x10000030 (node) | StartScriptOn | no | 0 () | 2 (C2) |  | 2 / 2 |
| 182 | 0x47 (expr) | Unk_47(a, b, c) (lerp?) | no | 0 () | 2 (C1 ST1) |  | 1 / 1 |
| 183 | 0x0C (node) | DebugLog | no | 0 () | 2 (ST2) |  | 9 / 2 |
| 184 | 0x10000137 (node) | ResizeHotspot | no | 0 () | 1 (C1) |  | 4 / 2 |
| 185 | 0x1000016E (node) | GetCurrentRange? | no | 0 () | 1 (C1) |  | 3 / 2 |
| 186 | 0x10000063 (node) | Unk_0063(-)[0x1000018B] | no | 0 () | 1 (ST1) |  | 4 / 3 |
| 187 | 0x10000065 (node) | GrantCurrency | no | 0 () | 1 (ST1) |  | 4 / 4 |
| 188 | 0x100001A5 (node) | SetLatencyWindow? | no | 0 () | 1 (C1) |  | 1 / 1 |
| 189 | 0x10000141 (node) | SetTeleportOffset? | no | 0 () | 1 (C1) |  | 1 / 1 |
| 190 | 0x100000F3 (node) | Unk_00F3 | no | 0 () | 1 (C1) |  | 1 / 1 |
| 191 | 0x10000002 (node) | SkillComponentAction_0002 | no | 0 () | 1 (C1) |  | 5 / 5 |
| 192 | 0x10000048 (node) | UI_Condition_0048 | no | 0 () | 1 (C1) |  | 2 / 2 |
| 193 | 0x10000043 (node) | UI_Unk_0043[flag] | no | 0 () | 0 () |  | 1 / 1 |
| 194 | 0x1000003A (node) | UI_ShowMovie | no | 0 () | 0 () |  | 10 / 1 |
| 195 | 0x1000003B (node) | UI_OnEvent | no | 0 () | 0 () |  | 59 / 1 |
| 196 | 0x1000011A (node) | ShowAnnouncement | no | 0 () | 0 () |  | 10 / 1 |
| 197 | 0x10000138 (node) | Unk_0138(user)[3] | no | 0 () | 0 () |  | 1 / 1 |
| 198 | 0x100001A3 (node) | ShowTrainingFloatyText | no | 0 () | 0 () |  | 2 / 1 |
| 199 | 0x10000167 (node) | NotifyHUDElement | no | 0 () | 0 () |  | 63 / 7 |
| 200 | 0x1000019D (node) | Unk_019D | no | 0 () | 0 () |  | 4 / 2 |
| 201 | 0x10000097 (node) | SetSkillCooldownState? | stub (no-op) | 0 () | 0 () |  | 165 / 75 |
| 202 | 0x10000195 (node) | SkillEcho? | stub (no-op) | 0 () | 0 () |  | 226 / 221 |
| 203 | 0x10000057 (node) | ReleaseFacing | stub (no-op) | 0 () | 0 () |  | 306 / 198 |
| 204 | 0x10000052 (node) | IsInRangeAndAngle | stub (always true) | 0 () | 0 () |  | 211 / 132 |
| 205 | 0x10000060 (node) | SetTutorialMarker? | no | 0 () | 0 () |  | 12 / 5 |
| 206 | 0x100000B2 (node) | StopMissionEvent | no | 0 () | 0 () |  | 1 / 1 |
| 207 | 0x10000039 (node) | SendMissionEvent | no | 0 () | 0 () |  | 4 / 1 |
| 208 | 0x10000119 (node) | StopAnnouncement | no | 0 () | 0 () |  | 5 / 1 |
| 209 | 0x10000086 (node) | Unk_0086 | no | 0 () | 0 () |  | 1 / 1 |
| 210 | 0x1000010A (node) | SetGeneratorEntry | no | 0 () | 0 () |  | 1 / 1 |
| 211 | 0x10000016 (node) | SpawnGeneratorUnit | no | 0 () | 0 () |  | 2 / 1 |
| 212 | 0x10000183 (node) | ActivateArtifacts? | no | 0 () | 0 () |  | 4 / 3 |
| 213 | 0x10000181 (node) | TutorialSetup_0181 | no | 0 () | 0 () |  | 7 / 4 |
| 214 | 0x1000019B (node) | BreakDestructible? | no | 0 () | 0 () |  | 1 / 1 |
| 215 | 0x10000117 (node) | SetTracked | no | 0 () | 0 () |  | 4 / 2 |
| 216 | 0x1000017B (node) | TutorialStep? | stub (no-op) | 0 () | 0 () |  | 29 / 21 |
| 217 | 0x10000121 (node) | UpdateObjective / MissionText? | no | 0 () | 0 () |  | 12 / 6 |
| 218 | 0x10000111 (node) | ShowTutorialHint | no | 0 () | 0 () |  | 1 / 1 |
| 219 | 0x1000007E (node) | SetTeam | no | 0 () | 0 () |  | 4 / 3 |
| 220 | 0x1000015D (node) | Unk_015D | no | 0 () | 0 () |  | 1 / 1 |
| 221 | 0x100000BD (node) | Unk_00BD | no | 0 () | 0 () |  | 1 / 1 |
| 222 | 0x100000B8 (node) | SetImpactState? | no | 0 () | 0 () |  | 6 / 3 |
| 223 | 0x10000173 (node) | RandomChance | no | 0 () | 0 () |  | 4 / 2 |
| 224 | 0x1000013C (node) | Unk_013C(SELF) trigger | no | 0 () | 0 () |  | 1 / 1 |
| 225 | 0x100001B0 (node) | SpawnFromShooter? | no | 0 () | 0 () |  | 1 / 1 |
| 226 | 0x1000004D (node) | UI_SendStateMachineEvent | no | 0 () | 0 () |  | 35 / 1 |
| 227 | 0x100001B7 (node) | UI_Condition_01B7 | no | 0 () | 0 () |  | 1 / 1 |
| 228 | 0x10000189 (node) | Unk_0189 | no | 0 () | 0 () |  | 1 / 1 |
| 229 | 0x1000000A (node) | EndSkill | stub (no-op) | 0 () | 0 () |  | 272 / 248 |
| 230 | 0x10000114 (node) | SetCollisionLayer | stub (no-op) | 0 () | 0 () |  | 4 / 4 |
| 231 | 0x1000006F (node) | DisableCollision | stub (no-op) | 0 () | 0 () |  | 109 / 82 |
| 232 | 0x10000070 (node) | EnableCollision | stub (no-op) | 0 () | 0 () |  | 89 / 87 |
| 233 | 0x1000000E (node) | BeginSkill | stub (no-op) | 0 () | 0 () |  | 255 / 248 |
| 234 | 0x1000009C (node) | SetEnvironmentSetting? | stub (no-op) | 0 () | 0 () |  | 36 / 19 |
| 235 | 0x100001A4 (node) | Unk_01A4[r4] | no | 0 () | 0 () |  | 2 / 1 |
| 236 | 0x100001A2 (node) | Unk_01A2[r4] | no | 0 () | 0 () |  | 1 / 1 |
| 237 | 0x10000049 (node) | OnMissionEvent | no | 0 () | 0 () |  | 4 / 1 |
| 238 | 0x10000182 (node) | TutorialSetup_0182 | no | 0 () | 0 () |  | 5 / 4 |
| 239 | 0x1000018A (node) | IsChampion(class) trigger | no | 0 () | 0 () |  | 1 / 1 |
| 240 | 0x100000CB (node) | UI_ShowMovie2 | no | 0 () | 0 () |  | 1 / 1 |
| 241 | 0x10000115 (node) | UI_Condition_0115 | no | 0 () | 0 () |  | 2 / 1 |
| 242 | 0x1000015E (node) | UI_Condition_015E | no | 0 () | 0 () |  | 2 / 1 |
| 243 | 0x100001B1 (node) | Unk_01B1[2] predicate | no | 0 () | 0 () |  | 1 / 1 |
| 244 | 0x1000017D (node) | OnTutorialEvent | no | 0 () | 0 () |  | 9 / 3 |
| 245 | 0x1000018F (node) | UI_ExitWorldLoadWrapper | no | 0 () | 0 () |  | 2 / 1 |
| 246 | 0x100000CC (node) | UI_DestroyGameFront | no | 0 () | 0 () |  | 10 / 1 |
| 247 | 0x10000179 (node) | UI_SetHUDVisibility | no | 0 () | 0 () |  | 1 / 1 |
| 248 | 0x10000186 (node) | Unk_0186 | no | 0 () | 0 () |  | 1 / 1 |



## 6. Reproduction (scratch, not in the project)

- Patched decoder: a copy of `tools/script_decoder.py` with fixes A-D (initializers 0x13A6710 / 0x13A67D0, record
  finder, bool slots and fallback sizes, compact counts), output to a scratch `trees3/` folder: 875 of 875 `ok`.
- Initializer scan: every `call 0x45FA20` in 0x13A0000-0x13D0000 with the stores before it: 365 node, 76 expression
  (74 + 0xC + 0x10), 6 value registrations; graph-registry types come from 0x44E240.
- Coverage: the logic of `tools/script_coverage.py`, extended to the five root sets and to statuses
  (`apply_status`), plus the static closure described in part 2.
