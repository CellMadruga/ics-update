"""End-to-end run of the new server (python -m ics) with a simulated client (no game needed).

  python tests/test_ics.py

Login, queue, lobby, loading, the layout's units, a walk, Q (Sonic Batarang) from its server script with the
missile as an object of its own class, damage, cooldown, and basic attacks until a unit dies. Uses ports 1888x /
1900x so it can run next to the real server. Needs data/script_trees (python tools\\script_decoder.py all).
"""
import os
import socket
import struct
import sys
import tempfile
import threading
import time
import urllib.request

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from ics import config, log                                       # noqa: E402
from ics.server import Server                                     # noqa: E402
from ics.wire import build_message, build_position, read_compact  # noqa: E402

SVC = 0x0600000000000403
SVC_INPUT = 0x0600000000000008
PLAYER = 0x0200000000000001
CHAMPION = 0x0200000000000002
CHECKS = []


def check(name, cond, detail=""):
    CHECKS.append((name, bool(cond)))
    print(f"  {'ok  ' if cond else 'FAIL'} {name}" + (f"  ({detail})" if detail and not cond else ""))


class Client:
    def __init__(self, port):
        self.sock = socket.create_connection(("127.0.0.1", port))
        self.events, self.packets, self.buf = [], [], b""
        self.lock = threading.Lock()
        threading.Thread(target=self._read, daemon=True).start()

    def _read(self):
        try:
            while True:
                d = self.sock.recv(65536)
                if not d:
                    break
                self.buf += d
                while len(self.buf) >= 4:
                    n = struct.unpack_from("<I", self.buf)[0]
                    if len(self.buf) < 4 + n:
                        break
                    fr, self.buf = self.buf[4:4 + n], self.buf[4 + n:]
                    with self.lock:
                        if fr[0] == 0x02:
                            ev, pos = read_compact(fr, 10)
                            self.events.append((time.monotonic(), struct.unpack_from("<Q", fr, 1)[0], ev, fr[pos:]))
                        else:
                            self.packets.append((time.monotonic(), struct.unpack_from("<I", fr, 1)[0], fr[5:]))
        except OSError:
            pass

    def send_event(self, dest, ev, body):
        self.sock.sendall(build_message(dest, ev, body))

    def wait_for(self, pred, timeout=5.0):
        end = time.monotonic() + timeout
        while time.monotonic() < end:
            with self.lock:
                hit = [e for e in self.events if pred(e)]
            if hit:
                return hit
            time.sleep(0.02)
        return []

    def since(self, t, ev=None, dest=None):
        with self.lock:
            return [e for e in self.events if e[0] >= t and (ev is None or e[2] == ev) and (dest is None or e[1] == dest)]


def hello_blob(key_n):
    from cryptography.hazmat.primitives import hashes
    from cryptography.hazmat.primitives.asymmetric import padding, rsa
    pub = rsa.RSAPublicNumbers(65537, key_n).public_key()
    blob = pub.encrypt(os.urandom(24), padding.OAEP(mgf=padding.MGF1(hashes.SHA1()), algorithm=hashes.SHA1(), label=None))
    return b"\x00" * 12 + b"\x043des" + struct.pack("<I", len(blob)) + blob


def object_class(body):
    return struct.unpack_from("<I", body, 1 + 1 + 2 + 4)[0]


def batch_kinds(body):
    """The sub-event ids of a 0x4 batch body (u8 base | compact n | n x (compact id | u32 length | body))."""
    n, p = read_compact(body, 1)
    out = []
    for _ in range(n):
        ev, p = read_compact(body, p)
        p += 4 + struct.unpack_from("<I", body, p)[0]
        out.append(ev)
    return out


def vit_cur(body):
    return max(struct.unpack_from("<H", body, 2)[0], struct.unpack_from("<H", body, 2 + 4 + 1)[0])


def auth_pairs(text):
    """AuthSelect's nameValuePairs as the client reads them (docs/re-notes/store-fix.md 2.3): the member
    nameValuePairs is a gSOAP NameValuePairArray (0xADE2D0) whose items are its child elements named nameValuePairs
    (NameValuePair 0xADE0F0: name, value); any other child is skipped, so a flat pair reads as an empty array."""
    import xml.etree.ElementTree as ET

    def local(tag):
        return tag.rsplit("}", 1)[-1]
    ret = next((e for e in ET.fromstring(text).iter() if local(e.tag) == "return"), None)
    out = {}
    for arr in (c for c in (ret if ret is not None else []) if local(c.tag) == "nameValuePairs"):
        for item in (c for c in arr if local(c.tag) == "nameValuePairs"):
            fields = {local(c.tag): c.text or "" for c in item}
            if "name" in fields:
                out[fields["name"]] = fields.get("value", "")
    return out


def main():
    cfg = config.load()
    # ICS_TEST_PORT moves the three ports (another copy of the test may be running next to this one)
    base = int(os.environ.get("ICS_TEST_PORT", "19000"))
    cfg["server"].update({"soap_port": base - 112, "user_port": base, "game_port": base + 1})
    cfg["timing"].update({"objects_min_delay": 0.5, "link_delay": 0.3, "units_delay": 0.2})
    cfg["ics"]["trace_scripts"] = False
    # a throw-away account and progress file: the test must not touch data/accounts/<player>.json
    _acct = tempfile.mkdtemp(prefix="ics_test_acct_")
    cfg["ics"]["account_dir"] = _acct
    cfg["ics"]["progress_file"] = os.path.join(_acct, "progress.json")
    cfg["ics"]["unit_aggro_radius"] = 0.0      # the drones' own attacks are checked at the end
    # the whole layout at once (the tutorial's flow is checked by tests/test_director.py)
    cfg["ics"]["encounters"]["0x40000991"]["director"] = ""
    cfg["ics"]["pathing"] = False              # the test teleports Batman anywhere (paths: tests/test_navmesh.py)
    log.setup(tempfile.mkdtemp(prefix="ics_test_"), False)
    server = Server(cfg)
    server.start()
    server._warm_up()                  # the encounter data, before the client asks (the server does it in a thread)
    s = cfg["server"]

    req = urllib.request.Request(f"http://127.0.0.1:{s['soap_port']}/WebLoginApp-1.3/AuthenticateWS",
                                 data=b"<Envelope><Body><AuthSelect><userName>t</userName></AuthSelect></Body></Envelope>",
                                 method="POST")
    soap = urllib.request.urlopen(req, timeout=5).read().decode()
    check("SOAP login answers with the user port", f"<userServerPort>{s['user_port']}<" in soap)
    check("SOAP login: URL.Store nested in nameValuePairs, as the client's NameValuePairArray reads it (store-fix.md)",
          auth_pairs(soap).get("URL.Store", "").endswith("/store"), soap)
    u = Client(s["user_port"])
    u.sock.sendall(hello_blob(server.key.n))
    check("account data delivered (0x2080 last)", u.wait_for(lambda e: e[2] == 0x2080))

    t0 = time.monotonic()
    u.send_event(SVC, 0x20EB, struct.pack("<II", 0x40000991, 0) + b"\x00" + struct.pack("<i", -1))
    check("queue joined + match found", u.wait_for(lambda e: e[0] >= t0 and e[2] == 0x20FA))
    u.send_event(SVC, 0x20CA, b"")
    time.sleep(0.3)
    check("referral to the game port", any(p[1] == 0x800 for p in u.packets))
    g = Client(s["game_port"])
    g.sock.sendall(b"\x00" * 40)
    check("enter match (0x20af)", u.wait_for(lambda e: e[2] == 0x20AF))
    g.send_event(SVC, 0x20F2, b"")
    check("lobby data", u.wait_for(lambda e: e[2] == 0x206D))
    g.send_event(SVC, 0x20D5, struct.pack("<I", 25))
    objs = u.wait_for(lambda e: e[2] == 0x4 and e[1] == CHAMPION, 3)
    check("champion created", objs and object_class(objs[0][3]) == cfg["ics"]["champion"])
    time.sleep(0.5)
    check("player object created", u.since(t0, 0x4, PLAYER))

    time.sleep(3.0)                    # the layout is read while queueing
    t_load = time.monotonic()
    g.send_event(PLAYER, 0x2, bytes.fromhex("5e010010") + bytes(8))
    time.sleep(1.0)
    units = {}
    for e in u.since(t_load, 0x4):
        if e[1] >= 0x0200000000000100:
            units.setdefault(e[1], object_class(e[3]))
    check("layout units spawned from the packs", len(units) >= 10, str(len(units)))

    w = server.sessions[-1].match.world
    ch = w.champion
    props = {e.eid for e in w.entities.values() if e.health is None}
    check("props are created too (doors, vehicles ...)", props, str(len(props)))
    check("no vitals (0x42) to an object without health (the client crashes)",
          not [e for e in u.since(t_load, 0x42) if e[1] in props])
    check("Batman's kit read from the catalog (6 slots) + Stolen Powers D / F from the data",
          all(slot in ch.kit for slot in range(6)) and 7 in ch.kit and 8 in ch.kit, str(ch.kit))
    prop_ents = [e for e in w.entities.values() if e.kind == "prop"]
    check("props get the movement module and a placed creation type (0x50F = 7 / 8)",
          prop_ents and all(e.module and (any(p[0] == 0x50F and p[2] == 8 for p in e.extra_props)
                                          or w.data.creation_type(e.world_state) in (7, 8)) for e in prop_ents))
    doors = [e for e in prop_ents if w.data.scriptlet_key("Object_Closed") in (e.scriptlet_keys or ())]
    time.sleep(cfg["timing"].get("prop_scriptlet_delay", 1.0) + 0.5)
    closed = [e for e in u.since(t_load, 0x8D) if e[1] in {d.eid for d in doors}]
    check("doors read their tables from the data and play Object_Closed", doors and len(closed) >= len(doors),
          f"{len(doors)} doors, {len(closed)} scriptlets")

    # walk next to the closest unit
    target = min((e for e in w.entities.values() if e.health is not None and getattr(e, "client_vitals", True)
                  and e.team == cfg["ics"]["enemy_team"]),
                 key=lambda e: e.distance_to(ch))
    for other in w.entities.values():          # keep the test simple: only two units near the target
        if other is not target and other.distance_to(target) < 6 and other is not None:
            pass
    near = [target.pos[0] - 3.0, target.pos[1], target.pos[2]]
    ch.pos = list(near)                        # teleport next to it (the walk is checked below)
    t_walk = time.monotonic()
    dest = [ch.pos[0] - 2.0, ch.pos[1], ch.pos[2]]
    region, lbx, lby, cell, x, y, z = w.wire_position(type("P", (), {"pos": dest})())
    g.send_event(SVC_INPUT, 0x20EE, struct.pack("<IIQ", 4, 0, 0) + build_position(region, lbx, lby, cell, x, y, z) + b"\x00")
    time.sleep(1.0)
    check("walking updates streamed", len(u.since(t_walk, 0x4, CHAMPION)) > 5)
    # 2026-10-28 15:00 (tester report 2026-10-28 15:00; docs/re-notes/object-update-bundles.md 13): [ics]
    # object_update_mode "delta" = the walk's states without 0xF2 / 0xBC, and no player-object bundle per tick
    walk4 = [batch_kinds(e[3]) for e in u.since(t_walk, 0x4, CHAMPION)]
    if str(cfg["ics"].get("object_update_mode", "delta")) == "delta":
        check("the walk goes as motion-only states (0x4 with only the 0xB0), no full bundle, nothing to the player object",
              walk4 and all(k == [0xB0] for k in walk4) and not u.since(t_walk, 0x4, PLAYER),
              (walk4[:4], len(u.since(t_walk, 0x4, PLAYER))))
    check("arrived", abs(ch.pos[0] - dest[0]) < 0.1)

    # Q on the unit
    t_q = time.monotonic()
    hp0 = target.health
    g.send_event(SVC_INPUT, 0x20EE, struct.pack("<IIQ", 9, 1, target.eid) + b"\x00\x00")
    time.sleep(2.0)
    check("Q: cast scriptlet 0x10000164 on Batman (0x8d)",
          any(b"\x10" in e[3] for e in u.since(t_q, 0x8D, CHAMPION)))
    missiles = [e for e in u.since(t_q, 0x4) if e[1] >= 0x0200000000000100 and object_class(e[3]) == 0x40000090]
    check("Q: missile created as an object of class 0x40000090", missiles)
    check("Q: missile removed at the end (0x3)", missiles and u.since(t_q, 0x3, missiles[0][1]))
    check("Q: damage from stat 5 (60 at rank 1)", target.health == hp0 - 60, f"{hp0} -> {target.health}")
    check("Q: cooldown sent (0x20f8)", u.since(t_q, 0x20F8))
    check("Q: Will spent (stat 3)", ch.will < ch.max_will, str(ch.will))
    g.send_event(SVC_INPUT, 0x20EE, struct.pack("<IIQ", 9, 1, target.eid) + b"\x00\x00")
    time.sleep(0.3)
    check("Q: second cast refused during the cooldown", target.health == hp0 - 60)

    # basic attack until dead
    t_a = time.monotonic()
    g.send_event(SVC_INPUT, 0x20EE, struct.pack("<IIQ", 2, 0, target.eid) + b"\x00\x00")
    dead = u.wait_for(lambda e: e[0] >= t_a and e[2] == 0x42 and e[1] == target.eid and vit_cur(e[3]) == 0, 30)
    check("basic attacks (basic attack script) kill the unit", dead, f"health {target.health}")
    time.sleep(cfg["ics"]["corpse_seconds"] + 0.5)
    check("dead unit removed (0x3)", u.since(t_a, 0x3, target.eid))

    # the drones fight back with their own attack script (template 0x10000328) once Batman is near
    cfg["ics"]["unit_aggro_radius"] = 8.0
    near = [e for e in w.entities.values() if e.kit and e.alive and e.team == cfg["ics"]["enemy_team"]]
    thugs = [e for e in w.entities.values() if e.kit and e.team == 0]
    check("the thugs (no side in the layout) are neutral", thugs and all(e.attack_target is None for e in thugs))
    if near:
        hp = ch.health
        ch.pos = [near[0].pos[0] + 2.0, near[0].pos[1], near[0].pos[2]]
        time.sleep(4.0)
        check("drones attack Batman with their own attack script", ch.health < hp, f"{hp} -> {ch.health}")

    # crowd control from the game's own stun status (0x48000293 -> script 0x34000130) on the champion
    # (full-combat-skills.md 2 A.3 / 3: 0x20F0 modifier, 0x6 Stunned and 0x10000B2D, orders refused server-side)
    cfg["ics"]["unit_aggro_radius"] = 0.0
    for e in w.entities.values():
        e.attack_target = None
    ch.pos = list(w.spawn_pos)
    ch.attack_target = None
    from ics import script_runtime as R
    from ics.world import CastWorld
    t_cc = time.monotonic()
    w.schedule(0.0, lambda: R.apply_status(CastWorld(w, ch, None), ch, ch, 0x48000293, {"EffectDuration": 2.0}))
    time.sleep(0.5)
    check("stun: Stunned modifier sent to the champion (0x20f0)", u.since(t_cc, 0x20F0, CHAMPION))
    sets = [e for e in u.since(t_cc, 0x6, CHAMPION)]
    check("stun: Stunned 0x100003F3 and cannot-act 0x10000B2D set as properties (0x6)",
          any(struct.pack("<I", 0x100003F3) in e[3] for e in sets)
          and any(struct.pack("<I", 0x10000B2D) in e[3] for e in sets))
    here = list(ch.pos)
    dest = [here[0] + 4.0, here[1], here[2]]
    region, lbx, lby, cell, x, y, z = w.wire_position(type("P", (), {"pos": dest})())
    g.send_event(SVC_INPUT, 0x20EE, struct.pack("<IIQ", 4, 0, 0) + build_position(region, lbx, lby, cell, x, y, z) + b"\x00")
    t_e = time.monotonic()
    g.send_event(SVC_INPUT, 0x20EE, struct.pack("<IIQ", 2, 3, 0) + build_position(region, lbx, lby, cell, x, y, z) + b"\x00")
    time.sleep(0.6)
    check("stun: a move order is ignored", abs(ch.pos[0] - here[0]) < 0.05, f"{here[0]} -> {ch.pos[0]}")
    check("stun: a skill is refused with Skill_Stunned (0x20dc)",
          any(struct.pack("<I", 0x10000051) in e[3] for e in u.since(t_e, 0x20DC)))
    time.sleep(2.0)
    check("stun ends: modifier removed (0x20e8)", u.since(t_cc, 0x20E8, CHAMPION))
    check("stun ends: orders accepted again", w.walk_to(ch, dest) and ch.dest is not None)

    # the record lookups of the 2026-10-28 log sweep (docs/re-notes/test-2026-10-28-1439-sweep.md S1 / S3), on the warm
    # server data (the tester's process had the same warm-up), with the defaults whatever config.toml sets
    d = server.data
    d.record_start_only = d.template_window_bounded = True
    for k in [k for k in d._scripts if isinstance(k, tuple) and len(k) == 2 and k[0] in ("ctype", "attack", "unitstats")]:
        del d._scripts[k]
    name = d.index().get(0x2E0009F0)
    d._starts.pop(name, None)
    t_ct = time.monotonic()
    ct = d.creation_type(0x2E0009F0)
    t_ct = time.monotonic() - t_ct
    check("S1: creation_type(0x2E0009F0) (AWW's sweep helper, pack 0xA00000DF) builds no record list (2.4-3.3 s on "
          "the game thread in fase3-ie) and reads type 3", ct == 3 and name not in d._starts and name in d._lists_skipped
          and t_ct < 1.0, (ct, name in d._starts, f"{t_ct:.2f} s"))
    atk = {c: (d.unit_attack(c).script if d.unit_attack(c) else None)
           for c in (0x40000CD6, 0x400005E1, 0x40000BD4, 0x40000E56, 0x400005D2, 0x4000020B, 0x40000D5F)}
    check("S3: skill-spawned helpers no longer take another record's attack (AWW's sweep 0x40000CD6 took her basic "
          "attack 0x34000257 from +0x4BB4; the jungle drop, Plutonium Peel, Zod's R); the real ones keep theirs",
          atk == {0x40000CD6: None, 0x400005E1: None, 0x40000BD4: None, 0x40000E56: None, 0x400005D2: 0x34000391,
                  0x4000020B: 0x34000116, 0x40000D5F: 0x3400077A}, {hex(k): v and hex(v) for k, v in atk.items()})
    from ics.world import STAT_HEALTH
    check("S3: World.spawn(0x40000CD6) makes a prop (no attack, its own stat block 0x48000534 has no Health)",
          d.unit_attack(0x40000CD6) is None and STAT_HEALTH not in d.unit_stats(0x40000CD6))
    check("S3: no stat block from another record for 0x400005E1 / 0x40000A6C / 0x40000CEB",
          not d.unit_stats(0x400005E1) and not d.unit_stats(0x40000A6C) and not d.unit_stats(0x40000CEB))
    keep = {0x40000BF8: 0x340004A1, 0x40000C92: 0x34000014, 0x40000CA2: 0x34000512, 0x40000C72: 0x340004A1,
            0x40000EB2: 0x3400058F}
    bounded = {c: (d.unit_attack(c).script, d.unit_stats(c)) for c in keep}
    d.template_window_bounded = False
    for c in keep:
        d._scripts.pop(("attack", c), None)
        d._scripts.pop(("unitstats", c), None)
    window = {c: (d.unit_attack(c).script, d.unit_stats(c)) for c in keep}
    d.template_window_bounded = True
    for c in keep:
        d._scripts.pop(("attack", c), None)
        d._scripts.pop(("unitstats", c), None)
    check("S3: map units keep their attack and stat block (minion, turret, Raider, tutorial drone, Destroyer)",
          all(bounded[c][0] == keep[c] and window[c][0] == keep[c] and bounded[c][1] == window[c][1] for c in keep),
          {hex(c): (hex(bounded[c][0]), hex(window[c][0])) for c in keep})
    t1, t2 = d.unit_attack(0x40000C92), d.unit_attack(0x40000C93)
    check("S3: Crime Alley's team 1 turret 0x40000C92 has the attack stats of team 2's 0x40000C93 (it took 7 more from "
          "the next records)", t1 and t2 and t1.stats == t2.stats, (t1 and sorted(t1.stats), t2 and sorted(t2.stats)))

    ok = sum(1 for _, c in CHECKS if c)
    print(f"\n{ok}/{len(CHECKS)} checks")
    return 0 if ok == len(CHECKS) else 1


if __name__ == "__main__":
    sys.exit(main())
