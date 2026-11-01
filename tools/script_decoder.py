"""Decode the server scripts (records 0x34) exactly, by running the client's own Unpack code under emulation.

The client exe contains the script VM's classes (docs/reverse-engineering.md, "The script VM in the client exe").
This tool maps the exe into a Unicorn x86 emulator, runs the static initializers that register the node types,
creates the record object with the factory registered for database type 7 (rva 0x9e0619: create 0x44b960, unpack
0x9d80a0 -> 0x44ece0) and lets the client's Unpack read the record from the player's pack. A hook on every node
class's Unpack attributes each field read to the node being read, which gives an exact tree:

    script -> nodes -> child nodes, each with the raw fields it read (offset, size, reader address, value)

Differences between the packed records and the client's reader (found 2026-10-20):
  - every read occupies a multiple of 4 bytes in the packs (a u8 takes 4 bytes, a 11-char string 12);
  - variable blocks carry their default values right after the type list; the client build does not read them
    (server-only field). They are skipped up to the name table "1 | 0 | n | n x (hash, slot)" and kept in the tree;
  - the variable-block validator 0x45a300 needs the game's string pool, which is not set up here: it is bypassed.

    python tools\\script_decoder.py tree 0x34000782       print one script's tree
    python tools\\script_decoder.py all                   decode every 0x34 record -> data\\script_trees\\*.json

Needs `pip install unicorn capstone` and the game install. The trees are derived from the player's packs and stay
out of git (data/script_trees/).
"""
import json
import os
import re
import struct
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from unicorn import Uc, UC_ARCH_X86, UC_MODE_32, UC_HOOK_CODE, UcError  # noqa: E402
from unicorn.x86_const import (UC_X86_REG_EAX, UC_X86_REG_ECX, UC_X86_REG_ESP, UC_X86_REG_EIP,  # noqa: E402
                               UC_X86_REG_EBP, UC_X86_REG_FS, UC_X86_REG_GDTR, UC_X86_REG_SS, UC_X86_REG_DS,
                               UC_X86_REG_ES, UC_X86_REG_GS)

OUT_DIR = os.path.join(ROOT, "data", "script_trees")

# client exe addresses (VA, image base 0x400000)
READ = 0xAFAE80              # CByteStream::Read(n) -> pointer or 0
FAIL = 0xAF8710              # stream error (HRESULT)
CREATE_SCRIPT = 0x44B960     # database type 7 (0x34 records): create
UNPACK_SCRIPT = 0x9D80A0     # database type 7: unpack(obj, stream) -> 0x44ece0
VAR_OPTIONAL = 0x45A940      # optional object reader; called from the variable block at 0x45aa67
VAR_OPTIONAL_RET = 0x45AA6C
VAR_TYPE_READ = 0x4590D4     # return address of the per-element u32 read of the variable type array
VAR_VALIDATE = 0x45A300      # variable block check (string pool)
REG_FIRST, REG_LAST = 0x13A0000, 0x13D0000   # static initializers that register the node types
EXPR_REGISTRY = 0x45FB30     # returns the expression type registry
REGISTRY_INSERT = 0x45FA20   # registry.insert(&{type, factory, size})
# Expression types 0xC (x - 1) and 0x10 (short-circuit or): their static initializers store the type id with
# "mov eax, imm" (id == object size), so the store pattern below misses them (fix B, script-nodes-complete.md 1;
# 2026-10-22). Initializer -> (type, factory).
EXTRA_INITIALIZERS = {0x13A67D0: (0x0C, 0x465F20), 0x13A6710: (0x10, 0x465D20)}
# Compact count reader 0x421430: one byte < 0x80, else a longer form. The packs store a whole word (fix D).
COUNT_READ, COUNT_READ_LONG = 0x421444, 0x421465

STUBS, HEAP, STACK, BUF, STREAM, TEB, GDT = (0x7F000000, 0x40000000, 0x3F000000, 0x60000000, 0x61000000,
                                             0x62000000, 0x63000000)
RET = 0x7F0FFFF0
# words a server-only variable default takes, by variable type (fix C; type 0xA is 1 or 3, see _on_var_optional)
DEFAULT_SIZES = {7: 2, 8: 2, 9: 3, 0xC: 5, 0xD: 2, 0xE: 2}


class Emulator:
    def __init__(self, exe_path):
        b = self.b = open(exe_path, "rb").read()
        pe = struct.unpack_from("<I", b, 0x3C)[0]
        nsec = struct.unpack_from("<H", b, pe + 6)[0]
        opt = struct.unpack_from("<H", b, pe + 20)[0]
        self.base = struct.unpack_from("<I", b, pe + 52)[0]
        size_img = struct.unpack_from("<I", b, pe + 80)[0]
        uc = self.uc = Uc(UC_ARCH_X86, UC_MODE_32)
        uc.mem_map(self.base, (size_img + 0xFFF) & ~0xFFF)
        uc.mem_write(self.base, b[:0x1000])
        self.text = None
        for i in range(nsec):
            o = pe + 24 + opt + 40 * i
            vs, va, rs, rp = struct.unpack_from("<4I", b, o + 8)
            uc.mem_write(self.base + va, b[rp:rp + min(rs, vs or rs)])
            if b[o:o + 5] == b".text":
                self.text = (self.base + va, rp)
        for start, size in ((STUBS, 0x100000), (HEAP, 0x8000000), (STACK, 0x200000), (BUF, 0x1000000),
                            (STREAM, 0x10000), (TEB, 0x10000), (GDT, 0x1000)):
            uc.mem_map(start, size)
        self.heap = HEAP + 0x1000
        self.stubs = {}
        self._imports(pe)
        self._segments()
        # TLS allocator: a struct of function pointers, +0 = alloc(self, size, count, tag, flags)
        self.alloc_obj = self.malloc(0x80)
        for k in range(32):
            self.w32(self.alloc_obj + 4 * k, self._stub(self._alloc if k == 0 else (lambda e: 0)))
        uc.hook_add(UC_HOOK_CODE, self._on_stub, begin=STUBS, end=STUBS + 0x100000)
        uc.hook_add(UC_HOOK_CODE, self._on_read, begin=READ, end=READ)
        uc.hook_add(UC_HOOK_CODE, self._on_fail, begin=FAIL, end=FAIL)
        self.reads, self.read_esp, self.failed = [], [], False

    # memory
    def malloc(self, n):
        n = max(min(n, 0x400000), 4)
        p = (self.heap + 15) & ~15
        self.heap = p + n
        self.uc.mem_write(p, b"\0" * n)
        return p

    def u32(self, a):
        return struct.unpack("<I", self.uc.mem_read(a, 4))[0]

    def w32(self, a, v):
        self.uc.mem_write(a, struct.pack("<I", v & 0xFFFFFFFF))

    def arg(self, i):
        return self.u32(self.uc.reg_read(UC_X86_REG_ESP) + 4 + 4 * i)

    def _segments(self):
        def entry(base, limit, access, flags):
            return struct.pack("<Q", (limit & 0xFFFF) | ((base & 0xFFFFFF) << 16) | ((access & 0xFF) << 40)
                               | (((limit >> 16) & 0xF) << 48) | ((flags & 0xF) << 52) | (((base >> 24) & 0xFF) << 56))
        self.uc.mem_write(GDT + 8, entry(TEB, 0xFFFFF, 0x92, 0xC))       # fs -> fake TEB (SEH chain)
        self.uc.mem_write(GDT + 16, entry(0, 0xFFFFF, 0x92, 0xC))        # flat 32-bit data
        self.uc.reg_write(UC_X86_REG_GDTR, (0, GDT, 0xFFF, 0))
        self.uc.reg_write(UC_X86_REG_FS, 1 << 3)
        for r in (UC_X86_REG_SS, UC_X86_REG_DS, UC_X86_REG_ES, UC_X86_REG_GS):
            self.uc.reg_write(r, 2 << 3)
        self.w32(TEB, 0xFFFFFFFF)

    # imports: everything becomes a Python stub
    def _stub(self, fn, stdcall=0):
        addr = STUBS + 16 * len(self.stubs)
        self.uc.mem_write(addr, b"\xc3")
        self.stubs[addr] = (fn, stdcall)
        return addr

    def _imports(self, pe):
        def rd(rva, n):
            return bytes(self.uc.mem_read(self.base + rva, n))
        known = {
            "TlsGetValue": (lambda e: e.alloc_obj, 4), "TlsSetValue": (lambda e: 1, 8), "TlsAlloc": (lambda e: 5, 0),
            "malloc": (lambda e: e.malloc(e.arg(0)), 0), "??2@YAPAXI@Z": (lambda e: e.malloc(e.arg(0)), 0),
            "??_U@YAPAXI@Z": (lambda e: e.malloc(e.arg(0)), 0), "calloc": (lambda e: e.malloc(e.arg(0) * e.arg(1)), 0),
            "scalable_malloc": (lambda e: e.malloc(e.arg(0)), 0),
            "scalable_aligned_malloc": (lambda e: e.malloc(e.arg(0)), 0),
            "scalable_calloc": (lambda e: e.malloc(e.arg(0) * e.arg(1)), 0),
            "realloc": (lambda e: e._realloc(), 0), "scalable_realloc": (lambda e: e._realloc(), 0),
            "scalable_msize": (lambda e: 0x10000, 0), "HeapAlloc": (lambda e: e.malloc(e.arg(2)), 12),
            "HeapFree": (lambda e: 1, 12), "GetProcessHeap": (lambda e: 1, 0),
            "memcpy": (lambda e: e._copy(), 0), "memmove": (lambda e: e._copy(), 0), "memset": (lambda e: e._fill(), 0),
            "DecodePointer": (lambda e: e.arg(0), 4), "EncodePointer": (lambda e: e.arg(0), 4),
            "__dllonexit": (lambda e: e.arg(0), 0), "_onexit": (lambda e: e.arg(0), 0),
            "_errno": (lambda e: e.malloc(4), 0), "GetCurrentThreadId": (lambda e: 1, 0),
            "InterlockedIncrement": (lambda e: e._add(1), 4), "InterlockedDecrement": (lambda e: e._add(-1), 4),
            "EnterCriticalSection": (lambda e: 0, 4), "LeaveCriticalSection": (lambda e: 0, 4),
            "InitializeCriticalSection": (lambda e: 0, 4), "SetLastError": (lambda e: 0, 4),
            "QueryPerformanceCounter": (lambda e: 0, 4),
        }
        d = struct.unpack_from("<I", self.b, pe + 128)[0]
        while True:
            oft, _, _, name_rva, ft = struct.unpack("<5I", rd(d, 20))
            if not name_rva:
                break
            k = 0
            while True:
                thunk = struct.unpack("<I", rd((oft or ft) + 4 * k, 4))[0]
                if not thunk:
                    break
                name = "" if thunk & 0x80000000 else rd(thunk + 2, 80).split(b"\0")[0].decode()
                fn, stdcall = known.get(name, (lambda e: 0, 0))
                self.w32(self.base + ft + 4 * k, self._stub(fn, stdcall))
                k += 1
            d += 20

    def _alloc(self, e):
        return e.malloc(min(e.arg(1), 0x100000) or 4)

    def _realloc(self):
        old, n = self.arg(0), self.arg(1)
        p = self.malloc(n)
        if old and n <= 0x400000:
            try:
                self.uc.mem_write(p, bytes(self.uc.mem_read(old, n)))
            except UcError:
                pass
        return p

    def _copy(self):
        d, s, n = self.arg(0), self.arg(1), self.arg(2)
        if 0 < n <= 0x400000:
            self.uc.mem_write(d, bytes(self.uc.mem_read(s, n)))
        return d

    def _fill(self):
        d, c, n = self.arg(0), self.arg(1), self.arg(2)
        if 0 < n <= 0x400000:
            self.uc.mem_write(d, bytes([c & 0xFF]) * n)
        return d

    def _add(self, delta):
        a = self.arg(0)
        v = (self.u32(a) + delta) & 0xFFFFFFFF
        self.w32(a, v)
        return v

    # hooks
    def _return(self, value, pop):
        esp = self.uc.reg_read(UC_X86_REG_ESP)
        self.uc.reg_write(UC_X86_REG_EAX, value & 0xFFFFFFFF)
        self.uc.reg_write(UC_X86_REG_EIP, self.u32(esp))
        self.uc.reg_write(UC_X86_REG_ESP, esp + 4 + pop)

    def _on_stub(self, uc, addr, size, _):
        if addr in self.stubs:
            fn, stdcall = self.stubs[addr]
            self._return(fn(self), stdcall)

    def _on_read(self, uc, addr, size, _):
        esp = uc.reg_read(UC_X86_REG_ESP)
        ret, n = self.u32(esp), self.u32(esp + 4)
        cur, end = self.u32(STREAM + 0xC), self.u32(STREAM + 0x34)
        if ret == COUNT_READ and cur + 4 <= end and self.u32(cur) >= 0x80:
            # fix D (2026-10-22): a count >= 0x80 is a whole word in the packs; hand the client the prefix of its
            # u32 form (0xE0) and the word itself on the next read
            self.w32(STREAM + 0x100, 0xE0)
            self.long_count = True
            self._return(STREAM + 0x100, 4)
            return
        if ret == COUNT_READ_LONG and getattr(self, "long_count", False):
            self.long_count = False
            self.w32(STREAM + 0xC, cur + 4)
            self.reads.append((cur - BUF, 4, COUNT_READ))
            self.read_esp.append(esp)
            self._return(cur, 4)
            return
        if cur + n <= end:
            self.w32(STREAM + 0xC, cur + ((n + 3) & ~3))      # packed records: every read padded to 4 bytes
            result = cur
        else:
            result = 0
        self.reads.append((cur - BUF, n, ret))
        self.read_esp.append(esp)
        self._return(result, 4)

    def _on_fail(self, uc, addr, size, _):
        self.failed = True
        uc.emu_stop()

    def call(self, fn, this=0, args=(), limit=50_000_000):
        self.uc.mem_write(RET, b"\xf4")
        sp = STACK + 0x1F0000
        for a in reversed(list(args)):
            sp -= 4
            self.w32(sp, a)
        sp -= 4
        self.w32(sp, RET)
        self.uc.reg_write(UC_X86_REG_ESP, sp)
        self.uc.reg_write(UC_X86_REG_EBP, sp)
        self.uc.reg_write(UC_X86_REG_ECX, this)
        self.failed = False
        try:
            self.uc.emu_start(fn, RET, count=limit)
        except UcError as e:
            if not self.failed:
                return ("error", str(e))
        return ("fail",) if self.failed else ("ok", self.uc.reg_read(UC_X86_REG_EAX))

    def stream(self, data):
        self.uc.mem_write(BUF, data)
        self.w32(STREAM + 0x4, 0)
        self.w32(STREAM + 0xC, BUF)
        self.w32(STREAM + 0x34, BUF + len(data))
        self.reads, self.read_esp, self.long_count = [], [], False
        return STREAM


class Decoder:
    """Client Unpack under emulation, with the server-format adjustments, producing node trees."""

    def __init__(self, exe_path):
        e = self.e = Emulator(exe_path)
        b = e.b
        text_va, text_raw = e.text
        sites = set()
        for m in re.finditer(rb"\xc7\x45\xf4(.{4})\xc7\x45\xf8(.{4})\xc7\x45\xfc(.{4})", b, re.S):
            k = b.rfind(b"\x55\x8b\xec", max(0, m.start() - 40), m.start())
            va = k + text_va - text_raw
            if k >= 0 and REG_FIRST <= va < REG_LAST:
                sites.add(va)
        for s in sorted(sites | set(EXTRA_INITIALIZERS)):
            e.call(s, limit=500_000)
        # node classes: runtime vtable -> type, and every Unpack (vtable slot 5) gets a hook
        # every registered class (node types 0x100000xx, built-in nodes and value types with low ids):
        # runtime vtable -> name, and every Unpack (vtable slot 5) gets a hook
        self.vt_type, unpacks = {}, set()
        for m in re.finditer(rb"\xc7\x45\xf4(.{4})\xc7\x45\xf8(.{4})\xc7\x45\xfc(.{4})", b, re.S):
            t, fac, size = (struct.unpack("<I", x)[0] for x in m.groups())
            site = m.start() + text_va - text_raw
            if not (REG_FIRST <= site < REG_LAST) or size > 0x10000 or not (text_va <= fac < text_va + 0x1200000):
                continue
            r = e.call(fac, limit=200_000)
            if r[0] != "ok" or not r[1]:
                continue
            vt = e.u32(r[1])
            self.vt_type.setdefault(vt, t)
            unpacks.add(e.u32(vt + 20))
        for t, fac in EXTRA_INITIALIZERS.values():
            r = e.call(fac, limit=200_000)
            if r[0] == "ok" and r[1]:
                vt = e.u32(r[1])
                self.vt_type.setdefault(vt, t)
                unpacks.add(e.u32(vt + 20))
        for a in unpacks:
            e.uc.hook_add(UC_HOOK_CODE, self._on_node, begin=a, end=a)
        e.uc.hook_add(UC_HOOK_CODE, self._on_var_optional, begin=VAR_OPTIONAL, end=VAR_OPTIONAL)
        e.uc.hook_add(UC_HOOK_CODE, lambda uc, a, s, _: e._return(1, 0), begin=VAR_VALIDATE, end=VAR_VALIDATE)

    def _on_node(self, uc, addr, size, _):
        e = self.e
        vt = e.u32(uc.reg_read(UC_X86_REG_ECX))
        esp = uc.reg_read(UC_X86_REG_ESP)
        idx = self.n_enter
        self.n_enter += 1
        self.events.append(["enter", self.vt_type.get(vt), esp, len(e.reads), vt])
        ret = e.u32(esp)
        handle = []

        def on_return(uc2, a, s, _):
            if uc2.reg_read(UC_X86_REG_ESP) > esp:          # back in the caller: this Unpack is done
                self.events.append(["exit", idx, None, len(e.reads), None])
                uc2.hook_del(handle[0])
        handle.append(uc.hook_add(UC_HOOK_CODE, on_return, begin=ret, end=ret))

    def _on_var_optional(self, uc, addr, size, _):
        """Skip the server-only default values that follow a variable type array."""
        e = self.e
        if e.u32(uc.reg_read(UC_X86_REG_ESP)) != VAR_OPTIONAL_RET or not e.reads or e.reads[-1][2] != VAR_TYPE_READ:
            return
        k = len(e.reads) - 1
        while k >= 0 and e.reads[k][2] == VAR_TYPE_READ:
            k -= 1
        types = [struct.unpack_from("<I", self.data, o)[0] for o, *_ in e.reads[k + 1:]]
        cur = e.u32(STREAM + 0xC)
        base, n, words = (cur - BUF) // 4, len(types), len(self.data) // 4
        skip = None
        for j in range(6 * n + 8):
            p = base + j
            if p + 3 + 2 * n > words:
                break
            w = struct.unpack_from("<%dI" % (3 + 2 * n), self.data, 4 * p)
            if w[0] == 1 and w[1] == 0 and w[2] == n and all(
                    w[3 + 2 * i] <= 0x0FFFFFFF and w[4 + 2 * i] < 0x1000 for i in range(n)):
                skip = j
                break
        if skip is None:                       # no name table: sizes measured over the whole corpus (fix C)
            skip = 0
            for t in types:
                if t == 0xA:                   # a frame: 1 word when empty, else 3 words starting with 0xCB
                    first = struct.unpack_from("<I", self.data, 4 * (base + skip))[0] if 4 * (base + skip) + 4 <= len(self.data) else 0
                    skip += 1 if first == 0 else 3
                else:
                    skip += DEFAULT_SIZES.get(t, 1)
        e.w32(STREAM + 0xC, cur + 4 * skip)
        self.defaults.append({"offset": 4 * base, "types": types,
                              "words": list(struct.unpack_from("<%dI" % skip, self.data, 4 * base))})

    def decode(self, did, data):
        """-> (status, bytes consumed, tree)"""
        e = self.e
        self.data, self.events, self.defaults, self.n_enter = data, [], [], 0
        obj = e.call(CREATE_SCRIPT, args=(did,))[1]
        st = e.stream(data)
        r = e.call(UNPACK_SCRIPT, args=(obj, st))
        used = e.u32(STREAM + 0xC) - BUF
        return r[0], used, self._tree(did)

    def _tree(self, did):
        e, data = self.e, self.data
        root = {"id": f"0x{did:08X}", "type": "script", "fields": [], "children": []}
        stack, ri, nodes = [root], 0, {}

        def take(upto):
            nonlocal ri
            while ri < upto:
                o, n, ret = e.reads[ri]
                raw = data[o:o + n]
                value = int.from_bytes(raw, "little") if n <= 4 else raw.decode("latin1")
                stack[-1]["fields"].append([o, n, f"0x{ret:X}", value])
                ri += 1
        merged = set()
        for kind, t, esp, nread, vt in self.events:
            take(nread)
            if kind == "exit":
                idx = t
                if idx in merged:
                    continue
                node = nodes.get(idx)
                if node is not None and stack[-1] is node:
                    stack.pop()
                continue
            if isinstance(t, tuple):
                name = f"{t[0]}:{t[1]:#x}"
            else:
                name = (f"0x{t:08X}" if t >= 0x10000000 else f"builtin:{t:#x}") if t is not None else None
            top = stack[-1]
            idx = len(nodes) + len(merged)
            if top is not root and top.get("vt") == f"0x{vt:X}" and not top["fields"] and not top["children"]:
                merged.add(idx)                # the base class's Unpack of the same node
                continue
            via = top["fields"][-1][2] if top["fields"] else None
            node = {"type": name, "vt": f"0x{vt:X}", "at": len(top["fields"]), "via": via,
                    "fields": [], "children": []}
            top["children"].append(node)
            stack.append(node)
            nodes[idx] = node
        take(len(e.reads))
        root["defaults"] = self.defaults
        return root


def show(node, depth=0, out=print):
    def fmt(v):
        return f"{v:x}" if isinstance(v, int) else repr(v)
    out("  " * depth + f"{node.get('id') or node['type']}: " + " ".join(fmt(f[3]) for f in node["fields"])[:200])
    for c in node["children"]:
        show(c, depth + 1, out)


def records(g, window=262144):
    """(did, [candidate bytes from a record start, ...]) for every 0x34 record; the decoder finds the real end.
    A record starts with `did | n | t`, n graphs (0 < n < 64) and t the first one's registry type (1 graph,
    2 state); every such occurrence is a candidate, the caller keeps the one that decodes (fix A, 2026-10-22)."""
    import collections
    idx = g.index()
    bypack = collections.defaultdict(set)
    for did, pack in idx.items():
        if did >> 24 == 0x34:
            bypack[pack].add(did)
    for pack, dids in sorted(bypack.items()):
        data = g.packs.pack(pack).data
        for did in sorted(dids):
            out = []
            k = data.find(struct.pack("<I", did))
            while k >= 0:
                if k + 12 <= len(data):
                    n, t = struct.unpack_from("<2I", data, k + 4)
                    if 0 < n < 64 and t in (1, 2):
                        out.append(data[k:k + window])
                k = data.find(struct.pack("<I", did), k + 1)
            if out:
                yield did, out


def decode_best(dec, did, candidates):
    """Decode every candidate start of a record; the one that reads ok (most bytes first), else the longest."""
    best = None
    for data in candidates:
        status, used, tree = dec.decode(did, data)
        key = (status == "ok", used)
        if best is None or key > best[0]:
            best = (key, status, used, tree)
    return best[1:]


def main(argv):
    from icserver import config as config_mod, gamedata
    cfg = config_mod.load(None)
    exe = os.path.join(cfg.game_dir, "InfiniteCrisis.exe")
    g = gamedata.Game(os.path.join(cfg.game_dir, "rp"))
    dec = Decoder(exe)
    if argv[:1] == ["tree"]:
        wanted = {int(a, 16) for a in argv[1:]}
        for did, cands in records(g):
            if did in wanted:
                status, used, tree = decode_best(dec, did, cands)
                print(f"0x{did:08X}: {status}, {used} bytes")
                show(tree)
        return 0
    os.makedirs(OUT_DIR, exist_ok=True)
    total = ok = 0
    for did, cands in records(g):
        total += 1
        status, used, tree = decode_best(dec, did, cands)
        tree["status"], tree["bytes"] = status, used
        ok += status == "ok"
        with open(os.path.join(OUT_DIR, f"{did:08x}.json"), "w", encoding="utf-8") as f:
            json.dump(tree, f)
    print(f"{ok} of {total} scripts decoded -> {OUT_DIR}")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
