# Store (SHOP) page and amplifier-screen purchases: root causes and fix plan (2026-10-28, fase3-if)

Tester report 2026-10-28 15:00 (run 14:39-15:00, Crime Alley v AI): SHOP shows the embedded browser's own version
page (screenshot 42: CEF 3.1650.1639, Chromium 31.0.1650.57, TurbineBrowser/4.0) and `server.log` has no request for
`/store`; buying an amplifier set slot in the amplifiers screen does nothing (`0x210E` "store purchase 0x49000aa2 for
4294967295 SC/HC", four times, 14:55:48-58).

Tags: **C** confirmed (code / data / log bytes), **P** probable, **O** open. Static base 0x400000; the exe is the
original `InfiniteCrisis.exe`; every function below is byte-identical in `InfiniteCrisis_patched.exe` (checked).
Sources: `re-work/decomp` (pseudo-C, strings.tsv, functions.tsv), capstone on the exe, the AS2 sources
`re-work/ui-as2/c_a00000d0_02189b08/scripts/__Packages` (`AS2:` below), the server's record reader, the run's logs.
Supersedes section 4 of `store-amplifiers.md` (see 2.6). Second pass (18:50): every claim of the first pass re-checked;
additions marked "(2nd pass)".

## 0. Root causes (both C)

1. **SHOP**: the client reads AuthSelect's `nameValuePairs` as a gSOAP `NameValuePairArray` whose items are child
   elements named `nameValuePairs` (`0xADE2D0`). fase3-ie wrote the pair flat (`<nameValuePairs><name>..`), which parses
   as an empty array: `URL.Store` not found, the store URL is "", `Turbine.Browser.NavigateByInfo` drops the request
   (`0x8308C0` IsValid = false) and the browser stays on its creation URL `chrome://version` (`0x83172A`).
2. **Set slot purchase**: `BoutiqueDataManager` keeps a price only for the currency names `"SC"` / `"HC"` (case
   ignored). The server named every `0x2107` price `"Merits"` (`[ics] store_currency`), so every cost stayed -1, the
   dialogs sent price `0xFFFFFFFF`, the server answered `0x210F` "price changed", which no UI listens to: nothing
   happened. The client has no other price source (no price in any record).

## 1. Evidence from the run

The `logs\` folder was empty when re-checked at 18:50; the excerpts below were copied from the run's logs by the first
pass (15:29) and by `test-2026-10-28-1439-sweep.md` section 12.

| What | Evidence | Tag |
|---|---|---|
| Login | `server.log` 14:39:14.780 `SOAP AuthSelect handled`; only `Metrics` and `AuthSelect` SOAP ops (no `getLauncherData`: the game ran without the launcher; command line in screenshot 42: `--loginurl http://127.0.0.1:8888/WebLoginApp-1.3/AuthenticateWS --loginregion NA --reportingurl .../Metrics --language en`, shown re-ordered by CEF) | C |
| SHOP opened 4 times | `unhandled.log` `MENU event 0x0095 dest 0x0600000000000415 flags 0x1` (empty body) at 14:39:21, 14:39:30, 14:54:51, 14:59:10. `0x95` is built only by `0x692DF0`, whose only caller is the web-ticket listener `0x420B90`, which first raises `UI_OnWebTicketUpdated` (`0x420BA5 call 0x6971D0`) and then sends `0x95` (`0x420BBC call 0x692DF0`). The only live sender of `UI_RequestWebTicket` is `Store.NavigateToStore` (the Assembler's `OpenStoreToAugmentOrModPage` is dead code, 2.5) | C (2nd pass) |
| No store request | no `store page: GET /store` line in `server.log` (the SOAP listener logs every `/store` request before answering) | C |
| Screenshot 42 | the page is CEF's `chrome://version` (CEF / Chromium / User Agent / Command Line / Module Path / Cache Path) | C |
| `0x2107` sent | `traffic.log` 14:54:56.727, 335 entries `u64 bid \| u32 DID \| str8 "Merits" \| u32 price`; the slot entry `a2 0a 00 49 00 00 00 0b  a2 0a 00 49  06 "Merits"  e8 03 00 00` (1000). The client parsed it (str8 is right): the purchases carried the bid `0x0B00000049000AA2` back | C |
| `0x2090` sent | `00 \| 06 00 00 00 \| 0c 00 00 00 \| 00 00 00 00` = total 6, max 12, no saved set: the "buy a set slot" row shows (6 < 12) | C |
| `0x210E` received | 14:55:48.873 `a2 0a 00 49 00 00 00 0b \| a2 0a 00 49 \| 02 "SC" \| ff ff ff ff \| 02 "en"`; again 14:55:51 SC, 14:55:54 **HC**, 14:55:58 SC | C |
| server answer | `0x210F` "purchase price changed 4294967295 -> 1000" (71 bytes) each time; nothing else, no further client message | C |

## 2. SHOP: why the store page never loaded

### 2.1 The client chain [C]

1. AS2 `gameplay/wrapper/store/Store.as`: `OnLoadComplete` registers `WebTicket.UI_OnWebTicketUpdated` (notice 100)
   and calls `NavigateToStore` (l.56): `m_bWaitingForWebTicket = true; EM_WebTicket.SendNotice_UI_RequestWebTicket()`
   (notice 99).
2. C++ listener: app sub-object built at `0x420950` (caller `0x4084A0`), interface at +0x30 with vtable `0x15A63BC`
   = {`0x420B90`}, registered by `0x4208A0` (component vtable `0x15A63F8` slot 10) through `0x68F1C0`. `0x420B90`
   (ECX = interface) raises `EM_WebTicket.RecvNotice_UI_OnWebTicketUpdated` at once (`0x6971D0`, a broadcast to the
   Flash movies) with (GUID text of obj+0x3C via `0xAFD950`, u32 obj+0x4C), then sends `0x95` to the server
   (`0x692DF0`). The GUID / u32 are set only by S->C event `0xC2` (exec `0x699550` -> `0x420920`); never sent, so a
   zero GUID and shard 0. Not needed by our page. No wait for the server: the store does not depend on `0xC2`.
3. `Store.RecvNotice_UI_OnWebTicketUpdated` (l.106) -> `GM_UI.SendQuery_InqStoreURL` (`Query_UI__InqStoreURL_ID` =
   `0x10000487`; the result is `gameOutputArgs[0]`) -> C++ **`0xA97320`** (gmConnectionManager GM_UI query vtable
   slot `0x1606E7C`): `mov ecx,[ebp+8]; add eax,0x144; push eax; call 0x402D60` = `*out = app+0x144` (app =
   `0x4092A0()`). Then `new utils.NavigateInfo(url)` (`Turbine.Browser.NavigateInfo_CreateDesc` -> `0x9FEF20`),
   `AddHeader("webticket", ticket)`, `AddHeader("shard", n)` (`0xA02B30`), `m_wbBrowser.HTTPRequest` ->
   `Turbine.Browser.NavigateByInfo` (bridge `0xA03ED0` -> `0x9FF070`) -> `0x8330D0` -> **`0x832F30`**. The URL is used
   as is: no placeholder, token or scheme rewriting anywhere on this path.
4. `0x832F30` calls `navInfo->IsValid()` = **`0x8308C0`** (`0x832F54`, ECX = the nav info) and returns when it is false
   (`0x832F5B je 0x833035`). IsValid: the URL string (nav info +0) is not null / empty (`cmp [ecx-4],1`) **and**
   `cef_parse_url(url)` succeeds (`0x1098E80`, libcef import); else only the LoadHTML case (+8 HTML set) is valid. A
   valid request is sent at once by `0x832A80` (`cef_request_create`, URL, post data, header multimap, main frame
   `LoadRequest`) when the CEF browser exists (`0x82AB20`), else copied (`0x832900`) to +0x80 and retried on event 7
   (`0x8076C0(7)` -> `0x8330F0` -> `0x833050`, which sends it and cancels event 7 (`0x805150(7)`) once the browser
   exists; P: `0x8076C0` arms a repeating timer event).
5. Every Flash browser widget (`ui_sys.UIWidget_Browser.InitializeBrowser` -> `Turbine.Browser.CreateDesc` ->
   `0xA00790` -> `0x9FF850` -> `0x831FD0` -> **`0x831520`**, `WebBrowserCEFHandler.cpp`) is created by
   `cef_browser_host_create_browser` (`0x1099D20`, called at `0x831774`) with the initial URL **`"chrome://version"`**
   (`push 0x15EB39C` at `0x83172A`, unconditional). A store whose navigation is dropped therefore shows CEF's version
   page: screenshot 42 exactly.

### 2.2 Where app+0x144 (the store URL) comes from [C]

- AuthSelect completion handler **`0xA9B890`** (gmConnectionManager vtable `0x1606F7C`, slot `0x1606F84`; the SOAP
  call is `0xADD900` in the worker `0xA96000`, its result fetched by `0xA96B40`). On success (`errorString` absent):
  `0xA9BA8B add eax,0x144` / `0xA9BA94 call 0x402C60` copies app+0x144; when it is empty, `0xA9BAC2 push 0x16075D8`
  (L"URL.Store") / `0xA9BADB call 0xA971D0(resp->nameValuePairs (+0x18), ...)`; when still empty, `0xA9B3B0` =
  `PROJECT_STORE_URL`. `0xA9A280` then stores it: `0xA9A309 lea ecx,[esi+0x144]; push [ebp+0x20]; call 0x402D60`.
  It also reads, with `0xA96BC0` ("" when missing), `URL.Tutorial1..3`, `URL.YouTubeChannel`, `URL.ReleaseNotes`,
  `URL.GothamDivided`, `URL.GothamHeights`, `URL.CoastCity`, `URL.CrimeAlley`, `URL.Survey`, `URL.Credits`,
  `URL.UpdateNews`, `URL.Augment`, `URL.Mod`.
- **Sticky per client process** (2nd pass, C): the pair is read only while app+0x144 is empty. Once a login stored a
  URL, later logins in the same client keep it; a changed `[ics] store_url` needs a client restart. Today it is ""
  (never parsed), so the next login after the server fix reads the pair without a client restart.
- `0xA971D0` walks the array (`__size` +4, item pointers +8, item `name` +4, `value` +8) and compares names with
  `0x437DD0`: exact (length, hash, UTF-16), case-sensitive. The name must be `URL.Store`.
- Other sources ruled out: `PROJECT_STORE_URL` (map `0x1B6901C`) is written only by `0x5E3970`, called by the getters
  `0xA9B340` / `0xA9B3B0` with an empty default and by `0x5E3A90` (CA-cert path, `0xB14220`): always "". The string
  `URL.Store` is referenced only by `0xA9B890`. No command-line option sets it (option table `0x40D6E0`: loginurl,
  loginregion, reportingurl, supporturl, bugurl, gametype, prefs, ...). `TurbineLauncher.exe.config` has only
  `URL.FallbackSkin`, `LoginServer.*`, `URL.SkinVersion`. The user's `UserPreferences.ini` / `.xml` hold no URL.
  `turbinebrowser.exe` is only CEF's `--browser-subprocess-path` (renderer); CEF runs in the game process (Module Path
  `libcef.dll`), and its switches (`--product-version`, `--lang`, `--resources-dir-path`, `--locales-dir-path`,
  `--no-sandbox`) carry no URL. A capstone scan of the 8 instructions after every `call 0x4092A0` (the app getter)
  finds +0x144 only at `0xA9732B` (InqStoreURL), `0xA9B5B1` (the `BYPASS` login path of `0xA9B420`, which also falls
  back to `PROJECT_STORE_URL`) and `0xA9BA8B`; the one writer is `0xA9A309` (esi = app).
- No host / scheme filter on the navigation path (`0x832F30`, `0x832A80`; strings `0x15EB2C8`-`0x15EB460`:
  `about:blank` is the LoadHTML base URL, `about:%ls` an error-page helper `0x830AB0`, `%s\cacert.pem` the CA path).
  CEF's request-handler callbacks were not enumerated (P: none filters).

### 2.3 The AuthSelect response type: why our pair was dropped [C]

gSOAP types of the login web service (deserializer / serializer pairs in the exe):

| Type | in / out | Members (offset) |
|---|---|---|
| `SOAP1:AuthSelectResponse` | `0xADE8B0` | `return` : `SOAP1:authResponseMessage` |
| `SOAP1:authResponseMessage` (type 9, 0x38 bytes) | `0xADE4F0` / `0xADC7C0` | `errorString` (+0x08), `loginTicket` xsd:long (+0x10), **`nameValuePairs` : pointer to `SOAP1:NameValuePairArray`** (+0x18, read by `0xADD710`), `newSocialMediaEncryptionKey` (+0x1C), `oldSocialMediaEncryptionKey` (+0x20), `randomID` (+0x24), `sessionKey` (+0x28), `userServerAddr` (+0x2C), `userServerPort` xsd:int (+0x30) |
| `SOAP1:NameValuePairArray` (type 10) | `0xADE2D0` / `0xADC520` | loop `soap_element_begin_in(soap, "nameValuePairs")` (`0x41BD50`) -> `0xADD600` "SOAP1:NameValuePair"; `__size` +4, items +8. The serializer writes one child element `nameValuePairs` per item |
| `SOAP1:NameValuePair` (type 11) | `0xADE0F0` | `name` (+4, tag `0x15A609C` = "name"), `value` (+8) |

So the pairs are nested one level:
`<nameValuePairs><nameValuePairs><name>URL.Store</name><value>..</value></nameValuePairs></nameValuePairs>`.
This is the same shape the launcher's `getLauncherData` answer already uses (`<return>` is itself the array:
`<return><nameValuePairs><name>..</name>..</nameValuePairs>..</return>`, `ics/server.py launcher_data`).

The fase3-ie `auth_select` (`ics/server.py` l.136-148) writes `<name>` / `<value>` directly inside the outer element:

```
<return><loginTicket>1001</loginTicket><nameValuePairs><name>URL.Store</name><value>http://127.0.0.1:8888/store</value>
</nameValuePairs><randomID>1</randomID><sessionKey>LOCALSESSIONKEY0001</sessionKey><userServerAddr>127.0.0.1
</userServerAddr><userServerPort>9000</userServerPort></return>
```

The array loop finds no child named `nameValuePairs`; `<name>` and `<value>` are skipped by `0xADB4B0`
(soap_ignore_element) because the client parses non-strict (C: with `SOAP_XML_STRICT`, mode bit 0x1000 tested at the
end of `0xADE4F0`, an unknown child is an error and the login itself would have failed; it succeeded). Result: an
empty array, `URL.Store` not found, URL "". A model of the client's reading (outer `nameValuePairs` -> children named
`nameValuePairs` -> `name` / `value`, run on `Server.auth_select()` output) gives `{}` for the current XML and
`{'URL.Store': 'http://127.0.0.1:8888/store'}` for the nested form (2nd pass).

Element order in `authResponseMessage` is free (gSOAP tries every member for each element); keep the schema order
anyway (after `loginTicket`, before `randomID`).

### 2.4 What the page must do [C unless marked]

- Request: `GET <URL.Store>` (main frame `LoadRequest`) with headers `webticket` (GUID text, zero GUID today) and
  `shard` (decimal, 0); no POST data. Our page may ignore both.
- `Store.RecvNotice_OnLoadEnd` (l.140; first main-frame load only, `m_bInitialPageLoad`): HTTP status >= 400 -> error
  dialog (`#0D6D26C5|`) and back to the landing screen; else the loading cover fades out. The first load can be the
  `chrome://version` creation page itself (P); later loads (form posts, redirects) are not watched. JS callbacks
  `OnShowSpinner` / `OnHideSpinner` are optional (the page may call them).
- The page is drawn off-screen into the Flash widget (`DataCache.LoadBrowser`), an area of about 1715 x 800 px in the
  1911 x 1007 screenshot 42; the X (`m_btnContinue`) returns to the landing screen.
- `URL.Augment` / `URL.Mod` are not needed: the Assembler's `OpenStoreToAugmentOrModPage` (l.863) returns while
  `m_adAmplifierClickedForPurchase` is null, and nothing ever sets it (only `= null`, l.880). Do not send
  `URL.UpdateNews` / `URL.ReleaseNotes` (other landing-screen features) (P).
- Navigation from `chrome://version` (a CEF internal scheme page, not WebUI) to `http://127.0.0.1` in the same main
  frame (P: Chromium 31 forks only WebUI / view-source / file navigations).

### 2.5 The amplifier screen's store links: dead code [C]

`Assembler` reads `UI_InqAugmentModStoreUrls` (`URL.Augment` / `URL.Mod`) at load (l.92) and would request a web
ticket and open a `BrowserDialog` (l.863-897), but only from `OpenStoreToAugmentOrModPage`, unreachable (2.4).

### 2.6 Corrections to store-amplifiers.md section 4

- `0xA9B890` is the AuthSelect completion handler (once per login), not `InqStoreURL`; `InqStoreURL` is `0xA97320`
  and only returns app+0x144.
- The `0xA9B3B0` default is empty: without a parsed `URL.Store` the store has no URL at all.
- The fase3-ie `URL.Store` pair was sent in the wrong shape (2.3).

## 3. Amplifier screen: "store purchase 0x49000aa2 for 4294967295"

### 3.1 Where the client gets prices [C]

- Only from `0x2107` (`Amplifier.NotifyContextualAmplifierData`, handler `0xA57510`: entries of 0x18 bytes, boutique
  ids turned into `%I64d` text, DIDs, currency names, values) -> AS2 `BoutiqueDataManager.RecvNotice_
  NotifyContextualAmplifierData` (l.49): per entry, by DID: `boutiqueID = id`; `if (name.toLowerCase() == "sc")
  softCurrencyCost = value; else if (... == "hc") hardCurrencyCost = value` (l.69 / l.73). Any other name sets no
  price. `BoutiqueData` starts at soft = hard = **-1** (l.17-18). One `BoutiqueData` per DID: several entries for the
  same DID fill both costs; the last entry's id is the `boutiqueID` the purchase sends, so one id for both currencies.
- The `BoutiqueDataManager` singleton sends `0x2106` when first used; `0x2106`'s str8 is the client language (app
  vtable +0xDC, the same getter as `0x210E`'s trailing "en"), not a currency key (2nd pass, C by `0xA2FCD0`).
- `0x20B8` has no price (17-byte items: DID, status, type, owned, count). The slot record `0x49000AA2` holds only
  `0x1000095E` icon `0x13002966`, `0x10000AFA` = 1, `0x1000095F` name; an augment twin (`0x49000689`) holds its stat
  lines `0x10000950`, two strings, `0x100009EF` = 1 and `0x10000956` = 7: no price (server reader run, 2nd pass). No
  record holds a store price (`account-systems-data.md` 2.3). A web search found no published prices either
  (engadget.com 2013-10-08 "amplifier set preview", segmentnext.com "October patch to add amplifiers": sets = 4
  augments + 3 mods, no prices).
- The server named every price `"Merits"` (`[ics] store_currency`): every cost stayed -1; the boutique id was taken,
  so the purchase carried the right id `0x0B00000049000AA2`.

### 3.2 The purchase dialogs [C]

- Set slot: shown while `!GetPlayerHasMaxNumberOfAmplifierSets()` (= set data received and current < max,
  `AmplifierSetManager` l.64) for the first ContentType-5 ownable that has boutique data by DID (Assembler l.444-469;
  owned or not does not matter). `AmplifierSetForSaleListItem` shows `String(soft)` and `String(hard)` ->
  `OnBuySlotClick` -> `DualCurrencyPurchaseDialog`: `m_btnUnlockSoft._visible = Merits >= soft`, `m_btnUnlockHard.
  _visible = CrisisCoins >= hard` (l.62-65; both visible with -1), click -> `purchasePendingCurrency` = SOFT / HARD and
  `GM_Contextual.SendNotice_UI_PurchaseContextualItem(boutiqueID, did, "SC" | "HC", cost)`; the dialog closes at once
  (no wait, no timeout, no feedback of its own). A missing HC price shows "-1" and a clickable hard button: the slot
  needs both prices.
- Augment / mod: `AmplifierPurchaseDialog`: soft cost only, sends `"SC"`, spinner and a 10 s timeout (error
  `#00242025|`) until a success / error dialog replaces it. (With `grant_all_amplifiers` every amplifier is owned and
  this dialog never opens.)
- Wire (`0x210E`, listener `0xA46FC0` -> send `0x8854D0` -> builder `0x8852A0`): `u64 boutique id (the id text
  through 0xAE9F60) | u32 DID | str8 "SC"/"HC" | u32 price | str8 language`. The price is the client's displayed cost
  (-1 -> `0xFFFFFFFF`).

### 3.3 What updates the client after 0x210E [C]

| Server message | Client |
|---|---|
| `0x210C` u64 id (handler `0xA359B0`, `%I64d`) | `Assembler.RecvNotice_PurchaseContextualItemSuccess` (l.820): BoutiqueData by id -> OwnableData by DID: type 12/13 -> `OWNED_PENDING`, `AmplifierPurchaseCompleteDialog` (cost = soft), asks `0x2106` again; type 5 -> `DualCurrencyPurchaseCompleteDialog` (shows the pending currency's cost, resets it) |
| `0x210D` u64 id, u32 error (`0xA35920`) | l.802: `0x10000069` InsufficientFunds -> `#03E93A25|` dialog; `0x10000068` GeneralError / other -> `#01657175|` |
| `0x210F` price changed (`0xA35A30`, raises `GM_Contextual.RecvNotice_PurchasePriceChanged`) | **no listener in any AS2 package** (only the dispatcher): ignored; so `0x2110` / `0x2111` never come from this UI |
| `0x2081` u32 hard, u32 soft | header and open dialogs (`EVENT_CURRENCY_BALANCE_CHANGE`) |
| `0x20B8` incremental, type 5 / 12 / 13 | `AmplifierSetManager.OnIncrementalItemStatusesUpdate` -> `AMPLIFIER_DATA_RECEIVED` -> `Assembler.OnAmplifierDataUpdate` -> sends `0x20BA` |
| `0x2090` | `NotifyListAmplifierSets` -> `Assembler.OnAmplifierSetsAllUpdated` rebuilds the rows (one more empty set; the for-sale row stays while total < max) |

In the run the server answered every `0x210E` with `0x210F` only (price check `0xFFFFFFFF != 1000`), which the UI
ignores: nothing happened and the tester clicked four times. The success path of `_complete_purchase` (`0x210C`,
`0x20B8`, `0x2081`, `0x2095`, then `0x2090` for a slot) is the right answer once the price matches.

### 3.4 Server faults (ics) [C]

1. `ics/session.py` `ev_request_boutique` (l.1651): currency name `[ics] store_currency` ("Merits") instead of
   `"SC"` / `"HC"`; no Crisis Coin prices at all, though the slot dialog shows both.
2. `ev_store_purchase` (l.1667): a price mismatch answers `0x210F` (no UI); a -1 price is not recognised.
3. `_complete_purchase` (l.1687): pays from `[ics] store_currency`, not from the currency the client chose; and
   `Account.spend` (`ics/account.py` l.406) maps "HC" to Merits ("hard" only for hard / crisiscoins / coins).
4. Default `store_prices.amp_slot` 1000 > the tester's 800 Merits: even with the names fixed only a Crisis Coin price
   would let the tester buy a slot.

## 4. Open

- The original prices (Merits and Crisis Coins) of set slots, augments, mods, champions, skins: not in the client data
  nor found published; configuration only (O). The tester's wallet in the run: 800 Merits, 50 Crisis Coins.
- Whether the original server used one boutique id per currency (P: this client keeps one id per DID, so one id
  serves both).
- `0xC2` web ticket: its destination object id is not known (O); not needed by our page. `0x95` should be logged,
  not left in `unhandled.log`.
- CEF and a system proxy (O: Chromium 31 sends loopback through a configured proxy unless bypassed).
- The page's look inside the ~1715 x 800 browser area (O, needs a screenshot after the fix).
- If the page still does not load after the fix while `server.log` shows the `0x95` line and no `GET /store`: the
  first renderer-side `LoadRequest` after the browser's creation would be the suspect (O, low).

## 5. Implementation plan

All behaviour changes get an `ics/config.py` default with a comment citing "tester report 2026-10-28 15:00
(store-fix.md)". Line numbers as of 18:50.

### 5.1 SHOP page: nested pairs (`ics/server.py`)

- `Server.auth_select` (l.136-148): build the pairs as the client's `NameValuePairArray`:
  ```python
  pairs = [("URL.Store", store)] if store else []
  if pairs:
      items = "".join(f"<nameValuePairs><name>{escape(k)}</name><value>{escape(v)}</value></nameValuePairs>"
                      for k, v in pairs)
      block = f"<nameValuePairs>{items}</nameValuePairs>" if ic.get("auth_pairs_nested", True) else items
      inner = inner.replace("</loginTicket>", "</loginTicket>" + block, 1)
  ```
  Result: `...<loginTicket>1001</loginTicket><nameValuePairs><nameValuePairs><name>URL.Store</name><value>
  http://127.0.0.1:8888/store</value></nameValuePairs></nameValuePairs><randomID>1</randomID>...`.
- Leave `launcher_data` as it is (its `<return>` is the array already).

### 5.2 Boutique prices and purchases (`ics/session.py`, `ics/account.py`, `ics/messages.py`)

- `Session._boutique()` (l.1630): value `(did, ct, soft_price, hard_price)` from `store_prices` / `store_prices_hc`;
  an item is sold when either is > 0. Update its users: `ev_request_boutique`, `ev_store_purchase`,
  `_complete_purchase`, `ev_store_confirm`, `ics/store_web.py` (`entries`, `buy`).
- `ev_request_boutique` (l.1651): with `store_boutique_currency_keys`, per augment / mod / slot item one entry
  `(bid, did, "SC", soft)` when soft > 0 and one `(bid, did, "HC", hard)` when hard > 0, the same `bid = BOUTIQUE_BASE
  | did`; else the fase3-ie entries (`store_currency`, soft). `messages.amplifier_boutique` (l.1098) is unchanged; fix
  its docstring (names "SC" / "HC" read by `BoutiqueDataManager`).
- `ev_store_purchase` (l.1667): `wallet = {"sc": "soft", "merits": "soft", "soft": "soft", "hc": "hard",
  "crisiscoins": "hard", "crisis coins": "hard", "coins": "hard", "hard": "hard"}.get(cur.strip().lower())`;
  `expected = soft if wallet == "soft" else hard`; unknown currency or expected 0 -> `0x210D` GeneralError
  (`M.purchase_error(bid)`); `price != expected` (incl. `0xFFFFFFFF`) -> per `store_price_mismatch`: "error" =
  `0x210D` GeneralError + a fresh `0x2107` (the same entries as `ev_request_boutique`), "changed" = the fase3-ie
  `0x210F` + `pending_orders`, "accept" = charge `expected`; else `_complete_purchase(bid, item, wallet, expected)`.
  Log `store purchase {did:#x} for {price} {cur} -> {wallet} {expected} (0x210e)`.
- `_complete_purchase(bid, item, wallet="soft", price=None)` (l.1687): `price = price if price is not None else
  item's soft price`; `acct.spend(wallet, price)`; the rest unchanged (`0x210C`, `0x20B8` incremental, `0x2081`,
  `0x2095`, then `0x2090` for a slot; insufficient funds -> `0x210D` `0x10000069`; every slot owned -> `0x210D`).
- `ev_store_confirm` (l.1711): unreachable from this UI (3.3); keep it, store `(item, wallet, price)` in
  `pending_orders` and pass them on.
- `Account.spend` (`ics/account.py` l.406): `key = "hard" if currency.lower() in ("hard", "hc", "crisiscoins",
  "crisis coins", "coins") else "soft"` (keep the old names).
- `HANDLERS` (l.2196-2220): `0x95: Session.ev_web_ticket` = one log line `web ticket request (0x95): store screen
  opened (no 0xC2 sent: the store page needs no ticket)`, no answer. It also marks each SHOP open in `server.log`
  (2.1: one `0x95` per store open).

### 5.3 Store page (`ics/store_web.py`)

- `entries()` (l.51): rows carry both prices; `render()` (l.94): per row a "Buy (N Merits)" form and a "Buy (M Crisis
  Coins)" form when that price > 0, hidden fields `did` and `cur` (`SC` / `HC`); `handle()` (l.119) passes `cur`
  (default `SC`) to `buy(session, did, cur)` (l.76), which calls `_complete_purchase(bid, item, wallet, price)`.
  Log stays `store page: ...`.

### 5.4 Config (`ics/config.py`, `[ics]`, next to `store_url` l.757 and `store_prices` l.780)

```python
        # 2026-10-28 15:00 (tester report 2026-10-28 15:00: SHOP showed the browser's chrome://version page and no
        # GET /store reached the server; store-fix.md 2.3, C): the client reads AuthSelect's nameValuePairs as a gSOAP
        # NameValuePairArray whose items are child elements named nameValuePairs (0xADE2D0); the flat fase3-ie pair
        # parsed as an empty array, URL.Store was "" and NavigateByInfo dropped the request (0x8308C0).
        # true = nested pairs; false = the fase3-ie flat form.
        "auth_pairs_nested": True,
        ...
        # 2026-10-28 15:00 (tester report 2026-10-28 15:00: buying a set slot sent 0x210E "for 4294967295" four times
        # and nothing happened; store-fix.md 3, C): BoutiqueDataManager keeps a price only for the currency names "SC"
        # (Merits) and "HC" (Crisis Coins); "Merits" left every cost at -1. true = 0x2107 names SC / HC with
        # store_prices / store_prices_hc; false = the fase3-ie store_currency name, Merit prices only.
        "store_boutique_currency_keys": True,
        # Crisis Coin prices (0 = not sold for Crisis Coins). The set slot's dialog shows both prices. Values: O.
        "store_prices_hc": {"augment": 0, "mod": 0, "champion": 0, "skin": 0, "amp_slot": 50},
        # 0x210E with a price that is not the server's (or -1): "error" = 0x210D general error + a fresh 0x2107 (the UI
        # has no 0x210F listener); "changed" = the fase3-ie 0x210F; "accept" = charge the server's price.
        "store_price_mismatch": "error",
```

and `store_prices.amp_slot` 1000 -> 500 with the comment "2026-10-28 15:00 (tester report 2026-10-28 15:00, wallet 800
Merits / 50 Crisis Coins): a slot both currencies can buy; original prices unknown (store-fix.md 4)". Keep
`store_currency` (used only when `store_boutique_currency_keys` is false), `store_url`, `store_web_page`.

### 5.5 Tests

`tests/test_session_flow.py` (env `SESSION_TEST_PORT`; add `"start_crisis_coins": 200` to the `ic.update` at l.59),
replacing / extending the checks at l.137-206:
1. "AuthSelect: URL.Store as the client's gSOAP reads it": parse `server.auth_select()` inside `SOAP_ENVELOPE` with
   ElementTree; `return` -> child `nameValuePairs` -> its children named `nameValuePairs` -> `{name: value}` has
   `URL.Store` ending in `/store`; the outer element sits after `loginTicket` and before `randomID`; no `<name>`
   directly inside the outer element (replaces l.189-190).
2. "0x2107 names prices SC / HC only; the slot has both (= store_prices / store_prices_hc)": decode `u8 0 | u32 n |
   n x (u64, u32, str8, u32)`; every name in {"SC", "HC"}; DID `0x49000AA2` has an SC and an HC entry with the same id.
3. "0x210E SC at the 0x2107 price -> 0x210C, 0x20B8, 0x2081, 0x2095; Merits - price" (augment `0x40000689`, currency
   "SC"; l.155 today sends "Merits", still accepted).
4. "0x210E HC for the set slot -> 0x210C and 0x2090 total + 1; Crisis Coins - 50".
5. "0x210E with price 0xFFFFFFFF -> 0x210D 0x10000068 and a fresh 0x2107, no 0x210F" (replaces the 0x210F check at
   l.164-165).
6. "0x210E HC for an augment (no HC price) -> 0x210D".
7. "0x210E without the funds -> 0x210D 0x10000069".
8. Page: `POST /store/buy` with `did=0x49000aa2&cur=HC` -> Crisis Coins - 50, `0x210C` + `0x2090`; `GET /store`
   shows "Crisis Coins" prices.
9. `0x95` from the client -> no answer, nothing in unhandled.log (`Session` returns None).

`tests/test_ics.py` (env `ICS_TEST_PORT`), after "SOAP login answers with the user port" (l.123): "SOAP login:
URL.Store nested in nameValuePairs (NameValuePairArray)" on the HTTP answer, same parser.
Run: `python tests/test_session_flow.py`, `python tests/test_ics.py`, `python tests/test_match.py`,
`python tests/test_catalog.py`.

### 5.6 Records (rule 3)

Done in this step: `catalog/data/network_events.tsv` (0x2106, 0x210E, 0x2110, 0x2111 notes; new rows 0x2107, 0x210C,
0x210D, 0x210F, 0x0095), `catalog/data/records.tsv` 0x49000AA2 (no price), `docs/reverse-engineering.md` section
"Store page URL and contextual purchase prices", `docs/CHANGELOG.md` fase3-if bullet "Store (SHOP) and amplifier-screen
purchases, investigation". After the fix: statuses 0x2107 `sent`, 0x0095 `handled`, the CHANGELOG fix bullet with the
four config keys.

### 5.7 How the tester confirms

Superseded by 7.3 / 7.4 (the skeptic's corrections 1 and 2 in section 6: restart the client too; the diag expression
at `0xA97331` is `s[[[esp]]]`). First version:

Restart the server (the client may stay open: its store URL is still empty, 2.2), log in, click SHOP: `server.log`
shows `web ticket request (0x95)` then `store page: GET /store`, and the page replaces the version page. In the
amplifiers screen the slot row and dialog show 500 Merits / 50 Crisis Coins; a purchase logs `store purchase
0x49000aa2 for 50 HC -> hard 50 (0x210e)` then `purchase done ... (0x210c)` and the list gets one more set. No diag
mode is needed. Fallback if the page still does not load (`0x95` logged, no `GET /store`): a `tools/diag.py` mode
(e.g. `--store`, alias `--tiendaweb`; tracer expressions) with
`0x697331: ("STORE: InqStoreURL (0xa97331)", [("url", "s[[esp]]")])` (the pushed arg is &app+0x144, a narrow string),
`0x432F54: ("STORE: NavigateByInfo (0x832f54)", [("url", "s[[ecx]]")])` (ECX = nav info, +0 = the URL string) and
`0x432F59: ("STORE: IsValid (0x832f59)", [("al", "eax")])`: an empty url / AL 0 = the pair was not read; a good url
with AL 1 and still no request = the CEF side.

## 6. Skeptic review (independent re-check, 2026-10-28)

**Verdict: confirmed.** Both root causes hold and nothing simpler explains the symptoms. The plan is sound with the
corrections below.

Re-checked first-hand (decomp, capstone on both exes, AS2, server code):
- gSOAP chain: `0xADD710` instantiates type 10, vtable `0x160DEF4`, slot +0x18 = `0xADF940` -> `0xADE2D0`. The loop
  reads children named `nameValuePairs` (error 3 = TAG_MISMATCH -> `0xADB4B0` skips the element; 6 = NO_TAG ends the
  array). Items go `0xADD600` -> vtable `0x160DF14` +0x18 = `0xADF8C0` -> `0xADE0F0` (`name` = string `0x15A609C`,
  `value`). The member offsets in `0xADE4F0` match the reads in `0xA9B890` (+0x18, +0x24, +0x28, +0x2C, +0x30).
- `0xA9BA91 lea ecx,[ebp-8]; call 0x402C60(app+0x144)`: the pair is looked up only when that copy is null or empty
  (`0xA9BAB1`-`0xA9BAC0`). Slot `0x1606F84` = `0xA9B890` and `0x1606E7C` = `0xA97320`. The URL is sticky: confirmed.
- No other source. An immediate scan of the image for the map `0x1B6901C` finds `0xA9B340`, `0xA9B3B0`, `0xB14268`, an
  EH funclet (`0x13A1710`), the static initializer `0x13AA728` (empty map, atexit `0x1547190`) and the destructor, and
  no writer with a value. `URL.Store` (`0x16075D8`) is referenced only by `0xA9B890`.
- CEF: `0x832F52 mov ecx,esi` passes the nav info to IsValid, and `0x1098E80` calls `[0x1579AAC]` =
  `libcef!cef_parse_url`. `0x83172A push 0x15EB39C` = "chrome://version" -> `0x831774` -> `0x1099D20` ->
  `[0x1579ACC]` = `cef_browser_host_create_browser`.
- Model of the client's read on today's `Server.auth_select()`: flat `{}`, nested `{'URL.Store':
  'http://127.0.0.1:8888/store'}` (reproduced). `ics/server.py` has not changed since 14:01 and `config.toml` has no
  store key, so the 14:39 run sent the flat pair.
- Every cited function is byte-identical in `InfiniteCrisis_patched.exe`. The nearest patch (`0xA9B102`, the connection
  watchdog in `0xA9AF20`) is unrelated.
- AS2: `UI_RequestWebTicket` is sent only by `Store.as` and `Assembler.as`. `m_adAmplifierClickedForPurchase` is only
  ever set to null (Assembler l.880). `PurchasePriceChanged` appears only in event_gen and GM_Contextual.
- `0xA57510` copies the entries into four parallel arrays with no dedupe by id, so an SC and an HC entry with one
  boutique id are safe (`BoutiqueDataManager` keys by DID and by `"bid"+id`, the same object).
- Wire layouts: `0x210C` (ser `0x839DD0`) = u8 0 + 8 bytes; `0x210D` (ser `0x444B70`) = u8 0 + 8 + 4. The error enums
  268435560 / 268435561 = `0x10000068` / `0x10000069` (`emp_gen/gmErrorTypeList.as` l.167-174) =
  `ics/messages.py` l.1136. `0x2081` is (hard, soft), as in the AS2 arguments and the account file (hard 50, soft 825
  today).
- Logs: the run's `logs\` folder is empty and no copy exists (the scratchpad `logs-*` folders hold older runs). The
  `0x95`, `0x2107`, `0x210E` and `0x210F` excerpts rest on this note's first pass and on
  `test-2026-10-28-1439-sweep.md` section 12, written by another agent. The two agree. Screenshot 42 shows CEF's version
  page (license | credits) and 50 / 800 in the header.

Extra evidence:
- `0x8330D0` navigates only when this+0x28 is non-zero. That field is the CEF handler, stored by `0x831FD0` right
  before `0x831520` creates the browser, so it is set whenever the version page exists.
- When the browser does not exist yet, the request waits at +0x80 and is retried by `0x8076C0(7)` (on this+0x44) ->
  `0x8330F0` -> `0x833050` -> `0x832A80`. This is the original's path too: `0x420B90` always answered the store at once
  from the stored ticket, so our server does not change the timing against browser creation.

Corrections:
1. Diag fallback (5.7): at `0xA97331`, [esp] is &app+0x144, the string object that holds the char pointer. The
   expression must be `s[[[esp]]]`; `s[[esp]]` prints the pointer bytes. `s[[ecx]]` at `0x832F54` is right (nav info
   +0 = the char pointer); if it prints a single character, the URL there is UTF-16.
2. Tester procedure (5.7): restart the client too, not only the server.
   - `BoutiqueDataManager` is a Flash singleton that sends `0x2106` only from its constructor (l.18). A client that
     already opened the amplifier screen keeps the -1 prices; only the "error" policy's fresh `0x2107` repairs them,
     and only after one failed click.
   - `BoutiqueData.purchasePendingCurrency` (l.70-76) is still SOFT from the 14:55:48 click. It changes only from NONE
     and only `DualCurrencyPurchaseCompleteDialog` resets it (l.46).
   - A server restart forces a new login (AuthSelect) anyway.
3. The same pending-currency stickiness follows any `0x210D` (price error, funds, every slot owned). The next success
   dialog then shows the first-clicked currency's cost, though the server charged the right wallet. This is client-side
   and cosmetic: say so in the CHANGELOG bullet and do not try to fix it in the server.
4. Changing `_boutique()` from a 3-tuple to a 4-tuple also touches:
   - the DID fallback generator in `ev_store_purchase` (`ics/session.py` l.1675);
   - `store_web.buy` (`item[1]`, `item[2]`, l.83-85);
   - the `store_web.entries` unpack (l.56);
   - `pending_orders`;
   - `tests/test_session_flow.py` l.181.

   A missed unpack raises inside the `0x210E` handler: one INTERNAL ERROR line and no answer, which is the original
   symptom again. Less ripple: keep `_boutique()` as it is and add the Crisis Coin price from `store_prices_hc` in one
   helper.
5. With `store_boutique_currency_keys = false`, the fase3-ie charging (`store_currency`'s wallet, soft price) must come
   back too. Otherwise the switch does not restore fase3-ie.
6. Catalog after the fix:
   - `0x210F` becomes `off` by default (sent only with `store_price_mismatch = "changed"`).
   - `0x2095` is listed `off`, though `_complete_purchase` has sent it since fase3-ie.
   - The success batch (`0x210C`, the `0x2095` ribbon with key = DID and an empty name, `0x2090`) has never run in the
     real client. Ask for a screenshot of the ribbon, and gate `0x2095` if it shows garbage.

Not applicable: bots, map sides, respawns. This area is menu-only; the plan does not touch the in-match shop
(`ics/shop.py`, `World.spend`).

Residual risk (unchanged, O): the first renderer-side `LoadRequest` from CEF's `chrome://version` page, and a system
proxy for 127.0.0.1 in Chromium 31.

## 7. Implementation (fase3-if, 2026-10-29)

Done after the skeptic's review, with its corrections. Every behaviour change has an `[ics]` key in `ics/config.py`
(comments cite the tester report 2026-10-28 15:00); an earlier, interrupted pass had already written the config keys
and the nested pair in `auth_select`, which were kept.

### 7.1 What changed

- `ics/server.py` `Server.auth_select`: `URL.Store` goes nested,
  `<nameValuePairs><nameValuePairs><name>URL.Store</name><value>http://<host>:<soap_port>/store</value></nameValuePairs>
  </nameValuePairs>`, after `loginTicket` and before `randomID`. `auth_pairs_nested = false` = the fase3-ie flat pair.
  `launcher_data` is unchanged.
- `ics/session.py`:
  - `store_price(ct, wallet)`: Merits from `store_prices`, Crisis Coins from `store_prices_hc` (0 = not sold in that
    currency; Crisis Coins only with `store_boutique_currency_keys`). `_boutique()` keeps its 3-tuple `(DID,
    ContentType, Merit price)` (correction 4, "less ripple") and also lists an item sold for Crisis Coins only (Merit
    price 0).
  - `boutique_entries()` / `ev_request_boutique`: per augment, mod and set slot an `"SC"` entry when the Merit price
    is > 0 and an `"HC"` entry when the Crisis Coin price is > 0, under one boutique id (`BOUTIQUE_BASE | DID`). Keys
    false = the fase3-ie `store_currency` entries.
  - `ev_store_purchase`: the client's currency picks the wallet (`STORE_WALLETS`: SC / Merits / soft -> Merits; HC /
    Crisis Coins / coins / hard -> Crisis Coins) and the expected price is the server's price there. An unknown
    currency or no price in it -> `0x210D` GeneralError. A different price (0xFFFFFFFF included) follows
    `store_price_mismatch`: "error" (default) = `0x210D` GeneralError + a fresh `0x2107`; "changed" = the fase3-ie
    `0x210F` and a pending order for `0x2110`; "accept" = charge the server's price. Keys false = the whole fase3-ie
    purchase (store_currency's wallet, the Merit price, `0x210F`; correction 5). Log line: `store purchase <DID> for
    <price> <cur> -> <wallet> <expected> (0x210e)`.
  - `_complete_purchase(bid, item, wallet=None, price=None)` spends that wallet and price (None = fase3-ie). The order
    is unchanged (`0x210C`, `0x20B8`, `0x2081`, then `0x2090` for a slot); the `0x2095` ribbon only with
    `store_purchase_ribbon` (7.2).
  - `ev_store_confirm`: a pending order carries (item, wallet, price).
  - `ev_web_ticket` (`HANDLERS[0x95]`): one `server.log` line per SHOP open, no answer (`0xC2` is not sent).
- `ics/account.py` `Account.spend`: `"hc"` is Crisis Coins too.
- `ics/store_web.py`: each row carries both prices and has a "Buy (N Merits)" and a "Buy (M Crisis Coins)" form when
  that price is > 0 (hidden `did` and `cur` = SC / HC); `buy(session, did, cur)` pays in that currency (keys false:
  fase3-ie).
- `ics/messages.py`: docstrings of `amplifier_boutique` (SC / HC) and `item_fulfilled` (icon DID, 7.2).
- `tools/diag.py --storepage` (Spanish `--tiendaweb`): the fallback of 5.7 with the corrected expression (7.4).
- Tests: `tests/test_session_flow.py` 80 checks (the 0x2107 names, SC / Merits / HC purchases, the -1 price, HC for an
  augment, the "changed" policy with 0x2110, the keys = false 0x2107, insufficient funds, the nested and flat
  AuthSelect read as the client does, the page's two currencies, 0x95); `tests/test_ics.py` 34 (the SOAP answer read
  the same way).

### 7.2 The 0x2095 ribbon [C, code]

`0x2095`'s exec `0x8AAF60` passes &msg+0x20 (first u32), &msg+0x24 (second u32) and &msg+0x28 (StringInfo) to
`0xA7EA00`. When `[0xA12D50()+0x54]` exists, it copies (first, second, StringInfo) into a map keyed by the first u32
(`0xA746B0` on +0x19C), sets +0x1B0 and calls `0xA26B50`, which hands every map node to `0x88F040(node[3] = the second
u32, &name)`. `0x88F040` turns its first argument into a double and raises `RecvNotice_Ribbon_ItemFulfilled(i_didIcon,
i_siName)`; `WrapperMain` builds an `UpgradeUnlockRibbonData { didIcon, siName }`. So the second u32 is an **icon**
DID (0x13...) and the StringInfo the shown name. fase3-ie sent key = icon = the bought item's DID (0x49... / 0x40...,
not an image) and no name: an empty ribbon right after the client's own purchase dialog. `[ics] store_purchase_ribbon`
(false) leaves it out; true = the fase3-ie ribbon. P: the original used it for orders fulfilled from the web store,
closed by `Ribbon_FinishedItemsFulfilled`.

### 7.3 What the tester should see (restart the server and the client)

- Restart both (correction 2): `BoutiqueDataManager` asks `0x2106` once per client process and the slot's pending
  currency is still SOFT from the failed clicks; the store URL itself would be read at the next login anyway (still
  empty in the old process).
- SHOP: `server.log` shows `web ticket request (0x95): store screen opened ...` and then `store page: GET /store`; the
  browser shows the store page (wallet; set slots, champions, skins, augments, mods; a button per currency).
- Amplifiers screen: the "buy a set slot" row and its dialog show 500 (Merits) and 50 (Crisis Coins); with 800 Merits
  and 50 Crisis Coins both buttons are visible. A click logs in `server.log` `store purchase 0x49000aa2 for 50 HC ->
  hard 50 (0x210e)` and `store purchase done: 0x49000aa2 for 50 hard; Merits .., Crisis Coins .. (0x210c)` (a refusal:
  `store purchase .. refused: ..`), and in `traffic.log` the answers `0x210C`, `0x20B8`, `0x2081`, `amplifier sets
  (0x2090): 7 slots`; the purchase-complete dialog shows the cost, the header the new balance, the list one more empty
  set.
- A refused purchase shows the client's error dialog (`0x210D`): insufficient funds, or the general error for a stale
  price (the prices are then sent again).
- Cosmetic, client-side (correction 3): after a `0x210D` on the slot the dialog's pending currency stays the first
  clicked one until a success dialog, which can then show the other currency's cost; the server charged the right
  wallet.

### 7.4 Fallback diag

If SHOP still shows the version page while `server.log` has the `0x95` line and no `GET /store`: with the game in the
menu, run `python tools\diag.py --tiendaweb` (= `--storepage`) in a second console, click SHOP, Ctrl+C, send
`logs\diag.log`. Breakpoints: `0xA97331` InqStoreURL, `url = s[[[esp]]]` (the string is narrow: `0x402C60` /
`0x402D60` copy `size` bytes of 1-byte characters); `0x832F54` NavigateByInfo's check, `url = s[[ecx]]`; `0x832F59`
IsValid, `eax` (AL 0 = dropped). An empty url = the pair was not read (old client process or the flat form); a good url
with AL 1 and still no request = the CEF side (residual risk above).

### 7.5 Still open

- The original prices (O): 500 Merits / 50 Crisis Coins for a slot and 300 Merits for an augment / mod are guesses.
- `0xC2` (the web ticket) is not sent; its destination object is O.
- The success batch has not run in the real client: a screenshot of a slot purchase is wanted (correction 6).
