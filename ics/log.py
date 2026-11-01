"""Three logs in logs\\:
  server.log     what happened, one line per step (read this first)
  traffic.log    every message in and out, with hex dumps (debug.hexdump)
  unhandled.log  client events the server does not answer yet -- this is
                 where new features start (e.g. click the skill-rank button
                 and look here for the event it sends).
"""
import datetime
import os
import threading

from .wire import hexdump

_lock = threading.Lock()
_dir = None
_hexdump = True


def setup(log_dir, with_hexdump=True):
    global _dir, _hexdump
    os.makedirs(log_dir, exist_ok=True)
    _dir, _hexdump = log_dir, with_hexdump
    stamp = datetime.datetime.now().isoformat(timespec="seconds")
    for name in ("server.log", "traffic.log", "unhandled.log"):
        _write(name, f"\n===== server start {stamp} =====")


def _write(name, text):
    if _dir is None:
        return
    with _lock:
        with open(os.path.join(_dir, name), "a", encoding="utf-8") as f:
            f.write(text + "\n")


def _now():
    return datetime.datetime.now().strftime("%H:%M:%S.%f")[:-3]


def info(text, session=None):
    tag = f"[s{session.sid} {session.phase}] " if session is not None else ""
    line = f"{_now()} {tag}{text}"
    print(line, flush=True)
    _write("server.log", line)


def traffic(direction, label, data=b"", session=None):
    tag = f"s{session.sid} " if session is not None else ""
    line = f"{_now()} {tag}{direction} {label} ({len(data)} bytes)"
    if _hexdump and data:
        line += "\n" + hexdump(data)
    _write("traffic.log", line)


def unhandled(msg, session=None):
    tag = f"s{session.sid} {session.phase} " if session is not None else ""
    _write("unhandled.log", f"{_now()} {tag}event {msg.event_id:#06x} dest {msg.dest:#018x} "
                            f"flags {msg.flags:#x} body {msg.body.hex()}")
