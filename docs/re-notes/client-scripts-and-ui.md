# Client-side logic (WLib scripts) and every UI screen: what the server must send (static analysis, 2026-10-22)

Client `InfiniteCrisis.exe` (image base 0x400000, all exe addresses are **VA**), the client script library record
**`0x39000001`** (pack `0xA0000038`) and the UI pack **`0xA00000D0`**. Nothing here was run against the client.
Tags: **[C]** confirmed from code or data, **[P]** probable (consistent evidence, one link missing), **[G]** guessed.

Companion notes: `progression-meta.md` (GM_Advancement, loadouts, account systems), `protocol-server-to-client.md`
(all 336 events + 44 network notices), `protocol-client-to-server.md`, `shop-items-inventory.md` section 5,
`champions-all.md` section 7, `ui_re.txt`, `reward_re.txt`. Flash AS2 dump: `old_files/tools/gfx/classes_all.txt`
(992 DoInitAction blocks = the AS2 code library). The method is in section 5.

---

## 0. Short version

1. **The client script library is one record, `0x39000001`** (the only DB type `0x39` record): a compiled class library
   ("WLib") with 4-byte-word bytecode, 159 classes (785 type slots), 708 methods, 376 debug strings, 242 distinct natives
   called. Format, instruction set and class table: section 1 [C].
2. **Skill ranking without exe patches [P, strong]:** the six GM_Advancement handlers are *static* methods of WLib class
   `0x233`; no instance of `0x233` is needed. They are registered by method `0x9654` (class `0x233` slot 18), which is
   called from exactly one place: the **player script** (class `0x137`, inherited by the player class type `0x21C`),
   slot 198 (`0x84DC`). That slot is reached only from the **script RPC handler** class `0x1A1` method id 11
   (`0xC164`), i.e. from the server: **event `0x9F` to the local player `0x0200000000000001` with message
   `0x81A1000B`** (empty blob). No client code, no exe immediate and no shipped data starts it, which is why it never
   ran in our sessions. After that the "+" goes to the server as **event `0x9F`, message `0x81910003`**
   (class `0x191`, `u32, u32, u64`), and the original server answered with **`0x9F` message `0x81910001`** (handler
   `0xBEBC` -> `0x233` slot 21 -> `GM_Advancement.RecvNotice_SkillRanked`). Section 1.7.
3. **Script RPC (event `0x9F`) is the general client<->server channel of the client scripts** [C]: 38 client->server
   stubs (admin commands, emotes, skill rank, agent and player requests) and 12 server->client handlers (section 1.6).
   `ics` handles none of them.
4. **The UI is 82 GFx movies** stored as DB type `0x20` records in pack `0xA00000D0` (plus the AS2 code library
   `0x20000025`, a CWS SWF of 3.1 MB). Every screen, its classes, its singleton managers, the C++ notices it listens
   to and the network events that feed them: section 2 [C for the Flash side, P for the event mapping].
5. **Screen-by-screen server requirements vs. `ics`**: section 3.

---

## 1. The client script library (WLib, record `0x39000001`)

### 1.1 Where and container format [C]

- Record `0x39000001` in pack `0xA0000038`, decompressed stream offset `0x102378`, **length `0x27074`** (160 kB; the
  old `rp_index.tsv` length 136061 is wrong, it cuts section `0x10`). DB type `0x39` = "WLib object", class `0x47A350`,
  Unpack `0x478900` (`db-types.md`). Only one `0x39` record exists in all packs.
- Header: `u32 did | u32 0x1A015342 ("BS" + 0x1A01, version magic) | u32 0x26 | u32 0x015E1591 (build stamp?)`,
  then sections `u32 0xFEDC1234 | u32 section id | u32 size | payload`, closed by a second `0x1A015342`.
  Loader `0xAE9BB0` / `0xAE9800`, section switch `0xAE99D0`:

| Section | Offset in record | Size | Loader (exe) | Content |
|---|---|---|---|---|
| `0x1` | `0x10` | `0xE6AC` | `0xAE6700` | **code**: `u32 length (0xE6A8)` + bytecode (code offset 0 = record `+0x20`) |
| `0x2` | `0xE6C8` | `0x7CC4` | `0xAE8350` | **string table**: `u32 n (376)`, each `u32 len + UTF-16`, 4-aligned. Developer/console strings only (admin commands, error logs) |
| `0x10` | `0x16398` | `0xF590` | `0xAE8810` -> `0xAE7E40` | **type table**: `u32 n (785)`, then per type index a record or a null (section 1.3) |
| `0x40` | `0x25934` | `0xC` | `0xAE8BC0` | empty table |
| `0x200` | `0x2594C` | `0xAC4` | `0xAE9970` -> `0xAE9410` | hash table: type -> list of (field-name hash, field index, kind) = **field reflection** for the 67 classes that have fields |
| `0x400` | `0x2641C` | `0xC48` | `0xAE7C60` | `u32 n (785)` x `i32 parent type` (-1 = root) |

### 1.2 Bytecode [C unless marked]

- Instructions are 4-byte little-endian words: **low byte = opcode**, byte 1 = a small operand (value tag for pushes),
  high 16 bits = a signed operand (offset, slot, size). Some opcodes carry extra words. Length decoder `0xAE6400`
  (table `0xAE6470`): opcodes `0x01 0x0C 0x0D 0x0E 0x0F 0x10 0x14 0x15 0x16` = 8 bytes; `0x02` = 12; `0x57`,`0xD8`
  = `12 + 8n` and `0x58`,`0xD9` = `12 + 12n` (`n` = word at +8: switch/jump tables [P]); all others 4 bytes. A linear
  sweep of the 0xE6A8 bytes with these lengths ends exactly at the end (10 846 instructions).
- Link pass `0x46C420` (jump table `0x46C504`/`0x46C518`) rewrites operands after load: `0x0C` type index -> type
  descriptor (table `0x1B588DC`); `0x0E` id -> C++ class via `0x486A90`; `0x15` native id -> function pointer (lookup in
  the native table `0x1854558`); `0x16` code offset -> absolute (code base `0x1B588D4`).
- Interpreter **`0x472B40`**, dispatch `jmp [op*4 + 0x47697C]` (224 handlers). Stack of 8-byte slots `{u32 value, u32 tag}`;
  tags seen: 1 object reference, 2 int, 3 float, `0x82` 64-bit int, `0x83` double [P for 0x82/0x83]. Frame stack
  of 12-byte records `{return ip, frame base, size}` capped at `0x97F4`.

Opcodes identified (enough to list classes, calls, natives and sends):

| Op | Meaning |
|---|---|
| `0x00` | no-op (fetch next) |
| `0x01` | push imm32 (next word) with tag = byte 1. With tag 2 and bit 31 set the value is a **function reference** `0x8000 \| type << 16 \| method id` |
| `0x02` | push imm64 with tag |
| `0x03` | push sign-extended imm16 (high half of the word) with tag; `0x04` same, 64-bit [P] |
| `0x05`/`0x07` | push int 0 / 1; `0x06`/`0x08` the 64-bit forms; `0xB6`/`0xB7` push -1; `0xB8`/`0xB9`/`0xBA` float/double constants |
| `0x0A` | pop [P] |
| `0x0C` | **new instance of a WLib type** (operand = type index; runs its constructor). Only 3 uses (types `0x127`, `0x12D`) |
| `0x0E` | **new native (C++) object** of class id (e.g. `0x83` = argument stream, `0x29`, `0xCB` = string) |
| `0x0F` | push string literal (string table index) |
| `0x10` | method entry: low 16 = locals bytes, high 16 = argument bytes (8 per argument). Every method starts with it (708) |
| `0x11` / `0x12` / `0x13` | return value / return 2-slot value / return |
| `0x14` | **virtual call**, operand = vtable slot of the object on the stack (`0x46A550`) |
| `0x15` | **native call**: high 16 of the word = argument bytes, next word = native id (`0xGGGGNNNN`) |
| `0x16` | **direct call** to a code offset |
| `0x43` / `0x44` / `0x45` | load argument / local / `this`-like slot (signed index in the high half) [P] |
| `0x54`, `0x99`, `0x9A`, `0xDA` ... | branches / compares (high half = offset) [P] |

### 1.3 Classes (type table, section `0x10`) [C]

Per type index `i` (0..784): `u32 0` = no type, or `u32 1 | u32 i | u32 nFields | nFields x 8 bytes (field defs) |
u32 n0 | n0 x u32 | u32 nSlots | nSlots x u32 code offset (vtable, 0xFFFFFFFF = none) | u32 nMap | nMap x u32 slot`.
Parsing this way ends exactly at the section end with **159 classes**. Slot 0 is the constructor.

- **Vtable** = all methods, inherited slots repeat the parent's code offset.
- **Map** = the class's *exported method ids*: method id `m` -> vtable slot `map[m]` (`0xFFFF` = none). A function
  reference `0x8000|type<<16|m` and every C++ call into a script use these ids, not slots: `0x4A5440(stack, fnref)`
  resolves `type` -> `map[m]` -> `vt[slot]` -> runs `0x46AE70` (VM). C++ calls an *interface* method on an object with
  `0x4A8D70(stack, object type, ref)`: the slot comes from the interface type's map, the code from the object's vtable.
- C++ only references interface/system method ids of types `0x62` (31 ids, `0x4A7016`..`0x4A7B3A`, `0x4B4ADC`..),
  `0x74` (4), `0x87`, `0x54` (`0x522213`), `0x10` (7, `0x6B354F`..), `0x8` (ContextMenuSystem, `0x6B34A3`), `0xF3`.
  None of them reaches class `0x233` (scan of every `push imm32` in the exe that resolves to a method).

**How instances are created** [C]:
1. **Entity class records**: a `0x40`-`0x47` record carries its WLib type at `+0x14` (`did | 2 | 0 | 0 | 0 | type | 0x1A ...`);
   `0x471E60(did, ...)` (exe) creates the script instance when the object is created. Types used by shipped class
   records (544 of 2015 class records have one): `0x27B` 312 (champions, e.g. `0x40000086`), `0x143` 101, `0x145` 34,
   `0x26D` 33, `0x223` 31, `0x250` 15, `0x27A` 6, `0x301` 6, `0x224` 2, `0x2C1` 2, `0x7` 1, **`0x21C` 1 (`0x4000007C`, the
   player)**. No record uses `0x233`.
2. **Deserialization** of a script object reference inside an event or record (`0x472330` / `0x472130`, type index read
   from the stream), and the argument-stream natives `0x830003`/`0x830008`.
3. Opcode `0x0C` (types `0x127`, `0x12D` only) and `0x0E` (C++ objects).
4. Static methods need no instance: natives that register handlers (group `0xE7`, `0xE9`) store function references.

### 1.4 Natives [C]

- Registration: `0x6B2E10(id, func)` appends to two parallel arrays (`0x1854560` ids, `0x1854564` functions, count
  `0x1854558`); **1978 natives** are registered (pattern `push func; push id; mov ecx,..; call 0x6B2E10`), mostly in
  `0x6B7470`-`0x6BE8D9` and `0x965D9C`-`0x966C6B`. The id is `group << 16 | index`. No names are stored.
- The WLib calls **242** of them. Most used groups (calls): `0xC6` 272 (string/print), `0xA3` 139 (admin command args),
  `0xE` 107, `0x83` 91 (argument stream), `0xCB` 80 (strings), `0xAF` 65, `0x29` 62 (properties / arrays), `0xC2` 38
  (script RPC send), `0x97` 28, `0x36` 23, `0xC8` 22, `0xBE` 19 (type checks, e.g. `0xBE0009` IsA), `0xC9` 19,
  `0x17` 18, `0x86` 18, `0x31` 16, `0xD5` 15, `0x99` 14, `0xE7` 14 (advancement), `0x105` 12 (skills).
- Known natives: `0xE70006/07/09/0A/0C/0D/0F/10/12/13/17/18` register/unregister the GM_Advancement handlers
  (`0x962E00`..`0x9631D0`, see `progression-meta.md` 1.2), `0xE70015` raise SkillRanked (`0x963040`), `0xE90010`/
  `0xE90011` register/unregister another handler (`0x9634D0`/`0x963630`), `0xE90007` (`0x963560`), `0x105000A`
  GetSkillRank (`0x84A830`), `0xF80001` local controlled agent (`0x84AE10`), `0xC90001` IID of a handle (`0x48BFB0`),
  `0xBE0009` IsA(object, type) (`0x48B090`), `0x340001` DID by key (`0x487AD0` -> DB manager vt+0x30), `0x720018`
  clamp (`0x488990`), `0x27C0002`/`0x2800001` send load-complete notice `0x1000015E` (`0x962240`), `0xC2000C`/`0xC2000D`
  **send script RPC event `0x9F`** (`0x4A1C90` -> `0x5624F0`), `0xC50001` (`0x48BA60`), `0xD50006`/`0xD5000B`,
  `0xE0004` (other senders, `protocol-client-to-server.md` 2d).
- Argument stream (native class `0x83`): write `0x830004` u32, `0x830005` u64, `0x830003` object reference; read
  `0x830009` u32, `0x83000A` u64, `0x830008` object reference, `0x83000D` begin/end; `0x830001/6/B` 4-byte and
  `0x830007/C` 8-byte variants (float/double [P]).

### 1.5 Network sends from the scripts [C]

Natives that reach the network send `0x444A90` (call-graph depth <= 6): `0xC2000C`, `0xC2000D` (event `0x9F`),
`0xC50001`, `0xD50006`, `0xD5000B`, `0xE0004`, `0x27C0002`. Classes that reach them (directly or through calls):
`0x143`, `0x160`, `0x18E`, `0x18F`, `0x190`, `0x191`, `0x197`, `0x19A`, `0x1A1`, `0x22C`, `0x22D`, `0x22E`, `0x230`,
`0x232`, **`0x233`**, `0x251`, `0x28F`.

### 1.6 Event `0x9F` = script RPC, both directions [C]

- **Client -> server**: native `0xC2000C`/`0xC2000D` (`0x4A1C90`) builds event `0x9F` (`0x5624F0`, base vtable
  `0x15A7DA0`, id `0x9F`) with `u32 message` (a function reference `0x8000|type<<16|method`), the argument-stream blob
  and the target object. Wire body as in `protocol-server-to-client.md`: `u8 0 | u32 message | u32 n | n bytes` [P for
  the blob framing]. The blob is the typed values written by the `0x83` natives (u32 / u64 / object reference).
- **Server -> client**: exec `0x568100` -> `0x567ED0`. If bit 31 of the message is clear, the target object's C++
  vtable `+0x54` handles it. If set, the blob becomes an argument stream (`0x83`), the stream and the target's script
  object are pushed and **`0x4A5440(stack, message)` runs the exported script method** of the class named by the
  message [C]. The handlers first check the target type with `0xBE0009` and return `0x38` if it does not match.
- The client copy of a server-side RPC body is a stub (e.g. `0xBEAC` returns 0): the WLib is shared with the server,
  which ran the real body.

RPC classes (`0x18E`, `0x18F`, `0x190`: admin/debug server commands; `0x191`: skill rank; `0x197`: emotes; `0x19A`:
agent requests; `0x1A1`: player requests; `0x1A5`, `0x251`): every exported method, generated from the type table.
"Called from" = client methods that call the stub (type:slot).

| class | method id -> slot | code | direction | blob (stream natives) | called from |
|---|---|---|---|---|---|
| `0x18e` | 1 -> 1 | `0xb5c4` | no stream access (empty client body; server-side implementation when a stub targets it) | - | - |
| `0x18e` | 4 -> 2 | `0xb1dc` | no stream access (empty client body; server-side implementation when a stub targets it) | - | - |
| `0x18e` | 5 -> 3 | `0xb014` | no stream access (empty client body; server-side implementation when a stub targets it) | - | - |
| `0x18e` | 6 -> 4 | `0xb36c` | no stream access (empty client body; server-side implementation when a stub targets it) | - | - |
| `0x18e` | 7 -> 5 | `0xb12c` | no stream access (empty client body; server-side implementation when a stub targets it) | - | - |
| `0x18e` | 8 -> 6 | `0xb234` | no stream access (empty client body; server-side implementation when a stub targets it) | - | - |
| `0x18e` | 11 -> 7 | `0xb4e4` | no stream access (empty client body; server-side implementation when a stub targets it) | - | - |
| `0x18e` | 14 -> 8 | `0xb684` | no stream access (empty client body; server-side implementation when a stub targets it) | - | - |
| `0x18e` | 16 -> 9 | `0xb54c` | no stream access (empty client body; server-side implementation when a stub targets it) | - | - |
| `0x18e` | 18 -> 10 | `0xb424` | server -> client handler | obj u64 | - |
| `0x18e` | 19 -> 11 | `0xaeec` | no stream access (empty client body; server-side implementation when a stub targets it) | - | - |
| `0x18e` | 20 -> 12 | `0xb0d4` | no stream access (empty client body; server-side implementation when a stub targets it) | - | - |
| `0x18e` | 21 -> 13 | `0xb07c` | no stream access (empty client body; server-side implementation when a stub targets it) | - | - |
| `0x18e` | 22 -> 14 | `0xb184` | no stream access (empty client body; server-side implementation when a stub targets it) | - | - |
| `0x18e` | 24 -> 15 | `0xaf54` | no stream access (empty client body; server-side implementation when a stub targets it) | - | - |
| `0x18e` | 25 -> 16 | `0xb2ac` | no stream access (empty client body; server-side implementation when a stub targets it) | - | - |
| `0x18e` | 29 -> 17 | `0xb6ec` | no stream access (empty client body; server-side implementation when a stub targets it) | - | - |
| `0x18e` | 30 -> 18 | `0xb024` | client stub -> server (event 0x9F) | obj obj | 0x4330(0x21b:298,0x22d:298) |
| `0x18e` | 31 -> 19 | `0xb49c` | client stub -> server (event 0x9F) | obj | 0x5be8(0x21b:296,0x22d:296) |
| `0x18e` | 32 -> 20 | `0xae94` | client stub -> server (event 0x9F) | obj u64 | 0x362c(0x21b:295,0x22d:295) |
| `0x18e` | 33 -> 21 | `0xb694` | client stub -> server (event 0x9F) | obj obj | 0x70d0(0x21b:289,0x22d:289) |
| `0x18e` | 34 -> 22 | `0xb314` | client stub -> server (event 0x9F) | u64 obj | 0x3510(0x21b:239,0x22d:239) |
| `0x18e` | 36 -> 23 | `0xafbc` | client stub -> server (event 0x9F) | u32 u64 | 0x6750(0x21b:258,0x22d:258) |
| `0x18e` | 37 -> 24 | `0xb62c` | client stub -> server (event 0x9F) | u32 u64 | 0x6054(0x21b:257,0x22d:257) |
| `0x18e` | 38 -> 25 | `0xb4f4` | client stub -> server (event 0x9F) | obj obj | 0x5b18(0x21b:215,0x22d:215) |
| `0x18e` | 40 -> 26 | `0xb13c` | client stub -> server (event 0x9F) | u64 | 0x5860(0x21b:228,0x22d:228) |
| `0x18e` | 41 -> 27 | `0xb0e4` | client stub -> server (event 0x9F) | u64 | 0x5c50(0x21b:251,0x22d:251) |
| `0x18e` | 42 -> 28 | `0xaefc` | client stub -> server (event 0x9F) | obj u64 | 0x5698(0x21b:217,0x22d:217) |
| `0x18e` | 43 -> 29 | `0xb194` | client stub -> server (event 0x9F) | obj | 0x418c(0x21b:288,0x22d:288) |
| `0x18e` | 46 -> 30 | `0xb55c` | client stub -> server (event 0x9F) | obj u32 u64 | 0x5de0(0x21b:256,0x22d:256) |
| `0x18e` | 47 -> 31 | `0xb08c` | client stub -> server (event 0x9F) | obj | 0x7394(0x21b:231,0x22d:231) |
| `0x18e` | 48 -> 32 | `0xb1ec` | client stub -> server (event 0x9F) | u64 | 0x4248(0x21b:286,0x22d:286) |
| `0x18e` | 50 -> 33 | `0xb244` | client stub -> server (event 0x9F) | u64 u32 u64 | 0x4ec0(0x21b:241,0x22d:241) |
| `0x18e` | 51 -> 34 | `0xb304` | no stream access (empty client body; server-side implementation when a stub targets it) | - | - |
| `0x18e` | 52 -> 35 | `0xb2bc` | client stub -> server (event 0x9F) | u64 | 0x7e4c(0x21b:309,0x22d:309) |
| `0x18e` | 53 -> 36 | `0xafac` | no stream access (empty client body; server-side implementation when a stub targets it) | - | - |
| `0x18e` | 54 -> 37 | `0xaf64` | client stub -> server (event 0x9F) | u32 | 0x81d4(0x21b:310,0x22d:310), 0x81f0(0x21b:311,0x22d:311) |
| `0x18e` | 56 -> 38 | `0xb3c4` | server -> client handler | u32 | - |
| `0x18e` | 57 -> 39 | `0xb61c` | no stream access (empty client body; server-side implementation when a stub targets it) | - | - |
| `0x18e` | 58 -> 40 | `0xb5d4` | client stub -> server (event 0x9F) | u32 | 0x801c(0x21b:319,0x22d:319) |
| `0x18e` | 59 -> 41 | `0xb3b4` | no stream access (empty client body; server-side implementation when a stub targets it) | - | - |
| `0x18e` | 60 -> 42 | `0xb37c` | client stub -> server (event 0x9F) | - | 0x8108(0x21b:321,0x22d:321) |
| `0x18f` | 2 -> 1 | `0xb854` | server -> client handler | obj obj obj u64 | - |
| `0x18f` | 3 -> 2 | `0xb844` | no stream access (empty client body; server-side implementation when a stub targets it) | - | - |
| `0x18f` | 4 -> 3 | `0xb7ec` | no stream access (empty client body; server-side implementation when a stub targets it) | - | - |
| `0x18f` | 7 -> 4 | `0xb8fc` | server -> client handler | obj obj | - |
| `0x18f` | 8 -> 5 | `0xb70c` | no stream access (empty client body; server-side implementation when a stub targets it) | - | - |
| `0x18f` | 14 -> 6 | `0xb6fc` | no stream access (empty client body; server-side implementation when a stub targets it) | - | - |
| `0x18f` | 18 -> 9 | `0xb7fc` | client stub -> server (event 0x9F) | obj | 0x44b4(0x21b:254,0x22d:254) |
| `0x18f` | 19 -> 10 | `0xb784` | client stub -> server (event 0x9F) | obj obj u64 | 0x4aa8(0x21b:211,0x22d:211) |
| `0x18f` | 22 -> 11 | `0xb774` | no stream access (empty client body; server-side implementation when a stub targets it) | - | - |
| `0x18f` | 23 -> 12 | `0xb71c` | client stub -> server (event 0x9F) | obj u64 | 0x4704(0x21b:240,0x22d:240) |
| `0x190` | 2 -> 1 | `0xbae4` | no stream access (empty client body; server-side implementation when a stub targets it) | - | - |
| `0x190` | 9 -> 2 | `0xbb94` | no stream access (empty client body; server-side implementation when a stub targets it) | - | - |
| `0x190` | 11 -> 3 | `0xbd7c` | server -> client handler | obj | - |
| `0x190` | 18 -> 4 | `0xb978` | server -> client handler | obj | - |
| `0x190` | 24 -> 5 | `0xbb3c` | no stream access (empty client body; server-side implementation when a stub targets it) | - | - |
| `0x190` | 29 -> 6 | `0xbd14` | no stream access (empty client body; server-side implementation when a stub targets it) | - | - |
| `0x190` | 33 -> 7 | `0xba8c` | no stream access (empty client body; server-side implementation when a stub targets it) | - | - |
| `0x190` | 34 -> 8 | `0xbcbc` | no stream access (empty client body; server-side implementation when a stub targets it) | - | - |
| `0x190` | 35 -> 9 | `0xba34` | no stream access (empty client body; server-side implementation when a stub targets it) | - | - |
| `0x190` | 38 -> 10 | `0xbde0` | server -> client handler | obj | - |
| `0x190` | 47 -> 11 | `0xbbec` | no stream access (empty client body; server-side implementation when a stub targets it) | - | - |
| `0x190` | 48 -> 12 | `0xbd6c` | no stream access (empty client body; server-side implementation when a stub targets it) | - | - |
| `0x190` | 49 -> 13 | `0xbba4` | client stub -> server (event 0x9F) | obj | 0x9070(0x232:85) |
| `0x190` | 53 -> 14 | `0xbd24` | client stub -> server (event 0x9F) | obj | 0x3cc8(0x21b:218,0x22d:218) |
| `0x190` | 59 -> 16 | `0xbb4c` | client stub -> server (event 0x9F) | obj | 0x9008(0x232:83) |
| `0x190` | 63 -> 17 | `0xbaf4` | client stub -> server (event 0x9F) | obj | 0x3b0c(0x21b:252,0x22d:252) |
| `0x190` | 65 -> 18 | `0xbc64` | client stub -> server (event 0x9F) | u64 obj | 0x382c(0x21b:300,0x22d:300) |
| `0x190` | 73 -> 19 | `0xba44` | client stub -> server (event 0x9F) | obj | 0x3a6c(0x21b:237,0x22d:237) |
| `0x190` | 74 -> 20 | `0xbccc` | client stub -> server (event 0x9F) | obj | 0x38fc(0x21b:283,0x22d:283) |
| `0x190` | 77 -> 21 | `0xba9c` | client stub -> server (event 0x9F) | obj | 0x3c00(0x21b:223,0x22d:223) |
| `0x190` | 81 -> 22 | `0xbc54` | no stream access (empty client body; server-side implementation when a stub targets it) | - | - |
| `0x190` | 82 -> 23 | `0xbbfc` | client stub -> server (event 0x9F) | u64 obj | 0x399c(0x21b:313,0x22d:313) |
| `0x190` | 85 -> 24 | `0xba24` | no stream access (empty client body; server-side implementation when a stub targets it) | - | - |
| `0x190` | 86 -> 25 | `0xb9dc` | client stub -> server (event 0x9F) | obj | 0x908c(0x232:86) |
| `0x191` | 1 -> 1 | `0xbebc` | server -> client handler | u32 obj u32 u64 | - |
| `0x191` | 3 -> 2 | `0xbeac` | no stream access (empty client body; server-side implementation when a stub targets it) | - | - |
| `0x191` | 4 -> 3 | `0xbe44` | client stub -> server (event 0x9F) | u32 u32 u64 | 0x3d7c(0x21b:265,0x22d:265), 0x9a88(0x233:25) |
| `0x197` | 6 -> 1 | `0xbfa4` | no stream access (empty client body; server-side implementation when a stub targets it) | - | - |
| `0x197` | 16 -> 2 | `0xbf5c` | client stub -> server (event 0x9F) | u32 | 0xa60c(0x28f:1) |
| `0x19a` | 43 -> 1 | `0xbffc` | no stream access (empty client body; server-side implementation when a stub targets it) | - | - |
| `0x19a` | 44 -> 2 | `0xbfb4` | client stub -> server (event 0x9F) | u64 | 0x86f4(0x135:127,0x13d:127) |
| `0x1a1` | 6 -> 1 | `0xc1b0` | no stream access (empty client body; server-side implementation when a stub targets it) | - | - |
| `0x1a1` | 7 -> 2 | `0xc0a4` | server -> client handler | obj u64 | - |
| `0x1a1` | 10 -> 3 | `0xc02c` | server -> client handler | u32 obj | - |
| `0x1a1` | 11 -> 4 | `0xc164` | server -> client handler | - | - |
| `0x1a1` | 16 -> 5 | `0xc154` | no stream access (empty client body; server-side implementation when a stub targets it) | - | - |
| `0x1a1` | 22 -> 6 | `0xc1c0` | no stream access (empty client body; server-side implementation when a stub targets it) | - | - |
| `0x1a1` | 23 -> 7 | `0xc11c` | client stub -> server (event 0x9F) | - | 0x8510(0x137:203,0x21b:203) |
| `0x1a5` | 1 -> 1 | `0xc288` | no stream access (empty client body; server-side implementation when a stub targets it) | - | - |
| `0x1a5` | 3 -> 2 | `0xc1d0` | server -> client handler | obj obj obj u64 | - |
| `0x1a5` | 5 -> 3 | `0xc278` | no stream access (empty client body; server-side implementation when a stub targets it) | - | - |
| `0x251` | 5 -> 1 | `0xc2e0` | no stream access (empty client body; server-side implementation when a stub targets it) | - | - |
| `0x251` | 6 -> 2 | `0xc298` | client stub -> server (event 0x9F) | obj | 0x7dc8(0x21b:307,0x22d:307) |

Notes on the table: in `0x18E`-`0x190` the stubs are called by the admin console class `0x22D` (`/dump`, `/edit`,
`/hfsm`, `/level`, `/xp`, `/skillrank`, `/respawn`, `/smite`, `/heal`, `/god`, `/sprint`, `/heartbeat`, `/fog`,
`/generator`, `/pvp`, ...; command names from the string table). They are developer tools a preservation server can
ignore. The gameplay ones are `0x191` (rank skill), `0x197` (emotes, from `CEmoteSystem` class `0x28F`), `0x19A` (from
the agent base `0x135` slot 127, sent by every champion script) and `0x1A1` (player).

### 1.7 Advancement handlers (class `0x233`): who registers them and how a rank-up reaches the server

**Corrected handler mapping** [C] (each `push fnref; native` pair in `0x9654`; this supersedes the [P] table in
`progression-meta.md` 1.2):

| Native (register / unregister) | GM_Advancement handler | Method (id -> slot) | Code | What it does |
|---|---|---|---|---|
| `0xE7000C` / `0xE7000D` | InqSkillRank `0x10000063` | 6 -> 23 | `0x9754` | GetSkillRank native `0x105000A` (rank from property `0x100000AF`) |
| `0xE70006` / `0xE70007` | InqCanRankSkill `0x1000006A` | 5 -> 22 | `0x9788` | calls `0x9A30` (max rank -> `SkillRank_AtMaxRank 0x10000018`, then `0x926C`: level / skill points / prerequisites) |
| `0xE70017` / `0xE70018` | InqNextRecommendedSkillToRank `0x1000023C` | 10 -> 27 | `0x97BC` | build record skill order `0x1000034B` |
| `0xE70012` / `0xE70013` | **RankSkill** notice `0x1000009B` | 8 -> 25 | `0x9A88` | checks can-rank; then either raises SkillRanked locally (`0xE70015`) or calls **`0x191` stub `0xBE44` -> event `0x9F` message `0x81910003`** |
| `0xE7000F` / `0xE70010` | InqXPForLevel `0x10000011` | 9 -> 26 | `0x9B70` | `0x91B8` -> `0xE154`/`0xE194`: XP table object of WLib type `0x21D` found by native `0x340001(0xB, 0x10000027)` [P] |
| `0xE70009` / `0xE7000A` | InqLevelCap `0x10000009` | 2 -> 19 | `0x9BF8` | `0x91E4`: int property `0x10000975` of the agent, default 19, clamped with 100 (`0x720018`) [P for the exact clamp] |

Register = method id 1 / slot 18 (`0x9654`, no arguments); unregister = id 3 / slot 20 (`0x96D4`).

**Who calls them** [C, static]: the only callers in the whole library are the **player** class `0x137` (and its
descendants `0x22E`, `0x21C`, `0x21B`, `0x22D`):
- slot **198** (`0x84DC`, exported as `0x22E` method id 23): `0x28F` emote-system setup (empty), **`0x9654` register
  the six advancement handlers**, `0x237` setup (registers handler `0xA284` with `0xE90010`), native `0xE90007`.
- slot **92** (`0x843C`, `0x22E` id 13, `0x22C` id 2): base teardown, then `0x96D4` unregister and `0x237` teardown.
  Slot 92 is reached from C++ through interface `0x62` method 16 (`0x10F8`, `vcall 92`) [C].

Slot 198 has exactly one caller: **`0x1A1` method id 11 (`0xC164`)**, a server->client RPC handler: IsA(target,
`0x22E`) else return; end-of-stream (`0x83000D`); `target.vcall(198)`. Nothing in the exe (immediates, interface
tables), in the bytecode (no `0x16` call, no function reference) or in the packs (scan of every pack for
`0x81A1000B`, `0x822E0017`, `0x82330001`: only unaligned hits inside textures/meshes) starts it.

**So the original server sent, once the player object existed (probably at match start, since `0x237` and the
advancement handlers concern the controlled agent):** event `0x9F` to `0x0200000000000001`, message `0x81A1000B`, empty
blob [P, strong]. Possible gotcha: the receive path (`0x567F4E`) takes the C++ branch if the blob object is null; send
`u32 n = 0` first and, if the log shows no handler, a 4-byte blob.

**Rank-up round trip** [P for field meanings]:
1. Flash "+" -> `InqCanRankSkill` (`0x9788`) -> `RankSkill` notice -> `0x9A88`.
2. Client -> server: event `0x9F`, message **`0x81910003`** (`0x191` id 3, server body), blob `u32, u32, u64`
   (written by `0xBE44`: two `0x830004` + one `0x830005`; probably slot, rank or skill-point cost, agent IID) [P].
   The same stub is used by the admin `/skillrank` command (`0x3D7C`).
3. Server: apply (property `0x100000AF` rank array, `SkillPoints 0x100001AF`), then event `0x9F` to the agent/player,
   message **`0x81910001`** (`0xBEBC`): IsA(target, `0x140` = agent base), reads `u32, object, u32, u64`, calls `0x233`
   slot 21 (`0x9B18`) which raises `GM_Advancement.RecvNotice_SkillRanked` (`0x10000054`, Flash feedback).
   The properties alone already update the bar; the notice is the "+" animation.

**Consequence for the patches** (`icserver/patcher.py`, caves A-E): with `0x9F 0x81A1000B` sent at match start, the
unpatched client would answer InqCanRankSkill / InqSkillRank / InqXPForLevel / InqLevelCap / NextRecommended from its
own script and send `0x9F 0x81910003` instead of the "KNAR" ping (`0x2136`). Needs a test with the patches off
(`config.toml`), then `ics` must decode `0x9F`; `ics/session.py HANDLERS` has no entry for it today.

### 1.8 Every class

Generated from the type table (`parent` from section `0x400`; `own` = slots whose code differs from the parent's;
`class records` = shipped `0x40`-`0x47` records using the type; native groups `gg:calls` over own methods; `net
natives` = direct network-reaching natives, see 1.5 for the transitive list; hints = class names or console commands
found in the developer strings the class uses). Roles worth knowing:
`0x8` ContextMenuSystem; `0xF3` `/pvp` encounter commands; `0x14F` AdminPropertySystem; `0x172` EmoteDirectory;
`0x28F` CEmoteSystem; `0x1BD` GeneratorSystem (profiling counters); `0x213`/`0x214`/`0x24B`/`0x24C` TestTools;
`0x22D` admin console (CAdmin, 111 own methods; the player variant `0x21B` derives from it); `0x137` -> `0x22E` ->
`0x21C` player; `0x140` -> `0x230` / `0x22C` -> `0x27B` agents (champions); `0x135`, `0x13B`, `0x13D` entity bases;
`0x120` -> `0x228` world object base; `0x11C`/`0x11D`/`0x11E` data-object bases; `0x15B` -> `0x233` advancement;
`0x237` second player-local handler set; `0x62`, `0x74`, `0x87`, `0x54`, `0x10` interfaces called by C++;
`0x18E`-`0x1A5`, `0x251` RPC classes; `0x21D` XP table data object [P]; `0x1BE`-`0x1C7` small data objects with fields.

| type | parent | slots / own | class records | native groups (calls) | net natives | dev-string hints |
|---|---|---|---|---|---|---|
| `0x8` | - | 6 / 4 |  | 6:2, 11:1, 29:1, 4d:1, d5:1 |  | ContextMenuSystem |
| `0xd` | `0x11e` | 76 / 3 |  |  |  |  |
| `0x10` | - | 9 / 7 |  | d5:1 |  |  |
| `0x28` | - | 5 / 0 |  |  |  |  |
| `0x50` | `0x11e` | 77 / 3 |  | 31:1 |  |  |
| `0x52` | `0x11d` | 70 / 1 |  |  |  |  |
| `0x54` | `0x11e` | 77 / 3 |  |  |  |  |
| `0x62` | - | 35 / 31 |  |  |  |  |
| `0x74` | - | 5 / 4 |  |  |  |  |
| `0x84` | `0x11e` | 76 / 2 |  |  |  |  |
| `0x87` | - | 2 / 1 |  |  |  |  |
| `0xae` | `0x11e` | 76 / 3 |  | 36:1 |  |  |
| `0xca` | - | 2 / 1 |  |  |  |  |
| `0xe5` | - | 5 / 3 |  |  |  |  |
| `0xf3` | - | 12 / 5 |  | be:1, c6:1, f8:1 |  | /pvp |
| `0x11a` | - | 4 / 0 |  |  |  |  |
| `0x11b` | `0x11c` | 64 / 5 |  | 94:3 |  |  |
| `0x11c` | - | 61 / 19 |  | 29:9 |  |  |
| `0x11d` | `0x11c` | 64 / 16 |  | 97:15 |  |  |
| `0x11e` | `0x52` | 75 / 4 |  | 34:1, 44:1, be:1 |  |  |
| `0x11f` | `0x11c` | 64 / 5 |  | 29:4 |  |  |
| `0x120` | `0xc9` | 149 / 63 |  | 97:15, af:1, c6:4 |  |  |
| `0x122` | `0x11e` | 78 / 1 |  |  |  |  |
| `0x123` | - | 8 / 4 |  |  |  |  |
| `0x127` | - | 26 / 5 |  |  |  |  |
| `0x128` | `0x11e` | 105 / 7 |  | 36:1, be:1, c6:3, c8:16, c9:1 |  |  |
| `0x12d` | `0x12e` | 35 / 5 |  | 29:3 |  |  |
| `0x12e` | - | 31 / 11 |  |  |  |  |
| `0x12f` | `0x11c` | 106 / 5 |  | 29:6 |  |  |
| `0x130` | `0x12e` | 34 / 4 |  | 17:1, 29:1 |  |  |
| `0x132` | `0x11e` | 80 / 4 |  |  |  |  |
| `0x133` | - | 2 / 0 |  |  |  |  |
| `0x134` | - | 19 / 0 |  |  |  |  |
| `0x135` | `0x22f` | 191 / 2 |  |  |  |  |
| `0x137` | `0x22e` | 208 / 1 |  | 31:1, 262:1 |  |  |
| `0x139` | `0x22c` | 191 / 1 |  |  |  |  |
| `0x13b` | `0x22c` | 196 / 4 |  | 31:1 |  |  |
| `0x13d` | `0x230` | 181 / 1 |  |  |  |  |
| `0x140` | `0x228` | 176 / 5 |  | 29:2, a5:1, a6:1, c9:1 |  |  |
| `0x141` | `0x230` | 176 / 1 |  |  |  |  |
| `0x143` | `0x230` | 176 / 3 | 101 (e.g. `0x4000000a`) |  |  |  |
| `0x145` | `0x230` | 177 / 2 | 34 (e.g. `0x4000025a`) |  |  |  |
| `0x146` | `0x230` | 176 / 1 |  |  |  |  |
| `0x149` | - | 46 / 2 |  |  |  |  |
| `0x14f` | - | 8 / 5 |  | 29:2, 71:1, c6:1 |  | AdminPropertySystem |
| `0x150` | `0x122` | 80 / 1 |  |  |  |  |
| `0x152` | - | 9 / 1 |  |  |  |  |
| `0x15b` | - | 18 / 9 |  | 17:2, 29:1, 72:1, 105:5 |  |  |
| `0x15e` | `0x50` | 77 / 2 |  |  |  |  |
| `0x15f` | - | 6 / 0 |  |  |  |  |
| `0x160` | `0x54` | 77 / 2 |  | 29:2, 4d:1, c9:1, d5:1 | `0xd5000b` |  |
| `0x161` | `0x54` | 77 / 2 |  | 29:2, c9:1, d5:1 |  |  |
| `0x16a` | - | 4 / 0 |  |  |  |  |
| `0x16b` | `0x11e` | 89 / 5 |  |  |  |  |
| `0x16f` | - | 3 / 3 |  |  |  |  |
| `0x171` | `0x11e` | 79 / 4 |  |  |  |  |
| `0x172` | `0x11e` | 79 / 5 |  | 17:2 |  | EmoteDirectory |
| `0x176` | `0x11e` | 107 / 7 |  |  |  |  |
| `0x17a` | - | 4 / 1 |  |  |  |  |
| `0x17d` | `0x123` | 48 / 1 |  |  |  |  |
| `0x180` | `0x11e` | 75 / 2 |  |  |  |  |
| `0x18b` | - | 56 / 1 |  |  |  |  |
| `0x18e` | - | 43 / 42 |  | 83:7, be:1, c2:1 | `0xc2000d` |  |
| `0x18f` | - | 13 / 10 |  | 83:5, be:1, c2:1 | `0xc2000d` |  |
| `0x190` | - | 26 / 24 |  | 83:4, be:1, c2:1 | `0xc2000d` |  |
| `0x191` | - | 4 / 3 |  | 83:6, be:1, c2:1 | `0xc2000c` |  |
| `0x197` | - | 3 / 2 |  | 83:1, c2:1 | `0xc2000c` |  |
| `0x19a` | - | 3 / 2 |  | 83:1, c2:1 | `0xc2000c` |  |
| `0x19e` | - | 5 / 2 |  |  |  |  |
| `0x1a1` | - | 10 / 7 |  | 83:4, be:1, c2:1 | `0xc2000c` |  |
| `0x1a5` | - | 6 / 3 |  | 83:3, be:1 |  |  |
| `0x1b6` | - | 6 / 2 |  |  |  |  |
| `0x1b7` | `0x11e` | 79 / 2 |  |  |  |  |
| `0x1bc` | `0x176` | 108 / 2 |  |  |  |  |
| `0x1bd` | `0x84` | 76 / 3 |  | 85:5, 86:3, c4:1 |  | EntityGeneratorRegistryData, GeneratorSystem, LinkBasedRegistry, ProfileBasedRegistry, SeedPointBasedRegistry |
| `0x1be` | `0x1bf` | 87 / 2 |  |  |  |  |
| `0x1bf` | `0x11e` | 85 / 1 |  |  |  |  |
| `0x1c0` | `0x1bf` | 87 / 2 |  |  |  |  |
| `0x1c1` | `0x1bf` | 87 / 2 |  |  |  |  |
| `0x1c2` | - | 7 / 2 |  |  |  |  |
| `0x1c3` | - | 3 / 1 |  |  |  |  |
| `0x1c4` | `0x1bf` | 86 / 2 |  |  |  |  |
| `0x1c5` | `0x1bf` | 87 / 2 |  |  |  |  |
| `0x1c6` | - | 2 / 2 |  |  |  |  |
| `0x1c7` | `0x1bf` | 88 / 2 |  |  |  |  |
| `0x1d8` | - | 12 / 0 |  |  |  |  |
| `0x1da` | `0x176` | 108 / 2 |  |  |  |  |
| `0x1eb` | - | 12 / 2 |  |  |  |  |
| `0x1ec` | - | 2 / 1 |  |  |  |  |
| `0x1ed` | - | 3 / 1 |  |  |  |  |
| `0x1ef` | - | 19 / 0 |  |  |  |  |
| `0x1f0` | - | 12 / 1 |  |  |  |  |
| `0x1f1` | - | 2 / 1 |  |  |  |  |
| `0x1f2` | `0x134` | 30 / 1 |  | 29:1, 97:1 |  |  |
| `0x1f3` | `0x11e` | 80 / 2 |  |  |  |  |
| `0x1f5` | `0x11e` | 75 / 2 |  |  |  |  |
| `0x212` | - | 3 / 3 |  | f:1, 29:3, 94:1, 97:3, 9e:2, d5:1 |  |  |
| `0x213` | - | 2 / 2 |  | 36:1, a3:3, a4:3, c6:2 |  |  |
| `0x214` | - | 2 / 2 |  | be:3, c6:1 |  | TestTools |
| `0x21b` | `0x22d` | 322 / 2 |  |  |  |  |
| `0x21c` | `0x22e` | 207 / 2 | 1 (e.g. `0x4000007c`) |  |  |  |
| `0x21d` | `0x11e` | 82 / 5 |  | 29:2, 34:1 |  |  |
| `0x21f` | `0x11e` | 79 / 2 |  |  |  |  |
| `0x220` | - | 2 / 2 |  |  |  |  |
| `0x221` | - | 3 / 1 |  |  |  |  |
| `0x222` | `0x11e` | 76 / 2 |  |  |  |  |
| `0x223` | `0x230` | 177 / 2 | 31 (e.g. `0x400001bd`) |  |  |  |
| `0x224` | `0x230` | 176 / 2 | 2 (e.g. `0x40000180`) |  |  |  |
| `0x225` | `0x230` | 176 / 2 |  |  |  |  |
| `0x227` | `0x146` | 176 / 2 |  |  |  |  |
| `0x228` | `0x120` | 162 / 11 |  |  |  |  |
| `0x229` | `0x11e` | 78 / 5 |  |  |  |  |
| `0x22c` | `0x135` | 191 / 5 |  |  |  |  |
| `0x22d` | `0x137` | 322 / 111 |  | e:3, 29:4, 31:1, 36:1, 40:2, 41:1, 43:2, 44:1, 46:1, 48:1, 57:4, 67:1, 68:3, 6d:4, 6e:4, 7f:2, 88:2, 8a:5, 94:1, 99:4, 9e:4, a3:10, a4:3, a5:1, af:1, b4:1, bc:1, c5:1, c6:9, c9:1, cb:8, d5:2, e8:2, f8:2, 105:1, 293:2, 2e1:1 | `0xe0004` `0xc50001` `0xd50006` `0xd5000b` | /Distance, /addclientlog, /cdbg, /characterswitch, /clientlog, /clone, /console, /createentity, /ctest, /dbg, /deleteobject, /dump, /edit, /flightcam, |
| `0x22e` | `0x13b` | 207 / 17 |  | e:2, af:4, c6:1, e9:1, f9:1, 2f8:1 |  |  |
| `0x22f` | `0x13d` | 182 / 0 |  |  |  |  |
| `0x230` | `0x140` | 176 / 3 |  | c9:1, d5:1, f8:1, 101:1, 27c:1 | `0x27c0002` |  |
| `0x232` | `0x150` | 88 / 8 |  | e:1, 9e:2, a3:1, c6:2 |  |  |
| `0x233` | `0x15b` | 28 / 10 |  | 17:3, 29:1, 31:1, 35:3, c9:1, e7:13, f8:1, 105:1, 306:1 |  |  |
| `0x237` | `0x16a` | 11 / 7 |  | 31:1, 97:4, a6:2, c9:1, e9:2, f8:1 |  |  |
| `0x23d` | - | 2 / 0 |  |  |  |  |
| `0x23f` | - | 4 / 3 |  | 29:3 |  |  |
| `0x242` | `0x11e` | 75 / 2 |  |  |  |  |
| `0x24b` | `0x213` | 2 / 2 |  |  |  |  |
| `0x24c` | `0x213` | 2 / 2 |  | 36:1, af:4 |  |  |
| `0x250` | `0x230` | 176 / 2 | 15 (e.g. `0x400000a4`) |  |  |  |
| `0x251` | - | 3 / 2 |  | 83:1, c2:1 | `0xc2000d` |  |
| `0x253` | - | 8 / 0 |  |  |  |  |
| `0x254` | `0x253` | 9 / 1 |  | 29:1, 97:1, a6:1, be:1, d5:1 |  |  |
| `0x259` | `0x11e` | 76 / 2 |  |  |  |  |
| `0x25e` | `0x11e` | 79 / 2 |  |  |  |  |
| `0x26d` | `0x230` | 177 / 2 | 33 (e.g. `0x40000132`) |  |  |  |
| `0x270` | `0x11e` | 75 / 2 |  |  |  |  |
| `0x27a` | `0x27b` | 193 / 6 | 6 (e.g. `0x4000013b`) |  |  |  |
| `0x27b` | `0x22c` | 191 / 2 | 312 (e.g. `0x40000009`) |  |  |  |
| `0x28f` | - | 5 / 4 |  | 17:4, c6:3 |  | CEmoteSystem |
| `0x296` | - | 8 / 2 |  |  |  |  |
| `0x2a6` | `0x230` | 176 / 2 |  |  |  |  |
| `0x2b0` | `0x11e` | 75 / 2 |  |  |  |  |
| `0x2c1` | `0x26d` | 177 / 2 | 2 (e.g. `0x400007fd`) |  |  |  |
| `0x2c4` | `0x11e` | 75 / 2 |  |  |  |  |
| `0x2c6` | - | 2 / 2 |  |  |  |  |
| `0x2c7` | - | 2 / 2 |  |  |  |  |
| `0x2c8` | - | 2 / 2 |  |  |  |  |
| `0x2d5` | `0x11e` | 76 / 2 |  |  |  |  |
| `0x2e2` | `0x11e` | 75 / 2 |  |  |  |  |
| `0x2e7` | `0x11e` | 75 / 2 |  |  |  |  |
| `0x2e8` | `0x11e` | 79 / 6 |  | 2e9:1 |  |  |
| `0x2ec` | `0x11e` | 75 / 2 |  |  |  |  |
| `0x2ee` | `0x11e` | 75 / 2 |  |  |  |  |
| `0x2f0` | - | 12 / 2 |  |  |  |  |
| `0x2f6` | `0x11e` | 76 / 2 |  |  |  |  |
| `0x2f7` | `0x11e` | 76 / 2 |  |  |  |  |
| `0x2f9` | `0x11e` | 75 / 2 |  |  |  |  |
| `0x2fb` | `0x11e` | 75 / 2 |  |  |  |  |
| `0x301` | `0x224` | 176 / 2 | 6 (e.g. `0x400008cf`) |  |  |  |
| `0x305` | `0x11e` | 75 / 2 |  |  |  |  |
| `0x30c` | `0x230` | 176 / 2 |  |  |  |  |
| `0x310` | `0x11e` | 75 / 2 |  |  |  |  |

---

## 2. The Flash (GFx) UI

### 2.1 Where the movies live [C]

- Pack **`0xA00000D0`** (always loaded): 89 DB type **`0x20`** records ("UI movie") among 1908 images (`0x13`), the
  font glyph table `0x24000007`, the wrapper config `0x48000E76`, Wwise banks (`0x52`).
- `0x20` record layout: `u32 did | u32 flags (0, or 2 = has imports) | [u32 n | n x (u32 0x31, u32 imported movie DID)]
  | u32 0 | u32 0 | u32 nImages | nImages x (u32 image DID 0x13..., u32 width, u32 height) | u32 length | GFX/CFX data`.
  The import list equals the movie's ImportAssets tags (`#2000xxxx` URLs). 82 movies parse this way.
- **`0x20000025`** = the **AS2 code library** (CWS, 3 179 564 bytes, all `__Packages.*` classes; disassembly in
  `old_files/tools/gfx/classes_all.txt`). Not found as movies in this pack: `0x20000003`, `0x20000005`, `0x20000008`
  (imported by the shared libraries: font/locale libraries [P], probably resolved from the language packs),
  `0x20000017`, `0x20000019`, `0x20000026` (no data found).
- The old extraction `old_files/tools/gfx/*.gfx` (84 files) names the files by stream offset; the DID of each is in
  the table of 2.4.

### 2.2 How Flash talks to the game [C]

- Every system is an AS2 class `GM_<System>` (31: Achievement, AdminAlert, Advancement, Amplifier, Artifact, Camera,
  Character, Chat, ConnectionManager, Contacts, Contextual, CustomMatch, Dialog, Encounter, Grouping, KeyBinding, Lobby,
  LoginReward, MapManager, Options, PlayerReport, ProfileUI, SelectionSystem, Skill, Sound, StatusIcon, Tutorial, UI,
  Upgrade, ViewMatch, Vitals) or `EM_<System>` (SocialMedia, Sound, UI, WebBrowser, WebTicket), extending
  `engNoticeSystemImpl`.
  - `SendNotice_X(...)` / `SendQuery_X(...)` = Flash -> C++: `flash.external.ExternalInterface.call("Turbine.SendNotice",
    event_gen.<System>NoticeIDList.Notice_<System>__X_ID, args...)`. Queries return a value synchronously.
  - `RecvNotice_X(...)` = C++ -> Flash: called by the exe with the arguments, forwarded to every listener registered
    with `engNoticeSystemImpl` for `Notice_<System>__X_ID`.
  - Ids: getters `__get__Notice_<System>__X_ID` in the `event_gen.*NoticeIDList` classes (2200 getters in the
    library; the numeric ids used below come from them).
- Screens rarely listen themselves: they use **singleton managers** (`gameplay.singleton.*`, 2.3) that cache the data.
- **Which notices the server can feed:** only the 44 notices with a network reader can be sent inside event `0x2`;
  everything else reaches Flash because a network *event* handler (or a local C++ system) raises the Flash notice.
  The "probable feeders" columns map a Flash notice to the network events whose handler names it in
  `protocol-server-to-client.md` (name match: [P]; a few generic names over-match).
- In-match **properties** feed the HUD directly: `PropertySystem.Register(controlledAgent, Level/XP/SkillPoints/
  Upgrade_Currency/PVP_Team)` (see `progression-meta.md` 1.1, `old_files/tools/ui_properties.json`).
- Screen switching is the C++ UI state machine (`UIStateMachineEvent`, ids in `old_files/tools/ui_events.json`, e.g.
  `0x21 TransitionToScorecard`, `0x14 TransitionToLobby`, `0x6C LoadLoginRewardsScreen`); network events `0x2038`
  (MatchEnded) and `0x2053` raise some of them.

### 2.3 Singleton managers (they receive the data) [C for names/ids, P for feeders]

| singleton | incoming notices (id) | probable feeders | Flash -> C++ |
|---|---|---|---|
| AccoladeManager | Character.SendAccountEndOfMatchAccoladesEarned `0x100004e4`; Character.SendBestChampAccolades `0x100004ef`; Character.SendBestMapAccolades `0x100004ee`; UI.SendHeaderNameAndProtectorIcons `0x1000047f` | `0x2104` `0x2154` `0x2186` `0x2188` `0x2190` | GM_Character.RequestAccountEndOfMatchAccoladesEarned, GM_Character.UI_RequestBestAccolades, GM_UI.RequestHeaderUIData |
| AchievementsManager | Achievement.SetAchievementData `0x1000045b`; Achievement.SetAchievementObjectiveData `0x10000459`; Achievement.SetDeprecatedAchievements `0x100004e7`; Achievement.TraineeAchievements `0x10000497`; UI.ProtectorAdvancementStatus `0x10000492` | `0x2080` `0x2120` `0x215d` `0x216a` `0x218b` `0x21a6` | GM_Achievement.RequestAllAchievementData, GM_Achievement.RequestTraineeAchievements |
| AmplifierSetManager | Amplifier.NotifyAmplifierSet `0x100003c3`; Amplifier.NotifyListAmplifierSets `0x100003bd` | `0x2090` `0x20c7` | GM_Amplifier.UI_RequestAllAmplifierSets, GM_Amplifier.?UI_InqAmplifierSetIcons, GM_Amplifier.?UI_InqAugmentData, GM_Amplifier.?UI_InqModData |
| BoutiqueDataManager | Amplifier.NotifyContextualAmplifierData `0x100003f9` | `0x2107` | GM_Amplifier.UI_RequestAllAmplifierBoutiqueData |
| ChatManager | Chat.UI_ShowWrapperGeneralChatWindow `0x10000451` | - | GM_Chat.HideChatForBrowser, GM_Chat.HideChatWindow, GM_Chat.RestoreChatForBrowser, GM_Chat.ShowChatWindow |
| ContactsManager | Contacts.UI_NotifyContactAccountIconChanged `0x10000350`; Contacts.UI_NotifyContactAdded `0x1000031d`; Contacts.UI_NotifyContactChangeNote `0x10000322`; Contacts.UI_NotifyContactChangeStatusMessage `0x10000337`; Contacts.UI_NotifyContactChangeSteamName `0x10000510`; Contacts.UI_NotifyContactChangedGroup `0x1000031e`; Contacts.UI_NotifyContactGroupCreated `0x10000320`; Contacts.UI_NotifyContactGroupDestroyed `0x10000324`; Contacts.UI_NotifyContactIgnored `0x1000031c`; Contacts.UI_NotifyContactList `0x10000323`; Contacts.UI_NotifyContactPresenceChanged `0x10000326`; Contacts.UI_NotifyContactRemoved `0x1000031f`; Contacts.UI_NotifyContactUnignored `0x10000321`; UI.ExitingWorld `0x10000103` | `0x2014` `0x2018` `0x2020` `0x2021` `0x204f` `0x2051` `0x205e` `0x208f` `0x20ae` `0x20c5` `0x20cb` `0x20cc` `0x20ec` | - |
| ControlledAgentDispatcher | Character.ActiveAgentControlledByThePlayerChanged `0x100001df`; Character.AgentControlledByThePlayerChanged `0x10000080`; Character.UpdateCharacterPanelInfo `0x100001f4`; UI.ExitingWorld `0x10000103` | `0x2021` | GM_Character.?InqCharacterPanelInfo, GM_Character.?InqCharacterPanelMetaData, GM_ViewMatch.?RequestInViewMatchMode, GM_ViewMatch.?RequestTeamGhostedAs |
| ConversationManager | Dialog.HideAllConversationSlots `0x1000044c`; Dialog.HideConversationSlot `0x10000449`; Dialog.HighlightConversationAdvanceButton `0x10000448`; Dialog.ShowConversationSlot `0x1000044b` | - | GM_Dialog.UI_ReadyForConversation, GM_Dialog.UI_SkipConversation |
| CustomMatchManager | CustomMatch.UI_CustomMatch_SetDraftMode `0x100003e9`; CustomMatch.UI_CustomMatch_SetEncounter `0x100003fe`; CustomMatch.UI_CustomMatch_SetTeamName `0x10000484`; CustomMatch.UI_CustomMatch_UpdateProtectorIcon `0x100004dd`; CustomMatch.UI_DeliverCustomMatchData `0x10000389` | `0x2103` `0x2109` `0x2151` `0x217c` | GM_CustomMatch.RequestCustomMatchData, GM_Lobby.?RequestTeamNames |
| DataReferencesManager | UI.ExitingWorld `0x10000103` | `0x2021` | - |
| DialogsManager | - | - | GM_UI.InGameMenuClosed, GM_UI.InGameMenuOpened, GM_UI.?IsBinkFileValid |
| EncounterManager | Encounter.ResetMapSelectionList `0x100003da`; UI.ProtectorAdvancementStatus `0x10000492`; UI.QueueEligibility `0x10000500` | `0x2024` `0x2080` `0x20ff` `0x2101` `0x2120` `0x215d` `0x216a` `0x218b` | GM_Encounter.?InqPVPEncounters, GM_UI.?InqQueueEligibility |
| HudModeManager | - | - | GM_Camera.FullScreenUIActive |
| LanguageManager | UI.ClientLanguage `0x10000518` | - | GM_UI.RequestClientLanguage |
| LeaderBoardManager | UI.DeliverFriendsLeaderboard `0x10000529`; UI.DeliverRegionalLeaderboard `0x10000528` | `0x21a2` `0x21a3` | GM_UI.RequestLeaderboards |
| MatchData | Encounter.AddParticipant `0x1000001e`; Encounter.RemoveParticipant `0x10000006`; Encounter.UI_UpdateMatchScorecard `0x1000007e`; UI.DefeatStatusUpdatedForEntity `0x100000bc`; UI.ExitingWorld `0x10000103`; UI.gmWErrorMessageOccurred `0x100001f9`; Upgrade.UpdateCurrentUpgrades `0x1000012f`; Upgrade.UpdatePowerGraphValues `0x10000160`; ViewMatch.ViewMatchScoreboardData `0x1000046c` | `0x100000bc` `0x2021` `0x20e2` | GM_Encounter.RequestMatchScorecard, GM_Lobby.?RequestTeamNames, GM_Skill.?InqSkillToolTipInfo, GM_Skill.?RequestStolenPowersForCharacter, GM_Upgrade.RequestSendEveryonesUpgrades, GM_ViewMatch.?RequestInViewMatchMode |
| NotificationPreviewsManager | - | - | EM_Sound.Play |
| OwnablesManager | UI.AvailableCharacterList `0x100002e2`; UI.CharacterAdvancementData `0x100002e8`; UI.Incremental_ItemStatuses `0x100004f3`; UI.ItemStatuses `0x100002e1` | `0x204c` `0x20b8` | GM_UI.RequestCharacterAdvancementData, GM_UI.RequestItemStatuses, GM_ViewMatch.?RequestInViewMatchMode |
| PVPGroupManager | Grouping.GroupInformation `0x10000286`; Grouping.PlayerLeftGroup `0x10000444`; Grouping.UI_Grouping_UpdateProtectorIcon `0x100004df` | `0x2071` `0x217d` | GM_Chat.RunCmd, GM_Contacts.UI_InviteContact, GM_Grouping.LeaveGroup, GM_Grouping.OnGroupPage, GM_Grouping.RequestGroupInformation, GM_UI.UIStateMachineEvent |
| ProtectorIconManager | - | - | GM_Character.?RequestProtectorIcons |
| RankedManager | UI.UI_DeliverAccountStandingsData `0x1000051e`; UI.UI_DeliverStaticStandingsData `0x10000521` | `0x219e` `0x219f` | GM_UI.RequestAccountStandingsData, GM_UI.RequestStaticStandingsData |
| RibbonManager | UI.PendingMatchFailure `0x10000244` | `0x20d7` `0x210b` | - |
| ScorecardManager | Character.SendAccountCurrencyBalance `0x1000028a`; Character.SendAccountEndOfMatchAccoladesEarned `0x100004e4`; Character.SendAccountEndOfMatchCharacterLevelAndXP `0x100003ee`; Character.SendAccountEndOfMatchLevelAndXP `0x100003f0`; Character.SendAccountEndOfMatchSoftCurrencyReward `0x100003ed`; Encounter.UI_SendEndOfMatchStats `0x10000366`; Encounter.UI_SetEndOfMatchStatsHeader `0x10000387`; UI.SendHeaderNameAndProtectorIcons `0x1000047f`; Upgrade.UpdateCurrentUpgrades `0x1000012f`; Upgrade.UpdatePowerGraphValues `0x10000160` | `0x2028` `0x2045` `0x2080` `0x2081` `0x20b9` `0x20e2` `0x2104` `0x2154` `0x2188` `0x2190` | GM_Character.RequestAccountCurrencyBalance, GM_Character.RequestAccountCurrencyBalanceChanges, GM_Character.RequestAccountEndOfMatchAccoladesEarned, GM_Character.RequestAccountEndOfMatchAccountLevelAndXP, GM_Character.RequestAccountEndOfMatchCharacterLevelAndXP, GM_Character.RequestAccountEndOfMatchSoftCurrencyReward, GM_Encounter.RequestPostMatchScorecard, GM_UI.RequestHeaderUIData |
| SecondaryPowerManager | - | - | GM_Lobby.?RequestStolenPowerList |
| SettingsManager | KeyBinding.UI_KeyBindingData `0x100003c9`; KeyBinding.UI_UpdateKeyBinding `0x100003c7` | - | GM_KeyBinding.UI_RequestKeyBindingData, GM_Options.SetBoolOption, GM_Options.?GetBoolOption |
| TipManager | Lobby.PreGameTips `0x1000026d` | - | GM_Lobby.RequestAllPregameTips |
| TooltipManager | - | - | EM_Sound.Play |

### 2.4 Every movie

Role from the class names; singletons without the generic DataReferences/Tooltip managers; incoming = C++ -> Flash notices the movie's classes listen to (Flash names, not game texts).

| DID | GFX bytes | role | singletons | incoming notices (Flash RecvNotice) | probable network feeders |
|---|---|---|---|---|---|
| `0x20000000` | 12045 | shared library (imports font lib 0x20000003) |  | - | - |
| `0x20000001` | 1221 | shared widget target |  | - | - |
| `0x20000002` | 24713 | shared library (imports 0x20000008) |  | - | - |
| `0x20000004` | 1526 | shared images |  | - | - |
| `0x20000006` | 79240 | HUD: overhead vitals + floaty damage/XP/currency/status |  | Advancement.XPGained, Upgrade.DisplayFloatyCurrencyChanged, Upgrade.DisplayFloatyCurrencyDenied, Vitals.DisplayFloatyStatus, Vitals.VOTUpdate | `0x208d` `0x20bd` `0x44` |
| `0x20000007` | 8922 | animation utilities |  | - | - |
| `0x2000000c` | 58793 | HUD: match bar (team health, timer, score, sector objectives) | ControlledAgentDispatcher, MatchData, AgentData | Encounter.NotifyMatchEnded, Encounter.SetMatchTime, Encounter.UI_BatchUpdateTrackerStatus, Encounter.UI_InitialTeamHealthUpdate, Encounter.UI_UpdateTeamHealth, Encounter.UI_UpdateTrackerStatus, Lobby.ClearLightResourcePackReferences | `0x1000000e` `0x10000109` `0x10000134` `0x100004fb` `0x2021` `0x2028` `0x204b` `0x2069` `0x206c` |
| `0x2000000d` | 33083 | in-game start menu (Esc) | DialogsManager | - | - |
| `0x2000000f` | 79378 | HUD: minimap + map notes / pings | ControlledAgentDispatcher | Encounter.UI_BatchUpdateTrackerStatus, Encounter.UI_UpdateTrackerStatus, MapManager.AddMapNotes, MapManager.AddStaticMapNote, MapManager.DeliverMapData, MapManager.MapNote_UnderAttack, MapManager.RemoveMapNote, MapManager.SetPingPrepped, MapManager.ShowMiniMapTargetingRing, MapManager.UI_StartTeleportEffects, MapManager.UI_StopTeleportEffects, MapManager.UpdateMapNotes, MapManager.UpdateMapNotesDecorations | `0x2069` `0x209f` `0x2137` `0x217f` `0x2180` `0x2189` `0x218a` |
| `0x20000010` | 19217 | HUD: floaty vitals/verbs managers | ControlledAgentDispatcher | UI.FadeFloatyVitals, UI.UpdateFloatyVitalArray, UI.UpdateTrainingFloatyText | `0x2171` `0x2172` `0x2173` |
| `0x20000011` | 46131 | HUD: experience bar | ControlledAgentDispatcher | Character.AgentControlledByThePlayerChanged | - |
| `0x20000013` | 40740 | HUD: defeat (death/respawn panel, recommendations) | ControlledAgentDispatcher, MatchData | Advancement.SkillRanked, Character.HideKillCard, Character.UI_ShowKillCard, Encounter.UI_UpdateHasBaseAccess, Encounter.UI_UpdateHasVendorAccess, UI.DefeatStatusUpdated, Upgrade.UpdateNextRecommendedUpgrade | `0x10000090` `0x2078` |
| `0x20000015` | 92283 | HUD: billboards (announcements, VICTORY/DEFEAT) |  | Character.ClearAnnouncement, Character.ShowAnnouncement, Character.StopProcessingNewBillboards, Encounter.UI_PlayerJoined, Encounter.UI_PlayerLeft, Lobby.ClearLightResourcePackReferences | `0x100000cb` `0x100000ce` `0x100002bc` `0x100002eb` `0x100002ec` `0x2021` `0x2028` `0x204b` `0x206c` |
| `0x20000016` | 3096 | resolution sizer |  | - | - |
| `0x20000020` | 3175 | loading into world |  | - | - |
| `0x20000022` | 48600 | champion picker (lobby / select) | OwnablesManager | Lobby.CharacterVariantsLoaded, Lobby.ClearHeavyResourcePackReferences, Lobby.ClearLightResourcePackReferences, Lobby.Draft_Selecting, Lobby.HeavyResourcePackLoaded | `0x2021` `0x2028` `0x204b` `0x206c` |
| `0x2000002b` | 28592 | HUD: player + selection vitals | ControlledAgentDispatcher | - | - |
| `0x20000051` | 23347 | HUD test buttons (dev) |  | - | - |
| `0x20000052` | 80259 | HUD test harness (dev) |  | - | - |
| `0x20000056` | 59500 | HUD: skill bar | ControlledAgentDispatcher, MatchData, SettingsManager | Advancement.SkillRanked, Encounter.UI_UpdateHasBaseAccess, Skill.EnableSkillButton, Skill.UI_NotifySkillButtonUpdateIsSuppressed, Skill.UI_NotifyVitalChange, Skill.UI_SkillUpdate, Skill.UpdateSkillUIOverlay, UI.ExecuteSkillError, UI.RemoveSkillStackCountString, UI.StartSkillCooldown, UI.UpdateSkillStackCountString | `0x1000015a` `0x207b` `0x208c` `0x2091` `0x2092` `0x20a0` `0x20a2` `0x20a8` `0x20c8` `0x20dc` `0x20e9` `0x20f8` `0x2187` `0x42` |
| `0x20000057` | 24572 | HUD: in-match currency | ControlledAgentDispatcher | Encounter.UI_UpdateHasVendorAccess | - |
| `0x20000058` | 81582 | shared art library (211 images) |  | - | - |
| `0x20000059` | 131362 | common controls (buttons, dropdowns, lists) |  | - | - |
| `0x2000005a` | 28273 | HUD: character panel (attributes) | ControlledAgentDispatcher, MatchData, AttributeMetadata | - | - |
| `0x2000005b` | 17904 | HUD: kill feed | ControlledAgentDispatcher | Character.NotifyPlayerDied | - |
| `0x2000005c` | 22226 | HUD: top bar |  | - | - |
| `0x2000005e` | 37408 | HUD: hero graph / power bar | ControlledAgentDispatcher, MatchData | Upgrade.UpdatePowerGraphValues | `0x20e2` |
| `0x2000005f` | 70002 | settings dialog | DialogsManager, SettingsManager | Camera.CameraLockedPreference, KeyBinding.UI_KeyBindingData, KeyBinding.UI_UpdateKeyBinding, Options.InGameFullScreenOptionChanged, Options.OutOfGameFullScreenOptionChanged | - |
| `0x20000062` | 30314 | HUD: player info panel (portraits) | ControlledAgentDispatcher, MatchData, AgentData | - | - |
| `0x20000063` | 20580 | HUD: status icons | ControlledAgentDispatcher | StatusIcon.AddStatusIcon, StatusIcon.BatchAddStatusIcon, StatusIcon.RemoveStatusIcon, StatusIcon.UpdateStatusIcon, StatusIcon.UpdateStatusIconTooltip | `0x20a2` `0x20a8` `0x20c8` `0x20d0` `0x20e9` `0x2127` |
| `0x20000064` | 53168 | HUD: objectives tracker | ControlledAgentDispatcher | Encounter.UI_AddObjective, Encounter.UI_DeliverCurrentObjectives, Encounter.UI_DeliverObjectiveCategories, Encounter.UI_RemoveObjective, Encounter.UI_RemoveObjectiveCategory, Encounter.UI_SetObjectiveTrackerEnabled, Encounter.UI_UpdateObjectiveCategory_State, Encounter.UI_UpdateObjective_BannerText, Encounter.UI_UpdateObjective_Count, Encounter.UI_UpdateObjective_CountDown, Encounter.UI_UpdateObjective_CountMax, Encounter.UI_UpdateObjective_ProgressPercent, Encounter.UI_UpdateObjective_State, Encounter.UI_UpdateObjective_TeamRelationship, Encounter.UI_UpdateObjective_Text, Encounter.UI_UpdateObjective_TimerDuration | `0x2009` `0x2023` `0x2034` `0x2075` |
| `0x20000065` | 51004 | HUD: event timer / timeline banners | ControlledAgentDispatcher, MatchData | Encounter.UI_MissionEvent_AddTimelineBanner, Encounter.UI_MissionEvent_AddTimelineEvent, Encounter.UI_MissionEvent_BatchAddTimelineEvent, Encounter.UI_MissionEvent_RemoveTimelineBanner, Encounter.UI_MissionEvent_RemoveTimelineEvent, Encounter.UI_MissionEvent_StartTimeline | - |
| `0x20000066` | 19192 | video player |  | - | - |
| `0x20000067` | 70057 | pre-match lobby (PvP lobby, amplifier set / Stolen Power pickers) | AmplifierSetManager, ChatManager, ConversationManager, DialogsManager, EncounterManager, LanguageManager, OwnablesManager, RibbonManager, SecondaryPowerManager, TipManager | Lobby.ClearLightResourcePackReferences, Lobby.Draft_Banning, Lobby.Draft_EnableTrade, Lobby.Draft_PlayersTrading, Lobby.Draft_Selecting, Lobby.Draft_TradeRequest, Lobby.HideBackButton, Lobby.LobbyEncounterDetails, Lobby.MatchLaunchWarning, Lobby.PlayerPickedAmplifierSet, Lobby.PlayerPickedStolenPowers, Lobby.PlayerSelectedEarlyLaunchFromServer, Lobby.UpdateEarlyLaunchTime, Lobby.UpdateLobbyLoadingPercent, Lobby.UpdateLobbyLoadingPercentForViewmatch, Lobby.UpdateLobbyState, Lobby.UpdateLobbyStateSingle, UI.BatchNotifyHUDElements, UI.GameFrontUIDestroyedInCPP, UI.NotifyHUDElement, UI.ToggleMainMenu, UI.UIStateMachineEvent | `0x2004` `0x2016` `0x2021` `0x2028` `0x2029` `0x2031` `0x2038` `0x204a` `0x204b` `0x204c` `0x2053` `0x2054` `0x2060` `0x2061` `0x206c` `0x206d` `0x213d` `0x213e` |
| `0x2000006b` | 70940 | tooltips | LeaderBoardManager, OwnablesManager, ProtectorIconManager, AccoladeData | - | - |
| `0x2000006c` | 2548 | disconnect dialog |  | UI.gmWErrorMessageOccurred | - |
| `0x2000006d` | 32783 | login / connecting / display-name screens | SettingsManager | Character.MasterCharacterListReceived, ConnectionManager.ShowLoginError, ConnectionManager.UpdateConnectionState, UI.ChargenError | `0x2024` `0x20ed` `0x20ff` |
| `0x2000006e` | 102193 | ribbons (level up, match found, queue...) |  | - | - |
| `0x2000006f` | 29521 | HUD: kill card | ControlledAgentDispatcher, MatchData | - | - |
| `0x20000070` | 29805 | tutorial hints |  | Tutorial.UI_CloseTutorialHint, Tutorial.UI_ShowTutorialHint, Tutorial.UI_ShowTutorialHints | - |
| `0x20000073` | 13284 | browser / social media test (dev) |  | SocialMedia.UI_OnSocialMediaURLUpdated, WebBrowser.OnAddressChange, WebBrowser.OnConsoleMessage, WebBrowser.OnJavaScriptAlert, WebBrowser.OnJavaScriptCallback, WebBrowser.OnJavaScriptContextCreated, WebBrowser.OnLoadEnd, WebBrowser.OnLoadStart, WebBrowser.OnNavStateChange, WebBrowser.OnPopUpWindowRequested, WebBrowser.OnTitleChange | - |
| `0x20000074` | 21561 | new player screen | AchievementsManager, EncounterManager | Achievement.AchievementDetails | - |
| `0x20000075` | 26462 | wrapper main (out-of-match shell; imports every wrapper screen) | AchievementsManager, ChatManager, ContactsManager, CustomMatchManager, DialogsManager, EncounterManager, GameTimer, LanguageManager, RankedManager, RibbonManager, ScorecardManager, WrapperCookie | Achievement.AllPendingAchivementBanners, Character.RewardSetsData, Character.Ribbon_CharacterLevelChanged, Character.Ribbon_FinishedItemsFulfilled, Character.Ribbon_ItemFulfilled, Character.SendAccountCurrencyBalance, Character.SendAccountLevelAndXP, CustomMatch.UI_CustomMatch_Cancelled, CustomMatch.UI_CustomMatch_Kicked, CustomMatch.UI_CustomMatch_Left, Grouping.PlayerLeftGroup, Lobby.LobbyRejoinRoom, UI.BarredFromMatching, UI.DisplayDialogText, UI.FoundMatch, UI.JoinedQueue, UI.PendingMatchFailure, UI.ProtectorAdvancementStatus, UI.RemovedFromQueue, UI.ShowURLDialog, UI.ToggleMainMenu, UI.UIStateMachineEvent, UI.UserCanCreateGroup | `0x2011` `0x2038` `0x203f` `0x2041` `0x2053` `0x205b` `0x2070` `0x2071` `0x2080` `0x2081` `0x2087` `0x2095` `0x20c0` `0x20d7` `0x20e0` `0x20ed` `0x20f3` `0x20fa` `0x2104` `0x210a` `0x210b` `0x211f` `0x2120` `0x2125` `0x215d` `0x216a` `0x218b` `0x2197` |
| `0x20000077` | 61931 | wrapper header (profile, currency, matchmaking indicator) | AchievementsManager, CustomMatchManager, DialogsManager, EncounterManager, PVPGroupManager, RankedManager, RibbonManager, WrapperCookie | Achievement.TraineeAchievements, AdminAlert.UI_NotifyAdminAlertsUpdated, Character.SendAccountCurrencyBalance, UI.FindMatchFailure, UI.Matchmaking_NewUpdateInterval, UI.QueueWaitTimesUpdated, UI.SendHeaderNameAndProtectorIcons | `0x2081` `0x2154` `0x218d` `0x218e` `0x218f` `0x2190` |
| `0x20000078` | 38048 | landing (home) screen | AchievementsManager, ChatManager, CustomMatchManager, DialogsManager, EncounterManager, WrapperCookie, AchievementData | Achievement.AchievementDetails, UI.ProtectorAdvancementStatus, UI.SendHeaderNameAndProtectorIcons | `0x2080` `0x2120` `0x2154` `0x215d` `0x216a` `0x218b` `0x2190` |
| `0x2000007c` | 21316 | store (web) | ChatManager, DialogsManager | WebBrowser.OnJavaScriptCallback, WebBrowser.OnJavaScriptContextCreated, WebBrowser.OnLoadEnd, WebBrowser.OnLoadStart, WebTicket.UI_OnMicroTxnAuthorizationResponse, WebTicket.UI_OnWebTicketUpdated | - |
| `0x2000007f` | 19297 | landing demo | ChatManager, EncounterManager | - | - |
| `0x20000080` | 67351 | dialogs (purchase, confirm, report, group invite, calling card...) | ChatManager, DialogsManager, OwnablesManager, ProtectorIconManager, WrapperCookie, BoutiqueData | WebBrowser.OnJavaScriptCallback, WebBrowser.OnJavaScriptContextCreated, WebBrowser.OnLoadEnd, WebBrowser.OnLoadStart, Character.SendAccountLevelAndXP, UI.FoundMatch, UI.SendHeaderNameAndProtectorIcons | `0x2080` `0x20fa` `0x2154` `0x2190` |
| `0x20000082` | 44325 | party / PvP group screen | ChatManager, DialogsManager, EncounterManager, PVPGroupManager, RibbonManager, WrapperCookie | Contacts.UI_NotifyContactAdded, UI.QueueWaitTimesUpdated | `0x2051` `0x20cc` `0x218f` |
| `0x20000083` | 22288 | chat | ChatManager | Chat.ToggleUnreadChat | `0x20b0` `0x20b6` |
| `0x20000084` | 72854 | artifact widgets (shared by foundry / skill bar) | ControlledAgentDispatcher, MatchData, SettingsManager | Skill.EnableSkillButton, Skill.UI_SkillUpdate, Skill.UpdateSkillUIOverlay, UI.ExecuteSkillError, UI.StartSkillCooldown, UI.UpdateSkillStackCountString | `0x1000015a` `0x207b` `0x2091` `0x2092` `0x20a0` `0x20a2` `0x20a8` `0x20c8` `0x20dc` `0x20f8` `0x2187` |
| `0x20000086` | 48133 | spectator (view match) HUD | MatchData, AgentData | ViewMatch.ViewMatchCameraChange, ViewMatch.ViewMatchFOWControls, ViewMatch.ViewMatchPlayerSkillUse, Vitals.VitalsChanged | `0x42` |
| `0x20000087` | 44399 | artifact foundry (in-match shop) | HudModeManager | - | - |
| `0x2000008a` | 22387 | HUD: selection panel (target) | ControlledAgentDispatcher, MatchData, AttributeMetadata | Character.UpdateCharacterPanelInfo, SelectionSystem.ClearTrackedEntity, SelectionSystem.FoundTrackedEntity, SelectionSystem.LostTrackedEntity, SelectionSystem.UpdateTrackedEntity | - |
| `0x2000008b` | 66002 | friends / contacts / notifications | ChatManager, ContactsManager, DialogsManager, NotificationPreviewsManager | Contacts.UI_ContactListNotification, Contacts.UI_NotifyContactOfInvitations, Contacts.UI_NotifyContactOfInvite, Contacts.UI_NotifyContactOfPendingInvites, Contacts.UI_NotifySelfChangedPresence, Contacts.UI_NotifySelfChangedStatusMessage, CustomMatch.UI_CustomMatch_InviteCancelled, CustomMatch.UI_CustomMatch_Invited, Grouping.GroupInviteCanceled, Grouping.ShowGroupInviteDialog, UI.SendHeaderNameAndProtectorIcons | `0x2003` `0x2013` `0x201f` `0x2027` `0x2033` `0x203a` `0x2058` `0x2065` `0x214c` `0x2154` `0x2190` `0x219c` |
| `0x2000008c` | 43804 | scorecard (end of match) | AchievementsManager, ChatManager, DialogsManager, EncounterManager, OwnablesManager, ScorecardManager | Achievement.AchievementDetails, Achievement.TraineeAchievements, Chat.UpdatedMemberList, Contacts.UI_NotifyContactAdded, Contacts.UI_NotifyContactIgnored, Contacts.UI_NotifyContactUnignored, Encounter.PlayEndOfMatchEncounterMovie, UI.Scorecard_HeavyOnlyLoaded, UI.UIStateMachineEvent | `0x2038` `0x2045` `0x204f` `0x2051` `0x2053` `0x20cc` `0x2135` |
| `0x2000008d` | 102597 | graphical numbers |  | - | - |
| `0x20000090` | 28473 | wrapper footer |  | UI.ReleaseNotesUrl | - |
| `0x20000093` | 68409 | custom match | ChatManager, CustomMatchManager, DialogsManager, EncounterManager, RibbonManager, WrapperCookie, EncounterDataObject | Contacts.UI_NotifyContactAdded, CustomMatch.UI_CustomMatch_Cancelled, CustomMatch.UI_CustomMatch_Kicked, CustomMatch.UI_CustomMatch_Launched, CustomMatch.UI_CustomMatch_Left | `0x2011` `0x203f` `0x2040` `0x2041` `0x2051` `0x20cc` |
| `0x20000094` | 45906 | amplifiers screen | AmplifierSetManager, BoutiqueDataManager, DialogsManager, OwnablesManager | WebTicket.UI_OnWebTicketUpdated, Contextual.PurchaseContextualItemError, Contextual.PurchaseContextualItemSuccess | `0x210c` `0x210d` |
| `0x20000099` | 46006 | tutorial highlight tips |  | - | - |
| `0x2000009a` | 25341 | conversation banner | ConversationManager | - | - |
| `0x2000009c` | 22098 | surrender vote | MatchData | Encounter.SurrenderVoteConcluded, Encounter.UpdateSurrenderData | `0x10000455` `0x10000456` |
| `0x2000009d` | 31103 | scorecard stats tab | ScorecardManager | - | - |
| `0x2000009e` | 29243 | wrapper background | SettingsManager | - | - |
| `0x2000009f` | 19734 | FPS display | SettingsManager | UI.FPSUpdate | - |
| `0x200000a0` | 24398 | calling card |  | - | - |
| `0x200000a1` | 38203 | spectator top bar | ControlledAgentDispatcher, MatchData, AgentData | Encounter.NotifyMatchEnded, Encounter.SetMatchTime, Encounter.UI_InitialTeamHealthUpdate, Encounter.UI_UpdateTeamHealth, ViewMatch.ViewMatch_UpdateDampenerCounts, ViewMatch.ViewMatch_UpdateTurretCounts | `0x1000000e` `0x10000109` `0x10000134` `0x100004fb` `0x215c` |
| `0x200000a2` | 40096 | achievements | AchievementsManager, AchievementData | Achievement.AchievementDetails | - |
| `0x200000a3` | 26603 | stats screen | AccoladeManager, EncounterManager, EncounterDataObject | Character.SendAccountEncounterStats | `0x2115` |
| `0x200000a4` | 42563 | veteran landing (profile overview) | AccoladeManager, AchievementsManager, ChatManager, CustomMatchManager, DialogsManager, EncounterManager, OwnablesManager, SecondaryPowerManager, WrapperCookie | Achievement.AchievementDetails, Encounter.UI_LastMapPlayed, ProfileUI.ProfileUI_HeavyResourcePackData, ProfileUI.ProfileUI_SpecialSecondaryPower | `0x214b` |
| `0x200000a5` | 61541 | characters (collection) screen | AccoladeManager, AmplifierSetManager, OwnablesManager, SecondaryPowerManager | ProfileUI.ProfileUI_AmplifierSetData, ProfileUI.ProfileUI_CharacterVariantsLoaded, ProfileUI.ProfileUI_HeavyResourcePackData, ProfileUI.ProfileUI_SpecialSecondaryPower | - |
| `0x200000a7` | 20270 | launch movie player |  | - | - |
| `0x200000a8` | 29107 | landing nav / switcher | AchievementsManager, DialogsManager | UI.UIStateMachineEvent | `0x2038` `0x2053` |
| `0x200000a9` | 23386 | encounter details | ChatManager, DialogsManager, EncounterManager, WrapperCookie | - | - |
| `0x200000aa` | 62693 | encounter / map / mode / tutorial selection | AccoladeManager, DialogsManager, EncounterManager, WrapperCookie | - | - |
| `0x200000ab` | 30747 | floaty verbs |  | - | - |
| `0x200000ad` | 42314 | scorecard accolades tab | AchievementsManager, EncounterManager, OwnablesManager, RankedManager, RibbonManager, ScorecardManager, SecondaryPowerManager, WrapperCookie, AccoladeData | Achievement.AchievementDetails, Encounter.UI_LastMapPlayed | `0x214b` |
| `0x200000ae` | 30198 | accolades widget | OwnablesManager, AccoladeData | - | - |
| `0x200000b0` | 80169 | ranked badges |  | - | - |
| `0x200000b1` | 43126 | login rewards | ChatManager, RibbonManager | LoginReward.UI_DeliverLoginRewardSet, LoginReward.UI_NoEligibleLoginReward | `0x219d` |
| `0x200000b2` | 30250 | ranked / leaderboards screen |  | - | - |

---

## 3. Screen by screen: what the server must send, what `ics` sends, what is missing

`ics` today (from `ics/messages.py`, `ics/session.py`): login `initial_events` = `0xEB`, `0x20B8` (champions and
costumes only), `0x20ED`, `0x209D`, `0x2024`, `0x216A` (empty), `0x2120` (empty), `0x218B` (featured maps),
`0x215D`, `0xCE`, `0x2080`; queue/lobby `0x20C0`, `0x20FA`, `0x20AD`, `0x2028`, `0x2029`, `0x204C`, `0x2016`,
`0x206D`, `0x2031`, `0x20AF`; match: object creation `0x4` (champion/player properties incl. Level, XP, SkillPoints,
currency, team), `0x42` vitals, `0x8D` scriptlets, `0x20F5` cinematic, `0x213D` HUD elements, `0x2034`/`0x2009`
objectives, `0x2001` conversations, notice `0x1000027F` hints, `0x100002EB`/`0x100002EC` announcements, `0x20F8`
cooldowns, `0x20E2` inventory, `0x2078` recommended, `0x2086` shop done, `0x100004D6` floaty currency,
`0x10000090`/`0x100000BC` defeat, `0x1000000E` match ended. Handles C->S `0x20EB 0x20CA 0x20F2 0x20D5 0x2 0x20EE
0x216E 0x2136 0x2102 0x208B 0x20A7 0x12D`. Builders that exist but are not called: `end_of_match_stats` (`0x2045`),
`completed_encounters` (`0x214B`), `exit_lobby` (`0x2021`), `server_preferences`, `timeline_banner`.

| Screen | Movies | Server must send (S->C) / answer (C->S) | Sent by `ics` | Missing | Tag |
|---|---|---|---|---|---|
| Login, connecting, display name | `0x2000006D`, `0x2000006C` (disconnect), `0x2000009E` (background), `0x20000090` (footer) | connection handshake; `0x20ED` (MasterCharacterListReceived), `0x2024`; if the account has no name: RequestScreenName flow (`SubmitScreenName`, ChargenError) | handshake, `0x20ED`, `0x2024` | display-name flow (not needed while the name is fixed); release-notes URL is local | C |
| Landing (home), header, nav | `0x20000075` wrapper, `0x20000078`, `0x200000A8`, `0x20000077`, `0x200000A4` (veteran landing), `0x20000074` (new player), `0x2000009E` | login list (3.1 of `progression-meta.md`); header **`0x2190` / `0x2154`** (name + protector icons), currency **`0x2081`**, `0x2080` + `0x2120` + `0x215D` (ProtectorAdvancementStatus), `0x214B` (last map / completed), `0x218F` queue wait times, `0x218D`/`0x218E` matchmaking | login list | `0x2190`, `0x2154`, `0x2081`, `0x214B`, `0x218F` (the header shows defaults without them) | C ids / P feeders |
| Encounter / map / mode selection, details | `0x200000AA`, `0x200000A9` | `0x2024` encounter info, `0x218B` featured maps, `0x2101` QueueEligibility, `0x20FF` reset map list; C->S JoinQueue `0x20EB` | `0x2024`, `0x218B`, `0x20EB` handled | `0x2101` (eligibility, probably defaults to allowed [P]) | P |
| Champion select / lobby | `0x20000067`, `0x20000022`, `0x2000006E` (ribbons), `0x2000006B` (tooltips) | `0x20FA`, `0x20AD`, `0x2028`, `0x2029`, `0x204C`, `0x2016`, `0x206D`, `0x2031`; amplifier sets **`0x2090`** + **`0x204A`**/**`0x2060`**; Stolen Powers `0x2004`/`0x2060`; `0x2061` early-launch time, `0x204B` launch warning, `0x206C`; answer C->S `0x2102` select, `0x2025` picker info, `0x200D` change set, `0x2057` my set | all of the first group, `0x2102` | amplifier-set and Stolen-Power pickers (`0x2090`, `0x204A`, `0x2060`, `0x2004`); C->S `0x200D`/`0x2057`/`0x2025` unhandled | C |
| Loadouts: amplifiers | `0x20000094` (+ dialogs `0x20000080`) | `0x2090` list, `0x20C7` one set, `0x2052` errors, `0x2107` boutique prices; owned augments/mods as `0x20B8` content types 12/13; answer `0x20FC` save | none of these | everything (the screen opens empty) | C |
| Store | `0x2000007C` (CEF web page) | none from the game server: `InqStoreURL` + Steam web ticket; contextual buys `0x210C`/`0x210D`/`0x210F`, balance `0x2081` | - | disable or grant directly (preservation) | C |
| Collection (characters screen) | `0x200000A5` | `0x20B8`, `0x20ED`, `0x209D` (advancement per champion); ProfileUI notices are local (raised when the heavy pack loads); amplifier sets `0x2090` | `0x20B8`, `0x20ED`, `0x209D` | `0x2090` (amplifier tab) | C |
| Profile / calling card | `0x200000A4`, `0x20000080` (calling-card dialog), `0x200000A0`, `0x20000077` | `0x2190`/`0x2154`, `0x2186` best accolades, `0x214B`, `0x2120`, `0x219E`/`0x219F` standings; answer `0x2093` set protector icon | - | all | C ids / P feeders |
| Friends, notifications | `0x2000008B`, `0x20000090` | contact list + presence (`0x203B` list n=0 is probably enough; `0x2051`/`0x20CC` added, `0x2018`/`0x20AE` presence, `0x2003`/`0x2013`/`0x219C` invites, `0x2014`/`0x205E` groups, `0x2058`/`0x203A` self status) | - | an empty list (menu works without it [G]) | C ids / G minimum |
| Party (PvP group) | `0x20000082` | `0x2070` can create group, `0x2071` group state, `0x2033` invite dialog, `0x214C`, `0x217D` | - | all (solo play does not need it) | C |
| Chat | `0x20000083` + ChatManager | channel join (C->S `0x20A6`), lines `0x20B0`/`0x20B6` (`ToggleUnreadChat`), member list `0x2135`, system text `0xAB`/`0xC9`; C->S `0x20F6` | - | all | C ids / G for line delivery |
| Achievements | `0x200000A2` | `0x2120` progress (+ `0x21A6`), `0x211F` pending banners; details are local queries on the records | `0x2120` empty | real progress | C |
| Rewards, login rewards, ribbons | `0x200000B1`, `0x2000006E`, wrapper | `0x2125` reward sets (`RewardSetsData`), `0x2197` login reward set / `0x219D` none eligible, `0x2095` item fulfilled, `0x2104` level-up ribbon, `0x20D7`/`0x210B` match failure ribbons | - (icserver has them) | `0x219D` at least (else the login-reward screen waits), rewards | C |
| Settings, key bindings | `0x2000005F` | local only (options, key bindings); `0x216A` server options; C->S `0x216E` | `0x216A`, `0x216E` | - | C |
| HUD: vitals, floaties | `0x2000002B`, `0x20000006`, `0x20000010`, `0x200000AB` | `0x42` vitals, `0x44` floaty status, `0x208D`/`0x20BD` [P], `0x2171`-`0x2173` training floaty text; properties XP/currency (floaties follow the deltas) | `0x42`, properties | `0x44`, training floaties (tutorial only) | C/P |
| HUD: skill bar | `0x20000056`, `0x20000084` | properties (`0x100000AF` ranks, SkillPoints), `0x20F8` cooldown, `0x1000015A`/`0x2091` overlay, `0x207B`/`0x20A0`/`0x2187` enable button, `0x2092`/`0x20DC` skill errors, `0x20A2`/`0x20A8`/`0x20C8`/`0x20E9` stack strings; **ranking: `0x9F 0x81A1000B` then answer `0x9F 0x81910003`** (1.7) | properties, `0x20F8` | errors/enables (optional), unpatched ranking | C / P for ranking |
| HUD: XP bar | `0x20000011` | properties Level/XP; thresholds come from the WLib (`InqXPForLevel`, `InqLevelCap`) once the handlers are registered | properties | thresholds (patched client falls back to test values) | C |
| HUD: status icons | `0x20000063` | `0x20A2`/`0x20C8` add, `0x20A8` update, `0x20E9` remove, `0x20D0`/`0x2127` tooltip | - | all (no buff icons) | P |
| HUD: objectives, timeline, match bar | `0x20000064`, `0x20000065`, `0x2000000C`, `0x200000A1` | `0x2034`/`0x2009` objectives, `0x2023` category, `0x2075` tracker on; timeline `0x100002AF`/`0x100002B1`/`0x10000424` (after `UI_ReadyForTimelineData 0x100002AD`); match time `0x10000109`, team health `0x100004FB`/`0x10000134` (after `0x10000137`/`0x100000D2`); sector trackers `0x2069` | objectives, timeline built but off | match time, team health, trackers (PvP) | C |
| HUD: minimap, pings | `0x2000000F` | map notes are local (MapManager) except `0x2137` remove, `0x209F`/`0x217F`/`0x2180` targeting ring, `0x2189`/`0x218A` teleport | - | PvP extras | P |
| HUD: billboards, kill feed, kill card | `0x20000015`, `0x2000005B`, `0x2000006F` | `0x100002EB`/`0x100002EC`/`0x100002BC`, `0x100000CB`/`0x100000CE` joined/left, kill feed `0x1000021C`/`0x100002B2` [P], kill card data (local `UI_ShowKillCard`, fed by the defeat system) | `0x100002EB`/`0x100002EC` | kill feed / player joined (PvP) | P |
| HUD: defeat / respawn | `0x20000013` | `0x10000090`, `0x100000BC`, `0x100000BA` pause, `0x2078` recommendations | `0x10000090`, `0x100000BC`, `0x2078` | - | C |
| HUD: currency, artifact foundry | `0x20000057`, `0x20000087`, `0x20000084`, `0x2000005E` (power graph) | `Upgrade_Currency` property, `0x20E2` (UpdateCurrentUpgrades + UpdatePowerGraphValues), `0x2078`, `0x2086`; answer `0x208B`/`0x20A7` | all | - | C |
| HUD: conversation, hints, highlights | `0x2000009A`, `0x20000070`, `0x20000099` | `0x2001` conversation, notice `0x1000027F` hint; ActivatedArtifacts from script node `0x10000183` | yes | - | C |
| HUD: character / selection / player-info panels | `0x2000005A`, `0x2000008A`, `0x20000062` | agent properties and participants (MatchData `AddParticipant` raised locally when agents exist [P]) | properties | - | P |
| HUD: top bar, start menu, surrender, FPS | `0x2000005C`, `0x2000000D`, `0x2000009C`, `0x2000009F` | surrender `0x10000455`/`0x10000456`, answer `0x10000454`; the rest local | - | surrender (PvP) | C |
| In-match scoreboard (Tab) | MatchData via `0x2000000C`/`0x20000062` | `UI_UpdateMatchScorecard 0x1000007E` after `RequestMatchScorecard`; candidate network source notice `0x1000005B` (list of `{StringInfo, 3 u64, 7 u32, u8}`) [G] | - | open | G |
| End of match / scorecard | `0x2000008C`, `0x2000009D`, `0x200000AD`, `0x200000AE`, `0x20000080` | `0x1000000E` + `0x2038`; prerequisites `0x2190`, `0x2045`, `0x2188`, `0x2080`, `0x2081`, `0x20B9`, `0x2104`, `0x2090`, `0x219F`/`0x219E`; then `0x212E`->`0x211F`, `0x2125`, `0x2095`; `0x2021` exit | `0x1000000E` only (the client leaves itself) | the whole scorecard (builders in `icserver/scorecard.py`) | C |
| Custom match | `0x20000093` | `0x2011`, `0x2012`, `0x201F`, `0x2027`, `0x203F`-`0x2042`, `0x2103`, `0x2109`, `0x2151`, `0x217C`; `UI_DeliverCustomMatchData 0x10000389` | - | all | C |
| Ranked, leaderboards, stats | `0x200000B2`, `0x200000B0`, `0x200000A3` | `0x219E`/`0x219F`, `0x21A2`/`0x21A3` (C->S `0x21A4`), `0x2115` (C->S `0x2116`) | - | all | C |
| Spectator | `0x20000086`, `0x200000A1` | ViewMatch notices (`0x215C` dampener counts, scoreboard data) | - | not needed | P |
| Loading, launch movie, video | `0x20000020`, `0x200000A7`, `0x20000066` | `0x2031` loading percent; local | `0x2031` | - | C |

---

## 4. Open points and runtime tests

1. **Advancement registration**: send `0x9F` (dest `0x0200000000000001`, message `0x81A1000B`, empty blob) after the
   player and the champion exist, with the rank patches off; `tools\diag.py` breakpoint on `0x962E00` must hit. Then
   decode the client's `0x9F 0x81910003` (`u32, u32, u64`) and answer `0x9F 0x81910001` (`u32, object, u32, u64`;
   the object reference encoding of `0x830003`/`0x830008` is not decoded yet).
2. The exact `0x9F` blob framing (u32 length + bytes vs. compact length) and the object-reference format inside the
   argument stream (`0x476D70` / `0x476D90`).
3. XP table: which DID native `0x340001(0xB, 0x10000027)` returns and the field layout of WLib type `0x21D`.
4. Opcodes beyond those in 1.2 (arithmetic, compares, branches) are not named; enough for structure, not for full
   decompilation of method bodies.
5. Event-to-notice mapping of the UI is by name ([P]); confirm the less obvious ones (`0x2101`, `0x2186`, `0x21A6`,
   contact list event) with `diag.py` on the handlers.
6. Missing UI records `0x20000003/05/08/17/19/26` (font / locale libraries [P]).

## 5. Method (reproducible)

- WLib: record extracted with `ics.rp.Pack`; sections walked by the `0xFEDC1234` headers; code swept with the length
  table of `0xAE6400`; types parsed as in 1.3 (exact end of section = check); function owners from the vtables;
  natives from the 1978 `push func; push id; mov ecx; call 0x6B2E10` sites; network reachability from
  `old_files/tools/analysis/callgraph.json` (depth 6 to `0x444A90`); exe code read with capstone and Ghidra (REA).
- UI: `0x20` records parsed as in 2.1; movies scanned with `old_files/tools/swf_as2.py` (tags 12/59 recursively,
  ExportAssets, ImportAssets, frame labels); AS2 classes, methods, notice-id getters and `GM_*.SendNotice_*` calls
  parsed from `classes_all.txt`; listeners = `Notice_*_ID` references in each class; network feeders matched by the
  Flash names in `protocol-server-to-client.md`.
