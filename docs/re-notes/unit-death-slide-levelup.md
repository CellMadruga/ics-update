# Unit deaths, the dead slide, the level-up ribbon icon (2026-10-29, fase3-ih)

Trigger: tester report 2026-10-29 12:45 (Crime Alley v AI, run 12:12-12:24, Atomic Green Lantern `0x4000080C` vs bot
Harley Quinn; `logs/server.log`, `logs/traffic.log`, frame 44 of the tester's recording).

Tags: **C** = confirmed (code, data or log bytes read), **P** = probable, **O** = open.

## 1. Drones / camp creatures: no destruction animation

Tester: "when their health runs out they stand still a moment and disappear".

* Traffic (C): `mid melee 1 t1 w1` at 12:15:02.383 0 hp; 02.416 one 0x4 bundle (`0x100000FA = 2`, speed 0); 02.417 the
  killing hit's `VFX_CBT_Hit_Shared 0x10000223`; 4 s later 0x3. Nothing else. ics `World.damage` unit branch
  (`ics/world.py`) only sent `update(target, "dead")` and scheduled the removal.
* Data (C, `Data.scriptlets(class, world state)`): every unit class of the run that dies holds `_Defeat_OnDead
  0x100001FA` and `_Defeat_OnFade 0x100001FE`:

| Class | World state | World-state table | Also holds |
|---|---|---|---|
| `0x40000BF8` / `0x4000010A` melee drone | `0x2E000808` | `0x1D0002F8` (bases `0x1D0002FA`, `0x1D0002F7`) | `Vfx_OnExplode`, `Vfx_Despawn`, `_HFSM_DestroyEntityAction` |
| `0x40000BFA` / `0x4000010B` ranged drone | `0x2E000840` | `0x1D0002F9` | same |
| `0x40000BF9` / `0x4000010D` siege drone | `0x2E000E21` | `0x1D0005D3` | same |
| `0x40000CA0` / `0x40000CA1` camp creature | `0x2E000BE2` | `0x1D00042D` | `Vfx_OnExplode` |
| `0x40000CA2` | `0x2E000F1B` | `0x1D000677` | - |

  Class tables (all of them): `0x1D0000E2`, `0x1D0000E1`, `0x1D0000E8` (the champions' defeat table: `_Defeat_OnDead` =
  type 0x14 raise of `CbtState_Death_Induce 0x100000AD`), `0x1D000385`.
* Minion `_Defeat_OnDead` entry (pack `0xA000006F` @`0x315794`, raw words, C): `100001fa 0 0 1 | 17 1 0 10000079 ...`
  (type 0x17: run `Vfx_OnExplode` on the target list) followed by two type 0x16 clears of `0x100003AF` /
  `0x100003B0`. Which table's entry the client picks (class `0x1D0000E8` fall vs world-state explode) is **O**; the old
  server sent `0x100001FA` on Tutorial 1 drones and the tester saw "the drone falls on its back" (CHANGELOG 2026-10-13, C).
* `_Defeat_OnFade` (pack `0xA000006F` @`0x315880`): one type 8 action with floats 2.0 / 1.0 / 10.0 and texture
  `0x13000CDC` (P: a 2 s dissolve of the body).
* No client code runs `_Defeat_*` (death-animation.md 2.3, C), so the server must.

**Fix** (`World._unit_fall`, called for `kind == "unit"` after the death bundle): the first of `[ics]
unit_death_scriptlets` (["_Defeat_OnDead"]) `unit_death_fall_delay` (0.15 s) later (after the stop state applies and
the hit 0x8D), the first of `unit_fade_scriptlets` (["_Defeat_OnFade"]) `unit_fade_delay` (2.0 s) later, the 0x3 at
`corpse_seconds` (4.0) as before. [] = fase3-ig.

**Tester should see**: a dying drone falls / explodes where it stands, fades, then goes. **O**: whether the fade is right
(if the body vanishes too early or flickers, set `unit_fade_scriptlets = []`); bosses / Raider / structures untouched.

## 2. AGL slid a little while falling (first death)

* server.log (C): 12:16:14.760 `move -> (63.4, 78.1) (2 segments)`; 14.912 AGL 0 hp; 14.913 defeated; **15.009
  `move -> (62.9, 78.2) (3 segments)`, 15.020 `move -> (62.8, 78.2)`**; 15.101 `_Defeat_OnDead`.
* traffic.log (C): 14.938 the death bundle (LifeState 2, stop); 15.002 / 15.013 two 0x20EE move orders from the client.
* Cause (C code): the client gates orders on LifeState 4 (client-movement.md 0) but applies a state 0.1 s after its
  stamp, so it still sent the clicks; `Session.ev_order` had no alive check; `World.walk_to` set the path and
  `World.tick` moves any entity with a destination, dead or not. The champion's per-tick states (unlabelled sends, not
  in traffic.log) walked the body during the 0.15 s before the fall and while falling.
* **Fix**: `[ics] dead_orders_ignored` (true): `ev_order` drops every order of a dead champion; `[ics] dead_hold_still`
  (true): `walk_to` refuses a dead champion / unit, and `World.tick` clears a destination left on a dead body with a
  stop state.
* **Tester should see**: the body falls where it died, even when clicking right after death. **O**: knockback motions
  at the killing blow are a separate path (Combat state cleared at death, unchanged).

## 3. "Champion Level Up!" popup without a portrait

* AS2 (C): `WrapperMain.RecvNotice_Ribbon_CharLevelChanged(i_didCharacterIcon, name, prev, level, totalXP, pct,
  nextLevelXP, didCharacter)` -> `CharLevelUpRibbon.SetData`: `m_icAccountIconContainer.SetIcon(didIcon)`. The summary's
  `AccoladesChampionDisplay` portrait is `ScorecardManager`'s `DidCharIcon` from the same message.
* C++ (C, decomp `0xA7E0A0`, the 0x2104 exec): stores champion +0x14C, **icon +0x150** (the u32 after the champion),
  level +0x118, prev +0x11C, field 3 +0x120, field 8 +0x124, field 6 +0x130; when level != prev it calls `0x88E780(icon,
  name, prev, level, +0x120, +0x130, +0x124, champion)` = the ribbon notice. ics sent icon 0 (traffic 12:24:25.088).
* Same message, wrong number order (C screenshot): the summary bar read "720 / 1061997773" (Total / ToNext) =
  our field 3 (720, meant as to-next) / the bits of our last f32 (0.8 = `0x3F4CCCCD`), and Earned 0 = our field 4.
  Client order: level, prev, total, earned, bonus (P), f32 pct, f32 prev pct (P), u32 to next.
* **Fix** (`ics/matchend.py champion_icon`, `ics/messages.py character_level(layout=)`): icon = the variant's
  `data/champions.json` `tex384` (the kill card's portrait; `[ics] level_up_icon`: tex384 / grid_icon / tex799 / "");
  `[ics] character_level_layout` "client" ("old" = fase3-ig).
* **Tester should see**: AGL's portrait in the ribbon box and the summary's champion hexagon; the XP bar text like
  "0 / 720". **O**: which picture the original used (tex384 vs grid_icon: change the key if it looks cropped); whether
  "to next" means the threshold or the remainder (we send the remainder); the tutorial's 0x2104 (icserver/scorecard.py)
  keeps the old order.

## 4. Tests

`tests/test_match.py unit_death_slide_levelup` (12 checks); test_match 327/327, test_session_flow 81/81, test_ics 40/40,
test_director 43/43.
