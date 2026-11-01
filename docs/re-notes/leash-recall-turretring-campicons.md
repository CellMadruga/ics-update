# Leash, recall effect, turret warning ring, camp drop icons (fase3-ij, 2026-10-29)

Tester report 2026-10-29 15:30 (runs 14:19-14:34 and 15:17-15:21: Crime Alley v AI, Gotham Heights v AI).
Tags: C = confirmed (code / data / traffic), P = probable, O = open.

## 1. Leash: minions and AI champions follow the champion across the map

Report: "in Crime Alley I can pull a wave around and bring it behind my tower. Minions should chase me while I am within
an attack range and, if I leave it, go back to their lane. Same for the AI champions."

### 1.1 What the data has (C)
- `0x3A000026` (every minion, jungle unit, structure): GetBestPerceivedTargetInterval_Min 0.5, _Max 0.8, AIActive; the
  vision 0x10000133 and the attack's stat 18. No aggro, chase or leash distance in any 0x3A record, template or script;
  the exe has no AI strings (units-and-ai.md 5.1). Starro's parasite 0x3400053A (the scripted twin of the minion AI)
  re-targets every 0.5-0.8 s and follows its owner; it has no leash either. The leash is server code: authored.
- Camp units have flag 0x1000055A = 1 (home return, P) and ics already leashes them to their home (match_camp_leash).

### 1.2 Cause (C, code)
`Units._valid` kept a minion's target while it was within `max(match_minion_leash 12, vision + 2)` m of the **minion**,
with no anchor: a champion walking away at about the minion's speed stays within 12 m forever, so the wave followed
him anywhere. The bots' `pick_target` re-picked a champion every 0.5-0.8 s within bot_sight (9 m) and, with allied
minions near the enemy turret ("cover") and 70 % health, followed him under and behind his tower.

### 1.3 Fix (`ics/match/units.py`, `ics/match/bots.py`)
- Minions (`[ics] match_leash_rules`): a non-structure target is kept only while it is within the acquisition range
  (`max(vision, reach + 1)`) + `match_minion_chase_margin` 1.5 m and while the minion is within
  `match_minion_leash_anchor` 8 m of the lane point where it left its lane (`MatchUnit.leash_from`). Past either: the
  target is dropped and ignored `match_minion_leash_ignore` 4 s, and the minion walks back to its lane (resume_lane)
  taking no target until it is within `match_minion_lane_rejoin` 2 m of the lane polyline (at most
  `match_minion_return_max` 6 s). Structures as targets are never leashed. false = the old 12 m rule.
- Bots (`[ics] bot_leash_rules`): an enemy champion standing in an enemy shooter's range + 1.5 m is taken only while
  that shooter is busy with one of the bot's minions (`bot_dive_needs_tank`); a chase is dropped when the bot is more
  than `bot_leash` 10 m from where it began or the champion is more than bot_sight + `bot_chase_margin` 2 m away, and
  the champion is ignored `bot_leash_ignore` 3 s (the bot goes back to push its lane).
- Log lines: "<minion>: leash, drops <target> (...)", "bot <name>: leash, stops chasing <champion>".

### 1.4 Tester should see
A minion chases you only while you are near it; kite it off the lane and it turns back after ~8 m and walks to its lane.
A bot stops chasing you at your turret (unless your turret is shooting its minions) and after ~10 m of chase.

O: the original's numbers (the prototype used LoL's 700 / 1200 units); tune the keys from the tester's feel.

## 2. Recall: sound and teleport, no visual

### 2.1 The script 0x3400000A (C, `python -m ics.script_model 0x3400000A`)
- S2 enter (channel start, T4 on skill used 0x1000001D): RaiseGraphEvent Recall_Start `0x100005BA`; StartScriptlet
  `0x10000223` with `0x1000033E` = RecallDuration (stat 14, 8 s) and fx `0x1E00009C` (handle kept); SetCleanupFlag;
  RunScriptlet Fidgets_Disable `0x10000320`; SetHidden? `0x100001A9`[1]; UINotify `0x100000C7`[89 9 2]; BeginTeleport
  `0x1000007D`; RemoveStatus; RecordPlayerAction `0x10000108`[9]; SetUntargetable? `0x100000C8`[1]; RaiseGraphEvent
  Emote_Abort `0x100001F2`; SetCameraMode `0x1000014B`[1 5].
- S2 exit: Fidgets_Enable `0x10000321`, EndTeleport `0x1000007F`, StopScriptlet(handle), camera mode 0, `0x100001A9`[0].
- S4 (timer): Recall_End `0x100005BB`, teleport `0x10000025`(HomePosition), arrival scriptlets, `0x10000108`[8];
  S3 (moved 0.25 m, damage, death, interrupt): Recall_Abort `0x100005CF`.
- Recall_Start is a main-machine wildcard only in Zod's graph (deep-scan-animations.md 2.1); the 53 other champion graphs
  drop it, so there is no champion recall animation in the data except Zod's (C). The visible channel is the fx.

### 2.2 Cause (C traffic, P mechanism)
Traffic 14:31:53.788: `0x100001E3` (Recall_Start), `0x10000223` (fx, 59 bytes: 0x1000033E = 8.0, 0x1000050A =
0x1E00009C), `0x10000320` Fidgets_Disable in the same tick, then `0x100001E3` Emote_Abort at .817. A later scriptlet
on the same object ends a looping run on the client (the Shards sphere case, fase3-ib / -ii, world.py
resend_looping_after_scriptlet), so the 8 s fx ended at once; its one-shot sound still played.

### 2.3 Fix
`[ics] start_scriptlet_hold = ["0x3400000A"]`: a StartScriptlet of these scripts whose variables carry a duration
(0 < s < 120) is registered as a looping key for that time (`CastWorld.run_scriptlet`, `hold_next_scriptlet`); the
existing `resend_looping_after_scriptlet` (0.35 s) re-sends it after Fidgets_Disable / Emote_Abort with the **same run
number** (looping_resend_same_run: a live run is only signalled, an ended one restarts). Its StopScriptlet (S2 exit)
signals the run and removes the loop (`World.signal_scriptlet`). [] = as before.

### 2.4 Tester should see
The recall's channel effect around the champion for the 8 s, then the teleport as before.
O: if the fx still does not show, `python tools\diag.py --bundles` (end of a persistent attachment, with its stack)
during a recall tells what ends it.

## 3. Turret warning ring (green / yellow / red)

### 3.1 Registration 0xA7CA20 (C, decompiled + disassembled)
The manager (ctor `0xA891A0`, built at client start by `0xA91E30`) subscribes its interface `0x1605074` to the event
list `[0x186CF14]` (`0x68EDA0`); slot 1 = `0xA7CA20(iid)` (entity added; no direct caller). Gates in order:
`0xA7CA29` disabled byte, `0xA7CA33` view-match, entity lookup (`[0x1B67258]` vt+0x58), **`0xA7CA63`
`0x9D0180(ent, 0x10)`**: the Turret bit of the PerceivedType, read from the unit component `[ent+0x84]` cache `+0xA4`
when it exists, else from property 0x1000019D; `0xA7CA81` 0x10000C5D; `0xA7CA9A` `0x85C130` allied -> refused;
`0xA7CAC6` already registered; then 0x10000C5B, 0x10000C66, alive `0x9CFAF0`, **range `0x9CFC40`** (cache `+0x8C`,
initial -1.0, else 0x10000133) and `(r + 1)^2 <= 0` refuses (`0xA7CBA5`). Listener `0xA8DFB0` (0x10000C5B, 0x100000FA,
0x10000B2D, 0x10000C66) updates only entries already registered (`0xA17A60` lookup).

### 3.2 Cause (C traffic)
The enemy turret's creation bundle (traffic 15:17:47.403, `turret mid t2`) carried 0x10000C5D = 1, 0x10000C5B = 1,
0x10000133 = 9.0, team, LifeState, but **no 0x1000019D**: the unit flags went as changes 6 and 10 s later (15:17:53,
15:17:57). At entity add `0x9D0180(ent, 0x10)` read 0, so no structure was ever registered and no ring could show.

### 3.3 Fix (`ics/match/units.py _properties`)
`[ics] turret_warning_flags_in_bundle`: a structure's unit flags (0x210 turrets, 0x810 dampener, 0x4010 core) ride in
its creation bundle and go again as a change (0, then the value: `refresh_flags`) for the caches; an enemy
structure's range 0x10000133 also goes as a change (0, then the radius). false = as before.

### 3.4 Open (P)
Whether `[ent+0x84]` exists at entity add. If it does, the cache is filled only by changes (fase3-gd, diag --target
2026-10-21: flags sent in the creation table stayed 0 in the cache) and registration still fails; then the event
list `[0x186CF14]` (who fires it, whether it fires again later) decides. `python tools\diag.py --ring` logs every call
of 0xA7CA20 and the gate it stops at ("HOT RING ..." lines: Turret bit al, c5d, allied al, range bits, registered).

### 3.5 Tester should see
Near an enemy turret: a ring, yellow with one of your minions under it, green with two or more, red when it shoots you.
If not: run `python tools\diag.py --ring` in a second console and send diag.log.

## 4. Jungle camps leave reward-like icons

### 4.1 What is spawned on a camp kill (C)
- Every camp unit: `_reward` credits + floaty (`+N credits over ...`, 0x100004D6), the death (`dead` bundle).
- The Heavy Tripod (`0x40000CA1` / `0x40000CA0` per side) runs its entity script `0x3400007D` on 0x10000007: S1
  `GetTeam(SELF)` then `SpawnEntity [.. 0x400005E1 1 0x1000009C]` (team = the dead creature's own team, KillerIID is
  read but unused). Traffic 12:15:45.691 "spawn 0x400005e1 of camp 1 0x40000ca1".
- Template 0x400005E1: icon `0x10000083` = 0x130006D3, minimap category `0x100004DA` = 5, `0x100006F1` = 6,
  `0x1000019D` = 4, `0x10000D8B` = 0x80000; world state 0x2E000FBB with the common tables plus `_Upgrade_Loot`,
  `_SUpgradeSystem_OnCurrencyGained` and the `Vfx_Item_*` keys; **no entity script**. ics made it inert
  (spawned_inert_classes) and nothing ever collected or removed it: its icon stayed on the ground and on the minimap.
- The original 2v2 Clash recording (crime-alley-2v2-video.md 4) shows "+50 / +100" credit pops and wreckage after a
  camp kill and the camp's minimap diamond only while it lives; no lasting icon.

### 4.2 Fix
`[ics] spawned_skip_classes = ["0x400005E1"]`: SpawnEntity of a listed class is skipped and logged ("spawn 0x400005e1
of ...: skipped"). [] = spawned as before. The CA Raider's pad 0x40000C49 is not affected.

### 4.3 Tester should see
No icon left where a heavy camp creature died; the "+credits" pop as before.
O: what the original server did with 0x400005E1 (a loot pickup for the killer's team, collected on contact or at once,
P from its `_Upgrade_Loot` / currency tables).

## Tests
`tests/test_match.py` `leash_turret_ring_camp_drop` (15 checks): the enemy turret's bundle flags, the changes, a kited
minion dropped within anchor + 2 m and back by its lane, the out-of-range drop, the old rule switch, the bot's tower and
leash rules, the skipped heavy drop and the held recall fx.
