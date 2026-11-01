# In-match shop (Artifact Foundry), items, inventory and currency (static analysis, 2026-10-21)

Sources: `InfiniteCrisis.exe` (Ghidra via REA, capstone; all addresses are VAs, image base 0x400000), the player's
packs (pack `0xA00000B3` holds every artifact record and the foundry lists), the AS2 dump of the HUD
(`old_files/tools/gfx/classes_all.txt`) and the decoded server scripts (`data/script_trees/`). Nothing here has been
checked against a running client: no `0x208B` / `0x20A7` appears in any log so far.
Confidence tags: **[C]** confirmed by code or data read directly; **[P]** probable (consistent evidence, not proven);
**[?]** guess / open.

The game calls items **artifacts** / **upgrades** (C++ system `GM_Upgrade`, Flash `GM_Upgrade` + `GM_Artifact`),
the shop the **Artifact Foundry**, and the in-match money **credits** (`Upgrade_Currency`).

## 0. Short version (what a server must do)

1. Before the match: the player object carries the encounter DID (`0x100001D3`, already sent by `ics`). When it
   changes the client reads the shop list from the **encounter template's `0x1000081E`** itself (`0xA91670` ->
   `0xA908F0`). Nothing has to be sent for the shop catalogue, prices, tooltips or build trees: the client reads all
   of it from its own packs. **[C]**
2. On the champion: `0x1000035E` Upgrade_Currency (f32) = credits; `0x10000A23` (bool) = may shop while alive
   (in base); optional `0x10000B55` / `0x10000B52` (free-shopping flag / whitelist). **[C]**
3. Client buys -> event `0x208B` `u32 artifact | handle`. Client sells -> `0x20A7` `u32 artifact | u32 slot | handle`.
   The client then **locks the shop until the server echoes the handle with event `0x2086`**. **[C]**
4. Server answers a valid purchase/sell with: new `0x1000035E` (property update on the champion), event **`0x20E2`
   to the champion object** with its 6 inventory slots (+ amplifier-set tail), event `0x2086` (handle) to unlock, and
   then applies the item: stat properties, passive status effects, active skill in item skill slots 10-15. **[C]/[P]**
5. Credits come from server logic: kills/assists/minions are not in client data except a few script nodes
   (`GrantCurrency` 0x10000065). The floaty "+N" over a killed entity is notice `0x100004D6` (`u64 iid | f32`). **[P]**

## 1. Data: records and keys

### 1.1 Artifact record (the `0x49` twin of the `0x40` class in a foundry list; header `did | 0 | count | entries`)

| Key | Kind | Meaning | Conf | Evidence |
|---|---|---|---|---|
| `0x10000372` | string | name (table `0x2B000097`), "(n)" suffix = tier | C | catalog_re.txt, exe `0x857883` |
| `0x10000825` | string | description (not copied) | C | catalog_re.txt |
| `0x10000436` | DID | icon `0x13…` | C | |
| `0x1000048A` | enum | category 1 Attack, 2 Defense, 3 Power, 4 Utility (= filter group) | C | exe `0x858B88`, `0x9D2538` |
| `0x1000036C` | f32 | **build cost** (cumulative price of this tier, credits) | C | `0x857910` reads it; `0x9D0030` price |
| `0x1000045E` | f32 | **sell-back value** (~0.75 x cost, some tier-1 0.9) | C | `0x85794E`; Flash `aArtifactSellBackAmount` |
| `0x10000698` | DID | **upgrade-from** (previous tier's `0x40` class); absent on tier 1 | C | `0x9D0C10` walks it to find the owned component |
| `0x10000697` | DID | **upgrades-into** (next tier); absent on the last tier | C | data: always the reverse of 698 (e.g. `0x400004AB` -> `0x4000048F`) |
| `0x10000684` | array | stat bonuses: `0x10000683{0x1000068B op (9 add, 10 add %), 0x1000068C table{stat key: f32}}` | C | `0x9D0F13`, `0xA51B4E` (power graph) |
| `0x100004EA` | array | passives: `0x100004EB{0x1000037D -> 0x48 effect record}` | C | `0x857A1E`, `0x9D12A1` |
| `0x100008E1` | DID | active ability record `0x48…` (its `0x100008E5` skill block: `0x10000328` script etc., like Stolen Powers) | C | `0x8579DE` |
| `0x100005F7` | int | stack limit (absent on all 228 -> 0 -> an artifact can be owned once) | C | `0x857970`, `0x9D1CF0` result 6 |
| `0x10000845` | array | extra filter keys (`0x10000839` stat key) | C | foundry filters |
| `0x10000827` | int 1..3 | display position / column in the foundry | P | Flash `aDisplayPosition`; values 1..3 independent of tier |
| `0x100008DC` | bool | tooltip updated dynamically (21 items: Gambits, Ruby of Life, Logoz, Lantern…) | P | Flash `aHasDynamicallyUpdatedTooltips` |
| `0x10000B5E` | bool | on all 228 (6 without value) | ? | |
| `0x1000036E` | string | "None" on all | ? | |

Stat keys are the champion's own f32 stat properties (Health `0x10000426`, Will `0x10000486`, Attack Damage
`0x10000B76`, Power Damage `0x10000B75`, Attack Armor `0x10000B84`, Power Armor `0x10000B7A`, Attack Speed `0x100006FE`,
Move Speed `0x100005E4`, Health Regen `0x10000140`, Will Regen `0x10000483`, Crit `0x10000B46`/`0x10000B80`, CDR
`0x10000B7B`, Resilience `0x100004AA`, Att Pen `0x10000B83`/`0x10000B7D`, Pow Pen `0x10000B7E`/`0x10000B82`, Att
Lifesteal `0x10000B7C`, Pow Lifesteal `0x10000B7F`; filter-only "Credits" `0x10000852`). See `catalog/data/item_stats.tsv`.

**Build tree / pricing (client `0x9D1780` + `0x9D0C10` + `0x9D0030`) [C]:** an artifact's price is
`cost(0x1000036C) - mod discount(0x873450, from the champion's amplifier mods)`, floored at 0. If the inventory holds
an artifact reachable through the target's `0x10000698` chain (any lower tier of the same line), that component's
(discounted) cost is subtracted and **its slot is reused** (the upgrade replaces it). So buying tier N while owning
tier N-1 costs `cost(N) - cost(N-1)`; e.g. Batman's Utility Belt 750 -> 1750 -> 2750. Selling refunds `0x1000045E`
(Flash queries `InqSellDifferenceSlot` / `InqSellDifferenceByDID` show the difference) [P for the exact sell formula].

**Passive effect records** (`0x48…` from `0x1000037D`): status-effect records; 48 of 73 carry a server script
(`0x10000242` -> `0x34…`, max stacks `0x10000063`, `0x10000334`); 25 are "stat keywords" without script
(`0x1000046F{0x1000046E{0x10000450 stat key, 0x1000044F f32 value, 0x10000453/0x10000AF3 op, 0x1000082D /
0x10000452 texts}}`), e.g. `0x480007DC` (the five "Gambit" tier-2 items): +0.2 of `0x10000C77` (credits income
stat? **[?]**). Server work: apply them as statuses on the owner (`ics` status runtime) or as stat modifiers.

**Active abilities** (32 artifacts, 29 records, table in section 6): skill records with a server script, cast from the
item skill slots. Champion properties `0x100008E5`, `0x100008E7`, `0x100008E9`, `0x100008EB`, `0x100008ED`,
`0x100008EE` are the slot 10-15 skill tables (properties.tsv); the HUD slot order is exchanged with event `0x212C`
(client -> server, `u32list`) / `0x212B` (server -> client, sets upgrade component `+0xB0`, Flash
`SetUIArtifactSkillSlotMapping`). **[P]**

### 1.2 Counts

228 artifacts (catalog `artifacts.tsv`): tiers 1:68, 2:68, 3:58, 4:30, none:4; Attack 73, Power 71, Defense 64,
Utility 20; 32 with an active, 100 with passives. Consumable-like lines: Modular Health Vial `0x40000925/29/2A`,
Will Vial `0x40000927/26/28`, Tektite Vial `0x400008C3/C2/C1` (100 / 250 / 500, active skills `0x48000CD1..CEF`).
Amplifiers (162 augments + 172 mods, `amplifiers.tsv`) are the pre-match loadout, not shop items; mods change an
artifact's price/stats/keywords in the match (`0x1000098C` discount etc., catalog_re.txt).

### 1.3 Shop list per encounter (foundry configs) [C]

A foundry config record (`0x48…`, header `did | 0 | n`) has `0x1000042C` (array of `0x10000693` DIDs = artifacts
offered, in display order) and `0x10000844` (18 filter categories `0x10000832{0x10000845 keys, 0x10000843 group,
0x1000083A label, 0x10000837 filter id}`). The encounter template (`0x49…`, header `did | 2 | n`) points at one with
**`0x1000081E`**. Client: `0xA908F0(encounter)` maps a `0x40` DID to its `0x49` twin, reads `0x1000081E`, loads the
list (`vfunc+4`) and the filters (`0xA8EBB0`, key `0x10000844`); `0x9D1B00` reads `0x1000042C`. Triggered by the
player property `0x100001D3` (listener `0xA91670`).

| List | Size | Referenced by (encounter template `0x1000081E`) | Notes |
|---|---|---|---|
| `0x48000163` | 228 (all) | not by any encounter; hits inside `0x48000C01`, `0x4800000F`, `0x48000C89`, `0x49000D45` and one unowned (b3 offset `0xC7BE54`) | probably the out-of-match foundry / collection preview (Flash `FakeFoundryNotice`) [?] |
| `0x48000EA9` | 210 | `0x49000991` Tutorial Basic (map `0xA0C112CA`), `0x49000A81` Tutorial Intermediate (`0xA0C112C2`), `0x49000CA6` Crime Alley 1vAI Tutorial (`0xA0C112BA`), `0x49000C82` Crime Alley v AI, `0x49000B6B` Gotham Divided v AI, `0x49000D63`, `0x49000D71`, `0x49000E61` (`0xA0C112B2`), `0x49000E62` (`0xA0C11AD2`), `0x49000E65` (`0xA0C112B2`), `0x49000E68` Crime Alley Clash 1v1, `0x49000E6D` (`0xA0C11ACA`), `0x49000E74` Crime Alley Clash 2v2, `0x49000EC0` Apokolips Causeway 1v1 (`0xA0C10AE2`), `0x49000399` Gotham Divided (`0xA0C11AD2`) | = 228 minus 18 (below) |
| `0x48000EAA` | 210 | `0x49000B6A` Coast City v AI, `0x49000E5A` (`0xA0C122DA`), `0x49000270` Coast City (`0xA0C122E2`), `0x4900039C` Crisis Labs Coast City | identical to EA9 (same order) |
| `0x480007B0` | 210 | `0x4900013E` Gotham Heights, `0x49000B6C` Gotham Heights v AI (`0xA0C11AF2`) | EA9 with 12 swapped (below) |
| `0x4800118B` | 210 | no encounter; only inside `0x1D000918` | same set as EA9, other order |

- Not in EA9/EAA (only in 163): Two Face's Coin (1)(2) `0x40000493`/`0x400004AE`, Joker's Crowbar (1)(2)
  `0x40000507`/`0x4000049E`, The Crime Bible (1)(2) `0x40000577`/`0x4000056E`, and the 4-tier lines Promethium Mace
  `0x4000056F/55F/561/564`, Radion Shard `0x40000579/580/584/586`, Hawkman's Harness `0x400005A1/59F/5A0/5A2`.
- Gotham Heights (`0x480007B0`) replaces the starter lines Marauder Shield `0x40000494/4CD/4E8/4A8`, Marauder Ring
  `0x400004D7/499/503/4C7`, Marauder Knife `0x400004E2/4A5/4BD/4F8` with Promethium Mace, Radion Shard and Hawkman's
  Harness (map-specific starter items).
- Encounters with an unknown display name are listed with their map pack (template `0x10000406`).
- Extra per-player restriction (tutorials): agent property **`0x10000B52`** (array of allowed artifact DIDs,
  whitelist) and **`0x10000B55`** (bool). See 3.2.

## 2. Currency

| Id | Where | Meaning | Conf | Evidence |
|---|---|---|---|---|
| `0x1000035E` | champion (f32) | **Upgrade_Currency** = in-match credits. Flash `gmUpgradePropertyList.Upgrade_Currency_Property` = 268436318, read with `PropertySystem.InqProperty` on `m_iidPlayerControlledAgent`, shown `Math.floor`; change -> `DispatchUpgradeCurrencyChange` | C | AS2 dump l.173278-174090, 283171; exe `0x9D1860` (can-afford check), `0xA8C8CF` (listener), `0xA93C99` (shop hint), `0xA9E2FD` (setter) |
| `0x10000CD6` | champion (int) | **Upgrade_CurrentItemCount** = non-empty slots; the client recomputes it from `0x20E2` itself (`0xAAABF0`), server may also send it | C | AS2 268438742; exe `0xAAAC19`, `0xAAAD57` |
| `0x10000D40` | entity (iid) | **Upgrade_Facade** = the entity whose upgrades a tracked entity shows (scoreboard / target frame) | P | AS2 l.299293 |
| `0x2081` / `0x20B9` | player system | account currency (hard/soft) and end-of-match soft-currency reward: **not** the in-match credits | C | protocol-server-to-client.md |

**Shop hint (`0xA93C50`) [C]:** the HUD highlights the shop button when credits >= 2500, or >= 500 with no item, and
fewer than 6 items.

**Income / rewards.** No client data holds kill/assist/minion/passive-income amounts (they were server rules). In the
data only:
- Script node `0x10000065` **GrantCurrency** (`entity, amount`, flags 8/128; script-nodes-names.md) in 4 scripts:
  `0x340004AE` (on a hostile hit, `$CurrencyGrant`; Stolen Power `0x48000A8C` X-Ray Vision, key `0x10000850`),
  `0x340005D2` (`$BonusCurrency`; Stolen Power `0x48000F9B` Consume), `0x34000740` (`$BonusCredits`; Stolen Power `0x48001298` Trap),
  `0x340006C3` (status `0x1E00057E`: `$CreditBonus` to `$G.KillerIID` when the marked target dies). [C]
- Node `0x100000EC` **SetCurrencyOption** (`UseTeamwideCurrencyGains` `0x10000680`) in `0x34000278` (a loot-drop
  skill spawning `0x4000043D` with `$CurrencyAmount`, rank formulas; used by `0x4900041C`, `0x4900080A`,
  `0x49000B15`). So credits can be team-wide. [C]
- Notice **`0x100004D6`** (network-readable, body `u64 iid | u32` read by `0x95F970`, deliver `0x923100` -> listener
  slot `0x64` = `0xA854F0`): plays scriptlet `0x100003EA` on the entity and calls `0x8C05A0` ->
  Flash `GM_Upgrade.RecvNotice_UI_ShowFloatyCurrencyOverEntity(iid, fCurrency)` = the "+N credits" floaty over a
  killed entity. The u32 is passed on as the float amount. [P: the Flash id of that notice is `0x100004D5`; the
  network id is `0x100004D6`]
- Flash `DisplayFloatyCurrencyChanged` (`0x10000506`, old/new value) / `DisplayFloatyCurrencyDenied` (`0x10000505`)
  have no network reader (local). Strings "Show floaty credits gained/stomped" (`0x1603E48`/`0x1603E2C`). [C]
- Suggested defaults for a server (not from data, [?]): start credits, passive income per second, kill/assist/minion
  bounties must be chosen in `config.py`.

## 3. Protocol

### 3.1 Client -> server [C]

Both senders run from the Flash natives of `Notice_Upgrade__PurchaseUpgrade` (0x10000125) / `__SellUpgrade`
(0x10000144), are refused locally when the shop is "busy" (see handle) and go to the world service (route 0x400).

| Event | Sender / ctor / serializer | Body after the `u8 0` base byte | Trigger |
|---|---|---|---|
| `0x208B` purchase | `0x88C410` / `0x87AF30` / `0x83F1D0` | `u32 artifact DID` (+0x20) \| `u32 handle.seq` (+0x28) \| `u64 handle.iid` (+0x30) = 16 bytes | `0xA17CE0(did)`: only if no transaction is pending; needs the local champion (`0x85D670`, via player `0x100000CF`) with an upgrade component; calls `0x96FBF0`, `0x9742D0` and `0x9D18B0`, whose result is only tested for != 0 (`0xA17D4B`) and is never 0 (2/3/4/5/7), so the event is sent whatever the price check says: the Flash UI asks `InqCanBuyUpgrade` first, and **the server must validate**; then `0xA0F5D0` makes a new handle and stores it as pending |
| `0x20A7` sell | `0x88C530` / `0x87AF90` / `0x840740` | `u32 artifact DID` \| `u32 slot index 0..5` \| `u32 handle.seq` \| `u64 handle.iid` = 20 bytes | `0xA17D90(did, slot)`: only if no transaction is pending and `inventory[slot].did == did` |
| `0x212C` | `0x8C4A60` / `0x845DF0` | `u32list` HUD order of the item skill slots | after every `0x20E2` for the local champion (`0xA51940`) and Flash `ChangeArtifactSkillSlotMapping` |

Correction to protocol-client-to-server.md: `0x208B` has **one** handle (u32 + u64), not two; `0x20A7` has one handle
after the slot. The handle is built by `0x853C40`: `seq` = a global counter `0x1B748C4` incremented per request
(never 0), `iid` = `0x635230()` (the local player/session id [P]).

**No undo event exists.** Flash `GM_Upgrade` has no undo notice; the only reversal is selling. The other upgrade
notices (`RequestCurrentUpgrades` 0x10000138, `RequestSendEveryonesUpgrades` 0x100002B0, `RequestAllAvailableUpgrades`
0x100001C3, `RequestUpgradeArrayPreview` 0x10000278, `ActivateItemSlot` 0x100001EF, the `Query_*` 0x10000128...) have
no network sender in the client->server scan: they are answered locally from the upgrade component. [C for "no
sender found"]

### 3.2 Client-side checks (the server should mirror them) [C]

`0x9D1CF0` (`Query_Upgrade__InqCanBuyUpgrade` result `eResult`):

| Code | Meaning |
|---|---|
| 2 | can buy |
| 3 | null DID or no record |
| 4 | no upgrade component, or its "can shop" flag (`+0xC4`) is off |
| 5 | 6 slots full and nothing in the inventory is a lower tier of the target |
| 6 | already owned (count >= stack limit `0x100005F7`, i.e. always, as no artifact has one) |
| 7 | not affordable (`price > 0x1000035E`), or alive outside base (see below) |
| 11 (`0xB`) | `0x10000B52` whitelist present and the DID is not in it (skipped when `0x10000B55` = true) |

`0x9D0620` (`InqCanSellUpgrade`): 9 can sell; 10 not owned (or not in that slot); 8 no component; 12 (`0xC`)
`0x10000B55` present and false (selling disabled).

**When shopping is allowed:** the upgrade component's second vtable (`0x15F9490`, listener `0x96C780`) watches the
champion's `0x100000FA` LifeState, `0x10000459` (bool) and `0x10000A23` (bool): `+0xC0 = LifeState not in {3, 4}`
(i.e. dead/respawning), `+0xC1 = 0x10000459`, `+0xC2 = 0x10000A23`, `+0xC3 = C0 || C1` (vfunc `+0x50`, UI),
**`+0xC4 = C0 || C2` = can buy/sell now**. The price check `0x9D1780` repeats it: alive (state 3/4) without
`0x10000A23` -> 7. So: **send `0x10000A23 = true` on the champion while it stands in its base / fountain** (or always,
for a "shop anywhere" option); dead champions can always shop. `0x10000459` also drives a HUD flag (`0xA1ADF0`,
in-base indicator [P]).

### 3.3 Server -> client

| Event / notice | Destination | Body (after `u8 0`) | Client effect | Conf |
|---|---|---|---|---|
| **`0x2086`** | any object (exec `0x8BFE50` QI; handler ignores it), e.g. the player `0x0200000000000001` | `u32 handle.seq` \| `u64 handle.iid` (ser `0x83F5B0`) | `0xA0F570`: if it equals the pending handle, clears it -> shop usable again. **Without it the shop stays locked** until a UI reset (`0xA3A940`) | C |
| **`0x20E2`** | **the champion object** (needs `obj+0xA4` upgrade component) | `u32 n` \| n x (`u32 artifact DID`, `u32 stack count`) \| `u32 a` \| `u64 b` \| `u32 c` \| StringInfo \| wstr \| `u32 d` \| `compact n` + n x `u32` (ser `0x847E80` -> `0x844710/0x844770`, `0x86FB20`) | `0xAAABF0`: for the local champion compares with the old slots (first change plays `0xA6EAC0`), sets `0x10000CD6`, stores slots at component `+0x10` (6 x 8 bytes, empty = null DID `[0x1B75314]`), sends `0x212C`, stores the tail at `+0x60`, then `0xA51760` (power-graph values, 5 categories capped at 100) and Flash `GM_Upgrade.RecvNotice_UpdateCurrentUpgrades(iid, DIDs, icons, stack sizes, mod DIDs, mod overlay icons)` | C (layout), P (tail = the champion's amplifier set `{id, owner, ?, name, custom name, ?, amplifier DIDs}`, same struct as `0x2090`/`0x20C7`; mods change prices and stats) |
| `0x20DD` | champion | `u32list` | stored at component `+0x40`, flag `+0xF0` = 1 | C (store), ? (meaning: bought-item history / build order) |
| `0x2078` | champion / player | `u32list` | `0xA9FF30`: stores at `+0x50` (recommended upgrades), picks the next one, `GM_Upgrade.RecvNotice_UpdateNextRecommendedUpgrade(did, canBuy)` | C |
| `0x212B` | champion | `u32list` | component vfunc `+0x54` = `0x9743B0`: stores at `+0xB0` (artifact skill slot mapping) -> Flash `SetUIArtifactSkillSlotMapping` | C (store), P (UI) |
| notice `0x100004D6` | object / player system | `u64 iid` \| `u32` (f32 amount) | "+credits" floaty over the entity (2.) | P |
| notice `0x10000414` | object | `u64` \| `u32` | upgrade listener slot 8 (`0x9220F0`) | ? |
| notice `0x10000364` | object | `u64` \| `u32` \| `u32` \| `u8` | upgrade listener slot `0xC` (`0x9221B0`) | ? |
| property `0x1000035E` | champion | f32 | credits (HUD, can-buy) | C |
| properties `0x10000B54` / `0x10000B55` / `0x10000B52` | champion | bool / bool / array | change -> `RecvNotice_UI_RefreshPurchasability` (`0x8A7C30`) | C |

There is no "purchase failed" event for the in-match shop (the `0x210C`/`0x210D`/`0x210F` events are the account
store, `GM_Contextual`). A refused purchase = send `0x2086` (unlock) and an unchanged `0x20E2`/currency. [C for the
absence in the event registry; behaviour P]

### 3.4 Suggested server handling (for `ics`)

On `0x208B (did, handle)`: find the champion; run the 3.2 checks with the server's own state (encounter list from
`0x1000081E`, whitelist, alive/base, slots, credits); price = cost(did) - cost(owned lower tier) - mod discount;
remove the replaced component (its slot is reused) or take the first empty slot; credits -= price; send the
`0x1000035E` update, `0x20E2` (6 slots, empty = `0`/null DID with count 0; tail: an empty amplifier set), `0x2086`
(handle), then apply: add the stat bonuses (op 9 add, op 10 percent) to the champion's stat properties, apply each
passive status (`0x1000037D`), install the active skill (`0x100008E1`) in the first free item skill slot.
On `0x20A7 (did, slot, handle)`: check `slots[slot] == did`; credits += `0x1000045E`; clear the slot; remove its
stats/statuses/skill; send the same three messages.

## 4. Inventory representation (client upgrade component, `obj+0xA4`, ctor `0x978A50`, vtables `0x15F94A8` / `0x15F9490`) [C]

| Offset | Content | Filled by |
|---|---|---|
| `+0x10` | 6 slots x {`u32 DID`, `u32 stack count`} (initialised to null DID by `0x9742D0`) | `0x20E2` |
| `+0x20` | power-graph values (5 f32, capped at 100) | computed (`0xA51650`) |
| `+0x40` | u32 list | `0x20DD` |
| `+0x50` | recommended upgrades (u32 list) | `0x2078` |
| `+0x60` | tail struct of `0x20E2` (amplifier set [P]) | `0x20E2` |
| `+0xB0` | artifact skill slot mapping | `0x212B` |
| `+0xC0..C4` | shop availability flags (3.2) | champion properties `0x100000FA`, `0x10000459`, `0x10000A23` |
| `+0xF0` / `+0xF1` | "list received" / refresh flags | `0x20DD` / several |

Item effects are **not** applied by the client: the client only displays. The server must send the resulting stat
property values, statuses and skill tables.

## 5. Shop UI requirements (Flash) [C]

- HUD reads `Upgrade_Currency_Property` (`0x1000035E`) and `Upgrade_CurrentItemCount_Property` (`0x10000CD6`) of
  `m_iidPlayerControlledAgent` (player property `0x100000CF` must point at the champion), plus `Upgrade_Facade` for
  other entities.
- The HUD setup `0xA8C770` runs only when the local champion has `0x100001D3` (encounter) and `0x100005F0` (array)
  and then registers listeners for `0x10000C85`, `0x100001AF` (SkillPoints), `0x1000035E`, `0x10000CD6`.
- Catalogue, names, icons, costs, sell values, tiers, filters, tooltips, recommended lists come from local queries
  (`Query_Artifact__InqAvailableArtifacts` `0x100002CC`, `InqArtifactDetails` `0x100002CD`, `InqRecommendedArtifacts`
  `0x100002ED`, `Query_Upgrade__InqCanBuyUpgrade` `0x100002F8`, ...), answered by the C++ upgrade system from the packs
  + the component state.
- Inventory display: `GM_Upgrade.RecvNotice_UpdateCurrentUpgrades` (from `0x20E2`), scoreboard via MatchData
  `EVENT_UPGRADES_CHANGE`.
- Tutorial hooks: Flash sends `Tutorial_ArtifactFoundryOpened` / `Closed` (0x10000462 / 0x10000468, local); script
  node `0x10000183` (ActivateArtifacts) in `0x34000603` (Tutorial 2 stage script, artifact `0x400004AD`) sends
  `GM_Upgrade.RecvNotice_ActivatedArtifacts(aArtifacts, bAllSelectable)` on the client (highlights given artifacts).

Flash notice ids (`GM_Upgrade` / `GM_Artifact`, AS2 getters): PurchaseUpgrade `0x10000125`, InqAvailableUpgrades
`0x10000128`, UpdateCurrentUpgrades `0x1000012F`, RequestCurrentUpgrades `0x10000138`, SellUpgrade `0x10000144`,
InqUpgradeDetails `0x10000145`, InqBuildOrder `0x1000014B`, InqSellDifferenceSlot `0x1000014D`, UpdatePowerGraphValues
`0x10000160`, SendAvailableUpgrades `0x100001C1`, RequestAllAvailableUpgrades `0x100001C3`, ActivateItemSlot
`0x100001EF`, InqPurchasedItems `0x100001F7`, BoughtItemListReceived `0x100001F8`, UpgradeCooldown `0x10000235`,
InqNextRecommendedUpgrade `0x10000271`, UpdateNextRecommendedUpgrade `0x10000272`, ReturnedUpgradeArrayPreview
`0x10000277`, RequestUpgradeArrayPreview `0x10000278`, RequestSendEveryonesUpgrades `0x100002B0`, InqCanBuyUpgrade
`0x100002F8`, InqCanSellUpgrade `0x100002F9`, InqSellDifferenceByDID `0x10000384`, ShowCurrencyCollectionRings
`0x100003FF`, SetUIArtifactSkillSlotMapping `0x1000042A`, ChangeArtifactSkillSlotMapping `0x1000042C`,
RequestArtifactSkillSlotMapping `0x1000042D`, Tutorial_ArtifactFoundryOpened `0x10000462` / Closed `0x10000468`,
UI_RefreshPurchasability `0x1000046D`, ActivatedArtifacts `0x10000470`, UI_ShowFloatyCurrencyOverEntity `0x100004D5`,
DisplayFloatyCurrencyDenied `0x10000505`, DisplayFloatyCurrencyChanged `0x10000506`; GM_Artifact
InqRemainingRecommendedArtifacts `0x100002CB`, InqAvailableArtifacts `0x100002CC`, InqArtifactDetails `0x100002CD`,
InqArtifactsMatchingCategoryFilterSet `0x100002D9`, InqRecommendedArtifacts `0x100002ED`, FakeFoundryNotice
`0x1000030B`, InqKillCardArtifactTooltip `0x100003DB`. Flash argument lists: AS2 dump lines 73285-73761 and
418681-420637.

## 6. Open points

- Kill / assist / minion / tower credit amounts, starting credits and passive income: not in client data.
- `0x20DD` list meaning; the tail of `0x20E2` (amplifier set: probable); `0x10000414` / `0x10000364` notices.
- The exact sell refund when a mod discount applies; `0x10000C77` (stat keyword of the Gambit items).
- Names of encounters `0x49000D63`, `0x49000D71`, `0x49000E5A`, `0x49000E61`, `0x49000E62`, `0x49000E65`,
  `0x49000E6D`.
- Who owns the `0x48000163` references (out-of-match foundry?) and `0x4800118B` (`0x1D000918`).

## 7. Active abilities (artifact `0x100008E1` -> record -> `0x10000328` script)

| Ability record | Script | Artifacts |
|---|---|---|
| `0x4800094B` | `0x34000398` | `0x40000618` |
| `0x4800098F` | `0x340003A8` | `0x4000059A` |
| `0x48000992` | `0x340003AA` | `0x4000058C` |
| `0x4800099C` | `0x340003B1` | `0x40000617` |
| `0x4800099D` | `0x340003B2` | `0x4000051F` |
| `0x480009A0` | `0x340003B4` | `0x4000061B` |
| `0x480009B2` | `0x340003C0` | `0x40000562` |
| `0x480009B3` | `0x340003C1` | `0x4000055E` |
| `0x480009B7` | `0x340003BE` | `0x40000598` |
| `0x480009B9` | `0x340003C3` | `0x4000061A` |
| `0x480009BD` | `0x340003C5` | `0x40000582` |
| `0x48000CD1` | `0x34000384` | `0x400008C1` |
| `0x48000CD2` | `0x34000384` | `0x400008C2` |
| `0x48000CD3` | `0x34000384` | `0x400008C3` |
| `0x48000CEA` | `0x340004BC` | `0x40000929` |
| `0x48000CEB` | `0x340004BC` | `0x4000092A` |
| `0x48000CEC` | `0x340004BC` | `0x40000925` |
| `0x48000CED` | `0x340004BD` | `0x40000926` |
| `0x48000CEE` | `0x340004BD` | `0x40000928` |
| `0x48000CEF` | `0x340004BD` | `0x40000927` |
| `0x48000D52` | `0x340004EA` | `0x40000501` |
| `0x48000EBD` | `0x340003AC` | `0x40000522` |
| `0x48000EC1` | `0x340003BC` | `0x4000058A` |
| `0x48000FA8` | `0x340005D6` | `0x40000BDE` `0x40000BDF` |
| `0x48000FB6` | `0x340005DD` | `0x40000595` |
| `0x48000FDE` | `0x340005F8` | `0x40000563` |
| `0x480012BA` | `0x340004ED` | `0x40000D1A` |
| `0x4800145B` | `0x34000399` | `0x40000E6A` `0x40000E6B` |
| `0x48001461` | `0x340003BA` | `0x4000061C` `0x4000061D` |

## 8. Passive effect records (artifact `0x100004EA` -> `0x1000037D`)

| Effect record | Status script (`0x10000242`) | Count | Artifacts (first 6) |
|---|---|---|---|
| `0x480007C4` | `0x340002E9` | 1 | `0x400004BB` |
| `0x480007C5` | `0x340002D5` | 2 | `0x400004A0` `0x40000617` |
| `0x480007C6` | `0x340002ED` | 2 | `0x400004B2` `0x40000618` |
| `0x480007C7` | `0x340002DB` | 1 | `0x400004C1` |
| `0x480007C8` | `0x340002D1` | 2 | `0x40000508` `0x40000619` |
| `0x480007C9` | `0x340002EA` | 2 | `0x4000048F` `0x4000061A` |
| `0x480007CA` | `0x340002E1` | 1 | `0x4000053A` |
| `0x480007CB` | (stat keyword) | 1 | `0x400004CC` |
| `0x480007CC` | `0x340002DE` | 1 | `0x40000500` |
| `0x480007CE` | `0x340002E3` | 6 | `0x4000049D` `0x400004B8` `0x40000515` `0x4000051B` `0x4000051C` `0x400008C6` |
| `0x480007D0` | `0x340002D7` | 2 | `0x400004CB` `0x40000C08` |
| `0x480007D1` | `0x340002E8` | 1 | `0x400004E0` |
| `0x480007D2` | `0x340002D4` | 1 | `0x400004A2` |
| `0x480007D3` | `0x340002E5` | 1 | `0x4000058B` |
| `0x480007D6` | `0x340002DA` | 1 | `0x400004F5` |
| `0x480007DC` | (stat keyword) | 5 | `0x400004AB` `0x400004BA` `0x400004C6` `0x400004C9` `0x40000591` |
| `0x480007DE` | `0x340007BD` | 1 | `0x4000048B` |
| `0x480007E0` | `0x340002D6` | 3 | `0x40000496` `0x400004EB` `0x400004FE` |
| `0x480007E1` | `0x340002DF` | 3 | `0x4000055B` `0x4000055D` `0x40000563` |
| `0x480007E2` | `0x340002D3` | 1 | `0x4000049E` |
| `0x480007E3` | `0x340002EB` | 1 | `0x400004AE` |
| `0x480008D3` | (stat keyword) | 3 | `0x40000564` `0x40000586` `0x400005A2` |
| `0x480008D5` | `0x3400036E` | 1 | `0x400004EC` |
| `0x48000917` | `0x34000381` | 2 | `0x4000057F` `0x40000583` |
| `0x48000919` | `0x3400037F` | 1 | `0x400004D0` |
| `0x48000920` | `0x34000322` | 1 | `0x400004F5` |
| `0x48000921` | `0x34000322` | 1 | `0x400004DE` |
| `0x48000922` | `0x34000322` | 1 | `0x4000049F` |
| `0x4800095D` | `0x340003A0` | 2 | `0x40000572` `0x40000576` |
| `0x48000961` | `0x340003A1` | 1 | `0x4000056E` |
| `0x4800096C` | (stat keyword) | 1 | `0x400004EE` |
| `0x4800096D` | (stat keyword) | 1 | `0x400004DB` |
| `0x4800096E` | (stat keyword) | 1 | `0x400004E7` |
| `0x4800096F` | (stat keyword) | 1 | `0x400004A7` |
| `0x48000970` | (stat keyword) | 1 | `0x40000995` |
| `0x48000971` | (stat keyword) | 2 | `0x40000996` `0x40000BDE` |
| `0x48000973` | (stat keyword) | 1 | `0x400004EA` |
| `0x48000974` | (stat keyword) | 1 | `0x40000505` |
| `0x48000976` | `0x340003A2` | 1 | `0x400004DD` |
| `0x48000979` | (stat keyword) | 3 | `0x400004A8` `0x400004C7` `0x400004F8` |
| `0x4800097A` | (stat keyword) | 3 | `0x400004BD` `0x400004E8` `0x40000503` |
| `0x4800097B` | (stat keyword) | 3 | `0x40000499` `0x400004A5` `0x400004CD` |
| `0x4800097C` | (stat keyword) | 3 | `0x40000494` `0x400004D7` `0x400004E2` |
| `0x480009C6` | (stat keyword) | 4 | `0x40000494` `0x400004A8` `0x400004CD` `0x400004E8` |
| `0x48000A2D` | (stat keyword) | 1 | `0x400004AA` |
| `0x48000A2E` | (stat keyword) | 1 | `0x40000492` |
| `0x48000CD5` | `0x340002FD` | 1 | `0x4000051D` |
| `0x48000CD6` | `0x340002FD` | 1 | `0x40000518` |
| `0x48000D58` | `0x340004EE` | 2 | `0x400004EC` `0x400004FF` |
| `0x48000D60` | (stat keyword) | 1 | `0x4000099B` |
| `0x48000E86` | `0x3400053D` | 1 | `0x40000599` |
| `0x48000E87` | `0x3400053E` | 1 | `0x4000056A` |
| `0x48000E88` | `0x3400053F` | 1 | `0x40000575` |
| `0x48000EB4` | (stat keyword) | 1 | `0x400004DF` |
| `0x48000EB6` | (stat keyword) | 1 | `0x4000099D` |
| `0x48000EBB` | `0x340002D8` | 1 | `0x400004D5` |
| `0x48000EBE` | (stat keyword) | 1 | `0x400004C3` |
| `0x48000EF1` | (stat keyword) | 7 | `0x400004A8` `0x400004BD` `0x400004C7` `0x400004CD` `0x400004E8` `0x400004F8` ... |
| `0x48000F03` | `0x34000572` | 2 | `0x40000499` `0x400004A5` |
| `0x48000F04` | `0x34000571` | 2 | `0x400004D7` `0x400004E2` |
| `0x48000F09` | (stat keyword) | 1 | `0x40000B0E` |
| `0x48000FBC` | `0x340005E4` | 2 | `0x4000058E` `0x40000595` |
| `0x48000FBE` | `0x340005E2` | 4 | `0x40000495` `0x400004E9` `0x400004FD` `0x40000504` |
| `0x4800101A` | `0x34000623` | 1 | `0x40000C08` |
| `0x4800103E` | `0x34000640` | 1 | `0x4000057A` |
| `0x48001064` | `0x34000385` | 1 | `0x400004CE` |
| `0x480010D5` | `0x3400069D` | 3 | `0x40000495` `0x400004E9` `0x400004FD` |
| `0x48001259` | `0x34000736` | 1 | `0x400004EF` |
| `0x48001295` | `0x3400073E` | 1 | `0x400004E7` |
| `0x4800140E` | `0x340002D2` | 1 | `0x400004CF` |
| `0x48001410` | (stat keyword) | 1 | `0x400004DA` |
| `0x48001450` | `0x340007BD` | 1 | `0x400004D1` |
| `0x480015D9` | `0x34000890` | 1 | `0x40000523` |

## 9. Every artifact (pack `0xA00000B3`; short names and numbers only)

Lists: A = `0x48000163`, B = `0x48000EA9` / `0x48000EAA` / `0x4800118B`, C = `0x480007B0`. Cost = `0x1000036C` (cumulative tier price), Sell = `0x1000045E`, From = `0x10000698`, Into = `0x10000697`; stats as in `catalog/data/artifacts.tsv` (op `+%` = percent).

| DID | Name | Cat | Tier | Cost | Sell | From | Into | Stats | Active | Passives | Lists |
|---|---|---|---|---|---|---|---|---|---|---|---|
| `0x4000048A` | Atlantean Royal Seal (2) | Pow | 2 | 1500 | 1125 | `0x4000049C` | `0x400004A4` | Health +200; Power Damage +30 |  |  | ABC |
| `0x4000048B` | Batman's Utility Belt (3) | Att | 3 | 2750 | 2065 | `0x400004F9` |  | Health +200; Attack Damage +30; Cooldown Reduction +0.1 |  | 0x480007DE | ABC |
| `0x4000048C` | Lobo's Chain (1) | Att | 1 | 500 | 450 |  | `0x400004F7` | Health +75; Attack Damage +5 |  |  | ABC |
| `0x4000048D` | Soultaker Katana (3) | Att | 3 | 2250 | 1690 | `0x400004A9` | `0x400004D0` | Attack Damage +30; Attack Lifesteal +0.12 |  |  | ABC |
| `0x4000048E` | Diana's Bracers (1) | Def | 1 | 750 | 565 |  | `0x400004CB` | Health Regeneration +1; Attack Armor +20 |  |  | ABC |
| `0x4000048F` | Qward Gambit (3) | Pow | 3 | 1750 | 1315 | `0x400004AB` | `0x4000061A` | Will +200; Power Damage +20 |  | 0x480007C9 | ABC |
| `0x40000491` | Kryptonian War Armor (1) | Def | 1 | 750 | 565 |  | `0x400004D4` | Health +50; Health Regeneration +1; Power Armor +15 |  |  | ABC |
| `0x40000492` | Suit of Sorrows (3) | Def | 3 | 2000 | 1500 | `0x400004D2` | `0x400004AA` | Health +125; Attack Armor +40 |  | 0x48000A2E | ABC |
| `0x40000493` | Two Face's Coin (1) | Uti | 1 | 500 | 450 |  | `0x400004AE` | Power Damage +20 |  |  | A |
| `0x40000494` | Marauder Shield (1) | Def | 1 | 250 | 225 |  | `0x400004CD` | Health +25 |  | 0x4800097C 0x480009C6 | AB |
| `0x40000495` | Abin Sur's Lantern (4) | Pow | 4 | 2750 | 2065 | `0x400004FD` |  | Will +400; Power Damage +30; Cooldown Reduction +0.1 |  | 0x48000FBE 0x480010D5 | ABC |
| `0x40000496` | Ruby of Life (2) | Def | 2 | 1250 | 940 | `0x400004B0` | `0x400004FE` | Health +75; Health Regeneration +0.7 |  | 0x480007E0 | ABC |
| `0x40000497` | Claw of Horus (2) | Att | 2 | 1750 | 1315 | `0x400004FB` | `0x40000500` | Health +150; Attack Damage +25; Attack Armor +15 |  |  | ABC |
| `0x40000498` | Spear of Destiny (1) | Def | 1 | 1000 | 750 |  | `0x400004D5` | Health +100; Attack Damage +10; Power Armor +10 |  |  | ABC |
| `0x40000499` | Marauder Ring (2) | Pow | 2 | 750 | 565 | `0x400004D7` | `0x40000503` | Health +50; Power Damage +10 |  | 0x4800097B 0x48000F03 | AB |
| `0x4000049C` | Atlantean Royal Seal (1) | Pow | 1 | 750 | 565 |  | `0x4000048A` | Health +75; Power Damage +20 |  |  | ABC |
| `0x4000049D` | Doctor Destiny's Dreamstone (2) | Pow | 2 | 750 | 565 | `0x400004E1` | `0x400004B8` | Will Regeneration +%0.25 |  | 0x480007CE | ABC |
| `0x4000049E` | Joker's Crowbar (2) | Uti | 2 | 1250 | 940 | `0x40000507` |  | Move Speed +0.05; Attack Damage +10 |  | 0x480007E2 | A |
| `0x4000049F` | Mega Rod (1) | Att | 1 | 750 | 565 |  | `0x400004DE` | Health Regeneration +1; Attack Damage +10 |  | 0x48000922 | ABC |
| `0x400004A0` | Atlantis Gambit (3) | Att | 3 | 1750 | 1315 | `0x400004BA` | `0x40000617` | Health Regeneration +1.5; Attack Damage +20 |  | 0x480007C5 | ABC |
| `0x400004A2` | Lobo's Chain (4) | Att | 4 | 3000 | 2250 | `0x4000050B` |  | Health +300; Attack Damage +30 |  | 0x480007D2 | ABC |
| `0x400004A4` | Atlantean Royal Seal (3) | Pow | 3 | 2250 | 1690 | `0x4000048A` | `0x400004E0` | Health +300; Power Damage +40 |  |  | ABC |
| `0x400004A5` | Marauder Knife (2) | Att | 2 | 750 | 565 | `0x400004E2` | `0x400004BD` | Attack Damage +10 |  | 0x4800097B 0x48000F03 | AB |
| `0x400004A6` | Atlantis Gambit (1) | Att | 1 | 250 | 225 |  | `0x400004BA` | Health Regeneration +0.5; Attack Damage +5 |  |  | ABC |
| `0x400004A7` | Coda Blade (3) | Att | 3 | 1750 | 1315 | `0x400004BF` | `0x400004E7` | Attack Damage +40 |  | 0x4800096F | ABC |
| `0x400004A8` | Marauder Shield (4) | Def | 4 | 2250 | 1690 | `0x400004E8` |  | Resilience +0.3; Health +250; Cooldown Reduction +0.1 |  | 0x48000979 0x480009C6 0x48000EF1 | AB |
| `0x400004A9` | Soultaker Katana (2) | Att | 2 | 1500 | 1125 | `0x400004E3` | `0x4000048D` | Attack Damage +20; Attack Lifesteal +0.08 |  |  | ABC |
| `0x400004AA` | Suit of Sorrows (4) | Def | 4 | 2750 | 2065 | `0x40000492` |  | Health +150; Attack Armor +50 |  | 0x48000A2D | ABC |
| `0x400004AB` | Qward Gambit (2) | Pow | 2 | 750 | 375 | `0x400004C4` | `0x4000048F` | Will +150; Power Damage +15 |  | 0x480007DC | ABC |
| `0x400004AC` | Olympus Gambit (1) | Def | 1 | 250 | 225 |  | `0x400004C6` | Health +75 |  |  | ABC |
| `0x400004AD` | Coda Blade (1) | Att | 1 | 500 | 450 |  | `0x400004BF` | Attack Damage +12 |  |  | ABC |
| `0x400004AE` | Two Face's Coin (2) | Uti | 2 | 1250 | 940 | `0x40000493` |  | Power Damage +20 |  | 0x480007E3 | A |
| `0x400004B0` | Ruby of Life (1) | Def | 1 | 500 | 450 |  | `0x40000496` | Health +75; Health Regeneration +0.7 |  |  | ABC |
| `0x400004B2` | Olympus Gambit (3) | Def | 3 | 1750 | 1315 | `0x400004C6` | `0x40000618` | Health +150; Attack Armor +10; Power Armor +5 |  | 0x480007C6 | ABC |
| `0x400004B3` | Helm of Fate (1) | Pow | 1 | 500 | 450 |  | `0x400004ED` | Power Damage +10; Power Armor +10 |  |  | ABC |
| `0x400004B5` | Eclipso's Diamond (1) | Pow | 1 | 1250 | 940 |  | `0x400004EF` | Power Damage +30; Power Lifesteal +0.15 |  |  | ABC |
| `0x400004B6` | Entropy Aegis (1) | Def | 1 | 750 | 565 |  | `0x400004CA` | Health +100; Power Armor +15 |  |  | ABC |
| `0x400004B7` | Deathstroke's Claymore (2) | Att | 2 | 1750 | 1315 | `0x400004F2` | `0x40000D1A` | Attack Damage +25; Attack Penetration +10; Cooldown Reduction +0.1 |  |  | ABC |
| `0x400004B8` | Doctor Destiny's Dreamstone (3) | Pow | 3 | 1750 | 1315 | `0x4000049D` | `0x400008C6` | Will Regeneration +%0.4; Power Damage +20; Cooldown Reduction +0.1 |  | 0x480007CE | ABC |
| `0x400004BA` | Atlantis Gambit (2) | Att | 2 | 750 | 375 | `0x400004A6` | `0x400004A0` | Health Regeneration +1; Attack Damage +10 |  | 0x480007DC | ABC |
| `0x400004BB` | Entropy Aegis (3) | Def | 3 | 2750 | 2065 | `0x400004CA` |  | Health +250; Power Armor +40 |  | 0x480007C4 | ABC |
| `0x400004BC` | Metallo's Heart (1) | Def | 1 | 750 | 565 |  | `0x400004FC` | Health +75; Attack Armor +20 |  |  | ABC |
| `0x400004BD` | Marauder Knife (3) | Att | 3 | 1250 | 940 | `0x400004A5` | `0x400004F8` | Attack Damage +20 |  | 0x4800097A 0x48000EF1 | AB |
| `0x400004BE` | Batman's Utility Belt (1) | Att | 1 | 750 | 565 |  | `0x400004F9` | Health +75; Attack Damage +10 |  |  | ABC |
| `0x400004BF` | Coda Blade (2) | Att | 2 | 1000 | 750 | `0x400004AD` | `0x400004A7` | Attack Damage +25 |  |  | ABC |
| `0x400004C0` | Eye of Ekron (2) | Pow | 2 | 1000 | 750 | `0x400004FA` | `0x4000053B` | Will +200; Power Damage +25 |  |  | ABC |
| `0x400004C1` | Metallo's Heart (3) | Def | 3 | 2750 | 2065 | `0x400004FC` |  | Health +200; Attack Armor +50; Cooldown Reduction +0.1 |  | 0x480007C7 | ABC |
| `0x400004C2` | Psi-Scimitar (2) | Pow | 2 | 1500 | 1125 | `0x400004D8` | `0x400004D1` | Will Regeneration +%0.35; Power Damage +50 |  |  | ABC |
| `0x400004C3` | Kryptonian War Armor (3) | Def | 3 | 2750 | 2065 | `0x400004D4` |  | Move Speed +0.2; Health +200; Health Regeneration +1; Power Armor +40 |  | 0x48000EBE | ABC |
| `0x400004C4` | Qward Gambit (1) | Pow | 1 | 250 | 225 |  | `0x400004AB` | Will +125 |  |  | ABC |
| `0x400004C6` | Olympus Gambit (2) | Def | 2 | 750 | 375 | `0x400004AC` | `0x400004B2` | Health +100; Attack Armor +5; Power Armor +5 |  | 0x480007DC | ABC |
| `0x400004C7` | Marauder Ring (4) | Pow | 4 | 2250 | 1690 | `0x40000503` |  | Health +150; Power Damage +30; Power Lifesteal +0.15 |  | 0x48000979 0x48000EF1 | AB |
| `0x400004C9` | Oa Gambit (2) | Def | 2 | 750 | 375 | `0x40000506` | `0x40000508` | Power Damage +15; Power Armor +15 |  | 0x480007DC | ABC |
| `0x400004CA` | Entropy Aegis (2) | Def | 2 | 1500 | 1125 | `0x400004B6` | `0x400004BB` | Health +200; Power Armor +30 |  |  | ABC |
| `0x400004CB` | Diana's Bracers (2) | Def | 2 | 1500 | 1125 | `0x4000048E` | `0x40000C08` | Health Regeneration +1.5; Attack Armor +20 |  | 0x480007D0 | ABC |
| `0x400004CC` | The Starheart (3) | Pow | 3 | 3500 | 2625 | `0x400004E6` |  | Power Damage +100 |  | 0x480007CB | ABC |
| `0x400004CD` | Marauder Shield (2) | Def | 2 | 750 | 565 | `0x40000494` | `0x400004E8` | Health +75 |  | 0x4800097B 0x480009C6 0x48000EF1 | AB |
| `0x400004CE` | Nil Ring | Pow |  | 500 | 165 |  |  | Health +75; Will Regeneration +%0.15; Power Damage +15 |  | 0x48001064 | ABC |
| `0x400004CF` | Nil Weapon | Att |  | 500 | 165 |  |  | Health +75; Attack Damage +10 |  | 0x4800140E | ABC |
| `0x400004D0` | Soultaker Katana (4) | Att | 4 | 3250 | 2440 | `0x4000048D` |  | Attack Damage +40; Attack Lifesteal +0.12 |  | 0x48000919 | ABC |
| `0x400004D1` | Psi-Scimitar (3) | Pow | 3 | 2750 | 2065 | `0x400004C2` |  | Will Regeneration +%0.4; Power Damage +85 |  | 0x48001450 | ABC |
| `0x400004D2` | Suit of Sorrows (2) | Def | 2 | 1250 | 940 | `0x400004E4` | `0x40000492` | Health +100; Attack Armor +30 |  |  | ABC |
| `0x400004D3` | The Starheart (1) | Pow | 1 | 1250 | 940 |  | `0x400004E6` | Power Damage +50 |  |  | ABC |
| `0x400004D4` | Kryptonian War Armor (2) | Def | 2 | 1500 | 1125 | `0x40000491` | `0x400004C3` | Move Speed +0.1; Health +75; Health Regeneration +1; Power Armor +30 |  |  | ABC |
| `0x400004D5` | Spear of Destiny (2) | Def | 2 | 2500 | 1875 | `0x40000498` |  | Health +150; Attack Damage +20; Power Armor +20 |  | 0x48000EBB | ABC |
| `0x400004D7` | Marauder Ring (1) | Pow | 1 | 250 | 225 |  | `0x40000499` |  |  | 0x4800097C 0x48000F04 | AB |
| `0x400004D8` | Psi-Scimitar (1) | Pow | 1 | 750 | 565 |  | `0x400004C2` | Will Regeneration +%0.3; Power Damage +20 |  |  | ABC |
| `0x400004D9` | Joe Chill's Revolver (1) | Att | 1 | 1500 | 1125 |  | `0x400004F6` | Attack Damage +20; Critical Chance +0.15 |  |  | ABC |
| `0x400004DA` | Nil Cloak | Def |  | 500 | 165 |  |  | Health +100; Health Regeneration +1 |  | 0x48001410 | ABC |
| `0x400004DB` | Atomic Axe (1) | Att | 1 | 1500 | 1125 |  | `0x400004EE` | Attack Damage +20 |  | 0x4800096D | ABC |
| `0x400004DD` | Velocity 9 Implants (4) | Att | 4 | 3250 | 2440 | `0x400004F4` |  | Move Speed +0.1; Critical Chance +0.25; Attack Speed +%0.4 |  | 0x48000976 | ABC |
| `0x400004DE` | Mega Rod (2) | Att | 2 | 1750 | 1315 | `0x4000049F` | `0x400004F5` | Move Speed +0.15; Health Regeneration +1.5; Attack Damage +20 |  | 0x48000921 | ABC |
| `0x400004DF` | Joe Chill's Revolver (3) | Att | 3 | 3750 | 2815 | `0x400004F6` |  | Attack Damage +50; Critical Chance +0.25 |  | 0x48000EB4 | ABC |
| `0x400004E0` | Atlantean Royal Seal (4) | Pow | 4 | 3000 | 2250 | `0x400004A4` |  | Health +300; Power Damage +50 |  | 0x480007D1 | ABC |
| `0x400004E1` | Doctor Destiny's Dreamstone (1) | Pow | 1 | 250 | 225 |  | `0x4000049D` | Will Regeneration +%0.25 |  |  | ABC |
| `0x400004E2` | Marauder Knife (1) | Att | 1 | 250 | 225 |  | `0x400004A5` |  |  | 0x4800097C 0x48000F04 | AB |
| `0x400004E3` | Soultaker Katana (1) | Att | 1 | 750 | 565 |  | `0x400004A9` | Attack Damage +10; Attack Lifesteal +0.04 |  |  | ABC |
| `0x400004E4` | Suit of Sorrows (1) | Def | 1 | 500 | 450 |  | `0x400004D2` | Health +50; Attack Armor +10 |  |  | ABC |
| `0x400004E6` | The Starheart (2) | Pow | 2 | 2500 | 1875 | `0x400004D3` | `0x400004CC` | Power Damage +100 |  |  | ABC |
| `0x400004E7` | Coda Blade (4) | Att | 4 | 2500 | 1875 | `0x400004A7` |  | Attack Damage +40 |  | 0x48001295 0x4800096E | ABC |
| `0x400004E8` | Marauder Shield (3) | Def | 3 | 1250 | 940 | `0x400004CD` | `0x400004A8` | Health +150 |  | 0x4800097A 0x480009C6 0x48000EF1 | AB |
| `0x400004E9` | Abin Sur's Lantern (2) | Pow | 2 | 1250 | 940 | `0x40000504` | `0x400004FD` | Will +100; Power Damage +10 |  | 0x48000FBE 0x480010D5 | ABC |
| `0x400004EA` | The Book of Eternity (2) | Pow | 2 | 2750 | 2065 | `0x40000505` |  | Power Damage +60 |  | 0x48000973 | ABC |
| `0x400004EB` | Ruby of Life (4) | Def | 4 | 3000 | 2250 | `0x400004FE` |  | Health +400; Health Regeneration +2 |  | 0x480007E0 | ABC |
| `0x400004EC` | Cosmic Staff (3) | Pow | 3 | 3000 | 2250 | `0x400004FF` |  | Power Damage +70; Cooldown Reduction +0.1 |  | 0x480008D5 0x48000D58 | ABC |
| `0x400004ED` | Helm of Fate (2) | Pow | 2 | 1250 | 940 | `0x400004B3` | `0x40000501` | Power Damage +30; Power Armor +20 |  |  | ABC |
| `0x400004EE` | Atomic Axe (2) | Att | 2 | 3000 | 2250 | `0x400004DB` |  | Attack Damage +40 |  | 0x4800096C | ABC |
| `0x400004EF` | Eclipso's Diamond (2) | Pow | 2 | 2750 | 2065 | `0x400004B5` |  | Power Damage +60; Power Lifesteal +0.3 |  | 0x48001259 | ABC |
| `0x400004F0` | Velocity 9 Implants (1) | Att | 1 | 750 | 565 |  | `0x40000509` | Attack Speed +%0.2 |  |  | ABC |
| `0x400004F1` | Cosmic Staff (1) | Pow | 1 | 750 | 565 |  | `0x400004FF` | Power Damage +30 |  |  | ABC |
| `0x400004F2` | Deathstroke's Claymore (1) | Att | 1 | 750 | 565 |  | `0x400004B7` | Attack Damage +15; Cooldown Reduction +0.05 |  |  | ABC |
| `0x400004F4` | Velocity 9 Implants (3) | Att | 3 | 2250 | 1690 | `0x40000509` | `0x400004DD` | Move Speed +0.1; Critical Chance +0.2; Attack Speed +%0.35 |  |  | ABC |
| `0x400004F5` | Mega Rod (3) | Att | 3 | 3000 | 2250 | `0x400004DE` |  | Move Speed +0.15; Health Regeneration +1.5; Attack Damage +30 |  | 0x48000920 0x480007D6 | ABC |
| `0x400004F6` | Joe Chill's Revolver (2) | Att | 2 | 2750 | 2065 | `0x400004D9` | `0x400004DF` | Attack Damage +45; Critical Chance +0.2 |  |  | ABC |
| `0x400004F7` | Lobo's Chain (2) | Att | 2 | 1250 | 940 | `0x4000048C` | `0x4000050B` | Health +175; Attack Damage +15 |  |  | ABC |
| `0x400004F8` | Marauder Knife (4) | Att | 4 | 2250 | 1690 | `0x400004BD` |  | Attack Damage +30; Attack Lifesteal +0.1 |  | 0x48000979 0x48000EF1 | AB |
| `0x400004F9` | Batman's Utility Belt (2) | Att | 2 | 1750 | 1315 | `0x400004BE` | `0x4000048B` | Health +150; Attack Damage +20; Cooldown Reduction +0.05 |  |  | ABC |
| `0x400004FA` | Eye of Ekron (1) | Pow | 1 | 500 | 450 |  | `0x400004C0` | Will +100; Power Damage +12 |  |  | ABC |
| `0x400004FB` | Claw of Horus (1) | Att | 1 | 750 | 565 |  | `0x40000497` | Health +50; Attack Damage +10; Attack Armor +10 |  |  | ABC |
| `0x400004FC` | Metallo's Heart (2) | Def | 2 | 1500 | 1125 | `0x400004BC` | `0x400004C1` | Health +150; Attack Armor +35 |  |  | ABC |
| `0x400004FD` | Abin Sur's Lantern (3) | Pow | 3 | 2000 | 1500 | `0x400004E9` | `0x40000495` | Will +200; Power Damage +20; Cooldown Reduction +0.1 |  | 0x48000FBE 0x480010D5 | ABC |
| `0x400004FE` | Ruby of Life (3) | Def | 3 | 2000 | 1500 | `0x40000496` | `0x400004EB` | Health +225; Health Regeneration +1.5 |  | 0x480007E0 | ABC |
| `0x400004FF` | Cosmic Staff (2) | Pow | 2 | 1750 | 1315 | `0x400004F1` | `0x400004EC` | Power Damage +45; Cooldown Reduction +0.05 |  | 0x48000D58 | ABC |
| `0x40000500` | Claw of Horus (3) | Att | 3 | 3000 | 2250 | `0x40000497` |  | Health +200; Attack Damage +40; Attack Armor +20 |  | 0x480007CC | ABC |
| `0x40000501` | Helm of Fate (3) | Pow | 3 | 2250 | 1690 | `0x400004ED` |  | Power Damage +60; Power Armor +30 | 0x48000D52 |  | ABC |
| `0x40000503` | Marauder Ring (3) | Pow | 3 | 1250 | 940 | `0x40000499` | `0x400004C7` | Health +75; Power Damage +20 |  | 0x4800097A 0x48000EF1 | AB |
| `0x40000504` | Abin Sur's Lantern (1) | Pow | 1 | 500 | 450 |  | `0x400004E9` | Will +100 |  | 0x48000FBE | ABC |
| `0x40000505` | The Book of Eternity (1) | Pow | 1 | 1500 | 1125 |  | `0x400004EA` | Power Damage +40 |  | 0x48000974 | ABC |
| `0x40000506` | Oa Gambit (1) | Def | 1 | 250 | 225 |  | `0x400004C9` | Power Damage +6; Power Armor +6 |  |  | ABC |
| `0x40000507` | Joker's Crowbar (1) | Uti | 1 | 500 | 450 |  | `0x4000049E` | Move Speed +0.05; Attack Damage +10 |  |  | A |
| `0x40000508` | Oa Gambit (3) | Def | 3 | 1750 | 1315 | `0x400004C9` | `0x40000619` | Power Damage +25; Power Armor +25 |  | 0x480007C8 | ABC |
| `0x40000509` | Velocity 9 Implants (2) | Att | 2 | 1500 | 1125 | `0x400004F0` | `0x400004F4` | Move Speed +0.05; Critical Chance +0.15; Attack Speed +%0.25 |  |  | ABC |
| `0x4000050B` | Lobo's Chain (3) | Att | 3 | 2000 | 1500 | `0x400004F7` | `0x400004A2` | Health +250; Attack Damage +25 |  |  | ABC |
| `0x40000513` | Sword of Beowulf (1) | Att | 1 | 750 | 565 |  | `0x40000518` | Attack Damage +15; Power Armor +10 |  |  | ABC |
| `0x40000514` | Rip Hunter's Time Pack (3) | Att | 3 | 1750 | 1315 | `0x4000051A` | `0x4000051F` | Attack Damage +35; Cooldown Reduction +0.1 |  |  | ABC |
| `0x40000515` | Blue Scarab (2) | Att | 2 | 1750 | 1315 | `0x4000051B` | `0x4000051C` | Will Regeneration +%0.15; Attack Damage +25; Cooldown Reduction +0.05 |  | 0x480007CE | ABC |
| `0x40000516` | Amulet of Isis (1) | Def | 1 | 500 | 450 |  | `0x40000520` | Health +75; Will +75 |  |  | ABC |
| `0x40000517` | Rip Hunter's Time Pack (1) | Att | 1 | 500 | 450 |  | `0x4000051A` | Attack Damage +12 |  |  | ABC |
| `0x40000518` | Sword of Beowulf (2) | Att | 2 | 1750 | 1315 | `0x40000513` | `0x4000051D` | Attack Damage +25; Power Armor +20 |  | 0x48000CD6 | ABC |
| `0x4000051A` | Rip Hunter's Time Pack (2) | Att | 2 | 1000 | 750 | `0x40000517` | `0x40000514` | Attack Damage +20; Cooldown Reduction +0.05 |  |  | ABC |
| `0x4000051B` | Blue Scarab (1) | Att | 1 | 750 | 565 |  | `0x40000515` | Will Regeneration +%0.1; Attack Damage +5 |  | 0x480007CE | ABC |
| `0x4000051C` | Blue Scarab (3) | Att | 3 | 3000 | 2250 | `0x40000515` |  | Will Regeneration +%0.2; Attack Damage +50; Cooldown Reduction +0.1 |  | 0x480007CE | ABC |
| `0x4000051D` | Sword of Beowulf (3) | Att | 3 | 3000 | 2250 | `0x40000518` |  | Attack Damage +45; Power Armor +30 |  | 0x48000CD5 | ABC |
| `0x4000051F` | Rip Hunter's Time Pack (4) | Att | 4 | 2750 | 2065 | `0x40000514` |  | Attack Damage +50; Cooldown Reduction +0.15 | 0x4800099D |  | ABC |
| `0x40000520` | Amulet of Isis (2) | Def | 2 | 1250 | 940 | `0x40000516` | `0x40000522` | Move Speed +0.05; Health +100; Will +100; Cooldown Reduction +0.1 |  |  | ABC |
| `0x40000521` | Ra's al Ghul's Robe (1) | Def | 1 | 1250 | 415 |  | `0x40000523` | Attack Armor +35; Power Armor +25 |  |  | ABC |
| `0x40000522` | Amulet of Isis (3) | Def | 3 | 2500 | 1875 | `0x40000520` |  | Move Speed +0.05; Health +200; Will +200; Cooldown Reduction +0.1 | 0x48000EBD |  | ABC |
| `0x40000523` | Ra's al Ghul's Robe (2) | Def | 2 | 2750 | 910 | `0x40000521` |  | Attack Armor +45; Power Armor +30 |  | 0x480015D9 | ABC |
| `0x4000053A` | Eye of Ekron (4) | Pow | 4 | 2500 | 1875 | `0x4000053B` |  | Move Speed +0.1; Will +400; Power Damage +40 |  | 0x480007CA | ABC |
| `0x4000053B` | Eye of Ekron (3) | Pow | 3 | 1750 | 1315 | `0x400004C0` | `0x4000053A` | Move Speed +0.1; Will +300; Power Damage +35 |  |  | ABC |
| `0x40000558` | Deadshot's Visor (2) | Att | 2 | 1750 | 1315 | `0x40000589` | `0x40000598` | Will +150; Attack Damage +25; Attack Speed +%0.15 |  |  | ABC |
| `0x40000559` | Fragment of Mogo (2) | Def | 2 | 1500 | 1125 | `0x40000594` | `0x4000059A` | Health +200; Attack Armor +30 |  |  | ABC |
| `0x4000055A` | Cheetah's Claw (2) | Att | 2 | 750 | 565 | `0x40000566` | `0x4000059B` | Attack Lifesteal +0.03; Attack Speed +%0.15 |  |  | ABC |
| `0x4000055B` | The Medusa Mask (3) | Def | 3 | 1750 | 1315 | `0x4000055D` | `0x40000563` | Health +200; Health Regeneration +1.2; Will Regeneration +%0.35 |  | 0x480007E1 | ABC |
| `0x4000055C` | Gorilla Grodd's Helmet (1) | Pow | 1 | 250 | 225 |  | `0x40000591` | Will +125 |  |  | ABC |
| `0x4000055D` | The Medusa Mask (2) | Def | 2 | 1000 | 750 | `0x40000597` | `0x4000055B` | Health Regeneration +1.2; Will Regeneration +%0.3 |  | 0x480007E1 | ABC |
| `0x4000055E` | Cheetah's Claw (4) | Att | 4 | 2250 | 1690 | `0x4000059B` |  | Attack Lifesteal +0.12; Attack Speed +%0.3 | 0x480009B3 |  | ABC |
| `0x4000055F` | Promethium Mace (2) | Att | 2 | 500 | 375 | `0x4000056F` | `0x40000561` | Attack Damage +14 |  |  | AC |
| `0x40000561` | Promethium Mace (3) | Att | 3 | 1000 | 750 | `0x4000055F` | `0x40000564` | Attack Damage +25 |  |  | AC |
| `0x40000562` | Neron's Contract (4) | Pow | 4 | 3000 | 2250 | `0x40000568` |  | Attack Armor +30; Power Damage +60 | 0x480009B2 |  | ABC |
| `0x40000563` | The Medusa Mask (4) | Def | 4 | 2500 | 1875 | `0x4000055B` |  | Health +200; Health Regeneration +1.2; Will Regeneration +%0.4 | 0x48000FDE | 0x480007E1 | ABC |
| `0x40000564` | Promethium Mace (4) | Att | 4 | 1500 | 1500 | `0x40000561` |  | Attack Damage +30 |  | 0x480008D3 | AC |
| `0x40000565` | Neron's Contract (2) | Pow | 2 | 1000 | 750 | `0x4000056D` | `0x40000568` | Attack Armor +15; Power Damage +25 |  |  | ABC |
| `0x40000566` | Cheetah's Claw (1) | Att | 1 | 250 | 225 |  | `0x4000055A` | Attack Speed +%0.08 |  |  | ABC |
| `0x40000567` | Phantom Stranger's Necklace (1) | Def | 1 | 250 | 225 |  | `0x40000572` | Attack Armor +5; Power Armor +5 |  |  | ABC |
| `0x40000568` | Neron's Contract (3) | Pow | 3 | 1750 | 1315 | `0x40000565` | `0x40000562` | Attack Armor +20; Power Damage +50 |  |  | ABC |
| `0x4000056A` | Shade's Cane (2) | Att | 2 | 1500 | 1125 | `0x40000575` | `0x40000599` | Attack Damage +21; Attack Speed +%0.06 |  | 0x48000E87 | ABC |
| `0x4000056D` | Neron's Contract (1) | Pow | 1 | 500 | 450 |  | `0x40000565` | Attack Armor +10; Power Damage +10 |  |  | ABC |
| `0x4000056E` | The Crime Bible (2) | Uti | 2 | 1250 | 940 | `0x40000577` |  | Health +75; Health Regeneration +1 |  | 0x48000961 | A |
| `0x4000056F` | Promethium Mace (1) | Att | 1 | 250 | 225 |  | `0x4000055F` | Attack Damage +7 |  |  | AC |
| `0x40000571` | Zeiss Goggles (3) | Att | 3 | 1750 | 1315 | `0x40000574` | `0x4000057A` | Attack Damage +25; Attack Speed +%0.25 |  |  | ABC |
| `0x40000572` | Phantom Stranger's Necklace (2) | Def | 2 | 1000 | 750 | `0x40000567` | `0x40000576` | Attack Armor +10; Power Armor +5 |  | 0x4800095D | ABC |
| `0x40000574` | Zeiss Goggles (2) | Att | 2 | 1000 | 750 | `0x40000587` | `0x40000571` | Attack Damage +15; Attack Speed +%0.15 |  |  | ABC |
| `0x40000575` | Shade's Cane (1) | Att | 1 | 750 | 565 |  | `0x4000056A` | Attack Damage +10; Attack Speed +%0.03 |  | 0x48000E88 | ABC |
| `0x40000576` | Phantom Stranger's Necklace (3) | Def | 3 | 2000 | 1500 | `0x40000572` |  | Attack Armor +20; Power Armor +10; Cooldown Reduction +0.1 |  | 0x4800095D | ABC |
| `0x40000577` | The Crime Bible (1) | Uti | 1 | 500 | 450 |  | `0x4000056E` | Health +75; Health Regeneration +1 |  |  | A |
| `0x40000578` | Steel's Breastplate (1) | Def | 1 | 500 | 450 |  | `0x4000057E` | Will +125; Attack Armor +10 |  |  | ABC |
| `0x40000579` | Radion Shard (1) | Pow | 1 | 250 | 225 |  | `0x40000580` | Power Damage +12 |  |  | AC |
| `0x4000057A` | Zeiss Goggles (4) | Att | 4 | 2500 | 1875 | `0x40000571` |  | Attack Damage +30; Attack Speed +%0.3 |  | 0x4800103E | ABC |
| `0x4000057B` | Pandora's Box (1) | Pow | 1 | 500 | 450 |  | `0x40000593` | Will Regeneration +%0.15; Power Damage +15 |  |  | ABC |
| `0x4000057D` | Fatality's Energy Lance (1) | Pow | 1 | 500 | 450 |  | `0x40000588` | Power Damage +20 |  |  | ABC |
| `0x4000057E` | Steel's Breastplate (2) | Def | 2 | 1250 | 940 | `0x40000578` | `0x40000582` | Health +100; Will +200; Attack Armor +20 |  |  | ABC |
| `0x4000057F` | The Logoz (3) | Pow | 3 | 2000 | 1500 | `0x40000583` |  | Will +300; Power Damage +30 |  | 0x48000917 | ABC |
| `0x40000580` | Radion Shard (2) | Pow | 2 | 500 | 375 | `0x40000579` | `0x40000584` | Power Damage +25 |  |  | AC |
| `0x40000582` | Steel's Breastplate (3) | Def | 3 | 2500 | 1875 | `0x4000057E` |  | Health +200; Will +300; Attack Armor +30 | 0x480009BD |  | ABC |
| `0x40000583` | The Logoz (2) | Pow | 2 | 1000 | 750 | `0x40000592` | `0x4000057F` | Will +75; Power Damage +10 |  | 0x48000917 | ABC |
| `0x40000584` | Radion Shard (3) | Pow | 3 | 1000 | 750 | `0x40000580` | `0x40000586` | Power Damage +45 |  |  | AC |
| `0x40000585` | Fatality's Energy Lance (3) | Pow | 3 | 1750 | 1315 | `0x40000588` | `0x4000058C` | Power Damage +50; Power Penetration +15 |  |  | ABC |
| `0x40000586` | Radion Shard (4) | Pow | 4 | 1500 | 1500 | `0x40000584` |  | Power Damage +50 |  | 0x480008D3 | AC |
| `0x40000587` | Zeiss Goggles (1) | Att | 1 | 500 | 450 |  | `0x40000574` | Attack Damage +7; Attack Speed +%0.07 |  |  | ABC |
| `0x40000588` | Fatality's Energy Lance (2) | Pow | 2 | 1000 | 750 | `0x4000057D` | `0x40000585` | Power Damage +30; Power Penetration +10 |  |  | ABC |
| `0x40000589` | Deadshot's Visor (1) | Att | 1 | 750 | 565 |  | `0x40000558` | Will +75; Attack Damage +10; Attack Speed +%0.08 |  |  | ABC |
| `0x4000058A` | Pandora's Box (4) | Pow | 4 | 3000 | 2250 | `0x4000058D` |  | Move Speed +0.05; Will Regeneration +%0.4; Power Damage +60; Cooldown Reduction +0.15 | 0x48000EC1 |  | ABC |
| `0x4000058B` | Huntress' Crossbow (3) | Att | 3 | 3000 | 2250 | `0x4000058F` |  | Attack Damage +40; Attack Speed +%0.3 |  | 0x480007D3 | ABC |
| `0x4000058C` | Fatality's Energy Lance (4) | Pow | 4 | 3000 | 2250 | `0x40000585` |  | Power Damage +70; Power Penetration +20 | 0x48000992 |  | ABC |
| `0x4000058D` | Pandora's Box (3) | Pow | 3 | 1750 | 1315 | `0x40000593` | `0x4000058A` | Move Speed +0.05; Will Regeneration +%0.3; Power Damage +40; Cooldown Reduction +0.1 |  |  | ABC |
| `0x4000058E` | Gorilla Grodd's Helmet (3) | Pow | 3 | 1750 | 1315 | `0x40000591` | `0x40000595` | Resilience +0.15; Will +300; Cooldown Reduction +0.1 |  | 0x48000FBC | ABC |
| `0x4000058F` | Huntress' Crossbow (2) | Att | 2 | 2250 | 1690 | `0x40000590` | `0x4000058B` | Attack Damage +40; Attack Speed +%0.2 |  |  | ABC |
| `0x40000590` | Huntress' Crossbow (1) | Att | 1 | 1250 | 940 |  | `0x4000058F` | Attack Damage +20; Attack Speed +%0.15 |  |  | ABC |
| `0x40000591` | Gorilla Grodd's Helmet (2) | Pow | 2 | 750 | 375 | `0x4000055C` | `0x4000058E` | Will +200; Cooldown Reduction +0.05 |  | 0x480007DC | ABC |
| `0x40000592` | The Logoz (1) | Pow | 1 | 250 | 225 |  | `0x40000583` | Will +75; Power Damage +5 |  |  | ABC |
| `0x40000593` | Pandora's Box (2) | Pow | 2 | 1000 | 750 | `0x4000057B` | `0x4000058D` | Move Speed +0.05; Will Regeneration +%0.15; Power Damage +30 |  |  | ABC |
| `0x40000594` | Fragment of Mogo (1) | Def | 1 | 750 | 565 |  | `0x40000559` | Health +100; Attack Armor +15 |  |  | ABC |
| `0x40000595` | Gorilla Grodd's Helmet (4) | Pow | 4 | 2500 | 1875 | `0x4000058E` |  | Resilience +0.15; Will +400; Cooldown Reduction +0.1 | 0x48000FB6 | 0x48000FBC | ABC |
| `0x40000597` | The Medusa Mask (1) | Def | 1 | 500 | 450 |  | `0x4000055D` | Health Regeneration +1; Will Regeneration +%0.25 |  |  | ABC |
| `0x40000598` | Deadshot's Visor (3) | Att | 3 | 3000 | 2250 | `0x40000558` |  | Will +300; Attack Damage +40; Attack Speed +%0.3 | 0x480009B7 |  | ABC |
| `0x40000599` | Shade's Cane (3) | Att | 3 | 2500 | 1875 | `0x4000056A` |  | Attack Damage +42; Attack Speed +%0.09 |  | 0x48000E86 | ABC |
| `0x4000059A` | Fragment of Mogo (3) | Def | 3 | 2750 | 2065 | `0x40000559` |  | Health +250; Attack Armor +40 | 0x4800098F |  | ABC |
| `0x4000059B` | Cheetah's Claw (3) | Att | 3 | 1250 | 940 | `0x4000055A` | `0x4000055E` | Attack Lifesteal +0.06; Attack Speed +%0.25 |  |  | ABC |
| `0x4000059F` | Hawkman's Harness (2) | Def | 2 | 500 | 375 | `0x400005A1` | `0x400005A0` | Health +125 |  |  | AC |
| `0x400005A0` | Hawkman's Harness (3) | Def | 3 | 1000 | 750 | `0x4000059F` | `0x400005A2` | Health +225 |  |  | AC |
| `0x400005A1` | Hawkman's Harness (1) | Def | 1 | 250 | 225 |  | `0x4000059F` | Health +65 |  |  | AC |
| `0x400005A2` | Hawkman's Harness (4) | Def | 4 | 1500 | 1500 | `0x400005A0` |  | Health +275 |  | 0x480008D3 | AC |
| `0x40000617` | Atlantis Gambit (4) | Att | 4 | 2500 | 1875 | `0x400004A0` |  | Health Regeneration +1.5; Attack Damage +30 | 0x4800099C | 0x480007C5 | ABC |
| `0x40000618` | Olympus Gambit (4) | Def | 4 | 2500 | 1875 | `0x400004B2` |  | Health +200; Attack Armor +10; Power Armor +10 | 0x4800094B | 0x480007C6 | ABC |
| `0x40000619` | Oa Gambit (4) | Def | 4 | 2500 | 1875 | `0x40000508` |  | Power Damage +40; Power Armor +40 |  | 0x480007C8 | ABC |
| `0x4000061A` | Qward Gambit (4) | Pow | 4 | 2500 | 1875 | `0x4000048F` |  | Will +300; Power Damage +30 | 0x480009B9 | 0x480007C9 | ABC |
| `0x4000061B` | Bleed Portal | Uti |  | 500 | 250 |  |  |  | 0x480009A0 |  | ABC |
| `0x4000061C` | Speed Force Battery (1) | Uti | 1 | 1250 | 625 |  | `0x4000061D` |  | 0x48001461 |  | ABC |
| `0x4000061D` | Speed Force Battery (2) | Uti | 2 | 2000 | 1000 | `0x4000061C` |  | Move Speed +0.1 | 0x48001461 |  | ABC |
| `0x400008C1` | Modular Tektite Vial (3) | Uti | 3 | 500 | 165 | `0x400008C2` |  |  | 0x48000CD1 |  | ABC |
| `0x400008C2` | Modular Tektite Vial (2) | Uti | 2 | 250 | 85 | `0x400008C3` | `0x400008C1` |  | 0x48000CD2 |  | ABC |
| `0x400008C3` | Modular Tektite Vial (1) | Uti | 1 | 100 | 35 |  | `0x400008C2` |  | 0x48000CD3 |  | ABC |
| `0x400008C6` | Doctor Destiny's Dreamstone (4) | Pow | 4 | 3000 | 2250 | `0x400004B8` |  | Will Regeneration +%0.5; Power Damage +60; Cooldown Reduction +0.15 |  | 0x480007CE | ABC |
| `0x40000925` | Modular Health Vial (1) | Uti | 1 | 100 | 35 |  | `0x40000929` |  | 0x48000CEC |  | ABC |
| `0x40000926` | Modular Will Vial (2) | Uti | 2 | 250 | 85 | `0x40000927` | `0x40000928` |  | 0x48000CED |  | ABC |
| `0x40000927` | Modular Will Vial (1) | Uti | 1 | 100 | 35 |  | `0x40000926` |  | 0x48000CEF |  | ABC |
| `0x40000928` | Modular Will Vial (3) | Uti | 3 | 500 | 165 | `0x40000926` |  |  | 0x48000CEE |  | ABC |
| `0x40000929` | Modular Health Vial (2) | Uti | 2 | 250 | 85 | `0x40000925` | `0x4000092A` |  | 0x48000CEA |  | ABC |
| `0x4000092A` | Modular Health Vial (3) | Uti | 3 | 500 | 165 | `0x40000929` |  |  | 0x48000CEB |  | ABC |
| `0x40000995` | Cosmic Belt (3) | Pow | 3 | 2250 | 1690 | `0x40000996` |  | Health +200; Power Damage +45 |  | 0x48000970 | ABC |
| `0x40000996` | Cosmic Belt (2) | Pow | 2 | 1250 | 940 | `0x40000997` | `0x40000995` | Health +125; Power Damage +20 |  | 0x48000971 | ABC |
| `0x40000997` | Cosmic Belt (1) | Pow | 1 | 500 | 450 |  | `0x40000996` | Health +75; Power Damage +5 |  |  | ABC |
| `0x4000099A` | Mirror Master's Prism (1) | Def | 1 | 500 | 450 |  | `0x4000099C` | Health +50; Power Armor +10 |  |  | ABC |
| `0x4000099B` | Mirror Master's Prism (3) | Def | 3 | 2000 | 1500 | `0x4000099C` | `0x4000099D` | Health +125; Power Armor +40 |  | 0x48000D60 | ABC |
| `0x4000099C` | Mirror Master's Prism (2) | Def | 2 | 1250 | 940 | `0x4000099A` | `0x4000099B` | Health +100; Power Armor +30 |  |  | ABC |
| `0x4000099D` | Mirror Master's Prism (4) | Def | 4 | 2750 | 2065 | `0x4000099B` |  | Health +150; Power Armor +50 |  | 0x48000EB6 | ABC |
| `0x40000B0C` | Booster Gold's Power Suit™ (1) | Def | 1 | 750 | 565 |  | `0x40000B0D` | Health +100; Attack Armor +15 |  |  | ABC |
| `0x40000B0D` | Booster Gold's Power Suit™ (2) | Def | 2 | 1500 | 1125 | `0x40000B0C` | `0x40000B0E` | Health +150; Attack Armor +30; Cooldown Reduction +0.05 |  |  | ABC |
| `0x40000B0E` | Booster Gold's Power Suit™ (3) | Def | 3 | 2750 | 2065 | `0x40000B0D` |  | Health +300; Attack Armor +40; Cooldown Reduction +0.1 |  | 0x48000F09 | ABC |
| `0x40000BDE` | Mr. Terrific's T-Mask (4) | Pow | 4 | 2000 | 1500 | `0x40000BDF` |  | Will +400; Power Damage +20 | 0x48000FA8 | 0x48000971 | ABC |
| `0x40000BDF` | Mr. Terrific's T-Mask (3) | Pow | 3 | 1250 | 940 | `0x40000BE0` | `0x40000BDE` | Will +300; Power Damage +10 | 0x48000FA8 |  | ABC |
| `0x40000BE0` | Mr. Terrific's T-Mask (2) | Pow | 2 | 750 | 565 | `0x40000BE1` | `0x40000BDF` | Will +200; Power Damage +10 |  |  | ABC |
| `0x40000BE1` | Mr. Terrific's T-Mask (1) | Pow | 1 | 250 | 225 |  | `0x40000BE0` | Will +100 |  |  | ABC |
| `0x40000C08` | Diana's Bracers (3) | Def | 3 | 2750 | 2065 | `0x400004CB` |  | Resilience +0.3; Health Regeneration +2; Attack Armor +20 |  | 0x480007D0 0x4800101A | ABC |
| `0x40000D1A` | Deathstroke's Claymore (3) | Att | 3 | 3250 | 2440 | `0x400004B7` |  | Attack Damage +50; Attack Penetration +15; Cooldown Reduction +0.1 | 0x480012BA |  | ABC |
| `0x40000E6A` | Mobius Core (2) | Uti | 2 | 2000 | 1000 | `0x40000E6B` |  | Power Armor +40 | 0x4800145B |  | ABC |
| `0x40000E6B` | Mobius Core (1) | Uti | 1 | 1250 | 625 |  | `0x40000E6A` | Power Armor +20 | 0x4800145B |  | ABC |
