"""Map the script VM's node classes in the client exe and write catalog/data/script_nodes.tsv.

The client registers every script node type with a static initializer
    mov [ebp-0xC], type ; mov [ebp-8], factory ; mov [ebp-4], object size
(e.g. rva 0x13c2f70 for 0x10000155). The factory allocates the object and jumps to the C++ constructor,
whose last vtable store is the class vtable. Vtable slot 5 is Unpack (stream reader), slot 6 Pack, slot 11
creates the runtime instance (or a clone). Unpack is summarised as a field signature:
    B  base node: u32 type of the next node in the chain (0 = none), then that node inline
    O  operand: 3 u32 (value | source | slot)
    rN read N raw bytes      {...} helper subroutine      V virtual call      *loop  contains a loop

    python tools\\script_nodes.py            rebuild the table (needs capstone and the game install)

Only IDs, sizes, addresses and counts are written; nothing from the game files is copied.
"""
import collections
import csv
import os
import re
import struct
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from icserver import config as config_mod, gamedata  # noqa: E402
import server_scripts  # noqa: E402

OUT = os.path.join(ROOT, "catalog", "data", "script_nodes.tsv")
READ, OPERAND, BASE, FAIL, NOP = 0xAFAE80, 0x453160, 0x45FE70, 0xAF8710, 0xAB4D80


class Exe:
    def __init__(self, path):
        self.b = open(path, "rb").read()
        pe = struct.unpack_from("<I", self.b, 0x3C)[0]
        nsec = struct.unpack_from("<H", self.b, pe + 6)[0]
        opt = struct.unpack_from("<H", self.b, pe + 20)[0]
        base = struct.unpack_from("<I", self.b, pe + 52)[0]
        self.secs = []
        for i in range(nsec):
            o = pe + 24 + opt + 40 * i
            vs, va, rs, rp = struct.unpack_from("<4I", self.b, o + 8)
            self.secs.append((self.b[o:o + 8].rstrip(b"\0").decode(), base + va, vs, rp, rs))

    def off(self, va):
        for _, start, vs, rp, rs in self.secs:
            if start <= va < start + max(vs, rs):
                return va - start + rp
        return None

    def section(self, va):
        for name, start, vs, _, _ in self.secs:
            if start <= va < start + vs:
                return name
        return None

    def u32(self, va):
        return struct.unpack_from("<I", self.b, self.off(va))[0]


def registrations(exe):
    """{node type: (factory, size, registration site)} for types 0x10000000-0x10000FFF."""
    text = next(s for s in exe.secs if s[0] == ".text")
    delta = text[1] - text[3]
    out = {}
    for m in re.finditer(rb"\xc7\x45\xf4(.{4})\xc7\x45\xf8(.{4})\xc7\x45\xfc(.{4})", exe.b, re.S):
        t, fac, size = (struct.unpack("<I", g)[0] for g in m.groups())
        if 0x10000000 <= t < 0x10001000 and size < 0x400:
            out.setdefault(t, (fac, size, m.start() + delta))
    return out


def vtable(exe, fac):
    """Class vtable reached through the factory's tail jump to the constructor, or None."""
    o = exe.off(fac)
    m = re.search(rb"\x85\xc0\x74.\x8b\xc8\xe9(.{4})", exe.b[o:o + 160], re.S)
    if not m:
        return None
    ctor = fac + m.start() + 11 + struct.unpack("<i", m.group(1))[0]
    co = exe.off(ctor)
    vts = [struct.unpack("<I", x.group(1))[0]
           for x in re.finditer(rb"\xc7[\x00\x01\x06\x07](.{4})", exe.b[co:co + 400], re.S)]
    vts = [v for v in vts if exe.section(v) == ".rdata"]
    return vts[-1] if vts else None


def signature(exe, md, fn, depth=0, seen=None):
    seen = seen if seen is not None else set()
    o, out, push, loop = exe.off(fn), [], None, False
    for ins in md.disasm(exe.b[o:o + 1500], fn):
        if ins.mnemonic == "push" and (ins.op_str.startswith("0x") or ins.op_str.isdigit()):
            push = int(ins.op_str, 0)
        if ins.mnemonic.startswith("j") and ins.op_str.startswith("0x") and fn <= int(ins.op_str, 16) < ins.address:
            loop = True
        if ins.mnemonic == "call":
            if not ins.op_str.startswith("0x"):
                out.append("V")
            else:
                tgt = int(ins.op_str, 16)
                if tgt == READ:
                    out.append(f"r{push}")
                elif tgt == OPERAND:
                    out.append("O")
                elif tgt == BASE:
                    out.append("B")
                elif tgt not in (FAIL, NOP) and depth < 2 and tgt not in seen and exe.section(tgt) == ".text":
                    seen.add(tgt)
                    sub = signature(exe, md, tgt, depth + 1, seen)
                    if sub:
                        out.append("{" + sub + "}")
        if ins.mnemonic == "ret":
            break
    return " ".join(out) + (" *loop" if loop else "")


def usage(g):
    """{node type: (uses, scripts)} from the heuristic 'u32 2 | type' node header in every 0x34 record."""
    uses, scripts = collections.Counter(), collections.defaultdict(set)
    for did, b in server_scripts.records(g):
        w = struct.unpack_from("<%dI" % (min(len(b), 400000) // 4), b)
        for j in range(1, len(w)):
            if w[j - 1] == 2 and 0x10000000 <= w[j] < 0x10001000:
                uses[w[j]] += 1
                scripts[w[j]].add(did)
    return {t: (uses[t], len(scripts[t])) for t in uses}


def main():
    from ics import script_runtime as runtime
    from capstone import Cs, CS_ARCH_X86, CS_MODE_32
    cfg = config_mod.load(None)
    exe = Exe(os.path.join(cfg.game_dir, "InfiniteCrisis.exe"))
    md = Cs(CS_ARCH_X86, CS_MODE_32)
    regs = registrations(exe)
    used = usage(gamedata.Game(os.path.join(cfg.game_dir, "rp")))
    rows = []
    for t in sorted(set(regs) | set(used)):
        fac, size, site = regs.get(t, (None, None, None))
        vt = vtable(exe, fac) if fac else None
        sig = signature(exe, md, exe.u32(vt + 20)) if vt else ""
        n_uses, n_scripts = used.get(t, (0, 0))
        name = server_scripts.NODE_NAMES.get(t, "")
        if fac is None:
            status, notes = "not started", "used by scripts, no registration found in the exe"
        elif t in runtime.HANDLERS or t in runtime.PREDICATES:
            status, notes = "partial", "run by the new server (ics/script_runtime.py)"
        else:
            status, notes = ("partial" if name else "data only"), ""
        rows.append([f"0x{t:08X}", name, f"0x{size:X}" if size is not None else "",
                     f"0x{fac:X}" if fac else "", f"0x{vt:X}" if vt else "", sig,
                     str(n_uses), str(n_scripts), status, notes])
    with open(OUT, "w", encoding="utf-8", newline="") as f:
        w = csv.writer(f, delimiter="\t", lineterminator="\n")
        w.writerow(["id", "name", "size", "factory", "vtable", "unpack", "uses", "scripts", "server_status", "notes"])
        w.writerows(rows)
    print(f"{len(rows)} node types ({len(regs)} registered in the exe) -> {OUT}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
