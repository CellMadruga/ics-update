# Full decompilation of the client (2026-10-22): index

The whole client was decompiled with Ghidra 12.1.4 headless (`re-work/scripts/DecompileAll.java`, outside the
repository: decompiled game code is never committed). InfiniteCrisis.exe: 60 529 functions to C (2 failed),
`re-work/decomp/c/<64 KB block>.c`, `functions.tsv` (callers / callees), `strings.tsv` (27 973 strings with their
functions). The launcher and the game's own DLLs: `re-work/decomp-other/<name>/` (turbineclientlauncher 5 137,
TurbineLauncher 2 465, turbinebrowser 800, DeltaPatch 6 432, D3D11 / D3D9 GraphicsCore 522 / 485, processtexture
408; corestrings has no code). The UI: 84 Scaleform movies exported with JPEXS FFDec 26.4 to `re-work/ui-as2/`
(56 922 .as files, 992 library classes). Third-party libraries (Qt, CEF, ffmpeg, Bink, OpenSSL, ICU, TBB) were not
analysed.

| Note | Subsystem |
|---|---|
| `full-maps-world.md` | map load order, landblocks, statics by type, ruleset filtering, environment, audio, minimap, what the server spawns per map |
| `full-match-mechanics.md` | modes, clock, death / respawn, scoreboard (notice 0x1000005B), kill feed 0x217A, surrender 0x10000454-456, structures, waves, objectives, map events; the rules the server must author |
| `full-combat-skills.md` | cast pipeline, CanActivate, attributes and modifiers, vitals, statuses / CC, missiles, hotspots; specs for every script node `ics` lacks; bugs in `ics` |
| `full-protocol.md` + `full-protocol.tsv` | 441 events (505 rows with notices and packets), connection layer, every flow as a message sequence |
| `full-entities-engine.md` | entity struct (64 component slots), factory steps, component gates (PerceivedType, mobility, 0x7D2), property lookup, per-kind property table, graphs, VFX, Wwise, DB loader, clock |
| `full-account-social.md` | login (AuthSelect, BYPASS), account data, store, loadouts, achievements, ranked, contacts / custom match vtables, chat, preferences, per-account persistence |
| `ui-complete.md` | every UI class, 315 C++ -> Flash notices, 420 Flash -> C++ calls, every screen's data |
| `client-movement.md`, `client-status-effects.md`, `client-scriptlets-graphs.md`, `client-cinematics-matchend.md` | the first four targeted subsystems (same day) |
| `object-update-bundles.md` | (2026-10-28) event 0x4 to a live object: 0xF2 no-op, 0xBC = a diff that removes the own net-1 / 3 ids it omits, 0xB0 one more state; 0x6 / 0x86; MasterProperty's network modes; ics's delta update path (section 13, fase3-if) |

## Conflicts between the notes (to settle in game, diag breakpoints)

| Item | Note A | Note B | Evidence so far |
|---|---|---|---|
| champion pick | `full-protocol`: 0x2102 SelectCharacter (C, sender 0x8864b0) | `full-account-social`: 0x20E4 (lobby vtable 0x160adb8), 0x2102 = custom-match draft toggle | `ics` handles 0x2102; the tutorial never picks |
| 0x2026 / 0x205A | `full-protocol`: Draft_RequestTrade / Draft_TradeResponse | `full-account-social`: custom match assign team / cancel | - |
| 0x2140 | `full-protocol`: "HUD element state" (G) | tester logs 2026-10-22: `u32 instance` after each 0x2001 conversation has played | confirmed in game: conversation finished |
| component +0x58 | `full-entities-engine`: CDestructionComponent | `protocol-server-to-client`: appearance | re-check the handler |
| damage-stage scriptlet field | code 0x10000074 | `units-and-ai.md` 0x10000174 | re-check |
| 0x6 body | ics / `reverse-engineering.md` fase3-gd: `u8 0 \| u32 id \| packed id \| value` (a table entry) | static read (`object-update-bundles.md` 13): serializer 0x445530 = base u8 0xB0D380 + 0x509740 (packed id + value), no u32 | ics's form works in game (2026-10-23 15:00 diag --target: a 0 -> flags toggle by 0x6 set the unit cache); what reads the u32 is open |

## What only the original server had (to author)

Respawn timers, wave timing and composition, siege cadence, structure layout of Gotham Divided / Coast City,
jungle camps and respawns, capture rules (Gotham Heights drain, Coast City relay -> Device, Gotham Divided
beacons), meteor / Device schedule, passive gold, starting gold, XP curve, surrender threshold, mitigation / crit /
lifesteal formulas (assumed forms in `full-combat-skills.md` section 2), prices and currency amounts. The user's
minion prototype (`sistema_suiditos_moba.py`, LoL-style numbers) can be a skeleton for waves once the numbers come
from the data (metres, unit speeds, formulas 0x3B).
