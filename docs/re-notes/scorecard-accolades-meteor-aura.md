# Score screen rewards panel (the Accolades tab), the meteorite's aura (2026-10-29, tester report 23:03)

Tester report 2026-10-29 23:03 (run 22:36-23:03, build fase3-io; the first match, Crime Alley v AI, ended by a core
kill at 22:51:45 and the score screen showed; `server.log`, `traffic.log`; screenshots 81 = our score screen, 79 =
the original's, 73 = an original meteorite, 83 = ours). Tags: **C** confirmed (data words, decompiled exe, Flash AS2),
**P** probable, **O** open. Exe = Ghidra decompile `re-work/decomp` (base 0x400000); Flash =
`re-work/ui-as2/c_a00000d0_02189b08`; the scorecard SWF = `old_files/tools/gfx/02767b98.gfx`.

## 1. "The rewards panel does not appear in the scorecard section"

### 1.1 Which tab is which (C)
The tab buttons of sprite 112 `Scorecard` (PlaceObject2 names and x, parsed from the gfx):

| depth | instance | x | label token | label (screenshot 81) |
|---|---|---|---|---|
| 369 | `m_btnTabAccolades` | 11.75 | `#01631949` | Summary |
| 368 | `m_btnTabSummary` | 158.75 | `#07AA4A04` | Scorecard |
| 367 | `m_btnTabStats` | 306.2 | `#01D14993` | Stats |

`SummaryTab` (sprite 99) holds only the two `TeamContainer`s: in this client the rewards panel (Victory / duration,
Protector XP, Merits, Champion XP) is **the first tab, labelled "Summary"** (`ScorecardAccolades`), never beside the
table. Screenshot 79 is another client build (two tabs Summary / Stats, an X button, the panel at the side); the
server cannot change this client's layout (it would take a SWF patch). Screenshot 81 has the "Scorecard" tab
selected (prev and next arrows both shown = tab index 1).

### 1.2 Which tab opens first (C)
The UI state machine is the 0x34 record **`0x34000000`** (pack `0xA0000037`; `old_files/tools/ui_sm.hkx` is a carve of
its strings), decoded by `tools/script_decoder.py` (`python -m ics.script_model 0x34000000`). Graph S16 (entered when
NextWrapperScreen == CONST_ScreenScorecard): S0 enter = event 100 LoadScorecardScreen + NextScorecardTab =
CONST_Tab_Scorecard_Accolades; T3 S0 -> S1 on 37 ScorecardLoadComplete (Flash sends it at the end of
`Scorecard.OnAllDataRecvd`); S1 -> S6 (event 106 LoadScorecard_Accolades) when the tab variable is Accolades. So the
client opens the "Summary" (Accolades) tab by itself once all scorecard data are in.

### 1.3 Why that tab stays empty (C Flash, P that it is what the tester saw)
- `ScorecardAccolades.show(true)` -> `Animate()` -> `AnimateScorecardAccolades()`: every display is made visible with
  **alpha 0**, then `m_adAccolades.Animate()`. The rest is a chain: accolades COMPLETE -> Merits fade in -> champion
  bar -> (ribbon queue done) -> protector bar -> map (Victory, duration).
- `AccoladesDisplay.Animate()` does nothing until it has `m_sdData`, and it gets it only (a) at load if
  `ScorecardManager.HasAllScorecardData()` or (b) on **ACCOLADES_RECVD**; it never listens to ALL_DATA_RECVD.
- `ScorecardManager.RecvNotice_SendAccountEndOfMatchAccoladesEarned` dispatches ACCOLADES_RECVD only when
  `m_bAllDataReceived` is already true after its own check, i.e. when the accolades notice is the **last** piece.
- The manager is created at `Scorecard.OnLoadComplete` (first `ScorecardManager.instance`), then
  `ScorecardManager.Init()` asks in this order: post-match scorecard, currency balance, currency changes, soft
  currency, character level, account level, **accolades**, header (0x2190 data) **last**. ics sends 0x2188 at the match
  end, before the scorecard exists, so the client answers the request from its cache before the header: no
  ACCOLADES_RECVD, the chain stops at its first step, every panel part stays at alpha 0 (only the background art).
  The table tab is filled by ALL_DATA_RECVD (as in 81).
- Esc on that tab (`WrapperMain` -> `ScorecardManager.KillAnimations` -> KILL_ANIMATION -> `draw()`) would show the
  parts at alpha 100: a quick in-game check.

Traffic 22:51:49.877-.895: 0x1000000E, 0x2075, 0x214B, 0x2045, 0x2120, 0x2190, 0x2081, 0x2080, 0x20B9, 0x2104,
**0x2188**, 0x2090, 0x219F, 0x219E, all before the client left the world (0x12D 22:51:50.046); the scorecard screen
started loading at 22:51:50.629 (its AskForRibbons = **0x212E**, `ScreenSettings` SCORECARD `m_bAskForRibbons`) and ran
its Init at ~22:51:50.80 (the `User.HasSeenPostEncounterVideo` preference is set by `0xA724A0`, called first by the
end-of-match stats sender `0xA795E0`, which also calls Flash `UI_SendEndOfMatchStats` `0x8E3AC0`).

### 1.4 Fix
`Session.ev_ask_achievement_banners`: after a match end, the scorecard's 0x212E schedules the same 0x2188 again
`[ics] scorecard_accolades_resend` (1.5) s later; `[ics] scorecard_accolades_resend_fallback` (8.0) s after the end
messages if no 0x212E came. Arriving after Init, the notice is delivered live with every other piece in, so the
manager raises ACCOLADES_RECVD and the chain runs (P: whether the client's request handler answered with defaults
first does not matter; either way the late copy sets the data and raises the event).

Other facts read on the way (C):
- 0x219E's handler `0xA37DC0` always sets the show-banner flag (+0x12 = 1): the rank ribbon shows when the 0x2045
  "ranked" flag (`0x8E3AC0`'s last argument, encounter manager +0x8E bit 0) is set; our queue key 0x200000 (blind) is
  not ranked.
- An empty `TimelineLite` completes at once (`renderTime`, duration 0, `_rawPrevTime` -1): no accolades is not a block.
- `tools/diag.py --scorecard` (`--puntuacion`): breakpoints on the Flash natives (RVA) `0x521BE0`
  UIStateMachineEvent (106 / 72 / 91 / 100), `0x4E3AC0` EndOfMatchStats (duration, encounter, ranked), `0x500350`
  header, `0x4908D0` account level, `0x48FF50` champion level, `0x490CE0` Merits, `0x4CEE70` accolades: their order shows
  whether the accolades now come last.

O: that the empty Accolades tab is what the tester saw (81 shows the other tab; nothing in the logs shows which tab
was open). If the panel still does not show: a `diag --scorecard` run, and Esc on the "Summary" tab.

## 2. "The meteorites' red aura is not the correct one" (73 vs 83)

### 2.1 What each picture shows (G, screenshots)
73 (original): the rubble pile with red streaks and, above it, a floating red **halo** with a pale centre. 83 (ours,
fase3-io): the round rock sitting on its base, thin red lines on it (the team-colour tint), red veins in the ground
cracks (the base).

### 2.2 The tint (C data)
`_Entity_OnSetClientRelationship` (table `0x1D000385`) sets appearance set `0x19000A61` group `0x10000004`; for side 5
(`0x1000011E`) the group's entries point at parameter sets such as `0x16000E7D` (param 0x7D0 = RGBA 1, 0, 0, 0.75) and
`0x16000E80` (param 0x7F3 = the same red): it recolours the rock's team-colour material parameters, which is what draws
the red lines in 83. Whether the original's halo is this parameter with more glow on its machine is O.

### 2.3 The "orb children" are not the meteorite's (C, corrects liftable-aura-lift-throw-break.md 1.1)
- `0x2E000D13` / `0x2E000D14` follow the Rock template `0x490005C9` in all four packs that carry it (an `0x8B` child
  entry right after its 111 properties), which is why fase3-io took them for its children.
- `0x2E000D14`'s `.entity 0x2D000ADE` has the bounding box (-3.42, -3.70, 0) .. (3.43, 3.28, 0.09): the 7 m flat plate
  of the Power Relay / cannon `0x2E000D12` (`0x2D000ADC`, deep-scan-maps.md); `0x2D000ADD` (D13) is a point.
- The relay base table `0x1D0004A1` (its body follows the placed record @`0x7D950C` in pack `0xA0000162`) spawns both
  with action **type 0xC** (spawn a world state as a client object, then run a key on it: `0xC 0x2E000D13 ...
  Vfx_Startup` @`0x7DA410`, `0x2E000D14` @`0x7DA6E4`), on its capture keys (Vfx_CapturePoint_* nearby). P: that the
  span after the placed record is that table (the record list places it; the table parser did not split it).
- Their table `0x1D00038B` is the team **hologram** table (turret heads, pedestals): Vfx_Startup by side,
  Vfx_Active_Red / _Purple / _Blue on appearance set `0x19001299` group `0x10000002`.
- No key of the rock's tables (class `0x1D0004FB`, world state `0x1D000385`) or of its scripts (`0x34000167`,
  `0x34000347`, Super Strength `0x34000164` / `0x34000177` / `0x34000161`) plays a particle, an overlay with a material
  or a 0x2E parameter on the lying rock: `Vfx_Active` is a type-8 overlay without material (a fade), `Vfx_PickUp` runs
  Vfx_Active. The base `0x1D0004AA` has the particle chain State1 `0x18000A31` -> State2 `0x18000A3C` -> State3
  `0x18000A3D` -> Vfx_Stop `0x18000A3E` (each stops the previous one).
- Action 0xC also explains other client-made objects: the superpad `0x2E001314` (table `0x1D0008FA`) spawns
  `0x2E00137F` with Vfx_Active_Pad_*, and has the rubble `0x2E000D22` as its own `0x8B` child.

### 2.4 What ships (fase3-ip)
- The tint stays (`[ics] liftable_aura` rock colour 5): it is the only red the rock's own data can show, and the
  original's rubble has red streaks too.
- `[ics] liftable_aura_probe` (default []): logged candidate steps on each lying rock, so one test run with a
  screenshot names the right look. Steps: `{"at": s after the aura is on, "kind": "rock", "target": "object" | "base",
  "key": name, "force": true (send a key the target's tables lack), "colour": n}`; each sent step is in `traffic.log`
  as `aura probe <i>: ...`. A ready probe for `config.toml`:

```toml
[ics]
liftable_aura_probe = [
  {at = 20.0, kind = "rock", colour = 0},
  {at = 30.0, kind = "rock", key = "Vfx_Active_Red", force = true},
  {at = 40.0, kind = "rock", colour = 5},
  {at = 50.0, kind = "rock", target = "base", key = "Vfx_Active_State2"},
  {at = 60.0, kind = "rock", target = "base", key = "Vfx_Active_State3"},
  {at = 70.0, kind = "rock", colour = 6},
  {at = 80.0, kind = "rock", colour = 3},
  {at = 90.0, kind = "rock", colour = 5},
]
```

(0 = no tint, the forced hologram key tests whether the rock's render takes a child table's key, the base's later
states, then other side colours.) O: the halo itself; next step after the probe: `diag` on the type-8 overlay /
0x2E parameter executes while the original's look is known from a probe step.

## 3. Checks
`tests/test_session_flow.py` +2 (0x212E -> the same 0x2188 again after `scorecard_accolades_resend`, once; a later
0x212E sends none); `tests/test_match.py` `aura_probe` (2: the steps on a lying rock, an unforced key outside its
tables not sent, [] = nothing).
