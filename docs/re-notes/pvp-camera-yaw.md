# PvP camera yaw (Crime Alley diagonal view)

Question: why our client shows the Crime Alley lane diagonally (lane along +x at y = 77.5) while the original
video shows it left-to-right with the blue base on the left, and what the server must send.
Confidence: C = confirmed in code / data, P = probable, G = guess.

## 1. The map camera and its yaw (C)

- Active camera manager: `[[0x1B73518]+0xE4]`; its frame is at `+0x78` (GetCameraHeading `0xAB60E0` reads the heading
  with `0x4C5F20`; forward = `(-sin h, cos h, 0)`, so h = 0 looks along +y, h > 0 turns counter-clockwise).
- The in-match (isometric) camera is the class with vtable `0x15F8650` (ctor `0x96AD40`, alloc 0x334 in factory
  `0x961A40`, option `IsometricCamera.TargetPositionLerpScalar`). Its yaw is an angle smoother at `+0x38`
  (ctor `0x849F00`, set `0x849F40`, lerp `0x84A070`, get `0x849F80`), in **degrees** (`Angle` ctor `0xAF3C20(v, 0)`:
  degrees, fmod 360; `(v, 1)` = radians). Default yaw value: `+0x28` (ctor: 0.0; also read by the state unpack
  `0x969370` / `0x969C27`).
- Camera rotation = `Euler(heading = -yaw, pitch, 0)` (`0x967B00`, `0x967F1C`, `0x968059`: `0xAF29F0` -> `fchs` ->
  `0xAF2D00`). `0xAF2D00` uses sinf/cosf (`0x134D82A` = `__libm_sse2_sinf`, `0x134D836` = cosf): z = sin(h/2), the
  same quaternion convention as the cinematic keys. So **camera heading h = -yaw**.

## 2. Where the yaw comes from: property 0x1000011E on the followed entity (C)

- `0x1000011E` (f32, kind 0x09, net group NetPredictedSharedVisually): no record in any pack carries it (full
  scan of `rp/*.rp` for `key | key | value`), so only the server sets it.
- Activation `0x96A930` (vtable +0x74): yaw = `param+0x78` when the flag `param+0x74` is set (camera hand-over),
  else **the followed entity's `0x1000011E`** (`0x54FBD0(entity, 0x1000011E, &v)` at `0x96AABF`), else `+0x28`;
  then `0x849F40` on `+0x38` (`0x96AAF3`). Done once (`+0x2B0`).
- Followed entity: `+0x314`, else handle `+0x1D8`, else the local player's link `0x100005E8` (`0x85C150`) — our
  champion (we send `0x100005E8` / `0x100000CF` = champion).
- Target change `0x968DA0` registers watchers for `0x1000011E`, `0x100003A7`, `0x100000FA` on the new target and
  re-reads `0x1000011E` (`0x968E81`). Watcher `0x968F30`: on a `0x1000011E` change it calls vtable +0x1C =
  `0x9677F0` (Angle(v) -> `0x84A070`, smooth turn). `0x100003A7` (f32) sets `+0x4C`, the yaw smoother's speed (P).
- The script node 0x1000011E (`0x97C520`, `script_nodes.py`) is another namespace.

## 3. What each map expects (C data, P inference)

Intro cinematics end on the gameplay view (they blend into it):

| Cinematic | Last camera key | Heading h | Implied yaw |
|---|---|---|---|
| Tutorial 1 intro `0x35000026`, cam `0x10000015` | (12.3, 53.7, 213.8), pitch -36 | **-45.1** | +45 (diagonal) |
| Crime Alley intro `0x3500003C`, cam `0x10000010` (cut 240) | (52.2, 69.7, 204.7), pitch -20 | **0.0** | 0 (straight) |

Our tutorial screenshots (reverse-engineering.md section 11: screen-up = world (0.63, 0.78)) give h ~ -40, i.e.
yaw ~ 45, and the same diagonal is seen in Crime Alley with no 0x1000011E sent: with yaw 45, from the blue start
(5, 77.5) the red base (+x) is up-right, as the tester reported. So our client's yaw is ~45 in both maps, which is
right for Tutorial 1 and wrong for Crime Alley (P: the original server sent 0x1000011E per map / team).

## 4. Ranked fix

1. **(C mechanism, P value)** Send `0x1000011E` f32 (kind 0x09) on the **champion** (event 0x6 `set_property`, after
   the intro cinematic ends, and in the champion's creation properties): **0.0 for team 1** (straight, blue base on
   the left; matches the CA intro's last camera), **180.0 for team 2** (G: own base on the left). A later change
   turns the camera through `0x9677F0`. Keep it in config (`[ics] match_camera_yaw = {"1": 0.0, "2": 180.0}`); for
   the tutorials send nothing (or 45).
2. (P) If 0.0 changes nothing (the 45 comes from a hand-over param, not `+0x28`), resend the property after the
   intro's end (the watcher applies any change), or try -45 / 315.
3. Not it: camera records `0x21` (lens: near 0.04, far 2000, FOV 45-60; type 4 = `0x21000014/15/23/24`, no yaw),
   gmCameraSystem `0xA56850` (places its own camera entity: pitch/bank zeroed by `0x4C7840` / `0x4C78F0` with
   angle 0 `0x1B77950`), landblock orientation (positions are landblock-local, axis-aligned).

## 5. Verify with diag (open)

Breakpoints that print the yaw (xmm0 / float at `[ebp-8]` / `[ebp-0xC]`): `0x96AAC7` (activation value),
`0x9677F0` arg (property change), `0x9696CA` / `0x969C27` (state unpack, `[edi+0x28]`). Expect 45 in the current
Crime Alley run, 0 after the fix.
