# Atomic Green Lantern: E (Shards of Will sphere) and R (Meltdown) (2026-10-25)

Tester session 2026-10-25 19:27-19:45 (`logs/server.log`, `logs/traffic.log`), AGL `0x4000047D`, match entered
19:27:45 (0x20AF packs `0xA00002E5 0xA00002E6 0xA00002E7 0xA0000116 0xA0000073 0xA000022E 0xA0000150 0xA000023E
0xA000023F 0xA0000151`). Exe `InfiniteCrisis.exe` (VA, base 0x400000) read with capstone; packs through
`ics.gamedata`. Tags: **C** confirmed (code / data / log), **P** probable, **G** guess.

Short version:
- **R**: the server's script VM re-enters a graph transition from inside that transition's own exit chain. AGL's
  passive (Rads, `0x340002B3`) then applies 3-4 Rad stacks per hit in the same tick, so every enemy AGL touches gets
  Rads Sickness (`0x480007BC`) at once. Meltdown's status is written to *jump away* from a target that has Sickness,
  so it pulses once and leaves. Fix: a re-entry guard in `Region.leave()` (section 2.4). Verified headless.
- **E**: the data needs nothing from the server beyond Shards_Start; every resource is in the loaded pack. The
  sphere is lost inside the client (spawn / lifetime). Not closable statically: new `diag.py --shards` (section 1.6).

## 1. E "Shards of Will" (slot 3, script 0x340002B1)

### 1.1 What the server sends (C, traffic 19:31:55)
- 55.254 `0x20C8` status icon `0x480007B7` on AGL; 55.255 vitals; 55.370 `0x8D 0x100001E3` (graph event 0x1000032C).
- 55.387 `0x8D 0x1000088C` Shards_Start with variable table `{0x1000033E = 0.05}` (f32 `3D4CCCCD`).
- 55.405 `0x10000886` Shards_Active dropped ("chained by 0x1000088c", `[ics] scriptlet_chained`).
- 19:32:00.409 `0x8D 0x1000088B` Shards_Stop (status end, 5 s).
- The `0x1000088D` bursts at 19:31:57.236 (x9) and 19:32:01.774 (x9) are **Rads_Stop of the passive**, not E: the
  passive loop of section 2.2 (C). Rads_Stop is one particle (`0x18000750`, pack 0xA0000150 @0x2012C) and stops
  nothing.

The status script `0x340002C3` (shield status `0x480007B5`) runs, in this order: AddTempVital(ShieldAmount),
`RunScriptlet(SELF, 0x10000886, {0x1000033E = ShieldPercentage})`, `RunScriptlet(SELF, 0x1000088C, {same})`,
AddStatusIcon `0x480007B7`; exit: RemoveTempVital, `RunScriptlet 0x1000088B`, RemoveStatusIcon (C, script tree).
ShieldPercentage = (ShieldAmount - BaseShieldAmount) / BaseShieldAmount.

### 1.2 The scriptlets (C data, pack 0xA0000150, table 0x1D0003D7)
Action node layout in the pack: `node id | 0 | 0 | type | fields...`; bools take 4 bytes.

| Scriptlet | Offset | Actions |
|---|---|---|
| Shards_Start `0x1000088C` | 0x35BC8 | (1) **type 0x17 run key `0x10000886`** (0x1BB = 0, 0x20E = 0, 0x163 = 0); (2) type 0x24 switch on `0x1000033E`: particles `0x18000813` (default), `0x18000762` (< 0.125), `0x18000815` (< 0.25), `0x18000814` (< 0.375); (3) type 0x22 group with an enum + sound (type 0x2C); (4) type 9 |
| Shards_Active `0x10000886` | 0x351E8 | (1) type 0x24 switch on `0x1000033E`; each branch = **type 0x0C spawn `0x2E000C89`** (keep 0x67C = 1, child scriptlet 0x325 = State4 / State1 / State2 / State3, scale 1.15 / 1.0 / 1.05 / 1.1, attach 0x160 = `0x10000081`) + type 0x0B (colour `FFE6FFB0`, 4.0, 3.0 ...: a light, P); (2) type 0x22 group + sound |
| Shards_Stop `0x1000088B` | 0x360B0 | (1) **type 0x17 on key `0x10000886` with 0x163 = 1**; ... |

Type 0x17 ("run key") definition: vtable `0x15CF0B0`, execute `0x684D10`, unpack `0x686870`: `+0x38` 0x78B array
(target bindings), `+0x6C` 0x2D0 enum (key), `+0x70` 0x1BB bool, `+0x71` 0x20E bool, `+0x72` 0x163 bool (property
visitor `0x655F30`, C). Instance `0x671A70` (vtable `0x15CFBB0`): start `0x671FA0` runs the key on every target with
`0x588AC0` -> `0x57B9D0` (own entity when no binding; deferred request `0x15CF06C` when the entity is not there
yet); end `0x671CE0` stops the key (`0x57C4B0`) only if `+0x70 && !+0x71`; `0x6832FA` / `0x672204` count the run
as finished at once when `+0x72` is set or `+0x70` is clear (C). Every entry of the generic `Vfx_Stop 0x10000130`
(stop Vfx_Active, Grab_Active, Rads_Active, Shards_Active, State0/1 ...) has 0x163 = 1, Start and the crater's
"run OnExplode" have 0 (C data), so 0x163 = the "stop / signal the running key" form (P). Consequences (P):
Start runs Active and does not wait for it nor stop it when Start ends (0x1BB = 0); Stop ends Active.

So Active is started by Start itself; the server copy of 0x886 is not needed (`scriptlet_chained` is consistent
with the data). The 11:30 test (Start + server Active 0.15 s later, both with the variable) showed no sphere
either (agl-visuals.md 3.1), so the order / the variable table are not the cause (C by two tests).

### 1.3 The shell world state (C data)
`0x2E000C89` (header `did | 7 | 0x2D000A69 | 0 | 7`): 0x7D2 = table `0x1D000418`, 0x7EB = 7, 0x4A8 = 1, 0x2A4 = 1,
0x50F = 3 (creation type), 0x357 model `0x17000F70`, 0x5B5 graph `0x1C000083` (`0x1A00090E`). Table `0x1D000418`
body at pack 0xA0000150 **@0x1E13E8** (keys in the order Fade_In, Fade_Out, State1, State4, State3, State2; the
block at 0x33E30 with particles `0x18000D9x` belongs to another table): Fade_In / Fade_Out = type 8 (0.25 s / 0.35 s
fades); Vfx_Active_StateN = type 1 action on `0x19000BA3` (a variant record: enum `0x10000002` = value N, P
material / crack level) + particle `0x18000761`. Every DID above (`0x2E000C89`, `0x2D000A69`, `0x1D000418`,
`0x17000F70`, `0x1C000083`, `0x1A00090E`, `0x19000BA3`, `0x18000761`) is in **0xA0000150**, which the 0x20AF list
of this match loads, and Start's own particles (same pack, same table) do show: **not a pack problem (C)**.

No server object, property (0x1000033E is a storage-6 variable, not an entity property), temp vital or 0x200F
status copy is read by any of these actions (C data). The client's own status-script path (0x200F / 0x20C8,
client-status-effects.md) is not involved: Active is reached from Start.

### 1.4 Client path of the spawn (C code)
`0x6852B0` (type 0x0C execute): returns when `ws == null DID` (`[0x1B6AB4C]`), or when `byte [ecx+0x124]` (0x67C)
is 0 and the context entity has flag 0x40 (`[[ctx]+0x50]`); else builds a request (vtable `0x15CF8EC`) and calls
`0x683AF0`: owner IID from the context (`+8/+0xC`), owner entity from the world manager `[0x1B67258]` vt+0x58,
then create through vt+0x30 (`[0x1B6AB48]` set) - result in `eax` at `0x683C5A`, pending flag `[esi+0x34]` - or
vt+0x24. With 0x67C set it wraps the request in a persistent instance (`0x655360`, vtable `0x15CEC90`) whose end
(vt[12] = `0x666B40`) destroys the child (`0x65F860`) and releases the request.

### 1.5 Where it can still fail (P, ordered)
1. The Active run ends at once (its last action is instant), its 0x24 container instance ends (`0x530310`), the
   persistent shell instance ends with it (`0x666B40`) and the shell is created and destroyed in the same frame.
   The original server would then have needed to keep Active alive (e.g. a StartScriptlet with a handle) - but the
   data's own Start->Active->Stop pattern suggests the run lives until Stop.
2. The world manager refuses / defers the create (result 0 at `0x683C5A`).
3. The shell is created but not seen (attach point `0x10000081` not on AGL's skeleton, scale) (G).

### 1.6 Diag `python tools\diag.py --shards` (added; alias `--escudo`)
Breakpoints (rva = VA - 0x400000): `0x6279D0` 0x8D started (did), `0x671FA0` 0x17 run (key), `0x671CE0` 0x17 end
(key, reason, flags), `0x6852B0` 0x0C execute (ws, keep byte, ctx flags), `0x683C5A` create result (eax,
pending), `0x655360` persistent instance created, `0x666B40` persistent instance END, `0x65F860` child destroyed.

Tester: open the game, enter a match with AGL, then in a second console `python tools\diag.py --shards`; cast E two
or three times a few seconds apart; Ctrl+C; send `logs\diag.log` + `logs\traffic.log` + `logs\server.log`.

Reading it (per cast, filter `ws=2e000c89`):

| Seen | Meaning | Server fix |
|---|---|---|
| no `0x17 run key 10000886` after `0x8d ... 1000088c` | Start does not reach Active | send Active ourselves: `[ics] scriptlet_chained = {}` |
| `0x0C execute ws=2e000c89` missing after the run | the 0x24 switch picks nothing | send 0x886 with `0x1000033E` = 0.0 and 0.2 to compare |
| create result 0 | world manager refused | look at the owner IID / world (next step) |
| `persistent ... END` within ~0.1 s of the create | cause 1.5.1: Active ends at once | keep Active alive: proposed `[ics] scriptlet_restart = {"0x10000886": 0.5}` (re-send 0x886 with the variable every 0.5 s while the status lives, stopped by 0x88B) or run it as a started scriptlet with a live instance number (the 0x8D form StopScriptletKey uses, `script_nodes.tsv 0x10000012`) |
| created, no END until Stop, still invisible | cause 1.5.3 | then `--visibility` on the shell / attach point |

## 2. R "Meltdown" (slot 4, script 0x340002B4)

### 2.1 The data (C, script trees)
- `0x340002B4`: S1 Cast + FaceTarget + graph event `0x1000032E` + scriptlet `0x10000894` Vfx_Atm_Glt_Meltdown;
  S3 (cast point) StartCooldown, SpendCost, **LaunchMissile `0x40000484`** at the target, PulsesRemaining =
  StartingPulseCount, scriptlet `0x10000AA4` Meltdown_Shard. Graph S2: on `0x100000EE` (missile hit) ApplySkill
  **`0x480007AF`** on the hit target for PulseDuration x PulsesRemaining; on `0x10000006` PulsesRemaining -= 1.
- Missile `0x340002BE`: chases (speed ramps MinSpeed -> MaxSpeed over BoostLifetime), on collision with its target:
  RaiseEvent `0x100000EE` to the shooter's 0x340002B4, hit FX `0x10000223` (record `0x1E000268`),
  `Vfx_OnCollision 0x10000016` with the target in `0x10000030`, then destroys itself.
- Status `0x480007AF` -> script **`0x340002BF`** (the "melting" on the target): icon `0x480007B1`, FX
  `0x10000223`/`0x1E000268`, **StartScriptlet `0x10000889` Vfx_Atm_Glt_Meltdown_Tgt_Active** on the target
  (variable `0x10000402` = EffectSource = AGL, FX `0x1E000266`); NumRemainingPulses = EffectDuration / PulseDuration.
  Every PulseDuration: ApplyDamage on the target, FX `0x1E000267`, FindTargets(PulseRange) + DestructionImpulse +
  ApplyDamage on everyone around; then if pulses remain: UpdateStatusIcon, RadStackCount = stacks of `0x480007B6`
  on the target, and **if the target has Rads Sickness `0x480007BC` or RadStackCount == MaxRadStacks - 1: jump**
  (FindTargets(JumpRange), best target without Sickness, LaunchMissile `0x40000484` to it, RemoveStatus self);
  RaiseEvent `0x10000006` to 0x340002B4. Exit: icon removed, 0x10000889 stopped, final jump.
- The slow is Rads Sickness: `0x480007BC` -> `0x340002C6` (icon `0x480007BE`, `0x10000892`
  Vfx_Atm_Glt_Rads_Tgt_Sickness_Active, DoT, ApplySkill **`0x48000294`** -> `0x34000134`: AddAttributeModifier
  `0x100005E4` (move speed) by SlowAmount, `0x100003CC` Vfx_Status_Slow_Active). ics sends it (`0x20F0 0x100005E4
  op 10 = -0.4` at 19:36:39.881) and slows the server-side movement (`World.on_attribute`).

So in game: a missile flies to the target, sticks (Meltdown_Tgt_Active), and hits it and the units around it
every PulseDuration (hit FX each pulse) while it stays, then hops to another enemy; the passive's Sickness slows.

### 2.2 What ics did (C, logs)
19:36:41.588 status `0x480007B1` + `0x10000889` on Atrocitus; 41.697 the first pulse; 41.737 icon update;
**41.741 jump missile created**; 41.749 icon removed; 41.750 Meltdown_Tgt_Active stopped. One pulse only, because
Atrocitus already had **Sickness since 19:36:39.876** (icon `0x480007BE`, slow `-0.4`).

Why he had it: AGL's E at 39.833 (Shards raises `0x1000001D` per target to the passive) -> in 30 ms Atrocitus got
Rad stacks 1, 2, 3 (`0x1000088E`, `0x1000088F`, `0x10000893` at 39.850-39.866), then Sickness. `server.log`
39.843-39.889: the passive `0x340002B3` repeats `S1 -> S2 (T2)` (graph S2) / `S0 -> S2 (T0)` / `S2 -> S1 (T2)` /
`S1 -> S0 (T3)` (graph S1) five times with no `enter S2` of graph S2 in between; then "slot 5 cooldown 4.0 s" x5
and `0x1000088D` Rads_Stop x9 on the wire. Reproduced headless: `champion_check.py --only 4000047D --trace 0`
gives 12 stack applications for one basic attack.

### 2.3 Cause (C, ics/script_runtime.py)
Passive `0x340002B3` graph S2: state S1 (a nested graph, "charged") -> S2 on T2 (target valid, alive enemy); the
**exit chain of S1** does `RaiseEvent(SELF, Target, 0x1000001D)`, StopScriptlet, `RunScriptlet 0x1000088D`.
`Region.enter()` calls `self.leave()` before it sets `self.state`; the RaiseEvent is delivered synchronously
(`ScriptInstance.event` -> every region), graph S1 handles it (applies a stack), and graph S2 - still in S1, its
transition half done - runs `check(use_event=True)`, where polled T2 still matches -> enters S2 again -> leaves S1
again -> raises again ... until `event_loop_limit` (4 in 20 ms) cuts it. Each pass is a stack; 3 stacks = Sickness.

### 2.4 Fix (verified headless, not in the repo)
`ics/script_runtime.py`, `Region`:
```python
    def leave(self):
        self._leaving = True            # [ics] exit_chain_reentry_guard
        try:
            ...                         # the current body
        finally:
            self._leaving = False

    def check(self, code=None, use_event=False):
        if EXIT_REENTRY_GUARD and getattr(self, "_leaving", False):
            return False                # a transition of this graph is under way: its exit chain's events
        ...                             # do not fire another one
```
Config: `[ics] exit_chain_reentry_guard = true` (default; 2026-10-25 19:36 tester: Meltdown hopped after one hit
because the passive stacked Rads x3 in one tick), set from `ics/server.py` like `event_loop_limit`. With it
(monkeypatched run of `champion_check.py --only 4000047D --trace 0 / 4`): 3 stack applications for the whole basic
attack window (one per hit), no "loop cut", Meltdown stays on its minion target and pulses 3 times (30 each, until
it dies), verdicts unchanged (DMG DMG DMG FX FX). Side effects expected: one `0x1000088D` and one slot-5 cooldown
per passive proc instead of 9 / 5. Run `tests\test_scriptvm.py`, `test_match.py` after the change (other scripts
with RaiseEvent in an exit chain: the guard only blocks the leaving graph itself; its child / sibling graphs still
get the event).

Messages the client must then get per Meltdown (all already produced by the scripts, C): 0x8D `0x10000894` on AGL
+ graph event `0x1000032E`; missile `0x40000484` create (+ `0x100004E2` creator, agl-visuals.md 1.4) and
Vfx_Active; on hit `0x10000016` on the missile, `0x20C8 0x480007B1` + 0x8D `0x10000889` {`0x10000402` = AGL} on
the target; per pulse damage + 0x8D `0x10000223` + `0x20A8` icon update; at the end `0x20E9` + StopScriptletKey
`0x10000889`; Sickness: `0x20C8 0x480007BE`, `0x10000892`, `0x20C8 0x48000536`, `0x20F0 0x100005E4 op 10`,
`0x100003CC`.

## 3. Open
- E: the diag result (1.6). Also the meaning of 0x163 / 0x20E (P from data and the counters at 0x6832FA).
- R: MaxRadStacks (skill stat 12 of R) and whether Meltdown's pulses add Rad stacks (through the passive's
  `0x1000008B` hook) - with the guard the stacks grow one per hit, so Meltdown should stay MaxRadStacks - 1 pulses.
