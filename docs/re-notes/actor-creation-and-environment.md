# Cinematic actors vs network objects, the environment system, the sphere (static analysis, 2026-10-21)

Read-only analysis (Ghidra via REA + capstone) of InfiniteCrisis.exe (sha256 463adfff...).

## Cinematic actors (confirmed)
- 0x6A4270 (called via 0x627270, the 0x954 read at 0x6A42B7) only collects 0x954 template DIDs (preload); it
  creates nothing.
- Play: 0x6A6540 stores the cinematic DID at +0x88, loads the 0x3E record (mode 1), copies a binding table
  `{u32 actorKey, pad, u64 IID}` (16 bytes each) to +0x78.
- Spawn loop 0x6A60A0: actors array at +0x20 (0x80 bytes each, key at +0x10); key -> IID through the binding
  table; spawn 0x6A5AE0(actor, IID); after a spawn, entity factory +0x90(this, new IID).
- Spawn 0x6A5AE0 (actor +0xC class, +0x14 "needs binding", +0x18 position, +0x1C properties, +0x30 a DID started on
  the actor via 0x588A00, +0x34 the new entity):
  - bound to an IID: the entity is looked up (factory +0x58, global factory [0x1B67258]); missing -> the actor is
    skipped; class = that entity's class (+0x110) (an entity 0x40... -> its 0x510 world state); later its visual
    component is copied (0x634EA0 -> 0x634ED0).
  - not bound and +0x14 set -> skipped; otherwise the scene record's class.
- Creation record ("desc", 0x48 bytes, ctor 0x54A4D0, vtable 0x15C56E8): +8 class DID, +0xC position, +0x28 u64
  IID, +0x30 mode, +0x34 flags (default 3), +0x38 u64 parent IID.
  The cinematic sets: class = the world state (0x2E...), mode = 1, flags 0x81 (setter 0x54A560), IID 0 -> allocated
  by 0x4DAD00 as 0x81000000_00000000 | counter (base 0x1854690); property 0x8EE (IID) = the bound source entity;
  0x50F = 1 if the world state says 1 or 7, else 6; factory +0x24 (0x603DE0 -> 0x54B6A0). After creation: motion
  component position (0x635020 -> 0x61DE50), motion flags +0x98 |= 0x40 (0x6350F0 -> 0x61CCC0), 0x7E3460(entity, 2).

## Network objects (confirmed)
- 0x54B790 (factory vtable +0x40) finds sub-event 0xF2 and calls +0x3C BuildCreationInfoFromEntityDesc 0x54AD90;
  the cinematic's 0x54B6A0 calls it too; both end in create 0x54F1F0 (factory vtable 0x15A32D0, +0xE4).
- 0xF2 reader 0x54BD00: `u32 class -> desc+8`, **`u64 -> desc+0x38` = the parent IID** (not padding). Landblock
  statics (BlockEntities 0x53DA40) set it to the landblock IID built from the cell (0x4DB130).
- Network objects leave mode 0: the mode comes from the IID top byte (1/4/5 -> 2, 2 -> 4, 3 -> 3, else 0); mode 1
  (the cinematic's) cannot be had through the IID. An entity class loads its 0x510 world state with mode 1 anyway
  (0x54A860); only a bare world-state class uses the IID mode. The mode goes to the database loader (0x43CE00 ->
  loader +0x98) on first creation; meaning unknown.

## Cinematic message 0x20F5 (confirmed reader 0x878020)
`u32 mask`, then by bit: bit10 u32 -> +0; bit0 DID -> +4; bit1 u32 -> +0x14; bit2 `u32 n` + n x `{u32 key, u64
IID}` (bindings, readers 0x877E90 / 0x962AD0); bit5 u8; bits 3,4,6,7,8,9 u32 -> +0xC, +0x10, +0x18, +0x1C, +0x20,
+0x24; bit11 a sub-struct; bit12 u32 -> +0x48. The server sends mask 1 + the DID.

## Ranked experiments (guesses)
1. Bind server entities to cinematic actors: 0x20F5 with bit 2 and the binding list (actor key format open; likely
   per-placement data of the 0x1D scene).
2. Props with IID top byte 0x01 (mode 2, like client statics), in a high counter range.
3. Bare world states: class = world state + 0x50F = 6 (or 1 for 1 / 7), and send them with the movement module
   (the cinematic always places through the motion component).
4. The parent IID (0xF2 u64) = the landblock IID (0x4DB130 from the cell), as the client's statics have.

## CEncounterEnvironmentSystem (structure confirmed, meaning a strong guess)
Set up from a 0x48 record (DB type 0x29) by 0xA8F890 / parser 0xA8E5C0; property 0x100009D2 = list of events (reader
0xA47A40): id 0x100009E5, hashes 0x100009EE / 0x100009D9, 0x100009DE, 0x100009DF (flags), 0x100009D6 (team),
0x100009D5, 0x100009DB, 0x10000A01, 0x100009D7, sub-events 0x100009E4 {0x100009E5, 0x100009E0}. 6 slots started by
id (0xA782C0 / 0xA72090, via 0xA59BD0) from per-team counters at +0x70 (ids 9, 0xD, 0xE, 0x1A, 0x13). Tutorial 1:
record 0x48000F28 (pack 0xA00000B3), event ids 1-4, 9, 13-15, 17-19, 24-26, 30, 31. The hashes look like Wwise event
hashes: the announcer / music state system, not meteors or lightning. 0xA847E0 (a local entity of the world state in
0x10000099 with timing 0x10000940-45) is an area effect with a duration.

## The sphere
Fall: 0x35000025 -> 0x1D000789 -> 0x1D00078A (15 path points, script 0x34000591, events 15 and 545). Opening: the
world state's templates 0x1D000360 / 0x1D000385 and graph 0x1C00006C.

## Open
The actor key format; the mode values; 0x7E3460(..., 2); why server drones render but doors do not (the movement
module is the main difference).

## Why network props stay invisible (static analysis, 2026-10-21)

Read-only (Ghidra via REA + capstone). "Confirmed" = read in the code; "likely" = strong inference; "open" = not traced.

### The 0xB0 sub-event (confirmed)
- Ctor 0x69AC40 (id 0xB0, size 0xF8, vtable 0x15D1E54), payload P at +0x20 (ctor 0x69A9A0), reader 0x57EE90
  (via 0x445430). Leading byte = flags: 0x20 -> 0x57E410 module (`u8 seq` -> P+0; if seq is not the sentinel
  [0x1B67A6B], `u8 type` -> P+4); 0x04 -> 0x57E310 `u64 IID` -> P+0x10 + `u32` (0x10 -> extra block);
  0x10 -> byte P+0x48; 0x08 -> P+0x4C; 0x40 -> 0x57E530 movement block at P+0x60 (sub-flags byte P+0xB2: bit 1 `f64`
  time P+0x80; bit 8 Position P+0x88 (reader 0x47C610: +4 region, +8/+9 landblock x/y, +0xA cell, +0xC u16 of
  Position flag 4); else bits 2/4); then always `u16` -> P+0xBA (the u16 after the Position; meaning open);
  0x02 -> the motion bytes; 0x80 -> 0x533940.
- Dispatch: sub-event vtable slot 1 (0x698CD0 -> 0x6298D0) and slot 9 (0x698D60 -> 0x629910) call every listener
  in entity+0x60 (registered by 0x57EAD0) at +8 and +0x18.
- 0x649230 copies P's region / landblock / cell into a location struct used by the create handler 0x64D8A0 only to
  decide when to create an IID-0x02 object (0x4DAF10 = top byte 2; landblock-loaded check via 0x15CD9B0 +0x50,
  0x64C310 vs 0x64CA10). Both paths create; the cell does not decide visibility there. 0x64CA10 merges the batch's
  0xBC table into the creation desc (0x502B00) before construction.

### Who places a network object (confirmed)
- The only 0xB0 listener that places is the movement component C: creator 0x604D80 -> 0x60AE40, ctor 0x60A9B0
  (base 0x553D80, vtable 0x15C6180, listener sub-object vtable 0x15C614C). +8 = 0x60AED0: stores P's movement block
  in its 9-entry motion history (0x609C70 -> 0x5525A0); if a module is present (0x57DEF0: P+0 != sentinel) it
  selects / creates the module by type (0x553E70, C vtable +0x58 = 0x608FC0); then forwards to the module
  (C+0x20)->+0x58. +0x18 = 0x60AFA0: the same, then module +0x68.
- The module (vtable 0x15C62A8) +0x68 = 0x60B0F0 -> 0x60A830 -> **0x588290 SetEntityFrame(entity, frame, 5)**
  (needs region != 0, landblock x/y != 0xFF, cell != the invalid sentinel). Without a module C+0x20 is null and
  nothing calls SetEntityFrame: the object is never placed. The other listener (vtable 0x15B52C8 / 0x15B5378,
  +0x18 = 0x6113E0) only handles flag 0x04 (attach to the IID at P+0x10: 0x634C70, else detach 0x64B330).
  A third registration (0x57AD20, listener at +8) was not examined (open).
- C exists only when the creation type's mobility is 2: step 3 (0x606400) calls 0x604D80 only if 0x603D80 =
  `0x580160(0x50F) == 2`. Tables (decoded): 0x580160 mobility: 1->1, 2->1, 3->3, 4->1, 5->1, 6->1, **7->2, 8->2**,
  9->3. 0x5801B0: 1->3, 2->1, 3->2, 4->1, 5->2, 6->2, 7->3, 8->2, 9->2 (component 0x604610 when 3). 0x580120
  ("unique"): 1, 4, 6, 7, 8, 9. The creation type is read by 0x54EF40 from the desc's property set, else the class.
- WorldEntityFactory 0x54F1F0 is the recursive template merge (class -> world state -> .entity, stops at a .entity
  DID; DB-type 0x0B). Entity class (DB type 0x40): if the world state's 0x50F is not "unique" (0x54F060) it writes
  0x50F = `mobility == 1 ? 6 : 8` (0x54F000, 0x4C0750 at 0x54F4EA) and logs 0x15B34C8 (".wc entities must be
  UniqueDynamicMobile, UniqueDynamicImmobile or UniqueClientOnlyImmobile"). Bare world state (DB type 0x2D): no
  coercion. Actual construction is factory +0xB0 = 0x54F540 (ConstructStep1..5 strings 0x15B3830..0x15B36C8); its
  third argument (diag "pos") is a serialized component-state stream for 0x54C1D0, not a position.

### Rendering (confirmed)
- 0x61C000-0x624000 is the RenderComponent (source path string after vtable 0x15C92xx). 0x61DE50 = SetPosition
  (copies the Position, +0x48 = has position). Render flag +0x98 bit 0x40 = "position set explicitly": without it
  the render position follows the entity frame / physics (0x6226E0 on model attach via 0x587A50 / 0x587F30,
  0x61DEE0 on change) and a detach resets it (0x6227C0). Bit 0x40 is set only by client-made objects (0x6350F0
  callers 0x683E38, 0x6A5DAD cinematic, 0x750820, 0x752BDD, 0x7EAE57); the property switch at 0x624500 never sets
  it. So a network object is drawn where SetEntityFrame put it, i.e. only after C + a module placed it.
- Model: 0x5693A0 -> 0x54CB80(class): entity -> 0x510 world state (0x54CAF0) -> world-state chain -> .entity; loaded
  with the IID mode (0x02 -> 4). Same for drones, so not the blocker.

### Why each case fails
- Drones (world state ctype 7 -> mobility 2) + module 0x62 / seq 1 / type 1: C + module -> placed -> render.
- Doors (entity 0x40000B0F, world state 0x2E0010F3 ctype 3 -> coerced to 8 -> C exists) sent **without** the module
  (0x42): history stored, never placed. The earlier server sent them with module [1, 1] and they were placed (they
  blocked) but showed nothing: the world state 0x2E0010F3 (props 0x7D2 = 0x1D00073F, 0x7EB = 7, 0x83C, 0x8C1, 0x50F =
  3, 0x83E) has no renderable part; the visible light wall is the separate world state 0x2E0010F4 (.entity
  0x2D000E52, ctype 3, has 0x2A4 and an effect block).
- Power core (entity 0x40000C90 -> 0x2E000AC5 ctype 8): C exists; only the missing module stops it.
- Bare world states (vehicle 0x2E000AAB ctype 5; 0x2E0010F4 ctype 3): no coercion, mobility 1 / 3 -> no C ->
  never placed with or without a module (earlier diag: "never placed"). Sending 0x50F = 6 changes nothing
  (mobility of 6 = 1).
- Section 9's carriers worked for the same reason: the Door entity's type 3 was coerced to 8 (C created) and the
  module was sent; cave Z only gave the model. Cinematic actors and landblock statics need no C: the cinematic
  sets the render position + bit 0x40 directly; BlockEntities 0x53DA40 builds the desc (IID 0x4DB130 from the cell,
  parent 0x38 for top byte 1 / 0x4DAF50 IDs, flag 0x10), creates it with factory +0x24 and calls SetEntityFrame
  0x588290(entity, frame from the record's xyz + quaternion, 5) itself.

### What the server should send (likely; to be tested)
- Any prop: 0xB0 **with** the module, as for drones (`0x62 | 1 | 1 | 0x0F`, f64 time, Position with a valid
  region / landblock / cell 0xFB, u16 0, motion bytes). Class = the entity when there is one (door, power core).
- Bare world states: add 0xBC property 0x50F = 8 (enum; mobility 2 and still "unique"). Open: that the 0xBC value
  reaches 0x54EF40 before step 3 (0x64CA10 merges 0xBC into the desc first, so likely). Fallback: an entity class
  whose world state coerces to 8 (the carrier trick).
- Doors: also create 0x2E0010F4 (with 0x50F = 8 and the module) at the gate to see the wall.
- Not needed (drones render without): parent IID (0xF2 u64 = 0), IID prefix other than 0x02, mode.
