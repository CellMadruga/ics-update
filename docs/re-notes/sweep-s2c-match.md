# Sweep: server->client match/world/combat messages ics does not send (2026-10-25)

Scope: every S2C row of `full-protocol.tsv` with status "not sent" / "ics builder unused" / "old server only" and a
match category (match, world, combat, objects, entities, skills, statuses, movement, effects, map, PvP). UI-only
notices (GM_UI / GM_Character announcements, end-of-match, lobby, account) belong to the other sweep and are only
listed in section 4 when the tsv status is wrong.

Method: handler / exec decompiled with REA (Ghidra, InfiniteCrisis.exe base 0x400000); ics call sites checked with
grep over `ics/` (2026-10-25 tree). Confidence: C confirmed (decompiled + named), P probable, G guess.
Priority: P1 = visible in an ordinary match if missing, P2 = rare / one feature, P3 = not needed (debug, no-op,
login-only, legacy path).

## 0. Stale tsv statuses (the tsv says "not sent", ics already sends it)

Checked by builder + live call site in `ics/` (some behind a config switch; see ics/config.py):

| id | ics builder (ics/messages.py) | call site |
|---|---|---|
| 0x0006 | set_property (EVT_SET_PROPERTY) | world.py cast bar 0x100004FD and others |
| 0x00B0 | batch sub-item of 0x4 (create_object, pvp_movement_state) | session.py / world.py / match/units.py |
| 0x00BC | batch sub-item of 0x4 (create_object) | same |
| 0x00F2 | batch descriptor of 0x4 | same |
| 0x200F / 0x202B | effect_add / effect_remove | world.py (status mirror, skill copies; config-gated) |
| 0x202A | load_announcer_set | match/match.py |
| 0x2039 | announcer / announcer_line | match/match.py |
| 0x2069 | pvp_tracker_status | match/objectives.py |
| 0x2075 | objective_tracker_enabled | matchend.py (tsv says "ics builder unused") |
| 0x2077 / 0x20CE / 0x2096 | induction / induction_complete / induction_cancelled | world.py cast bar |
| 0x207B, 0x2092, 0x20A0, 0x20DC, 0x20C9 | skill_usable_override, skill_resource_error, skill_disable_condition, skill_error, skill_script_event | world.py |
| 0x20C8 / 0x20A8 / 0x20E9 / 0x20D0 / 0x2127 | status_icon_add / update / remove / tooltip / refresh | world.py |
| 0x20BD | floaty_status | world.py |
| 0x20D2 | pvp_map_marker | match/objectives.py |
| 0x20F0 / 0x20E8 | attribute_modifier_add / remove | world.py, shop.py |
| 0x2137 | ping_echo (map-note remove builder reused as ping echo) | session.py |
| 0x215C | pvp_dampener_counts | match/match.py |
| 0x2189 / 0x218A | teleport_effects | world.py |
| 0x2198 | root_counter | world.py |
| 0x10000109, 0x10000134, 0x100004FB, 0x1000005B, 0x10000455, 0x10000456, 0x10000205, 0x100002AB, 0x100002AF, 0x100002B1, 0x10000424 | pvp_* / dialog_enable / timeline_banner | match/*.py, session.py |
| 0x0001 / 0x008A | destruction_box / destruction_sphere (box / sphere destruction impulse; the tsv calls them "movement update": wrong, see full-combat-skills.md 4.6) | world.py (DestructionImpulse node) |
| 0x100002AC | pvp_timeline_remove | builder exists, **no call site** (= "ics builder unused") |


## 1. Rows still not sent (ics tree 2026-10-25)

| id | name | what the client does | layout | needed for | trigger | priority | conf |
|---|---|---|---|---|---|---|---|
| 0x0008 | Destruction raycast impulse | 0x6325C0 -> 0x62C990 + 0x6323F0: ray query over the Havok destructibles, then 0x631FA0 plays the hit scriptlet key + FX record on the broken pieces | u8 0 \| ray{GUID/u64/Position/vec3 vec3 u32...} \| u32 x4 \| u8 | debris of props hit by a ray skill (DestructionRaycast 0x100000DD, 2 scripts) | server runs node 0x100000DD | P2 | C |
| 0x0005 / 0x00B0 (standalone) | 0xB0 listener dispatch | 0x629910 / 0x6298D0 call every listener at obj+0x60 (vt+0x18 / vt+0x8) with the payload = the listeners of the 0xB0 sub-item of 0x4 (0x60AED0 create / 0x60AFA0 update). The tsv layout `{u8 {u16}}` is a trace error: the payload is the movement block | u8 0 \| 0xB0 movement block (client-movement.md 1.2) | cheaper movement updates than a 0x4 batch | each movement segment (ics sends 0x4 with only 0xB0) | P3 | P |
| 0x0007 / 0x013B | Set one property (aliases of 0x6) | same exec 0x699450 / handler 0x635360 as 0x6 | u8 0 \| PropValue | nothing beyond 0x6 (ics sends 0x6) | - | P3 | C |
| 0x0086 / 0x0129 / 0x013C | Remove one property | obj+0x38 vt+0x54 (0x6353B0 / 0x6353A0): removes the id from the object's table through the change path; watchers fire | u8 0 \| u32 property id | clearing a watched property instead of writing 0 (P: temporary flags) | a status / skill removes a property | P2 | C |
| 0x00BC (standalone) / 0x013D | Set a property table | obj+0x38 vt+0xA4 / vt+0xA8 (0x13D replace variant, P) | u8 0 \| PropTable | batching many 0x6 (ics sends 0xBC only inside 0x4) | level up, respawn | P3 | C |
| 0x0081 / 0x0096 / 0x0104 / 0x0110 / 0x00C4 / 0x00D7 | Region / cell properties (iface 79d30b39) | no game handler resolved; region/cell property service by position | u8 0 \| Position \| (u8) PropTable / PropValue / u32 | Turbine landblock-cell properties; IC loads cell data from the packs | maps render and fog works without them | P3 | G |
| 0x0083 | Factory service call vt+0xD4 | 0x603E40: [0x1B67258] (WorldEntityFactory) vt+0xD4(u32) | u8 0 \| u32 | unknown factory command | - | P3 | G |
| 0x008B | Refresh appearance of object | 0x631050: re-applies the model component (obj+0x58) of IID u64 | u8 0 \| u64 | costume / part change mid-match | after 0x00F5 / 0x0124 | P3 | C |
| 0x00B8 | Appearance / model setup with parts | 0x6322D0 -> 0x631FA0 (CModelComponent): position + parts list | u8 0 \| u64 \| {Position u64 u32 x4 {parts}} \| u32 \| vec3 \| u8 u8 | server-driven model attachments; IC builds models from the class templates | - | P3 | C |
| 0x010D / 0x0138 | Add appearance parts / batch refresh | 0x630160 -> 0x62FB20; 0x631550 (+ scriptlet 0x14 on type-9 objects) | u8 0 \| {u64 {u32 {Position}}} | extra meshes (P: legacy parts path) | - | P3 | C |
| 0x00F5 / 0x0124 / 0x0106 / 0x0115 | Appearance part attribute / state / reset / LOD flags | 0x62CC20 (part +0x194), 0x62CBE0 / 0x62BA80 (part state), 0x62EF80 (remove part), 0x62CC60 (flags for all parts) | u8 0 \| u64 \| u32 part \| u32 value (0x115: u8) | per-part visibility (P); kits do this with scriptlets | - | P3 | C |
| 0x0094 / 0x0117 / 0x00B7 / 0x00D8 / 0x00D9 / 0x00F8 | Engine object component calls | 0x60C0F0 obj+8 vt+0x4C (u8); 0x634F70; 0x634F00 -> 0x60D9A0 obj+4 (behaviour graph) list {u32,u8}; 0x634F40 obj vt+100; 0x6354C0 / 0x6352D0 key {cint,u8} | see tsv | 0xB7 may set graph variables (P); others unknown | - | P3 | G |
| 0x009C / 0x00E2 / 0x00C2 / 0x00BA | Session-level property / flag | 0x6A8380 / 0x6A8410 service 0x15D2B10 (session); 0x420920 stores a session GUID + u32; 0x635670 service 0x15CB5B0 | u8 0 \| PropValue / u32 / GUID u32 / u8 | login-era session state | - | P3 | G |
| 0x009E / 0x00A5 / 0x00A7 / 0x00B1 / 0x00B2 / 0x00C8 / 0x00E9 / 0x00EE / 0x00FC / 0x00FF | TypedWorldObject service events | service 0x15BAB54 / 0x15BA360 (strings `TypedWorldObject::CacheInstanceID_`): IID-set diffs (0x5A14B0), world object resolve / unload (0x5D1C50), +0x154 of a typed object (0x5A19D0). Turbine container / world-object references; 0xA7 / 0xB1 h 0x558060 is only a QueryInterface helper | u8 0 \| WorldRef{u64,u64,GUID} \| ... | none in IC: every match object comes through 0x4 bundles | - | P3 | P |
| 0x00AB / 0x00C9 / 0x0101 | System text (StringInfo) | 0x5A8680 + 0x6A81F0 / 0x6A81C0 / 0x6A8190 (0x101 with a source IID) | u8 0 \| (u64) \| StringInfo | system chat lines (UI sweep) | - | P3 | P |
| 0x00AC / 0x00E0 / 0x010F | Queue-key events | exec 0x538780 only | u8 0 \| QueueKey{u32,u32} (\| u8) | engine leftovers | - | P3 | G |
| 0x00CF / 0x0105 | Login / character result | 0x6A8330 / 0x6A8130 (+ StringInfo) | u8 0 \| u32 (\| StringInfo) | login errors, not match | - | P3 | P |
| 0x00F2 (standalone) | Engine event | no-op in this build | u8 0 \| {{u32} u64} \| u32 | nothing (meaningful only as the 0x4 descriptor) | - | P3 | C |
| 0x0116 | Map visualization chunk | 0x635520 debug map visualisation | u8 0 \| Position \| {...} \| u32 part \| u32 of | debug only | - | P3 | C |
| 0x0123 | Client scale factor | 0x633270 clamps 0.08-1.0 | u8 0 \| u32 (f32) | unknown global scale | - | P3 | G |
| 0x2006 / 0x200E | Handle-tracked client effect start / stop | 0xA56C90: [root+0xA4] drops any entry with that handle, builds an effect (0xA95B70: DID + params, position -1,-1,-1 = on the entity), 0xA33F40 starts it and stores it by handle; 0xA21A00 stops it. Not map notes (full-maps-world.md 7.2) | u8 0 \| u32 \| Handle{u32,u64} \| u32 \| u32 \| {u32} \| u32  /  u8 0 \| Handle | looping sounds / VFX the server owns (P) | script node that starts / stops a handle effect | P2 | P |
| 0x2008 / 0x204E / 0x2041 / 0x2158 / 0x2063 / 0x2157 / 0x202C / 0x204D | Raise script events on client effect instances | 0xAA1BF0 (agent, event, script DID), 0xAA1B90 (all instances), 0xAA1C50 (list), 0xAA1C90 (list + key), 0xA9FBB0 (one GUID): queue events on client copies of 0x34 scripts (0x96DED0) | u8 0 \| u64 agent \| u32 event \| u32 script  (or list<u32> / GUID) | client status / skill scripts reacting (end VFX, stacks, interrupt); matters only for scripts ics mirrors with 0x200F | server raises an event on a status / skill script the client hosts | P2 | C |
| 0x2019 / 0x206F | Effect instance variable update | 0xAAA830: writes a script variable of client instance GUID | u8 0 \| GUID \| {u32 u32 u32} \| {u32 {u32}} | stack counts / charge values in status VFX | status variable changes | P2 | C |
| 0x200C / 0x2043 / 0x2062 / 0x2037 | Effect list apply / aliases | 0xAA1CD0 applies a list (0x200F x n); 0x2062 = 0x200F, 0x2037 = 0x202B | u8 0 \| {u32 n {instance}} \| u8 | late join (all current statuses at once) | object creation for late joiners | P3 | C |
| 0x203D | Cleanse / expire all flagged effects | 0xAA1B60: raises 0x10000009 on every effect flagged 0x10000007 | u8 0 \| u64 agent | death / cleanse clears status VFX on client copies | death, cleanse | P2 | C |
| 0x0043 / 0x0044 / 0x201D | Floaty component (obj+0x90) entries | 0xAA4EE0 remove by handle; 0xAAF7C0 handle-tracked status floaty -> GM_Vitals.RecvNotice_DisplayFloatyStatus; 0xAA7200 replace list | u8 0 \| Handle \| u32 \| u32 | persistent over-head status text on any unit (ics sends the one-shot 0x20BD) | status with a floaty start / end | P2 | C |
| 0x2022 / 0x2074 / 0x2000003D | **Visual progression** (component 47 obj+0xBC; the tsv / full-entities-engine.md call it 'agent component') | 0xAAC760 adds a 0x58-byte entry: resolves / spawns (0xA884A0 with class DID at +0x28, or 0xA88590 when f32 duration +0x20 > 0) a client entity and raises scriptlet `_VisualProgression_Start` 0x10000AD3 if the entry is fresh (< 0.2 s on the game clock); 0x2074 (0xAA2C60) removes entry id: 0x10000AD5 then `_Interrupt` 0x10000AD4 (u8 1) or `_Stop` 0x10000AD2 (u8 0) and destroys it after 0.5 s; 0x2000003D = whole list | u8 0 \| {u32 id, u32, u32, u32, u32, vec3, u8, u64 target, u32, u8, u32 x5}  /  u8 0 \| u32 id \| u8 interrupted | progress visuals bound to an entity for a duration (table 0x1D00046A; P: capture beam / channel tether / recall); exists only if the template has bool 0x100008DA | channel / capture start and end | P1 if champions carry 0x100008DA, else P2 | C handler / P use |
| 0x2023 | Objective category update / remove | 0xA14040 -> Encounter.RecvNotice_UI_UpdateObjectiveCategory / RemoveObjectiveCategory | u8 0 \| u32 \| {u32 u32} | objective tracker categories (PvE / tutorial) | objective changes | P2 | C |
| 0x201C | Encounter UI entry list add | 0xA80440: encounter manager [root+0x68] appends entries (0xA752B0), flag +0x1C8 from u8, first time registers (0xA3CB70) | u8 0 \| {u32 n {u32 {u8 u32 u32 PropTable}}} \| u8 | P: encounter objective entries with properties (PvE) | encounter start | P2 | P |
| 0x2047 | Dialog: play / advance a conversation line | 0xA13B40 -> CDialogSystem vt+4 0xA67670: find conversation (0xA13BF0: entity, u32, u32) then 0xA58E30 with the node | u8 0 \| u64 entity \| u64 \| u32 \| u32 \| u32 | conversations that advance on server events (tutorial / PvE VO) | script conversation advance | P2 | P |
| 0x2142 / 0x2143 | Dialog: stop conversations | 0xA475C0 on [root+0x1C]: u8 selects the queue (+0xA0 / +0x90); 0x2142 stops those whose id is in the list, 0x2143 stops every one in the queue | u8 0 \| list<u32> ids \| u8 queue  /  u8 0 \| u8 queue | cutting announcer / VO lines (match end, overlapping events) | match end, cinematic skip | P2 | C |
| 0x2044 | LockInput: controller counter +0x70 | 0xA1A510 -> 0x85EBD0(u8): ++ / -- ; non-zero = move / stop orders buffered by 0x863860 | u8 0 \| u64 entity \| u8 on | client-side order lock during CC / cinematics / channels (node 0x100000AD) | CC applied / released on the local champion | P2 | C |
| 0x2083 | Controller u32 (+0xC0) | 0xA1A5A0: [[root+0x90]+0xC0] = u32 | u8 0 \| u32 | unknown controller mode | - | P3 | G |
| 0x215F | Controller handle list add / remove | 0xA1A570 -> 0x8728E0: u8 1 adds the handle (0x8607E0), u8 0 checks / removes (0x860730, 0x86BE30) and calls 0x85E9A0 when [ctrl+0x84] == 1 | u8 0 \| Handle{u32,u64} \| u8 | P: action handles that block orders (DisableActions mirror) | CC with a handle | P2 | P |
| 0x2059 | Spawn a client-only entity | 0xA69170 on [root+0x24]: creates a local entity from class DID u32 (factory vt+0x30) with a property table, kept in a 0x58-byte list | u8 0 \| u32 class DID \| PropTable | client-only props / indicators placed by the server (P) | - | P2 | P |
| 0x205C | Tracked player list add / remove | 0xA4EBC0 -> 0xA38F20 on [root+0x5C]: adds (u8 1) / removes (0) the destination player's IID (+0x100), 0x868220 notifies | u8 0 \| u8 on | P: party / spectated players list | - | P3 | G |
| 0x2050 | Run scriptlet key on object (no variables) | 0xA14580: obj+0x10 scriptlet component runs key u32 | u8 0 \| u64 \| u32 key | same as 0x8D with one entry (ics uses 0x8D) | - | P3 | C |
| 0x2056 | Run scriptlet with a variable table | 0xA0D040: key + PropTable variables on the destination | u8 0 \| u32 key \| PropTable | alternative to 0x8D variables | - | P3 | C |
| 0x2073 | Start scriptlets via the local player | 0xA883F0: same body as 0x8D (0xA22DA0) | u8 0 \| ScriptletList | alias of 0x8D | - | P3 | C |
| 0x203E / 0x20F7 | no-op handlers | 0x132C5C0 (ret) | u8 0 \| u8  /  u64 u32 u64 | nothing | - | P3 | C |
| 0x207C | Skill HUD slot override | 0xA3A000: slot < 5 -> (u32, u8, u32) override of that button | u8 0 \| u32 slot \| u32 \| u8 \| u32 \| u32 | second-stage skills that swap the button (skill-second-stages.md) | stage-2 window opens / closes | P1 | C |
| 0x2082 / 0x20B2 | Channel started / stopped | 0xAAF400 / 0xAA4670: Usage.RecvNotice_UpdateChannelStarted / ChannelingInterrupted / UpdateChannelStopped | u8 0 \| u64 agent  /  u8 0 \| u64 \| u8 interrupted | channel bar for channelled skills and the recall channel | channel start / end / interrupt | P1 | C |
| 0x20BB | Induction percent (variant) | 0xAA2540 | u8 0 \| u32 \| u32 | alias of 0x2077 (sent) | - | P3 | C |
| 0x20DB / 0x20BC | Usage component user set add / remove | usage vt+0x4C 0xAA26E0 (add IID) / vt+0x50 0xAA2740 (remove); if the IID is the controlled champion: 0xA16470(0), 0xA1CDD0, 0xAA23C0 (HUD usage refresh) | u8 0 \| u64 user | interactables in use (capture / pickup progress on the HUD) | champion starts / stops using an object (0x100005A6 objects) | P2 | P |
| 0x2091 / notice 0x1000015A | Skill UI overlay | 0xA5D0A0 / 0x8BC9B0 -> GM_Skill.RecvNotice_UpdateSkillUIOverlay | u8 0 \| u64 \| u64 \| u32 \| u32  (notice: u32 slot \| u32 overlay \| u8 on) | button overlays primed / charged / combo (node 0x10000097) | skill script runs UpdateSkillUIOverlay | P1 | C |
| 0x208C | Skill button update suppressed | 0xA0E3C0 | u8 0 \| u32 slot \| u8 | avoid icon flicker during stage swaps | with 0x207C | P2 | C |
| 0x208D | Vitals floaty status (u8) | 0xA16DD0 | u8 | family of 0x20BD (sent) | - | P3 | C |
| 0x20F9 | Skill availability event | 0xA2A1B0: raises 0x100000B6 (off) / 0x100000B7 (on) with SkillSlot on the agent's client scripts | u8 0 \| u64 agent \| u32 slot \| u8 on | client skill scripts that light up when usable | availability changes | P2 | C |
| 0x2187 | Enable skill button (variant) | 0xA39F90 | u8 0 \| u32 | P: one-argument enable | - | P3 | C |
| 0x209F / 0x217F / 0x2180 | Minimap targeting ring | 0xA5DA40 / 0xA5D070 / 0xA6D800 MapManager.RecvNotice_ShowMiniMapTargetingRing (nodes 0x10000022 / 0x10000056) | u8 0 \| u32 \| u64  /  u32 u8  /  u32 | global-range ults (ring on the minimap while aiming) | 8 scripts with ShowMinimapTargetingRing | P2 | C |
| 0x2084 / 0x20C2 | Remove / set property on entity u64 via the player | 0xA0E430 -> 0x58B4C0 / 0xA0E480 -> 0x58B770 | u8 0 \| u64 \| u32  /  u8 0 \| u64 \| PropValue | alias of 0x86 / 0x6 | - | P3 | C |
| 0x20E7 | Attribute modifier full sync | 0xAA0F20 -> 0x97A300: replaces every modifier (own + per team) | u8 0 \| own map {attr -> list} \| per-team maps \| u8 u8 | late join / resync after many 0x20F0 | creation for late joiners | P3 | C |
| 0x20DD | Upgrade list (+0x40) | 0xAAA190 -> 0xADB230 copy, flag +0xF0 = 1 | u8 0 \| list<u32> | bought-item history (P) | after a purchase | P2 | C store / P |
| 0x212B | Artifact skill-slot mapping | upgrade vt+0x54 0x9743B0: +0xB0 -> Flash SetUIArtifactSkillSlotMapping | u8 0 \| list<u32> | active-item buttons | after buying an active item; answer to client 0x212C | P1 | C |
| 0x20DA | Current encounter triple | 0xA7F0B0: with >= 3 values sets +0xC/+0x10/+0x14 of 0xA7DF00's struct and [root+0x68]+0x6C = first | u8 0 \| list<u32> | P: current encounter ids for the HUD (not map notes) | match start | P3 | P |
| 0x20DE | Service 0x160D8E0 event | 0xADB190 only queries the service | u8 0 \| u32 \| u64 | unknown | - | P3 | G |
| 0x2123 / 0x2126 / 0x2129 / 0x212A | Status icon component (obj+0xC0) store | vt+0x5C 0x97BAE0 -> 0x97B6D0 add / update icon by handle with two tooltip arg lists; vt+0x58 0x97B920 same by (u32,u32) key; vt+0x50 0x97B590 remove by key; vt+0x54 0x97B680 remove by handle (0x97AF10) | u8 0 \| u64 \| Handle \| u32 \| u32 \| {u8 cint {u32 u32}} x2  (other forms in tsv) | per-entity icon store read by the target frame / overhead (ics fills only the local HUD via 0x20C8 / 0x20A8) | status applied to any visible unit | P2 | P |
| 0x213E | Batch HUD element events | 0xA5A7B0 UI.RecvNotice_BatchNotifyHUDElements | u8 0 \| {u32 n {u32 u32 u32 u32}} | alias of 0x213D x n (sent) | - | P3 | C |
| 0x2150 | HUD visibility | 0xA9CCA0 UI.RecvNotice_UpdateHUDVisibility | u8 0 \| u32 mask | hide HUD for cinematics / victory | cinematic start / end | P2 | C |
| 0x2159 | Raise an HFSM event on a list of entities | 0xA1CAC0 -> 0xA15680 (needs [root+0x38]): builds event u32 (0x4607A0) and queues it on each IID's script component (0xAA1A60) | u8 0 \| list<u64> \| u32 event | map-wide client script reactions (P) | encounter events | P2 | C |
| 0x215A | Entity-group table | 0xA5CF20 -> 0xA55690 on [root+0x38]: replaces a list of {u32, u32, list<u64>} | u8 0 \| {u32 n {u32 u32 list<u64>}} | P: named entity groups | match start | P3 | P |
| 0x2171 / 0x2173 / 0x2174 | Training control / floaty / lesson event | 0xA8DE40 / 0xA7A930 / 0xA93DF0 | see tsv | tutorial / training only | lessons | P3 (PvP) | C |
| 0x2179 | Minimap polyline | 0xA5C350: pixel pairs + colour flag (0x7EC = RGBA; not fog, full-maps-world.md 7.2) | u8 0 \| {{u32 u8}} \| u32 | lines drawn on the minimap (P: routes) | - | P2 | C |
| 0x2038 / 0x2045 | Match ended UI event / end-of-match stats | 0xA79170 / 0xA91BF0 | see tsv | other sweep. 0x2045: **no ics builder exists** (tsv 'builder unused' is wrong) | match end | other sweep | C |
| notice 0x100000BA | PauseDefeatStatusTimerForEntity | GM_UI reader 0x8C4960 | u64 iid \| u32 | respawn timer pause | rare | P3 | C |
| notice 0x10000076 | TimerClockSync | GM_UI reader 0x8C4A00 | u32 | HUD timer sync (P) | match start / periodic | P2 | C |
| notice 0x10000414 / 0x10000364 | Upgrade group | readers 0x95B140 / 0x95B1F0 | u64 \| u32 (\| u32 \| u8) | P: purchase results | after purchase | P2 | G |
| other notices | 0x100004F7, 0x10000118, 0x10000192, 0x10000229, 0x100004A5, 0x10000288, 0x100003D5/6/7, 0x10000059, 0x1000004A, 0x100000B6, 0x1000021C, 0x100002B2, 0x100002BC, 0x100002AE, 0x100000CA/CD/CB/CE | UI notices (readers only) | see tsv | UI sweep; 0x1000021C kill feed is covered by ics event 0x217A | - | other sweep | - |

## 2. Corrections to full-protocol.tsv (do not edit the tsv; apply when it is regenerated)

| id | tsv says | correct |
|---|---|---|
| 0x0001 / 0x008A | "Movement update (?)", not sent | box / sphere **destruction impulse** (C, full-combat-skills.md 4.6); ics sends both (destruction_box / destruction_sphere) |
| 0x0008 | "Object (re)placement" | destruction **raycast** impulse (C); not sent |
| 0x0005 / 0x00B0 | "Object listener callback u8 + u16" | dispatch of the 0xB0 movement block to the obj+0x60 listeners; payload = movement block (P strong). 0xB0 is sent by ics inside 0x4 |
| 0x0006, 0x00BC, 0x00F2 | not sent | sent (0x6 standalone; 0xBC / 0xF2 inside 0x4) |
| 0x2022 / 0x2074 / 0x2000003D | "agent component, movement/knock/teleport (?)" | **Visual progression component** (obj+0xBC, scriptlets `_VisualProgression_Start/Active/Interrupt/Stop` 0x10000AD3/AD5/AD4/AD2) (C) |
| 0x2044 | "Root+0x90 counter push/pop (?)" | LockInput: local controller order-lock counter +0x70 (0x85EBD0) (C) |
| 0x2198 | "Root+0x90 counter (?)" | PushRootCounter: controller counter +0x74 (0x85EBF0); **ics sends it** (root_counter) |
| 0x2006 / 0x200E | "MapManager: add / remove map note" | handle-tracked client effect start / stop on [root+0xA4] (P) |
| 0x2142 / 0x2143 | "Dialog: queue/allow list (?) / flag (?)" | stop conversations by id list / all, per queue (C) |
| 0x2159 | "Encounter: root+0x38 list of IIDs + u32 (?)" | raise HFSM event u32 on each listed entity's script component (C) |
| 0x20DB / 0x20BC | "Usage component vt+0x4c / +0x50 (?)" | add / remove a user IID of a usable object, refreshes the HUD when it is the local champion (P) |
| 0x2123 / 0x2126 / 0x2129 / 0x212A | "StatusIcon component (?)" | per-entity status icon store: add/update by handle, add/update by key, remove by key, remove by handle (P) |
| 0x00A7 / 0x00B1 | h 0x558060 | 0x558060 is a QueryInterface helper, not the handler; TypedWorldObject service (P) |
| 0x2045 | ics builder unused | no ics builder exists |
| 0x2075 | ics builder unused | sent (matchend.py objective_tracker_enabled) |
| 0x200F, 0x202B, 0x202A, 0x2039, 0x2069, 0x2077, 0x2096, 0x20CE, 0x207B, 0x2092, 0x20A0, 0x20DC, 0x20C9, 0x20C8, 0x20A8, 0x20E9, 0x20D0, 0x2127, 0x20BD, 0x20D2, 0x20F0, 0x20E8, 0x2137, 0x215C, 0x2189, 0x218A, 0x2198, notices 0x10000109 / 0x10000134 / 0x100004FB / 0x1000005B / 0x10000455 / 0x10000456 / 0x10000205 / 0x100002AB / 0x100002AF / 0x100002B1 / 0x10000424 / 0x100002EB | not sent / builder unused | sent by ics (section 0) |
| 0x100002AC | not sent | builder exists (pvp_timeline_remove), never called |

## 3. Top 20 server-side implementations (ordered)

1. **0x2082 / 0x20B2 channel bar**: on a channelled cast (and the recall channel) send 0x2082 `u8 0 | u64 agent` to the
   caster's player at start; 0x20B2 `u8 0 | u64 agent | u8 interrupted` at the end (1 when damage / CC broke it).
2. **0x207C slot override** (+ 0x208C suppress): when a second-stage window opens, `u8 0 | u32 slot | u32 | u8 | u32 | u32`
   (field meaning: P - skill DID, flag, icon); restore when it closes.
3. **0x2091 / notice 0x1000015A skill overlay**: when a skill script runs UpdateSkillUIOverlay 0x10000097, send the notice
   `u32 slot | u32 overlay | u8 on` to the owner.
4. **0x212B artifact skill-slot mapping**: after a purchase that adds an active item and as the answer to client 0x212C,
   `u8 0 | list<u32>` (slot order) to the champion IID.
5. **0x2022 / 0x2074 visual progression**: at capture / channel start `0x2022` entry (u32 id, ..., f32 duration,
   u64 target); at the end `0x2074 u32 id | u8 interrupted`. First check which templates set bool 0x100008DA (open).
6. **0x20DB / 0x20BC usage users**: when a champion starts / stops using a usable object (capture point, pickup), send
   `u8 0 | u64 user` to the object's IID; the HUD refreshes for the local champion.
7. **0x2008 / 0x204E / 0x202C script events to mirrored effects**: whenever ics raises an event on a status it mirrored
   with 0x200F, mirror it (`u64 agent | u32 event | u32 script DID`, or 0x202C by GUID) so the status VFX ends / changes.
8. **0x203D on death / cleanse**: `u8 0 | u64 agent` before removing the instances.
9. **0x2019 effect variable**: stack / charge changes of mirrored statuses (`GUID | {u32 u32 u32} | {u32 {u32}}`).
10. **0x2123 / 0x2126 / 0x212A per-entity status icons** for every visible unit (target frame / overhead), alongside the
    local-HUD 0x20C8 / 0x20A8 / 0x20E9 ics already sends.
11. **0x0044 / 0x0043 handle floaties**: persistent over-head status text `Handle | u32 id | u32 value`, removed by handle.
12. **0x2044 LockInput**: `u64 champion | u8 on` to its player when a hard CC / cinematic starts and ends (balanced).
13. **0x2150 HUD visibility**: `u32 mask` 0 at cinematics / victory, restore after.
14. **0x2142 / 0x2143 stop dialog**: at match end and when a higher-priority announcer line preempts (`u8 queue`).
15. **0x0086 remove property**: `u8 0 | u32 id` to an object when a temporary property ends (instead of writing 0).
16. **0x209F / 0x217F / 0x2180 minimap targeting ring** for ShowMinimapTargetingRing 0x10000022 / Hide 0x10000056.
17. **0x20F9 skill availability**: `u64 agent | u32 slot | u8 on` when a slot becomes usable / unusable.
18. **0x0008 destruction raycast** for DestructionRaycast 0x100000DD (beam debris), like 0x1 / 0x8A today.
19. **0x2006 / 0x200E handle effects** for looping server-owned effects (layout P; needs one test).
20. **notice 0x10000076 TimerClockSync** `u32` at match start, and call the existing **0x100002AC** builder when a timeline
    banner expires.

Open: which records carry 0x100008DA (decides 5 between P1 and P2); 0x2006 field meanings; 0x207C field meanings.
