# Costume shows the base model over it: client-side analysis and fix (2026-10-25)

Follow-up of `costume-model-overlay.md` (hypothesis: a second visual built from the base). C = confirmed, P = probable,
O = open. Exe addresses with base 0x400000.

## 0. Starting points (from earlier notes)

- Event `0x4` batch: `0xF2` (class, parent IID, sequence; reader `0x54BD00`), `0xB0`, `0xBC`.
- Create handler `0x64D8A0` -> factory `+0x40` `0x54B790` -> `0x54AD90` -> `0x54F1F0` (template merge) ->
  `0x54F540` construction; step 1 `0x54B9A0` fails if the IID already exists.
- The ics server sends the champion's full `0x4` bundle on every change (`_objects`), not only at creation.

## 1. What the client does with a create bundle for an IID that already exists (C)

Dispatcher `0x64E070` (object-manager event handler): event `0x4` -> `0x64AB70` splits the batch and `0x64BD30`
re-dispatches each sub-event; sub-event `0xF2` -> `0x64D8A0` (after the landblock checks `0x635230` / `0x47FA70`).

`0x64D8A0(iid_lo, iid_hi, f2)` (this = object manager, ESI):
1. `0x64A3A0(iid)` = lookup in the live map `this+0x78` (returns 0 while `this+0x150` holds an entry with `+0x10 != 0`).
   **If the entity exists**: compare `f2+0x28` (the bundle's class) with `entity+0x110` (its class). Equal -> return 1,
   **nothing is built** (the 0xB0 / 0xBC sub-events of the same batch go to their own handlers as updates).
   Different -> `[0x1B67258]->vt+0x28` = `0x603E70` -> `vt+0xD4` (re-class of the live entity; O what it rebuilds).
2. Not live: `this+0x17C` entry removed (`0x5460F0`), the 0xB0 block is read (`0x649230`; no 0xB0 -> return 0).
3. **Already waiting for its landblock** (`this+0x1C4`, `0x649720`) -> return 1: the new bundle is dropped.
4. Landblock not ready -> queued in `this+0x1C4` (`0x64C310`), else `0x64CA10` -> factory `vt+0x2C` `0x607EE0` (with a
   0xBC table) or `vt+0x30` `0x607DC0` (without): an **asynchronous creation job** (0x110 bytes, ctor `0x7DFDE0`,
   job id = factory `+0x2C` counter), registered in `this+0x13C` by job id (`0x64C520`), not by IID.
5. The job ends in `0x54F1F0` (template merge) and construction; step 1 `0x54B9A0` asks factory `vt+0x58(iid)` and
   **fails `0x80004005` if the IID already exists**. So two jobs for one IID (a create re-sent while the first job is
   still running) give one entity; the second never reaches component creation (no second visual).

## 2. Missing class record at creation (C)

`0x54F1F0`, class of DB type 0x40: `0x478880(class)` fetches the class record; null -> log (WorldEntityFactory.cpp line
0x602) and fail `0x80004005`. Then `0x54BE10` takes its world state (`0x510`); none (`== [0x1B67260]`) -> fail. No
fallback to another class or variant. A create sent before the costume's pack is loaded fails outright; it can not
produce the base model.

## 3. The descriptor's third u32 is a world-state override, not a sequence (C)

`0x445970` (0xF2 sub-event reader): `+0x20` = the desc built by `0x54BD00` (class -> desc `+8`, u64 parent IID ->
desc `+0x38`), then **`+0x28` = the trailing u32** (ics `create_object(sequence=...)`, `struct "<IQI"`).
`0x64D8A0` compares that u32 with `entity+0x110` and, when different, calls factory `vt+0x28` `0x603E70` ->
`vt+0xD4` = **`0x54D5C0` ChangeWorldState(entity, ws)**: `0x5DFBA0(ws, 0x2D)` + `0x43A1E0` load the world state; null
-> fail, nothing changes; else detach (`0x54D410`, `vt+0xDC`), rebuild the components from the new world state
(`vt+0xD8`), `entity+0x110 = ws` (or `[0x1B67260]` "none" when ws is the class's own world state, `0x54CAF0`),
`vt+0xE0`, `0x54D4C0`, `0x588DC0`. A value equal to `[0x1B6AB20]` means "the class's own world state".
So `entity+0x110` is the world-state override (earlier notes: "class DID"; the class is desc `+8`).

ics sends 1, 2, 3 ... (incremented per bundle): every champion / unit bundle asks the client to switch the entity to
world state DID n. DB lookups use full DIDs (`0x478880` builds `0x49......` from the class), so DID n (no type
prefix) is not found (P) and the call fails harmlessly; it is still a world-state change request on every bundle.
`[0x1B67260]` / `[0x1B6AB20]` are BSS (set at run time): read them in diag before choosing the value to send. The
correct value is the one the entity holds after creation (`[0x1B67260]`, most likely 0): then the compare is equal and
the bundle is a pure update. Sending the costume's own world state would rebuild the visual on every bundle (it is
stored back as "none", so the next bundle differs again).

## 4. Verdict on the hypothesis (C for the client paths above)

- A create for a live IID builds nothing (section 1). Two creates in flight give one entity (factory step 1).
- A create whose class / template / world state is missing fails; no base fallback (section 2).
- So the 35 % create, the link, load-complete and idle re-sends can not make a base copy of the champion's IID.
  The base model must come from **another entity** (another IID: client-local 0x81 actor, a bot, a placement) or from
  **extra model parts / a world-state rebuild** on the champion. Section 5 tells them apart at run time.

## 5. Diag breakpoints (tools/diag.py)

| Address | When | Log |
|---|---|---|
| `0x54B9A0` | every entity construction (step 1) | IID `[arg2+0x10]`,`[arg2+0x14]`; class `[[arg2+4]+8]` |
| `0x54F1F0` | template merge | class `[arg2+0x30]` (`arg2` = creation info), result `[arg1]` on return |
| `0x64D8A0` | every 0xF2 | IID (arg1, arg2), `[arg3+0x28]`, `[[arg3+0x20]+8]` (class) |
| `0x54D5C0` | world-state change | entity IID `[arg2+0x100/0x104]`, new ws `arg3`, `[arg2+0x110]` before, return code |
| `0x61AEB0` | CModelComponent setup / rebuild | `ent=[ECX+4]`: IID `[ent+0x100]`, class `[[ent+0x108]+8]`, ws `[ent+0x110]`, parts `[ECX+0x50]` |
| `0x6A5AE0` | cinematic actor spawn | actor class `[actor+0xC]`, binding flag `[actor+0x14]`, bound IID |
| once | | `[0x1B67260]`, `[0x1B6AB20]` (the "none" world-state values) |

Expected: one `0x61AEB0` for IID `0x0200000000000002` (class `0x400003C7`) per rebuild. A `0x54B9A0` / `0x61AEB0` on
another IID with class `0x40000086` or world state `0x2E0001B2` names the overlay entity; a second `0x61AEB0` on the
champion after a `0x54D5C0` that succeeded points at the world-state field.

## 6. Fix (ordered)

1. Server: send the descriptor's third u32 as the client's "none" (`[0x1B67260]`, verify; 0 expected) for every object
   instead of the per-bundle counter; new `[ics]` key with the old behaviour restorable. Confidence: high that it is
   the protocol's meaning, medium that it changes the overlay.
2. Keep the 35 % create (a too-early create fails and the link create succeeds), or delay it to load complete; either
   is safe for the model (section 2).
3. Run section 5 once with a costume to find the second entity before changing packs.
