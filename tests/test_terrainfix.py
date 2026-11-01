"""The terrain-socket pack patch (icserver/terrainfix.py, part of `python ic.py patch`): on a small synthetic 10PR pack
(stored deflate blocks that split the patched bytes across deflate and file blocks) a dry run writes nothing, the
patch raises the socket and levels its normals with a valid Adler-32, a second run keeps it, taking the site out of the
list restores the file byte for byte, and unexpected bytes or a compressed stream are refused. Then a read-only dry run
of the built-in sites against the install named in config.toml ([game] dir): every site must be recognised, and
Crime Alley's bytes must be the ones tools/diag.py --mapa-rellenar wrote in memory (the state the tester confirmed).
The defaults are checked against the server's socket lids ([ics] match_socket_covers). --real also applies, re-applies
and restores every site on copies of the installed packs in a temporary folder (about 400 MB of copies, seconds).

    python tests\\test_terrainfix.py [--real]
"""
import hashlib
import json
import math
import os
import struct
import sys
import tempfile
import zlib

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from icserver import terrainfix as T         # noqa: E402

results = []
PACK = 0xA0F0FFFE                            # no such pack in the game: the test writes only to a temporary folder
RECORD = 0x80F013BB
REC_AT = 0x1FFF1                             # odd offsets: the heights / normals straddle deflate and file blocks
NORMALS_AT = 0x1000
STREET, SOCKET = 6553, 5897                  # 199.98 m / 179.96 m (Crime Alley's dampener socket)


def check(name, cond, detail=""):
    results.append(bool(cond))
    print(f"  {'ok  ' if cond else 'FAIL'} {name}" + (f"  ({detail})" if detail and not cond else ""))


def record():
    """Two sockets, as Crime Alley's: (40, 75) / (40, 80) and (120, 75) / (120, 80)."""
    h = [STREET] * 1089
    for i, j in ((8, 15), (8, 16), (24, 15), (24, 16)):
        h[i * 33 + j] = SOCKET
    rec = struct.pack("<II", RECORD, 0x441) + bytes([0x80, 0]) * 544 + b"\x80" + b"\0" * 3
    rec += struct.pack("<I", 0x441) + struct.pack("<1089H", *h)
    rec += b"\xAB" * (NORMALS_AT - 4 - len(rec)) + struct.pack("<I", 0x441)
    normals = [(0.0, 0.0, 1.0)] * 1089
    for i in (7, 8, 9, 23, 24, 25):
        for j in (14, 15, 16, 17):
            normals[i * 33 + j] = (0.3, 0.1, 0.95)
    return rec + b"".join(struct.pack("<3f", *n) for n in normals)


def with_crc(stream, site):
    spots = T.site_spots(stream, site)
    site["crc"] = (zlib.crc32(b"".join(stream.read(d, len(b)) for d, b in spots)),
                   zlib.crc32(b"".join(b for _d, b in spots)))
    return site


def build_pack(path, data, stored=True, deflate_block=7000):
    """10PR file: header, then the payload (2 DIDs + the zlib stream) in 0x20000-byte blocks with a length trailer."""
    if stored:
        z = bytearray(b"\x78\x01")
        for k in range(0, len(data), deflate_block):
            part = data[k:k + deflate_block]
            z += bytes([1 if k + deflate_block >= len(data) else 0]) + struct.pack("<HH", len(part), len(part) ^ 0xFFFF)
            z += part
        z += struct.pack(">I", zlib.adler32(data))
    else:
        z = zlib.compress(data)
    payload = struct.pack("<II", RECORD, 0x13000001) + bytes(z)
    out = bytearray(b"10PR" + struct.pack("<IIIII", 17, 1, len(payload), 2, 0))
    out += b"\0" * (0x400 - len(out))
    for k in range(0, len(payload), T.BLOCK_DATA):
        part = payload[k:k + T.BLOCK_DATA]
        out += part + b"\0" * (T.BLOCK_DATA - len(part)) + struct.pack("<I", len(part))
    with open(path, "wb") as f:
        f.write(out)


def stream_data(path):
    raw = open(path, "rb").read()
    size = struct.unpack_from("<I", raw, 0xC)[0]
    payload = b"".join(raw[0x400 + k * T.BLOCK: 0x400 + k * T.BLOCK + T.BLOCK_DATA]
                       for k in range((size + T.BLOCK_DATA - 1) // T.BLOCK_DATA))[:size]
    return zlib.decompress(payload[8:])        # checks the Adler-32


def md5(path):
    return hashlib.md5(open(path, "rb").read()).hexdigest()


def diag_fill_spots(stream, site):
    """tools/diag.py --mapload-fill (ml_fill, 2026-10-28 14:40, the in-memory fill the tester saw remove both black
    octagons) replayed on the record's heights: [(decompressed offset, bytes)] of the heights it raised and the normals
    it rewrote. A copy of its rule (each FILL_SPOTS vertex 450-820 units under at least two axis neighbours goes to the
    median of the higher ring; central-difference normals on the 3 x 3 around each)."""
    import importlib.util
    spec = importlib.util.spec_from_file_location("diag", os.path.join(ROOT, "tools", "diag.py"))
    diag = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(diag)                  # constants only: its main() runs under __main__
    rec = site["at"]
    h = list(struct.unpack("<1089H", stream.read(rec + T.HEIGHTS_AT, 2178)))
    out, changed = [], []
    for x, y in diag.FILL_SPOTS:
        i, j = int(x / 5), int(y / 5)
        if not (0 < i < 32 and 0 < j < 32):
            continue
        v = h[i * 33 + j]
        high = [a for a in (h[(i + 1) * 33 + j], h[(i - 1) * 33 + j], h[i * 33 + j + 1], h[i * 33 + j - 1]) if a > v]
        if len(high) < 2 or not all(450 <= a - v <= 820 for a in high):
            continue
        ring = sorted(h[(i + di) * 33 + (j + dj)] for di in (-1, 0, 1) for dj in (-1, 0, 1)
                      if (di or dj) and h[(i + di) * 33 + (j + dj)] - v >= 450)
        h[i * 33 + j] = ring[len(ring) // 2]
        out.append((rec + T.HEIGHTS_AT + 2 * (i * 33 + j), struct.pack("<H", h[i * 33 + j])))
        changed.append((i, j))
    done = set()
    for i, j in changed:
        for a in (i - 1, i, i + 1):
            for b in (j - 1, j, j + 1):
                if (a, b) in done or not (0 < a < 32 and 0 < b < 32):
                    continue
                done.add((a, b))
                zx = (h[(a + 1) * 33 + b] - h[(a - 1) * 33 + b]) * 2000 / 65535 / 10.0
                zy = (h[a * 33 + b + 1] - h[a * 33 + b - 1]) * 2000 / 65535 / 10.0
                ln = (zx * zx + zy * zy + 1.0) ** 0.5
                out.append((rec + site["normals_at"] + 12 * (a * 33 + b), struct.pack("<3f", -zx / ln, -zy / ln, 1.0 / ln)))
    return out


def same_values(a, b):
    """Two spots' bytes hold the same u16 / f32 values (-0.0 == 0.0)."""
    if len(a) != len(b):
        return False
    if len(a) == 2:
        return a == b
    return all(abs(p - q) < 1e-6 for p, q in zip(struct.unpack("<3f", a), struct.unpack("<3f", b)))


def inflate(path):
    """The pack's records (zlib checks the Adler-32), read as icserver/rp.py does."""
    raw = open(path, "rb").read()
    size, count = struct.unpack_from("<II", raw, 0xC)
    payload = b"".join(raw[0x400 + k * T.BLOCK: 0x400 + k * T.BLOCK + T.BLOCK_DATA]
                       for k in range((size + T.BLOCK_DATA - 1) // T.BLOCK_DATA))[:size]
    return zlib.decompressobj().decompress(payload[4 * count:])


def real_round_trip(rp_dir):
    """--real: every built-in site applied, re-applied and taken out again on copies of the installed map packs (and
    their backups, if python ic.py patch already ran) in a temporary folder; the install is only read."""
    import glob
    import shutil
    packs = sorted({s["pack"] for s in T.SITES.values()})
    with tempfile.TemporaryDirectory() as tmp:
        fresh = True
        for p in packs:
            src = os.path.join(rp_dir, f"0x{p:08x}.rp")
            shutil.copyfile(src, os.path.join(tmp, os.path.basename(src)))
            if os.path.isfile(src + ".terrainfix.json"):
                shutil.copyfile(src + ".terrainfix.json", os.path.join(tmp, os.path.basename(src) + ".terrainfix.json"))
                fresh = False
        before = {p: md5(os.path.join(tmp, f"0x{p:08x}.rp")) for p in packs}
        lines = T.apply(tmp, list(T.SITES))
        ok, detail = True, []
        for key, site in T.SITES.items():
            data = inflate(os.path.join(tmp, f"0x{site['pack']:08x}.rp"))
            with T.Stream(os.path.join(tmp, f"0x{site['pack']:08x}.rp"), lazy=True) as st:
                spots = T.site_spots(st, site)
            if any(data[d:d + len(b)] != b for d, b in spots):
                ok = False
                detail.append(key)
        check(f"--real: all {len(T.SITES)} sites applied to copies of the {len(packs)} installed packs; each pack "
              "inflates (Adler-32) and holds the site's bytes", ok and not any("not " in x for x in lines),
              (detail, lines))
        after = {p: md5(os.path.join(tmp, f"0x{p:08x}.rp")) for p in packs}
        lines = T.apply(tmp, list(T.SITES))
        check("--real: a second run changes nothing (every site already flattened)",
              after == {p: md5(os.path.join(tmp, f"0x{p:08x}.rp")) for p in packs}
              and all("already flattened" in x for x in lines), lines)
        lines = T.apply(tmp, [])
        states = {k: T.installed_state(tmp, k) for k in T.SITES}
        left = glob.glob(os.path.join(tmp, "*.json")) + glob.glob(os.path.join(tmp, "*.tmp"))
        check("--real: all sites taken out -> every site original, no backup or .tmp left"
              + (", every pack md5-identical to the install" if fresh else ""),
              all(v == "original" for v in states.values()) and not left
              and (not fresh or before == {p: md5(os.path.join(tmp, f"0x{p:08x}.rp")) for p in packs}),
              (states, left, lines))


def main():
    data = b"\x11" * REC_AT + record() + b"\x22" * 50000
    site = {"pack": PACK, "record": RECORD, "at": REC_AT, "normals_at": NORMALS_AT, "vertices": [(40, 75), (40, 80)],
            "crc": (0, 0), "maps": "test"}
    with tempfile.TemporaryDirectory() as tmp:
        path = os.path.join(tmp, f"0x{PACK:08x}.rp")
        build_pack(path, data)
        stream = T.Stream(path)
        spots = T.site_spots(stream, site)
        site["crc"] = (zlib.crc32(b"".join(stream.read(d, len(b)) for d, b in spots)),
                       zlib.crc32(b"".join(b for _d, b in spots)))
        check("the stream is parsed (stored blocks, Adler-32 valid)",
              len(stream.blocks) > 10 and stream.stored_adler() == stream.adler() == zlib.adler32(data))
        check("the socket's two heights and the 12 normals around them are the spots",
              sum(len(b) == 2 for _d, b in spots) == 2 and sum(len(b) == 12 for _d, b in spots) == 12, len(spots))
        sites = {"test_socket": site}
        before = md5(path)

        lines = T.apply(tmp, ["test_socket"], dry_run=True, sites=sites)
        check("dry run reports the change and writes nothing",
              any("would flatten" in x for x in lines) and md5(path) == before, lines)

        lines = T.apply(tmp, ["test_socket"], sites=sites)
        new = stream_data(path)
        h = struct.unpack_from("<1089H", new, REC_AT + T.HEIGHTS_AT)
        n = struct.unpack_from("<3f", new, REC_AT + NORMALS_AT + 12 * (7 * 33 + 15))
        check("patched: the stream inflates (Adler-32 rewritten), both vertices at the street, normals (0, 0, 1)",
              h[8 * 33 + 15] == h[8 * 33 + 16] == STREET and n == (0.0, 0.0, 1.0), (h[8 * 33 + 15], n, lines))
        changed = [k for k in range(len(data)) if data[k] != new[k]]
        check("only the site's bytes changed", all(any(d <= k < d + len(b) for d, b in spots) for k in changed),
              len(changed))
        backup = os.path.join(tmp, f"0x{PACK:08x}.rp.terrainfix.json")
        check("backup of the original bytes written", os.path.isfile(backup) and "test_socket" in json.load(open(backup)))

        after = md5(path)
        lines = T.apply(tmp, ["test_socket"], sites=sites)
        check("second run: already flattened, file untouched", md5(path) == after and "already" in " ".join(lines), lines)

        lines = T.apply(tmp, [], sites=sites)
        check("site taken out of the list: restored byte for byte, backup removed",
              md5(path) == before and not os.path.exists(backup), lines)

        other = T.Stream(path)                         # another pack version: one socket height differs
        other.write(REC_AT + T.HEIGHTS_AT + 2 * (8 * 33 + 15), struct.pack("<H", SOCKET + 7))
        other.set_adler(other.adler())
        other.save()
        raw = open(path, "rb").read()
        lines = T.apply(tmp, ["test_socket"], sites=sites)
        check("unexpected bytes: refused, file untouched", "unexpected bytes" in " ".join(lines) and
              open(path, "rb").read() == raw, lines)

        broken = bytearray(raw)
        broken[0x400 + 0x30] ^= 0x01                   # a data byte changed without its Adler-32
        open(path, "wb").write(broken)
        lines = T.apply(tmp, ["test_socket"], sites=sites)
        check("a stream whose Adler-32 does not match is refused", "Adler-32 does not match" in " ".join(lines) and
              open(path, "rb").read() == bytes(broken), lines)

        build_pack(path, data, stored=False)
        lines = T.apply(tmp, ["test_socket"], sites=sites)
        check("a compressed stream is refused", "not a stored deflate stream" in " ".join(lines), lines)

    # 2026-10-28 (map-audit-all.md 11): a site split in two (Gotham Divided's lane exits, one site per team) over a
    # pack that the combined site had patched; the server's read-only probe; a pack the game holds open
    with tempfile.TemporaryDirectory() as tmp:
        path = os.path.join(tmp, f"0x{PACK:08x}.rp")
        build_pack(path, data)
        before = md5(path)
        stream = T.Stream(path)
        base = {"pack": PACK, "record": RECORD, "at": REC_AT, "normals_at": NORMALS_AT, "maps": "test"}
        both = with_crc(stream, dict(base, vertices=[(40, 75), (40, 80), (120, 75), (120, 80)]))
        split = {"west": with_crc(stream, dict(base, vertices=[(40, 75), (40, 80)])),
                 "east": with_crc(stream, dict(base, vertices=[(120, 75), (120, 80)]))}
        check("the two halves' spots are exactly the combined site's",
              sorted(T.site_spots(stream, both)) == sorted(T.site_spots(stream, split["west"])
                                                          + T.site_spots(stream, split["east"])))
        with T.Stream(path, lazy=True) as lazy:
            same = lazy.size == len(data) and lazy.read(REC_AT, 8) == stream.read(REC_AT, 8)
        check("probe of the installed pack: original (lazy read, no whole-file load)",
              T.installed_state(tmp, "west", sites=split) == "original" and same)
        T.apply(tmp, ["both"], sites={"both": both})
        lines = T.apply(tmp, ["west"], sites=split)
        new = stream_data(path)
        west = T.site_spots(T.Stream(path), split["west"])
        changed = [k for k in range(len(data)) if data[k] != new[k]]
        backup = os.path.join(tmp, f"0x{PACK:08x}.rp.terrainfix.json")
        kept = json.load(open(backup)) if os.path.isfile(backup) else {}
        check("split over the combined patch: west kept, east restored from the combined site's backup entry",
              "already flattened" in " ".join(lines) and "restored" in " ".join(lines) and changed
              and all(any(d <= k < d + len(b) for d, b in west) for k in changed), lines)
        check("the backup now holds only the west half (the combined entry is gone)", list(kept) == ["west"], list(kept))
        check("probe after the patch: west flattened, east original",
              T.installed_state(tmp, "west", sites=split) == "patched"
              and T.installed_state(tmp, "east", sites=split) == "original")
        T.apply(tmp, [], sites=split)
        check("both off: the pack is as installed, backup removed", md5(path) == before and not os.path.exists(backup))

        other = os.path.join(tmp, f"0x{PACK + 1:08x}.rp")      # a second pack, written although the first fails
        build_pack(other, data)
        two = dict(split, other=dict(split["west"], pack=PACK + 1))
        save = T.Stream.save

        def locked(self):
            if self.path == path:
                raise PermissionError(13, "the game holds the pack open")
            save(self)
        T.Stream.save = locked
        try:
            lines = T.apply(tmp, ["west", "other"], sites=two)
        finally:
            T.Stream.save = save
        check("a pack that cannot be written is reported, untouched, its backup kept; the next pack is still patched",
              md5(path) == before and "not written" in " ".join(lines) and os.path.isfile(backup)
              and T.installed_state(tmp, "other", sites=two) == "patched", lines)
        lines = T.apply(tmp, ["west", "other"], sites=two)
        check("the rerun with the pack free patches it", T.installed_state(tmp, "west", sites=two) == "patched", lines)

    # 2026-10-29 (fase3-if review: Stream._dspans walked off the block list with an IndexError that no caller handles,
    # so `python ic.py patch` stopped with a traceback): a site past the end of a shorter pack's stream (another version
    # of the pack), or one that straddles its end, is reported and left alone; the server's probe caches "unknown"
    with tempfile.TemporaryDirectory() as tmp:
        path = os.path.join(tmp, f"0x{PACK:08x}.rp")
        build_pack(path, b"\x11" * 0x100)
        before = md5(path)
        short = {"past_the_end": dict(site, at=0x10000), "straddles_the_end": dict(site, at=0xFC)}
        lines = T.apply(tmp, list(short), dry_run=True, sites=short) + T.apply(tmp, list(short), sites=short)
        states = {k: T.installed_state(tmp, k, sites=short) for k in short}
        cached = sorted(v for ck, v in T._STATES.items()
                        if ck[3] in short and ck[0] == os.path.normcase(os.path.abspath(path)))
        check("a site past (or across) the end of a shorter pack's stream: ValueError, reported as not touched in the "
              "dry run and the real run, the pack untouched; the server's probe reads and caches \"unknown\"",
              len([x for x in lines if "past the end of the stream" in x and "not touched" in x]) == 4
              and md5(path) == before and set(states.values()) == {"unknown"} and cached == ["unknown", "unknown"],
              (lines, states, cached))

    # 2026-10-29 (tester report 2026-10-29 16:40, ca-black-strips.md 3): a site redefined with one more vertex over a
    # pack that its earlier version patched: restored from the backup and patched again in one run (dry run: reported,
    # nothing written); taken out: the pack is as installed
    with tempfile.TemporaryDirectory() as tmp:
        path = os.path.join(tmp, f"0x{PACK:08x}.rp")
        build_pack(path, data)
        before = md5(path)
        stream = T.Stream(path)
        base = {"pack": PACK, "record": RECORD, "at": REC_AT, "normals_at": NORMALS_AT, "maps": "test"}
        v1 = {"grow": with_crc(stream, dict(base, vertices=[(40, 75)]))}
        v2 = {"grow": with_crc(stream, dict(base, vertices=[(40, 75), (40, 80)]))}
        stream.close()
        T.apply(tmp, ["grow"], sites=v1)
        v1_md5 = md5(path)
        dry = T.apply(tmp, ["grow"], dry_run=True, sites=v2)
        lines = T.apply(tmp, ["grow"], sites=v2)
        with T.Stream(path, lazy=True) as st:
            ok = T.site_state(st, v2["grow"])[0] == "patched"
        build_pack(os.path.join(tmp, "fresh.bin"), data)
        os.makedirs(os.path.join(tmp, "f"))
        os.replace(os.path.join(tmp, "fresh.bin"), os.path.join(tmp, "f", f"0x{PACK:08x}.rp"))
        T.apply(os.path.join(tmp, "f"), ["grow"], sites=v2)
        check("redefined site over its earlier version: the dry run reports the restore and writes nothing; the run "
              "restores from the backup and flattens the new definition, byte-identical to a fresh install patched once",
              md5(path) != v1_md5 and ok and any("earlier version" in x and "would be restored" in x for x in dry)
              and any("earlier version" in x and "restored from the backup first" in x for x in lines)
              and md5(path) == md5(os.path.join(tmp, "f", f"0x{PACK:08x}.rp")), (dry, lines))
        T.apply(tmp, ["grow"], sites=v1)               # back to the earlier version, then the new one taken out
        lines = T.apply(tmp, [], sites=v2)
        check("the earlier version patched and the new definition taken out: the pack is as installed, no backup",
              md5(path) == before and not os.path.exists(path + ".terrainfix.json"), lines)

    check("[game] terrain_sockets: the old name gotham_divided_lane_exits stands for both teams' sites",
          T.wanted_sites(["gotham_divided_lane_exits", "crime_alley_dampeners"])
          == {"gotham_divided_lane_exits_team1", "gotham_divided_lane_exits_team2", "crime_alley_dampeners"})

    # 2026-10-29 (map-audit-all.md 9.1 / 10.2 / 11): triangles that leave the record's MOPP collision tree
    check("whole raised triangles: a 2 x 2 block 2, an L of three 1, a pair or a lone vertex 0",
          T.whole_triangles({"vertices": [(40, 75), (40, 80), (45, 75), (45, 80)]}) == 2
          and T.whole_triangles({"vertices": [(40, 75), (40, 80), (45, 75)]}) == 1
          and T.whole_triangles({"vertices": [(40, 75), (40, 80)]}) == 0
          and T.whole_triangles({"vertices": [(150, 40)]}) == 0)
    whole = {k: T.whole_triangles(s) for k, s in T.SITES.items() if T.whole_triangles(s)}
    # 2026-10-29 (tester report 2026-10-29 16:40, ca-black-strips.md 3): the lane-turret site now raises (70, 75) too
    check("only coast_city_centre (8: keys 862-865, 926-929) and crime_alley_lane_turret (3, its (70, 75)) lift whole "
          "triangles out of their MOPP tree; a new site that does needs the in-game cursor check of map-audit-all.md 9.1",
          whole == {"coast_city_centre": 8, "crime_alley_lane_turret": 3}, whole)
    # 2026-10-29 (tester report 2026-10-29 12:45, ca-holes-pedestal-turrets.md C1): a rim-only site (a socket vertex
    # stays beside a raised one) writes an upright normal at the raised vertex only with "raised_normals_up"
    with tempfile.TemporaryDirectory() as tmp:
        path = os.path.join(tmp, f"0x{PACK:08x}.rp")
        build_pack(path, b"\x11" * REC_AT + record() + b"\x22" * 5000)
        with T.Stream(path) as st:
            rim = {"pack": PACK, "record": RECORD, "at": REC_AT, "normals_at": NORMALS_AT, "vertices": [(40, 80)]}
            at = REC_AT + NORMALS_AT + 12 * (8 * 33 + 16)
            plain = dict(T.site_spots(st, rim))
            up = dict(T.site_spots(st, dict(rim, raised_normals_up=True)))
        check("rim-only site: the raised vertex keeps the record's normal by default and gets (0, 0, 1) with "
              "raised_normals_up; nothing else differs", at not in plain and up.get(at) == struct.pack("<3f", 0, 0, 1)
              and {d: b for d, b in up.items() if d != at} == plain, (len(plain), len(up)))
    ca_turret = T.SITES["crime_alley_lane_turret"]
    # 2026-10-29 (tester report 2026-10-29 16:40, ca-black-strips.md 3): the centre row's east vertex (70, 75) is
    # raised too (both triangles of the open cell (70-75, 70-75) end there); (60, 75) / (65, 75) stay under the lane
    check("crime_alley_lane_turret raises the rim rows (y 70 / 80) of the lane-turret socket and the centre row's "
          "east vertex (70, 75) only; (60, 75) / (65, 75) stay",
          {v for v in ca_turret["vertices"] if v[1] == 75} == {(70, 75)}
          and all(y in (70, 75, 80) for _x, y in ca_turret["vertices"])
          and T.whole_triangles(ca_turret) == 3 and ca_turret.get("raised_normals_up") is True)
    check("the report names the MOPP caveat for coast_city_centre only",
          "MOPP" in T._describe(T.SITES["coast_city_centre"], [])
          and "MOPP" not in T._describe(T.SITES["crime_alley_dampeners"], []))

    # 2026-10-29 (tester report 2026-10-28 15:00; map-audit-all.md 10.1 / 11): the defaults and the server's lids agree
    from icserver import config as gcfg
    from ics import config as icfg
    from ics.match import maps
    default = gcfg.DEFAULTS["game"]["terrain_sockets"]
    check("[game] terrain_sockets default: Crime Alley (dampeners, lane-turret rim, south alcove rim), Gotham Divided "
          "team 1, Coast City on; GD team 2 (asphalt not installed), GD pits (pods + lids), Tutorial 2 (not run by ics) off",
          T.wanted_sites(default) == {"crime_alley_dampeners", "crime_alley_lane_turret", "crime_alley_south_alcove_rim",
                                      "gotham_divided_lane_exits_team1", "coast_city_centre"}
          and T.wanted_sites(default) <= set(T.SITES), default)
    covers, bad, seen = icfg.DEFAULTS["ics"]["match_socket_covers"], [], set()
    for enc in maps.ENCOUNTERS:
        m, _mode = maps.map_for(enc)
        if m["key"] in seen:
            continue
        seen.add(m["key"])
        lb = (m["landblock"][0] << 8) | m["landblock"][1]
        here = {k: s for k, s in T.SITES.items() if s["pack"] == m["map_pack"] and s["record"] & 0xFFFF == lb}
        for spec in covers.get(m["key"]) or ():
            x, y = spec["pos"][:2]
            under = {k for k, s in here.items() if any(math.hypot(vx - x, vy - y) < 1.0 for vx, vy in s["vertices"])}
            if spec.get("terrain_site") not in (under or {None}):
                bad.append((m["key"], (x, y), spec.get("terrain_site"), sorted(under)))
    check("every [ics] match_socket_covers lid on a site's vertex names that site (terrain_site), so the server leaves "
          "it out once python ic.py patch flattens it, and no lid names a site it does not stand on",
          not bad and {"crime_alley", "gotham_divided", "coast_city"} <= seen, bad)
    check("[ics] match_socket_covers_skip_flat is on by default (a lid on a flattened socket z-fights with the street)",
          icfg.DEFAULTS["ics"]["match_socket_covers_skip_flat"] is True)

    # the built-in sites against the install (read only)
    try:
        from icserver import config
        rp_dir = config.load().game_file("rp")
    except Exception:                                  # noqa: BLE001
        rp_dir = ""
    if os.path.isdir(rp_dir):
        lines = T.apply(rp_dir, list(T.SITES), dry_run=True)
        # 2026-10-29 (ca-black-strips.md 3): a site whose earlier version the install still holds is recognised too
        # (python ic.py patch restores and re-patches it); the server's probe reads it as "unknown" until then
        earlier = {k for k in T.SITES if any(f" {k} (" in x and "earlier version" in x for x in lines)}
        bad = [x for x in lines if not ("would flatten" in x or "already flattened" in x or "earlier version" in x)]
        check(f"install {rp_dir}: all {len(T.SITES)} sites recognised (original, flattened, or an earlier version "
              "flattened)" + (f" [{', '.join(sorted(earlier))}: run python ic.py patch]" if earlier else ""), not bad, bad)
        states = {k: T.installed_state(rp_dir, k) for k in T.SITES}
        check("install: the server's probe reads every site as original or patched (an earlier version: unknown)",
              all(v in ("original", "patched") or (k in earlier and v == "unknown") for k, v in states.items()), states)
        ca = T.SITES["crime_alley_dampeners"]
        if states.get("crime_alley_dampeners") == "original":
            with T.Stream(os.path.join(rp_dir, f"0x{ca['pack']:08x}.rp"), lazy=True) as st:
                ours, fill = dict(T.site_spots(st, ca)), dict(diag_fill_spots(st, ca))
            check("crime_alley_dampeners writes what tools/diag.py --mapa-rellenar wrote in memory (the state the tester "
                  "confirmed 2026-10-28 14:40): the same 4 heights and 24 normals (sign of zero aside)",
                  len(ours) == 28 and sorted(ours) == sorted(fill) and all(same_values(ours[d], fill[d]) for d in ours),
                  (len(ours), len(fill), [hex(d) for d in set(ours) ^ set(fill)]))
        else:
            print("  (Crime Alley's pack is already patched: the diag-fill comparison needs the installed bytes)")
        if "--real" in sys.argv:
            real_round_trip(rp_dir)
    else:
        print("  (no game install found: built-in sites not checked)")
    print(f"\n{sum(results)}/{len(results)} terrain-fix checks")
    return 0 if all(results) else 1


if __name__ == "__main__":
    sys.exit(main())
