# Client script instances for skill slots, and the 0x200F crash (static analysis, 2026-10-23)

Exe `InfiniteCrisis.exe`, VA (image base 0x400000). **C** = read in the code (Ghidra 12.1.4 via REA + capstone),
**P** = probable, **O** = open. Trigger: fase3-hh sent 0x200F (ics `messages.effect_add`) per kit-slot script of
Atomic Green Lantern at load complete; the client died with 0xC0000005 at VA 0x448BE3 (fase3-hi).

## 1. The crash: every network-created script instance faults in its constructor (C)

Call chain (the diag stack is exact, it is not stale):

| Return address | In | What |
|---|---|---|
| `0x843DAB` | `0x843D60` (0x200F / 0x2062 body serializer) | archive flag bit 0 clear (= reading) -> `0x83D530` |
| `0x83D56B` | `0x83D530` | releases the message's instance, `0x838F80(..., 0x56, &out)`, then `0x44C480` reads the body |
| `0x838FE7` | `0x838F80` | TLS allocator `alloc(0x1EC, pool, tag 0x56 "HFSM", 0)`, then **default ctor `0x44BD00`** |
| `0x44BD95` | `0x44BD00` | `[inst+0xC] = 0` (script record pointer), ..., `0x461510(inst+8)` on the variable store `inst+0x70` |
| `0x461586` | `0x461510` | appends the listener `inst+8` to `[store+0xB8]`, then calls listener vtable slot 2 |
| fault | `0x448BE0` | `mov eax,[ecx+4]` (= `[inst+0xC]` = **0**); `mov eax,[eax+0x44]` -> AV reading 0x44 (eax = 0 in the dump) |

`inst+8` has vtable `0x15A8190` (`[0]=0x44BDB0, [1]=0x44A0F0, [2]=0x448BE0`); slot 2 returns the record's
event-id list (`record+0x44`), which `0x461360` merges into the store's sorted accepted-event list (`store+0xD8`).
The two other constructors of the same class set the record **before** `0x461510`: `0x44D730(…, record, addref)`
and `0x44D800(…, scriptDID)` (`0x5DFBA0(did,7)` -> `0x43A1E0`). Only the network path uses `0x44BD00`, whose
record is filled later by `0x44C480` -> `0x44B090` (the DID field), too late.

Consequences (C): the fault happens **before a single byte of the instance body is read**, so it does not depend
on the script (skill or status), the GUID, the variable store or `fresh`. `0x200F`, `0x2062` (`0x843D60`) and the
list forms `0x200C` / `0x2043` (`0x8431xx`: `0x843254` -> `0x838F80`) all go through `0x838F80` -> `0x44BD00` and
crash this build. `status_mirror` was never enabled, so "status 0x200F works" was never observed. The only callers
of `0x44BD00` are `0x838FE2` (C, call scan), i.e. this path is dead in the shipped client; the original server can
not have used it with this exe (P).

## 2. How the client gets skill-slot instances: it creates them itself (C)

Effects / HFSM component (`entity+0x8C`, getter `0xAA1A60`, list `+0x20` / count `+0x28`):

- **Add by DID `0x9789C0(scriptDID)`**: `0x5DFBA0(did,7)` -> record; `component->vt+0x4C(record)` (accept?);
  `record->vt+0x68()` creates the instance with the record set; `0x976A80` appends it (same list 0x200F uses);
  `0x4490E0`; if the instance listens to `0x10000009`, `0x9756E0`.
- **Component init `0xA9F9F0`** (vtable method, any entity): `0x9798E0` adds the scripts listed by
  `0x44C620(entity)`, registers slot listeners 1-5 (`0x85D550`), then **`0x979860`** adds every DID returned by
  **`0xA39B00(entity)`**.
- **`0xA39B00(entity, out)`**: for slots 0..15 reads the slot skill table (`0x58B320` with the ids of table
  `0x15EDA28`: `0x100008E3`, `0x100008E8`, ...); from each skill takes **property `0x1000063A`** (DID, kind 0x15 =
  a 0x34 script); if absent and targeting type `0x1000003D` is not 0 / 5 / 9 (and its kind is 8 / 0xA), a default
  built by `0x439E00(0x1000005B, 0xF)` (O: which DID). `0x85F1E0(skill)` is the single-skill form.
- **Slot changes (local player)**: property listeners `0xA5DF80` / `0xA5E0A0` / `0xA5E150`: prop `0x100000AF`
  (ranks) -> `0xA3A050` (HUD refresh of slots 0-5, 7-15); a slot property (`0x85D100`) -> `0xA4F6B0(old, new)`
  (remove the old slot script `0xA3A0E0`, add the new one with `0x9789C0` unless present, `0x96DF50`) or
  `0xA4F750` (removal: posts `0x10000009` to it, then `0x976BF0`); `0x10000167` (level) -> refresh all.
- Node client halves can also start client instances: StartScriptOn `0x10000030` / `0x10000081` (vt `0x15FBD84`,
  execute `0x9C78B0` -> `0x9C4A80` -> `0x9789C0`, then event `0x10000085`); `0x100000A0` / `0x10000155` / `0x10000168`
  (vt `0x15FE33C`, `0x9C76C0` -> `0x975850`, a 0x108-byte handler object in list `+0x84`). HUD / UI instances use
  `0x44D8C0(did)` (callers `0x6A601A`, `0xA741C3`, `0xA7902B`).

**0x20C9** (`0xA1D400` -> `0xA16E60(agent, slot, event)`): `0x861580(agent, slot)` = the slot skill's
**`0x1000063A`** (same default rule), *not* `0x10000328`; `0x96DED0(event, did)` walks list `+0x20`, compares
`instance->vt+8` (`0x448B90`: `[record]+0x14` = DID) and queues with `0x461430`. Data: `0x1000063A` occurs 114 times
in the packs, mostly `0x3400020B` (60), `0x34000438` (12), `0x340001A8` (8), `0x340001A3` (6), `0x34000735` (6):
the **targeting-indicator** scripts (targeting-indicator-and-structures.md 1c). So the client copy of a slot is a
presentation script for the aiming decal, and `0x10000328` (the cast script) is never instantiated on the client.

## 3. Why started 0x8D scriptlets can still show nothing (C path, causes P/O)

Visuals of a cast are the server's 0x8D only. After `0x6279D0` returns 0 (started), each action runs:
- action 0x14 (raise graph event) `0x672930`: event = literal or variable `0x780` (kind 8 / 0xA); entity via
  `0x514D20` (fail -> `0x6729C7`, 0x80004005); **if `[entity+4]` (behaviour-graph component) is 0 the action
  returns success silently** (`0x6729A2`); else `vt+0x58` = `0x55BD30`;
- `0x55BD30`: **dropped** (`0x55BDAA`) when `[entity+0x118]` has bit 0x40 and not bit 8; queued (`0x55BD82`) while
  the graph is not ready (`vt+0x50`); delivered by `0x55AF70`, which maps the global id with `0x5590E0`: **-1 = the
  champion's graph has no such event** (return at `0x55AF83`), else the Havok graph gets it.
- Every action type checked allows network starts (`vt+0x48` = `0x9C3A20` `mov al,1`): types 1, 4, 0xE, 0x14, 0x17,
  0x1B, 0x20, 0x22.

## 4. diag probes (rva = VA - 0x400000)

| rva | log |
|---|---|
| `0x5789C0` | add-by-DID: `[esp+4]` = script DID (which slot instances exist; expect `0x1000063A` values at load) |
| `0x576A80` | instance appended (`[esp+4]` = instance) |
| `0x616E60` | 0x20C9 local: `[esp+8]` slot, `[[esp+0xC]+8]` event |
| `0x56DED0` | event fan-out: `[esp+8]` = DID searched, `[ecx+0x28]` = instance count |
| `0x2729A9` | graph event reaches the graph component: `esi` event, `ecx` component (0 never reaches here) |
| `0x27299D` | `[eax+4]` = graph component of the target (0 = silent no-op) |
| `0x15BD30` | `[[ecx+4]+0x118]` entity flags, `[esp+4]` event |
| `0x15BD43` / `0x15BD82` / `0x15BD9F` | bit 0x40 set (dropped unless `al & 8`) / queued (graph not ready) / delivered |
| `0x15AF83` | `eax` = graph-local index (-1 = unknown event for this graph) |
