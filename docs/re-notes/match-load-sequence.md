# Match load sequence: from the lobby launch to "load complete" (2026-10-25)

Static analysis of InfiniteCrisis.exe (image base 0x400000, every address a VA; decompilation in `re-work/decomp`,
disassembly of the read-only exe with capstone) plus logs/server.log and logs/traffic.log of the 17:46-17:54 session.
Tags: **C** = confirmed in code or logs, **P** = probable, **G** = guess, **O** = open. Builds on
`second-match-load-hang.md`, `map-loading-deep-scan.md`, `full-maps-world.md` 1, `full-protocol.md` 4.3 / 4.5 and
reverse-engineering.md ("Packs after a match", "Champion select -> costume countdown -> loading").

## 1. The objects involved (C)

| Object | Global | Role |
|---|---|---|
| gmConnectionManager | `[0x1b763c0]` | +0x70 load gate bits (1 = game connection state 4, 2 = 0x20AF received, 4 = lobby not loading, 8 = load started), +0x74 u32 of 0x20AF, +0xA0 map pack (encounter 0x10000406), +0xA4/+0xAC 0x20AF champion list, +0xB4/+0xBC 0x20AF pack list, +0xC4 encounter, +0xC8 last reported percent |
| CLobbyManager | `[0x1b77068]` | +0x4BC room id (set by 0x2028 `0xabde80`), +0x4C8 / +0x4C9 lobby-RP tick registered, +0x4CA VerifyAndLoadAllNeededRPS running, +0x4CB m_bForceOverrideNoLoading (set by 0x20AF), +0x4CC transition called (0x2016), +0x1C0 everyone loaded (0x206D), +0x230 skin-picker choice, +0x234 own champion |
| ResourcePackLoader | `[0x1b75808]` | one request queue (+0x48 head, +0x50 count, 0x2C-byte requests); lists: +0x04 parent RPs (count +0x14 pending), +0x18 match data (+0x28 pending), +0x34 lobby (+0x44 pending); +0x58 "tick registered" |
| Pack table | `0x9d30f0()` | +0x04 0x28-byte entries (pack id at +0x1C, flags at +0x10), +0x0C count; `0x9d33c0(id)` = index or -1 (-1 also for id 0xFFFFFFFF) |
| gmCCharacterManagementSystem | `[[0x1b758d4]+0x64]` (= `0xa1a040()`), ctor `0xa75730`, vtable `0x160498c` | holds **both halves of 0x20ED**: +0x14 / +0x1C the champion groups (part 1), +0x24..+0x30 the hash of per-variant metadata (part 2) |
| match player info | `[[0x1b758d4]+0x68]` (= `0xa1ba20()`) | +0x14 the cumulative loading percent (`0xab7bf0` adds), +0x6C encounter |

### 1.1 Request record and queue (C)

A request (built by `0xa09e50`, `0xa09f90`, `0xa0a050`, `0xa0a120`, `0xa0a1e0`, `0xa09230`) is
`+0 u8 | +4 u32 1 | +8 list<u32 pack> | +0x18 start(req) | +0x1C done(status) | +0x20 final callback | +0x24 name
string | +0x28 sequence`. It is appended (`0xa09980`); only the head runs. `0xa09b90` / the per-frame tick `0xa09cf0`
do, for the head: `0xa08960(req)` = **if every pack id of the list is in the pack table, call done() now**; else
`start(req)`; if start returns 0, register the tick (`0xa3cb70`) and **try again next frame**. A start function
(`0xa08e50`, `0xa08e90`, `0xa092c0`) calls `0x9e3e80(new list, old list)` and registers one done() callback per pack
that had to be loaded (`0x9d7570`), adding that number to the list's pending counter; it returns 0 when
`0x9e3e80` returned -1 or when **no pack needed loading**.

`0x9e3e80` (C): sorts both lists (`0x9d43a0`, output lists end with -1), releases old-only packs (`0x9e3e20`),
then for each new pack `0x9dd120`: already in the table -> counted as present; else looked up in the pack directory
(`0x9da330`) and registered; a pack that cannot be resolved counts as a failure. Return: 1, or **-(number of
failures)**. Callers test `!= -1`, so **exactly one** unresolvable pack makes the whole request return 0; two or
more are skipped silently.

### 1.2 0x20AF (handler 0xa99f00) (C)

Wire: `u8 0 | u32 (-> +0x74, ics 0) | u32 n + n x u32 champion DIDs | u32 m + m x u32 pack ids | u32 encounter`
(17:52:25 hex: 10 DIDs, 23 packs, 0x40000B6C). The handler copies both lists, sets +0xC4, lobby+0x4CB = 1, gate bit 2;
**if lobby+0x4CA and +0x4C8 are clear** it sets bit 4 and calls `0xa99e20`; otherwise the lobby tick `0xabd9c0` does
it when its own load ends ("m_bForceOverrideNoLoading is true, now LoadMatchDataAndLevel"). It never looks at the
lobby slots (C: `0xa99f00`, `0xa99e20`, `0xa99370`, `0xa99460`, `0xa09f10`, `0xa09de0` read only the two 0x20AF
lists, the encounter and the 0x20ED table).

### 1.3 0x20ED part 2: the per-variant metadata the loader reads (C)

Serializer `0x83bcf0 -> 0x877a80 -> 0x877080 -> 0x876750 -> 0x866240`: `u8 0 | cint n | n x (u32 variant | 8 x u32
f0..f7 | u8 | u32 f9 | StringInfo name)`. Hash entry = `{next, key, f0..f7, u8, f9, name}`; accessors (all on the
system object):

| field | entry dword | accessor | read by | ics value (`_meta_entry`) |
|---|---|---|---|---|
| f0 | [2] | `0x866420` | **LoadMatchData `0xa99460`** (no -1 filter), `0xa1a230` | **0xFFFFFFFF** for every entry |
| f1 parent pack | [3] | `0x866480` | LoadParentRPs `0xa99370` (-1 skipped) | parent pack |
| f2 heavy pack | [4] | `0x866540` (`0xa0a5d0`) | VerifyAndLoadAllNeededRPS `0xabc620`, Scorecard heavy-only `0xa3e180` (no -1 filter), `0xabb870` | heavy pack |
| f3 light pack | [5] | `0x8664e0`, `0xa3e240` | lobby light packs (skin picker, slots) | light pack |
| f4 wallpaper pack | [6] | `0xa23b30` via `0xa253b0` | `0xabc620` (added **without** a -1 check), `0xa3e180` | wallpaper pack |
| f5 | [7] | - | - | pregame heavy record |
| **f6** | **[8] = entry+0x20** | **`0xa25430`** | lobby slot handler `0xabd0a0` -> `0xab9690` (pick voice line, property 0x10000575 of that record) and `0xabbb90` (slot arrays +0x108) | light record (base `id`, costume `light`, e.g. 0x48000AC2 in 0xA000021A) |
| f7 | [9] | `0x8665a0` | - | heavy dbpc |
| f9 | [11] | **`0xa25510` = vtable +0xC** | slot handler `0xabd0a0` (to the Flash slot update `0x8f1ed0`) | grid icon for a champion, **0 for a costume** |

Defaults when a variant is missing (`0xa253b0`): f0..f4 = -1, f5..f9 = none.

## 2. Loading-percent steps (C unless marked)

`0xa964b0(n)` adds n (only while lobby+0x4BC != 0), reports it with 0x20D5 (`0x889bc0`) when the value changed, and
raises UI event 0x33 + notice 0x10000204 once lobby+0x1C0 (0x206D) and connection +0x78 are set. Every direct caller:

| reached | +n | function | what finished | needs from the server |
|---|---|---|---|---|
| (not seen) | 5 | `0xa9aaa0` (connection listener `0xa9bcd0` case 4) | game connection ready: gate bit 1, tries `0xa99e20` | referral, welcome, ServerSwitch |
| **10** | 10 | `0xa99460` LoadMatchData (= final callback `0xa99ef0` of LoadParentRPs) | the packs holding the 0x20AF champion DIDs (f1) are in | 0x20AF, gate bits 1+2+4, 0x20ED f1 |
| **20** | 10 | `0xa97340` (start `0xa09b30` of the level request `0xa09de0`, queued by `0xa09f10` "ResourcePackLoader::OnCharacterSwapComplete") | **every pack of LoadMatchData** (f0 of each champion + the 0x20AF pack list) has called done() and the match-data counter +0x28 is 0 | packs that load |
| 25 | 5 | `0xa087c0` (progress callback of the map load `0x7e2ce0`, map pack +0xA0) | map pack load started (P: or `0xa9aaa0`) | encounter 0x10000406 |
| **35** | 10 | `0xa097a0` (done of the map load) | map pack loaded; **sends 0xCC level loaded** (`0x692a80`); failure -> error 0x10000014 (`0xac8620`) | - |
| 55 | 20 | `0xa96af0` (gmConnectionManager listener, vtable `0x1606f30`) (P: local player object ready) | player object created as the local player | 0xEB before the match (`second-match-load-hang.md`), player bundle |
| 75 | 20 | `0xa0a570` (char-management listener, vtable `0x1604908`) | the player's controlled agent changed to a non-zero IID different from player+0x100 (P: AgentControlledByThePlayerChanged) | the link bundle (0x100000CF / 0x100005E8) |
| 80 | 5 | `0xab5200` (script native, table `0x15fa030`) | the local player's position is in a loaded cell and the local champion (`0x85d670`) passes `0x409760` | champion bundle with a position in a loaded landblock |
| 95 | 15 | `0xa96cf0` (vtable `0x1606e48`) | local player + char-system +0x100 + connection +0x78: **sends notice 0x1000015E load complete** (`0x884010`); view-match adds 25 | - |
| (100) | 5 | the remaining +5 (`0xa9aaa0` or `0xa087c0`, whichever did not make 25) | - | - |

Logs 17:47 (Crime Alley, C): 10 at 07.67 (0.14 s after 0x20AF), 20 at 08.51, 25 at 08.59, 35 at 08.64 + 0xCC; objects
at 14.63 -> 0x211B / 0x207A -> 55 at 14.79; link bundle 16.64 -> 75, 80 at 16.65; 95 at 21.56 + 0x1000015E. ics never
sees 100: the first +5 of the session arrives before the counter is reported (P), harmless (UI event 0x33 depends on the
flags, not on 100).

## 3. The chain, step by step (C)

1. **Lobby -> launch.** 0x204B (handler `0xabd420`) locks the own slot, clears +0x230 and runs
   VerifyAndLoadAllNeededRPS `0xabc620` (lobby list +0x34: light packs of my base champion's costumes (`0xab93a0`
   -> `0xa3e240`), the slot champion's f2 + f4, the skin pick's packs, the encounter template pack `0x857e60`).
   Each own-slot 0x2029 (`0xabd0a0`) does the same while lobby+0x4CC == 0 and the slot is locked; one at a time
   (+0x4CA "Already Loading"); its callback `0xabba90` re-verifies, and with +0x4CB set goes to `0xaba750` (tick).
2. **0x20AF** (1.2). Gate `0xa99e20` (bits 1, 2, 4 all set, bit 8 clear, once per match): world reset `0xa960e0`,
   encounter template `0x8535d0` (ruleset 0x1000028A, map pack 0x10000406), **LoadParentRPs `0xa99370`**: releases the
   previous match-data list (`0xa08860`) and parent list (`0xa08810`), then queues the packs of the champion DIDs (f1).
3. **10 %**: LoadParentRPs' final callback runs **LoadMatchData `0xa99460`**: list = f0 of every 0x20AF champion
   (deduplicated, -1 kept) + the whole 0x20AF pack list -> `0xa09f90` (start `0xa08e90`, done `0xa09f10`).
4. **20 %**: when the match-data counter reaches 0, `0xa09f10` queues the level request `0xa09de0` (list = {-1}); its
   start `0xa09b30` adds +10 and starts the map load `0x7e2ce0(map pack, u32 of 0x20AF)` with progress `0xa087c0`
   (+5) and done `0xa09b10 -> 0xa097a0` (+10, **0xCC**).
5. **35 -> 95**: the world: player object local (0xEB), link, champion in a loaded cell, then 0x1000015E.
   0x2016 (`0xab9080`, UI event 0x23 to the loading screen) and 0x206D (`0xab84f0`, lobby+0x1C0) only drive the UI.

## 4. The 17:52 failure (Gotham Heights 0x40000B6C, costume 0x4000080C)

Facts (C, logs): second match of the session; 0xEB re-sent at 17:52:06.42; costume picked during the costume countdown
(0x20E4 at 11.770) and answered with my slot naming the base 0x4000047D (fase3-hu `lobby_slot_base_for_costume`);
0x20AF at 25.190 (champions 0x4000080C + 9 bots, 23 packs, the costume model pack 0xA000021B last) with 0x2016 and
0x206D; **10 % at 25.648, never 20 %**; the server's 10 s fallback sent bots, structures, notices and the player while
the client was at 10 % (36.94); the client still answered 0x211B (its player became local) and quit at 17:54:37. The
same map with the same costume loaded at 16:24 while the slot named the costume (test-2026-10-25-1612.md, C).

What the client was waiting for (C): **the done() callbacks of LoadMatchData** (step 3). 10 % proves LoadParentRPs
finished; 20 % is the first thing that runs after every match-data pack reported in.

Why the slot DID matters (C for the paths, P for the trigger): nothing in the match load compares the slot with 0x20AF
(1.2), so the mismatch acts only through the **shared pack table and request queue**. With the slot naming the base,
the lobby requests of step 1 load and keep the base model / wallpaper / light packs (0xA0000151 / 0xA000014E /
0xA000014F) and release the costume's again after the client's own skin-pick load (pick -> +0x230 = costume -> load;
our 0x2029 -> +0x230 = none -> the next verify drops 0xA000021B / 0xA0000219). LoadMatchData then has to load the
costume model pack fresh, next to the base model pack that carries many of the same DIDs (fase3-hc), while every
other pack it names is already resident (the parents from LoadParentRPs, the light packs). Which of the conditions of
section 5 then held is **not decidable statically** (O): (a) its only fresh loads failed or never called back, or
(b) nothing was left to load and the -1 that ics puts in f0 kept the "all present" shortcut from firing (5.1).
diag section 8 settles it in one run. The revert (slot names the costume again) removes the trigger; 5.1 / 5.2 remove
the class.

## 5. Every condition that stops the load the same way

### 5.1 LoadMatchData (10 % -> 20 %) never completes (C mechanism)
1. **All its packs already resident while the list holds an id the table does not know.** ics sends f0 = 0xFFFFFFFF
   for every champion, so every LoadMatchData list contains -1: `0xa08960` can never succeed and the request only ends
   through per-pack done() calls; if nothing needs loading, `0xa08e90` returns 0 every frame forever. Happens whenever
   every named pack is held by another list (parents, lobby, start-up, a previous request).
2. **Exactly one pack id unresolvable** (not in the player's pack directory, 0, a typo, a pack of another build):
   `0x9e3e80` returns -1 -> start returns 0 forever. (Two or more are just skipped.)
3. **A pack load that fails**: done() with status 0 -> error 0x10000014 and return before the counter decrement
   (`0xa09f10`, also `0xa09840`, `0xa097a0`).
4. **The queue head is another request stuck by 1 or 2**: the lobby's VerifyAndLoadAllNeededRPS (f4 added without a
   check; f2 of the slot champion; the encounter template pack) or `0xa3e180` Scorecard heavy-only (f2 unchecked).
   A slot champion missing from 0x20ED part 2, or a meta entry with pack 0 / a bogus id, does it. Before 0x20AF this
   keeps lobby+0x4CA set and 0x20AF is deferred forever (no 10 % at all); after it, LoadMatchData waits behind it.
### 5.2 Before 10 %
5. Gate bit 1 missing (game connection never reached state 4), bit 4 (lobby load running and its tick never ending:
   item 4), or bit 8 already set (a second 0x20AF in the same match does not restart the load: it only replaces the
   lists, which LoadMatchData then reads while the parents loaded were the first list's) (C).
### 5.3 Later steps
6. 20 -> 35: map pack (0x10000406) not loadable -> error 0x10000014; a second zone pack in 0x20AF (config note,
   2026-10-23) (C path / P cause).
7. 35 -> 55: no local player (0xEB not re-sent after a teardown) (C, `second-match-load-hang.md`).
8. 55 -> 75: no link to the champion (0x100000CF) or the same IID as before (P).
9. 75 -> 80: the champion outside a loaded cell (`0xab5200`) (C code, P meaning).
10. 80 -> 95: char-system +0x100 or connection +0x78 not set (O who sets them; ics reaches 95 every time).

## 6. Message sequence: original (P from the client) vs ics (C from the logs / code)

| # | Original server (what the client needs) | ics today | Verdict |
|---|---|---|---|
| 1 | 0x2028 room created (sets lobby+0x4BC), referral, welcome + ServerSwitch, 0xEB if a match ran before | same (0xEB in `ev_connect_to_lobby`) | ok |
| 2 | 0x204C + 0x2029 slots; picks answered with the **picked variant** in 0x2029 | slot names the costume again (`lobby_slot_base_for_costume = false`) | ok after fase3-hv |
| 3 | 0x204B launch warning (f64 times) | same | ok |
| 4 | at the launch: 0x214B (optional), **0x20AF** naming champions that are all in 0x20ED part 2 and packs that exist | same; f0 of 0x20ED = -1 makes 5.1.1 possible; packs not checked against the install | fix 7.2, 7.3 |
| 5 | 0x2016 (UI 0x23) after 0x20AF | same batch | ok |
| 6 | 0x206D when **every** player is loaded (sets lobby+0x1C0; with it the client enters at its own 100 %) | with 0x20AF | harmless with bots (P); send it when all humans sent 0x1000015E in PvP |
| 7 | 0x2031 percents as players report | same, bots 100 | ok (display only) |
| 8 | **after 0xCC level loaded**: 0x4 bundles 0xF2: player object (local, with 0x956 / team) and champion, 0x42 vitals | objects when percent >= 15 and 4 s, **or after 10 s at any percent** (`objects_max_wait`); 0xCC ignored (`ev_silent`); in a 5v5 the mode layer also sends 9 bot champions, structures, captures, 0x10000109 / 0x100004FB / 0x100002AF / 0x100002B1 / 0x1000005B **at 10 %** (17:52:35.6-36.9) | too early (objects queue per landblock; nothing to gain before 0xCC) |
| 9 | link bundle (0x100000CF / 0x100005E8 to the champion) -> 75 % | 2 s later (`link_delay`) | ok |
| 10 | client: 0x211B, 0x207A, 0x2, 0x20D3, 0x213A, 0x2139, notice 0x1000015E, 0x10000204 | handled / silent | ok |
| 11 | after 0x1000015E: 0x100001D3 as a change (map manager, shop), 0x10000205 dialog on, HUD, match clock 0x10000109, timeline 0x100002AF / B1 | after load complete (+ exe caves M/N/S/T) | ok; timeline / clock / scoreboard should also wait for load complete in the mode layer |
| 12 | 0x1000000 time packet on the game connection (< 60 s) | every 2 s | ok |
| 13 | client 0x201A (empty, after 0x100001D3 reaches the map manager) | not handled | O what the original answered |

## 7. Portrait in champion select with the slot naming the costume (item 4)

- The value `0xabd0a0 -> 0xa25430` reads at entry +0x20 is **f6 of 0x20ED part 2** (the light presentation record,
  0x48...), not a base DID; it feeds the pick voice line (`0xab9690`, property 0x10000575) and the slot array +0x108
  (C). ics fills it correctly for costumes (s["light"]; 0x48000AC2 is in 0xA000021A, C).
- The **variant -> base map** is `0x85e010` on **0x20ED part 1** (system +0x14: per champion a group of 5-dword items,
  the first one the base): any member DID returns the group's first DID (C). ics's groups list the base first, then
  its costumes (C).
- The slot's **icon** is `vtable+0xC = 0xa25510` = **f9** of the variant's 0x20ED part 2 entry, passed with the base
  (`0x85e010`) to the Flash slot update `0x8f1ed0` (C reads; P that f9 is the team-column portrait). ics sends **f9 = 0
  for every costume entry** (`_meta_entry(..., 0, c["name"])`), the base gets `grid_icon`: exactly the 16:12 symptom
  (portrait gone, "Player" only, as soon as a costume is picked; loading-screen art right) and why naming the base
  "fixed" it.
- **Fix**: send each costume's own grid icon (`costume_info[*].grid_icon`, e.g. 0x13001652 for Shattered Light) as f9
  of its 0x20ED meta entry; keep the slot naming the costume. No change to 0x2029.

## 8. Diag plan (rva = VA - 0x400000)

`--load` breakpoints: 0x699f00 (0x20AF: lobby+0x4CA / +0x4C8), 0x699e20 (+0x70), 0x699460 (LoadMatchData: list
count), 0x608e90 (start of match data: log `0x9e3e80` result and local_8 at return 0x60890f / eax), 0x609f10 (done:
status [arg+4], counter [[0x1b75808]+0x28]), 0x609cf0 / 0x609b90 (head request: **name string [head+0x24]**, pack ids
[head+8], count [head+0x10]), 0x5dd120 (pack lookup result per id), 0x6097a0 (map loaded), 0x6964b0 (every percent
add, arg), 0x6bc620 / 0x6bba90 (lobby verify start / end). Expected in a hang: the same request name at the head
every frame with start returning 0.

## 9. Server changes (ranked)

| # | Change | Why | `[ics]` key (default) |
|---|---|---|---|
| 1 | **f9 = the costume's grid icon** in 0x20ED part 2 | champion-select portrait with the slot naming the costume (7) | `champion_data_costume_icon = true` |
| 2 | **f0 = a real, always-resident pack** (the champion's parent pack f1; already loaded by LoadParentRPs) instead of 0xFFFFFFFF, for champions and costumes (the skills pseudo-entry too) | lets LoadMatchData finish through the "all present" shortcut; removes 5.1.1 | `champion_data_match_pack = "parent"` ("none" = 0xFFFFFFFF as before) |
| 3 | Check every pack id of 0x20AF (and of 0x20ED f1-f4) against the player's rp folder before sending; drop 0 / unknown ids and log them; never exactly one unknown id | 5.1.2, 5.1.4 | `enter_match_check_packs = true` |
| 4 | Create the objects on **0xCC level loaded** (35 %); `objects_max_wait` only as a fallback counted from 0xCC; the mode layer's world (bots, structures, notices) after the player bundle | nothing before the level exists (6 #8); 17:52 sent everything at 10 % | `objects_on_level_loaded = true`, `[timing] objects_max_wait` (10.0, now from 0xCC) |
| 5 | Log a load watchdog: no 0x20D5 progress for 20 s -> one line with the last percent and the step it waits for (table 2) | the next report names the step without diag | `load_watchdog_seconds = 20` |
| 6 | Keep 0x20AF to one per match (no resend after it was sent: bit 8 makes the second one half-applied, 5.2) | 5.2 | `resend_enter_match_on_pick` (true) -> only before the first 0x20AF |
| 7 | 0x206D when every human player has sent 0x1000015E (PvP); now with 0x20AF | 6 #6 | `all_loaded_when_everyone_loaded = true` |
| 8 | Match clock / timeline / scoreboard notices after load complete, not at object creation | 6 #11 | `mode_notices_after_load = true` |

Record the outcome in the catalog (`network_events.tsv`: 0x20AF, 0x20ED, 0xCC, 0x20D5 rows), reverse-engineering.md
and CHANGELOG with the build that carries these keys.

## 10. Open

- Which branch of 4 held on 17:52 (diag 8).
- Who sets char-system +0x100 and connection +0x78 (the 95 % step's conditions) and the meaning of the 0x20ED u8.
- What f0 held in the original data (P: a match-time pack per champion; the parent pack is the safe stand-in).
- 0x201A: what the original answered.
