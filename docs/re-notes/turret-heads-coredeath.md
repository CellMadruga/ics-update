# Turret heads, the Power Core Turret's body, the Raider's kill voice, the match end (2026-10-29, fase3-im)

Tester report 2026-10-29 23:03 on build fase3-io (exe patched 22:36; run 22:36-23:03, several Crime Alley v AI
matches; the first ended "team 1 wins (core destroyed) after 670 s" at 22:51:45). Screenshots 82 (ours, blue base)
and 83 (ours, blue lane turret); original frames 64-72, 77. Logs: that run's server.log / traffic.log.
C = read in data / code / logs, P = probable, G = guess, O = open. Table dumps with the scratchpad's `pct/tab.py`
(raw words of one scriptlet); nothing of the game copied. Builds on `power-core-turret.md`, `throw-padlock-coredeath.md`,
`announcer-and-map-elements.md`, `cinematics-vfx-audio.md`, `client-cinematics-matchend.md`.

## 1. Two heads on a turret (C data, C traffic, P which is white)

- Traffic 22:39:24.175: `spawn turret mid t1 head (0x2e000aa8)` (the server-made head of `[ics] match_turret_heads`),
  then 22:39:35.910 `turret mid t1: Vfx_AI_Active (0x8d)` (from `match_structure_scriptlets["turret"]`).
- Lane turret base table `0x1D000372` Vfx_AI_Active `0x10000D63` = one type-12 spawn: child **`0x2E000AA8`**, scale
  0.9 (`0x3F666666` x 3), event `0x100000FE` -> Vfx_Startup `0x1000018E`, then Vfx_Targeting `0x1000005C` wired (C).
  So the client already makes the head; the server's was a second copy of the same model.
- Screenshot 83: the blue head on the body plus a white one beside it; fase3-in made the server heads Vfx_Startup-only
  (`match_turret_head_team_keys` false), and their colour stayed Null (white). The original (frame 68): one blue head.
- The dampener (x 40 / 120) never had a server head: Vfx_Active spawns `0x2E000A9E` (zero box: particles, no mesh) and
  Vfx_AI_Active spawns `0x2E000AA8` (scale 0.75, z -1.4) (C, table `0x1D00063A`). The grey tilted ring in screenshot 82
  is P the body rig's own Ring part (`env_pvp_dampener_a`), not a head.
- Fix: `[ics] match_turret_head_skip_own_child` (true): no server-made head when the role's body scriptlets include
  Vfx_AI_Active and its tables hold it. Applies to every turret type (`match_turret_heads` still names the head for
  roles without their own). The head's Vfx_Targeting on target changes is the client child's own (wired in the spawn).

## 2. The Power Core Turret with no body (C data, P look)

- Screenshot 82: at (27, 77.5) only a translucent blue cylinder with a flag hologram; the original (66 / 67) has an
  opaque glossy blue cylinder in the core prow's socket under that hologram.
- World states (C, raw records): `0x2E000AC4` and `0x2E000AA0` carry the same 13 properties (graph `0x1C000069`,
  0x7EB 7, collision 1.4 x 1.4) except **0x50F 8 / 7**; entities `0x2D0008D4` / `0x2D0008B7`.
- Rig names in pack `0xA0000162` (C): the lane body `env_pvp_turret_powercore_a` has `Root, Base, Ring_*, Shield,
  Vfx_Ground, Head_Aim` **and `Lane_Turret_A` / `Lane_Turret_A_Head`** (mesh nodes); the PCT body
  `env_pvp_powercore_turret_a_body` has the same bones and **no mesh node**. So `0x2E000AC4` draws only what its
  scripts spawn: the Vfx_Active child `0x2E000A9A` (ctype 9, table `0x1D00060A`: Vfx_Startup + Vfx_Object_Phase1-14,
  base `0x1D00038B` = the heads' colour keys; spawned at z -0.25 with no Vfx_Startup) = P the translucent cylinder,
  and the Vfx_AI_Active head `0x2E000AC3` = the flag. Vfx_Fade_In (fase3-io) changes the alpha of a mesh that is not there.
- Template diff `0x49000C8F` / `C8E` / `C8D` (C): **`0x40000C8E` = `0x40000C8F` property for property** (3500 HP,
  0x10000B84 35, 0x10000B76 185, regen 0x10000140 50, side 3, team 1, range, credits) **except 0x510 = `0x2E000AA0`**
  (and its 0x7D2 list); the red `0x40000C8D` uses `0x2E000AA0` too. Both are in Crime Alley's `0xA00002E6`.
- Fix (P): `[ics] match_structure_classes` {"crime_alley": {"core_turret": {"1": "0x40000C8E"}}}: the blue Power Core
  Turret is the twin on the lane body (dark body + team column + its own head `0x2E000AA8`), as the red one is by data.
  Vfx_Fade_In still goes (a class table holds the key; harmless on a mesh that draws). {} = `0x40000C8F` /
  `0x2E000AC4` again.
- O: the original's glossy cylinder and the prow piece it stands in. No Crime Alley world state with a prow-sized box
  exists (`crime-alley-structures.md` 3, `stubborn-visuals.md` 4); the "base" the tester misses is that prow (O). If the
  tester wants the flag head back, the next try is the original class plus a server-made `0x2E000A9A` with side and
  Vfx_Startup (its colour keys), which no build has sent yet.

## 3. The Raider's kill voice (C traffic, C sets)

- 22:49:46.405 Raider defeated (by Gaslight Batman, team 1). Traffic: 46.463 `announcer event 61 channel 2 (0x2039)`,
  49.383 `announcer line 0x2bd channel 2` (= 701, "the enemy defeated the Raider"), both to the same (team 1) player.
- Set rows (C, `announcer-and-map-elements.md` 0.1): event 61 has only the acting-team column (0x1000082A = 697); 701 is
  the other team's line. `Bosses.on_killed` sent the event for the killer's team and 701 to everyone.
- Fix: `[ics] match_boss_kill_voice_by_team` (true): killer = local team -> event 61 only; otherwise line 701 only.
  The same path covers Gotham Divided's Raider (`match_pods.raider`).

## 4. The match end cut short (C traffic, C cinematic data)

### 4.1 What was sent (traffic 22:51:45-49)

| Time | Message |
|---|---|
| 45.881 | core t2 vitals 0 |
| 45.909 | cinematic `0x3500003A` (0x20F5) |
| 45.910 | billboards stop 0x100002BC, **billboard type 9 (VICTORY)** |
| 45.951 | core t2 dead (bundle) |
| 46.845 | announcer event 29 channel 1 (queued 1.0 s) |
| 49.877 | **0x1000000E** match ended -> the client leaves the world at once (`0xa809e0` -> `0xab52a0`, C) |

### 4.2 The cinematic (C data, `cinematics-vfx-audio.md` 1.3)

- `0x3500003A` / `3B`: **11.50 s**, no script; actor PowerCore `0x2E000AC5` (side, team): frame 0 Vfx_Destruct_State0,
  **frame 225 Cinematic_Announcement** {0x100008F6 = winner, 0x100008F7 = loser}. 30 fps (0x35000038: frame 2130 in 72 s;
  0x35000025: 590 in 23 s), so 225 = **7.5 s**. Gotham Divided / Coast City (11.5 s) raise `0x100000F2` / `F3` at 225,
  whose scripts play event 29; Gotham Heights `0x3500000D` / `0E` (10.5 s): Vfx_OnExplode 120 (4.0 s),
  Cinematic_Announcement 210 (7.0 s).
- Core table `0x1D00098A` (C dumps): Vfx_Destruct_State0 `0x100000EA` = a type-35 render action (14.0), a timeline
  (1.0 s: stop Vfx_OnExplode + graph event Death `0x100001C0`; 13.0 s: graph `0x1000013D` ...; 7 actions incl.
  Vfx_Destruct_State1 `0x100000F5` = side-chosen particles `0x180009AD` / `AC` / `0x18001456`, and child `0x2E00103B`).
  Cinematic_Announcement `0x10000A50` = fx `0x1E00035F`, Vfx_Indestructible_Stop, a type-34 mesh action
  (`0x1700132F`, travel -600), particles `0x18000A8A` by side: P the explosion out of the hole and the announcement.
- So the original order (P strong): the core falls (0-7.5 s), then the explosion / announcement at 7.5 s, the
  cinematic ends at 11.5 s, then the end page. Ours put VICTORY at 0 s and left the world at 4 s: the fall was cut and
  frame 225 never played; the event-29 voice at 1 s was P lost with the world (or under the cinematic's start).

### 4.3 Fix

`[ics] match_end_timing` {map: {"announce", "notice"}}: with an end cinematic, billboard 0x100002BC + type 9 / 8 and
the victory voice (event 29, team = winner: 393 Victory for the winners, 392 Defeat for the others; skipped on GD / CC,
whose cinematic scripts voice it) at "announce" s after the core's death (CA / GD / CC 7.5, GH 7.0), 0x1000000E at
"notice" (12.0 / 11.0 = cinematic + 0.5 s, at least announce + match_end_hold). {} = fase3-io. Without an end
cinematic (surrender with none, team health) the old timing stays.

## 5. What the tester should see

1. Each lane turret and dampener: one head, blue (red on the enemy's), no white copy.
2. The blue Power Core Turret: an opaque dark body with the team column and a head, like the red one (not the flag head).
3. Raider killed by us: "our team has slain the Raider" only; by the enemy: "the enemy defeated the Raider" only.
4. The core's whole fall, the explosion from the hole, then VICTORY / DEFEAT with the announcer's Victory / Defeat, and
   the end page about 12 s after the core died.

## 6. Open

- O: the prow and the glossy cylinder of the original's blue Power Core Turret (2).
- P: whether the voice plays during the cinematic for CA (GD / CC prove the dialog channel works then).
- P: Cinematic_Announcement shows its own banner; if VICTORY shows twice, set the billboard off for maps with it.
