# Coverage sweep — consolidated backlog (2026-10-25)

One ranked list built from the six sweep notes (sweep-s2c-match.md, sweep-s2c-ui.md, sweep-c2s.md,
sweep-property-listeners.md, sweep-scriptlets-nodes.md, sweep-flash-hud.md) plus agl-visuals.md and
crime-alley-still-missing.md. Status: DONE (in ics, build tag), OPEN, or DEFER (not needed for a normal match).

Main correction: docs/re-notes/full-protocol.tsv's status column is stale; about 150 rows marked "not sent" /
"builder unused" are sent today (sweep-s2c-ui.md section 0, sweep-s2c-match.md section 0). Use the sweep notes, not
that column, until the tsv is regenerated.

## P1 — visible in an ordinary match

| # | Item | Source | Status |
|---|---|---|---|
| 1 | Kill card notice 0x1000021C to the victim (attackers, icons, teams, killer name) | flash-hud 2.1 | DONE fase3-hr (damage columns zero, P) |
| 2 | StopProcessingNewBillboards 0x100002BC before the result billboard | flash-hud, s2c-ui | DONE fase3-hr |
| 3 | Missile / spawned object creator 0x100004E2 (beam end: tethers, lassos, returning shots; 259 binds) | agl-visuals 1, scriptlets-nodes | DONE fase3-hr |
| 4 | Attribute_AttackSpeed 0x100006FE on units (graph variable, attack clip speed) | property-listeners | DONE fase3-hr (champions: via stat properties, check) |
| 5 | 0x00DA remote scriptlets played by 0x8D | c2s | DONE fase3-hr |
| 6 | Channel bar 0x2082 / 0x20B2 (channelled skills, recall) | s2c-match top 1 | OPEN |
| 7 | Slot override 0x207C / 0x208C (second-stage windows) and skill overlay 0x1000015A / 0x2091 (node 0x10000097) | s2c-match 2-3 | OPEN |
| 8 | ReleaseFacing 0x10000057 as the end of a FaceTarget lock (306 uses / 198 scripts) | scriptlets-nodes B | OPEN |
| 9 | Status icons on every visible unit (0x2123 / 0x2126 / 0x2129 / 0x212A) | s2c-match 10, flash-hud 18 | OPEN |
| 10 | Timeline icons 0x100002AB (start, drones, jungle, meteor) + banners 0x10000424 + removal 0x100002AC | flash-hud 3-5 | OPEN (icon DIDs unknown) |
| 11 | Recommended widget only in shop zones: shop_anywhere false in matches, 0x10000A23 from the base aura | flash-hud 2.2 | OPEN |
| 12 | 0x20EA raised only on skill scripts waiting for it (Deadshot R) | c2s | OPEN |
| 13 | Scriptlet variable 0x10000400 (vector3, 198 binds) never written | scriptlets-nodes A | OPEN (find the writer) |
| 14 | Dampener black octagon (property group 0x8A5 / 0x8A3 / 0x8B2) | still-missing 3 | OPEN (tests) |

## P2 — rarer features

- 0x212B artifact slot mapping echo (after 0x212C); 0x2022 / 0x2074 visual progression (templates with 0x100008DA);
  0x20DB / 0x20BC usable-object users; 0x2008 / 0x204E / 0x202C status script events; 0x203D death / cleanse;
  0x2019 effect variables (stacks); 0x0044 / 0x0043 over-head floaties; 0x2044 LockInput for hard CC / cinematics;
  0x2150 HUD restore; 0x2142 / 0x2143 stop conversations; 0x0086 remove property; minimap ring 0x209F / 0x217F /
  0x2180; 0x20F9 skill availability; 0x0008 raycast destruction; 0x2006 / 0x200E server looping effects; notice
  0x10000076 TimerClockSync.
- Script nodes with visible effects: 0x1000009C (lighting 0x956 in scenes), 0x1000010D / 0x1000010E (clone /
  disguise), 0x1000009E (Raven vitals link), 0x1000011E (reveal to team), 0x100001B9 (Grundy fake death),
  SetObjectState 0x10000090 / SetPhysicsEnabled 0x100000E4 / SetUsageObject 0x10000087, SetTargetingMode 0x10000075,
  SetCollisionLayer 0x10000114, 0x3F reaction chains.
- UI: queue wait times 0x218F, match build failure 0x210B / 0x20D7, error dialog 0x2087, early launch 0x2061, rejoin
  0x205B, join / leave billboards 0x100000CB / 0x100000CE, 0x20E2 for every champion (Tab board), achievement
  progress 0x21A6, login calendar 0x2197.
- Map: red rubble rocks (0x400005C9?), core platform "prow", stealth L-shaped mouth fields, lava cracks (probably
  another build's art).

## DEFER

Engine leftovers (TypedWorldObject, region / cell, appearance parts, session), debug / admin messages, social /
contacts / party, telemetry (answered silently since fase3-hr).
