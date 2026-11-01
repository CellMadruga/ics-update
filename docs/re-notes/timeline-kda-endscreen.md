# Timeline strip, K/D/A counter and the empty end screen (2026-10-28)

Tester 2026-10-28 ~13:52 (logs 13:38-13:52, diag `--finpartida --estadisticas`): (1) the strip under the match clock
is not in step with the announcer: the match starts and the first red mark arrives seconds later; (2) the K/D/A
counter (top right) shows the wrong numbers; (3) after the end cinematic the score screen shows no data and the
client lands on an empty HOME. Tags: **C** confirmed (exe / Flash / logs), **P** probable, **O** open.
Sources: Flash AS2 (`re-work/ui-as2/c_a00000d0_02189b08`), decompiled exe (`re-work/decomp/c`, base 0x400000),
`logs/traffic.log` / `server.log` / `diag.log` of the run.

---

## 1. Timeline strip

### 1.1 How the client positions the marks (C, Flash)

- `EventTimerV2.RecvNotice_UI_MissionEvent_StartTimeline(now)` -> `EventTimelineDisplay.StartTimeline(t)`:
  `m_ttStartTime = t`, then an `IntervalTimer` counting up from `GameTimer.GetGameTime()` at that moment
  (`StartTimer`: `m_tsStart = GetGameTime()`, duration 14400, update every 500 ms).
- Each tick: `x = floor((ttEventTime - (m_ttStartTime + elapsed)) / 5 * 12)` px; a mark at x in [-4, 4] lights the
  now-marker in its severity (1 High = red, 2 Medium, 3 Low; `MissionEventNotificationSeverityList`), at x <= -50 it
  is removed. So a mark meets the now-marker when **client elapsed = event time - the 'now' of StartTimeline**:
  only differences of the client's clock matter; the payload 'now' must be the real time at send.
- C++ (listener vtable `0x1605930`): `0x100002AF` / `0x100002B1` set flags `+0x144` / `+0x145` and call `0xA5A0F0`
  -> Flash `0x898F50`, then, if the stored list `+0x128` is not empty, `0xA480E0` replays the stored events.
  `0x100002AB` (`0xA786F0`) appends the event to the stored list (`0xA6ED90`) and, with both flags, calls Flash
  `0x8B33E0`. `0x100002AC` (`0xA48A50`): the current banner if the handle matches, else removes the event from
  Flash (`0x8B4160`) and from the stored list.

### 1.2 What ics did (C, traffic.log)

| Time | Sent | Decoded |
|---|---|---|
| 13:39:24.602 | pre-start clock, start = 1793212822.4 (13:40:22.4) | match created, `t = -60`, `t0` set |
| 13:39:27.697 | `0x100002AF/B1` now = 13:39:22.35 | **5.35 s old**: `match.t` does not run during the load, `clock() = t0 + t` stood still |
| 13:39:27.698 | events 900 drones (45 s), 901 jungle (45 s), 902 start (0 s) at `t0 + at` | start mark at 13:40:22.35 |
| 13:39:49.58 | intro over: `t = -42`, `t0` re-based, start = 13:40:31.6 | **the marks were not moved** |
| 13:40:31.56 | `match: started`, line 0xAE | |

Net: the strip was placed on a start 9.2 s too early with a 'now' 5.35 s too old. The jungle announcer lines were
scheduled from `match_camps.first` (60 s: lines at 13:41:01 / 21 / 31) while Crime Alley's camps spawn and the
jungle mark sit at `match_camps_first_by_map` = 45 s: a second mismatch of 15 s.

### 1.3 Fix (C mechanism)

- 'now' of `0x100002AF/B1/AB/0x10000424` = `time.time()` (`Match.timeline_now`), event time = `time.time() +
  (at - match.t)` (`Match.timeline_time`): the time the server's own timers (announcer lines, waves, camps) fire.
  `[ics] timeline_wall_now = true`.
- When the intro's end re-bases the clock: `0x100002AC` for each strip handle, `0x100002AF/B1` again, the events
  again (`Match._timeline_rebase`). `[ics] timeline_rebase = true`.
- The jungle lines count from `Match._camps_first()` (the camps' real first time). `[ics]
  match_jungle_lines_follow_camps = true`.
- O: the strip's icon DIDs (icons 0 = the default marker); the original's exact event list.

## 2. K/D/A counter

### 2.1 Client (C)

- Flash `PersonalScore` (MatchManager `kdaTarget` = the top bar right) shows `MatchData.GetAgentDataByIID(controlled
  agent)` `.playerKills / .deaths / .assists`, refreshed on `MatchData.EVENT_SCORECARD_CHANGE`.
- `MatchData.RecvNotice_UI_UpdateMatchScorecard` is fed by `0xA4A4F0` from the `0x1000005B` rows (element reader
  `0x867BF0`, 0x60 bytes): agent `+0x30`, player `+0x38`, champion `+0x40`, team `+0x44`, money `+0x48`, level `+0x4C`,
  **kills `+0x50`, deaths `+0x54`, assists `+0x58`**, bot `+0x5C`; your IID = the controlled agent's `+0x100/+0x104`.
  ics' wire order matches; the last scorecard of the run decodes to Player 0 / 5 / 0 and the bot 3 / 1 / 0 (C).

### 2.2 Cause (C code, P effect)

The numbers sent were what the server counted, and the counting missed kills: `_champion_died` credited a kill only
when the killing entity itself was a scoreboard champion. The bot's only death (13:42:35) was the tower's last blow
after the player's damage: no kill. Assists were recorded by `Scoreboard.hit` only when the damage source was the
champion object itself, so damage through a skill's object (`_champion_of` creator chain) gave no assist.

### 2.3 Fix

- `score_hit_owner`: the hit is recorded for `_champion_of(source)` when it is an enemy of the victim.
- `score_kill_owner`: the killer is `_champion_of(killer)`.
- `score_kill_credit_last_champion`: a champion finished by a turret / minion / creature is the kill of the last
  enemy champion who hit it within `match_assist_window` s (`Scoreboard.last_damager`); nobody -> no kill (P: the
  original's rule, as in other MOBAs; O: the exact window). The kill feed still shows the real killer.

## 3. End screen with no data, then an empty HOME

### 3.1 What the Flash scorecard waits for (C)

`ScorecardManager.CheckForAllDataReceived` dispatches `ALL_DATA_RECVD` (every scorecard widget waits for it) only
when it has: header + icons, `UI_SendEndOfMatchStats`, `UI_SetEndOfMatchStatsHeader`, **`UpdatePowerGraphValues` and
`UpdateCurrentUpgrades` for as many distinct IIDs as `AccountIIDs.length`** (both skipped only in tutorials),
accolades, account level / XP, currency, Merits, champion level / XP, amplifier sets, and the RankedManager's static
and account standings.

### 3.2 Who sends the per-row upgrades / power graph (C)

The end page `0xA795E0`, after Flash `UI_SendEndOfMatchStats` (`0x8E3AC0`), loops the rows: `0x9D1700` copies the
entry's **`+0x2FC` list** (reader `0x844770`: `u32 n | n x (u32 artifact DID, u32 stack)`) into DID / stack lists,
`0x4FD4E0` reads the entry's `+0x1C` (champion DID) -> `0xA25430` -> `0xA51820` (power graph values), then
`0xA3AC70(account IID +0x08, ...)`, which calls Flash `UpdateCurrentUpgrades` (`0x906DD0`) and
`UpdatePowerGraphValues` (`0x907A00`) **only if the DID list is not empty** (`param_4[2] != 0`). `0x8E76D0`
(`SetEndOfMatchStatsHeader`) is also called by `0xA795E0`.

### 3.3 What ics sent (C, traffic 13:50:50.964 and diag)

- `end_stats_from_ledger = false` (set after the 10-26 crash, which was the `0x219E` handler, fixed in fase3-id):
  2 empty rows, team 0, account 0, the `+0x2FC` list empty.
- diag: `END second row loop` x2 and no crash: `0xA3AC70` returned at once for both rows, so Flash never got the
  upgrades / power graph and the scorecard never left its loading state: "no data".
- Even with filled rows both rows had account IID 0: Flash keys the two dictionaries by that IID, so it would have
  counted 1 of 2.
- After the end cinematic ended (13:50:51.119) the server re-sent the objects and the HUD elements; the client left
  (0x12D, 13:50:51.133) and ics answered `0x2021`, whose handler `0xABC480` ran a second world teardown
  (diag `exit lobby (0x2021) received` -> `LEAVE WORLD`), while the end page was being filled.

### 3.4 Fix

- `end_stats_from_ledger = true`; `end_stats_unique_accounts`: each row's account IID = the local account
  (`0x0200000000000001`) or the bot's player IID; `end_stats_upgrades`: the champion's 6 artifact slots (DID 0 =
  empty, as `0x20E2`), champion DID at `+0x1C`, in-match level at `+0x20` (P meaning of +0x20).
- `exit_lobby_after_match = false` (client-cinematics-matchend.md 2.1 step 6, C in game: not needed).
- `restore_after_end_cinematic = false`: no objects / HUD re-send when the end cinematic ends after the match end.
- `menu_refresh_on_end_page_closed = 1.0`: `0x20FF` + `0x2101` again 1 s after `0x20A6` (P: the empty HOME; the
  refresh after `0x12D` went while the end page was up). O: whether HOME needs more (landing data of the login list).

## 4. Runtime check

`python tools\diag.py --finpartida --estadisticas --marcador` (`--marcador` = `--timelinekda`): Flash StartTimeline /
AddTimelineEvent with their f64 (lo / hi dwords), the K/D/A scorecard's your-IID and row count, `END row upgrades`
(count 0 = no Flash data), `END Flash UpdateCurrentUpgrades` / `UpdatePowerGraphValues` once per row, and
`SetEndOfMatchStatsHeader`.
