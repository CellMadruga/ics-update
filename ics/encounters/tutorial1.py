"""Tutorial 1, "A Champion in Peril" (encounter 0x40000991): its flow.

What comes from the game data: the objectives (table 0x48000D3F, by index), the conversations (catalogue
0x40000CB7, in this order), the cinematics (0x35000026 intro, 0x35000034 Catwoman, 0x35000028 Destroyer, 0x35000025
end), every placement by name (layout pack 0xA0000256: class, position, side), the units' stats and attacks, the
doors' and the crater's scriptlets. What the data does not have (tutorial-data-inventory.md section 6.6): when
each thing happens and where the server-made objects stand. Those are authored here, from the earlier server
(icserver/tutorial1.py, bridge.py, finale.py: measured on the original's video and the tester's pings).

Skill slots: 1 Q, 2 W, 3 E, 4 R, 5 passive, 7 D and 8 F (Stolen Powers).
"""
import math

from ..director import (HUD_HINTS, HUD_LEVEL_XP, HUD_MINIMAP, HUD_OBJECTIVES, HUD_PORTRAIT, HUD_SKILLS_BAR,
                        HUD_STATUS_ICONS, HUD_VITALS, HL_LEVEL_XP, HL_WILL, SKILL_BUTTON, SKILL_HIGHLIGHT)

Q, W, E, R, PASSIVE, D, F = 1, 2, 3, 4, 5, 7, 8
TARGET_DRONE = 0x40000BA9        # "Practice Target" (only skills hurt it; script 0x34000600 shows its guide arrow)
METEOR_ROCK = 0x2E000BB3         # the meteor's rock (Vfx_Spawn_Event01 attaches it; a copy falls again)
# 2026-10-22 08:13 (tester: the crater still vanishes, its lava stays): the crater world state's table 0x1D000155
# attaches these meshes on Vfx_Active, and they go with the effect; they are left as objects of their own
# 2026-10-22 09:13 (tester's video: 0x2E000375 is a roof, not a crater): the crater meshes 0x170001D0-D2 that
# Vfx_Spawn_Event02 attaches are the world states 0x2E0002F8 / F7 / F6 (pack 0xA000024C, 0x1EB = the mesh)
CRATER_MESHES = [0x2E0002F6, 0x2E0002F7, 0x2E0002F8]
# 2026-10-22 (original's video: red lava cracks in a star stay on the cobbles): the crater world state itself (the
# intro / bridge cinematics place it as "Crater1"-"Crater3" with Object_Closed); its table 0x1D000155 attaches the
# lava meshes 0x2E001060 / 0x2E001061, which alone showed as a flat red disk
CRATER_STATE = 0x2E0004BE
# hints (table 0x4800070C, ids as the earlier server used them)
HINT_GUIDE_ARROWS, HINT_BASIC_ATTACK, HINT_EXPERIENCE, HINT_SKILL_POINTS = 16, 17, 18, 34
HINT_PASSIVE, HINT_SUPER_STRENGTH = 23, 26
HINT_WILL, HINT_SKILL_RANKS, HINT_SKILL_CHARGES, HINT_SPACEBAR, HINT_CAMERA_ZOOM, HINT_STOLEN_POWERS = 20, 21, 22, 24, 25, 27
# Superman when a practice target is hit by the wrong attack (each once; the earlier server's bridge.wrong_attack):
# 0x1CD a basic attack ("only skills"), 0x1DB then 0x1B2 another skill ("ineffective", "try the new skill")
IMMUNE_LINES = {"basic": [0x1CD], "skill": [0x1DB, 0x1B2]}
CRATER = 0x40000CAB              # meteor crater entity (world state 0x2E0004BE, scriptlet table 0x1D0008B6)
CATWOMAN = 0x35000034
# 2026-10-22 14:45 (tester, original's video 2:35-2:50: the vehicle Catwoman strikes explodes and its wreck stays):
# her CinematicCharacter_State02 (table 0x1D0008C2) at frame 146 on InvisibleTarget (the vehicle's spot) spawns the
# wreck pieces 0x2E00135E / 5F / 60 (tables 0x1D000916-918: their key 0x5 fire) and particles, as cinematic-local
# copies that go with the cinematic; ours stay. The intact vehicle goes at that frame.
CATWOMAN_STRIKE_FRAME = 146
VEHICLE_WRECK = [0x2E00135E, 0x2E00135F, 0x2E001360]
VEHICLE_YAW = -2.513
DESTROYER_CINEMATIC = 0x35000028
ENDING = 0x35000025

# the bridge runs from 03GateA (54.05, 44.80) to 03GateB (89.87, 26.21): s metres along it, lat across it
_O, _U, _N = (54.05, 44.80), (0.8875, -0.4606), (0.4606, 0.8875)


def along(s, lat=0.0):
    return (_O[0] + s * _U[0] + lat * _N[0], _O[1] + s * _U[1] + lat * _N[1])


CROSS_YAW = math.atan2(_N[1], _N[0])
POSITIONS = {
    "marker1": (25.0, 60.3), "marker2": (30.5, 59.0),
    "big_meteor": (18.0, 61.3),
    # 2026-10-22 (original Part 1 1:15: the wave's strike lands ~1.5 m from Batman, toward the vehicle, where he
    # finished the first drone (03MeleeC 35.3, 56.3); before: (24.0, 66.0), the earlier server's spot)
    "wave_meteor": (37.0, 55.4), "wave_meteor_gp": (24.0, 66.0),
    # 2026-10-22 (original's video 0:44): a smaller strike lands beside Batman two seconds into his first walk
    "small_meteor": (20.8, 57.6),         # the earlier server's second small meteor spot
    "wave1": (43.6, 55.3), "wave2": (41.2, 53.5), "thug_flee": (24.0, 64.0),
    "targetA": (42.8, 59.6), "targetB": (44.2, 57.3),
    "pursuer1": (49.36, 49.34), "pursuer2": (47.87, 46.76),
    "w_target": (49.6, 48.2),
    "surround1": (46.0, 51.5), "surround2": (51.0, 50.5), "surround3": (48.5, 53.0),
    "gate_mid": along(17.5), "marker_bridge": along(12.0),
    "ambush_melee1": along(14.8, -1.2), "ambush_melee2": along(14.8, 1.2), "ambush_ranged": along(16.3),
    "ambush_gate_melee1": along(3.0, -1.2), "ambush_gate_melee2": along(3.0, 1.2), "ambush_gate_ranged": along(1.8),
    "ambush_strike": along(9.8, -0.3),
    "camera": along(12.5),
    "gate_drones": along(31.5),
    "gate_melee1": along(38.6, -1.0), "gate_melee2": along(38.6, 1.0),
    "gate_ranged1": along(36.4, -0.8), "gate_ranged2": along(36.4, 1.2),
    "e_target": along(35.5),
    "more_melee1": along(33.0, -1.5), "more_melee2": along(33.0, 1.5),
    "more_ranged1": along(37.0, -1.0), "more_ranged2": along(37.0, 1.0),
    "vehicle": along(60.0),
    "vehicle_melee1": along(56.5, -1.0), "vehicle_melee2": along(56.5, 1.0),
    "vehicle_ranged1": along(54.3, -0.8), "vehicle_ranged2": along(54.3, 1.0),
    "scream1": along(15.9, -1.3), "scream2": along(15.3), "scream3": along(15.9, 1.3),
    "strength_melee1": along(69.0, -1.8), "strength_melee2": along(70.5, 0.4), "strength_ranged": along(69.5, 2.4),
    "car_b": (133.85, 13.9),
    "car_b_melee": (130.1, 15.6), "car_b_ranged": (130.9, 13.4),
    "ahead_melee": (145.5, 19.6), "ahead_ranged": (146.6, 17.6),
    "destroyer": (152.75, 24.0),
    "vehicle_wreck": (43.66, 52.61),       # DestVehicle / InvisibleTarget in 0x35000034
}

# 2026-10-22 (original's videos, Part 1 0:42-6:05 and wAngel 2:40-10:45; client: a Tutorial_Basic encounter starts with
# only the objective tracker and the hints, BaseHudElement.SetInitialVisibilityBasedOnEncounter): what the HUD shows
# when. The rest of the bar comes with level 2, the vitals with the first Sonic Batarang (Will), the experience bar
# with the W unlock, D with the camera, F with Super Strength.
START_HUD = [HUD_PORTRAIT, HUD_MINIMAP, HUD_OBJECTIVES, HUD_HINTS]
SKILL_BAR_HUD = [HUD_SKILLS_BAR, SKILL_BUTTON[0]]


def reveal_skill(slot, highlight=False):
    """A skill button appears (and may be used); with highlight, the tutorial's yellow frame around it."""
    return [("skill_button", slot)] + ([("highlight", SKILL_BUTTON[slot], SKILL_HIGHLIGHT[slot])] if highlight else [])


# the champion at the start: level 1, only the basic attack (each level gives a skill point)
START = {"level": 1, "skill_points": 0, "ranks": {0: 1}}
# placements created at the start (the rest come with their steps; the cinematics bring their own actors)
# 2026-10-22 08:13 (tester: the Destroyer's two flying vehicles stay doubled on the street and he walks through
# them): the intro cinematic brings its own wagons; ours were a second copy
INITIAL = ["03GateA", "03GateB", "DestVehicle", "01GateA", "PowerCore"]


def _p(*names):
    return [POSITIONS[n] for n in names]


METEOR_SCALE = 0.3                 # the earlier server's small meteors (property 0x6B4, the render scale)
DUST_CLOUD = 0x2E0007D4            # the impact's dust cloud (table 0x1D00020B: Vfx_Startup -> Vfx_Event1)
# 2026-10-22 (tester after fase3-gp: only the first big meteor leaves the lava crater; original Part 1 video 0:44-0:47
# and 1:15-1:18): a small strike is a fire column (~1 s) and a dust cloud, and leaves only small red rocks. The rock
# lands this long after it is created; the fire column (the strike entity's Vfx_Active, which loops) goes this
# long after the impact, the dust cloud object later.
STRIKE_IMPACT = 1.2
STRIKE_FIRE_SECONDS = 2.0
STRIKE_DUST_SECONDS = 8.0


def strike(group, spot):
    """A small meteor: the rock world state alone falls and lands with its own graph (env_event_meteor_a) at a third
    of its size and stays (the small red rocks); at its impact the strike entity's fire column (Vfx_Active of table
    0x1D0008B6 alone: no Vfx_Spawn_Event02, whose crater meshes 0x170001D0-D2 are the big crater) and the dust cloud.
    2026-10-22 10:00 (tester: the small one was the big strike again)."""
    xy = [POSITIONS[spot]]
    # the strike entity is created with the rock (an object takes its scriptlets once it exists on the client: the
    # big meteor waits 1 s too); the dust cloud comes at the impact
    # 2026-10-23 (tester after fase3-gq: "the big meteor's animation with the crater appears in several places"): the
    # crater entity's Vfx_Active also brings the big crater with its lava (its world state's table 0x1D000155), so the
    # small strike no longer creates it: the rock (its own fall and fire trail) and the dust cloud only
    return [("spawn_at", group, METEOR_ROCK, xy, 0, {0x6B4: METEOR_SCALE}),
            ("wait", STRIKE_IMPACT),
            ("spawn_at", group + "_dust", DUST_CLOUD, xy, 0),
            ("after", 0.3, ("scriptlet", group + "_dust", "Vfx_Startup")),
            ("after", STRIKE_DUST_SECONDS, ("remove", group + "_dust"))]


def strike_gp(group, spot):
    """fase3-gp's small meteor: the rock alone ([ics] tutorial_small_strikes = false)."""
    return [("spawn_at", group, METEOR_ROCK, [POSITIONS[spot]], 0, {0x6B4: METEOR_SCALE})]


def meteor(group, spot, knockdown=False):
    """A meteor: the crater entity plays its own fall (rock 0x2E000BB3), impact (dust 0x2E0007D4 and shockwaves)
    and fire column (Vfx_Active particles)."""
    # 2026-10-21 22:52 (tester: the crater vanishes right after the impact): the rock / crater 0x2E000BB3 that
    # Vfx_Spawn_Event01 attaches goes with the next scriptlet; the earlier server left its own copy on the spot
    return [("spawn_at", group, CRATER, [POSITIONS[spot]], 0),
            ("wait", 1.0),
            ("scriptlet", group, "Vfx_Spawn_Event01"),
            ("wait", 1.2),
            # 2026-10-22 09:30 (tester: two meteors fall): our copy of the rock 0x2E000BB3 played its own fall again
            # (graph env_event_meteor_a); it is no longer created
            *[("spawn_at", group + "_crater", mesh, [POSITIONS[spot]], 0) for mesh in CRATER_MESHES + [CRATER_STATE]],
            # 2026-10-22 10:00 (tester: the crater has no lava): the crater state's own Vfx_Active (table 0x1D000155)
            # attaches its lava meshes 0x2E001060 / 0x2E001061
            ("scriptlet", group + "_crater", "Vfx_Active"),
            # 2026-10-22 08:39 (tester: the crater still vanishes, the fire stays): Vfx_Spawn_Event02 attaches the
            # crater meshes 0x170001D0-D2 and runs Vfx_Active itself (table 0x1D0008B6); a Vfx_Active of ours replaced
            # it and took the meshes with it, leaving only Vfx_Active's fire
            ("scriptlet", group, "Vfx_Spawn_Event02")] + ([("knockdown", 5.0)] if knockdown else [])


STEPS = [
    # ---- part 1: the street ---------------------------------------------------------------------------------
    {"name": "intro", "do": [("cinematic", 0x35000026)]},
    # the marker comes with the objective (original's video 0:42); the small strike two seconds into the walk
    {"name": "walk1", "do": [("hud", START_HUD), ("objective", 0), ("marker", "marker1"), ("say_bg", 0x1BA),
                             ("wait", 2.0),
                             ("if", "tutorial_small_strikes", strike("meteor0", "small_meteor"),
                              strike_gp("meteor0", "small_meteor"))],
     "until": ("reach", "marker1", 3.5)},
    # the big meteor knocks Batman down (the earlier server: down from +1 s to +6 s)
    {"name": "meteor", "do": [("marker_off",)] + meteor("meteor1", "big_meteor", knockdown=True) + [
        ("say", 0x193), ("say_bg", 0x19C), ("objective", 1), ("marker", "marker2"), ("hint", HINT_GUIDE_ARROWS)],
     "until": ("reach", "marker2", 3.5)},
    # 2026-10-22 10:06 (tester): the drone fights the human; it may be attacked only once the dialogue says so,
    # and the human runs off when Batman attacks it
    {"name": "first_drone", "do": [
        ("marker_off",), ("remove", "meteor0"), ("say", 0x1AC), ("spawn", "drone", ["03MeleeC"]),
        ("untargetable", "drone"), ("spawn", "thug", ["03ThugB"]), ("aggro", "drone", 0),
        ("fight", "drone", "thug"), ("say", 0x1B8),
        ("targetable", "drone"), ("objective", 2), ("marker", "03MeleeC")],
     "until": [("hit", "drone"), ("killed", "drone")]},
    {"name": "drone_fight", "do": [
        ("fight", "drone", "champion"), ("walk", "thug", "thug_flee"), ("wait", 6.0), ("remove", "thug")],
     "until": ("killed", "drone")},
    {"name": "wave", "do": [
        # 2026-10-22 (tester after fase3-gp; original 1:15: a fire column beside Batman, then dust, small red rocks):
        # the wave's strike is a small one, not the big crater
        ("marker_off",), ("say", 0x1E1), ("say", 0x1E0),
        ("if", "tutorial_small_strikes", strike("meteor2", "wave_meteor"), meteor("meteor2", "wave_meteor_gp")),
        # 2026-10-22 (original's videos: the two drones come straight at Batman once they are there)
        ("spawn_at", "wave", "03MeleeA", _p("wave1", "wave2")), ("aggro", "wave"),
        ("objective", 3), ("say_bg", 0x38C), ("hint", HINT_BASIC_ATTACK)],
     "until": ("killed", "wave")},
    # level 2 (original 1:33): the skill bar with Q, W, E, R (rank 0, greyed), the passive and the basic attack; an
    # arrow over Q's "+" (1:41)
    {"name": "unlock_q", "do": [("say", 0x1DF), ("level", 2), ("hud", SKILL_BAR_HUD)]
     + [a for slot in (Q, W, E, R, PASSIVE) for a in reveal_skill(slot)] + [
        ("ranks", [Q]), ("say", 0x1D4), ("say_bg", 0x1BE), ("objective", 4), ("hint", HINT_SKILL_POINTS)],
     "until": ("ranked", Q)},
    {"name": "practice_q", "do": [
        ("ranks", []), ("say", 0x19B), ("say", 0x1AB),
        ("spawn_at", "targets", TARGET_DRONE, [POSITIONS["targetA"] + (-0.5,), POSITIONS["targetB"] + (-0.5,)]),
        ("only_skill", "targets", Q), ("guide", "targets"),
        ("say_bg", 0x1B7), ("objective", 5)],
     "until": [("cast", Q), ("killed", "targets")]},
    # the first Sonic Batarang costs Will: the health / Will bars appear, the Will one framed, and the Will hint (2:15)
    {"name": "will", "do": [("hud", [HUD_VITALS, HUD_STATUS_ICONS]), ("highlight", HUD_VITALS, HL_WILL),
                            ("hint", HINT_WILL)],
     "until": ("killed", "targets")},
    {"name": "catwoman", "do": [
        ("highlight_off", HUD_VITALS), ("say", 0x19A), ("say", 0x1E3),
        ("after", CATWOMAN_STRIKE_FRAME / 30.0, ("remove_named", "DestVehicle")), ("cinematic", CATWOMAN),
        # Catwoman broke the vehicle in the cinematic (her CinematicCharacter_State02 on InvisibleTarget); a skipped
        # cinematic can end before her strike
        ("remove_named", "DestVehicle"),
        *[("spawn_at", "vehicle_wreck", piece, [POSITIONS["vehicle_wreck"] + (VEHICLE_YAW,)], 0)
          for piece in VEHICLE_WRECK]]},

    # ---- part 2: the bridge ----------------------------------------------------------------------------------
    {"name": "pursuers", "do": [
        ("say", 0x1C9), ("spawn_at", "pursuers", "03MeleeA", _p("pursuer1", "pursuer2")), ("aggro", "pursuers"),
        ("objective", 6)],
     "until": ("killed", "pursuers")},
    # the experience bar under the portrait appears, framed, with the Experience hint (original 2:56)
    {"name": "unlock_w", "do": [("say", 0x1E5), ("level", 3), ("hud", [HUD_LEVEL_XP]),
                                ("highlight", HUD_LEVEL_XP, HL_LEVEL_XP), ("hint", HINT_EXPERIENCE),
                                ("ranks", [W]), ("say", 0x1E4), ("say_bg", 0x1C2), ("objective", 7)],
     "until": ("ranked", W)},
    {"name": "practice_w", "do": [
        ("ranks", []), ("highlight_off", HUD_LEVEL_XP), ("spawn_at", "w_target", TARGET_DRONE, _p("w_target")), ("only_skill", "w_target", W), ("guide", "w_target"),
        ("say", 0x1B1), ("say_bg", 0x192),
        ("objective", 8)],
     "until": ("killed", "w_target")},
    {"name": "surround", "do": [
        ("say", 0x191), ("spawn_at", "surround", "03MeleeA", _p("surround1", "surround2", "surround3")),
        ("aggro", "surround"), ("say_bg", 0x199), ("objective", 9)],
     "until": ("killed", "surround")},
    {"name": "upgrade", "do": [("say", 0x1D9), ("level", 4), ("ranks", [Q, W]), ("say_bg", 0x1D3), ("objective", 10)],
     "until": ("ranked", [Q, W])},
    {"name": "to_bridge", "do": [
        ("ranks", []), ("open", "03GateA"), ("say", 0x38D), ("marker", "marker_bridge"), ("objective", 1)],
     "until": ("reach", "marker_bridge", 3.0)},
    {"name": "ambush", "do": [
        ("marker_off",), ("close", "03GateA"),
        # 2026-10-22 (original Part 1 3:55-3:59: the three drones spawn in at the closed gate behind Batman and come
        # at him; 2.5 s later a small strike lands among them, ~2 m from him toward the gate, and leaves a red rock)
        ("if", "tutorial_ambush_from_gate",
         [("spawn_at", "ambush", "03MeleeA", _p("ambush_gate_melee1", "ambush_gate_melee2")),
          ("spawn_at", "ambush", "03RangedA", _p("ambush_gate_ranged"))],
         [("spawn_at", "ambush", "03MeleeA", _p("ambush_melee1", "ambush_melee2")),
          ("spawn_at", "ambush", "03RangedA", _p("ambush_ranged"))]),
        ("aggro", "ambush"), ("say_bg", 0x1CC), ("objective", 11),
        ("if", "tutorial_small_strikes", [("wait", 1.3)] + strike("meteor3", "ambush_strike"))],
     "until": ("killed", "ambush")},
    # the Surveillance Camera (D, slot 7: Gaslight Batman's own Stolen Power); standing on the spot also counts
    # its button appears framed (original 4:14)
    {"name": "camera", "do": reveal_skill(D, highlight=True) + [
        ("say", 0x22B), ("say", 0x22A), ("say_bg", 0x196), ("marker", "camera"), ("objective", 12)],
     "until": [("cast", D), ("reach", "camera", 1.5)]},
    {"name": "gate_fight", "do": [
        ("marker_off",), ("highlight_off", SKILL_BUTTON[D]), ("hint", HINT_SKILL_CHARGES),
        ("say", 0x1BD), ("spawn_at", "gate_mid", "03GateA", _p("gate_mid")),
        ("open", "gate_mid"), ("say_bg", 0x1D2),
        ("spawn_at", "gate", "03MeleeA", _p("gate_melee1", "gate_melee2")),
        ("spawn_at", "gate", "03RangedA", _p("gate_ranged1", "gate_ranged2")), ("aggro", "gate", 0),
        ("marker", "gate_drones"), ("objective", 13)],
     "until": ("killed", "gate")},
    {"name": "unlock_e", "do": [("marker_off",), ("say", 0x1C6), ("level", 5), ("ranks", [E]), ("say_bg", 0x1D1),
                                ("hint", HINT_SKILL_RANKS), ("objective", 14)],
     "until": ("ranked", E)},
    {"name": "practice_e", "do": [
        ("ranks", []), ("spawn_at", "e_target", TARGET_DRONE, _p("e_target")), ("only_skill", "e_target", E), ("guide", "e_target"),
        ("say_bg", 0x190), ("objective", 15)],
     "until": ("killed", "e_target")},
    {"name": "more_drones", "do": [
        ("say", 0x1AA), ("say", 0x1AE),
        ("spawn_at", "more", "03MeleeA", _p("more_melee1", "more_melee2")),
        ("spawn_at", "more", "03RangedA", _p("more_ranged1", "more_ranged2")), ("aggro", "more"),
        ("objective", 16)],
     "until": ("killed", "more")},
    {"name": "passive", "do": [("say", 0x1A1), ("points", 1), ("ranks", [PASSIVE]), ("hint", HINT_PASSIVE), ("say_bg", 0x18F),
                               ("objective", 17)],
     "until": ("ranked", PASSIVE)},
    {"name": "vehicle", "do": [
        ("ranks", []), ("say", 0x1E2), ("open", "03GateB"),
        ("spawn_at", "bridge_vehicle", "DestVehicle", [POSITIONS["vehicle"] + (CROSS_YAW - math.pi,)]),
        ("spawn_at", "vdrones", "03MeleeA", _p("vehicle_melee1", "vehicle_melee2")),
        ("spawn_at", "vdrones", "03RangedA", _p("vehicle_ranged1", "vehicle_ranged2")), ("aggro", "vdrones", 0),
        ("objective", 18)],
     "until": ("killed", "vdrones")},
    {"name": "unlock_r", "do": [("say", 0x1CB), ("level", 6), ("ranks", [R]), ("say_bg", 0x1DC), ("objective", 19)],
     "until": ("ranked", R)},
    {"name": "camera_unlock", "do": [
        ("ranks", []), ("say", 0x1A0), ("spawn_at", "scream", "03MeleeA", _p("scream1", "scream2", "scream3")),
        ("say", 0x1C8), ("say", 0x1B6), ("say_bg", 0x1B0), ("objective", 20)],
     # the client reports its camera setting (0x216E User.CameraLocked); after 20 s the flow goes on anyway
     "until": [("preference", "User.CameraLocked", "false", "0"), ("time", 20)]},
    {"name": "scream", "do": [("say", 0x1CA), ("objective", 21), ("say", 0x1B5), ("say", 0x1D8), ("objective", 22),
                              ("say_bg", 0x1D0)],
     "until": ("killed", "scream")},
    # the Spacebar and Camera zoom hints (wAngel 8:55, 9:05)
    {"name": "camera_lock", "do": [("say", 0x1A5), ("say", 0x1AD), ("objective", 23), ("hint", HINT_SPACEBAR),
                                   ("say", 0x1A8), ("objective", 24), ("hint", HINT_CAMERA_ZOOM), ("say_bg", 0x19F)],
     "until": [("preference", "User.CameraLocked", "true", "1"), ("time", 20)]},

    # ---- part 3: to the Destroyer ----------------------------------------------------------------------------
    # Super Strength (F, slot 8: Superman's) lifts and throws the vehicle at the drones; killing them any way ends it
    # F appears framed with the Earn Stolen Powers hint (wAngel 9:28)
    {"name": "strength", "do": reveal_skill(F, highlight=True) + [
        ("say", 0x1C5), ("say_bg", 0x1C1), ("objective", 25), ("hint", HINT_STOLEN_POWERS),
        ("spawn_at", "strength", "03MeleeA", _p("strength_melee1", "strength_melee2")),
        ("spawn_at", "strength", "03RangedA", _p("strength_ranged")), ("aggro", "strength", 0),
        ("say", 0x1C0), ("say_bg", 0x1B4), ("objective", 26)],
     "until": ("killed", "strength")},
    {"name": "destroyer_cinematic", "do": [("highlight_off", SKILL_BUTTON[F]),
                                           ("scriptlet", "bridge_vehicle", "Vfx_OnExplode"),
                                           ("cinematic", DESTROYER_CINEMATIC)]},
    # level 7 right after the Destroyer's cinematic: arrows over the passive, Q, W and E "+" (wAngel 9:57), and the
    # Super Strength and moving hint (9:55)
    {"name": "reach", "do": [
        ("level", 7), ("ranks", [Q, W, E, PASSIVE]), ("hint", HINT_SUPER_STRENGTH),
        ("say", 0x1D7), ("objective", 27),
        ("spawn_at", "car_b", "02PaddyWagonA", _p("car_b")),
        ("spawn_at", "car_b_drones", "03MeleeA", _p("car_b_melee")),
        ("spawn_at", "car_b_drones", "03RangedA", _p("car_b_ranged")), ("aggro", "car_b_drones", 0),
        ("spawn_at", "ahead", "03MeleeA", _p("ahead_melee")),
        ("spawn_at", "ahead", "03RangedA", _p("ahead_ranged")), ("aggro", "ahead", 6)],
     "until": ("reach", "destroyer", 14.0)},
    {"name": "destroyer", "do": [("say", 0x1C7), ("spawn", "destroyer", ["Destroyer"]),
                                 ("aggro", "destroyer", 0), ("objective", 28)],
     "until": ("killed", "destroyer")},
    {"name": "ending", "do": [("cinematic", ENDING), ("victory",)]},
]
