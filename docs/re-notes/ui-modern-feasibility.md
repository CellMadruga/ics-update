# A "Modern" client UI next to the "Legacy" one: feasibility (static analysis + a tool, 2026-10-30)

Question (user): can a new interface be put into the client with every button still working, switchable from the
options menu? This note answers it with evidence, ships a small in-game test (`python ic.py ui-test apply` /
`revert`, `tools/ui_mod.py`) and lists what a full Modern UI would still need. Nothing was run in the client yet; the
test below is the tester's step. Design reference: the approved UI redesign artifact (dark navy, electric blue
accent); this test only proves the pipeline. No game file is in the repository: extracted movies go to the git-ignored
`data/cache/ui_test/` (or any folder given to `extract`).

Tags: **[C]** confirmed (code, data or a run on a copy of the pack), **[P]** probable, **[G]** guess.

Builds on `client-scripts-and-ui.md` 2 (pack layout, movie table), `ui-complete.md` (every class and notice),
`full-account-social.md` 9 (preferences sync), `install-inventory.md` 2.1 (pack header, tail streams),
`map-audit-all.md` 6 / 9 (stored-block pack edits, terrainfix).

## 0. Verdict per point

| # | Point | Verdict |
|---|---|---|
| 1 | Extraction | **Done [C].** Movies are DB type `0x20` records in `0xA00000D0` only; uncompressed **GFX** (Scaleform's SWF, v8, one v9), **ActionScript 2** everywhere (no DoABC); the code library `0x20000025` is a zlib `CWS`. The home-screen bar with PLAY / Store / Settings / Help / Exit / profile / currency is the **wrapper header `0x20000077`**; extracted and decoded (2). |
| 2 | Modify and keep every button working | **Done statically [C], in-game check pending.** The buttons' behaviour is library code bound to instance names (`m_btPlayGame`, `m_btStoreButton`, ...) and registerClass init actions; the edit keeps all of them byte-identical, recolours the header and PLAY with colour transforms and adds a vector "MODERN UI TEST" badge, at the same record length (3). |
| 3 | Repacking, integrity, how packs are found | **Done [C].** The pack is one stored-block zlib stream; the only check is zlib's Adler-32 (which the tool rewrites). No CRC / hash / signature over packs or records in the loader; packs are opened by name `0x%08x.rp`; no other pack holds movies; the English tail layout does not override `0x20000077`. Same-length edits are proven on a copy; a length-changing repack is feasible (loader reads sequentially, header fields known) but not built yet (4). |
| 4 | Tooling | **Done.** `python ic.py ui-test apply / revert / status / info / extract` (`tools/ui_mod.py`), refuses while the game runs, backup `0xa00000d0.rp.uitest.json`, revert verified byte-identical on a copy; `tests/test_ui_mod.py` 31 checks (5). |
| 5 | The switch | **Feasible [C for the mechanism].** Flash can read and write any `User.*` preference: `GM_Options.SendQuery_GetBoolOption / GetIntOption(name)` -> `0xA4DBC0` / `0xA4DEF0` register an unknown name on first use (default false / 0) and read it; `SetBoolOption / SetIntOption` -> `0xA4DA00` / `0xA4DD30` register + store + save to `UserPreferences.ini`; once synced the client uploads it with `0x216E` and `ics` already stores it per account and sends it back with `0x216A`. The login screen reads the same local INI value before any account exists [P]. A menu entry and the Legacy/Modern branch need new AS2 (in a movie or the library), not built here (6). |

## 1. Where the UI lives [C]

- `client-scripts-and-ui.md` 2.1: 89 type-`0x20` records in `0xA00000D0` (82 parse as movies) plus 1908 images
  (`0x13`). Scanning the DID lists of all 616 packs (2026-10-30): **only `0xA00000D0` holds `0x20` records**, and
  `0x20000077` is in no other pack.
- Record: `u32 did | u32 flags (0, or 2 = imports) | [u32 n | n x (u32 0x31, u32 movie DID)] | u32 0 | u32 0 |
  u32 nImages | nImages x (u32 image DID 0x13.., u32 w, u32 h) | u32 length | GFX`. The import list repeats the
  movie's `ImportAssets2` URLs (`#2000xxxx`); bitmaps are `DefineExternalImage2` (GFx tag 1009) with
  `img://#1300xxxx` URLs = the record's image list.
- Formats over all 82 movies: 80 `GFX` v8, 1 `GFX` v9 (`0x20000000`, no FileAttributes, no DoABC), 1 `CWS` v8
  (`0x20000025`, the library: 809 892 bytes, 3 179 564 uncompressed). No DoABC / DoABC2 tag anywhere: **all AS2**.
- The pack also has 4 language tail streams (`install-inventory.md` 2.1), each the UI layout record `0x27000012`
  (zlib, 1.89 MB English): it carries 4 more movies (`0x20000017` HUD shell, `0x20000019`, and two whose record
  header differs, 69 012 and 1 731 045 bytes: the font / locale libraries [P]). **`0x20000077` is not among them**, so
  the payload copy is the one the client uses for it [C for absence; P that the tail is consulted by language].

## 2. The home-screen movie `0x20000077` (wrapper header) [C]

`python ic.py ui-test info` prints this from the install:

- Record at stream `0x26D52DC` (flags 2, imports `0x200000B0 0x20000058 0x20000059 0x20000000 0x20000001
  0x20000002 0x20000004 0x200000A0 0x200000AA`, 20 images), GFX v8 at stream `0x26D5430` (= the JPEXS folder
  `026d5430`), 61 931 bytes, CRC-32 `0xD3D3_FF27`. Stage 1280 x 720, 60 fps, 1 frame, 2478 top-level tags.
- Tags: 815 DefineSprite, 790 ExportAssets, **762 DoInitAction (723 empty = sprite id + ActionEnd, the stubs gfxexport
  left when it moved the classes into the library; 39 = `Object.registerClass("<symbol>", <library class>)`)**,
  45 shapes (most bitmap fills), 36 ImportAssets2, 20 DefineExternalImage2, 1 ExporterInfo (tag 1000, 3554 bytes:
  prefix "as2_headers" and 883 offsets into the pre-export SWF), 1 DoAction (`stop(); _focusrect = false;`).
  No DefineEditText: every label is an imported `UIWidget_Text` filled by code with `#<string id>|` tokens.
- **Its root timeline is never shown.** `WrapperMain` (library, `gameplay/wrapper/WrapperMain.as` `AttachHeader*`)
  attaches the exported symbols by linkage name into its scaling containers: `HeaderLetterbox` (sprite 193: four
  backgrounds `m_mcWideBumpBG`, `m_mcMediumBumpBG`, `m_mcBumpBG`, `m_mcFlatBG`), `HeaderLeft` (122: `m_hpProfile`,
  `m_hcTraineeHeaderCurrency`, `m_mcLogo`), `HeaderCenter` (179, centred: `m_miMatchmakingIndicator`, **`m_pvpPlay`**
  = `PVPLauncher` (145: `m_btPlayGame`, `m_btnGroup`, `m_btnGroupCancel`, `m_btnGroupSmall`), `m_btnHome`, `m_Alert`),
  `HeaderRight` (85: `m_mcNavButtons` = `NavButtons` (83: **`m_btStoreButton`**), `m_btSettingsButton`,
  `m_btExitButton`, `m_btHelpButton`).
- **Calls to C++.** The movie itself has none. Its classes (library `0x20000025`) call
  `ExternalInterface.call("Turbine.SendNotice", id, ...)`: `PVPLauncher` -> `GM_UI.SendNotice_UIStateMachineEvent(
  TransitionToEncounterSelectScreen / ToPVPGroupingScreen / ToCustomMatch)`, `GM_Grouping.LeaveGroup`,
  `GM_Lobby.AttemptToRejoinLobbyRoom`, queries `IsInGroup` / `IsInCustomMatch`; `NavButtons` ->
  `UIStateMachineEvent(TransitionToStore / ToLandingScreen)`; `HeaderRight` -> `GM_UI.RequestExitGame`, `ShowHelp`,
  `GM_Dialog.PlayUIDialogElement`; `HeaderLeft` -> `GM_UI.RequestHeaderUIData`, `GM_Character.
  RequestAccountCurrencyBalance`; `HeaderCenter` -> `GM_AdminAlert.UI_RequestAdminAlerts`, `TransitionToLandingScreen`.
  There is no `fscommand` / `getURL` anywhere (`ui-complete.md` 0.3).
- **Consequence for "every button keeps working":** a button works when (a) its instance name is still on a
  placement of the right symbol, (b) the symbol is still linked to its class (export name + registerClass), (c) the
  library is untouched. Art, colours, extra shapes and new placements at free depths do not take part.

## 3. The test edit (`tools/ui_mod.py build_test_movie`) [C]

- `HeaderLetterbox`: a CXFORMWITHALPHA on each of the four background placements (mult 0.30 / 0.36 / 0.62, add
  0 / 6 / 22: navy). Flag `0x08` set, the transform inserted after the matrix; depth, character, name and clip actions
  byte-identical.
- `HeaderCenter`: a colour transform on `m_pvpPlay` (mult 0.45 / 0.65 / 1.0, add 0 / 18 / 70: electric blue; the
  launcher's code only tweens `_alpha` / `_visible`, so the tint stays) and a new `PlaceObject2` (depth 35 = one above
  the sprite's highest, character 917 = one above the movie's highest) of a new **DefineShape3**: a 225 x 29 px navy
  box (`#0B1530`, 94 %) with a 2 px `#2F7BFF` border and "MODERN UI TEST" drawn as 2.5 px strokes on a 4 x 6 grid font
  (no font needed: the movie has no font of its own). It sits centred under the bar (HeaderCenter coordinates
  -112.5 .. 112.5, 96 .. 125 px). A plain shape on a timeline takes no mouse events, so it cannot block a button.
- **Same record length**: the new bytes (357) are paid for by dropping **72 empty DoInitAction stubs** (5 bytes each)
  from the end of the tag list; the shape tag carries the last 3 bytes as padding after its end record (a player reads
  a tag by its length). The GFX header (and its file-length field) is unchanged.
- `tests/test_ui_mod.py` checks, on the installed movie in memory: same length and header, exports equal, every
  top-level tag other than the two edited sprites, the new shape and the dropped stubs byte-identical and in order, all
  39 registerClass init actions kept, in both sprites the same placements (depth, character, name) with only the
  colour transform added, the non-placement tags identical, the badge placed once at a free depth with a free id, the
  shape parsing back as 1 fill / 2 line styles / the box + 19 letter strokes, and zlib inflating the edited pack copy (Adler-32 good).
  The badge was also drawn from the shape bytes (scratch PNG) and reads correctly.

## 4. Repacking and what the client checks [C unless marked]

- **Header** (`0x9DACA0` -> `0x9DA330` reads 0x400 bytes of `0x%08x.rp`, string `0x15FF08C`): +8 block-size shift
  (`1 << 10`), +0xC payload size, +0x10 record count; `0x9D31C0` reads the tail table (+0x14 count, +0x18 language
  ids, then sizes) and places tail stream k at `align_0x400(0x400 + payload size) + sum(align_0x400(earlier sizes))`.
  **No checksum field is read.**
- **Payload** (`0x9D9280`, callers `0x9D9630` / `0x9D96A0`): a streaming zlib 1.2.3 inflate (`inflateInit_
  0xAE0930`, `inflate 0xAE0A60` with flush 2) fed one 0x20000 file block at a time, the block's payload length taken
  from its 4-byte trailer; records are pulled out in DID-list order as u32 words. zlib verifies the Adler-32 at the
  end of the stream ("incorrect data check", string `0x160EBD8` in `0xAE0A60`), so an edit **must** rewrite it.
- **No other integrity check**: the exe's checksum / CRC / signature strings are zlib's own ("header crc mismatch" is
  gzip-mode inflate) or OpenSSL / curl; `CLobbyManager::VerifyAndLoadAllNeededRPS` (`0xABC620`) only loads the
  lobby's champion packs. Practical precedent: `icserver/terrainfix.py` (map packs, tester 2026-10-28/29) and
  `patcher.patch_packs` (`0xA0000038`) edit packs the same way and the client loads them.
- **How a pack is found**: by file name `rp\0x%08x.rp`; `0xA00000D0` is pushed as a constant before the loader
  `0x9DD580` at `0xAC7AB8` (`install-inventory.md` 2.2). An "override pack" is not needed (and not known to work: no
  pack-priority rule was looked for); the edit goes into `0xA00000D0` itself, with a backup.
- **Same-length edit** (what the tool does): a byte edit of the record inside the stored blocks + the new Adler-32,
  through `terrainfix.Stream` (file block layout respected, temp file + `os.replace`). Tried on a copy of the
  installed pack: apply -> zlib inflates the whole pack, the movie reads back with the test CRC `0x3710_2D2B`;
  revert -> SHA-1 identical to the original (`6bd720aa...`).
- **Length-changing edit** (needed for a full Modern UI, e.g. new art or a recompressed library) [P]: because the
  reader is sequential and records carry their own lengths (the movie's `u32 length`), a longer record only needs the
  stream rebuilt (stored or real deflate blocks, trailers = bytes used per block, the first block's minus the DID
  list), header +0xC = new payload size, and the four tail streams copied after the new payload at the 0x400-aligned
  offsets `0x9D31C0` computes. Not built or tested in game yet; it is the next step if the Modern UI needs new bytes
  beyond what dropping stubs gives (723 stubs = 3 615 bytes in this movie).

## 5. The tool [C]

`python ic.py ui-test <cmd>` (configured `[game] dir`) or `python tools\ui_mod.py <cmd> [rp folder]`:

| cmd | does |
|---|---|
| `status` | `original` (CRC `0xD3D3_FF27`), `test` (CRC in the backup) or `unknown` |
| `info` | record, tags, the header symbols and their placements |
| `extract [folder]` | the installed movie and the test movie as `.gfx` (default `data/cache/ui_test`, git-ignored) |
| `apply` | refuses if `InfiniteCrisis_patched.exe` / `InfiniteCrisis.exe` runs (tasklist), or the Adler-32 or movie CRC is not the expected one; writes `0xa00000d0.rp.uitest.json` (offset, original bytes, CRCs, original Adler-32 and file SHA-1), then the pack (temp + replace), then re-reads and verifies |
| `revert` | refuses while the game runs; writes the original bytes and Adler-32 back, checks the SHA-1 against the backup's and removes the backup |

The tool writes nothing else (no exe change, no server change, no config key: it is an opt-in, reversible test).
`python ic.py patch` does not touch `0xA00000D0`, so it neither undoes nor conflicts with the test.

### The in-game test (tester)

1. Close the game. `python ic.py ui-test apply` (expect "UI test movie written ... verified").
2. Start the server and the game as usual (`python ic.py play` or `python -m ics play`), log in.
3. Home screen: the top bar is navy instead of its usual colour, the PLAY button is blue-tinted, and a navy box with
   "MODERN UI TEST" in light blue sits centred just under the bar.
4. Click through, checking each still works: **PLAY** (goes to mode / encounter select), **Store**, **Home** (back
   to the landing), **Settings** (opens the settings dialog), **Help**, the **profile** (top left), the currency
   display tooltip, **Exit** (cancel the dialog). Then enter a match (tutorial or PvP) and come back to the menu: the
   bar must come back the same.
5. Close the game. `python ic.py ui-test revert` (expect "file identical to the original; backup removed").
Send `logs\server.log` / `logs\unhandled.log` and a screenshot of the home screen.

If the header is missing or the client stops loading the menu, revert and report: that would mean GFx refuses one of
the three structural changes (dropped empty init actions, padding after a shape's end record, new character id).

## 6. The switch (Legacy / Modern) [C for the mechanism, P for the rest]

- **Preferences from Flash** (`GM_Options`, library): `SendQuery_GetBoolOption(name)` = notice `0x1000013E`,
  `SetBoolOption(name, b)` = `0x1000013F`; int / uint / float twins. C++: `0xA4DBC0` "read bool from ui." /
  `0xA4DA00` "save bool from ui." (int32 `0xA4DEF0` / `0xA4DD30`, uint32 `0xA4E220` / `0xA4E060`, float
  `0xA4E570` / `0xA4E390`, strings `0x1603274..`). Both check the option registry (`0x4D2DD0` -> `0x4D2C40`, a hash
  map keyed by the name string) and, **when the name is unknown, register it** (`0x4D8930`, type 3 = bool, default
  from a constant, false [P]; flag +0x44 = 1) before reading / storing; save then writes `UserPreferences.ini` (`0x4D9040`). So
  `User.InterfaceStyle` (int: 0 Legacy, 1 Modern) needs no exe change; first read returns 0 = Legacy.
- **INI**: `Documents\InfiniteCrisis\UserPreferences.ini`, `[User]` section holds `User.*` keys (the tester's file has
  `FirstTimeLogin=False`). Dynamic names already exist: `User.HasSeenPostEncounterVideo@<encounter>` (`0xA724A0`).
- **Per account**: once the server's `0x216A` arrived, a change from Flash is uploaded with `0x216E` (kind
  `0x10000A0E` number / `0x10000C33` bool); `ics/account.py set_preference` stores it and `preferences_for_216a`
  sends bool / number ones back at login, which the client writes into the INI (`0xA6CA80` int, `0xA6CC20` bool) - no
  server change needed.
- **Login screen** (`0x2000006D`, before any account): the INI is loaded at client start (`0x4D5740` names
  `UserPreferences.ini`) [P: start-up order not traced], so the login movie can read the last-used style locally; the
  account's value replaces it after `0x216A`.
- **How a movie would branch** (to build next):
  - (a) *Two looks in one movie*: each restyled movie keeps the Legacy art and adds the Modern art (or a second frame /
    a second set of symbols with the **same instance names**), plus one small init action of our own in that movie
    that reads `GM_Options.SendQuery_GetIntOption("User.InterfaceStyle")` and shows the right set. Existing code stays
    untouched; needs AS2 bytecode writing (small: a constant pool, push, call, if) and usually more bytes (section 4,
    length-changing repack).
  - (b) *Library-level*: change `WrapperMain.AttachHeader*` etc. to attach `HeaderCenterModern` when the preference is
    1: one decision point per screen, but it edits the shared library `0x20000025` (CWS: decompress, patch AS2,
    recompress -> length change).
  - (c) *Install-level* (works today): `ui-test apply` / `revert` is already a Legacy/Modern switch outside the game.
- **The options entry**: the settings dialog is `0x2000005F` (panes `GameplayPane`, `GraphicsPaneContents`,
  `UIPaneContents` in the library, each option a checkbox / dropdown bound by instance name and set with
  `GM_Options.SetBoolOption("User.*")`). A new "Interface: Legacy / Modern" entry = a new checkbox / dropdown instance
  in that movie plus its handler (in the movie, way (a), or in `UIPaneContents`, way (b)); "applies after restart" or
  "on next screen load" is the simple first version (the wrapper re-attaches the header on screen changes [P]).

## 7. Open points

- In-game result of section 5 (the only proof that GFx accepts the three structural changes).
- Length-changing repack (section 4) and AS2 bytecode writing are the two pieces a real Modern UI needs; neither is
  built. JPEXS is no longer installed here (it was used for the 2026-10-22 dump); everything above is plain Python.
- Whether GFx renders the badge's fill on the right side as expected (fill style 1 on a clockwise box, the Flash IDE
  convention); if the box shows only its outline, swap to fill style 0.
- The tail layout `0x27000012`'s two unidentified movies (fonts / locale libraries [P]).

## In-game result (2026-10-30 00:36-00:38)

The tester applied `python ic.py ui-test apply`, played and reported "it worked": the modified header loaded and the
menu flow ran normally (server.log: menu -> queue -> champion select -> Crime Alley match -> back to the menu, no
errors; unhandled.log empty), then reverted (`ui-test status`: movie 0x20000077 original, crc 0xd3d3ff27). Verdict:
a restyled UI movie in pack 0xA00000D0 loads and keeps its buttons working. Next steps: a length-changing repacker,
the options entry (User.InterfaceStyle), then screen by screen.
