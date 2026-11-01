# The original's rewards side panel on the Scorecard view: not in this client (2026-10-30, tester report 14:51)

Tester's correction (14:51): the rewards must appear on the **Scorecard** tab, as in the original's end screen
(screenshot 79): to the right of the team tables, a panel "Victory / Match Duration / Rewards: Protector XP (level +
bar), Merit earned / total + bar, Champion XP (level + bar)". Our screen (screenshot 92, run 14:48-15:11, Crime Alley
v AI, lost) shows the tables and, on the right, only the champion art and the chat box. Tags: **C** confirmed, **P**
probable, **O** open. Flash = movies of pack `0xA00000D0` parsed from the installed pack (read only; tag walker in
the agent's scratchpad, not in the repo) plus the JPEXS AS2 dump `re-work/ui-as2/c_a00000d0_02189b08`.
Builds on `scorecard-summary-tab-conditions.md`, `scorecard-panel-turret-head.md`, `scorecard-accolades-meteor-aura.md`.

## 1. Verdict: this client has no such panel on the Scorecard view (C)

### 1.1 Screenshot 79 is another layout
- 79 has **two** tab buttons, "Summary" and "Stats", and "Summary" shows the tables **with** the side panel.
- This client's `Scorecard` sprite has **three** buttons (`m_btnTabAccolades` "Summary", `m_btnTabSummary`
  "Scorecard", `m_btnTabStats` "Stats"), and the panel's parts are a separate tab. The original was rebuilt between
  the two builds: the tables became "Scorecard", the panel became the new "Summary" tab.

### 1.2 Movie `0x2000008C` (stream offset `0x2767B98`, GFX v8, 43 804 bytes, frame 1280 x 720)
Every placement of the view (frame 1; frame 2 only places the import stubs):
- Sprite 113 `ScorecardScreen` -> sprite 112 `Scorecard` (`m_scScorecard` at -640, -311).
- Sprite 112 `Scorecard`: `profile_page_bg` (bg), `m_liScorecardLevelImage` (105, tutorial), `m_ncNextChallenge`
  (101, tutorial), `m_wtMissionComplete` (tutorial), **`m_stSummaryTab` (99)**, `m_btnPrev` / `m_btnNext` (+ sheens),
  the three tab buttons. Nothing else.
- Sprite 99 `SummaryTab` (class `gameplay.wrapper.scorecard.SummaryTab`): **only** `m_tcTeamContainerTop` (75, 67) and
  `m_tcTeamContainerBottom` (75, 333.8), both sprite 98 `TeamContainer` (background, WINNER, team total, 5 player
  rows, header row). The class has no other member; its `show(true)` shows the chat window
  (`ChatManager.ShowChat(All)`): that is the box at the right of screenshot 92.
- No clip with alpha 0, no hidden child, no frame label, no `attachMovie` / `AddChildFromLibrary` of a panel in
  `Scorecard` / `SummaryTab` / `TeamContainer` (the only run-time attaches are the two tabs `ScorecardAccolades` and
  `ScorecardTabStats`).
- Left-overs of the old layout: the movie still **exports** external images `XPInfoBG_png`, `OrangeBarFill*_png`,
  `YellowBarFill*_png`, `BlueBarFill*_png`, `expBarBackground_png`, `GoldGlowBack_png` (the panel's orange Protector,
  yellow Merit and blue Champion bars of 79) and an unplaced sprite `OrangeBarFillDarker` (48). No sprite places them
  and no AS2 class names them (grep over the whole dump): dead assets.

### 1.3 Where the panel's parts are now: movie `0x200000AD` (`0x2A910E0`), the "Summary" tab
Sprite 134 `ScorecardAccolades`: `m_adAccolades` (accolade cards), `m_amdMerit` (`AccoladesMeritDisplay`, 241 y),
`m_acdChampion` (`AccoladesChampionDisplay` + `YellowMultiBar`), `m_apdProtector` (`AccoladesProtectorDisplay` +
`RedMultiBar`), `m_amdMap` (`AccoladesMapDisaply`: map icon, `m_wtEncounterName`, a static label, `m_wtMapDuration`,
the bot icon, a PLAY button), the champion title and level frame. The only `Duration` in the whole class library is
`AccoladesMapDisaply.UpdateDuration`. `0x2000009D` (Stats tab) and `0x200000AE` (the accolade buttons) carry no
rewards part.

## 2. What the 14:48-15:11 run did (diag `--scorecard`, C)
15:01:57 0x2104 handler (encounter `0x40000C82`, record found, build al 1) -> Flash target non-zero; 15:01:58 Init's
accolades replay delivered, ScorecardLoadComplete (37), **106 LoadScorecard_Accolades** ("Summary" opened first),
`EndOfMatchStats ranked = 0`; 15:01:59 the late 0x2104 delivered (al 1) after ALL_DATA. So every condition of
`scorecard-summary-tab-conditions.md` 3 that can be logged held (no ranked-ribbon wait, a live notice after ALL_DATA).
Then tab switches: 91 Stats (15:02:57), 72 Scorecard (15:03:00, screenshot 92), 106 Summary (15:03:03), 72, 91, ...
O: what the "Summary" tab showed at 15:01:58-15:02:57 and at 15:03:03 (no screenshot).

## 3. Closest equivalent (fase3-is)
- The real panel = the "Summary" tab (it opens first after every match).
- On the Scorecard view the only free surface is the chat window on its right. `[ics] scorecard_chat_summary`
  (true): `matchend.scorecard_chat_summary` builds four lines, sent as chat lines (0x2183, the echo's form, which
  shows in game) 2.5 s after the scorecard's 0x212E (`scorecard_chat_summary_delay`; fallback 9 s after the end
  messages, `scorecard_chat_summary_fallback`), once:
  `Victory|Defeat - Match Duration: m:ss`, `Rewards - Protector XP: Lvl n  total / next  (+earned)`,
  `Rewards - Merit: Earned n  Total n`, `Rewards - Champion XP: Lvl n  total / next  (+earned)`.
  Channel name `scorecard_chat_summary_channel` ("All"). P: the line lands in the log the scorecard shows (the
  handler `0xA5CF40` -> `0xA4D140` picks the wrapper channel only when the last u32 is -1; ics sends 0).
- A true panel on the Scorecard view needs a Flash edit of `0x2000008C` (place `ScorecardAccolades`' parts, or a
  copy of them, to the right of the tables). That writes the game's pack; not done here (the Modern UI pipeline that
  patched movies is archived in `archive-2026-10-30/ui`).

## 4. What the tester should check
1. After the match the "Summary" tab opens first: does it show Merits, Champion XP bar, Protector XP bar, the map
   name and duration (screenshot after ~10 s)?
2. Click "Scorecard": the chat box on the right shows the four lines (result + duration, Protector XP, Merit,
   Champion XP). If the chat box stays empty, send traffic.log (the 0x2183 lines are logged as "scorecard summary in
   the chat").
