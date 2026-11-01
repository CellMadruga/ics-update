# Client status effects and crowd control (static analysis, 2026-10-22)

Exe: `InfiniteCrisis.exe` (VA, image base 0x400000). Confidence: **C** = read in the decompiled code, **P** = probable
(inferred from code + data, not tested in game), **?** = open.

Question: the server must knock Gaslight Batman down when the big meteor lands (and generally stun / root / slow).
Raising graph events alone (`0x100001E3` + variable `0x780` = `CbtState_Knockdown 0x100002F5`, fase3-gj) showed
nothing and the client kept moving him. `logs/traffic.log` of that run: after `CbtState_Knockdown` the server sent no
movement for Batman, yet the client kept sending move orders (`0x20EE` cmd 4 every ~0.2 s) and he kept walking, so the
client moves its own champion from its orders (local prediction) unless the client itself refuses the order (P).

## 1. How crowd control is represented in the client

CC is **not** a property of the effect message. It is a set of **bool unit attributes** (property group 0x3F,
`NetSharedVisually`, object table `[ent+0x38]`), read through the attribute component (`obj+0x84`, getter `0xaa0dc0`)
with `0x974940(obj, &iid, &attrId, default)` -> `0x973730` (base value via vtable +0x60, then the per-attribute
modifier hash at component `+0x10..+0x1c`, plus a second source at `+0x38`) (C). Attribute modifiers are what status
scripts add with `AddAttributeModifier 0x10000008` / remove with `RemoveAttributeModifier 0x10000033`. The server can
also set the base value directly with event `0x6` (set property) - that is exactly how fase3-gf made the drones
targetable (`0x10000029` / `0x10000249` go through the same `0x974940` reader) (C by analogy, same reader and group).

Attribute ids (tables of u32 ids in .rdata; `0x8709e0` = CanActivate, `0x9cfaf0` = "may act"):

| Attribute | Table addr | Meaning (evidence) | Conf |
|---|---|---|---|
| `0x100003F3` | 0x15ED810 | **Stunned**. CanActivate returns ErrorType `0x10000051` (Stunned); `0x863860` (via `0x8686c0`) buffers skill/attack orders (cmd 2/9) instead of sending them; listener `0x85ec10` clears the queued cast (`0x85e9a0`) when it turns true. Added by every stun/knock status script (`0x34000130/131/132`, `0x340006D3`, `0x340000C6`, `0x340000EA`, `0x340003DB`, `0x340004A4`, `0x3400052D`); `HasFlagAttribute 0x1000006A` tests it | C |
| `0x100007FE` | 0x15ED824 | **Rooted**: CanActivate `0x10000050` for skills with bool `0x100007FD` (movement skills) | C (id) |
| `0x10000B39` | 0x15ED830 | **Crippled**: CanActivate `0x1000006B` for movement skills | C (id) |
| `0x100005A3` | 0x15ED818 | **Silenced**: CanActivate `0x1000003B` (slot != 0); added by `0x340001C1` | C (id) |
| `0x10000B2D` | 0x15FE67C, 0x15ED82C | **Cannot act / disabled**: `0x9cfaf0(obj, &checkB2D)` = `LifeState(0x100000FA) == 4 && !0x10000B2D`. `0xa70030` (issue order) returns 0 **before sending 0x20EE** when this fails, for every command (move included); also CanActivate `0x10000054`; listeners `0x85ec10` (clear queued cast), `0xab00a0`, `0xa1dc10`, `0xa8dfb0` (HUD "can act" flags). Added by `0x3400041C`, `0x34000662` | C (code), name P |
| `0x100000FA` | - | LifeState (4 Alive). Anything but 4 also fails `0x9cfaf0` (all orders refused) but hides the nameplate | C |
| `0x100004ED`, `0x10000627`, `0x10000907` | 0x15ED814.. | other bools in the same table (unknown) | ? |
| `0x100006FE` (f32) | 0x15ED820 | modified by 16 scripts (likely a speed / slow multiplier) | P |

Order path (C): `0xa8a140` -> `0xa86a00` (target / point) -> `0xa70030(champ, cmd, ability, pos)`:
1. if skill bool `0x10000B4D` is false, `0x9cfaf0(champ, check B2D)` must pass, else **return 0 (nothing sent)**;
2. `0x8686c0` (`0x9cfaf0` again, then cmd 2/9 -> `0x863860`: Stunned -> buffer; cmd 3/4 -> buffered only while an
   action lock `[+0x70]/[+0x74]/[+0x8c]` is held); a buffered order is not sent;
3. otherwise the order is sent with `0x88b030` (0x20EE). `0x868bf0` is a navmesh check of the clicked point, not motion.

So **Stunned alone does not stop move orders** (cmd 3/4 pass `0x863860`); only `0x10000B2D` (or LifeState != 4)
makes the client refuse a move order before it is sent / predicted (C for the code path, P that this also stops the
local motion).

## 2. Status records and their scripts (the original data)

Status effect records `0x48...` (property `0x10000242` = server script, `0x10000063` max stacks):

| Status | Script | Props | What the script does |
|---|---|---|---|
| `0x48000293` (also `0x4800159D`) | `0x34000130` **Stun** | stacks 1, `0x1000072D`=0xC, `0x10000334`=0x4100 | enter: scriptlet `0x10000999` Vfx_Status_Stun_Active, `DisableActions` (family 77, prio 50), RunScriptlet `0x10000331`, `SetAIEnabled 0`, `AddAttributeModifier Stunned 0x100003F3`; exit: `RemoveAttributeModifier`, RunScriptlet `0x10000330`, `RaiseGraphEvent 0x1000004E` (`0x100000AA`), `StopAction`, `SetAIEnabled 1`, FX `0x1E0000CF` |
| `0x48000295` | `0x34000131` **Knockdown** (thrown car) | stacks 1, `0x1000096E`=4, `0x1000072D`=0xC | enter: EffectStartTime = now, `DisableActions(SELF, 77, 1, 50)` -> KnockupHandle, `AddAttributeModifier(SELF, Stunned 0x100003F3)` -> StunnedHandle, `SetAIEnabled(SELF, 0)`; state 2: `PlayHitScriptlet` (`0x100003EA` _ExecuteScriptlet, FX record `0x1E000057`), get-up timer from EffectDuration / InAirTime / BaseGetupTime / MinGetupTime; get-up: `SetGraphVariable AnimationSpeedMultiplier (0x10000936)` = BaseGetupTime / TimeForGetup, RunScriptlet `0x10000355` (get-up; catalog name is a hash collision); exit: remove modifier, `StopAction`, `SetAIEnabled 1`, if alive and not still stunned RunScriptlet `0x100002FD` _Combat_GoToLocomotion + AnimationSpeedMultiplier = 1.0 |
| `0x48000296` | `0x34000132` **Knockup** | `0x1000096E`=0xB | like 0x131; get-up raises graph event `0x1000009D` CbtState_GetUp through `0x1000004E`; FX `0x1E0000CA` |
| `0x4800113C` | `0x340006D3` knockdown variant | `0x1000096E`=4 | like 0x131 plus hit scriptlet `0x10000223` (VFX_CBT_Hit_Shared) |

Script parameters (from the trees): EffectDuration, EffectSource, plus constants 0.7 / 0.4 / 0.07 for the get-up
times. `DisableActions 0x1000005B` has an empty client execute (vtable slot 10 = `0xab4d80` = `ret`), so it is
server-only; `AddAttributeModifier` has a client execute (`0x992a70`) (C). The knockdown fall clip itself is not
raised by the script directly: it comes from the FX scriptlet record `0x1E000057` (not located in the packs by a plain
header search) (P).

## 3. Effect messages: wire format (C unless noted)

Effect component = agent `obj+0x8C` (getter `0xaa1a60`): instance list at `+0x20` (data) / `+0x28` (count), dirty
flags `+0x30` (bit 0 set on add). An effect instance is a **generic script instance** (size 0x1EC, ctor `0x44bd00`,
serializer `0x44c480`) running a **DB-type-7 record = a 0x34 script graph** (the same factory `script_decoder.py`
uses). Its vtable +4 returns its GUID (`+0x1D8`); instances are matched by GUID (`0x96cff0`, 16-byte compare).

### 0x200F / 0x2062 add one (serializer `0x843d60`, handler `0xa9fb00`)

```
u8 0                         header (0xb0d380)
ScriptInstance               (0x83d530 -> new instance, 0x44c480 reads it)
  -- variable store at +0x70 (0x461e10) --
  cint nA, nA x Value        list +0x80 (0x461940; count via 0x421430/0x4fd820 compact int)
  cint nB, nB x Value        list +0xD0
  u32 count, u32 capacity    map (0x461c00), capacity >= count (allocates capacity x 16)
  count x { u64 key, Value } read from the last entry to the first
  -- identity --
  GUID (u32, u16, u16, u64)  +0x1D8 (0x450fa0): the instance id used by remove / update / events
  u8                         +0x1E8 (stored as u32; meaning ?)
  u32 script DID             +0x0C, resolved as DB type 7 (0x5dfba0(did, 7) -> 0x43a1e0); the null DID value
                             (global 0x1b57f2c) = no script; an unknown DID is a stream error (0x80004005)
  u8 hasLocalState           0x44afe0; if 1: a variable block object (factory 0x55, ctor 0x452580) read by
                             0x45aa30 (types 0x45a610, name table 0x45a940, check 0x45a300) - the script record's
                             local-variable block format
u8 fresh                     +0x24; if 1 the handler first notifies the instance's listeners (0x449120)
```
`Value` (0x461860): `u32 typeId` (0 = null); else the value object is built by `0x45e450(typeId)`, then `u32` (+8)
and the typed payload `0x44a370` (P for the payload layout). Empty variable lists are `00 00 00000000 00000000`.

Add (`0x976a80`): if an instance with the same GUID is already there the message is ignored; otherwise it is
appended, addref'd and the component marked dirty. Starting / ticking the script happens in the component update
(not traced, P).

### 0x200C / 0x2043 list (`0x846f30`, handler `0xaa1cd0` -> `0xa9fb40`)
`u8 0 | u32 n | n x ScriptInstance | u8 fresh`; each instance not already present (by GUID) is added as above.

### Others
- `0x202B` / `0x2037` remove: `u8 0 | GUID` -> `0xaa4220` -> `0x976b30` (C).
- `0x2019` / `0x206F` set variable: `u8 0 | GUID | {u32 u32 u32} var ref | Value`; ignored unless the instance has a
  slot for that variable (`[inst+0x60]+4+idx*8`) (`0xaaa830` -> `0xaa46a0`) (C).
- `0x2008`: `u8 0 | u64 agent | u32 event DID | u32 key` -> script event (`0x4607a0`) queued on the agent's effects
  (`0xaa1bf0` -> `0x96ded0`); an instance only queues events its graph listens to (`0x461430`, sorted list `+0xD8`).
- `0x970a80` raises script event `0x1000009D` on the effect whose GUID a component holds (`+0x70`) when its flag 4 is
  set - effects receive script events (C).

## 4. Recipe: knock Batman down for ~5 s

Recommended (simple, uses channels already proven by fase3-gf), all on `CHAMPION_AGENT_ID`:

| t | Send | Why |
|---|---|---|
| 0 | stop Batman server-side (dest / path cleared) and send his authoritative position / stop as the server normally does for a stop | cancels a path the client already predicted (P) |
| 0 | event 0x6 `0x10000B2D` (bool, kind 0x16) = 1 | `0x9cfaf0` fails -> `0xa70030` refuses every order (move included) before 0x20EE / prediction; queued cast cleared (C code, P effect) |
| 0 | event 0x6 `0x100003F3` Stunned = 1 | skills refused with ErrorType Stunned, buffered skill orders, the original's stun semantics (C) |
| 0 | graph events as now: `CbtState_Knockdown 0x100002F5`, +1.8 s `CbtState_Dead 0x1000010B` | the fall; should now stay visible because no new order/locomotion overrides it (P) |
| 0 (optional) | scriptlet `0x10000999` Vfx_Status_Stun_Active | stun stars, as `0x34000130` |
| +5 s | scriptlet `0x10000490` RunScript_Vfx_GetUp + graph event `CbtState_GetUp 0x1000009D` (0x34000132 raises exactly this) | the get-up returns to Locomotion by itself (`state_to_locomotion` at 0.4 s) |
| +5.5 s | event 0x6 `0x100003F3` = 0 and `0x10000B2D` = 0; optional scriptlet `0x100002FD` _Combat_GoToLocomotion | the knockdown script's exit; orders accepted again |

Keep the server-side `down_until` guard. Config keys suggested: `[ics] knockdown_attributes =
["0x10000B2D", "0x100003F3"]`, `knockdown_hold = 5.0`.

Other CC with the same mechanism: stun = `0x100003F3` (+ `0x10000B2D` to stop walking) with `0x10000999` FX; root =
`0x100007FE` plus the server refusing move orders (no client check of Rooted on plain move orders was found, so also
`0x10000B2D` if the client must not walk); silence = `0x100005A3`; slow = lower the speed the server moves him at
(`0x100006FE` f32 is the likely client-side multiplier, P); FX `0x100003CC` / `0x100003CD` Vfx_Status_Slow_Active /
_Stop.

Alternative (the original's full way, higher risk): `0x200F` with a script instance of `0x34000131` (or `0x34000130`
for a stun), fresh GUID, empty variable lists / map, `u8 0` local state, `fresh = 1`, plus the same `0x6` values (the
server owns the attributes); remove with `0x202B` + GUID after the duration. The client would run the script's client
nodes (modifier, get-up scriptlets, FX `0x1E000057`) itself, but EffectDuration / EffectStartTime live in the variable
store, whose Value payload is not fully mapped (P), so an empty store may end the effect at once.

## Open
- Where the client applies local motion for an accepted move order (the component that predicts); whether it also
  honours Stunned / Rooted. Test: with `0x10000B2D` = 1, clicks must not produce 0x20EE in `traffic.log`.
- Real names of `0x10000B2D`, `0x100004ED`, `0x10000627`, `0x10000907`; the FX record `0x1E000057`.
- The `Value` payload (`0x44a370`) and the component update that starts an effect's script.
