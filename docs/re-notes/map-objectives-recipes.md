# Map objectives and bosses: implementable recipes (2026-10-25)

Recipes for every v AI map objective and boss, from the game's own server scripts / templates where they exist,
run headlessly in the ics script VM (NullWorld, scratch harness modelled on tools/champion_check.py). Builds on
map-manifests.md, map-gaps-gotham-divided.md, map-gaps-coast-city.md, map-gaps-gotham-heights.md,
announcer-and-map-elements.md, full-match-mechanics.md, maps-encounters.md. Tags: C = read in data / VM run,
P = probable, G = guessed (becomes a config default), O = open. Written incrementally.

## 0. Which objectives have a server script at all (C, scan of all 875 data/script_trees by value)

A scan of every decoded script for the objective classes / statuses (as int or hex values) finds only:
| DID referenced | Script(s) | Role |
|---|---|---|
| 0x40000C49 (CA Raider drop) | 0x34000670 | Raider death script |
| 0x4000035D + 0x4000054F (CC strike, pad) | 0x340001FA | Doomsday pad skill 0x4800064A |
| 0x400005E1 (heavy drop) | 0x3400007D | heavy creature death |
| 0x10000925 (cannon charge scriptlet) | 0x340002CF | GH Orbital Cannon controller |
No script names 0x40000CA2, 0x40000938, 0x40000937, 0x40000A79, 0x48000E4C, 0x4000093D / 940 / 93F,
0x400001F0, 0x40000430, 0x40000511, 0x4000089D, the dampeners or Leviathan_Spawn / _Respawn: **the spawn schedule
of every boss, pod, beacon, relay and the Device was C++ match rules on the original server**, not data. Only the
GH cannon flow, the Doomsday strike and the death drops are scripted.

Template facts used below (C, `Data.template_properties` / `entity_scripts`): capture radius 0x10000504 = Phase Pod
0x40000A79 **6.0**, Doomsday Device 0x400001F0 **5.0** (sight 9), GH cannon 0x40000511 **4.1**, GH point 0x4000013B
4.25, relay 0x4000089D **3.0**, pad 0x4000054F / CA drop 0x40000C49 1.0 (usable pads). Kill buffs 0x10000AC2: GD
Raider 0x40000938 -> **0x48000E4B**, Leviathan 0x40000937 -> **0x48000E4C**, Doomsday Guardian 0x40000430 ->
**0x48000A73**, CC Raiders 0x400007C1 / 0x40000D60 -> **0x48000CCF**; the CA Raider 0x40000CA2 has none (camp kind 7,
its reward is the drop). Unit scripts 0x10000328: Raiders 0x34000512, Leviathan 0x3400057B + 0x34000541,
Guardian 0x34000442 + 0x3400057A, buff destroyers 0x34000088 / 0x340004A1; entity scripts: CA Raider 0x34000670,
Haste 0x4000093D 0x3400051B, Regen 0x40000940 0x3400051A, dampeners 0x34000838; Device / point attack 0x340000D5.

## 1. Gotham Heights: Orbital Cannon controller 0x340002CF (C script, run in the VM)

Host: GH Power Core 0x400003F2 (template 0x10000539 = 0x340002CF, id 0x100001EB = 0xDB). It talks to the cannon
0x40000511 by entity id **165** (0x100001EB = 0xA5, C: the only template with that id). Defaults read by the VM from
the script's server block (C): LockDuration **120 s**, NeutralizedDuration **65 s**, NeutralPlusLockDuration **185 s**,
ImpactCounterMax **4**, Duration05sec 5, Duration10sec 10, DurationImpactPhase1 / Phase2 / Total **5 / 5 / 10**
(set to **20 / 10 / 61** for the 4th impact), Impact4Delay **31 s**, DestructionMagnitude Destroy 99999 / Cosmetic 10,
Small impact destroy / cosmetic radius **4.5 / 14**, Large (4th) **13.1 / 23**; generator entries
Entry_Team01_Tier01-03 = 14 / 15 / 16, Entry_Team02_Tier01-03 = 17 / 12 / 13, Tier04 = 2 (both).

Flow (graph 0, C):
1. S0 waits for event **0x10000085** (match / phase start). Exit: SendMissionEvent **0x10000060 (unlock) -> id 165**,
   RaiseEvent 0x10000129 to 0x34000285, lighting **0x956 = 0x1000000D**, UpdateObjective line **406** ("power
   signature detected"), hint 10. -> S1 (pre-fire announcement banner by ImpactCounter, tokens of 0x2B000098).
2. The cannon raises **0x1000007A** (team 1 fired, team 2 damaged) or **0x10000079** (team 2 fired) with id 165 ->
   S2 / S3: TeamFired / TeamDamaged, **ImpactCounter++**, ImpactPending = 1 -> S7.
3. S7: Entry_Current = Entry_Team<damaged>_Tier<ImpactCounter>; RaiseEvent 0x10000107 (starts graph 1, the
   impacts); banner icon 0x130029AD / 0x130016CD with a NeutralizedDuration countdown for TeamFired; if
   ImpactCounter < 4 a second banner (icon 0x130029C4) counting NeutralPlusLockDuration = "cannon available in
   185 s"; NeutralizedTimer = 65 s.
4. Timer -> S9: SendMissionEvent **0x10000078 (reset to neutral) -> 165**; if ImpactCounter < 4 -> S4: LockTimer
   120 s; exit: **0x10000060 (unlock) -> 165** and line **418** ("massive charge online") when ImpactCounter == 3,
   else **419** ("charge online") -> S1. After the 4th: S8 (LockTimer, then **0x100000C9 (lock) -> 165**) -> end.
   So capture -> 65 s held -> neutral -> 120 s locked -> capturable again (185 s cycle). Event 0x10000110 jumps
   ImpactCounter to 3 (next shot is the final one; P: overtime / test).
Impacts (graph 1, C): 5 s after the fire, for LoopIndex < LoopMax (= ImpactCounter, 1 for the 4th: tier N drops N
strikes): SetGeneratorEntry(Entry_Current) -> SpawnGeneratorUnit -> the generator answers event **0x1000001C** with
id 284 or 314 carrying the spawned impact (param hash 0x07556A74) -> (4th: 31 s delay, lighting **0x1000000B**) ->
RunScriptlet **Vfx_Spawn_Sequence 0x10000925** on the impact, Phase1 -> reveal it in fog (attribute 0x100006FC) for
Phase2 -> DestructionImpulse cosmetic + destroy at its position (small radii, large on the 4th), SetObjectState /
SetPhysicsEnabled, 10 s (5 s between strikes, P random 3-10 s) -> next; after the 4th lighting **0x1000000A**.
No node in the script touches team health or a vital: the score effect of a strike is C++ rule (O).

VM run (scratch harness: NullWorld, events 0x10000085 at 1 s, 0x1000007A at 5 s): no unknown node, but
- **bug**: RaiseEvent(SELF, 0x10000107) in S7 is delivered synchronously (`script_nodes._raise_event_node` ->
  `other.event` on the same instance), so graph 0 re-checks its transitions mid-chain while NeutralizedTimer is still
  unset (= expired): S7 -> S9 at once, the 65 s neutral phase is skipped (cannon neutral at 5 s, unlock at 125 s
  instead of 190 s). Fix: queue an event raised on its own instance until the current chain ends
  (`inst.post(ev, 0.0)`), config `[ics] raise_event_self_deferred = true`.
- the match-rule nodes are logged no-ops (`script_nodes` names): 0x10000039 SendMissionEvent, 0x1000010A
  SetGeneratorEntry, 0x10000016 SpawnGeneratorUnit, 0x1000011A ShowAnnouncement, 0x10000121 UpdateObjective (the
  line), 0x10000111 hint, 0x100000B8 / 0x100000E4 / 0x10000090: graph 1 stops at S5 -> S0 (GeneratorIID stays 0).

Recipe (GH cannon; config `[ics] match_cannon`):
1. Spawn the cannon 0x40000511 at (80, 74) (P) as objective role "cannon", tracker slot = the template's 6th entry
   (category 27, HUD 1), id 165, capture by presence radius **4.1** (C), capture time G 10 s, start **locked**.
2. Host **one** instance of 0x340002CF (both Power Cores carry it; two instances would double-count the impacts, P) on
   the team-1 Power Core with `R.start_script`; raise **0x10000085** at match start (the GH intro end).
3. Implement the match-rule nodes for this host: 0x10000039 [1, ev, 165] -> cannon state: 0x10000060 unlock (send
   Vfx_TeamColor_SetNull, capturable), 0x10000078 neutral (owner 0, 0x10000456 = 0), 0x100000C9 lock (not
   capturable); 0x10000121 [line, ...] -> 0x2001 line to both teams; 0x1000011A -> timeline banner 0x100002AF with
   the countdown operand; 0x1000009C -> 0x956 lighting on every player.
4. Cannon captured by team T: lock it, raise **0x1000007A** (T = 1) / **0x10000079** (T = 2) to the host, 0x2039
   event **54** (ch 2; 409 to the firing team, 412 to the other). The script then neutralizes at +65 s and unlocks
   at +185 s (after the RaiseEvent fix).
5. Impacts: 0x1000010A + 0x10000016 -> spawn an impact marker for (entry, tier) at the damaged team's base (G: tiers
   1-3 at the core + random 4-8 m, tier 4 on the Power Core), then raise 0x1000001C [284] on the host with
   param 0x07556A74 = the marker. On DestructionImpulse (destroy radius 4.5 / 13.1) damage units inside
   (G `strike_damage` 400 / 99999) and take `tier_team_health` = 125 (G: 4 x 125 = the 500 of 0x10000463) from the
   damaged team; play core lines 15 / 17 / 10 at 375 / 250 / 125 and end the match on the 4th (cinematic
   0x3500000D team 1 lost / 0x3500000E team 2 lost).

## 2. Gotham Heights capture points 0x4000013B (C data, P use)

- Capture radius 0x10000504 = 4.25; tables accept only Vfx_TeamColor_SetNull / SetContention /
  _CapturePoint_OnTeamBiasChanged (owner via 0x10000456) - stop sending BeingCaptured / Captured / Lost (C).
- Ring: the client derives Property_Vital_CaptureBuffer_Percent 0x1000047B (net 0, C) from the point's vital of
  VitalType **3 = CaptureBuffer**; the point's vitals list 0x1000031A has four 0x3B000095 / 96 / 9C / 9D (not in any
  indexed pack, O which index is type 3). Recipe: give points a vitals component (`client_vitals`) and send 0x42 with
  four pairs, the capture progress (0-100 of 100) in one slot; config `[ics] capture_vital_slot` default 0, to try
  0-3 in a test build.
- Attack 0x340000D5 (C defaults): SkillRange **9.0**, CooldownDuration **0.6 s**, warm-up 0.3 s,
  SkillDamageIncreasePerHit 0.2, max x3.5, x1.5 vs minions, x0.5 vs boss minions, EffectDuration 10; damage from
  the class stats 0x48000148 (SkillDamage 0 in the script). Owned points (and the Doomsday Device, same script)
  shoot enemies in 9 m: run it as the unit's basic attack (units.think) once owner != 0.

## 3. Coast City: Doomsday Device, pad strike 0x340001FA, relays, elites

### 3.1 Pad skill script 0x340001FA (C script, run in the VM)
Host: firing pad 0x4000054F (skill 0x4800064A: radius 7.5, range 10, ground target). C defaults: CooldownDuration
**3 s**, DamageCharacter Base / Delta **100 / 60**, DamageBuilding Base / Delta **750 / 100** (per Device level).
- Graph 0: enter -> StartScriptlet 0x1000020D (VFX 0x1E0005D7, the pad's active FX). On skill use 0x1000001D
  (alive, holds the action lock) -> S4 Cast at TargetPosition -> S2: SpawnEntity **0x4000035D** at TargetPosition
  (+0.1 z) with the **caster's team** (only scriptlet Vfx_OnFire, minimap 4), SetEnumProperty 0x1000001D,
  node 0x100000BD [14], node 0x1000015D (SELF, point) -> S1 (node 0x1000008E [9]). On 0x100000ED (damaged) by a
  champion-kind attacker (0x100008): StartCooldown 3 s + coaching lesson 53 + disabled VFX 0x1000020E /
  0x1E00062E until off cooldown. On 0x10000012 / 0x10000105: SpawnEntity 0x4000054F (a fresh pad).
- Graph 1: node 0x10000086 [281] + GetDetectedTarget -> DoomsdayDeviceIID (P: the Device's id 281 comes from its
  static marker 0x2E001178, no template has it), DeviceLevel = node 0x1000004B, damage = base + delta x level
  (node 0x10000003), node 0x10000118 [.., 3 = characters / 4 = buildings]; recomputed on each 0x10000060.
- VM run: no unknown node; **two gaps**: (a) T0 `S0 -> S7 on IsSkillOffCooldown` with S7 -> S0 immediately
  livelocks the instance at start (2424 re-entries in 0 s; the real engine checks a polled transition once per tick).
  Fix: evaluate polled transitions at most once per tick per region (`[ics] script_poll_once_per_tick = true`).
  (b) node 0x10000118 is emitted as a floaty number (100 / 750 at start): it is a damage setter (P "SetSkillDamage
  by target kind"), so `world.floaty` must not fire; 0x10000086 is a no-op (no device -> level 0).
### 3.2 Device / pad recipe (`[ics] match_device`, replaces charge_per_relay / damage_fraction)
1. Spawn the Device 0x400001F0 (ws 0x2E0008FD) at (80.0, 82.0) yaw 180 (C marker), id 281, scriptlets Vfx_Active +
   **Vfx_Locked**; pad 0x4000054F beside it with Vfx_Start_Pad_DoomsdayDevice 0x10001125 then
   Vfx_Active_DoomsdayDevice_Disabled 0x10001166. Level = 1 + floor(t / 90 s), max 100 (0x3B0001E7, C), t from spawn.
2. Lines (0x2001, C keys): 237 detected at spawn, 238 / 442 / 244 at -60 / -30 / -10 s, 234 at activation:
   `device_unlock` G 60 s after spawn; spawn G at 120 s (with the relays, see 3.3); then Vfx_Unlocked, pad
   Vfx_Active_Pad_DoomsdayDevice 0x10001096.
3. Guardian 0x40000430 ("the Device's defenses", line 441 at unlock) at the C camp marker (80, 57) yaw 180, patrol
   P around the Device; kill -> 0x2039 event **62** (714 / 715) and kill buff 0x48000A73 (-> 0x48000A74) on the
   killer's team (modifier 0x100000AD x -0.5, P a team-wide reduction). While it lives the Device stays locked (P).
4. Capture by presence, radius **5.0**, Vfx_CapturePoint_BeingCaptured / Captured / Lost on the Device (its own
   table, C); captured -> 0x2039 event **51** (240 enemy / 279 ours), the pad's team = owner; the owner's champions
   use the pad: cast 0x4800064A at a point <= 10 m away -> run 0x340001FA (or author it): spawn 0x4000035D there
   (Vfx_OnFire), after G 1.0 s damage enemies in 7.5 m: champions 100 + 60 L, structures 750 + 100 L; 3 s cooldown,
   pad Vfx_Active_DoomsdayDevice_Disabled while cooling.
5. Auto-fire: 0x2001 **440** at -10 s, then the server casts once at the enemy core (G `auto_fire` 30 s after a capture
   with no use) and the Device goes neutral + locked again (G `relock` 60 s, then 238 / 442 / 244 / 234 again).
### 3.3 Relays 0x4000089D (C classes / lines, G positions / timing; `[ics] match_relays`)
- Capture radius **3.0** (C); visuals only Vfx_TeamColor_SetNull / SetContention + owner 0x10000456 (C).
- Positions: no marker (C); keep (80, 131), (62, 76), (98, 76) (G; (80, 131) is 0.8 m off the navmesh -> (80, 130)).
- Timeline (lines C, times G): 241 / 248 at -30 / -10 s, 257 "unaligned relays operational" at `relays_open` 90 s.
  Two-step capture: enemy-owned -> neutral (0x2039 **59**, 459 / 460) -> own (57 "being captured" 443 / 444 at
  start, **50** captured 251 / 275), `seconds` 8 G. Owner change -> owning team's core Vfx_Relay_0N_Start then _Active
  (N = slot), _Stop on loss (C keys, P rule; today `match_relay_beams`).
- Lockout: when a team fires the Device, its relays go dark: **66** (738 / 736, "unlock in 60 s", C time) +
  core Vfx_Relay_All_Stop, **58** at -10 s, **49** unlocked + **65** reactivated at 0 (P trigger, C 60 s).
- Fix config: `relays_unlocked` 49 (not 58), `relays_unlock_soon` 58 (not 66) (announcer-and-map-elements.md 2).
### 3.4 Elite drones (lines 734 / 735, C keys; rule G)
Elites 0x40000442 / 0x40000443 replace the pair of a lane's wave once the enemy's inner turret of that lane is
down: 0x2001 **735** (top lane) or **734** (both lanes) to the gaining team. No data gives the trigger (O);
`[ics] match_waves.elites_after` = "inner_turret" (G).

## 4. Crime Alley v AI: Raider 0x40000CA2 and the tracker slot

- Class (C): ws 0x2E000F1B, camp kind **7**, attack 0x34000512, stats 0x480010D2, entity script **0x34000670**: on
  event 0x10000149 (spawned / activated) StartScriptlet 0x1000020D with VFX **0x1E000070** (its aura), on
  **0x10000007** (defeated) SpawnEntity **0x40000C49** at its own position (team argument absent: neutral pad,
  P usable by anyone; template: usable radius 1.0, active scriptlet 0x100007F8, 0x1000034C = 40, icon 0x130027DF).
  No 0x10000AC2 kill buff (unlike the GD / CC Raiders). Its tables have Vfx_Spawn_Event01-04 / Alt01-02 but **no**
  Vfx_Spawn_PhasingComplete (the GD Raider has it, C).
- VM: 0x34000670 runs clean (no unknown node); needs ics to raise 0x10000149 after the spawn and 0x10000007 on
  death on unit scripts (check units.py: today the units run only their 0x10000328 attack).
- Recipe (`[ics] match_raider` = {at: 300 G, respawn: 300 G, pos: [80.0, 97.25], yaw: 180}):
  1. 0x2001 **696** at -30 s, **699** at -10 s (C keys; both teams).
  2. Spawn 0x40000CA2 at the nook (80.0, 97.25) yaw 180 (C markers 0x2E000944 / 945; P that the Raider stands there,
     replacing that small camp), neutral team, Vfx_Spawn_Event01; 0x2001 **698** ("phasing complete"); start
     0x34000670 with 0x10000149.
  3. On death: 0x2039 event **61** (697) to the killer's team, 0x2001 **701** to the other; 0x10000007 -> the drop
     0x40000C49 (Vfx_Spawn_Event01 then its active key); respawn after `respawn`.
- Tracker: CA's template has one entry (category **26** SMALL_CAPTURABLE, slot **1**, no icon, 0x10000A9B false, C).
  The CA pack holds relay 0x4000089D and relay lines 704 / 705 / 256 ("new relay operational in 30 / 10 s / now"),
  so slot 1 is a relay (P). Recipe: relay at the jungle centre (80, 77.5)? No: the lane runs there; use the nook
  (80, 97.25) G only if the Raider is not placed there, else (80, 119) (C ambient marker 0x2E001121, G use);
  lines 704 / 705 / 256 at `relay_open` G 120 s, capture as CC 3.3 (50 on capture; 59 is not in the CA set).
- Death-event gap (C code): `World._death_events` raises **0x10000012** on the dead unit's scripts and 0x10000007
  only on its statuses; the drop / reward scripts 0x34000670, 0x3400007D, 0x3400051A, 0x3400051B wait for
  **0x10000007 {KillerIID}** on the entity script itself (and 0x34000670 / 51A / 51B first for **0x10000149** after
  the spawn). `run_unit_scripts` is False by default. Recipe: for jungle / boss units start their entity scripts at
  spawn (`[ics] run_jungle_scripts = true`), raise 0x10000149, and on death raise 0x10000007 with param
  #KillerIID = killer (hash of "KillerIID" by script_model) on those scripts; then the heavy drop 0x400005E1
  (killer's team) and the CA Raider drop come from the data.

## 5. Gotham Divided: phase pods, Raider, Leviathan, beacons, dampeners

### 5.1 What the data fixes (C)
- Phase Pod 0x40000A79 / ws 0x2E000FC7: **capturable** (capture radius 6.0, team-colour keys SetNull /
  SetContention / _CapturePoint_OnTeamBiasChanged) and **usable** (_Selection_UsableTarget); scriptlets Vfx_Spawn,
  Vfx_SpawnIdle, Vfx_Spawn_Hit, Object_Activate / Object_Deactivate, Vfx_Active_State0, Vfx_Event1 / Vfx_Event10,
  Vfx_Fade_Out, _HFSM_DestroyEntityAction; graph 0x1A000E0B clips: entrance, raider_open, leviathan_begin /
  leviathan_thump / leviathan_inactive_idle. No script, no kill buff.
- GD Raider 0x40000938: kind 6, attack 0x34000512, kill buff **0x48000E4B** (-> display 0x48000E4E), scriptlets
  Vfx_Spawn_Event01-04, **Vfx_Spawn_PhasingComplete**, Vfx_Active (C). Leviathan 0x40000937 (ws 0x2E000FA5): attacks
  0x3400057B + ground pound 0x34000541 (LoadSkillStats cooldown 15 / range 18 / damage 5, FindTargets around self,
  ApplyDamage + Vfx_Min_Leviathan_GroundPound_*), kill buff **0x48000E4C** (-> 0x48000E4D), scriptlets
  **Leviathan_Spawn 0x10000E57**, **Leviathan_Respawn 0x10000E56**, Vfx_Active_State1 / 5.
- Kill buffs 0x48000E4B / E4C / A73 / CCF share one shape: modifiers on 0x100003D4 (type 10, value from the
  record) and 0x100000AD x -0.5 (type 9), 0x1000072D = 8, 0x10000334 = 0x4000, no script; duration not in the record
  (O; G 120 s). Apply to every champion of the killer's team.
- Tracker (template 0x49000B6B, parsed exactly): **6** entries: (29, A9B 0, icon 0x1300256D, slot 1), (29, 0,
  0x1300256A, 2), (29, **1**, 0x1300256D, 3), (29, **1**, 0x1300256A, 4), (no category, slot 5), (no category,
  slot 6). Two icons x the bool 0x10000A9B: P two sites (Upper / Lower) x two stages, or two beacon pairs; with the
  four beacon lines (5.3) the best fit is **slot 1-4 = Regen, Speed, Pulse, Vision** (icon by kind, A9B = upgraded
  tier, P). No template has minimap category 29 (C): the beacon is a tracker entry only, not an entity.
- Buff destroyers: Haste 0x4000093D (script 0x3400051B), Regen 0x40000940 (0x3400051A) store #KillerIID on
  0x10000007 and nothing else; Surveillance 0x4000093F (attack 0x340004A1) has no entity script (C). The buff is C++.
- Dampener 0x40000C61 / C60 script 0x34000838 only drives the under-attack ping (UnderAttackPingDuration **5 s**, on
  0x100000E7 hit; ends on 0x10000088): **no respawn rule in data** (C).
- Encounter 0x1000021C = 600.0 on every v AI map (C, meaning O; candidate "boss / pod event at 10:00").

### 5.2 Pod -> Raider -> Leviathan recipe (`[ics] match_pods`; lines C keys, order P, times G)
1. `pods_at` G 600 s (0x1000021C): 0x2001 **685** (incoming) at -60 s, **683** at -30 s, **684** at -10 s.
2. Spawn two pods 0x40000A79 at the pits **(105, 105)** = Upper and **(55, 55)** = Lower (C sunk sites 0x2E0003F0 +
   0x2E000FBE + ctype-9 0x2E00133D / 133E; P upper = team 2's half by the -45 deg minimap), Vfx_Spawn then
   Vfx_SpawnIdle, Vfx_TeamColor_SetNull; 0x2001 **681** (touched down). Tracker: pods are not slots (beacons are).
3. Raider first: one pod (G: Upper) plays `raider_open` (RaiseGraphEvent) + Object_Activate; 0x2001 **696** / **699**
   at -30 / -10 s before, Raider 0x40000938 at the pod (+3 m), Vfx_Spawn_Event01 then **Vfx_Spawn_PhasingComplete**,
   0x2001 **698**. Death: 0x2039 **61** (697) killer's team, 0x2001 **701** other, buff 0x48000E4B to the killer's team.
4. Seismic mode, per pod: capture by presence (radius 6, G 10 s) -> 0x2001 **686 / 691** (upper / lower "seismic
   in 30 s"), **690 / 687** at -10 s, **688 / 692** initializing, **689 / 693** engaged + leviathan_begin /
   leviathan_thump on that pod; both pods engaged (P) -> 0x2001 **660** anomaly, **653** creature detected, **662**
   identified, Leviathan 0x40000937 between the pits at (80, 80) G (or the second pod's pit) with **Leviathan_Spawn**,
   0x2001 **652** emerged. Pods Object_Deactivate + leviathan_inactive_idle.
5. Leviathan death: 0x2039 **60** (666 enemy / 667 us), buff 0x48000E4C; respawn `leviathan_respawn` G 360 s with
   **658 / 659 / 663** at -60 / -30 / -10 s and **Leviathan_Respawn**.
### 5.3 Beacons (`[ics] match_beacons`; lines C, rule P)
Kill of a buff destroyer -> that team's beacon: Regen 0x40000940 -> slot 1 "Regen activated" **674**, second kill
**677** upgraded; Haste 0x4000093D -> Speed slot 2 **676 / 675**; Surveillance 0x4000093F -> Vision slot 4 (only
**680** upgraded exists); Pulse slot 3 **679 / 678** from the Heavy Mauler 0x4000093E (G: the only remaining buff-ish
heavy). Tracker 0x2069 slot owner = team, decoration 9 BeaconAlert on change. Effect (G): team aura status for
`beacon_seconds` 180 (Regen: the base aura 0x4800028B regen, Speed: 0x34000138 haste, Vision: surveillance tower
0x400007FD at the team's half, Pulse: pulse emitter 0x40000951). Replaces the two 0x400003AF "beacons".
### 5.4 Dampeners (lines / keys C, time G)
On death keep the body: scriptlet **Object_Deactivate** (ws 0x2E000E04), LifeState dead, untargetable; 0x2039
**38 / 40 / 48** (top / mid / bottom deactivated). `match_dampener_respawn` 300 s (G, existing key): at -30 s 0x2039
**64** (721 / 719), at 0 **Object_Activate** + Vfx_Active + full HP + 0x2039 **63** (725 / 718). Under attack: 0x2039
**47 / 41 / 39** throttled by the script's own 5 s ping (0x34000838; start it and raise 0x100000E7 on each hit).

## 6. VM gaps found (all three scripts run with no unknown node; behaviour gaps)
| # | Gap | Where | Fix (config) |
|---|---|---|---|
| 1 | RaiseEvent to the own instance re-enters mid-chain; an unset timer reads expired | `script_nodes._raise_event_node` | defer self events (`raise_event_self_deferred`) |
| 2 | polled transition S0 -> S7 -> S0 livelocks (0x340001FA) | `Region.check` polling | once per tick (`script_poll_once_per_tick`) |
| 3 | match-rule nodes 0x10000039 / 1000010A / 10000016 / 1000011A / 10000121 / 10000086 are no-ops | `script_nodes` `_logged` | map hooks (GH 1, CC 3.1) |
| 4 | node 0x10000118 sent as floaty numbers | 0x340001FA | damage setter, no message |
| 5 | unit entity scripts: no 0x10000149 / 0x10000007 {KillerIID} | `World._death_events` | section 4 |
