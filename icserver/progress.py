"""The player's progress kept between logins: the encounters completed (the
home screen unlocks Tutorial 2 once Tutorial 1 is in the list the server sends,
event 0x214B). Stored in data/progress.json next to the server; delete the file
to start over."""
import json
import os

from .config import ROOT


def _path(cfg):
    try:
        custom = cfg["account"].get("progress_file")
    except (KeyError, TypeError, AttributeError):
        custom = None
    return custom or os.path.join(ROOT, "data", "progress.json")


def _load(cfg):
    try:
        with open(_path(cfg), encoding="utf-8") as f:
            return json.load(f)
    except (OSError, ValueError):
        return {}


def completed(cfg):
    """Completed encounter DIDs, oldest first."""
    return [int(d) for d in _load(cfg).get("completed", [])]


def complete(cfg, did):
    """Record an encounter as completed; returns the updated list."""
    data = _load(cfg)
    done = [int(d) for d in data.get("completed", []) if int(d) != did] + [did]
    data["completed"] = done
    path = _path(cfg)
    try:
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2)
    except OSError:
        pass
    return done
