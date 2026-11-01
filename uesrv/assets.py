"""Finds records in the player's own rp packs and converts them. Nothing here is ever written into the repo:
converted files go to the cache folder (data/uesrv_cache, git-ignored)."""
import glob
import hashlib
import os
import struct
import threading
from collections import OrderedDict

from icserver.rp import Pack
from . import meshes, textures


class AssetStore:
    def __init__(self, rp_dir, cache_dir):
        self.rp_dir, self.cache_dir = rp_dir, cache_dir
        self.index = None                  # DID -> [pack file names]
        self.lock = threading.Lock()
        self.packs = OrderedDict()         # small LRU of decompressed packs

    def build_index(self):
        idx = {}
        for path in sorted(glob.glob(os.path.join(self.rp_dir, "*.rp"))):
            with open(path, "rb") as f:
                head = f.read(0x400)
                if head[:4] != b"10PR":
                    continue
                size, count = struct.unpack_from("<II", head, 0xC)
                need, raw, p = 4 * count, bytearray(), 0x400
                while len(raw) < need:
                    f.seek(p)
                    raw += f.read(0x1FFFC)
                    p += 0x20000
            for did in struct.unpack_from("<%dI" % count, raw, 0):
                idx.setdefault(did, []).append(os.path.basename(path))
        self.index = idx
        return len(idx)

    def _pack(self, name):
        if name in self.packs:
            self.packs.move_to_end(name)
            return self.packs[name]
        self.packs[name] = Pack(os.path.join(self.rp_dir, name))
        while len(self.packs) > 2:
            self.packs.popitem(last=False)
        return self.packs[name]

    def texture(self, did):
        """Parsed texture dict for a 0x13 DID, or None."""
        with self.lock:
            if self.index is None:
                self.build_index()
            for name in self.index.get(did, []):
                pack = self._pack(name)
                for off in pack.find_all(did, struct.pack("<I", 2)):
                    tex = textures.parse(pack.data, off)
                    if tex:
                        return tex
        return None

    def mesh(self, did):
        """Parsed static mesh for a 0x17 DID, or None (only verified formats)."""
        with self.lock:
            if self.index is None:
                self.build_index()
            for name in self.index.get(did, []):
                pack = self._pack(name)
                for off in pack.find_all(did):
                    m = meshes.parse(pack.data, off)
                    if m:
                        return m
        return None

    def get(self, kind, did, fmt):
        """(bytes, content_type) or None. Cached on disk by kind/did/fmt."""
        path = os.path.join(self.cache_dir, kind, "%08x.%s" % (did, fmt))
        if os.path.exists(path):
            with open(path, "rb") as f:
                body = f.read()
        else:
            if kind == "texture" and fmt in ("png", "dds"):
                tex = self.texture(did)
                if not tex:
                    return None
                body = textures.to_png(tex) if fmt == "png" else textures.to_dds(tex)
            elif kind == "mesh" and fmt == "obj":
                m = self.mesh(did)
                if not m:
                    return None
                body = meshes.to_obj(m).encode()
            else:
                return None
            os.makedirs(os.path.dirname(path), exist_ok=True)
            with open(path, "wb") as f:
                f.write(body)
        return body, {"png": "image/png", "obj": "text/plain"}.get(fmt, "application/octet-stream")

    @staticmethod
    def etag(body):
        return hashlib.sha1(body).hexdigest()
