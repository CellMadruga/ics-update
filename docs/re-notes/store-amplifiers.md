# Main-menu store (SHOP) and amplifier sets (2026-10-28, fase3-ie)

Tester 2026-10-28 ~13:52: "could you try to enable the shop and creating amplifier sets?" (main menu, account level
30, 50 / 800 currencies). Tags: **C** confirmed (code / data / log), **P** probable, **O** open.

Sources: the AS2 dump `old_files/tools/gfx/classes_all.txt` (line numbers below), the decompiled exe
`re-work/decomp/c/*.c`, the vtables read from `InfiniteCrisis.exe`, the run of 13:38-13:53 (`logs/traffic.log`).
Companion notes: `account-systems-data.md` 1.2-1.4 / 2, `full-account-social.md` 4-5.

## 1. What the last run shows [C]

| time | client | server |
|---|---|---|
| 13:38:52, 13:50:51 | `0x20BA` (request all sets) | `0x2090` total 0, max 6, no set |
| 13:52:30 | `0x2106` (amplifiers screen opened) | `0x2107` 335 prices |
| SHOP | nothing on the game connections (a CEF page) | - |

No message went unanswered: the problems are in what was answered.

## 2. Amplifier sets

| Finding | Evidence | Tag |
|---|---|---|
| `NotifyListAmplifierSets(total, max, ...)` builds `total` rows: rows `i < slotIDs.length` from the server, the rest `clientOnlySet = true` with the lowest free id and the first set icon | `AmplifierSetManager` l.82058-82246 | C |
| total 0 -> no row -> nothing to select or save: the reported bug | log + above | C |
| `GetPlayerHasMaxNumberOfAmplifierSets` = `!(current < max)` (true until the list arrived) | l.81979-81995 | C |
| while not at max the Assembler adds a "for sale" row from the first ContentType-5 ownable + its boutique data by DID; the slot name / icon come from `UI_InqAmplifierSetSlotInfo` | l.385643-385760 | C |
| save = `UI_SaveAmplifierSet(ampSetID, didCharacter, name, didSetIcon, e1..e7)` of the working set; empty icon -> first set icon | l.387990-388068 | C |
| `NotifyAmplifierSet` (`0x20C7`) updates only a set whose id is already listed (else ignored) | l.81997-82055 | C |
| the set slot item is `0x49000AA2` (only the `0x49` record exists, no `0x40` twin) | packs | C |
| `didCharacter` of a new set: 0 or the champion chosen in the Assembler | not traced | O |
| the original number of free slots / the max | not in the data | O (config) |

Server (ics): `0x2090` total = `max(saved sets, account slots, highest saved slot)`, max = `[ics] amplifier_set_max`;
`0x20FC` stores at the client's slot; `0x20B8` lists `0x49000AA2` (type 5, not owned) while for sale; a bought slot
(`0x210E` or the store page) adds one slot and sends `0x2090` again; a purchase past the max -> `0x210D`.

## 3. Applying a set in the match

| Finding | Evidence | Tag |
|---|---|---|
| augment stats: twin `0x10000950` entries {`0x10000952` op 9 add / 10 percent, `0x10000958` stat, `0x10000954` f32} | records, `account-systems-data.md` 1.1 | C |
| the stat keys are the champion stats keys (Health `0x10000426`, Attack Damage `0x10000B76`, Attack Speed `0x100006FE` percent, Move Speed `0x100005E4`, CDR `0x10000B7B`, armors, pens, lifesteals) | data | C |
| no client code applies `0x10000950` to the champion: server work | `account-systems-data.md` 1.1 | C |
| mods change artifacts (discounts, artifact stats, keyword swaps) | data | C (layout) / O (server effect) |

Server: the lobby's set (`0x2098` pick, remembered per champion; else the newest set for that champion or for no
champion; else the default loadout) -> `Account.amplifier_bonuses` -> `champion.amp_add` / `amp_pct`, folded in by
`World.recompute_stats` apart from the items; the HUD modifiers (`0x20F0`) carry them with the items' after the first
shop change. Bots keep no amplifier stats. Mods: not applied (O).

## 4. Store (SHOP) screen

| Step | Evidence | Tag |
|---|---|---|
| `Store.OnLoadComplete` -> `NavigateToStore` -> `EM_WebTicket.UI_RequestWebTicket` | l.366720, 366852 | C |
| the C++ listener: app object (`0x420950`, built by `0x4084A0`, app+0x1A8), interface vtable `0x15A63BC` = {`0x420B90`}: raises `UI_OnWebTicketUpdated(GUID text, shard)` (`0x6971D0`) at once | vtable bytes, decomp | C |
| the GUID + shard come from S->C event `0xC2` (`0x420920`); never sent -> zero GUID | decomp | C (store) / P (no other check) |
| `RecvNotice_UI_OnWebTicketUpdated` -> `GM_UI.InqStoreURL` -> `HTTPRequest(url + headers webticket, shard)` | l.367070-367113 | C |
| URL = app config (+0x144) else AuthSelect `nameValuePairs` `URL.Store` else `0xA9B3B0` default | `0xA9B890` | C |
| `OnLoadEnd` status >= 400 -> error dialog + back to landing; else hide spinner; JS callbacks `OnShowSpinner` / `OnHideSpinner` | l.367157-367240 | C |
| MicroTxn (Steam) -> `FinalizeSteamPurchase("order", bool)` in the page | `0x420C00`, l.367115 | C |

Server: AuthSelect sends `URL.Store` (after `loginTicket`, the response's field order) = `http://host:soap_port/store`;
the SOAP listener serves `GET /store` (wallet, set slots, champions, skins, augments, mods, `[ics] store_prices`) and
`POST /store/buy` (form field `did`): the purchase runs in the logged-in session (`Session._complete_purchase`) and the
client gets `0x210C`, `0x20B8`, `0x2081`, `0x2095` (and `0x2090`). Not yet seen in the real client: whether its CEF
accepts the plain form post and redirect (P), and whether the page's size fits the screen (O).

## 5. Open

- The amplifier screen's per-amplifier "buy" (`UI_InqAugmentModStoreUrls`, `URL.Augment` / `URL.Mod`): not sent (O).
- Mods' effects in the match (artifact discounts in the shop, artifact stat changes, keyword swaps) (O).
- Bots' amplifier stats (their default loadout) (O).
- `0xC2` web ticket: harmless without it for the local page; its destination object id is not known (O).
