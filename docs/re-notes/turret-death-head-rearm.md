# Turret heads lost (the `--heads` trace), lane turret death and wreck (2026-10-30, tester report 18:12)

Tester run 17:59-18:12 (Crime Alley v AI, Atomic Green Lantern vs bot Atomic Joker `0x40000D2F`, match start
18:00:43). Logs: that run's `server.log`, `traffic.log`, `diag.log` (session scratchpad `logs1800/`). Tags: **C**
confirmed (logs, data, decompiled exe `re-work/decomp`, tests), **P** probable, **O** open. Scripts in the session
scratchpad (`heads1812/`); nothing of the game copied.

## 1. "The heads of the towers got lost" (C trace, O cause, P mitigation)

### 1.1 Which diag ran when (C, diag.log)
| lines | time | probe | breakpoints |
|---|---|---|---|
| 1-1615 | 18:00:46-18:03:29 | `--hover` (+ the default skills set) | 12 |
| 1617-2400 | **18:03:38-18:04:29** | **`--heads`** (602 0x8D, 100 run removals, 27 child ends, 50 render-effect ends) | 4 |
| 2402-2489 | 18:04:36-18:12:25 | `--strip` (statics steps did nothing: started after the map load) | 2 |

### 1.2 Who is who (C)
World entities start at `0x0200000000000100` in creation order (`ics/world.py ENTITY_BASE_ID`); the bot took 0x100 in
the lobby (server.log 18:00:43.561), then the structures in the order of the spawn traffic (18:00:43.657-44.331):
core 0x101 / 0x102, Power Core Turret t1 0x103 (platform 0x104, cylinder 0x105, flag head 0x106), t2 0x107-0x10A,
**dampener 0x10B / 0x10C, lane turret t1 0x10D (plate 0x10E), t2 0x10F (plate 0x110)**, foundries 0x111 / 0x112
(checked with the same config in `heads1812/ids.py`).

### 1.3 What the trace shows (C)
- Spawned-child ends (`0x666b40`) by owner: 0x2 (champion) 6, 0x100 (bot) 3, foundries 0x111 / 0x112 5, minions
  0x156 / 0x163, client-local `0x81000000_xxx` 10 (minion missiles); render-effect ends (`0x65ca30`): minions, the
  champion, client-local. **None with a structure's IID.**
- During the window the blue lane turret 0x10D fought four times (traffic 18:03:45-47, 18:04:03-06, 18:04:06-09,
  18:04:17-19: `0x10000C66` target + 11 shots `0x100002E0` / `0x1000029D`, instances 0x2A5 ... 0x421 in the 0x8D
  lines); no run removal inside the 0x8D handler followed a shot (the in-handler removals, stack `1365cb 227abe
  227e97`, follow only `0x100002F5` / `0x10000223` on other objects).
- Its **first** fight was 18:03:08-18:03:25 (target 0x14A at 08.334, 12 shots 12.388-24.788), while `--hover` ran;
  the tester stopped it at 18:03:28 and attached `--heads` at 18:03:38. The red lane turret 0x10F and both dampeners
  got **no message at all** after 18:00:55.9 (no target, no shot) in this match.
- So the head was not ended while the probe ran: it had gone before (P: in the first fight, the moment every report
  since fase3-ip names: 11:23 "when attacked", 12:05 "when it targeted me", 15:30, 18:12). What ended it is not named.

### 1.4 Client facts read on the way (C, decompiled)
- Run start `0x57C260`: counts the live runs of the same scriptlet on the component and refuses a new one when the
  count reaches the definition's limit (`0x51F080`, property 0x479, default 1) -> `0x80044321`.
- `0x536C40` runs the scriptlet and removes the run at once (`0x57BAF0`) when it is not live (`0x514B70`: state +0x8C
  1 / 3 / 4, or 2 with children / flag): a run that holds a spawned child stays.
- `0x57BDC0` (create): a run started with the "no instance" value `DAT_0185F2B0` = 0xFFFFFFFF (local type-23 runs)
  takes its id from a per-component counter (+0x50, post-increment); server runs keep the server's instance number.
  Both go into the same unsorted id list (+0x14 ids / +0x18 runs, linear first-match lookup `0x57B390`), and a removal
  (`0x57BAF0` -> `0x57B400`) drops the FIRST entry with the run's id. ics numbers its runs from 1 per session, so a
  structure's start runs (Vfx_Active 0x0F, Vfx_AI_Active 0x36 / 0x37 on the lane turrets) sit in the range the body's
  own local runs (one per shot at least) reach. O: whether that collision is what ends the head (it would explain "after
  the turret fights"); the counter's start value was not found (its component's constructor is not decompiled).
- A server 0x8D whose instance matches a live run signals it (`0x57B9D0`); the spawned-child ends of the champion in
  the trace come through that path (`17b947 17c517 17cc59 227e52`).

### 1.5 Mitigation (P) and next probe
- `[ics] match_turret_head_rearm` = {"after": 3.0, "gap": 0.2, "min_gap": 20.0} (`Units._head_rearm_later`): when a
  structure whose head is its own Vfx_AI_Active child (no server head; the lane turrets) drops its target, and still has
  none "after" s later, the server sends 0x11F for **every** Vfx_AI_Active run of the body (instance 0xFFFFFFFF: an
  old head that is still there ends, so never two) and "gap" s later a new Vfx_AI_Active 0x8D; at most once per
  "min_gap" s. The head comes back after each fight whatever removed it. {} = off.
- Next probe if the tester wants the cause: start `python tools\diag.py --heads` **before Launch** (as `--strip`
  asks), then fight with the turret; the END line whose owner is 0x10D / 0x10F (or the dampener's 0x10B / 0x10C) and
  its stack name the trigger.

## 2. "The first 2 towers have no destruction animation" (C traffic, C data)

### 2.1 What was sent (C)
- Lane turret t1, 18:11:11.741 `turret mid t1 dead` (bundle), 18:11:15.751 `removed (0x3)`, nothing between (the
  same at 16:47:52.760 / 56.766): no death key, removed after `corpse_seconds` 4 s.
- The dampener (16:52:43.515 dead, 43.803 graph Death, 43.976 Object_Deactivate, body kept until 16:57:13) already
  plays its data death: Object_Deactivate (table `0x1D0005A1`) = graph Death 0x100001C0 (graph `0x1A000B15`: Deactivate
  clip 1.0 s, the body sinks), run Vfx_OnExplode, stop Vfx_Active. Not changed.
- Power Core Turret: `_Defeat_OnDead` since fase3-in (`match_structure_death_scriptlets`), body kept.

### 2.2 The data (C)
- The lane turret is the same body as the blue Power Core Turret (ws `0x2E000AA0`, tables `0x1D00035D` + base
  `0x1D000372` + `0x1D000600`). `0x1D00035D` `_Defeat_OnDead` = type-23 **run** (flag 0) of Vfx_OnExplode
  `0x10000079` (base table: render / particle blast), a type-9 branch (`0x1000000B`, `0x1000096F`, `0x1000093B`,
  `0x10000B0D`, `0x1000093A`, `0x10000711`), type-20 graph event **Death `0x100001C0`**. (Earlier notes called the
  first action a stop: its flag word is 0, as Object_Deactivate's run of the same key; Vfx_Stop's entries carry 1.)
- The class tables (`0x1D0000E8`, every unit) hold another `_Defeat_OnDead` (graph `0x100000AD`); the Power Core
  Turret's fall (no tester complaint since fase3-in) suggests the client uses the world state's (P).
- Graph `env_pvp_lane_turret_a_body_behavior` (packfile in `0xA0000162` / `0xA0000168` / `0xA00002E6`): machine
  Animation = Idle (`env_pvp_lane_turret_a_body_idle_a`, 5.98 s, the ring bones orbit) and **Death**
  (`env_pvp_lane_turret_a_body_die_a`, **0.1 s**, with DelayedModifiers, `RigidBodyRagdollControlsModifier` and
  `TurbinePoweredRagdollControlsModifier`): the rings fall by physics after the pose and lie there; the state has no
  exit, no fade, no timed end. The original's destroyed Power Core Turret (frame 70) keeps its fallen rings.
- Base `0x1D000372` Vfx_Stop = four type-23 stops: Vfx_Active (A9E particles + hum), Vfx_Targeting, Vfx_Event1,
  Vfx_AI_Active (the client-made head).

### 2.3 Fix
- `match_keep_body_roles` += "turret", "inner_turret": the wreck stays for the rest of the match (lane turrets never
  respawn; decided from the data: a ragdoll Death state with no end, as the Power Core Turret's remains).
- `match_structure_death_scriptlets` "turret" / "inner_turret" = ["_Defeat_OnDead", "Vfx_Stop"] (0.3 s / 0.5 s after
  the death bundle): blast, the rings fall, the head and hum go.
- Back to fase3-in: `match_keep_body_roles` ["core_turret"], `match_structure_death_scriptlets` {"core_turret":
  ["_Defeat_OnDead"]}.

## 3. Tests
`tests/test_match.py turret_death_head_rearm_1812` (8 checks): the lane turret's head is its own child; after a fight
nothing before 3 s, then the 0x11F stop (key 0x10000D63, instance 0xFFFFFFFF) and a new Vfx_AI_Active; none again
within min_gap; none when a new target comes first; a dead lane turret plays _Defeat_OnDead then Vfx_Stop and its
wreck stays 30 s later; with the fase3-in settings the body goes after corpse_seconds and no death key goes.

## 4. What the tester should see
1. A lane turret that fought: if its head went, it comes back (materialising) about 3 s after the fight.
2. A lane turret at 0 HP: a blast, its rings fall and stay on the plate; no head, no hum; the wreck stays.
