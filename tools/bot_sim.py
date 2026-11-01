"""Headless bot champions run (docs/re-notes/bot-champions.md 3.7 step 9): a PvP match with bot champions on a
simulated session and clock; prints what each bot did (lane, casts, kills, deaths, respawns, levels, buys).

    python tools\\bot_sim.py [encounter] [seconds]        (default Crime Alley v AI 0x40000C82, 300 s)
"""
import collections
import math
import os
import random
import sys
import time

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
sys.path.insert(0, os.path.join(ROOT, "tests"))

from ics import config                                   # noqa: E402
from ics import match as pvp                             # noqa: E402
from ics.gamedata import Data                            # noqa: E402
from ics.lobby import BOT_IID_BASE                       # noqa: E402
from ics.world import World                              # noqa: E402
from test_match import FakeSession                       # noqa: E402

TEAM_SIZE = {0x40000C82: 1, 0x40000E68: 1}


def players(data, cfg, encounter, n):
    roster = [c["variant"] for c in data.roster]
    rng = random.Random(7)
    rows = [{"iid": 1, "name": "Player", "team": 1, "index": 0, "champion": cfg["ics"]["champion"], "bot": False}]
    k = 0
    for team in (1, 2):
        for i in range(n):
            if team == 1 and i == 0:
                continue
            rows.append({"iid": BOT_IID_BASE + k, "name": f"Bot {k}", "team": team, "index": i,
                         "champion": rng.choice(roster), "bot": True, "stolen": []})
            k += 1
    return rows


def main():
    encounter = int(sys.argv[1], 0) if len(sys.argv) > 1 else 0x40000C82
    seconds = float(sys.argv[2]) if len(sys.argv) > 2 else 300.0
    cfg = config.load()
    cfg["ics"]["trace_scripts"] = False
    data = Data(cfg.game_dir)
    s = FakeSession()
    real_time = time.time
    time.time = lambda: s.clock                  # cooldowns and timers on the simulated clock
    lines = []
    log = lines.append
    spawn = pvp.spawn_point(encounter, 1)
    w = World(data, cfg, encounter, spawn, send=s.send, schedule=s.schedule, log=log)
    nav = pvp.navgrid(data, encounter, spawn[1:3])
    w.nav = nav.copy() if nav else None
    w.ground_z = spawn[6]
    w.create_champion(cfg["ics"]["champion"], spawn)
    w.in_world = True
    w.champion.alive = True
    m = pvp.start_match(w, s, encounter, players(data, cfg, encounter, TEAM_SIZE.get(encounter, 5)))
    m.log = log
    # the human stays home (out of the way)
    step = 0.1
    on_lane = collections.Counter()
    samples = collections.Counter()
    for k in range(int(seconds / step)):
        s.clock += step
        m.tick(step, s.clock)
        w.tick(step, s.clock)
        s.run_due()
        w.champion.pos = list(spawn[4:7])
        if k % 10 == 0 and m.t > 60:
            for b in m.bots.brains:
                e = b.ent
                if not e.alive or not b.route or b.state in ("base", "recall", "retreat", "dead"):
                    continue
                samples[e.name] += 1
                d = min(math.hypot(e.pos[0] - p[0], e.pos[1] - p[1]) for p in b.route)
                on_lane[e.name] += d <= 10.0
    time.time = real_time
    stats = collections.defaultdict(collections.Counter)
    names = sorted((b.ent.name for b in m.bots.brains), key=len, reverse=True)
    for ln in lines:
        if ln.startswith("bot "):
            name = next((n for n in names if ln[4:].startswith(n + ":")), None)
            if name is None:
                continue
            what = ln[4 + len(name) + 2:].split(" ")[0]
            stats[name][what] += 1
    print(f"{seconds:g} s on {encounter:#x}")
    for b in m.bots.brains:
        e = b.ent
        p = m.score.by_agent(e)
        print(f"  {e.name} ({e.class_id:#x}) team {e.team} lane {b.lane}: level {e.level}, {e.gold:.0f} credits, "
              f"items {sum(1 for d in e.inventory if d)}, K/D/A {p.kills}/{p.deaths}/{p.assists}, state {b.state}, "
              f"on its lane {on_lane[e.name] / max(1, samples[e.name]):.0%}, actions {dict(stats[e.name])}")
    errors = [ln for ln in lines if "error" in ln.lower()]
    print(f"  {len(errors)} error lines" + ("".join(f"\n    {x[:200]}" for x in errors[:10])))
    print(f"  {len(s.sent)} messages, {sum(len(d) for _l, d in s.sent) / 1024:.0f} KB")


if __name__ == "__main__":
    main()
