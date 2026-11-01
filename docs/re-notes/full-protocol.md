# Full network protocol of the client (decompilation pass, 2026-10-22)

The single reference for what `InfiniteCrisis.exe` (image base 0x400000, **every address is a VA**) puts on and
takes off the wire. It builds on `protocol-complete.md` (which keeps the long per-event rows and the 2026-10-21
traffic evidence) and adds what the full Ghidra decompilation (`re-work\decomp`) made possible: a byte-exact count
of every event class, the Flash-notice → C++ listener → network-event map for the menu systems, the source of the
lobby/draft notices the UI note could not place, and the message sequences of every out-of-match flow.

**Machine-readable table:** `docs/re-notes/full-protocol.tsv`, one row per id (505 rows: 441 events, 52 notices,
12 connection packets). Columns: `id, kind, direction, name, fields, handler_va, status, confidence, route,
reply_or_server_action, category, constructor_va`. `direction` = C2S / S2C / both / local. `status` = what `ics`
does today. `fields` is the wire layout (S→C: with the leading u8 base byte; C→S: packed, no base byte).

**Confidence.** **C** = confirmed by code (a reader/serializer, a dispatcher slot, a call chain) or by the logs;
**P** = probable (structural inference, consistent naming, expected reply); **G** = guess / structure only
(rows whose meaning still carries "(?)"). In the TSV: 306 events C, 15 P, 120 G.

---------------------------------------------------------------------------------------------------------------------

## 1. What exists, counted (not sampled) [C]

| item | count | how it was counted |
|---|---|---|
| event-class constructions | **484** | byte scan of `.text` for `C7 4x 0C 00 04 30 00` (`mov [r+0xC], 0x300400`) with the `mov [r+8], id` beside it |
| distinct event ids | **441** | 438 from the scan + `0x1`, `0x10F`, `0xA7` (their 3 constructions at `0x5382b4`, `0x538314`, `0x691a2f` set the id elsewhere) |
| receivable (S→C) events | 336 | calls of the factory registry `0xb0ec50` (285 with a literal id in the decompilation; the other 51 come from template registrars, listed in `protocol-complete.md` §3.3) |
| client-sent events | 100 C2S + 8 both | calls of the send helper `0x444a90` (161 sites) + 2 in-place builders (`0x20EE` at `0x88b030`, `0x20B4` at `0x888820`) |
| local-only events | 31 | object-service events whose serializer refuses packed streams (§2.4) + `0x87` |
| dead event | `0x87` | constructed only by `0x64a660` (vtable `0x15cdb04`, exec `0x5d9ff0` = the batch executor, caller `0x64ab70`); never registered, never sent |
| notices with a network reader (S→C, inside event 0x2) | 44 | calls of `0x483240` with a real reader (464 calls; 420 use the stub reader `0x11893c0`) |
| notices the client sends (inside event 0x2) | 8 | all calls of the network notice constructor `0x481e70` |
| connection packets | 12 | calls of the packet registry `0xb03a80` (from `0xb0acc0`) |
| Flash notice ids | 730 | `event_gen\*NoticeIDList.as` getters; 464 of them have a C++ "raise" function (`0x4820f0` callers, one per notice, each calling one listener-interface slot) |

Distribution of the 441 events by direction and system (exact lists in the TSV):

| dir | system / route | n | ids (hex) |
|---|---|---|---|
| C2S | lobby/account service `0x0600000000000401` (user connection) | 76 | 200A 200B 200D 2017 201E 2025 2026 202D 2057 205A 2064 2066 206A 207D 2089 208E 2093 2094 2098 2099 20A1 20A6 20B4 20BA 20BE 20BF 20C1 20C3 20C4 20C6 20CA 20CD 20D4 20D5 20D6 20DF 20E3 20E4 20E5 20E6 20EB 20F1 20F2 20F4 20F6 20FB 20FC 20FD 2102 2106 2108 210E 2110 2111 2112 2116 211D 211E 2124 2128 212E 2148 214E 214F 2156 2160 216E 2178 218C 2193 2199 219A 219B 21A4 21A5 21A8 |
| C2S | world service 0x400 → world route `0x0600000000000008` (game connection) | 23 | 95 DA DC 12D 201A 207A 208B 2097 20A7 20AB 20D1 20D3 20EA 20EE 211B 212C 2136 2138 2139 213A 2140 214D 2170 |
| C2S | service 0x402 | 1 | CC |
| both | object IID (notices, script → entity messages, object events) | 8 | 2 98 9D 9F A3 D2 EA 112 |
| S2C | engine (objects, properties, movement, messages, login) | 70 | see TSV, routes `engine: *` |
| S2C | Contacts 21, Lobby 20, Skill HUD 19, CustomMatch 18, Effects 17, Matchmaking 17, Encounter 16, Character 16, Player-object 11, StatusIcon 10, Usage 8, Dialog 6, Upgrade 6, Grouping 5, Chat 5, Amplifier 4, MapManager 8, Floaty 3, GM_UI 3, Agent 3, Contextual 3, Achievement 3, Account settings 3, Cinematic 2, Training 2, LoginReward 2, Vitals 1, Connection 1, ViewMatch 1, svc 0x20DE 1 | 266 | see TSV |
| local | object services | 31 | 82 87 8C 8F 91 97 9B AD C0 C1 CA D0 D1 E4 E6 F3 FA FD 103 10B 111 113 11A 11B 11F 121 127 12B 12C 133 134 |

---------------------------------------------------------------------------------------------------------------------

## 2. Connection layer

### 2.1 Transports [C]

| channel | what | evidence |
|---|---|---|
| HTTP SOAP (`/WebLoginApp-1.3/…`) | login web service: `Metrics` (form post, `event_type=GameClientStart`, MAC as `pcid`), `AuthenticateWS` → `AuthSelect{userName,password,region,language,steamid}` → `AuthSelectResponse{loginTicket, randomID, sessionKey, userServerAddr, userServerPort}` (`errorString` must be absent on success); `getLauncherData` only from the launcher | 2026-10-21 run, ics SOAP stub |
| TCP **user connection** | to `userServerAddr:userServerPort`; account, menus, queue, lobby (service 0x401) | logs |
| TCP **game connection** | to the host/port of the Referral packet (0x800); world service 0x400 / 0x402 and object traffic | logs |
| UDP | log datagrams from the client to the user port (ignored) | ics `_udp_log` |

### 2.2 Frames [C]

Every TCP read is a run of `u32 length (LE) | payload`. Frame parser `0xb0af10` (called with the header byte):

| header bit | meaning |
|---|---|
| `0x01` | **packet block**: `u32 mask` then one sub-packet per set bit in ascending order (reader per bit, §2.3). The parser bails if `mask & 0xFFFFFF00 == 0` (`0xb0af10`, the low byte is not a packet bit) |
| `0x02` | **message**: `u64 destination | u8 flags | compact event id | body`. Built into a `0xb048f0` message object (size 0x58: dest at +0x10, flags at +0x30, id at +0x2C) |
| `0x04` | with 0x02: keep a reference to the receive buffer instead of copying (`0xb0b10d` path); no wire change [P] |

Flags byte: the client sends `0x01`; the server sends `0x02`, which lets the message through the client's
delivery gate `0xfe1b50` while it is still loading. Compact ints: `<0x80` 1 byte; `<0x4000` `0x80|hi, lo`;
`<0x20000000` `0xC0|b3, b2, u16 LE`; else `0xE0 u32` (`0x421430`; ics `wire.pack_compact`).

**No encryption, no compression, no application acks.** The connect request carries an RSA-encrypted 3DES session
key, but nothing in the receive path decrypts frames and `ics` works in plaintext end to end [C by behaviour]. The only
error string of the transport is `E_TCPFRONTEND_BADPACKET 0x81950002` "Unable to decrypt, decompress, and/or split a
packet" (registered by `0xb059c0`, the IOCP front end) — inherited from the shared Turbine network library, unused
here [P]. Reliability is TCP's: there is no per-message sequence or ack; the only sequence number is the u32 of
ServerSwitch (0x100).

### 2.3 Connection packets (12) [C layout; meaning as marked]

| mask | reader | layout | dir | role |
|---|---|---|---|---|
| `0x100` | `0xb0a010` | `u32 sequence` | S→C | **ServerSwitch**: makes the game connection current; without it the game connection is dropped when match data loads [C] |
| `0x800` | `0xb090d0` | `u64 cookie, u16, u8 flags, u8, u16 port, char[256] host` | S→C | **Referral** to the game server (after AcceptMatch) [C] |
| `0x8000` | `0xfe2610` | empty | C→S | **disconnect**, sent when the client quits [C wire / P meaning] |
| `0x10000` | `0xb08570` | `str8 version ("141112_netver:7948") | u32 n | blob` (blob: `u32 0x2711 | u32 1 | u32 nonce | str8 "3des" | u32 128 | RSA(3DES key) | u32 0x18 | u32 0x10 | 16 bytes`) | C→S | **connect request**, first frame on the user connection [C layout] |
| `0x20000` | `0xb05bd0` | `u64` (referral cookie echoed) | C→S | first frame on the game connection [C wire / P meaning] |
| `0x40000` | `0xb05070` | `16 bytes route id | BE f64 server time | 8 bytes | u32 | BE u32 | BE u32 connection id` | S→C | **welcome** on both connections; handled by the user/game connection class `0xfe4950` [C] |
| `0x80000` | `0xb09040` | `GUID | u64` | C→S | after 0x20000 on the game connection [C wire / meaning unknown] |
| `0x100000` | `0xb08fb0` | `u32 | u32` | – | never seen |
| `0x200000` | `0xb09170` | `u32 | u32` | – | never seen |
| `0x1000000` | `0xb04af0` | `BE f64 time` | both | **time sync / keepalive**: client every 10 s on each connection; server must send it on the game connection (ics: every 2 s) or the client drops it after 60 s [C] |
| `0x2000000` | `0xb04db0` | `BE u32` | C→S | millisecond counter sent with each time packet (ping) [C wire / P meaning] |
| `0x4000000` | `0xb04f40` | `u32 | u32` | – | base handler slot +0x30; probably the ping echo [P] |

Base connection dispatcher `0xb03cc0` handles 0x1000000 / 0x2000000 / 0x4000000 (vt +0x28/+0x2C/+0x30); the user/game
connection class handles welcome `0xfe4950`, ServerSwitch `0xfe2080`, Referral `0x6a8890 → 0xfe3240`.

### 2.4 Bodies, routes, batching [C]

- **S→C bodies** start with the u8 base byte (`0xb0d380`, value 0); sub-events of batch 0x4 and notice blobs are packed
  (no base byte). **C→S bodies** are written packed (stream flag 0x800): no base byte, and some u32 fields shrink
  (scriptlet run flags in 0xDA).
- **Batching.** S→C event **0x4** = `cint n | n × (cint id | u32 len | body)`, executed by `0x5d9ff0` (object creation
  and updates; the 0xF2 descriptor). The client never batches. A frame may carry a packet block and a message together
  (header 0x03; parser allows it, never seen).
- **Routes.** Sender pattern (every C→S event): `if ([0x1b6ab18]+0x1D8 == 0) return E_FAIL` → route `{0, service from
  table 0x1854460 (0x400 world, 0x401 lobby/account, 0x402) with high dword 0x06000000 (0x185446c)} + mode word (1/2)`
  → `0x444a90` → router `[0x1ba1288]` vt+0x18. On the wire: `0x0600000000000401` (user connection),
  `0x0600000000000008` (world route, game connection), `0x0600000000000402` (0xCC only) or an object IID.
- **Object-service events refuse packed streams** (error `0x81960005`): 0x82 0x8C 0x8F 0x91 0x97 0x9B 0xAD 0xC0 0xC1 0xCA
  0xD0 0xD1 0xE4 0xE6 0xF3 0xFA 0xFD 0x103 0x10B 0x111 0x113 0x11A 0x11B 0x11F 0x121 0x127 0x12B 0x12C 0x133 0x134. They are
  posted through the same helper but only ever delivered locally (client-side object services). The S→C ones among them
  are registered and can be sent by the server (TSV direction `local` keeps their S→C layout).

### 2.5 Keepalive, timeouts and disconnects

| event | effect | conf |
|---|---|---|
| no 0x1000000 from the server for 60 s | client drops the **game** connection | C (ics) |
| S→C 0x2016 (u32) | lobby "end room check": hides the back button and arms a 60 s watchdog | C |
| C→S 0x8000 | client quit | C |
| S→C 0x2021 (u32) | exit lobby / leave world (`ExitingWorld`, `GameFrontUIDestroyedInCPP`) | C |
| S→C 0x210B (empty) | queue/match error → removed from queue + dialog | C |
| S→C 0x20D7 (u32) / 0x218D (u32, StringInfo) / 0x20F3 (u32) | pending-match failure / find-match failure / barred from matching | C |
| S→C 0xCF (u32) / 0x105 (u32, StringInfo) | login/character result code / error text (handlers `0x6a8330`, `0x6a8130`) | P |
| server closes the socket | client shows the disconnect dialog (`gameplay.disconnect`) | C (observed) |

---------------------------------------------------------------------------------------------------------------------

## 3. Events

The full per-id layouts (field by field, from each serializer/reader) are in the TSV and, with commentary, in
`protocol-complete.md` §2.2 (C→S), §3.3 (S→C), §2.3 / §3.4 (notices). This section only lists what this pass added or
corrected.

### 3.1 Flash request → C++ listener → network event (C→S side of the menus)

Method [C]: each Flash notice id has one C++ raise function (calls `0x4820f0(registry, id)` and then
`listener->vtbl[slot]`); the slot is read from the raise function, and the handler is the listener-interface vtable entry
at that slot. Listener vtables used: UI `0x1602a80` (75 slots), Lobby `0x1604b84`, CustomMatch `0x1602f04`, Character
`0x1604af8`, Achievement `0x1604498`, Upgrade `0x1605ae0`, Encounter (mission events) `0x16031d8` (38 slots). The
stub `0x132c5c0` / `0xab4d80` / `0xab4b40` / `0x7b0350` entries mean "this listener ignores the notice".

| Flash notice (slot) | handler | network | conf |
|---|---|---|---|
| UI AcceptMatch (0x0) | `0xa0da60` | **0x20CA** | C |
| UI DisplayPendingDodgePenaltyNotifications (0x20) | `0xa0db10` | **0x21A8** | C |
| UI JoinQueue (0xA4) / JoinQueueForPromotedMap (0xA8) | `0xa31330` / `0xa312d0` | **0x20EB** | C |
| UI LeaveQueue (0xAC) | `0xa0da40` | **0x20C3** | C |
| UI RequestLeaderboards (0xE0) | `0xa7bfa0` | **0x21A4** | C |
| UI RequestAccountStandingsData (0xC8) / RequestStaticStandingsData (0xEC) | `0xa15540` sets `[this+0x11]` / `0xa15520` sets `[this+0x100]` | none directly: they set a "pending" flag; a throttled tick sends the request (0x2178 / 0x2193 senders `0x887d30`, `0x887f80`) | P |
| UI PlayerAcknowledgedStandingsChange (0xC0) | `0xa313b0` | local (copies the standings arrays) | C |
| Lobby AttemptToRejoinLobbyRoom (0x0) | `0xa77020` | none found | P |
| Lobby **Draft_RequestTrade (0x4)** | `0xa0c410` (skips a trade with oneself) | **0x2026** `u64 player, u32` | C (corrects "rejoin lobby room") |
| Lobby **Draft_TradeResponse (0x8)** | `0xa0c2f0` | **0x205A** empty | C (was "slot 8 unknown") |
| Lobby ExitLobbyToMainMenu … TriggerWaitAfterReadyFlag | – | 0x200A, 0x202D, 0x206A, 0x201E, 0x200D, 0x2025, 0x2057, 0x2064, 0x2102, 0x2108, 0x214E | C (unchanged) |
| Lobby **PlayerChangedCharacterLockStatus (0x14)** | stub | **none — local only** (the lock button is client-side; the server only learns the pick from 0x2102) | C |
| Lobby **RequestChangeStolenPower (0x24)** | `0xa0c7d0` (a 2-line identical-code-folded body: writes a bool) | **none** | C |
| Lobby RequestToPurchaseVariant (0x3C) | `0xa71e60` | none found | P |
| CustomMatch Create … SetDraftMode | – | 0x20C1, 0x2094, 0x20E6, 0x2199/0x219A, 0x20A1, 0x20C6, 0x219B, 0x20F4, 0x2066, 0x200B | C (unchanged) |
| CustomMatch AssignTeam (0x0), ChangeCoordinator (0x8), GivePerm (0x14), Invite (0x18) | `0xa57d10`, `0xa35790`, `0xa0c200`, `0xa64d30` | none reached (no sender within 4 calls) | P |
| CustomMatch Cancel (0x4) | stub | none | C |
| CustomMatch SetEncounter (0x40), SetTeamNames (0x44) | beyond this listener's 16 slots | not handled by this listener | C |
| Character RequestAccountEncounterStats (0x38) | `0xa57170` | **0x2116** | C |
| Character UI_ClaimPostMatchReward (0x68) | `0xa411d0` | **0x2128** | C |
| Character UI_RequestPendingRewardUpdateFromServer (0x78) | `0xa0b3e0` | **0x2124** | C |
| Character UI_SetProtectorIcon (0x7C) | `0xa2fbc0` | **0x2093** | C |
| Character RequestAccountCurrencyBalance(+Changes), RequestAccountEndOfMatchSoftCurrencyReward, Ribbon_ReceivedItemsFulfilled, UI_RequestPendingPostMatchRewards | `0xa12ed0`, `0xa12f00`, `0xa1aa40`, `0xa63050`, `0xa57300` | none: answered from the cache filled by 0x2081 / 0x20B9 / 0x2095 / 0x2125 | P |
| Character RequestAccountCharacterData, RequestAccountLevelAndXP, RequestPostMatchChanges, End-of-match XP/accolades, UI_RequestBestAccolades | stubs in this listener | none (0x20BA is sent by `0xa2fc80` on its own, not by this notice) | C |
| Achievement **AcknowledgeAchievementDisplayed (0x4)** | `0xa63070` | **0x211E** `u32 achievement` | C (resolves ui-complete "0x211E?") |
| Achievement RequestAllAchievementData (0x10) | `0xa434f0` | **0x211D**, and locally `0xa428b0` → `SetAchievementData` | C |
| Achievement RequestAllPendingRewardlessAchievementNotifications (0x14) | `0xa34900` | **0x212E** (reply 0x211F → `AllPendingAchivementBanners` via `0xa347e0`) | C |
| Achievement **RequestTraineeAchievements (0x18)** | `0xa63200` → `0xa43530` → `TraineeAchievements` | **none: built locally** from the achievement records + 0x2120 progress | C |
| Achievement RequestAchievementDetails (0xC) | `0xa42cf0` | none: built locally | C |
| Upgrade PurchaseUpgrade (0x44) / SellUpgrade (0x5C) | `0xa17ce0` / `0xa17d90` | **0x208B / 0x20A7** | C |
| Upgrade ChangeArtifactSkillSlotMapping (0x4) | `0xa5ea70` | **0x212C** | C |
| Upgrade RequestAllAvailableUpgrades, RequestArtifactSkillSlotMapping, RequestCurrentUpgrades, RequestSendEveryonesUpgrades, RequestUpgradeArrayPreview, ShowCurrencyCollectionRings, Tutorial_ArtifactFoundryOpened/Closed | `0xa318a0`, `0xa0f4b0`, `0xa5ea00`, `0xa5ea10`, `0xa5e6c0`, `0xa518e0`, `0xa2ac70`, `0xa2acd0` | none (local) | C |
| Encounter **UI_Mission_RaiseEvent (0x88)** | listener `0x16031d8` slot 34 = `0xa29440` → `0xa29380`: builds engine notice **0x100000D3** with the `eClientMissionEvent` value (`0x460bb0`) and posts it to the local mission object (`0x461430`) | **none on the wire** (0x100000D3 has no network reader and is not one of the 8 notices the client sends) | C |

### 3.2 Where the "unknown network source" UI notices come from (ui-complete §6 / §9)

| UI notice | source | conf |
|---|---|---|
| `Lobby.Draft_Selecting`, `Draft_Banning`, `Draft_EnableTrade`, `Draft_PlayersTrading` | raised by the lobby-state applier `0xab98c0`, called from the handlers of **S→C 0x2029** (single slot, `0xabd0a0`, exec `0x8b9150`) and **0x2060** (full state, `0xabe1b0`, exec `0x8b9060`) — the draft phase is part of the lobby state | C |
| `Lobby.Draft_TradeRequest` | **S→C 0x2054** handler `0xab7c10` (exec `0x8b8870`) | C |
| `Lobby.PreGameTips` | `0xaba430` builds the list locally from game-data records (`0x439e00` record lookups 0x10000018 / 0x10000022, type 0x15) after `RequestAllPregameTips`; C→S 0x201E is also sent | P |
| `Encounter.UI_UpdateMatchScorecard`, `ViewMatch.ViewMatchScoreboardData` | `0xa4a4f0` / `0xac49a0`, both called from `0xa901f0`, the encounter UI object's update: built **locally** from the replicated player entities (kills/deaths/assists/money are entity properties). No network event | P |
| `Achievement.TraineeAchievements`, `SetAchievementData` | local (§3.1) | C |
| `LoginReward.UI_DeliverLoginRewardSet` | `0x8f2db0` ← `0xa5aaa0` (a listener slot reading cached reward-set data, i.e. what 0x2197 delivered) | P |
| `Achievement.AllPendingAchivementBanners` | S→C **0x211F** (`0xa8b7f0` → `0xa347e0`) | C |

### 3.3 Still unmapped C→S (no network sender reached)

`GM_Contacts.*` (13 sends), `GM_Grouping.*` (7), `PlayerReport.ReportAPlayer`, `Contextual.UI_PurchaseContextualItem`,
`LoginReward.QueueLoginReward` / `ReadyForLoginRewardSet`, `Encounter.RequestMatchScorecard`. Their listeners call
through manager objects (`[this+0x38]` vt+0xAC/+0xB0, `[this+0x40]`) whose class could not be fixed statically; the
listener vtables could not be located because this build has no RTTI for game classes and its vtables are packed with
no separators. Candidates among the unexplained senders: **0x2112** `wstr, wstr, u64, QueueKey, wstr, u32, wstr, u32`
(sender `0x888210` ← `0xa22ce0`, which reads the account name and the queue key: a **group invite with the cached
queue** — Grouping SendGroupInvite + CacheQueueForGrouping) [P]; **0x20E5** `QueueKey, u32, wstr` (`0x888dd0` ← `0xa0d2a0`,
`0xa227c0`) [G]; **0x2148** `wstr` (≥ 2 chars, throttled, `0xac05e0`) [G]; **0x20CD** `wstr target, wstr text` = chat
whisper (`0xa71b10` rejects names < 3 chars and the player's own name) [P]. Runtime test: `tools\diag.py` breakpoint on
`0x444a90` while using the friends panel.

### 3.4 Corrections to earlier notes

- `0x2026` is **Draft_RequestTrade**, not "rejoin lobby room"; `0x205A` is **Draft_TradeResponse** (Lobby listener slots
  4 and 8; raise functions `0x918610`, `0x9186a0`). Rejoin is S→C 0x205B only.
- `PlayerChangedCharacterLockStatus` and `RequestChangeStolenPower` have **no** network event (ui-complete §9.3).
- The trainee landing and achievement definitions are client-built (ui-complete §9.2): the server only sends 0x2120
  (progress) and 0x211F (banners).
- `UI_Mission_RaiseEvent` never reaches the server (ui-complete §9.9): tutorial scripts that wait on "foundry opened",
  "Stolen Power chosen" etc. are **client-side** mission scripts listening to notice 0x100000D3.
- Total distinct event ids is 441 (438 + 3), not 438.

---------------------------------------------------------------------------------------------------------------------

## 4. Flows as message sequences

`C:` = client → server, `S:` = server → client. user = user connection (service 0x401), game = game connection.
Everything not marked is [C] (logs of 2026-10-21 or a handler chain); [P] where noted.

### 4.1 Login and landing

```
HTTP  C: POST Metrics (GameClientStart)            S: empty envelope
HTTP  C: AuthenticateWS AuthSelect                 S: AuthSelectResponse {ticket, randomID, sessionKey, host, port}
user  C: pkt 0x10000 connect (version, RSA 3DES blob)
      S: pkt 0x40000 welcome
      S: 0xEB, 0x20B8 item statuses, 0x20ED champion data, 0x209D master character list, 0x2024 encounter list,
         0x216A server preferences, 0x2120 achievement progress, 0x218B account tables, 0x215D account flags,
         0xCE account character set, 0x2080 account level/XP  (0x2080 last: it opens the landing-screen gate)
      C: 0x20D4 u8, 0x20E3 machine info, 0x212E (-> S: 0x211F banners), 0x20C4, 0x216E × n preferences
      C: 0x21A5 only if 0x20ED had no champions (-> S: 0x20ED again)
      optional [P]: S: 0x2081 currency, 0x2190 header + protector icons, 0x2186 best accolades, 0x2197 or 0x219D login
         rewards, 0x2101 queue eligibility, 0x218F queue wait times, 0x218E matchmaking update interval
both  C/S: pkt 0x1000000 (+0x2000000 from the client) every 10 s
```

### 4.2 Queue, match found, accept (matchmaking) 

```
user  C: 0x20EB JoinQueue {QueueKey(encounter DID, queue flags), u8, u32}  (UI JoinQueue / JoinQueueForPromotedMap)
      S: 0x20C0 joined queue {QueueKey, u32, u32, u32}
      S: 0x218F wait times / 0x218E update interval (periodic, optional) [P]
      ... S: 0x20FA match found {u32, u32}                       (accept dialog + timer)
      C: 0x20CA AcceptMatch                                        S: 0x20AD players accepted {u32} (repeat per accept)
      S: 0x2028 lobby room created {QueueKey, StringInfo lists ...}
      S: pkt 0x800 Referral (game host/port/cookie)
   failure paths: C: 0x20C3 LeaveQueue -> S: 0x20E0 removed from queue [P reply]
                  S: 0x20D7 pending match failure {u32} (someone declined; back to queue)
                  S: 0x218D find match failure {u32, StringInfo}; S: 0x20F3 barred {u32}; S: 0x210B error
                  C: 0x21A8 (dodge-penalty notifications request, from the UI)
```

### 4.3 Game connection and lobby (champion select, blind pick)

```
game  C: pkt 0x20000 cookie                         S: pkt 0x40000 welcome, pkt 0x100 ServerSwitch
user  S: 0x20AF enter match {u32, list, list, u32}, 0x2016 end-room check
game  C: pkt 0x80000
user  C: 0x20BA, 0x20F2 ConnectToLobby {u64 account, u32 character DID, u8, u8 view-match, list<u32> settings}
      S: 0x204C lobby state (LobbyEncounterDetails: teams, players per team, encounter, draft?, ranked?, custom?, ...)
      S: 0x2060 full lobby state (all slots)  or  0x2029 one slot per player
      S: 0x2016, 0x206D (all loaded / hide back button)
      C: 0x202D LobbyUIReady {QueueKey}; 0x2025 RequestCharacterPickerInformation {u64}; 0x201E RequestAllPregameTips
      C: 0x2057 RequestMyAmplifierSet -> S: 0x2090 / 0x20C7;  C: 0x2064 RequestMyStolenPowers -> S: 0x2004
      C: 0x2102 SelectCharacter {u32 variant DID, u8}  -> S: 0x2029 (slot of that player, everyone)  | 0x2005 lock failed
      C: 0x200D RequestChangeAmplifierSet {u8}         -> S: 0x204A player picked amplifier set
      (Stolen Power change and lock button: local only, §3.1)
      S: 0x204B match launch warning {u64, u64, u32};  S: 0x2061 early-launch time {u64, u64, u32}
      C: 0x206A PlayerSelectedEarlyLaunch {u64, u32, u8} -> S: 0x206C (StringInfo, u32)
      C: 0x2108 TeamDisplayReady {u32}; 0x214E TriggerWaitAfterReadyFlag
      S: 0x2053 match started (UI state-machine event 0x14)
```

### 4.4 Draft (ranked-style pick/ban) [C for the routing, P for the order]

The draft has **no events of its own**: its phase, the current picker/banner and the trade window are fields of the
lobby state, and the client derives `Draft_Selecting`, `Draft_Banning`, `Draft_EnableTrade`, `Draft_PlayersTrading` from
every 0x2029 / 0x2060 it receives (`0xab98c0`). Picks and bans both go up as **0x2102 SelectCharacter** (ban vs pick is
decided by the phase in the lobby state) [P]. Trades:

```
C(A): 0x2026 Draft_RequestTrade {u64 player B, u32}
S(B): 0x2054 trade request {StringInfo, StringInfo}            -> B's UI raises Draft_TradeRequest
C(B): 0x205A Draft_TradeResponse                                 (empty body; how a refusal differs is unknown) [P]
S(all): 0x2029 / 0x2060 with the swapped picks (Draft_PlayersTrading cleared)
```

Custom matches switch the mode with C: 0x200B SetDraftMode {u32} → S: 0x2103 {u32, u8}.

### 4.5 Loading, match start, match end

```
game  C: 0xCC level loaded {u64 character}
user  C: 0x20D5 loading percent {u32} (repeated)   S: 0x2031 loading percents of everyone
game  C: 0x211B, 0x207A, 0x213A, notice 0x10000207, 0x20D3, 0x2139, notice 0x10000204, 0x212C, notice 0x1000015E
      S: world: 0xEB, batches 0x4 (0xF2 / 0xB0 / 0xBC), 0x42 vitals, 0x2078 recommended upgrades, 0x20E2 inventory
      C: notice 0x100000D2 (HUD ready)   -> S: notice 0x10000109 SetMatchTime   [P]
      C: notice 0x100002AD (timeline)    -> S: notices 0x100002AF, 0x100002B1, then 0x10000424 banners [P]
      ... play (protocol-complete.md §4.1) ...
end   S: notice 0x1000000E NotifyMatchEnded, 0x2038 match ended (UI event 0x12), 0x2045 end-of-match stats,
         0x214B completed encounters + last map
      C: 0x12D left the match world;  C: 0x20BE / 0x20B4 / 0x214F profiler telemetry (≈ 170 events)
      S: 0x2021 exit lobby/world
user  C: 0x20BA, 0x2124 -> S: 0x2125 pending reward sets; S: 0x2080 / 0x2104 / 0x20B9 / 0x2188 post-match deltas
      C: 0x2128 ClaimPostMatchReward {reward set, choice, source, instance, items, qty, bestowal}
      surrender: C: notice 0x10000454 {u8} -> S: notice 0x10000455 state, 0x10000456 concluded [P]
```

### 4.6 Custom match [C ids / P order]

```
C: 0x20C1 Create_CustomMatch {u64, wstr}          S: 0x2012 participant added (self) / 0x2042 creation failed
C: 0x2066 RequestCustomMatchData {u64}             S: 0x203F full custom-match data
invite: (GM_CustomMatch.Invite has no sender found)  S(invitee): 0x201F invited {StringInfo, u32}
C(invitee): 0x20E6 InviteResponse {wstr}           S: 0x202E invitation status {u64, wstr, u32}; 0x2012 / 0x2027
C: 0x219B MovePosition {list<u64>}                 S: 0x2048 moved {u64, u32}
C: 0x20F4 Randomize {u64, u64}                     S: 0x2076 assigned team {u64, u32}
C: 0x200B SetDraftMode {u32}                       S: 0x2103 {u32, u8};  S: 0x2109 set encounter; 0x2151 team name
C: 0x2199 / 0x219A Kick {wstr}                     S: 0x2041 kicked {u32}; 0x205D removed {u64}
C: 0x20C6 Leave {u64, wstr, u8}                    S: 0x203F / 0x205D
S: 0x2035 permission changed, 0x2036 coordinator changed, 0x217C protector icon, 0x2011 cancelled
C: 0x20A1 Launch {wstr} / 0x2094 ForceLaunch {wstr} S: 0x2040 launched -> then the lobby flow of 4.3 (0x2028 ...)
```

### 4.7 Ranked, standings, leaderboards [P]

Ranked is a queue (QueueKey flags) plus standings: C: 0x2178 → S: 0x219E (10 u32: account standings) and C: 0x2193 →
S: 0x219F (9 u32 lists + table + 5 u32: the static tier table), both throttled behind the UI's pending flags (§3.1);
S: 0x21A0 {u32, u32}; leaderboards C: 0x21A4 {u32} → S: 0x21A2 / 0x21A3 (`{n × (u64, wstr, 5 × u32)}, u32`).
UI PlayerAcknowledgedStandingsChange is local.

### 4.8 Party (grouping) and contacts [S→C C, C→S open]

S→C only is mapped: grouping 0x2033 show invite dialog {StringInfo}, 0x2070 can create group, 0x2071 player left
group (full group list), 0x214C invite cancelled, 0x217D protector icon; contacts 0x2003 … 0x219C (21 events: list,
added/removed, presence, notes, groups, invitations); chat 0x20B0, 0x20B6, 0x2134, 0x2135 member list, 0x2183. C→S
candidates in §3.3 (0x2112 group invite with cached queue [P]). Chat C→S: 0x20A6 channel list (joins "Team"/
"Wrapper"), 0x20F6 send text {StringInfo channel, wstr}, 0x20CD whisper.

### 4.9 View match (spectator) and rejoin

S: 0x206E view-match enable → client handler `0xab8e00` sends C: 0x20F2 with view-match byte 1 → S: lobby state as in
4.3 plus 0x206D (`UpdateLobbyLoadingPercentForViewmatch`) and 0x215C dampener counts. Rejoin: S: 0x205B {u32, u32}
(LobbyRejoinRoom) [C]; the Flash `AttemptToRejoinLobbyRoom` sends nothing [P].

---------------------------------------------------------------------------------------------------------------------

## 5. Gaps and next runtime tests

1. Social C→S (Contacts 13, Grouping 7, PlayerReport, Contextual purchase, LoginReward ready/queue, CustomMatch
   AssignTeam / ChangeCoordinator / GivePerm / Invite, RequestMatchScorecard): break on `0x444a90` with
   `tools\diag.py` and use each control once.
2. 120 S→C events are still structure-only (G): engine object-service family, movement 0x1 / 0x8A, agent 0x2022 /
   0x2074 / 0x2000003D, and the unnamed notices of the GM_UI / Upgrade / Encounter groups.
3. The connect blob's `0x2711`, nonce and trailing 24 bytes, and packets 0x80000 / 0x100000 / 0x200000 / 0x4000000.
4. Ban vs pick in draft: whether bans really use 0x2102 (watch a draft lobby state 0x2060 with the phase field).
5. The order of the flag-driven fields in 0xDA (0x04-0x40) and the 0x2009 flags → objective setters.

## 6. Method (reproducible, scripts not kept)

1. Split `re-work\decomp\c\*.c` on `// ==== <addr>` into functions; read `functions.tsv` for the call graph.
2. Map every `.data` dword whose value is a Flash notice id (from `event_gen`) to its `DAT_` address (8 715 hits:
   each translation unit has its own copy) and annotate the decompilation.
3. Raise functions = callers of `0x4820f0`; the slot is the `(*listener + slot)` offset in the body.
4. Listener vtables from `.rdata` (pefile); senders = functions that construct an event id and call `0x444a90`,
   plus the senders already tied in `protocol-complete.md`; reachability depth 4.
5. Event census: byte scan of `.text` (§1). Reverse search "who raises notice N": callers of the functions that
   reference N, up to 7 levels, stopping at a known S→C handler.
