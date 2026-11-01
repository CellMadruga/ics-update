"""Turbine 0x13 texture records -> DDS / PNG.

Record: u32 did | u32 version (2) | u32 mips | u32 0 | u32 flags (3 or 0x103) | u32 width | u32 height |
4s FourCC (DXT1/DXT3/DXT5) | u32 data size | mip chain, largest first. Version 4 records use another
header and are not supported yet (None is returned).
"""
import struct
import zlib

HEADER = 36


def parse(data, off=0):
    """Return dict(did, mips, width, height, fourcc, size, data) or None if this is not a v2 DXT texture."""
    if off + HEADER > len(data):
        return None
    did, ver, mips, zero, flags, w, h = struct.unpack_from("<7I", data, off)
    fourcc = bytes(data[off + 28:off + 32])
    if did >> 24 != 0x13 or ver != 2 or fourcc not in (b"DXT1", b"DXT3", b"DXT5"):
        return None
    if not (1 <= w <= 8192 and 1 <= h <= 8192 and 1 <= mips <= 16):
        return None
    size = struct.unpack_from("<I", data, off + 32)[0]
    blk = 8 if fourcc == b"DXT1" else 16
    if size < ((w + 3) // 4) * ((h + 3) // 4) * blk or off + HEADER + size > len(data):
        return None
    return {"did": did, "mips": mips, "width": w, "height": h, "fourcc": fourcc,
            "size": size, "data": bytes(data[off + HEADER:off + HEADER + size])}


def to_dds(tex):
    flags = 0x1 | 0x2 | 0x4 | 0x1000 | 0x80000 | (0x20000 if tex["mips"] > 1 else 0)
    caps = 0x1000 | (0x400000 if tex["mips"] > 1 else 0)
    head = b"DDS " + struct.pack("<7I", 124, flags, tex["height"], tex["width"], tex["size"], 0, tex["mips"])
    head += b"\0" * 44 + struct.pack("<II4s", 32, 4, tex["fourcc"]) + b"\0" * 20
    head += struct.pack("<I", caps) + b"\0" * 16
    return head + tex["data"]


def _rgb565(c):
    return (((c >> 11) & 31) * 255 // 31, ((c >> 5) & 63) * 255 // 63, (c & 31) * 255 // 31)


def decode_rgba(tex):
    """Decode mip 0 to a bytearray of RGBA (pure Python, fine for a few textures)."""
    w, h, fcc, d = tex["width"], tex["height"], tex["fourcc"], tex["data"]
    out = bytearray(w * h * 4)
    blk = 8 if fcc == b"DXT1" else 16
    bw = (w + 3) // 4
    for by in range((h + 3) // 4):
        for bx in range(bw):
            o = (by * bw + bx) * blk
            alpha = [255] * 16
            if fcc == b"DXT5":
                a0, a1 = d[o], d[o + 1]
                tab = [a0, a1] + ([(a0 * (7 - i) + a1 * i) // 7 for i in range(1, 7)] if a0 > a1
                                  else [(a0 * (5 - i) + a1 * i) // 5 for i in range(1, 5)] + [0, 255])
                bits = int.from_bytes(d[o + 2:o + 8], "little")
                alpha = [tab[(bits >> (3 * i)) & 7] for i in range(16)]
            elif fcc == b"DXT3":
                bits = int.from_bytes(d[o:o + 8], "little")
                alpha = [((bits >> (4 * i)) & 15) * 17 for i in range(16)]
            co = o + (blk - 8)
            c0, c1 = struct.unpack_from("<HH", d, co)
            p0, p1 = _rgb565(c0), _rgb565(c1)
            if c0 > c1 or fcc != b"DXT1":
                pal = [p0, p1, tuple((2 * a + b) // 3 for a, b in zip(p0, p1)),
                       tuple((a + 2 * b) // 3 for a, b in zip(p0, p1))]
                clear = None
            else:
                pal = [p0, p1, tuple((a + b) // 2 for a, b in zip(p0, p1)), (0, 0, 0)]
                clear = 3
            idx = struct.unpack_from("<I", d, co + 4)[0]
            for i in range(16):
                px, py = bx * 4 + (i & 3), by * 4 + (i >> 2)
                if px >= w or py >= h:
                    continue
                k = (idx >> (2 * i)) & 3
                r, g, b = pal[k]
                p = (py * w + px) * 4
                out[p:p + 4] = bytes((r, g, b, 0 if k == clear else alpha[i]))
    return out


def to_png(tex):
    return png_from_rgba(tex["width"], tex["height"], decode_rgba(tex))


def normal_map_rgba(tex):
    """RGBA of a DXT5 normal map stored swizzled (x in alpha, y in green, as Gaslight Batman's 0x130002CB) as a
    standard tangent-space normal map in the glTF / OpenGL convention (green flipped from DirectX)."""
    src = decode_rgba(tex)
    out = bytearray(len(src))
    for i in range(0, len(src), 4):
        x = src[i + 3] / 127.5 - 1.0
        y = src[i + 1] / 127.5 - 1.0
        z = max(0.0, 1.0 - x * x - y * y) ** 0.5
        out[i], out[i + 1], out[i + 2], out[i + 3] = src[i + 3], 255 - src[i + 1], int(z * 127.5 + 127.5), 255
    return out


def png_from_rgba(w, h, rgba):
    raw = b"".join(b"\0" + bytes(rgba[y * w * 4:(y + 1) * w * 4]) for y in range(h))

    def chunk(t, body):
        c = struct.pack(">I", len(body)) + t + body
        return c + struct.pack(">I", zlib.crc32(t + body) & 0xFFFFFFFF)
    return (b"\x89PNG\r\n\x1a\n" + chunk(b"IHDR", struct.pack(">IIBBBBB", w, h, 8, 6, 0, 0, 0))
            + chunk(b"IDAT", zlib.compress(raw, 6)) + chunk(b"IEND", b""))
