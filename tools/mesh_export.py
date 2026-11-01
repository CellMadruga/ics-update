"""Exports the skinned meshes of a pack to OBJ (for the UE5 migration work).

Usage:
    python tools\\mesh_export.py <pack id or .rp path> <output folder outside the repository> [--skin]

The format is in uesrv/meshes.py (find_skinned) and docs/reverse-engineering.md. With --skin, <name>.skin.json
gets each vertex's bone indices (skeleton-global) and weights. Only reads the pack; the output must stay out of
the repository (CLAUDE.md hard rule 1).
"""
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, ROOT)

from icserver import config as config_mod   # noqa: E402
from icserver.rp import Pack                 # noqa: E402
from uesrv import meshes                     # noqa: E402


def main():
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    if len(args) != 2:
        print(__doc__)
        return 1
    src, out = args
    if not src.lower().endswith(".rp"):
        src = os.path.join(config_mod.load().game_dir, "rp", "0x%08x.rp" % int(src, 16))
    if os.path.abspath(out).lower().startswith(ROOT.lower()):
        print("refusing to write game geometry inside the repository:", out)
        return 1
    os.makedirs(out, exist_ok=True)
    stem = os.path.splitext(os.path.basename(src))[0]
    found = meshes.find_skinned(Pack(src).data)
    for m in found:
        name = "%s_%08x" % (stem, m["offset"])
        with open(os.path.join(out, name + ".obj"), "w") as f:
            f.write(meshes.to_obj(m))
        if "--skin" in sys.argv:
            with open(os.path.join(out, name + ".skin.json"), "w") as f:
                json.dump({"bones": m["bones"], "weights": m["weights"]}, f)
        print("%s  ref 0x%08X  format 0x%X  %6d vertices  %6d triangles  bbox %s" % (
            name, m["did"], m["format"], len(m["vertices"]), len(m["indices"]) // 3,
            " ".join("%.2f" % b for b in m["bbox"])))
    print("%d skinned meshes -> %s" % (len(found), out))
    return 0


if __name__ == "__main__":
    sys.exit(main())
