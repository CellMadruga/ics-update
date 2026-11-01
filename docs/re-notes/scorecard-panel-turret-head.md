# Score screen rewards panel, turret heads, the Power Core Turret's base, log audit (2026-10-30, tester report 11:23)

Tester run 11:05-11:23 on build fase3-ip: Crime Alley v AI, Atomic Green Lantern against a bot (AI: Catwoman, random
skins); the match ended by surrender at 930 s (team 2 wins). Logs: that run's `server.log`, `traffic.log`,
`unhandled.log` (empty), `diag.log` (the fog ring's breakpoints only). Tags: **C** confirmed (decompiled exe, Flash AS2,
traffic, data), **P** probable, **O** open. Exe = Ghidra decompile `re-work/decomp` (base 0x400000); Flash =
`re-work/ui-as2/c_a00000d0_02189b08`. Builds on `scorecard-accolades-meteor-aura.md`, `turret-heads-coredeath.md`,
`power-core-turret.md`, `client-scriptlets-graphs.md`.

## 1. "The card in the scorecard section is not visible" (C exe, C traffic)

### 1.1 What was sent (traffic)
The surrender path sends the same end messages as a core kill (`Session.match_result` -> `matchend.pvp_match_end`):
11:23:03.006 cinematic `0x3500003B` (our core's end cinematic), 11:23:10.496 billboard type 8 + announcer event 29
(`match_end_timing` 7.5 s), 11:23:14.994 `0x1000000E`, then 0x2075, 0x214B, 0x2045, 0x2120, 0x2190, 0x2081, 0x2080,
0x20B9, **0x2104**, **0x2188**, 0x2090, 0x219F, 0x219E (all at 15.002-15.007), the client left the world at 15.168,
the scorecard asked for its ribbons (0x212E) at 15.687, and the fase3-ip late **0x2188 went at 17.193**. So the resend
ran; the panel stayed empty anyway.

### 1.2 Why the late 0x2188 did nothing (C, 0xA61DA0 / 0xA56DB0)
- 0x2188's handler `0xA61DA0` runs only when `*(param_8 + 8) != 0`: the count of its **second list** (the accolade
  records). Ours are all empty (54 bytes, six zero counts), so it returns before `0xA56DB0` and before the Flash call
  `0x8CEE70` (SendAccountEndOfMatchAccoladesEarned). An empty 0x2188 never reaches Flash, at the match end or later.
- `0xA56DB0(stringinfo, encounter, list2, list3, bytelist, list4, list5, flag, ...)`: all five lengths equal, then
  `0x8535D0(encounter)` must find the encounter's record, then per entry `0xA344C0(&list2[i], ..., list3[i] = medal
  1/2/3, byte[i], list4[i], list5[i])` builds name / description / summary / icon (`0x10000CE1..CE3` by medal; an entry
  that fails is skipped). It returns 1 (Flash gets called) even with no entry when the encounter is found.
- `0x8CEE70` has exactly two callers: 0x2188's `0xA61DA0` and **0x2104's `0xA7E0A0`**. 0x2104 calls `0xA56DB0` with its
  own lists (param_16..20), its trailing u32 **param_21 as the encounter** and u8 param_22 as the flag; when that
  returns 1 it caches (encounter, ranked bit, champion) and calls `0x8CEE70` with the (empty) arrays. ics sent 0 there,
  so `0x8535D0(0)` failed and 0x2104 delivered no accolades either.
- Flash (C, from the previous note): `ScorecardManager.RecvNotice_SendAccountEndOfMatchAccoladesEarned` raises
  **ACCOLADES_RECVD** only when every other piece is already in; `AccoladesDisplay` gets its data only from that event
  (or `HasAllScorecardData()` at its own load, false at that time); the "Summary" tab's chain (accolades -> Merits ->
  champion bar -> protector bar -> map) waits on it. With no live accolades notice the chain never starts and every
  part stays at alpha 0.
- What fills `bRecvdAccoladesEarned` for ALL_DATA_RECVD (the table tab showed in screenshot 81) is the C++ answer to
  the Init request (cached data); it is not the live notice (O: which function answers notice 0x100004E6).

### 1.3 Fix
- `[ics] scorecard_level_encounter` (true): 0x2104 carries the match's encounter after its accolade lists
  (`messages.character_level(..., encounter=)`). Its handler then hands Flash an empty accolades notice.
- `[ics] scorecard_accolades_resend_event` ("0x2104"): the late copy (1.5 s after the scorecard's 0x212E, or the 8 s
  fallback) is that 0x2104, not the empty 0x2188. Arriving with every other piece in, it raises ACCOLADES_RECVD; the
  empty accolade list makes an empty TimelineLite whose COMPLETE starts the Merits / champion / protector / map chain.
  "0x2188" = the fase3-ip resend.
- P: that the encounter record lookup (`0x8535D0`) succeeds for `0x40000C82` (it is the generic record fetch, used the
  same way on the accolade records). O: real accolade cards (list 2 = accolade records of `0x48001242`, medal 1-3) are
  still not sent (`match_accolades`, hud-shop-timeline-kills.md 6.2).

## 2. "When the turrets are attacked their top part disappears" (C traffic, P cause)

### 2.1 What goes to a turret (traffic, fase3-io vs fase3-ip)
Per lane turret: Object_Ranged_Attack `0x100002E0` + Vfx_Basic_Ranged `0x1000029D` per shot, VFX_CBT_Hit_Shared
`0x10000223` from the attackers' scripts (not in the turret's tables: the client drops it at the table test),
0x42 vitals, the under-attack ping 0x2008 `0x100000E7` -> client script `0x34000838` (minimap blink only; handler
`0xAA1BF0` only delivers the event), and **Target_Acquired `0x1000014A` + Target_Lost `0x1000002C` 1 ms apart**:
135 acquires / 127 losses on the two lane turrets in this run (e.g. 11:10:04.302 / .303, .021 / .021, ... every
0.6-0.7 s), 63 / 57 in fase3-io. Nothing else (no Vfx_Stop, no 0x11F, no bundle) goes to the bodies after the start.

### 2.2 The flap (C code)
`Units.think` gave a structure the closest enemy within `range + 1 m` (centre distance), `Units.act` dropped a target
farther than `_reach` = range + the target's radius (0.5 for minions) when the unit cannot move: every minion between
9.5 and 10 m was picked and dropped in the same tick, then picked again at the next think (0.5-0.8 s).

### 2.3 What each pair does on the client (C data)
- Body table `0x1D00035D` (bases `0x1D000372`, `0x1D000600`): Target_Acquired = two type-0x17 actions running
  Vfx_Targeting `0x1000005C` (flag 0); Target_Lost = the same with flag 1 (stop). Vfx_Stop's type-0x17 actions use the
  same form for Vfx_Active / Vfx_Targeting / Vfx_Event1, so flag 1 = stop that key.
- The head is the client's own child: Vfx_AI_Active `0x10000D63` = one type-0x0C spawn of `0x2E000AA8` + event
  `0x100000FE` + Vfx_Startup. The head's table `0x1D00035C` has its own Vfx_Targeting: start raises graph event
  `0x1000009C`, end raises `0x1000013D` on the head's animation graph (type 0x14 actions).
- So each flap starts and ends the targeting on the body and on the head (graph events 1 ms apart, ~1.4 times a
  second while minions stand at 9.5-10 m). P: this is what leaves the head hidden / collapsed after the turret
  engages; the head never had another cause in the traffic. In fase3-io the white server head stayed on top and hid it.

### 2.4 Fix
`[ics] match_turret_pick_in_reach` (true): structures pick only targets within the reach `act()` keeps, so a target
change is one Target_Acquired and, later, one Target_Lost. false = the fase3-ip pick.
O: if the head still goes, the next step is `diag.py` on the type-0x0C spawn's child removal (`0x57BAF0` / `0x516F80`
with the head's IID) while a turret fires, and the head's graph `0x1000009C` / `0x1000013D` states.

## 3. "The base of the turret near the core is missing" (C traffic, C data)
- Traffic 11:06:21: `spawn turret mid t1 plate (0x2e000a9f)` and t2, no plate for `core_turret t1` / `t2`.
- Since fase3-ip the blue Power Core Turret is `0x40000C8E` on the lane body `0x2E000AA0` (the red `0x40000C8D` uses it
  by data): the same body as the lane turrets, which stand on the gear plate `0x2E000A9F`. The 2026-10-24 rule "core
  turret: no plate" (crime-alley-video-compare.md) was for the old `0x2E000AC4` body on the original's prow; the prow is
  not in this client's data (crime-alley-still-missing.md 8, P another build).
- Fix: `[ics] match_turret_plates` gets `core_turret: 0x2E000A9F` (the plate stays when the turret falls, as on the
  lanes). Drop the key for the fase3-ip look.

## 4. Log audit (C)
- `unhandled.log`: empty. No traceback; one `Attack: refused, error 0x10000051` (stunned) at 11:19:30.
- **Surrender at 930 s was the tester's own vote**: game-channel notice `0x10000454` with u8 1 at 11:23:02.993
  (`54 04 00 10 01 00 00 00 01`), team 1 has one human, so 1 / 1 passed at once (0x10000455 / 0x10000456 at .002).
- 12 x `script rpc 0x81910003 ... not handled`: the client's RankSkill stub (u32 rank | u32 slot | u64 agent), each
  ~130 ms before the patched rank request ics applies (Grab 1, Scorched Earth 1 ...). Now logged as RankSkill
  (log only).
- 125 x `Atomic Green Lantern: move refused (crowd control)` in spans of 2-5 s at 11:10:21, 11:10:50, 11:13:19,
  11:16:35-11:16:56: each during a Super Strength lift / carry (11:10:20.438 "lifts vehicle 10"); the liftables work's
  area (not changed here).
- After the surrender the world kept running until the client left (11:23:03-11:23:15): minions fought, `mid melee 1 t1
  w30` died at 11:23:05, the bot levelled to 12, credits ticked. Harmless for the end screen (the stats were taken at
  11:23:03); not changed.
- Showroom item lines at the start (`showroom_prefetch`): a test aid on in the tester's config.

## 5. What the tester should see
1. The score screen's first tab ("Summary") fills: Merits, champion XP bar, Protector XP bar, the map with Victory /
   Defeat and the duration (no accolade cards yet).
2. Turret heads stay while turrets fight; turrets no longer flick their targeting line on minions at the edge of range.
3. The Power Core Turret stands on the gear plate like the lane turrets.
