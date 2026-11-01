# Modern UI: the home body, footer, background and login ("home" area), 2026-10-30

Builds on `ui-modern-build.md` (pipeline, module convention, section 8) and `ui-modern-feasibility.md` (point 5, the
switch). Eight movie modules, one per movie, all in `ui/modern/movies/`; shared helpers of this area in
`ui/modern/common/` (`home_style.py`: tints and card art; `home_lib.as`: `icm_*` script helpers; moved there from
`0x200000A4_veteran_landing/` (integrated 2026-10-30, `ui-modern-build.md` 10)).
Design: the approved canvas (navy `#0A1220` / `#101C30` translucent panels, accent `#2FA8FF`, pointed plates).

Tags: **[C]** confirmed (code, data, the test VM, a build of the real pack), **[P]** probable, **[G]** guess. Nothing
here has run in the client yet.

## 0. What each movie does in Modern

| Movie (module) | Symbol(s) edited | Modern | Not done / why |
|---|---|---|---|
| `0x200000A4` veteran landing (`..._veteran_landing`) | `VeteranLanding` | The Legacy card bitmaps (achievements depth 98, champion `m_vcChampion` depth 3, map `m_vmMap` depth 1) and the three red title tabs (`Widget_Title`, depths 72 / 96 / 182) get `_alpha` 0; translucent navy chamfered cards `m_icAchCard` / `m_icChampCard` / `m_icMapCard` sit at depths 99 / 33 / 70 (just under each card's content) and accent header strips `m_ic*Header` are fitted onto the titles they replace (the titles' text, unnamed `UIWidget_Text`, stays above); View All x2 and Play Again tinted electric blue; accent rule under the upcoming rewards; a game-mode card `m_icModePanel` at the bottom right (right edge = the header's Exit button, hidden under 960 px of room) with two copies of the View All button: **PLAY PVP** (calls the header launcher's own `PVPLauncher.OnPlayClick`, shown only while the header's PLAY is) and **RANKED** (`TransitionToRanked`, as LandingNav). The champion art behind stays (WrapperBackground). | The cards' text, icons, bars and reward icons are the game's own and keep their look; a colour transform cannot recolour the orange buttons and keep their white label (the label turns pale cyan). |
| `0x200000A8` landing nav (`..._landing_nav`) | `LandingNav` | HOME / CHAMPIONS / AMPLIFIERS hidden (the Modern header has them; `K_SUBNAV_DUPES` 1 keeps them), ACHIEVEMENTS / RANKED / STATS moved into the first three slots as a slim sub-nav, the band behind (`profile_page_bg`, depth 1) tinted navy, accent rule `m_icNavRule` under the row; kept every frame (ticker). | Not removed: it is the only way to Achievements / Ranked / Stats from their sibling screens. `LandingSwitcher` (Training Mode) is restyled from the footer. |
| `0x20000090` footer (`..._footer`) | `FooterLetterBox`, `FooterCenter`, `FooterRight`, `ReleaseNotesElement` | Legacy bar `m_mcFooterBG` `_alpha` 0, navy strip `m_icFooterBar` (90 %, 2 px accent top rule + glow) in exactly the same 1280 x 52 box; Training Mode toggle, contacts, notifications and release-notes buttons tinted towards the accent. | The chat launcher next to them is `0x20000083` (chat area). The icon buttons keep their own shapes (no new pointed plates behind them: they are already pointed / hexagonal). |
| `0x2000009E` background (`..._background`) | `WrapperBackground` | Navy shade `m_icShade` over the art (depth 8): a left-to-right fade (62 % -> 0 over 1400 of 2560 px) behind the cards / the login form and a soft bottom fade. Every out-of-match screen with this background gets it in Modern (`K_BG_SHADE` 0 turns it off). | The art itself is the game's. |
| `0x2000006D` login (`..._login`) | `LoginScreen` | Legacy form background (`wbid_login`, depth 1) `_alpha` 0; a full-height navy column with an accent right edge (`m_icLoginPanel`, depth 2) holds the form on the left, the login art / intro movie stays visible on the right; LOG IN (`ButtonPlay m_btnLogin`) tinted with the header's PLAY tint over a pointed plate `m_icLoginPlate` (depth 16); title plate (depth 13), field backgrounds (depths 15, 17) and the small buttons tinted. | `DisplayNameRequestScreen` and `ConnectingScreen` (same movie) stay Legacy. |
| `0x200000B1` login rewards (`..._login_rewards`) | `LoginRewards`, `RewardDay` | Navy card `m_icRewardsPanel` fitted every frame behind the timeline (depth 6: inside the Legacy mask at depth 5, which clips 6..9 like the timeline itself), accent rule under the welcome title, Continue and every day's Claim tinted. | Day cells' art (sunburst, cradle) unchanged. |
| `0x20000078` trainee landing (`..._landing`) | `TraineeAchievement` | Tints only: card bitmap (depth 3) navy, title tab (depth 5) blue, PLAY with the PLAY tint. | No panel: the large achievement icon (depth 1) is drawn *under* the card bitmap (depth 3), so nothing new can go between them. Trainee screens only show under account level 5 (ics default 30). |
| `0x20000074` new player (`..._new_player`) | `NewPlayerScreen` | Navy card `m_icTextPanel` behind the text column (depth 2), LAUNCH with the PLAY tint, the cyan underline (depth 11) in the accent. | The movie already has an original `m_icBG` (Legacy art container): not ours, untouched. |

In Legacy every script only hides its own clips (art is alpha 0 from the build anyway, the two clones are off screen);
**no original instance is written** (tested for every edited symbol). A live switch from the settings check box
re-applies every registered part (`_global.ICModern.applyAll`); each Modern change to an original is remembered on
the instance (`icm_a` alpha, `icm_t` tinted, `icm_x/icm_y`, `icm_v`) and undone exactly on the way back.

## 1. Mechanisms used [C in the VM / P in game]

- **Unnamed Legacy art by depth.** The card bitmaps and title tabs have no instance name; they are reached with
  `MovieClip.getInstanceAtDepth(swfDepth - 16384)` (timeline placements live at AS depth `depth - 16384`).
  [P] GFx 3 supports `getInstanceAtDepth` (Flash 7 API); if it does not, every helper gets `undefined`, nothing is
  faded and our cards / header strips / login column hide themselves (the Legacy art stays: a Legacy-looking screen
  with tinted buttons, never a broken one). Tested both ways.
- **Depth slots.** New art must be at a free depth in the right z-order: the cards go one depth under each card's
  content (99 above the faded 98, 33 under `m_vcChampion` 34, 70 under `m_vmMap` 75); header strips one under each
  title's text (71 / 95 / 180). Where no slot exists (trainee card, login title plate) the Legacy art is tinted instead.
- **Clips whose size the game measures** stay inside their Legacy bounds: `WrapperMain.OnSized` positions the header
  and footer from `m_wgWrapperBackground._height` (the shade stays in 0..2560 x 0..1440), and
  `FooterBkgd.GetFooterHeight()` is the footer letterbox's `_height` (the strip is exactly 0..1280 x 0..52). An
  alpha-0 or hidden child still counts in `_height`, so a larger shape would move Legacy too (tested: art bounds).
- **Tints**: `flash.geom.Transform(mc).colorTransform` like the header; constants in `home_style.TINTS`
  (`K_BTN_*` orange / green -> electric blue, `K_PLAY_*` = the header's PLAY tint, `K_ICON_*` footer icons,
  `K_NAVYT_*` navy for kept bitmaps).
- **Game-mode buttons** are new instances of the View All button (`MediumTextButtonLearn`, char 131) with the game's
  component parameters (`mode_button.as`), scaled to 26 px tall like the header's nav.

## 2. Is `User.InterfaceStyle` readable on the login screen? Yes [C for the read path, P for the start-up value]

- The login screen comes before the account's `0x216A`, but the preference also lives in
  `Documents\InfiniteCrisis\UserPreferences.ini`, `[User]` section: the tester's file has `InterfaceStyle=0` right
  next to `ShowWrapperMovies=True` and `FirstTimeLogin=False` [C, file read 2026-10-30].
- The login screen already reads a `[User]` key through the same query before any account exists:
  `LoginScreen.OnLoadComplete` sets its "disable animations" check box from
  `SettingsManager.ShowWrapperMovies`, which the `SettingsManager` constructor reads with
  `GM_Options.SendQuery_GetBoolOption("User.ShowWrapperMovies")` [C, library code]. `common.as ic.read()` does the
  same with `SendQuery_GetIntOption("User.InterfaceStyle")` (`0xA4DEF0`).
- [P] `User.InterfaceStyle` is registered by Flash on first use, not by the exe; that the value loaded from the INI
  at start-up is adopted when the name is registered later is not traced (`0x4D8930` looks an existing entry up with
  `0x4D2C40` before creating it and copies its value when found). Precedent: `User.HasSeenPostEncounterVideo@<DID>`,
  also a Flash-only name, persists across sessions. If it were not adopted the login would simply be Legacy (the home
  is right anyway once `0x216A` arrives).
- So the login module uses the preference; in-game check: tick Modern, quit, restart: the login must be Modern.

## 3. Problems found for shared code (not changed here)

- **`gfx_edit.define_shape3` cannot draw an edge longer than 3276.75 px** (65535 twips): `NumBits - 2` is written in
  4 bits, so a longer edge corrupts the shape. The header's `ModernBar` is 12 000 px wide (`rect(-4000, 0, 8000, 76)`):
  `shape_polys` fails on it (IndexError), so the bar the tester "did not notice" may well be a broken shape. Fix in
  `gfx_edit`: split edges into pieces of at most 3276 px (or check and refuse); every art of this area stays under it
  (tested by a shape round trip).
- `tests/test_ui_build.py` checks `set(man["movies"]) == {"0x20000077", "0x2000005f"}`: it fails as soon as any other
  module exists (with the header, settings and this area's modules in a scratch copy: 237 passed, that 1 failed).
  Should be "contains" (or derived from the layout). Its `codes[sname]` is keyed by symbol name only (two movies
  may export the same name).
- `ui_build.Layout` loads every module folder: one half-written module of another screen stops every build;
  `tests/test_ui_home.py` therefore builds from a temporary copy holding only `common/` and this area's modules.

## 4. In-game test (tester)

1. Game closed: `python ic.py ui build`, `python ic.py ui apply`. Log in: everything Legacy (default).
2. Settings > UI > "Modern interface (beta)": the home body switches at once: navy cards with blue header strips,
   blue View All / Play Again, the sub-tabs reduced to ACHIEVEMENTS / RANKED / STATS on a navy band, the navy footer
   strip, a navy shade over the left of the champion art, the PLAY PVP / RANKED card at the bottom right.
   Untick: back to Legacy at once.
3. In Modern click: View All (x2), Play Again, PLAY PVP, RANKED, ACHIEVEMENTS / RANKED / STATS tabs, Training Mode,
   contacts, notifications, release notes. Visit Achievements / Stats and come back.
4. Quit with Modern on and restart: the login screen must be Modern (navy column on the left, blue LOG IN). Log in.
5. `python ic.py ui revert` when done. Screenshots of the home (Modern and Legacy) and the login, plus
   `logs\server.log`, `logs\unhandled.log`.

What a wrong result would mean: cards missing but Legacy bitmaps still visible -> `getInstanceAtDepth` unsupported
(section 1); header strips misplaced -> the titles' `getBounds`; login Legacy after a restart -> the INI value is not
adopted before login (section 2); footer or header shifted in Legacy -> some art grew a measured clip's bounds.

## 5. Open points

- Every size / position comes from the movies' placement data; none of the Modern layouts has been seen on screen.
- The orange -> blue button tint turns their white labels pale cyan (colour transforms are per channel).
- `profile_page_bg` (LandingNav band) is tinted without having been looked at; if it is a large panel the navy tint
  covers more than the tab row.
- The game-mode card overlaps the lower right of the champion art by design; `K_MODE_CARDS` 0 removes it.
