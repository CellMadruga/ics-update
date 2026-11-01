# Modern UI, rebuilt from scratch: login, header, home body, sub-nav, footer (2026-10-30)

The first Modern UI (`ui-modern-build.md` 6-10, `ui-modern-home.md`) **restyled** the Legacy movies: tints, moves,
panels behind or over the original art. The tester's screenshots of it (login and home, 2026-10-30) were judged
"nothing like the approved design: only colours change and things get misaligned". Agreed new approach: **build each
screen from scratch** with our own design, keeping the instance names and widget classes the game's library code
expects, so the game still fills the data and every button works. This note covers the method and the first five
movies rebuilt with it. The 27 restyle modules (and the header restyle) moved to `ui/modern/retired/` (reference
only, not built; their area tests build them from there in a scratch tree and still pass).

Design reference: the approved mockups `Login.dc.html` and `Main.dc.html` (1440 x 810), scaled x 0.8889 to the game's
1280 x 720 stage (colours, spacing and the pointed `.pt` / `.pts` buttons exactly; the type is the game's own fonts).

Tags: **[C]** confirmed (code, data, the test VM, a build of the real pack), **[P]** probable, **[G]** guess. Nothing
here has run in the client yet: section 9 is the tester's step.

## 0. Short version

| Movie | Legacy linkage(s) -> Modern twin | What the twin is |
|---|---|---|
| `0x20000077` header | `HeaderLetterbox` / `HeaderLeft` / `HeaderCenter` / `HeaderRight` -> `ICM_Header*` | 64 px navy glass bar; the game's IC logo; pointed PLAY; HOME / CHAMPIONS / AMPLIFIERS / STORE links (current one white + accent underline); Merits (blue dot) / Crisis Coins (gold dot) pills; avatar (the game's calling card) with level badge, name, ONLINE, XP bar; help / settings / exit icon buttons |
| `0x2000006D` login | `LoginScreen` -> `ICM_LoginScreen` | navy column on the left (logo, Sign in, USERNAME / PASSWORD fields, Remember me, Disable menu animations, full-width pointed LOG IN, error line, links, region), the game's login animation on the right with NEWS / PATCH / SERVER cards |
| `0x200000A4` home body | `VeteranLandingScreen` -> `ICM_VeteranLandingScreen` | hero = last champion played (name 36 px, skin, level, XP bar, next rewards, the champion's own mini wallpaper, PLAY NOW / VIEW CHAMPION), achievement progress card, four game-mode cards (the game's map-type icons), last map played card, level rewards card, navy shade over the left of the champion wallpaper |
| `0x200000A8` sub-nav | `LandingNav` -> `ICM_LandingNav` | ACHIEVEMENTS / RANKED / STATS tabs under the header (selected = accent underline) |
| `0x20000090` footer | `FooterLetterBox`, `FooterLogoLeft` -> `ICM_Footer*` | navy strip with accent rule (same 1280 x 52 box); logo moved to the header |

Not rebuilt (Legacy in both looks): login rewards `0x200000B1` (not simple: a timeline of day cells with their own
animation states; 2-3 h with this method), ConnectingScreen / DisplayNameRequestScreen, the trainee landing
(`0x20000078`, accounts under level 5), FooterCenter (Training Mode) / FooterRight (contacts, notifications), the
legal LogoFooter on the login, the contacts (friends) panel, the background (game art, kept on purpose).

Build: `python ic.py ui build` -> `data/ui_build/0xa00000d0.rp` (6 movies: these 5 + the settings switch;
2026-10-30: 57 082 880 bytes, SHA-1 `8d008e7b5f86...`, every other record byte-identical, zlib verified). Tests:
`tests/test_ui_rebuild_home.py` (630), `test_ui_build.py` (117), the five retired area tests unchanged in count.
Preview without the game: `python tools/ui_preview.py` -> `data/ui_build/preview/login.png`, `home.png` (our art
exactly, game widgets as dashed boxes, a stand-in font).

## 1. The method [C for the build and the VM; P in game where marked]

**Where to switch.** Every screen, header part, footer part and the landing nav is attached by linkage name through
ONE library method: `ui_sys.UIWidget_Base.prototype.AddChildFromLibrary(i_sClip, i_sVar, i_bSize, i_aInit)` ->
`this.attachMovie(i_sClip, i_sVar, getNextHighestDepth(), init)` (`WrapperMain.AttachHeader / AttachHeaderLeft /
...Center / ...Right`, `AttachFooter`, `AttachLogoFooter`, `AttachLandingNav`, `AttachNextScreen` with
`m_ssData.m_sScreenIDString` = `"LoginScreen"`, `"VeteranLandingScreen"`, ...). The store (`ResolutionSizer.
AttachClipWithOInit`) and the background (`ResolutionSizer.AttachClip`) are the exceptions. So the switch is a wrapper
around that method, installed at run time (the library's bytes are not edited):

```
ic_proto.ic_LegacyAdd = ic_proto.AddChildFromLibrary;                 // common/rebuild.as
ic_proto.AddChildFromLibrary = function (clip, var, size, init) {
    alt = ICModern.swap[clip];                                         // "HeaderLeft" -> "ICM_HeaderLeft"
    if (alt != undefined && ICModern.read() == 1) { mc = this.ic_LegacyAdd(alt, var, size, init); if (mc) return mc; }
    return this.ic_LegacyAdd(clip, var, size, init);                   // Legacy: the original call, unchanged
};
ASSetPropFlags(ic_proto, "ic_LegacyAdd,AddChildFromLibrary", 1);       // not enumerable, like class methods
```

The instance name, the init object and the class stay the same, so WrapperMain's casts (`HeaderLeft(...)`: AS2's
cast returns the object only if it is an instance of the class) and every later call work on the twin. If a twin
cannot be attached the Legacy symbol is (tested). The preference is read at every swapped attach (a cheap
`GM_Options` query), so a change applies to the next attach.

**Where the hook comes from.** Each rebuilt movie gets ONE `DoInitAction` (on an exported empty sprite
`ICM_Init_<DID>`, like the library's `__Packages` stubs, so it runs whether or not the sprite is ever placed) that
includes `common/rebuild.as` (the wrapper, installed once), then `Object.registerClass("ICM_X", <the Legacy class>)`
for every new symbol and `ic_Swap("<Legacy linkage>", "ICM_X")` for the twins. Init actions of the screen movies
run when WrapperMain's movie (`0x20000075`) imports them, before its `OnLoadComplete` attaches the header: the
Legacy header's own `registerClass` init actions must have run by then too, or HeaderLeft would have no class [C by
that evidence; P that ours run in the same pass]. Safety net: if a rebuilt movie's init action finds the Legacy
header already attached while the preference is Modern, it switches at once (`ICModern.rebuild`).

**Why a new export is found.** `0x20000075` imports a single dummy symbol from each screen movie
(`Import_VeteranLanding`, `Import_Login`, `Import_Header`, ...) yet attaches `"VeteranLandingScreen"`,
`"HeaderLeft"` ...: GFx resolves `attachMovie` names through the movies a movie imports from, not only its own
import list [C: that is how Legacy works]. A new export in the same movie is found the same way [P].

**What a twin must hold.** The class's own code (decompiled library, `re-work/ui-as2/.../__Packages`) lists every
instance it reaches; the twin places a child under each of those names (section 3-7 list them). A child is one of:

- our own symbol linked to the SAME class as the Legacy child (`ICM_PVPLauncher` = `PVPLauncher`, `ICM_PlayButton` =
  `MissionTypeButton`, ...), with our art and its own required children (recursively);
- the Legacy placement's own character and clip actions (`copy`): data widgets whose look is the game's data (the
  calling card avatar, champion / map images, achievements, level rewards, accolades, stolen power, star, locks);
- a `UIWidget_Text` (the movie's own import of `0x20000000`) with the game's template parameters (`iprp_Template`,
  colour, alignment): the game's fonts, our size / colour / box; `TextButton.Text` and the class code fill them;
- an empty clip where the class only toggles `_visible` / `gotoAndStop` on something we do not want (Legacy bump
  backgrounds, the Legacy home button, ring masks).

**Buttons.** Our buttons are CLIK buttons of the game's classes (`BasicButton`, `TextButton`, `MissionTypeButton`,
`CheckBoxButton`): a sprite with one frame per state, labelled `up` / `over` / `down` / `disabled` (+ `selected_*`
for check boxes and tabs), each ending in `stop()`; `Button.setState` plays the labels of `stateMap` from the last to
the first (`release` -> `over`, `out` -> `up`, `kb_*` ...) and ignores missing ones, so four labels suffice. The label
is a `UIWidget_Text` named `m_wtText` placed on frame 1 (kept by every frame); the component parameters are the
game's own (`autoSize none`, `soundMap`, `Text`, `toggle`, tooltip ids), written as `on(construct)` in the Flash
IDE's order.

**Meters.** `SimpleMeter.m_mcMeter` and `ProtectorLevelDisplay.m_Mask` are frame-driven (`gotoAndStop(n)`): our
meters are 100 / 101-frame sprites, each frame the same fill shape scaled to its value (inverted for SimpleMeter:
frame = 100 - percent).

**Two traps found on the way** [C, library code]:

- `UIWidget_Base.CreatePosIfNeeded` (run from the constructor) records `getBounds(this).xMax / yMax x placement scale`
  as the widget's size and **resets `_xscale` / `_yscale` to 100**. `UIWidget_Text` and `utils.Icon` draw into that
  size (so a text box or an image is sized by the placement scale, as Legacy does), but composite widgets
  (`VeteranAchievement`, `VeteranLevelReward`, `Accolades`, `CallingCardDisplay`) keep their authored size: they are
  placed at 100 % and scaled by our frame scripts once built.
- Liquid layout (`LiquidNode.ComputeNewPosition`): an attachment `loc: "center"` puts the origin at the container's
  centre whatever the widget's size; `"same"` on the right / bottom edge uses the widget's own measured width /
  height (`xMax`, `yMax` of its bounds). So the screens (centred) can draw anywhere, `HeaderRight` hugs the right edge
  by its own `xMax` (an invisible author box sets the margin), and `FooterLetterBox` must stay 52 px tall
  (`FooterBkgd.GetFooterHeight()` = `_height`).

**Art.** DefineShape3 polygons from `common/rebuild_kit.py` (chamfered "rounded" corners, pointed ends, gradients as
bands, circles, icons). One shape per polygon inside the art sprite (overlapping polygons stack on the display list
instead of sharing one shape, where fill sides are ambiguous); a polygon may carry holes (`frame()`: outer clockwise +
inner counter-clockwise in one shape) so translucent cards keep a crisp 1 px border without tinting their inside.

**Legacy stays byte-identical** [C, tested]: no Legacy symbol is edited; every original tag of the five movies is
byte-identical and in order; ours are inserted before the movie's last `ShowFrame` (shapes, sprites, one
`ExportAssets`, one `DoInitAction`), with free character ids. With `User.InterfaceStyle` = 0 the hook only forwards
calls.

**Live switch** (the settings check box, `0x2000005F`): `ICModern.write(style)` then `ICModern.rebuild()`: remove and
re-attach the header parts, footer parts, the legal footer and the landing nav through WrapperMain's own `Attach*`
methods (the hook picks the look), then `LoadNewScreen(current)` if the current screen has a twin (its normal
transition re-applies the header / nav settings), else `SetScreenSettingsOnTransitionIn` + nav show / hide +
`OnSized`. Removal is the game's own path (`removeMovieClip` -> `onUnload` -> `OnUnloadComplete` unregisters the
notices; the liquid node detaches) [P: never done to header parts by the game itself].

## 2. Files

| Path | What |
|---|---|
| `ui/modern/common/rebuild.as` | the hook, `ic_Swap`, `ICModern.rebuild`, the safety net |
| `ui/modern/common/rebuild_kit.py` | colours, shapes, text / button parameters, shared widget art (icons, meters, pointed / .pts buttons, glass cards) |
| `ui/modern/movies/0x20000077_header/` | `module.py` (SYMBOLS), `header_bkgd.as`, `header_left.as`, `header_center.as`, `header_profile.as` |
| `ui/modern/movies/0x2000006D_login/` | `module.py`, `login_screen.as` |
| `ui/modern/movies/0x200000A4_veteran_landing/` | `module.py`, `veteran_landing.as`, `veteran_map.as` |
| `ui/modern/movies/0x200000A8_landing_nav/`, `0x20000090_footer/` | `module.py` |
| `tools/ui_build.py` | `SYMBOLS` support: `build_symbols`, `compile_symbols`, `init_source`, `art_groups` (`ui-modern-build.md` 11) |
| `tools/gfx_edit.py` | `frame_label`, `remove_object2`, `export_assets`, `define_sprite_frames`, `construct_source`, holes in `define_shape3` |
| `tools/ui_preview.py` | PNG preview of the rebuilt screens from their source |
| `tests/test_ui_rebuild_home.py` | section 8 |

## 3. Header `0x20000077` (stage px; bar 0..64)

| Twin (class) | Children (name: what) | Layout |
|---|---|---|
| `ICM_HeaderLetterbox` (HeaderBkgd) | `m_mcWideBumpBG` / `m_mcMediumBumpBG` / `m_mcBumpBG` / `m_mcFlatBG`: empty (SetBumpType); `m_icBar` rgba(13,23,41,0.86) x -2000..3280, `m_icRule` 1 px rgba(47,168,255,0.35) | bar hidden on the login screen (`m_ssData.m_bLogin`); 0.86 instead of the design's 0.6 glass: in game the bar sits on the champion art |
| `ICM_HeaderLeft` (HeaderLeft) | `m_icLogo` (copy of the Legacy `m_mcLogo`: the game's `infinite_crisis_logo_small`, 352 x 64, at 45 %), `m_mcLogo` empty (the class fades it), `m_hpProfile` = `ICM_HeaderProfile`, `m_hcTraineeHeaderCurrency` = `ICM_CurrencyPills` | logo at (21, 17.5); on the login at (43, 34) x 72 % (top of the login column); profile / trainee pills right-aligned to the help button minus 14 px, every frame |
| `ICM_HeaderProfile` (HeaderProfile) | `m_hcHeaderCurrency` = `ICM_CurrencyPills` (HeaderCurrencyDisplay: `m_wtCurrency` Merits, `m_wtCrisisCoins`); `m_ccDisplay` copy (avatar, scaled 31 % by `header_profile.as`) in an accent box; `m_wtAccountLevel` in a badge under it; `m_wtDisplayName`; "ONLINE"; `m_pldLevelDisplay` = `ICM_ProtectorLevel` (`m_BaseRing` / `m_MaskedRing` empty, `m_Mask` = 101-frame bar); `m_ccDisplayBtn` = invisible BasicButton over avatar + name (opens the calling card dialog: the profile); `m_btnRanked` / `m_btnRankedDisplay` empty | pills 0..270, avatar 282..322, name 332..; the name's text end is put 14 px left of help |
| `ICM_HeaderCenter` (HeaderCenter) | `m_pvpPlay` = `ICM_PVPLauncher` (`m_btPlayGame` / `m_btnGroup` = pointed MissionTypeButtons 133 x 46 / 180 x 46, `m_btnGroupCancel` / `m_btnGroupSmall` copies); `m_miMatchmakingIndicator` copy (y 58: hangs under the bar while queued); `m_Alert` copy; `m_btnHome` empty; `m_icNavHome` / `Champions` / `Amplifiers` / `Store` = `ICM_NavLink` (TextButton: hit box, underline, label) | PLAY at screen-left + 197; links after it (+25), gap 22, measured from `textWidth`; if they would reach the profile the gap shrinks to 10 then the row scales (>= 72 %); links shown when the Legacy store button would be (`m_HeaderRight.m_mcNavButtons._visible`) for veterans; white + underline for the current screen, white on hover, else #A9BBD3 |
| `ICM_HeaderRight` (HeaderRight) | `m_mcNavButtons` = `ICM_NavButtons` (NavButtons, empty: our STORE / HOME call its `OnStorePress` / `OnHomePress`, which ask about unsaved amplifier changes); `m_btHelpButton` / `m_btSettingsButton` / `m_btExitButton` = 36 px icon buttons (the design's 40 px square: #101D31, border #1E3350 / accent on hover) with the Legacy tooltip ids | author box 135 wide: right margin 10 + 11 px |

Links: HOME -> `NavButtons.OnHomePress`, CHAMPIONS -> `TransitionToCharacters`, AMPLIFIERS ->
`TransitionToAmplifiers`, STORE -> `NavButtons.OnStorePress`; PLAY, the group buttons, help, settings, exit and the
avatar are the class's own handlers.

## 4. Login `0x2000006D` (stage px; the screen symbol's origin is the stage centre)

`LoginScreen` reaches `m_wtWBID`, `m_wtPassword` (copies of the Legacy input widgets: `InputSmall`, password flag),
`m_wtError`, `w_tRegion` (copy), `m_btnLogin` (MissionTypeButton), `m_btnRememberWBID` / `m_btnDisableAnimations`
(CheckBoxButton, `toggle`), `m_btnResetPassword` / `m_btnSignUp` / `m_btnReplay` (TextButton); `m_mcConnectingAnim1/2`
are absent in Legacy too.

| Element | Where |
|---|---|
| column rgba(9,16,29,0.92), 1 px #1E3350 right edge | x 0..391, full height (and beyond, for letterboxing) |
| logo (the header's, moved) / "Sign in" | (43, 34) / (43, 90) |
| USERNAME / input 305 x 39 (#0A1220, border #284566) | 132 / 150 |
| PASSWORD / input | 205 / 223 |
| Remember me / Disable menu animations (16 px boxes, accent + tick when on) | 272 / 298 |
| LOG IN: pointed 305 x 50, accent edge, #123A5E -> #0B2440 | 330 |
| error line (the class shows it) | 388 |
| Forgot password? / Create account / Replay intro (#7CC8FF, hover #B5E0FF) | 470 / 470 / 498 |
| REGION + the region name | 532 |
| NEWS / PATCH / SERVER cards 258 x 66 (our own short texts) | x 434.., y 470 |

The game's legal block (`LogoFooter`, shown on the login only) still covers the bottom ~145 px over the whole width;
everything above stays clear of it. Help / settings / exit stay at the top right (the header). The right side is the
game's login animation (WrapperBackground).

## 5. Home body `0x200000A4`

`VeteranLandingScreen` (WrapperScreen) > `m_scVeteran` (ScreenComponent: `m_mcContents`, `m_mcFrame`,
`m_mcFrameHot`, `m_mcHotEdge`) > `m_mcContents` = `ICM_VeteranLanding` (VeteranLanding: `m_vlr0-2`, `m_va0-2`,
`m_vcChampion`, `m_vmMap`, `m_btnAchievementsViewAll`, `m_btnChampionsViewAll`, `m_wtUpcomingLevel`,
`m_mcDivider1-2`). `ICM_VeteranChampion` (VeteranChampion: `m_iMiniWallpaper`, `m_mcCharLevelFrame` (empty),
`m_smXPMeter` (`ICM_XpBar`: SimpleMeter + 100-frame inverted fill), `m_spbStolenPower`, `m_bsStar`, `m_ricIcon`,
`m_mcIconLock`, `m_mcSPLock`, `m_wtChampionName`, `m_wtSkinName`, `m_wtLevel`, `m_wtXP`, `m_wtUpcomingRewards`);
`ICM_VeteranMap` (VeteranMap: `m_iIcon`, `m_mcTutorialIcon`, `m_mcDraft`, `m_mcRanked`, `m_mcRobotIcon`,
`m_mcMapTypeLabel`, `m_mcMapTypeIcon`, `m_wtSubtitle`, `m_wtLevel`, `m_btnMapsPlayAgain`, `m_accolades`).

| Block | Box (stage px) | Content |
|---|---|---|
| shade | whole screen | navy, 82 % on the left fading to 12 % on the right, over the champion wallpaper (WrapperBackground: the game's art) |
| hero | 21..760 x 106..356 | radial-like navy gradient card; LAST CHAMPION PLAYED; name (TitleRegularLarge 36 px); skin; LEVEL n + XP bar + xp / next; next rewards (stolen power, star, icon + locks: the game's widgets); the champion's mini wallpaper (the game's loader, 209 px) on the right in a thin accent frame; PLAY NOW (.pts accent, dark text) and VIEW CHAMPION (.pts #1A2C47) |
| achievements | 772..1259 x 106..356 | ACHIEVEMENT PROGRESS, VIEW ALL (small .pts), the three VeteranAchievement widgets at 72 % |
| GAME MODES | 21..1259 x 394..520 | four glass cards (rgba(15,27,46,0.6), border rgba(47,168,255,0.22), lit on hover) with the game's map-type icons (this movie's shapes 76 / 72 / 70 / 74 = frames CA / GH / GD / CC of `m_mcMapTypeIcon`), name and a one-line description (the design's) |
| last map played | 21..630 x 532..660 | the map image (the game's loader), name, type icons / subtitle, accolades at 75 %, PLAY AGAIN |
| level rewards | 642..1259 x 532..660 | `m_wtUpcomingLevel` (the game's title), the three VeteranLevelReward widgets at 92 % with two dividers |

PLAY NOW and the four mode cards call the header launcher's `PVPLauncher.OnPlayClick` (trainee check, rejoin the
lobby room, `TransitionToEncounterSelectScreen`: the mode / map choice is the game's next screen); they hide /
disable while the header has no PLAY (queue, group, custom match).

## 6. Sub-nav `0x200000A8`

`LandingNav` reaches `m_btHomeButton`, `m_btnAchievements`, `m_btnAmplifiers`, `m_btnStats`, `m_btnCharacters`,
`m_btnRanked` (it sets `selected` on all six on every screen change). ACHIEVEMENTS / RANKED / STATS are `ICM_Tab`
(TextButton, 132 x 28, selected = accent underline on a navy pill) at stage (21, 70) / (161, 70) / (301, 70) over a
faint rule; HOME / CHAMPIONS / AMPLIFIERS are invisible buttons (the header has them). The same nav shows on the
champions, amplifiers, achievements, stats and ranked screens (still Legacy bodies), right under the Modern header.

## 7. Footer `0x20000090`

`ICM_FooterLetterBox` (FooterBkgd): navy strip rgba(13,23,41,0.86) 1280 x 52 with a 1 px accent top rule
(`m_mcFooterBG` empty). `ICM_FooterLogoLeft` (FooterLogoLeft): empty with the Legacy size as an invisible box.
FooterCenter (Training Mode switch) and FooterRight (contacts / notifications) stay Legacy.

## 8. Tests (`tests/test_ui_rebuild_home.py`, 630 checks)

- Modules: the five movies have twins for exactly their Legacy linkages, every symbol is `ICM_*`, linkage names are
  unique across movies (registerClass is by name), every script / construct block / init action compiles.
- Class surface: for every twin and every nested symbol, each instance name its class reaches (table `REQUIRED`, from
  the library code) exists, once, with the right kind (our symbol of that class or a subclass, the Legacy placement of
  the same name, a UIWidget_Text, any clip).
- Art: chamfer / band / clip helpers, frames with holes (opposite winding), one shape per group, every art round-trips.
- VM: the hook (Legacy forwards everything; Modern swaps only twins; a missing twin falls back; the preference is
  read at each attach; installed once); `ICModern.rebuild` (re-attach, reload a rebuilt screen, not another one,
  nothing in a match, the start-up safety net); header layout (PLAY position, links in order, current link underlined
  and white, hover, labels measured, shrink before the profile, hidden for trainees), header left (profile against
  help, logo on login), bar hidden on login; home (PLAY NOW / mode cards through the launcher, hidden / disabled in a
  queue, composite widgets scaled); login link hover; the settings box saves and rebuilds.
- Installed pack: deterministic build; per movie: record header kept, every original tag byte-identical and in
  order, additions only shapes / sprites / one ExportAssets / one DoInitAction before the last ShowFrame with free
  ids, original exports kept, exports = twins + init sprite, the init action on the exported init sprite registering
  every class and swap; copies keep the Legacy character and clip actions; texts are the movie's UIWidget_Text.

## 9. In-game test (tester)

1. Close the game. `python ic.py ui build` then `python ic.py ui apply` (expect "installed and verified").
2. Start, log in: the login and home must look exactly as before (Legacy is the default unless Modern was ticked
   with the earlier build: then untick it first, see 3).
3. Settings (gear) > UI > "Modern interface (beta)": tick it. The header, footer, sub-nav and the home switch at
   once to the rebuilt ones. Untick: back to Legacy at once.
4. In Modern click: PLAY (header), PLAY NOW, a game-mode card, VIEW CHAMPION, VIEW ALL, PLAY AGAIN, HOME /
   CHAMPIONS / AMPLIFIERS / STORE, ACHIEVEMENTS / RANKED / STATS, the avatar (calling card dialog), help, settings,
   exit (cancel), Training Mode, contacts. Join a group / queue once if possible (the return-to-group button and the
   matchmaking indicator).
5. With Modern ticked, quit and restart the game: the **login** must be the rebuilt one (navy column, LOG IN). Log in.
6. `python ic.py ui revert` when done (byte-identical original). Send screenshots (login + home, Modern and Legacy),
   `logs\server.log`, `logs\unhandled.log`.

What a wrong result would mean: Modern ticked but everything Legacy -> the hook is not installed (init actions of
imported movies not run, or run after the attach) or the new exports are not found from WrapperMain's movie (then
`attachMovie` returns undefined and the hook falls back to Legacy, by design); a part blank -> a required child or
class missing (compare section 3-7 with the class); text missing -> a template name; the login Legacy after a
restart -> the INI value is not read before the account (`ui-modern-home.md` 2); something misplaced -> a constant in
the module (sizes are the design's, positions from section 3-7).

## 10. Open points

- Never run in the client: GFx's handling of new exports in an imported movie [P], init-action timing [P], the live
  re-attach of header / footer / nav [P], CLIK buttons with four state frames instead of the game's 80 [P], the
  game's font metrics (the header measures its links; the cards use fixed boxes with ellipses).
- Text: the game's templates fix the font and size (H3 ~20, H4 ~15, TitleRegularSmall ~14, ToolTipSmall ~11,
  TitleRegularLarge 36: read from the Legacy screens, the template XML was not found); no letter-spacing.
- The home's mode cards all start PLAY (the game chooses mode and map on its next screen), not a specific map.
- Login rewards, the trainee landing, the Training Mode / contacts buttons, the legal block, the friends panel: Legacy.

## 11. Effort per further screen with this method

Measured on these five: the infrastructure (builder, hook, kit, preview, tests) is done; a screen is mostly reading
its class(es) for the instance names, laying out the design and writing a 20-60 line script for anything the class
does not do. Estimates for one person / agent, including the VM tests:

| Screen | Movies | Estimate |
|---|---|---|
| login rewards | `0x200000B1` (LoginRewards, RewardDay x 7, timeline) | 2-3 h |
| champions collection + champion info | `0x200000A5` (CharactersScreen, browser list items, ChampionDetailPanel) | 5-7 h (scrolling lists: list item renderers must be rebuilt as symbols too) |
| amplifiers | `0x20000094` (assembler, sets, lists) | 6-8 h |
| store | `0x2000007C` (a web page host: the page is `ics/store_web.py`) | 1-2 h for the frame, the page itself is HTML |
| profile / stats / achievements / ranked | `0x200000A3` / `0x200000A2` / `0x200000B2` / `0x200000A0` | 3-4 h each |
| champion select + lobby | `0x20000022` / `0x20000067` (big, many lists and state) | 8-12 h |
| dialogs | `0x20000080` (every dialog) | 1-2 h per dialog family |
| results / scorecard | `0x2000008C`, `0x2000009D`, `0x200000AD`, `0x200000AE` | 5-7 h |
| custom match / group / chat / contacts | `0x20000093`, `0x20000082`, `0x20000083`, `0x2000008B` | 3-5 h each |
| in-match HUD | 14 movies, two of them only in the tail layout | not with this method alone (the HUD shell is not attached through AddChildFromLibrary; needs its own switch) |
