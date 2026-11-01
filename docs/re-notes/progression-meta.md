# Progression and out-of-match systems (static analysis, 2026-10-21)

Client `InfiniteCrisis.exe` (image base 0x400000, all addresses **VA**), the AS2 dump of the UI pack
(`old_files/tools/gfx/classes_all.txt`), the client script library **WLib `0x39000001`** (pack `0xA0000038`, record at
stream offset `0x102378`) and the data packs. Nothing here was run against the client. Tags: **[C]** confirmed from code or
data, **[P]** probable (consistent evidence, one link missing), **[G]** guessed.

Companion notes: `protocol-server-to-client.md` (all 336 events / 44 network notices, byte layouts),
`protocol-client-to-server.md`, `reward_re.txt` (the reward-ribbon chain), `icserver/scorecard.py` (end-of-match builders).

---

## 1. In-match progression

### 1.1 Properties on the controlled champion (Flash names from the AS2 `__get__*_Property` getters) [C]

| Property | Flash name | Kind | Who reads it |
|---|---|---|---|
| `0x10000167` | `Level_Property` | int | Flash `ControlledAgentDispatcher` (`LEVEL_CHANGED/ADDED`), XP bar, `GetSkillRank` for slots outside 1-5, WLib advancement methods |
| `0x10000142` | `XP_Property` | int | Flash dispatcher (`EXPERIENCE_CHANGED/ADDED`), XP bar |
| `0x100001AF` | `SkillPoints_Property` | int | Flash (`OnSkillPointsChanged/Added/Removed`), HUD watcher `0xa93b70`, WLib CanRank method |
| `0x1000035E` | `Upgrade_Currency_Property` | f32 | in-match gold: Flash shop/currency display, HUD watcher `0xa93c50` |
| `0x10000CD6` | `Upgrade_CurrentItemCount_Property` | int | number of artifacts owned (HUD watcher) |
| `0x100000AF` | (none) | array of int, element key `0x10000167` (as the servers send it) | skill ranks per slot; `GetSkillRank` VA `0x863ce0` (slots 1-5; element 0 = basic attack) |
| `0x100006C1` | (none) | int | **only the patched client** (caves A-E). Unpatched code never reads it |
| `0x1000009C` | `PVP_Team_Property` | int | team |
| `0x100000FA` | (LifeState) | enum | `LifeStateList`: 1 DeadAndFaded, 2 Dead, 3 Incapacitated, 4 Alive, 5 Respawning [C] |
| `0x10000975` | ? | int | read by WLib advancement method `0x91e4`; data: on unit templates (`0x49...`) in map packs, values 100 / 10-39 [P: a level or bounty-like value of units] |

Flash registers listeners with `PropertySystem.Register(controlledAgent, gmAdvancementPropertyList.{Level,XP,SkillPoints},
gmUpgradePropertyList.Upgrade_Currency, gmPVPPropertyList.PVP_Team)` (AS2 l.~173900) [C]. **So in-match level, XP, skill
points and gold are plain champion properties: sending them (create `0x4`, or the single-property events `0x6/0x7/0x13B`)
is all the HUD needs to show them** [C].

C++ HUD watcher (listener registered at VA `0xa8c8a5` on `0x10000C85`, `0x100001AF`, `0x1000035E`, `0x10000CD6`; callback
`0xa93e60`) [C]:
- `SkillPoints > 1` -> coaching flag (spend-your-points hint, HUD element 27 `SkillPointSpendReminder`), `0xa93b70`.
- Gold `>= 2500`, or `>= 500` with 0 artifacts, and fewer than 6 artifacts -> "you can shop" hint, `0xa93c50`.
- `0x10000C85` (bool) toggles another coaching flag.

### 1.2 GM_Advancement (ranking, XP bar thresholds) [C]

Flash ids (AS2 getters) and the C++ dispatchers:

| Id | Name | Kind | C++ side |
|---|---|---|---|
| `0x10000009` | `Query_Advancement__InqLevelCap` | query | script handlers only |
| `0x10000011` | `Query_Advancement__InqXPForLevel` (level -> `iXP`, `iXPPreviousLevel`) | query | script handlers only |
| `0x10000063` | `InqSkillRank` | query | dispatcher `0x90e840`, script handlers only |
| `0x1000006A` | `InqCanRankSkill` -> ErrorType | query | dispatcher `0x90e580`, script handlers only |
| `0x1000009B` | `Notice RankSkill(agent, slot)` | notice | dispatcher `0x90e9a0` -> `0x964110` (run script handler) only |
| `0x1000023C` | `InqNextRecommendedSkillToRank` | query | dispatcher `0x90e6d0`, script handlers only |
| `0x10000054` | `Notice SkillRanked(iid, slot, rank, ?)` -> Flash `GM_Advancement.RecvNotice_SkillRanked` | notice | `0x90eaf0`, raised only by script native `0xE70015` (`0x963040`) |
| `0x100004F9` | `Notice XPGained(iid string, amount)` -> Flash | notice | `0x8a9d30`, fed by the XP floaty accumulator `0xa74a30` (sums for 0.2 s per agent) [P: fed by XP property deltas] |
| `0x10000302` | `ShowExperienceRings` | notice | (Flash -> C++) |
| `0x10000423` | `InqSkillPointsAvailableString` | query | ? |

None of these ten ids is one of the 44 network-readable notices: **the server cannot answer them over the wire** [C].

**Who answers them: the WLib.** Script natives `0xE700xx` (registered at `0x965f34`) register/unregister script functions
as handlers (`0x8788b0` / `0x878910` -> generic `0x484390`) [C]:

| Native | Function | Effect |
|---|---|---|
| `0xE70012` / `0xE70013` | `0x962e00` / `0x9630b0` | register / unregister RankSkill handler |
| `0xE70006` / `0xE70007` | `0x962e60` / `0x963110` | InqCanRankSkill |
| `0xE70009` / `0xE7000A` | `0x962ec0` / `0x963170` | InqLevelCap |
| `0xE70017` / `0xE70018` | `0x962f20` / `0x9631d0` | InqNextRecommendedSkillToRank |
| `0xE7000C` / `0xE7000D` | `0x962f80` / `0x963230` | InqSkillRank |
| `0xE7000F` / `0xE70010` | `0x962fe0` / `0x963290` | InqXPForLevel |
| `0xE70015` | `0x963040` | raise SkillRanked |

In the WLib bytecode (code section at record `+0x20`, 0xE6AC bytes; native call = opcode `0x0015, argbytes, u32 id`;
function reference = push `0x8000|type, method`) all twelve register/unregister calls sit in **one WLib type, `0x233`**
(vtable in section 16, class header `1 | 0x233 | 0 | 0 | 28 slots`): method `0x9654` registers the six handlers
(`0x8233:0006, :0005, :000A, :0008, :0009, :0002`), method `0x96d4` unregisters them [C]. The type's other methods are the
handler bodies [P for the exact mapping]:

| WLib method | Reads | Probable role |
|---|---|---|
| `0x9194` | `Level 0x10000167` | level / XP queries |
| `0x91e4` | `0x10000975` | level cap? |
| `0x9248` | `SkillPoints 0x100001AF` | points available |
| `0x926c` | ErrorTypes `SkillRank_Skill_NotDefined 0x1000002D`, `NotManuallyChanged 0x10000017`, `InvalidRank 0x10000008`, `NotHighEnoughLevel 0x10000022`, `NotEnoughSkillPoints 0x10000014`, `NeedPrerequisite 0x10000072`; `0x10000B0C` | **InqCanRankSkill** |
| `0x93f8` | `0x10000B0C`, `InvalidRank` | InqSkillRank / RankSkill |
| `0x97bc` | `0x1000034B` (build skill order), `0x10000AA1` | **InqNextRecommendedSkillToRank** (see 1.3) |
| `0x9a30` | `SkillRank_AtMaxRank 0x10000018` | rank cap check |
| `0x9a88` / `0x9b70` | native `0xE70015` | raise SkillRanked (the "+" feedback) |

The natives these methods call are all local (GetSkillRank `0x105000A` -> `0x863ce0`, slot skill `0x1050005` -> `0x85d1f0`,
skill data `0x1050008`, local agent `0xF80001`, IID of a handle `0xC90001`, DID/array helpers); **none reaches the network
send `0x444a90`** in a depth-4 call scan [P]. How the original forwarded a rank-up to the server is therefore not found
(candidates: a property written by the script and replicated through the property-channel events `0x103/0x134/0x10B/0x8C/0xA3`,
or a VM object-method call the scan cannot see).

**Why nothing is registered here [C for the fact, open for the cause]:** no entity class record uses WLib type `0x233`
(every champion class `0x40...` uses type `0x27B`, the player class `0x4000007C` type `0x21C`; pattern scan of all packs),
the type number appears nowhere else in the WLib, and the exe has no immediate `0x233` near the WLib API. The type is a
root "system" class instantiated by something not found statically; in our sessions it never is, so every advancement
query returns its default.

**Answer to "does a correct server reply make the exe patches unnecessary?"** Not by replying alone [C]:
1. The "+" calls `InqCanRankSkill` first; with no handler it returns a non-zero error and Flash never calls `RankSkill`.
2. Even `RankSkill` only runs script handlers (`0x90e9a0` -> `0x964110`); the C++ side sends nothing (the client->server scan
   found no rank event).
3. The XP bar's `InqXPForLevel` / `InqLevelCap` also fail (Flash logs "MAX XP FOR LEVEL FAILED", falls back to test
   values).
The patches are needed **until the trigger that instantiates WLib type `0x233` is found**. Once it is, the client would
compute can-rank / recommended / XP thresholds itself from the properties above and the champion build record (1.3), and
the server would only keep `Level`, `XP`, `SkillPoints` and `0x100000AF` correct. Runtime test to settle it:
`tools\diag.py` breakpoints on `0x962e00` (register RankSkill handler) and `0x962e60` -- if they never fire in a match, the
type is never created; then trace WLib object creation for type `0x233`.

### 1.3 Champion build records (recommended skills, artifacts, amplifiers) [C]

The skill set / champion twin points to **builds** through property `0x10000CEB` (Gaslight Batman: `0x48000615` and
`0x49000086` -> `0x4800137C`, `0x4800137D`, `0x4800137E`, `0x4800137F`, pack `0xA0000122`). One build record:

| Key | Content (Batman build `0x4800137C`) |
|---|---|
| `0x1000095F` | build name (string token) |
| `0x1000095E` | build icon `0x13...` |
| `0x1000034B` | **skill order**: 19 enums (`0x10000353`) = slot to rank at each skill point: 1,2,1,3,2,4,1,2,1,4,5,2,5,4,5,3,3,4,3 (Q/W/E/R 4 ranks each, passive 3; R at the 6th, 10th, 14th, 18th point) |
| `0x10000AA1` | enum 4 (build role / index?) [G] |
| `0x10000478` | recommended artifact order: 21 x {`0x10000475` = 3 (content type Artifact?), `0x10000694` artifact `0x400004..`} |
| `0x1000084C`, `0x1000084D`, `0x1000084E`, `0x1000084F`, `0x10000893` | smaller artifact groups (starter / core / situational?) [G] |
| `0x10000A12` | 4 augments (`0x1000095A` -> `0x400006..`); `0x1000098F` 3 mods (`0x400008..`) -> the champion's default amplifier set [P] |
| `0x1000064E` | two related records (`0x48000780`, `0x48000529`) |

19 skill points over the levels implies **level cap 20, one point per level from 2** (or levels 1-19) [P].

### 1.4 XP, level curve, gold, kills, respawn

| Item | Finding | Tag |
|---|---|---|
| XP per level / level cap | No numeric curve in the client data: a scan of every `0x48` record of `0xA00000B3` for monotonic arrays of 15-60 numbers found none. Flash gets the thresholds only through `InqXPForLevel` (WLib). The server owns the curve | [P] |
| XP sources | No server script (0x34) grants XP; variable names in all decoded scripts mention no XP. XP for kills/minions is server code that did not ship | [P] |
| Gold sources | Script node **`0x10000065` GrantCurrency** (`entity, amount` [type 0/4, flags 8/128]); e.g. `0x340004AE` grants `CurrencyGrant` (stat 12) when an enemy **Surveillance Camera `0x40000265`** is killed (event `0x10000098`). Node `0x100000EC` SetCurrencyOption `UseTeamwideCurrencyGains`. Passive gold / kill gold otherwise server-side | [C] |
| Gold display | Flash `UI_ShowFloatyCurrencyOverEntity(iidAgentDefeated, fCurrencyEarned)` (`Notice_Upgrade__UI_ShowFloatyCurrencyOverEntity 0x100004D5`), `DisplayFloatyCurrencyChanged 0x10000506(iid, old, new)`, `...Denied 0x10000505`. These ids are local notices: driven by the `0x1000035E` property change [P] |
| Can shop | Base aura sets attribute `0x10000A23` (`HandleCanShop`, node `0x10000008` in a base script); Flash asks `InqCharacterCanShop` | [C] attribute / [P] link |
| Kill feed / billboards | Network notices `0x1000021C` / `0x100002B2` (big list layouts, see protocol map), `0x100002EB` ShowAnnouncement (`BillboardUpdateType`: 2 Generic, 6 Location, 7 Tie, 8 Loss, 9 Win, 10/11 Team victory) | [P] |
| Kill / assist pair | Network notice `0x100000CA` `(u64, u64)` (probably killer, victim); `0x100000CD` same shape | [G] |
| Respawn timer | Network notice **`0x10000090` DefeatStatusUpdated** = Flash `(iidPlayer, state, tsTimeOfNextState)`: state 3 Incapacitated -> "Incapacitated2" panel, 2 Dead -> "DeadTimer" panel counting to `tsTimeOfNextState`, 4 Alive -> respawned. **`0x100000BC` ...ForEntity** = `(iidPlayer, iidAgent, eKillerPerceivedType, state, timeOfNextState f64)` for scoreboard/portraits. **`0x100000BA`** pauses an entity's timer. Flash asks `Encounter.UI_ReadyForDefeatStatus` first | [C] layouts/fields |
| Respawn durations | Not in client data | [P] |

---

## 2. Pre-match loadouts

### 2.1 Artifacts (in-match shop, "Artifact Foundry")

Records (catalog `artifacts.tsv`, `records.tsv`): foundry configs `0x48000163` (228 artifacts, filter groups `0x10000844`) and
per-mode/map `0x48000EA9`, `0x48000EAA`, `0x4800118B`, `0x480007B0` (210; maps point to one through `0x1000081E`);
artifact = `0x4000....` with tier, cost, upgrade-from, stats (`item_stats.tsv`). Bought in the match with
`Upgrade_Currency`; up to 6 (`Upgrade_CurrentItemCount < 6`) [C].

| Direction | Event / notice | Layout | Meaning | Tag |
|---|---|---|---|---|
| C->S | `0x208B` (sender `0x88c410` <- `0xa17ce0` = `Notice_Upgrade__PurchaseUpgrade 0x10000125`) | `u32 artifact DID` + 16 bytes (selection handle from `0xa0f5d0`) | buy | [C] |
| C->S | `0x20A7` (`0x88c530` <- `0xa17d90`, `SellUpgrade 0x10000144`) | `u32 artifact | u32 slot` + 16 bytes; only if the slot holds that artifact | sell | [C] |
| C->S | `0x212C` | `u32list` | artifact skill-slot mapping (`ChangeArtifactSkillSlotMapping 0x1000042C`) | [P] |
| S->C | `0x20E2` | `{u32 QueueKey}` + amplifier-set struct | `UpdateCurrentUpgrades` + `UpdatePowerGraphValues` | [P] |
| S->C | `0x20DD`, `0x212B` | `list<u32>` | current upgrade list on the upgrade component (`obj+0xA4`) | [P] |
| S->C | `0x2078` | `list<u32>` | next recommended upgrade | [P] |
| S->C | notices `0x10000414`, `0x10000364`, `0x100004D6` | `(u64,u32)`, `(u64,u32,u32,u8)`, `(u64,u32)` | upgrade group (cooldown / activated artifact?) | [G] |
| Flash | `UpdateCurrentUpgrades(iidAgent, upgrades[], iconDIDs[], stackSizes[], modDIDs[], modBrandOverlayIcons[])` | | the HUD item bar | [C] |

The rest of the shop (`InqAvailableUpgrades`, `InqCanBuyUpgrade`, `InqUpgradeDetails`, `InqBuildOrder`, ...) are local
queries answered by the C++ upgrade component from the records; `InqBuildOrder` / recommended use the build record's
`0x10000478` (1.3) [P]. Gold is the champion's `0x1000035E`; the server must also apply the artifact stats (the client only
displays).

### 2.2 Amplifiers ("aumentos": augments and mods)

Lists: `0x48000A49` augments (162), `0x48000A4A` mods (172) (property `0x1000099F`, element `0x100009A0`) [C]. An
**amplifier set** has 7 entries (`entryOne..entrySeven`, augments + mods; Batman's default build has 4 augments + 3 mods) [C].

Amplifier-set wire struct (reader `0x86fb20`, 0x50 bytes in memory; mapped to Flash by `0xa64520`) [C for the fields Flash
reads]:

`u32 slotID | u64 (id, not shown) | u32 characterReference (champion DID) | StringInfo name | wstr custom name | u32 icon DID |
{cint n | n x u32 amplifier DIDs}` -> Flash `(uiAmplifierSlotID, didCharacterReference, strAmplifierNames, didIcon,
didEntryOne..Seven)`.

| Direction | Id | Layout | Meaning | Tag |
|---|---|---|---|---|
| S->C | `0x2090` | `u8 0 | u32 total | u32 max | u32 n | n x set` | `NotifyListAmplifierSets(total, max, slots, champions, names, icons, entries 1-7)`; also a scorecard prerequisite | [C] |
| S->C | `0x20C7` | `u8 0 | set` | one set (`NotifyAmplifierSet`) | [C] |
| S->C | `0x2052` | `u8 0 | u32 ErrorType` | `Amplifier_SaveAmplifierSet_Failed 0x10000063`, `LoadAmplifierSets_Failed 0x10000064`, `SetNameTooLarge 0x10000065` | [C] |
| S->C | `0x2107` | `{u32 n x (u64, u32, StringInfo-ish, u32)}` | `NotifyContextualAmplifierData(boutiqueIDs, amplifierDIDs, currencyNames, currencyValues)`: Steam store prices | [P] |
| S->C | `0x204A` | `u8 0 | u32 | set | u64` | lobby: `PlayerPickedAmplifierSet(team, teamIdx, iidPlayer, slot, icon, name, set, bMine)` | [C] names |
| S->C | `0x2060` | full lobby state (includes sets and Stolen Powers) | | [C] |
| C->S | `0x200D` | `u8 slot` | lobby `RequestChangeAmplifierSet` | [P] |
| C->S | `0x2057` | empty | `RequestMyAmplifierSet` | [P] |
| C->S | `0x20FC` | name (<= 21 chars) + 7 values | `UI_SaveAmplifierSet` | [P] |

Owned augments / mods come from **`0x20B8` item statuses** with content types 12 (Augments) / 13 (Mods) (Flash builds the
amplifier panel from `OwnableData`; details via local `InqAugmentData` / `InqModData`) [P]. In the match the set's stats are
the server's job; the scoreboard and loading screen show it through `AddParticipant(... uiAmplifierSetSlot,
didAmplifierSetIcon, strAmplifierSetName, aAmplifierSetModifiers)` [C names].

---

## 3. Account and meta systems

### 3.1 What the landing screen needs (current `icserver/messages.initial_events`, order matters) [C]

`0xEB` local player -> `0x20B8` item statuses -> `0x20ED` champion data -> `0x209D` master character list -> `0x2024`
encounters -> `0x216A` server options -> `0x2120` achievements -> `0x218B` game settings (e.g. `FeaturedMap_PVP`) ->
`0x215D` account flags -> `0xCE` character set -> **`0x2080` account level (last: opens the landing gate)**.

### 3.2 Event table

| System | Id (S->C unless noted) | Layout / Flash args | Notes | Tag |
|---|---|---|---|---|
| Account level (protector) | `0x2080` | `u8 0 | level | prevLevel | xpToNext | xpTotal | xpEarned | xpBonus | f32 pct | f32 prevPct` | login + end of match; LevelUp ribbon data also has hard/soft currency rewards | [C] |
| Protector advancement status | (computed) | `ProtectorAdvancementStatus`: 1 Player, 2 Trainee, 3 FirstTimePlayer (from trainee achievements, see `scorecard.py`) | | [C] |
| Account-level unlocks | record `0x48000372` (`0x10000589`: 20 x {`0x1000058A` level, `0x1000058C` enum}) levels 1,3,5,10,...,210 | probably features/rewards unlocked per account level | [G] |
| Currency | `0x2081` | `u8 0 | u32 hard | u32 soft` | **hard = Crisis Coins** (Steam boutique), **soft = Merits** (`PostMatchRewardType` 1 Merit, 2 CrisisCoins). No Gems/Prestige in this build | [C] |
| Merit reward | `0x20B9` | base, daily (first win), f32 time till next daily, streak, potential daily, potential streak, 2 tooltips, u32 | end-of-match and balance changes | [C] |
| Owned items | `0x20B8` | `u8 0 | u32 n | n x (u32 DID, u32 ContentStatus, u32 ContentType, u8 owned, u32 count)` | ContentStatus 1 Free, 2 Available, 3 Disabled, 4 Unreleased, 5 Hidden, 6 AlwaysOwned, 1001 Innate, 1002 Unavailable. ContentType 1 Character, 2 StolenPower, 3 AvatarIcon, 4 Skins, 5 Amplifier, 6 Boost, 7 Currency, 8 Bundle, 9 Skill, 11 Artifact, 12 Augments, 13 Mods, 17 Achievement, 18 RewardSet, 20 AccountXP, 25 LoginReward | [C] |
| Champions / costumes | `0x20ED`, `0x209D` (per champion `u32 DID, u32, u32, u32, u64, u64`: level/XP per champion [P]), `0x209E` delta | | [C] layout |
| Champion level / XP | `0x2104` | per champion end-of-match level/XP + accolades | | [C] |
| Header / protector icons (profile) | `0x2190`, `0x2154`; C->S `0x2093` `UI_SetProtectorIcon u32,u32` | header name + 5 icons with names/descriptions | | [C]/[P] |
| Achievements | `0x2120` progress, `0x211F` pending banners, `0x21A6`; C->S `0x211D` RequestAll, `0x211E u32`, `0x212E` | categories 1 General, 2 Training, 3 ProtectorLevel, 4 ChampionLevel | | [C] |
| **Daily / weekly quests** | the same achievement system: `AchievementRepeatType` 2 Daily, 3 Weekly, 4 Monthly, 5 BiWeekly; progress in `0x2120` (`TimeValid`, `TimesCompleted`) | no separate quest event exists | [C] enum / [P] usage |
| Rewards | `0x2125` pending reward sets, C->S `0x2124` / `0x2128` claim; `0x2095` item fulfilled ribbon | see `reward_re.txt` (working in game) | [C] |
| Login rewards | `0x2197` reward sets (LoginReward), `0x219D` none eligible; Flash `DeliverLoginRewardSet(lastDay, eligible, days, labels, quality, bestowal, rewardTypes, descriptions, mysteries, itemDIDs, icons, names, quantities)`; C->S notices `QueueLoginReward`, `ReadyForLoginRewardSet` | `RewardSourceType` 2 LoginReward | [C] Flash / [P] wire |
| Store (Crisis Coins) | `0x210C` success, `0x210D` error (`ContextualPurchase_GeneralError 0x10000068`, `InsufficentFunds 0x10000069`), `0x210F` price changed `(boutiqueID, didItem, currencyName, initial, orderID, final)`; Flash `PurchaseContextualItem(boutiqueID, didItem, currencyName, price)` | Steam microtransactions; for a preservation server: grant directly or disable | [C] |
| Purchase variant in lobby | `GM_Lobby.SendNotice_RequestToPurchaseVariant` | | [P] |
| Accolades | `0x2188` end of match, `0x2186` best map/champion accolades; C->S `UI_RequestBestAccolades` | `AccoladeRankType` 1 Gold, 2 Silver, 3 Bronze | [C] |
| Standings / ranked | `0x219E`, `0x219F`; leaderboards `0x21A2`/`0x21A3` (C->S `0x21A4`); `RankedDisplayTier` 1 Diamond, 2 Gold, 3 Silver, 4 Bronze | | [C] |
| Account encounter stats | `0x2115` (C->S `0x2116`) | long per-encounter stat rows | [C] layout |
| Friends (contacts) | `0x2003`, `0x2013`, `0x2014`, `0x2018`, `0x2020`, `0x202F`, `0x203A`, `0x203B`, `0x204F`, `0x2051`, `0x2058`, `0x205E`, `0x2065`, `0x208F`, `0x20AE`, `0x20C5`, `0x20CB`, `0x20CC`, `0x20EC`, `0x2161`, `0x219C`; C->S `0x20C1`, `0x2094`, `0x20E6`, `0x20FB`, `0x2199/0x219A`, `0x20A1`, `0x20C6`, `0x219B`, `0x20F4`, `0x2066`, `0x200B` | contact = `u64 iid, u64, wstr name, u64, wstr, wstr, u32, u8, 5 x icon u32, u32 level, wstr status, u32 presence`; `ContactPresence` 1 Online ... 9 InCustomMatch; `ContactListType` 1 Friend, 2 Ignored; errors `0x1000005A..0x10000070` | an empty list (`0x203B` n=0) is probably enough for the menu | [C] fields / [G] minimum |
| Party (grouping) | `0x2033` invite dialog, `0x2070` can create group, `0x2071` group state, `0x214C`, `0x217D` | | [C] layout |
| Custom match | `0x2011`, `0x2012`, `0x201F`, `0x2027`, `0x202E`, `0x2035`, `0x2036`, `0x203F`, `0x2040`, `0x2041`, `0x2042`, `0x2048`, `0x205D`, `0x2076`, `0x2103`, `0x2109`, `0x2151`, `0x217C` | | [C] layout |
| Chat | C->S `0x20A6` channel list (wrapper `0x37dfc6c`, team 1/2 `0xdc6f571`/`0xdc6f572`), `0x20F6` send text, `0x20CD`/`0x2112`/`0x2148` name commands; S->C `0x2135` member list `(StringInfo room, list<u64>)`, `0x20B0` `(wstr, StringInfo, wstr)`, `0x20B6`, `0x2134`, `0x2183`, system text `0xAB`/`0xC9` | `ChatLogType` 2 General, 3 Private, 4 Group, 8 All, 9 Team, 1 CustomMatch. The event that delivers another player's line is not identified (candidates `0x20B0`, `0x2183`) | [C]/[G] |
| Server preferences | `0x216A`, `0x218B`; C->S `0x216E` | | [C] |

---

## 4. End of match

| Step | Id | Notes | Tag |
|---|---|---|---|
| In-world result | `0x100002EB` ShowAnnouncement (type 9 MatchWin / 8 Loss / 7 Tie, 10/11 team victory) | | [C] |
| Match ended | notice `0x1000000E` `(winning team, player team, f32 seconds, tier, f32 target time)` + `0x2038` | client leaves the world itself | [C] |
| Scoreboard | `0x2045` -> Flash `UI_SendEndOfMatchStats(accountIIDs, playerIIDs, icons, names, protectorChampLevels, isBot, isFriend, isIgnored, inMatchLevels, teams, kills, deaths, assists, currency, coinPickups, amplifiers, column1-5, grid labels / section flags / tooltips, grid values for players 1-10, team sums 1-2, yourIID, ...)` | tutorials skip it (`0x10000D0B`) | [C] Flash fields |
| Scorecard prerequisites | `0x2190`, `0x2045`, `0x2188`, `0x2080`, `0x2081`, `0x20B9`, `0x2104`, `0x2090`, `0x219F`/`0x219E` (+ power graph / current upgrades outside tutorials) | `icserver/scorecard.py` | [C] |
| Rewards panels | `0x212E`->`0x211F`, `0x2124`->`0x2125`, claim `0x2128`; level-up ribbon from `0x2080`/`0x2104`; `0x2095` item fulfilled | `reward_re.txt`; confirmed in game (fase3-ff) | [C] |
| Back home | `0x2021` exit lobby; client `0x20A6` / `0x20C4` / `0x20BA` after the end page | | [C] |

---

## 5. What a data-driven server should send (summary)

1. **In match:** keep `Level`, `XP`, `SkillPoints`, `Upgrade_Currency`, `Upgrade_CurrentItemCount` and `0x100000AF` on the
   champion; respawn with `0x100000FA` + notices `0x10000090` / `0x100000BC`; artifacts with `0x20DD`/`0x20E2` after each
   `0x208B` / `0x20A7`; gold floaties follow the property.
2. **Ranking:** the exe patches stay until WLib type `0x233` can be instantiated; the skill order for "recommended" is the
   build record's `0x1000034B` (no need to hard-code it); level cap 20 / one point per level [P].
3. **Lobby:** `0x2090` (+ `0x204A` / `0x2060`) for amplifier sets, built from the build record's default augments/mods or
   saved sets; answer `0x200D` / `0x20FC`.
4. **Account:** the login list in 3.1 plus, when the menus are wanted, empty contact / party / login-reward replies
   (`0x203B`, `0x219D`), currency `0x2081` (Crisis Coins / Merits).

## 6. Open questions

- What instantiates WLib type `0x233` (the advancement handlers) -- runtime check on `0x962e00`; and how its RankSkill
  handler reaches the server.
- Exact method <-> handler mapping inside type `0x233` (needs a WLib VM decoder: method references are `0x8000|type:id`,
  not vtable indices).
- Meaning of `0x10000975`, `0x10000B0C`, `0x10000AA1`, `0x10000C85`, `0x48000372`'s enum.
- XP curve, XP / gold per kill, respawn durations: not in the client (server rules to choose).
- Which event delivers chat lines from other players.
