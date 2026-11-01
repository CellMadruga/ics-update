# Hover highlight: the 0x3CB listener is never registered for a top-byte-2 champion (2026-10-30)

Tester report 2026-10-30 18:12: "the minions are not highlighted when I pass the cursor over them" (both teams), no
left-click select / stats. Evidence: `diag --hover` in the 18:00:46-18:03:29 section of that run's diag.log (the
18:03:38-18:04:29 section has `HOT` / `STACK HEADS` lines only and the 18:04:36 one is `--strip`), traffic.log for the
IIDs. Labels: C = code read, R = runtime log, P = probable.

## 1. What the diag shows (R)

IIDs (traffic `spawn` bundles): local champion AGL `0x...002` (team 1), bot Joker `0x...100` (team 2), core t1 `0x101`,
core turret t1 `0x103`, dampener t1 `0x10B`, turret t1 `0x10D`, rocks / vehicles `0x131` / `0x139`, camp `0x13F` /
`0x140` / `0x142`, wave 1: `0x147` / `0x149` / `0x14B` / `0x14D` = team 1 (ally) melee 1, melee 2, ranged 3, ranged 4,
`0x148` / `0x14A` / `0x14C` / `0x14E` = team 2 (enemy).

- **The tick's pick works.** `HOVER: tick pick` / `0x3CB write new_iid` named, among others, every enemy wave-1 minion
  (`0x148`, `0x14A`, `0x14C`, `0x14E`), the allied minions `0x147`, `0x149`, `0x14D`, the bot `0x100`, our structures,
  a camp, our own champion. (The diag logs a `0x3CB write` only the first time an IID appears: per-first-field dedupe.)
- Candidate scores: enemy minions 20.0 (`0x41a00000`, flags 2 = box sweep, i.e. they have the body) or 19.0 (camp
  `0x142`), allied minions 1.3 (`0x3fa66666`), own champion 1.4. Enemies win; nothing is refused by the validator.
- **`HOVER: outline colour` (0xA4EDEC, right after 0xA1D020) was hit only 12 times**, never for an allied minion, a
  structure or the bot, and for enemies only next to an attack / ability order: vehicle `0x139` at 18:02:15 after the
  slot-7 order on it (18:02:14), rock `0x131` at 18:02:25 after slot 8, `0x148` alpha 1 at 18:02:54 = the server's
  `attack mid melee 1 t2 w1` at 18:02:54.4, `0x14A` at 18:03:00 after its attack at 18:02:59.7, and so on. Those calls
  come from the lock / ability paths (`0xA88700`'s expiry list, `0xA4F0C0`, `0xA5DAB0`), not from a hover change.
  All four colours (hover `0x186D9D8` (0,1,0,1), locked `0x186D9C8` (1,1,0,1), selected `0x186D9B8` (1,1,1,1)) have
  green = alpha = 1, so the alpha-1 lines are the attack lock's yellow, not the hover.

So 0x3CB changes, but nothing that reacts to a 0x3CB change runs.

## 2. Why (C)

- Everything the hover does is in the property listener **`0xA5D5F0`** (vtable `0x1604224` slot 3, the selection
  object's `+0x14` interface) case 0x3CB: `0xA4ECC0(new)` -> `0xA1CD40` = scriptlet **`_Selection_SoftSelection_Valid`
  0x100001E4** on the hovered unit when the validator `0x9D01D0(champion, unit, slot, 1)` accepts it, else
  **`_Selection_SoftSelection_Invalid` 0x100001E6** (`0x588A00` = start scriptlet key; stopped by `0x58CBB0` on the next
  change, which also clears 0x974); old unit: `0x8BBBA0` + `_Selection_Usage_Invalid` 0x100001E1, `0xA4EDD0`; new unit
  the champion can attack (`0x9D0490` = 0): `0x8BB950` ("GM_SelectionSystem.RecvNotice_UsableTargetInRange") +
  `_Selection_Usage_Valid` 0x100001DF, then `0xA4EDD0` (green outline only when the unit is NOT attackable, is our
  champion, or an armed ability accepts it: `0xA1D020`); then `0xA1CDD0` (cursor: attack `0x10000024` etc.) and
  `0xA39820`.
- Lane minions (0x40000BF8 / 0x40000BFA), turrets (0x40000C8C) and camps (0x40000CA0) all have 0x100001E4 / 0x100001E6
  in their scriptlet tables (gamedata `scriptlets()`); none has 0x100001DF / 0x100001E1. So the hover highlight of a
  unit is its own SoftSelection scriptlet (P: the outline / ring VFX), the green 0x974 outline is for allies.
- The listener is registered on the champion by the controlled-agent handler **`0xA16730`** (vtable entry
  `0x16041A4`): `0x58BA40(agent, 0x3CB, listener, 1)`, then 0x100000FA (LifeState), 0x10000B2D, `0x85D130` (the 16
  attributes 0x100008E3-0x100008F2), 0x100000CE = true and the attack range at +0x58 (`0x874930`). **All of it sits
  behind `0x4DAF10(agent IID)` = "IID top byte == 2" (`test al, al; jne 0xA168DA` at va 0xA16807 / 0xA16809).** ics
  gives every object top byte 2 (the local champion is `0x0200000000000002`), so the listener is never registered
  (already seen for 0x100000CE in `skill-button-will.md` 2b, where option 2 was this same patch).
- That explains every symptom at once: no SoftSelection scriptlet on hovered enemies or allies, no green outline on
  allies, no attack cursor, no UsableTargetInRange notice; the outline lines seen came only from the lock / ability
  paths that do not need the listener. Left-click select / stats (selected = `+0xD8` / `+0xE0`, colour `0x186D9B8`)
  likely needs the same listener (0x10000B2D / LifeState cases; P, not traced).

## 3. Fix (fase3-is): exe patch "controlled agent listeners"

`icserver/patcher.py`: file offset `0x615C07` `84c00f85cb000000` -> `84c0909090909090` (the jne becomes nops; the same
kind of fix as the "perception filter" patch for the top-byte-2 gate at 0x852146). The client then registers the
listeners on our champion as the original did for its non-2 agents. ics already sets 0x100000CE on the champion
(fase3-hc), so that write changes nothing. The old-agent half of `0xA16730` (unregister) had no gate. `[game]
exe_patch_skip ["controlled agent listeners"]` restores the original bytes on the next `python ic.py patch`. No server
code or `[ics]` key changes (a server-side alternative, a non-2 top byte for the champion, would touch the creation
pools and every `0x4DAF10` caller: `skill-button-will.md` 4.3).

The user must run `python ic.py patch`. tests/test_match.py `hover_listener_gate` checks the patch bytes / jump target,
the installed exe and the minion's SoftSelection keys.

## 4. If the highlight is still missing after the patch (next probe)

New `--hover` lines (tools/diag.py): `HOVER: agent listener gate` (va 0xA16807, `al` 1 = top byte 2; with the patch the
jne is gone, so the line only confirms the agent IID), `HOVER: 0x3CB listener` (va 0xA5D709, the listener's 0x3CB case:
the new hovered IID) and `HOVER: soft selection start` (va 0xA4EDAB, the `0x588A00` call: hovered IID and key
0x100001E4 Valid / 0x100001E6 Invalid). Readings: no `0x3CB listener` lines = the patch is not in the running exe (run
`python ic.py patch`) or `0xA16730` ran before the champion object existed; listener lines but no `soft selection
start` = `0xA1CD40` returned 0 (no `0x85C150` champion or the unit is unknown); start lines with no highlight on screen =
the SoftSelection scriptlet's own VFX (render side); allies should also log `outline colour` alpha 0x3f800000.
