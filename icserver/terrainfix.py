"""Black terrain sockets flattened in the game's own map packs (part of `python ic.py patch`; local, never distributed).

docs/re-notes/map-audit-all.md 2 and 6. A landblock's ground is the 33 x 33 height grid of its record 0x80......
(vertex (x, y) = index (x / 5) * 33 + y / 5, 5 m apart, z = u16 * 2000 / 65535): the client builds the render mesh
(0x712860) and the collision mesh (0x53BB00) from it and takes the vertex normals from the same record (0x4DF920
array at object +0xC4). A few vertices sit 20-250 m under the street, a "socket" for a model this install lacks or
the client never draws, and the funnel shows as a black polygon. Raising Crime Alley's four dampener-socket vertices
to the street in the running client removed both black octagons (tools/diag.py --mapa-rellenar, tester 2026-10-28
14:40); this module writes the same change into the pack, so no diag is needed.

A map pack keeps its records in one zlib stream made only of stored (uncompressed) deflate blocks ("78 01"; the 4-byte
trailers of the file's 0x20000-byte blocks are lengths, countdown-keymap-gaps.md 2.3), so a same-length edit of a
record is a byte edit of the file plus the stream's Adler-32 (big-endian, right after the last block), which inflate
checks. Every site is verified first: the stream is all stored blocks with a valid Adler-32, the record's DID and
array counts are where expected, and the CRC-32 of the bytes the site rewrites is the original's (apply) or the
patched one (already applied / revert); anything else is reported and left alone. The original bytes of each site go
to <pack>.terrainfix.json next to the pack before its first write; a site taken out of [game] terrain_sockets is
written back from it on the next `python ic.py patch` (by offset, so the original bytes of a site that a later
version split or renamed are found too).

The game server never reads terrain heights; it only asks installed_state() (a read-only probe that loads a few KB of
the pack, not the whole file) whether a site is flattened, so it leaves out the cover it would put over that socket
([ics] match_socket_covers "terrain_site", map-audit-all.md 11).
"""
import bisect
import json
import math
import os
import struct
import zlib

BLOCK, BLOCK_DATA = 0x20000, 0x1FFFC     # file block and its payload (the last 4 bytes are a length trailer)
GRID = 33                                # vertices per side of a landblock (5 m apart)
HEIGHTS_AT = 0x450                       # did | 0x441 | 1089 flag bytes | pad | 0x441 | u16 heights (0x5490D0)
M_PER_UNIT = 2000.0 / 65535.0            # z = u16 * 2000 * [0x185F0FC] (0x53BB00 / 0x712860)
STEEP_M = 3.0                            # a normal next to another drop this deep is left as the record has it

# key -> pack, landblock record, decompressed offset of the record, record offset of its normals array (each after
# a u32 0x441), the socket vertices (x, y in metres in the landblock: each connected group is raised to the median of
# the vertices around it), and the CRC-32 of the bytes the site rewrites (its heights, then the normals of every
# vertex around them, in index order) before and after (written with an underscore, 0x7DB4_EFBF: CRC values, not
# game IDs, so tests/test_catalog.py's ID scan skips them). The pack files are the same in the server install and
# the Steam copy (md5 of 0xa0c112ba.rp 35e55d3e..., 2026-10-28).
SITES = {
    # 2026-10-28 15:00 (tester: the dampener sockets' black octagons were gone with diag --mapa-rellenar, C): two
    # vertices per side at 179.96 m in the 199.98 m street, under the type-3 markers 0x2E0011A9 / 0x2E0011A8
    "crime_alley_dampeners": {
        "pack": 0xA0C112BA, "record": 0x800113BB, "at": 0x38E1A44, "normals_at": 0x81F8,
        "vertices": [(40, 75), (40, 80), (120, 75), (120, 80)], "crc": (0x7DB4_EFBF, 0x8BB7_F049),
        "maps": "Crime Alley v AI, 1vAI Tutorial, Clash 1v1 / 2v2"},
    # 2026-10-29 (tester report 2026-10-29 12:45: "in the centre there are sections in black"; recording 12-09-37.mp4
    # 6:30-13:00, ca-holes-pedestal-turrets.md C1, C frames + data): two black strips on the sidewalks east of team 1's
    # lane turret, x 70-75 at y 80-85 and y 65-70. The lane-turret socket (60-70, 70-80) + (75, 80) is at 0 m in the
    # 199.98 m street (team-1 side only); the street pieces cover its middle but not those sidewalks. Only the socket's
    # rim rows y 70 / 80 are raised (the y 75 row stays under the lane cover), so no triangle gets three raised corners
    # and the record's MOPP collision tree still bounds every one (whole_triangles = 0, unlike coast_city_centre)
    # 2026-10-29 (tester report 2026-10-29 16:40, screenshot 49.webp; ca-black-strips.md, C georeference + heights):
    # the south strip stayed black at x 70-75, y 70-71.7 because both terrain triangles of the cell (70-75, 70-75) end
    # at the centre-row vertex (70, 75), still at 0 m; the lane mesh covers that cell only north of y 71.7. (70, 75)
    # is raised too (was the rim rows only, CRC 0xF375_46A7 -> 0x7534_9554; a pack patched by that version is
    # restored from its backup and re-patched in the same run). (60, 75) / (65, 75) stay at 0 m under the lane mesh
    # and the turret, so at most 3 triangles get three raised corners (whole_triangles 3: if the cursor or a
    # ground-target ring drops through the ground right by the blue lane turret, report it, map-audit-all.md 9.1)
    "crime_alley_lane_turret": {
        "pack": 0xA0C112BA, "record": 0x800113BB, "at": 0x38E1A44, "normals_at": 0x81F8, "raised_normals_up": True,
        "vertices": [(60, 70), (65, 70), (70, 70), (60, 80), (65, 80), (70, 80), (75, 80), (70, 75)],
        "crc": (0xFD6B_E526, 0x3979_96D8), "maps": "Crime Alley v AI, 1vAI Tutorial, Clash 1v1 / 2v2 (team-1 lane turret)"},
    # 2026-10-29 (tester report 2026-10-29 14:40, screenshot 46.webp: a black band on the south sidewalk under the south
    # stealth tile, x ~79-87 at y ~66-70; gh-freeze-holes-picking.md H2, C heights): the south alcove (85, 50-65),
    # (90, 55-60) lies at 0 m in the 199.98 m street, and its rim vertex (85, 65) opens the sidewalk quads x 80-90,
    # y 65-70. The props there stand at street level (0x2E00026D (82.3, 68.6, 199.98), 0x2E000481 (87.1, 69.6, 200.9),
    # 0x2E0006E1 (90.8, 61.2, 199.98)), so the ground belongs at 200. Only that rim vertex is raised (the alcove's
    # inside stays, no triangle gets three raised corners: whole_triangles 0); (80, 65) at 195 m stays (its quad holds
    # 0x2E000B59 at 197.24 m)
    "crime_alley_south_alcove_rim": {
        "pack": 0xA0C112BA, "record": 0x800113BB, "at": 0x38E1A44, "normals_at": 0x81F8, "raised_normals_up": True,
        "vertices": [(85, 65)], "crc": (0xBD45_DDC9, 0xF230_ADFD),
        "maps": "Crime Alley v AI, 1vAI Tutorial, Clash 1v1 / 2v2 (south sidewalk by the south stealth field)"},
    # the six base lane exits (one vertex each at 199.98 m in the 249.97 m street; black squares GD-1 / GD-2 of the
    # 2026-10-25 16:12 video; only a 1.2 m debris static 0x2E000EE1 stands on each), P: same cause as Crime Alley's.
    # 2026-10-28 (tester report 2026-10-28 15:00; map-audit-all.md 10.1 / 11, C: the render index buffer holds
    # y_i * 33 + x_i, every batch's triangles then span exactly its stored bbox): one site per team. Team 1's exits are
    # in render batch 2 (layer types 0x7 / 0xD: textures 0x13000097 / 98, 0x130023B4 / B3, in GD's zone pack
    # 0xA00000FC), so flat street is drawn there. Team 2's are in batch 1 (asphalt 0xE / 0xF: 0x130007AC-A9, in none
    # of GD's packs): flattened they would show unbound, dark ground, so that site is off and the server keeps its
    # lids there. The two together were fase3-if's first "gotham_divided_lane_exits" (ALIASES)
    "gotham_divided_lane_exits_team1": {
        "pack": 0xA0C11AD2, "record": 0x80011BD3, "at": 0x5950C, "normals_at": 0x800C,
        "vertices": [(40, 150), (35, 125), (10, 120)], "crc": (0x5492_9DF6, 0xA5E1_7FE7),
        "maps": "Gotham Divided (5v5, v AI, 5vAI), team 1's base"},
    "gotham_divided_lane_exits_team2": {
        "pack": 0xA0C11AD2, "record": 0x80011BD3, "at": 0x5950C, "normals_at": 0x800C,
        "vertices": [(150, 40), (125, 35), (120, 10)], "crc": (0xBF41_DA05, 0x6F0E_1927),
        "maps": "Gotham Divided (5v5, v AI, 5vAI), team 2's base"},
    # the two neutral pits (one vertex at 0 m each; black diamond GD-3): the phase pods rise there and the server puts
    # the lid 0x2E0003F0 on them ([ics] match_socket_covers), so not in the default list (P)
    "gotham_divided_pits": {
        "pack": 0xA0C11AD2, "record": 0x80011BD3, "at": 0x5950C, "normals_at": 0x800C,
        "vertices": [(55, 55), (105, 105)], "crc": (0xABA7_B767, 0x1D49_4C5E),
        "maps": "Gotham Divided (5v5, v AI, 5vAI)"},
    # the 3 x 3 vertices at 0 m in the middle (black polygon CC-2 of the 2026-10-25 video; occupant unknown,
    # map-object-census.md 3.1)
    "coast_city_centre": {
        "pack": 0xA0C122E2, "record": 0x800123E3, "at": 0x57BAF54, "normals_at": 0x8C9C,
        "vertices": [(x, y) for x in (75, 80, 85) for y in (65, 70, 75)], "crc": (0x2E6B_93F3, 0x50EE_BE42),
        "maps": "Coast City (5v5, Crisis Labs, v AI)"},
    # 2026-10-28 (map-audit-all.md 10.6, C): Tutorial 2 (0x40000A81, "Tutorial -- Intermediate") has Crime Alley's
    # dampener socket on the team-1 side only (two vertices at 179.96 m in the 199.98 m street; its only occupant,
    # 0x2E00119F, has no geometry). Not in the default list: ics runs no Tutorial 2 flow (ics/match/maps.py, encounters/)
    "tutorial_2_dampener": {
        "pack": 0xA0C112C2, "record": 0x800113C3, "at": 0x472D570, "normals_at": 0x80FC,
        "vertices": [(40, 75), (40, 80)], "crc": (0xB697_2663, 0xE058_3DCF),
        "maps": "Tutorial 2 (Intermediate)"},
}

# names a [game] terrain_sockets list may still use -> the sites they stand for
ALIASES = {"gotham_divided_lane_exits": ("gotham_divided_lane_exits_team1", "gotham_divided_lane_exits_team2")}


def wanted_sites(enabled, sites=None):
    """The site keys a [game] terrain_sockets list asks for (aliases expanded; unknown names kept, apply reports
    them)."""
    sites = SITES if sites is None else sites
    out = set()
    for k in enabled or ():
        out.update(ALIASES[k] if k not in sites and k in ALIASES else (k,))
    return out


class _FileView:
    """Slices of an open file, read on demand (Stream(..., lazy=True): a read-only look at a few records)."""

    def __init__(self, f):
        self.f = f

    def __getitem__(self, s):
        self.f.seek(s.start)
        return self.f.read(s.stop - s.start)


class Stream:
    """A pack file's zlib stream of stored deflate blocks, read and written through the file's own block layout.
    lazy=True reads only what is asked (block headers and records) and cannot write or check the Adler-32."""

    def __init__(self, path, lazy=False):
        self.path, self._file = path, None
        if lazy:
            self._file = open(path, "rb", buffering=0)
            self.raw = _FileView(self._file)
        else:
            with open(path, "rb") as f:
                self.raw = bytearray(f.read())
        try:
            self._parse()
        except Exception:
            self.close()
            raise

    def close(self):
        if self._file is not None:
            self._file.close()
            self._file = None

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        self.close()

    def _parse(self):
        head = bytes(self.raw[0:0x14])
        if head[:4] != b"10PR":
            raise ValueError("not a 10PR pack")
        _size, count = struct.unpack_from("<II", head, 0xC)
        q = 4 * count                                     # the DID list, then the stream
        if self._get(q, 2) != b"\x78\x01":
            raise ValueError("the stream is not a stored deflate stream (78 01)")
        q += 2
        self.blocks, d = [], 0                            # (decompressed start, payload offset of the data, length)
        while True:
            head = self._get(q, 5)
            if len(head) < 5:
                raise ValueError(f"the stream ends at payload {q:#x} before its last block")
            n, nn = struct.unpack("<HH", head[1:5])
            if head[0] & 0x06 or n ^ nn != 0xFFFF:
                raise ValueError(f"a compressed deflate block at payload {q:#x}: cannot be patched in place")
            self.blocks.append((d, q + 5, n))
            q, d = q + 5 + n, d + n
            if head[0] & 1:
                break
        self.size, self.adler_at = d, q
        self.starts = [b[0] for b in self.blocks]

    @staticmethod
    def file_offset(q):
        """File offset of payload byte q."""
        return 0x400 + (q // BLOCK_DATA) * BLOCK + q % BLOCK_DATA

    def _spans(self, q, n):
        while n > 0:
            k = min(n, BLOCK_DATA - q % BLOCK_DATA)
            yield self.file_offset(q), k
            q, n = q + k, n - k

    def _get(self, q, n):
        return b"".join(bytes(self.raw[o:o + k]) for o, k in self._spans(q, n))

    def _put(self, q, data):
        p = 0
        for o, k in self._spans(q, len(data)):
            self.raw[o:o + k] = data[p:p + k]
            p += k

    def _dspans(self, d, n):
        """(payload offset, length) pieces of decompressed bytes d .. d + n. 2026-10-29 (fase3-if review: a site past
        the end of a shorter pack's stream walked off the block list with an IndexError that no caller handles):
        bytes outside the stream raise ValueError, which site_spots / apply report as "not touched" and
        installed_state as "unknown" (another version of the pack)."""
        if d < 0 or n < 0 or d + n > self.size:
            raise ValueError(f"bytes {d:#x}+{n:#x} are past the end of the stream ({self.size:#x}): another version "
                             "of the pack?")
        i = bisect.bisect_right(self.starts, d) - 1
        while n > 0:
            start, q, length = self.blocks[i]
            k = min(n, start + length - d)
            yield q + d - start, k
            d, n, i = d + k, n - k, i + 1

    def read(self, d, n):
        return b"".join(self._get(q, k) for q, k in self._dspans(d, n))

    def write(self, d, data):
        p = 0
        for q, k in self._dspans(d, len(data)):
            self._put(q, data[p:p + k])
            p += k

    def adler(self):
        a = 1
        for _start, q, n in self.blocks:
            for o, k in self._spans(q, n):
                a = zlib.adler32(memoryview(self.raw)[o:o + k], a)
        return a

    def stored_adler(self):
        return struct.unpack(">I", self._get(self.adler_at, 4))[0]

    def set_adler(self, value):
        self._put(self.adler_at, struct.pack(">I", value))

    def save(self):
        """Whole file through a temporary copy (an interrupted write never leaves half a pack; a pack the running
        game holds open makes os.replace fail, and nothing changes)."""
        tmp = self.path + ".tmp"
        try:
            with open(tmp, "wb") as f:
                f.write(self.raw)
            os.replace(tmp, self.path)
        except OSError:
            if os.path.exists(tmp):
                os.remove(tmp)
            raise


def site_spots(stream, site):
    """[(decompressed offset, new bytes)] the site writes, in a fixed order: the raised heights, then the normals
    around them (central differences of the raised grid; a normal with a drop of STEEP_M m or more next to it stays as
    the record has it). Raises ValueError when the record is not where the site expects it."""
    rec = site["at"]
    if stream.read(rec, 8) != struct.pack("<II", site["record"], GRID * GRID):
        raise ValueError(f"record {site['record']:#010x} is not at {rec:#x} (another version of the pack?)")
    for at in (HEIGHTS_AT - 4, site["normals_at"] - 4):
        if stream.read(rec + at, 4) != struct.pack("<I", GRID * GRID):
            raise ValueError(f"record {site['record']:#010x}: no 0x441 array count at +{at:#x}")
    h = list(struct.unpack("<%dH" % (GRID * GRID), stream.read(rec + HEIGHTS_AT, 2 * GRID * GRID)))
    cells = {(x // 5, y // 5) for x, y in site["vertices"]}
    new = {}
    for group in _groups(cells):
        ring = sorted(h[(i + a) * GRID + j + b] for i, j in group for a in (-1, 0, 1) for b in (-1, 0, 1)
                      if (i + a, j + b) not in group and 0 <= i + a < GRID and 0 <= j + b < GRID)
        for i, j in group:
            new[(i, j)] = ring[len(ring) // 2]
    h2 = list(h)
    for (i, j), v in new.items():
        h2[i * GRID + j] = v
    spots = [(rec + HEIGHTS_AT + 2 * (i * GRID + j), struct.pack("<H", v)) for (i, j), v in sorted(new.items())]
    around = sorted({(i + a, j + b) for i, j in new for a in (-1, 0, 1) for b in (-1, 0, 1)
                     if 0 < i + a < GRID - 1 and 0 < j + b < GRID - 1})
    for i, j in around:
        z = h2[i * GRID + j] * M_PER_UNIT
        xp, xm, yp, ym = (h2[(i + 1) * GRID + j] * M_PER_UNIT, h2[(i - 1) * GRID + j] * M_PER_UNIT,
                          h2[i * GRID + j + 1] * M_PER_UNIT, h2[i * GRID + j - 1] * M_PER_UNIT)
        if any(abs(v - z) >= STEEP_M for v in (xp, xm, yp, ym)):
            if site.get("raised_normals_up") and (i, j) in new:
                # 2026-10-29 (tester report 2026-10-29 12:45, ca-holes-pedestal-turrets.md C1): a raised vertex that keeps
                # a socket vertex beside it (a site that raises only the socket's rim) gets an upright normal; the
                # record's own one leans into the pit and would shade the new street dark
                spots.append((rec + site["normals_at"] + 12 * (i * GRID + j), struct.pack("<3f", 0.0, 0.0, 1.0)))
            continue
        dx, dy = (xp - xm) / 10.0, (yp - ym) / 10.0
        n = math.sqrt(dx * dx + dy * dy + 1.0)
        spots.append((rec + site["normals_at"] + 12 * (i * GRID + j),
                      struct.pack("<3f", 0.0 - dx / n, 0.0 - dy / n, 1.0 / n)))     # no -0.0
    return spots


def _groups(cells):
    out, seen = [], set()
    for c in sorted(cells):
        if c in seen:
            continue
        group, todo = set(), [c]
        seen.add(c)
        while todo:
            i, j = todo.pop()
            group.add((i, j))
            for a in (-1, 0, 1):
                for b in (-1, 0, 1):
                    n = (i + a, j + b)
                    if n in cells and n not in seen:
                        seen.add(n)
                        todo.append(n)
        out.append(group)
    return out


def whole_triangles(site):
    """How many terrain triangles have all three corners raised by the site: 2 per grid cell whose four corners are
    socket vertices, up to 1 per cell with three (its split diagonal decides; counted). 2026-10-29 (map-audit-all.md
    9.1 / 10.2, C geometry): such a triangle leaves the z range the record's embedded Havok MOPP tree was built for
    (the client attaches record +0xD8 to the collision mesh it rebuilds from the heights, 0x53BCB2 -> 0x539D90), so a
    collision query the tree prunes (a box or a short ray at street level) can miss it; a site whose triangles all keep
    a ring vertex stays inside the tree. Coast City's centre: 8 (MOPP keys 862-865, 926-929), the other sites 0."""
    cells = {(x // 5, y // 5) for x, y in site["vertices"]}
    n = 0
    for i, j in {(a - da, b - db) for a, b in cells for da in (0, 1) for db in (0, 1)}:
        k = sum((i + a, j + b) in cells for a in (0, 1) for b in (0, 1))
        n += 2 if k == 4 else 1 if k == 3 else 0
    return n


def site_state(stream, site, spots=None):
    """("original" | "patched" | "unknown", spots, CRC-32 of the current bytes, CRC-32 of the new bytes)."""
    spots = spots if spots is not None else site_spots(stream, site)
    cur = zlib.crc32(b"".join(stream.read(d, len(b)) for d, b in spots))
    new = zlib.crc32(b"".join(b for _d, b in spots))
    orig_crc, new_crc = site["crc"]
    if cur == new_crc and new == new_crc:
        return "patched", spots, cur, new
    if cur == orig_crc and new == new_crc:
        return "original", spots, cur, new
    return "unknown", spots, cur, new


_STATES = {}


def installed_state(rp_dir, key, sites=None):
    """The state of one site in the installed pack ("original" | "patched" | "unknown"; None when the pack is not
    there), read without loading the pack (its block headers and the record's arrays only) and cached per pack file
    (path, size, mtime): what ics asks before it places a cover over a socket ([ics] match_socket_covers
    "terrain_site", map-audit-all.md 11)."""
    site = (SITES if sites is None else sites)[key]
    path = os.path.join(rp_dir, f"0x{site['pack']:08x}.rp")
    try:
        st = os.stat(path)
    except OSError:
        return None
    ck = (os.path.normcase(os.path.abspath(path)), st.st_size, st.st_mtime_ns, key, site["at"], tuple(site["crc"]))
    if ck not in _STATES:
        try:
            with Stream(path, lazy=True) as stream:
                _STATES[ck] = site_state(stream, site)[0]
        except (OSError, ValueError, struct.error, IndexError):
            _STATES[ck] = "unknown"
    return _STATES[ck]


def _backup_path(pack_path):
    return pack_path + ".terrainfix.json"


def apply(rp_dir, enabled, dry_run=False, sites=None):
    """Bring every site to its wanted state: enabled -> patched, the others -> original (from the backup). Returns
    report lines; dry_run only reports what would change. `sites` overrides SITES (tests).

    The backup ({site: [[decompressed offset, original bytes as hex], ...]}) is read by offset, so the entry of a site
    this version no longer has (fase3-if's first "gotham_divided_lane_exits", now one site per team) still restores
    the sites that cover its bytes; such an entry is dropped once every byte of it belongs to a current site in a known
    state. A pack that cannot be written (the game holds it open) is reported, and the other packs go on."""
    sites = SITES if sites is None else sites
    wanted = wanted_sites(enabled, sites)
    out = [f"terrain sockets: unknown site {k!r} in [game] terrain_sockets (known: {', '.join(sorted(sites))})"
           for k in sorted(wanted - set(sites))]
    by_pack = {}
    for key, site in sites.items():
        by_pack.setdefault(site["pack"], []).append(key)
    for pack_id, keys in sorted(by_pack.items()):
        name = f"0x{pack_id:08x}.rp"
        path = os.path.join(rp_dir, name)
        if not os.path.isfile(path):
            out.append(f"{name}: not found, terrain sockets {', '.join(keys)} skipped")
            continue
        try:
            stream = Stream(path)
        except ValueError as e:
            out.append(f"{name}: {e}; terrain sockets not touched")
            continue
        if stream.stored_adler() != stream.adler():
            out.append(f"{name}: the stream's Adler-32 does not match its data (modified elsewhere?); not touched")
            continue
        backup_file = _backup_path(path)
        try:
            with open(backup_file, encoding="utf-8") as f:
                backup = json.load(f)
        except (OSError, ValueError):
            backup = {}
        originals = {}                               # (offset, length) -> original bytes (hex), from every entry
        for rows in backup.values():
            for d, hx in rows:
                originals.setdefault((int(d), len(hx) // 2), hx)
        final, known, changed = {}, set(), False     # site -> (state after this run, spots); spots of known sites
        for key in keys:
            site = sites[key]
            label = f"{name} {key} ({site['maps']})"
            try:
                state, spots, cur, new = site_state(stream, site)
            except (ValueError, struct.error, IndexError) as e:
                out.append(f"{label}: {e}; not touched")
                continue
            earlier = False
            if state == "unknown":
                # 2026-10-29 (tester report 2026-10-29 16:40, ca-black-strips.md 3): a site redefined with more vertices
                # over a pack an earlier version of it patched. The backup holds the installed bytes of every offset it
                # wrote and the bytes it never touched are still the installed ones: when that mix has the site's
                # original CRC, those bytes go back first (in memory; a dry run never saves) and the site is handled
                # from the installed state, in this run
                rows = [originals.get((d, len(b))) or stream.read(d, len(b)).hex() for d, b in spots]
                if zlib.crc32(b"".join(bytes.fromhex(hx) for hx in rows)) == site["crc"][0]:
                    for (d, _b), hx in zip(spots, rows):
                        stream.write(d, bytes.fromhex(hx))
                    state, spots, cur, new = site_state(stream, site)
                    earlier = state == "original"
                    changed = changed or (earlier and not dry_run)
            if state == "unknown":
                out.append(f"{label}: unexpected bytes (crc {cur:#010x}, expected {site['crc'][0]:#010x} original or "
                           f"{site['crc'][1]:#010x} patched); not touched")
                continue
            if earlier:
                out.append(f"{label}: an earlier version of this site was flattened; "
                           f"{'would be restored' if dry_run else 'restored'} from the backup first")
            known.update((d, len(b)) for d, b in spots)
            if key not in wanted and state == "original":
                if dry_run:
                    out.append(f"{label}: off (as installed)")
                final[key] = ("original", spots)
            elif key in wanted and state == "patched":
                out.append(f"{label}: already flattened")
                final[key] = ("patched", spots)
            elif key in wanted:
                out.append(f"{label}: {'would flatten' if dry_run else 'flattened'} {_describe(site, spots)}")
                final[key] = ("patched", spots)
                if not dry_run:
                    for d, b in spots:
                        originals[(d, len(b))] = stream.read(d, len(b)).hex()     # the CRC said: installed bytes
                        stream.write(d, b)
                    changed = True
            else:                                    # flattened, no longer wanted: the installed bytes back
                rows = [originals.get((d, len(b))) for d, b in spots]
                if None in rows or zlib.crc32(b"".join(bytes.fromhex(h) for h in rows)) != site["crc"][0]:
                    out.append(f"{label}: patched, but {os.path.basename(backup_file)} has no matching original "
                               "bytes; not restored")
                    final[key] = ("patched", spots)
                    continue
                out.append(f"{label}: {'would be restored' if dry_run else 'restored'} "
                           "(not in [game] terrain_sockets)")
                final[key] = ("original", spots)
                if not dry_run:
                    for (d, _b), hx in zip(spots, rows):
                        stream.write(d, bytes.fromhex(hx))
                    changed = True
        if dry_run:
            continue
        keep = {}                                    # the backup after this run
        for key, (state, spots) in final.items():
            if state == "patched":
                rows = [[d, originals[(d, len(b))]] for d, b in spots if (d, len(b)) in originals]
                if len(rows) == len(spots):
                    keep[key] = rows
                elif key in backup:
                    keep[key] = backup[key]
        for key, rows in backup.items():
            if key not in final and (key in sites or any((int(d), len(hx) // 2) not in known for d, hx in rows)):
                keep[key] = rows                     # a site in an unknown state, or bytes no current site covers
        if changed:
            pre = dict(backup)
            pre.update(keep)
            _write_json(backup_file, pre)            # every original byte (the restored sites' too) before saving
            stream.set_adler(stream.adler())
            try:
                stream.save()
            except OSError as e:
                out.append(f"{name}: not written ({e.__class__.__name__}: {e}); close the game and run python ic.py "
                           "patch again (the backup keeps the installed bytes)")
                continue
        if keep and keep != backup:
            _write_json(backup_file, keep)
        elif not keep and os.path.exists(backup_file):
            os.remove(backup_file)
        if changed:
            out.append(f"{name}: written (Adler-32 {stream.stored_adler():#010x}"
                       + (f", backup {os.path.basename(backup_file)})" if keep else ", as installed again)"))
    return out


def _write_json(path, data):
    with open(path + ".tmp", "w", encoding="utf-8") as f:
        json.dump(data, f, indent=1)
    os.replace(path + ".tmp", path)


def _describe(site, spots):
    n = sum(1 for _d, b in spots if len(b) == 12)
    whole = whole_triangles(site)
    return (f"record {site['record']:#010x}: " + ", ".join(f"({x}, {y})" for x, y in site["vertices"])
            + f" -> street level, {n} normals"
            + (f"; {whole} triangles leave the record's MOPP collision tree (map-audit-all.md 9.1: if the cursor or a "
               "ground-target ring drops through there in game, take this site out)" if whole else ""))
