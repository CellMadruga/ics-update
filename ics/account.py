"""One player account: what the server keeps between logins and the account screens' data.

docs/re-notes/full-account-social.md section 10 lists what the original server persisted; this module keeps the same
stores in one JSON file per account, data/accounts/<name>.json ([ics] account_dir; gitignored like data/progress.json):

  account       name, IID, created (unix s), first login day
  progression   account level / XP; per champion level / XP / last used (ranked / unranked)
  wallet        Crisis Coins (hard), Merits (soft), last daily first-win bonus, win streak
  ownables      DID -> {type (ContentType), count}      (champions, skins, Stolen Powers, icons, amplifiers, slots)
  loadouts      amplifier sets [{slot, champion, name, icon, amplifiers[7]}], max sets; Stolen Power pair per champion
  achievements  DID -> {times, current {objective: n}, previous {...}, updated, acknowledged, valid_until}
  rewards       pending [{instance, set, source, source_type, items [[item, qty, bestowal]]}], claimed [instance],
                next instance id; login calendar last claimed day
  accolades     best per map / champion (empty until accolades are computed)
  stats         per encounter: played, won, ranked played / won
  ranked        per encounter: rank, sub-rank, position, streak
  profile       5 protector icon slots, status message
  social        contacts, groups, ignored names
  preferences   name -> [kind, value text]   (client 0x216E; sent back with 0x216A)
  encounters    completed encounter DIDs, last map played

Nothing of the game's text is stored (names are the player's own; achievement and reward contents are DIDs read
from the install). Amounts the client data does not hold (XP curve, Merits per match, prices) are [ics] settings.
"""
import csv
import json
import os
import re
import struct
import threading
import time

from . import messages as M
from . import records

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CATALOG = os.path.join(ROOT, "catalog", "data")
ACCOUNT_IID = M.LOCAL_PLAYER_ID            # the account is the local player object (0x0200000000000001)
VERSION = 1

# ContentType (account-systems-data.md 2.1)
CT_CHARACTER, CT_STOLEN_POWER, CT_ICON, CT_SKIN, CT_AMP_SLOT, CT_SKILL = 1, 2, 3, 4, 5, 9
CT_AUGMENT, CT_MOD, CT_ACHIEVEMENT = 12, 13, 17
STATUS_AVAILABLE, STATUS_HIDDEN = 2, 5
# reward items (account-systems-data.md 3.3): currency / XP records
MERIT_ITEMS = {0x48000722, 0x48000CD7, 0x48000D62, 0x4800152C}
COIN_ITEMS = {0x48000723, 0x48000D61, 0x48000E3D, 0x4800152D}
XP_FLAT_ITEM, XP_PERCENT_ITEM = 0x48000F31, 0x48000F30
# reward bestowal (RewardBestowalType) and source types
BESTOW_CHOICE, BESTOW_GRANT, BESTOW_AUTO = 1, 2, 3
SOURCE_ACHIEVEMENT, SOURCE_LOGIN = 1, 2
# achievement objective types (AchievementObjectiveType, account-systems-data.md 3.1)
OBJ_PROTECTOR_LEVEL, OBJ_KILL, OBJ_MATCH_COMPLETE, OBJ_MATCH_WIN, OBJ_GAME = 1, 2, 3, 4, 5
OBJ_CHARACTER_CYCLE, OBJ_CHARACTER_LEVEL5, OBJ_MM_COMPLETE, OBJ_MM_WIN, OBJ_CHAMPION_LEVEL, OBJ_CHAMPION_OWNED = (
    6, 7, 8, 9, 10, 11)
CATEGORY_GENERAL, CATEGORY_TRAINING, CATEGORY_PROTECTOR_LEVEL, CATEGORY_CHAMPION_LEVEL = 1, 2, 3, 4
REPEAT_NEVER, REPEAT_DAILY, REPEAT_WEEKLY, REPEAT_MONTHLY, REPEAT_BIWEEKLY = 1, 2, 3, 4, 5
REPEAT_SECONDS = {REPEAT_DAILY: 86400, REPEAT_WEEKLY: 7 * 86400, REPEAT_MONTHLY: 30 * 86400,
                  REPEAT_BIWEEKLY: 14 * 86400}

ACHIEVEMENT_MASTER_LIST = 0x48000CF0       # 0x1000099F entries (the client's 0x100000B7)
LOGIN_CALENDAR = 0x48001528                # 0x10000D94 entries {0x10000D93 reward set, 0x10000D92 day}
AMP_SLOT_ITEM = 0x49000AA2                 # "Amplifier Set Slot" (ContentType 5)


def _tsv(name):
    try:
        with open(os.path.join(CATALOG, name), encoding="utf-8") as f:
            return list(csv.DictReader(f, delimiter="\t"))
    except OSError:
        return []


def _hex(v):
    return f"0x{int(v):08X}"


# ---- what the install holds (cached on the Data object) ---------------------------------------------------------
class AccountData:
    """Readers of the account systems' records (achievements, reward sets, the login calendar, amplifiers, Stolen
    Powers). One per Data object."""

    def __init__(self, data):
        self.data = data
        self._cache = {}
        self._lock = threading.Lock()

    @classmethod
    def of(cls, data):
        ad = getattr(data, "_account_data", None)
        if ad is None:
            ad = cls(data)
            try:
                data._account_data = ad
            except AttributeError:
                pass
        return ad

    def _memo(self, key, fn):
        with self._lock:
            if key not in self._cache:
                self._cache[key] = fn()
            return self._cache[key]

    def _record_type1(self, did):
        """A "did | 1 | n" record (achievements), which Data.record does not read."""
        name = self.data.index().get(did)
        if not name:
            return None
        blob = self.data.packs.pack(name).data
        pat = struct.pack("<I", did)
        k = blob.find(pat)
        while k >= 0:
            if k + 12 <= len(blob) and struct.unpack_from("<I", blob, k + 4)[0] == 1:
                out = records.read_at(blob, k, self.data._all_kinds)
                if out:
                    return out
            k = blob.find(pat, k + 1)
        return None

    def achievements(self):
        """[{did, category, repeat, reward_set, objectives: [{index, type, target, encounter}]}] of the master list."""
        def read():
            out, seen = [], set()
            for _k, _kind, did in records.get(self.data.record(ACHIEVEMENT_MASTER_LIST), 0x1000099F) or []:
                if not did or did in seen:
                    continue
                seen.add(did)
                e = self._record_type1(0x49000000 | (did & 0xFFFFFF))
                if not e:
                    continue
                objs = []
                for _ok, _okind, ob in records.get(e, 0x10000A2D) or []:
                    d = records.as_dict(ob)
                    objs.append({"index": int(d.get(0x10000A2B) or 1), "type": int(d.get(0x10000A30) or 0),
                                 "target": int(d.get(0x10000A2F) or 1), "encounter": int(d.get(0x10000B0A) or 0)})
                out.append({"did": did, "category": int(records.get(e, 0x10000C25) or 0),
                            "repeat": int(records.get(e, 0x10000A28) or REPEAT_NEVER),
                            "reward_set": int(records.get(e, 0x10000A5C) or 0),
                            "champion_index": int(records.get(e, 0x10000A27) or 0), "objectives": objs})
            return out
        return self._memo("achievements", read)

    def reward_set(self, set_did):
        """[{group, bestowal, items: [(item DID, quantity)]}] of a reward set (0x10000A1F -> groups 0x10000A1D)."""
        def read():
            groups = []
            e = self.data.record(0x49000000 | (set_did & 0xFFFFFF))
            for _k, _kind, el in records.get(e, 0x10000A1F) or []:
                gdid = records.as_dict(el).get(0x10000A1B) or 0
                g = self.data.record(0x49000000 | (gdid & 0xFFFFFF)) if gdid else None
                items = []
                for _ik, _ikind, it in records.get(g, 0x10000A1D) or []:
                    d = records.as_dict(it)
                    item = d.get(0x10000A1A) or d.get(0x10000AB7) or 0
                    if item:
                        items.append((int(item), int(d.get(0x10000A36) or 1)))
                groups.append({"group": gdid, "bestowal": int(records.get(g, 0x10000A4D) or BESTOW_GRANT),
                               "items": items})
            return groups
        return self._memo(("reward set", set_did), read)

    def login_calendar(self):
        """[(day, reward set)] in day order (the first entry has no day: day 0)."""
        def read():
            out = []
            for _k, _kind, el in records.get(self.data.record(LOGIN_CALENDAR), 0x10000D94) or []:
                d = records.as_dict(el)
                if d.get(0x10000D93):
                    out.append((int(d.get(0x10000D92) or 0), int(d[0x10000D93])))
            return sorted(out)
        return self._memo("calendar", read)

    def amplifiers(self):
        """{DID: ContentType 12 augment / 13 mod} (catalog amplifiers.tsv, read from the install by the catalog)."""
        return self._memo("amplifiers", lambda: {int(r["id"], 16): CT_AUGMENT if r.get("type") == "augment" else CT_MOD
                                                 for r in _tsv("amplifiers.tsv") if r.get("id", "").startswith("0x")})

    def amplifier_stats(self, did):
        """An augment's stat lines [(op 9 add / 10 percent, stat key, value)] from its twin's 0x10000950 entries
        (0x10000952 op, 0x10000958 stat, 0x10000954 value; account-systems-data.md 1.1, C). Mods have none."""
        def read():
            e = self.data.record(0x49000000 | (did & 0xFFFFFF))
            out = []
            for _k, _kind, el in records.get(e, 0x10000950) or []:
                d = records.as_dict(el)
                if d.get(0x10000958) and d.get(0x10000954) is not None:
                    out.append((int(d.get(0x10000952) or 9), int(d[0x10000958]), float(d[0x10000954])))
            return out
        return self._memo(("amp stats", did), read)

    def stolen_powers(self):
        """{power DID: (group, base power?)} (catalog stolen_powers.tsv)."""
        return self._memo("stolen", lambda: {int(r["id"], 16): (int(r.get("group") or 0), "base" in r.get("champion", ""))
                                             for r in _tsv("stolen_powers.tsv") if r.get("id", "").startswith("0x")})

    def protector_icons(self):
        """Every protector icon item (WC DID) the profile picker offers: record 0x48000803 property 0x10000848, elements
        0x10000847 (134 entries; docs/re-notes/profile-icons.md, C)."""
        def read():
            r = self.data.record(0x48000803)
            return [int(v) for k, _kind, v in records.get(r, 0x10000848) or () if k == 0x10000847 and v]
        return self._memo("protector icons", read)

    def is_icon(self, did):
        """An avatar (protector) icon item: its twin has 0x10000AB9."""
        def read():
            e = self.data.record(0x49000000 | (did & 0xFFFFFF))
            return any(k == 0x10000AB9 for k, _kind, _v in e or ())
        return self._memo(("icon", did), read)

    def encounter_template(self, did):
        """{players_per_team, humans, category, bot_pool, select_seconds, name} of an encounter template."""
        def read():
            e = self.data.record(0x49000000 | (did & 0xFFFFFF))
            pool = [v for _k, _kind, v in records.get(e, 0x10000B3E) or [] if v]
            return {"players_per_team": int(records.get(e, 0x10000BCB) or 1),
                    "humans": int(records.get(e, 0x10000BCC) or 1),
                    "category": int(records.get(e, 0x10000D0B) or 0),
                    "bot_pool": pool,
                    "select_seconds": float(records.get(e, 0x100004A1) or 0.0),
                    "required": [v for _k, _kind, v in records.get(e, 0x10000AE7) or [] if v]}
        return self._memo(("encounter", did), read)


# ---- the account ----------------------------------------------------------------------------------------------------
def _safe_name(name):
    return re.sub(r"[^A-Za-z0-9_.-]", "_", name or "Player")[:40] or "Player"


def account_dir(ic):
    return ic.get("account_dir") or os.path.join(ROOT, "data", "accounts")


class Account:
    """One account's stores (see the module docstring); load() / save() keep them in data/accounts/<name>.json."""

    def __init__(self, name, ic, path=None):
        self.name, self.ic = name, ic
        self.path = path or os.path.join(account_dir(ic), _safe_name(name) + ".json")
        self.d = self._new()
        self.lock = threading.RLock()

    # ---- persistence ------------------------------------------------------------------------------------------
    def _new(self):
        now = int(time.time())
        ic = self.ic
        return {
            "version": VERSION, "name": self.name, "iid": ACCOUNT_IID, "created": now,
            "first_login_day": now // 86400,
            "level": int(ic.get("account_level", 30) or 1), "xp": 0,
            "champions": {},
            "wallet": {"hard": int(ic.get("start_crisis_coins", 0) or 0), "soft": int(ic.get("start_merits", 0) or 0),
                       "last_daily": 0, "streak": 0},
            "owned": {},
            "amplifier_sets": [], "max_amplifier_sets": int(ic.get("amplifier_set_slots", 6) or 6),
            "amplifier_selected": {},        # champion -> set slot picked in a lobby (0 = the default set)
            "stolen_powers": {},
            "achievements": {},
            "rewards": {"pending": [], "claimed": [], "next_instance": 1, "login_last_day": -1},
            "accolades": {"map": {}, "champion": {}},
            "stats": {}, "ranked": {},
            "profile": {"icons": [0, 0, 0, 0, 0], "status": ""},
            "social": {"contacts": [], "groups": [], "ignored": [], "next_group": 1},
            "preferences": {},
            "encounters": {"completed": [], "last": 0},
        }

    @classmethod
    def load(cls, name, ic):
        acct = cls(name, ic)
        try:
            with open(acct.path, encoding="utf-8") as f:
                stored = json.load(f)
            base = acct._new()
            base.update({k: v for k, v in stored.items() if k in base})
            acct.d = base
            acct.loaded = True
        except (OSError, ValueError):
            acct.loaded = False
            acct._migrate_progress()
        default = int(str(ic.get("default_protector_icon", "0x40000AE3")), 0)
        icons = acct.d.setdefault("profile", {}).setdefault("icons", [0, 0, 0, 0, 0])
        if default and icons and not icons[0]:
            # 2026-10-25 (profile-icons.md 3.4, P): slot 0 is the icon the scorecard / accolades show; an account without
            # one gets the list's first icon
            icons[0] = default
        return acct

    def _migrate_progress(self):
        """A new account takes the completed tutorials of the earlier data/progress.json (ics/matchend.py)."""
        path = self.ic.get("progress_file") or os.path.join(ROOT, "data", "progress.json")
        try:
            with open(path, encoding="utf-8") as f:
                done = [int(x) for x in json.load(f).get("completed", [])]
        except (OSError, ValueError):
            done = []
        self.d["encounters"]["completed"] = done
        if done:
            self.d["encounters"]["last"] = done[-1]

    def save(self):
        with self.lock:
            try:
                os.makedirs(os.path.dirname(self.path), exist_ok=True)
                tmp = self.path + ".tmp"
                with open(tmp, "w", encoding="utf-8") as f:
                    json.dump(self.d, f, indent=1, sort_keys=True)
                os.replace(tmp, self.path)
                return True
            except OSError:
                return False

    # ---- progression -----------------------------------------------------------------------------------------
    def xp_to_next(self, level, champion=False):
        """XP from level to level + 1: [ics] account_xp_curve / champion_xp_curve = [base, per level] (the curve
        is not in the client data, account-systems-data.md 3.7)."""
        base, step = self.ic.get("champion_xp_curve" if champion else "account_xp_curve", [1000, 100])
        return int(base) + int(step) * max(0, int(level) - 1)

    def add_account_xp(self, amount):
        """Returns (previous level, previous XP into the level)."""
        with self.lock:
            prev = (self.d["level"], self.d["xp"])
            self.d["xp"] += max(0, int(amount))
            cap = int(self.ic.get("account_level_cap", 100) or 100)
            while self.d["level"] < cap and self.d["xp"] >= self.xp_to_next(self.d["level"]):
                self.d["xp"] -= self.xp_to_next(self.d["level"])
                self.d["level"] += 1
            return prev

    def champion(self, did):
        return self.d["champions"].setdefault(_hex(did), {"level": 1, "xp": 0, "last_used": 0, "last_ranked": 0})

    def add_champion_xp(self, did, amount, ranked=False):
        with self.lock:
            c = self.champion(did)
            prev = (c["level"], c["xp"])
            c["xp"] += max(0, int(amount))
            cap = int(self.ic.get("champion_level_cap", 20) or 20)
            while c["level"] < cap and c["xp"] >= self.xp_to_next(c["level"], True):
                c["xp"] -= self.xp_to_next(c["level"], True)
                c["level"] += 1
            c["last_ranked" if ranked else "last_used"] = int(time.time())
            return prev

    # ---- ownables ----------------------------------------------------------------------------------------------
    def owns(self, did):
        return _hex(did) in self.d["owned"]

    def own(self, did, ctype, count=1):
        with self.lock:
            o = self.d["owned"].setdefault(_hex(did), {"type": int(ctype), "count": 0})
            o["count"] += int(count)
            return o

    def not_owned_by_default(self, did):
        """[ics] own_all_except: a DID that own_all_champions / own_all_skins do not cover (bought only)."""
        return _hex(did) in {_hex(int(str(v), 16) if isinstance(v, str) else v)
                             for v in self.ic.get("own_all_except", []) or []}

    def skin_owned(self, did):
        if self.ic.get("own_all_skins", True) and not self.not_owned_by_default(did):
            return True
        return self.owns(did)

    def apply_grants(self):
        """[ics] account_grants: one-time Merits / Crisis Coins, each id once per account. Returns the ids applied."""
        done = []
        with self.lock:
            seen = self.d["wallet"].setdefault("grants", [])
            for g in self.ic.get("account_grants", []) or []:
                gid = str(g.get("id", ""))
                if not gid or gid in seen:
                    continue
                self.d["wallet"]["soft"] += int(g.get("soft", 0) or 0)
                self.d["wallet"]["hard"] += int(g.get("hard", 0) or 0)
                seen.append(gid)
                done.append(gid)
        return done

    def champion_owned(self, variant, roster_champions=()):
        if self.ic.get("own_all_champions", True) and not self.not_owned_by_default(variant):
            return True
        starters = {int(str(v), 16) if isinstance(v, str) else int(v) for v in self.ic.get("starter_champions", [])}
        return variant in starters or self.owns(variant)

    def ownable_items(self, roster, adata, changed=None):
        """The 0x20B8 list: every roster champion (type 1), skin (4) and skills pseudo-item (9, hidden), then the
        account's other ownables (Stolen Powers 2, icons 3, set slots 5, augments 12, mods 13). changed = only
        these DIDs (an incremental delivery)."""
        items = []
        for c in roster:
            items.append((c["variant"], STATUS_AVAILABLE, CT_CHARACTER, self.champion_owned(c["variant"]), 1))
            for s in c.get("costume_info", []):
                owned = self.skin_owned(s["variant"])
                items.append((s["variant"], STATUS_AVAILABLE, CT_SKIN, owned, 1))
            items.append((c["skills_key"], STATUS_HIDDEN, CT_SKIN, False, 1))
        if self.ic.get("ownables_extra_types", True):
            if self.ic.get("grant_all_amplifiers", True):
                for did, ct in sorted(adata.amplifiers().items()):
                    if not self.owns(did):
                        items.append((did, STATUS_AVAILABLE, ct, True, 1))
            if self.ic.get("send_protector_icons", True):
                # 2026-10-25 (tester: the profile icons cannot be customized; profile-icons.md, C): the picker lists the
                # type-3 items of 0x20B8 only, and none were sent (nothing owned); every icon goes, owned when
                # [ics] own_all_icons, else locked with its unlock text
                for did in adata.protector_icons():
                    if not self.owns(did):
                        items.append((did, STATUS_AVAILABLE, CT_ICON, bool(self.ic.get("own_all_icons", True)), 1))
            if self.ic.get("grant_all_stolen_powers", True):
                for did in sorted(adata.stolen_powers()):
                    if not self.owns(did):
                        items.append((did, STATUS_AVAILABLE, CT_STOLEN_POWER, True, 1))
            for key, o in sorted(self.d["owned"].items()):
                if o["type"] in (CT_CHARACTER, CT_SKIN):
                    continue
                items.append((int(key, 16), STATUS_AVAILABLE, o["type"], True, max(1, o["count"])))
            if self.ic.get("amplifier_slot_for_sale", True) and not self.owns(AMP_SLOT_ITEM):
                # 2026-10-28 (store-amplifiers.md): the Assembler's "buy a set slot" row takes the first type-5 ownable
                items.append((AMP_SLOT_ITEM, STATUS_AVAILABLE, CT_AMP_SLOT, False, 1))
        if changed is not None:
            items = [i for i in items if i[0] in changed]
        return items

    # ---- wallet ------------------------------------------------------------------------------------------------
    @property
    def wallet(self):
        return self.d["wallet"]

    def spend(self, currency, amount):
        # "HC" = Crisis Coins in the client's purchase messages (store-fix.md 3.2); anything else = Merits
        key = "hard" if str(currency).lower() in ("hard", "hc", "crisiscoins", "crisis coins", "coins") else "soft"
        with self.lock:
            if self.wallet[key] < amount:
                return False
            self.wallet[key] -= int(amount)
            return True

    # ---- grants (rewards, store) -----------------------------------------------------------------------------
    def grant(self, item, qty, adata, roster):
        """Give one reward / store item. Returns the DIDs whose ownable status changed (for an incremental 0x20B8)."""
        changed = set()
        with self.lock:
            if item in MERIT_ITEMS:
                self.wallet["soft"] += qty
            elif item in COIN_ITEMS:
                self.wallet["hard"] += qty
            elif item == XP_FLAT_ITEM:
                self.add_account_xp(qty * int(self.ic.get("account_xp_item_flat", 100) or 0))
            elif item == XP_PERCENT_ITEM:
                self.add_account_xp(qty * self.xp_to_next(self.d["level"]) // 10)
            elif any(c["variant"] == item for c in roster):
                self.own(item, CT_CHARACTER)
                changed.add(item)
            elif any(s["variant"] == item for c in roster for s in c.get("costume_info", [])):
                self.own(item, CT_SKIN)
                changed.add(item)
            elif item in adata.amplifiers():
                self.own(item, adata.amplifiers()[item], qty)
                changed.add(item)
            elif item in adata.stolen_powers():
                self.own(item, CT_STOLEN_POWER)
                changed.add(item)
            elif item == AMP_SLOT_ITEM or item == (AMP_SLOT_ITEM & 0x00FFFFFF | 0x40000000):
                self.d["max_amplifier_sets"] += qty
                self.own(item, CT_AMP_SLOT, qty)
                changed.add(item)
            else:
                # avatar icons (twin 0x10000AB9) and anything not typed above: kept as an icon-type ownable
                self.own(item, CT_ICON, qty)
                changed.add(item)
        return changed

    # ---- loadouts ----------------------------------------------------------------------------------------------
    def amplifier_sets(self, champion=None):
        """The saved sets; for a champion, its own sets and the sets made for no champion (DID 0)."""
        sets = self.d["amplifier_sets"]
        return [s for s in sets if champion is None or s["champion"] in (champion, 0)]

    def amplifier_sets_msg(self):
        """0x2090: total = the account's set slots ([ics] amplifier_sets_total_slots; the client fills the rows after
        the saved sets with empty client-only sets it can edit and save), max = [ics] amplifier_set_max."""
        sets = [M.amplifier_set(s["slot"], s.get("id", s["slot"]), s["champion"], s.get("name", ""), s.get("icon", 0),
                                (list(s["amplifiers"]) + [0] * 7)[:7]) for s in self.amplifier_sets()]
        slots = int(self.d["max_amplifier_sets"])
        if self.ic.get("amplifier_sets_total_slots", True):
            total = max(len(sets), slots, max((s["slot"] for s in self.amplifier_sets()), default=0))
            maximum = max(total, int(self.ic.get("amplifier_set_max", 12) or 0))
        else:
            total, maximum = len(sets), slots
        return M.amplifier_sets_list(total, maximum, sets)

    def select_amplifier_set(self, champion, slot):
        with self.lock:
            self.d.setdefault("amplifier_selected", {})[_hex(champion)] = int(slot)

    def chosen_amplifier_set(self, champion):
        """The set picked for this champion in a lobby (0x2098; slot 0 = its default set -> None), else its newest
        saved set, else None (the caller uses the default loadout)."""
        sets = self.amplifier_sets(champion)
        slot = self.d.get("amplifier_selected", {}).get(_hex(champion))
        if slot == 0:
            return None
        return next((s for s in sets if s["slot"] == slot), None) or (sets[-1] if sets else None)

    def amplifier_bonuses(self, adata, amp_set):
        """({stat: add}, {stat: percent}) of a set's augments (mods give no champion stat)."""
        add, pct = {}, {}
        for did in (amp_set or {}).get("amplifiers", []):
            for op, stat, v in adata.amplifier_stats(did) if did else ():
                table = pct if op == 10 else add
                table[stat] = table.get(stat, 0.0) + v
        return add, pct

    def save_amplifier_set(self, slot, champion, name, icon, amps):
        """Stores a set (slot 0 = the next free slot). Returns the stored set, or None (no slot left)."""
        with self.lock:
            sets = self.d["amplifier_sets"]
            if not slot:
                used = {s["slot"] for s in sets}
                slot = next((i for i in range(1, self.d["max_amplifier_sets"] + 1) if i not in used), 0)
                if not slot:
                    return None
            if slot > self.d["max_amplifier_sets"]:
                return None
            amps = (list(amps) + [0] * 7)[:7]
            entry = {"slot": int(slot), "champion": int(champion), "name": name, "icon": int(icon), "amplifiers": amps,
                     "id": int(slot)}
            self.d["amplifier_sets"] = [s for s in sets if s["slot"] != slot] + [entry]
            self.d["amplifier_sets"].sort(key=lambda s: s["slot"])
            return entry

    def default_amplifier_set(self, data, champion):
        """The champion's default set from its loadout record (4 augments + 3 mods, account-systems-data.md 1.3)."""
        lo = data.loadout(champion) if champion else {}
        amps = (list(lo.get("augments", []))[:4] + list(lo.get("mods", []))[:3] + [0] * 7)[:7]
        return {"slot": 0, "champion": champion, "name": "", "icon": 0, "amplifiers": amps, "id": 0}

    def stolen_pair(self, data, champion):
        pair = self.d["stolen_powers"].get(_hex(champion))
        if pair:
            return [int(pair[0]), int(pair[1])]
        st = list(data.loadout(champion).get("stolen", [])) if champion else []
        return (st + [0, 0])[:2]

    def set_stolen_power(self, data, champion, slot, power):
        with self.lock:
            pair = self.stolen_pair(data, champion)
            if slot in (0, 1):
                pair[slot] = int(power)
            self.d["stolen_powers"][_hex(champion)] = pair
            return pair

    # ---- encounters ---------------------------------------------------------------------------------------------
    @property
    def completed(self):
        return [int(x) for x in self.d["encounters"]["completed"]]

    def complete_encounter(self, did):
        with self.lock:
            done = [x for x in self.completed if x != did] + [did]
            self.d["encounters"]["completed"] = done
            self.d["encounters"]["last"] = did
            return done

    def record_match(self, encounter, won, ranked=False):
        with self.lock:
            s = self.d["stats"].setdefault(_hex(encounter), {"played": 0, "won": 0, "ranked_played": 0,
                                                             "ranked_won": 0, "kills": 0, "deaths": 0})
            s["ranked_played" if ranked else "played"] += 1
            if won:
                s["ranked_won" if ranked else "won"] += 1
                self.wallet["streak"] += 1
            else:
                self.wallet["streak"] = 0
            return s

    # ---- preferences ------------------------------------------------------------------------------------------
    def set_preference(self, name, value, kind):
        with self.lock:
            self.d["preferences"][name] = [int(kind), value]

    def server_options(self):
        """The bool / number preferences for 0x216A (string ones stay on the client: no string type in its reader)."""
        out = []
        for name, (kind, value) in sorted(self.d["preferences"].items()):
            try:
                name.encode("ascii")
            except UnicodeEncodeError:
                continue
            if kind == 0x10000C33:
                out.append((name, M.SERVER_OPTION_BOOL, str(value).strip().lower() in ("1", "true", "yes", "on")))
            elif kind == 0x10000A0E:
                try:
                    f = float(value)
                except ValueError:
                    continue
                if f.is_integer() and f >= 0:
                    out.append((name, M.SERVER_OPTION_INT, int(f)))
                else:
                    out.append((name, M.SERVER_OPTION_F32, f))
        return out

    # ---- achievements ----------------------------------------------------------------------------------------
    def achievement(self, did):
        return self.d["achievements"].setdefault(_hex(did), {"times": 0, "current": {}, "previous": {},
                                                             "updated": 0, "acknowledged": True, "valid_until": 0})

    def achievement_entries(self, adata, only=None, exclude=()):
        """0x2120 entries of every achievement with progress (the trainee ones are built by ics/matchend.py)."""
        out = []
        for a in adata.achievements():
            st = self.d["achievements"].get(_hex(a["did"]))
            if st is None or a["did"] in exclude or (only is not None and a["did"] not in only):
                continue
            objs = [M.achievement_objective(o["index"], int(st["current"].get(str(o["index"]), 0)),
                                            int(st["previous"].get(str(o["index"]), 0)), st.get("updated", 0),
                                            int(st["current"].get(str(o["index"]), 0)) > 0)
                    for o in a["objectives"]]
            out.append(M.achievement_entry(a["did"], st["times"], st.get("valid_until", 0), objs))
        return out

    def evaluate(self, adata, ctx):
        """Advance every achievement whose objective the context meets. ctx: {encounter, won, matchmade, kills,
        champion, champion_level, protector_level, owned_champions, champions_played}. Returns the newly completed
        achievement records."""
        done = []
        now = int(time.time())
        with self.lock:
            for a in adata.achievements():
                if a["category"] == CATEGORY_TRAINING:
                    continue                                  # the tutorials' own flow (ics/matchend.py)
                st = self.achievement(a["did"]) if self._touches(a, ctx) else None
                if st is None:
                    continue
                rep = REPEAT_SECONDS.get(a["repeat"])
                if st["times"] and not rep:
                    continue                                  # a one-time achievement already done
                if st["times"] and rep and st.get("valid_until", 0) > now:
                    continue
                if st["times"] and rep:
                    st["current"] = {}
                st["previous"] = dict(st["current"])
                complete = True
                for o in a["objectives"]:
                    k = str(o["index"])
                    cur = self._objective_value(o, ctx, int(st["current"].get(k, 0)))
                    st["current"][k] = min(cur, o["target"])
                    complete &= st["current"][k] >= o["target"]
                st["updated"] = now
                if complete:
                    st["times"] += 1
                    st["acknowledged"] = False
                    st["valid_until"] = now + rep if rep else 0
                    done.append(a)
                elif st["current"] == st["previous"]:
                    continue
            # untouched entries created by achievement() with no progress are dropped again
            self.d["achievements"] = {k: v for k, v in self.d["achievements"].items()
                                      if v["times"] or any(v["current"].values())}
        return done

    def seed_achievements(self, adata):
        """A new account starts at [ics] account_level (30): its protector-level achievements up to that level count
        as done and acknowledged, without their rewards (they would all be pending at once)."""
        n = 0
        with self.lock:
            for a in adata.achievements():
                objs = a["objectives"]
                if a["category"] == CATEGORY_PROTECTOR_LEVEL and objs and all(
                        o["type"] == OBJ_PROTECTOR_LEVEL and o["target"] <= self.d["level"] for o in objs):
                    st = self.achievement(a["did"])
                    st.update({"times": 1, "acknowledged": True,
                               "current": {str(o["index"]): o["target"] for o in objs},
                               "previous": {str(o["index"]): o["target"] for o in objs}})
                    n += 1
        return n

    @staticmethod
    def _touches(a, ctx):
        for o in a["objectives"]:
            t, enc = o["type"], o["encounter"]
            if enc and enc != ctx.get("encounter"):
                continue
            if t in (OBJ_MATCH_COMPLETE, OBJ_GAME) and ctx.get("encounter"):
                return True
            if t == OBJ_MATCH_WIN and ctx.get("won"):
                return True
            if t in (OBJ_MM_COMPLETE, OBJ_MM_WIN) and ctx.get("matchmade") and (t == OBJ_MM_COMPLETE or ctx.get("won")):
                return True
            if t == OBJ_KILL and ctx.get("kills"):
                return True
            if t in (OBJ_PROTECTOR_LEVEL, OBJ_CHAMPION_OWNED, OBJ_CHARACTER_CYCLE, OBJ_CHARACTER_LEVEL5):
                return True
        return False

    @staticmethod
    def _objective_value(o, ctx, cur):
        t, enc = o["type"], o["encounter"]
        same = not enc or enc == ctx.get("encounter")
        if t in (OBJ_MATCH_COMPLETE, OBJ_GAME) and same and ctx.get("encounter"):
            return cur + 1
        if t == OBJ_MATCH_WIN and same and ctx.get("won"):
            return cur + 1
        if t == OBJ_MM_COMPLETE and same and ctx.get("matchmade"):
            return cur + 1
        if t == OBJ_MM_WIN and same and ctx.get("matchmade") and ctx.get("won"):
            return cur + 1
        if t == OBJ_KILL and same:
            return cur + int(ctx.get("kills", 0))
        if t == OBJ_PROTECTOR_LEVEL:
            return int(ctx.get("protector_level", 0))
        if t == OBJ_CHAMPION_OWNED:
            return int(ctx.get("owned_champions", 0))
        if t == OBJ_CHARACTER_CYCLE:
            return int(ctx.get("champions_played", 0))
        if t == OBJ_CHARACTER_LEVEL5:
            return int(ctx.get("champions_level5", 0))
        return cur

    # ---- rewards -----------------------------------------------------------------------------------------------
    def add_pending_reward(self, adata, set_did, source, source_type=SOURCE_ACHIEVEMENT):
        """A pending reward instance (0x2125) for a reward set; returns it."""
        with self.lock:
            inst = self.d["rewards"]["next_instance"]
            self.d["rewards"]["next_instance"] += 1
            items = [[item, qty, g["bestowal"]] for g in adata.reward_set(set_did) for item, qty in g["items"]]
            entry = {"instance": inst, "set": set_did, "source": source, "source_type": source_type, "items": items}
            self.d["rewards"]["pending"].append(entry)
            return entry

    def reward_elements(self, entries=None, day=0):
        out = []
        for r in (self.d["rewards"]["pending"] if entries is None else entries):
            for item, qty, bestow in r["items"] or [[0, 0, BESTOW_GRANT]]:
                out.append(M.reward_element(r["set"], r["source"], item, qty, bestow, r["instance"], day=day))
        return out

    def claim(self, adata, roster, instance, set_did, choice=0, items=()):
        """Grant a pending reward (0x2128). Choice groups give the chosen item(s); Grant / AutoGrant all theirs.
        Returns (entry, changed DIDs) or (None, set())."""
        with self.lock:
            pend = self.d["rewards"]["pending"]
            entry = next((r for r in pend if r["instance"] == instance), None) \
                or next((r for r in pend if r["set"] == set_did), None)
            if entry is None:
                return None, set()
            chosen = set(int(i) for i in items if i) | ({int(choice)} if choice else set())
            changed, choice_given = set(), False
            for item, qty, bestow in entry["items"]:
                if bestow == BESTOW_CHOICE:
                    if (chosen and item in chosen) or (not chosen and not choice_given):
                        changed |= self.grant(item, qty, adata, roster)
                        choice_given = True
                    continue
                changed |= self.grant(item, qty, adata, roster)
            self.d["rewards"]["pending"] = [r for r in pend if r is not entry]
            self.d["rewards"]["claimed"] = (self.d["rewards"]["claimed"] + [entry["instance"]])[-200:]
            return entry, changed

    def login_reward_due(self, adata, today=None):
        """(day, reward set) of the calendar entry due today, or None (account-systems-data.md 3.4: the day is the
        number of days since the account's first login [P])."""
        day = (int(time.time()) // 86400 if today is None else today) - int(self.d["first_login_day"])
        last = int(self.d["rewards"].get("login_last_day", -1))
        due = [(d, s) for d, s in adata.login_calendar() if last < d <= day]
        return due[-1] if due else None
