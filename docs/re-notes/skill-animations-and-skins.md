# Skill animations, VFX and skins for every champion variant

Static analysis of `InfiniteCrisis.exe` (image base 0x400000, addresses are VA) and reads of the player's packs
with `ics.rp` / `ics.gamedata`, 2026-10-23. Trigger: tester report 2026-10-23, champions other than Gaslight Batman
(e.g. Atomic Green Lantern `0x4000047D`, costume `0x4000080C`) show skill animations / VFX and skins only in part.
Confidence: **C** = read in code or data, **P** = probable, **O** = open. Helper scripts live in the session
scratchpad (not in the repo).

## 1. What the client loads for a match's champions (C)

`0x20AF` handler **`0xA99F00`** copies the **champion DID list** to `[0x1B763C0]+0xA4` (count `+0xAC`) and the
**pack list** to `+0xB4` (count `+0xBC`), the encounter to `+0xC4` (instructions at `0xA99F25` / `0xA99F34`).
Then, from `0xA99E20`:

1. **`0xA99370` `gmConnectionManager::LoadParentRPs`**: for every champion DID of the list, `0x866480(variant)`
   on the champion-metadata hash `[0xA12D50()+0x64]` returns **value[1] = the parent pack** of the `0x20ED` metadata
   entry; the packs are de-duplicated and queued (`0xA09E50`, done callback `0xA99EF0`). The client loads every
   listed champion's **parent pack by itself**, whatever the pack list says.
2. **`0xA99460` `gmConnectionManager::LoadMatchData_`**: for every champion DID, `0x866420(variant)` returns
   **value[0]** of the same entry; then the server's pack list (`+0xB4`) is appended **after** them, and the whole
   list goes to `0xA09F90`.

The hash: node = `{next, key = variant, value...}` with the value at node+8 (`0x876750`: key read into `node+4`,
then `lea ecx,[esi+8]; call 0x866240` reads the value). The value is the 8 u32 after the variant in each `0x20ED`
metadata entry (`0x866240`: 8 x u32, u8, u32). Getters: `0x866420` -> value[0], `0x866480` -> value[1],
`0x866540` -> value[2], `0x8664E0` -> value[3]. The `0x20ED` reader is `0xA833D0` (same object `[mgr+0x64]`).

`ics/messages._meta_entry` (and the old server) sends **value[0] = 0xFFFFFFFF**, value[1] = parent pack, value[2] =
heavy (model) pack, value[3] = light pack. So LoadMatchData_ looks up `0xFFFFFFFF` for every champion (C for the
read; what the original server put in value[0] is O: the only champion-related pack categories in the install are
4 skills, 5 wallpaper, 6 light, 7 heavy, 8 parent, all already in the entry; P: value[0] = the in-match model pack,
i.e. the heavy pack, which `ics` instead names in the 0x20AF pack list, so the load set is the same).

Order of loading, therefore: (1) every champion's parent pack (by the client), (2) value[0] per champion, (3) the
server's pack list in its order (ics: map packs, parent packs again (already loaded: de-duplicated by the pack
manager, P), the other champions' heavy packs, the local champion's heavy pack last).

## 2. Where a champion's scriptlets, graph and FX live (C, data)

Atomic Green Lantern, read from the packs (`0x4000047D`, costumes `0x4000080C` Shattered Light, `0x40000C1B`):

| What | Base `0x4000047D` | Costume `0x4000080C` | Pack |
|---|---|---|---|
| entity / template | `0x4000047D` / `0x4900047D` | `0x4000080C` / `0x4900080C` | own heavy pack (`0xA0000151` / `0xA000021B`) |
| template 0x7D2 | `0x1D0000E2 E1 E8 EF`, `0x1D0001A1 1F6`, **`0x1D0003CE`** | identical list | E2-EF: `0xA00000DF`; 1A1 / 1F6: `0xA00000B3` (both resident); **3CE: parent pack `0xA0000150`** |
| world state | `0x2E000BB9` (.entity `0x2D0009A9`, 0xC3 `0x19000BBD`) | `0x2E000EBD` (.entity `0x2D000C47`) | own heavy pack |
| world-state 0x7D2 | `0x1D0003CF`, `0x1D0003D0`, `0x1D0005FC` | `0x1D0003CF`, `0x1D0003D0`, `0x1D0005FB` | CF / D0: parent pack; 5FC / 5FB: own heavy pack (idle aura: `Vfx_Active_State1` with particle `0x18000841` / `0x1800124B`) |
| animation graph 0x5B5 | `0x1C000077` | `0x1C000077` (same) | parent pack `0xA0000150` |
| Havok ragdoll `0x3600002C` | yes | yes | in every variant's heavy pack, **byte-identical** (see 2.2) |

Heavy (model) packs are small: `0xA0000151` = 21 records (one 0x40 / 0x49 / 0x2E / 0x2D / 0x1D / 0x36 / 0x18, meshes,
textures). The parent pack `0xA0000150` holds the champion's behaviour: 73 animation packfiles (0x1A), 4 graphs (0x1C),
50 particle systems (0x18), 17 scriptlet tables (0x1D), 15 FX scriptlets (0x1E), 12 skill / status scripts (0x34),
12 status records (0x48), 5 missile / spawn entities (0x40 / 0x49 / 0x2E). The skills pack `0xA0000287` (category 4)
only has 8 icons, a `0x2B` and 4 `0x48` records (the kit / tooltips); the light pack `0xA000014F` (category 6) has
the portrait textures and the pregame record. So **animations and VFX of every variant come from the parent pack**;
neither the light nor the skills pack carries anything a skill needs in the match (C, header lists).

`0x1D0003CE` (6 bases `0x1D0003CD 3D1 3D3 3D6 3D7 3D9`, 7 keys incl. `Combat_Basic_Attack 0x10000128`) is what
makes the skill VFX keys reachable: `Vfx_Atm_Glt_Grab_Start/Active/Stop 0x10000899/89A/890` (in `0x1D0003D3`),
`Vfx_Atm_Glt_Smash_Active 0x100008AB` (`0x1D0003D9`), `Vfx_Atm_Glt_Meltdown 0x10000894` + `_Shard 0x10000AA4`
(`0x1D0003D6`), `Vfx_Atm_Glt_Rads_Start/Active/Stop` (`0x1D0003CF`). The costume uses exactly the same tables, so a
costume needs the base champion's **parent pack** (which the client loads by itself, section 1) and not the base
variant's heavy pack.

### 2.1 Key resolution in the client (C)

* Table set: `0x58EDD0(object, out)` reads property **0x7D2** through `0x58B320` (the object's property table,
  descriptor container 4 = `[ent+0x38]`, flags NetSharedVisually, net 1; properties-complete.tsv). The array
  elements (`0x462` = table DID) are resolved as DB objects and pushed; called only from `0x57A8E0`. The keys of every
  champion's graph-event scriptlet `0x100001E3` sit only in the template's list (`0x1D0000E2`), and that works for
  Gaslight Batman, so the template list is (at least) in the set (P for the world state's list being merged too).
* Lookup `0x5235C0(tableset, key, mask)`: for each table, its key hash (`table+0x24/+0x28/+0x30`), then **its base
  tables recursively** (`table+0x4C`, count `+0x54`, via `0x522E40`); the entry's property `0x211` (default 2) & mask
  must be non-zero. No other fallback: no costume -> base lookup, no global table. A table whose record is not
  loaded is simply absent (the DB object is not there); a missing key returns `0x80070057` and the 0x8D entry is
  dropped silently (client-scriptlets-graphs.md 1.2).
* Definition `0x525690`: the action lists of the key from **every** table that has it are merged.

### 2.2 The DID collision `0x36000009` / `0x3600002C` (C)

Prefix `0x36` = DB type 3, Havok packfile, class at `0x556F90`, Unpack `0x557030` (db-types.md): here an
`hkaRagdollInstance` / `hkpRigidBody` packfile (the champion's ragdoll). Its Havok header gives its true size
(first u32 0x3DCC for `0x36000009`, 0x42FC for `0x3600002C`); bounded by it, the record is **byte-identical** in
every pack that has it (`0x36000009`: `0xA0000076`, `0xA000010C`, `0xA0000183`, `0xA00002F3`, md5 97188be053;
`0x3600002C`: `0xA0000151`, `0xA000021B`, `0xA0000312`, md5 8251805a3f). The "68 KB vs 46 KB" sizes in the
2026-10-23 16:20 note measured up to the next *placed* record and so included the unplaced records that follow
(textures / tables); they are not different contents. Which copy wins does not matter for these DIDs.

### 2.3 Dependencies of the model and parent packs (C, heuristic scan)

`deps.py` / `deps_parent.py` (scratchpad) scanned the structured records (0x2D / 0x2E / 0x49 / 0x40 / 0x16 / 0x17 /
0x19 / 0x37, plus 0x18 / 0x1E in parent packs) for DIDs of record kinds a model or effect references (0x13 0x16 0x17
0x18 0x19 0x1A 0x1C 0x1D 0x1E 0x2D 0x2E 0x36 0x37) that no loaded pack provides, with loaded = resident packs +
Crime Alley's map list + the variant's heavy pack + its champion's parent pack (+ its light / wallpaper pack):

* 156 / 156 variants: the only outside references are the portrait / wallpaper textures of the template (tex384,
  tex799, wallpaper: light and wallpaper packs, UI only); 10 variants show one stray word each (noise).
* 54 / 54 parent packs: no outside reference except single stray words in 9.

So a skin needs exactly **its heavy pack + its champion's parent pack**; no other variant's pack, no light or skills
pack, no other champion's pack.

## 3. How a skill's animation and VFX are triggered

### 3.1 What the client plays by itself (C unless marked)

* **Locomotion, idle, death pose, get-up, stuns**: the animation graph `0x5B5` (Havok behaviour graph, record 0x1C)
  runs by itself from movement and properties; the data-authored containers (action type 0x22) of
  `_Combat_GoToLocomotion`, `CbtState_KnockUp`, `CbtState_GetUp` watch LifeState `0x100000FA`, `0x10000B2D` and
  `0x100003F3` (client-scriptlets-graphs.md 1.5). These still need their scriptlet started (they are scriptlets).
* **Nothing from the skill record**: the client never casts on its own (`0x20EE` is the only C->S message;
  full-combat-skills.md 1.1); there is no "skill used" animation in the skill record path.
* **Client copies of 0x34 scripts**: the `gmHFSMComponent` at `entity+0x8C` runs script instances that the server
  creates with `0x200F` / `0x200C` (status scripts today). Inside such a copy the nodes that send visuals have a
  client half (vtable slot 10):

| Node | Client execute | What it does on the client |
|---|---|---|
| `0x10000034` RunScriptlet | `0x9CE2E0` | `0x9CE050(block)`: resolves the entity, builds the variable table from the node's variable list (`0x9CDDE0`), originator = local player (`0x635230`), flags `0x12` (+4), optional sub-entity, runs the key through the **local** path (vfunc +0x34) |
| `0x10000103` StartScriptlet | `0x9CE300` | evaluates its fx operand and sets **variable `0x1000050A`** to it (`0x4C07F0(0x1000050A, ...)`), then `0x9CE050` |
| `0x1000013A` RunFxScriptlet | `0xAB7620` | variable **`0x1000050A` = node+0x54** (its 0x1E fx record), then `0x9CE050` |
| `0x1000004E` RaiseGraphEvent | `0x9CE1C0` | scriptlet `0x100001E3` with `0x780` = event (local path) |
| `0x1000007A` TargetHit | **`0xAB4D80` (empty)** | nothing: server-only, so a server must send its hit scriptlet itself |

  Because the client copy sends its own runs with originator = local player, a server 0x8D carrying that originator
  is dropped by `0x6279D0` (no double play). `0x20C9` raises the "skill used" event `0x1000001D` etc. on the client
  copy of the slot's script (`0xA16E60` -> `0x96DED0`); this message exists only to drive such copies, so the
  original server most probably **replicated each champion's skill scripts to the client** and let the copies play
  RunScriptlet / StartScriptlet / RunFx / RaiseGraphEvent with their full variables (P). `ics` does not replicate
  skill instances, so every visual must come from 0x8D (3.2).

### 3.2 What needs server messages (C)

* `0x8D` scriptlet key + **its variables** (`ics/messages.start_scriptlets`), looked up in the entity's tables
  (2.1). Each action field bound to a variable whose descriptor container is 6 ("data only") reads the 0x8D variable
  table; a missing variable leaves the field at its literal (usually 0) and the action does nothing or plays at the
  wrong place (client-scriptlets-graphs.md 1.4).
* Graph events: `0x100001E3` + `0x780` (in `0x1D0000E2`, a template table of every champion).
* `0x20C9` (script events to client copies), `0x20F0` attribute modifiers (the client half applies them),
  `0x200F` / `0x200C` (client copies of status scripts: auras / buff FX run there).

**Variables the scripts pass (all 875 decoded scripts, `varscan.py`):** 316 RunScriptlet / StartScriptlet / RunFx
nodes pass a variable list, to **124 distinct keys**: `0x10000030` target IID (242 nodes), `0x100009EB` speed (88),
`0x1000049D` (61), `0x100003FF` (32), `0x10000050` (15), `0x1000033E` (14), `0x1000050A` fx (10), `0x100002F8` (8),
`0x100007A8` (4), others 1-2. And **642 nodes name a 0x1E fx record** that reaches the client only as variable
`0x1000050A`: 445 TargetHit (values[5] = normal hit fx, values[6] = critical, e.g. Atomic GL basic attack
`0x1E000258` / `0x1E000259`), 138 StartScriptlet, 59 RunFx.

The receiving end, read from the tables (`entry.py`): `VFX_CBT_Hit_Shared 0x10000223` (`0x1D0002A7`, pack
`0xA00000B3`) = props `{0x479 = 100, 0x7E6 = 1}` and one action **type 0x18 with field `0x617` bound to variable
`0x1000050A`** (0x617 and 0x1000050A are both DID kind 0x15, DB type 0x15 = the 0x1E records; 0x1000050A container
6 = scriptlet variable). `_Combat_GoToLocomotion 0x100002FD` also has a type 0x18 action on `0x1000050A`.
`0x100001E3` binds field 0x97 to `0x780`.

What `ics` sends today (`ics/world.py CastWorld.run_scriptlet`, `ics/script_runtime.py`): variables only for the 7
keys of `[ics] shot_scriptlet_variables` (`scriptlet_variables = false` since 2026-10-21); `_hit_effect` sends
TargetHit's key with no variable; `_start_scriptlet` sends `values[0]` with no variable (the fx and the variable list
are dropped); `_run_fx_scriptlet` builds `0x1000050A` but `0x100003EA` is not whitelisted, so it is dropped. Gaslight
Batman looks right because his shot keys (`0x10000188 / 89 / 17E`) are in the whitelist; other champions' shot
and FX keys are not.

## 4. Per-variant sweep: keys the skill scripts send vs the tables the client has

Script `coverage.py` (scratchpad; helpers `tables.py`, `entry.py`, `nodes.py`, `where.py`). For each of the 156
variants: the kit's scripts from `skills.tsv`, plus every status script (`0x48` value -> `0x10000242`) and missile /
spawn script (`0x40` class of LaunchMissile / LaunchLobbedMissile / LaunchTetheredMissile / SpawnEntity -> its
`0x8E` list) they reach; every RunScriptlet / StartScriptlet / RunFx / TargetHit node (key = values[0]; RunFx
without a key = `0x100003EA`) and RaiseGraphEvent node. A key sent to SELF from a skill script is resolved in the
champion's tables (template 0x7D2 first, then the world state's 0x7D2, bases recursively); a missile's own keys in
the missile class's tables; keys sent to another entity / from status scripts are counted as "on target". Loaded
packs = resident (`[ics] resident_packs`) + Crime Alley's map list + the variant's heavy pack + its parent pack.
Table bodies are read with `ics.rp`'s anchor but with two fixes (below).

Totals over 156 variants (780 + status / missile scripts):

| Result | Nodes |
|---|---|
| key in a template table (or its bases) | 2598 |
| key only in a world-state table | 148 (56 distinct keys, e.g. AGL passive `Vfx_Atm_Glt_Rads_Start/Active/Stop` in `0x1D0003CF`; Green Arrow `Vfx_Gar_*_Empowered_Active`; Batman `Vfx_Bat_Cape_Sweep_Active`) |
| missile key resolved / not | 439 / 93 |
| sent to another entity or from a status script | 2403 |
| not resolved | 254 (109 distinct) |
| nodes naming a 0x1E fx record (needs variable `0x1000050A`) | 1658 |
| graph events not present in the parent / heavy pack | 0 (every RaiseGraphEvent id appears in the champion's packs) |
| **tables of a variant's chain that are in no loaded pack** | **0 / 156 variants** |

The 254 unresolved come from tables the heuristic reader cannot cut (14 champions: Superman 16, Deathstroke 18,
Raven 17, Hawkgirl 7, Deadshot 5, ...: their chains hold unparsed tables such as `0x1D000035`, `0x1D000662`,
`0x1D00086A-C`, `0x1D000723-729`; e.g. Superman's `Vfx_Sup_*` keys sit in `0x1D00050F`, a base of one of them), not
from missing data. Costumes resolve exactly like their base (94 / 102 identical counts; the other 8 differ only in
their own world-state table, the costume's idle / aura FX). Per base champion (template / ws-only / unresolved / on
target / fx nodes): AGL 10 / 3 / 0 / 24 / 19; Gaslight Batman 18 / 0 / 0 / 8 / 8; full table in `coverage.json`.

**Conclusion for the packs (C):** with the packs ics names today (map + parent packs + heavy packs) every scriptlet
table, graph and particle a variant's skills reference is loaded. The missing animations / VFX are not a pack
problem. The causes are in what the server sends (section 3.2): the dropped variables (124 keys), the 0x1E fx of
TargetHit / StartScriptlet / RunFx (1658 nodes), and (P) the world-state-only keys if the client reads only the
template's 0x7D2.

Reader bugs found on the way (they affect `ics.gamedata.Data.script_table` / `scriptlets`, used for props'
`scriptlet_keys` and initial scriptlets, not the champion's 0x8D):
* `ics/rp._placed_starts` places a 0x1D table at a *reference* to its DID (AGL's `0x1D0005FC` "placed" inside world
  state `0x2E000BB9`'s 0x7D2 list), so `script_tables` skips it. Table bodies never start with their DID: treat every
  0x1D record as unplaced.
* `ics/rp._table_headers` tries at most 4 base tables; `0x1D0003CE` has 6 (`0x1D0003CD 3D1 3D3 3D6 3D7 3D9`) and
  `0x1D000064` (Gaslight Batman) has 6: allow up to 16.
* `ics/gamedata.Data.record_tables` reads 0x7D2 within `max(end, start + 0x400)`; champion templates carry it at
  +0x1600..+0x1B00 (Zod +0x1618, Flash +0x183C, Huntress +0x163C, Arcane Supergirl +0x199C) and the record list ends
  earlier, so 5+ champions get no tables at all. Search 32 KB as `champion_world_state` does.

### 4.1 Heavy-pack DID sharing (C, headers)

Across the 158 heavy packs, DIDs present in more than one heavy pack belong to the **same champion** in every case but
one texture: 0x1A animations 406, 0x18 particles 83, 0x36 ragdolls 45, 0x13 textures 42, 0x1D tables 26, 0x2E 13,
0x19 14, 0x1C graphs 8, 0x40 / 0x49 8 (e.g. Superman `0xA0000075` and his costume packs `0xA0000212 / 27B / 2BB`
share 0x1A / 0x1C / 0x1D / 0x2E records: older champions keep their behaviour in the heavy pack and each costume pack
carries a copy). Only one variant of a champion is loaded per match when `bots_avoid_my_champion` holds, so the
"last loaded wins" rule matters only if two variants of one champion are loaded (bot + player, or a lobby preview
pack still resident). The 0x36 copies are byte-identical (2.2); whether the shared 0x13 textures differ is O.

## 5. Server changes, ranked by confidence

1. **Send each scriptlet's variables (C).** `CastWorld.run_scriptlet` drops the variable table unless the key is in
   `[ics] shot_scriptlet_variables` (7 keys). The scripts pass variables to 124 keys (`0x10000030` target IID,
   `0x100009EB` speed, `0x1000049D`, `0x100003FF`, `0x10000050`, `0x1000033E`, `0x1000050A`, `0x100002F8`, ...), and
   the tables bind them (container-6 variables). Either `scriptlet_variables = true` (typed by kind, as fase3-hc does
   for the shots; the 2026-10-21 regression predates the typed encoding) or derive the whitelist from the data: every
   key whose table entry has a binding to a container-6 variable (`entry.py` logic). Expected: other champions' shots
   home and their basic-attack / skill FX play at the target like Gaslight Batman's.
2. **TargetHit fx (C).** `0x1000007A` has no client half (`0xAB4D80`). `_hit_effect` must send
   `VFX_CBT_Hit_Shared 0x10000223` (values[0]) on the target with variable **`0x1000050A` = values[5]** (normal) or
   **values[6]** (critical, when operand 2 CriticalChanceRoll is true; fall back to values[5] when 0), kind DID; put
   0x10000223 in the variable whitelist. 445 nodes in all champions (AGL basic `0x1E000258 / 259`, W `0x1E0002A7`,
   E `0x1E000263`). Expected: hit sparks / impact FX on every target.
3. **StartScriptlet and RunFx fx (C).** Client halves `0x9CE300` / `0xAB7620` set `0x1000050A` to the node's fx (the
   last 0x1E value) and pass the nested block's variable list. `_start_scriptlet` should send values[0] with the
   block's variables (values[1] = count, values[2..] = ids, operands 2.. = values) plus `0x1000050A` = the 0x1E value;
   `_run_fx_scriptlet` already builds them but `0x100003EA _ExecuteScriptlet` must be whitelisted. 138 + 59 nodes.
   Expected: the persistent skill FX (auras, channel effects, AGL-style `_Active` loops started through
   StartScriptlet) appear.
4. **Champion 0x7D2 = template list + world-state list (P).** 56 keys (148 nodes) resolve only through the world
   state's tables (AGL passive Radiation Sickness, Green Arrow empowered shots, Blue Beetle forms, Nightwing). 0x7D2 is
   an instance property (container 4, net 1): send it on the champion's create with both lists, as props get theirs.
   Expected: those auras play if the client reads only the template's list; harmless otherwise. Test first with AGL's
   passive (diag break on `0x6279D0` return: `0x80070057` = key not found).
5. **ics readers (C, server side only):** treat 0x1D records as unplaced in `rp.script_tables`, allow 16 bases in
   `_table_headers`, read 0x7D2 32 KB into templates in `Data.record_tables`. Expected: correct `scriptlet_keys` for
   props and any key filtering; no client effect.
6. **Packs (C):** keep naming the parent pack and the heavy pack; the light and skills packs are not needed in a
   match; the base variant's heavy pack must not be named for a costume (no dependency, 2.3). `local_champion_pack_last`
   only matters when two variants of one champion are loaded; the 0x36 collision is harmless (identical bytes).
7. **0x20ED value[0] (O/P):** LoadMatchData_ loads value[0] per listed champion; ics sends 0xFFFFFFFF. Putting the
   heavy pack there would let the client load each champion's model pack itself (as it does the parent pack); test
   only if a champion's model is ever missing in a lobby match.
8. **Long term (P):** replicate each champion's skill scripts to the client (0x200F / 0x200C) and drive them with
   0x20C9; the client copies then play RunScriptlet / StartScriptlet / RunFx / RaiseGraphEvent with their own
   variables (originator = local player, so no duplicate with the server's 0x8D), which is most probably what the
   original server did.

Catalog follow-ups (when implemented): `scriptlets.tsv` rows `0x10000223` (needs 0x1000050A), `0x100003EA`;
`properties.tsv` `0x1000050A` (scriptlet variable: 0x1E fx record), `0x617` (action field: fx record); exe addresses
`0xA99370`, `0xA99460`, `0x866420`, `0x866480`, `0x876750`, `0x58EDD0`, `0x9CE050`, `0x9CE300`, `0xAB7620`.
