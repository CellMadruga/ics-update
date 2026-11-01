# Modern UI: player profile and match results (the "profile" area), 2026-10-30

Builds on `ui-modern-build.md` (pipeline, module convention, sections 8 / 9), `scorecard-accolades-meteor-aura.md`
(the scorecard's tabs; the rewards chain waits for the accolades) and `aggro-recall-scorepanel.md`. Design: the
approved canvas (navy `#0A1220`, panels `#0F1B2E` translucent, accent `#2FA8FF`, gold `#F2B33D` = Crisis Coins /
protector XP, blue `#3FA9FF` = Merits, green `#6FD08C` victory, red `#FF7B7F` defeat / enemy, pointed plates).

Tags: **[C]** confirmed (code, data, the test VM, a build on a copy of the pack), **[P]** probable, **[G]** guess.
Nothing here has run in the real client yet.

## 0. Short version

| Movie | Module | Modern |
|---|---|---|
| `0x2000008C` scorecard | `ui/modern/movies/0x2000008C_scorecard/` | navy backdrop, pointed tab pills (selected = blue), VICTORY / DEFEAT title with glow, map name + duration, our table blue / enemy red, arrows + CONTINUE blue |
| `0x200000AD` rewards tab ("Summary") | `0x200000AD_rewards/` | one translucent side panel behind Merits / champion XP / protector XP with a coloured stripe each, protector bar gold, champion bar blue, Merits blue, map box on a card, fail-safe for the stalled chain |
| `0x2000009D` scorecard Stats tab | `0x2000009D_scorestats/` | navy card over the Legacy frame, header strip toward the accent, zebra navy rows |
| `0x200000AE` accolades widget | `0x200000AE_accolades/` | the medal strip on a navy card, navigator arrows blue |
| `0x200000A0` calling card | `0x200000A0_callingcard/` | electric-blue outline around the card (all five sizes) |
| `0x200000A3` profile stats | `0x200000A3_stats/` | page frame navy, dropdown blue, rows navy with light-blue values, headings blue |
| `0x200000A2` achievements | `0x200000A2_achievements/` | page / detail frames navy, progress bars + arrows blue, counters / title light blue |
| `0x200000B2` ranked | `0x200000B2_ranked/` | frames navy, header strips accent, PLAY RANKED blue on a pointed pill, leaderboards navy zebra with our row blue |

Shared by the eight modules (in `ui/modern/common/`; first written as `0x2000008C_scorecard/ic_kit.as` and
`ic_profile_art.py`, moved and renamed (integrated 2026-10-30, `ui-modern-build.md` 10)):
`profile_kit.as` (AS2 helpers, included after `common.as`) and `profile_art.py` (our vector art, block-letter title
font, colour constants; `import profile_art as pa` in each `module.py`). Tests: `python tests\test_ui_profile.py` (755 checks).

## 1. What the movies allow [C]

- Every screen's behaviour is library code bound to instance names (`ui-modern-feasibility.md` 2); the modules keep
  every original tag / placement / instance name / clip action / `registerClass` byte-identical and in order (tested on
  the installed movies).
- **No fonts of our own**: a movie has no DefineFont; labels are imported `UIWidget_Text` widgets. New text is either
  a *clone* of a text widget the symbol already places (the map name / duration: clones of `m_wtMissionComplete`,
  template `H4`, filled by our script), or *drawn*: the VICTORY / DEFEAT title is a 5 x 7 block font made of slanted
  parallelograms (`profile_art.block_text`, 68 / 56 polygons, no overlap).
- **Unnamed Legacy art** (frames, backings) is reached with `getInstanceAtDepth(depth - 16384)` (timeline depth d =
  AS depth d - 16384; the library's own TweenLite calls it, so GFx has it [P that it returns unnamed placements]). Only
  sprites come back (shapes do not): every depth used below was checked to be a sprite or an imported symbol.
- **Layers**: our art can only go at free depths of the edited symbol. Where a card must lie *under* the content there
  must be a free depth below it (Scorecard 4, TeamContainer 2, ScorecardAccolades 2, AccoladesMapDisaply 2,
  ScorecardTabStats 2, Accolades 2, Ranked 8); `Stats` (`0x200000A3`) has none (depths 1..8 used), so its frame is
  recoloured instead of covered.
- Polygons of one DefineShape3 are drawn in one layer by `gfx_edit.define_shape3` (no new-styles records): our art
  never relies on overlapping polygons; glows are separate sprites (the glow band is non-overlapping slices).
- Multi-frame symbols (Scorecard, ScorecardAccolades, ScorecardTabStats, Stats: 2 frames) may re-enter frame 1:
  `ic_Install` registers once (`ic_ready`) and every Modern change is idempotent. Symbols with long timelines of their
  own (AccoladeButton 120 frames, AchievementButton 240, MultiBar 23) are **not** edited; they are styled from their
  parent.

## 2. The kit (`ui/modern/common/profile_kit.as`) [C in the VM]

`ic_Keep(mc)` remembers an original instance once (x, y, alpha, colour transform, text colour); `ic_Paint` (a
`flash.geom.ColorTransform`, the library's own way), `ic_Navy` / `ic_Accent` (fixed transforms), `ic_Fade`, `ic_MoveTo`,
`ic_TextColour` go through it; `ic_Restore` puts back exactly what was changed (moved -> x / y, faded -> alpha,
painted -> the saved colour transform or identity, text colour). `ic_Colour` / `ic_Box` / `ic_Over` place and colour
*our* white art. `ic_Install(ours)` is the usual `ic_Apply`: Modern = our clips shown, the ticker `m_icTicker`
started (if the symbol has one and the script defines `ic_Frame`), `ic_Modern()`; Legacy = our clips hidden, the ticker
stopped and, if Modern was on, `ic_Legacy()` + `ic_Restore()`. In Legacy nothing original is written (tested).

## 3. Scorecard `0x2000008C` [C in the VM, P in game]

| Symbol | Modern |
|---|---|
| `Scorecard` | Legacy frame (depth 1, imported sprite) faded, `m_icBackdrop` (translucent navy card, depth 4) over its bounds (or `K_BD_*`); a pill `m_icTabPill0..2` (depths 300-302, under the tab buttons 367-369) sized around each **visible** tab button every frame: `selected` = electric blue and the button untinted, the others navy `#101C30` at 85 % and the button dimmed; `m_btnPrev` / `m_btnNext` tinted blue; once `m_bAllDataRecevied` and not `m_bIsTutorial`: `m_icTitleVictory` + `m_icGlowVictory` (green) or `m_icTitleDefeat` + `m_icGlowDefeat` (red) at `K_TITLE_X/Y` (960, 84: the right side of the tab row), from `ScorecardManager.instance.GetData()` (`WinningTeam == YourTeam`); `m_icMapName` / `m_icDuration` filled once with `EncounterManager.instance.GetEncounterData(didEncounter).sName` and `utils.UIUtils.FormatTimeString(Duration, 2, 0, false)` (the calls `AccoladesMapDisaply` makes) at `K_MAP_X/Y` |
| `TeamContainer` | `m_mcBkgd` (team-colour frame) transparent; `m_icTeamPanel` (white card, depth 2) over its bounds, tinted our blue (`m_tcTeamContainerTop`, SummaryTab puts our team there) or the enemy red, alpha `K_TEAM_ALPHA`; `m_icTeamStripe` (depth 4) on its left edge, accent / red; the five rows' and the total row's `m_mcBackground` pushed to navy (their "player" highlight keeps its shading) |
| `NextChallenge` | `m_btnContinue` (tutorial CONTINUE) tinted blue |

The first tab: the client's UI state machine already opens the rewards tab (`m_btnTabAccolades`, "Summary") first
(`scorecard-accolades-meteor-aura.md` 1.2); in Modern its pill is the bright one while it is selected. The tab
**labels and order are not changed** (labels are string tokens set by the game's clip actions; reordering would move
original instances the class does not expect to move) [choice].

## 4. The rewards tab `0x200000AD` [C in the VM, P in game]

| Symbol | Modern |
|---|---|
| `ScorecardAccolades` | `m_icRewardsPanel` (card, depth 2) over the union of `m_amdMerit` / `m_acdChampion` / `m_apdProtector` (padded, room for the stripes), fallback `K_PANEL_*`; stripes `m_icStripeMerit` (blue), `m_icStripeChampion` (accent), `m_icStripeProtector` (gold) left of each row, their alpha following the row's own fade (the class's chain); **fail-safe**: on this tab, with `m_sdData` in, the chain not complete and all three rows still at alpha 0 for `K_REWARDS_FAILSAFE` frames (420, about 7 s; 0 = off), it calls the tab's own `KillAnimations()` then `draw()` once (= `OnManagerKillAnimation`, what Esc does through `ScorecardManager`, which only works while the manager is "animating") |
| `AccoladesProtectorDisplay` | backing (depth 1) faded, total box (depth 3) navy, `m_mbBar.m_ttcFrontBar` / `m_mcMiddleBar` gold (a third of the bar's shading kept), `m_wtEarnedXP` gold |
| `AccoladesChampionDisplay` | same, bar and earned XP electric blue |
| `AccoladesMeritDisplay` | backing (depth 3) faded, total box (depth 1) navy, the three Merit numbers `#3FA9FF` |
| `AccoladesMapDisaply` | `m_icMapPanel` (card, depth 2) over the backing (depth 3), both backings faded, PLAY AGAIN `m_btnPlay` blue |

Text colours are set again every frame by a ticker in the three display symbols (their `m_tfText` exist only once the
widgets have loaded, and `UIWidget_Text.Text` writes `htmlText`, which may bring the template's colour back); these
classes never set a colour themselves [C, library grep]. The library's persistent way would be the widget's
`iprp_TextColor` setter (`SetTextAttr("textColor")`, kept in `m_HtmlTextColorCache`), but its original value cannot be
read back for Legacy, so the scripts use `m_tfText.textColor` like the header.

## 5. The other movies [C in the VM, P in game]

- `0x2000009D` ScorecardTabStats: frame (depth 1) faded under `m_icStatsPanel` (depth 2), `m_mcHeader` toward the
  accent; `ScorecardTabStatsRow1` / `Row2`: `m_mcBkgnd` navy / lighter navy (Row2's own colour transform is saved and
  put back).
- `0x200000AE` Accolades: `m_mcBackground` faded under `m_icAccoladesPanel` (depth 2); AccoladeNavigator: arrows blue
  (their placement colour transforms saved and put back).
- `0x200000A0` CallingCardDisplay_L / _M / _S / _L_Simple / _M_Simple: `m_icCardRing` (depth 60, four strips, 3 px at
  200 x 200, stretched to `m_mcBG`); `m_mcBG` (the player's chosen card art, clickable) untouched. The ring has no mouse
  handler (an AS2 clip without handlers does not take clicks) [P that GFx agrees].
- `0x200000A3` Stats: frame (depth 3) navy, `m_ddEncounterSelect` blue; StatRow: background (depth 1) navy, value
  `#BFE4FF`; StatHeading: label `#2FA8FF`; EloDisplay: value `#BFE4FF` (set every frame by a ticker, as in the header:
  `UIWidget_Text.Text` writes `htmlText`, which may bring the template's colour back).
- `0x200000A2` Achievements: frame (depth 1) navy, arrows blue, `m_btn0..7.m_barAchievement.m_mcFrontBar` blue,
  `m_wtEarned` / `m_wtPages` light blue; AchievementDetail: frames (depths 1, 3, 5) navy, `m_barDetails.m_mcFrontBar`
  blue, title blue.
- `0x200000B2` Ranked: frames (depths 1, 3) and `m_mcRequirementsBackground` navy, header strips (depths 5, 83,
  `m_mcRequirementsHeader`) toward the accent, `m_btnPlay` blue on `m_icPlayPlate` (pill, depth 8, 55 %);
  LeaderBoard: `m_mcBkgd` / `m_mcNoDataBG` navy; LeaderBoardEntry: even navy, odd lighter, `m_mcMeFrame` blue.

## 6. What the movies do not allow (or what is left to other areas)

- **The profile page layout** (left card with protector icon + level badge + name + gold protector-XP bar + summary
  tiles; right: tabs Match history / Champion mastery / Achievements / Ranked as pills) is not in these movies: the
  page shell and its tab switch are the veteran landing `0x200000A4` (VeteranLanding, `ProfileTabButton`) and the
  landing nav `0x200000A8` (LandingSwitcher), owned by the "home" area. Stats / Achievements / Ranked are separate
  screens attached by `WrapperMain`; each is restyled on its own here. The home area would need: pills for the
  profile tab buttons (same `Pill` art + `selected` logic as the scorecard tabs, `profile_kit.as` can be included), the card
  over the protector panel and a gold tint on its XP bar.
- **Match history / champion mastery** screens: no movie of this area holds them (the stats page is per map; mastery
  is in the champion screens).
- **Tab labels / order** on the scorecard: kept (section 3).
- **The calling-card dialog** (`0x20000080`, the "collection" area): nothing needed from it; it shows the
  `0x200000A0` card, which now has the Modern outline in Modern.
- **Fonts / text styles** of the game's own labels (Rajdhani-like bold uppercase): only colour can change
  (`TextField.textColor`); the font face is the library's.
- In-game unknowns [P]: `getInstanceAtDepth` returning unnamed placements in GFx; the title font's look at the
  client's scale; whether `K_TITLE_*` / `K_MAP_*` collide with the champion wallpaper / nameplate (constants in
  `0x2000008C_scorecard/module.py`); the fail-safe's 7 s.

## 7. Checks

`python tests\test_ui_profile.py [rp folder]` (755): the eight modules in a temporary copy (with
`ui/modern/common`, so other areas' modules do not take part), every script and clip action compiles with every `K_`
constant resolved, art well formed; on the installed pack (or the Modern build's backup): the full pack built in memory
twice (deterministic, `verify_build`), each movie's CRC, record header, exports, init actions, every other top-level
tag and every original sprite tag byte-identical and in order, original instance names, added names `m_ic*`, one
script after the placements, art transparent, clones off screen; each script in the VM against mocks built from the
symbol's own placements: Legacy writes nothing original, Modern writes only `_x _y _alpha` scale / colour transform /
text colour on originals, Modern -> Legacy restores every original; behaviour: title win / loss / no data / tutorial,
map + duration, pills, team colours, rewards panel, stripes, fail-safe timing (once, not while the rows show), bar and
Merit colours, the PLAY RANKED plate.
`tests\test_ui_build.py` with these modules plus header and settings: 340 pass; its `install: manifest movies` check
hard-codes `{0x20000077, 0x2000005f}` and fails as soon as any other module exists (needs updating by its owner).
A full build of header + settings + these eight to a scratch folder: 57 152 512 bytes, verified.
