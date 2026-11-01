# Modern UI: champion select, skin carousel and loading screen (2026-10-30)

Builds on `ui-modern-build.md` (pipeline, module convention, section 8) and `ui-complete.md` (classes). Three movie
modules: `ui/modern/movies/0x20000022_champselect/`, `0x20000067_lobby/`, `0x20000020_loading/`. Test:
`python tests\test_ui_champselect.py` (170 checks: build of only these three modules on the installed pack, originals
kept, scripts in the test VM in Legacy and Modern, restore on switching back). Nothing here has run in the client yet.

Tags: **[C]** confirmed (code, data, the test VM, a build on a copy of the pack), **[P]** probable, **[G]** guess.

## 1. Which movie draws what [C]

Read from the library classes (`re-work/ui-as2/.../__Packages/gameplay/lobby`, `charPicker`, `state`) and the movies:

| Screen part | Movie / symbol | Class | Notes |
|---|---|---|---|
| Lobby root | `0x20000067` `LobbyWrapper` | `gameplay.lobby.LobbyWrapper` | depth 1 background sizer, 3 the scaling target where `PvPLobby` is attached |
| Champion select | `0x20000067` `PvPLobby` (centred, lobby = stage - (640, 360)) | `PvPLobby` | `m_tdLeftTeam` (-640, -320) = team A, `m_tdRightTeam` (444, -320) = team B, `m_wtCharPickerAttachTarget` (-640, -360) gets `CharacterPicker`, `m_wtSecondaryPowerDisplayTarget` / `m_wtAmplifierDisplayTarget` (-453, -253) get `SecondaryPowerDisplay` / `AmplifierSetPicker` (`AttachPickerUIs`), `m_cChat` (imported `Chat` of `0x20000083`, 392 x 160 at stage 187, 553), `m_mcCurtain` = the loading screen |
| Player card (select) | `0x20000067` `LobbyPlayerDisplay` (180 x 112) | `LobbyPlayerDisplay` | portrait (character icon, 110 x 104) at x 63 for team A / 8 for team B, Stolen Powers + roles at 11 / 121, ready mark at 5 / 154 (`Update*ForTeam`), player name only (no champion name) |
| Champion grid, preview, LOCK IN, skins | `0x20000022` `CharacterPicker` (stage coordinates) | `CharacterPicker` | `m_svCharButtons` (scroll view at 190, 131, 5 columns of 74 x 70), unnamed backdrops at depth 54 (`CharacterPickerBG` 392 x 296 at 187, 107), 56 (title widget), 57 (label); `m_cpCharacterPreview` (splash portrait at stage 502, 0; name / subtitle / skills / roles at stage 580-1060, 598-700); `m_rbLobbyLock` (220 x 60 at 268, 491); after lock-in the class hides the grid and shows `m_spSkinPicker` |
| Skins | `0x20000022` `SkinPicker` | `SkinPicker` | buttons `SkinButton_<did>` (128 x 128) in a 3-column grid (105 px) inside a masked scroll view at the grid's place; selected index `m_nSelectedButtonIndex`; a click sends `GM_Lobby.SelectCharacter` and the preview shows that skin's splash |
| Loading screen (PvP) | `0x20000067` `PVPCurtain` (the curtain, local = stage - (4, 1)) | `gameplay.lobby.Curtain` | two rows of five `CurtainPlayerDisplay` (240 x 262: frame 240 x 256, mini wallpaper portrait, name, champion, skin, percent text; the per-player meter is hidden by the class), map label / title in the middle, `m_smOverall` meter; `m_icMapFlavorImage` (the encounter's loading-screen image) only in the tutorial |
| "Loading..." while the HUD loads | `0x20000020` `LoadingMovie` / `LoadingMovieCurtain` | `LoadingIntoWorld` | a 3 KB shell: an unnamed `UIWidget_Text` "Loading..." at 1111, 667 (`MainHUD` attaches `LoadingMovieCurtain`) |

## 2. What Modern does [C in the VM, P in game]

All layout runs in `onEnterFrame` of our empty ticker clips (data arrives late; the class re-positions things on
events). Every original value written is remembered once per Modern session (`ic_Set`, keyed by `_target` + property)
and written back by Legacy (`ic_RestoreAll`), so a live switch restores the class's own layout. Original instances only
get `_x _y _xscale _yscale _width _height _alpha _visible` and a colour transform (LOCK IN); the map image gets one
`SetIcon` call. Legacy writes nothing to an original instance (tested).

### 2.1 Champion select (`0x20000067` PvPLobby + `0x20000022` CharacterPicker)

- **Lobby veil** (`LobbyWrapper.m_icVeil`, depth 2): navy 55 % between the lobby background and the lobby.
- **Team columns**: our team on the left (the two `LobbyTeamDisplay` swap `_x` when `m_nMyTeamNumber == 2`).
  Each card: our card art (`m_icCardBlue` left / `m_icCardRed` right, pointed toward the centre, team strip on the
  outer edge, depths 2 / 4 under the portrait), the Legacy frame `_alpha` 0, the portrait at the outer edge with a
  fade toward the centre (`m_icFade`, depth 6), powers / roles / ready mark on the inner side (the class's own team-B
  values for the left column, team-A values for the right), and the **champion / skin name** in a new text widget at
  the top of the card (`m_icChampText`, a clone of `UIWidget_Text` with our clip actions: template `SansSerifSmall`,
  `#9FD4FF`, box widened with `_xscale = 140` in `on(construct)`; text from `PropertySystem.InqPropertyDID(
  m_didPregameLight, Character_Name_Property / Character_Skin_Name_Property)`, as `CurtainPlayerDisplay` does).
- **Grid**: the Legacy backdrops (depths 54 / 56, reached with `getInstanceAtDepth(depth - 16384)`) transparent, the
  scroll view centred at x 640, top 192, over `m_icGridPanel` (navy, cut corners, accent rule). Label (57), help text
  and the draft "your turn" banner move with it.
- **Splash**: the preview portrait `_alpha` 40 behind the grid before lock-in, 100 after; `m_icSplashShade` darkens
  toward the bottom bar. The champion name / subtitle / skills / roles move as a group to the top right (right edge
  1075, top 62).
- **LOCK IN** centred under the grid (y 510), tinted electric blue (the header's PLAY transform), over the shared pointed
  plate `m_icLockPlate`; BAN (draft) follows it.
- **Bottom bar** (`m_icBottomBar`, stage 196-1084 x 552-716) with the chat on its left (nudged to x 204 over
  `m_icChatPanel`) and the Stolen Power + amplifier-set pickers moved by (418, 190) from their Legacy row (stage y 422)
  into it. Their pop-up menus move with them.
- **Timer**: a pointed plate `m_icTimerPlate` drawn in the lobby at lobby (0, -334) under the header (the header is
  attached above the lobby; its own symbol `LobbyHeaderCenter` has no free depth under its only child).
- **After lock-in**: the skins in one row centred at y 330 (all of them, the base included, as the class lists them):
  others 80 %, the selected one 104 % with the accent frame `SkinPicker.m_icSkinSelect`, unowned ones `_alpha` 45
  (owned = ownable state 1 / 3 / 6 / 9), over `m_icSkinStrip`; the scroll view's mask is opened to the row and its
  scroll reset. Clicking a skin is still `SkinPicker.OnSkinButtonClick`; the selected skin's splash is the preview
  (full alpha) behind.

### 2.2 Loading screen (`0x20000067` PVPCurtain + CurtainPlayerDisplay)

PvP only: in the tutorial (`m_wtMapTitleTutorial` visible or team 1 hidden) the original curtain is kept.

- Background: the encounter's loading-screen image (`EncounterManager.GetEncounterLoadingScreenImage(m_nEncounterID)`
  into `m_icMapFlavorImage`, the clip the tutorial curtain uses) under `m_icVeil`; `m_mcLoadingScreenBkgd`,
  `m_mcTitleBG`, the team labels and `m_smOverall` `_alpha` 0.
- Our team in a column on the left (x 22), the enemy on the right; cards 470 x 100, 108 px apart from y 92. Each
  card: `m_icCard` (depth 2), the portrait scaled to 100 px tall at the outer edge (level frame with it), `m_icFade`
  toward the centre, team strip (`m_icStripBlue` / `m_icStripRed`), name / champion / skin / Stolen Powers moved
  beside it, and a pointed bar (`m_icBarTrack` + `m_icBarBlue` / `m_icBarRed`, `m_icBarGreen` at 100 %) whose length
  is `m_nCurrentLoadingPercent`; at 100 % the percent text fades and `m_icReadyText` (a copy of it) says READY in green.
  Empty slots (`m_bPlayerJoined` false) show nothing.
- Map label + name centred at the top over `m_icMapPlate` (centred by `m_tfText.textWidth`), the overall pointed bar
  (`m_icOverallTrack` / `m_icOverallFill`, 760 px at y 650) from `m_nOverallLoadCurrent / m_nOverallLoadTotal`.

### 2.3 Loading into world (`0x20000020`)

A pointed navy plate behind "Loading..." (`m_icPlate`), the label white (its `m_tfText`, retried every frame until the
widget has initialised), an accent segment sweeping under it (`m_icSweep`).

## 3. Not done / needs more than these movies

- **Search box and role filter pills** over the grid: no text input exists in this movie (an input `TextField` needs
  a font GFx accepts at run time [G]) and the role of each champion needs `GM_Character.SendQuery_InqCharacterRoles`
  with a pregame-light DID while the grid buttons only carry `didVariant` (untested whether it accepts that) [P].
  Filtering itself would be easy (hide / re-position the `CharacterButtonTurbine_*` children, `SetInnerSize`), the
  labels could be cloned text widgets. Left out rather than shipping pills that do nothing.
- **Player name on the right, champion below it**: the name wrapper spans the card; it stays at the bottom and the
  champion line goes to the top. A real two-line block needs a narrower name widget (new placement with our clip
  actions, like `m_icChampText`) and hiding the original wrapper.
- **Tall loading cards**: five 240 x 262 cards do not fit a 720 px column, so the cards become wide rows (portrait
  100 px tall). Cropping the portrait into a tall strip needs a mask (`setMask`) on an original instance [G].
- **Chat contents** (`0x20000083`, another module) are not restyled here, only placed on a panel.
- **Map art in the centre**: the loading image is used as the full background (it is a full-screen picture); a
  separate centre picture would need new art.
- The Legacy team colours inside the class's own art (ready / unready marks, IsMe frame, team label frames) are kept.

## 4. Uncertain until the in-game test

- `getInstanceAtDepth` in GFx (the Legacy grid backdrops and the "Loading..." label are unnamed): if missing, the
  backdrops stay visible (our grid panel is under them) and the label keeps its grey.
- Whether `_target` is set on every clip we key (a missing one would merge saved values: restore could miss a write).
- The SkinPicker scroll view: opening its mask and resetting `m_mcInner` every frame; if the class's `OnSized` resets
  them the ticker writes them again next frame.
- The header-timer plate position (the header is scaled on its own, `K_TIMER_Y`), the chat's real bounds, the lock
  button's bounds (its glow child may make the plate large: `K_LOCK_PAD_*`), the mini wallpaper's size (assumed the
  frame's 240 x 256: `K_CPORT_SRC_H`).
- `SetIcon` of the loading image outside the tutorial (the same call the tutorial curtain makes).
All positions are module constants (`K_*` in each `module.py`).

## 5. Shared-code notes

- `tests/test_ui_build.py` `installed()` expects the manifest to hold exactly the header and settings movies (`check(
  "install: manifest movies", ... == {"0x20000077", "0x2000005f"})`): every new module makes it fail. It should compare
  with `layout.MOVIES`. With header + settings + these three modules everything else in it passes (205 / 206).
- The same test assumes one script per edited symbol and that any `m_ic*` placement without clip actions starts at
  alpha 0: a `copy` of a placement without clip actions would fail it, so these modules only copy placements that have
  clip actions and give every edited symbol a script.
- `ic_Set` / `ic_Orig` / `ic_RestoreAll` were repeated in three scripts; they could live in `ui/modern/common/`.
- Done (integrated 2026-10-30, `ui-modern-build.md` 10): the manifest check compares with the layout, scripts are keyed by (DID, symbol), a `copy` is
  checked as a moved copy of its template (no alpha-0 rule) and a symbol without a script is allowed;
  `ic_Set` / `ic_Orig` / `ic_RestoreAll` (+ `ic_self`, `ic_saved`, `ic_keys`) are `ui/modern/common/saved_values.as`,
  included by `character_picker.as`, `pvp_lobby.as` and `pvp_curtain.as`. The lobby's `Veil` art (12 000 px wide)
  was hit by the `define_shape3` long-edge bug and is fixed with it.
