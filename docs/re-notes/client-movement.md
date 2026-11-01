# Client movement: position authority, replay of server states, order gating (static analysis, 2026-10-22)

Read-only analysis of InfiniteCrisis.exe (sha256 463adfff..., Ghidra via REA + capstone, image base 0x400000; all
addresses are VA). C = confirmed in decompiled code, P = probable (strong inference), O = open.
Builds on `movement-collision-fog-map.md` 1.1-1.3 (0xB0 block layout, movement-mode table 0x48000002, module
classes) and `targeting-and-relations.md` 1 (right click -> 0xA86A00 -> 0xA70030 -> 0x88B030).

---------------------------------------------------------------------------------------------------------------

## 0. Summary

- **The server is fully authoritative for every networked character, the local champion included** (C). With the
  wire movement mode 1 and no controller IID (what `ics` sends) the champion gets the *remote* module key 1
  (vtable 0x15C6360, "ClientRigidBodyCharacterReplayMovementModule"). There is **no client-side prediction**: the
  order path (0xA70030) only snaps the click to the navmesh, shows the click marker and sends 0x20EE; it never
  touches the champion's frame (C).
- Each 0xB0 movement block becomes one **timestamped state** `{time, seq bytes, Position, orientation, velocity}`
  pushed into a 9-entry history (C). Every physics tick the client takes the **newest state whose time <= now -
  0.1 s** and **dead-reckons** it: `pos = state.pos + velocity * (t - state.time)` (C, 0x552130). There is no
  interpolation between two states and no path/destination field: velocity = heading/speed from the motion bytes.
- The rigid body is then steered to that point: error <= 2 m -> smooth velocity correction; > 2 m, or a newer
  "teleport" sequence byte -> hard snap with velocity reset (C, 0x60B5F0).
- The run animation is driven by the replayed velocity (anim graph variables 0x501 / 0x300 / 0x1F1) (C).
- **Stopping** needs an explicit state with speed 0: fields absent from an update keep their old value, so an
  update without the speed field keeps the unit sliding (C, 0x57DA90).
- Client order gating: all orders need LifeState 4 and bool 0x10000B2D clear (unless the skill has 0x10000B4D);
  skill/attack orders are *buffered* (not sent) while bool **0x100003F3 (stunned)** is set or the movement mode is
  one of 0x40/0x41/0x47/0x48/0x4A/0x4B/0x4D/0x4E/0x4F; **move orders are not blocked by stun** (C) -> the server
  must ignore them itself.

---------------------------------------------------------------------------------------------------------------

## 1. Position authority for the local champion

### 1.1 Module choice (C, recap + new)
- 0x553E70 (from the 0xB0 listeners 0x60AED0 create / 0x60AFA0 update) picks the row of record 0x48000002 for the
  wire mode; 0x608D20: controller IID (C+0x2C8) == local player id -> local controller + local module, else no
  controller + remote module (row 0x4C). `ics` sends `0x62 | seq | 1 | 0x0F` (bit 0 clear: no IID) -> remote module 1.
- Component C vtables: 0x15C5F80 and 0x15C6180 (two variants; identical except +0x10/+0x14/+0x38/+0x7C). Slots used
  below: +0x58 = 0x608FC0 (mode change), +0x60 = **0x609240 (sampler)**, +0x4C = 0x608D20 (is-local test).
- Module key 1 vtable 0x15C6360: +0x58 = 0x608CE0 (-> its own +0x68), +0x68 = **0x60BB00** (per update), event
  handler 0x60B5F0 (event 0xE = physics step).

### 1.2 What a 0xB0 update does (C)
Path: event 0x4 batch sub-item 0xB0, or (P) a standalone event 0xB0 to the object (handler 0x6298D0 calls every
listener at obj+0x60 with the payload; the same listeners 0x60AED0 / 0x60AFA0 receive it).
1. 0x57E530 reads the block (layout in `movement-collision-fog-map.md` 1.1). Field offsets in the block object:
   +0x20 f64 time (subflag 1), +0x28 Position object (subflag 8; else subflag 2 = z only, 4 = x,y), +0x5A u16
   time offset (always present), motion bytes (leading-byte flag 0x02): bit 1 -> +0x5C/+0x5E s16 dx,dy; 2 -> +0x60
   s16 dz (all /1024 m, added to the position); 4 -> +0x44 f32 **heading** (rad); 0x20 -> +0x48 f32 **speed** (m/s);
   0x40 -> +0x4C f32 pitch; 8 -> +0x54 s16 **facing yaw** (rad*10000); 0x400 -> +0x56 s16 facing pitch; 0x4000 ->
   +0x58 s16 roll; 0x800 -> +0x62 u8 **seq A**; 0x1000 -> +0x63 u8 **seq B**; 0x2000 -> +0x53 u8 **seq C**.
2. 0x60AFA0 (only after the create listener ran: C+0x308 set) -> 0x57DA90 merges the new block into the stored
   one **field by field: only the flags present overwrite** (C). Then:
   - if bits 4|0x20|0x40 present: velocity = (cos h * speed * cos p, sin h * speed * cos p, sin p * speed) (C);
   - facing: bit 8 -> given yaw; else bit 0x200 -> yaw = heading; pitch/roll likewise; 0xAF2D00 builds the
     orientation quaternion from (yaw, pitch, roll) * 0.0001 (C).
3. 0x57DD70 builds the state (0x48 bytes): `time = f64 time + u16/1024`, seq A, seq B, seq C, Position (+ s16
   offsets), orientation, velocity (C).
4. 0x609C70 -> 0x5525A0 pushes it into the history (component +0x30 start, +0x38 count, +0x40 entries, 9 x 0x48)
   (C): **a state older than the newest is dropped**; equal time replaces the newest; a state equal to the newest
   (same seqs, position within 0.05 m, same non-zero velocity, or both at rest) is dropped as a duplicate.
5. 0x60BB00 (module +0x68): if seq C is newer than entity+0x100 (u8 wrap compare 0x60A040): 0x635300 -> **0x551CB0
   clears the whole history** and re-places the entity (0x588330(ent, 5)); for the local player object it also
   calls 0x7D1C60 (P: teleport/zone-change wait state). Note: this runs *after* step 4, so the state just pushed is
   cleared too (C order; effect O). Do not use seq C for ordinary teleports.

### 1.3 Replay every physics step (C)
- 0x60B5F0 (event 0xE, "ClientRigidBodyCharacterReplayMovementModule"): t = clock(0xE) - **0.1 s** (float at
  0x1862938, blended by 0x633380 between 0x186293C and 0x1862940, both 0.1); 0x609A50 -> sampler 0x609240:
  - entity flags +0x118 & 0x40 and not & 8 -> no replay (P: attached/scripted);
  - else **0x552130**: newest history state with time <= t; `pos += velocity * (t - time)` if |v| > 0.0002; no
    state <= t -> the entity's current frame.
- Seq A / seq B of the sampled state compared with component +0x20 / +0x21 (0x609AF0, u8 wrap compare): newer seq
  A also stamps entity+0x110, seq B entity+0x114.
- If neither seq is newer **and** |target - current|^2 <= 4.0 (2 m): 0x5C9FE0 sets the rigid body velocity toward
  the target, 0x60A270(state, .., 0) sets the frame/orientation (vt+0x58(frame, 5)), 0x6097E0 feeds the anim graph.
- Otherwise (a newer seq A/B, or > 2 m): 0x5C9E90 snap + 0x60A270(state, .., 1) which also **zeroes the body's
  velocity** (piVar[0x43..0x45]) = teleport.
- 0x6097E0: velocity in the entity's local frame -> anim graph variables **0x501** (forward) and **0x300** (side)
  (clamped to the movement component's +0x2D0 max speed) and **0x1F1** (turn, yaw rate * -1/180, clamped -1..1)
  (C: ids read at 0x15C5D7C / 0x15C5D78 / 0x15C5D74). So "walking" = non-zero replayed velocity.

### 1.4 Consequences for the server (C unless marked)
- Clock: the f64 time must be in the client's game clock (the one the time packet syncs). A state time behind the
  client clock by D renders a moving unit D * speed *ahead* of the truth; ahead -> it waits (shows the older state).
- **Stop / knockdown / root**: send one update with the current position, speed 0 (bit 0x20 with 0.0; keep heading
  so velocity is recomputed) and the facing. Afterwards no further updates are needed. Do not send states with
  speed > 0 while down; ignore 0x20EE moves server-side (section 3).
- **Teleport**: new Position + speed 0 + **seq A (0x800 byte) incremented** (u8, wrap ok) -> hard snap, velocity
  zeroed. A jump > 2 m snaps anyway, but the seq makes it explicit. `ics` sends seq A = 1 forever today
  (`tele_seq=1`): keep a per-entity counter. Leave seq C alone (history flush, local-player side effects).
- Seq B (0x1000 byte, `second_seq`): newer value also snaps; the old server's rule (0 until load complete, then 1)
  stays; do not change it during play.
- Never send a time older than the previous update for that entity (dropped). Equal time = replace.
- The champion with mode 1 is replayed exactly like any NPC; there is nothing to "correct": the client shows only
  what the server sends, 0.1 s late.

---------------------------------------------------------------------------------------------------------------

## 2. Moving other units smoothly; facing

- There is no path / destination / speed-only movement message (C, recap): one state per straight segment is
  enough because the client extrapolates linearly from the last state.
- **Best message**: the 0xB0 block alone. Today `ics` re-sends the whole 0x4 bundle (0xF2 + 0xB0 + 0xBC) every tick;
  a 0x4 batch with only the 0xB0 sub-item, or event 0xB0 sent directly to the object id with the same payload, goes
  to the same listener 0x60AFA0 (P strong: 0x6298D0 dispatches to obj+0x60 listeners; the create listener must have
  run first, C+0x308). Test it before dropping the full bundle.
- Recipe for a path (human fleeing):
  1. At each corner k (time t_k, position p_k): send `time=t_k, Position=p_k, heading=atan2(dir), speed=v,
     facing=heading` (bits 4, 0x20, 8). Between corners send nothing (or a refresh every ~1 s for error control;
     redundant states are dropped as duplicates).
  2. At the end: `time=t_end, Position=end, speed=0, facing=final`.
  3. Optionally the whole path at once: states with **future** times are kept (history 9 deep) and each takes
     effect when the client clock reaches it (C: the sampler skips states newer than t). Up to 9 corners per send;
     a later state with an older time than the newest is dropped, so a path change must use times >= the newest
     queued one (P: simplest is to send corners only as they are reached).
  - Error > 2 m from the replayed point causes a snap: keep server and client positions consistent (same speed, same
    corner times).
- **Facing a target** without moving: speed 0 and facing yaw = atan2(target - unit) (bit 8, s16 = yaw * 10000,
  i.e. +-3.1416 rad fits in s16); or send heading with bit 0x200 (yaw = heading). `ics` already writes facing from
  `facing_yaw(heading + facing_offset)`.
- Units placed with mode 0x41 / 0x4C (remote module 9, 0x60B0F0 -> SetEntityFrame) are set directly without
  physics (recap of 1.2 in the older note; P: usable for props/rigid placement, not for walkers).

---------------------------------------------------------------------------------------------------------------

## 3. Client-side gating of orders (what the server must set)

Order API 0xA70030(champ, cmd, ability, &target, pos...) (C):
1. `0x8619B0(champ, ability)` = skill bool **0x10000B4D** (usable while dead). If not set: **0x9CFAF0** must pass:
   life component (0xAA05A0) +0x34 == 0 and +0x2C (LifeState **0x100000FA**) == 4, and bool **0x10000B2D** not set
   (0x974940 -> 0x973730 single-property check). Fails -> no order at all.
2. Input controller +0xCC != 0 -> no order (O: probably a UI/cinematic lock).
3. Moves (cmd 3/4) and attacks (2/9, if 0x861850 = skill bool 0x10000708): the point is snapped onto the navmesh
   (0x4FB400, radius 2.5 = 0x40200000); off-mesh -> dropped (C). For moves with a marker object (+0x100) the click
   marker is placed (0x588290) and effect 0x1000005C (move) / 0x10000F52 (attack-move) played (C).
4. **0x8686C0** (buffer at controller+0x48) re-checks 0x9CFAF0, then:
   - cmd 2/9 (skill/attack): **0x863860** returns "hold" when the skill is in the controller's disabled list
     (+0x60/+0x68 pairs), or 0xA235F0(.., 0x1000006C), or bool **0x100003F3 (stunned)** is set, or the champion's
     movement mode (C+0x2C via 0x550120) is **0x40, 0x41, 0x47, 0x48, 0x4A, 0x4B, 0x4D, 0x4E, 0x4F**, or +0x70 of
     its object != 0 (O). Held orders are stored and retried every frame by gmClientInputSystem 0xA8B0B0, so they
     fire as soon as the condition clears (C).
   - cmd 3/4 (move): held only while buffer +0x70/+0x74 != 0 or +0x8C != -1 (until time +0x90) (O: probably the
     current cast lock). **Stun does not hold moves** (C).
   - anything else: held while +0x70 != 0.
5. Holding the mouse button re-issues the right-click order every **0.125 s** (0xA8B0B0: +0x104 / +0x108) (C) ->
   expect a stream of 0x20EE while the button is held; the server should treat a repeated move as a re-path.

What to set (recommendations):
- Knockdown / stun: set bool **0x100003F3 = 1** on the champion (skills and attacks are held client-side and fire
  when it clears) and **ignore 0x20EE move/attack orders server-side** while down (moves are still sent). Send the
  stop state of 1.4. Clear 0x100003F3 (and send nothing else) when he gets up. (P for the visual: the HUD may show a
  stun icon; status icons are separate events 0x20A2.)
- Death: LifeState 0x100000FA != 4 (or bool 0x10000B2D = 1) blocks every order client-side (C).
- Do not put the champion into movement modes 0x40.. to block input: the mode also changes the module (row table)
  and may remove the replay module (P).

---------------------------------------------------------------------------------------------------------------

## 4. Open points
- O: what writes buffer +0x70/+0x74/+0x8C (move hold) - probably the cast/channel state from the server's cast
  events; trace with `tools/diag.py` on 0x8686C0 if moves are swallowed while casting.
- O: controller +0xCC (global order lock).
- O: standalone event 0xB0 to an existing object not yet tested in the game (P strong from 0x6298D0).
- O: entity flags +0x118 (0x40 without 8 = replay off) - what sets them.
