# Complete network protocol catalogue (static analysis + 2026-10-21 logs, written 2026-10-22)

One place for everything the client (`InfiniteCrisis.exe`, image base 0x400000, **all addresses are VAs**) sends
and receives: the connection layer, the login, every client → server event and notice, every server → client event
and network notice, and a priority table for the server. It supersedes the tables of
`protocol-client-to-server.md` and `protocol-server-to-client.md` (kept for their method notes) and corrects them
where noted.

**Evidence levels.** *confirmed* = seen in `logs/traffic.log` / `logs/unhandled.log` of the 2026-10-21 run, or proven
by the client's code (dispatcher slot, call chain, serializer run in an emulator); *probable* = structural or naming
inference. Several addresses quoted as "rva" in `ics/messages.py` docstrings are really VA − 0x400000
(e.g. welcome handler rva `0xbe4950` = VA `0xfe4950`).

**How it was enumerated (not sampled).**
- Event classes: every `mov [r+8], id` followed by `mov [r+0xC], 0x300400` in `.text`: **484 constructions, 438
  distinct event ids** (3 constructions with the id set elsewhere).
- Client senders: every call of the send helper `0x444a90` (**161 call sites in 159 functions**). Each was tied to its
  event id; this found 2 senders the earlier notes missed (`0x20C3` LeaveQueue and the local-only `0xD0`, `0xAD`,
  `0x12C`, `0x9D` senders).
- Receivable events: all 336 calls of the registry `0xb0ec50`; receivable notices: all 464 calls of `0x483240`
  (44 with a network reader).
- Connection packets: all 12 calls of the packet registry `0xb03a80`.
- Body layouts of client events: each serializer (vtable slot 7) was run in a unicorn emulator **with the packed
  stream flag 0x800 set** (what the client really uses, see §1.4) and checked against the logged bodies.
- Names: Flash listener vtables were aligned with the C++ notice dispatchers (`0x4820f0` callers give
  `notice id → listener slot`). A name is *confirmed* when the slot of the sending wrapper equals the dispatcher's slot
  for that notice in a vtable where many neighbouring slots also match.

---------------------------------------------------------------------------------------------------------------------

## 1. Connection layer

### 1.1 Frame

Every TCP read is a sequence of frames: `u32 length (LE) | payload[length]`. Parser `0xb0af10`:

| header bit (payload[0]) | meaning |
|---|---|
| `0x01` | **packet block**: `u32 packet mask (LE)` follows, then one sub-packet per set bit (§1.2), in ascending bit order (the registry keeps them sorted, `0xb03a80`). The mask's low byte is not a packet bit. *(confirmed)* |
| `0x02` | **game message**: `u64 destination \| u8 message flags \| compact event id \| event body` (rest of the frame). *(confirmed)* |
| `0x04` | only with 0x02: the message keeps a reference to the receive buffer instead of copying it (`0xb0b10d`); no wire difference. *(probable)* |

Bits 0x01 and 0x02 can be combined (packets first, then the message) *(confirmed by the parser; never seen on the wire)*.

**Message flags byte.** The client always sends `0x01`. The server sends `0x02`; bit 0x02 lets the message through the
client's delivery gate (`0xfe1b50`) while it is still loading (ics/wire.py). *(confirmed)*

**Event id** is a compact int (`<0x80` 1 byte; `<0x4000` 2 bytes `0x80|hi, lo`; `<0x20000000` 4 bytes; else `0xE0`+u32),
e.g. `a0 ba` = 0x20BA, `80 cc` = 0xCC. *(confirmed)*

### 1.2 Connection packets (packet block, header bit 0x01)

Registered by `0xb0acc0` (all 12 calls of `0xb03a80`). Base connection dispatcher `0xb03cc0` handles 0x1000000 /
0x2000000 / 0x4000000 (vtable +0x28 / +0x2C / +0x30); the others are handled by the user / game connection classes
(welcome `0xfe4950`, ServerSwitch `0xfe2080`, Referral `0x6a8890 → 0xfe3240`). Layouts from running each reader:

| mask | reader | layout | direction / when | server must |
|---|---|---|---|---|
| `0x100` | `0xb0a010` | `u32 sequence` | S→C **ServerSwitch**: makes the game connection current | send it right after the game welcome; without it the client drops the game connection when match data loads *(confirmed, ics)* |
| `0x800` | `0xb090d0` | `u64 cookie \| u16 \| u8 flags \| u8 \| u16 port \| char[256] host` | S→C **Referral** (after AcceptMatch): connect to the game server | ics sends cookie 1 *(confirmed)* |
| `0x8000` | `0xfe2610` | empty | C→S **disconnect**: seen once on the game connection when the client quit (23:30:48.962) | nothing; close *(confirmed on the wire, meaning probable)* |
| `0x10000` | `0xb08570` | `str8 version \| u32 n \| n bytes connect blob` | C→S **login connect request**, first frame on the user connection. Version `141112_netver:7948`; blob = `u32 0x2711 \| u32 1 \| u32 nonce \| str8 "3des" \| u32 128 \| 128-byte RSA-encrypted 3DES session key \| u32 0x18 \| u32 0x10 \| 16 bytes` (173 bytes) | decrypt the key (ics/crypto.py), answer with welcome 0x40000 and the account data *(confirmed layout; the meaning of 0x2711 / nonce / last 24 bytes probable: version, random id, encrypted ticket)* |
| `0x20000` | `0xb05bd0` | `u64` (big-endian 1 in the log) | C→S first frame on the **game** connection: the referral cookie echoed | answer with welcome 0x40000 + ServerSwitch *(confirmed on the wire, meaning probable)* |
| `0x40000` | `0xb05070` | `16 bytes route id \| BE f64 server time \| 8 bytes \| u32 \| BE u32 \| BE u32 connection id` (44 bytes) | S→C **welcome** on both connections | ics: zero route id, `1, 1` *(confirmed)* |
| `0x80000` | `0xb09040` | `GUID \| u64` | C→S on the game connection right after 0x20000 (a GUID + 0) | nothing needed *(confirmed on the wire, meaning unknown)* |
| `0x100000` | `0xb08fb0` | `u32 \| u32` | not seen | — |
| `0x200000` | `0xb09170` | `u32 \| u32` | not seen | — |
| `0x1000000` | `0xb04af0` | `BE f64 time` | **time**, both ways. S→C: ics every 2 s on the game connection; without it the client drops the game connection after 60 s. C→S: every 10 s on each connection (its wall clock) | send it (keepalive) *(confirmed)* |
| `0x2000000` | `0xb04db0` | `BE u32` | C→S every 10 s with the time packet: a millisecond counter (11010, 21018, 31053 … on the user connection) | nothing *(confirmed on the wire; ping counter probable)* |
| `0x4000000` | `0xb04f40` | `u32 \| u32` | not seen; base handler slot +0x30 — probably the ping echo for 0x2000000 | not needed so far *(probable)* |

### 1.3 Handshake sequences (2026-10-21 run)

```
SOAP  POST /WebLoginApp-1.3/Metrics      form: user_name, machine_name, event_type=GameClientStart, pcid (MAC),
                                          time_stamp, language          -> ics answers an empty envelope
SOAP  POST /WebLoginApp-1.3/AuthenticateWS  AuthSelect{userName, password, region, language, steamid}
                                          -> AuthSelectResponse{loginTicket, randomID, sessionKey, userServerAddr,
                                             userServerPort}; errorString must be ABSENT on success
      (getLauncherData is asked only by the launcher: Launcher.*, Patch.*, GameClient.* name/value pairs)
user  C: 0x10000 connect request (version, RSA blob)
      S: 0x40000 welcome, then account data (0xEB, 0x20B8, 0x20ED, 0x209D, 0x2024, 0x216A, 0x2120, 0x218B, 0x215D,
         0xCE, 0x2080 last: it opens the landing-screen gate)
      C: 0x20D4, 0x20E3 (machine info), 0x212E, 0x20C4, 0x216E (all preferences) ...
      C: 0x20EB join queue      S: 0x20C0, 0x20FA
      C: 0x20CA accept          S: 0x20AD, 0x2028, 0x800 referral
game  C: 0x20000 cookie       S: 0x40000 welcome, 0x100 ServerSwitch; (user) 0x20AF enter match, 0x2016
      C: 0x80000, 0x1000000 + 0x2000000 every 10 s on both connections; S: 0x1000000 every 2 s (game)
user  C: 0x20BA, 0x20F2 connect to lobby  S: 0x2029, 0x204C, 0x2016, 0x206D
game  C: 0xCC level loaded; user C: 0x20D5 loading % ...  S: 0x2031; objects (0x4) on the user connection
game  C: 0x211B, 0x207A, 0x213A, notice 0x10000207, 0x211B, 0x20D3, 0x2139 ... notice 0x10000204, 0x212C,
      notice 0x1000015E (load complete) ...
game  C: 0x8000 disconnect when the client quits
```

UDP: the client also sends log datagrams to the user port (ics logs them, `server._udp_log`). *(confirmed)*

### 1.4 Base byte and packed streams

- **Server → client** bodies start with the **u8 base byte** (`0xb0d380` reads it unless the stream has flag 0x800;
  its value is the low byte of the event's `+0xC` field, always 0). Batch sub-events and notice blobs are packed (no
  base byte). *(confirmed)*
- **Client → server** bodies have **no base byte**: the client writes with the packed flag 0x800 (0x20D4's body is
  1 byte = its u8; 0xCC's is 8 bytes = its u64; notice bodies start directly with the notice id). Packed mode also
  narrows some fields (scriptlet run flags u32 → u8, seen in 0xDA). *(confirmed)*
- Serializers of the object-service family **refuse packed streams** (they set error `0x81960005` when flag 0x800 is
  set): 0x82, 0x8C, 0x8F, 0x91, 0x97, 0x9B, 0xAD, 0xC0, 0xC1, 0xCA, 0xD0, 0xD1, 0xE4, 0xE6, 0xF3, 0xFA, 0xFD, 0x103,
  0x10B, 0x111, 0x113, 0x11A, 0x11B, 0x11F, 0x121, 0x127, 0x12B, 0x12C, 0x133, 0x134. The client posts them through
  the same helper but they cannot be written to the server connection: they are local (client-side object services,
  several triggered by the handlers of the S→C events 0xE4, 0x112, 0x11A, 0x11B, 0xA3, 0xE6, 0x113, 0xD1).
  *(confirmed that they refuse; "never on the wire" probable, consistent with the logs)*

### 1.5 How the client sends an event

Sender = `if ([0x1b6ab18]+0x1D8 == 0) return E_FAIL` → route struct (first dword 0, service id from the table
`0x1854460`: k = 0 → `0x0600000000000400` world, 1 → `…401` lobby/account, 2 → `…402`; or an object IID) + mode word
(1 or 2) → allocate + construct the event → `0x444a90(hr, event, route)` → router `[0x1ba1288]` vt+0x18. The server
sees dest `0x0600000000000401` (lobby service, sent on the user connection), `0x0600000000000008` (world service 0x400
rewritten to the world route, game connection), `0x0600000000000402` (0xCC only) or an object IID (notices, script
events). *(confirmed by the logs)*

Notation in the tables: `str8` = compact length + ASCII bytes (`0x424b80`), `wstr` = compact length + UTF-16
(`0x421690`/`0x4215d0`), `list<u32>` = `u32 n + n × u32`, `Handle` = `u32 seq | u64 iid`, `QueueKey` = `u32 encounter DID
| u32 queue flags`, `StringInfo` = see reverse-engineering.md. Packed layouts (what the server receives).

---------------------------------------------------------------------------------------------------------------------

## 2. Client → server

### 2.1 Events named in the task (the ones `ics` logs as unhandled), in detail

| id | dest | exact body (packed) | sent when | server must answer | evidence |
|---|---|---|---|---|---|
| `0x00DA` | 400 (mode 1) | `u64 entity \| u8 DID high byte \| compact DID low 24 bits \| u8 run flags \| u8 field mask \| [0x01] u64 originator \| [0x20] u64 \| [0x02] property table \| [0x04/0x10] f32 \| [0x08/0x40] u32 \| f64 start time` (order of the 0x04-0x40 fields not verified; same parameter block as one 0x8D entry, packed). Log: entity 0x02…02, DID **0x10000320 Fidgets_Disable** (then 0x10000321 Fidgets_Enable), flags 0x1E, mask 0x01, originator 0x02…01, f64 unix time | Scriptlet runner `0x628bf0`: a scriptlet whose descriptor has flags 4 and 2 (networked) starts on an object the client does not own (`0x550140` false) → the client does **not** run it, it asks the server (sender `0x692cb0`). Seen at the start and end of the Catwoman cinematic | Re-broadcast it as **0x8D** to the entity (same DID / parameters) for every client; for a single player it only costs the fidget animation toggle | layout + trigger *confirmed*; expected reply *probable* |
| `0x00CC` | 402 (mode 2) | `u64 account character id` (`[0x1b579f0]`; log `0x0200000000000001`) | `0xa097a0` level-load done (+10 % loading step) | none | *confirmed* |
| `0x20BE` | 401 | `u32 1 \| u32 16 \| u32 0 \| u32 6 \| u32 frames (46849) \| wstr parent \| wstr stat \| f32 min \| f32 max \| f32 avg \| f32 stddev \| f32 samples \| f32 \| f32 \| f32 \| f32 \| f32 count` (88 per match) | `0xa97ea0` at match end: one per profiler stat (StatRoot, GameThread, DeleteDrawList, …) | none (telemetry) | layout *confirmed*; header field names *probable* |
| `0x20B4` | 401 | `u32 1 \| u32 GPU vendor (0x10DE) \| u32 GPU device (0x2DD8) \| u32 width \| u32 height \| u32 width \| u32 height \| f32 (74939.7) \| wstr parent \| wstr stat \| 10 × f32 (as 0x20BE)` — no serializer vtable, written by `0x888820` itself | `0xa98200` at match end (42 per match): GPU-tagged profiler stats | none (telemetry) | *confirmed* |
| `0x214F` | 401 | `wstr parent \| wstr stat \| f32 min \| f32 max \| f32 avg \| f32 stddev \| f32 samples` | `0xa98550` at match end: render counters (StreaksRendered, ParticlesRendered, ParticleSystemsRendered …) | none (perf telemetry) | *confirmed* |
| `0x2139` | 400 (mode 2) | `u32 encounter DID \| u8 held` (log `0x40000991 00`) | `InputAction_Camera_TempLock` (`0x10000064`) press / release (`0xa30e70`, `0xa336b0`), also camera-override pops from scripts (`0x967730`, `0x968f30`) | none; a tutorial step may wait for it | *confirmed* |
| `0x213A` | 400 (mode 2) | `u32 encounter DID \| u8 camera locked` (log `0x40000991 01`) | `InputAction_Camera_ToggleLock` (`0x10000065`, `0xa30df0`); the client also saves `User.CameraLocked` | none | *confirmed* |
| `0x211B` | 400 (mode 1) | `u64 entity` (log 0x02…01, then 0x02…02) | a component attached to the local player / its controlled agent (`0xa9f9f0`, `0xa9e080`) | none | *confirmed* |
| `0x207A` | 400 (mode 2) | `u8 flag` (`[0x186ce07]`, log 0) | world-entry setup `0xa23140` (and `0xa16d50`) | none | *confirmed layout; meaning probable* |
| `0x20D3` | 400 (mode 2) | empty | the local player's controlled agent changed (`0xa8d5e0`, `0xa8d680`) | none | *confirmed* |
| `0x212C` | 400 (mode 1) | `list<u32>` of SkillSlot ids (log `6 × 10..15`) | Upgrade listener (vtable `0x1605ae0`) slot 1 `0xa5ea70`: artifact-slot order; it first applies the order locally (upgrade component `obj+0xA4` vt+0x54, the same call as S→C 0x212B), at load complete | none (optionally echo 0x212B) | *confirmed layout/trigger; reply probable* |
| `0x20D4` | 401 | `u8` (`obj+0xC6`, log 0) | `0xa9be40` after login account data, before 0x20E3 | none | *confirmed* |
| `0x20E3` | 401 | `str8 MAC address \| wstr machine name \| wstr memory info \| wstr OS version info \| wstr CPU info \| wstr GPU device/vendor info` | `0xa97bd0` at login | none (machine telemetry; do not store) | *confirmed* |
| `0x212E` | 401 | empty | Notice_Achievement__RequestAllPendingRewardlessAchievementNotifications (achievement listener `0x1604498` slot 0x14) when its list is empty; right after login | **0x211F** (empty table is enough) — ics does not answer yet | *confirmed* |
| `0x20C4` | 401 | empty | slot 0 (`0xab9540`) of the lobby client object (vtable `0x160adb8`): once when flag `obj+0x4ED` is set and the throttle allows it; seen 1.3 s after login | none | *confirmed layout; meaning unknown* |
| `0x20BA` | 401 | empty | `0xa2fc80` (throttled; listener at `0x1601e50`); seen when the game connection came up. Probable Notice_Character__RequestPostMatchChanges (0x10000251) | none needed (old server: the post-match deltas 0x2080 / 0x2104 / 0x20B9 / 0x2188 are the natural answer) | *layout confirmed, name probable* |
| `0x20EA` | 400 (mode 2) | `u32 \| list<u32>` | `0xa23510`, reached from the order API (`0xa700a6`, `0xa70900`, `0xa8b0b0`) and `0xa33bd0`/`0xa33c90` | none known | *layout confirmed; meaning unknown* |
| `0x2106` | 401 | `str8` (locale/region from `[0x4092a0]`->vt+0xDC) | throttled UI request (`0xa2fcd0`) | unknown | *layout confirmed; meaning probable* |
| `0x21A4` | 401 | `u32` | **Notice_UI__RequestLeaderboards** (UI listener `0x1602a80` slot 0xE0 = dispatcher slot) | 0x21A2 / 0x21A3 leaderboards | *confirmed name; reply probable* |
| `0x2116` | 401 | empty | **Notice_Character__RequestAccountEncounterStats** (Character listener `0x1604af8` slot 0x38 = dispatcher slot) | 0x2115 account encounter stats | *confirmed name; reply probable* |
| notice `0x10000207` | 0x02…01 | `u32 0x10000207 \| u32 0` | `0xa0a510`: the local player's controlled agent changed (the "link" step) | none | *confirmed* |
| notice `0x10000204` | 0x02…01 | `u32 0x10000204 \| u32 0` | `0xa964b0`: all loaded (0x206D seen) and load complete; the client also raises UI event 0x33 (entered the match) | none required (the client is ready; a server may start the match here) | *confirmed* |

### 2.2 Every client → server event

Columns: **svc** = route (400 world / game connection, 401 lobby-account / user connection, 402, obj = an object
IID); **m** = mode word; **cat** = match / menus / social / telemetry / local. **ics**: H = handled, U = logged as
unhandled. Names in bold are confirmed (dispatcher slot, runtime use or code); others *(probable)*.

| id | name / meaning | svc m | body (packed) | sender ← trigger | server reply | cat | ics |
|---|---|---|---|---|---|---|---|
| `0x0002` | notice (8 kinds, §2.3) | obj | `u32 notice \| u32 len \| args` | 8 senders | per notice | match | H/U |
| `0x0095` | empty object event | 400 m1 | empty | `0x692df0` ← `0x420b90` | none | local? | – |
| `0x009F` / `0x00D2` / `0x0112` | **script native → entity message** | target obj | `u32 message \| u32 len \| arg blob` | `0x562300`, `0x563970`, `0x563b20`, `0x5624f0`, `0x563440`, `0x5635b0`, `0x563730` ← natives `0xC20003-0xC2000D` | the entity's server script reacts | match | – |
| `0x00CC` | **level loaded** | 402 m2 | `u64` | `0x692a80` ← `0xa097a0` | none | match | U |
| `0x00DA` | **networked scriptlet request** (§2.1) | 400 m1 | see §2.1 | `0x692cb0` ← `0x628bf0` | 0x8D | match | U |
| `0x00DC` | **performance report** | 400 m2 | `u64 \| 2 × (u32,u32) \| 6 × (u32,u32,u32) \| 2 × (u32,u32,u32) \| u32 \| u32 \| u32` | `0x6927b0` ← `0x633170` = handler of S→C **0xA8** | none (answer to 0xA8) | telemetry | – |
| `0x00EA` | object event u32,u32 | obj | `u32 \| u32` | `0x6932e0` ← `0x62b450`, `0x62b7b0` | unknown | match | – |
| `0x009D` | object event, empty when packed | obj | empty (unpacked: base byte only) | `0x6366d0` region (inline) | unknown | local? | – |
| `0x0098` / `0x00A3` | object events built without a vtable serializer (`0x5608e0`, `0x5884f0`) | obj | not identified | `0x562dd0`, `0x564aa0`, `0x565656` / `0x58b080` | — | local? | – |
| `0x012D` | **left the match world** | 400 m2 | empty | `0x692950` ← `0xa99b60` | none | match | H |
| `0x201A` | UI event, empty | 400 m2 | empty | `0x886cb0` ← `0xa80cd0` | unknown | match | – |
| `0x2097` | UI slot event, empty | 400 m2 | empty | `0x88af00` ← `0xa0e5b0` | unknown | match | – |
| `0x20AB` | **hold position flag** | 400 m2 | `u8` | `0x88b150` ← `0xa0abf0` (1 after InputAction_Hold, 0 after stop/cast), `0xa404d0` | none | match | – |
| `0x20D1` | selected / inspected object | 400 m2 | `u64 \| u64` | `0x88b7a0` ← `0xa5d250` | none | match | – |
| `0x20D3` | controlled agent changed | 400 m2 | empty | §2.1 | none | match | U |
| `0x20EA` | order-related list | 400 m2 | `u32 \| list<u32>` | §2.1 | ? | match | U |
| `0x20EE` | **order: move / attack / skill / stop** | 400 m2 | `u32 command \| u32 ability slot \| u64 target \| Position \| u8` (built in place, no vtable) | `0x88b030` ← `0xa70030` order API | object updates (movement, 0x8D, 0x42, 0x20F8) | match | H |
| `0x207A` | world-entry flag | 400 m2 | `u8` | §2.1 | none | match | U |
| `0x208B` | **shop purchase** | 400 m1 | `u32 artifact \| Handle` | `0x88c410` ← `0xa17ce0` = **Notice_Upgrade__PurchaseUpgrade** (slot 0x44) | 0x2086, 0x20E2, currency | match | H |
| `0x20A7` | **shop sale** | 400 m1 | `u32 artifact \| u32 slot \| Handle` | `0x88c530` ← `0xa17d90` = **Notice_Upgrade__SellUpgrade** (slot 0x5C) | 0x2086, 0x20E2 | match | H |
| `0x211B` | entity attached | 400 m1 | `u64` | §2.1 | none | match | U |
| `0x212C` | artifact skill-slot order | 400 m1 | `list<u32>` | §2.1 | (0x212B) | match | U |
| `0x2136` | **player ping** | 400 m1 | `f32 x \| f32 y \| u64 target \| u32 type` | `0x887e60` ← `0xa31030` (Alt+click); patched client: RankSkill type "KNAR" | server places the ping marker / ranks the skill | match | H |
| `0x2138` | script node 0x10000060 forwards an objective record | 400 m2 | `u32 node arg \| u32 character DID \| objective record (reader 0x872330: u32 flags + flag-driven fields, as in 0x2034)` | `0x887200` ← `0xab6e30` (vtable slot 10 of node `0x10000060`, when the target object's `+0xB0` mode is 2) | the server's mission logic updates the objective (0x2009) | match | – |
| `0x2139` / `0x213A` | **camera hold / toggle lock** | 400 m2 | `u32 encounter \| u8` | §2.1 | none | match | U |
| `0x2140` | HUD element state | 400 m2 | `u32` | `0x886700` ← `0xa676b0` | unknown | match | – |
| `0x214D` | UI event, empty | 400 m1 | empty | `0x887570` ← `0xa0aab0` | unknown | match | – |
| `0x2170` | coaching tip seen | 400 m2 | `u64 lobby id \| u32 tip` | `0x887c20` ← `0xa1d930`, `0xa5e2d0` | none | match | – |
| `0x20EB` | **join queue** | 401 m1 | `QueueKey \| u8 \| u32` | `0x889f50` ← `0xa31330` **Notice_UI__JoinQueue** (slot 0xA4), `0xa312d0` **JoinQueueForPromotedMap** (0xA8) | 0x20C0, 0x20FA | menus | H |
| `0x20C3` | **leave queue** *(new)* | 401 m1 | empty | `0x88a070` ← `0xa0da40` = **Notice_UI__LeaveQueue** (UI listener slot 0xAC = dispatcher slot) | 0x20E0 removed from queue | menus | – |
| `0x20CA` | **accept match** | 401 m1 | empty | `0x889cf0` ← `0xa0da60` (UI listener slot 0 = AcceptMatch), `0xa7f200` | 0x20AD, 0x2028, referral | menus | H |
| `0x20F2` | **connect to lobby** | 401 m1 | `u64 account \| u32 character DID \| u8 flag \| u8 view-match \| list<u32> user settings` | `0x8c46c0` ← `0xa98850` (game connection up), `0xab8e00` (= handler of S→C 0x206E, view match) | 0x2029, 0x204C, 0x2016, 0x206D | menus | H |
| `0x20D5` | **loading percent** | 401 m1 | `u32` | `0x889bc0` ← `0xa964b0` | 0x2031 | menus | H |
| `0x20BA` | post-match changes request | 401 | empty | §2.1 | (0x2080 / 0x2104 / 0x20B9 / 0x2188) | menus | U |
| `0x20C4` | lobby client slot 0 | 401 | empty | §2.1 | none | menus | U |
| `0x216E` | **user preference saved** | 401 m1 | `str8 name \| wstr value \| u32 type tag` (0x10000C33 bool, 0x10000A0E number, 0x100009ED string) | `0x88ac00` ← `0xa38cc0` | none | menus | H |
| `0x2124` | **request pending rewards** | 401 m1 | empty | `0x888340` ← `0xa0b3e0` **Notice_Character__UI_RequestPendingRewardUpdateFromServer** (slot 0x78) | 0x2125 | menus | – |
| `0x2128` | **claim post-match reward** | 401 m1 | `u32 reward set \| u32 choice \| u32 source \| u64 instance \| list<u32> items \| list<u32> qty \| list<u32> bestowal` | `0x8c4470` ← `0xa411d0` **Notice_Character__UI_ClaimPostMatchReward** (slot 0x68) | none required | menus | – |
| `0x2116` | **request account encounter stats** | 401 m1 | empty | §2.1 | 0x2115 | menus | – |
| `0x2093` | set protector icon | 401 m1 | `u32 \| u32` | `0x88aac0` ← `0xa2fbc0` (Character listener slot 0x7C, after the last dispatched name: UI_SetProtectorIcon) | (0x2154 / 0x2190) | menus | – |
| `0x212E` | **request achievement banners** | 401 m1 | empty | §2.1 | 0x211F | menus | U |
| `0x211D` | **request all achievement data** | 401 m1 | empty | `0x882f60` ← `0xa434f0` (achievement listener slot 0x10 = **RequestAllAchievementData**) | 0x2120 | menus | – |
| `0x211E` | achievement request with u32 | 401 m1 | `u32` | `0x882e30` ← `0xa63070` (achievement listener slot 4) | (0x21A6) | menus | – |
| `0x21A4` | **request leaderboards** | 401 m1 | `u32` | §2.1 | 0x21A2 / 0x21A3 | menus | U |
| `0x2178` | request account standings | 401 m1 | empty | `0x887d30` ← `0xa8dec0`, `0xa939b0` | 0x219E | menus | – |
| `0x2193` | request static standings | 401 m1 | empty | `0x887f80` ← `0xa31090` | 0x219F | menus | – |
| `0x21A5` | **champion data again** | 401 m1 | empty | `0x883910` ← `0xa833d0` = handler of S→C 0x20ED, sent once when its champion list is empty | 0x20ED | menus | – |
| `0x21A8` | dodge-penalty notifications | 401 | empty | `0x889ed0` ← `0xa0db10` (UI listener slot 0x20 = **DisplayPendingDodgePenaltyNotifications**) | none known | menus | – |
| `0x20FC` | save amplifier set | 401 m1 | amplifier set `{u32 \| u64 \| u32 \| StringInfo \| wstr name \| u32 \| (compact n, n × u32)}` | `0x8cc730` ← `0xa2fd40` | 0x20C7 / 0x2052 | menus | – |
| `0x2106` | locale / region request | 401 m1 | `str8` | §2.1 | ? | menus | – |
| `0x2099` | lobby system line | 401 m1 | `u32 string token` | `0x888ef0` ← `0xa0d310`, `0xa1bce0` … | none | menus | – |
| `0x20DF` | lobby/UI, empty | 401 m1 | empty | `0x888ca0` ← `0xa0d270` | ? | menus | – |
| `0x20E4` | lobby/UI | 401 m1 | `u32 \| u8 \| u32` | `0x889150` ← `0xabd890` | ? | menus | – |
| `0x2160` | u32 request | 401 | `u32` | `0x88c9b2` ← `0x882780` | ? | menus | – |
| **Lobby listener** (vtable `0x1604b84`, every slot matches the Lobby dispatcher) | | | | | | | |
| `0x200A` | **ExitLobbyToMainMenu** | 401 m1 | `u64` | `0x885870` ← slot 0xC | (0x2021) | menus | – |
| `0x202D` | **LobbyUIReady** | 401 m1 | `QueueKey` | `0x885980` ← slot 0x10 | lobby state | menus | – |
| `0x206A` | **PlayerSelectedEarlyLaunch** | 401 m1 | `u64 \| u32 \| u8` | `0x885a90` ← slot 0x18 | 0x206C / 0x2061 | menus | – |
| `0x201E` | **RequestAllPregameTips** | 401 m1 | `wstr` | `0x885ba0` ← slot 0x1C | tips | menus | – |
| `0x200D` | **RequestChangeAmplifierSet** | 401 m1 | `u8` | `0x885ca0` ← slot 0x20 | 0x204A | menus | – |
| `0x2025` | **RequestCharacterPickerInformation** | 401 m1 | `u64` | `0x885dd0` ← slot 0x28 | 0x2029 / 0x2060 | menus | – |
| `0x2057` | **RequestMyAmplifierSet** | 401 m1 | empty | `0x885ee0` ← slot 0x2C | 0x2090 / 0x20C7 | menus | – |
| `0x2064` | RequestMyStolenPowers (slot 0x30, no dispatcher name) | 401 m1 | empty | `0x886010` | 0x2004 | menus | – |
| `0x2017` | RequestStolenPowerList (slot 0x34) | 401 m1 | `u64 \| u32` | `0x886140` | stolen power list | menus | – |
| `0x20FD` | **RequestTeamNames** (Query, slot 0x38) | 401 m1 | empty | `0x886250` | team names | menus | – |
| `0x2102` | **SelectCharacter** | 401 m1 | `u32 variant DID \| u8` | `0x8864b0` ← slot 0x40 | lobby slot 0x2029 | menus | H |
| `0x2108` | **TeamDisplayReady** | 401 m1 | `u32` | `0x886380` ← slot 0x44 | none | menus | – |
| `0x214E` | **TriggerWaitAfterReadyFlag** | 401 m1 | `u32 \| StringInfo \| StringInfo` | `0x8865f0` ← slot 0x48 | none | menus | – |
| `0x2026` | rejoin lobby room (slot 4) | 401 m1 | `u64 \| u32` | `0x885630` | 0x205B | menus | – |
| `0x205A` | lobby slot 8 | 401 m1 | empty | `0x885740` | ? | menus | – |
| **Lobby client object** (vtable `0x160adb8`, not a notice listener) | | | | | | | |
| `0x20C4` / `0x20D6` / `0x20F1` / `0x20BF` / `0x208E` / `0x2089` / `0x2098` / `0x207D` / `0x2156` | slots 0, 1, 2, 3, 5, 6, 8, 9, 18 | 401 m1 | empty / `u64` / `u8` / empty / `u32 \| u8 \| u32` / empty / `u32 \| u32` / `u32 \| u32` / empty | `0x889020`, `0x889260`, `0x889370`, `0x889830`, `0x8894a0`, `0x889960`, `0x8895b0`, `0x8896f0`, `0x889a90` | none known (custom match / view match controls *probable*) | menus | U (0x20C4) |
| **CustomMatch listener** (vtable `0x1602f04`, 12 slots match the CustomMatch dispatcher) | | | | | | | |
| `0x20C1` | **Create_CustomMatch** | 401 m1 | `u64 \| wstr` | `0x8846b0` ← slot 0xC | 0x2012 … | social | – |
| `0x2094` | **ForceLaunch** | 401 m1 | `wstr` | `0x8847c0` ← slot 0x10 | 0x2040 | social | – |
| `0x20E6` | **InviteResponse_CustomMatch** | 401 m1 | `wstr` | `0x8848c0` ← slot 0x1C | 0x202E | social | – |
| `0x20FB` | slot 0x20 (IsInCustomMatch is a query; sender takes a u64) | 401 m1 | `u64` | `0x8849c0` | ? | social | – |
| `0x2199` / `0x219A` | **Kick_CustomMatch** (two variants) | 401 m1 | `wstr` | `0x884fe0` / `0x884ac0` ← slot 0x24 | 0x2041 | social | – |
| `0x20A1` | **Launch_CustomMatch** | 401 m1 | `wstr` | `0x884bc0` ← slot 0x28 | 0x2040 | social | – |
| `0x20C6` | **Leave_CustomMatch** | 401 m1 | `u64 \| wstr \| u8` | `0x884cc0` ← slot 0x2C | 0x203F | social | – |
| `0x219B` | **MovePosition_CustomMatch** | 401 m1 | `list<u64>` | `0x8c37b0` ← slot 0x30 | 0x2048 | social | – |
| `0x20F4` | **Randomize** | 401 m1 | `u64 \| u64` | `0x884dd0` ← slot 0x34 | 0x2076 | social | – |
| `0x2066` | **RequestCustomMatchData** | 401 m1 | `u64` | `0x884ee0` ← slot 0x38 | 0x203F | social | – |
| `0x200B` | **SetDraftMode** | 401 m1 | `u32` | `0x8850e0` ← slot 0x3C | 0x2103 | social | – |
| **Chat / text / social** | | | | | | | |
| `0x20A6` | chat channel list (join "Team"/"Wrapper") | 401 m1 | `u32 n \| n × StringInfo` | `0x8d6830` ← `0xa455d0`, `0xa45317` | channel joins (0x2135) | social | – |
| `0x20F6` | send chat text | 401 m1 | `StringInfo channel \| wstr text` | `0x883df0` ← `0xa45aa0` + 3 | echo to channel | social | – |
| `0x20CD` | name-based command (tell / whisper target) | 401 m1 | `wstr \| wstr` | `0x883f00` ← `0xa71b10` | ? | social | – |
| `0x2112` | contact / invite by name | 401 m1 | `wstr \| wstr \| u64 \| QueueKey \| wstr \| u32 \| wstr \| u32` | `0x888210` ← `0xa22ce0` | ? | social | – |
| `0x20E5` | lobby line with key | 401 m1 | `QueueKey \| u32 \| wstr` | `0x888dd0` ← `0xa227c0` + 5 | ? | social | – |
| `0x2148` | name request (≥ 2 chars) | 401 m1 | `wstr` | `0x88c830` ← `0xac05e0` | ? | social | – |
| `0x210E` | encounter tracker request | 401 m1 | `u64 \| u32 \| str8 \| u32 \| str8` | `0x8854d0` ← `0xa46fc0` | ? | social | – |
| `0x2110` / `0x2111` | encounter tracker request (lists) | 401 m1 | `u64 \| (u64 \| u32 \| str8 \| u32 \| str8 \| u32)` | `0x8853c0` ← `0xa470d0`, `0x893760` ← `0xa47200` | ? | social | – |
| **Telemetry** | | | | | | | |
| `0x20D4`, `0x20E3`, `0x20BE`, `0x20B4`, `0x214F` | §2.1 | 401 | §2.1 | §2.1 | none | telemetry | U |
| `0x218C` | **UserActionMetric** (UI dispatcher name, slot 0x128) | 401 m1 | `u32 metric` | `0x88ad30` ← `0xac4e40` | none | telemetry | – |
| **Local only (cannot be written to the server connection, §1.4)** | | | | | | | |
| `0x82`, `0x8C`, `0x8F`, `0x91`, `0x97`, `0x9B`, `0xAD`, `0xC0`, `0xC1`, `0xCA`, `0xD0`, `0xD1`, `0xE4`, `0xE6`, `0xF3`, `0xFA`, `0xFD`, `0x103`, `0x10B`, `0x111`, `0x113`, `0x11A`, `0x11B`, `0x11F`, `0x121`, `0x127`, `0x12B`, `0x12C`, `0x133`, `0x134` | world-object / object-service events | object or service | unpacked layouts = the S→C table (same serializers) | object services `0x55xxxx-0x6Fxxxx` | — | local | – |

### 2.3 Notices the client sends (event 0x2, dest = local player `0x0200000000000001`)

Exactly 8 senders (all calls of the notice constructor `0x481e70`); body `u32 notice id | u32 args length | args`.

| notice | args | sender ← trigger | meaning | server should | ics |
|---|---|---|---|---|---|
| `0x1000015E` | none | `0x884010` ← `0xa96cf0` (+15 %), `0xa96a00`, script natives `0x2800001` / `0x27C0002` | **load complete** | start the match (intro cinematic, HUD) | H |
| `0x10000117` | `u32 cinematic DID` (args length 4) | `0x8919c0` ← `0xa9cd00` finished, `0xa9cd90` skipped, `0xa9ce20`/`0xa9ce70`/`0xa9ceb0` could not start, `0xa9cff0` (0x20F5 refused) | **cinematic done** (no state field: ics reads the length 4 as "state 4") | continue the flow | H |
| `0x10000204` | none | `0x886950` ← `0xa964b0` | **entered the match** (all loaded + load complete; UI event 0x33) | optional start trigger | U |
| `0x10000207` | none | `0x883a40` ← `0xa0a510` | **player ↔ champion link done** | none | U |
| `0x100000D2` | none | `0x88baf0` ← `0xa0cbc0` (match HUD set up, listens for 0x1000000E, 0x10000109, 0x10000424, 0x100002AB-2B1), `0xa13eb0` | match HUD ready *(probable)* | 0x10000109 SetMatchTime, timeline notices | – |
| `0x100002AD` | none | `0x887310` ← Flash `Notice_Encounter__UI_ReadyForTimelineData` | ready for timeline data | 0x100002AF + 0x100002B1, then 0x10000424 banners | – |
| `0x10000137` | none | `0x886b00` ← Flash `Notice_Encounter__RequestCurrentTeamHealth` | team health request | 0x10000134 (or 0x100004FB) | – |
| `0x10000454` | `u8 yes/no` | `0x886de0` ← Flash `Notice_Encounter__SurrenderResponse`, `0xa0cd90` | surrender vote | 0x10000455 / 0x10000456 | – |

Not sent over the network: scriptlet / animation-graph events, per-frame cinematic timeline, emotes (local script
handler `0x28F0001`), skill rank-up on the unpatched client (patched: ping type "KNAR").

---------------------------------------------------------------------------------------------------------------------

## 3. Server → client

### 3.1 Dispatch

`0xb0ec50(event, factory)` × 336; exec = event vtable slot 1 (QueryInterface of the destination, then the owning
system), serializer = slot 7. Destinations: OBJ (generic object: local player `0x0200000000000001`, agents, props),
PSYS (player system `0x0600000000000403`), SESSION, REGION, TypedWorldObject, service. Notices (event 0x2):
`0x483240` × 464, only 44 have a network reader; the other 420 are local C++/Flash notices and are ignored if sent.

### 3.2 Gaps filled in this pass

- `0xA8` → the client answers with `0xDC` (performance report). *(confirmed, call chain)*
- `0x206E` → its handler sends `0x20F2` with the view-match byte (spectator connect). *(confirmed)*
- `0x20ED` with an empty champion list → the client asks once more with `0x21A5`. *(confirmed)*
- `0x212B` ↔ client `0x212C`: the same upgrade-component call (artifact skill-slot order). *(probable)*
- Replies (probable, except 0x211F / 0x2125 which the old server already sends in game): `0x20E0` ← `0x20C3`; `0x2115` ← `0x2116`; `0x21A2`/`0x21A3` ← `0x21A4`; `0x211F` ← `0x212E`;
  `0x2125` ← `0x2124`; `0x2120` ← `0x211D`; `0x219E` ← `0x2178`; `0x219F` ← `0x2193`; `0x8D` ← `0xDA`;
  notices `0x10000134` ← `0x10000137`, `0x10000455/456` ← `0x10000454`, `0x100002AF/2B1/424` ← `0x100002AD`.
- Meanings confirmed by ics in game: `0x2086` shop transaction done, `0x20E2` inventory, `0x2078` recommended
  upgrades, notices `0x10000090` / `0x100000BC` (defeat timers), `0x100004D6` (floaty currency, layout probable).
- Connection packets 0x100000, 0x200000, 0x4000000: layouts known (§1.2), never seen.
- Still structural only ("(?)" kept): the world-object service family (they are object-service events, see §1.4),
  movement 0x1 / 0x8A (handlers `0x6322f0` / `0x632370` go into the model placement code `0x631d00` /
  `0x631fa0`, the same path as 0xB8: position + appearance), 0x2022 / 0x2074 / 0x2000003D (agent component
  `obj+0xBC`), and the unnamed notices of the GM_UI / Upgrade / Encounter groups.

### 3.3 Every server → client event (336)

`cat` = match / match (end) / menus / social / telemetry. `ics`: sent = ics sends it; built, unused = a builder exists
in `ics/messages.py` but nothing calls it; old server only = only `icserver/` sends it.

| id | cat | system / destination | exec / serializer / handler | body layout (u8 0 = base byte) | meaning / client effect | ics |
|---|---|---|---|---|---|---|
| `0x1` | match | engine: movement/appearance / object IID (player 0x02..01 or entity) | exec `0x698090` / ser `0x445a30` / h 0x632560 | u8 0 \| Position \| vec3 \| u32 \| u32 \| u32 \| u32 \| u8 | Movement update (?): position + velocity vec3 + 4 u32 + flag (exec->0x6322f0). Probable server-driven position/heading of an entity | no |
| `0x2` | match | engine static / object IID (player 0x02..01 or entity) | exec `0x482160` / ser `0x481f20` / h 0x482090,0xaf9650 | u8 0 \| u32 notice id \| u32 len \| blob (read by the notice reader, stream flag 0x800) | Notice delivery: u32 notice id / u32 len / blob; the blob is read by the notice's own reader (see notice table). Dest 0x...403 accepted with no target object | sent |
| `0x3` | match | engine: object lifecycle / object IID (player 0x02..01 or entity) | exec `0x698a20` / ser `0xb0d380` / h - | u8 | Remove (destroy) object | sent |
| `0x4` | match | engine static / any (exec uses a service) | exec `0x5d9ff0` / ser `0x447770` / h - | u8 0 \| cint n \| n x (cint event id \| u32 len \| body without its base byte) | Batch: create/update objects (0xF2 descriptor); sub-events compact id / u32 len / body | sent |
| `0x5` | match | engine: object lifecycle / object IID (player 0x02..01 or entity) | exec `0x698d60` / ser `0x445430` / h 0x629910 | u8 0 \| {u8 {u16}} | Object listener callback (obj+0x60 listeners, vt+0x18) with u8 + u16 id (?) | no |
| `0x6` | match | engine: properties / object IID (player 0x02..01 or entity) | exec `0x699450` / ser `0x445530` / h 0x635360 | u8 0 \| PropValue (packed property id, kind, value: wire.pack_value) | Set one property on the object (property collection obj+0x38, vt+0x50) | no |
| `0x7` | match | engine: properties / object IID (player 0x02..01 or entity) | exec `0x699450` / ser `0x445530` / h 0x635360 | u8 0 \| PropValue | Set one property on the object (same handler as 0x6) | no |
| `0x8` | match | engine: movement/appearance / object IID (player 0x02..01 or entity) | exec `0x698140` / ser `0x445b60` / h 0x62c990,0x6325c0 | u8 0 \| {{{u8} GUID} u8 u64 u8 u8 Position u8 {vec3 vec3 u32}} \| u32 \| u32 \| u32 \| u32 \| u8 | Object (re)placement with world-object GUID, position, two vec3 and timing (?) | no |
| `0x41` | match | Effects (agent obj+0x8C) / object IID (player 0x02..01 or entity) | exec `0x8b6780` / ser `0x849a10` / h 0xaa1c50 | u8 0 \| u64 \| {u32} | Effects: raise a script-event list on every effect of agent u64 | no |
| `0x42` | match | Vitals / object IID (player 0x02..01 or entity) | exec `0x8c26f0` / ser `0x846fc0` / h 0xab2880 | u8 0 \| {cint {{u16} {u16}}} \| {cint {{u16} {u16}}} \| {cint {u8 u8 u8 {cint {u8 u16}}}} \| u8 | Vitals (health / secondary resource, DOT/VOT ticks) -> GM_Vitals.RecvNotice_VitalsChanged / DOTUpdate / VOTUpdate, GM_Skill.UI_NotifyVitalChange | sent |
| `0x43` | match | Floaty (obj+0x90) / object IID (player 0x02..01 or entity) | exec `0x8b26b0` / ser `0x83f5b0` / h 0xaa4ee0 | u8 0 \| Handle{u32,u64} | Floaty/combat-text component (obj+0x90): remove entry by handle {u32,u64} | no |
| `0x44` | match | Floaty (obj+0x90) / object IID (player 0x02..01 or entity) | exec `0x8b2610` / ser `0x83f530` / h 0xaaf7c0 | u8 0 \| Handle{u32,u64} \| u32 \| u32 | Floaty/combat-text (obj+0x90): display status floaty (handle, u32, u32) -> GM_Vitals.RecvNotice_DisplayFloatyStatus | no |
| `0x81` | match | engine: properties / region object (iface 79d30b39) | exec `0x698df0` / ser `0x445de0` / h - | u8 0 \| Position \| u8 \| PropTable [trace stopped early] | Region/cell-level properties at a position (iface 79d30b39) (?) | no |
| `0x82` | match | engine static / object IID (player 0x02..01 or entity) | exec `0x56e220` / ser `0x569a60` / h 0x56e040 | u8 0 | Service event, empty body (0x56e040 timer sweep) (?) | no |
| `0x83` | match | engine: misc / object IID (player 0x02..01 or entity) | exec `0x6985e0` / ser `0x839500` / h 0x603e40 | u8 0 \| u32 | Engine service call with u32 (0x603e40 -> service vt+0xd4) (?) | no |
| `0x86` | match | engine: properties / object IID (player 0x02..01 or entity) | exec `0x699210` / ser `0x839500` / h 0x6353b0 | u8 0 \| u32 | Remove one property id from the object (obj+0x38 vt+0x54) | no |
| `0x8a` | match | engine: movement/appearance / object IID (player 0x02..01 or entity) | exec `0x698350` / ser `0x445c90` / h 0x632590 | u8 0 \| Position \| u32 \| u32 \| u32 \| u32 \| u32 \| u8 | Movement update variant: position + 5 u32 + flag (exec->0x632370) (?) | no |
| `0x8b` | match | engine: movement/appearance / object IID (player 0x02..01 or entity) | exec `0x6982b0` / ser `0x839dd0` / h 0x631050 | u8 0 \| u64 | Refresh appearance/model of object u64 (obj+0x58) | no |
| `0x8c` | match | engine static / any (exec uses a service) | exec `0x588f30` / ser `0x589be0` / h - | u8 0 \| u32 | Service event u32 (exec 0x588f30, obj+0x94 component vt+0x28) (?) | no |
| `0x8d` | match | engine: object lifecycle / object IID (player 0x02..01 or entity) | exec `0x698c40` / ser `0x83c030` / h 0x634f20 | u8 0 \| ScriptletList: cint n x entry (DID, instance, flags, originator, variables) - see ics/messages.start_scriptlets | Start scriptlets on an entity. Also the server's answer to client 0xDA (a networked scriptlet the client did not run itself). *(confirmed for 0x8D; 0xDA relation probable)* — earlier note: Start scriptlets on an entity (animations, VFX, sounds) | sent |
| `0x8f` | match | engine static / any (exec uses a service) | exec `0xb15a80` / ser `0xb16420` / h - | u8 0 \| {{u8} GUID} | Session/GUID-keyed engine event (exec 0xb15a80) (?) | no |
| `0x91` | match | engine static / object IID (player 0x02..01 or entity) | exec `0x59d7d0` / ser `0x59e890` / h 0x558060 | u8 0 \| WorldRef{u64,u64,GUID} \| {u32 u32 u32 u32 u32 u32} \| {{{u8} GUID}} | World-object service event: object ref {u64,u64,GUID} + 6 u32 (transform?) + ref (?) | no |
| `0x94` | match | engine: misc / object IID (player 0x02..01 or entity) | exec `0x697e50` / ser `0x839720` / h 0x60c0f0 | u8 0 \| u8 | Engine object flag u8 (obj+8 vt+0x4c) (?) | no |
| `0x96` | match | engine: properties / region object (iface 79d30b39) | exec `0x699090` / ser `0x4454e0` / h - | u8 0 \| Position \| PropValue [trace stopped early] | Region/cell property at position (iface 79d30b39) (?) | no |
| `0x98` | match | engine static / object IID (player 0x02..01 or entity) | exec `0x5643f0` / ser `0x565a50` / h 0x562f80 | u8 0 \| {u8,u64} \| GUID \| u32 \| u8 | World-object service event: {u8,u64} + GUID + u32 + u8 (?) | no |
| `0x9b` | match | engine static / object IID (player 0x02..01 or entity) | exec `0x57bd30` / ser `0x57bb50` / h 0x588a80 | u8 0 \| u32 \| u32 \| u8 | World-object service event: u32 u32 u8 (exec 0x57bd30) (?) | no |
| `0x9c` | match | engine: properties / session object (iface 37feb363) | exec `0x699020` / ser `0x445530` / h 0x6a8380 | u8 0 \| PropValue | Session-level property (iface 37feb363) (?) | no |
| `0x9d` | match | engine static / object IID (player 0x02..01 or entity) | exec `0x59da30` / ser `0x596ad0` / h 0x558060 | u8 | World-object service event, u8 (?) | no |
| `0x9e` | match | engine static / any (exec uses a service) | exec `0x59c030` / ser `0x59df70` / h 0x59bc80 | u8 0 \| WorldRef{u64,u64,GUID} \| Position \| u32 \| u8 | World-object (service 0x15bab54): object ref + position + u32 + u8 (0x59bc80) (?) | no |
| `0x9f` | match | engine static / object IID (player 0x02..01 or entity) | exec `0x568100` / ser `0x563f90` / h 0x567ed0 | u8 0 \| u32 \| {{{u32 u8}}} | World-object service event u32 (?) | no |
| `0xa3` | match | engine static / any (exec uses a service) | exec `0x589090` / ser `0x58f470` / h 0x4994d0 | u8 0 \| {u8,u64} \| GUID \| u64 \| u32 | World-object service event: {u8,u64} + GUID + u64 + u32 (?) | no |
| `0xa5` | match | engine static / any (exec uses a service) | exec `0x588fb0` / ser `0x58d5d0` / h 0x56f600 | u8 0 \| GUID \| {{GUID}} | World-object service event: GUID + list of GUIDs (?) | no |
| `0xa7` | match | engine static / object IID (player 0x02..01 or entity) | exec `0x59d930` / ser `0x59d8d0` / h 0x558060 | u8 0 \| WorldRef{u64,u64,GUID} \| {GUID} | World-object service event: object ref + GUID (?) | no |
| `0xa8` | telemetry | engine: client / object IID (player 0x02..01 or entity) | exec `0x698700` / ser `0x443e50` / h 0x633170 | u8 0 \| u64 | **Request a client performance report**: its handler `0x633170` is the trigger of the 0xDC sender, so the client answers with event 0xDC (frame-time buckets). *(confirmed, static: call chain)* — earlier note: Client performance/report request (?) (0x633170 resets frame counters, uses 120.0) - u64 | no |
| `0xab` | match | engine: messages / session object (iface 37feb363) | exec `0x697dd0` / ser `0x4452e0` / h 0x5a8680,0x6a81f0 | u8 0 \| StringInfo | System text message (StringInfo) shown by the client (session service 0x15d2b10) (?) | no |
| `0xac` | match | engine static / object IID (player 0x02..01 or entity) | exec `0x538780` / ser `0x538970` / h - | u8 0 \| QueueKey{u32 did,u32 flags} | Engine handshake-style event {u32,u32} (exec 0x538780) (?) | no |
| `0xad` | match | engine static / object IID (player 0x02..01 or entity) | exec `0x538780` / ser `0x538970` / h - | u8 0 \| QueueKey{u32 did,u32 flags} | Engine handshake-style event {u32,u32} (?) | no |
| `0xb0` | match | engine: object lifecycle / object IID (player 0x02..01 or entity) | exec `0x698cd0` / ser `0x445430` / h 0x6298d0 | u8 0 \| {u8 {u16}} | Object listener callback (obj+0x60, vt+0x8) u8 + u16 (?) | no |
| `0xb1` | match | engine static / object IID (player 0x02..01 or entity) | exec `0x59d580` / ser `0x59d530` / h 0x558060 | u8 0 \| WorldRef{u64,u64,GUID} | World-object service event: object ref (?) | no |
| `0xb2` | match | engine static / typed world object (iface 6d8bb31c) | exec `0x5a19d0` / ser `0x59e050` / h 0x5c7c60,0x5697c0 | u8 0 \| WorldRef{u64,u64,GUID} \| Position \| {{{u8} GUID}} \| u32 | TypedWorldObject: object ref + position + ref + u32 (sets +0x154 of a typed world object) (?) | no |
| `0xb7` | match | engine: misc / object IID (player 0x02..01 or entity) | exec `0x698670` / ser `0x444bf0` / h 0x634f00 | u8 0 \| {{u32 u8}} | Engine object component (obj+4) list {u32,u8} (?) | no |
| `0xb8` | match | engine: movement/appearance / object IID (player 0x02..01 or entity) | exec `0x698210` / ser `0x4488e0` / h 0x6322d0 | u8 0 \| u64 \| {Position u64 u32 u32 u32 u32 {u32 {u64 {u32 {Position vec3 u32}}}} u32 vec3 u8 u8} | Appearance/model setup for object u64 with position and parts (0x631fa0, CModelComponent) | no |
| `0xba` | match | engine: messages / object IID (player 0x02..01 or entity) | exec `0x697c20` / ser `0xb0d380` / h 0x635670 | u8 | Engine service flag u8 (service 0x15cb5b0) (?) | no |
| `0xbc` | match | engine: properties / object IID (player 0x02..01 or entity) | exec `0x699330` / ser `0x445450` / h 0x635440 | u8 0 \| PropTable [trace stopped early] | Set several properties (property table) on the object (obj+0x38 vt+0xa4) | no |
| `0xc0` | match | engine static / object IID (player 0x02..01 or entity) | exec `0x564210` / ser `0x5658d0` / h 0x4a8550 | u8 0 \| {u8,u64} \| GUID \| {{{u32 u8}}} | World-object service event {u8,u64} + GUID (?) | no |
| `0xc1` | match | engine static / object IID (player 0x02..01 or entity) | exec `0x567710` / ser `0x589be0` / h 0x566e40 | u8 0 \| u32 | World-object service event u32 (?) | no |
| `0xc2` | match | engine: misc / iface SESS2 | exec `0x699550` / ser `0x444d00` / h 0x420920 | u8 0 \| GUID \| u32 | Store a session GUID + u32 (iface d4bce8af) (?) | no |
| `0xc4` | match | engine: properties / region object (iface 79d30b39) | exec `0x698f40` / ser `0x445480` / h - | u8 0 \| Position \| u32 | Region/cell event: position + u32 (iface 79d30b39) (?) | no |
| `0xc8` | match | engine static / any (exec uses a service) | exec `0x5958c0` / ser `0x839830` / h 0x5951f0 | u8 0 \| GUID | World-object service event: GUID (?) | no |
| `0xc9` | match | engine: messages / session object (iface 37feb363) | exec `0x697d50` / ser `0x4452e0` / h 0x5a8680,0x6a81c0 | u8 0 \| StringInfo | System text message variant (StringInfo) (?) | no |
| `0xca` | match | engine static / object IID (player 0x02..01 or entity) | exec `0x674f70` / ser `0x6786c0` / h 0x57b570,0x667320 | u8 0 \| QueueKey{u32 did,u32 flags} \| u32 | Engine event {u32,u32} + u32 (?) | no |
| `0xce` | match | engine: login/account / session object (iface 37feb363) | exec `0x698920` / ser `0x445310` / h 0x6a8520 | u8 0 \| {u32 {u64 u64 wstr u32 PropTable}} [trace stopped early] | Account character set (login) | sent |
| `0xcf` | match | engine: login/account / session object (iface 37feb363) | exec `0x6988b0` / ser `0x839500` / h 0x6a8330 | u8 0 \| u32 | Login/character result code u32 (0x6a8330) (?) | no |
| `0xd0` | match | engine static / object IID (player 0x02..01 or entity) | exec `0x577040` / ser `0x5763a0` / h - | u8 0 \| u8 \| WorldRef{u64,u64,GUID} \| u32 | World-object service: u8 + object ref + u32 (?) | no |
| `0xd1` | match | engine static / typed world object (iface 6d8bb31c) | exec `0x5a0d10` / ser `0x5a13e0` / h 0x599a70,0xaf4780 | u8 0 \| {WorldRef{u64,u64,GUID} {{{{u8} GUID}} {{u8}} {{u8}} {u32 u32 u32 u32 u32 u32} Position u8 u32 u8 u8 u8 u8 u32 u64} {u32 u32 u32 u32 u32 u32} {u32 u32 u32 u32 u32 u32} Position Position u32} | TypedWorldObject create/update: object ref, template refs, 3 transforms, positions, flags (big) (?) | no |
| `0xd2` | match | engine static / object IID (player 0x02..01 or entity) | exec `0x564080` / ser `0x5641c0` / h 0x54cc90,0x402d60 | {u8 0 u32 {{{u32 u8}}}} \| u64 | World-object event with u32 + u64 (header inside struct) (?) | no |
| `0xd7` | match | engine: properties / region object (iface 79d30b39) | exec `0x698fb0` / ser `0x839500` / h - | u8 0 \| u32 | Region/cell event u32 (iface 79d30b39) (?) | no |
| `0xd8` | match | engine: object lifecycle / object IID (player 0x02..01 or entity) | exec `0x698bb0` / ser `0x447e60` / h 0x634f40 | u8 0 \| {u32 Position} | Object call obj vt+100 with u32 (?) | no |
| `0xd9` | match | engine: object lifecycle / object IID (player 0x02..01 or entity) | exec `0x698b10` / ser `0x446f30` / h 0x402c60,0x6354c0 | u8 0 \| {cint,u8} | Object call with {cint,u8} key (?) | no |
| `0xe0` | match | engine static / object IID (player 0x02..01 or entity) | exec `0x538780` / ser `0x538970` / h - | u8 0 \| QueueKey{u32 did,u32 flags} | Engine handshake-style event {u32,u32} (?) | no |
| `0xe2` | match | engine: properties / session object (iface 37feb363) | exec `0x698ed0` / ser `0x839500` / h 0x6a8410 | u8 0 \| u32 | Session-level u32 (iface 37feb363) (?) | no |
| `0xe4` | match | engine static / any (exec uses a service) | exec `0x599100` / ser `0x59e4e0` / h 0x56e6a0 | u8 0 \| u8 \| WorldRef{u64,u64,GUID} \| {u32} \| u32 \| u32 \| {{u8} GUID} | Visibility/awareness of an object (?) (0x56e6a0: u8 on/off, ref, timers +10 s/+20 s) | no |
| `0xe6` | match | engine static / object IID (player 0x02..01 or entity) | exec `0x5b7be0` / ser `0x5b9fa0` / h 0x4a6010 | u8 0 \| {u8,u64} \| GUID \| u32 \| {{u8} GUID} | World-object service: {u8,u64} GUID u32 GUID (?) | no |
| `0xe9` | match | engine static / any (exec uses a service) | exec `0x588f70` / ser `0x58aa00` / h 0x58fbd0 | u8 0 \| PropTable [trace stopped early] | Property table (service) (?) | no |
| `0xea` | match | engine static / object IID (player 0x02..01 or entity) | exec `0x697ac0` / ser `0x68f240` / h 0x62a580 | u8 0 \| u32 \| u32 | Engine event u32 u32 (?) | no |
| `0xeb` | match | engine: object lifecycle / session object (iface 37feb363) | exec `0x698a90` / ser `0x4453c0` / h 0x6a8170 | u8 0 \| u64 \| PropTable [trace stopped early] | Set local player | sent |
| `0xee` | match | engine static / typed world object (iface 6d8bb31c) | exec `0x59c060` / ser `0x59edf0` / h 0x5c7c60,0x5697c0 | u8 0 \| WorldRef{u64,u64,GUID} \| Position \| Position \| {u32 u32 u32 u32 u32 u32} \| u32 \| {{u8} GUID} | TypedWorldObject: ref + 2 positions + 6 u32 + u32 + GUID (?) | no |
| `0xf2` | match | engine static / any (exec uses a service) | exec `0x5d9ff0` / ser `0x445970` / h - | u8 0 \| {{u32} u64} \| u32 | Engine event (no-op handler in this build) | no |
| `0xf5` | match | engine: movement/appearance / object IID (player 0x02..01 or entity) | exec `0x698400` / ser `0x83faa0` / h 0x62cc20 | u8 0 \| u64 \| u32 \| u32 | Appearance part attribute: object u64, part u32, value u32 (obj+0x58 part +0x194) | no |
| `0xf8` | match | engine: properties / object IID (player 0x02..01 or entity) | exec `0x699170` / ser `0x446f30` / h 0x402c60,0x6352d0 | u8 0 \| {cint,u8} | Object string/key event {cint,u8} (?) | no |
| `0xfa` | match | engine static / object IID (player 0x02..01 or entity) | exec `0x446460` / ser `0x444b10` / h - | u32 | Raw u32 event (no-op handler) | no |
| `0xfc` | match | engine static / any (exec uses a service) | exec `0x589020` / ser `0x5896c0` / h 0x572b80 | u8 0 \| GUID | World-object service: GUID (?) | no |
| `0xfd` | match | engine static / object IID (player 0x02..01 or entity) | exec `0x5683b0` / ser `0x5659e0` / h 0x46d1a0,0x476d00 | u8 0 \| {u8,u64} \| GUID | World-object service: {u8,u64} GUID (?) | no |
| `0xff` | match | engine static / iface SVC-fdd7 | exec `0x594fc0` / ser `0x595870` / h - | u8 0 \| {{{u8} GUID}} \| GUID | Service event: GUID list + GUID (iface fdd74f27) (?) | no |
| `0x101` | match | engine: messages / session object (iface 37feb363) | exec `0x697ba0` / ser `0x445270` / h 0x5a8680,0x6a8190 | u8 0 \| u64 \| StringInfo | System text from an IID: u64 + StringInfo (?) | no |
| `0x103` | match | engine static / object IID (player 0x02..01 or entity) | exec `0x58dd70` / ser `0x589b80` / h 0x58b4c0 | u8 0 \| {u8,u8} | Property-kind event {u8,u8} (?) | no |
| `0x104` | match | engine: properties / region object (iface 79d30b39) | exec `0x699100` / ser `0x445530` / h - | u8 0 \| PropValue | Region/cell property (iface 79d30b39) (?) | no |
| `0x105` | match | engine: login/account / session object (iface 37feb363) | exec `0x698840` / ser `0x83c2e0` / h 0x6a8130 | u8 0 \| u32 \| StringInfo | Login/character error code + StringInfo text (0x6a8130) (?) | no |
| `0x106` | match | engine: movement/appearance / object IID (player 0x02..01 or entity) | exec `0x698540` / ser `0x444b70` / h 0x62ef80 | u8 0 \| u64 \| u32 | Appearance: object u64, part u32 -> remove/reset part (0x62ebf0) (?) | no |
| `0x10b` | match | engine static / any (exec uses a service) | exec `0x588ef0` / ser `0x58a9a0` / h - | u8 0 \| PropValue | Property value (service) (?) | no |
| `0x10d` | match | engine: movement/appearance / object IID (player 0x02..01 or entity) | exec `0x697ee0` / ser `0x4486b0` / h 0x630160 | u8 0 \| {u64 {u32 {Position}}} [trace stopped early] | Appearance: add parts list to object (obj+0x58 -> 0x62fb20) | no |
| `0x10f` | match | engine static / object IID (player 0x02..01 or entity) | exec `0x538780` / ser `0x51bb20` / h - | {u8 0 QueueKey{u32 did,u32 flags}} \| u8 | Engine handshake-style event {u32,u32} + u8 (?) | no |
| `0x110` | match | engine: properties / region object (iface 79d30b39) | exec `0x698e60` / ser `0x445450` / h - | u8 0 \| PropTable [trace stopped early] | Region/cell property table (iface 79d30b39) (?) | no |
| `0x111` | match | engine static / any (exec uses a service) | exec `0x5709d0` / ser `0x570a90` / h 0x588290 | u8 0 \| {cint Position u64 {{u8} GUID}} \| u32 | World-object service: cint + position + u64 + ref + u32 (?) | no |
| `0x112` | match | engine static / object IID (player 0x02..01 or entity) | exec `0x5681c0` / ser `0x565860` / h 0x568040,0x54cc90 | {u8 0 u32 {{{u32 u8}}}} \| {u8,u64} \| GUID | World-object event (header in struct) + {u8,u64} GUID (?) | no |
| `0x113` | match | engine static / object IID (player 0x02..01 or entity) | exec `0x5b7db0` / ser `0x5ba050` / h 0x4a6100 | u8 0 \| {u8,u64} \| GUID \| u32 \| {{u8} GUID} | World-object service: {u8,u64} GUID u32 GUID (?) | no |
| `0x115` | match | engine: movement/appearance / object IID (player 0x02..01 or entity) | exec `0x698000` / ser `0xb0d380` / h 0x62cc60 | u8 | Appearance LOD/refresh flags u8 for all parts (0x62cc60) | no |
| `0x116` | match | engine: messages / object IID (player 0x02..01 or entity) | exec `0x697cb0` / ser `0x4483a0` / h 0x635520 | u8 0 \| Position \| {u32 {{u32 u32 u32 u32}} {u32}} \| u32 \| u32 | Map visualization chunk (debug): position, list, part n of m | no |
| `0x117` | match | engine: object lifecycle / object IID (player 0x02..01 or entity) | exec `0x698990` / ser `0xb0d380` / h 0x634f70 | u8 | Engine object event u8 (?) | no |
| `0x11a` | match | engine static / object IID (player 0x02..01 or entity) | exec `0x5642c0` / ser `0x5659e0` / h 0x4a8550 | u8 0 \| {u8,u64} \| GUID | World-object service: {u8,u64} GUID (?) | no |
| `0x11b` | match | engine static / any (exec uses a service) | exec `0x560ce0` / ser `0x5659e0` / h 0x484f60 | u8 0 \| {u8,u64} \| GUID | World-object service: {u8,u64} GUID (?) | no |
| `0x11f` | match | engine static / object IID (player 0x02..01 or entity) | exec `0x675280` / ser `0x6751a0` / h 0x57c4b0 | u8 0 \| u32 \| u32 \| u8 | World-object event u32 u32 u8 (?) | no |
| `0x123` | match | engine: client / object IID (player 0x02..01 or entity) | exec `0x6987a0` / ser `0x444cb0` / h 0x633270 | u8 0 \| u32 | Set a client scale factor 0.08-1.0 (0x633270) (?) | no |
| `0x124` | match | engine: movement/appearance / object IID (player 0x02..01 or entity) | exec `0x6984a0` / ser `0x83faa0` / h 0x62cbe0 | u8 0 \| u64 \| u32 \| u32 | Appearance: object u64, part u32, state u32 (0x62ba80) | no |
| `0x127` | match | engine static / object IID (player 0x02..01 or entity) | exec `0x6750f0` / ser `0x675030` / h 0x588ac0 | u8 0 \| u32 \| u32 \| u32 | World-object event u32 u32 u32 (?) | no |
| `0x129` | match | engine: properties / object IID (player 0x02..01 or entity) | exec `0x699210` / ser `0x839500` / h 0x6353b0 | u8 0 \| u32 | Remove one property id (same as 0x86) | no |
| `0x12c` | match | engine static / object IID (player 0x02..01 or entity) | exec `0x59d6d0` / ser `0x59d670` / h 0x558060 | u8 0 \| WorldRef{u64,u64,GUID} \| Position | World-object service: object ref + position (?) | no |
| `0x133` | match | engine static / object IID (player 0x02..01 or entity) | exec `0x674ec0` / ser `0x6786c0` / h 0x671740 | u8 0 \| QueueKey{u32 did,u32 flags} \| u32 | Engine event {u32,u32} + u32 (?) | no |
| `0x134` | match | engine static / object IID (player 0x02..01 or entity) | exec `0x58dcd0` / ser `0x58a9a0` / h 0x58b770 | u8 0 \| PropValue | Property value (service) (?) | no |
| `0x138` | match | engine: movement/appearance / object IID (player 0x02..01 or entity) | exec `0x697f70` / ser `0x4488b0` / h 0x631550 | u8 0 \| {u32 {u64 {u32 {Position}}}} [trace stopped early] | Batch appearance refresh for a list of objects (+ scriptlet 0x14 on type-9 objects) | no |
| `0x13b` | match | engine: properties / object IID (player 0x02..01 or entity) | exec `0x699450` / ser `0x445530` / h 0x635360 | u8 0 \| PropValue | Set one property (same as 0x6) | no |
| `0x13c` | match | engine: properties / object IID (player 0x02..01 or entity) | exec `0x6992a0` / ser `0x839500` / h 0x6353a0 | u8 0 \| u32 | Remove one property id (same as 0x86) | no |
| `0x13d` | match | engine: properties / object IID (player 0x02..01 or entity) | exec `0x6993c0` / ser `0x445450` / h 0x635480 | u8 0 \| PropTable [trace stopped early] | Set property table on object (obj+0x38 vt+0xa8) | no |
| `0x2001` | match | Dialog / object IID (player 0x02..01 or entity) | exec `0x8b2180` / ser `0x8453a0` / h 0xa13b90 | u8 0 \| u64 \| u32 \| u32 conversation key \| list<u64> speakers \| u8 \| u32 instance | Dialog: start conversation (root+0x1c dialog system, vt+8) | sent |
| `0x2003` | social | Contacts / player system 0x0600000000000403 | exec `0x8ac770` / ser `0x842450` / h 0xa35810 | u8 0 \| u64 \| u64 \| wstr | Contacts: invite received [Contacts.RecvNotice_UI_NotifyContactOfInvite] | no |
| `0x2004` | menus | Lobby / player system 0x0600000000000403 | exec `0x8b8d30` / ser `0x83fca0` / h 0xab87d0 | u8 0 \| u32 \| u32 \| u32 \| u64 | Lobby: player picked Stolen Powers [Lobby.RecvNotice_PlayerPickedStolenPowers] | no |
| `0x2005` | menus | Lobby / player system 0x0600000000000403 | exec `0x8b8a10` / ser `0x68f240` / h 0xab8690 | u8 0 \| u32 \| u32 | Lobby: character lock failed [Lobby.RecvNotice_CharacterLockFail] | no |
| `0x2006` | match | MapManager notes / object IID (player 0x02..01 or entity) | exec `0x8b70e0` / ser `0x83fb40` / h 0xa56c90 | u8 0 \| u32 \| Handle{u32,u64} \| u32 \| u32 \| {u32} \| u32 | MapManager: add map note (minimap marker/ping): type, handle {u32,u64}, ... | no |
| `0x2008` | match | Effects (agent obj+0x8C) / object IID (player 0x02..01 or entity) | exec `0x8b68c0` / ser `0x83faa0` / h 0xaa1bf0 | u8 0 \| u64 \| u32 \| u32 | Effects: raise script event (DID) on the agent's effects matching key | no |
| `0x2009` | match | Encounter / object IID (player 0x02..01 or entity) | exec `0x8b56b0` / ser `0x83bf50` / h 0xa84330 | u8 0 \| u32 objective id \| objective (u32 flags, then fields by flag: 0x8000 state, 0x1 category, 0x80 text, 0x10 count, 0x4 max, 0x4000 sort, 0x80000 active, 0x100 optional, 0x1000000 banner) | Encounter: objective update (flag-driven fields) [Encounter.RecvNotice_UI_UpdateObjective_Count, Encounter.RecvNotice_UI_UpdateObjective_CountMax, Encounter.RecvNotice_UI_UpdateObjective_State] | sent |
| `0x200c` | match | Effects (agent obj+0x8C) / object IID (player 0x02..01 or entity) | exec `0x8b6c70` / ser `0x846f30` / h 0xaa1cd0 | u8 0 \| {u32 {{{cint {u32}} {cint {u32}} {u32 u32}} GUID u8 {u32}}} \| u8 | Effects: apply a list of effect instances to the agent (+ u8) | no |
| `0x200e` | match | MapManager notes / object IID (player 0x02..01 or entity) | exec `0x8b71a0` / ser `0x83f5b0` / h 0xa21a00 | u8 0 \| Handle{u32,u64} | MapManager: remove map note by handle | no |
| `0x200f` | match | Effects (agent obj+0x8C) / object IID (player 0x02..01 or entity) | exec `0x8b6bd0` / ser `0x843d60` / h 0xa9fb00 | u8 0 \| {{{{cint {u32}} {cint {u32}} {u32 u32}} GUID u8 {u32}}} \| u8 | Effects: add one effect instance (u8 = fresh) | no |
| `0x2011` | social | CustomMatch / player system 0x0600000000000403 | exec `0x8af920` / ser `0xb0d380` / h 0xa775b0 | u8 | CustomMatch: cancelled [CustomMatch.RecvNotice_UI_CustomMatch_Cancelled] | no |
| `0x2012` | social | CustomMatch / player system 0x0600000000000403 | exec `0x8af820` / ser `0x83bdf0` / h 0xa1b290 | u8 0 \| {wstr u64 u64 u32 u32 u32 u8} u32 | CustomMatch: participant added [CustomMatch.RecvNotice_UI_CustomMatch_AddedParticipant] | no |
| `0x2013` | social | Contacts / player system 0x0600000000000403 | exec `0x8ac970` / ser `0x847950` / h 0xa57da0 | u8 0 \| {u32 {u64 wstr u64}} | Contacts: pending invites [Contacts.RecvNotice_UI_NotifyContactOfPendingInvites] | no |
| `0x2014` | social | Contacts / player system 0x0600000000000403 | exec `0x8ac470` / ser `0x8423e0` / h 0xa58650 | u8 0 \| u64 \| wstr | Contacts: group created [Contacts.RecvNotice_UI_NotifyContactGroupCreated] | no |
| `0x2015` | menus | Lobby / player system 0x0600000000000403 | exec `0x8b8c20` / ser `0x83f690` / h 0x132c5c0 | u8 0 \| u32 \| u8 | Player system: u32 u8 (no-op handler in this build) | no |
| `0x2016` | menus | Lobby / player system 0x0600000000000403 | exec `0x8b8a90` / ser `0x839500` / h 0xab9080 | u8 0 \| u32 | Lobby: end room check (arms 60 s watchdog) [Lobby.RecvNotice_HideBackButton] | sent |
| `0x2018` | social | Contacts / player system 0x0600000000000403 | exec `0x8ac6f0` / ser `0x846d10` / h 0xa58970 | u8 0 \| {u32 {u64 u64 wstr u64 wstr wstr u32 u8 u32 u32 u32 u32 u32 u32 u32 wstr u32}} | Contacts: presence changed [Contacts.RecvNotice_UI_NotifyContactPresenceChanged] | no |
| `0x2019` | match | Effects (agent obj+0x8C) / object IID (player 0x02..01 or entity) | exec `0x8b6d10` / ser `0x83c1a0` / h 0xaaa830 | u8 0 \| GUID \| {u32 u32 u32} \| {u32 {u32}} | Effects: update an effect instance's script variable (GUID, var, value) | no |
| `0x201c` | match | Encounter / object IID (player 0x02..01 or entity) | exec `0x8b57f0` / ser `0x848af0` / h 0xa80440 | u8 0 \| {u32 {u32 {u8 u32 u32 PropTable}}} [trace stopped early] | Encounter: add entries to the encounter UI list (root+0x68) + u8 (?) | no |
| `0x201d` | match | Floaty (obj+0x90) / object IID (player 0x02..01 or entity) | exec `0x8b2580` / ser `0x8454d0` / h 0xaa7200 | u8 0 \| {u32 {u32 Handle{u32,u64}}} | Floaty/combat-text: replace floaty list (obj+0x90) | no |
| `0x201f` | social | CustomMatch / player system 0x0600000000000403 | exec `0x8afc90` / ser `0x83c280` / h 0xa0c570 | u8 0 \| StringInfo \| u32 | CustomMatch: invited [CustomMatch.RecvNotice_UI_CustomMatch_Invited] | no |
| `0x2020` | social | Contacts / player system 0x0600000000000403 | exec `0x8ac7f0` / ser `0x839dd0` / h 0xa306d0 | u8 0 \| u64 | Contacts: contact removed [Contacts.RecvNotice_UI_NotifyContactRemoved] | no |
| `0x2021` | menus | Lobby / player system 0x0600000000000403 | exec `0x8b8dc0` / ser `0x839500` / h 0xabd730 | u8 0 \| u32 | Lobby: exit lobby / leave world (RecvEvt_DeliverNotifyPlayerToExitLobby) [UI.RecvNotice_GameFrontUIDestroyedInCPP, UI.RecvNotice_ExitingWorld, Lobby.RecvNotice_ClearLightResourcePackReferences] | built, unused |
| `0x2022` | match | Player-object gameplay / object IID (player 0x02..01 or entity) | exec `0x8b5950` / ser `0x83c010` / h 0xaa0500 | u8 0 \| {u32 u32 u32 u32 u32 vec3 u8 u64 u32 u8 u32 u32 u32 u32 u32} | Agent component obj+0xbc vt+0x4c: big struct (5 u32, vec3, u8, u64, u32, u8, 5 u32) - probable movement/knock/teleport command (?) | no |
| `0x2023` | match | Encounter / object IID (player 0x02..01 or entity) | exec `0x8b5750` / ser `0x83bfb0` / h 0xa14040 | u8 0 \| u32 \| {u32 u32} | Encounter: objective category update / remove [Encounter.RecvNotice_UI_RemoveObjectiveCategory, Encounter.RecvNotice_UI_UpdateObjectiveCategory_State] | no |
| `0x2024` | menus | Encounter / player system 0x0600000000000403 | exec `0x8b2970` / ser `0x846d40` / h 0xa733b0 | u8 0 \| list<u32> \| list<u32> \| {u32 {cint,u8}} \| list<u32> \| u32 \| {u32 {cint,u8}} \| u8 \| wstr \| wstr \| u64 | Encounter info (master encounter list) [Encounter.RecvNotice_MasterEncounterListReceived, Encounter.RecvNotice_ResetMapSelectionList, ConnectionManager.RecvNotice_UpdateConnectionState] | sent |
| `0x2027` | social | CustomMatch / player system 0x0600000000000403 | exec `0x8afc10` / ser `0x839500` / h 0xa0c710 | u8 0 \| u32 | CustomMatch: invite cancelled [CustomMatch.RecvNotice_UI_CustomMatch_InviteCancelled] | no |
| `0x2028` | menus | Lobby / player system 0x0600000000000403 | exec `0x8b9240` / ser `0x846620` / h 0xabc3c0 | u8 0 \| QueueKey{u32 did,u32 flags} \| {u32 StringInfo} \| {u32 StringInfo} | Lobby: room created [Lobby.RecvNotice_LobbyRoomCreated, Encounter.RecvNotice_UI_SetEndOfMatchStatsHeader, Lobby.RecvNotice_ClearLightResourcePackReferences] | sent |
| `0x2029` | menus | Lobby / player system 0x0600000000000403 | exec `0x8b9150` / ser `0x8479b0` / h 0xabd0a0 | u8 0 \| {u8 u32 u32 u32 list<u32> list<u64> u32 u32 u64} \| u32 \| u32 \| u64 \| StringInfo \| u8 \| u32 \| u32 \| u8 \| u32 \| u32 \| u32 \| u32 \| u32 \| u32 \| u32 \| u32 \| u32 \| {u32 u64 u32 StringInfo wstr u32 {cint u32}} | Lobby: player slot [Lobby.RecvNotice_PlayerPickedStolenPowers, Lobby.RecvNotice_UpdateLobbyStateSingle, Lobby.RecvNotice_PlayerPickedAmplifierSet] | sent |
| `0x202a` | match | Dialog / object IID (player 0x02..01 or entity) | exec `0x8b2230` / ser `0x839500` / h 0xa1b400 | u8 0 \| u32 | Dialog: set voice/speaker DID (root+0x1c +0xd0) | no |
| `0x202b` | match | Effects (agent obj+0x8C) / object IID (player 0x02..01 or entity) | exec `0x8b6b40` / ser `0x839830` / h 0xaa4220 | u8 0 \| GUID | Effects: remove effect instance (GUID) | no |
| `0x202c` | match | Effects (agent obj+0x8C) / object IID (player 0x02..01 or entity) | exec `0x8b6aa0` / ser `0x849b80` / h 0xa9fbb0 | u8 0 \| GUID \| {u32} | Effects: raise script events on one effect instance (GUID, list) | no |
| `0x202e` | social | CustomMatch / player system 0x0600000000000403 | exec `0x8afb90` / ser `0x8427a0` / h 0xa1b210 | u8 0 \| u64 \| wstr \| u32 | CustomMatch: invitation status [CustomMatch.RecvNotice_UI_CustomMatch_InvitationStatus] | no |
| `0x202f` | social | Contacts / player system 0x0600000000000403 | exec `0x8ac570` / ser `0x8478d0` / h 0xa46ad0 | u8 0 \| {u32 {u64 wstr}} | Contacts: list (0xa3d140) (?) | no |
| `0x2031` | menus | Lobby / player system 0x0600000000000403 | exec `0x8b8fd0` / ser `0x8459e0` / h 0xab8730 | u8 0 \| list<u32> \| list<u32> \| list<u32> \| u32 | Lobby: loading percent [Lobby.RecvNotice_UpdateLobbyLoadingPercent] | sent |
| `0x2033` | social | Grouping / player system 0x0600000000000403 | exec `0x8b6220` / ser `0x4452e0` / h 0xa0d1e0 | u8 0 \| StringInfo | Grouping: show group invite dialog [Grouping.RecvNotice_ShowGroupInviteDialog] | no |
| `0x2034` | match | Encounter / object IID (player 0x02..01 or entity) | exec `0x8b28e0` / ser `0x83bf30` / h 0xa803e0 | u8 0 \| u32 n x objective (flags-driven, 0x872330) \| u32 n x category (0x863570) | Encounter: objective list + categories [Encounter.RecvNotice_UI_SetObjectiveTrackerEnabled, Encounter.RecvNotice_UI_DeliverObjectiveCategories] | sent |
| `0x2035` | social | CustomMatch / player system 0x0600000000000403 | exec `0x8afe80` / ser `0x839550` / h 0xa0c640 | u8 0 \| u64 \| u32 \| u8 | CustomMatch: permission changed [CustomMatch.RecvNotice_UI_CustomMatch_PermissionChanged] | no |
| `0x2036` | social | CustomMatch / player system 0x0600000000000403 | exec `0x8af990` / ser `0x839e20` / h 0xa0c6a0 | u8 0 \| u64 \| u64 | CustomMatch: coordinator changed [CustomMatch.RecvNotice_UI_CustomMatch_ChangedCoordinator] | no |
| `0x2037` | match | Effects (agent obj+0x8C) / object IID (player 0x02..01 or entity) | exec `0x8b6b40` / ser `0x839830` / h 0xaa4220 | u8 0 \| GUID | Effects: remove effect instance (GUID) (same as 0x202B) | no |
| `0x2038` | match (end) | Encounter / player system 0x0600000000000403 | exec `0x8b2ab0` / ser `0x68f240` / h 0xa79170 | u8 0 \| u32 \| u32 | Encounter: match ended (UI state machine event 0x12) [UI.RecvNotice_UIStateMachineEvent] | old server only |
| `0x2039` | match | Dialog / object IID (player 0x02..01 or entity) | exec `0x8b2040` / ser `0x83beb0` / h 0xa7fe60 | u8 0 \| u32 \| u32 \| PropTable [trace stopped early] | Dialog: play a context dialog element (announcer/VO chosen from team/context properties 0x100003BD, 0x10000865, 0x10000806, 0x1000081C...) with PropTable | no |
| `0x203a` | social | Contacts / player system 0x0600000000000403 | exec `0x8aca70` / ser `0x839500` / h 0xa13850 | u8 0 \| u32 | Contacts: self presence changed [Contacts.RecvNotice_UI_NotifySelfChangedPresence] | no |
| `0x203b` | social | Contacts / player system 0x0600000000000403 | exec `0x8ac670` / ser `0x846d10` / h 0xa46aa0 | u8 0 \| {u32 {u64 u64 wstr u64 wstr wstr u32 u8 u32 u32 u32 u32 u32 u32 u32 wstr u32}} | Contacts: list (0xa3ced0) (?) | no |
| `0x203d` | match | Effects (agent obj+0x8C) / object IID (player 0x02..01 or entity) | exec `0x8b6a00` / ser `0x839dd0` / h 0xaa1b60 | u8 0 \| u64 | Effects: raise 0x10000009 on effects flagged 0x10000007 (cleanse/expire all?) | no |
| `0x203e` | match | Player-object gameplay / object IID (player 0x02..01 or entity) | exec `0x8b5e20` / ser `0x839720` / h 0x132c5c0 | u8 0 \| u8 | Player-object event u8 (no-op handler) | no |
| `0x203f` | social | CustomMatch / player system 0x0600000000000403 | exec `0x8aff80` / ser `0x83be20` / h 0xa77520 | u8 0 \| {u32 QueueKey{u32 did,u32 flags} {u32 {u32 {wstr u64 u64 u32 u32 u32 u8} u32}} {u32 {wstr u64 u64 u32 u32 u32 u8} u32 u32} u64 u32 u32 {u32 StringInfo} {u32 StringInfo} u8} | CustomMatch: left [CustomMatch.RecvNotice_UI_CustomMatch_Left] | no |
| `0x2040` | social | CustomMatch / player system 0x0600000000000403 | exec `0x8afd90` / ser `0xb0d380` / h 0xa0c6f0 | u8 | CustomMatch: launched [CustomMatch.RecvNotice_UI_CustomMatch_Launched] | no |
| `0x2041` | social | CustomMatch / player system 0x0600000000000403 | exec `0x8afd10` / ser `0x839500` / h 0xa77600 | u8 0 \| u32 | CustomMatch: kicked [CustomMatch.RecvNotice_UI_CustomMatch_Kicked] | no |
| `0x2042` | social | CustomMatch / player system 0x0600000000000403 | exec `0x8afb10` / ser `0x4452e0` / h 0x5a8680,0xa0c6d0 | u8 0 \| StringInfo | CustomMatch: creation failed [CustomMatch.RecvNotice_UI_CustomMatch_CreationFailed] | no |
| `0x2043` | match | Effects (agent obj+0x8C) / object IID (player 0x02..01 or entity) | exec `0x8b6c70` / ser `0x846f30` / h 0xaa1cd0 | u8 0 \| {u32 {{{cint {u32}} {cint {u32}} {u32 u32}} GUID u8 {u32}}} \| u8 | Effects: apply a list of effect instances (same as 0x200C) | no |
| `0x2044` | match | Player-object gameplay / object IID (player 0x02..01 or entity) | exec `0x8b5eb0` / ser `0x839790` / h 0xa1a510 | u8 0 \| u64 \| u8 | Root+0x90 counter push/pop (u64, u8 on/off) (?) | no |
| `0x2045` | match (end) | Encounter / player system 0x0600000000000403 | exec `0x8b2bd0` / ser `0x849ea0` / h 0xa91bf0 | u8 0 \| u32 n \| n x entry (reader 0x8776a0) \| f32 | Encounter: end-of-match stats [Encounter.RecvNotice_UI_SetEndOfMatchStatsHeader, Encounter.RecvNotice_PlayEndOfMatchEncounterMovie] | built, unused |
| `0x2047` | match | Dialog / object IID (player 0x02..01 or entity) | exec `0x8b20e0` / ser `0x839620` / h 0xa13b40 | u8 0 \| u64 \| u64 \| u32 \| u32 \| u32 | Dialog: dialog-system call vt+4 (u64, u64, 3 u32) - probable conversation line/advance (?) | no |
| `0x2048` | social | CustomMatch / player system 0x0600000000000403 | exec `0x8afe00` / ser `0x444b70` / h 0xa0c670 | u8 0 \| u64 \| u32 | CustomMatch: moved position [CustomMatch.RecvNotice_UI_CustomMatch_MovedPosition] | no |
| `0x204a` | menus | Lobby / player system 0x0600000000000403 | exec `0x8b8ca0` / ser `0x83c200` / h 0xab9ab0 | u8 0 \| u32 \| {u32 u64 u32 StringInfo wstr u32 {cint u32}} \| u64 | Lobby: player picked amplifier set [Lobby.RecvNotice_PlayerPickedAmplifierSet] | no |
| `0x204b` | menus | Lobby / player system 0x0600000000000403 | exec `0x8b8b90` / ser `0x838930` / h 0xabd420 | u8 0 \| u64 \| u64 \| u32 | Lobby: match launch warning [Lobby.RecvNotice_MatchLaunchWarning, Lobby.RecvNotice_ClearLightResourcePackReferences, Lobby.RecvNotice_ClearHeavyResourcePackReferences] | no |
| `0x204c` | menus | Lobby / player system 0x0600000000000403 | exec `0x8b8970` / ser `0x845810` / h 0xabde80 | u8 0 \| u32 \| u32 \| QueueKey{u32 did,u32 flags} \| u64 \| u32 \| u32 \| {u32 {u32 u32 u32 u8 u32}} \| list<u32> \| u8 \| u8 | Lobby: state [Lobby.RecvNotice_UpdateLobbyStateSingle, Lobby.RecvNotice_LobbyEncounterDetails, UI.RecvNotice_Incremental_ItemStatuses] | sent |
| `0x204d` | match | Effects (agent obj+0x8C) / object IID (player 0x02..01 or entity) | exec `0x8b6aa0` / ser `0x849b80` / h 0xa9fbb0 | u8 0 \| GUID \| {u32} | Effects: raise events on one effect instance (same as 0x202C) | no |
| `0x204e` | match | Effects (agent obj+0x8C) / object IID (player 0x02..01 or entity) | exec `0x8b6820` / ser `0x444b70` / h 0xaa1b90 | u8 0 \| u64 \| u32 | Effects: raise script event DID on all effects of agent u64 | no |
| `0x204f` | social | Contacts / player system 0x0600000000000403 | exec `0x8ac870` / ser `0x839dd0` / h 0xa30740 | u8 0 \| u64 | Contacts: unignored [Contacts.RecvNotice_UI_NotifyContactUnignored] | no |
| `0x2050` | match | Player-object gameplay / object IID (player 0x02..01 or entity) | exec `0x8b5c50` / ser `0x444b70` / h 0xa14580 | u8 0 \| u64 \| u32 | Run scriptlet key u32 on object u64 (obj+0x10 scriptlet component, no variables) | no |
| `0x2051` | social | Contacts / player system 0x0600000000000403 | exec `0x8ac5f0` / ser `0x8423e0` / h 0xa58340 | u8 0 \| u64 \| wstr | Contacts: added / ignored / removed [Contacts.RecvNotice_UI_NotifyContactAdded, Contacts.RecvNotice_UI_NotifyContactIgnored, Contacts.RecvNotice_UI_NotifyContactRemoved] | no |
| `0x2052` | menus | Amplifier / player system 0x0600000000000403 | exec `0x8a9fc0` / ser `0x839500` / h 0xa0b560 | u8 0 \| u32 | Amplifier: set error [Amplifier.RecvNotice_NotifyAmplifierSetError] | no |
| `0x2053` | menus | Lobby / player system 0x0600000000000403 | exec `0x8b8ec0` / ser `0x8465b0` / h 0xaba390 | u8 0 \| u32 \| {u32 StringInfo} \| {u32 StringInfo} | Lobby: match started (UI event 0x14) [UI.RecvNotice_UIStateMachineEvent] | built, unused |
| `0x2054` | menus | Lobby / player system 0x0600000000000403 | exec `0x8b8870` / ser `0x83c4e0` / h 0xab7c10 | u8 0 \| StringInfo \| StringInfo | Lobby: draft trade request [Lobby.RecvNotice_Draft_TradeRequest] | no |
| `0x2056` | match | Player-object gameplay / object IID (player 0x02..01 or entity) | exec `0x8b5bb0` / ser `0x83c050` / h 0xa0d040 | u8 0 \| u32 \| PropTable [trace stopped early] | Run scriptlet key u32 on the destination object with a variable table (PropTable) | no |
| `0x2058` | social | Contacts / player system 0x0600000000000403 | exec `0x8acaf0` / ser `0x842830` / h 0xa27f70 | u8 0 \| wstr | Contacts: self status message changed [Contacts.RecvNotice_UI_NotifySelfChangedStatusMessage] | no |
| `0x2059` | match | Player-object gameplay / object IID (player 0x02..01 or entity) | exec `0x8b59e0` / ser `0x83f9b0` / h 0xa73580 | u8 0 \| u32 \| PropTable [trace stopped early] | Spawn a client-side object/effect from a template with properties (root+0x24, 0xa69170) (?) | no |
| `0x205b` | menus | Lobby / player system 0x0600000000000403 | exec `0x8b87f0` / ser `0x68f240` / h 0xab8490 | u8 0 \| u32 \| u32 | Lobby: rejoin room [Lobby.RecvNotice_LobbyRejoinRoom] | no |
| `0x205c` | match | Player-object gameplay / object IID (player 0x02..01 or entity) | exec `0x8b5d90` / ser `0x839720` / h 0xa4ebc0 | u8 0 \| u8 | Root+0x5c: add/remove the destination player from a tracked list (u8) (?) | no |
| `0x205d` | social | CustomMatch / player system 0x0600000000000403 | exec `0x8aff00` / ser `0x839dd0` / h 0xa0c5b0 | u8 0 \| u64 | CustomMatch: participant removed [CustomMatch.RecvNotice_UI_CustomMatch_RemovedParticipant] | no |
| `0x205e` | social | Contacts / player system 0x0600000000000403 | exec `0x8ac4f0` / ser `0x846ca0` / h 0xa46b00 | u8 0 \| u64 \| {u32 {u64 u64 wstr u64 wstr wstr u32 u8 u32 u32 u32 u32 u32 u32 u32 wstr u32}} | Contacts: group destroyed [Contacts.RecvNotice_UI_NotifyContactGroupDestroyed] | no |
| `0x2060` | menus | Lobby / player system 0x0600000000000403 | exec `0x8b9060` / ser `0x848380` / h 0xabe1b0 | u8 0 \| list<u32> \| list<u32> \| list<u64> \| {u32 StringInfo} \| {{u32 u8}} \| list<u32> \| list<u32> \| {{u32 u8}} \| u32 \| u32 \| u8 \| list<u32> \| list<u32> \| list<u32> \| list<u32> \| list<u32> \| list<u32> \| list<u32> \| {u32 {u32 u64 u32 StringInfo wstr u32 {cint u32}}} \| {u8 u32 u32 u32 list<u32> list<u64> u32 u32 u64} | Lobby: full state update [Lobby.RecvNotice_PlayerPickedStolenPowers, Lobby.RecvNotice_UpdateLobbyStateSingle, Lobby.RecvNotice_PlayerPickedAmplifierSet] | no |
| `0x2061` | menus | Lobby / player system 0x0600000000000403 | exec `0x8b8f40` / ser `0x838930` / h 0xab85a0 | u8 0 \| u64 \| u64 \| u32 | Lobby: early launch time [Lobby.RecvNotice_UpdateEarlyLaunchTime] | no |
| `0x2062` | match | Effects (agent obj+0x8C) / object IID (player 0x02..01 or entity) | exec `0x8b6bd0` / ser `0x843d60` / h 0xa9fb00 | u8 0 \| {{{{cint {u32}} {cint {u32}} {u32 u32}} GUID u8 {u32}}} \| u8 | Effects: add one effect instance (same as 0x200F) | no |
| `0x2063` | match | Effects (agent obj+0x8C) / object IID (player 0x02..01 or entity) | exec `0x8b6960` / ser `0x849ab0` / h 0xaa1c90 | u8 0 \| u64 \| {u32} \| u32 | Effects: raise events on effects matching key (u64 agent, list, u32 key) | no |
| `0x2065` | social | Contacts / player system 0x0600000000000403 | exec `0x8acb70` / ser `0x839500` / h 0xa0c260 | u8 0 \| u32 | Contacts: contact list notification [Contacts.RecvNotice_UI_ContactListNotification] | no |
| `0x2069` | match | Encounter / object IID (player 0x02..01 or entity) | exec `0x8b5890` / ser `0x83f7b0` / h 0xa5a680 | u8 0 \| u64 \| u32 \| u32 \| u32 \| u32 \| u32 \| u32 \| u32 \| u32 \| u32 \| u32 \| u32 | Encounter: objective tracker status (world tracker icon x/y/state/icon/variant/category) [Encounter.RecvNotice_UI_UpdateTrackerStatus] | no |
| `0x206b` | menus | Lobby / player system 0x0600000000000403 | exec `0x8b92c0` / ser `0x839500` / h 0xab8900 | u8 0 \| u32 | Lobby: connect to lobby (store or send ConnectToLobbyMessage) | no |
| `0x206c` | menus | Lobby / player system 0x0600000000000403 | exec `0x8b8e40` / ser `0x83c280` / h 0xabd570 | u8 0 \| StringInfo \| u32 | Lobby: player selected early launch [Lobby.RecvNotice_PlayerSelectedEarlyLaunchFromServer, Lobby.RecvNotice_ClearLightResourcePackReferences, Lobby.RecvNotice_ClearHeavyResourcePackReferences] | no |
| `0x206d` | menus | Lobby / player system 0x0600000000000403 | exec `0x8b8b10` / ser `0x839500` / h 0xab84f0 | u8 0 \| u32 | Lobby: all loaded? [Lobby.RecvNotice_HideBackButton, Lobby.RecvNotice_UpdateLobbyLoadingPercentForViewmatch, ViewMatch.RecvNotice_ViewMatch_ShowAllPlayersPanel] | sent |
| `0x206e` | menus | Lobby / player system 0x0600000000000403 | exec `0x8b88f0` / ser `0x839500` / h 0xab8e00 | u8 0 \| u32 | **View-match enable**: handler `0xab8e00` sends 0x20F2 (connect to lobby) with the view-match byte = 1. *(confirmed, static)* — earlier note: Lobby: view-match enable (spectator) (?) | no |
| `0x206f` | match | Effects (agent obj+0x8C) / object IID (player 0x02..01 or entity) | exec `0x8b6d10` / ser `0x83c1a0` / h 0xaaa830 | u8 0 \| GUID \| {u32 u32 u32} \| {u32 {u32}} | Effects: update effect variable (same as 0x2019) | no |
| `0x2070` | social | Grouping / player system 0x0600000000000403 | exec `0x8b6310` / ser `0xb0d380` / h 0xa0d290 | u8 | Grouping: user can create group [UI.RecvNotice_UserCanCreateGroup] | no |
| `0x2071` | social | Grouping / player system 0x0600000000000403 | exec `0x8b6190` / ser `0x83c100` / h 0xa7b2d0 | u8 0 \| {u32 u64 {u32 {wstr u64 u64 u32 u32 u32 u8} u32} {u32 {wstr u64 u64 u32 u32 u32 u8} u32 u32} QueueKey{u32 did,u32 flags} u32} \| u8 \| StringInfo | Grouping: player left group [Grouping.RecvNotice_PlayerLeftGroup] | no |
| `0x2073` | match | Player-object gameplay / object IID (player 0x02..01 or entity) | exec `0x8b5b20` / ser `0x83c030` / h 0xa883f0 | u8 0 \| ScriptletList (same reader family as 0x8D) | Start scriptlets on listed entities via the local player (same body as 0x8D; 0xa22da0) | no |
| `0x2074` | match | Player-object gameplay / object IID (player 0x02..01 or entity) | exec `0x8b5a80` / ser `0x83f690` / h 0xaa0530 | u8 0 \| u32 \| u8 | Agent component obj+0xbc vt+0x50: u32 u8 (?) | no |
| `0x2075` | match | Encounter / object IID (player 0x02..01 or entity) | exec `0x8b2cf0` / ser `0x839720` / h 0xa14010 | u8 0 \| u8 | Encounter: objective tracker enabled [Encounter.RecvNotice_UI_SetObjectiveTrackerEnabled] | built, unused |
| `0x2076` | social | CustomMatch / player system 0x0600000000000403 | exec `0x8af8a0` / ser `0x444b70` / h 0xa0c610 | u8 0 \| u64 \| u32 | CustomMatch: assigned team [CustomMatch.RecvNotice_UI_CustomMatch_AssignedTeam] | no |
| `0x2077` | match | Usage (cast/channel bars) / object IID (player 0x02..01 or entity) | exec `0x8c1a70` / ser `0x839f20` / h 0xaa2570 | u8 0 \| u64 \| u64 \| u32 | Usage: induction (cast bar) percent [Usage.RecvNotice_UpdateInductionPercent] | no |
| `0x2078` | match | Upgrade / object IID (player 0x02..01 or entity) | exec `0x8c0a20` / ser `0x845df0` / h 0xa9ff30 | u8 0 \| list<u32> | **Recommended upgrades** (the shop's next-buy hint), to the champion IID (ics). *(confirmed)* — earlier note: Upgrade: next recommended upgrade [Upgrade.RecvNotice_UpdateNextRecommendedUpgrade] | sent |
| `0x207b` | match | Skill HUD / object IID (player 0x02..01 or entity) | exec `0x8bc5f0` / ser `0x839ab0` / h 0xa26570 | u8 0 \| u64 \| u32 \| u8 \| u8 | Skill HUD: enable skill button [Skill.RecvNotice_EnableSkillButton] | no |
| `0x207c` | match | Skill HUD / object IID (player 0x02..01 or entity) | exec `0x8bc540` / ser `0x8399a0` / h 0xa3a000 | u8 0 \| u32 \| u32 \| u8 \| u32 \| u32 | Skill HUD: slot override table (slot<5: u32, u8, u32) | no |
| `0x2080` | menus | Character/account / player system 0x0600000000000403 | exec `0x8aaac0` / ser `0x8392f0` / h 0xa7dfb0 | u8 0 \| u32 \| u32 \| u32 \| u32 \| u32 \| u32 \| u32 \| u32 | Account level / XP [Character.RecvNotice_SendAccountEndOfMatchLevelAndXP, Character.RecvNotice_SendAccountLevelAndXP, UI.RecvNotice_ProtectorAdvancementStatus] | sent |
| `0x2081` | menus | Character/account / player system 0x0600000000000403 | exec `0x8aa970` / ser `0x68f240` / h 0xa1ab40 | u8 0 \| u32 \| u32 | Currency balance [Character.RecvNotice_SendAccountCurrencyBalance] | old server only |
| `0x2082` | match | Usage (cast/channel bars) / object IID (player 0x02..01 or entity) | exec `0x8c0ec0` / ser `0x839dd0` / h 0xaaf400 | u8 0 \| u64 | Usage: channel started [Usage.RecvNotice_UpdateChannelStarted] | no |
| `0x2083` | match | Skill HUD / object IID (player 0x02..01 or entity) | exec `0x8bc730` / ser `0x839500` / h 0xa1a5a0 | u8 0 \| u32 | Root+0x90: store u32 (+0xc0) (?) | no |
| `0x2084` | match | Skill HUD / object IID (player 0x02..01 or entity) | exec `0x8bc2c0` / ser `0x444b70` / h 0xa0e430 | u8 0 \| u64 \| u32 | Remove a property (id u32) from entity u64 (0x58b4c0) | no |
| `0x2086` | match | Upgrade / object IID (player 0x02..01 or entity) | exec `0x8bfe50` / ser `0x83f5b0` / h 0xa0f570 | u8 0 \| Handle{u32,u64} | **Shop transaction done**: `u8 0 \| Handle{u32 seq, u64 iid}`; clears the shop's pending selection so the shop is usable again (ics/shop.py, tested in game). *(confirmed)* — earlier note: Clear the current selection if it equals handle (0xa0f570) (?) | sent |
| `0x2087` | menus | GM_UI / player system 0x0600000000000403 | exec `0x8be910` / ser `0x83c4e0` / h 0xac85f0 | u8 0 \| StringInfo \| StringInfo | UI: display dialog text (StringInfo, StringInfo) [UI.RecvNotice_DisplayDialogText] | no |
| `0x208c` | match | Skill HUD / object IID (player 0x02..01 or entity) | exec `0x8bc220` / ser `0x83f690` / h 0xa0e3c0 | u8 0 \| u32 \| u8 | Skill HUD: skill-button update suppressed [Skill.RecvNotice_UI_NotifySkillButtonUpdateIsSuppressed] | no |
| `0x208d` | match | Skill HUD / object IID (player 0x02..01 or entity) | exec `0x8bc190` / ser `0xb0d380` / h 0xa16dd0 | u8 | Vitals: display floaty status (u8) [Vitals.RecvNotice_DisplayFloatyStatus] | no |
| `0x208f` | social | Contacts / player system 0x0600000000000403 | exec `0x8ac3f0` / ser `0x83bdd0` / h 0xa27f10 | u8 0 \| {u64 u64 wstr u64 wstr wstr u32 u8 u32 u32 u32 u32 u32 u32 u32 wstr u32} | Contacts: change note [Contacts.RecvNotice_UI_NotifyContactChangeNote] | no |
| `0x2090` | menus | Amplifier / player system 0x0600000000000403 | exec `0x8aa0c0` / ser `0x8481a0` / h 0xa64520 | u8 0 \| u32 \| u32 \| {u32 {u32 u64 u32 StringInfo wstr u32 {cint u32}}} | Amplifier sets list [Amplifier.RecvNotice_NotifyListAmplifierSets] | old server only |
| `0x2091` | match | Skill HUD / object IID (player 0x02..01 or entity) | exec `0x8bc910` / ser `0x839c70` / h 0xa5d0a0 | u8 0 \| u64 \| u64 \| u32 \| u32 | Skill HUD: skill UI overlay [Skill.RecvNotice_UpdateSkillUIOverlay] | no |
| `0x2092` | match | Skill HUD / object IID (player 0x02..01 or entity) | exec `0x8bbfb0` / ser `0x68f240` / h 0xa2a190 | u8 0 \| u32 \| u32 | UI: execute-skill error [UI.RecvNotice_ExecuteSkillError] | no |
| `0x2095` | menus | Character/account / player system 0x0600000000000403 | exec `0x8aaf60` / ser `0x83f410` / h 0xa7ea00 | u8 0 \| u32 \| u32 \| StringInfo | Item fulfilled ribbon [Character.RecvNotice_Ribbon_ItemFulfilled, Character.RecvNotice_Ribbon_FinishedItemsFulfilled] | built, unused |
| `0x2096` | match | Usage (cast/channel bars) / object IID (player 0x02..01 or entity) | exec `0x8c0f50` / ser `0x839e20` / h 0xaa2620 | u8 0 \| u64 \| u64 | Usage: induction cancelled [Usage.RecvNotice_UpdateCancelledInductionForUserToFlash, Usage.RecvNotice_UpdateInductionPercent] | no |
| `0x209d` | menus | Character/account / player system 0x0600000000000403 | exec `0x8aac90` / ser `0x849630` / h 0xa7e4b0 | u8 0 \| {u8 cint {u32 {u32 u32 u32 u64 u64}}} | Master character list | sent |
| `0x209e` | menus | Character/account / player system 0x0600000000000403 | exec `0x8aab70` / ser `0x849e50` / h 0xa83370 | u8 0 \| {u8 cint {u32 {u32 StringInfo}}} | Character list delta (0xa83370) (?) | no |
| `0x209f` | match | Skill HUD / object IID (player 0x02..01 or entity) | exec `0x8bc690` / ser `0x839d50` / h 0xa5da40 | u8 0 \| u32 \| u64 | MapManager: show minimap targeting ring [MapManager.RecvNotice_ShowMiniMapTargetingRing] | no |
| `0x20a0` | match | Skill HUD / object IID (player 0x02..01 or entity) | exec `0x8bc4a0` / ser `0x8401e0` / h 0xa6dd10 | u8 0 \| u32 \| u32 \| Handle{u32,u64} \| u8 | Skill HUD: skill disable condition (slot, ErrorType, add/remove); catalog note says 16 bytes after ErrorType, the emulated Handle reader took 12 - check [Skill.RecvNotice_EnableSkillButton] | no |
| `0x20a2` | match | StatusIcon / object IID (player 0x02..01 or entity) | exec `0x8bd860` / ser `0x847d30` / h 0xab37b0 | u8 0 \| u64 \| list<u32> \| {u32 Handle{u32,u64}} \| list<u32> \| list<u32> \| {u32 StringInfo} \| list<u64> \| {u32 u64} \| {u32 u32} \| list<u64> \| {u32 {StringInfo u32 u32 {u32 {u8 u8 u8 u32}}}} \| list<u32> | StatusIcon: add status icon (+ stack count string) [UI.RecvNotice_UpdateSkillStackCountString, StatusIcon.RecvNotice_AddStatusIcon] | no |
| `0x20a8` | match | StatusIcon / object IID (player 0x02..01 or entity) | exec `0x8be360` / ser `0x840580` / h 0x5a8680,0xab3250 | u8 0 \| u64 \| Handle{u32,u64} \| u32 \| u32 \| StringInfo \| u64 \| u64 \| u32 \| u64 \| {StringInfo u32 u32 {u32 {u8 u8 u8 u32}}} \| u32 | StatusIcon: update status icon (+ stack count) [UI.RecvNotice_UpdateSkillStackCountString, StatusIcon.RecvNotice_UpdateStatusIcon] | no |
| `0x20ad` | menus | Matchmaking / player system 0x0600000000000403 | exec `0x8ba9a0` / ser `0x839500` / h 0xa0dbe0 | u8 0 \| u32 | Players accepted match [UI.RecvNotice_NumPlayersAcceptedMatch] | sent |
| `0x20ae` | social | Contacts / player system 0x0600000000000403 | exec `0x8ac170` / ser `0x444b70` / h 0xa58790 | u8 0 \| u64 \| u32 | Contacts: presence changed (variant) [Contacts.RecvNotice_UI_NotifyContactPresenceChanged] | no |
| `0x20af` | menus | Connection / player system 0x0600000000000403 | exec `0x8ac0e0` / ser `0x8452d0` / h 0xa99f00 | u8 0 \| u32 \| list<u32> \| list<u32> \| u32 | Enter match | sent |
| `0x20b0` | social | Chat / player system 0x0600000000000403 | exec `0x8abe20` / ser `0x8422a0` / h 0xa57cd0 | u8 0 \| wstr \| StringInfo \| wstr | Chat: strings, toggle unread / channel (?) [Chat.RecvNotice_ToggleUnreadChat] | no |
| `0x20b2` | match | Usage (cast/channel bars) / object IID (player 0x02..01 or entity) | exec `0x8c0ff0` / ser `0x839790` / h 0xaa4670 | u8 0 \| u64 \| u8 | Usage: channel interrupted / stopped [Usage.RecvNotice_ChannelingInterrupted, Usage.RecvNotice_UpdateChannelStopped] | no |
| `0x20b6` | social | Chat / player system 0x0600000000000403 | exec `0x8abea0` / ser `0x842300` / h 0xa770c0 | u8 0 \| wstr \| wstr | Chat: toggle unread [Chat.RecvNotice_ToggleUnreadChat] | no |
| `0x20b8` | menus | Character/account / player system 0x0600000000000403 | exec `0x8aaff0` / ser `0x844fd0` / h 0xa88030 | u8 0 \| {u32 {u32 u32 u32 u8 u32}} | Item statuses [UI.RecvNotice_ItemStatuses, UI.RecvNotice_AvailableCharacterList, UI.RecvNotice_Incremental_ItemStatuses] | sent |
| `0x20b9` | menus | Character/account / player system 0x0600000000000403 | exec `0x8aaeb0` / ser `0x83bb90` / h 0xa1aa50 | u8 0 \| u32 \| u32 \| u32 \| u32 \| u32 \| u32 \| StringInfo \| StringInfo \| u32 | Soft currency reward [Character.RecvNotice_SendAccountCurrencyBalanceChanges, Character.RecvNotice_SendAccountEndOfMatchSoftCurrencyReward] | old server only |
| `0x20bb` | match | Usage (cast/channel bars) / object IID (player 0x02..01 or entity) | exec `0x8c1780` / ser `0x839eb0` / h 0xaa2540 | u8 0 \| u32 \| u32 | Usage: induction percent (variant) [Usage.RecvNotice_UpdateInductionPercent] | no |
| `0x20bc` | match | Usage (cast/channel bars) / object IID (player 0x02..01 or entity) | exec `0x8c0b50` / ser `0x839dd0` / h 0xaa02a0 | u8 0 \| u64 | Usage component obj+0x9c vt+0x50 (u64) (?) | no |
| `0x20bd` | match | Skill HUD / object IID (player 0x02..01 or entity) | exec `0x8bc050` / ser `0x444b70` / h 0xa16e20 | u8 0 \| u64 \| u32 | Vitals: display floaty status (u64, u32) [Vitals.RecvNotice_DisplayFloatyStatus] | no |
| `0x20c0` | menus | Matchmaking / player system 0x0600000000000403 | exec `0x8ba780` / ser `0x83fe00` / h 0xa37c70 | u8 0 \| QueueKey{u32 did,u32 flags} \| u32 \| u32 \| u32 | Joined queue [UI.RecvNotice_JoinedQueue] | sent |
| `0x20c2` | match | Skill HUD / object IID (player 0x02..01 or entity) | exec `0x8bc870` / ser `0x83c470` / h 0xa0e480 | u8 0 \| u64 \| PropValue [trace stopped early] | Set a property (PropValue) on entity u64 (0x58b770) | no |
| `0x20c5` | social | Contacts / player system 0x0600000000000403 | exec `0x8ac1f0` / ser `0x8423e0` / h 0xa27fa0 | u8 0 \| u64 \| wstr | Contacts: status message changed [Contacts.RecvNotice_UI_NotifyContactChangeStatusMessage] | no |
| `0x20c7` | menus | Amplifier / player system 0x0600000000000403 | exec `0x8aa040` / ser `0x83baf0` / h 0xa1ace0 | u8 0 \| {u32 u64 u32 StringInfo wstr u32 {cint u32}} | Amplifier: set [Amplifier.RecvNotice_NotifyAmplifierSet] | no |
| `0x20c8` | match | StatusIcon / object IID (player 0x02..01 or entity) | exec `0x8bdcd0` / ser `0x840390` / h 0x5a8680,0xab2d30 | u8 0 \| u64 \| u32 \| Handle{u32,u64} \| u32 \| u32 \| StringInfo \| u64 \| u64 \| u32 \| u64 \| {StringInfo u32 u32 {u32 {u8 u8 u8 u32}}} \| u32 | StatusIcon: add status icon (variant) [UI.RecvNotice_UpdateSkillStackCountString, StatusIcon.RecvNotice_AddStatusIcon] | no |
| `0x20c9` | match | Skill HUD / object IID (player 0x02..01 or entity) | exec `0x8bc400` / ser `0x849ce0` / h 0xa1d400 | u8 0 \| u64 \| u32 \| {u32} | Raise skill-slot event on agent (u64, u32, list) (0xa16e60) | no |
| `0x20cb` | social | Contacts / player system 0x0600000000000403 | exec `0x8ac370` / ser `0x83bdd0` / h 0xa35850 | u8 0 \| {u64 u64 wstr u64 wstr wstr u32 u8 u32 u32 u32 u32 u32 u32 u32 wstr u32} | Contacts: changed group [Contacts.RecvNotice_UI_NotifyContactChangedGroup] | no |
| `0x20cc` | social | Contacts / player system 0x0600000000000403 | exec `0x8ac270` / ser `0x83bdd0` / h 0xa58140 | u8 0 \| {u64 u64 wstr u64 wstr wstr u32 u8 u32 u32 u32 u32 u32 u32 u32 wstr u32} | Contacts: added / unignored / removed [Contacts.RecvNotice_UI_NotifyContactAdded, Contacts.RecvNotice_UI_NotifyContactUnignored, Contacts.RecvNotice_UI_NotifyContactRemoved] | no |
| `0x20ce` | match | Usage (cast/channel bars) / object IID (player 0x02..01 or entity) | exec `0x8c1b10` / ser `0x839e20` / h 0xa9e590 | u8 0 \| u64 \| u64 | Usage: induction complete [Usage.RecvNotice_UpdateInductionComplete] | no |
| `0x20d0` | match | StatusIcon / object IID (player 0x02..01 or entity) | exec `0x8be7d0` / ser `0x849300` / h 0xab1500 | u8 0 \| u64 \| Handle{u32,u64} \| u32 \| {u8 cint {u32 u32}} \| {u8 cint {u32 u32}} | StatusIcon: update tooltip [StatusIcon.RecvNotice_UpdateStatusIconTooltip] | no |
| `0x20d2` | match | MapManager / object IID (player 0x02..01 or entity) | exec `0x8ba4c0` / ser `0x83fd70` / h 0xa4c660 | u8 0 \| u64 \| Position \| u32 | MapManager: add minimap marker for IID at position (type u32) | no |
| `0x20d7` | menus | Matchmaking / player system 0x0600000000000403 | exec `0x8baa20` / ser `0x839500` / h 0xa0dc00 | u8 0 \| u32 | Pending match failure [UI.RecvNotice_PendingMatchFailure] | no |
| `0x20da` | match | MapManager notes 2 / player system 0x0600000000000403 | exec `0x8c2ee0` / ser `0x845df0` / h 0xadb230,0xa7f0b0 | u8 0 \| list<u32> | Map notes: set u32 list (0xadb230) (?) | no |
| `0x20db` | match | Usage (cast/channel bars) / object IID (player 0x02..01 or entity) | exec `0x8c0e30` / ser `0x839dd0` / h 0xaa0270 | u8 0 \| u64 | Usage component obj+0x9c vt+0x4c (u64) (?) | no |
| `0x20dc` | match | Skill HUD / object IID (player 0x02..01 or entity) | exec `0x8bc360` / ser `0x68f240` / h 0xa0e3e0 | u8 0 \| u32 \| u32 | UI: execute-skill error (variant) [UI.RecvNotice_ExecuteSkillError] | no |
| `0x20dd` | match | Upgrade / object IID (player 0x02..01 or entity) | exec `0x8c0990` / ser `0x845df0` / h 0xaaa190 | u8 0 \| list<u32> | Upgrade: set list on obj+0xa4 (current upgrades) (?) | no |
| `0x20de` | match | svc 0x20DE / object IID (player 0x02..01 or entity) | exec `0x8bd0e0` / ser `0x839d50` / h 0xadb190 | u8 0 \| u32 \| u64 | Service event u32 u64 (service 0x160d8e0) (?) | no |
| `0x20e0` | menus | Matchmaking / player system 0x0600000000000403 | exec `0x8bac30` / ser `0xb0d380` / h 0xa0dbd0 | u8 | Removed from queue: the expected answer to client 0x20C3 LeaveQueue. *(probable)* — earlier note: Removed from queue [UI.RecvNotice_RemovedFromQueue] | no |
| `0x20e2` | match | Upgrade / object IID (player 0x02..01 or entity) | exec `0x8c0ab0` / ser `0x847e80` / h 0xaaabf0 | u8 0 \| {u32 QueueKey{u32 did,u32 flags}} \| {u32 u64 u32 StringInfo wstr u32 {cint u32}} | **Inventory of a champion** (6 artifact slots + amplifier-set tail), sent to the champion IID (ics). *(confirmed)* — earlier note: Upgrade: current upgrades + power graph values [Upgrade.RecvNotice_UpdateCurrentUpgrades, Upgrade.RecvNotice_UpdatePowerGraphValues] | sent |
| `0x20e7` | match | Agent obj+0x84 / object IID (player 0x02..01 or entity) | exec `0x8aa300` / ser `0x8495f0` / h 0xaa0f20 | u8 0 \| {{u32 u32} {u32 {u64 Handle{u32,u64} u32 {u32 {u32}}}}} \| {u32 {u32 u32 {u32 {u64 Handle{u32,u64} u32 {u32 {u32}}}}}} | Agent component obj+0x84: update entries (?) | no |
| `0x20e8` | match | Agent obj+0x84 / object IID (player 0x02..01 or entity) | exec `0x8aa260` / ser `0x83f1d0` / h 0xaa0ef0 | u8 0 \| u32 \| Handle{u32,u64} | Agent component obj+0x84: u32 + handle (?) | no |
| `0x20e9` | match | StatusIcon / object IID (player 0x02..01 or entity) | exec `0x8bdc30` / ser `0x8402e0` / h 0xab38d0 | u8 0 \| u64 \| Handle{u32,u64} \| u8 | StatusIcon: remove status icon [UI.RecvNotice_RemoveSkillStackCountString, StatusIcon.RecvNotice_RemoveStatusIcon] | no |
| `0x20ec` | social | Contacts / player system 0x0600000000000403 | exec `0x8ac2f0` / ser `0x846d10` / h 0xa46bb0 | u8 0 \| {u32 {u64 u64 wstr u64 wstr wstr u32 u8 u32 u32 u32 u32 u32 u32 u32 wstr u32}} | Contacts: account icon changed [Contacts.RecvNotice_UI_NotifyContactAccountIconChanged] | no |
| `0x20ed` | menus | Character/account / player system 0x0600000000000403 | exec `0x8ab100` / ser `0x83bcf0` / h 0xa833d0 | u8 0 \| {{u32 {u32 {u32 u32 u32 u8 u32}}} {u8 cint {u32 {u32 u32 u32 u32 u32 u32 u32 u32 u8 u32 StringInfo}}}} | Champion data. If its champion list is empty, handler `0xa833d0` asks once more with client event 0x21A5. *(confirmed, static)* — earlier note: Champion data [Character.RecvNotice_MasterCharacterListReceived, UI.RecvNotice_DisplayDialogText, ConnectionManager.RecvNotice_UpdateConnectionState] | sent |
| `0x20f0` | match | Agent obj+0x84 / object IID (player 0x02..01 or entity) | exec `0x8aa1c0` / ser `0x83bb10` / h 0xaa0ec0 | u8 0 \| u32 \| {u64 Handle{u32,u64} u32 {u32 {u32}}} \| u32 | Agent component obj+0x84: u32, {u64, handle, u32, list}, u32 (?) | no |
| `0x20f3` | menus | Matchmaking / player system 0x0600000000000403 | exec `0x8ba600` / ser `0x839500` / h 0xa0dc50 | u8 0 \| u32 | Barred from matching [UI.RecvNotice_BarredFromMatching] | no |
| `0x20f5` | match | Cinematic/HUD / object IID (player 0x02..01 or entity) | exec `0x8ac050` / ser `0x83bdb0` / h 0xa9d140 | u8 0 \| {u32 u32} | Play cinematic [UI.RecvNotice_UpdateHUDVisibility] | sent |
| `0x20f7` | match | Upgrade / object IID (player 0x02..01 or entity) | exec `0x8c04f0` / ser `0x839bd0` / h 0x132c5c0 | u8 0 \| u64 \| u32 \| u64 | Same layout as 0x20F8 (u64 u32 f64) - no-op handler in this build | no |
| `0x20f8` | match | Skill HUD / object IID (player 0x02..01 or entity) | exec `0x8bc7c0` / ser `0x839bd0` / h 0xa0e320 | u8 0 \| u64 \| u32 \| u64 | Skill cooldown [UI.RecvNotice_StartSkillCooldown] | sent |
| `0x20f9` | match | Skill HUD / object IID (player 0x02..01 or entity) | exec `0x8bc0f0` / ser `0x839550` / h 0xa2a1b0 | u8 0 \| u64 \| u32 \| u8 | Raise skill availability event 0x100000B6/B7 on agent (slot, bool) | no |
| `0x20fa` | menus | Matchmaking / player system 0x0600000000000403 | exec `0x8ba700` / ser `0x68f240` / h 0xa15550 | u8 0 \| u32 \| u32 | Match found [UI.RecvNotice_FoundMatch] | sent |
| `0x20ff` | menus | Encounter / player system 0x0600000000000403 | exec `0x8b5610` / ser `0x846eb0` / h 0xa734d0 | u8 0 \| list<u32> \| list<u32> \| {u32 {cint,u8}} \| list<u32> | Encounter info update [Encounter.RecvNotice_MasterEncounterListReceived, Encounter.RecvNotice_ResetMapSelectionList, ConnectionManager.RecvNotice_UpdateConnectionState] | no |
| `0x2101` | menus | Matchmaking / player system 0x0600000000000403 | exec `0x8baba0` / ser `0x845ac0` / h 0xa740d0 | u8 0 \| u32 \| u32 \| list<u32> \| list<u32> \| u32 \| u32 | Queue eligibility [UI.RecvNotice_QueueEligibility] | no |
| `0x2103` | social | CustomMatch / player system 0x0600000000000403 | exec `0x8afa90` / ser `0x83f690` / h 0xa13950 | u8 0 \| u32 \| u8 | CustomMatch: draft mode [CustomMatch.RecvNotice_UI_CustomMatch_SetDraftMode] | no |
| `0x2104` | menus | Character/account / player system 0x0600000000000403 | exec `0x8aadb0` / ser `0x849680` / h 0xa7e0a0 | u8 0 \| u32 \| u32 \| StringInfo \| u32 \| u32 \| u32 \| u32 \| u32 \| u32 \| u32 \| u32 \| {u8 cint {u32 {u32 u32 u32 u64 u64}}} \| list<u32> \| list<u32> \| list<u32> \| {{u32 u8}} \| list<u32> \| list<u32> \| u32 \| u8 | Character level / XP [Character.RecvNotice_SendAccountEndOfMatchCharacterLevelAndXP, Character.RecvNotice_SendAccountEndOfMatchAccoladesEarned, Character.RecvNotice_Ribbon_CharacterLevelChanged] | old server only |
| `0x2105` | match | engine static / object IID (player 0x02..01 or entity) | exec `0xab7720` / ser `0x996170` / h 0x634f90,0x6575e0 | u8 0 [trace stopped early] | Static-registered event (empty/odd body) (?) | no |
| `0x2107` | menus | Amplifier / player system 0x0600000000000403 | exec `0x8aa140` / ser `0x847870` / h 0xa57510 | u8 0 \| {u32 {u64 u32 {cint,u8} u32}} | Amplifier: contextual data [Amplifier.RecvNotice_NotifyContextualAmplifierData] | no |
| `0x2109` | social | CustomMatch / player system 0x0600000000000403 | exec `0x8afa10` / ser `0x839500` / h 0xa0c760 | u8 0 \| u32 | CustomMatch: set encounter [CustomMatch.RecvNotice_UI_CustomMatch_SetEncounter] | no |
| `0x210a` | menus | GM_UI / player system 0x0600000000000403 | exec `0x8be990` / ser `0x83f090` / h 0xac86f0 | u8 0 \| u32 \| u32 \| u32 | UI: display dialog text (u32 ids) [UI.RecvNotice_DisplayDialogText] | no |
| `0x210b` | menus | Matchmaking / player system 0x0600000000000403 | exec `0x8ba820` / ser `0xb0d380` / h 0xa818e0 | u8 | Match/queue error -> leave (dialog text, removed from queue) [UI.RecvNotice_RemovedFromQueue, UI.RecvNotice_PendingMatchFailure, UI.RecvNotice_DisplayDialogText] | no |
| `0x210c` | menus | Contextual store / player system 0x0600000000000403 | exec `0x8af7a0` / ser `0x839dd0` / h 0xa359b0 | u8 0 \| u64 | Contextual purchase success [Contextual.RecvNotice_PurchaseContextualItemSuccess] | no |
| `0x210d` | menus | Contextual store / player system 0x0600000000000403 | exec `0x8af6a0` / ser `0x444b70` / h 0xa35920 | u8 0 \| u64 \| u32 | Contextual purchase error [Contextual.RecvNotice_PurchaseContextualItemError] | no |
| `0x210f` | menus | Contextual store / player system 0x0600000000000403 | exec `0x8af720` / ser `0x846520` / h 0xa35a30 | u8 0 \| u64 \| u32 \| {u64 u32 {cint,u8} u32 {cint,u8} u32} | Contextual purchase price changed [Contextual.RecvNotice_PurchasePriceChanged] | no |
| `0x2115` | menus | Character/account / player system 0x0600000000000403 | exec `0x8aad20` / ser `0x846460` / h 0xa57000 | u8 0 \| {u32 {u64 u8 u32 u64 u64 u64 u64 u64 u64 u64 u64 u64 u64 u64 u64 u64 u64 u32 u32 u64 u64 u64 u64 u64 u64 u32 u64 u64 u64 u64 u64 u64 u64 u64 u32 u64 u64 u64 u64 u64 u64 u32 StringInfo StringInfo u64 u64 u64 u64 u64 u64 u64 u64 u64 u64 u64 u64 u64 u64 u64 u64 u64 u64 u64 u64 u64 u32 u32}} | Account encounter stats: the answer to client 0x2116 (Notice_Character__RequestAccountEncounterStats, slot confirmed). *(probable as reply)* — earlier note: Account encounter stats [Character.RecvNotice_SendAccountEncounterStats] | no |
| `0x211f` | menus | Achievement / player system 0x0600000000000403 | exec `0x8a9c30` / ser `0x8495a0` / h 0xa8b7f0 | u8 0 \| {u8 cint {u32 {u32 u32 u64 {u32 {u32 u32 u32 u32 u64 u8}}}}} | Pending achievement banners: answer to client 0x212E (the old server answers with an empty table). *(confirmed)* — earlier note: Pending achievement notifications [Achievement.RecvNotice_AllPendingAchivementBanners] | old server only |
| `0x2120` | menus | Achievement / player system 0x0600000000000403 | exec `0x8a9bb0` / ser `0x849540` / h 0xa870e0 | u8 0 \| {u8 cint {u32 {u32 u32 u64 {u32 {u32 u32 u32 u32 u64 u8}}}}} \| list<u32> | Achievement progress [Achievement.RecvNotice_SetAchievementObjectiveData, Achievement.RecvNotice_SetDeprecatedAchievements, UI.RecvNotice_ProtectorAdvancementStatus] | sent |
| `0x2123` | match | StatusIcon / object IID (player 0x02..01 or entity) | exec `0x8b2410` / ser `0x8490f0` / h 0xa9f030 | u8 0 \| u64 \| Handle{u32,u64} \| u32 \| u32 \| {u8 cint {u32 u32}} \| {u8 cint {u32 u32}} | StatusIcon component obj+0xc0 vt+0x5c (tooltip data) (?) | no |
| `0x2125` | menus | Character/account / player system 0x0600000000000403 | exec `0x8ab080` / ser `0x846680` / h 0xa7ebb0 | u8 0 \| {u32 {u32 u32 u32 u32 u32 u32 u64 u32 StringInfo}} | Pending reward sets: answer to client 0x2124 (old server). *(confirmed)* — earlier note: Pending reward sets [Character.RecvNotice_RewardSetsData] | old server only |
| `0x2126` | match | StatusIcon / object IID (player 0x02..01 or entity) | exec `0x8b24d0` / ser `0x849200` / h 0xa9f080 | u8 0 \| u64 \| u32 \| u32 \| {u8 cint {u32 u32}} \| {u8 cint {u32 u32}} | StatusIcon component obj+0xc0 vt+0x58 (?) | no |
| `0x2127` | match | StatusIcon / object IID (player 0x02..01 or entity) | exec `0x8be870` / ser `0x83f4d0` / h 0xab15d0 | u8 0 \| u64 \| Handle{u32,u64} | StatusIcon: update tooltip (variant) [StatusIcon.RecvNotice_UpdateStatusIconTooltip] | no |
| `0x2129` | match | StatusIcon / object IID (player 0x02..01 or entity) | exec `0x8b2370` / ser `0x83faa0` / h 0xa9f110 | u8 0 \| u64 \| u32 \| u32 | StatusIcon component obj+0xc0 vt+0x50 (u64 u32 u32) (?) | no |
| `0x212a` | match | StatusIcon / object IID (player 0x02..01 or entity) | exec `0x8b22c0` / ser `0x83f4d0` / h 0xa9f0d0 | u8 0 \| u64 \| Handle{u32,u64} | StatusIcon component obj+0xc0 vt+0x54 (handle) (?) | no |
| `0x212b` | match | Upgrade / object IID (player 0x02..01 or entity) | exec `0x8c0460` / ser `0x845df0` / h 0xa9ffd0 | u8 0 \| list<u32> | Upgrade component `obj+0xA4` vt+0x54 with a u32 list: the same call the client makes before it sends 0x212C (artifact skill-slot order, SkillSlot ids 10..15). Server echo of 0x212C. *(probable)* — earlier note: Upgrade component obj+0xa4 vt+0x54 (u32 list) (?) | no |
| `0x2134` | social | Chat / player system 0x0600000000000403 | exec `0x8abda0` / ser `0x8478a0` / h 0xa21f20 | u8 0 \| {u32 wstr} | Player system list (0xa21f20, compares names) (?) | no |
| `0x2135` | social | Chat / player system 0x0600000000000403 | exec `0x8abd20` / ser `0x845280` / h 0xa0ba80 | u8 0 \| StringInfo \| list<u64> | Chat: member list [Chat.RecvNotice_UpdatedMemberList] | no |
| `0x2137` | match | MapManager notes 2 / object IID (player 0x02..01 or entity) | exec `0x8b72c0` / ser `0x83fc20` / h 0xa8eb60 | u8 0 \| u64 \| {u32 u32 u64 u32} | MapManager: remove map note [MapManager.RecvNotice_RemoveMapNote] | no |
| `0x213d` | match | Encounter / object IID (player 0x02..01 or entity) | exec `0x8b2c50` / ser `0x83f5d0` / h 0xa368b0 | u8 0 \| u32 \| u32 \| u32 \| u32 | HUD element event [UI.RecvNotice_NotifyHUDElement] | sent |
| `0x213e` | match | Encounter / object IID (player 0x02..01 or entity) | exec `0x8b27d0` / ser `0x845500` / h 0xa5a7b0 | u8 0 \| {u32 {u32 u32 u32 u32}} | HUD: batch HUD element events [UI.RecvNotice_BatchNotifyHUDElements] | no |
| `0x2142` | match | Dialog / object IID (player 0x02..01 or entity) | exec `0x8b1fa0` / ser `0x8455e0` / h 0xa58e00 | u8 0 \| list<u32> \| u8 | Dialog: queue/allow list (u32 list, u8) (0xa475c0) (?) | no |
| `0x2143` | match | Dialog / object IID (player 0x02..01 or entity) | exec `0x8b1f10` / ser `0x839720` / h 0xa58dd0 | u8 0 \| u8 | Dialog: flag u8 (0xa475c0) (?) | no |
| `0x214b` | menus | Encounter / player system 0x0600000000000403 | exec `0x8b2860` / ser `0x845530` / h 0xa35f90 | u8 0 \| list<u32> \| QueueKey{u32 did,u32 flags} | Completed encounters + last map played [Encounter.RecvNotice_UI_CompletedEncounters, Encounter.RecvNotice_UI_LastMapPlayed] | built, unused |
| `0x214c` | social | Grouping / player system 0x0600000000000403 | exec `0x8b62a0` / ser `0xb0d380` / h 0xa0d230 | u8 | Grouping: invite cancelled [Grouping.RecvNotice_GroupInviteCanceled] | no |
| `0x2150` | match | Cinematic/HUD / object IID (player 0x02..01 or entity) | exec `0x8abfc0` / ser `0x839500` / h 0xa9cca0 | u8 0 \| u32 | UI: HUD visibility [UI.RecvNotice_UpdateHUDVisibility] | no |
| `0x2151` | social | CustomMatch / player system 0x0600000000000403 | exec `0x8b0080` / ser `0x83be40` / h 0xa0c780 | u8 0 \| u32 \| StringInfo \| StringInfo | CustomMatch: team name [CustomMatch.RecvNotice_UI_CustomMatch_SetTeamName] | no |
| `0x2154` | menus | Character/account / player system 0x0600000000000403 | exec `0x8ab190` / ser `0x68f240` / h 0xa571a0 | u8 0 \| u32 \| u32 | Protector icon slot [UI.RecvNotice_SendHeaderNameAndProtectorIcons] | no |
| `0x2157` | match | Effects (agent obj+0x8C) / object IID (player 0x02..01 or entity) | exec `0x8b6960` / ser `0x849ab0` / h 0xaa1c90 | u8 0 \| u64 \| {u32} \| u32 | Effects: raise events on matching effects (same as 0x2063) | no |
| `0x2158` | match | Effects (agent obj+0x8C) / object IID (player 0x02..01 or entity) | exec `0x8b6780` / ser `0x849a10` / h 0xaa1c50 | u8 0 \| u64 \| {u32} | Effects: raise events on all effects (same as 0x41) | no |
| `0x2159` | match | Encounter / object IID (player 0x02..01 or entity) | exec `0x8b2b30` / ser `0x845580` / h 0xa1cac0 | u8 0 \| list<u64> \| u32 | Encounter: root+0x38 list of IIDs + u32 (0xa15680) (?) | no |
| `0x215a` | match | Encounter / object IID (player 0x02..01 or entity) | exec `0x8b2740` / ser `0x847980` / h 0xa5cf20 | u8 0 \| {u32 {u32 u32 list<u64>}} | Encounter: root+0x38 list (0xa55690) (?) | no |
| `0x215c` | match | ViewMatch / object IID (player 0x02..01 or entity) | exec `0x8c1e40` / ser `0x845df0` / h 0xac0d90 | u8 0 \| list<u32> | ViewMatch: dampener counts [ViewMatch.RecvNotice_ViewMatch_UpdateDampenerCounts] | no |
| `0x215d` | menus | Account settings / player system 0x0600000000000403 | exec `0x8bae30` / ser `0x83f690` / h 0xa76b80 | u8 0 \| u32 \| u8 | Account flags [UI.RecvNotice_ProtectorAdvancementStatus] | sent |
| `0x215f` | match | Player-object gameplay / object IID (player 0x02..01 or entity) | exec `0x8b5cf0` / ser `0x83fa20` / h 0xa1a570 | u8 0 \| Handle{u32,u64} \| u8 | Root+0x90: handle + u8 (0x8728e0) (?) | no |
| `0x2161` | social | Contacts / player system 0x0600000000000403 | exec `0x8ac8f0` / ser `0x847900` / h 0xa46a70 | u8 0 \| {u32 {u64 u64 wstr u64 wstr wstr u32 u8 u32 u32 u32 u32 u32 u32 u32 wstr u32}} \| {u32 {u64 wstr}} | Contacts: two lists (?) | no |
| `0x216a` | menus | Account settings / player system 0x0600000000000403 | exec `0x8baeb0` / ser `0x849c00` / h 0xa76bb0 | u8 0 \| {u8 cint {{cint,u8} PropValue}} [trace stopped early] | Server preferences [UI.RecvNotice_ProtectorAdvancementStatus] | sent |
| `0x2171` | match | Training / player system 0x0600000000000403 | exec `0x8c3f60` / ser `0x8455e0` / h 0xadb230,0xa8de40 | u8 0 \| list<u32> \| u8 | Training: load control (encounter DIDs + lesson) [UI.RecvNotice_UpdateTrainingFloatyText] | no |
| `0x2172` | menus | GM_UI / object IID (player 0x02..01 or entity) | exec `0x8bea10` / ser `0x83c530` / h 0xa177e0 | u8 0 \| u64 \| u8 \| u32 \| u32 \| u32 \| StringInfo | UI: training floaty text [UI.RecvNotice_UpdateTrainingFloatyText] | no |
| `0x2173` | match | Encounter / object IID (player 0x02..01 or entity) | exec `0x8b2a20` / ser `0x839500` / h 0xa7a930 | u8 0 \| u32 | Encounter: training floaty text trigger (u32) [UI.RecvNotice_UpdateTrainingFloatyText] | no |
| `0x2174` | match | Training / object IID (player 0x02..01 or entity) | exec `0x8b7230` / ser `0x839500` / h 0xa93df0 | u8 0 \| u32 | Training: lesson event u32 (local player) | no |
| `0x2179` | match | MapManager / object IID (player 0x02..01 or entity) | exec `0x8ba420` / ser `0x845a70` / h 0xa5c350 | u8 0 \| {{u32 u8}} \| u32 | MapManager: minimap revealed cells (list of byte x,y) + flags -> property 0x7EC rect (fog of war) | no |
| `0x217a` | menus | Character/account / object IID (player 0x02..01 or entity) | exec `0x8ab2e0` / ser `0x845170` / h 0xa67110 | u8 0 \| u64 \| u32 \| u32 \| u64 \| u32 \| list<u32> | Character: (u64, u32, u32, u64, u32, list) (0xa67110) (?) | no |
| `0x217c` | social | CustomMatch / player system 0x0600000000000403 | exec `0x8b0000` / ser `0x444b70` / h 0xa0c5e0 | u8 0 \| u64 \| u32 | CustomMatch: protector icon [CustomMatch.RecvNotice_UI_CustomMatch_UpdateProtectorIcon] | no |
| `0x217d` | social | Grouping / player system 0x0600000000000403 | exec `0x8b6110` / ser `0x444b70` / h 0xa0d210 | u8 0 \| u64 \| u32 | Grouping: protector icon [Grouping.RecvNotice_UI_Grouping_UpdateProtectorIcon] | no |
| `0x217f` | match | Skill HUD / object IID (player 0x02..01 or entity) | exec `0x8bbf10` / ser `0x83f690` / h 0xa5d070 | u8 0 \| u32 \| u8 | MapManager: targeting ring (u32, u8) [MapManager.RecvNotice_ShowMiniMapTargetingRing] | no |
| `0x2180` | match | Skill HUD / object IID (player 0x02..01 or entity) | exec `0x8bbdf0` / ser `0x839500` / h 0xa6d800 | u8 0 \| u32 | MapManager: targeting ring (u32) [MapManager.RecvNotice_ShowMiniMapTargetingRing] | no |
| `0x2183` | social | Chat / object IID (player 0x02..01 or entity) | exec `0x8abf20` / ser `0x83bd10` / h 0xa5cf40 | u8 0 \| StringInfo \| StringInfo \| u32 \| u32 | Chat: (StringInfo, StringInfo, u32, u32) (0xa4d140) (?) | no |
| `0x2186` | menus | Character/account / player system 0x0600000000000403 | exec `0x8aac00` / ser `0x846410` / h 0xa3f2d0 | u8 0 \| {u32 {u32 u32 u8 u32 u32 StringInfo}} \| {u32 {u32 u32 u8 u32 u32 StringInfo}} | Best map / champion accolades [Character.RecvNotice_SendBestMapAccolades, Character.RecvNotice_SendBestChampAccolades] | no |
| `0x2187` | match | Skill HUD / object IID (player 0x02..01 or entity) | exec `0x8bbe80` / ser `0x839500` / h 0xa39f90 | u8 0 \| u32 | Skill HUD: enable skill button (variant) [Skill.RecvNotice_EnableSkillButton] | no |
| `0x2188` | menus | Character/account / player system 0x0600000000000403 | exec `0x8ab220` / ser `0x845000` / h 0xa61da0 | u8 0 \| u32 \| u8 \| u32 \| StringInfo \| list<u32> \| list<u32> \| list<u32> \| {{u32 u8}} \| list<u32> \| list<u32> | Accolades [Character.RecvNotice_SendAccountEndOfMatchAccoladesEarned] | old server only |
| `0x2189` | match | MapManager / object IID (player 0x02..01 or entity) | exec `0x8b9d10` / ser `0x839dd0` / h 0xa73e80 | u8 0 \| u64 | MapManager: teleport effects start/stop (u64) [MapManager.RecvNotice_UI_StopTeleportEffects, MapManager.RecvNotice_UI_StartTeleportEffects] | no |
| `0x218a` | match | MapManager / object IID (player 0x02..01 or entity) | exec `0x8b9c80` / ser `0x839dd0` / h 0xa846d0 | u8 0 \| u64 | MapManager: teleport effects start/stop (u64) [MapManager.RecvNotice_UI_StopTeleportEffects, MapManager.RecvNotice_UI_StartTeleportEffects] | no |
| `0x218b` | menus | Account settings / player system 0x0600000000000403 | exec `0x8baf30` / ser `0x83c340` / h 0xa839b0 | u8 0 \| {{u8 cint {u32 PropTable}}} [trace stopped early] | Account tables (game settings) [UI.RecvNotice_ProtectorAdvancementStatus] | sent |
| `0x218d` | menus | Matchmaking / player system 0x0600000000000403 | exec `0x8ba680` / ser `0x83c2e0` / h 0xa155f0 | u8 0 \| u32 \| StringInfo | Find match failure [UI.RecvNotice_FindMatchFailure] | no |
| `0x218e` | menus | Matchmaking / player system 0x0600000000000403 | exec `0x8ba910` / ser `0x839930` / h 0xa0dc20 | u8 0 \| u32 \| u32 | Matchmaking update interval [UI.RecvNotice_Matchmaking_NewUpdateInterval] | no |
| `0x218f` | menus | Matchmaking / player system 0x0600000000000403 | exec `0x8ba890` / ser `0x8466b0` / h 0xa38500 | u8 0 \| {u32 QueueKey{u32 did,u32 flags}} \| {u32 list<u32>} | Queue wait times [UI.RecvNotice_QueueWaitTimesUpdated] | no |
| `0x2190` | menus | Character/account / player system 0x0600000000000403 | exec `0x8aaa00` / ser `0x83f230` / h 0xa57200 | u8 0 \| u32 \| u32 \| u32 \| u32 \| u32 \| u32 \| u32 \| StringInfo \| StringInfo \| u32 \| u8 | Header + protector icons [UI.RecvNotice_SendHeaderNameAndProtectorIcons] | old server only |
| `0x2191` | menus | Matchmaking / player system 0x0600000000000403 | exec `0x8baca0` / ser `0xb0d380` / h 0xa12fd0 | u8 | Player system, empty (resets advancement view 0xa12fd0) (?) | no |
| `0x2197` | menus | LoginReward / player system 0x0600000000000403 | exec `0x8b9450` / ser `0x846680` / h 0xa81520 | u8 0 \| {u32 {u32 u32 u32 u32 u32 u32 u64 u32 StringInfo}} | Reward sets data (variant) [Character.RecvNotice_RewardSetsData] | no |
| `0x2198` | match | Player-object gameplay / object IID (player 0x02..01 or entity) | exec `0x8b5f50` / ser `0x839790` / h 0xa1a540 | u8 0 \| u64 \| u8 | Root+0x90 counter (u64, u8) (same family as 0x2044) (?) | no |
| `0x219c` | social | Contacts / player system 0x0600000000000403 | exec `0x8ac9f0` / ser `0x847950` / h 0xa1b0e0 | u8 0 \| {u32 {u64 wstr u64}} | Contacts: invitations [Contacts.RecvNotice_UI_NotifyContactOfInvitations] | no |
| `0x219d` | menus | LoginReward / player system 0x0600000000000403 | exec `0x8b94d0` / ser `0xb0d380` / h 0xa0d570 | u8 | Login reward: none eligible [LoginReward.RecvNotice_UI_NoEligibleLoginReward] | no |
| `0x219e` | menus | Matchmaking / player system 0x0600000000000403 | exec `0x8bad90` / ser `0x83feb0` / h 0xa37dc0 | u8 0 \| u32 \| u32 \| u32 \| u32 \| u32 \| u32 \| u32 \| u32 \| u32 \| u32 | Account standings [UI.RecvNotice_UI_DeliverAccountStandingsData] | old server only |
| `0x219f` | menus | Matchmaking / player system 0x0600000000000403 | exec `0x8ba560` / ser `0x848b80` / h 0xa5c840 | u8 0 \| {list<u32> list<u32> list<u32> list<u32> list<u32> list<u32> list<u32> list<u32> list<u32> {u32 {u32 u32 u32}}} \| u32 \| u32 \| u32 \| u32 \| u32 | Standings [UI.RecvNotice_UI_DeliverAccountStandingsData] | old server only |
| `0x21a0` | menus | Matchmaking / player system 0x0600000000000403 | exec `0x8bad10` / ser `0x68f240` / h 0xa37d60 | u8 0 \| u32 \| u32 | Player system u32 u32 (0xa37d60) (?) | no |
| `0x21a2` | menus | Matchmaking / player system 0x0600000000000403 | exec `0x8bab20` / ser `0x848e70` / h 0xa74100 | u8 0 \| {u32 {u64 wstr u32 u32 u32 u32 u32}} \| u32 | Leaderboard: answer to client 0x21A4 (Notice_UI__RequestLeaderboards, slot confirmed). *(probable)* — earlier note: Leaderboard (regional/friends) [UI.RecvNotice_DeliverRegionalLeaderboard, UI.RecvNotice_DeliverFriendsLeaderboard] | no |
| `0x21a3` | menus | Matchmaking / player system 0x0600000000000403 | exec `0x8baaa0` / ser `0x848e70` / h 0xa74140 | u8 0 \| {u32 {u64 wstr u32 u32 u32 u32 u32}} \| u32 | Leaderboard (variant): answer to client 0x21A4. *(probable)* — earlier note: Leaderboard (regional/friends) variant [UI.RecvNotice_DeliverRegionalLeaderboard, UI.RecvNotice_DeliverFriendsLeaderboard] | no |
| `0x21a6` | menus | Achievement / player system 0x0600000000000403 | exec `0x8a9cb0` / ser `0x83f090` / h 0xa57330 | u8 0 \| u32 \| u32 \| u32 | Achievement objective data / deprecated achievements [Achievement.RecvNotice_SetAchievementObjectiveData, Achievement.RecvNotice_SetDeprecatedAchievements] | no |
| `0x2000003d` | match | engine static / object IID (player 0x02..01 or entity) | exec `0xa313f0` / ser `0x874730` / h 0xaa0460 | u8 0 \| {u32 {u32 u32 u32 u32 u32 vec3 u8 u64 u32 u8 u32 u32 u32 u32 u32}} | Agent component obj+0xbc query (u32 list) (?) | no |

### 3.4 Network notices (44, inside event 0x2)

Send as event 0x2 to the object (usually the local player): `u8 0 | u32 notice | u32 blob length | blob`.

| notice | reader / deliver | blob layout (no base byte) | meaning | ics |
|---|---|---|---|---|
| `0x100004f7` | reader `0x9244a0` / deliver 0x90e4c0 | u32 | u32 (registration group 0x90e4c0) (?) | no |
| `0x10000118` | reader `0x92dc00` / deliver 0x910830 | u8 \| Position | u8 + Position: position-carrying notice (MapManager-side group 0x910830) (?) | no |
| `0x10000192` | reader `0x92dcd0` / deliver 0x9108f0 | u32 \| {u8 u8 u64 u64} | u32 + {u8,u8,u64,u64} (group 0x9108f0) (?) | no |
| `0x10000229` | reader `0x92dd50` / deliver 0x9109b0 | u8 \| Handle{u32,u64} | u8 + handle {u32,u64} (group 0x9109b0) (?) | no |
| `0x100004a5` | reader `0x9560d0` / deliver 0x91e780 | u32 | u32 (group 0x91e780, same block as tutorial hint) (?) | no |
| `0x1000027f` | reader `0x956130` / deliver 0x91e840 | u32 \| u8 | Tutorial hint: u32 hint id / u8 force open | sent |
| `0x10000288` | reader `0x9561f0` / deliver 0x91e900 | list<u32> | u32 list (same block as tutorial hint) (?) | no |
| `0x100003d5` | reader `0x955e30` / deliver 0x91e2e0 | u32 | u32 (group with event 0x20DE) (?) | no |
| `0x100003d7` | reader `0x955f90` / deliver 0x91e3a0 | u32 | u32 (group with event 0x20DE) (?) | no |
| `0x100003d6` | reader `0x955ff0` / deliver 0x91e510 | list<u32> | u32 list (group with event 0x20DE) (?) | no |
| `0x10000090` | reader `0x8c48c0` / deliver 0x8beac0 | u32 \| u64 | GM_UI.RecvNotice_DefeatStatusUpdated (u32 status, u64 iid) - defeat/respawn timer | sent |
| `0x100000bc` | reader `0x956580` / deliver 0x91edb0 | u64 \| u32 \| u32 \| u64 | GM_UI.RecvNotice_DefeatStatusUpdatedForEntity (u64 iid, u32, u32, f64 time) | sent |
| `0x10000059` | reader `0x9567d0` / deliver 0x91f3c0 | u32 \| u32 \| u32 \| u32 | GM_UI group, 4 u32 (0x91f3c0) (?) | no |
| `0x1000004a` | reader `0x9568b0` / deliver 0x91f3c0 | (empty) | GM_UI group, empty (0x91f3c0) (?) | no |
| `0x100000b6` | reader `0x956a30` / deliver 0x91f6e0 | (empty) | GM_UI group, empty (0x91f6e0) (?) | no |
| `0x100000ba` | reader `0x8c4960` / deliver 0x8bf180 | u64 \| u32 | GM_UI.RecvNotice_PauseDefeatStatusTimerForEntity (u64 iid, u32) | no |
| `0x10000076` | reader `0x8c4a00` / deliver 0x8bf4f0 | u32 | GM_UI.RecvNotice_TimerClockSync (u32) | no |
| `0x1000015a` | reader `0x8c47e0` / deliver 0x8bc9b0 | u32 \| u32 \| u8 | GM_Skill.RecvNotice_UpdateSkillUIOverlay (u32, u32, u8) | no |
| `0x10000414` | reader `0x95b140` / deliver 0x9220f0 | u64 \| u32 | Upgrade group: u64 + u32 (0x9220f0) (?) | no |
| `0x10000364` | reader `0x95b1f0` / deliver 0x9221b0 | u64 \| u32 \| u32 \| u8 | Upgrade group: u64 + u32 + u32 + u8 (0x9221b0) (?) | no |
| `0x100004d6` | reader `0x95f970` / deliver 0x923100 | u64 \| u32 | Floaty currency over an entity: `u64 entity \| f32 amount` (ics sends it with f32). *(probable)* — Upgrade group: u64 + u32 (0x923100) (?) | sent |
| `0x100002ec` | reader `0x8c2f70` / deliver 0x8aa720 | (empty) | GM_Character.RecvNotice_ClearAnnouncement (empty) | built, unused |
| `0x100002eb` | reader `0x8c2fa0` / deliver 0x8ab390 | StringInfo \| u32 \| u32 \| u32 \| u32 \| u32 \| u8 | GM_Character.RecvNotice_ShowAnnouncement (StringInfo text, u32 billboard type, u32 src icon, u32 tgt icon, i32 src team, i32 tgt team, u8) | built, unused |
| `0x1000021c` | reader `0x9326c0` / deliver 0x9121e0 | list<u64> \| list<u32> \| list<u32> \| StringInfo \| {u32 u32} \| {u32 u32} \| {u32 u32} \| {u32 u32} \| {u32 u32} \| list<u32> \| list<u32> \| list<u32> \| list<u32> \| list<u32> \| list<u32> \| list<u32> \| list<u32> \| list<u32> \| list<u32> \| list<u32> \| list<u32> \| list<u32> \| list<u32> \| list<u32> \| list<u32> \| list<u32> \| list<u32> \| list<u32> \| list<u32> \| list<u32> \| list<u32> \| list<u32> \| list<u32> \| list<u32> \| list<u32> \| list<u32> \| list<u32> \| {u32 StringInfo} \| {u32 StringInfo} \| {u32 StringInfo} \| {u32 StringInfo} \| {u32 u32} \| {u32 u32} \| list<u32> \| list<u32> \| u32 | Billboard/kill-feed style announcement: u64 list, two u32 lists, StringInfo, more (0x9121e0) (?) | no |
| `0x100002b2` | reader `0x933570` / deliver 0x912390 | u64 \| list<u64> \| list<u32> \| list<u32> \| StringInfo \| {u32 u32} \| {u32 u32} \| {u32 u32} \| {u32 u32} \| {u32 u32} \| list<u32> \| list<u32> \| list<u32> \| list<u32> \| list<u32> \| list<u32> \| list<u32> \| list<u32> \| list<u32> \| list<u32> \| list<u32> \| list<u32> \| list<u32> \| list<u32> \| list<u32> \| list<u32> \| list<u32> \| list<u32> \| list<u32> \| list<u32> \| list<u32> \| list<u32> \| list<u32> \| list<u32> \| list<u32> \| list<u32> \| list<u32> \| list<u32> \| {u32 StringInfo} \| {u32 StringInfo} \| {u32 StringInfo} \| {u32 StringInfo} \| {u32 u32} \| {u32 u32} \| list<u32> \| list<u32> \| u32 | Same as 0x1000021C with a leading u64 (0x912390) (?) | no |
| `0x100002bc` | reader `0x8c3130` / deliver 0x8ab800 | (empty) | GM_Character.RecvNotice_StopProcessingNewBillboards (empty) | no |
| `0x10000424` | reader `0x941390` / deliver 0x916450 | {Handle{u32,u64} u32 u32 u32 u8 u32 u64 u8 {u32 {StringInfo StringInfo u32}}} \| u64 | AddTimelineBanner; needs 0x100002AF + 0x100002B1 first. *(confirmed by the old server's notes)* — AddTimelineBanner (Encounter group): banner desc + f64 | built, unused |
| `0x100002ab` | reader `0x941430` / deliver 0x916520 | {Handle{u32,u64} u32 u32 u32 u8 u32 u64 u8 {u32 {StringInfo StringInfo u32}}} \| {u32 {Handle{u32,u64} u32 u32 u32 u64}} \| u64 | Timeline banner variant (banner desc + list + f64) (?) | no |
| `0x100002ae` | reader `0x941520` / deliver 0x9165f0 | {u32 {Handle{u32,u64} u32 u32 u32 u8 u32 u64 u8 {u32 {StringInfo StringInfo u32}}}} \| {u32 {Handle{u32,u64} u32 u32 u32 u64}} \| u64 | Timeline banners list (u32 n x desc) + list + f64 (?) | no |
| `0x100002af` | reader `0x941620` / deliver 0x9166c0 | u64 | Timeline banners on; send after client notice 0x100002AD (UI_ReadyForTimelineData). *(probable)* — Timeline banners on (u64 iid) | built, unused |
| `0x100002ac` | reader `0x941690` / deliver 0x916780 | Handle{u32,u64} | Timeline banner remove by handle {u32,u64} (?) | no |
| `0x100002b1` | reader `0x9416e0` / deliver 0x916840 | u64 | Timeline banners on (2); send after client notice 0x100002AD. *(probable)* — Timeline banners on, 2 (u64 iid) | built, unused |
| `0x1000000e` | reader `0x941750` / deliver 0x916900 | u32 \| u32 \| u32 \| u32 \| u32 | GM_Encounter.RecvNotice_NotifyMatchEnded (u32 winning team, u32 player team, f32 seconds, u32 tier, f32 target time) | sent |
| `0x100000ca` | reader `0x9419a0` / deliver 0x916ec0 | u64 \| u64 | Encounter group: u64 + u64 (0x916ec0) (?) - probable kill/assist (killer, victim) | no |
| `0x100000cd` | reader `0x941a50` / deliver 0x916f80 | u64 \| u64 | Encounter group: u64 + u64 (0x916f80) (?) | no |
| `0x10000205` | reader `0x941b70` / deliver 0x9170d0 | (empty) | Encounter group, empty (0x9170d0) (?) | no |
| `0x10000109` | reader `0x941d60` / deliver 0x9173c0 | u64 \| u64 \| u8 | SetMatchTime (f64, f64, u8); natural answer to client notice 0x100000D2 (match HUD ready). *(probable)* — GM_Encounter.RecvNotice_SetMatchTime (f64 start?, f64, u8) | no |
| `0x10000456` | reader `0x941e60` / deliver 0x9177a0 | (empty) | Surrender vote concluded. *(probable)* — GM_Encounter.RecvNotice_SurrenderVoteConcluded (empty) | no |
| `0x100004fb` | reader `0x90b230` / deliver 0x8e1e80 | list<u32> \| list<u32> \| list<u32> | GM_Encounter.RecvNotice_UI_InitialTeamHealthUpdate (3 u32 lists) | no |
| `0x100000cb` | reader `0x8c3d00` / deliver 0x8b4560 | u64 \| u64 \| StringInfo \| u32 \| u32 | GM_Encounter.RecvNotice_UI_PlayerJoined (u64, u64, StringInfo name, u32, u32) | no |
| `0x100000ce` | reader `0x8c3e30` / deliver 0x8b4990 | u64 \| u64 \| StringInfo \| u32 \| u32 | GM_Encounter.RecvNotice_UI_PlayerLeft (u64, u64, StringInfo, u32, u32) | no |
| `0x10000134` | reader `0x90b320` / deliver 0x8e9a10 | list<u32> \| list<u32> | Answer to client notice 0x10000137 (RequestCurrentTeamHealth). *(probable)* — GM_Encounter.RecvNotice_UI_UpdateTeamHealth (2 u32 lists) | no |
| `0x1000005b` | reader `0x942a80` / deliver 0x917d90 | {u32 {StringInfo u64 u64 u64 u32 u32 u32 u32 u32 u32 u32 u8}} | Encounter group: list of {StringInfo, 3 u64, 7 u32, u8} (0x917d90) (?) - scoreboard rows? | no |
| `0x10000455` | reader `0x90b3d0` / deliver 0x8ea0b0 | {u32 u8} \| u32 \| u8 \| u32 \| u32 | Surrender vote state; client votes with notice 0x10000454. *(probable)* — GM_Encounter.RecvNotice_UpdateSurrenderData ({u32,u8}, u32, u8, u32, u32) | no |

Local-only notices (420, reader stub `0x11893c0`) are listed by registering function in
`protocol-server-to-client.md` §6; sending them does nothing.

---------------------------------------------------------------------------------------------------------------------

## 4. Priority table for the server

### 4.1 Needed for a working match

| step | client sends | server sends | ics today |
|---|---|---|---|
| connection | 0x10000, 0x20000, 0x80000, 0x1000000/0x2000000 (10 s), 0x8000 | 0x40000 welcome (both), 0x100 ServerSwitch, 0x800 referral, 0x1000000 every 2 s | done |
| queue / accept | 0x20EB, 0x20CA, (0x20C3 leave) | 0x20C0, 0x20FA, 0x20AD, 0x2028, referral, (0x20E0) | done except 0x20C3 → 0x20E0 |
| lobby / loading | 0x20F2, 0x2102, 0x20D5, 0xCC | 0x2029, 0x204C, 0x2016, 0x206D, 0x2031, 0x20AF | done |
| world entry | 0x211B, 0x207A, 0x20D3, notices 0x10000207 / 0x10000204 / 0x1000015E, 0x212C | 0xEB, 0x4 (0xF2 / 0xB0 / 0xBC), 0x42, 0x2078, 0x20E2 | done (the client events need no answer) |
| play | 0x20EE, 0x2136, 0x20AB, 0x208B / 0x20A7, 0xDA, 0x2139 / 0x213A, 0x2138, 0x20D1, 0x2170 | 0x8D, 0x42, 0x20F8, 0x3, 0x2086, 0x20E2, 0x6 / 0x86 (single properties), effects 0x200C…, status icons 0x20A2…, cast bars 0x2077…, 0x20A0 | 0xDA (→ 0x8D) and 0x2138 not handled; property / effect / status / usage groups not used yet |
| match HUD | notices 0x100000D2, 0x100002AD, 0x10000137, 0x10000454 | 0x10000109 SetMatchTime, 0x100002AF/2B1/424, 0x10000134 / 0x100004FB, 0x10000455/456, 0x10000090 / 0x100000BC | defeat timers only |
| scripted flow | 0x10000117 | 0x20F5, 0x2001, 0x2034 / 0x2009, 0x213D, 0x1000027F, 0x2150 | done (0x2150 unused) |
| match end | 0x12D, 0x20BA, 0x20C4 | notice 0x1000000E, 0x2038, 0x2045, 0x214B, 0x2021 | 0x1000000E only (rest built or old server) |

### 4.2 Menus (account, rewards, achievements, lobby options)

Client: 0x216E, 0x212E, 0x211D, 0x211E, 0x2124, 0x2128, 0x2116, 0x21A4, 0x2178, 0x2193, 0x21A5, 0x2093, 0x20FC,
0x2106, 0x2099, 0x20DF, 0x20E4, 0x2160, 0x21A8, Lobby listener 0x200A … 0x214E, lobby client object 0x20C4 …
0x2156. Server: 0xCE, 0x20B8, 0x20ED, 0x209D, 0x2024, 0x216A, 0x2120, 0x218B, 0x215D, 0x2080, 0x2081, 0x2104,
0x20B9, 0x2188, 0x2190, 0x2154, 0x219E, 0x219F, 0x211F, 0x2125, 0x2115, 0x21A2/3, 0x2090, 0x20C7, 0x2052, 0x2107,
0x2186, 0x2197, 0x219D, 0x2101, 0x218D, 0x218E, 0x218F, 0x20D7, 0x20F3, 0x210B, 0x20E0, contextual store 0x210C/D/F.
**Quick wins:** answer 0x212E with 0x211F and 0x2124 with 0x2125 in ics (the old server already does), and 0x20C3
with 0x20E0.

### 4.3 Social

Client: CustomMatch 0x20C1 … 0x200B, chat 0x20A6, 0x20F6, 0x20CD, 0x2112, 0x20E5, 0x2148, 0x210E, 0x2110, 0x2111.
Server: contacts 0x2003 … 0x219C, custom match 0x2011 … 0x217C, grouping 0x2033, 0x2070, 0x2071, 0x214C, 0x217D,
chat 0x20B0, 0x20B6, 0x2134, 0x2135, 0x2183. None needed for single-player.

### 4.4 Telemetry (accept and ignore)

Client: 0x20D4, 0x20E3, 0x20BE, 0x20B4, 0x214F, 0x218C, 0xDC (only after S→C 0xA8), connection 0x2000000;
SOAP Metrics POST; UDP log datagrams. Server: 0xA8 (optional).
