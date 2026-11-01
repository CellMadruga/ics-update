# Pre-match countdown notices, keymap persistence, match messages ics does not send

Static analysis 2026-10-24/25 (exe `InfiniteCrisis.exe`, VA, base 0x400000; packs in `C:\Infinite Crisis Server\rp`).
Tags: [C] confirmed in code/data, [P] probable, [G] guess. Written incrementally.

## 1. Pre-match countdown notices

### 1.1 The strings and the lines [C]

The on-screen notices of the 2v2 video are **announcer line captions** (English table `0x2B000093`, the announcer
texts), not encounter texts:

| Line (conversation key) | Caption token (table 0x2B000093) | Text | Wwise hash | f32 field |
|---|---|---|---|---|
| **156 (0x9C)** | 0x02F660E0 | "The match begins in 60 seconds." | 0x89C83064 | -1.0 |
| **187 (0xBB)** | 0x02F66010 | "The match begins in 30 seconds." | 0x86C82BAB | 2.0 |
| **151 (0x97)** | 0x02F66030 | "The match begins in 10 seconds." | 0x88C82EF1 | 2.0 |
| **174 (0xAE)** | 0x0F668447 | "Match: Initiating" | 0x0049BFEE | 2.0 |
| 173 (0xAD) | 0x0D87FCF4 | "The match has begun!" | 0x6B623231 | -1.0 |

They sit in the shared announcer line table of record `0x4000047A` (packs 0xA0000162 / 0xA0000168 / 0xA000016B /
0xA00002E6), line entry `f32 1.0 | f32 x | u32 line | u32 Wwise event hash | u8 0 | u32 token | u32 table | ... | u32
type` (type 2 for all five). The similar texts in table `0x2B00006D` ("The match will begin in 60/30/10 seconds!"
0x027A6261-63, "...{} seconds!" 0x0127A624, "The match has begun!" 0x027A6264, "The match is initializing."
0x0D6468E5, "Match Initialization" 0x0F55A5D5) are referenced by no pack record and not by the exe (raw search of
decompressed packs and the exe image): probably texts the original server put in chat / system messages [P].

### 1.2 Nothing on the client plays them by itself [C]

- No announcer set maps a match event to lines 156 / 187 / 151 / 174 / 173: a scan of every pack for any
  `u32 key | u32 key | value` entry with those values finds only unrelated properties (0x10000C1E training step,
  0x100000C8, 0x100001EB). The shared set 0x4900047A holds events 8, 18-30, 52 only (section 3.2). So **0x2039
  cannot produce them** (the client picks a line only through an event of a set, 0xa309d0).
- The match clock is Flash: `gameplay.match.MatchManager.RecvNotice_SetMatchTime(iid, start, end, bIsPreStartTime)`
  -> `MatchTimer.SetCountDown / SetupTimer` (IntervalTimer, 200 ms) only formats "mm:ss" and dispatches
  `MatchTimer_Tick`; no notice, sound or announcement at any value (re-work/ui-as2 `__Packages/gameplay/match/
  MatchTimer.as`, `MatchManager.as`). `AnnouncementsManager` is dead code (listens to SkillRanked / UI_AddObjective).
- The exe holds no table pairing these keys (raw search of .rdata/.data for 0xBB, 0x97, 0xAE / 0x9C within 64 bytes:
  none; no `push 0xBB` near `push 0x97`).

### 1.3 How the original played them [P]

Announcer line keys are global conversation keys (each key exists once across the packs; the sets are copies). An
encounter script plays them with **StartConversation (node 0x100000D1)**: the Crime Alley 1vAI tutorial's encounter
script `0x34000628` starts 28 conversations whose keys are announcer lines: 247 "Drones in 10 seconds!" (table 0x2B0000A1), 204 "{}
claimed First Blood!", 173 "The match has begun!", 174 "Match: Initiating", 167 / 200 "is Dominating!", 202
"Unstoppable", 189 "Triple Kill", 190 "defeated", 214 "Power Core at 50%", 388 / 389 "shutdown", ... StartConversation reaches the client as conversation
event **0x2001** with the key (the same path ics already uses for victory line 0x250 = 592, which the tester heard).
So for ics: at -60 / -30 / -10 / 0 s send **0x2001 with keys 0x9C / 0xBB / 0x97 / 0xAE** (and optionally 0xAD a
moment after the start). Notice 0x10000205 (dialog enable) must have been sent first, as for 0x2039 (fase3-gx).
`[ics] announcer_events` names `match_starts_30 / match_starts_10 / match_start` can never get a 0x2039 event id;
they need a line-key path (0x2001) instead.

## 2. Keymap

### 2.1 What the files show [C]

- `Documents\InfiniteCrisis\infinitecrisis.keymap`: the two backups written by `tools/keymap.py` (22:51 and 23:54)
  are byte-identical. server.log shows client sessions 22:53:34-23:02:24 and 23:48:12-23:50:51, so the client read
  the 22:51 edit at least once and wrote the defaults back at an exit.
- MetaKeys in the file: bit 1 = Shift (0x1), bit 2 = Ctrl (0x2), **bit 3 = Alt (0x4)**, bit 4 = Win (0x8), bits 5-8
  mouse buttons.
- Default `Main` section: `Dance/Joke/Laugh/Taunt/Oath [ Old [ 0 DIK_NUMPAD1..5 ] 0x00000004 ]` (Alt+Numpad). The
  `DoNothing [ Old [ 0 DIK_1..4 ] 0x00000002 ]` lines are in **`BlockInput`** (a blocking layer), not Main. Main has
  no Ctrl+1..6 binding (Alt+1..6 SmartSelfCastItem, Shift+1..6 SmartCastItem, 1..6 ActivateItem).

### 2.2 Loader / saver [C]

Input manager `DAT_01b694b8`, vtable `0x15C4048` (`cinputmap/CInputManager.cpp`).

| vtable | function | what |
|---|---|---|
| +0x28 | `0x603570(path)` | reads the text file through the serializer at `this+0x1A0` (vtable +0x4C) into a temporary map; only if the whole parse succeeds, merges it into the live map `this+0xFC` with `0x601260(map, override=1)` |
| +0x2C | `0x603450(id)` | loads a packed default map (record lookup `0x43A9E0(id, 8, 0x25, 5)`) and merges it into `this+0xFC` with `0x601260(map, 1)` |
| +0x30 | `0x5F5C50(path)` | writes `this+0xFC` through `this+0x1A0` vtable +0x50 (text writer `0x5FBD30`) |

Startup `0x404B20`: +0x24, **+0x28 (file) first**, +0xB8, then **+0x2C(0x10000001), (0x10000002), (0x10000003),
(3)** (the defaults), sets `this+0x140`. Exit `0x4066D0`: if `this+0x140`, +0x30 (save). So the file is always
merged first and the packed defaults are merged on top.

Merge rules (`0x601260` -> per map section `0x5FFE80` -> `0x5FFD60` per binding): a binding is keyed by section +
device + control + meta (+ activation, bit 1 of the activation selects the up-list `0x5FEF50` vs down-list `0x5FEFD0`).
On a key collision with override set, the old binding is removed (`0x5FDFC0`) and the new one inserted. Nothing
removes other bindings of the same action. Consequences:
- An action may hold several bindings (the defaults themselves bind ChatTextEntry_SendToAll twice).
- A key + meta in one section holds one action; **the later merge wins, i.e. the packed default beats the file** on
  any key the default also uses. A file binding on a key the defaults do not use survives and is saved back.
- Deleting a default binding from the file has no effect: the defaults re-add it at every start (that is why the
  BlockInput `DoNothing Ctrl+1..4` and the Alt+Numpad emote lines come back).

Text parse (`0x603390`, called through `0x603940`): exactly 4 parts (Name, Devices, MetaKeys, Bindings) else "ERROR -
must have exactly 4 parts"; devices `0x5FB960`; metakeys `0x6024B0` (index 1..32, valid device); bindings
`0x600380`: each section name must be in enum list 0x46 ("invalid input map name"), no section twice ("duplicate
input map name"); each line `0x6000E0`: action name looked up in enum list 0x1D (unknown names are skipped
silently), control spec (`0x5FB770`), meta flags (`0x5F83F0`), optional control range (`0x5FCE70`). Any error in
these makes the whole file ignored (the temporary map is dropped) and only the defaults stay. No version line, no
checksum. Error strings at `0x15C308C-0x15C4EF8`.

Why the 22:51 edit was lost [P]: the first tools/keymap.py version replaced the `DoNothing Ctrl+1..4` lines, which
live in BlockInput; the defaults (merged after the file) re-bind those exact keys in BlockInput, so the emote
bindings put there were overwritten. The 23:54 version (Ctrl+1..5 in Main) uses keys no default uses in Main, so
by these rules it should survive; the Alt+Numpad lines it deletes will be re-added by the defaults each start.

### 2.3 Packed defaults and a byte-exact patch [C]

Pack `0xA0000038.rp`, record **`0x22000004`** (decompressed offset `0x12AA84`, header name string
`gmXBox360Keymap`), 16-byte binding rows `u16 device | u16 DIK | u32 meta | u32 activation (3) | u32 action DID`.
Packed meta bits are mirrored: Shift `0x80000000`, Ctrl `0x40000000`, Alt `0x20000000` (checked: Ctrl+F
ToggleFPSDisplay 0x100000C7, Alt+1..6 0x100000BE-C2, Shift+1..6 0x100000B8-BC, Ctrl+Tab RankUpPassive 0x10000089).
Emote actions: Dance `0x100000CF`, Joke `0x100000CC`, Laugh `0x100000CE`, Taunt `0x100000CD`, Oath `0x100000DB`.
No row in the record uses Ctrl+1..6.

The pack's payload is a zlib stream of **stored (uncompressed) deflate blocks** (`78 01`, compressed size 1234517 vs
1234316 data), so the data lies verbatim in the file. The 0x20000-byte block trailers are lengths, not checksums;
the header has no checksum. The only integrity value is the zlib Adler-32 at the end of the stream (inflate checks
it; updated below). Patch of the .rp file itself (file offsets; same length; verified by decompressing a patched copy
with `icserver/rp.py`, Adler check passes):

| File offset | Original | New | Meaning |
|---|---|---|---|
| `0x12B769` | `4F` | `02` | Dance: DIK_NUMPAD1 -> DIK_1 |
| `0x12B76E` | `20` | `40` | Dance: Alt -> Ctrl |
| `0x12B779` | `50` | `03` | Joke: NUMPAD2 -> 2 |
| `0x12B77E` | `20` | `40` | Joke: Ctrl |
| `0x12B789` | `51` | `04` | Laugh: NUMPAD3 -> 3 |
| `0x12B78E` | `20` | `40` | Laugh: Ctrl |
| `0x12B799` | `4B` | `05` | Taunt: NUMPAD4 -> 4 |
| `0x12B79E` | `20` | `40` | Taunt: Ctrl |
| `0x12B7A9` | `4C` | `06` | Oath: NUMPAD5 -> 5 |
| `0x12B7AE` | `20` | `40` | Oath: Ctrl |
| `0x12DD2D` | `CB EC B7 CF` | `C7 BD B6 FC` | zlib Adler-32 (big-endian) of the patched data |

(decompressed offsets of the rows: `0x12AFD0`, `0x12AFE0`, `0x12AFF0`, `0x12B000`, `0x12B010`.) Both rp folders
(`C:\Infinite Crisis Server\rp`, `C:\Infinite Crisis Steam\rp`) hold the same file (md5 b7d0c51b...). The user's
keymap file must also lose its `Alt+Numpad` emote lines (else the file keeps them); with the patch, a file edit is
no longer needed. Not checked: whether a launcher / DeltaPatch verifies pack hashes before start [G: no evidence].

## 3. Match-relevant client behaviour ics does not drive (yet)

### 3.1 Announcer lines with no match event (0x2001 only) [C for the captions]

Lines found in every pack's line tables (key, caption): 231 "Drones in 30 seconds!", 247 "Drones in 10 seconds!", 233
"Drones operational!" (table 0x2B0000A1); 241 / 248 "Power Relays operational in 30 / 10 seconds!"; 256 / 257 new /
unaligned relay operational; 443-446 relay being captured; 459-461 relay neutralized; 238 / 442 / 244 / 440 Doomsday
Device (Gotham Heights); 156 / 187 / 151 / 174 / 173 the countdown (1.1). None is in an event set, so they need
0x2001 with the key. The encounter text table 0x2B00006D also has "Drone phasing systems operational." 0x0123A295,
"Unidentified creatures are phasing into the urban jungle." 0x0EAA0EC5, "Creatures of the wastes have now spawned."
0x0251866E, "Our Power Core is under attack!" 0x0188DDDB (unreferenced by pack records: server-side texts, e.g. for
timeline banners 0x10000424 / billboards 0x100002EB, P).

### 3.2 The event sets, decoded by caption [C] (vs `[ics] announcer_events`, named by ear)

Event -> own-team line / enemy line (sets 0x4900047A shared, 0x49000D4C Crime Alley), captions from the line
tables: 8 annihilated; 10 / 15 / 17 core 25 / 75 / 50 %; 18 First Blood; 19 Relentless; 20 Ferocious; 21 Dominating;
22 Unstoppable; 23 Double Kill; 24 "{} shutdown {}"; 25 Invincible; 26 / 27 / 28 Triple / Quadra / Penta; 29
Defeat / Victory; 30 "{} defeated {}"; **31 our Top Turret under attack (303); 32 our Power Core under attack
(292); 33 Bottom Turret destroyed (307 / 309); 34 our Bottom Turret under attack (305); 35 our Middle Turret under
attack (291); 36 Top Turret destroyed (315 / 312); 37 Middle Turret destroyed (302 / 304); 40 Middle Dampener
deactivated (384 / 380); 41 our Middle Dampener under attack (382); 49 Power Relays unlocked (436 / 437); 50 Power
Relay captured (251 / 275); 52 "{} was shutdown"; 55 Power Core Turret destroyed (428 / 431); 56 our Power Core Turret
under attack (433); 58 relays unlock in 10 s (447 / 448); 61 Raider defeated (697); 63 Dampener reactivated (725 /
718); 64 Dampener reactivating in 30 s (721 / 719).**

The current defaults disagree with these captions for 11 names: turret_bot 31 (caption: top turret *under attack*;
bottom destroyed = 33), turret_top 32 (core under attack; top destroyed = 36), turret_mid 33 (= 37), dampener 34
(= 40), relays_unlocked 35 (= 49), relay_captured 36 (= 50), core_turret 40 (= 55), relays_unlock_soon 41 (= 58),
raider_defeated 49 (= 61), dampener_reactivated 50 (= 63), dampener_reactivating 52 (= 64). Either the by-ear test
log was off by one row or the names were assigned loosely; worth one more listening check before changing it.
"Under attack" events (31, 32, 34, 35, 41, 56 and the enemy-side texts 290-331, 363-383, 429-433) are never sent by
ics: the original most likely sent them when a structure took damage (with a cooldown, G).

### 3.3 Other notices/listeners in the match HUD that ics never sends [C: grep of ics/]

- `0x10000076` TimerClockSync (UI.TimerClockSync -> utils.CountdownTimer, used by billboards / objectives timers).
- `0x10000422` is the Flash-side id of UI_MissionEvent_AddTimelineBanner (fed by network 0x10000424, which ics sends); not a gap.
- `0x210A` / `0x210B` UI.DisplayDialogText forms (ics sends 0x2087 only).
- `0x100000BE` UI_AddObjective (AnnouncementsManager is dead code, so low value).
