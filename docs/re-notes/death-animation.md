# Champion death animation: why the fall does not play, what the client needs (2026-10-28)

Trigger: tester report 2026-10-28 15:00 (run 14:39-15:00, Crime Alley v AI, Atomic Green Lantern `0x4000080C` vs bot
AI: Atomic Wonder Woman `0x400003EC`, build fase3-ie): "the animation when I kill an enemy or I am killed and the
champion goes down to the floor does not play".

Second pass (same day, 18:55; the first pass's text is kept where it was re-checked). New in this pass: the death
screen is the server's `_CDefeatSystem_DeathOverlay` (section 3), event `0x11F` is the real "stop a scriptlet run"
(section 4), and two first-pass statements are corrected (full bundles while dead do not re-fire the LifeState
listeners; the grey screen did not "come with the bundle form").

2026-10-29: skeptic review (section 10) and implementation (section 11). Section 10.2 withdraws this note's "the grey
on our builds is P the fog of war" (sections 0.5, 1.3, 3): our client runs the DeathOverlay itself; the server's copy
is opt-in.

Sources: the full decompilation (`re-work/decomp/c/*.c`, `functions.tsv`; VA, image base 0x400000), capstone on
`InfiniteCrisis.exe` (bytes identical in `InfiniteCrisis_patched.exe` at every address used), the champion behaviour
graphs and their Havok Script Lua (packs `0xA0000124` Atomic Wonder Woman, `0xA0000150` Atomic Green Lantern, via the
`tools/skill_graphs.py` readers) and `data/skill_graphs.json` (all 56 champion graphs), the scriptlet tables
(`ics.gamedata.Data`, packs `0xA00000DF` / `0xA00000B3`), the server scripts (`ics.script_model`), the Flash sources
(`re-work/ui-as2`, `gameplay/defeat/DefeatManager.as`, `emp_gen/LifeStateList.as`), and the run's
`logs/traffic.log` / `logs/server.log`. **The logs were decoded in the first pass (15:28); `logs/` was emptied at
18:49, before this pass**, so the byte excerpts of section 1 are quoted from that decode (C at the time; not re-read).
Scratch scripts (scratchpad, not in the repo): `death/` (`tabs.py`, `which.py`, `lua.py`, `luaslots.py`, `vars.py`,
`ragdoll.py`, `entries.py`, `entry2.py`, `traffic.py`) and `death2/` (`fn.py` decompilation extractor, `pe.py`
PE / capstone helper, `which2.py`, `entry3.py`, `entry4.py` table-entry dumper, `scanword.py` pack scanner). No game
text is copied (Lua logic is paraphrased: only function / variable / state names and numbers).

Tags: **C** = confirmed (code, data or log bytes read), **P** = probable (strong inference), **O** = open.

Builds on: deep-scan-animations.md 1-2 (event path, defeat scriptlets, respawn fix), object-update-bundles.md 0-3
(what a 0x4 does to a live object; corrects this note's first pass), client-scriptlets-graphs.md 1.2-1.5 / 3,
sweep-scriptlets-nodes.md A (action registry; two meanings corrected in 3.3), full-combat-skills.md S3.4 and
StopScriptlet / StopScriptletKey, bot-champions.md 3.2, test-2026-10-25-2207.md (BOT-1, AGL-3),
cinematics-vfx-audio.md 2.3 / 3, hud-shop-timeline-kills.md 5, movement-collision-fog-map.md 2,
fog-vision-runtime.md 3, sweep-property-listeners.md, champion-animation-matrix.md 1, test-2026-10-28-1439-sweep.md 6.

---------------------------------------------------------------------------------------------------------------------

## 0. Summary

1. **The local champion never gets a fall (C, code + traffic).** `World.damage` (`ics/world.py:1558`) raises the
   death graph event for the local champion only inside the `death_as_property` branch (lines 1637-1646).
   `[ics] death_as_property` is `False` since fase3-gv (`ics/config.py:819`), so a local death sends only the full
   bundle with LifeState 2 (line 1648). In the run: AGL deaths at 14:45:56.404 and 14:53:25.927, each a 1533-byte 0x4
   bundle with `0x100000FA = 2` and speed 0; nothing reaches AGL's graph until `_Defeat_OnRespawn` 10 s / 20 s later
   (section 1). The 2026-10-25 22:07 video (fase3-hx, test-2026-10-25-2207.md AGL-3) shows the same: the dead AGL never
   lies down, while the bot falls flat on the server's bot path.
2. **The client never starts the fall by itself (C).** The fall is the behaviour graph's `Death` state, entered only on
   the graph event `CbtState_Death_Induce 0x100000AD` (a main-machine wildcard, flags 0xC00, in all 56 champion
   graphs). No client code raises it, no client code names a `_Defeat_*` key, no graph variable is bound to LifeState,
   and every LifeState listener is UI / camera / fog / order gating (section 2.3). The server must send it.
3. **The data's death message is `_Defeat_OnDead 0x100001FA` (C data; P that the original sent it).** Table
   `0x1D0000E8`: one type 0x14 action raising `0x100000AD`; audio table `0x1D0001F6`: one type 9 action (P: the death
   voice cue). All 156 champion variants hold `0x100001FA`, `0x100001FC` and `0x100001E3`. The game's own content uses
   it for deaths (cinematic actors; status `0x340000EE` re-runs it at its exit when SELF is dead, C).
4. **Bots: the sequence is right (C traffic) and is the one seen falling (C, 2026-10-25 video, 2026-10-26 report).**
   Each of the 4 bot deaths sent: stop bundle (LifeState 2 inside, speed 0) -> 0x6 LifeState 2 -> 0x8D `0x100001E3` +
   `0x780 = 0x100000AD`, and nothing that could stand the bot up before its respawn. All 4 were turret kills while the
   bot retreated under GL's tower (test-2026-10-28-1439-sweep.md 6); no screenshot shows one, so whether the tester's
   sentence includes this run's bot is **O**. The plan sends `_Defeat_OnDead` to bots too (same graph event plus the cue).
5. **New: the original's death screen is `_CDefeatSystem_DeathOverlay 0x10000843` (C data and code, P look).** It sits
   in the shared champion table `0x1D0000EF` (with `_Advancement_LevelUp`, `_Team_SetTeamIndicator`,
   `_Player_OnAgentControlledByPlayer`: server-system scriptlets), no client code names it, and its one action is a
   timeline container holding two screen AfterEffects: a type 0x10 full-screen texture `0x13001485` and a type 0x2D
   **Colorize with saturation -100** (fade-in 0.75 s, held until the run stops, fade-out 0.25 s, no local-player
   filter). ics never sent it. The "grey screen" the tester saw on our builds is therefore not this effect: P it is the
   fog of war (the dead champion stops being a vision source), which also explains fase3-gt (grey) vs fase3-gu (no grey,
   allied minions had just become vision sources). The bundle and the 0x6 forms notify LifeState identically (C,
   object-update-bundles.md 3), so "the grey screen came with the bundle form" (CHANGELOG fase3-gv) is not a mechanism.
6. **New: event `0x11F` stops a scriptlet run (C path).** `u8 0 | u32 key | u32 instance (0xFFFFFFFF = every run of
   the key) | u8 flag` -> `0x675280` -> `0x57C4B0` -> `0x529EF0` (end list, state 5, attachments released). A 0x8D
   with the run's instance and a signal bit (`World.signal_scriptlet`) only runs the definition's signal handlers
   (`0x534290`) and stops nothing by itself (C). The overlay must be stopped with 0x11F at the respawn.
7. Side findings: the bot's respawn sends `_Defeat_OnRespawn` 4 times (C); the local death bundle is held while a carry
   holds bundles (C code); hits land on a dead champion (C); the client's "`_Defeat_OnRespawn` hooks"
   (cinematics-vfx-audio.md 2.3) are property `0x100001FC` reads (C); the sweep's meanings of action types 0x10 / 0x2D
   ("sound") are wrong: both are screen AfterEffects (C, 3.3). Corrected from the first pass: a full bundle of a dead
   champion with the same LifeState fires no LifeState notification (C, `0x62AFD0` is a diff).

Fix (section 9): right after the message that carries LifeState 2, send 0x8D `_Defeat_OnDead` (fallback: the bare graph
event) to the local champion and to bots; for the local champion also `_CDefeatSystem_DeathOverlay`, stopped by 0x11F
at the respawn; keep the death bundle (it carries the stop) and send it past a carry's hold; one get-up per delay for
bots.

---------------------------------------------------------------------------------------------------------------------

## 1. Evidence from the run 2026-10-28 14:39-15:00 (C, first-pass decode of `logs/traffic.log`)

Decoded with scratch `death/traffic.py` (0x8D first DID, `0x780` enum of a `0x100001E3` run, `0x100000FA` value of 0x4 /
0x6 bodies). AGL = `0x0200000000000002`, the bot = `0x0200000000000100`.

### 1.1 Local champion (2 deaths)

| t | traffic line | message |
|---|---|---|
| 14:45:56.398 / .400 | 70819 / 70823 | 0x42 vitals 0/824 (x2) |
| 14:45:56.401 | | 0x20E9 status icon removed (death events) |
| 14:45:56.402 | 70831 | 0x217A kill feed "AGL by turret mid t2"; notice 0x1000021C kill card |
| **14:45:56.404** | 70865 | **0x4 bundle "dead (LifeState 2)" 1533 B**: `fa 00 00 10 40 fa 00 02` (0x100000FA = 2), motion `ac 18 8a 20 36 40 00 00 00 00` (heading 2.85, speed 0.0) |
| 14:45:56.405 | | notices 0x10000090 (2, t + 10) + 0x100000BC; 0x2039 announcer event 18 |
| 14:45:56.537 | | 0x8D `Vfx_Atm_Glt_Shards_Stop 0x1000088B` (the passive's own end) |
| 14:45:58.651, 14:46:03.651 | | 0x4 bundles "credits 930 / 940" (LifeState 2 inside, same value) |
| 14:46:06.419 | 74522 | 0x4 respawn bundle (teleport 3, 1720 B, LifeState 4) |
| 14:46:06.422 | 74646 | 0x8D `_Defeat_OnRespawn 0x100001FC` |
| **14:53:25.927** | 177126 | **0x4 bundle "dead (LifeState 2)" 1533 B** (killed by the bot) |
| 14:53:25.990 / 26.074 | | 0x8D `VFX_CBT_Hit_Shared 0x10000223` on the dead AGL (hits landing after death) |
| 14:53:28.6 - 43.6 | | 0x4 bundles "credits 2320 ... 2350", "ranks slot 1" (30.834), "ranks slot 5" (32.892), all LifeState 2 |
| 14:53:45.945 / .949 | 182137 / 182261 | respawn bundle (teleport 4) / `_Defeat_OnRespawn` |

Between each death bundle and its respawn there is **no** 0x8D to AGL except the passive's VFX stop and hit effects;
none of the 36 `0x100001E3` runs on AGL in the whole log carries `0x100000AD` (their `0x780`: `skill_to_locomotion` x8,
AGL skill events `0x1000032C`-`0x10000331` x17, `CbtState_DisableHit` / `EnableHit` x6, `CarPickup` x2, `Recall_Start` /
`_End`, `0x100001F2`). `grep _Defeat_OnDead logs/traffic.log` = 0 (first pass); `_CDefeatSystem_DeathOverlay` has no
sender anywhere in `ics/` or `icserver/` (code grep, this pass).

The credits / ranks bundles sent while AGL is dead carry the same LifeState 2: the 0xBC is a diff (`0x62AFD0` ->
`0x578DE0`: an equal value fires nothing, object-update-bundles.md 3), so they re-fire no LifeState listener and do
not touch the graph (C; the first pass said "re-fire", wrong).

### 1.2 Bot (4 deaths: 14:49:39.5, 14:50:39.5, 14:51:29.6, 14:52:16.5; all "by turret mid t1")

```
14:49:39.546  0x42 vitals 0/1030
14:49:39.555  0x217A kill feed; notice 0x100000BC "dead for 18 s"           (Match._champion_died)
14:49:39.556  0x4 "stops where it falls" 516 B: ... 9c 00 00 10 40 9c 02 fa 00 00 10 40 fa 00 02 ...
              motion ac 18 64 59 72 bc 00 00 00 00 (speed 0)               (LifeState 2 already inside: the change)
14:49:39.557  0x6 "dead: LifeState 2": 14 00 00 00 02 | 00 01 00 00 00 00 00 02 | 02 | 06 | 00 | fa 00 00 10 40 fa 00 02
                                                                           (same value: no notification)
14:49:39.557  0x8D "falls (graph event 0x100000ad)", 48 B:
              2c 00 00 00 02 00 01 00 00 00 00 00 02 02 80 8d | 00 01 | 10 81 e3 (DID 0x100001E3) | 92 5e (run)
              | 00 00 00 00 | 02 (variables) | 00 01 80 07 00 00 07 80 10 80 ad (0x780 = enum 0x100000AD) | f64 0 | 00
14:49:39.639  0x20E2 inventory (the dead bot shops); nothing else to the bot until
14:49:57.562  0x6 LifeState 4; notice 0x100000BC alive; 0x4 respawn bundle 526 B; 0x42
14:49:57.564 / .565 / 58.187 / 58.188   0x8D _Defeat_OnRespawn x4
```

The other three deaths are byte-for-byte the same pattern. No graph event, `_Combat_GoToLocomotion`, bundle or skill
key reached the bot between its fall and its respawn. The bot brain stops at death (`bots.py:143`, C).

### 1.3 Earlier runs (C, the tester's words and videos; reading of the grey screen revised)

| Build | Local death message | Tester |
|---|---|---|
| fase3-gs (10-23 09:43) | full bundle | "the game froze, then the champion was at the base" |
| fase3-gt (10-23 10:10) | 0x6 LifeState 2 only (`death_as_property` true) | "no fall, a grey screen with the timer"; also "minions have no vision" |
| fase3-gu (10-23 11:25) | 0x6 + 0x100001E3/`0x100000AD` | "no grey screen; **the champion slid while falling**; after the respawn he stayed lying" (the get-up was `0x10000034`, dropped). Same build added allied minions as fog vision sources (`match_unit_vision`) |
| fase3-gv .. ie | full bundle, **no fall event** (`death_as_property` false) | 10-25 22:07 video: grey screen + "Respawn 0:08", AGL never lies down (AGL-3); 10-28: "no death animation" |

Bots since fase3-hu: stop + 0x6 + `0x100000AD` -> the 10-25 22:07 video shows Katana lying on her back (BOT-1, frames
2:38 / 9:06.4, after her respawns: the `Death` pose held through the respawn bundle); the 10-26 Zod report "a
respawned bot walks back lying down" (the fall had played; the get-up `0x10000034` was then fixed to
`_Defeat_OnRespawn`, fase3-ia). So the graph event works on the local champion (fase3-gu) and on remote champions
(C by observation).

**The grey screen (revised, P).** ics has never sent the original's greyscale (section 3). What the tester called a
grey screen is P the fog of war: a champion is a vision source only while alive (`0xAB12C0` needs `0x9CFAF0` =
LifeState 4, `0xAADF70` drops the dead; fog-vision-runtime.md 3), so the dead local champion's surroundings fog over
unless an ally sees them. fase3-gt (no minion vision): grey; fase3-gu (allied minions became vision sources in that
very build): not grey; later deaths away from allied minions (AGL-3 under the enemy turret): grey. The death message's
form is not the cause: a bundle that changes LifeState and a 0x6 both reach the same setter `0x578DE0` and notify the
same listeners (object-update-bundles.md 3, C).

### 1.4 Screenshots of this run

42-47 show the store page, the stealth fields, the drones and the SUV; none shows a death (C). Nothing on screen to
compare for the fall.

---------------------------------------------------------------------------------------------------------------------

## 2. Client: what makes a champion fall (C unless marked)

### 2.1 The behaviour graph

* `data/skill_graphs.json`, all 56 champion graphs: the main machine (`SM_Main_Machine`, or `Logic_Behavior`) has the
  wildcard **`CbtState_Death_Induce 0x100000AD` (flags 0xC00, no condition) -> state `Death`**, whose body is the
  sub-machine `SM_Death` with `startStateId <- Death_Selection` (graph variable **4** in AGL and AWW): 42 graphs
  `0 Death_FaceUp / 1 Death_FaceDown / 3 Ragdoll_Death`, 5 `Death_A / Death_B / Ragdoll_Death`, 4
  `Non_Ragdoll_Death / Ragdoll_Death`, 5 small variants. `Death` (state 15 in AGL / AWW) has no outgoing transition.
* AGL / AWW main-machine wildcards (23 each, re-read this pass): `Global_Locomotion 0x100000AA` and `Combat_Locomotion
  0x1000024D` -> `Locomotion`; `CbtState_Death_Induce 0x100000AD` -> `Death`; `CbtState_Dead 0x1000010B` (0xE00) ->
  `Dead` (clip `attk_recover_fdown_a` at speed 0 = held prone pose); `CbtState_GetUp 0x1000009D` -> `Get_Up`
  (`state_to_locomotion` out); `CbtState_Cower 0x10000179` / `_Cower_Instant 0x100002BA`, `CbtState_Laugh`,
  `InductionUsage_Start`, `SuperStrength_InitCarPickup` / `_Rubble_Pickup`, `Basic_Attack 0x1000006E`,
  `Basic_Attack_Critical`, the four skill starts, `CbtState_KnockDown`, `CbtState_Stasis 0x1000046C`,
  `CbtState_KnockBack 0x1000005E`, `CbtState_KnockUp 0x10000020`, `SpawnIdle`. **No `CbtState_GetHit` wildcard**.
  Any of the others arriving after the fall stands the body up (graph semantics, C).
* Clips (AWW `chr_atomic_wonder_woman_behavior.hkb`, AGL `..._green_lantern_...`): `Death_FaceUp` =
  `..._attk_death_fup_a` (no loop, trigger `RunScript_Vfx_Death_A` at 0.0, exit `StopScript_Vfx_Death_A`),
  `Death_FaceDown` = `..._attk_death_fdown_a` (`..._B`), `Ragdoll_Death` = `..._idle_combat_a` with powered-ragdoll
  modifiers (AGL's graph has `DisableRagdolls` var 18 = 1 by default). The clips end in the lying pose and hold it.
* `Death_Selection` is written only by the graph's Lua (scratch `luaslots.py`): `Script_Locomotion.onActivate =
  onStandardDeath()` -> random 0 or 1 at every entry to Locomotion; `KnockDown Script` / `Script_KnockUp .onActivate =
  onRagdollDeath()` -> 3 (a death inside a knock is a ragdoll).
* Graph variables (AWW 18, AGL 21, `death/vars.py`): none is bound to LifeState `0x100000FA`.

### 2.2 How the event reaches the graph (deep-scan-animations.md 1, re-checked)

0x8D (handler rva 0x234F20 -> script component) -> `0x6279D0`: originator test, table test `0x5235C0` (key in the
object's tables and the entry's property `0x211 & 3`), instance test, context, start -> scriptlet entry -> action
**type 0x14** executor **`0x672930`**: event = the literal, or script variable `0x780` when its kind is 8 / 10;
`(entity+4)->vt+0x58` = **`0x55BD30`** (dropped only if `[ent+0x118] & 0x40` without `& 8`, never for a server champion;
queued while the graph is inactive) -> **`0x55AF70`** global -> local index (-1 = not in this graph, dropped) -> the
Havok machine. No step reads LifeState. `_Defeat_OnDead` and `0x100001E3` + `0x780` both end in this path.

### 2.3 What does NOT start the fall

* **No client code raises it** (byte scan of the PE, this pass): `0x100000AD` has 3 `.text` immediates: `0x97C461`
  (`mov eax, 0x100000AD; ret`, a type-id getter stub), `0x9B5E56` in `0x9B5E00` (picks `0x1000009C` / `0x100000AD` for
  the type registry lookup `0x456260(id, 0xF)`), `0x13C3B7D` (a static registration); plus the input switch
  `0xAC3CC0` (`case 0x100000ad: return`). `_Defeat_OnIncapacitated` / `_OnRevive` / `_OnFade` (`0x100001FB` /
  `FD` / `FE`) occur nowhere in the PE; `0x100001F9` / `0x100001FA` only in `.data` sorted id lists (property-id
  tables). `0x100001FC` has 6 `.text` immediates (`0x9CE559`, `0x9CE6DD`, `0xA4A1B2`, `0xA5D4C4`, `0xAB3080`,
  `0xAB33C6`), all **property** reads (`0x556470(entity, 0x100001FC, &out)` / `0x4A9B60`), e.g. in the status-icon
  handlers `0xAB2D30` / `0xAB3250`: not hooks of the scriptlet (corrects cinematics-vfx-audio.md 2.3).
* **LifeState listeners are UI / camera / fog / orders.** `0x968F30` (target-frame watcher: 2 -> dead list `0xA3FE60`,
  and for the local agent `0xA30E70` -> `0x8870F0`, which builds client message **0x2139** (camera temp-lock,
  constructor `0x8795F0`), gated by `0xA2CC40` (a time budget kept in property `0x10000B08`, constants 4.0, P a rate
  limit); 4 -> `0xA336B0`), `0xA80CD0` (HUD / minimap, 2 -> `0xA0A600`),
  `0xAB00A0` / `0xAB01D0` (HUD can-act), `0xABF320`, `0x96C780` (shop), `0x85EC10`, `0x979A60` (unit component cache
  read by the order gate `0x9CFAF0`), the fog component `0xAB12C0` (vision sources), `0x13C5280` (static registration,
  P the script node). None in the entity / graph / scriptlet code (`0x54xxxx`-`0x67xxxx`).
* **A full bundle does not reset the graph** (object-update-bundles.md 1-3, C): `0x64D8A0` compares only the
  descriptor's world-state override with `entity+0x110` (both 0); 0xBC is a diff; 0xB0 is one more movement state.
  Observed: the bot held its `Death` pose through its respawn bundle (BOT-1, 10-25; Zod 10-26).
* **Flash** (`DefeatManager.as`): `RecvNotice_DefeatStatusUpdated` (notice `0x10000090`) only attaches `DeadTimer` to
  the character panel (state 2) or the `Incapacitated2` panel (3); no screen filter (C). LifeState enum
  (`LifeStateList.as`): 1 DeadAndFaded, 2 Dead, 3 Incapacitated, 4 Alive, 5 Respawning.

### 2.4 The defeat scriptlets (pack `0xA00000DF` table `0x1D0000E8`, base `0x1D0004F4`; audio table `0x1D0001F6` of pack `0xA00000B3`) (C, raw words, `death/entries.py`, `death2/entry4.py`)

| Key | Name | Entry words (after `key 0`) | Meaning |
|---|---|---|---|
| `0x100001FA` | `_Defeat_OnDead` | `0 1 \| 14 0 0 0 1 3f800000 0 3f800000 ffffffff 100000ad` | no props; 1 action: type 0x14 raise **`0x100000AD`**. In `0x1D0001F6` (@`0x450F8`): `0 1 \| 9 10000004 0 0 0 4 \| 100006f0 500006f0 \| 100003b6 100003b6 2 \| 100006ef 100006ef 3 \| 100003b9 100003b9 4a ...`: one type 9 action with four fields, `0x100006EF` = 3 and `0x100003B9` = 0x4A (P the death voice cue) |
| `0x100001FB` | `_Defeat_OnIncapacitated` | `0 2 \| 14 .. 100000ad \| 17 1 0 10000130 ..` | raise `0x100000AD` + type 0x17 `Vfx_Stop 0x10000130` |
| `0x100001FC` | `_Defeat_OnRespawn` | `0 1 \| 14 .. 100000aa` | raise **`Global_Locomotion 0x100000AA`**; `0x1D0001F6`: the same type 9 with `0x100006EF` = 4, `0x100003B9` = 0x4F (P the respawn cue) |
| `0x100001FD` | `_Defeat_OnRevive` | `0 2 \| 14 .. 1000009d \| 14 .. 100000aa` | GetUp then Locomotion |
| `0x100001F9` | `_Defeat_StartupIncapacitated` | `1 7e6 7e6 1 \| 14 .. 1000010b` | props {0x7E6}; raise `CbtState_Dead` (starts lying) |
| `0x100001FE` | `_Defeat_OnFade` | `0 3 \| 23 ..` x3 | three type 0x23 timeline containers (P the body fade-out, LifeState 1) |
| `0x100002FD` | `_Combat_GoToLocomotion` | `1 479 479 2 \| 22 .. 100000fa 0 3 5 1 100000fa 4 .. \| 22 .. 10000b2d .. \| 14 .. 100000aa` | property containers on LifeState 4 / `0x10000B2D` around a raise of `0x100000AA` (P: a no-op on a dead champion) |

Every champion variant (156) reaches `0x100001FA`, `0x100001FC` and `0x100001E3` through `0x1D0000E8` / `0x1D0001F6` /
`0x1D0000E2` (`death/tabs.py`, roster scan); AGL `0x4000080C`, AGL base `0x4000047D` and AWW `0x400003EC` re-checked
this pass (`death2/which2.py`). `Data.scriptlet_key("_Defeat_OnDead") = 0x100001FA`. The server's graph copy maps it:
`data/skill_graphs.json` `shared_scriptlets["0x100001FA"] = [0x100000AD]`, `["0x100001FC"] = [0x100000AA]`.

### 2.5 The game's own content uses these keys for deaths (C data)

* Cinematic scenes raise `_Defeat_OnDead` on actors when they die (cinematics-vfx-audio.md 2: Thug_01 frame 236,
  Melee01 955, Melee02 895).
* Status script `0x340000EE` (a disguise: node `0x1000010D` to world state `0x2E0004E6`, restored by `0x1000010E`): its
  exit runs `RunScriptlet(SELF)[0x100001FA]` when `!IsAlive(SELF) || HasFlagAttribute(SELF)[0x10000B2D]` (re-read this
  pass with `ics.script_model`): after restoring a dead entity's model it puts it back into the fallen pose.
* Nightmare Superman's passive `0x3400041C` fakes a death with `SetDefeatType [1 0]` (`0x10000162`) and
  `RaiseGraphEvent(SELF)[0x100000AD]` + TreatAsDead `0x10000B2D` (kit-audit-3.md).
* Only two scripts raise `Global_Locomotion` directly: `0x34000130` (Stun status, SELF, at its end) and `0x340000E0`
  (Doomsday Charge, on the carried target). ics ends statuses in the death events before the fall goes, and status
  application skips dead targets (`script_nodes.py:848` `world.alive(target)`), so neither can stand a dead champion up
  today (P; a Charge ending on a dead victim is the edge case).

---------------------------------------------------------------------------------------------------------------------

## 3. The death screen: `_CDefeatSystem_DeathOverlay 0x10000843` (new)

### 3.1 Where it is (C)

Table `0x1D0000EF` (pack `0xA00000DF`, 28 keys, no base) is in the 0x7D2 chain of every champion (AGL, AGL base, AWW
re-checked). Its keys are system scriptlets named after server classes: `_Team_SetTeamIndicator 0x100001FF`,
`_Player_OnAgentControlledByPlayer 0x100001E8`, `_Encounter_OnAgentControlledByPlayer 0x10000200`,
`_Advancement_LevelUp 0x10000201` (ics already sends it on level-up, `[ics] level_up_scriptlet`),
`_Advancement_UltimateUnlocked 0x1000065D`, `_gmSUsageComponent_Proximity_*`, `_Entity_OnSwap 0x10000809`,
**`_CDefeatSystem_DeathOverlay 0x10000843`**, plus Super Strength / channeling keys. The PE has no string
`DeathOverlay` / `DefeatSystem` and no usable immediate `0x10000843`: its two `.text` byte hits are `0x41B2E8` (inside
`test dword ptr [ebx+8], 0x1000`) and `0xA8EEBB` (property `0x10000843` of the shop's filter list in `0xA8EBB0`).
So it is sent by the server (C absence; P "CDefeatSystem" = the original server's defeat system).

### 3.2 The entry (C words, `death2/entry4.py`, pack `0xA00000DF` @`0x1485DF8`)

```
10000843 0 | 2 | 737 40000737 | 211 211 1 | 1 |
23 0 0 1 1 3f800000 3f800000 0 0 0 0 1 3f800000 0 3f800000            type 0x23 container (same header as _Defeat_OnFade's)
  2b | 1 6 3f000000 6 2 |
  10 | 1 3f400000 3f800000 3e800000 1 0 5 13001485 0 1 1 3f800000 ffffffff 3 1 0 1 0 1 3f800000 1 3f800000 | 0 0 0 0 1 3f800000 0 3f800000
  35 0 0 |
  2d | 1 3f400000 3f800000 3e800000 1 0 5 | 1 c2c80000 | 1 0 | 1 0 | 1 0 | 0 0 0 1 3f800000 0 3f800000
  3f 0 0 0                                                           (next entry: 0x100007A2)
```

* Props: `0x737` in the flagged form (the bool the definition builder `0x525690` -> `0x51F140` stores at def+8 when
  a signal list exists), `0x211` = 1 (network start allowed: `1 & 3 != 0` in `0x5235C0`).
* One action, type **0x23** (factory vtable `0x15CF4F8` -> create `0x6633D0` -> definition `0x52B290`, vtable
  `0x15B13B8`: +0x24 `0x126AE20` = `mov eax, 0x23`, +0x28 execute `0x52F760`, +0x0C fields `0x52B4D0`: 0x677, 0x4CD,
  0x41C, 0x5C6, 0x100, 0x7DE, 0x786 and the children `0x52A0B0`). Its instance (vtable `0x15B0D08`, `0x533A30` /
  `0x533AB0`) replays the children on a period with a repeat count (P: a timeline container). The words `2b`, `35`,
  `3f` before each child are child headers (P: start positions; `_Defeat_OnFade` has `5f`, `69`, `73`, `82`).
* Child **type 0x10** (execute `0x657F60`): persistent 1, fade-in 0.75 s, hold 1.0, fade-out 0.25 s, +0x44 = 1, local
  player only (+0x45) = 0, +0x48 = 5, texture **`0x13001485`** (asset type 0x13 = image / texture).
* Child **type 0x2D** (execute `0x659460`): the same timing and flags, then four one-key curves: **-100.0**, 0, 0, 0.

### 3.3 Types 0x10 and 0x2D are screen AfterEffects (C; corrects sweep-scriptlets-nodes.md A.2 "sound")

* 0x2D: factory vtable `0x15CF688` -> create `0x6648A0` -> definition `0x653C60` (vtable `0x15CE5D0`, defaults
  0.25 / 1.0 / 0.25, +0x44 / +0x45 = 1 / 1, +0x48 = 5). Field order (`0x67A380`): `0x613` +0x34 byte (persistent),
  `0x1B6` / `0x5C3` / `0x31C` +0x38 / +0x3C / +0x40 f32 (fade-in, hold, fade-out), `0x419` +0x44, `0x5C2` +0x45
  (local player only), `0x9B` +0x48 int, curves `0x8D5` +0x4C, `0x8D4` +0x5C, `0x8D3` +0x7C, `0x8D2` +0x6C. The data
  words follow that order (byte, three floats, two bytes, int match the types and differ from the defaults).
* Execute `0x659460`: skip unless the run's entity passes the flag test `0x588240` (bit 1 of `[[ent]+0x64]`, P an
  "in the scene" flag); if +0x45, only on the local player's object (`0x635200`: IID at +0x100 == `[0x1B6A710]`);
  then `0x776060` builds a 0x98-byte effect `0x76ED70` (vtable `0x15DAB80`) and hands it to the AfterEffect manager
  `0x774930`; persistent (+0x34) -> an instance `0x6537A0` stays attached to the scriptlet run.
* Effect `0x76ED70` (disassembly of `0x659460` -> `0x776060` -> `0x76ED70`, argument order checked): curves at
  +0x58 / +0x68 / +0x78 / +0x88 <- definition +0x4C / +0x5C / +0x6C / +0x7C; +0x48 <- +0x44, +0x4C <- +0x48;
  timing `0x7AA620(held = +0x34 != 0, fade-in, hold, fade-out)` (state 1 = fading in while fade-in > 0.0002).
* Effect update `0x765980`: writes the global VideoPost object `[0x1B72160]`: +0x1DC = curve +0x58, +0x1E0 = +0x68,
  +0x1E4 = +0x88, +0x1E8 = +0x78, **+0x1DA = 1**; its destructor `0x767930` writes +0x1DA = 0. The VideoPost
  registration `0x76D640` names those fields `VideoPost.UseColorize` (+0x1DA), `Colorize.Saturation` (+0x1DC),
  `Colorize.Hue` (+0x1E0), `Colorize.Contrast` (+0x1E4), `Colorize.Brightness` (+0x1E8). No other code writes +0x1DA
  (decompilation grep). So the DeathOverlay's first curve, **-100, is the Colorize saturation** (C chain, P that the
  binary curve order equals the serializer's): the whole 3D view turns grey, as in the tester's reference of the
  original (hud-shop-timeline-kills.md 5).
* 0x10 (execute `0x657F60`, same gates) -> `0x775E20` -> `0x76EAA0` (0xF8 bytes, vtable `0x15DAB70`; loads the texture
  DID with `0x5DFBA0(did, 9)`; its error path names `.../render/scene/manager/effects/AfterEffect.cpp`): a full-screen
  texture AfterEffect (P: the death vignette / overlay image). `0x7AA620`'s other callers (`0x775F30` = type 0x07's
  target, `0x76E9F0`, `0x6E3760`, `0x623C70`, `0x74A930`) are P the other AfterEffect kinds.

### 3.4 Lifetime and audience (C code, P data alignment)

* Persistent children keep the run alive (a run without a live child is removed, client-scriptlets-graphs.md 1.4), so
  the grey stays until the run is stopped (section 4) or the object is destroyed; the fade-out (0.25 s) plays on
  release (P).
* +0x45 = 0 in both children: no local-player filter. Whatever entity the 0x8D names, the receiving client's screen
  goes grey. The server must send it **only to the dead player's own client, on his champion**; in ics only for the
  session's champion, **never for a bot** (a bot's overlay would grey the human's screen).

---------------------------------------------------------------------------------------------------------------------

## 4. Stopping a scriptlet run: event 0x11F (new, C)

* Serializer `0x6751A0`: base byte (`0xB0D380`, u8) | u32 -> +0x20 | u32 -> +0x24 | u8 -> +0x28 (0 or 1 only).
* Exec `0x675280` (disassembly): entity by the frame's IID (`0x445070`), script component `[[ent+4]+0x10]`, then
  `0x57C4B0(&r, key = +0x20, flag = +0x28, instance = +0x24, 0)`.
* `0x57C4B0`: instance == `[0x185F2B0]` (0xFFFFFFFF in `.data`, never written) -> every run of that key (hash by key),
  else the run with that instance (hash by instance); each -> `0x57B920` -> `0x52D790` -> **`0x529EF0`** (state 4,
  end list `0x529E40`, state 5) -> unlinked from both lists (`0x57B400`, `0x57AB30`), leftovers stopped `0x516F80`,
  released. This is the client's own StopScriptletKey path too (full-combat-skills.md: `0x588A80` -> `0x57C4B0`).
* Wire: `build_message(entity, 0x11F, b"\x00" + struct.pack("<IIB", key, instance, 0))`. The object manager dispatches
  any non-create event for a live IID to its exec (object-update-bundles.md 1).
* By contrast a 0x8D entry whose instance is alive (`0x6279D0` step 4) goes `0x534BF0` -> `0x534290`, which only runs
  the definition's signal list (def+0x1C, count +0x24) for the set bits; with no signal handler nothing stops (C).
  `World.signal_scriptlet` (0x8D + signal bit 1, `[ics] stop_scriptlet_signal`) is used by the script nodes'
  StopScriptlet / StopScriptletKey (`ics/world.py:2440`), the stealth shimmer (`world.py:1751`, `match.py:773`) and
  the camp phase (`match.py:1514`): those stops work only for keys that author a signal handler (P per key; other
  areas, see open questions).

---------------------------------------------------------------------------------------------------------------------

## 5. What the original server sent on a champion death (C kinds from the handlers and data; P order)

No capture of the original exists.

1. Stop: a movement state with speed 0 where the champion fell (the client dead-reckons otherwise; fase3-gu slid).
2. LifeState `0x100000FA` = 2 (0x6, or as a change inside the object state): order gate, HUD, nameplate, dead list,
   camera lock, fog vision. (3 Incapacitated has its own Flash panel; P: not used in PvP.)
3. **0x8D `_Defeat_OnDead`** on the victim: the fall (`Death`, face up / down by `Death_Selection`) and the voice cue;
   the clip's own trigger runs `Vfx_Death_A` / `_B`.
4. **0x8D `_CDefeatSystem_DeathOverlay`** to the victim's player only: grey screen + overlay texture (section 3).
5. Notices `0x10000090` (to the victim's player: state 2, time of respawn: `DeadTimer`) and `0x100000BC` (everyone:
   portraits), kill feed 0x217A, kill card `0x1000021C` (victim), announcer 0x2039.
6. Respawn: teleport (seq A + 1) at the team's start, LifeState 4 (5 Respawning first is P), vitals,
   `0x10000090` / `0x100000BC` state 4, **0x8D `_Defeat_OnRespawn`** (back to Locomotion + cue), **0x11F stop of the
   DeathOverlay run** (P). `_Defeat_OnRevive` is for revives in place; `_Defeat_StartupIncapacitated` for an object
   created already down.
7. `_Defeat_OnFade` (LifeState 1) for bodies that fade: P creatures / units; champions keep their body (O).

---------------------------------------------------------------------------------------------------------------------

## 6. ics today (C, code; line numbers of 2026-10-28 18:55)

| Where | What |
|---|---|
| `ics/world.py:1558` `World.damage` | health 0 -> `alive = False`, `_death_events` (0x10000012 / statuses' 0x10000007 and removal / 0x10000098), clear combat motion, `emit("killed")` -> `Match._on_killed` -> `_champion_died` (`ics/match/match.py:1284`: score, 0x217A, kill card, announcer, 0x100000BC for others, respawn timer) |
| `ics/world.py:1601-1619` (bot) | stop bundle (`bot_motion_only` false -> full bundle, 1612), 0x6 LifeState 2 (1614), `graph_event(target, death_graph_event)` = 0x8D `0x100001E3` + `0x780` (1616-1618) |
| `ics/world.py:1630-1654` (local) | stop (1635); `death_as_property` (false, 1637) -> **else: `self.update(target, "dead (LifeState 2)")` only (1648)**; notices 0x10000090 + 0x100000BC (1649-1653); `schedule(wait, respawn)` (1654) |
| `ics/world.py:586-597` `World.update` | while a carry holds bundles (`bundle_hold`, `liftables.py:249`) the champion's bundle is held (592), also the death one; the carry's drop on death (`liftables.py:381` -> `_drop` -> `_release` -> `restore`) sends it later as a refresh |
| `ics/world.py:665` `scriptlet` / `699` `graph_event` | any resolvable key goes to the local champion and to bots (`scriptlet_keys` None, `world.py:314`); records the run in `live_scriptlets[(eid, key)]`; feeds the server's graph copy (`graph_feed`, 1156) |
| `ics/world.py:1767` `respawn` / `1796` `get_up` | vitals, teleport bundle (`send_champion`: champion + player object 0x4, no remove), then `get_up`: the first held of `respawn_scriptlets` = `_Defeat_OnRespawn` |
| `ics/match/match.py:1346-1378` `_respawn_other` (bot) | 0x6 LifeState 4, 0x100000BC alive, bundle, vitals, then at each of `bot_getup_delays` [0.0, 0.6]: `get_up` (sends `_Defeat_OnRespawn`) **and** `bot_getup_scriptlets` (`_Defeat_OnRespawn` again) = 4 runs |
| `ics/config.py:816-829`, `1438-1441` | `death_as_property` False (comment still says a full bundle "re-creates" the champion: wrong, object-update-bundles.md), `respawn_graph_events` [], `respawn_scriptlets` ["_Defeat_OnRespawn", "_Entity_OnEnterWorld_Default"], `death_graph_event` 0x100000AD, `bot_getup_delays` [0.0, 0.6], `bot_getup_scriptlets` ["_Defeat_OnRespawn"] |
| `ics/messages.py` | no builder for event 0x11F |

---------------------------------------------------------------------------------------------------------------------

## 7. Why ours does not play it

| # | Cause | Who | Tag |
|---|---|---|---|
| 1 | No fall event / scriptlet after the death bundle (`death_as_property` false branch) | local champion | **C** (code 1648, traffic 14:45:56 / 14:53:25, video AGL-3) |
| 2 | The client has no self-driven fall (no LifeState -> graph link, no code raising `0x100000AD`) | both | **C** (2.3) |
| 3 | Bare graph event instead of `_Defeat_OnDead`: same `Death` state, no voice cue | bots | C data / P minor |
| 4 | Ruled out for bots: key rejected (keys present), event unknown to AWW's graph (wildcard present), drop flag 0x40, a later bundle resetting the graph (`0x64D8A0` + diff 0xBC + BOT-1), later locomotion / CC events (none sent), ragdoll selection (needs a knock first; AWW got none in this run, only `Cower_Instant` / `Cower_Recover` once at 14:45:5x) | bots | C |
| 5 | Edge: the death bundle is held during a carry (`bundle_hold`); a fall sent right after it would reach the client before LifeState 2 | local | C code, P effect |
| 6 | The original's grey screen (`_CDefeatSystem_DeathOverlay`) is never sent; the grey seen today is P the fog | local | C (data / absence), P (fog) |

What the tester saw on the bot this time is O (no frame; all four deaths were turret kills during a retreat).

Side issues (own keys in the plan where cheap):

* Bot respawn: `_Defeat_OnRespawn` x2 at +0.0 s and x2 at +0.6 s (C): `get_up` already sends it, then
  `bot_getup_scriptlets` sends it again; the type 9 cue of `0x1D0001F6` runs per 0x8D (P: the respawn cue 4 times).
  `Global_Locomotion` has no self-transition, so the repeats are graph no-ops (C).
* Hits land on a dead champion (`VFX_CBT_Hit_Shared` at 14:53:25.990 / 26.074, C) and Will regenerates while dead
  (vitals 155 -> 170, C). No hit wildcard in the graph, so harmless for the pose; the original's rule is O.
* The client's own skill-script mirrors (0x200F effects driven by 0x20C9, `mirror_skill_scripts`) can raise graph
  events locally; one still running at death could stand the body up after the fall (P edge, never observed).

---------------------------------------------------------------------------------------------------------------------

## 8. Runtime check (only if the fix does not show the fall or the grey does not end; not needed to implement)

`tools\diag.py --grafo` already has the breakpoints (`0x2729A9` event about to reach the graph, esi = event;
`0x15AF83` local index, -1 = unknown; `0x15BD82` queued; `0x15BD9F` delivered), but each logs only its first 100 hits,
which basic attacks use up long before a death. A filtered mode (`--muerte` / `--death`) would need a per-breakpoint
filter in `tools/tracer.py` (log only when esi is `0x100000AD`, `0x100000AA`, `0x1000010B` or `0x1000009D`), plus
`0x2279D0` filtered on did `0x100001FA` / `0x100001FC` / `0x10000843`, and for the overlay `0x675280` (0x11F exec),
`0x57C4B0` and `0x767930` (Colorize released). Not added in this step: the static evidence is enough.

---------------------------------------------------------------------------------------------------------------------

## 9. Implementation plan

### 9.1 Config (`ics/config.py`)

Next to `death_graph_event` (line ~829):

```python
        # 2026-10-28 (tester report 2026-10-28 15:00: the death animation does not play when killing / being killed;
        # docs/re-notes/death-animation.md 2): a champion's fall is the 0x8D of the first of these keys it holds
        # (_Defeat_OnDead 0x100001FA: graph event CbtState_Death_Induce 0x100000AD + the death cue), sent right after
        # the message that carries LifeState 2; else the bare death_graph_event. [] = the bare event (fase3-ie's bots).
        "death_scriptlets": ["_Defeat_OnDead"],
        # same report (traffic 14:45:56 / 14:53:25: the local champion's death sent only its LifeState 2 bundle; the
        # fall was raised only in the death_as_property branch): the local champion falls too. false = fase3-ie.
        "death_fall_local": True,
        # same report (death-animation.md 6): the local champion's death bundle goes even while a carry holds its
        # bundles, so LifeState 2 precedes the fall. false = held until the carry's drop (fase3-ie).
        "death_bundle_force": True,
        # same report (death-animation.md 3, C data: the original's grey screen is the server's
        # _CDefeatSystem_DeathOverlay 0x10000843, a Colorize at saturation -100 + an overlay texture, held while the run
        # lives): sent to the local champion only (never to bots: no local-player filter) after the fall. [] = none.
        "death_overlay_scriptlets": ["_CDefeatSystem_DeathOverlay"],
        # same report (death-animation.md 4, C: event 0x11F stops a run; a 0x8D signal does not): at the respawn the
        # overlay's run is stopped by 0x11F (u8 0 | u32 key | u32 run | u8 0). false = no stop (the grey stays).
        "death_overlay_stop": True,
```

At `bot_getup_scriptlets` (line ~1441):

```python
        # 2026-10-28 (traffic of the tester report 2026-10-28 15:00: _Defeat_OnRespawn went twice at each get-up delay,
        # World.get_up already sends it; death-animation.md 7): [] = get_up's only. ["_Defeat_OnRespawn"] = fase3-ie.
        "bot_getup_scriptlets": [],
```

Optional, when touching it: fix the `death_as_property` comment (a full bundle does not re-create the champion).

### 9.2 `ics/messages.py`

```python
EVT_STOP_SCRIPTLET = 0x11F


def stop_scriptlet(entity_id, key, instance=0xFFFFFFFF, flag=0):
    """Event 0x11F (serializer 0x6751A0, exec 0x675280 -> 0x57C4B0 on the entity's script component): u8 0 | u32 key |
    u32 run instance (0xFFFFFFFF = every run of the key) | u8 flag (0 / 1). Stops the run(s): 0x529EF0 runs the end
    list and releases the attachments (docs/re-notes/death-animation.md 4)."""
    return build_message(entity_id, EVT_STOP_SCRIPTLET,
                         b"\x00" + struct.pack("<IIB", key & 0xFFFFFFFF, instance & 0xFFFFFFFF, 1 if flag else 0))
```

### 9.3 `ics/world.py`

Two helpers next to `graph_event` (line ~699):

```python
    def death_fall(self, ent):
        """2026-10-28 (tester report 2026-10-28 15:00; death-animation.md 2): the champion falls into its graph's Death
        state after the message that carried LifeState 2: the first of [ics] death_scriptlets it holds
        (_Defeat_OnDead), else the bare graph event [ics] death_graph_event."""
        for name in self.ic.get("death_scriptlets") or ():
            if self.scriptlet(ent, name, f"{ent.name}: {name} (0x8d, falls)"):
                return True
        ev = int(self.ic.get("death_graph_event", 0x100000AD) or 0)
        return bool(ev) and self.graph_event(ent, ev, f"{ent.name} falls (graph event {ev:#x})")

    def death_overlay(self, ch, on):
        """2026-10-28 (same report; death-animation.md 3-4): the dead player's grey screen, the server's
        _CDefeatSystem_DeathOverlay ([ics] death_overlay_scriptlets), on the session's champion only; at the respawn
        its run is stopped by event 0x11F ([ics] death_overlay_stop)."""
        if ch is not self.champion:
            return
        for name in self.ic.get("death_overlay_scriptlets") or ():
            key = self.data.scriptlet_key(name) if isinstance(name, str) else int(str(name), 0)
            if not key:
                continue
            if on:
                self.scriptlet(ch, key, f"{ch.name}: {name} (0x8d, death screen)")
            elif self.ic.get("death_overlay_stop", True):
                run = self.live_scriptlets.pop((ch.eid, key), None)
                if run is not None:
                    self.send(f"{ch.name}: stop {name} (0x11f, run {run})", M.stop_scriptlet(ch.eid, key, run))
```

`World.damage`:
* bot branch: lines 1616-1618 (`ev = ...; if ev: self.graph_event(...)`) -> `self.death_fall(target)`. Order unchanged:
  stop bundle, 0x6, fall. No overlay.
* local branch, lines 1637-1648:
  ```python
            if self.ic.get("death_as_property", False):
                self.send(f"{target.name} dead: LifeState 2 (0x6)",
                          M.set_property(target.eid, 0x100000FA, KIND_ENUM, M.LIFE_DEAD))
                self.death_fall(target)
            else:
                self.update(target, f"{target.name} dead (LifeState 2)",
                            force=bool(self.ic.get("death_bundle_force", True)))
                if self.ic.get("death_fall_local", True):
                    self.death_fall(target)
            self.death_overlay(target, True)
  ```
  (notices 0x10000090 / 0x100000BC and `schedule(wait, self.respawn)` stay after it).

`World.respawn` (line ~1794): after `self.get_up(ch)` add `self.death_overlay(ch, False)`. Final respawn order:
teleport bundle -> `_Defeat_OnRespawn` -> 0x11F stop.

`World.scriptlet` feeds the server's graph copy: `_Defeat_OnDead` -> `0x100000AD` (Death), `_Defeat_OnRespawn` ->
`0x100000AA` (Locomotion); `_CDefeatSystem_DeathOverlay` has no graph event (not in `shared_scriptlets`). No change.

### 9.4 `ics/match/match.py`

No code change: with `bot_getup_scriptlets = []` the loop at 1373-1376 sends one `_Defeat_OnRespawn` per delay (from
`get_up`). Bots never get the overlay (`death_overlay` returns for any entity but the session's champion).

### 9.5 Tests (`tests/test_match.py`, no ports)

Module-level helpers (frame = `u32 len | 0x02 | u64 dest | u8 flags | compact event | body`, `ics/wire.py:72`):

```python
from ics.wire import read_compact

def frames(s, since=0):
    """[(send index, label, dest, event, body)] of every frame sent since `since` (one send may hold several)."""
    out = []
    for i, (lbl, data) in enumerate(s.sent[since:], since):
        p = 0
        while p + 4 <= len(data):
            n = struct.unpack_from("<I", data, p)[0]
            fr, p = data[p + 4:p + 4 + n], p + 4 + n
            if len(fr) > 10 and fr[0] == 2:
                ev, q = read_compact(fr, 10)
                out.append((i, lbl, struct.unpack_from("<Q", fr, 1)[0], ev, fr[q:]))
    return out

def key_of(body):           # first DID of a 0x8D body: u8 0 | compact n | u8 hi | compact lo | compact run
    _, q = read_compact(body, 1)
    lo, _ = read_compact(body, q + 1)
    return (body[q] << 24) | lo

def life(body):             # LifeState in a 0x4 / 0x6 body: id 0x100000FA as sent (fa 00 00 10 40 fa 00 <v>)
    k = body.find(b"\xfa\x00\x00\x10\x40\xfa\x00")
    return body[k + 7] if k >= 0 else None
```

In the "champion death" block (after `n = len(s.sent)` and `w.damage(turret.ent, ch, ch.health + 1)`):
1. "death: the local champion's LifeState 2 bundle, then _Defeat_OnDead (0x100001FA), then the death overlay
   (0x10000843)": indices of the first 0x4 to `ch.eid` with `life == 2`, of the 0x8D to `ch.eid` with key
   `0x100001FA`, of the 0x8D with key `0x10000843`, strictly increasing.
2. After `s.clock += 20; s.run_due()`: "respawn: bundle with LifeState 4, then one _Defeat_OnRespawn, then 0x11F stops
   the overlay's run" (0x11F body = `00 | key | run | 00`: `struct.unpack_from("<IIB", body, 1)` == (0x10000843, the
   overlay 0x8D's run number from `read_compact` after the DID, 0)).
3. "nothing stands the dead champion up": between 1's fall and 2's bundle no 0x8D to `ch.eid` with key `0x100001FC` /
   `0x100002FD`, and no `0x100001E3` run whose `0x780` value is a main-machine wildcard other than `0x100000AD` /
   `0x1000010B`.
4. `w.ic["death_fall_local"] = False`, kill again, respawn: "death_fall_local false: no _Defeat_OnDead (fase3-ie)".
5. `w.ic["death_overlay_scriptlets"] = []`, kill: "no overlay, no 0x11F at the respawn".
6. `ch.bundle_hold = True` before a kill: "the death bundle is sent while a carry holds bundles, before the fall".

In the bot block (`before = len(s.sent)`, `w.damage(w.champion, bot, (bot.health or 0) + 1)`):
7. "bot death: stop bundle (LifeState 2) < 0x6 LifeState 2 < 0x8D _Defeat_OnDead" (all to `bot.eid`) and "no
   0x10000843 / 0x11F to anyone for a bot's death".
8. After `run(s, m, 30.0)`: "bot respawn: 0x6 LifeState 4 < bundle < _Defeat_OnRespawn" and "one _Defeat_OnRespawn per
   get-up delay" (count == `len(bot_getup_delays)`).
9. `w.ic["death_scriptlets"] = []`, kill the bot: "death_scriptlets []: the bare graph event" (a `0x100001E3` 0x8D to
   `bot.eid` whose variable table holds `07 80 10 80 ad`).

Also `tests/test_ics.py` (port `ICS_TEST_PORT`) if it builds messages: `M.stop_scriptlet(0x02...02, 0x10000843, 7)`
-> frame event 0x11F, body `00 43 08 00 10 07 00 00 00 00`.

### 9.6 What not to do

* No `CbtState_Dead` / `_Defeat_StartupIncapacitated` for a normal death (jumps to the held face-down pose without the
  fall); no `_Defeat_OnIncapacitated` (its `Vfx_Stop` cuts looping FX; P meant for downed states).
* No overlay for bots (it would grey the human's screen), no `World.signal_scriptlet` to end it (a 0x8D signal does
  not stop a run without a signal handler).
* Do not re-create the champion (0x3 + 0x4) to end the pose: `_Defeat_OnRespawn` does it.

### 9.7 Records

Added with this note (investigation, both passes): `catalog/data/scriptlets_other.tsv` rows `0x100001FA
_Defeat_OnDead` (used "no"), `0x100001FC _Defeat_OnRespawn` (used "yes"), `0x10000843 _CDefeatSystem_DeathOverlay`
(used "no"); `catalog/data/network_events.tsv` row `0x11F` (data only); `catalog/data/animations.tsv` `0x100000AD`
(row 141); `docs/reverse-engineering.md` section "Champion death animation: the fall is the server's"; the
`docs/CHANGELOG.md` fase3-if bullet "Death animation, investigation". `python ic.py catalog` regenerates
`scriptlets.tsv` / `index.html` (whole-file rewrite): run it once no other agent edits the catalog.

With the implementation: `0x100001FA` and `0x10000843` rows used "yes", `0x11F` "sent", `0x100000AD` "implemented",
a fase3-if bullet with the keys of 9.1.

### 9.8 What to ask the tester

Die once and kill the bot once in a match, watching both bodies: the fall (face up or face down at random), the body
lying until the respawn, standing again at the base; while dead the screen grey (desaturated, with an overlay) and back
to colour at the respawn. If the screen stays grey after the respawn: `death_overlay_scriptlets = []` in
`config.toml` and a short video (section 8 otherwise).

---------------------------------------------------------------------------------------------------------------------

## 10. Skeptic review (2026-10-29, independent re-check; no code changed)

**Verdict: partly confirmed.** The local champion's missing fall and its fix (`_Defeat_OnDead` after the LifeState 2
message) stand. The death-screen half is refuted: our builds already show the original's grey screen without any
server message, so the server-sent `_CDefeatSystem_DeathOverlay` must not be on by default. Go ahead with the
corrections below.

### 10.1 Re-checked independently (C)

- Code: the local branch sends only `update(... "dead (LifeState 2)")` (`ics/world.py` 1638-1649 today); bot branch
  1602-1620; `respawn` 1768-1795 -> `get_up` 1797-1805; bot get-up loop `ics/match/match.py` 1403-1407 = 2 x 2
  `_Defeat_OnRespawn`. The note's line numbers drifted (other agents): `death_as_property` is at `ics/config.py` 850,
  `death_graph_event` 860, `bot_getup_delays` / `bot_getup_scriptlets` 1515 / 1516. Anchor edits on the text.
- Video, ours (tester recording of fase3-ia/ib, `Videos\2026-10-27 13-22-10.mp4`, 7:27.9 - 7:39.5): the dead Gaslight
  Batman stays upright in his last pose for the whole timer (no fall). Cause 1 is also C by video.
- Graph data (AGL, AWW): `Global_Locomotion` -> 0 and `CbtState_Death_Induce` -> 15 are flags 0xC00; state 15 `Death`
  has `out: []` and the sub-machine bound to `Death_Selection`.
- Entries (`death2/entry4.py`): `_Defeat_OnDead` @`0x1481EA0`, `_Defeat_OnRespawn` @`0x1481FA0`, the overlay
  @`0x1485DF8`: the words match 2.4 / 3.2. All 156 variants of `data/champions.json` reach `0x100001FA`, `0x100001FC`,
  `0x10000843` and `0x100001E3` (`Data.scriptlets`).
- `_Defeat_OnDead` has no props, and the network table test `0x5235C0` starts from 0x211 = 2 when the entry has none
  (2 & 3 != 0), so the client accepts it from the server (as it does `_Defeat_OnRespawn`).
- 0x11F: disassembly of `0x675280` pushes `0, [+0x24] instance, movzx [+0x28] flag, [+0x20] key` to `0x57C4B0` on
  `[[ent+4]+0x10]`. The run's instance is the 0x8D's own run number (`0x627E20` hands entry words 0 / 1 = key /
  instance to `0x6279D0` -> `0x57BDC0(key, instance)`, which stores it in the instance map at +0xC / +0x18), so the
  plan's `(key, run)` addressing is right. Detail: `0x57B920` -> `0x52D790` may defer the stop to the run's time stamp
  (vt+0x60, code 0xFFFFFF01) instead of stopping at once. It still stops.
- Colorize: `0x765980` writes +0x1DC / +0x1E0 / +0x1E4 / +0x1E8 and +0x1DA = 1, and the names come from `0x76D640`.
  The effect `0x76ED70` is only built by `0x776060`, which is only called by the type 0x2D execute `0x659460`.

### 10.2 Refuted: "ics never sent it, so the grey on our builds is P the fog of war" (section 0.5, 1.3, 3)

- **Ours** (same recording, deaths at 7:27.9 and 9:46): the whole 3D view goes grey, models included, with smoke
  clouds at the screen edges. Mean HSV saturation of the view (x 20-80 %, y 12-70 %): 85 -> 34 in one frame, 23 after
  0.4 s, 7-8 while dead. Colour returns 0.13 s after the respawn teleport (7:39.5).
- **Original** (`Downloads\videoplayback.mp4`, M1, recorder's death 4:30.8): 90 -> 43 in one frame, 28 after 1 s,
  17 while dead, with the same smoke edges. Colour returns 0.27 s after the respawn teleport (4:40.3). Side by side at
  7:32 (ours) and 4:34 (original), the two look the same.
- The fog only darkens the ground (fog-vision-runtime.md 2.6). It does not grey models and draws no smoke.
- A scan of all 617 packs finds this Colorize signature only in `_CDefeatSystem_DeathOverlay` (`0xA00000DF`
  @`0x1485EF8`). The only other -100 curve is `Cinematic_FadeToBlack`'s brightness. Texture `0x13001485` is the
  overlay's and its own record. No pack or config sets `VideoPost.UseColorize` by name.
- So in fase3-ia/ib the client ran the DeathOverlay on the local death by itself. ics has no sender, and old code
  copies had none either. **How the client gets the key is O**: there is no `.text` immediate, `.data` word or string
  of `0x10000843` or `DeathOverlay` / `DefeatSystem`, no CRC32 / FNV / djb2 hash of the name, no other u32 reference in
  the packs, and no Lua or graph trigger string. hud-shop-timeline-kills.md 5.2 ("client side on LifeState 2") was
  closer than this note's correction.
- **Consequence**: `death_overlay_scriptlets` defaults to `[]`. A second run sent by the server would stack a second
  smoke texture, and if its 0x11F stop missed, the grey would outlive the respawn. Keep the 9.3 code and
  `M.stop_scriptlet` as an opt-in fallback.

### 10.3 New risk: the fall may cost the grey screen (P)

The fog explanation of fase3-gu's "no grey screen" is gone. Of that build's changes, only the fall's 0x8D touched the
local death: fase3-gt (0x6 only) was grey, fase3-gu (0x6 + `0x100001E3` / `0x100000AD`) was not, fase3-gv onward
(bundle, no fall) is grey again (videos 10-25, 10-27). There is a precedent for one scriptlet ending another on the
champion: `world.py` 2347-2352 (tester 10-28 12:27: each basic-attack scriptlet ended the Shards sphere's run). Ask
the tester explicitly: "Is the screen still grey and smoky while you lie dead?" If not, set
`death_overlay_scriptlets = ["_CDefeatSystem_DeathOverlay"]`. It is sent after the fall and stopped by 0x11F at the
respawn, and also at a match end: in the original, the M1 death at 11:40 went back to colour when the end cinematic
started at 11:44.6, with 0:06 still on the timer.

### 10.4 Other corrections and missing cases

- **Bots, "not on screen"**: not established. Deaths 3 and 4 (14:51:29.6, 14:52:16.5) were credited to GL as the
  last champion to hit the bot within 10 s (sweep S9: "+160 / +80 credits"), so GL was close by. The bot path is
  unchanged since fase3-hz, where the fall played (10-26 report). If the tester says the bot did not fall,
  `_Defeat_OnDead` (same `Death` state) will not fix it: use section 8's filtered diag.
- **Timing (P, optional key)**: the death bundle's stop is applied 0.1 s after its stamp, but a 0x8D is applied at
  once (object-update-bundles.md 6.1). The script runtime also sends every script 0x8D on the local champion
  `champion_scriptlet_delay` (0.13 s) late (`world.py` 2390-2438), so status-exit graph events from `_death_events`
  reach the client after an immediate fall. The SELF raisers found (`0x34000130` `Global_Locomotion`; `0x34000132` /
  `0x3400013B` `CbtState_GetUp`) are gated by `IsAlive(SELF)`, and ics sets `alive = False` first (`world.py` 1587),
  so this is P harmless. Still, sending the local fall `champion_scriptlet_delay` + 0.02 s late keeps the order
  "exits -> stop -> fall" and costs nothing visible.
- **Death while carrying**: `_drop` -> `_release` posts EVENT_END to the carry script (`liftables.py` 597-600) after
  the fall. Test 6 should kill during a real carry and check that no main-machine wildcard reaches the dead carrier.
  Setting `bundle_hold` alone is not enough.
- **Tests**: with `[]` as the default, test 5 flips. Add "default: no `0x10000843`, no 0x11F", and a separate test
  that sets the key to `["_CDefeatSystem_DeathOverlay"]` for the opt-in path (overlay after the fall, 0x11F at the
  respawn).
- **Records to correct with the implementation**: the "P the fog of war" sentences in reverse-engineering.md
  ("Champion death animation", death-screen bullet) and in the CHANGELOG fase3-if bullet, and the "server-sent / ics
  never sent it" wording of the `scriptlets_other.tsv` row `0x10000843`. It is client-run in our builds (C by video);
  the trigger is O.

Scratch (not in the repo): `skeptic_death/` (`satscan.py`, `sheet.py`, `colorize_scan2.py`, `sigscan.py`,
`strscan.py`, `fn.py`, `pe.py`). Video frames stayed in the scratchpad.

---------------------------------------------------------------------------------------------------------------------

## 11. Implemented (fase3-if, 2026-10-29; section 9 with the corrections of section 10)

Sections 0.5, 1.3 and 3's "the grey on our builds is P the fog of war" are withdrawn (10.2): our client runs the
DeathOverlay itself on the local death; its trigger is O.

### 11.1 Code

| Where | What |
|---|---|
| `ics/messages.py` `stop_scriptlet(entity, key, instance=0xFFFFFFFF, flag=0)`, `EVT_STOP_SCRIPTLET = 0x11F` | section 4's layout |
| `ics/world.py` `World._config_key` | an `[ics]` scriptlet entry: a name, a `"0x..."` string or a number |
| `ics/world.py` `World.death_fall(ent)` | the first of `[ics] death_scriptlets` that goes (`_Defeat_OnDead`), else the bare `death_graph_event` |
| `ics/world.py` `World.death_overlay(ch, on)` | session champion only; on: each of `death_overlay_scriptlets` (default []), the run kept in `ch.death_overlay_runs`; off: 0x11F per kept run (`death_overlay_stop`) |
| `ics/world.py` `World._local_fall(ch, fall)` | the fall (+ the opt-in overlay) `death_fall_delay` s later, dropped if the champion is alive again (`ch.death_mark`) |
| `World.damage`, bot branch | stop bundle -> 0x6 LifeState 2 -> `death_fall` (at once) |
| `World.damage`, local branch | `death_as_property`: 0x6 then the fall (as before, now `_Defeat_OnDead`); else the bundle with `force = death_bundle_force`, the fall if `death_fall_local`; then `_local_fall` |
| `World.respawn` | after `get_up`: `death_overlay(ch, False)` |
| `ics/match/match.py` `Match.end` | `death_overlay(world.champion, False)` before the end cinematic (10.3) |
| `ics/config.py` | `death_scriptlets` ["_Defeat_OnDead"], `death_fall_local` true, `death_fall_delay` 0.15, `death_bundle_force` true, `death_overlay_scriptlets` [] (10.2), `death_overlay_stop` true, `bot_getup_scriptlets` [] (was ["_Defeat_OnRespawn"]) |

`death_fall_delay` (10.4): in a simulated Gotham Divided death the Haste status's exit scriptlet `0x100003EA` (sent
`champion_scriptlet_delay` = 0.13 s late) landed before the 0.15 s fall; with no delay it would have come after it.

### 11.2 Messages now (simulated, tests/test_match.py `death_animation`)

* Local champion: `0x42` 0 hp -> status exits -> `0x217A` / kill card -> **0x4 LifeState 2** (stop inside; sent even
  with `bundle_hold`) -> `0x10000090` / `0x100000BC` -> (+0.13 s) status-exit 0x8Ds -> (+0.15 s) **0x8D
  `_Defeat_OnDead`** -> ... -> respawn: `0x10000090` alive, `0x42`, **0x4 teleport LifeState 4** -> **0x8D
  `_Defeat_OnRespawn`** [-> **0x11F** for an opt-in overlay].
* Bot: **0x4 stop (LifeState 2)** -> **0x6 LifeState 2** -> **0x8D `_Defeat_OnDead`**, then at the respawn **0x6
  LifeState 4** -> `0x100000BC` -> **0x4** -> one **`_Defeat_OnRespawn`** per `bot_getup_delays` entry (2).
* Mid-carry death (real Super Strength cast, script `0x34000164`): death bundle at once, the drop on the next tick
  (`slot 7: Super Strength again` refresh, vehicle dropped / explodes), then the fall; no stand-up event until the
  respawn. The carry script's possible `skill_to_locomotion` (EVENT_END) is a main-machine wildcard in none of the 56
  graphs; `Death` has no transition and `SM_Death` no wildcard in any of them (Vampire Batman / Zatanna:
  `Non_Ragdoll_Death` -> `Ragdoll_Death` on `CbtState_KnockUp`, still lying).

### 11.3 Tests (18 checks in `tests/test_match.py`, function `death_animation`)

0x11F bytes; graph data sanity; local: LifeState 2 bundle at once and no fall before the delay, then one
`_Defeat_OnDead` after it, no overlay / 0x11F by default, LifeState 4 bundle -> one `_Defeat_OnRespawn`, no stand-up
event (a main-machine wildcard other than `0x100000AD` / `0x1000010B`, by a `0x100001E3` run or a key whose events
`data/skill_graphs.json` lists) between the fall and the respawn, no 0x11F; `death_fall_local` false; opt-in overlay
after the fall, its 0x11F (`00 | 0x10000843 | run | 00`) after the get-up, and once at `Match.end`; mid-carry death;
bot death order, no overlay for a bot, bot respawn order and one get-up per delay, `death_scriptlets` [] = the bare
event. Mutants (scratch `death_impl/mutants.py`): `bot_getup_scriptlets` back, `death_bundle_force` false,
`death_fall_delay` 0, fase3-ie local each fail their checks.

### 11.4 For the tester

Die once and kill the bot once (watch both bodies): each falls (face up or down at random), lies until the respawn and
stands at the base. **While lying dead: is the screen still grey with the smoke edges?** If not (the fall may cost it,
10.3), set `death_overlay_scriptlets = ["_CDefeatSystem_DeathOverlay"]` under `[ics]` in `config.toml`. If a body does
not fall, section 8's filtered diag is the next step (not built).

## 12. Review fix (fase3-if, 2026-10-29): no death screen after the match end

A confirmed review finding (C ics, reproduced on the tests/test_match.py harness): `Match._on_event` runs inside
`World.emit`, so in Clash the local death that takes the last 20 team health ends the match
(`_champion_died` -> `hurt_team` -> `Match.end`) before `World.damage` reaches `_local_fall`. `Match.end`'s
`death_overlay(champion, False)` found no run, and 0.15 s later the fall's opt-in `_CDefeatSystem_DeathOverlay` started
and was never stopped (the respawn is cancelled when the client leaves the world, about 4 s after the end). A match
that ends 0.1 s after the death (a core) did the same; 0.5 s after was already right. Now `Match.end` sets
`world.match_ended` before its stop and `World.death_overlay(ch, True)` returns while it is set (`[ics]
death_overlay_skip_after_end`, true; false = as before). The fall (`_Defeat_OnDead`) still plays: a dead champion
falls during the 4 s end hold. Default config: only the late `_Defeat_OnDead` ever went, so nothing changes there.
Tests: test_match `death_animation` +2 (the Clash death ending the match falls and starts no screen; the key off lets
it start).
