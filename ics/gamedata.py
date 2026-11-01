"""Everything the new server knows about the game comes from here: the player's rp packs and the catalog
tables built from them (catalog/data/*.tsv). Nothing about a champion, a skill or a map is written in code.

  Data.roster                       champions for the account screens (data/champions.json, from the packs)
  Data.kit(variant)                 {slot: Skill} of a champion variant (catalog champions.tsv + skills.tsv)
  Data.entity_scripts(class_did)    server scripts (0x34) of an entity class: template 0x49xxxxxx, property 0x8E
  Data.layout(pack_id)              named placements of an encounter layout pack (name, world state, positions)
  Data.variants(pack_id)            {world state: character variant} (the units that fight)
"""
import bisect
import csv
import json
import os
import re
import struct
import threading

from . import records, rp

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CATALOG = os.path.join(ROOT, "catalog", "data")
# Value kinds the client's descriptors give these properties (read with tools\diag.py --props, 2026-10-16;
# the Stolen Powers catalog and its skills); the catalog's properties.tsv adds the rest.
EXTRA_KINDS = {
    0x1000003d: 0x08,
    0x1000003e: 0x0e,
    0x1000003f: 0x0b,
    0x100000e6: 0x08,
    0x100001c0: 0x0e,
    0x100002a3: 0x15,
    0x10000302: 0x15,
    0x10000328: 0x15,
    0x10000448: 0x13,
    0x100004ae: 0x0e,
    0x100004af: 0x0b,
    0x100004b0: 0x0e,
    0x100004b3: 0x0b,
    0x100004b4: 0x0c,
    0x100004b6: 0x08,
    0x100004b7: 0x09,
    0x100004b9: 0x0e,
    0x100004d1: 0x0e,
    0x100004d2: 0x09,
    0x100004d3: 0x0b,
    0x100004d4: 0x0b,
    0x100004d7: 0x15,
    0x10000534: 0x10,
    0x10000535: 0x16,
    0x10000620: 0x15,
    0x10000645: 0x08,
    0x10000646: 0x08,
    0x1000068d: 0x13,
    0x100006d7: 0x15,
    0x100006d8: 0x15,
    0x100006df: 0x13,
    0x10000708: 0x16,
    0x10000729: 0x0e,
    0x100007a6: 0x13,
    0x100007a7: 0x16,
    0x1000083d: 0x08,
    0x10000840: 0x15,
    0x10000841: 0x0c,
    0x10000842: 0x0c,
    0x10000850: 0x15,
    0x10000853: 0x08,
    0x10000854: 0x0b,
    0x10000855: 0x0c,
    0x10000920: 0x0e,
    0x10000922: 0x0b,
    0x10000abc: 0x08,
    0x10000d32: 0x16,
    0x10000d9e: 0x16,
}
CACHE_DIR = os.path.join(ROOT, "data", "cache")   # derived indexes of the player's packs (not committed)
TARGET_PROPERTY_KINDS = {0x1000019D: 0x13, 0x10000AA7: 0x16, 0x100001C3: 0x08, 0x1000034C: 0x08}
PROP_SCRIPTS = 0x8E          # template property: list of server scripts (kind 0x30E entries = DIDs)
PROP_STATUS_SCRIPT = 0x10000242   # status effect record (0x48...): its server script
PACK_ZONE, PACK_VARIANTS, PACK_LAYOUT = 0xD, 0xE, 0xF   # pack categories (header +4) in a map's pack list
PROP_MAP_PACK = 0x10000406        # encounter template: the map pack (category 1: terrain cells + its pack list)
PROP_ENCOUNTER_CHAMPION = 0x10000AE6   # encounter template: a required champion (array 0x10000AE7)
ENCOUNTER_MASTER_LIST = 0x48000001  # record: the game's encounters (0x1000025D)
PROP_ENCOUNTER_CATEGORY = 0x10000D0B   # encounter template: 1 vs AI, 2 challenge, 3 PvP, 4 tutorial
PROP_CHAMPION_STATS = 0x100008E2      # champion definition: its stats record (0x40 / 0x49 pair)
PROP_DEFAULT_LOADOUT = 0x10000CEB    # champion definition: its default loadout record
# skill set record: each slot's skill block (catalog properties.tsv / skill_slots.tsv)
SKILL_BLOCK_PROPERTIES = {0: 0x100008E3, 1: 0x100008E8, 2: 0x100008EA, 3: 0x100008EC, 4: 0x100008E6, 5: 0x100008EF}
STOLEN_POWER_CATALOG = 0x480003CD    # Stolen Power groups: base power first, then the champions' versions
PROP_SHOP_LIST = 0x1000081E          # encounter template: its shop's foundry record
PROP_OBJECTIVES = 0x100001D2       # encounter template: its objective table 0x48...
PROP_STAT_BLOCK = 0x10000165       # unit template: its base stat block 0x48...
PROP_SCRIPT_TABLES = 0x7D2       # world state / entity template: its scriptlet tables (array of 0x462 = 0x1D DID)
SCRIPTLET_NAMES_PACK = 0xA0000038   # holds the scriptlet key name table 0x33000000
_SCRIPT_LIST = re.compile(rb"\x8e\x00\x00\x00(.{4})((?:\x0e\x03\x00\x00.{4})+)", re.S)
_STAT = re.compile(r"(\d+)=(-?[\d.]+)(?:\(([+-]?[\d.]+)/rank\))?")


def pack_header(path):
    """(record count, [DIDs]) without decompressing the records."""
    with open(path, "rb") as f:
        head = f.read(0x400)
        if head[:4] != b"10PR":
            return 0, []
        size, count = struct.unpack_from("<II", head, 0xC)
        raw, p = bytearray(), 0x400
        while len(raw) < 4 * count:
            f.seek(p)
            raw += f.read(min(0x1FFFC, 4 * count - len(raw)))
            p += 0x20000
    return count, list(struct.unpack_from("<%dI" % count, raw, 0))


# 2026-10-28 15:00 (tester report 2026-10-28 15:00; docs/re-notes/object-update-bundles.md 13, properties-complete.md 1):
# the client's property descriptors live in one record, MasterProperty 0x32000000 (pack 0xA0000039). Its unpack
# (0x502750) reads whole words only: u32 tag (1 / 2 / 3 / 0x81 / 0x82 / 0x83, 0 = end), then w0 = id | kind << 16,
# w1 (group, container), w2 (byte +2 = network mode), w3 flags; tag 2 / 0x82 + a u32 EnumMapper, tag 3 / 0x83 + two
# words (DB type, flags); tags 0x8x + a default / minimum / maximum for flags 0x800 / 0x1000 / 0x2000 (by kind) and a
# member set for flags 0x200000 (u8 size class, compact count, count x u32, one word each). Checked on the install:
# 3822 descriptors, the record's exact end, every network mode equal to properties-complete.tsv.
MASTER_PROPERTY = 0x32000000
_MP_VALUE_WORDS = {0x04: 2, 0x05: 1, 0x06: 3, 0x07: 2, 0x08: 1, 0x09: 1, 0x0A: 1, 0x0F: 2, 0x10: 1, 0x11: 1, 0x13: 1,
                   0x14: 2, 0x15: 1, 0x16: 1}


def _master_property_modes(data, pos):
    """{property id: network mode} of the MasterProperty body at pos, or None when the bytes there are not one (an
    unknown tag or kind, a default of a kind this reader does not walk, fewer than 1000 descriptors)."""
    out = {}
    try:
        while True:
            tag = struct.unpack_from("<I", data, pos)[0]
            pos += 4
            if tag == 0:
                break
            if tag not in (1, 2, 3, 0x81, 0x82, 0x83):
                return None
            w0, _w1, w2, w3 = struct.unpack_from("<4I", data, pos)
            pos += 16
            kind = (w0 >> 16) & 0xFF
            if not 1 <= kind <= 0x16:
                return None
            pos += {2: 4, 3: 8}.get(tag & 0x7F, 0)
            if tag & 0x80:
                for bit in (0x800, 0x1000, 0x2000):
                    if not w3 & bit:
                        continue
                    if kind in _MP_VALUE_WORDS:
                        pos += 4 * _MP_VALUE_WORDS[kind]
                    elif kind == 0x01:                    # ascii: u32 length, bytes padded to a word
                        pos += 4 + (struct.unpack_from("<I", data, pos)[0] + 3) // 4 * 4
                    elif kind == 0x03:                    # frame: u8 type; 1 = a cell word, else 13 words
                        pos += 4 + (4 if struct.unpack_from("<I", data, pos)[0] == 1 else 52)
                    else:
                        return None
                if w3 & 0x200000:
                    pos += 8 + 4 * struct.unpack_from("<I", data, pos + 4)[0]
            if pos > len(data):
                return None
            out[w0 & 0xFF00FFFF] = (w2 >> 16) & 0xFF
    except struct.error:
        return None
    return out if len(out) >= 1000 else None


class Skill:
    def __init__(self, row):
        self.id = row["id"]
        self.slot = int(row["slot"])
        self.key, self.name = row["key"], row["name"]
        self.script = int(row["script"], 16) if row.get("script") else 0
        self.targeting = int(row["targeting"]) if row.get("targeting") else 0
        self.stats = {}
        for m in _STAT.finditer(row.get("stats", "")):
            self.stats[int(m.group(1))] = (float(m.group(2)), float(m.group(3) or 0.0))

    def stat(self, stat, rank):
        base, per = self.stats.get(stat, (0.0, 0.0))
        return base + per * max(0, int(rank) - 1)

    def __repr__(self):
        return f"{self.key} {self.name} ({self.script:#x})"


def _tsv(name):
    with open(os.path.join(CATALOG, name), encoding="utf-8") as f:
        return list(csv.DictReader(f, delimiter="\t"))


WIRE_KINDS = {records.KIND_ENUM, records.KIND_F32, 0x0A, records.KIND_TABLE, records.KIND_ARRAY, records.KIND_STRING,
              records.KIND_INT, records.KIND_U32, records.KIND_DID, records.KIND_BOOL, records.KIND_IID}


def _wire_entries(entries):
    """Record entries the wire can carry (icserver/skilldata.py _clean): kinds the property writer knows, entries
    with a value, nested tables and arrays alike."""
    out = []
    for k, kind, v in entries or ():
        if kind not in WIRE_KINDS or v is None:
            continue
        if kind in (records.KIND_TABLE, records.KIND_ARRAY):
            v = _wire_entries(v)
        out.append((k, kind, v))
    return out


def _first(v):
    """An array's first element value (an entry list), or the value itself."""
    if isinstance(v, list):
        return next((x for _k, _kind, x in v), None)
    return v


STOLEN_STAT_MERGE = True             # [ics] stolen_stat_merge (set by ics/server.py)


class Data:
    def __init__(self, game_dir, roster_path=None):
        self.rp_dir = os.path.join(game_dir, "rp")
        self.packs = rp.PackSet(self.rp_dir)
        self._lock = threading.Lock()
        self._enc_lock = threading.Lock()
        self._prep_lock = threading.Lock()
        self._tables_lock = threading.Lock()
        self._tables = {}             # pack name -> its scriptlet tables
        self._encounters = {}
        self._index = None
        self._starts = {}
        self._scripts = {}
        self.missile_scripts_past_starts = True   # [ics] missile_scripts_past_starts (set by the server)
        self.class_scripts = {}                   # [ics] spawned_class_scripts: class -> scripts (set by the server)
        self.record_start_only = True             # [ics] record_start_only (set by the server)
        self.template_window_bounded = True       # [ics] template_window_bounded (set by the server)
        self._lists_skipped = set()               # packs whose record list a start-only lookup did not build
        self._id_sets = {}                        # pack name -> its DIDs (Data._template_end)
        self.roster = []
        path = roster_path or os.path.join(ROOT, "data", "champions.json")
        if os.path.isfile(path):
            with open(path, encoding="utf-8") as f:
                self.roster = json.load(f)
        self._skill_set = {}          # champion or costume variant -> skill set DID
        for row in _tsv("champions.tsv"):
            ss = int(row["skill_set"], 16)
            for v in [row["variant"]] + row.get("costume_variants", "").split():
                self._skill_set[int(v, 16)] = ss
        self._skills = {}             # skill set -> {slot: Skill}
        for row in _tsv("skills.tsv"):
            if ":" not in row["id"]:
                continue              # Stolen Powers: no skill set of their own
            ss = int(row["id"].split(":")[0], 16)
            sk = Skill(row)
            self._skills.setdefault(ss, {})[sk.slot] = sk

        self._kinds = {}              # property -> wire kind code (catalog properties.tsv)
        for row in _tsv("properties.tsv"):
            try:
                self._kinds[int(row["id"], 16)] = int(row["kind_code"], 16)
            except (KeyError, ValueError):
                continue
        # record reading: the catalog's kinds plus the ones the old server learned from the client (diag --props)
        self._all_kinds = dict(EXTRA_KINDS)
        self._all_kinds.update(self._kinds)
        self._net_modes = None        # property -> network mode (MasterProperty 0x32000000), read on first use
        self._net_lock = threading.Lock()

    def record(self, did):
        """A record's entries [(key, kind, value)] read by property kind (ics.records), or None. Every occurrence
        of the DID followed by a record header is tried (references to it come first in some packs)."""
        key = ("record", did)
        if key in self._scripts:
            return self._scripts[key]
        out = None
        name = self.index().get(did)
        if name:
            data = self.packs.pack(name).data
            pat = struct.pack("<I", did)
            k = data.find(pat)
            while k >= 0 and out is None:
                if k + 12 <= len(data):
                    a = struct.unpack_from("<I", data, k + 4)[0]
                    # 2: encounter templates, 4: entity definitions (a champion's 0x49 twin), 7: world states
                    if a in (0, 2, 3, 4, 7):
                        out = records.read_at(data, k, self._all_kinds)
                k = data.find(pat, k + 1)
        self._scripts[key] = out
        return out

    def objectives(self, encounter_did):
        """The encounter's objective table (template property 0x100001D2, e.g. Tutorial 1 -> 0x48000D3F): {"title":
        (token, table), "list": [{"id", "text": (token, table), "count", "key"}]} in play order. Texts stay in the
        game's string tables: the client is sent the (token, table) reference."""
        key = ("objectives", encounter_did)
        if key not in self._scripts:
            table = next(iter(self.template_properties(encounter_did).get(PROP_OBJECTIVES, [])), 0)
            entries = self.record(table) if table >> 24 == 0x48 else None
            out = {"did": table, "title": records.get(entries, 0x10000391), "list": []}
            for _ek, _kind, el in records.get(entries, 0x1000019F) or ():
                d = records.as_dict(el)
                out["list"].append({"id": d.get(0x1000030B, 0), "text": d.get(0x10000C15) or d.get(0x1000032D),
                                    "count": d.get(0x10000283), "key": _first(d.get(0x10000B20))})
            self._scripts[key] = out
        return self._scripts[key]

    def resource_vital(self, variant):
        """The champion's resource vital type: its twin's 0x1000000C (5 Will for 43 champions; 6 Rev: Atomic Wonder
        Woman, Huntress; 4: Atrocitus, Dex-Starr, Doomsday, Nightmare Robin; 1: Batman, Nightmare Batman, Shazam; 7:
        Katana; aww-kit.md), or 0."""
        twin = self.record(0x49000000 | (variant & 0xFFFFFF))
        v = records.get(twin, 0x1000000C) if twin else None
        return int(v) if isinstance(v, (int, float)) else 0

    def champion_stats(self, variant):
        """{stat property: (at level 1, per level)} of a champion variant: its twin's stats record (0x100008E2, a
        0x40 / 0x49 pair) array 0x100008E0 of 0x100008DD {0x10000100 stat, 0x100008DF value at level 1,
        0x100008DE growth per level}. Gaslight Batman: Health 0x10000426 455 (+76), Will 0x10000432 350 (+30),
        Attack Damage 0x10000B76 47 (+2.8), Attack Armor 13 (+3.1), Attack Speed 0.68 (+0.03), Move Speed 3.65."""
        key = ("champion stats", variant)
        if key not in self._scripts:
            out = {}
            twin = self.record(0x49000000 | (variant & 0xFFFFFF))
            st = records.get(twin, PROP_CHAMPION_STATS) or 0
            for _k, _kind, el in records.get(self.record(0x49000000 | (st & 0xFFFFFF)) if st else None, 0x100008E0) or []:
                d = records.as_dict(el)
                if d.get(0x10000100):
                    out[d[0x10000100]] = (float(d.get(0x100008DF) or 0.0), float(d.get(0x100008DE) or 0.0))
            self._scripts[key] = out
        return self._scripts[key]

    def artifact(self, did):
        """A shop artifact 0x40... (its twin 0x49...): {"cost", "sell", "prev", "next", "category", "stats":
        [(op, {stat: value})] (op 9 add, 10 add percent), "passives": [status records], "active": skill record}.
        shop-items-inventory.md section 1.1."""
        key = ("artifact", did)
        if key not in self._scripts:
            e = self.record(0x49000000 | (did & 0xFFFFFF))
            out = None
            if e:
                stats = []
                for _k, _kind, blk in records.get(e, 0x10000684) or []:
                    b = records.as_dict(blk)
                    stats.append((b.get(0x1000068B), {k: v for k, _kk, v in b.get(0x1000068C) or []}))
                passives = [v for _k, _kind, blk in records.get(e, 0x100004EA) or []
                            for k, _kk, v in blk if k == 0x1000037D]
                out = {"did": did, "cost": float(records.get(e, 0x1000036C) or 0.0),
                       "sell": float(records.get(e, 0x1000045E) or 0.0), "prev": records.get(e, 0x10000698) or 0,
                       "next": records.get(e, 0x10000697) or 0, "category": records.get(e, 0x1000048A) or 0,
                       "stats": stats, "passives": passives, "active": records.get(e, 0x100008E1) or 0,
                       "stack": records.get(e, 0x100005F7) or 0}
            self._scripts[key] = out
        return self._scripts[key]

    def shop_list(self, encounter_did):
        """The artifacts an encounter's shop offers: template 0x1000081E -> foundry record 0x1000042C (Tutorial 1 /
        Gotham Divided 0x48000EA9, Coast City 0x48000EAA, Gotham Heights 0x480007B0)."""
        key = ("shop", encounter_did)
        if key not in self._scripts:
            e = self.record(0x49000000 | (encounter_did & 0xFFFFFF))
            lst = records.get(e, PROP_SHOP_LIST) or 0
            self._scripts[key] = [v for _k, _kind, v in records.get(self.record(lst), 0x1000042C) or []] if lst else []
        return self._scripts[key]

    def loadout(self, variant):
        """A champion's default loadout (twin 0x10000CEB -> record 0x48...): {"stolen": the Stolen Power pair
        (0x1000064E), "artifacts": the recommended buys in order (0x10000478), "augments" (0x10000A12), "mods"
        (0x1000098F), "skill_order": the slot to rank at each level (0x1000034B: 19 points, 1-4 Q/W/E/R, 5 passive)}."""
        key = ("loadout", variant)
        if key not in self._scripts:
            twin = self.record(0x49000000 | (variant & 0xFFFFFF))
            e = self.record(records.get(twin, PROP_DEFAULT_LOADOUT) or 0) if twin else None

            def dids(prop, inner=0x10000694):
                out = []
                for _k, _kind, v in records.get(e, prop) or []:
                    if isinstance(v, list):             # {0x10000475 enum, 0x10000694 artifact}
                        v = next((x for k, _kk, x in v if k == inner), None)
                    if v:
                        out.append(v)
                return out
            self._scripts[key] = {"stolen": dids(0x1000064E), "artifacts": dids(0x10000478),
                                  "augments": dids(0x10000A12), "mods": dids(0x1000098F),
                                  "skill_order": dids(0x1000034B), "own_stolen": records.get(twin, 0x10000CE5) or 0}
        return self._scripts[key]

    def stolen_power(self, version):
        """(skill block, Skill) of a Stolen Power version (e.g. Gaslight Batman's camera 0x48000808): its block
        0x1000003F on top of its base power's (the first of its group in catalog 0x480003CD), as the client's
        champion property 0x100008F0 / 0x100008F1 holds it (icserver/skilldata.py, 2026-10-16)."""
        key = ("stolen", version)
        if key not in self._scripts:
            base = 0
            for _k, _kind, groups in self.record(STOLEN_POWER_CATALOG) or []:
                for _gk, _gkind, members in groups if isinstance(groups, list) else ():
                    ids = [v for _mk, _mkind, v in members] if isinstance(members, list) else []
                    if version in ids:
                        base = ids[0]
            merged, order = {}, []
            for did in ([base] if base and base != version else []) + [version]:
                for k, kind, v in records.get(self.record(did), 0x1000003F) or []:
                    if k not in merged:
                        order.append(k)
                    elif k == 0x100004B4 and STOLEN_STAT_MERGE and isinstance(v, list)                             and isinstance(merged[k][2], list):
                        # 2026-10-25 (stolen-powers-audit.md 1, verified headless: 50 versions lost damage, range and
                        # cooldown): a version's stat list holds only its deltas; it overrides the base power's entries
                        # stat by stat (0x100004B6), the rest of the base list kept
                        def sid(el):
                            return records.as_dict(el[2]).get(0x100004B6) if isinstance(el[2], list) else None
                        mine = {sid(el): el for el in v}
                        kept = [el for el in merged[k][2] if sid(el) not in mine]
                        v = kept + list(v)
                    merged[k] = (k, kind, v)
            block = _wire_entries([merged[k] for k in order])
            self._scripts[key] = (block, self._skill_from_block(block, version, "Stolen")) if block else (None, None)
        return self._scripts[key]

    def _skill_from_block(self, entries, did, key_name):
        b = records.as_dict(entries)
        stats = []
        for _k, _kind, st in b.get(0x100004B4) or []:
            sd = records.as_dict(st)
            val = records.as_dict(sd.get(0x100004D3) or sd.get(0x100004D4) or [])
            if sd.get(0x100004B6) is not None and val.get(0x100004B7) is not None:
                per = val.get(0x100004D2)
                stats.append(f"{sd[0x100004B6]}={val[0x100004B7]:g}" + (f"({per:+g}/rank)" if per else ""))
        script = b.get(0x10000328) or 0
        return Skill({"id": f"0x{did:08X}", "slot": "10", "key": key_name, "name": f"{key_name.lower()} {did:#x}",
                      "script": f"0x{script:08X}" if script else "", "targeting": str(b.get(0x1000003D) or ""),
                      "stats": " ".join(stats)})

    def item_skill(self, record_did):
        """An artifact's active ability (record 0x48... named by 0x100008E1) as a Skill: its block 0x100008E5's
        script (0x10000328) and stats (0x100004B4), as a Stolen Power's."""
        key = ("item skill", record_did)
        if key not in self._scripts:
            out = None
            e = self.record(record_did)
            blk = records.get(e, 0x100008E5) or records.get(e, 0x1000003F)
            if blk:
                b = records.as_dict(blk)
                stats = []
                for _k, _kind, st in b.get(0x100004B4) or []:
                    sd = records.as_dict(st)
                    val = records.as_dict(sd.get(0x100004D3) or sd.get(0x100004D4) or [])
                    if sd.get(0x100004B6) is not None and val.get(0x100004B7) is not None:
                        per = val.get(0x100004D2)
                        stats.append(f"{sd[0x100004B6]}={val[0x100004B7]:g}" + (f"(+{per:g}/rank)" if per else ""))
                script = b.get(0x10000328) or 0
                out = Skill({"id": f"0x{record_did:08X}", "slot": "10", "key": "Item", "name": f"item {record_did:#x}",
                             "script": f"0x{script:08X}" if script else "", "targeting": str(b.get(0x1000003D) or ""),
                             "stats": " ".join(stats)})
            self._scripts[key] = out
        return self._scripts[key]

    def navgrid(self, encounter_did, origin_lb):
        """The encounter map's walkable grid (ics.navmesh: the map pack's champion-sized NavMesh), or None."""
        key = ("nav", encounter_did, tuple(origin_lb))
        if key not in self._scripts:
            from . import navmesh
            mp = self.encounter(encounter_did).get("map_pack")
            grid = None
            try:
                grid = navmesh.load(self.packs.pack(mp).data, tuple(origin_lb)) if mp else None
            except (OSError, struct.error, ValueError):
                grid = None
            self._scripts[key] = grid
        return self._scripts[key]

    def encounter_list(self):
        """[(encounter DID, category)] of the master list (record 0x48000001, property 0x1000025D) whose map pack
        (template 0x10000406) is installed. Category 0x10000D0B: 1 vs AI, 2 challenge, 3 PvP, 4 tutorial
        (maps-encounters.md). 2026-10-21: Metropolis Skyway and Apokolips Causeway have no map in the install."""
        key = ("encounter list",)
        if key not in self._scripts:
            out = []
            for _k, _kind, did in records.get(self.record(ENCOUNTER_MASTER_LIST), 0x1000025D) or []:
                e = self.record(0x49000000 | (did & 0xFFFFFF))
                mp = records.get(e, PROP_MAP_PACK) or 0
                if mp and os.path.isfile(os.path.join(self.rp_dir, f"0x{mp:08x}.rp")):
                    out.append((did, records.get(e, PROP_ENCOUNTER_CATEGORY) or 0))
            self._scripts[key] = out
        return self._scripts[key]

    def conversation_seconds(self, key, default=4.0):
        """How long a conversation plays: catalog conversations.tsv ("Est. N s", timed on the original's video)."""
        if not hasattr(self, "_conv_seconds"):
            self._conv_seconds = {}
            for row in _tsv("conversations.tsv"):
                m = re.search(r"Est\. ([0-9.]+) s", row.get("notes", ""))
                try:
                    if m:
                        self._conv_seconds[int(row["id"], 16)] = float(m.group(1))
                except ValueError:
                    continue
        return self._conv_seconds.get(key, default)

    def hud_elements(self):
        """HUD element ids (catalog hud_elements.tsv, from the client's HUD tables)."""
        return [int(r["id"]) for r in _tsv("hud_elements.tsv") if r.get("id", "").isdigit()]

    def property_kind(self, prop):
        return self._kinds.get(prop)

    def network_mode(self, prop):
        """2026-10-28 15:00 (tester report 2026-10-28 15:00; docs/re-notes/object-update-bundles.md 3 / 13): a
        property's network mode, the descriptor's byte +0x16 (properties-complete.md 3): 1 / 3 are the ids a full
        bundle's 0xBC REMOVES when it leaves them out (0x62AFD0 -> 0x4FB520), so World.delta removes exactly those (0x86).
        Read once from the client's own MasterProperty record 0x32000000 (pack 0xA0000039, 3822 descriptors); None =
        unknown (no such descriptor, or the record could not be read: then nothing is removed)."""
        if self._net_modes is None:
            with self._net_lock:                  # its own lock: index() takes self._lock (not re-entrant)
                if self._net_modes is None:
                    self._net_modes = self._read_network_modes()
        return self._net_modes.get(prop)

    def _read_network_modes(self):
        name = self.index().get(MASTER_PROPERTY)
        if not name:
            return {}
        try:
            data = self.packs.pack(name).data
        except (OSError, ValueError):
            return {}
        pat = struct.pack("<I", MASTER_PROPERTY)
        k = data.find(pat)
        while k >= 0:
            modes = _master_property_modes(data, k + 4)
            if modes:
                return modes
            k = data.find(pat, k + 1)
        return {}

    # ---- champions ------------------------------------------------------------------------
    def champion_name(self, variant):
        for c in self.roster:
            if c["variant"] == variant or any(s["variant"] == variant for s in c.get("costume_info", [])):
                return c["name"], c.get("tex384", 0)
        return "Champion", 0

    def base_variant(self, variant):
        """The champion's default variant for any of its costumes (itself when it is one), or 0."""
        for c in self.roster:
            if c["variant"] == variant or any(s["variant"] == variant for s in c.get("costume_info", [])):
                return c["variant"]
        return 0

    def champion_pack(self, variant):
        """A champion variant's model pack ("heavy" pack in the roster), or 0."""
        for c in self.roster:
            if c["variant"] == variant:
                return c.get("heavy_pack", 0)
            for s in c.get("costume_info", []):
                if s["variant"] == variant:
                    return s.get("heavy_pack", 0)
        return 0

    def champion_shared_packs(self, variant):
        """The packs a variant's model pack leans on: the champion's parent pack (2026-10-23 15:40, tester: the
        Samurai costume showed without its mask; the costume's template 0x490003C7 points at skill scripts / icons
        in Batman's parent pack 0xA0000122). Not the base variant's model pack: it carries the costume's DIDs with
        other content (2026-10-23 16:20, the base model showed over the costume)."""
        for c in self.roster:
            if c["variant"] == variant or any(s["variant"] == variant for s in c.get("costume_info", [])):
                return [p for p in [c.get("parent_pack", 0)] if p]
        return []

    def kit(self, variant):
        return dict(self._skills.get(self._skill_set.get(variant), {}))

    def skill_rank_levels(self, variant):
        """{slot: [level for rank 1, rank 2, ...]} from the champion's skill set: array 0x1000099C inside a slot's skill
        block (0x100008E3 basic, 0x100008E8 Q, 0x100008EA W, 0x100008EC E, 0x100008E6 R, 0x100008EF passive). The
        client's InqCanRankSkill (WLib 0x926C -> 0x94E4, native 0x1050008 = exe 0x8509A0 -> 0x86EF10 reading
        0x1000099C) uses it for rank r when 1 <= r <= its length, else its built-in table (skill-rank-levels.md).
        Only Green Arrow's R [1, 6, 11, 16] and Starro's E [2] carry one in this client's data."""
        ss = self._skill_set.get(variant)
        key = ("rank_levels", ss)
        if key not in self._scripts:
            out = {}
            e = self.record(ss) if ss else None
            for slot, prop in SKILL_BLOCK_PROPERTIES.items():
                blk = records.get(e, prop) if e else None
                arr = records.get(blk, 0x1000099C) if isinstance(blk, list) else None
                if isinstance(arr, list):
                    levels = [int(v) for _k, _kind, v in arr if isinstance(v, int)]
                    if levels:
                        out[slot] = levels
            self._scripts[key] = out
        return self._scripts[key]

    # ---- packs ------------------------------------------------------------------------------
    def index(self):
        """{DID: pack file} for every record of every pack (headers only, read once)."""
        with self._lock:
            if self._index is None:
                self._index = {}
                self._table_packs = {}           # scriptlet table 0x1D... -> every pack that lists it
                for name in sorted(os.listdir(self.rp_dir)):
                    if name.lower().endswith(".rp"):
                        try:
                            for did in pack_header(os.path.join(self.rp_dir, name))[1]:
                                self._index.setdefault(did, name.lower())
                                if did >> 24 == 0x1D:
                                    self._table_packs.setdefault(did, []).append(name.lower())
                        except (OSError, struct.error):
                            continue
            return self._index

    def _record(self, did, need_end=True):
        """(pack data, start, end) of a record, or None. need_end=False is for the readers that search a window from
        the record's start and never use its end (creation_type, champion_world_state, unit_attack, unit_stats,
        record_u32, template_properties, record_tables): they get end = start + 16 KB."""
        name = self.index().get(did)
        if not name:
            return None
        pack = self.packs.pack(name)
        data = pack.data
        if not need_end and self.record_start_only:
            # 2026-10-28 15:00 (tester report; docs/re-notes/test-2026-10-28-1439-sweep.md S1: the match froze 2.77 s at
            # AWW's first Savage Sweep: creation_type(0x2E0009F0) built the record list of the 22 MB pack 0xA00000DF,
            # 2.7 s on the game thread, for a lookup that reads 4000 bytes from the start): no record list for a
            # start-only lookup; Data.prepare (server start / queue thread) builds the skipped ones, as before
            # ([ics] record_start_only)
            if name not in self._starts:
                self._lists_skipped.add(name)
            starts = None
        else:
            if name not in self._starts:
                self._build_starts(name)
            starts = self._starts[name]
        # the record header: "did | 0 | count" (world states "did | 7 | entity | 0 | count"); other hits of the
        # DID are references from other records
        k = data.find(struct.pack("<I", did))
        while k >= 0:
            a, b = struct.unpack_from("<II", data, k + 4) if k + 12 <= len(data) else (1, 0)
            c = struct.unpack_from("<I", data, k + 12)[0] if k + 16 <= len(data) else 0
            # 2026-10-22: header 2 also comes as "did | 2 | entity | 0 | count" (the crater pieces 0x2E0002F6-F8)
            if (a == 0 and 0 < b < 400) or (a == 7 and c == 0) or (a in (2, 3, 4) and 0 < b < 400)                     or (a == 2 and b >> 24 == 0x2D and c == 0):
                if starts is None:
                    return data, k, min(len(data), k + 0x4000)
                i = bisect.bisect_right(starts, k)
                nxt = starts[i] if i < len(starts) else len(data)
                return data, k, max(nxt, min(len(data), k + 64))
            k = data.find(struct.pack("<I", did), k + 1)
        return None

    def _build_starts(self, name):
        """A pack's record-start list (what bounds a record). For the big packs (the zone pack: 114 MB, 3711 records)
        that costs half a minute, so a fixed window is used there (2026-10-21)."""
        data = self.packs.pack(name).data
        self._starts[name] = sorted(o for o, _ in self.packs.pack(name).record_starts()) \
            if len(data) < 40_000_000 else None

    def build_skipped_lists(self):
        """The record lists the start-only lookups skipped ([ics] record_start_only), built off the game thread
        (Data.prepare): the lookups that need a record's end (a status' script, a template's script list) then find
        them, as before. Returns the pack names built."""
        todo = sorted(set(self._lists_skipped) - set(self._starts))
        for name in todo:
            self._build_starts(name)
        self._lists_skipped.difference_update(todo)
        return todo

    def _template_end(self, did, data, s, limit=0x8000):
        """Where the template that starts at s ends, for the readers that search past the pack's record list (unit_attack,
        unit_stats): the first word after its header that is a DID of the same pack followed by a record header word
        (0 / 1 / 2 / 3 / 4 / 7) and a count 0 < c < 4096, else s + limit. 7 is harmless: a world state's header
        "did | 7 | entity | 0 | count" never passes the count test. Checked (test-2026-10-28-1439-sweep.md S3 and section
        16): attack, stat block and 0x510 unchanged for the 97 map classes, the tutorial drone, the Destroyer, the
        practice target and the Raider; 7 skill-spawned classes stop taking another record's attack."""
        name = self.index().get(did)
        ids = self._id_sets.get(name)
        if ids is None:
            ids = self._id_sets[name] = frozenset(self.packs.pack(name).ids) if name else frozenset()
        n = min(limit, len(data) - s) // 4
        w = struct.unpack_from("<%dI" % n, data, s)
        for j in range(3, n - 2):
            if w[j] in ids and w[j + 1] in (0, 1, 2, 3, 4, 7) and 0 < w[j + 2] < 4096:
                return s + 4 * j
        return s + 4 * n

    def entity_scripts(self, class_did):
        """The server scripts of an entity class (e.g. a missile 0x40000090 -> [0x3400003F, 0x340001A6])."""
        if class_did in self._scripts:
            return self._scripts[class_did]
        if class_did in self.class_scripts:
            # 2026-10-25 (skill-mechanics-recipes.md 7): a spawned class no template links to its (orphan) script
            self._scripts[class_did] = list(self.class_scripts[class_did])
            return self._scripts[class_did]
        out = []
        rec = self._record(0x49000000 | (class_did & 0xFFFFFF))
        if rec:
            data, start, end = rec
            for m in _SCRIPT_LIST.finditer(data, start, end):
                n = struct.unpack("<I", m.group(1))[0]
                items = [struct.unpack_from("<I", m.group(2), 8 * j + 4)[0] for j in range(len(m.group(2)) // 8)]
                if n == len(items):
                    out = items
                    break
            if not out and self.missile_scripts_past_starts:
                # 2026-10-23 18:00 (champion-kits-status.md 2: 43 of 93 skill projectiles flew with no script): the
                # record-start list also "starts" records inside a template (after 0x510, inside the 0x8E list), so
                # the window ended before the list; search on to the next template header (0x49xxxxxx | 3) or 4 KB
                limit = min(len(data), end + 0x1000)
                for k in range(start + 4, limit - 8, 4):
                    if data[k + 3] == 0x49 and struct.unpack_from("<I", data, k + 4)[0] == 3:
                        limit = k
                        break
                for m in _SCRIPT_LIST.finditer(data, start, limit):
                    n = struct.unpack("<I", m.group(1))[0]
                    items = [struct.unpack_from("<I", m.group(2), 8 * j + 4)[0] for j in range(len(m.group(2)) // 8)]
                    if n == len(items):
                        out = items
                        break
        self._scripts[class_did] = out
        return out

    def status_script(self, status_did):
        """The server script of a status effect record 0x48xxxxxx (property 0x10000242, kind DID), or 0.
        E.g. 0x48000ab0 (applied by Batman's basic attack) -> 0x34000470, which tracks the shot."""
        key = ("status", status_did)
        if key not in self._scripts:
            out = 0
            rec = self._record(status_did)
            if rec:
                data, start, end = rec
                k = data.find(struct.pack("<II", PROP_STATUS_SCRIPT, PROP_STATUS_SCRIPT), start, end)
                if k >= 0:
                    out = struct.unpack_from("<I", data, k + 8)[0]
            self._scripts[key] = out if out >> 24 == 0x34 else 0
        return self._scripts[key]

    def record_u32(self, did, prop):
        """A record's own "prop | prop | u32" value (the first one in its first 6000 bytes), or None. 2026-10-26: the
        vehicles' destruction record 0x800 (0x2E000F04 -> 0x500001F0) read by CDestructionComponent (0x57FCD0)."""
        key = ("u32", did, prop)
        if key not in self._scripts:
            out = None
            rec = self._record(did, need_end=False)
            if rec:
                data, s, _e = rec
                k = data.find(struct.pack("<II", prop, prop), s, s + 6000)
                if k >= 0:
                    out = struct.unpack_from("<I", data, k + 8)[0]
            self._scripts[key] = out
        return self._scripts[key]

    def template_properties(self, entity_did):
        """{property: [values]} of an entity's template 0x49xxxxxx (entries "key | key | value"; an array
        "key | key | count" is followed by its elements, collected under the element's key). 4-byte values only."""
        rec = self._record(0x49000000 | (entity_did & 0xFFFFFF), need_end=False)
        out = {}
        if not rec:
            return out
        data, s, e = rec
        # 2026-10-22 (ics/match: Data.encounter gave map pack 0 for 0x40000C82 / 0x4000013E / 0x40000B6B /
        # 0x40000B6A): templates can run past the pack's record list end, so the record bound cut them short; a
        # template ends at the next template's header "0x49...... | <8 | count"
        n = min(0x3000, len(data) - s) // 4
        w = list(struct.unpack_from("<%dI" % n, data, s))
        nxt = next((j for j in range(1, n - 2) if w[j] >> 24 == 0x49 and w[j + 1] < 8 and 0 < w[j + 2] < 1000), None)
        # no header in the window: read all of it (only "key | key | value" entries are taken, so the next record's
        # words do not produce false keys in practice)
        w = w[:nxt] if nxt is not None else w
        i = 3
        while i < len(w) - 2:
            k = w[i]
            if 0x10000000 <= k < 0x10010000 and (w[i + 1] & 0xBFFFFFFF) == k:
                out.setdefault(k, []).append(w[i + 2])
                i += 3
            elif k == PROP_ENCOUNTER_CHAMPION and w[i + 1] >> 24 == 0x40:
                out.setdefault(k, []).append(w[i + 1])     # an array element: "element key | value"
                i += 2
            else:
                i += 1
        return out

    def encounter(self, encounter_did):
        """Cached encounter_info (it opens big packs: done once, at server start for the known encounters)."""
        with self._enc_lock:
            if encounter_did not in self._encounters:
                self._encounters[encounter_did] = self.encounter_info(encounter_did)
            return self._encounters[encounter_did]

    def encounter_info(self, encounter_did):
        """What an encounter needs, from its template (2026-10-21, client loader 0xA99E20 reads 0x10000406):
        map pack (0x10000406), the packs the map lists (zone, layout, variants, ...), required champions
        (0x10000AE6)."""
        props = self.template_properties(encounter_did)
        map_pack = next((v for v in props.get(PROP_MAP_PACK, []) if v >> 24 == 0xA0), 0)
        champions = [v for v in props.get(PROP_ENCOUNTER_CHAMPION, []) if v >> 24 == 0x40]
        packs = self.map_packs(map_pack) if map_pack else []
        by_category = {}
        for p in packs:
            by_category.setdefault(self.pack_category(p), []).append(p)
        return {"map_pack": map_pack, "packs": packs, "champions": champions,
                "layout_pack": (by_category.get(PACK_LAYOUT) or [0])[0],
                "variants_pack": (by_category.get(PACK_VARIANTS) or [0])[0],
                "zone_packs": by_category.get(PACK_ZONE, [])}

    def pack_category(self, pack_id):
        try:
            with open(os.path.join(self.rp_dir, f"0x{pack_id:08x}.rp"), "rb") as f:
                return struct.unpack_from("<I", f.read(8), 4)[0]
        except (OSError, struct.error):
            return None

    def map_packs(self, map_pack):
        """The packs a map pack depends on: "u32 count | count x pack DID" (Tutorial 1's map 0xA0C112CA:
        zone 0xA000024C, layout 0xA0000256, variants 0xA0000257, 0xA00002D6, 0xA00002D7)."""
        try:
            data = self.packs.pack(map_pack).data
        except OSError:
            return []
        have = {n.lower() for n in os.listdir(self.rp_dir)}
        best = []
        for k in range(0, len(data) - 8, 4):
            n = struct.unpack_from("<I", data, k)[0]
            if not 1 <= n <= 32 or k + 4 + 4 * n > len(data):
                continue
            ids = list(struct.unpack_from("<%dI" % n, data, k + 4))
            if all(x >> 24 == 0xA0 and f"0x{x:08x}.rp" in have for x in ids) and len(ids) > len(best):
                best = ids
        return best

    def world_state_classes(self, enc):
        """{world state: entity class} for an encounter's layout: the entity (0x40...) whose template
        0x49... has property 0x510 = the world state, looked for in the encounter's packs."""
        key = ("wsclasses", enc.get("layout_pack"))
        if key not in self._scripts:
            wanted = sorted({e["wstate"] for e in self.layout(enc["layout_pack"])})
            found = {}
            for pid in [enc.get("layout_pack"), enc.get("variants_pack")] + list(enc.get("zone_packs", ())):
                if not pid:
                    continue
                for ws, cls in rp.entity_classes_for(self.packs.pack(pid), [w for w in wanted if w not in found]).items():
                    found[ws] = cls
            self._scripts[key] = found
        return self._scripts[key]

    def champion_world_state(self, variant):
        """A champion variant's world state (template property 0x510), or 0. Templates run longer than the
        pack's record list says (Gaslight Batman: 0x510 at +0x1C74)."""
        key = ("championws", variant)
        if key not in self._scripts:
            out = 0
            rec = self._record(0x49000000 | (variant & 0xFFFFFF), need_end=False)
            if rec:
                data, s, _e = rec
                k = data.find(struct.pack("<II", 0x510, 0x510), s, s + 0x8000)
                if k >= 0:
                    ws = struct.unpack_from("<I", data, k + 8)[0]
                    out = ws if ws >> 24 == 0x2E else 0
            self._scripts[key] = out
        return self._scripts[key]

    def champion_world_states(self, variants):
        """World states of these champion variants (their layout placements are the player's or cinematic
        actors'). Only the match's champions: reading all 44 opened dozens of packs (69 s, 2026-10-21)."""
        return {ws for ws in (self.champion_world_state(v) for v in variants) if ws}

    def unit_attack(self, class_did):
        """A unit's attack as a Skill: its template's skill script (property 0x10000328, e.g. the tutorial drone
        0x40000C72 -> 0x340004A1, the Destroyer 0x40000EB2 -> 0x3400058F) and stats (0x100004B6 id / 0x100004B7
        base), or None. Templates run past the pack's record list end, so a wide window is read."""
        key = ("attack", class_did)
        if key not in self._scripts:
            out = None
            tpl = 0x49000000 | (class_did & 0xFFFFFF)
            rec = self._record(tpl, need_end=False)
            if rec:
                data, s, _e = rec
                n = min(0x8000, len(data) - s) // 4
                if self.template_window_bounded:
                    # 2026-10-28 15:00 (tester report; docs/re-notes/test-2026-10-28-1439-sweep.md S3: AWW's sweep helper
                    # 0x40000CD6 "attacked" GL x7 with AWW's basic attack 0x34000257, found at +0x4BB4 inside record
                    # 0x480006D4; its template ends at +0x46C): the search stops at the template's end
                    # ([ics] template_window_bounded)
                    n = (self._template_end(tpl, data, s) - s) // 4
                w = struct.unpack_from("<%dI" % n, data, s)
                script = next((w[i + 2] for i in range(n - 2) if w[i] == 0x10000328 and w[i + 1] == 0x10000328), 0)
                if script >> 24 == 0x34:
                    stats = {}
                    for i in range(n - 12):
                        if w[i] == 0x100004B6 and w[i + 1] == 0x100004B6 and w[i + 2] not in stats:
                            j = next((j for j in range(i + 3, min(i + 20, n - 2))
                                      if w[j] == 0x100004B7 and w[j + 1] == 0x100004B7), None)
                            if j is not None:
                                stats[w[i + 2]] = struct.unpack("<f", struct.pack("<I", w[j + 2]))[0]
                    out = Skill({"id": f"0x{class_did:08X}:0", "slot": "0", "key": "Basic", "name": "Attack",
                                 "script": f"0x{script:08X}",
                                 "stats": " ".join(f"{k}={v:g}" for k, v in stats.items())})
            self._scripts[key] = out
        return self._scripts[key]

    def unit_stats(self, class_did):
        """A unit's base stats {stat property: f32} from the stat block its template names (property 0x10000165,
        record "did | 0 | count | key | key | f32 ..."): the tutorial drone 0x40000C72 -> 0x480010EA = Health
        0x10000426 200, Attack Damage 0x10000B76 10, Attack Speed 0x100006FE 1.0, Move Speed 0x100005E4 3.0."""
        key = ("unitstats", class_did)
        if key not in self._scripts:
            out = {}
            tpl = 0x49000000 | (class_did & 0xFFFFFF)
            rec = self._record(tpl, need_end=False) if class_did >> 24 == 0x40 else None
            if rec:
                data, s, _e = rec
                # [ics] template_window_bounded (S3: 0x400005E1 / 0x40000A6C / 0x40000CEB took another record's stat block)
                end = self._template_end(tpl, data, s) if self.template_window_bounded else s + 0x8000
                k = data.find(struct.pack("<II", PROP_STAT_BLOCK, PROP_STAT_BLOCK), s, end)
                block = struct.unpack_from("<I", data, k + 8)[0] if k >= 0 else 0
                brec = self._record(block, need_end=False) if block >> 24 == 0x48 else None
                if brec:
                    bdata, bs, _be = brec
                    n = struct.unpack_from("<I", bdata, bs + 8)[0]
                    p = bs + 12
                    for _ in range(min(n, 64)):
                        a, b = struct.unpack_from("<II", bdata, p)
                        if (b & 0xBFFFFFFF) == a and b == a:
                            out[a] = struct.unpack_from("<f", bdata, p + 8)[0]
                            p += 12
                        elif (b & 0x0FFFFFFF) == (a & 0x0FFFFFFF) and b >> 28 == 5:
                            p += 8                  # "key | 0x5... key": a formula / default, no value here
                        else:
                            break
            self._scripts[key] = out
        return self._scripts[key]

    def target_properties(self, class_did):
        """[(property, kind, value)] the client's attack check needs on a unit (targeting-and-relations.md:
        validator 0x9d01d0): unit flags 0x1000019D, targetable 0x10000AA7, 0x100001C3, 0x1000034C. They are in the
        server-side template 0x49... only, not in the client's records, so the server sends them with the object."""
        key = ("target props", class_did)
        if key not in self._scripts:
            e = self.record(0x49000000 | (class_did & 0xFFFFFF)) if class_did >> 24 == 0x40 else None
            self._scripts[key] = [(k, TARGET_PROPERTY_KINDS[k], v) for k, _kind, v in e or ()
                                  if k in TARGET_PROPERTY_KINDS and v is not None]
        return self._scripts[key]

    def creation_type(self, world_state):
        """A world state's creation type (property 0x50F). 5 = a landblock static (the client never places one sent by
        the server); the "unique" types 1, 4, 6, 7, 8, 9 are what server objects use (client 0x580120)."""
        key = ("ctype", world_state)
        if key not in self._scripts:
            out = None
            rec = self._record(world_state, need_end=False)
            if rec:
                data, s, _e = rec
                k = data.find(struct.pack("<II", 0x50F, 0x50F), s, s + 4000)
                if k >= 0:
                    out = struct.unpack_from("<I", data, k + 8)[0]
            self._scripts[key] = out
        return self._scripts[key]

    def scriptlet_names(self):
        """{scriptlet key: name} from table 0x33000000 (pack 0xA0000038)."""
        key = ("scriptlet names",)
        if key not in self._scripts:
            try:
                runs = rp.name_tables(self.packs.pack(SCRIPTLET_NAMES_PACK))
            except OSError:
                runs = []
            self._scripts[key] = runs[0] if runs else {}
        return self._scripts[key]

    def scriptlet_key(self, name):
        """A scriptlet key by name ("Object_Closed" -> 0x1000034F), or 0."""
        key = ("scriptlet keys",)
        if key not in self._scripts:
            self._scripts[key] = {v: k for k, v in self.scriptlet_names().items()}
        return self._scripts[key].get(name, 0)

    def script_table(self, table_did):
        """{"bases", "keys"} of a scriptlet table 0x1D... (from the first pack that lists it), or None."""
        name = self.index().get(table_did)
        if not name:
            return None
        # 2026-10-26 (deep-scan-maps.md 2: the first pack listing 0x1D0004A0 / A1 (0xA0000162) does not parse them, the
        # next one (0xA000016B) does; the relays' / the cannon's / the Destroyer drone's keys were dropped): every pack
        # that lists the table, in order
        for name in getattr(self, "_table_packs", {}).get(table_did) or [name]:
            with self._tables_lock:
                if name not in self._tables:
                    self._tables[name] = self._cached_tables(name)
                got = self._tables[name].get(table_did)
            if got is not None:
                return got
        return None

    def _cached_tables(self, name):
        """A pack's scriptlet tables, from data/cache/ when the pack file is unchanged (reading a big pack takes
        seconds: 2026-10-21, the session froze while it happened mid-match)."""
        path = os.path.join(self.rp_dir, name)
        try:
            st = os.stat(path)
        except OSError:
            return {}
        stamp = f"{st.st_size}:{int(st.st_mtime)}"
        cache = os.path.join(CACHE_DIR, f"tables_{name}.json")
        try:
            with open(cache, encoding="utf-8") as f:
                saved = json.load(f)
            if saved.get("stamp") == stamp:
                return {int(k): v for k, v in saved["tables"].items()}
        except (OSError, ValueError, KeyError):
            pass
        try:
            tables = rp.script_tables(self.packs.pack(name))
        except (OSError, struct.error, ValueError):
            return {}
        try:
            os.makedirs(CACHE_DIR, exist_ok=True)
            with open(cache, "w", encoding="utf-8") as f:
                json.dump({"stamp": stamp, "tables": {str(k): v for k, v in tables.items()}}, f)
        except OSError:
            pass
        return tables

    def record_tables(self, did):
        """The scriptlet tables a world state or an entity template 0x49... names (property 0x7D2, an array of
        element 0x462 = table DID)."""
        key = ("tables", did)
        if key not in self._scripts:
            out = []
            # start-only ([ics] record_start_only): over 680 templates and world states (spawned, map, champion, layout
            # classes) a start + 32 KB window finds the same tables as the record's true end (test-2026-10-28-1439-sweep.md)
            rec = self._record(0x49000000 | (did & 0xFFFFFF) if did >> 24 == 0x40 else did, need_end=False)
            if rec:
                data, s, e = rec
                # 2026-10-23 20:20 (skill-animations-and-skins.md 5: 0x7D2 sits at +0x1600 or later in some
                # champion templates, so 5+ champions got no tables): read 32 KB into the record
                k = data.find(struct.pack("<II", PROP_SCRIPT_TABLES, PROP_SCRIPT_TABLES), s,
                              min(len(data), max(e, s + 0x8000)))
                if k >= 0:
                    n = struct.unpack_from("<I", data, k + 8)[0]
                    for j in range(min(n, 32)):
                        elem, table = struct.unpack_from("<II", data, k + 12 + 8 * j)
                        if elem == 0x462 and table >> 24 == 0x1D:
                            out.append(table)
            self._scripts[key] = out
        return self._scripts[key]

    def scriptlets(self, class_did, world_state=0, extra_tables=()):
        """Every scriptlet key an object of this class accepts: its tables (the entity's, its world state's, the
        placement's 0x954) and their base tables, recursively."""
        todo = list(extra_tables) + self.record_tables(class_did) + (self.record_tables(world_state)
                                                                      if world_state and world_state != class_did else [])
        seen, keys = set(), []
        while todo:
            t = todo.pop(0)
            if t in seen:
                continue
            seen.add(t)
            tab = self.script_table(t)
            if tab:
                keys += [k for k in tab["keys"] if k not in keys]
                todo += tab["bases"]
        return keys

    def scene(self, scene_did):
        """A cinematic scene record 0x1D... (header "did | 0x1000xxxx | 1 | 0 | cell ..."): its actors' placements,
        then "n events | n x (frame, event) | n vars | u32 | n x (hash, type, value)" and the scene's server script
        (the record's last word, which the pack's record list mistakes for the next record). Returns
        {"script", "events": [(frame, event)], "vars": [(hash, value)]} or None."""
        key = ("scene", scene_did)
        if key in self._scripts:
            return self._scripts[key]
        out = None
        name = self.index().get(scene_did)
        if name:
            pack = self.packs.pack(name)
            data = pack.data
            k = data.find(struct.pack("<I", scene_did))
            while k >= 0:
                a, b, c = struct.unpack_from("<III", data, k + 4)
                if 0x10000000 <= a < 0x10010000 and b == 1 and c == 0:
                    break
                k = data.find(struct.pack("<I", scene_did), k + 1)
            if k >= 0:
                starts = self._starts.get(name)
                if starts is None and len(data) < 40_000_000:
                    starts = self._starts[name] = sorted(o for o, _ in pack.record_starts())
                nxt = starts[bisect.bisect_right(starts, k)] if starts and bisect.bisect_right(starts, k) < len(starts)                     else min(len(data), k + 0x8000)
                n = min((nxt - k) // 4 + 1, (len(data) - k) // 4)
                w = list(struct.unpack_from("<%dI" % n, data, k))
                if w[-1] >> 24 != 0x34 and len(w) > 1 and w[-2] >> 24 == 0x34:
                    w = w[:-1]                      # the next record's DID came along: drop it
                script = w[-1] if w[-1] >> 24 == 0x34 else 0
                events, vars_ = [], []
                if script:
                    # walk back from the script: n_vars | u32 | (hash, type, value) x n_vars, then before it
                    # n_events | (frame, event) x n_events; take the largest layout where both blocks fit
                    for nv in range(15, -1, -1):
                        i = len(w) - 3 - 3 * nv     # index of n_vars
                        if i < 3 or w[i] != nv or any(w[i + 3 + 3 * j] >= 0x40 for j in range(nv)):
                            continue
                        found = None
                        for ne in range(1, 32):
                            e0 = i - 1 - 2 * ne
                            if e0 < 0:
                                break
                            if w[e0] == ne and all(w[e0 + 2 + 2 * j] >> 28 == 1 for j in range(ne)):
                                found = [(w[e0 + 1 + 2 * j], w[e0 + 2 + 2 * j]) for j in range(ne)]
                                break
                        if found is None and nv:
                            continue
                        events = found or []
                        vars_ = [(w[i + 2 + 3 * j], w[i + 4 + 3 * j]) for j in range(nv)]
                        break
                out = {"script": script, "events": events, "vars": vars_}
        self._scripts[key] = out
        return out

    def cinematic_scenes(self, cinematic, layout_pack):
        """The scenes a cinematic plays, through its placements' 0x954 links, recursively (the intro 0x35000026 ->
        0x1D0007A4 -> 0x1D000771 -> 0x1D0007EE ...)."""
        links = {}
        for e in self.layout(layout_pack):
            for s in e.get("props", {}).get(0x954, []):
                links.setdefault(e["record"], []).append(s)
        out, todo = [], [cinematic]
        while todo:
            r = todo.pop(0)
            for s in links.get(r, []):
                if s not in out and s != cinematic:
                    out.append(s)
                    todo.append(s)
        return out

    def status_max_stacks(self, status_did):
        """Property 0x10000063 of a status record: how many can run at once (99 for shot trackers, 1 for a stun)."""
        key = ("stacks", status_did)
        if key not in self._scripts:
            out = 1
            rec = self._record(status_did)
            if rec:
                data, start, end = rec
                k = data.find(struct.pack("<II", 0x10000063, 0x10000063), start, end)
                if k >= 0:
                    out = struct.unpack_from("<I", data, k + 8)[0] or 1
            self._scripts[key] = out
        return self._scripts[key]

    def layout(self, pack_id):
        key = ("layout", pack_id)
        if key not in self._scripts:
            self._scripts[key] = rp.layout_entries(self.packs.pack(pack_id))
        return self._scripts[key]

    def variants(self, pack_id):
        key = ("variants", pack_id)
        if key not in self._scripts:
            self._scripts[key] = rp.variants_for_wstates(self.packs.pack(pack_id))
        return self._scripts[key]

    def prepare(self, enc, classes=()):
        """Read an encounter's layout and variants ahead (they take a few seconds; done at server start and
        while queueing). One thread at a time: two at once doubled the time and slowed the match (2026-10-21).
        classes: what the encounter's flow creates besides the layout (their scriptlet tables, stats and attacks:
        2026-10-21 21:45, the crater's tables, read from a 42 MB pack mid-match, froze the session for 13 s)."""
        with self._prep_lock:
            key = ("prepared", enc.get("map_pack"))
            if key not in self._scripts:
                self._prepare(enc)
                self._scripts[key] = True
            for cls in classes:
                ws = cls if cls >> 24 == 0x2E else self.champion_world_state(cls)
                self.scriptlets(cls, ws)
                if cls >> 24 == 0x40:
                    self.unit_attack(cls)
                    self.unit_stats(cls)
                    self.creation_type(ws)
            # [ics] record_start_only: the record lists these start-only reads used to build, built here (off the game
            # thread) as before, for the later lookups that need a record's end
            self.build_skipped_lists()

    def _prepare(self, enc):
        if enc.get("layout_pack"):
            self.layout(enc["layout_pack"])
        if enc.get("variants_pack"):
            self.variants(enc["variants_pack"])
        if enc.get("layout_pack"):
            self.world_state_classes(enc)
            variants = self.variants(enc["variants_pack"]) if enc.get("variants_pack") else {}
            classes = self.world_state_classes(enc)
            for e in self.layout(enc["layout_pack"]):
                self.creation_type(e["wstate"])
                # the scriptlet tables (a few seconds for the zone pack)
                self.scriptlets(variants.get(e["wstate"]) or classes.get(e["wstate"]) or e["wstate"], e["wstate"],
                                e.get("props", {}).get(0x954, []))
                if variants.get(e["wstate"]):
                    self.unit_attack(variants[e["wstate"]])
                    self.unit_stats(variants[e["wstate"]])
        for v in enc.get("champions", ()):
            self.champion_world_state(v)
