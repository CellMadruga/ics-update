# Skill animations vs the original: generic causes that cut or skip them (2026-10-29, fase3-ih)

Tester report 2026-10-29 12:45 (run 12:12-12:24, Crime Alley v AI, AGL vs the bot Harley Quinn; recording
`Videos/2026-10-29 12-09-37.mp4`, logs `server.log` / `traffic.log` of that run): "AGL's animations are still not complete;
the problem is with every champion: some skill animations do not look right". Follow-up: Q must launch its arm as the
projectile; E's sphere never shows completely and goes when AGL attacks; R's flight is sometimes not seen, its detonation
is late / sometimes missing and the enemy is not slowed; W still does not play right.

Sources: both videos (frames with cv2, scratch `sheet.py`), the run's logs, `data/skill_graphs.json`, the script trees
(`python -m ics.script_model`), `ics/world.py`, `ics/script_runtime.py`, `ics/graph.py`. Tags: **C** confirmed (log /
traffic / code / data read), **P** probable, **O** open. No game text or images are copied: only ids, names of states /
events / keys and times.

Clock sync (C): the recording starts at 12:09:37.4 (the taskbar clock turns 12:14 at video 262.6 s); video t = log time -
12:09:37.4. The original AGL video (YouTube promo, 137 s): passive 18-29 s, Q 30-41, W 42-50, E 51-59, R 60-74.

## 1. How a skill animation reaches the client (C, recap)

The client plays its own copy of the champion graph. ics drives it only with 0x8D messages: scriptlet 0x100001E3 + variable
0x780 = a graph event (RaiseGraphEvent), and keys whose table entries raise graph events. The server runs its own copy of
the graph (ics/graph.py, the BGE) to get the cast signals (0x1000000F codes 1-5) the skill scripts wait for; a script's
reaction to a code (a missile, a stop, skill_to_locomotion) goes back to the client as more 0x8D / object messages. So any
lead or lag between the server's graph and the client's graph moves the script's reactions inside the client's clip.

## 2. Generic causes found (and fixed)

### 2.1 The server graph ran 0.13-0.17 s ahead of the client's (C)

`CastWorld.run_scriptlet` fed the BGE when the script ran the scriptlet, but sent the local champion's 0x8D
`champion_scriptlet_delay` (0.13 s) + a scheduler tick later. Every hook therefore came that much early relative to the
client's clip:

| Skill (run 2026-10-29) | Server graph start | Client got the graph event | Script reaction (server) |
|---|---|---|---|
| Grab 12:13:34.537 | hook 1 at .546 | 0x100001E3 at .715 | hook 5 at .717 -> LaunchTetheredMissile: the throw began on the client as the missile left (code 5 is at 0.14 s of the start clip) |
| Scorched Earth 12:16:48.912 | hook 1 at .919 | 49.094 | crater 0x40000487 spawned at 49.088 (before the client began the slam); code 2 at 49.095 -> stop of Vfx_Atm_Glt_Smash_Active 0x100008AB at 49.097, 3 ms after its start reached the client |
| Meltdown 12:22:26.275 | hook 1 at .282 | 26.414 | missile 0x40000484 created at 26.406 (before Meltdown_Start); code 2 at 26.458 -> skill_to_locomotion sent 26.596 |
| Basic attack (any) | hook 1 | +0.13-0.17 s | code 5 / 3 (shot, hit) 0.13 s before the client's swing reached them |

Bots have no deferral (their 0x8D goes at once), so the lead was the local champion's only, which is the one the tester
watches. **Fix:** `[ics] graph_feed_at_send` (true): the local champion's graph is fed when its 0x8D is sent; the
cast-start grace (`graph_start_grace`) waits while such a feed is pending (`graph_feed_pending` on the entity) instead of
falling back to the timed signals. Keys with `scriptlet_delays` / `scriptlet_chained` are still fed at once (they are not
graph keys).

### 2.2 Cosmetic tails were cut by the script's own skill_to_locomotion (C)

Many skill states end with `skill_to_cosmetic` a fraction of a second into their clip and hand the rest of the same clip
to a `<skill>_Cosmetic` state (AGL: Meltdown 111 -> 120 at 0.17 s of a 1.0 s clip, Scorched Earth 113 -> 119 at 0.15 s).
That hand-over is the skill state's exit, so the script gets code 2 there, and several scripts raise
`skill_to_locomotion` (0x10000002) in their code-2 state (Meltdown 0x340002B4 S2, Grab 0x340002B5 S2, ...). The
cosmetic state's only exit is `skill_to_locomotion` (no interval flags in any graph: all out-transition flags are 0, 16 or
32, C census), so the event ends the tail on the client at once: Meltdown's throw ran 0.18 s of its 1.0 s on the client.
ics had a guard for this since 2026-10-25 (`keep_cosmetic_tail`, champion-animation-matrix.md cause 2), but it is armed
only by the timed cast path (`_graph_cast` sets `cosmetic_until`); with `graph_runtime` on (fase3-if) nothing armed it.
**Fix:** `[ics] graph_cosmetic_tail` (true): the BGE marks a `_Cosmetic` state entered by `skill_to_cosmetic` (for its
clip length - start + its end-relative exit trigger when the clip length is in the data, else `graph_cosmetic_hold`
0.8 s), and `RaiseGraphEvent(skill_to_locomotion)` is dropped while that tail plays (logged
"skill_to_locomotion kept off: the cosmetic tail plays"). The tail still ends on its own (clip trigger) or by moving
(onCosmeticEarlyOut on the client; the BGE's Lua early-out on the server). P that the original did not cut it: the
original video shows Meltdown's full raise-and-throw (59.75-60.75 s) and the tail is the throw's follow-through.

### 2.3 Scriptlet stops overtook their starts (C)

`StopScriptletKey` (0x10000012) went out at once (`World.signal_scriptlet`) while the start of the same key had been
deferred `champion_scriptlet_delay`: Scorched Earth's smash VFX 0x100008AB was started at 49.095 and stopped at 49.097.
**Fix:** `[ics] champion_stop_deferred` (true): the local champion's stops wait the same delay, so they keep their order
behind the starts.

### 2.4 Checked and not a cause here

* Full object bundles ("stops to cast", "faces the target", 1.5 KB) go before the graph event; object-update-bundles.md
  3 (C) says a bundle re-creates nothing and drops no run. No clip restart was seen after them in the frames.
* Basic attacks: Basic_Attack -> Basic_Attack_Cosmetic at the hit (0.24 s / attack speed); the script's
  `_Combat_GoToLocomotion` 0x100002FD runs only when the attack order ended (target dead or 0x10000009), as in the data.
* Clip durations: 1 357 of 3 720 clips have end-relative triggers and only 228 a known length (enforced duration). The
  character clip table (`u32 n | n x 0x1A DID | ... | n durations`, uesrv/havok_anim.clip_table) has one entry per clip
  generator, and the first 6 of Gaslight Batman's 81 match his graph's generators in object order (C), but the order
  diverges after (59 vs 41 for the car run clips; offset, DFS and BFS orders give the same 26 conflicts), so names still
  cannot be joined to lengths without `diag --anims` (O). AGL's skill states use absolute triggers, so his casts are not
  affected; cosmetic tails and fidgets are.

## 3. AGL per skill: original vs ours (fase3-ig run) and after fase3-ih

| Skill | Original (video) | Ours (12:12-12:24 run) | After fase3-ih |
|---|---|---|---|
| Basic attack | swing, green streak, punch lands, follow-through | swing plays; shot / hit 0.13 s before the swing reached them (2.1) | hit at the clip's own time (C by construction; to see in game) |
| Q Grab | 31.5-31.6 wind-up with the construct hand at the arm; 31.6-31.9 the hand and a stretched arm fly to the target; 32.0-32.4 target dragged back along the arm; ~1.0 s | 237.13 start clip, 237.4-238.13 the grab loop pose held with the construct hand **still at AGL**; the missile shows only as faint streaks; 238.2 end on skill_to_locomotion when the hand turned back | throw / missile in step (2.1). **Still missing: the hand leaving AGL as the projectile and the arm beam** (O, 4.1) |
| W Scorched Earth | 42-45 s: slam, crater, second blast | slam began after the crater appeared; the smash VFX stopped 2 ms after it started (2.1, 2.3) | crater at the slam's hook 3 (0.11 s); smash VFX plays to code 2 (0.15 s) as the data says; cosmetic tail kept |
| E Shards of Will | 50.75 shards burst out, 51.0-53.5 they close into a large rotating sphere that stays | 533.0 burst, 533.5 a small cluster at AGL, no sphere after 534.5 | unchanged (O, 4.2) |
| R Meltdown | 59.75-60.0 shard raised overhead (wind-up), 60.25-60.75 it flies, 61.0 impact (crystal cluster + ring), pulses about every 0.75-1 s with the ring for 5+ s | missile created before the client's Meltdown_Start, throw cut at 0.18 s (2.1, 2.2); impact flash 769.33; first pulse 0.1 s after the hit, then the status jumped to a minion and left Harley 0.14 s after the hit | wind-up then missile, full throw (2.1, 2.2). Pulses / jump / slow unchanged (4.3) |
| Passive Radiation Sickness | rads aura, slow at 4 stacks | slow modifier 0x100005E4 -0.4 sent on Harley at 12:22:43 / 12:23:29 (C) | unchanged |
| Recall / Super Strength | - | recall 12:18:01; lifts 12:14:52 / 12:16:00 | not in my area (liftables agent) |

## 4. Open items

### 4.1 Q: the hand as the projectile (O)
Frames: in the original the construct hand leaves AGL; in ours it stays at AGL for the whole flight and the missile
object 0x40000485 shows only its streak. The missile's tables (world state 0x2E000C4C, table 0x1D000456) hold
Vfx_Active 0x100000EB, Vfx_Event1 0x10000076, Vfx_Streak_Right 0x10000617 and _HFSM_DestroyEntityAction 0x100001E0
(C). Vfx_Active on AGL's own table raises graph events 0x1000001E / 0x1000013D (C, skill_graphs.json); on the missile it
is the beam (agl-grab-arm.md 3). P: the flying hand is the missile object's model, which needs its world state's graph
templates (property 0x5B5, as carrier props do, CLAUDE.md) that `dress_spawned` does not send (only 0x7D2). Check with
`python tools\diag.py --brazo` during one Grab, then try 0x5B5 on spawned missiles.

### 4.2 E: the sphere (O)
Traffic 12:18:30.25: ShardsofWill_Start (graph) .394, Shards_Start 0x1000088C .441, Shards_Active 0x10000886 .583, then
0x10000886 again at .710, .974, 1.069 ("again after its bundle" / after another scriptlet) and every 1 s
(`scriptlet_restart`). object-update-bundles.md 3 (C): a re-sent key starts a second run beside the first, so each
re-send restarts the sphere's burst; the frames show only bursts and no settled sphere. The 2026-10-25 diag (agl-e-r.md)
saw Active's run end at once on the client. P: the stack of workarounds (`scriptlet_delays`, `scriptlet_restart`,
`resend_looping_after_bundle`, `resend_looping_after_scriptlet`) now hides the real cause; next step: one run with all
four off and `diag.py --escudo`, to see whether the run ends by itself or by our messages.

### 4.3 R: pulses, jump, slow (C cause, design)
The target status 0x340002BF pulses at once (its PulseTimer starts unset = expired, script_runtime timers, C) and, when
the target already has MaxRads - 1 Radiation stacks, jumps to the best other enemy in JumpRange and removes itself
(the 12:22:26 cast: hit .688, pulse .797, jump missile .805, status removed .830). The slow is the passive's Sickness at 4
pulses / stacks (meltdown-moving-target.md 1.5), so a status that jumps after one pulse never slows. The original video
shows the first pulse about 1 s after the hit (61.0 -> ~62.0) and a single target (no jump). P: the first pulse waits
PulseDuration in the original (timer started at the status' start); not changed here (the "unset = expired" rule is C
from the client VM). To decide with `diag.py --reward` / a status trace of one Meltdown.

### 4.4 Other
* Grab during the countdown (12:13:34): the missile was created 0.36 s after its code 5 with no log line between (a server
  stall, P); not seen after the start.
* champion_check's EARLY2 rule now allows the feed lag (a code 2 within champion_scriptlet_delay + 0.06 s after the script's
  own raise).

## 5. Validation

`tools/champion_check.py --vs-champion --window 5`, fase3-ig keys vs fase3-ih keys (scratch `cc_before.json` /
`cc_after3.json`): every hook moves 0.15 s later for the local champion (the feed lag); sequence verdicts OK 182 -> 183,
EARLY2 1 -> 0, SIG 14 = 14, HANG 1 = 1; no slot loses its effect. Hit-count changes (Deathstroke Q, Flash R, Stargirl Q,
Wonder Woman E, Zatanna E) are pulses moved across the 5 s window edge or minions standing elsewhere when the cast comes
0.15 s later (Zatanna / Stargirl equal with --window 6; Wonder Woman E's trace has the same script path). The cosmetic-tail
drop fires in two headless slots: AGL R (Meltdown) and Nightwing E (one graph-event 0x8D fewer each). The drop is armed
before the code-2 delivery (the hook is delivered inside the transition). Suites: test_match 327/327, test_meltdown 50/50
(walking-away Grab bot from 4 m: from 5 m the later hand reaches the 7 m range end after it), test_graph 34, test_scriptvm
78, test_ics 40, test_catalog OK.
