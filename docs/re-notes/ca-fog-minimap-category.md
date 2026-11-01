# Crime Alley: enemies off the minimap by note category, sight inside the lit circle (2026-10-30, fase3-is)

Tester report 2026-10-30 15:30 (build fase3-ir, Crime Alley v AI, AGL vs AI Poison Ivy, server run 16:36-17:02).
Evidence: `logs/server.log`, `logs/traffic.log` (copies worked on, not kept), the decompiled client
(`re-work/decomp`), capstone reads of `InfiniteCrisis.exe` (image base 0x400000), the Flash HUD
(`re-work/ui-as2`, `gameplay/minimap/MinimappyThing.as`), a headless replay of the match layer. Tags: **C** confirmed,
**P** probable, **G** guessed, **O** open. Builds on `ca-fog-minimap-ring.md` 3 and `fog-vision-runtime.md` 4.

## 1. Enemy minions and champion still on the minimap (item 1)

### 1.1 What the server sent (C traffic)
fase3-io's lever went out as designed. Every 0x4 to an enemy (team 2) minion or Poison Ivy carries `0x2A1` and `0x90F`
(byte patterns `a1 02 00 00 02 a1 v` / `0f 09 00 00 09 0f v`), counted over the whole log:

| Object | 0x2A1 = 0, 0x90F = 1 (hidden, off the map) | 0x2A1 = 1, 0x90F = 0 (seen) | 0x2A1 = 1, 0x90F = 1 |
|---|---|---|---|
| lane minions (melee / ranged / siege) | 3 272 | 6 599 | 1 420 (super minions `0x40000C9C` / `C9B`, hidden but kept) |
| AI: Poison Ivy (labelled bundles only) | 29 | 32 | 0 |

The minions get a full bundle (179-210 bytes) at every movement state, so 0x2A1 = 0 was re-sent about once a second.

### 1.2 Why the note stayed (C code)
- `0x2A1` is a **client-local** id (descriptor net 0, group "local"; `properties-complete.tsv`). The fog component's
  visibility evaluator **0xAAA670** (vt+0x6C, run by 0xA9F240 on every fog candidate and source at each update; every
  ics object is a candidate, top byte 2) ends with `0x5563E0(entity, 0x2A1, value)`: the value is **true** unless the
  owner (our champion) has attribute `0x100007C0` (`[0x16088DC]`), and with it true only for `0x100006F3`
  (`[0x16088D8]`) / `0x58A430` / range and line of sight. Nothing gives AGL `0x100007C0`, so the client writes 0x2A1 =
  true on every enemy each update (`fog-vision-runtime.md` 4 said so; fase3-io used it anyway).
- The map manager's property watcher **0xA6A8E0** (listener at manager+0x20, registered by the entity hook 0xA5B190
  for 0x100000FA / 0x10000B2D / 0x10000548 / 0x100004DA / 0x2A1 / 0x10000D0A / 0x10000587): `0x2A1` false ->
  **0xA4C030** (remove), true -> **0xA4BD80** (add; it reads 0x2A1 first). So each server false removed the note and
  the client's own true put it back within ~0.4 s; the dot stayed (at most a flicker).
- Note lists of the manager: +0x38 pending add (0xA4BD80 pushes there, va 0xa4bf9b), +0x48 live, +0x28 pending removal
  (0xA4C030 moves a live note there, va 0xa4c076; a note still pending add is just dropped); **0xA22A10** sends Flash
  `RecvNotice_RemoveMapNote(iid, null DID)` for every +0x28 entry (0x8B9880), which pools the clip
  (`MinimappyThing.RemoveMapNote`; a non-null DID would only re-skin it as dead). Per-frame positions go by
  `UpdateMapNotes` (0xA5BC50 -> 0xA4C430); the hidden position -65536 is used only for an entity outside the manager's
  landblock, never for fog (C).
- **0x100004DA** (minimap note category) is net 1 and nothing in the client writes it except the ping builder 0xA843E0.
  Watcher 0xA6A8E0: kind 8 / 10 and a non-zero value -> 0xA4BD80, anything else (0, a removal) -> 0xA4C030. The other
  add paths check the category: the entity hook 0xA5B190 (skips 0 and 0x1D) and the LifeState branch 0xA5C2C0 (4 ->
  only with a category). 0xA4BD80 itself does not, so a 0x2A1 change or 0x10000587 would still add a category-0 note;
  ics sends neither for these objects once it stops writing 0x2A1.

### 1.3 Fix
`[ics] fog_minimap_lever` = `"category"` (default): `World.fog` gives an enemy lane unit / champion out of sight one
`0x100004DA = 0` (kind enum) in its bundle / 0x6 and, back in sight, its template's category (`UnitData`, minions 9,
champions 2; `[ics] fog_minimap_categories` when the template has none). 0x2A1 is left to the client (the units' own
0x2A1 = 1 and the bot's default stay). Super minions (unit flags 0x400000, `fog_minimap_always_flags`) keep theirs.
`bot_properties` no longer adds its fixed `0x100004DA = 2` once the fog holds the id (no duplicate id in a bundle).
`"on_map"` = fase3-io (0x2A1 = false). `fog_hide_minimap` false = neither.

Uncertainty: P that a category change is all the note needs in game (C code path; not run). Other readers of
0x100004DA (4 entity reads) may change for a hidden enemy (P harmless: it is hidden and not targetable).

## 2. Enemy champion inside our vision not drawn until very close or it attacks (item 2)

### 2.1 What the logs show (C, limited)
The bot's movement and its fog flips go out unlabelled (not in `traffic.log`). Its 63 labelled bundles show it hidden
only when out of every source's range: e.g. 16:45:12.173 at (86.9, 75.1), 11.6 m from AGL's last known spot, but AGL had
died at 16:45:09.958 (a dead champion is no source); 16:51:37.728 at (93.7, 79.1), nearest allied minion 8.3 m (minion
vision 3 m). Ivy never entered a stealth strip (no "enters a stealth strip" line for her; AGL entered 7 times). A
headless replay (Poison Ivy bot, AGL following the minion front, 400 s) gave 1 039 shown and 6 hidden samples inside
12 m, the 6 all within one 0.4 s fog step of entering the range: in the lane the server's rule matches the circle.

### 2.2 Cause (P strong)
The lane is one open navmesh strip (y 73-82); its holes are the buildings between the lane and the jungle mouths, where
the stealth strips are. With `vision_through_blockers` (and the fase3-ip "fog occluder pass" exe patch) every allied
source draws a **full** circle on the client, but `World.fog` still required a clear navmesh line, so an enemy behind
a building corner stayed hidden inside the lit circle until it came within 3 m (the line exemption) or walked into the
line by attacking. Example (C on the navmesh): AGL at the mouth (55, 88), an enemy in the lane at (60, 81.5): 8.2 m,
line blocked -> hidden before, shown now.

### 2.3 Fix
`[ics] fog_sight_line` = `"auto"` (default): the navmesh line is needed only when `vision_through_blockers` is off
(then the client clips its circles at the occluders too); inside a source's radius an enemy is seen. Stealth strips
still hide (`Match.visible_to`). `true` = the line as before. `[ics] fog_log_champions` (true): one `fog:` line in
server.log per change of an enemy champion's state: its position, the nearest allied source, distance, radius, navmesh
line and the reason (`in range`, `out of range`, `line blocked`, `stealth strip`, no source). If the report comes back,
those lines name the moment.

O: whether the original server blocked sight at buildings (its client drew occluded circles, the occluder pass this
client blackens wrongly); minion vision stays 3 m (`match_minion_vision` "min").

## 3. Tests
`tests/test_match.py` `fog_minimap_category` (6 checks): out of sight the lane minion and the bot carry one
0x100004DA = 0 and keep 0x2A1 = 1, the super minion keeps 9; the update carries it; back in sight 9 / 2; one fog line
per champion change; 8.2 m behind a corner shown with "auto", hidden with `true` or without vision_through_blockers;
the "on_map" lever as fase3-io. `fog_minimap_ring` runs its 0x2A1 checks with `fog_minimap_lever = "on_map"`.

## 4. Tester should see
1. Enemy lane minions and the enemy champion on the minimap only while one of ours sees them; super minions always.
2. The enemy champion drawn as soon as it is inside our champion's lit circle (12 m) or 3 m from our minions, also
   around a building corner; still hidden inside a stealth strip unless we stand in it or it attacks.
