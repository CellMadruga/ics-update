"""The new, data-driven server.

  python -m ics play       server + opens the game (InfiniteCrisis_patched.exe from python ic.py patch)
  python -m ics server     server only
  python -m ics skills [champion variant]   the champion's kit as the server reads it from the data
"""
import os
import subprocess
import sys
import time

from . import config, log


def client_args(cfg):
    s, g = cfg["server"], cfg["game"]
    base = f"http://{s['host']}:{s['soap_port']}/WebLoginApp-1.3"
    return ["--loginurl", f"{base}/AuthenticateWS", "--loginregion", g["region"],
            "--reportingurl", f"{base}/Metrics", "--language", g["language"]]


def launch_client(cfg):
    exe = os.path.join(cfg.game_dir, cfg["game"]["patched_exe"])
    if not os.path.isfile(exe):
        print(f"{exe} does not exist: run  python ic.py patch")
        return False
    aff = cfg["game"]["cpu_affinity"]
    cmd = f'start "" {f"/affinity {aff} " if aff else ""}"{exe}" ' + " ".join(client_args(cfg))
    subprocess.Popen(cmd, shell=True, cwd=cfg.game_dir)
    print(f"Game launched: {exe}")
    return True


def no_quick_edit():
    """2026-10-22 13:59 (tester: the second login hung at "retrieving champions"; the server logged nothing more):
    a click in a Windows console turns on QuickEdit selection, and the process then blocks on its next print until
    the selection ends. QuickEdit is switched off for this console."""
    if os.name != "nt":
        return
    try:
        import ctypes
        k32 = ctypes.windll.kernel32
        handle = k32.GetStdHandle(-10)                 # STD_INPUT_HANDLE
        mode = ctypes.c_uint32()
        if k32.GetConsoleMode(handle, ctypes.byref(mode)):
            # clear ENABLE_QUICK_EDIT_MODE (0x40), keep ENABLE_EXTENDED_FLAGS (0x80) so the change applies
            k32.SetConsoleMode(handle, (mode.value & ~0x40) | 0x80)
    except Exception:                                  # noqa: BLE001 - never stop the server for this
        pass


def main(argv):
    cmd = argv[0] if argv else "play"
    if config.load()["ics"].get("console_no_quick_edit", True):
        no_quick_edit()
    cfg = config.load()
    if cmd == "skills":
        from .gamedata import Data
        variant = int(argv[1], 16) if len(argv) > 1 else cfg["ics"]["champion"]
        for slot, sk in sorted(Data(cfg.game_dir).kit(variant).items()):
            print(f"  slot {slot}: {sk.key:<8} {sk.name:<32} script {sk.script:#x}  stats {sk.stats}")
        return 0
    if cmd not in ("play", "server"):
        print(__doc__)
        return 1
    from .server import Server
    log.setup(cfg.log_dir, cfg["debug"]["hexdump"])
    try:
        Server(cfg).start()
    except (OSError, RuntimeError) as e:
        print(f"Could not start: {e}")
        return 1
    print(f"Logs in {cfg.log_dir} (server.log, traffic.log, unhandled.log)")
    if cmd == "play":
        launch_client(cfg)
        print("Log in with any name -> Play Now -> VS A.I. -> Tutorial -> Tutorial 1 -> Launch")
    print("Server running. Ctrl+C to stop it.")
    try:
        while True:
            time.sleep(3600)
    except KeyboardInterrupt:
        print("\nServer stopped.")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
