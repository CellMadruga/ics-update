# Skill range indicator that never ends; structures after the first turret (static analysis 2026-10-23)

Exe `InfiniteCrisis.exe` sha256 `463adfff...`, Ghidra 12.1.4 via REA, image base 0x400000, all addresses VA.
"C" = read in the decompiled code, "P" = probable. Tester run 2026-10-23 17:10-17:29 (`logs/server.log`,
`logs/traffic.log`; `logs/diag.log` of that run had only `--skills` / shop breakpoints, no `--target`).

## 1. The skill range indicator stays after a cast

### 1a. What the logs show
Cast at 17:12:22.19 (Sonic Batarang, slot 1): the client sends `0x20EA` (slot 1, events [0x10000023]) and 6 ms
later `0x20EE` (command 2, slot 1, point). We answer with the facing, scriptlets 0x10000164 / 0x100001C1, the
missile, `0x20F8` cooldown, vitals, `0x20F0` / `0x20C8` status, `0x1000015A` overlay. **No `0x20C9` is sent in the
whole run** (`grep -c 0x20c9 traffic.log` = 0) and `skill_client_events` is false, so 0x20EA is dropped.

### 1b. Who draws and who removes the indicator (C)
The range decal is owned by the HUD targeting-display object (ecx = `[0xa12d50()]->vt+4`), field `+0x60` = slot
shown (-1 none), decal handles `+0x80/+0x84/+0x88/+0x8C/+0x90`.

- Draw: **0xa39360(slot)** (reads targeting type 0x1000003D, range `0x874930`, radius `0x5897a0`, creates decals
  with `0xa33f40`). Remove: **0xa22e20** (frees the decal handles).
- Start for a slot (sets `+0x60`, ends the previous slot, draws): **0xa5dab0(slot, flag)** and **0xa6d800(slot)**.
- End for a slot: **0xa4f0c0(slot, interrupted, keepTargeting, ...)**: if `+0x60 == slot` -> 0xa22e20, `+0x60 = -1`;
  with arg 3 == 0 it also clears the HUD controller's targeting state (`+0xEC` slot, `+0xF0/+0xF8` = -1.0).
- Callers of the start/end functions: only
  - script nodes run by the **client** script VM: node **0x10000056** executes 0xab62d0 -> **0xa5dab0 (START)**;
    node **0x10000022** executes 0xab6330 -> **0xa4f0c0 (END)**, arg 2 = (current event == 0x10000009). The
    catalog / full-combat-skills.md 4.7 names them "Show/HideMinimapTargetingRing"; the names are swapped and they
    are the world range indicator, not a minimap ring.
  - S->C `0x2180` (`u8 0 | u32 slot`, exec 0x8bbdf0) -> 0xa6d800 = START; S->C `0x217F` (`u8 0 | u32 slot | u8`,
    exec 0x8bbf10) -> 0xa5d070 -> 0xa4f0c0(slot, u8, 1, 0) = END (decal only).
  - vector targeting (type 16) 0xa6d870 / 0xa1a430.
- The order path (0xa75d20 second click, 0xa70600 ground, 0xa70030 order API) clears only the HUD controller's
  targeting state `+0xEC/+0xF0/+0xF8` after sending 0x20EE; **it never calls 0xa4f0c0 / 0xa22e20**.

### 1c. The client targeting script (C)
Entering targeting, 0xa26420 calls **0xa23510(agent, slot, &0x10000023)**: sends `0x20EA` and raises the event
locally through **0xa16e60(agent, slot, event)** -> 0x96ded0(event, DID), which posts it to the script instance
with that DID in the agent's effects component (entity+0x8C). The DID is the slot's skill property **0x1000063A**
(`0x861580`; if absent and the targeting type is not 0/5/9, a default from enum 0x1000005B). Constants at
0x16016b4 = 0x10000009 (cancel), 0x16016b8 = 0x10000023 (begin).

Such a client script, e.g. **0x3400019E** (same pattern in 0x340001A3, 0x340001A8, 0x3400020B, 0x34000214,
0x34000438, 0x34000735):

    S0 -> S1 on 0x10000023 (alive)       S1 enter: LastSkillSlotUsed = event SkillSlot; node 0x10000056(slot) = START
    S1 -> S2 on 0x1000001D (skill used)  S1 exit : node 0x10000022(slot) = END
    S1 -> S0 on 0x10000023 again         any -> S0 on 0x10000009 (interrupt); S2 -> S0 after a delay

So the indicator ends when the instance leaves S1: on **0x1000001D**, on 0x10000009 (the client raises it itself
when another skill's targeting replaces this one: 0xa70030 -> 0xa171d0 / 0xa23510 with 0x10000009), or on a new
0x10000023 (another button). The client never raises 0x1000001D itself; only S->C **0x20C9** (handler 0xa1d400 ->
0xa16e60) delivers it. This matches the report exactly: the indicator stays until another button is clicked.

### 1d. 0x20C9 layout (C, serializer 0x849ce0, event 0x460d20 / 0x460da0)
`u8 0 | u64 agent IID | u32 slot | u32 event class id (1; 0 = no event) | u32 event id | u8 has-params (0)`.
The client's own 0x20EA shows the same ScriptEvent encoding: `01 00 00 00 | 23 00 00 10 | 00`. The event is
dropped if the client slot map (0x186dd8c, set by 0x10000023) says another slot for that DID.

### 1e. Server change
After `R.activate` succeeds in `World.cast` (ics/world.py ~line 957) for the local champion, send
`0x20C9(champion, slot, 0x1000001D)`; when a cast is refused (the 0x20DC path) or interrupted, send
`0x20C9(champion, slot, 0x10000009)`. Optional: the 0x20F9 on/off pair (0x100000B7 / 0x100000B6) when a slot is
disabled. Keep `skill_client_events` false for the server skill scripts (0x10000023 belongs to the client
targeting script, not to the 0x34 skill script).

## 2. Only the first enemy turret can be attacked

### 2a. Logs
Positions (create messages): turret t2 (95, 77.5) with plate 0x2E000A9F and head 0x2E000AA8 at the same spot;
dampener t2 **(120, 77.5), no plate, no head**; core turret (134.5), core (142.5). After the turret fell
(17:19:21.117) the dampener got 0x100007D9 = true and flags 0, 0x810. From 17:19:43 the player right-clicked around
(116-121, 74.7-78.2), i.e. on the dampener, and every click became a move (`move ->`), never an attack. The
dampener died to minions at 17:24:20.

So the base plates cannot be the cause for the dampener: nothing else is near (120, 77.5), and the turret t2 that
was attacked had a plate and a head on top of it.

### 2b. Hover pick and validator (C)
A right click becomes an attack only if the hover pick 0xa81b30 returns the entity, and the pick scores only what
**0x9d01d0** accepts (targeting-and-relations.md 1a/1b). Re-read 0x9d01d0 with the tag table at 0x15fe670:
check B attribute **0x10000029** must be 1 (default 1), check C **0x10000249** must be 1 (default 1), alive check
0x10000B2D must be 0. They are read by 0x974940 -> **0x973730**: the base value (unit component vt+0x60) then the
attribute modifiers (per source IID hash `+0x10/+0x1C`, per team table `+0x38`), combined by 0x96d460 (bool ops
0/5/6 set, 3 or, 8 and). The outer turret's template has 0x10000249 = 1; the dampener / core turret / core have
0x10000249 = a reference to property 0x100007D9. **That is the only template difference between the attackable
turret and the three refused structures.** Instance properties sent by 0x6 (0x10000249 = 1 at 17:10:40, and
0x100007D9 = true at unlock) evidently do not change the evaluated base (P: the reference is resolved when the
component attaches, or the base reads the template, not the instance property). The fase3-ha "diag accepts the
dampener" line was the flags step ("flags accepted"); the run did not show a dampener attack order either.

### 2c. Server changes, ranked
1. (P, high) At unlock (`Match.unlock_structures`) add attribute modifiers on the structure with op 6 (set) = true
   for 0x10000249 and 0x10000029 (`combat.add_modifier(mu.ent, attr, 6, True)` -> 0x20F0, the same channel as the
   death modifier 0x100003AB op 6). Modifiers are applied after the base in 0x973730, so this bypasses the
   template reference.
2. (C to confirm) A `tools\diag.py --target` run with a click on the dampener: the failing step of 0x9d01d0
   (check C expected).
3. (low) The plates: give 0x2E000A9F no pick (it carries no unit flags, so 0x9d01d0 rejects it and it scores 0;
   it cannot hide an attackable entity unless the render pick keeps only the nearest hit). Not the dampener cause.
