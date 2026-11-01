# Bot champions in the world (research + design, 2026-10-25)

Static reading of `ics/` and the earlier notes, plus template reads from the install (`UnitData.template`).
Confidence: **C** = confirmed in code / data, **P** = probable (strong inference), **G** = guess, **O** = open.

Problem (C, map-gaps-gotham-divided.md 5.1, map-gaps-coast-city.md 141, map-manifests.md): the lobby bots
(`ics/lobby.py`, `Slot.as_player()`) reach `Match._players()` as `{"iid", "name", "team", "index", "champion",
"bot", ...}` with no `"agent"`, so `Scoreboard` gets rows with `agent = None` and nothing is ever created in the world.

Side finding (C, code): `Match._players()` reads `g["player"]` and `g["agent"]`, but `as_player()` gives `"iid"` and
no agent, so in every **lobby** match the human's own row also has `player_iid = 0` and `agent = None`:
`score.by_agent(w.champion)` is None, his kills / deaths / assists / money never count, and he is not placed at his
slot's start by the match. The fix belongs to the same change (map `iid` -> `player`, attach `w.champion` to the
`lobby.me` row).

---------------------------------------------------------------------------------------------------------------------

## 1. What the client needs for a non-local champion

### 1.1 The object (C unless marked)

| Item | Value for a bot | Evidence |
|---|---|---|
| Message | event `0x4` bundle (`0xF2` class + `0xB0` + `0xBC`), as the local champion | `M.create_object`; full-entities-engine.md 5 |
| Class | the champion **variant DID** (`0x40......`) the lobby picked; its world state = template `0x510` | same as `World.create_champion` |
| IID | a world entity id from `World.new_id()` (`0x0200000000000100`+, top byte 2 = server object, so game component 34 exists) | full-entities-engine.md 4.2 |
| Player IID | the lobby slot's `iid` (`BOT_IID_BASE 0x0200000000F00000 + n`), sent as `0x10000064` on the agent | lobby.py; ui-complete.md 2.4 (OverheadVitalsDeluxe registers it) |
| Player object for the bot | **not needed for a first build (P)**: the local/remote decision is the local player IID `0x1B6A710` and its `0x100000CF`; colours use the local player's team, targeting uses the controlled champion (targeting-and-relations.md 2). Whether the overhead bar resolves the name through the player object is **O** (Flash): the agent carries `0x3CE` / `0x10000433` itself. Option `[ics] bot_player_objects` to create one (player class, `0x1000009C`, `0x100000CF` = agent) if the nameplate shows no name | |
| Movement | `0xB0` with `0x62 | seq | 1 | 0x0F` (mode 1, no controller IID) -> **remote module 1**, the same path the local champion uses today (ics never sends a controller IID) | client-movement.md 0, 1.1 (C) |

Because `ics` already drives its own champion as a remote, server-replayed entity, a bot champion is the
same object without the player link: there is nothing "local-only" in its movement or animation path (C).

### 1.2 Properties in the creation bundle

From `M.champion_properties` (the local champion's list) with the bot's values:
`0x1000009C` team, `0x100000FA` LifeState 4 (nameplate and every order check need 4), `0x10000167` level,
`0x10000142` XP, `0x3CE` / `0x10000433` name, icons `0x10000384` / `0x10000338` / `0x10000337`, `0x100005E4` move
speed (else the walk cap is 0 and it slides), `0x956` lighting, `0x10000064` = the bot's player IID, `0x7D2` table
list (`World.champion_tables`: class + world state tables, so its skill FX keys resolve), stat f32s
(`World.stat_properties`), `0x100006FE` attack speed (the attack clips' speed, sweep-property-listeners.md 4.11).

Leave out (C/P): `0x100001AF` skill points, `0x1000035E` currency, rank array `0x100000AF` and `SKILL_RANKS_PROPERTY`
(HUD of the controlled agent only), `0x100008F0/F1` Stolen Power tables (several KB each; only the local HUD reads
them, P), `0x10000A23` may-shop, `0x10000CD6`, `PROP_CAMERA_YAW`, `PROP_SECONDARY_VITAL` (P: harmless but only the
skills panel of the controlled agent reads it; keep it if the overhead bar should show Will, `0x972940` reads it at
creation for every entity with vitals -> **send it**, P).

Template values read from the install (C, `UnitData.template`, same for `0x40000086`, `0x40000BD3`, `0x4000002B`,
`0x4000015B`): `0x1000019D` PerceivedType = **8** (Character), `0x10000AA7` = 1, `0x100001C3` = 0x28,
`0x1000034C` = 0x1E, `0x10000133` vision = 12.0, `0x83C` = 2, `0x100006F1` = 2 (champion kind), `0x100004DA` = **2**
(minimap category: champion), `0x10000083` = `0x13000376` (map icon), `0x100008DA` = 1, `0x100005A6` = 3.
These live in the server-side 0x49 template, which the client does not read (targeting-and-relations.md 1c, C for
units), so the server sends them:

| Property | Kind | Value | Why |
|---|---|---|---|
| `0x1000019D` PerceivedType | u32 | 8 | validator 0x9d01d0 step 8 (8 is in DefaultBasicAttackTarget 0x555959 and DefaultCombatTarget 0x450109); **as a 0x6 change after creation** (0 then 8, as `Units.refresh_flags`): the unit component caches it only on change (fase3-gd, C) |
| `0x10000AA7` | bool | 1 | step 9 |
| `0x100001C3` | enum | 0x28 | step 10 + hover score |
| `0x1000034C` | enum | 0x1E | hover fallback |
| `0x10000029`, `0x10000249` | bool | 1 | status tag checks B / C (`[ics] unit_targetable_tags`, the structures' lesson) |
| `0x100004DA` | enum | 2 | minimap note "champion" (0xA5B190 -> 0xA4BD80) |
| `0x2A1` | bool | 1 | minimap note + fog source + hover (default true; send it so `PROP_HIDDEN`-style toggles work) |
| `0x10000083` | DID | template icon | minimap icon |
| `0x10000133` | f32 | 12.0, **allies only**, as a change (0 then value) | fog vision source (fog-vision-runtime.md: stored on change only) |

The game components (vitals `+0x80`, floaty `+0x90`, status icons `+0xC0`, upgrade `+0xA4`) are created from the
PerceivedType at construction (`0x9CFBF0`: unit component or property): the local champion of the same class gets
them, so the class data carries Character (P strong; the 0x42 vitals to the local champion never crashed).
Health bar = `0x42` vitals to the bot's IID (`World.vitals`, `client_vitals = True`), level = `0x10000167`,
team colour = client-computed from `0x1000009C` vs the local player's team (`0xA7B0D0`, C).

### 1.3 Target validity for the local player (C, targeting-and-relations.md 1b)

Relation 2 (teams 1 / 2), unit flags with a bit of 0x555959 and none of 0x80000, `0x10000AA7` = 1, `0x100001C3` != 0,
LifeState 4, plus statuses `0x10000029` / `0x10000249` true through the unit component. A dead bot must get
LifeState 2 by 0x6 (then the hover pick drops it and the target frame closes, 0x968DA0).

### 1.4 Movement replication (C, client-movement.md)

The client keeps a 9-state history and dead-reckons the newest state older than 0.1 s: `pos + velocity * dt`, with
velocity from heading + speed; error <= 2 m is corrected smoothly, > 2 m or a newer teleport byte snaps. So a
remote champion needs one state **per change of velocity** (new path corner, start, stop, heading change), not one
per tick, and an explicit speed-0 state to stop. A respawn / Recall / Bat Flight end bumps `tele_seq`.
`M.pvp_movement_state` (0x4 batch with only `0xB0`) already exists for this (P strong: same listener 0x60AFA0 as the
full bundle; not yet seen in the game -> keep `[ics] bot_motion_only` to fall back to full bundles).

### 1.5 Skills of a remote champion (C path, P result)

- Visuals are the server's `0x8D` on the caster's IID with the key in its `0x7D2` tables (`World.scriptlet` /
  `CastWorld.run_scriptlet`); the 0x8D reader `0x634F20 -> 0x627E20 -> 0x6279D0` takes any IID (originator test only
  drops the local player's own copies; ics sends 0). Graph events = scriptlet `0x100001E3` + variable `0x780`
  (table `0x1D0000E2`, a template table of every champion). Missiles are their own objects (`ObjectMissile`). So
  **the same path as the local champion** (C for the messages; P that the remote graph plays them, since it is the
  same object kind with the same tables).
- Do **not** send `0x200F` (crashes, client-skill-instances.md 1), `0x20C9` (only the controlled agent's slot
  copies, targeting indicator), `0x20F8` cooldowns, `0x2077` cast bar, `0x20DC` skill errors to a bot: all are
  controlled-agent HUD messages; ics already guards them with `ent is self.champion` (C).
- `0x20F0` attribute modifiers (slows, buffs) go to any entity with `client_vitals` (`CastWorld.on_modifier`): keep.

---------------------------------------------------------------------------------------------------------------------

## 2. Bot AI in the original data

| Data | What | Use |
|---|---|---|
| Encounter `0x10000B3E` (`0x10000B3D` variants) | bot pool (14 on 5v5, `0x40000BD3` on Crime Alley 1v1) | already used (`lobby.bot_pool`) (C) |
| Encounter `0x10000B41` = **`0x340007E2`** | levelling script: on events `0x1000000C` / `0x10000088` / `0x100001B2` GetLevel -> server-only node `0x10000189` (choose ranks) -> `InitSkill(rank)` slots 1-4; graph 1 while HasFlagAttribute `0x10000A23` (in base) runs server-only node `0x10000186` (shopping) (C decoded, data/script_trees/340007e2.json; node meaning P) | run it on each bot (VM), with `0x10000189` -> loadout `skill_order`, `0x10000186` -> loadout `artifacts` |
| Champion loadout `0x10000CEB` | `skill_order` (`0x1000034B`, 19 points), recommended artifacts in order (`0x10000478`), Stolen Power pair (`0x1000064E`) | `Data.loadout(variant)` (C) |
| Encounter `0x10000CE0` | per team 5 enums `0x10000CDE` (GD: team 1 0xB,7,6,9,0xA; team 2 8,7,6,9,0xA): per-slot role / lane (P), enum names **O** | lane assignment; until decoded, by slot index |
| `0x10000B3F` / `0x10000B40` / `0x10000B3C` | bots on / bots also on the players' team / 10 or 2 (P) | info |
| `0x3A000026` / per-champion 0x3A records | `GetBestPerceivedTargetInterval_Min/_Max` 0.5 / 0.8, `AIActive`, skill cooldown timers | retarget interval (C values) |
| `0x340007D6` + nodes `0x100001B3` / `0x100001B6` | lane statuses SetLane / GetLane (implemented, P) | tag each bot with its lane |
| Script AI template `0x3400053A` (Starro's parasite) | GetBestPerceivedTarget / AIMoveTo / SetAITarget priorities | the brain's target rules (units-and-ai.md 5.3) |
| Kynapse | client links it for path finding / obstruction only; the bots' Kynapse data is the 0x90 navmeshes (`ics.navmesh`) | no AI data (C) |
| Difficulty | none in the data (C); beginner / intermediate are two encounters with the same data | server tunables |

No decision logic (target choice, lane push, retreat, combos) exists in the data or the client (C, units-and-ai.md 5.1):
the brain is server code; the data gives the triggers (levelling, shopping), the choices (loadout) and the intervals.

---------------------------------------------------------------------------------------------------------------------

## 3. Implementation design for `ics`

### 3.1 Creation (session -> match)

1. `ics/lobby.py Slot.as_player()`: add `"player": self.iid` (keep `"iid"`).
2. `ics/session.py` before `start_match`: attach `w.champion` as `"agent"` to the `lobby.me` row; for each bot row,
   `agent = w.create_bot_champion(variant, team, name, player_iid, stolen)` (only when `[ics] bot_champions_in_world`).
3. `World.create_bot_champion(...)` = `create_champion` without `self.champion = ent`: eid `new_id()`, `kind =
   "champion"`, `ent.bot = True`, `ent.player_iid`, stats / resource vital / kit / ranks 0 + `match_start_ranks`,
   `give_stolen_powers`, `world_state` + `scriptlet_keys = None` (champion: unfiltered), `client_vitals = True`,
   `self.add(ent)`, `start_kit(ent)`, `champion_init_event(ent)`, and the 0x340007E2 levelling script started on it.
4. `World.properties(ent)`: new branch `ent.kind == "champion" and ent is not self.champion` -> section 1.2 list
   (`M.champion_properties(..., player=ent.player_iid)` + `0x7D2` + stat f32s + `0x100006FE` + `0x956` + minimap
   `0x100004DA` / `0x2A1` / `0x10000083` + `0x10000AA7` / `0x100001C3` / `0x1000034C` + `PROP_SECONDARY_VITAL`).
5. `Match._players()` already places agents at `maps.spawn_point(team, slot)` and fills the scoreboard (`agent.eid`
   in 0x1000005B rows). After placement: one bundle per bot (`w.update`) once the client is in world (`second_seq`
   1), `w.vitals`, then 0.8 s later the late changes: `0x1000019D` 0 -> 8, `0x10000029` / `0x10000249` = 1, allies'
   `0x10000133` 0 -> 12 (reuse `World._late_flags` / `Units._late_vision`).

### 3.2 World fixes so a second champion behaves like the first (C, each a one-liner today keyed on `self.champion`)

| Where | Today | Change |
|---|---|---|
| `World.damage` death branch | non-local -> `update` + `remove` after `corpse_seconds` | `kind == "champion"`: keep the object, LifeState 2 by 0x6 + death graph event `0x100000AD`, stop it; no local notices |
| `Match._respawn_other` | re-adds a removed entity with a full bundle | teleport (`tele_seq` bump) + LifeState 4 by 0x6 + vitals + state 0xB0 |
| `World.tick` regen | Will / health regen for the local champion only | loop every alive `kind == "champion"`; vitals at most every 0.5 s per bot |
| `World.fog` | hides only `kind == "unit"` enemies | also enemy `kind == "champion"` (0x90F; `Match.visible_to` for stealth) |
| `CastWorld.player()` / GetAgent | always the local champion | the caster when it is a champion agent (bot scripts asking "my agent") (P) |
| `World._unit_ai` | units chase only the local champion | unchanged (match units use `Units.think`, which already takes every `Match.champions()`) |
| `Match.grant` level-up | `champ.level = level` for non-local | `w.bot_level(champ, level)`: `recompute_stats`, 0x6 `0x10000167`, vitals, raise `0x1000000C` on the bot (the levelling script picks ranks) |

### 3.3 `ics/match/bots.py` - BotBrain (one per bot, ticked from `Match.tick` after `units.tick`)

State machine, decisions every `uniform(0.5, 0.8)` s (`0x3A000026` interval, C), movement every tick:

- **lane**: slot -> lane (`0x10000CE0` when decoded; else Crime Alley `mid`, 5v5 `[north, north, mid, south, south]`
  by slot), `SetLane` status for scripts. Route = `maps.lane_path(map, lane, team)`.
- **push**: walk the route behind the most advanced allied minion of the lane (`Units.by_eid`, role minion, same
  lane) at 3 m; with no wave, wait at the first allied turret of the lane.
- **fight**: targets within 9 m (`Units.enemies_near`-like over minions + `Match.champions()` + attackable
  structures): enemy champion if its health share < own or it hit an ally (`Match.aggressors`), else lowest-health
  minion (last hit), else a structure **only when an allied minion is within the structure's range** (tower rule).
  Basic attack = `ent.attack_target = target` (World `_attack_step` already chases and casts slot 0).
- **skills**: per decision, the first of slots 4, 1, 2, 3, 7, 8 that is ranked, off cooldown (`ready_at`), affordable
  (`stat 3` vs Will) and in range (`stat 18`, else 6 m) on a champion target (on minions only slots with stat 22 > 0,
  i.e. area, and Will > 50 %); targeting by `Skill.targeting` (C table, champion_check.py): 9 / 14 -> `cast(ent, s,
  target, None)`, 1 / 10 / 11 / 13 / 16 -> `cast(ent, s, None, target.pos)` (lead by `stat 30` speed when known),
  5 / 7 -> `cast(ent, s, None, None)` when the target is within `stat 22` (or 4 m). Face the target first.
- **retreat**: health < 30 % (`[ics] bot_retreat_health`) or under an enemy turret's aim without minions -> walk the
  route backwards; < 15 % and no enemy within 10 m -> Recall (slot 6 when the kit has it, else walk) to base.
- **base**: at the start point: heal (base aura already in `Match._auras_tick`), shop (`Shop.buy(bot, did)` along
  loadout `artifacts`, as node `0x10000186` would), then back to the lane at 100 %.
- **dead**: nothing (Match respawns it).
- Difficulty knobs `[ics] bot_reaction` (decision interval multiplier), `bot_skill_chance`, `bot_aggression`.

### 3.4 Damage / kills / assists (C: already generic)

`World.damage` emits "hit" / "killed" with the source; `Match._on_hit` records `score.hit` and `aggressors` for any
agent in the scoreboard; `_champion_died` counts kills / deaths / assists with `score.by_agent`, grants bounty + XP
(`Match.grant`), kill feed, voices, and the respawn timer for non-local champions (0x100000BC). Minion / structure
rewards (`_reward`) already loop over every champion near. Missing only: the side finding (the human's row) and
`grant` levelling (3.2).

### 3.5 Messages per tick and bandwidth

Today `Session._tick` sends a **full bundle per changed entity per tick** (30 Hz). A bot bundle with `0x7D2` and
stats is ~0.5 KB (the Stolen Power tables would add KBs): 9 moving bots = ~135 KB/s. Plan:

| Message | When | Size (approx.) |
|---|---|---|
| full bundle 0x4 | creation, respawn fallback, level-up only if 0x6 fails | ~500 B |
| `M.pvp_movement_state` (0x4 with only 0xB0) | a new path segment, a stop (speed 0), heading change > 10 deg, else every 1 s while moving | ~70 B |
| 0x6 set property | level, LifeState, flags, vision | ~25 B |
| 0x42 vitals | on change, at most 4 Hz per bot | ~30 B |
| 0x8D | per cast / scriptlet, as for the local champion | 40-120 B |

9 bots moving: ~3 states/s each = ~2 KB/s + vitals ~1 KB/s + casts. Implement in `Session._tick`: for a
`kind == "champion"` non-local entity (and later for minions) call `w.motion_update(ent)` that compares
`(dest, speed, heading)` with the last state sent and returns the small message or None; `[ics] bot_motion_only`
(default true) / false = full bundles as today. `CastWorld.move` / `stop` call `w.update` for full bundles: route
them through the same helper for bots.

### 3.6 Open checks for the tester's first run (diag)

1. Nameplate with name + level and a red / blue health bar on the bot (O: whether `0x10000064` must name an existing
   player object; switch `[ics] bot_player_objects`).
2. Right click on an enemy bot = attack (diag `--target`: flags 8 cached, tags B / C pass).
3. The bot's run animation while it walks with motion-only states (else `bot_motion_only = false`).
4. A bot's skill 0x8D plays its animation on its model (P).

### 3.7 Exact code changes

1. `ics/lobby.py`: `Slot.as_player()` + `"player": self.iid`.
2. `ics/session.py` (`_start_world` near `start_match`): agents for `lobby.me` (= `w.champion`) and every bot slot
   (`w.create_bot_champion`); after `_link`, `w.update` + vitals + late props for each bot; `_tick`: motion-only path.
3. `ics/world.py`: `create_bot_champion`; `properties()` bot branch; `motion_update()`; `bot_level()`; `damage()`
   champion death without removal; regen loop over champions; `fog()` includes enemy champions; `CastWorld.player()`
   caster-aware; `CastWorld.move/stop` via motion helper for bots.
4. `ics/messages.py`: `champion_properties(..., player_iid=LOCAL_PLAYER_ID, hud=True)` (bot: no HUD-only ids).
5. `ics/match/match.py`: `_players()` accepts `"iid"`; `_respawn_other` without re-creation; `grant()` calls
   `w.bot_level`; `tick()` ticks `self.bots`; start: `self.bots = BotManager(self)`.
6. `ics/match/bots.py` (new): `BotManager`, `BotBrain` (3.3), lane table, skill picker by `Skill.targeting`.
7. `ics/script_nodes.py`: `0x10000189` -> `world.bot_choose_ranks(owner)` (loadout `skill_order`), `0x10000186` ->
   `world.bot_shop(owner)`; no-ops for non-bots.
8. `ics/config.py` `[ics]`: `bot_champions_in_world` (true), `bot_motion_only` (true), `bot_player_objects` (false),
   `bot_retreat_health` 0.3, `bot_recall_health` 0.15, `bot_decision_interval` [0.5, 0.8], `bot_skill_chance` 1.0,
   `bot_lanes` {map: [lane per slot]}, `bot_vitals_hz` 4, each with a dated comment.
9. Tests: `tests/test_match.py` (bot agents exist, bundles carry 0x10000064 / 0x7D2, a bot kill counts for the bot,
   the bot respawns without 0x3), `tests/test_session_flow.py` (bundle per bot after the link), a `tools/bot_sim.py`
   headless 1v1 Crime Alley run (bot pushes, last-hits, casts, dies, respawns, levels, buys).
10. Catalog / docs per CLAUDE.md rule 3 when built (`world_objects.tsv` bot rows, `properties.tsv` statuses,
    reverse-engineering.md, CHANGELOG `fase3-hs`).
