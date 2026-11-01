"""The match roster: players, their K / D / A, credits earned and level; the scoreboard notice 0x1000005B, the kill feed
0x217A and assist tracking (full-match-mechanics.md 3-4)."""
from .. import messages as M


class Player:
    def __init__(self, player_iid, agent, name, champion, team, bot=False, account=0):
        self.player_iid, self.agent, self.name = player_iid, agent, name
        self.champion, self.team, self.bot, self.account = champion, team, bot, account
        self.kills = self.deaths = self.assists = 0
        self.money = 0.0
        self.streak = 0                 # consecutive kills without dying (bounty 0x3B0000B7)
        self.death_streak = 0
        self.slot = 0

    def row(self, level):
        return {"name": self.name, "account": self.account, "agent": self.agent.eid if self.agent else 0,
                "player": self.player_iid, "champion": self.champion, "team": self.team, "money": self.money,
                "level": int(level), "kills": self.kills, "deaths": self.deaths, "assists": self.assists,
                "bot": self.bot}


class Scoreboard:
    def __init__(self, match):
        self.m = match
        self.players = []
        self.damage = {}                # victim eid -> {attacker eid: last time}
        self.dirty = True
        self.sent_at = -1e9

    def add(self, player):
        player.slot = sum(1 for p in self.players if p.team == player.team)
        self.players.append(player)
        self.dirty = True
        return player

    def by_agent(self, ent):
        return next((p for p in self.players if p.agent is ent), None)

    def team(self, team):
        return [p for p in self.players if p.team == team]

    def hit(self, victim, source, t):
        if source is None or victim is None:
            return
        if self.by_agent(source) is not None:
            self.damage.setdefault(victim.eid, {})[source.eid] = t

    def assisters(self, victim, killer, t):
        window = float(self.m.ic.get("match_assist_window", 10.0))
        recent = self.damage.pop(victim.eid, {})
        out = []
        for p in self.players:
            if p.agent is None or p.agent is killer or p.agent is victim:
                continue
            if t - recent.get(p.agent.eid, -1e9) <= window:
                out.append(p)
        return out

    def last_damager(self, victim, t):
        """The enemy player whose champion hit victim last, within [ics] match_assist_window s (None = nobody):
        the kill credit when a turret, a minion or a creature lands the last blow (timeline-kda-endscreen.md 2)."""
        window = float(self.m.ic.get("match_assist_window", 10.0))
        recent = self.damage.get(victim.eid, {})
        best, at = None, -1e9
        for p in self.players:
            if p.agent is None or p.agent is victim or p.team == getattr(victim, "team", 0):
                continue
            when = recent.get(p.agent.eid, -1e9)
            if t - when <= window and when > at:
                best, at = p, when
        return best

    def rows(self):
        return [p.row(p.agent.level if p.agent else 1) for p in self.players]

    def tick(self, t):
        interval = float(self.m.ic.get("match_scoreboard_interval", 1.0))
        if self.dirty and t - self.sent_at >= interval:
            self.send(t)

    def send(self, t=None):
        self.dirty = False
        if t is not None:
            self.sent_at = t
        self.m.send(f"scoreboard: {len(self.players)} rows (0x1000005b)", M.pvp_match_roster(self.rows()))

    def kill_feed(self, victim, killer, assists):
        vp = self.by_agent(victim)
        vicon = self.m.world.data.champion_name(vp.champion)[1] if vp else self.m.ud.first(victim.class_id, 0x10000083, 0)
        kp = self.by_agent(killer) if killer is not None else None
        kicon = (self.m.world.data.champion_name(kp.champion)[1] if kp
                 else (self.m.ud.first(killer.class_id, 0x10000083, 0) if killer is not None else 0))
        icons = [kicon or 0] + [self.m.world.data.champion_name(p.champion)[1] for p in assists]
        self.m.send(f"kill feed: {victim.name} by {killer.name if killer is not None else '?'} (0x217a)",
                    M.pvp_kill_feed(victim.eid, vicon or 0, victim.team, killer.eid if killer is not None else 0,
                                    killer.team if killer is not None else 0, icons))
