# Atomic Green Lantern: Q arm, E sphere end, R target / orb / impact (2026-10-30, tester report 15:30)

Tester (translated): (1) Q's arm projectile does not show; (2) E does not show the shield until the skill's duration
ends; (3) R must only be castable on enemy champions, sometimes loses its projectile, sometimes hits and sometimes
not, sometimes one impact and then it disappears.
Evidence: the latest run 16:36-17:00 (`logs/` copied to the scratchpad as `logs1530`: 6 Grabs, 2 Shards, **no R
cast**), the 11:05-11:28 run (`logs1105`: 5 Meltdown casts, the only R casts of the day), the 14:51 run with its
screen recording (`logs1451`, video `2026-10-30 14-51-59.mp4`, offset t = log - 14:51:59.6), the original-game video
`agl_video.mp4` (Grab 31.1-32.6 s), the script trees (`python -m ics.script_model`), pack 0xA0000150, the exe (capstone).
Tags: **C** confirmed, **P** probable, **O** open. Follows `meltdown-moving-target.md`, `agl-qer-lift.md`,
`agl-grab-arm.md`, `agl-arm-meteor-vehicle-tilt.md`.

## 1. Q Grab: the hand at the head of the arm (O, no server change)

- Original (C video 31.6-31.9 s): a solid green construct hand flies at the head of the particle streak.
- Ours (C video 141.55-142.02 = 14:54:21.15-21.62): AGL's clip raises the arm; the beam's particle line runs from AGL
  to Cyborg (141.68-141.88) and Cyborg is pulled at 142.0, so the missile object **does move to the target** (the
  beam's far end is the missile, `agl-arm-meteor-vehicle-tilt.md` 1); no hand model is drawn at the head.
- Traffic (C, 16:44:14 / 14:54:21 / 14:55:28 / 14:55:45): missile 0x40000485 created with 0x100004E2 = AGL and 0x7D2
  [0x1D000456, 0x1D0003D2], descriptor world state 0 (template 0x49000485 -> 0x510 = world state 0x2E000C4C:
  0x357 = model **0x17000F70**, 0x6B4 = 1.25, 0x50F = 7), Vfx_Active 5-9 ms later, 0x10000016 / 0x10000076, 0x3. The
  missile's motion states go unlabelled (net.py logs no `None` label), so they are not in traffic.log.
- The model 0x17000F70 is also the Shards shell's (0x2E000C89), which carries graph 0x5B5 = 0x1C000083 (animation
  0x1A00090E); the missile's world state has no 0x5B5 (C bytes @0x22089D / @0x35C5FD). P (unverified): this skinned
  construct model is drawn only posed by a graph; the earlier `--brazo` diag saw `model(ok=1)` on the missile, so the
  render model exists. No server message is missing that the data names.
- In the 14:54:21 Grab the missile left 22 ms after the client got Grab_Start (no `graph hook 5` line; the 16:44 and
  later Grabs left at hook 5, 0.16 s after it, as `graph_feed_at_send` intends) (C log). Not the hand's cause.
- Next: a diag probe on the missile's render node (draw / skin pose) for one Grab; or an A/B with a 0x5B5 sent on the
  missile (no ics code sends 0x5B5 today).

## 2. E Shards of Will: the sphere ends when the shield breaks (C, no change)

- Status 0x480007B5 script 0x340002C3: S1 AddTempVital(ShieldAmount), Shards_Active / Shards_Start; exit
  RemoveTempVital, Shards_Stop 0x1000088B. Its graph S1: `S0 -> S1 on 0x1000008C`, `S1 -> S2` when VitalExpiredHandle
  == the status' TempVitalHandle, S2 **RemoveStatus**. ics raises 0x1000008C when a shield is drained (`deal_damage`).
- Latest run (C): 16:45:02.737 -> 04.416 (1.68 s) and 16:48:37.267 -> 40.298 (3.03 s): in both the shield was drained by
  Poison Ivy's hits (16:45:04.265 "takes 3.91" = the rest of a 44.1 hit after the shield; 16:48:40.144 / .149) and the
  status left through graph S1. Shield at rank 1: ShieldAmount 50 x min(1 + 0.2 per sick champion + 0.05 per sick
  minion, MaxShield + 1 = 1.5) = 50-75 (skill stats 10 / 12 / 22 / 2).
- The game's own tooltip (paraphrased): a shield that blocks an amount of damage for a duration. So a broken shield
  ends the sphere in the original too (C data, P original behaviour).
- When the shield is not broken the sphere lasts the whole 5 s (C video 363.4-369.0 = 14:58:03.0-08.6; Shards_Stop at
  08.592). Short gaps seen in the 14:54:34 cast fall in a stealth strip (157.4-157.8) and once at 155.8-156.2 (P: the
  shell's own animation).

## 3. R Meltdown

### 3.1 The orb's effect was sent 0.1 s late (C)
`spawned_effect_scriptlets` sends Vfx_Active 0.1 s after a missile's creation. 11:22:32.685 (jump orb to an adjacent
minion): hit 85 ms after the creation, no Vfx_Active ever sent; the other orbs flew their first 0.1 s with no effect.
Fix: `[ics] spawned_effect_delays_by_class` gains `"0x40000484": {"Vfx_Active": 0.0}` (as Grab's 0x40000485).

### 3.2 The impact was cut (C)
Every orb went `0x3` 20-25 ms after its `Vfx_OnCollision 0x10000016` (11:13:39.198 -> .213, 43.876 -> .901, ...,
eleven of eleven). Its script 0x340002BE: S1 (hit) RaiseEvent 0x100000EE, hit FX, RunScriptlet(SELF) 0x10000016;
S1 -> S2 immediately; S2 RunScriptlet(Shooter) 0x10000039, node 0x1000006F, **DestroyEntity(SELF)[0.5 f32, 1]**.
`Missile.arrive` ended the missile at once (`world.after(0.0)`) before S2 even ran (S1 -> S2 comes one update tick,
~30 ms, later), so the impact effect on the orb object was removed with it.
Fix: `[ics] missile_destroy_delay_scripts` ["0x340002BE"]: a homing missile of those scripts that reached its target is
left to its script's own delayed DestroyEntity (fallback end 2 s). 61 script nodes in 55 scripts use a delayed
DestroyEntity(SELF) (0.03-2.5 s); only Meltdown's orb is listed (others: candidates, unverified).

### 3.3 Targets (C data, P rule)
- Slot block 0x100008E6 of 0x480007A2: targeting 0x1000003D = 14 (unit), no 0x10000448 / 0x1000068D / 0x100007A6.
  The client validator `0x9D01D0` then uses the defaults: relation mask 3 (enemy | neutral) and unit flags
  **0x450109** for every slot but 0 (exe `0x85F97C mov edi, 0x450109`; `0x85F986` 0x555959 for slot 0 / -1): Character
  8, Minion 0x10000, elite 0x400000, 0x40000, 0x100, 1. 18 skill blocks carry `0x1000068D = 8` (champions only;
  among them the R of Katana, Hawkgirl, Superman, Starro, Supergirl, Stargirl, Zatanna, Sinestro, Arcane Green
  Lantern, AWW and Nightmare Batman / Robin / Superman); Meltdown does not. So this client lets Meltdown target minions and neutral bosses
  (logs1105: casts on the Raider 11:20:26 and a minion 11:22:29). The orb (IsKind 0x10108) and the jump (FindTargets
  kinds 0x10108, +101 for a champion) accept minions as well.
- Fix (tester's rule): `[ics] cast_target_kind_mask` {"0x480007A2:4": 8}: World.cast refuses a unit-target order whose
  target's kind flags miss the mask, with `0x20DC` Skill_InvalidTarget 0x1000003C (the client's own error id) and the
  skill-interrupt event. The client still lets the player click a minion (its filter is the data's); the jump to a
  nearby minion stays (the tooltip: "moves to a nearby enemy").

### 3.4 "Hits sometimes, one impact and gone" (C logs1105, data behaviour)
Five casts: every orb landed (0.24-1.7 s chase); pulses ~1.1 s apart; on a target already holding 3 Rad stacks or
Radiation Sickness the status moves after its first pulse to the best enemy within 4 m, often a minion (11:16:00.517,
02.096, 05.982; 11:18:02.785), and back to the champion once its Sickness ends (11:18:06.344 -> 07.939). With the orb's
effect and impact now shown, each move is a visible orb flying from the old target. No server fault found in the
schedule. Still open from meltdown-moving-target.md 6.6: the passive's aliased TargetIID (an extra stack while its
proc is charged).

### 3.5 The target dies mid-Meltdown (2026-10-30, tester; C data, C headless, P VM order)
Tester rule: Meltdown may be cast on minions too (`[ics] cast_target_kind_mask` now `{}` by default), and when the
target (minion or champion) dies, the remaining hits go on the nearest enemy.
- **The data does it.** Status script `0x340002BF`'s exit chain (meltdown-moving-target.md 1.4): if NOT IsAlive(SELF)
  and NumRemainingPulses > 0 and DamageSuccess, the same jump search as the 4-stack jump: FindTargets(JumpRange) [add
  radius 1, kinds 0x10108, relation 3, max 12], best = non-sick +202, champion +101, then 1 / distance; if one exists,
  LaunchMissile `0x40000484` at it (no RemoveStatus: the status is ending anyway). **JumpRange = skill stat 23 = 4 m**
  (measured from the dead target; its +1 add radius as for the pulse). The orb's hit runs AGL's `0x340002B4` S2:
  AdjustedEffectDuration = PulseDuration x PulsesRemaining. So "nearest" is the data's score: a champion within 4 m wins
  over a nearer minion, a not-sick enemy over a sick one, then the nearest. Nobody within 4 m: no orb, Meltdown ends.
- **ics already ran it** for a death by any other hit: `World._death_events` (`death_script_events`) raises
  0x10000007 on each status of the dead entity and removes it; the removal event runs S1's exit chain with
  IsAlive(SELF) false (`World.damage` sets `alive = False` first). Headless: target killed after pulse 1 -> an AGL orb
  from the corpse to the next enemy at once, EffectDuration 5 (PulsesRemaining 6 - 1), 5 pulses in all.
- **One pulse too many when the pulse itself kills (fixed).** A pulse is ApplyDamage(SELF) inside the status' update
  chain; the death was handled inside that node, so the status ended and jumped before the chain's own
  NumRemainingPulses - 1 and RaiseEvent 0x10000006 (AGL's PulsesRemaining - 1) ran: the next target got 6 s (6 pulses
  in all). The client VM queues events (0x96DED0), so the death's 0x10000007 / removal comes after the running chain
  (P, the same rule as `status_self_remove_after_chain`). `[ics] death_status_end_after_chain` (true): a status whose
  own chain is running when its owner dies (`Chain.run`'s `_chain_depth` or `run_nodes`' new `_run_depth`) gets
  0x10000007 and its removal by `after(0.0)`; false = at once (the fase3-ir behaviour).

## 4. Validation
`tests/test_meltdown.py` 54/54 (+4: orb effect <= 0.06 s after creation, orb gone 0.4-0.7 s after its impact, R at a
minion refused with 0x1000003C, no orb launched), test_match 557/557, test_scriptvm 78/78, test_graph 34/34, test_ics
40/40 (ICS_TEST_PORT=21531).
- 2026-10-30 (3.5): `tests/test_meltdown.py` 77/77 (case 8, `target_dies`: R on a minion with the bot 1.5 m away and
  on the bot with a bot-team unit 2 m away, killed by a hit after pulse 1 and by pulse 1 itself -> one AGL orb from the
  corpse to the other enemy at the death, EffectDuration one pulse less, 5 pulses in all; the bot alone, with a unit
  6 m away (beyond 4 m) and alone killed by its pulse -> no orb, 1 pulse, no Meltdown left, no error; the key off ->
  6 pulses), test_match 573/573, test_scriptvm 78/78, test_ics 40/40 (ICS_TEST_PORT=21537), test_graph 34/34,
  test_director 43/43.
