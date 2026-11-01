"""An encounter's flow: what happens when, as a list of steps.

The game data has the pieces (objective table, conversation catalogue, cinematics, layout placements, units,
scriptlets) but not their order or triggers: the original server drove them (docs/re-notes/tutorial-data-inventory.md
section 6.6). A flow module (ics/encounters/<name>.py) lists STEPS; each step is a dict:

    {"name": "first_drone",
     "do": [("say", 0x1AC), ("objective", 2), ("spawn", "drone", ["03MeleeC"]), ("aggro", "drone")],
     "until": ("killed", "drone")}

Actions run in order ("say" and "wait" hold the next one back; "cinematic" waits for the client to end it).
When the actions are done the step waits for its "until" trigger, then the next step starts.

Actions:
  ("wait", s)                      pause
  ("say", key) / ("say_bg", key)   a conversation (0x2001); "say" waits for its length (catalog conversations.tsv)
  ("objective", n[, done])         objective n of the encounter's table (text by reference); the old one completes
  ("progress", n)                  the objective's counter
  ("cinematic", did)               plays it (0x20F5, its scenes' scripts) and waits for the client's end notice
  ("hud",) / ("hud", [elements])   every HUD element shown / these (0x213D ShowElement; a tutorial starts with only
                                   the objective tracker and the hints, BaseHudElement.SetInitialVisibilityBasedOnEncounter)
  ("hud_hide", [elements])         0x213D HideElement (never a skill button: the skill panel hides as a whole)
  ("highlight", element, id[, arrows])   a tutorial highlight frame (gmUIHUDHighlightIDList id) on an element
  ("highlight_off", element)       the element's highlights go
  ("skill_button", slot[, on])     a skill slot's button revealed and usable (False: the slot refused again)
  ("after", s, action)             an action s seconds later, without holding the step
  ("spawn", group, [names])        layout placements by name (their class, position, side from the data)
  ("spawn_at", group, name, [(x, y, yaw), ...][, side[, props]])   copies of placement `name` at authored positions
  ("scriptlet", target, name)      a scriptlet by name on a placement / group ("Object_Open", "Vfx_OnExplode" ...)
  ("open", door) / ("close", door) Object_Open / Object_Closed
  ("remove", group)                the group's objects removed; ("remove_named", name) one object by name
  ("aggro", group[, radius])       the group's units go for the champion (radius 0 = only when attacked)
  ("only_skill", group, slot)     neutral targets only that skill slot hurts (others: flow.IMMUNE_LINES once)
  ("walk", target, position)       a placement / group walks somewhere along the navmesh (the thug runs off)
  ("level", n)                     the champion reaches level n (one skill point per level)
  ("ranks", [slots])               the skills whose "+" may be clicked (None = any); their "+" get the tutorial arrow
  ("marker", x, y) / ("marker_off",)   guide marker (minimap ping object) at a spot
  ("guide", group)                 a guide ring on each of the group and the champion's arrow at the first living one
  ("hint", id)                     tutorial hint
  ("call", fn)                     fn(director) from the flow module (anything the list cannot say)
  ("if", key, [actions], [actions]) the first list when [ics] <key> is true (default), else the second (at start)
  ("victory",)                     the match ends, won
Triggers ("until"):
  ("reach", x, y, r) or ("reach", "position name", r)   ("killed", group[, n])   ("cast", slot)
  ("ranked", slot, [slots] or None)   ("time", s)   ("preference", name, value, ...) (client setting 0x216E)
"""
import math
import struct
import time
import traceback

from . import messages as M

OBJECTIVE_CATEGORY = 1
OBJECTIVE_CATEGORY_SHOW = 8
STATE_ACTIVE, STATE_DONE = 1, 2
NOTICE_CINEMATIC_ENDED = 4

# HUD element ids (emp_gen gmUIHUDElementIDList) and highlight ids (gmUIHUDHighlightIDList), from the UI scripts
HUD_VITALS, HUD_SKILLS_BAR, HUD_MINIMAP, HUD_PORTRAIT, HUD_LEVEL_XP = 2, 14, 15, 18, 20
HUD_STATUS_ICONS, HUD_HINTS, HUD_OBJECTIVES = 31, 32, 35
# skill slot -> its button element (SkillsPanel.ShowElement reveals m_SkillControlN); slot 0 = the basic attack
SKILL_BUTTON = {0: 6, 1: 9, 2: 17, 3: 25, 4: 12, 5: 7, 7: 22, 8: 23}
SKILL_HIGHLIGHT = {1: 2, 2: 10, 3: 4, 4: 13, 5: 17, 7: 3, 8: 16}          # SkillsPanel<Slot>Skill
UPGRADE_HIGHLIGHT = {1: 15, 2: 7, 3: 11, 4: 12, 5: 9}                    # SkillsPanel<Slot>UpgradeButton
UPGRADE_BUTTON = {1: 30, 2: 4, 3: 28, 4: 5, 5: 19}
HL_VITALS, HL_WILL, HL_LEVEL_XP, HL_MINIMAP = 25, 53, 24, 20


def flow_classes(flow, ic):
    """The classes a flow creates by DID (spawn_at with a class, its EXTRA_CLASSES) and the guide marker's: read
    ahead with Data.prepare so that no step waits for the packs."""
    out = set(getattr(flow, "EXTRA_CLASSES", ()))
    def walk(actions):
        for a in actions:
            if a and a[0] == "if":
                walk(list(a[2]) + list(a[3] if len(a) > 3 else ()))
                continue
            if a and a[0] == "after":
                a = a[2]
            if a and a[0] == "spawn_at" and isinstance(a[2], int):
                out.add(int(a[2]))
    for step in getattr(flow, "STEPS", ()):
        walk(step.get("do", ()))
    if ic.get("marker_class"):
        out.add(int(ic["marker_class"]))
    return sorted(out)


class Director:
    def __init__(self, session, world, flow, encounter):
        self.s, self.w, self.flow = session, world, flow
        self.encounter = encounter
        self.steps = [self._expand(st, session.ic) for st in flow.STEPS]
        self.positions = dict(getattr(flow, "POSITIONS", {}))
        self.i = -1
        self.step = None
        self.pc = 0                        # next action of the current step
        self.waiting = None                # the trigger the step waits for
        self.groups = {}                   # group -> [entities]
        self.kills = {}                    # group -> defeated so far
        self.objective = None              # (index, count so far)
        self.allowed_ranks = None
        self.marker = None
        self.guides = {}                   # guided target -> its ring (a guide marker at its spot)
        self.cinematic = None              # the cinematic being waited for
        self.speaking_until = 0.0          # the current conversation ends (time.time())
        self.conv_queue = []               # conversations waiting for the one that plays
        self.playing = None                # the playing conversation's instance id (or ("scene", key))
        self.say_wait = None               # the queued "say" the step waits for (it ends -> run())
        self.started = time.time()
        self.data = world.data
        self.table = self.data.objectives(encounter)
        world.listeners.append(self.on_event)
        world.rank_filter = self.rank_filter
        self.log = world.log
        # the HUD and the skill buttons come piece by piece when the flow reveals them ("hud", "skill_button");
        # [ics] tutorial_progressive_hud = false shows every element at the first "hud" and allows every slot
        self.progressive = bool(session.ic.get("tutorial_progressive_hud", True)) and any(
            a and a[0] == "skill_button" for st in self.steps for a in st.get("do", ()))
        self.shown_slots = {0}
        self.arrows = False                # tutorial arrows on "+" buttons are up
        if self.progressive:
            world.cast_filter = self.cast_filter

    @staticmethod
    def _expand(step, ic):
        """("if", config key, [actions], [actions]) in a step's list becomes the first list when [ics] <key> is true
        (default true), else the second: a flow's visual changes can be switched back from config.toml."""
        out = []
        for a in step.get("do", ()):
            if a and a[0] == "if":
                out += list(a[2] if ic.get(a[1], True) else (a[3] if len(a) > 3 else ()))
            else:
                out.append(a)
        return dict(step, do=out)

    # ---- running --------------------------------------------------------------------------------
    def start(self):
        self.log(f"director: {len(self.steps)} steps")
        self.next_step()

    def next_step(self):
        self.i += 1
        if self.i >= len(self.steps):
            self.log("director: flow finished")
            self.step = None
            return
        self.step = self.steps[self.i]
        self.pc = 0
        self.waiting = None
        self.early = []                    # events that came while the step still ran its actions
        self.log(f"director: step {self.i} '{self.step.get('name', '')}'")
        self.run()

    def jump(self, name):
        """Start at a named step (testing; [ics] director_start)."""
        for i, st in enumerate(self.steps):
            if st.get("name") == name:
                self.i = i - 1
                self.next_step()
                return True
        return False

    def run(self):
        """Run actions until one has to wait, then the step's trigger."""
        step = self.step
        actions = step.get("do", ())
        while self.step is step and self.pc < len(actions):
            action = actions[self.pc]
            self.pc += 1
            try:
                hold = self.act(action)
            except Exception:              # noqa: BLE001 - one broken action must not stop the flow
                self.log(f"director: action {action!r} failed\n{traceback.format_exc()}")
                hold = 0.0
            if hold is None:               # waits for an event (cinematic)
                return
            if hold > 0:
                self.s.later(hold, lambda st=step: self.run() if self.step is st else None)
                return
        if self.step is not step:
            return
        until = step.get("until")
        if not until:
            self.next_step()
            return
        # one trigger, or a list of them (any one ends the step)
        self.waiting = list(until) if isinstance(until, list) else [until]
        for t in self.waiting:
            if t[0] == "time":
                self.s.later(float(t[1]), lambda st=step, t=t: self._fire(st, t))
            elif t[0] == "killed" and self._killed_enough(t):
                self._fire(step, t)
                return
        # 2026-10-22 10:21 (tester: stuck at "unlock Sonic Batarang"): Q was ranked during the step's own dialogue,
        # before its trigger was armed; an event that came early still ends the step
        for event, d in getattr(self, "early", ()):
            for t in self.waiting or ():
                if self.step is step and self._matches(t, event, d):
                    self._fire(step, t)
                    return

    def _fire(self, step, t):
        if self.step is step and self.waiting:
            self.log(f"director: '{step.get('name', '')}' done ({t[0]})")
            self.waiting = None
            self.next_step()

    # ---- triggers -------------------------------------------------------------------------------
    def tick(self):
        """Called by the session's tick: position triggers."""
        ch = self.w.champion
        for t in self.waiting or ():
            if t[0] != "reach" or ch is None:
                continue
            if isinstance(t[1], str):
                (x, y), r = self._xy(t[1]), float(t[2])
            else:
                x, y, r = self._xy(t[1:3]) + (float(t[3]),)
            if math.hypot(ch.pos[0] - x, ch.pos[1] - y) <= r:
                self._fire(self.step, t)
                return

    def on_event(self, event, **d):
        if event == "conversation" and self.s.ic.get("queue_scene_conversations", True):
            # 2026-10-22 08:13 (tester: Superman still repeats lines): the intro's scene script starts 441 (0x1B9)
            # and 0x1BA came 2 s later over it; two conversations at once make the client repeat lines. The client
            # plays a scene's conversations itself (no 0x2140 comes back): their catalog length holds the queue.
            length = self.data.conversation_seconds(d["key"], float(self.s.ic.get("scene_conversation_seconds", 6.0)))
            token = ("scene", d["key"], time.time())
            self.playing = token
            self.s.later(length, lambda t=token: self._finished(t))
            return
        if event == "conversation_done":
            self._finished(d.get("instance"))
            return
        if event == "immune":
            # a practice target hit by the wrong attack: the flow's lines, each once (IMMUNE_LINES: "basic" for the
            # basic attack, "skill" for another skill; the earlier server's bridge.wrong_attack)
            lines = getattr(self.flow, "IMMUNE_LINES", {}).get("basic" if d.get("slot") == 0 else "skill", ())
            said = self.__dict__.setdefault("immune_said", set())
            for key in lines:
                if key not in said:
                    said.add(key)
                    self.conv_queue.append((key, object()))
                    self._pump()
                    break
            return
        if event == "killed":
            ent = d.get("ent")
            mk = self.guides.pop(ent, None)
            if mk is not None:
                if mk.eid in self.w.entities:
                    self.w.remove(mk, f"{mk.name} removed (0x3)")
                self._guide_next()
            for g, members in self.groups.items():
                if ent in members:
                    self.kills[g] = self.kills.get(g, 0) + 1
                    if self.objective and self.table_entry(self.objective[0]).get("count"):
                        self.set_progress(self.objective[1] + 1)
        if event == "ranked" and self.arrows:
            # the clicked "+" loses its arrow; the others keep theirs while points are left
            ch = self.w.champion
            left = [x for x in (self.allowed_ranks or ()) if x != d.get("slot")] \
                if ch is not None and getattr(ch, "skill_points", 0) > 0 else []
            self._rank_arrows(left)
        if self.waiting is None and self.step is not None and event in ("ranked", "cast", "preference", "hit"):
            self.early.append((event, d))
        for t in self.waiting or ():
            if self._matches(t, event, d):
                self._fire(self.step, t)
                return

    def _matches(self, t, event, d):
        if event != t[0] and not (event == "killed" and t[0] == "killed"):
            return False
        if event == "killed":
            return self._killed_enough(t)
        if event == "preference":
            return d.get("name") == t[1] and str(d.get("value", "")).lower() in [str(v).lower() for v in t[2:]]
        if event == "cast":
            return d.get("slot") == t[1]
        if event == "hit":                 # ("hit", group): the champion hits one of the group
            return d.get("ent") in self.groups.get(t[1], ()) and d.get("source") is self.w.champion
        if event == "ranked":
            want = t[1] if len(t) > 1 else None
            return want is None or d.get("slot") == want or (isinstance(want, (list, tuple)) and d.get("slot") in want)
        return False

    def _killed_enough(self, t):
        group = t[1]
        n = t[2] if len(t) > 2 else len(self.groups.get(group, ()))
        return n > 0 and self.kills.get(group, 0) >= n

    def cinematic_state(self, did, state):
        if state == NOTICE_CINEMATIC_ENDED and self.cinematic == did:
            self.cinematic = None
            self.log(f"director: cinematic {did:#x} ended")
            self.s.later(0.5, self.run)

    def _pump(self):
        if self.playing is not None or not self.conv_queue:
            return
        key, token = self.conv_queue.pop(0)
        inst = self.w.say(key)
        self.playing = inst
        self._tokens = getattr(self, "_tokens", {})
        self._tokens[inst] = token
        # the client's 0x2140 normally ends it; the catalog length (+ a margin) is the fallback
        margin = 1.5 if self.s.ic.get("conversation_done_event", True) else 0.0
        self.s.later(self.data.conversation_seconds(key) + margin, lambda i=inst: self._finished(i))

    def _finished(self, inst):
        if inst is None or inst != self.playing:
            return
        self.playing = None
        token = getattr(self, "_tokens", {}).pop(inst, None)
        gap = float(self.s.ic.get("conversation_gap", 0.4))

        def next_one():
            self._pump()
            if token is not None and self.say_wait is token:
                self.say_wait = None
                self.run()
        self.s.later(gap, next_one)

    def rank_filter(self, slot):
        return self.allowed_ranks is None or slot in self.allowed_ranks

    def cast_filter(self, slot):
        return slot in self.shown_slots

    def _rank_arrows(self, slots):
        """The tutorial arrow over each rankable skill's "+" (0x213D ShowArrowHighlight, SkillsPanel<Slot>Upgrade
        Button: the original's "Click the highlighted button"), or none (HideHighlight on the skill panel)."""
        if not self.s.ic.get("tutorial_rank_arrows", True):
            return
        msgs = []
        if self.arrows:
            msgs.append(("skill '+' arrows off (0x213d)", M.hud_element(HUD_SKILLS_BAR, M.HUD_HIGHLIGHT_OFF)))
            self.arrows = False
        for slot in sorted(slots or ()):
            if slot in UPGRADE_HIGHLIGHT:
                msgs.append((f"arrow on slot {slot}'s '+' (0x213d)",
                             M.hud_element(UPGRADE_BUTTON[slot], M.HUD_ARROW_HIGHLIGHT, UPGRADE_HIGHLIGHT[slot])))
                self.arrows = True
        if msgs:
            self.s.send_many(msgs)

    # ---- actions --------------------------------------------------------------------------------
    def act(self, a):
        """Run one action; returns the seconds to wait before the next one (None = until an event)."""
        kind = a[0]
        w, s = self.w, self.s
        if kind == "wait":
            return float(a[1])
        if kind in ("say", "say_bg"):
            # one conversation at a time: a new one while another plays made the client repeat lines (2026-10-21
            # 21:46, tester: "some dialogues repeat"; 0x1AC came 0.5 s after the 11 s 0x19C). They queue; the next
            # starts when the client reports the last one finished (0x2140), or after its catalog length.
            token = object()
            self.conv_queue.append((a[1], token))
            if kind == "say":
                self.say_wait = token
            self._pump()
            if kind == "say" and self.say_wait is token:
                return None                # run() again when it has played
            return 0.0
        if kind == "objective":
            self.set_objective(int(a[1]))
            return 0.0
        if kind == "progress":
            self.set_progress(int(a[1]))
            return 0.0
        if kind == "cinematic":
            self.cinematic = int(a[1])
            s.play_cinematic(self.cinematic)
            return None
        if kind == "hud":
            # 2026-10-22 14:43 (tester: the whole HUD was there from the start; original's videos: the tutorial
            # reveals it piece by piece): ("hud", [elements]) shows those; ("hud",) or a non-progressive flow, all
            s.show_hud(list(a[1]) if len(a) > 1 and self.progressive else None)
            return 0.0
        if kind == "hud_hide":
            s.send_many([(f"HUD element {e} hidden (0x213d)", M.hud_element(e, M.HUD_HIDE)) for e in a[1]])
            return 0.0
        if kind == "highlight":
            # ("highlight", element, highlight id[, arrows]): the yellow tutorial frame (0x213D ShowHighlight /
            # ShowArrowHighlight); only elements whose UI class draws tips show it (skill panel, vitals, XP, minimap)
            if self.progressive:
                ev = M.HUD_ARROW_HIGHLIGHT if len(a) > 3 and a[3] else M.HUD_HIGHLIGHT
                s.send(f"highlight {a[2]} on HUD element {a[1]} (0x213d)", M.hud_element(int(a[1]), ev, int(a[2])))
            return 0.0
        if kind == "highlight_off":
            if self.progressive:
                s.send(f"highlights off on HUD element {a[1]} (0x213d)", M.hud_element(int(a[1]), M.HUD_HIGHLIGHT_OFF))
            return 0.0
        if kind == "skill_button":
            # ("skill_button", slot[, on]): the slot's button is revealed (SkillsPanel.ShowElement; the bar itself
            # with the first one) and the champion may use it. Off only refuses it again: a HideElement on a skill
            # button hides the whole skill panel (BaseHudElement.HideElement), so none is sent
            slot, on = int(a[1]), (a[2] if len(a) > 2 else True)
            if not on:
                self.shown_slots.discard(slot)
                return 0.0
            self.shown_slots.add(slot)
            if self.progressive and slot in SKILL_BUTTON:
                s.show_hud([SKILL_BUTTON[slot]])
            return 0.0
        if kind == "after":
            step = self.step

            def later(action=a[2]):
                try:
                    self.act(action)
                except Exception:      # noqa: BLE001
                    self.log(f"director: action {action!r} failed\n{traceback.format_exc()}")
            self.log(f"director: {a[2]!r} in {float(a[1]):.1f} s" + (f" (step '{step.get('name', '')}')" if step else ""))
            s.later(float(a[1]), later)
            return 0.0
        if kind == "spawn":
            self._spawn(a[1], [self._placement(n) for n in a[2]])
            return 0.0
        if kind == "spawn_at":
            # a placement's copy, or a class DID (the practice targets 0x40000BA9, the meteor crater 0x40000CAB)
            base = self._placement(a[2]) if isinstance(a[2], str) else {
                "name": a[1], "class": int(a[2]), "wstate": 0, "props": {}, "heading": 0.0,
                "pos": [0.0, 0.0, w.ground_z]}
            if len(a) > 5 and a[5] and base:
                # extra placement properties, e.g. {0x6B4: 0.3} (scale); floats as their u32 bits, as in a layout
                extra = {k: struct.unpack("<I", struct.pack("<f", v))[0] if isinstance(v, float) else v
                         for k, v in a[5].items()}
                base = dict(base, props={**base.get("props", {}), **extra})
            side = a[4] if len(a) > 4 else (base or {}).get("props", {}).get(0x100007A2)
            pls = []
            for spot in a[3]:
                x, y = self._xy(spot[:2])
                yaw = spot[2] if len(spot) > 2 else (base or {}).get("heading", 0.0)
                pls.append(dict(base or {}, pos=[x, y, (base or {}).get("pos", [0, 0, w.ground_z])[2]],
                                heading=yaw, side=side))
            self._spawn(a[1], pls)
            return 0.0
        if kind in ("scriptlet", "open", "close"):
            name = {"open": "Object_Open", "close": "Object_Closed"}.get(kind) or a[2]
            for ent in self._targets(a[1]):
                if not w.scriptlet(ent, name):
                    self.log(f"director: {ent.name} has no scriptlet {name}")
            return 0.0
        if kind == "remove_named":
            for ent in [e for e in w.entities.values() if e.name == a[1]]:
                w.remove(ent, f"{ent.name} removed (0x3)")
            return 0.0
        if kind == "remove":
            for ent in self.groups.pop(a[1], []):
                if ent.eid in w.entities:
                    w.remove(ent)
            return 0.0
        if kind == "walk":
            # a unit walks somewhere on its own (the human thug runs off), with no fight on the way
            x, y = self._xy(a[2])
            for ent in self._targets(a[1]):
                ent.aggro, ent.attack_target = 0.0, None
                ent.move_speed = max(ent.move_speed, float(self.s.ic.get("flee_speed", 4.0)))
                w.walk_to(ent, [x, y, ent.pos[2]])
            return 0.0
        if kind == "knockdown":
            # 2026-10-22 10:06 (tester: Batman should fall when the meteor lands): the earlier server's face-down
            # knockdown, raised on his animation graph: CbtState_Knockdown, CbtState_Dead (the held pose), then
            # RunScript_Vfx_GetUp + CbtState_GetUp; his orders are ignored meanwhile
            # 2026-10-22 (decompiled: docs/re-notes/client-status-effects.md, client-movement.md): the client knows
            # a champion is disabled only through his bool attributes: 0x10000B2D blocks every order (0x9cfaf0, no
            # 0x20EE is sent), 0x100003F3 (Stunned) holds skills; the stun / knockdown status scripts set them. He
            # is stopped with an explicit speed-0 state (the server drives his position)
            ch = w.champion
            hold = float(a[1]) if len(a) > 1 else 5.0
            ch.dest, ch.path, ch.speed, ch.attack_target = None, [], 0.0, None
            ch.down_until = time.time() + hold
            w.update(ch, "Batman stops (knockdown, speed 0)")
            flags = [int(str(p), 0) for p in self.s.ic.get("knockdown_flags", ["0x10000B2D", "0x100003F3"])]
            for prop in flags:
                w.send(f"Batman: {prop:#x} = 1 (0x6, disabled)", M.set_property(ch.eid, prop, M.KIND_BOOL, 1))
            w.graph_event(ch, 0x100002F5, "Batman knocked down (CbtState_Knockdown)")
            self.s.later(1.8, lambda: w.graph_event(ch, 0x1000010B, "Batman lies face down (CbtState_Dead)"))

            def up():
                w.scriptlet(ch, 0x10000490, "Batman gets up: RunScript_Vfx_GetUp (0x8d)")
                w.graph_event(ch, 0x1000009D, "Batman gets up (CbtState_GetUp)")

                def free():
                    for prop in flags:
                        w.send(f"Batman: {prop:#x} = 0 (0x6, free)", M.set_property(ch.eid, prop, M.KIND_BOOL, 0))
                self.s.later(float(self.s.ic.get("knockdown_free_after", 0.5)), free)
            self.s.later(hold, up)
            return 0.0
        if kind in ("untargetable", "targetable"):
            # 2026-10-22 10:06 (tester: the drone may only be attacked once the dialogue says so): its targeting
            # properties are held back, then sent (event 0x6) with a full bundle, which is what made the earlier
            # drones targetable when they started fighting
            for ent in self._targets(a[1]):
                if kind == "untargetable":
                    ent.hold_flags = True
                    continue
                ent.hold_flags = False
                flags = getattr(ent, "pending_flags", None)
                if flags:
                    w._late_flags(ent, flags)
                w.update(ent, f"{ent.name}: targetable (bundle)")
            return 0.0
        if kind == "only_skill":
            # ("only_skill", group, slot): the practice targets (0x40000BA9, neutral) are targets of the champion's
            # effects and only that skill slot hurts them (2026-10-22 14:10, tester: Sonic Batarang and basic attacks
            # did nothing to them; original objective "press Q to destroy it with Sonic Batarang")
            for ent in self._targets(a[1]):
                ent.hittable = True
                ent.only_slot = int(a[2])
            return 0.0
        if kind == "fight":
            # ("fight", group, other group | "champion"): the group's units attack someone (the drone and the human)
            others = [w.champion] if a[2] == "champion" else self._targets(a[2])
            for ent in self._targets(a[1]):
                ent.attack_target = others[0] if others else None
            return 0.0
        if kind == "aggro":
            radius = float(a[2]) if len(a) > 2 else math.inf
            for ent in self._targets(a[1]):
                ent.aggro = radius
            return 0.0
        if kind == "level":
            w.set_level(int(a[1]))
            return 0.0
        if kind == "points":
            w.champion.skill_points += int(a[1])
            w.refresh_champion(f"{int(a[1])} skill point(s)")
            return 0.0
        if kind == "ranks":
            self.allowed_ranks = None if a[1] is None else set(a[1])
            w.refresh_champion("skill '+' buttons")
            # 2026-10-22 (original's videos 1:41, 3:00, 9:57: a yellow arrow over each "+" to click)
            if self.progressive:
                self._rank_arrows(self.allowed_ranks)
            return 0.0
        if kind == "marker":
            self.set_marker(self._xy(a[1:3] if len(a) > 2 else a[1]))
            return 0.0
        if kind == "marker_off":
            self.set_marker(None)
            return 0.0
        if kind == "guide":
            # ("guide", group): what the targets' own 0x34000600 shows (IsActive 0x10000B94 = 1 in the practice
            # target's template): a ping ring on each and the champion's arrow at the first (original Part 1 video
            # 1:55-2:05: a green ring on each practice target, green chevrons at Batman's feet). The rings are guide
            # markers at their spots (their tables have neither guide scriptlet); a target's ring goes when it dies.
            if not self.s.ic.get("guide_targets", True) or not int(self.s.ic.get("marker_class", 0) or 0):
                return 0.0
            for ent in self._targets(a[1]):
                mk = self._marker_at(ent.pos, f"guide ring {ent.name}")
                self.guides[ent] = mk
                self._guide_fx(mk, ent, roles=("marker",))
            self._guide_next()
            return 0.0
        if kind == "hint":
            s.send(f"tutorial hint {a[1]}", M.tutorial_hint(int(a[1])))
            return 0.0
        if kind == "call":
            out = a[1](self)
            return float(out or 0.0)
        if kind == "victory":
            s.victory(time.time() - self.started)
            return 0.0
        self.log(f"director: unknown action {a!r}")
        return 0.0

    def _xy(self, v):
        if isinstance(v, (list, tuple)) and len(v) == 1:
            v = v[0]
        if isinstance(v, str):
            p = self.positions.get(v) or (self._placement(v) or {}).get("pos")
            return float(p[0]), float(p[1])
        return float(v[0]), float(v[1])

    def _placement(self, name):
        pl = self.w.placements(self.s.encounter_info()).get(name)
        if pl is None:
            self.log(f"director: no layout placement '{name}'")
        return pl

    def _spawn(self, group, placements):
        w = self.w
        made = []
        for pl in placements:
            if not pl:
                continue
            n = len(self.groups.get(group, ())) + len(made)
            ent = w.spawn(pl["class"], list(pl["pos"]), pl["heading"], side=pl.get("side", pl["props"].get(0x100007A2)),
                          name=pl["name"] if pl["name"] != group else f"{group}{n + 1}", world_state=pl["wstate"],
                          placement=pl)
            ent.aggro = 0.0 if ent.kind == "unit" else None   # quiet until an "aggro" (or attacked)
            made.append(ent)
            self.s.send(f"spawn {ent.name} ({ent.class_id:#x})", w.bundle(ent))
            w.vitals(ent)
            w.spawn_in(ent)
        self.groups.setdefault(group, []).extend(made)
        if made:
            self.s.later(float(self.s.cfg["timing"].get("prop_scriptlet_delay", 1.0)),
                         lambda: [w.initial_scriptlets(e) for e in made if e.eid in w.entities])
        return made

    def _targets(self, name):
        if name in self.groups:
            return [e for e in self.groups[name] if e.eid in self.w.entities]
        return [e for e in self.w.entities.values() if e.name == name]

    # ---- objectives / marker ---------------------------------------------------------------------
    def table_entry(self, index):
        lst = self.table.get("list", [])
        return lst[index] if 0 <= index < len(lst) else {}

    def set_objective(self, index):
        msgs = []
        if self.objective is not None:
            old = self.table_entry(self.objective[0])
            msgs.append((f"objective {old.get('id', 0):#x} done (0x2009)",
                         M.objective_update(M.objective(old.get("id", 0), state=STATE_DONE, active=False))))
        e = self.table_entry(index)
        self.objective = (index, 0)
        obj = M.objective(e.get("id", 0), text=e.get("text") or "", active=True, state=STATE_ACTIVE,
                          category=OBJECTIVE_CATEGORY, sort_order=index, optional=False,
                          count=0 if e.get("count") else None, count_max=e.get("count"),
                          banner=(e.get("text") or "") if self.s.ic.get("objective_banner", True) else None)
        title = self.table.get("title") or ""
        msgs.append((f"objective {index} ({e.get('id', 0):#x}) (0x2034)",
                     M.objective_list([obj], [M.objective_category(OBJECTIVE_CATEGORY, title,
                                                                   state=OBJECTIVE_CATEGORY_SHOW)])))
        self.s.send_many(msgs)

    def set_progress(self, n):
        if self.objective is None:
            return
        index, _ = self.objective
        e = self.table_entry(index)
        self.objective = (index, n)
        self.s.send(f"objective {e.get('id', 0):#x}: {n}/{e.get('count')} (0x2009)",
                    M.objective_update(M.objective(e.get("id", 0), count=n)))

    def set_marker(self, xy):
        w = self.w
        if self.marker is not None and self.marker.eid in w.entities:
            w.remove(self.marker, "guide marker removed (0x3)")
        self.marker = None
        cls = int(self.s.ic.get("marker_class", 0) or 0)
        if xy is None or not cls:
            return
        ent = self._marker_at(xy, "guide marker")
        self.marker = ent
        self._guide_fx(ent, ent)

    def _marker_at(self, xy, name):
        w = self.w
        ent = w.spawn(int(self.s.ic["marker_class"]), [xy[0], xy[1], w.ground_z], name=name)
        ent.aggro = None
        self.s.send(f"{name} at ({xy[0]:.1f}, {xy[1]:.1f})", w.bundle(ent))
        return ent

    def _guide_fx(self, marker, aim, roles=("marker", "champion")):
        """What the guide script 0x34000600 does when 0x10000060 is raised on its entity (inventory 6.4): the
        ping on the marker, and the champion's Vfx_GuideArrow aimed at `aim`.
        2026-10-22 (tester after fase3-gp: no ground marker where to go, only the arrows at Batman's feet; original
        Part 1 video 0:43: a green ring at the spot): 0x34000600's locals (pack 0xA00000B3) name the FX templates
        its Vfx_GuideArrow_Ping / Vfx_GuideArrow play through script variable 0x1000050A (Group ping 0x1E00055E,
        Group arrow 0x1E000510; Alert 0x1E00055D / 0x1E000511). Both scriptlets only play "the FX template in
        0x1000050A"; the marker's table 0x1D0006E2 holds Vfx_GuideArrow (not _Ping), so the ping goes through it.
        [ics] marker_scriptlets: [on, scriptlet(, FX template)], the FX as variable 0x1000050A."""
        w = self.w
        for entry in self.s.ic.get("marker_scriptlets") or ():
            on, name = entry[0], entry[1]
            if on not in roles:
                continue
            fx = int(str(entry[2]), 0) if len(entry) > 2 and entry[2] else 0
            holder, target = (w.champion, aim) if on == "champion" else (marker, w.champion)
            variables = [(M.PROP_SCRIPT_FX, M.KIND_DID, fx)] if fx else None
            self.s.later(0.5, lambda h=holder, n=name, t=target, m=marker, v=variables:
                         w.scriptlet(h, n, target=t, variables=v)
                         if m.eid in w.entities and t is not None and (t is w.champion or t.eid in w.entities)
                         else None)

    def _guide_next(self):
        """The champion's arrow aims at the next living guided target (the practice targets, one after the other)."""
        for ent, mk in list(self.guides.items()):
            if ent.eid in self.w.entities and ent.alive:
                self._guide_fx(mk, ent, roles=("champion",))
                return
