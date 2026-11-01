"""Exports a champion's skinned meshes + Havok skeleton + weights + textures to one .glb for Unreal Engine.

Usage:
    python tools\\gltf_export.py <pack id or .rp path> <output folder outside the repository> [name]
                                 [--anims <behavior pack id>]

Example (Gaslight Batman): python tools\\gltf_export.py 0xA0000076 C:\\ic_export\\batman batman_gaslight
                           --anims 0xA0000122
With --anims, every hkaSplineCompressedAnimation of that pack whose tracks match the skeleton is added as a glTF
animation (Unreal imports each one as an Animation Sequence).
Writes <name>.glb (mesh, 86-bone skeleton, skin weights, base colour / normal / emissive textures) and
<name>_specular.png (specular / gloss map, to hook up by hand). Formats: uesrv/meshes.py, uesrv/havok.py,
uesrv/gltf.py. Only reads the pack; the output must stay out of the repository (CLAUDE.md hard rule 1).
"""
import os
import struct
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, ROOT)

from icserver import config as config_mod   # noqa: E402
from icserver.rp import Pack                 # noqa: E402
from uesrv import gltf, havok, havok_anim, meshes   # noqa: E402


def pack_path(src):
    if src.lower().endswith(".rp"):
        return src
    return os.path.join(config_mod.load().game_dir, "rp", "0x%08x.rp" % int(src, 16))


def clip_names():
    """{0x1A DID: name} for the clips the catalog names (catalog/data/animations.tsv, kind "clip")."""
    out = {}
    with open(os.path.join(ROOT, "catalog", "data", "animations.tsv"), encoding="utf-8") as f:
        for line in f.read().splitlines()[1:]:
            cols = line.split("\t")
            if len(cols) > 3 and cols[3] == "clip":
                out[int(cols[0], 16)] = cols[1]
    return out


def load_animations(path, skel):
    """[{name, frame_duration, frames}] for the clips of a behavior pack that match the skeleton. Clips the catalog
    names keep that name; the others are anim_<DID>_<duration> (names not resolved yet)."""
    names = clip_names()
    pack = Pack(path)
    data = pack.data
    found = []
    for h in havok.find_packfiles(data):
        try:
            pf = havok.Packfile(data, h)
        except (ValueError, KeyError, struct.error):
            continue
        found += [(h, a) for a in havok_anim.animations(pf)]
    dids = havok_anim.clip_dids(pack, [a for _, a in found])
    out = []
    for k, (h, anim) in enumerate(found):
        joints = havok_anim.bone_map(anim.track_names, skel["bones"])
        if None in joints or len(set(joints)) != len(joints):
            continue
        frames = [dict(zip(joints, anim.sample(f))) for f in range(anim.frames)]
        if k < len(dids) and dids[k] in names:
            name = names[dids[k]]
        elif k < len(dids):
            name = "anim_%08X_%.2fs" % (dids[k], anim.duration)
        else:
            name = "clip_%06x_%.2fs" % (h, anim.duration)
        out.append({"name": name, "frame_duration": anim.frame_duration, "frames": frames})
    return out


def main():
    args = sys.argv[1:]
    anim_pack = None
    if "--anims" in args:
        k = args.index("--anims")
        anim_pack = args[k + 1]
        del args[k:k + 2]
    if len(args) not in (2, 3):
        print(__doc__)
        return 1
    src, out = pack_path(args[0]), args[1]
    name = args[2] if len(args) == 3 else os.path.splitext(os.path.basename(src))[0]
    if os.path.abspath(out).lower().startswith(ROOT.lower()):
        print("refusing to write game assets inside the repository:", out)
        return 1
    pack = Pack(src)
    data = pack.data
    found = meshes.find_skinned(data)
    if not found:
        print("no skinned mesh in", src)
        return 1
    skels = [s for h in havok.find_packfiles(data) for s in havok.skeletons(havok.Packfile(data, h))]
    need = max(max(b) for m in found for b in m["bones"]) + 1
    skels = [s for s in skels if len(s["bones"]) >= need]
    if not skels:
        print("no hkaSkeleton with %d+ bones in %s" % (need, src))
        return 1
    skel = max(skels, key=lambda s: (s["name"] == "MainSkeleton", len(s["bones"])))
    material = gltf.binding_material(data, pack, found[0]["did"])
    keys = gltf.material_textures(data, pack.find_all(material)) if material else {}
    images = gltf.texture_images(data, pack, keys)
    anims = load_animations(pack_path(anim_pack), skel) if anim_pack else []
    os.makedirs(out, exist_ok=True)
    glb = gltf.build_glb(name, found, skel, images, anims)
    with open(os.path.join(out, name + ".glb"), "wb") as f:
        f.write(glb)
    if "specular" in images:
        with open(os.path.join(out, name + "_specular.png"), "wb") as f:
            f.write(images["specular"])
    print("%s.glb: %d meshes (%d vertices, %d triangles), skeleton %r (%d bones), material %s, textures %s (%d KB)" % (
        name, len(found), sum(len(m["vertices"]) for m in found), sum(len(m["indices"]) // 3 for m in found),
        skel["name"], len(skel["bones"]), "0x%08X" % material if material else "-",
        ", ".join(sorted(images)) or "-", len(glb) // 1024))
    if anims:
        print("%d animations (%d frames)" % (len(anims), sum(len(a["frames"]) for a in anims)))
    return 0


if __name__ == "__main__":
    sys.exit(main())
