# Second match of a client session stuck at 35 % (2026-10-23)

Static analysis of InfiniteCrisis.exe (Ghidra, image base 0x400000) plus logs of the 22:32-22:35 run.
C = confirmed in code, P = probable, O = open.

## Symptom in the logs

- Both loads get the same server messages (0x214B, 0x20AF, 0x2016, 0x206D), both clients report 10 / 20 / 25 / 35 %
  and send **0xCC level loaded** (traffic.log 3064 and 10916), and the server sends the same objects + "create champion
  + player" ~4 s later in both.
- Good load: client answers 0x211B, 0x207A, 0x2, then 0x20D5 55 % (traffic 3446-3461); diag shows 0x64dac0 finalise
  for IID ...01 first, then "local player object ready" (0x69bd90), then the queued entities 0x100-0x111.
- Bad load: no 0x211B, no 0x64dac0 at all, never 55 %.
- ics sends **0xEB (set local player) only once, at login** (traffic.log line 68). The old server re-sends it before
  every later match (`icserver/session.py` ev_connect_to_lobby, `[match] resend_local_player`, CHANGELOG "Replay").

## Root cause (C)

1. World teardown `0xa99b60` (run when the client leaves; 0x12D follows) calls `0x7d14b0(1)`, which calls
   **`0x635250(0, 0)`**: the local player IID global `[0x1b6a710]/[0x1b6a714]` becomes 0. The only other writers of
   that global are `0x64b2e0` (local player assignment: `0x635250(id)`, `0x504630`, `0x64b170(0,0)` - the 0xEB path)
   and `0x64c910` (another reset, also to 0).
2. The 55 % step is **`0xa0a570`** (+20 via `0xa964b0(0x14)`): it runs only when `0x6351d0()` returns the local player
   object, i.e. `[0x1b6a710]` != 0 and the object manager finds it (`[0x1b67258]` vtbl +0x58). With the IID at 0 it
   returns 0 and the step is skipped forever. The +15 step (`0xa96cf0`) also needs the player object.
3. Object creation `0x64d8a0`: objects with IID top byte 2 and IID != local player are queued (`0x64c310`) while the
   local player is not finalised; the local player's own finalise (`0x64dac0`, async callback `0x64dd70` of
   `0x64ca10`) calls `0x69bd90` only when the IID equals `0x635230()` (the local IID) and flushes the queue
   (`0x64b170` / `0x64b370`). With the local IID 0 the player is never "local": no `0x69bd90`, no 0x211B (the same
   chain the old server documented as "loading stopped at 10 %" in fase3-f*). Why diag saw no `0x64dac0` at all is
   O (the async create in `0x64ca10` may wait on the player link); it is consistent with the player never becoming
   local.

## Pack release path (C; not the cause)

- 0x20AF `0xa99f00`: stores lists, encounter at +0xC4, sets lobby+0x4CB, flag 2 of +0x70; if lobby+0x4CA and +0x4C8
  are clear, flag 4 and `0xa99e20`.
- `0xa99e20` (flags & 7 == 7, bit 8 clear): `0xa960e0` world reset, encounter template, `0xa99370` LoadParentRPs.
  Teardown `0xa99b60` zeroes +0x70, +0x78, +0xC8 and clears lobby+0x4CD, so the second 0x20AF passes the gate.
- `0xa99370` first calls `0xa08860`, which releases the previous match-data list synchronously (`0x9e3e20`), then
  queues the new loads (`0xa09e50`); `0xa99460` LoadMatchData (+10) re-adds the 0x20AF packs (`0xa09f90` ->
  `0xa08e90`). A pack named in both matches is unloaded and loaded again in order; the second load reached 35 % and
  sent 0xCC, so the loader finished. No evidence that an overlapping pack blocks.
- 0x2021 arrives after the teardown (the client sent 0x12D), which already cleared lobby+0x4CD; the exit hazard in
  reverse-engineering.md (0x2021 while lobby RPs load) does not apply here.

## Fixes (ranked)

1. (High) Send **0xEB** `M.set_local_player()` again before every match after the first in a login session (before
   the next 0x20AF / objects; the old server put it ahead of the lobby data at 0x20F2). New `[ics]` key, e.g.
   `resend_local_player = true`.
2. (Low) Alternatively send it in `ev_left_world` right after 0x12D (teardown already done), so the menu also has the
   player id back.
3. (Not needed) Omitting overlapping packs from the second 0x20AF: no evidence it matters.

## Diag plan (rva = VA - 0x400000)

0x235250 (set local IID, log [esp+4]/[esp+8] and return rva), 0x3d14b0 (teardown reset), 0x24b2e0 (0xEB applied),
0x60a570 (55 % step; log [0x1b6a710]), 0x6b7bf0 (percent add, arg), 0x24d8a0 (object create entry, IID args),
0x24c310 (queued), 0x24ca10 (direct create), 0x24cba0 (create failed), 0x24dac0 (finalise), 0x29bd90,
0x699f00, 0x699e20, 0x699370, 0x699460, 0x608860, 0x608e90, 0x608ed0, 0x699b60.
Expected after fix 1: 0x24b2e0 / 0x235250(id=...01) before the second 0x20AF, then 0x24dac0 for ...01 and 0x60a570.
