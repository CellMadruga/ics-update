"""Survey and read the original server's scripts (record type 0x34) from the player's packs.

The 0x34 records are the server's skill/effect logic shipped as data (blocks of statements, variables, a small
state machine, the events it handles); the client exe contains the script VM that reads them. See
docs/reverse-engineering.md, "Server scripts (0x34)".

    python tools\\server_scripts.py survey              node-type vocabulary over every 0x34 record
    python tools\\server_scripts.py dump 0x34000167     one record, readable (names, operands, known nodes)
    python tools\\server_scripts.py words 0x34000167    one record as raw u32 words

Nothing read here is written to the repository.
"""
import collections
import os
import re
import struct
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from icserver import config as config_mod, gamedata  # noqa: E402

FF = 0xFFFFFFFF
SELF = 0x4DD4

# Node types identified so far (by matching scripts whose in-game behaviour is known).
NODE_NAMES = {
    0x10000010: "Delay",          # target, f32 seconds
    0x10000034: "RunScriptlet",   # key (0x33 name table), target, argument
    0x10000027: "ApplySkill",     # skill 0x48, target, parameter (e.g. knockdown duration)
    0x1000001D: "ApplyEffects",   # source, count, status effects 0x1E..., magnitude, target
    # fase3-fn: identified while running Sonic Batarang (icserver/scriptvm_runtime.py)
    0x10000007: "StartCooldown",
    0x10000014: "IsValidPosition",
    0x1000001E: "IsValid",
    0x10000024: "GetDetected",
    0x10000026: "Cast",
    0x10000028: "IsHostile",
    0x10000029: "IsKind",
    0x10000031: "Spend",
    0x1000003E: "IsAlive",
    0x1000003F: "FaceTarget",
    0x10000047: "FindTargetsInRadius",
    0x10000050: "InitSkill",
    0x10000052: "IsWithinAngle",
    0x10000058: "SetVariable",
    0x1000005A: "Offset",
    0x1000005E: "LaunchMissile",
    0x10000062: "RedirectMissile",
    0x1000006A: "HasStatus",
    0x1000009F: "LoadSkillStats",
    # fase3-fo: identified while running the basic attack and the status effects (ics/script_runtime.py)
    0x1000004E: "RaiseGraphEvent",      # entity [graph event]: scriptlet 0x100001E3 + variable 0x780
    0x10000011: "GetPosition",          # entity, out position
    0x1000007A: "HitEffect",            # target [scriptlet key, ...]
    0x10000103: "StartScriptlet",       # entity, -, [duration], out handle [scriptlet key]
    0x1000010B: "RollCritical",         # out roll, target
    0x10000027: "ApplySkill",           # target, duration, ... [status record 0x48...]: starts its script
    0x1000006B: "RaiseEvent",           # entity, iid, position, value [event]
    0x100000A4: "HasStatus",            # target [status record]
    0x10000002: "GetAttribute",         # (expression) entity [attribute property]
}

# Variable source codes in a "name hash | source | slot" operand.
SOURCES = {1: "", 3: "L.", 4: "G.", 5: "P."}


def elf_hash(name):
    """Variable names are stored as the ELF/PJW hash of the name."""
    h = 0
    for c in name.encode():
        h = ((h << 4) + c) & 0xFFFFFFFF
        g = h & 0xF0000000
        if g:
            h ^= g >> 24
        h &= ~g & 0xFFFFFFFF
    return h


def records(g, wanted_type=0x34):
    """Yield (did, bytes) for every record of one type. A 0x34 record starts with
    "did | n | 1 | 0 | 0 | 0" and ends where the next DID of the pack's list starts."""
    idx = g.index()
    bypack = collections.defaultdict(set)
    for did, pack in idx.items():
        if did >> 24 == wanted_type:
            bypack[pack].add(did)
    for pack, dids in sorted(bypack.items()):
        pk = g.packs.pack(pack)
        data, order = pk.data, {d: i for i, d in enumerate(pk.ids)}
        for did in sorted(dids):
            k = data.find(struct.pack("<I", did))
            while k >= 0:
                a, one, z1, z2, z3 = struct.unpack_from("<5I", data, k + 4)
                if 0 < a < 64 and one == 1 and z1 == z2 == z3 == 0:
                    break
                k = data.find(struct.pack("<I", did), k + 1)
            if k < 0:
                continue
            i = order[did]
            end = data.find(struct.pack("<I", pk.ids[i + 1]), k + 24) if i + 1 < len(pk.ids) else -1
            yield did, data[k:end if end > 0 else len(data)]


def _names(b):
    """{elf hash: name} for every identifier written in the record (the variable name tables)."""
    return {elf_hash(m.group(0).decode()): m.group(0).decode()
            for m in re.finditer(rb"[A-Za-z_][A-Za-z0-9_]{2,60}", b)}


def _float(x):
    f = struct.unpack("<f", struct.pack("<I", x))[0]
    return f if 1e-4 < abs(f) < 1e6 and (x & 0xFFF) == 0 else None


def render(b):
    """Readable token stream: #literal, $variable, SELF, <record DID>, node names, raw words."""
    names = _names(b)
    w = struct.unpack_from("<%dI" % (len(b) // 4), b)
    i, out = 0, []
    while i < len(w):
        x = w[i]
        a = w[i + 1] if i + 1 < len(w) else None
        c = w[i + 2] if i + 2 < len(w) else None
        if a == FF and c == FF:
            f = _float(x)
            out.append("#" + (f"{f:g}" if f is not None else f"'{names[x]}'" if x in names else f"{x:x}"))
            i += 3
        elif x in names and a is not None and 1 <= a <= 8 and c is not None and c < 0x1000:
            out.append(f"${SOURCES.get(a, f'{a}.')}{names[x]}")
            i += 3
        elif x == SELF and a == 2:
            out.append("SELF")
            i += 3
        else:
            if x in NODE_NAMES:
                out.append(NODE_NAMES[x])
            elif 0x10000000 <= x < 0x10010000:
                out.append(f"T{x & 0xFFFF:x}")
            elif x >> 24 in (0x1D, 0x1E, 0x2D, 0x2E, 0x30, 0x34, 0x3B, 0x40, 0x48):
                out.append(f"<{x:08x}>")
            elif x in names and x > 0xFFFF:
                out.append(f"'{names[x]}'")
            elif _float(x) is not None:
                out.append(f"{_float(x):g}f")
            else:
                out.append(f"{x:x}")
            i += 1
    return " ".join(out)


def survey(g):
    types, users, total = collections.Counter(), collections.defaultdict(set), 0
    for did, b in records(g):
        total += 1
        w = struct.unpack_from("<%dI" % (len(b) // 4), b)
        for j in range(1, len(w)):
            if w[j - 1] == 2 and 0x10000000 <= w[j] < 0x10000200:
                types[w[j]] += 1
                users[w[j]].add(did)
    print(f"server scripts: {total}, candidate node types: {len(types)}")
    covered = 0
    for n, (t, c) in enumerate(types.most_common(), 1):
        covered += c
        print(f"  {n:3d} {t:#010x} {NODE_NAMES.get(t, ''):<13} uses {c:5d} in {len(users[t]):4d} scripts"
              f"  ({100 * covered / sum(types.values()):.0f}% of uses)")


def _one(g, did):
    for d, b in records(g, did >> 24):
        if d == did:
            return b
    return None


def main(argv):
    cfg = config_mod.load(None)
    g = gamedata.Game(os.path.join(cfg.game_dir, "rp"))
    if argv[:1] in (["dump"], ["words"]) and len(argv) > 1:
        did = int(argv[1], 16)
        b = _one(g, did)
        if b is None:
            print(f"{did:#010x} not found")
            return 1
        print(f"{did:#010x}: {len(b)} bytes")
        if argv[0] == "dump":
            print(render(b))
        else:
            for j in range(0, len(b) - 3, 4):
                print(f"{j:6d} {struct.unpack_from('<I', b, j)[0]:08x}")
        return 0
    survey(g)
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
