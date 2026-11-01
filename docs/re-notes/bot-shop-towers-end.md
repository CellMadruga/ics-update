# Bot champions: shopping at base, tower awareness, nothing after the match ends (2026-10-30, tester report 15:30)

Confidence: **C** = confirmed in code / data / logs, **P** = probable, **G** = guess, **O** = open.
Run: Crime Alley v AI, Atomic Green Lantern vs AI Poison Ivy (`0x40000AAE`), 16:37-16:58, surrender at 16:58:43.750.
Code: `ics/match/bots.py`, `World.combat_frozen` (`ics/world.py`), `Match.end` -> `BotManager.freeze`.
Tests: `tests/test_match.py bot_shop_towers_end_1530` (21 checks).

## 1. Shopping

Tester: "the AI buys one item at a time as it can upgrade it, and when it finishes it moves on to the next. When it
reaches the base it should buy or upgrade the item it can afford, otherwise wait for gold to upgrade the one it has
bought, in order."

What the log shows (C, server.log of the run):

| Time | Event | Where |
|---|---|---|
| 16:45:20-24 | 4 buys (0x925, 0x929, 0x4E9, 0x4FD), one per second | base aura (entered 16:45:20.258) |
| 16:48:47.959 | Poison Ivy defeated (recall cut) | lane |
| 16:48:48-50 | 0x495, 0x4FA, 0x4C0 | **dead, in lane** |
| 16:50:36.004 | 0x53B (16 credits left) | dead 0.2 s |
| 16:52:43-44, 16:53:06.966 | 0x53A, 0x4C4, then 0x4AB with **1 credit left** | dead (the last 24 s after the death, P: still dead), the trickle (2 credits/s) paid it |
| 16:55:41.543 | 0x48F | dead 0.7 s |

So most buys came while the body lay in the lane: `bot_shop_in_base_only` let a dead bot shop (the player's client rule:
dead champions may shop, shop-items-inventory.md 3.2), every second, so each tier went the moment the income paid for
it - "one item at a time as it can upgrade it".

The original's rule for bots (C data, P meaning): the bot script `0x340007E2` (encounter `0x10000B41`) runs its shopping
node `0x10000186` in a graph gated by `HasFlagAttribute 0x10000A23`; `0x10000A23` is the may-shop attribute the base
aura status `0x48001109` adds (crime-alley-missing-elements.md; traffic: `modifier 0x10000a23 removed (0x20e8)` when the
bot leaves the aura). A dead bot lying outside its base has no such attribute: **bots shop only inside their base
aura**. There is no "shop anywhere" switch for bots in the data (`shop_anywhere` is the player's HUD flag).

The build order is the champion's default loadout `0x10000CEB` -> recommended artifacts `0x10000478` (the shop's
Recommended row, 0x2078). The list is grouped by line, tier by tier (C, e.g. AWW `0x400003EC`: 0x4CF; 0x925 -> 0x929;
0x4F2 -> 0x4B7 -> 0xD1A; 0x4E3 -> 0x4A9 -> 0x48D -> 0x4D0; ...; Poison Ivy: 0x504 -> 0x4E9 -> 0x4FD -> 0x495; ...).
Infinite Crisis has no components: a line's lower tier is the "component" of the next (cost 0x1000036C is cumulative,
the shop charges cost - cost of the held tier).

ics (`BotBrain.plan` / `shop_visit`, `[ics] bot_shop_plan`):

1. Only inside its base aura (`in_base_aura`, Match._auras_tick); dead outside it: nothing (`bot_shop_when_dead`).
2. A visit simulates the purchases on a copy of the inventory: the first list entry not owned (an owned item's `prev`
   chain counts as owned) - with `bot_shop_upgrades_first` the next tier of a held line before a new line, both in
   list order. A step the shop can never sell now (not offered, slots full) is passed over; the first step it cannot
   pay ends the visit: it **saves** for it (it never buys a later, cheaper line instead). All buys go at once, one
   0x20E2.
3. Going home to shop: in push / fight, when the plan would spend `bot_shop_recall_value` (1250) credits or more, no
   enemy champion within `bot_shop_recall_safe` (12 m), and `bot_shop_recall_gap` (45 s) since it left base: state
   retreat (walks or Recalls home, as for low health). Low health still sends it home at `bot_retreat_health`.

Test (C): 1450 credits at base -> 0x4CF, 0x925 and its upgrade 0x929, 700 kept for 0x4F2 (750); then 1700 -> 0x4F2 and
it saves 950 for 0x4B7 (1000 more) instead of the affordable 0x4E3 (750); then 0x4B7 replaces 0x4F2.

## 2. Towers

Tester: "check that they don't dive into the towers so much chasing minions".

Before (fase3-ir, C code): a minion was taken unless an enemy shooter covered **the minion** with no allied minion
anywhere in its range (`turret_danger(minion_cover=True)`): one allied minion was "cover" even when the turret shot the
bot, and the point the bot walks to to hit it (`World._attack_step` stops at reach x 0.8) was never checked. The
shooters' priority (C, `Units.think`): an enemy champion that hit an allied champion (`champion_aggressor`, 2 s), else
the current target, else the closest minion, else a champion. So a turret with no minion left takes the bot at once,
and hitting a champion under it turns it on the bot whatever minions are there.

ics (`[ics] bot_tower_awareness`, default true):

- `unsafe(pos)`: an enemy shooter (turret, core turret, inner turret, foundry) whose range + `bot_tower_margin` (1.5 m)
  covers pos, unless it is busy with one of the bot's minions (`tower_busy`) **and** at least `bot_tower_min_tanks` (2)
  of them stand in its range.
- A minion is taken only when neither its position nor the bot's attack point is unsafe; a structure when the attack
  point is not (allied minions tanking it).
- An enemy champion an enemy shooter covers (it or the attack point): only while every such shooter is busy with the
  bot's minions and the bot has `bot_dive_health`, or for a near-certain kill (`sure_kill`: health share <=
  `bot_dive_kill_share` 0.2, health <= attack damage 0x10000B76 x `bot_dive_kill_hits` 2, within reach + 2 m, the bot at
  `bot_dive_health`). The fase3-ij leash rules (`bot_dive_needs_tank`, `bot_leash`) still apply.
- `step_out`: a bot (push / fight) standing in an unsafe range walks back along its lane out of it before it is
  targeted (state evade, 0.5 s); the existing S6 evade (`bot_turret_aggro_retreat`) still handles a bot already
  targeted.
- `push_point`: when the point behind its lead minion is unsafe, it waits at the last lane point out of that range.

## 3. After the match is over

Tester's video: after the surrender passed the bot kept casting / attacking ~9 s and "killed" the player after the
match was over.

C code: `Match.tick` returns early once `over` (no `units.tick`, no `bots.tick`), and `Match.end` cleared the match
units' targets, but **not the bots'**: `World.tick` keeps running every session tick (`Session._tick`), and its
`_attack_step` keeps casting slot 0 for any entity with an `attack_target`, missiles in flight still land, and
`World.damage` had no end check. (In this log the bot was walking out of base at the end, so nothing was sent after
16:58:43.750; the video's run had the bot in a fight - P.)

ics (`[ics] match_end_freeze_combat`, default true): `Match.end` -> `BotManager.freeze` (no target, no path, a stop
state for a moving bot, brain state "over"); `World.combat_frozen()` (match_ended and the key) makes `World.damage`
return, `World.cast` refuse every entity but the local champion, and `World.tick` drop any attack target.

## 4. Tower tactics (tester report 18:12)

Tester (translated): "now it doesn't go in to attack the tower. If it can attack me and get out without the tower
hitting it, it should attack me; if it can go under the tower because there are minions, it should and attack the tower;
if the tower targets it, it should leave its range - more natural, as if it were a player."

Run: Crime Alley v AI, Atomic Green Lantern vs AI Atomic Joker (`0x40000D2F`, mid), 18:00-18:11.

Why it stopped (C, logs):

| Evidence | Meaning |
|---|---|
| 13 x "steps out of turret mid t1's range (its minions do not hold it)", 2 x "backs off" | the 15:30 `step_out` fired all the time |
| bot hits on turret mid t1 only 18:10:36.8-18:10:41.2 (Joker basic 88.86), then "steps out" at 18:10:41.087 | the turret's 0x10000C66 went to 0x0 at 18:10:41.031 |
| traffic: after each minion death `0x10000C66 = 0` for 0.1-0.6 s before the next minion | `Units.think` re-picks at its next 0.5-0.8 s think |

So `tower_busy` (the target is a live minion now) failed at every minion death, `bot_tower_min_tanks` 2 failed with one
minion left, `pick_target` took the enemy minions before any structure, and from the push point's waiting spot
(range + 1.5 + 1 m from the turret) the turret was beyond `bot_sight` 9 m. Headless (player kept at home, 300 s, AWW
bot mid): 2 bot hits on the turret with the 15:30 rules.

The turret's rules (C code): keeps its target while it is within range + radius + 0.5; with none, the closest minion in
reach before a champion; an enemy champion that hit an allied champion in the last `match_call_for_help` (2 s) and is
within its reach first, re-thought at the hit (`match_call_for_help_now`) - the hitter's position counts, not the
victim's. Shots every 1 / attack speed s (`Units.attack`).

ics (`[ics] bot_tower_tactics`, default true; false = the 15:30 rules of 2):

- `holds(shooter)`: the shooter is not on the bot, the bot is no champion aggressor (`Match.aggressors`, 2 s), at least
  `bot_siege_min_tanks` (1) of its minions are in range, and their health together exceeds the shooter's attack damage
  x (`bot_siege_tank_shots` (1) + the shots it fires while the bot walks out of range + 1 m: `escape_shots`,
  `bot_siege_escape`). A moment with no target still holds while tanks remain (the shooter takes a minion next).
- Siege: `siege_target` - an enemy structure within max(`bot_sight`, `bot_siege_sight` 14 m) it can hit from a held
  point, shooters first, before minions (`bot_siege_first`); `Match.protected` still decides what is attackable.
- Retreat: not held while in range -> `step_out` (the tank is about to die, the wave is gone, the bot just hit a
  champion); targeted -> `evade`, and back in as soon as `holds` is true again (the turret dropped the bot and is on a
  minion), with no `EVADE_SECONDS` wait.
- Champions (`champion_ok`): the point it hits from is out of every shooter's range + `bot_tower_margin` (a player at
  the edge of his turret's range is fair game, a ranged bot hits him from outside); or a short trade: every shooter
  covering that point held, bot health >= `bot_trade_health` (0.5), the point at most `bot_trade_depth` (2 m) inside
  range + 1, and when the hit lands now the shooter's `next_attack` is later than `bot_trade_windup` (0.4 s) + the walk
  out; after the hit the bot is the aggressor -> not held -> it steps out; or a near-certain kill (`sure_kill`, as
  before). `bot_dive_needs_tank` (leash) gives way to `champion_ok`.
- Near an enemy shooter (range + margin + 3 m) the brain re-decides every `bot_tower_react` (0.2 s) instead of
  0.5-0.8 s.

Headless lane with the tactics (same setup): 11-18 bot hits on the turret, its health 2500 -> 1209-1446, the bot never
killed; the turret took it once in 300 s (two tanks died while it walked in, ~97 damage, it walked out). Tests:
`tests/test_match.py bot_tower_tactics_1812` (20 checks: siege with one tank, stays through a target gap, leaves before
the last tank dies, out when targeted and back when the turret is on a minion, steps out alone, a player at the edge
taken from outside, not deep under a free or tanked turret, the trade timed to the turret's shot and not below
`bot_trade_health`, out after the hit, the lane run).

Open (O): the original's own bot tower logic is not in the data (units-and-ai.md 5.1); these thresholds are the
tester's description of a sensible player, not recovered values.
