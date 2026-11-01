# Sweep: client property listeners

Scope: code in InfiniteCrisis.exe that reacts when an object property is created or changes. Builds on
`properties-complete.md` section 6 (126 decoded `0x58BA40` call sites), `full-entities-engine.md`,
`animation-deep-scan.md` section 3, `targeting-and-relations.md`, `fog-vision-runtime.md`. C = confirmed in code,
P = probable, O = open.

## 1. Registration mechanisms (C)

| Mechanism | Register / unregister | Callback | Used by |
|---|---|---|---|
| Entity property watcher | `0x58BA40(ent, id, watcher, notify)` / `0x58BCA0(ent, id, watcher)` | watcher vtable (`PropertyMonitorCallback`, game/shared/system/propertymonitor); `notify=1` fires once at register with the current value (so a create-time value is applied immediately) | HUD, world UI, targeting, fog, graph binder |
| Component-held properties (container 3) | `0x573B60` + component `vt+0x4C` | component | `0x100001D3`, `0x1000065C`, `0x10000B0C` |
| Change notification for descriptors with flag bit 2 | `0x575B90` | - | engine |
| Flash | `PropertySystem.RegisterForPropertyChange` -> `OnPropertyChanged/Added/Removed` | AS3 observers | name, team, XP, level, skill points, gold |
| Network writes that trigger them | `0x6`/`0x7`/`0x13B` set one (slot 14 `vt+0x50` -> `0x578DE0`), `0x86`/`0x129`/`0x13C` remove, `0xBC`/`0x13D` replace table | | |

## 2. Animation-graph variable binder (C for the mechanism)

- Binder object (ecx): `+4` = entity, `+8` = watcher sub-object, hash `+0xBC` (bucket count, sign bit = single
  bucket), `+0xC0` (count), `+0xC8` (buckets); node = `{next, property id, variable index}`.
- `0x559150`: for every key of the hash, `0x58BA40(entity, property id, this+8, notify=1)`; `0x5591E0` the matching
  unregister. So **every bound property gets a watcher, and the current value is pushed at bind time**.
- On change: vt+0x5C `0x55A830` -> `0x559F50(value)`: returns unless `[[ecx+0x30]+0x112]` (graph ready); id via
  `0x4FCE30`, index via `0x5594C0` (-1 = unbound, dropped); typed write by value kind: 6 vector3 (`0x556C60`),
  7 (`0x556CA0`), 8 / 9 / 0x10 raw 32-bit into `[[graph+0xA8]+8][index]`, 0x12 position (`0x557630`), 0x16 bool
  (byte, sign-extended); then `vt+0xB0` (update request).
- Other users of the map `0x5594C0`: `0x58F340` (raw f32 set, spawn callers `0xA88532/0xA88674/0xA8868E`),
  `0x6770D0` / `0x677150` / `0x6771D0` (scriptlet actions that set a graph variable by property id).

### 2.1 Where the map comes from (C)

- The binder's data is the **0x1C "object behaviour graph" record** (db-types.md: size 0xE0, vtable `0x15B50B8`,
  load `0x9D8340 -> 0x55D8E0`). `0x55D8E0` reads, in order: two headers (`0x53D570`), `0x4E4530`, `0x4F5B50`, hash
  `+0x94` and hash `+0xA8` (`0x440620`, u32 -> u32: the graph event maps), hash **`+0xBC`** (`0x55C980` ->
  `0x55C130`: u8 size class <= 0x16, count, then count x {u32 property id, u32 variable index}), then three asset
  references (`+0x5C/+0x64/+0x6C`), `+0x80`, `+0xD0`.
- In the packs the `+0xBC` hash is the last thing before the record's Havok packfile (`u32 count`, pairs, 8 bytes,
  magic `57E0E057 10C0C010`). The variable index is an index into the graph's
  `hkbBehaviorGraphStringData.variableNames` (field +32), so the names confirm every pair.
- Offline scan (all packs that hold 0x1C records, 163 graphs, 163 maps, every count matched, no conflicts):

| property | graph variable | graphs | descriptor (properties-complete.tsv) | who sets it |
|---|---|---|---|---|
| `0x00000300` | Property_Slider_Propel | 128 | f32, min -1 max 1, net 0 (local) | client (P: locomotion speed from movement; the "Propel >= 1" cosmetic early-out) |
| `0x000001F1` | Property_Slider_Turn | 128 | f32, net 0 | client (P: turn rate) |
| `0x100001BF` | Property_BehaviorParams_TargetHeading | 120 | f32, net 0 | scripts (SetGraphVariable node `0x1000002F`) |
| `0x100006FE` | Property_Attribute_AttackSpeed | 111 | f32, **net 1 NetSharedVisually** | **server** |
| `0x10000936` | Property_BehaviorParams_AnimationSpeedMultiplier | 83 | f32, default 1, net 0 | scripts |
| `0x100003B0` | Property_BehaviorParams_TurnSpeed | 76 | f32, net 0 | scripts / client |
| `0x1000044E` | Property_BehaviorParams_ToggleFidget | 74 | f32, default 1, net 0 | scripts |
| `0x100001E7` | Property_BehaviorParams_UsToTargetHeading | 24 | f32, net 0 | scripts |
| `0x1000047B` | Property_Vital_CaptureBuffer_Percent | 14 | f32, net 0 (also HUD listener `0xAA43A0`) | client (capture point) |
| `0x1000082F` | Property_BehaviorParams_EntranceAnimationMultiplier | 4 | f32, net 0 | scripts |
| `0x10000AC3` | Property_BehaviorParams_DistanceToTarget | 3 | f32, default 5, net 0 | scripts |
| `0x100008D5/D7/D8`, `0x1000093F`, `0x10000944/45` | Property_VisualProgression_Driven_Value / Timed_Duration / Timed_CurrentTime / Timed_Shrinking / Radius_Outer / Radius_Inner | 1 each | f32, net 0 | client visual-progression component (P) |
| `0x100003C3` | Property_BehaviorParam_CinematicTwistAngle | 1 | f32, net 0 | cinematic |
| `0x100007EF` | Property_BehaviorParams_ClipOffset | 1 | f32, net 0 | scripts |
| `0x10000C3B` | Property_BehaviorVariable_IsDeadlyCatch | 1 | bool, net 0 | scripts |

Consequence for ics: only **AttackSpeed `0x100006FE`** is a network property among the graph inputs; ics sends it on
the champion through `stat_properties` (when the stats record has it) but **not on match units** (minions / jungle /
structures with a graph that binds it: 111 graphs). The rest are client-local; the server reaches them only through
the scripts the client runs (SetGraphVariable) or, for Propel / Turn, through the movement it replicates. The
`notify=1` registration means a value present in the creation bundle is pushed into the graph as soon as the graph
binds, so AttackSpeed can go in the create bundle (no change trick needed).

## 3. Listener table (from properties-complete.md 6.1, plus ics status)

"ics" = the id appears in `ics/` (grep, may be a reference only). S = server-authoritative network mode.

| id | object | client reaction (listener fns) | ics | priority |
|---|---|---|---|---|
| 0x100000FA LifeState | every unit | 18 UI fns: nameplate, target loss (0x968DA0), HUD, death camera, may-act | yes (create + change) | done |
| 0x1000009C PVP_Team | every unit, player | team colour scriptlet (0xA4B150), minimap (0xA5A7E0), unit comp 0x977490 (relations), Flash | yes | done |
| 0x10000B2D cannot-act | champions | 9 fns: clear queued cast 0x85EC10, HUD dim, order refusal | yes | done |
| 0x1000019D PerceivedType | every unit | unit comp +0xA4 (targeting mask, fog type), 0xAAA5C0 | yes (late change) | done |
| 0x10000133 vision radius | units, structures | unit comp +0x8C (only on change) | yes (0 then value) | done |
| 0x10000167 Level / 0x10000142 XP / 0x100001AF SkillPoints / 0x1000035E gold / 0x10000CD6 items | champion | XP bar, rank buttons (0xA824E0, 0xA8C770), shop, Flash | yes | done |
| 0x100003F3 Stunned | champions | 0x85EA30: drop queued cast, buffer orders | yes | done |
| 0x1000011E / 0x100003A7 | target | 0x968DA0 / 0x9678C0 target frame watchers | 11E yes, 3A7 no | medium |
| 0x10000715 (iid) / 0x100005E4 move speed | units | unit comp 0x977490 (owner link), motion cap | 5E4 yes, 715 no | medium |
| 0x100004FF / 0x10000548 / 0x100006B6 / 0x100006BC-BD / 0x1000072C / 0x10000083 | units the HUD shows | 0xA4B150 (nameplate / minimap icon class), 0x96E4E0, 0xAA42A0 | 4FF, 083 only | medium |
| 0x100002B7 (cont 8) / 0x10000556 (net 3) / 0x1000065C (component) | units | 0xA5A7E0 minimap / environment state (`_CEntitySystem_EnvironmentStateChange`) | no | low-medium |
| 0x100001D3 encounter DID (component) | player | map manager (0xA0CBC0, 0xA5AAA0, 0xA85BF0): needs a CHANGE | yes (late) | done |
| 0x10000B0C (component) / 0x100000AF slot array | player | skill slots (0xA824E0, 0xA5DF80..) | AF yes, B0C no | medium |
| 0x10000456 / 0x100007C7 / 0x1000047B / 0x100006BC-BD | capture points | 0xAA43A0 capture UI, graph var | 456 only | GH mode |
| 0x10000459 / 0x10000A23 / 0x10000C13 / 0x10000C85 / 0x10000D0A / 0x10000587 / 0x100004DA | champion | HUD flags (0x96C6B0, 0xA0EB20, 0xA174F0, 0xA8C770, 0xA5B190) | 459, A23, 4DA only | low-medium |
| 0x100004E2 / 0x100008C9 | pings / markers | 0x8531B0 | no | low |
| 0x100000CF / 0x10000064 / 0x100005E8 | player <-> agent | 0x8764C0, 0xA256F0 (controlled agent, local bool 0x100000CE via 0xAA6270) | yes | done |
| 0x1000065D / 0x10000554 | env entities | 0xA813F0 -> 0xA7AFA0 run 0x10000413 | no | low |

## 4. TOP-20 properties for ics (value, when, create vs change)

Already right (keep): 1 `0x100000FA` LifeState 4/2, create + every change. 2 `0x1000009C` team, create (+ change on
team swap). 3 `0x1000019D` PerceivedType, late change (0 then value). 4 `0x10000133` vision, change (0 then value).
5 `0x10000B2D` cannot-act, change on stun/root/death. 6 `0x100003F3` stunned, change. 7 `0x10000167`/`0x10000142`/
`0x100001AF` level / XP / skill points, create + change. 8 `0x1000035E`/`0x10000CD6` gold / item count, change.
9 `0x100005E4` move speed, create (motion cap). 10 `0x100001D3` encounter DID, late change.

To add / fix:
11. **`0x100006FE` AttackSpeed (f32, net 1)** on every unit whose 0x1C graph binds it (111 graphs; minions, jungle,
    turrets as well as champions): create with the unit's attack-speed stat (1.0 default), change when items / buffs
    change it. Drives basic-attack clip speed (`Property_Attribute_AttackSpeed`). Confidence C (map), P (effect).
12. `0x10000715` (iid, net 1) owner / controller link read by the unit component `0x977490`: create (P: pets, summons).
13. `0x100003A7` (f32, net 3) target-frame watcher `0x968DA0` / `0x9678C0`: change (P: capture / bar value).
14. `0x10000548` (enum 0x300001D0) + `0x100004FF` (enum 0x30000153): nameplate / minimap class `0xA4B150`; create.
15. `0x100006B6` (int), `0x1000072C` (bool), `0x100006BC/BD` (bool): HUD nameplate bits `0xA4B150` / `0xAA43A0`; create.
16. `0x100002B7` (enum 0x300001EC, container 8) and `0x10000556` (enum, net 3): minimap `0xA5A7E0`; create.
17. `0x10000B0C` (component array, net 8): skill slot list `0xA824E0`; create on the champion, change on slot swap.
18. `0x10000C85` / `0x10000C13` / `0x10000D0A` (bool, net 1): HUD flags (`0xA8C770` shop, `0xA0EB20`, `0xA5B190`); create.
19. `0x100007C7` / `0x10000456` / `0x100006BC-BD`: capture-point UI `0xAA43A0` (GH); change as the capture moves.
20. `0x100004E2` / `0x100008C9`: ping / marker `0x8531B0`; on ping.

Never send: the net-0 graph variables (Propel `0x300`, Turn `0x1F1`, TargetHeading, AnimationSpeedMultiplier, ...):
they are local; container-7 (computed) ids.

## 5. Probes (diag.py, rva = VA - 0x400000)

- `0x159150` binder registration: `[ecx+4]` entity; walk `[ecx+0xC8]` for the bound ids (equals the table above).
- `0x159F87` (after `0x5594C0`): `esi` variable index; with `0x159F7F` `eax` property id: live check that the server's
  `0x100006FE` reaches the graph.

## 6. Open

- O: what the meanings of 0x100004FF / 0x10000548 / 0x100006B6 / 0x1000072C / 0x10000715 are (enum tables given).
- O: whether the client refuses a network write of a net-0 property (`0x578DE0` mode check not read here).
- P: Propel / Turn are written by the movement component each tick (writer not located; candidates: callers of
  `0x58F340` `0xA88532/0xA88674/0xA8868E` at spawn).
