"""Champion select (the pre-match lobby) with bots in the free slots, and custom match rooms.

Message sequences: docs/re-notes/full-protocol.md 4.3 / 4.4 / 4.6; the client events are named as in
full-account-social.md 1.2 / 1.3 (checked by argument types). 2026-10-22, decompilation: the only caller of the
0x2102 builder 0x8864b0 is 0xa0c530 (custom-match listener slot +0x3C, SetDraftMode) with the constant 0x20000, so
0x2102 is the draft toggle and the champion pick is 0x20E4 (builder 0x87a770, sender 0x889150). Both are accepted;
the log says which one the client sent.

The lobby state is fields, not events: one 0x2029 per slot (team, index, player, name, bot flag, champion, locked,
Stolen Powers, amplifier set) and the encounter details 0x204C. Bots take the encounter's bot pool (template
0x10000B3E: vs-AI maps); PvP maps have none, so they use every vs-AI pool of the install (units-and-ai.md), then the
roster. A bot's Stolen Powers and amplifier set are its champion's default loadout (0x10000CEB).
"""
import random
import time

from . import messages as M
from .account import AccountData

BOT_IID_BASE = 0x0200000000F00000          # lobby identities of the bots (player ids; apart from the world's
                                           # entities, which start at 0x0200000000000100)


class Slot:
    def __init__(self, team, index, iid, name, champion, bot=False):
        self.team, self.index, self.iid, self.name, self.champion, self.bot = team, index, iid, name, champion, bot
        self.locked = bot
        self.stolen = [0, 0]
        self.amp = None                    # {"slot", "champion", "name", "icon", "amplifiers"}
        self.level = 0

    def as_player(self):
        """What the mode layer (ics/match) gets for each player of the match."""
        return {"iid": self.iid, "name": self.name, "team": self.team, "index": self.index, "champion": self.champion,
                "bot": self.bot, "stolen": list(self.stolen), "amplifiers": list((self.amp or {}).get("amplifiers", [])),
                "level": self.level}


def is_lobby_encounter(adata, cfg, encounter):
    """Champion select with bots for vs-AI / challenge / PvP encounters (category 1-3) without a scripted flow;
    the tutorials (category 4) keep the direct path they had."""
    if (cfg.encounter(encounter) or {}).get("director"):
        return False
    t = adata.encounter_template(encounter)
    return t["category"] in (1, 2, 3) and (t["players_per_team"] > 1 or t["bot_pool"] or t["category"] == 3)


def bot_pool(data, adata, encounter, ic):
    """Champion variants bots may play: the encounter's pool, else every vs-AI pool, else the roster ([ics]
    bot_champions overrides all). Only variants with a kit (skills) are kept."""
    forced = [int(str(v), 16) if isinstance(v, str) else int(v) for v in ic.get("bot_champions", []) or []]
    if not forced and ic.get("bot_pool_all_champions", True):
        # 2026-10-23 17:30 (tester: every champion playable vs AI): the bots draw from the whole roster
        forced = [c["variant"] for c in data.roster]
    pool = forced or list(adata.encounter_template(encounter)["bot_pool"])
    if not pool:
        for did, _cat in data.encounter_list():
            for v in adata.encounter_template(did)["bot_pool"]:
                if v not in pool:
                    pool.append(v)
    if not pool:
        pool = [c["variant"] for c in data.roster]
    return [v for v in pool if data.kit(v)] or [c["variant"] for c in data.roster if data.kit(c["variant"])]


class Lobby:
    def __init__(self, session, encounter, qflags, champion, custom=None):
        self.s = session
        self.data, self.ic = session.data, session.ic
        self.adata = AccountData.of(self.data)
        self.account = session.account
        self.encounter, self.qflags, self.room = encounter, qflags, int(self.ic["room_id"])
        self.custom = custom
        t = self.adata.encounter_template(encounter)
        self.per_team = max(1, int(self.ic.get("lobby_players_per_team", 0) or t["players_per_team"]))
        self.teams = 2
        sel = float(self.ic.get("select_seconds", -1))
        self.select_seconds = t["select_seconds"] if sel < 0 else sel
        self.opened_at = None
        self.lock_at = None
        self.launched = False
        self.launching = False
        seed = int(self.ic.get("bot_seed", 0) or 0)
        self.rng = random.Random(seed or None)
        me_team = int(self.ic["team"])
        self.me = Slot(me_team, 0, M.LOCAL_PLAYER_ID, str(self.ic["player_name"]), champion)
        self._dress(self.me, human=True)
        self.slots = [self.me]
        pool = self.pool = bot_pool(self.data, self.adata, encounter, self.ic)
        base = self.data.base_variant
        taken = {base(champion) or champion}
        n = 0
        for team in range(1, self.teams + 1):
            first = 1 if team == me_team else 0
            for index in range(first, self.per_team):
                choices = [v for v in pool if (base(v) or v) not in taken] or pool
                pick = self.rng.choice(choices)
                taken.add(base(pick) or pick)
                pick = self.bot_skin(pick)
                n += 1
                name = self.bot_name(pick)
                bot = Slot(team, index, BOT_IID_BASE + n, name, pick, bot=True)
                self._dress(bot)
                self.slots.append(bot)

    def _dress(self, slot, human=False):
        """Stolen Powers and amplifier set for the slot's champion: the account's choices, else the defaults."""
        if human and self.account is not None:
            slot.stolen = self.account.stolen_pair(self.data, slot.champion)
            # 2026-10-28 (store-amplifiers.md): the set picked for this champion last time (0x2098), else its newest
            slot.amp = (self.account.chosen_amplifier_set(slot.champion)
                        or self.account.default_amplifier_set(self.data, slot.champion))
            slot.level = int(self.account.champion(self.data.base_variant(slot.champion) or slot.champion)["level"])
        else:
            st = list(self.data.loadout(slot.champion).get("stolen", []))
            slot.stolen = (st + [0, 0])[:2]
            lo = self.data.loadout(slot.champion)
            slot.amp = {"slot": 0, "champion": slot.champion, "name": "", "icon": 0,
                        "amplifiers": (list(lo.get("augments", []))[:4] + list(lo.get("mods", []))[:3] + [0] * 7)[:7]}
            slot.level = 1

    # ---- messages ------------------------------------------------------------------------------------------------
    @staticmethod
    def amp_bytes(amp):
        if not amp:
            return None
        return M.amplifier_set(amp.get("slot", 0), amp.get("id", 0), amp.get("champion", 0), amp.get("name", ""),
                               amp.get("icon", 0), (list(amp.get("amplifiers", [])) + [0] * 7)[:7])

    def slot_msg(self, slot):
        shown = slot.champion
        base = self.data.base_variant(slot.champion) or 0
        if base and base != slot.champion and self.ic.get("lobby_slot_base_for_costume", True):
            # 2026-10-25 16:12 (tester: picking a skin loses the team slot's portrait, "Player" only): the slot names the
            # base champion (its portrait resolves); the costume stays the slot's pick for the match and the loading
            shown = base
        return (f"lobby slot (0x2029): team {slot.team}/{slot.index} {'bot ' if slot.bot else ''}{slot.name} "
                f"{shown:#x}{' locked' if slot.locked else ''}",
                M.lobby_slot(slot.team, slot.index, slot.iid, slot.name, shown, self.room, is_bot=slot.bot,
                             locked=slot.locked, level=slot.level if self.ic.get("lobby_send_level", False) else 0,
                             stolen=slot.stolen if self.ic.get("lobby_slot_stolen_powers", True) else (0, 0),
                             amp=self.amp_bytes(slot.amp) if self.ic.get("lobby_slot_amplifiers", True) else None))

    def owned_entries(self):
        """0x204C's owned list (DID, status 2, type, owned, count): the client's skin picker keeps the costumes
        (type 4) of my champion from it (0xa95e70 -> lobby+0x40, 0xab93a0); 2026-10-23 09:44 (tester: no skin list)
        it held only my champion. lobby_owned_costumes = false: only that one entry, as before."""
        if not self.ic.get("lobby_owned_costumes", True):
            return [(self.me.champion, 2, 1, 1, 1)]
        owns = (lambda v: True) if self.account is None else self.account.champion_owned
        out = []
        for c in self.data.roster:
            if owns(c["variant"]):
                out.append((c["variant"], 2, 1, 1, 1))
            out += [(s["variant"], 2, 4, 1, 1) for s in c.get("costume_info", []) if owns(s["variant"])]
        if not any(o[0] == self.me.champion for o in out):
            out.insert(0, (self.me.champion, 2, 1, 1, 1))
        return out

    def details_msg(self):
        owned = self.owned_entries()
        return (f"lobby details (0x204c): {self.teams} teams x {self.per_team}, room {self.room}",
                M.lobby_details(self.encounter, self.qflags, self.room, self.teams, self.per_team, M.LOCAL_PLAYER_ID,
                                self.me.team, owned, [self.me.champion], admin=False))

    def state_msgs(self):
        out = [self.details_msg()] + [self.slot_msg(s) for s in self.slots]
        out += [("my Stolen Powers (0x2004)", M.picked_stolen_powers(self.room, *self.me.stolen))]
        amp = self.amp_bytes(self.me.amp)
        if amp:
            out.append(("my amplifier set (0x204a)", M.picked_amplifier_set(self.room, amp)))
        return out

    # ---- player actions -------------------------------------------------------------------------------------------
    def pick(self, champion):
        """A pick (0x20E4 / 0x2102). Returns messages, or None when refused."""
        if self.launched:
            return None
        skin = self.me.locked and self.data.base_variant(champion) == self.data.base_variant(self.me.champion) != 0
        if self.me.locked and not skin:
            return None                    # locked: only a costume of the same champion (the skin picker)
        if not self.data.kit(champion) and not skin:
            return None
        if self.account is not None and not self.account.champion_owned(champion):
            return None
        if self.ic.get("lobby_unique_picks", True) and any(s.champion == champion and s.team == self.me.team
                                                             for s in self.slots if s is not self.me):
            return None
        self.me.champion = champion
        self._dress(self.me, human=True)
        return ([self.slot_msg(self.me), ("my Stolen Powers (0x2004)", M.picked_stolen_powers(self.room, *self.me.stolen))]
                + self._bots_avoid(champion))

    def bot_skin(self, variant):
        """2026-10-29 23:30 (tester: "whenever we play against bots, they use a random skin of the champion, never the
        base look"): one of the champion's costumes at random ([ics] bot_random_skin; a champion without costumes keeps
        its base variant; false = the base variant as before)."""
        if not self.ic.get("bot_random_skin", True):
            return variant
        base = self.data.base_variant(variant) or variant
        champ = next((c for c in self.data.roster if c["variant"] == base), None)
        skins = [s["variant"] for s in (champ or {}).get("costume_info", []) if self.data.kit(s["variant"])]
        return self.rng.choice(skins) if skins else variant

    def bot_name(self, champion):
        """2026-10-25 (tester's frame of the original: "... defeated AI: Gaslight Batman"): [ics] bot_name_prefix + the
        champion's name ("" = the earlier "<champion> Bot")."""
        name = self.data.champion_name(champion)[0]
        prefix = self.ic.get("bot_name_prefix", "AI: ")
        return f"{prefix}{name}" if prefix else f"{name} Bot"

    def _bots_avoid(self, champion):
        """2026-10-23 17:30 (tester: one model shows over another): two variants of one champion in a match load model
        packs that carry the same DIDs with different content; a bot playing my champion takes another one
        ([ics] bots_avoid_my_champion)."""
        if not self.ic.get("bots_avoid_my_champion", True):
            return []
        base = self.data.base_variant
        mine = base(champion) or champion
        out = []
        for slot in self.slots:
            if not slot.bot or (base(slot.champion) or slot.champion) != mine:
                continue
            used = {base(x.champion) or x.champion for x in self.slots}
            choices = [v for v in getattr(self, "pool", []) if (base(v) or v) not in used]
            if not choices:
                continue
            slot.champion = self.bot_skin(self.rng.choice(choices))
            slot.name = self.bot_name(slot.champion)
            self._dress(slot)
            out.append(self.slot_msg(slot))
        return out

    def lock(self, champion=None):
        if champion and champion != self.me.champion:
            if self.pick(champion) is None:
                return None
        self.me.locked = True
        return [self.slot_msg(self.me)]

    def change_stolen_power(self, slot, power):
        if self.account is not None:
            self.me.stolen = self.account.set_stolen_power(self.data, self.me.champion, slot, power)
        elif slot in (0, 1):
            self.me.stolen[slot] = power
        return [("my Stolen Powers (0x2004)", M.picked_stolen_powers(self.room, *self.me.stolen)), self.slot_msg(self.me)]

    def change_amplifier_set(self, slot_id):
        sets = self.account.amplifier_sets(self.me.champion) if self.account else []
        chosen = next((s for s in sets if s["slot"] == slot_id), None)
        if chosen is None:
            chosen = next((s for s in (self.account.amplifier_sets() if self.account else []) if s["slot"] == slot_id),
                          None)
        self.me.amp = chosen or (self.account.default_amplifier_set(self.data, self.me.champion) if self.account
                                 else self.me.amp)
        return [("my amplifier set (0x204a)", M.picked_amplifier_set(self.room, self.amp_bytes(self.me.amp))),
                self.slot_msg(self.me)]

    def trade(self, target_iid):
        """Draft trade with a teammate bot: bots always accept; the picks swap (full-protocol.md 4.4)."""
        other = next((s for s in self.slots if s.iid == target_iid and s.team == self.me.team and s is not self.me),
                     None)
        if other is None or self.launched:
            return None
        self.me.champion, other.champion = other.champion, self.me.champion
        self._dress(self.me, human=True)
        self._dress(other)
        return [self.slot_msg(self.me), self.slot_msg(other)]

    def all_locked(self):
        return all(s.locked for s in self.slots)

    def players(self):
        return [s.as_player() for s in self.slots]

    def champions(self):
        return [s.champion for s in self.slots]


class CustomMatch:
    """A custom match room (full-protocol.md 4.6): the player is the coordinator; the other slots are filled with
    bots when it launches. Invites, kicks and permissions only concern bots or nobody (one human for now)."""

    def __init__(self, session, encounter, qflags=0):
        self.s = session
        self.encounter = encounter
        self.qflags = qflags or int(session.ic.get("custom_match_qflags", (1 << 21) | (1 << 17)))
        self.draft = False
        self.team_names = {}
        self.team = int(session.ic["team"])
        self.position = 0
        self.permissions = {}

    def created_msgs(self):
        ic = self.s.ic
        lvl = int(self.s.account.d["level"]) if self.s.account else 1
        return [("custom match: me as participant (0x2012)",
                 M.cm_participant_added(str(ic["player_name"]), M.LOCAL_PLAYER_ID, M.LOCAL_PLAYER_ID, lvl, 0, 1,
                                        False, self.team)),
                (f"custom match: encounter {self.encounter:#x} (0x2109)", M.cm_set_encounter(self.encounter)),
                (f"custom match: draft {'on' if self.draft else 'off'} (0x2103)", M.cm_draft_mode(0x20000, self.draft))]


def launch_times(seconds):
    """0x204B's start / end: f64 seconds on the client's game clock, which the time packets set from time.time()."""
    now = time.time()
    return now, now + max(0.0, float(seconds))
