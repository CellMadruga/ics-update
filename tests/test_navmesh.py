"""The map's navmesh (ics/navmesh.py) from Tutorial 1's map pack: walkable spots, a path along the whole route.

    python tests\test_navmesh.py
"""
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from ics import config                 # noqa: E402
from ics.gamedata import Data          # noqa: E402

results = []


def check(name, cond, detail=""):
    results.append(bool(cond))
    print(f"  {'ok  ' if cond else 'FAIL'} {name}" + (f"  ({detail})" if detail and not cond else ""))


def main():
    cfg = config.load()
    g = Data(cfg.game_dir).navgrid(0x40000991, (0x13, 0xCB))
    check("navmesh read from the map pack", g is not None and len(g.tris) > 100, g and len(g.tris))
    spots = {"spawn": (18.7, 60.4), "first drone": (35.3, 56.3), "first gate": (54.05, 44.8),
             "bridge": (69.6, 36.7), "last gate": (89.9, 26.2), "Destroyer": (152.75, 24.0)}
    for name, p in spots.items():
        check(f"{name} is walkable", g.walkable(*p))
    path = g.path(spots["spawn"], spots["Destroyer"])
    check("a path from the start to the Destroyer", path and path[-1] == spots["Destroyer"], path)
    check("every segment of it stays on the mesh",
          path and all(g.line_clear(a, b) for a, b in zip([spots["spawn"]] + path[:-1], path)))
    check("a straight line from the start to the Destroyer is NOT clear (buildings in between)",
          not g.line_clear(spots["spawn"], spots["Destroyer"]))
    m = g.copy()
    m.block("vehicle", 43.66, 52.61, 4.0, 1.6, -2.513)
    check("a vehicle's box blocks its spot (dynamic obstacle)", not m.walkable(43.66, 52.61))
    check("...on the match's copy only", g.walkable(43.66, 52.61))
    m.unblock("vehicle")
    check("unblocked again", m.walkable(43.66, 52.61))
    print(f"\n{sum(results)}/{len(results)} navmesh checks")
    return 0 if all(results) else 1


if __name__ == "__main__":
    sys.exit(main())
