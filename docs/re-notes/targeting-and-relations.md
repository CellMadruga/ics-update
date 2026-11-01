# Targeting, team relation and team colour (client exe, static analysis 2026-10-21)

Exe `InfiniteCrisis.exe` sha256 `463adfff...`, Ghidra, image base 0x400000. All addresses are **VA**
(rva = VA - 0x400000; .text file offset = VA - 0x400C00). "C" = confirmed (read in the code), "P" = probable.
Note: the order builder named "0x670030 / 0x48B030" in older notes is rva; the VAs are `0xa70030` / `0x88b030`.

Problem: tester 2026-10-21 (`ics`): drones class 0x40000C72 / world state 0x2E001167, sent with PVP_Team
0x1000009C = 2 and LifeState 0x100000FA = 4, cannot be targeted (right click -> 0x20EE command 4) and look
purple instead of red.

## 1. Right click -> order (who decides "attack" vs "move")

Call chain (C):

    0xa8a270  input handler (action 0x37) -> 0xa8a140(champ, 0, p3, p4)
    0xa8a140  -> cmd = 0xa86a00(champ, &targetIID, &pos, 0, p3, p4) -> 0xa70030(champ, cmd, ...) -> 0x88b030 sends 0x20EE
    0xa86a00  (the decision):
        target = 0xa81b30(champ, 0, 1)            entity under the cursor (hover pick), IID at +0x100
        if p5 && 0x9d0490(champ, target)==0        -> "interact" (cmd 1, 0x96fdf0)
        if p6 && !byte[this+0x110] && 0x9d01d0(champ, target, slot 0, 0, 0)
                                                   -> cmd 2 (or 9 with attack-move byte [this+0x113])
        else                                       -> cmd 3 / 4 = move to the ground point
    0xa8b630  (another binding) calls 0xa8a140(champ, 0, 1, 1).

So a right click on an entity becomes an attack order only if (a) the hover pick returns it and (b) the attack
validator **0x9d01d0** accepts it for the basic attack (slot 0). Our drones fail one of them.

### 1a. Hover pick 0xa81b30 (C)
- Physics/render pick around the cursor ray (0x75d150 with filter 0xa0e120: render object type +0x218 == 2
  (entity at +0x260) or 0x200, flags +0x220 & 0x8000 / 0x800 clear, current view layer visible, +0x210 > 0.0002).
- Per candidate: entity property 0x100004A4 (kind 0x13), if present, must be a subset of the pick mask.
- Score 0xa16a60(champ, ent, ...): bool 0x2A1 (default true) must not be 0; if 0x9d01d0(champ, ent, 0, 0, 1)
  accepts it: 15 (+2 enemy, +1 neutral, +4 if unit flag 0x8 and enemy) + 0x100001C3 * 0.1. Otherwise only
  "interact" (0x9d0490, needs 0x1000034C) or bool 0x10000AA7 + bool 0x100006C2 give a tiny score; else 0 =
  not hovered. => an entity that 0x9d01d0 rejects and that is not interactable is **not even hovered**.

### 1b. Attack validator 0x9d01d0(caster, target, slot, rangeCheck, skipCasterAlive) (C)
Skill properties are read from the caster's slot collection (table 0x15eda28: slot 0 = 0x100008E3, 1 = 0x100008E8,
...), via 0x85ee30. Steps, in order (each failure returns 0):
1. relation mask = skill 0x10000448 (kind 0x13, **default 3** = neutral|enemy) & relation(caster, target) (0x854a90).
2. caster == target and skill bool ... (0x8619d0) -> reject self.
3. 0x85d420: the caster must have the slot collection (0x100008E3 for slot 0).
4. if skill 0x10000D30 & relation: caster 0x10000593 checked by 0x85fb90.
5. if skill bool 0x10000D32: status-tag check 0x974940 (set 0x15fe680).
6. relation != 4: component [target+0x88] vtbl+0x5c(caster, 1) must accept (P: visibility / fog-of-war).
7. !skipCasterAlive: caster alive (0x9cfaf0: life component 0xaa05a0 +0x2c == 4) and not tagged (0x15fe67c).
8. **unit flags** of the target: `[target+0x84] ? [[target+0x84]+0xa4] : property 0x1000019D (kind 0x13)`.
   0x8618c0: reject if flags & skill 0x100007A6 (default **0x80000**); accept only if flags & skill 0x1000068D
   (default **0x555959** for slot 0 / -1, **0x450109** for other slots; assembly 0x85f97c / 0x85f986).
   **Flags 0 => always rejected.**
9. status-tag check (set 0x15fe670); then skill bool 0x100007A7, or else the target needs **bool 0x10000AA7** (kind 0x16).
10. if not (target flags & 0x82 and skill 0x1000068D & 0x82) (always true for the default slot-0 mask):
    unless 0x100007A7: target **0x100001C3** (kind 0x08/0x0A) must be non-zero + status check (0x15fe674);
    then the **target must be alive** (0x9cfaf0: LifeState component == 4, not tagged 0x15fe67c).
11. optional range check (rangeCheck != 0): distance <= skill range (0x874930) + both radii (0x5897a0).

Gaslight Batman's basic attack (collection 0x100008E3 in record 0x48000615) has none of 0x10000448, 0x1000068D,
0x100007A6, 0x100007A7, so the defaults apply (C: read in the pack). The target therefore needs:
relation 1 or 2, **unit flags with a bit of 0x555959 and none of 0x80000**, **0x10000AA7 = 1**,
**0x100001C3 != 0**, LifeState 4.

### 1c. What the client knows about a drone (data, C)
The server-side entity templates (0x49xxxxxx, pack 0xA0000257) carry exactly these values:

| | 0x49000A5C (generic Soldier Drone, targetable 2026-10-13) | 0x49000C72 (tutorial variant, not targetable) |
|---|---|---|
| 0x1000019D unit flags | `8` (+0xcc) and `0x10000` (+0x2f8) | `0x10000` only |
| 0x10000AA7 | 1 | 1 |
| 0x100001C3 | 0x1E | 0x1E |
| 0x1000034C | 0x1E | 0x1E |
| 0x10000CF0 (colour override) | 1 | absent |

The client's own data for the drone (world state 0x2E001167 -> entity 0x2D00068A, class record 0x40000C72 ->
0x48000168) contains none of 0x1000019D / 0x10000AA7 / 0x100001C3 (C). 0x2E001167 differs from 0x2E000808
(the world state the client used for 0x40000A5C) only by the extra scriptlet tables 0x1D000770 (cinematic) and
0x1D000385 (team colour). P: the original server pushed the template's targeting properties as instance
properties; the old server proved this works for the crater (`CRATER_PROPS`: 0x10000AA7 = 1, 0x1000019D = 0x2000
made it a Super Strength target). Our `creature_properties` sends only PVP_Team and LifeState.

**Why our drones fail (P, strongest reading):** unit flags / 0x10000AA7 / 0x100001C3 are not on the client
object (or the unit component's cached copy `[ent+0x84]+0xa4` stays 0), so step 8 (or 9/10) rejects the drone,
the hover score is 0 and the right click falls through to a move. Static analysis cannot tell which of the
two drone classes' template values the client applies (the 0x10000 bit alone would pass step 8 with the
default mask); a diag run settles it (section 5).

## 2. Relationship (C)

    team(ent)   0x854050: comp = [ent+0x84] (unit component, 0xaa0dc0)
                  comp ? [comp+0x4c] : property 0x1000009C via the generic reader 0x61c990 (kind 0x10, int)
                  if -1: same lookup on the owner/parent 0x8631a0(ent)
    relation(a,b) 0x854a90: a == b -> 4; teams ta, tb (0x854050); both != -1: equal -> 4 (ally),
                  either 0 -> 1 (neutral); otherwise (including an unknown team -1) -> 2 (enemy)
    relation(ta,tb) 0x853380: same rule on two team numbers

- Unit component: constructor 0x979170 (derived 0xaafd50, vtable 0x1609b78). It caches properties with
  watchers registered on attach (0x977490 / 0xaaa5c0 -> 0x58ba40(ent, id, watcher, notify=1)):
  +0x40 PVP_Team 0x1000009C -> value +0x4c (initial -1), +0x58 0x10000715 (iid), +0x80 0x10000133 (f32 pair,
  attack range used by 0x9cfc40 / 0x9cfca0), +0x98 **0x1000019D -> +0xa4**, +0xb0 0x1000063E. The watcher
  callbacks (0x978bd0 / 0x978c00) store the value only for kind 0x10 (team) and update on every change.
- Property lookup 0x58b320: the property definition (0x4fee60(id), byte +0x12) selects the container:
  4 -> `[ent+0x38]` vtbl+0x4c, 3 -> `[[ent+0x40]+8]` vtbl+0x2c, 8 -> `[ent+0x3c]`, 7 -> a computed provider.
  **0x588820** (the minimap note reader) calls `[ent+0x38]` vtbl+0x58 directly, i.e. it only sees container-4
  properties; PVP_Team lives in another container, hence "not found" there (fase3-cf). 0x61c990 is the right reader.
- **LOCAL team** for colours: 0xa7b0d0 uses `0x854050(0x6351d0())`, where 0x6351d0 = object of the IID held at
  0x1b6a710/0x1b6a714 (0x635200 / 0x634e30 = "is the local player"); in view-match/spectator (0xabee50:
  [[0x1b77138]+0xac]) the local team is forced to 1. So the local team is the **PVP_Team of the local player
  object** (the server already sends 1 on 0x0200000000000001). [[0x1777068]+0xbc] (match object) is used by the
  minimap notes only; no code path for targeting or colour reads it (P: filled by a match/encounter message
  that `ics` does not send; not needed here).
- Targeting uses the **champion** as caster (0x9d01d0 relation champion <-> target), colours use the **local
  player**. Both are team 1 on our server.
- No server message sets the relation directly (C for this path): it is always derived from PVP_Team.

## 3. Team colour (C)

- HUD/world-UI manager, vtable around 0x1602a10: on entity add **0xa5a7e0** registers a listener for
  0x1000009C on the entity with notify = 1 (also 0x1000065C/D if bool 0x10000554, 0x10000556 if unit flag 0x1000,
  0x100002B7 if unit flags & 0x110008). On remove 0xa80a70 / 0xa69080 unregister.
- Listener callback **0xa813f0**: property 0x1000009C changed -> **0xa7b0d0(ent)**:
  - relation = 0x853380(team(ent), localTeam) -> stored as entity property 0x10000425 and scriptlet variable
    0x100004A8 (kind 0x13);
  - colour: if team(ent) in 0..2: entity 0x10000CF0 if non-zero, else 0xa95ab0(team, localTeam): with the
    relative-colour option byte 0x186de9c (default 1) and not spectating -> 0x8533c0(relation): ally 4 -> 3,
    enemy 2 -> **5**, neutral 1 -> 6; else absolute 0x853450(team): 0 -> 6, 1 -> 3, 2 -> 5. Team -1 or >= 3 ->
    colour 0. Stored as entity property 0x100007A2 and scriptlet variable 0x100007A9;
  - runs scriptlet **0x100003A6 `_Entity_OnSetClientRelationship`** on the entity (0x588a80 / 0x588a00), which
    the drone's table 0x1D000385 handles (with Vfx_TeamColor_SetNull 0x10000B0D, Vfx_TeamColor_SetContention
    0x100008C4).
- So the colour is client-computed and is (re)applied whenever PVP_Team **changes** on the entity (and once at
  listener registration if the property is already there). P: purple = colour 6 (neutral) or the material's
  default when the scriptlet never ran; red = 5. A drone with team 2 vs local team 1 gives 5 in both modes.
  The cinematic 0x35000028 playing `_Entity_OnSetClientRelationship` by hand fits: the scriptlet only runs from
  this listener.

## 4. What the server should send

To each drone (create message 0x4, property table 0xBC; kinds per catalog):

| property | kind | value | why |
|---|---|---|---|
| 0x1000009C PVP_Team | 0x10 int | 2 | relation 2 (enemy), colour 5 |
| 0x100000FA LifeState | enum | 4 | step 10 alive check |
| **0x1000019D** unit flags | 0x13 | **0x10008** (A5C template: 8 \| 0x10000) | step 8; 0 always fails |
| **0x10000AA7** | 0x16 bool | **1** | step 9 (basic attack has no 0x100007A7) |
| **0x100001C3** | 0x08 enum | **0x1E** | step 10 + hover score |
| 0x1000034C | 0x08 enum | 0x1E | interact/hover fallback (template value) |

Then, once the local player and the drone exist, **re-send PVP_Team (and 0x1000019D) as a property change**
(same mechanism as `player_late_properties`): the HUD listener (0xa813f0 -> 0xa7b0d0) and the unit component
watchers react to changes, so the colour scriptlet runs with the final teams even if the first notify happened
before the local player had its team (P).

Thugs (neutral): PVP_Team **0** -> relation 1, colour 6. Note the basic attack's default relation mask 3 includes
neutral, so a thug with unit flags + 0x10000AA7 + 0x100001C3 would also be attackable; to keep them
non-targetable do not send those three (flags 0 rejects them at step 8, and they get no hover score).

Order: create (with the table above) -> after the champion/player link -> property update with PVP_Team.

## 5. Diag to confirm (tools/diag.py breakpoints)

- return of **0x9d01d0** (eax; called from 0xa86a00 and from the hover score 0xa16a60) with args [esp+4] caster, [esp+8] target, [esp+0xc] slot.
- return of **0xa81b30** (hovered entity) on right click.
- for the drone pointer: `[ent+0x84]` (unit component), `[[ent+0x84]+0x4c]` (team), `[[ent+0x84]+0xa4]` (flags);
  return of 0x854050(drone) and 0x854050(0x6351d0()).
- 0xa7b0d0 hit count per drone (colour scriptlet ran or not) and the colour it computed (local_8 before
  0x54fc60(ent, 0x100007A2, ...)).

## 6. Exe patch fallback (not applied)

Only if the cached component value is the problem (team or flags not filled although sent):
- Team from the property, not the component cache: VA **0x85406e** (file 0x45346E) `74 08` (jz 0x854078) ->
  `EB 08` (jmp 0x854078): 0x854050 always reads 0x1000009C with 0x61c990. (Context bytes at 0x85406c:
  `85 C0 74 08 8B 58 4C 89`.)
- Flags: 0x9d01d0 and 0x9d0180 read `[comp+0xa4]` when the component exists; the analogous change is to take
  their `iVar5 == 0` branch (property 0x1000019D via 0x58d2d0). Bytes not prepared; the server-side fix comes first.
