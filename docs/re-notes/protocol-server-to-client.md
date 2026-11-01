# Server → client protocol map (static analysis, 2026-10-21)

Complete list of what the client (`InfiniteCrisis.exe`, image base 0x400000, all addresses are **VAs**) can
receive from the server: every registered network event (336) and every notice that can arrive inside event
`0x2` (44). Static analysis only (Ghidra via REA + capstone/unicorn scripts on the exe); nothing here was checked
against a running client unless the "used" column says the server already sends it.

## 1. How the client dispatches server messages

- **Event registry.** `0xb0ec50(event_id, factory)` fills a hash map event id → factory. There are exactly 336
  calls (static initialisers grouped per system, e.g. `0x8c3940` registers the dialog events 0x2143, 0x2142, 0x2039,
  0x2047, 0x2001, 0x202A). Only *receivable* events are registered: client→server ids (0x20EE, 0x20D5, 0x12D, …)
  are absent.
- **Factory → event object.** Each factory allocates the event object and constructs it (base vtable `0x15a7da0`,
  `[obj+8]` = event id, `[obj+0xc]` = 0x300400). The final vtable gives two important slots:
  - slot 1 (`vt+4`) = **exec**: `QueryInterface` of the destination object for an interface GUID, then a direct
    call into the owning system (the "handler" column). Ghidra shows most exec bodies as "return E_NOINTERFACE"
    because it removes the QI branch; read them as assembly.
  - slot 7 (`vt+0x1c`) = **serializer** (one function for read and write; stream `[s+4]&1` = writing).
- **Body reader.** Every serializer first calls `0xb0d380`, which reads the **u8 base byte** (`u8 0` in the
  layouts) unless the stream has flag 0x800 (packed: batch sub-events and notice blobs). Fields are read with
  `0xafae80(n)` (reserve n bytes, `0xafa7a0`), compact ints with `0x421430`, `wstr` = compact length + UTF-16
  (`0x4215d0`), StringInfo `0x5a9580`, Position `0x47c610`, property value `0x509740`, property table `0x509950`,
  lists `0x4e4530` (u32 n + n×u32), `0x5bce30` (u32 n + n×u64). A list reader checks `n <= stream end - pos`.
- **Destinations (interface GUIDs used by exec):**

| tag | GUID (rdata) | events | meaning |
|---|---|---|---|
| OBJ | `ca62fa10-72fe-4c9f-a7d3-a3178af34d09` (0x15a7a70) | 177 | generic game object: the local player `0x0200000000000001`, agents, props. Handlers then use object components (`obj+0x10` scriptlets, `+0x38` properties, `+0x58` appearance, `+0x60` listeners, `+0x84`, `+0x8C` effects, `+0x90` floaties, `+0x9C` usage bars, `+0xA4` upgrades, `+0xBC`, `+0xC0` status icons) or the client root `0xa12d50()` members (`+0x1C` dialog, `+0x24`, `+0x38`, `+0x5C`, `+0x68` encounter UI, `+0x90`, `+0xA4` map notes) |
| PSYS | `b14973cd-a40b-4169-b58b-b4acd0016242` (0x15ee5b4) | 125 | player system `0x0600000000000403` |
| SESSION | `37feb363-…` (0x15d1254) | 9 | session/account object (0xCE, 0xEB, text messages) |
| REGION | `79d30b39-…` (0x15d1364) | 6 | position-qualified property events (0x81, 0x96, 0xC4, 0xD7, 0x104, 0x110) |
| TWO | `6d8bb31c-…` (0x15aa4a4) | 3 | TypedWorldObject (0xB2, 0xD1, 0xEE) |
| service | none | ~14 | exec looks a service up by GUID itself (`0xafde60`), e.g. world-object service `0x15bab54` |

- **Notices (event 0x2).** `0x483240(notice_id, &descriptor)` registers 464 notice ids (ids read from `.data`
  globals). A descriptor is two function pointers: `[0]` = *network reader + deliver* (`reader(target, stream)`:
  reads the blob with stream flag 0x800, then calls the notice's deliver function, which forwards it to the
  object's notice listeners / Flash `GM_*.RecvNotice_*`), `[1]` = *build from script/Flash arguments*. Event 0x2's
  exec (`0x482160`) looks the id up (`0x482090`), QIs the destination (or uses no target when the destination is the
  player system 0x…403) and calls `[0]`. **Only 44 descriptors have a real reader**; the other 420 have the stub
  `0x11893c0` ("return false"), so sending them over the network does nothing (they are local C++/Flash notices).

## 2. Highlights for the requested areas

### Environment effects (meteors, lightning, weather, `CEncounterEnvironmentSystem`)
- No string for meteor/lightning/weather exists in the exe. `CEncounterEnvironmentSystem` (constructor `0xa917b0`,
  vtable `0x160542c`, per-frame update `0xa801f0`) is an **encounter cue system**, not weather:
  - `0xa59bd0(cue_type, arg)` looks the cue up in the current encounter record (`0xa47a40(encounter DID, …)`) and
    plays it in one of **6 timed slots** (0x48 bytes each; expiry at `slot+0x38`, active flag `+0x40`); `0xa782c0`
    stops a cue; `0xa8f890` (encounter start, from `0xab46ea`) resets slots and reads encounter properties
    (record property 0x29, 0x10000AD8, 0x10000003).
  - The cues are raised **client-side** by listeners on game state, not by a server event: `0xa80190` (an entity's
    life state changes; per-team counters) → `0xa78370` → cues 0x0D/0x0E/0x13/0x09; `0xa59c80` → cues
    0x0F/0x11/0x12/0x09; `0xa67ef0` (game event types 3 and 6) → cue 0x19; `0xa59d10` (every 3 s, champion in
    danger: flags 0x84810/8 and recent damage) → cues 0x1B/0x1C.
  - So the server drives environment cues indirectly: entity life state / team properties (0x4, or the single
    property events 0x6/0x7/0x86) and kill/game events. Visual hazards such as falling meteors have no dedicated
    message; they must be world objects + scriptlets (0x4 + 0x8D, or 0x2050 / 0x2056 below) or data in the
    encounter record.
- No server→client event reaches `0xa59bd0`/`0xa782c0` in a call-graph search (depth 6) from all 336 exec
  functions and the 44 notice readers.

### Object spawning, visibility, properties
- Known: 0x4 batch create, 0x3 remove, 0x8D scriptlets, 0xEB local player.
- **New: single-property updates.** 0x6/0x7/0x13B set one property (`obj+0x38` vt+0x50), 0x86/0x129/0x13C remove a
  property id (vt+0x54), 0xBC/0x13D set a property table (vt+0xA4/+0xA8). These would let the server change e.g.
  life state or team without re-creating the object. 0x20C2/0x2084 do the same for an entity named by IID in the
  body (sent to the player).
- **Appearance family** (group `0x69b0e0`): 0x8B refresh model, 0xB8 model setup (CModelComponent strings), 0xF5 part
  attribute, 0x106 reset part, 0x10D add parts, 0x115 LOD flags, 0x124 part state, 0x138 batch refresh.
- **World-object service family** keyed by `WorldRef{u64,u64,GUID}` (0x91, 0x98, 0x9E, 0xA3, 0xA5, 0xA7, 0xB1,
  0xC0, 0xC8, 0xD0, 0xE6, 0xFC, 0xFD, 0x111–0x113, 0x11A, 0x11B, 0x12C) and TypedWorldObject events 0xB2/0xD1/0xEE:
  map-placed objects addressed by GUID (no strings; meanings marked "?").
- 0xE4: per-object awareness/visibility toggle with 10 s / 20 s timers (`0x56e6a0`) – probable fog-of-war
  visibility of an entity.
- **New scriptlet entry points:** 0x2050 (`u64 object, u32 scriptlet key`, no variables) and 0x2056 (`u32 key` +
  property table of variables, on the destination object) both go to `obj+0x10 → 0x57d8b0`; 0x2073 carries an 0x8D
  scriptlet list through the local player (`0xa22da0`).

### Cinematics
- 0x20F5 play cinematic (used) and 0x2150 HUD visibility (`GM_UI.RecvNotice_UpdateHUDVisibility`) are registered
  together (`0x8c3160`).

### Objectives / mission flow / match phases
- Encounter group (`0x960fc0`): 0x2009, 0x2023 (category state/remove), 0x2034, 0x2069 (tracker status), 0x2075,
  0x201C, 0x2159/0x215A (root+0x38 lists), 0x2173 (training floaty trigger), 0x2038 match ended, 0x2045, 0x214B,
  0x213D/0x213E HUD elements. Training: 0x2171 (load control: encounter DIDs + lesson), 0x2174 (lesson event).
- Network notices with match flow: 0x10000109 `SetMatchTime` (f64, f64, u8), 0x10000076 `TimerClockSync`,
  0x100000CB/0x100000CE `UI_PlayerJoined/Left`, 0x100004FB/0x10000134 team health, 0x10000455/0x10000456
  surrender, 0x10000090/0x100000BC/0x100000BA defeat (respawn) timers, 0x1000000E match ended, timeline banners
  0x10000424/0x100002AB/0x100002AE/0x100002AC/0x100002AF/0x100002B1, announcements 0x100002EB/0x100002EC/0x100002BC,
  billboard/kill-feed style 0x1000021C/0x100002B2.

### Conversations
- Dialog group (`0x8c3940`): 0x2001 start conversation (dialog system root+0x1C vt+8), 0x2047 (vt+4, probable line
  advance), **0x2039** = play a context dialog element chosen from team/context properties (0x100003BD, 0x10000865,
  0x10000806, 0x1000081C/0x1000081D, 0x10000811/0x10000812) – the announcer path; 0x202A set speaker/voice DID,
  0x2142/0x2143 dialog queue flags.

### HUD, skill bar, combat feedback, status effects
- Skill HUD (`0x8bccd0`): 0x207B/0x2187 enable button, 0x207C slot override (5 slots), 0x208C, 0x2091 overlay,
  0x2092/0x20DC execute-skill error, 0x20A0 disable condition, 0x20F8 cooldown, 0x20F9 availability event
  (script events 0x100000B6/0x100000B7), 0x20C9, 0x209F/0x217F/0x2180 targeting ring.
- Combat feedback: 0x42 vitals (also DOT/VOT ticks), 0x44 / 0x208D / 0x20BD `DisplayFloatyStatus`, 0x43 remove
  floaty, 0x201D floaty list. Damage numbers themselves are produced client-side (Floaty system, `User.ShowFloaty*`).
- **Status effects (new):** effect component `obj+0x8C` (`0x8b6db0` group) mirrors server effect instances:
  0x200C/0x2043 apply list, 0x200F/0x2062 add one, 0x202B/0x2037 remove by GUID, 0x2019/0x206F set an effect
  variable, 0x2008/0x41/0x2158/0x2063/0x2157/0x204E/0x202C/0x204D raise script events on effects, 0x203D raise
  0x10000009 on effects flagged 0x10000007. Display: StatusIcon group (0x20A2/0x20C8 add, 0x20A8 update, 0x20E9
  remove, 0x20D0/0x2127 tooltip, 0x2123/0x2126/0x2129/0x212A component calls). Cast/channel bars: Usage group
  (0x2077, 0x2082, 0x2096, 0x20B2, 0x20BB, 0x20CE).

### Minimap
- 0x2006 add map note / 0x200E remove (handle {u32,u64}), 0x2137 remove map note, 0x20DA note list, 0x20D2 marker
  for an IID at a position, 0x2179 revealed cells (fog of war, property 0x7EC rect), 0x2189/0x218A teleport effects.

### AI / pathing, destructibles
- No server→client pathing message: Havok AI (`hkaiNavMesh…`) is client-side. Server-driven motion candidates:
  0x1 and 0x8A (position + vec3), 0x2022 (agent component `+0xBC`, vec3 + IIDs) – all "?" until traced.
- No destructible-specific event (`Render.DestructiblePriorityLevel` is a render setting); destruction must be
  scriptlets / world state + remove.

## 3. Layout notation

`u8 0` = base byte read by `0xb0d380`. Layouts were recovered by emulating each serializer in unicorn with a
recording stream (every first read of a field fed the value 1, so optional branches and one list element show;
StringInfo fed in token form). `{…}` = a sub-reader, `list<u32>` = u32 count + elements, `Handle{u32,u64}` =
reader `0x962ad0`, `WorldRef` = `0x574ff0`, `QueueKey` = `0x6b01a0` (encounter DID + queue flags). "[trace stopped
early]" = the emulation hit uninitialised client state after that point (the rest of the body is unknown).
Flag-driven readers (objectives, StringInfo variables) only show the branch selected by value 1.
"Used" = the project already sends it (`ics/`, `icserver/`, catalog `network_events.tsv`).

## 4. Network events (336)

| id | kind | system / dest | exec / serializer / handler | body layout | meaning | used |
|---|---|---|---|---|---|---|
| `0x1` | event | engine: movement/appearance / object IID (player 0x02..01 or entity) | exec `0x698090` / ser `0x445a30` / h 0x632560 | u8 0 \| Position \| vec3 \| u32 \| u32 \| u32 \| u32 \| u8 | Movement update (?): position + velocity vec3 + 4 u32 + flag (exec->0x6322f0). Probable server-driven position/heading of an entity | no |
| `0x2` | event | engine static / object IID (player 0x02..01 or entity) | exec `0x482160` / ser `0x481f20` / h 0x482090,0xaf9650 | u8 0 \| u32 notice id \| u32 len \| blob (read by the notice reader, stream flag 0x800) | Notice delivery: u32 notice id / u32 len / blob; the blob is read by the notice's own reader (see notice table). Dest 0x...403 accepted with no target object | yes |
| `0x3` | event | engine: object lifecycle / object IID (player 0x02..01 or entity) | exec `0x698a20` / ser `0xb0d380` / h - | u8 | Remove (destroy) object | yes |
| `0x4` | event | engine static / any (exec uses a service) | exec `0x5d9ff0` / ser `0x447770` / h - | u8 0 \| cint n \| n x (cint event id \| u32 len \| body without its base byte) | Batch: create/update objects (0xF2 descriptor); sub-events compact id / u32 len / body | yes |
| `0x5` | event | engine: object lifecycle / object IID (player 0x02..01 or entity) | exec `0x698d60` / ser `0x445430` / h 0x629910 | u8 0 \| {u8 {u16}} | Object listener callback (obj+0x60 listeners, vt+0x18) with u8 + u16 id (?) | no |
| `0x6` | event | engine: properties / object IID (player 0x02..01 or entity) | exec `0x699450` / ser `0x445530` / h 0x635360 | u8 0 \| PropValue (packed property id, kind, value: wire.pack_value) | Set one property on the object (property collection obj+0x38, vt+0x50) | no |
| `0x7` | event | engine: properties / object IID (player 0x02..01 or entity) | exec `0x699450` / ser `0x445530` / h 0x635360 | u8 0 \| PropValue | Set one property on the object (same handler as 0x6) | no |
| `0x8` | event | engine: movement/appearance / object IID (player 0x02..01 or entity) | exec `0x698140` / ser `0x445b60` / h 0x62c990,0x6325c0 | u8 0 \| {{{u8} GUID} u8 u64 u8 u8 Position u8 {vec3 vec3 u32}} \| u32 \| u32 \| u32 \| u32 \| u8 | Object (re)placement with world-object GUID, position, two vec3 and timing (?) | no |
| `0x41` | event | Effects (agent obj+0x8C) / object IID (player 0x02..01 or entity) | exec `0x8b6780` / ser `0x849a10` / h 0xaa1c50 | u8 0 \| u64 \| {u32} | Effects: raise a script-event list on every effect of agent u64 | no |
| `0x42` | event | Vitals / object IID (player 0x02..01 or entity) | exec `0x8c26f0` / ser `0x846fc0` / h 0xab2880 | u8 0 \| {cint {{u16} {u16}}} \| {cint {{u16} {u16}}} \| {cint {u8 u8 u8 {cint {u8 u16}}}} \| u8 | Vitals (health / secondary resource, DOT/VOT ticks) -> GM_Vitals.RecvNotice_VitalsChanged / DOTUpdate / VOTUpdate, GM_Skill.UI_NotifyVitalChange | yes |
| `0x43` | event | Floaty (obj+0x90) / object IID (player 0x02..01 or entity) | exec `0x8b26b0` / ser `0x83f5b0` / h 0xaa4ee0 | u8 0 \| Handle{u32,u64} | Floaty/combat-text component (obj+0x90): remove entry by handle {u32,u64} | no |
| `0x44` | event | Floaty (obj+0x90) / object IID (player 0x02..01 or entity) | exec `0x8b2610` / ser `0x83f530` / h 0xaaf7c0 | u8 0 \| Handle{u32,u64} \| u32 \| u32 | Floaty/combat-text (obj+0x90): display status floaty (handle, u32, u32) -> GM_Vitals.RecvNotice_DisplayFloatyStatus | no |
| `0x81` | event | engine: properties / region object (iface 79d30b39) | exec `0x698df0` / ser `0x445de0` / h - | u8 0 \| Position \| u8 \| PropTable [trace stopped early] | Region/cell-level properties at a position (iface 79d30b39) (?) | no |
| `0x82` | event | engine static / object IID (player 0x02..01 or entity) | exec `0x56e220` / ser `0x569a60` / h 0x56e040 | u8 0 | Service event, empty body (0x56e040 timer sweep) (?) | no |
| `0x83` | event | engine: misc / object IID (player 0x02..01 or entity) | exec `0x6985e0` / ser `0x839500` / h 0x603e40 | u8 0 \| u32 | Engine service call with u32 (0x603e40 -> service vt+0xd4) (?) | no |
| `0x86` | event | engine: properties / object IID (player 0x02..01 or entity) | exec `0x699210` / ser `0x839500` / h 0x6353b0 | u8 0 \| u32 | Remove one property id from the object (obj+0x38 vt+0x54) | no |
| `0x8a` | event | engine: movement/appearance / object IID (player 0x02..01 or entity) | exec `0x698350` / ser `0x445c90` / h 0x632590 | u8 0 \| Position \| u32 \| u32 \| u32 \| u32 \| u32 \| u8 | Movement update variant: position + 5 u32 + flag (exec->0x632370) (?) | no |
| `0x8b` | event | engine: movement/appearance / object IID (player 0x02..01 or entity) | exec `0x6982b0` / ser `0x839dd0` / h 0x631050 | u8 0 \| u64 | Refresh appearance/model of object u64 (obj+0x58) | no |
| `0x8c` | event | engine static / any (exec uses a service) | exec `0x588f30` / ser `0x589be0` / h - | u8 0 \| u32 | Service event u32 (exec 0x588f30, obj+0x94 component vt+0x28) (?) | no |
| `0x8d` | event | engine: object lifecycle / object IID (player 0x02..01 or entity) | exec `0x698c40` / ser `0x83c030` / h 0x634f20 | u8 0 \| ScriptletList: cint n x entry (DID, instance, flags, originator, variables) - see ics/messages.start_scriptlets | Start scriptlets on an entity (animations, VFX, sounds) | yes |
| `0x8f` | event | engine static / any (exec uses a service) | exec `0xb15a80` / ser `0xb16420` / h - | u8 0 \| {{u8} GUID} | Session/GUID-keyed engine event (exec 0xb15a80) (?) | no |
| `0x91` | event | engine static / object IID (player 0x02..01 or entity) | exec `0x59d7d0` / ser `0x59e890` / h 0x558060 | u8 0 \| WorldRef{u64,u64,GUID} \| {u32 u32 u32 u32 u32 u32} \| {{{u8} GUID}} | World-object service event: object ref {u64,u64,GUID} + 6 u32 (transform?) + ref (?) | no |
| `0x94` | event | engine: misc / object IID (player 0x02..01 or entity) | exec `0x697e50` / ser `0x839720` / h 0x60c0f0 | u8 0 \| u8 | Engine object flag u8 (obj+8 vt+0x4c) (?) | no |
| `0x96` | event | engine: properties / region object (iface 79d30b39) | exec `0x699090` / ser `0x4454e0` / h - | u8 0 \| Position \| PropValue [trace stopped early] | Region/cell property at position (iface 79d30b39) (?) | no |
| `0x98` | event | engine static / object IID (player 0x02..01 or entity) | exec `0x5643f0` / ser `0x565a50` / h 0x562f80 | u8 0 \| {u8,u64} \| GUID \| u32 \| u8 | World-object service event: {u8,u64} + GUID + u32 + u8 (?) | no |
| `0x9b` | event | engine static / object IID (player 0x02..01 or entity) | exec `0x57bd30` / ser `0x57bb50` / h 0x588a80 | u8 0 \| u32 \| u32 \| u8 | World-object service event: u32 u32 u8 (exec 0x57bd30) (?) | no |
| `0x9c` | event | engine: properties / session object (iface 37feb363) | exec `0x699020` / ser `0x445530` / h 0x6a8380 | u8 0 \| PropValue | Session-level property (iface 37feb363) (?) | no |
| `0x9d` | event | engine static / object IID (player 0x02..01 or entity) | exec `0x59da30` / ser `0x596ad0` / h 0x558060 | u8 | World-object service event, u8 (?) | no |
| `0x9e` | event | engine static / any (exec uses a service) | exec `0x59c030` / ser `0x59df70` / h 0x59bc80 | u8 0 \| WorldRef{u64,u64,GUID} \| Position \| u32 \| u8 | World-object (service 0x15bab54): object ref + position + u32 + u8 (0x59bc80) (?) | no |
| `0x9f` | event | engine static / object IID (player 0x02..01 or entity) | exec `0x568100` / ser `0x563f90` / h 0x567ed0 | u8 0 \| u32 \| {{{u32 u8}}} | World-object service event u32 (?) | no |
| `0xa3` | event | engine static / any (exec uses a service) | exec `0x589090` / ser `0x58f470` / h 0x4994d0 | u8 0 \| {u8,u64} \| GUID \| u64 \| u32 | World-object service event: {u8,u64} + GUID + u64 + u32 (?) | no |
| `0xa5` | event | engine static / any (exec uses a service) | exec `0x588fb0` / ser `0x58d5d0` / h 0x56f600 | u8 0 \| GUID \| {{GUID}} | World-object service event: GUID + list of GUIDs (?) | no |
| `0xa7` | event | engine static / object IID (player 0x02..01 or entity) | exec `0x59d930` / ser `0x59d8d0` / h 0x558060 | u8 0 \| WorldRef{u64,u64,GUID} \| {GUID} | World-object service event: object ref + GUID (?) | no |
| `0xa8` | event | engine: client / object IID (player 0x02..01 or entity) | exec `0x698700` / ser `0x443e50` / h 0x633170 | u8 0 \| u64 | Client performance/report request (?) (0x633170 resets frame counters, uses 120.0) - u64 | no |
| `0xab` | event | engine: messages / session object (iface 37feb363) | exec `0x697dd0` / ser `0x4452e0` / h 0x5a8680,0x6a81f0 | u8 0 \| StringInfo | System text message (StringInfo) shown by the client (session service 0x15d2b10) (?) | no |
| `0xac` | event | engine static / object IID (player 0x02..01 or entity) | exec `0x538780` / ser `0x538970` / h - | u8 0 \| QueueKey{u32 did,u32 flags} | Engine handshake-style event {u32,u32} (exec 0x538780) (?) | no |
| `0xad` | event | engine static / object IID (player 0x02..01 or entity) | exec `0x538780` / ser `0x538970` / h - | u8 0 \| QueueKey{u32 did,u32 flags} | Engine handshake-style event {u32,u32} (?) | no |
| `0xb0` | event | engine: object lifecycle / object IID (player 0x02..01 or entity) | exec `0x698cd0` / ser `0x445430` / h 0x6298d0 | u8 0 \| {u8 {u16}} | Object listener callback (obj+0x60, vt+0x8) u8 + u16 (?) | no |
| `0xb1` | event | engine static / object IID (player 0x02..01 or entity) | exec `0x59d580` / ser `0x59d530` / h 0x558060 | u8 0 \| WorldRef{u64,u64,GUID} | World-object service event: object ref (?) | no |
| `0xb2` | event | engine static / typed world object (iface 6d8bb31c) | exec `0x5a19d0` / ser `0x59e050` / h 0x5c7c60,0x5697c0 | u8 0 \| WorldRef{u64,u64,GUID} \| Position \| {{{u8} GUID}} \| u32 | TypedWorldObject: object ref + position + ref + u32 (sets +0x154 of a typed world object) (?) | no |
| `0xb7` | event | engine: misc / object IID (player 0x02..01 or entity) | exec `0x698670` / ser `0x444bf0` / h 0x634f00 | u8 0 \| {{u32 u8}} | Engine object component (obj+4) list {u32,u8} (?) | no |
| `0xb8` | event | engine: movement/appearance / object IID (player 0x02..01 or entity) | exec `0x698210` / ser `0x4488e0` / h 0x6322d0 | u8 0 \| u64 \| {Position u64 u32 u32 u32 u32 {u32 {u64 {u32 {Position vec3 u32}}}} u32 vec3 u8 u8} | Appearance/model setup for object u64 with position and parts (0x631fa0, CModelComponent) | no |
| `0xba` | event | engine: messages / object IID (player 0x02..01 or entity) | exec `0x697c20` / ser `0xb0d380` / h 0x635670 | u8 | Engine service flag u8 (service 0x15cb5b0) (?) | no |
| `0xbc` | event | engine: properties / object IID (player 0x02..01 or entity) | exec `0x699330` / ser `0x445450` / h 0x635440 | u8 0 \| PropTable [trace stopped early] | Set several properties (property table) on the object (obj+0x38 vt+0xa4) | no |
| `0xc0` | event | engine static / object IID (player 0x02..01 or entity) | exec `0x564210` / ser `0x5658d0` / h 0x4a8550 | u8 0 \| {u8,u64} \| GUID \| {{{u32 u8}}} | World-object service event {u8,u64} + GUID (?) | no |
| `0xc1` | event | engine static / object IID (player 0x02..01 or entity) | exec `0x567710` / ser `0x589be0` / h 0x566e40 | u8 0 \| u32 | World-object service event u32 (?) | no |
| `0xc2` | event | engine: misc / iface SESS2 | exec `0x699550` / ser `0x444d00` / h 0x420920 | u8 0 \| GUID \| u32 | Store a session GUID + u32 (iface d4bce8af) (?) | no |
| `0xc4` | event | engine: properties / region object (iface 79d30b39) | exec `0x698f40` / ser `0x445480` / h - | u8 0 \| Position \| u32 | Region/cell event: position + u32 (iface 79d30b39) (?) | no |
| `0xc8` | event | engine static / any (exec uses a service) | exec `0x5958c0` / ser `0x839830` / h 0x5951f0 | u8 0 \| GUID | World-object service event: GUID (?) | no |
| `0xc9` | event | engine: messages / session object (iface 37feb363) | exec `0x697d50` / ser `0x4452e0` / h 0x5a8680,0x6a81c0 | u8 0 \| StringInfo | System text message variant (StringInfo) (?) | no |
| `0xca` | event | engine static / object IID (player 0x02..01 or entity) | exec `0x674f70` / ser `0x6786c0` / h 0x57b570,0x667320 | u8 0 \| QueueKey{u32 did,u32 flags} \| u32 | Engine event {u32,u32} + u32 (?) | no |
| `0xce` | event | engine: login/account / session object (iface 37feb363) | exec `0x698920` / ser `0x445310` / h 0x6a8520 | u8 0 \| {u32 {u64 u64 wstr u32 PropTable}} [trace stopped early] | Account character set (login) | yes |
| `0xcf` | event | engine: login/account / session object (iface 37feb363) | exec `0x6988b0` / ser `0x839500` / h 0x6a8330 | u8 0 \| u32 | Login/character result code u32 (0x6a8330) (?) | no |
| `0xd0` | event | engine static / object IID (player 0x02..01 or entity) | exec `0x577040` / ser `0x5763a0` / h - | u8 0 \| u8 \| WorldRef{u64,u64,GUID} \| u32 | World-object service: u8 + object ref + u32 (?) | no |
| `0xd1` | event | engine static / typed world object (iface 6d8bb31c) | exec `0x5a0d10` / ser `0x5a13e0` / h 0x599a70,0xaf4780 | u8 0 \| {WorldRef{u64,u64,GUID} {{{{u8} GUID}} {{u8}} {{u8}} {u32 u32 u32 u32 u32 u32} Position u8 u32 u8 u8 u8 u8 u32 u64} {u32 u32 u32 u32 u32 u32} {u32 u32 u32 u32 u32 u32} Position Position u32} | TypedWorldObject create/update: object ref, template refs, 3 transforms, positions, flags (big) (?) | no |
| `0xd2` | event | engine static / object IID (player 0x02..01 or entity) | exec `0x564080` / ser `0x5641c0` / h 0x54cc90,0x402d60 | {u8 0 u32 {{{u32 u8}}}} \| u64 | World-object event with u32 + u64 (header inside struct) (?) | no |
| `0xd7` | event | engine: properties / region object (iface 79d30b39) | exec `0x698fb0` / ser `0x839500` / h - | u8 0 \| u32 | Region/cell event u32 (iface 79d30b39) (?) | no |
| `0xd8` | event | engine: object lifecycle / object IID (player 0x02..01 or entity) | exec `0x698bb0` / ser `0x447e60` / h 0x634f40 | u8 0 \| {u32 Position} | Object call obj vt+100 with u32 (?) | no |
| `0xd9` | event | engine: object lifecycle / object IID (player 0x02..01 or entity) | exec `0x698b10` / ser `0x446f30` / h 0x402c60,0x6354c0 | u8 0 \| {cint,u8} | Object call with {cint,u8} key (?) | no |
| `0xe0` | event | engine static / object IID (player 0x02..01 or entity) | exec `0x538780` / ser `0x538970` / h - | u8 0 \| QueueKey{u32 did,u32 flags} | Engine handshake-style event {u32,u32} (?) | no |
| `0xe2` | event | engine: properties / session object (iface 37feb363) | exec `0x698ed0` / ser `0x839500` / h 0x6a8410 | u8 0 \| u32 | Session-level u32 (iface 37feb363) (?) | no |
| `0xe4` | event | engine static / any (exec uses a service) | exec `0x599100` / ser `0x59e4e0` / h 0x56e6a0 | u8 0 \| u8 \| WorldRef{u64,u64,GUID} \| {u32} \| u32 \| u32 \| {{u8} GUID} | Visibility/awareness of an object (?) (0x56e6a0: u8 on/off, ref, timers +10 s/+20 s) | no |
| `0xe6` | event | engine static / object IID (player 0x02..01 or entity) | exec `0x5b7be0` / ser `0x5b9fa0` / h 0x4a6010 | u8 0 \| {u8,u64} \| GUID \| u32 \| {{u8} GUID} | World-object service: {u8,u64} GUID u32 GUID (?) | no |
| `0xe9` | event | engine static / any (exec uses a service) | exec `0x588f70` / ser `0x58aa00` / h 0x58fbd0 | u8 0 \| PropTable [trace stopped early] | Property table (service) (?) | no |
| `0xea` | event | engine static / object IID (player 0x02..01 or entity) | exec `0x697ac0` / ser `0x68f240` / h 0x62a580 | u8 0 \| u32 \| u32 | Engine event u32 u32 (?) | no |
| `0xeb` | event | engine: object lifecycle / session object (iface 37feb363) | exec `0x698a90` / ser `0x4453c0` / h 0x6a8170 | u8 0 \| u64 \| PropTable [trace stopped early] | Set local player | yes |
| `0xee` | event | engine static / typed world object (iface 6d8bb31c) | exec `0x59c060` / ser `0x59edf0` / h 0x5c7c60,0x5697c0 | u8 0 \| WorldRef{u64,u64,GUID} \| Position \| Position \| {u32 u32 u32 u32 u32 u32} \| u32 \| {{u8} GUID} | TypedWorldObject: ref + 2 positions + 6 u32 + u32 + GUID (?) | no |
| `0xf2` | event | engine static / any (exec uses a service) | exec `0x5d9ff0` / ser `0x445970` / h - | u8 0 \| {{u32} u64} \| u32 | Engine event (no-op handler in this build) | no |
| `0xf5` | event | engine: movement/appearance / object IID (player 0x02..01 or entity) | exec `0x698400` / ser `0x83faa0` / h 0x62cc20 | u8 0 \| u64 \| u32 \| u32 | Appearance part attribute: object u64, part u32, value u32 (obj+0x58 part +0x194) | no |
| `0xf8` | event | engine: properties / object IID (player 0x02..01 or entity) | exec `0x699170` / ser `0x446f30` / h 0x402c60,0x6352d0 | u8 0 \| {cint,u8} | Object string/key event {cint,u8} (?) | no |
| `0xfa` | event | engine static / object IID (player 0x02..01 or entity) | exec `0x446460` / ser `0x444b10` / h - | u32 | Raw u32 event (no-op handler) | no |
| `0xfc` | event | engine static / any (exec uses a service) | exec `0x589020` / ser `0x5896c0` / h 0x572b80 | u8 0 \| GUID | World-object service: GUID (?) | no |
| `0xfd` | event | engine static / object IID (player 0x02..01 or entity) | exec `0x5683b0` / ser `0x5659e0` / h 0x46d1a0,0x476d00 | u8 0 \| {u8,u64} \| GUID | World-object service: {u8,u64} GUID (?) | no |
| `0xff` | event | engine static / iface SVC-fdd7 | exec `0x594fc0` / ser `0x595870` / h - | u8 0 \| {{{u8} GUID}} \| GUID | Service event: GUID list + GUID (iface fdd74f27) (?) | no |
| `0x101` | event | engine: messages / session object (iface 37feb363) | exec `0x697ba0` / ser `0x445270` / h 0x5a8680,0x6a8190 | u8 0 \| u64 \| StringInfo | System text from an IID: u64 + StringInfo (?) | no |
| `0x103` | event | engine static / object IID (player 0x02..01 or entity) | exec `0x58dd70` / ser `0x589b80` / h 0x58b4c0 | u8 0 \| {u8,u8} | Property-kind event {u8,u8} (?) | no |
| `0x104` | event | engine: properties / region object (iface 79d30b39) | exec `0x699100` / ser `0x445530` / h - | u8 0 \| PropValue | Region/cell property (iface 79d30b39) (?) | no |
| `0x105` | event | engine: login/account / session object (iface 37feb363) | exec `0x698840` / ser `0x83c2e0` / h 0x6a8130 | u8 0 \| u32 \| StringInfo | Login/character error code + StringInfo text (0x6a8130) (?) | no |
| `0x106` | event | engine: movement/appearance / object IID (player 0x02..01 or entity) | exec `0x698540` / ser `0x444b70` / h 0x62ef80 | u8 0 \| u64 \| u32 | Appearance: object u64, part u32 -> remove/reset part (0x62ebf0) (?) | no |
| `0x10b` | event | engine static / any (exec uses a service) | exec `0x588ef0` / ser `0x58a9a0` / h - | u8 0 \| PropValue | Property value (service) (?) | no |
| `0x10d` | event | engine: movement/appearance / object IID (player 0x02..01 or entity) | exec `0x697ee0` / ser `0x4486b0` / h 0x630160 | u8 0 \| {u64 {u32 {Position}}} [trace stopped early] | Appearance: add parts list to object (obj+0x58 -> 0x62fb20) | no |
| `0x10f` | event | engine static / object IID (player 0x02..01 or entity) | exec `0x538780` / ser `0x51bb20` / h - | {u8 0 QueueKey{u32 did,u32 flags}} \| u8 | Engine handshake-style event {u32,u32} + u8 (?) | no |
| `0x110` | event | engine: properties / region object (iface 79d30b39) | exec `0x698e60` / ser `0x445450` / h - | u8 0 \| PropTable [trace stopped early] | Region/cell property table (iface 79d30b39) (?) | no |
| `0x111` | event | engine static / any (exec uses a service) | exec `0x5709d0` / ser `0x570a90` / h 0x588290 | u8 0 \| {cint Position u64 {{u8} GUID}} \| u32 | World-object service: cint + position + u64 + ref + u32 (?) | no |
| `0x112` | event | engine static / object IID (player 0x02..01 or entity) | exec `0x5681c0` / ser `0x565860` / h 0x568040,0x54cc90 | {u8 0 u32 {{{u32 u8}}}} \| {u8,u64} \| GUID | World-object event (header in struct) + {u8,u64} GUID (?) | no |
| `0x113` | event | engine static / object IID (player 0x02..01 or entity) | exec `0x5b7db0` / ser `0x5ba050` / h 0x4a6100 | u8 0 \| {u8,u64} \| GUID \| u32 \| {{u8} GUID} | World-object service: {u8,u64} GUID u32 GUID (?) | no |
| `0x115` | event | engine: movement/appearance / object IID (player 0x02..01 or entity) | exec `0x698000` / ser `0xb0d380` / h 0x62cc60 | u8 | Appearance LOD/refresh flags u8 for all parts (0x62cc60) | no |
| `0x116` | event | engine: messages / object IID (player 0x02..01 or entity) | exec `0x697cb0` / ser `0x4483a0` / h 0x635520 | u8 0 \| Position \| {u32 {{u32 u32 u32 u32}} {u32}} \| u32 \| u32 | Map visualization chunk (debug): position, list, part n of m | no |
| `0x117` | event | engine: object lifecycle / object IID (player 0x02..01 or entity) | exec `0x698990` / ser `0xb0d380` / h 0x634f70 | u8 | Engine object event u8 (?) | no |
| `0x11a` | event | engine static / object IID (player 0x02..01 or entity) | exec `0x5642c0` / ser `0x5659e0` / h 0x4a8550 | u8 0 \| {u8,u64} \| GUID | World-object service: {u8,u64} GUID (?) | no |
| `0x11b` | event | engine static / any (exec uses a service) | exec `0x560ce0` / ser `0x5659e0` / h 0x484f60 | u8 0 \| {u8,u64} \| GUID | World-object service: {u8,u64} GUID (?) | no |
| `0x11f` | event | engine static / object IID (player 0x02..01 or entity) | exec `0x675280` / ser `0x6751a0` / h 0x57c4b0 | u8 0 \| u32 \| u32 \| u8 | World-object event u32 u32 u8 (?) | no |
| `0x123` | event | engine: client / object IID (player 0x02..01 or entity) | exec `0x6987a0` / ser `0x444cb0` / h 0x633270 | u8 0 \| u32 | Set a client scale factor 0.08-1.0 (0x633270) (?) | no |
| `0x124` | event | engine: movement/appearance / object IID (player 0x02..01 or entity) | exec `0x6984a0` / ser `0x83faa0` / h 0x62cbe0 | u8 0 \| u64 \| u32 \| u32 | Appearance: object u64, part u32, state u32 (0x62ba80) | no |
| `0x127` | event | engine static / object IID (player 0x02..01 or entity) | exec `0x6750f0` / ser `0x675030` / h 0x588ac0 | u8 0 \| u32 \| u32 \| u32 | World-object event u32 u32 u32 (?) | no |
| `0x129` | event | engine: properties / object IID (player 0x02..01 or entity) | exec `0x699210` / ser `0x839500` / h 0x6353b0 | u8 0 \| u32 | Remove one property id (same as 0x86) | no |
| `0x12c` | event | engine static / object IID (player 0x02..01 or entity) | exec `0x59d6d0` / ser `0x59d670` / h 0x558060 | u8 0 \| WorldRef{u64,u64,GUID} \| Position | World-object service: object ref + position (?) | no |
| `0x133` | event | engine static / object IID (player 0x02..01 or entity) | exec `0x674ec0` / ser `0x6786c0` / h 0x671740 | u8 0 \| QueueKey{u32 did,u32 flags} \| u32 | Engine event {u32,u32} + u32 (?) | no |
| `0x134` | event | engine static / object IID (player 0x02..01 or entity) | exec `0x58dcd0` / ser `0x58a9a0` / h 0x58b770 | u8 0 \| PropValue | Property value (service) (?) | no |
| `0x138` | event | engine: movement/appearance / object IID (player 0x02..01 or entity) | exec `0x697f70` / ser `0x4488b0` / h 0x631550 | u8 0 \| {u32 {u64 {u32 {Position}}}} [trace stopped early] | Batch appearance refresh for a list of objects (+ scriptlet 0x14 on type-9 objects) | no |
| `0x13b` | event | engine: properties / object IID (player 0x02..01 or entity) | exec `0x699450` / ser `0x445530` / h 0x635360 | u8 0 \| PropValue | Set one property (same as 0x6) | no |
| `0x13c` | event | engine: properties / object IID (player 0x02..01 or entity) | exec `0x6992a0` / ser `0x839500` / h 0x6353a0 | u8 0 \| u32 | Remove one property id (same as 0x86) | no |
| `0x13d` | event | engine: properties / object IID (player 0x02..01 or entity) | exec `0x6993c0` / ser `0x445450` / h 0x635480 | u8 0 \| PropTable [trace stopped early] | Set property table on object (obj+0x38 vt+0xa8) | no |
| `0x2001` | event | Dialog / object IID (player 0x02..01 or entity) | exec `0x8b2180` / ser `0x8453a0` / h 0xa13b90 | u8 0 \| u64 \| u32 \| u32 conversation key \| list<u64> speakers \| u8 \| u32 instance | Dialog: start conversation (root+0x1c dialog system, vt+8) | yes |
| `0x2003` | event | Contacts / player system 0x0600000000000403 | exec `0x8ac770` / ser `0x842450` / h 0xa35810 | u8 0 \| u64 \| u64 \| wstr | Contacts: invite received [Contacts.RecvNotice_UI_NotifyContactOfInvite] | no |
| `0x2004` | event | Lobby / player system 0x0600000000000403 | exec `0x8b8d30` / ser `0x83fca0` / h 0xab87d0 | u8 0 \| u32 \| u32 \| u32 \| u64 | Lobby: player picked Stolen Powers [Lobby.RecvNotice_PlayerPickedStolenPowers] | no |
| `0x2005` | event | Lobby / player system 0x0600000000000403 | exec `0x8b8a10` / ser `0x68f240` / h 0xab8690 | u8 0 \| u32 \| u32 | Lobby: character lock failed [Lobby.RecvNotice_CharacterLockFail] | no |
| `0x2006` | event | MapManager notes / object IID (player 0x02..01 or entity) | exec `0x8b70e0` / ser `0x83fb40` / h 0xa56c90 | u8 0 \| u32 \| Handle{u32,u64} \| u32 \| u32 \| {u32} \| u32 | MapManager: add map note (minimap marker/ping): type, handle {u32,u64}, ... | no |
| `0x2008` | event | Effects (agent obj+0x8C) / object IID (player 0x02..01 or entity) | exec `0x8b68c0` / ser `0x83faa0` / h 0xaa1bf0 | u8 0 \| u64 \| u32 \| u32 | Effects: raise script event (DID) on the agent's effects matching key | no |
| `0x2009` | event | Encounter / object IID (player 0x02..01 or entity) | exec `0x8b56b0` / ser `0x83bf50` / h 0xa84330 | u8 0 \| u32 objective id \| objective (u32 flags, then fields by flag: 0x8000 state, 0x1 category, 0x80 text, 0x10 count, 0x4 max, 0x4000 sort, 0x80000 active, 0x100 optional, 0x1000000 banner) | Encounter: objective update (flag-driven fields) [Encounter.RecvNotice_UI_UpdateObjective_Count, Encounter.RecvNotice_UI_UpdateObjective_CountMax, Encounter.RecvNotice_UI_UpdateObjective_State] | yes |
| `0x200c` | event | Effects (agent obj+0x8C) / object IID (player 0x02..01 or entity) | exec `0x8b6c70` / ser `0x846f30` / h 0xaa1cd0 | u8 0 \| {u32 {{{cint {u32}} {cint {u32}} {u32 u32}} GUID u8 {u32}}} \| u8 | Effects: apply a list of effect instances to the agent (+ u8) | no |
| `0x200e` | event | MapManager notes / object IID (player 0x02..01 or entity) | exec `0x8b71a0` / ser `0x83f5b0` / h 0xa21a00 | u8 0 \| Handle{u32,u64} | MapManager: remove map note by handle | no |
| `0x200f` | event | Effects (agent obj+0x8C) / object IID (player 0x02..01 or entity) | exec `0x8b6bd0` / ser `0x843d60` / h 0xa9fb00 | u8 0 \| {{{{cint {u32}} {cint {u32}} {u32 u32}} GUID u8 {u32}}} \| u8 | Effects: add one effect instance (u8 = fresh) | no |
| `0x2011` | event | CustomMatch / player system 0x0600000000000403 | exec `0x8af920` / ser `0xb0d380` / h 0xa775b0 | u8 | CustomMatch: cancelled [CustomMatch.RecvNotice_UI_CustomMatch_Cancelled] | no |
| `0x2012` | event | CustomMatch / player system 0x0600000000000403 | exec `0x8af820` / ser `0x83bdf0` / h 0xa1b290 | u8 0 \| {wstr u64 u64 u32 u32 u32 u8} u32 | CustomMatch: participant added [CustomMatch.RecvNotice_UI_CustomMatch_AddedParticipant] | no |
| `0x2013` | event | Contacts / player system 0x0600000000000403 | exec `0x8ac970` / ser `0x847950` / h 0xa57da0 | u8 0 \| {u32 {u64 wstr u64}} | Contacts: pending invites [Contacts.RecvNotice_UI_NotifyContactOfPendingInvites] | no |
| `0x2014` | event | Contacts / player system 0x0600000000000403 | exec `0x8ac470` / ser `0x8423e0` / h 0xa58650 | u8 0 \| u64 \| wstr | Contacts: group created [Contacts.RecvNotice_UI_NotifyContactGroupCreated] | no |
| `0x2015` | event | Lobby / player system 0x0600000000000403 | exec `0x8b8c20` / ser `0x83f690` / h 0x132c5c0 | u8 0 \| u32 \| u8 | Player system: u32 u8 (no-op handler in this build) | no |
| `0x2016` | event | Lobby / player system 0x0600000000000403 | exec `0x8b8a90` / ser `0x839500` / h 0xab9080 | u8 0 \| u32 | Lobby: end room check (arms 60 s watchdog) [Lobby.RecvNotice_HideBackButton] | yes |
| `0x2018` | event | Contacts / player system 0x0600000000000403 | exec `0x8ac6f0` / ser `0x846d10` / h 0xa58970 | u8 0 \| {u32 {u64 u64 wstr u64 wstr wstr u32 u8 u32 u32 u32 u32 u32 u32 u32 wstr u32}} | Contacts: presence changed [Contacts.RecvNotice_UI_NotifyContactPresenceChanged] | no |
| `0x2019` | event | Effects (agent obj+0x8C) / object IID (player 0x02..01 or entity) | exec `0x8b6d10` / ser `0x83c1a0` / h 0xaaa830 | u8 0 \| GUID \| {u32 u32 u32} \| {u32 {u32}} | Effects: update an effect instance's script variable (GUID, var, value) | no |
| `0x201c` | event | Encounter / object IID (player 0x02..01 or entity) | exec `0x8b57f0` / ser `0x848af0` / h 0xa80440 | u8 0 \| {u32 {u32 {u8 u32 u32 PropTable}}} [trace stopped early] | Encounter: add entries to the encounter UI list (root+0x68) + u8 (?) | no |
| `0x201d` | event | Floaty (obj+0x90) / object IID (player 0x02..01 or entity) | exec `0x8b2580` / ser `0x8454d0` / h 0xaa7200 | u8 0 \| {u32 {u32 Handle{u32,u64}}} | Floaty/combat-text: replace floaty list (obj+0x90) | no |
| `0x201f` | event | CustomMatch / player system 0x0600000000000403 | exec `0x8afc90` / ser `0x83c280` / h 0xa0c570 | u8 0 \| StringInfo \| u32 | CustomMatch: invited [CustomMatch.RecvNotice_UI_CustomMatch_Invited] | no |
| `0x2020` | event | Contacts / player system 0x0600000000000403 | exec `0x8ac7f0` / ser `0x839dd0` / h 0xa306d0 | u8 0 \| u64 | Contacts: contact removed [Contacts.RecvNotice_UI_NotifyContactRemoved] | no |
| `0x2021` | event | Lobby / player system 0x0600000000000403 | exec `0x8b8dc0` / ser `0x839500` / h 0xabd730 | u8 0 \| u32 | Lobby: exit lobby / leave world (RecvEvt_DeliverNotifyPlayerToExitLobby) [UI.RecvNotice_GameFrontUIDestroyedInCPP, UI.RecvNotice_ExitingWorld, Lobby.RecvNotice_ClearLightResourcePackReferences] | built, off |
| `0x2022` | event | Player-object gameplay / object IID (player 0x02..01 or entity) | exec `0x8b5950` / ser `0x83c010` / h 0xaa0500 | u8 0 \| {u32 u32 u32 u32 u32 vec3 u8 u64 u32 u8 u32 u32 u32 u32 u32} | Agent component obj+0xbc vt+0x4c: big struct (5 u32, vec3, u8, u64, u32, u8, 5 u32) - probable movement/knock/teleport command (?) | no |
| `0x2023` | event | Encounter / object IID (player 0x02..01 or entity) | exec `0x8b5750` / ser `0x83bfb0` / h 0xa14040 | u8 0 \| u32 \| {u32 u32} | Encounter: objective category update / remove [Encounter.RecvNotice_UI_RemoveObjectiveCategory, Encounter.RecvNotice_UI_UpdateObjectiveCategory_State] | no |
| `0x2024` | event | Encounter / player system 0x0600000000000403 | exec `0x8b2970` / ser `0x846d40` / h 0xa733b0 | u8 0 \| list<u32> \| list<u32> \| {u32 {cint,u8}} \| list<u32> \| u32 \| {u32 {cint,u8}} \| u8 \| wstr \| wstr \| u64 | Encounter info (master encounter list) [Encounter.RecvNotice_MasterEncounterListReceived, Encounter.RecvNotice_ResetMapSelectionList, ConnectionManager.RecvNotice_UpdateConnectionState] | yes |
| `0x2027` | event | CustomMatch / player system 0x0600000000000403 | exec `0x8afc10` / ser `0x839500` / h 0xa0c710 | u8 0 \| u32 | CustomMatch: invite cancelled [CustomMatch.RecvNotice_UI_CustomMatch_InviteCancelled] | no |
| `0x2028` | event | Lobby / player system 0x0600000000000403 | exec `0x8b9240` / ser `0x846620` / h 0xabc3c0 | u8 0 \| QueueKey{u32 did,u32 flags} \| {u32 StringInfo} \| {u32 StringInfo} | Lobby: room created [Lobby.RecvNotice_LobbyRoomCreated, Encounter.RecvNotice_UI_SetEndOfMatchStatsHeader, Lobby.RecvNotice_ClearLightResourcePackReferences] | yes |
| `0x2029` | event | Lobby / player system 0x0600000000000403 | exec `0x8b9150` / ser `0x8479b0` / h 0xabd0a0 | u8 0 \| {u8 u32 u32 u32 list<u32> list<u64> u32 u32 u64} \| u32 \| u32 \| u64 \| StringInfo \| u8 \| u32 \| u32 \| u8 \| u32 \| u32 \| u32 \| u32 \| u32 \| u32 \| u32 \| u32 \| u32 \| {u32 u64 u32 StringInfo wstr u32 {cint u32}} | Lobby: player slot [Lobby.RecvNotice_PlayerPickedStolenPowers, Lobby.RecvNotice_UpdateLobbyStateSingle, Lobby.RecvNotice_PlayerPickedAmplifierSet] | yes |
| `0x202a` | event | Dialog / object IID (player 0x02..01 or entity) | exec `0x8b2230` / ser `0x839500` / h 0xa1b400 | u8 0 \| u32 | Dialog: set voice/speaker DID (root+0x1c +0xd0) | no |
| `0x202b` | event | Effects (agent obj+0x8C) / object IID (player 0x02..01 or entity) | exec `0x8b6b40` / ser `0x839830` / h 0xaa4220 | u8 0 \| GUID | Effects: remove effect instance (GUID) | no |
| `0x202c` | event | Effects (agent obj+0x8C) / object IID (player 0x02..01 or entity) | exec `0x8b6aa0` / ser `0x849b80` / h 0xa9fbb0 | u8 0 \| GUID \| {u32} | Effects: raise script events on one effect instance (GUID, list) | no |
| `0x202e` | event | CustomMatch / player system 0x0600000000000403 | exec `0x8afb90` / ser `0x8427a0` / h 0xa1b210 | u8 0 \| u64 \| wstr \| u32 | CustomMatch: invitation status [CustomMatch.RecvNotice_UI_CustomMatch_InvitationStatus] | no |
| `0x202f` | event | Contacts / player system 0x0600000000000403 | exec `0x8ac570` / ser `0x8478d0` / h 0xa46ad0 | u8 0 \| {u32 {u64 wstr}} | Contacts: list (0xa3d140) (?) | no |
| `0x2031` | event | Lobby / player system 0x0600000000000403 | exec `0x8b8fd0` / ser `0x8459e0` / h 0xab8730 | u8 0 \| list<u32> \| list<u32> \| list<u32> \| u32 | Lobby: loading percent [Lobby.RecvNotice_UpdateLobbyLoadingPercent] | yes |
| `0x2033` | event | Grouping / player system 0x0600000000000403 | exec `0x8b6220` / ser `0x4452e0` / h 0xa0d1e0 | u8 0 \| StringInfo | Grouping: show group invite dialog [Grouping.RecvNotice_ShowGroupInviteDialog] | no |
| `0x2034` | event | Encounter / object IID (player 0x02..01 or entity) | exec `0x8b28e0` / ser `0x83bf30` / h 0xa803e0 | u8 0 \| u32 n x objective (flags-driven, 0x872330) \| u32 n x category (0x863570) | Encounter: objective list + categories [Encounter.RecvNotice_UI_SetObjectiveTrackerEnabled, Encounter.RecvNotice_UI_DeliverObjectiveCategories] | yes |
| `0x2035` | event | CustomMatch / player system 0x0600000000000403 | exec `0x8afe80` / ser `0x839550` / h 0xa0c640 | u8 0 \| u64 \| u32 \| u8 | CustomMatch: permission changed [CustomMatch.RecvNotice_UI_CustomMatch_PermissionChanged] | no |
| `0x2036` | event | CustomMatch / player system 0x0600000000000403 | exec `0x8af990` / ser `0x839e20` / h 0xa0c6a0 | u8 0 \| u64 \| u64 | CustomMatch: coordinator changed [CustomMatch.RecvNotice_UI_CustomMatch_ChangedCoordinator] | no |
| `0x2037` | event | Effects (agent obj+0x8C) / object IID (player 0x02..01 or entity) | exec `0x8b6b40` / ser `0x839830` / h 0xaa4220 | u8 0 \| GUID | Effects: remove effect instance (GUID) (same as 0x202B) | no |
| `0x2038` | event | Encounter / player system 0x0600000000000403 | exec `0x8b2ab0` / ser `0x68f240` / h 0xa79170 | u8 0 \| u32 \| u32 | Encounter: match ended (UI state machine event 0x12) [UI.RecvNotice_UIStateMachineEvent] | yes |
| `0x2039` | event | Dialog / object IID (player 0x02..01 or entity) | exec `0x8b2040` / ser `0x83beb0` / h 0xa7fe60 | u8 0 \| u32 \| u32 \| PropTable [trace stopped early] | Dialog: play a context dialog element (announcer/VO chosen from team/context properties 0x100003BD, 0x10000865, 0x10000806, 0x1000081C...) with PropTable | no |
| `0x203a` | event | Contacts / player system 0x0600000000000403 | exec `0x8aca70` / ser `0x839500` / h 0xa13850 | u8 0 \| u32 | Contacts: self presence changed [Contacts.RecvNotice_UI_NotifySelfChangedPresence] | no |
| `0x203b` | event | Contacts / player system 0x0600000000000403 | exec `0x8ac670` / ser `0x846d10` / h 0xa46aa0 | u8 0 \| {u32 {u64 u64 wstr u64 wstr wstr u32 u8 u32 u32 u32 u32 u32 u32 u32 wstr u32}} | Contacts: list (0xa3ced0) (?) | no |
| `0x203d` | event | Effects (agent obj+0x8C) / object IID (player 0x02..01 or entity) | exec `0x8b6a00` / ser `0x839dd0` / h 0xaa1b60 | u8 0 \| u64 | Effects: raise 0x10000009 on effects flagged 0x10000007 (cleanse/expire all?) | no |
| `0x203e` | event | Player-object gameplay / object IID (player 0x02..01 or entity) | exec `0x8b5e20` / ser `0x839720` / h 0x132c5c0 | u8 0 \| u8 | Player-object event u8 (no-op handler) | no |
| `0x203f` | event | CustomMatch / player system 0x0600000000000403 | exec `0x8aff80` / ser `0x83be20` / h 0xa77520 | u8 0 \| {u32 QueueKey{u32 did,u32 flags} {u32 {u32 {wstr u64 u64 u32 u32 u32 u8} u32}} {u32 {wstr u64 u64 u32 u32 u32 u8} u32 u32} u64 u32 u32 {u32 StringInfo} {u32 StringInfo} u8} | CustomMatch: left [CustomMatch.RecvNotice_UI_CustomMatch_Left] | no |
| `0x2040` | event | CustomMatch / player system 0x0600000000000403 | exec `0x8afd90` / ser `0xb0d380` / h 0xa0c6f0 | u8 | CustomMatch: launched [CustomMatch.RecvNotice_UI_CustomMatch_Launched] | no |
| `0x2041` | event | CustomMatch / player system 0x0600000000000403 | exec `0x8afd10` / ser `0x839500` / h 0xa77600 | u8 0 \| u32 | CustomMatch: kicked [CustomMatch.RecvNotice_UI_CustomMatch_Kicked] | no |
| `0x2042` | event | CustomMatch / player system 0x0600000000000403 | exec `0x8afb10` / ser `0x4452e0` / h 0x5a8680,0xa0c6d0 | u8 0 \| StringInfo | CustomMatch: creation failed [CustomMatch.RecvNotice_UI_CustomMatch_CreationFailed] | no |
| `0x2043` | event | Effects (agent obj+0x8C) / object IID (player 0x02..01 or entity) | exec `0x8b6c70` / ser `0x846f30` / h 0xaa1cd0 | u8 0 \| {u32 {{{cint {u32}} {cint {u32}} {u32 u32}} GUID u8 {u32}}} \| u8 | Effects: apply a list of effect instances (same as 0x200C) | no |
| `0x2044` | event | Player-object gameplay / object IID (player 0x02..01 or entity) | exec `0x8b5eb0` / ser `0x839790` / h 0xa1a510 | u8 0 \| u64 \| u8 | Root+0x90 counter push/pop (u64, u8 on/off) (?) | no |
| `0x2045` | event | Encounter / player system 0x0600000000000403 | exec `0x8b2bd0` / ser `0x849ea0` / h 0xa91bf0 | u8 0 \| u32 n \| n x entry (reader 0x8776a0) \| f32 | Encounter: end-of-match stats [Encounter.RecvNotice_UI_SetEndOfMatchStatsHeader, Encounter.RecvNotice_PlayEndOfMatchEncounterMovie] | yes |
| `0x2047` | event | Dialog / object IID (player 0x02..01 or entity) | exec `0x8b20e0` / ser `0x839620` / h 0xa13b40 | u8 0 \| u64 \| u64 \| u32 \| u32 \| u32 | Dialog: dialog-system call vt+4 (u64, u64, 3 u32) - probable conversation line/advance (?) | no |
| `0x2048` | event | CustomMatch / player system 0x0600000000000403 | exec `0x8afe00` / ser `0x444b70` / h 0xa0c670 | u8 0 \| u64 \| u32 | CustomMatch: moved position [CustomMatch.RecvNotice_UI_CustomMatch_MovedPosition] | no |
| `0x204a` | event | Lobby / player system 0x0600000000000403 | exec `0x8b8ca0` / ser `0x83c200` / h 0xab9ab0 | u8 0 \| u32 \| {u32 u64 u32 StringInfo wstr u32 {cint u32}} \| u64 | Lobby: player picked amplifier set [Lobby.RecvNotice_PlayerPickedAmplifierSet] | no |
| `0x204b` | event | Lobby / player system 0x0600000000000403 | exec `0x8b8b90` / ser `0x838930` / h 0xabd420 | u8 0 \| u64 \| u64 \| u32 | Lobby: match launch warning [Lobby.RecvNotice_MatchLaunchWarning, Lobby.RecvNotice_ClearLightResourcePackReferences, Lobby.RecvNotice_ClearHeavyResourcePackReferences] | no |
| `0x204c` | event | Lobby / player system 0x0600000000000403 | exec `0x8b8970` / ser `0x845810` / h 0xabde80 | u8 0 \| u32 \| u32 \| QueueKey{u32 did,u32 flags} \| u64 \| u32 \| u32 \| {u32 {u32 u32 u32 u8 u32}} \| list<u32> \| u8 \| u8 | Lobby: state [Lobby.RecvNotice_UpdateLobbyStateSingle, Lobby.RecvNotice_LobbyEncounterDetails, UI.RecvNotice_Incremental_ItemStatuses] | yes |
| `0x204d` | event | Effects (agent obj+0x8C) / object IID (player 0x02..01 or entity) | exec `0x8b6aa0` / ser `0x849b80` / h 0xa9fbb0 | u8 0 \| GUID \| {u32} | Effects: raise events on one effect instance (same as 0x202C) | no |
| `0x204e` | event | Effects (agent obj+0x8C) / object IID (player 0x02..01 or entity) | exec `0x8b6820` / ser `0x444b70` / h 0xaa1b90 | u8 0 \| u64 \| u32 | Effects: raise script event DID on all effects of agent u64 | no |
| `0x204f` | event | Contacts / player system 0x0600000000000403 | exec `0x8ac870` / ser `0x839dd0` / h 0xa30740 | u8 0 \| u64 | Contacts: unignored [Contacts.RecvNotice_UI_NotifyContactUnignored] | no |
| `0x2050` | event | Player-object gameplay / object IID (player 0x02..01 or entity) | exec `0x8b5c50` / ser `0x444b70` / h 0xa14580 | u8 0 \| u64 \| u32 | Run scriptlet key u32 on object u64 (obj+0x10 scriptlet component, no variables) | no |
| `0x2051` | event | Contacts / player system 0x0600000000000403 | exec `0x8ac5f0` / ser `0x8423e0` / h 0xa58340 | u8 0 \| u64 \| wstr | Contacts: added / ignored / removed [Contacts.RecvNotice_UI_NotifyContactAdded, Contacts.RecvNotice_UI_NotifyContactIgnored, Contacts.RecvNotice_UI_NotifyContactRemoved] | no |
| `0x2052` | event | Amplifier / player system 0x0600000000000403 | exec `0x8a9fc0` / ser `0x839500` / h 0xa0b560 | u8 0 \| u32 | Amplifier: set error [Amplifier.RecvNotice_NotifyAmplifierSetError] | no |
| `0x2053` | event | Lobby / player system 0x0600000000000403 | exec `0x8b8ec0` / ser `0x8465b0` / h 0xaba390 | u8 0 \| u32 \| {u32 StringInfo} \| {u32 StringInfo} | Lobby: match started (UI event 0x14) [UI.RecvNotice_UIStateMachineEvent] | built, off |
| `0x2054` | event | Lobby / player system 0x0600000000000403 | exec `0x8b8870` / ser `0x83c4e0` / h 0xab7c10 | u8 0 \| StringInfo \| StringInfo | Lobby: draft trade request [Lobby.RecvNotice_Draft_TradeRequest] | no |
| `0x2056` | event | Player-object gameplay / object IID (player 0x02..01 or entity) | exec `0x8b5bb0` / ser `0x83c050` / h 0xa0d040 | u8 0 \| u32 \| PropTable [trace stopped early] | Run scriptlet key u32 on the destination object with a variable table (PropTable) | no |
| `0x2058` | event | Contacts / player system 0x0600000000000403 | exec `0x8acaf0` / ser `0x842830` / h 0xa27f70 | u8 0 \| wstr | Contacts: self status message changed [Contacts.RecvNotice_UI_NotifySelfChangedStatusMessage] | no |
| `0x2059` | event | Player-object gameplay / object IID (player 0x02..01 or entity) | exec `0x8b59e0` / ser `0x83f9b0` / h 0xa73580 | u8 0 \| u32 \| PropTable [trace stopped early] | Spawn a client-side object/effect from a template with properties (root+0x24, 0xa69170) (?) | no |
| `0x205b` | event | Lobby / player system 0x0600000000000403 | exec `0x8b87f0` / ser `0x68f240` / h 0xab8490 | u8 0 \| u32 \| u32 | Lobby: rejoin room [Lobby.RecvNotice_LobbyRejoinRoom] | no |
| `0x205c` | event | Player-object gameplay / object IID (player 0x02..01 or entity) | exec `0x8b5d90` / ser `0x839720` / h 0xa4ebc0 | u8 0 \| u8 | Root+0x5c: add/remove the destination player from a tracked list (u8) (?) | no |
| `0x205d` | event | CustomMatch / player system 0x0600000000000403 | exec `0x8aff00` / ser `0x839dd0` / h 0xa0c5b0 | u8 0 \| u64 | CustomMatch: participant removed [CustomMatch.RecvNotice_UI_CustomMatch_RemovedParticipant] | no |
| `0x205e` | event | Contacts / player system 0x0600000000000403 | exec `0x8ac4f0` / ser `0x846ca0` / h 0xa46b00 | u8 0 \| u64 \| {u32 {u64 u64 wstr u64 wstr wstr u32 u8 u32 u32 u32 u32 u32 u32 u32 wstr u32}} | Contacts: group destroyed [Contacts.RecvNotice_UI_NotifyContactGroupDestroyed] | no |
| `0x2060` | event | Lobby / player system 0x0600000000000403 | exec `0x8b9060` / ser `0x848380` / h 0xabe1b0 | u8 0 \| list<u32> \| list<u32> \| list<u64> \| {u32 StringInfo} \| {{u32 u8}} \| list<u32> \| list<u32> \| {{u32 u8}} \| u32 \| u32 \| u8 \| list<u32> \| list<u32> \| list<u32> \| list<u32> \| list<u32> \| list<u32> \| list<u32> \| {u32 {u32 u64 u32 StringInfo wstr u32 {cint u32}}} \| {u8 u32 u32 u32 list<u32> list<u64> u32 u32 u64} | Lobby: full state update [Lobby.RecvNotice_PlayerPickedStolenPowers, Lobby.RecvNotice_UpdateLobbyStateSingle, Lobby.RecvNotice_PlayerPickedAmplifierSet] | no |
| `0x2061` | event | Lobby / player system 0x0600000000000403 | exec `0x8b8f40` / ser `0x838930` / h 0xab85a0 | u8 0 \| u64 \| u64 \| u32 | Lobby: early launch time [Lobby.RecvNotice_UpdateEarlyLaunchTime] | no |
| `0x2062` | event | Effects (agent obj+0x8C) / object IID (player 0x02..01 or entity) | exec `0x8b6bd0` / ser `0x843d60` / h 0xa9fb00 | u8 0 \| {{{{cint {u32}} {cint {u32}} {u32 u32}} GUID u8 {u32}}} \| u8 | Effects: add one effect instance (same as 0x200F) | no |
| `0x2063` | event | Effects (agent obj+0x8C) / object IID (player 0x02..01 or entity) | exec `0x8b6960` / ser `0x849ab0` / h 0xaa1c90 | u8 0 \| u64 \| {u32} \| u32 | Effects: raise events on effects matching key (u64 agent, list, u32 key) | no |
| `0x2065` | event | Contacts / player system 0x0600000000000403 | exec `0x8acb70` / ser `0x839500` / h 0xa0c260 | u8 0 \| u32 | Contacts: contact list notification [Contacts.RecvNotice_UI_ContactListNotification] | no |
| `0x2069` | event | Encounter / object IID (player 0x02..01 or entity) | exec `0x8b5890` / ser `0x83f7b0` / h 0xa5a680 | u8 0 \| u64 \| u32 \| u32 \| u32 \| u32 \| u32 \| u32 \| u32 \| u32 \| u32 \| u32 \| u32 | Encounter: objective tracker status (world tracker icon x/y/state/icon/variant/category) [Encounter.RecvNotice_UI_UpdateTrackerStatus] | no |
| `0x206b` | event | Lobby / player system 0x0600000000000403 | exec `0x8b92c0` / ser `0x839500` / h 0xab8900 | u8 0 \| u32 | Lobby: connect to lobby (store or send ConnectToLobbyMessage) | no |
| `0x206c` | event | Lobby / player system 0x0600000000000403 | exec `0x8b8e40` / ser `0x83c280` / h 0xabd570 | u8 0 \| StringInfo \| u32 | Lobby: player selected early launch [Lobby.RecvNotice_PlayerSelectedEarlyLaunchFromServer, Lobby.RecvNotice_ClearLightResourcePackReferences, Lobby.RecvNotice_ClearHeavyResourcePackReferences] | no |
| `0x206d` | event | Lobby / player system 0x0600000000000403 | exec `0x8b8b10` / ser `0x839500` / h 0xab84f0 | u8 0 \| u32 | Lobby: all loaded? [Lobby.RecvNotice_HideBackButton, Lobby.RecvNotice_UpdateLobbyLoadingPercentForViewmatch, ViewMatch.RecvNotice_ViewMatch_ShowAllPlayersPanel] | yes |
| `0x206e` | event | Lobby / player system 0x0600000000000403 | exec `0x8b88f0` / ser `0x839500` / h 0xab8e00 | u8 0 \| u32 | Lobby: view-match enable (spectator) (?) | no |
| `0x206f` | event | Effects (agent obj+0x8C) / object IID (player 0x02..01 or entity) | exec `0x8b6d10` / ser `0x83c1a0` / h 0xaaa830 | u8 0 \| GUID \| {u32 u32 u32} \| {u32 {u32}} | Effects: update effect variable (same as 0x2019) | no |
| `0x2070` | event | Grouping / player system 0x0600000000000403 | exec `0x8b6310` / ser `0xb0d380` / h 0xa0d290 | u8 | Grouping: user can create group [UI.RecvNotice_UserCanCreateGroup] | no |
| `0x2071` | event | Grouping / player system 0x0600000000000403 | exec `0x8b6190` / ser `0x83c100` / h 0xa7b2d0 | u8 0 \| {u32 u64 {u32 {wstr u64 u64 u32 u32 u32 u8} u32} {u32 {wstr u64 u64 u32 u32 u32 u8} u32 u32} QueueKey{u32 did,u32 flags} u32} \| u8 \| StringInfo | Grouping: player left group [Grouping.RecvNotice_PlayerLeftGroup] | no |
| `0x2073` | event | Player-object gameplay / object IID (player 0x02..01 or entity) | exec `0x8b5b20` / ser `0x83c030` / h 0xa883f0 | u8 0 \| ScriptletList (same reader family as 0x8D) | Start scriptlets on listed entities via the local player (same body as 0x8D; 0xa22da0) | no |
| `0x2074` | event | Player-object gameplay / object IID (player 0x02..01 or entity) | exec `0x8b5a80` / ser `0x83f690` / h 0xaa0530 | u8 0 \| u32 \| u8 | Agent component obj+0xbc vt+0x50: u32 u8 (?) | no |
| `0x2075` | event | Encounter / object IID (player 0x02..01 or entity) | exec `0x8b2cf0` / ser `0x839720` / h 0xa14010 | u8 0 \| u8 | Encounter: objective tracker enabled [Encounter.RecvNotice_UI_SetObjectiveTrackerEnabled] | yes |
| `0x2076` | event | CustomMatch / player system 0x0600000000000403 | exec `0x8af8a0` / ser `0x444b70` / h 0xa0c610 | u8 0 \| u64 \| u32 | CustomMatch: assigned team [CustomMatch.RecvNotice_UI_CustomMatch_AssignedTeam] | no |
| `0x2077` | event | Usage (cast/channel bars) / object IID (player 0x02..01 or entity) | exec `0x8c1a70` / ser `0x839f20` / h 0xaa2570 | u8 0 \| u64 \| u64 \| u32 | Usage: induction (cast bar) percent [Usage.RecvNotice_UpdateInductionPercent] | no |
| `0x2078` | event | Upgrade / object IID (player 0x02..01 or entity) | exec `0x8c0a20` / ser `0x845df0` / h 0xa9ff30 | u8 0 \| list<u32> | Upgrade: next recommended upgrade [Upgrade.RecvNotice_UpdateNextRecommendedUpgrade] | no |
| `0x207b` | event | Skill HUD / object IID (player 0x02..01 or entity) | exec `0x8bc5f0` / ser `0x839ab0` / h 0xa26570 | u8 0 \| u64 \| u32 \| u8 \| u8 | Skill HUD: enable skill button [Skill.RecvNotice_EnableSkillButton] | no |
| `0x207c` | event | Skill HUD / object IID (player 0x02..01 or entity) | exec `0x8bc540` / ser `0x8399a0` / h 0xa3a000 | u8 0 \| u32 \| u32 \| u8 \| u32 \| u32 | Skill HUD: slot override table (slot<5: u32, u8, u32) | no |
| `0x2080` | event | Character/account / player system 0x0600000000000403 | exec `0x8aaac0` / ser `0x8392f0` / h 0xa7dfb0 | u8 0 \| u32 \| u32 \| u32 \| u32 \| u32 \| u32 \| u32 \| u32 | Account level / XP [Character.RecvNotice_SendAccountEndOfMatchLevelAndXP, Character.RecvNotice_SendAccountLevelAndXP, UI.RecvNotice_ProtectorAdvancementStatus] | yes |
| `0x2081` | event | Character/account / player system 0x0600000000000403 | exec `0x8aa970` / ser `0x68f240` / h 0xa1ab40 | u8 0 \| u32 \| u32 | Currency balance [Character.RecvNotice_SendAccountCurrencyBalance] | yes |
| `0x2082` | event | Usage (cast/channel bars) / object IID (player 0x02..01 or entity) | exec `0x8c0ec0` / ser `0x839dd0` / h 0xaaf400 | u8 0 \| u64 | Usage: channel started [Usage.RecvNotice_UpdateChannelStarted] | no |
| `0x2083` | event | Skill HUD / object IID (player 0x02..01 or entity) | exec `0x8bc730` / ser `0x839500` / h 0xa1a5a0 | u8 0 \| u32 | Root+0x90: store u32 (+0xc0) (?) | no |
| `0x2084` | event | Skill HUD / object IID (player 0x02..01 or entity) | exec `0x8bc2c0` / ser `0x444b70` / h 0xa0e430 | u8 0 \| u64 \| u32 | Remove a property (id u32) from entity u64 (0x58b4c0) | no |
| `0x2086` | event | Upgrade / object IID (player 0x02..01 or entity) | exec `0x8bfe50` / ser `0x83f5b0` / h 0xa0f570 | u8 0 \| Handle{u32,u64} | Clear the current selection if it equals handle (0xa0f570) (?) | no |
| `0x2087` | event | GM_UI / player system 0x0600000000000403 | exec `0x8be910` / ser `0x83c4e0` / h 0xac85f0 | u8 0 \| StringInfo \| StringInfo | UI: display dialog text (StringInfo, StringInfo) [UI.RecvNotice_DisplayDialogText] | no |
| `0x208c` | event | Skill HUD / object IID (player 0x02..01 or entity) | exec `0x8bc220` / ser `0x83f690` / h 0xa0e3c0 | u8 0 \| u32 \| u8 | Skill HUD: skill-button update suppressed [Skill.RecvNotice_UI_NotifySkillButtonUpdateIsSuppressed] | no |
| `0x208d` | event | Skill HUD / object IID (player 0x02..01 or entity) | exec `0x8bc190` / ser `0xb0d380` / h 0xa16dd0 | u8 | Vitals: display floaty status (u8) [Vitals.RecvNotice_DisplayFloatyStatus] | no |
| `0x208f` | event | Contacts / player system 0x0600000000000403 | exec `0x8ac3f0` / ser `0x83bdd0` / h 0xa27f10 | u8 0 \| {u64 u64 wstr u64 wstr wstr u32 u8 u32 u32 u32 u32 u32 u32 u32 wstr u32} | Contacts: change note [Contacts.RecvNotice_UI_NotifyContactChangeNote] | no |
| `0x2090` | event | Amplifier / player system 0x0600000000000403 | exec `0x8aa0c0` / ser `0x8481a0` / h 0xa64520 | u8 0 \| u32 \| u32 \| {u32 {u32 u64 u32 StringInfo wstr u32 {cint u32}}} | Amplifier sets list [Amplifier.RecvNotice_NotifyListAmplifierSets] | yes |
| `0x2091` | event | Skill HUD / object IID (player 0x02..01 or entity) | exec `0x8bc910` / ser `0x839c70` / h 0xa5d0a0 | u8 0 \| u64 \| u64 \| u32 \| u32 | Skill HUD: skill UI overlay [Skill.RecvNotice_UpdateSkillUIOverlay] | no |
| `0x2092` | event | Skill HUD / object IID (player 0x02..01 or entity) | exec `0x8bbfb0` / ser `0x68f240` / h 0xa2a190 | u8 0 \| u32 \| u32 | UI: execute-skill error [UI.RecvNotice_ExecuteSkillError] | no |
| `0x2095` | event | Character/account / player system 0x0600000000000403 | exec `0x8aaf60` / ser `0x83f410` / h 0xa7ea00 | u8 0 \| u32 \| u32 \| StringInfo | Item fulfilled ribbon [Character.RecvNotice_Ribbon_ItemFulfilled, Character.RecvNotice_Ribbon_FinishedItemsFulfilled] | built, off |
| `0x2096` | event | Usage (cast/channel bars) / object IID (player 0x02..01 or entity) | exec `0x8c0f50` / ser `0x839e20` / h 0xaa2620 | u8 0 \| u64 \| u64 | Usage: induction cancelled [Usage.RecvNotice_UpdateCancelledInductionForUserToFlash, Usage.RecvNotice_UpdateInductionPercent] | no |
| `0x209d` | event | Character/account / player system 0x0600000000000403 | exec `0x8aac90` / ser `0x849630` / h 0xa7e4b0 | u8 0 \| {u8 cint {u32 {u32 u32 u32 u64 u64}}} | Master character list | yes |
| `0x209e` | event | Character/account / player system 0x0600000000000403 | exec `0x8aab70` / ser `0x849e50` / h 0xa83370 | u8 0 \| {u8 cint {u32 {u32 StringInfo}}} | Character list delta (0xa83370) (?) | no |
| `0x209f` | event | Skill HUD / object IID (player 0x02..01 or entity) | exec `0x8bc690` / ser `0x839d50` / h 0xa5da40 | u8 0 \| u32 \| u64 | MapManager: show minimap targeting ring [MapManager.RecvNotice_ShowMiniMapTargetingRing] | no |
| `0x20a0` | event | Skill HUD / object IID (player 0x02..01 or entity) | exec `0x8bc4a0` / ser `0x8401e0` / h 0xa6dd10 | u8 0 \| u32 \| u32 \| Handle{u32,u64} \| u8 | Skill HUD: skill disable condition (slot, ErrorType, add/remove); catalog note says 16 bytes after ErrorType, the emulated Handle reader took 12 - check [Skill.RecvNotice_EnableSkillButton] | no (documented) |
| `0x20a2` | event | StatusIcon / object IID (player 0x02..01 or entity) | exec `0x8bd860` / ser `0x847d30` / h 0xab37b0 | u8 0 \| u64 \| list<u32> \| {u32 Handle{u32,u64}} \| list<u32> \| list<u32> \| {u32 StringInfo} \| list<u64> \| {u32 u64} \| {u32 u32} \| list<u64> \| {u32 {StringInfo u32 u32 {u32 {u8 u8 u8 u32}}}} \| list<u32> | StatusIcon: add status icon (+ stack count string) [UI.RecvNotice_UpdateSkillStackCountString, StatusIcon.RecvNotice_AddStatusIcon] | no |
| `0x20a8` | event | StatusIcon / object IID (player 0x02..01 or entity) | exec `0x8be360` / ser `0x840580` / h 0x5a8680,0xab3250 | u8 0 \| u64 \| Handle{u32,u64} \| u32 \| u32 \| StringInfo \| u64 \| u64 \| u32 \| u64 \| {StringInfo u32 u32 {u32 {u8 u8 u8 u32}}} \| u32 | StatusIcon: update status icon (+ stack count) [UI.RecvNotice_UpdateSkillStackCountString, StatusIcon.RecvNotice_UpdateStatusIcon] | no |
| `0x20ad` | event | Matchmaking / player system 0x0600000000000403 | exec `0x8ba9a0` / ser `0x839500` / h 0xa0dbe0 | u8 0 \| u32 | Players accepted match [UI.RecvNotice_NumPlayersAcceptedMatch] | yes |
| `0x20ae` | event | Contacts / player system 0x0600000000000403 | exec `0x8ac170` / ser `0x444b70` / h 0xa58790 | u8 0 \| u64 \| u32 | Contacts: presence changed (variant) [Contacts.RecvNotice_UI_NotifyContactPresenceChanged] | no |
| `0x20af` | event | Connection / player system 0x0600000000000403 | exec `0x8ac0e0` / ser `0x8452d0` / h 0xa99f00 | u8 0 \| u32 \| list<u32> \| list<u32> \| u32 | Enter match | yes |
| `0x20b0` | event | Chat / player system 0x0600000000000403 | exec `0x8abe20` / ser `0x8422a0` / h 0xa57cd0 | u8 0 \| wstr \| StringInfo \| wstr | Chat: strings, toggle unread / channel (?) [Chat.RecvNotice_ToggleUnreadChat] | no |
| `0x20b2` | event | Usage (cast/channel bars) / object IID (player 0x02..01 or entity) | exec `0x8c0ff0` / ser `0x839790` / h 0xaa4670 | u8 0 \| u64 \| u8 | Usage: channel interrupted / stopped [Usage.RecvNotice_ChannelingInterrupted, Usage.RecvNotice_UpdateChannelStopped] | no |
| `0x20b6` | event | Chat / player system 0x0600000000000403 | exec `0x8abea0` / ser `0x842300` / h 0xa770c0 | u8 0 \| wstr \| wstr | Chat: toggle unread [Chat.RecvNotice_ToggleUnreadChat] | no |
| `0x20b8` | event | Character/account / player system 0x0600000000000403 | exec `0x8aaff0` / ser `0x844fd0` / h 0xa88030 | u8 0 \| {u32 {u32 u32 u32 u8 u32}} | Item statuses [UI.RecvNotice_ItemStatuses, UI.RecvNotice_AvailableCharacterList, UI.RecvNotice_Incremental_ItemStatuses] | yes |
| `0x20b9` | event | Character/account / player system 0x0600000000000403 | exec `0x8aaeb0` / ser `0x83bb90` / h 0xa1aa50 | u8 0 \| u32 \| u32 \| u32 \| u32 \| u32 \| u32 \| StringInfo \| StringInfo \| u32 | Soft currency reward [Character.RecvNotice_SendAccountCurrencyBalanceChanges, Character.RecvNotice_SendAccountEndOfMatchSoftCurrencyReward] | yes |
| `0x20bb` | event | Usage (cast/channel bars) / object IID (player 0x02..01 or entity) | exec `0x8c1780` / ser `0x839eb0` / h 0xaa2540 | u8 0 \| u32 \| u32 | Usage: induction percent (variant) [Usage.RecvNotice_UpdateInductionPercent] | no |
| `0x20bc` | event | Usage (cast/channel bars) / object IID (player 0x02..01 or entity) | exec `0x8c0b50` / ser `0x839dd0` / h 0xaa02a0 | u8 0 \| u64 | Usage component obj+0x9c vt+0x50 (u64) (?) | no |
| `0x20bd` | event | Skill HUD / object IID (player 0x02..01 or entity) | exec `0x8bc050` / ser `0x444b70` / h 0xa16e20 | u8 0 \| u64 \| u32 | Vitals: display floaty status (u64, u32) [Vitals.RecvNotice_DisplayFloatyStatus] | no |
| `0x20c0` | event | Matchmaking / player system 0x0600000000000403 | exec `0x8ba780` / ser `0x83fe00` / h 0xa37c70 | u8 0 \| QueueKey{u32 did,u32 flags} \| u32 \| u32 \| u32 | Joined queue [UI.RecvNotice_JoinedQueue] | yes |
| `0x20c2` | event | Skill HUD / object IID (player 0x02..01 or entity) | exec `0x8bc870` / ser `0x83c470` / h 0xa0e480 | u8 0 \| u64 \| PropValue [trace stopped early] | Set a property (PropValue) on entity u64 (0x58b770) | no |
| `0x20c5` | event | Contacts / player system 0x0600000000000403 | exec `0x8ac1f0` / ser `0x8423e0` / h 0xa27fa0 | u8 0 \| u64 \| wstr | Contacts: status message changed [Contacts.RecvNotice_UI_NotifyContactChangeStatusMessage] | no |
| `0x20c7` | event | Amplifier / player system 0x0600000000000403 | exec `0x8aa040` / ser `0x83baf0` / h 0xa1ace0 | u8 0 \| {u32 u64 u32 StringInfo wstr u32 {cint u32}} | Amplifier: set [Amplifier.RecvNotice_NotifyAmplifierSet] | no |
| `0x20c8` | event | StatusIcon / object IID (player 0x02..01 or entity) | exec `0x8bdcd0` / ser `0x840390` / h 0x5a8680,0xab2d30 | u8 0 \| u64 \| u32 \| Handle{u32,u64} \| u32 \| u32 \| StringInfo \| u64 \| u64 \| u32 \| u64 \| {StringInfo u32 u32 {u32 {u8 u8 u8 u32}}} \| u32 | StatusIcon: add status icon (variant) [UI.RecvNotice_UpdateSkillStackCountString, StatusIcon.RecvNotice_AddStatusIcon] | no |
| `0x20c9` | event | Skill HUD / object IID (player 0x02..01 or entity) | exec `0x8bc400` / ser `0x849ce0` / h 0xa1d400 | u8 0 \| u64 \| u32 \| {u32} | Raise skill-slot event on agent (u64, u32, list) (0xa16e60) | no |
| `0x20cb` | event | Contacts / player system 0x0600000000000403 | exec `0x8ac370` / ser `0x83bdd0` / h 0xa35850 | u8 0 \| {u64 u64 wstr u64 wstr wstr u32 u8 u32 u32 u32 u32 u32 u32 u32 wstr u32} | Contacts: changed group [Contacts.RecvNotice_UI_NotifyContactChangedGroup] | no |
| `0x20cc` | event | Contacts / player system 0x0600000000000403 | exec `0x8ac270` / ser `0x83bdd0` / h 0xa58140 | u8 0 \| {u64 u64 wstr u64 wstr wstr u32 u8 u32 u32 u32 u32 u32 u32 u32 wstr u32} | Contacts: added / unignored / removed [Contacts.RecvNotice_UI_NotifyContactAdded, Contacts.RecvNotice_UI_NotifyContactUnignored, Contacts.RecvNotice_UI_NotifyContactRemoved] | no |
| `0x20ce` | event | Usage (cast/channel bars) / object IID (player 0x02..01 or entity) | exec `0x8c1b10` / ser `0x839e20` / h 0xa9e590 | u8 0 \| u64 \| u64 | Usage: induction complete [Usage.RecvNotice_UpdateInductionComplete] | no |
| `0x20d0` | event | StatusIcon / object IID (player 0x02..01 or entity) | exec `0x8be7d0` / ser `0x849300` / h 0xab1500 | u8 0 \| u64 \| Handle{u32,u64} \| u32 \| {u8 cint {u32 u32}} \| {u8 cint {u32 u32}} | StatusIcon: update tooltip [StatusIcon.RecvNotice_UpdateStatusIconTooltip] | no |
| `0x20d2` | event | MapManager / object IID (player 0x02..01 or entity) | exec `0x8ba4c0` / ser `0x83fd70` / h 0xa4c660 | u8 0 \| u64 \| Position \| u32 | MapManager: add minimap marker for IID at position (type u32) | no |
| `0x20d7` | event | Matchmaking / player system 0x0600000000000403 | exec `0x8baa20` / ser `0x839500` / h 0xa0dc00 | u8 0 \| u32 | Pending match failure [UI.RecvNotice_PendingMatchFailure] | no |
| `0x20da` | event | MapManager notes 2 / player system 0x0600000000000403 | exec `0x8c2ee0` / ser `0x845df0` / h 0xadb230,0xa7f0b0 | u8 0 \| list<u32> | Map notes: set u32 list (0xadb230) (?) | no |
| `0x20db` | event | Usage (cast/channel bars) / object IID (player 0x02..01 or entity) | exec `0x8c0e30` / ser `0x839dd0` / h 0xaa0270 | u8 0 \| u64 | Usage component obj+0x9c vt+0x4c (u64) (?) | no |
| `0x20dc` | event | Skill HUD / object IID (player 0x02..01 or entity) | exec `0x8bc360` / ser `0x68f240` / h 0xa0e3e0 | u8 0 \| u32 \| u32 | UI: execute-skill error (variant) [UI.RecvNotice_ExecuteSkillError] | no |
| `0x20dd` | event | Upgrade / object IID (player 0x02..01 or entity) | exec `0x8c0990` / ser `0x845df0` / h 0xaaa190 | u8 0 \| list<u32> | Upgrade: set list on obj+0xa4 (current upgrades) (?) | no |
| `0x20de` | event | svc 0x20DE / object IID (player 0x02..01 or entity) | exec `0x8bd0e0` / ser `0x839d50` / h 0xadb190 | u8 0 \| u32 \| u64 | Service event u32 u64 (service 0x160d8e0) (?) | no |
| `0x20e0` | event | Matchmaking / player system 0x0600000000000403 | exec `0x8bac30` / ser `0xb0d380` / h 0xa0dbd0 | u8 | Removed from queue [UI.RecvNotice_RemovedFromQueue] | no |
| `0x20e2` | event | Upgrade / object IID (player 0x02..01 or entity) | exec `0x8c0ab0` / ser `0x847e80` / h 0xaaabf0 | u8 0 \| {u32 QueueKey{u32 did,u32 flags}} \| {u32 u64 u32 StringInfo wstr u32 {cint u32}} | Upgrade: current upgrades + power graph values [Upgrade.RecvNotice_UpdateCurrentUpgrades, Upgrade.RecvNotice_UpdatePowerGraphValues] | no |
| `0x20e7` | event | Agent obj+0x84 / object IID (player 0x02..01 or entity) | exec `0x8aa300` / ser `0x8495f0` / h 0xaa0f20 | u8 0 \| {{u32 u32} {u32 {u64 Handle{u32,u64} u32 {u32 {u32}}}}} \| {u32 {u32 u32 {u32 {u64 Handle{u32,u64} u32 {u32 {u32}}}}}} | Agent component obj+0x84: update entries (?) | no |
| `0x20e8` | event | Agent obj+0x84 / object IID (player 0x02..01 or entity) | exec `0x8aa260` / ser `0x83f1d0` / h 0xaa0ef0 | u8 0 \| u32 \| Handle{u32,u64} | Agent component obj+0x84: u32 + handle (?) | no |
| `0x20e9` | event | StatusIcon / object IID (player 0x02..01 or entity) | exec `0x8bdc30` / ser `0x8402e0` / h 0xab38d0 | u8 0 \| u64 \| Handle{u32,u64} \| u8 | StatusIcon: remove status icon [UI.RecvNotice_RemoveSkillStackCountString, StatusIcon.RecvNotice_RemoveStatusIcon] | no |
| `0x20ec` | event | Contacts / player system 0x0600000000000403 | exec `0x8ac2f0` / ser `0x846d10` / h 0xa46bb0 | u8 0 \| {u32 {u64 u64 wstr u64 wstr wstr u32 u8 u32 u32 u32 u32 u32 u32 u32 wstr u32}} | Contacts: account icon changed [Contacts.RecvNotice_UI_NotifyContactAccountIconChanged] | no |
| `0x20ed` | event | Character/account / player system 0x0600000000000403 | exec `0x8ab100` / ser `0x83bcf0` / h 0xa833d0 | u8 0 \| {{u32 {u32 {u32 u32 u32 u8 u32}}} {u8 cint {u32 {u32 u32 u32 u32 u32 u32 u32 u32 u8 u32 StringInfo}}}} | Champion data [Character.RecvNotice_MasterCharacterListReceived, UI.RecvNotice_DisplayDialogText, ConnectionManager.RecvNotice_UpdateConnectionState] | yes |
| `0x20f0` | event | Agent obj+0x84 / object IID (player 0x02..01 or entity) | exec `0x8aa1c0` / ser `0x83bb10` / h 0xaa0ec0 | u8 0 \| u32 \| {u64 Handle{u32,u64} u32 {u32 {u32}}} \| u32 | Agent component obj+0x84: u32, {u64, handle, u32, list}, u32 (?) | no |
| `0x20f3` | event | Matchmaking / player system 0x0600000000000403 | exec `0x8ba600` / ser `0x839500` / h 0xa0dc50 | u8 0 \| u32 | Barred from matching [UI.RecvNotice_BarredFromMatching] | no |
| `0x20f5` | event | Cinematic/HUD / object IID (player 0x02..01 or entity) | exec `0x8ac050` / ser `0x83bdb0` / h 0xa9d140 | u8 0 \| {u32 u32} | Play cinematic [UI.RecvNotice_UpdateHUDVisibility] | yes |
| `0x20f7` | event | Upgrade / object IID (player 0x02..01 or entity) | exec `0x8c04f0` / ser `0x839bd0` / h 0x132c5c0 | u8 0 \| u64 \| u32 \| u64 | Same layout as 0x20F8 (u64 u32 f64) - no-op handler in this build | no |
| `0x20f8` | event | Skill HUD / object IID (player 0x02..01 or entity) | exec `0x8bc7c0` / ser `0x839bd0` / h 0xa0e320 | u8 0 \| u64 \| u32 \| u64 | Skill cooldown [UI.RecvNotice_StartSkillCooldown] | yes |
| `0x20f9` | event | Skill HUD / object IID (player 0x02..01 or entity) | exec `0x8bc0f0` / ser `0x839550` / h 0xa2a1b0 | u8 0 \| u64 \| u32 \| u8 | Raise skill availability event 0x100000B6/B7 on agent (slot, bool) | no |
| `0x20fa` | event | Matchmaking / player system 0x0600000000000403 | exec `0x8ba700` / ser `0x68f240` / h 0xa15550 | u8 0 \| u32 \| u32 | Match found [UI.RecvNotice_FoundMatch] | yes |
| `0x20ff` | event | Encounter / player system 0x0600000000000403 | exec `0x8b5610` / ser `0x846eb0` / h 0xa734d0 | u8 0 \| list<u32> \| list<u32> \| {u32 {cint,u8}} \| list<u32> | Encounter info update [Encounter.RecvNotice_MasterEncounterListReceived, Encounter.RecvNotice_ResetMapSelectionList, ConnectionManager.RecvNotice_UpdateConnectionState] | no |
| `0x2101` | event | Matchmaking / player system 0x0600000000000403 | exec `0x8baba0` / ser `0x845ac0` / h 0xa740d0 | u8 0 \| u32 \| u32 \| list<u32> \| list<u32> \| u32 \| u32 | Queue eligibility [UI.RecvNotice_QueueEligibility] | no |
| `0x2103` | event | CustomMatch / player system 0x0600000000000403 | exec `0x8afa90` / ser `0x83f690` / h 0xa13950 | u8 0 \| u32 \| u8 | CustomMatch: draft mode [CustomMatch.RecvNotice_UI_CustomMatch_SetDraftMode] | no |
| `0x2104` | event | Character/account / player system 0x0600000000000403 | exec `0x8aadb0` / ser `0x849680` / h 0xa7e0a0 | u8 0 \| u32 \| u32 \| StringInfo \| u32 \| u32 \| u32 \| u32 \| u32 \| u32 \| u32 \| u32 \| {u8 cint {u32 {u32 u32 u32 u64 u64}}} \| list<u32> \| list<u32> \| list<u32> \| {{u32 u8}} \| list<u32> \| list<u32> \| u32 \| u8 | Character level / XP [Character.RecvNotice_SendAccountEndOfMatchCharacterLevelAndXP, Character.RecvNotice_SendAccountEndOfMatchAccoladesEarned, Character.RecvNotice_Ribbon_CharacterLevelChanged] | yes |
| `0x2105` | event | engine static / object IID (player 0x02..01 or entity) | exec `0xab7720` / ser `0x996170` / h 0x634f90,0x6575e0 | u8 0 [trace stopped early] | Static-registered event (empty/odd body) (?) | no |
| `0x2107` | event | Amplifier / player system 0x0600000000000403 | exec `0x8aa140` / ser `0x847870` / h 0xa57510 | u8 0 \| {u32 {u64 u32 {cint,u8} u32}} | Amplifier: contextual data [Amplifier.RecvNotice_NotifyContextualAmplifierData] | no |
| `0x2109` | event | CustomMatch / player system 0x0600000000000403 | exec `0x8afa10` / ser `0x839500` / h 0xa0c760 | u8 0 \| u32 | CustomMatch: set encounter [CustomMatch.RecvNotice_UI_CustomMatch_SetEncounter] | no |
| `0x210a` | event | GM_UI / player system 0x0600000000000403 | exec `0x8be990` / ser `0x83f090` / h 0xac86f0 | u8 0 \| u32 \| u32 \| u32 | UI: display dialog text (u32 ids) [UI.RecvNotice_DisplayDialogText] | no |
| `0x210b` | event | Matchmaking / player system 0x0600000000000403 | exec `0x8ba820` / ser `0xb0d380` / h 0xa818e0 | u8 | Match/queue error -> leave (dialog text, removed from queue) [UI.RecvNotice_RemovedFromQueue, UI.RecvNotice_PendingMatchFailure, UI.RecvNotice_DisplayDialogText] | no |
| `0x210c` | event | Contextual store / player system 0x0600000000000403 | exec `0x8af7a0` / ser `0x839dd0` / h 0xa359b0 | u8 0 \| u64 | Contextual purchase success [Contextual.RecvNotice_PurchaseContextualItemSuccess] | no |
| `0x210d` | event | Contextual store / player system 0x0600000000000403 | exec `0x8af6a0` / ser `0x444b70` / h 0xa35920 | u8 0 \| u64 \| u32 | Contextual purchase error [Contextual.RecvNotice_PurchaseContextualItemError] | no |
| `0x210f` | event | Contextual store / player system 0x0600000000000403 | exec `0x8af720` / ser `0x846520` / h 0xa35a30 | u8 0 \| u64 \| u32 \| {u64 u32 {cint,u8} u32 {cint,u8} u32} | Contextual purchase price changed [Contextual.RecvNotice_PurchasePriceChanged] | no |
| `0x2115` | event | Character/account / player system 0x0600000000000403 | exec `0x8aad20` / ser `0x846460` / h 0xa57000 | u8 0 \| {u32 {u64 u8 u32 u64 u64 u64 u64 u64 u64 u64 u64 u64 u64 u64 u64 u64 u64 u32 u32 u64 u64 u64 u64 u64 u64 u32 u64 u64 u64 u64 u64 u64 u64 u64 u32 u64 u64 u64 u64 u64 u64 u32 StringInfo StringInfo u64 u64 u64 u64 u64 u64 u64 u64 u64 u64 u64 u64 u64 u64 u64 u64 u64 u64 u64 u64 u64 u32 u32}} | Account encounter stats [Character.RecvNotice_SendAccountEncounterStats] | no |
| `0x211f` | event | Achievement / player system 0x0600000000000403 | exec `0x8a9c30` / ser `0x8495a0` / h 0xa8b7f0 | u8 0 \| {u8 cint {u32 {u32 u32 u64 {u32 {u32 u32 u32 u32 u64 u8}}}}} | Pending achievement notifications [Achievement.RecvNotice_AllPendingAchivementBanners] | yes |
| `0x2120` | event | Achievement / player system 0x0600000000000403 | exec `0x8a9bb0` / ser `0x849540` / h 0xa870e0 | u8 0 \| {u8 cint {u32 {u32 u32 u64 {u32 {u32 u32 u32 u32 u64 u8}}}}} \| list<u32> | Achievement progress [Achievement.RecvNotice_SetAchievementObjectiveData, Achievement.RecvNotice_SetDeprecatedAchievements, UI.RecvNotice_ProtectorAdvancementStatus] | yes |
| `0x2123` | event | StatusIcon / object IID (player 0x02..01 or entity) | exec `0x8b2410` / ser `0x8490f0` / h 0xa9f030 | u8 0 \| u64 \| Handle{u32,u64} \| u32 \| u32 \| {u8 cint {u32 u32}} \| {u8 cint {u32 u32}} | StatusIcon component obj+0xc0 vt+0x5c (tooltip data) (?) | no |
| `0x2125` | event | Character/account / player system 0x0600000000000403 | exec `0x8ab080` / ser `0x846680` / h 0xa7ebb0 | u8 0 \| {u32 {u32 u32 u32 u32 u32 u32 u64 u32 StringInfo}} | Pending reward sets [Character.RecvNotice_RewardSetsData] | yes |
| `0x2126` | event | StatusIcon / object IID (player 0x02..01 or entity) | exec `0x8b24d0` / ser `0x849200` / h 0xa9f080 | u8 0 \| u64 \| u32 \| u32 \| {u8 cint {u32 u32}} \| {u8 cint {u32 u32}} | StatusIcon component obj+0xc0 vt+0x58 (?) | no |
| `0x2127` | event | StatusIcon / object IID (player 0x02..01 or entity) | exec `0x8be870` / ser `0x83f4d0` / h 0xab15d0 | u8 0 \| u64 \| Handle{u32,u64} | StatusIcon: update tooltip (variant) [StatusIcon.RecvNotice_UpdateStatusIconTooltip] | no |
| `0x2129` | event | StatusIcon / object IID (player 0x02..01 or entity) | exec `0x8b2370` / ser `0x83faa0` / h 0xa9f110 | u8 0 \| u64 \| u32 \| u32 | StatusIcon component obj+0xc0 vt+0x50 (u64 u32 u32) (?) | no |
| `0x212a` | event | StatusIcon / object IID (player 0x02..01 or entity) | exec `0x8b22c0` / ser `0x83f4d0` / h 0xa9f0d0 | u8 0 \| u64 \| Handle{u32,u64} | StatusIcon component obj+0xc0 vt+0x54 (handle) (?) | no |
| `0x212b` | event | Upgrade / object IID (player 0x02..01 or entity) | exec `0x8c0460` / ser `0x845df0` / h 0xa9ffd0 | u8 0 \| list<u32> | Upgrade component obj+0xa4 vt+0x54 (u32 list) (?) | no |
| `0x2134` | event | Chat / player system 0x0600000000000403 | exec `0x8abda0` / ser `0x8478a0` / h 0xa21f20 | u8 0 \| {u32 wstr} | Player system list (0xa21f20, compares names) (?) | no |
| `0x2135` | event | Chat / player system 0x0600000000000403 | exec `0x8abd20` / ser `0x845280` / h 0xa0ba80 | u8 0 \| StringInfo \| list<u64> | Chat: member list [Chat.RecvNotice_UpdatedMemberList] | no |
| `0x2137` | event | MapManager notes 2 / object IID (player 0x02..01 or entity) | exec `0x8b72c0` / ser `0x83fc20` / h 0xa8eb60 | u8 0 \| u64 \| {u32 u32 u64 u32} | MapManager: remove map note [MapManager.RecvNotice_RemoveMapNote] | no |
| `0x213d` | event | Encounter / object IID (player 0x02..01 or entity) | exec `0x8b2c50` / ser `0x83f5d0` / h 0xa368b0 | u8 0 \| u32 \| u32 \| u32 \| u32 | HUD element event [UI.RecvNotice_NotifyHUDElement] | yes |
| `0x213e` | event | Encounter / object IID (player 0x02..01 or entity) | exec `0x8b27d0` / ser `0x845500` / h 0xa5a7b0 | u8 0 \| {u32 {u32 u32 u32 u32}} | HUD: batch HUD element events [UI.RecvNotice_BatchNotifyHUDElements] | no |
| `0x2142` | event | Dialog / object IID (player 0x02..01 or entity) | exec `0x8b1fa0` / ser `0x8455e0` / h 0xa58e00 | u8 0 \| list<u32> \| u8 | Dialog: queue/allow list (u32 list, u8) (0xa475c0) (?) | no |
| `0x2143` | event | Dialog / object IID (player 0x02..01 or entity) | exec `0x8b1f10` / ser `0x839720` / h 0xa58dd0 | u8 0 \| u8 | Dialog: flag u8 (0xa475c0) (?) | no |
| `0x214b` | event | Encounter / player system 0x0600000000000403 | exec `0x8b2860` / ser `0x845530` / h 0xa35f90 | u8 0 \| list<u32> \| QueueKey{u32 did,u32 flags} | Completed encounters + last map played [Encounter.RecvNotice_UI_CompletedEncounters, Encounter.RecvNotice_UI_LastMapPlayed] | yes |
| `0x214c` | event | Grouping / player system 0x0600000000000403 | exec `0x8b62a0` / ser `0xb0d380` / h 0xa0d230 | u8 | Grouping: invite cancelled [Grouping.RecvNotice_GroupInviteCanceled] | no |
| `0x2150` | event | Cinematic/HUD / object IID (player 0x02..01 or entity) | exec `0x8abfc0` / ser `0x839500` / h 0xa9cca0 | u8 0 \| u32 | UI: HUD visibility [UI.RecvNotice_UpdateHUDVisibility] | no |
| `0x2151` | event | CustomMatch / player system 0x0600000000000403 | exec `0x8b0080` / ser `0x83be40` / h 0xa0c780 | u8 0 \| u32 \| StringInfo \| StringInfo | CustomMatch: team name [CustomMatch.RecvNotice_UI_CustomMatch_SetTeamName] | no |
| `0x2154` | event | Character/account / player system 0x0600000000000403 | exec `0x8ab190` / ser `0x68f240` / h 0xa571a0 | u8 0 \| u32 \| u32 | Protector icon slot [UI.RecvNotice_SendHeaderNameAndProtectorIcons] | no (documented) |
| `0x2157` | event | Effects (agent obj+0x8C) / object IID (player 0x02..01 or entity) | exec `0x8b6960` / ser `0x849ab0` / h 0xaa1c90 | u8 0 \| u64 \| {u32} \| u32 | Effects: raise events on matching effects (same as 0x2063) | no |
| `0x2158` | event | Effects (agent obj+0x8C) / object IID (player 0x02..01 or entity) | exec `0x8b6780` / ser `0x849a10` / h 0xaa1c50 | u8 0 \| u64 \| {u32} | Effects: raise events on all effects (same as 0x41) | no |
| `0x2159` | event | Encounter / object IID (player 0x02..01 or entity) | exec `0x8b2b30` / ser `0x845580` / h 0xa1cac0 | u8 0 \| list<u64> \| u32 | Encounter: root+0x38 list of IIDs + u32 (0xa15680) (?) | no |
| `0x215a` | event | Encounter / object IID (player 0x02..01 or entity) | exec `0x8b2740` / ser `0x847980` / h 0xa5cf20 | u8 0 \| {u32 {u32 u32 list<u64>}} | Encounter: root+0x38 list (0xa55690) (?) | no |
| `0x215c` | event | ViewMatch / object IID (player 0x02..01 or entity) | exec `0x8c1e40` / ser `0x845df0` / h 0xac0d90 | u8 0 \| list<u32> | ViewMatch: dampener counts [ViewMatch.RecvNotice_ViewMatch_UpdateDampenerCounts] | no |
| `0x215d` | event | Account settings / player system 0x0600000000000403 | exec `0x8bae30` / ser `0x83f690` / h 0xa76b80 | u8 0 \| u32 \| u8 | Account flags [UI.RecvNotice_ProtectorAdvancementStatus] | yes |
| `0x215f` | event | Player-object gameplay / object IID (player 0x02..01 or entity) | exec `0x8b5cf0` / ser `0x83fa20` / h 0xa1a570 | u8 0 \| Handle{u32,u64} \| u8 | Root+0x90: handle + u8 (0x8728e0) (?) | no |
| `0x2161` | event | Contacts / player system 0x0600000000000403 | exec `0x8ac8f0` / ser `0x847900` / h 0xa46a70 | u8 0 \| {u32 {u64 u64 wstr u64 wstr wstr u32 u8 u32 u32 u32 u32 u32 u32 u32 wstr u32}} \| {u32 {u64 wstr}} | Contacts: two lists (?) | no |
| `0x216a` | event | Account settings / player system 0x0600000000000403 | exec `0x8baeb0` / ser `0x849c00` / h 0xa76bb0 | u8 0 \| {u8 cint {{cint,u8} PropValue}} [trace stopped early] | Server preferences [UI.RecvNotice_ProtectorAdvancementStatus] | yes |
| `0x2171` | event | Training / player system 0x0600000000000403 | exec `0x8c3f60` / ser `0x8455e0` / h 0xadb230,0xa8de40 | u8 0 \| list<u32> \| u8 | Training: load control (encounter DIDs + lesson) [UI.RecvNotice_UpdateTrainingFloatyText] | no |
| `0x2172` | event | GM_UI / object IID (player 0x02..01 or entity) | exec `0x8bea10` / ser `0x83c530` / h 0xa177e0 | u8 0 \| u64 \| u8 \| u32 \| u32 \| u32 \| StringInfo | UI: training floaty text [UI.RecvNotice_UpdateTrainingFloatyText] | no |
| `0x2173` | event | Encounter / object IID (player 0x02..01 or entity) | exec `0x8b2a20` / ser `0x839500` / h 0xa7a930 | u8 0 \| u32 | Encounter: training floaty text trigger (u32) [UI.RecvNotice_UpdateTrainingFloatyText] | no |
| `0x2174` | event | Training / object IID (player 0x02..01 or entity) | exec `0x8b7230` / ser `0x839500` / h 0xa93df0 | u8 0 \| u32 | Training: lesson event u32 (local player) | no |
| `0x2179` | event | MapManager / object IID (player 0x02..01 or entity) | exec `0x8ba420` / ser `0x845a70` / h 0xa5c350 | u8 0 \| {{u32 u8}} \| u32 | MapManager: minimap revealed cells (list of byte x,y) + flags -> property 0x7EC rect (fog of war) | no |
| `0x217a` | event | Character/account / object IID (player 0x02..01 or entity) | exec `0x8ab2e0` / ser `0x845170` / h 0xa67110 | u8 0 \| u64 \| u32 \| u32 \| u64 \| u32 \| list<u32> | Character: (u64, u32, u32, u64, u32, list) (0xa67110) (?) | no |
| `0x217c` | event | CustomMatch / player system 0x0600000000000403 | exec `0x8b0000` / ser `0x444b70` / h 0xa0c5e0 | u8 0 \| u64 \| u32 | CustomMatch: protector icon [CustomMatch.RecvNotice_UI_CustomMatch_UpdateProtectorIcon] | no |
| `0x217d` | event | Grouping / player system 0x0600000000000403 | exec `0x8b6110` / ser `0x444b70` / h 0xa0d210 | u8 0 \| u64 \| u32 | Grouping: protector icon [Grouping.RecvNotice_UI_Grouping_UpdateProtectorIcon] | no |
| `0x217f` | event | Skill HUD / object IID (player 0x02..01 or entity) | exec `0x8bbf10` / ser `0x83f690` / h 0xa5d070 | u8 0 \| u32 \| u8 | MapManager: targeting ring (u32, u8) [MapManager.RecvNotice_ShowMiniMapTargetingRing] | no |
| `0x2180` | event | Skill HUD / object IID (player 0x02..01 or entity) | exec `0x8bbdf0` / ser `0x839500` / h 0xa6d800 | u8 0 \| u32 | MapManager: targeting ring (u32) [MapManager.RecvNotice_ShowMiniMapTargetingRing] | no |
| `0x2183` | event | Chat / object IID (player 0x02..01 or entity) | exec `0x8abf20` / ser `0x83bd10` / h 0xa5cf40 | u8 0 \| StringInfo \| StringInfo \| u32 \| u32 | Chat: (StringInfo, StringInfo, u32, u32) (0xa4d140) (?) | no |
| `0x2186` | event | Character/account / player system 0x0600000000000403 | exec `0x8aac00` / ser `0x846410` / h 0xa3f2d0 | u8 0 \| {u32 {u32 u32 u8 u32 u32 StringInfo}} \| {u32 {u32 u32 u8 u32 u32 StringInfo}} | Best map / champion accolades [Character.RecvNotice_SendBestMapAccolades, Character.RecvNotice_SendBestChampAccolades] | no |
| `0x2187` | event | Skill HUD / object IID (player 0x02..01 or entity) | exec `0x8bbe80` / ser `0x839500` / h 0xa39f90 | u8 0 \| u32 | Skill HUD: enable skill button (variant) [Skill.RecvNotice_EnableSkillButton] | no |
| `0x2188` | event | Character/account / player system 0x0600000000000403 | exec `0x8ab220` / ser `0x845000` / h 0xa61da0 | u8 0 \| u32 \| u8 \| u32 \| StringInfo \| list<u32> \| list<u32> \| list<u32> \| {{u32 u8}} \| list<u32> \| list<u32> | Accolades [Character.RecvNotice_SendAccountEndOfMatchAccoladesEarned] | yes |
| `0x2189` | event | MapManager / object IID (player 0x02..01 or entity) | exec `0x8b9d10` / ser `0x839dd0` / h 0xa73e80 | u8 0 \| u64 | MapManager: teleport effects start/stop (u64) [MapManager.RecvNotice_UI_StopTeleportEffects, MapManager.RecvNotice_UI_StartTeleportEffects] | no |
| `0x218a` | event | MapManager / object IID (player 0x02..01 or entity) | exec `0x8b9c80` / ser `0x839dd0` / h 0xa846d0 | u8 0 \| u64 | MapManager: teleport effects start/stop (u64) [MapManager.RecvNotice_UI_StopTeleportEffects, MapManager.RecvNotice_UI_StartTeleportEffects] | no |
| `0x218b` | event | Account settings / player system 0x0600000000000403 | exec `0x8baf30` / ser `0x83c340` / h 0xa839b0 | u8 0 \| {{u8 cint {u32 PropTable}}} [trace stopped early] | Account tables (game settings) [UI.RecvNotice_ProtectorAdvancementStatus] | yes |
| `0x218d` | event | Matchmaking / player system 0x0600000000000403 | exec `0x8ba680` / ser `0x83c2e0` / h 0xa155f0 | u8 0 \| u32 \| StringInfo | Find match failure [UI.RecvNotice_FindMatchFailure] | no |
| `0x218e` | event | Matchmaking / player system 0x0600000000000403 | exec `0x8ba910` / ser `0x839930` / h 0xa0dc20 | u8 0 \| u32 \| u32 | Matchmaking update interval [UI.RecvNotice_Matchmaking_NewUpdateInterval] | no |
| `0x218f` | event | Matchmaking / player system 0x0600000000000403 | exec `0x8ba890` / ser `0x8466b0` / h 0xa38500 | u8 0 \| {u32 QueueKey{u32 did,u32 flags}} \| {u32 list<u32>} | Queue wait times [UI.RecvNotice_QueueWaitTimesUpdated] | no |
| `0x2190` | event | Character/account / player system 0x0600000000000403 | exec `0x8aaa00` / ser `0x83f230` / h 0xa57200 | u8 0 \| u32 \| u32 \| u32 \| u32 \| u32 \| u32 \| u32 \| StringInfo \| StringInfo \| u32 \| u8 | Header + protector icons [UI.RecvNotice_SendHeaderNameAndProtectorIcons] | yes |
| `0x2191` | event | Matchmaking / player system 0x0600000000000403 | exec `0x8baca0` / ser `0xb0d380` / h 0xa12fd0 | u8 | Player system, empty (resets advancement view 0xa12fd0) (?) | no |
| `0x2197` | event | LoginReward / player system 0x0600000000000403 | exec `0x8b9450` / ser `0x846680` / h 0xa81520 | u8 0 \| {u32 {u32 u32 u32 u32 u32 u32 u64 u32 StringInfo}} | Reward sets data (variant) [Character.RecvNotice_RewardSetsData] | no |
| `0x2198` | event | Player-object gameplay / object IID (player 0x02..01 or entity) | exec `0x8b5f50` / ser `0x839790` / h 0xa1a540 | u8 0 \| u64 \| u8 | Root+0x90 counter (u64, u8) (same family as 0x2044) (?) | no |
| `0x219c` | event | Contacts / player system 0x0600000000000403 | exec `0x8ac9f0` / ser `0x847950` / h 0xa1b0e0 | u8 0 \| {u32 {u64 wstr u64}} | Contacts: invitations [Contacts.RecvNotice_UI_NotifyContactOfInvitations] | no |
| `0x219d` | event | LoginReward / player system 0x0600000000000403 | exec `0x8b94d0` / ser `0xb0d380` / h 0xa0d570 | u8 | Login reward: none eligible [LoginReward.RecvNotice_UI_NoEligibleLoginReward] | no |
| `0x219e` | event | Matchmaking / player system 0x0600000000000403 | exec `0x8bad90` / ser `0x83feb0` / h 0xa37dc0 | u8 0 \| u32 \| u32 \| u32 \| u32 \| u32 \| u32 \| u32 \| u32 \| u32 \| u32 | Account standings [UI.RecvNotice_UI_DeliverAccountStandingsData] | yes |
| `0x219f` | event | Matchmaking / player system 0x0600000000000403 | exec `0x8ba560` / ser `0x848b80` / h 0xa5c840 | u8 0 \| {list<u32> list<u32> list<u32> list<u32> list<u32> list<u32> list<u32> list<u32> list<u32> {u32 {u32 u32 u32}}} \| u32 \| u32 \| u32 \| u32 \| u32 | Standings [UI.RecvNotice_UI_DeliverAccountStandingsData] | yes |
| `0x21a0` | event | Matchmaking / player system 0x0600000000000403 | exec `0x8bad10` / ser `0x68f240` / h 0xa37d60 | u8 0 \| u32 \| u32 | Player system u32 u32 (0xa37d60) (?) | no |
| `0x21a2` | event | Matchmaking / player system 0x0600000000000403 | exec `0x8bab20` / ser `0x848e70` / h 0xa74100 | u8 0 \| {u32 {u64 wstr u32 u32 u32 u32 u32}} \| u32 | Leaderboard (regional/friends) [UI.RecvNotice_DeliverRegionalLeaderboard, UI.RecvNotice_DeliverFriendsLeaderboard] | no |
| `0x21a3` | event | Matchmaking / player system 0x0600000000000403 | exec `0x8baaa0` / ser `0x848e70` / h 0xa74140 | u8 0 \| {u32 {u64 wstr u32 u32 u32 u32 u32}} \| u32 | Leaderboard (regional/friends) variant [UI.RecvNotice_DeliverRegionalLeaderboard, UI.RecvNotice_DeliverFriendsLeaderboard] | no |
| `0x21a6` | event | Achievement / player system 0x0600000000000403 | exec `0x8a9cb0` / ser `0x83f090` / h 0xa57330 | u8 0 \| u32 \| u32 \| u32 | Achievement objective data / deprecated achievements [Achievement.RecvNotice_SetAchievementObjectiveData, Achievement.RecvNotice_SetDeprecatedAchievements] | no |
| `0x2000003d` | event | engine static / object IID (player 0x02..01 or entity) | exec `0xa313f0` / ser `0x874730` / h 0xaa0460 | u8 0 \| {u32 {u32 u32 u32 u32 u32 vec3 u8 u64 u32 u8 u32 u32 u32 u32 u32}} | Agent component obj+0xbc query (u32 list) (?) | no |

## 5. Notices that can arrive in event 0x2 (44 with a network reader)

Sent as event `0x2` to the target object (usually the local player `0x0200000000000001`): `u8 0 | u32 notice id | u32 blob length | blob`. The blob has no base byte (packed stream).

| id | kind | dest | reader / deliver | blob layout | meaning | used |
|---|---|---|---|---|---|---|
| `0x100004f7` | notice (event 0x2) | object IID or player system | reader `0x9244a0` / deliver 0x90e4c0 | u32 | u32 (registration group 0x90e4c0) (?) | no |
| `0x10000118` | notice (event 0x2) | object IID or player system | reader `0x92dc00` / deliver 0x910830 | u8 \| Position | u8 + Position: position-carrying notice (MapManager-side group 0x910830) (?) | no |
| `0x10000192` | notice (event 0x2) | object IID or player system | reader `0x92dcd0` / deliver 0x9108f0 | u32 \| {u8 u8 u64 u64} | u32 + {u8,u8,u64,u64} (group 0x9108f0) (?) | no |
| `0x10000229` | notice (event 0x2) | object IID or player system | reader `0x92dd50` / deliver 0x9109b0 | u8 \| Handle{u32,u64} | u8 + handle {u32,u64} (group 0x9109b0) (?) | no |
| `0x100004a5` | notice (event 0x2) | object IID or player system | reader `0x9560d0` / deliver 0x91e780 | u32 | u32 (group 0x91e780, same block as tutorial hint) (?) | no |
| `0x1000027f` | notice (event 0x2) | object IID or player system | reader `0x956130` / deliver 0x91e840 | u32 \| u8 | Tutorial hint: u32 hint id / u8 force open | yes |
| `0x10000288` | notice (event 0x2) | object IID or player system | reader `0x9561f0` / deliver 0x91e900 | list<u32> | u32 list (same block as tutorial hint) (?) | no |
| `0x100003d5` | notice (event 0x2) | object IID or player system | reader `0x955e30` / deliver 0x91e2e0 | u32 | u32 (group with event 0x20DE) (?) | no |
| `0x100003d7` | notice (event 0x2) | object IID or player system | reader `0x955f90` / deliver 0x91e3a0 | u32 | u32 (group with event 0x20DE) (?) | no |
| `0x100003d6` | notice (event 0x2) | object IID or player system | reader `0x955ff0` / deliver 0x91e510 | list<u32> | u32 list (group with event 0x20DE) (?) | no |
| `0x10000090` | notice (event 0x2) | object IID or player system | reader `0x8c48c0` / deliver 0x8beac0 | u32 \| u64 | GM_UI.RecvNotice_DefeatStatusUpdated (u32 status, u64 iid) - defeat/respawn timer | no |
| `0x100000bc` | notice (event 0x2) | object IID or player system | reader `0x956580` / deliver 0x91edb0 | u64 \| u32 \| u32 \| u64 | GM_UI.RecvNotice_DefeatStatusUpdatedForEntity (u64 iid, u32, u32, f64 time) | no |
| `0x10000059` | notice (event 0x2) | object IID or player system | reader `0x9567d0` / deliver 0x91f3c0 | u32 \| u32 \| u32 \| u32 | GM_UI group, 4 u32 (0x91f3c0) (?) | no |
| `0x1000004a` | notice (event 0x2) | object IID or player system | reader `0x9568b0` / deliver 0x91f3c0 | (empty) | GM_UI group, empty (0x91f3c0) (?) | no |
| `0x100000b6` | notice (event 0x2) | object IID or player system | reader `0x956a30` / deliver 0x91f6e0 | (empty) | GM_UI group, empty (0x91f6e0) (?) | no |
| `0x100000ba` | notice (event 0x2) | object IID or player system | reader `0x8c4960` / deliver 0x8bf180 | u64 \| u32 | GM_UI.RecvNotice_PauseDefeatStatusTimerForEntity (u64 iid, u32) | no |
| `0x10000076` | notice (event 0x2) | object IID or player system | reader `0x8c4a00` / deliver 0x8bf4f0 | u32 | GM_UI.RecvNotice_TimerClockSync (u32) | no |
| `0x1000015a` | notice (event 0x2) | object IID or player system | reader `0x8c47e0` / deliver 0x8bc9b0 | u32 \| u32 \| u8 | GM_Skill.RecvNotice_UpdateSkillUIOverlay (u32, u32, u8) | no |
| `0x10000414` | notice (event 0x2) | object IID or player system | reader `0x95b140` / deliver 0x9220f0 | u64 \| u32 | Upgrade group: u64 + u32 (0x9220f0) (?) | no |
| `0x10000364` | notice (event 0x2) | object IID or player system | reader `0x95b1f0` / deliver 0x9221b0 | u64 \| u32 \| u32 \| u8 | Upgrade group: u64 + u32 + u32 + u8 (0x9221b0) (?) | no |
| `0x100004d6` | notice (event 0x2) | object IID or player system | reader `0x95f970` / deliver 0x923100 | u64 \| u32 | Upgrade group: u64 + u32 (0x923100) (?) | no |
| `0x100002ec` | notice (event 0x2) | object IID or player system | reader `0x8c2f70` / deliver 0x8aa720 | (empty) | GM_Character.RecvNotice_ClearAnnouncement (empty) | no (documented) |
| `0x100002eb` | notice (event 0x2) | object IID or player system | reader `0x8c2fa0` / deliver 0x8ab390 | StringInfo \| u32 \| u32 \| u32 \| u32 \| u32 \| u8 | GM_Character.RecvNotice_ShowAnnouncement (StringInfo text, u32 billboard type, u32 src icon, u32 tgt icon, i32 src team, i32 tgt team, u8) | yes |
| `0x1000021c` | notice (event 0x2) | object IID or player system | reader `0x9326c0` / deliver 0x9121e0 | list<u64> \| list<u32> \| list<u32> \| StringInfo \| {u32 u32} \| {u32 u32} \| {u32 u32} \| {u32 u32} \| {u32 u32} \| list<u32> \| list<u32> \| list<u32> \| list<u32> \| list<u32> \| list<u32> \| list<u32> \| list<u32> \| list<u32> \| list<u32> \| list<u32> \| list<u32> \| list<u32> \| list<u32> \| list<u32> \| list<u32> \| list<u32> \| list<u32> \| list<u32> \| list<u32> \| list<u32> \| list<u32> \| list<u32> \| list<u32> \| list<u32> \| list<u32> \| list<u32> \| list<u32> \| {u32 StringInfo} \| {u32 StringInfo} \| {u32 StringInfo} \| {u32 StringInfo} \| {u32 u32} \| {u32 u32} \| list<u32> \| list<u32> \| u32 | Billboard/kill-feed style announcement: u64 list, two u32 lists, StringInfo, more (0x9121e0) (?) | no |
| `0x100002b2` | notice (event 0x2) | object IID or player system | reader `0x933570` / deliver 0x912390 | u64 \| list<u64> \| list<u32> \| list<u32> \| StringInfo \| {u32 u32} \| {u32 u32} \| {u32 u32} \| {u32 u32} \| {u32 u32} \| list<u32> \| list<u32> \| list<u32> \| list<u32> \| list<u32> \| list<u32> \| list<u32> \| list<u32> \| list<u32> \| list<u32> \| list<u32> \| list<u32> \| list<u32> \| list<u32> \| list<u32> \| list<u32> \| list<u32> \| list<u32> \| list<u32> \| list<u32> \| list<u32> \| list<u32> \| list<u32> \| list<u32> \| list<u32> \| list<u32> \| list<u32> \| list<u32> \| {u32 StringInfo} \| {u32 StringInfo} \| {u32 StringInfo} \| {u32 StringInfo} \| {u32 u32} \| {u32 u32} \| list<u32> \| list<u32> \| u32 | Same as 0x1000021C with a leading u64 (0x912390) (?) | no |
| `0x100002bc` | notice (event 0x2) | object IID or player system | reader `0x8c3130` / deliver 0x8ab800 | (empty) | GM_Character.RecvNotice_StopProcessingNewBillboards (empty) | no |
| `0x10000424` | notice (event 0x2) | object IID or player system | reader `0x941390` / deliver 0x916450 | {Handle{u32,u64} u32 u32 u32 u8 u32 u64 u8 {u32 {StringInfo StringInfo u32}}} \| u64 | AddTimelineBanner (Encounter group): banner desc + f64 | built, off |
| `0x100002ab` | notice (event 0x2) | object IID or player system | reader `0x941430` / deliver 0x916520 | {Handle{u32,u64} u32 u32 u32 u8 u32 u64 u8 {u32 {StringInfo StringInfo u32}}} \| {u32 {Handle{u32,u64} u32 u32 u32 u64}} \| u64 | Timeline banner variant (banner desc + list + f64) (?) | no |
| `0x100002ae` | notice (event 0x2) | object IID or player system | reader `0x941520` / deliver 0x9165f0 | {u32 {Handle{u32,u64} u32 u32 u32 u8 u32 u64 u8 {u32 {StringInfo StringInfo u32}}}} \| {u32 {Handle{u32,u64} u32 u32 u32 u64}} \| u64 | Timeline banners list (u32 n x desc) + list + f64 (?) | no |
| `0x100002af` | notice (event 0x2) | object IID or player system | reader `0x941620` / deliver 0x9166c0 | u64 | Timeline banners on (u64 iid) | built, off |
| `0x100002ac` | notice (event 0x2) | object IID or player system | reader `0x941690` / deliver 0x916780 | Handle{u32,u64} | Timeline banner remove by handle {u32,u64} (?) | no |
| `0x100002b1` | notice (event 0x2) | object IID or player system | reader `0x9416e0` / deliver 0x916840 | u64 | Timeline banners on, 2 (u64 iid) | built, off |
| `0x1000000e` | notice (event 0x2) | object IID or player system | reader `0x941750` / deliver 0x916900 | u32 \| u32 \| u32 \| u32 \| u32 | GM_Encounter.RecvNotice_NotifyMatchEnded (u32 winning team, u32 player team, f32 seconds, u32 tier, f32 target time) | yes |
| `0x100000ca` | notice (event 0x2) | object IID or player system | reader `0x9419a0` / deliver 0x916ec0 | u64 \| u64 | Encounter group: u64 + u64 (0x916ec0) (?) - probable kill/assist (killer, victim) | no |
| `0x100000cd` | notice (event 0x2) | object IID or player system | reader `0x941a50` / deliver 0x916f80 | u64 \| u64 | Encounter group: u64 + u64 (0x916f80) (?) | no |
| `0x10000205` | notice (event 0x2) | object IID or player system | reader `0x941b70` / deliver 0x9170d0 | (empty) | Encounter group, empty (0x9170d0) (?) | no |
| `0x10000109` | notice (event 0x2) | object IID or player system | reader `0x941d60` / deliver 0x9173c0 | u64 \| u64 \| u8 | GM_Encounter.RecvNotice_SetMatchTime (f64 start?, f64, u8) | no |
| `0x10000456` | notice (event 0x2) | object IID or player system | reader `0x941e60` / deliver 0x9177a0 | (empty) | GM_Encounter.RecvNotice_SurrenderVoteConcluded (empty) | no |
| `0x100004fb` | notice (event 0x2) | object IID or player system | reader `0x90b230` / deliver 0x8e1e80 | list<u32> \| list<u32> \| list<u32> | GM_Encounter.RecvNotice_UI_InitialTeamHealthUpdate (3 u32 lists) | no |
| `0x100000cb` | notice (event 0x2) | object IID or player system | reader `0x8c3d00` / deliver 0x8b4560 | u64 \| u64 \| StringInfo \| u32 \| u32 | GM_Encounter.RecvNotice_UI_PlayerJoined (u64, u64, StringInfo name, u32, u32) | no |
| `0x100000ce` | notice (event 0x2) | object IID or player system | reader `0x8c3e30` / deliver 0x8b4990 | u64 \| u64 \| StringInfo \| u32 \| u32 | GM_Encounter.RecvNotice_UI_PlayerLeft (u64, u64, StringInfo, u32, u32) | no |
| `0x10000134` | notice (event 0x2) | object IID or player system | reader `0x90b320` / deliver 0x8e9a10 | list<u32> \| list<u32> | GM_Encounter.RecvNotice_UI_UpdateTeamHealth (2 u32 lists) | no |
| `0x1000005b` | notice (event 0x2) | object IID or player system | reader `0x942a80` / deliver 0x917d90 | {u32 {StringInfo u64 u64 u64 u32 u32 u32 u32 u32 u32 u32 u8}} | Encounter group: list of {StringInfo, 3 u64, 7 u32, u8} (0x917d90) (?) - scoreboard rows? | no |
| `0x10000455` | notice (event 0x2) | object IID or player system | reader `0x90b3d0` / deliver 0x8ea0b0 | {u32 u8} \| u32 \| u8 \| u32 \| u32 | GM_Encounter.RecvNotice_UpdateSurrenderData ({u32,u8}, u32, u8, u32, u32) | no |

## 6. Local-only notices (420, reader stub `0x11893c0`)

Registered but **cannot be delivered over the network** (descriptor slot 0 is the stub). They are C++/Flash/script notices; listed by registering function so they are not mistaken for server messages. Names come from the Flash call found next to the id, when there is one.

- reg `0x69d010` (8): `0x3e`, `0x42`, `0x63` (EM_WebBrowser.RecvNotice_OnLoadEnd), `0x89`, `0x92` (EM_UI.RecvNotice_ForceOnSized), `0xb8`, `0xba`, `0xbd`
- reg `0x878970` (8): `0x10000009`, `0x10000011`, `0x10000063`, `0x1000006a`, `0x1000009b`, `0x1000023c`, `0x10000302`, `0x10000423`
- reg `0x878ba0` (7): `0x100002cb`, `0x100002cc`, `0x100002cd`, `0x100002d9`, `0x100002ed`, `0x1000030b`, `0x100003db`
- reg `0x878d20` (1): `0x10000174`
- reg `0x879aa0` (5): `0x100003c8`, `0x100003ca`, `0x100003cc`, `0x100003cd`, `0x100003ce`
- reg `0x879c50` (19): `0x100001ca`, `0x100001cc`, `0x100001ce`, `0x100001cf`, `0x100001d3`, `0x100001f1`, `0x100001f6`, `0x100001fc`, `0x100001ff`, `0x1000026c`, `0x100002b7`, `0x100002d1`, `0x100002fb`, `0x100002fd`, `0x100002fe`, `0x1000038e`, `0x1000038f`, `0x10000485`, `0x10000489`
- reg `0x87a010` (102): `0x1000013a`, `0x1000013d`, `0x1000013e`, `0x1000013f`, `0x10000146`, `0x10000147`, `0x10000149`, `0x1000014a`, `0x10000163`, `0x1000017c`, `0x1000017d`, `0x1000017e`, `0x1000017f`, `0x10000180`, `0x10000181`, `0x10000182`, `0x10000183`, `0x100001bc`, `0x100001bd`, `0x100001c7`, `0x100001c8`, `0x10000214`, `0x10000215`, `0x10000254`, `0x10000255`, `0x10000256`, `0x10000257`, `0x10000258`, `0x10000259`, `0x10000266`, `0x10000267`, `0x10000268`, `0x10000269`, `0x1000026a`, `0x1000026b`, `0x100002f2`, `0x100002f3`, `0x100002f6`, `0x100002f7`, `0x10000305`, `0x10000306`, `0x10000307`, `0x10000308`, `0x1000035f`, `0x10000360`, `0x10000362`, `0x10000363`, `0x1000039c`, `0x1000039d`, `0x100003aa`, `0x100003ab`, `0x100003b2`, `0x100003b3`, `0x100003b4`, `0x100003b5`, `0x100003b6`, `0x100003b7`, `0x100003bb`, `0x100003bc`, `0x10000428`, `0x10000429`, `0x10000479`, `0x100004aa`, `0x100004ab`, `0x100004ac`, `0x100004ad`, `0x100004ae`, `0x100004af`, `0x100004b0`, `0x100004b1`, `0x100004b3`, `0x100004b4`, `0x100004b5`, `0x100004b6`, `0x100004b8`, `0x100004b9`, `0x100004bb`, `0x100004bc`, `0x100004bd`, `0x100004be`, `0x100004c2`, `0x100004c3`, `0x100004c5`, `0x100004c6`, `0x100004c7`, `0x100004c8`, `0x100004c9`, `0x100004cd`, `0x100004ce`, `0x100004cf`, `0x100004d0`, `0x100004d1`, `0x100004d2`, `0x100004d3`, `0x100004d8`, `0x100004d9`, `0x100004e2`, `0x100004e3`, `0x10000507`, `0x10000508`, `0x1000050e`, `0x1000050f`
- reg `0x87ade0` (1): `0x10000283`
- reg `0x88b5e0` (1): `0x10000202`
- reg `0x88bce0` (74): `0x10000020` (UI.RecvNotice_UIStateMachineEvent), `0x10000032`, `0x10000040`, `0x1000006d` (UI.RecvNotice_ToggleMainMenu), `0x10000078`, `0x10000079`, `0x100000bb`, `0x10000108`, `0x1000011c`, `0x1000011d`, `0x1000012a`, `0x10000141`, `0x1000015c`, `0x1000015d`, `0x1000022c`, `0x10000230`, `0x10000234`, `0x10000238`, `0x1000023f`, `0x10000240`, `0x10000241`, `0x10000242`, `0x1000025b`, `0x1000025c`, `0x1000025d`, `0x10000265` (UI.RecvNotice_ShowURLDialog), `0x10000279`, `0x10000287`, `0x10000294`, `0x1000029c`, `0x1000029e`, `0x1000029f`, `0x100002a0`, `0x100002e7`, `0x100003b1`, `0x100003ba`, `0x100003ea` (UI.RecvNotice_SetupSettingsButtons), `0x10000431`, `0x10000439`, `0x10000452`, `0x1000046a`, `0x10000473`, `0x10000476`, `0x10000477`, `0x1000048e`, `0x10000495`, `0x10000496`, `0x10000499`, `0x1000049a`, `0x1000049c`, `0x1000049d`, `0x1000049e`, `0x1000049f`, `0x100004bf`, `0x100004d7`, `0x100004da`, `0x100004e5`, `0x100004e9`, `0x100004ec`, `0x100004f4`, `0x100004fa`, `0x100004fe`, `0x10000501`, `0x10000503`, `0x10000517`, `0x10000520`, `0x10000522`, `0x10000523`, `0x10000524`, `0x10000526`, `0x10000527`, `0x1000052a`, `0x1000052c`, `0x1000052e`
- reg `0x8945f0` (3): `0x1000040d`, `0x1000040e`, `0x1000040f`
- reg `0x8bccd0` (5): `0x10000164`, `0x10000223`, `0x100002c7`, `0x1000030f`, `0x10000374`
- reg `0x8c31d0` (4): `0x10000208`, `0x1000022d`, `0x100003a5`, `0x100003a6`
- reg `0x8c3940` (6): `0x100003c4`, `0x100003c5`, `0x100003c6`, `0x10000447`, `0x1000044a`, `0x1000044d`
- reg `0x8c4070` (8): `0x100001b3`, `0x100001b5`, `0x100001b6`, `0x100001e3`, `0x100001e6`, `0x100001e7`, `0x100002f1`, `0x1000047b`
- reg `0x8c4b70` (25): `0x10000125`, `0x10000128`, `0x10000138`, `0x10000144`, `0x10000145`, `0x1000014b`, `0x1000014d`, `0x10000154`, `0x10000155`, `0x100001c3`, `0x100001ef`, `0x100001f7`, `0x10000271`, `0x10000278`, `0x100002b0`, `0x100002bd`, `0x100002d8`, `0x100002f8`, `0x100002f9`, `0x10000384`, `0x100003ff`, `0x1000042c`, `0x1000042d`, `0x10000462`, `0x10000468`
- reg `0x8c4fb0` (14): `0x10000236`, `0x10000237`, `0x100002be`, `0x100002c0`, `0x100002ce`, `0x100002cf`, `0x100002d6`, `0x100002db`, `0x100002dc`, `0x100002de`, `0x10000368`, `0x10000490`, `0x100004db`, `0x100004dc`
- reg `0x8ebd90` (7): `0x10000290`, `0x100002a3`, `0x10000381`, `0x100003c2`, `0x100003e0`, `0x100004a4`, `0x100004e0`
- reg `0x8f4640` (2): `0x1000050a`, `0x1000050b`
- reg `0x90bbf0` (10): `0x1000026e`, `0x1000026f`, `0x10000270`, `0x1000027e`, `0x1000028f`, `0x10000298`, `0x10000299`, `0x100003de`, `0x10000411`, `0x10000504`
- reg `0x90bda0` (13): `0x10000312`, `0x10000313`, `0x10000314`, `0x10000315`, `0x10000316`, `0x10000317`, `0x10000318`, `0x10000319`, `0x1000031a`, `0x10000335`, `0x10000336`, `0x10000512`, `0x10000513`
- reg `0x90c6c0` (3): `0x10000064`, `0x10000088`, `0x10000151`
- reg `0x90c840` (11): `0x100003c0`, `0x100003c1`, `0x100003cf`, `0x100003d0`, `0x100003d8`, `0x100003ef`, `0x10000405`, `0x10000406`, `0x1000044f`, `0x1000045f`, `0x10000460`
- reg `0x9129b0` (25): `0x10000091`, `0x10000092`, `0x100000aa`, `0x100001eb`, `0x100001f2`, `0x100001f3`, `0x10000233`, `0x10000251`, `0x10000261`, `0x1000028b`, `0x10000292`, `0x10000370`, `0x100003a2`, `0x100003d4`, `0x100003f1`, `0x100003f2`, `0x100003f4`, `0x100003f5`, `0x100003fa`, `0x10000418`, `0x1000042f`, `0x1000047d`, `0x1000047e`, `0x100004e6`, `0x100004f0`
- reg `0x914db0` (18): `0x10000372`, `0x10000373`, `0x10000375`, `0x10000376`, `0x10000378`, `0x10000379`, `0x1000037a`, `0x1000037b`, `0x1000037c`, `0x1000037d`, `0x10000386`, `0x1000038a`, `0x100003a0`, `0x100003d1`, `0x100003e7`, `0x100003e8`, `0x100003fd`, `0x1000047c`
- reg `0x924320` (6): `0x1000041a`, `0x1000041b`, `0x1000041c`, `0x1000042e`, `0x10000498`, `0x1000049b`
- reg `0x960a30` (1): `0x100001a5`
- reg `0x960fc0` (28): `0x10000036`, `0x1000003c`, `0x10000042`, `0x10000071`, `0x10000084`, `0x10000098`, `0x100000b8`, `0x100000c0`, `0x100000cc`, `0x10000135`, `0x10000137`, `0x100001ab`, `0x100001b8`, `0x10000264`, `0x100002ad`, `0x1000030e`, `0x1000037f`, `0x100003e6`, `0x100003fb`, `0x1000041d`, `0x1000041e` (Encounter.RecvNotice_SurrenderVoteConcluded), `0x10000432`, `0x10000454`, `0x10000464`, `0x10000471`, `0x1000048d`, `0x100004a9`, `0x100004c1`
- reg `0x961650` (5): `0x100000c9`, `0x10000401`, `0x10000403`, `0x10000438`, `0x10000458`

## 7. Open points

- All "(?)" meanings are structural guesses; trace them with `tools/diag.py` breakpoints on the listed exec/handler VAs.
- First candidates to try in game: 0x6/0x86 single property updates (life state), 0x2050/0x2056 scriptlet by key, 0x2039 announcer dialog element, the effect group (0x200C/0x200F/0x202B) with StatusIcon 0x20A2/0x20E9, minimap 0x2006/0x2179, notices 0x10000109 (match time) and 0x10000090/0x100000BC (respawn timers).
- Notice names for the unnamed network notices are not in the exe; they are probably in the Flash library of pack 0xA00000D0.
