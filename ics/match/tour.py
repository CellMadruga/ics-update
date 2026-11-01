"""A guided tour of a match map for the tester (chat command /tour): the champion is teleported from stop to stop and the
chat says what the server placed there, so the tester can name what does not show (2026-10-25 23:45, tester: "a tour
over every element of the map, so I can identify the elements that still do not load").

Stops: every object the server placed that is not a unit (structures, turret heads / plates, gates, auras, stealth
tiles, covers, pads, liftables, pickups), every jungle camp, and the lane every [ics] tour_lane_step m, ordered as a
walk from the champion's base. Each stop is logged in server.log ("tour stop N: ...") so the tester can quote it.
"""
import math

from . import maps


def prefetch(match):
    """2026-10-26 14:49 (tester: the first "vitrina" froze the match for seconds: reading ~600 world states took 28 s
    on the server's thread): the showroom list is read in a background thread at match start ([ics]
    showroom_prefetch)."""
    import threading
    state = {"items": None}
    match._showroom_prefetch = state

    def run():
        try:
            t = Tour(match, lambda text: None)
            t._prefetching = True
            items = t.showroom_list()
            state["items"] = items
        except Exception as e:                      # noqa: BLE001 - a test aid must never stop the match
            match.log(f"showroom prefetch failed: {e!r}")
    threading.Thread(target=run, name="showroom-prefetch", daemon=True).start()


class Tour:
    def __init__(self, match, say):
        self.m = match
        self.w = match.world
        self.say = say                  # say(text): a chat line to the player
        self.stops = []
        self.i = -1
        self.auto = 0.0
        self._token = 0

    def build(self):
        w, m = self.w, self.m
        near = float(m.ic.get("tour_group_radius", 3.0) or 3.0)
        points = []                     # (x, y, label)
        for e in list(w.entities.values()):
            if e.kind in ("unit", "champion", "missile") or not e.alive and e.kind != "prop":
                continue
            ws = getattr(e, "world_state", 0) or 0
            points.append((e.pos[0], e.pos[1], f"{e.name} [{e.class_id:#x}" + (f" / {ws:#x}]" if ws and ws != e.class_id
                                                                              else "]")))
        for c in getattr(m, "camps", ()):
            x, y = c.spec["pos"][:2]
            names = ", ".join(f"{int(str(u), 0) if not isinstance(u, int) else u:#x}" for u in c.spec.get("units", ())
                              if isinstance(u, (int, str)))
            points.append((x, y, f"jungle camp {c.index} ({c.spec.get('kind', 'small')}{': ' + names if names else ''})"))
        step = float(m.ic.get("tour_lane_step", 12.0) or 0)
        if step > 0:
            for lane in (m.map.get("lanes") or {}):
                path = maps.lane_path(m.map, lane, maps.T1)
                for (ax, ay), (bx, by) in zip(path, path[1:]):
                    d = math.hypot(bx - ax, by - ay)
                    for k in range(int(d // step) + 1):
                        f = k * step / d if d else 0.0
                        points.append((ax + (bx - ax) * f, ay + (by - ay) * f, f"lane {lane}"))
        # group what stands together into one stop
        stops = []
        for x, y, label in points:
            for s in stops:
                if math.hypot(s["pos"][0] - x, s["pos"][1] - y) <= near:
                    if label not in s["labels"]:
                        s["labels"].append(label)
                    break
            else:
                stops.append({"pos": (x, y), "labels": [label]})
        # a walk from the champion's position: always the nearest stop not yet visited
        ch = w.champion
        here = (ch.pos[0], ch.pos[1]) if ch is not None else (0.0, 0.0)
        ordered = []
        while stops:
            s = min(stops, key=lambda s: math.hypot(s["pos"][0] - here[0], s["pos"][1] - here[1]))
            stops.remove(s)
            ordered.append(s)
            here = s["pos"]
        self.stops = ordered
        m.log(f"tour: {len(ordered)} stops")
        for n, s in enumerate(ordered, 1):
            m.log(f"tour stop {n}: ({s['pos'][0]:.1f}, {s['pos'][1]:.1f}) " + "; ".join(s["labels"]))

    def go(self, n):
        if not self.stops:
            self.build()
        if not self.stops:
            self.say("Tour: nothing to visit")
            return
        self.i = max(0, min(len(self.stops) - 1, n))
        s = self.stops[self.i]
        w, ch = self.w, self.w.champion
        if ch is None or not ch.alive:
            self.say("Tour: the champion is not alive")
            return
        x, y = s["pos"]
        back = float(self.m.ic.get("tour_stand_off", 2.5) or 0)
        # stand a little south of the stop so the object itself is not under the champion
        y -= back
        z = (w.nav.height(x, y) if w.nav is not None else None) or self.m.map["z"]
        ch.pos, ch.dest, ch.path, ch.speed, ch.attack_target = [x, y, z], None, [], 0.0, None
        w.teleport(ch)
        ch._motion_sent = None
        w.send_champion(f"tour: champion to stop {self.i + 1}")
        text = f"Parada {self.i + 1}/{len(self.stops)} ({s['pos'][0]:.0f}, {s['pos'][1]:.0f}): " + "; ".join(s["labels"])
        self.m.log("tour " + text)
        self.say(text[:240])

    # ---- the showroom: every placeable element of the map's packs, one at a time in front of the champion ------------
    def showroom_list(self):
        """2026-10-26 13:00 (tester: the tour only moves the champion; as the old server's tour played Batman's actions
        one by one, show the map's elements one by one): every world state of the map's own packs whose creation type
        is one the server places (3 marker, 7 / 8 placed, 9; [ics] showroom_creation_types), with the catalog name."""
        w, m = self.w, self.m
        if getattr(self, "_show", None) is not None:
            return self._show
        pre = getattr(m, "_showroom_prefetch", None)
        if pre is not None and pre.get("items") is not None:
            self._show = pre["items"]
            return self._show
        if pre is not None and pre.get("items") is None and not getattr(self, "_prefetching", False):
            return None                     # still being read in the background thread
        names = {}
        try:
            import os
            path = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))),
                                "catalog", "data", "world_objects.tsv")
            for line in open(path, encoding="utf-8").read().splitlines()[1:]:
                c = line.split("\t")
                if len(c) > 1 and c[0].startswith("0x"):
                    names[int(c[0], 16)] = c[1]
        except OSError:
            pass
        types = {int(t) for t in (m.ic.get("showroom_creation_types") or [3, 7, 8, 9])}
        cache_key = ("showroom", m.map.get("key"), tuple(sorted(types)))
        cached = w.data._scripts.get(cache_key)
        if cached is not None:
            self._show = cached
            return cached
        packs = [int(str(p), 0) for p in (m.ic.get("showroom_packs") or {}).get(m.map.get("key"), ())] or \
            list((w.data.encounter(m.encounter) or {}).get("packs") or ())
        out = []
        for p in packs:
            try:
                ids = sorted(d for d in w.data.packs.pack(p).ids if d >> 24 == 0x2E)
            except Exception:                       # noqa: BLE001 - a pack not in this install
                continue
            for did in ids:
                if getattr(self, "_prefetching", False):
                    # 2026-10-26 16:18 (tester: "disconnected from the server" for seconds while the match loaded: the
                    # prefetch thread held the interpreter): a pause per record leaves the server's thread its turn
                    import time
                    time.sleep(float(m.ic.get("showroom_prefetch_pause", 0.03) or 0))
                t = w.data.creation_type(did)
                if t in types and did not in {d for d, _t, _n, _p in out}:
                    out.append((did, t, names.get(did, ""), p))
        self._show = out
        w.data._scripts[cache_key] = out          # later matches on this map: no second read
        m.log(f"showroom: {len(out)} world states from packs " + " ".join(f"{p:#x}" for p in packs))
        for n, (did, t, name, p) in enumerate(out, 1):
            m.log(f"showroom item {n}: {did:#x} type {t} pack {p:#x} {name}")
        return out

    def show(self, n, carrier=False):
        items = self.showroom_list()
        if items is None:
            self.say("Vitrina: preparing the list, try again in a few seconds")
            return
        w, ch = self.w, self.w.champion
        if not items:
            self.say("Vitrina: nothing to show")
            return
        if ch is None or not ch.alive:
            self.say("Vitrina: the champion is not alive")
            return
        old = getattr(self, "_shown", None)
        if old is not None and old.eid in w.entities:
            w.remove(old, f"{old.name} removed (0x3)")
        self.si = max(0, min(len(items) - 1, n))
        did, t, name, p = items[self.si]
        d = float(self.m.ic.get("showroom_distance", 5.0) or 5.0)
        x, y = ch.pos[0] + math.cos(ch.heading) * d, ch.pos[1] + math.sin(ch.heading) * d
        try:
            # carrier: the exe patch's class 0x4A + low bits (icserver/patcher.py: a bare world state may be built and
            # never placed)
            # carrier = True (slot 0, the Door) or a slot 0-5 of the patch's table (icserver/patcher.py
            # PROP_CARRIERS_DEFAULT: 3 = 0x4000081B, Crime Alley's own gaslight truck entity)
            slot = 0 if carrier is True else int(carrier or 0)
            cls = ((0x4A + slot) << 24 | (did & 0xFFFFFF)) if carrier is not False else did
            ent = w.spawn(cls, [x, y, ch.pos[2]], ch.heading + math.pi, name=f"showroom {did:#x}", start=False,
                          world_state=did)
            if carrier is not False:
                w.dress_spawned(ent)
                # 2026-10-26 14:50 (diag --create: the carrier vehicle crashed in CDestructionComponent 0x62F960 ->
                # 0x4E1100 on a null destruction record: 0x57FCD0 reads property 0x800 from the carrier entity's
                # template, which has none): the world state's own 0x800 goes in the bundle
                rec = w.data.record_u32(did, 0x800)
                if rec and self.m.ic.get("carrier_destruction_record", True):
                    ent.extra_props.append((0x800, 0x15, rec))
                # 2026-10-26 15:54 (tester: no crash now, nothing drawn): Tutorial 1's carrier props showed in the
                # layout's cell 0xFB and after a re-send ([ics] carrier_cell, carrier_resend)
                cell = self.m.ic.get("carrier_cell", 0xFB)
                if cell is not None:
                    ent.cell = int(cell)
        except Exception as e:                      # noqa: BLE001
            self.say(f"Vitrina {self.si + 1}/{len(items)}: {did:#x} not created ({e!r})"[:240])
            return
        ent.kind, ent.health, ent.max_health, ent.kit = "prop", None, None, {}
        ent.pos[2] = ch.pos[2]
        w.update(ent, f"showroom: {did:#x} (type {t})")
        self._shown = ent
        rec = w.data.record_u32(did, 0x800)
        if rec and self.m.ic.get("destruction_reset_event", True):
            # a destructible (0x800) draws only after 0x8B builds its pieces (destructible-vehicles.md)
            from .. import messages as M
            for at in self.m.ic.get("destruction_reset_delays") or [0.3, 1.0, 3.0]:
                self.m.later(float(at), lambda e=ent: w.send(f"{e.name}: rebuild intact (0x8b)", M.destruction_reset(e.eid))
                             if e.eid in w.entities else None)
        if carrier is not False:
            for again in self.m.ic.get("carrier_resend") or ():
                # a creation retry: a full bundle in delta mode too (2026-10-28 15:00, object-update-bundles.md 10.3)
                self.m.later(float(again), lambda e=ent: w.update(e, f"{e.name} again", full=True)
                             if e.eid in w.entities else None)
        for k, key in enumerate(self.m.ic.get("showroom_scriptlets") or ["Vfx_Startup", "Object_Closed", "Vfx_Active"]):
            self.m.later(0.3 + 0.3 * k, lambda e=ent, s=key: w.scriptlet(e, s, f"{e.name}: {s} (0x8d)")
                         if e.eid in w.entities else None)
        text = (f"Vitrina {self.si + 1}/{len(items)}: {did:#x} tipo {t}"
                + (f" (portadora {cls:#x})" if carrier is not False else "")
                + (f" - {name}" if name else ""))
        self.m.log("showroom " + text)
        self.say(text[:240])

    def showroom(self, words):
        """vitrina | vitrina N | vitrina atras | vitrina auto S | vitrina stop: the element appears ~5 m in front."""
        arg = words[1].lower() if len(words) > 1 else ""
        cur = getattr(self, "si", -1)
        if arg in ("stop", "parar", "fin"):
            self._token += 1
            self.say("Vitrina: stopped")
            return
        if arg in ("atras", "back", "prev"):
            self.show(cur - 1)
            return
        if arg == "auto":
            every = float(words[2]) if len(words) > 2 else 4.0
            self._token += 1
            token = self._token

            def step():
                if token != self._token or self.m.over:
                    return
                if getattr(self, "si", -1) + 1 >= len(self.showroom_list() or ()):
                    self.say("Vitrina: end")
                    return
                self.show(getattr(self, "si", -1) + 1)
                self.m.later(every, step)
            step()
            return
        if arg.isdigit():
            c = words[2].lower() if len(words) > 2 else ""
            # "p" = carrier slot 0 (the Door), "p3" = slot 3 (0x4000081B, the truck entity), ...
            carrier = (int(c[1:]) if c[1:].isdigit() and 0 <= int(c[1:]) <= 5 else True) if c[:1] == "p" else False
            self.show(int(arg) - 1, carrier=carrier)
            return
        self.show(cur + 1)

    def vehicle(self, words):
        """vehiculo N (1..7): the gallery's vehicle N alone in front of the champion, as a showroom item (2026-10-26:
        tester, the seven vehicles drew in a row and could not be told apart)."""
        gallery = [_ws for _cls, _ws in (self.m.ic.get("liftable_gallery_classes") or ())]
        arg = words[1] if len(words) > 1 else ""
        if not arg.isdigit() or not 1 <= int(arg) <= len(gallery):
            self.say(f"Vehiculo: 1-{len(gallery)}")
            return
        want = int(str(gallery[int(arg) - 1]), 0)
        items = self.showroom_list()
        if items is None:
            self.say("Vitrina: preparing the list, try again in a few seconds")
            return
        k = next((i for i, it in enumerate(items) if it[0] == want), None)
        if k is None:
            self.say(f"Vehiculo {arg}: {want:#x} not in this map's packs")
            return
        self.show(k)
        self.say(f"Vehiculo {arg}/{len(gallery)}: {want:#x}")

    def command(self, words):
        """/tour | /tour sig | /tour atras | /tour N | /tour auto S | /tour stop | /tour reset"""
        arg = words[1].lower() if len(words) > 1 else ""
        if arg in ("stop", "parar", "fin"):
            self.auto = 0.0
            self._token += 1
            self.say("Tour: stopped")
            return
        if arg in ("reset", "rehacer"):
            self.stops, self.i = [], -1
            self.build()
            self.say(f"Tour: {len(self.stops)} stops")
            return
        if arg in ("atras", "back", "prev"):
            self.go(self.i - 1)
            return
        if arg == "auto":
            self.auto = float(words[2]) if len(words) > 2 else 6.0
            self._token += 1
            token = self._token

            def step():
                if token != self._token or self.m.over:
                    return
                if self.i + 1 >= len(self.stops) and self.stops:
                    self.say("Tour: end")
                    return
                self.go(self.i + 1)
                self.m.later(self.auto, step)
            step()
            return
        if arg.isdigit():
            self.go(int(arg) - 1)
            return
        self.go(self.i + 1)
