# The scorecard's "Summary" (rewards) tab: every condition, end to end (2026-10-30, tester report 13:18)

Tester run 13:05-13:18 (build fase3-ir, Crime Alley v AI, surrender at 624 s, team 2 won): the scorecard showed (table
filled, screenshot 90 with the "Scorecard" tab selected); the rewards card stays missing; the tester clicked "Summary"
and it was **empty**. Three server changes in a row (late 0x2188, 0x2104 with the encounter, late 0x2104) did not
change it. This note reads the whole path (Flash AS2 of pack `0xA00000D0` + the exe) instead of guessing.

Tags: **C** confirmed (decompiled exe, Flash AS2, traffic), **P** probable, **O** open. Exe = Ghidra decompile
`re-work/decomp` (VA, base 0x400000; `tools/diag.py` takes RVA = VA - 0x400000); Flash = JPEXS dump
`re-work/ui-as2/c_a00000d0_02189b08/scripts/__Packages` (the shared class library; the movies only `registerClass`).
Movies: scorecard `0x2000008C` (pack offset `02767b98`), Accolades tab `0x200000AD` (`02a910e0`). The installed
`0xA00000D0.rp` is the original (SHA-1 6bd720aa... = the Modern UI manifest's `source_sha1`; its backup is empty).
Builds on `scorecard-accolades-meteor-aura.md`, `scorecard-panel-turret-head.md`, `aggro-recall-scorepanel.md`.

## 1. The Flash path (C, AS2)

### 1.1 Who is who
- `Scorecard` (sprite 112, movie `0x2000008C`): tab buttons `m_btnTabAccolades` = label **"Summary"** (index 0),
  `m_btnTabSummary` = "Scorecard" (index 1, the placed `SummaryTab`, the team tables), `m_btnTabStats` = "Stats".
- Tab 0 = `ScorecardAccolades`, **attached at run time**: `Scorecard.OnLoadComplete -> AttachTabContents ->
  AddChildFromLibrary("ScorecardAccolades")`. The symbol lives in movie `0x200000AD` (exports `ScorecardAccolades`);
  `0x2000008C` only imports `Import_ScorecardAccolades` from `#200000AD` (the same pattern as the Stats tab:
  `Import_ScorecardTabStats` from `#2000009D`). `0x200000AD` itself imports from `#200000AE`, `#200000B0`, `#200000AA`,
  `#20000058/59/02/00/04` (all present in the pack).
- Its parts: `m_adAccolades` (`AccoladesDisplay`, the 3 accolade cards), `m_amdMerit`, `m_acdChampion`,
  `m_apdProtector`, `m_amdMap` (Victory / duration).
- `ScorecardManager` (singleton, created by the first `instance` in `Scorecard.OnLoadComplete`; the wrapper is a fresh
  Flash view after every world exit, so it starts empty each match).

### 1.2 Which tab opens first (C, UI state machine `0x34000000` graph S16 + AS2)
S0 (enter: event 100 LoadScorecardScreen, `NextScorecardTab = Accolades`) -> S1 on event 37 ScorecardLoadComplete
(sent at the end of `Scorecard.OnAllDataRecvd`) -> S6 = event **106 LoadScorecard_Accolades** -> `Scorecard.
RecvNotice_UIStateMachineEvent(106)`: `ShowTab(0)` ("Summary") unless `WrapperMain.InViewMatchModeLastMatch()` (then
tab 1 and the "Summary" button hidden). Screenshot 90 shows three buttons, so the last `ShowTab` had that flag false:
"Summary" opens first; the "Scorecard" selection in 90 is the tester's click. Clicking a button sends
TransitionToScorecard_* -> the state machine answers 106 / 72 / 91 -> `ShowTab`.

### 1.3 `ShowTab(i)` (C)
Returns early (nothing shown) while `m_bShowingMovieDialog` (the post-encounter Bink, notice
PlayEndOfMatchEncounterMovie; cleared by the dialog's complete event, then `ShowTab` again) or before ALL_DATA_RECVD
(`m_bAllDataRecevied`). Else every tab `show(tab == i)`.

### 1.4 `ScorecardAccolades` (C)
- `OnLoadComplete`: every part `_visible = false`; listeners (ribbons, KILL_ANIMATION, parts' COMPLETE); data = the
  manager's data at once if `HasAllScorecardData()`, else on ALL_DATA_RECVD (`UpdateDisplay` -> `m_sdData`).
- `show(true)`, first time (`m_bAnimationComplete` unset): `ShowRankedRibbon()` (once only): if `m_sdData.IsRanked`
  (0x2045's last argument) **and** `RankedManager.bShowRankRibbon` (0x219E's show-banner, always 1, `0xA37DC0`) it
  queues the rank ribbon and returns true -> **no `Animate()`**: the tab stays fully invisible until the ribbon's
  RIBBON_DONE (rank) calls `Animate()`. Otherwise `Animate()` -> (with `m_sdData`) `AnimateScorecardAccolades`: all
  parts visible at alpha 0, `m_adAccolades` alpha 100 + `AccoladesDisplay.Animate()`.
- The chain: AccoladesDisplay COMPLETE -> Merits fade in -> Merits text done -> champion fade in -> champion bar ->
  (RibbonManager QUEUE_DONE with the first four done) -> protector -> (QUEUE_DONE) -> map.
- `show(false)` while it has data and the chain is not complete: `KillAnimations()` (sets `m_bAnimationComplete`,
  stops everything). `show(true)` after that: **`draw()` -> `DrawScorecardAccolades`: every part visible at alpha
  100** (no data from the accolades needed; only `ScorecardAccolades.m_sdData`).
- Esc (`WrapperMain`): dismiss movie / dialog / settings / start menu, else `ScorecardManager.KillAnimations()` (only
  while `m_bIsAnimating`, set by `AnimateScorecardAccolades`) -> KILL_ANIMATION -> `KillAnimations` + `draw()`; when not
  animating Esc opens the menu instead.

### 1.5 `AccoladesDisplay` (C)
- `OnLoadComplete`: cards alpha 0; data at once if `HasAllScorecardData()`; listens **only to ACCOLADES_RECVD** (its
  ALL_DATA_RECVD handler is never registered).
- `Animate()`: does nothing without `m_sdData` (only `m_bAnimateCalled = true`). `UpdateDisplay()` (data) then
  animates if `m_bAnimateCalled && !m_tlAccolades`, or draws if `m_bDrawCalled`.
- With no accolade icons the TimelineLite is empty and completes at once (COMPLETE -> the Merits step).

### 1.6 `ScorecardManager` (C)
- `Init()` (in `Scorecard.OnLoadComplete`) asks in this order: post-match scorecard, currency balance, currency
  changes, soft currency, character level, account level, **accolades (0x100004E6)**, header (**last**).
- ALL_DATA_RECVD (once): header + stats (0x2045) + (header icons, power graph per row, upgrades per row: not for a
  tutorial) + **accolades** + account level + currency + soft currency + character level + amplifier sets +
  `RankedManager` static and account standings.
- `RecvNotice_SendAccountEndOfMatchAccoladesEarned`: sets the data, checks, then raises **ACCOLADES_RECVD only if
  ALL_DATA is (now) complete**. No other source raises it.

## 2. The C++ side (C, exe)

| What | Where | Gate |
|---|---|---|
| Flash notice AccountEndOfMatchAccoladesEarned | `0x8CEE70` (callers: `0xA61DA0`, `0xA7E0A0`; the request replay `0xA1A190` calls it too, not in Ghidra's function list) | `[ebp-0xA0]` = Flash target; 0 -> dropped (`0x8CEEE6`) |
| Flash request 0x100004E6 | dispatcher `0x911D30` (listeners' vt+0x3C), from `0x931360` (`0x9313AE`) | -> `0xA1A190`: if the manager `0xA12D50` +8 (the accolades cache: encounter, ranked byte, champion, 5 lists) exists, replays it through `0x8CEE70` **always** (empty or not) |
| 0x2188 handler | `0xA61DA0` | manager +0x64 != 0; accolade-record count (2nd list) != 0; `0xA56DB0` = 1 |
| 0x2104 handler | `0xA7E0A0` | cache +8 exists; `0xA56DB0(name, param_21 encounter, lists, param_22 flag)` = 1; ranked = encounter manager (+0x68) +0x8E bit 0 |
| `0xA56DB0` | | the five list lengths equal; flag != 0 with 0 entries -> first-map accolade `0xA40B10`, returns 1 without a lookup; else the encounter record (`0x8535D0`, record at `[ebp-8]`, `0xA56E2C`) must exist; then 1 even with 0 entries |
| Request for the character level (0x100003F1) | `0xA1A100` | replays manager +0x54 (the 0x2104 cache) via `0x88FF50` |
| Account level (0x100003FA) | `0xA1A1D0` -> `0x8908D0`; `0xA1A050` -> header level (`0x891200`) | |

- **0x2104 reader `0x849680` (C)**: champion, icon, StringInfo, 8 u32, a hash list (u8 size index <= 0x16 + packed
  count; ics `00 00`), 3 u32 lists, a bytelist, 2 u32 lists, u32 encounter (`+0xE0`), u8 flag (`+0xE4`): ics' layout is
  aligned, the encounter field is read where ics writes it.
- Consequence: Flash's Init always receives an accolades notice from the cache (that is why ALL_DATA_RECVD fired and the
  table showed); it is never the last piece (the header is asked after it), so Init never raises ACCOLADES_RECVD. Only a
  live 0x2104 / 0x2188 that reaches `0x8CEE70` **after** ALL_DATA does.

## 3. Every condition for the card to become visible

| # | Condition | Source | This run |
|---|---|---|---|
| 1 | The scorecard gets ALL_DATA_RECVD (table + `ShowTab` allowed) | 1.6 | **met** (table shown) |
| 2 | The post-encounter movie dialog completed (else `ShowTab` returns) | 1.3 | P met: `HasSeenPostEncounterVideo@0x40000C82` set at 13:18:01.468 (the movie started); tabs switch later (screenshot) |
| 3 | `ScorecardAccolades` exists (attach from `0x200000AD`) and its `OnLoadComplete` ran (all its children loaded) | 1.1, 1.4 | **O** (no runtime evidence) |
| 4 | `ScorecardAccolades.m_sdData` set (ALL_DATA_RECVD after its load, or all data in at its load) | 1.4 | P met if 3 |
| 5 | Not ranked, or the rank ribbon finished: 0x2045 last argument (encounter manager +0x8E bit 0) | 1.4 | P not ranked (queue key 0x220000 = blind \| draft, no 0x10000); **O** at run time |
| 6 | `AccoladesDisplay.m_sdData`: all data in at its load, or **ACCOLADES_RECVD** after it registered | 1.5, 1.6 | needs a live accolades notice after ALL_DATA (7) |
| 7 | A live accolades notice after ALL_DATA: late 0x2104 (13:18:02.831) -> `0xA7E0A0`: cache +8 exists (C: yes, the Init replay needs the same cache and ALL_DATA fired) -> `0xA56DB0`: lists equal (C: all 0), record of `0x40000C82` found (**O**) -> `0x8CEE70` Flash target (P yes, same as the replay) | 2 | **O** |
| 8 | ALL_DATA already complete at 13:18:02.831 (else the 0x2104 completes it itself: ALL_DATA and then ACCOLADES_RECVD in the same call, also fine) | 1.6 | met either way |
| 9 | The chain after the cards: Merits / champion need nothing more; protector and map need RibbonManager QUEUE_DONE (a stuck ribbon stops them, not the first three) | 1.4 | n/a (nothing at all shows) |

So the tab can be fully empty only if: (a) 7 failed (the live notice never reached Flash: chain stuck at step 1, every
part at alpha 0), (b) 5 (ranked: the tab waits for a rank ribbon), or (c) 3 (the tab content never loaded). (a) and
(b) are undone by leaving the tab and coming back (`show(false)` -> `KillAnimations`, then `draw()`): the parts show at
alpha 100 without accolades; (a) is also undone by Esc on the tab (it is "animating"); in (b) and (c) Esc opens the
menu. (c) survives both.

## 4. What the server sent (traffic 13:17:48-13:18:03, C)
13:17:48.571 cinematic 0x3500003B; 56.059 billboard 8 + announcer 29; 18:00.565 0x1000000E; .577-.586 0x2075, 0x214B
(0x40000991, 0x40000C82), 0x2045 (2 players), 0x2120, 0x2190, 0x2081, 0x2080, 0x20B9, 0x2104 (encounter `0x40000C82`,
flag 0), 0x2188 (empty), 0x2090, 0x219F, 0x219E; 0x12D at .720; 0x212E 01.314 -> 0x211F; 0x20BA 01.446 -> 0x2090;
0x216E `HasSeenPostEncounterVideo@0x40000C82 = True` 01.467; 0x2124 02.172 (none); **late 0x2104 at 02.831**; menu
refresh (0x20FF, 0x20B8, 0x209D, 0x2081, 0x214B, 0x2101) at 03.733. Nothing is missing from what the path in 1-2
needs; whether 7 / 5 / 3 held cannot be read from the traffic.

## 5. Fix
None that can be proven from the code: every condition the server controls is met by the fase3-ir messages (the 0x2104
layout is aligned, it carries the encounter, the late copy arrives after ALL_DATA). No behaviour change in this build;
the run-time decision is `diag --scorecard` (extended) plus two in-game checks.

## 6. `tools/diag.py --scorecard` (extended) and the tester's steps
New breakpoints (RVA; label prefix `SC`): the accolades notice's Flash-target gate (`0x4CEEE6`, `target` 0 =
dropped), 0x2188's gate and build (`0x661DAE`, `0x661E86`, `0x661F17`), 0x2104's handler with its encounter / flag /
levels (`0x67E0A0`), its build result (`0x67E321`, al 0 = no Flash call) and Flash call (`0x67E3C9`), the encounter
record inside `0xA56DB0` (`0x656E2C`, 0 = not found), Flash's Init request (`0x5313AE`) and the cache replay
(`0x61A19C` encounter / ranked / champion / names, `0x61A1C5`), the movie (`0x497AC0`) and the level ribbon
(`0x48E780`); the accolades notice itself now logs ranked / champion / count; 0x2045's `ranked` was already there.

Steps: start the server and the game; reach the match; once in the match, in a second console
`python tools\diag.py --scorecard` (Spanish alias `--puntuacion`); end the match (surrender is fine); on the scorecard:
1. If the movie plays, let it end (or Esc once). Wait 10 s on the "Summary" tab; screenshot.
2. Press Esc once on "Summary"; screenshot (panel = case a; the menu opens = b or c; close it).
3. Click "Scorecard", then "Summary" again; screenshot (panel = a or b; still empty = c).
4. Click "Stats"; screenshot (empty too = an attach problem common to both imported tabs).
Then send `logs\diag.log`, `logs\traffic.log`, `logs\server.log`.

Reading diag.log: expect, in order, `SC Flash asks for the accolades (Init)` + `replay` (al 1), the header, then
`SC UIStateMachineEvent to Flash` 106, and after the late 0x2104: `SC 0x2104 handler` (encounter 0x40000C82) ->
`encounter record` (non-zero) -> `build` al 1 -> `Flash target` non-zero -> `AccoladesEarned to Flash` -> `returned`
al 1. The first line that differs names the failed condition; `ranked=1` on `EndOfMatchStats to Flash` = case b.

## 7. Open
O: conditions 3, 5 and 7 at run time (section 6). O: a real accolade list (0x2188 list 2 = accolade records, medals
1-3) is still not sent; with it the cards would show text.
