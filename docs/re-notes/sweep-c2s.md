# Sweep: client -> server events that `ics` does not handle (2026-10-25)

Sources: `ics/session.py` HANDLERS (line ~1935) and `ev_notice`, `logs/unhandled.log` (runs 10:33 and 11:25,
2026-10-25), `logs/traffic.log`, `protocol-client-to-server.md`, `protocol-complete.md` §2.1/2.2, REA/Ghidra on
`InfiniteCrisis.exe` (VA, base 0x400000). New in this sweep: 0x20D1 field order, 0x212C trigger (after every
purchase), 0x20EA slot 4 / R usage, 0x00DA from minions (0x81... entities) while playing.

## 1. Seen in today's unhandled.log

| id | count | name | sent when | layout | expected server reaction | prio | conf |
|---|---|---|---|---|---|---|---|
| 0x20BE | 442 | profiler stat | match end (`0xa97ea0`) | 5 u32, wstr parent, wstr stat, 10 f32 | none (telemetry) | P3 | C |
| 0x20B4 | 210 | GPU-tagged profiler stat | match end (`0xa98200`) | u32 1, GPU vendor/device, 2x(w,h), f32, wstr, wstr, 10 f32 | none | P3 | C |
| 0x214F | 95 | render counters | match end (`0xa98550`) | wstr parent, wstr stat, 5 f32 | none | P3 | C |
| 0x20EA | 25 | skill script event | entering / leaving targeting of a slot (`0xa26420` -> `0xa23510(agent, slot, &0x10000023)`); also order API callers `0xa70030`, `0xa70600`, `0xa85da0`, `0xa8a270`, `0xa8b0b0`, `0xa33ac0/0xa33c90` | u32 slot, list<u32> events, u8 0 (log: slot 1 and slot 4, [0x10000023]) | in HANDLERS but `skill_client_events=false` -> logged unhandled. The original server raised it on the server copy of the slot's skill script only (Deadshot R waits 0x10000023; Batman scripts broke when every script got it). Raise only on scripts that have a transition waiting for that event | P1 | P |
| 0x212C | 15 | ChangeArtifactSkillSlotMapping | load complete and ~100 ms after every 0x208B purchase (after our 0x20E2), Upgrade listener `0xa5ea70` | list<u32> SkillSlot ids = inventory index + 10 (log 6 x 10..15) | store the mapping (inventory slot i -> SkillSlot 10+i, used by 0x20EE command 2 slot 10..15 = artifact active); optional echo S2C 0x212B list<u32> to the champion | P2 | C layout / P reply |
| 0x20D1 | 14 | target-of-interest changed | `0xa5d250`: local player's selected target (`obj+0xd8`) changes; the client sets 0x100000FA / 0x10000029 on old/new target locally | u64 old target, u64 new target (log `0 -> 0x02..011e`, `0x..011e -> 0x..0120`, `x -> 0`) | none required; server may track the player's target (bot AI, "targeted" info for other clients) | P3 | C |
| 0x00DA | 10 | networked scriptlet request | scriptlet runner `0x628bf0`: networked scriptlet (flags 4+2) on an object the client does not own | u64 entity, u8 DID high (0x10), compact DID low, u8 run flags 0x0E, u8 mask 0x02/0x03..., u32/u8 fields, u64 originator (= entity), ..., f64 unix time. DIDs read: loading 0x100000EB on 0x02..0100/0101; playing 0x1000005D and 0x1000006B pairs on minions 0x81..0068/0069/0A32/0389 | re-broadcast as S2C 0x8D (start scriptlets, same DID/params) to every client but the sender has already decided not to run it -> without it those entities miss the scriptlet visuals | P1 | P |
| 0x211B | 8 | entity attached | `0xa9f9f0` / `0xa9e080` | u64 (0x02..01 then 0x02..02) | none | P3 | C |
| 0x20D3 | 8 | controlled agent changed | `0xa8d5e0` / `0xa8d680` | empty | none | P3 | C |
| 0x207A | 4 | world-entry flag | `0xa23140` | u8 | none | P3 | C |
| 0x00CC | 4 | level loaded | `0xa097a0` (+10 %) | u64 account character | none | P3 | C |

Notices (0x2) without an ics reaction outside PvP: 0x10000207 (agent linked), 0x10000204 (entered match) -> none
needed. 0x100000D2 / 0x100002AD / 0x10000137 / 0x10000454 are handled only by `ics/match` (PvP); the tutorial
director ignores them (fine; no HUD timeline there).

## 2. Not in HANDLERS and not seen today (trigger not used in these runs)

| id | name | sent when | layout | expected reaction | prio | conf |
|---|---|---|---|---|---|---|
| 0x20AB | hold position | InputAction_Hold (1) / stop or cast (0), `0xa0abf0`, `0xa404d0` | u8 | stop the champion and suppress auto-acquire while 1 | P1 | C |
| 0x2139 / 0x213A | camera temp-lock / toggle lock | `0xa30e70`/`0xa336b0`, `0xa30df0` | u32 encounter, u8 | none (tutorial camera step may wait) | P2 | C |
| 0x2138 | objective record from script node 0x10000060 | `0xab6e30` when target obj +0xB0 mode 2 | u32 node arg, u32 char DID, objective record | update the objective (S2C 0x2009) | P2 | P |
| 0x00DC | performance report | handler of S2C 0xA8 (`0x633170`) | u64, buckets | none (only if we send 0xA8) | P3 | C |
| 0x009B | hover/selection changed | `0xa4ecc0` | u32, u32, u8 | none | P3 | P |
| 0x00D2 / 0x0112 / 0x00C0 / 0x011B / 0x00C1 / 0x0098 / 0x00FD | script natives -> entity message | natives 0xC20003-0xC2000D, 0xC50001/3/A/B, 0xA60002, 0xBE0004/11 | u32 message, u32 len, blob | route like 0x9F to the entity's server script | P2 | P |
| 0x2170 | coaching tip seen | `0xa1d930`, `0xa5e2d0` | u64 lobby, u32 tip | none | P3 | C |
| 0x2140 | (in HANDLERS as conversation done) | `0xa676b0` | u32 | - | - | - |
| 0x201A / 0x2097 / 0x214D | empty UI events | `0xa80cd0` / `0xa0e5b0` / `0xa0aab0` | empty | unknown; log quietly | P3 | U |
| 0x00EA / 0x0121 / 0x012B / 0x0095 | object events | `0x62b450`, `0x62de20`, `0x62c030`..., `0x420b90` | u32,u32 / u32 / u64,u64,f32,vec / empty | unknown (0x12B: agent -> target with 0.1 f32, likely a client prediction report) | P2 | U |
| 0x2112 / 0x20E5 / 0x20DF / 0x2099 | social / lobby text (names + account id, system lines) | `0xa22ce0`, `0xa227c0`, `0xa0d270`, `0xa0d310` | strings / u32 token | chat or lobby system-line reply | P2 | P |

## 3. Top handlers to add (in order)

1. 0x00DA -> S2C 0x8D on the entity (same DID, flags, originator, start time) to all clients.
2. 0x20EA -> raise on the slot's server skill script only if a state waits for that event (Deadshot R).
3. 0x20AB -> hold: stop + no auto-attack; clear on 0.
4. 0x212C -> store artifact SkillSlot map; echo 0x212B.
5. 0x00D2 / 0x0112 / 0x00C0 family -> same path as 0x9F.
6. 0x2138 -> objective update 0x2009.
7. 0x20D1 -> store player target (bots / later PvP).
8. 0x2139 / 0x213A -> quiet, expose to the director as step triggers.
9-15. Quiet (no reply, no unhandled line): 0x20BE, 0x20B4, 0x214F, 0x211B, 0x20D3, 0x207A, 0x00CC
   (and notices 0x10000207 / 0x10000204 in director mode).
