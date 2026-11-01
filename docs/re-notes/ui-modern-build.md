# The Modern UI build pipeline (phase 0) and the first Modern screen (phase 1), 2026-10-30

> **Current method: rebuild (section 11, `ui-modern-rebuild-home.md`).** Sections 6 and 10 describe the first,
> restyle method (tint / move / cover the Legacy art), rejected by the tester on 2026-10-30; its modules are in
> `ui/modern/retired/`. Sections 1-5 and 8 (pipeline, switch, module convention) still apply.

Builds on `ui-modern-feasibility.md` (the same-length `ui-test` that ran in game on 2026-10-30) and `ui-complete.md`
(every class of the AS2 library). Goal: a second client UI, "Modern", next to the original ("Legacy"), chosen in the
options menu. This note covers the durable pipeline (repacker, AS2 compiler, build / apply / revert) and the first
screen built with it: the Settings switch and the Modern home header. Design: the approved canvas (dark navy
`#0A1220`, electric blue `#2FA8FF`, gold `#F2B33D` Crisis Coins, blue `#3FA9FF` Merits, pointed IC buttons,
translucent panels).

Tags: **[C]** confirmed (code, data, or a run on a copy of the pack / in the test VM), **[P]** probable, **[G]** guess.
Nothing below has run in the real client yet: the in-game check is the tester's (section 7).

## 0. Short version

| Piece | Where | State |
|---|---|---|
| Length-changing repacker for `0xA00000D0` | `tools/rp_repack.py` | **[C]** rebuilds the installed pack byte-identical (SHA-1 `6bd720aa...`) and round-trips longer records + appended DIDs on a synthetic pack |
| AS2 -> AVM1 compiler (pure Python) + a test VM | `tools/as2c.py` | **[C]** subset below; every script of the build runs in the VM against mock clips |
| SWF tag writing (placements, clip actions, shapes, sprites, DoAction) | `tools/gfx_edit.py` (+ readers in `tools/ui_mod.py`) | [C] |
| Build / apply / revert / status / list | `tools/ui_build.py`, `python ic.py ui ...` | [C] on a copy of the pack (apply -> modern, revert -> byte-identical) |
| Our UI source | `ui/modern/common/` (palette, shared art, `common.as`, `rebuild.as`, `rebuild_kit.py`, area helpers) + one module per movie in `ui/modern/movies/<did>_<name>/` (`module.py` + `*.as`), sections 8 and 11 | **2026-10-30, rebuild method (section 11):** header, login, home body, sub-nav, footer rebuilt from scratch + the settings switch (6 movies). The 28 restyle modules of sections 6 / 10 are retired to `ui/modern/retired/` (reference, not built) |
| Tests | `tests/test_ui_build.py` (117 checks) + `test_ui_rebuild_home.py` (630) + the retired area tests (section 10, built from `retired/` in a scratch tree) | pass |

No game file is in the repository: the build reads the movies from the user's install at build time and writes the
modified pack to the git-ignored `data/ui_build/`. The original is backed up to `data/ui_build/backup/` by `apply`.

## 1. Commands

```
python ic.py ui build      # data/ui_build/0xa00000d0.rp + manifest.json from ui/modern/ and the installed pack
python ic.py ui apply      # game closed: backup of the original, install the build, SHA-1 verified
python ic.py ui revert     # game closed: the original back, byte-identical; backup removed
python ic.py ui status     # original | modern (current build) | modern-old (earlier build) | ui-test | unknown
python ic.py ui list [0x20000077]   # the compiled scripts, disassembled
```

- `apply` / `revert` refuse while `InfiniteCrisis_patched.exe` or `InfiniteCrisis.exe` runs (tasklist, as `ui-test`).
- `build` takes its source from the installed pack when it is the original, else from the backup (so it can be
  rebuilt after every change while a Modern build is installed: `ui build` then `ui apply` replaces it).
- The movies it edits are pinned by CRC-32 (`ORIGINAL_CRCS`: `0x20000077` `0xD3D3FF27`, `0x2000005F` `0xE491D802`);
  another version of the pack is refused, not edited blindly.
- `ui-test` still works on an original pack; with a Modern build installed it refuses ("unexpected bytes"), and
  `ui apply` refuses while the `ui-test` movie is installed. Revert one before applying the other.
- `python ic.py patch` does not touch `0xA00000D0`. Caches keyed on the pack (`data/cache/tables_*.json`, size +
  mtime stamp) refresh by themselves.

## 2. The pack file and the repacker [C]

Checked on the installed `0xA00000D0` (56 995 840 bytes, 2274 records, 4 tails):

- Header `+0xC` = **payload span**: file bytes from 0x400 to the end of the zlib Adler-32 (`0x2F1F153`), trailers
  included. `+0x10` record count. `+0x14` 4 tails, `+0x18` languages 1/3/5/6, `+0x28` tail spans.
- Payload in 0x20000-byte file blocks: 0x1FFFC data + u32 trailer = **zlib bytes in that block**; block 0's trailer is
  `0x1FFFC - 4 x count` (`0x1DC74`: the DID list comes first and is not zlib). **The last block is partial and has no
  trailer** (the stream's Adler-32 ends the span exactly). The repacker never produces a last block of exactly
  0x1FFFC bytes (it adds an empty stored block instead), so that ambiguous case cannot happen.
- Tail streams start at `align_0x400(0x400 + span)`, each padded to 0x400, and have **the same block / trailer layout
  relative to their own start** (inflating tail 0 only works with trailers dropped every 0x20000 bytes from its
  start). They are copied byte for byte, so moving them by any multiple of 0x400 keeps them valid.
- The zlib stream is stored blocks only, split 65 531, 32 773, then 32 768 each, the remainder, an empty block, an
  empty final block (zlib 1.2.3 level 0 fed 32 KB at a time, then a sync flush and finish). `rp_repack.zlib_stored`
  reproduces it: `python tools/rp_repack.py verify ..\rp\0xa00000d0.rp` -> byte-identical.
- Records are in DID-list order, each 4-byte aligned with zero padding. A movie record carries its own length (`u32
  length` before the GFX, and the GFX header's file length), so `Pack.replace(start, end, record)` swaps a record for
  one of any length; `Pack.record_bounds` finds a record by its DID, checks it parses, that the padding is zero and
  that the next DID in the list follows. `Pack.append(did, record)` adds a record at the end of the list and stream:
  the format allows it, but whether the client registers a DID it only finds in a pack's list is **not tested** [P]
  (the loader pulls records in list order, `0x9D9280`); the Modern build does not need it (it edits existing movies).
- `ui_build.verify_build` re-reads the result: same DID list, tails and header (but span), every byte outside the
  edited records identical (shifted), each edited record parses as a movie, the terrainfix stored-stream reader
  accepts it and the Adler-32 matches.

## 3. The AS2 compiler (`tools/as2c.py`) [C]

Pure Python, no download. The game's code is AS2 (SWF 8 actions); our scripts are small, so a compiler for a
JavaScript-like subset is enough:

- statements: `var a = e, b;`, `function f(a) {...}`, `if / else`, `while`, `for (init; cond; step)`, `break`,
  `continue`, `return`, blocks, expression statements, `=`, `+=`, `-=`, `++`, `--` (assignments are statements only).
- expressions: number / string / `true false null undefined this` literals, names, `a.b`, `a[e]`, calls, method
  calls, `new X(...)`, `new a.b.C(...)`, function expressions, `[..]`, `{k: v}`, `! - typeof`, arithmetic,
  comparisons, `== != === !==`, `&& ||`, `?:`.
- `#include "file.as"` (textual), build constants (`K_*` from `ui/modern/common/palette.py` + the module's `CONSTS`) replaced by literals.
- Code: one `ConstantPool` per action list (most used strings first, 16-bit indices past 256), `GetVariable` /
  `GetMember` for every name (dotted library classes such as `GM_Options` or `gameplay.wrapper.WrapperMain.Instance`
  resolve through `_global` like in the library's own code), `DefineFunction` v1 (closures over the timeline they
  are defined on; `this` = the call's object), `DefineLocal` for `var`, `If` / `Jump` with fixed 5-byte records.
- `disassemble()` lists any action bytes (used by `ui list` and the tests); `VM` runs exactly the opcodes the compiler
  emits against Python objects (natives, getters / setters, clip mocks) so a script's behaviour can be tested.

The same compiler builds clip actions (`on(construct)` of a new button: `gfx_edit.clip_actions([(0x40000, code)])`).

## 4. How a movie is changed (a movie module, `tools/ui_build.py edit_movie`) [C]

Per exported symbol (the ones `WrapperMain` / the settings dialog attach by linkage name):

- **art**: a `DefineShape3` of RGBA polygons (each made clockwise on screen and filled with FillStyle1, the badge's
  convention that rendered in game), wrapped in a 1-frame `DefineSprite` so a script can show / move / size it,
  placed at a free depth **with a colour transform of alpha 0** (a Legacy client never sees it, even before the
  script runs). Empty art = an empty sprite (the per-frame "ticker").
- **clone**: a new placement of a symbol the movie already has (game buttons with their own art, text and sounds),
  off screen (`x = -6000`), with clip actions compiled from our source (`nav_button.as` = the game's own button
  parameters with our label, no tooltip).
- **copy**: the same symbol's placement duplicated with a new depth / name / position (its clip actions kept).
- **script**: one `DoAction` appended to frame 1, after the placements and before `ShowFrame` (the symbols' own
  frame 1 already starts with `stop();`, so it runs once per attach).
- New character ids are allocated above the movie's highest; definitions are inserted before the edited sprite.
- Everything original stays byte-identical and in order: every top-level tag, every placement (depth, character,
  instance name, clip actions), the `stop()` actions, exports, imports, the 39 `registerClass` init actions, the
  record header (DID, flags, imports, images). The tests check exactly this.

## 5. The switch: `User.InterfaceStyle` [C for the mechanism, P for the client side]

- Settings dialog `0x2000005F`, symbol `UIPaneContents` (class `gameplay.settings.UIPaneContents`, the UI pane): a
  copy of the profanity-filter check box (`m_btnUseProfanityFilter`, a `LabeledCheckbox` / `CheckBoxButton`,
  `toggle = true`) as **`m_btnICModernUI`** 30 px under it (depth 76), label "Modern interface (beta)".
- `settings_ui_pane.as`: reads the preference, sets `selected`, and on the button's `select` event saves at once with
  `GM_Options.SendNotice_SetIntOption("User.InterfaceStyle", 0 | 1)` (notice `0x1000013D` -> `0xA4DD30`, registers the
  name and writes `UserPreferences.ini`) and re-applies the look to every header part (`_global.ICModern.applyAll`).
  The pane's Apply / Cancel are not involved. Default (unknown name): the query `0x1000013A` -> `0xA4DEF0` registers it
  with 0 = **Legacy**.
- Server: once synced, the client uploads it with `0x216E` (wstr value, kind `0x10000A0E` number);
  `ics/account.py set_preference` stores it and `server_options()` sends it back as `0x216A` type `0x10` int (the
  test checks `"1"` -> `("User.InterfaceStyle", 0x10, 1)` and back to 0). No server change.
- `_global.ICModern` (`common.as`, included by every script): `read()`, `write(style)`, `register(clip)` (the header
  parts, pruned of unloaded clips), `applyAll(style)`, `style`. Each header part re-reads the preference when the
  wrapper attaches it.

## 6. The Modern header (`0x20000077`) [C in the VM, P in game]

The class code is untouched; every button keeps its instance name and handler. In Legacy the scripts only hide our
clips (no original instance is written: tested); in Modern:

| Symbol | Modern | Legacy restore (live switch) |
|---|---|---|
| `HeaderLetterbox` (HeaderBkgd) | the four backgrounds `_alpha = 0` (their `_visible` stays under `SetBumpType`), navy bar `m_icModernBar` (90 % navy, 2 px `#2FA8FF` rule + glow, 12 000 px wide); `m_icProfilePanel` (placed by HeaderLeft) | alphas 100, our clips hidden |
| `HeaderCenter` | `m_pvpPlay` moved to 250 px from the screen's left edge and tinted electric blue (`flash.geom.Transform` + `ColorTransform`, the library's own way, `MapNote.as`), pointed plate `m_icPlayPlate` sized around `m_btPlayGame` (follows its `_visible` / `_alpha` tweens), nav buttons `m_icNavHome / Champions / Amplifiers / Store` (new `MediumTextButtonLarge` instances, char 113) in a row after PLAY, each scaled to `K_NAV_H` 22 stage px tall and at most `K_NAV_MAX_W` 100 px wide (the strip `m_icNavPanel` is off: `K_NAV_PANEL` 0), shown for veterans (`eProtectorAdvancementStatus == Player`); the Legacy `m_btnHome` moved away | original `_x` of `m_pvpPlay` / `m_btnHome`, identity colour transform, our clips hidden and off screen |
| `HeaderLeft` | `m_hpProfile` (calling card = avatar, name, level, currencies) moved to the top right, its right edge 14 px left of Help, top 3 px, scaled 68 % (down to 50 % if it would reach the nav), over the subtle panel `m_icProfilePanel`; `m_hcTraineeHeaderCurrency` likewise; Crisis Coins text gold `#F2B33D`, Merits blue `#3FA9FF` (`m_tfText.textColor`, original saved) | position, scale and colours back |
| `HeaderRight` | `m_mcNavButtons` (Legacy Store) moved away: STORE in the Modern nav calls `NavButtons.OnStorePress` | original `_x` |

Button behaviour: HOME -> `NavButtons.OnHomePress()` (asks about unsaved amplifier changes, then
`TransitionToLandingScreen`), CHAMPIONS -> `GM_UI.SendNotice_UIStateMachineEvent(TransitionToCharacters)`, AMPLIFIERS ->
`TransitionToAmplifiers` (as `LandingNav`), STORE -> `NavButtons.OnStorePress()`; PLAY, Settings, Help, Exit and the
avatar are the original instances. The layout is recomputed every frame by `onEnterFrame` on our empty ticker clips
(screen size, HUD scale and the launcher's own tweens change it); it converges after one frame (tested).

### 6.1 First in-game test (2026-10-30) and the fixes

The tester applied the build and ticked the box: **the switch works and the scripts run** (the header changed live).
Screenshot at 1905 x 1000 (the client scales the 1280 x 720 stage about x1.49):

| Seen | Cause | Fix (header module) |
|---|---|---|
| HOME / CHAMPIONS / AMPLIFIERS / STORE ~290 x 60 screen px each, the row reaching x 1840 and covering the profile | the clones are the game's `MediumTextButtonLarge` at 100 % (~195 x 40 stage px) | each scaled at run time to `K_NAV_H` 22 px tall, at most `K_NAV_MAX_W` 100 px wide (~33 x 150 screen px); its own unscaled bounds measured once (`ic_s`) |
| a big pointed blue-outlined frame behind the nav (x 510-1840) and a tab under the profile (to y 185), read as Legacy art | they were ours: `NavPanel` and `ProfilePanel` with a bright accent outline (the Legacy backgrounds were already transparent) | nav strip off (`K_NAV_PANEL` 0); profile panel navy without outline, a thin accent rule at its bottom |
| the navy bar not noticeable | 62 px of 90 % `#0A1220` over a dark background, its rule hidden behind the nav strip | bar 76 px tall in `#101C30` at 94 %, 2 px `#2FA8FF` rule + glow |
| currencies not visible | the profile (with its currency row) sat under the nav buttons (HeaderCenter draws above HeaderLeft) | profile right-aligned to Help, scaled 68 %, top 3 px; the compact nav no longer reaches it |
| PLAY NOW keeps a blue-green look | the first tint was mild | stronger tint (mult 0.35 / 0.65 / 1.0, add 10 / 70 / 150) over the pointed plate |

Expected layout in 1280 x 720 stage px: PLAY centred at x 250 (plate ~130-380), nav ~404-830, profile ~940-1171,
Help / Settings / Exit from ~1185 (unchanged). Legacy is unchanged (tests: no original instance written).

## 7. In-game test (tester)

1. Close the game. `python ic.py ui build`, then `python ic.py ui apply` (expect "installed and verified").
2. Start as usual, log in. The home screen must look exactly as before (Legacy is the default).
3. Settings (gear) > UI pane > scroll to the end: "Modern interface (beta)" check box. Tick it: the header switches
   at once (navy bar, blue PLAY at the left on a pointed plate, HOME / CHAMPIONS / AMPLIFIERS / STORE, profile and
   currencies at the top right, coins gold / merits blue). Untick: back to Legacy at once.
4. In Modern click PLAY, HOME, CHAMPIONS, AMPLIFIERS, STORE, the avatar (calling-card dialog), Settings, Help, Exit
   (cancel); play a match and come back (the choice persists: INI + account).
5. Close the game; `python ic.py ui revert` (byte-identical original) when done or if anything breaks.
Send `logs\server.log`, `logs\unhandled.log` and screenshots of Legacy and Modern.

What could go wrong and what it would mean: no check box -> GFx ignored the copied placement or the pane's scroll
size; the header unchanged in Modern -> the frame scripts do not run (or `GM_Options` is not reachable from a
movie timeline); nav buttons without text -> the clip actions or `Text` setter; the profile misplaced -> the
`getBounds` / `globalToLocal` maths (constants `K_*` in the header module).

## 8. Adding a screen (the module convention)

`ui/modern/` is split so several people (or agents) can add screens in parallel without touching the same files:

```
ui/modern/
  common/                       shared: change here, every screen follows
    palette.py                  colours (NAVY, NAVY_2, ACCENT, GOLD, MERIT), rgba() / hexagon() / rect(), shared ART
                                (PointedPlate, Panel, Ticker) and shared CONSTS (K_PREF, K_ACCENT, K_GOLD, K_MERIT,
                                K_OFFSCREEN, ...)
    common.as                   _global.ICModern: read() / write() the User.InterfaceStyle preference, register() /
                                applyAll() for live switching, header()
  movies/
    0x20000077_header/          one folder per movie: "<DID>_<short name>", found automatically by tools/ui_build.py
      module.py                 DID, NAME, ORIGINAL_CRC, ART, CONSTS, SPRITES
      header_center.as ...      the scripts named in SPRITES
    0x2000005F_settings/
```

A module (`module.py`) declares:

- `DID` (the movie record, `0x20xxxxxx`; the folder name must start with it), `NAME`, `ORIGINAL_CRC` (CRC-32 of the
  original GFX bytes, `zlib.crc32` of the record's GFX as `tools/ui_mod.find_movie` returns it; the build refuses
  another version of the movie).
- `ART = {name: [(rgba, polygon px), ...]}` (merged over the shared `palette.ART`; `from palette import ...` works
  inside a module).
- `CONSTS = {"K_...": value}` (merged over the shared ones; the scripts use them as literals).
- `SPRITES = {exported symbol: {"add": [...], "script": "file.as"}}`, where each add entry is one of
  - `("art", art name, depth, instance name)`: a sprite of that art at a free depth, alpha 0 until the script shows it;
  - `("clone", template symbol, template instance, depth, instance name, clip-action script or None, {K: const})`: a
    new instance of the character the template placement uses (a game button), off screen, with clip actions compiled
    from the script (`nav_button.as` in the header module is the pattern);
  - `("copy", instance in the same symbol, depth, instance name, dx, dy)`: the same placement duplicated and moved.
- Scripts start with `#include "../../common/common.as"`, define `this.ic_Apply = function (style) {...}`, call
  `ic.register(this)` and `this.ic_Apply(ic.style)`. In Legacy (style 0) a script must not write to any original
  instance (only hide its own clips); in Modern it may move / scale / tint / fade original instances and must put them
  back when switched to Legacy (`ic_wasModern`). Behaviour stays in the game's classes: keep instance names, add
  listeners (`addEventListener(gfx.events.EventTypes.CLICK, this, "handler")`), call the same `GM_*` notices the
  library calls. Game buttons are sized by scaling (`_xscale` / `_yscale`) measured from their own unscaled bounds
  (`getBounds(itself)`), as the header's nav does.
- Rules: one module per movie (the build refuses two modules for one DID); depths and instance names must be free in
  that symbol (checked); new names start with `m_ic`; never put extracted game data in a module (IDs, names, numbers
  and our own art only).
- Test: `python tests\test_ui_build.py` checks every module's movie (originals kept byte-identical and in order, the
  added instances, one script per symbol that names one, art at alpha 0, clones off screen, copies = their template
  moved).
- Shared code: helpers used by several modules go in `ui/modern/common/` (`*.py` there are loaded by the build and
  imported by name: `import social_art as sa`; `*.as` are included as `#include "../../common/x.as"`). A module never
  includes or names a file of another module's folder: `ui_build.check_isolation` refuses it when the layout loads. For behaviour, add a VM check with mock clips like
  `scripts_in_vm()` (the header's).

## 9. Target screens and their movies

From `client-scripts-and-ui.md` 2.4 (the movie table) and `ui-complete.md` (class -> movies). A movie used by two
screens gets ONE module; coordinate its symbols between the screens.

| Screen | Movie(s) (main classes) | Shared with |
|---|---|---|
| Wrapper header (done) | `0x20000077` (HeaderLetterbox / Left / Center / Right) | every out-of-match screen |
| Settings (switch done) | `0x2000005F` (SettingsPanelDialog, UIPaneContents, GameplayPane, GraphicsPaneContents, AudioPane) | - |
| Home body | `0x20000078` landing, `0x200000A4` veteran landing (VeteranLanding), `0x200000A8` landing nav (LandingNav, LandingSwitcher), `0x20000074` new-player screen, `0x2000009E` wrapper background, `0x20000090` footer | `0x200000A4` is also the profile overview |
| Champion select + skin carousel | `0x20000022` champion picker (CharacterPicker, SkinPicker), `0x20000067` pre-match lobby (PvPLobby) | `0x20000022` is placed in the lobby; `0x20000067` also holds the amplifier-set / Stolen Power pickers, the lobby chat and the loading percent |
| Loading | `0x20000020` loading into world (LoadingIntoWorld, a 3 KB shell); lobby loading percent in `0x20000067` | `0x20000067` |
| Store | `0x2000007C` store (web page host, Store); purchase dialogs in `0x20000080` | `0x20000080` holds every dialog |
| Champions collection | `0x200000A5` characters screen (CharactersScreen) | champion info (same movie) |
| Champion info / biography | `0x200000A5` (ChampionDetailPanel) | champions collection (same movie) |
| Amplifier sets | `0x20000094` amplifiers screen (AmplifiersScreen, Assembler, AmplifierSet*); lobby picker in `0x20000067` | `0x20000067` |
| Profile | `0x20000080` (CallingCardDialog), `0x200000A0` calling card (CallingCardDisplay), `0x200000A4` overview, `0x200000A3` stats, `0x200000A2` achievements, `0x200000B2` ranked / leaderboards | `0x20000080` (all dialogs), `0x200000A4` (home) |
| Match results / scorecard | `0x2000008C` scorecard, `0x2000009D` stats tab, `0x200000AD` accolades tab, `0x200000AE` accolades widget | - |
| Custom match lobby | `0x20000093` custom match (CustomMatchScreen and its parts); party screen `0x20000082` | `0x20000082` also hosts chat / contacts |
| Chat | `0x20000083` chat (Chat, ChatLauncher), `0x2000008B` friends / contacts / notifications | lobby `0x20000067` and party `0x20000082` place chat widgets too |
| Login | `0x2000006D` login / connecting / display name (LoginScreen); `0x200000B1` login rewards | - |
| In-match HUD | `0x2000000C` match bar, `0x2000000F` minimap, `0x20000010` floaty vitals, `0x20000011` XP bar, `0x20000013` defeat, `0x20000015` billboards, `0x2000002B` vitals, `0x20000056` skill bar, `0x20000057` currency, `0x2000005A` character panel, `0x2000005B` kill feed, `0x2000005C` top bar, `0x2000005E` power bar, `0x20000062` player info, `0x20000063` status icons, `0x20000064` objectives, `0x20000065` event timer, `0x2000006F` kill card, `0x2000008A` selection panel, `0x20000087` foundry, `0x20000084` artifact widgets, `0x20000006` overhead vitals, `0x2000000D` Esc menu (MainHUD spans 14 movies) | `0x20000084` is shared by the foundry and the skill bar |

Not editable through the payload: the HUD shell `0x20000017` and `0x20000019` live only in the per-language tail
layout `0x27000012` (`ui-modern-feasibility.md` 1); editing them needs the tail stream rebuilt (the repacker copies
tails as they are). The shared libraries (`0x20000000/1/2/4`, `0x20000058` art, `0x20000059` controls, `0x20000025`
code) are best left alone: a change there affects every screen and both looks.

## 10. Integration of the parallel modules (2026-10-30)

Five area agents added 27 movie modules next to the header and the settings switch (notes `ui-modern-home.md`,
`ui-modern-champselect.md`, `ui-modern-collection.md`, `ui-modern-profile.md`, `ui-modern-social.md`). Then:

### 10.1 `define_shape3`: long edges corrupted the shape [C]

A `StraightEdgeRecord` stores `NumBits - 2` in a **4-bit** field, so a delta has at most 17 signed bits
(-65 536..65 535 twips, ~3 276 px). `define_shape3` wrote `k - 2` with `k` up to 19 for the header's `ModernBar`
(`rect(-4000, 0, 8000, 76)` = 12 000 px = 240 000 twips): the field overflowed into the next bits and the rest of the
shape decoded as garbage. **This is probably why the tester never saw the navy bar** (6.1). The lobby's `Veil`
(same width) had the same fault. Fix (`tools/gfx_edit.py`): `edge_segments(dx, dy)` splits any edge into
`ceil(max(|dx|, |dy|) / 65 535)` collinear segments with rounded integer end points (the sum is exact), and
`_straight_edge` refuses a delta that still does not fit. Also: a fill-style count of 255 or more is written as
`0xFF` + u16 (the extended count; 255 used to be read back as "extended"), and `shape_polys` reads it. Tests
(`test_ui_build.py long_edges`): the ModernBar reads back as its four rectangles (corners in order, split points on
the edges, bounds), long diagonal edges, 300 colours; the old writer fails these checks. Only `0x20000077` and
`0x20000067` changed in the build because of it.

### 10.2 Shared code moved to `ui/modern/common/` [C]

Byte-identical: the full build before and after the move has the same SHA-1 (`90a34f69...`), so behaviour is unchanged.

| Was | Now | Used by |
|---|---|---|
| `0x200000A4_veteran_landing/home_style.py`, `home_lib.as` | `common/home_style.py`, `common/home_lib.as` | home, footer, background, login, new player, landing nav, login rewards |
| `0x20000080_dialogs/collection_art.py`, `collection_lib.as` | `common/collection_art.py`, `common/collection_lib.as` | store, dialogs, champions, amplifiers |
| `0x2000008C_scorecard/ic_profile_art.py`, `ic_kit.as` | `common/profile_art.py`, `common/profile_kit.as` | the eight profile / results modules |
| `0x20000093_custom_match/social_art.py`, `social.as` | `common/social_art.py`, `common/social.as` | custom match, group, chat, contacts |
| `ic_Set` / `ic_Orig` / `ic_RestoreAll` repeated in 3 scripts | `common/saved_values.as` | `character_picker.as`, `pvp_lobby.as`, `pvp_curtain.as` (bytecode changed: one copy, `pvp_curtain` gains `ic_Orig`; same behaviour, `test_ui_champselect.py` green) |

`Layout` loads every `common/*.py` fresh from the tree it is given (after `palette.py`) and registers it in
`sys.modules` under its own name, so a module writes `import social_art as sa` and scratch copies used by the area
tests get their own copy. `check_isolation` (run per module when the layout loads) follows every `#include`
recursively and refuses one that leaves the module's folder and `common/`, and refuses a module `.py` that names
another module's folder.

### 10.3 Robust build [C]

`ui_build.ModuleError` (a `ValueError`, so `ui build` still fails with exit 1 and prints `build failed: ...`) names the
module for: a `common/*.py` or `module.py` that does not import (exception type + message), missing keys, two
modules for one DID, a folder without its DID, a cross-module include / path, a script or clone clip-action that does
not compile or a missing include (`compile_all` compiles every script before the pack is even read: `module
<folder> (<did>) <symbol>: CompileError: ...`), a movie missing from the pack, a CRC mismatch, an edit that fails
(free depth, unknown export or placement). `test_ui_build.py modules()` breaks a scratch copy of the header module
five ways and checks the message names it.

### 10.4 `tests/test_ui_build.py` changes

- `install: manifest movies` compares with the layout's DIDs (was hard-coded to the header and settings).
- Scripts keyed by `(DID, symbol)` (`ChatLauncher` is edited in both `0x20000083` and `0x20000067`); the header /
  settings VM run takes its scripts from those two DIDs only. `install: every module's scripts built` = `compile_all`.
- Per added placement, by its `add` kind: `art` starts at alpha 0 without clip actions; `clone` starts off screen;
  `copy` is checked as its template moved (same character, colour transform, ratio, clip depth and clip actions,
  offset = the module's dx / dy, the given depth) instead of the alpha-0 rule: a copy shows what its template shows
  (the settings check box is meant to be visible in Legacy), and the old rule failed any copy of a placement without
  clip actions, which the champion-select agent had to avoid. A symbol without a `script` must get no DoAction; one with a script
  gets exactly one, right before `ShowFrame`. Unchanged: every original tag byte-identical and in order, exports,
  record and movie headers, fresh character ids, unique frame-1 depths, the header's Legacy / Modern VM checks (no
  original written in Legacy, names and handlers kept); the area tests keep the Legacy-writes-nothing check of their
  own symbols.

### 10.5 The full build (2026-10-30)

`python ic.py ui build` from the installed original (SHA-1 `6bd720aa...`): **57 571 328 bytes, SHA-1
`1868d70a51701dc5071cc066a503ac26377e4a90`**, 2274 records, 4 tails, every other record byte-identical, zlib stream
verified (`verify_build`); `python tools/rp_repack.py verify` on the result rebuilds it byte-identical. No module
disabled. 29 movies (GFX bytes original -> built):

| DID | Module | Area | Bytes |
|---|---|---|---|
| `0x20000020` | loading | champion select | 3 175 -> 7 789 |
| `0x20000022` | champselect | champion select | 48 600 -> 57 475 |
| `0x2000005F` | settings | (switch) | 70 002 -> 71 988 |
| `0x20000067` | lobby | champion select | 70 057 -> 87 946 |
| `0x2000006D` | login | home | 32 783 -> 37 627 |
| `0x20000074` | new_player | home | 21 561 -> 25 576 |
| `0x20000077` | header | (header) | 61 931 -> 76 855 |
| `0x20000078` | landing | home | 38 048 -> 41 850 |
| `0x2000007C` | store | collection | 21 316 -> 27 863 |
| `0x20000080` | dialogs | collection | 67 351 -> 201 782 |
| `0x20000082` | group | social | 44 325 -> 71 643 |
| `0x20000083` | chat | social | 22 288 -> 30 369 |
| `0x2000008B` | contacts | social | 66 002 -> 81 137 |
| `0x2000008C` | scorecard | profile | 43 804 -> 64 960 |
| `0x20000090` | footer | home | 28 473 -> 43 530 |
| `0x20000093` | custom_match | social | 68 409 -> 121 972 |
| `0x20000094` | amplifiers | collection | 45 906 -> 100 255 |
| `0x2000009D` | scorestats | profile | 31 103 -> 45 429 |
| `0x2000009E` | background | home | 29 243 -> 31 421 |
| `0x200000A0` | callingcard | profile | 24 398 -> 48 583 |
| `0x200000A2` | achievements | profile | 40 096 -> 50 359 |
| `0x200000A3` | stats | profile | 26 603 -> 45 727 |
| `0x200000A4` | veteran_landing | home | 42 563 -> 51 893 |
| `0x200000A5` | characters | collection | 61 541 -> 96 930 |
| `0x200000A8` | landing_nav | home | 29 107 -> 34 313 |
| `0x200000AD` | rewards | profile | 42 314 -> 69 074 |
| `0x200000AE` | accolades | profile | 30 198 -> 39 724 |
| `0x200000B1` | login_rewards | home | 43 126 -> 51 405 |
| `0x200000B2` | ranked | profile | 30 250 -> 45 100 |

Tests (all pass): `test_ui_build.py` 1108, `test_ui_mod.py` 31, `test_ui_champselect.py` 170, `test_ui_collection.py`
838, `test_ui_profile.py` 755, `test_ui_home.py` 309, `test_ui_social.py` 557, `test_catalog.py` OK. The in-match HUD
(section 9) is deliberately not started.

## 11. The rebuild method (2026-10-30, current)

The restyle (sections 6 / 10) kept the Legacy art and could only tint, move and cover it; the tester's verdict on the
login / home screenshots: "nothing like the approved design". The rebuild builds each screen **from scratch** and
keeps only what the game's code needs: the instance names and classes. Full account, per-screen class surfaces and
the in-game test: `ui-modern-rebuild-home.md`.

- **A module declares `SYMBOLS`** (next to `ART`, `CONSTS`, `SPRITES`, usually empty now): new symbols built at build
  time, each `{"class": <the Legacy symbol's library class>, "replaces": <Legacy linkage>, "children": [...],
  "states": [...], "script": "file.as"}`. Children (frame 1): `("art", name, depth, inst, x, y[, sx, sy])`, `("place",
  linkage | character id, depth, inst, x, y, sx, sy, params)` (our symbols defined earlier, or this movie's exports /
  imports), `("copy", Legacy symbol, instance | depth, depth, inst, x, y, sx, sy, params)` (the Legacy placement's
  character and clip actions; `None` keeps a value), `("text", depth, inst, x, y, w, h, params)` (the movie's
  `UIWidget_Text`, box w x h = scale of the 120 x 24 author box). `params` = component parameters, written as
  `on(construct)`. `states` = `[(frame label, [children])]`: one frame per state with `stop()` (CLIK buttons, meters).
- **The build** (`ui_build.build_symbols`) appends, before the movie's last `ShowFrame`: our art (one DefineShape3 per
  polygon group, in a 1-frame sprite), the symbols (DefineSprite), one `ExportAssets` (the symbols + an empty
  `ICM_Init_<DID>` sprite), one `DoInitAction` on that sprite: `#include "rebuild.as"` + `Object.registerClass` per
  symbol + `ic_Swap(legacy, twin)` per twin. Nothing original changes (tested).
- **The switch at run time** (`common/rebuild.as`): `ui_sys.UIWidget_Base.prototype.AddChildFromLibrary` (WrapperMain
  attaches every screen, header / footer part and the landing nav through it) is wrapped once: with
  `User.InterfaceStyle` = 1 a linkage that has a twin attaches the twin (same instance name, init object, class);
  otherwise, or if the twin cannot be attached, the original call. `ICModern.rebuild()` re-attaches the parts and
  reloads the current screen (the settings check box calls it: live switch).
- **Rules** (tested in `test_ui_rebuild_home.py`): names `ICM_*`, unique across movies; every instance name the class
  reaches is present with a child of the right kind; composite `UIWidget_Base` widgets reset a placement's scale in
  their constructor, so scale them from the script (texts and `utils.Icon` keep the placement's scale as their box);
  a part attached to the right / bottom edge is measured by its own bounds (use an invisible author box).

### Adding a screen (rebuild)

1. Find how it is attached: `WrapperMain.AttachNextScreen` (`m_ssData.m_sScreenIDString`), `Attach*`, or another
   `AddChildFromLibrary` caller; the store and the background use `ResolutionSizer` (not hooked yet).
2. Read the class(es) in the decompiled library (`re-work/ui-as2/c_a00000d0_02189b08/scripts/__Packages`): every
   `this.m_*` it touches, recursively for each child class; dump the Legacy symbol's placements (names, characters,
   clip actions, positions) and its sizes.
3. Write `ui/modern/movies/<did>_<name>/module.py`: `ORIGINAL_CRC`, `ART` (from `common/rebuild_kit.py`), `SYMBOLS`
   with the twin (`replaces`) and its nested symbols, the design scaled x 0.8889 to 1280 x 720 (screens centred:
   origin = stage centre). Reuse the Legacy placement (`copy`) for data widgets, our symbols of the same class for
   anything with Legacy-looking art, `UIWidget_Text` for text.
4. A frame script only for what the class does not do (layout against other parts, hover colours, extra buttons
   calling the same `GM_*` notices / class methods the game uses).
5. Add the class surface to `REQUIRED` in a test (or the screen's own test) and VM checks for the script; `python
   tools/ui_preview.py` to look at it; `python ic.py ui build`.
