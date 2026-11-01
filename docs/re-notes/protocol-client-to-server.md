# Client -> server protocol map (static analysis, 2026-10-21)

Everything the client (`InfiniteCrisis.exe`, image base 0x400000; all addresses are **VA**, rva = VA - 0x400000)
can send to the server, found by scanning the exe for event constructors and their send calls, then reading the
triggers in Ghidra (REA). Cross-checked with `logs/traffic.log` / `logs/unhandled.log` of the 2026-10-21 run.
Names marked *(probable)* come from slot matching against the Flash notice tables (see "Method") and are not proven.

## 1. How the client sends an event

- **Event object.** Every outgoing event is a heap object: base vtable `0x15a7da0`, `+8 = event id`,
  `+0xc = 0x300400`, then the event's own vtable. **Vtable slot 7 is the serializer** (one bidirectional
  `Serialize(archive)`: `archive+4 & 1` = writing; `0xafae80(n)` reserves n bytes; `0xb0d380` is the common
  header, which adds no visible bytes to the body the server logs). Strings are `compact length + chars`
  (ASCII for names, UTF-16 for text); lists are `u32 n + n items`.
- **Sender functions** (one per event, almost all in `0x882e00-0x88cb00`, a few at `0x8c3xxx-0x8d6xxx`):
  `if ([0x1b6ab18]+0x1d8 == 0) return E_FAIL` (no connection) -> build the route struct -> allocate + construct the
  event -> `0x444a90(hr, event, route)` -> router `[0x1ba1288]->vfunc+0x18`.
- **Route / destination.** The route struct holds a service id read from the table at `0x1854460`
  (`0x0600000000000400 + k`) and a mode word (`1` or `2`, probably reliable vs. sequenced channel):

  | Service constant | Connection it leaves on | `dest` the server sees |
  |---|---|---|
  | `0x...400` (world) | game | `0x0600000000000008` (the 0x400 placeholder is replaced by the world route) |
  | `0x...401` (lobby / account) | user (lobby) | `0x0600000000000401` |
  | `0x...402` | game | `0x0600000000000402` (only `0xCC`) |
  | object id (`obj+0x100/0x104`) | game | e.g. `0x0200000000000001` (local player) for every notice `0x2` |

- **Rate limiters.** Many UI-originated senders first call a token-bucket check with cost `1.0f`
  (`0xa2c0b0`, `0xa2c300`, `0xa2c550`, `0xa2cc40`, `0xa2ce80`, `0xa2d0c0`, `0xa2d310`, `0xa2d550`, `0xab6ad0`,
  `0xabff10`); when it refuses, nothing is sent (some show a "slow down" message `0x88de80`).
- **Notices (event `0x2`).** Constructor `0x481e70`, serializer `0x481f20`: `u32 notice id | u32 args length |
  args bytes` (args written with the same archive, `0x444600`). Only 8 functions send them (section 3).

## 2. Event table

Columns: **kind** = (L) lobby/account, (W) world/match, (S) system/telemetry, (O) object/script level.
**ctor / ser** = event constructor VA / serializer VA; **sender** = the function that sends it; **trigger** = its
callers. **ics** = handled by `ics/session.py` HANDLERS (old = only the legacy `icserver`).

### 2a. Events named in the task

| id | kind | dest | ctor / ser | sender | body | trigger (VA) | expected server reply | ics |
|---|---|---|---|---|---|---|---|---|
| `0x20EB` | L | 401 | `0x87a860` / `0x840120` | `0x889f50` | `u32 encounter | u32 queue flags | u8 | u32` (log: did, `0x200000`, 1, `[0x186cdf8]`) | `0xa312d0` = Flash `Notice_UI__JoinQueueForPromotedMap` (slot 0xa8); `0xa31330` = the other join-queue path (lobby id from `[0x1b758ec]+0x174` or a built one) | `0x20C0` joined queue, `0x20FA` match found | yes |
| `0x20CA` | L | 401 | `0x889cf0` / `0xb0d380` | itself | empty | `0xa0da60` (UI listener slot 0, accept button), `0xa7f200` | `0x20AD`, `0x2028`, referral `0x800` | yes |
| `0x20F2` | L | 401 | `0x8c4590` / `0x845cc0` | `0x8c46c0` | `u64 account id | u32 character DID | u8 flag (lobby+0x4f0) | u8 view-match | u32list user settings` (SkillSmartcastOption, UseSelfCast, UseAutoAttack, CameraShift, CameraLocked, Camera.ShakeEnabled, render options...) | `0xa98850` (game connection up), `0xab8e00` (view match "Start") | `0x2029`, `0x204C`, `0x2016`, `0x206D` | yes |
| `0x20D5` | L | 401 | `0x889bc0` / `0x839500` | itself | `u32 percent` | `0xa964b0` loading step (only when it changes) | `0x2031` | yes |
| `0x0002` | W | object | `0x481e70` / `0x481f20` | 8 senders (section 3) | `u32 notice | u32 len | args` | see section 3 | per notice | partial (`0x1000015E`, `0x10000117`) |
| `0x2136` | W | 400 | `0x879b70` / `0x83fc80` | `0x887e60` | `f32 x | f32 y | u64 target | u32 ping type` | `0xa31030` (Alt+click ping; throttled; not in view-match). Patched client: RankSkill cave also sends type "KNAR" | none (the server places the ping marker) | old |
| `0x216E` | L | 401 | `0x888b30` / `0x8430f0` | `0x88ac00` | `str8 name | str16 value | u32 type tag` (`0x10000C33` bool, `0x10000A0E` int/float, `0x100009ED` string) | `0xa38cc0` user-preference save (all prefs at load, then on change) | none | yes (logged) |
| `0x012D` | W | 400 | `0x692950` / `0xb0d380` | itself | empty | `0xa99b60` world teardown (if session+0xce) | none (client already left) | yes |
| `0x20A6` | L | 401 | `0x8d6600` / `0x846490` | `0x8d6830` | list of chat channel tokens (`0x37dfc6c` wrapper, `0xdc6f571` / `0xdc6f572` team 1/2, `0x2cb0b02`) | `0xa455d0` (back to the wrapper after the end page), `0xa451c0` (join "Team"/"Wrapper" channels) | channel joins; the catalog's "End page closed" is this chat-channel request | old |
| `0x212E` | L | 401 | `0x883090` / `0xb0d380` | itself | empty | `0xa34900` Flash `RequestAllPendingRewardlessAchievementNotifications` when the list is empty | `0x211F` | old |
| `0x2124` | L | 401 | `0x888340` / `0xb0d380` | itself | empty | `0xa0b3e0` Flash `Notice_Character__UI_RequestPendingRewardUpdateFromServer` | `0x2125` | old |
| `0x2128` | L | 401 | `0x8c4300` / `0x845bb0` | `0x8c4470` | `u32 reward set | u32 choice | u32 source | u64 instance | u32list items | u32list qty | u32list bestowal` | `0xa411d0` Flash `UI_ClaimPostMatchReward` | none required | old |
| `0x20D4` | S | 401 | `0x88a860` / `0x839720` | itself | `u8` (`obj+0xc6`) | `0xa9be40` after login account data (also stores ProtectorName, then sends `0x20E3`) | none | no |
| `0x20E3` | S | 401 | `0x8889b0` / `0x843050` | `0x88a610` | strings: MAC address, machine name, memory / OS / CPU / GPU info text | `0xa97bd0` (login) | none | no |
| `0x20C4` | L | 401 | `0x889020` / `0xb0d380` | itself | empty | `0xab9540` once after the end page (flag obj+0x4ed, throttled) | none | no |
| `0x20BA` | L | 401 | `0x883430` / `0xb0d380` | itself | empty | `0xa2fc80` (throttled), Flash RequestPostMatchChanges path | none needed for the ribbon | no |
| `0x00CC` | W | 402 | `0x68f650` / `0x839dd0` | `0x692a80` | `u64 account character id` (`[0x1b579f0]`) | `0xa097a0` level-load done (+10 %) | none | no |
| `0x211B` | W | 400 | `0x8798b0` / `0x839dd0` | `0x887aa0` | `u64 entity` (local player `0x02...01`, then champion `0x02...02`) | `0xa9f9f0` component attached to the local player; `0xa9e080` | none | no |
| `0x207A` | W | 400 | `0x88b390` / `0x839720` | itself | `u8 flag [0x186ce07]` (computed from the character record at world entry) | `0xa23140` world-entry setup, `0xa16d50` | none | no |
| `0x213A` | W | 400 | `0x8795a0` / `0x83f690` | `0x886fe0` | `u32 encounter DID | u8 camera locked` (log: `0x40000991`, 0/1) | `0xa30df0` <- `0xa3ff50` **InputAction_Camera_ToggleLock** (`0x10000065`; also saves `User.CameraLocked` and raises `Notice_Camera__CameraLockedPreference`) | none | no |
| `0x2139` | W | 400 | `0x8795f0` / `0x83f690` | `0x8870f0` | `u32 encounter DID | u8 held` | `0xa30e70` / `0xa336b0` <- `0xa3ff50` **InputAction_Camera_TempLock** (`0x10000064`, hold to lock; release sends 0) and camera-override pops from scripts (`0x967730...`) | none | no |
| `0x20D3` | W | 400 | `0x88b670` / `0xb0d380` | itself | empty | `0xa8d5e0` / `0xa8d680` local player's controlled agent changed (the link) | none | no |
| `0x00DA` | W | 400 | `0x68f6a0` / `0x445350` | `0x692cb0` | `u64 entity | state block ... | f64 time` (log: champion id, ..., `time.time()`) | `0x628bf0` agent movement/state change (flags 4 and 2); seen at cinematic start and end | none known | no |
| `0x20BE` | S | 401 | `0x8886a0` / `0x842ad0` | `0x88a2e0` | profiler stats: 5 u32, parent name, stat name, floats | `0xa97ea0` at match end | none | no |
| `0x20B4` | S | 401 | `0x888820` / (no vtable) | `0x88a470` | GPU vendor/device (`0x10de`), resolution, then profiler entries | `0xa98200` at match end | none | no |
| `0x214F` | S | 401 | `0x888570` / `0x8429d0` | `0x88a1a0` | `str parent | str stat | 5 u32/f32` (render counters) | `0xa98550` at match end | none | no |
| `0x2116` | L | 401 | `0x88a730` / `0xb0d380` | itself | empty | `0xa57170` Flash `Notice_Character__RequestAccountEncounterStats` *(probable)* when not cached | account encounter stats (reply event not identified) | no |
| `0x2106` | L | 401 | `0x883340` / `0x446f30` | `0x883560` | one string (from `[0x4092a0]->vfunc 0xdc`, locale/region) | `0xa2fcd0` (throttled UI request) | unknown | no |
| `0x21A4` | L | 401 | `0x88a990` / `0x839500` | itself | `u32` | `0xa7bfa0` Flash `Notice_UI__RequestLeaderboards` *(probable)* | leaderboard data | no |
| `0x20EE` | W | 400 (mode 2) | `0x87c040` / (built in place) | `0x88b030` | `u32 command | u32 ability | u64 target | position | u8` | `0xa70030` order API (callers: move 4/-1 `0xa70500`; skill 2/slot from `0xa75d20`, `0xa76320`, `0xa85da0`; stop 6/-1 and hold from `0xa8a8e0`; click commands from `0xa8a140`), `0xa70600`, `0xa8b0b0` | object updates | yes |

### 2b. Other world-connection events (service 0x400)

| id | ctor / ser | sender | body | trigger | meaning |
|---|---|---|---|---|---|
| `0x2138` | `0x879640` / `0x83f730` | `0x887200` | `u32 node arg (+0xc) | u32 character DID | message block (4 u32, strings, u32list, ...)` | `0xab6e30` = **vtable slot 10 of script node `0x10000060`** (vtable `0x15fc7dc`, type id from `0x97c830`) | the node builds a HUD/mission message (`0x85e6xx` setters, local path `0xa804a0` -> Flash `0x89a3d0`...); when the target object's `+0xb0` mode is 2 it is forwarded to the server instead of shown locally (throttled by `0xab6ad0`) |
| `0x2140` | `0x886700` / `0x839500` | itself | `u32` | `0xa676b0` (HUD element state changes) | unknown |
| `0x2170` | `0x879960` / `0x444b70` | `0x887c20` | `u64 lobby id | u32 tip id` | `0xa1d930`, `0xa5e2d0` coaching tips shown | coaching tip seen |
| `0x20D1` | `0x87aba0` / `0x839e20` | `0x88b7a0` | `u64 | u64` (object ids) | `0xa5d250` selected/inspected object changed | target-of-interest |
| `0x20EA` | `0x881fa0` / `0x849c50` | `0x88b280` | `u32 | u32 | list` | `0xa23510` | unknown |
| `0x20AB` | `0x88b150` / `0x839720` | itself | `u8` | `0xa0abf0`: 1 after **InputAction_Hold**, 0 after Stop / casts | hold-position flag |
| `0x2097` | `0x88af00` / `0xb0d380` | itself | empty | `0xa0e5b0` (UI slot) | unknown |
| `0x201A` | `0x886cb0` / `0xb0d380` | itself | empty | `0xa80cd0` | unknown |
| `0x214D` | `0x887570` / `0xb0d380` | itself | empty | `0xa0aab0` | unknown |
| `0x212C` | `0x8c4a60` / `0x845df0` | `0x8c4b70` | `u32list` | `0xa51940` (after `obj->vfunc 0x54`), `0xa5ea70` (skill slots + 10) | artifact skill slot mapping *(probable)* |
| `0x208B` | `0x87af30` / `0x83f1d0` | `0x88c410` | `u32 upgrade | (u32,u64) | (u32,u64)` | `0xa17ce0` = Flash **Notice_Upgrade__PurchaseUpgrade** *(probable, slot 0x44)* | **shop purchase** |
| `0x20A7` | `0x87af90` / `0x840740` | `0x88c530` | `u32 upgrade | u32 slot | (u32,u64) x2` | `0xa17d90` = Flash **Notice_Upgrade__SellUpgrade** *(probable, slot 0x5c)* | **shop sell** |

### 2c. Other lobby / account events (service 0x401), all unhandled

Grouped by the listener vtable their trigger lives in. Lobby listener (vtable `0x1604b84`, Flash `Notice_Lobby__*`
in alphabetical slot order): `0x200A` ExitLobbyToMainMenu `u64`; `0x202D` LobbyUIReady `(u32,u32)x2`; `0x206A`
PlayerSelectedEarlyLaunch `u64,u32,u8`; `0x201E` RequestAllPregameTips `str`; `0x200D` RequestChangeAmplifierSet `u8`;
`0x2025` RequestCharacterPickerInformation `u64`; `0x2057` RequestMyAmplifierSet (empty); `0x2064` RequestMyStolenPowers
(empty); `0x2017` RequestStolenPowerList `u64,u32`; `0x20FD` RequestTeamNames (empty); `0x2102` SelectCharacter
`u32 DID, u8`; `0x2108` TeamDisplayReady `u32`; `0x214E` TriggerWaitAfterReadyFlag / team-name strings `u32, str, str`;
`0x2026` (`0xa0c410`, rejoin lobby room `u64,u32`); `0x205A` (empty). All *(probable)*.

Character/account listener (`0x1604af8`): `0x2124`, `0x2128`, `0x2116` (above), `0x2093` UI_SetProtectorIcon `u32,u32`.
Achievements (`0x1604498`): `0x212E`, `0x211D` RequestAllAchievementData (empty), `0x211E` `u32` (`0xa63070`).
UI (`0x1602a80`): `0x20EB`, `0x20CA`, `0x21A4`; standings `0x2178` RequestAccountStandingsData, `0x2193`
RequestStaticStandingsData; `0x218C` UserActionMetric `u32`; `0x2156`, `0x20F1` `u8`, `0x20D6` `u64`, `0x20BF`,
`0x2089`, `0x208E` `u32,u8,u32`, `0x2098`/`0x207D` `u32,u32` (custom-match group `0x160adb8`).
Contacts / social (`0x1602f04`): `0x20C1`, `0x2094`, `0x20E6`, `0x20FB`, `0x2199`/`0x219A`, `0x20A1`, `0x20C6`,
`0x219B`, `0x20F4`, `0x2066`, `0x200B` (strings and u64 contact ids).
Chat / text: `0x20F6` (`0xa45aa0` and 3 more: send chat text to a channel, echoed locally), `0x20CD` (`0xa71b10`:
player name, >= 3 chars, not self; slash-command target), `0x2112` (`0xa22ce0`: names + account id), `0x20E5`
(`0xa227c0`), `0x2148` (`0xac05e0`: string >= 2 chars), `0x210E`/`0x2110`/`0x2111` (`0xa46fc0`/`0xa470d0`/`0xa47200`,
encounter tracker requests with two parsed u64 and strings), `0x20FC` (`0xa2fd40`: name <= 21 chars + 7 values,
amplifier set save *(probable)*), `0x2099` `u32 string token` (lobby system lines, `0xa0d310`, `0xa1bce0`...),
`0x20DF` (empty, `0xa0d270`), `0x20E4` (`0xabd890`), `0x2160` (`0x882780`), `0x21A5` (`0xa833d0`, once at login),
`0x21A8` (`0x889e20` <- `0xa0db10`).

### 2d. Low-id object / system events (no service constant, routed to an object or the game connection)

Not seen in the Tutorial logs except `0xCC`, `0xDA`, `0x12D`. `0xDC` (`0x633170` -> `0x6927b0`): client performance
report (`u64`, frame-time buckets, fps ratio). `0xEA` (`0x62b450`, `0x62b7b0`) `u32,u32`; `0x121` (`0x62de20`) `u32`;
`0x12B` (`0x62c030`, `0x62c490`, `0x65f860`, `0x683cd0`: `u64 agent | u64 target | f32 0.1 | vector...`); `0x95`
(`0x420b90`, empty); `0x111` (`0x61c150`); `0x9B` (`0xa4ecc0`, hovered/selected object changed: `u32,u32,u8`);
`0x103`, `0x134`, `0x10B`, `0x8C`, `0xA3` (property-channel requests, `0x58xxxx`); `0x8F` (`0xb15f50`);
`0x91`, `0x97`, `0x12C`, `0xE4`, `0xE6`, `0x113`, `0xD1`, `0xCA`, `0x133`, `0x11F`, `0x127`, `0x82`, `0xF3`, `0xFA`.
**Script-driven:** client scripts call natives that send events to an entity on the server:
natives `0xC20003-0xC2000D` -> `0x9F` / `0xD2` / `0x112` / `0xC0` (`u32 message | arg blob`, dest = the target
object, sender `0x562300`, `0x563970`, `0x563b20`); `0xC50001/3/A/B` -> `0x11B`, `0xC1`, `0x98`;
`0xA60002`, `0xBE0004`, `0xBE0011` -> `0xFD`; `0x2800001`, `0x27C0002` -> notice `0x1000015E`.

## 3. Notices the client sends (event 0x2, dest = local player 0x0200000000000001)

Only these 8 exist (all constructor `0x481e70` calls). The notice id comes from a static global.

| notice | sender | args | trigger | meaning / expected server reaction | ics |
|---|---|---|---|---|---|
| `0x10000207` | `0x883a40` | none (len 0) | `0xa0a510` (local player's controlled agent changed, the +20 link step) | player linked to its champion | no |
| `0x1000015E` | `0x884010` | none | `0xa96cf0` load complete (+15), `0xa96a00` local player arrived after load, script natives `0x2800001`/`0x27C0002` (`0x9636c0`, `0x962240`) | load complete: server starts the match (intro cinematic) | yes |
| `0x10000204` | `0x886950` | none | `0xa964b0` when all-loaded (`0x206D`, lobby+0x1c0) and load complete (session+0x78); also raises UI event `0x33` | client entered the match (ready) | no |
| `0x10000117` | `0x8919c0` | **`u32 cinematic DID` only** | `0xa9cd00` (cinematic finished), `0xa9cd90` (ended/skipped), `0xa9ce20`, `0xa9ce70`, `0xa9ceb0` (could not start), `0xa9cff0` (the `0x20F5` handler: already playing / failed) | **cinematic done** | yes, but see note |
| `0x10000137` | `0x886b00` | none | Flash native `0x897df0` = `Notice_Encounter__RequestCurrentTeamHealth` | server should answer with `Notice_Encounter__UI_UpdateTeamHealth` (`0x10000134`) | no |
| `0x10000454` | `0x886de0` | `u8 yes/no` | Flash native `0x898010` = `Notice_Encounter__SurrenderResponse`; also `0xa0cd90` | surrender vote | no |
| `0x100002AD` | `0x887310` | none | Flash native `0x899210` = `Notice_Encounter__UI_ReadyForTimelineData` | server should send the timeline banners (`0x100002AF` / `0x100002B1`, then `0x10000424` AddTimelineBanner) | no |
| `0x100000D2` | `0x88baf0` | none | `0xa0cbc0` (match HUD setup: registers listeners for NotifyMatchEnded `0x1000000E`, SetMatchTime `0x10000109`, `0x10000424`, `0x100002AB..2B1`; sends only if obj+0x161), `0xa13eb0` | HUD ready for match state *(probable)*: answer with SetMatchTime / timeline notices | no |

**Note on `0x10000117`:** there is no "state" field. The body is `id | u32 4 (args length) | u32 DID`; `ics` reads
the length as "state 4 = ended", which works only because every such notice carries one u32. The client sends it once
per cinematic, when it finishes, is skipped, or cannot be played.

## 4. Specific questions

- **Scriptlet / animation-graph events reported back:** no. No sender is reached from the scriptlet runner or the
  animation graph; `0x8D` scriptlets and graph events stay client-local.
- **Cinematic timeline (`0x10000060` at frames):** the client sends nothing per frame; its only cinematic report is
  `0x10000117` (done). Separately, script **node type `0x10000060`** (same number, script-node table) has an execute
  method (`0xab6e30`) that forwards its message to the server as **event `0x2138`** when the target object is in mode
  2 (`obj+0xb0`); otherwise it shows it locally. Whether the scene timeline entries are this node is not proven.
- **Clicking props / doors:** no dedicated "use" event. A click becomes `0x20EE` (command 2 / attack-move with the
  target IID, or move); hover / selection changes may send `0x9B` / `0x20D1`.
- **Emotes (Joke/Taunt/Laugh/Dance/Oath, `0x100000CC-0xCF`, `0x100000DB`):** handled in `0xa8a8e0`; `0xa0ab70` maps them
  to 0x16 / 0x15 / 0x17 / 0x18 / 0x1C and `0x964060` runs the local player's script handler `0x28F0001` with that
  index. No direct network event; anything sent depends on the champion's client script (e.g. via natives -> `0x9F`).
- **Skill rank-up:** unpatched client sends nothing (`GM_Advancement` RankSkill dispatcher `0x90e9a0` has no handlers);
  the patched client sends ping `0x2136` type "KNAR".
- **Shop:** `0x208B` purchase, `0x20A7` sell (world service), from the Upgrade (artifact) UI.
- **Chat:** lobby service: `0x20F6` (send text), `0x20A6` (channel list), `0x20CD`/`0x2112`/`0x2148` (name-based
  commands); chat-window notices (`Notice_Chat__*`) stay local.
- **Camera lock:** `0x213A` (toggle) and `0x2139` (hold) on the game connection — the tutorial's camera-lock step can
  wait for these (they were in the 2026-10-21 log: `40000991 00` then `40000991 01`).

## 5. Method and limits

1. Scan `.text` for `mov [r+8], id` + `mov [r+0xc], 0x300400` (438 event classes); a constructor whose function (or
   caller) also calls `0x444a90` is a client sender (139 hits, ~110 distinct client events; the rest are server ->
   client factories).
2. Notice ids: the global loaded before `0x481e70` in each of its 8 callers.
3. Flash names: the AS2 dump (`old_files/tools/gfx/classes_all.txt`, `__get__Notice_X__Y_ID` getters) gives notice ids;
   the C++ dispatchers (`0x90e000-0x924000`, calls `0x4820f0(channel, id)` then `[listener vtable + slot]`) give each
   notice's slot; a sender's wrapper is matched by its own vtable slot. Vtable bases are uncertain without RTTI, so
   these names are *(probable)* unless anchored (`0x2124`/`0x2128`/`0x212E` match `reward_re.txt`).
4. Body layouts come from a serializer summarizer plus the logged bodies; lists and strings were read by pattern,
   so field order inside strings/lists of the social events is approximate.
