# Install inventory: every file, pack and record type of `C:\Infinite Crisis Server` (2026-10-22)

Read-only survey of the player's install (client build `0200.0015.4235.8152`, branch `hendrix_pre`). Nothing here
comes from the game files beyond file names, IDs, short internal names, sizes and counts. **C** = confirmed (read
from the data / exe, or cross-checked two ways), **P** = probable (fits the evidence, not proven).

Method (scratch scripts, not added to the project): every pack opened with `ics/rp.py`; pack headers read raw;
record starts found as the longest list-ordered chain of the pack's own DIDs (as `rp._placed_starts`, numpy version:
58 842 of 68 900 listed records placed); typed references = `key | key | value` / `element key | value` words whose
key is a DID-kind property in `catalog/data/properties.tsv`; the exe scanned for pack ids and DIDs and disassembled
with capstone; the Wwise packages parsed (AKPK header and bank tables); the decoded server-script trees
(`data/script_trees/*.json`, 826 of 987 scripts) walked for DIDs.

## 0. Summary

| What | Count | Size |
|---|---|---|
| Files outside `server\` | 1 602 | 5.8 GB |
| Resource packs `rp\0x????????.rp` | 616 | 2.60 GB on disk, 2.58 GB decompressed |
| Listed records (DIDs) | 68 900 (52 301 distinct; 8 018 DIDs listed in more than one pack) | |
| Record prefixes present | 59 (top bytes 0x01-0xFF; 0x40-0x47 and 0x48-0x4F, 0x90-0x9F are ranges) | |
| Pack categories (header +4) | 22 values (1, 4-17, 19-24) | |
| Wwise packages `audio\**\*.pck` | 10 (167 sound banks, 13 475 x 4 + 579 streamed files) | 1.89 GB |
| Movies `video\` | 25 Bink files | 1.11 GB |
| Launcher skins `de\ en\ fr\ ru\` | 4 x 219-220 files (identical `dist\` apps) | 4 x 9.6 MB |

What the server needs from outside `rp\`: **only `InfiniteCrisis.exe`** (source of `InfiniteCrisis_patched.exe`, built
by `python ic.py patch`, and target of the static analysis). Every other non-pack file is read by the client or the
launcher by itself; the server only ever names movies, sound banks and packs by ID or name (C, section 1).

---

## 1. Every file and folder outside `rp\`

### 1.1 Game client and its engine DLLs

| File | Size | What it is | Who reads it | Server needs it? |
|---|---|---|---|---|
| `InfiniteCrisis.exe` | 26.5 MB | The game client (Turbine engine, 32-bit, version 0200.0015.4235.8152). Statically links Scaleform GFx, Havok 2012.2.1, Wwise (AK::SoundEngine, XAudio2_7), Kynapse. Imports `tbbmalloc`, `xerces-c_3_1`, `libcef`, `bink2w32`, `ijl15`, `oodle_141_win32`, `steam_api` (C, import table) | launched by `turbineclientlauncher.exe` or directly by `ic.py play` / `python -m ics play` | **yes**: patched copy + all static analysis |
| `InfiniteCrisis_patched.exe` | 26.5 MB | Built by `python ic.py patch` (`icserver/patcher.py`, server key + 4 patches) | the servers launch it | yes (generated, not original) |
| `D3D9GraphicsCore.dll`, `D3D10GraphicsCore.dll`, `D3D11GraphicsCore.dll` | 0.29 MB each | Turbine renderer back ends, chosen by `Render.GraphicsCore` in `UserPreferences.ini`; the exe also names a `NullGraphicsCore.dll` that is **not installed** (C, exe strings) | exe (LoadLibrary) | no |
| `OpenGLGraphicsCore.dll` | 0.29 MB | OpenGL back end; **no binary names it** (P: unused leftover) | nothing found | no |
| `processtexture.dll` | 0.20 MB | "Turbine Engine Process Texture" 1.0.0; **no binary names it** (P: content-tool DLL, unused at run time) | nothing found | no |
| `corestrings.dll` | 12 KB | Resource-string DLL for the exe's error messages ("corestrings.dll is missing string ID %d") | exe | no |
| `d3dcompiler_43.dll` | 2.1 MB | HLSL compiler | `D3D11GraphicsCore.dll`, `libcef`, ANGLE | no |
| `d3dcompiler_46.dll` | 3.2 MB | HLSL compiler | `libcef.dll`, `libGLESv2.dll` (ANGLE) | no |
| `tbb.dll`, `tbbmalloc.dll` | 0.15 / 0.06 MB | Intel TBB 4.2 (threads, allocator) | exe, renderers, `DeltaPatch`, launchers | no |
| `xerces-c_3_1.dll` | 1.9 MB | Apache Xerces XML parser | exe, `turbineclientlauncher.exe` | no |
| `ijl15.dll` | 0.35 MB | Intel JPEG Library | exe | no |
| `oodle_141_win32.dll` | 0.77 MB | RAD Oodle; network compression only (`OodleNetwork1TCP`, see reverse-engineering.md) | exe | no (the wire format is already handled) |
| `bink2w32.dll` | 0.34 MB | RAD Bink, version string "2.3d/1.993d": plays both Bink 1 `.bik` and Bink 2 `.bk2` (P: both players in one DLL) | exe (`./video`) | no |
| `steam_api.dll` | 0.15 MB | Steamworks (SteamAPI_Init, SteamUser, SteamFriends) | exe | no |
| `dbghelp.dll` | 1.2 MB | Minidump writer | exe, launchers, renderers | no |
| `MFC71.dll`, `msvcp71.dll`, `msvcr71.dll`, `zlib1T.dll` | 1.1 / 0.5 / 0.35 / 0.06 MB | VC 7.1 runtime, MFC, zlib 1.2.3; only import each other; **nothing else imports them** (P: leftovers of an older launcher / tools) | nothing found | no |
| `InfiniteCrisis.ico` | 79 KB | Desktop icon | shortcut | no |

### 1.2 In-game browser (CEF)

| File | Size | What | Who reads it |
|---|---|---|---|
| `turbinebrowser.exe` | 0.22 MB | Out-of-process browser ("TurbineBrowser/4.0") for store / web pages shown in the client | started by the exe (C, exe string) |
| `libcef.dll` | 38.6 MB | Chromium Embedded Framework 3.1650 | exe, `turbinebrowser.exe` |
| `cef.pak`, `locales\{en-GB,en-US,fr,zh-CN}.pak` | 2.6 MB, 4 x ~7 KB | CEF resources and UI locales ("Could not find cef.pak, CEF will not initialize!") | libcef |
| `icudt.dll` | 10 MB | ICU data for CEF | libcef |
| `ffmpegsumo.dll` | 0.87 MB | CEF media codecs | libcef |
| `libEGL.dll`, `libGLESv2.dll` | 0.1 / 0.9 MB | ANGLE (GL on D3D) for CEF | libcef |

Server: no (the browser pages were web content on Turbine's servers).

### 1.3 Launcher, patcher, crash reporter

| File | Size | What | Who reads it |
|---|---|---|---|
| `TurbineLauncher.exe` + `.exe.config` | 0.49 MB + 664 B | Qt 5.1 launcher. The config holds the login server (`ls.infinitecrisis.com:443`, `WebLoginApp-1.3/AuthenticateWS`, `LauncherWS`, `Metrics`), skin version 2.0.1 and the fallback skin `{lang}/launcher.html` (C) | user |
| `DeltaPatch.dll` | 1.8 MB | "InfiniteCrisis File Patching Client" (patches `rp\` and binaries) | `TurbineLauncher.exe` |
| `Qt5*.dll` (16), `icuin51.dll`, `icuuc51.dll`, `icudt51.dll` (22 MB) | 59 MB together | Qt 5.1.1 (WebKit, QML, network...) and its ICU 51 | `TurbineLauncher.exe` |
| `qt.conf` | 26 B | `Plugins=plugins` | Qt |
| `plugins\imageformats\q{gif,jpeg,svg}.dll`, `plugins\platforms\qwindows.dll` | 1.1 MB | Qt plugins | Qt |
| `libeay32.dll`, `ssleay32.dll` | 1.1 / 0.26 MB | OpenSSL for Qt network (HTTPS) | `Qt5Network.dll` |
| `cacert.pem` | 4.9 KB | CA bundle for HTTPS | exe, launcher, `DeltaPatch`, `turbinebrowser` (C, strings) |
| `de\`, `en\`, `fr\`, `ru\` | 9.6 MB each | Launcher HTML skin: `launcher.html` + `dist\` web app (2 js, 2 css, 45 html views incl. EULA / ToS per country, 5 language json, 6 ttf + 1 eot/svg/woff fonts, 155 png/jpg/gif images: intro animation, rewards, achievements). `dist\` is byte-identical in all four; `de`/`fr`/`ru` add `Launcher_<lang>.qm` (Qt translations) | `TurbineLauncher.exe` |
| `turbineclientlauncher.exe` | 1.6 MB | Crash-handling wrapper: starts `InfiniteCrisis.exe` with the login / region arguments (`--loginurl`, `--reportingurl`, `--loginregion`, `--language` ...) and uploads crash dumps to the crash receiver | launcher |
| `turbineclientlauncher.log`, `InfiniteCrisis-2015-06-28-...crashuploadcontext`, `InfiniteCrisis_2015-06-28_..._mini.dmp` (10 MB) | | Leftovers of a 2015 session and crash (they hold a local path and an account alias: keep them out of any shared report) | nobody (logs) |
| `uninstall.exe` | 0.4 MB | Uninstaller | user |
| `avutil-ttv-51.dll`, `swresample-ttv-0.dll`, `libmp3lame-ttv.dll`, `libmfxsw32.dll` | 0.25 / 0.11 / 0.39 / 16.2 MB | FFmpeg / LAME builds suffixed `-ttv` and Intel Media SDK: the Twitch ("TTV") broadcasting kit. **No binary in the install names them** except `swresample` -> `avutil` (P: leftover of an earlier Twitch-streaming feature) | nothing found |

Server: the launcher's login web service is replaced by `ics/server.py` (SOAP login, `GameClient.ArgTemplate`), and
`python -m ics play` passes `--loginurl` etc. itself, so none of these files are needed.

### 1.4 Movies `video\` (Bink, played from `./video` by the exe)

| File(s) | Size | Purpose | Referenced by |
|---|---|---|---|
| `map_CoastCityOverview.bik`, `map_GothamDividedOverview.bik`, `map_GothamHeightsOverview.bik` | 154 / 159 / 93 MB | Map overview shown before a match | encounter template 0x10000C45 (string in pack 0xA0000038's string tables) (C) |
| `vig_<Champion>Vignette.bik` x 7 (Batman, Doomsday, Gaslight Batman, Green Lantern, Harley Quinn, Superman, Wonder Woman) | 32-76 MB | Post-match vignette | encounter template 0x10000C1B (C) |
| `sb_<Champion>.bk2` x 6 | 8-13 MB | Champion showcase after "Champion Unlocked" | achievement twin property 0x10000BCD (e.g. 0x49000B08) (C) |
| `ic_login_movie_champion_1.bik`, `login_reward_bg_movie.bk2` | 7.5 / 14.7 MB | Login and reward-screen backgrounds | names in 0xA0000038 string tables (C) |
| `trainingintro_batman.bik` | 1.4 MB | Training intro | name in 0xA0000351 (C) |
| `<lang>\InfiniteCrisis_What_Do_You_Fight_For_1080p.bk2` (de, en, fr, ru) | 59-61 MB | Localized trailer | name in 0xA0000038 string tables (C) |
| `ic_particles_bg.bk2` | 17 MB | Particle background | **no reference found** in packs, Flash movies or exe (P: built at run time or unused) |

The `.bik`/`.bk2` names live in the 4-language string tables of `0xA0000038` (each name found 4 times). Server: only
the names / property values, never the files.

### 1.5 Sound `audio\` (Wwise file packages, read from `./audio/` by the exe)

| File | Size | Content (C, AKPK header v1) |
|---|---|---|
| `Audio_SB.pck` | 80 MB | 41 sound banks, language "sfx" |
| `Audio_Str.pck` | 143 MB | 579 streamed media files, "sfx" |
| `English(US)\`, `French(France)\`, `German\`, `Russian\` `Audio_SB.pck` | 160 MB each | 126 localized sound banks each (voice) |
| same folders `Audio_Str.pck` | 243-267 MB | 13 475 streamed media files each (voice lines) |

**Link to the packs (C):** a record `0x52xxxxxx` is `did | Wwise bank id | u32 length | bank name`; the id is the
Wwise FNV-1 32 hash of the lower-case name. All **161** distinct 0x52 records match (hash = name) and all 161 bank
ids are in the `.pck` tables; the packages hold 167 banks, so **6 banks are named by no 0x52 record** (P: loaded by
name from code, e.g. the init bank). Bank name families: `chr_*` (76, champion sounds), `FE_*` (56, front end incl.
`FE_Music_Lobby_*`), `Announcer_*` (7), `VO_*` (5), `mse_*` (4, map events), `AMB_*` (4), `Music_*` (3), `Init`,
`GlobalElements`, `Destruction`, `Turrets`, `UI`. Server: no; sound plays from scriptlets / client events. The
event ids inside the banks (`.bnk` HIRC) are not decoded by the project (only needed for a new client).

### 1.6 `server\`

This project (not part of the install). `rp\` is section 2.

---

## 2. The 616 packs

### 2.1 Pack format (C)

`+0 "10PR" | +4 category | +8 1 | +0xC payload size | +0x10 record count | +0x14 n tail streams (0 or 4) | +0x18 n x
language id (always 1, 3, 5, 6 = en, fr, de, ru) | +0x28 n x stream size`, payload at 0x400 in 0x20000-byte blocks
(last 4 bytes a trailer): `count x u32 DID` then one zlib stream; then the tail streams, one per language, each
aligned to 0x400. 130 packs have tail streams. In 124 they are **string tables** (222 distinct 0x2B tables, 13 738
entries in English); in the 5 zone packs (cat 13) they are a **localized texture** (`0x13000D9E`, one per language),
and in the UI pack 0xA00000D0 a **localized UI layout** (`0x27000012`, 1.9 MB per language) (C: decompressed;
`icserver/gamedata.text_streams` skips them because they are not 0x2B tables). So the tail is "per-language
versions of records", string tables being the common case.

Records inside the payload are 4-byte aligned (C: every placed start is aligned). A record starts with its DID,
except where the format has no own DID (0x85/0x90 nav records, most 0x1D scriptlet tables, some 0x1E/0x2B/0x11).

### 2.2 How a pack gets loaded (who references it)

| Way | Packs | Evidence |
|---|---|---|
| Hard-coded in the exe | 0xA0000039 (cat 9), 0xA0000038 (10), 0xA000011A (11) each from its own method, then 0xA000011A, 0xA0000037, 0xA00000DF, 0xA00000B3, 0xA0000103, 0xA0000351 in one method (vtable at 0x1600FBC, slots 0xA08680 / 0xA086A0 / 0xA086C0 / 0xA086F0, loader 0x9DD580); 0xA00000D0 at 0xAC7AB8 | C (`push imm32` before `call 0x9DD580`); P: staged start-up loading (enums, config, front end, then game data) |
| Encounter template 0x10000406 (in 0xA00000B3) | the 6 map packs | C |
| A map pack's list `u32 n | n x pack` (repeated once per landblock) | zone (13), layout (15), variants (14), Tutorial 1 textures 0xA00002D6/D7 (7) | C |
| Encounter template 0x10000897 | lobby-music packs 0xA0000188/189/18A (cat 23) | C |
| Champion definition `0x49` twin (inside the champion's own pack, cat 7): 0x1000035C own pack (itself), 0x100005E0 light (6), 0x100005DF wallpaper (5), 0x10000730 shared (8), 0x10000B0D skills UI (4) | 156 + 156 + 156 + 54 + 54 | C (156 variants x 5 properties) |
| UI pack 0xA00000D0 array 0x10000B62 of 0x10000B61 | 0xA00002FF (achievements), 0xA000036E (11 textures) | C |
| Record 0x48000E36 (in 0xA00000B3) 0x10000B87 | 0xA0000316 (cat 8) | C |
| The server's 0x20AF pack list / account roster | every cat 7 own pack (only the pack itself names it) | C (`ics/session.py`, `tools/roster.py`) |

**Packs nothing references** (no exe constant, no typed reference, no map list; raw 0xA0 words in textures and
shader bytecode were discarded as noise): **0xA000006F** (cat 14, shared minion variants Trooper / Soldier Drone) and
**0xA0000164** (cat 16, Meteor Storm event). Both must be named by the server (0x20AF) when used (C for "no
reference in the data", P that the original server named them).

The client finds packs by name: `0x%08x.rp` (C, exe string at 0x11FD48C). Pack slots per category: see
`tools/diag.py --packs` (zone category 0xD has a single slot).

### 2.3 Categories (header +4)

| cat | Meaning | Packs | Records | MB | String tables | Record prefixes (count) |
|---|---|---|---|---|---|---|
| 1 | map (Tutorial 1) | 1 | 48 | 1 | 0 | 13:17 80:9 81:9 82:9 85:1 90:3 |
| 4 | champion skills UI | 54 | 727 | 26 | 54 | 13:457 2B:54 48:216 |
| 5 | champion wallpaper | 156 | 312 | 181 | 0 | 13:156 48:156 |
| 6 | champion light | 156 | 514 | 30 | 0 | 13:305 48:156 52:53 |
| 7 | champion own / map textures | 158 | 6451 | 631 | 0 | 10:641 13:1217 16:428 17:320 18:353 19:489 1A:1514 1C:28 1D:262 1E:17 1F:17 2D:211 2E:245 34:3 36:148 37:167 3A:7 40:192 49:192 |
| 8 | champion shared / misc | 57 | 14061 | 254 | 55 | 10:385 11:1 13:1248 14:15 15:366 16:597 17:528 18:1784 19:310 1A:3612 1C:113 1D:774 1E:644 1F:56 2B:55 2D:235 2E:341 30:7 34:635 36:3 37:13 3A:38 3B:103 3F:4 40:668 48:784 49:668 52:74 |
| 9 | core enums | 1 | 21 | 0 | 0 | 30:1 31:19 32:1 |
| 10 | core config | 1 | 174 | 2 | 16 | 01:1 02:1 03:1 04:1 05:1 06:1 07:1 0F:1 21:5 22:5 23:1 27:2 2B:16 30:102 33:2 39:1 48:29 F7:1 FC:1 FE:1 |
| 11 | front-end render | 1 | 86 | 1 | 0 | 13:3 14:1 15:80 30:2 |
| 12 | core render | 1 | 2695 | 14 | 0 | 08:2 0C:1 10:8 13:56 14:254 15:2256 16:23 17:26 18:12 19:7 1B:1 1D:5 24:2 2A:1 2D:9 2E:13 30:4 34:1 3A:2 40:5 49:5 52:1 FF:1 |
| 13 | zone | 5 | 26327 | 717 | 0 | 08:12 10:8489 11:626 13:3067 14:116 15:3013 16:2099 17:1423 18:778 19:1781 1A:25 1C:20 1D:553 1E:1 2B:1 2D:1687 2E:1867 34:12 37:5 3E:17 40:56 48:30 49:56 50:591 52:2 |
| 14 | variants (units) | 6 | 2714 | 59 | 13 | 10:84 13:301 16:101 17:80 18:361 19:93 1A:416 1C:45 1D:193 1E:128 1F:35 2B:13 2D:71 2E:128 34:43 36:39 3B:234 40:122 48:90 49:122 52:15 |
| 15 | layout | 5 | 5016 | 95 | 49 | 08:3 10:362 11:77 13:601 14:22 15:520 16:412 17:255 18:590 19:281 1A:164 1C:52 1D:249 1E:71 1F:5 2B:49 2D:235 2E:304 30:6 34:86 35:30 36:6 3A:1 3B:77 40:180 48:155 49:180 52:43 |
| 16 | event (meteor storm) | 1 | 46 | 1 | 3 | 10:8 13:7 16:2 17:2 18:4 19:2 1A:3 1C:1 1D:1 1E:1 2B:3 2D:1 2E:1 40:4 48:1 49:4 52:1 |
| 17 | map (terrain + navmesh) | 5 | 496 | 478 | 0 | 13:341 80:45 81:45 82:45 85:5 90:15 |
| 19 | UI | 1 | 2274 | 57 | 0 | 13:1908 20:89 24:1 27:1 2B:1 40:134 48:2 49:134 52:4 |
| 20 | game data | 1 | 3911 | 32 | 112 | 10:20 13:564 14:12 15:256 16:65 17:41 18:201 19:25 1A:8 1C:4 1D:35 1E:146 21:6 2B:112 2D:18 2E:32 30:25 34:207 36:1 3A:10 3B:25 3C:11 40:732 48:622 49:732 52:1 |
| 21 | shared effects | 1 | 2736 | 22 | 0 | 10:13 13:150 14:67 15:1600 16:304 17:298 18:129 19:7 1A:3 1C:1 1D:11 1E:126 1F:1 2D:5 2E:6 40:1 48:13 49:1 |
| 22 | global textures | 1 | 56 | 1 | 0 | 13:56 |
| 23 | lobby music | 3 | 3 | 0 | 0 | 52:3 |
| 24 | training data | 1 | 232 | 1 | 7 | 13:6 2B:7 40:7 48:204 49:7 52:1 |

Notes: cat 7 = 156 champion "own" packs (model, skeleton, animations, behaviour graph, the variant's 0x40/0x49) + the
2 Tutorial 1 texture packs. cat 8 = 54 champion "shared" packs (skill scripts, effects, behaviour packs such as
0xA0000122) + 0xA00002FF, 0xA000036E, 0xA0000316. There is no category 2, 3 or 18 in this install.

### 2.4 Every pack

Columns: category, listed records, file MB, string tables (English stream), DID prefixes (top byte: count), what it
holds, who names it (section 2.2). `none` = nothing references it.

| Pack | cat | records | MB | text | prefixes | contents | named by |
|---|---|---|---|---|---|---|---|
| 0xA0000037 | 12 | 2695 | 13.5 | 0 | 08:2 0C:1 10:8 13:56 14:254 15:2256 16:23 17:26 18:12 19:7 1B:1 1D:5 24:2 2A:1 2D:9 2E:13 30:4 34:1 3A:2 40:5 49:5 52:1 FF:1 | core render pack: shader/material templates (0x14), compiled shaders (0x15), generic world states 0x2E000000- | exe |
| 0xA0000038 | 10 | 174 | 1.9 | 16 | 01:1 02:1 03:1 04:1 05:1 06:1 07:1 0F:1 21:5 22:5 23:1 27:2 2B:16 30:102 33:2 39:1 48:29 F7:1 FC:1 FE:1 | core config: engine singletons 0x01-0x07/0x0F/0xF7/0xFC/0xFE, enum tables 0x30 (graph events 0x300000A4), name tables 0x33, cameras 0x21, maps 0x22, UI layouts 0x27, 29 config records 0x48, movie names in its string tables | exe |
| 0xA0000039 | 9 | 21 | 0.1 | 0 | 30:1 31:19 32:1 | enum tables 0x31, master property table 0x32000000, 0x30800000 | exe |
| 0xA000006F | 14 | 159 | 4.1 | 1 | 10:6 13:14 16:5 17:5 18:34 19:6 1A:19 1C:2 1D:11 1E:17 1F:2 2B:1 2D:4 2E:8 34:4 36:2 3B:11 40:2 48:3 49:2 52:1 | shared minion variants (Trooper / Soldier Drone 0x4000012D / 0x4000012E) | **none** |
| 0xA0000073 | 7 | 15 | 2.9 | 0 | 10:2 13:5 16:1 17:1 19:1 2D:1 2E:1 36:1 40:1 49:1 | own (cat 7): Nightmare Batman | server (0x20AF / roster); self 0x1000035C |
| 0xA0000075 | 7 | 97 | 6.1 | 0 | 10:1 13:7 16:2 17:1 18:3 19:3 1A:71 1C:1 1D:2 2D:1 2E:2 36:1 40:1 49:1 | own (cat 7): Superman | server (0x20AF / roster); self 0x1000035C |
| 0xA0000076 | 7 | 24 | 4.9 | 0 | 10:3 13:6 16:1 17:1 18:3 19:2 1D:2 2D:1 2E:1 36:1 37:1 40:1 49:1 | own (cat 7): Gaslight Batman | server (0x20AF / roster); self 0x1000035C |
| 0xA000009A | 13 | 6674 | 141.3 | 0 | 08:1 10:2464 11:171 13:577 14:24 15:595 16:423 17:243 18:220 19:505 1A:8 1C:8 1D:170 1E:1 2B:1 2D:473 2E:521 34:2 37:2 3E:4 40:8 48:10 49:8 50:235 | zone of Gotham Heights | map list 0xa0c11af2 |
| 0xA000009B | 7 | 23 | 3.0 | 0 | 10:3 13:6 16:2 17:1 18:1 19:3 1D:1 2D:1 2E:2 36:1 40:1 49:1 | own (cat 7): Poison Ivy | server (0x20AF / roster); self 0x1000035C |
| 0xA00000A2 | 7 | 14 | 1.0 | 0 | 10:2 18:4 19:1 1D:2 2D:1 2E:1 36:1 40:1 49:1 | own (cat 7): Doomsday | server (0x20AF / roster); self 0x1000035C |
| 0xA00000A3 | 7 | 31 | 4.8 | 0 | 10:5 13:5 16:2 17:1 18:3 19:4 1D:3 2D:1 2E:2 36:1 37:2 40:1 49:1 | own (cat 7): Zatanna | server (0x20AF / roster); self 0x1000035C |
| 0xA00000B3 | 20 | 3911 | 32.0 | 112 | 10:20 13:564 14:12 15:256 16:65 17:41 18:201 19:25 1A:8 1C:4 1D:35 1E:146 21:6 2B:112 2D:18 2E:32 30:25 34:207 36:1 3A:10 3B:25 3C:11 40:732 48:622 49:732 52:1 | GAME DATA: 28 encounter templates, every champion definition / skill / status / item (0x40/0x48/0x49), 207 server scripts 0x34, 146 status FX 0x1E, 112 string tables | exe |
| 0xA00000B4 | 7 | 95 | 3.4 | 0 | 10:3 13:4 16:2 17:2 18:2 19:2 1A:70 1C:1 1D:2 1F:1 2D:1 2E:1 36:1 37:1 40:1 49:1 | own (cat 7): The Joker | server (0x20AF / roster); self 0x1000035C |
| 0xA00000B7 | 5 | 2 | 1.4 | 0 | 13:1 48:1 | wallpaper (cat 5): Gaslight Batman | 0x100005df in 0xa0000076 |
| 0xA00000B8 | 6 | 3 | 0.2 | 0 | 13:1 48:1 52:1 | light (cat 6): Gaslight Batman | 0x100005e0 in 0xa0000076 |
| 0xA00000B9 | 5 | 2 | 0.5 | 0 | 13:1 48:1 | wallpaper (cat 5): Nightmare Batman | 0x100005df in 0xa0000073 |
| 0xA00000BA | 6 | 4 | 0.1 | 0 | 13:2 48:1 52:1 | light (cat 6): Nightmare Batman | 0x100005e0 in 0xa0000073 |
| 0xA00000BB | 5 | 2 | 1.4 | 0 | 13:1 48:1 | wallpaper (cat 5): Superman | 0x100005df in 0xa0000075 |
| 0xA00000BC | 6 | 3 | 0.2 | 0 | 13:1 48:1 52:1 | light (cat 6): Superman | 0x100005e0 in 0xa0000075 |
| 0xA00000C1 | 5 | 2 | 1.4 | 0 | 13:1 48:1 | wallpaper (cat 5): Poison Ivy | 0x100005df in 0xa000009b |
| 0xA00000C2 | 6 | 4 | 0.2 | 0 | 13:2 48:1 52:1 | light (cat 6): Poison Ivy | 0x100005e0 in 0xa000009b |
| 0xA00000C3 | 5 | 2 | 1.4 | 0 | 13:1 48:1 | wallpaper (cat 5): Doomsday | 0x100005df in 0xa00000a2 |
| 0xA00000C4 | 6 | 4 | 0.2 | 0 | 13:2 48:1 52:1 | light (cat 6): Doomsday | 0x100005e0 in 0xa00000a2 |
| 0xA00000C5 | 5 | 2 | 1.4 | 0 | 13:1 48:1 | wallpaper (cat 5): Zatanna | 0x100005df in 0xa00000a3 |
| 0xA00000C6 | 6 | 4 | 0.2 | 0 | 13:2 48:1 52:1 | light (cat 6): Zatanna | 0x100005e0 in 0xa00000a3 |
| 0xA00000C7 | 5 | 2 | 1.4 | 0 | 13:1 48:1 | wallpaper (cat 5): The Joker | 0x100005df in 0xa00000b4 |
| 0xA00000C8 | 6 | 4 | 0.2 | 0 | 13:2 48:1 52:1 | light (cat 6): The Joker | 0x100005e0 in 0xa00000b4 |
| 0xA00000C9 | 7 | 22 | 1.4 | 0 | 10:5 13:3 16:2 19:5 1D:1 2D:1 2E:1 36:1 37:1 40:1 49:1 | own (cat 7): Wonder Woman | server (0x20AF / roster); self 0x1000035C |
| 0xA00000CA | 5 | 2 | 1.4 | 0 | 13:1 48:1 | wallpaper (cat 5): Wonder Woman | 0x100005df in 0xa00000c9 |
| 0xA00000CB | 6 | 3 | 0.2 | 0 | 13:1 48:1 52:1 | light (cat 6): Wonder Woman | 0x100005e0 in 0xa00000c9 |
| 0xA00000CC | 7 | 25 | 4.8 | 0 | 10:3 13:7 16:2 17:1 19:4 1D:1 2D:1 2E:1 36:1 37:2 40:1 49:1 | own (cat 7): Gaslight Catwoman | server (0x20AF / roster); self 0x1000035C |
| 0xA00000CD | 5 | 2 | 0.7 | 0 | 13:1 48:1 | wallpaper (cat 5): Gaslight Catwoman | 0x100005df in 0xa00000cc |
| 0xA00000CE | 6 | 4 | 0.2 | 0 | 13:2 48:1 52:1 | light (cat 6): Gaslight Catwoman | 0x100005e0 in 0xa00000cc |
| 0xA00000D0 | 19 | 2274 | 57.0 | 0 | 13:1908 20:89 24:1 27:1 2B:1 40:134 48:2 49:134 52:4 | UI pack: 89 Scaleform movies 0x20, 1908 textures, 134 UI entities 0x40/0x49, fonts 0x24, UI layout 0x27 | exe |
| 0xA00000D2 | 13 | 5874 | 162.2 | 0 | 08:5 10:2325 11:111 13:619 14:23 15:619 16:453 17:321 18:210 19:292 1A:4 1C:4 1D:130 2D:270 2E:315 34:2 37:3 3E:3 40:17 48:6 49:17 50:125 | zone of Coast City | map list 0xa0c122e2 |
| 0xA00000D5 | 6 | 3 | 0.2 | 0 | 13:2 48:1 | light (cat 6): Zatanna costume 1 | 0x100005e0 in 0xa00000d7 |
| 0xA00000D6 | 5 | 2 | 0.5 | 0 | 13:1 48:1 | wallpaper (cat 5): Zatanna costume 1 | 0x100005df in 0xa00000d7 |
| 0xA00000D7 | 7 | 28 | 3.6 | 0 | 10:4 13:5 16:1 17:1 18:3 19:3 1D:3 2D:1 2E:2 36:1 37:2 40:1 49:1 | own (cat 7): Zatanna costume 1 | server (0x20AF / roster); self 0x1000035C |
| 0xA00000D8 | 6 | 3 | 0.2 | 0 | 13:2 48:1 | light (cat 6): Poison Ivy costume 1 | 0x100005e0 in 0xa00000d9 |
| 0xA00000D9 | 7 | 29 | 4.7 | 0 | 10:4 13:8 16:3 17:2 18:1 19:3 1D:1 2D:1 2E:2 36:1 37:1 40:1 49:1 | own (cat 7): Poison Ivy costume 1 | server (0x20AF / roster); self 0x1000035C |
| 0xA00000DA | 5 | 2 | 1.4 | 0 | 13:1 48:1 | wallpaper (cat 5): Poison Ivy costume 1 | 0x100005df in 0xa00000d9 |
| 0xA00000DB | 5 | 2 | 1.1 | 0 | 13:1 48:1 | wallpaper (cat 5): Batman | 0x100005df in 0xa00000dd |
| 0xA00000DC | 6 | 3 | 0.2 | 0 | 13:1 48:1 52:1 | light (cat 6): Batman | 0x100005e0 in 0xa00000dd |
| 0xA00000DD | 7 | 29 | 3.9 | 0 | 10:3 13:10 16:2 17:2 18:2 19:2 1D:2 2D:1 2E:1 36:1 37:1 40:1 49:1 | own (cat 7): Batman | server (0x20AF / roster); self 0x1000035C |
| 0xA00000DF | 21 | 2736 | 21.7 | 0 | 10:13 13:150 14:67 15:1600 16:304 17:298 18:129 19:7 1A:3 1C:1 1D:11 1E:126 1F:1 2D:5 2E:6 40:1 48:13 49:1 | shared effects: 1600 compiled shaders, materials/model parts/particles, 126 status FX 0x1E (statics of the PvP maps need it) | exe |
| 0xA00000E0 | 7 | 14 | 2.2 | 0 | 10:1 13:4 16:1 17:1 19:1 1D:1 2D:1 2E:1 36:1 40:1 49:1 | own (cat 7): Green Lantern | server (0x20AF / roster); self 0x1000035C |
| 0xA00000E1 | 6 | 3 | 0.2 | 0 | 13:1 48:1 52:1 | light (cat 6): Green Lantern | 0x100005e0 in 0xa00000e0 |
| 0xA00000E2 | 5 | 2 | 1.4 | 0 | 13:1 48:1 | wallpaper (cat 5): Green Lantern | 0x100005df in 0xa00000e0 |
| 0xA00000E3 | 5 | 2 | 1.4 | 0 | 13:1 48:1 | wallpaper (cat 5): Shazam | 0x100005df in 0xa00000e5 |
| 0xA00000E4 | 6 | 4 | 0.2 | 0 | 13:2 48:1 52:1 | light (cat 6): Shazam | 0x100005e0 in 0xa00000e5 |
| 0xA00000E5 | 7 | 31 | 3.6 | 0 | 10:3 13:8 16:3 17:3 18:4 19:2 1D:2 2D:1 2E:1 36:1 37:1 40:1 49:1 | own (cat 7): Shazam | server (0x20AF / roster); self 0x1000035C |
| 0xA00000E9 | 6 | 4 | 0.2 | 0 | 13:2 48:1 52:1 | light (cat 6): Gaslight Joker | 0x100005e0 in 0xa00000eb |
| 0xA00000EA | 5 | 2 | 1.4 | 0 | 13:1 48:1 | wallpaper (cat 5): Gaslight Joker | 0x100005df in 0xa00000eb |
| 0xA00000EB | 7 | 22 | 4.1 | 0 | 10:4 13:5 16:2 17:1 19:3 1D:1 2D:1 2E:1 36:1 37:1 40:1 49:1 | own (cat 7): Gaslight Joker | server (0x20AF / roster); self 0x1000035C |
| 0xA00000F1 | 5 | 2 | 0.7 | 0 | 13:1 48:1 | wallpaper (cat 5): The Joker costume 1 | 0x100005df in 0xa00000f3 |
| 0xA00000F2 | 6 | 3 | 0.2 | 0 | 13:2 48:1 | light (cat 6): The Joker costume 1 | 0x100005e0 in 0xa00000f3 |
| 0xA00000F3 | 7 | 93 | 3.4 | 0 | 10:1 13:6 16:2 17:1 18:2 19:2 1A:70 1C:1 1D:2 1F:1 2D:1 2E:1 36:1 40:1 49:1 | own (cat 7): The Joker costume 1 | server (0x20AF / roster); self 0x1000035C |
| 0xA00000F5 | 6 | 4 | 0.2 | 0 | 13:2 48:1 52:1 | light (cat 6): Flash | 0x100005e0 in 0xa00000f7 |
| 0xA00000F6 | 5 | 2 | 1.1 | 0 | 13:1 48:1 | wallpaper (cat 5): Flash | 0x100005df in 0xa00000f7 |
| 0xA00000F7 | 7 | 75 | 6.2 | 0 | 10:8 13:11 16:8 17:7 18:11 19:6 1A:3 1C:2 1D:6 1E:2 2D:3 2E:5 36:1 40:1 49:1 | own (cat 7): Flash | server (0x20AF / roster); self 0x1000035C |
| 0xA00000F8 | 6 | 3 | 0.2 | 0 | 13:2 48:1 | light (cat 6): Gaslight Catwoman costume 1 | 0x100005e0 in 0xa00000fa |
| 0xA00000F9 | 5 | 2 | 1.4 | 0 | 13:1 48:1 | wallpaper (cat 5): Gaslight Catwoman costume 1 | 0x100005df in 0xa00000fa |
| 0xA00000FA | 7 | 27 | 2.4 | 0 | 10:4 13:7 16:3 17:1 19:4 1D:1 2D:1 2E:1 36:1 37:2 40:1 49:1 | own (cat 7): Gaslight Catwoman costume 1 | server (0x20AF / roster); self 0x1000035C |
| 0xA00000FC | 13 | 4941 | 166.3 | 0 | 08:2 10:1935 11:53 13:699 14:24 15:655 16:445 17:346 18:184 19:149 1D:71 2D:143 2E:145 34:3 3E:4 40:8 48:5 49:8 50:62 | zone of Gotham Divided | map list 0xa0c11ad2 |
| 0xA00000FE | 5 | 2 | 1.4 | 0 | 13:1 48:1 | wallpaper (cat 5): Doomsday costume 1 | 0x100005df in 0xa0000100 |
| 0xA00000FF | 6 | 3 | 0.2 | 0 | 13:2 48:1 | light (cat 6): Doomsday costume 1 | 0x100005e0 in 0xa0000100 |
| 0xA0000100 | 7 | 31 | 3.9 | 0 | 10:5 13:6 16:1 17:1 18:4 19:4 1D:2 2D:1 2E:1 36:1 37:3 40:1 49:1 | own (cat 7): Doomsday costume 1 | server (0x20AF / roster); self 0x1000035C |
| 0xA0000103 | 22 | 56 | 0.5 | 0 | 13:56 | 56 textures (global UI / HUD art, probable) | exe |
| 0xA0000108 | 5 | 2 | 1.4 | 0 | 13:1 48:1 | wallpaper (cat 5): Cyborg | 0x100005df in 0xa000010a |
| 0xA0000109 | 6 | 4 | 0.2 | 0 | 13:2 48:1 52:1 | light (cat 6): Cyborg | 0x100005e0 in 0xa000010a |
| 0xA000010A | 7 | 35 | 5.5 | 0 | 10:3 13:11 16:3 17:3 19:3 1D:3 2D:3 2E:3 36:1 40:1 49:1 | own (cat 7): Cyborg | server (0x20AF / roster); self 0x1000035C |
| 0xA000010B | 8 | 202 | 2.8 | 1 | 10:3 13:17 16:11 17:10 18:21 19:4 1A:71 1C:1 1D:11 1E:11 1F:1 2B:1 2D:3 2E:3 34:10 3B:2 40:4 48:13 49:4 52:1 | shared (cat 8): Gaslight Catwoman | 0x10000730 in 0xa00000cc, 0x10000730 in 0xa00000fa, 0x10000730 in 0xa0000275 |
| 0xA000010C | 7 | 25 | 4.6 | 0 | 10:3 13:6 16:1 17:1 18:4 19:2 1D:2 2D:1 2E:1 36:1 37:1 40:1 49:1 | own (cat 7): Gaslight Batman costume 1 | server (0x20AF / roster); self 0x1000035C |
| 0xA000010F | 5 | 2 | 1.1 | 0 | 13:1 48:1 | wallpaper (cat 5): Gaslight Batman costume 1 | 0x100005df in 0xa000010c |
| 0xA0000110 | 6 | 3 | 0.2 | 0 | 13:2 48:1 | light (cat 6): Gaslight Batman costume 1 | 0x100005e0 in 0xa000010c |
| 0xA0000111 | 8 | 230 | 6.4 | 1 | 10:7 13:26 16:11 17:11 18:16 19:7 1A:65 1C:2 1D:17 1E:11 1F:1 2B:1 2D:5 2E:9 34:13 37:2 3B:2 40:4 48:15 49:4 52:1 | shared (cat 8): Poison Ivy | 0x10000730 in 0xa000009b, 0x10000730 in 0xa00000d9, 0x10000730 in 0xa0000272, +1 |
| 0xA0000112 | 8 | 273 | 3.8 | 1 | 10:8 13:24 16:18 17:13 18:42 19:12 1A:75 1C:2 1D:18 1E:9 1F:1 2B:1 2D:8 2E:9 34:10 3A:1 3B:1 40:3 48:14 49:3 52:1 | shared (cat 8): Cyborg | 0x10000730 in 0xa000010a, 0x10000730 in 0xa000022b |
| 0xA0000113 | 8 | 257 | 4.0 | 1 | 10:5 13:16 16:8 17:7 18:40 19:6 1A:76 1C:4 1D:17 1E:18 1F:1 2B:1 2D:5 2E:9 34:13 3B:2 40:5 48:18 49:5 52:1 | shared (cat 8): Zatanna | 0x10000730 in 0xa00000a3, 0x10000730 in 0xa00000d7, 0x10000730 in 0xa00002aa |
| 0xA0000114 | 8 | 206 | 4.0 | 1 | 10:4 13:24 16:6 17:6 18:28 19:2 1A:67 1C:3 1D:10 1E:10 1F:1 2B:1 2D:2 2E:2 34:13 3A:1 3B:2 40:3 48:17 49:3 52:1 | shared (cat 8): Gaslight Joker | 0x10000730 in 0xa00000eb, 0x10000730 in 0xa00001dc, 0x10000730 in 0xa00001fe, +1 |
| 0xA0000115 | 8 | 292 | 6.6 | 1 | 10:17 13:23 16:10 17:9 18:49 19:15 1A:63 1C:2 1D:22 1E:12 1F:1 2B:1 2D:13 2E:18 34:11 3A:1 3B:1 40:6 48:11 49:6 52:1 | shared (cat 8): Green Lantern | 0x10000730 in 0xa00000e0, 0x10000730 in 0xa00001ef, 0x10000730 in 0xa0000307 |
| 0xA0000116 | 8 | 223 | 3.8 | 1 | 10:4 13:20 16:9 17:9 18:16 19:4 1A:89 1C:3 1D:11 1E:8 1F:1 2B:1 2D:3 2E:4 34:13 3B:2 40:3 48:19 49:3 52:1 | shared (cat 8): Nightmare Batman | 0x10000730 in 0xa0000073, 0x10000730 in 0xa0000148, 0x10000730 in 0xa00001e2, +1 |
| 0xA000011A | 11 | 86 | 1.2 | 0 | 13:3 14:1 15:80 30:2 | front-end / login render pack: 80 compiled shaders 0x15, 2 enum tables 0x30 | exe |
| 0xA000011B | 8 | 230 | 3.1 | 1 | 10:11 11:1 13:17 14:1 15:28 16:10 17:5 18:28 19:14 1A:10 1C:4 1D:20 1E:6 2B:1 2D:8 2E:13 34:16 37:3 3A:1 3B:2 40:7 48:16 49:7 52:1 | shared (cat 8): The Joker | 0x10000730 in 0xa00000b4, 0x10000730 in 0xa00000f3, 0x10000730 in 0xa00001df, +2 |
| 0xA000011C | 8 | 200 | 5.3 | 1 | 10:4 13:22 16:10 17:9 18:15 19:6 1A:75 1C:1 1D:8 1E:9 1F:1 2B:1 2D:4 2E:4 34:11 3B:1 40:2 48:14 49:2 52:1 | shared (cat 8): Doomsday | 0x10000730 in 0xa00000a2, 0x10000730 in 0xa0000100, 0x10000730 in 0xa0000232 |
| 0xA000011D | 8 | 191 | 3.3 | 1 | 10:3 13:18 16:9 17:10 18:17 19:3 1A:68 1C:1 1D:10 1E:13 1F:1 2B:1 2D:2 2E:2 34:9 37:1 3A:1 3B:3 40:2 48:14 49:2 52:1 | shared (cat 8): Superman | 0x10000730 in 0xa0000075, 0x10000730 in 0xa0000212, 0x10000730 in 0xa0000238, +3 |
| 0xA000011E | 8 | 212 | 4.0 | 1 | 10:4 13:19 14:1 16:8 17:8 18:22 19:3 1A:84 1C:2 1D:11 1E:13 1F:1 2B:1 2D:2 2E:2 34:9 37:1 3B:2 40:3 48:12 49:3 52:1 | shared (cat 8): Wonder Woman | 0x10000730 in 0xa00000c9, 0x10000730 in 0xa0000154, 0x10000730 in 0xa0000247 |
| 0xA000011F | 8 | 200 | 3.3 | 1 | 10:3 13:17 16:8 17:7 18:20 19:4 1A:74 1C:2 1D:10 1E:10 1F:1 2B:1 2D:3 2E:3 34:10 3B:2 40:4 48:15 49:4 52:2 | shared (cat 8): Batman | 0x10000730 in 0xa00000dd, 0x10000730 in 0xa0000180, 0x10000730 in 0xa00001e5, +1 |
| 0xA0000120 | 8 | 226 | 4.0 | 1 | 10:5 13:20 16:9 17:6 18:26 19:8 1A:70 1C:3 1D:16 1E:7 1F:2 2B:1 2D:5 2E:8 30:1 34:11 3B:5 40:4 48:14 49:4 52:1 | shared (cat 8): Shazam | 0x10000730 in 0xa00000e5, 0x10000730 in 0xa00001d8, 0x10000730 in 0xa0000322 |
| 0xA0000121 | 8 | 182 | 3.2 | 1 | 10:4 13:14 16:10 17:10 18:24 19:2 1A:63 1C:1 1D:10 1E:10 1F:1 2B:1 2D:2 2E:1 34:9 3A:1 3B:3 40:2 48:11 49:2 52:1 | shared (cat 8): Flash | 0x10000730 in 0xa00000f7, 0x10000730 in 0xa00001ec, 0x10000730 in 0xa000034f |
| 0xA0000122 | 8 | 216 | 2.8 | 1 | 10:6 13:21 16:11 17:11 18:20 19:6 1A:70 1C:2 1D:12 1E:6 1F:1 2B:1 2D:6 2E:6 34:12 3A:1 3B:1 40:5 48:11 49:5 52:2 | shared (cat 8): Gaslight Batman | 0x10000730 in 0xa0000076, 0x10000730 in 0xa000010c, 0x10000730 in 0xa0000183, +1 |
| 0xA0000123 | 7 | 36 | 2.9 | 0 | 10:5 13:10 16:5 17:2 19:5 1D:1 2D:1 2E:1 36:1 37:3 40:1 49:1 | own (cat 7): Atomic Wonder Woman | server (0x20AF / roster); self 0x1000035C |
| 0xA0000124 | 8 | 176 | 3.1 | 1 | 13:16 16:5 17:6 18:23 1A:65 1C:1 1D:9 1E:13 1F:1 2B:1 34:11 3A:1 3B:2 40:3 48:15 49:3 52:1 | shared (cat 8): Atomic Wonder Woman | 0x10000730 in 0xa0000123, 0x10000730 in 0xa0000208, 0x10000730 in 0xa00002f9 |
| 0xA0000125 | 6 | 4 | 0.2 | 0 | 13:2 48:1 52:1 | light (cat 6): Atomic Wonder Woman | 0x100005e0 in 0xa0000123 |
| 0xA0000126 | 5 | 2 | 1.4 | 0 | 13:1 48:1 | wallpaper (cat 5): Atomic Wonder Woman | 0x100005df in 0xa0000123 |
| 0xA000012A | 5 | 2 | 1.1 | 0 | 13:1 48:1 | wallpaper (cat 5): Catwoman | 0x100005df in 0xa000012d |
| 0xA000012B | 6 | 4 | 0.2 | 0 | 13:2 48:1 52:1 | light (cat 6): Catwoman | 0x100005e0 in 0xa000012d |
| 0xA000012C | 8 | 216 | 3.0 | 1 | 10:12 13:18 14:1 15:14 16:9 17:6 18:17 19:6 1A:64 1C:1 1D:12 1E:8 1F:1 2B:1 2D:3 2E:3 30:1 34:11 3A:1 3B:5 40:3 48:15 49:3 52:1 | shared (cat 8): Catwoman | 0x10000730 in 0xa000012d, 0x10000730 in 0xa0000218, 0x10000730 in 0xa00002ca |
| 0xA000012D | 7 | 27 | 1.8 | 0 | 10:2 13:8 16:7 17:1 19:3 1D:1 2D:1 2E:1 36:1 40:1 49:1 | own (cat 7): Catwoman | server (0x20AF / roster); self 0x1000035C |
| 0xA0000142 | 6 | 4 | 0.2 | 0 | 13:2 48:1 52:1 | light (cat 6): Arcane Green Lantern | 0x100005e0 in 0xa0000144 |
| 0xA0000143 | 5 | 2 | 1.1 | 0 | 13:1 48:1 | wallpaper (cat 5): Arcane Green Lantern | 0x100005df in 0xa0000144 |
| 0xA0000144 | 7 | 98 | 4.3 | 0 | 10:5 13:5 16:1 17:1 19:4 1A:68 1C:1 1D:2 1F:1 2D:2 2E:3 36:1 37:2 40:1 49:1 | own (cat 7): Arcane Green Lantern | server (0x20AF / roster); self 0x1000035C |
| 0xA0000145 | 8 | 246 | 6.8 | 1 | 10:12 13:39 16:21 17:19 18:37 19:11 1A:8 1C:5 1D:14 1E:20 2B:1 2D:9 2E:9 34:15 3A:1 3B:1 40:4 48:15 49:4 52:1 | shared (cat 8): Arcane Green Lantern | 0x10000730 in 0xa0000144, 0x10000730 in 0xa0000205, 0x10000730 in 0xa00002f0, +1 |
| 0xA0000146 | 5 | 2 | 1.1 | 0 | 13:1 48:1 | wallpaper (cat 5): Nightmare Batman costume 1 | 0x100005df in 0xa0000148 |
| 0xA0000147 | 6 | 3 | 0.1 | 0 | 13:2 48:1 | light (cat 6): Nightmare Batman costume 1 | 0x100005e0 in 0xa0000148 |
| 0xA0000148 | 7 | 22 | 4.6 | 0 | 10:4 13:6 16:1 17:1 19:3 2D:1 2E:1 36:1 37:2 40:1 49:1 | own (cat 7): Nightmare Batman costume 1 | server (0x20AF / roster); self 0x1000035C |
| 0xA000014E | 5 | 2 | 1.4 | 0 | 13:1 48:1 | wallpaper (cat 5): Atomic Green Lantern | 0x100005df in 0xa0000151 |
| 0xA000014F | 6 | 4 | 0.2 | 0 | 13:2 48:1 52:1 | light (cat 6): Atomic Green Lantern | 0x100005e0 in 0xa0000151 |
| 0xA0000150 | 8 | 296 | 3.8 | 1 | 10:15 13:25 16:15 17:14 18:50 19:11 1A:73 1C:4 1D:17 1E:15 1F:1 2B:1 2D:9 2E:9 34:12 3B:1 3F:1 40:5 48:12 49:5 52:1 | shared (cat 8): Atomic Green Lantern | 0x10000730 in 0xa0000151, 0x10000730 in 0xa000021b, 0x10000730 in 0xa0000312 |
| 0xA0000151 | 7 | 21 | 1.6 | 0 | 10:3 13:6 16:1 17:1 18:1 19:2 1D:1 2D:1 2E:1 36:1 37:1 40:1 49:1 | own (cat 7): Atomic Green Lantern | server (0x20AF / roster); self 0x1000035C |
| 0xA0000152 | 5 | 2 | 1.4 | 0 | 13:1 48:1 | wallpaper (cat 5): Wonder Woman costume 1 | 0x100005df in 0xa0000154 |
| 0xA0000153 | 6 | 3 | 0.2 | 0 | 13:2 48:1 | light (cat 6): Wonder Woman costume 1 | 0x100005e0 in 0xa0000154 |
| 0xA0000154 | 7 | 35 | 5.9 | 0 | 10:5 13:10 16:4 17:2 19:6 1D:1 2D:1 2E:1 36:1 37:2 40:1 49:1 | own (cat 7): Wonder Woman costume 1 | server (0x20AF / roster); self 0x1000035C |
| 0xA0000155 | 5 | 2 | 0.7 | 0 | 13:1 48:1 | wallpaper (cat 5): Mecha Wonder Woman | 0x100005df in 0xa0000156 |
| 0xA0000156 | 7 | 22 | 3.4 | 0 | 10:3 13:6 16:3 17:1 19:2 1D:1 2D:1 2E:1 36:1 3A:1 40:1 49:1 | own (cat 7): Mecha Wonder Woman | server (0x20AF / roster); self 0x1000035C |
| 0xA0000157 | 8 | 225 | 3.3 | 1 | 10:5 13:18 16:8 17:7 18:35 19:6 1A:67 1C:3 1D:14 1E:10 1F:1 2B:1 2D:5 2E:6 34:14 3B:2 40:3 48:16 49:3 52:1 | shared (cat 8): Mecha Wonder Woman | 0x10000730 in 0xa0000156, 0x10000730 in 0xa0000225, 0x10000730 in 0xa0000368 |
| 0xA0000158 | 6 | 4 | 0.2 | 0 | 13:2 48:1 52:1 | light (cat 6): Mecha Wonder Woman | 0x100005e0 in 0xa0000156 |
| 0xA0000161 | 14 | 673 | 13.5 | 4 | 10:19 13:73 16:24 17:17 18:80 19:23 1A:103 1C:11 1D:48 1E:28 1F:9 2B:4 2D:18 2E:33 34:8 36:10 3B:73 40:32 48:24 49:32 52:4 | variants (units) of Coast City | map list 0xa0c122e2 |
| 0xA0000162 | 15 | 1021 | 18.3 | 12 | 10:86 11:15 13:124 14:5 15:92 16:97 17:51 18:121 19:61 1A:33 1C:11 1D:45 1E:14 1F:1 2B:12 2D:50 2E:57 30:1 34:12 35:3 36:1 3B:22 40:32 48:35 49:32 52:8 | layout of Coast City | map list 0xa0c122e2 |
| 0xA0000164 | 16 | 46 | 1.0 | 3 | 10:8 13:7 16:2 17:2 18:4 19:2 1A:3 1C:1 1D:1 1E:1 2B:3 2D:1 2E:1 40:4 48:1 49:4 52:1 | Meteor Storm event (Meteor Fragment 0x400006F1, bank mse_MeteorStorm) | **none** |
| 0xA0000168 | 15 | 1178 | 20.5 | 13 | 10:85 11:12 13:156 14:4 15:90 16:97 17:57 18:134 19:60 1A:49 1C:16 1D:52 1E:11 1F:1 2B:13 2D:48 2E:55 30:1 34:26 35:3 36:3 3B:23 40:60 48:55 49:60 52:7 | layout of Gotham Divided | map list 0xa0c11ad2 |
| 0xA000016B | 15 | 832 | 16.0 | 4 | 08:3 10:57 11:20 13:101 14:5 15:125 16:65 17:55 18:69 19:52 1A:17 1C:6 1D:30 1E:9 1F:1 2B:4 2D:47 2E:72 30:1 34:9 35:4 3A:1 3B:6 40:25 48:16 49:25 52:7 | layout of Gotham Heights | map list 0xa0c11af2 |
| 0xA000016E | 14 | 672 | 14.2 | 3 | 10:21 13:73 16:22 17:17 18:78 19:22 1A:119 1C:12 1D:50 1E:30 1F:11 2B:3 2D:17 2E:31 34:11 36:10 3B:72 40:23 48:23 49:23 52:4 | variants (units) of Gotham Divided | map list 0xa0c11ad2 |
| 0xA0000173 | 6 | 4 | 0.2 | 0 | 13:2 48:1 52:1 | light (cat 6): Robin | 0x100005e0 in 0xa0000175 |
| 0xA0000174 | 5 | 2 | 0.5 | 0 | 13:1 48:1 | wallpaper (cat 5): Robin | 0x100005df in 0xa0000175 |
| 0xA0000175 | 7 | 29 | 1.8 | 0 | 10:3 13:7 16:2 17:2 18:2 19:2 1D:1 2D:1 2E:1 36:1 37:1 40:3 49:3 | own (cat 7): Robin | server (0x20AF / roster); self 0x1000035C |
| 0xA0000176 | 8 | 195 | 3.2 | 1 | 10:3 13:14 16:7 17:7 18:22 19:3 1A:70 1C:1 1D:10 1E:17 1F:1 2B:1 2D:3 2E:3 34:11 3A:1 3B:1 48:19 52:1 | shared (cat 8): Robin | 0x10000730 in 0xa0000175, 0x10000730 in 0xa0000244, 0x10000730 in 0xa00002c4 |
| 0xA0000179 | 14 | 234 | 6.6 | 1 | 10:8 13:32 16:8 17:8 18:43 19:8 1A:37 1C:4 1D:15 1E:17 1F:3 2B:1 2D:6 2E:10 34:4 36:3 3B:14 40:3 48:5 49:3 52:2 | variants (units) of Gotham Heights | map list 0xa0c11af2 |
| 0xA000017E | 5 | 2 | 1.1 | 0 | 13:1 48:1 | wallpaper (cat 5): Batman costume 1 | 0x100005df in 0xa0000180 |
| 0xA000017F | 6 | 3 | 0.2 | 0 | 13:2 48:1 | light (cat 6): Batman costume 1 | 0x100005e0 in 0xa0000180 |
| 0xA0000180 | 7 | 23 | 2.9 | 0 | 10:2 13:5 16:2 17:1 18:2 19:3 1D:2 2D:1 2E:1 36:1 37:1 40:1 49:1 | own (cat 7): Batman costume 1 | server (0x20AF / roster); self 0x1000035C |
| 0xA0000181 | 6 | 3 | 0.2 | 0 | 13:2 48:1 | light (cat 6): Gaslight Batman costume 2 | 0x100005e0 in 0xa0000183 |
| 0xA0000182 | 5 | 2 | 1.1 | 0 | 13:1 48:1 | wallpaper (cat 5): Gaslight Batman costume 2 | 0x100005df in 0xa0000183 |
| 0xA0000183 | 7 | 28 | 6.2 | 0 | 10:4 13:6 16:1 17:1 18:4 19:3 1D:2 2D:1 2E:1 36:1 37:2 40:1 49:1 | own (cat 7): Gaslight Batman costume 2 | server (0x20AF / roster); self 0x1000035C |
| 0xA0000184 | 5 | 2 | 0.5 | 0 | 13:1 48:1 | wallpaper (cat 5): Harley Quinn | 0x100005df in 0xa0000187 |
| 0xA0000185 | 6 | 3 | 0.2 | 0 | 13:1 48:1 52:1 | light (cat 6): Harley Quinn | 0x100005e0 in 0xa0000187 |
| 0xA0000186 | 8 | 188 | 3.6 | 1 | 10:2 13:15 16:9 17:9 18:23 19:2 1A:62 1C:2 1D:12 1E:12 1F:1 2B:1 2D:2 2E:5 34:11 3A:1 3B:2 40:3 48:10 49:3 52:1 | shared (cat 8): Harley Quinn | 0x10000730 in 0xa0000187, 0x10000730 in 0xa0000215, 0x10000730 in 0xa000021e, +1 |
| 0xA0000187 | 7 | 49 | 4.8 | 0 | 10:12 13:5 16:3 17:3 18:4 19:8 1D:1 2D:4 2E:4 36:1 37:1 3A:1 40:1 49:1 | own (cat 7): Harley Quinn | server (0x20AF / roster); self 0x1000035C |
| 0xA0000188 | 23 | 1 | 0.0 | 0 | 52:1 | lobby music bank (Coast City) | 0x10000897 in 0xa00000b3 |
| 0xA0000189 | 23 | 1 | 0.0 | 0 | 52:1 | lobby music bank (Gotham Heights) | 0x10000897 in 0xa00000b3 |
| 0xA000018A | 23 | 1 | 0.0 | 0 | 52:1 | lobby music bank (Gotham Divided / default) | 0x10000897 in 0xa00000b3 |
| 0xA000018B | 5 | 2 | 1.4 | 0 | 13:1 48:1 | wallpaper (cat 5): Atomic Poison Ivy | 0x100005df in 0xa000018e |
| 0xA000018C | 6 | 4 | 0.2 | 0 | 13:2 48:1 52:1 | light (cat 6): Atomic Poison Ivy | 0x100005e0 in 0xa000018e |
| 0xA000018D | 8 | 262 | 7.5 | 1 | 10:8 13:26 16:16 17:13 18:34 19:8 1A:75 1C:4 1D:14 1E:13 1F:1 2B:1 2D:5 2E:7 34:11 3A:1 3B:1 40:4 48:15 49:4 52:1 | shared (cat 8): Atomic Poison Ivy | 0x10000730 in 0xa000018e, 0x10000730 in 0xa0000235, 0x10000730 in 0xa0000365 |
| 0xA000018E | 7 | 28 | 2.9 | 0 | 10:6 13:4 16:3 17:2 18:1 19:4 1D:1 2D:1 2E:1 36:1 37:2 40:1 49:1 | own (cat 7): Atomic Poison Ivy | server (0x20AF / roster); self 0x1000035C |
| 0xA000018F | 5 | 2 | 1.4 | 0 | 13:1 48:1 | wallpaper (cat 5): Aquaman | 0x100005df in 0xa0000192 |
| 0xA0000190 | 6 | 4 | 0.2 | 0 | 13:2 48:1 52:1 | light (cat 6): Aquaman | 0x100005e0 in 0xa0000192 |
| 0xA0000191 | 8 | 233 | 4.3 | 1 | 10:3 13:24 16:11 17:10 18:35 19:4 1A:67 1C:2 1D:13 1E:17 1F:1 2B:1 2D:3 2E:3 34:14 3A:1 3B:1 40:3 48:15 49:3 52:2 | shared (cat 8): Aquaman | 0x10000730 in 0xa0000192, 0x10000730 in 0xa0000251, 0x10000730 in 0xa00002c1 |
| 0xA0000192 | 7 | 22 | 3.3 | 0 | 10:2 13:5 16:1 17:1 18:5 19:1 1D:2 2D:1 2E:1 36:1 40:1 49:1 | own (cat 7): Aquaman | server (0x20AF / roster); self 0x1000035C |
| 0xA00001CF | 6 | 4 | 0.2 | 0 | 13:2 48:1 52:1 | light (cat 6): Star Sapphire | 0x100005e0 in 0xa00001d1 |
| 0xA00001D0 | 5 | 2 | 1.4 | 0 | 13:1 48:1 | wallpaper (cat 5): Star Sapphire | 0x100005df in 0xa00001d1 |
| 0xA00001D1 | 7 | 88 | 5.4 | 0 | 10:2 13:7 16:2 17:2 19:2 1A:61 1C:1 1D:1 1F:1 2D:1 2E:1 34:1 36:1 37:1 40:2 49:2 | own (cat 7): Star Sapphire | server (0x20AF / roster); self 0x1000035C |
| 0xA00001D2 | 8 | 281 | 7.4 | 1 | 10:17 13:26 16:25 17:15 18:44 19:10 1A:23 1C:4 1D:29 1E:18 1F:1 2B:1 2D:9 2E:12 34:14 3A:1 3B:7 40:5 48:14 49:5 52:1 | shared (cat 8): Star Sapphire | 0x10000730 in 0xa00001d1, 0x10000730 in 0xa000023b, 0x10000730 in 0xa000032b |
| 0xA00001D6 | 5 | 2 | 0.7 | 0 | 13:1 48:1 | wallpaper (cat 5): Shazam costume 1 | 0x100005df in 0xa00001d8 |
| 0xA00001D7 | 6 | 3 | 0.2 | 0 | 13:2 48:1 | light (cat 6): Shazam costume 1 | 0x100005e0 in 0xa00001d8 |
| 0xA00001D8 | 7 | 22 | 2.0 | 0 | 10:2 13:6 16:1 17:1 18:2 19:2 1D:2 2D:1 2E:1 36:1 37:1 40:1 49:1 | own (cat 7): Shazam costume 1 | server (0x20AF / roster); self 0x1000035C |
| 0xA00001DA | 6 | 3 | 0.2 | 0 | 13:2 48:1 | light (cat 6): Gaslight Joker costume 1 | 0x100005e0 in 0xa00001dc |
| 0xA00001DB | 5 | 2 | 1.4 | 0 | 13:1 48:1 | wallpaper (cat 5): Gaslight Joker costume 1 | 0x100005df in 0xa00001dc |
| 0xA00001DC | 7 | 34 | 2.6 | 0 | 10:6 13:10 16:3 17:2 19:5 1D:1 2D:1 2E:1 36:1 37:2 40:1 49:1 | own (cat 7): Gaslight Joker costume 1 | server (0x20AF / roster); self 0x1000035C |
| 0xA00001DD | 5 | 2 | 1.4 | 0 | 13:1 48:1 | wallpaper (cat 5): The Joker costume 2 | 0x100005df in 0xa00001df |
| 0xA00001DE | 6 | 3 | 0.2 | 0 | 13:2 48:1 | light (cat 6): The Joker costume 2 | 0x100005e0 in 0xa00001df |
| 0xA00001DF | 7 | 99 | 6.0 | 0 | 10:3 13:9 16:2 17:1 18:2 19:3 1A:70 1C:1 1D:1 1F:1 2D:1 2E:1 36:1 37:1 40:1 49:1 | own (cat 7): The Joker costume 2 | server (0x20AF / roster); self 0x1000035C |
| 0xA00001E0 | 6 | 3 | 0.2 | 0 | 13:2 48:1 | light (cat 6): Nightmare Batman costume 2 | 0x100005e0 in 0xa00001e2 |
| 0xA00001E1 | 5 | 2 | 1.4 | 0 | 13:1 48:1 | wallpaper (cat 5): Nightmare Batman costume 2 | 0x100005df in 0xa00001e2 |
| 0xA00001E2 | 7 | 21 | 5.3 | 0 | 10:3 13:6 16:2 17:2 19:2 2D:1 2E:1 36:1 37:1 40:1 49:1 | own (cat 7): Nightmare Batman costume 2 | server (0x20AF / roster); self 0x1000035C |
| 0xA00001E3 | 5 | 2 | 1.4 | 0 | 13:1 48:1 | wallpaper (cat 5): Batman costume 2 | 0x100005df in 0xa00001e5 |
| 0xA00001E4 | 6 | 3 | 0.2 | 0 | 13:2 48:1 | light (cat 6): Batman costume 2 | 0x100005e0 in 0xa00001e5 |
| 0xA00001E5 | 7 | 31 | 2.2 | 0 | 10:8 13:5 16:1 17:1 18:2 19:4 1D:2 2D:1 2E:1 36:1 37:3 40:1 49:1 | own (cat 7): Batman costume 2 | server (0x20AF / roster); self 0x1000035C |
| 0xA00001E6 | 5 | 2 | 1.4 | 0 | 13:1 48:1 | wallpaper (cat 5): Mecha Superman | 0x100005df in 0xa00001e9 |
| 0xA00001E7 | 6 | 4 | 0.2 | 0 | 13:2 48:1 52:1 | light (cat 6): Mecha Superman | 0x100005e0 in 0xa00001e9 |
| 0xA00001E8 | 8 | 302 | 4.1 | 1 | 10:7 13:19 14:1 15:64 16:9 17:6 18:42 19:9 1A:66 1C:2 1D:13 1E:17 1F:1 2B:1 2D:6 2E:6 34:10 3A:1 3B:1 3F:1 40:4 48:11 49:4 52:1 | shared (cat 8): Mecha Superman | 0x10000730 in 0xa00001e9, 0x10000730 in 0xa000025c, 0x10000730 in 0xa00003ac |
| 0xA00001E9 | 7 | 29 | 3.5 | 0 | 10:3 13:6 16:1 17:1 18:8 19:1 1D:3 2D:1 2E:2 36:1 40:1 49:1 | own (cat 7): Mecha Superman | server (0x20AF / roster); self 0x1000035C |
| 0xA00001EA | 5 | 2 | 1.4 | 0 | 13:1 48:1 | wallpaper (cat 5): Flash costume 1 | 0x100005df in 0xa00001ec |
| 0xA00001EB | 6 | 3 | 0.2 | 0 | 13:2 48:1 | light (cat 6): Flash costume 1 | 0x100005e0 in 0xa00001ec |
| 0xA00001EC | 7 | 75 | 6.9 | 0 | 10:8 13:11 16:8 17:7 18:11 19:6 1A:3 1C:2 1D:6 1E:2 2D:3 2E:5 36:1 40:1 49:1 | own (cat 7): Flash costume 1 | server (0x20AF / roster); self 0x1000035C |
| 0xA00001ED | 6 | 3 | 0.2 | 0 | 13:2 48:1 | light (cat 6): Green Lantern costume 1 | 0x100005e0 in 0xa00001ef |
| 0xA00001EE | 5 | 2 | 1.4 | 0 | 13:1 48:1 | wallpaper (cat 5): Green Lantern costume 1 | 0x100005df in 0xa00001ef |
| 0xA00001EF | 7 | 15 | 4.4 | 0 | 10:1 13:5 16:1 17:1 19:1 1D:1 2D:1 2E:1 36:1 40:1 49:1 | own (cat 7): Green Lantern costume 1 | server (0x20AF / roster); self 0x1000035C |
| 0xA00001F0 | 5 | 2 | 1.4 | 0 | 13:1 48:1 | wallpaper (cat 5): Green Arrow | 0x100005df in 0xa00001f2 |
| 0xA00001F1 | 6 | 4 | 0.2 | 0 | 13:2 48:1 52:1 | light (cat 6): Green Arrow | 0x100005e0 in 0xa00001f2 |
| 0xA00001F2 | 7 | 18 | 3.6 | 0 | 10:4 13:5 16:1 17:1 19:1 1D:1 2D:1 2E:1 36:1 40:1 49:1 | own (cat 7): Green Arrow | server (0x20AF / roster); self 0x1000035C |
| 0xA00001F3 | 8 | 331 | 4.2 | 1 | 10:10 13:23 16:9 17:9 18:78 19:6 1A:78 1C:2 1D:28 1E:16 1F:1 2B:1 2D:6 2E:20 34:14 3A:1 3B:1 40:6 48:15 49:6 52:1 | shared (cat 8): Green Arrow | 0x10000730 in 0xa00001f2, 0x10000730 in 0xa0000262, 0x10000730 in 0xa0000343, +1 |
| 0xA00001F4 | 5 | 2 | 1.4 | 0 | 13:1 48:1 | wallpaper (cat 5): The Joker costume 3 | 0x100005df in 0xa00001f6 |
| 0xA00001F5 | 6 | 3 | 0.2 | 0 | 13:2 48:1 | light (cat 6): The Joker costume 3 | 0x100005e0 in 0xa00001f6 |
| 0xA00001F6 | 7 | 93 | 4.8 | 0 | 10:1 13:6 16:2 17:1 18:2 19:2 1A:70 1C:1 1D:2 1F:1 2D:1 2E:1 36:1 40:1 49:1 | own (cat 7): The Joker costume 3 | server (0x20AF / roster); self 0x1000035C |
| 0xA00001F7 | 5 | 2 | 1.4 | 0 | 13:1 48:1 | wallpaper (cat 5): Nightmare Superman | 0x100005df in 0xa00001f9 |
| 0xA00001F8 | 6 | 4 | 0.2 | 0 | 13:2 48:1 52:1 | light (cat 6): Nightmare Superman | 0x100005e0 in 0xa00001f9 |
| 0xA00001F9 | 7 | 7 | 0.0 | 0 | 16:1 17:1 18:1 1D:1 2E:1 40:1 49:1 | own (cat 7): Nightmare Superman | server (0x20AF / roster); self 0x1000035C |
| 0xA00001FA | 8 | 386 | 7.1 | 1 | 10:18 13:32 16:34 17:20 18:57 19:19 1A:85 1C:4 1D:22 1E:23 1F:1 2B:1 2D:8 2E:13 34:13 36:1 37:2 3B:2 40:6 48:18 49:6 52:1 | shared (cat 8): Nightmare Superman | 0x10000730 in 0xa00001f9, 0x10000730 in 0xa00002ea, 0x10000730 in 0xa000038d |
| 0xA00001FC | 6 | 3 | 0.2 | 0 | 13:2 48:1 | light (cat 6): Gaslight Joker costume 2 | 0x100005e0 in 0xa00001fe |
| 0xA00001FD | 5 | 2 | 0.7 | 0 | 13:1 48:1 | wallpaper (cat 5): Gaslight Joker costume 2 | 0x100005df in 0xa00001fe |
| 0xA00001FE | 7 | 27 | 4.4 | 0 | 10:5 13:6 16:3 17:2 19:4 1D:1 2D:1 2E:1 36:1 37:1 40:1 49:1 | own (cat 7): Gaslight Joker costume 2 | server (0x20AF / roster); self 0x1000035C |
| 0xA00001FF | 6 | 4 | 0.2 | 0 | 13:2 48:1 52:1 | light (cat 6): Blue Beetle | 0x100005e0 in 0xa0000201 |
| 0xA0000200 | 5 | 2 | 0.7 | 0 | 13:1 48:1 | wallpaper (cat 5): Blue Beetle | 0x100005df in 0xa0000201 |
| 0xA0000201 | 7 | 49 | 4.3 | 0 | 10:11 13:11 16:3 17:3 18:12 19:2 1D:2 2D:1 2E:1 36:1 40:1 49:1 | own (cat 7): Blue Beetle | server (0x20AF / roster); self 0x1000035C |
| 0xA0000202 | 8 | 327 | 4.9 | 1 | 10:5 13:28 16:15 17:15 18:47 19:5 1A:111 1C:1 1D:20 1E:17 1F:1 2B:1 2D:5 2E:10 34:14 3A:1 3B:1 40:6 48:17 49:6 52:1 | shared (cat 8): Blue Beetle | 0x10000730 in 0xa0000201, 0x10000730 in 0xa0000254, 0x10000730 in 0xa000034c |
| 0xA0000203 | 5 | 2 | 0.7 | 0 | 13:1 48:1 | wallpaper (cat 5): Arcane Green Lantern costume 1 | 0x100005df in 0xa0000205 |
| 0xA0000204 | 6 | 3 | 0.2 | 0 | 13:2 48:1 | light (cat 6): Arcane Green Lantern costume 1 | 0x100005e0 in 0xa0000205 |
| 0xA0000205 | 7 | 177 | 8.7 | 0 | 10:16 13:26 16:9 17:9 18:2 19:13 1A:68 1C:1 1D:3 1E:3 1F:1 2D:9 2E:9 36:1 37:3 40:2 49:2 | own (cat 7): Arcane Green Lantern costume 1 | server (0x20AF / roster); self 0x1000035C |
| 0xA0000206 | 6 | 3 | 0.2 | 0 | 13:2 48:1 | light (cat 6): Atomic Wonder Woman costume 1 | 0x100005e0 in 0xa0000208 |
| 0xA0000207 | 5 | 2 | 0.7 | 0 | 13:1 48:1 | wallpaper (cat 5): Atomic Wonder Woman costume 1 | 0x100005df in 0xa0000208 |
| 0xA0000208 | 7 | 43 | 3.5 | 0 | 10:5 13:14 16:7 17:3 19:5 1D:1 2D:1 2E:1 36:1 37:3 40:1 49:1 | own (cat 7): Atomic Wonder Woman costume 1 | server (0x20AF / roster); self 0x1000035C |
| 0xA000020C | 5 | 2 | 0.7 | 0 | 13:1 48:1 | wallpaper (cat 5): Sinestro | 0x100005df in 0xa000020f |
| 0xA000020D | 6 | 4 | 0.2 | 0 | 13:2 48:1 52:1 | light (cat 6): Sinestro | 0x100005e0 in 0xa000020f |
| 0xA000020E | 8 | 189 | 3.8 | 1 | 10:10 13:22 16:17 17:13 18:21 19:13 1A:7 1C:2 1D:15 1E:11 2B:1 2D:7 2E:8 34:13 37:1 3A:1 3B:1 40:5 48:15 49:5 52:1 | shared (cat 8): Sinestro | 0x10000730 in 0xa000020f, 0x10000730 in 0xa00002fe, 0x10000730 in 0xa00003b0, +1 |
| 0xA000020F | 7 | 99 | 3.4 | 0 | 10:2 13:5 16:1 17:1 18:5 19:3 1A:67 1C:1 1D:4 1F:1 2D:3 2E:3 36:1 40:1 49:1 | own (cat 7): Sinestro | server (0x20AF / roster); self 0x1000035C |
| 0xA0000210 | 5 | 2 | 0.7 | 0 | 13:1 48:1 | wallpaper (cat 5): Superman costume 1 | 0x100005df in 0xa0000212 |
| 0xA0000211 | 6 | 3 | 0.2 | 0 | 13:2 48:1 | light (cat 6): Superman costume 1 | 0x100005e0 in 0xa0000212 |
| 0xA0000212 | 7 | 98 | 4.8 | 0 | 10:2 13:6 16:2 17:1 18:3 19:3 1A:71 1C:1 1D:2 2D:1 2E:2 36:1 37:1 40:1 49:1 | own (cat 7): Superman costume 1 | server (0x20AF / roster); self 0x1000035C |
| 0xA0000213 | 6 | 3 | 0.2 | 0 | 13:2 48:1 | light (cat 6): Harley Quinn costume 1 | 0x100005e0 in 0xa0000215 |
| 0xA0000214 | 5 | 2 | 0.7 | 0 | 13:1 48:1 | wallpaper (cat 5): Harley Quinn costume 1 | 0x100005df in 0xa0000215 |
| 0xA0000215 | 7 | 50 | 4.6 | 0 | 10:12 13:4 16:3 17:3 18:4 19:9 1D:1 2D:4 2E:4 36:1 37:2 3A:1 40:1 49:1 | own (cat 7): Harley Quinn costume 1 | server (0x20AF / roster); self 0x1000035C |
| 0xA0000216 | 5 | 2 | 1.1 | 0 | 13:1 48:1 | wallpaper (cat 5): Catwoman costume 1 | 0x100005df in 0xa0000218 |
| 0xA0000217 | 6 | 3 | 0.1 | 0 | 13:2 48:1 | light (cat 6): Catwoman costume 1 | 0x100005e0 in 0xa0000218 |
| 0xA0000218 | 7 | 29 | 4.5 | 0 | 10:3 13:7 16:7 17:1 19:4 1D:1 2D:1 2E:1 36:1 37:1 40:1 49:1 | own (cat 7): Catwoman costume 1 | server (0x20AF / roster); self 0x1000035C |
| 0xA0000219 | 5 | 2 | 1.4 | 0 | 13:1 48:1 | wallpaper (cat 5): Atomic Green Lantern costume 1 | 0x100005df in 0xa000021b |
| 0xA000021A | 6 | 3 | 0.2 | 0 | 13:2 48:1 | light (cat 6): Atomic Green Lantern costume 1 | 0x100005e0 in 0xa000021b |
| 0xA000021B | 7 | 25 | 2.6 | 0 | 10:3 13:9 16:2 17:2 18:1 19:2 1D:1 2D:1 2E:1 36:1 40:1 49:1 | own (cat 7): Atomic Green Lantern costume 1 | server (0x20AF / roster); self 0x1000035C |
| 0xA000021C | 5 | 2 | 0.7 | 0 | 13:1 48:1 | wallpaper (cat 5): Harley Quinn costume 2 | 0x100005df in 0xa000021e |
| 0xA000021D | 6 | 3 | 0.2 | 0 | 13:2 48:1 | light (cat 6): Harley Quinn costume 2 | 0x100005e0 in 0xa000021e |
| 0xA000021E | 7 | 56 | 5.0 | 0 | 10:14 13:5 16:4 17:3 18:4 19:10 1D:1 2D:4 2E:4 36:1 37:3 3A:1 40:1 49:1 | own (cat 7): Harley Quinn costume 2 | server (0x20AF / roster); self 0x1000035C |
| 0xA000021F | 5 | 2 | 0.7 | 0 | 13:1 48:1 | wallpaper (cat 5): Supergirl | 0x100005df in 0xa0000222 |
| 0xA0000220 | 6 | 4 | 0.2 | 0 | 13:2 48:1 52:1 | light (cat 6): Supergirl | 0x100005e0 in 0xa0000222 |
| 0xA0000221 | 8 | 158 | 3.0 | 1 | 10:2 13:14 16:2 17:2 18:18 1A:67 1C:1 1D:9 1E:11 1F:1 2B:1 2E:1 34:9 3A:1 3B:2 40:2 48:12 49:2 52:1 | shared (cat 8): Supergirl | 0x10000730 in 0xa0000222, 0x10000730 in 0xa00002d5, 0x10000730 in 0xa00003bd |
| 0xA0000222 | 7 | 28 | 3.6 | 0 | 10:3 13:6 16:2 17:2 18:3 19:3 1D:2 2D:1 2E:1 36:1 37:2 40:1 49:1 | own (cat 7): Supergirl | server (0x20AF / roster); self 0x1000035C |
| 0xA0000223 | 6 | 3 | 0.2 | 0 | 13:2 48:1 | light (cat 6): Mecha Wonder Woman costume 1 | 0x100005e0 in 0xa0000225 |
| 0xA0000224 | 5 | 2 | 0.7 | 0 | 13:1 48:1 | wallpaper (cat 5): Mecha Wonder Woman costume 1 | 0x100005df in 0xa0000225 |
| 0xA0000225 | 7 | 28 | 4.9 | 0 | 10:2 13:11 16:4 17:2 19:2 1D:1 2D:1 2E:1 36:1 3A:1 40:1 49:1 | own (cat 7): Mecha Wonder Woman costume 1 | server (0x20AF / roster); self 0x1000035C |
| 0xA0000229 | 5 | 2 | 0.7 | 0 | 13:1 48:1 | wallpaper (cat 5): Cyborg costume 1 | 0x100005df in 0xa000022b |
| 0xA000022A | 6 | 3 | 0.2 | 0 | 13:2 48:1 | light (cat 6): Cyborg costume 1 | 0x100005e0 in 0xa000022b |
| 0xA000022B | 7 | 33 | 1.9 | 0 | 10:3 13:11 16:2 17:2 19:3 1D:3 2D:3 2E:3 36:1 40:1 49:1 | own (cat 7): Cyborg costume 1 | server (0x20AF / roster); self 0x1000035C |
| 0xA000022C | 5 | 2 | 0.7 | 0 | 13:1 48:1 | wallpaper (cat 5): Nightmare Robin | 0x100005df in 0xa000022f |
| 0xA000022D | 6 | 4 | 0.2 | 0 | 13:2 48:1 52:1 | light (cat 6): Nightmare Robin | 0x100005e0 in 0xa000022f |
| 0xA000022E | 8 | 219 | 3.6 | 1 | 10:2 13:15 14:1 15:14 16:9 17:9 18:28 19:3 1A:75 1C:1 1D:11 1E:10 1F:1 2B:1 2D:2 2E:4 34:9 3A:1 3B:2 40:3 48:14 49:3 52:1 | shared (cat 8): Nightmare Robin | 0x10000730 in 0xa000022f, 0x10000730 in 0xa00002ad |
| 0xA000022F | 7 | 37 | 5.3 | 0 | 10:4 13:10 16:6 17:6 19:2 1D:1 2D:1 2E:1 36:1 37:1 40:2 49:2 | own (cat 7): Nightmare Robin | server (0x20AF / roster); self 0x1000035C |
| 0xA0000230 | 5 | 2 | 0.7 | 0 | 13:1 48:1 | wallpaper (cat 5): Doomsday costume 2 | 0x100005df in 0xa0000232 |
| 0xA0000231 | 6 | 3 | 0.2 | 0 | 13:2 48:1 | light (cat 6): Doomsday costume 2 | 0x100005e0 in 0xa0000232 |
| 0xA0000232 | 7 | 37 | 3.5 | 0 | 10:4 13:9 16:4 17:3 18:5 19:3 1D:2 2D:1 2E:1 36:1 37:2 40:1 49:1 | own (cat 7): Doomsday costume 2 | server (0x20AF / roster); self 0x1000035C |
| 0xA0000233 | 5 | 2 | 0.7 | 0 | 13:1 48:1 | wallpaper (cat 5): Atomic Poison Ivy costume 1 | 0x100005df in 0xa0000235 |
| 0xA0000234 | 6 | 3 | 0.2 | 0 | 13:2 48:1 | light (cat 6): Atomic Poison Ivy costume 1 | 0x100005e0 in 0xa0000235 |
| 0xA0000235 | 7 | 39 | 4.5 | 0 | 10:6 13:10 16:6 17:4 18:1 19:4 1D:1 2D:1 2E:1 36:1 37:2 40:1 49:1 | own (cat 7): Atomic Poison Ivy costume 1 | server (0x20AF / roster); self 0x1000035C |
| 0xA0000236 | 5 | 2 | 0.7 | 0 | 13:1 48:1 | wallpaper (cat 5): Superman costume 2 | 0x100005df in 0xa0000238 |
| 0xA0000237 | 6 | 3 | 0.2 | 0 | 13:2 48:1 | light (cat 6): Superman costume 2 | 0x100005e0 in 0xa0000238 |
| 0xA0000238 | 7 | 27 | 5.9 | 0 | 10:2 13:7 16:2 17:1 18:3 19:3 1D:2 2D:1 2E:2 36:1 37:1 40:1 49:1 | own (cat 7): Superman costume 2 | server (0x20AF / roster); self 0x1000035C |
| 0xA0000239 | 5 | 2 | 0.7 | 0 | 13:1 48:1 | wallpaper (cat 5): Star Sapphire costume 1 | 0x100005df in 0xa000023b |
| 0xA000023A | 6 | 3 | 0.2 | 0 | 13:2 48:1 | light (cat 6): Star Sapphire costume 1 | 0x100005e0 in 0xa000023b |
| 0xA000023B | 7 | 86 | 6.4 | 0 | 10:2 13:7 16:1 17:1 19:2 1A:61 1C:1 1D:1 1F:1 2D:1 2E:1 34:1 36:1 37:1 40:2 49:2 | own (cat 7): Star Sapphire costume 1 | server (0x20AF / roster); self 0x1000035C |
| 0xA000023C | 5 | 2 | 0.7 | 0 | 13:1 48:1 | wallpaper (cat 5): Atrocitus | 0x100005df in 0xa000023f |
| 0xA000023D | 6 | 4 | 0.2 | 0 | 13:2 48:1 52:1 | light (cat 6): Atrocitus | 0x100005e0 in 0xa000023f |
| 0xA000023E | 8 | 207 | 3.3 | 1 | 10:1 13:20 16:11 17:11 18:35 19:1 1A:64 1C:1 1D:10 1E:13 1F:1 2B:1 2D:1 2E:2 34:10 3A:1 3B:2 40:3 48:14 49:3 52:2 | shared (cat 8): Atrocitus | 0x10000730 in 0xa000023f, 0x10000730 in 0xa000026a, 0x10000730 in 0xa00003b3 |
| 0xA000023F | 7 | 19 | 2.1 | 0 | 10:1 13:6 16:2 17:1 18:1 19:2 1D:1 2D:1 2E:1 36:1 40:1 49:1 | own (cat 7): Atrocitus | server (0x20AF / roster); self 0x1000035C |
| 0xA0000242 | 5 | 2 | 0.7 | 0 | 13:1 48:1 | wallpaper (cat 5): Robin costume 1 | 0x100005df in 0xa0000244 |
| 0xA0000243 | 6 | 3 | 0.2 | 0 | 13:2 48:1 | light (cat 6): Robin costume 1 | 0x100005e0 in 0xa0000244 |
| 0xA0000244 | 7 | 37 | 5.3 | 0 | 10:5 13:7 16:3 17:3 18:2 19:4 1D:1 2D:1 2E:1 36:1 37:3 40:3 49:3 | own (cat 7): Robin costume 1 | server (0x20AF / roster); self 0x1000035C |
| 0xA0000245 | 6 | 3 | 0.2 | 0 | 13:2 48:1 | light (cat 6): Wonder Woman costume 2 | 0x100005e0 in 0xa0000247 |
| 0xA0000246 | 5 | 2 | 0.7 | 0 | 13:1 48:1 | wallpaper (cat 5): Wonder Woman costume 2 | 0x100005df in 0xa0000247 |
| 0xA0000247 | 7 | 45 | 6.3 | 0 | 10:12 13:10 16:4 17:3 19:6 1D:1 2D:1 2E:1 36:1 37:4 40:1 49:1 | own (cat 7): Wonder Woman costume 2 | server (0x20AF / roster); self 0x1000035C |
| 0xA0000248 | 5 | 2 | 0.7 | 0 | 13:1 48:1 | wallpaper (cat 5): Atomic Joker | 0x100005df in 0xa000024b |
| 0xA0000249 | 6 | 4 | 0.2 | 0 | 13:2 48:1 52:1 | light (cat 6): Atomic Joker | 0x100005e0 in 0xa000024b |
| 0xA000024A | 8 | 359 | 4.4 | 1 | 10:20 13:28 14:1 15:14 16:13 17:13 18:67 19:13 1A:75 1C:5 1D:23 1E:12 1F:2 2B:1 2D:10 2E:13 34:14 3B:4 40:8 48:14 49:8 52:1 | shared (cat 8): Atomic Joker | 0x10000730 in 0xa000024b, 0x10000730 in 0xa000027c, 0x10000730 in 0xa000037c |
| 0xA000024B | 7 | 21 | 3.3 | 0 | 10:4 13:6 16:1 17:1 19:1 1D:1 2D:1 2E:1 36:1 40:2 49:2 | own (cat 7): Atomic Joker | server (0x20AF / roster); self 0x1000035C |
| 0xA000024C | 13 | 3711 | 114.6 | 0 | 08:2 10:683 11:133 13:506 14:20 15:513 16:374 17:217 18:59 19:331 1A:9 1C:4 1D:73 2D:323 2E:373 34:3 3E:2 40:14 48:5 49:14 50:51 52:2 | zone of Tutorial 1 | map list 0xa0c112ca |
| 0xA000024F | 5 | 2 | 0.7 | 0 | 13:1 48:1 | wallpaper (cat 5): Aquaman costume 1 | 0x100005df in 0xa0000251 |
| 0xA0000250 | 6 | 3 | 0.2 | 0 | 13:2 48:1 | light (cat 6): Aquaman costume 1 | 0x100005e0 in 0xa0000251 |
| 0xA0000251 | 7 | 35 | 3.8 | 0 | 10:5 13:6 16:3 17:2 18:5 19:4 1D:2 2D:1 2E:1 36:1 37:3 40:1 49:1 | own (cat 7): Aquaman costume 1 | server (0x20AF / roster); self 0x1000035C |
| 0xA0000252 | 5 | 2 | 1.4 | 0 | 13:1 48:1 | wallpaper (cat 5): Blue Beetle costume 1 | 0x100005df in 0xa0000254 |
| 0xA0000253 | 6 | 3 | 0.2 | 0 | 13:2 48:1 | light (cat 6): Blue Beetle costume 1 | 0x100005e0 in 0xa0000254 |
| 0xA0000254 | 7 | 49 | 3.9 | 0 | 10:11 13:11 16:3 17:3 18:12 19:2 1D:2 2D:1 2E:1 36:1 40:1 49:1 | own (cat 7): Blue Beetle costume 1 | server (0x20AF / roster); self 0x1000035C |
| 0xA0000256 | 15 | 812 | 18.1 | 5 | 10:37 11:14 13:90 14:5 15:149 16:60 17:40 18:107 19:43 1A:28 1C:6 1D:50 1E:23 1F:1 2B:5 2D:37 2E:51 30:1 34:11 35:5 3B:3 40:14 48:11 49:14 52:7 | layout of Tutorial 1 | map list 0xa0c112ca |
| 0xA0000257 | 14 | 324 | 9.4 | 1 | 10:11 13:39 16:17 17:12 18:47 19:13 1A:65 1C:5 1D:24 1E:17 1F:4 2B:1 2D:9 2E:15 34:5 36:5 3B:5 40:10 48:8 49:10 52:2 | variants (units) of Tutorial 1 | map list 0xa0c112ca |
| 0xA000025A | 5 | 2 | 1.4 | 0 | 13:1 48:1 | wallpaper (cat 5): Mecha Superman costume 1 | 0x100005df in 0xa000025c |
| 0xA000025B | 6 | 3 | 0.2 | 0 | 13:2 48:1 | light (cat 6): Mecha Superman costume 1 | 0x100005e0 in 0xa000025c |
| 0xA000025C | 7 | 41 | 6.9 | 0 | 10:4 13:11 16:3 17:3 18:8 19:2 1D:3 2D:1 2E:2 36:1 37:1 40:1 49:1 | own (cat 7): Mecha Superman costume 1 | server (0x20AF / roster); self 0x1000035C |
| 0xA000025D | 5 | 2 | 1.4 | 0 | 13:1 48:1 | wallpaper (cat 5): The Joker costume 4 | 0x100005df in 0xa000025f |
| 0xA000025E | 6 | 3 | 0.2 | 0 | 13:2 48:1 | light (cat 6): The Joker costume 4 | 0x100005e0 in 0xa000025f |
| 0xA000025F | 7 | 96 | 7.0 | 0 | 10:1 13:9 16:2 17:2 18:2 19:1 1A:70 1C:1 1D:2 1F:1 2D:1 2E:1 36:1 40:1 49:1 | own (cat 7): The Joker costume 4 | server (0x20AF / roster); self 0x1000035C |
| 0xA0000260 | 5 | 2 | 1.4 | 0 | 13:1 48:1 | wallpaper (cat 5): Green Arrow costume 1 | 0x100005df in 0xa0000262 |
| 0xA0000261 | 6 | 3 | 0.2 | 0 | 13:2 48:1 | light (cat 6): Green Arrow costume 1 | 0x100005e0 in 0xa0000262 |
| 0xA0000262 | 7 | 29 | 5.5 | 0 | 10:6 13:10 16:2 17:2 19:2 1D:1 2D:1 2E:1 36:1 37:1 40:1 49:1 | own (cat 7): Green Arrow costume 1 | server (0x20AF / roster); self 0x1000035C |
| 0xA0000268 | 5 | 2 | 1.4 | 0 | 13:1 48:1 | wallpaper (cat 5): Atrocitus costume 1 | 0x100005df in 0xa000026a |
| 0xA0000269 | 6 | 3 | 0.2 | 0 | 13:2 48:1 | light (cat 6): Atrocitus costume 1 | 0x100005e0 in 0xa000026a |
| 0xA000026A | 7 | 25 | 4.2 | 0 | 10:3 13:6 16:2 17:1 18:1 19:4 1D:1 2D:1 2E:1 36:1 37:2 40:1 49:1 | own (cat 7): Atrocitus costume 1 | server (0x20AF / roster); self 0x1000035C |
| 0xA000026B | 5 | 2 | 1.4 | 0 | 13:1 48:1 | wallpaper (cat 5): Starro | 0x100005df in 0xa000026d |
| 0xA000026C | 6 | 4 | 0.2 | 0 | 13:2 48:1 52:1 | light (cat 6): Starro | 0x100005e0 in 0xa000026d |
| 0xA000026D | 7 | 21 | 5.3 | 0 | 10:1 13:6 16:2 17:2 18:1 19:1 1D:2 2D:1 2E:2 36:1 40:1 49:1 | own (cat 7): Starro | server (0x20AF / roster); self 0x1000035C |
| 0xA000026E | 8 | 328 | 5.6 | 1 | 10:6 13:24 14:1 15:62 16:12 17:11 18:32 19:7 1A:73 1C:3 1D:15 1E:15 1F:2 2B:1 2D:6 2E:10 34:14 3A:1 3B:2 40:6 48:18 49:6 52:1 | shared (cat 8): Starro | 0x10000730 in 0xa000026d, 0x10000730 in 0xa00002c7, 0x10000730 in 0xa000035d |
| 0xA0000270 | 6 | 3 | 0.2 | 0 | 13:2 48:1 | light (cat 6): Poison Ivy costume 2 | 0x100005e0 in 0xa0000272 |
| 0xA0000271 | 5 | 2 | 1.4 | 0 | 13:1 48:1 | wallpaper (cat 5): Poison Ivy costume 2 | 0x100005df in 0xa0000272 |
| 0xA0000272 | 7 | 25 | 4.5 | 0 | 10:4 13:5 16:1 17:1 18:1 19:3 1D:2 2D:1 2E:2 36:1 37:2 40:1 49:1 | own (cat 7): Poison Ivy costume 2 | server (0x20AF / roster); self 0x1000035C |
| 0xA0000273 | 6 | 3 | 0.2 | 0 | 13:2 48:1 | light (cat 6): Gaslight Catwoman costume 2 | 0x100005e0 in 0xa0000275 |
| 0xA0000274 | 5 | 2 | 1.4 | 0 | 13:1 48:1 | wallpaper (cat 5): Gaslight Catwoman costume 2 | 0x100005df in 0xa0000275 |
| 0xA0000275 | 7 | 26 | 2.0 | 0 | 10:4 13:5 16:2 17:2 19:4 1D:1 2D:1 2E:1 36:1 37:3 40:1 49:1 | own (cat 7): Gaslight Catwoman costume 2 | server (0x20AF / roster); self 0x1000035C |
| 0xA0000276 | 6 | 3 | 0.2 | 0 | 13:2 48:1 | light (cat 6): Poison Ivy costume 3 | 0x100005e0 in 0xa0000278 |
| 0xA0000277 | 5 | 2 | 1.4 | 0 | 13:1 48:1 | wallpaper (cat 5): Poison Ivy costume 3 | 0x100005df in 0xa0000278 |
| 0xA0000278 | 7 | 29 | 3.8 | 0 | 10:3 13:9 16:3 17:2 18:1 19:3 1D:2 2D:1 2E:2 36:1 40:1 49:1 | own (cat 7): Poison Ivy costume 3 | server (0x20AF / roster); self 0x1000035C |
| 0xA0000279 | 5 | 2 | 1.4 | 0 | 13:1 48:1 | wallpaper (cat 5): Superman costume 3 | 0x100005df in 0xa000027b |
| 0xA000027A | 6 | 3 | 0.2 | 0 | 13:2 48:1 | light (cat 6): Superman costume 3 | 0x100005e0 in 0xa000027b |
| 0xA000027B | 7 | 95 | 4.0 | 0 | 10:1 13:5 16:1 17:1 18:5 19:2 1A:71 1C:1 1D:2 2D:1 2E:2 36:1 40:1 49:1 | own (cat 7): Superman costume 3 | server (0x20AF / roster); self 0x1000035C |
| 0xA000027C | 7 | 53 | 2.1 | 0 | 10:11 13:16 16:3 17:3 19:4 1D:3 2D:3 2E:3 36:1 40:3 49:3 | own (cat 7): Atomic Joker costume 1 | server (0x20AF / roster); self 0x1000035C |
| 0xA000027D | 6 | 3 | 0.2 | 0 | 13:2 48:1 | light (cat 6): Atomic Joker costume 1 | 0x100005e0 in 0xa000027c |
| 0xA000027E | 5 | 2 | 1.4 | 0 | 13:1 48:1 | wallpaper (cat 5): Atomic Joker costume 1 | 0x100005df in 0xa000027c |
| 0xA000027F | 5 | 2 | 1.4 | 0 | 13:1 48:1 | wallpaper (cat 5): Arcane Supergirl | 0x100005df in 0xa0000282 |
| 0xA0000280 | 6 | 4 | 0.2 | 0 | 13:2 48:1 52:1 | light (cat 6): Arcane Supergirl | 0x100005e0 in 0xa0000282 |
| 0xA0000281 | 8 | 271 | 7.5 | 1 | 10:14 13:20 16:17 17:14 18:42 19:7 1A:66 1C:4 1D:17 1E:12 1F:1 2B:1 2D:5 2E:9 34:16 3B:1 40:6 48:12 49:6 52:1 | shared (cat 8): Arcane Supergirl | 0x10000730 in 0xa0000282, 0x10000730 in 0xa00002ed |
| 0xA0000282 | 7 | 42 | 5.2 | 0 | 10:5 13:8 16:3 17:3 18:7 19:4 1D:2 2D:1 2E:1 36:1 37:3 40:2 49:2 | own (cat 7): Arcane Supergirl | server (0x20AF / roster); self 0x1000035C |
| 0xA0000283 | 4 | 13 | 0.5 | 1 | 13:8 2B:1 48:4 | skills UI (cat 4): Atrocitus | 0x10000b0d in 0xa000023f, 0x10000b0d in 0xa000026a, 0x10000b0d in 0xa00003b3 |
| 0xA0000284 | 4 | 14 | 0.6 | 1 | 13:9 2B:1 48:4 | skills UI (cat 4): Atomic Wonder Woman | 0x10000b0d in 0xa0000123, 0x10000b0d in 0xa0000208, 0x10000b0d in 0xa00002f9 |
| 0xA0000285 | 4 | 14 | 0.5 | 1 | 13:9 2B:1 48:4 | skills UI (cat 4): Atomic Poison Ivy | 0x10000b0d in 0xa000018e, 0x10000b0d in 0xa0000235, 0x10000b0d in 0xa0000365 |
| 0xA0000287 | 4 | 13 | 0.4 | 1 | 13:8 2B:1 48:4 | skills UI (cat 4): Atomic Green Lantern | 0x10000b0d in 0xa0000151, 0x10000b0d in 0xa000021b, 0x10000b0d in 0xa0000312 |
| 0xA0000288 | 4 | 14 | 0.6 | 1 | 13:9 2B:1 48:4 | skills UI (cat 4): Arcane Green Lantern | 0x10000b0d in 0xa0000144, 0x10000b0d in 0xa0000205, 0x10000b0d in 0xa00002f0, +1 |
| 0xA0000289 | 4 | 14 | 0.5 | 1 | 13:9 2B:1 48:4 | skills UI (cat 4): Aquaman | 0x10000b0d in 0xa0000192, 0x10000b0d in 0xa0000251, 0x10000b0d in 0xa00002c1 |
| 0xA000028A | 4 | 13 | 0.5 | 1 | 13:8 2B:1 48:4 | skills UI (cat 4): Batman | 0x10000b0d in 0xa00000dd, 0x10000b0d in 0xa0000180, 0x10000b0d in 0xa00001e5, +1 |
| 0xA000028B | 4 | 13 | 0.5 | 1 | 13:8 2B:1 48:4 | skills UI (cat 4): Nightmare Batman | 0x10000b0d in 0xa0000073, 0x10000b0d in 0xa0000148, 0x10000b0d in 0xa00001e2, +1 |
| 0xA000028C | 4 | 13 | 0.5 | 1 | 13:8 2B:1 48:4 | skills UI (cat 4): Superman | 0x10000b0d in 0xa0000075, 0x10000b0d in 0xa0000212, 0x10000b0d in 0xa0000238, +3 |
| 0xA000028D | 4 | 14 | 0.6 | 1 | 13:9 2B:1 48:4 | skills UI (cat 4): Gaslight Batman | 0x10000b0d in 0xa0000076, 0x10000b0d in 0xa000010c, 0x10000b0d in 0xa0000183, +1 |
| 0xA000028E | 4 | 13 | 0.5 | 1 | 13:8 2B:1 48:4 | skills UI (cat 4): Poison Ivy | 0x10000b0d in 0xa000009b, 0x10000b0d in 0xa00000d9, 0x10000b0d in 0xa0000272, +1 |
| 0xA000028F | 4 | 14 | 0.6 | 1 | 13:9 2B:1 48:4 | skills UI (cat 4): Doomsday | 0x10000b0d in 0xa00000a2, 0x10000b0d in 0xa0000100, 0x10000b0d in 0xa0000232 |
| 0xA0000290 | 4 | 13 | 0.5 | 1 | 13:8 2B:1 48:4 | skills UI (cat 4): Zatanna | 0x10000b0d in 0xa00000a3, 0x10000b0d in 0xa00000d7, 0x10000b0d in 0xa00002aa |
| 0xA0000291 | 4 | 13 | 0.5 | 1 | 13:8 2B:1 48:4 | skills UI (cat 4): The Joker | 0x10000b0d in 0xa00000b4, 0x10000b0d in 0xa00000f3, 0x10000b0d in 0xa00001df, +2 |
| 0xA0000292 | 4 | 13 | 0.5 | 1 | 13:8 2B:1 48:4 | skills UI (cat 4): Wonder Woman | 0x10000b0d in 0xa00000c9, 0x10000b0d in 0xa0000154, 0x10000b0d in 0xa0000247 |
| 0xA0000293 | 4 | 14 | 0.6 | 1 | 13:9 2B:1 48:4 | skills UI (cat 4): Gaslight Catwoman | 0x10000b0d in 0xa00000cc, 0x10000b0d in 0xa00000fa, 0x10000b0d in 0xa0000275 |
| 0xA0000294 | 4 | 13 | 0.5 | 1 | 13:8 2B:1 48:4 | skills UI (cat 4): Green Lantern | 0x10000b0d in 0xa00000e0, 0x10000b0d in 0xa00001ef, 0x10000b0d in 0xa0000307 |
| 0xA0000295 | 4 | 13 | 0.5 | 1 | 13:8 2B:1 48:4 | skills UI (cat 4): Shazam | 0x10000b0d in 0xa00000e5, 0x10000b0d in 0xa00001d8, 0x10000b0d in 0xa0000322 |
| 0xA0000296 | 4 | 13 | 0.5 | 1 | 13:8 2B:1 48:4 | skills UI (cat 4): Gaslight Joker | 0x10000b0d in 0xa00000eb, 0x10000b0d in 0xa00001dc, 0x10000b0d in 0xa00001fe, +1 |
| 0xA0000297 | 4 | 14 | 0.6 | 1 | 13:9 2B:1 48:4 | skills UI (cat 4): Flash | 0x10000b0d in 0xa00000f7, 0x10000b0d in 0xa00001ec, 0x10000b0d in 0xa000034f |
| 0xA0000298 | 4 | 14 | 0.6 | 1 | 13:9 2B:1 48:4 | skills UI (cat 4): Cyborg | 0x10000b0d in 0xa000010a, 0x10000b0d in 0xa000022b |
| 0xA0000299 | 4 | 13 | 0.2 | 1 | 13:8 2B:1 48:4 | skills UI (cat 4): Catwoman | 0x10000b0d in 0xa000012d, 0x10000b0d in 0xa0000218, 0x10000b0d in 0xa00002ca |
| 0xA000029A | 4 | 14 | 0.6 | 1 | 13:9 2B:1 48:4 | skills UI (cat 4): Mecha Wonder Woman | 0x10000b0d in 0xa0000156, 0x10000b0d in 0xa0000225, 0x10000b0d in 0xa0000368 |
| 0xA000029B | 4 | 14 | 0.6 | 1 | 13:9 2B:1 48:4 | skills UI (cat 4): Robin | 0x10000b0d in 0xa0000175, 0x10000b0d in 0xa0000244, 0x10000b0d in 0xa00002c4 |
| 0xA000029C | 4 | 14 | 0.6 | 1 | 13:9 2B:1 48:4 | skills UI (cat 4): Harley Quinn | 0x10000b0d in 0xa0000187, 0x10000b0d in 0xa0000215, 0x10000b0d in 0xa000021e, +1 |
| 0xA000029D | 4 | 13 | 0.5 | 1 | 13:8 2B:1 48:4 | skills UI (cat 4): Star Sapphire | 0x10000b0d in 0xa00001d1, 0x10000b0d in 0xa000023b, 0x10000b0d in 0xa000032b |
| 0xA000029E | 4 | 13 | 0.5 | 1 | 13:8 2B:1 48:4 | skills UI (cat 4): Mecha Superman | 0x10000b0d in 0xa00001e9, 0x10000b0d in 0xa000025c, 0x10000b0d in 0xa00003ac |
| 0xA000029F | 4 | 13 | 0.5 | 1 | 13:8 2B:1 48:4 | skills UI (cat 4): Green Arrow | 0x10000b0d in 0xa00001f2, 0x10000b0d in 0xa0000262, 0x10000b0d in 0xa0000343, +1 |
| 0xA00002A0 | 4 | 14 | 0.6 | 1 | 13:9 2B:1 48:4 | skills UI (cat 4): Nightmare Superman | 0x10000b0d in 0xa00001f9, 0x10000b0d in 0xa00002ea, 0x10000b0d in 0xa000038d |
| 0xA00002A1 | 4 | 14 | 0.5 | 1 | 13:9 2B:1 48:4 | skills UI (cat 4): Blue Beetle | 0x10000b0d in 0xa0000201, 0x10000b0d in 0xa0000254, 0x10000b0d in 0xa000034c |
| 0xA00002A2 | 4 | 14 | 0.6 | 1 | 13:9 2B:1 48:4 | skills UI (cat 4): Sinestro | 0x10000b0d in 0xa000020f, 0x10000b0d in 0xa00002fe, 0x10000b0d in 0xa00003b0, +1 |
| 0xA00002A3 | 4 | 13 | 0.5 | 1 | 13:8 2B:1 48:4 | skills UI (cat 4): Supergirl | 0x10000b0d in 0xa0000222, 0x10000b0d in 0xa00002d5, 0x10000b0d in 0xa00003bd |
| 0xA00002A4 | 4 | 14 | 0.6 | 1 | 13:9 2B:1 48:4 | skills UI (cat 4): Nightmare Robin | 0x10000b0d in 0xa000022f, 0x10000b0d in 0xa00002ad |
| 0xA00002A5 | 4 | 13 | 0.5 | 1 | 13:8 2B:1 48:4 | skills UI (cat 4): Atomic Joker | 0x10000b0d in 0xa000024b, 0x10000b0d in 0xa000027c, 0x10000b0d in 0xa000037c |
| 0xA00002A6 | 4 | 13 | 0.5 | 1 | 13:8 2B:1 48:4 | skills UI (cat 4): Starro | 0x10000b0d in 0xa000026d, 0x10000b0d in 0xa00002c7, 0x10000b0d in 0xa000035d |
| 0xA00002A8 | 5 | 2 | 1.4 | 0 | 13:1 48:1 | wallpaper (cat 5): Zatanna costume 2 | 0x100005df in 0xa00002aa |
| 0xA00002A9 | 6 | 3 | 0.2 | 0 | 13:2 48:1 | light (cat 6): Zatanna costume 2 | 0x100005e0 in 0xa00002aa |
| 0xA00002AA | 7 | 35 | 3.9 | 0 | 10:6 13:4 16:3 17:2 18:3 19:5 1D:3 2D:1 2E:2 36:1 37:3 40:1 49:1 | own (cat 7): Zatanna costume 2 | server (0x20AF / roster); self 0x1000035C |
| 0xA00002AB | 5 | 2 | 1.4 | 0 | 13:1 48:1 | wallpaper (cat 5): Nightmare Robin costume 1 | 0x100005df in 0xa00002ad |
| 0xA00002AC | 6 | 3 | 0.2 | 0 | 13:2 48:1 | light (cat 6): Nightmare Robin costume 1 | 0x100005e0 in 0xa00002ad |
| 0xA00002AD | 7 | 30 | 2.5 | 0 | 10:4 13:9 16:3 17:3 19:2 1D:1 2D:1 2E:1 36:1 37:1 40:2 49:2 | own (cat 7): Nightmare Robin costume 1 | server (0x20AF / roster); self 0x1000035C |
| 0xA00002AE | 5 | 2 | 1.4 | 0 | 13:1 48:1 | wallpaper (cat 5): Stargirl | 0x100005df in 0xa00002b2 |
| 0xA00002AF | 6 | 4 | 0.2 | 0 | 13:2 48:1 52:1 | light (cat 6): Stargirl | 0x100005e0 in 0xa00002b2 |
| 0xA00002B0 | 4 | 13 | 0.4 | 1 | 13:8 2B:1 48:4 | skills UI (cat 4): Stargirl | 0x10000b0d in 0xa00002b2, 0x10000b0d in 0xa00002be, 0x10000b0d in 0xa0000371, +1 |
| 0xA00002B1 | 8 | 270 | 5.2 | 1 | 10:10 13:20 16:10 17:10 18:50 19:6 1A:65 1C:1 1D:16 1E:17 1F:1 2B:1 2D:6 2E:9 34:13 3A:1 3B:1 40:7 48:18 49:7 52:1 | shared (cat 8): Stargirl | 0x10000730 in 0xa00002b2, 0x10000730 in 0xa00002be, 0x10000730 in 0xa0000371, +1 |
| 0xA00002B2 | 7 | 31 | 2.2 | 0 | 10:3 13:6 16:2 17:2 18:4 19:3 1D:3 2D:2 2E:2 36:1 37:1 40:1 49:1 | own (cat 7): Stargirl | server (0x20AF / roster); self 0x1000035C |
| 0xA00002B3 | 5 | 2 | 1.4 | 0 | 13:1 48:1 | wallpaper (cat 5): Hawkgirl | 0x100005df in 0xa00002b5 |
| 0xA00002B4 | 8 | 214 | 4.3 | 1 | 10:5 13:21 16:11 17:11 18:19 19:4 1A:74 1C:2 1D:11 1E:8 1F:1 2B:1 2D:4 2E:4 34:11 3A:1 3B:2 40:3 48:17 49:3 52:1 | shared (cat 8): Hawkgirl | 0x10000730 in 0xa00002b5, 0x10000730 in 0xa00002da, 0x10000730 in 0xa00003c0 |
| 0xA00002B5 | 7 | 34 | 2.1 | 0 | 10:3 13:7 16:5 17:3 18:6 19:3 1D:2 2D:1 2E:1 36:1 40:1 49:1 | own (cat 7): Hawkgirl | server (0x20AF / roster); self 0x1000035C |
| 0xA00002B6 | 6 | 4 | 0.2 | 0 | 13:2 48:1 52:1 | light (cat 6): Hawkgirl | 0x100005e0 in 0xa00002b5 |
| 0xA00002B7 | 4 | 14 | 0.5 | 1 | 13:9 2B:1 48:4 | skills UI (cat 4): Hawkgirl | 0x10000b0d in 0xa00002b5, 0x10000b0d in 0xa00002da, 0x10000b0d in 0xa00003c0 |
| 0xA00002B8 | 4 | 13 | 0.4 | 1 | 13:8 2B:1 48:4 | skills UI (cat 4): Arcane Supergirl | 0x10000b0d in 0xa0000282, 0x10000b0d in 0xa00002ed |
| 0xA00002B9 | 5 | 2 | 1.4 | 0 | 13:1 48:1 | wallpaper (cat 5): Superman costume 4 | 0x100005df in 0xa00002bb |
| 0xA00002BA | 6 | 3 | 0.2 | 0 | 13:2 48:1 | light (cat 6): Superman costume 4 | 0x100005e0 in 0xa00002bb |
| 0xA00002BB | 7 | 102 | 5.6 | 0 | 10:2 13:8 16:3 17:2 18:3 19:3 1A:71 1C:1 1D:2 2D:1 2E:2 36:1 37:1 40:1 49:1 | own (cat 7): Superman costume 4 | server (0x20AF / roster); self 0x1000035C |
| 0xA00002BC | 5 | 2 | 1.4 | 0 | 13:1 48:1 | wallpaper (cat 5): Stargirl costume 1 | 0x100005df in 0xa00002be |
| 0xA00002BD | 6 | 3 | 0.2 | 0 | 13:2 48:1 | light (cat 6): Stargirl costume 1 | 0x100005e0 in 0xa00002be |
| 0xA00002BE | 7 | 38 | 2.9 | 0 | 10:6 13:6 16:3 17:3 18:4 19:4 1D:3 2D:2 2E:2 36:1 37:2 40:1 49:1 | own (cat 7): Stargirl costume 1 | server (0x20AF / roster); self 0x1000035C |
| 0xA00002BF | 5 | 2 | 1.4 | 0 | 13:1 48:1 | wallpaper (cat 5): Aquaman costume 2 | 0x100005df in 0xa00002c1 |
| 0xA00002C0 | 6 | 3 | 0.2 | 0 | 13:2 48:1 | light (cat 6): Aquaman costume 2 | 0x100005e0 in 0xa00002c1 |
| 0xA00002C1 | 7 | 40 | 5.8 | 0 | 10:4 13:9 16:3 17:3 18:5 19:3 1D:3 2D:2 2E:2 36:1 37:1 40:2 49:2 | own (cat 7): Aquaman costume 2 | server (0x20AF / roster); self 0x1000035C |
| 0xA00002C2 | 5 | 2 | 1.4 | 0 | 13:1 48:1 | wallpaper (cat 5): Robin costume 2 | 0x100005df in 0xa00002c4 |
| 0xA00002C3 | 6 | 3 | 0.2 | 0 | 13:2 48:1 | light (cat 6): Robin costume 2 | 0x100005e0 in 0xa00002c4 |
| 0xA00002C4 | 7 | 29 | 4.3 | 0 | 10:3 13:7 16:2 17:2 18:2 19:2 1D:1 2D:1 2E:1 36:1 37:1 40:3 49:3 | own (cat 7): Robin costume 2 | server (0x20AF / roster); self 0x1000035C |
| 0xA00002C5 | 5 | 2 | 1.4 | 0 | 13:1 48:1 | wallpaper (cat 5): Starro costume 1 | 0x100005df in 0xa00002c7 |
| 0xA00002C6 | 6 | 3 | 0.2 | 0 | 13:2 48:1 | light (cat 6): Starro costume 1 | 0x100005e0 in 0xa00002c7 |
| 0xA00002C7 | 7 | 41 | 4.4 | 0 | 10:2 13:11 16:4 17:4 18:3 19:2 1D:3 1E:2 2D:2 2E:3 36:1 40:2 49:2 | own (cat 7): Starro costume 1 | server (0x20AF / roster); self 0x1000035C |
| 0xA00002C8 | 5 | 2 | 1.4 | 0 | 13:1 48:1 | wallpaper (cat 5): Catwoman costume 2 | 0x100005df in 0xa00002ca |
| 0xA00002C9 | 6 | 3 | 0.2 | 0 | 13:2 48:1 | light (cat 6): Catwoman costume 2 | 0x100005e0 in 0xa00002ca |
| 0xA00002CA | 7 | 35 | 3.5 | 0 | 10:3 13:9 16:9 17:3 19:4 1D:1 2D:1 2E:1 36:1 37:1 40:1 49:1 | own (cat 7): Catwoman costume 2 | server (0x20AF / roster); self 0x1000035C |
| 0xA00002CB | 4 | 13 | 0.5 | 1 | 13:8 2B:1 48:4 | skills UI (cat 4): Swamp Thing | 0x10000b0d in 0xa00002ce, 0x10000b0d in 0xa00002d2 |
| 0xA00002CC | 5 | 2 | 1.4 | 0 | 13:1 48:1 | wallpaper (cat 5): Swamp Thing | 0x100005df in 0xa00002ce |
| 0xA00002CD | 6 | 4 | 0.2 | 0 | 13:2 48:1 52:1 | light (cat 6): Swamp Thing | 0x100005e0 in 0xa00002ce |
| 0xA00002CE | 7 | 43 | 2.1 | 0 | 10:6 13:9 16:2 17:2 18:8 19:4 1D:2 2D:2 2E:2 36:1 37:1 40:2 49:2 | own (cat 7): Swamp Thing | server (0x20AF / roster); self 0x1000035C |
| 0xA00002CF | 8 | 319 | 7.5 | 1 | 10:10 13:33 14:1 15:20 16:14 17:14 18:52 19:5 1A:77 1C:3 1D:16 1E:11 1F:2 2B:1 2D:5 2E:7 30:1 34:13 3A:1 3B:3 40:5 48:18 49:5 52:2 | shared (cat 8): Swamp Thing | 0x10000730 in 0xa00002ce, 0x10000730 in 0xa00002d2 |
| 0xA00002D0 | 5 | 2 | 1.4 | 0 | 13:1 48:1 | wallpaper (cat 5): Swamp Thing costume 1 | 0x100005df in 0xa00002d2 |
| 0xA00002D1 | 6 | 3 | 0.2 | 0 | 13:2 48:1 | light (cat 6): Swamp Thing costume 1 | 0x100005e0 in 0xa00002d2 |
| 0xA00002D2 | 7 | 45 | 3.6 | 0 | 10:6 13:11 16:3 17:3 18:7 19:4 1D:1 2D:2 2E:2 36:1 37:1 40:2 49:2 | own (cat 7): Swamp Thing costume 1 | server (0x20AF / roster); self 0x1000035C |
| 0xA00002D3 | 5 | 2 | 1.4 | 0 | 13:1 48:1 | wallpaper (cat 5): Supergirl costume 1 | 0x100005df in 0xa00002d5 |
| 0xA00002D4 | 6 | 3 | 0.2 | 0 | 13:2 48:1 | light (cat 6): Supergirl costume 1 | 0x100005e0 in 0xa00002d5 |
| 0xA00002D5 | 7 | 25 | 3.2 | 0 | 10:2 13:6 16:2 17:2 18:3 19:2 1D:2 2D:1 2E:1 36:1 37:1 40:1 49:1 | own (cat 7): Supergirl costume 1 | server (0x20AF / roster); self 0x1000035C |
| 0xA00002D6 | 7 | 7 | 3.2 | 0 | 13:7 | Tutorial 1 map textures | map list 0xa0c112ca |
| 0xA00002D7 | 7 | 9 | 3.3 | 0 | 13:9 | Tutorial 1 map textures | map list 0xa0c112ca |
| 0xA00002D8 | 5 | 2 | 1.4 | 0 | 13:1 48:1 | wallpaper (cat 5): Hawkgirl costume 1 | 0x100005df in 0xa00002da |
| 0xA00002D9 | 6 | 3 | 0.2 | 0 | 13:2 48:1 | light (cat 6): Hawkgirl costume 1 | 0x100005e0 in 0xa00002da |
| 0xA00002DA | 7 | 37 | 4.6 | 0 | 10:3 13:8 16:6 17:4 18:6 19:3 1D:2 2D:1 2E:1 36:1 40:1 49:1 | own (cat 7): Hawkgirl costume 1 | server (0x20AF / roster); self 0x1000035C |
| 0xA00002DB | 5 | 2 | 1.1 | 0 | 13:1 48:1 | wallpaper (cat 5): Lex Luthor | 0x100005df in 0xa00002df |
| 0xA00002DC | 6 | 4 | 0.1 | 0 | 13:2 48:1 52:1 | light (cat 6): Lex Luthor | 0x100005e0 in 0xa00002df |
| 0xA00002DD | 4 | 13 | 0.2 | 1 | 13:8 2B:1 48:4 | skills UI (cat 4): Lex Luthor | 0x10000b0d in 0xa00002df, 0x10000b0d in 0xa0000344 |
| 0xA00002DE | 8 | 284 | 4.0 | 1 | 10:7 13:27 16:11 17:11 18:54 19:6 1A:72 1C:2 1D:20 1E:10 1F:2 2B:1 2D:6 2E:11 34:14 3A:1 3B:2 40:6 48:13 49:6 52:2 | shared (cat 8): Lex Luthor | 0x10000730 in 0xa00002df, 0x10000730 in 0xa0000344 |
| 0xA00002DF | 7 | 24 | 4.5 | 0 | 10:1 13:11 16:2 17:2 19:1 2D:1 2E:1 36:1 40:2 49:2 | own (cat 7): Lex Luthor | server (0x20AF / roster); self 0x1000035C |
| 0xA00002E0 | 5 | 2 | 1.1 | 0 | 13:1 48:1 | wallpaper (cat 5): Katana | 0x100005df in 0xa00002e4 |
| 0xA00002E1 | 6 | 4 | 0.1 | 0 | 13:2 48:1 52:1 | light (cat 6): Katana | 0x100005e0 in 0xa00002e4 |
| 0xA00002E2 | 4 | 13 | 0.4 | 1 | 13:8 2B:1 48:4 | skills UI (cat 4): Katana | 0x10000b0d in 0xa00002e4, 0x10000b0d in 0xa000031f, 0x10000b0d in 0xa000038a |
| 0xA00002E3 | 8 | 270 | 5.7 | 1 | 10:7 13:26 14:1 15:4 16:11 17:11 18:34 19:2 1A:84 1C:1 1D:20 1E:10 1F:1 2B:1 2D:2 2E:8 30:1 34:15 3A:1 3B:2 3F:1 40:3 48:19 49:3 52:2 | shared (cat 8): Katana | 0x10000730 in 0xa00002e4, 0x10000730 in 0xa000031f, 0x10000730 in 0xa000038a |
| 0xA00002E4 | 7 | 37 | 3.4 | 0 | 10:4 13:12 16:4 17:2 18:2 19:4 1D:2 2D:1 2E:2 36:1 37:1 40:1 49:1 | own (cat 7): Katana | server (0x20AF / roster); self 0x1000035C |
| 0xA00002E5 | 13 | 5127 | 132.6 | 0 | 08:2 10:1082 11:158 13:666 14:25 15:631 16:404 17:296 18:105 19:504 1A:4 1C:4 1D:109 2D:478 2E:513 34:2 3E:4 40:9 48:4 49:9 50:118 | zone of Crime Alley (v AI, 1vAI tutorial, Clash 1v1/2v2) / Tutorial 2 | map list 0xa0c112ba, map list 0xa0c112c2 |
| 0xA00002E6 | 15 | 1173 | 22.0 | 15 | 10:97 11:16 13:130 14:3 15:64 16:93 17:52 18:159 19:65 1A:37 1C:13 1D:72 1E:14 1F:1 2B:15 2D:53 2E:69 30:2 34:28 35:15 36:2 3B:23 40:49 48:38 49:49 52:14 | layout of Crime Alley (v AI, 1vAI tutorial, Clash 1v1/2v2) / Tutorial 2 | map list 0xa0c112ba, map list 0xa0c112c2 |
| 0xA00002E7 | 14 | 652 | 10.9 | 3 | 10:19 13:70 16:25 17:21 18:79 19:21 1A:73 1C:11 1D:45 1E:19 1F:6 2B:3 2D:17 2E:31 34:11 36:9 3B:59 40:52 48:27 49:52 52:2 | variants (units) of Crime Alley (v AI, 1vAI tutorial, Clash 1v1/2v2) / Tutorial 2 | map list 0xa0c112ba, map list 0xa0c112c2 |
| 0xA00002E8 | 5 | 2 | 1.4 | 0 | 13:1 48:1 | wallpaper (cat 5): Nightmare Superman costume 1 | 0x100005df in 0xa00002ea |
| 0xA00002E9 | 6 | 3 | 0.2 | 0 | 13:2 48:1 | light (cat 6): Nightmare Superman costume 1 | 0x100005e0 in 0xa00002ea |
| 0xA00002EA | 7 | 40 | 3.8 | 0 | 10:4 13:8 16:5 17:4 18:3 19:4 1D:2 1E:3 2D:1 2E:2 37:2 40:1 49:1 | own (cat 7): Nightmare Superman costume 1 | server (0x20AF / roster); self 0x1000035C |
| 0xA00002EB | 5 | 2 | 1.4 | 0 | 13:1 48:1 | wallpaper (cat 5): Arcane Supergirl costume 1 | 0x100005df in 0xa00002ed |
| 0xA00002EC | 6 | 3 | 0.2 | 0 | 13:2 48:1 | light (cat 6): Arcane Supergirl costume 1 | 0x100005e0 in 0xa00002ed |
| 0xA00002ED | 7 | 42 | 5.6 | 0 | 10:5 13:8 16:2 17:2 18:7 19:5 1D:2 2D:1 2E:1 36:1 37:4 40:2 49:2 | own (cat 7): Arcane Supergirl costume 1 | server (0x20AF / roster); self 0x1000035C |
| 0xA00002EE | 5 | 2 | 1.4 | 0 | 13:1 48:1 | wallpaper (cat 5): Arcane Green Lantern costume 2 | 0x100005df in 0xa00002f0 |
| 0xA00002EF | 6 | 3 | 0.2 | 0 | 13:2 48:1 | light (cat 6): Arcane Green Lantern costume 2 | 0x100005e0 in 0xa00002f0 |
| 0xA00002F0 | 7 | 108 | 8.2 | 0 | 10:6 13:10 16:3 17:2 19:5 1A:68 1C:1 1D:2 1F:1 2D:2 2E:3 36:1 37:2 40:1 49:1 | own (cat 7): Arcane Green Lantern costume 2 | server (0x20AF / roster); self 0x1000035C |
| 0xA00002F1 | 6 | 2 | 0.2 | 0 | 13:1 48:1 | light (cat 6): Gaslight Batman costume 3 | 0x100005e0 in 0xa00002f3 |
| 0xA00002F2 | 5 | 2 | 1.1 | 0 | 13:1 48:1 | wallpaper (cat 5): Gaslight Batman costume 3 | 0x100005df in 0xa00002f3 |
| 0xA00002F3 | 7 | 21 | 2.0 | 0 | 10:2 13:6 16:1 17:1 18:3 19:1 1D:2 2D:1 2E:1 36:1 40:1 49:1 | own (cat 7): Gaslight Batman costume 3 | server (0x20AF / roster); self 0x1000035C |
| 0xA00002F4 | 5 | 2 | 0.5 | 0 | 13:1 48:1 | wallpaper (cat 5): Krypto | 0x100005df in 0xa00002f8 |
| 0xA00002F5 | 6 | 4 | 0.1 | 0 | 13:2 48:1 52:1 | light (cat 6): Krypto | 0x100005e0 in 0xa00002f8 |
| 0xA00002F6 | 4 | 13 | 0.5 | 1 | 13:8 2B:1 48:4 | skills UI (cat 4): Krypto | 0x10000b0d in 0xa00002f8, 0x10000b0d in 0xa000035a, 0x10000b0d in 0xa00003b6, +1 |
| 0xA00002F7 | 8 | 252 | 7.7 | 1 | 10:13 13:27 14:1 16:14 17:14 18:31 19:5 1A:68 1C:1 1D:13 1E:17 1F:1 2B:1 2D:5 2E:6 34:9 3A:1 3B:2 40:3 48:15 49:3 52:2 | shared (cat 8): Krypto | 0x10000730 in 0xa00002f8, 0x10000730 in 0xa000035a, 0x10000730 in 0xa00003b6, +1 |
| 0xA00002F8 | 7 | 23 | 2.3 | 0 | 10:2 13:5 16:2 17:2 18:3 19:2 1D:1 2D:1 2E:1 36:1 37:1 40:1 49:1 | own (cat 7): Krypto | server (0x20AF / roster); self 0x1000035C |
| 0xA00002F9 | 7 | 35 | 5.3 | 0 | 10:3 13:14 16:6 17:2 19:3 1D:1 2D:1 2E:1 36:1 37:1 40:1 49:1 | own (cat 7): Atomic Wonder Woman costume 2 | server (0x20AF / roster); self 0x1000035C |
| 0xA00002FA | 6 | 3 | 0.2 | 0 | 13:2 48:1 | light (cat 6): Atomic Wonder Woman costume 2 | 0x100005e0 in 0xa00002f9 |
| 0xA00002FB | 5 | 2 | 0.7 | 0 | 13:1 48:1 | wallpaper (cat 5): Atomic Wonder Woman costume 2 | 0x100005df in 0xa00002f9 |
| 0xA00002FC | 5 | 2 | 1.4 | 0 | 13:1 48:1 | wallpaper (cat 5): Sinestro costume 1 | 0x100005df in 0xa00002fe |
| 0xA00002FD | 6 | 3 | 0.2 | 0 | 13:2 48:1 | light (cat 6): Sinestro costume 1 | 0x100005e0 in 0xa00002fe |
| 0xA00002FE | 7 | 114 | 7.3 | 0 | 10:4 13:7 16:3 17:3 18:7 19:6 1A:67 1C:1 1D:4 1F:1 2D:3 2E:3 36:1 37:2 40:1 49:1 | own (cat 7): Sinestro costume 1 | server (0x20AF / roster); self 0x1000035C |
| 0xA00002FF | 8 | 929 | 4.1 | 0 | 13:22 40:453 48:1 49:453 | achievement entities 0x40/0x49 (453), named by the UI pack list 0x10000B62 | 0x10000b61 (array 0x10000b62) in 0xa00000d0 |
| 0xA0000300 | 5 | 2 | 1.4 | 0 | 13:1 48:1 | wallpaper (cat 5): Arcane Zatanna | 0x100005df in 0xa0000304 |
| 0xA0000301 | 6 | 4 | 0.2 | 0 | 13:2 48:1 52:1 | light (cat 6): Arcane Zatanna | 0x100005e0 in 0xa0000304 |
| 0xA0000302 | 4 | 13 | 0.5 | 1 | 13:8 2B:1 48:4 | skills UI (cat 4): Arcane Zatanna | 0x10000b0d in 0xa0000304, 0x10000b0d in 0xa0000349, 0x10000b0d in 0xa00003a6 |
| 0xA0000303 | 8 | 326 | 6.6 | 1 | 10:10 13:42 16:14 17:13 18:45 19:7 1A:97 1C:3 1D:16 1E:12 1F:2 2B:1 2D:6 2E:8 34:14 3A:2 3B:2 40:7 48:16 49:7 52:2 | shared (cat 8): Arcane Zatanna | 0x10000730 in 0xa0000304, 0x10000730 in 0xa0000349, 0x10000730 in 0xa00003a6 |
| 0xA0000304 | 7 | 32 | 2.6 | 0 | 10:5 13:10 16:2 17:2 19:4 1D:1 2D:1 2E:1 36:1 37:3 40:1 49:1 | own (cat 7): Arcane Zatanna | server (0x20AF / roster); self 0x1000035C |
| 0xA0000305 | 5 | 2 | 1.4 | 0 | 13:1 48:1 | wallpaper (cat 5): Green Lantern costume 2 | 0x100005df in 0xa0000307 |
| 0xA0000306 | 6 | 3 | 0.2 | 0 | 13:2 48:1 | light (cat 6): Green Lantern costume 2 | 0x100005e0 in 0xa0000307 |
| 0xA0000307 | 7 | 17 | 4.0 | 0 | 10:2 13:4 16:1 17:1 19:2 1D:1 2D:1 2E:1 36:1 37:1 40:1 49:1 | own (cat 7): Green Lantern costume 2 | server (0x20AF / roster); self 0x1000035C |
| 0xA0000308 | 5 | 2 | 1.4 | 0 | 13:1 48:1 | wallpaper (cat 5): Arcane Green Lantern costume 3 | 0x100005df in 0xa000030a |
| 0xA0000309 | 6 | 3 | 0.2 | 0 | 13:2 48:1 | light (cat 6): Arcane Green Lantern costume 3 | 0x100005e0 in 0xa000030a |
| 0xA000030A | 7 | 114 | 8.4 | 0 | 10:7 13:10 16:3 17:2 19:7 1A:68 1C:1 1D:2 1F:1 2D:3 2E:4 36:1 37:3 40:1 49:1 | own (cat 7): Arcane Green Lantern costume 3 | server (0x20AF / roster); self 0x1000035C |
| 0xA000030B | 5 | 2 | 0.7 | 0 | 13:1 48:1 | wallpaper (cat 5): Deathstroke | 0x100005df in 0xa000030f |
| 0xA000030C | 6 | 4 | 0.2 | 0 | 13:2 48:1 52:1 | light (cat 6): Deathstroke | 0x100005e0 in 0xa000030f |
| 0xA000030D | 4 | 17 | 0.2 | 1 | 13:12 2B:1 48:4 | skills UI (cat 4): Deathstroke | 0x10000b0d in 0xa000030f, 0x10000b0d in 0xa0000387, 0x10000b0d in 0xa00003c3 |
| 0xA000030E | 8 | 191 | 2.9 | 1 | 10:4 13:19 16:5 17:5 18:24 19:2 1A:67 1C:1 1D:11 1E:10 1F:1 2B:1 2D:2 2E:2 34:10 3A:1 3B:1 40:4 48:15 49:4 52:2 | shared (cat 8): Deathstroke | 0x10000730 in 0xa000030f, 0x10000730 in 0xa0000387, 0x10000730 in 0xa00003c3 |
| 0xA000030F | 7 | 40 | 6.1 | 0 | 10:8 13:16 16:3 17:3 19:3 1D:1 2D:1 2E:1 36:1 37:1 40:1 49:1 | own (cat 7): Deathstroke | server (0x20AF / roster); self 0x1000035C |
| 0xA0000310 | 6 | 3 | 0.2 | 0 | 13:2 48:1 | light (cat 6): Atomic Green Lantern costume 2 | 0x100005e0 in 0xa0000312 |
| 0xA0000311 | 5 | 2 | 0.7 | 0 | 13:1 48:1 | wallpaper (cat 5): Atomic Green Lantern costume 2 | 0x100005df in 0xa0000312 |
| 0xA0000312 | 7 | 27 | 3.9 | 0 | 10:3 13:11 16:2 17:2 18:1 19:2 1D:1 2D:1 2E:1 36:1 40:1 49:1 | own (cat 7): Atomic Green Lantern costume 2 | server (0x20AF / roster); self 0x1000035C |
| 0xA0000313 | 7 | 27 | 5.7 | 0 | 10:5 13:6 16:3 17:2 19:4 1D:1 2D:1 2E:1 36:1 37:1 40:1 49:1 | own (cat 7): Gaslight Joker costume 3 | server (0x20AF / roster); self 0x1000035C |
| 0xA0000314 | 6 | 3 | 0.2 | 0 | 13:2 48:1 | light (cat 6): Gaslight Joker costume 3 | 0x100005e0 in 0xa0000313 |
| 0xA0000315 | 5 | 2 | 1.4 | 0 | 13:1 48:1 | wallpaper (cat 5): Gaslight Joker costume 3 | 0x100005df in 0xa0000313 |
| 0xA0000316 | 8 | 6 | 0.1 | 1 | 13:1 2B:1 40:1 49:1 52:2 | small shared pack (2 sound banks, 1 entity 0x40000CBD), named by record 0x48000E36 property 0x10000B87 | 0x10000b87 in 0xa00000b3 |
| 0xA000031D | 5 | 2 | 1.1 | 0 | 13:1 48:1 | wallpaper (cat 5): Katana costume 1 | 0x100005df in 0xa000031f |
| 0xA000031E | 6 | 3 | 0.1 | 0 | 13:2 48:1 | light (cat 6): Katana costume 1 | 0x100005e0 in 0xa000031f |
| 0xA000031F | 7 | 39 | 5.5 | 0 | 10:5 13:11 16:4 17:2 18:2 19:5 1D:2 2D:1 2E:2 36:1 37:2 40:1 49:1 | own (cat 7): Katana costume 1 | server (0x20AF / roster); self 0x1000035C |
| 0xA0000320 | 5 | 2 | 0.7 | 0 | 13:1 48:1 | wallpaper (cat 5): Shazam costume 2 | 0x100005df in 0xa0000322 |
| 0xA0000321 | 6 | 3 | 0.2 | 0 | 13:2 48:1 | light (cat 6): Shazam costume 2 | 0x100005e0 in 0xa0000322 |
| 0xA0000322 | 7 | 20 | 1.2 | 0 | 10:2 13:5 16:2 17:2 18:1 19:1 1D:2 2D:1 2E:1 36:1 40:1 49:1 | own (cat 7): Shazam costume 2 | server (0x20AF / roster); self 0x1000035C |
| 0xA0000324 | 4 | 13 | 0.4 | 1 | 13:8 2B:1 48:4 | skills UI (cat 4): Solomon Grundy | 0x10000b0d in 0xa0000327, 0x10000b0d in 0xa000032e |
| 0xA0000325 | 5 | 2 | 0.5 | 0 | 13:1 48:1 | wallpaper (cat 5): Solomon Grundy | 0x100005df in 0xa0000327 |
| 0xA0000326 | 6 | 4 | 0.2 | 0 | 13:2 48:1 52:1 | light (cat 6): Solomon Grundy | 0x100005e0 in 0xa0000327 |
| 0xA0000327 | 7 | 32 | 3.3 | 0 | 10:3 13:11 16:3 17:2 18:3 19:3 1D:1 2D:1 2E:1 36:1 37:1 40:1 49:1 | own (cat 7): Solomon Grundy | server (0x20AF / roster); self 0x1000035C |
| 0xA0000328 | 8 | 303 | 4.3 | 1 | 10:13 13:29 14:1 15:52 16:13 17:13 18:37 19:2 1A:73 1C:1 1D:10 1E:14 1F:1 2B:1 2D:2 2E:2 30:1 34:13 3A:1 3B:1 40:2 48:17 49:2 52:2 | shared (cat 8): Solomon Grundy | 0x10000730 in 0xa0000327, 0x10000730 in 0xa000032e |
| 0xA0000329 | 5 | 2 | 1.4 | 0 | 13:1 48:1 | wallpaper (cat 5): Star Sapphire costume 2 | 0x100005df in 0xa000032b |
| 0xA000032A | 6 | 3 | 0.2 | 0 | 13:2 48:1 | light (cat 6): Star Sapphire costume 2 | 0x100005e0 in 0xa000032b |
| 0xA000032B | 7 | 89 | 6.4 | 0 | 10:4 13:6 16:1 17:1 19:3 1A:61 1C:1 1D:1 1F:1 2D:1 2E:1 34:1 36:1 37:2 40:2 49:2 | own (cat 7): Star Sapphire costume 2 | server (0x20AF / roster); self 0x1000035C |
| 0xA000032C | 5 | 2 | 0.5 | 0 | 13:1 48:1 | wallpaper (cat 5): Solomon Grundy costume 1 | 0x100005df in 0xa000032e |
| 0xA000032D | 6 | 3 | 0.2 | 0 | 13:2 48:1 | light (cat 6): Solomon Grundy costume 1 | 0x100005e0 in 0xa000032e |
| 0xA000032E | 7 | 28 | 3.3 | 0 | 10:2 13:11 16:2 17:2 18:3 19:2 1D:1 2D:1 2E:1 36:1 40:1 49:1 | own (cat 7): Solomon Grundy costume 1 | server (0x20AF / roster); self 0x1000035C |
| 0xA000032F | 5 | 2 | 1.4 | 0 | 13:1 48:1 | wallpaper (cat 5): Raven | 0x100005df in 0xa0000333 |
| 0xA0000330 | 6 | 4 | 0.2 | 0 | 13:2 48:1 52:1 | light (cat 6): Raven | 0x100005e0 in 0xa0000333 |
| 0xA0000331 | 4 | 14 | 0.5 | 1 | 13:9 2B:1 48:4 | skills UI (cat 4): Raven | 0x10000b0d in 0xa0000333, 0x10000b0d in 0xa00003a9 |
| 0xA0000332 | 8 | 336 | 7.1 | 1 | 10:11 13:26 14:1 15:20 16:14 17:11 18:61 19:9 1A:63 1C:3 1D:18 1E:27 1F:1 2B:1 2D:6 2E:9 34:14 36:1 37:2 3A:1 3B:1 40:5 48:24 49:5 52:2 | shared (cat 8): Raven | 0x10000730 in 0xa0000333, 0x10000730 in 0xa00003a9 |
| 0xA0000333 | 7 | 7 | 0.0 | 0 | 16:1 19:2 1D:1 2E:1 40:1 49:1 | own (cat 7): Raven | server (0x20AF / roster); self 0x1000035C |
| 0xA0000334 | 5 | 2 | 0.7 | 0 | 13:1 48:1 | wallpaper (cat 5): Deadshot | 0x100005df in 0xa0000338 |
| 0xA0000335 | 6 | 4 | 0.2 | 0 | 13:2 48:1 52:1 | light (cat 6): Deadshot | 0x100005e0 in 0xa0000338 |
| 0xA0000336 | 4 | 13 | 0.2 | 1 | 13:8 2B:1 48:4 | skills UI (cat 4): Deadshot | 0x10000b0d in 0xa0000338, 0x10000b0d in 0xa00003c6 |
| 0xA0000337 | 8 | 263 | 3.9 | 1 | 10:3 13:24 16:9 17:9 18:41 19:1 1A:99 1C:1 1D:15 1E:11 1F:1 2B:1 2D:1 2E:6 34:11 3A:1 3B:2 40:5 48:15 49:5 52:2 | shared (cat 8): Deadshot | 0x10000730 in 0xa0000338, 0x10000730 in 0xa00003c6 |
| 0xA0000338 | 7 | 22 | 2.4 | 0 | 10:2 13:7 16:3 17:3 19:1 1D:1 2D:1 2E:1 36:1 40:1 49:1 | own (cat 7): Deadshot | server (0x20AF / roster); self 0x1000035C |
| 0xA0000339 | 5 | 2 | 1.1 | 0 | 13:1 48:1 | wallpaper (cat 5): Superman costume 5 | 0x100005df in 0xa000033b |
| 0xA000033A | 6 | 3 | 0.1 | 0 | 13:2 48:1 | light (cat 6): Superman costume 5 | 0x100005e0 in 0xa000033b |
| 0xA000033B | 7 | 100 | 6.6 | 0 | 10:2 13:6 16:4 17:2 18:3 19:3 1A:71 1C:1 1D:2 2D:1 2E:2 37:1 40:1 49:1 | own (cat 7): Superman costume 5 | server (0x20AF / roster); self 0x1000035C |
| 0xA000033C | 5 | 2 | 1.4 | 0 | 13:1 48:1 | wallpaper (cat 5): Dex-Starr | 0x100005df in 0xa0000340 |
| 0xA000033D | 6 | 4 | 0.2 | 0 | 13:2 48:1 52:1 | light (cat 6): Dex-Starr | 0x100005e0 in 0xa0000340 |
| 0xA000033E | 4 | 13 | 0.2 | 1 | 13:8 2B:1 48:4 | skills UI (cat 4): Dex-Starr | 0x10000b0d in 0xa0000340 |
| 0xA000033F | 8 | 272 | 3.0 | 1 | 10:6 13:21 14:1 15:50 16:8 17:8 18:45 19:5 1A:64 1C:1 1D:12 1E:6 1F:1 2B:1 2D:5 2E:6 34:10 3B:3 40:3 48:11 49:3 52:2 | shared (cat 8): Dex-Starr | 0x10000730 in 0xa0000340 |
| 0xA0000340 | 7 | 19 | 1.7 | 0 | 10:1 13:7 16:1 17:1 19:1 1D:1 2D:1 2E:1 36:1 40:2 49:2 | own (cat 7): Dex-Starr | server (0x20AF / roster); self 0x1000035C |
| 0xA0000341 | 5 | 2 | 1.4 | 0 | 13:1 48:1 | wallpaper (cat 5): Green Arrow costume 2 | 0x100005df in 0xa0000343 |
| 0xA0000342 | 6 | 3 | 0.2 | 0 | 13:2 48:1 | light (cat 6): Green Arrow costume 2 | 0x100005e0 in 0xa0000343 |
| 0xA0000343 | 7 | 27 | 2.2 | 0 | 10:5 13:8 16:3 17:2 19:2 1D:1 2D:1 2E:1 36:1 37:1 40:1 49:1 | own (cat 7): Green Arrow costume 2 | server (0x20AF / roster); self 0x1000035C |
| 0xA0000344 | 7 | 35 | 4.1 | 0 | 10:3 13:12 16:3 17:3 19:2 1D:1 2D:2 2E:2 36:1 40:3 49:3 | own (cat 7): Lex Luthor costume 1 | server (0x20AF / roster); self 0x1000035C |
| 0xA0000345 | 6 | 3 | 0.1 | 0 | 13:2 48:1 | light (cat 6): Lex Luthor costume 1 | 0x100005e0 in 0xa0000344 |
| 0xA0000346 | 5 | 2 | 1.1 | 0 | 13:1 48:1 | wallpaper (cat 5): Lex Luthor costume 1 | 0x100005df in 0xa0000344 |
| 0xA0000347 | 5 | 2 | 0.7 | 0 | 13:1 48:1 | wallpaper (cat 5): Arcane Zatanna costume 1 | 0x100005df in 0xa0000349 |
| 0xA0000348 | 6 | 3 | 0.2 | 0 | 13:2 48:1 | light (cat 6): Arcane Zatanna costume 1 | 0x100005e0 in 0xa0000349 |
| 0xA0000349 | 7 | 56 | 5.9 | 0 | 10:8 13:17 16:6 17:5 19:6 1D:1 2D:2 2E:2 36:1 37:4 40:2 49:2 | own (cat 7): Arcane Zatanna costume 1 | server (0x20AF / roster); self 0x1000035C |
| 0xA000034A | 5 | 2 | 0.7 | 0 | 13:1 48:1 | wallpaper (cat 5): Blue Beetle costume 2 | 0x100005df in 0xa000034c |
| 0xA000034B | 6 | 3 | 0.2 | 0 | 13:2 48:1 | light (cat 6): Blue Beetle costume 2 | 0x100005e0 in 0xa000034c |
| 0xA000034C | 7 | 53 | 3.9 | 0 | 10:12 13:11 16:4 17:3 18:12 19:3 1D:2 2D:1 2E:1 36:1 37:1 40:1 49:1 | own (cat 7): Blue Beetle costume 2 | server (0x20AF / roster); self 0x1000035C |
| 0xA000034D | 5 | 2 | 1.4 | 0 | 13:1 48:1 | wallpaper (cat 5): Flash costume 2 | 0x100005df in 0xa000034f |
| 0xA000034E | 6 | 3 | 0.2 | 0 | 13:2 48:1 | light (cat 6): Flash costume 2 | 0x100005e0 in 0xa000034f |
| 0xA000034F | 7 | 82 | 8.7 | 0 | 10:10 13:11 16:9 17:7 18:11 19:8 1A:3 1C:2 1D:6 1E:2 2D:3 2E:5 36:1 37:2 40:1 49:1 | own (cat 7): Flash costume 2 | server (0x20AF / roster); self 0x1000035C |
| 0xA0000351 | 24 | 232 | 0.8 | 7 | 13:6 2B:7 40:7 48:204 49:7 52:1 | training / progression data: 204 records 0x48 (0x48001xxx, mission-style lists), 7 entities 0x40000CC2-CC8, the training intro movie name | exe |
| 0xA0000352 | 5 | 2 | 0.7 | 0 | 13:1 48:1 | wallpaper (cat 5): Green Arrow costume 3 | 0x100005df in 0xa0000354 |
| 0xA0000353 | 6 | 3 | 0.2 | 0 | 13:2 48:1 | light (cat 6): Green Arrow costume 3 | 0x100005e0 in 0xa0000354 |
| 0xA0000354 | 7 | 24 | 4.9 | 0 | 10:4 13:9 16:2 17:2 19:1 1D:1 2D:1 2E:1 36:1 40:1 49:1 | own (cat 7): Green Arrow costume 3 | server (0x20AF / roster); self 0x1000035C |
| 0xA0000355 | 5 | 2 | 1.4 | 0 | 13:1 48:1 | wallpaper (cat 5): Batman costume 3 | 0x100005df in 0xa0000357 |
| 0xA0000356 | 6 | 3 | 0.2 | 0 | 13:2 48:1 | light (cat 6): Batman costume 3 | 0x100005e0 in 0xa0000357 |
| 0xA0000357 | 7 | 27 | 2.3 | 0 | 10:2 13:8 16:2 17:2 18:3 19:2 1D:2 2D:1 2E:1 36:1 37:1 40:1 49:1 | own (cat 7): Batman costume 3 | server (0x20AF / roster); self 0x1000035C |
| 0xA0000358 | 5 | 2 | 1.1 | 0 | 13:1 48:1 | wallpaper (cat 5): Krypto costume 1 | 0x100005df in 0xa000035a |
| 0xA0000359 | 6 | 3 | 0.1 | 0 | 13:2 48:1 | light (cat 6): Krypto costume 1 | 0x100005e0 in 0xa000035a |
| 0xA000035A | 7 | 18 | 1.5 | 0 | 10:1 13:5 16:1 17:1 18:3 19:1 1D:1 2D:1 2E:1 36:1 40:1 49:1 | own (cat 7): Krypto costume 1 | server (0x20AF / roster); self 0x1000035C |
| 0xA000035B | 5 | 2 | 1.4 | 0 | 13:1 48:1 | wallpaper (cat 5): Starro costume 2 | 0x100005df in 0xa000035d |
| 0xA000035C | 6 | 3 | 0.2 | 0 | 13:2 48:1 | light (cat 6): Starro costume 2 | 0x100005e0 in 0xa000035d |
| 0xA000035D | 7 | 42 | 5.3 | 0 | 10:3 13:10 16:4 17:3 18:3 19:3 1D:3 1E:2 2D:2 2E:3 36:1 37:1 40:2 49:2 | own (cat 7): Starro costume 2 | server (0x20AF / roster); self 0x1000035C |
| 0xA000035E | 5 | 2 | 1.4 | 0 | 13:1 48:1 | wallpaper (cat 5): Huntress | 0x100005df in 0xa0000362 |
| 0xA000035F | 6 | 4 | 0.2 | 0 | 13:2 48:1 52:1 | light (cat 6): Huntress | 0x100005e0 in 0xa0000362 |
| 0xA0000360 | 4 | 13 | 0.1 | 1 | 13:8 2B:1 48:4 | skills UI (cat 4): Huntress | 0x10000b0d in 0xa0000362 |
| 0xA0000361 | 8 | 129 | 0.9 | 1 | 10:5 13:15 16:3 17:3 18:29 19:3 1D:14 1E:9 2B:1 2D:3 2E:6 34:13 3B:2 40:4 48:13 49:4 52:2 | shared (cat 8): Huntress | 0x10000730 in 0xa0000362 |
| 0xA0000362 | 7 | 113 | 4.8 | 0 | 10:5 13:11 16:3 17:2 19:3 1A:77 1C:1 1D:1 1F:1 2D:1 2E:1 36:1 37:2 40:2 49:2 | own (cat 7): Huntress | server (0x20AF / roster); self 0x1000035C |
| 0xA0000363 | 5 | 2 | 1.4 | 0 | 13:1 48:1 | wallpaper (cat 5): Atomic Poison Ivy costume 2 | 0x100005df in 0xa0000365 |
| 0xA0000364 | 6 | 3 | 0.2 | 0 | 13:2 48:1 | light (cat 6): Atomic Poison Ivy costume 2 | 0x100005e0 in 0xa0000365 |
| 0xA0000365 | 7 | 23 | 2.1 | 0 | 10:3 13:6 16:3 17:2 18:1 19:2 1D:1 2D:1 2E:1 36:1 40:1 49:1 | own (cat 7): Atomic Poison Ivy costume 2 | server (0x20AF / roster); self 0x1000035C |
| 0xA0000366 | 5 | 2 | 1.4 | 0 | 13:1 48:1 | wallpaper (cat 5): Mecha Wonder Woman costume 2 | 0x100005df in 0xa0000368 |
| 0xA0000367 | 6 | 3 | 0.2 | 0 | 13:2 48:1 | light (cat 6): Mecha Wonder Woman costume 2 | 0x100005e0 in 0xa0000368 |
| 0xA0000368 | 7 | 29 | 5.4 | 0 | 10:3 13:11 16:4 17:2 19:2 1D:1 2D:1 2E:1 36:1 3A:1 40:1 49:1 | own (cat 7): Mecha Wonder Woman costume 2 | server (0x20AF / roster); self 0x1000035C |
| 0xA0000369 | 4 | 13 | 0.5 | 1 | 13:8 2B:1 48:4 | skills UI (cat 4): Nightmare Catwoman | 0x10000b0d in 0xa000036c |
| 0xA000036A | 6 | 4 | 0.2 | 0 | 13:2 48:1 52:1 | light (cat 6): Nightmare Catwoman | 0x100005e0 in 0xa000036c |
| 0xA000036B | 5 | 2 | 1.4 | 0 | 13:1 48:1 | wallpaper (cat 5): Nightmare Catwoman | 0x100005df in 0xa000036c |
| 0xA000036C | 7 | 32 | 5.0 | 0 | 10:5 13:6 16:3 17:1 19:6 1D:1 2D:1 2E:1 36:1 37:3 40:2 49:2 | own (cat 7): Nightmare Catwoman | server (0x20AF / roster); self 0x1000035C |
| 0xA000036D | 8 | 237 | 8.0 | 1 | 10:10 13:31 14:1 15:20 16:11 17:9 18:24 19:4 1A:72 1C:1 1D:12 1E:8 1F:1 2B:1 2D:2 2E:3 34:8 3B:1 3F:1 40:3 48:9 49:3 52:2 | shared (cat 8): Nightmare Catwoman | 0x10000730 in 0xa000036c |
| 0xA000036E | 8 | 11 | 0.7 | 0 | 13:11 | 11 textures, named by the UI pack list 0x10000B62 | 0x10000b61 (array 0x10000b62) in 0xa00000d0 |
| 0xA000036F | 5 | 2 | 1.1 | 0 | 13:1 48:1 | wallpaper (cat 5): Stargirl costume 2 | 0x100005df in 0xa0000371 |
| 0xA0000370 | 6 | 3 | 0.1 | 0 | 13:2 48:1 | light (cat 6): Stargirl costume 2 | 0x100005e0 in 0xa0000371 |
| 0xA0000371 | 7 | 32 | 2.1 | 0 | 10:4 13:6 16:2 17:2 18:4 19:3 1D:3 2D:2 2E:2 36:1 37:1 40:1 49:1 | own (cat 7): Stargirl costume 2 | server (0x20AF / roster); self 0x1000035C |
| 0xA0000372 | 5 | 2 | 1.1 | 0 | 13:1 48:1 | wallpaper (cat 5): Nightmare Batman costume 3 | 0x100005df in 0xa0000374 |
| 0xA0000373 | 6 | 3 | 0.1 | 0 | 13:2 48:1 | light (cat 6): Nightmare Batman costume 3 | 0x100005e0 in 0xa0000374 |
| 0xA0000374 | 7 | 20 | 3.6 | 0 | 10:3 13:6 16:2 17:1 19:2 2D:1 2E:1 36:1 37:1 40:1 49:1 | own (cat 7): Nightmare Batman costume 3 | server (0x20AF / roster); self 0x1000035C |
| 0xA0000375 | 5 | 2 | 0.7 | 0 | 13:1 48:1 | wallpaper (cat 5): Zod | 0x100005df in 0xa0000379 |
| 0xA0000376 | 6 | 4 | 0.2 | 0 | 13:2 48:1 52:1 | light (cat 6): Zod | 0x100005e0 in 0xa0000379 |
| 0xA0000377 | 4 | 14 | 0.6 | 1 | 13:9 2B:1 48:4 | skills UI (cat 4): Zod | 0x10000b0d in 0xa0000379 |
| 0xA0000378 | 8 | 224 | 6.6 | 1 | 10:2 13:23 14:1 15:4 16:12 17:12 18:29 19:2 1A:85 1C:1 1D:10 1E:5 1F:1 2B:1 2D:1 2E:2 30:1 34:10 3A:1 3B:2 40:2 48:13 49:2 52:2 | shared (cat 8): Zod | 0x10000730 in 0xa0000379 |
| 0xA0000379 | 7 | 20 | 1.2 | 0 | 10:2 13:3 16:2 17:2 19:2 1D:1 2D:1 2E:1 36:1 37:1 40:2 49:2 | own (cat 7): Zod | server (0x20AF / roster); self 0x1000035C |
| 0xA000037A | 5 | 2 | 1.4 | 0 | 13:1 48:1 | wallpaper (cat 5): Atomic Joker costume 2 | 0x100005df in 0xa000037c |
| 0xA000037B | 6 | 3 | 0.2 | 0 | 13:2 48:1 | light (cat 6): Atomic Joker costume 2 | 0x100005e0 in 0xa000037c |
| 0xA000037C | 7 | 39 | 3.1 | 0 | 10:10 13:6 16:1 17:1 18:1 19:4 1D:3 2D:3 2E:3 36:1 40:3 49:3 | own (cat 7): Atomic Joker costume 2 | server (0x20AF / roster); self 0x1000035C |
| 0xA000037D | 5 | 2 | 1.4 | 0 | 13:1 48:1 | wallpaper (cat 5): Harley Quinn costume 3 | 0x100005df in 0xa000037f |
| 0xA000037E | 6 | 3 | 0.2 | 0 | 13:2 48:1 | light (cat 6): Harley Quinn costume 3 | 0x100005e0 in 0xa000037f |
| 0xA000037F | 7 | 55 | 3.1 | 0 | 10:11 13:9 16:4 17:4 18:4 19:8 1D:2 2D:4 2E:4 36:1 37:1 3A:1 40:1 49:1 | own (cat 7): Harley Quinn costume 3 | server (0x20AF / roster); self 0x1000035C |
| 0xA0000380 | 4 | 14 | 0.6 | 1 | 13:9 2B:1 48:4 | skills UI (cat 4): Arcane Harley Quinn | 0x10000b0d in 0xa0000383 |
| 0xA0000381 | 5 | 2 | 1.4 | 0 | 13:1 48:1 | wallpaper (cat 5): Arcane Harley Quinn | 0x100005df in 0xa0000383 |
| 0xA0000382 | 6 | 4 | 0.2 | 0 | 13:2 48:1 52:1 | light (cat 6): Arcane Harley Quinn | 0x100005e0 in 0xa0000383 |
| 0xA0000383 | 7 | 4 | 0.0 | 0 | 40:2 49:2 | own (cat 7): Arcane Harley Quinn | server (0x20AF / roster); self 0x1000035C |
| 0xA0000384 | 8 | 176 | 5.4 | 1 | 10:4 13:29 16:4 17:4 18:8 19:2 1A:67 1C:1 1D:10 1E:4 1F:1 2B:1 2D:1 2E:1 30:1 34:10 36:1 37:1 3A:1 3B:1 40:3 48:16 49:3 52:2 | shared (cat 8): Arcane Harley Quinn | 0x10000730 in 0xa0000383 |
| 0xA0000385 | 5 | 2 | 1.4 | 0 | 13:1 48:1 | wallpaper (cat 5): Deathstroke costume 1 | 0x100005df in 0xa0000387 |
| 0xA0000386 | 6 | 3 | 0.2 | 0 | 13:2 48:1 | light (cat 6): Deathstroke costume 1 | 0x100005e0 in 0xa0000387 |
| 0xA0000387 | 7 | 32 | 3.1 | 0 | 10:9 13:7 16:2 17:2 19:4 1D:1 2D:1 2E:1 36:1 37:2 40:1 49:1 | own (cat 7): Deathstroke costume 1 | server (0x20AF / roster); self 0x1000035C |
| 0xA0000388 | 5 | 2 | 1.1 | 0 | 13:1 48:1 | wallpaper (cat 5): Katana costume 2 | 0x100005df in 0xa000038a |
| 0xA0000389 | 6 | 3 | 0.2 | 0 | 13:2 48:1 | light (cat 6): Katana costume 2 | 0x100005e0 in 0xa000038a |
| 0xA000038A | 7 | 38 | 3.2 | 0 | 10:5 13:13 16:4 17:2 18:1 19:5 1D:1 2D:1 2E:1 36:1 37:2 40:1 49:1 | own (cat 7): Katana costume 2 | server (0x20AF / roster); self 0x1000035C |
| 0xA000038B | 5 | 2 | 1.4 | 0 | 13:1 48:1 | wallpaper (cat 5): Nightmare Superman costume 2 | 0x100005df in 0xa000038d |
| 0xA000038C | 6 | 3 | 0.2 | 0 | 13:2 48:1 | light (cat 6): Nightmare Superman costume 2 | 0x100005e0 in 0xa000038d |
| 0xA000038D | 7 | 35 | 4.6 | 0 | 10:3 13:13 16:4 17:3 19:3 1D:2 1E:1 2D:1 2E:2 37:1 40:1 49:1 | own (cat 7): Nightmare Superman costume 2 | server (0x20AF / roster); self 0x1000035C |
| 0xA0000396 | 4 | 14 | 0.6 | 1 | 13:9 2B:1 48:4 | skills UI (cat 4): Nightwing | 0x10000b0d in 0xa0000399 |
| 0xA0000397 | 5 | 2 | 1.4 | 0 | 13:1 48:1 | wallpaper (cat 5): Nightwing | 0x100005df in 0xa0000399 |
| 0xA0000398 | 6 | 4 | 0.2 | 0 | 13:2 48:1 52:1 | light (cat 6): Nightwing | 0x100005e0 in 0xa0000399 |
| 0xA0000399 | 7 | 18 | 3.1 | 0 | 10:2 13:5 16:1 17:1 19:1 1D:1 2D:1 2E:1 36:1 40:2 49:2 | own (cat 7): Nightwing | server (0x20AF / roster); self 0x1000035C |
| 0xA000039A | 8 | 203 | 6.4 | 1 | 10:5 13:27 16:9 17:8 18:18 19:5 1A:71 1C:3 1D:10 1E:10 1F:1 2B:1 2D:3 2E:3 34:10 3A:1 3B:1 40:3 48:9 49:3 52:2 | shared (cat 8): Nightwing | 0x10000730 in 0xa0000399 |
| 0xA000039B | 4 | 13 | 0.5 | 1 | 13:8 2B:1 48:4 | skills UI (cat 4): John Stewart | 0x10000b0d in 0xa000039e |
| 0xA000039C | 5 | 2 | 1.4 | 0 | 13:1 48:1 | wallpaper (cat 5): John Stewart | 0x100005df in 0xa000039e |
| 0xA000039D | 6 | 3 | 0.2 | 0 | 13:2 48:1 | light (cat 6): John Stewart | 0x100005e0 in 0xa000039e |
| 0xA000039E | 7 | 32 | 3.2 | 0 | 10:4 13:14 16:3 17:3 19:1 1D:1 2D:1 2E:1 40:2 49:2 | own (cat 7): John Stewart | server (0x20AF / roster); self 0x1000035C |
| 0xA000039F | 8 | 111 | 1.4 | 1 | 13:10 16:2 17:2 18:12 1A:53 1C:1 1D:10 1E:2 1F:1 2B:1 2E:2 34:7 3B:1 40:1 48:5 49:1 | shared (cat 8): John Stewart | 0x10000730 in 0xa000039e |
| 0xA00003A4 | 5 | 2 | 1.4 | 0 | 13:1 48:1 | wallpaper (cat 5): Arcane Zatanna costume 2 | 0x100005df in 0xa00003a6 |
| 0xA00003A5 | 6 | 3 | 0.2 | 0 | 13:2 48:1 | light (cat 6): Arcane Zatanna costume 2 | 0x100005e0 in 0xa00003a6 |
| 0xA00003A6 | 7 | 35 | 6.5 | 0 | 10:5 13:9 16:3 17:2 19:4 1D:1 2D:2 2E:2 36:1 37:2 40:2 49:2 | own (cat 7): Arcane Zatanna costume 2 | server (0x20AF / roster); self 0x1000035C |
| 0xA00003A7 | 5 | 2 | 1.4 | 0 | 13:1 48:1 | wallpaper (cat 5): Raven costume 1 | 0x100005df in 0xa00003a9 |
| 0xA00003A8 | 6 | 3 | 0.2 | 0 | 13:2 48:1 | light (cat 6): Raven costume 1 | 0x100005e0 in 0xa00003a9 |
| 0xA00003A9 | 7 | 14 | 5.0 | 0 | 10:2 13:3 16:1 17:1 19:2 1D:1 2D:1 2E:1 40:1 49:1 | own (cat 7): Raven costume 1 | server (0x20AF / roster); self 0x1000035C |
| 0xA00003AA | 5 | 2 | 1.4 | 0 | 13:1 48:1 | wallpaper (cat 5): Mecha Superman costume 2 | 0x100005df in 0xa00003ac |
| 0xA00003AB | 6 | 3 | 0.2 | 0 | 13:2 48:1 | light (cat 6): Mecha Superman costume 2 | 0x100005e0 in 0xa00003ac |
| 0xA00003AC | 7 | 38 | 4.6 | 0 | 10:3 13:11 16:2 17:2 18:8 19:2 1D:3 2D:1 2E:2 36:1 37:1 40:1 49:1 | own (cat 7): Mecha Superman costume 2 | server (0x20AF / roster); self 0x1000035C |
| 0xA00003AE | 5 | 2 | 1.4 | 0 | 13:1 48:1 | wallpaper (cat 5): Sinestro costume 2 | 0x100005df in 0xa00003b0 |
| 0xA00003AF | 6 | 3 | 0.2 | 0 | 13:2 48:1 | light (cat 6): Sinestro costume 2 | 0x100005e0 in 0xa00003b0 |
| 0xA00003B0 | 7 | 108 | 5.7 | 0 | 10:3 13:8 16:3 17:2 18:5 19:4 1A:67 1C:1 1D:4 1F:1 2D:3 2E:3 36:1 37:1 40:1 49:1 | own (cat 7): Sinestro costume 2 | server (0x20AF / roster); self 0x1000035C |
| 0xA00003B1 | 5 | 2 | 1.1 | 0 | 13:1 48:1 | wallpaper (cat 5): Atrocitus costume 2 | 0x100005df in 0xa00003b3 |
| 0xA00003B2 | 6 | 3 | 0.2 | 0 | 13:2 48:1 | light (cat 6): Atrocitus costume 2 | 0x100005e0 in 0xa00003b3 |
| 0xA00003B3 | 7 | 22 | 2.2 | 0 | 10:2 13:5 16:3 17:1 18:1 19:3 1D:1 2D:1 2E:1 36:1 37:1 40:1 49:1 | own (cat 7): Atrocitus costume 2 | server (0x20AF / roster); self 0x1000035C |
| 0xA00003B4 | 5 | 2 | 1.1 | 0 | 13:1 48:1 | wallpaper (cat 5): Krypto costume 2 | 0x100005df in 0xa00003b6 |
| 0xA00003B5 | 6 | 3 | 0.2 | 0 | 13:2 48:1 | light (cat 6): Krypto costume 2 | 0x100005e0 in 0xa00003b6 |
| 0xA00003B6 | 7 | 18 | 2.2 | 0 | 10:1 13:5 16:1 17:1 18:3 19:1 1D:1 2D:1 2E:1 36:1 40:1 49:1 | own (cat 7): Krypto costume 2 | server (0x20AF / roster); self 0x1000035C |
| 0xA00003B8 | 5 | 2 | 1.4 | 0 | 13:1 48:1 | wallpaper (cat 5): Stargirl costume 3 | 0x100005df in 0xa00003ba |
| 0xA00003B9 | 6 | 3 | 0.2 | 0 | 13:2 48:1 | light (cat 6): Stargirl costume 3 | 0x100005e0 in 0xa00003ba |
| 0xA00003BA | 7 | 34 | 3.3 | 0 | 10:4 13:6 16:2 17:1 18:5 19:4 1D:3 2D:2 2E:2 36:1 37:2 40:1 49:1 | own (cat 7): Stargirl costume 3 | server (0x20AF / roster); self 0x1000035C |
| 0xA00003BB | 6 | 3 | 0.2 | 0 | 13:2 48:1 | light (cat 6): Supergirl costume 2 | 0x100005e0 in 0xa00003bd |
| 0xA00003BC | 5 | 2 | 1.4 | 0 | 13:1 48:1 | wallpaper (cat 5): Supergirl costume 2 | 0x100005df in 0xa00003bd |
| 0xA00003BD | 7 | 25 | 2.7 | 0 | 10:2 13:6 16:2 17:2 18:3 19:2 1D:2 2D:1 2E:1 36:1 37:1 40:1 49:1 | own (cat 7): Supergirl costume 2 | server (0x20AF / roster); self 0x1000035C |
| 0xA00003BE | 5 | 2 | 1.4 | 0 | 13:1 48:1 | wallpaper (cat 5): Hawkgirl costume 2 | 0x100005df in 0xa00003c0 |
| 0xA00003BF | 6 | 3 | 0.2 | 0 | 13:2 48:1 | light (cat 6): Hawkgirl costume 2 | 0x100005e0 in 0xa00003c0 |
| 0xA00003C0 | 7 | 21 | 2.4 | 0 | 10:4 13:1 16:1 17:1 18:5 19:2 1D:2 2D:1 2E:1 36:1 40:1 49:1 | own (cat 7): Hawkgirl costume 2 | server (0x20AF / roster); self 0x1000035C |
| 0xA00003C1 | 5 | 2 | 1.4 | 0 | 13:1 48:1 | wallpaper (cat 5): Deathstroke costume 2 | 0x100005df in 0xa00003c3 |
| 0xA00003C2 | 6 | 3 | 0.2 | 0 | 13:2 48:1 | light (cat 6): Deathstroke costume 2 | 0x100005e0 in 0xa00003c3 |
| 0xA00003C3 | 7 | 27 | 3.9 | 0 | 10:7 13:6 16:3 17:3 19:2 1D:1 2D:1 2E:1 36:1 40:1 49:1 | own (cat 7): Deathstroke costume 2 | server (0x20AF / roster); self 0x1000035C |
| 0xA00003C4 | 5 | 2 | 1.4 | 0 | 13:1 48:1 | wallpaper (cat 5): Deadshot costume 1 | 0x100005df in 0xa00003c6 |
| 0xA00003C5 | 6 | 3 | 0.2 | 0 | 13:2 48:1 | light (cat 6): Deadshot costume 1 | 0x100005e0 in 0xa00003c6 |
| 0xA00003C6 | 7 | 42 | 5.3 | 0 | 10:4 13:16 16:7 17:3 19:4 1D:1 2D:1 2E:1 36:1 37:2 40:1 49:1 | own (cat 7): Deadshot costume 1 | server (0x20AF / roster); self 0x1000035C |
| 0xA00003CE | 5 | 2 | 1.4 | 0 | 13:1 48:1 | wallpaper (cat 5): Krypto costume 3 | 0x100005df in 0xa00003d0 |
| 0xA00003CF | 6 | 3 | 0.2 | 0 | 13:2 48:1 | light (cat 6): Krypto costume 3 | 0x100005e0 in 0xa00003d0 |
| 0xA00003D0 | 7 | 22 | 4.6 | 0 | 10:2 13:8 16:2 17:2 19:2 1D:1 2D:1 2E:1 36:1 40:1 49:1 | own (cat 7): Krypto costume 3 | server (0x20AF / roster); self 0x1000035C |
| 0xA00003D1 | 5 | 2 | 1.4 | 0 | 13:1 48:1 | wallpaper (cat 5): Sinestro costume 3 | 0x100005df in 0xa00003d3 |
| 0xA00003D2 | 6 | 3 | 0.2 | 0 | 13:2 48:1 | light (cat 6): Sinestro costume 3 | 0x100005e0 in 0xa00003d3 |
| 0xA00003D3 | 7 | 108 | 4.9 | 0 | 10:3 13:9 16:2 17:2 18:5 19:4 1A:67 1C:1 1D:4 1F:1 2D:3 2E:3 36:1 37:1 40:1 49:1 | own (cat 7): Sinestro costume 3 | server (0x20AF / roster); self 0x1000035C |
| 0xA0C112BA | 17 | 98 | 79.7 | 0 | 13:67 80:9 81:9 82:9 85:1 90:3 | map pack: Crime Alley (v AI, 1vAI tutorial, Clash 1v1/2v2) | 0x10000406 in 0xa00000b3 |
| 0xA0C112C2 | 17 | 99 | 79.7 | 0 | 13:68 80:9 81:9 82:9 85:1 90:3 | map pack: Tutorial 2 | 0x10000406 in 0xa00000b3 |
| 0xA0C112CA | 1 | 48 | 1.3 | 0 | 13:17 80:9 81:9 82:9 85:1 90:3 | map pack: Tutorial 1 | 0x10000406 in 0xa00000b3 |
| 0xA0C11AD2 | 17 | 98 | 91.1 | 0 | 13:67 80:9 81:9 82:9 85:1 90:3 | map pack: Gotham Divided | 0x10000406 in 0xa00000b3 |
| 0xA0C11AF2 | 17 | 97 | 79.9 | 0 | 13:66 80:9 81:9 82:9 85:1 90:3 | map pack: Gotham Heights | 0x10000406 in 0xa00000b3 |
| 0xA0C122E2 | 17 | 104 | 147.3 | 0 | 13:73 80:9 81:9 82:9 85:1 90:3 | map pack: Coast City | 0x10000406 in 0xa00000b3 |

---

## 3. Record types (DID prefixes)

`listed` = DIDs in the 616 pack lists / distinct / packs. Class names and DB types: `db-types.md`. Decoding status:
**full** = every field read; **partial** = the parts the project needs; **none**.

### 3.1 Present in the packs

| Prefix | Listed / distinct / packs | What it is (C/P) | Decoded by the project | Status |
|---|---|---|---|---|
| 0x01-0x07, 0x0C, 0x0F, 0x1B, 0x23, 0x2A, 0x39, 0xF7, 0xFC, 0xFE, 0xFF | 1 each (0xA0000037/38) | Engine / world singletons (tag Region, Cell, Database, WLib). Seen: 0x07 terrain material list (`ter_*` names), 0x0C and 0xF7 config numbers, 0x22-like map defaults, 0x23 a list naming a string table, 0x39 a 160 KB WLib blob, 0xFFBADA55 placeholder (C content glance) | no | **none** |
| 0x08 | 17 / 15 / 7 | Lens flares (LensFlareEffect.cpp) | no | none |
| 0x10 | 10 010 / 8 293 / 225 | Property-key names: the record is only its DID (`0x1000xxxx` = the property ids used as keys) | nothing to decode | n/a |
| 0x11 | 704 / 555 / 11 | Mesh resources (tag Mesh), mostly zone packs (626) | no | none |
| 0x13 | 10 460 / 7 603 / 607 | Textures. Version 2: DXT1 4 283, DXT3 3 272, DXT5 1 902, format 0x15 (A8R8G8B8) 825, 0x1C (A8) 10; version 4: 161 (C) | `uesrv/textures.py` (v2 DXT only) | partial (v4 and the uncompressed formats not read) |
| 0x14 | 487 / 379 / 29 | Material / shader templates with layer stages and DXBC (Depth, Normals..., parameter names) | names only | none |
| 0x15 | 8 091 / 5 237 / 27 | **Compiled shaders** (C: D3D9 `ps_3_0`/`vs_3_0` tokens with CTAB, and DXBC for D3D10/11; sampler / constant names), not text files; 2 256 in 0xA0000037, 1 600 in 0xA00000DF, 3 013 in zone packs | no | none (render only) |
| 0x16 | 4 031 / 2 591 / 228 | Material instances: entries `(key, 0xBB8, texture 0x13, 0, 0)` + floats | `uesrv/gltf.py` (texture keys) | partial |
| 0x17 | 2 973 / 2 183 / 226 | Model parts: 20-byte binding `did | shader 0x14 | key | 1 | material 0x16` (1 402) or a mesh | `uesrv/meshes.py` (static format 0x1205102, skinned 0x23D102 / 0x24D102) | partial (other vertex formats: 0x205102, 0x2205102, 0x21D102 ...) |
| 0x18 | 4 212 / 3 136 / 167 | Particle system descriptions (PSDesc.cpp) | no | none |
| 0x19 | 2 995 / 2 256 / 225 | Appearance parameter sets (key / value, material parameters) | no | none |
| 0x1A | 5 745 / 4 360 / 96 | Havok packfiles: animation clips and behaviour graphs | `uesrv/havok_anim.py` (spline clips), `tools/catalog_scan.py` (graph / clip names) | partial (graphs not run) |
| 0x1C | 264 / 176 / 96 | Object behaviour graphs (Havok packfile, lists its 0x1A clips) | names only | none |
| 0x1D | 2 083 / 1 556 / 224 | DBScriptTable: scriptlet tables (property 0x7D2), layout records, cinematic scenes ending in a scene script | `ics/rp.py` (`script_tables`, `layout_entries`), `ics/gamedata.py` (`scene`, `cinematic_scenes`) | partial (per-frame scene tracks not decoded) |
| 0x1E | 1 134 / 987 / 77 | Status / FX scriptlet records (tag Scriptlet) named by scripts' ApplyEffects (785 references in decoded scripts) | no (the server uses the 0x48 status records and their 0x34 script) | **none** |
| 0x1F | 114 / 77 / 79 | Behaviour-graph Lua scripts (e.g. 0x1F000002 in a clip table) | no | none |
| 0x20 | 89 / 89 / 1 | Scaleform GFx movies (81 `GFX`, 1 `CWS`; UI pack 0xA00000D0) | `tools/extract_records.py --swf` (extraction); AS2 read by hand (`docs/ui-pack-0xa00000d0-notes.txt`) | partial |
| 0x21 | 11 / 11 / 2 | Cameras (`did | 0x2E000003 | floats`) | no | none |
| 0x22 | 5 / 5 / 1 | Map definitions (`gmDefaultMap`, ...) (P) | no | none |
| 0x24 | 3 / 3 / 2 | Font glyph tables | no | none |
| 0x27 | 3 / 3 / 2 | UI layouts (one localized per language in 0xA00000D0's tail) | no | none |
| 0x2B | 311 / 224 / 126 | String tables (text in the tail streams) | `icserver/gamedata.py` | full |
| 0x2D | 2 472 / 1 842 / 224 | `.entity` setups (skeleton, parts, appearance; contain Havok packfiles) | skeleton via `uesrv/havok.py` | partial |
| 0x2E | 2 937 / 2 165 / 228 | World states `did | 7 | .entity 0x2D | 0 | count | properties` (all 2 766 placed ones name an existing 0x2D, C) | `ics/records.py` (properties) | partial (the rest after the properties) |
| 0x30 | 147 / 140 / 17 | EnumMapper name tables (graph events 0x300000A4, variable names) | `ics/rp.py name_tables` | partial |
| 0x31 | 19 / 19 / 1 | Enum tables linking 0x22 / 0x39 records | no | none |
| 0x32 | 1 (0x32000000, 97 KB) | **Master property table**: the property definitions (ids, kinds, names) | no (the catalog's kinds come from `tools/diag.py --props` at run time) | **none** (worth decoding: it would give every property's kind and name offline) |
| 0x33 | 2 | Name tables 0x33000000 (scriptlet keys) / 0x33000001 | `ics/rp.py name_tables` | full |
| 0x34 | 987 / 875 / 75 | Server scripts (HFSM node graphs) | `tools/script_decoder.py` (exact, by emulating the client's Unpack), `ics/script_model.py`, `ics/script_runtime.py` | full format; runtime partial (`tools/script_coverage.py`) |
| 0x35 | 30 / 30 / 5 | Cinematics (scene lists) | `ics/rp.py layout_entries`, `ics/gamedata.py cinematic_scenes` | partial |
| 0x36 | 197 / 71 / 161 | Havok ragdoll / skeleton / mapper packfiles | `uesrv/havok.py` (hkaSkeleton) | partial |
| 0x37 | 185 / 185 / 111 | Entity data next to champion models (tag Entity) | no | none |
| 0x3A | 58 / 52 / 47 | HFSM definitions (variable blocks such as champion timers) | variable blocks only (by hand) | partial |
| 0x3B | 439 / 277 / 66 | Expression trees / scaling formulas (tooltip and stat curves: Linear, Logistic, Step, Power, ScaleByLevel) | no (tooltips only; skills.tsv keeps base + per-rank numbers) | **none** |
| 0x3C | 11 / 11 / 1 | HFSM variable declarations (names such as EntityPosition, Collider) | no | none |
| 0x3E | 17 / 16 / 5 | Square byte grids (64x64, 512x512, 4 bytes per cell; zone and layout packs) (P: terrain / lighting maps) | no | none |
| 0x3F | 4 / 4 / 4 | HFSM objects | no | none |
| 0x40-0x47 | 2 101 / 2 015 / 233 | Entity classes (weenies; only 0x40 used) | class ids on the wire; record body not read | partial |
| 0x48-0x4F | 2 458 (0x48) + 2 101 (0x49) | Property collections: 0x48 data records, 0x49 templates (twins of 0x40) | `ics/records.py`, `ics/gamedata.py` | full (where every property's kind is known; `properties.tsv` has 3 823) |
| 0x50 | 591 / 411 / 5 | Zone-only entity data (0x484-byte object; starts with counts, 0x100003A8, unit-vector floats) | no | none |
| 0x52 | 198 / 161 / 127 | Wwise sound-bank references (`id | name`, section 1.5) | this survey | full (format); banks themselves not read |
| 0x80 | 54 / 54 / 6 | Landblock terrain cells (heights / materials) | no | none |
| 0x81 | 54 / 54 / 6 | Landblock cell data | no | none |
| 0x82 | 54 / 54 / 6 | Landblock statics (type 2/3/7/10/21, cell, world state, position, rotation) | `docs/re-notes/movement-collision-fog-map.md` (by hand) | partial |
| 0x85 | 6 / 6 / 6 | Nav index (agent radii) | read alongside the navmesh | partial |
| 0x90-0x9F | 18 / 18 / 6 | Kynapse NavMesh blobs (one per agent class) | `ics/navmesh.py` | full (what pathing needs) |

### 3.2 Mapped by the client but absent from every pack (C, db-types.md + listing)

0x09, 0x0A, 0x0B, 0x12, 0x25 (movies as records: the install uses loose `video\` files instead), 0x26, 0x2F, 0x38,
0x3D, 0x83, 0x84, 0xA0 (packs themselves: no record bodies), 0xA1, 0xF9, 0xFA.

### 3.3 Not yet decoded, by priority for a working game server

**Gameplay (needed or likely needed):**
1. **0x3B expression trees** (439): stat / damage scaling per level and rank; today `skills.tsv` holds flat numbers. The
   client classes are known (0x10000003-0x1000000F); decode by emulation like the 0x34 scripts.
2. **0x1E status / FX scriptlet records** (1 134): what ApplyEffects (0x1000001D) applies. The server currently goes
   through 0x48 status records; the 0x1E bodies (scriptlets, durations?) are unread.
3. **0x32 master property table** (1 record): property ids, kinds and probably names offline; would replace the
   run-time `diag --props` source and fill the "kind not read yet" gaps.
4. **0x3A / 0x3C / 0x3F HFSM definitions and variable declarations** (73): only variable blocks are read; needed for
   champion timers and conversation handles that scripts reference.
5. **0x40 entity-class bodies** (2 101; the 0x49 twins are read, the class record itself is not).
6. **0x82 statics / 0x81 cells / 0x80 terrain** (162): only the statics are understood by hand; height / collision
   data for server-side movement and line of sight.
7. **0x1D scene tracks** (cinematic per-frame tracks) and **0x35** beyond scene lists.
8. **0x31 enum tables, 0x30 beyond name tables, 0x22 map definitions, 0x23, 0x0C/0xF7 config singletons**.
9. **0x50** zone entity data (591) and **0x37** entity data (185): meaning unknown; could be gameplay (P: physics /
   destructible state).

**UI:** 0x20 Flash movies (extraction works, no structured reader), 0x27 UI layouts, 0x24 fonts.

**Rendering / sound (only for a new client):** 0x11 meshes, 0x13 version-4 and uncompressed textures, 0x14 / 0x15
shaders, 0x16 materials (beyond texture keys), 0x17 other vertex formats, 0x18 particles, 0x19 appearance sets, 0x1A
behaviour graphs, 0x1C, 0x1F Lua, 0x2D setups beyond the skeleton, 0x08 lens flares, 0x3E grids, 0x21 cameras,
engine singletons 0x01-0x07, Wwise bank contents (`.bnk` events).

---

## 4. Referenced DIDs that exist in no pack

| Kind of reference | Links checked | Missing | Status |
|---|---|---|---|
| World state -> `.entity` (0x2E header) | 2 766 | 0 | C |
| Model part -> material 0x16 | 897 | 0 | C |
| Model part -> shader 0x14 | 912 | 0 (8 non-DID words: parts with another layout) | C |
| Material -> texture (`0xBB8` entries) | 10 546 | 0 | C |
| Sound bank 0x52 -> `.pck` bank | 161 | 0 | C |
| Typed pack references (0x10000406 / 0x10000897 / champion packs / UI list / 0x10000B87 / map lists) | 836 | 0 | C |
| **Map statics 0x82 -> world state** | 3 637 placements in the 6 map packs | **308 placements, 64 distinct world states** (Tutorial 1 alone: 91 placements, 44 world states) | C |
| **Decoded server scripts (826 trees) -> any DID** | 3 056 DID words (3 036 resolve) | **14 scripts 0x34 + 4 records 0x48** | C |
| Typed property values (`key | key | DID`, `element | DID`), 195 trusted DID keys | 94 721 candidate words | 7 real-looking misses (rest is texture / float noise) | P |

Missing world states (map statics, low bits of 0x2E00xxxx): 0625, 0626, 0628, 06B3, 06B4, 0944, 0945, 0AF4-0AF9,
10D2, 110F-1119, 111B-112B, 112D, 112E, 1130-1134, 1137, 1139, 113A, 113C, 113D, 113F, 1140, 1178, 1181, 11A6-11A9,
11AC, 11AD. The client drops a static whose class
cannot be built (BlockEntities 0x53DA40), so these are invisible scenery / emitters; nothing the server can supply.

Missing scripts referenced by decoded scripts: 0x34000013, 0x34000027, 0x3400006F, 0x3400016D, 0x340001C5,
0x34000285, 0x34000299, 0x340003B7, 0x340003F9, 0x340004A6, 0x34000534, 0x340005CD, 0x3400060C, 0x3400077C;
missing records: 0x480007E6, 0x480007E7 (from 0x34000384 / 0x340004BC / 0x340004BD), 0x48001022 (0x34000615),
0x4800129B (0x340005AD). A script that starts one of these must treat it as absent (P: dead branches or content cut
before this build).

Probable misses from typed properties: 0x400004B9 and 0x400004E5 (array element 0x10000694 in 0xA000033E and
0xA000033F), 0x34000275 (0x1000041B in the Coast City zone 0xA00000D2), 0x48001409-0x4800140B (0x10000BE1 in
0xA00000B3, the mission lists of record 0x480010F6), 0x1E0004A0 (0x100009A7 in 0xA0000205).

Not "missing": 0x10xxxxxx values (property ids, not records); DIDs present in the install but outside the packs an
encounter lists (e.g. map statics that need 0xA000009A / 0xA00000B3 / 0xA00000DF: maps-encounters.md).

---

## 5. What remains unknown (short)

- **Files:** purpose of `ic_particles_bg.bk2`, `OpenGLGraphicsCore.dll`, `processtexture.dll`, the Twitch / VC 7.1
  DLLs (no binary names them); 6 Wwise banks without a 0x52 record.
- **Packs:** none unaccounted for; 0xA000006F and 0xA0000164 are referenced by nothing in the data.
- **Record formats not decoded:** gameplay 0x3B formulas, 0x1E status FX, 0x32 master property table, HFSM 0x3A /
  0x3C / 0x3F, 0x40 class bodies, terrain 0x80 / 0x81, 0x50, 0x37, 0x31, 0x22, 0x23, engine singletons; UI 0x20
  (structured), 0x27, 0x24; rendering 0x11, 0x14, 0x15, 0x18, 0x19, 0x1C, 0x1F, 0x08, 0x3E and the remaining 0x13 /
  0x17 formats.
- **Missing content:** 64 world states of map statics and 18 DIDs named by scripts are not in this install.

