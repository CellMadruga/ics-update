"""Turns a `python tools\\diag.py --anims` trace into clip DID -> animation name.

Usage:
    python tools\\anim_names.py [logs\\diag.log] [--pack 0xA0000122] [--write]

Each "ANIM" line of the trace has a clip generator's animationName and the signature of the animation the
client linked to it (duration, frames, blocks, data size, first 32 data bytes). The same signature is computed
for every hkaSplineCompressedAnimation of the behavior pack (uesrv/havok_anim.py), and each packfile has its
0x1A DID (havok_anim.clip_dids), so a match gives DID -> name with no guessing. With --write the names go into
catalog/data/animations.tsv (kind "clip"); existing clip rows are checked, never overwritten. Then run
python ic.py catalog and re-export the .glb (tools\\gltf_export.py).
"""
import os
import re
import struct
import sys
import zlib

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, ROOT)

from icserver import config as config_mod   # noqa: E402
from icserver.rp import Pack                 # noqa: E402
from uesrv import havok, havok_anim          # noqa: E402

LINE = re.compile(r"ANIM clip='(?P<clip>[^']*)' anim='(?P<anim>[^']*)' binding=(?P<binding>\S+)"
                  r"(?: anim_obj=\S+ dur=(?P<dur>[\d.]+) tracks=(?P<tracks>\d+) frames=(?P<frames>\d+) "
                  r"blocks=(?P<blocks>\d+) data=(?P<data>\d+) head=(?P<head>[0-9a-f]*) crc=(?P<crc>[0-9a-f]+))?")
CATALOG = os.path.join(ROOT, "catalog", "data", "animations.tsv")


def pack_signatures(pack):
    """{(frames, blocks, data size, head hex, crc32 of the data): [(DID, duration)]} for the pack's animations
    (the head alone is not unique: 0x1A000F5B / F5C and 0x1A0000F6 / F7 share it)."""
    found = []
    for h in havok.find_packfiles(pack.data):
        try:
            pf = havok.Packfile(pack.data, h)
        except (ValueError, KeyError, struct.error):
            continue
        for o in pf.of_class("hkaSplineCompressedAnimation"):
            found.append((pf, o, havok_anim.SplineAnimation(pf, o)))
    dids = havok_anim.clip_dids(pack, [a for _, _, a in found])
    sigs = {}
    for did, (pf, o, a) in zip(dids, found):
        da, dn = pf.array(o + 116)
        blob = pack.data[pf.base + da:pf.base + da + dn]
        key = (a.frames, a.blocks, dn, blob[:32].hex(), "%08x" % (zlib.crc32(blob) & 0xFFFFFFFF))
        sigs.setdefault(key, []).append((did, a.duration))
    return sigs, len(found), len(dids)


def parse_trace(path):
    out = []
    with open(path, encoding="utf-8", errors="replace") as f:
        for line in f:
            m = LINE.search(line)
            if m:
                out.append(m.groupdict())
    return out


def main():
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    cfg = config_mod.load()
    pack_id = 0xA0000122
    if "--pack" in sys.argv:
        pack_id = int(sys.argv[sys.argv.index("--pack") + 1], 16)
        args = [a for a in args if a != sys.argv[sys.argv.index("--pack") + 1]]
    trace = args[0] if args else os.path.join(cfg.log_dir, "diag.log")
    pack = Pack(os.path.join(cfg.game_dir, "rp", "0x%08x.rp" % pack_id))
    sigs, n_anims, n_dids = pack_signatures(pack)
    print("pack 0x%08X: %d animations, %d with a DID" % (pack_id, n_anims, n_dids))
    links = parse_trace(trace)
    print("%s: %d linked clips" % (trace, len(links)))
    names, clips, unmatched = {}, {}, []
    for ln in links:
        anim = os.path.basename(ln["anim"].replace("\\", "/"))
        anim = anim[:-4] if anim.lower().endswith(".hkx") else anim
        if not ln.get("frames"):
            unmatched.append((ln["clip"], anim, "no animation loaded"))
            continue
        key = (int(ln["frames"]), int(ln["blocks"]), int(ln["data"]), ln["head"], ln["crc"])
        hits = sigs.get(key, [])
        if len(hits) != 1:
            unmatched.append((ln["clip"], anim, "%d packfiles with that signature" % len(hits)))
            continue
        did, dur = hits[0]
        if abs(dur - float(ln["dur"])) > 0.01:
            unmatched.append((ln["clip"], anim, "duration differs (%s vs %.3f)" % (ln["dur"], dur)))
            continue
        if did in names and names[did] != anim:
            print("CONFLICT: 0x%08X linked as %s and %s" % (did, names[did], anim))
        names.setdefault(did, anim)
        clips.setdefault(did, set()).add(ln["clip"])
    for did in sorted(names):
        print("0x%08X  %-48s clips: %s" % (did, names[did], ", ".join(sorted(clips[did]))))
    for clip, anim, why in unmatched:
        print("unmatched: %s (%s): %s" % (clip, anim, why))
    if "--write" in sys.argv:
        write_catalog(names, clips)
    return 0


def write_catalog(names, clips):
    with open(CATALOG, encoding="utf-8") as f:
        text = f.read()
    known = {}
    for line in text.splitlines()[1:]:
        cols = line.split("\t")
        if len(cols) > 3 and cols[3] == "clip":
            known[int(cols[0], 16)] = cols[1]
    added = 0
    if not text.endswith("\n"):
        text += "\n"
    for did, name in sorted(names.items()):
        if did in known:
            if known[did] != name:
                print("CHECK: catalog has 0x%08X = %s, the trace says %s (left as is)" % (did, known[did], name))
            continue
        note = ("Gaslight Batman animation clip (hkaSplineCompressedAnimation, pack 0xA0000122). Name from a "
                "diag.py --anims trace (the client linked it for clip generator(s) %s); exported by "
                "tools/gltf_export.py." % ", ".join(sorted(clips[did])))
        text += "\t".join(("0x%08X" % did, name, "", "clip", "data only", note)) + "\n"
        added += 1
    with open(CATALOG, "w", encoding="utf-8", newline="") as f:
        f.write(text)
    print("catalog: %d clip names added (%d were already there)" % (added, len(known)))


if __name__ == "__main__":
    sys.exit(main())
