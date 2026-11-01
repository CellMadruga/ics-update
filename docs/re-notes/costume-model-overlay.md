# Costume shows the base model over it ("model over model"), 2026-10-24

Tester (fase3-hj..hl): picking a Gaslight Batman costume (Samurai `0x400003C7`, `0x40000549`) in PvP vs AI shows the
base Batman over the costume. Static reads of the packs (`ics/rp.py`, scratch scripts costume1-8.py) and the client
(Ghidra). C = confirmed, P = probable, O = open.

## 1. What a costume is in the data (C)

A costume is a **full replacement**, not "base + swapped parts":

| | Base `0x40000086` (pack `0xA0000076`) | Samurai `0x400003C7` (pack `0xA000010C`) | `0x40000549` (pack `0xA0000183`) |
|---|---|---|---|
| template | `0x49000086` (no own 0x2E ref; world state via 0x510) | `0x490003C7` -> world state `0x2E000A86` (+0x1C28) | `0x49000549` -> `0x2E000C94` |
| world state -> .entity | `0x2E0001B2` -> `0x2D000115` | `0x2E000A86` -> `0x2D00089E` | `0x2E000C94` -> `0x2D000A73` |
| .entity -> 0x19 / 0x16 / 0x17 | `0x190001C4`, `0x160000E5`, `0x170000DB` | `0x19000997`, `0x16000D4E`, `0x17000BB4` | `0x19000BB1`, `0x16001247`, `0x17001019` |

DIDs present in both the base and a costume pack: only `0x18000302`, `0x1800054B`, `0x18000A7A` (particles),
`0x1D0003AB` (8-byte table), `0x36000009` (ragdoll). Bounded by their record starts, all five are **byte-identical**
in the three packs. No costume record references any base-pack DID (`0x40000086`, `0x49000086`, `0x2E0001B2`,
`0x2D000115`, `0x160000E5`, `0x170000DB`); hits only inside texture bytes (noise). Both templates reference the same
parent-pack records (`0x1D000064`, skill scripts `0x34000037-3B/48`, `0x400005C3`, `0x40000462`, textures
`0x13000372-77`). So loading the base pack next to a costume pack cannot change the costume's model through a DID
collision ("last pack wins" is irrelevant here).

## 2. What the server sends (C, traffic 2026-10-23 23:11 and 2026-10-24 00:53)

- 0x20AF (23:11:43): `0xa00002e5 e6 e7 0xa0000116 0xa0000073 0xa000022e 0xa0000122 0xa0000112 0xa000010a 0xa000010c`;
  champions `0x400003C7 0x400003B2`. No `0xA0000076`.
- After 0x20AF no server message carries the base variant: the champion create, link and "objects again" carry only
  `0x400003C7` (00:53 Supergirl match: only `0x40000E87` after 0x20AF). The base DID appears only in the lobby's 0x2029
  slots before the costume pick (picked + locked at 23:11:27-28, 0x204B at lock, costume picks at 23:11:30-31).
- Champion 0x7D2 = `0x1D0000E2 E1 E8 EF 1A1 1F6 064 3AB 527` (costume's world-state table `0x1D000527`; correct).

## 3. Client paths that load a base model pack outside 0x20AF (C)

- `0xA6FCD0` "gmCCharacterManagementSystem::LoadCharactersHeavy" (callers `0xA75B80/BA0/BC0`, profile / collection
  character selection; finished in `0xA60A60`): loads value[2] (heavy = model pack) of the 0x20ED entry for the
  characters at `+0xF4` and `+0xF8` through `0xA56410` -> `0x866540`; the references live in the manager's list
  `+0xDC`, not released by the match load.
- `0xA3E180` "RecvNotice_Scorecard_LoadCharacterHeavyOnly": the scorecard loads the played champion's model pack.
So `0xA0000076` can stay resident in the client's DB during a later costume match (P for the tester's session).
Harmless by itself (section 1).

## 4. Remaining hypothesis (P/O)

The overlay must be a second visual instance. The champion object is created at client load 35 % (23:11:48, before
the last pack of 0x20AF, the costume's model pack, has loaded: `local_champion_pack_last` puts it last) and the full
create is sent again at link (23:11:50), at load complete (23:11:55) and at `idle_resend`. With the base variant both
instances would coincide and be invisible (Tutorial 1 never showed it); with a costume, an instance built while
`0x400003C7`'s records were absent could fall back to a resident model (section 3). O: the client's fallback when the
class record is missing at creation, and whether a re-create of a live IID builds a second visual.

## 5. Proposed fix (P), in order of test

1. Create the champion only after the packs have loaded (on the client's load-complete notice or >= 80 %), and do
   not send a second full create for the same IID (send the bundle/changes instead): new `[ics]` keys, old behaviour
   restorable.
2. `local_champion_pack_last` false (the collision it guarded against is identical bytes, section 1) and put each
   champion's model pack in 0x20ED value[0] so `LoadMatchData_` (`0xA99460`) loads it before the server list.
3. Diag to settle section 4: break on the entity-visual build for IID `0x0200000000000002` and log the .entity
   (0x2D) DID each time; two builds (`0x2D000115` and `0x2D00089E`) confirm the hypothesis.
