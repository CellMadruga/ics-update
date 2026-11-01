# Announcer lines by key, Atomic Green Lantern's shield, client disconnects

Static analysis 2026-10-25 (exe `InfiniteCrisis.exe`, VA, base 0x400000, Ghidra via REA; packs in
`C:\Infinite Crisis Server\rp`). Tags: [C] confirmed in code/data, [P] probable, [G] guess. Written incrementally.

## 1. Why 0x2001 announcer lines are silent in PvP

### 1.1 The 0x2001 path [C]

- Exec 0x8b2180 -> handler **0xa13b90**: resolves the message's first u64 (ics sends 0) through the object manager
  `[0x1b67258] vt+0x58`, then calls the dialog system `[0xa12d50()+0x1c]` **vt+8** with
  (entity, u32 mode, u32 key, speaker list, u8, 0, instance, -1.0f).
- The dialog system object is built by 0xa8ba40 (dtor 0xa87db0); main vtable **0x1604dfc**:
  vt+0 0xa8d0a0, vt+4 0xa67670 (0x2047), **vt+8 0xa7ff20** (0x2001), vt+0xc 0xa8e3a0, vt+0x10 0xa284f0.
- 0xa7ff20 = `conv = 0xa13c90(entity, mode, key); if (!conv) return 0; return 0xa77ae0(conv, speakers, u8, 0, inst)`.
- **0xa13c90** (the key lookup):
  - `mode == 1` (what ics sends): `if (byte [dialog+0x128] == 0) return 0` (**0xa13d11 / 0xa13d18**), else
    `0x85e210(key)` on the conversation catalogue at `dialog+0xF8` (24-byte entries, key first).
  - `mode != 1`: needs a non-null entity; `[[entity+0x108]+8]` must be in the list `[dialog+0xb0]` (count +0xb8),
    which indexes a catalogue in `[dialog+0xc0]` (0x3C each, loaded flag +0x38); 0xa8f640 adds them on demand.
- The catalogue at `dialog+0xF0` (DID +0xF4, table +0xF8, loaded +0x128) is filled only by **0xa35dc0** at
  encounter start from the encounter template's **0x10000B21** (0xa35dc0 runs with ecx = dialog+8, so its +0xEC /
  +0xF0 / +0x120 are dialog +0xF4 / +0xF8 / +0x128), and by 0xa13e20 (only caller 0xab8130, front end). In the
  same function 0x10000803 -> channel 1 set (`[dialog+0xd0]+0x40`), 0x10000802 -> channel 2 set (`+0x7c`).

### 1.2 The data [C]

Template 0x10000B21 / 0x10000802 / 0x10000803 per encounter (`Data.template_properties`):

| Encounter | 0x10000B21 (conversation catalogue) | 0x10000802 | 0x10000803 |
|---|---|---|---|
| Tutorial 1 0x40000991 | 0x40000CB7 | 0x40000B69 | - |
| Tutorial Advanced (CA 1vAI) 0x40000CA6 | 0x40000CE3 | - | - |
| CA v AI 0x40000C82 | **none** | 0x40000D4C | **none** |
| CA 0x40000E68 / 0x40000E74 | none | 0x40000D4C | 0x4000047A |
| GD 0x40000399, CC 0x40000270, GH 0x4000013E | none | own set | 0x4000047A |

The line entries (`f32 1.0 | f32 x | u32 key | hash | ...`) of the keys sent are inside the announcer **set**
records, not in any conversation catalogue: in CA's layout pack 0xA00002E6, 0x9C / 0xBB / 0x97 / 0xAE / 0xAD sit
in record 0x4000047A (header 0xC8A6C, lines 0xC9584-0xC9640) and 0x29C-0x2A1 in record 0x40000D4C (header 0x7FD84,
lines 0x80247-0x80332). Same layout in CC's 0xA0000162.

**Failure branch:** no PvP template has 0x10000B21, so `[dialog+0x128] == 0` and 0xa13c90 returns 0 at 0xa13d18;
0xa7ff20 returns 0, nothing plays. Even with a catalogue, the lookup there is 0x85e210 (conversation entries),
while set lines are looked up by 0x85e1d0. Tutorial 1 works because its catalogue 0x40000CB7 holds its
conversations (0x250 etc.). Speaker / voice components are not involved.

### 1.3 The path that plays a set line by key [C]

0x2039 handler 0xa77da0 (args: flag, channel, PropTable), first branch: property **0x100003BD** (enum, value type
8 or 10) != 0 -> **0xa596b0(key, channel, now, list, 0)**: `[[dialog+0xd0] + channel*0x3C + 0x38]` must be set
(channel's set loaded), `0x85e1d0(key)` finds the line in that channel's set, 0xa0a960 builds it, then 0xa597b0
queues it. No match event and no team logic.

Channel 3's set is set by message **0x202A** (`u8 0 | u32 DID`, exec 0x8b2230 -> 0xa1b400: `[dialog+0xd0]+0xb8 = DID`,
loads it, flag +0xEC).

### 1.4 Fix

- Lines of the encounter set (CA 0x29C-0x2A1, CC 231 / 247 / 233, ...): send 0x2039 `u8 0 | u32 flag 1 | u32
  channel 2 | PropTable{0x100003BD (KIND_ENUM) = key}` (`M.announcer` with 0x100003BD in place of 0x10000806).
- Lines of the shared set (0x9C / 0xBB / 0x97 / 0xAE / 0xAD): channel 1 when the template has 0x10000803 (E68 /
  E74, GD / CC / GH PvP). For CA v AI 0x40000C82 (no 0x10000803) send once, after load complete,
  **0x202A `u8 0 | u32 0x4000047A`** (record is in 0xA00002E6, loaded) and play them on **channel 3**. Sending 0x202A
  on every map is harmless and makes the shared lines independent of the template.
- Keep 0x2001 for catalogue conversations only (tutorials). Config: `[ics] announcer_line_mode = "2039key"`
  (default) / `"2001"` (old).

Diag breakpoints to confirm: 0xa13d18 (`al` = byte [ecx+0x128], expect 0 in PvP), 0xa7ff39 after the 0xa13c90 call
(`eax` = 0), for the fix 0xa77da0 entry (edx/stack: flag, channel), 0xa596b0 entry (`[esp+4]` key, `[esp+8]`
channel) and its return (`al` = 1), and 0xa1b400 entry (DID of 0x202A).

## 2. Atomic Green Lantern E (Shards of Will): the shield sphere

### 2.1 What the server runs [C]

Status script 0x340002C3 (decoded tree, `tools/script_decoder.py tree`), enter chain in order: SetVariable
EffectDuration, SetVariable ShieldAmount = apply param 0x9F942E2 (the skill's AdjustedShieldAmount),
LoadSkillStats(SELF, stat 10, slot 3) -> BaseShieldAmount, **ShieldPercentage = (ShieldAmount - BaseShieldAmount)
/ BaseShieldAmount** (vt 0x15A9478 "-", 0x15A94E8 "/"), AddTempVital(ShieldAmount, SELF -> TempVitalHandle),
RunScriptlet(SELF, **0x10000886** Active, {0x1000033E = ShieldPercentage}), RunScriptlet(SELF, **0x1000088C** Start,
same), ApplyStatus icon 0x480007B7. Exit on 0x1000008C (shield broken) / timer: RemoveTempVital, RunScriptlet
0x1000088B End. ics runs this in that order (traffic 2026-10-25 10:38:30: vitals, icon, 0x886, 0x88C).

ShieldPercentage is the **bonus over the base shield** (the skill adds ShieldPerCharacter 0.2 / ShieldPerMinion
0.05 per target near AGL, capped by MaxShield 0.5), not the remaining fraction: 0.0 is the correct value when no
target is near. NullWorld sim of 0x480007A2 slot 3: ShieldAmount 50, Base 50, ShieldPercentage 0.0, one shield 50 on
vital 2 (C).

### 2.2 The table is reachable [P strong]

Pack 0xA0000150 offset 0x1F700: a table body `u32 6 | 0x1D0003CD 0x1D0003D1 0x1D0003D3 0x1D0003D6 0x1D0003D7
0x1D0003D9 | 1 | 7 | 0x10000128 ...`: the six "orphan" tables are the **bases** of AGL's champion table (0x1D0003CE,
named by template 0x7D2; `rp.script_tables` cannot read this body, so it showed no bases). That is how Smash
0x100008AB (0x1D0003D9) resolves, and 0x886 / 0x88C / 0x88B (0x1D0003D7) resolve the same way. Every DID the
scriptlets use (world state 0x2E000C89, sounds 0x18000762 / 813 / 814 / 815) is in 0xA0000150, which 0x20AF names.

### 2.3 What the scriptlets do [P]

- 0x886 Active (pack 0xA0000150 0x351E8-0x360D0): spawns world state **0x2E000C89** (the shard / sphere piece) at
  frame 0x12 (no gate), then again at frames 0x2F, 0x70, 0xB2, each gated `0x17 | 0x1000033E | thr | 0 | 4` with thr
  0.125, 0.25, 0.375: more shards for a bigger bonus. At frame 0x1A9 it runs 0x88B / loops on 0x886.
- 0x88C Start (from 0x35BC8): header `0x1000088C | 0 | 0 | 4 | 0x17 | 1 | 0 | 0x10000886` (it chains to 0x886),
  sounds 0x18000813 (frame 0x148, no gate), 0x18000762 / 815 / 814 gated at 0.125 / 0.25 / 0.375.
- So with ShieldPercentage 0.0 one piece and the base sound should still play: the value is not what hides it.

### 2.4 Most likely cause and recipe [P]

1. Order on the wire: a scriptlet sent to the same object replaces the running one and its attachments (meteor,
   fase3-hk). 0x88C arrives in the same tick right after 0x886 and kills it before frame 0x12; 0x88C then plays its
   own start and only re-enters 0x886 at its end (the original server probably sent both too, but its two 0x8D
   might have been one message or a tick apart: G). Recipe: send **0x88C only** and let it chain into 0x886
   (`[ics] agl_shield_start_only = true`), or send 0x886 0.1 s after 0x88C.
2. Pass the real bonus: ShieldPercentage = (AdjustedShieldAmount - Base) / Base, clamp 0..0.5 (already the VM
   result; check the skill's target count in game, the tester was near minions and got 0.0).
3. Show the shield amount: send it in 0x42 as the temp vital so the HUD bar shows it (0xAB1BD0 copies the second
   list into the vitals component +0x50; P that it is the shield layer).
4. Diag: break on the 0x8D scriptlet lookup for AGL's object (key 0x886 / 0x88C found or not) and on the
   replacement path (0x588A80 -> 0x57C4B0 signal) to see 0x886 stopped by 0x88C.

## 3. "Unable to connect to Match" and the closed connections

### 3.1 The string and its only caller [C]

The text is game table 0x2B000010, tokens 0x0529C505 ("Unable to connect to Match.") and 0x0E256657 (the long form
naming ports 9000-9036 / 5000-5036). The exe pushes both in one place: **0xa9af20**, the gmConnectionManager tick
(profile name "gmConnectionManager"):

```
if (cm[+0xD1] && now - cm[+0xD8] > 60.0 && cm[+0xC8] == 0) {     // 0xa9b0e0..0xa9b0f9
    if (!view_match [0x1b77138]+0xAC && !replay [0x1b77138]+0xAD) {  // 0xa9b0fb / 0xa9b104
        0xac5010(0x0529C505, 0x0E256657, 0x10000014);               // error dialog, 0xa9b127
        0xabc480(lobby[+0x4BC]);                                     // exit lobby + world teardown, 0xa9b134
    }
    cm[+0xD1] = 0; cm[+0xD8] = -1.0;                                 // 0xa9b143
}
```

- Armed only by **0x2016** (exec 0x8b8a90 -> 0xab9080, room check passed) -> 0xa9aa50(1): `+0xD1 = 1`, `+0xD8 = now`.
- Cleared only by 0xa9aaa0 (the game connection's "connected" path: clears it, sets +0xCE, 0xa964b0(5), loader
  0xa99e20) or when it fires. The 0x20AF handler 0xa99f00 does not clear it.
- `cm+0xC8` is set by 0xa964b0 (into the world, 0xa96607) and zeroed by the world teardown **0xa99b60**.
- 0xabc480 is the 0x2021 "DeliverNotifyPlayerToExitLobby" body (0xa99b60 teardown, UI 0x5F).

### 3.2 What happened on 2026-10-25 [C for the second case]

traffic.log: game connection 10:34:10 (connected status), then at launch 10:34:29.361 **0x20AF, then 0x2016**
(`lobby_transition_at_launch`, needed after champion select). That 0x2016 came after the connected status, so it
armed the watchdog and nothing cleared it. During the match `cm+0xC8 != 0` held it. At 10:41:42.280 the client sent
0x12D and tore the world down (`+0xC8 = 0`); the next tick the 60 s had long passed: dialog + 0xabc480, and the client
closed login and game 70 ms later. This is the fase3-ev watchdog again, brought back by the at-launch 0x2016.
The load-time case (~4 s after 0x20AF, 5th match) fits the same watchdog (armed > 60 s earlier, `+0xC8` is 0 while
loading) [P]; no exe fault path was needed to explain either, and the 0x956 / 0x2E00033F sky lead is not supported
by these logs (not traced further).

### 3.3 Fix

- Exe patch (icserver/patcher.py), keeps the clear and drops the dialog / exit: at **0xa9b102** `75 35` -> `EB 35`
  (context `E8 50 3D 02 00 84 C0 [75 35] E8 67 3D 02 00 84 C0 75 2C`). The jump lands on 0xa9b139 = after the
  0xabc480 call, so +0xD1 is still cleared. Then `python ic.py patch`.
- Server-only alternative: never send an accepted 0x2016 after the connected status (send 0x2016 with a u32 that
  fails the room check is not usable: then 0xab8ec0 does not run and the lobby never goes to loading). So the patch
  is the clean fix; config `[ics] lobby_transition_at_launch` stays.
- Diag: break 0xa9aa59 (armed), 0xa9b11d (dialog about to show), 0xa99d6b (teardown zeroes +0xC8).
