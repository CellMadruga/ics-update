# HUD, shop, timeline, kills, death screen and post-match vs the original (2026-10-25)

Scope: the tester's reference frames of the ORIGINAL game (Crime Alley 2v2 video; shop with a full "Recommended"
row, timeline icons under the clock, a centre kill banner with two portraits, the death screen, the three post-match
tabs) and the 1:00:00 pre-start clock (`test-2026-10-25-1928.md` GH-5). For each: the client feature, what drives it,
the exact layout, what `ics` sends today and the server fix with proposed `[ics]` keys.

Sources: the decompiled exe (`re-work/decomp/c`, Ghidra, base 0x400000), the Flash movies (`re-work/ui-as2`, AS2),
the game data through `ics.gamedata`, `ics/` code, and `logs/traffic.log` of the 19:27 session (read before the logs
were cleared at 20:55). Tags: **C** confirmed in code / data, **P** probable, **G** guess, **O** open.

---

## 1. Shop: the "Recommended Artifacts" row is empty

### 1.1 How the client fills it (C)

- Flash `ArtifactDataManager` (singleton) runs `SetupYourBuildDIDs()` **once, in its constructor**, calling query
  `InqRecommendedArtifacts` (`0x100002ED`). Its six outputs: `aBaseArtifacts` (the Recommended row,
  `YOUR_BUILD_CATEGORY`) and the five situational lists (Starting / Offense / Defense / General / Core).
  `RecommendedItemsDisplay` reads the cached list (`GetTier1DataByCategory`) and never re-queries; only
  `GetYourBuildData()` re-queries when the list is empty, and the foundry does not use it.
- The singleton is created as soon as any HUD widget touches it: `FoundryManager` constructor (line 56),
  `DefeatRecommendationsPanel`, the inventory slot widgets (`ArtifactBase` / `ArtifactBasicData`). So it is built while
  the HUD movies load, long before the player opens the shop.
- The query's C++ handler is `0xA34CA0` (in the artifact query class, vtable `0x1601E78`, which registers the six
  queries `0x186DA94`..`0x186DAAC` and unregisters them in `0xA13240`):
  - `aBaseArtifacts` = copy of the **controlled agent's upgrade component `+0x50`** (`0x85D670` controlled agent ->
    `0xAA1FD0` upgrade component -> `0xADB230(comp + 0x50)`);
  - the situational lists = five properties of the controlled agent (`DAT_0160180C` / `808` / `804` / `800` / `810`,
    read with `0x9D0E60`), which come from the champion's data, so they appear without any server message.
- `+0x50` is written only by event **`0x2078`** (handler `0xA9FF30`): accepted only if the target is the controlled
  agent (`0x85D670() == target`) and it has its upgrade component (`agent + 0xA4 != 0`); it stores the list
  (`0x9743A0`) and raises `UpdateNextRecommendedUpgrade` (`0x10000272`, the HUD widget).

### 1.2 What ics did (C, traffic 19:27)

`create champion + player` 19:27:52.487, `link player -> champion` 19:27:54.495, client `UI_ReadyForTimelineData`
19:27:55.507 (the HUD movies are loading), **first `0x2078` at 19:27:59.431** (in `ev_notice` on load complete). The
situational rows show, so the query ran after the link (controlled agent known) and before `0x2078`: `+0x50` was empty
and the Recommended row stays empty for the whole match. Same on Gotham Heights (`0x2078` 19:42:36.86, at load
complete).

### 1.3 Fix

- Send `0x2078` (to the champion, `M.recommended_upgrades(ch.eid, rec)`, `rec` = `Data.loadout(class)["artifacts"]`
  = record `0x49......` `0x10000CEB` -> `0x10000478`, 24 DIDs for AGL) **in `Session._link()` right after the link
  bundle**, before the HUD loads. Keep the resend at load complete and after each purchase (HUD widget's next buy).
- With `recommended_follow_inventory` the resends drop held items; that only feeds the HUD widget, the shop row is
  frozen at the first list, which is what the original shows (24 items at 0:38 with 750 credits).
- `[ics] recommended_at_link = true` (2026-10-25, tester: the shop's Recommended row is empty; the client reads the
  list once while the HUD loads).
- P: if the row is still empty, send it also right after `create champion + player` with the champion as target and
  check `agent + 0xA4` (upgrade component) exists at that point (`tools/diag.py` breakpoint on `0xA9FF30` / `0xA34CA0`).
- O: a second match in the same session may keep the first champion's list if the Flash singleton survives (static
  class var); watch the GH match after a CA match.

---

## 2. Timeline strip under the clock: no icons

### 2.1 Client (C)

- Flash `EventTimerV2` (movie `0x20000065`) sends `UI_ReadyForTimelineData` (`0x100002AD`) on load and listens to the
  six `UI_MissionEvent_*` notices. C++ listener vtable `0x1605930`: `0x100002AF` -> `0xA68000` (sets flag `+0x144`),
  `0x100002B1` -> `0xA5A240` (flag `+0x145`), both -> `0xA5A0F0` -> **`0x898F50` = Flash
  `RecvNotice_UI_MissionEvent_StartTimeline(ttCurrentTime)`**, passing the notice's 8-byte payload as a **GFx Number
  (type 3, a double)**. Reader `0x941620` copies the 8 bytes unchanged. So the payload of `0x100002AF` / `0x100002B1`
  is an **f64 game time (now)**, not an IID.
- `EventTimelineDisplay.StartTimeline(t)` stores `m_ttStartTime = t` and starts its own interval timer at the local
  game time; an event's x = `(ttEventTime - (m_ttStartTime + elapsed)) / 5 s * 12 px` (46 ticks visible, removed
  at x <= -50). With `m_ttStartTime` ~ 0, events with game times ~1.79e9 land millions of pixels to the right.
- `0x100002AB` -> `0xA786F0`: delivered only once **both** `+0x144` and `+0x145` are set; one Flash
  `AddTimelineEvent` per text entry whose audience (u32 after the strings) is 7 (all), 6 (team 1 viewer), 5 (team 2
  viewer) or 4 (`0xABEE50`). Descriptor fields: `[0]` handle id, `[2..3]` handle IID, `[4]` severity, `[5]` timeline
  icon, `[6]` examination icon, `[7]` u8 tint, `[8]` owning team, `[10..11]` f64 event time (game clock).
- `TimelineEvent`: a valid `didTimelineIcon` draws that icon (tinted by team if `bTint`); icon 0 draws the default
  button, so icons are optional. The now-marker lights in the event's severity when an event crosses x in [-4, 4],
  with the low / med / high sound (`SetAlertBG`).

### 2.2 What ics sends (C)

`pvp_timeline_start(iid)` packs **`struct.pack("<Q", iid)`** = 0x0200000000000001 -> as a double ~1e-299, i.e.
`m_ttStartTime` ~ 0: every later event is far off-screen. And on Crime Alley no `0x100002AB` was sent at all (only the
meteor storm schedule exists, `[ics] match_events`, and only GD / CC / T1 use it). `timeline_banner()` in
`messages.py` (tutorial) has the same iid payload.

### 2.3 Fix

1. `0x100002AF` and `0x100002B1`: payload `struct.pack("<d", match.clock())` (game time at send). Same in the
   tutorial `timeline_banner()`. `[ics] timeline_start_time = true`.
2. Schedule the original strip (video, `crime-alley-2v2-video.md` 1): at the timeline-ready notice (and again at
   intro end if the clock was reset) send `0x100002AB` for each future event, `event_time = clock(at)`,
   `now = clock()`:
   - match start, `at = 0`, severity 1 (the red X), team 0;
   - first drone wave, `at = match_waves.first` (15 s), severity 2 (blue), team 0;
   - jungle camps, `at = match_camps.first` (45 s), severity 3 (green), team 0;
   - meteor / Device events as today.
   `[ics] match_timeline = {"start": {"at": 0, "severity": 1}, "drones": {"at": "waves", "severity": 2},
   "jungle": {"at": "camps", "severity": 3}}` (icons 0 until the strip icon DIDs are found: O, the EventTimerV2 icon
   images in pack `0xA00000D0`; the severity alone gives the colour).
3. Banners `0x10000424` alongside the announcer lines at -30 / -10 s, 0, wave -10 s / 0, jungle -10 s / 0 (text as
   StringInfo, `ttCountdown < 0` = no countdown), removed with `0x100002AC` after ~4 s
   (`pvp_timeline_remove`, built, never called). `[ics] match_timeline_banners = true`.
4. The strip removes past icons itself (x <= -50); no remove is needed for events.

---

## 3. Pre-start clock shows 1:00:00 (C)

- Flash `MatchTimer` / `IntervalTimer` (constrained mode): count-down display = `duration - elapsed` with
  `duration = end - start` and `elapsed = 0 while now <= start`. C++ `0xA902F0` only stores start / end (`+0x34` /
  `+0x3C`) and, when not pre-start, starts the match systems.
- ics `send_clock()`: `start = clock(0)` (the match start, in the future during pre-start), `end = start + 3600`,
  `isPreStart = 1` -> elapsed stays 0 -> **3600 s = 1:00:00** for the whole pre-start. Exactly the tester's frames.
- The original showed 00:42 counting down to 00:00, then counting up: only possible with `start <= now`,
  `end = match start` during pre-start.
- Fix: while `t < 0`: `pvp_set_match_time(clock(), clock(0.0), True)` (start = now, end = match start); at the start
  (unchanged) `pvp_set_match_time(clock(0.0), clock(0.0) + match_clock_length, False)`. Every resend (HUD ready,
  intro end) uses the current `clock()` as start. `[ics] match_clock_prestart_countdown = true`.

---

## 4. Centre kill banner "<killer> defeated <victim>" with two portraits

### 4.1 Client (C)

- The banner is a **billboard** (`BillboardManager.RecvNotice_ShowAnnouncement`, default type -> `BasicBillboard`
  with `m_didIcon1` = source icon, `m_didIcon2` = target icon, team colour of the source unless `bUseTargetTeamColor`).
- Kill billboards are **raised by the client itself** while it plays an announcer line: dialog item handler
  `0xA59300` (caller `0xA673C0`) -> when the line has a billboard type (`item[0x16] != 0`, flag bit 5 clear) and
  `0x5A68B0(1,0)`, it reads from the context table of the `0x2039` that started the line:
  `0x10000816` source icon, `0x10000815` target icon, `0x1000081D` / `0x1000081C` teams, `0x10000819` / `0x10000818`
  source / target **names** (StringInfo), sets them as text tokens (`0x89DE2F5` source name, `0xDCEF0B5` target name,
  `0x5AB7D` team), then `0x6351D0(...)` -> `0x8AB390` = Flash `RecvNotice_ShowAnnouncement`.
- Who fills those keys: the context-dialog builder `0x9CE360` (the script node that plays an announcer event) fills,
  for the source IID: `0x10000812` IID, `0x10000814` the entity's class DID (`ent+0x108 -> +8`), `0x10000816` = the
  entity's **`0x100001FC` Character_Billboard_Icon** (e.g. AGL `0x13000452`, Atrocitus `0x1300123D`, in the champion
  template), `0x10000819` = the entity's **Name `0x3CE`**, `0x10000823` = the entity's `0x10000593` (enum: AGL 35,
  Atrocitus 33; P the champion's announcer-name id, used to voice the champion's name), `0x1000081D` team; and the same
  for the target with `0x10000811` / `0x10000813` / `0x10000815` / `0x10000818` / `0x10000822` / `0x1000081C`.
  On the server this node ran on the original server; the client handler `0xA77DA0` reads the table as sent.
- The left-side kill feed (`KillDisplayManager`, event `0x217A`) is a different element: victim icon + killer /
  assist icons, no text, needs `killerTeam > 0`.

### 4.2 What ics sends (C)

`M.announcer()` (`0x2039`) carries only `0x10000806`, `0x10000812`, `0x10000811`, `0x1000081D`, `0x1000081C`:
names and icons are missing, so the billboard (if the line has one) shows an empty strip with no portraits (the
16:12 report "an empty strip at every kill"), and the line cannot name the champions (P: the 19:28 report "the kill
voice says the same whoever kills"). Kill voices are only played when the killer is a champion of the other team
(`_kill_voices`).

### 4.3 Fix

- Build the `0x2039` table like `0x9CE360`: for source and target entities add
  `0x10000814` (u32 class DID, kind DID), `0x10000816` / `0x10000815` (DID, value of `0x100001FC` from the champion
  template, `ud.first(class, 0x100001FC)`), `0x10000819` / `0x10000818` (StringInfo literal = the entity's display
  name), `0x10000823` / `0x10000822` (enum, the template's `0x10000593`), with the real champion IIDs.
  `[ics] announcer_entity_fields = true`.
- Bot display names: the original showed the bot as "AI: <champion>" (frame 5) [P: the bot agent's Name `0x3CE`];
  `[ics] bot_name_prefix = "AI: "` (the name also feeds the kill card and the scoreboard).
- O: which announcer events carry a billboard (`item[0x16]`): read the encounter's announcer set (template
  `0x10000802`, e.g. `0x40000D4C`) line entries; and what `0x5A68B0(1,0)` tests (also gates the kill-card overrides).

---

## 5. Death screen (greyscale, killer panel, respawn timer)

Tester's reference (original): the whole 3D view turns greyscale while dead; top-left a killer panel with the
killer's name, portrait, champion name, the killer's artifacts row, damage per skill (icons + numbers) and totals, a
row of killer / assister portraits with a skull; bottom-left "Respawn 0:07" over the champion portrait.

### 5.1 Respawn timer (C, ics OK)

`DefeatManager.OnDead(ts)` attaches `DeadTimer` to the character panel (bottom-left) from Flash
`DefeatStatusUpdated(iid, 2, tsTimeOfNextState)` = notice `0x10000090` `u32 state | f64 time of next state`
(ics sends it since 2026-10-23 with the game time; respawn `0x10000090` state 4). Portraits / scoreboard skulls:
`0x100000BC` (ics sends for other champions). Nothing to change.

### 5.2 Greyscale (P)

Client side, on LifeState `0x100000FA` = 2 of the local champion (listener `0x968F30`: dead list `0xA3FE60`, death
view `0xA30E70`; the post filter itself was not located: the exe has a video-post "Colorize" (saturation) effect,
`0x76D640`). The tester saw the grey screen with the creation-bundle death form (CHANGELOG fase3-gu / fase3-gv;
`[ics] death_as_property = false` is the current default). If it is missing in a new test, check that the LifeState 2
bundle reaches the local champion before `0x10000090`.

### 5.3 Killer panel = kill card, notice `0x1000021C` (C layout; ics layout wrong)

Flash `DefeatManager.RecvNotice_UI_ShowKillCard` -> `KillCard.SetData` -> **shows itself at once** (`Show(false)`)
and enables the toggle button. It needs:
- the killer (first attacker IID) to be in Flash `MatchData` (the Tab-scoreboard roster, notice `0x1000005B`): then
  name, champion name, **artifacts row = MatchData `artifactBasicDatas`** (from `0x20E2` UpdateCurrentUpgrades for
  that agent) and the hero graph (`0x10000160` / amplifier set). Otherwise only the override name;
- portrait: `didKillerIcon`, else MatchData billboard icon, else portrait icon.

Wire layout from the reader **`0x9326C0`** (C, read order):

| # | Field | Type |
|---|---|---|
| 1 | attacker IIDs (killer first) | list<u64> |
| 2 | attacker icon DIDs | list<u32> |
| 3 | team ints (P: Flash `i_aTeamInts`) | list<u32> |
| 4 | killer name override | StringInfo |
| 5-9 | total damage, slot 1..4 damage, one value per attacker (P order: as the Flash args, total first or last: O) | **5 x list<f32>** |
| 10-37 | per attacker: slot 1..4 slot type, slot 1..4 damage type (1 Attack, 2 Power, 3 True, 4 Mixed), slot 1..4 icon DID, slot 1..4 source artifact DID, slot 1..4 source mod DID (20 lists) + 8 more lists (P: slot skill DIDs, used by the listener `0xA61260` -> `0xA5DE20` to build names / tooltips) | **28 x list<u32>** |
| 38-41 | slot 1..4 name overrides per attacker | **4 x list<StringInfo>** |
| 42-43 | damage-type totals, damage-type percentages (indexed by DamageType: [1] Attack, [2] Power, so >= 3 entries) | **2 x list<f32>** |
| 44-45 | (P: teams / flags) | 2 x list<u32> |

`ics M.kill_card()` writes `5 x {u32 0, u32 0}` where the reader wants 5 float lists (10 u32 = 10 empty lists for
the reader), then 28 lists, then `4 x {u32, StringInfo}` where the reader wants `list<StringInfo>`, then
`2 x {u32 u32}` + 2 lists + u32: from field 5 on everything is shifted, the damage numbers are empty / garbage and the
tail is misread. Fix (`[ics] kill_card_layout = "reader"`):
- every per-attacker list with exactly `n = len(attackers)` entries;
- float lists for the 5 damage columns and the 2 damage-type lists (`[0, attack, power, true, mixed]` totals and
  the same as fractions 0..1);
- slot columns from a damage ledger: per (victim, attacker, skill slot 1..4, damage type) since the victim's last
  respawn (ics `World.damage` knows the attacker and the skill's slot; basic attacks = slot 0 / the "total" only);
  slot icon = the attacker's skill icon of that slot; artifact / mod DIDs 0;
- name lists empty (n empty StringInfo) or the skill names; the client fills tooltips;
- killer name override: "" when the killer is in MatchData (champion), else the unit's name;
- also send `0x20E2` for every champion (not only the local one) so the killer's artifacts row and the hero graph
  fill. `[ics] kill_card_damage_ledger = true`, `[ics] upgrades_for_all_champions = true`.

---

## 6. Post-match screen (Summary / Scorecard / Stats)

The end page (`0xA795E0`, called from the `0x2045` handler `0xA91BF0` and four others) builds Flash
`UI_SendEndOfMatchStats` (`0x8E3AC0`, 42 args) once it has the match-ended notice and the entries of **`0x2045`**
(`u8 0 | u32 n | n x entry (reader 0x8776A0, 0x350 bytes in memory) | f32 duration`).

### 6.1 The `0x2045` entry (C, reader `0x8776A0` + `0x866650`)

| Wire | Memory | Meaning |
|---|---|---|
| u64 | +0x00 | (P: account / player IID) |
| u64 | +0x08 | account IID (`0x85C790`, aAccountIIDs; also the friend / ignore lookups) |
| u64 | +0x10 | player IID (`0x85C750`, aPlayerIIDs) |
| u32, u32 | +0x1C, +0x20 | (P: champion level / protector level) |
| amplifier set `0x86FB20` | +0x28 | its u32 list = Flash `aAmplifiers` |
| u32 | +0x2D0 | **team** (1 / 2; `0x85CA00`, aTeams; rows with team 1 / 2 only) |
| map `0x583DD0` | +0x2A8 | **kills by target type**: `u8 bucket index (<= 22) | compact n | n x (u32 key, u32 count)` |
| map `0x583DD0` | +0x2BC | second map (P: deaths by killer type) |
| StringInfo | +0x2D4 | display name (aNames) |
| u32 | +0x2F8 | (P: icon / champion DID) |
| `0x86F400`, `0x86F520`, `0x844770` | | three small blocks (ics: 1 + 3 u32) |
| stats block `0x866650` | +0x70 | below |
| u32 | +0x32C | CreditsStomped (stat 7) |
| u8, u8 | +0x330, +0x331 | (P: flag), **is bot** |

Stats block (`0x866650`, wire read k -> memory `+0x70 + offset`); ics writes it as
`Q B I | 14 Q | 2 I | 6 Q | I | 8 Q | I | 6 Q | I | StringInfo StringInfo | 21 Q | 2 I`, all zero today.

The Stats tab grid and the Scorecard columns are **data-driven**: the encounter twin's `0x10000B2C` (Crime Alley vAI
`0x49000C82` -> `0x480012A4`) lists sections (`0x10000B32`: label `0x10000B33`, stat list `0x10000AB1` of enum
`0x10000CEF`), and `0x10000AB2` (`0x480012A3`) lists the 5 Scorecard objective columns. Each stat id is read from the
entry by `0x8677F0` (switch). Stat ids = catalog `0x48001172` (key names below are its internal identifiers). Map from
stat id to wire position (C, offsets and types agree: f64 stats sit on 8-byte reads, u32 stats on u32 reads):

| Stat id | Key name | Wire read in stats block | Type |
|---|---|---|---|
| 0x01 | TimeSpentDead | 36 | u64 |
| 0x02 / 0x11 | TurretsCaptured / ControlPointsCaptured | 28 | u64 |
| 0x03 | PowerDamageTakenFromChampions | 56 | u64 |
| 0x04 | OrbitalCannonCaptures | 21 (P, decompiler alias with 33) | u64 |
| 0x05 | AttackDamageReducedFromChampions | 52 | u64 |
| 0x06 | QuadraKills | 15 | u64 |
| 0x07 | CreditsStomped | entry u32 +0x32C (after the block) | u32 |
| 0x08 | CreditsEarnedFromObjectives | 61 | f64 |
| 0x09 | CreditsEarnedFromCreatures | 60 | f64 |
| 0x0A | CreditsEarnedFromChampions | 58 | f64 |
| 0x0B | CoinsCollected (aCoinPickups) | 31 | u64 |
| 0x0C | ExperienceEarned | 27 | u64 |
| 0x0D | DroneKills | kills map key 0x10000 | u32 |
| 0x0E / 0x2A | DestructionCaused / DestructionValue | 13 | u64 |
| 0x0F | AttackDamageDealt | 48 | u64 |
| 0x10 | DoomsdayDeviceActivations | 25 | u32 |
| 0x12 | PentaKills | 16 | u64 |
| 0x13 | HealingReceived | 41 | u32 |
| 0x14 | CreditsEarnedFromDrones | 59 | f64 |
| 0x15 | PowerDamageDealt | 53 | u64 |
| 0x16 | Assists (aAssists) | 8 | u64 |
| 0x17 | AttackDamageTakenFromChampions | 51 | u64 |
| 0x18 | ExperienceFromCreatures | 64 | u64 |
| 0x1A | PowerRelaysCaptured | 22 | u64 |
| 0x1B | DamageTaken | 37 | u64 |
| 0x1C | ExperienceFromChampions | 62 | u64 |
| 0x1D | DampenersDisabled | 45 | u64 |
| 0x1E | Deaths (aDeaths) | 7 | u64 |
| 0x1F | DamageDealt | 38 | u64 |
| 0x20 | TurretsDestroyed | kills map key 0x10 | u32 |
| 0x21 | TripleKills | 14 | u64 |
| 0x22 | ExperienceFromObjectives | 65 | u32 |
| 0x24 | BeaconsDeployed | 32 | u64 |
| 0x25 | ExperienceFromDrones | 63 | u64 |
| 0x26 | PowerDamageReducedFromChampions | 57 | u64 |
| 0x27 | DamageReduced | 39 | u64 |
| 0x28 | CreditsEarned (aCurrency) | 12 | f64 |
| 0x29 | CreatureKills | kills map key 0x100 | u32 |
| 0x2B | ChampionKills (aPlayerKills) | kills map key 0x8 | u32 |
| 0x2C | RaiderKills | 20 | u64 |
| 0x2D | PowerDamageDealtToChampions | 54 | u64 |
| 0x2E | HealingDone | 40 | u64 |
| 0x2F | DoomsdayGuardiansDestroyed | kills map key 0x40000 | u32 |
| 0x30 / 0x32 | TurretsNeutralized / ControlPointsNeutralized | 29 | u64 |
| 0x31 | DoomsdayDeviceFired | 34 | u32 |
| 0x33 | DamageTakenFromChampions | 46 | u64 |
| 0x34 | AttackDamageDealtToChampions | 49 | u64 |
| 0x3C | LeviathanKills | 23 | u64 |
| (0x19) | team (not a stat) | entry +0x2D0 | u32 |

Read numbering: 0 = the first u64, 1 = the u8, 2 = the u32, 3..16 = the 14 u64, 17-18 the two u32, ... 42-43 the two
StringInfo, 44..64 the 21 u64, 65-66 the last two u32 (same order as `ics M._end_stats_entry`).

Crime Alley's grid (`0x480012A4`), 4 sections in order:
1. 0x1F, 0x0F, 0x34, 0x15, 0x2D, 0x2B, 0x1E, 0x16, 0x0D, 0x29 (damage dealt / attack / attack to champions / power /
   power to champions, kills, deaths, assists, drone kills, creature kills: exactly the tester's Stats rows);
2. 0x1B, 0x33, 0x17, 0x03, 0x2E, 0x13, 0x27, 0x05, 0x26, 0x01 (damage taken, from champions, attack / power from
   champions, healing done / received, damage reduced, attack / power reduced from champions, time dead);
3. 0x0B, 0x07, 0x28, 0x0A, 0x14, 0x09, 0x08, 0x0C, 0x1C, 0x25, 0x18, 0x22 (coins, credits stomped, credits earned and
   by source, XP and by source);
4. 0x20, 0x1D, 0x24 (turrets destroyed, dampeners disabled, beacons deployed).
Scorecard objective columns (`0x480012A3`): 0x0B, 0x24, 0x20, 0x1D, 0x07. The other maps have their own
`0x10000B2C` / `0x10000AB2` on their encounter twins (read the same way).

### 6.2 What ics sends and what is missing (C, `ics/matchend.py`)

| Tab element | Message | ics today | Fix |
|---|---|---|---|
| Scorecard rows (names, team, bot flag, K/D/A, credits, coins, objective columns) | `0x2045` | entries all zero: no team (rows need team 1 / 2), no name, 0 K/D/A | fill per player from a match ledger: account / player IIDs, team (+0x2D0), name, is bot, kills map {0x8 champions, 0x10 turrets, 0x100 creatures, 0x10000 drones, 0x40000 guardians}, deaths, assists, credits earned (f64), coins, the stats above |
| Scorecard portrait + champion level, protector level | `0x2045` head / `0x2190` | zero | entry u32s +0x1C / +0x20 (P) and the champion icon (P +0x2F8); verify in game |
| Scorecard graph + artifacts icons | Flash MatchData (in-match `0x20E2` / `0x10000160` per champion) and the entry's amplifier list | own champion only | `0x20E2` for every champion during the match; amplifier set in the entry |
| Team totals / WINNER | computed by the client from the rows; winner from `0x1000000E` | winner OK | - |
| Stats tab (Detailed Match Stats) | `0x2045` stats block + grid record | zeros | ledger (6.3) |
| Summary: accolade cards + Personal Best | `0x2188` (and inside `0x2104`) `(encounter, ranked, champion, StringInfo, names[], descriptions[], summaries[], icons[], medal types bytelist, isAllTimeBest[])` | empty lists: no cards | pick up to 3 of the 46 accolades of `0x48001242` by the player's stat (`0x10000C6A` = stat id above), medal 1 / 2 / 3 by rank among players, icons `0x10000CE1`..`CE3`, texts as the record's StringInfo tokens (not copied text), all-time best from the account; first match on a map -> `0x48001490` |
| Summary: Merit (match / bonus / first win / total) | `0x20B9` | sent (pvp_rewards) | OK; bonus 0 |
| Summary: champion level bar | `0x2104` | sent | OK |
| Summary: protector level bar | `0x2080` | sent | OK |
| Summary: last map played + duration | `0x214B` last played, `0x2045` / `0x1000000E` duration | sent | OK |

### 6.3 Per-player statistics the server must keep during the match

Per player (champions and bots), reset never during the match: damage dealt (total, attack, power; to champions
split attack / power), damage taken (total, from champions, attack / power from champions), damage reduced (total,
attack / power from champions; = pre-mitigation minus post-mitigation), healing done / received, kills by target type
(champions, drones, creatures, turrets, guardians, raiders, Leviathan), deaths, assists, triple / quadra / penta kills,
time spent dead, credits earned (total and by source: champions, drones, creatures, objectives), credits stomped,
coins collected, XP earned (total and by source), turrets / dampeners destroyed, beacons, capture / neutralise counts
(GH / CC / GD), destruction caused. Plus per victim life: damage per (attacker, skill slot, damage type) for the kill
card. Hook points: `World.damage` (dealt / taken / reduced, slot, type), heal paths, `Match._champion_died` /
`_reward` / `grant` (kills, credits, XP by source), `pickups` (coins), structure deaths, objectives.
`[ics] match_stats_ledger = true`, `[ics] end_stats_from_ledger = true`, `[ics] match_accolades = 3`.

---

## 7. Proposed `[ics]` keys (summary)

| Key | Default | Item |
|---|---|---|
| `recommended_at_link` | true | 1: `0x2078` right after the player link |
| `timeline_start_time` | true | 2: f64 game time in `0x100002AF` / `0x100002B1` |
| `match_timeline` | start 0 s sev 1, drones = first wave sev 2, jungle = first camps sev 3 | 2: `0x100002AB` schedule |
| `match_timeline_banners` | true | 2: `0x10000424` + `0x100002AC` with the countdown lines |
| `match_clock_prestart_countdown` | true | 3: pre-start `(now, match start, 1)` |
| `announcer_entity_fields` | true | 4: `0x10000814/16/19/23` + target twins in `0x2039` |
| `bot_name_prefix` | "AI: " | 4: bot display name |
| `kill_card_layout` | "reader" | 5: `0x1000021C` as read by `0x9326C0` |
| `kill_card_damage_ledger` | true | 5: per-slot damage columns |
| `upgrades_for_all_champions` | true | 5 / 6: `0x20E2` for every champion |
| `match_stats_ledger`, `end_stats_from_ledger` | true | 6: real `0x2045` entries |
| `match_accolades` | 3 | 6: `0x2188` cards |

> 2026-10-26 correction (end-stats-2045.md, C): the stats block starts at entry +0x78, so every read index in
> section 6 is one too high; f64 reads are 11 and 57-60, reads 65 / 66 are f32; the head's second u64 is the account IID.
