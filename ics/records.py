"""Generic reader of the game's property records ("did | 0 | count | entries", world states "did | 7 | .entity |
0 | count | entries").

An entry is "u32 key | u32 key (| 0x40000000 = present without a value) | value", the value read by the property's
kind (catalog properties.tsv, the client's own descriptors): a table is "u32 | u32 count | entries", an array
"u32 count | count x (element key | value)", a string "u32 0 | u32 token | u32 table | u32 | u32" (a reference into
a string table 0x2B..., never the text itself), an IID two words, an ASCII name "u32 length | bytes" (padded to 4),
a vector three f32, a 0x14 DID two words, anything else one word.
"""
import struct

KIND_IID, KIND_ENUM, KIND_F32, KIND_TABLE, KIND_ARRAY = 0x07, 0x08, 0x09, 0x0B, 0x0C
KIND_BITFIELD, KIND_STRING, KIND_INT, KIND_U32, KIND_DID, KIND_BOOL = 0x0D, 0x0E, 0x10, 0x13, 0x15, 0x16
# found in the encounter templates (maps-encounters.md): an ASCII name, a 3-float vector, a DID padded to 8 bytes
KIND_ASCII, KIND_VECTOR, KIND_DID64 = 0x01, 0x06, 0x14
NO_VALUE = 0x40000000


class Reader:
    def __init__(self, data, pos, kinds):
        self.d, self.p, self.kinds = data, pos, kinds

    def u32(self):
        v = struct.unpack_from("<I", self.d, self.p)[0]
        self.p += 4
        return v

    def value(self, key):
        kind = self.kinds.get(key)
        if kind is None:
            raise ValueError(f"no kind known for property {key:#x}")
        if kind == KIND_TABLE:
            self.u32()
            return kind, self.entries(self.u32())
        if kind == KIND_ARRAY:
            out = []
            for _ in range(self.u32()):
                ekey = self.u32()
                ekind, evalue = self.value(ekey)
                out.append((ekey, ekind, evalue))
            return kind, out
        if kind == KIND_STRING:
            _, token, table, _, _ = (self.u32() for _ in range(5))
            return kind, (token, table)
        if kind == KIND_IID:
            lo, hi = self.u32(), self.u32()
            return kind, lo | hi << 32
        if kind == KIND_DID64:
            did, _zero = self.u32(), self.u32()
            return kind, did
        if kind == KIND_ASCII:
            n = self.u32()
            text = self.d[self.p:self.p + n].decode("latin-1")
            self.p += (n + 3) & ~3
            return kind, text
        if kind == KIND_VECTOR:
            return kind, tuple(struct.unpack("<f", struct.pack("<I", self.u32()))[0] for _ in range(3))
        if kind == KIND_F32:
            return kind, struct.unpack("<f", struct.pack("<I", self.u32()))[0]
        return kind, self.u32()

    def entries(self, n):
        out = []
        for _ in range(n):
            key, word = self.u32(), self.u32()
            if (word & 0xBFFFFFFF) != key:
                raise ValueError(f"entry {key:#x}: bad key echo {word:#x}")
            if word == key | NO_VALUE:
                out.append((key, None, None))
                continue
            kind, value = self.value(key)
            out.append((key, kind, value))
        return out


def read_at(data, pos, kinds):
    """Entries of the record whose header starts at pos, or None."""
    try:
        a = struct.unpack_from("<I", data, pos + 4)[0]
        start = pos + 20 if a == 7 else pos + 8
        r = Reader(data, start, kinds)
        n = r.u32()
        if not 0 < n < 400:
            return None
        return r.entries(n)
    except (ValueError, struct.error):
        return None


def get(entries, key, default=None):
    for k, _kind, v in entries or ():
        if k == key:
            return v
    return default


def get_all(entries, key):
    return [v for k, _kind, v in entries or () if k == key]


def as_dict(entries):
    """{key: value} (nested tables and arrays stay lists of entries)."""
    return {k: v for k, _kind, v in entries or ()}
