# Vitals crash on a spawned skill object, hover picks in the fase3-im run (2026-10-29, fase3-in)

Tester run 19:46-19:55 (Crime Alley v AI, AGL vs AI Arcane Supergirl, `diag.py --hover` + skills): the game froze
and closed at 19:55:11. Labels: C = read in code / logs, P = probable, O = open.

## 1. The crash (C)

- diag.log: first-chance 0xC0000005 at **rva 0x6B1BD9** (runtime base 0x440000; static VA = rva + 0x400000 =
  **0xAB1BD9**), `ecx=0 edi=0`, thread 23032 (the main thread, the same one that runs the hover picker).
- 0xAB1BD9 is the 4th instruction of **0xAB1BD0** (push ebp / mov ebp,esp / sub esp,0x9C / **`inc [ecx+0x98]`**):
  the function's `this` is null. Its only caller is **0xAB2880**: `edi = arg1 ? [arg1+0x80] : 0; mov ecx, edi;
  call 0xAB1BD0` with no null check. 0xAB2880's caller is **0x8C26F0**, the executor of server event **0x42 Vitals**
  (`protocol-complete.md`: exec 0x8c26f0 / serializer 0x846fc0 / handler 0xab2880): it looks the object up (0x445070,
  an unknown object returns 0x80004002 harmlessly), then passes the entity (`[obj+4]`) to 0xAB2880. **`[entity+0x80]`
  is the vitals component** (slot 32, `full-entities-engine.md`), created only if PerceivedType `0x1000019D &
  0x7F59FB` (CreateGameComponents) at construction. So: a 0x42 to an existing object without a vitals component.
- The stack scan (diag's `stack_rvas` is a heuristic: every value on the stack inside the image) holds 0x8C276D (the
  return into 0x8C26F0 after `call 0xAB2880`), 0xAB2913, and the event dispatch 0xB0BD96 / 0xB0DC07 / 0xB0E43B /
  0x64958B / 0xB0DA95 / 0x64E28B (game router) / 0xB0C7B4 / 0xB0FAA9.
- traffic.log 19:55:11.454: **`0x40000bef of AI: Arcane Supergirl vitals 0/1 (0x42)`**, the only 0x42 the session
  ever sent to a spawned object; server.log 11.453 `0x40000bef ... takes 40 (0/1)` / `defeated`. 0x40000BEF is
  Supergirl's **Firewall** (W, script 0x3400054C, spawned 19:55:02.626). Its stat block has health 0x10000426 = 1.0,
  so `World.spawn` treated it as a variant unit with `client_vitals = True`; its template 0x49000BEF has **no
  0x1000019D**, so the client built no vitals component. AGL's Scorched Earth (W, 0x340002B2) hit it.
- Same rva as the 2026-10-25 23:22 crash (the jungle heavy drop 0x400005E1, PerceivedType 4 = Loot, `& 0x7F59FB` =
  0), which was patched per class (`spawned_inert_classes`). Now the rule is general.
- Not the debugger: the hover breakpoints are at 0xA82299 / 0xA88784 (other functions), the fault is a plain data
  read through a null `this`, and the same rva crashed on 2026-10-25 without `--hover`. Not property 0x100008CE
  (`vision_through_blockers_property`): nothing in this path reads it.
- Checked (C, headless): every map's units and structures that get 0x42 (Crime Alley, Gotham Divided, Gotham Heights,
  Coast City; minions 0x40000BF8 / 0x40000BFA / 0x4000010A / 0x4000010B, camps, turrets, cores, dampeners, foundries)
  pass the PerceivedType test (template or the role bits ics sends, `maps.PERCEIVED`); bot champions (8) and
  spawned fighters (Star Sapphire's Predator 0x400005D2, 0x110000) too.

### Fix (fase3-in)
- `World.vitals_component(ent)`: PerceivedType from the class template (`Data.target_properties`) OR'd with the
  0x1000019D the server sends (`extra_props`), `& 0x7F59FB`; the local / bot champions always pass. A failing object
  gets `client_vitals = False` (status icons / floaty numbers / CC events stop too). `[ics] vitals_need_perceived_type`.
- `CastWorld.spawn_entity`: a spawned object with health, no attack and no vitals component becomes an inert prop (no
  health, not hit, not killed early). `[ics] spawned_need_vitals_component`.

## 2. Hover picks (C log, P conclusions)

`--hover` logs one line per change: candidates at 0xA82299 (right after the score call 0xA16A60) and the tick's pick
at 0xA88784. `best_priority` / `score` printed "?" because `tracer.ev` did not parse `-` offsets (`[ebp-24]`); every
probe with `ebp-N` was broken. Fixed; the probe also logs `best_score` `[ebp-2c]`. At 0xA82299: `[ebp-3c]` = the
score just stored (f32), `[ebp-2c]` = the best score; the candidate wins when score > best (`jbe` at 0xA822A7), after
`flags & mask == mask` (0xA8225F) and priority >= `[ebp-24]` (0xA8226C).

What the run shows (iids matched to traffic.log labels; AGL is team 1):
- Enemy units **do** get flags 0x2 (box sweep) and 0x3 (ray + box) with priorities 1-3: Supergirl 0x100 (0x2: 80
  changes, 0x3: 49), team-2 minions of every wave (0x141, 0x143, 0x145, 0x147, 0x14B, 0x14D, 0x17A, 0x17E, 0x180,
  0x182, ...). They are **picked** by the tick (53 distinct picks: our champion, Supergirl, team 1 and team 2
  minions, turrets, the core, liftables).
- 0x20EE orders: 131 attack orders (command 2) on team-2 enemies (all from the client's own pick), 803 move orders
  with no pick, 24 on our champion, 23 on allies, 1 move order on an enemy; `click_assist` turned 7 move orders into
  attacks. In the 18:31 run the enemies were almost never in the box sweep (`ca-fog-stealth-hover.md` 3.2).
- Never picked: the base gate 0x115 (0x2 only, probably no validator / 0x2A1), Grab's arm missiles 0x40000485,
  Supergirl's companions 0x40000ADF, the Firewall, and minions of the last waves only seen for a moment.
- Conclusion (P): in this run the client's pick finds the enemies (the outline follows the pick, C); the tester did not
  report the outline. What changed since 18:31 is O (the scores were not logged); keep `click_assist_radius` and run
  `--hover` again with the fixed score / best_score fields if the outline is missing again.
