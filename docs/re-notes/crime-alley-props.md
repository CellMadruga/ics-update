# Crime Alley props: liftable meteorites and vehicles, tower floors, turret warning ring (2026-10-25)

Source: the tester's 20 screenshots of original-game videos (`crime_alley_map_video.mp4` = images 1-9, the 2v2
recording with Katana "Nap" = images 10-20; not in the repo), the packs of the player's install (throw-away scripts in
the session scratchpad, nothing copied), `ics.script_model` dumps of the server scripts, and the client exe through
REA / Ghidra (VA, image base 0x400000). Tags: **C** confirmed (data / code read), **P** probable, **G** guess (frames),
**O** open. Builds on `map-object-census.md`, `crime-alley-*.md`, `map-manifests.md`, `black-ground-shapes.md`,
`stolen-powers-audit.md`, `targeting-and-relations.md`, `tutorial-data-inventory.md` 5.2.

Image map (tester's list in order): 3 = the x 40 dampener (blue, "Match: Initiating", round segmented ring on cobbles,
no gear, no black disc); 6 = red-orb rubble between the two south stealth strips; 7 / 8 = the enemy lane turret (gear
plate) with the green / yellow disc; 9 = the x 120 dampener (round ring) with the green disc; 10 = minimap x ~40, the
street north of the x 40 dampener (the "second tower" counted from the base: core turret 25.5, dampener 40); 11 = camp
respawn (not mine); 12 = the parked SUV outlined (hover); 13 / 14 = the nook pad with two red rubble craters at its
south corners; 15 = the gaslight armoured truck parked on the west raised street; 16 / 17 = the SUV respawning as a
yellow translucent model; 18 = the truck carried over the champion's head; 19 = the truck in flight; 20 = the impact
(fire, debris, enemies hit).

---------------------------------------------------------------------------------------------------------------------

## A. Liftable props

### A.1 What the data has (C)

No Crime Alley static, layout or type-3 marker places a liftable object (statics `0x820113BB` / `12BB` / `14BB`:
no world state with a Super Strength scriptlet; layout `0xA00002E6` holds only Tutorial 2 placements; `0xA00002E5` /
`E7` none). The original server spawned them from its own data, like the stealth strips. But the map's packs carry
the classes, which is why they are there:

| Class (template) | World state | Pack on CA | Kind | Unit flags 0x1000019D (template) | Scripts 0x8E | Entity table 0x7D2 | WS tables |
|---|---|---|---|---|---|---|---|
| `0x400005C9` "Rock" (`0x490005C9`) | `0x2E000D22` (ctype 7, children `0x2E000D13` / `D14`, team-colour table `0x1D00038B`) | `0xA00002E6` | rubble with red orb = the **meteorite** | **0x22** | `0x34000167`, `0x34000347` | `0x1D0004FB`: Vfx_Fade_In, Vfx_Active, Vfx_PickUp, Vfx_OnThrown, Vfx_OnCollision, Vfx_OnExplode, Vfx_Fade_Out, StateChange_Hide, _Entity_OnEnterWorld_Default, ... | - |
| `0x40000454` (`0x49000454`) | `0x2E000559` | `0xA00002E5` (also GD `0xA000009A`, `0xA00000FC`) | destructible vehicle, modern set | **0x1080** | `0x3400015F`, `0x34000160` | `0x1D00067A`: **Vfx_Spawn_Event01-04, Vfx_Spawn_Alt01 / Alt02** | `0x1D0001FE` + `0x1D00034B` + `0x1D000111` |
| `0x40000459` (`0x49000459`) | `0x2E0008B8` (sound binding 0x7A3) | `0xA00002E5` (GD, CC) | same, modern | 0x1080 | same | `0x1D00067A` | `0x1D000287` (+ Vfx_Active, _Entity_OnEnterWorld_Default) + 34B + 111 |
| `0x4000045D` (`0x4900045D`) | `0x2E000795` | `0xA00002E5` (GD) | same, modern | 0x1080 | same | `0x1D00067A` | `0x1D0001FD` + 34B + 111 |
| `0x40000C40` (`0x49000C40`) | `0x2E000EFE` | `0xA00002E5` (Tutorial 1 `0xA000024C`) | same, gaslight (the tutorial's car; extra script `0x34000600` = tutorial guide ring) | 0x1080 | + `0x34000600` | `0x1D00067A` | `0x1D00060D` + 34B + 111 |
| `0x4000081A` / `81B` / `81C` | `0x2E000F03` / `F04` / `F05` | `0xA00002E5` (T1, GD) | same, gaslight | 0x1080 | `0x3400015F`, `0x34000160` | `0x1D00067A` | `0x1D000611` / `612` / `615` + 34B + 111 |

- Shared vehicle table `0x1D00034B`: SuperStrength_InitObjectPickup `0x100007A2`, SuperStrength_PickupObject
  `0x100007A1`, SuperStrength_ThrowObject `0x100007A0`, Vfx_OnThrown `0x1000087A`, Vfx_OnExplode `0x10000079`,
  Destructible_OnCollision_Metal / _Rubber, Vfx_GuideArrow(_Ping), the Stolen Power hit keys; the per-vehicle tables
  hold Destructible_OnBreak_* and Destructible_OnCompletelyDestroyed. (C)
- The vehicle **world states** carry only `0x1000019D = 0x1000`, `0x50F = 8`, fracture data `0x800`; the
  **templates** add bit `0x80`, `0x10000AA7 = 1`, `0x100000FA = 4`, `0x10000786 = 3`, `0x1000051F` = two carry points
  (+-2, 0, 0) (rock: four at +-1). The client builds the object from the world state, so without the template values it
  is not a Super Strength target (C data; this is why the Tutorial 1 picker refused our car, CHANGELOG `strength
  targeting`). `Data.target_properties` returns [] for these classes (the template records do not parse with the known
  kinds), so the values must be given explicitly.
- Which model is the SUV and which the armoured truck is **O**: no model name survives in the records (`.entity` =
  one-bone skeleton, the mesh comes through the fracture record `0x800`). Set split (P): `0x454 / 459 / 45D` are the
  modern-city cars (also GD / CC packs) -> the **SUV** (images 12, 16); `0xC40 / 81A-81C` the Gaslight vehicles (also
  Tutorial 1) -> the **armoured truck** (images 15, 18-20). The gallery key below settles it in one run.

### A.2 What makes them targetable by Super Strength (C)

Client validator `0x9d01d0` with the Super Strength block `0x480003CB` (`0x1000003D = 14` unit target, relation mask
`0x10000448 = 7` any, unit-flag mask **`0x1000068D = 0x82`**, `0x100007A6` default 0x80000):
- the object's unit flags (`[unit comp]+0xA4`, else property `0x1000019D`) must share a bit with **0x82** and have
  none of 0x80000: vehicle 0x1080 (bit 0x80), rock 0x22 (bit 0x02) pass; the world-state-only 0x1000 fails;
- **`0x10000AA7 = 1`** (targetable) and the status-tag bool **`0x10000029 = 1`** (check B, see `unit_targetable_tags`);
- step 10 is skipped (target & 0x82 and mask & 0x82), so no `0x100001C3` / LifeState needed (send LifeState 4 anyway).
- The right-click basic attack keeps ignoring them: rock 0x22 has no bit of 0x555959; a vehicle's 0x1000 passes step
  8 but fails step 10 (no `0x100001C3`). (C)

Server side: `0x34000164` S2 -> S4 needs `EntityExists(TargetIID) && IsTargetable(TargetIID)` (node `0x1000001C`,
ics: attribute `0x10000029`, `ATTR_TARGETABLE`) (C); the rock's own `0x34000167` also waits on `IsTargetable(SELF)`
before it listens for the throw (S0 -> S5).

### A.3 The full lift / carry / throw sequence (C scripts, P native glue)

Super Strength `0x480003CB` lists three sub-skills in **`0x10000855`** (entries `0x10000854 {0x10000620 skill,
0x10000853 type}`):

| type | sub-skill | script | stats (C) | used for |
|---|---|---|---|---|
| 3 | `0x480003C9` | **`0x34000161`** (lob) | 18 = 2.5 (blast radius), 23 = 9.0 (range), 19 = 2.0, 9 = -0.2, 5 = 75 (+20 / rank, scaling `0x3B0000CA`) | **vehicles**: it raises `0x10000124` for `0x3400015F` (the vehicle's script) |
| 2 | `0x480004A2` | **`0x34000177`** (rubble) | 18 = 8.5 (range), 30 = 15.5 (speed), 22 = 1.25 (width), 14 = 1.5 (knock-down), 5 = 50 (+12.5) | **rocks**: it raises `0x1000001D` for `0x34000167` (the rock's script) |
| 1 | `0x4800044B` | `0x3400016C` (melee weapon, AttacksRemaining) | 18 = 4.5, 5 = 75 (+20) | not on Crime Alley |

The script pairing is C; that the type is chosen by the object's unit flag (0x80 heavy -> 3, 0x02 rubble -> 2, else
1) is **P** (both kinds have `0x10000786 = 3`, so that property is not the selector). No script starts the sub-skill:
`0x34000164` S4 only does `RaiseEvent(TargetIID, SELF)[0x10000037]` on the object, and neither object script handles
0x10000037, so the original server's native code started it. The server must:

1. **Cast** (`0x34000164`, first press, target = the object): S0 -> S2 on `0x1000001D`, Cast, S2 -> S4 (exists +
   targetable): RaiseEvent `0x10000037` on the object (+ SetCleanupFlag 1, SuppressInput). It then waits for
   `0x100000BB` (-> S3, the second-press ground-target state) or `0x10000009` (end).
2. **On 0x10000037 raised on a liftable object** (ics hook in `CastWorld` / `_raise_event_node`): pick the sub-skill
   from the caster's Super Strength `0x10000855` by the object's unit flags, start its script on the caster in the
   same slot (8) with the sub-skill's merged stats, and raise **`0x10000085 {0x9A6A765: object IID}`** on it (both
   sub-skill scripts read `ObjectIID` / `WeaponIID` from that event, graph S0). **Drop the fake `raise_event_follow
   {0x10000037: [0x100000BB, 1.2]}`** for this path: the sub-skill raises `0x100000BB` on `0x34000164` itself (S7 /
   S3) at the right moment.
3. **Vehicle, `0x34000161` graph S3** (HoldsActionLock -> S5 BeginSkill -> S10 range check `IsInRangeAndAngle` -> S6):
   - S6 pickup: RunScriptlet(SELF) `0x100000E9` + **SuperStrength_InitObjectPickup `0x100007A2`**, face the object,
     object untargetable (AddAttributeModifier `0x10000029` false), input suppressed. Needs **OnCastSignal
     `[0x1000000F 3]`** to go on (the animation's grab frame; ics: synthesize ~0.5 s, icserver `lift_step`).
   - S7 toss: object's team = thrower's (`0x1000007E`), SetObjectState(object)[19], **LaunchLobbedMissile(object ->
     the champion, override script `0x34000160`)**, RunScriptlet(object) `0x10000223`, DropObject = 1,
     **RaiseEvent `0x100000BB` -> `0x34000164`** (unblocks it into S3).
   - The toss lands: raise **`0x10000035`** on the object -> `0x34000160` S1: GetCreator, RaiseEvent(creator)
     `0x10000002` for `0x34000161` -> S8/S7 -> **S9 carry**: RaiseGraphEvent `0x100003AF` (CbtState_DisableHit),
     **AttachEntity(SELF, object, offset, attach point `0x100000B0`)**, RunScriptlet both **SuperStrength_PickupObject
     `0x100007A1`**; after AttachmentDuration -> S4 (input back; the Hold graph walks with the hands up: no keys).
     If the old tutorial graph needs it, CarPickup `0x10000246` (via `0x100001E3` + var `0x780`) after PickupObject.
   - Second press (`0x34000164` S3 ground target -> S1 Cast(position)): forward **`0x1000001D` with the cast
     position** to `0x34000161` (S4 -> S1): Cast, FaceTarget, **SuperStrength_ThrowObject `0x100007A0`** on SELF and
     object; OnCastSignal `[0x1000000F 5]` (release, ~0.2-0.35 s: icserver `throw_windup`) -> S2:
     **LaunchLobbedMissile(object -> TargetPosition)** (range stat 23 = 9 m, no override script) and
     ActivateSlotSkill `0x10000136`[0x1000001D]; OnCastSignal `[0x1000000F 2]` -> S3 end: RaiseGraphEvent `0x100003AE`
     (CbtState_EnableHit), RaiseEvent(SELF)`0x10000009` -> `0x34000164` (ends it), EndSkill,
     **_Combat_GoToLocomotion `0x100002FD`**, detach (StopAction), targetable back. If interrupted while carrying
     (DropObject still 1) S3 raises `0x10000124` on the object = explode in place.
   - The vehicle `0x3400015F`: `0x10000049` (launch) twice -> S3 (ShooterIID, LoadSkillStats(shooter)[5 damage, 19
     slow duration, 9 slow magnitude]) -> S1: **Vfx_OnFire `0x1000013E` + Vfx_OnThrown `0x1000087A`** (image 19).
     **On landing raise `0x10000124`** -> S2: FindTargets(ExplosionRange, hostile) -> per target hit FX
     `0x10000223`, **ApplyDamage(stat 5 = 75 + 20/rank)**, **ApplySkill slow `0x48000294`** (2 s, -20 %), accolade
     node `0x100001B0` [0x40000E96] for champions; then Vfx_OnInit / **Vfx_OnExplode `0x10000079`** /
     Destructible_IgnoreAOI `0x10000A9D`, DestructionImpulse; after DestructionDelay -> S4 DestructionImpulse +
     **DestroyEntity [10.5 s]** (image 20). (C; the locals' default ranges are in the script's own data, ics' VM reads
     them.)
4. **Rock, `0x34000177`**: S2 face + RunScriptlet(SELF, object) **SuperStrength_PickupRubble `0x100004CD`**; signal 3
   -> S3: RunScriptlet(object) **Vfx_PickUp `0x1000023A`**, team = thrower's, SetObjectState[17], AttachEntity
   (`0x100000B0`), movement interrupt off, RaiseEvent `0x100000BB` -> `0x34000164`, **RaiseEvent(object,
   SELF)`0x1000001D` -> `0x34000167`** (shooter = the champion), RaiseEvent(object)`0x100000F9`, graph `0x100003AF`,
   StartScriptlet **SuperStrength_Rubble_Active `0x10000775`** (loop while held); signal 2 -> S4 wait for the second
   press `0x1000001D` -> S5: stop the loop, Cast, **SuperStrength_ThrowRubble `0x100004CC`**; signal 5 -> S6
   **LaunchMissile(object, TargetPosition, range 8.5, speed 15.5)** (straight, width 1.25), RunScriptlet(object)
   `0x1000008D`; signal 2 -> S7 end (graph `0x100004C6` SuperStrength_Rubble_End, `0x10000009` -> `0x34000164`).
   The rock `0x34000167`: `0x10000049` -> S2 Vfx_OnThrown -> S7: each collision **`0x10000002 {0x632FE62 target,
   0x33016EE position}`** -> if alive, hostile, `IsKind 0x10108`: **ApplyDamage (50 + 12.5/rank)**, hit FX,
   **ApplySkill knock-down `0x48000295` for stat 14 = 1.5 s** (the tester's "stun"), Vfx_OnCollision `0x10000016`,
   DestructionImpulse, then fizzle -> DestroyEntity 0.3 s; a destructible (IsKind 0x1000) only gets the impulse; flight
   end `0x10000035` with no hit -> S3 **Vfx_Fade_Out `0x1000006A`** -> destroy. `0x34000347` (phasing / sub-entity
   impulses on collision) needs nothing extra. ics already raises these for the Meteor Drop meteor
   (`thrown_spawn_classes`), so the same events serve the rock once it flies as a missile.

### A.4 Placement (G from frames unless tagged)

| Prop | Class / WS | Pos (x, y, z) | Yaw | Evidence |
|---|---|---|---|---|
| Meteorite 1 (vs AI) | `0x400005C9` / `0x2E000D22` | (80.1, 72.8, 200.0) | 0 | image 6: between the south stealth strips (76.6, 72.2) / (83.6, 72.3) (C strips in `maps.py`, G rock) |
| Meteorite 2 / 3 (vs AI) | same | (54.7, 82.9, 200.0), (105.0, 82.7, 200.0) | 0 | `crime-alley-still-missing.md` 7 (G) |
| Meteorites at the nook (image 14, "2 craters") | same | (72.0, 92.5, 200.0), (88.0, 92.5, 200.0) | 0 | G: the two red rubbles at the nook pad's (80, 97.25) south corners by the fence; the 2v2 survey had one at ~(84, 93.5) - check against image 14 in game |
| Clash variant | same | (69.3, 72.7), (90.7, 72.7) | 0 | 2v2 15:56 (G) |
| SUV (east) | one of `0x40000454` / `459` / `45D` | (100.0, 95.5, z from navmesh) | 180 (long side along x, G) | images 12 / 16: north-west of the east jungle-mouth stealth tile (108.3, 85.5); minimap x 95-107; 2v2 survey "parked SUV next to the camp (~110, 95)" |
| Armoured truck (west) | one of `0x40000C40` / `81A` / `81B` / `81C` | (61.5, 96.0, z from navmesh) | ~210 (nose to the south-west, G) | image 15: north-east of the west mouth tile (51.7, 85.5); minimap x ~58; "like the one on the other side" |

Spawned by the server at match start (no client static exists). Each spawn: class + world state as above,
`0x100007A2` side none / neutral team (relation mask 7 accepts any; the scripts set the thrower's team at pickup and
the rubble goes back to neutral `0x1000007E` at the end), extra props **`0x1000019D` (template value), `0x10000AA7 =
1`, `0x10000029 = 1`, `0x100000FA = 4`**, server attribute `ATTR_TARGETABLE` set, scripts from the template (`0x8E`;
`Data.entity_scripts` reads them: C). After create: vehicle **Vfx_Spawn_Event01** (the yellow phase-in of image 16,
same key the jungle camps use) then, P, Vfx_Spawn_Event02 when solid; rock **_Entity_OnEnterWorld_Default + Vfx_Active**
(glow), **Vfx_Fade_In** on a respawn. Respawn (tester: "every so often"): when the object is destroyed (vehicle 10.5 s
after impact, rock 0.3 s after its hit / fizzle) start a timer and spawn a fresh one at the same spot with the spawn
scriptlets (G: 60 s; the 2v2 survey saw the SUV back at a new spot between 7:30 and 11:00). Packs: `0xA00002E5`
(vehicles) and `0xA00002E6` (rock) are both in Crime Alley's 0x20AF list (C). Navmesh: a vehicle should block a
footprint (~4.5 x 2 m, icserver `CAR_B_BOX`) while parked, none while carried.

### A.5 Proposed `[ics]` keys

```toml
liftable_props = true                     # spawn the map's liftable props (below)
liftable_respawn_seconds = 60.0           # G: tester "every so often"
[ics.liftable_props_by_map]
crime_alley = [
  {kind = "rock", class = "0x400005C9", world_state = "0x2E000D22", pos = [80.1, 72.8, 200.0], yaw = 0.0},
  {kind = "rock", class = "0x400005C9", world_state = "0x2E000D22", pos = [54.7, 82.9, 200.0], yaw = 0.0},
  {kind = "rock", class = "0x400005C9", world_state = "0x2E000D22", pos = [105.0, 82.7, 200.0], yaw = 0.0},
  {kind = "rock", class = "0x400005C9", world_state = "0x2E000D22", pos = [72.0, 92.5, 200.0], yaw = 0.0},
  {kind = "rock", class = "0x400005C9", world_state = "0x2E000D22", pos = [88.0, 92.5, 200.0], yaw = 0.0},
  {kind = "vehicle", class = "0x40000454", world_state = "0x2E000559", pos = [100.0, 95.5, 0.0], yaw = 180.0},
  {kind = "vehicle", class = "0x4000081B", world_state = "0x2E000F04", pos = [61.5, 96.0, 0.0], yaw = 210.0},
]                                          # z 0 = from the navmesh
liftable_props_extra = {"rock" = {"0x1000019D" = 0x22}, "vehicle" = {"0x1000019D" = 0x1080},
                        "all" = {"0x10000AA7" = true, "0x10000029" = true, "0x100000FA" = 4}}
liftable_spawn_scriptlets = {"vehicle" = ["Vfx_Spawn_Event01"], "rock" = ["_Entity_OnEnterWorld_Default", "Vfx_Active"]}
liftable_respawn_scriptlets = {"vehicle" = ["Vfx_Spawn_Event01"], "rock" = ["Vfx_Fade_In", "Vfx_Active"]}
liftable_gallery = false                  # test aid: all 7 vehicle classes in a row behind the blue base
                                          # (x 8, y 66..90 every 3.5 m) so the tester names the SUV and the truck
super_strength_subskills = true           # 0x10000037 on a liftable -> sub-skill of 0x10000855 by unit flags
super_strength_subskill_by_flag = {"0x80" = 3, "0x02" = 2}   # else type 1
super_strength_cast_signals = {"pickup" = 0.5, "release" = 0.25, "end" = 0.6}   # OnCastSignal 3 / 5 / 2, s
super_strength_landing_event = "0x10000124"   # raised on a thrown vehicle when its lob lands
# and raise_event_follow loses its "0x10000037" entry when super_strength_subskills is on
```

---------------------------------------------------------------------------------------------------------------------

## B. Floors

### B.1 Dampener floor, image 3 (C cause, P fix)

The black disc under both dampeners is the **terrain socket** of `0x800113BB` (vertices (40, 75) / (40, 80) and
(120, 75) / (120, 80) lowered to 179.96 m: a 20 m funnel, opening x 35-45, y 70-85; `map-object-census.md` 1.3, C).
Image 3 shows what the original had there: the dampener's own round segmented ring (`0x2E000E04`, ~6 m, drawn by ours
already) on **continuous cobbles with ember craters**, no gear plate, no hole. So the socket must be closed by a floor
piece, not by the structure. Data: `0x2E00119F` has no geometry (C); the only fitting piece in the map's packs is
`0x2E0000E3` (zone pack `0xA00002E5`, `.entity 0x2D00007B` bbox -5..5 x -10..10 x 0..2, placed by nothing) (C bbox,
P identity). ics took the Crime Alley covers back after the 19:28 test ("what was placed at the towers' base is not
right": `match_socket_covers.crime_alley = []`), so the octagon is open again. Recipe:
- Keep the dampener alone on (40, 77.5) / (120, 77.5) without a turret plate (already so, `match_turret_plates` only
  "turret").
- Re-test `0x2E0000E3` **once more with z 198.0 and yaw 0** (top flush with the street at 200.0, 10 x 20 m covering
  y 67.5-87.5), created **before** the dampener, `0x2A1 = true`, no team; ask the tester for a screenshot from above
  the dampener. If it shows a raised box or wrong material (what 19:28 probably saw), the fallback is a lower z
  (199.9: only the lid at street level) or a terrain fix: the socket vertices are server-independent, so the last
  resort is an exe-side (patcher) or pack-free option (O). Config already exists (`match_socket_covers`).
- Image 10 (the street just north of the x 40 dampener, y ~85-90) is the north end of the same funnel (y up to 85):
  the same cover closes it (P). Nothing else in the statics within x 30-55, y 82-105 depends on the server (all type
  7 with creation types 3 / 5 / 6, one type-3 ambient marker `0x2E001118` with no record) (C).

### B.2 Lane-turret floor, images 7 / 8 / 18 (C)

The lane turret's gear plate `0x2E000A9F` (ics `match_turret_plates`) is what images 7, 8, 18 show; the ground
around it is the client's cracked-cobble street. Nothing missing there from data; the "segment" remark most likely
refers to image 10 / the dampener socket (B.1). If the tester means a gap in the gear ring itself, that is the model's
own look (the original's ring in image 18 also has open teeth) (P).

---------------------------------------------------------------------------------------------------------------------

## C. Turret warning ring (green / yellow / red), images 7-9 (C)

Entirely client-computed (`0xA84FB0`, run every frame by `0xA8C960` and on property changes by `0xA8CA10` <-
listener `0xA8DFB0`). Registration `0xA7CA20` (on entity add) takes an entity only if:
1. unit flags `0x1000019D & 0x10` (`0x9D0180`) - turrets / core turrets 0x210, dampeners 0x810, cores 0x4010 (C
   templates; ics already sends them on hostile units);
2. bool **`0x10000C5D` = true** (all CA structure templates have it, C; **ics never sends it**);
3. not allied with the local player (`0x85C130`), not view-match;
4. attack range from the unit component (`0x9CFC40`, property `0x10000133`, 9.0 on CA turrets / dampeners, 10.0 on
   the core) > 0.

Entry (0x50 bytes): IID, +8 = bool **`0x10000C5B`** (armed), +9 = dead (LifeState `0x100000FA` != 4 or
`0x10000B2D`), +0x10 = IID **`0x10000C66`** (the turret's current target), +0x20 range r, +0x24 r^2, +0x28 r + 5.5,
+0x2C (r + 5.5)^2, +0x30 (r + 1)^2, a physics phantom of radius r + 5.5 (`0xA2A710`, team filter `0x210000` =
minion unit flags, P) fills +0x3C with the units inside. Listener `0xA8DFB0` updates +8 on 0x10000C5B, +9 on
0x100000FA / 0x10000B2D, +0x10 on 0x10000C66.

State each frame (C, assembly checked): dead / inactive -> 6 (hidden); `0x10000C5B` false -> **3 green**; target
IID == local champion -> **5 red** (solid, alpha 0.7); champion farther than r + 5.5 -> 6 hidden; else count the
alive units of the list within r **of the turret**: >= 2 -> **3 green**, 1 -> **2 yellow**, 0 -> **5 red** if the
champion is inside r, **1 red** (fading) if outside. Colours (`0xA0EF20`, RGBA at `0x186DB90`): 1 (0.9, 0.1, 0.1),
2 (1, 1, 0.65), 3 (0.5, 1, 0.5), 5 (1, 0.05, 0.05, 0.7), 6 white alpha 0; alpha for 1-3 fades from 0.55 inside
r + 1 to 0 at r + 5.5. Needs option `TurretWarningEnabled` (byte `0x186CE4F`) and the dialog enable notice
`0x10000205` (ics sends it). On each state change it plays **`_TurretWarning_WarningState 0x1000103D`** (table
`0x1D000923`) on the turret with variables `0x10000CC2` = state, `0x10000CC3` = previous, `0x10000CC5` = champion
IID, `0x10000CC1` = inside-range flag, and sets property `0x10000D87` = state (WarningStateCurrent, read by the
coaching script `0x340007EC`).

Server recipe:
- In every structure's create bundle (turret, core turret, dampener, core): **`0x10000C5D` = true** (kind 0x16) and
  **`0x10000C5B` = true** (armed; false before the gates open would show green during the countdown, P), unit flags
  and `0x10000133` as today. Must be in the create bundle: registration runs once at entity add.
- When the server turret's target changes (`units.py _turret_target`): event 0x6 **`0x10000C66` = target IID**
  (kind 0x07), 0 when it drops the target. That alone gives red when the local champion is shot.
- The minion count is the client's own, but the phantom filter wants **minion unit flags on the allied minions too**
  (the champion's own wave is what makes yellow / green); ics sends `0x1000019D` only on hostile units
  (`unit_target_properties`), so allied minions must get their template's `0x1000019D` (0x10000) as well (P: the
  validator still refuses allies by relation, so it changes nothing else).
- Keys: `turret_warning = true` (C5D / C5B in the bundle, C66 on target change), `turret_warning_armed_at_start =
  true`, `unit_flags_on_allies = true`.

---------------------------------------------------------------------------------------------------------------------

## D. Open / to check in game

1. Which vehicle class is the SUV and which the truck (`liftable_gallery`).
2. The sub-skill selector (unit flag vs something native): if the rock is lifted with the vehicle animation, swap the
   map in `super_strength_subskill_by_flag`.
3. Respawn time and whether the vehicle's yellow phase-in also needs Vfx_Spawn_Event02-04 in sequence.
4. Meteorite positions beside the nook (image 14) and whether they sit in a crater model (the rubble model itself has
   the crater look in image 6, P).
5. Whether `0x2E0000E3` at z 198 is the right lid (B.1) or a lower z is needed.
