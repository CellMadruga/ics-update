"""Analyse a dump made by tools/renderdoc_dump.py.

    python tools/rdoc_analyze.py <dump folder>                       # table of draws (skinned ones first)
    python tools/rdoc_analyze.py <dump folder> --obj <folder>        # one OBJ per distinct mesh draw
    python tools/rdoc_analyze.py <dump folder> --match <pack.rp>     # where those buffers sit in a pack

--match is the point of the capture: the client got its vertex/index buffers from the pack, so the byte offsets
found there (and the draw's baseVertex / indexOffset / numIndices) tell where the submesh table is and how it is
laid out. Output goes only to the folders you name; keep them outside the repository.
"""
import argparse
import json
import os
import struct
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

HALF = struct.Struct("<e")


def load(folder):
    with open(os.path.join(folder, "draws.json")) as f:
        draws = json.load(f)

    def buf(key):
        if not key:
            return b""
        with open(os.path.join(folder, "buf_%s.bin" % key), "rb") as f:
            return f.read()
    return draws, buf


def skinned(d):
    return any(a["name"].upper().startswith("BLENDINDICES") for a in d["attributes"])


def read_attr(vdata, stride, base, attr, fmt, i):
    o = base + i * stride + attr["offset"]
    f = fmt.upper()
    if "R32G32B32_FLOAT" in f:
        return struct.unpack_from("<3f", vdata, o)
    if "R32G32_FLOAT" in f:
        return struct.unpack_from("<2f", vdata, o)
    if "R16G16_UNORM" in f:
        return tuple(x / 65535.0 for x in struct.unpack_from("<2H", vdata, o))
    if "R16G16_SNORM" in f:  # the client's UV format (capture 2026-10-18)
        return tuple(max(x / 32767.0, -1.0) for x in struct.unpack_from("<2h", vdata, o))
    if "R16G16_FLOAT" in f:
        return tuple(HALF.unpack_from(vdata, o + 2 * k)[0] for k in range(2))
    return None


def mesh_of(d, buf):
    """(positions, uvs, triangles) for one draw, or None if the layout is not a plain triangle list."""
    pos = next((a for a in d["attributes"] if a["name"].upper().startswith("POSITION")), None)
    if not pos or "LIST" not in d["topology"].upper() or not d["ib"]:
        return None
    vb = next(v for v in d["vbuffers"] if v["slot"] == pos["slot"])
    vdata, idata = buf(vb["buf"]), buf(d["ib"])
    istride = d["indexByteStride"]
    fmt = "<%d%s" % (d["numIndices"], "H" if istride == 2 else "I")
    first = d["indexByteOffset"] + d["indexOffset"] * istride
    idx = [i + d["baseVertex"] for i in struct.unpack_from(fmt, idata, first)]
    used = sorted(set(idx))
    if vb["offset"] + (used[-1] + 1) * vb["stride"] > len(vdata):
        return None  # dynamic buffer: RenderDoc saved its end-of-frame contents, not this draw's
    remap = {v: n for n, v in enumerate(used)}
    uv = next((a for a in d["attributes"] if a["name"].upper().startswith("TEXCOORD") and a["index"] == 0), None)
    P, T = [], []
    for v in used:
        P.append(read_attr(vdata, vb["stride"], vb["offset"], pos, pos["format"], v))
        T.append(read_attr(vdata, vb["stride"], vb["offset"], uv, uv["format"], v) if uv else None)
    tris = [(remap[idx[i]], remap[idx[i + 1]], remap[idx[i + 2]]) for i in range(0, len(idx) - 2, 3)]
    return P, T, tris


def write_obj(path, mesh):
    P, T, tris = mesh
    with open(path, "w") as f:
        for p in P:
            f.write("v %.6f %.6f %.6f\n" % p)
        if all(t for t in T):
            for t in T:
                f.write("vt %.6f %.6f\n" % (t[0], 1.0 - t[1]))
        has_uv = all(t for t in T)
        for a, b, c in tris:
            if has_uv:
                f.write("f %d/%d %d/%d %d/%d\n" % (a + 1, a + 1, b + 1, b + 1, c + 1, c + 1))
            else:
                f.write("f %d %d %d\n" % (a + 1, b + 1, c + 1))


def match(draws, buf, pack_path):
    from icserver.rp import Pack
    data = Pack(pack_path).data
    seen = set()
    for d in sorted(draws, key=lambda d: not skinned(d)):
        for v in d["vbuffers"]:
            if not v["buf"] or (v["buf"], "vb") in seen or v["stride"] <= 0:
                continue
            seen.add((v["buf"], "vb"))
            raw = buf(v["buf"])
            if len(raw) < v["stride"] * 4:
                continue
            probe = raw[v["offset"]:v["offset"] + v["stride"] * 4]
            at = data.find(probe)
            if at >= 0:
                n = len(raw) // v["stride"]
                print("VB buf %s stride %d (%d vertices) found at pack stream offset %d (event %d, %s)"
                      % (v["buf"], v["stride"], n, at, d["event"], "skinned" if skinned(d) else "static"))
        if d["ib"] and (d["ib"], "ib") not in seen:
            seen.add((d["ib"], "ib"))
            raw = buf(d["ib"])
            at = data.find(raw[:48]) if len(raw) >= 48 else -1
            if at >= 0:
                print("IB buf %s (%d bytes, %d-byte indices) found at pack stream offset %d"
                      % (d["ib"], len(raw), d["indexByteStride"], at))


def main():
    p = argparse.ArgumentParser()
    p.add_argument("folder")
    p.add_argument("--obj")
    p.add_argument("--match")
    a = p.parse_args()
    draws, buf = load(a.folder)
    print("%d draws, %d skinned" % (len(draws), sum(skinned(d) for d in draws)))
    for d in sorted(draws, key=lambda d: (not skinned(d), -d["numIndices"]))[:40]:
        print("event %5d  idx %6d  base %6d  %-8s ib %s  layout %s" % (
            d["event"], d["numIndices"], d["baseVertex"], "skinned" if skinned(d) else "static", d["ib"],
            ",".join("%s%d:%s@%d" % (x["name"], x["index"], x["format"].replace("DXGI_FORMAT_", ""), x["offset"])
                     for x in d["attributes"])))
    if a.obj:
        os.makedirs(a.obj, exist_ok=True)
        done, written, skipped = set(), 0, 0
        for d in draws:
            key = (d["ib"], d["indexOffset"], d["numIndices"], d["baseVertex"])
            if key in done:
                continue
            done.add(key)
            m = mesh_of(d, buf)
            if m:
                write_obj(os.path.join(a.obj, "%s_e%d.obj" % ("skin" if skinned(d) else "static", d["event"])), m)
                written += 1
            else:
                skipped += 1
        print("%d OBJ files in %s (%d draws skipped: not a triangle list or dynamic buffer)" % (written, a.obj, skipped))
    if a.match:
        match(draws, buf, a.match)


if __name__ == "__main__":
    main()
