# Sweep: Flash HUD and menu entry points vs what `ics` sends (2026-10-25)

Scope: every `GM_*` / `EM_*` `RecvNotice_*` the Flash UI listens to that matters for a normal match, the HUD element
that shows it, the network message that feeds it, and whether `ics/` sends it today. Sources: `ui-complete.md`
section 4 (the 315 Recv notices, arguments, listeners, feeders), `full-match-mechanics.md` (sections 3, 4, 9, 14),
`crime-alley-2v2-video.md` (what the original HUD showed), `countdown-keymap-gaps.md` 3, `protocol-complete.md`,
and a grep of `ics/` (builders in `ics/messages.py`, callers in `ics/match/*.py`, `ics/world.py`, `ics/session.py`,
`ics/matchend.py`). Exe checks with REA (ghidra, base 0x400000) where marked.

Tags: **C** confirmed (code / grep), **P** probable, **G** guess. "ics" column: **yes** = a caller sends it in a
match, **built** = builder exists but nothing calls it, **no** = neither. Flash ids (`0x10000222` ...) differ from
the network notice ids (`0x1000021C` ...): the network notice reaches a C++ listener, which raises the Flash one.

Out of scope (covered by `ui-complete.md` 6.1 / other notes): wrapper menus, social, custom match, lobby, login
rewards, spectator (`GM_ViewMatch`), web browser, options.

---

## 1. In-match HUD: entry point -> feeder -> ics

| Flash notice (id) | HUD element | Network feeder | ics | Normal match | Prio | Conf |
|---|---|---|---|---|---|---|
| Encounter.SetMatchTime `0x10000109` | top clock (count down / up) | notice `0x10000109` (player) | yes (`send_clock`) | yes | - | C |
| UI.TimerClockSync `0x10000076` | `CountdownTimer` used by billboards / objective timers | notice `0x10000076` u32 | no | low (timers fall back to local clock, P) | 4 | P |
| Encounter.UI_MissionEvent_StartTimeline `0x100002A8` | timeline strip under the clock | notices `0x100002AF` / `0x100002B1` (answer to C->S `0x100002AD`) | yes | yes | - | C |
| UI_MissionEvent_AddTimelineEvent `0x100002A5` | icon on the strip (match start X, drones, jungle, meteor) | notice `0x100002AB` | yes, **only meteor storm**, icon 0 | yes | **1** | C (gap) |
| UI_MissionEvent_BatchAddTimelineEvent `0x100002A6` | same, many at once | notice `0x100002AE` | no | optional (single adds suffice) | 5 | C |
| UI_MissionEvent_AddTimelineBanner `0x10000422` | centre notice under the top bar ("Drones in 10 seconds!", "Match: Initiating") | notice `0x10000424` | yes, meteor only | yes | **1** | C |
| UI_MissionEvent_Remove* `0x10000421` / `0x100002A7` | drop icon / banner | notice `0x100002AC` | built, never called | yes (stale icons) | 3 | C |
| Encounter.UI_InitialTeamHealthUpdate `0x100004FB` / UI_UpdateTeamHealth `0x10000134` | two core / team-health bars (Clash, GH) | notices `0x100004FB`, `0x10000134` | yes | Clash / GH | - | C |
| Encounter.UI_UpdateTrackerStatus `0x1000037E` | sector tracker pips + minimap | event `0x2069` | yes (capturables) | CC / GD / GH / CA | 3 (CA/GD slots) | C |
| UI_BatchUpdateTrackerStatus `0x10000380` | same, batch | no network source found (local re-batch of cached `0x2069`, P) | n/a | - | - | P |
| Encounter.UI_UpdateMatchScorecard `0x1000007E` + AddParticipant `0x1000001E` | Tab scoreboard (K/D/A, credits, level), team portraits | notice `0x1000005B` (full roster) | yes (`scoreboard.send`) | yes | 2 (resend on every change) | C |
| Character.NotifyPlayerDied `0x10000127` | kill feed (4 rows, 5 s) | event `0x217A` | yes | yes | - | C |
| Character.ShowAnnouncement `0x100002EB` / Clear `0x100002EC` | billboards (kills, structures, VICTORY / DEFEAT) | notices `0x100002EB` / `0x100002EC` | yes | yes | - | C |
| Character.StopProcessingNewBillboards (n `0x100002BC`) | stops billboards at match end | notice `0x100002BC` | no | yes (end) | 4 | C |
| Encounter.UI_PlayerJoined / Left `0x100000CB` / `0x100000CE` | join / leave billboards | notices `0x100000CB` / `0x100000CE` (u64, u64, StringInfo, u32 icon, u32 team) | no | PvP with real players | 4 | C |
| Character.UI_ShowKillCard `0x10000222` | **death recap / kill card** (attackers, damage per skill slot, damage-type split) | notice **`0x1000021C`** to the victim (`0x100002B2` spectator) | **no** | yes | **1** | P (layout C from reader, mapping P) |
| UI.DefeatStatusUpdated `0x10000090` | own death panel + respawn countdown | notice `0x10000090` | yes | yes | - | C |
| UI.DefeatStatusUpdatedForEntity `0x100000BC` | portrait skull + respawn timers | notice `0x100000BC` | yes | yes | - | C |
| UI.PauseDefeatStatusTimerForEntity `0x100000BA` | (dead in Flash) | notice `0x100000BA` | no | no | - | C |
| Encounter.UI_UpdateHasVendorAccess `0x100002FA` | Recommended widget / foundry button / death recommendations | client, from attribute `0x10000A23` (P, progression-meta 1.4) | indirect (ics sets `0x10000A23`; `shop_anywhere`) | yes | 2 (zone-based toggle) | P |
| Encounter.UI_UpdateHasBaseAccess `0x100003FC` | kill-card hide on leaving base, SkillsPanel | client region (P) | indirect | yes | 3 | P |
| Upgrade.UpdateNextRecommendedUpgrade `0x10000272` | Recommended widget right slot (next buy + Build) | event `0x2078` (champion) | yes | yes | - | C |
| Advancement.SkillRanked `0x10000054` | rank-up result, death panel | script native `0xE70015` only (local) | n/a | - | - | C |
| properties `SkillPoints` `0x100001AF`, `Level`, `XP` | skill "+" buttons, "N Point Available", XP bar, level | property updates on the champion | yes | yes | - | C |
| Advancement.XPGained `0x100004F9` | "+XP" floaty | local, from `0x10000142` deltas (P) | indirect | yes | - | P |
| Upgrade.UI_ShowFloatyCurrencyOverEntity `0x100004D5` | "+50" credits over a kill | notice `0x100004D6` (u64, f32) | yes | yes | - | P |
| Upgrade.DisplayFloatyCurrencyChanged / Denied `0x10000506` / `0x10000505` | credits counter pulse | local from `0x1000035E` (P) | indirect | yes | - | P |
| Upgrade.UpdateCurrentUpgrades / UpdatePowerGraphValues `0x1000012F` / `0x10000160` | item slots, hero graph, scoreboard Artifacts / Graph columns | event `0x20E2` (per champion) | yes (own champion) | yes | 2 (send for **every** champion for the Tab board) | P |
| Skill.EnableSkillButton `0x100002D7` | skill / item button greyed | `0x207B` / `0x20A0` / `0x2187` | yes (combat.py) | yes | - | C |
| UI.StartSkillCooldown `0x10000055` | skill **and item** cooldown sweep | event `0x20F8` | yes | yes (items too) | 3 (verify item slots) | C/P |
| UI.ExecuteSkillError `0x1000008A` | "not enough Will" / "on cooldown" popup | `0x20DC` / `0x2092` | yes | yes | - | C |
| UI.Update/RemoveSkillStackCountString `0x1000030C` / `0x100004DE` | stack counter on a button | `0x20A2` / `0x20A8` / `0x20C8` / `0x20E9` | partly (status icons) | some kits | 4 | P |
| StatusIcon.Add/Update/Remove/Tooltip | buff / debuff bar | `0x20C8` / `0x20A8` / `0x20E9` / `0x20D0` / `0x2127` (to the agent) | yes (world.py) | yes | 3 (enemy target row, tooltips) | C |
| Vitals.VitalsChanged / DisplayFloatyStatus | bars, damage numbers, "Stunned" floaties | `0x42`, `0x20BD` | yes | yes | - | C |
| Vitals.DOTUpdate / VOTUpdate `0x10000311` / `0x10000310` | DoT / VoT ticks on bars | local from vitals tails (P) | indirect | yes | 5 | P |
| UI.NotifyHUDElement / Batch `0x10000420` / `0x10000440` | show / hide / highlight HUD parts | `0x213D` / `0x213E` | yes (`0x213D`) | yes | - | C |
| UI.UpdateHUDVisibility `0x10000048` | HUD hide (cinematics) | `0x20F5` / `0x2150` | yes (`0x20F5`) | yes | - | C |
| Encounter.UpdateSurrenderData / SurrenderVoteConcluded | surrender panel | notices `0x10000455` / `0x10000456` | yes | yes | - | C |
| MapManager.ShowMiniMapTargetingRing, Start/StopTeleportEffects | minimap ring, recall | `0x209F`/`0x217F`/`0x2180`, `0x218A`/`0x2189` | teleport yes | yes | 4 | P |
| MapManager.AddStaticMapNote / RemoveMapNote / pings | minimap notes, pings | `0x20D2`, `0x2137`, `0x2006` / `0x200E` | `0x20D2`, `0x2137` yes; `0x2006`/`0x200E` no | yes (alert / retreat pings to team) | 3 | C |
| MapManager.MapNote_UnderAttack `0x100001B1` | flashing structure icon | local? (no feeder found) | n/a | yes | 3 (find source) | G |
| Encounter.UI_* objective notices (16) | left objective tracker ("Crime Alley Clash!" panel) | `0x2034` / `0x2009` / `0x2023` / `0x2075` | tutorial only (director.py); match: tracker enable only | yes (PvP rules panel) | 2 | C |
| Encounter.NotifyMatchEnded `0x1000000E` | VICTORY / DEFEAT, HUD exit | notice `0x1000000E` | yes | yes | - | C |
| Encounter.UI_SendEndOfMatchStats / SetEndOfMatchStatsHeader | scorecard | `0x2045` (+ `0x2028` header, P) | yes (`end_of_match_stats_all`) | yes | 2 (real per-player stats) | C |
| Character.SendAccountEndOfMatch* , accolades, ribbons | scorecard XP / credits / accolades / level-up ribbon | `0x2080`, `0x2104`, `0x20B9`, `0x2188`, `0x2081`, `0x2190` | yes (matchend.py) | yes | - | C |

---

## 2. New checks in this sweep

### 2.1 Kill card / death recap is network-driven (C for the listener -> Flash link)

REA decompile of `0xa61260` (listener of network notice `0x1000021C`, vtable `0x1604908` slot `+0x60`): it resolves
every attacker IID through the entity table (`[0x1b67258]` vfunc `+0x58`, missing entity -> 0), then for each of the
4 skill-slot columns calls `0xa5de20(attacker list[i], slot artifact DID, slot DID, slot type, out name, out tooltip)`
to build the per-slot name / tooltip overrides (skips them when `0x5a68b0(1,0)` is false and the wire override is
taken instead), and finally calls **`0x8d1e70` = the `GM_Character.RecvNotice_UI_ShowKillCard` (`0x10000222`)
deliverer** with the 38 Flash arrays. So the death recap appears only if the server sends `0x1000021C` (wire layout:
`protocol-complete.md` row `0x1000021c`, reader `0x9326c0`). The attacker IIDs must be live entities on the client
(their names come from the entity), damage per attacker / per slot and the Attack / Power split come from the wire.
`ics` tracks damage contributors for assists (`scoreboard.assisters`) but not per-slot damage: a minimal card (one
row per attacker, total damage, slot 1..4 = 0) should already render. `HideKillCard` (`0x100002B3`) is local.

### 2.2 Recommended widget / vendor access (C from `shop-items-inventory.md` 3.2, P for the widget link)

`UI_UpdateHasVendorAccess` (`0x100002FA`) has no network feeder: the ids `0x100002FA` / `0x100003FC` occur only in
`.data` notice tables (`0x1853774` / `0x185379c` ...), no immediate push in `.text` (REA byte search). The client
raises it from the upgrade component's flags (`+0xC4 = dead || 0x10000A23`). `ics` sends `0x10000A23 = true` on
creation (`[ics] shop_anywhere` default true), so the HUD Recommended widget and the foundry button are on
everywhere; the original showed them only in the base aura (video section 7). The base aura status `0x48001109`
("may shop") is already applied by `Match._auras_tick`; with `shop_anywhere = false` the attribute would follow it.
`UI_UpdateHasBaseAccess` (`0x100003FC`) most likely follows `0x10000459` (in-base flag, `0xA1ADF0`) [P].

### 2.3 Timeline: only the meteor storm is scheduled (C, grep)

`Objectives.events_tick` sends `0x100002AB` + `0x10000424` only for `[ics] match_events` (meteor storm), with
`icon = 0`. The original strip showed a red X at match start, a blue drone marker at +15 s and a green jungle marker
at +45 s with centre banners "Drones in 10 seconds!", "Drones operational!", "Jungle Creatures: Online in 10
seconds" / "Phasing Complete" (video section 1). `ics` plays these as announcer lines (`match_wave_lines`,
`match_jungle_lines`) but never puts them on the timeline; the banners `0x10000424` (text as StringInfo) and
`0x100002AC` removal (built, never called) are missing. Icon DIDs for the three markers are not identified (O: look for
the EventTimerV2 icon images in pack `0xA00000D0`, or keep icon 0 and rely on severity colour).

### 2.4 Other gaps confirmed by grep

- `0x100002BC` StopProcessingNewBillboards never sent (late kill billboards can overlap VICTORY / DEFEAT).
- `0x100000CB` / `0x100000CE` join / leave billboards never sent.
- `0x10000076` TimerClockSync never sent.
- No PvP objective panel (`0x2034` / `0x2009` / `0x2075`): the video's left "Crime Alley Clash!" rules panel is absent.
- `0x20E2` (UpdateCurrentUpgrades / power graph) only for the own champion: the Tab board's Artifacts and Graph
  columns of other players stay empty.
- `0x2006` / `0x200E` map-note pings (alert / retreat for allies) never sent; `MapNote_UnderAttack` has no feeder found.
- Structure "under attack" announcer events (31, 32, 34, 35, 41, 56) never raised (`countdown-keymap-gaps.md` 3.2).

---

## 3. Top-20 server-side implementations (ordered)

1. Send kill card `0x1000021C` to the victim on every champion death (attackers = killer + assisters, total damage per
   attacker from a per-victim damage ledger; Attack / Power totals and percentages).
2. Track damage per (victim, attacker, skill slot, damage type) in `World.damage` to fill the 4 slot columns.
3. Timeline icons: `0x100002AB` for match start (t=0), first wave (+15 s), jungle (+45 s), meteor; config table
   `[ics] match_timeline` {key: time, severity, icon, title}.
4. Centre banners `0x10000424` for "match begins in 30 / 10", "Match: Initiating", drones -10 s / operational,
   jungle -10 s / phasing complete (alongside the announcer lines).
5. Remove fired timeline items with `0x100002AC` (builder exists).
6. Recommended widget only in base: default `shop_anywhere` false in matches (keep for tutorial), let the base aura
   status drive `0x10000A23`; set `0x10000459` in base for `HasBaseAccess`.
7. `0x2078` re-sent on base entry and after every death (panel `DefeatRecommendationsPanel`).
8. `0x20E2` for every champion to the local player (Tab board artifacts + hero graph).
9. Scoreboard `0x1000005B`: kills / grants already mark it dirty (1 s throttle); also mark it on passive income and on
   other champions' level-ups (`grant` sets `champ.level` without touching the board).
10. `0x100002BC` StopProcessingNewBillboards just before the result billboard.
11. Structure under-attack announcer events + `0x100002EB` billboard with a 30 s per-structure throttle.
12. Core threshold notices 75 / 50 / 25 % (own / enemy) as billboards + lines (events 10 / 15 / 17).
13. PvP objective panel: `0x2034` category + one `0x2009` objective with the map's rules text (template objective record).
14. `0x100000CB` / `0x100000CE` when a real player joins / drops (multi-client).
15. `0x10000076` TimerClockSync at HUD ready and on match start (billboard / objective countdowns).
16. Ally pings: relay `0x2136` from one client to teammates as `0x2006` map notes, `0x200E` on expiry.
17. Skill-point notice: verify `SkillPoints` property update after each level (Recommended "N Point Available").
18. Status icons on enemy / target agents: `world.py` sends `0x20C8` only for the own champion or `client_vitals`
    entities; extend to every visible champion (selection panel / overhead buff row).
19. End-of-match `0x2045` with the real per-player K/D/A, damage, credits columns from the match ledger.
20. Respawn: pause `0x100000BA` not needed (dead in Flash); instead send `0x100000FA` = 5 (Respawning) before 4.
