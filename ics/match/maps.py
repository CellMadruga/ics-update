"""What each PvP map holds for the server: start points, structures, lanes, wave mouths, camps and objectives.

Every number is transcribed from the data surveys (docs/re-notes/maps-complete.md 3-4, full-maps-world.md 8,
units-and-ai.md 1.3) with the survey's confidence tag: C = read in the data (statics, pedestals, cinematics,
waypoints), P = probable, G = guessed / derived (the 31.3 % / 74.2 % lane rule of maps-complete.md 4, mirrored
positions, camp compositions). Positions are (x, y) in metres in the encounter's spawn landblock (region 1); z is the
map's ground (navmesh altitudes). Team 2 is the mirror of team 1 on every map (CA / CC / GH: x -> 160 - x, GD:
(x, y) -> (y, x)); a team-2 position is written out only where the data gives it.

Roles: core, core_turret, turret (lane), dampener, foundry (base turret), capture (GH point), relay (CC small
capturable), device (CC Doomsday Device), beacon (GD control point).
"""
import math

T1, T2 = 1, 2

MINIMAP = {"turret": 3, "inner_turret": 3, "dampener": 3, "core": 30, "core_turret": 3, "foundry": 6, "capture": 8, "minion": 9,
           "relay": 26, "device": 28, "beacon": 29}
# PerceivedType bits 0x1000019D per role (units-and-ai.md 1.2: 0x210 turret, 0x810 dampener, 0x4010 core, 0x4000
# foundry, 0x80200 capture objective, 0x80010 Doomsday Device) for classes whose template lacks them (C values)
PERCEIVED = {"turret": 0x210, "inner_turret": 0x210, "core_turret": 0x210, "dampener": 0x810, "core": 0x4010, "foundry": 0x4000,
             "capture": 0x80200, "relay": 0x80200, "beacon": 0x80000, "device": 0x80010}


def _mirror_x(p):
    return (160.0 - p[0], p[1]) + tuple(p[2:])


def _mirror_diag(p):
    return (p[1], p[0]) + tuple(p[2:])


# ---- Crime Alley (one lane; LB 0x13BB) -------------------------------------------------------------------------
_CA_LANE_1 = [(21.8, 77.5), (23.2, 77.5), (35.5, 77.5), (50.0, 77.5), (60.0, 77.5), (76.0, 77.5), (93.0, 77.5),
              (106.0, 77.5), (117.5, 77.5), (132.5, 77.5), (138.2, 77.5)]                      # C, idx 0x134-0x13D
_CA_LANE_2 = [(138.2, 77.5), (136.8, 77.5), (124.5, 77.5), (110.0, 77.5), (100.0, 77.5), (84.0, 77.5), (67.0, 77.5),
              (54.0, 77.5), (42.5, 77.5), (27.5, 77.5), (21.8, 77.5)]                         # C, idx 0x13E-0x147


def _crime_alley(family):
    # classes: "vai" = the tutorial / vs-AI family (explicit health), "clash" = the Clash family (formula stats)
    c = {"vai": {"core": (0x40000C8A, 0x40000C89), "dampener": (0x40000C88, 0x40000C87),
                 # 2026-10-26 (deep-scan-maps.md 3.1 row 6, C data: 0x40000C8B mirrors team 1's 0x40000C8C value for
                 # value, 2500 health, with the turret-warning table; 0x40000C86 is a 3000-health variant without it)
                 "turret": (0x40000C8C, 0x40000C8B), "core_turret": (0x40000C8F, 0x40000C8D)},
         "clash": {"core": (0x40000C96, 0x40000C98), "dampener": (0x40000C91, 0x40000C95),
                   "turret": (0x40000C92, 0x40000C93), "core_turret": (0x40000C94, 0x40000C97)}}[family]
    return {
        "name": "Crime Alley", "key": "crime_alley", "map_pack": 0xA0C112BA, "landblock": (0x13, 0xBB), "z": 200.3, "mirror": _mirror_x,
        "starts": {T1: [(5.0, 77.5), (6.0, 79.5), (6.0, 75.5), (7.0, 73.5), (7.0, 81.5)],
                   T2: [(155.0, 77.5), (154.0, 79.5), (153.0, 81.5), (154.0, 75.5), (153.0, 73.5)]},   # C (type 16)
        "structures": [
            {"role": "core", "lane": None, "cls": c["core"], "pos": {T1: (17.5, 77.5), T2: (142.5, 77.5)},
             "yaw": {T1: 90.0, T2: -90.0}, "conf": "C"},
            {"role": "core_turret", "lane": None, "cls": c["core_turret"], "pos": {T1: (25.5, 77.5), T2: (134.5, 77.5)},
             "conf": "G"},
            {"role": "dampener", "lane": "mid", "cls": c["dampener"], "pos": {T1: (40.0, 77.5), T2: (120.0, 77.5)},
             "conf": "C pos, P role"},
            {"role": "turret", "lane": "mid", "cls": c["turret"], "pos": {T1: (65.0, 77.5), T2: (95.0, 77.5)},
             "conf": "C pos, P class"},
            {"role": "foundry", "lane": None, "cls": (0x40000170, 0x4000016F),
             "pos": {T1: (1.3, 77.1, 201.8), T2: (158.7, 77.1, 201.8)}, "conf": "G"},
        ],
        "lanes": {"mid": {"mouth": {T1: (21.8, 77.5), T2: (138.2, 77.5)}, "path": {T1: _CA_LANE_1, T2: _CA_LANE_2}}},
        # minions: the set with CC stats in the CA packs (units-and-ai.md 1.4: which set each CA mode used is O)
        "minions": {"melee": 0x40000BF8, "ranged": 0x40000BFA, "siege": 0x40000BF9},
        # jungle camp: type-21 loop + markers 0x2E000944 / 945 at (80, 95.5) (P); composition G
        # 2026-10-23 14:18 (tester: the camp must stand in the hole, facing the street): at the jungle markers
        # 0x2E000944 / 945 / 0x2E001120 / 0x2E001117 (80.0, 97.2) instead of the loop's first point, yaw 180 (south)
        # 2026-10-23 16:20 (tester: "turned to the right and a bit further into the hole in the wall"): 1.5 m deeper,
        # yaw 90 (G; a camp's "pos" / "yaw" can be overridden by [ics] match_camp_overrides)
        # 2026-10-24 00:40 (tester's screenshot: "turn them 90 degrees counter-clockwise, then a bit up into the hole"):
        # yaw 180 (the 180 -> 90 step was a clockwise turn on screen) and 1 m deeper (+y = up on screen)
        # 2026-10-24 23:50 (crime-alley-2v2-video.md 5 and crime-alley-missing-elements.md 1.4: one camp per jungle
        # passage, 1 big + 2 small robots, minimap diamonds at ~(52, 90) / (113, 90), P): two more camps
        # 2026-10-25 19:28 (tester: the camps stand in the wrong places; crime-alley-jungle.md: the original v AI
        # minimap at 0:45, G +-1 m, navmesh checked; the west one on the type-3 marker 0x2E001118, C): middle on the
        # Raider pad (80, 97.66), west (48.75, 93.0), east its mirror (111.25, 93.0)
        # 2026-10-28 15:00 (tester report 2026-10-28 15:00: no camp in the centre; the side camps stand on the upper
        # sidewalk by each jungle mouth, north-west of its stealth field; camps-colour-bar-positions.md 3, P +-0.3 m: four
        # frames of the original video georeferenced with the client's camera 0x2100001E): 1 Heavy Tripod + 3 Tripods per
        # camp on the original's slots ("slots", first = the heavy = "pos"; [ics] match_camp_slots), every slot on the
        # navmesh. The east camp is the original's own: the west's mirror 0.45-0.6 m further west (the exact mirror's
        # south-east slot (112.80, 90.33) is off the navmesh). Facing (P, G for the head): west yaw 180, east 135 (the
        # heavy's front feet mirror the west's). The middle camp is "camps_centre" ([ics] match_camp_centre)
        # 2026-10-29 11:00 (tester: "those are the right camps; move them back a little so they sit deeper in the wall's
        # niches"): every slot 0.9 m north (the front slots stay on the navmesh up to 1.0 m)
        "camps": [{"pos": (48.82, 92.77), "yaw": 180.0, "kind": "small",
                   "units": [0x40000CA1, 0x40000CA0, 0x40000CA0, 0x40000CA0],
                   "slots": [(48.82, 92.77), (51.04, 92.81), (47.20, 91.23), (49.60, 91.14)]},
                  {"pos": (110.58, 92.73), "yaw": 135.0, "kind": "small",
                   "units": [0x40000CA1, 0x40000CA0, 0x40000CA0, 0x40000CA0],
                   "slots": [(110.58, 92.73), (108.50, 92.72), (112.20, 91.21), (109.95, 91.05)]}],
        # the fase3-ie middle camp on the Raider pad (the Raider waits until it is cleared): only with [ics]
        # match_camp_centre = true (2026-10-28 15:00, tester report: there must be no camp in the centre)
        "camps_centre": [{"pos": (80.0, 97.66), "yaw": 180.0, "units": [0x40000CA1, 0x40000CA0, 0x40000CA0],
                          "kind": "small", "middle": True,
                          "loop": [(80, 95.5), (87, 94.8), (96, 93.8), (108.5, 88.8), (73, 94.8), (64, 93.8),
                                   (51.5, 88.8)]}],
        "objectives": [],
        # 2026-10-23 18:50 (tester: no blue gate at the start, no white zones; crime-alley-missing-elements.md): the base
        # gate Door 0x40000557 / 0x2E000CD7 at the base exit (navmesh: x 29.5, open y 72.25-82.75; P), closed during the
        # countdown; the base aura Base 0x40000C7F / 0x2E000A35 on the spawn platform (radius 0x100002AA = 6)
        "gates": [{"pos": {T1: (29.5, 77.5)}, "heading": {T1: 0.0, T2: 3.14159265}, "cls": 0x40000557,
                   "world_state": 0x2E000CD7}],
        "auras": [{"pos": {T1: (5.0, 77.5)}, "cls": 0x40000C7F, "world_state": 0x2E000A35, "radius": 6.0}],
        # 2026-10-24 00:55 (tester: the areas that make a champion invisible, seen in the video, are missing;
        # crime-alley-missing-elements.md 1.3): purple stealth strips, 4 x 2 m tiles (world state 0x2E000D36) on the lane
        # edges; positions G from the video frames (north x 75-85, y ~81.5; south x 71-77 and 83-89, y ~73.5)
        # 2026-10-24 23:50 (tester: the zones are elsewhere; crime-alley-video-compare.md 1, positions G +-0.3 m from the
        # original video): a 4 x 2 m tile shows its 4 m side along y at yaw 0; the centre tiles lie along the lane (yaw
        # 90): north two end to end against the fence, south two with a 3 m gap at x 80; one at each jungle-passage mouth
        # 2026-10-25 (crime-alley-still-missing.md 2): the yaws were swapped (centre tiles lie along the lane at yaw 0)
        "stealth": [{"pos": (78.0, 82.3), "yaw": 0.0}, {"pos": (82.0, 82.3), "yaw": 0.0},
                    {"pos": (76.6, 72.2), "yaw": 0.0}, {"pos": (83.6, 72.3), "yaw": 0.0},
                    # 2026-10-28 10:3x (tester: move the vertical fields at the left and right a little lower): y -1.5
                    # 2026-10-28 12:5x (tester: turn them a few degrees, the blue side's to the right, the red side's to
                    # the left): the top of each vertical field leans 8 deg toward the lane's centre (yaw is CCW from +x)
                    # 2026-10-28 13:5x (tester: still off, turn them twice as far the other way): 16 deg back from
                    # 82 / 98, i.e. the top of each field now leans 8 deg away from the lane's centre
                    # 2026-10-28 15:00 (tester: both side fields are off; the vertical one back as it was, lined up with
                    # the collision edge of that corner; stealth-alignment.md): each jungle mouth is the original's L.
                    # Vertical tile yaw 90, its inner edge on the garden's side face and its south end on the garden
                    # corner (navmesh rim + 0.525 m: x 52.725, y 83.125, C); y 85.2 = the original's tile centre (its
                    # "+" in calibrated frames of the original, P +-0.25 m: the 10:3x "a little lower" was 0.3 m, not
                    # 1.5). East = the mirror, as in the original (its side face is 0.2 m west of a mirror, so the tile
                    # stays 0.225 m off it). "flush": checked by test_match; [ics] match_stealth_overrides switches back
                    # 2026-10-29 18:31 (tester: the side fields are still too far from the edge; their edge must sit
                    # against the collision of the central block; ca-fog-stealth-hover.md 2, C statics): "render" =
                    # the inner long edge on the drawn face (west brick pillar 580 x 53.30 - 0.40 = 52.90, east chain-link
                    # side panel 472 x 106.85 + 0.10 = 106.95) instead of the navmesh face (52.725 / 107.075, 0.18 /
                    # 0.35 m off the drawn wall); [ics] match_stealth_render_faces = false = "pos" as before
                    # 2026-10-29 19:55 (tester, screenshot 63: "at both ends move this section a little further down,
                    # toward the lane"): "lane_dir" = the way to the lane (screen down = -y with the yaw-0 camera); the
                    # vertical tiles move [ics] match_stealth_lane_shift m along it (1.0: south end from the garden
                    # corner y 83.1 to 82.1, on the curb's lane edge, ca-ring-fog-bundles.md 4); the diagonals stay
                    {"pos": (51.7, 85.2), "yaw": 90.0, "flush": True, "render": {"pos": (51.9, 85.2)},
                     "lane_dir": (0.0, -1.0)},
                    {"pos": (108.3, 85.2), "yaw": 90.0, "flush": True, "render": {"pos": (107.95, 85.2)},
                     "lane_dir": (0.0, -1.0)},
                    # 2026-10-25 23:22 (tester's frame of the original: at each jungle mouth the field bends from the
                    # vertical leg into a diagonal along the curb; crime-alley-still-missing.md 9, G numbers)
                    # 2026-10-28 15:00 (stealth-alignment.md 4-5): along the garden fence on the path side, from the
                    # corner, its edge on the fence face (22.93 / 157.25 deg, C; yaw 23 / 157 = the mirror; the yaw
                    # 50 / 130 tiles crossed the corner 0.46 / 0.26 m into the gardens)
                    # 2026-10-29 18:31 (same report): the west diagonal's edge already lies on the brick fence's drawn
                    # face (pillars 584-595, centre line 23.9 deg + 0.40 m); the east one moves 0.37 m onto the chain-link
                    # panels' face (467 / 466 / 465, yaw 67: centre line + 0.10 m, 157 deg)
                    {"pos": (54.2, 87.5), "yaw": 23.0, "flush": True},
                    {"pos": (105.8, 87.5), "yaw": 157.0, "flush": True, "render": {"pos": (105.66, 87.16)}}],
        # the drawn faces the "render" tiles lie on (statics 0x820113BB, stealth-alignment.md 3; test_match checks them):
        # (point on the face, direction deg, unit normal pointing to the walkable side)
        "stealth_render_faces": [((52.90, 83.26), 90.0, (-1.0, 0.0)), ((106.95, 83.46), 90.0, (1.0, 0.0)),
                                 ((106.889, 85.552), 157.0, (0.3907, 0.9205))],
        "intro": 0x3500003C, "end_cinematic": {T1: 0x3500003B, T2: 0x3500003A},
    }


# ---- Gotham Divided (three lanes; LB 0x1BD3; team 2 = (y, x)) ---------------------------------------------------
_GD_NORTH = [(26.3, 134.4), (37, 146), (49, 148.2), (61, 148.2), (72.5, 148.2), (86, 148.2), (99.8, 148.2),
             (106.5, 141.5), (115, 133), (124, 124), (133, 115), (141.5, 106.5), (148.2, 99.8), (148.2, 86),
             (148.2, 72.5), (148.2, 61), (148.2, 49), (147, 40), (144.6, 29.3), (134.4, 26.3)]    # C
_GD_MID = [(31, 127.5), (42.5, 117.5), (50, 109.8), (57, 102.8), (63.5, 95.5), (72, 88), (80, 80), (88, 72),
           (95.5, 63.5), (102.8, 57), (109.8, 50), (117.5, 42.5), (123.8, 33.8), (127.5, 31)]          # C
_GD_SOUTH = [(14.9, 130.8), (13, 120), (11.8, 111), (11.8, 99), (11.8, 87.5), (11.8, 74), (11.8, 60.2), (18.5, 53.5),
             (27, 45), (36, 36), (45, 27), (53.5, 18.5), (60.2, 11.8), (74, 11.8), (87.5, 11.8), (99, 11.8),
             (111, 11.8), (120, 13), (130.8, 14.9)]                                                  # C


def _gotham_divided():
    return {
        "name": "Gotham Divided", "key": "gotham_divided", "map_pack": 0xA0C11AD2, "landblock": (0x1B, 0xD3), "z": 250.2, "mirror": _mirror_diag,
        "starts": {T1: [(7.5, 152.5), (9.0, 151.0), (10.5, 152.5), (12.0, 154.0), (7.5, 149.5), (6.0, 148.0)]},
        "structures": [
            {"role": "core", "lane": None, "cls": (0x40000A7E, 0x40000A7B), "pos": {T1: (17.5, 142.5)},
             "yaw": {T1: 45.0, T2: -135.0}, "conf": "C"},
            {"role": "core_turret", "lane": None, "cls": (0x400003BA, 0x400003C1), "pos": {T1: (21.8, 136.9)},
             "conf": "G"},
            {"role": "dampener", "lane": "north", "cls": (0x40000C61, 0x40000C60), "pos": {T1: (56.3, 148.2)}, "conf": "G"},
            {"role": "turret", "lane": "north", "cls": (0x400003BB, 0x400003C0), "pos": {T1: (103.3, 144.7)}, "conf": "G"},
            {"role": "dampener", "lane": "mid", "cls": (0x40000C61, 0x40000C60), "pos": {T1: (46.8, 113.1)}, "conf": "G"},
            {"role": "turret", "lane": "mid", "cls": (0x400003BF, 0x400003BE), "pos": {T1: (67.3, 92.2)}, "conf": "G"},
            {"role": "dampener", "lane": "south", "cls": (0x40000C61, 0x40000C60), "pos": {T1: (11.8, 98.2)}, "conf": "G"},
            {"role": "turret", "lane": "south", "cls": (0x400003BC, 0x400003BD), "pos": {T1: (16.8, 55.2)}, "conf": "G"},
            # no anchor; Crime Alley's sits 3.7 m behind the start centre: 3 m toward the corner (G)
            {"role": "foundry", "lane": None, "cls": (0x40000170, 0x4000016F), "pos": {T1: (5.4, 154.6)}, "conf": "G"},
        ],
        "lanes": {"north": {"mouth": {T1: (26.0, 142.5)}, "path": {T1: _GD_NORTH}},
                  "mid": {"mouth": {T1: (23.5, 136.5)}, "path": {T1: _GD_MID}},
                  "south": {"mouth": {T1: (17.5, 134.0)}, "path": {T1: _GD_SOUTH}}},
        "minions": {"melee": 0x4000010A, "ranged": 0x4000010B, "siege": 0x4000010D, "elite_melee": 0x40000942,
                    "elite_ranged": 0x40000941, "super": 0x40000E5F},
        # no camp anchor on GD: the four jungle quarters between the lanes (maps-complete.md 4.2, G)
        "camps": [{"pos": (45.0, 80.0), "units": [0x40000939, 0x4000093B, 0x4000093B], "kind": "small"},
                  {"pos": (80.0, 45.0), "units": [0x40000939, 0x4000093B, 0x4000093B], "kind": "small"},
                  {"pos": (80.0, 115.0), "units": [0x4000093E, 0x4000093A, 0x4000093A], "kind": "small"},
                  {"pos": (115.0, 80.0), "units": [0x4000093E, 0x4000093A, 0x4000093A], "kind": "small"}],
        # the two neutral sites 0x2E0003F0 (C pos) as control points 0x400003AF = beacons (tracker 29, slots 1-2)
        "objectives": [{"role": "beacon", "cls": 0x400003AF, "pos": (55.0, 55.0), "slot": 1, "conf": "C pos, G role"},
                       {"role": "beacon", "cls": 0x400003AF, "pos": (105.0, 105.0), "slot": 2, "conf": "C pos, G role"}],
        # 2026-10-25 (map-gaps-gotham-divided.md 5, classes C in layout pack 0xA0000168, positions P): base gates at the
        # static frames 0x2E000EE1 (yaw -90 / -135 / 180 -> heading yaw + 90 deg; team 2 mirrored across x = y) and the
        # base aura on the spawn platform
        "gates": [{"pos": {T1: p}, "heading": {T1: h, T2: math.pi / 2 - h}, "cls": 0x40000557, "world_state": 0x2E000CD7}
                  for p, h in (((39.0, 149.5), 0.0), ((35.5, 124.5), -math.pi / 4), ((10.5, 121.0), 1.5 * math.pi))],
        "auras": [{"pos": {T1: (7.5, 152.5)}, "cls": 0x40000C7F, "world_state": 0x2E000A35, "radius": 6.0}],
        "intro": 0x35000024, "end_cinematic": {T1: 0x35000014, T2: 0x35000015},
        "events": ["meteor_storm"],
    }


# ---- Coast City (two lanes; LB 0x23E3; team 2 = 160 - x) --------------------------------------------------------
_CC_NORTH = [(21.5, 68), (24.5, 80), (30.5, 95.5), (36.5, 110.5), (41, 120.8), (46.5, 123.5), (64, 123.5), (80, 123.5),
             (96, 123.5), (113.5, 123.5), (119, 120.8), (123.5, 110.5), (129.5, 95.5), (135.5, 80), (138.5, 68)]  # C
_CC_SOUTH = [(23.8, 60), (33.5, 51.5), (60.5, 31), (77.5, 19), (82.5, 19), (99.5, 31), (126.5, 51.5), (136.2, 60)]


def _coast_city():
    return {
        "name": "Coast City", "key": "coast_city", "map_pack": 0xA0C122E2, "landblock": (0x23, 0xE3), "z": 250.2, "mirror": _mirror_x,
        "starts": {T1: [(4.7, 59.2), (2.7, 62.8), (3.7, 61.0), (4.7, 57.1), (4.8, 55.0)],
                   T2: [(155.4, 59.1), (155.3, 55.0), (155.3, 57.1), (156.4, 60.9), (157.4, 62.7)]},
        "structures": [
            {"role": "core", "lane": None, "cls": (0x40000C24, 0x40000C23), "pos": {T1: (17.0, 62.5)},
             "yaw": {T1: 105.0, T2: 255.0}, "conf": "C"},
            {"role": "core_turret", "lane": None, "cls": (0x40000400, 0x400003FF), "pos": {T1: (21.5, 64.0)}, "conf": "G"},
            {"role": "inner_turret", "lane": "north", "cls": (0x400003FA, 0x400003F9), "pos": {T1: (30.9, 96.5)}, "conf": "G"},
            {"role": "turret", "lane": "north", "cls": (0x400003FD, 0x400003FC), "pos": {T1: (55.2, 123.5)}, "conf": "G"},
            {"role": "inner_turret", "lane": "south", "cls": (0x400003FE, 0x400003FB), "pos": {T1: (40.7, 46.0)}, "conf": "G"},
            {"role": "turret", "lane": "south", "cls": (0x400003FD, 0x400003FC), "pos": {T1: (64.8, 28.0)}, "conf": "G"},
            {"role": "foundry", "lane": None, "cls": (0x40000170, 0x4000016F), "pos": {T1: (1.0, 59.2)}, "conf": "G"},
        ],
        "lanes": {"north": {"mouth": {T1: (20.8, 67.0)}, "path": {T1: _CC_NORTH}},
                  "south": {"mouth": {T1: (22.5, 60.5)}, "path": {T1: _CC_SOUTH}}},
        "minions": {"melee": 0x400002D5, "ranged": 0x400002D4, "siege": 0x40000441, "elite_melee": 0x40000443,
                    "elite_ranged": 0x40000442, "super": 0x40000D5C},
        # camps: type-3 markers 0x2E000942 / 944 / 945 with patrol loops (P); compositions G
        "camps": [{"pos": (80.0, 145.0), "units": [0x400007C1], "kind": "big"},
                  {"pos": (44.5, 90.5), "units": [0x40000894, 0x40000898, 0x40000898], "kind": "small"},
                  {"pos": (115.5, 90.5), "units": [0x40000894, 0x40000898, 0x40000898], "kind": "small"},
                  {"pos": (80.0, 9.0), "units": [0x40000D60], "kind": "big"},
                  {"pos": (80.0, 57.0), "units": [0x40000430], "kind": "boss"}],
        # tracker [26, 26, 26, 28] / [1, 2, 3, 1] (C): 3 power relays + the Doomsday Device (x = 80: neutral, G)
        "objectives": [{"role": "relay", "cls": 0x4000089D, "pos": (80.0, 131.0), "slot": 1, "conf": "G"},
                       {"role": "relay", "cls": 0x4000089D, "pos": (62.0, 76.0), "slot": 2, "conf": "G"},
                       {"role": "relay", "cls": 0x4000089D, "pos": (98.0, 76.0), "slot": 3, "conf": "G"},
                       {"role": "device", "cls": 0x400001F0, "pos": (80.0, 82.0), "slot": 1, "trigger": 0x4000054F,
                        "conf": "P"}],
        # 2026-10-25 (map-gaps-coast-city.md 3, C): base auras on the spawn platforms 0x2E000CA5; base gates (Door
        # 0x40000557, C class; G positions: the team-1 base's two navmesh necks, north y = 79 and south-east x = 33;
        # team 2 = 160 - x, the wall's heading mirrored)
        "auras": [{"pos": {T1: (3.21, 58.8), T2: (156.79, 58.81)}, "cls": 0x40000C7F, "world_state": 0x2E000A35,
                   "radius": 6.0}],
        "gates": [{"pos": {T1: p}, "heading": {T1: h, T2: math.pi - h}, "cls": 0x40000557, "world_state": 0x2E000CD7,
                   "conf": "G"} for p, h in (((24.1, 79.0), math.pi / 2), ((33.0, 51.5), 0.0))],
        # 2026-10-25 16:12 (tester's video 15:16: the player walked through the north gate): heading 0 is a wall along
        # y (Crime Alley's gate); the north neck runs along x, so its heading is 90 deg and the south-east one 0
        "intro": 0x35000020, "end_cinematic": {T1: 0x35000013, T2: 0x35000012},
        "events": ["meteor_storm"],
    }


# ---- Gotham Heights (domination; LB 0x1BF3; team 2 = 160 - x) ---------------------------------------------------
# the minions' routes: the two waypoint rings through the capture points (west half C, mirrored east half)
_GH_RING_NORTH_W = [(18.0, 47.0), (31, 47), (26, 60.5), (24.5, 75.5), (26.5, 88), (27, 90), (32.5, 103), (40, 112),
                    (50, 119.5), (65.5, 126), (78.5, 127.8)]
_GH_RING_SOUTH_W = [(18.0, 47.0), (31, 47), (38.5, 35.5), (48.5, 27.5), (51.5, 25.5), (60, 21), (72.5, 18)]


def _half_to_full(west):
    east = [_mirror_x(p) for p in reversed(west)]
    if east and abs(east[0][0] - west[-1][0]) < 4.0:
        east = east[1:]
    return west + east


def _gotham_heights():
    return {
        "name": "Gotham Heights", "key": "gotham_heights", "map_pack": 0xA0C11AF2, "landblock": (0x1B, 0xF3), "z": 250.1, "mirror": _mirror_x,
        "starts": {T1: [(6.0, 47.0), (5.7, 44.8), (5.4, 42.6), (4.4, 48.6), (2.8, 50.1)],
                   T2: [(154.0, 47.0), (154.3, 44.8), (154.6, 42.6), (155.6, 48.6), (157.2, 50.1)]},
        # 2026-10-25 (map-gaps-gotham-heights.md 1, C positions): the Power Cores 0x400003F2 (env_pvp_core_a) stand where
        # the foundries were; the team health is their health (domination drains it), so nobody hits them; the
        # foundries move behind the starts (G)
        "structures": [
            {"role": "core", "lane": None, "cls": (0x400003F2, 0x400003F2), "pos": {T1: (18.39, 50.08), T2: (142.67, 50.33)},
             "yaw": {T1: 15.0, T2: -20.0}, "invulnerable": True, "conf": "C"},
            {"role": "foundry", "lane": None, "cls": (0x40000170, 0x4000016F), "pos": {T1: (1.5, 47.0), T2: (158.5, 47.0)},
             "conf": "G"},
        ],
        "auras": [{"pos": {T1: (4.0, 46.2)}, "cls": 0x4000041F, "world_state": 0x2E000A35, "radius": 6.0}],
        # 2026-10-25 19:28 (tester: big pieces of the base ramps and the doors missing; test-2026-10-25-1928.md 2): the
        # layout pack's two "Door" classes, placed by no static (C): team 1 0x4000026B / ws 0x2E00084A, team 2
        # 0x40000269 / ws 0x2E000845, 20 x 37 m with the ramps in their mesh (Object_Closed / Object_Open). Position G:
        # the mesh's best fit on the navmesh edges, (26, 54) yaw 180, mirrored. They open at the start and stay.
        "gates": [{"pos": {T1: (26.0, 54.0)}, "heading": {T1: math.radians(180.0) + math.pi / 2, T2: math.pi / 2},
                   "cls": 0x4000026B, "cls_by_team": {T2: 0x40000269}, "world_state": 0x2E00084A,
                   "world_state_by_team": {T2: 0x2E000845}, "keep": True, "conf": "G"}],
        "lanes": {"north": {"mouth": {T1: (18.0, 47.0)}, "path": {T1: _half_to_full(_GH_RING_NORTH_W)}},
                  "south": {"mouth": {T1: (18.0, 47.0)}, "path": {T1: _half_to_full(_GH_RING_SOUTH_W)}}},
        "minions": {"melee": 0x4000012E, "ranged": 0x4000012D, "super": 0x40000EAA},
        "camps": [],
        # 5 capture points 0x4000013B at the markers 0x10000188 (P), tracker category 8 slots 1-5
        # 2026-10-29 (gh-ca-floor-spawn.md 3, C): "pad" = the point's pad static 0x2E0008D5 (type 7, yaw 180, LB 0x1BF3
        # idx 0x182A-0x182E), used with [ics] match_capture_on_pads
        "objectives": [{"role": "capture", "cls": 0x4000013B, "pos": p, "pad": pad, "slot": i + 1, "conf": "P"}
                       for i, (p, pad) in enumerate([((48.5, 27.5), (49.45, 26.5)), ((111.5, 27.5), (111.72, 26.99)),
                                                     ((27.0, 90.0), (26.91, 90.47)), ((133.0, 90.2), (133.1, 90.1)),
                                                     ((80.0, 127.8), (80.0, 127.93))])],
        "intro": 0x35000023, "end_cinematic": {T1: 0x3500000D, T2: 0x3500000E},   # core destruction shots (C)
    }


# ---- encounters --------------------------------------------------------------------------------------------------
# mode: "core" (destroy the enemy power core), "onslaught" (core + relays + Doomsday Device), "clash" (core + team
# health), "domination" (team health drained by the capture points); encounter type enum 0x1000054E in comments
ENCOUNTERS = {
    0x40000C82: ("crime_alley_vai", "core"),        # 1 Gas_Lane (v AI)
    0x40000CA6: ("crime_alley_vai", "core"),        # 9 Tutorial Advanced (its own script 0x34000628 on top)
    0x40000E68: ("crime_alley_clash", "clash"),     # 2 Gas_Lane_Tournament 1v1
    0x40000E74: ("crime_alley_clash", "clash"),     # 2v2
    0x4000013E: ("gotham_heights", "domination"),   # 3 Got_Dominion
    0x40000B6C: ("gotham_heights", "domination"),
    0x40000399: ("gotham_divided", "core"),         # 4 Got_Rift
    0x40000B6B: ("gotham_divided", "core"),
    0x40000E62: ("gotham_divided", "core"),
    0x40000270: ("coast_city", "onslaught"),        # 5 Cst_Onslaught
    0x4000039C: ("coast_city", "onslaught"),
    0x40000B6A: ("coast_city", "onslaught"),
}
_BUILDERS = {"crime_alley_vai": lambda: _crime_alley("vai"), "crime_alley_clash": lambda: _crime_alley("clash"),
             "gotham_divided": _gotham_divided, "coast_city": _coast_city, "gotham_heights": _gotham_heights}


def team_pos(m, table, team):
    """A {team: pos} entry for this team (the mirror of team 1's when the data gives only that)."""
    if team in table:
        return tuple(table[team])
    return tuple(m["mirror"](table[T1]))


def lane_path(m, lane, team):
    """The lane's points from this team's mouth to the enemy base (team 2 walks team 1's polyline backwards: a lane
    is one physical road, its points run from team 1's base to team 2's)."""
    paths = m["lanes"][lane]["path"]
    if team in paths:
        return [tuple(p) for p in paths[team]]
    return [tuple(p) for p in reversed(paths[T1])]


def map_for(encounter):
    """(map dict, mode) of a PvP encounter, or (None, None)."""
    key = ENCOUNTERS.get(int(encounter))
    if not key:
        return None, None
    return _BUILDERS[key[0]](), key[1]


def spawn_point(encounter, team, slot=0):
    """[region, landblock x, landblock y, cell, x, y, z] where a player of this team starts (type-16 start points:
    slot 0 = the team's centre). For the session's World(..., spawn) and the champion's position."""
    m, _mode = map_for(encounter)
    if not m:
        return None
    starts = m["starts"].get(team) or [m["mirror"](p) for p in m["starts"][T1]]
    x, y = starts[min(slot, len(starts) - 1)][:2]
    return [1, m["landblock"][0], m["landblock"][1], 0, float(x), float(y), float(m["z"])]


def extra_packs(encounter):
    """Packs the 0x20AF list needs on top of the map's own for this layer's content: the meteor event pack
    0xA0000164 (Meteor Fragment 0x400006F1: no map pack lists it, full-match-mechanics.md 9.2)."""
    m, _mode = map_for(encounter)
    return [0xA0000164] if m and "meteor_storm" in m.get("events", ()) else []


_NAV = {}


def map_pack(encounter):
    """The encounter's map pack (template 0x10000406; C). 2026-10-22: Data.encounter_info returns 0 for 0x40000C82,
    0x4000013E, 0x40000B6B and 0x40000B6A (Data.template_properties stops before the property), so the session's
    0x20AF pack list and Data.navgrid miss the map on those encounters; this is the value to use there."""
    m, _mode = map_for(encounter)
    return m["map_pack"] if m else 0


def navgrid(data, encounter, origin_lb=None):
    """The map's walkable grid (ics.navmesh, champion agent) from the map pack named here, shared per map (copy() it
    per match)."""
    from .. import navmesh
    m, _mode = map_for(encounter)
    if not m:
        return None
    key = (m["map_pack"], tuple(origin_lb or m["landblock"]))
    if key not in _NAV:
        try:
            _NAV[key] = navmesh.load(data.packs.pack(m["map_pack"]).data, key[1], agent_class=0x10000003)
        except (OSError, ValueError):
            _NAV[key] = None
    return _NAV[key]
