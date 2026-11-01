# Account, meta and social systems of the client: data sources, message sequences, what to persist (2026-10-22)

Static analysis of the full Ghidra decompilation of `InfiniteCrisis.exe` (image base 0x400000, **all addresses are
VAs**; `re-work/decomp/c/*.c`), of `TurbineLauncher.exe` (`re-work/decomp-other/TurbineLauncher`), REA/Ghidra byte
reads of vtables and notice-id tables, and the earlier notes. Only IDs, short names and numbers are written here.
Tags: **[C]** confirmed in code or data, **[P]** probable (one link missing), **[G]** guess.

This note is the per-system view for a preservation server. Byte layouts of every event are in `protocol-complete.md`
(§2.2 client→server, §3.3 server→client); record contents (achievements, reward sets, login calendar, accolades,
standings, amplifiers, Stolen Powers) are in `account-systems-data.md`; the Flash arguments of every notice are in
`ui-complete.md` §4-5. **Section 1 corrects several client→server names of `protocol-complete.md`** (contacts,
custom match, lobby, amplifiers): read it first.

---

## 1. How Flash requests reach the wire, and corrections to the earlier event names [C]

**Mechanism.** Flash calls `Turbine.SendNotice(id, args)`; the bridge (e.g. `0x935ad0` for `0x10000319`) checks the
argument count and calls the notice's dispatcher (`0x90e000`-`0x924000`, one per notice, e.g. `0x913cc0`). The
dispatcher looks the notice id up (`0x4820f0`, hash of listeners) and calls the listener's **vtable slot at a fixed
offset**. Listener objects register their notice ids with `0x879000` / `0x879430` (`0x879080` unregister) from static
id tables (`0x186dab0` contacts, `0x186dc48` custom match, …). The notice-id globals used by the dispatchers sit at
`0x1867360`+ (e.g. `[0x1867388] = 0x10000319`).

**Every listener interface is the alphabetical list of its system's Flash `SendNotice_*`/`SendQuery_*` names**, one
slot each, starting at the vtable pointer the object stores. Earlier passes aligned the dispatcher offsets with the
wrong vtable base (off by 3 slots for contacts, 1 for the lobby/custom-match object), which produced wrong names.
The mappings below are checked three ways: alphabetical order, dispatcher offsets, and **argument types** of every
slot against the Flash signature (they all agree).

### 1.1 Contacts listener (object built at `0xa468a0`, stored at UI system `+0x10`; vtable `0x1602f10`) [C]

| slot | Flash notice (id) | handler | event | body (packed) |
|---|---|---|---|---|
| +0x00 | UI_AddNoteToContact (`0x10000315`) | `0xa137e0` | **`0x20C1`** | `u64 contact IID \| wstr note` |
| +0x04 | UI_AddStatusMessage (`0x10000336`) | `0xa13820` | **`0x2094`** | `wstr status message` |
| +0x08 | ?UI_CanInviteSteamFriends (`0x10000513`) | `0xa0c200` | - (local query) | |
| +0x0C | UI_ContactList_Ready (`0x1000031A`) | `0xa64d30` | - (pushes the cached list to Flash: `0x8d8020` NotifyContactList, `0x8d9fc0` pending invites) | |
| +0x10 | UI_CreateContactGroup (`0x10000313`) | `0xa137a0` | **`0x20E6`** | `wstr group name` |
| +0x14 | UI_DestroyContactGroup (`0x10000314`) | `0xa46970` | **`0x20FB`** | `u64 group id` (string id parsed `0xae9f40`) |
| +0x18 | UI_IgnoreUnignoreContact (`0x10000312`) | `0xa13750` | **`0x219A`** ignore / **`0x2199`** unignore | `wstr name` (≤ 21 chars, else local error) |
| +0x1C | UI_InviteContact (`0x10000319`) | `0xa136e0` | **`0x20A1`** | `wstr name` (friend request by name) |
| +0x20 | UI_InviteResponse (`0x10000316`) | `0xa13710` | **`0x20C6`** | `u64 inviter IID \| wstr inviter name \| u8 accept` |
| +0x24 | UI_InviteSteamFriends (`0x10000512`) | `0xa27ec0` | **`0x219B`** | `list<u64>` (Steam friend ids from the Steam API wrapper `0x717620`) [P for the ids] |
| +0x28 | UI_MoveContactToGroup (`0x10000318`) | `0xa469f0` | **`0x20F4`** | `u64 contact IID \| u64 group id` |
| +0x2C | UI_RemoveContact (`0x10000317`) | `0xa0c220` | **`0x2066`** | `u64 contact IID` |
| +0x30 | UI_UpdatePresence (`0x10000335`) | `0xa0c240` | **`0x200B`** | `u32 ContactPresence` |

Chat slash commands registered in `0xa27db0`→`0xa22330` region (`0x5e9830(token, 0x10000004, fn)`): `0xa22240` →
`0x20A1` (add friend), `0xa22290` → `0x219A` (ignore), `0xa222e0` → `0x2199` (unignore) [C]. So the same events are
reachable from chat text.

### 1.2 Custom-match listener (object `[0x1b758e4]`, ctor `0xa76f90`, vtable `0x1604b88`; registered `0xa22330`) [C]

| slot | Flash notice (id) | handler | event | body |
|---|---|---|---|---|
| +0x00 | AssignTeam_CustomMatch (`0x10000379`) | `0xa0c410` (skips self / coordinator) | **`0x2026`** | `u64 target IID \| u32 team` |
| +0x04 | Cancel_CustomMatch (`0x10000373`) | `0xa0c2f0` | **`0x205A`** | empty |
| +0x08 | ChangeCoordinator_CustomMatch (`0x10000386`) | `0xa0c4e0` | **`0x200A`** | `u64 account IID` |
| +0x0C | Create_CustomMatch (`0x10000372`) | `0xa0c2c0` | **`0x202D`** | `QueueKey {u32 encounter DID, u32 flags=0}` |
| +0x10 | ForceLaunch (`0x100003A0`) | `0x132c5c0` | - (no-op in this build) | |
| +0x14 | GivePerm_CustomMatch (`0x1000037C`) | `0xa0c460` | **`0x206A`** | `u64 target \| u32 perm \| u8 grant` |
| +0x18 | Invite_CustomMatch (`0x10000375`) | `0xa0c310` | **`0x201E`** | `wstr name` |
| +0x1C | InviteResponse_CustomMatch (`0x1000037B`) | `0xa0c340` | **`0x200D`** | `u8 accept` |
| +0x20 | ?IsInCustomMatch (`0x100003E7`) | `0xa0c7d0` | - (local) | |
| +0x24 | Kick_CustomMatch (`0x1000037A`) | `0xa0c3e0` | **`0x2025`** | `u64 target` |
| +0x28 | Launch_CustomMatch (`0x1000037D`) | `0xa0c4c0` | **`0x2057`** | empty |
| +0x2C | Leave_CustomMatch (`0x10000376`) | `0xa0c3c0` | **`0x2064`** | empty |
| +0x30 | MovePosition_CustomMatch (`0x10000378`) | `0xa0c490` | **`0x2017`** | `u64 target \| u32 direction` |
| +0x34 | Randomize (`0x100003D1`) | `0xa0c510` | **`0x20FD`** | empty |
| +0x38 | RequestCustomMatchData (`0x1000038A`) | `0xa71e60` | - (rebuilds `UI_DeliverCustomMatchData` from the client cache) | |
| +0x3C | SetDraftMode (`0x100003E8`) | `0xa0c530` | **`0x2102`** | `u32 0x20000 (queue flag "draft") \| u8 enable` |
| +0x40 | SetEncounter (`0x100003FD`) | `0xa0c550` (only if it changed) | **`0x2108`** | `u32 encounter DID` |
| +0x44 | SetTeamNames (`0x1000047C`) | `0xa35ba0` (coordinator only; both names go through the text filter `0x4e4ab0`) | **`0x214E`** | `u32 team \| StringInfo long \| StringInfo short` |

### 1.3 Lobby listener (lobby client object, vtable `0x160adb8`) [C slots / P for empty-name slots]

| slot | Flash notice | handler | event | body |
|---|---|---|---|---|
| +0x00 | AttemptToRejoinLobbyRoom (`0x100002D1`) | `0xab9540` | **`0x20C4`** (seen 1.3 s after login) | empty |
| +0x04 | Draft_RequestTrade (`0x100002FD`) | `0xab7c80` | **`0x20D6`** | `u64 account` |
| +0x08 | Draft_TradeResponse (`0x100002FB`) | `0xab7ca0` | **`0x20F1`** | `u8 accepted` |
| +0x0C | ExitLobbyToMainMenu (`0x100001D3`) | `0xabc5c0` | **`0x20BF`** | empty |
| +0x10 | LobbyUIReady (`0x100001CA`) | `0xabea40` | (local: Flash pushes `0x89e7c0`/`0x89e170`) | |
| +0x14 | PlayerChangedCharacterLockStatus (`0x100001CF`) | `0xab89d0` | **`0x208E`** | `u32 variant DID \| u8 lock \| u32` |
| +0x18 | PlayerSelectedEarlyLaunch (`0x100001CC`) | `0xab8980` | **`0x2089`** | empty |
| +0x1C | RequestAllPregameTips | `0xaba430` | - | |
| +0x20 | RequestChangeAmplifierSet (`0x1000038F`) | `0xab7ce0` | **`0x2098`** | `u32 set slot \| u32 default-set DID` |
| +0x24 | RequestChangeStolenPower (`0x100001F1`) | `0xab8a30` | **`0x207D`** | `u32 slot \| u32 Stolen Power DID` |
| +0x28..+0x3C | RequestCharacterPickerInformation, RequestMyAmplifierSet, RequestMyStolenPowers, ?RequestStolenPowerList, ?RequestTeamNames, RequestToPurchaseVariant | `0xab7d20`, `0xab9c20`, `0xab8a90`, `0xab7d00`, `0xab9bf0`, `0xab8b30` | - (answered from the cache) | |
| +0x40 | SelectCharacter (`0x100001CE`, id global `[0x1867a40]`; its dispatcher calls +0x40) | `0xabd750` | **`0x20E4`** | `u32 variant DID \| u8 (1 = not a locked pick) \| u32` |
| +0x44 | TeamDisplayReady | `0xab9be0` | - | |
| +0x48 | TriggerWaitAfterReadyFlag (`0x10000489`) | `0xab7cc0` | **`0x2156`** | empty |

### 1.4 Other identifications made in this pass

| event | real meaning | evidence | tag |
|---|---|---|---|
| `0x20BA` (empty) | **Amplifier.UI_RequestAllAmplifierSets** → answer `0x2090` | sender `0xa2fc80`; when throttled it raises `GM_Amplifier.RecvNotice_NotifyAmplifierSetError` (`0x88de80`) instead | C (was "RequestPostMatchChanges") |
| `0x2106` (`str8`) | **Amplifier.UI_RequestAllAmplifierBoutiqueData** (str8 = region / currency key from the app config vt+0xDC) → answer `0x2107` | sender `0xa2fcd0`, same throttle + amplifier error path | C |
| `0x210E` | **Contextual.UI_PurchaseContextualItem** `u64 boutique id \| u32 item DID \| str8 currency \| u32 price \| str8` | Contextual listener vtable `0x1602018`: `0xa47200`, `0xa470d0`, `0xa46fc0` = Cancel, Confirm, Purchase (alphabetical) | P |
| `0x2110` | **Contextual.UI_ConfirmContextualPurchase** `u64 \| (u64 boutique, u32 DID, str8 currency, u32 initial, str8 order id, u32 final)` | same | P |
| `0x2111` | **Contextual.UI_CancelContextualPurchase** (same body) | same | P |
| `0x2112` | **PlayerReport.ReportAPlayer** `wstr \| wstr \| u64 \| QueueKey \| wstr \| u32 \| wstr \| u32` (reporter, target, match, encounter, …, choice, extra text) | sender `0xa22ce0` takes 3 args (target, choice, text) = the Flash signature | P |
| `0x20CD` | chat **tell**: `wstr target \| wstr text` | chat command type 0x12 → `0xa71b10` (target ≥ 3 chars, not self) | C |
| `0x20F6` | chat say on a channel: `StringInfo channel \| wstr text` | chat types 0x0D, 0x0E, 0x10, 0x11, 0x13 → `0xa45aa0` … `0xa46160` | C |
| `0x2148` / `0x2160` | admin console commands (name string / integer) | `0xac05e0` / `0xac0660`, gated by `0xabff10` (admin check), registered with `0x5e9830` | C |
| `0x2099` / `0x20E5` | lobby slash commands (`u32 command token` / `QueueKey \| u32 token \| wstr arg`) | `0xa1bd20`…`0xa1bf40`, `0xa0d310`, `0xa0d360` | C (purpose of each token: G) |

**Consequence for `ics` [C]:** `ics/session.py` maps `0x2102` to SelectCharacter; the real champion pick is
**`0x20E4`** (`u32 variant | u8 | u32`). `0x2102` is the custom-match draft toggle. The ics/old-server tables of
`0x200A`, `0x200D`, `0x2017`, `0x201E`, `0x2025`, `0x2026`, `0x202D`, `0x2057`, `0x205A`, `0x2064`, `0x206A`,
`0x20FD`, `0x2108`, `0x214E` (lobby names) and of `0x20C1`, `0x2094`, `0x20E6`, `0x20FB`, `0x2199/219A`, `0x20A1`,
`0x20C6`, `0x219B`, `0x20F4`, `0x2066`, `0x200B` (custom-match names) should be renamed as above.

---

## 2. Launcher and login handshake

### 2.1 Launcher (`TurbineLauncher.exe`) [C]
- Reads `LoginServer.Host/Port/Protocol/Auth/Launch/Reporting/Disable` (`0x409160`, `0x411100`, `0x416420`) and asks
  `WebLoginApp-1.3/LauncherWS` **getLauncherData(region, language)** (envelope at `0x4402b0`, `Config::GetLauncherData_`
  `0x411360`); answers are `Launcher.*`, `Patch.*`, `GameClient.*` name/value pairs. Metrics go to
  `WebLoginApp-1.3/Metrics`. It does **not** authenticate: `AuthenticateWS` is only named as a URL (`0x40fd30`).
- It starts the client with `{LOGINURL}` substituted (`Patcher::LaunchClient`, `0x409160`).

### 2.2 Client command line [C] (`0x40d6e0`)
`loginurl`, `loginregion` (shard), `reportingurl`, `account`, `host`, `port`, `outport`, `language`, `franchise`,
`prefs` (preferences file), `gametype`, `supporturl`, `bugurl`, `resource-set`, `rodat`, debug flags.

### 2.3 AuthSelect (SOAP, client `0xa9b420` → `0xa973e0`; request serializer `0xadcd70`, response `0xadc7c0`) [C]
- Request `AuthSelect {userName, password, region, language, steamid (xsd:long)}`; Flash entry
  `GM_ConnectionManager.LoginWithWBID(sWBID, sPassword)`; the default URL string is
  `http://localhost:8084/WebLoginApp/AuthenticateWS` (overridden by `loginurl`).
- **Bypass** [C code / P trigger]: if a configured login value equals `"BYPASS"` (`0x186e91c`) the client logs
  "Bypassing login service" and connects directly with the host/port of its own config (`0xa9a280`).
- Response fields, in order: `errorString`, `loginTicket` (xsd:long), `nameValuePairs` (array),
  `newSocialMediaEncryptionKey`, `oldSocialMediaEncryptionKey`, `randomID`, `sessionKey`, `userServerAddr`,
  `userServerPort` (int).
- Result handling (`0xa9b890`): transport failure → error `LOGIN_DOWN` (`0xa96d80` → `ConnectionManager.ShowLoginError`).
  `errorString` present → shown as the login error; **`errorString == "NO_DISPLAY_NAME"`** opens the
  `URL.Registration` pair. Success → `0xa9a280(userServerAddr, port, loginTicket, randomID, sessionKey, …)`: clears
  `User.FirstTimeLogin`, stores host/port in the app config, then reads these **nameValuePairs** keys:
  `URL.Store`, `URL.Registration`, `URL.Tutorial1/2/3`, `URL.YouTubeChannel`, `URL.ReleaseNotes`,
  `URL.GothamDivided`, `URL.GothamHeights`, `URL.CoastCity`, `URL.CrimeAlley`, `URL.Survey`, `URL.Credits`,
  `URL.UpdateNews`, `URL.Augment`, `URL.Mod` (all optional; a server may send none).
- Then the user connection (connect packet 0x10000 with the RSA-wrapped session key; `protocol-complete.md` §1.2-1.3).

**Server must persist per account:** user name, password hash, display name (absent → `NO_DISPLAY_NAME`), Steam id
(optional), the account IID (`0x02000000_0000000N` style, used as `u64 account` everywhere below).

### 2.4 Web ticket / Steam microtransactions [C names / P use]
`EM_WebTicket.UI_RequestWebTicket` → `RecvNotice_UI_OnWebTicketUpdated(strWebTicket, shardId)` (`0x6971d0`) and
`UI_OnMicroTxnAuthorizationResponse(strOrderID, bAuthorized)` (`0x696df0`) are fed by Steam callbacks
(`steam_api.dll`: `SteamUser`, `SteamFriends`), not by the game server. The store screen is a CEF page
(`URL.Store`). A preservation server can leave them unanswered.

---

## 3. Login data (landing screen) — order and meaning

Current `ics/messages.initial_events` sends (order matters; `0x2080` last opens the landing gate) [C]:

| # | event | content | persisted source |
|---|---|---|---|
| 1 | `0xEB` | set local player (`u64 0x0200000000000001`) | account IID |
| 2 | `0x20B8` | ownables (§4.1) | owned items |
| 3 | `0x20ED` | champion catalogue (groups head/costumes/skills pseudo-item, pack ids) | data (champions.json) |
| 4 | `0x209D` | **CharacterAdvancementData**: per champion `u32 DID, u32 level, u32 XP, u32 next-level XP, u64 last used (unix s), u64 last used ranked` [P field names from the Flash signature] | per champion level/XP/timestamps |
| 5 | `0x2024` | encounter list (queue flags, completed, last played) | data + completed encounters |
| 6 | `0x216A` | server options (§9) | preferences |
| 7 | `0x2120` | achievement progress (§6.1) | achievement progress |
| 8 | `0x218B` | game settings table (`FeaturedMap_PVP`, `FeaturedMap_BOTS`, …) | server config |
| 9 | `0x215D` | `u32 status \| u8` → `UI.ProtectorAdvancementStatus(eStatus, strMovie)`: 1 Player, 2 Trainee, 3 FirstTimePlayer [P mapping] | derived from trainee achievements |
| 10 | `0xCE` | account character set (name) | display name |
| 11 | `0x2080` | account level / XP | account level, XP |

The client then sends (user connection) `0x20D4`, `0x20E3` (machine info: do not store), `0x212E`, `0x20C4`
(AttemptToRejoinLobbyRoom: answer nothing or `0x205B` if a room is open), every server-synced preference with
`0x216E` (§9), `0x20BA` (→ `0x2090`), `0x2106` (→ `0x2107`), `0x21A5` if the champion list was empty.
Header data on demand: `0x2190` header + 5 protector icons, `0x2081` currencies (§4.3).

---

## 4. Collection, currencies, store

### 4.1 Ownables `0x20B8` [C]
`u8 0 | u32 n | n × (u32 DID, u32 ContentStatus, u32 ContentType, u8 owned, u32 count)`; first delivery →
`UI.ItemStatuses`, later ones (changed items only) → `UI.Incremental_ItemStatuses` (handler `0xa88030`). Types and
statuses: `account-systems-data.md` §2.1-2.2. Flash `GM_UI.RequestItemStatuses` / `RequestCharacterAdvancementData`
are answered from the cache (no wire event).
**Persist:** set of owned DIDs per ContentType (champions 1, skins 4, Stolen Power versions 2, icons 3, amplifier
set slots 5, augments 12, mods 13) with counts.

### 4.2 Champion and costume unlocks [C]
Unlock = an ownables change (`0x20B8` incremental) + the ribbon `0x2095` (`u32 key | u32 item | StringInfo`,
`Ribbon_ItemFulfilled`, then `Ribbon_FinishedItemsFulfilled`). Sources: rewards (§6.2), login calendar (§6.4),
store (§4.4). Stolen Power versions unlock at champion level 5 when owned (`account-systems-data.md` §5).

### 4.3 Currencies [C]
`0x2081 u32 hard (Crisis Coins) | u32 soft (Merits)` (`Character.SendAccountCurrencyBalance`); end-of-match
`0x20B9` (base, daily, f32 time to next daily, streak, potential daily, potential streak, 2 tooltips, u32).
Flash `RequestAccountCurrencyBalance` / `…Changes` have no wire event: the server pushes. **Persist:** both balances,
time of the last daily first-win bonus, win streak.

### 4.4 Store / boutique [C names, P bodies]
- Amplifier prices: client `0x2106` (str8) → server `0x2107` `u32 n × {u64 boutique id, u32 amplifier DID,
  StringInfo currency, u32 price}`.
- Purchase: client `0x210E` → server `0x210C u64 order` (success) or `0x210D u64 order | u32 error`
  (`0x10000068` general, `0x10000069` insufficient funds); price change `0x210F` → client `0x2110` confirm /
  `0x2111` cancel. After success send `0x20B8` (incremental) + `0x2081` + optionally `0x2095`.
- Champion / skin purchases were made in the CEF store (`URL.Store`) with Steam MicroTxn; no game event lists their
  prices (`account-systems-data.md` §2.3). `GM_Lobby.RequestToPurchaseVariant` is never called by Flash.
**Persist:** orders (id, item, currency, price) only if a real economy is wanted; otherwise grant directly.

---

## 5. Loadouts: amplifier sets and Stolen Powers

### 5.1 Amplifier sets [C]
Set struct, `0x2090` / `0x20C7` / `0x2052` / `0x20FC` layouts and the worked example: `account-systems-data.md` §1.4.
Corrected requests: **`0x20BA` = request all sets** (answer `0x2090`), **`0x2106` = request boutique data**
(answer `0x2107`), `0x20FC` = save (answer `0x20C7` or `0x2052`). In the lobby: **`0x2098 u32 slot | u32
default-set DID`** = RequestChangeAmplifierSet (answer `0x204A` to every player of the room); RequestMyAmplifierSet
is answered from the client cache. **Persist:** per account the list of sets (slot, champion DID, name, icon DID,
7 amplifier DIDs) and max slots (owned set-slot items + base).

### 5.2 Stolen Powers [C]
Lobby: **`0x207D u32 slot | u32 power DID`** = RequestChangeStolenPower; server answers `0x2004`
(`u32 | u32 | u32 | u64`: PlayerPickedStolenPowers) and keeps the pair for the match (properties `0x100008F0` /
`0x100008F1`). Ownership by `0x20B8` type 2. **Persist:** last chosen pair per champion [P: the original kept a
per-champion selection, the picker shows the current one].

### 5.3 Champion pick and lock [C]
**`0x20E4` = SelectCharacter** (`u32 variant DID | u8 | u32`), **`0x208E` = lock status** (`u32 DID | u8 lock |
u32`), `0x2089` early launch, `0x2156` wait-after-ready, `0x20BF` exit lobby. Server answers: `0x2029` / `0x2060`
(player slots), `0x2005` lock failed.

---

## 6. Progression and rewards

### 6.1 Achievements (incl. trainee, daily/weekly quests) [C]
Data: 192 achievement records (`account-systems-data.md` §3.1). Wire: `0x2120` progress (+ list of deprecated),
`0x21A6` objective data, `0x211F` pending banners (answer to `0x212E`), `0x211D` request all, `0x211E u32`
(AcknowledgeAchievementDisplayed or RequestAchievementDetails [P]). Trainee status (`0x215D`) is derived from the 5
trainee achievements. **Persist:** per achievement: progress, times completed, valid-until time (repeatable ones),
acknowledged flag.

### 6.2 Reward sets, claims, ribbons [C]
`0x2124` → `0x2125` pending reward sets; claim `0x2128 u32 set | u32 choice | u32 source | u64 instance | list item
| list qty | list bestowal`; then grant (ownables/currency) + `0x2095`. **Persist:** pending reward instances
(id, set DID, source type/DID) and claimed ones.

### 6.3 Account (protector) level and champion levels [C]
`0x2080` account level/XP (also end of match), `0x2104` champion level/XP + accolades, `0x209D` per-champion table.
No XP curve exists in the client (`account-systems-data.md` §3.7). **Persist:** account level/XP, per champion
level/XP, last used (ranked/unranked) unix time.

### 6.4 Login calendar [C data / P wire]
Calendar `0x48001528` (110 entries, days 0-374). Server → `0x2197` (same layout as `0x2125`;
`LoginReward.UI_DeliverLoginRewardSet(lastDay, eligible, days[], …)`) or `0x219D` (none eligible). Flash
`QueueLoginReward` / `ReadyForLoginRewardSet` (`0x1000050B` / `0x1000050A`) have **no client→server event among
the 161 senders** [C absence]: the server must push `0x2197` at login when a day is due and grant it itself.
**Persist:** first-login date (day index), last claimed day.

### 6.5 Accolades [C]
`0x2188` end of match; `0x2186` best map / best champion accolades. `UI_RequestBestAccolades` has no wire event
(push `0x2186` at login). **Persist:** best medal per (accolade, map) and per (accolade, champion), ranked flag.

### 6.6 Account stats [C]
`0x2116` → `0x2115` per-encounter stat rows (59 stat ids, `account-systems-data.md` §3.9). **Persist:** per
encounter (ranked / unranked) totals of each stat, matches played/won.

---

## 7. Ranked, leaderboards, profile icons

- Static standings (21 teams, 4 tiers): data `0x4800155F`; `0x2193` → `0x219F`. Account standings: `0x2178` →
  `0x219E` (`UI_DeliverAccountStandingsData(featured, lastPlayed, encounters[], ranks[], subRanks[], positions[],
  streak[], previous…, played[], won[], wonLast[], bShowBanner)`). Leaderboards: `0x21A4 u32 encounter` →
  `0x21A2` / `0x21A3` (`u32 n × {u64 account, wstr name, u32 rank, u32 sub-pips, u32 position, u32 champion, u32}
  | u32`; regional / friends). Queue eligibility `0x2101`. **Persist:** per ranked encounter: rank, sub-rank,
  position, streak, previous values, played/won, last result.
- Protector (avatar) icons: `0x2093 u32 icon DID | u32 index` (UI_SetProtectorIcon) → answer `0x2154 u32 | u32`
  or a full `0x2190` (`header name + 5 icon DIDs + names/descriptions`). **Persist:** 5 icon slots; owned icons via
  `0x20B8` type 3.

---

## 8. Social

### 8.1 Friends / contacts [C]
Client requests: §1.1. Server events (`protocol-complete.md` §3.3; Flash args `ui-complete.md` §4): full list
`0x203B` (contact record `u64 iid, u64, wstr steam name, u64 group id, wstr group name, wstr note, u32 type (1
friend, 2 ignored), u8, 5 × u32 icon, u32 level, wstr status, u32 presence`) or `0x2161` (contacts + groups),
added/ignored/removed `0x2051` / `0x20CC`, removed `0x2020`, unignored `0x204F`, group created `0x2014` / destroyed
`0x205E`, changed group `0x20CB`, note `0x208F`, status message `0x20C5`, presence `0x2018` / `0x20AE`, account
icons `0x20EC`, invite received `0x2003`, pending invites `0x2013`, invitations text `0x219C`, own presence
`0x203A`, own status `0x2058`, errors `0x2065` (eContactError).
Sequence: login → `0x203B` (n = 0 is enough) → Flash `UI_ContactList_Ready` (local) → user actions → reply with the
matching notify event; a friend request (`0x20A1`) → `0x2003` to the target; `0x20C6` accept → `0x20CC` to both.
**Persist:** contacts (account, type friend/ignored, group id, note), groups (id, name), status message, last
presence; pending invites.

### 8.2 Parties (grouping) [C server side / gap client side]
Server: `0x2071` group information (`GroupInformation(name, leader, me, encounter, bAllCanInvite, members[]…,
invites[]…)` and player left), `0x2033` invite dialog (StringInfo message), `0x214C` invite cancelled, `0x2070`
user can create group, `0x217D` member icon. Invites go through chat text (`GM_Chat.RunCmd`, used by
GroupInviteDialog / PVPGroupManager) → a chat command event. Grouping `LeaveGroup` / `RequestGroupInformation` /
`OnGroupPage` / `CacheQueueForGrouping` senders: **not found** (candidates `0x20DF` empty, `0x201A`, `0x214D`) [G].
Join queue as a group uses `0x20EB` with the cached queue. **Persist:** nothing (session state).

### 8.3 Custom matches [C]
Client: §1.2. Server: `0x203F` room data / left, `0x2012` participant added, `0x205D` removed, `0x2035`
permission, `0x2036` coordinator, `0x2048` moved, `0x2076` team, `0x2103` draft mode, `0x2109` encounter,
`0x2151` team name, `0x217C` icon, `0x201F` invited, `0x202E` invitation status, `0x2027` invite cancelled,
`0x2041` kicked, `0x2011` cancelled, `0x2040` launched, `0x2042` creation failed. **Persist:** nothing.

### 8.4 Chat [C]
Client: `0x20A6 u32 n × StringInfo` channel list (wrapper `0x37dfc6c`, team 1/2 `0xdc6f571` / `0xdc6f572`),
`0x20F6` say (`StringInfo channel | wstr`), `0x20CD` tell (`wstr target | wstr text`), lobby commands `0x2099` /
`0x20E5`, admin `0x2148` / `0x2160`. Server: `0x2135` member list (StringInfo room, list<u64>), `0x20B0` /
`0x20B6` (unread toggles + text, `(wstr, StringInfo, wstr)`), `0x2134`, `0x2183` (`StringInfo, StringInfo, u32,
u32`), system text `0xAB` / `0xC9`. The event that delivers another player's line is still `0x20B0` or `0x2183`
[G]. **Persist:** nothing (optional ignore list from §8.1).

### 8.5 Notifications / dialogs [C]
`0x2087` dialog (StringInfo, StringInfo), `0x210A` dialog (3 × u32), `0x2065` contact error, admin alerts
(`GM_AdminAlert.UI_RequestAdminAlerts`, local Flash query), dodge penalty `0x21A8` (client asks; no reply known),
matchmaking errors `0x20D7` / `0x210B` / `0x218D` / `0x20F3`.

---

## 9. Preferences sync (`0x216A` / `0x216E`) [C]

- **Server → client `0x216A`** (handler `0xa76bb0` → `0xa742d0`): a hash table `{ASCII name → typed value}`:
  `u8 0 | u8 0 | compact n | n × (compact len + ASCII name | u16 BE type | value)` with **type 9 = f32, 0x10 =
  compact int, 0x16 = bool** (any other type logs "Unsupported server option type" (string `0x16046fc`)). Each entry is
  written to `UserPreferences.ini` without echoing (`0xa6cb50` f32, `0xa6ca80` int, `0xa6cc20` bool, flag 0) and
  removed from the client's pending-upload list (`obj+0x74`, count `obj+0x7C`).
- After the table the client sets "synced" (`[0x1b758d3] = 1`) and **sends `0x216E` for every pending preference the
  server did not supply** (`0xa38cc0`). Later changes (`GM_Options.SetBoolOption` / `SetFloatOption` /
  `SetIntOption`, camera lock …) also send `0x216E` once synced.
- **Client → server `0x216E`** (sender `0x88ac00`): `str8 name | wstr value text | u32 kind` with kind
  `0x10000C33` bool (local type 3), `0x10000A0E` number (types 4/5), `0x100009ED` string (type 10).
- **Persist per account:** name → (kind, value text). On login send the bool/number ones back in `0x216A`
  (number → type 0x10 if integral, else 9 [P]); string preferences cannot be sent back (no string type in the
  reader) and stay local.
- Notable names: `User.CameraLocked`, `User.ShowAllChat`, `User.HasSeenPostEncounterVideo@<encounter>` (post-match
  movie), `User.FirstTimeLogin`.

---

## 10. What the server must persist per account (summary)

| store | fields | used by |
|---|---|---|
| account | IID, login name, password hash, display name, Steam id, created date | AuthSelect, `0xCE`, `0x2190` |
| progression | account level, XP; per champion level, XP, last used / last used ranked | `0x2080`, `0x2104`, `0x209D` |
| wallet | Crisis Coins, Merits, last daily bonus time, streak | `0x2081`, `0x20B9` |
| ownables | DID → (type, status, owned, count) | `0x20B8` |
| loadouts | amplifier sets (slot, champion, name, icon, 7 DIDs), max sets; Stolen Power pair per champion | `0x2090`, `0x20C7`, `0x2004` |
| achievements | progress, completions, valid-until, acknowledged | `0x2120`, `0x211F`, `0x21A6` |
| rewards | pending / claimed reward instances; login calendar first day + last claimed day | `0x2125`, `0x2128`, `0x2197` |
| accolades + stats | best medals per map / champion; per-encounter stat totals | `0x2186`, `0x2115` |
| ranked | per encounter rank, sub-rank, position, streak, previous, played/won | `0x219E`, `0x21A2/3` |
| profile | 5 protector icon slots, status message | `0x2190`, `0x2154`, `0x2058` |
| social | contacts (friend/ignored, group, note), groups, pending invites | §8.1 |
| preferences | name → (kind, value) | `0x216A` / `0x216E` |
| encounters | completed encounter DIDs, last map played | `0x2024`, `0x214B` |

---

## 11. Gaps

- Grouping (party) client requests (`LeaveGroup`, `RequestGroupInformation`, `OnGroupPage`, `ClearInvite`,
  `CacheQueueForGrouping`) and the login-reward requests: no sender found; parties likely use chat commands
  (`RunCmd`) whose command tokens are hashes registered with `0x5e9830` (names not in the exe).
- The meaning of the lobby command tokens of `0x2099` / `0x20E5` and of the `u32` tails of `0x20E4` / `0x208E`.
- Which of `0x20B0` / `0x2183` delivers another player's chat line; `0x2134` purpose.
- `0x211E`: Acknowledge vs RequestAchievementDetails (both `u32 DID`).
- `0x2112` field meaning beyond the three Flash arguments; trailing `str8` of `0x210E`.
- The `"BYPASS"` login trigger: which config value is compared (`app config +0xAC/+0xB4`).
- Remaining unknown client events: `0x201A`, `0x2097`, `0x214D`, `0x2140` (world service), `0x20DF`.
- Amounts (XP curve, Merits per match, prices) are not in the client (see `account-systems-data.md` §6).
