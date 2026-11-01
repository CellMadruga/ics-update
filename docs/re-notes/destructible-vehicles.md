# Destructible vehicles: why a networked CDestructionComponent object is not drawn (2026-10-26)

Source: static analysis of the client exe (REA / Ghidra and a local capstone read of the same image; VA, image base
0x400000; diag RVA = VA - 0x400000), the packs of the player's install (throw-away scripts in the session scratchpad,
nothing copied), and the tester's logs of 16:17-16:22 (`vitrina 27 p3`, `27 p`, `12 p`). Tags: **C** confirmed (code
/ data read), **P** probable, **G** guess, **O** open. Builds on `full-entities-engine.md` 4.2, `crime-alley-props.md`
A.1, `actor-creation-and-environment.md`, `full-protocol.tsv` (events 0x8B / 0x10D / 0x138).

## 1. Short answer

- An object whose record chain has property `0x800` (destruction record, DB type 0x4E) gets the **destruction variant
  of the RenderComponent** (slot 5: creator `0x604920` -> `0x626FC0`, vtable `0x15C94D0`, size 0x140) instead of the
  normal one (`0x604990` -> `0x626DC0`, vtable `0x15C9440`). The destruction variant draws **nothing of its own**: its
  draw / update methods walk the destruction component's **active piece list** (`comp+0x10`, count `comp+0x18`) and
  draw each piece's render sub-object (`piece+0xD0`) (C: `0x622610`, `0x6224D0`, `0x622550`; its construction step
  `0x623A40` just stores entity+0x58 = the destruction component in render+0x138).
- The client fills that list by itself **only for creation types 6 and 9** (the immobile ones). Every local build path
  checks `entity+0x114` (the creation type, the value `0x580160` turns into mobility) for 9 or 6 before it calls the
  intact-piece builder `0x630650` (C: `0x630FC0` at `0x631004`, `0x630BF0` at `0x630C17`). Crime Alley's vehicles are
  creation type **8** (UniqueDynamicMobile, needed for the movement component that places them), so **no piece is
  ever built, and the object is created, placed and invisible**. That matches every test: entity class, bare world
  state, carrier + 0x800, cell 0xFB, re-sends; and `liftable_creation_type` 7 (also not 6 / 9).
- For a mobile destructible the pieces come from the **server**: three S2C events build them (C, `full-protocol.tsv`):
  - **0x8B** (exec `0x6982B0`, serializer `0x839DD0`, handler `0x631050`): `u8 0 | u64 IID`. Looks the IID up in the
    entity manager (`[0x1B67258]` vt+0x58), clears the pieces (`0x62ED50`, `0x62BE90`), **builds the intact pieces
    from the record with no creation-type check** (`0x6303F0`: one piece per entry of record+0x50 / count +0x58, pushed
    into the active list `comp+0x10`), applies the record's model part list (`0x62EB40(record+0x74, record+0x470)` ->
    model component vt+0x5C), then `0x630FC0(0)`: sets `comp+0x80` = built and, with pieces present, creates each
    piece's physics body at the entity's frame (`0x62DBA0` -> `0x62CFE0`, `0x5CD300`) and its **render instance**
    (`0x62C490` -> `0x7E3460(piece, 0x200, ...)` at `0x62C4EA`). This is the "reset to intact" message. The catalog's
    name "Refresh appearance/model of object" is this.
  - **0x10D** (exec `0x697EE0`, handler `0x630160` -> `0x62FB20`): one object's saved piece state (piece id `+0x2C`,
    Position `+0x04..+0x28`, motion state `+0x34` = 0 / 2 / 3 / 4, flags `+0x30`, `+0x38`; entries of 0x3C, count at
    state+0x10, bit mask at state+0x18). Used for broken / moving pieces (O: full layout).
  - **0x138** (exec `0x697F70`, handler `0x631550`): the list of all states at join, kept in the global list
    `0x18628CC` (count `0x18628D4`) so an object created later picks its state up in `0x630650` (C).
- So the missing step is **event 0x8B to each vehicle after it is placed**. No property, scriptlet, LifeState or
  phase is involved in drawing (C for the render path; P that 0x8B alone is enough, see 4).

## 2. Data checked (C)

| What | Value |
|---|---|
| Truck world state `0x2E000F04` (`.entity 0x2D000C8F`) | 0x7D2 = [0x1D000612, 0x1D00034B, 0x1D000111], 0x93D = 1, 0x1000060E = 0x14, **0x800 = 0x500001F0**, 0x7EB = 8, 0x402 = 1, 0x2A4 (no value), 0x83C = 1, **0x50F = 8**, 0x8C1 = 6, 0x1000019D = 0x1000, 0x83E = 1; one model 0x17000847 |
| SUV world state `0x2E000559` (`.entity 0x2D0003FC`) | same keys, 0x1000060E = 3, **0x800 = 0x5000000A**, 0x50F = 8; models 0x170004AE, 0x170006F0 |
| Tutorial 1 street vehicle `0x2E000AAB` (drew via carrier) | 0x50F = 5, 0x7D2 = [0x1D000199], 0x7EB = 0x11, 0x2A4 = 1; **no 0x800** -> normal render component, drawn from its .entity model |
| Meteorite `0x2E000D22` (draws) | 0x50F = 7, 0x93D, 0x7EB = 7, 0x2A4; **no 0x800** |
| Showroom list (148 Crime Alley world states, types 3 / 7 / 8 / 9) | only the seven vehicle world states (`0x2E000559`, `795`, `8B8`, `EFE`, `F03`, `F04`, `F05`) have 0x800; nothing that drew had it |
| Destruction record `0x500001F0` (DB type 0x4E) | in 0xA000024C and in Crime Alley's 0xA00002E5 (38,948 bytes); aligned DID references 0x19000E3C and 0x1700017E, both present in 0xA00002E5, so the data is loadable on Crime Alley (the 0x800 fix loaded it: no crash) |
| Static placements | `0x2E000559` is referenced only by its own record, template `0x49000454` (packs 0xA000009A, 0xA00000FC) and the shared vehicle table `0x1D00067A` (0xA00002E5); the other hits (0x100011D2, 0x10001D45, 0x100012CA, 0x160002C8) are unaligned noise. No landblock static of Gotham Divided or Crime Alley places a vehicle: the original server spawned them (agrees with `map-object-census.md`) |

## 3. Client code (C unless tagged)

| Address | What |
|---|---|
| `0x606400` | component creation; slot 22 CDestructionComponent (`0x604E60` -> `0x62E310`) and the render variant `0x604920` when `0x57FF30` finds property 0x800 |
| `0x57FCD0` | destruction component loads record 0x800 (`0x556470`, DB type 0x4E via `0x5DFBA0`) into comp+8; failure 0x80004005 |
| `0x62F960` (comp vt+0x24, OnEntityConstruction) | loads the record; if `comp+0x80` == 0: `0x4E1100(record)` (any piece def with flag bit 13 at def+0x49C) and `0x62EA60(record+0x74, record+0x470, 0 or 4)` = the record's model part list onto the CModelComponent (entity+0x18, `0x61AF40` -> `0x6086B0`); entries {record+0x474, part, 2} (`0x62E9D0`) |
| `0x630490` (vt+0x30) | OnAttach: registers the component in the global destruction list (`0x9760A0`) |
| `0x6305A0` (vt+0x70 loop) | per-frame update ("CDestructionComponent" profiling scope): active pieces, then the removed list +0x20 / +0x28 |
| Component lists | `+0x10` / `+0x18` active pieces (drawn), `+0x20` / `+0x28` broken-off / removed, `+0x30` (record+0x28 entries of 0x38, damage effects P), `+0x34` listeners, `+0x80` u8 built, `+0x81` registered |
| `0x62F540` | new piece (0x1A0 bytes, ctor `0x62F0D0`) on the list in ECX; +0x40 = piece def (record+0x30 + index * 0x5D0), +0x44 = def+0x498, +0x194 = def+0x49C, +0x198 = component; +0x188 = physics body, +0x15C = render instance |
| `0x630650(frame)` | intact build at a frame: if the entity's IID is in the 0x138 list -> `0x62FB20`; else one piece per record+0x50 entry, bodies at the frame (`0x57FF60`), then the part list, and `0x588A00(entity, 0x14)` for mobility 1 |
| `0x630FC0(arg)` / `0x630BF0(parent, arg)` | "entity entered the scene / was attached": **build only if comp+0x80 == 0 and entity+0x114 is 9 or 6**; then +0x80 = 1 and, with active pieces, bodies + render instances (`0x62DBA0`, `0x62C490`, `0x62EFC0`; attached branch `0x7602A0`, `0x62C030`). Callers: `0x75A500` (scene registration, P), `0x6239A0` (render variant vt+0x68), `0x631050`, `0x630650`, `0x62FB20` |
| `0xA5A8E0` (vtable `0x1602A04` +0x18) | game-layer pending-frame list (entries of 0x58, property 0x1000059C default 60): sets the frame (`0x588290`, mode 5) and calls `0x630650` for any creation type (O: who fills it; not reached by our objects) |
| `0x631050` | event 0x8B handler (above) |
| `0x62C490` | per active piece without a render instance: `0x7E3460(piece, 0x200, 0, 0, 0, 0, 0, arg)` (call at `0x62C4EA`, ESI = piece) |

Creation types for reference (`actor-creation-and-environment.md`): mobility `0x580160`: 1->1, 2->1, 3->3, 4->1, 5->1,
6->1, 7->2, 8->2, 9->3; only mobility 2 gets the movement component that places a network object. So a networked
destructible has to be type 7 / 8 to be placed and 6 / 9 to build its own pieces: no type does both, and the server
must send the pieces (0x8B / 0x10D).

## 4. Server recipe

1. **Class** (C): the vehicle's own entity class (`0x4000081B` truck, `0x40000454` SUV, ... `crime-alley-props.md`
   A.1) or the bare world state; both carry 0x800 through the world state and creation type 8. **The carrier is not
   needed** (and its template lacks 0x800). Keep the 0xB0 module (`0x62 | 1 | 1`), a valid Position, cell 0xFB as for
   other props. Do not override 0x50F (7, 6 or 9 all break placement or pieces).
2. **0xBC** (C for drawing: none needed beyond what the class gives). For Super Strength keep the late flags
   (0x1000019D = 0x1080, 0x10000AA7, 0x10000029, LifeState 4) as `liftables.py` already does.
3. **Event 0x8B to the vehicle** (P, the step that was missing): `build_message(ent.eid, 0x8B, b"\x00" +
   struct.pack("<Q", ent.eid))`, i.e. dest = the vehicle IID, body `u8 0 | u64 vehicle IID`. Send it **after** the
   create bundle has been applied (the pieces' bodies are made at the entity's current frame, `0x62DBA0` reads the
   entity's Position; an IID the client does not have yet is ignored with 0x80004002): e.g. 0.3 s after the bundle and
   again with each `liftable_resend` / `carrier_resend` while the vehicle is intact (0x8B clears and rebuilds, so it
   is idempotent; never after a throw or a break, it would restore the intact model). In ics: `w.send(label,
   M.build_message(...))` after `w.update(ent, ...)` in `ics/match/liftables.py` spawn and `ics/match/tour.py`
   showroom, behind a config key (`[ics] destruction_reset_event` = true, `destruction_reset_delays` = [0.3, 1.0,
   3.0]).
4. **When it breaks** (G): the explosion path (`0x3400015F` S2 / S4: Vfx_OnExplode, DestructionImpulse, DestroyEntity)
   is scripted; the client's own break code works on the active pieces once they exist (`0x6316D0` vt+0x60 detaches a
   piece). If the pieces should fly apart as in the original, that is a 0x10D state per break (O). Removing the object
   (0x3) after DestructionDelay is enough to start with.
5. **Respawn** (P): the SUV's "yellow translucent" respawn (images 16 / 17) = a new object + 0x8B again.

Confidence: **high** that the missing pieces are why nothing draws (C: the render variant only draws pieces; the
6 / 9 gate is explicit). **Medium-high** that 0x8B alone builds a visible intact vehicle (C path, P runtime: the
bodies need a valid entity frame, and `0x7E3460` was not traced further).

## 5. Diag breakpoint set (tools/diag.py, to add; not added by this note)

A new mode `--destruction`, written as `--create` is (RVA keys; nested reads and `q[...]` as in tracer.py):

```python
    if "--destruction" in sys.argv:
        # Destructible vehicles (docs/re-notes/destructible-vehicles.md, 2026-10-26): at which step a
        # CDestructionComponent object drops out. comp = the destruction component (entity+0x58).
        bps.update({
            0x22F960: ("DEST start 0x62f960", [("comp", "ecx"), ("entity", "[ecx+4]"), ("record", "[ecx+8]"),
                                               ("built", "[ecx+80]")]),
            0x230FC0: ("DEST build check 0x630fc0", [("comp", "ecx"), ("built", "[ecx+80]"), ("pieces", "[ecx+18]"),
                                                     ("ctype", "[[ecx+4]+114]"), ("arg", "[esp+4]")]),
            0x230BF0: ("DEST build check (attached) 0x630bf0", [("comp", "ecx"), ("built", "[ecx+80]"),
                                                                ("pieces", "[ecx+18]"), ("ctype", "[[ecx+4]+114]")]),
            0x230650: ("DEST intact pieces at a frame 0x630650 (types 6 / 9)", [("comp", "ecx"), ("frame", "[esp+4]")]),
            0x231050: ("DEST event 0x8B reset 0x631050", [("iid", "q[esp+8]")]),
            0x230453: ("DEST intact pieces built 0x6303f0", [("comp", "esi"), ("pieces", "[esi+18]"),
                                                            ("record_pieces", "[[esi+8]+58]")]),
            0x22FB20: ("DEST state 0x10D / 0x138 applied 0x62fb20", [("comp", "ecx"), ("state", "[esp+4]"),
                                                                     ("count", "[[esp+4]+10]")]),
            0x22C4EA: ("DEST piece render instance 0x62c4ea", [("piece", "esi"), ("def", "[esi+40]")]),
        })
```

Reading it (built is a byte: look at the low byte):
- Today (no 0x8B): expect `DEST start` and `DEST build check` with ctype 8 and pieces 0, and no `intact pieces` /
  `render instance` line: the drop-out step.
- With 0x8B: `DEST event 0x8B` -> `intact pieces built` (pieces = record_pieces > 0) -> `build check` (arg 0) ->
  one `piece render instance` per piece. Pieces > 0 but no render instance = the frame / body step (`0x62DBA0`);
  no `event 0x8B` line = the message was not delivered (dest or body wrong).
