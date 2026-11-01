"""Turbine 0x17 static meshes -> OBJ (reverse-engineered 2026-10-18, see docs/reverse-engineering.md).

Record: u32 did | u32 shader 0x14.. | u32 key 0x10.. | u32 1 | u32 material 0x16.. | u32 1 | u32 1 | u32 ref |
u32 1 | u32 format (0x1205102 verified) | u32 vertex count | vertices (24 bytes each) | 6 floats bbox min/max |
u32 0 | u32 1 | u32 index count | u16 indices (triangle list).
Vertex: f32 x,y,z | u32 normal (3 signed bytes) | u32 uv (2 x UNORM16, u low half) | u32 tangent (3 signed bytes).
Only format 0x1205102 is verified for parse(); other static formats return None.

Skinned meshes (find_skinned, verified 2026-10-18 against a RenderDoc capture of Gaslight Batman, pack 0xA0000076):
... | u32 0x170000xx ref | u32 1 | u32 format (0x24D102 / 0x23D102) | u32 vertex count | vertices (32 bytes each) |
bbox | u32 0 | u32 1 | u32 index count | u16 indices. Vertex: f32 x,y,z | normal RGBA8 unorm | uv int16x2 snorm |
tangent RGBA8 unorm | bone indices u8x4 (skeleton-global; the client remaps them per draw) | weights u8x4 unorm.
These bytes are exactly the client's D3D11 vertex buffer except the bone indices.
"""
import math
import struct

VERIFIED_FORMATS = (0x1205102,)
SKINNED_FORMATS = (0x24D102, 0x23D102)
_MARK = struct.pack("<II", 0, 1)


def parse(data, off):
    """Return {did, vertices: [(x,y,z,nx,ny,nz,u,v)], indices, bbox} or None."""
    if off + 48 > len(data):
        return None
    w = struct.unpack_from("<11I", data, off)
    did, shader, key, one, material, _, _, _, _, fmt, nv = w
    if did >> 24 != 0x17 or shader >> 24 != 0x14 or material >> 24 != 0x16 or one != 1:
        return None
    if fmt not in VERIFIED_FORMATS or not 3 <= nv <= 65535:
        return None
    vs = off + 44
    ve = vs + nv * 24
    if ve + 36 > len(data):
        return None
    ic = struct.unpack_from("<I", data, ve + 32)[0]
    if ic % 3 or ve + 36 + ic * 2 > len(data):
        return None
    idx = struct.unpack_from("<%dH" % ic, data, ve + 36)
    if idx and max(idx) >= nv:
        return None
    verts = []
    for i in range(nv):
        x, y, z, n, uv, _t = struct.unpack_from("<3f3I", data, vs + 24 * i)
        nx, ny, nz = ((b - 256 if b > 127 else b) / 127.0 for b in (n & 255, (n >> 8) & 255, (n >> 16) & 255))
        verts.append((x, y, z, nx, ny, nz, (uv & 0xFFFF) / 65535.0, (uv >> 16) / 65535.0))
    return {"did": did, "vertices": verts, "indices": idx, "bbox": struct.unpack_from("<6f", data, ve),
            "shader": shader, "material": material}


def find_skinned(data):
    """Every skinned mesh in a decompressed pack stream, as parse() dicts plus "offset", "bones" and "weights"."""
    out, k = [], data.find(_MARK, 24)
    while k >= 0:
        mesh = _skinned_at(data, k)
        if mesh:
            out.append(mesh)
        k = data.find(_MARK, k + 1)
    return out


def _skinned_at(data, k):
    """The mesh whose bbox ends at k (k = the "0 | 1" marker before the index count), or None."""
    bbox = struct.unpack_from("<6f", data, k - 24)
    if not all(math.isfinite(v) and abs(v) < 1e4 for v in bbox) or any(bbox[i] > bbox[i + 3] for i in range(3)):
        return None
    if k + 12 > len(data):
        return None
    ic = struct.unpack_from("<I", data, k + 8)[0]
    if ic < 3 or ic % 3 or k + 12 + ic * 2 > len(data):
        return None
    idx = struct.unpack_from("<%dH" % ic, data, k + 12)
    nv = max(idx) + 1
    vs = k - 24 - nv * 32
    if vs < 16:
        return None
    ref, one, fmt, count = struct.unpack_from("<4I", data, vs - 16)
    if count != nv or fmt not in SKINNED_FORMATS or one != 1 or ref >> 24 != 0x17:
        return None
    verts, bones, weights = [], [], []
    for i in range(nv):
        o = vs + 32 * i
        x, y, z = struct.unpack_from("<3f", data, o)
        nx, ny, nz = (b / 127.5 - 1.0 for b in data[o + 12:o + 15])
        u, v = (max(c / 32767.0, -1.0) for c in struct.unpack_from("<2h", data, o + 16))
        verts.append((x, y, z, nx, ny, nz, u, v))
        bones.append(tuple(data[o + 24:o + 28]))
        weights.append(tuple(round(b / 255.0, 4) for b in data[o + 28:o + 32]))
    return {"did": ref, "vertices": verts, "indices": idx, "bbox": bbox, "format": fmt, "offset": vs,
            "bones": bones, "weights": weights}


def to_obj(mesh):
    out = ["# Infinite Crisis mesh 0x%08X (private export)" % mesh["did"]]
    out += ["v %.6f %.6f %.6f" % v[:3] for v in mesh["vertices"]]
    out += ["vt %.6f %.6f" % (v[6], 1.0 - v[7]) for v in mesh["vertices"]]
    out += ["vn %.5f %.5f %.5f" % v[3:6] for v in mesh["vertices"]]
    idx = mesh["indices"]
    for i in range(0, len(idx), 3):
        a, b, c = (j + 1 for j in idx[i:i + 3])
        out.append("f %d/%d/%d %d/%d/%d %d/%d/%d" % (a, a, a, b, b, b, c, c, c))
    return "\n".join(out) + "\n"
