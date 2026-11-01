"""Tutorial 1, "A Champion in Peril": the scripted part, as data.

Phase 1 ported the old server's first two steps. Phase 2 adds the encounter
layout read from the game's own packs (see LAYOUT below and `ic.py layout`)
and the first fight: the drone from the cinematic, then the wave that
follows it, then the level-up that unlocks the first skill.
"""
import math
import struct
import time

from . import batman
from . import messages as M
from .bridge import Bridge
from .wire import KIND_BOOL, KIND_DID, KIND_ENUM, KIND_F32, KIND_IID, KIND_INT

ENCOUNTER = 0x40000991
LAYOUT_PACK = 0xA0000256          # encounter layout records (prefix 0x1d) live here

HUD_MINIMAP, HUD_PORTRAIT, HUD_MISSION_OBJECTIVES, HUD_HINTS = 15, 18, 35, 32
HUD_EVENT_FIRST_RESTORED = 1
START_ELEMENTS = (HUD_PORTRAIT, HUD_MINIMAP, HUD_MISSION_OBJECTIVES, HUD_HINTS)
# HUD element ids (emp_gen UIHUDElementID, read from the UI scripts' getters).
HUD = {
    "PlayerVitalBars": 2, "SkillButtonWUpgradeButton": 4, "SkillButtonRUpgradeButton": 5,
    "SkillButtonBasic": 6, "SkillButtonPassive": 7, "SkillButtonQ": 9, "SkillButtonR": 12,
    "SkillsBar": 14, "Minimap": 15, "SkillButtonW": 17, "Portrait": 18,
    "SkillButtonPassiveUpgradeButton": 19, "LevelAndExperience": 20, "SkillButtonE": 25,
    "SkillPointSpendReminder": 27, "SkillButtonEUpgradeButton": 28, "SkillButtonQUpgradeButton": 30,
    "StatusIconDisplay": 31, "HintManager": 32, "MissionObjectiveTracker": 35,
    "SkillsBarUpgradeReccommendedText": 45,
}
HUD_EVENT_SHOW_HIGHLIGHT = 7
# Revealed at the first level-up: vitals, skills bar, the skill buttons and
# their separate UPGRADE buttons (in a tutorial every element starts hidden;
# the upgrade buttons are elements of their own: Q 30, W 4, E 28, R 5, passive 19).
SKILL_ELEMENTS = tuple(HUD[n] for n in (
    "PlayerVitalBars", "SkillsBar", "LevelAndExperience", "StatusIconDisplay",
    "SkillButtonBasic", "SkillButtonQ", "SkillButtonW", "SkillButtonE", "SkillButtonR", "SkillButtonPassive",
    "SkillButtonQUpgradeButton", "SkillButtonWUpgradeButton", "SkillButtonEUpgradeButton",
    "SkillButtonRUpgradeButton", "SkillButtonPassiveUpgradeButton",
    "SkillPointSpendReminder", "SkillsBarUpgradeReccommendedText"))
FIRST_SKILL_UPGRADE = HUD["SkillButtonQUpgradeButton"]   # highlighted: "unlock the first skill"

OBJECTIVE_CATEGORY_SHOW = 8
CATEGORY_TITLE = "A Champion in Peril"
FIRST_OBJECTIVE = ("<font color='#FFFF00'>Right-click</font> on the marked location to move there"
                   "<br>(Follow the arrows at your Champion's feet)")
INTRO_CONVERSATIONS = (0x1BA,)

HINT_GUIDE_ARROWS, HINT_BASIC_ATTACK, HINT_EXPERIENCE, HINT_SKILL_RANKS, HINT_SKILL_POINTS = 16, 17, 18, 21, 34

# Guide-ping targets per step (landblock 0x13,0xcb local x, y, z). Overridden by
# [tutorial] targets in config.toml. Both walk targets lie west of the first
# drone (35.3, 56.3, from the layout and cinematic 0x35000033), on the way from
# the spawn point; after the second one the drone appears and the guide arrows
# point at it (step DRONE_STEP). The originals' positions are not in the packs.
TARGETS = {1: (25.0, 60.3, 200.0), 2: (30.5, 59.0, 200.0)}
DRONE_STEP = 3
TARGET_RADIUS = 3.5
DRONE_TRIGGER_RADIUS = 7.0     # walking this close to the first drone's spot brings it out

# Pacing (2026-10-14, from the original's chat log timestamps): each beat is
# (seconds after the event, what). "conv" = conversation key, "hint" = tutorial
# hint, "objective" = new objective text, "ping" = next guide ping. All delays
# are multiplied by [tutorial] pacing (0 = everything at once, as before).
#   00:43 A narrow escape! / 00:46-00:50 We need to keep moving... fog of war
#   00:55 What ARE these accursed machines? / 00:58 A corrupted drone. Take it out!
OBJ_MOVE = "<font color='#FFFF00'>Right-click</font> to move to the marked location"
OBJ_DRONE = ("<font color='#FFFF00'>Right-click</font> the drone to "
             "<font color='#00FF00'>Basic Attack</font> and defeat it")
MOVE_STEPS = {
    # he is down from +1 s to +6 s: "A narrow escape!" when he is up again, the
    # next marker (drone_appear_delay) at +7 s
    1: ((6.2, "conv", 0x193), (9.2, "conv", 0x19C), (7.0, "objective", OBJ_MOVE),
        (7.0, "hint", HINT_GUIDE_ARROWS), (7.0, "ping", None)),
    2: ((0.0, "conv", 0x1AC), (3.0, "conv", 0x1B8), (3.0, "objective", OBJ_DRONE)),
}

PING_CLASS = 0x40000A9C                      # "Map Ping": guide arrows point at it
GUIDE_KEYS = (0x10000F80, 0x10000F86)        # Vfx_GuideArrow, Vfx_GuideArrow_Ping (Batman's table)
# type 1 = Alt+click (alert), 2 = Ctrl+click (retreat). 2026-10-14 14:14: with
# 1 -> 0x4000025A they showed swapped, so alert is 0x4000025B.
PLAYER_PING_CLASSES = {1: 0x4000025B, 2: 0x4000025A}

# ---- encounter layout (pack 0xa0000256, records 0x1d000771 / 0x1d0007ee) --------------
# name: (world state DID, (x, y, z) in landblock 0x13,0xcb, yaw radians)
# Extracted with `python ic.py layout 0xa0000256`; tests/test_layout.py checks
# that this table still matches the packs.
LAYOUT = {
    "03MeleeC": (0x2E001167, (35.34, 56.35, 199.95), 0.293),    # = "Drone_01" in cinematic 0x35000033
    "03MeleeD": (0x2E001167, (36.26, 57.69, 199.95), 1.584),
    "03MeleeA": (0x2E001167, (49.36, 49.34, 200.05), -1.835),
    "03MeleeB": (0x2E001167, (47.87, 46.76, 200.08), -1.905),
    "03RangedA": (0x2E001168, (46.58, 50.33, 199.93), -1.906),
    "03RangedB": (0x2E001168, (45.61, 48.59, 199.93), -2.073),
    "03ThugA": (0x2E0012BB, (44.22, 59.02, 199.99), 1.571),
    "03ThugB": (0x2E0012BB, (34.92, 57.60, 199.93), -1.529),
    "DestVehicle": (0x2E000AAB, (43.66, 52.61, 199.86), -2.512),
    "03GateA": (0x2E0010F3, (54.05, 44.80, 200.08), -2.042),
    "03GateB": (0x2E0010F3, (89.87, 26.21, 200.16), -2.042),
}
# World state -> character variant (pack 0xa0000257: the variant's twin record
# 0x49xxxxxx names the world state). A variant gets the game components
# (vitals, combat); a bare world state does not, and must never get event 0x42.
VARIANTS = {
    # The tutorial's own Soldier Drone variant 0x40000C72 can NOT be targeted by
    # the client (it never sent an attack order for it, 2026-10-13), while the
    # Trooper 0x40000A5D could. 0x40000A5C is the matching generic Soldier Drone.
    0x2E001167: 0x40000A5C,   # Soldier Drone (melee)
    0x2E0012BB: 0x40000C71,   # Stabber (thug)
    0x2E001298: 0x40000BA9,   # Target Drone (practice): rig 0x2D000F92 chr_minion_target_drone
    0x2E001168: 0x40000A5D,   # no variant names the tutorial's ranged drone: Trooper Drone stands in
    0x2E000AB5: 0x40000EB2,   # the Destroyer (02Destroyer / Destroyer of the layout), pack 0xA0000257
}
# Not in the layout: the practice targets after the first skill ("Construct:
# can we have some target drones?"). Their world state is 0x2E001298 (rig
# 0x2D000F92 = chr_minion_target_drone: small drone on a stand with a ring) and
# their entity 0x40000BA9 (twin 0x49000BA9, property 0x510). 0x2E000808, used
# before, is a generic soldier drone (rig 0x2D00068A, like 0x2E001167).
# Positions estimated from the original's screenshot (2026-10-14): up the
# street from the fight, left of the vehicle. Overridable: [tutorial] practice_positions.
TARGET_DRONE = 0x2E001298
# 14:30 (picture): the paddy wagon's model lies along its yaw + 90 degrees
# (the street's police wagon lies along its yaw). Spawns add this offset so a
# yaw always names the line the car covers (its walking box uses the same yaw).
MODEL_YAW_OFFSET = {0x2E00034D: -math.pi / 2, 0x2E00034E: -math.pi / 2}
EXTRA_SPAWNS = {
    "03TargetA": (TARGET_DRONE, (42.8, 59.6, 200.0), -0.5),
    "03TargetB": (TARGET_DRONE, (44.2, 57.3, 200.0), -0.5),
    # 2026-10-14 20:54 (dump "crater"): the crater the big meteor leaves is the
    # entity 0x400004FD (world state 0x2E0004BE, .entity 0x2D000375; "Crater1-3"
    # in another tutorial's placement list 0x1D0007E9). Its records are in packs
    # 0xA00000B3 / 0xA000024C, which the tutorial loads.
    "Crater": (0x400004FD, (19.6, 58.9, 200.0), 0.0),
    # 2026-10-15: three blue gates on the bridge (the original's video): the
    # layout has the first and the last (03GateA / 03GateB); the one in the
    # middle is placed on the line between them (bridge.py, [tutorial] bridge_gates)
    "03GateMid": (0x2E0010F3, (69.58, 36.74, 200.1), -2.042),
}
CRATER_WSTATE = 0x2E0004BE
LAVA_CRATER_WSTATES = (0x2E001144, 0x2E001145, 0x2E001146)
# [debug] tour_keys = "core" (old spelling "nucleo" also accepted): the actions
# that matter for Batman's kit and the combat engine (00:50: the full tour is
# mostly shared effects of every champion).
TOUR_CORE = (
    (0x10000164, "Q Sonic Batarang (full skill)"), (0x10000163, "W Sonic Shell"),
    (0x10000165, "E Bat Flight"), (0x10000162, "R The Bat Scream"),
    (0x10000195, "basic attack right"), (0x10000196, "basic attack left"),
    (0x10000188, "shot effect right"), (0x10000189, "shot effect left"),
    (0x1000017e, "critical effect"), (0x10000209, "hit reaction"),
    (0x1000003d, "CbtState_KnockUp (knocked into the air)"), (0x100001f9, "_Defeat_StartupIncapacitated"),
    (0x100001fb, "_Defeat_OnIncapacitated"), (0x10000490, "RunScript_Vfx_GetUp (get up)"),
    (0x100001fa, "_Defeat_OnDead (death)"), (0x100001fc, "_Defeat_OnRespawn (respawn)"),
    (0x100001fd, "_Defeat_OnRevive"), (0x10000999, "stunned (effect)"),
    (0x10000201, "level up"), (0x10000181, "Vfx_Bmg_Spawn (appear)"),
    (0x100009fb, "teleport"), (0x100001d3, "emote laugh"), (0x10000641, "emote dance"),
    (0x10000643, "emote joke"), (0x1000115e, "emote oath"),
)
CRATER_EXTRAS = ()   # 00:08: 0x2E0005D6 showed as a grey square: no extras
# the map's copy sits ~(-1.7, +1.4) m from what it shows: same spot on screen as
# the old crater (accepted at 23:07)
LAVA_CRATER_AT = (19.5, 63.0)
# 2026-10-14 21:44 (diag --create): the crater object builds like the rocks, but its
# .entity 0x2D000375 (in pack 0xA000024C) is only a one-bone skeleton without a
# mesh: what shows must come from its scripts (VFX/decals). Probes: Vfx_Startup,
# Vfx_Spawn_Alt01, Vfx_Event1, _Entity_OnEnterWorld_Default (diag --scripts lists
# the crater's own table).
CRATER_KEYS = (0x1000018E, 0x10000347, 0x10000076, 0x100002F5)
# 2026-10-14 22:14: entity 0x400004FD loads but has no scriptlets either (0 groups),
# so the lava is not a script. Tutorial 1's own pack has the crater's spawn
# template 0x1D0008B6 (entity 0x400004FD, world state 0x2E0004BE) with these
# properties. 22:21: sent with the crater it no longer showed (and the player's
# pings stopped reaching the minimap): off by default ([tutorial] crater_props =
# "template" sends them, or a list of [id, kind, value]).
CRATER_PROPS = ((0x10000AA7, "int", 1), (0x8B2, "int", 8), (0x8A5, "f32", 5.0), (0x8A3, "f32", 3.0),
                (0x83C, "int", 1), (0x8C1, "int", 1), (0x1000019D, "int", 0x2000), (0x149, "u32", 0x08000000))
_PROP_KINDS = {"int": KIND_INT, "f32": KIND_F32, "u32": 0x13, "bool": KIND_BOOL, "did": KIND_DID, "enum": KIND_ENUM}
STATIC_SCENERY = ("Crater",)      # entities that are part of the ground: never hidden by the fog
FIRST_DRONE = "03MeleeC"
THUG = "03ThugB"          # the human fighting the first drone; runs away when Batman attacks
THUG_FLEE_TO = (24.0, 64.0, 200.0)
CATWOMAN_CINEMATIC = 0x35000034   # Catwoman breaks the vehicle blocking the street
# How long the client takes to speak a conversation (text length; the voice
# files are not read): ~2.6 words/s + 0.8 s per line. 0x19A: "When you use a
# skill, it goes 'on cooldown'." + "After the timer ends, you can use it again."
# 0x1E3: "Using that skill also consumed 'Will', a resource Gaslight Batman
# recovers over time."
CONV_SECONDS = {0x1BA: 5.1, 0x193: 3.1, 0x19C: 11.5, 0x1AC: 3.0, 0x1B8: 3.1, 0x1E1: 4.6, 0x1E0: 4.7,
                0x38C: 6.6, 0x1DF: 1.6, 0x1D4: 5.3, 0x1BE: 4.9, 0x19B: 6.4, 0x1AB: 3.7, 0x1B7: 9.7,
                0x19A: 8.8, 0x1E3: 5.8,
                # the Bat Scream part (estimates from the line lengths)
                0x1A0: 5.0, 0x1C8: 3.2, 0x1B6: 3.0, 0x1B0: 3.0, 0x1CA: 5.5, 0x1B5: 5.0, 0x1D8: 9.5,
                0x1D0: 3.0, 0x3AC: 5.5, 0x1A5: 7.5, 0x1AD: 3.2, 0x1A8: 5.0, 0x19F: 3.0}
# The client queues conversations: one sent while another is being spoken waits
# for it (2026-10-14: after a quick Batarang, 0x1B7, 0x19A and 0x1E3 were still
# queued when the cinematic started). speech_end tracks when the queue empties.
# The cinematic has its own "Gaslight_Batman" actor here (pack 0xa0000256);
# the player's Batman is not hidden, so he is moved onto it beforehand.
CATWOMAN_CINEMATIC_BATMAN = ((40.687, 58.229, 199.985), 2 * math.atan2(-0.9724, 0.2333))
# Meteor impacts: world state 0x2E0007D4 (pack 0xa0000256) carries the
# vfx_env_event_meteor_dust_cloud rig (0x2D000656) and script table 0x1D00020B.
# ("PowerCore" 0x2E000AC5 was wrong: its scripts are Vfx_Relay_*, a relay/turret.)
# 2026-10-14 20:30 (dump): 0x2E0007D4 (.entity 0x2D000656) is only the impact's
# DUST CLOUD (vfx_env_event_meteor_dust_cloud_rig: the "grey columns"). The rock
# is 0x2E000BB3 (.entity 0x2D00048D, env_event_meteor_a_rig: Root / Meteor /
# Meteor_cap), present in pack 0xA000024C, the one the tutorial already loads.
METEOR_CLASS = 0x2E000BB3
METEOR_DUST_CLASS = 0x2E0007D4
PROP_OBJECT_BASE_ID = 0x0200000000001000     # meteors, craters, blasts: + n
# 2026-10-14 16:15 (screenshot): the 3 small meteors land right around Batman's
# start (18.7, 60.4) and stay until he gets up after the big one; the big one
# opens a crack behind him at the first marker and stays.
SMALL_METEORS = ((20.6, 60.0, 200.0), (20.8, 57.6, 200.0), (17.6, 57.2, 200.0))
WAVE_METEOR = (24.0, 66.0, 200.0)
# 2026-10-14 22:00 (screenshot vs video): at (19.6, 58.9) the crater showed ~6 m
# to the right of where the video has it (x = screen right, y = screen down)
# 22:14: at (13.5, 60.0) it was too far left; the video has it ~3.5 m further on
# 22:28: a bit closer to the street lamp (video)
# 22:35: the extra 0x2E000A9F was a turret base plate, centred on the object's
# origin: the camera turns the map (+x = screen up-right, +y = screen up-left,
# ~53 px/m) and the crater's mesh sits ~(3.2, 0.3) m off its origin. Against
# the lamp (~(18.2, 66.0)) the video's crater needs its origin at ~(15.7, 60.3).
# 22:57: still ~(+2.3, +1.0) m off against the lamp in the video
BIG_METEOR = (18.0, 61.3, 200.0)
METEOR_LIFETIME = 8.0
# 2026-10-14 16:30: 0x10000209 (_HFSM_TargetHitAction_PhysicalReaction) is only a
# flinch. CbtState_KnockUp (0x1000003D, in Batman's scriptlet table) throws him
# up and down; then he gets up ([tutorial] knockdown_keys).
KNOCKDOWN_KEYS = (0x100001FB,)            # _Defeat_OnIncapacitated (seen 01:15)
GETUP_KEYS = (0x100001FD, 0x10000490)     # _Defeat_OnRevive + RunScript_Vfx_GetUp
# graph events (name table 0x300000A4) for the face-down knockdown (knockdown())
KNOCKDOWN_EVENTS = (0x100002F5,)          # CbtState_Knockdown
KNOCKDOWN_SNAP_EVENTS = (0x1000010B,)     # CbtState_Dead: the frozen face-down pose
GETUP_EVENTS = (0x1000009D,)              # CbtState_GetUp (Knockup_Selection 0 = face down)
GETUP_FX_KEYS = (0x10000490,)             # RunScript_Vfx_GetUp
RAISE_EVENT_KEY, RAISE_EVENT_VAR = 0x100001E3, 0x780   # _HFSM_BehaviorRaiseEventAction, event variable
# Probes sent to a new meteor / the vehicle so `diag.py --scripts` lists their
# script tables: _Entity_OnEnterWorld_Default, Destructible_AdvanceState.
# The meteor's own table (diag 2026-10-13): Vfx_Startup, Vfx_Spawn_Alt01, Vfx_Event1.
METEOR_PROBE_KEYS = (0x1000018E, 0x10000347, 0x10000076)
VEHICLE_PROBE_KEYS = (0x10000063,)
VEHICLE_BREAK_KEYS = (0x10000063,)     # Destructible_AdvanceState: intact -> damaged -> wreck
VEHICLE_HIT_RADIUS = 4.5               # m from the vehicle's centre: a Q thrown there hits it
# While the player does not attack, the first drone fights the human: its melee
# attack (0x100000EC, "Vfx_Min_Basic_Melee"/"Combat_Special_Attack_1", in the
# drones' script table) every FIGHT_INTERVAL s, and the human reacts.
DRONE_FIGHT_KEYS = (0x100000EC,)
THUG_HIT_KEYS = (0x10000209,)
# The human swings back half a beat later (0x10000124 is in his table too) and
# the drone flinches ([tutorial] thug_attack_keys, [] = he only takes hits).
THUG_ATTACK_KEYS = (0x10000124,)
DRONE_HIT_KEYS = (0x10000209,)
# 22:57: the human stood side-on to the drone. His model faces +x at yaw 0
# (the layout's -1.529 points at the drone), the drones' +y: [tutorial] thug_yaw_offset.
# 23:07: with +pi/2 he had his back to the drone: -pi/2. 23:15: almost facing
# it, still ~30 degrees short (he looks straight down the screen, the drone is
# down-right): -pi/2 + 0.52
# 00:00: the video has him side-on to the drone while they fight (a batter's
# stance): his original spot and facing were right. No turn, no shift.
THUG_SHIFT = (0.0, 0.0)
THUG_YAW_OFFSET = 0.0
FIGHT_INTERVAL = 1.4    # _HFSM_TargetHitAction_PhysicalReaction on Batman
WAVE = ("03MeleeA", "03MeleeB")   # "2 new drones hit the vehicle blocking the street"
# The layout puts them past the vehicle (x 48-49, by the first blue door); in the
# game they hit it from Batman's side (2026-10-14). Overridable: [tutorial] wave_positions.
# Drones fight back (2026-10-14: "the drones should attack me and hurt me").
# A drone turns aggressive when Batman attacks it (the wave also when he comes
# close); it walks up to him and hits with its melee script.
DRONE_AGGRO_RADIUS = 0.0     # 0 = only the drone Batman attacks turns on him (2026-10-14 11:50: "as
                             # before: they appear hitting the vehicle and the one I attack attacks me";
                             # 6 m made the wave charge at once). Earlier: they
                             # attacked by themselves from far away)
DRONE_LEASH = 8.0            # an aggressive drone farther than this from Batman calms down
DRONE_ATTACK_RANGE = 2.2
RANGED_ATTACK_RANGE = 6.0    # the ranged drones (Trooper) shoot from here
DRONE_ATTACK_INTERVAL = 1.6
DRONE_DAMAGE = 6          # halved 2026-10-14 ("a bit high")
DRONE_WALK_SPEED = 1.6      # m/s ([tutorial] drone_walk_speed); 3.0 looked like sliding
DRONE_TICK = 0.25           # s between AI updates (smaller steps = smoother walk)
DRONE_SPAWN_KEYS = (0x10000032, 0x10000033)    # Vfx_Spawn + Vfx_Fade_In: they "teleport in"
# (delay s, script key): the teleport-in, spread out (2026-10-14: "too fast").
# Overridable: [tutorial] spawn_sequence = [[0.1, 0x10000032], ...]
SPAWN_SEQUENCE = ((0.1, 0x10000032), (0.9, 0x10000033), (1.6, 0x10000033))
# Attack scripts tried in turn, one per hit, logged with the key so the one that
# shows the swing can be kept ([tutorial] drone_attack_keys). 0x100000EC alone
# showed nothing (2026-10-14).
# 2026-10-14: the old keys came from the wrong name table (animnames); the
# scriptlet keys are the anim-event ids (animevents): Robot_Minion_Melee_Attack
# 0x10000124, Combat_Basic_Attack 0x10000128, Vfx_Min_Basic_Melee 0x100000EC,
# Vfx_Min_Basic_Melee_Active 0x10000008. Each entry = the scripts of one swing
# (animation + effect, like Batman's basic attack: Combat_Basic_Attack_Right +
# Vfx_Bmg_Basic_Ranged_Right).
# 2026-10-14 21:52 (diag --scripts): the drone's table rejects 0x10000128 and
# 0x10000008 (0x80070057): only the first swing played, the others did nothing.
DRONE_ATTACK_KEYS = ((0x10000124, 0x100000EC),)
# Skill ranks for the HUD: the patched client reads them from this champion
# property (int, 4 bits per skill slot; slot 1 = Q). See patcher.py.
SKILL_RANKS_PROPERTY = 0x100006C1
# Sonic Batarang (Q). Batman: Batman_Gaslight_Sonic_Batarang (0x10000164, in his
# script table) with the target as script variable 0x108; each drone it reaches:
# VFX_CBT_Hit_Shared + physical reaction. It ricochets to the nearest other
# enemy within BATARANG_RICOCHET_RANGE, BATARANG_BOUNCES times at most.
# 0x100000EB is Vfx_Active (not Combat_Special_Attack_2: that came from the wrong
# name table). Batman_Gaslight_Sonic_Batarang + Vfx_Bmg_Batarang (the projectile),
# Vfx_Bmg_Batarang_Stop when it is over.
BATARANG_CAST_KEYS = (0x10000164, 0x10000171)
BATARANG_STOP_KEYS = (0x1000017B,)
BATARANG_COOLDOWN = 2.0        # s: the client repeats Q while it is held (4 orders in 0.5 s)
BATARANG_HIT_KEYS = (0x10000223, 0x10000209)
BATARANG_DAMAGE = 200
BATARANG_RICOCHET_RANGE = 8.0
BATARANG_BOUNCES = 2
BATARANG_FLIGHT = 0.45         # s until it reaches the first target
BATARANG_HOP = 0.3             # s per ricochet
# The client's real skill ranks (GetSkillRank rva 0x463ce0): champion property
# 0x100000AF (kind 0xC, array) indexed by slot 1-5 (a slot's own index
# property 0x10000A16 is absent for Gaslight Batman), int elements. Any int
# property id types the elements; Level's is used.
RANK_ARRAY_PROPERTY = 0x100000AF
RANK_ELEMENT_PROPERTY = 0x10000167
Q_SLOT = 1          # the client's skill slot index of Q (its "+" queries slot 1)


def set_recommended(ranks, slot):
    """SKILL_RANKS_PROPERTY: bits 0-27 = rank per slot (4 bits each, slots 0-6),
    bits 28-31 = recommended slot + 1 (0 = none)."""
    return (ranks & 0x0FFFFFFF) | ((slot + 1) << 28 if slot is not None else 0)
BATMAN_HIT_KEYS = (0x10000223,)                # VFX_CBT_Hit_Shared on Batman
# along the vehicle's square-side flank, 2.2 m from its long axis (2026-10-14
# 16:22: MeleeB at (40.6, 52.6) stood apart from the vehicle)
WAVE_POSITIONS = {"03MeleeA": (43.6, 55.3, 200.0), "03MeleeB": (41.2, 53.5, 200.0)}
SCENERY = ("DestVehicle", "03GateA", "03GateMid", "03GateB")
# Props are entities 0x40xxxxxx whose twin 0x49xxxxxx names the world state
# (property 0x510). Creating the bare world state gives an object with scripts
# but no model (2026-10-14: vehicle, gates and meteors invisible although all
# their records are in loaded packs). Filled at server start by
# resolve_prop_classes() from the packs below; the Door is known already.
PROP_CLASSES = {0x2E0010F3: 0x40000B0F}
# Class 0x4A-0x4F + the low 24 bits of a world state = "carrier entity N
# (N = prefix - 0x4A, table in the patched exe: [combat] prop_carriers) built
# with world state 0x2Exxxxxx" (patcher.py, props). For world states that no
# entity names (vehicle, meteors).
PROP_OVERRIDE_BASE = 0x4A


def prop_class(wstate, cfg, slot=None):
    """Class id to send for a prop world state."""
    if wstate in PROP_CLASSES:
        return PROP_CLASSES[wstate]
    if cfg["combat"].get("prop_override", True):
        slot = int(cfg["combat"].get("prop_carrier_slot", 0) if slot is None else slot) % 6
        return ((PROP_OVERRIDE_BASE + slot) << 24) | (wstate & 0x00FFFFFF)
    return wstate


def is_override_class(class_id):
    return PROP_OVERRIDE_BASE <= class_id >> 24 <= PROP_OVERRIDE_BASE + 5
WSTATE_PROPERTY = 0x510         # an entity's world state (twin 0x49 records)
# 17:36 (static analysis): a client object's allowed-scriptlet list is built,
# once, from its property 0x7D2 (a list of 0x1D script templates, element key
# 0x462) when its script component starts (0x57B860 -> 0x58EDD0). A prop built
# on a carrier never gets its world state's 0x7D2 ("0 groups" in diag
# --scripts), so every scriptlet on it was rejected. Sent with the object:
# world state -> (script template, behavior graph)  ([combat] prop_script_tables)
SCRIPT_TABLE_PROPERTY, SCRIPT_TABLE_ELEMENT = 0x7D2, 0x462
WSTATE_SCRIPT_TABLES = {
    0x2E00034D: (0x1D0000BB, 0x1C000021),     # 02PaddyWagonA
    0x2E00034E: (0x1D0000BA, 0x1C000021),     # 02PaddyWagonB
}


def script_table_props(wstate, cfg):
    """Extra properties giving a carrier-built prop its world state's scriptlets."""
    from .wire import KIND_ARRAY
    tables = dict(WSTATE_SCRIPT_TABLES)
    for key, value in (cfg["combat"].get("prop_script_table_map") or {}).items():
        tables[int(str(key), 16)] = tuple(int(v) for v in value)
    if not cfg["combat"].get("prop_script_tables", True) or wstate not in tables:
        return []
    table, behavior = tables[wstate]
    templates = table if isinstance(table, (tuple, list)) else (table,)
    props = [(SCRIPT_TABLE_PROPERTY, KIND_ARRAY, [(SCRIPT_TABLE_ELEMENT, KIND_DID, t) for t in templates])]
    if behavior:
        props.append((0x5B5, KIND_DID, behavior))
    return props
PROP_PACKS = (0xA000024C, 0xA0000256, 0xA0000257)
# 14:54 (diag --scripts): the paddy wagon on its carrier (entity 0x40000B0F)
# has an empty scriptlet table; its own entity, if a pack has one, is used
PROP_WSTATES = (0x2E000AAB, METEOR_CLASS, 0x2E0010F3, 0x2E00034D, 0x2E00034E)


def resolve_prop_classes(cfg, log=None):
    """Look up the entity class of each prop world state in the game's packs
    (a few seconds; run in a background thread at server start)."""
    import os
    from . import rp
    if not cfg["combat"].get("prop_entities", True):
        PROP_CLASSES.clear()
        return {}
    for key, value in (cfg["combat"].get("prop_classes") or {}).items():
        PROP_CLASSES[int(str(key), 16)] = int(value)
    packs = rp.PackSet(os.path.join(cfg.game_dir, "rp"))
    missing = [w for w in PROP_WSTATES if w not in (cfg["combat"].get("prop_classes") or {})]
    for pack_id in PROP_PACKS:
        if not missing:
            break
        try:
            found = rp.entity_classes_for(packs.pack(pack_id), missing)
        except (OSError, ValueError) as e:
            if log:
                log(f"props: could not read pack {pack_id:#x}: {e}")
            continue
        PROP_CLASSES.update(found)
        missing = [w for w in missing if w not in found]
    if log:
        log("props: " + ", ".join(f"{w:#x} -> {PROP_CLASSES[w]:#x}" if w in PROP_CLASSES else f"{w:#x} -> (no entity)"
                                  for w in PROP_WSTATES))
    resolve_script_tables(cfg, log)
    return dict(PROP_CLASSES)


# world states the server builds on a carrier: their scriptlet templates are read
# from their own records at server start (resolve_script_tables)
TABLE_WSTATES = (0x2E00034D, 0x2E00034E, 0x2E000AAB, 0x2E000AC5, METEOR_CLASS, METEOR_DUST_CLASS, 0x2E0010F4)


def resolve_script_tables(cfg, log=None):
    """2026-10-16 (diag --scripts): a prop built on a carrier had no scriptlets
    unless its world state's templates were sent (property 0x7D2, behavior graph
    0x5B5): the falling sphere (0x2E000AC5) rejected its start / open scripts.
    They are now read from each world state's own record ("did | 7 | .entity |
    0 | count | entries") in the player's packs."""
    import os
    from . import gamedata
    if not cfg["combat"].get("prop_script_tables_auto", True):
        return
    try:
        game = gamedata.Game(os.path.join(cfg.game_dir, "rp"), os.path.join(cfg.log_dir, "props.txt"))
        found = []
        for ws in TABLE_WSTATES:
            rec = game.world_state(ws)
            if not rec:
                continue
            _entity, entries = rec
            tables = tuple(v for _k, _kind, v in (gamedata.get(entries, SCRIPT_TABLE_PROPERTY) or [])
                           if isinstance(v, int))
            behavior = gamedata.get(entries, 0x5B5) or 0
            if tables:
                WSTATE_SCRIPT_TABLES[ws] = (tables, behavior)
                found.append(f"{ws:#x} -> {' '.join(hex(t) for t in tables)}" + (f" (graph {behavior:#x})" if behavior else ""))
        if log:
            log("prop scriptlet tables: " + ("; ".join(found) or "none found in the packs"))
    except Exception as e:                # never stop the server for this
        if log:
            log(f"prop scriptlet tables: {e!r}")

WAVE_OBJECTIVE = ("<font color='#FFFF00'>Right-click</font> the drones to defeat them with "
                  "<font color='#00FF00'>Basic Attacks</font> ({}/2)")
SKILL_OBJECTIVE = "Click the highlighted button to unlock your <font color='#00FFFF'>Sonic Batarang</font> Skill"
PRACTICE = ("03TargetA", "03TargetB")
PRACTICE_OBJECTIVE = ("Place your cursor on a target and press <font color='#FFFF00'>('Q')</font> "
                      "to destroy it with <font color='#00FFFF'>Sonic Batarang</font>")
UPGRADE_ELEMENTS = tuple(HUD[n] for n in (
    "SkillButtonQUpgradeButton", "SkillButtonWUpgradeButton", "SkillButtonEUpgradeButton",
    "SkillButtonRUpgradeButton", "SkillButtonPassiveUpgradeButton",
    "SkillPointSpendReminder", "SkillsBarUpgradeReccommendedText"))
HUD_EVENT_HIDE = 2
OTHER_UPGRADE_BUTTONS = tuple(HUD[n] for n in (
    "SkillButtonWUpgradeButton", "SkillButtonEUpgradeButton",
    "SkillButtonRUpgradeButton", "SkillButtonPassiveUpgradeButton"))


# The guide ping's own property set in the packs (0x1D0007A9, "Map Ping", the
# one with map note category 0x12) carries property 0x8E = a list of two 0x30E
# entries: 0x3400053C (only used by that set) and 0x34000600. Candidates for the
# green ground ring; sent with the markers ([tutorial] marker_vfx, [] = off).
MARKER_VFX = (0x3400053C, 0x34000600)
VFX_LIST_PROPERTY, VFX_ELEMENT_PROPERTY = 0x8E, 0x30E


def marker_vfx_property(cfg):
    dids = cfg["tutorial"].get("marker_vfx", [])        # crashes the client (2026-10-14 15:11)
    if not dids:
        return []
    from .wire import KIND_ARRAY
    return [(VFX_LIST_PROPERTY, KIND_ARRAY, [(VFX_ELEMENT_PROPERTY, KIND_DID, int(d)) for d in dids])]


def ping_team(match):
    """PVP_Team on the pings. 2026-10-14: with the champion's team (1) the marker
    shows RED (enemy colour?); the player object carries no team, so 0 may read
    as "ours" (green). [tutorial] ping_team, -1 = the champion's team."""
    v = int(match.cfg["tutorial"].get("ping_team", 0))
    return match.team if v < 0 else v


def ping_properties(team, style="minimal", show=True):
    """Properties sent on pings / markers ([tutorial] ping_style):
      minimal - only "show on the map": each ping class keeps its own icon
                (2026-10-14 17:12: the two pings show different icons this way)
      team    - minimal plus PVP_Team (the colour, see ping_team_for)
      full    - the old set (icon 0x13000A15, category 0x12, scriptlet bool)"""
    # "show on the map": off when an invisible companion carries the minimap
    # note (else, with the exe's team-read patch, every ping would show twice)
    props = [(0x100007D8, KIND_BOOL, 1 if show else 0)]
    if style in ("team", "full"):
        props.append((0x1000009C, KIND_INT, team))       # PVP_Team
    if style == "full":
        props += [
            (0x10000083, KIND_DID, 0x13000A15),  # map note icon
            (0x100004DA, KIND_ENUM, 0x12),       # map note category
            (0x10000909, KIND_BOOL, 1),          # scriptlet bool (ground marker candidate)
        ]
    return props


def ping_style(match):
    return str(match.cfg["tutorial"].get("ping_style", "team")).lower()


# The client colours a ping by the relation of its PVP_Team to the local
# player's team (rva 0x853380): same team = friend (4, blue), one of them 0 =
# neutral (1), different / -1 = enemy (2, red). 2026-10-14: team 1 (Batman's)
# gave blue, -1 / no player team gave red. So Alt (alert) goes as an enemy
# team (red) and Ctrl (retreat) and the tutorial marker as neutral (0; green?).
# [tutorial] ping_class_teams = { "0x4000025B" = 2, "0x4000025A" = 0 }
PING_CLASS_TEAMS = {0x4000025B: 2, 0x4000025A: 0}


# Minimap notes (map manager rva 0x64b150): an entity with "show on the map"
# gets a note with its icon 0x10000083, category 0x100004DA and icon variant
# 0x100007FB, but NOT when its team is an enemy's (relation 2, rva 0x853380).
# The red (enemy-team) Alt ping would never show there, so every ping gets an
# invisible companion (the guide's "Map Ping" class, InvisibleTarget) on the
# same spot that only carries the note, with a neutral team.
# The ping classes' own record (0x4900025A): icon 0x13000A15, category 1.
MAP_NOTE_ICON = 0x13000A15
MAP_NOTE_BASE_ID = 0x0200000000000070       # + n % 0x10
MAP_NOTE_VARIANTS = {0x4000025B: 0, 0x4000025A: 1}   # alert / retreat (guess)


def map_note_properties(match, class_id, category=None):
    tc = match.cfg["tutorial"]
    if category is None:
        category = int(tc.get("map_note_category", 0x1D))
    variants = dict(MAP_NOTE_VARIANTS)
    raw = tc.get("map_note_variants")
    if isinstance(raw, dict):
        for k, v in raw.items():
            try:
                variants[int(str(k), 0)] = int(v)
            except ValueError:
                pass
    return [
        (0x100007D8, KIND_BOOL, 1),                                       # show on the map
        (0x1000009C, KIND_INT, int(tc.get("map_note_team", 0))),          # not an enemy's
    ] + ([(0x10000083, KIND_DID, int(tc.get("map_note_icon", 0)))] if int(tc.get("map_note_icon", 0)) else []) + [
        # 2026-10-14 18:41: with icon 0x13000A15 the minimap showed a yellow cone
        # next to the ping's own icon: the HUD draws the ping icon by itself
        (0x100004DA, KIND_ENUM, int(category)),
        (0x100007FB, KIND_INT, variants.get(class_id, 0)),
    ]


def note_mode(match):
    """[tutorial] map_notes: "self" = the visible ping / marker carries its own
    minimap note (2026-10-14 18:24: the invisible companions reached the HUD but
    never got a position), "companion" = an invisible object next to it does,
    "off" = none."""
    v = match.cfg["tutorial"].get("map_notes", "self")
    if v is True:
        return "companion"
    if v is False:
        return "off"
    return str(v).lower()


def note_extras(match, class_id, category=None):
    """Icon, category and variant of the minimap note (no show flag, no team)."""
    return [p for p in map_note_properties(match, class_id, category) if p[0] not in (0x100007D8, 0x1000009C)]


# 22:57: with category 1 and variants 0/1 both ping types showed the same icon
# on the minimap. Guess: the HUD's variant is the client's ping type (1 = alert,
# 2 = retreat). [tutorial] player_note_variants = { "0x4000025B" = 1, ... }
PLAYER_NOTE_VARIANTS = {0x4000025B: 0, 0x4000025A: 0}   # 23:22: the category picks the icon
# 23:07: still one icon for both with category 1. Category 0x1D is the client's
# ping category (the note reader shifts it to the enemy's icons for team 2, and
# the guide marker's retreat icon draws with it): back to 0x1D + variant 0/1,
# with the patched exe keeping the alert pings (team 2) on their own icon.


def player_note_variant(match, class_id):
    table = dict(PLAYER_NOTE_VARIANTS)
    raw = match.cfg["tutorial"].get("player_note_variants")
    if isinstance(raw, dict):
        for k, v in raw.items():
            table[int(str(k), 0)] = int(v)
    return table.get(class_id, 1)


def player_note_props(match, class_id, extras_only=False):
    props = map_note_properties(match, class_id, player_note_category(match, class_id))
    props = [(k, kind, player_note_variant(match, class_id) if k == 0x100007FB else v) for k, kind, v in props]
    if extras_only:
        props = [p for p in props if p[0] not in (0x100007D8, 0x1000009C)]
    return props


# 23:22: the HUD's Flash (MapNoteCategoryList, classes_all.txt) picks the ping
# icon/animation by CATEGORY: 1 = PING, 18 = ALERT_PING_INGAME,
# 21 = RETREAT_PING_INGAME (17 / 22 = ALERT_PING / RETREAT_PING; 0x1D = 29 is
# BEACON). [tutorial] player_note_categories = { "0x4000025B" = 18, ... }
# 23:42: on screen the two came out swapped (like the ping classes themselves)
PLAYER_NOTE_CATEGORIES = {0x4000025B: 21, 0x4000025A: 18}


def player_note_category(match, class_id=None):
    tc = match.cfg["tutorial"]
    if "player_note_category" in tc:            # one category for both (old setting)
        return int(tc["player_note_category"])
    table = dict(PLAYER_NOTE_CATEGORIES)
    raw = tc.get("player_note_categories")
    if isinstance(raw, dict):
        for k, v in raw.items():
            table[int(str(k), 0)] = int(v)
    return table.get(class_id, 1)


def ping_team_for(match, class_id):
    raw = match.cfg["tutorial"].get("ping_class_teams")
    table = dict(PING_CLASS_TEAMS)
    if isinstance(raw, dict):
        for k, v in raw.items():
            try:
                table[int(str(k), 0)] = int(v)
            except ValueError:
                pass
    if class_id in table:
        return table[class_id]
    return ping_team(match)


def objective_one(text):
    return M.objective(1, text=text, active=True, category=1, sort_order=0, optional=False, banner=text)


class Tutorial:
    def __init__(self, match, targets=None, drone_step=DRONE_STEP):
        self.started_at = time.time()    # match length on the end page
        self.aggressive = set()          # eids of drones fighting Batman
        self.next_hit = {}
        self.walk_logged = {}
        self.attack_count = {}           # eid -> hits so far (attack script rotation)
        self.match = match
        self.targets = {i + 1: tuple(t) for i, t in enumerate(targets)} if targets else dict(TARGETS)
        self.drone_step = drone_step     # the drone appears when the guide points at this step
        self.step = 0
        self.objective_text = FIRST_OBJECTIVE
        self.first_attack_done = False
        self.phase = "walk"          # walk -> first_drone -> wave -> skills
        self.thug_eid = None
        # set by the session: schedule(delay, fn) sends fn()'s messages later
        self.schedule = lambda delay, fn: None
        self.run_scripts = lambda entity_id, keys, what, variables=None, second=0: None
        self.log = lambda text: None      # server.log (set by the session)
        self.on_skill_prompt = None       # set by the session (auto-rank fallback timer)
        self.damage = lambda ent, amount: None   # set by the session
        self.batarang_casts = 0
        self.locked_until = 0.0           # Batman cannot move before this (time.time())
        self.lock_reason = ""
        self.meteor_count = 0
        self.visible_markers = set()      # steps with a visible marker on the ground
        self.marker_ids = {}              # step -> object id of its visible marker now
        self.flying_until = 0.0           # Bat Flight: move orders wait until he lands
        self.low_health_said = False
        self.bridge = Bridge(self)        # part 2: after the Catwoman cinematic
        from .finale import Finale
        self.finale = Finale(self)        # part 3: Super Strength, the Destroyer, the victory

    def ping(self, step, now):
        xyz = self.targets.get(step)
        if not xyz:
            return None
        spawn = self.match.mover.spawn
        # the ping is a placed prop like the doors: cell 251 of the layout ([combat] ping_cell;
        # 2026-10-14 12:20: the markers were never seen with cell 0)
        cc = self.match.cfg.get("combat", {}) if hasattr(self.match.cfg, "get") else {}
        cell = int(cc.get("ping_cell", cc.get("scenery_cell", 251)))
        pos = (spawn[0], 0x13, 0xCB, cell) + tuple(xyz)
        # The ping entity is an "InvisibleTarget" (world state 0x2E000002): the
        # marker on the ground and the arrows at Batman's feet are Batman's own
        # scripts Vfx_GuideArrow (0x10000F80) and Vfx_GuideArrow_Ping (0x10000F86),
        # both in his script table, aimed at the ping (2026-10-14 12:27).
        ping_id = M.PING_OBJECT_ID + step
        keys = tuple(int(k) for k in (self.match.cfg["tutorial"].get("guide_keys") or GUIDE_KEYS))
        if keys:
            # 2026-10-14: the scripts were accepted but nothing showed. The game's
            # guide script (0x1E00055B: AlertPingScriptlet / AlertArrowScriptlet)
            # plays them aimed at the ping, so try three ways one after the other
            # and ask which moment shows the marker ([tutorial] guide_variants):
            #   A: both on Batman, target as script variable 0x108 (as before)
            #   B: as A plus the ping as the order's second object (field 0x20)
            #   C: the ground marker (GuideArrow_Ping) on the ping itself, the
            #      arrows (GuideArrow) on Batman aimed at the ping
            tc = self.match.cfg["tutorial"]
            variants = [str(v).upper() for v in tc.get("guide_variants", ["A", "B", "C"])]
            gap = float(tc.get("guide_variant_gap", 4.0))
            target = [(M.PROP_SCRIPT_TARGET, KIND_IID, ping_id)]
            arrow = [k for k in keys if k != GUIDE_KEYS[1]] or list(keys)
            marker = [k for k in keys if k == GUIDE_KEYS[1]] or list(keys)

            def run(v, step=step):
                if self.step != step:
                    return []                                 # that marker is already behind
                self.log(f"tutorial: marker {step}, guide variant {v}")
                if v == "A":
                    self.run_scripts(M.CHAMPION_AGENT_ID, keys, f"guide {v} -> ping {step}", target)
                elif v == "B":
                    self.run_scripts(M.CHAMPION_AGENT_ID, keys, f"guide {v} -> ping {step}", target, ping_id)
                elif v == "C":
                    self.run_scripts(ping_id, marker, f"guide {v}: marker on ping {step}", target)
                    self.run_scripts(M.CHAMPION_AGENT_ID, arrow, f"guide {v}: arrows -> ping {step}", target, ping_id)
                return []
            for i, v in enumerate(variants):
                self.schedule(0.3 + gap * i, lambda v=v: run(v))
        # The guide ping itself is invisible. The players' own pings (Alt / Ctrl +
        # click) DO show (2026-10-14 14:14), so a player ping goes on the same spot
        # as the visible marker until the guide's ground circle works
        # ([tutorial] marker_ping_class, 0 = off).
        vis = int(self.match.cfg["tutorial"].get("marker_ping_class", PLAYER_PING_CLASSES[2]) or 0)
        if vis:
            self.visible_markers.add(step)
            mpos = (spawn[0], spawn[1], spawn[2], 0) + tuple(xyz)
            cat = int(self.match.cfg["tutorial"].get("marker_category", 0x1D))
            mode = note_mode(self.match)
            # 2026-10-14 19:56: swapping the marker after 5 s lost the ground marker
            # and the minimap kept its icon. Now the ground marker never carries
            # the note; an invisible object on the same spot carries it and is
            # removed after [tutorial] marker_note_seconds (the note manager now
            # runs, so it should get its position).
            # 20:04: without "show on the map" the ground marker is not drawn at
            # all (the ping's ground ring is part of the map-note system), so the
            # marker carries its note again; the minimap icon is meant to fade by
            # itself with the ping category 0x1D (see [tutorial] map_note_category)
            props = ping_properties(ping_team_for(self.match, vis), ping_style(self.match), show=True)
            props += [(k, kind, cat if k == 0x100004DA else v) for k, kind, v in note_extras(self.match, vis)]
            props += marker_vfx_property(self.match.cfg)
            msg = M.create_object(M.MARKER_OBJECT_ID + step, vis, now, position=mpos,
                                  module=self.match.module, second_seq=self.match.second_seq,
                                  properties=props)
            self.marker_ids[step] = M.MARKER_OBJECT_ID + step
            note_id = M.MARKER_OBJECT_ID + 0x8 + step
            note = None
            if mode == "companion":
                note = M.create_object(note_id, PING_CLASS, now, position=mpos, module=self.match.module,
                                       second_seq=self.match.second_seq,
                                       properties=map_note_properties(self.match, vis))
            note_s = float(self.match.cfg["tutorial"].get("marker_note_seconds", 5.0) or 0)

            def show(step=step, msg=msg, note=note):
                if self.step != step:
                    return []
                self.log(f"tutorial: visible marker {step} at ({xyz[0]:.1f}, {xyz[1]:.1f})")
                out = [(f"visible marker {step} (player ping class {vis:#x})", msg)]
                if note:
                    out.append((f"minimap note of marker {step}", note))
                return out
            self.schedule(0.1, show)

            def unnote(step=step):
                self.log(f"tutorial: marker {step} leaves the minimap")
                return [(f"minimap note of marker {step} removed (0x3)", M.remove_object(note_id))]
            if note and note_s > 0:
                self.schedule(0.1 + note_s, unnote)
        if note_mode(self.match) == "companion":
            props = map_note_properties(self.match, vis or PLAYER_PING_CLASSES[2])
        else:
            props = ping_properties(ping_team(self.match), ping_style(self.match), show=not vis)
        return M.create_object(ping_id, PING_CLASS, now, position=pos,
                               module=self.match.module, second_seq=self.match.second_seq,
                               properties=props + marker_vfx_property(self.match.cfg))

    def remove_ping(self, step, keep_visible=False):
        """Remove a guide ping and the visible marker that goes with it (the
        visible one stays until Batman steps on it when keep_visible)."""
        out = [(f"guide ping {step} removed (0x3)", M.remove_object(M.PING_OBJECT_ID + step))]
        if step in self.visible_markers and not keep_visible:
            self.visible_markers.discard(step)
            mid = self.marker_ids.pop(step, M.MARKER_OBJECT_ID + step)
            out.append((f"visible marker {step} removed (0x3)", M.remove_object(mid)))
            out.append((f"minimap note of marker {step} removed (0x3)",
                        M.remove_object(M.MARKER_OBJECT_ID + 0x8 + step)))
        return out

    def _objective(self, text):
        self.objective_text = text
        return [("objective 1 new text (0x2009)", M.objective_update(objective_one(text)))]

    def _beat_msgs(self, kind, value, now):
        if kind == "conv":
            return self.say(value, now)
        if kind == "hint":
            return [(f"tutorial hint {value}", M.tutorial_hint(value))]
        if kind == "objective":
            return self._objective(value)
        if kind == "ping":
            ping = self.ping(self.step, now)
            return [(f"guide ping {self.step}", ping)] if ping else []
        if kind == "call":
            return value() or []
        raise ValueError(kind)

    def say(self, key, now=None):
        """Start a conversation and move the end of the client's speech queue."""
        now = now or time.time()
        pacing = float(self.match.cfg["tutorial"].get("pacing", 1.0))
        self.speech_end = max(getattr(self, "speech_end", 0.0), now) + CONV_SECONDS.get(key, 4.0) * pacing
        return [(f"conversation {key:#x} (0x2001)", M.start_conversation(key))]

    def after_speech(self, margin, fn):
        """Call fn once every queued line has been spoken (+ margin s)."""
        def check():
            wait = getattr(self, "speech_end", 0.0) + margin - time.time()
            if wait > 0.05:
                self.schedule(wait, check)
                return []
            return fn()
        return check()

    def beats(self, beats, now=None):
        """Play (delay, kind, value) beats: delay 0 ones are returned now, the
        rest are scheduled ([tutorial] pacing scales the delays)."""
        scale = float(self.match.cfg["tutorial"].get("pacing", 1.0))
        now_msgs = []
        for delay, kind, value in beats:
            delay *= scale
            if delay <= 0:
                now_msgs += self._beat_msgs(kind, value, now or time.time())
            else:
                self.schedule(delay, lambda kind=kind, value=value: self._beat_msgs(kind, value, time.time()))
        return now_msgs

    def start(self, now):
        """Cinematic finished: HUD, vitals, objective, first conversation, ping.
        Returns the messages, or [] if the tutorial already started."""
        if self.step:
            return []
        self.step = 1
        m = self.match
        msgs = [(f"HUD element {e} restored (0x213d)", M.hud_element(e, HUD_EVENT_FIRST_RESTORED))
                for e in START_ELEMENTS]
        msgs.append(("champion vitals (0x42)", M.vitals(M.CHAMPION_AGENT_ID, m.vitals)))
        msgs.append(("objective list (0x2034)", M.objective_list(
            [objective_one(self.objective_text)],
            [M.objective_category(1, CATEGORY_TITLE, state=OBJECTIVE_CATEGORY_SHOW)])))
        start_at = str(m.cfg["tutorial"].get("start_at", "") or "")
        if start_at:
            # [tutorial] start_at: skip part 1 and start at a later point (testing)
            if m.cfg["tutorial"].get("drones_fight_back", True):
                self.schedule(0.5, self._drone_ai)
            self.schedule(0.5, self._bridge_tick)
            self.schedule(1.0, lambda: self.bridge.jump(start_at, time.time()))
            self._action_tour()
            return msgs
        for k in INTRO_CONVERSATIONS:
            msgs += self.say(k, now)
        ping = self.ping(1, now)
        if ping:
            msgs.append(("guide ping 1", ping))
        if m.cfg["tutorial"].get("drones_fight_back", True):
            self.schedule(0.5, self._drone_ai)
        self.schedule(0.5, self._bridge_tick)
        if self.match.cfg["tutorial"].get("meteors", True):
            # "before you can move, 3 small meteors fall near him"
            tc = m.cfg["tutorial"]
            for i, xyz in enumerate(tc.get("small_meteors") or SMALL_METEORS):
                self.schedule(1.0 + 0.7 * i, lambda xyz=tuple(xyz): self.meteor(xyz, time.time(), lifetime=0,
                                                                                  group="small"))
            self.lock(now, float(m.cfg["tutorial"].get("start_lock", 3.5)), "the first meteors are falling")
        self._action_tour()
        return msgs

    def _action_tour(self):
        """[debug] tour_keys: play Batman's scriptlets one by one to see what each does."""
        import os
        dc = self.match.cfg["debug"]
        raw = dc.get("tour_keys") or []
        if not raw:
            return
        names = {}
        path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "data", "batman_actions.tsv")
        try:
            for line in open(path, encoding="utf-8"):
                k, _, n = line.rstrip("\n").partition("\t")
                names[int(k, 16)] = n
        except OSError:
            pass
        if raw == "all":
            keys = list(names)
        elif raw in ("core", "nucleo"):
            keys = [k for k, _ in TOUR_CORE]
            names.update(dict(TOUR_CORE))
        else:
            keys = [int(str(k), 0) for k in raw]
        gap = float(dc.get("tour_interval", 3.0))
        start = float(dc.get("tour_start", 6.0))
        for i, key in enumerate(keys):
            def play(key=key, i=i):
                self.log(f"tour {i + 1}/{len(keys)}: {key:#x} {names.get(key, '')}")
                self.run_scripts(M.CHAMPION_AGENT_ID, [key], f"tour {key:#x}")
                return []
            self.schedule(start + gap * i, play)

    def meteor(self, xyz, now, knockdown=False, lifetime=None, group=None):
        """A falling PowerCore at xyz, removed after METEOR_LIFETIME (lifetime
        0 = stays; group = removed together by remove_meteors(group))."""
        m = self.match
        tc = m.cfg["tutorial"]
        msgs = []
        if knockdown and tc.get("big_meteor_crater", True):
            # the big one: no rock falling, a blast and the crater appears
            msgs += self.crater(xyz, now)
            if not tc.get("big_meteor_rock", False):
                self.knockdown()
                return msgs
        if not tc.get("meteor_objects", False):
            # 2026-10-14 16:22: the meteor model shows as big grey "fur" columns
            # (wrong asset / not animated): no objects until the real one is found
            if knockdown:
                self.knockdown()
            return msgs
        # 2026-10-14 21:03: property 0x10000426 did not change the size. The
        # render component (VA 0x622F10) multiplies its scale by property
        # 0x6B4 (float; world state 0x2E001037 carries 0x6B4 = 2.1, and the
        # exe's SetScale at 0x58D650 writes 0x6B4) and by 0x450.
        scale = float(tc.get("big_meteor_scale", 1.0) if knockdown else tc.get("meteor_scale", 0.3))
        wstate = int(tc.get("meteor_wstate", METEOR_CLASS))
        slot = (self.meteor_count + 1) % 6 if m.cfg["combat"].get("prop_try_all_carriers", True) else None
        eid, msg = self._prop_object(wstate, xyz, now, slot, scale, "meteor")
        if group:
            self.meteor_groups = getattr(self, "meteor_groups", {})
            self.meteor_groups.setdefault(group, []).append(eid)
        msgs.append(msg)
        self.schedule(0.3, lambda: (self.run_scripts(eid, METEOR_PROBE_KEYS, "meteor start"), [])[1])
        life = METEOR_LIFETIME if lifetime is None else lifetime
        if life:
            self.schedule(life, lambda: [(f"meteor {eid:#x} removed", M.remove_object(eid))])
        if knockdown:
            self.knockdown()
        return msgs

    def raise_events(self, events, what):
        """Graph events on Batman through _HFSM_BehaviorRaiseEventAction
        (0x100001E3, event id in script variable 0x780)."""
        for ev in events:
            self.run_scripts(M.CHAMPION_AGENT_ID, (RAISE_EVENT_KEY,), f"{what}: graph event {ev:#x}",
                             [(RAISE_EVENT_VAR, M.KIND_ENUM, ev)])
        return []

    def knockdown(self):
        """The big meteor knocks Batman down.

        2026-10-16 (his behavior graph 0x1A0002E7 and its Lua): _Defeat_OnIncapacitated
        enters SM_Death, whose state is Death_Selection, set 50/50 by
        onStandardDeath() on every return to walking: face up (Death_A) or face
        down (Death_B), while the get-up (SM_Get_Up) is always the face-down one.
        So by default ([tutorial] knockdown_mode = "face_down") the graph events
        are raised directly: CbtState_Knockdown (the knockdown clip, end pose
        held), CbtState_Dead a little later (frozen face-down pose, the get-up's
        first frame), then CbtState_GetUp (face-down get-up; it returns to
        walking by itself). "incapacitated" = the old scriptlets."""
        tc = self.match.cfg["tutorial"]
        hold = float(tc.get("knockdown_hold", 5.0)) * float(tc.get("pacing", 1.0))
        if str(tc.get("knockdown_mode", "face_down")) == "face_down":
            self.raise_events([int(e) for e in tc.get("knockdown_events") or KNOCKDOWN_EVENTS],
                              "Batman knocked down (face down)")
            snap = float(tc.get("knockdown_snap_delay", 1.8))
            snap_events = [int(e) for e in tc.get("knockdown_snap_events", list(KNOCKDOWN_SNAP_EVENTS)) or []]
            if snap > 0 and snap_events:
                self.schedule(snap, lambda: self.raise_events(snap_events, "Batman lies face down"))
            if hold > 0:
                getup = [int(e) for e in tc.get("getup_events") or GETUP_EVENTS]
                keys = [int(k) for k in tc.get("getup_fx_keys", list(GETUP_FX_KEYS)) or []]

                def up():
                    if keys:
                        self.run_scripts(M.CHAMPION_AGENT_ID, keys, "get-up effect")
                    return self.raise_events(getup, "Batman gets up (face down)")
                self.schedule(hold, up)
            return
        self.run_scripts(M.CHAMPION_AGENT_ID, [int(k) for k in tc.get("knockdown_keys") or KNOCKDOWN_KEYS],
                         "Batman knocked down")
        keys = [int(k) for k in tc.get("getup_keys") or GETUP_KEYS]
        if hold > 0 and keys:
            self.schedule(hold, lambda: (self.run_scripts(M.CHAMPION_AGENT_ID, keys, "Batman gets up"), [])[1])

    def _prop_object(self, wstate, xyz, now, slot, scale, what, eid=None):
        """A placed prop (world state through a carrier class, cell 251 of the
        layout) with optional scale. Returns (object id, message)."""
        m = self.match
        tc = m.cfg["tutorial"]
        if eid is None:                   # (an eid = the same object again, moved)
            self.meteor_count += 1
            # 2026-10-15: PING_OBJECT_ID + 0x100 + n ran into the server's entity
            # ids (0x...100 up): its own range now
            eid = PROP_OBJECT_BASE_ID + self.meteor_count
        spawn = m.mover.spawn
        pos = (spawn[0], 0x13, 0xCB, m.cfg["combat"].get("scenery_cell", 251)) + tuple(xyz)
        cls = prop_class(wstate, m.cfg, slot)
        props = []
        prop_ids = tc.get("meteor_scale_property", 0x6B4)
        if not isinstance(prop_ids, (list, tuple)):
            prop_ids = [prop_ids]
        if abs(scale - 1.0) > 1e-6:
            props = [(int(p), KIND_F32, float(scale)) for p in prop_ids if int(p)]
        if what == "crater":
            raw = tc.get("crater_props")
            for pid, kind, value in (() if raw is None else CRATER_PROPS if raw == "template" else raw):
                kind = _PROP_KINDS[str(kind)]
                props.append((int(pid), kind, float(value) if kind == KIND_F32 else int(value)))
        carrier = m.cfg["combat"].get("prop_carrier") or 0
        if cls >> 24 == 0x2E and carrier:
            cls, props = carrier, props + [(WSTATE_PROPERTY, KIND_DID, wstate)]
        if cls != wstate and wstate >> 24 == 0x2E:
            # its world state's scriptlet templates (meteors, dust, the sphere)
            props = props + script_table_props(wstate, m.cfg)
        module = M.scenery_module(m.cfg) if cls >> 24 == 0x2E else m.module
        heading = float(tc.get("crater_yaw", 0.0)) if what == "crater" else 0.0
        label = f"{what} {self.meteor_count} ({cls:#x}) at ({xyz[0]:.0f}, {xyz[1]:.0f}, {xyz[2]:.0f}) scale {scale:g}"
        return eid, (label, M.create_object(eid, cls, now, position=pos, module=module, heading=heading,
                                            second_seq=m.second_seq, properties=props))

    def crater(self, xyz, now):
        """The big meteor's crater (+ its start scripts as the blast).
        [tutorial] crater_mode: "wstate" = world state 0x2E0004BE placed like
        the meteor rocks (which render); "entity" = entity 0x400004FD."""
        m = self.match
        tc = m.cfg["tutorial"]
        if tc.get("crater_mode", "wstate") == "entity":
            return m.spawn("Crater", now, attackable=False, xyz=tuple(xyz))
        if tc.get("crater_set", "old") == "lava":
            # 23:53: the lava crater the map already has by the bank is three world
            # states placed on one spot (landblock 0x13cb, (38.31, 66.99)):
            # 0x2E001144 / 45 / 46 (.entity 0x2D000E6B / 6C / 6D, pack 0xA000024C;
            # 46 carries a warm light). [tutorial] crater_set = "old" = 0x2E0004BE.
            lx, ly = tc.get("lava_crater_at") or LAVA_CRATER_AT
            pos = (float(lx), float(ly), xyz[2])
            msgs = []
            for ws in tc.get("lava_crater_wstates") or LAVA_CRATER_WSTATES:
                eid, msg = self._prop_object(int(ws), pos, now, int(tc.get("lava_carrier_slot", 0)),
                                             1.0, "crater")
                msgs.append(msg)
            self.crater_id = eid
            self.log(f"tutorial: lava crater at ({pos[0]:.1f}, {pos[1]:.1f})")
            return msgs
        wstate = int(tc.get("crater_wstate", CRATER_WSTATE))
        slot = int(tc.get("crater_carrier_slot", 1))
        eid, msg = self._prop_object(wstate, xyz, now, slot, float(tc.get("crater_scale", 1.0)), "crater")
        self.crater_id = eid
        self.log(f"tutorial: crater {eid:#x} (world state {wstate:#x}) at ({xyz[0]:.1f}, {xyz[1]:.1f})")
        # 22:28: still no lava. The other tutorial's placement list 0x1D0008CC puts
        # world state 0x2E000A9F next to its craters; its .entity 0x2D0008B6 is a
        # flat 6 x 6 m piece (0.18 m high): probably the lava pool.
        # [tutorial] crater_extras = [[world state, dx, dy], ...]
        extra_msgs = []
        # 00:04: the bank's set (0x2E001144-46) was not it either (pale glowing
        # pit). 0x2E0005D6 uses the crater's own entity 0x400004FD, three meshes
        # and colour 0x2A0 = 0xFF0000FF (red): the lava, laid over the crater.
        for extra in tc.get("crater_extras", []) or []:
            ws, dx, dy = int(extra[0]), float(extra[1]), float(extra[2])
            pos = (xyz[0] + dx, xyz[1] + dy, xyz[2])
            extra_msgs.append(self._prop_object(ws, pos, now, slot, 1.0, "crater extra")[1])
            self.log(f"tutorial: crater extra {ws:#x} at ({pos[0]:.1f}, {pos[1]:.1f})")
        if tc.get("crater_blast", True):
            keys = [int(k) for k in tc.get("crater_keys") or CRATER_KEYS]
            self.schedule(0.2, lambda: (self.run_scripts(eid, keys, "crater blast"), [])[1])
        return [msg] + extra_msgs

    def remove_meteors(self, group):
        eids = getattr(self, "meteor_groups", {}).pop(group, [])
        return [(f"meteor {eid:#x} removed ({group})", M.remove_object(eid)) for eid in eids]

    def scenery(self, now):
        """Static map pieces of the first area (vehicle, drone gates)."""
        out = []
        cc = self.match.cfg["combat"]
        if cc.get("vehicle_blocks", True):
            # the street vehicle blocks the way until Catwoman breaks it (even while
            # the client does not show it): [combat] vehicle_box = [half length, half width]
            (vx, vy, _), yaw = LAYOUT["DestVehicle"][1], LAYOUT["DestVehicle"][2]
            hl, hw = cc.get("vehicle_box", [4.0, 1.6])
            self.match.mover.obstacles["DestVehicle"] = (vx, vy, float(hl), float(hw), yaw)
            self.log("tutorial: the street vehicle blocks the way")
        for ob in cc.get("obstacles", []):
            name, rest = str(ob[0]), ob[1:]
            if len(rest) == 1:                                # polygon
                pts = [(float(x), float(y)) for x, y in rest[0]]
                self.match.mover.obstacles[name] = pts
                self.log(f"tutorial: obstacle {name} ({len(pts)} corners)")
            else:                                             # box
                self.match.mover.obstacles[name] = tuple(float(v) for v in rest)
                self.log(f"tutorial: obstacle {name} at ({float(rest[0]):.1f}, {float(rest[1]):.1f})")
        for name in SCENERY:
            out += self.match.spawn(name, now, attackable=False)
        out += self.bridge.gate_obstacles(now)   # the blue gates on the bridge block the way
        if self.match.cfg["combat"].get("prop_try_all_carriers", True):
            # test: the same vehicle with each of the 6 carriers (diag --entities
            # shows which one builds without "step 3 (components)")
            base = int(self.match.cfg["combat"].get("prop_carrier_slot", 0)) % 6
            for slot in range(6):
                if slot == base:
                    continue
                out += self.match.spawn("DestVehicle", now, attackable=False, carrier_slot=slot)
                ent = self.match.entities[max(self.match.entities)]
                ent.name = f"DestVehicle~{slot}"
        self.vehicle_state = 0
        return out

    # ---- the street vehicle breaks in steps (Destructible_AdvanceState) ------------
    def _vehicle(self):
        return next((e for e in self.match.entities.values() if e.name == "DestVehicle"), None)

    def advance_vehicle(self, reason):
        """One step more broken (state 1 = damaged, 2 = wreck)."""
        v = self._vehicle()
        last = int(self.match.cfg["tutorial"].get("vehicle_states", 2))
        if not v or getattr(self, "vehicle_state", 0) >= last:
            return []
        self.vehicle_state = getattr(self, "vehicle_state", 0) + 1
        keys = [int(k) for k in self.match.cfg["tutorial"].get("vehicle_break_keys", VEHICLE_BREAK_KEYS)]
        self.log(f"tutorial: vehicle state {self.vehicle_state} ({reason})")
        self.run_scripts(v.eid, keys, f"vehicle breaks a step ({reason})")
        return []

    def break_vehicle(self, now, reason):
        """All the way to the wreck."""
        last = int(self.match.cfg["tutorial"].get("vehicle_states", 2))
        for i in range(max(0, last - getattr(self, "vehicle_state", 0))):
            self.schedule(0.4 * i, lambda: self.advance_vehicle(reason))
        return []

    def _vehicle_destroyed(self):
        """Catwoman's blow: the vehicle goes (its explosion is not reproduced yet:
        it accepts no scriptlets, diag 2026-10-14 15:52) and the way opens."""
        m = self.match
        m.mover.obstacles.pop("DestVehicle", None)
        out = []
        for ent in list(m.entities.values()):
            if ent.name.startswith("DestVehicle"):
                out.append(("vehicle destroyed by Catwoman (0x3)", M.remove_object(ent.eid)))
                del m.entities[ent.eid]
        if out:
            self.log("tutorial: Catwoman destroys the vehicle")
        return out

    def batarang_at_vehicle(self, xyz, now):
        """Q thrown at the vehicle (no drone on the way): Batman throws it and
        the vehicle breaks one step when it arrives."""
        v = self._vehicle()
        if not v or math.hypot(xyz[0] - v.pos[0], xyz[1] - v.pos[1]) > VEHICLE_HIT_RADIUS:
            return []
        if now < getattr(self, "batarang_ready", 0):
            return []
        self.batarang_ready = now + BATARANG_COOLDOWN
        m = self.match
        bx, by, _ = m.mover.pos
        m.mover.heading = math.atan2(v.pos[1] - by, v.pos[0] - bx)
        m.sequence += 1
        keys = tuple(m.cfg["tutorial"].get("batarang_keys") or BATARANG_CAST_KEYS)
        self.run_scripts(M.CHAMPION_AGENT_ID, keys, "Sonic Batarang at the vehicle",
                         [(M.PROP_SCRIPT_TARGET, KIND_IID, v.eid)])
        self.schedule(BATARANG_FLIGHT, lambda: self.advance_vehicle("Sonic Batarang"))
        self.schedule(BATARANG_FLIGHT + BATARANG_HOP, lambda: (
            self.run_scripts(M.CHAMPION_AGENT_ID, BATARANG_STOP_KEYS, "Sonic Batarang over"), [])[1])
        self.log("Sonic Batarang: at the vehicle")
        return [("Batman faces the vehicle", m.champion_bundle(now))]

    def lock(self, now, seconds, reason):
        """Batman cannot move for `seconds` (x pacing)."""
        seconds *= float(self.match.cfg["tutorial"].get("pacing", 1.0))
        if seconds > 0:
            self.locked_until = max(self.locked_until, now + seconds)
            self.lock_reason = reason
            self.lock_logged = False
            mv = self.match.mover
            if mv.target is not None:                         # stop where he is
                mv.target, mv.speed = None, 0.0
            self.log(f"tutorial: Batman cannot move for {seconds:.1f} s ({reason})")

    def at_target(self, passing=False):
        """Batman stands on the current marker (2026-10-14 14:26: 3.5 m was far
        too wide; he has to step onto it: [tutorial] marker_radius where he
        stops, marker_pass_radius while walking through)."""
        xyz = self.targets.get(self.step)
        tc = self.match.cfg["tutorial"]
        radius = float(tc.get("marker_pass_radius", 0.6) if passing else tc.get("marker_radius", TARGET_RADIUS))
        if not xyz:
            # 2026-10-14 15:17: the drone's marker has no spot until the drone
            # appears; "no target = arrived" skipped it (and its lines) at once
            return self.step != self.drone_step
        return self.match.mover.distance_to(xyz) <= radius

    def arrived(self, now, passing=False):
        beats = MOVE_STEPS.get(self.step)
        if not beats or not self.at_target(passing):
            return []
        if self.step == self.drone_step and self.phase != "first_drone":
            # the drone was beaten before he stepped on its marker: just clear it
            self.step += 1
            return self.remove_ping(self.step - 1)
        self.step += 1
        msgs = self.remove_ping(self.step - 1)
        drone_now = self.step == self.drone_step and self.phase == "walk"
        if drone_now:
            beats = tuple(b for b in beats if b[1] != "ping")
        if self.step == 2 and self.match.cfg["tutorial"].get("meteors", True):
            # "after 4 steps a big meteor falls behind him and he falls down"
            # 2026-10-14 16:42: on the marker the falling meteor is heard; 1 s later
            # it hits behind him and he falls; up after 5 s; 1.5 s more before he
            # can move, the next marker showing 1 s into it (drone_appear_delay)
            tc = self.match.cfg["tutorial"]
            big = tuple(tc.get("big_meteor") or BIG_METEOR)
            self.schedule(float(tc.get("knockdown_delay", 1.0)) * float(tc.get("pacing", 1.0)),
                          lambda: self.meteor(big, time.time(), knockdown=True, lifetime=0))   # the crack stays
            self.lock(now, float(tc.get("knockdown_lock", 7.5)), "knocked down by the meteor")
        msgs += self.beats(beats, now)
        if drone_now:
            # he gets up first; then the drone and the human are seen fighting
            delay = float(self.match.cfg["tutorial"].get("drone_appear_delay", 6.5))
            delay *= float(self.match.cfg["tutorial"].get("pacing", 1.0))
            if delay > 0:
                self.schedule(delay, lambda: self._drone_appears(time.time()))
            else:
                msgs += self._drone_appears(now)
        return msgs

    def _drone_appears(self, now):
        """The drone from cinematic 0x35000033 appears ahead and the guide
        arrows point at it."""
        if self.phase != "walk":          # already out (scheduled + walked up to it)
            return []
        self.log("tutorial: the drone and the human appear fighting")
        self.phase = "first_drone"
        gone = self.remove_meteors("small")       # "the 3 first meteors disappear" with the next marker
        # the second marker goes on the ground next to the fight, not under the
        # drone (2026-10-14 14:26); [tutorial] drone_marker, [] = at the drone
        dm = self.match.cfg["tutorial"].get("drone_marker") or LAYOUT[FIRST_DRONE][1]
        self.targets[self.drone_step] = tuple(float(v) for v in dm)
        msgs = list(gone)
        ping = self.ping(self.drone_step, now)
        if ping:
            msgs.append(("guide ping at the drone", ping))
        msgs += self.match.spawn(FIRST_DRONE, now)
        thug = self.match.spawn(THUG, now, attackable=False)
        if thug:
            self.thug_eid = max(self.match.entities)
            drone = next(e for e in self.match.entities.values() if e.name == FIRST_DRONE)
            t = self.match.entities[self.thug_eid]
            t.heading = math.atan2(drone.pos[1] - t.pos[1], drone.pos[0] - t.pos[0])
            t.yaw_offset = float(self.match.cfg["tutorial"].get("thug_yaw_offset", THUG_YAW_OFFSET))
            # 23:42: "a little to one side so he is in front of the drone": keep
            # the facing, shift him [tutorial] thug_shift m (screen right = world
            # (+0.78, -0.63))
            dx, dy = self.match.cfg["tutorial"].get("thug_shift", THUG_SHIFT)
            t.pos = [t.pos[0] + float(dx), t.pos[1] + float(dy), t.pos[2]]
            drone.heading = math.atan2(t.pos[1] - drone.pos[1], t.pos[0] - drone.pos[0])
            msgs += thug + [("thug faces the drone", self.match.entity_bundle(t, now)),
                            ("drone faces the thug", self.match.entity_bundle(drone, now))]
            self.schedule(1.0, self._fight)
        return msgs

    def _spawn_effect(self, names):
        """The drones 'teleport in': Vfx_Spawn, then Vfx_Fade_In, spread over
        ~1.5 s ([tutorial] spawn_sequence; the old spawn_keys still works)."""
        tc = self.match.cfg["tutorial"]
        seq = tc.get("spawn_sequence")
        if seq is None and tc.get("spawn_keys") is not None:
            seq = [(0.1 + 0.8 * i, k) for i, k in enumerate(tc["spawn_keys"])]
        seq = SPAWN_SEQUENCE if seq is None else seq
        for e in list(self.match.entities.values()):
            if e.name in names and e.alive:
                for delay, key in seq:
                    self.schedule(float(delay), lambda eid=e.eid, name=e.name, key=int(key): (
                        self.run_scripts(eid, (key,), f"{name} teleports in ({key:#x})"), [])[1])

    def _attack_key(self, eid, ent=None):
        """Next attack script for this drone (they are tried in turn)."""
        keys = self.match.cfg["tutorial"].get("drone_attack_keys") or DRONE_ATTACK_KEYS
        if getattr(ent, "role", None) == "ranged":
            keys = self.match.cfg["tutorial"].get("ranged_attack_keys") or keys
        n = self.attack_count.get(eid, 0)
        self.attack_count[eid] = n + 1
        entry = keys[n % len(keys)]
        combo = tuple(int(k) for k in entry) if isinstance(entry, (list, tuple)) else (int(entry),)
        e = self.match.entities.get(eid)
        self.log(f"{e.name if e else hex(eid)}: attack scripts {'+'.join(f'{k:#x}' for k in combo)} (hit {n + 1})")
        return combo

    def immune_to_basic(self, ent):
        """The yellow target drones only take the skill they are there for."""
        if getattr(ent, "only_slot", None):
            return True
        return ent.name in PRACTICE and self.match.cfg["tutorial"].get("practice_immune", True)

    def wrong_attack(self, ent, slot):
        """Superman's line when a target drone is hit by the wrong attack."""
        return self.bridge.wrong_attack(ent, slot) if getattr(ent, "only_slot", None) else []

    def skill_hit(self, ent, damage, slot):
        """Damage from a skill (slot), unless the target only takes another one."""
        only = getattr(ent, "only_slot", None)
        if only and only != slot:
            self.log(f"{ent.name}: only skill slot {only} hurts it (hit by slot {slot})")
            return self.wrong_attack(ent, slot)
        msgs = self.attacked(ent, time.time())
        self.damage(ent, damage)
        return msgs

    # ---- W, E and D (batman.py) ----------------------------------------------------
    def sonic_shell(self, point, target, now):
        from . import batman
        return batman.sonic_shell(self, point, target, now)

    def bat_flight(self, point, target, now):
        from . import batman
        return batman.bat_flight(self, point, target, now)

    def bat_scream(self, point, target, now):
        from . import batman
        return batman.bat_scream(self, point, target, now)

    def scream_result(self, hit):
        return self.bridge.scream_result(hit)

    def resend(self, ent, delays=(1.0, 3.0)):
        """Send a placed object again a little later. 2026-10-15 13:11 (diag
        --create): the vehicle at the end of the bridge was never built by the
        client from its first message, only when it was moved (lifted)."""
        for d in self.match.cfg["tutorial"].get("prop_resend", delays) or ():
            self.schedule(float(d), lambda: [] if getattr(ent, "removed", False) or ent.eid not in self.match.entities
                          else [(f"{ent.name} sent again", self.match.entity_bundle(ent, time.time()))])

    def cinematic_done(self, did, now):
        """A cinematic ended on the client; None = not one the tutorial waits for."""
        return self.finale.cinematic_done(did, now)

    def carrying(self):
        return self.finale.carrying

    def throw(self, xyz, how):
        return self.finale.throw(xyz, how)

    def super_strength(self, xyz, target, now):
        """F (slot 8): lift the car, or throw it when carrying it."""
        if self.finale.carrying:
            return self.finale.throw(tuple(target.pos) if target is not None else xyz, "F")
        return self.finale.lift("F", xyz)

    def preference(self, name, value, now):
        """A client preference change (event 0x216E), e.g. User.CameraLocked."""
        if name == "User.CameraLocked" and self.phase == "bridge":
            return self.bridge.camera_lock_changed(value.lower() == "true", now)
        return []

    def stolen_power(self, point, now, how="D"):
        """D: Gaslight Batman's surveillance camera."""
        return self.bridge.place_camera(point or tuple(self.match.mover.pos), now, how)

    def rank_slots(self):
        """The skill slots whose '+' the tutorial is waiting for (() = none)."""
        if self.phase == "skills":
            return (Q_SLOT,)
        return tuple(self.bridge.pending_ranks)

    def rank_slot(self):
        """The recommended one of rank_slots() (None = none)."""
        slots = self.rank_slots()
        return slots[0] if slots else None

    def after_catwoman(self, now):
        return self.bridge.start(now)

    def batarang(self, target, now):
        """Q: Batman throws the Sonic Batarang at target; it ricochets."""
        m = self.match
        if now < getattr(self, "batarang_ready", 0):
            return []
        self.batarang_ready = now + BATARANG_COOLDOWN
        if m.cfg["scriptvm"].get("batarang"):
            # 2026-10-21 (fase3-fn): Q from the game's own server scripts ([scriptvm] batarang)
            from . import scriptvm_world
            if scriptvm_world.available():
                self.batarang_casts += 1
                return scriptvm_world.batarang(self, target, now)
            self.log("scriptvm: data/script_trees missing (python tools\script_decoder.py all); hand-written Q")
        tc = m.cfg["tutorial"]
        bx, by, _ = m.mover.pos
        m.mover.heading = math.atan2(target.pos[1] - by, target.pos[0] - bx)
        batman.root(self, now, reason="Sonic Batarang")
        m.sequence += 1
        msgs = [("Batman faces the Batarang target", m.champion_bundle(now))]
        keys = tuple(tc.get("batarang_keys") or BATARANG_CAST_KEYS)
        self.run_scripts(M.CHAMPION_AGENT_ID, keys, f"Sonic Batarang at {target.name}",
                         [(M.PROP_SCRIPT_TARGET, KIND_IID, target.eid)])
        chain, last = [target], target
        others = [e for e in m.entities.values() if e.alive and e.attackable and e is not target]
        for _ in range(BATARANG_BOUNCES):
            near = [e for e in others if e not in chain and e.distance_to(last.pos[:2]) <= BATARANG_RICOCHET_RANGE]
            if not near:
                break
            last = min(near, key=lambda e: e.distance_to(last.pos[:2]))
            chain.append(last)
        self.log("Sonic Batarang: " + " -> ".join(e.name for e in chain))
        damage = int(tc.get("batarang_damage", BATARANG_DAMAGE))
        for i, e in enumerate(chain):
            def hit(e=e):
                if not e.alive:
                    return []
                self.run_scripts(e.eid, BATARANG_HIT_KEYS, f"Batarang hits {e.name}",
                                 [(M.PROP_SCRIPT_TARGET, KIND_IID, M.CHAMPION_AGENT_ID)])
                if getattr(e, "only_slot", None) or getattr(e, "group", None):
                    return self.skill_hit(e, damage, Q_SLOT)
                self.damage(e, damage)
                return []
            self.schedule(BATARANG_FLIGHT + BATARANG_HOP * i, hit)
        self.schedule(BATARANG_FLIGHT + BATARANG_HOP * len(chain), lambda: (
            self.run_scripts(M.CHAMPION_AGENT_ID, BATARANG_STOP_KEYS, "Sonic Batarang over"), [])[1])
        self.batarang_casts += 1
        return msgs

    def batarang_at_point(self, xyz, now):
        """Q with nothing to hit: Batman still throws it towards the cursor
        (17:36: nothing was shown at all)."""
        m = self.match
        if xyz is None or now < getattr(self, "batarang_ready", 0):
            return []
        self.batarang_ready = now + BATARANG_COOLDOWN
        bx, by, _ = m.mover.pos
        if abs(xyz[0] - bx) + abs(xyz[1] - by) > 1e-3:
            m.mover.heading = math.atan2(xyz[1] - by, xyz[0] - bx)
        batman.root(self, now, reason="Sonic Batarang")
        m.sequence += 1
        keys = tuple(m.cfg["tutorial"].get("batarang_keys") or BATARANG_CAST_KEYS)
        self.run_scripts(M.CHAMPION_AGENT_ID, keys, "Sonic Batarang (no target)")
        self.schedule(BATARANG_FLIGHT + BATARANG_HOP, lambda: (
            self.run_scripts(M.CHAMPION_AGENT_ID, BATARANG_STOP_KEYS, "Sonic Batarang over"), [])[1])
        self.log("Sonic Batarang: no target, thrown towards the cursor")
        return [("Batman faces the Batarang throw", m.champion_bundle(now))]

    def _drone_ai(self):
        """Aggressive drones walk up to Batman and hit him (every 0.4 s)."""
        m = self.match
        tc = m.cfg["tutorial"]
        tick = float(tc.get("drone_tick", DRONE_TICK))
        walk = float(tc.get("drone_walk_speed", DRONE_WALK_SPEED))
        self.schedule(tick, self._drone_ai)
        if self.phase in ("done",):
            return []
        bx, by, bz = m.mover.pos
        now = time.time()
        out = []
        for e in list(m.entities.values()):
            if not (e.alive and e.attackable) or e.name in PRACTICE or getattr(e, "role", None) == "target":
                continue
            d = math.hypot(e.pos[0] - bx, e.pos[1] - by)
            leash = getattr(e, "leash", None) or DRONE_LEASH * (1.75 if e.name in WAVE else 1.0)
            if e.eid in self.aggressive and d > leash:
                self.aggressive.discard(e.eid)
                self.log(f"{e.name}: Batman is {d:.1f} m away, stops chasing")
            if e.eid not in self.aggressive:
                if e.name in WAVE and d < float(m.cfg["tutorial"].get("wave_aggro_radius", DRONE_AGGRO_RADIUS)):
                    self.aggressive.add(e.eid)
                    self.wave_quiet = False
                    self.log(f"{e.name}: leaves the vehicle and goes for Batman ({d:.1f} m)")
                else:
                    continue
            reach = (float(tc.get("ranged_attack_range", RANGED_ATTACK_RANGE))
                     if getattr(e, "role", None) == "ranged" else DRONE_ATTACK_RANGE)
            if d > reach:
                if now >= self.walk_logged.get(e.eid, 0):
                    self.walk_logged[e.eid] = now + 2.0
                    self.log(f"{e.name}: walks to Batman ({d:.1f} m)")
                # 2026-10-14 16:22: drones "jumped": each update sent the point
                # one tick AHEAD (the client then ran on from there and snapped).
                # Now: send where it IS, heading and speed, then advance; and walk
                # round the wagon / boxes instead of through them.
                from .world import route
                pts = route(m.mover.obstacles, e.pos, (bx, by), radius=0.4)
                wx, wy = pts[1] if len(pts) > 1 else (bx, by)
                last_leg = len(pts) <= 2
                dw = math.hypot(wx - e.pos[0], wy - e.pos[1]) or 1e-6
                step = min(walk * tick, (d - reach * 0.8) if last_leg else dw)
                e.heading = math.atan2(wy - e.pos[1], wx - e.pos[0])
                e.speed = walk
                out.append((f"{e.name} walks", m.entity_bundle(e, now)))
                e.pos = [e.pos[0] + (wx - e.pos[0]) / dw * step, e.pos[1] + (wy - e.pos[1]) / dw * step, e.pos[2]]
                continue
            if now < self.next_hit.get(e.eid, 0):
                continue
            self.next_hit[e.eid] = now + DRONE_ATTACK_INTERVAL
            e.heading = math.atan2(by - e.pos[1], bx - e.pos[0])
            out += m.move_entity(e, tuple(e.pos), now, speed=0.0)
            keys = self._attack_key(e.eid, e)
            self.log(f"{e.name}: hits Batman ({d:.1f} m)")
            self.run_scripts(e.eid, keys, f"{e.name} hits Batman",
                             [(M.PROP_SCRIPT_TARGET, KIND_IID, M.CHAMPION_AGENT_ID)])
            self.run_scripts(M.CHAMPION_AGENT_ID, BATMAN_HIT_KEYS, "Batman hit")
            hp, hp_max = m.vitals[0]
            m.vitals[0] = (max(1, hp - DRONE_DAMAGE), hp_max)
            out.append((f"Batman takes {DRONE_DAMAGE} ({m.vitals[0][0]}/{hp_max}) (0x42)",
                        M.vitals(M.CHAMPION_AGENT_ID, m.vitals)))
            self.last_hit_at = now
        return out

    def _bridge_tick(self):
        """Every 0.25 s: the bridge's markers and gates, and Batman's healing."""
        self.schedule(0.25, self._bridge_tick)
        now = time.time()
        return self.bridge.camera_tick(now) + self.bridge.update(now) + self.finale.update(now) + self._regen(now)

    def _regen(self, now):
        """'The Construct is healing him': Batman never dies in the tutorial. Out
        of combat he heals ([tutorial] regen_per_second); low on health he gets
        a quick heal and Superman's warning (once)."""
        m = self.match
        hp, hp_max = m.vitals[0]
        out = []
        if hp < hp_max * 0.25:
            m.vitals[0] = (int(hp_max * 0.6), hp_max)
            if not self.low_health_said:
                self.low_health_said = True
                out += self.say(0x1CE)
            return out + [("Batman healed by the Construct (0x42)", M.vitals(M.CHAMPION_AGENT_ID, m.vitals))]
        rate = float(m.cfg["tutorial"].get("regen_per_second", 8.0))
        if hp < hp_max and rate > 0 and now - getattr(self, "last_hit_at", 0.0) > 4.0:
            if now - getattr(self, "last_regen", 0.0) >= 1.0:
                self.last_regen = now
                m.vitals[0] = (min(hp_max, hp + int(rate)), hp_max)
                out.append(("Batman regenerates (0x42)", M.vitals(M.CHAMPION_AGENT_ID, m.vitals)))
        return out

    def _hit_vehicle(self):
        """The wave drones hit the vehicle until Batman attacks one of them."""
        m = self.match
        if not getattr(self, "wave_quiet", False):
            return []
        vehicle = next((v for v in m.entities.values() if v.name == "DestVehicle"), None)
        target = [(M.PROP_SCRIPT_TARGET, KIND_IID, vehicle.eid)] if vehicle else None
        for e in m.entities.values():
            if e.name in WAVE and e.alive and e.eid not in self.aggressive:
                keys = self._attack_key(e.eid)
                self.run_scripts(e.eid, keys, f"{e.name} hits the vehicle ({keys[0]:#x})", target)
        self.schedule(FIGHT_INTERVAL, self._hit_vehicle)
        return []

    def _fight(self):
        """One exchange of the drone-vs-human fight; repeats until Batman attacks."""
        m = self.match
        drone = next((e for e in m.entities.values() if e.name == FIRST_DRONE and e.alive), None)
        thug = m.entities.get(self.thug_eid)
        if self.first_attack_done or not drone or not thug:
            return []
        keys = self._attack_key(drone.eid)
        self.run_scripts(drone.eid, keys, f"drone hits the human ({keys[0]:#x})")
        self.run_scripts(thug.eid, THUG_HIT_KEYS, "human hit")
        tc = m.cfg["tutorial"]
        back = tc.get("thug_attack_keys")
        back = THUG_ATTACK_KEYS if back is None else tuple(int(k) for k in back)
        if back:
            def swing_back():
                if self.first_attack_done or not drone.alive:
                    return []
                self.run_scripts(thug.eid, back, "human hits the drone")
                self.run_scripts(drone.eid, DRONE_HIT_KEYS, "drone hit")
                return []
            self.schedule(FIGHT_INTERVAL / 2, swing_back)
        self.schedule(FIGHT_INTERVAL, self._fight)
        return []

    def near_drone(self, now):
        """Called while walking: getting close to the drone's spot skips the
        remaining walk steps (the player found it on their own)."""
        if self.phase != "walk" or not self.step or self.step >= self.drone_step:
            return []                     # after the first marker it appears on its own timer
        if not self.match.cfg["tutorial"].get("skip_markers", False):
            # 2026-10-14 19:39: walking past the first marker must not start the
            # next one: every marker has to be stepped on, in order
            return []
        if self.match.mover.distance_to(LAYOUT[FIRST_DRONE][1]) > DRONE_TRIGGER_RADIUS:
            return []
        msgs = self.remove_ping(self.step)
        # what the skipped steps would have said (the last one: the drone's lines)
        skipped = []
        while self.step < self.drone_step:
            skipped = [b for b in MOVE_STEPS.get(self.step, ()) if b[1] != "ping"]
            self.step += 1
        return msgs + self.beats(skipped) + self._drone_appears(now)

    def attacked(self, entity, now):
        bridge_msgs = self.bridge.attacked(entity) or []
        if (entity.name in WAVE or entity.name == FIRST_DRONE) and entity.eid not in self.aggressive:
            self.aggressive.add(entity.eid)
            self.log(f"{entity.name}: attacked, turns on Batman")
            if entity.name in WAVE:
                # 2026-10-14 20:12: attacking one of the two drones at the vehicle
                # turns BOTH on Batman
                for other in self.match.entities.values():
                    if (other.name in WAVE and other.eid not in self.aggressive
                            and other.alive and not getattr(other, "removed", False)):
                        self.aggressive.add(other.eid)
                        self.wave_quiet = False
                        self.log(f"{other.name}: its partner was attacked, turns on Batman")
        if self.first_attack_done:
            return bridge_msgs
        self.first_attack_done = True
        msgs = bridge_msgs
        thug = self.match.entities.get(self.thug_eid)
        if thug:
            # the human runs away from the fight, then leaves
            # run in small steps (the client animates each one), then leave
            # around the wagon and the boxes, not through them
            from .world import route
            sz = thug.pos[2]
            thug.yaw_offset = 0.0           # 23:42: the fight's turn made his run look wrong
            # 00:00: he vanished mid-run: the fog of war hid him behind the boxes /
            # wagon. He leaves the fight for good, so the fog no longer applies.
            thug.no_fog = True
            pts = route(self.match.mover.obstacles, thug.pos, THUG_FLEE_TO)
            speed, dt = 5.0, 0.15
            xyzs = []
            for (ax, ay), (bx, by) in zip(pts, pts[1:]):
                n = max(1, int(math.ceil(math.hypot(bx - ax, by - ay) / (speed * dt))))
                xyzs += [(ax + (bx - ax) * k / n, ay + (by - ay) * k / n, sz) for k in range(1, n + 1)]
            steps = len(xyzs)
            for i, xyz in enumerate(xyzs, 1):
                self.schedule(dt * i, lambda xyz=xyz, last=(i == steps): self.match.move_entity(
                    thug, xyz, time.time(), speed=0.0 if last else speed))
            eid = thug.eid
            self.log(f"tutorial: the human runs away ({len(pts) - 2} corners, {steps * dt:.1f} s)")
            def gone(thug=thug, eid=eid):
                thug.removed = True
                return [("thug gone (0x3)", M.remove_object(eid))]
            self.schedule(dt * steps + 1.5, gone)
        return msgs

    def killed(self, entity, now):
        m = self.match
        if str(getattr(entity, "group", None) or "").startswith("finale"):
            return self.finale.killed(entity, now)
        if getattr(entity, "group", None):
            return self.bridge.killed(entity, now)
        if self.phase == "first_drone" and entity.name == FIRST_DRONE:
            # 01:05 These metallic monsters... / 01:09 Not so fast, Batman. More drones
            # are coming! (+ the wave) / 01:12 Once you start attacking... + hint
            self.phase = "wave"
            msgs = self.remove_ping(self.drone_step, keep_visible=True)
            return msgs + self.beats((
                (0.5, "conv", 0x1E1), (4.0, "conv", 0x1E0), (5.0, "call", self._wave),
                (7.0, "conv", 0x38C), (7.0, "hint", HINT_BASIC_ATTACK)))
        if self.phase == "wave" and entity.name in WAVE:
            left = sum(1 for e in m.entities.values() if e.alive and e.name in WAVE)
            if left:
                return self._objective(WAVE_OBJECTIVE.format(len(WAVE) - left))
            # 01:22 Good job! (+ level 2) / 01:24 Beyond his basic attack... /
            # 01:29 Use a skill point... + highlighted Q
            self.phase = "skills"
            return self._objective(WAVE_OBJECTIVE.format(len(WAVE))) + self.beats((
                (0.5, "conv", 0x1DF), (0.5, "call", self._level_up),
                (2.5, "conv", 0x1D4), (7.5, "call", self._skill_prompt)))
        if self.phase == "practice" and not any(e.alive and e.name in PRACTICE for e in m.entities.values()):
            # After the Batarang: "When you use a skill, it goes 'on cooldown'..." /
            # "...consumed 'Will'..." / "It appears the path forward is blocked."
            # then Catwoman breaks the vehicle.
            self.phase = "catwoman"
            # "It appears the path forward is blocked." (0x1AF) is the first line of
            # the Catwoman cinematic itself (conversation flag 0x4000, like 0x358 and
            # 0x357), so the server does not start it: it played twice (2026-10-14).
            # Each line waits for the previous one to be spoken (2026-10-14: the
            # cinematic cut Superman's 'Will' line).
            will_at = 2.0 + CONV_SECONDS[0x19A] + 0.5
            msgs = self.beats(((2.0, "conv", 0x19A), (will_at, "conv", 0x1E3)))
            cin = m.cfg["tutorial"].get("catwoman_cinematic", CATWOMAN_CINEMATIC)
            if cin:
                delay = m.cfg["tutorial"].get("catwoman_delay")
                pacing = float(m.cfg["tutorial"].get("pacing", 1.0))
                if delay:
                    self.schedule(float(delay) * pacing + 0.5, lambda: self._catwoman(cin))
                else:
                    # once 0x1E3 is sent, wait for the whole queue to be spoken
                    # 2026-10-14 11:39: "the time between the last line and the
                    # cinematic is too long, halve it": the estimate was generous
                    scale = float(m.cfg["tutorial"].get("catwoman_wait_scale", 0.5))

                    def go():
                        wait = max(0.0, (getattr(self, "speech_end", 0.0) - time.time()) * scale) + 0.5 * pacing
                        self.schedule(wait, lambda: self._catwoman(cin))
                        return []
                    self.schedule(will_at * pacing + 0.1, go)
            else:
                # no cinematic: part 2 (the bridge) starts once the lines are spoken
                self.schedule(will_at * pacing + 0.1, lambda: self.after_speech(1.0 * pacing, lambda: (
                    self._vehicle_destroyed() + self.bridge.start(time.time()))))
            return msgs
        return []

    def _wave(self):
        """'More drones are coming!': the wave teleports in by the vehicle."""
        m = self.match
        now = time.time()
        msgs = []
        if m.cfg["tutorial"].get("meteors", True):
            msgs += self.meteor(WAVE_METEOR, now)          # "not so fast, Batman": another one falls
        override = m.cfg["tutorial"].get("wave_positions") or WAVE_POSITIONS
        for name in WAVE:
            msgs += m.spawn(name, now, xyz=tuple(override[name]) if name in override else None)
        self._spawn_effect(WAVE)
        vehicle = next((e for e in m.entities.values() if e.name == "DestVehicle"), None)
        if vehicle:
            for e in m.entities.values():
                if e.name in WAVE:
                    e.heading = math.atan2(vehicle.pos[1] - e.pos[1], vehicle.pos[0] - e.pos[0])
                    msgs.append((f"{e.name} faces the vehicle", m.entity_bundle(e, now)))
            self.wave_quiet = True
            self.schedule(1.0, self._hit_vehicle)
        self.log("tutorial: the wave arrives")
        return msgs + self._objective(WAVE_OBJECTIVE.format(0))

    def _level_up(self):
        m = self.match
        m.level, m.xp, m.skill_points = 2, 0, 1
        m.skill_ranks = set_recommended(m.skill_ranks, Q_SLOT)    # orange frame + arrow on Q
        m.sequence += 1      # a higher sequence so the client applies the new property values
        msgs = [("champion level 2 + skill point", m.champion_bundle(time.time()))]
        # Only Q's upgrade button: the W/E/R/passive ones stay hidden (never
        # restored), so only Q shows the rank-up animation (2026-10-14).
        others = () if m.cfg["tutorial"].get("restore_other_upgrades", False) else OTHER_UPGRADE_BUTTONS
        if not m.cfg["tutorial"].get("skill_point_reminder", False):
            # 2026-10-14 14:44: every skill still showed the rank-up animation; the
            # "spend your skill point" reminder is the candidate (only Q should)
            others = tuple(others) + (HUD["SkillPointSpendReminder"],)
        msgs += [(f"HUD element {e} restored (0x213d)", M.hud_element(e, HUD_EVENT_FIRST_RESTORED))
                 for e in SKILL_ELEMENTS if e not in others]
        msgs.append(("champion vitals (0x42)", M.vitals(M.CHAMPION_AGENT_ID, m.vitals)))
        msgs.append((f"tutorial hint {HINT_EXPERIENCE}", M.tutorial_hint(HINT_EXPERIENCE)))
        return msgs

    def _skill_prompt(self):
        if self.phase != "skills":        # Q was already ranked: no prompt, no highlight
            return []
        msgs = self.say(0x1BE) + [
                ("highlight Q upgrade button (0x213d)",
                 M.hud_element(FIRST_SKILL_UPGRADE, HUD_EVENT_SHOW_HIGHLIGHT))]
        if self.match.cfg["tutorial"].get("lock_other_skills", False):
            msgs += [(f"HUD element {e} hidden: only Q can be ranked (0x213d)", M.hud_element(e, HUD_EVENT_HIDE))
                     for e in OTHER_UPGRADE_BUTTONS]
        msgs.append((f"tutorial hint {HINT_SKILL_POINTS}", M.tutorial_hint(HINT_SKILL_POINTS)))
        msgs.append((f"tutorial hint {HINT_SKILL_RANKS}", M.tutorial_hint(HINT_SKILL_RANKS)))
        if self.on_skill_prompt:
            self.on_skill_prompt()
        return msgs + self._objective(SKILL_OBJECTIVE)

    def _catwoman(self, cin):
        m = self.match
        out = []
        tc = m.cfg["tutorial"]
        # she breaks the vehicle during the cinematic ([tutorial] vehicle_break_at
        # seconds after it starts; the wreck stays, see vehicle_keep_wreck)
        at = float(tc.get("vehicle_break_at", 6.0))
        if at >= 0:
            self.schedule(at, self._vehicle_destroyed)
        if tc.get("cinematic_place_champion", True):
            xyz, heading = CATWOMAN_CINEMATIC_BATMAN
            m.mover.place(xyz, heading)
        if tc.get("cinematic_hide_champion", True):
            m.champion_hidden = True        # shown again when the cinematic ends (state 4)
        if tc.get("cinematic_place_champion", True) or tc.get("cinematic_hide_champion", True):
            m.sequence += 1
            out.append(("Batman placed / hidden for the cinematic", m.champion_bundle(time.time())))
        return out + [(f"Catwoman cinematic {cin:#x} (0x20f5)", M.cinematic(cin))]

    def skill_ranked(self, now, auto=False, slot=Q_SLOT):
        """A skill's '+' was clicked (the patched client sends RankSkill as a
        ping). The first one is Q; the later ones belong to the bridge."""
        if self.phase != "skills":
            return self.bridge.ranked(slot, now, auto)
        if slot != Q_SLOT:
            return []
        m = self.match
        self.phase = "practice"
        m.skill_points = 0
        m.skill_ranks = set_recommended(m.skill_ranks, None) | 1 << (4 * Q_SLOT)   # Q at rank 1
        m.sequence += 1
        msgs = [("champion skill point spent" + (" (automatic)" if auto else ""), m.champion_bundle(now))]
        if m.cfg["tutorial"].get("hide_upgrade_buttons"):
            msgs += [(f"HUD element {e} hidden (0x213d)", M.hud_element(e, HUD_EVENT_HIDE))
                     for e in UPGRADE_ELEMENTS]
        # 01:36 You can learn more... / 01:40 Construct: Can we have some target
        # drones? (they appear) / 01:43 Practice your new skill... + objective
        return msgs + self.beats((
            (0.5, "conv", 0x19B), (4.5, "conv", 0x1AB), (5.5, "call", self._practice_drones),
            (7.5, "conv", 0x1B7), (7.5, "objective", PRACTICE_OBJECTIVE)))

    def _practice_drones(self):
        m = self.match
        now = time.time()
        msgs = []
        override = m.cfg["tutorial"].get("practice_positions") or {}
        for name in PRACTICE:
            xyz = override.get(name)
            msgs += m.spawn(name, now, xyz=tuple(xyz) if xyz else None)
        self._spawn_effect(PRACTICE)
        return msgs


def player_ping(match, body, count, now):
    """Answer client event 0x2136 (Alt+click): f32 x | f32 y | u64 target | u32 type.
    Returns (object id, message, [(note id, note message)]) or None."""
    if len(body) < 20:
        return None
    x, y, target, ptype = struct.unpack_from("<ffQI", body, 0)
    object_id = M.PLAYER_PING_BASE_ID + (count % 0x20)
    class_id = PLAYER_PING_CLASSES.get(ptype, 0x4000025A)
    spawn = match.mover.spawn
    pos = (spawn[0], spawn[1], spawn[2], 0, x, y, spawn[6])
    mode = note_mode(match)
    props = ping_properties(ping_team_for(match, class_id), ping_style(match), show=mode == "self")
    if mode == "self":
        props += player_note_props(match, class_id, extras_only=True)
    msg = M.create_object(object_id, class_id, now, position=pos, module=match.module,
                          second_seq=match.second_seq, properties=props)
    notes = []
    if mode == "companion":
        note_id = MAP_NOTE_BASE_ID + (count % 0x10)
        notes.append((note_id, M.create_object(note_id, PING_CLASS, now, position=pos, module=match.module,
                                               second_seq=match.second_seq,
                                               properties=player_note_props(match, class_id))))
    return object_id, msg, notes
