# Fog of war at run time: draw gates, vision sources, client-side visibility (static analysis, 2026-10-23)

Context: the tester's Crime Alley match on 2026-10-23. The minimap image now loads (cave N, `icserver/patcher.py`
"minimap"), but the fog is never drawn and allied minions give no vision: he only sees enemies near himself.
Complements `movement-collision-fog-map.md` 2 and `full-maps-world.md` 7.3, and corrects them in places. C =
confirmed in the code, P = probable, O = open. Addresses are VAs (image base 0x400000; file offset = VA - 0x400C00
in .text). Sources: a capstone sweep of the exe and the Ghidra decompilation cache.

## 1. Object graph (C)

- **Fog component** CFogOfWarComponent (component type `0x10000013`, system object `0x1B76C28`, vtable 0x1609A70,
  list at +4). It is built by the entity factory **0xA9D7A0** for every class with DID type 0x40 whose **IID top
  byte is 2** (`0x4DAF10`), through 0xA9D730 -> 0xAB0370. The normal class has vtable 0x16098E8 (ctor 0xAAF7F0 /
  0xAAB070). The view-match class has vtable 0x16099D8 and is picked when `0xABEE50` = `[[0x1B77138]+0xAC]` is set.
  Every `ics` object has top byte 2, so every unit carries one. Only the one whose owner is valid does any work.
- Interfaces: +8 vt 0x16098BC (slot 1 **0xAAB210** = "entity added": puts the IID in the candidate list +0x170 /
  count +0x178); +0x40 vt 0x1609990 (slot 1 **0xAAFAE0** -> **0xAAE5B0** RenderFogScene); +0x44 vt 0x1609984.
- vt+0x24 **0xAADD80** (called by the object-added notifier 0x54D4C0): runs only when the added object is
  `0x6351D0()` = the local player object (IID at 0x1B6A710). It then subscribes +8 to event list 0x26
  (`0x68EDA0`), joins the update list 0x1B76C2C (`0x9760A0`) and, only if `[[0x1B73518]+0xDC]` (WorldRender)
  exists at that moment, creates the render targets (`0xAA5050` -> `0xAA3C90`, 256 x 256 = `[0x1870694]`*4) and
  registers +0x40 with WorldRender (`0x78F2D0`, list +0x644). There is no later retry of that registration (P).
- vt+0x68 **0xAB3520** update (from the system's 0xAACAB0) -> 0xAA5050, **0xA9F240**, **0xAB12C0** (add sources),
  0xAADF70 (refresh), 0xAAE0E0 (draw circles).
- Owner = vt+0x7C 0xA9DE00 -> `0x85D620(property 0x100000CF)` (the champion). The update needs the owner's
  position to be valid and game state != 7.

## 2. RenderFogScene 0xAAE5B0: gates in order (C)

1. `[comp+0xA8]` render target exists and `[RT+0x70] == [0x1B76C64]` (256). Otherwise the function returns.
2. Throttle: when `[comp+0xF8] == 0` it waits until the accumulators +0xF0 / +0xF4 reach 1.0.
3. `darken = !attribute(0x85C150(), 0x100007C0)` (address 0xAAE7C5).
4. `MM = [0x1B758F4]`. MapManager's ctor sets this to itself (0xA6A4AA) and its dtor clears it (0xA6A54D), so in a
   match it is **always set**. It is the same object as `[[0x1B758D4]+0x50]`. If the landblock lookup
   `0x6CCE60(MM+0xAC, +0xB0, +0xB4)` fails, or the result is cached and darken is unchanged (+0x15C), only the
   **base bake is skipped**. The bake: per texel `[comp+0xDC] * v`, where v = 1.0, or `1 - sample(terrain layer
   0x10000002)` when darken is set. The MM+0x70 / +0x74 textures feed the material `0x10000001` (gmFogOfWar).
   Missing textures skip only that material.
5. Compose: `WR = [[0x1B73518]+0xDC]`. It draws when WR == 0 or (`WR+0x36` EnableFog and `WR+0x39` EnableMaskFog).
   Otherwise it clears to `[0x1B76958]`, sets +0xF8 and returns. Defaults (ctor 0x7F1310): +0x36 = 1; +0x39 = 1
   unless `[0x1B779A4] & 0x80000011 == 0x80000011`. The client app type is 0x40000001 (0x4032E3), so both are on.
   Strings: `WorldRender.EnableFog` / `EnableMaskFog` registered at 0x7F1B28 / 0x7F1BC8.
6. Output: the RT goes to `[0x1B72170]+0x48` (`0x778960`), then a ping-pong blend into `[comp+0xB0]`
   (`0x76A0F0`). World materials read it as texture source **type 4** (`0x6CCF60` case 4). So the darkness on the
   ground comes from the map's materials. The server sends nothing for it.

None of these gates depends on a value that only the server can supply, apart from the owner (0x100000CF) and the
local player object. Which one fails at run time is O: `tools\diag.py --fog` already has breakpoints at 0x6AE5B0
(gate 1), 0x6AE65B, 0x6AE7C9 (darken), 0x6AE8C5 / 0x6AE900 (gate 4) and 0x6A5074 (RT).

## 3. Vision sources 0xAB12C0 (every 0.4 s, per candidate) (C)

A candidate becomes a source (0xAB0C60) only if all of these hold:
- The entity exists. Entity flags +0x118: not (bit 0x40 set without bit 8).
- vt+0x70 0xA9DE10 accepts it (always, unless the owner has 0x100007C0).
- `0x2A1` != false.
- It has attribute **0x100006FC**, or:
  - it is alive (`0x9CFAF0`: LifeState 4, without 0x10000B2D), and
  - an **ally** (relation 4) needs `0x9D0180(ent, 0x1F4978)`, an enemy needs 0x9D0180(ent, 8), and a neutral
    is never a source.
- Its position is valid (0x409760).
- Its radius vt+0x78 `0xA0D0D0` is > 0. For an ally the radius is **0x9CFCA0** =
  `([ent+0x84] ? [unit comp+0x8C] : property 0x10000133) + attribute 0x10000642`.

Two cached values decide this, and both live in the **unit component** (ctor 0x979170):
- `0x9D0180` reads the PerceivedType from **`[unit comp+0xA4]`** (watcher 0x1000019D). The mask 0x1F4978 =
  Character 8, Turret 16, Missile, CharacterInteractive, Creature, Inhibitor 2048, Base 16384, Minion 65536,
  Device, DoomsdayDevice, CapturePoint, Pet. It excludes Siege (1024), Objective, Destructible, Boss and
  AutomatedPlayer.
- The radius is read from **`[unit comp+0x8C]`**. Its initial value is **-1.0**, and the watcher at +0x80
  (vt 0x15F9804, 0x978C30 / 0x978C60) stores a value only for kind 9 when the property *changes*. This is the same
  mechanism that left 0x1000019D at 0 when it was sent in the creation table (fase3-gd).

So a radius sent only in the creation bundle stays -1 (P, by analogy with 0x1000019D). An ally is then not a
source unless 0x10000642 > 1. The champion has no 0x1000019D change at all (only units get `_late_flags`), so it
fails the type test (P).

## 4. Does the client hide entities? (C)

vt+0x6C **0xAAA670** is the client's visibility evaluator. 0xA9F240 runs it on every candidate and source on
every update, unless `[0x1B766B0]+0x30` is set. It skips in view-match (0xABEE50) and **writes property 0x2A1**
(`0x5563E0`):
- The owner has no attribute **0x100007C0**: **0x2A1 = true for every entity**.
- Otherwise 0x2A1 is true if the entity has attribute 0x100006F3, or `0x58A430(owner, iid)`, or (distance <=
  0x9CFCA0(owner) and line of sight 0xAA97C0). Otherwise false.

Meaning of 0x100007C0 (P): a blind-type status. With it, sources are limited to 0x100006F3 entities (0xA9DE10),
the bake ignores the terrain layer, and enemies are hidden locally. Normally it is absent, so the client never
hides enemies. **The server must hide them with 0x90F**, and must not use 0x2A1 for that: the client overwrites
it with true about every 0.4 s.

## 5. Changes, ranked

1. (C, server) `World.fog()` (`ics/world.py`) shows an enemy only when it is within `fog_vision_radius` of the
   **champion**. This is the tester's "only enemies near me". It should count every allied source: allied
   units and structures with their vision radius (`mu.vision`), alive, plus beacons and cameras, each with its
   own line check.
2. (P, server) After creation (and after a respawn or full re-bundle), send by event 0x6 `0x10000133` kind 9 as a
   change, first 0.0 and then the radius. Do this on the champion and on every allied unit and structure that
   should see, the way `refresh_flags` does for 0x1000019D.
3. (P, server) Send by event 0x6 `0x1000019D` kind 0x13 = 8 (Character) on the champion, as a change. Allied
   sources whose PerceivedType is outside the mask (Siege 1024) need a mask bit, or attribute 0x100006FC = true.
4. (O, run time) If the ground is still not dark: run `tools\diag.py --fog` and see which gate in section 2 fails
   (RT missing = WorldRender was absent when the local player object was added).
5. Never send 0x100007C0. No exe patch is needed for the above.
