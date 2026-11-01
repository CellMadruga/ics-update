# Master plan v2 — from the full survey of the install (2026-10-22)

Built on every survey note in this folder. First round (2026-10-21): `actor-creation-and-environment.md`,
`protocol-server-to-client.md`, `protocol-client-to-server.md`, `script-nodes-names.md`, `db-types.md`,
`tutorial-data-inventory.md`, `maps-encounters.md`, `shop-items-inventory.md`, `champions-all.md`,
`progression-meta.md`, `targeting-and-relations.md`, `movement-collision-fog-map.md`. Full survey (2026-10-22):
`install-inventory.md`, `script-nodes-complete.md`, `protocol-complete.md`, `units-and-ai.md`, `maps-complete.md`,
`client-scripts-and-ui.md`, `properties-complete.md` (+ `.tsv`), `account-systems-data.md`, `cinematics-vfx-audio.md`.

## What the client data holds and what only the original server had

| Area | In the data (decoded) | Never in the client: the server must author it |
|---|---|---|
| Install | 1 602 files, 616 packs, 59 record prefixes; 9 packs the exe always loads | — |
| Properties | all 3 822 descriptors (master table 0x32000000): kind, container, network mode, defaults | names (only 37 in the UI) |
| Protocol | 438 event ids, 336 server events, 44 notices, 12 connection packets, all client senders | — |
| Server scripts | 875 / 875 decodable with 4 decoder fixes; 325 node classes catalogued | the 248 node classes the runtime lacks (to implement) |
| Formulas 0x3B | 276 / 277 decodable: stat curves, unit level by time, XP and credit rewards, bounties | — |
| Champions | 54 / 156 variants, kits, stats per level, loadouts, Stolen Powers (unlock at level 5) | roster status (free / owned) |
| Units | 356 classes: stats, growth, attacks, rewards, flags | AI (minions, jungle, turrets, bots): only Starro's parasite script is a full example |
| Maps | 6 map packs, navmeshes (2 parser fixes), start points, lane mouths, core pedestals, Crime Alley structure sites, cinematics, packs per map | wave composition / timers, jungle camps (Gotham Divided), turret count per lane (GD, CC) |
| Shop / account | 228 artifacts, 162 augments, 172 mods, 192 achievements, 179 reward sets, login calendar, accolades, icons, ranked tiers | prices, XP per match, Merits, XP curve, boosts / bundles |
| Client logic | script library 0x39000001 (159 classes); GM_Advancement handlers registered by RPC `0x9F` msg `0x81A1000B` | — |
| UI | 82 Flash movies, 28 managers, what each screen needs | — |
| Presentation | 30 cinematics, 1 323 scriptlet tables, 167 Wwise banks, lighting node 0x1000009C | when each cinematic plays |

## Build order

1. **Fixes found by the survey** (small, unblock a lot):
   - `ics/navmesh.py`: cell count from the pair at +0x98; big-endian blobs (Gotham Divided).
   - `tools/script_decoder.py`: fixes A-D (headers, expressions 0xC / 0x10, bool defaults, counts >= 128) -> all
     875 scripts; runtime: 0xC = x - 1, 0x10 = short-circuit OR, `DEFAULT_WORDS`, 0x33 negate, 0x41 rotate.
   - `ics/records.py`: entries `key | 0x5...`, inline string form, 8-byte kinds 0x04 / 0x07 / 0x0F / 0x14.
   - `Data.unit_stats`: the level-scaled list 0x1000031A; unit level = clamp(floor((t + 90) / 90), 1, 100).
   - Record headers 1 (seven encounter templates, achievements).
2. **Skill ranks without exe patches**: send event 0x9F msg 0x81A1000B to the player; answer the client's
   0x81910003 with 0x81910001 (runtime test first, diag breakpoint 0x962E00).
3. **Script runtime**: the top unimplemented nodes (0x100000B1 OnAttributeChanged, 0x10000008 AddAttributeModifier,
   0x100000A7, 0x10000015, 0x10000155, 0x10000177, 0x1000013B in lists, 0x10000102, 0x10000040, 0x100000DF): every
   champion, Stolen Power, item and status.
4. **Formulas 0x3B in the server**: XP, credits, bounties, unit stats per level from the data instead of `[ics]`.
5. **Tutorial 1 polish** (tester feedback) and the other tutorials' flows (objective lists 0x48000E3B /
   0x48001150, encounter script 0x34000628).
6. **Menus**: amplifier sets (0x2090 / 0x20C7 / 0x204A / 0x2052; client 0x200D / 0x20FC), Stolen Power picker,
   profile header (0x2190 / 0x2154 / 0x2081), achievements (0x212E -> 0x211F, 0x2124 -> 0x2125), leaderboards,
   LeaveQueue 0x20C3 -> 0x20E0, end-of-match scorecard (0x2045 ...), rewards (0x219D).
7. **PvP**: structures at the data's anchors, minion waves from lane mouths, unit AI modelled on Starro's parasite
   script, bots from the pools and default loadouts, win conditions; packs per map from maps-complete.md.
8. **Social** (friends, party, chat, custom match, ranked) last.

Each step: tests, catalog / reverse-engineering / CHANGELOG entries, one build tag, then the tester.
