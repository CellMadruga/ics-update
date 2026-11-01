# Cinematics, the end of a tutorial match, tutorial completion (static analysis, 2026-10-22)

Read-only analysis of InfiniteCrisis.exe (sha256 463adfff...) with Ghidra via REA (image base 0x400000, VA) and
capstone, plus the earlier server's in-game results (`icserver/finale.py`, `icserver/scorecard.py`, CHANGELOG
fase3-eo .. fase3-ff). Confidence: **C** = read in code (or confirmed in game by the old server), **P** = probable.

Related: `actor-creation-and-environment.md` (cinematic actors, binding table), `cinematics-vfx-audio.md` (the 30
cinematic records), `protocol-complete.md`, `progression-meta.md`, `account-systems-data.md` section 4,
`docs/reverse-engineering.md` "Ending a match".

## Summary

| # | Finding | Conf. |
|---|---|---|
| 1 | `0x20F5` = `u8 0 | u32 mask | fields by mask bit`; the first u32 is the **mask** (reader 0x878020 stores it at struct +0x4C). The **bit-1 field is a flags word** the cinematic manager acts on (HUD, binding check, input context, camera). | C |
| 2 | The client answers **only** notice `0x10000117`, args = `u32 cinematic DID` (args length 4). Finished, skipped, refused and failed-to-start all send the same notice; there is **no start notice and no state field** (ics' "state 4" is the args length). | C |
| 3 | A `0x20F5` is refused (notice sent at once with the new DID) while another cinematic is playing or not yet cleared, or when flags bit 1 asks for a binding check and no binding entry is the local champion. | C |
| 4 | During a cinematic the client hides the HUD itself (`GM_UI.RecvNotice_UpdateHUDVisibility(false)`) and shows it again at the end; it pushes input contexts 0x10000009 + 0x10000008 (0x10000010 with flags bit 7); input action **0x10000061 skips**. | C |
| 5 | After the end the client restores HUD, camera, input and the entities it hid; the actors were client-local copies (IIDs 0x81...). Nothing has to be re-sent for the cinematic itself. | C (client side) / P (no re-send needed) |
| 6 | The post-match "motion comic" is the **encounter's post-match movie** (`0x10000C1B`, a StringInfo naming a `vig_*.bik`), played by the end page `0xa795e0` -> `0xa724a0` once it has the match-ended notice **and** the stats `0x2045`, while `User.HasSeenPostEncounterVideo@<encounter>` is unset. No server message names the movie. | C |
| 7 | The reward screen = the scorecard (MISSION COMPLETE) + the Champion Unlocked ribbon, which the client pulls: `0x212E` -> `0x211F`, `0x2124` -> `0x2125`, claim `0x2128`. | C (in game, fase3-ff) |
| 8 | "Complete Tutorial 1" in TRAINING MISSIONS = **trainee achievement `0x40000B08` at OverallProgress 100** in `0x2120`; the unlock of the next mission/queue = `0x214B` completed encounters. Both must be sent at every login from persisted state. | C (code) / P (exact label) |

---------------------------------------------------------------------------------------------------------------------

## 1. Cinematic playback

### 1.1 `0x20F5` wire format [C]

Event `0x20F5` (exec `0x8ac050`, handler `0xa9d140` -> `0xa9cff0` when the cinematic manager `[0x1b766b0]` exists).
Reader/writer `0x878020` (struct base S; the manager keeps its copy at manager+0x38):

```
u8 0
u32 mask                                   -> S+0x4C
bit10: u32  "alt mode" A                   -> S+0x00   (0 = solo binding, !=0 = team binding, see 1.3)
bit0 : u32  cinematic DID (0x35...)        -> S+0x04
bit1 : u32  FLAGS (see 1.2)                -> S+0x14
bit2 : u32 n + n x {u32 actor key, u64 IID} -> S+0x28 list (count at S+0x30); readers 0x877E90 / 0x962AD0
bit5 : u8   bool (0/1, else error 0x80004005) -> S+0x08
bit3 : u32                                 -> S+0x0C
bit4 : u32                                 -> S+0x10
bit6 : u32  DID run on the local champion when the cinematic is skipped-all (0xa9caa0)   -> S+0x18  [P]
bit7 : u32  DID run on the local champion when the cinematic ends (0xa9cb30 -> 0xa9caa0) -> S+0x1C  [P]
bit8 : u32  transition id used before the skip-all path (0xa9c180)                     -> S+0x20  [P]
bit9 : u32  transition id played after a normal end (0xa9ce20 -> 0xa9c180)            -> S+0x24  [P]
bit11: sub-struct (0x5BCE30 / 0x6AC5C0)    -> S+0x38
bit12: u32  (== 2 -> manager+0x31, a "second" player 0x6a5ef0 stopped at the end)     -> S+0x48
```
Field order on the wire is the order above (mask, bit10, bit0, bit1, bit2, bit5, bit3, bit4, bit6..9, bit11, bit12).
`0xa9caa0(did)`: when did != none, runs it on the local champion/player through 0x588A00 with property
0x1000050A and scriptlet-table id 0x100003EA (a script/effect start). ics sends `mask 1 + DID`: no flags, no bindings.

### 1.2 FLAGS (bit-1 field, manager+0x4C) [C for the effect, P for the names]

| Bit | Effect in the client |
|---|---|
| 0 | HUD: hide/show is done also when "skip all" (manager+0x36) is set (`0xa9ceb0` / `0xa9cb30`: `if (flags&1 || !skipAll) UpdateHUDVisibility(...)`) |
| 1 | Binding check (`0xa9c610`): without a binding entry for the local champion the cinematic is refused |
| 6 | Clear means: camera component `[0x1b73518]+0xdc` gets +0x39 = 0 at start (camera taken over) |
| 7 | Input context 0x10000010 instead of 0x10000008 (P: the one without the skip action = unskippable) |
| 10 | Passed to the player as "do not scale the camera/fov" (`0xa9c200`) and to 0x6A6540 |

### 1.3 Bindings [C]

`0xa9c610(A, S)` (only when flags bit 1 and the list is not empty): the local champion's IID comes from
`0x85c1f0`.
- A == 0: the entry whose IID equals the local champion gets key **1**; none -> refuse.
- A != 0: every entry gets a key: the local champion 1, the others (valid IIDs, `0x5bbe70`) 0x10000001..0x10000005 in
  order; more than 5 -> refuse.

So the server sends `{key 0, champion IID}` and the client writes the key itself. Without flags bit 1 the keys
are used as sent (actor variable `1` / `0x10000001..5`, `cinematics-vfx-audio.md` 6.1). Unbound "needs binding"
actors are skipped (actor-creation note).

### 1.4 Start (`0xa9cff0`) [C]

1. No local player -> nothing. Manager DID (manager+0x3C) != none or manager+0x30 (playing) set -> notice
   `0x10000117(new DID)` at once (refused).
2. Copy the message (0x877F50); binding check (1.3); on failure `0xa9ceb0(did, 0)` + notice.
3. `0x6A6540(did, bindings, flags bit10, S+0x48 == 2)` (stores the DID at +0x88, loads the 0x3E record, spawns the
   actors 0x6A60A0). Success -> registers two listeners (`0x68ebc0` with 0x186f6d8 / 0x186f6dc), playing = 1.
4. `0xa9ceb0(did, ok)`:
   - fail: unregister, reset, notice `0x10000117(did)`;
   - ok: push input context 0x10000009 (priority 1000); `0x963fc0(local champion, 1)` (script call 0x2370006 on
     the agent: "in cinematic" state, P); `0xa9bfe0` (reads three scene variables of the local champion);
     `0xa1a250(4)` + `0xa62c00(4)` (UI/HUD mode 4, P); `0xa9c200` (camera); `0xa9c490(1)` **hides world entities**
     (property 0x90F on entities that match the mask 0x10000B5B / manager+0x48, or `0x9d0180`); `0xa9e430(1)`
     (global "cinematic playing" flag 0x1b76952); `UpdateHUDVisibility(false)` (`0x8a7050`); push input context
     0x10000008 / 0x10000010 (priority 0x3E9). If "skip all" (manager+0x36) is set: skip at once (`0xa9cd90`).

### 1.5 End, skip, failure [C]

- **Skip by the player:** input listener `0xa9bf40` (vtable 0x1607E50) on input action **0x10000061**, unless a UI
  dialog holds it (`[0x1b758dc]+0x48` and `0xac5330`): sets manager+0x34 (skipped) and stops the player
  (`0x6a6670(0)`); during an end transition (manager+0x33) it cancels the transition instead.
- **Player listener** (vtable 0x1607E70, the manager at +0x2C): slot 2 `0xa9ce20(did)` = the scene finished
  (natural or skipped): when not skipped and the bit-9 transition can start, waits for it (`0xa9cd00` when it
  completes); else notice + `0xa9cb30`. Slot 3 `0xa9ce70(did)` = stopped/aborted: notice + `0xa9cb30`.
- **Skip all** `0xa9d120` (set manager+0x36 = 1 and skip the current one) is called only by the UI-state action
  `0xab46c0` (vtable 0x15FA118), which also touches the timeline (`0xa13b20`) and re-applies the environment
  (`0xa8f890`). manager+0x36 is cleared only by the manager constructor `0xa9c8c0`: once that action ran, **every
  later cinematic in that world ends at once** (P: the action belongs to a "match started / gameplay" UI state).
- **Cleanup `0xa9cb30`:** stop the second player (bit12), `0x688160(1)`, pop the input contexts, `0xa9e430(0)`,
  `0xa9c490(0)` (hidden entities back), `UpdateHUDVisibility(true)` (same condition as at start), camera +0x39 = 1,
  `0x963fc0(champion, 0)`, run the bit-7 DID, `0xa1a250(4)/0xa62d00(4)` (UI mode back), reset the struct
  (0x877FD0), unregister.

### 1.6 Notice `0x10000117` [C]

Built by `0x8919c0(player, did)`: event 0x2 to the local player (IID at player+0x100), body
`u32 0x10000117 | u32 4 | u32 DID`. Senders: `0xa9cd00`, `0xa9cd90`, `0xa9ce20`, `0xa9ce70`, `0xa9ceb0`, `0xa9cff0`.
The server cannot tell finished from skipped from refused; a notice arriving within a few hundred ms of the `0x20F5`
is a refusal (P). ics `session.py` unpacks `state, did` from body+4: "state" is the args length (always 4).

### 1.7 What the server must do [P unless marked]

- Wait for the notice before the next step; never send a second `0x20F5` before it (it is refused) [C].
- Do not re-show the HUD for the cinematic (the client does it) [C]; the HUD elements 0x213D are a separate,
  server-driven set and are untouched.
- The real entities are only hidden and their visuals copied; the client moves nothing of the server's. Re-sending
  the champion is only needed when the server itself moved it (scene scripts that teleport).
- Bind the champion when a scene has a player actor: mask `0x7` (DID, flags, bindings), flags `0x2`, one entry
  `{0, champion IID}`.

---------------------------------------------------------------------------------------------------------------------

## 2. End of a tutorial match

### 2.1 What the client does [C]

1. Notice **`0x1000000E`** (reader 0x941750): `u32 winning team | u32 player team | f32 seconds | u32 tier | f32
   target time`. End page `0xa809e0`: stores the team, UI event **0x21**; that UI state's action `0xab52a0`
   (`UI_ExitWorldLoadWrapper`, 0x1000018F) **leaves the world at once** (teardown 0xa99b60, client sends `0x12D`).
   So VICTORY must be shown *in the world before* this notice: `0x100002EB` ShowAnnouncement type 9 (MatchWin) +
   `0x2038` during the ending cinematic (old server: 18.5 s into `0x35000025`).
2. **`0x2045`** end-of-match stats `u8 0 | u32 n | n x entry (0x8776a0) | f32` (exec 0x8b2bd0 -> 0xa91bf0). The end
   page `0xa795e0` fills itself only when its flags +0x1A9 and +0x1AA are set and the entry count (+0xE4) is not 0;
   then it calls **`0xa724a0(encounter)`**. Tutorials (`0x10000D0B` = 4 on both tutorial templates) skip the
   scoreboard grid.
3. **Movie** `0xa724a0`: name = encounter template `0x10000C1B` (`0x8596b0`; on `0x49000991` a StringInfo, table
   0x2B0000D1 token 0x02AB0499 -> a `vig_*Vignette.bik`, the "Batman's story" the tester saw). If it is set and
   `User.HasSeenPostEncounterVideo@0x%08X` (encounter) is false: save the preference (0xa6cc20; the client then
   sends `0x216E`) and play it (`0x897ac0` = `GM_Encounter.RecvNotice_PlayEndOfMatchEncounterMovie`, Bink from
   `video\`). If the encounter has no movie (or it was seen) and the current trainee achievement (trainee list
   entry `[mgr+0x5C]-1`) has TimesCompleted 1 and its own `HasSeenPostEncounterVideo@<achievement>` is unset, it
   plays a movie named by string table 0x10000027 key 0x0E2C7CEE instead (P: a trainee intro). To replay the
   movie every time, the server resets the preference with `0x216A` before the notice.
4. **Scorecard / MISSION COMPLETE** shows only with all its data: `0x2190`, `0x2081`, `0x2080`, `0x20B9`, `0x2104`,
   `0x2188`, `0x2090`, `0x219F`, `0x219E` (`icserver/scorecard.py scorecard_bundle`). [C in game]
5. **Reward (Champion Unlocked)**: on the end page the client sends `0x212E` -> answer `0x211F` (empty `00 00 00`);
   the UI asks `0x2124` -> answer `0x2125` (reward set `0x40000B07`, item Gaslight Batman `0x40000086`, source
   1 = achievement, instance id unique). A `0x2125` that arrives while in the world is lost. Continue sends `0x2128`
   (claim); the client then plays the showcase movie itself (achievement `0x10000BCD` / champion `0x10000C58`).
   [C in game, fase3-ff]
6. Closing the end page sends `0x20A6`; home screen. `0x2021` (exit lobby) is not needed (the client already left)
   and closing the game connection after `0x12D` causes a "connection problem" teardown. [C in game]

### 2.2 Recommended server sequence (Tutorial 1) [C: confirmed by the old server unless marked]

| When | Send |
|---|---|
| ending cinematic `0x35000025` + ~18.5 s | `0x100002EB` ShowAnnouncement type 9 (source/target team = player team) + `0x2038`; objective cleared (`0x2009`) + tracker off (`0x2075`) |
| cinematic + ~22.6 s (just before its end) | `0x216A` `User.HasSeenPostEncounterVideo@0x40000991 = False` (optional replay); notice `0x1000000E (team, team, secs, 0, 0.0)`; `0x214B` completed encounters (with 0x40000991); `0x2120` trainee progress (0x40000B08 current 1 / previous 0, TimesCompleted 1); scorecard bundle (2.1 step 4); keep the `0x2125` pending |
| + ~6 s | `0x2045` stats (so VICTORY/the banner has time; starts the movie) |
| client `0x212E` / `0x2124` / `0x2128` | `0x211F` empty / pending `0x2125` / mark claimed |
| client `0x12D` | match over; keep the game connection open; next referral replaces it; `0xEB` again before the next match's lobby data |

Gaps in `ics` today: `victory()` sends only `0x1000000E`; `0x214B`, `0x2045`, `0x2120`, the scorecard bundle,
`0x216A` and the `0x212E`/`0x2124`/`0x2128` answers exist only in `icserver/` (builders already in
`ics/messages.py`: `end_of_match_stats`, `completed_encounters`, `exit_lobby`, `server_preferences`).

---------------------------------------------------------------------------------------------------------------------

## 3. How the menu knows a tutorial is complete

- **Training Missions checkmarks** [C code, `scorecard.py` notes]: `0x2120` (ser 0x849540, exec 0xa870e0 ->
  0xa839e0) stores the achievement progress; Flash `SetAchievementObjectiveData`; the TraineeAchievements list
  (prop `0x10000BAC` of client config `0x48000E76` = `0x40000B08, 0x40000BD5, 0x40000C59, 0x40000EB9, 0x40000EBA`,
  no server data) is shown by `0xa43530`. A mission is done when its OverallProgress is 100 (objective current >=
  target 1); button i unlocks when every previous one is 100; MISSION COMPLETE's NextChallenge = the first < 100.
  Entry: `u32 DID | u32 DID | u32 TimesCompleted | u64 TimeValid | u32 n | n x {u32 objective index 1, u32 current,
  u32 previous, u32 0, u64 last updated, u8 has progress}`.
- **Screen visibility** [C]: ProtectorAdvancementStatus (`0xa70db0`) is computed only after a `0x2120`: 3
  FirstTimePlayer (TimesCompleted(0x40000B08)=0, level 1), 2 Trainee (TimesCompleted(0x40000EBA)=0, level < 5), else
  1 Player. The trainee screens (and their light packs) need status 2/3: **account level < 5** in `0x2080`
  (ics default `account_level` 30 = veteran).
- **Queue unlock** [C]: `0x214B` `u8 0 | u32 n | n x u32 encounter | u32 last played | u32 flags`
  (`GM_Encounter.RecvNotice_UI_CompletedEncounters`, 0xa30cd0); Tutorial 2 (`0x49000A81`, prerequisite
  `0x10000B68` = 0x40000991) stays locked until 0x40000991 is in the list.
- **Movie seen** [C]: `User.HasSeenPostEncounterVideo@<DID>` lives in the client's `UserPreferences.ini`; the
  client reports it with `0x216E`; the server can override it with `0x216A`.

Persist per account (as `data/progress.json` does for the old server): completed encounters, trainee achievement
TimesCompleted, claimed reward sets. Send at every login: `0x214B` (before `0x2080`), `0x2120` with the trainee
entries (done ones current = previous = 1), `0x2080` with the account level.

## 4. Open points

- Names/meaning of 0x20F5 fields bit3, bit4, bit5, bit11 and the 0x963fc0 script call 0x2370006.
- Which UI state runs the skip-all action `0xab46c0` (vtable 0x15FA118).
- The resolved text of StringInfo 0x2B0000D1 / 0x02AB0499 and of string table 0x10000027 key 0x0E2C7CEE.
