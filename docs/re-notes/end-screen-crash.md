# End-of-match crash at 0xA37DEE: account standings 0x219E (2026-10-28)

Tester 2026-10-28 12:56: "the match ended (I surrendered), the score screen should appear". The game crashed
instead, as in the earlier runs. Tags: **C** = confirmed (assembly + decompiler + the bytes in traffic.log),
**P** = probable, **O** = open. The exe was read-only (static base 0x400000; the tester's image base was 0x370000, so
static = rva + 0x400000).

## 1. The faulting instruction (C)

diag.log 12:56:03: `NotifyMatchEnded` -> end page fill (`0xA795E0`) -> `0x2045` received -> end page fill again ->
first-chance `0xC0000005` at rva `0x637DEE` = static **`0xA37DEE`**, `eax = 0x46216380`, then UNHANDLED.

```
0xa37dc9 call 0xa37bf0              ; standings singleton (global 0x1B758F8)
0xa37dce mov  esi, eax
0xa37dd0 mov  eax, [ebp+0xC]        ; arg 1 (event +0x20)
0xa37dd3 mov  [esi+0x3C], eax
0xa37dd6 call 0xa37bf0              ; eax = singleton (0x46216380 in the dump)
0xa37ddb mov  ecx, [esi+0x20]       ; minimum streak
0xa37dde mov  edi, [ebp+0x24]       ; arg 7 = streak (event +0x38)
0xa37de1 cmp  edi, ecx
0xa37de3 jb   0xa37df8              ; streak < minimum -> no lookup
0xa37de5 mov  edx, [eax+0x188]      ; per-rank byte table
0xa37deb mov  ebx, [ebp+0x10]       ; arg 2 = rank (event +0x24)
0xa37dee cmp  byte [ebx+edx], 0     ; <-- CRASH: table[rank], no bounds check
```

The function `0xA37DC0` is not part of the end page: it is the handler of **`0x219E` account standings**. The stack's
second frame, rva `0x4BAE06` = static `0x8BAE06`, is inside `0x8BAD90`, the exec method of the event class with vtable
`0x15EFF68` (constructor at `0x87FDC7`: id `0x219E`, size 0x48, flags 0x300400). The serializer `0x83FEB0` reads 10 u32
into event +0x20 .. +0x44 in wire order, and `0x8BAD90` passes them as the 10 arguments of `0xA37DC0`.

## 2. The bad value (C)

traffic.log 12:56:03.440, `account standings (0x219e)` (57 bytes), body after the event id:
`00 | 00000000 | 40000C82 | 00000000 ...`. The second u32 (`ebx`, the rank) was the encounter DID `0x40000C82`:
ics' `ranked_values` put `[0 featured, encounter, rank, ...]`. The `0x219F` sent just before carried all zeros, so the
minimum streak (singleton +0x20) was 0, the streak (0) passed `streak >= 0`, and the client read
`table + 0x40000C82`: an access violation. The `0x2045` stats and the end page itself were not involved (they had
already been processed; the earlier suspects `0xA72860` / the stats layout are not the cause of this crash).

## 3. The real layout of 0x219E (C)

`0xA37DC0` (args = event +0x20 .. +0x44) stores into the singleton's vectors, which `0x900FC0` hands to Flash
`UI_DeliverAccountStandingsData(didFeaturedEncounter = +0x38, didLastPlayedEncounter = +0x3C, aEncounters +0x40,
aRanks +0x50, aSubRanks +0x60, aRankPositions +0x70, aStreakActives +0x80, aPreviousRanks +0x90, aPreviousSubRanks
+0xA0, aPreviousRankPositions +0xB0, aPreviousStreakActives +0xC0, aMatchesPlayed +0xD0, aMatchesWon +0xE0,
aWonLastMatch +0xF0, bShowBanner +0x12)`:

| Wire | Event | Meaning |
|---|---|---|
| u8 0 | | |
| u32 | +0x20 | encounter (the key of the per-encounter vectors; also `didLastPlayedEncounter`) |
| u32 | +0x24 | rank -> aRanks; indexes the byte table (streak active) |
| u32 | +0x28 | previous rank -> aPreviousRanks; indexes the table too |
| u32 | +0x2C | sub-rank |
| u32 | +0x30 | previous sub-rank |
| u32 | +0x34 | rank position (the old value moves to aPreviousRankPositions) |
| u32 | +0x38 | streak (compared with the minimum streak) |
| u32 | +0x3C | previous streak (aWonLastMatch = previous streak < streak) |
| u32 | +0x40 | matches played |
| u32 | +0x44 | matches won |

`didFeaturedEncounter` (+0x38 of the singleton) is not written by `0x219E` (O: probably by `0x219F`'s 5th tail value,
which goes to singleton +0x24, or by the client's data).

`0x219F` (serializer `0x848B80`, exec `0x8BA560`, handler `0xA5C840`): its 5 trailing u32 (event +0xC0 .. +0xD0) are
params 3..7; params 3..5 go to `0xA4CA10`, which rebuilds the rank tiers and the per-rank byte table (+0x188, count
+0x190) from client data (`0x100000FA`, `0x10000DBB` / `0x10000DD5`); param 6 = the minimum streak (singleton +0x20).
Unlike `0x219E`, `0xA5C840` checks `rank < [singleton + 0x190]` before reading the table.

## 4. Fix

- `ics/matchend.py ranked_values` sends the wire order above. With the account's default ranked data every rank is 0
  (P: index 0 is inside the table; the old server sent all-zero `0x219E` in the tutorial scorecard without a crash).
- Used at the match end (`pvp_match_end`) and for the menu's `0x2178` request (`Session.ev_standings`), which would
  have crashed the same way once the account had a last played encounter.
- `[ics] standings_layout = "reader"`; `"old"` = the fase3-ic order (crashes).
- `tests/test_session_flow.py` checks that the first u32 is the encounter and the rank / previous rank are small.

No diag mode was added: the static evidence and the bytes in traffic.log are enough. If a crash remains at the end, the
tracer's exception line names the next site.

## 5. Open (O)

- The real rank range (table size) comes from `0xA4CA10`; ics does not compute ranks yet. Any future ranked data must
  keep rank and previous rank below that count, or send a minimum streak in `0x219F` greater than the streak.
- Whether the score screen has further problems after this point (the next messages are `0x2125` / `0x211F` on the
  client's request) is untested in the game.
