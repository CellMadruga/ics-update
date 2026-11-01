# The game closing after `diag --layers`; the Power Core Turret as a composite (2026-10-30, tester report 13:00)

Tester runs 12:51-13:00 (server / traffic / diag logs; unhandled empty) and 13:05-13:18 (second run). Screenshots 89 / 91
(ours: next to the blue core only a small translucent white cylinder with the health bar), original frames 66 / 67
(blue, glossy opaque cylinder under a translucent flag hologram, on the platform's pointed prow) and 70 (red,
destroyed: the prow with a red disc in a round socket and two fallen rings), ours 71 (fase3-in) / 82 (fase3-io) / 88
(fase3-ir). Tags: **C** confirmed (logs, code, table words), **P** probable, **G** from the frames, **O** open. Scripts
in the session scratchpad (`pct3/`); nothing of the game copied.

## 1. "The game closed" (C cause in the debugger, C fix by test)

### 1.1 What the logs show
- diag.log: `--ring` attached 12:52:06 (22 breakpoints), ended 12:59:03 (Ctrl+C); `--layers` attached 12:59:08 to the
  same pid (1 breakpoint at `0x6AE5B0`, the fog render, hit every frame on the main thread), all 12 steps, "LAYERS done"
  13:00:18, "===== end" 13:00:42 (Ctrl+C). The second attach worked, so the first diag had detached (C).
- traffic.log: the client's keep-alive every ~10 s, the last at 13:00:38.98; server.log 13:00:46.342 WinError 10054 on
  both connections. The server sent only ordinary minion / script traffic from 13:00:40 on (C): nothing of ours.
- So the game died between 13:00:42 and 13:00:46, right after the diag stopped.

### 1.2 Cause (C, code)
`tools/tracer.py` `run()` called `DebugSetProcessKillOnExit(FALSE)` (so the game is not killed when the debugger ends),
but Ctrl+C raised `KeyboardInterrupt` in Python's main loop. Python checks signals right after a ctypes call returns,
and with a breakpoint hit every frame (two debug events per frame: the int3, then the single step that re-arms it)
`WaitForDebugEvent` almost always returns an event at that moment. The exception left that event **received and never
continued**; the `finally` restored the breakpoint bytes and called `DebugActiveProcessStop`. Windows then completes the
held (and any queued) event without the debugger: the thread gets its int3 (Eip one past the restored byte, i.e. in
the middle of an instruction) or its single step (TF set) as an ordinary exception, the game has no handler, and it
closes (no `UNHANDLED` line: the debugger was gone). The `--ring` stop at 12:59:03 survived by timing (its hot
breakpoints are not hit every frame).

### 1.3 Fix
- Ctrl+C / Ctrl+Break / closing the console go to a `SetConsoleCtrlHandler` routine that only sets `stop_requested`
  (for a close it waits up to 4.5 s for the detach); the loop stops between events, never with one held.
- `detach()`: restores every int3 byte and clears the hardware watchpoints (`disarm`), puts back every byte written
  through `restore_on_detach`, continues a held event safely (`settle`: a thread on one of our int3s gets Eip = the
  breakpoint, TF cleared; a single step is finished without re-arming; the inject cave restores its saved context),
  drains the events already queued for up to 3 s the same way, clears TF on any thread still pending (suspend / set /
  resume), and only then `DebugActiveProcessStop`. An escaping error goes through the same path. "detached: every
  breakpoint byte restored" is logged.
- `diag --layers` / `--nofog` write through `restore_on_detach`: a Ctrl+C in the middle of a step puts the toggle (and
  the fog colour / EnableFog) back.
- `tests/test_tracer_detach.py` (53 checks): a fake kernel32 drives `Tracer.run()`: Ctrl+C on a per-frame breakpoint
  with a second thread queued on it, an error with an event held, a stop while idle, two threads through the
  breakpoint. At `DebugActiveProcessStop`: no event held or queued, byte restored, pokes undone, no TF, no pending step,
  no thread one byte past the int3.
- Second run (13:05-13:18) already used this tracer: two `--layers` diags stopped with Ctrl+C at 13:08:22 and 13:09:42
  ("Ctrl+C: detaching cleanly" / "detached" lines, the next diag attached 2 s later to the same pid) and a third ran to
  "LAYERS done" 13:10:54; the game kept running (C, diag.log; that last one has no end line in the copy).

## 2. The Power Core Turret as a composite (C data, G look, P result)

### 2.1 What each try drew (G, frames; C, traffic)
| build | class / keys | seen |
|---|---|---|
| fase3-in (71) | `0x40000C8F` / `0x2E000AC4`: Vfx_Active, Vfx_AI_Active | translucent blue cylinder + flag hologram, no body |
| fase3-io (82) | + Vfx_Fade_In first | the same ("only the blue transparent effects") |
| fase3-ip..ir (88) | `0x40000C8E` / lane body `0x2E000AA0` + gear plate | solid dark turret body with the ring head; plate rejected |
| fase3-is (89 / 91) | `0x40000C8F`, + Object_Reset last | a white translucent cylinder only, no flag |

`0x2E000AC4` draws nothing of its own (no mesh node, `turret-heads-coredeath.md` 2): three builds on it showed only its
hologram children. The second run (13:05) still ran fase3-is (traffic 13:06:18 `spawn core_turret t1 (0x40000c8f)`).

### 2.2 The data (C, table words)
- `0x1D000374` (AC4's base): Vfx_Active = loop sound + type-0x0C spawn of `0x2E000A9A` (z -0.25, Vfx_Startup);
  Vfx_AI_Active = spawn of `0x2E000AC3` at attach `0x100000FE`, scale 0.9, Vfx_Startup; **Vfx_Stop** = four type-23
  stops (Vfx_AI_Active, Vfx_Targeting, Vfx_Event1, Vfx_Active); **Vfx_Object_Reset** = a timeline of type-23 runs of
  Vfx_Object_Phase0 (`0x100002DB`), Phase1, 2, 3, 4.
- `0x1D000600`: Object_Reset = a type-23 run of Vfx_Object_Reset; Object_PhaseN = run of Vfx_Object_PhaseN.
- `0x1D00060A` (A9A): every Vfx_Object_PhaseN / Reset is one type-46 action `0, 0x7D0, N, 0x10000002, 1, 1.0`
  (N: Phase1 16, 2 18, 3 20, 4 23, 5 26, 6 30, 7 32, 8 4, 9 6, 10 11, 11 12, 12 13, 13 14, 14 15; Reset 2 with -1).
  0x7D0 is the material colour parameter (`camps-colour-bar-positions.md`), group 0x10000002 the hologram colour group:
  P a per-phase parameter change of the hologram. After Object_Reset (Phase0..4) the cylinder was white (89).
- Base `0x1D00038B`: Vfx_Active_Red / _Purple / _Blue = appearance `0x19001299` group 0x10000002 = 0x10000002 /
  0x10000003 / 0x10000001. Nothing in A9A's or AC3's tables makes an opaque surface (O: the original's glossy fill).
- `0x2E000AA0` (lane body, table `0x1D00035D` + base `0x1D000372`): a real mesh (drew solid in 88); its Vfx_AI_Active
  child is the ring head `0x2E000AA8`, its Vfx_Active child `0x2E000A9E`. The red `0x40000C8D` is this body by data.

### 2.3 What changed
- `match_structure_classes` = {"crime_alley": {"core_turret": {"1": "0x40000C8E"}}}: a body that draws, the same as the
  red one.
- `match_structure_scriptlets["core_turret"]` = ["Vfx_Active"]: no Vfx_AI_Active (no lane ring head), no Object_Reset,
  no Vfx_Fade_In.
- `match_turret_heads["core_turret"]` = `0x2E000AC3`: the flag head made by the server (side, team as change,
  Vfx_Startup; Vfx_Targeting while it has a target), as the lane heads were until fase3-io.
- New `match_structure_parts` = {"core_turret": [[0x2E000A9A, -0.25]]}: the PCT's own cylinder made by the server round
  the body (side, team, Vfx_Startup), removed with the head when the turret falls.
- No base piece: the tester (13:18) says the base is not round; frames 66 / 67 / 70 put it on the platform's pointed
  prow, which is not in this client's data (`turret-head-pct-look.md` 2.2), so no gear plate and no round pedestal.
- Back to fase3-is: `match_structure_classes` {}, `match_structure_parts` {}, no "core_turret" head, core_turret keys
  ["Vfx_Fade_In", "Vfx_Active", "Vfx_AI_Active", "Object_Reset"].

## 3. Open
- P: whether AC3 made by the server sits at the right height (the client child hangs from attach `0x100000FE`; the
  lane head AA8 drew right at the body's spot in the layout and as a server object).
- P: how the blue hologram cylinder over the dark lane body reads against 66 / 67's glossy blue cylinder; if it looks
  wrong, `match_structure_parts` {} leaves body + flag.
- O: the original's opaque fill (no key in the data found), the prow.
