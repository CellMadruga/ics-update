# End-of-match stats `0x2045` with filled rows: layout check (2026-10-26)

Tester 2026-10-26 19:53: at the end of a match the client froze and closed before the stats screen. That was the
first match where `0x2045` went out with FILLED rows (`end_stats_from_ledger`). The bytes are in traffic.log at
19:53:26.354 (2 players, 1261 bytes). Tags: **C** = confirmed in the exe (decompiler + assembly), **P** = probable,
**G** = guess. The exe was opened read-only (Ghidra, base 0x400000).

## 1. The wire layout is consumed exactly (C)

The dump was parsed with a script that follows the client readers one call at a time (scratch `end2045/parse.py`):
every sub-reader takes exactly what ics wrote, and the f32 duration ends at the last byte (0 bytes left). The client
does **not** read past the end, and no reader rejects a value (each bool byte is 0/1, the bucket hints are 0, every
count is small).

Entry reader `0x8776A0` (`EDI` = entry, 0x350 bytes in memory), in wire order:

| Wire | Memory | Reader / note |
|---|---|---|
| u64 | +0x00 | (P: unused here) |
| u64 | +0x08 | **account IID** (getter `0x85C790`; friends list compare in `0xA795E0`). ics writes the champion iid here: harmless, but wrong |
| u64 | +0x10 | player IID (`0x85C750`; `0xA1B0A0` looks up the player) |
| u32 | +0x1C | (P) champion DID: `0x4FD4E0` reads +0x1C -> `0x85E010` (portrait) and `0xA25430` (record), in both row loops of `0xA795E0` |
| u32 | +0x20 | (P: level) |
| `0x86FB20` | +0x28 | `u32, u64, u32, StringInfo, wstring (0x421690 -> 0x4215D0), u32, compact n + n x u32 (0x53D570)`; the list is the artifacts (`0x85C7F0` -> +0x68/+0x6C) |
| u32 | +0x2D0 | team (`0x85CA00`) |
| map `0x583DD0` | +0x2A8 | kills by target type |
| map `0x583DD0` | +0x2BC | second map (P: by killer type; the getter `0x8677F0` never reads it) |
| StringInfo `0x5A9580` | +0x2D4 | name |
| u32 | +0x2F8 | (P: icon) |
| u32 n + n elements (`0x86F400`, element `0x867550`) | +0x30C | ics sends n = 0 |
| u32 n + n elements (`0x86F520`, element `0x867660`) | +0x31C | ics sends n = 0 |
| u32 n + n x 8 bytes (`0x844770`, element `0x6B01A0`) | +0x2FC | n = 0. When n > 0, `0xA795E0` runs `0x9D1700` / `0xA3AC70` on it (pairs u32, u32) |
| stats block `0x866650` | **+0x78** | `LEA ECX, [EDI + 0x78]` at `0x8778BD` (see 2) |
| u32 | +0x32C | CreditsStomped (stat 7) |
| u8 | +0x330 | bool: not 0 or 1 sets a stream error (`0xAF8710(0x80004005)`) |
| u8 | +0x331 | bool: is bot (same check) |

The count map (C, `0x583DD0` -> `0x5838E0`, insertion `0x4C1700`):
`u8 bucket hint (<= 22, index into the prime table at 0x1612B30: 11, 23, 47, ...) | compact n | n x (u32 key, u32 value)`.
That is the whole format. There is no other byte prefix: the leading `u8 0` IS the bucket hint (0 = 11 buckets).
When n < 5 the map is a plain linked list (flag 0x80000000, `0x50B080`). With n >= 5 it hashes by key % prime.
Both work with hint 0. The kills key is a u32 and the count is a u32. Lookup is `0x867740(key)` (list or bucket walk).
Copying the entry into the page's vector (`0xA916E0` -> `0x8761D0`) deep-copies both maps (`0x4DD9F0`), so the
nodes are not left dangling (C).

StringInfo (C, `0x5A9580`): `u8 mode | mode 1: compact length + UTF-16 | else u32 token, u32 table`, then the
variables table (`0x5A9440`: `u8 hint | compact n | ...`). It matches `string_info`.

## 2. The real layout mismatch: the stats block starts at +0x78, not +0x70 (C)

`hud-shop-timeline-kills.md` 6 put the block at entry +0x70. The assembly calls `0x866650` with `ECX = entry + 0x78`.
The getter `0x8677F0` uses entry offsets, so **every read index in that table is one too high**. The types were also
partly wrong. The real read order (block offset; entry offset = block + 0x78):

| Reads | Kind | Block offsets |
|---|---|---|
| 0 | u64 | +0x00 |
| 1 | u8 bool (0/1) | +0x0C |
| 2 | u32 | +0x08 |
| 3..10 | u64 | +0x10 .. +0x48 (step 8) |
| **11** | **f64** (`FLD/FSTP double`) | +0x50 |
| 12..16 | u64 | +0x58 .. +0x78 |
| 17, 18 | u32 | +0x80, +0x84 |
| 19..24 | u64 | +0x88, +0x90, +0xD0, +0xD8, +0x98, +0xA0 |
| 25 | u32 | +0xA8 |
| 26..33 | u64 | +0xB0, +0xB8, +0xC0, +0xC8, +0xE0, +0xE8, +0xF0, +0xD0 (read 33 writes +0xD0 again: client quirk) |
| 34 | u32 | +0xF8 |
| 35..40 | u64 | +0x100 .. +0x128 |
| 41 | u32 | +0x130 |
| 42, 43 | StringInfo | +0x1E8, +0x20C |
| 44..56 | u64 | +0x138 .. +0x198 |
| **57..60** | **f64** | +0x1A0, +0x1A8, +0x1B0, +0x1B8 |
| 61..64 | u64 | +0x1C0 .. +0x1D8 |
| **65, 66** | **f32** (`FLD/FSTP float`) | +0x1E0, +0x1E4 |

The wire size is the same as ics' `_STAT_READS`: every 8-byte slot stays 8 bytes and every 4-byte slot stays 4. Only
the meaning of each slot changes. The corrected stat id -> read index (the getter only uses the low 32 bits of a u64):

| Stat | Read | | Stat | Read | | Stat | Read |
|---|---|---|---|---|---|---|---|
| 0x01 TimeSpentDead | 35 | | 0x13 HealingReceived | 40 | | 0x24 BeaconsDeployed | 31 |
| 0x02/0x11 captures | 27 | | 0x14 CreditsFromDrones | 58 f64 | | 0x25 XPFromDrones | 62 |
| 0x03 PowerDmgTakenFromChamps | 55 | | 0x15 PowerDamageDealt | 51 | | 0x26 PowerReducedFromChamps | 56 |
| 0x04 OrbitalCannonCaptures | 29 | | 0x16 Assists | 7 | | 0x27 DamageReduced | 38 |
| 0x05 AttackReducedFromChamps | 50 | | 0x17 AttackTakenFromChamps | 49 | | 0x28 CreditsEarned | 11 f64 |
| 0x06 QuadraKills | 14 | | 0x18 XPFromCreatures | 63 | | 0x2C RaiderKills | 19 |
| 0x08 CreditsFromObjectives | 60 f64 | | 0x1A PowerRelaysCaptured | 21 (and 33) | | 0x2D PowerDealtToChamps | 52 |
| 0x09 CreditsFromCreatures | 59 f64 | | 0x1B DamageTaken | 36 | | 0x2E HealingDone | 39 |
| 0x0A CreditsFromChampions | 57 f64 | | 0x1C XPFromChampions | 61 | | 0x30/0x32 neutralised | 28 |
| 0x0B CoinsCollected | 30 | | 0x1D DampenersDisabled | 44 | | 0x31 DoomsdayDeviceFired | 32 |
| 0x0C ExperienceEarned | 26 | | 0x1E Deaths | 6 | | 0x33 DmgTakenFromChamps | 45 |
| 0x0E/0x2A Destruction | 12 | | 0x1F DamageDealt | 37 | | 0x34 AttackDealtToChamps | 48 |
| 0x0F AttackDamageDealt | 47 | | 0x21 TripleKills | 13 | | 0x3C LeviathanKills | 20 |
| 0x10 DoomsdayActivations | 24 | | 0x22 XPFromObjectives | 64 | | 0x12 PentaKills | 15 |

Kills map keys (C, `0x867740`): 0x8 champions (0x2B), 0x10 turrets (0x20), 0x100 creatures (0x29), 0x10000 drones
(0x0D), 0x40000 guardians (0x2F). Deaths (0x1E) come from read 6 through `0x8677B0` (its key `DAT_016012C0` is 0 ->
returns entry +0xA0).

What ics did with the old numbering (from the dump): credits went as an f64 into read 12 (a u64, DestructionCaused),
so its low dword was 0x6D971C29. The objectives credits went as an f64 into read 61 (XP from champions). Deaths went
to read 7 (which shows as Assists) and assists to read 8. Every damage, healing and XP value landed one stat to the
side, an int went into the f32 at 65, and the real f64 slots (11, 57) got 0. **None of this reads invalid memory.**
Every f64 slot held a valid double or 0, and the getter rounds f64 and truncates u64. So the shift explains wrong
numbers on the Stats tab (C). On its own it does not explain the crash (P).

## 3. What the filled form changes in the client (C) and where the crash must be (P)

With the empty form every row had team 0. The page builder `0xA795E0` runs the Stats-grid / team-totals builder
`0xA72860` only for rows with `team - 1 in {0, 1}` (`0xA72860`, `local_74`). So **filled rows are the first time this
client ever ran `0xA72860`** (grid record `0x10000B2C` -> sections `0x10000B33` / stat lists `0x10000AB1`, `0xA140A0`,
`0x86BE10`, the getter `0x8677F0`, time / number formatting `0xA49D60` / `0xA31E20` "%I64u"), and the first time it
built team totals and the Flash Scorecard rows (`0x8E3AC0`, 42 args, at `0xA7A44B`). Nothing in that path indexes
memory with our values: the column counts come from the grid record, not from the entry. The crash is therefore in
this team-gated path or in Flash (P). The obvious null dereferences are `0xA72AAD` (vtable +0xF0 on the grid ref) and
`0xA72DED` (vtable +0xF0 on a section's stat list, `[EBP-8]`), and they depend on the data, not on our bytes (G).
Timeline in the logs: the client left the world (0x12D) 230 ms after the batch and died 5 s later (10054). That fits
the end page being built.

## 4. Fix (exact)

Layout, `ics/messages.py` `_end_stats_entry` (wire size unchanged):
- `_STAT_F64 = {11, 57, 58, 59, 60}`, and add `_STAT_F32 = {65, 66}` (pack with `<f`). Read 1 stays a 0/1 byte.
- `Match.end_rows` reads, renumbered: `6: deaths, 7: assists, 11: credits (f64), 26: xp, 37: dealt, 47: dealt_1,
  48: dealt_champ_1, 51: dealt_2, 52: dealt_champ_2, 36: taken, 45: taken_champ, 49: taken_champ_1, 55: taken_champ_2,
  38: reduced, 39: healed, 40: heal_received, 57: credits_champions, 58: credits_drones, 59: credits_creatures,
  60: credits_objectives (all four f64), 61: xp_champions, 62: xp_drones, 63: xp_creatures, 64: xp_objectives,
  19: raider, 20: leviathan, 44: dampeners`. Coins go to 30, time dead (seconds) to 35, captures to 27, beacons to 31.
- Head: the second u64 should be the account IID (or 0 for a bot), not the champion iid. The u32 at +0x1C is (P)
  the champion DID for the portrait.
- Maps, name, the three counts and the tail are correct as sent. Keep the bucket hint 0.

Isolating the crash (the layout fix alone may not cure it): add `[ics] end_stats_team = true`. When false, the rows
are filled but go out with team 0, which skips `0xA72860` and the totals. That splits "our bytes" from the client's
grid path in one test. Default: true once fixed. Keep `end_stats_from_ledger = false` until the tester confirms.

## 5. Diag breakpoints for the tester (`tools/diag.py --matchend` + these; keys are RVA = VA - 0x400000)

The tracer already logs first-chance exceptions with their address (tracer.py, EXCEPTION_DEBUG_EVENT), which gives
the crash site directly. Add:

| RVA | Label | Values |
|---|---|---|
| 0x679AA6 | page: Scorecard columns read (`0xA49EC0` returned) | |
| 0x672860 | grid builder `0xA72860` entered | `this = ecx` |
| 0x672AAF | grid: section count call | `grid = ecx` (0 = will crash) |
| 0x672B2E | grid: section label + stat list (`0xA140A0`) | `section = [esp]` |
| 0x672DEF | grid: stat-list count call | `list = ecx` (0 = will crash) |
| 0x673020 | grid: getter for one stat | `entry = ecx`, `stat = [[esp]]` |
| 0x67A338 | grid builder returned | |
| 0x67A44B | Flash `UI_SendEndOfMatchStats` call | |
| 0x67A450 | Flash call returned | |
| 0x67A4C3 | second row loop (`0x9D1700`) | |

The last label logged before the exception is where it dies. If every label up to 0x67A450 shows and the crash comes
later, it is in Flash or in the front end after the world teardown.
