# Minion aggro indicator, recall streaks, score-screen rewards panel (fase3-io, 2026-10-29)

Tester report 2026-10-29 21:10 (run 21:03-21:10, Crime Alley v AI, AGL vs Gaslight Batman, build fase3-in; screenshots
of the original game 74 / 75 / 79). Tags: **C** confirmed (data words, decompiled exe, Flash AS2), **P** probable,
**O** open. Data read with `ics.gamedata` from the install's packs; exe = the Ghidra decompile in `re-work/decomp`
(static base 0x400000); Flash = `re-work/ui-as2/c_a00000d0_02189b08`.

## 1. Minion aggro indicator

Report: enemy minions that turn on the player after he hits an enemy champion show golden chevrons over their heads.

### 1.1 The switch rule (C, code)
Already in ics (2026-10-28): `Match._on_damage` records a champion who hits an enemy champion
(`aggressors[eid] = (t, victim team)`) and wakes the victim's allied minions / turrets (`match_call_for_help_now`);
`UnitAI.think` makes `champion_aggressor(team, pos, sight)` (hit within `match_call_for_help` 2 s, within sight) the
first target of minions and structures. No change.

### 1.2 The indicator in the data (C for the words, P for the meaning)
Every unit's and champion's common scriptlet table `0x1D0000E8` (pack `0xA00000DF`) holds:

| Key | Body |
|---|---|
| `CbtState_Aggro 0x10000D61` (@0x147FBEC) | prop `0x479` (instance cap); type `0x22` on `0x100000CE` (case `== 1`) -> type `0x22` on `0x100007A2` (cases 5 enemy / 3 ally / 6 neutral) -> type 8 overlay, material `0x170011FB` (fresnel shader), 0.15 / 0.5 s, enemy `0xFFFF1A00`, ally `0xFF0058FF` |
| `CbtState_Aggro_Active 0x10000D62` (@0x14803B0) | same gates; enemy branch: type `0x2E` (`0x4A3`), type `0x2E` (`0x7F3`, colour `0xFFFF2929`, 0.1), type 8 overlay with material `0x17001A92` (a DXT5 texture) in gold `0xFF783A04` / `0x77783704`; ally branch the same in blue `0xFF1B53FF` |

The case words are read like `CbtState_KnockUp`'s container on LifeState (`0x100000FA ... 4` = alive). No other key
in the 0x33000000 name table matches aggro / threat / chevron (the `Vfx_Status_Target_Enemy_*` keys are not in the Crime Alley / Gotham Divided minions' or AGL's tables).

### 1.3 0x100000CE (C code, P meaning)
Client writer `0xA16730` (no direct caller; a listener slot, pointer at `0x16041A4`): sets `0x100000CE` false on the
old object and true on the new one (not for 0x02 IIDs, `0x4DAF10`) and watches `0x3CB`, LifeState, `0x10000B2D`. The
vitals listener `0xAAFCD0` turns the object's HUD vital notices on when it becomes true (fase3-hc sets it on the
champion for the Will buttons). So it marks the controlled agent; setting it on a minion could feed the HUD with the
minion's vitals. The recall FX's sounds are behind the same gate and play on our champion (where it is true), which
supports the `== 1` reading.

### 1.4 Fix (`ics/match/units.py aggro_indicator`, called each tick)
While a unit whose role is in `[ics] match_aggro_roles` (["minion"]) has the local champion as its target: 0x8D
`CbtState_Aggro`, then `CbtState_Aggro_Active` (held as a looping key: re-sent after the unit's full bundles); both
carry `0x100000CE = 1` as a run variable (`match_aggro_flag`, `match_aggro_flag_mode` "variable"; "property" = a 0x6 on
the unit; "none"). When the unit drops him: `0x11F` for both keys (a dead unit's runs end with its object; the hold is dropped) (every run; a 0x8D signal stops
nothing). [] roles = as before.

### 1.5 Open
O: whether a 0x22 container reads a run variable before the object's property (the bindings do: ctx variable table
when the descriptor byte is 6, else the target's property, client-scriptlets-graphs.md 1.4). If the gold overlay does
not show: `match_aggro_flag_mode = "property"` (watch the HUD health / Will while a minion targets you). P: that the
overlay is the chevrons of the screenshot (the texture of `0x17001A92` was not decoded).

## 2. Recall: the six converging streaks

Report: during the recall channel the six light streaks closing in on the champion are missing (the glow and sound
show since fase3-ij's hold).

### 2.1 What the server sends (C, traffic 19:51:20.903)
Recall script `0x3400000A` S2: `0x10000223` (`VFX_CBT_Hit_Shared`, plays the FX template in variable `0x1000050A` for
`0x1000033E` s) with `0x1E00009C` / 8.0; the hold re-sends it (same run) at +0.28 / +0.30 / +1.17 s.

### 2.2 The FX template 0x1E00009C (C words, P names)
An unplaced record of pack `0xA00000B3` (between `0x48000D48` and `0x4800014E`, body at `0x3D85A8`), 6 actions:
particle `0x180001F2` (`1 | 40 | 60`); a type `0xC`; a timed container bound to `0x1000033E` holding lights (type
`0xB`, `0xFF9CDFFA`, `0xFFB6A1FB`), sounds (type `0x2C` hashes) behind `0x22` on `0x100000CE == 1`, a type `0x17` on
`0x1000033E` (8.0); a **type-3 spawn** (creation 9, `0x10000008`) whose property table names FX `0x10000941 =
0x1E00037F`, `0x10000942 = 0x1E000380`, `0x10000943 = 0x1E00037E`, offset `0x10000949 = (0, 0, 2)`, `0x1000094A =
0x15`, `0x10000946 = 3`, `0x1000093C = 2`, `0x10000944 = 2.0`, bound `0x10000940` / `0x10000945` / `0x100008D9`, and
binds `0x100008D7` (duration) to `0x1000033E`; a type-8 overlay `0x170011FB` (`0xFF78B8F5`). `0x1E00037F` / `380` are
particles `0x18000A3A` / `0x18000A39` (offset -0.45), `0x1E00037E` particle `0x18000A4D` + light.
`Vfx_Test_Status_Recall_*` (`0x1000031A/D`, `0x10000318`, `0x100004B3`) are in no table.

### 2.3 Status
P: the streaks are the type-3 spawn (a client-only object with start / loop / end FX). Nothing the server sends is
missing from the template's own needs that could be proven (its only binding is the duration, which is sent); the
bound `0x10000940` (a DID) has no binding in the action and no value on the wire. **No behaviour change** in this
build. O: what the type-3 spawn needs (exe: the action's execute through the scriptlet action vtable, `0x52DC90`), and
whether the hold's re-sends restart it.

## 3. Score screen: the rewards panel

Report: the right panel of the original's score screen (Victory, Match Duration, Rewards: Protector XP with level and
bar, Merit earned / total, Champion XP with level and bar) does not show.

### 3.1 The client's panel (C, Flash)
This client's scorecard (`gameplay.wrapper.scorecard.Scorecard`) has three tabs: **Accolades** (index 0,
`ScorecardAccolades`: accolades, `AccoladesMeritDisplay` match / streak / first-win / total Merits,
`AccoladesChampionDisplay`, `AccoladesProtectorDisplay`, `AccoladesMapDisaply` = encounter name + duration), Summary
(the team tables) and Stats. The original video's layout (Summary + Stats tabs, the panel beside the table, "Earned /
Total" Merits) is another client version; here the same data is the Accolades tab. Its animation chain: accolades ->
Merits -> champion bar -> (ribbon queue done) -> protector bar -> map; every part waits on `ScorecardManager`'s
`ALL_DATA_RECVD` (0x2190, 0x2045, 0x2188, 0x2080, 0x2081, 0x20B9, 0x2104, 0x2090, upgrades / power graph per row,
0x219F / 0x219E), which ics sends.

### 3.2 Bug found: 0x2080's word order (C)
Handler `0xA7DFB0` (the 0x2080 exec's target) stores the 8 wire words and calls Flash
`SendAccountEndOfMatchLevelAndXP(level, prev, xpToNext, xpTotal, xpEarned, xpBonus, pct, prevPct)` (`0x8908D0`) with
`(w0, w1, w5, w2, w3, w4, w6, w7)` and the header's `SendAccountLevelAndXP(level, totalXP, pct, xpToNext)` (`0x891200`)
with `(w0, w2, w6, w5)`. ics sent `level, prev, to next, total, earned, bonus`: the panel got total = our "to next",
earned = our total, bonus = our earned and to next = 0. Now `level | prev | total | earned | bonus | to next | pct |
prev pct` (`[ics] account_level_layout` "client"; "old" = before), at the match end and at login.

### 3.3 XP numbers (C from the original's screenshot)
"247793 / 273500" at Protector level 54 with the bar ~10 % full and "6625 / 7200" at champion level 12 with the bar
~33 % full: the text is cumulative XP / cumulative XP of the next level, the bar the share inside the level
(`AccoladesProtectorDisplay`: text `AccountXpTotal + " / " + AccountXpToNextLevel`, front bar `total - earned`). ics
sent XP inside the level / XP still missing. Now cumulative (`[ics] xp_numbers` "cumulative"; "remainder" = before)
for 0x2080 and 0x2104.

### 3.4 Open
O: which tab the client opens first (the UI state machine's `NextScorecardTab`, CONST_Tab_Scorecard_Accolades /
Summary / Stats, `old_files/tools/ui_sm.hkx`, a Turbine format not decoded). If the panel still does not show, the
Accolades tab (first tab button, or the arrow left of Summary) is where it is in this client; a diag of the Flash
calls `0x921BE0` (UIStateMachineEvent: 106 LoadScorecard_Accolades, 72 Summary), `0x8908D0`, `0x88FF50`, `0x890CE0`
would show what the client received.

## Tests
`tests/test_match.py aggro_indicator` (7 checks); `tests/test_session_flow.py` +2 (0x2080 order and cumulative
numbers at the match end, the "old" layout).
