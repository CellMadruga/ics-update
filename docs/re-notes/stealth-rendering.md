# Stealth brush: what the client needs to draw a hidden champion (static analysis, 2026-10-28)

Context: Crime Alley, a champion walking into a stealth strip. `ics/match/match.py` `_stealth_tick` applies status
`0x4800028C` -> script `0x340001CF`; the tester sees no change on screen. Sources: byte scans of
`InfiniteCrisis.exe` (capstone / pefile), Ghidra via REA, the packs read with `ics.gamedata` / `ics.rp`, and
`logs/traffic.log` + `logs/server.log` of the 2026-10-28 09:33 session. C = confirmed by code or data, P = probable,
O = open. Addresses are VAs (image base 0x400000).

## 0. Answer in short

- The client never reads `0x100007BF` (IsHidden) and never runs `0x1000011E`. Both are server-side only. No property
  or attribute message for them changes anything on screen (C).
- What the owner (and allies) see is the scriptlet **`Vfx_Status_Stealth_Active 0x10000648`**. It sits in the
  generic champion table **`0x1D0000E1`**, which every champion's `0x7D2` lists, and it attaches the purple particle
  **`0x18000504`**. The original "translucent" look is that particle (P). The client has no entity-level
  "draw translucent" switch from the network: the render bucket bit for translucency comes from the material (C).
- "Vanishes for the enemy" is the server's job: send or withhold the entity per team. The tool for that is **0x90F
  Hidden** (bool), as `World.fog` already does for units (C mechanism, P for its use here).
- Our server *does* send `0x10000648` to the champion (C, traffic.log). Two things on our side keep it from
  showing:
  1. The runtime often goes to the revealed state S1 instead of the hidden state S2, so no 0x8D is sent at all. In
     the log, 3 of 6 entries never reach S2.
  2. When S2 is reached, it is left after 0.5-2 s (combat reveal).
  See section 4.

## 1. Who reads 0x100007BF and the other stealth attributes (C)

| Item | Evidence | Meaning |
|---|---|---|
| `0x100007BF` IsHidden | **0 occurrences** of bytes `BF 07 00 10` anywhere in the exe (`.text` and `.rdata`) | no client code reads it; the `AddAttributeModifier` mirror (client execute `0x992A70`) stores it, and nothing uses it |
| `0x100007BF` in the packs | about 600 hits, nearly all in entity templates `0x49......` as `(0x100007BF, 0x500007BF)` = a declared attribute with no value, plus the 0x34 scripts that use it (`0x340001CF`, `0x340004AB`, `0x34000304`, `0x340001B5`) | declared on every combat template; no scriptlet table (0x1D) tests it (1 hit in `0x1D000678` is a template header that follows the table) |
| `0x1000011E` (BrushIID node) | vtable `0x15FC1DC`, slot 10 (client execute) = **`0xAB4D80` = `ret`**. Compare `AddAttributeModifier` `0x15FE30C` slot 10 = `0x992A70` and `StartScriptlet` `0x15FE16C` slot 10 = `0x9CE300` | server-only. In `0x340001CF` it runs `[1 0]` on entering the hidden group and `[0 0]` on leaving it, with BrushIID = the brush. Reading (P): "hide SELF from everyone not inside BrushIID" |
| `0x10000B4A` (P: stealth flag attribute) | one use: `.rdata 0x15FE680`, pushed at `0x9D0283` in **`0x9D01D0`** (target validator), `0x974940(target, &iid, 0x10000B4A, default 0)`, only when `0x861A10(caster, filter)` is set | a target filter "may target stealthed units"; not a renderer |
| `0x100006F3` (Revealed / always-visible) | `0xA9DE81`, `0xAA9C87`, `0xAAA73A` (fog, `fog-vision-runtime.md` 4) | the fog evaluator treats an entity with `0x100006F3` as visible. `0x340001CF` uses `HasFlagAttribute 0x1000006A [0x100006F3]` in its state transitions: a Revealed champion leaves the hidden state |
| `0x100007C0` | `0xA9DE4C`, `0xAAA714`, `0xAAE7AF` | blind-type flag of the *viewer* (fog). Unrelated to stealth; never send it |

Render side (C):
- The render-component property listener **`0x624490`** maps entity properties to render flags. `0x2A1`, `0x90F`
  and `0x76A` -> `0x61CB30` -> visible bit 1 / render `+0x220` bit `0x800` (drawn when `0x2A1 && 0x76A && !0x90F`).
  The others: `0x7A` -> render `0x4000`, `0x79` -> `0x20000000`, `0x4A8` -> `0x400`, `0x5F8` -> `0x200`,
  `0x924` -> `0x40000000`, `0x962 == 4` -> `+0x224` bit 1, `0x971` / `0x974` -> `+0x224` bit 8, `0x93C` -> render
  `+0x231`, `0x44E` -> component `+0x8C` bit `0x400000`. None of them is named "stealth"; none is touched by the
  stealth data.
- Bucket sort **`0x756CD0`**: an object goes to the translucent list (`0x1B716A0`) when render `+0x220 & 0x20`. That
  bit is copied from the **material's** flag word (`0x77E840`: `[[+0x260]+0x70]+0xC4` bit 1 -> `+0x220 |= 0x20`).
  So translucency follows the material. It is not an entity property the server can set (C for this path; O whether
  another path exists, for example a scriptlet action that swaps material).
- `0xA9C0E0` / `0xA9C490` write `0x90F` locally (UI "hide all" toggles filtered by `0x10000B5B`), so the client does
  honour `0x90F` as "do not draw".

## 2. What the server must send (recipe)

### 2.1 Owner and allies: the shimmer (C data, P look)

- Key `0x10000648` Vfx_Status_Stealth_Active is the **last entry of table `0x1D0000E1`** (pack `0xA00000DF`, entry
  at file offset `0x141DB04`, right before the particle record `0x18000504` at `0x141DB24`). Every champion variant
  lists `0x1D0000E1` first in `0x7D2` (C, all 54 champions). Entry: `0x10000648 | 0 | 1 prop (0x479 = 99) | ... |
  particle 0x18000504`.
- Particle `0x18000504`: colours `ff7b7bd0` (purple), `207878b0` (purple, alpha 0x20), `ccffffff`, `66ffffff`;
  textures `0x17000303`, `0x17000687`, `0x17000724`, `0x170016DD`. This is the translucent purple look of the
  original video (P).
- `0x10000649` Stealth_Start and `0x10000647` Stealth_Stop are **not** in any champion table. They exist only in
  creature / object tables (`0x1D0002C8`, `0x1D0005B7`, `0x1D00012A`), so the client rejects them on a champion
  (`0x6279D0` table test -> `0x80070057`). Sending them is harmless; you can skip them.
- Send: event 0x8D on the champion, key `0x10000648`, a new run number, when the script enters its **hidden state
  S2** (sub-script `0x48000874` / `ActiveScriptHandle` -> `StartScriptlet 0x10000648`). Clear it when S2 is left:
  0x8D with the same run number and signal bit 1 (what `World.signal_scriptlet` already does). Our 09:34:53 /
  09:35:06 / 09:35:12 runs had exactly this shape (C, traffic.log lines 8357 / 8438).
- Bots and other players' champions: `World.scriptlet` filters non-local entities by `ent.scriptlet_keys`. Those
  keys come from `Data.scriptlets()`, and **`script_table(0x1D0000E1)` returns None** (the `ics.rp` parser does not
  recognise that table; also `0x1D0001A1` and every champion's own table, for example `0x1D000064`). So the shimmer
  is never sent for an allied bot (C). Fix (P): add `0x10000648` to the champion keys by hand, or teach
  `rp.script_tables` this table layout.

### 2.2 Enemies: not drawn (C mechanism, P use)

- 0x6 set property on the hidden champion, sent **only to clients on the other team(s)**: prop `0x90F`, kind
  `0x16` (bool), value `1` when the champion enters S2 (hidden and not Revealed). Send value `0` when it leaves S2
  (Revealed, attacks, leaves the brush, or an enemy enters the same brush, which is the BrushIID rule). Do not use
  `0x2A1` for this: the fog evaluator rewrites it about every 0.4 s (`fog-vision-runtime.md` 4).
- Same team / owner: never send `0x90F = 1` (the owner must still see itself, with the shimmer).
- Single player against bots: there is no enemy client. What matters is the server model: AI target search,
  turrets, `FindTargets` and the targeting validator must skip the hidden champion unless the attacker is in the
  same brush or the champion is Revealed. `IsStealthed` (`0x10000143`) is "has IsHidden flags and is in S2";
  `IsRevealed` (`0x10000144`) is "has `0x100006F3` or is in S1".
- Minimap: the enemy minimap reads the same entity, so `0x90F` (or not sending the position) also hides the icon
  (P, not traced).

### 2.3 What not to send

- No 0x6 for `0x100007BF` (the exe never reads it), and no `0x100007C0`.
- No status-list message is needed for the visual. The client mirror of `0x340001CF` (if 0x200F were sent) would
  only start the same scriptlet locally.

## 3. IsHidden value and hidden vs translucent (P / O)

- `0x340001CF` locals (hash, type, slot): IsHidden `0x7EFAFBE` (slot 0), BrushIID `0x9C9C944` (slot 8),
  HiddenHandle `0x609E1E5` (slot 16), StealthRevealed `0x7489594` (top level). `AddAttributeModifier(SELF)`:
  attribute `0x100007BF`, value = local IsHidden, op 3 (P: OR a flag set), handle -> HiddenHandle. The status record
  `0x4800028C` overrides no variable (its props are `0x1000072D`, `0x10000242 = 0x340001CF`, `0x10000063 = 10`,
  `0x10000334 = 0x8000`), so IsHidden keeps the script default. The default is a flag-set value (type 0xE / 0xF)
  in the record's variable block. A word `0x0101` at script field +1952 is the best candidate (O, not decoded).
  The client never needs this value.
- Transitions (C tree): hidden group ⇔ `!HasFlagAttribute(0x100006F3)` and `(GetAttribute[0x100007BF] & IsHidden)
  != 0`. Inside it: S2 (hidden, shimmer) / S1 (revealed). The difference between "translucent to self" and
  "vanished to the enemy" is not a client flag. It is a per-team decision of the server (`0x1000011E` with the
  BrushIID): the owner and allies get the scriptlet, enemies get `0x90F` (section 2).

## 4. Why the tester saw nothing (C logs, P cause)

- server.log: of 6 entries, 3 went S0 -> S2 and sent `0x10000648` (09:34:53.004, 09:35:06.391, 09:35:12.811), and
  each was stopped 0.5-2 s later by S2 -> S1. At 09:35:13 this followed the stun / hit script `0x34000130`. The
  other entries (09:36:27.7, 09:36:53.5) went **S0 -> S1 (T3) directly**, so no scriptlet was sent at all.
- So the runtime too often sees the champion as Revealed: `HasFlagAttribute 0x100006F3` true, or the IsHidden &
  flags test false after the mask. Check (P): what sets `0x100006F3` on our champion (an in-combat status from the
  basic attack or Grab), and that `(GetAttribute & IsHidden)` uses the same flag-set value the modifier added.
  Walking in out of combat should keep S2 for the whole stay.
- The 0x8D messages themselves were well formed (same 36-byte shape as the working `0x10000897`), and the key is in
  the champion's tables, so the client did attach `0x18000504` for those 0.5-2 s (P). A short window and a subtle
  purple shimmer during a fight explain "nothing visible".
- Diagnostic: with the game open, walk into a strip **without attacking** and wait 5 s. If S2 holds and still nothing
  shows, put a breakpoint on `0x6279D0` (`tools/diag.py --scripts`) for key `0x10000648` and check the return value.

## 5. The strip itself: purple hex vs our "white zones" (C data, P / G look)

- Hex mesh world state `0x2E000D37` (.entity `0x2D000AFD`, ctype 5): material `0x1600215E`, textures
  `0x130033A9` / `0x130033A8` / `0x130029F1` / `0x130033A7` / `0x170013D1`, tint prop **`0x7D1` = (0.737, 0.737,
  0.737) grey**, `0x4A8 = 1`, `0x2A4 = 1`, `0x7EB = 7`, `0x50F = 5`. On its own it is a light grey hex pattern: the
  tester's "white zones" (C data, P look).
- The purple comes from particle **`0x18000A57`** (pack `0xA00000FC`, colour `ff7878e1` = blue-purple; textures
  `0x17000303`, `0x1700059B`, `0x170008E8`, `0x17000B52`). Vfx_Active of the tile tables plays it (`0x1D000509` for
  ws `0x2E000D36`, `0x1D00050B` for ws `0x2E000D40`) together with the hex child `0x2E000D37`. Our config
  `stealth_tile_direct = True` (`stubborn-visuals.md` 3) spawns only the hex mesh and drops the particle, so the
  purple is gone (P).
- Fix (P): go back to Vfx_Active on the hotspot entity (`0x4000039D` / `0x40000405`, not the bare world state), with
  the yaw fix of `crime-alley-still-missing.md` 1. The earlier "+" and streaks were seen with tiles in the wrong
  orientation and as bare world states. Check them again before dropping the particle (G).
- Team / side: neither tile table has a `0x22` / `0x16` switch on `0x100007A2` or `0x1000009C` (C,
  `stubborn-visuals.md` 3), unlike the base gate wall. The brush colour is the same for both teams.
- Length: the two classes differ only in the box (`0x4000039D` 4 x 2 m centred; `0x40000405` 4.5 x 2 m anchored at
  its +x end, visual offset -2.1). No scale property was found in either (O). A long diagonal strip is a row of
  tiles placed end to end along the strip's direction, all with the same yaw (P). The positions must come from the
  video (G).

## 6. Open

- O: the exact default of IsHidden (flag-set variable block of `0x340001CF`).
- O: whether a scriptlet action type (for example one of 0x1B-0x1E, 0x26-0x2F in `client-scriptlets-graphs.md` 1.6)
  swaps the champion's material to a translucent one. No such action is in the `0x10000648` entry. Its other words
  were not decoded past the particle.
- O: why `ics.rp.script_tables` cannot parse `0x1D0000E1` / `0x1D0001A1` / the per-champion tables.
