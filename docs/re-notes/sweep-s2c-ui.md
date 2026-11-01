# Sweep: server -> client UI messages that ics does not send (2026-10-25)

Scope: every S2C event / notice in `full-protocol.tsv` with status "not sent", "ics builder unused" or "old server
only" whose category is UI / HUD / notices / announcements / dialog / scoreboard / end of match / rewards / lobby /
queue / champion select / account / store / social / chat / achievements. Method: static (REA + Ghidra on
`InfiniteCrisis.exe`, base 0x400000) plus the existing notes (`ui-complete.md` section 4/6, `full-account-social.md`).

## 0. The status column of `full-protocol.tsv` is stale

Cross-check against `ics/` source (builder in `ics/messages.py` or `icserver/scorecard.py` **and** a call site in
`ics/`): **96** of the 314 S2C rows marked not-sent / builder-unused / old-server-only are in fact sent by ics today,
among them everything at the end of the match (0x2038, 0x2045, 0x2080, 0x2081, 0x2090, 0x20B9, 0x2104, 0x2188,
0x2190, 0x2154, 0x219E/F, 0x211F, 0x2125), the queue / lobby (0x2101, 0x20E0, 0x2004, 0x2005, 0x204A, 0x204B,
0x2053, 0x206C, 0x2021, 0x20FF), store (0x2107, 0x210C, 0x210D, 0x210F, 0x20C7, 0x2052), profile (0x2115, 0x2186,
0x214B, 0x21A2, 0x219D), chat (0x20B0, 0x2135, 0x2183), most custom-match events, the skill HUD (0x207B, 0x20A0,
0x2092, 0x20DC, 0x1000015A), status icons (0x20A2.. 0x20E9, 0x2127), PvP match HUD notices (0x10000109, 0x100004FB,
0x10000134, 0x1000005B, 0x10000455/6, 0x100002EB, 0x10000424, 0x100002AF/B1, 0x100002AB), announcer (0x202A,
0x2039), kill feed 0x217A, teleport 0x218A, map marker 0x20D2, ping 0x2137.
Builders that exist but have **no call site**: 0x2041 `cm_kicked`, 0x2054 `draft_trade_request`, 0x2087
`dialog_text`, 0x210B `queue_error`, 0x218F `queue_wait_times`, notice 0x100002EC `clear_announcement`, notice
0x100002AC `pvp_timeline_remove`.

The table below covers only what is really missing (no builder or no call site). 0x2189 is also sent
(`teleport_effects` stop). Pure gameplay rows (effects, scriptlets, properties, appearance, movement, world-object
services) are left to `sweep-s2c-match.md`.

## 1. Missing UI messages

Columns: id | name | what the client does (decompiled handler) | layout (after the `u8 0` base byte) | needed for |
trigger (when the original server sent it) | priority (P1 noticed in the normal flow, P2 rare / optional feature,
P3 not needed) | confidence (C confirmed static, P probable, G guess).

### 1.1 Queue, matchmaking, dialogs

| id | name | what the client does | layout | needed for | trigger | prio | conf |
|---|---|---|---|---|---|---|---|
| 0x210B | Match/queue error -> leave | `0xa818e0`: dialog text (ids 0x7FD5E15/0x737F2C7), `PendingMatchFailure(0)`, leaves the queue, the group (`0x1b758ec`) and the custom-match room (`0x1b758e4`) | empty | error path of queue / match build | match could not be built | P2 | C (builder, no call) |
| 0x20D7 | PendingMatchFailure | `0xa0dc00` -> `UI.PendingMatchFailure(arg == 0x10000049)` (bTimeout): the match-found ribbon closes | u32 reason (0x10000049 = timeout) | accept-match timeout | a player did not accept (0x20CA) | P2 | C |
| 0x218D | FindMatchFailure | `0xa155f0`: adds the u32 to the queue bonus counter (UI `+0x54 +200`), formats the StringInfo into the matchmaking tooltip | u32 bonus, StringInfo | long-queue bonus text | periodically in a long queue | P3 | C |
| 0x218E | Matchmaking_NewUpdateInterval | `0xa0dc20` -> Flash (interval, next update) | u32, u32 | queue indicator refresh | queue | P3 | C |
| 0x2191 | (reset queue bonus) | `0xa12fd0`: clears the bonus counter, rebuilds the tooltip with empty values | empty | - | re-queue | P3 | C |
| 0x20F3 | BarredFromMatching | `0xa0dc50` -> `UI.BarredFromMatching(nTimeout)` (dodge-penalty dialog) | u32 seconds | dodge penalty | after dodging a lobby | P3 | C |
| 0x218F | QueueWaitTimesUpdated | `0xa38500`: stores wait times per QueueKey; Flash reads them with `GetWaitTimeForQueue` (play screen, party, header indicator) | n x QueueKey{u32 did, u32 flags}, n x list<u32> | wait estimate on the play screen / queue indicator | login + timer | P2 | C (builder, no call) |
| 0x2087 | DisplayDialogText (strings) | `0xac85f0` -> `UI.DisplayDialogText(title, body)`: modal OK dialog | StringInfo, StringInfo | server-side errors / notices | errors, admin | P2 | C (builder, no call) |
| 0x210A | DisplayDialogText (ids) | `0xac86f0` -> `0xac8620(u32, u32, u32)`: same dialog from string-table tokens | u32 table, u32 token, u32 | localized errors | errors | P3 | C |

### 1.2 Champion select / lobby

| id | name | what the client does | layout | needed for | trigger | prio | conf |
|---|---|---|---|---|---|---|---|
| 0x2061 | UpdateEarlyLaunchTime | `0xab85a0`: only when u32 room == the lobby's room (`+0x4bc`, or 0): stores both times (`+0xc0`/`+0xc8`); if the lobby UI is ready (`+0xaa`) raises `Lobby.UpdateEarlyLaunchTime(begin, end)` -> early-launch countdown | u64 tt begin, u64 tt end, u32 room | early-launch countdown in champion select | all players locked | P2 | C |
| 0x205B | LobbyRejoinRoom | `0xab8490`: stores the room (`0xa1ba20`, `0xa0cd60`), `+0x4f0` = 1, refreshes the header -> "Rejoin match" | u32 room, u32 | reconnect to a running match | login while the account's match runs | P2 | C |
| 0x206B | Connect to lobby | `0xab8900`: lobby UI up -> sends ConnectToLobbyMessage for the room, else stores it (`+0x4c4`) | u32 room | server-driven lobby entry (ics has its own sequence) | match found | P3 | C |
| 0x2060 | UpdateLobbyState (full) | `0xabe1b0` -> `Lobby.UpdateLobbyState` (24 parallel arrays) | see full-protocol.tsv | - (0x2029 per slot works) | lobby open | P3 | P |
| 0x2054 | Draft_TradeRequest | -> `Lobby.Draft_TradeRequest(name, text)` | StringInfo, StringInfo | draft mode | trade request | P3 | C (builder, no call) |
| 0x206E | View-match enable | sends 0x20F2 with the view-match byte = 1 | u32 | spectating | - | P3 | C |

### 1.3 Account, rewards, achievements, profile

| id | name | what the client does | layout | needed for | trigger | prio | conf |
|---|---|---|---|---|---|---|---|
| 0x2197 | RewardSetsData (login reward) | `0xa81520` -> login-reward screen (`LoginReward.UI_DeliverLoginRewardSet`) | n x {6 u32, u64, u32, StringInfo} | daily login calendar (ics sends 0x219D "none") | after login | P2 | C |
| 0x21A6 | SetAchievementObjectiveData (one) | `0xa57330`: finds achievement u32 in the table (UI `+0x58`), sets the objective's value, refreshes (`0xa42430`) | u32 did, u32 objective, u32 value | live progress without a full 0x2120 | objective progress | P2 | C |
| 0x21A3 | Friends leaderboard | `0xa74140` -> `DeliverFriendsLeaderboard` | n x {u64, wstr, 5 u32}, u32 | leaderboard (friends tab) | 0x21A4 | P3 | P |
| 0x209E | (list replace) | `0xa83370`: replaces the list at UI `+0x64 +200` (`0xa6f030`) | u8, cint, n x {u32, StringInfo} | unknown | - | P3 | G |
| 0x21A0 | (table update) | `0xa37d60`: for id u32 in list `+0x1f8` writes `0xa292f0(id)` into `+0x208` | u32, u32 | unknown cache | - | P3 | G |
| 0x2015 | - | no-op handler | u32, u8 | - | - | P3 | C |

### 1.4 Social, chat, custom match (solo server: only empty states matter; 0x203B is sent)

| id | name / client effect | prio | conf |
|---|---|---|---|
| 0x2003, 0x2013, 0x219C, 0x2065 | contact invite / pending invites / invitations / list notification (toasts, invite list) | P3 | C |
| 0x2018, 0x20AE, 0x203A, 0x2058, 0x20C5, 0x208F, 0x20EC | presence, status message, note, icon changes (contact rows) | P3 | C |
| 0x2051, 0x20CC, 0x2020, 0x204F, 0x20CB, 0x205E | contact added / ignored / removed / unignored / moved, group destroyed | P3 | C |
| 0x202F, 0x2161, 0x2134 | contact lists (?); 0x2134 (`0xa21f20`) walks a name list, skips the own name (`_wcsicmp` vs UI `+0x64 +0xf0`), adds the others (`0xac6ea0`) | P3 | G |
| 0x2070 | UserCanCreateGroup (`GM_UI.RecvNotice_UserCanCreateGroup`, party button) | P3 | C |
| 0x2033, 0x214C, 0x2071, 0x217D | party invite dialog / cancelled / GroupInformation / icon | P3 | C/P |
| 0x203F, 0x2041 | custom match Left / Kicked (closes the room screen; 0x2041 builder has no call) | P2 | C |
| 0x201F, 0x2027, 0x202E, 0x217C | custom match invited / invite cancelled / invitation status / icon | P3 | C |
| 0x20B6 | ToggleUnreadChat (wstr, wstr): chat launcher blink | P3 | C |

### 1.5 In-match HUD, notices, tutorial

| id | name | what the client does | layout | needed for | trigger | prio | conf |
|---|---|---|---|---|---|---|---|
| 0x1000021C | Kill card (to the victim) | Encounter listener slot `+0x60` -> `0xa61260` -> `UI_ShowKillCard`: the defeat panel's "killed by" card (killer, contributors, damage sources) | list<u64> attackers, list<u32> icons, list<u32> teams, StringInfo, {u32 u32}, ... | PvP death screen | the victim dies | **P1** | P |
| 0x100002B2 | Kill card (spectator) | same + leading u64 | | spectator | | P3 | P |
| 0x100002BC | StopProcessingNewBillboards | billboard manager drops new billboards | empty | VICTORY/DEFEAT not covered by a late kill billboard | match end, before the win/loss billboard | P2 | C |
| 0x100002EC | ClearAnnouncement | clears the current billboard | empty | - (billboards time out) | | P3 | C (builder, no call) |
| 0x100000CB, 0x100000CE | UI_PlayerJoined / UI_PlayerLeft | kill-feed line "X joined / left" (player key) | u64 player, u64 agent, StringInfo name, u32, u32 | disconnect notices | connect / leave mid-match | P2 | C |
| 0x100000CA, 0x100000CD | Encounter (u64, u64) | empty stubs (`0xa0b5a0`) in the Encounter listener | | - | | P3 | C |
| 0x100000BA, 0x10000076 | PauseDefeatStatusTimer / TimerClockSync | no listener / clock resync | u64 u32 / u32 | - | | P3 | C |
| 0x100002AE | Timeline: batch add | `0xa72340` BatchAddTimelineEvent | n x desc, list, f64 | rejoin mid-match (0x100002AB per event is sent) | | P3 | C |
| 0x100002AC | Timeline: remove banner / event | `0xa48a50` | Handle{u32,u64} | timeline icons do not linger | event over | P2 | C (builder, no call) |
| 0x2077, 0x20BB | UpdateInductionPercent | `0xaa2570`: usage component (`+0x9c`) of agent u64: elapsed -> `+0x50`, percent = elapsed / property 0x100004FD -> cast bar (`0x8c1bb0`) | u64 agent, u64, u32 elapsed | cast bar of induction skills | each tick | P2 | C |
| 0x20CE, 0x2096 | InductionComplete / CancelledInduction | `0xa9e590` -> `0x8c1820`; `0xaa2620` resets and flashes the bar | u64, u64 | cast bar end | end / cancel | P2 | C |
| 0x2082, 0x20B2 | ChannelStarted / ChannelingInterrupted-Stopped | `0xaac620` / `0xaa2680` on the usage component | u64 / u64 u8 | channel bar | start / stop | P2 | C |
| 0x2150 | UpdateHUDVisibility | `0xa9cca0`: if u32 == the current hide request (`+0x3c`) the HUD is restored | u32 request | HUD back after a scripted hide | end of cinematic | P2 | C |
| 0x213E | BatchNotifyHUDElements | `0xa5a7b0` -> `0xa2bd30` + `0xa4b6a0`: highlights several HUD elements | n x {4 u32} | tutorial highlights | tutorial steps | P2 | C |
| 0x208D, 0x201D | DisplayFloatyStatus (u8) / replace floaty list | status floaty / floaty list (0x20BD is sent) | u8 / n x {u32, Handle} | | | P3 | C |
| 0x2091, 0x208C, 0x2187, 0x207C | skill overlay / update suppressed / enable variant / slot override | skill-bar alternates (0x1000015A, 0x207B, 0x20A0 sent) | | | | P3 | C |
| 0x2006, 0x200E | MapManager add / remove map note | `0xa56c90`: drops the note with the same handle, builds a note (`0xa95b70`: icon, team) and adds it to the map list (`+0xa4 +0x1c`) | u32 type, Handle, u32, u32, {u32}, u32 / Handle | server-placed minimap icons | objective spawn, ping | P2 | C |
| 0x209F, 0x217F, 0x2180 | ShowMiniMapTargetingRing | ring on the minimap for global targeting | u32 u64 / u32 u8 / u32 | global-range skills | targeting | P2 | C |
| 0x2179 | minimap revealed cells | fog rect property 0x7EC | n x {u32 u8}, u32 | minimap fog | vision change | P2 | P |
| 0x2023 | objective category update / remove | `0xa14040`: if the category exists and the tracker is up: state 7 removes it (`0x899570`), other states set it (`0x89bd20`) | u32, {u32 u32} | objective tracker (PvE / tutorial) | objective state | P2 | C |
| 0x2047 | dialog-system call | `0xa13b40`: dialog system (`+0x1c`) vt+4 (entity, u64, 3 u32) | u64 u64 u32 u32 u32 | conversation line on an entity | scripted | P3 | G |
| 0x2142, 0x2143 | dialog queue / flag | `0xa475c0(list, 0, u8, 1, 0)` | list<u32> u8 / u8 | | | P3 | G |
| 0x2171 | Training: load control | `0xa8de40`: flag set -> loads the lesson list (`0xadb230`), `+0x170` = 1, starts (`0xa8c770`) | list<u32>, u8 | training lessons | training start | P2 | C |
| 0x2172 | UpdateTrainingFloatyText | `0xa177e0`: u8 1 shows training floaty text on entity u64 (`0xa0eb20`), 0 hides it (`0xa0ec60`) | u64, u8, u32 u32 u32, StringInfo | tutorial floaty text | tutorial step | P2 | C |
| 0x2173 | training floaty trigger | `0xa7a930`: sets flags (`+0x1c +0x14c` bit 2, `+0x74 +0x173`), advances the training floaty (`0xa17a10`) | u32 | tutorial | step done | P2 | C |
| 0x2174 | training lesson event | `0xa93df0`: local player only, raises a lesson event (`0xa93260`) | u32 | training | | P3 | C |
| 0x10000288, 0x100004A5 | ShowTutorialHints / CloseTutorialHint | hint popups (0x1000027F single hint is the known one) | list<u32> / u32 | tutorial hints | tutorial | P2 | P |
| 0x10000059, 0x1000004A, 0x100000B6 | GM_UI group (4 u32 / empty / empty) | listener slots `+0x28` / ? / `+0x3c`, not resolved | | unknown | | P3 | G |
| 0x100003D5, 0x100003D6, 0x100003D7 | group with 0x20DE | unresolved | u32 / list / u32 | unknown | | P3 | G |
| 0x2123, 0x2126, 0x2129, 0x212A | StatusIcon component vt calls | alternate status-icon paths (0x20A2 family is sent) | | | | P3 | C |
| 0x20DD, 0x212B, 0x10000414, 0x10000364 | Upgrade component (upgrade list, artifact slot mapping) | shop HUD alternates (0x20E2 sent) | | | | P3 | G |

## 2. Counts

- 314 S2C rows flagged in `full-protocol.tsv`; 100 are already sent by ics (section 0), 7 more have a builder with no
  call site. Of the remaining, **~120 are in this UI scope** (tables above, grouped rows counted per id); the rest is
  gameplay (effects, scriptlets, properties, appearance, world-object services) for `sweep-s2c-match.md`.
- Priorities: **P1: 1** (kill card 0x1000021C); **P2: ~45** (queue errors and wait times, early launch, rejoin,
  login rewards, live achievement progress, custom-match left/kicked, cast/channel bar, minimap notes/rings/fog,
  objective categories, HUD restore, tutorial / training texts and hints, timeline remove, player joined/left,
  billboard stop); **P3: the rest** (social, alternates, no-op or unresolved).
- The normal flow (login -> menu -> queue -> select -> loading -> match -> end screen -> rewards -> menu) is already
  covered by what ics sends; the only gap a player sees in that flow is the empty kill card when killed in PvP.

## 3. Top 20 implementations

1. Notice 0x1000021C kill card to the victim on death (attackers, icons, teams, killer name).
2. Notice 0x100002BC before the VICTORY/DEFEAT billboard.
3. 0x218F queue wait times after 0x20C0 (builder exists).
4. 0x210B / 0x20D7 on a failed match build or accept timeout (builder for 0x210B exists).
5. 0x2087 DisplayDialogText for server-side errors / disabled features (builder exists).
6. 0x2061 early-launch countdown in champion select (with 0x206C, already sent).
7. 0x205B LobbyRejoinRoom when the account logs in while its match still runs.
8. Induction / channel bar: 0x2077, 0x20CE, 0x2096, 0x2082, 0x20B2 for skills with an induction time.
9. 0x2023 objective category state for PvE / tutorial objective trackers.
10. Training text: 0x2172 / 0x2173 (+ 0x2171 / 0x2174 for training lessons).
11. Tutorial hints list / close: notices 0x10000288 / 0x100004A5.
12. 0x2006 / 0x200E minimap notes for objectives and pings.
13. 0x209F / 0x217F / 0x2180 minimap targeting ring for global skills.
14. 0x2179 minimap fog cells (with the match sweep).
15. 0x2150 HUD restore after a scripted hide.
16. 0x213E batch HUD highlights (tutorial).
17. Notice 0x100002AC timeline remove (builder exists).
18. Notices 0x100000CB / 0x100000CE player joined / left in the kill feed.
19. 0x21A6 live achievement objective progress.
20. 0x2197 login-reward calendar instead of the fixed 0x219D; 0x203F / 0x2041 custom-match left / kicked.

