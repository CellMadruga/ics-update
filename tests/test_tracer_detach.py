"""The diag debugger (tools/tracer.py) stops without killing the game.

2026-10-30 tester report 13:00: the game closed 4 s after Ctrl+C ended a `diag --layers` run. Ctrl+C used to raise
KeyboardInterrupt right after WaitForDebugEvent returned an event of the per-frame breakpoint, and the debugger
detached with that event never continued (the thread stopped one byte past an int3, or with a single step armed):
Windows then gave the int3 / single-step exception to the game, which has no handler.

This test drives Tracer.run() against a fake kernel32 (no game needed) and checks, at the moment of
DebugActiveProcessStop: no event held, every breakpoint byte and every restore_on_detach write back, every thread
caught on an int3 rewound to it, no thread with the trap flag set, nothing pending.

    python tests\\test_tracer_detach.py
"""
import ctypes
import os
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "..", "tools"))

if os.name != "nt":
    print("SKIP: Windows only (tools/tracer.py loads kernel32)")
    sys.exit(0)

import tracer as T  # noqa: E402

BASE = 0x400000
BP_RVA = 0x6AE5B0
VA = BASE + BP_RVA
ORIG = b"\x55"            # push ebp
POKE = 0x900000           # a byte the diag switches off (like a WorldRender toggle)
PID = 4242
TF = 0x100

checks = 0
fails = 0


def check(cond, what):
    global checks, fails
    checks += 1
    if not cond:
        fails += 1
        print("FAIL:", what)


class FakeKernel:
    """Just enough kernel32 for Tracer.run(): a scripted debug-event queue and per-thread contexts."""

    def __init__(self, tracer_ref, script):
        self.tracer_ref = tracer_ref
        self.queue = list(script)      # (kind, tid, address, callback-before-delivery or None)
        self.held = None               # (pid, tid) of the event the debugger has not continued yet
        self.threads = {}              # tid -> {"Eip", "EFlags"}
        self.stopped = None            # snapshot at DebugActiveProcessStop
        self.kill_on_exit = True
        self.continued = []

    # --- process / debug API ------------------------------------------------------------------------------------
    def OpenProcess(self, *a):
        return 1

    def DebugActiveProcess(self, pid):
        return True

    def DebugSetProcessKillOnExit(self, flag):
        self.kill_on_exit = bool(flag)
        return True

    def SetConsoleCtrlHandler(self, *a):
        return True

    def WaitForDebugEvent(self, pev, timeout):
        assert self.held is None, "WaitForDebugEvent with an event still held"
        if not self.queue:
            return False
        kind, tid, addr, before = self.queue.pop(0)
        if before:
            before(self.tracer_ref[0])
        ev = pev._obj
        ctypes.memset(ctypes.byref(ev), 0, ctypes.sizeof(ev))
        ev.dwProcessId, ev.dwThreadId = PID, tid
        th = self.threads.setdefault(tid, {"Eip": 0, "EFlags": 0x202})
        if kind == "create":
            ev.dwDebugEventCode = T.CREATE_PROCESS_DEBUG_EVENT
        else:
            ev.dwDebugEventCode = T.EXCEPTION_DEBUG_EVENT
            ev.u.Exception.dwFirstChance = 1
            rec = ev.u.Exception.ExceptionRecord
            if kind == "int3":
                rec.ExceptionCode = 0x4000001F
                rec.ExceptionAddress = addr
                th["Eip"] = addr + 1           # the trap leaves Eip one past the int3
            else:                              # "step"
                rec.ExceptionCode = 0x4000001E
                rec.ExceptionAddress = th["Eip"]
                th["EFlags"] &= ~TF
        self.held = (PID, tid)
        return True

    def ContinueDebugEvent(self, pid, tid, status):
        assert self.held == (pid, tid), f"continue of {tid} but held {self.held}"
        self.held = None
        self.continued.append((tid, status))
        th = self.threads[tid]
        if th["EFlags"] & TF:
            # the thread runs one instruction and traps again
            th["Eip"] += 2                 # one instruction (2 bytes) further
            self.queue.insert(0, ("step", tid, None, None))
        return True

    def DebugActiveProcessStop(self, pid):
        t = self.tracer_ref[0]
        self.stopped = {
            "held": self.held,
            "queued": list(self.queue),
            "byte": t.mem.get(VA),
            "poke": t.mem.get(POKE),
            "threads": {k: dict(v) for k, v in self.threads.items()},
            "pending": dict(t.pending),
        }
        return True

    # --- threads ------------------------------------------------------------------------------------------------
    def OpenThread(self, access, inherit, tid):
        return 1000 + tid

    def CloseHandle(self, h):
        return True

    def SuspendThread(self, h):
        return 0

    def ResumeThread(self, h):
        return 1

    def Wow64GetThreadContext(self, h, pctx):
        th = self.threads.setdefault(h - 1000, {"Eip": 0, "EFlags": 0x202})
        ctx = pctx._obj
        ctx.Eip, ctx.EFlags = th["Eip"], th["EFlags"]
        return True

    def Wow64SetThreadContext(self, h, pctx):
        ctx = pctx._obj
        if ctx.ContextFlags & 0x1:     # CONTROL: Eip / EFlags
            th = self.threads.setdefault(h - 1000, {"Eip": 0, "EFlags": 0x202})
            th["Eip"], th["EFlags"] = ctx.Eip, ctx.EFlags
        return True


class MemTracer(T.Tracer):
    def __init__(self, pid):
        super().__init__(pid)
        self.mem = {VA: ORIG[0], POKE: 1}

    def find_base(self):
        return BASE

    def read(self, addr, n):
        return bytes(self.mem.get(addr + i, 0) for i in range(n))

    def write(self, addr, data):
        for i, b in enumerate(data):
            self.mem[addr + i] = b


def run_case(name, script, tracer_cls=MemTracer, expect_raise=None):
    ref = [None]
    fake = FakeKernel(ref, script)
    old_k32 = T.k32
    T.k32 = fake
    T.BREAKPOINTS.clear()
    T.BREAKPOINTS[BP_RVA] = ("FOGPOLY fog render (test)", [])
    T.WATCHES = []
    try:
        t = tracer_cls(PID)
        ref[0] = t
        try:
            t.run()
            raised = None
        except BaseException as e:      # noqa: BLE001
            raised = type(e)
    finally:
        T.k32 = old_k32
    check(raised is expect_raise, f"{name}: raised {raised}, expected {expect_raise}")
    st = fake.stopped
    check(not fake.kill_on_exit, f"{name}: DebugSetProcessKillOnExit(FALSE)")
    check(st is not None, f"{name}: DebugActiveProcessStop called")
    if st is None:
        return fake, t
    check(st["held"] is None, f"{name}: no event held at detach ({st['held']})")
    check(not st["queued"], f"{name}: no event left queued at detach ({st['queued']})")
    check(st["byte"] == ORIG[0], f"{name}: breakpoint byte restored ({st['byte']:#x})")
    check(st["poke"] == 1, f"{name}: restore_on_detach write undone ({st['poke']})")
    check(not st["pending"], f"{name}: no half-done single step ({st['pending']})")
    for tid, th in st["threads"].items():
        check(not th["EFlags"] & TF, f"{name}: thread {tid} has no trap flag left")
        check(th["Eip"] != VA + 1, f"{name}: thread {tid} not left one byte past the int3")
    return fake, t


def stop(t):
    t.request_stop("Ctrl+C (test)")


def poke(t):
    t.restore_on_detach(POKE, b"\x00")


T.LOG_PATH = os.path.join(tempfile.mkdtemp(), "trace.log")
T.STOP_PATH = T.LOG_PATH + ".stop"
T.INJECT_PATH = T.LOG_PATH + ".inject"

# 1. the 13:00 crash: Ctrl+C arrives with the per-frame int3 of thread 7 just received; thread 9 already sits in
#    the queue on the same int3 (it hit it before the byte was restored)
fake, t = run_case("ctrl+c on a per-frame breakpoint", [
    ("create", 1, None, None),
    ("int3", 1, 0x77000000, None),         # attach break-in -> arm
    ("int3", 7, VA, poke),
    ("int3", 7, VA, stop),
    ("int3", 9, VA, None),
])
check(fake.threads[9]["Eip"] == VA, "case 1: thread 9 rewound onto the restored instruction")
check(fake.threads[7]["Eip"] == VA + 2, "case 1: thread 7 stepped over the original instruction")

# 2. an error escapes in the middle of a breakpoint (the event is held when the finally runs)
class Boom(MemTracer):
    def on_breakpoint(self, tid, va):
        super().on_breakpoint(tid, va)      # byte restored, TF set, pending -- then the error
        raise KeyboardInterrupt


fake, t = run_case("error while an event is held", [
    ("create", 1, None, None),
    ("int3", 1, 0x77000000, None),
    ("int3", 7, VA, poke),
], tracer_cls=Boom, expect_raise=KeyboardInterrupt)
check(fake.threads[7]["Eip"] == VA, "case 2: the held thread is rewound onto the instruction")

# 3. stop file / request while idle: plain detach
fake, t = run_case("stop while idle", [
    ("create", 1, None, None),
    ("int3", 1, 0x77000000, stop),
])

# 4. two threads through the breakpoint, Ctrl+C on the second: its step is drained, no 0xCC is re-armed
fake, t = run_case("stop with a step in flight", [
    ("create", 1, None, None),
    ("int3", 1, 0x77000000, None),
    ("int3", 5, VA, None),
    ("int3", 6, VA, stop),                 # two threads through the breakpoint, the second with the stop
])

print(f"{checks - fails}/{checks} checks passed")
sys.exit(1 if fails else 0)
