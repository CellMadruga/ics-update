"""Configuration: config.toml next to ic.py, merged over the defaults below.

Every value the old server had hard-coded in its source lives here, so testing
a different champion, spawn point or timing never means editing code.
"""
import copy
import os

try:
    import tomllib
except ImportError:          # Python < 3.11: doctor reports it, nothing else works anyway
    tomllib = None

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

DEFAULTS = {
    "game": {
        # Folder that contains InfiniteCrisis.exe and the rp\ data packs.
        "dir": r"C:\Program Files (x86)\Steam\steamapps\common\Infinite Crisis Steam",
        "exe": "InfiniteCrisis.exe",
        "patched_exe": "InfiniteCrisis_patched.exe",
        "language": "en",
        "region": "NA",
        # CPU affinity mask for the client ("" = leave alone). The old project
        # always kept the game off CPU 0 (FFFE).
        "cpu_affinity": "FFFE",
        # 2026-10-28 15:00 (tester report: the black octagons at both Crime Alley dampeners were gone with diag
        # --mapa-rellenar; docs/re-notes/map-audit-all.md 2 / 6): the terrain sockets `python ic.py patch` flattens
        # in the map packs (icserver/terrainfix.py SITES). A site left out is written back to the installed bytes
        # (from the pack's .terrainfix.json backup) on the next patch; [] = every pack as installed.
        # gotham_divided_pits is off: the phase pods rise there and [ics] match_socket_covers puts the lids on them.
        # 2026-10-28 (tester report 2026-10-28 15:00; map-audit-all.md 10.1 / 11, C): Gotham Divided's lane exits are
        # one site per team. Team 1's ground there is drawn with installed layers (types 0x7 / 0xD), team 2's with
        # the asphalt 0xE / 0xF that no GD pack holds (flat it would be dark), so only team 1's is on and the server
        # keeps its lids on team 2's exits (it leaves out a lid whose socket is flattened in the pack). The old name
        # "gotham_divided_lane_exits" still means both. tutorial_2_dampener (Tutorial 2's copy of Crime Alley's
        # socket) is off: ics runs no Tutorial 2. Coast City's centre: if the cursor or a ground-target ring drops
        # through its square after the patch (MOPP, map-audit-all.md 9.1), leave coast_city_centre out.
        # 2026-10-29 (tester report 2026-10-29 12:45: black sections in Crime Alley's centre; ca-holes-pedestal-turrets.md
        # C1): crime_alley_lane_turret raises the rim of team 1's lane-turret socket (the black sidewalk strips at x 70-75)
        # 2026-10-29 (tester report 2026-10-29 14:40, screenshot 46.webp; gh-freeze-holes-picking.md H2):
        # crime_alley_south_alcove_rim raises the one alcove vertex that opens the south sidewalk under the south
        # stealth field (x 80-90, y 65-70)
        # 2026-10-29 (tester report 2026-10-29 16:40, screenshot 49.webp; ca-black-strips.md 3): crime_alley_lane_turret
        # also raises the socket's centre-row vertex (70, 75) (the south strip x 70-75, y 70-71.7 was its funnel);
        # python ic.py patch restores the rim-only version from the backup and re-patches in one run. Leaving the site
        # out of this list restores the installed bytes
        "terrain_sockets": ["crime_alley_dampeners", "crime_alley_lane_turret", "crime_alley_south_alcove_rim",
                            "gotham_divided_lane_exits_team1", "coast_city_centre"],
        # 2026-10-29 (tester report 2026-10-29 21:10: the turret warning ring never shows; ca-fog-minimap-ring.md 2):
        # exe patches `python ic.py patch` leaves at the original bytes, by a text of their description (e.g.
        # ["perception filter"] = the ring phantom's filter refuses our top-byte-2 units again, as fase3-in). [] = all
        # 2026-10-29 (tester report 2026-10-29 23:03, 83.webp: the black strip by the fence east of our lane turret;
        # ca-street-occluder-ring.md 1): ["fog occluder pass"] = the client's fog draws occluder shadows again (the strip
        # comes back with our structures' circles)
        # 2026-10-30 (tester report 18:12: no hover highlight on any minion, no left-click select; hover-listener-iid-
        # gate.md): ["controlled agent listeners"] = the champion's 0x3CB / LifeState listeners stay unregistered again
        # (no soft-selection scriptlet, outline or attack cursor on hover)
        "exe_patch_skip": [],
    },
    "server": {
        "host": "127.0.0.1",
        "soap_port": 8888,
        "user_port": 9000,
        "game_port": 9001,
        "key": "keys/server_private.pem",
        # champions.json (roster extracted from the packs by tools/roster.py).
        # Empty = data\champions.json.
        "champions_json": "",
    },
    "uesrv": {
        # New server for the UE5 client (2026-10-18, user decided the server is the base and the client a thin
        # copy). Separate ports from the legacy server so both can run; "host" 127.0.0.1 = this machine only,
        # use 0.0.0.0 to let another PC on the LAN connect.
        "host": "127.0.0.1",
        "control_port": 9100,       # JSON-lines control protocol (login, profile, catalog)
        "asset_port": 9101,         # HTTP asset service (needs the session token)
        "accounts": "data/uesrv_accounts.json",
        "cache_dir": "data/uesrv_cache",
        "protocol": 1,
    },
    "account": {
        "level": 30,           # veteran level: skips the trainee light-pack load
        "player_name": "Player",
    },
    "match": {
        # Send the champion's skill ranks as the client's own rank array
        # (property 0x100000AF); needed for the client to allow casting Q.
        "rank_array": True,
        # Vitals (0x42): put health / Will in the client's first list instead of
        # the second (the HUD shows their sum). Test for "not enough Will" on Q.
        "vitals_first_list": True,
        "champion": 0x40000086,         # Gaslight Batman variant (Tutorial 1)
        "agent_class": 0x40000086,      # descriptor of the champion object you control
        # Descriptor of the "player object". The original game had a separate,
        # invisible object here; the old server reused Batman (= a second,
        # gliding Batman drawn over the walking one). 0x4000007C is the
        # "Unnamed Player" variant (always-loaded pack 0xa0000037, no model).
        # `python ic.py play --classic` goes back to 0x40000086.
        "player_class": 0x4000007C,
        # Extra packs the match must load (0x20AF). 0xA000024C is the tutorial's
        # zone pack (category 0xd: the client has ONE slot for it, diag 2026-10-14;
        # another zone pack such as 0xA000009A takes the slot and the load hangs).
        # 0xA00000CC: Gaslight Catwoman's heavy pack (she is in cinematic 0x35000034).
        "packs": [0xA0000076, 0xA000024C, 0xA00000CC],
        # Other champions the match must load: Gaslight Catwoman (variant 0x40000262)
        # for the cinematic where she breaks the vehicle (2026-10-13: dialogue but no model).
        "extra_champions": [0x40000262],
        "team": 1,
        "room_id": 1,
        # Spawn: region, landblock x, landblock y, cell, x, y, z
        "spawn": [1, 0x13, 0xCB, 0, 18.7, 60.4, 200.3],
        # Ground height of the tutorial street: clicked heights within 3 m are
        # snapped to it (the client's click height creeps up, 2026-10-14). 0 = off.
        "ground_z": 200.0,
        "cinematic": 0x35000026,        # 0 = no intro cinematic
        # Played before it, in order (each one after the previous ends). The
        # tutorial's other cinematics: 0x35000025 (power cores falling from the
        # sky: the meteor?), 0x35000033 (drone vs thugs), 0x35000034 (Catwoman).
        "pre_cinematics": [],
        # Event 0x2053 "match started": the client's game systems (dialog gate bit 4,
        # probably the Advancement scripts that answer the skill "+") start with it.
        # 2026-10-14: sent after the load, the client goes back to the loading
        # screen and connects to the lobby again (= the real match load).
        # false | "reload" (send it with the lobby data, create the objects on the
        # reload) | "lobby" | "in_world" | "after_intro" (these two hang).
        "send_match_start": False,
        # replaying in the same login: the client's own teardown already destroys
        # every object (2026-10-15 static analysis), so removing them (0x3) is off;
        # what the next match needs is 0xEB (set local player) again
        "remove_objects_on_leave": False,
        "resend_local_player": True,
        # 0x20AF + 0x2016(0) before the game welcome (the client's 60 s lobby
        # watchdog), and no room-id 0x2016 with the lobby data. 22:43: with
        # both, the FIRST load stalled at 55 %: back to the old order
        "enter_match_first": False,
        "lobby_room_check": True,
        # Movement speed property (0x100005E4) on the champion: the client derives
        # the walk-animation speed cap from it (0 = Batman slides). 0 = don't send.
        "anim_move_speed": 4.5,
        "lighting_env": 0x10000016,       # property 0x956 (lighting environment); 0 = not sent (test for the dark fog)
        # extra minimap icon on Batman (0 = none). 2026-10-14 19:39: the minimap
        # already draws the local player (yellow ring); 0x13000376 added a 2nd icon
        "champion_map_icon": 0,
        "health": [600, 600],
        "secondary": [100, 100],
    },
    "timing": {
        # Match objects are created once ALL of: the client is in the lobby,
        # at least objects_min_delay s have passed, and the client reported at
        # least objects_min_percent % loading. objects_max_wait is the fallback.
        "objects_min_delay": 4.0,
        "objects_min_percent": 15,      # the client waits for the objects at 15% (log 2026-10-13)
        "objects_max_wait": 10.0,
        "link_delay": 2.0,             # 2nd bundle: links player -> champion
        "cinematic_delay": 5.0,        # after the client's load-complete notice
        "tutorial_start_delay": 0.5,
        "idle_resend": 5.0,            # full object refresh while standing still (0 = off)
        "keepalive": 2.0,              # time packet on the game connection
        "move_hz": 60,
        "move_speed": 4.5,             # 6.0 looked too fast in game (2026-10-13)
        "ping_lifetime": 4.5,             # s a player ping stays (ground + minimap); original ~4-5 s
    },
    "tutorial": {
        # Spacing of the tutorial's dialogue and events, taken from the original's
        # chat log (seconds between lines). 1.0 = like the original, 0 = all at once.
        "pacing": 1.0,
        # Guide points (x, y, z in landblock 0x13,0xcb), in order. Empty = built-in.
        "targets": [[25.0, 60.3, 200.0], [30.5, 59.0, 200.0]],   # old flow (unused)
        "drone_step": 3,                                          # old flow (unused)
        # 2026-10-14 12:08 (as in the original): a marker where Batman must walk;
        # there the big meteor knocks him down; when he is up, the drone and the
        # human are fighting and a second marker points at them.
        "walk_targets": [[25.1, 60.3, 200.0]],     # 23:07: 1.5 m further on (was 23.6, 60.6)
        "drone_appear_delay": 7.0,     # s after reaching marker 1 (x pacing): the next marker, 1 s after he is up
        "start_lock": 3.5,             # s Batman cannot move at the start (the 3 small meteors)
        # Ground marker / guide arrows: three ways of playing the guide scripts,
        # one every guide_variant_gap seconds after each marker (see tutorial1.ping)
        "guide_variants": ["A", "B", "C"],
        "guide_variant_gap": 4.0,
        # Visible marker: a player ping (retreat class, green) on each guide target, since
        # the guide's own ground circle does not show yet (0 = off)
        # The street vehicle breaks in steps (Destructible_AdvanceState 0x10000063,
        # not accepted by the client yet). vehicle_break_at = seconds into the
        # Catwoman cinematic when she hits it: the vehicle is removed then.
        "vehicle_states": 2,
        "batarang_aim_radius": 1.5,       # m: the cursor must be this close to a drone (or on the throw line)
        "vehicle_break_keys": [0x10000063],
        "vehicle_break_at": 6.0,
        # 2026-10-14 15:52 (diag --scripts): the vehicle's scriptlet table is EMPTY
        # ("0 grupos"), so Destructible_AdvanceState never runs and it stays whole:
        # it is removed after the cinematic again until the destruction works.
        "vehicle_keep_wreck": False,
        "fog_of_war": True,               # hide units out of Batman's sight (radius / walls) with 0x90F
        "vision_radius": 14.0,
        "meteor_objects": True,           # meteor rocks as objects (False = only Batman's knockdown)
        "meteor_scale": 0.3,              # size of the small meteors (1.0 = model size)
        "big_meteor_scale": 1.0,
        "meteor_scale_property": 0x6B4,   # object scale (render component; may be a list)
        "big_meteor_crater": True,        # the big meteor: a crater instead of a rock
        "crater_mode": "wstate",          # wstate = 0x2E0004BE placed like the rocks | entity = 0x400004FD
        "crater_wstate": 0x2E0004BE,
        "crater_carrier_slot": 1,            # 1 = the crater's own entity 0x400004FD (its scripts); 0 = the gate (no scripts)
        "crater_scale": 1.0,
        "crater_yaw": 0.0,
        "crater_blast": True,             # run the start scripts (VFX) on the crater
        "big_meteor_rock": False,         # also drop a rock there
        "meteor_wstate": 0x2E000BB3,      # the rock (env_event_meteor_a); 0x2E0007D4 = its dust cloud
        "ping_team": -1,                  # PVP_Team on markers/pings (-1 = champion's; 0 also showed red)
        "ping_style": "team",             # minimal | team | full: properties on pings (team = class icon + team colour)
        # PVP_Team per ping class: the colour is the relation to Batman's team
        # (same = blue, 0 = neutral, other = red). Alt 0x4000025B red, Ctrl 0x4000025A neutral
        "ping_class_teams": {"0x4000025B": 2, "0x4000025A": 0},
        # minimap notes: an invisible companion on each ping / marker carries the
        # minimap icon (enemy-team objects never get one)
        "skip_markers": False,            # walking near the drone skips the markers left (off: in order)
        "marker_note_seconds": 5.0,       # s the tutorial marker shows on the minimap (ground marker stays)
        "map_notes": "self",              # self | companion | off: who carries the minimap note
        "map_note_team": 0,
        "map_note_icon": 0,               # extra minimap icon for pings (0x13000A15 = yellow cone; 0 = none)
        "map_note_category": 0x1D,        # 0x1D = player-ping notes (the client special-cases it); 1 drew 2 icons
        "map_note_variants": {"0x4000025B": 0, "0x4000025A": 1},   # icon variant per ping (guess)
        "marker_ping_class": 0x4000025A,   # the green one (2026-10-14 14:26)
        "marker_radius": 1.5,             # m: where Batman STOPS counts as on the marker
        "marker_pass_radius": 0.6,        # m: walking through counts only this close
        # ground ring candidates (property 0x8E = [0x3400053C, 0x34000600]): the
        # client CRASHED when the marker carried them (2026-10-14 15:11), so off
        "marker_vfx": [],
        "marker_category": 0x1D,          # minimap note category of the tutorial marker (as the pings)
        # second marker: on the ground next to the drone and the human ([] = at the drone)
        "drone_marker": [36.9, 57.6, 200.0],
        "knockdown_delay": 1.0,        # s from marker 1 to the meteor hitting (he falls)
        "knockdown_lock": 7.5,         # s from marker 1 until he can move: 1 + 5 down + 1.5
        # The patched exe (`ic.py patch`) sends the skill "+" to the server (a lone
        # rank query for Q; the HUD's refresh bursts are ignored). As a fallback
        # (old exe) the server unlocks the first skill itself this many seconds
        # after asking (0 = off).
        "auto_rank_seconds": 60,
        # Hide the "+" buttons after that unlock. Off: in game (2026-10-13) the
        # whole skill HUD disappeared with them.
        "hide_upgrade_buttons": False,
        # Falling meteors (PowerCore objects) at the start, when reaching the
        # first marker (Batman knocked down) and after the first drone.
        "meteors": True,
        # Cinematic after the practice drones: Catwoman breaks the vehicle (0 = off).
        "catwoman_cinematic": 0x35000034,
        # Drones that Batman attacks (the wave also when he comes close) walk up
        # to him, hit him and take health (6 per hit, never below 1).
        "drones_fight_back": True,
        # The wave and practice drones "teleport in": [seconds after appearing,
        # script] pairs. Vfx_Spawn, then Vfx_Fade_In twice. [] = off.
        "spawn_sequence": [[0.1, 0x10000032], [0.9, 0x10000033], [1.6, 0x10000033]],
        # Attack scripts the drones use, one swing per hit, in turn; each entry is
        # one key or a list of keys run together. The log names them ("attack
        # scripts 0x...+0x..."): keep the one whose swing shows. [] = built-in
        # (Robot_Minion_Melee_Attack / Combat_Basic_Attack + Vfx_Min_Basic_Melee).
        "drone_attack_keys": [],
        # Drone walk: speed (m/s) and seconds between steps.
        "drone_walk_speed": 1.6,
        "drone_tick": 0.25,
        # Seconds from the last practice drone to the Catwoman cinematic (its own
        # first line is "It appears the path forward is blocked.").
        # 0 = after Superman's last line (~18 s).
        "catwoman_delay": 0,
        # At level 2 restore also the W/E/R/passive upgrade buttons (false: only
        # Q shows the rank-up animation, as in the original).
        "restore_other_upgrades": False,
        # Practice target drones: {name = [x, y, z]} to move them. {} = built-in.
        "practice_positions": {},
        # The yellow target drones only take the Sonic Batarang (Q), not basic attacks.
        "practice_immune": True,
        # Only Q can be ranked in the tutorial: hide the W/E/R/passive "+" buttons
        # while the Q one is highlighted. Off: hiding them makes the whole skill
        # HUD disappear (2026-10-13 and 2026-10-14).
        "lock_other_skills": False,
        # Sonic Batarang: damage per drone it reaches (it ricochets to 2 more within
        # 8 m) and Batman's scripts for the throw ([] = built-in: 0x10000164
        # Batman_Gaslight_Sonic_Batarang + 0x10000171 Vfx_Bmg_Batarang).
        "batarang_damage": 200,
        "batarang_keys": [],
        # Before it, put Batman where the cinematic's own Batman stands, so the
        # two copies overlap instead of showing two Batmen (false = off).
        "cinematic_place_champion": True,
        # ...and hide him during it (property 0x90F, the flag the client's
        # cinematic player uses to hide entities); shown again at the end.
        "cinematic_hide_champion": True,
        # ---- part 2: the bridge (icserver/bridge.py) ------------------------------
        # Skip part 1 and start at a later point, for testing: "" (play it all),
        # "bridge" (Catwoman's pursuers), "camera", "gate_fight", "unlock_e",
        # "e_practice", "vehicle", "scream", "strength", "destroyer".
        "start_at": "",
        # Move any spot of the bridge: { name = [x, y], ... }. Names: pursuer1,
        # pursuer2, w_target, marker1, ambush_melee1, ambush_melee2, ambush_ranged,
        # camera, gate_drones (marker), gate_melee1/2, gate_ranged1/2, e_target,
        # more_melee1/2, more_ranged1/2, vehicle, vehicle_melee1/2,
        # vehicle_ranged1/2, scream1/2/3, and the gates 03GateA, 03GateMid,
        # 03GateB. An Alt+click logs its x, y.
        "bridge_positions": {},
        # The three blue gates block the way while closed.
        "gates_block": True,
        # The middle gate closes again when Batman is this far along the bridge
        # (metres from the first gate; the last gate is at 40.4).
        "gate2_close_at": 27.0,
        # The last gate closes again behind him, this far past it.
        "gate3_reclose": True,
        "gate3_close_after": 6.0,
        # The drones hitting a gate / the vehicle turn on Batman when one of them
        # is attacked; > 0 = also when he comes this close (m).
        "gate_drones_notice": 0.0,
        "vehicle_drones_notice": 0.0,
        # The team given to the gates' light walls ("player" = Batman's, -1 = none):
        # a test, they showed white instead of blue.
        "gate_team": "player",
        "bridge_marker_radius": 2.0,
        # Health of the yellow target drones of W and E (one hit of the skill).
        "bridge_target_health": 100,
        # The D button (surveillance camera): if the client sends no D order, the
        # camera is placed by itself this many seconds after the prompt (0 = never).
        # An Alt / Ctrl + click on the marked spot also places it.
        "camera_auto_seconds": 25.0,
        "camera_spot_radius": 3.5,
        # The surveillance cameras see this far (fog of war).
        "camera_vision_radius": 10.0,
        # The Bat Scream part: how long to wait for the client's "camera unlocked"
        # / "camera locked" (User.CameraLocked) before going on (s), and the
        # tutorial's R cooldown ([combat] cooldowns overrides it).
        "camera_unlock_wait": 10.0,
        # The Stolen Powers on D / F: "auto" = send each slot's skill definition
        # (needs logs\props.txt from tools\diag.py --props; nothing is sent
        # without it), false = never (place the camera with an Alt+click, lift
        # cars with an Alt+click or by walking into them).
        "stolen_power_property": "auto",
        # W and E aimed at the ground: the drone within this many metres of the
        # cursor is the target.
        "skill_aim_radius": 3.0,
        # Part 3 (icserver/finale.py): Super Strength and the Destroyer.
        # finale_positions = { name = [x, y] }: strength_melee1/2, strength_ranged,
        # car_b, car_b_melee, car_b_ranged, ahead_melee, ahead_ranged, destroyer.
        "finale_positions": {},
        "destroyer_cinematic": 0x35000028,   # the sphere falls and the Destroyer comes out
        "ending_cinematic": 0x35000025,      # "You did it, Protector!", the last gate opens
        "cinematic_timeout": 60.0,           # go on if the client never reports the end
        "lift_range": 4.5,                   # F / Alt+click lifts the car from this close
        "lift_on_touch": 3.0,                # walking this close to the car lifts it (0 = no)
        # Super Strength on Batman: SuperStrength_InitObjectPickup (bends down,
        # grabs), lift_step s later SuperStrength_PickupObject (lifts; then the
        # hands-up carry walk on its own); the car goes up lift_attach s after
        # that, to carry_height m. Nothing is sent to Batman while he carries.
        "lift_keys": [0x100007A2, 0x100007A1],
        "lift_step": 0.5,
        # graph events raised on Batman with the last lift key, through
        # _HFSM_BehaviorRaiseEventAction (0x100001E3, variable 0x780): CarPickup
        # takes him from the crouch to the lift and the hands-up hold
        "lift_events": [0x10000246],
        "raise_event_kind": 8,               # kind of variable 0x780 (8 enum; 0x0A the other enum kind)
        "throw_end_events": [],              # e.g. [0x100000BB] state_to_locomotion after the throw
        "lift_attach": 0.1,
        "carry_height": 2.1,                 # 12:18: 2.7 left a gap above his hands
        "carry_keys": [],
        "throw_keys": [0x100007A0],
        "throw_windup": 0.2,                 # the car leaves his hands 0.20 s into the throw
        "throw_seconds": 0.9,                # then _Combat_GoToLocomotion (normal walking)
        "throw_range": 14.0,
        "blast_radius": 4.5,
        "destroyer_health": 3000,
        "destroyer_hit_range": 7.0,          # Batman's basic attack reaches the Destroyer from here
        "car_b_wstate": 0x2E00034D,          # the second car: 02PaddyWagonA (0x2E000AAB = the street's police wagon)
        "car_b_box": [7.5, 1.6],             # car B blocks the street: [half length, half width] across it
        # scenery near car B Batman walks through: ["Name", [[x, y], ...]] or
        # ["Name", x, y, half_length, half_width, yaw]
        # 13:56: with only car B's box the server walked Batman round its south end,
        # through the wall (the client showed him jumping past). The street's
        # walls at car B, from the clicks the client snapped to their edges:
        "finale_obstacles": [
            # (14:15: on to the building corner and the street turning north-east)
            ["CarBSouthWall", [[117.0, 11.25], [136.0, 11.25], [137.5, 11.6], [139.0, 11.95], [141.5, 13.15],
                               [143.5, 13.9], [143.5, -10.0], [117.0, -10.0]]],
            ["CarBNorthCrates", [[117.0, 18.65], [131.5, 18.65], [135.0, 18.95], [138.0, 20.0], [141.0, 22.0],
                                 [141.0, 45.0], [117.0, 45.0]]],
        ],
        # the car's own scriptlets when it lands: Vfx_OnExplode (as in the
        # original's intro cinematic); it needs the car's script table (0x7D2,
        # [combat] prop_script_tables). [] = none
        "car_explode_keys": [0x10000079],
        # earlier tries (they do nothing on the client): the behavior property
        # 0x100003F2 set to these one every car_crash_step s, and
        # Destructible_AdvanceState as a property (car_break_property)
        "car_crash_states": [],
        "car_crash_step": 1.0,
        "car_break_property": 0,
        "wreck_seconds": 6.0,
        # the car at the end of the bridge: 0x2E000AAB (police wagon, a static
        # prop: it cannot break) or 0x2E00034D (the paddy wagon, which can)
        # 15:09 (the original's video): the car at the end of the bridge is not
        # the paddy wagon of car B; 02PaddyWagonB (0x2E00034E, model 0x17000BC4,
        # the same breakable behavior graph) is the other wagon of the layout
        "bridge_vehicle_wstate": 0x2E00034E,
        "car_b_behavior_state": 0x10000116,  # car B starts as the graph's IdleState02 (0 = as the world state says)
        "destroyer_in_cinematic": True,      # spawn the Destroyer before its cinematic (it opens when it ends)
        # the end of the match (docs/reverse-engineering.md "Ending a match")
        "send_match_end": True,              # notice 0x1000000E (VICTORY) + completed list 0x214B
        "send_match_stats": True,            # 0x2045: completes the end page (then the post-match movie plays)
        "victory_hold": 6.0,                 # seconds of in-world VICTORY before the match-ended notice
        # the VICTORY during the ending cinematic, this long after it starts
        # (after Superman's last line; the cinematic lasts ~23 s); 0 = at its end
        "victory_in_cinematic": 18.5,
        "victory_end_delay": 0.0,            # then the match ends this long after the cinematic ends
        # ...or rather this long after the cinematic starts, just before its end
        # (so the camera does not come back to Batman); 0 = at its end
        "match_end_in_cinematic": 22.6,
        # once the client closes the end page (0x20A6), 0x2190 again (harmless;
        # the reward itself now answers the end page's 0x212E/0x2124 requests)
        "reward_after_scorecard": False,
        "reward_at_match_end": False,        # also send the 0x2125 in the world (it is lost there)
        "reward_with_banners": True,         # 0x2125 right after the 0x211F answer too
        "car_back_shift": -0.8,              # cars 2 and 3 moved this much towards their rear (m); 22:35: -0.8 (from +0.8, 1.6 m the other way)
        # the in-world VICTORY: an announcement (notice 0x100002EB
        # ShowAnnouncement: [text, a, b, c, d, e, flag]; [] = none), the
        # objective banner (victory_banner, "" = none) and, optionally, a
        # timeline banner (notices 0x100002AF / 0x100002B1 / 0x10000424)
        # [text, billboard type (9 MatchWin / 11 Team1Victory: the big box; 2 the
        # strip), b, c, source team, target team, flag]
        "victory_announcement": ["VICTORY", 9, 0, 0, 1, 1, 0],
        "send_match_ended_event": True,      # 0x2038 with the VICTORY (UI event MatchEnded)
        # the scorecard's data (icserver/scorecard.py) with the match end, and
        # again these many seconds later (after the post-match movie)
        "send_scorecard": True,
        # training achievements: their progress at login and, at the end of a
        # tutorial, "newly complete" + its reward (Champion Unlocked)
        "send_achievements": True,
        "scorecard_resend": [5.0, 25.0, 60.0],
        "reward_ribbon_icon": 0,             # 0x2095 "upgrade unlocked" ribbon icon DID (0 = none)
        "victory_banner": "",
        "victory_timeline_banner": False,
        # The reward panels at home ("Champion Unlocked" Gaslight Batman, then
        # "Mission Complete"): Batman's item turns owned (0x20B8 again) and a
        # ribbon "item fulfilled" (0x2095) at the end of the match. With
        # replay_champion_unlock he is shown as not owned when the tutorial
        # starts, so the panel comes every time.
        "reward_champion": 0x40000086,       # 0 = no reward
        "reward_text": "Gaslight Batman",    # the ribbon's text
        "replay_champion_unlock": True,
        "replay_post_match_movie": True,     # reset User.HasSeenPostEncounterVideo@<encounter> (0x216A) each time
        "exit_lobby_delay": -1.0,            # >= 0: also send 0x2021 this long after the notice
        "sphere_wstate": 0x2E000AC5,         # the sphere that falls before the Destroyer's cinematic (0 = none)
        "sphere_fall_seconds": 2.0,
        "sphere_from_height": 15.0,
        "camera_lock_wait": 10.0,
        "r_cooldown": 10.0,
        # The passive (Echoes) is ranked automatically after this many seconds if
        # its "+" does not arrive (0 = wait for the click).
        "passive_auto_seconds": 30.0,
        # Ranged drones shoot from this far (m); their attack scripts
        # ([] = the melee drones' ones).
        "ranged_attack_range": 6.0,
        "ranged_attack_keys": [],
        # Batman heals this much per second out of combat; below 25 % the
        # Construct heals him at once (he never dies in the tutorial).
        "regen_per_second": 8.0,
    },
    "combat": {
        "use_variants": True,          # drones as character variants (vitals, attackable)
        "enemy_team": 2,
        "drone_health": 200,
        "basic_attack_damage": 45,
        "attack_interval": 1.0,        # seconds between basic attacks
        "attack_range": 2.5,
        "corpse_seconds": 3.0,         # dead drone removed after this
        "spawn_scenery": True,
        # Movement module for props (bare world states: vehicle, meteors).
        # Without the module part (flag 0x20) the client never places an object
        # (old project's notes; diag 2026-10-14: the Door, sent with [1, 1], is
        # placed). "none" or [sequence, type] (types 1 = character replay, 2, 3, 9).
        "scenery_module": [1, 1],
        # Create props as their entity 0x40... (found in the packs at server
        # start: twin 0x49... property 0x510 = world state). false = old way.
        "prop_entities": True,
        # Cell of the position sent for props. Every placement in the encounter
        # layout (landblock 0x13cb) has cell 251; the server sent 0 (2026-10-14).
        "scenery_cell": 251,
        # World states with no entity of their own (vehicle, meteor) are created
        # as this entity (the Door, which the client does place: diag 2026-10-14)
        # with property 0x510 = the world state. 0 = create the bare world state
        # (never placed by the client: no physics placement in the diag).
        # 2026-10-14: the vehicle sent as the Door WAS placed at its spot but
        # stayed invisible (the Door has no model; 0x510 does not swap it). Off.
        "prop_carrier": 0,
        # 2026-10-14: the client only builds an object from an ENTITY (0x40...)
        # and takes its world state from it; the vehicle and meteor world states
        # have none. With the patched exe, class 0x4F + the world state's low
        # bits builds the Door entity with that world state. false = off.
        # 2026-10-14 15:17 (diag): sent as its bare world state (0x2E000AAB) the
        # vehicle builds without errors (.entity 0x2D0008BC, type 4), the meteors
        # too (0x2D000656); through the carriers it failed. So off by default.
        # 2026-10-14 15:35: bare world state = model built but never placed; the
        # carriers are placed. Cave Z (`ic.py patch` again) gives the carrier the
        # world state's model, so back on.
        "prop_override": True,
        # Carrier entities of the patched exe (class prefix 0x4A + index; needs
        # `ic.py patch` again when changed). Door 0x40000B0F failed at component
        # creation (diag 2026-10-14 11:36); the others come from `ic.py carriers`
        # (0x40000289: same creation type 0x50F = 5 as the vehicle; the rest are
        # entities of the loaded tutorial packs).
        # Skill cooldowns per client slot (1 = Q ... 4 = R), seconds; empty = the
        # kit's values (icserver/abilities.py). The client shows them on the buttons
        # (event 0x20F8); a skill on cooldown is not cast.
        "cooldowns": {},
        "enforce_cooldowns": True,
        # Batman stops where he casts Q / W and stays this long (s) so the cast
        # shows; R uses r_root (1.0 s)
        "cast_root": 0.35,
        # W (Sonic Shell) and E (Bat Flight), icserver/batman.py: damage, range,
        # projectile / flight speed (m/s) and radius of the hit.
        "w_damage": 120, "w_range": 11.0, "w_speed": 14.0, "w_radius": 3.0,
        "e_damage": 100, "e_range": 9.0, "e_speed": 14.0, "e_radius": 3.0,
        "r_damage": 400, "r_range": 60.0, "r_width": 4.0, "r_speed": 40.0, "r_duration": 1.2,
        "prop_carriers": [0x40000B0F, 0x400004FD, 0x400001BD, 0x4000081B, 0x40000B0A, 0x40000092],
        "prop_carrier_slot": 0,            # the carrier used for the vehicle and meteors
        # Test: also spawn the vehicle with the other 5 carriers (same spot) and
        # cycle the meteors through them.
        "prop_try_all_carriers": False,    # all 6 failed (2026-10-14 13:04)
        # Areas Batman cannot walk into: the server moves him itself, so the
        # map's own collisions do not apply. Each entry is [name, [[x, y], ...]]
        # (a polygon: the line Batman's centre cannot cross) or [name, x, y,
        # half length, half width, yaw] (a box, grown by his radius). The two
        # polygons follow the clicks the client snapped to the edge of the
        # walkable area in every log so far (2026-10-14): "Wagon" = the parked
        # wagon plus the pile of boxes in front of it, "SouthWall" = the wall
        # and the building south of them.
        "vehicle_blocks": True,
        "vehicle_box": [4.0, 1.6],
        "obstacles": [
            # the parked wagon plus the pile of boxes in front of it
            ["Wagon", [[28.85, 55.5], [33.45, 55.5], [33.3, 58.35], [34.3, 58.5], [34.9, 58.65], [35.4, 58.85], [36.0, 59.15], [36.55, 59.4], [37.0, 59.75], [37.25, 60.5], [37.1, 61.5], [36.65, 62.3], [35.6, 62.45], [34.4, 62.0], [33.3, 61.75], [32.3, 61.5], [31.2, 61.2], [30.0, 60.9], [28.85, 60.4], [28.75, 59.6], [28.75, 58.3], [29.0, 57.65]]],
            # the wall and building south of the wagon
            ["SouthWall", [[25.5, 56.55], [28.75, 56.6], [33.45, 56.0], [34.6, 55.6], [35.2, 54.95], [35.7, 54.2], [36.05, 53.0], [36.0, -10], [25.5, -10]]],
            # the building east of the square (2026-10-14 14:55)
            ["EastBuilding", [[45.3, 170], [45.3, 52.6], [45.75, 52.0], [53.15, 52.0], [53.3, 51.3], [170, 51.3], [170, 170]]],
            # the boxes and debris at the end of the street (2026-10-14 13:55)
            ["Boxes2", [[35.9, 52.95], [40.7, 52.85], [41.6, 52.2], [42.05, 51.4], [41.6, 50.4], [41.0, 49.2], [40.3, 48.3], [35.9, 48.3]]],
            # the north edge of the square (clicks stop at y 64.1)
            ["NorthWall", [[-10, 64.3], [170, 64.3], [170, 170], [-10, 170]]],
            # south side of the street past the vehicle
            ["SouthStreet", [[35.9, 48.3], [40.3, 48.3], [40.65, 48.35], [42.2, 46.5], [45.5, 44.85], [52.0, 43.55], [57.7, 41.45], [60.0, 39.0], [64.3, 36.1], [68.7, 34.4], [72.4, 32.5], [75.4, 31.7], [79.4, 30.0], [82.0, 28.5], [89.2, 25.6], [89.2, -10], [35.9, -10]]],
        ],
        # Manual override: {"0x2E000AAB" = 0x40000xxx}
        "prop_classes": {},
        # A right-click on the ground this close to an enemy counts as attacking
        # it (the client does not let you target the drones yet); attack-move (A)
        # picks the nearest enemy within the larger radius.
        "click_attack_radius": 1.6,        # the 2nd marker is 2 m from the drone
        "attack_move_radius": 8.0,         # vehicle and drone gates of the first area
    },
    "scripts": {
        # Event 0x8D runs a script on an entity. The id is NOT the scriptlet DID
        # (0x34...): the client only accepts names from the entity's script tables
        # (class property 0x7D2 -> records 0x1d...; diag 2026-10-13 rejected
        # 0x34000037 with 0x80070057). Names from shared table 0x1d0001f6:
        # Each hit uses the next entry (an id or a list of ids run together):
        # Combat_Basic_Attack_Right + Vfx_Bmg_Basic_Ranged_Right, then the Left pair.
        # [] = off. (2026-10-13: the Combat_Basic_Attack_* names start: Batman moves.)
        "basic_attack_keys": [[0x10000195, 0x10000188], [0x10000196, 0x10000189]],
        # Give the attack scripts the target (script variable 0x108) so the shot
        # flies at the drone instead of straight ahead.
        "send_target": True,
        # Pistol shots: where they reach the drone (distance / shot_speed) the shot
        # is ended (Vfx_Bmg_Basic_Stop) and the hit effect plays (Vfx_Bmg_Basic_Hit)
        "shot_speed": 20.0,
        "shot_stop_keys": [0x10000170],
        "shot_hit_keys": [0x10000187],
        # Run on the drone that is hit: VFX_CBT_Hit_Shared + _HFSM_TargetHitAction_PhysicalReaction.
        # [] = off.
        "hit_keys": [0x10000223, 0x10000209],
        # Run on a drone when it dies: _Defeat_OnDead (CbtState_Death_Induce is not
        # in the drones' table). [] = off.
        "death_keys": [0x100001FA],
        # Scriptlets on the champion go this many seconds after the messages of
        # the same moment (a champion bundle sent after them cut the animation).
        "champion_defer": 0.06,
        # Who "started" the script (u64; 0 = the server). The client skips the
        # order if this equals its own local id, because it already predicted it.
        "originator": 0,
    },
    "scriptvm": {
        # 2026-10-21 (fase3-fn): run Q (Sonic Batarang) from the game's own server scripts (0x3400003B, missile
        # 0x3400003F, decoded into data\script_trees by tools\script_decoder.py) instead of tutorial1.batarang.
        # Off until tested in game; the hand-written Q stays the fallback (also used when the trees are missing).
        "batarang": False,
        # Seconds from the cast animation start to the release (the scripts wait for the "cast point" result 5,
        # which the original server got from the animation; no data for it yet).
        "cast_point": 0.25,
        # The missile is simulated on the server (no client object): these scriptlets on Batman show it,
        # as the hand-written Q did (Vfx_Bmg_Batarang at the launch, Vfx_Bmg_Batarang_Stop at the end).
        "missile_vfx": {"0x40000090": [0x10000171]},
        "missile_stop_vfx": {"0x40000090": [0x1000017B]},
        # On each hit, on the target (VFX_CBT_Hit_Shared + physical reaction); the missile script only plays
        # the hit effect on props.
        "hit_keys": [0x10000223, 0x10000209],
        # Will is not tracked by the server yet: the scripts' Spend is logged only.
        # Log every state change of the scripts in server.log.
        "trace": True,
    },
    "debug": {
        "hexdump": True,              # full hex dumps in logs\traffic.log
        "dev_send_file": True,         # logs\send.txt: "<player|svc|hexid> <event hex> <body hex>"
        "old_server_dir": "",          # optional: an earlier _server folder whose tracer.py replaces tools\tracer.py
        # Batman action tour: once the tutorial starts, play these scriptlet keys
        # on Batman one by one (server.log names each one). "all" = the keys of
        # data/batman_actions.tsv (see docs/batman_actions.md); "core" = a short list
        # of the actions that matter for Batman's kit (old spelling "nucleo" also
        # accepted); [] = off.
        "tour_keys": [],
        "tour_interval": 3.0,
        "tour_start": 6.0,
    },
}


def _merge(base, extra):
    for key, value in extra.items():
        if isinstance(value, dict) and isinstance(base.get(key), dict):
            _merge(base[key], value)
        else:
            base[key] = value
    return base


class Config:
    def __init__(self, data, path=None):
        self.data = data
        self.path = path

    def __getitem__(self, section):
        return self.data[section]

    def resolve(self, relpath):
        """Paths in the config are relative to the folder of ic.py."""
        if not relpath:
            return relpath
        return relpath if os.path.isabs(relpath) else os.path.join(ROOT, relpath)

    @property
    def game_dir(self):
        return self.data["game"]["dir"]

    def game_file(self, name):
        return os.path.join(self.game_dir, name)

    @property
    def key_path(self):
        return self.resolve(self.data["server"]["key"])

    @property
    def log_dir(self):
        return os.path.join(ROOT, "logs")

    def champions_path(self):
        explicit = self.data["server"].get("champions_json")
        candidates = [self.resolve(explicit)] if explicit else []
        candidates += [os.path.join(ROOT, "data", "champions.json")]
        for c in candidates:
            if c and os.path.isfile(c):
                return c
        return None


def load(path=None):
    path = path or os.path.join(ROOT, "config.toml")
    data = copy.deepcopy(DEFAULTS)
    if os.path.isfile(path):
        if tomllib is None:
            raise RuntimeError("Python 3.11 or newer is required (tomllib)")
        with open(path, "rb") as f:
            _merge(data, tomllib.load(f))
    return Config(data, path if os.path.isfile(path) else None)
