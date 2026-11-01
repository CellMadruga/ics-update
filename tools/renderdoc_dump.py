"""Dump the geometry of every draw call of a RenderDoc capture (for the mesh-format work).

Run it INSIDE RenderDoc (qrenderdoc): open the capture (.rdc), Window > Python Shell, then

    OUT = r"C:\\ic_capture"            # any folder outside the repository
    exec(open(r"C:\\path\\to\\tools\\renderdoc_dump.py").read())

It writes OUT\\draws.json (one entry per draw: event id, counts, topology, vertex-input layout, buffer ids)
and OUT\\buf_<id>.bin (raw bytes of each vertex/index buffer used). Nothing here touches the game files.
Analyse the result with: python tools\\rdoc_analyze.py <OUT> [--match <pack>] [--obj <folder>]
Tested against the RenderDoc 1.x Python API only on paper: if a name differs in your version the error says which.
"""
import json
import os

import renderdoc as rd

try:
    OUT
except NameError:
    OUT = os.path.join(os.path.expanduser("~"), "ic_capture")
os.makedirs(OUT, exist_ok=True)


def _actions(ctrl):
    getter = getattr(ctrl, "GetRootActions", None) or ctrl.GetDrawcalls
    return getter()


def _walk(actions):
    for a in actions:
        yield a
        for c in _walk(a.children):
            yield c


def _is_draw(a):
    flags = a.flags
    draw = getattr(rd, "ActionFlags", None) or rd.DrawFlags
    return bool(flags & draw.Drawcall) and a.numIndices > 0


def _semantic(attr):
    """{"name", "index"}: RenderDoc 1.46 has no semanticIndex, the index is appended to the name (TEXCOORD1)."""
    index = getattr(attr, "semanticIndex", None)
    name = attr.name
    if index is None:
        base = name.rstrip("0123456789")
        index = int(name[len(base):]) if len(base) < len(name) else 0
        name = base
    return {"name": name, "index": index}


def _dump(ctrl):
    result, saved = [], set()

    def save(rid, size_hint=None):
        key = str(int(rid))
        if key in saved or int(rid) == 0:
            return key
        data = ctrl.GetBufferData(rid, 0, 0)
        with open(os.path.join(OUT, "buf_%s.bin" % key), "wb") as f:
            f.write(bytes(data))
        saved.add(key)
        return key

    for a in _walk(_actions(ctrl)):
        if not _is_draw(a):
            continue
        ctrl.SetFrameEvent(a.eventId, True)
        st = ctrl.GetPipelineState()
        ib = st.GetIBuffer()
        vbs = st.GetVBuffers()
        attrs = st.GetVertexInputs()
        entry = {
            "event": a.eventId, "name": a.GetName(ctrl.GetStructuredFile()) if hasattr(a, "GetName") else "",
            "numIndices": a.numIndices, "numInstances": a.numInstances, "indexOffset": a.indexOffset,
            "baseVertex": a.baseVertex, "indexByteStride": ib.byteStride, "indexByteOffset": ib.byteOffset,
            "ib": save(ib.resourceId) if int(ib.resourceId) else None,
            "topology": str(st.GetPrimitiveTopology()),
            "vbuffers": [{"slot": i, "buf": save(v.resourceId) if int(v.resourceId) else None,
                          "stride": v.byteStride, "offset": v.byteOffset} for i, v in enumerate(vbs)],
            "attributes": [dict(_semantic(t), rawName=t.name, slot=t.vertexBuffer,
                                offset=t.byteOffset, format=str(t.format.Name())) for t in attrs],
        }
        result.append(entry)
    with open(os.path.join(OUT, "draws.json"), "w") as f:
        json.dump(result, f, indent=1)
    print("dumped %d draws, %d buffers -> %s" % (len(result), len(saved), OUT))


pyrenderdoc.Replay().BlockInvoke(_dump)  # noqa: F821  (pyrenderdoc is provided by qrenderdoc)
