# Grab's beam: what the type 2 action draws and why nothing shows (2026-10-28)

Sources: decompiled client (`re-work/decomp/c/00670000.c`, `00740000.c`, `00610000.c`, `00580000.c`), capstone
disassembly of `InfiniteCrisis.exe` (VA, image base 0x400000; RVA = VA - 0x400000), pack 0xA0000150 (Vfx_Active of
table 0x1D0003D2 @0x29220, missile `.entity` 0x2D000A33 @0x39B8C4), pack 0xA0000151 (AGL `.entity` 0x2D0009A9
@0x11B020), `logs/traffic.log` 09:35:13 (one Grab), `ics/world.py` / `ics/session.py` / `ics/messages.py`.
Tags: **C** confirmed (code / data / log read), **P** probable, **O** open. Follows `grab-arm-carry.md` and
`agl-visuals.md`.

## 1. Summary

- The type 2 action in the missile's Vfx_Active is **not a textured beam**: its width is 0, it has no head / tail
  caps and no stretched mesh entity. What it draws is **particle 0x18000752 emitted at random points along the line
  from the missile's attach point 0x10000039 to AGL's attach point 0x1000007C**, 70 particles per second per 5 m of
  length. That particle line is the "stretched arm" (C data + code, P that it is what the tester calls the arm).
- Both attach points exist (missile: 0x10000039, no bone; AGL: 0x1000007C on bone 29) (C). The target binding is
  right (diag: AGL's IID) and the scale mode is 4, which matches the diag's `eax=4` (C). Nothing in the beam code
  checks team or fog. There is no server parameter or 0x8D variable the beam needs beyond 0x100004E2 (C).
- The particles are emitted only from the end points that the draw pass works out, and the draw pass runs only while
  **both ends resolve every frame**. An end resolves only if its entity has a render model that is "active" (not
  hidden, not detached, ready this frame) and the attach point is found (C). So the beam fails at one of those
  per-frame checks, or the beam object is deleted before it draws (O: which one; section 5 gives the breakpoints).
- Best server-side suspects (P): (1) the **full 0x4 bundle sent to the missile on every tick** (`session.py` 1091 ->
  `w.bundle(ent)`, unlogged: `net.py` drops label None). It replaces all of the missile's properties, its 0x7D2
  tables included, and a full bundle has already been seen dropping a running scriptlet's visuals (the Shards
  sphere, fase3-ib). (2) The missile's render model is not active on the client (creation bundle with speed 0 /
  heading 0, no team). (3) The missile lives only ~0.5 s and is removed 0.25 s after the hit (section 4).

## 2. What 0x673280 does after it resolves the target (C)

Execute `0x673280` (type 2 definition vtable 0x15CF890, field serializer `0x67A980`):

1. `owner = 0x514D20()` = the entity the 0x8D ran on (the **missile**). Source IID = owner+0x100/+0x104; source
   sub-id = `[*run + 0x58]` (a destructible piece, 0 here).
2. Target = field 0x18 -> `0x51EF90(0x18)` -> `0x51D590` -> u64 IID at `ebp-0x28` (+ sub-id `ebp-0x14`). The diag's
   breakpoint at 0x67338E reads this value: AGL.
3. Scale: definition +0x15C (property 0x414): 1 -> `0x58D6B0(owner)`, 2 -> `0x58D6E0(owner)`, 3 ->
   `0x634CD0(owner)`, any other value -> 1.0. The data has **4**, so the scale is 1.0 (diag eax=4).
4. Builds a 0x15C-byte description on the stack (`local_198`) from the definition and calls `0x74AE80`. That
   allocates the beam object (0x2C0 bytes, constructor `0x749E00`), copies the description into beam+0x50
   (`0x74A620`), sets up the beam (`0x74A930`: random end jitter, particle systems, materials `0x74A160`, optional
   mesh entity) and appends it to the global beam list. The run keeps a 0x60-byte attachment (vtable 0x15CE6A0)
   whose +0x5C is the beam, and beam+0x1B0 points back to it. So **the beam lives as long as the scriptlet run**.

Description -> beam -> definition field map (C, from the copy code; property ids from `0x67A980`):

| Beam offset | Definition | Property | Meaning (C code use, P name) | Grab data |
|---|---|---|---|---|
| +0x68/+0x6C | owner IID | - | source entity | missile |
| +0x70 | `[*run+0x58]` | - | source sub-id | 0 |
| +0x78/+0x7C | field 0x18 | - | target entity | AGL (0x100004E2) |
| +0x80 | from 0x51D590 | - | target sub-id | 0 |
| +0x51 | +0x35 | 0x8F8 | keep the last target point if the target fails | 0 |
| +0x52 | +0x36 | 0x91C | lifetime mode (delete rule in 0x74A520) | 0 |
| +0xB4 | +0x84 | 0x726 | **body width** (0 = no body: 0x74BDA0 skips it) | **0.0** |
| +0xB8 | +0x88 | 0x152 | length with no target | 5.0 |
| +0xBC | +0x8C | 0xFC | segment length (caps, particle density) | 5.0 |
| +0xC0 / +0xC4 | +0x90 / +0x94 | 0x610 / 0xFB | head / tail cap counts | 0 / 0 |
| +0xC8/+0xCC/+0xD0 | +0x78/+0x7C/+0x80 | 0x153 / 0x611 / 0x39 | materials (DB type 0x2C) | defaults 0x17000001/3/0 |
| +0xDC/+0xE0/+0xE4 | +0x9C/+0xA0/+0xA4 | 0x315 / 0x66F / 0xFA | head start / delay / speed (m/s) | 0 / 0 / **200** |
| +0xE8/+0xEC/+0xF0 | +0xA8/+0xAC/+0xB0 | 0x4C2 / 0xF9 / 0x372 | tail start / delay / speed | 0 / 1.0 / 0 |
| +0x100 / +0x104 | +0xC0 / +0xC4 | 0x204 (enum 0x30000028) / 0x60F (enum 0x3000002A) | source attach point / bone | **0x10000039** / 0 |
| +0x108 | +0xC8 | 0x38 | source offset | 0,0,0 |
| +0x118 / +0x11C | +0xD8 / +0xDC | 0x564 / 0x4C1 | target attach point / bone | **0x1000007C** / 0 |
| +0x120 | +0xE0 | 0x513 | target offset | 0,0,0 |
| +0x12D | +0xED | 0x416 | (lifetime gate in 0x74C8E0 with state 3/4) | 0 |
| +0x130 / +0x134 | +0xF0 / +0xF4 | 0xF8 / 0x66D | head / tail end times | 0 / 0 (none) |
| +0x140 / +0x144 | +0x100 / +0x104 | 0x512 / 0x415 | particle along the line / at the head | **0x18000752** / 0 |
| +0x148 / +0x14C | +0x108 / +0x10C | 0x781 / 0x2BF | their emission rates | **70** / 10 |
| +0x198 | +0x158 | 0x2BE | stretched mesh entity (world state) | **0** (none) |
| (scale) | +0x15C | 0x414 | scale mode | 4 |

The words of Vfx_Active (pack 0xA0000150 @0x29298, type 2 = `2`, then one word per field in serializer order:
`0 0 0 | ffffffff | 0 | 0 | 17000001 17000003 17000000 | 0 5.0 5.0 0 0 1.5 0 0 200 0 1.0 0 0 0.75 0 | 10000039 0 |
0 0 0 | 0 | 1000007c 0 | 0 0 0 | 0 0 | 0 0 0 0 | 18000752 0 | 46 a | ... | 0 (0x2BE) 4 (0x414)`). The 0x414 = 4
alignment check matches the diag (C).

## 3. Per-frame update: what can stop it (C)

`0x74C8E0` (beam list update, each frame), for each beam:

1. `0x749960(src_on, dst_on)` resolves both ends with `0x749800`:
   - `[0x1B67258]->vt+0x58(IID)` = entity by IID. **No entity -> fail.** (VA 0x74981B)
   - sub-id 0: `render = entity+0x14` (component slot 5, always created), `model = render+0xA0`. **No model
     instance -> fail.** (0x749845)
   - beam+0x2B4 = model+0x1F4 (scene) the first time.
   - `0x747DD0(model)` "active": `(model+0x220 & 0x8000) == 0`, `model+0x228 != [0x1864A84]`,
     `byte model[0x29 + [0x1864A88]*0x28] != 0`, `(model+0x220 & 0x800) == 0`. It is the same test the scene uses to
     build its draw list (`0x755FD0`). **Not active -> fail** (the 8th argument is 0, so there is no fallback).
   - `0x61E710 -> 0x61E0B0(bone, attach, offset)`: needs the model setup (`model+4`, its +0x18 != 0, `model+0x10`);
     attach id != 0 -> `0x581850` (hash at setup+0x90); **not found -> fail**; a bone index != -1 uses the skeleton
     pose (`0x556C30`), -1 uses the attach point's own transform (the missile's case).
   - The source end -> beam+0x1D8 (+ jitter +0x264), the target end -> beam+0x1E4 (+0x270). A failed target with
     beam+0x51 set would reuse the last point (0x8F8 = 0 here: no).
   - Result stored at beam+0x1FC (source ok) / +0x1FD (target ok) (0x749D22 / 0x749D28).
2. Draw only if both are ok, beam+0x1C4 is set, beam+0x2B4 != 0 and **== [0x1864A80]** (the current scene),
   `0x7582E0(scene)` (scene in the active list), length <= 1000 m, tail fraction <= head fraction, and the end points
   are valid (`0x47B630` / `0x409760`). Then `0x74BDA0` (VA 0x74CC05). Any failure -> beam+0x2B8 += 1 (0x74CC0C).
3. `0x74BDA0` writes the drawn end points beam+0x280 (tail) / +0x28C (head) = lerp(src, dst, fraction). With width 0
   and no caps it then returns without geometry (C).
4. Particles: `0x74A520 -> 0x74A0C0 -> 0x7480A0`. If length(+0x280 -> +0x28C) > 0.1 m, beam+0x44 == 0 and
   beam+0x40 > 0: spawn round(rate * dt * length / +0xBC) particles of +0x298 (0x18000752) at random points on the
   segment (`0x7423F0`), and the +0x29C particle at the head. Since +0x280 / +0x28C are only written in step 3,
   **no draw pass = no particles** (C).
5. Deletion (`0x74A520`): a beam with no live particles is deleted when `0x7AA6B0()` says its effect finished
   (+0x52 == 0) (P: the scriptlet run released it).

Head growth: 200 m/s, so a 7 m beam reaches full length in 0.035 s; the tail stays at 0 (speed 0), no end times.
Nothing here depends on the missile's velocity: the ends are read from the render transforms every frame (C).

## 4. What the server sends (C, traffic 09:35:13)

| t | message |
|---|---|
| 13.041 | AGL graph event + Grab_Start 0x10000899 + Grab_Active 0x1000089A |
| 13.064 | missile 0x40000485 created (0x4, 134 bytes): module (1,1), position at AGL + 1 m z, **heading 0.0, speed 0.0**, 0xBC = {0x100004E2 = AGL, 0x7D2 = [0x1D000456, 0x1D0003D2]}; no team property |
| 13.069 | missile Vfx_Active 0x100000EB (0x8D) -> the type 2 group starts at +0.1 s (~13.17) |
| every tick | **full 0x4 bundle of the missile** (`session.py` 1091-1103: not a bot, so `w.bundle(ent)`; label None, so not in traffic.log) |
| 13.314 | missile Vfx_OnCollision 0x10000016 (hit) |
| 13.338 | missile Vfx_Event1 0x10000076 |
| 13.591 | missile removed (0x3): the run, and the beam with it, ends |
| 13.729 | AGL Grab_Stop 0x10000890 (hand construct back) |

So the beam can exist for ~0.42 s at most (13.17-13.59). The missile is moved on the client only by the per-tick
bundles; the client does not fly it by itself (the creation has no velocity and no destination; `ObjectMissile` sets
`ent.dest` / `follow` on the server only) (C).

## 5. Which check fails: diag breakpoints (to run, O)

All RVAs (VA - 0x400000), `esi` = beam in 0x749960, `edi` = beam in 0x749800:

| RVA | Read | Means |
|---|---|---|
| 0x3499EA | `al`, `[esi+0x68]` (u64 source IID) | source end ok? (missile) |
| 0x349C07 | `al`, `[esi+0x78]` (u64 target IID) | target end ok? (AGL) |
| 0x34981B | `eax` (0 = no entity), `[ebp+8]` IID | entity lookup |
| 0x349845 | `ecx` (0 = no render model) | render model of that entity |
| 0x349865 | `al` (0 = model not active), `[ecx+0x220]` flags | hidden 0x800 / 0x8000 vs not ready |
| 0x34989E / 0x3498C1 | `al` | attach point found |
| 0x34CA3C | `eax` vs `[0x1864A80]` | scene match |
| 0x34CC05 | (hit = drawn) | draw pass reached |
| 0x34CC0C | `[esi+0x2B8]` | per-frame failure count |

Expected reading: if 0x34CC05 is hit and particles still do not show -> particle 0x18000752 (O: is the record loaded;
emitter needs `[[+0x298]+4]+0xF0` and `**([..]+0xE8)` non-zero). If the source fails at 0x349845 / 0x349865 -> the
missile's render model (P suspects 1-2 in section 1). If no beam is updated at all after the first frame -> the beam
was deleted (the per-tick bundle or the 0x3).

## 6. Server recipe (no code changed here)

1. **No per-tick full bundles for a missile object** (P, most likely cause): after the creation bundle, send the
   missile only what changes its course (return leg, retarget) and its removal. Put the velocity in the creation
   bundle (heading towards the target and `speed = move_speed`, not 0 / 0) so the client dead-reckons it. If a
   per-tick position is needed, try the motion-only form (0x4 with just 0xB0) for missiles. Key:
   `[ics] missile_tick_bundles = false` (2026-10-28, report 09:35: the beam action starts but never draws; a full
   bundle replaces the 0x7D2 tables and dropped the Shards sphere the same day).
2. Vfx_Active in the creation tick (no 0.1 s step, `spawned_effect_delays = {"Vfx_Active": 0}`), as in
   grab-arm-carry.md 1.4 (3).
3. Keep the missile alive out and back (grab-arm-carry.md 1.4 (1)): the beam ends when the missile goes (0x3);
   remove the missile only after Grab_Stop, when it is back at AGL.
4. Give the missile its team (the owner's team property, as champions get it) so nothing treats it as an unknown
   object (P, harmless).
5. If 1-4 do not show the arm: run the section 5 breakpoints for one Grab and act on the failing check.
