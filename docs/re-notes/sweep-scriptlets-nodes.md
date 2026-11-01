# Sweep: client scriptlet action types and the server-side gaps in the script nodes

Static analysis of `InfiniteCrisis.exe` (Ghidra via REA, image base 0x400000, VA), the scriptlet tables of the 127
packs that hold them (`data/cache/tables_*.json` list), the 875 decoded script trees (`data/script_trees`) and the
`ics` runtime (`ics/script_runtime.py`, `ics/script_nodes.py`, `ics/world.py`). 2026-10-25.
Confidence: **C** = read in code or exact data, **P** = probable, **O** = open.

Scratch scripts (not in the project): action-type / variable scans over the packs (numpy word scans), the factory
table parse of `0x669CE0`, and the node-execute (vtable +0x28) read of every logged node.

---------------------------------------------------------------------------------------------------------------------

## A. Scriptlet action types

### A.1 The registry (C)

`0x669CE0` builds 0x31 factory slots (`slot = type`), each factory object = `{vtable, category}` (`puVar2[1]`);
factory vtable = `[dtor 0x9F66F0, create, ?, size getter (mov eax, size)]`. 47 factories: types 0x01-0x30
except 0x13 (no factory in `0x669CE0`, but an action vtable `0x15CED88` reports type 0x13); type 0x00 does not exist. Action (definition) vtables were found by their fixed slots (`+0x04 = 0x672630`,
`+0x2C = 0x55B9C0`); `+0x24` = type getter (`mov eax, type; ret`), **`+0x28` = execute**, `+0x0C` = field
serializer, `+0x48` = allowed when started from the network (`0x9C3A20` = true for every type except 0x29 / 0x2F,
whose +0x48 is `0x55B9C0`).

An action's execute gets `(result, ctx, run, out instance)`; a returned *instance* stays attached to the run (the
"attachments", client-scriptlets-graphs.md 1.4). The common target rule (C, types 1, 2, 9, 0x16, 0x17, 0x1F, 0x2F):
`0x51EF90(field)` reads a **target selector** field (0x18 = target, 0x06 = target list, 0x03 = re-target), resolved
by `0x517F00` / `0x51D590`; **no selector -> the run's own object** (`ctx+8` IID). A selector is serialized as
`field | field | 1 | mode | value`; **mode 3 = a scriptlet variable or the target entity's own property** (by the
property's storage: 6 = the 0x8D variable table, 4 = the entity's object table), mode 4 = a fixed role (9535 uses,
no server input), mode 5 once.

### A.2 Every action type (C: addresses; P: meanings)

Data counts = top-level actions found in the 127 packs (header `type | n_bind | (a, b, field, var) x n | 0 | 0 | 1 |
1.0f | jitter | intensity | time`); child actions inside containers use the property form and are not counted.

| Type | Def vtable | Execute | Data | Meaning | Needs from the server |
|---|---|---|---|---|---|
| 0x01 | `0x15CE630` | `0x677590` | 5558 | **material / tint on the targets' render component**: for each target of field 0x18 (else self) `entity+0x18` vfunc +0x58 / +0x60 with three floats (def +0x34..+0x3C, P an RGB) and an index (+0x6C), via `0x673180`; persistent instance `0x15CFB50` restores it (P: hit flashes, glows) | target var `0x10000030` / `0x100003FF` / `0x100004E2` (prop) when bound |
| 0x02 | `0x15CF890` | `0x673280` | 165 | projectile / beam (C, projectiles-homing.md) | field 0x18 target (`0x10000030`, or prop `0x100004E2` for tethers), speed `0x100009EB` -> fields 0xFA / 0x372 |
| 0x03 | `0x15CE450` | `0x657780` | 627 | sound event (`0x775D40`; skipped when the object is not audible `0x588240` or, with +0x45, not the local player `0x635200`) (P) | nothing |
| 0x04 | `0x15CE6E0` | `0x65B0A0` | 517 | object at the entity's transform (`0x635070` -> `0x7DDD20`, P: decal / light / mesh) | binds `0x100007CF` (f32 prop), `0x10000559` (position var), `0x10000205` |
| 0x05 | `0x15B1280` | `0x52F170` | 4595 | timed child list: runs its children (property 6) in time order (C) | nothing |
| 0x06 | `0x15CE828` | `0x66CC00` | 45 | acts on the run's sub-entity (`ctx+0x58`, `0x6689D0`) (O) | sub-entity of 0x8D (`second`) |
| 0x07 | `0x15CE570` | `0x658E10` | - | sound, variant (`0x775F30`) (P) | nothing |
| 0x08 | `0x15CEAB0` | `0x673CF0` | - | 8-kind switch into the entity's `+0x14` component vfunc +0x50 (P: camera / render effect) | nothing |
| 0x09 | `0x15B18E0` | `0x5327D0` | 14 | run a scriptlet key on other entities (field 3 re-target, field 0x18 list, copies vars through `0x77A`) (C for the calls) | the targets' vars |
| 0x0A | `0x15B1888`? | (factory `0x662890`) | 1 | O | - |
| 0x0B | `0x15CEB70` | `0x65DA00` | - | persistent object (`0x616500`, local-player filter +0x10C) (O) | - |
| 0x0C | `0x15CEC20` | `0x6852B0` | 2 | (`0x683AF0`) (O) | - |
| 0x0D | `0x15CE510` | `0x658B60` | - | **disabled** (returns 1) | - |
| 0x0E | `0x15CF3B8` | `0x5157B0` | - | **no-op** (returns 0) | - |
| 0x0F | `0x15B17B0` | `0x532210` | 641 | keep-alive instance (holds the run until stopped / signalled) (C) | a stop signal (StopScriptlet) |
| 0x10 | `0x15CE4B0` | `0x657F60` | - | sound with position / parameters (`0x775E20`) (P) | - |
| 0x11 | `0x15CECD8` | `0x67F650` | children | particle emitter `0x18......` (P, data) | - |
| 0x12 | `0x15B1220` | `0x52EEF0` | 1 | container (`0x5271A0`) (O) | - |
| 0x13 | `0x15CED88` | `0x660650` | - | two flagged calls `0x6341E0` / `0x634230` on the entity (O) | - |
| 0x14 | `0x15CF250` | `0x672930` | 1045 | raise animation-graph event; literal or **var `0x780`** (C) | `0x780` (also `0x100003F2` bound 3x) |
| 0x15 | `0x15CF0B0`? | `0x684D10` | 111 | as 0x17 (shares the vtable) (P) | - |
| 0x16 | `0x15B1690` | `0x524030` | - | **clear a property** (field +0x34) on the targets (field 6); authority-only when +0x38 (`DAT_01B779A4 & 2`) (C) | - |
| 0x17 | `0x15CF0B0` | `0x684D10` | (children) | run a key on a target list (C) | - |
| 0x18 | `0x15B16F0` | `0x531CE0` | - | run an action-list **record** (DB type 0x15) (C) | - |
| 0x19 | `0x15B1750` | `0x531F00` | - | pick a child branch by name (`_stricmp`) (C) | - |
| 0x1A | `0x15B1430` | `0x52FDD0` | 127 | timer instance (`0x52B840`) (P: delay / loop) | - |
| 0x1B-0x1E | `0x15CF7B0` / `750` / `6F0` / `810` | `0x6774D0` / `470` / `410` / `530` | 17 | **set an animation-graph variable** on the entity's graph component (`entity+4`, `0x677150`) (C) | - |
| 0x1F | `0x15B15D0` | `0x523C50` | - | **set a property** (field +0x34) on the targets, value from field 0x16 (IID) or literal; authority-gated like 0x16 (C) | - |
| 0x20 | `0x15CEFD0` | `0x660E40` | - | `0x611C10(flag, run IID)` (O) | - |
| 0x21 | `0x15CEF20` | `0x6609E0` | - | random-time instance (`0x616360`) (P: random delay) | - |
| 0x22 / 0x24 | `0x15CF1E0` / `0x15B1500` | `0x530310` | 2329 / 341 | property-condition container (C, P condition) | **the watched properties**: `0x10000030` (as var), LifeState `0x100000FA`, `0x10000B2D`, `0x100003F3`, `0x100007A2` ... |
| 0x23 | (`0x15B1490`?) | `0x530310` | 1 | container variant | - |
| 0x25 | `0x15B1570` | `0x534480` | 162 | container (`0x52C110`) (O) | - |
| 0x26 | `0x15CE790` | `0x65B6A0` | - | global timed effect (`DAT_01B694B8` vfunc +0x34, two durations) (P: screen / lighting fade) | - |
| 0x27 / 0x2A | `0x15CE8D8` / `0x15CE9F8` | `0x9DB900` | - | **no-op** | - |
| 0x28 | `0x15CE938` | `0x65C7D0` | 39 | sub-entity component (`entity+0x58` vfunc +0x4C(ctx+0x58)) (O) | 0x8D sub-entity |
| 0x29 | `0x15B1630` | `0x530FA0` | 237 | for each element of a list (`0x4F5C20(0x801)` / `entity+0x58` vfunc +0x5C) run the children (P) | - |
| 0x2B | `0x15CE998` | `0x668E50` | 13 | toggle a sub-entity flag (`+0x194`) (O) | - |
| 0x2C | `0x15CEE38` | `0x674B80` | - | named global / UI variable (`DAT_015CE30C`) (O) | - |
| 0x2D | `0x15CE5D0` | `0x659460` | - | sound variant (`0x776060`) (P) | - |
| 0x2E | `0x15CEB10` | `0x682110` | - | render / post-process parameter, kinds 1000-5000 (`0x718xxx`) (P) | - |
| 0x2F | `0x15CFC30` | `0x6694F0` | 36 | if the target (field 0x18) has a given effect in its `+0x58` list: run child list 0x12, else 0x1C (P) | the target's statuses (`0x200F` effects) |
| 0x30 | `0x15B1340` | `0x5158C0` | - | delegates to a sub-definition (vfunc +0x60 / +0x3C) (O) | - |

Consequence (C): the only server inputs any action reads are (1) the 0x8D **variable table**, (2) the **target
entity's own properties** (mode 3 on an object-table property), (3) the 0x8D **sub-entity** (types 6, 0x28), and
(4) the entity's statuses (0x2F). No action type needs a separate network message.

### A.3 What the scriptlet data reads, and who supplies it (C counts, P meanings)

Variable references in all 127 table packs: selectors `f | f | 1 | 3 | var` and bindings `(a, b, field, var)`.
"Scripts pass" = the variable lists of RunScriptlet `0x10000034` / StartScriptlet `0x10000103` / RunFxScriptlet
`0x1000013A` in the 875 trees (ics forwards all of them since `[ics] scriptlet_variables = true`).

| Id | Kind / storage | Data refs | Scripts pass | Supplied by ics today | Gap |
|---|---|---|---|---|---|
| `0x10000030` | iid, variable | 496 sel (field 0x18) | 242 | yes (RunScriptlet vars, `run_scriptlet`) | - |
| `0x100003FF` | iid, variable | 445 sel (0x18) | 32 (22 keys) | yes when passed | O: a per-key diff (body vars vs passed vars) was attempted and failed (body delimiting); keys started by ics itself (director, units) without it get the field default |
| `0x100004E2` | iid, **entity prop** (net, NetSharedVisually) | 259 sel (0x18 / 6) | - | spawned objects / missiles get it = creator (`world.py` 1845, 2155) | objects created otherwise (units, map props, cinematic actors) never get it; P minor |
| `0x10000019` | position, entity prop | 60 sel (field 2) | - | no | P: the object's anchor / spawn position |
| `0x10000402` | iid, variable | 47 sel | 1 | when passed | AGL Meltdown passes it (skill-second-stages.md 5) |
| `0x100008BA` | iid, entity prop (net) | 25 sel | - | no | O (group 0x5C) |
| `0x1000018D` | iid, entity prop | 25 sel | - | no | the order target (client stores it on order, full-combat-skills.md); a server-started key on another unit lacks it |
| `0x1000099A` | iid, entity prop (attribute, net) | 6 sel | - | no | O |
| `0x1000050A` | did (0x1E fx), variable | 373 binds (field 0x617) | 10 + every Start/RunFx/HitEffect | yes | - |
| `0x10000400` | vector3, variable | 198 binds (field 0x3DB) | **0** | **no** | O: no script passes it; the client registers it next to 0x100003FF / 0x10000402 (`0x876F00`-`0x876F60`): P set by the client's local start path (hit / aim point); a server 0x8D gets the field default |
| `0x100009EB` | f32, variable | 305 binds (0xFA / 0x372) | 88 | yes | - |
| `0x100006FE` | f32, attribute (net) | 143 binds (field 0x7DE) | - | units only (`units.py` 251, `unit_attack_speed_property`) | champions keep the template value; P: an attack-speed buff (AddAttributeModifier) does not reach the bound field if the binding reads the raw property (`0x58B320`) rather than the attribute |
| `0x100007D3` / `0x10000449` / `0x1000049A` / `0x1000089D` / `0x10000592` / `0x100007CF` | entity props | 14 / 13 / 10 / 8 / 4 / 5 binds | - | no | O (low counts) |
| `0x100002F8` / `0x1000033E` / `0x10000050` / `0x1000075E` / `0x10000126` | variables | 9 / 9 / 8 / 5 / 4 binds | 8 / 14 / 15 / - / - | when passed | - |
| `0x780` | enum, variable | 2 binds + action 0x14 | ics `graph_event` | yes | - |

Two storage rules decide the recipe (client-scriptlets-graphs.md 1.4, C): a **variable** (storage 6) must be in the
0x8D table; an **entity property** (storage 4) must be on the *target* object, sent with its creation bundle or the
set-property event 0x6.

---------------------------------------------------------------------------------------------------------------------

## B. Script nodes that ics runs as no-ops (`_logged` / `_noop`)

63 node classes are registered as logged no-ops (`ics/script_nodes.py` 2111-2175) or `_noop`
(`ics/script_runtime.py` 2059-2067). Uses = node count / scripts in the 875 trees (the catalog `uses` column is stale
for several of them). **Client execute** = node vtable +0x28 read from the tree's own `vt` (`0xAB4D80` / `0x9DB900`
= empty: the node is **server-only**, its effect existed only on the original server). A non-empty client half only
runs inside a client copy of the script; ics replicates no script instances (full-combat-skills.md 1.8), so a
visible client half must be reproduced with a server message too.

### B.1 Visible: must be implemented (priority H / M)

| Node | Uses | Client execute | What it does | Server recipe |
|---|---|---|---|---|
| `0x10000057` ReleaseFacing | 306 / 198 | `0x995E80` (empty call) | ends the facing lock of FaceTarget `0x1000003F` (`$FacingIDVariable`) | make FaceTarget a lock: keep turning the caster to the target every tick (and ignore move-heading) until ReleaseFacing / script end (M; 194 scripts use FaceTarget) |
| `0x1000009C` SetEnvironment | 36 / 19 | `0xAB4AE0` | on the **local player's** entity: values[0] on -> set property **`0x956`** (enum `0x30000092`, lighting environment) = values[1], or clear it when 0 (`0x58B4C0`) | event 0x6 on the champion: `0x956` = value (kind enum) / reset; scene and match scripts (`0x340002CF`, cinematics) (H for maps' look) |
| `0x1000010D` / `0x1000010E` | 3 / 3, 1 / 1 | empty | `(slave, SELF)[0]` right after SpawnEntity of a clone (`0x34000543`, Arcane Harley E `0x34000778`), `(-, -)[0x2E0004E6]` in status `0x340000EE` (+ untargetable); `0x1000010E` at that status' exit (P: **copy SELF's appearance onto the clone / disguise as world state, and restore**) | clone: create the slave with the caster's class + costume (and name / health bar); disguise: re-send the entity with world state `0x2E0004E6`, restore at 0x1000010E (M) |
| `0x1000009E` VitalsLink | 1 / 1 | `0x9946F0` | Raven R (`0x3400067C`): `(AstralProjection, SELF)[1]` -> projection's vitals component `vfunc+0x60(&SELF, 1)` (P: the projection shows Raven's health) | mirror Raven's 0x42 vitals onto the projection's eid while linked (M) |
| `0x1000011E` RevealToTeam | 5 / 2 | empty | `(-, EffectSource)[1 46] / [1 45] / [0 0]` beside a `0x100007BF` HiddenHandle modifier (`0x34000363`) | per-team visibility of SELF (needs the vision model): send / withhold the entity to EffectSource's team (M, with fog) |
| `0x100001B9` BeginFakeDeath | 1 / 1 | empty | Solomon Grundy passive `0x34000662`, with TreatAsDead `0x10000B2D`, untargetable, health lock | play the defeat set: LifeState / `_Defeat_OnIncapacitated` on him, `_Defeat_OnRevive` at the exit (M) |
| `0x10000087` SetUsageObject | 2 / 1 | empty | `(SELF, object)[0/1]` (`0x3400012D`) | the usage messages 0x2077 / 0x20CE for that object while on (M, props) |
| `0x10000090` SetObjectState | 11 / 10 | empty | `(entity)[17/19/1/8, flag]` on thrown objects / weapons (Super Strength, Stolen Powers) | P: the object's state scriptlet (Object_* keys of its table) or its LifeState; check the prop tables (M) |
| `0x100000E4` SetPhysicsEnabled | 8 / 7 | empty | `(entity)[0/1]` on lifted / thrown props | stop / resume the prop's server physics and send its stop state (M) |
| `0x10000075` SetTargetingMode | 25 / 22 | empty | `(SELF/Target)[0]` after StartCooldown in basic attacks and pick-ups | P: drop the queued order / auto-attack target, so the champion does not resume attacking (M-L) |
| `0x10000114` SetCollisionLayer | 4 / 4 | `0x97D950` -> `0x971F30` (physics component `0xAA10B0`) | sets the object's collision layer on the client | P: the client-side collision of dashes; mirror in `CastWorld.collides` (M-L) |
| `0x100000BB` PlaySound | 21 / 11 | `0xAB6820` | Wwise event hash (+0x58), filtered by team (`0x854050`) and by the local player | no audio message is known; P: only reachable through a scriptlet with a sound action (types 3 / 7 / 0x10 / 0x2D) (L, O) |

### B.2 Client UI / HUD halves (the director already sends what the tutorial needs)

| Node | Uses | Client execute | Effect | Recipe |
|---|---|---|---|---|
| `0x10000022` / `0x10000056` / `0x10000150` minimap targeting ring | 8 / 7 each, 7 / 3 | `0xAB6330` / `0xAB62D0` / `0xAB4D90` -> `0xA4F0C0` / `0xA4F060` | show / hide the minimap ring of a slot (ultimates) | the ring messages `0x209F` / `0x217F` / `0x2180` (protocol tables) for the caster's player (L) |
| `0x10000078` | 10 / 6 | `0xAB56D0` | for the locally controlled entity: `0x910830(component, flag, position)` (P: ground marker / camera centre in recall) | L |
| `0x100000B8` | 6 / 3 | `0xAB4700` -> `0xA4C1F0(iid, value, 1)` | HUD state of an entity (match rules `0x340002CF`) | L |
| `0x1000017B` / `0x10000060` / `0x10000111` / `0x10000121` / `0x10000167` / `0x100001A3` / `0x10000181` / `0x10000182` / `0x10000183` | tutorial | GM_UI calls (`0xA475C0`, `0xAB6E30`, `0xAB4750`, `0xAB4970`, `0xAB4E00`, `0xAB57A0`, `0x97D590`, `0xAB6DA0`) | tutorial HUD | done by `ics/director.py` (keep) |
| `0x1000003A` / `0x10000043` / `0x1000004D` / `0x100000CB` / `0x100000CC` / `0x10000179` / `0x1000018F` | UI flow script `0x34000000` | `0xAB4090` ... `0xAB52A0` | front-end state machine | client-only (no server role) |
| `0x1000017E` SetDestructibleState | 2 / 1 | `0x996B00` | sets properties `0x1000051E` / `0x1000051F` on the entity, then `0x58B770` | event 0x6 with those two properties on the sunstone (`0x340003F1`) (L) |
| `0x1000019D` | 4 / 2 | `0xAB61F0` -> `0xA93A60` | local-player / team-filtered UI string | L |
| `0x100000DD` DestructionRaycast | 2 / 2 | `0xAB6440` | client destruction of breakables along a box | L (cosmetic) |

### B.3 Server-only bookkeeping (client empty; nothing visible found)

`0x10000195` SkillEcho? (226 / 221, after SkillEchoMultiplier: P a Stolen Power "echo" hook; keep no-op until a
listener exists), `0x10000016` / `0x10000039` / `0x1000010A` / `0x1000011A` (match rules, done by `ics/match`),
`0x10000063` (`[0x1000018B]`), `0x10000086`, `0x100000A1` (Atomic Joker head link), `0x100000BD`, `0x100000DA`,
`0x100000E5`, `0x10000108`, `0x10000135`, `0x10000138`, `0x1000014B` (recall camera mode, client empty),
`0x10000151`, `0x1000015D`, `0x10000172` / `0x10000174` (clone setup with 0x1000010D), `0x10000186` / `0x10000189`,
`0x100000EC` (`0x9B5D80`, shop option), `0x1000019B`.

Reaction handlers (`0x1000014D` AddReactionHandler `[0x3F000003/6/9]`, `0x10000168` `[1, 0x3F000007, 0x100000ED, 3]`,
`0x1000014C` remove; 3 + 2 + 7 uses): handles only, the 0x3F records (variable block + one node chain) are not run.
They are collision / damage reactions of three missiles and one passive (`0x340005D5`), no visuals of their own
(skill-second-stages.md 6): run the 0x3F chain on the matching event (L-M, behaviour only).

StopScriptlet `0x10000102` (362 / 231): handled (signals the key's live run, plus fx `0x100003EA`); a handle that
did not come from StartScriptlet (a variable never set) stops nothing.

---------------------------------------------------------------------------------------------------------------------

## C. TOP-20 (priority order, recipes above)

1. FaceTarget as a facing lock released by ReleaseFacing `0x10000057` (194 / 198 scripts).
2. SetEnvironment `0x1000009C`: property `0x956` on the champion (scene / match lighting).
3. Attribute properties a binding reads (`0x100006FE` field 0x7DE, 143 binds): also on champions, refreshed on modifier changes (verify `0x58B320` reads raw property vs attribute first).
4. `0x10000400` (198 binds, vector3, never passed): find its client writer (`0x876F60` registration; break on the 0x8D variable reader `0x44AEC0` with id 0x10000400) and send it in 0x8D.
5. Entity props read as targets: `0x1000018D` (order target), `0x10000019` (anchor position), `0x100008BA`, `0x1000099A` - send on the objects whose scriptlets select them.
6. `0x1000010D` / `0x1000010E`: clone appearance (Arcane Harley E, `0x34000543`) and disguise world state `0x2E0004E6` (`0x340000EE`).
7. BeginFakeDeath `0x100001B9` (Grundy passive): defeat / revive scriptlets.
8. VitalsLink `0x1000009E` (Raven R): mirror vitals onto the projection.
9. SetObjectState `0x10000090` + SetPhysicsEnabled `0x100000E4` + SetUsageObject `0x10000087`: lifted / thrown props.
10. RevealToTeam `0x1000011E` with the vision model.
11. SetTargetingMode `0x10000075`: clear the champion's attack order after pick-ups / basic attacks.
12. Minimap targeting rings `0x10000022` / `0x10000056` / `0x10000150` -> `0x209F` / `0x217F` / `0x2180`.
13. SetCollisionLayer `0x10000114` in the server collision test.
14. Reaction handlers `0x1000014D` / `0x10000168`: run the 0x3F chains on their events.
15. Sub-entity (`second`) of 0x8D for action types 6 / 0x28 when a script targets a sub-entity.
16. SetDestructibleState `0x1000017E`: properties `0x1000051E` / `0x1000051F`.
17. PlaySound `0x100000BB`: find a sound scriptlet or audio message (open).
18. `0x10000078` ground marker / recall camera; `0x1000014B` recall camera mode (server-only, open).
19. SkillEcho `0x10000195` (226 uses): identify the Stolen Power / passive that listens to it.
20. Catalog: `script_nodes.tsv` `uses` / `server_status` are stale for the logged nodes (e.g. 0x10000057 listed 20 scripts, trees have 198; 0x100000A7 etc. are implemented but say "data only"): regenerate from the trees and the runtime tables.
