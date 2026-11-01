"""The map's navigation mesh (Kynapse / Gameware "BlobAggFile" NavMesh in the map pack) and paths on it.

The client links Kynapse but only snaps a click onto the navmesh; the original server walked the champions and units
along paths on the same mesh (movement-collision-fog-map.md 1.3). Layout read from the Tutorial 1 map pack 0xA0C112CA
(records 0x900113CB / 0x901113CB / 0x902113CB, one per agent class; 2026-10-21):

    u32 1 | f32 radius | f32 height | u32 agent class | 0 | 0 | u32 size | "BlobAggFile" ... "NavMesh"
    from "BlobAggFile" (B): +0x0C 1 = a big-endian blob (Gotham Divided); +0x54 min cell x, y | max cell x, y;
        +0x98 cell count | offset (0x14: the list starts at +0xB0), each (u32 size | u32 offset), the offset
        counted from its own field.
    cell: u32 x | u32 y | 4 x (u32 count | u32 offset); the fourth array lists the floors as (u32 size | u32 offset).
    floor: u32 | u8 x 4 box | (n | off) vertices (u8 x, u8 y) | (n | off) f32 altitudes |
        (n | off) half-edges (u16 pair | u16 start vertex + type bits), three per triangle.
Offsets are counted from the field that holds them. A cell is 1/8 landblock (20 m), a vertex unit 0.2 m (100 per
cell), cell index = landblock x 8 + n.

The walkable floor is rasterised into a grid and paths are A* on it, then smoothed (straight segments along
walkable lines of sight).
"""
import heapq
import array
import math
import struct

LANDBLOCK = 160.0
CELL_METERS = 20.0
UNITS = 100.0


def _arr(data, at, e="<"):
    """(count, absolute offset) of an array whose "count | offset" fields are at `at`."""
    n, off = struct.unpack_from(e + "II", data, at)
    return n, at + 4 + off


def _ref(data, at, e="<"):
    """An element "u32 size | u32 offset" of a list of blobs; the offset is counted from its own field."""
    return _arr(data, at, e)[1]


def blob_endian(data, blob):
    """'>' for a big-endian blob (Gotham Divided: "BlobAggFile" +0x0C = 1, +0x10 = 3 big-endian), else '<'
    (maps-complete.md 2.4, 2026-10-22)."""
    return ">" if struct.unpack_from("<I", data, blob + 0x0C)[0] == 1 else "<"


def parse_blob(data, blob):
    """[(triangle as 3 (x, y, z) in absolute metres)] of one NavMesh blob ("BlobAggFile" at `blob`).

    2026-10-22 (maps-complete.md 0 #4 / 2.4): the NavCell list is the "count | offset" pair at +0x98 (the +0x2C
    word, 19, is something else: GH loaded 558 of 1579 triangles, CC 547 of 1690); Gotham Divided's blobs are
    big-endian (every u32 / u16 / f32 swapped, vertex bytes unchanged; the half-edge's start vertex is the high
    half of its u32 in both byte orders)."""
    e = blob_endian(data, blob)
    cells, at = _arr(data, blob + 0x98, e)
    x0, y0, x1, y1 = struct.unpack_from(e + "4I", data, blob + 0x54)      # the cell box
    tris = []
    for c in range(min(cells, 4096)):
        cell = _ref(data, at + 8 * c, e)
        if not 0 <= cell < len(data) - 0x30:
            continue
        cx, cy = struct.unpack_from(e + "II", data, cell)
        if not (x0 <= cx <= x1 and y0 <= cy <= y1):
            continue
        n_floors, floors = _arr(data, cell + 0x20, e)
        for f in range(min(n_floors, 256)):
            floor = _ref(data, floors + 8 * f, e)
            if not 0 <= floor < len(data) - 0x20:
                continue
            nv, verts = _arr(data, floor + 0x08, e)
            na, alts = _arr(data, floor + 0x10, e)
            nh, edges = _arr(data, floor + 0x18, e)
            if not (0 < nv < 4096 and nh % 3 == 0 and nh < 16384):
                continue
            vs = [struct.unpack_from("<BB", data, verts + 2 * i) for i in range(nv)]
            zs = [struct.unpack_from(e + "f", data, alts + 4 * i)[0] for i in range(na)] if na == nv else [0.0] * nv
            starts = [(struct.unpack_from(e + "I", data, edges + 4 * i)[0] >> 16) & 0x0FFF for i in range(nh)]
            for t in range(nh // 3):
                idx = starts[3 * t:3 * t + 3]
                if any(i >= nv for i in idx):
                    continue
                tris.append(tuple((cx * CELL_METERS + vs[i][0] * CELL_METERS / UNITS,
                                   cy * CELL_METERS + vs[i][1] * CELL_METERS / UNITS, zs[i]) for i in idx))
    return tris


def find_blobs(data):
    """[(agent class, radius, offset of "BlobAggFile")] in a pack's data."""
    out, k = [], data.find(b"BlobAggFile")
    while k >= 0:
        if k >= 0x1C:
            one, radius, _height, cls = struct.unpack_from("<IffI", data, k - 0x1C)
            if one == 1:
                out.append((cls, radius, k))
        k = data.find(b"BlobAggFile", k + 1)
    return out


class NavGrid:
    """Walkable cells of a navmesh around an origin landblock (world coordinates as ics uses them: metres from the
    origin landblock's corner)."""

    def __init__(self, tris, origin_lb, step=0.25):
        self.step = step
        ox, oy = origin_lb[0] * LANDBLOCK, origin_lb[1] * LANDBLOCK
        self.tris = [tuple((x - ox, y - oy, z) for x, y, z in t) for t in tris]
        xs = [p[0] for t in self.tris for p in t] or [0.0]
        ys = [p[1] for t in self.tris for p in t] or [0.0]
        self.x0, self.y0 = min(xs), min(ys)
        self.w = int((max(xs) - self.x0) / step) + 2
        self.h = int((max(ys) - self.y0) / step) + 2
        self.cells = bytearray(self.w * self.h)
        # 2026-10-23 18:40 (tester: the champions walk above the ground): the mesh's height per cell (NaN = none)
        self.heights = array.array("f", [float("nan")]) * (self.w * self.h)
        for t in self.tris:
            self._fill(t)

    def _fill(self, t):
        (ax, ay, az), (bx, by, bz), (cx, cy, cz) = t
        i0, i1 = int((min(ax, bx, cx) - self.x0) / self.step), int((max(ax, bx, cx) - self.x0) / self.step) + 1
        j0, j1 = int((min(ay, by, cy) - self.y0) / self.step), int((max(ay, by, cy) - self.y0) / self.step) + 1
        d = (by - cy) * (ax - cx) + (cx - bx) * (ay - cy)
        if abs(d) < 1e-9:
            return
        for j in range(max(0, j0), min(self.h, j1 + 1)):
            py = self.y0 + (j + 0.5) * self.step
            for i in range(max(0, i0), min(self.w, i1 + 1)):
                px = self.x0 + (i + 0.5) * self.step
                l1 = ((by - cy) * (px - cx) + (cx - bx) * (py - cy)) / d
                l2 = ((cy - ay) * (px - cx) + (ax - cx) * (py - cy)) / d
                if l1 >= -1e-6 and l2 >= -1e-6 and l1 + l2 <= 1 + 1e-6:
                    self.cells[j * self.w + i] = 1
                    k = j * self.w + i
                    if self.heights[k] != self.heights[k]:          # NaN: the first (lowest-indexed) layer wins
                        self.heights[k] = l1 * az + l2 * bz + (1.0 - l1 - l2) * cz

    def height(self, x, y):
        """The mesh's ground height at (x, y), or None off the mesh (the nearest cell within 1 m)."""
        heights = getattr(self, "heights", None)
        if heights is None:
            return None
        i, j = int((x - self.x0) / self.step), int((y - self.y0) / self.step)
        for r in range(0, 5):
            for dj in range(-r, r + 1):
                for di in range(-r, r + 1):
                    if max(abs(di), abs(dj)) != r:
                        continue
                    ii, jj = i + di, j + dj
                    if 0 <= ii < self.w and 0 <= jj < self.h:
                        z = heights[jj * self.w + ii]
                        if z == z:
                            return float(z)
        return None

    def copy(self):
        """A grid of its own for one match (its obstacles do not reach the shared one)."""
        g = NavGrid.__new__(NavGrid)
        g.__dict__.update(self.__dict__)
        g.cells = bytearray(self.cells)
        g._blocked = {}
        return g

    # ---- dynamic obstacles (vehicles, closed gates: they are not in the navmesh) ---------------------
    def block(self, key, cx, cy, half_length, half_width, angle):
        """Make a box (centre, half sizes, angle of its length) unwalkable until unblock(key)."""
        self.unblock(key)
        if not hasattr(self, "_blocked"):
            self._blocked = {}
        ca, sa = math.cos(angle), math.sin(angle)
        r = math.hypot(half_length, half_width)
        i0, j0 = self.cell(cx - r, cy - r)
        i1, j1 = self.cell(cx + r, cy + r)
        cells = []
        for j in range(max(0, j0), min(self.h, j1 + 1)):
            for i in range(max(0, i0), min(self.w, i1 + 1)):
                px, py = self.x0 + (i + 0.5) * self.step - cx, self.y0 + (j + 0.5) * self.step - cy
                if abs(px * ca + py * sa) <= half_length and abs(-px * sa + py * ca) <= half_width:
                    k = j * self.w + i
                    if self.cells[k] == 1:
                        self.cells[k] = 2              # 2 = walkable floor, blocked by an object
                        cells.append(k)
        self._blocked[key] = cells

    def unblock(self, key):
        for k in getattr(self, "_blocked", {}).pop(key, ()):
            if not any(k in c for c in self._blocked.values()):
                self.cells[k] = 1

    # ---- queries --------------------------------------------------------------------------------
    def cell(self, x, y):
        return int((x - self.x0) / self.step), int((y - self.y0) / self.step)

    def walkable(self, x, y):
        i, j = self.cell(x, y)
        return 0 <= i < self.w and 0 <= j < self.h and self.cells[j * self.w + i] == 1

    def nearest(self, x, y, max_r=8.0):
        """The walkable point closest to (x, y) within max_r metres, or None."""
        if self.walkable(x, y):
            return (x, y)
        i0, j0 = self.cell(x, y)
        for r in range(1, int(max_r / self.step) + 1):
            best = None
            for j in range(j0 - r, j0 + r + 1):
                for i in (range(i0 - r, i0 + r + 1) if j in (j0 - r, j0 + r) else (i0 - r, i0 + r)):
                    if 0 <= i < self.w and 0 <= j < self.h and self.cells[j * self.w + i] == 1:
                        px, py = self.x0 + (i + 0.5) * self.step, self.y0 + (j + 0.5) * self.step
                        dd = (px - x) ** 2 + (py - y) ** 2
                        if best is None or dd < best[0]:
                            best = (dd, (px, py))
            if best:
                return best[1]
        return None

    def line_clear(self, a, b, through_objects=False):
        """Every cell on the segment walkable. through_objects: cells blocked by an object (block(): structures,
        vehicles, closed gates; value 2) count as clear, only the navmesh's own holes stop the line."""
        d = math.hypot(b[0] - a[0], b[1] - a[1])
        n = max(1, int(d / (self.step * 0.5)))
        if through_objects:
            ok = (1, 2)

            def clear(x, y):
                i, j = self.cell(x, y)
                return 0 <= i < self.w and 0 <= j < self.h and self.cells[j * self.w + i] in ok
            return all(clear(a[0] + (b[0] - a[0]) * k / n, a[1] + (b[1] - a[1]) * k / n) for k in range(n + 1))
        return all(self.walkable(a[0] + (b[0] - a[0]) * k / n, a[1] + (b[1] - a[1]) * k / n) for k in range(n + 1))

    def path(self, start, goal, max_nodes=200000):
        """[(x, y)] waypoints from start to goal (the goal snapped onto the mesh), or None. The start is the
        champion's position; when it stands just off the mesh it starts from the nearest walkable cell."""
        s = self.nearest(*start, max_r=3.0)
        g = self.nearest(*goal)
        if s is None or g is None:
            return None
        if self.line_clear(s, g):
            return [g]
        si, sj = self.cell(*s)
        gi, gj = self.cell(*g)
        w, cells = self.w, self.cells
        openq = [(0.0, si, sj)]
        came = {(si, sj): None}
        cost = {(si, sj): 0.0}
        nbrs = [(1, 0, 1.0), (-1, 0, 1.0), (0, 1, 1.0), (0, -1, 1.0),
                (1, 1, 1.4142), (1, -1, 1.4142), (-1, 1, 1.4142), (-1, -1, 1.4142)]
        found = False
        while openq and len(came) < max_nodes:
            _f, i, j = heapq.heappop(openq)
            if (i, j) == (gi, gj):
                found = True
                break
            c0 = cost[(i, j)]
            for di, dj, dc in nbrs:
                ni, nj = i + di, j + dj
                if not (0 <= ni < w and 0 <= nj < self.h) or cells[nj * w + ni] != 1:
                    continue
                if di and dj and not (cells[j * w + ni] == 1 and cells[nj * w + i] == 1):
                    continue                      # no corner cutting
                nc = c0 + dc
                if nc < cost.get((ni, nj), 1e18):
                    cost[(ni, nj)] = nc
                    came[(ni, nj)] = (i, j)
                    heapq.heappush(openq, (nc + math.hypot(gi - ni, gj - nj), ni, nj))
        if not found:
            return None
        pts, node = [], (gi, gj)
        while node is not None:
            pts.append((self.x0 + (node[0] + 0.5) * self.step, self.y0 + (node[1] + 0.5) * self.step))
            node = came[node]
        pts.reverse()
        pts[-1] = g
        # string pulling: keep only the points a straight walk cannot skip
        out, anchor, k = [], s, 0
        while k < len(pts):
            far = k
            for m in range(len(pts) - 1, k - 1, -1):
                if self.line_clear(anchor, pts[m]):
                    far = m
                    break
            out.append(pts[far])
            anchor = pts[far]
            k = far + 1
        return out


def load(pack_data, origin_lb, agent_class=None):
    """A NavGrid from a map pack's data: the blob of `agent_class`, else the smallest agent (the champions')."""
    blobs = find_blobs(pack_data)
    if not blobs:
        return None
    chosen = next((b for b in blobs if b[0] == agent_class), None) or min(blobs, key=lambda b: b[1])
    tris = parse_blob(pack_data, chosen[2])
    return NavGrid(tris, origin_lb) if tris else None
