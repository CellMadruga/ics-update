# Turret head lost on target, the Power Core Turret's real parts (2026-10-30, tester report 12:05)

Tester run 11:59-12:05 on build fase3-ir (Crime Alley v AI, Atomic Green Lantern vs a bot). Logs: that run's
`server.log`, `traffic.log`, `diag.log` (fog ring only), `unhandled.log` (empty). Screenshot 88 (ours: the blue Power Core
Turret on the gear plate with the lane body); original frames 66 / 67 (blue, start of a match) and 70 (red, destroyed).
Tags: **C** confirmed (data, traffic, decompiled exe `re-work/decomp`), **P** probable, **O** open. Scripts in the
session scratchpad (`pct2/`); nothing of the game copied. Builds on `power-core-turret.md`, `turret-heads-coredeath.md`,
`scorecard-panel-turret-head.md`, `client-scriptlets-graphs.md`, `agl-e-r.md` 1.2.

## 1. "When the enemy tower targeted me, its head disappeared" (C traffic / data, P cause)

### 1.1 What went to the turret (traffic, `turret mid t2`)
Spawn keys at 12:00:37 (Vfx_Active run 0x0F, Vfx_AI_Active run 0x36 = the client-made head), then nothing until AGL came
in range: 12:02:09.698 `0x10000C66 = 0x200000000000002` + **Target_Acquired 0x1000014A** (run 0x6D, variables 0x10000030
and 0x108 = AGL), 12:02:10.229 `0x10000C66 = 0` + **Target_Lost 0x1000002C**; the same pair at 12.392 / 13.406 and
15.087 / 16.827 (no shot: AGL left the reach), then 17.988 acquire + Object_Ranged_Attack / Vfx_Basic_Ranged at 17.989
and 19.018, lost at 19.460. No 0x11F, no bundle, no graph event, no Vfx_AI_Active again. With
`match_turret_pick_in_reach` there was no same-tick flap any more; the head still went.

### 1.2 The keys (C, tables in pack `0xA0000162`)
- Body `0x1D00035D` Target_Acquired = two type-0x17 runs of **Vfx_Targeting `0x1000005C`** (no binding: the body
  itself; 0x163 = 0); Target_Lost = the same two with 0x163 = 1 (signal / stop).
- Base `0x1D000372` Vfx_Targeting = the type-0x22 targeting beam (meshes `0x17000001/03/00`, side colours) from point
  `0x10000043` to `0x10000082`; Vfx_AI_Active = type-0x0C spawn of the head `0x2E000AA8` (0x160 = `0x100000FE`, 0x325 =
  Vfx_Startup, scale 0.9).
- Head `0x1D00035C` Vfx_Targeting = graph event `0x1000009C` (Combat_Idle), a type-0x0F hold, on end graph event
  `0x1000013D` (Idle). The head's graph `0x1C00006E` is `env_pvp_lane_turret_head_a_behavior` (events state_to_state,
  Combat_Locomotion, Global_Locomotion only; both states play the idle clip): neither event changes it. The flag head
  `0x2E000AC3` has graph `0x1C00006A` = `env_pvp_powercore_a_turret_head_behavior` (Idle / Combat_Idle = the same clip
  at 1.0 / 2.5x).
- The turret's attack script **0x34000014** (C, script dump): Cast -> BeginSkill -> S3 RunScriptlet
  Object_Ranged_Attack `0x100002E0`; it never runs Target_Acquired / Target_Lost. ics sends them since 2026-10-23 as a
  guess (`match_turret_target_scriptlets`).
- Client run start `0x57B9D0` (C): with a live instance number the run is signalled; with the "no instance" value
  (`DAT_0185F2B0`, what a type-0x17 action uses) it also walks the component's list `+0x1C/+0x24/+0x28` (key -> child
  forwarder) and runs the key on the child: the spawn's wired keys. So Target_Acquired's local Vfx_Targeting runs reach
  the client-made head, and Target_Lost's stops do too.

### 1.3 Cause (P) and fix
The head first vanished in fase3-ip, the build in which it became the client child (`match_turret_head_skip_own_child`,
2026-10-29 23:03); while the head was a server object, Target_Acquired never reached it. P: the forwarded Vfx_Targeting
start / stop (two runs each, from a key the original server never sent) ends or hides the child. `[ics]
match_turret_own_head_no_target_keys` (true): no Target_Acquired / Target_Lost for a structure whose head is its own
Vfx_AI_Active child; the warning-ring target 0x10000C66 and the shots stay. false = as before. O: if the original drew a
targeting beam, it came from elsewhere (`cinematics-vfx-audio.md`: one client site names Target_Acquired / Vfx_Targeting,
not traced); next step if the head still goes: `diag.py` on `0x57BAF0` / `0x516F80` with the body's IID.

## 2. The Power Core Turret's look (C data, P fill, O prow)

### 2.1 What the frames show (G)
66 / 67 (blue): the core platform has a pointed **prow** to the east; in a round socket on it a glossy, opaque blue
cylinder about 1.5 m high, a translucent flag hologram over it, a health bar. 70 (red, destroyed): the prow with a red
disc in the socket and two fallen rings. 88 (ours, fase3-ir): round platform, no prow; the lane turret's dark body
and ring head on the 6.26 m gear plate.

### 2.2 Its parts (C)
- Class `0x40000C8F` (team 1) -> world state **`0x2E000AC4`** (rig `env_pvp_powercore_turret_a_body`: Root, Base,
  Ring_Base, Ring_A_A/B, Ring_B, Ring_C_A/B/Hub, Vfx_Ground, Shield, Head_Aim; graph `0x1C000069` = the lane body's
  `env_pvp_lane_turret_a_body_behavior`: Master (Aiming) twist on UsToTargetHeading, Death / Idle clips). Tables
  `0x1D00035F` + `0x1D000374` + `0x1D000600`.
- `0x1D000374` Vfx_Active: looping sound, hold, type-0x0C spawn of **`0x2E000A9A`** (z -0.25, scale 1.0, 0x325 =
  Vfx_Startup); Vfx_AI_Active: spawn of the flag head **`0x2E000AC3`** (0x325 = Vfx_Startup, scale 0.9). The lane base
  `0x1D000372` spawns `0x2E000A9E` / `0x2E000AA8` instead.
- `0x2E000A9A` (ctype 9, table `0x1D00060A`, base `0x1D00038B`): Vfx_Startup = the side-coloured hologram overlay
  (type 0x22, as the heads'), **Vfx_Object_Phase1..14 + Vfx_Object_Reset**: each one type-0x2E action on group
  `0x10000002` (values 16, 13, 18, 4, ... reset 2 / 12). Nothing else has these keys: they are driven by the body.
- Body `0x1D000600`: **Object_Reset `0x100002C0`** = type-0x17 run of Vfx_Object_Reset; Object_PhaseN = run of
  Vfx_Object_PhaseN. `0x1D000374` Vfx_Object_Reset = a timeline of type-0x17 runs of Vfx_Object_Phase keys
  (`0x100002DB`, Phase1, Phase2, ...). The body has no Vfx_Object_PhaseN of its own, so (1.2) they go to the A9A child.
- Body `_Entity_OnSetClientRelationship` (both bases) = a local run of Vfx_Active: the client re-runs it on every team
  change.
- The red `0x40000C8D` uses the lane body `0x2E000AA0` by data (as its twins `0x40000C8E` / `C86`).
- Search of every pack for `prow`, `pedestal`, `platform`, `powercore`, `core_base`, `turret_base` names (C): only the
  rigs above, the core `env_pvp_powercore_a`, the heads; no prow / socket model. With `deep-scan-maps.md` 9 (no
  ruleset-only statics but the team-2 core pedestals) and `crime-alley-still-missing.md` 8 (the Clash video has no
  prow): the prow is not in this client's data (C for the names / statics, P for "another build").
- The render-mesh link of `0x2D0008D4` / `0x2D0008B7` is still unresolved (O): the rig names say AC4 has no
  Lane_Turret_A mesh node, but the destroyed frame 70 shows rings, so AC4 may draw ring parts (tester 23:03 saw only the
  "blue transparent effects", P the rings sit in the prow's socket in the original).

### 2.3 What changed
- `match_turret_plates`: no `core_turret` (the gear plate is the lane turret's, not the PCT's: frames 66 / 67 / 70).
- `match_structure_classes` = {}: the blue one is `0x40000C8F` / `0x2E000AC4` again (A9A cylinder + AC3 flag head = the
  original's shapes); the red one stays `0x40000C8D` by data.
- `match_structure_scriptlets["core_turret"]` += `Object_Reset` (last, after A9A exists): P the cylinder's opaque fill
  (fase3-io showed it translucent: no phase had been set).

## 3. What the tester should see
1. A lane turret keeps its blue / red head while it targets and shoots the champion.
2. The blue Power Core Turret: no gear plate; a blue cylinder (hopefully opaque now) with the flag hologram over it, on
   the platform's edge. The prow itself cannot be drawn (not in the data).

## 4. Open
- O: whether Object_Reset makes the cylinder opaque; if not, the next tries are Object_Phase1 (full health) or the
  cylinder's Vfx_Active_Blue (base `0x1D00038B`, appearance `0x19001299`).
- O: the damage phases (Object_Phase1..14 by health) are not sent; `cinematics-vfx-audio.md` says the client maps damage
  states to keys itself (P).
- O: the red Power Core Turret's look (data: lane body); `match_structure_classes` {"crime_alley": {"core_turret":
  {"2": "0x40000C8F"}}} would give it the blue one's parts (stats of C8F, colours by side 5).
