"""Message builders (byte layouts of the client protocol; every value comes in as an argument).

Copied from icserver/messages.py, protocol formats only; the client addresses in the docstrings are where each
layout can be checked in InfiniteCrisis.exe.
"""
import math
import struct

from .wire import (KIND_BOOL, KIND_DID, KIND_ENUM, KIND_IID, KIND_INT, KIND_STRING, KIND_F32,
                   build_batch, build_frame, build_message, build_position, facing_yaw,
                   pack_compact, property_table, string_any, string_info, wstring)

# ---- ids ---------------------------------------------------------------------
SVC_PLAYER_SYSTEM = 0x0600000000000403     # client player/character system (rva 0x2a8090)
LOCAL_PLAYER_ID = 0x0200000000000001       # top byte 2 = player object
CHAMPION_AGENT_ID = 0x0200000000000002     # the champion the player controls
PING_OBJECT_ID = 0x0200000000000030        # guide pings: + step
PLAYER_PING_BASE_ID = 0x0200000000000040   # player pings: + n % 0x20
MARKER_OBJECT_ID = 0x0200000000000060      # visible tutorial markers: + step

PROP_CONTROLLED_AGENT = 0x100000CF
PROP_PLAYER_ENTITY_LINK_2 = 0x100005E8

EVT_SET_LOCAL_PLAYER = 0xEB
EVT_ACCOUNT_CHARACTER_SET = 0xCE
EVT_MASTER_CHARACTER_LIST = 0x209D
EVT_DELIVER_ENCOUNTER_INFO = 0x2024
EVT_CHAMPION_DATA = 0x20ED

EMPTY_TABLE_EVENT = b"\x00" + b"\x00" + b"\x00"   # u8 base | empty table
NONE32 = 0xFFFFFFFF

ENCOUNTERS = [
    (0x4000013E, "Gotham Heights"),
    (0x40000270, "Coast City"),
    (0x4000039C, "Crisis Labs: Coast City Variant"),
    (0x40000399, "Gotham Divided"),
    (0x40000E68, "Crime Alley Clash: 1v1"),
    (0x40000E74, "Crime Alley Clash: 2v2"),
    (0x40000EC0, "Apokolips Causeway Clash: 1v1"),
    (0x40000C28, "Metropolis Skyway"),
    (0x40000C82, "Crime Alley v AI"),
    (0x40000B6C, "Gotham Heights v AI"),
    (0x40000B6A, "Coast City v AI"),
    (0x40000B6B, "Gotham Divided v AI"),
    (0x40000991, "Tutorial -- Basic"),
    (0x40000A81, "Tutorial -- Intermediate"),
    (0x40000CA6, "Crime Alley: 1vAI Tutorial"),
]


# ---- connection-level packets ------------------------------------------------------

def hello_reply(now):
    """0x40000 welcome (builder rva 0x705070, handler 0xbe4950): 16-byte route
    id | BE f64 server time | 8 | u32 | BE u32 | BE u32 connection id."""
    pkt = (bytes(16) + struct.pack(">d", now) + bytes(8)
           + struct.pack("<I", 0) + struct.pack(">II", 1, 1))
    return build_frame(0x00040000, pkt)


def time_packet(now):
    """Packet 0x01000000: BE f64 time (keepalive; base dispatcher 0x703cc0)."""
    return build_frame(0x01000000, struct.pack(">d", now))


def server_switch(sequence=1):
    """Packet 0x100 ServerSwitch (handler 0xbe2080): makes the game connection
    the current one; without it the client drops it once match data loads."""
    return build_frame(0x00000100, struct.pack("<I", sequence))


def referral(host, port, cookie=1):
    """Packet 0x800 Referral (handler 0x2a8890 -> 0xbe3240): u64 cookie | u16 |
    u8 flags | u8 | u16 port | char[256] host."""
    pkt = struct.pack("<QHBBH", cookie, 0, 0, 0, port) + host.encode().ljust(256, b"\x00")
    return build_frame(0x00000800, pkt)


# ---- account / menus -------------------------------------------------------------

def character_set(player_name, player_id=LOCAL_PLAYER_ID):
    """0xCE account character set (serializer rva 0x45310), one entry."""
    empty_table = b"\x00" + pack_compact(0)
    entry = (struct.pack("<QQ", player_id, 0) + wstring(player_name)
             + struct.pack("<I", 0) + empty_table + empty_table)
    return b"\x00" + struct.pack("<I", 1) + entry + empty_table


def _ownable(did, content_type, status=2, owned=1):
    return struct.pack("<IIIBI", did, status, content_type, owned, 1)


def _champion_items(c, locked=()):
    owned = 0 if c["variant"] in locked else 1
    return ([_ownable(c["variant"], 1, owned=owned)] + [_ownable(s["variant"], 4) for s in c["costume_info"]]
            + [_ownable(c["skills_key"], 4, status=5, owned=0)])


def _item_statuses_body(roster, locked=()):
    items = [i for c in roster for i in _champion_items(c, locked)]
    return bytes([0]) + struct.pack("<I", len(items)) + b"".join(items)


def set_local_player(player_id=None):
    """0xEB: u8 0 | u64 local player id | u8 0 | compact 0 (sent at login; again
    before each later match: the client's world teardown resets it to 0)."""
    pid = LOCAL_PLAYER_ID if player_id is None else player_id
    return build_message(SVC_PLAYER_SYSTEM, EVT_SET_LOCAL_PLAYER,
                         b"\x00" + struct.pack("<Q", pid) + b"\x00" + pack_compact(0))


def item_statuses(roster, locked=()):
    """0x20B8 item statuses again (handler 0xa88030: from the second delivery
    on, only the changed items go to Flash as Incremental_ItemStatuses).
    locked = champion variants sent as not owned."""
    return build_message(SVC_PLAYER_SYSTEM, 0x20B8, _item_statuses_body(roster, locked))


def item_fulfilled(key, item_did, text=""):
    """0x2095 ribbon "item fulfilled" (serializer 0x83f410, handler 0x8aaf60 ->
    0xa7ea00): u8 0 | u32 key | u32 icon DID | StringInfo name. 0xa7ea00 queues (key, icon, name) in a map keyed by
    the first u32 (0xa746b0) and 0xa26b50 hands each entry to 0x88f040(icon, &name), which raises
    RecvNotice_Ribbon_ItemFulfilled(i_didIcon, i_siName) -> WrapperMain's UpgradeUnlockRibbon (store-fix.md 7.2, C).
    The second argument is therefore an icon (0x13...) DID, not the item's DID."""
    return build_message(SVC_PLAYER_SYSTEM, 0x2095,
                         b"\x00" + struct.pack("<II", key, item_did) + string_info(text))


# 2026-10-25 (match-load-sequence.md, C: LoadMatchData's pack list is field f0 of each 0x20ED entry plus 0x20AF; a
# 0xFFFFFFFF in it keeps the "all present" shortcut from firing and the request retries forever; the slot portrait is
# f9, 0 for every costume): set by the server from [ics] champion_data_match_pack / champion_data_costume_icon
CHAMPION_DATA_MATCH_PACK = [True]
CHAMPION_DATA_COSTUME_ICON = [True]


def _meta_entry(variant, parent_pack, heavy_pack, light_pack, wallpaper_pack, heavy_dbpc, light_dbpc,
                powerset_dbpc, icon, name):
    f0 = parent_pack if CHAMPION_DATA_MATCH_PACK[0] and parent_pack not in (0, NONE32) else NONE32
    return (struct.pack("<I", variant)
            + struct.pack("<8I", f0, parent_pack, heavy_pack, light_pack, wallpaper_pack,
                          heavy_dbpc, light_dbpc, powerset_dbpc)
            + bytes([1]) + struct.pack("<I", icon)
            + bytes([1]) + wstring(name) + bytes([0]) + pack_compact(0))


def _setting(name, value):
    return (pack_compact(len(name)) + name.encode() + struct.pack(">H", 9)
            + struct.pack("<I", len(value)) + value.encode())


CATEGORY_TUTORIAL = 4

# The 0x2024 / 0x20FF per-encounter flag word = the queue types the encounter offers; the same bits the client puts in
# its QueueKey (0x86E060): 0x200000 blind pick / solo, 0x20000 draft, 0x10000 ranked (0x30000 = ranked draft), 0x100000
# added by the client for category 4 (tutorial). The play menu's query 0xA68030 reads bit 21 -> aPVPBlindPickEnabled,
# bit 17 -> aPVPDraftEnabled, bit 16 -> aPVPRankedEnabled; with none set the map tile says "Queues are currently
# unavailable" (EncounterDataObject.IsNoQueuesAvailable) (C, 2026-10-22).
QUEUE_BLIND = 0x200000
QUEUE_DRAFT = 0x20000
QUEUE_RANKED = 0x10000
DEFAULT_QUEUE_FLAGS = {0: QUEUE_BLIND | QUEUE_DRAFT, 1: QUEUE_BLIND | QUEUE_DRAFT, 2: QUEUE_BLIND | QUEUE_DRAFT,
                       3: QUEUE_BLIND | QUEUE_DRAFT, CATEGORY_TUTORIAL: 0}


def _encounter_lists(enc_list, queue_flags=None):
    """The four per-encounter lists of 0x2024 / 0x20FF (serializer 0x846D40, handler 0xA733B0 -> encounter
    manager [0xA12D50()+0x68]): list<u32> DIDs (+0x04) | list<u32> queue flags (+0x14) | u32 n x string (cint
    length + chars) access filter (+0x34: empty = every player, else compared with the account's access strings
    by 0x86FD90) | list<u32> (+0x24, zeros)."""
    flags = dict(DEFAULT_QUEUE_FLAGS)
    flags.update(queue_flags or {})
    n = len(enc_list)
    return (_u32s(n, *[e for e, _ in enc_list])
            + _u32s(n, *[flags.get(cat, flags[0]) for _, cat in enc_list])
            + _u32s(n) + b"\x00" * n
            + _u32s(n, *([0] * n)))


def encounter_update(enc_list, queue_flags=None):
    """0x20FF UpdateEncounterInfo (exec 0x8B5610, handler 0xA734D0): the four lists of 0x2024 again. The client
    replaces its encounter list (only after a 0x2024) and raises Encounter.ResetMapSelectionList, so the Flash
    EncounterManager queries the encounters again (GM_Encounter.InqPVPEncounters = 0xA68030)."""
    return _player_msg(0x20FF, _encounter_lists(enc_list, queue_flags))


def queue_eligibility(level, owned_champions, encounters, ranked_min_level=0, draft_requirement=0):
    """0x2101 queue eligibility (serializer 0x845AC0, exec 0x8BABA0, handler 0xA740D0 -> 0xA6AFA0 on the
    singleton 0xA37BF0): u8 0 | u32 account level | u32 ranked capacity | list<u32> encounters (+0x1F8) |
    list<u32> per-encounter values (+0x208, same length: the client overwrites them with 0xA292F0(encounter)) |
    u32 ranked minimum level | u32 draft requirement. Per encounter: ranked eligible = 0x10000BCC (players) +
    [0x1866B8C] <= capacity, draft eligible = requirement <= value, meets level = minimum <= level; then
    UI.QueueEligibility (0xA5CD00) to EncounterManager.UpdateEncounterDataQueueEligibility (C, 2026-10-22)."""
    encounters = list(encounters)
    return _player_msg(0x2101, _u32s(level, owned_champions) + _u32list(encounters) + _u32list([0] * len(encounters))
                       + _u32s(ranked_min_level, draft_requirement))


def initial_events(roster, account_level, player_name, encounters=None, queue_flags=None):
    """Everything the client needs between login and the landing screen.
    ORDER MATTERS (see the old server's comments): 0x20b8 + 0x20ED before
    0x209D, and 0x2080 last (it opens the landing-screen gate)."""
    set_player = b"\x00" + struct.pack("<Q", LOCAL_PLAYER_ID) + b"\x00" + pack_compact(0)
    champions = [(c["variant"], 1, 0, 100, 0, 0) for c in roster]
    item_statuses = _item_statuses_body(roster)
    char_list = (b"\x00" + b"\x00" + pack_compact(len(champions))
                 + b"".join(struct.pack("<IIIIQQ", *c) for c in champions))
    groups = b""
    for c in roster:
        members = _champion_items(c)
        groups += struct.pack("<I", len(members)) + b"".join(members)
    meta, n_meta = b"", 0
    for c in roster:
        meta += _meta_entry(c["variant"], c["parent_pack"], c["heavy_pack"], c["light_pack"], c["wallpaper_pack"],
                            c["pregame_heavy"], c["id"], c["heavy_dbpc"], c["grid_icon"], c["name"])
        n_meta += 1
        for s in c["costume_info"]:
            meta += _meta_entry(s["variant"], c["parent_pack"], s["heavy_pack"], s["light_pack"],
                                s["wallpaper_pack"], s["pregame_heavy"], s["light"], s["heavy_dbpc"],
                                (s.get("grid_icon") or c["grid_icon"]) if CHAMPION_DATA_COSTUME_ICON[0] else 0,
                                c["name"])
            n_meta += 1
        meta += _meta_entry(c["skills_key"], NONE32, NONE32, c["skills_pack"], NONE32, 0, 0, 0, 0, c["name"])
        n_meta += 1
    champ_data = (bytes([0]) + struct.pack("<I", len(roster)) + groups
                  + bytes([0]) + pack_compact(n_meta) + meta)
    # encounters: [(DID, category)] from the data (Data.encounter_list), else the fixed list
    enc_list = encounters or [(e, CATEGORY_TUTORIAL if "Tutorial" in name else 0) for e, name in ENCOUNTERS]
    # the four lists (_encounter_lists), then u32 (+0x70) | access strings (u32 n x string: [+0x54]+0x18C, matched
    # against the per-encounter filters) | u8 ([0x1B77138]+0xAF) | wstr (+0x1FC) | wstr (+0x200) | u64 (+0x208)
    encounters = (b"\x00"
                  + _encounter_lists(enc_list, queue_flags)
                  + struct.pack("<I", 0)
                  + struct.pack("<I", 0) + b"\x00" + pack_compact(0) + pack_compact(0)
                  + struct.pack("<Q", 0))
    settings = [_setting("FeaturedMap_PVP", "0x40000399"), _setting("FeaturedMap_BOTS", "0x40000B6A")]
    game_settings = b"\x00" + pack_compact(len(settings)) + b"".join(settings)
    svc = SVC_PLAYER_SYSTEM
    return [
        ("set local player (0xeb)", build_message(svc, EVT_SET_LOCAL_PLAYER, set_player)),
        ("item statuses (0x20b8)", build_message(svc, 0x20B8, item_statuses)),
        ("champion data (0x20ed)", build_message(svc, EVT_CHAMPION_DATA, champ_data)),
        ("character list (0x209d)", build_message(svc, EVT_MASTER_CHARACTER_LIST, char_list)),
        ("encounter info (0x2024)", build_message(svc, EVT_DELIVER_ENCOUNTER_INFO, encounters)),
        ("server options (0x216a)", build_message(svc, 0x216A, EMPTY_TABLE_EVENT)),
        ("achievements (0x2120)", build_message(svc, 0x2120, EMPTY_TABLE_EVENT + struct.pack("<I", 0))),
        ("account tables (0x218b)", build_message(svc, 0x218B, EMPTY_TABLE_EVENT + game_settings)),
        ("account flags (0x215d)", build_message(svc, 0x215D, b"\x00" + struct.pack("<I", 1) + b"\x00")),
        ("account character set (0xce)", build_message(svc, EVT_ACCOUNT_CHARACTER_SET,
                                                       character_set(player_name))),
        ("account level (0x2080)", build_message(
            svc, 0x2080, b"\x00" + struct.pack("<6I2f", account_level, account_level, 0, 100, 0, 0, 0.0, 0.0))),
    ]


# ---- queue / lobby / match entry -----------------------------------------------------

def joined_queue(did, qflags):
    return build_message(SVC_PLAYER_SYSTEM, 0x20C0, b"\x00" + struct.pack("<IIffI", did, qflags, 0.0, 0.0, 0))


def match_found(max_players=1, timeout=30):
    return build_message(SVC_PLAYER_SYSTEM, 0x20FA, b"\x00" + struct.pack("<II", max_players, timeout))


def players_accepted(n=1):
    return build_message(SVC_PLAYER_SYSTEM, 0x20AD, b"\x00" + struct.pack("<I", n))


def lobby_room_created(did, qflags):
    return build_message(SVC_PLAYER_SYSTEM, 0x2028, b"\x00" + struct.pack("<IIII", did, qflags, 0, 0))


def lobby_player(champion, name, team, room_id, player_id=LOCAL_PLAYER_ID):
    """0x2029 one lobby slot (serializer rva 0x4479b0)."""
    s = b"\x00"
    tail = (struct.pack("<IQI", 0, 0, 0) + string_info("") + pack_compact(0)
            + struct.pack("<I", 0) + pack_compact(1) + struct.pack("<I", champion))
    body = (b"\x00" + s
            + struct.pack("<IIQ", team, 0, player_id) + string_info(name)
            + b"\x00" + struct.pack("<II", champion, 0) + b"\x00"
            + struct.pack("<II", room_id, 1) + struct.pack("<7I", *([0] * 7))
            + tail)
    return build_message(SVC_PLAYER_SYSTEM, 0x2029, body)


def lobby_state(did, qflags, champion, room_id):
    """0x204C lobby state (serializer rva 0x445810)."""
    owned = struct.pack("<IIIBI", champion, 2, 1, 1, 1)
    body = (b"\x00" + struct.pack("<II", 0, 0) + struct.pack("<II", did, qflags)
            + struct.pack("<QII", 0, 0, room_id)
            + struct.pack("<I", 1) + owned
            + struct.pack("<II", 1, champion)
            + b"\x00\x00")
    return build_message(SVC_PLAYER_SYSTEM, 0x204C, body)


def end_room_check(room_id):
    return build_message(SVC_PLAYER_SYSTEM, 0x2016, b"\x00" + struct.pack("<I", room_id))


def all_loaded(room_id):
    return build_message(SVC_PLAYER_SYSTEM, 0x206D, b"\x00" + struct.pack("<I", room_id))


def match_start():
    return build_message(SVC_PLAYER_SYSTEM, 0x2053, b"\x00" + struct.pack("<III", 0, 0, 0))


def loading_percents(entries, room_id):
    """0x2031 for several slots: entries = [(team, index, percent)] (handler 0xab8730 -> 0x8eed40, display only)."""
    body = b"\x00"
    for k in range(3):
        body += struct.pack("<I", len(entries)) + b"".join(struct.pack("<I", e[k]) for e in entries)
    return build_message(SVC_PLAYER_SYSTEM, 0x2031, body + struct.pack("<I", room_id))


def loading_percent(team, percent, room_id):
    body = (b"\x00" + struct.pack("<II", 1, team) + struct.pack("<II", 1, 0)
            + struct.pack("<II", 1, percent) + struct.pack("<I", room_id))
    return build_message(SVC_PLAYER_SYSTEM, 0x2031, body)


def enter_match(encounter_did, champion, packs, extra_champions=()):
    """0x20AF (handler 0x699f00): u8 base | u32 | u32 n + champion DIDs |
    u32 n + pack ids | u32 encounter DID. The champion list is every champion
    whose data the match needs (extra ones: cinematic actors such as Catwoman)."""
    champs = [champion] + [c for c in extra_champions if c != champion]
    body = (b"\x00" + struct.pack("<I", 0)
            + struct.pack("<I", len(champs)) + b"".join(struct.pack("<I", c) for c in champs)
            + struct.pack("<I", len(packs)) + b"".join(struct.pack("<I", p) for p in packs)
            + struct.pack("<I", encounter_did))
    return build_message(SVC_PLAYER_SYSTEM, 0x20AF, body)


# ---- world objects ----------------------------------------------------------------

DESCRIPTOR_WS_ZERO = [True]          # [ics] descriptor_world_state_zero (set by ics/server.py)


def create_object(object_id, class_id, now, sequence=1, position=None, heading=0.0, speed=0.0,
                  tele_seq=1, second_seq=0, module=(1, 1), iid_properties=None, properties=None,
                  unknown64=0, facing_offset=0.0, parent=None, pitch=None, roll=None, vel_pitch=None):
    """Object bundle = batch 0x4 to the object's id with 0xF2 descriptor,
    0xB0 position/motion and 0xBC properties (see the old server for every
    field). second_seq must be 0 until the client reports load complete
    (1 afterwards): the smooth movement branch crashes during loading."""
    # 2026-10-25 (skin-overlay-fix.md 3, C: the 0xF2 reader 0x445970 / 0x54BD00 puts this u32 at +0x28 and the handler
    # 0x64D8A0 compares it with entity+0x110, calling ChangeWorldState 0x54D5C0 when they differ): it is a world-state
    # override, not a sequence; the counter asked for a world-state switch on every bundle. DESCRIPTOR_WS_ZERO sends 0.
    descriptor = struct.pack("<IQI", class_id, unknown64, 0 if DESCRIPTOR_WS_ZERO[0] else sequence)
    if position:
        pos = movement_block(now, position, heading, speed, module, tele_seq, second_seq, facing_offset, parent,
                             pitch, roll, vel_pitch)
    else:
        pos = bytes([0]) + struct.pack("<H", 0)
    entries = [(pid, KIND_IID, iid) for pid, iid in (iid_properties or {}).items()] + list(properties or [])
    body = build_batch([(0xF2, descriptor), (0xB0, pos), (0xBC, property_table(entries))])
    return build_message(object_id, 0x4, body)


def movement_block(now, position, heading, speed, module=(1, 1), tele_seq=1, second_seq=0, facing_offset=0.0,
                   parent=None, pitch=None, roll=None, vel_pitch=None):
    """The 0xB0 movement state of an object bundle (create_object) and of a motion-only update (pvp_movement_state):
    the same bytes for the same arguments (client-movement.md 1.2; reader 0x57EE90, listener 0x60AFA0).
    2026-10-29 tester report 2026-10-29 17:45 (agl-arm-meteor-vehicle-tilt.md 3, C reader 0x57E530 / 0x60AFA0): pitch /
    roll (rad) = the motion bits 0x400 (facing pitch) / 0x4000 (roll), s16 rad * 10000 after the facing yaw; the client
    builds the model's orientation from (yaw, pitch, roll) (0xAF2D00). None = not sent (the bytes stay as before).
    2026-10-29 tester report 21:10 (liftable-aura-lift-throw-break.md 3, C reader 0x57E530 order heading 4 / speed 0x20 /
    0x40 / facing 8, velocity 0x57DA90 = (cos h cos p, sin h cos p, sin p) * speed): vel_pitch (rad) = motion bit 0x40,
    an f32 after the speed, the pitch of the replayed velocity, so the client dead-reckons a state up / down as well
    (a thrown object's curve). None = not sent."""
    region, lb_x, lb_y, cell, x, y, z = position
    if module:
        module_seq, module_type = module
        head = bytes([0x62, module_seq, module_type, 0x0F])
        if parent is not None:
            # 2026-10-26 (grab-arm-carry.md 2, C reader 0x57EE90 / listener 0x6113E0): flag 0x04 = attached to a
            # parent: u64 parent IID (0 = detach); if not 0, u32 mode and, for mode 0x10, {u32 attach point, u8, u8}
            # (P values: AttachEntity's literals 0x100000B0 0 1)
            iid, mode, point, b1, b2 = (list(parent) + [0, 0, 0, 0, 0])[:5]
            block = struct.pack("<Q", iid)
            if iid:
                block += struct.pack("<I", mode) + (struct.pack("<IBB", point, b1, b2) if mode == 0x10 else b"")
            head = bytes([0x62 | 0x04, module_seq, module_type]) + block + bytes([0x0F])
    else:
        # No movement module (flag 0x20 left out): for static props. The
        # module (type 1 = rigid-body CHARACTER replay) is what places a
        # character; props have no character physics and stayed invisible.
        head = bytes([0x42, 0x0F])
    hi, extra = 0x18, b""
    if pitch is not None:
        hi |= 0x04                  # 0x400: s16 facing pitch
        extra += struct.pack("<h", _s16_angle(pitch))
    if roll is not None:
        hi |= 0x40                  # 0x4000: s16 roll
        extra += struct.pack("<h", _s16_angle(roll))
    return (head
            + struct.pack("<d", now)
            + build_position(region, lb_x, lb_y, cell, x, y, z) + struct.pack("<H", 0)
            + bytes([0x80 | 0x2C | (0x40 if vel_pitch is not None else 0), hi]) + struct.pack("<ff", heading, speed)
            + (struct.pack("<f", float(vel_pitch)) if vel_pitch is not None else b"")
            + struct.pack("<h", int(round(facing_yaw(heading + facing_offset) * 10000.0)))
            + extra
            + bytes([tele_seq, second_seq]))


def _s16_angle(rad):
    """An angle as the motion block's s16 (rad * 10000), wrapped to [-pi, pi]."""
    a = (float(rad) + math.pi) % (2 * math.pi) - math.pi
    return max(-32767, min(32767, int(round(a * 10000.0))))


def advancement_handlers(leading_u8=True, blob4=False):
    """0x9F to the local player, message 0x81A1000B (class 0x1A1 method 11 -> player slot 198 -> 0x9654): registers the
    six GM_Advancement handlers, among them InqXPForLevel 0x10000011, which the HUD's XP ring asks for its thresholds
    (hud-xp-ring.md; C data, P framing): u8 0 | u32 message | u32 blob size | blob."""
    blob = struct.pack("<I", 0) if blob4 else b""
    body = (bytes(1) if leading_u8 else b"") + struct.pack("<II", 0x81A1000B, len(blob)) + blob
    return build_message(LOCAL_PLAYER_ID, 0x9F, body)


def destruction_reset(object_id):
    """0x8B to a destructible object: u8 0 | u64 IID (handler 0x631050). Rebuilds its intact pieces (0x6303F0, no
    creation-type check) and their bodies / render instances (0x630FC0): a creation type 8 destructible (Crime Alley's
    vehicles) gets no pieces from the client itself, so nothing draws (destructible-vehicles.md, C path, P result)."""
    return build_message(object_id, 0x8B, b"\x00" + struct.pack("<Q", object_id))


def remove_object(object_id):
    """Event 0x3 to the object: hidden at once, freed 30 s later."""
    return build_message(object_id, 0x3, bytes(1))


# 2026-10-25 (map-loading-deep-scan.md 3, C mechanism: 0x7E35C0 reads the player's 0x956 and looks it up in the region
# environment table 0x04000000): 0x10000016 -> 0x08000016 is the cinematic setup, 0x10000002 -> 0x08000003 Crime
# Alley's bluer outdoor one. Set per encounter by the session ([ics] lighting_env).
LIGHTING_ENV = [0x10000016]


def champion_properties(name, team, icon, level=1, xp=0, skill_points=1, move_speed=None, currency=0.0, alive=True,
                        player_iid=None, hud=True):
    """move_speed: property 0x100005E4 (movement speed; drones carry 3.0 in their
    world state, items +0.05..0.2). The client copies it into the motion
    component's walk-animation cap (+0x2d0); without it Batman's cap is 0 and he
    slides (diag.log 2026-10-13: drones 3.0, Batman 0.0). None = not sent."""
    extra = [] if move_speed is None else [(0x100005E4, KIND_F32, float(move_speed))]
    props = extra + [
        (0x10000064, KIND_IID, LOCAL_PLAYER_ID if player_iid is None else player_iid),   # agent -> player IID
        (0x00000956, KIND_ENUM, LIGHTING_ENV[0]),  # lighting environment (region table 0x04000000 key)
        (0x1000009C, KIND_INT, team),              # PVP_Team
        (0x100000FA, KIND_ENUM, 4 if alive else 2),   # LifeState: 4 Alive (else nameplate hidden), 2 Dead
        (0x10000167, KIND_INT, level),             # Level
        (0x10000142, KIND_INT, xp),                # XP
        (0x10000637, KIND_INT, 0),                 # 2026-10-26: the floaty-number viewer key's sub (deep-scan-s2c.md 1.3, P)
        (0x100001AF, KIND_INT, skill_points),      # SkillPoints
        (0x1000035E, KIND_F32, float(currency)),   # Upgrade_Currency (the HUD's credits)
        (0x000003CE, KIND_STRING, name),           # Name
        (0x10000433, KIND_STRING, name),           # Character_Name
        (0x10000384, KIND_DID, icon),              # Character_SmallIcon
        (0x10000338, KIND_DID, icon),              # portrait (guess)
        (0x10000337, KIND_DID, icon),              # large icon (guess)
    ]
    if not hud:
        # a champion the player does not control (a bot, bot-champions.md 1.2): no skill points or credits (only the
        # controlled agent's HUD reads them)
        props = [p for p in props if p[0] not in (0x100001AF, 0x1000035E)]
    return props


LIFE_ALIVE, LIFE_DEAD = 4, 2


def creature_properties(team, alive=True):
    """Drones / creatures: team (enemy = 2) and LifeState (nameplate needs Alive)."""
    return [(0x1000009C, KIND_INT, team),
            (0x100000FA, KIND_ENUM, LIFE_ALIVE if alive else LIFE_DEAD)]


def player_properties():
    return [(0x00000956, KIND_ENUM, LIGHTING_ENV[0])]          # lighting environment


PLAYER_PROPERTIES = player_properties()


def player_late_properties(encounter_did):
    """Only on re-sends: the map manager listens for a CHANGE of 0x100001d3."""
    return [(0x100001D3, KIND_DID, encounter_did)]


EVT_START_SCRIPTLETS = 0x8D
PROP_SCRIPT_TARGET = 0x108      # script variable: target instance id (u64)
PROP_SCRIPT_FX = 0x1000050A     # script variable: the FX template a scriptlet plays (Vfx_GuideArrow / _Ping)


def scriptlet_entry(did, instance, originator=0, packed=False, variables=None, second=0, signals=0):
    """One "run this scriptlet" order (list reader rva 0x12d4a0, entry stride 0x60).

      DID         u8 high byte | compact low 24 bits (rva 0xfeb20)
      instance    compact (rva 0x43f40). A new number starts a new run; a number
                  that is still running only gets signalled (rva 0x57b510).
      parameters  rva 0x2837e0:
                    run flags   u32 (u8 when the stream is packed, flag 0x800)
                    field mask  u8: 0x01 originator u64, 0x20 2nd iid u64,
                                0x02 variable table, 0x04 f32, 0x10 f32,
                                0x08 u32, 0x40 u32 (all left out here)
                    [0x01] originator u64: the client skips the order when it
                                equals its own local id (rva 0x2279d0)
                    start time  f64 (the client zeroes it, rva 0x227e7b)
      signals     bit set (rva 0x100750): compact bit count, then the bytes
    Packed = inside an object bundle (batch sub-events have no base byte and
    use the packed widths, see rva 0x70d380)."""
    out = bytes([did >> 24]) + pack_compact(did & 0xFFFFFF) + pack_compact(instance)
    out += bytes([0]) if packed else struct.pack("<I", 0)
    mask = (0x01 if originator else 0) | (0x02 if variables else 0) | (0x20 if second else 0)
    out += bytes([mask])
    if originator:
        out += struct.pack("<Q", originator)
    if second:
        out += struct.pack("<Q", second)      # [0x20] second instance id (the target object)
    if variables:
        # script variables = a property table (rva 0x109950 -> 0x103330); the
        # client's own skills put the target there as property 0x108 (rva 0x281269)
        out += property_table(variables)
    out += struct.pack("<d", 0.0)
    if signals:
        # 2026-10-23 23:30 (skill-second-stages.md 3, P): a live instance number with a signal set signals that run;
        # StopScriptletKey's client path signals 1 (0x57C4B0). Bit set = compact bit count, then the bytes.
        count = signals.bit_length()
        return out + pack_compact(count) + signals.to_bytes((count + 7) // 8, "little")
    return out + pack_compact(0)


def start_scriptlets(entity_id, entries, originator=0, variables=None, second=0, signals=0):
    """Event 0x8D to an entity (serializer rva 0x43c030, handler rva 0x234f20 ->
    the entity's script component +0x10): u8 base | compact count | entries.
    entries = [(scriptlet DID, instance number), ...]."""
    body = b"\x00" + pack_compact(len(entries)) + b"".join(
        scriptlet_entry(did, inst, originator, variables=variables, second=second, signals=signals)
        for did, inst in entries)
    return build_message(entity_id, EVT_START_SCRIPTLETS, body)


EVT_STOP_SCRIPTLET = 0x11F


def stop_scriptlet(entity_id, key, instance=0xFFFFFFFF, flag=0):
    """Event 0x11F (serializer 0x6751A0, exec 0x675280 -> 0x57C4B0 on the entity's script component): u8 0 | u32 key |
    u32 run instance (the 0x8D's own run number; 0xFFFFFFFF = every run of the key) | u8 flag (0 / 1). Stops the
    run(s): 0x529EF0 runs the end list and releases the attachments. A 0x8D signal only runs a definition's signal
    handlers (0x534290) and stops nothing by itself (docs/re-notes/death-animation.md 4)."""
    return build_message(entity_id, EVT_STOP_SCRIPTLET,
                         b"\x00" + struct.pack("<IIB", key & 0xFFFFFFFF, instance & 0xFFFFFFFF, 1 if flag else 0))


VITALS_FIRST_LIST = True    # 2026-10-14 (earlier server): in the second list the client said "not enough Will"
                            # for Q with 100/100 shown


def vitals(object_id, pairs, first=None):
    """0x42 (only to objects WITH a vitals component, else the client crashes).
    u8 0 | u8 n | n x (u16, u16) | u8 n | n x (u16 cur, u16 max) | u16 0. The HUD
    shows the sum of both lists. The values used to go in the second list only;
    with first=True they go in the first (2026-10-14: the client said "not
    enough Will" for Q with 100/100 shown, as if it read the first list)."""
    first = VITALS_FIRST_LIST if first is None else first
    data = b"".join(struct.pack("<HH", int(cur) & 0x7FFF, int(mx) & 0x7FFF) for cur, mx in pairs)
    zeros = bytes(len(data))
    a, b = (data, zeros) if first else (zeros, data)
    body = bytes([0, len(pairs)]) + a + bytes([len(pairs)]) + b + bytes([0, 0])
    return build_message(object_id, 0x42, body)


CINEMATIC_FLAG_BIND_CHECK = 0x2       # bit-1 field: the bindings must name the local champion (0xa9c610)


def cinematic(did, flags=None, bindings=(), hide_types=0):
    """0x20F5 (reader 0x878020): u8 0 | u32 mask | bit0 DID | bit1 u32 flags | bit2 u32 n + n x (u32 actor key,
    u64 IID) | bit3 u32 PerceivedType mask. Bindings: key 0 + the local champion's IID -> the client gives it key 1,
    the scene's "player" actor (actor variable 1) becomes a copy of the champion (docs/re-notes/
    client-cinematics-matchend.md 1.3). hide_types: while the cinematic plays, 0xa9c490 hides (property 0x90F)
    every world entity whose PerceivedType 0x1000019D & mask != 0 and shows it again at the end (Character = 8: the
    champion, so the scene's own Batman is the only one)."""
    mask, body = 0x1, struct.pack("<I", did)
    if flags is not None:
        mask |= 0x2
        body += struct.pack("<I", flags)
    if bindings:
        mask |= 0x4
        body += struct.pack("<I", len(bindings)) + b"".join(struct.pack("<IQ", k, iid) for k, iid in bindings)
    if hide_types:
        mask |= 0x8
        body += struct.pack("<I", hide_types)
    return build_message(LOCAL_PLAYER_ID, 0x20F5, bytes(1) + struct.pack("<I", mask) + body)


# ---- HUD / objectives / dialogue ---------------------------------------------------

# 0x213D events (emp_gen gmUIHUDElementEventList; MainHUD.RecvNotice_NotifyHUDElement)
HUD_SHOW, HUD_HIDE, HUD_HIGHLIGHT, HUD_HIGHLIGHT_OFF, HUD_ARROW_HIGHLIGHT = 1, 2, 7, 8, 9


def hud_element(element, event, highlight=0, highlight_did=0):
    return build_message(LOCAL_PLAYER_ID, 0x213D,
                         b"\x00" + struct.pack("<IIII", element, event, highlight, highlight_did))


def objective(objective_id, text=None, active=None, state=None, count=None, count_max=None,
              category=None, sort_order=None, optional=None, banner=None):
    flags, out = 0x20, struct.pack("<I", objective_id)
    if state is not None:
        flags |= 0x8000; out += struct.pack("<I", state)
    if category is not None:
        flags |= 0x01; out += struct.pack("<I", category)
    if text is not None:
        flags |= 0x80; out += string_any(text)
    if count is not None:
        flags |= 0x10; out += struct.pack("<I", count)
    if count_max is not None:
        flags |= 0x04; out += struct.pack("<I", count_max)
    if sort_order is not None:
        flags |= 0x4000; out += struct.pack("<I", sort_order)
    if active is not None:
        flags |= 0x80000; out += bytes([1 if active else 0])
    if optional is not None:
        flags |= 0x100; out += bytes([1 if optional else 0])
    if banner is not None:
        flags |= 0x1000000; out += string_any(banner)
    return struct.pack("<I", flags) + out


def objective_category(category_id, title, description="", sort_order=0, state=None, visible=True):
    flags, out = 0x01, struct.pack("<I", category_id)
    if state is not None:
        flags |= 0x08; out += struct.pack("<I", state)
    flags |= 0x10; out += string_any(title)
    flags |= 0x02; out += string_any(description or title)
    flags |= 0x04; out += struct.pack("<I", sort_order)
    flags |= 0x20; out += bytes([1 if visible else 0])
    return struct.pack("<I", flags) + out


def objective_list(objectives, categories=()):
    body = (b"\x00" + struct.pack("<I", len(objectives)) + b"".join(objectives)
            + struct.pack("<I", len(categories)) + b"".join(categories))
    return build_message(LOCAL_PLAYER_ID, 0x2034, body)


def objective_update(obj):
    objective_id = struct.unpack_from("<I", obj, 4)[0]
    return build_message(LOCAL_PLAYER_ID, 0x2009, b"\x00" + struct.pack("<I", objective_id) + obj)


_conversation_instances = iter(range(1, 1 << 31))


def next_conversation_instance():
    """A new conversation instance id (each 0x2001 of a match its own; [ics] conversation_instances)."""
    return next(_conversation_instances)


def announcer(event, source=0, target=0, team=0, other_team=0, channel=0, flag=1, dest=LOCAL_PLAYER_ID, extra=()):
    """0x2039 context dialog (exec 0x8b2040, handler 0xa7fe60 -> 0xa77da0): u8 0 | u32 flag | u32 channel |
    PropTable. With 0x10000806 = a match event, 0xa309d0 picks the line from the encounter's announcer set (template
    0x10000802, e.g. 0x40000D4C for Crime Alley, plus the shared 0x4000047A); 0x10000812 / 0x10000811 = source /
    target IID, 0x1000081D / 0x1000081C = teams. Which event is which is not in the client (tested by ear)."""
    from .wire import KIND_ENUM, KIND_IID, KIND_INT, property_table
    entries = [(0x10000806, KIND_ENUM, int(event))]
    if source:
        entries.append((0x10000812, KIND_IID, int(source)))
    if target:
        entries.append((0x10000811, KIND_IID, int(target)))
    if team:
        entries.append((0x1000081D, KIND_INT, int(team)))
    if other_team:
        entries.append((0x1000081C, KIND_INT, int(other_team)))
    entries += list(extra)          # the entities' class / billboard icon / name / announcer name id (Match.voice)
    body = bytes(1) + struct.pack("<II", flag, channel) + property_table(entries)
    return build_message(dest, 0x2039, body)


def announcer_line(key, channel, flag=1, dest=LOCAL_PLAYER_ID):
    """0x2039 with 0x100003BD = an announcer line key (dialog-shield-disconnect.md 1, C): the handler 0xa77da0 then
    plays that line from the channel's set (0xa596b0(key, channel)) with no match event: 1 = the shared set
    (template 0x10000803), 2 = the encounter's set, 3 = a set loaded by 0x202A."""
    from .wire import KIND_ENUM, property_table
    body = bytes(1) + struct.pack("<II", flag, channel) + property_table([(0x100003BD, KIND_ENUM, int(key))])
    return build_message(dest, 0x2039, body)


def load_announcer_set(set_did, dest=LOCAL_PLAYER_ID):
    """0x202A u8 0 | u32 announcer set DID (exec 0x8b2230 -> 0xa1b400): loads the set into dialog channel 3."""
    return build_message(dest, 0x202A, bytes(1) + struct.pack("<I", set_did))


def start_conversation(key, speaker=CHAMPION_AGENT_ID, instance_id=0xFFFFFFFF):
    body = (bytes(1) + struct.pack("<QIII", 0, 1, key, 1) + struct.pack("<Q", speaker)
            + bytes([1]) + struct.pack("<I", instance_id))
    return build_message(LOCAL_PLAYER_ID, 0x2001, body)


def tutorial_hint(hint_id, force_open=True):
    blob = struct.pack("<I", hint_id) + bytes([1 if force_open else 0])
    return build_message(LOCAL_PLAYER_ID, 0x2, bytes(1) + struct.pack("<II", 0x1000027F, len(blob)) + blob)


NOTICE_SHOW_ANNOUNCEMENT = 0x100002EB  # GM_Character.RecvNotice_ShowAnnouncement (reader 0x8c2fa0)
NOTICE_CLEAR_ANNOUNCEMENT = 0x100002EC


def _notice(notice_id, blob):
    return build_message(LOCAL_PLAYER_ID, 0x2, bytes(1) + struct.pack("<II", notice_id, len(blob)) + blob)


def show_announcement(text, a=1, b=0, c=0, d=-1, e=-1, flag=0):
    """The big centre-screen announcement: StringInfo text | u32 a | u32 b |
    u32 c | i32 d | i32 e | u8 flag (the client's own kill announcements fill
    the same fields; a must not be 0)."""
    return _notice(NOTICE_SHOW_ANNOUNCEMENT, string_info(text) + struct.pack("<IIIiiB", a, b, c, d, e, 1 if flag else 0))


def clear_announcement():
    return _notice(NOTICE_CLEAR_ANNOUNCEMENT, b"")


def dialog_enable():
    """Notice 0x10000205 (empty; handler 0xa8ea40): the match is on for the client's dialog system (bit 0x4 at
    [dialog+0x14c], without which 0x2039 is dropped) and the turret-warning system starts."""
    return _notice(0x10000205, b"")


def timeline_banner(title, subtitle="", event_id=1, iid=LOCAL_PLAYER_ID, now=0.0, audience=7):
    """The mission timeline banner: notices 0x100002AF and 0x100002B1 (both
    needed before any banner shows), then 0x10000424 AddTimelineBanner:
    u32 event | u64 iid | u32 | u32 | u32 | u8 | u32 | f64 time | u8 |
    u32 n | n x (StringInfo title | StringInfo subtitle | u32 audience) | f64."""
    enable = struct.pack("<Q", iid)
    desc = (struct.pack("<IQ", event_id, iid) + struct.pack("<IIIBI", 0, 0, 0, 0, 0) + struct.pack("<d", now)
            + b"\x00" + struct.pack("<I", 1) + string_info(title) + string_info(subtitle)
            + struct.pack("<I", audience))
    return [("timeline banners on (0x100002af)", _notice(0x100002AF, enable)),
            ("timeline banners on (0x100002b1)", _notice(0x100002B1, enable)),
            (f"timeline banner '{title}' (0x10000424)", _notice(0x10000424, desc + struct.pack("<d", now)))]


def objective_tracker_enabled(enabled=True):
    return build_message(LOCAL_PLAYER_ID, 0x2075, bytes([0, 1 if enabled else 0]))


# ---- the end of a match ----------------------------------------------------------------
# (2026-10-15, static analysis of the client; see docs/reverse-engineering.md "Ending a match")
NOTICE_MATCH_ENDED = 0x1000000E      # GM_Encounter.RecvNotice_NotifyMatchEnded (reader rva 0x941750)
EVT_END_OF_MATCH_STATS = 0x2045      # end-of-match page (exec 0x8b2bd0 -> 0xa91bf0)
EVT_COMPLETED_ENCOUNTERS = 0x214B    # GM_Encounter.RecvNotice_UI_CompletedEncounters (0xa30cd0)


def match_ended(winning_team, seconds, b=0, d=0, e=0.0):
    """Notice 0x1000000E to the local player: u32 winning team | u32 | f32 match
    seconds | u32 | f32. The end page compares the winning team with the
    player's PVP_Team (0x1000009C): equal = VICTORY."""
    blob = struct.pack("<IIfIf", winning_team, b, float(seconds), d, float(e))
    return build_message(LOCAL_PLAYER_ID, 0x2, bytes(1) + struct.pack("<II", NOTICE_MATCH_ENDED, len(blob)) + blob)


# the stats block 0x866650 in wire-read order (hud-shop-timeline-kills.md 6.1): kind per read index
_STAT_READS = (["Q", "B", "I"] + ["Q"] * 14 + ["I"] * 2 + ["Q"] * 6 + ["I"] + ["Q"] * 8 + ["I"] + ["Q"] * 6 + ["I"]
               + ["S", "S"] + ["Q"] * 21 + ["I"] * 2)
# 2026-10-26 (end-stats-2045.md, C: the stats block starts at entry +0x78, FLD/FSTP pattern): f64 reads 11 and 57-60,
# f32 reads 65 / 66 (the earlier indexes were one too high)
_STAT_F64 = {11, 57, 58, 59, 60}
_STAT_F32 = {65, 66}


def _end_stats_entry(player_iid, champion_iid, row=None):
    """One player's end-of-match entry (reader 0x8776a0). row (2026-10-25, hud-shop-timeline-kills.md 6, C layout):
    {"team", "name", "bot", "kills": {target-type key: count}, "reads": {stats-block read index: value},
    "stomped"}; None = all zero / empty (as before)."""
    row = row or {}
    empty = string_info("")
    i = lambda n: struct.pack("<%dI" % n, *([0] * n))
    # the second u64 is the account IID (getter 0x85C790, end-stats-2045.md C), not the champion: 0 for a row
    # 2026-10-28 (timeline-kda-endscreen.md 3, C: 0x4FD4E0 reads +0x1C, the end page maps it to the champion's
    # record for the power graph and the portrait): u32 +0x1C = champion DID, +0x20 = in-match level (P)
    head = struct.pack("<QQQII", player_iid, int(row.get("account", champion_iid if not row else 0)), player_iid,
                       int(row.get("champion", 0)), int(row.get("level", 0)))
    sub = struct.pack("<IQI", 0, 0, 0) + empty + wstring("") + i(1) + pack_compact(0)     # 0x86fb20

    def counts(m):
        m = {int(k): int(v) for k, v in (m or {}).items() if v}
        return b"\x00" + pack_compact(len(m)) + b"".join(struct.pack("<II", k, v) for k, v in sorted(m.items()))
    # 2026-10-28 (timeline-kda-endscreen.md 3, C: 0xA795E0's second row loop sends Flash UpdateCurrentUpgrades +
    # UpdatePowerGraphValues per row (0xA3AC70) only when this list (entry +0x2FC, reader 0x844770: u32 n | n x (u32
    # artifact DID, u32 stack)) is not empty; the Flash scorecard waits for both from every row before it shows)
    ups = [(int(d), int(s)) for d, s in (row.get("upgrades") or ())]
    upgrades = struct.pack("<I", len(ups)) + b"".join(struct.pack("<II", d, s) for d, s in ups)
    mid = (struct.pack("<I", int(row.get("team", 0)) if row.get("send_team", True) else 0) + counts(row.get("kills")) + counts(row.get("deaths_by"))
           + string_info(str(row.get("name", ""))) + i(1) + i(2) + upgrades)
    reads = row.get("reads") or {}
    stats = b""
    for k, kind in enumerate(_STAT_READS):
        v = reads.get(k, 0)
        if kind == "S":
            stats += empty
        elif kind == "B":
            stats += bytes([int(v) & 0xFF])
        elif kind == "I":
            stats += struct.pack("<I", int(v) & 0xFFFFFFFF)
        elif k in _STAT_F64:
            stats += struct.pack("<d", float(v))
        elif k in _STAT_F32:
            stats += struct.pack("<f", float(v))
        else:
            stats += struct.pack("<Q", max(0, int(round(float(v)))))
    tail = struct.pack("<I", int(row.get("stomped", 0))) + b"\x00" + bytes([1 if row.get("bot") else 0])
    return head + sub + mid + stats + tail


def end_of_match_stats(seconds, player_iid=LOCAL_PLAYER_ID, champion_iid=CHAMPION_AGENT_ID):
    """0x2045 to the player system: u8 0 | u32 n | n entries | f32. The end
    page fills in only once it has these AND the match-ended notice."""
    body = bytes(1) + struct.pack("<I", 1) + _end_stats_entry(player_iid, champion_iid) + struct.pack("<f", float(seconds))
    return build_message(SVC_PLAYER_SYSTEM, EVT_END_OF_MATCH_STATS, body)


def completed_encounters(dids, last_played=0, flags=0):
    """0x214B: u8 0 | u32 n | n x u32 encounter | u32 last played | u32 flags.
    Tutorial 2 (0x40000A81) needs Tutorial 1 (0x40000991) in this list."""
    dids = list(dids)
    body = (bytes(1) + struct.pack("<I", len(dids)) + b"".join(struct.pack("<I", d) for d in dids)
            + struct.pack("<II", last_played, flags))
    return build_message(SVC_PLAYER_SYSTEM, EVT_COMPLETED_ENCOUNTERS, body)


EVT_EXIT_LOBBY = 0x2021              # RecvEvt_DeliverNotifyPlayerToExitLobby (handler 0xabc480)


def exit_lobby(room_id):
    """0x2021 to the player system: u8 0 | u32 room id (as in 0x2028 / 0x2029).
    The client leaves the match world (it answers with 0x12D) and goes home."""
    return build_message(SVC_PLAYER_SYSTEM, EVT_EXIT_LOBBY, b"\x00" + struct.pack("<I", room_id))


def server_preferences(prefs):
    """0x216A "server options" to the player system: the client stores each
    entry in its UserPreferences.ini (handler 0xa742d0). prefs = [(name, bool)]:
    u8 0 | u8 size class 0 | compact n | n x (compact len + ASCII name | u16 BE
    type 0x16 | u8 value)."""
    body = b"\x00\x00" + pack_compact(len(prefs))
    for name, value in prefs:
        body += pack_compact(len(name)) + name.encode("ascii") + struct.pack(">H", 0x16) + bytes([1 if value else 0])
    return build_message(SVC_PLAYER_SYSTEM, 0x216A, body)


EVT_SKILL_COOLDOWN = 0x20F8


def skill_cooldown(slot, end_time, agent=CHAMPION_AGENT_ID, dest=LOCAL_PLAYER_ID):
    """0x20F8 (handler rva 0x4bc7c0, reader rva 0x439bd0): u8 0 | u64 agent IID | u32 skill slot | f64 end time.
    The client shows end - now on the skill button (GM_UI.RecvNotice_StartSkillCooldown)."""
    return build_message(dest, EVT_SKILL_COOLDOWN, b"\x00" + struct.pack("<QId", agent, slot, float(end_time)))


# ---- the in-match shop (shop-items-inventory.md section 3) ------------------------------------------------------

EVT_SHOP_TRANSACTION_DONE = 0x2086   # u32 handle seq | u64 handle iid: the client's shop is usable again
EVT_INVENTORY = 0x20E2               # to the champion: its 6 item slots + the amplifier-set tail
NOTICE_FLOATY_CURRENCY = 0x100004D6  # u64 entity | f32 amount: "+N credits" over a killed entity (probable)


def shop_transaction_done(seq, iid):
    return build_message(LOCAL_PLAYER_ID, EVT_SHOP_TRANSACTION_DONE, b"\x00" + struct.pack("<IQ", seq, iid))


def inventory(champion_id, slots):
    """0x20E2: u32 n | n x (u32 artifact, u32 stack count) | tail = an empty amplifier set (u32 | u64 | u32 |
    StringInfo | wstr | u32 | compact n + n x u32)."""
    body = struct.pack("<I", len(slots)) + b"".join(struct.pack("<II", d, 1 if d else 0) for d in slots)
    tail = struct.pack("<IQI", 0, 0, 0) + string_info("") + wstring("") + struct.pack("<I", 0) + pack_compact(0)
    return build_message(champion_id, EVT_INVENTORY, b"\x00" + body + tail)


def floaty_currency(entity_id, amount):
    return _notice(NOTICE_FLOATY_CURRENCY, struct.pack("<Qf", entity_id, float(amount)))


# ---- defeat / respawn timers (progression-meta.md 1.4, protocol-server-to-client.md) ----------------------------

NOTICE_DEFEAT_STATUS = 0x10000090             # u32 state | u64 player: the local "dead" panel
NOTICE_DEFEAT_STATUS_ENTITY = 0x100000BC      # u64 agent | u32 killer type | u32 state | f64 time of the next state
DEFEAT_DEAD, DEFEAT_INCAPACITATED, DEFEAT_ALIVE = 2, 3, 4


def defeat_status(state, next_time=0.0, player_id=LOCAL_PLAYER_ID):
    """Notice 0x10000090 to the player: u32 state | f64 time of the next state (reader 0x8c48c0, deliverer 0x8beac0
    movsd; Flash DefeatStatus.StartCountdownTimerNow on the game clock). 2026-10-23: it carried the u64 player id there,
    which as a double is ~0, so the respawn countdown ended at once."""
    return _notice(NOTICE_DEFEAT_STATUS, struct.pack("<Id", state, float(next_time)))


def ping_echo(pinger_id, x, y, target_id, ping_type):
    """0x2137 to the player: u8 0 | u64 pinger | f32 x | f32 y | u64 target (0 = ground) | u32 type (as 0x2136)."""
    return build_message(LOCAL_PLAYER_ID, 0x2137, bytes(1) + struct.pack("<QffQI", pinger_id, x, y, target_id, ping_type))


def defeat_status_entity(agent_id, state, next_time, killer_type=0):
    return _notice(NOTICE_DEFEAT_STATUS_ENTITY, struct.pack("<QIId", agent_id, killer_type, state, float(next_time)))


EVT_RECOMMENDED_UPGRADES = 0x2078    # to the champion: u32 list of recommended buys (the shop's "next" hint)


def kill_card(attackers, icons, teams, killer_name, damage=None, type_totals=None, reader_layout=True):
    """Notice 0x1000021C, the victim's kill card (listener 0xa61260 -> UI_ShowKillCard 0x10000222). 2026-10-25
    (hud-shop-timeline-kills.md 5.3, C, reader 0x9326C0): list<u64> attackers | list<u32> icons | list<u32> teams |
    StringInfo killer name | 5 x list<f32> (total, slot 1..4 damage per attacker) | 28 x list<u32> per attacker (slot
    1..4 slot type, damage type, icon, artifact, mod, + 8 more) | 4 x list<StringInfo> (slot names) | 2 x list<f32>
    (damage-type totals, percentages: [_, attack, power, true, mixed]) | 2 x list<u32>. damage: per attacker
    {"total", "slots": {slot: dmg}, "types": {slot: damage type}, "icons": {slot: DID}}. reader_layout False = the
    fase3-hs layout."""
    n = len(attackers)
    u32s = lambda vals: struct.pack("<I", len(vals)) + b"".join(struct.pack("<I", int(v) & 0xFFFFFFFF) for v in vals)
    f32s = lambda vals: struct.pack("<I", len(vals)) + b"".join(struct.pack("<f", float(v)) for v in vals)
    head = (struct.pack("<I", n) + b"".join(struct.pack("<Q", a) for a in attackers)
            + u32s(icons) + u32s(teams) + string_info(killer_name))
    if not reader_layout:
        blob = (head + struct.pack("<II", 0, 0) * 5 + b"".join(u32s([0] * n) for _ in range(28))
                + b"".join(struct.pack("<I", 0) + string_info("") for _ in range(4))
                + struct.pack("<II", 0, 0) * 2 + u32s([]) + u32s([]) + struct.pack("<I", 0))
        return _notice(0x1000021C, blob)
    damage = list(damage or [{}] * n)[:n] + [{}] * max(0, n - len(damage or []))
    cols = [[d.get("total", 0.0) for d in damage]] + [[(d.get("slots") or {}).get(s, 0.0) for d in damage]
                                                      for s in (1, 2, 3, 4)]
    blob = head + b"".join(f32s(c) for c in cols)
    lists = []
    lists += [[1 if (d.get("slots") or {}).get(s) else 0 for d in damage] for s in (1, 2, 3, 4)]     # slot types
    lists += [[(d.get("types") or {}).get(s, 0) for d in damage] for s in (1, 2, 3, 4)]              # damage types
    lists += [[(d.get("icons") or {}).get(s, 0) for d in damage] for s in (1, 2, 3, 4)]              # slot icons
    lists += [[0] * n for _ in range(4)]                                                              # artifacts
    lists += [[0] * n for _ in range(4)]                                                              # mods
    lists += [[0] * n for _ in range(8)]
    blob += b"".join(u32s(v) for v in lists)
    blob += b"".join(struct.pack("<I", n) + b"".join(string_info("") for _ in range(n)) for _ in range(4))
    tt = list(type_totals or [0.0] * 5)
    total = sum(tt[1:]) or 1.0
    blob += f32s(tt) + f32s([0.0] + [v / total for v in tt[1:]]) + u32s([]) + u32s([])
    return _notice(0x1000021C, blob)


def recommended_upgrades(champion_id, dids):
    return build_message(champion_id, EVT_RECOMMENDED_UPGRADES,
                         b"\x00" + struct.pack("<I", len(dids)) + b"".join(struct.pack("<I", d) for d in dids))


EVT_SET_PROPERTY = 0x6   # u8 0 | one property entry (u32 id | packed id | value): set on the object's table [obj+0x38]
                         # through its change path (exec 0x699450, handler 0x635360 -> collection vt+0x50), so the
                         # client's watchers (unit component cache, HUD) see the change


def set_property(object_id, prop, kind, value):
    from .wire import pack_property
    return build_message(object_id, EVT_SET_PROPERTY, bytes(1) + pack_property(prop, kind, value))


def set_property_entry(object_id, entry):
    """Event 0x6 with an entry already packed (wire.pack_property): the same bytes as set_property (World.delta)."""
    return build_message(object_id, EVT_SET_PROPERTY, bytes(1) + entry)


# ---- PvP flow, account and social (2026-10-22; docs/re-notes/full-protocol.md 4, full-account-social.md) ----------
# Layouts from docs/re-notes/full-protocol.tsv (the serializers); [P] where a field's meaning is probable only.

def _u32s(*vals):
    return struct.pack("<%dI" % len(vals), *[int(v) & 0xFFFFFFFF for v in vals])


def _u32list(vals=()):
    vals = list(vals)
    return _u32s(len(vals), *vals)


def str8(text):
    """compact length + ASCII (the client's "str8": 0x216E names, 0x2106 / 0x210E currency keys)."""
    raw = text.encode("ascii", "replace")
    return pack_compact(len(raw)) + raw


def _player_msg(event, body):
    return build_message(SVC_PLAYER_SYSTEM, event, b"\x00" + body)


def ownables(items):
    """0x20B8 ownables (ser 0x844FD0): u8 0 | u32 n | n x (u32 DID, u32 ContentStatus, u32 ContentType, u8 owned,
    u32 count). items = [(did, status, content_type, owned, count)]. The second and later deliveries are
    incremental on the client (handler 0xa88030)."""
    items = list(items)
    return _player_msg(0x20B8, _u32s(len(items)) + b"".join(
        struct.pack("<IIIBI", d, st, t, 1 if o else 0, c) for d, st, t, o, c in items))


def character_advancement(rows):
    """0x209D CharacterAdvancementData: u8 0 | table (u8 0 | compact n | n x (u32 DID, u32 level, u32 XP, u32
    next-level XP, u64 last used, u64 last used ranked)) [P field names]."""
    rows = list(rows)
    return build_message(SVC_PLAYER_SYSTEM, EVT_MASTER_CHARACTER_LIST, b"\x00\x00" + pack_compact(len(rows)) + b"".join(
        struct.pack("<IIIIQQ", *r) for r in rows))


SERVER_OPTION_F32, SERVER_OPTION_INT, SERVER_OPTION_BOOL = 9, 0x10, 0x16


def server_options(entries):
    """0x216A server options (handler 0xa742d0): u8 0 | u8 0 | compact n | n x (compact len + ASCII name | u16 BE
    type | value): type 9 f32, 0x10 compact int, 0x16 bool (full-account-social.md 9). entries = [(name, type,
    value)]."""
    entries = list(entries)
    body = b"\x00\x00" + pack_compact(len(entries))
    for name, typ, value in entries:
        body += pack_compact(len(name)) + name.encode("ascii") + struct.pack(">H", typ)
        if typ == SERVER_OPTION_F32:
            body += struct.pack("<f", float(value))
        elif typ == SERVER_OPTION_INT:
            body += pack_compact(max(0, int(value)))
        else:
            body += bytes([1 if value else 0])
    return build_message(SVC_PLAYER_SYSTEM, 0x216A, body)


def account_level(level, prev_level, xp_to_next, xp_total, xp_earned=0, xp_bonus=0, pct=0.0, prev_pct=0.0, layout="client"):
    """0x2080 account level / XP (ser 0x8392f0): u8 0 | 6 x u32 | f32 | f32. Last of the login data.
    layout "client" (tester report 2026-10-29 21:10, aggro-recall-scorepanel.md 3, C: handler 0xA7DFB0 passes wire
    words w0..w7 to Flash SendAccountEndOfMatchLevelAndXP(level, prev, toNext, total, earned, bonus, pct, prevPct) as
    (w0, w1, w5, w2, w3, w4, w6, w7) and to the header's SendAccountLevelAndXP(level, totalXP, pct, toNext) as
    (w0, w2, w6, w5)): level | prev | total | earned | bonus | to next | f32 pct | f32 prev pct; "old" = level, prev,
    to next, total, earned, bonus (to fase3-in: the panel read total = our remainder, to next = our bonus 0)."""
    if layout == "client":
        words = _u32s(level, prev_level, xp_total, xp_earned, xp_bonus, xp_to_next)
    else:
        words = _u32s(level, prev_level, xp_to_next, xp_total, xp_earned, xp_bonus)
    return _player_msg(0x2080, words + struct.pack("<ff", float(pct), float(prev_pct)))


def currency_balance(hard, soft):
    """0x2081: u8 0 | u32 Crisis Coins | u32 Merits."""
    return _player_msg(0x2081, _u32s(hard, soft))


def soft_currency_reward(base=0, daily=0, time_to_daily=0.0, streak=0, potential_daily=0, potential_streak=0):
    """0x20B9 end-of-match Merits: u8 0 | u32 base | u32 daily | f32 time to next daily | u32 streak | u32 potential
    daily | u32 potential streak | StringInfo | StringInfo | u32."""
    return _player_msg(0x20B9, _u32s(base, daily) + struct.pack("<f", float(time_to_daily))
                       + _u32s(streak, potential_daily, potential_streak) + string_info("") + string_info("") + _u32s(0))


def character_level(champion, name, level, prev_level, xp_to_next, xp_total, xp_earned=0, xp_bonus=0, pct=0.0,
                    prev_pct=0.0, icon=0, layout="client", encounter=0):
    """0x2104 champion level / XP at the end of a match (+ empty accolade lists). layout "client" (tester report
    2026-10-29 12:45; unit-death-slide-levelup.md 3, C 0xA7E0A0 + the summary's "720 / 1061997773"): after the name
    u32 level | prev | total | earned | bonus | f32 pct | f32 prev pct | u32 to next; "old": to next, total, earned,
    bonus, pct, prev pct (fase3-ig).
    encounter: the u32 after the six accolade lists (handler 0xA7E0A0 param_21, C): 0xA56DB0 looks it up as a record
    and, when found, the handler hands the (here empty) accolade lists to Flash SendAccountEndOfMatchAccoladesEarned
    (0x8CEE70) and caches it as the accolades' encounter; 0 = no record, no accolades notice (to fase3-ip).
    2026-10-30 tester report 11:23 (scorecard-panel-turret-head.md 1)."""
    if layout == "client":
        nums = (_u32s(level, prev_level, xp_total, xp_earned, xp_bonus) + struct.pack("<ff", float(pct), float(prev_pct))
                + _u32s(xp_to_next))
    else:
        nums = (_u32s(level, prev_level, xp_to_next, xp_total, xp_earned, xp_bonus)
                + struct.pack("<ff", float(pct), float(prev_pct)))
    body = (_u32s(champion, icon) + string_info(name) + nums + b"\x00\x00"
            + _u32s(0) * 3 + _u32s(0) + _u32s(0) * 2 + _u32s(encounter) + b"\x00")
    return _player_msg(0x2104, body)


def accolades_earned(encounter, champion, ranked=False):
    """0x2188 end-of-match accolades (none): u8 0 | u32 encounter | u8 ranked | u32 champion | StringInfo | 3 x
    list<u32> | bytelist | 2 x list<u32>. NB (C, 0xA61DA0): the handler drops the whole message when the second list
    (the accolade records) is empty, so this empty copy never reaches Flash; the empty accolades notice comes from
    0x2104's encounter field instead (scorecard-panel-turret-head.md 1)."""
    return _player_msg(0x2188, _u32s(encounter) + bytes([1 if ranked else 0]) + _u32s(champion) + string_info("")
                       + _u32s(0) * 3 + _u32s(0) + _u32s(0) * 2)


# ---- queue -----------------------------------------------------------------------------------------------------------
def removed_from_queue():
    """0x20E0 (UI.RemovedFromQueue): the base byte only; the answer to LeaveQueue 0x20C3 [P]."""
    return _player_msg(0x20E0, b"")


def queue_error():
    """0x210B: queue / match error -> removed from queue + dialog (base byte only)."""
    return _player_msg(0x210B, b"")


def queue_wait_times(keys, seconds):
    """0x218F: u8 0 | u32 n | n x QueueKey (u32 encounter, u32 flags) | u32 n | n x list<u32> wait times [P units]."""
    keys = list(keys)
    return _player_msg(0x218F, _u32s(len(keys)) + b"".join(_u32s(d, f) for d, f in keys)
                       + _u32s(len(keys)) + b"".join(_u32list(s) for s in seconds))


# ---- lobby / champion select -----------------------------------------------------------------------------------------
def amplifier_set(slot=0, set_id=0, champion=0, name="", icon=0, amplifiers=()):
    """The amplifier set struct (0x86FB20; account-systems-data.md 1.4): u32 slot | u64 id | u32 champion |
    StringInfo name | wstr custom name | u32 icon | compact n + n x u32 amplifiers (always 7 for 0x2090)."""
    amps = list(amplifiers)
    return (struct.pack("<IQI", slot, set_id, champion) + string_info("") + wstring(name)
            + struct.pack("<I", icon) + pack_compact(len(amps)) + b"".join(struct.pack("<I", a) for a in amps))


def lobby_slot(team, index, player_id, name, champion, room_id, is_bot=False, locked=False, level=0,
               stolen=(0, 0), amp=None, extra=(0, 0, 0, 0, 0)):
    """0x2029 one lobby slot (ser 0x8479b0, exec 0x8b9150 -> 0xabd0a0): u8 0 | draft struct (u8 0 = none) |
    u32 team | u32 team index | u64 player | StringInfo name | u8 bot | u32 champion | u32 [P: level] | u8 locked |
    u32 room | u32 1 | 5 x u32 [P: icon / pre-game / base champion ...] | u32 Stolen Power one | u32 Stolen Power
    two (both stored at lobby +0x1d4 / +0x1d8, as 0x2004 does) | amplifier set. With the defaults it is byte for
    byte the earlier lobby_player (the tutorial's)."""
    tail = amp if amp is not None else (struct.pack("<IQI", 0, 0, 0) + string_info("") + pack_compact(0)
                                        + struct.pack("<I", 0) + pack_compact(1) + struct.pack("<I", champion))
    ex = (list(extra) + [0] * 5)[:5]
    body = (b"\x00" + b"\x00" + struct.pack("<IIQ", team, index, player_id) + string_info(name)
            + bytes([1 if is_bot else 0]) + struct.pack("<II", champion, level) + bytes([1 if locked else 0])
            + struct.pack("<II", room_id, 1) + _u32s(*ex) + _u32s(stolen[0], stolen[1]) + tail)
    return build_message(SVC_PLAYER_SYSTEM, 0x2029, body)


def lobby_details(did, qflags, room_id, teams=2, per_team=5, player_id=LOCAL_PLAYER_ID, team=1, owned=(),
                  required=(), admin=False, rejoin=False):
    """0x204C lobby state (ser 0x845810, handler 0xabde80): u8 0 | u32 teams | u32 players per team | QueueKey |
    u64 my player | u32 my team | u32 room | u32 n x (u32 DID, u32 status, u32 type, u8 owned, u32 count) |
    list<u32> | u8 | u8. The handler keeps teams / players per team only when queue flag bit 17 is set."""
    owned = list(owned)
    body = (_u32s(teams, per_team, did, qflags) + struct.pack("<Q", player_id) + _u32s(team, room_id)
            + _u32s(len(owned)) + b"".join(struct.pack("<IIIBI", *o) for o in owned) + _u32list(required)
            + bytes([1 if admin else 0, 1 if rejoin else 0]))
    return _player_msg(0x204C, body)


def picked_stolen_powers(room_id, one, two, player_id=LOCAL_PLAYER_ID):
    """0x2004 PlayerPickedStolenPowers (handler 0xab87d0): u8 0 | u32 room | u32 power one | u32 power two |
    u64 player."""
    return _player_msg(0x2004, _u32s(room_id, one, two) + struct.pack("<Q", player_id))


def picked_amplifier_set(room_id, amp_set, player_id=LOCAL_PLAYER_ID):
    """0x204A PlayerPickedAmplifierSet: u8 0 | u32 room [P] | set | u64 player."""
    return _player_msg(0x204A, _u32s(room_id) + amp_set + struct.pack("<Q", player_id))


def amplifier_sets_list(total, maximum, sets):
    """0x2090 NotifyListAmplifierSets: u8 0 | u32 total | u32 max | u32 n | n x set."""
    sets = list(sets)
    return _player_msg(0x2090, _u32s(total, maximum, len(sets)) + b"".join(sets))


def amplifier_set_saved(amp_set):
    """0x20C7 NotifyAmplifierSet: u8 0 | set (the answer to a save 0x20FC)."""
    return _player_msg(0x20C7, amp_set)


AMP_SAVE_FAILED, AMP_LOAD_FAILED, AMP_NAME_TOO_LARGE = 0x10000063, 0x10000064, 0x10000065


def amplifier_set_error(error=AMP_SAVE_FAILED):
    return _player_msg(0x2052, _u32s(error))


def amplifier_boutique(entries):
    """0x2107 NotifyContextualAmplifierData: u8 0 | u32 n | n x (u64 boutique id | u32 DID | str8 currency | u32
    price) (handler 0xA57510, ids as %I64d text; the str8 is right: the client sent the ids back). BoutiqueDataManager
    keeps a price only for the currency names "SC" (Merits) / "HC" (Crisis Coins), case ignored, one BoutiqueData per
    DID; any other name leaves the cost at -1 (store-fix.md 3.1, C)."""
    entries = list(entries)
    return _player_msg(0x2107, _u32s(len(entries)) + b"".join(
        struct.pack("<QI", bid, did) + str8(cur) + _u32s(price) for bid, did, cur, price in entries))


def lock_failed(room_id, champion):
    """0x2005 CharacterLockFail: u8 0 | u32 | u32 [P: room, champion]."""
    return _player_msg(0x2005, _u32s(room_id, champion))


def launch_warning(start, end, room_id, f64=True):
    """0x204B MatchLaunchWarning(ttMatchLaunchTimeStart, ttMatchLaunchTimeEnd): u8 0 | f64 | f64 | u32 room. The two
    times are doubles (serializer 0x838930 copies 8 bytes, handler 0xabd420 reads them with movsd): game-clock seconds,
    LaunchWarning.as counts down to the end (callbacks at end-10, -5, -2, -1, end). f64=False: the old u64 form."""
    times = struct.pack("<dd", float(start), float(end)) if f64 else struct.pack("<QQ", int(start), int(end))
    return _player_msg(0x204B, times + _u32s(room_id))


def early_launch_selected(name, room_id):
    """0x206C PlayerSelectedEarlyLaunchFromServer: u8 0 | StringInfo | u32."""
    return _player_msg(0x206C, string_info(name) + _u32s(room_id))


def match_started(room_id, team_names=(), team_short=()):
    """0x2053 match started (UI state-machine event 0x14): u8 0 | u32 | u32 n x StringInfo | u32 n x StringInfo."""
    return _player_msg(0x2053, _u32s(room_id) + _u32s(len(team_names)) + b"".join(string_info(t) for t in team_names)
                       + _u32s(len(team_short)) + b"".join(string_info(t) for t in team_short))


def draft_trade_request(name, text=""):
    """0x2054 Draft_TradeRequest: u8 0 | StringInfo | StringInfo."""
    return _player_msg(0x2054, string_info(name) + string_info(text))


# ---- store -----------------------------------------------------------------------------------------------------------
PURCHASE_GENERAL_ERROR, PURCHASE_INSUFFICIENT_FUNDS = 0x10000068, 0x10000069


def purchase_success(order):
    return _player_msg(0x210C, struct.pack("<Q", order))


def purchase_error(order, error=PURCHASE_GENERAL_ERROR):
    return _player_msg(0x210D, struct.pack("<QI", order, error))


def purchase_price_changed(boutique_id, did, currency, initial, order, final):
    """0x210F: u8 0 | u64 boutique | u32 DID | (u64, u32, str8 currency, u32 initial, str8 order, u32 final) [P]."""
    return _player_msg(0x210F, struct.pack("<QI", boutique_id, did) + struct.pack("<QI", boutique_id, did)
                       + str8(currency) + _u32s(initial) + str8(str(order)) + _u32s(final))


# ---- achievements, rewards, accolades, standings -------------------------------------------------------------------
def achievement_objective(index, current, previous, last_updated=0, has_progress=True):
    return _u32s(index, current, previous, 0) + struct.pack("<Q", int(last_updated)) + bytes([1 if has_progress else 0])


def achievement_entry(did, times_completed, time_valid, objectives):
    """One progress entry (table key u32 | value: u32 DID | u32 times | u64 valid until | u32 n | objectives)."""
    objectives = list(objectives)
    return (_u32s(did, did, times_completed) + struct.pack("<Q", int(time_valid)) + _u32s(len(objectives))
            + b"".join(objectives))


def achievement_progress(entries, deprecated=()):
    """0x2120 achievement progress: u8 0 | table (u8 0 | compact n | entries) | list<u32> deprecated."""
    entries = list(entries)
    return _player_msg(0x2120, b"\x00" + pack_compact(len(entries)) + b"".join(entries) + _u32list(deprecated))


def achievement_banners(entries=()):
    """0x211F AllPendingAchivementBanners (answer to 0x212E): u8 0 | table of progress entries."""
    entries = list(entries)
    return _player_msg(0x211F, b"\x00" + pack_compact(len(entries)) + b"".join(entries))


def reward_element(reward_set, source, item, quantity, bestowal, instance, icon=0, name="", day=0):
    """A pending reward element (ser 0x867fb0): u32 set | u32 source | u32 (+8: login day [P]) | u32 item | u32 qty |
    u32 bestowal | u64 instance | u32 icon | StringInfo name."""
    return (_u32s(reward_set, source, day, item, quantity, bestowal) + struct.pack("<Q", instance)
            + _u32s(icon) + string_info(name))


def reward_sets(elements, event=0x2125):
    """0x2125 pending reward sets (source type 1 achievement) / 0x2197 login reward (source type 2): u8 0 | u32 n |
    elements; consecutive elements with the same set form one set."""
    elements = list(elements)
    return _player_msg(event, _u32s(len(elements)) + b"".join(elements))


def no_login_reward():
    return _player_msg(0x219D, b"")


def best_accolades(by_map=(), by_champion=()):
    """0x2186 best map / champion accolades: u8 0 | 2 x (u32 n | n x (u32, u32, u8, u32, u32, StringInfo))."""
    def part(rows):
        rows = list(rows)
        return _u32s(len(rows)) + b"".join(_u32s(a, b) + bytes([c & 0xFF]) + _u32s(d, e) + string_info("")
                                          for a, b, c, d, e in rows)
    return _player_msg(0x2186, part(by_map) + part(by_champion))


def leaderboard(rows, total=0, event=0x21A2):
    """0x21A2 regional / 0x21A3 friends leaderboard: u8 0 | u32 n | n x (u64 account | wstr name | u32 rank | u32
    sub-pips | u32 position | u32 champion | u32) | u32."""
    rows = list(rows)
    return _player_msg(event, _u32s(len(rows)) + b"".join(
        struct.pack("<Q", iid) + wstring(name) + _u32s(rank, pips, pos, champ, extra)
        for iid, name, rank, pips, pos, champ, extra in rows) + _u32s(total))


def account_standings(values):
    """0x219E account standings: u8 0 | 10 x u32 = last played encounter, rank, previous rank, sub-rank, previous
    sub-rank, position, streak, previous streak, played, won (matchend.ranked_values; end-screen-crash.md)."""
    vals = (list(values) + [0] * 10)[:10]
    return _player_msg(0x219E, _u32s(*vals))


def static_standings(values=(0,) * 5):
    """0x219F: u8 0 | 9 x list<u32> | u32 n x (u32, u32, u32) | 5 x u32 (the client rebuilds the tiers from data)."""
    vals = (list(values) + [0] * 5)[:5]
    return _player_msg(0x219F, b"".join(_u32s(0) for _ in range(9)) + _u32s(0) + _u32s(*vals))


def encounter_stats(rows):
    """0x2115 account encounter stats (answer to 0x2116): u8 0 | u32 n | n x (u64 | u8 | u32 | 14 x u64 | 2 x u32 |
    6 x u64 | u32 | 8 x u64 | u32 | 6 x u64 | u32 | StringInfo | StringInfo | 21 x u64 | 2 x u32). rows = [(u64, u8
    ranked, u32 encounter)]; the statistics stay 0 (their order is not mapped yet)."""
    rows = list(rows)
    q = lambda n: bytes(8 * n)
    i = lambda n: bytes(4 * n)
    out = b""
    for a, ranked, enc in rows:
        out += (struct.pack("<QBI", a, ranked, enc) + q(14) + i(2) + q(6) + i(1) + q(8) + i(1) + q(6) + i(1)
                + string_info("") + string_info("") + q(21) + i(2))
    return _player_msg(0x2115, _u32s(len(rows)) + out)


def end_of_match_stats_all(seconds, players):
    """0x2045 with one entry per player: players = [(player iid, champion iid)] or [(player, champion, row)]."""
    players = list(players)
    return _player_msg(EVT_END_OF_MATCH_STATS, struct.pack("<I", len(players)) + b"".join(
        _end_stats_entry(*p) for p in players) + struct.pack("<f", float(seconds)))


def dialog_text(title, text):
    """0x2087 DisplayDialogText: u8 0 | StringInfo | StringInfo."""
    return _player_msg(0x2087, string_info(title) + string_info(text))


# ---- chat / contacts -------------------------------------------------------------------------------------------------
def chat_line(channel, text, a=0, b=0, dest=LOCAL_PLAYER_ID):
    """0x2183 (exec 0x8abf20, handler 0xa5cf40): u8 0 | StringInfo | StringInfo | u32 | u32, to the player object
    [G: the event that shows another player's line]."""
    return build_message(dest, 0x2183, b"\x00" + string_info(channel) + string_info(text) + _u32s(a, b))


def chat_toggle_unread(sender, channel, text):
    """0x20B0 (ToggleUnreadChat): u8 0 | wstr | StringInfo | wstr [G]."""
    return _player_msg(0x20B0, wstring(sender) + string_info(channel) + wstring(text))


def chat_members(channel, members):
    """0x2135 UpdatedMemberList: u8 0 | StringInfo room | list<u64>."""
    members = list(members)
    return _player_msg(0x2135, string_info(channel) + _u32s(len(members))
                       + b"".join(struct.pack("<Q", m) for m in members))


def contact_list(contacts=()):
    """0x203B contact list: u8 0 | u32 n | n x contact record (n = 0 is enough to open the panel)."""
    contacts = list(contacts)
    return _player_msg(0x203B, _u32s(len(contacts)) + b"".join(contacts))


def contact_group_created(group_id, name):
    return _player_msg(0x2014, struct.pack("<Q", group_id) + wstring(name))


# ---- custom match ----------------------------------------------------------------------------------------------------
def cm_participant_added(name, account, player, level, icon, permission, is_friend, team):
    """0x2012 AddedParticipant: u8 0 | (wstr | u64 | u64 | u32 | u32 | u32 | u8) | u32 [P: team]."""
    return _player_msg(0x2012, wstring(name) + struct.pack("<QQ", account, player) + _u32s(level, icon, permission)
                       + bytes([1 if is_friend else 0]) + _u32s(team))


def cm_participant_removed(account):
    return _player_msg(0x205D, struct.pack("<Q", account))


def cm_set_encounter(did):
    return _player_msg(0x2109, _u32s(did))


def cm_draft_mode(flag, enabled):
    return _player_msg(0x2103, _u32s(flag) + bytes([1 if enabled else 0]))


def cm_team_name(team, long_name, short_name):
    return _player_msg(0x2151, _u32s(team) + string_info(long_name) + string_info(short_name))


def cm_assigned_team(account, team):
    return _player_msg(0x2076, struct.pack("<Q", account) + _u32s(team))


def cm_moved(account, position):
    return _player_msg(0x2048, struct.pack("<Q", account) + _u32s(position))


def cm_permission(account, permission, granted):
    return _player_msg(0x2035, struct.pack("<Q", account) + _u32s(permission) + bytes([1 if granted else 0]))


def cm_coordinator(old, new):
    return _player_msg(0x2036, struct.pack("<QQ", old, new))


def cm_kicked(reason=0):
    return _player_msg(0x2041, _u32s(reason))


def cm_cancelled():
    return _player_msg(0x2011, b"")


def cm_launched():
    return _player_msg(0x2040, b"")


def cm_creation_failed(text=""):
    return _player_msg(0x2042, string_info(text))


# ---- PvP match (ics/match; layouts from docs/re-notes/full-match-mechanics.md, 2026-10-22) -----------------------
# Every builder here is prefixed pvp_ (another engineer appends to this file too).

def _pvp_u32_lists(*lists):
    import math
    return b"".join(struct.pack("<I", len(v)) + b"".join(struct.pack("<I", int(math.ceil(x))) for x in v)
                    for v in lists)


def pvp_set_match_time(start, end, pre_start):
    """Notice 0x10000109 SetMatchTime (reader 0x941d60, C++ 0xa902f0): f64 start | f64 end | u8 isPreStart. While
    isPreStart the HUD clock counts down to start, afterwards it counts up from start; end must be > start. Times
    are the game clock (the time packet's)."""
    return _notice(0x10000109, struct.pack("<ddB", float(start), float(end), 1 if pre_start else 0))


def pvp_match_roster(rows):
    """Notice 0x1000005B (reader 0x942a80 -> 0xa901f0): the Tab scoreboard, team portraits and KDA. rows: dicts
    name, account, agent, player, champion, team, money, level, kills, deaths, assists, bot."""
    blob = struct.pack("<I", len(rows))
    for r in rows:
        blob += (string_info(r.get("name", "")) + struct.pack("<QQQ", r.get("account", 0), r.get("agent", 0),
                                                               r.get("player", 0))
                 + struct.pack("<IIfIIIIB", r.get("champion", 0), r.get("team", 0), float(r.get("money", 0.0)),
                               r.get("level", 1), r.get("kills", 0), r.get("deaths", 0), r.get("assists", 0),
                               1 if r.get("bot") else 0))
    return _notice(0x1000005B, blob)


def pvp_kill_feed(victim, victim_icon, victim_team, killer, killer_team, icons=(), dest=LOCAL_PLAYER_ID):
    """Event 0x217A NotifyPlayerDied (exec 0x8ab2e0 -> 0xa67110): u8 0 | u64 victim | u32 victim icon | u32 victim
    team | u64 killer | u32 killer team | list<u32> killer + assists (icons)."""
    icons = [int(i) for i in icons]
    body = (b"\x00" + struct.pack("<QIIQI", victim, victim_icon, victim_team, killer, killer_team)
            + struct.pack("<I", len(icons)) + b"".join(struct.pack("<I", i) for i in icons))
    return build_message(dest, 0x217A, body)


def pvp_team_health_initial(teams, start, current):
    """Notice 0x100004FB InitialTeamHealthUpdate: list<u32> teams | list<u32> start health | list<u32> health."""
    return _notice(0x100004FB, _pvp_u32_lists(teams, start, current))


def pvp_team_health(teams, current):
    """Notice 0x10000134 UpdateTeamHealth (answer to client 0x10000137, and on every change): list<u32> teams |
    list<u32> health (rounded up)."""
    return _notice(0x10000134, _pvp_u32_lists(teams, current))


def pvp_tracker_status(entity, team, contender, lock, icon, hud_position, category, decoration=0, extra=(),
                       dest=LOCAL_PLAYER_ID):
    """Event 0x2069 (handler 0xa5a680 -> UI_UpdateTrackerStatus): u8 0 | u64 entity | 11 x u32: owner team,
    contending team, locked-to team (TeamUsageLock), icon DID, HUD position, map-note category, decoration, then
    four not yet named (0). A pip is matched by (category, HUD position)."""
    vals = ([team, contender, lock, icon, hud_position, category, decoration] + list(extra) + [0] * 11)[:11]
    return build_message(dest, 0x2069, b"\x00" + struct.pack("<Q", entity)
                         + struct.pack("<11I", *[int(v) & 0xFFFFFFFF for v in vals]))


def pvp_surrender_status(votes, expected, can_vote, remaining, total):
    """Notice 0x10000455 UpdateSurrenderData (reader 0x90b3d0): u32 n | n x u8 vote | u32 expected votes | u8 can
    vote | f32 time remaining | f32 total time."""
    blob = struct.pack("<I", len(votes)) + bytes(1 if v else 0 for v in votes)
    return _notice(0x10000455, blob + struct.pack("<IBff", expected, 1 if can_vote else 0, float(remaining),
                                                  float(total)))


def pvp_surrender_end():
    """Notice 0x10000456 (empty): the vote is over (buttons off, the panel closes after 2 s)."""
    return _notice(0x10000456, b"")


def _pvp_timeline_desc(handle, iid, severity, icon, tint, team, event_time, title, text, examination_icon=None):
    # [5] the strip's icon (0 = the default marker), [6] the hover tooltip's picture (Flash EventTimelineTooltip
    # m_IconContainer.SetIcon(didExaminationIcon)); None = the strip's icon, as before (timeline-tooltip-camp-prespawn.md)
    icon2 = icon if examination_icon is None else examination_icon
    return (struct.pack("<IQ", handle, iid) + struct.pack("<IIIBI", severity, icon, icon2, tint, team)
            + struct.pack("<d", float(event_time)) + b"\x00" + struct.pack("<I", 1)
            + string_any(title) + string_any(text) + struct.pack("<I", 7))


def pvp_timeline_start(now=None, iid=LOCAL_PLAYER_ID):
    """Notices 0x100002AF / 0x100002B1: StartTimeline(ttCurrentTime), both before any event. 2026-10-25
    (hud-shop-timeline-kills.md 2, C: reader 0x941620 passes the 8 bytes to Flash as a double): the payload is the
    f64 game time now; an IID read as a double (~0) put every event millions of pixels off the strip."""
    payload = struct.pack("<d", float(now)) if now is not None else struct.pack("<Q", iid)
    return [("timeline start (0x100002af)", _notice(0x100002AF, payload)),
            ("timeline start (0x100002b1)", _notice(0x100002B1, payload))]


def pvp_timeline_event(handle, event_time, now, title="", text="", severity=2, icon=0, team=0, iid=LOCAL_PLAYER_ID,
                       examination_icon=None):
    """Notice 0x100002AB AddTimelineEvent: descriptor {Handle{u32, u64} u32 severity u32 icon u32 icon2 u8 tint
    u32 team f64 time u8 {u32 n {StringInfo title, StringInfo text, u32}}} | {u32 n ...} (empty) | f64 now.
    icon = the strip's icon, examination_icon = the hover tooltip's picture (None = icon)."""
    desc = _pvp_timeline_desc(handle, iid, severity, icon, 0, team, event_time, title, text, examination_icon)
    return _notice(0x100002AB, desc + struct.pack("<I", 0) + struct.pack("<d", float(now)))


def pvp_timeline_banner(handle, countdown, now, title="", text="", severity=1, icon=0, team=0, iid=LOCAL_PLAYER_ID):
    """Notice 0x10000424 AddTimelineBanner: the descriptor (its time = the countdown's end, < 0 none) | f64 now.
    Severity 1 High / 2 Medium / 3 Low (colour and sound)."""
    desc = _pvp_timeline_desc(handle, iid, severity, icon, 0, team, countdown, title, text)
    return _notice(0x10000424, desc + struct.pack("<d", float(now)))


def pvp_timeline_remove(handle, iid=LOCAL_PLAYER_ID):
    """Notice 0x100002AC: remove a banner / timeline event by its handle {u32, u64}."""
    return _notice(0x100002AC, struct.pack("<IQ", handle, iid))


def pvp_announcement(kind, text="", source_icon=0, target_icon=0, source_team=-1, target_team=-1, use_target=False):
    """Notice 0x100002EB ShowAnnouncement with its billboard type: 2 generic (kill / structure), 6 location, 7 tie,
    8 loss, 9 win, 10 team 2 victory, 11 team 1 victory."""
    return show_announcement(text, kind, source_icon, target_icon, source_team, target_team, use_target)


def pvp_map_marker(iid, position, icon):
    """Event 0x20D2 (exec 0x8ba4c0 -> MapManager 0xa4c660): u8 0 | u64 IID | Position | u32 icon: a static map
    note (category 0x17) for a site with no entity. position = (region, lb x, lb y, cell, x, y, z)."""
    return build_message(LOCAL_PLAYER_ID, 0x20D2, b"\x00" + struct.pack("<Q", iid) + build_position(*position)
                         + struct.pack("<I", icon))


def pvp_dampener_counts(counts):
    """Event 0x215C (spectator top bar): u8 0 | list<u32> dampeners alive per team."""
    return build_message(LOCAL_PLAYER_ID, 0x215C, b"\x00" + struct.pack("<I", len(counts))
                         + b"".join(struct.pack("<I", int(c)) for c in counts))


def pvp_movement_state(object_id, now, position, heading, speed, module=(1, 1), tele_seq=1, second_seq=1,
                       facing_offset=0.0, parent=None, pitch=None, roll=None, vel_pitch=None):
    """A 0x4 batch with only the 0xB0 movement block: one timestamped state the client dead-reckons from (pos +
    velocity x (t - time)). It reaches the same listener 0x60AFA0 as a full bundle's (exec 0x698CD0 -> 0x6298D0; C,
    docs/re-notes/object-update-bundles.md 1 / 4; the fase3-hx bot's 0xB0-only death stop was applied in the game).
    2026-10-28 15:00 (tester report 2026-10-28 15:00): parent = the attach block of create_object (flag 0x04), so an
    attached object moves, attaches and detaches with motion-only states too (World.delta)."""
    return build_message(object_id, 0x4, build_batch([(0xB0, movement_block(
        now, position, heading, speed, module, tele_seq, second_seq, facing_offset, parent, pitch, roll, vel_pitch))]))


EVT_REMOVE_PROPERTY = 0x86


def remove_property(object_id, prop):
    """2026-10-28 15:00 (tester report 2026-10-28 15:00; docs/re-notes/object-update-bundles.md 1 / 12.1, C): event 0x86
    (factory 0x6912A0, flags 0x300400 as 0x6; serializer 0x839500 = u8 base | u32 id; exec 0x699210 -> 0x6353B0 ->
    property component vt+0x54 = 0x577E10, the remover a full bundle's 0xBC runs on each id it leaves out): u8 0 |
    u32 id. Notifies "removed", or "changed" back to the class template's value (0x577F90)."""
    return build_message(object_id, EVT_REMOVE_PROPERTY, b"\x00" + struct.pack("<I", prop & 0xFFFFFFFF))


# ---- combat (script VM): docs/re-notes/full-combat-skills.md, layouts C from the client's readers ----------------

def _handle(n, iid):
    """Handle{u32, u64}: the server's number and the IID it belongs to."""
    return struct.pack("<IQ", n & 0xFFFFFFFF, iid & 0xFFFFFFFFFFFFFFFF)


def vital_word(value):
    """One vital value of 0x42 as the client's serializer 0x96D360 writes it: |v| < 16384 a 15-bit signed u16, else
    u16 (v >> 16) | 0x8000 then u16 v & 0xFFFF. (The client's reader 0x96D3F0 keeps only the second word, shifted up
    by 16, so values >= 16384 still read wrong there; IC's vitals stay far below that.)"""
    v = int(value)
    if v == 0 and value:
        v = 1 if value > 0 else -1
    if -0x4000 <= v <= 0x3FFF:
        return struct.pack("<H", v & 0x7FFF)
    return struct.pack("<HH", ((v >> 16) & 0x7FFF) | 0x8000, v & 0xFFFF)


def vitals_long(object_id, pairs, first=None, second=None, vots=()):
    """0x42 with the client's own value encoding (vital_word): u8 0 | cint n | n x {cur, max} | cint m | m x {cur, max}
    | cint k | k x VOT | u8. second: the second list's pairs (P: temp vitals / shields); vots: [(vital, id, flag,
    [(u8, amount)])] (the client predicts regen / DoT ticks with them)."""
    first = VITALS_FIRST_LIST if first is None else first
    data = b"".join(vital_word(c) + vital_word(m) for c, m in pairs)
    zeros = b"".join(vital_word(0) + vital_word(0) for _ in pairs)
    if second is not None:
        a, b, nb = data, b"".join(vital_word(c) + vital_word(m) for c, m in second), len(second)
    else:
        a, b = (data, zeros) if first else (zeros, data)
        nb = len(pairs)
    body = bytes([0]) + pack_compact(len(pairs)) + a + pack_compact(nb) + b + pack_compact(len(vots))
    for vital, vid, flag, amounts in vots:
        body += bytes([vital & 0xFF, vid & 0xFF, 1 if flag else 0]) + pack_compact(len(amounts))
        body += b"".join(bytes([u & 0xFF]) + vital_word(x) for u, x in amounts)
    return build_message(object_id, 0x42, body + bytes([0]))


def _value(kind, value):
    """Value (0x456CE0): u32 type | payload; 0 bool u8, 1 int32, 3 f32, 4 DID, 8 IID."""
    if kind == KIND_BOOL:
        return struct.pack("<IB", 0, 1 if value else 0)
    if kind in (KIND_INT, 0x13):
        v = float(value) if isinstance(value, (int, float)) else 0.0
        # a script's NaN / inf (an unset operand divided) must not stop the message (2026-10-25, Teleport sweep)
        return struct.pack("<Ii", 1, int(v) if v == v and abs(v) < 2 ** 31 else 0)
    if kind == KIND_DID:
        return struct.pack("<II", 4, int(value) & 0xFFFFFFFF)
    if kind == KIND_IID:
        return struct.pack("<IQ", 8, int(value))
    return struct.pack("<If", 3, float(value))


def attribute_modifier_add(object_id, attr, source, handle_n, op, kind, value, team=-1):
    """0x20F0 (handler 0xAA0EC0): u8 0 | u32 attr | u64 source | Handle | u32 op | Value | u32 team (-1 = own list)."""
    body = (b"\x00" + struct.pack("<IQ", attr, source) + _handle(handle_n, object_id) + struct.pack("<I", op)
            + _value(kind, value) + struct.pack("<i", team))
    return build_message(object_id, 0x20F0, body)


def attribute_modifier_remove(object_id, attr, handle_n):
    """0x20E8 (handler 0xAA0EF0): u8 0 | u32 attr | Handle."""
    return build_message(object_id, 0x20E8, b"\x00" + struct.pack("<I", attr) + _handle(handle_n, object_id))


def skill_error(slot, error, dest=LOCAL_PLAYER_ID):
    """0x20DC (0xA0E3E0): u8 0 | u32 slot | u32 ErrorType: the execute-skill error popup."""
    return build_message(dest, 0x20DC, b"\x00" + struct.pack("<iI", slot, error))


def skill_script_event(agent, slot, event, dest=LOCAL_PLAYER_ID):
    """0x20C9 (serializer 0x849ce0, handler 0xa1d400 -> 0xa16e60): u8 0 | u64 agent | u32 slot | u32 1 | u32 event |
    u8 0: raises a ScriptEvent on the client copy of the slot's skill script (0x1000001D skill used ends the range
    indicator, 0x10000009 interrupt). docs/re-notes/targeting-indicator-and-structures.md."""
    return build_message(dest, 0x20C9, b"\x00" + struct.pack("<QiII", agent, slot, 1, event) + b"\x00")


def skill_availability(agent, slot, available, dest=LOCAL_PLAYER_ID):
    """0x20F9 (serializer 0x839550, handler 0xa2a1b0): u8 0 | u64 agent | u32 slot | u8 available. Raises ScriptEvent
    0x100000B6 (available = 0) / 0x100000B7 (1) with parameter SkillSlot (0x31D944) on the client copy of the slot's
    skill script (0xa16e60). The Super Strength throw sub-skills' client script 0x340001A3 shows the slot's targeting
    indicator on 0x100000B6 and hides it on 0x100000B7 (docs/re-notes/throw-truck-padlock.md 1)."""
    return build_message(dest, 0x20F9, b"\x00" + struct.pack("<QiB", agent, slot, 1 if available else 0))


def slot_indicator_start(slot, dest=LOCAL_PLAYER_ID):
    """0x2180 (serializer 0x839500, handler 0xa6d800): u8 0 | u32 slot. Starts the slot's targeting indicator with no
    targeting-state gate (ends the one shown, sets the HUD targeting display's +0x60 = slot, draws 0xa39360: range
    decal, stat-23 ring, cursor area that 0xa29680 keeps on the cursor) (docs/re-notes/throw-padlock-coredeath.md 1)."""
    return build_message(dest, 0x2180, b"\x00" + struct.pack("<i", slot))


def slot_indicator_end(slot, interrupted=False, dest=LOCAL_PLAYER_ID):
    """0x217F (serializer 0x83f690, handler 0xa5d070 -> 0xa4f0c0(slot, u8, 1, 0)): u8 0 | u32 slot | u8. Ends the
    slot's indicator (the decals only; the HUD targeting state is kept)."""
    return build_message(dest, 0x217F, b"\x00" + struct.pack("<iB", slot, 1 if interrupted else 0))


def entity_script_event(entity, event, script, dest=LOCAL_PLAYER_ID):
    """0x2008 (handler 0xAA1BF0 on the entity's effects component, map-runtime-state.md 3, P delivery): u8 0 | u64
    entity | u32 event | u32 script DID: an event for the client's own copy of one of the entity's 0x8E scripts."""
    return build_message(dest, 0x2008, b"\x00" + struct.pack("<QII", entity, event, script))


def skill_resource_error(slot, kind, dest=LOCAL_PLAYER_ID):
    """0x2092 (0xA2A190): u8 0 | u32 slot | u32 kind: out-of-resource popup; kind 2 = health, else energy."""
    return build_message(dest, 0x2092, b"\x00" + struct.pack("<iI", slot, kind))


def skill_disable_condition(slot, error, handle_n, iid, add, dest=LOCAL_PLAYER_ID):
    """0x20A0 (0xA6DD10): u8 0 | u32 slot (-2 all) | u32 ErrorType | Handle | u8 add."""
    return build_message(dest, 0x20A0, b"\x00" + struct.pack("<iI", slot, error) + _handle(handle_n, iid)
                         + bytes([1 if add else 0]))


def skill_usable_override(agent, slot, enable, flag, dest=LOCAL_PLAYER_ID):
    """0x207B (0xA26570): u8 0 | u64 agent | u32 slot | u8 enable | u8 flag."""
    return build_message(dest, 0x207B, b"\x00" + struct.pack("<Qi", agent, slot)
                         + bytes([1 if enable else 0, 1 if flag else 0]))


NOTICE_SKILL_UI_OVERLAY = 0x1000015A


def skill_ui_overlay(slot, overlay, on):
    """Notice 0x1000015A (GM_Skill.RecvNotice_UpdateSkillUIOverlay): u32 slot | u32 overlay | u8 on."""
    return _notice(NOTICE_SKILL_UI_OVERLAY, struct.pack("<iIB", slot, overlay, 1 if on else 0))


def induction(agent, elapsed, dest=None):
    """0x2077 (0xAA2570): u8 0 | u64 agent | u64 | f32 elapsed: the cast bar (elapsed / agent f32 0x100004FD)."""
    return build_message(dest or agent, 0x2077, b"\x00" + struct.pack("<QQf", agent, 0, float(elapsed)))


def induction_complete(agent, dest=None):
    """0x20CE (0xA9E590): u8 0 | u64 agent | u64."""
    return build_message(dest or agent, 0x20CE, b"\x00" + struct.pack("<QQ", agent, 0))


def induction_cancelled(agent, dest=None):
    """0x2096 (0xAA2620): u8 0 | u64 agent | u64."""
    return build_message(dest or agent, 0x2096, b"\x00" + struct.pack("<QQ", agent, 0))


def _icon_tail(source, end_time, duration, source2=0, tooltip_icon=0):
    """The common tail of 0x20C8 / 0x20A8 after u32 | u32: StringInfo | u64 source | u64 end time (f64) | u32
    duration (f32) | u64 | Tooltip{StringInfo u32 u32 {u32 count}} | u32 icon (byte layout C, field mapping P)."""
    tooltip = string_info("") + struct.pack("<III", 0, 0, 0)
    return (string_info("") + struct.pack("<Q", source) + struct.pack("<d", float(end_time))
            + struct.pack("<f", float(duration)) + struct.pack("<Q", source2) + tooltip
            + struct.pack("<I", tooltip_icon))


def status_icon_add(agent, icon, handle_n, stacks=0, source=0, end_time=0.0, duration=0.0, priority=0xFFFFFFFF):
    """0x20C8 (handler 0xAB2D30): add a status icon to the agent's row."""
    body = (b"\x00" + struct.pack("<QI", agent, icon) + _handle(handle_n, agent)
            + struct.pack("<II", priority & 0xFFFFFFFF, stacks) + _icon_tail(source, end_time, duration))
    return build_message(agent, 0x20C8, body)


def status_icon_update(agent, handle_n, stacks=0, source=0, end_time=0.0, duration=0.0, priority=0xFFFFFFFF):
    """0x20A8 (handler 0xAB3250): new stack count / end time of an icon."""
    body = (b"\x00" + struct.pack("<Q", agent) + _handle(handle_n, agent)
            + struct.pack("<II", priority & 0xFFFFFFFF, stacks) + _icon_tail(source, end_time, duration))
    return build_message(agent, 0x20A8, body)


def status_icon_remove(agent, handle_n):
    """0x20E9 (handler 0xAB38D0): u8 0 | u64 agent | Handle | u8 1."""
    return build_message(agent, 0x20E9, b"\x00" + struct.pack("<Q", agent) + _handle(handle_n, agent) + b"\x01")


def status_icon_tooltip(agent, handle_n, icon, pairs):
    """0x20D0 (handler 0xAB1500): u8 0 | u64 | Handle | u32 icon | {u8 cint {u32 index, u32 attribute}} |
    {u8 cint {u32 index, u32 value bits}}."""
    a = b"\x00" + pack_compact(len(pairs)) + b"".join(struct.pack("<II", i, attr) for i, attr, _v in pairs)
    b = b"\x00" + pack_compact(len(pairs)) + b"".join(struct.pack("<If", i, float(v)) for i, _attr, v in pairs)
    return build_message(agent, 0x20D0, b"\x00" + struct.pack("<Q", agent) + _handle(handle_n, agent)
                         + struct.pack("<I", icon) + a + b)


def status_icon_refresh(agent, handle_n):
    """0x2127 (handler 0xAB15D0): u8 0 | u64 | Handle."""
    return build_message(agent, 0x2127, b"\x00" + struct.pack("<Q", agent) + _handle(handle_n, agent))


def floaty_status(entity, kind, dest=LOCAL_PLAYER_ID):
    """0x20BD (0xA16E20 -> GM_Vitals.RecvNotice_DisplayFloatyStatus): u8 0 | u64 entity | u32 status id."""
    return build_message(dest, 0x20BD, b"\x00" + struct.pack("<QI", entity, kind))


def teleport_effects(entity, start, dest=LOCAL_PLAYER_ID):
    """0x218A start / 0x2189 stop the teleport effects (MapManager): u8 0 | u64 entity."""
    return build_message(dest, 0x218A if start else 0x2189, b"\x00" + struct.pack("<Q", entity))


def root_counter(entity, on, dest=LOCAL_PLAYER_ID):
    """0x2198 (0xA1A540): u8 0 | u64 | u8 on (the counter node 0x100001B8 drives)."""
    return build_message(dest, 0x2198, b"\x00" + struct.pack("<QB", entity, 1 if on else 0))


def destruction_sphere(object_id, position, radius, magnitude, level, key, fx, flag=0):
    """0x8A (0x632590 -> 0x632370): u8 0 | Position | f32 radius | f32 magnitude | u32 level | u32 key | u32 FX | u8."""
    body = (b"\x00" + build_position(*position) + struct.pack("<ffIII", radius, magnitude, level, key, fx)
            + bytes([1 if flag else 0]))
    return build_message(object_id, 0x8A, body)


def destruction_box(object_id, position, half_extents, magnitude, level, key, fx, flag=0):
    """0x1 (0x632560 -> 0x6322F0): u8 0 | Position | vec3 half extents | f32 magnitude | u32 level | u32 key | u32 FX
    | u8."""
    body = (b"\x00" + build_position(*position) + struct.pack("<fff", *half_extents)
            + struct.pack("<fIII", magnitude, level, key, fx) + bytes([1 if flag else 0]))
    return build_message(object_id, 0x1, body)


def _guid(guid):
    g = guid & ((1 << 128) - 1)
    return struct.pack("<IHHQ", g & 0xFFFFFFFF, (g >> 32) & 0xFFFF, (g >> 48) & 0xFFFF, g >> 64)


def effect_add(object_id, guid, script_did, fresh=True):
    """0x200F (handler 0xA9FB00): one script instance (a status effect) on the agent's effects component, with an
    empty variable store: cint 0 | cint 0 | u32 0 | u32 0 | GUID (u32 u16 u16 u64) | u8 0 | u32 script | u8 0, then
    u8 fresh (client-status-effects.md 3)."""
    inst = (pack_compact(0) + pack_compact(0) + struct.pack("<II", 0, 0) + _guid(guid) + b"\x00"
            + struct.pack("<I", script_did) + b"\x00")
    return build_message(object_id, 0x200F, b"\x00" + inst + bytes([1 if fresh else 0]))


def effect_remove(object_id, guid):
    """0x202B (handler 0xAA4220): u8 0 | GUID."""
    return build_message(object_id, 0x202B, b"\x00" + _guid(guid))
