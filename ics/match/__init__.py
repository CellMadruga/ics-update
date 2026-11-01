"""The PvP mode layer: everything a PvP map holds and runs besides the champions (2026-10-22).

Entry point (for the session / lobby; one call at match start, one per tick):

    from ics import match as pvp

    if pvp.is_pvp(encounter):
        spawn = pvp.spawn_point(encounter, team, slot)        # [1, lb x, lb y, cell, x, y, z]: World(..., spawn)
        packs += pvp.extra_packs(encounter)                    # 0x20AF extras (the meteor event pack)
        pvp.map_pack(encounter)        # the map pack (Data.encounter returns 0 on 4 PvP encounters: use this one)
        world.nav = pvp.navgrid(data, encounter).copy()        # the map's navmesh (same reason)
        ...                                                     # World created, champion created, client in world
        m = pvp.start_match(world, session, encounter, players)
        ...
        m.tick(dt)                     # every server tick, before or after World.tick (pvp.tick(m, dt) is the same)
        m.on_notice(notice_id, body)   # client notices 0x100000D2 HUD ready, 0x100002AD timeline ready,
                                       # 0x10000137 team health request, 0x10000454 surrender vote -> True if handled

    players: [{"player": player IID, "agent": champion Entity (or None), "name": str, "champion": variant DID,
               "team": 1 / 2, "bot": bool}]; empty = the World's own champion as the only player.
    session: any object; used when present: play_cinematic(did) (intro / end cinematic), match_over(winner team,
             seconds) (end page, rewards, leaving), send_team(team, label, data) / broadcast(label, data) (more than
             one player); without them everything goes through World.send to the local player.

What start_match does (per map, ics/match/maps.py): both teams' structures (power core, core turret, lane turrets,
dampeners, Foundry) with their data classes, stats at their level (stat block + level formulas), team, side, LifeState,
minimap category / visibility, PerceivedType flags and a navmesh footprint; the objectives (Gotham Heights capture
points, Coast City relays + Doomsday Device, Gotham Divided beacons) with their tracker pips (0x2069); the neutral
camps on their timer; the match clock 0x10000109 (pre-start during the 13 s intro, then counting up), the team health
bar (GH / Clash), the timeline and the scoreboard 0x1000005B. The tick runs the minion waves, the unit AI (lane walking,
target priorities, leash, structure targeting), captures, the Device, map events, rewards from the data's formulas,
death -> respawn timers at the team's start, the structure protection order, the win conditions, surrender votes and
the end sequence (end cinematic, billboard, 0x1000000E, session.match_over).
"""
from . import maps
from .match import Match

spawn_point = maps.spawn_point
extra_packs = maps.extra_packs
map_pack = maps.map_pack
navgrid = maps.navgrid


def is_pvp(encounter):
    return int(encounter) in maps.ENCOUNTERS


def start_match(world, session, encounter_did, players=None):
    """Build and start the mode layer for this encounter on the World; returns the Match (keep it, tick it)."""
    return Match(world, session, encounter_did, players).start()


def tick(match, dt, now=None):
    """Advance a match started with start_match by dt seconds."""
    if match is not None:
        match.tick(dt, now)
