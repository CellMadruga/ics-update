"""Unit numbers from the game data: stat blocks (with their level formulas), the 0x3B formulas and the rewards.

`ics.gamedata.Data.unit_stats` reads only a stat block's fixed values; most minions' Health / Attack Damage / Armour
and every structure's are formulas of the unit's level in the block's 0x1000031A table (units-and-ai.md 2). This
module reads that table and evaluates the formulas the way the client's expression classes do
(units-and-ai.md 3.2 / 3.3):

    0x3B record: did | 1 | 1 | n | n x type | defaults (slot order) | 1 | 0 | n | n x (ELF hash, slot) | n | names
    types: 0 bool, 1 int, 2 uint, 3 float, 4 DID (1 word), 5 / 6 int64, 7 double, 8 IID (2 words), 9 vector (3),
           0xD enum, 0xE bitfield (2 words: table | value)

The families are recognised by their variable names (Linear: Level, Base, Delta; level by time: Time, TimeToLevel,
MaxLevel; kill XP: BaseXP, DeltaXP, GroupBonus; kill credits: BaseValue, DeltaValue, *_RewardPercent,
GroupBonusMultiplier). Formulas whose numbers are constants inside the expression (turret health 2550, team
bounties ...) were read by the survey's decoder (units-and-ai.md 3.4) and are listed in CONSTANT / LEVEL_LINEAR.
"""
import math
import struct

PROP_STAT_BLOCK = 0x10000165
PROP_FORMULAS = 0x1000031A           # array of 0x100002B4 {0x10000319 formula, 0x10000100 stat}
PROP_LEVEL_FORMULA = 0x100001D9
PROP_XP_FORMULA = 0x10000224
PROP_CREDITS_FORMULA = 0x10000689
PROP_TEAM_BOUNTY = 0x10000362
PROP_VISION = 0x10000133
STAT_HEALTH, STAT_ATTACK_DAMAGE, STAT_ATTACK_SPEED, STAT_MOVE_SPEED = 0x10000426, 0x10000B76, 0x100006FE, 0x100005E4

# units-and-ai.md 3.4 "kill-other" (formulas that are one constant; C, decoded by tools/script_decoder.py)
CONSTANT = {0x3B00000E: 200.0, 0x3B000282: 100.0, 0x3B0002C8: 200.0, 0x3B0002CB: 195.0, 0x3B0002CC: 90.0,
            0x3B0002CD: 150.0, 0x3B0002D1: 350.0, 0x3B0002D2: 200.0, 0x3B0002D3: 150.0, 0x3B0002D4: 100.0,
            0x3B000347: 200.0, 0x3B00034A: 350.0, 0x3B000351: 100.0, 0x3B000095: 100.0, 0x3B000096: 1.0,
            0x3B00012F: 3.0}
# units-and-ai.md 3.4 "level-const": a x Level + b (turret / core health and damage)
LEVEL_LINEAR = {0x3B000051: (0, 2550), 0x3B000052: (0, 2550), 0x3B000053: (0, 2700), 0x3B000054: (0, 3000),
                0x3B00009C: (4, 90), 0x3B000107: (20, 100), 0x3B000183: (4, 195), 0x3B000184: (4, 185),
                0x3B000185: (4, 175), 0x3B000186: (4, 200), 0x3B0002CF: (0, 4000), 0x3B0002F5: (0, 6000),
                0x3B00031D: (0, 2700), 0x3B00034D: (0, 4000), 0x3B000394: (4, 175)}
# "N / NumReceivers" formulas (kill-other): turret credits 100 / N, 4 x KillerLevel / N
PER_RECEIVER = {0x3B00025C: lambda v: 100.0 / v["NumReceivers"],
                0x3B0000CE: lambda v: 4.0 * v["KillerLevel"] / v["NumReceivers"],
                # structure kill XP: 5 x KilledLevel x clamp(1 + 0.25 x (KilledLevel - KillerLevel), 0.25, 2) / N
                0x3B000016: lambda v: 5.0 * v.get("KilledLevel", 1) * min(max(
                    1 + 0.25 * (v.get("KilledLevel", 1) - v["KillerLevel"]), 0.25), 2.0) / v["NumReceivers"]}


def elf_hash(name):
    h = 0
    for c in name.encode():
        h = ((h << 4) + c) & 0xFFFFFFFF
        g = h & 0xF0000000
        if g:
            h ^= g >> 24
        h &= ~g & 0xFFFFFFFF
    return h


_WORDS = {0: 1, 1: 1, 2: 1, 3: 1, 4: 1, 5: 2, 6: 2, 7: 2, 8: 2, 9: 3, 0xD: 2, 0xE: 2}


def _f(word):
    return struct.unpack("<f", struct.pack("<I", word))[0]


def parse_formula(data, at):
    """{name: default} of the 0x3B record at `at` (its DID), or None when it does not parse."""
    try:
        n_words = min(512, (len(data) - at) // 4)
        w = struct.unpack_from("<%dI" % n_words, data, at)
        if w[1] != 1 or w[2] != 1 or not 0 < w[3] < 64:
            return None
        n = w[3]
        types = list(w[4:4 + n])
        if any(t not in _WORDS for t in types):
            return None
        p = 4 + n
        defaults = []
        for t in types:
            k = _WORDS[t]
            v = w[p:p + k]
            defaults.append(_f(v[0]) if t == 3 else (v[-1] if t in (0xD, 0xE) else v[0]))
            p += k
        if w[p] != 1 or w[p + 1] != 0 or w[p + 2] != n:
            return None
        pairs = [(w[p + 3 + 2 * i], w[p + 4 + 2 * i]) for i in range(n)]
        p += 3 + 2 * n
        m = w[p]
        p += 1
        raw = bytes(data[at + 4 * p: at + 4 * p + 4 * 200])
        names, q = {}, 0
        for _ in range(m):
            ln = struct.unpack_from("<I", raw, q)[0]
            name = raw[q + 4:q + 4 + ln].decode("ascii", "replace")
            names[elf_hash(name)] = name
            q += 4 + ((ln + 3) // 4) * 4
        # well-known hashed names (units-and-ai.md 3.1: not spelled out in the name table)
        names.update({0x48895: "Base", 0x5B035: "Time", 0x5884B: "Rank", 0x5454: "Mod", 0x4DD4: "SELF"})
        by_slot = sorted(pairs, key=lambda hs: hs[1])
        return {names.get(h, f"{h:#x}"): defaults[i] for i, (h, _slot) in enumerate(by_slot) if i < len(defaults)}
    except (struct.error, IndexError):
        return None


class UnitData:
    """Cached reads over an ics.gamedata.Data."""

    def __init__(self, data):
        self.data = data
        self._formulas, self._blocks, self._tpl = {}, {}, {}

    # ---- raw records -----------------------------------------------------------------------------------------
    def formula(self, did):
        if did not in self._formulas:
            out = None
            name = self.data.index().get(did)
            if name:
                buf = self.data.packs.pack(name).data
                pat = struct.pack("<III", did, 1, 1)
                k = buf.find(pat)
                while k >= 0 and out is None:
                    out = parse_formula(buf, k)
                    k = buf.find(pat, k + 1)
            self._formulas[did] = out
        return self._formulas[did]

    def template(self, cls):
        """{property: [u32 values]} of the class's template 0x49..: every "key | key | value" entry up to the next
        template's header ("0x49...... | 3 | count"). Templates run past the pack's record list end, so
        Data.template_properties misses the minions' reward / level formulas (2026-10-22)."""
        if cls in self._tpl:
            return self._tpl[cls]
        out = {}
        rec = self.data._record(0x49000000 | (cls & 0xFFFFFF)) if cls >> 24 == 0x40 else None
        if rec:
            buf, s, _e = rec
            n = min(0x3000, len(buf) - s) // 4
            w = struct.unpack_from("<%dI" % n, buf, s)
            end = next((i for i in range(1, n - 2) if w[i] >> 24 == 0x49 and w[i + 1] < 8 and 0 < w[i + 2] < 1000), n)
            i = 3
            while i < end - 2:
                k = w[i]
                if (0x10000000 <= k < 0x10010000 or k < 0x1000) and k and w[i + 1] == k:
                    out.setdefault(k, []).append(w[i + 2])
                    i += 3
                else:
                    i += 1
        self._tpl[cls] = out
        return out

    def first(self, cls, prop, default=None):
        v = self.template(cls).get(prop)
        return v[0] if v else default

    def stat_block(self, cls):
        """{"fixed": {stat: f32}, "formulas": {stat: 0x3B DID}} of the class's stat block (0x10000165)."""
        if cls in self._blocks:
            return self._blocks[cls]
        out = {"fixed": {}, "formulas": {}}
        block = self.first(cls, PROP_STAT_BLOCK, 0)
        if not block:
            # Data.template_properties misses it on some templates (cores): look for the pair by hand
            rec = self.data._record(0x49000000 | (cls & 0xFFFFFF))
            if rec:
                buf, s, _e = rec
                k = buf.find(struct.pack("<II", PROP_STAT_BLOCK, PROP_STAT_BLOCK), s, s + 0x8000)
                block = struct.unpack_from("<I", buf, k + 8)[0] if k >= 0 else 0
        rec = self.data._record(block) if block >> 24 == 0x48 else None
        if rec:
            buf, s, _e = rec
            n = struct.unpack_from("<I", buf, s + 8)[0]
            p = s + 12
            for _ in range(min(n, 64)):
                a, b = struct.unpack_from("<II", buf, p)
                if a == PROP_FORMULAS and b == PROP_FORMULAS:
                    count = struct.unpack_from("<I", buf, p + 8)[0]
                    p += 12
                    for _t in range(min(count, 32)):
                        _key, _zero, m = struct.unpack_from("<III", buf, p)
                        p += 12
                        entry = {}
                        for _e2 in range(min(m, 8)):
                            k1, k2, v = struct.unpack_from("<III", buf, p)
                            entry[k1] = v
                            p += 12
                        if entry.get(0x10000319, 0) >> 24 == 0x3B and entry.get(0x10000100):
                            out["formulas"][entry[0x10000100]] = entry[0x10000319]
                elif b == a:
                    out["fixed"][a] = _f(struct.unpack_from("<I", buf, p + 8)[0])
                    p += 12
                elif (b & 0x0FFFFFFF) == (a & 0x0FFFFFFF) and b >> 28 in (4, 5):
                    p += 8
                else:
                    break
        self._blocks[cls] = out
        return out

    # ---- evaluation --------------------------------------------------------------------------------------------
    def evaluate(self, did, **inputs):
        """A formula's value for the given inputs (Level, Time, KilledLevel, KillerLevel, NumReceivers, LastHit,
        DamagedByTurret ...), or None when the formula is not one of the known families."""
        if not did:
            return None
        if did in CONSTANT:
            return CONSTANT[did]
        if did in LEVEL_LINEAR:
            a, b = LEVEL_LINEAR[did]
            return a * float(inputs.get("Level", 1)) + b
        v = dict(self.formula(did) or {})
        if did in PER_RECEIVER:
            v.update({"NumReceivers": 1, "KillerLevel": 1})
            v.update(inputs)
            v["NumReceivers"] = max(1, v["NumReceivers"])
            return PER_RECEIVER[did](v)
        if not v:
            return None
        v.update(inputs)
        n = max(1, int(v.get("NumReceivers", 1) or 1))

        def linear(level, base, delta):
            return base + (level - 1) * delta

        if "TimeToLevel" in v:
            ttl = float(v["TimeToLevel"]) or 90.0
            return float(min(max(int(math.floor((float(v.get("Time", 0)) + ttl) / ttl)), 1), int(v.get("MaxLevel", 100))))
        if "Delta" in v and "Base" in v:
            return linear(float(v.get("Level", v.get("Rank", 1))), float(v["Base"]), float(v["Delta"]))
        if "BaseXP" in v:
            killed, killer = float(v.get("KilledLevel", 1)), float(v.get("KillerLevel", 1))
            xp = linear(killed, float(v["BaseXP"]), float(v.get("DeltaXP", 0)))
            if "PercentLevelToGain" in v:      # champion kills (0x3B000003)
                xp *= float(v["PercentLevelToGain"]) * min(max(1 + 0.25 * (killed - killer), 0.25), 2.0)
            bonus = float(v.get("GroupBonus", 1.0)) if n > 1 else 1.0
            return xp * bonus / n
        if "BaseValue" in v:
            killed = float(v.get("KilledLevel", 1))
            value = linear(killed, float(v["BaseValue"]), float(v.get("DeltaValue", 0)))
            group = min(max(float(v.get("GroupBonusMultiplier", 1.0)), 1.0), 1.2) if n > 1 else 1.0
            if inputs.get("DamagedByTurret"):
                share = float(v.get("TurretValue_RewardPercent", 1.0))
            elif inputs.get("LastHit", True):
                share = float(v.get("LastHitValue_RewardPercent", 1.0))
            else:
                share = float(v.get("CharacterValue_RewardPercent", 1.0))
            return group * value / n * share
        return None

    # ---- a unit's numbers ----------------------------------------------------------------------------------------
    def level_at(self, cls, seconds):
        """The unit's level after `seconds` of match time (its 0x100001D9 formula: +1 every 90 s), else 1."""
        lv = self.evaluate(self.first(cls, PROP_LEVEL_FORMULA, 0), Time=float(seconds))
        return int(lv) if lv else 1

    def stats_at(self, cls, level):
        """{stat: value} at this level: the block's fixed stats plus its formulas."""
        blk = self.stat_block(cls)
        out = dict(blk["fixed"])
        for stat, did in blk["formulas"].items():
            val = self.evaluate(did, Level=level)
            if val is not None:
                out[stat] = float(val)
        return out

    def vision(self, cls, default=0.0):
        """Vision radius 0x10000133 (f32): the largest of the template's values (the 0x10000A3C detection table
        carries a 3.0 of its own)."""
        vals = [_f(x) for x in self.template(cls).get(PROP_VISION, [])]
        vals = [x for x in vals if 0 < x < 100]
        return max(vals) if vals else default

    def reward(self, cls, prop, **inputs):
        did = self.first(cls, prop, 0)
        return self.evaluate(did, **inputs) if did >> 24 == 0x3B else None
