"""Sessions and the match loading sequence.

One Session per login connection (the "user server" link). A Match is created
when the player accepts a queue and lives until the game connection closes.
Every step of the match load waits for the client message that makes it safe,
instead of the fixed sleeps the old server used:

  JoinQueue 0x20EB           -> QUEUED       joined queue + match found
  AcceptMatch 0x20CA         -> REFERRED     lobby room + referral to the game port
  game connection hello      -> GAME_CONNECTED   welcome, ServerSwitch, 0x20AF, 0x2016
  ConnectToLobby 0x20F2      -> LOBBY        lobby slot / state / room checks
  (min delay AND load %) ---> LOADING      champion + player objects created
  load-complete notice 0x2   -> IN_WORLD     intro cinematic after cinematic_delay
  cinematic finished 0x2     -> PLAYING      tutorial script starts
"""
import math
import os
import struct
import threading
import time

from . import log
from . import messages as M
from . import stolenpowers
from . import progress
from . import tutorial1
from .crypto import find_session_key_blob
from .scheduler import Group
from .wire import KIND_ARRAY, KIND_BOOL, KIND_DID, KIND_IID, KIND_INT, KIND_TABLE, FrameReader, parse_client_position
from .world import Combat, Entity, Mover

CONNECTED, MENU, QUEUED, REFERRED, GAME_CONNECTED, LOBBY, LOADING, IN_WORLD, PLAYING = (
    "CONNECTED", "MENU", "QUEUED", "REFERRED", "GAME_CONNECTED", "LOBBY", "LOADING", "IN_WORLD", "PLAYING")
MATCH_PHASES = (REFERRED, GAME_CONNECTED, LOBBY, LOADING, IN_WORLD, PLAYING)

NOTICE_LOAD_COMPLETE = bytes.fromhex("5e010010")   # notice 0x1000015e
NOTICE_CINEMATIC = bytes.fromhex("17010010")       # notice 0x10000117: u32 state | u32 DID
ENTITY_BASE_ID = 0x0200000000000100                # server-created entities (drones, scenery)
CMD_ATTACK, CMD_ATTACK_MOVE, CMD_MOVE, CMD_STOP = 2, 3, 4, 6
CMD_SKILL = 9     # the client's command sender (rva 0x670030) treats 2 and 9 alike: targeted abilities


RANK_BURST_GAP = 0.08             # s: rank queries closer than this are a HUD refresh
RANK_SKILL_MAGIC = 0x52414E4B     # ping type sent by the patched client for the skill "+"


class Match:
    def __init__(self, session, encounter, qflags):
        cfg = session.cfg
        mc, cc = cfg["match"], cfg["combat"]
        self.session = session
        self.cfg = cfg
        self.encounter, self.qflags = encounter, qflags
        self.group = Group(f"match s{session.sid}")
        self.champion = mc["champion"]
        self.team = mc["team"]
        self.room_id = mc["room_id"]
        self.vitals = [tuple(mc["health"]), tuple(mc["secondary"])]
        self.mover = Mover(mc["spawn"], cfg["timing"]["move_speed"])
        self.mover.ground_z = float(mc.get("ground_z", 0.0) or 0.0)
        self.combat = Combat(cc["basic_attack_damage"], cc["attack_interval"], cc["attack_range"])
        self.module = (1, 1)            # movement module: seq 1, type 1 (character replay)
        # Property 0x90F on the champion: the client hides entities that have it
        # (visibility test rva 0x21cb30: 0x2A1 && 0x76A && !0x90F; the cinematic
        # player sets it on the entities it hides). None = not sent.
        self.champion_hidden = None
        self.in_world = False
        self.sequence = 0               # object bundle sequence (0 = not created yet)
        self.seq_base = 0               # added on the wire (a second match in the same login)
        self.linked = False             # player -> champion link sent
        self.lobby_at = None
        self.percent = 0
        self.cinematic_sent = False
        self.last_move_tick = None
        self.last_motion = 0.0
        self.ping_count = 0
        self.scriptlet_runs = 0         # instance numbers for event 0x8D (new number = new run)
        self.attack_count = 0
        self.level, self.xp, self.skill_points = 1, 0, 0   # the first point comes with level 2
        self.skill_ranks = 0     # 4 bits per skill slot, sent as tutorial1.SKILL_RANKS_PROPERTY
        self.stolen_power = 0    # skill DID of slot 7 (D), 0 = none (old test: sent as a DID)
        self.stolen_powers = {}  # slot (7 D, 8 F) -> the skill collection (icserver/skilldata.py)
        self.hud_refresh = 0     # toggled to make the client refresh the skill buttons
        self.entities = {}              # eid -> Entity
        self._next_eid = ENTITY_BASE_ID
        tc = cfg["tutorial"]
        walk = tc.get("walk_targets") or tc["targets"]
        self.tutorial = (tutorial1.Tutorial(self, walk, len(walk) + 1)
                         if encounter == tutorial1.ENCOUNTER else None)

    @property
    def second_seq(self):
        return 1 if self.in_world else 0

    # ---- champion + player objects ---------------------------------------------------
    def _common(self):
        return dict(position=self.mover.position(), sequence=self.sequence + self.seq_base, heading=self.mover.heading,
                    speed=self.mover.speed, tele_seq=self.mover.tele_seq, second_seq=self.second_seq,
                    module=self.module)

    def champion_bundle(self, now):
        champ = self.session.server.champion_info(self.champion)
        props = M.champion_properties(champ["name"], self.team, champ["icon"],
                                      self.level, self.xp, self.skill_points,
                                      move_speed=self.cfg["match"].get("anim_move_speed") or None)
        if self.champion_hidden is not None:
            props = props + [(0x90F, KIND_BOOL, bool(self.champion_hidden))]
        icon = int(self.cfg["match"].get("champion_map_icon", 0x13000376) or 0)
        if icon:
            # minimap: "show on the map" + the note icon (map manager rva
            # 0x64b150); 0x13000376 = the tutorial avatar's own (0x2E0001B2)
            props = props + [(0x100007D8, KIND_BOOL, 1), (0x10000083, M.KIND_DID, icon)]
        if self.stolen_power:
            # the skill of slot 7 (Secondary1, the D button): table at VA 0x15EDA28
            props = props + [(0x100008F0, M.KIND_DID, self.stolen_power)]
        for slot, table in sorted(self.stolen_powers.items()):
            # a Stolen Power slot holds the skill's whole definition (a property
            # collection, value kind 0x0B), built from the game data
            props = props + [({7: 0x100008F0, 8: 0x100008F1}[slot], KIND_TABLE, table)]
        if self.skill_ranks or self.level >= 2:
            props = props + [(tutorial1.SKILL_RANKS_PROPERTY, KIND_INT, self.rank_property())]
        if self.cfg["match"].get("rank_array", True):
            # The client's own skill rank (rva 0x463ce0): champion property
            # 0x100000AF, an array of ints indexed by skill slot. Without it
            # every skill is rank 0 and Q cannot be cast. (2026-10-15: 8
            # elements, for the Stolen Power on slot 7, coincided with Batman
            # walking off for good on the client: back to 6.)
            # 2026-10-16: sent from the first bundle on, with the basic attack
            # (slot 0) at rank >= 1: a rank-0 button is drawn grey (locked).
            ranks = [(self.skill_ranks >> (4 * slot)) & 0xF for slot in range(6)]
            ranks[0] = max(ranks[0], int(self.cfg["match"].get("basic_attack_rank", 1)))
            props = props + [(tutorial1.RANK_ARRAY_PROPERTY, KIND_ARRAY,
                              [(tutorial1.RANK_ELEMENT_PROPERTY, KIND_INT, r) for r in ranks])]
        out = M.create_object(M.CHAMPION_AGENT_ID, self.cfg["match"]["agent_class"], now,
                              properties=self._lighting(props), **self._common())
        if self.cfg["match"].get("vitals_with_bundle", True):
            # 2026-10-16 (static analysis): Flash's skill bar reads the champion's
            # Will when it is set up (at the link) and only updates it on a vitals
            # change; with no 0x42 before that, Will = 0 and every skill with a
            # cost (Q/W/E) kept the "not enough Will" dull look
            out += M.vitals(M.CHAMPION_AGENT_ID, self.vitals)
        return out

    def preload_stolen_powers(self):
        """[tutorial] stolen_powers_from_start: D and F get their skill data in
        the first bundle. Flash sets up only the slots that have a skill at the
        link; slots given later never got their icon (and showed the level).
        Their HUD buttons stay hidden until the tutorial grants them."""
        tc = self.cfg["tutorial"]
        if not self.tutorial or not tc.get("stolen_powers_from_start", True):
            return
        from . import skilldata
        for slot, key, default in ((7, "camera_skill", skilldata.CAMERA_VERSION),
                                   (8, "strength_skill", skilldata.SUPER_STRENGTH_VERSION)):
            if slot not in self.stolen_powers:
                table = skilldata.slot_table(self.cfg, slot, stolenpowers.resolve(tc.get(key), default))
                if table:
                    self.stolen_powers[slot] = table

    def rank_property(self):
        """What the patched client reads from SKILL_RANKS_PROPERTY.

        2026-10-15: the HUD skill loop (VA 0xa7c8b1) passes the nibble that
        caves A/B return as SkillUpdate's eCanRankSkill, an ErrorType: 0 =
        None_ErrorType = the "+" shows. It is NOT the rank (the HUD's rank comes
        from the 0x100000AF array): with the rank there, every rank-0 skill showed
        a "+" and a rank-1 skill never did (Q could not be upgraded to rank 2).
        So per slot 0-6: 0 = this slot may be ranked now, 1 = not; bits 28-31 =
        recommended slot + 1 (caves C and E2). The slot-6 nibble (Recall, never
        ranked) toggles 1/2 to force a HUD refresh (cave D) without other change."""
        allowed = self.tutorial.rank_slots() if self.tutorial else ()
        value = 0
        for slot in range(7):
            if slot in allowed and self.skill_points > 0:
                continue
            value |= (1 + (self.hud_refresh & 1 if slot == 6 else 0)) << (4 * slot)
        return value | (self.skill_ranks & 0xF0000000)

    def _lighting(self, props):
        """[match] lighting_env: the scene's lighting environment (property 0x956).
        0x10000016 lit the world on 2026-10-05, when without it the scene went
        almost black -- but then the fog of war had no vision source, so that
        black may have been the fog itself. 0 = don't send it (client default)."""
        env = int(self.cfg["match"].get("lighting_env", 0x10000016) or 0)
        out = [p for p in props if p[0] != 0x956]
        return out + [(0x956, M.KIND_ENUM, env)] if env else out

    def objects(self, link, now):
        links = ({M.PROP_CONTROLLED_AGENT: M.CHAMPION_AGENT_ID, M.PROP_PLAYER_ENTITY_LINK_2: M.CHAMPION_AGENT_ID}
                 if link else {})
        player_props = self._lighting(M.PLAYER_PROPERTIES + (M.player_late_properties(self.encounter)
                                                             if self.sequence >= 2 else []))
        if self.cfg["match"].get("player_team", True):
            # 2026-10-14: the player object had no team. The client's fog of war
            # has an "all teams" view (keymap SetAllFogOfWarVision) and pings are
            # coloured by their team against the player's: without a team the map
            # is all clear and every ping red (enemy). PVP_Team = the champion's.
            player_props = player_props + [(0x1000009C, KIND_INT, self.team)]
        return (self.champion_bundle(now)
                + M.create_object(M.LOCAL_PLAYER_ID, self.cfg["match"]["player_class"], now,
                                  iid_properties=links, properties=player_props, **self._common()))

    # ---- server entities -----------------------------------------------------------------
    def spawn(self, name, now, attackable=True, xyz=None, carrier_slot=None):
        """Create a layout entity by name (tutorial1.LAYOUT). Returns messages."""
        entry = tutorial1.LAYOUT.get(name) or tutorial1.EXTRA_SPAWNS.get(name)
        if not entry:
            log.info(f"spawn: '{name}' is not in the layout table", self.session)
            return []
        wstate, layout_xyz, yaw = entry
        yaw += tutorial1.MODEL_YAW_OFFSET.get(wstate, 0.0)
        xyz = xyz or layout_xyz
        cc = self.cfg["combat"]
        variant = tutorial1.VARIANTS.get(wstate) if cc["use_variants"] else None
        class_id = variant or (tutorial1.prop_class(wstate, self.cfg, carrier_slot) if wstate >> 24 == 0x2E else wstate)
        extra = []
        carrier = cc.get("prop_carrier") or 0
        if class_id >> 24 == 0x2E and carrier:
            # No entity names this world state (vehicle, meteor): create a known
            # placeable entity and give it the world state as property 0x510.
            extra = [(tutorial1.WSTATE_PROPERTY, KIND_DID, wstate)]
            class_id = carrier
        if class_id != wstate and wstate >> 24 == 0x2E:
            extra = extra + tutorial1.script_table_props(wstate, self.cfg)
        attackable = attackable and variant is not None
        eid = self._next_eid
        self._next_eid += 1
        ent = Entity(eid, name, class_id, xyz, yaw, cc["enemy_team"],
                     health=cc["drone_health"] if attackable else None, attackable=attackable)
        ent.extra_props = extra
        self.entities[eid] = ent
        log.info(f"spawn {name}: object {eid:#x} class {class_id:#x} at ({xyz[0]:.1f}, {xyz[1]:.1f})"
                 + ("" if attackable else " (scenery)"), self.session)
        out = [(f"spawn {name} ({class_id:#x})", self.entity_bundle(ent, now))]
        if attackable:
            out.append((f"{name} vitals (0x42)", M.vitals(eid, [(ent.health, ent.max_health)])))
        return out

    def move_entity(self, ent, xyz, now, speed=0.0, heading=None):
        """Send the entity walking/running to xyz (one bundle with its new
        position and speed; the client animates the motion). heading: keep
        this yaw instead of facing the motion (a tumbling thrown car)."""
        import math as _m
        dx, dy = xyz[0] - ent.pos[0], xyz[1] - ent.pos[1]
        if heading is not None:
            ent.heading = heading
        elif abs(dx) + abs(dy) > 1e-3:        # standing still keeps the heading set by the caller
            ent.heading = _m.atan2(dy, dx)  # (2026-10-14: atan2(0, 0) turned attacking drones to
                                            # face east, i.e. the vehicle)
        ent.pos = list(xyz)
        ent.speed = speed
        return [(f"{ent.name} moves to ({xyz[0]:.0f}, {xyz[1]:.0f})", self.entity_bundle(ent, now))]

    def entity_bundle(self, ent, now):
        ent.sequence += 1
        spawn = self.mover.spawn
        prop = (ent.class_id >> 24 == 0x2E or tutorial1.is_override_class(ent.class_id) or ent.class_id in tutorial1.PROP_CLASSES.values()
                or bool(getattr(ent, "extra_props", None)) or ent.name in tutorial1.STATIC_SCENERY)
        # Props carry the cell of the encounter layout (251 for every placement in
        # landblock 0x13cb); characters keep cell 0, which works for them.
        cell = self.cfg["combat"].get("scenery_cell", 251) if prop else 0
        pos = (spawn[0], 0x13, 0xCB, cell) + tuple(ent.pos)
        props = M.creature_properties(ent.team, ent.alive) if ent.attackable else []
        props = props + list(getattr(ent, "extra_props", []))
        if getattr(ent, "hidden", None) is not None:
            props.append((0x90F, KIND_BOOL, bool(ent.hidden)))     # out of Batman's sight
        module = self.module
        if ent.class_id >> 24 == 0x2E:      # bare world state = static prop (vehicle, gates, meteors)
            module = M.scenery_module(self.cfg)
        return M.create_object(ent.eid, ent.class_id, now, position=pos, sequence=ent.sequence,
                               heading=ent.heading, speed=getattr(ent, "speed", 0.0),
                               second_seq=self.second_seq, module=module, properties=props,
                               facing_offset=getattr(ent, "yaw_offset", 0.0))


class Session:
    _ids = iter(range(1, 1 << 30))

    def __init__(self, server, user_conn):
        self.server = server
        self.cfg = server.cfg
        self.sched = server.sched
        self.sid = next(Session._ids)
        self.user = user_conn
        self.user.session = self
        self.game = None
        self.phase = CONNECTED
        self.match = None
        self.group = Group(f"session {self.sid}")
        self.lock = threading.RLock()
        self.user_reader = FrameReader()
        self.game_reader = FrameReader()
        self.got_hello = False
        self.referred_at = 0.0
        self._rank_ping_last = (0.0, None)   # (monotonic time, slot) of the last skill-rank query
        if self.cfg["debug"]["dev_send_file"]:
            self.sched.every(1.0, self._dev_send_file, self.group)

    # ---- helpers -----------------------------------------------------------------
    def set_phase(self, phase, why=""):
        if phase != self.phase:
            old, self.phase = self.phase, phase
            log.info(f"phase {old} -> {phase}" + (f" ({why})" if why else ""), self)

    def send(self, label, data):
        """Everything goes out on the login connection (as in the old server,
        also replies to events that arrived on the game connection)."""
        return self.user.send(data, label)

    def send_many(self, labelled):
        return self.user.send_all(labelled)

    def later(self, delay, fn, group=None):
        def run():
            with self.lock:
                fn()
        self.sched.after(delay, run, group or self.group)

    def every(self, interval, fn, group, first_delay=None):
        def run():
            with self.lock:
                return fn()
        self.sched.every(interval, run, group, first_delay)

    # ---- login connection ------------------------------------------------------------
    def on_user_data(self, data):
        with self.lock:
            log.traffic("user <<", "recv", data, self)
            if not self.got_hello:
                self.got_hello = True
                self._hello(data)
                return
            for msg in self.user_reader.feed(data):
                self.handle(msg, "user")

    def _hello(self, data):
        blob = find_session_key_blob(data)
        if blob is None:
            log.info("hello without a session key blob (unexpected client?)", self)
        else:
            scheme, plain = self.server.key.decrypt_session_key(blob)
            if plain:
                log.info(f"login handshake OK (session key decrypted, {scheme})", self)
            else:
                log.info("WARNING: could not decrypt the session key. The patched exe and "
                         "keys\\server_private.pem do not match: run  python ic.py patch", self)
        self.send("welcome (0x40000)", M.hello_reply(time.time()))
        events = M.initial_events(self.server.roster, self.cfg["account"]["level"],
                                  self.cfg["account"]["player_name"])
        done = progress.completed(self.cfg)
        if self.cfg["tutorial"].get("send_achievements", True):
            # the training achievements' progress (scorecard.py): Tutorial n done
            # = its achievement completed; the Training Missions list and the
            # Mission Complete page's "next challenge" read it
            from . import scorecard
            n = 0
            while n + 1 in scorecard.TUTORIALS and scorecard.TUTORIALS[n + 1][1] in done:
                n += 1
            events = [(f"achievements (0x2120): {n} tutorial(s) done", scorecard.trainee_progress(completed=n))
                      if label.startswith("achievements (0x2120)") else (label, msg) for label, msg in events]
        if done:
            # before 0x2080, which must stay last (it opens the landing screen)
            events.insert(len(events) - 1, (f"completed encounters (0x214b): {', '.join(hex(d) for d in done)}",
                                            M.completed_encounters(done, done[-1])))
        self.send_many(events)
        self.set_phase(MENU, "account data sent")

    def on_user_closed(self):
        with self.lock:
            log.info("login connection closed", self)
            self.end_match("login connection closed")
            self.group.cancel()
            if self.game:
                self.game.close()

    # ---- game connection ------------------------------------------------------------
    def attach_game(self, conn):
        with self.lock:
            if self.game and not self.game.closed:
                log.info("a new game connection replaces the old one", self)
                self.game.close()
            self.game = conn
            conn.session = self
            self.game_reader = FrameReader()
            self.game_hello_done = False

    def on_game_data(self, data):
        with self.lock:
            log.traffic("game <<", "recv", data, self)
            if not self.game_hello_done:
                self.game_hello_done = True
                self._game_hello()
                return
            for msg in self.game_reader.feed(data):
                self.handle(msg, "game")

    def _game_hello(self):
        if self.match is None:
            log.info("game connection without a match (stale client?) -- answering anyway", self)
            self.match = Match(self, tutorial1.ENCOUNTER, 0)
        g = self.game
        m = self.match
        packs = list(self.cfg["match"]["packs"])
        enter = [("enter match (0x20af)", M.enter_match(m.encounter, m.champion, packs,
                                                        self.cfg["match"].get("extra_champions") or ())),
                 ("end room check 0 (0x2016)", M.end_room_check(0))]
        early = self.cfg["match"].get("enter_match_first", False)
        if early:
            # 22:07 (static analysis): every accepted 0x2016 arms a 60 s client
            # watchdog that only the game connection's "connected" status
            # clears; sent after it, the watchdog fired once the player left the
            # world: a second teardown + exit lobby + an error. Sent first now.
            self.send_many(enter)
        g.send(M.hello_reply(time.time()), "welcome/ConnectRequest (0x40000)")
        g.send(M.server_switch(1), "ServerSwitch (0x100)")
        if not early:
            self.send_many(enter)
        self.set_phase(GAME_CONNECTED)
        # 19:04: after the match the client keeps its game connection; with no
        # 'time' from the server for 60 s it dropped it with an error ("You
        # have been disconnected", "verify ports"). The keepalive belongs to
        # the connection, not to the match.
        self.every(self.cfg["timing"]["keepalive"], lambda g=g: self._keepalive(g), self.group)

    def _keepalive(self, g=None):
        g = g or self.game
        if g is None or g.closed or g is not self.game:
            return False
        g.send(M.time_packet(time.time()), "time")
        return True

    def on_game_closed(self, conn):
        with self.lock:
            if conn is not self.game:
                return
            log.info("game connection closed", self)
            self.end_match("game connection closed")

    def end_match(self, why):
        if self.match:
            self.match.group.cancel()
            self.match = None
            log.info(f"match ended: {why}", self)
        if self.phase in MATCH_PHASES or self.phase == QUEUED:
            self.set_phase(MENU, why)

    # ---- client events ----------------------------------------------------------------
    def handle(self, msg, via):
        log.traffic(f"{via} <<", f"event {msg.event_id:#x}", msg.body, self)
        handler = HANDLERS.get(msg.event_id)
        if handler is None or handler(self, msg) is NotImplemented:
            log.unhandled(msg, self)

    def ev_join_queue(self, msg):
        if len(msg.body) < 8:
            return NotImplemented
        if self.phase in MATCH_PHASES and self.match and getattr(self.match, "finished", False):
            # 15:55: after the victory and the post-match movie the client is back
            # on the home screen while its old game connection is still open
            # (no message says so); a new Launch must not be ignored
            g, self.game = self.game, None
            # 16:14: the second match in the same login stuck at 15% loading.
            # The client still holds the old world's objects at their last
            # sequence numbers; the next match continues the numbering and
            # first removes the old server objects (session.carry_over)
            old = self.match
            self.carry_over = {"sequence": old.sequence + old.seq_base + 16,
                               "stale": [eid for eid in old.entities]}
            if g and not g.closed:
                g.close()
            self.end_match("the previous match is over, queueing again")
        if self.phase not in MATCH_PHASES and self.game is not None:
            # 20:17: back home after a match, the old game connection is still
            # open (keepalive). The client closes it itself on the new referral;
            # that close used to end the NEW match, so the client's next game
            # connection got a bare stand-in match (objects from seq 1, stuck at
            # 15%, "Unable to connect to Match"). It is let go first.
            self.game = None
        if self.phase in MATCH_PHASES:
            if time.time() - self.referred_at < 30 or self.phase != REFERRED:
                log.info("JoinQueue ignored: a match is already being set up "
                         "(a second Launch click used to disconnect the client)", self)
                return
            self.end_match("referral timed out, queueing again")
        did, qflags = struct.unpack_from("<II", msg.body, 0)
        self.match = Match(self, did, qflags)
        carry = getattr(self, "carry_over", None)
        if carry:
            self.match.seq_base = carry["sequence"]
            self.match.stale_objects = list(carry["stale"])
            self.carry_over = None
        log.info(f"joined queue for encounter {did:#x}"
                 + ("" if self.match.tutorial else "  (no script for this map yet: objects only)"), self)
        self.send_many([(f"joined queue (0x20c0) {did:#x}", M.joined_queue(did, qflags)),
                        ("match found (0x20fa)", M.match_found(1, 30))])
        self.set_phase(QUEUED)

    def ev_accept_match(self, msg):
        if self.phase != QUEUED or not self.match:
            log.info(f"AcceptMatch ignored in phase {self.phase}", self)
            return
        m, s = self.match, self.cfg["server"]
        self.referred_at = time.time()
        self.server.expect_game(self)
        self.send_many([("players accepted (0x20ad)", M.players_accepted(1)),
                        ("lobby room created (0x2028)", M.lobby_room_created(m.encounter, m.qflags)),
                        (f"referral -> {s['host']}:{s['game_port']}", M.referral(s["host"], s["game_port"]))])
        self.set_phase(REFERRED)

    def ev_connect_to_lobby(self, msg):
        m = self.match
        if not m:
            log.info("ConnectToLobby without a match", self)
            return
        first = m.lobby_at is None
        reloading = getattr(m, "reload_pending", False)
        if first or reloading:
            m.lobby_at = time.monotonic()
        name = self.cfg["account"]["player_name"]
        out = []
        if first and getattr(self, "matches_entered", 0) and self.cfg["match"].get("resend_local_player", True):
            # 2026-10-15 (static analysis): the world teardown after a match sets
            # the client's local player id to 0 and only 0xEB sets it again; without
            # it the next match's player is never "local" and the load stops at 10 %
            out.append(("set local player again (0xeb)", M.set_local_player()))
        if first:
            self.matches_entered = getattr(self, "matches_entered", 0) + 1
        out += [("lobby player slot (0x2029)", M.lobby_player(m.champion, name, m.team, m.room_id)),
               ("lobby state (0x204c)", M.lobby_state(m.encounter, m.qflags, m.champion, m.room_id))]
        if self.cfg["match"].get("lobby_room_check", True):
            # (re-arms the client's 60 s watchdog; without it the first load stalled at 55 %)
            out.append(("end room check (0x2016)", M.end_room_check(m.room_id)))
        out += [
               ("all loaded? (0x206d)", M.all_loaded(m.room_id))]
        mode = self._match_start_mode()
        if mode == "lobby" or (mode == "reload" and first):
            out.append(("match start (0x2053)", M.match_start()))
        self.send_many(out)
        if reloading:
            # 2026-10-14: after 0x2053 the client goes back to the loading screen
            # and connects to the lobby again: THIS is the real match load.
            m.reload_pending = False
            m.percent = 0
            log.info("match started: the client reloads the match, objects follow this load", self)
            self.every(0.25, self._maybe_create_objects, m.group, first_delay=0.25)
            return
        if not first:
            log.info("ConnectToLobby repeated: lobby data re-sent", self)
            return
        self.set_phase(LOBBY)
        if mode == "reload":
            m.reload_pending = True
            log.info("match start (0x2053) sent: waiting for the client to reload", self)
            self.later(15.0, lambda: self._reload_timeout(), m.group)
            return
        # The objects wait for the conversation pack to finish loading (else
        # the tutorial's dialogue table stays "not loaded" for the whole match).
        self.every(0.25, self._maybe_create_objects, m.group, first_delay=0.25)

    def _reload_timeout(self):
        m = self.match
        if m and getattr(m, "reload_pending", False) and not m.sequence:
            m.reload_pending = False
            m.lobby_at = time.monotonic()
            log.info("no reload after 0x2053 within 15 s: creating the objects anyway", self)
            self.every(0.25, self._maybe_create_objects, m.group, first_delay=0.25)

    def ev_loading_percent(self, msg):
        if len(msg.body) < 4 or not self.match:
            return NotImplemented
        m = self.match
        m.percent = max(m.percent, struct.unpack_from("<I", msg.body, 0)[0])
        log.info(f"client loading {m.percent}%", self)
        self.send(f"lobby loading percent {m.percent} (0x2031)", M.loading_percent(m.team, m.percent, m.room_id))
        self._maybe_create_objects()

    def _maybe_create_objects(self):
        m = self.match
        if not m or m.sequence or m.lobby_at is None:
            return False
        if getattr(m, "reload_pending", False):
            return False                   # 0x2053 sent: wait for the client's reload
        t = self.cfg["timing"]
        waited = time.monotonic() - m.lobby_at
        ready = waited >= t["objects_min_delay"] and m.percent >= t["objects_min_percent"]
        if not ready and waited < t["objects_max_wait"]:
            return True                    # keep polling
        freed = getattr(self, "objects_freed_at", 0.0) + float(t.get("object_free_seconds", 0.0))
        if time.time() < freed:
            # 22:07 (static analysis): the client frees a removed object (0x3)
            # only 30 s later; a create with the same id before that updates
            # the old object and the load never moves on (stuck at 10-14 %)
            if not getattr(m, "free_wait_logged", False):
                m.free_wait_logged = True
                log.info(f"objects: waiting {freed - time.time():.0f} s more for the client to free "
                         "the previous match's objects", self)
            return True
        why = (f"{waited:.1f}s after lobby, client at {m.percent}%" if ready
               else f"fallback after {waited:.1f}s (client at {m.percent}%)")
        stale = getattr(m, "stale_objects", None)
        if stale and self.cfg["match"].get("remove_stale_objects", True):
            self.send_many([(f"old match object {eid:#x} removed (0x3)", M.remove_object(eid)) for eid in stale])
            log.info(f"objects: {len(stale)} objects of the previous match removed", self)
            m.stale_objects = None
        m.preload_stolen_powers()
        self._send_objects(link=False, label=f"create champion + player ({why})")
        self.set_phase(LOADING)
        self.later(t["link_delay"], self._link_objects, m.group)
        if t["idle_resend"] > 0:
            self.every(t["idle_resend"], self._idle_resend, m.group)
        self.every(1.0 / t["move_hz"], self._move_tick, m.group)
        return False

    def _objects(self, link):
        return self.match.objects(link, time.time())

    def _send_objects(self, link, label, bump=True):
        m = self.match
        if bump:
            m.sequence += 1
        m.linked = m.linked or link
        if label != "refresh":
            log.info(f"objects: {label} (seq {m.sequence})", self)
        return self.send(f"{label} seq {m.sequence}", self._objects(link))

    def _link_objects(self):
        if self.match:
            self._send_objects(link=True, label="link player -> champion")

    def _idle_resend(self):
        m = self.match
        if not m or not m.linked:
            return True
        if m.mover.target is None and time.monotonic() - m.last_motion > 1.0:
            self._send_objects(link=True, label="refresh")
        return True

    def _move_tick(self):
        m = self.match
        if not m or not m.sequence:
            return False
        now = time.monotonic()
        dt = now - m.last_move_tick if m.last_move_tick else 0.0
        m.last_move_tick = now
        changed = self._combat_step(m, now)
        if m.mover.tick(dt):
            changed = True
        self._vision(m)
        if not changed:
            return True
        m.last_motion = now
        if not self.user.send(self._objects(m.linked), None):
            return False
        if m.tutorial and m.tutorial.carrying():
            # the car overhead moves with him, in the same moment
            self.send_many(m.tutorial.finale.carry_tick(time.time()))
        if m.tutorial and m.tutorial.phase == "walk":
            msgs = m.tutorial.near_drone(time.time())
            if msgs:
                log.info("tutorial: reached the drone's area, drone appears", self)
                self.send_many(msgs)
        # the markers trigger when Batman walks INTO their area, not only when he
        # stops inside it (2026-10-14: the marker is not visible yet, so players
        # walk past it)
        passing = (m.tutorial is not None and m.combat.target is None
                   and m.tutorial.step in tutorial1.MOVE_STEPS and m.tutorial.at_target(passing=True))
        if m.mover.arrived or passing:
            stopped = m.mover.arrived
            m.mover.arrived = False
            if m.tutorial and m.combat.target is None:
                was_moving = m.mover.target is not None
                msgs = m.tutorial.arrived(time.time(), passing=not stopped)
                if msgs:
                    log.info(f"tutorial: reached target, now step {m.tutorial.step}", self)
                    self.send_many(msgs)
                    if was_moving and m.mover.target is None:   # stopped by the knockdown
                        m.last_motion = time.monotonic()
                        if not self.user.send(self._objects(m.linked), None):
                            return False
        return True

    def _vision(self, m):
        """Fog of war on the server: units Batman cannot see (farther than his
        vision radius, or behind a wall / the wagon / the vehicle) are hidden
        with property 0x90F, and shown again when he sees them (2026-10-14)."""
        tc = self.cfg["tutorial"]
        if not tc.get("fog_of_war", True):
            return
        radius = float(tc.get("vision_radius", 14.0))
        bx, by = m.mover.pos[0], m.mover.pos[1]
        now = time.time()
        # Batman and his surveillance cameras see ("With my cameras, our enemies
        # cannot hide from us!")
        sources = [(bx, by, radius)]
        cam_radius = float(tc.get("camera_vision_radius", 10.0))
        bridge = getattr(m.tutorial, "bridge", None) if m.tutorial else None
        for eid in (bridge.cameras if bridge else ()):
            cam = m.entities.get(eid)
            if cam is not None:
                sources.append((cam.pos[0], cam.pos[1], cam_radius))
        for ent in list(m.entities.values()):
            if (ent.class_id >> 24 != 0x40 or ent.class_id in tutorial1.PROP_CLASSES.values()
                    or ent.name in tutorial1.STATIC_SCENERY):
                continue                              # props (vehicle, gates) stay visible
            if getattr(ent, "no_fog", False):
                continue                              # e.g. the human running away (removed at the end)
            if getattr(ent, "removed", False) or (ent.attackable and not ent.alive):
                continue                              # gone: re-sending it would bring it back
            seen = False
            for sx, sy, r in sources:
                d = ent.distance_to((sx, sy))
                if d <= r and (d < 1.0 or m.mover.segment_clear(sx, sy, ent.pos[0], ent.pos[1])):
                    seen = True
                    break
            hidden = not seen
            if getattr(ent, "hidden", None) is None and not hidden:
                ent.hidden = False                    # created visible: nothing to send
                continue
            if getattr(ent, "hidden", None) != hidden:
                ent.hidden = hidden
                self.send(f"{ent.name} {'hidden (fog of war)' if hidden else 'seen again'}",
                          m.entity_bundle(ent, now))

    def _combat_step(self, m, now):
        """Walk into range of the attack target, face it and hit it every
        interval. Returns True when the champion's state changed."""
        c = m.combat
        ent = c.target
        if ent is None:
            return False
        if not ent.alive:
            c.stop()
            return False
        mv = m.mover
        dx, dy = ent.pos[0] - mv.pos[0], ent.pos[1] - mv.pos[1]
        dist = math.hypot(dx, dy)
        reach = getattr(ent, "hit_range", None) or c.range      # e.g. the Destroyer: hit from further away
        if dist > reach:
            k = (dist - reach * 0.8) / dist
            mv.target = [mv.pos[0] + dx * k, mv.pos[1] + dy * k, mv.pos[2]]
            return False
        changed = mv.target is not None or mv.speed != 0.0
        mv.target, mv.speed = None, 0.0
        face = math.atan2(dy, dx)
        if abs((face - mv.heading + math.pi) % (2 * math.pi) - math.pi) > 0.05:
            mv.heading = face
            changed = True
        if now >= c.next_hit:
            c.next_hit = now + c.interval
            self._hit(m, ent)
        return changed

    def _cast(self, m, ability, target, xyz):
        """A skill order: the ability number is the skill slot (1 Q, 2 W, 3 E,
        4 R, 7 = Secondary1, the Stolen Power on D)."""
        if not m.tutorial:
            return
        from . import abilities, batman
        if getattr(m, "cooldowns", None) is None:
            overrides = dict(self.cfg["combat"].get("cooldowns") or {})
            if not any(str(k) == str(batman.SLOT_R) for k in overrides):
                # the original's tutorial showed a 10 s Bat Scream cooldown (2026-10-15 video)
                overrides[batman.SLOT_R] = float(self.cfg["tutorial"].get("r_cooldown", 10.0))
            m.cooldowns = abilities.Cooldowns(abilities.GASLIGHT_BATMAN, overrides)
        slot = ability if ability else abilities.SLOT_Q
        if slot == batman.SLOT_D:
            log.info(f"skill slot {slot}: Stolen Power (surveillance camera)", self)
            self.send_many(m.tutorial.stolen_power(xyz, time.time()))
            return
        if slot == 8:
            log.info(f"skill slot {slot}: Stolen Power (Super Strength)", self)
            self.send_many(m.tutorial.super_strength(xyz, target, time.time()))
            return
        if m.tutorial.carrying():
            # 17:36: any scriptlet on Batman drops him out of the carry pose;
            # with the car overhead the skills wait for the throw
            log.info(f"skill slot {slot}: ignored while carrying the car", self)
            return
        if slot not in (batman.SLOT_Q, batman.SLOT_W, batman.SLOT_E, batman.SLOT_R):
            log.info(f"skill slot {slot}: not programmed yet", self)
            return
        if slot != batman.SLOT_Q and not (m.skill_ranks >> (4 * slot)) & 0xF:
            log.info(f"skill slot {slot}: not unlocked yet", self)
            return
        name = abilities.GASLIGHT_BATMAN.get(slot, {}).get("name", f"slot {slot}")
        left = m.cooldowns.remaining(slot, time.time())
        if left > 0 and self.cfg["combat"].get("enforce_cooldowns", True):
            log.info(f"{name}: on cooldown ({left:.1f} s left)", self)
            return
        if slot == batman.SLOT_R:
            msgs = m.tutorial.bat_scream(xyz, target, time.time())
            if msgs:
                self._start_cooldown(m, slot)
                self.send_many(msgs)
            return
        if slot in (batman.SLOT_W, batman.SLOT_E):
            if target is None and xyz:
                live = [e for e in m.entities.values() if e.alive and e.attackable]
                aim = float(self.cfg["tutorial"].get("skill_aim_radius", 3.0))
                near = [e for e in live if e.distance_to(xyz[:2]) <= max(aim, getattr(e, "click_radius", 0))]
                target = min(near, key=lambda e: e.distance_to(xyz[:2])) if near else None
            cast = m.tutorial.sonic_shell if slot == batman.SLOT_W else m.tutorial.bat_flight
            msgs = cast(xyz, target, time.time())
            if not msgs:
                return
            self._start_cooldown(m, slot)
            self.send_many(msgs)
            return
        self._start_cooldown(m, slot)
        live = [e for e in m.entities.values() if e.alive and e.attackable]
        if target is None or not target.alive:
            # cursor ON a drone (2026-10-14 16:02: within 5 m of the cursor hit
            # drones behind Batman's back; now only a direct aim or the line below)
            ref = xyz or tuple(m.mover.pos)
            radius = float(self.cfg["tutorial"].get("batarang_aim_radius", 1.5))
            near = [e for e in live if e.distance_to(ref[:2]) <= radius]
            target = min(near, key=lambda e: e.distance_to(ref[:2])) if near else None
        if target is None and xyz:
            # it is a skillshot: the first drone along the throw (12 m, 1.5 m wide)
            import math as _m
            bx, by = m.mover.pos[0], m.mover.pos[1]
            dx, dy = xyz[0] - bx, xyz[1] - by
            n = _m.hypot(dx, dy)
            if n > 0.01:
                dx, dy = dx / n, dy / n
                along = []
                for e in live:
                    t = (e.pos[0] - bx) * dx + (e.pos[1] - by) * dy
                    side = abs((e.pos[0] - bx) * dy - (e.pos[1] - by) * dx)
                    if 0 < t <= 12.0 and side <= 1.5:
                        along.append((t, e))
                target = min(along, key=lambda p: p[0])[1] if along else None
        if target is None:
            # no drone: the street vehicle, if the throw goes at it (it breaks a
            # step further with each hit: Destructible_AdvanceState)
            msgs = m.tutorial.batarang_at_vehicle(xyz, time.time()) if xyz else []
            if msgs:
                m.combat.stop()
                self.send_many(msgs)
                return
            m.combat.stop()
            msgs = m.tutorial.batarang_at_point(xyz, time.time())
            if not msgs:
                log.info("Sonic Batarang: no target", self)
            self.send_many(msgs)
            return
        m.combat.stop()
        self.send_many(m.tutorial.batarang(target, time.time()))

    def _start_cooldown(self, m, slot):
        from . import abilities
        cd = m.cooldowns.start(slot, time.time())
        if cd:
            self.send(*cd)
            # 00:19: after the sweep the button stayed grey. At the end, one more
            # 0x20F8 with 0 s left (StartSkillCooldown(slot, 0)) to put it back.
            if self.cfg["combat"].get("cooldown_end_notice", True):
                end = m.cooldowns.ready_at[slot]
                self.later(max(0.0, end - time.time()) + 0.05,
                           lambda: self.send(f"slot {slot} ready (0x20f8, 0 s)",
                                             abilities.skill_cooldown(slot, time.time())), m.group)

    def _hit(self, m, ent):
        if m.tutorial and m.tutorial.immune_to_basic(ent):
            # the yellow target drones only take their skill
            self._play_attack(m, ent)
            if not getattr(ent, "immune_logged", False):
                ent.immune_logged = True
                log.info(f"{ent.name}: immune to basic attacks", self)
                self.send_many(m.tutorial.wrong_attack(ent, 0))
            return
        # the tutorial reacts to the first hit that lands, not to the order: the
        # first drone keeps fighting the human until Batman actually reaches it
        if m.tutorial:
            self.send_many(m.tutorial.attacked(ent, time.time()))
        self._play_attack(m, ent)
        self._damage(m, ent, m.combat.damage)

    def _damage(self, m, ent, amount):
        if not ent.alive or ent.health is None:
            return
        ent.health = max(0, ent.health - amount)
        self.send(f"{ent.name} vitals {ent.health}/{ent.max_health} (0x42)",
                  M.vitals(ent.eid, [(ent.health, ent.max_health)]))
        if ent.health > 0:
            return
        ent.alive = False
        if m.combat.target is ent:
            m.combat.stop()
        log.info(f"{ent.name} defeated", self)
        self._run_scripts(m, ent.eid, self._key_list(self.cfg["scripts"].get("death_keys")), f"{ent.name} death")
        now = time.time()
        self.send(f"{ent.name} dead (LifeState)", m.entity_bundle(ent, now))
        eid = ent.eid
        self.later(self.cfg["combat"]["corpse_seconds"],
                   lambda: self.send(f"{ent.name} removed (0x3)", M.remove_object(eid)), m.group)
        if m.tutorial:
            msgs = m.tutorial.killed(ent, now)
            if msgs:
                log.info(f"tutorial: phase {m.tutorial.phase}", self)
                self.send_many(msgs)
                delay = float(self.cfg["tutorial"].get("auto_rank_seconds", 0) or 0)
                if m.tutorial.phase == "skills" and delay > 0:
                    self.later(delay, lambda: self._auto_rank(m), m.group)

    @staticmethod
    def _key_list(value):
        """Config entry -> list of script ids (an int or a list of ints)."""
        if isinstance(value, (list, tuple)):
            return [int(v) for v in value]
        return [int(value)] if value else []

    def _play_attack(self, m, target=None):
        """Tell the client to run the champion's basic-attack scripts (attack
        animation and its effects), alternating the configured entries, and the
        hit reaction on the target."""
        sc = self.cfg["scripts"]
        entries = sc.get("basic_attack_keys") or []
        if entries:
            keys = self._key_list(entries[m.attack_count % len(entries)])
            m.attack_count += 1
            target_vars = [(M.PROP_SCRIPT_TARGET, KIND_IID, target.eid)] if target is not None else None
            self._run_scripts(m, M.CHAMPION_AGENT_ID, keys, "basic attack", target_vars)
        if target is None:
            return
        # 2026-10-14 14:50: each pistol shot flew on through the drone and
        # vanished far away. Where it reaches the drone: Vfx_Bmg_Basic_Stop ends
        # the shot and Vfx_Bmg_Basic_Hit + the drone's hit reaction play there
        # ([scripts] shot_speed m/s, shot_stop_keys, shot_hit_keys).
        speed = float(sc.get("shot_speed", 20.0) or 0)
        dist = math.hypot(target.pos[0] - m.mover.pos[0], target.pos[1] - m.mover.pos[1])
        flight = min(1.0, dist / speed) if speed > 0 else 0.0
        stop = self._key_list(sc.get("shot_stop_keys", [0x10000170]))
        hit = self._key_list(sc.get("shot_hit_keys", [0x10000187]))
        hit_vars = [(M.PROP_SCRIPT_TARGET, KIND_IID, target.eid)]

        def impact(target=target):
            if self.match is not m:
                return
            self._run_scripts(m, M.CHAMPION_AGENT_ID, stop + hit, f"shot reaches {target.name}", hit_vars)
            self._run_scripts(m, target.eid, self._key_list(sc.get("hit_keys")), f"{target.name} hit")
        if flight > 0:
            self.later(flight, impact, m.group)
        else:
            impact()

    def _run_scripts(self, m, entity_id, keys, what, variables=None, second=0, deferred=False):
        if not keys:
            return
        defer = float(self.cfg["scripts"].get("champion_defer", 0.06) or 0)
        if entity_id == M.CHAMPION_AGENT_ID and defer > 0 and not deferred:
            # 17:36: the champion's animations (skill casts, the basic attack,
            # Cinematic_Victory) were cut: every one went out just BEFORE a
            # champion bundle of the same moment (facing, stop, visible again),
            # a full re-create of the object. They now go just after it.
            self.later(defer, lambda: self._run_scripts(m, entity_id, keys, what, variables, second, True)
                       if self.match is m else None, m.group)
            return
        runs = []
        for key in keys:
            m.scriptlet_runs += 1
            runs.append((key, m.scriptlet_runs))
        self.send(f"{what}: scripts {' '.join(f'{k:#x}' for k in keys)} (0x8d)",
                  M.start_scriptlets(entity_id, runs, int(self.cfg["scripts"].get("originator") or 0),
                                     variables if self.cfg["scripts"].get("send_target", True) else None,
                                     second))

    def _auto_rank(self, m):
        if self.match is not m or not m.tutorial:
            return
        msgs = m.tutorial.skill_ranked(time.time(), auto=True, slot=m.tutorial.rank_slot() or tutorial1.Q_SLOT)
        if msgs:
            log.info("tutorial: first skill unlocked automatically, phase practice", self)
            self.send_many(msgs)

    def ev_notice(self, msg):
        m = self.match
        body = msg.body
        if not m:
            return NotImplemented
        if body[:4] == NOTICE_LOAD_COMPLETE:
            if m.in_world:
                return
            m.in_world = True
            self.set_phase(IN_WORLD, "client reports load complete")
            if self._match_start_mode() == "in_world":
                self.send("match start (0x2053, in world)", M.match_start())
            chain = self._cinematic_chain()
            delay = self.cfg["timing"]["cinematic_delay"]
            if chain and not m.cinematic_sent:
                m.cinematic_sent = True
                first = chain[0]
                self.later(delay, lambda: self.send(f"intro cinematic {first:#x} (0x20f5)", M.cinematic(first)),
                           m.group)
            elif not chain:
                self.later(delay, self._start_script, m.group)
            return
        if body[:4] == NOTICE_CINEMATIC and len(body) >= 12:
            state, did = struct.unpack_from("<II", body, 4)
            log.info(f"cinematic {did:#x} state {state}", self)
            chain = self._cinematic_chain()
            if state == 4 and m.tutorial and did == self.cfg["tutorial"].get("catwoman_cinematic",
                                                                         tutorial1.CATWOMAN_CINEMATIC):
                if m.champion_hidden:
                    m.champion_hidden = False
                    m.sequence += 1
                    self.send("Batman visible again (0x90F off)", m.champion_bundle(time.time()))
                m.mover.obstacles.pop("DestVehicle", None)
                keep = self.cfg["tutorial"].get("vehicle_keep_wreck", True)
                for ent in list(m.entities.values()):
                    if ent.name.startswith("DestVehicle"):
                        if keep and ent.name == "DestVehicle":
                            # the wreck stays (broken during the cinematic); the way is open
                            self.send_many(m.tutorial.break_vehicle(time.time(), "after the Catwoman cinematic"))
                            continue
                        self.send("vehicle broken by Catwoman (0x3)", M.remove_object(ent.eid))
                        del m.entities[ent.eid]
                # part 2: "Or, Selina has left it to us to deal with her pursuers!"
                self.send_many(m.tutorial.after_catwoman(time.time()))
                return
            if state == 4 and m.tutorial:
                msgs = m.tutorial.cinematic_done(did, time.time())
                if msgs is not None:
                    self.send_many(msgs)
                    return
            if state == 4 and did in chain:
                i = chain.index(did)
                if i + 1 < len(chain):
                    nxt = chain[i + 1]
                    self.send(f"intro cinematic {nxt:#x} (0x20f5)", M.cinematic(nxt))
                else:
                    self._start_script()
            return
        return NotImplemented

    def _cinematic_chain(self):
        """Intro cinematics in order: [match] pre_cinematics, then [match] cinematic."""
        mc = self.cfg["match"]
        chain = [int(c) for c in (mc.get("pre_cinematics") or []) if c]
        if mc["cinematic"]:
            chain.append(int(mc["cinematic"]))
        return chain

    def _match_start_mode(self):
        """[match] send_match_start: false | true / "lobby" (with the lobby data,
        objects as usual: crashed the client) | "reload" (with the first lobby
        data; the objects wait for the client's reload) | "in_world" |
        "after_intro" (both: the client goes back to the loading screen)."""
        v = self.cfg["match"].get("send_match_start", False)
        if v is True:
            return "lobby"
        return v if v in ("lobby", "reload", "in_world", "after_intro") else None

    def _start_script(self):
        m = self.match
        if not m or self.phase == PLAYING:
            return
        self.set_phase(PLAYING)
        if self._match_start_mode() == "after_intro":
            self.send("match start (0x2053, after the intro)", M.match_start())
        # Re-send the objects at once: closes the ~2 s dark gap after the intro.
        if m.sequence:
            self._send_objects(link=True, label="refresh after intro")
        if m.tutorial:
            m.tutorial.schedule = lambda delay, fn: self.later(delay, lambda: self.send_many(fn()), m.group)
            m.tutorial.log = lambda text: log.info(text, self)
            m.tutorial.damage = lambda ent, amount: self._damage(m, ent, amount)
            m.tutorial.run_scripts = lambda eid, keys, what, variables=None, second=0: self._run_scripts(
                m, eid, list(keys), what, variables, second)
            m.tutorial.roster = self.server.roster
            msgs = m.tutorial.start(time.time())
            tc = self.cfg["tutorial"]
            reward = int(tc.get("reward_champion", 0x40000086) or 0)
            if reward and tc.get("replay_champion_unlock", True) and tc.get("send_match_end", True):
                # the reward champion as not owned during the tutorial: it turns
                # owned at the end, which brings the "Champion Unlocked" panel
                self.send(f"item statuses (0x20b8): {reward:#x} not owned until the end",
                          M.item_statuses(self.server.roster, {reward}))
            if self.cfg["combat"]["spawn_scenery"]:
                msgs += m.tutorial.scenery(time.time())
            self.later(self.cfg["timing"]["tutorial_start_delay"], lambda: self.send_many(msgs), m.group)
            log.info("tutorial 1 started", self)

    def ev_end_page_closed(self, msg):
        """0x20A6: the client closed the end page (scorecard / Mission Complete).
        The reward ribbons (Champion Unlocked) are held while the scorecard is up;
        a 0x2190 now makes the client send its pending reward again, unheld."""
        log.info("client closed the end page (0x20a6)", self)
        if self.cfg["tutorial"].get("reward_after_scorecard", True):
            from . import scorecard
            self.later(float(self.cfg["tutorial"].get("reward_after_scorecard_delay", 0.5)),
                       lambda: self.send("header + icons again: pending rewards to the UI (0x2190)",
                                         scorecard.header_and_protector_icons(
                                             header_name=str(self.cfg["account"].get("player_name", "Player")))),
                       self.group)

    def ev_ask_achievement_banners(self, msg):
        """0x212E (empty): the end page's wrapper asks for its pending achievement
        notifications (Flash AskForRibbons -> notice 0x1000042E -> a34900). The
        answer 0x211F (an empty table: Tutorial 1's reward comes as a reward set)
        makes the UI ask for the pending rewards (0x2124)."""
        log.info("client asks for achievement banners (0x212e)", self)
        out = [("achievement banners: none (0x211f)", M.build_message(M.SVC_PLAYER_SYSTEM, 0x211F, b"\x00\x00\x00"))]
        pending = getattr(self, "pending_reward", None)
        if pending and self.cfg["tutorial"].get("reward_with_banners", True):
            out.append(pending)            # (a repeat with the same instance id is ignored)
        self.send_many(out)

    def ev_ask_pending_rewards(self, msg):
        """0x2124 (empty): the UI asks for the pending reward sets -> 0x2125
        (Champion Unlocked ribbon over the Mission Complete page)."""
        pending = getattr(self, "pending_reward", None)
        log.info(f"client asks for pending rewards (0x2124): {'sending it' if pending else 'none'}", self)
        if pending:
            self.send_many([pending])

    def ev_claim_reward(self, msg):
        """0x2128: Continue on the reward ribbon: u32 reward set (no leading u8 in practice) | u32 choice
        | u32 source | u64 instance id | item lists. The client then plays the
        showcase movie by itself (achievement record property 0x10000BCD)."""
        rs = struct.unpack_from("<I", msg.body, 0)[0] if len(msg.body) >= 4 else 0
        log.info(f"client claimed the reward set {rs:#x} (0x2128)", self)
        self.pending_reward = None

    def ev_left_world(self, msg):
        """0x12D (empty): the client has left the match world (rva 0x692950,
        called from its world teardown 0x699b60). After a finished match the
        game connection can close now; the session goes back to the menu."""
        m = self.match
        log.info("client left the match world (0x12d)", self)
        if m and getattr(m, "finished", False):
            old = m
            self.carry_over = {"sequence": old.sequence + old.seq_base + 16, "stale": []}
            if self.cfg["match"].get("remove_objects_on_leave", False):
                # 22:07: the client's teardown keeps the world objects; a second
                # match's creates with the same ids were taken as updates of
                # them and its load stalled. Everything goes now (the client
                # frees them 30 s later: the next match waits for that)
                ids = [M.CHAMPION_AGENT_ID, M.LOCAL_PLAYER_ID] + [e for e in old.entities]
                self.send_many([(f"object {i:#x} removed after the match (0x3)", M.remove_object(i)) for i in ids])
                self.objects_freed_at = time.time()
                log.info(f"{len(ids)} objects of the finished match removed", self)

            # 17:06: closing the game connection here made the client report a
            # connection problem 3 s later; it stays open (the next referral's
            # connection replaces it)
            if self.match is old:
                self.end_match("the client left the finished match")

    def ev_preference(self, msg):
        """0x216E: the client saves a user preference: u8 n + n ASCII bytes
        (name) | u8 n + n UTF-16 chars (value) | u32 (a type DID). Logged in
        server.log; User.CameraLocked (the camera lock key) goes to the tutorial."""
        try:
            b = msg.body
            n = b[0]
            name = b[1:1 + n].decode("ascii")
            k = b[1 + n]
            value = b[2 + n:2 + n + 2 * k].decode("utf-16-le")
        except (IndexError, UnicodeDecodeError):
            return NotImplemented
        log.info(f"client preference {name} = {value}", self)
        m = self.match
        if m and m.tutorial and self.phase in (IN_WORLD, PLAYING):
            msgs = m.tutorial.preference(name, value, time.time())
            if msgs:
                self.send_many(msgs)

    def ev_move(self, msg):
        """0x20EE: u32 command | u32 | u64 target IID | Position | u8.
        Commands: 2 = attack target, 3 = attack-move, 4 = move."""
        m = self.match
        if not m or len(msg.body) < 16:
            return NotImplemented
        command, ability = struct.unpack_from("<II", msg.body, 0)
        if m.tutorial and time.time() < m.tutorial.flying_until and command in (CMD_ATTACK, CMD_ATTACK_MOVE, CMD_MOVE,
                                                                                CMD_STOP, CMD_SKILL):
            log.info("order ignored: Batman is flying (Bat Flight)", self)
            return
        if command in (CMD_ATTACK, CMD_SKILL) and (ability or command == CMD_SKILL):
            # a skill: u32 = the ability (0 = basic attack), target IID and/or a position
            target_id = struct.unpack_from("<Q", msg.body, 8)[0]
            xyz = None
            if len(msg.body) >= 17:
                try:
                    p = parse_client_position(msg.body, 16)
                    xyz = (p[3], p[4], p[5])
                except (struct.error, IndexError, ValueError):
                    xyz = None
            log.info(f"skill order: command {command}, ability {ability}, target {target_id:#x}, "
                     f"position {xyz and tuple(round(v, 1) for v in xyz)}", self)
            self._cast(m, ability, m.entities.get(target_id), xyz)
            return
        if command == CMD_ATTACK:
            target_id = struct.unpack_from("<Q", msg.body, 8)[0]
            ent = m.entities.get(target_id)
            if ent and ent.attackable and ent.alive and m.tutorial and m.tutorial.carrying():
                self.send_many(m.tutorial.throw(tuple(ent.pos), f"attack order on {ent.name}"))
                return
            if ent and ent.attackable and ent.alive and m.tutorial and time.time() < m.tutorial.locked_until:
                log.info(f"attack order on {ent.name} ignored: {m.tutorial.lock_reason}", self)
                return
            if ent and ent.attackable and ent.alive:
                m.combat.engage(ent, time.monotonic())
                log.info(f"attack order -> {ent.name} ({ent.health}/{ent.max_health})", self)
            else:
                what = ("the player object (the duplicate Batman)" if target_id == M.LOCAL_PLAYER_ID
                        else f"{target_id:#x}")
                log.info(f"attack order on {what}: not attackable", self)
            return
        if command == CMD_STOP:                      # S key: stop moving and attacking
            m.combat.stop()
            m.mover.target = None
            if m.mover.speed:
                m.mover.speed = 0.0
                self.send("stop", self._objects(m.linked))
            log.info("stop order", self)
            return
        if command in (CMD_ATTACK_MOVE, CMD_MOVE) and m.tutorial and time.time() < m.tutorial.locked_until:
            # the 3 small meteors at the start / Batman knocked down: he cannot move yet
            if not getattr(m.tutorial, "lock_logged", False):
                m.tutorial.lock_logged = True
                log.info(f"move order ignored: {m.tutorial.lock_reason}", self)
            m.mover.target = None
            if m.mover.speed:
                m.mover.speed = 0.0
            self.send("stay (locked)", self._objects(m.linked))
            return
        if command not in (CMD_ATTACK_MOVE, CMD_MOVE) or len(msg.body) < 17:
            return NotImplemented
        m.combat.stop()
        target = parse_client_position(msg.body, 16)
        ent = self._enemy_near(m, target, command)
        if ent and m.tutorial and m.tutorial.carrying():
            # Super Strength: a right-click on the drones throws the car at them
            self.send_many(m.tutorial.throw(tuple(ent.pos), f"right-click near {ent.name}"))
            return
        if ent:
            m.combat.engage(ent, time.monotonic())
            log.info(f"{'attack-move' if command == CMD_ATTACK_MOVE else 'click'} near {ent.name} "
                     f"-> attacking it ({ent.health}/{ent.max_health})", self)
            return
        if m.mover.order(target):
            log.info(f"move order {command} -> lb {target[1]:02x}{target[2]:02x} "
                     f"({target[3]:.1f}, {target[4]:.1f}, {target[5]:.1f})", self)
        else:
            log.info(f"move order rejected (other region or unreadable): {msg.body.hex()}", self)

    def _enemy_near(self, m, target, command):
        """The client does not let the drones be targeted yet, so a click on
        the ground right next to one (or attack-move near one) attacks it."""
        if not target or target[1:3] != (0x13, 0xCB):
            return None
        cc = self.cfg["combat"]
        radius = cc["attack_move_radius"] if command == CMD_ATTACK_MOVE else cc["click_attack_radius"]
        xy = (target[3], target[4])
        live = [e for e in m.entities.values() if e.attackable and e.alive
                and e.distance_to(xy) <= max(radius, getattr(e, "click_radius", 0))]
        return min(live, key=lambda e: e.distance_to(xy)) if live else None

    def ev_ping(self, msg):
        m = self.match
        if not m or not m.sequence:
            return NotImplemented
        if len(msg.body) >= 20 and struct.unpack_from("<I", msg.body, 16)[0] == RANK_SKILL_MAGIC:
            # Patched client: GM_Advancement RankSkill (the "+" once InqCanRankSkill
            # says yes for the recommended slot, or the "rank recommended" key)
            # arrives as a ping with the slot. Bursts (several within a few ms)
            # are ignored, as the old patch's rank-query bursts were.
            arg = struct.unpack_from("<Q", msg.body, 8)[0]
            now = time.monotonic()
            prev_t, prev_arg = self._rank_ping_last
            self._rank_ping_last = (now, arg)
            burst = now - prev_t < RANK_BURST_GAP
            allowed = m.tutorial.rank_slots() if m.tutorial else ()
            if burst or arg not in allowed:
                if not burst:
                    log.info(f"skill '+' for slot {arg}: the tutorial waits for slot {allowed}", self)
                return          # a burst, or another slot
            log.info(f"skill '+' clicked (RankSkill, slot {arg})", self)
            if m.tutorial:
                # decided a moment later: a burst starting with this slot is not a click
                def decide(t=now):
                    if self._rank_ping_last[0] != t and self._rank_ping_last[0] - t < RANK_BURST_GAP:
                        log.info("...it was the start of a HUD refresh, ignored", self)
                        return
                    msgs = m.tutorial.skill_ranked(time.time(), slot=arg)
                    if msgs:
                        log.info(f"tutorial: skill slot {arg} ranked up by the player", self)
                        self.send_many(msgs)
                self.later(RANK_BURST_GAP * 1.5, decide)
            return
        if m.tutorial and len(msg.body) >= 8:
            x, y = struct.unpack_from("<ff", msg.body, 0)
            ptype = struct.unpack_from("<I", msg.body, 16)[0] if len(msg.body) >= 20 else 1
            if ptype == 1 and m.tutorial.finale.wants_ping((x, y)):
                # while the F button does not work: an Alt+click on the car lifts it
                # (a Ctrl+click is always a ping: the tester marks spots with it)
                log.info(f"ping Alt+click at ({x:.1f}, {y:.1f}) on the car: Super Strength", self)
                self.send_many(m.tutorial.finale.lift("Alt+click", (x, y, m.mover.pos[2])))
                return
        if m.tutorial and m.tutorial.bridge.stage == "camera" and len(msg.body) >= 8:
            # fallback while the D button does not work: a ping on the marked
            # spot places the surveillance camera
            x, y = struct.unpack_from("<ff", msg.body, 0)
            msgs = m.tutorial.stolen_power((x, y, m.mover.pos[2]), time.time(), "ping")
            if msgs:
                self.send_many(msgs)
                return
        m.ping_count += 1
        result = tutorial1.player_ping(m, msg.body, m.ping_count, time.time())
        if not result:
            return NotImplemented
        object_id, data, notes = result
        x, y, target_id = struct.unpack_from("<ffQ", msg.body, 0)
        hit = m.entities.get(target_id)
        what = (f", on {hit.name}" if hit else ", on the player object" if target_id == M.LOCAL_PLAYER_ID
                else f", on object {target_id:#x}" if target_id else "")
        ptype = struct.unpack_from("<I", msg.body, 16)[0]
        kind = {1: "Alt+click (alert)", 2: "Ctrl+click (retreat)"}.get(ptype, f"type {ptype}")
        log.info(f"ping {kind} [type {ptype}] at ({x:.1f}, {y:.1f}){what} -- usable as a [tutorial] target", self)
        self.send(f"player ping object {object_id:#x}", data)
        for note_id, note in notes:
            self.send(f"minimap note {note_id:#x} for the ping", note)
        ids = [object_id] + [n for n, _ in notes]
        self.later(self.cfg["timing"]["ping_lifetime"],
                   lambda: [self.send("player ping removed (0x3)", M.remove_object(i)) for i in ids], m.group)

    # ---- developer hook ----------------------------------------------------------------
    def _dev_send_file(self):
        path = os.path.join(self.cfg.log_dir, "send.txt")
        if self.user.closed:
            return False
        if not os.path.exists(path):
            return True
        try:
            with open(path) as f:
                lines = f.read().splitlines()
            os.remove(path)
            for ln in lines:
                if not ln.strip():
                    continue
                dest, ev, hx = ln.split(None, 2)
                dest = (M.LOCAL_PLAYER_ID if dest == "player" else
                        M.SVC_PLAYER_SYSTEM if dest == "svc" else int(dest, 16))
                from .wire import build_message
                self.send(f"send.txt {ev}", build_message(dest, int(ev, 16), bytes.fromhex(hx)))
                log.info(f"send.txt: sent event {ev} to {dest:#x}", self)
        except (OSError, ValueError) as e:
            log.info(f"send.txt failed: {e}", self)
        return True


HANDLERS = {
    0x20EB: Session.ev_join_queue,
    0x20CA: Session.ev_accept_match,
    0x20F2: Session.ev_connect_to_lobby,
    0x20D5: Session.ev_loading_percent,
    0x2: Session.ev_notice,
    0x20EE: Session.ev_move,
    0x2136: Session.ev_ping,
    0x216E: Session.ev_preference,
    0x12D: Session.ev_left_world,
    0x20A6: Session.ev_end_page_closed,
    0x212E: Session.ev_ask_achievement_banners,
    0x2124: Session.ev_ask_pending_rewards,
    0x2128: Session.ev_claim_reward,
}
