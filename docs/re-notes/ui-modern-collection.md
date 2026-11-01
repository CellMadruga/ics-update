# The Modern UI, "collection" area: store, dialogs, champions + champion info, amplifier sets (2026-10-30)

Builds on `ui-modern-build.md` (pipeline, module convention, section 8) and `ui-complete.md` (the classes). Four
movie modules, one per movie, written in parallel with the other screen areas:

| Movie | Module | Symbols edited |
|---|---|---|
| `0x2000007C` store | `ui/modern/movies/0x2000007C_store/` | `StoreComponent` |
| `0x20000080` dialogs (every wrapper dialog, incl. purchases and the profile's `CallingCardDialog`) | `ui/modern/movies/0x20000080_dialogs/` | 13 dialogs + `ProtectorIconSubmenu` |
| `0x200000A5` champions (collection + champion info / biography) | `ui/modern/movies/0x200000A5_characters/` | `CharacterBrowser`, `CharacterBrowserButton`, `ChampionDetailPanel` |
| `0x20000094` amplifier sets | `ui/modern/movies/0x20000094_amplifiers/` | `Assembler`, both slot kinds, library card, set rows, save ribbon, set-icon menu |

Tags: **[C]** confirmed (movie bytes, the decompiled library in `re-work/ui-as2/`, the build, the as2c VM),
**[P]** probable, **[G]** guess. Nothing here has run in the real client yet (section 7).

## 0. Short version

- In **Legacy** nothing original is written (VM-tested for every edited symbol: no write to any original instance,
  none of our clips shown, no notice sent).
- In **Modern** the scripts only change originals' alpha, colour transform (`flash.geom`, the library's own way, as the
  header's PLAY), depth (one `swapDepths` per panel, see 0.1) and text colour (`m_tfText.textColor`); the champion
  filter also moves / hides the grid buttons while a filter is active. Switching back to Legacy live restores all of
  it (VM-tested: depths, alphas, colours, positions, visibility).
- Every class, instance name, handler and `registerClass` is kept byte-identical (`tests/test_ui_collection.py`).

### 0.1 The one trick: a panel under the content when the Legacy background is a shape

The Legacy backgrounds of the dialogs and of the champion info panel are **plain shapes** (DefineShape with a bitmap
fill) at the symbol's lowest depth, with the content starting at the very next depth: no script can reach a shape and
no depth is free between it and the content. Our panel art is therefore placed at a free (high) depth and, in Modern,
`swapDepths` with the symbol's lowest named instance: the panel lands right above the background, that instance goes
to the panel's old depth (still above the panel, now on top of the others). Undone when switched back. In the
dialogs the swapped instance is the close X or the title (on top is harmless); in `ChampionDetailPanel` it is
`m_btnSkin0` (nothing overlaps it); in `CharacterBrowser` the panels swap with the scroll view and the text (they
stay under the detail panel). Where a free depth sits right above the background (`StoreComponent` 2, `Assembler` 2,
slots 2, rows 2 / 3) the art is just placed there, no swap.

## 1. Store `0x2000007C` (`store_component.as`)

The store is a CEF web page in `UIWidget_Browser m_wbBrowser` (800 x 600 scaled 1.6 x 1.03 = the whole 1280 x 618
screen) [C]. The page is served by this server (`ics/store_web.py`, `[ics] store_page_style = "cards"`: card grid with
art, tabs, search, prices in both currencies). The movie only frames it:

- `m_icStoreFrame` at the free depth 2 of `StoreComponent` (above the Legacy frame, an unnamed sprite at depth 1,
  1280 x 615 at (-2, -2); under `m_mcContents`): navy panel, 2 px accent border, accent rule at the top; it follows
  `m_mcContents._visible` (Store hides itself on an HTTP error);
- the loading cover's backing (`m_mcContents.m_cbLoadingCover.m_mcBacking`) flat navy (colour transform 0 x + navy
  offsets), the close X (`m_btnContinue`) muted blue.

The browser covers the frame once the page has drawn, so the store's Modern look (section tabs on the left,
"hide owned", pointed price chips Merits blue / Crisis Coins gold, navy palette) **is the web page's job**: see 8.

## 2. Dialogs `0x20000080` (`dialog.as`, one script for all)

Edited: AmplifierPurchaseDialog, AmplifierPurchaseCompleteDialog, AssemblerUnsavedChangesDialog (class
SaveDiscardCancelDialog), BrowserErrorDialog, CallingCardDialog, ConfirmationDialog,
CustomMatchExitConfirmationDialog, DualCurrencyPurchaseDialog, DualCurrencyPurchaseCompleteDialog,
GroupExitConfirmationDialog, GroupInviteDialog, ReportAPlayerDialog, TextEntryDialog and the calling card's icon
picker ProtectorIconSubmenu. Not edited: MajorUpdateDialog (full-screen news, background 1280 x 544 with three info
boxes as unnamed shapes), BrowserDialog (full-screen web page), MovieDialog (no placements).

Per dialog (instances looked up by name, skipped when absent):

- `m_icPanel`: the dialog's own panel art, drawn at its Legacy background's bounds (the DefineShape bounds + the
  placement; 4 px inset for the bitmaps' soft edge): navy 94 %, notched corners, 2 px `#2FA8FF` border, a lighter
  title band (50 px) with an accent rule. Swapped under the content (0.1). BrowserErrorDialog's background is a named
  clip (`m_mcBkgd`): it is faded to 0 as well;
- price chips drawn in the panel (pointed, gold / merit outline) behind the cost texts: DualCurrencyPurchaseDialog
  (Crisis Coins at (-40, -101)-(102, -67), Merits at (-38, 45)-(102, 79)), AmplifierPurchaseDialog and
  AmplifierPurchaseCompleteDialog (Merits);
- buttons: primary (`m_btnConfirm`, `m_btnUnlock`, `m_btnSave`, `m_btnContinue`, `m_btnOK`, `m_btnCloseTextButton`,
  `m_btnLeaveAndCancel`, `m_btnUnlockSoft`) electric blue, `m_btnUnlockHard` gold, secondary (`m_btnDiscard`,
  `m_btnCancel`) and the close X muted; each action button gets a pointed outline + glow (`m_icRing0..2`, sized every
  frame around the button's bounds, hidden with it);
- texts: `m_wtHardCost` / `m_wtHardBalance` gold `#F2B33D`, `m_wtSoftCost` / `m_wtSoftBalance` / `m_wtCost` /
  `m_wtBalance` merit blue `#3FA9FF`, `m_wtTitle` near-white; re-applied every frame (UIWidget_Text html texts carry
  their own colour, `UIWidget_Text.Text` setter) [P that textColor sticks between frames];
- CallingCardDialog: the XP bar fill (`m_xpDisplay.m_mcBar`) blue.

## 3. Champions `0x200000A5`

Structure [C]: `CharactersScreen > CharactersComponent > CharacterBrowser` (d1 scroll view
`m_svCharactersScrollView` at (23, 148), 752 x 480; d2 `m_CharText`, the right-hand text column; d5
`m_cdpChampionPanel`). The class builds one `CharacterBrowserButton` per champion inside the scroll view
(`AddChildFromLibrary`, 5 columns, 150 x 173 px, `INITIAL_Y` 5) in the ButtonGroup `m_btngCharacterButtons`, plus
`ClipSizerShape` fixers; a click shows the detail panel and hides the scroll view and the text.

`characters_browser.as` (Modern):

- `m_icGridPanel` / `m_icTextPanel`: translucent navy panels (62 %) swapped under the scroll view / the text (0.1),
  sized every frame around them (`K_GRID_PAD`, `K_TEXT_PAD`), hidden with them;
- search: `m_icSearchPlate` (pointed plate) + `m_icSearch`, a new instance of the library's `UIWidget_Text` with the
  game's own `InputSmall` template (what the amplifier screen's `m_wtSearch` uses; its `on(construct)` sets the
  template, colour and the size through the creation scale, `UIWidget_Base.CreatePosIfNeeded`) + the hint
  `m_icSearchHint` ("SEARCH", shown while the field is empty). The text is read every frame (`m_tfText.text`);
- role pills `m_icRole0..5`: new instances of the game's `MediumTextButtonLearn` (the detail panel's CLOSE button)
  scaled to 22 px tall like the header's nav; `m_icRole0` = ALL, the others get the roster's distinct roles: for each
  grid button `GM_Character.SendQuery_InqCharacterRoles(characterData.didPregameLight)` (as CharacterPreview asks;
  cached per champion), keyed by role icon DID, labelled with the client's own role name (`asiName`). Active pill
  blue, others muted;
- filtering: matches are packed into the class's own slots (`CharacterBrowser.getX/getY` maths from its statics), the
  others hidden and parked at slot 0, the fixers parked too, then `SetInnerSize` (as `CreateCharacterButtons`); ALL +
  empty search puts every moved button back to its `listIndex` slot. Nothing is moved while no filter is active; a
  rebuilt grid (new ButtonGroup or count) re-scans the roles and re-applies the filter.

`character_button.as`: an accent frame around the portrait (`m_icCardFrame`, free depth 16) and a navy name band
under the name (`m_icNameBand`, free depth 26); the badges (owned, for sale, free, level frame, progress) are the
game's.

`champion_detail.as` (ChampionDetailPanel) [C structure]: the champion's splash is the wrapper background
(`UpdateWallpaper -> WrapperMain.m_wgWrapperBackground.SetDynamicCharacter`), so it already fills the right side. The
Legacy frame is one DefineShape2 at depth 2 spanning (65, 75)-(1177, 524) (left info column + skins row).

- `m_icDetailPanel`: navy panels over the info column (62, 74)-(506, 526) and the skins row (782, 411)-(1182, 526)
  (below the skins title plate at (792, 379), which stays), swapped to `m_btnSkin0`'s depth (0.1);
- BIOGRAPHY: `m_icBioButton` (a `MediumTextButtonLearn` like CLOSE, same height, just left of it) calls the panel's
  own `OnDrawerClick` = opens / closes the biography drawer `m_mcBio` (the movie's own lore text, `Character_About`);
- abilities: key letters P Q W E R (`m_icKey0..4`, UIWidget_Text clones, on `m_icKeyChip0..4` chips) at each ability
  icon's bottom-right corner (`m_spSkillPreview0..4` = Passive, Skill1..3, UltimateAttack, `UpdateSkills`); the
  descriptions stay in the icons' tooltips;
- arrows (`m_btnNext/Prev`, `m_btnSkinNext/Prev`, `m_btnAmpNext/Prev`) blue, CLOSE muted, CLOSE and BIOGRAPHY outlined,
  XP meter fill blue, `m_wtChampionSubTitle` / `m_wtChampionSubTitle2` blue.

## 4. Amplifier sets `0x20000094`

`Assembler` [C]: d1 builder base (unnamed sprite, 563 x 452 at (161.6, -2)), left column art at d3 / d4 / d5 / d8
(unnamed), the sets list `m_svAmpSets`, search `m_wtSearch`, mod slots `m_asAmplifierSlot0..2`, augment slots 3..6,
CLEAR / SAVE / REVERT, name, set icon + menu, hero graph, library `m_ali0..7` with MODS / AUGMENTS tabs and page
arrows, the selected item's texts at the right (d215 / d216, unnamed). Because the backgrounds and labels are
unnamed the **layout stays** (sets left, editor top, library below, item text right); Modern restyles it in place:

- `m_icPanels` at the free depth 2 (right above the builder base, under everything else): three navy columns with
  accent borders (left (-36, -6)-(164, 452), centre = the builder base with an accent rule above the library at y 146,
  right (764, -50)-(1164, 466));
- `m_icSearchPlate` at the free depth 6 over the Legacy search box (between its background at 5 and the field at 7);
- SAVE blue, CLEAR / REVERT muted, all three outlined (`m_icRingSave/Clear/Revert`); MODS / AUGMENTS tabs, page arrows
  and the set-icon menu button blue; page number blue, set name near-white;
- slots (`amp_slot.as`): `m_mcBkgd` darkened navy, an accent circle (augments) / notched square (mods) at the free depth
  2, kept around the slot art (it loads late: re-sized every frame);
- library card (`amp_list_item.as`): thin accent frame at the free depth 8, SLOT / merit buttons blue;
- set rows (`amp_set_row.as`): `AmplifierSetListItem` navy row with an accent bar at depth 2 (later frames use 3:
  the highlight stays above it), `AmplifierSetForSaleListItem` the same at depth 3 with Merits / Crisis Coins chips
  behind the prices (texts coloured), `SaveMiniRibbon` and `AmplifierSetIconSubmenu` navy plates at depth 2.

## 5. Shared helpers of the area

- `ui/modern/common/collection_lib.as` (included by every script of the four modules after `common.as`):
  `icc_Install(this, cfg)` with `art` / `swap` / `fade` / `tint` / `colour` / `ring` / `hook` / `ticker`, the Legacy
  restore (`icc_wasModern`), and the palette's colour transforms (`icc_kAccent`, `icc_kGold`, `icc_kMuted`,
  `icc_kNavy`).
- `ui/modern/common/collection_art.py` (`import collection_art as ca` in the four `module.py`): `panel`, `plate`, `chip`,
  `button_ring`, `ring`, `notched`, `frame`, `circle_ring`, `accent_rule` and the tint constants (`K_TINT_*`).
- Both would belong in `ui/modern/common/` (section 8).

## 6. Tests

`python tests\test_ui_collection.py [rp folder]` (838 checks): builds only these four modules (+ common) from a
scratch copy into memory, checks CRCs, determinism, every original top-level tag / placement / name / clip action /
registerClass kept in order, exactly the module's additions, art transparent at placement, every script compiles;
then runs every edited symbol's script in the as2c VM against mock clips made from the symbol's **real placements**
(nested local sprites expanded, text widgets with a TextField): Legacy writes nothing original, Modern writes only
alpha / colour transform / depth (plus the grid buttons' position / visibility while filtering), live switch back
restores everything; and the screen behaviour (dialog panel under the content + outlines + currency colours, store
frame, champion role pills / search / ALL / Legacy reset on a made-up roster, BIOGRAPHY -> OnDrawerClick, key letters,
amplifier panels / outlines / slot rings / price colours). `python tests\test_ui_build.py` passes except its manifest
check, which lists only the header and settings movies (section 8).

## 7. In-game test (tester)

`python ic.py ui build` + `ui apply` (game closed), Modern ticked in Settings > UI, then:

1. STORE: navy frame while the page loads, close X muted blue, the page itself unchanged (8).
2. Dialogs: buy a champion / skin from the champions screen (DualCurrencyPurchaseDialog: navy panel, gold / blue
   chips and texts, gold / blue buttons with outlines), an amplifier (AmplifierPurchaseDialog), leave the amplifier
   screen with unsaved changes (Save / Discard / Cancel), the avatar (CallingCardDialog: panel, blue XP bar; the icon
   picker), a group invite. Every button must still work.
3. CHAMPIONS: navy panels behind the grid and the right text; SEARCH field (click, type a name: the grid filters as
   you type) and the role pills (each shows only that role; ALL resets); cards with an accent frame and a name band;
   open a champion: navy info column and skins row over the splash, P Q W E R on the abilities, BIOGRAPHY opens /
   closes the lore drawer, arrows / skins / CLOSE work.
4. AMPLIFIERS: navy columns, blue SAVE with an outline, circle / square slot outlines, card frames, set rows; drag /
   slot / save / revert / buy work.
5. Untick Modern on any of these screens: back to Legacy at once (or on the next screen).

What could go wrong and what it would mean: a dialog or the info panel with its content hidden -> GFx's
`swapDepths` with a timeline instance behaves differently (fallback: `K_PANEL_SWAP` 0 in `collection_art.py` hides those panels and swaps nothing);
panels misplaced / the Legacy frame peeking out -> the rectangles in the modules (`DIALOGS`, `DETAIL_*`, `LEFT` /
`CENTRE` / `RIGHT`) need the tester's screenshot; no search field or a tiny one -> the creation-scale sizing of
`UIWidget_Text` (`K_TW_SX`), or `InputSmall` needs focus handling; pills without text -> role names are tokens the
button does not resolve (then use the icons); colours not sticking -> html text colours (then tint the widgets).

## 8. Not possible here / shared changes needed

- **Store design** (left section tabs incl. Amplifiers and Set slots, "hide owned", pointed price chips, navy palette):
  the content is `ics/store_web.py`'s page, outside this area's files. The server already has the account's
  `User.InterfaceStyle` (uploaded with `0x216E`, `ics/account.py set_preference`), so `render_cards` can switch to the
  Modern palette and layout when it is 1. Suggested owner: whoever owns `ics/store_web.py`.
- **Champion "base stats tiles"**: the detail panel gets no stat data (its notices carry the power set / light / heavy
  records only); the attack / health / power bars exist in the amplifier screen's hero graph (`0x2000005E`). Would need
  a new query or the hero-graph movie imported: not done.
- **Inline ability descriptions** under P / Q / W / E / R: needs a text area per ability and the tooltip data
  (`GM_Skill.SendQuery_InqSkillToolTipInfo`); the tooltips already show them. Possible next step.
- **Amplifier layout as designed** (sets left / editor centre / library right with Augments / Mods tabs): the
  Assembler's backgrounds and labels are unnamed, so moving the named parts would leave them behind; restyled in place.
- **MajorUpdateDialog / BrowserDialog**: not edited (full screen, unnamed art).
- **Shared code**: `collection_lib.as` / `collection_art.py` moved to `ui/modern/common/` (integrated 2026-10-30, `ui-modern-build.md` 10); `as2c` has no
  `for (k in o)` (the dialogs list their instance names instead); `tests/test_ui_build.py`'s
  `check("install: manifest movies", set(man["movies"]) == {"0x20000077", "0x2000005f"})` fails as soon as any area
  module exists: it should check a superset / every module's DID.
- Size: the four movies grow 21 -> 28 KB, 67 -> 199 KB, 62 -> 96 KB, 46 -> 99 KB (each symbol carries its own copy of
  the helper code, 6-13 KB of AVM1; a shared `DoInitAction` would need a builder change).
