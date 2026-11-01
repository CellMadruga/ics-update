"""Havok binary packfiles (hk_2012.2.1-r1, file version 9, 4-byte pointers) -> skeletons.

Packfile: 64-byte header (magic 57E0E057 10C0C010, u32 user tag, u32 version, 4 layout bytes, u32 section count,
contents section / offset, class-name section / offset, version string) then one 48-byte header per section:
char tag[20] | u32 absolute start | local fixups | global fixups | virtual fixups | exports | imports | end (all relative
to the section start). In the data section, local fixups are (src, dst) pairs, global fixups (src, section, dst) and
virtual fixups (object offset, class-name section, name offset): they say where pointers point and which class each
object is. Found in Gaslight Batman's pack 0xA0000076 (2026-10-18); see docs/reverse-engineering.md.
"""
import struct

MAGIC = bytes.fromhex("57E0E05710C0C010")


class Packfile:
    def __init__(self, data, off=0):
        if data[off:off + 8] != MAGIC:
            raise ValueError("not a Havok packfile at %d" % off)
        self.version, = struct.unpack_from("<I", data, off + 12)
        self.layout = data[off + 16:off + 20]
        if self.layout[0] != 4 or self.layout[1] != 1:
            raise ValueError("only 4-byte pointers, little endian are supported")
        count, = struct.unpack_from("<I", data, off + 20)
        self.tag = data[off + 40:off + 56].split(b"\0")[0].decode("ascii", "replace")
        sections = {}
        for i in range(count):
            h = off + 64 + 48 * i
            name = data[h:h + 20].split(b"\0")[0].decode()
            start, local, glob, virt, exports, imports, end = struct.unpack_from("<7I", data, h + 20)
            sections[name] = (i, off + start, local, glob, virt, exports, end)
        names_i, names_at = sections["__classnames__"][:2]
        data_i, base, local, glob, virt, exports, _ = sections["__data__"]
        self.data, self.base = data, base
        self.ptr = {}                                 # field offset -> target offset (both in the data section)
        for p in range(base + local, base + glob, 8):
            src, dst = struct.unpack_from("<2I", data, p)
            if src != 0xFFFFFFFF:
                self.ptr[src] = dst
        for p in range(base + glob, base + virt, 12):
            src, sec, dst = struct.unpack_from("<3I", data, p)
            if src != 0xFFFFFFFF and sec == data_i:
                self.ptr[src] = dst
        self.objects = []                             # (offset, class name)
        for p in range(base + virt, base + exports, 12):
            src, sec, name = struct.unpack_from("<3I", data, p)
            if src != 0xFFFFFFFF and sec == names_i:
                at = names_at + name
                self.objects.append((src, data[at:data.index(b"\0", at)].decode()))

    def of_class(self, name):
        return [o for o, c in self.objects if c == name]

    def u32(self, o):
        return struct.unpack_from("<I", self.data, self.base + o)[0]

    def string(self, field):
        """The C string a hkStringPtr / char* field points to ("" when null)."""
        if field not in self.ptr:
            return ""
        at = self.base + self.ptr[field]
        return self.data[at:self.data.index(b"\0", at)].decode("ascii", "replace")

    def array(self, field):
        """(data offset or None, size) of the hkArray at that field."""
        return self.ptr.get(field), self.u32(field + 4)


def skeletons(pf):
    """[{name, bones: [names], parents: [int], pose: [(t xyz, r xyzw, s xyz)]}] for every hkaSkeleton.

    hkaSkeleton under these layout rules: hkReferencedObject (8 bytes) | name @8 | parentIndices hkArray<hkInt16> @12 |
    bones hkArray<hkaBone> @24 (hkaBone = name ptr + hkBool, 8 bytes) | referencePose hkArray<hkQsTransform> @36
    (48 bytes: translation, rotation quaternion, scale; each a 16-byte vector).
    """
    out = []
    for o in pf.of_class("hkaSkeleton"):
        pa, pn = pf.array(o + 12)
        ba, bn = pf.array(o + 24)
        ra, rn = pf.array(o + 36)
        if not (pn == bn == rn) or bn == 0:
            raise ValueError("hkaSkeleton at %d: array sizes differ (%d %d %d)" % (o, pn, bn, rn))
        d, b = pf.data, pf.base
        parents = list(struct.unpack_from("<%dh" % pn, d, b + pa))
        bones = [pf.string(ba + 8 * i) for i in range(bn)]
        pose = []
        for i in range(rn):
            v = struct.unpack_from("<12f", d, b + ra + 48 * i)
            pose.append((v[0:3], v[4:8], v[8:11]))
        out.append({"name": pf.string(o + 8), "bones": bones, "parents": parents, "pose": pose})
    return out


def find_packfiles(data):
    out, k = [], data.find(MAGIC)
    while k >= 0:
        out.append(k)
        k = data.find(MAGIC, k + 1)
    return out
