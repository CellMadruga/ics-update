"""hkaSplineCompressedAnimation (Havok 2012.2.1, 4-byte pointers) -> per-frame local bone transforms.

Object layout (from the packfiles of Batman's behavior pack 0xA0000122, 2026-10-18):
hkaAnimation: type @8 (3 = spline) | duration f32 @12 | numberOfTransformTracks @16 | numberOfFloatTracks @20 |
extractedMotion ptr @24 | annotationTracks hkArray @28 (16-byte hkaAnnotationTrack: track name ptr + annotations
array; the names are the skeleton's bone names). hkaSplineCompressedAnimation: numFrames @40 | numBlocks @44 |
maxFramesPerBlock @48 | maskAndQuantizationSize @52 | blockDuration @56 | blockInverseDuration @60 |
frameDuration @64 | blockOffsets hkArray<u32> @68 | floatBlockOffsets @80 | transformOffsets @92 | floatOffsets @104 |
data hkArray<u8> @116 | endian @128.

Block (at data + blockOffsets[b]): one 4-byte mask per transform track (quantization types, position / rotation /
scale flags: bits 0-3 static x/y/z/w, bits 4-7 spline), one byte per float track, pad to 4; then per track the
position, rotation and scale, each padded to 4 at its end. A spline vector is u16 control-point count - 1, u8 degree,
u8 knots[n + degree + 2], pad 4, (min, max) f32 per spline component or one f32 per static component, then the
quantized control points (8 or 16 bits per spline component). A spline rotation is the same header, padding to the
quaternion format's alignment, then n + 1 packed quaternions. Static values are stored once. Knots are in frames
from the start of the block; blocks are (maxFramesPerBlock - 1) frames long. B-spline evaluation as in de Boor.
"""
import math
import struct

ROT_FORMATS = {0: ("polar32", 4, 4), 1: ("threecomp40", 5, 1), 2: ("threecomp48", 6, 2),
               3: ("threecomp24", 3, 1), 4: ("straight16", 8, 2), 5: ("uncompressed", 16, 4)}


class _Reader:
    def __init__(self, data, pos, base):
        self.d, self.p, self.base = data, pos, base

    def align(self, n):
        rel = (self.p - self.base) % n
        if rel:
            self.p += n - rel

    def take(self, fmt):
        v = struct.unpack_from("<" + fmt, self.d, self.p)
        self.p += struct.calcsize("<" + fmt)
        return v


def _quat(fmt, raw):
    if fmt == 5:
        return struct.unpack("<4f", raw)
    if fmt == 2:                                   # THREECOMP48: 3 x 15 bits, 2-bit index of the dropped one, sign
        a, b, c = struct.unpack("<3H", raw)
        half, frac = 0x3FFF, 0.000043161
        comps = [((a & 0x7FFF) - half) * frac, ((b & 0x7FFF) - half) * frac, ((c & 0x7FFF) - half) * frac]
        drop = ((b >> 14) & 2) | (a >> 15)
        neg = c >> 15
    elif fmt == 1:                                 # THREECOMP40: 3 x 12 bits, 2-bit index, sign bit
        v = int.from_bytes(raw, "little")
        frac = 0.000345436
        comps = [((v >> s) & 0xFFF) - 2049 for s in (0, 12, 24)]
        comps = [c * frac for c in comps]
        drop = (v >> 36) & 3
        neg = (v >> 38) & 1
    else:
        raise NotImplementedError("rotation format %s" % ROT_FORMATS[fmt][0])
    w = math.sqrt(max(0.0, 1.0 - sum(c * c for c in comps)))
    if neg:
        w = -w
    comps.insert(drop, w)
    return tuple(comps)


def _vector(r, quant, flags, default):
    """Returns ('spline', degree, knots, points [n+1 x 3]) or ('static', xyz)."""
    spline = [(flags >> (4 + i)) & 1 for i in range(3)]
    static = [(flags >> i) & 1 for i in range(3)]
    if any(spline):
        n, = r.take("H")
        degree, = r.take("B")
        knots = r.take("%dB" % (n + degree + 2))
        r.align(4)
        lo, hi, fixed = [0.0] * 3, [0.0] * 3, list(default)
        for i in range(3):
            if spline[i]:
                lo[i], hi[i] = r.take("2f")
            elif static[i]:
                fixed[i], = r.take("f")
        q, scale = ("B", 255.0) if quant == 0 else ("H", 65535.0)
        pts = []
        for _ in range(n + 1):
            p = list(fixed)
            for i in range(3):
                if spline[i]:
                    p[i] = lo[i] + (hi[i] - lo[i]) * r.take(q)[0] / scale
            pts.append(p)
        r.align(4)
        return ("spline", degree, knots, pts)
    value = list(default)
    for i in range(3):
        if static[i]:
            value[i], = r.take("f")
    r.align(4)
    return ("static", value)


def _rotation(r, quant, flags):
    _, size, align = ROT_FORMATS[quant]
    if flags & 0xF0:
        n, = r.take("H")
        degree, = r.take("B")
        knots = r.take("%dB" % (n + degree + 2))
        r.align(align)
        pts = []
        for _ in range(n + 1):
            pts.append(_quat(quant, r.d[r.p:r.p + size]))
            r.p += size
        r.align(4)
        return ("spline", degree, knots, pts)
    if flags & 0x0F:
        r.align(align)
        q = _quat(quant, r.d[r.p:r.p + size])
        r.p += size
        r.align(4)
        return ("static", q)
    return ("static", (0.0, 0.0, 0.0, 1.0))


def _span(degree, t, n_points, knots):
    if t >= knots[n_points]:
        return n_points - 1
    lo, hi = degree, n_points
    mid = (lo + hi) // 2
    while t < knots[mid] or t >= knots[mid + 1]:
        if t < knots[mid]:
            hi = mid
        else:
            lo = mid
        mid = (lo + hi) // 2
    return mid


def _eval(track, t):
    if track[0] == "static":
        return list(track[1])
    _, degree, knots, pts = track
    s = _span(degree, t, len(pts), knots)
    N = [1.0] + [0.0] * degree
    for i in range(1, degree + 1):
        for j in range(i - 1, -1, -1):
            den = knots[s + i - j] - knots[s - j]
            a = (t - knots[s - j]) / den if den else 0.0
            tmp = N[j] * a
            N[j + 1] += N[j] - tmp
            N[j] = tmp
    out = [0.0] * len(pts[0])
    for i in range(degree + 1):
        p = pts[s - i]
        for k in range(len(out)):
            out[k] += p[k] * N[i]
    return out


class SplineAnimation:
    def __init__(self, pf, obj):
        d, b = pf.data, pf.base
        self.duration, = struct.unpack_from("<f", d, b + obj + 12)
        self.tracks, self.float_tracks = struct.unpack_from("<2I", d, b + obj + 16)
        (self.frames, self.blocks, self.max_frames, self.mask_size) = struct.unpack_from("<4I", d, b + obj + 40)
        self.block_duration, _, self.frame_duration = struct.unpack_from("<3f", d, b + obj + 56)
        ta, tn = pf.array(obj + 28)
        self.track_names = [pf.string(ta + 16 * i) for i in range(tn)] if ta is not None else []
        oa, on = pf.array(obj + 68)
        offsets = struct.unpack_from("<%dI" % on, d, b + oa)
        da, dn = pf.array(obj + 116)
        self.data_size = dn
        self.block_tracks, self.block_ends = [], []
        base = b + da
        for blk in range(self.blocks):
            start = base + offsets[blk]
            masks = [struct.unpack_from("<4B", d, start + 4 * t) for t in range(self.tracks)]
            r = _Reader(d, start + 4 * self.tracks + self.float_tracks, base)
            r.align(4)
            tracks = []
            for q, pos_f, rot_f, scl_f in masks:
                pos = _vector(r, q & 3, pos_f, (0.0, 0.0, 0.0))
                rot = _rotation(r, (q >> 2) & 0xF, rot_f)
                scl = _vector(r, (q >> 6) & 3, scl_f, (1.0, 1.0, 1.0))
                tracks.append((pos, rot, scl))
            self.block_tracks.append(tracks)
            self.block_ends.append(r.p - base)
        self.block_offsets = offsets

    def sample(self, frame):
        """[(translation xyz, rotation xyzw, scale xyz)] per track at a frame index (0 .. frames - 1)."""
        per = self.max_frames - 1
        blk = min(int(frame // per), self.blocks - 1)
        t = frame - blk * per
        out = []
        for pos, rot, scl in self.block_tracks[blk]:
            q = _eval(rot, t)
            n = math.sqrt(sum(c * c for c in q)) or 1.0
            out.append((tuple(_eval(pos, t)), tuple(c / n for c in q), tuple(_eval(scl, t))))
        return out


def bone_map(track_names, bones):
    """Skeleton bone index for each track, matched by the name after the rig prefix: Batman's clips name their
    tracks either chr_batman_gaslight_main_<bone> (like the skeleton) or chr_batman_gaslight_<bone>."""
    def key(n):
        return n.rsplit("_main_", 1)[-1] if "_main_" in n else n
    by_suffix = {key(b): i for i, b in enumerate(bones)}
    out = []
    for n in track_names:
        k = key(n)
        hit = by_suffix.get(k)
        if hit is None:                            # chr_batman_gaslight_<bone>: try the longest known suffix
            hit = next((i for s, i in sorted(by_suffix.items(), key=lambda x: -len(x[0])) if n.endswith("_" + s)),
                       None)
        out.append(hit)
    return out


def clip_table(pack):
    """{0x1A DID: duration} from the character's clip table, or {}.

    Found in Batman's behavior pack (2026-10-18, stream offset 810724, just before the behavior-graph packfile):
    u32 n | n x u32 0x1A DIDs | u32 1 | u32 0x1F000002 (the graph's Lua script) | u32 0 | u32 n | n x f32 durations.
    The n entries match the graph's n clip generators in count, not (verifiably) in order, so they give no names.
    Other tables have the same "u32 n | n DIDs | ... | u32 n | n durations" shape with other words in between
    (the sonic-shell VFX clips: n = 3, then 0, 0). Every such table in the pack is merged.
    """
    d, ids, out = pack.data, set(pack.ids), {}
    p, end = 0, len(d) - 8
    while p < end:
        n = struct.unpack_from("<I", d, p)[0]
        if not 1 <= n <= 1000 or p + 4 + 4 * n + 24 > len(d):
            p += 4
            continue
        dids = struct.unpack_from("<%dI" % n, d, p + 4)
        if not all(x >> 24 == 0x1A and x in ids for x in dids):
            p += 4
            continue
        q = p + 4 + 4 * n
        for gap in range(0, 20, 4):
            if struct.unpack_from("<I", d, q + gap)[0] == n and q + gap + 4 + 4 * n <= len(d):
                durs = struct.unpack_from("<%df" % n, d, q + gap + 4)
                if all(0.0 < x < 120.0 for x in durs):
                    out.update(zip(dids, durs))
                    break
        p = q
    return out


def clip_dids(pack, anims):
    """The 0x1A DID of each animation (in stream order): records are stored in the pack's id-list order, so the
    animation packfiles follow the clip-table DIDs in that order. Checked by duration; [] if anything disagrees."""
    table = clip_table(pack)
    order = [i for i in pack.ids if i in table]
    out = []
    for did, anim in zip(order, anims):
        if abs(table[did] - anim.duration) > 0.01:
            return []
        out.append(did)
    return out


def animations(pf):
    return [SplineAnimation(pf, o) for o in pf.of_class("hkaSplineCompressedAnimation")]
