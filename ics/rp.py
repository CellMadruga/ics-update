"""Reader for Turbine "10PR" resource packs (rp\\*.rp).

Format as documented by the original project's tools/rplib.py: header at 0
(u32 payload size at 0xC, u32 record count at 0x10); payload from 0x400 in
0x20000-byte blocks whose last 4 bytes are a trailer; payload = count x u32
DIDs followed by one zlib stream with all records concatenated.

Records carry no size table. Instead of guessing where a record ends, this
module answers the questions the server needs ("where is this DID's record
with this header?", "which records reference that DID?") directly on the
decompressed stream.
"""
import bisect
import os
import re
import struct
import zlib


class Pack:
    def __init__(self, path):
        self.path = path
        self.name = os.path.basename(path).lower()
        with open(path, "rb") as f:
            d = f.read()
        if d[:4] != b"10PR":
            raise ValueError(f"{path}: not a 10PR pack")
        size, count = struct.unpack_from("<II", d, 0xC)
        raw = bytearray()
        p, end = 0x400, 0x400 + size
        while p < end:
            raw += d[p:min(p + 0x1FFFC, end)]
            p += 0x20000
        self.ids = list(struct.unpack_from("<%dI" % count, raw, 0))
        self.data = zlib.decompress(bytes(raw[4 * count:]))

    def find_all(self, did, header=b""):
        """Offsets where the u32 DID is followed by the given header bytes."""
        pat = struct.pack("<I", did) + header
        out, k = [], self.data.find(pat)
        while k >= 0:
            out.append(k)
            k = self.data.find(pat, k + 1)
        return out

    def record_starts(self):
        """Best-effort record starts (DID in list order), sorted by offset."""
        starts, pos = [], 0
        for did in self.ids:
            k = self.data.find(struct.pack("<I", did), pos)
            if k < 0:
                k = self.data.find(struct.pack("<I", did))
            if k >= 0:
                starts.append((k, did))
                pos = k + 4
        starts.sort()
        return starts


class PackSet:
    """Lazy access to the game's rp folder (only the packs that are asked for)."""

    def __init__(self, rp_dir):
        self.rp_dir = rp_dir
        self._cache = {}

    def pack(self, pack_id):
        name = f"0x{pack_id:08x}.rp" if isinstance(pack_id, int) else pack_id
        if name not in self._cache:
            self._cache[name] = Pack(os.path.join(self.rp_dir, name))
        return self._cache[name]


# ---- encounter layouts ---------------------------------------------------------------

_ENTRY = re.compile(rb"([\x03-\x40])\x00\x00\x00([0-9A-Za-z_]{3,64})\x00{0,3}(...\x2e)", re.S)
# lookahead so that overlapping candidates are all tried
_POS = re.compile(rb"(?=([\x00-\xff])\x00\x00\x00([\x00-\xff])\x00\x00\x00([\x00-\xff])\x00\x00\x00(.{12})(.{16}))", re.S)


def _positions(seg):
    """Position structs: u32 cell | u32 landblock x | u32 landblock y | f32 x,y,z |
    quaternion (w, x, y, z). Accepted only when the quaternion is normalised."""
    out = []
    for m in _POS.finditer(seg):
        x, y, z = struct.unpack("<fff", m.group(4))
        q = struct.unpack("<4f", m.group(5))
        norm = sum(v * v for v in q)
        if 0.98 < norm < 1.02 and all(abs(v) < 4000 for v in (x, y, z)) and abs(z) > 1:
            out.append({"cell": m.group(1)[0], "lb": (m.group(2)[0], m.group(3)[0]),
                        "xyz": (x, y, z), "quat": q})
    return out


def layout_entries(pack, max_span=4096):
    """Named placements: u32 name length | name (padded to 4) | u32 world-state
    DID (0x2e...), followed by properties and position structs. Found in the
    encounter layout records (DID prefix 0x1d) and in cinematics (0x35).
    Returns [{record, name, wstate, positions}]; positions[0] is the spawn
    point, further ones a patrol path. 'record' is the enclosing record as
    far as the pack's record list can tell."""
    starts = pack.record_starts()
    offs = [o for o, _ in starts]
    found = [(m.start(), m.group(2).decode(), struct.unpack("<I", m.group(3))[0])
             for m in _ENTRY.finditer(pack.data) if len(m.group(2)) == m.group(1)[0]]
    entries = []
    for j, (pos, name, ws) in enumerate(found):
        stop = min(found[j + 1][0] if j + 1 < len(found) else len(pack.data), pos + max_span)
        i = bisect.bisect_right(offs, pos) - 1
        record = starts[i][1] if i >= 0 else 0
        entries.append({"record": record, "name": name, "wstate": ws,
                        "positions": _positions(pack.data[pos:stop]),
                        "props": _placement_props(pack.data, pos)})
    return entries


def _placement_props(data, pos):
    """A placement's own properties, after its world state: u32 x3 | u32 count | entries "key | key | value";
    an array (0x954 = linked 0x1D templates) is "key | key | count | count x (element key 0x462 | DID)".
    Seen: 0x100007A2 side (1 the drones, 3 doors and the power core, none the thugs), 0x6B3 / 0x6B4 scale."""
    out = {}
    k = pos + 4 + ((data[pos] + 3) & ~3) + 4   # u32 length | name (padded) | u32 world state
    try:
        n = struct.unpack_from("<I", data, k + 12)[0]
        p = k + 16
        for _ in range(min(n, 16)):
            key, word = struct.unpack_from("<II", data, p)
            if (word & 0xBFFFFFFF) != key or not (key < 0x4000 or 0x10000000 <= key < 0x10010000):
                break
            value = struct.unpack_from("<I", data, p + 8)[0]
            if key == 0x954:
                out[key] = [struct.unpack_from("<I", data, p + 12 + 8 * e + 4)[0] for e in range(min(value, 8))]
                p += 12 + 8 * value
            else:
                out[key] = value
                p += 12
    except struct.error:
        pass
    return out


def variants_for_wstates(pack):
    """{world state DID: character variant DID}: a variant 0x40xxxxxx has a
    twin 0x49xxxxxx (same low bits) whose properties name its world state."""
    out = {}
    twins = [d for d in pack.ids if d >> 24 == 0x49]
    for twin in twins:
        for k in pack.find_all(twin):
            head = pack.data[k + 4:k + 8]
            if head not in (b"\x03\x00\x00\x00", b"\x04\x00\x00\x00", b"\x00\x00\x00\x00"):
                continue
            seg = pack.data[k:k + 4000]
            for j in range(8, len(seg) - 4, 4):
                v = struct.unpack_from("<I", seg, j)[0]
                if v >> 24 == 0x2E and v & 0xFFFFFF < 0x100000:
                    out.setdefault(v, 0x40000000 | (twin & 0xFFFFFF))
                    break
            break
    return out


ENTITY_WSTATE_PROP = 0x510   # property of an entity twin (0x49...) naming its world state


def entity_classes_for(pack, wstates):
    """{world state: entity class 0x40xxxxxx} for the given world states.

    A placeable object (a door, a destructible vehicle, a character) is an
    entity 0x40xxxxxx whose twin 0x49xxxxxx has property 0x510 = its world
    state 0x2e... (e.g. Door 0x49000b0f -> 0x2e0010f3). Creating the bare world
    state builds an object without the entity's model, so it is invisible."""
    twins = sorted(d for d in pack.ids if d >> 24 == 0x49)
    twin_set = set(twins)
    out = {}
    for ws in wstates:
        pat = struct.pack("<III", ENTITY_WSTATE_PROP, ENTITY_WSTATE_PROP, ws)
        k = pack.data.find(pat)
        while k >= 0 and ws not in out:
            # owner: the nearest preceding twin DID (records are a few KB at most)
            lo = max(0, k - 8000)
            j = k - 4
            while j >= lo:
                if pack.data[j + 3] == 0x49:
                    v = struct.unpack_from("<I", pack.data, j)[0]
                    if v in twin_set and pack.data[j + 4:j + 8] in (b"\0\0\0\0", b"\x03\0\0\0", b"\x04\0\0\0"):
                        out[ws] = 0x40000000 | (v & 0xFFFFFF)
                        break
                j -= 1
            k = pack.data.find(pat, k + 1)
    return out


# ---- scriptlet tables (records 0x1D) ---------------------------------------------------------------

# A scriptlet table's body does not start with its DID, so the pack's record list cannot place it. Body:
# "u32 n bases | n x base table DID | u32 1 | u32 count | count x scriptlet"; scriptlet = "key | 0 | n props |
# props | n actions | ...". The bodies of the unplaced records between two placed ones come in list order
# (static analysis of the tutorial packs, 2026-10-21: door 0x1D00073F = Object_Closed, Object_Open; base 0x1D000385).
_TABLE_ANCHOR = re.compile(rb"(?=\x01\x00\x00\x00[\x00-\xff][\x00\x01]\x00\x00[\x00-\xff]{4}\x00\x00\x00\x00"
                           rb"[\x00-\x08]\x00\x00\x00)", re.S)


def _is_key(k):
    return 0x10000000 <= k < 0x10010000 or 1 <= k < 0x40


def _is_scriptlet(w, i, n):
    if i + 3 >= n or not (_is_key(w[i]) and w[i + 1] == 0 and w[i + 2] <= 8):
        return False
    p = i + 3
    for _ in range(w[i + 2]):
        if p + 1 >= n:
            return False
        a, b = w[p], w[p + 1]
        if (b & 0xBFFFFFFF) != a:
            return False
        p += 2 if b == a | 0x40000000 else 3
    return p + 1 < n and 0 < w[p] <= 40 and 0 < w[p + 1] < 0x40


def _words(data, k, n):
    n = max(0, min(n, (len(data) - k) // 4))
    return list(struct.unpack_from("<%dI" % n, data, k)) if n else []


def _table_headers(data, lo, hi):
    """[(offset, bases, count)] of the scriptlet table bodies in data[lo:hi]."""
    out = []
    for m in _TABLE_ANCHOR.finditer(data, lo, hi):
        j = m.start()
        cnt = struct.unpack_from("<I", data, j + 4)[0]
        if not 1 <= cnt <= 300:
            continue
        w = _words(data, j + 8, 60)
        if not _is_scriptlet(w + [0] * 4, 0, len(w)):
            continue
        for nb in range(0, 5):
            s = j - 4 - 4 * nb
            if s < lo:
                break
            head = _words(data, s, nb + 1)
            if head[0] == nb and all(b >> 24 == 0x1D for b in head[1:]):
                out.append((s, head[1:], cnt))
                break
    out.sort()
    return [h for t, h in enumerate(out) if not (t + 1 < len(out) and out[t + 1][0] - h[0] <= 32)]


def _table_keys(data, pos, nbases, cnt, end):
    w = _words(data, pos, (end - pos) // 4)
    n = len(w)
    first = 1 + nbases + 2
    if first >= n:
        return []
    keys, i = [w[first]], first + 1
    while i < n - 3 and len(keys) < cnt:
        if (w[i] not in keys and w[i] >= 0x10000000 and w[i - 1] == 0 and not (w[i - 3] == 0x17 and w[i - 2] == 1)
                and _is_scriptlet(w, i, n)):
            keys.append(w[i])
        i += 1
    return keys


def _placed_starts(pack):
    """Offset of each listed record whose body starts with its DID (None for the others): the longest chain of
    occurrences that keeps the list order (a reference to a DID elsewhere in the pack is not its start)."""
    wanted = set(pack.ids)
    occ = {}
    data = pack.data
    for a in range(4):
        n = (len(data) - a) // 4
        for i, v in enumerate(struct.unpack_from("<%dI" % n, data, a)):
            if v in wanted:
                occ.setdefault(v, []).append(a + 4 * i)
    tails, tails_node, parent = [], [], {}
    for i, did in enumerate(pack.ids):
        for o in sorted(occ.get(did, ()), reverse=True):
            j = bisect.bisect_left(tails, o)
            parent[(i, o)] = tails_node[j - 1] if j > 0 else None
            if j == len(tails):
                tails.append(o)
                tails_node.append((i, o))
            else:
                tails[j], tails_node[j] = o, (i, o)
    chain, node = {}, tails_node[-1] if tails_node else None
    while node is not None:
        chain[node[0]] = node[1]
        node = parent[node]
    return [chain.get(i) for i in range(len(pack.ids))]


def script_tables(pack):
    """{table DID: {"bases": [DIDs], "keys": [scriptlet keys]}} for every scriptlet table of the pack."""
    starts = _placed_starts(pack)
    ids, data, out = pack.ids, pack.data, {}
    i, n = 0, len(ids)
    while i < n:
        if starts[i] is not None:
            i += 1
            continue
        j = i
        while j < n and starts[j] is None:
            j += 1
        tables = [ids[t] for t in range(i, j) if ids[t] >> 24 == 0x1D]
        if tables:
            lo = next((starts[t] for t in range(i - 1, -1, -1) if starts[t] is not None), 0)
            hi = starts[j] if j < n else len(data)
            heads = _table_headers(data, lo, hi)
            for t, did in enumerate(tables[:len(heads)]):
                pos, bases, cnt = heads[t]
                end = heads[t + 1][0] if t + 1 < len(heads) else hi
                out[did] = {"bases": bases, "keys": _table_keys(data, pos, len(bases), cnt, end)}
        i = j
    return out


_NAME = re.compile(rb"(?=([\x00-\xff][\x00-\xff][\x00-\x0f]\x10)([\x02-\x7f])\x00\x00\x00)", re.S)
_NAME_CHARS = re.compile(rb"[A-Za-z0-9_./ \-]+")


def name_tables(pack):
    """Runs of "u32 key | u32 length | name (padded to 4)" entries: [{key: name}], largest first. In pack
    0xA0000038 the largest is the scriptlet key table 0x33000000."""
    data, runs, cur, last = pack.data, [], None, -100
    for m in _NAME.finditer(data):
        if m.start() < last:
            continue
        length = m.group(2)[0]
        st = m.start() + 8
        name = data[st:st + length]
        if not _NAME_CHARS.fullmatch(name):
            continue
        if cur is None or m.start() - last > 12:
            cur = {}
            runs.append(cur)
        cur.setdefault(struct.unpack("<I", m.group(1))[0], name.decode())
        last = st + length
    return sorted((r for r in runs if len(r) > 20), key=len, reverse=True)
