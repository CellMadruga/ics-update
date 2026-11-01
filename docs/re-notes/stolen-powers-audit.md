# Stolen Powers audit (slots 7 / 8, D / F) — 2026-10-25

Scope: every Stolen Power in the data, how the client lets the player pick them, a headless cast of each through the
`ics` script VM, and what the client HUD needs for the D / F buttons. Written incrementally; sections fill in as the
work proceeds.

## 1. Inventory (data)

Source: catalog record `0x480003CD` (12 groups, the first member = the base power), `catalog/data/stolen_powers.tsv`,
`ics/gamedata.py Data.stolen_power` (the version's block `0x1000003F` merged on top of the base power's, key by key).
65 power records = 12 base + 53 champion versions. One script per group (every version of a group runs the base
script). No power has stat 3 (cost): Stolen Powers cost no Will.

| Group | Power | Script | Targeting `0x1000003D` | Base stats (stat=value, + per rank) | Versions |
|---|---|---|---|---|---|
| 0 | Consume `0x4800056E` | `0x340001C4` | 14 (unit) | 15 cd 60, 18 range 2.5, 5 dmg 75 (+10), 8 = 30 (+7.5) | 5 |
| 1 | Detonate `0x4800055F` | `0x340001BF` | 14 (unit) | 15 cd 120, 18 range 5.5, 17 = 3, 23 = 15, 5 dmg 40 (+10), 1 = 225 (+30) | 4 |
| 2 | Healing Wave `0x480007A8` | `0x340002B9` | 7 (instant) | 15 cd 120, 8 heal 50 (+12.5), 18 = 4, 14 = 30, 11 = 0.5 | 3 |
| 3 | Invulnerability `0x48000780` | `0x340002A2` | 5 (instant) | 15 cd 180, 14 dur 2, 10 = 60 (+15) | 4 |
| 4 | Meteor Drop `0x480005A2` | `0x340001D3` | 1 (point) | 15 cd 90, 5 dmg 60 (+15), 18 range 3, 14 = 120, 19 = 2, 23 = 45 | 5 |
| 5 | Psychic Assault `0x48000785` | `0x340002A3` | 14 (unit) | 15 cd 120, 14 = 2.5, 18 range 3.5, 9 = -0.35 | 7 |
| 6 | Super Strength `0x480003CB` | `0x34000164` | 14 (unit) | 15 cd 90, 18 range 1.5, 14 = 1.5, 19 = 2, 9 = -0.2 | 5 |
| 7 | Super Speed `0x48000529` | `0x3400019F` | 5 (instant) | 15 cd 120, 14 dur 4, 4 = 0.2 | 3 |
| 8 | Surveillance Camera `0x48000523` | `0x3400019D` | 1 (point) | 15 cd 5, 18 range 7, 23 = 6, 14 = 180, 21 = 2, 2 = 3, 32 = 3, 33 = 2 | 4 |
| 9 | Teleport `0x48000809` | `0x34000304` | 14 (unit) | 15 cd 420, 18 range 227, 14 = 4, 19 = 60, 12 = 120 | 4 |
| 10 | Trap `0x480007AC` | `0x340002BB` | 1 (point) | 15 cd 25, 18 range 1.5, 14 = 40, 19 = 1.5, 21 = 5, 12 = 3, 23 = 3, 31 = 60, 32 = 3, 33 = 2 | 5 |
| 11 | X-Ray Vision `0x48000549` | `0x340001AE` | 5 (instant) | 15 cd 100, 14 = 8, 18 range 12.5, 17 = 0.5 | 4 |

Block properties seen across the 65 merged blocks: `0x1000003D` targeting, `0x1000003E`, `0x100000E6`, `0x100001C0`
name, `0x100002A3`, `0x10000302` icon, `0x10000328` script, `0x10000448`, `0x100004AF`, `0x100004B4` stats,
`0x10000645`, `0x10000646`, `0x1000068D`, `0x100006D7`, `0x100006D8`, `0x100006DF`, `0x10000708`, `0x100007A6`,
`0x100007A7`, `0x1000083D` power type (group + 1), `0x10000850`, `0x10000855`, `0x10000ABC`, `0x10000D32`,
`0x10000D9E`; versions add `0x10000922` (unlock rule: champion level 5 + owned).

### 1.1 Finding: the version's stat list replaces the base power's

`Data.stolen_power` merges the two blocks **per top-level key**, so a version that carries its own `0x100004B4`
(stats) **drops the whole base stat list**. Examples (merged `Skill.stats`):

- Atomic Green Lantern Consume `0x48000815`: only {14: 4, 4: 0.125} — no cooldown (15), range (18), damage (5).
- Superman Super Strength `0x48000A3B` (the tutorial's F): only {12: 6 (+0.5)} — no cooldown 90 / range 1.5.
- Gaslight Batman Camera `0x48000808` (the tutorial's D): only {18: 10} — no cooldown 5, duration 180, etc.

Only the three versions with no stat list of their own (Nightmare Catwoman, Solomon Grundy and Wonder Woman Super
Strength) keep the base stats; the other **50 of 53** versions lose at least one base stat. The version lists are **deltas** (one or two stats each: a bigger range, a
shorter cooldown, an extra stat), so the right merge is stat-by-stat (version stat id overrides base stat id).
Effect on the server: `GetSkillStat` / cooldown / range read 0 for most versions (cooldown 0 = spam; range 0 =
out-of-range checks fail; damage 0). The same merged block is what the client gets in `0x100008F0 / F1`, so the
HUD tooltip / cooldown / range indicator show the same holes.

## 2. Headless cast sweep (script VM)

Harness: a copy of `tools/champion_check.py`'s world setup (Crime Alley `0x40000C82`, Gaslight Batman `0x40000086`
level 6, minions frozen 2 m away), `World.stolen_choice = [X, Y]` before `create_champion`, then `World.cast(ch, 7 / 8)`
with the targeting the data gives (14 = the enemy minion, 1 = its position, 5 / 7 = no target), 6 s of game time per
cast. A cast with no effect is retried on an ally minion, on self, and on a dummy enemy champion. Heals / damage
coming from the champion's own Q/W/E/R/passive scripts or from value-over-time ticks are not counted. Scratch
script: `sp_check.py` (scratchpad; not in the repository). Two runs: **as is**, and with the experiment
**stat-by-stat merge** (`SP_STAT_MERGE=1`: the version's `0x100004B4` entries override the base power's entries with
the same stat id `0x100004B6`, the rest of the base list kept).

All 65 casts are **accepted** (no refusal, no exception, no unknown node, nothing "not implemented") in both runs.

### 2.1 Run 1: as is

| Group | Base power | Versions (53) |
|---|---|---|
| Consume | DMG 75, cd 60 | 5 x nothing on the minion (damage stat missing), cd 0 |
| Detonate | DMG (900 over 4 hits), cd 120 | 4 x status only, no damage, cd 0 (Atomic Joker keeps its own cd 100) |
| Healing Wave | status, cd 120 | 3 x status, cd 0 |
| Invulnerability | status (self), cd 180 | 4 x status, cd 0 |
| Meteor Drop | spawns the meteor, cd 90, no damage in 6 s | 5 x same, cd 0 |
| Psychic Assault | status on the target, cd 120 | 7 x status, cd 0 |
| Super Strength | nothing (S4 waits for `0x100000BB` / `0x10000009`) | 5 x same |
| Super Speed | status (self), cd 120 | 3 x status, cd 0 |
| Surveillance Camera | spawns camera `0x40000265` (charges, no cd) | 4 x same |
| Teleport | nothing (S0 never leaves on `0x1000001D`) | 4 x same |
| Trap | spawns the trap, cd 25, no damage (frozen minion) | 5 x spawn, cd 0 |
| X-Ray Vision | cooldown only (cd 100), no visible effect | 4 x same |

### 2.2 Run 2: stat-by-stat merge

Every version now behaves as its base power **with its own deltas** (Consume 75 dmg + cd 60 for all 6; Detonate 900
dmg for all 5, Atomic Joker cd 100; Atomic Poison Ivy X-Ray cd 85; every group's versions get the base cooldown).
The merge alone fixes the stats of the 50 versions that lost some (the three Super Strength copies with no own list
were already full).
Groups still without their main effect: Super Strength (6), Teleport (5), X-Ray Vision (5, nothing visible),
Meteor Drop (6, no damage), Trap (6, no damage). See section 3.

## 3. Per-group findings (with the stat merge)

C = checked in data / the VM run, P = probable.

| Group (n) | Verdict | Evidence |
|---|---|---|
| Consume (6) | works | 75 damage to the minion, cd 60 (C) |
| Detonate (5) | works | 900 damage in 4 hits around the target, status, cd 120 / 100 (C) |
| Healing Wave (4) | works | `SpendCost(HealAmount)[vital 2]` heals self + allies in range (+50 seen at 30 % health; not a `heal` call, so the probe's heal counter misses it), status icon `0x48000832`, cd 120 (C) |
| Invulnerability (5) | works | self status `0x48000FF4`, cd 180 (C) |
| Psychic Assault (8) | works | status on the target, cd 120 (C) |
| Super Speed (4) | works | self status, cd 120 (C) |
| Surveillance Camera (5) | works | spawns `0x40000265` (charges `MaxCharges` / `NumCharges`, recharge timer, no cooldown by design) (C) |
| X-Ray Vision (5) | works (unverifiable headless) | S1: attribute modifier, scriptlet, status icon `0x4800093B`, `CreateAura 0x48000F21` (reveal), cd 100 / 85; nothing to reveal in the test (C nodes run, P effect) |
| Meteor Drop (6) | partial | spawns the meteor `0x4000044F` (scripts `0x34000167` thrown-object + `0x34000347`), cd 90; no damage: `0x34000167` sits in S5 waiting for `0x1000001D` (thrown) / `0x10000035` (flight end), which nothing raises on a SpawnEntity'd (not launched) entity (C) |
| Trap (6) | partial | spawns the trap `0x40000482`, charges + cd 25; the trap entity has **no 0x8E script** and `Data.record` finds no template for it, so nothing ever triggers it (C); the trigger lives in data the server does not read yet (P: its template in another pack / a hotspot) |
| Super Strength (6) | broken | S2 -> S4 on the target, `RaiseEvent 0x10000037` on it, then waits for **`0x100000BB`** (the lift's end, graph `state_to_locomotion`) forever; S3 (carry, second press = throw) is never reached. Needs a liftable map object as target (P) and the pickup event the old server faked (`icserver/finale.py` EV_TO_LOCOMOTION) (C) |
| Teleport (5) | broken | S0 -> S1 (Cast) -> S0: the target check `CheckRelation[4] & IsKind[0x90150] & IsAlive & (...) & !IsKind[0x4000] & HasFlagAttribute[0x1000104A]` fails: an ally minion passes all but **`HasFlagAttribute 0x1000104A`**, a turret fails `IsKind 0x90150` (C). No record or script sets `0x1000104A` (only `0x34000304` and Lex's drone `0x340005D8` mention it) (C); P: a flag the original server put on teleport-eligible allies |

Counts: **42 working**, **12 partial** (Meteor Drop, Trap), **11 broken** (Super Strength, Teleport) of 65 — with
the stat merge. **As is**: 8 of the 12 base powers work (the same 4 groups fail); of the 53 versions the 5 Consume
and 4 Detonate ones do no damage, and every version except Atomic Joker, Atomic Poison Ivy and Catwoman (own
cooldown stat) and the 3 full Super Strength copies has **cooldown 0** (castable on every press) and lost its range /
duration / radius stats: as is, only 8 + 1 (Atomic Poison Ivy X-Ray) work as designed, 24 cast with wrong stats (mostly cooldown 0), 32
fail.

None of the 12 Stolen Power scripts has a row in `data/skill_hooks.tsv` (graph cast timings): their cast states end
on the `graph_exit_fallback` (3 s) or on Cast's own result, and graph events (`0x100000BB` lift end) are never raised.

## 4. Client side (HUD, picker)

- **Slots 7 / 8 on the HUD** (C, `ics/world.py` champion properties): `0x100008F0` / `0x100008F1` carry the merged
  block (script, targeting, stats, icon `0x10000302`, name `0x100001C0`) — the client reads icon, name and tooltip
  stats from it (`GM_Skill.InqSkillToolTipInfo` / `RequestStolenPowersForCharacter 0x1000030F` are local queries over
  those tables). 9 versions have no icon of their own and inherit the base one through the key merge (C). With the
  stat list replaced, the tooltip, range indicator (18) and cooldown shown are the version's deltas only (P).
- **Ranks**: the client's CanActivate takes the champion level for slots > 5 (`0x863CE0`, full-combat-skills.md) so
  `0x100000AF` (slots 0-5) does not need 7 / 8 (C).
- **Cooldowns**: `CastWorld.start_cooldown` sends `0x20F8` for slot 7 / 8 like any slot (C); with stat 15 missing
  the scripts start a 0 s cooldown and no `0x20F8` is sent (`seconds <= 0` returns).
- **Keys D / F**: orders arrive as `0x20EE` with ability 7 / 8; `Session.ev_order` -> `World.cast` is generic (C).
- **Picker / account**: `0x20B8` lists all 65 as ContentType 2 (`grant_all_stolen_powers`), the lobby answers
  `0x2064` / `0x2017` with `0x2004`, `0x207D` changes the pair (persisted per champion, `Account.set_stolen_power`)
  and the pair reaches the match (`World.stolen_choice`) — covered by `tests/test_session_flow.py` (C, simulated
  client). The real client has never sent `0x207D` / `0x2064` / `0x2017` in the current `logs/server.log` (all
  matches used the default loadout pair). Every one of the 53 versions carries the unlock rule `0x10000922`
  (champion level 5 + owned) and `0x209D` reports every champion at level 1 unless played: P the picker shows only the
  12 base powers as selectable until the version's champion reaches level 5.

## 5. Fixes, ranked by powers fixed

1. **`ics/gamedata.py` `Data.stolen_power`** — merge `0x100004B4` stat by stat (version entry replaces the base entry
   with the same `0x100004B6`, the rest kept), new `[ics] stolen_stat_merge = true`. Fixes the stats of **50
   versions** (damage, cooldown, range, duration) on the server and in what the client shows (tooltip, range
   indicator, `0x20F8` cooldown). Verified headless (run 2).
2. **Meteor Drop (6)** — `ics/script_nodes.py` SpawnEntity (`0x100000A0`) / `ics/world.py CastWorld.spawn_entity`: an
   entity spawned with the thrown-object script `0x34000167` must get the thrown sequence (`0x1000001D`, then
   `0x10000049`, then `0x10000035` at the end of its fall — stat 19 = 2 s delay) as a launched entity does
   (`Missile` carried path, `spawned_entity_events`). P on the exact order; the states are in section 3.
3. **Trap (6)** — `ics/gamedata.py` `Data.record` / `entity_scripts` do not find template `0x40000482` (nor the
   meteor's `0x4000044F`): index the pack that holds them, then read the trap's trigger (scripts / hotspot).
4. **Super Strength (6)** — `ics/world.py` (CastWorld hook on `RaiseEvent 0x10000037` from `0x34000164`): raise
   `0x100000BB` on the caster's script after the lift time (as `icserver/finale.py` did), and give PvP maps liftable
   objects (layout props on carriers, `IsKind 0x1000`); the throw then runs `0x34000167` on the object.
5. **Teleport (5)** — find who sets attribute `0x1000104A` (REA: constant in the exe, the client CanActivate target
   filter) and set it on allied minions / wards (`ics/combat.py` flags) — P until found.
6. **Cast timing (all 65, cosmetic)** — `tools/graph_hooks.py`: none of the 12 scripts has a row in
   `data/skill_hooks.tsv`; find the graph that holds the Stolen Power states (P: a shared behaviour graph, not the
   champions') so casts end on their clip triggers instead of the 3 s fallback.
7. **Picker unlocks (53 versions in the UI, P)** — `ics/session.py` account data: report owned champions at level
   >= 5 in `0x209D` (or a `[ics] stolen_versions_unlocked` key) so the client's `0x10000922` rule lets the versions be
   picked; confirm in the client first (`tools/diag.py` on PowerPicker).

Side note: `python tools\script_decoder.py --help` runs the `all` mode and rewrites `data/script_trees/` (gitignored
cache, regenerated identically from the install).
