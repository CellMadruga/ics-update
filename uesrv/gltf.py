"""Skinned character (mesh + Havok skeleton + weights + material textures) -> binary glTF (.glb) for Unreal.

The game is Z-up with characters facing +Y; glTF is Y-up facing +Z, so every position, normal and bone transform
is turned by (x, y, z) -> (-x, z, y) (-90 degrees about X, then 180 about Y: a rotation, so nothing is mirrored;
checked 2026-10-18 with a render, the first try showed Batman's back). Units stay metres (Unreal scales to cm).
Joints are the hkaSkeleton bones in skeleton order, which is what the mesh's bone indices already refer to
(checked 2026-10-18: every vertex sits ~0.2 m from its dominant bone, ~0.9 m from a random one).
UVs need no flip (the game and glTF both put the origin top-left).
Material texture keys (Gaslight Batman 0x160000E5; meaning from the decoded images, not from names):
0xBB8 base colour, 0xBC3 normal (DXT5 swizzled), 0xBCA emissive, 0xBE6 specular / gloss (not mapped into glTF,
written next to the .glb), 0xBC7 version-4 texture (not decoded).
"""
import json
import math
import struct

from . import textures

BASE, NORMAL, EMISSIVE, SPECULAR = 0xBB8, 0xBC3, 0xBCA, 0xBE6
_C = (0.0, math.sqrt(0.5), math.sqrt(0.5), 0.0)      # quaternion (x, y, z, w) of to_y_up


def to_y_up(v):
    return (-v[0], v[2], v[1])


def _qmul(a, b):
    ax, ay, az, aw = a
    bx, by, bz, bw = b
    return (aw * bx + ax * bw + ay * bz - az * by, aw * by - ax * bz + ay * bw + az * bx,
            aw * bz + ax * by - ay * bx + az * bw, aw * bw - ax * bx - ay * by - az * bz)


def _qrot(q, v):
    x, y, z, w = q
    t = (2 * (y * v[2] - z * v[1]), 2 * (z * v[0] - x * v[2]), 2 * (x * v[1] - y * v[0]))
    return (v[0] + w * t[0] + y * t[2] - z * t[1], v[1] + w * t[1] + z * t[0] - x * t[2],
            v[2] + w * t[2] + x * t[1] - y * t[0])


def _qnorm(q):
    n = math.sqrt(sum(c * c for c in q)) or 1.0
    return tuple(c / n for c in q)


def material_textures(data, material_offsets):
    """{key: texture DID} from a 0x16 material record: entries (key, 0xBB8, 0x13xxxxxx, 0, 0)."""
    out = {}
    for off in material_offsets:
        for p in range(off + 4, min(off + 1024, len(data) - 12), 4):
            key, kind, did = struct.unpack_from("<3I", data, p)
            if kind == 0xBB8 and did >> 24 == 0x13 and key not in out:
                out[key] = did
    return out


def binding_material(data, pack, ref):
    """The 0x16 material that a 0x17 model part binds (record: did | 0x14 shader | 0x10 key | 1 | 0x16 material)."""
    for off in pack.find_all(ref):
        w = struct.unpack_from("<5I", data, off)
        if w[1] >> 24 == 0x14 and w[2] >> 24 == 0x10 and w[4] >> 24 == 0x16:
            return w[4]
    return None


def _winding_flipped(mesh):
    """True when most triangles are clockwise relative to their vertex normals (glTF wants counter-clockwise)."""
    v, idx, votes = mesh["vertices"], mesh["indices"], 0
    for i in range(0, len(idx) - 2, 3):
        a, b, c = v[idx[i]], v[idx[i + 1]], v[idx[i + 2]]
        e1 = [b[k] - a[k] for k in range(3)]
        e2 = [c[k] - a[k] for k in range(3)]
        n = (e1[1] * e2[2] - e1[2] * e2[1], e1[2] * e2[0] - e1[0] * e2[2], e1[0] * e2[1] - e1[1] * e2[0])
        dot = sum(n[k] * (a[3 + k] + b[3 + k] + c[3 + k]) for k in range(3))
        votes += 1 if dot < 0 else -1
    return votes > 0


class _Bin:
    def __init__(self):
        self.buf, self.views, self.accessors = bytearray(), [], []

    def view(self, blob, target=None):
        while len(self.buf) % 4:
            self.buf += b"\0"
        v = {"buffer": 0, "byteOffset": len(self.buf), "byteLength": len(blob)}
        if target:
            v["target"] = target
        self.buf += blob
        self.views.append(v)
        return len(self.views) - 1

    def accessor(self, fmt, ctype, kind, rows, target=None, minmax=False, normalized=False):
        blob = b"".join(struct.pack("<" + fmt, *r) for r in rows)
        a = {"bufferView": self.view(blob, target), "componentType": ctype, "count": len(rows), "type": kind}
        if normalized:
            a["normalized"] = True
        if minmax:
            a["min"] = [min(r[k] for r in rows) for k in range(len(rows[0]))]
            a["max"] = [max(r[k] for r in rows) for k in range(len(rows[0]))]
        self.accessors.append(a)
        return len(self.accessors) - 1


def _convert(t, r, s):
    """A game-space local transform (Z-up) in glTF space."""
    return to_y_up(t), _qnorm(_qmul(_qmul(_C, r), (-_C[0], -_C[1], -_C[2], _C[3]))), (s[0], s[2], s[1])


def _animation(b, anim, local):
    """glTF animation from {"name", "frame_duration", "frames": [{joint index: (t, r, s)} per frame]} in game
    space. Rotations are written for every animated joint (signs kept continuous); translations and scales only
    where they leave the reference pose."""
    frames = anim["frames"]
    times = b.accessor("f", 5126, "SCALAR", [(i * anim["frame_duration"],) for i in range(len(frames))], minmax=True)
    samplers, channels = [], []
    for j in sorted(frames[0]):
        conv = [_convert(*f[j]) for f in frames]
        rots, prev = [], None
        for _, r, _ in conv:
            if prev is not None and sum(a * c for a, c in zip(prev, r)) < 0:
                r = tuple(-c for c in r)
            rots.append(r)
            prev = r
        rest_t, _, _ = local[j]
        paths = [("rotation", "4f", "VEC4", rots)]
        if any(max(abs(a - c) for a, c in zip(t, rest_t)) > 1e-5 for t, _, _ in conv):
            paths.append(("translation", "3f", "VEC3", [t for t, _, _ in conv]))
        if any(max(abs(c - 1.0) for c in s) > 1e-4 for _, _, s in conv):
            paths.append(("scale", "3f", "VEC3", [s for _, _, s in conv]))
        for path, fmt, kind, rows in paths:
            samplers.append({"input": times, "output": b.accessor(fmt, 5126, kind, rows), "interpolation": "LINEAR"})
            channels.append({"sampler": len(samplers) - 1, "target": {"node": j + 1, "path": path}})
    return {"name": anim["name"], "samplers": samplers, "channels": channels}


def build_glb(name, meshes_, skeleton, images, animations=()):
    """images: {"base": png bytes, "normal": png bytes, "emissive": png bytes} (any may be missing);
    animations: see _animation (joint indices are skeleton bone indices)."""
    b = _Bin()
    bones, parents = skeleton["bones"], skeleton["parents"]
    local = [_convert(t, r, s) for t, r, s in skeleton["pose"]]
    world = []
    for i, (t, r, s) in enumerate(local):
        if parents[i] < 0:
            world.append((t, r))
        else:
            pt, pr = world[parents[i]]
            rt = _qrot(pr, t)
            world.append(((pt[0] + rt[0], pt[1] + rt[1], pt[2] + rt[2]), _qnorm(_qmul(pr, r))))
    ibm = []
    for t, r in world:                                   # inverse of the rigid world transform, column-major
        ri = (-r[0], -r[1], -r[2], r[3])
        it = _qrot(ri, (-t[0], -t[1], -t[2]))
        cols = [_qrot(ri, e) for e in ((1, 0, 0), (0, 1, 0), (0, 0, 1))]
        ibm.append(cols[0] + (0.0,) + cols[1] + (0.0,) + cols[2] + (0.0,) + it + (1.0,))
    prims = []
    for m in meshes_:
        flip = _winding_flipped(m)
        pos = [to_y_up(v[:3]) for v in m["vertices"]]
        nrm = []
        for v in m["vertices"]:
            n = to_y_up(v[3:6])
            ln = math.sqrt(sum(c * c for c in n)) or 1.0
            nrm.append(tuple(c / ln for c in n))
        uv = [(v[6], v[7]) for v in m["vertices"]]
        wts = []
        for w in m["weights"]:
            s = sum(w) or 1.0
            wts.append(tuple(c / s for c in w))
        idx = list(m["indices"])
        if flip:
            for i in range(0, len(idx) - 2, 3):
                idx[i + 1], idx[i + 2] = idx[i + 2], idx[i + 1]
        attrs = {"POSITION": b.accessor("3f", 5126, "VEC3", pos, 34962, minmax=True),
                 "NORMAL": b.accessor("3f", 5126, "VEC3", nrm, 34962),
                 "TEXCOORD_0": b.accessor("2f", 5126, "VEC2", uv, 34962),
                 "JOINTS_0": b.accessor("4B", 5121, "VEC4", m["bones"], 34962),
                 "WEIGHTS_0": b.accessor("4f", 5126, "VEC4", wts, 34962)}
        ind = b.accessor("H", 5123, "SCALAR", [(i,) for i in idx], 34963)
        prims.append({"attributes": attrs, "indices": ind, "material": 0, "mode": 4})
    gl_images, gl_textures, material = [], [], {"name": name + "_material", "pbrMetallicRoughness":
                                                 {"metallicFactor": 0.0, "roughnessFactor": 0.8}}
    for slot in ("base", "normal", "emissive"):
        if slot not in images:
            continue
        gl_images.append({"bufferView": b.view(images[slot]), "mimeType": "image/png", "name": "%s_%s" % (name, slot)})
        gl_textures.append({"source": len(gl_images) - 1})
        ref = {"index": len(gl_textures) - 1}
        if slot == "base":
            material["pbrMetallicRoughness"]["baseColorTexture"] = ref
        elif slot == "normal":
            material["normalTexture"] = ref
        else:
            material["emissiveTexture"] = ref
            material["emissiveFactor"] = [1.0, 1.0, 1.0]
    nodes = [{"name": name, "mesh": 0, "skin": 0}]
    for i, (t, r, s) in enumerate(local):
        node = {"name": bones[i], "translation": list(t), "rotation": list(r)}
        if any(abs(c - 1.0) > 1e-4 for c in s):
            node["scale"] = list(s)
        kids = [j + 1 for j, p in enumerate(parents) if p == i]
        if kids:
            node["children"] = kids
        nodes.append(node)
    roots = [i + 1 for i, p in enumerate(parents) if p < 0]
    gltf = {"asset": {"version": "2.0", "generator": "icserver uesrv/gltf.py (private export)"},
            "scene": 0, "scenes": [{"nodes": [0] + roots}], "nodes": nodes,
            "meshes": [{"name": name, "primitives": prims}],
            "skins": [{"name": skeleton["name"], "joints": [i + 1 for i in range(len(bones))], "skeleton": roots[0],
                       "inverseBindMatrices": b.accessor("16f", 5126, "MAT4", ibm)}],
            "materials": [material]}
    if animations:
        gltf["animations"] = [_animation(b, a, local) for a in animations]
    if gl_images:
        gltf["images"], gltf["textures"] = gl_images, gl_textures
        gltf["samplers"] = [{"magFilter": 9729, "minFilter": 9987, "wrapS": 10497, "wrapT": 10497}]
        for t in gl_textures:
            t["sampler"] = 0
    while len(b.buf) % 4:
        b.buf += b"\0"
    gltf["buffers"] = [{"byteLength": len(b.buf)}]
    gltf["bufferViews"], gltf["accessors"] = b.views, b.accessors
    js = json.dumps(gltf, separators=(",", ":")).encode()
    js += b" " * (-len(js) % 4)
    body = struct.pack("<II", len(js), 0x4E4F534A) + js + struct.pack("<II", len(b.buf), 0x004E4942) + bytes(b.buf)
    return struct.pack("<III", 0x46546C67, 2, 12 + len(body)) + body


def texture_images(data, pack, keys):
    """{"base"|"normal"|"emissive"|"specular": png bytes} for the material texture keys found."""
    out = {}
    for slot, key in (("base", BASE), ("normal", NORMAL), ("emissive", EMISSIVE), ("specular", SPECULAR)):
        did = keys.get(key)
        tex = None
        for off in pack.find_all(did, struct.pack("<I", 2)) if did else []:
            tex = textures.parse(data, off)
            if tex:
                break
        if not tex:
            continue
        if slot == "normal" and tex["fourcc"] == b"DXT5":
            out[slot] = textures.png_from_rgba(tex["width"], tex["height"], textures.normal_map_rgba(tex))
        else:
            out[slot] = textures.to_png(tex)
    return out
