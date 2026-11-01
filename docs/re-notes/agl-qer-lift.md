# Atomic Green Lantern Q / E / R and the Super Strength lift (2026-10-29, fase3-ii)

Tester report 2026-10-29 14:40 (run 14:19-14:34, Crime Alley v AI, AGL vs the bot Nightwing; `logs/server.log`,
`logs/traffic.log`, `logs/diag.log` with `--brazo`): "AGL's animations are still not solved; the lift of vehicles and
objects still looks odd, as if some animations were skipped". Sources: those logs, the original AGL video
(`agl_video.mp4`: Q 31.2-32.6 s, E 50.5-58 s, R 60.5-66.4 s) and our recording `2026-10-29 12-09-37.mp4` (frames with
cv2), pack 0xA0000150 (scriptlet bodies), `data/skill_graphs.json`, the script trees (`python -m ics.script_model`),
`InfiniteCrisis.exe` (capstone, VA, base 0x400000). Tags: **C** confirmed (log / data / code read), **P** probable,
**O** open. No game text or images are copied.

## 1. Q Grab: the hand and the stretched arm

### 1.1 What the diag of the 14:19 run says (C)

- `tracer.py` logs at most 100 hits per breakpoint. The per-frame beam checks (0x749800 / 0x749960 / 0x74CC05) used
  all 100 at **14:20:01-02** on the map's own beams (targets 0x02..0115 / 0x02..0116, both ends resolved, drawn), and
  the failure counter 0x74CC0C used its 100 at **14:20:06-10** on the intro cinematic's beams (0x20F5 cinematic at
  14:20:05.958; two beams to AGL at 14:20:06 / 07). The same happened in the 12:41 session.
- So **no Grab beam was ever seen by the per-frame checks**: the diag cannot tell which check fails. What it does show:
  every Grab (14:20:38, 14:21:04, 14:21:58, ...) built its type-2 beam with **target = AGL** (0x67338E, two starts
  per Grab, scale mode 4): the binding to 0x100004E2 works.
- Fix of the diag (`tools/diag.py --arm` / `--brazo`, `tools/tracer.py`): the per-frame checks are grouped per beam
  (entry 0x749960 with ecx = beam, key = source IID > target IID; steps entity / model / active / attach / SRC / DST;
  end DRAWN 0x74CC05 or FAILED 0x74CC0C). One line per beam whenever its chain changes, no budget. New `z:` (non-zero)
  and `b:` (low byte) field forms in `tracer.ev`.

### 1.2 The 0x5B5 hypothesis: refuted (C data)

The missile's world state `0x2E000C4C` (pack 0xA0000150 @0x21FE68, `did | 7 | 0x2D000A33 | 0 | 7`) has seven
properties: 0x6B4 = 1.25 (scale), 0x7D2 = [0x1D0003D2], 0x4FD, 0x7EB = 7, 0x2A4, 0x50F = 7 (creation type), **0x357 =
model 0x17000F70**. There is **no 0x5B5** in it (nor in the template 0x49000485, whose 0x510 = 0x2E000C4C and 0x7D2 =
[0x1D000456]). The missile is created as its own class 0x40000485 (descriptor world state 0 = the template's), so the
client builds it from these records itself; 0x5B5 was needed only by props built on a carrier class. Nothing to send.

Same model 0x17000F70 as the Shards shell 0x2E000C89 (which has graph 0x5B5 = 0x1C000083): the missile's own model is
the construct model the hand would be drawn with (P).

### 1.3 Frames (C video, P reading)

- Original 31.6-32.2 s: a long streak of green particles from AGL's arm to the target with the construct hand at its
  head (the type-2 beam's particle 0x18000752 line + the missile's model), then dragged back.
- Ours (12:13:34, video 237.0-238.4): AGL's construct arm extends, **the hand stays on it** for the whole flight, and only
  a few faint green dots travel along the line (237.7-237.9 s).
- Grab_Start 0x10000899 (C body @0x29C80): type 0x23 group at 0.24 s with particle 0x18000754, type 0x17 run of
  **ArmFade_RemoveHand 0x10000911** (type 8 fade of the construct hand), type 0x17 run of Grab_Active. Grab_Stop
  0x10000890: at 0.06 s run ArmFade_AddHand 0x1000093D + particle 0x18000755, stop of Grab_Active (0x163 = 1).
  The hand staying in our frames means RemoveHand did not take effect, or the hand seen is the arm's own mesh (O).

### 1.4 Status

No server change for the arm in this build (nothing in the data is missing from what the server sends, C). Open (O):
which per-frame check fails for the missile end (render model present / active / attach 0x10000039) and whether
RemoveHand runs. Next diag: `python tools\diag.py --brazo`, one or two Grabs; the lines `ARM: <missile IID> <AGL IID>:
beam > entity(ok=1) > model(ok=..) > active(ok=..) > attach(ok=..) > SRC(ok=..) > ...  > DRAWN / FAILED` answer it.
Side facts (C): ics' own table parser returns None for AGL's main tables 0x1D0003CE / 0x1D0003CF / 0x1D0003D0 /
0x1D0005FC (their header lists 6 base tables 0x1D0003CD / D1 / D3 / D6 / D7 / D9), so `Data.scriptlets` misses the Grab
and Shards keys (only server-side filtering; champions are not filtered); the first Grab's missile was created 0.26 s
after its code 5 (server stall, once).

## 2. E Shards of Will: one run that stays

### 2.1 What we sent (C, traffic 14:22:44-49)

Shards_Start 0x1000088C at .168, Shards_Active 0x10000886 at .325, then 0x886 again at .448, 45.480, 46.135, 46.501,
47.868 ("again after its bundle": `resend_looping_after_bundle` / `_after_scriptlet` / `scriptlet_restart`), Stop
0x1000088B at 49.221. Later casts: up to 16 re-sends in 5 s. **Every re-send carried a new run number.**

### 2.2 Why that restarts the sphere (C rule, P look)

The 0x8D entry handler 0x6279D0 (client-scriptlets-graphs.md 1.2 step 4, C): a run number already alive on the object
makes the entry a **signal** to that run (no restart); an unknown number creates a **new run**. Shards_Active's run
spawns the shell 0x2E000C89 (type 0x0C, keep) whose own scriptlets play the burst-out and the closing into the sphere
(original 51.0-53.5 s: shards burst, then gather into a dense sphere that stays, also while AGL fights 54-57 s). Each
new run = a new burst: the sphere never reached its settled look (our 12:18:31 frames: bursts only).

What ended the single run in 2026-10-25 / 10-28 (why the workarounds were added) is still **O**: the 12:27 traffic tied
it to the basic attack's Combat_Basic_Attack 0x10000128 (AGL's body @0x1F724: graph event 0x1000006E + a 0x22
container on 0x100000CE; no stop of 0x886). Vfx_Stop 0x10000130 (@0x1D334) does stop Shards_Active, Grab_Active,
Rads_Active, Vfx_Active ..., but the server did not send it during E (C).

### 2.3 Fix

`[ics] looping_resend_same_run` (true): every re-send of a looping key (`scriptlet_restart`, `resend_looping_after_bundle`,
`resend_looping_after_scriptlet`, the camps' phase-in) reuses the key's last run number (`World.looping_run`). While the
client's run lives it is only a signal (nothing visible), so the sphere plays its burst and close once and stays; if
something on the client ends the run, the next re-send starts it again (self-healing instead of a restart every
0.35-1 s). Shards_Stop still ends it (type 0x17 stop with 0x163 = 1 on the key). false = a new number per re-send.

## 3. R Meltdown: first pulse, detonation, slow

### 3.1 One cast traced (C, 14:28:20-24)

hook 1 .639, missile 0x40000484 .756, hit on Nightwing 21.105 (status 0x340002BF S1, icon 0x480007B1, Meltdown_Tgt_Active
0x10000889), **first pulse 21.209** (0.1 s after the hit: PulseTimer never started = expired), the pulse damage gave
Nightwing (who had Rads stack 3) Radiation Sickness 0x480007BC at 21.230 (slow -0.4 sent 21.233), so the status jumped
at the same pulse: Meltdown_Tgt_Active stopped 21.239, i.e. **the detonation lived 0.13 s** on the target; jump missiles
to minions at 21.212 / 21.508, each pulsing at once again.

### 3.2 The original (C video, P timing)

Impact 60.75-61.0 s (crystal cluster); crystal eruptions at ~62.0, 63.0, 64.0, 65.0, 66.0 s on the same target: five
pulses about 1 s apart, **the first about 1 s after the impact**.

### 3.3 Fixes

- `[ics] status_timer_first_wait` (["0x340002BF"]): in these status scripts a timer the update chain tests before it was
  ever started starts at that first test with the duration of the script's own StartTimer of the same variable
  (Meltdown: PulseTimer = PulseDuration). The general "unset timer = expired" rule (C, client VM) stays for every other
  script. Effect: 5 pulses (EffectDuration / PulseDuration), the first ~1.1 s after the hit (headless: hit <= 1.5 s,
  pulses 2.45, 3.55, ...), Meltdown_Tgt_Active stays at least one PulseDuration on each target before a jump.
- `[ics] slow_motion_update` (true): a move-speed change on a walking unit / bot sends its movement state with the new
  speed at once (`CastWorld.on_attribute`); before, the walking bot kept the speed of its last state until its next
  throttled update. The slow itself (Sickness -> 0x34000134 -> 0x100005E4 -0.4) was already applied and sent (C).
- Design (C data, unchanged): the status jumps when its target has Sickness or MaxRadStacks - 1 stacks; on a target
  already stacked by basic attacks the jump comes at the first pulse (now ~1 s after the hit).

## 4. Super Strength lift (rocks and vehicles)

### 4.1 Graph (C, AGL's SM_SuperStrength_Rubble / _Car)

Rubble: wildcard SuperStrength_Rubble_Pickup -> Rubble_Pickup (clip at speed 1.25: grab hook 3 at 0.216 s, Hold at
0.296 s) -> Rubble_Hold (loop) -> Rubble_Throw (release code 5 at 0.26 s, end 0.28 s, Rubble_End at clip end - 0.2).
Car: InitCarPickup -> Car_Pickup_Start; CarPickup -> Car_Pickup (from frame 0.45 at speed 0.8, hook 3, Hold); PickupCar in
Hold -> Car_Catch; ThrowCar -> Car_Throw (release 0.2, end 0.22). ics' KINDS / `_graph_times` match these (C).

### 4.2 Cause found (C traffic, C client rule)

Lift 14:21:34.983 "stops to cast", **34.997 "faces rock 1" bundle (a turn) and 34.998 the pickup 0x8D**; throw 39.093
"throws rock 1" bundle (a turn toward the throw point) and **39.096 the throw 0x8D**. The client applies a movement state
0.1 s after its stamp (0x60B5F0) but an 0x8D at once (object-update-bundles.md 6.1, C), and a turn step cuts a skill clip
(champion-animation-matrix.md 1, C). So the turn landed 0.1 s into the 0.30 s pickup clip and 0.1 s into the throw clip
(the release is at 0.26 s): a third of each was replaced by the turn. Skill casts avoid this with
`champion_scriptlet_delay`; the lift path (World.scriptlet) sent its keys in the same millisecond.

### 4.3 Fix

`[ics] liftable_face_lead` (0.13 s): the pickup key and its whole timeline (grab, toss, catch, hold) and the throw key
with its release / end wait this long after the facing bundle; the carry stops at the throw press (no second throw). 0 =
the same tick as before. The rock still goes to the hold point at the grab frame (0.216 s) in one state: the original
attaches it to the hand (0x34000177 S3 AttachEntity at 0x100000B0, offset (0, 1.4, 1.4)); the client attach did not move
it in game (2026-10-29 10:53), so the raise between grab and Hold (0.08 s) is not followed (O, minor).

## 5. Validation

`tests/test_meltdown.py` 50/50 (pulse count expectation 6 -> 5 with `status_timer_first_wait`), `tests/test_graph.py`
34/34, `tests/test_ics.py` 40/40 (ICS_TEST_PORT=20700), `tests/test_match.py` (see CHANGELOG fase3-ii),
`tools/champion_check.py --only 0x4000047D --vs-champion --window 5`: DMG on all five slots, sequences OK.

## 6. What the tester should see / open

- E: one burst that closes into the sphere and stays until the shield ends, also while attacking (if it still vanishes,
  run `python tools\diag.py --escudo` during E while attacking: the 0x666B40 END line names what ended it).
- R: the shard lands, the first eruption ~1 s later, then one per second; a stacked target is left after its first
  eruption; a walking target slows at once when Sickness comes.
- Lift / throw: AGL turns first, then plays the whole pickup (bend, grab, raise) and the whole throw.
- Q: unchanged; needs `python tools\diag.py --brazo` (section 1.4).
