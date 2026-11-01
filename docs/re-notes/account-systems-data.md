# Account-level and meta systems in the game data (survey, 2026-10-21)

Read-only survey of the player's install (`C:\Infinite Crisis Server\rp`, 616 packs) and of `InfiniteCrisis.exe`
(image base 0x400000, addresses are VAs), for the preservation server. Only IDs, short names and numbers are written
here (no descriptions, dialogue or other game texts). Tags: **[C]** confirmed in the data or the client code, **[P]**
probable (consistent evidence, one link missing), **[G]** guess.

Companion notes: `progression-meta.md` (in-match progression, the event table of section 3), `shop-items-inventory.md`
(artifacts), `champions-all.md` (roster, loadout list per champion), `reward_re.txt` (reward ribbon chain),
`protocol-server-to-client.md` / `protocol-client-to-server.md`, `icserver/scorecard.py` (end-of-match builders).

**Method.** Every `0x40`-`0x4F` record of every pack was parsed with the catalog's property kinds (`ics.records`;
headers `did | 0 | n`, `did | 1 | n` (achievements), `did | 4 | n` (champion definitions), `did | 7 | entity | 0 | n`):
4506 records. Records were grouped by their property-key signature, every group that is not gameplay (skills, world
states, AI, stat blocks) is listed below. Enum names come from the UI's AS2 dump (`old_files/tools/gfx/classes_all.txt`,
`*List.__get__*` getters). Field meanings marked [C] were matched to the client reader (VA given) or to the Flash
function the C++ passes them to. Scratch scripts (not in the project): scratchpad `acct/scan.py`, `gen.py`, `gen2.py`.

**Important general finding [C]:** records with **no properties** (`did | 0 | 0`) exist in the packs (e.g. most of
`0x48000C71`'s list); and the **reward groups keep only their first 1-3 item slots**: every group has exactly 30
`0x10000A17` slots, but in the client data only the displayed items carry an item (`0x10000A1A` / `0x10000AB7`), the
other 27-29 slots carry only the quantity `0x10000A36 = 1`. The server-side contents of the rest were stripped from the
client packs. Same for prices: **no record holds a store price** (champion twins, skins, Stolen Powers, icons and
amplifiers have no cost property; checked on the 190 properties of the champion definitions). Prices were server /
Steam boutique data (`0x2107`, `0x210F`).

## 0. Record types (all of them) and counts

| System | Record type (key that identifies it) | DIDs (`0x49` twins of the listed `0x40`) | Count | Pack | Lists / masters | Tag |
|---|---|---|---|---|---|---|
| Augment | `0x100009EF = true` | `0x49000649`-`0x490006EA` | 162 | `0xA00000B3` | `0x48000A49` (`0x1000099F` of `0x100009A0`, 162) | C |
| Mod | `0x100009F0 = true` | `0x49000820`-`0x49000E6E` | 172 | `0xA00000B3` | `0x48000A4A` (172) | C |
| Amplifier set icons | list of `0x13...` images (`0x100009E9`) | `0x48000AAF` | 28 icons | `0xA00000B3` | - | C (record) / P (meaning: icons the set picker offers) |
| Amplifier brand icons | `0x10000999` {`0x10000996` icon, `0x10000997` brand} / `0x100009CF` {`0x100009C9`, brand} + `0x100009CB` stat icons | `0x48000A34`, `0x48000AAD` | 7 + 7 brands, 21 stat icons | `0xA00000B3` | - | C (data) / P (use: augment / mod overlay icons `didModBrandOverlayIcon`) |
| Amplifier set slot (ownable) | `0x1000095F` name + `0x1000095E` icon + `0x10000AFA = 1` | `0x49000AA2` | 1 | `0xA00000B3` | - | P (ContentType 5 Amplifier, "buy another set slot") |
| Default loadout (amplifier set + build) | `0x1000034B` skill order + `0x10000A12` / `0x1000098F` | `0x48001340`-`0x48001525` | 166 (163 used) | the champions' skills packs | champion twin `0x10000CE9` / `0x10000CEB` | C |
| Champion definition (ownable Character / Skins) | `did | 4 | n`, template `0x48000732` | 156 `0x49` twins | 156 | own packs | none in data (server sends `0x20ED`) | C |
| Stolen Power | skill block `0x1000003F` (+ `0x10000922` unlock rule) | 12 base + 53 versions | 65 | `0xA00000B3` | `0x480003CD` (12 groups) | C |
| Avatar / protector icon | `0x10000AB9 = 1` (+ `0x100008F8` image, `0x10000B77..79` strings) | `0x490005D4`-`0x49000F17` | 134 | `0xA00000D0` | none | C |
| Achievement | `did | 1 | n`; `0x10000A2D` objectives | `0x490008D9`-`0x49000F12` | 192 | `0xA00002FF` (187), `0xA00000B3` (5) | `0x48000CF0` (`0x1000099F` of `0x100009A0`, 193 entries, 192 distinct) = master list `0x100000B7` | C |
| Reward set | `0x10000A1F` list of groups | `0x490008DD`-`0x49000F1C` | 179 | `0xA00002FF` (174), `0xA00000B3` (5) | achievement `0x10000A5C`, login calendar | C |
| Reward group | `0x10000A1D` 30 slots + `0x10000A4D` bestowal | `0x490008DC`-`0x49000F21` | 97 | `0xA00002FF` (92), `0xA00000B3` (5) | reward set `0x10000A1B` | C |
| Currency / XP reward items | `0x10000AB4` (Merit), `0x10000AB3` (Crisis Coins), `0x10000B38` 1/2 (account XP flat / percent) | Merit `0x48000722`, `0x48000CD7`, `0x48000D62`, `0x4800152C`; Coins `0x48000723`, `0x48000D61`, `0x48000E3D`, `0x4800152D`; XP `0x48000F31` (flat), `0x48000F30` (percent) | 4 + 4 + 2 | `0xA00000B3` | `0x48000C71` (33 entries `0x10000A0F`, 27 of them empty records) | C |
| Login reward calendar | `0x10000D94` {`0x10000D93` reward set, `0x10000D92` day} | `0x48001528` | 1 (110 entries) | `0xA00000B3` | UI config `0x48000E76` (movie `0x10000DA0`, image `0x10000D9F`) | C (data) / P (days) |
| Accolade | `0x10000C68` + `0x10000C69` + `0x10000C6A` + texts `0x10000CD7`-`0x10000D5B` | `0x49000CE4`-`0x49000EA6` | 55 | `0xA00000B3` | `0x48001242` (`0x10000C6C`, 46), `0x48001490` (`0x10000D6D`: encounter -> first-match accolade, 9) | C |
| Accolade medal names | `0x10000B25` {`0x10000B22` letter, `0x10000B6F` name, `0x10000B23` rank} | `0x48000EF9` | 3 (G 1 / S 2 / B 3) | `0xA00000B3` | `AccoladeRankType` | C |
| Account level unlocks | `0x10000589` {`0x1000058A` level, `0x1000058C` enum}, `0x100006C0` | `0x48000372` | 1 (20 entries) | `0xA00000B3` | - | C (data) / G (enum) |
| Protector (account) levels | the 104 `ProtectorLevel` achievements (targets 2-100) | see 3.1 | 104 | `0xA00002FF` | - | C |
| Ranked tiers + standings teams | `0x10000DD5` tiers, `0x10000DBB` teams | `0x4800155F` | 4 tiers, 21 teams | `0xA00000B3` | `RankedDisplayTier`, `0x219F` handler | C (data) / P (use) |
| Match / account statistics | `0x10000C40` {`0x10000C3D` id, `0x10000C3E` key name, `0x10000C47` encounters, `0x10000C9A`} | `0x48001172` | 1 (59 stats) | `0xA00000B3` | - | C |
| Account stats pages | `0x10000A82` stat ids + `0x10000A8C` title | `0x48000D44`-`0x48000D47`, `0x48001598` | 5 | `0xA00000B3` | `0x2115` | P |
| Scoreboard grid (end of match) | `0x10000B28` {`0x10000AB1` stat ids, `0x10000B33` section} | `0x48000F06`, `0x48000F92`, `0x48000F93`, `0x48000F95`, `0x48000FB0`, `0x480012A4` | 6 | `0xA00000B3` | `0x2045` grid | P |
| Scoreboard columns (end of match) | `0x10000AB1` (5 stat ids) | `0x48000E29`, `0x48000E2B`, `0x48000E2C`, `0x48000F94`, `0x480012A3` | 5 | `0xA00000B3` | `0x2045` column1-5 | P |
| Secret achievement conditions | `0x10000D1A` {`0x10000D18` condition record, `0x10000D85` achievement, `0x10000D1B` champion indexes / DIDs, `0x10000D29` / `0x10000D1F` counts} | `0x4800144D` | 1 | `0xA00000B3` | the 6 Secret General achievements | C (data) / P (meaning: team composition) |
| Pregame tips | `0x100007AF` | `0x4900040B`-`0x49000EE4` | 42 | `0xA00000B3` | `0x201E` RequestAllPregameTips | C (data) |
| Tutorial / trainee UI config | `0x10000BAC` trainee achievements, `0x10000B62` packs | `0x48000E76` | 1 | `0xA00000D0` | - | C |

No record type exists in the data for: **boosts** (ContentType 6), **bundles** (8), **entitlements** (14), **store
catalogue / prices**, **daily quests** as a separate system, **XP curve** (account or champion), **Merit per match**.
Those were server data [C for the absence in all 616 packs; the scan covered every `0x4x` record].

---

## 1. Amplifiers (augments and mods)

### 1.1 Records [C]

| Record | Key | Kind | Meaning | Tag |
|---|---|---|---|---|
| Augment (`0x49` twin of the listed `0x40`) | `0x100009EF` | bool | is an augment (client item type 8, `0x86E830`; PostMatchRewardType 8 Augment) | C |
| | `0x10000951` | string | name (table `0x2B0000B4`; "{Brand} Augment / Codename: X") | C |
| | `0x10000953` | string | description (empty) | C |
| | `0x10000956` | enum | brand: 3 Kord, 4 S.T.A.R. Labs, 5 LexCorp, 6 Queen, 7 Holt, 8 Wayne | C (values) / P (names from the strings) |
| | `0x10000950` | array of `0x10000955` | **exactly 2 stats** each: `0x10000952` op (9 add, 10 add %), `0x10000958` stat key, `0x10000954` f32 value, `0x10000B23` 1..3 (per-stat grade; 115 x 1, 100 x 2, 109 x 3) | C (G for `0x10000B23`) |
| Mod | `0x100009F0` | bool | is a mod (client item type 9) | C |
| | `0x1000097D` / `0x1000097C` | string | name ("{Brand} Mod / {Discounted, Enhanced, Empowered...} {artifact}") / effect text (table `0x2B0000B7`) | C |
| | `0x1000097B` | enum | brand (same values) | C |
| | `0x10000989` | array of `0x10000987` | 1-4 target artifacts (71 mods x1, 62 x2, 21 x3, 18 x4); each: `0x1000098B` artifact (`0x40` DID) + one effect: `0x1000098C` credit discount (122 entries) / `0x10000986` op + `0x10000985` stat + `0x10000984` value (118) / `0x10000988` keyword record (`0x48`) [+ `0x1000098A` replaced keyword, `0x10000A08`] (77) / `0x1000098D`, `0x1000098E` (13, unknown) | C (G for `98D/98E/A08`) |

Brand counts: augments Holt 29, LexCorp 29, Kord 27, Wayne 27, S.T.A.R. 26, Queen 24; mods Queen 46, LexCorp 31,
S.T.A.R. 31, Holt 26, Wayne 24, Kord 14. Augment stat keys used (count of stat lines): CDR `0x10000B7B` 40, Attack Armor
`0x10000B84` 30, Power Armor `0x10000B7A` 30, Health `0x10000426` 30, Power Damage `0x10000B75` 30, Attack Damage
`0x10000B76` 29, Move Speed `0x100005E4` 25, Attack Speed `0x100006FE` (op 10) 24, Power Pen `0x10000B7E` 24, Attack Pen
`0x10000B83` 23, Attack Lifesteal `0x10000B7C` 16, Power Lifesteal `0x10000B7F` 16, Crit Damage `0x10000B80` 7.

Who uses them in the client [C]: the mods change artifact prices in the shop (`0x873450` discount, see
`shop-items-inventory.md`); the client asks `UI_InqAugmentData` / `UI_InqModData` / `UI_InqAugmentsPassingFilter` /
`UI_InqModsPassingFilter` locally (no network). Applying the stats in the match is the server's job [C: no client code
applies `0x10000950` to the champion].

### 1.2 Amplifier set rules

| Rule | Value | Source | Tag |
|---|---|---|---|
| Entries per set | **7** (`AmplifierSetData.AMPLIFIERS_PER_SET = 7`); the C++ handler `0xa64520` reads `list[0..6]` directly for every set (no bounds check): **always send 7 entries** (`0` = empty, but the client treats `[0x1B74A0C]` = invalid DID as empty) | AS2 l.459059, `0xa64520` | C |
| Slot order | entries 1-4 augments, 5-7 mods: all 166 default sets are 4 augments (`0x10000A12`) + 3 mods (`0x1000098F`) | data | P (no client check of the slot type found) |
| Client-side validation before `0x20FC` (`0x875420`) | (1) no DID twice in a set; (2) for each mod (`0x100009F0`), the root artifact of its target (`0x865E80` -> `0x9D1910`) must differ from every other mod's (one mod per artifact family). Failure -> local error notice (`0x16013C4`), nothing sent | `0x875420` | C (rule 2: P for "root of the build tree") |
| Name length | custom name <= 21 characters (`cmp [ecx-4], 0x15`); longer -> error `0x16013CC` (= `Amplifier_SetNameTooLarge 0x10000065` [P]) | `0xa2fd40` | C |
| Ownership | the picker lists only owned augments/mods: `OwnablesManager` content types 12 Augments / 13 Mods from `0x20B8` | AS2 | P |
| Set count | `NotifyListAmplifierSets(uiTotalAmplifierSets, uiMaxAmplifierSets, ...)`; when total < max the UI offers to buy a set slot = ownable of ContentType 5 Amplifier (`0x49000AA2` "Amplifier Set Slot", boutique data via `BoutiqueDataManager.GetBoutiqueDataByDID`, `UI_InqAmplifierSetSlotInfo`) | AS2 l.385640-385720 | C (UI) / P (slot item) |
| Default sets | the client builds the champion's default sets itself (`UI_InqCharacterDefaultAmplifierSet`, AS2 `m_aDefaultAmplifierSetsArray`; `AmplifierSetData.didCharacterDefaultSet` = the loadout record): the server does not need to send them | AS2 | P |
| Set icons | 28 images in `0x48000AAF` (`UI_InqAmplifierSetIcons`); the default sets use `0x130037AA` (Gotham Heights), `0x130037AB` (Gotham Divided), `0x130037AC` (Coast City) | data | C (data) / P (picker) |

### 1.3 Default loadouts per champion and map [C]

Loadout record (`0x48`, in the champion's skills pack): `0x1000095F` name ("<map>: Default Amplifier Set"),
`0x1000095E` set icon, `0x10000A12` 4 augments (`0x1000095A`), `0x1000098F` 3 mods (`0x1000095A`), `0x1000064E`
Stolen Power pair (`0x1000064F`), `0x10000478` recommended artifacts (21 x {`0x10000475` = 3, `0x10000694` artifact}),
`0x1000084C`-`0x1000084F`, `0x10000893` artifact groups, `0x1000034B` skill order (19), `0x10000AA1` = 4 in all 166.

The champion twin's `0x10000CE9` = array of `0x10000CEC` {`0x10000CEB` loadout, `0x10000CE4` map id}; `0x10000CEB`
at the top level = the default one. **Map id = `EncounterIdentifierType` [P]**: 1 Gas_Lane, 3 Got_Dominion (Gotham
Heights), 4 Got_Rift (Gotham Divided), 5 Cst_Onslaught (Coast City), 6 Mch_Aram, 7/8/9 Tutorial Basic / Intermediate /
Advanced (only Gaslight Batman's `0x4800137F` has 1, 7, 8, 9). The names agree: id 3 and 6 records are named "Gotham
Heights", 4 "Gotham Divided", 5 "Coast City". Three records are not referenced by any champion: `0x48001522`,
`0x48001523`, `0x48001525` (Coast City sets in packs `0xA0000114`, `0xA0000124`, `0xA000011D`).

All 163 used loadout records (augments and mods as `0x40` DIDs):

| Champion | Loadout record | Maps (`0x10000CE4`) | `0x10000AA1` | Augments (`0x10000A12`) | Mods (`0x1000098F`) | Stolen pair (`0x1000064E`) | Icon `0x1000095E` |
|---|---|---|---|---|---|---|---|
| Aquaman | `0x480013BD` | 3,6 | 4 | `40000696` `40000652` `400006BE` `400006B0` | `400008B0` `4000086A` `4000085A` | `48000529` `48000913` | `130037AA` |
| Aquaman | `0x480013BE` | 5 | 4 | `40000696` `40000652` `400006BE` `400006B0` | `400008B0` `4000086A` `4000085A` | `48000523` `48000913` | `130037AC` |
| Aquaman | `0x480013BC` (default) | 4 | 4 | `40000696` `40000652` `400006BE` `400006B0` | `400008B0` `4000086A` `4000085A` | `48000523` `48000913` | `130037AB` |
| Arcane Green Lantern | `0x4800136B` | 3,6 | 4 | `40000696` `4000065E` `400006CD` `40000689` | `4000085F` `4000084A` `400008B7` | `480003CB` `48000869` | `130037AA` |
| Arcane Green Lantern | `0x4800136C` | 5 | 4 | `40000696` `4000065E` `400006CD` `40000689` | `4000085F` `4000084A` `400008B7` | `48000523` `48000869` | `130037AC` |
| Arcane Green Lantern | `0x4800136A` (default) | 4 | 4 | `40000696` `4000065E` `400006CD` `40000689` | `4000085F` `4000084A` `400008B7` | `48000523` `48000869` | `130037AB` |
| Arcane Harley Quinn | `0x48001393` | 3 | 4 | `40000652` `400006DB` `400006E8` `400006D6` | `40000883` `40000842` `4000086A` | `480003CB` `4800131B` | `130037AA` |
| Arcane Harley Quinn | `0x48001394` | 5 | 4 | `40000652` `400006DB` `400006E8` `400006D6` | `40000883` `40000842` `4000086A` | `480003CB` `4800131B` | `130037AC` |
| Arcane Harley Quinn | `0x48001392` (default) | 4 | 4 | `40000652` `400006DB` `400006E8` `400006D6` | `40000883` `40000842` `4000086A` | `480003CB` `4800131B` | `130037AB` |
| Arcane Supergirl | `0x480013C9` | 3,6 | 4 | `400006BB` `400006BA` `4000068E` `40000649` | `40000830` `40000881` `40000829` | `48000529` `48000F05` | `130037AA` |
| Arcane Supergirl | `0x480013CA` | 5 | 4 | `400006BB` `400006BA` `4000068E` `40000649` | `40000830` `40000881` `40000829` | `48000523` `48000F05` | `130037AC` |
| Arcane Supergirl | `0x480013C8` (default) | 4 | 4 | `400006BB` `400006BA` `4000068E` `40000649` | `40000830` `40000881` `40000829` | `48000523` `48000F05` | `130037AB` |
| Arcane Zatanna | `0x480013A8` | 3,6 | 4 | `40000666` `400006C8` `400006CD` `400006BB` | `40000881` `40000829` `40000A8A` | `48000529` `48001060` | `130037AA` |
| Arcane Zatanna | `0x480013A9` | 5 | 4 | `40000666` `400006C8` `400006CD` `400006BB` | `40000881` `40000829` `40000A8A` | `48000523` `48001060` | `130037AC` |
| Arcane Zatanna | `0x480013A7` (default) | 4 | 4 | `40000666` `400006C8` `400006CD` `400006BB` | `40000881` `40000829` `40000A8A` | `48000523` `48001060` | `130037AB` |
| Atomic Green Lantern | `0x48001365` | 3,6 | 4 | `40000696` `4000065E` `400006CD` `4000067D` | `4000082B` `400008B7` `40000881` | `480003CB` `480005A2` | `130037AA` |
| Atomic Green Lantern | `0x48001366` | 5 | 4 | `40000696` `4000065E` `400006CD` `4000067D` | `4000082B` `400008B7` `40000881` | `480003CB` `48000815` | `130037AC` |
| Atomic Green Lantern | `0x48001364` (default) | 4 | 4 | `40000696` `4000065E` `400006CD` `4000067D` | `4000082B` `400008B7` `40000881` | `480003CB` `48000815` | `130037AB` |
| Atomic Joker | `0x480013C3` | 3,6 | 4 | `4000066F` `40000652` `4000068C` `4000064B` | `40000824` `400008B0` `40000AC7` | `48000780` `48000529` | `130037AA` |
| Atomic Joker | `0x480013C4` | 5 | 4 | `4000066F` `40000652` `4000068C` `4000064B` | `40000824` `400008B0` `40000AC7` | `48000780` `48000529` | `130037AC` |
| Atomic Joker | `0x480013C2` (default) | 4 | 4 | `4000066F` `40000652` `4000068C` `4000064B` | `40000824` `400008B0` `40000AC7` | `48000780` `48000529` | `130037AB` |
| Atomic Poison Ivy | `0x48001381` | 3,6 | 4 | `40000696` `4000067D` `4000065E` `400006B6` | `4000085F` `4000084A` `400008B7` | `480003CB` `480007A8` | `130037AA` |
| Atomic Poison Ivy | `0x48001382` | 5 | 4 | `40000696` `4000067D` `4000065E` `400006B6` | `4000085F` `4000084A` `400008B7` | `480003CB` `48000523` | `130037AC` |
| Atomic Poison Ivy | `0x48001380` (default) | 4 | 4 | `40000696` `4000067D` `4000065E` `400006B6` | `4000085F` `4000084A` `400008B7` | `480003CB` `48000523` | `130037AB` |
| Atomic Wonder Woman | `0x48001387` | 3,6 | 4 | `40000652` `400006DB` `400006E8` `400006D6` | `4000086A` `400008B0` `40000870` | `48000780` `48000868` | `130037AA` |
| Atomic Wonder Woman | `0x48001388` | 5 | 4 | `40000652` `400006DB` `400006E8` `400006D6` | `4000086A` `400008B0` `40000870` | `48000780` `48000868` | `130037AC` |
| Atomic Wonder Woman | `0x48001386` (default) | 4 | 4 | `40000652` `400006DB` `400006E8` `400006D6` | `4000086A` `400008B0` `40000870` | `48000780` `48000868` | `130037AB` |
| Atrocitus | `0x480013AE` | 3,6 | 4 | `40000696` `4000065E` `400006B6` `40000649` | `4000082B` `400008B7` `40000AD6` | `480003CB` `48000D28` | `130037AA` |
| Atrocitus | `0x480013AF` | 5 | 4 | `40000696` `4000065E` `400006B6` `40000649` | `4000082B` `400008B7` `40000AD6` | `480003CB` `48000D28` | `130037AC` |
| Atrocitus | `0x480013AD` (default) | 4 | 4 | `40000696` `4000065E` `400006B6` `40000649` | `4000082B` `400008B7` `40000AD6` | `480003CB` `48000D28` | `130037AB` |
| Batman | `0x48001341` | 3,6 | 4 | `40000652` `40000683` `400006BE` `40000696` | `40000824` `4000087D` `400008B0` | `480003CB` `48000780` | `130037AA` |
| Batman | `0x48001342` | 5 | 4 | `40000652` `40000683` `400006BE` `40000696` | `40000824` `4000087D` `400008B0` | `48000523` `48000780` | `130037AC` |
| Batman | `0x48001340` (default) | 4 | 4 | `40000652` `40000683` `400006BE` `40000696` | `40000824` `4000087D` `400008B0` | `48000523` `48000780` | `130037AB` |
| Blue Beetle | `0x480013B4` | 3,6 | 4 | `40000652` `4000068C` `4000066B` `40000683` | `40000824` `400008B0` `40000AC7` | `48000780` `48000529` | `130037AA` |
| Blue Beetle | `0x480013B5` | 5 | 4 | `40000652` `4000068C` `4000066B` `40000683` | `40000824` `400008B0` `40000AC7` | `48000780` `48000529` | `130037AC` |
| Blue Beetle | `0x480013B3` (default) | 4 | 4 | `40000652` `4000068C` `4000066B` `40000683` | `40000824` `400008B0` `40000AC7` | `48000780` `48000529` | `130037AB` |
| Catwoman | `0x4800135C` | 3,6 | 4 | `400006CD` `4000067D` `400006CC` `40000699` | `40000A8A` `40000881` `40000829` | `48000523` `4800080A` | `130037AA` |
| Catwoman | `0x4800135D` | 5 | 4 | `400006CD` `4000067D` `400006CC` `40000699` | `40000A8A` `40000881` `40000829` | `48000523` `4800080A` | `130037AC` |
| Catwoman | `0x4800135B` (default) | 4 | 4 | `400006CD` `4000067D` `400006CC` `40000699` | `40000A8A` `40000881` `40000829` | `48000523` `4800080A` | `130037AB` |
| Cyborg | `0x480013A5` | 3,6 | 4 | `40000652` `400006A1` `400006B0` `40000693` | `40000824` `400008B0` `40000AC7` | `48000780` `48000529` | `130037AA` |
| Cyborg | `0x480013A6` | 5 | 4 | `40000652` `400006A1` `400006B0` `40000693` | `40000824` `400008B0` `40000AC7` | `48000780` `48000529` | `130037AC` |
| Cyborg | `0x480013A4` (default) | 4 | 4 | `40000652` `400006A1` `400006B0` `40000693` | `40000824` `400008B0` `40000AC7` | `48000780` `48000529` | `130037AB` |
| Deadshot | `0x480013C0` | 3,6 | 4 | `400006EA` `400006BE` `40000652` `400006D6` | `40000824` `400008B0` `40000AC7` | `48000780` `48000529` | `130037AA` |
| Deadshot | `0x480013C1` | 5 | 4 | `400006EA` `400006BE` `40000652` `400006D6` | `40000824` `400008B0` `40000AC7` | `48000780` `48000529` | `130037AC` |
| Deadshot | `0x480013BF` (default) | 4 | 4 | `400006EA` `400006BE` `40000652` `400006D6` | `40000824` `400008B0` `40000AC7` | `48000780` `48000529` | `130037AB` |
| Deathstroke | `0x480013A2` | 3,6 | 4 | `400006E9` `4000069D` `400006D2` `400006DA` | `400008B0` `4000086A` `40000864` | `480003CB` `48000523` | `130037AA` |
| Deathstroke | `0x480013A3` | 5 | 4 | `400006E9` `4000069D` `400006D2` `400006DA` | `400008B0` `4000086A` `40000864` | `480003CB` `48000523` | `130037AC` |
| Deathstroke | `0x480013A1` (default) | 4 | 4 | `400006E9` `4000069D` `400006D2` `400006DA` | `400008B0` `4000086A` `40000864` | `480003CB` `48000523` | `130037AB` |
| Dex-Starr | `0x480013CC` | 3,6 | 4 | `400006E9` `4000069D` `400006D2` `400006DA` | `400008B0` `4000086E` `40000846` | `480007AC` `48001253` | `130037AA` |
| Dex-Starr | `0x480013CD` | 5 | 4 | `400006E9` `4000069D` `400006D2` `400006DA` | `400008B0` `4000086E` `40000846` | `480007AC` `48001253` | `130037AC` |
| Dex-Starr | `0x480013CB` (default) | 4 | 4 | `400006E9` `4000069D` `400006D2` `400006DA` | `400008B0` `4000086E` `40000846` | `480007AC` `48001253` | `130037AB` |
| Doomsday | `0x48001353` | 3,6 | 4 | `40000652` `40000683` `40000696` `4000065E` | `400008B0` `40000864` `4000085A` | `480003CB` `48000813` | `130037AA` |
| Doomsday | `0x48001354` | 5 | 4 | `40000652` `40000683` `40000696` `4000065E` | `400008B0` `40000864` `4000085A` | `480003CB` `48000813` | `130037AC` |
| Doomsday | `0x48001352` (default) | 4 | 4 | `40000652` `40000683` `40000696` `4000065E` | `400008B0` `40000864` `4000085A` | `480003CB` `48000813` | `130037AB` |
| Flash | `0x48001399` | 3,6 | 4 | `40000652` `400006DB` `400006E8` `400006D6` | `40000864` `400008B0` `4000087F` | `48000785` `48000807` | `130037AA` |
| Flash | `0x4800139A` | 5 | 4 | `40000652` `400006DB` `400006E8` `400006D6` | `40000864` `400008B0` `4000087F` | `48000785` `48000807` | `130037AC` |
| Flash | `0x48001398` (default) | 4 | 4 | `40000652` `400006DB` `400006E8` `400006D6` | `40000864` `400008B0` `4000087F` | `48000785` `48000807` | `130037AB` |
| Gaslight Batman | `0x4800137D` | 3,6 | 4 | `40000652` `400006B0` `400006BE` `40000693` | `40000824` `400008B0` `40000AC7` | `48000780` `48000529` | `130037AA` |
| Gaslight Batman | `0x4800137E` | 5 | 4 | `40000652` `400006B0` `400006BE` `40000693` | `40000824` `400008B0` `40000AC7` | `48000780` `48000529` | `130037AC` |
| Gaslight Batman | `0x4800137C` (default) | 4 | 4 | `40000652` `400006B0` `400006BE` `40000693` | `40000824` `400008B0` `40000AC7` | `48000780` `48000529` | `130037AB` |
| Gaslight Batman | `0x4800137F` | 1,7,8,9 | 4 | `40000652` `400006B0` `400006BE` `40000693` | `40000870` `400008B0` `40000878` | `48000529` `48000808` | `13002378` |
| Gaslight Catwoman | `0x48001347` | 3,6 | 4 | `40000652` `400006DB` `400006E8` `400006D6` | `4000087D` `400008B0` `4000086A` | `48000529` `48000785` | `130037AA` |
| Gaslight Catwoman | `0x48001348` | 5 | 4 | `40000652` `400006DB` `400006E8` `400006D6` | `4000087D` `400008B0` `4000086A` | `48000529` `48000785` | `130037AC` |
| Gaslight Catwoman | `0x48001346` (default) | 4 | 4 | `40000652` `400006DB` `400006E8` `400006D6` | `4000087D` `400008B0` `4000086A` | `48000529` `48000785` | `130037AB` |
| Gaslight Joker | `0x4800134A` | 3,6 | 4 | `40000696` `4000065E` `400006B6` `40000649` | `40000AD5` `40000884` `400008B7` | `48000529` `48000863` | `130037AA` |
| Gaslight Joker | `0x4800134B` | 5 | 4 | `40000696` `4000065E` `400006B6` `40000649` | `40000AD5` `40000884` `400008B7` | `48000529` `48000523` | `130037AC` |
| Gaslight Joker | `0x48001349` (default) | 4 | 4 | `40000696` `4000065E` `400006B6` `40000649` | `40000AD5` `40000884` `400008B7` | `48000529` `48000523` | `130037AB` |
| Green Arrow | `0x4800135F` | 3,6 | 4 | `4000066F` `40000652` `4000068C` `4000064B` | `40000824` `400008B0` `40000AC7` | `48000780` `48000529` | `130037AA` |
| Green Arrow | `0x48001360` | 5 | 4 | `4000066F` `40000652` `4000068C` `4000064B` | `40000824` `400008B0` `40000AC7` | `48000780` `48000529` | `130037AC` |
| Green Arrow | `0x4800135E` (default) | 4 | 4 | `4000066F` `40000652` `4000068C` `4000064B` | `40000824` `400008B0` `40000AC7` | `48000780` `48000529` | `130037AB` |
| Green Lantern | `0x48001344` | 3,6 | 4 | `40000677` `400006C3` `400006CD` `400006BB` | `40000833` `40000881` `40000829` | `48000529` `4800085F` | `130037AA` |
| Green Lantern | `0x48001345` | 5 | 4 | `40000677` `400006C3` `400006CD` `400006BB` | `40000833` `40000881` `40000829` | `48000523` `4800085F` | `130037AC` |
| Green Lantern | `0x48001343` (default) | 4 | 4 | `40000677` `400006C3` `400006CD` `400006BB` | `40000833` `40000881` `40000829` | `48000523` `4800085F` | `130037AB` |
| Harley Quinn | `0x4800134D` | 3,6 | 4 | `40000696` `4000065E` `400006C3` `400006CC` | `40000BE6` `40000833` `40000881` | `480007A8` `48000529` | `130037AA` |
| Harley Quinn | `0x4800134E` | 5 | 4 | `40000696` `4000065E` `400006C3` `400006CC` | `40000BE6` `40000833` `40000881` | `480007A8` `48000523` | `130037AC` |
| Harley Quinn | `0x4800134C` (default) | 4 | 4 | `40000696` `4000065E` `400006C3` `400006CC` | `40000BE6` `40000833` `40000881` | `480007A8` `48000523` | `130037AB` |
| Hawkgirl | `0x48001390` | 3,6 | 4 | `400006E9` `4000069D` `400006D2` `400006DA` | `400008B0` `40000873` `40000BEB` | `480003CB` `48000F57` | `130037AA` |
| Hawkgirl | `0x48001391` | 5 | 4 | `400006E9` `4000069D` `400006D2` `400006DA` | `400008B0` `40000873` `40000BEB` | `480003CB` `48000F57` | `130037AC` |
| Hawkgirl | `0x4800138F` (default) | 4 | 4 | `400006E9` `4000069D` `400006D2` `400006DA` | `400008B0` `40000873` `40000BEB` | `480003CB` `48000F57` | `130037AB` |
| Huntress | `0x480013D5` | 3 | 4 | `400006EA` `400006BE` `40000652` `400006D6` | `40000824` `400008B0` `40000AC7` | `48000780` `48000529` | `130037AA` |
| Huntress | `0x480013D6` | 5 | 4 | `400006EA` `400006BE` `40000652` `400006D6` | `40000824` `400008B0` `40000AC7` | `48000780` `48000529` | `130037AC` |
| Huntress | `0x480013D4` (default) | 4 | 4 | `400006EA` `400006BE` `40000652` `400006D6` | `40000824` `400008B0` `40000AC7` | `48000780` `48000529` | `130037AB` |
| John Stewart | `0x48001412` | 3 | 4 | `400006EA` `400006BE` `40000652` `400006D6` | `40000865` `4000086E` `40000842` | `480003CB` `480005A2` | `130037AA` |
| John Stewart | `0x48001413` | 5 | 4 | `400006EA` `400006BE` `40000652` `400006D6` | `40000865` `4000086E` `40000842` | `480003CB` `480005A2` | `130037AC` |
| John Stewart | `0x48001411` (default) | 4 | 4 | `400006EA` `400006BE` `40000652` `400006D6` | `40000865` `4000086E` `40000842` | `480003CB` `480005A2` | `130037AB` |
| Katana | `0x480013B1` | 3,6 | 4 | `40000652` `4000068C` `400006EA` `400006E1` | `40000AC7` `400008B0` `40000840` | `480003CB` `48000FB1` | `130037AA` |
| Katana | `0x480013B2` | 5 | 4 | `40000652` `4000068C` `400006EA` `400006E1` | `40000AC7` `400008B0` `40000840` | `48000529` `480003CB` | `130037AC` |
| Katana | `0x480013B0` (default) | 4 | 4 | `40000652` `4000068C` `400006EA` `400006E1` | `40000AC7` `400008B0` `40000840` | `48000529` `480003CB` | `130037AB` |
| Krypto | `0x4800137A` | 3,6 | 4 | `40000670` `40000656` `4000066C` `4000069C` | `40000BE6` `40000B29` `40000850` | `48000529` `48001003` | `130037AA` |
| Krypto | `0x4800137B` | 5 | 4 | `40000670` `40000656` `4000066C` `4000069C` | `40000BE6` `40000B29` `40000850` | `48000523` `48001003` | `130037AC` |
| Krypto | `0x48001379` (default) | 4 | 4 | `40000670` `40000656` `4000066C` `4000069C` | `40000BE6` `40000B29` `40000850` | `48000523` `48001003` | `130037AB` |
| Lex Luthor | `0x480013D8` | 3,6 | 4 | `400006BB` `400006BA` `4000068E` `40000649` | `4000082B` `40000881` `40000887` | `480007A8` `48000529` | `130037AA` |
| Lex Luthor | `0x480013D9` | 5 | 4 | `400006BB` `400006BA` `4000068E` `40000649` | `4000082B` `40000881` `40000887` | `480007A8` `48000523` | `130037AC` |
| Lex Luthor | `0x480013D7` (default) | 4 | 4 | `400006BB` `400006BA` `4000068E` `40000649` | `4000082B` `40000881` `40000887` | `480007A8` `48000523` | `130037AB` |
| Mecha Superman | `0x480013DB` | 3,6 | 4 | `40000696` `4000065E` `400006B6` `40000649` | `4000085F` `4000084A` `400008B7` | `480003CB` `48000A3F` | `130037AA` |
| Mecha Superman | `0x480013DC` | 5 | 4 | `40000696` `4000065E` `400006B6` `40000649` | `4000085F` `4000084A` `400008B7` | `480003CB` `48000A3F` | `130037AC` |
| Mecha Superman | `0x480013DA` (default) | 4 | 4 | `40000696` `4000065E` `400006B6` `40000649` | `4000085F` `4000084A` `400008B7` | `480003CB` `48000A3F` | `130037AB` |
| Mecha Wonder Woman | `0x48001384` | 3,6 | 4 | `40000652` `400006BE` `4000066F` `400006C0` | `40000824` `400008B0` `40000AC7` | `48000780` `48000529` | `130037AA` |
| Mecha Wonder Woman | `0x48001385` | 5 | 4 | `40000652` `400006BE` `4000066F` `400006C0` | `40000824` `400008B0` `40000AC7` | `48000780` `48000529` | `130037AC` |
| Mecha Wonder Woman | `0x48001383` (default) | 4 | 4 | `40000652` `400006BE` `4000066F` `400006C0` | `40000824` `400008B0` `40000AC7` | `48000780` `48000529` | `130037AB` |
| Nightmare Batman | `0x48001371` | 3,6 | 4 | `40000652` `400006DB` `400006E8` `400006D6` | `40000AC7` `400008B0` `4000086A` | `48000785` `48000841` | `130037AA` |
| Nightmare Batman | `0x48001372` | 5 | 4 | `40000652` `400006DB` `400006E8` `400006D6` | `40000AC7` `400008B0` `4000086A` | `48000785` `48000841` | `130037AC` |
| Nightmare Batman | `0x48001370` (default) | 4 | 4 | `40000652` `400006DB` `400006E8` `400006D6` | `40000AC7` `400008B0` `4000086A` | `48000785` `48000841` | `130037AB` |
| Nightmare Catwoman | `0x48001362` | 3 | 4 | `40000696` `4000065E` `400006CD` `4000068E` | `40000AD7` `40000B29` `400008B7` | `480005A2` `480012B6` | `130037AA` |
| Nightmare Catwoman | `0x48001363` | 5 | 4 | `40000696` `4000065E` `400006CD` `4000068E` | `40000AD7` `40000B29` `400008B7` | `480005A2` `480012B6` | `130037AC` |
| Nightmare Catwoman | `0x48001361` (default) | 4 | 4 | `40000696` `4000065E` `400006CD` `4000068E` | `40000AD7` `40000B29` `400008B7` | `480005A2` `480012B6` | `130037AB` |
| Nightmare Robin | `0x48001377` | 3,6 | 4 | `40000652` `400006DB` `400006E8` `4000066B` | `4000086A` `40000AC7` `400008B0` | `48000529` `48000780` | `130037AA` |
| Nightmare Robin | `0x48001378` | 5 | 4 | `40000652` `400006DB` `400006E8` `4000066B` | `4000086A` `40000AC7` `400008B0` | `48000529` `48000780` | `130037AC` |
| Nightmare Robin | `0x48001376` (default) | 4 | 4 | `40000652` `400006DB` `400006E8` `4000066B` | `4000086A` `40000AC7` `400008B0` | `48000529` `48000780` | `130037AB` |
| Nightmare Superman | `0x4800138D` | 3,6 | 4 | `40000696` `4000068D` `400006CD` `4000067D` | `40000BE6` `40000833` `40000881` | `480007A8` `48000529` | `130037AA` |
| Nightmare Superman | `0x4800138E` | 5 | 4 | `40000696` `4000068D` `400006CD` `4000067D` | `40000BE6` `40000833` `40000881` | `480007A8` `48000523` | `130037AC` |
| Nightmare Superman | `0x4800138C` (default) | 4 | 4 | `40000696` `4000068D` `400006CD` `4000067D` | `40000BE6` `40000833` `40000881` | `480007A8` `48000523` | `130037AB` |
| Nightwing | `0x480013DE` | 3 | 4 | `40000652` `40000683` `40000683` `40000696` | `40000864` `4000087D` `400008B0` | `480003CB` `48001466` | `130037AA` |
| Nightwing | `0x480013DF` | 5 | 4 | `40000652` `40000683` `40000683` `40000696` | `40000864` `4000087D` `400008B0` | `480003CB` `48001466` | `130037AC` |
| Nightwing | `0x480013DD` (default) | 4 | 4 | `40000652` `40000683` `40000683` `40000696` | `40000864` `4000087D` `400008B0` | `480003CB` `48001466` | `130037AB` |
| Poison Ivy | `0x48001359` | 3,6 | 4 | `40000696` `400006B6` `4000068D` `400006CD` | `40000BE6` `40000833` `40000881` | `48000529` `48000846` | `130037AA` |
| Poison Ivy | `0x4800135A` | 5 | 4 | `40000696` `400006B6` `4000068D` `400006CD` | `40000BE6` `40000833` `40000881` | `48000523` `48000846` | `130037AC` |
| Poison Ivy | `0x48001358` (default) | 4 | 4 | `40000696` `400006B6` `4000068D` `400006CD` | `40000BE6` `40000833` `40000881` | `48000523` `48000846` | `130037AB` |
| Raven | `0x480013B7` | 3,6 | 4 | `400006E0` `4000064A` `400006BB` `4000067D` | `40000BE6` `40000833` `40000881` | `480007A8` `48001160` | `130037AA` |
| Raven | `0x480013B8` | 5 | 4 | `400006E0` `4000064A` `400006BB` `4000067D` | `40000BE6` `40000833` `40000881` | `480007A8` `48000523` | `130037AC` |
| Raven | `0x480013B6` (default) | 4 | 4 | `400006E0` `4000064A` `400006BB` `4000067D` | `40000BE6` `40000833` `40000881` | `480007A8` `48000523` | `130037AB` |
| Robin | `0x480013C6` | 3,6 | 4 | `400006BE` `40000696` `4000065E` `40000652` | `4000086A` `4000085A` `400008B0` | `480007A8` `48000529` | `130037AA` |
| Robin | `0x480013C7` | 5 | 4 | `400006BE` `40000696` `4000065E` `40000652` | `4000086A` `4000085A` `400008B0` | `480007A8` `48000876` | `130037AC` |
| Robin | `0x480013C5` (default) | 4 | 4 | `400006BE` `40000696` `4000065E` `40000652` | `4000086A` `4000085A` `400008B0` | `480007A8` `48000876` | `130037AB` |
| Shazam | `0x480013AB` | 3,6 | 4 | `40000689` `4000065E` `400006B6` `40000696` | `400008B7` `4000082B` `4000085F` | `48000809` `4800080E` | `130037AA` |
| Shazam | `0x480013AC` | 5 | 4 | `40000689` `4000065E` `400006B6` `40000696` | `400008B7` `4000082B` `4000085F` | `48000809` `4800080E` | `130037AC` |
| Shazam | `0x480013AA` (default) | 4 | 4 | `40000689` `4000065E` `400006B6` `40000696` | `400008B7` `4000082B` `4000085F` | `48000809` `4800080E` | `130037AB` |
| Sinestro | `0x48001396` | 3,6 | 4 | `400006A0` `400006CD` `400006BB` `4000067D` | `40000853` `40000881` `40000829` | `48000780` `48000529` | `130037AA` |
| Sinestro | `0x48001397` | 5 | 4 | `400006A0` `400006CD` `400006BB` `4000067D` | `40000853` `40000881` `40000829` | `48000780` `48000523` | `130037AC` |
| Sinestro | `0x48001395` (default) | 4 | 4 | `400006A0` `400006CD` `400006BB` `4000067D` | `40000853` `40000881` `40000829` | `48000780` `48000523` | `130037AB` |
| Solomon Grundy | `0x4800138A` | 3,6 | 4 | `400006D7` `400006AE` `400006A9` `400006E2` | `400008B7` `4000082B` `40000881` | `480005A2` `480010E3` | `130037AA` |
| Solomon Grundy | `0x4800138B` | 5 | 4 | `400006D7` `400006AE` `400006A9` `400006E2` | `400008B7` `4000082B` `40000881` | `48000523` `480010E3` | `130037AC` |
| Solomon Grundy | `0x48001389` (default) | 4 | 4 | `400006D7` `400006AE` `400006A9` `400006E2` | `400008B7` `4000082B` `40000881` | `48000523` `480010E3` | `130037AB` |
| Star Sapphire | `0x4800139F` | 3,6 | 4 | `400006C3` `400006CD` `400006BB` `400006CC` | `40000830` `40000881` `40000829` | `48000780` `48000529` | `130037AA` |
| Star Sapphire | `0x480013A0` | 5 | 4 | `400006C3` `400006CD` `400006BB` `400006CC` | `40000830` `40000881` `40000829` | `48000780` `48000523` | `130037AC` |
| Star Sapphire | `0x4800139E` (default) | 4 | 4 | `400006C3` `400006CD` `400006BB` `400006CC` | `40000830` `40000881` `40000829` | `48000780` `48000523` | `130037AB` |
| Stargirl | `0x4800136E` | 3,6 | 4 | `400006CD` `4000067D` `400006CC` `40000699` | `4000082B` `40000881` `40000829` | `480007A8` `48000529` | `130037AA` |
| Stargirl | `0x4800136F` | 5 | 4 | `400006CD` `4000067D` `400006CC` `40000699` | `4000082B` `40000881` `40000829` | `480007A8` `48000523` | `130037AC` |
| Stargirl | `0x4800136D` (default) | 4 | 4 | `400006CD` `4000067D` `400006CC` `40000699` | `4000082B` `40000881` `40000829` | `480007A8` `48000523` | `130037AB` |
| Starro | `0x480013BA` | 3,6 | 4 | `40000696` `400006BA` `400006AE` `400006D2` | `40000833` `40000BE6` `40000881` | `48000529` `480007A8` | `130037AA` |
| Starro | `0x480013BB` | 5 | 4 | `40000696` `400006BA` `400006AE` `400006D2` | `40000833` `40000BE6` `40000881` | `48000523` `48000529` | `130037AC` |
| Starro | `0x480013B9` (default) | 4 | 4 | `40000696` `400006BA` `400006AE` `400006D2` | `40000833` `40000BE6` `40000881` | `48000523` `48000529` | `130037AB` |
| Supergirl | `0x48001374` | 3,6 | 4 | `40000652` `40000683` `400006E1` `40000696` | `40000AC7` `400008B0` `4000086A` | `480003CB` `48000D2C` | `130037AA` |
| Supergirl | `0x48001375` | 5 | 4 | `40000652` `40000683` `400006E1` `40000696` | `40000AC7` `400008B0` `4000086A` | `480003CB` `48000D2C` | `130037AC` |
| Supergirl | `0x48001373` (default) | 4 | 4 | `40000652` `40000683` `400006E1` `40000696` | `40000AC7` `400008B0` `4000086A` | `480003CB` `48000D2C` | `130037AB` |
| Superman | `0x48001350` | 3,6 | 4 | `40000652` `40000683` `400006E1` `40000696` | `400008B0` `40000873` `40000B29` | `48000A3B` `48000529` | `130037AA` |
| Superman | `0x48001351` | 5 | 4 | `40000652` `40000683` `400006E1` `40000696` | `400008B0` `40000873` `40000B29` | `48000A3B` `48000523` | `130037AC` |
| Superman | `0x4800134F` (default) | 4 | 4 | `40000652` `40000683` `400006E1` `40000696` | `400008B0` `40000873` `40000B29` | `48000A3B` `48000523` | `130037AB` |
| Swamp Thing | `0x480013D2` | 3,6 | 4 | `4000068B` `40000696` `4000065E` `400006B6` | `4000085F` `40000AD5` `400008B7` | `480003CB` `48000F9B` | `130037AA` |
| Swamp Thing | `0x480013D3` | 5 | 4 | `4000068B` `40000696` `4000065E` `400006B6` | `4000085F` `40000AD5` `400008B7` | `480003CB` `48000F9B` | `130037AC` |
| Swamp Thing | `0x480013D1` (default) | 4 | 4 | `4000068B` `40000696` `4000065E` `400006B6` | `4000085F` `40000AD5` `400008B7` | `48000523` `48000F9B` | `130037AB` |
| The Joker | `0x48001368` | 3,6 | 4 | `400006A0` `400006CD` `400006BB` `40000688` | `40000A8A` `40000881` `40000829` | `480007A8` `48000529` | `130037AA` |
| The Joker | `0x48001369` | 5 | 4 | `400006A0` `400006CD` `400006BB` `40000688` | `40000A8A` `40000881` `40000829` | `480007A8` `48000523` | `130037AC` |
| The Joker | `0x48001367` (default) | 4 | 4 | `400006A0` `400006CD` `400006BB` `40000688` | `40000A8A` `40000881` `40000829` | `480007A8` `48000523` | `130037AB` |
| Wonder Woman | `0x48001356` | 3,6 | 4 | `40000696` `4000065E` `400006B6` `40000649` | `4000085F` `40000AD5` `400008B7` | `48000529` `4800081D` | `130037AA` |
| Wonder Woman | `0x48001357` | 5 | 4 | `40000696` `4000065E` `400006B6` `40000649` | `4000085F` `40000AD5` `400008B7` | `48000523` `4800081D` | `130037AC` |
| Wonder Woman | `0x48001355` (default) | 4 | 4 | `40000696` `4000065E` `400006B6` `40000649` | `4000085F` `40000AD5` `400008B7` | `48000523` `4800081D` | `130037AB` |
| Zatanna | `0x4800139C` | 3,6 | 4 | `40000696` `400006CD` `400006BB` `4000067D` | `40000BE6` `40000833` `40000881` | `480007A8` `48000852` | `130037AA` |
| Zatanna | `0x4800139D` | 5 | 4 | `40000696` `400006CD` `400006BB` `4000067D` | `40000BE6` `40000833` `40000881` | `480007A8` `48000523` | `130037AC` |
| Zatanna | `0x4800139B` (default) | 4 | 4 | `40000696` `400006CD` `400006BB` `4000067D` | `40000BE6` `40000833` `40000881` | `480007A8` `48000523` | `130037AB` |
| Zod | `0x480013CF` | 3 | 4 | `40000652` `40000683` `400006E1` `40000696` | `40000BEB` `400008B0` `40000873` | `480003CB` `48000523` | `130037AA` |
| Zod | `0x480013D0` | 5 | 4 | `40000652` `40000683` `400006E1` `40000696` | `40000BEB` `400008B0` `40000873` | `480003CB` `48000523` | `130037AC` |
| Zod | `0x480013CE` (default) | 4 | 4 | `40000652` `40000683` `400006E1` `40000696` | `40000BEB` `400008B0` `40000873` | `480003CB` `48000523` | `130037AB` |

### 1.4 Wire format [C unless marked]

**Amplifier set struct** (reader/writer `0x86FB20`, 0x50 bytes in memory; same bytes in `0x2090`, `0x20C7`, `0x204A`,
`0x2029` tail, `0x20E2` tail and client `0x20FC`):

| Off (mem) | Wire | Field | Flash |
|---|---|---|---|
| +0x00 | u32 | slot ID (1-based; the UI's `ampSetID`, `isValid` = slot > 0 or a default-set DID) | `uiAmplifierSlotID` |
| +0x08 | u64 | id (not shown; server-side set id) [P] | - |
| +0x10 | u32 | champion DID (`0x40` variant) the set belongs to | `didCharacterReference` |
| +0x14 | StringInfo | name (literal or token) | `strAmplifierNames` (via `0x863310`: custom name if not empty, else the StringInfo) [P for the precedence] |
| +0x38 | wstr (compact length + UTF-16) | custom name | |
| +0x3C | u32 | icon DID (`0x13...`) | `didIcon` |
| +0x40 | compact n + n x u32 | amplifier DIDs (augment / mod `0x40` DIDs) | `didEntryOne..Seven` |

| Event | Dir | Body (after the u8 0 base byte) | Handler / Flash | Tag |
|---|---|---|---|---|
| `0x2090` NotifyListAmplifierSets | S->C | `u32 total | u32 max | u32 n | n x set` (ser `0x8481A0`, list `0x839170`) | `0xa64520` -> `NotifyListAmplifierSets(uiTotalAmplifierSets, uiMaxAmplifierSets, slots[], chars[], names[], icons[], entry1[]..entry7[])`; also sets the scorecard flag `bRecvdAmpliferSetManagerData` | C |
| `0x20C7` NotifyAmplifierSet | S->C | `set` (ser `0x83BAF0`) | `0xa1ace0` -> `NotifyAmplifierSet(slot, char, names, icon, e1..e7)`: one set added/changed (answer to a save) | C (layout) / P (use) |
| `0x2052` NotifyAmplifierSetError | S->C | `u32 ErrorType`: `0x10000063` SaveAmplifierSet_Failed, `0x10000064` LoadAmplifierSets_Failed, `0x10000065` SetNameTooLarge | `0xa0b560` | C |
| `0x204A` PlayerPickedAmplifierSet | S->C | `u32 (lobby room id [P]) | set | u64 player IID` (ser `0x83C200`) | `0xab9ab0` -> Flash `(nTeam, nTeamIdx, iidPlayer, uiAmplifierSetSlot, didAmplifierSetIcon, strAmplifierSetName, aAmplifierSet, bMyAmplifierSet)`: team/index looked up from the player IID, bMine = player is local | C (layout) / P (u32) |
| `0x2107` NotifyContextualAmplifierData | S->C | `u32 n | n x {u64 boutique id, u32 amplifier DID, StringInfo currency name, u32 value}` | `(aBoutiqueIDs, aAmplifierDIDs, aCurrencyNames, aCurrencyValues)` = store prices of augments/mods | P |
| `0x200D` RequestChangeAmplifierSet | C->S | `u8 slot` (ser `0x839720`, built at `0x885D70`). Flash passes `(uiAmplifierSet, didDefaultAmplifierSet)` but only the slot byte goes on the wire | lobby | C (layout) / P (default sets: slot 0) |
| `0x2057` RequestMyAmplifierSet | C->S | empty | lobby | P |
| `0x20FC` SaveAmplifierSet | C->S | `set` (ctor `0x8CA5B0` copies the whole struct; ser `0x83BAF0`, same as `0x20C7`) built by `0xa2fd40(slot, char, name, icon, e1..e7)` after `0x875420` validation | `Notice_Amplifier__UI_SaveAmplifierSet` | C |

Server handling: at login (or before the lobby / scorecard) send `0x2090` with the account's saved sets; on `0x20FC`
validate (ownership, rules of 1.2), store, answer `0x20C7` with the stored set (or `0x2052`); in the lobby answer
`0x200D` / `0x2057` with `0x204A` (to every player of the room) and keep the chosen set for the match (apply the
augment stats to the champion, and the mod discounts / stats to the shop: `0x20E2` tail carries the set) [P].

**Example built from the data** (Gaslight Batman `0x40000086`, his default Gotham Divided loadout `0x4800137C`: augments
`0x40000652`, `0x400006B0`, `0x400006BE`, `0x40000693`, mods `0x40000824`, `0x400008B0`, `0x40000AC7`, icon
`0x130037AB`; slot 1, custom name "Default", empty StringInfo `01 00 00 00`, total 1, max 6):

```
set (68 bytes):
01 00 00 00                     slot 1
00 00 00 00 00 00 00 00         u64 id
86 00 00 40                     champion 0x40000086
01 00 00 00                     StringInfo: literal, length 0, no variables
07 44 00 65 00 66 00 61 00 75 00 6c 00 74 00     wstr "Default" (compact 7 + UTF-16)
ab 37 00 13                     icon 0x130037AB
07                              compact count 7
52 06 00 40  b0 06 00 40  be 06 00 40  93 06 00 40     augments
24 08 00 40  b0 08 00 40  c7 0a 00 40                  mods

0x2090 body: 00 | 01 00 00 00 (total) | 06 00 00 00 (max) | 01 00 00 00 (n) | set
0x20C7 body: 00 | set
0x204A body: 00 | 01 00 00 00 (room) | set | 01 00 00 00 00 00 00 02 (player IID 0x0200000000000001)
0x2052 body: 00 | 63 00 00 10
```

(build with `icserver.wire.string_info("")`, `wstring("Default")`, `pack_compact(7)`; each wrapped by
`build_message(SVC_PLAYER_SYSTEM, id, body)`.)

### 1.5 Every augment and mod

Augments (162; `0x48000A49` order; stat format `key op value (grade 0x10000B23)`):

| DID (0x40) | Codename | Brand | Stats (key, op, value, `0x10000B23`) |
|---|---|---|---|
| `0x400006E7` | PAPRIKA | Holt | AttArmor +3.9 (t1); CDR +0.0152 (t3) |
| `0x40000689` | FORTRESS | Holt | AttArmor +3.9 (t1); PowArmor +3.9 (t1) |
| `0x4000065B` | CLAYMORE | Holt | CDR +0.0152 (t3); AttSpeed +%0.0269 (t3) |
| `0x400006E0` | WEREWOLF | Holt | Health +20.05 (t2); CDR +0.0152 (t3) |
| `0x40000685` | HYPER | Holt | Health +20.05 (t2); AttSpeed +%0.0269 (t3) |
| `0x400006C9` | SCORPION | Holt | AttArmor +3.9 (t1); MoveSpeed +0.0252 (t2) |
| `0x400006A4` | PANTHER | Holt | AttArmor +3.9 (t1); AttSpeed +%0.0269 (t3) |
| `0x400006DA` | DAGGER | Holt | MoveSpeed +0.0252 (t2); AttSpeed +%0.0269 (t3) |
| `0x4000064E` | PEGASUS | Holt | MoveSpeed +0.0252 (t2); CDR +0.0152 (t3) |
| `0x40000661` | SILK | Holt | PowArmor +3.9 (t1); AttSpeed +%0.0269 (t3) |
| `0x400006A8` | HYDRA | Holt | PowArmor +3.9 (t1); CDR +0.0152 (t3) |
| `0x40000662` | EARTHQUAKE | Holt | Health +20.05 (t2); MoveSpeed +0.0252 (t2) |
| `0x4000068D` | GIANT | Holt | PowArmor +3.9 (t1); Health +20.05 (t2) |
| `0x400006B4` | ICARUS | Holt | MoveSpeed +0.0252 (t2); CDR +0.0015 (t3) |
| `0x400006C3` | TERROR | Holt | PowArmor +3.9 (t1); MoveSpeed +0.0252 (t2) |
| `0x40000651` | TIGER | Holt | AttArmor +0.39 (t1); AttSpeed +%0.0269 (t3) |
| `0x400006B6` | FORCEFIELD | Holt | AttArmor +3.9 (t1); Health +20.05 (t2) |
| `0x400006D4` | GOBLIN | Holt | AttArmor +0.39 (t1); CDR +0.0015 (t3) |
| `0x400006E2` | RAMPAGE | Holt | Health +2.51 (t2); MoveSpeed +0.0252 (t2) |
| `0x400006D1` | OAK | Holt | AttArmor +0.39 (t1); Health +2.51 (t2) |
| `0x400006D7` | PHALANX | Holt | AttArmor +0.39 (t1); PowArmor +0.39 (t1) |
| `0x400006B2` | ARROW | Holt | Health +2.51 (t2); AttSpeed +%0.0269 (t3) |
| `0x4000068F` | SWORD | Holt | CDR +0.0015 (t3); AttSpeed +%0.0269 (t3) |
| `0x4000067E` | BREAKFAST | Holt | PowArmor +0.39 (t1); CDR +0.0015 (t3) |
| `0x4000066A` | HENDRIX | Holt | Health +2.51 (t2); CDR +0.0015 (t3) |
| `0x400006A9` | SAMURAI | Holt | PowArmor +0.39 (t1); MoveSpeed +0.0252 (t2) |
| `0x400006AE` | TORNADO | Holt | AttArmor +0.39 (t1); MoveSpeed +0.0252 (t2) |
| `0x40000674` | ORIGIN | Kord | AttDmg +2.01 (t2); AttLifesteal +0.01 (t2) |
| `0x40000686` | VANGUARD | Holt | PowArmor +0.39 (t1); Health +2.51 (t2) |
| `0x400006B7` | CRASH | Kord | AttDmg +2.01 (t2); CDR +0.0152 (t3) |
| `0x400006C6` | POPCORN | Kord | AttDmg +2.01 (t2); Health +18.51 (t3) |
| `0x40000695` | CHILLY | Kord | AttLifesteal +0.01 (t2); Health +18.51 (t3) |
| `0x4000067A` | BOOTS | Kord | AttLifesteal +0.01 (t2); CDR +0.0152 (t3) |
| `0x400006A2` | SNOWSTORM | Holt | PowArmor +0.39 (t1); AttSpeed +%0.0269 (t3) |
| `0x400006AD` | BURRITO | Kord | AttLifesteal +0.01 (t2); CDR +0.0015 (t3) |
| `0x400006E8` | SHREW | Kord | AttPen +1.8 (t1); AttLifesteal +0.01 (t2) |
| `0x40000671` | ALPHA | Kord | AttPen +1.8 (t1); Health +18.51 (t3) |
| `0x400006D0` | FORTYTWO | Kord | AttLifesteal +0.01 (t2); Health +2.31 (t3) |
| `0x400006BE` | SLASHER | Kord | AttPen +1.8 (t1); AttDmg +2.01 (t2) |
| `0x400006A6` | OMNI | Kord | AttPen +1.8 (t1); CDR +0.0152 (t3) |
| `0x4000065C` | BUTTER | Kord | CDR +0.0152 (t3); Health +2.31 (t3) |
| `0x400006D6` | LASER | Kord | MoveSpeed +0.0302 (t1); AttDmg +2.01 (t2) |
| `0x400006B0` | FORCE | Kord | AttPen +1.8 (t1); AttDmg +0.25 (t2) |
| `0x4000064A` | TURTLE | Kord | CDR +0.0152 (t3); Health +18.51 (t3) |
| `0x4000067F` | NOTCH | Kord | MoveSpeed +0.0302 (t1); CDR +0.0152 (t3) |
| `0x400006CA` | OMEGA | Kord | AttPen +1.8 (t1); Health +2.31 (t3) |
| `0x40000655` | PIXXY | Kord | MoveSpeed +0.0302 (t1); AttLifesteal +0.01 (t2) |
| `0x400006EA` | HORSEPOWER | Kord | AttPen +1.8 (t1); MoveSpeed +0.0302 (t1) |
| `0x40000672` | PLATINUM | Kord | AttPen +1.8 (t1); CDR +0.0015 (t3) |
| `0x400006D2` | VENGEANCE | Kord | MoveSpeed +0.0302 (t1); Health +18.51 (t3) |
| `0x4000066B` | VEX | Kord | MoveSpeed +0.0302 (t1); AttDmg +0.25 (t2) |
| `0x400006B1` | BLIGHT | Kord | MoveSpeed +0.0302 (t1); Health +2.31 (t3) |
| `0x400006E3` | DIVER | Kord | AttDmg +0.25 (t2); AttLifesteal +0.01 (t2) |
| `0x400006A7` | ARMADILLO | LexCorp | AttArmor +3 (t3); PowArmor +3 (t3) |
| `0x40000687` | BLADELORD | Kord | AttDmg +0.25 (t2); CDR +0.0015 (t3) |
| `0x400006B3` | BEETLE | Kord | AttDmg +0.25 (t2); Health +2.31 (t3) |
| `0x4000069E` | MASTER | LexCorp | CDR +0.0197 (t1); PowArmor +3 (t3) |
| `0x4000065A` | ANGRY | Kord | MoveSpeed +0.0302 (t1); CDR +0.0015 (t3) |
| `0x400006B9` | SANDSTORM | LexCorp | CDR +0.0197 (t1); AttArmor +3 (t3) |
| `0x400006BF` | CROSSROAD | LexCorp | CDR +0.0197 (t1); PowLifesteal +0.0168 (t1) |
| `0x400006A0` | FOREST | LexCorp | CDR +0.0197 (t1); PowDmg +3.51 (t2) |
| `0x400006B8` | CACTUS | LexCorp | PowLifesteal +0.0168 (t1); PowDmg +3.51 (t2) |
| `0x400006CB` | TITAN | LexCorp | PowDmg +3.51 (t2); AttArmor +3 (t3) |
| `0x400006D9` | DRAGON | LexCorp | PowLifesteal +0.0168 (t1); PowArmor +3 (t3) |
| `0x4000067B` | VAMPIRE | LexCorp | PowLifesteal +0.0168 (t1); AttArmor +3 (t3) |
| `0x40000699` | VIPER | LexCorp | PowDmg +3.51 (t2); PowPen +1.5 (t2) |
| `0x400006CF` | LAVA | LexCorp | PowDmg +3.51 (t2); PowArmor +3 (t3) |
| `0x4000066E` | QUICKSAND | LexCorp | CDR +0.0197 (t1); PowPen +1.5 (t2) |
| `0x40000677` | CHRONO | LexCorp | PowLifesteal +0.0168 (t1); PowDmg +0.44 (t2) |
| `0x400006D5` | WHIP | LexCorp | PowPen +1.5 (t2); AttArmor +3 (t3) |
| `0x400006DE` | OCEAN | LexCorp | PowLifesteal +0.0168 (t1); PowArmor +0.3 (t3) |
| `0x40000698` | ENERGY | LexCorp | PowPen +1.5 (t2); PowArmor +3 (t3) |
| `0x40000682` | STARBUCK | LexCorp | PowLifesteal +0.0168 (t1); AttArmor +0.3 (t3) |
| `0x40000653` | SCIENCE | LexCorp | PowPen +1.5 (t2); AttArmor +0.3 (t3) |
| `0x400006C4` | EAGLE | LexCorp | PowLifesteal +0.0168 (t1); PowPen +1.5 (t2) |
| `0x40000660` | STEEL | LexCorp | AttArmor +0.3 (t3); PowArmor +0.3 (t3) |
| `0x400006DF` | ANDROID | LexCorp | CDR +0.002 (t1); PowArmor +0.3 (t3) |
| `0x40000670` | SWAMP | LexCorp | CDR +0.002 (t1); PowDmg +0.44 (t2) |
| `0x40000656` | PYRAMID | LexCorp | CDR +0.002 (t1); AttArmor +0.3 (t3) |
| `0x400006E5` | TUNDRA | LexCorp | CDR +0.002 (t1); PowLifesteal +0.0168 (t1) |
| `0x400006A5` | COBRA | LexCorp | PowDmg +0.44 (t2); PowPen +1.5 (t2) |
| `0x400006D3` | MAZE | LexCorp | CDR +0.002 (t1); PowPen +1.5 (t2) |
| `0x40000652` | KAI | Queen | AttDmg +2.41 (t1); AttPen +1.5 (t2) |
| `0x4000066C` | MAGMA | LexCorp | PowDmg +0.44 (t2); PowArmor +0.3 (t3) |
| `0x4000069C` | CRYPT | LexCorp | PowDmg +0.44 (t2); AttArmor +0.3 (t3) |
| `0x40000676` | VOLCANO | Queen | AttDmg +2.41 (t1); PowDmg +3.24 (t3) |
| `0x4000066F` | FALCON | Queen | AttDmg +2.41 (t1); AttSpeed +%0.035 (t1) |
| `0x400006B5` | PLASMA | LexCorp | PowPen +1.5 (t2); PowArmor +0.3 (t3) |
| `0x40000664` | ELEVEN | Queen | AttDmg +2.41 (t1); PowPen +1.39 (t3) |
| `0x400006C1` | XBERGER | Queen | AttPen +1.5 (t2); PowDmg +3.24 (t3) |
| `0x40000692` | BULWARK | Queen | AttPen +1.5 (t2); CritDmg +0.0625 (t1) |
| `0x4000069A` | PHAX | Queen | AttSpeed +%0.035 (t1); AttPen +1.5 (t2) |
| `0x4000064B` | HEX | Queen | AttDmg +2.41 (t1); CritDmg +0.0625 (t1) |
| `0x4000065D` | ZAG | Queen | AttPen +1.5 (t2); PowPen +1.39 (t3) |
| `0x40000684` | CROW | Queen | AttPen +1.5 (t2); PowDmg +0.4 (t3) |
| `0x40000666` | BRAMBLE | Queen | AttSpeed +%0.035 (t1); PowDmg +3.24 (t3) |
| `0x400006C5` | MANTLE | Queen | AttSpeed +%0.035 (t1); CritDmg +0.0625 (t1) |
| `0x4000065F` | LION | Queen | CritDmg +0.0625 (t1); PowPen +1.39 (t3) |
| `0x40000665` | FIREBALL | Queen | CritDmg +0.0625 (t1); PowDmg +3.24 (t3) |
| `0x40000697` | ECLIPSE | Queen | CritDmg +0.0625 (t1); PowDmg +0.4 (t3) |
| `0x4000068C` | COLUMBUS | Queen | AttDmg +0.3 (t1); AttPen +1.5 (t2) |
| `0x400006AF` | YEW | Queen | PowDmg +3.24 (t3); PowPen +1.39 (t3) |
| `0x40000679` | GANK | Queen | AttDmg +0.3 (t1); PowDmg +0.4 (t3) |
| `0x400006A1` | DANGER | Queen | AttDmg +0.3 (t1); AttSpeed +%0.035 (t1) |
| `0x40000669` | MELTDOWN | Queen | PowDmg +0.4 (t3); PowPen +1.39 (t3) |
| `0x400006DB` | BEAVER | Queen | AttDmg +0.3 (t1); CritDmg +0.0625 (t1) |
| `0x400006A3` | SHEEP | Queen | AttDmg +0.3 (t1); PowPen +1.39 (t3) |
| `0x400006BC` | LOCKDOWN | S.T.A.R. Labs | CDR +0.0164 (t2); AttDmg +1.85 (t3) |
| `0x400006C8` | FLOON | Queen | AttSpeed +%0.035 (t1); PowDmg +0.4 (t3) |
| `0x40000694` | TUSK | Queen | AttSpeed +%0.035 (t1); PowPen +1.39 (t3) |
| `0x40000688` | NOVA | S.T.A.R. Labs | PowDmg +4.21 (t1); PowLifesteal +0.014 (t2) |
| `0x4000066D` | GALAXY | S.T.A.R. Labs | PowDmg +4.21 (t1); AttDmg +1.85 (t3) |
| `0x4000064C` | RED | S.T.A.R. Labs | CDR +0.0164 (t2); AttPen +0.9 (t3) |
| `0x4000069F` | IMPACT | S.T.A.R. Labs | PowDmg +4.21 (t1); AttPen +0.9 (t3) |
| `0x40000663` | LIBRA | S.T.A.R. Labs | PowLifesteal +0.014 (t2); AttDmg +1.85 (t3) |
| `0x400006CD` | BLAST | S.T.A.R. Labs | PowDmg +4.21 (t1); PowPen +1.8 (t1) |
| `0x4000067D` | NEBULA | S.T.A.R. Labs | PowDmg +4.21 (t1); CDR +0.0164 (t2) |
| `0x40000690` | BULLET | S.T.A.R. Labs | AttDmg +1.85 (t3); AttPen +0.9 (t3) |
| `0x40000678` | ARES | S.T.A.R. Labs | PowLifesteal +0.014 (t2); AttPen +0.9 (t3) |
| `0x40000668` | ISIS | S.T.A.R. Labs | PowPen +1.8 (t1); AttDmg +1.85 (t3) |
| `0x4000067C` | SHARK | S.T.A.R. Labs | PowLifesteal +0.014 (t2); CDR +0.0164 (t2) |
| `0x40000691` | STARFISH | S.T.A.R. Labs | PowLifesteal +0.014 (t2); CDR +0.0016 (t2) |
| `0x40000649` | HAVOC | S.T.A.R. Labs | PowPen +1.8 (t1); PowLifesteal +0.014 (t2) |
| `0x400006C2` | RA | S.T.A.R. Labs | PowPen +1.8 (t1); AttDmg +0.23 (t3) |
| `0x4000068A` | REEF | S.T.A.R. Labs | PowPen +1.8 (t1); AttPen +0.9 (t3) |
| `0x4000064D` | ZEUS | S.T.A.R. Labs | PowDmg +0.53 (t1); AttPen +0.9 (t3) |
| `0x400006BB` | ORION | S.T.A.R. Labs | PowDmg +0.53 (t1); PowPen +1.8 (t1) |
| `0x40000657` | CLAW | S.T.A.R. Labs | CDR +0.0016 (t2); AttPen +0.9 (t3) |
| `0x40000680` | CYCLONE | S.T.A.R. Labs | CDR +0.0016 (t2); AttDmg +1.85 (t3) |
| `0x400006CC` | LIGHTNING | S.T.A.R. Labs | PowPen +1.8 (t1); CDR +0.0164 (t2) |
| `0x40000673` | PORTAL | S.T.A.R. Labs | PowDmg +0.53 (t1); AttDmg +0.23 (t3) |
| `0x4000068E` | COMET | S.T.A.R. Labs | PowDmg +0.53 (t1); PowLifesteal +0.014 (t2) |
| `0x400006BA` | SUN | S.T.A.R. Labs | PowDmg +0.53 (t1); CDR +0.0016 (t2) |
| `0x400006E6` | HAWK | Wayne | AttArmor +3.25 (t2); MoveSpeed +0.0232 (t3) |
| `0x40000658` | MONSTER | Wayne | AttArmor +3.25 (t2); AttSpeed +%0.0269 (t3) |
| `0x40000659` | CLIFF | Wayne | AttArmor +3.25 (t2); PowArmor +3.25 (t2) |
| `0x400006C0` | LEMON | Wayne | AttLifesteal +0.012 (t1); AttArmor +3.25 (t2) |
| `0x400006D8` | BREAKER | Wayne | AttLifesteal +0.012 (t1); MoveSpeed +0.0232 (t3) |
| `0x40000667` | SPIDER | S.T.A.R. Labs | PowPen +1.8 (t1); CDR +0.0016 (t2) |
| `0x4000064F` | HEAT | Wayne | AttLifesteal +0.012 (t1); PowArmor +3.25 (t2) |
| `0x400006E1` | CUBE | Wayne | AttLifesteal +0.012 (t1); Health +24.06 (t1) |
| `0x40000683` | LEGEND | Wayne | AttLifesteal +0.012 (t1); Health +3.01 (t1) |
| `0x400006DC` | RAZOR | S.T.A.R. Labs | AttDmg +0.23 (t3); AttPen +0.9 (t3) |
| `0x400006E9` | SPEED | Wayne | Health +24.06 (t1); AttSpeed +%0.0269 (t3) |
| `0x40000654` | WAVE | Wayne | AttLifesteal +0.012 (t1); AttSpeed +%0.0269 (t3) |
| `0x400006BD` | ESSCENCE | Wayne | AttLifesteal +0.012 (t1); PowArmor +0.32 (t2) |
| `0x4000065E` | WOLF | Wayne | Health +24.06 (t1); PowArmor +3.25 (t2) |
| `0x400006E4` | TEACHER | Wayne | AttSpeed +%0.0269 (t3); MoveSpeed +0.0232 (t3) |
| `0x40000681` | PANDA | Wayne | PowArmor +3.25 (t2); AttSpeed +%0.0269 (t3) |
| `0x40000693` | TOWER | Wayne | AttLifesteal +0.012 (t1); AttArmor +0.32 (t2) |
| `0x4000069D` | TSUNAMI | Wayne | Health +24.06 (t1); MoveSpeed +0.0232 (t3) |
| `0x400006AB` | RAVEN | Wayne | AttArmor +0.32 (t2); AttSpeed +%0.0269 (t3) |
| `0x400006AA` | FOX | Wayne | AttArmor +0.32 (t2); MoveSpeed +0.0232 (t3) |
| `0x40000675` | ICEBOX | Wayne | PowArmor +3.25 (t2); MoveSpeed +0.0232 (t3) |
| `0x4000069B` | MOUNTAIN | Wayne | AttArmor +0.32 (t2); PowArmor +0.32 (t2) |
| `0x400006AC` | RAGE | Wayne | Health +3.01 (t1); AttSpeed +%0.0269 (t3) |
| `0x40000650` | WRECK | Wayne | Health +3.01 (t1); PowArmor +0.32 (t2) |
| `0x400006CE` | RABBIT | Wayne | PowArmor +0.32 (t2); AttSpeed +%0.0269 (t3) |
| `0x4000068B` | BEAST | Wayne | Health +3.01 (t1); AttArmor +0.32 (t2) |
| `0x400006C7` | LANDSLIDE | Wayne | Health +3.01 (t1); MoveSpeed +0.0232 (t3) |
| `0x400006DD` | REVENGE | Wayne | PowArmor +0.32 (t2); MoveSpeed +0.0232 (t3) |
| `0x40000696` | CASTLE | Wayne | Health +24.06 (t1); AttArmor +3.25 (t2) |

Mods (172; `0x48000A4A` order; effects per target artifact, `cr` = credit discount on the artifact price):

| DID (0x40) | Short name | Brand | Effects per target artifact |
|---|---|---|---|
| `0x40000874` | Discounted Nil Weapon | Queen | 0x400004CF: -150 cr |
| `0x400008B0` | Empowered Nil Weapon | Queen | 0x400004CF: keyword 0x4800140D (replaces 0x4800140E) |
| `0x40000865` | Discounted Marauder Knife | Kord | 0x400004E2: -100 cr; 0x400004A5: -100 cr; 0x400004BD: -100 cr; 0x400004F8: -100 cr |
| `0x40000858` | Enhanced Attack Damage Marauder Knife | Kord | 0x400004BD: AttDmg +10; 0x400004F8: AttDmg +10 |
| `0x40000868` | Empowered Marauder Knife | Kord | 0x400004F8: keyword 0x4800096F |
| `0x40000A8B` | Discounted Cheetah's Claw | Kord | 0x40000566: -100 cr; 0x4000055A: -100 cr; 0x4000059B: -100 cr; 0x4000055E: -100 cr |
| `0x40000A88` | Enhanced Attack Lifesteal Cheetah's Claw | Queen | 0x4000059B: AttLifesteal +0.04; 0x4000055E: AttLifesteal +0.04 |
| `0x40000ACE` | Empowered Cheetah's Claw | Queen | 0x4000055E: keyword 0x48000EB3 (replaces 0x48000EB1) |
| `0x4000086E` | Optimized Coda Blade | Kord | 0x400004E7: -350 cr |
| `0x4000087D` | Enhanced Attack Damage Coda Blade | Queen | 0x400004A7: AttDmg +10; 0x400004E7: AttDmg +10 |
| `0x40000832` | Rapid Coda Blade | Queen | 0x400004A7: keyword 0x48001295 |
| `0x4000084E` | Enhanced Attack Armor Atlantis Gambit | Queen | 0x400004BA: AttArmor +10; 0x400004A0: AttArmor +10; 0x40000617: AttArmor +10 |
| `0x40000847` | Resonant Atlantis Gambit | Queen | 0x400004A0: keyword 0x48000A53 (replaces 0x480007C5); 0x40000617: keyword 0x48000A53 (replaces 0x480007C5) |
| `0x4000087B` | Enhanced Attack Damage Shade's Cane | Queen | 0x4000056A: AttDmg +10; 0x40000599: AttDmg +10 |
| `0x400008BE` | Optimized Shade's Cane | Queen | 0x40000599: -350 cr |
| `0x40000824` | Enhanced Attack Damage Zeiss Goggles | Queen | 0x40000571: AttDmg +10; 0x4000057A: AttDmg +10 |
| `0x400008A7` | Discounted Zeiss Goggles | Queen | 0x40000587: -150 cr; 0x40000574: -150 cr; 0x40000571: -150 cr; 0x4000057A: -150 cr |
| `0x40000872` | Enhanced Attack Damage Rip Hunter's Time Pack | Wayne | 0x40000514: AttDmg +10; 0x4000051F: AttDmg +10 |
| `0x40000883` | Enhanced Cooldown Reduction Rip Hunter's Time Pack | Wayne | 0x40000514: CDR +0.05; 0x4000051F: CDR +0.05 |
| `0x400008B1` | Discounted Rip Hunter's Time Pack | Wayne | 0x40000517: -150 cr; 0x4000051A: -150 cr; 0x40000514: -150 cr; 0x4000051F: -150 cr |
| `0x40000B28` | Empowered Rip Hunter's Time Pack | LexCorp | 0x4000051A: keyword 0x480007CE; 0x40000514: keyword 0x480007CE; 0x4000051F: keyword 0x480007CE |
| `0x4000084D` | Enhanced Health Lobo's Chain | Wayne | 0x4000050B: Health +75; 0x400004A2: Health +75 |
| `0x400008B8` | Discounted Lobo's Chain | Wayne | 0x4000048C: -150 cr; 0x400004F7: -150 cr; 0x4000050B: -150 cr; 0x400004A2: -150 cr |
| `0x40000BEB` | Empowered Lobo's Chain | Wayne | 0x400004A2: 1000098e=48000f91 |
| `0x40000841` | Overclocked Joker's Crowbar | Queen | 0x4000049E: keyword 0x48000A56 (replaces 0x480007E2) |
| `0x40000856` | Accelerated Joker's Crowbar | Queen | 0x4000049E: keyword 0x48000A55 (replaces 0x480007E2) |
| `0x40000864` | Enhanced Attack Armor Claw of Horus | Wayne | 0x40000497: AttArmor +15; 0x40000500: AttArmor +15 |
| `0x4000086D` | Magnified Claw of Horus | Wayne | 0x40000500: keyword 0x48000A66 (replaces 0x480007CC) |
| `0x400008B3` | Discounted Claw of Horus | Wayne | 0x400004FB: -250 cr; 0x40000497: -250 cr; 0x40000500: -250 cr |
| `0x40000875` | Discounted Huntress' Crossbow | Kord | 0x40000590: -250 cr; 0x4000058F: -250 cr; 0x4000058B: -250 cr |
| `0x40000873` | Enhanced Attack Damage Huntress' Crossbow | Kord | 0x4000058F: AttDmg +10; 0x4000058B: AttDmg +10 |
| `0x40000ABE` | Enhanced Attack Speed Huntress' Crossbow | Kord | 0x4000058F: AttSpeed +%0.1; 0x4000058B: AttSpeed +%0.1 |
| `0x40000840` | Enhanced Move Speed Batman's Utility Belt | Wayne | 0x4000048B: MoveSpeed +0.1; 0x40000633: MoveSpeed +0.1 |
| `0x400008AE` | Discounted Batman's Utility Belt | Wayne | 0x400004BE: -250 cr; 0x400004F9: -250 cr; 0x4000048B: -250 cr; 0x40000633: -250 cr |
| `0x4000087F` | Empowered Mega Rod | Queen | 0x400004F5: keyword 0x48000B77 (replaces 0x48000920) |
| `0x400008A9` | Discounted Mega Rod | Queen | 0x4000049F: -250 cr; 0x400004DE: -250 cr; 0x400004F5: -250 cr |
| `0x40000821` | Enhanced Power Armor Sword of Beowulf | Wayne | 0x40000518: PowArmor +15; 0x4000051D: PowArmor +15 |
| `0x400008A8` | Discounted Sword of Beowulf | Wayne | 0x40000513: -250 cr; 0x40000518: -250 cr; 0x4000051D: -250 cr |
| `0x40000AD3` | Empowered Sword of Beowulf | Wayne | 0x4000051D: keyword 0x48000EB2 (replaces 0x48000CD5) |
| `0x4000083D` | Enhanced Critical Chance Velocity 9 Implants | Queen | 0x400004F4: Crit +0.1; 0x400004DD: Crit +0.1 |
| `0x400008BD` | Optimized Velocity 9 Implants | Queen | 0x400004DD: -350 cr |
| `0x40000AC0` | Empowered Velocity 9 Implants | Queen | 0x400004DD: keyword 0x48000EB4 |
| `0x4000083A` | Optimized Deadshot's Visor | Queen | 0x40000598: -350 cr |
| `0x4000087A` | Enhanced Will Deadshot's Visor | Queen | 0x40000558: Will +200; 0x40000598: Will +200 |
| `0x4000083E` | Empowered Deadshot's Visor | Queen | 0x40000598: keyword 0x48000B7E (replaces 0x480008B2) |
| `0x40000861` | Accelerated Soultaker Katana | Queen | 0x400004D0: keyword 0x48000A60 (replaces 0x48000919) |
| `0x4000088F` | Capacity Soultaker Katana | Queen | 0x400004D0: keyword 0x48000A5F (replaces 0x48000919) |
| `0x400008B5` | Enhanced Attack Damage Soultaker Katana | Queen | 0x4000048D: AttDmg +10; 0x400004D0: AttDmg +10 |
| `0x40000842` | Optimized Atomic Axe | Kord | 0x400004EE: -300 cr |
| `0x40000870` | Enhanced Attack Damage Atomic Axe | Queen | 0x400004DB: AttDmg +10; 0x400004EE: AttDmg +10 |
| `0x40000846` | Enhanced Cooldown Reduction Deathstroke's Claymore | Kord | 0x400004B7: CDR +0.05; 0x40000D1A: CDR +0.05 |
| `0x4000086A` | Enhanced Attack Damage Deathstroke's Claymore | Queen | 0x400004B7: AttDmg +10; 0x40000D1A: AttDmg +10 |
| `0x40000AC1` | Empowered Deathstroke's Claymore | Queen | 0x40000D1A: 1000098e=480012b9 1000098d=480012ba |
| `0x40000878` | Optimized Joe Chill's Revolver | Queen | 0x400004DF: -350 cr |
| `0x40000AC7` | Empowered Joe Chill's Revolver | Queen | 0x400004DF: keyword 0x48000EDC (replaces 0x48000EB4) |
| `0x40000825` | Discounted Nil Cloak | Holt | 0x400004DA: -150 cr |
| `0x400008B7` | Empowered Nil Cloak | Holt | 0x400004DA: keyword 0x4800140F (replaces 0x48001410) |
| `0x4000084B` | Discounted Marauder Shield | Wayne | 0x40000494: -100 cr; 0x400004CD: -100 cr; 0x400004E8: -100 cr; 0x400004A8: -100 cr |
| `0x40000885` | Enhanced Health Marauder Shield | Holt | 0x400004E8: Health +75; 0x400004A8: Health +75 |
| `0x40000849` | Enhanced Health Olympus Gambit | Queen | 0x400004C6: Health +50; 0x400004B2: Health +50; 0x40000618: Health +50 |
| `0x4000085F` | Resonant Olympus Gambit | Queen | 0x400004B2: keyword 0x48000C88 (replaces 0x480007C6); 0x40000618: keyword 0x48000C88 (replaces 0x480007C6) |
| `0x40000835` | Enhanced Power Armor Oa Gambit | Queen | 0x400004C9: PowArmor +10; 0x40000508: PowArmor +10; 0x40000619: PowArmor +10 |
| `0x40000853` | Resonant Oa Gambit | Queen | 0x40000508: keyword 0x48000C85 (replaces 0x480007C8); 0x40000619: keyword 0x48000C85 (replaces 0x480007C8) |
| `0x40000AD7` | Empowered Mirror Master's Prism | LexCorp | 0x4000099D: keyword 0x48000EB9 (replaces 0x48000EB6) |
| `0x40000ACA` | Optimized Mirror Master's Prism | LexCorp | 0x4000099D: -350 cr |
| `0x40000889` | Discounted Medusa Mask | LexCorp | 0x40000597: -150 cr; 0x4000055D: -150 cr; 0x4000055B: -150 cr; 0x40000563: -150 cr |
| `0x4000082D` | Rapid Medusa Mask | LexCorp | 0x40000597: keyword 0x480007E1 |
| `0x40000828` | Optimized Steel's Breastplate | Holt | 0x40000582: -350 cr |
| `0x4000085D` | Altered Steel's Breastplate | Holt | 0x40000582: 1000098e=48000c91 1000098d=480009bd |
| `0x40000AD4` | Enhanced Will Steel's Breastplate | Holt | 0x40000582: Will +200 |
| `0x4000082A` | Accelerated Phantom Stranger's Necklace | Queen | 0x40000572: keyword 0x48000A62 (replaces 0x4800095D); 0x40000576: keyword 0x48000A62 (replaces 0x4800095D) |
| `0x40000891` | Capacity Phantom Stranger's Necklace | Queen | 0x40000572: keyword 0x48000A61 (replaces 0x4800095D); 0x40000576: keyword 0x48000A61 (replaces 0x4800095D) |
| `0x40000AC6` | Enhanced Cooldown Reduction Phantom Stranger's Necklace | Queen | 0x40000576: CDR +0.05 |
| `0x40000884` | Enhanced Attack Armor Diana's Bracers | Queen | 0x400004CB: AttArmor +15; 0x40000C08: AttArmor +15 |
| `0x400008B4` | Discounted Diana's Bracers | Queen | 0x4000048E: -250 cr; 0x400004CB: -250 cr; 0x40000C08: -250 cr |
| `0x40000848` | Optimized Metallo's Heart | Wayne | 0x400004C1: -350 cr |
| `0x4000083F` | Enhanced Attack Armor Metallo's Heart | Holt | 0x400004FC: AttArmor +15; 0x400004C1: AttArmor +15 |
| `0x4000084A` | Resonant Metallo's Heart | Holt | 0x400004C1: keyword 0x48000C82 (replaces 0x480007C7) |
| `0x4000085B` | Discounted Helm of Fate | Holt | 0x400004B3: -250 cr; 0x400004ED: -250 cr; 0x40000501: -250 cr |
| `0x400008BA` | Optimized Helm of Fate | Holt | 0x40000501: -350 cr |
| `0x40000A89` | Rapid Helm of Fate | Holt | 0x400004ED: 1000098e=48000d52 |
| `0x40000AC8` | Enhanced Power Armor Helm of Fate | Holt | 0x400004ED: PowArmor +15; 0x40000501: PowArmor +15 |
| `0x40000B27` | Enhanced Health Booster Gold's Power Suit™ | Wayne | 0x40000B0D: Health +75; 0x40000B0E: Health +75 |
| `0x40000B26` | Enhanced Cooldown Reduction Booster Gold's Power Suit™ | Holt | 0x40000B0D: CDR +0.05; 0x40000B0E: CDR +0.05 |
| `0x40000B29` | Empowered Booster Gold's Power Suit™ | LexCorp | 0x40000B0E: keyword 0x48000F39 |
| `0x40000879` | Optimized Spear of Destiny | Wayne | 0x400004D5: -300 cr |
| `0x40000836` | Enhanced Attack Damage Spear of Destiny | Wayne | 0x40000498: AttDmg +10; 0x400004D5: AttDmg +10 |
| `0x40000AD2` | Empowered Spear of Destiny | Wayne | 0x400004D5: keyword 0x48000EBA (replaces 0x48000EBB) |
| `0x40000823` | Discounted Amulet of Isis | LexCorp | 0x40000516: -150 cr; 0x40000520: -150 cr; 0x40000522: -150 cr |
| `0x40000855` | Enhanced Cooldown Reduction Amulet of Isis | LexCorp | 0x40000520: CDR +0.05; 0x40000522: CDR +0.05 |
| `0x40000ACD` | Empowered Amulet of Isis | LexCorp | 0x40000522: 1000098e=48000ebc 1000098d=48000ebd |
| `0x40000886` | Overclocked Crime Bible | Queen | 0x4000056E: keyword 0x48000A5A (replaces 0x48000961) |
| `0x4000088A` | Accelerated Crime Bible | Queen | 0x4000056E: keyword 0x48000A58 (replaces 0x48000961) |
| `0x40000844` | Accelerated Ruby of Life | Holt | 0x40000496: keyword 0x48000A5E (replaces 0x480007E0); 0x400004FE: keyword 0x48000A5E (replaces 0x480007E0); 0x400004EB: keyword 0x48000A5E (replaces 0x480007E0) |
| `0x4000088E` | Capacity Ruby of Life | Holt | 0x40000496: keyword 0x48000A5D (replaces 0x480007E0); 0x400004FE: keyword 0x48000A5D (replaces 0x480007E0); 0x400004EB: keyword 0x48000A5D (replaces 0x480007E0) |
| `0x400008AA` | Enhanced Health Ruby of Life | Holt | 0x400004FE: Health +75; 0x400004EB: Health +75 |
| `0x40000871` | Discounted Suit of Sorrows | Wayne | 0x400004E4: -150 cr; 0x400004D2: -150 cr; 0x40000492: -150 cr; 0x400004AA: -150 cr |
| `0x4000085A` | Empowered Suit of Sorrows | Wayne | 0x400004AA: keyword 0x48000A2C (replaces 0x48000A2D) |
| `0x40000ACC` | Enhanced Move Speed Suit of Sorrows | Wayne | 0x40000492: MoveSpeed +0.1; 0x400004AA: MoveSpeed +0.1 |
| `0x4000082C` | Optimized Entropy Aegis | Holt | 0x400004BB: -350 cr |
| `0x40000854` | Enhanced Health Entropy Aegis | LexCorp | 0x400004CA: Health +75; 0x400004BB: Health +75 |
| `0x40000A8C` | Empowered Entropy Aegis | LexCorp | 0x400004BB: keyword 0x48000E53 (replaces 0x480007C4) |
| `0x40000AC2` | Enhanced Power Armor Entropy Aegis | LexCorp | 0x400004CA: PowArmor +15; 0x400004BB: PowArmor +15 |
| `0x40000876` | Enhanced Move Speed Kryptonian War Armor | Wayne | 0x400004D4: MoveSpeed +0.1; 0x400004C3: MoveSpeed +0.1 |
| `0x40000850` | Enhanced Health Regen per 10s Kryptonian War Armor | Holt | 0x400004D4: HealthRegen +1.5; 0x400004C3: HealthRegen +1.5 |
| `0x40000AD5` | Empowered Kryptonian War Armor | Holt | 0x400004C3: keyword 0x48000EBF (replaces 0x48000EBE) |
| `0x40000834` | Optimized Ra's al Ghul's Robe | LexCorp | 0x40000523: -350 cr |
| `0x400008AD` | Empowered Ra's al Ghul's Robe | LexCorp | 0x40000523: keyword 0x480015DA (replaces 0x480015D9) |
| `0x40000862` | Enhanced Health Fragment of Mogo | Holt | 0x40000559: Health +75; 0x4000059A: Health +75 |
| `0x400008B9` | Optimized Fragment of Mogo | Holt | 0x4000059A: -350 cr |
| `0x4000087E` | Discounted Nil Ring | S.T.A.R. Labs | 0x400004CE: -150 cr |
| `0x400008B6` | Empowered Nil Ring | S.T.A.R. Labs | 0x400004CE: keyword 0x48001063 (replaces 0x48001064) |
| `0x40000851` | Discounted Marauder Ring | S.T.A.R. Labs | 0x400004D7: -100 cr; 0x40000499: -100 cr; 0x40000503: -100 cr; 0x400004C7: -100 cr |
| `0x40000857` | Enhanced Power Damage Marauder Ring | S.T.A.R. Labs | 0x40000503: PowDmg +15; 0x400004C7: PowDmg +15 |
| `0x4000082F` | Empowered Marauder Ring | S.T.A.R. Labs | 0x400004C7: keyword 0x48000971 |
| `0x40000880` | Discounted Doctor Destiny's Dreamstone | LexCorp | 0x400004E1: -100 cr; 0x4000049D: -100 cr; 0x400004B8: -100 cr; 0x400008C6: -100 cr |
| `0x40000830` | Enhanced Power Damage Doctor Destiny's Dreamstone | LexCorp | 0x400004B8: PowDmg +15; 0x400008C6: PowDmg +15 |
| `0x40000863` | Enhanced Will Qward Gambit | Queen | 0x400004AB: Will +125; 0x4000048F: Will +125; 0x4000061A: Will +125 |
| `0x4000086F` | Resonant Qward Gambit | Queen | 0x4000048F: keyword 0x48000C7F (replaces 0x480007C9); 0x4000061A: keyword 0x48000C7F (replaces 0x480007C9) |
| `0x40000829` | Enhanced Power Damage Fatality's Energy Lance | S.T.A.R. Labs | 0x40000585: PowDmg +15; 0x4000058C: PowDmg +15 |
| `0x40000852` | Enhanced Cooldown Reduction Fatality's Energy Lance | S.T.A.R. Labs | 0x40000585: CDR +0.05; 0x4000058C: CDR +0.05 |
| `0x40000AC9` | Discounted Fatality's Energy Lance | S.T.A.R. Labs | 0x4000057D: -150 cr; 0x40000588: -150 cr; 0x40000585: -150 cr; 0x4000058C: -150 cr |
| `0x40000869` | Discounted Gorilla Grodd's Helmet | LexCorp | 0x4000055C: -100 cr; 0x40000591: -100 cr; 0x4000058E: -100 cr; 0x40000595: -100 cr |
| `0x400008AB` | Enhanced Resilience Gorilla Grodd's Helmet | LexCorp | 0x4000058E: Resilience +0.1; 0x40000595: Resilience +0.1 |
| `0x40000AD1` | Enhanced Will Gorilla Grodd's Helmet | LexCorp | 0x4000058E: Will +200; 0x40000595: Will +200 |
| `0x40000BE7` | Enhanced Cooldown Reduction Gorilla Grodd's Helmet | LexCorp | 0x40000591: CDR +0.05; 0x4000058E: CDR +0.05; 0x40000595: CDR +0.05 |
| `0x40000BEA` | Resonant Gorilla Grodd's Helmet | LexCorp | 0x4000058E: keyword 0x48000FC1 (replaces 0x48000FBC); 0x40000595: keyword 0x48000FC1 (replaces 0x48000FBC) |
| `0x40000BE9` | Enhanced Power Lifesteal Mr. Terrific's T-Mask | LexCorp | 0x40000BDF: PowLifesteal +0.05; 0x40000BDE: PowLifesteal +0.05 |
| `0x40000BEC` | Empowered Mr. Terrific's T-Mask | LexCorp | 0x40000BE1: keyword 0x48000F04; 0x40000BE0: keyword 0x48000F03; 0x40000BDF: keyword 0x48000EF1; 0x40000BDE: keyword 0x48000EF1 |
| `0x40000BE8` | Altered Mr. Terrific's T-Mask | LexCorp | 0x40000BDF: 1000098e=48000fd9 1000098d=48000fa8; 0x40000BDE: 1000098e=48000fd9 1000098d=48000fa8 |
| `0x4000085C` | Discounted The Logoz | S.T.A.R. Labs | 0x40000592: -100 cr; 0x40000583: -100 cr; 0x4000057F: -100 cr |
| `0x40000837` | Accelerated The Logoz | S.T.A.R. Labs | 0x40000583: keyword 0x48000A5C (replaces 0x48000917); 0x4000057F: keyword 0x48000A5C (replaces 0x48000917) |
| `0x40000890` | Capacity The Logoz | S.T.A.R. Labs | 0x40000583: keyword 0x48000A5B (replaces 0x48000917); 0x4000057F: keyword 0x48000A5B (replaces 0x48000917) |
| `0x40000AC4` | Enhanced Will The Logoz | S.T.A.R. Labs | 0x4000057F: Will +200 |
| `0x4000083B` | Overclocked Two Face's Coin | Queen | 0x400004AE: keyword 0x48000A59 (replaces 0x480007E3) |
| `0x40000826` | Accelerated Two Face's Coin | Queen | 0x400004AE: keyword 0x48000A57 (replaces 0x480007E3) |
| `0x40000AD6` | Enhanced Health Cosmic Belt | S.T.A.R. Labs | 0x40000996: Health +75; 0x40000995: Health +75 |
| `0x40000ACF` | Discounted Cosmic Belt | S.T.A.R. Labs | 0x40000997: -150 cr; 0x40000996: -150 cr; 0x40000995: -150 cr |
| `0x4000084F` | Optimized Cosmic Staff | S.T.A.R. Labs | 0x400004EC: -350 cr |
| `0x40000881` | Empowered Cosmic Staff | S.T.A.R. Labs | 0x400004EC: keyword 0x48000BFB (replaces 0x480008D5) |
| `0x40000838` | Enhanced Health Atlantean Royal Seal | LexCorp | 0x400004A4: Health +75; 0x400004E0: Health +75 |
| `0x4000082B` | Empowered Atlantean Royal Seal | LexCorp | 0x400004E0: keyword 0x48000BF8 (replaces 0x480007D1) |
| `0x400008AC` | Optimized Atlantean Royal Seal | LexCorp | 0x400004E0: -350 cr |
| `0x40000888` | Enhanced Will Eye of Ekron | S.T.A.R. Labs | 0x4000053B: Will +200; 0x4000053A: Will +200 |
| `0x4000088D` | Empowered Eye of Ekron | S.T.A.R. Labs | 0x400004FA: keyword 0x48001063; 0x400004C0: keyword 0x48001063; 0x4000053B: keyword 0x48001063; 0x4000053A: keyword 0x48001063 |
| `0x400008BB` | Discounted Eye of Ekron | S.T.A.R. Labs | 0x400004FA: -150 cr; 0x400004C0: -150 cr; 0x4000053B: -150 cr; 0x4000053A: -150 cr |
| `0x4000084C` | Enhanced Attack Damage Blue Scarab | Kord | 0x40000515: AttDmg +10; 0x4000051C: AttDmg +10 |
| `0x4000086B` | Empowered Shade's Cane | Kord | 0x40000599: keyword 0x48000924 |
| `0x40000866` | Empowered Eclipso's Diamond | Kord | 0x400004EF: keyword 0x480008A9 |
| `0x400008AF` | Discounted Blue Scarab | Kord | 0x4000051B: -250 cr; 0x40000515: -250 cr; 0x4000051C: -250 cr |
| `0x40000877` | Enhanced Power Damage Psi-Scimitar | S.T.A.R. Labs | 0x400004C2: PowDmg +15; 0x400004D1: PowDmg +15 |
| `0x400008B2` | Discounted Psi-Scimitar | S.T.A.R. Labs | 0x400004D8: -250 cr; 0x400004C2: -250 cr; 0x400004D1: -250 cr |
| `0x40000A8A` | Empowered Psi-Scimitar | S.T.A.R. Labs | 0x400004D1: keyword 0x4800144F (replaces 0x48001450) |
| `0x40000859` | Optimized Neron's Contract | S.T.A.R. Labs | 0x40000562: -350 cr |
| `0x40000887` | Enhanced Attack Armor Neron's Contract | Holt | 0x40000568: AttArmor +15; 0x40000562: AttArmor +15 |
| `0x40000AD0` | Discounted Neron's Contract | Holt | 0x4000056D: -150 cr; 0x40000565: -150 cr; 0x40000568: -150 cr; 0x40000562: -150 cr |
| `0x40000845` | Optimized Pandora's Box | LexCorp | 0x4000058A: -350 cr |
| `0x4000082E` | Enhanced Cooldown Reduction Pandora's Box | S.T.A.R. Labs | 0x4000058D: CDR +0.05; 0x4000058A: CDR +0.05 |
| `0x40000ABF` | Empowered Pandora's Box | S.T.A.R. Labs | 0x4000058A: 1000098e=48000ec0 1000098d=48000ec1 |
| `0x4000087C` | Discounted Abin Sur's Lantern | S.T.A.R. Labs | 0x40000504: -150 cr; 0x400004E9: -150 cr; 0x400004FD: -150 cr; 0x40000495: -150 cr |
| `0x40000867` | Accelerated Abin Sur's Lantern | S.T.A.R. Labs | 0x400004E9: keyword 0x480010D3 (replaces 0x480010D5); 0x400004FD: keyword 0x480010D3 (replaces 0x480010D5); 0x40000495: keyword 0x480010D3 (replaces 0x480010D5) |
| `0x40000833` | Empowered Eye of Ekron | S.T.A.R. Labs | 0x4000053A: keyword 0x48000B7D (replaces 0x480007CA) |
| `0x40000BE6` | Overclocked Abin Sur's Lantern | LexCorp | 0x400004E9: keyword 0x480010D4 (replaces 0x480010D5); 0x400004FD: keyword 0x480010D4 (replaces 0x480010D5); 0x40000495: keyword 0x480010D4 (replaces 0x480010D5) |
| `0x40000839` | Optimized Book of Eternity | LexCorp | 0x400004EA: -300 cr |
| `0x4000083C` | Enhanced Power Damage Book of Eternity | S.T.A.R. Labs | 0x40000505: PowDmg +15; 0x400004EA: PowDmg +15 |
| `0x4000086C` | Optimized Eclipso's Diamond | LexCorp | 0x400004EF: -350 cr |
| `0x40000822` | Enhanced Power Lifesteal Eclipso's Diamond | S.T.A.R. Labs | 0x400004B5: PowLifesteal +0.05; 0x400004EF: PowLifesteal +0.05 |
| `0x4000085E` | Optimized The Starheart | S.T.A.R. Labs | 0x400004CC: -350 cr |
| `0x40000843` | Optimized Speed Force Battery | Holt | 0x4000061D: -300 cr |
| `0x40000ACB` | Empowered Speed Force Battery | Holt | 0x4000061C: 1000098e=48001460 1000098d=48001461; 0x4000061D: 1000098e=48001460 1000098d=48001461 |
| `0x40000820` | Altered Bleed Portal | Holt | 0x4000061B: 1000098e=48000bfd 1000098d=480009a0 |
| `0x40000E6E` | Empowered Mobius Core | Queen | 0x40000E6B: 1000098e=4800145a 1000098d=4800145b; 0x40000E6A: 1000098e=4800145a 1000098d=4800145b |

---

## 2. Store and collection

### 2.1 Purchasable / ownable item types (`ContentTypeList`) and what the data holds

| ContentType | Name | Data in the packs | Count | Granted / sold how | Tag |
|---|---|---|---|---|---|
| 1 | Character | champion definitions (base variants); typed by the client from the `0x20ED` catalogue (group head = type 7 Character) | 54 | `0x20B8` status + boutique (Crisis Coins / Merits); also reward groups (8 champions in rewards) | C |
| 2 | StolenPower | `0x480003CD` 53 versions + 12 base | 65 | versions unlock with champion level 5 + ownership (2.4) | C |
| 3 | AvatarIcon | `0x10000AB9` records in `0xA00000D0` | 134 (66 are given by reward groups) | reward groups (protector / champion-level achievements); `0x2093` UI_SetProtectorIcon; header `0x2190` / `0x2154` | C |
| 4 | Skins | champion costume variants (group members after the head in `0x20ED`, client type 10 Costume) | 102 | boutique; 1 in the login calendar (`0x40000BD3`) | C |
| 5 | Amplifier | amplifier set slot item `0x49000AA2` | 1 | boutique ("buy a set slot") | P |
| 6 | Boost | none in data | 0 | server | C (absence) |
| 7 | Currency | Merit / Crisis Coins items (`0x10000AB4` / `0x10000AB3`) | 4 + 4 | reward groups via `0x10000AB7` | C |
| 8 | Bundle | none | 0 | server | C (absence) |
| 9 | Skill | the champion "skills" pseudo item of `0x20ED` (sent Hidden) | 54 | - | C |
| 10 | Texture | none | 0 | - | C |
| 11 | Artifact | in-match only (`0x48000163` etc.) | 229 | shop in match | C |
| 12 | Augments | `0x100009EF` | 162 | reward groups (Choice of 20 / 1), boutique (`0x2107` prices) | C |
| 13 | Mods | `0x100009F0` | 172 | reward groups, boutique | C |
| 14 | Entitlement | none | 0 | - | C |
| 15 | GenericDataID | - | - | - | - |
| 16 | SubCurrency | none | 0 | - | C |
| 17 | Achievement | 192 | 192 | `0x2120` | C |
| 18 | RewardSet | 179 | 179 | `0x2125` | C |
| 19 | RewardGroup | 97 | 97 | (inside sets) | C |
| 20 | AccountXP | `0x48000F30` (percent), `0x48000F31` (flat) | 2 | reward groups (training rewards give `0x48000F31` x1) | C (data) / P (meaning) |
| 21 | Encounter | encounters `0x2024` | - | `0x2024` | C |
| 22 | Effect | - | - | - | - |
| 23 | TrainingLesson | trainee achievements | 5 | `0x48000E76` `0x10000BAC` | C |
| 24 | Accolade | `0x10000C68` records | 55 | `0x2188` / `0x2186` | C |
| 25 | LoginReward | `0x48001528` | 110 days | `0x2197` | P |

**Reward item typing in the client** (`0x86E830`, used by `0x2125` / `0x2197` handlers): the value it returns is a
**`PostMatchRewardTypeList`** value [C: values match]: champion head of a `0x20ED` group -> 7 Character, costume -> 10
Costume, else by record: `0x10000AB9` -> 3 AccountIcon, `0x100009EF` -> 8 Augment, `0x100009F0` -> 9 Mod,
`0x10000AB4` -> 1 Merit, `0x10000AB3` -> 2 CrisisCoins, `0x10000B38` 1 -> 5 AccountXPFlat / 2 -> 6 AccountXPPercent,
else 0 (dropped). (4 = ServerOriginated.)

### 2.2 Ownables list (`0x20B8`) [C]

`u8 0 | u32 n | n x (u32 DID, u32 ContentStatus, u32 ContentType, u8 owned, u32 count)` (ser `0x844FD0`, handler
`0xa88030`; first delivery -> `UI.RecvNotice_ItemStatuses`, later ones -> `Incremental_ItemStatuses` with the changed
items only). ContentStatus: 1 Free, 2 Available, 3 Disabled, 4 Unreleased, 5 Hidden, 6 AlwaysOwned, 1001 Innate, 1002
Unavailable (UI states in `champions-all.md` 7). What a complete collection message should list: every champion base
variant (type 1) and costume (4), the 54 skills pseudo-items (9, Hidden), Stolen Power versions (2), avatar icons (3),
augments (12), mods (13), the set slot item (5) [P for types 2/3/5/12/13: the Flash managers read them by type through
`OwnablesManager.GetAllOwnableDatasOfType`]. `count` = quantity (augments/mods may stack [G]).

### 2.3 Store (boutique) events

| Event | Dir | Layout | Meaning | Tag |
|---|---|---|---|---|
| `0x2107` | S->C | `u32 n x {u64 boutiqueID, u32 DID, StringInfo currencyName, u32 value}` | amplifier prices (`AMPLIFIER_BOUTIQUE_DATA_RECEIVED`) | P |
| `0x210C` | S->C | `u64 order` | contextual purchase success | C |
| `0x210D` | S->C | `u64 order | u32 ErrorType` (`0x10000068` GeneralError, `0x10000069` InsufficientFunds) | purchase error | C |
| `0x210F` | S->C | `u64 boutiqueID | u32 DID | {u64, u32, StringInfo, u32, StringInfo, u32}` | price changed `(boutiqueID, didItem, currencyName, initial, orderID, final)` | C (layout) |
| `0x2081` | S->C | `u32 hard (Crisis Coins) | u32 soft (Merits)` | balance | C |
| `0x2095` | S->C | `u32 key | u32 item | StringInfo` | item fulfilled ribbon | C |
| Flash `UI_PurchaseContextualItem(boutiqueID, didItem, currencyName, price)`, `UI_ConfirmContextualPurchase`, `UI_CancelContextualPurchase`; lobby `RequestToPurchaseVariant` | C->S | not located (the senders of these notices were not found in the event table of section 2c) | | open |

No catalogue event lists champion / skin prices: the Flash `BoutiqueDataManager` gets boutique data per DID; for
champions the price shown comes from the Steam overlay / boutique (not in the client data) [P]. For a preservation
server the simplest path is: everything Available + owned, or grant with Merits and send `0x20B8` + `0x2081`.

### 2.4 Stolen Power unlocks

See section 5: every one of the 53 champion versions carries `0x10000922` (unlock rule string: "champion reaches level 5
and is owned"); the 12 base powers have none (always available) [C].

---

## 3. Achievements, quests, rewards, accolades, login rewards, account levels, standings

### 3.1 Achievements [C]

Record (`did | 1 | n`, 23 properties, all 192 identical in shape; read by `0xa428B0` -> Flash `SetAchievementData`):

| Key | Flash argument / meaning | Values in data | Tag |
|---|---|---|---|
| `0x1000073F` | `siAchievementName` (getter `0x86D060`) | | C |
| `0x1000073E` | `siAchievementDescription` (`0x86D090`) | | C |
| `0x1000073A` | `didAchievementIcon` (`0x86D0C0`) | | C |
| `0x10000BBD` / `0x10000BDB` | `didPromotionImage` / `didPromotionImage2` (`0x86D0F0` / `0x86D120`) | | C |
| `0x10000DA4` | `bIsFeatured` (`0x86D180`) | 3 x 1 | C |
| `0x10000C25` | **`eCategoryType`** (`0x86D1A0`): 1 General, 2 Training, 3 ProtectorLevel, 4 ChampionLevel | 24 / 12 / 104 / 52 | C |
| `0x10000A25` | **`eVisiblityType`** (`0x86D150`): 1 Hidden, 2 HiddenUntilDepsCleared, 3 Visible, 4 Secret | 156 / 0 / 18 / 18 | C |
| `0x10000A28` | **`eRepeatType`** (`0x86D1D0`): 1 Never, 2 Daily, 3 Weekly, 4 Monthly, 5 BiWeekly | 191 Never, **1 Weekly** | C |
| `0x10000A2D` | objectives: one `0x10000A2C` each: `0x10000A30` **AchievementObjectiveType** (1 ProtectorLevel, 2 Kill, 3 MatchComplete, 4 MatchWin, 5 Game, 6 CharacterCycle, 7 CharacterLevel5, 8 MatchmadeComplete, 9 MatchmadeWin, 10 ChampionLevel, 11 ChampionOwned), `0x10000A2F` target count, `0x10000B0A` encounter, `0x10000A31` / `0x10000A26` texts, `0x10000A32` icon, `0x10000A2B` objective index (1) | all 192 have exactly 1 objective | C |
| `0x10000A5C` | reward set (`0x40`) | 182 have one | C |
| `0x10000C1C` | internal key (string) | | C |
| `0x10000C1E` | order / id 1-192 | | P |
| `0x10000A27` | champion index (`0x10000593`) for ChampionLevel achievements (Catwoman 10, Doomsday 1...) | 52 | C (matches) |
| `0x10000CD4` | 10 / 11 / 34 / 42 | 7 | G (a UI group) |
| `0x10000CD5` | 1 / 2 on training achievements | 9 | G |
| `0x10000A2A` | start date string (`05/20/2014 04:00:00`) of the weekly achievement | 1 | P (repeat anchor) |
| `0x10000BB9`, `0x10000CCF`, `0x10000BAD`, `0x10000BAE` | flags; `0x10000BAE` = trainee queue encounter, `0x10000BAD` UI transition | | C (BAE/BAD) / G |
| `0x10000BCD` | showcase movie name (played after a Champion Unlocked ribbon) | 9 | C |
| `0x10000A29` | (always absent) | | - |

Category x objective: ProtectorLevel/ProtectorLevel 104 (targets 2..100: one per level, levels 10/20/30/40/50 twice ->
the protector level cap is **100** [P]); ChampionLevel/ChampionLevel 52 (target 20: one per champion -> champion level
cap **20** [P], reward = that champion's protector icon, AutoGrant); Training 12 (tutorials, trainee missions);
General 24 (match counts, wins, champion cycle, secret team compositions, ranked readiness, ranked tier pseudo-levels
500/501/502).

**Daily / weekly quests [C]:** there is no separate quest system in the data. Repeating achievements use
`0x10000A28` RepeatType; the data has exactly **one**: `0x40000C3D` `Play10MatchesPerWeek` (Weekly, 10 MatchComplete,
start `05/20/2014 04:00`, reward 250 Merit). Progress / reset is the server's: `0x2120` per entry carries
`TimesCompleted` and `TimeValid` (u64 unix seconds) [C fields, `scorecard.progress_entry`].

**Secret achievements:** `0x4800144D` (`0x10000D1A`) lists conditions per secret achievement `0x40000EC7`-`0x40000ECB`
(`0x10000D85`): champion index lists (`0x10000D1E`, e.g. 3, 11, 12, 15, 16, 44, 22 for `0x40000ECA` Justice League) or
champion DIDs (`0x10000D1C`) plus a required count (`0x10000D29` / `0x10000D1F`): **team composition in one match** [P].

Events [C]: S->C `0x2120` progress table (+ deprecated list), `0x211F` pending rewardless banners (answer to C->S
`0x212E`), `0x21A6` `(u32,u32,u32)` single objective update; C->S `0x211D` RequestAllAchievementData (empty), `0x211E`
`u32` (acknowledge displayed achievement [P]). Definitions are never sent: the client reads them from the master list
`0x48000CF0` (via `0x100000B7`, `0xa428B0`).

All 192 achievements (sorted by category, then `0x10000C1E`):

| DID (0x40) | Key (`0x10000C1C`) | Cat | Vis | Repeat | Order `C1E` | Objective | Target | Encounter `B0A` | Extra | Reward set -> contents |
|---|---|---|---|---|---|---|---|---|---|---|
| `40000BD6` | CompleteThirdTutorialMission | General | Hidden | Never | 3 | MatchWin | 1 | `40000A80` | cd5=2, ccf=1 | `40000BD7` -> `40000BDA` [Grant] `48000D62` Merit x1000 |
| `40000C54` | DNTDeprecatedTrainee2 | General | Hidden | Never | 4 | MatchComplete | 1 | `40000A80` | ccf=1 | `40000BD7` -> `40000BDA` [Grant] `48000D62` Merit x1000 |
| `40000C3D` | Play10MatchesPerWeek | General | Visible | Weekly | 9 | MatchComplete | 10 | - | cd4=34, start=05/20/2014 04:00:00 | `40000C3B` -> `40000C3C` [Grant] `48000D62` Merit x250 |
| `40000AF1` | Well Rounded | General | Visible | Never | 114 | CharacterLevel5 | 5 | - |  | `40000AF4` -> `40000AFE` [Grant] `48000D62` Merit x1500 |
| `40000AEF` | Counterpicker | General | Visible | Never | 115 | CharacterLevel5 | 20 | - |  | `40000AFF` -> `40000AF6` [Grant] `48000D61` CrisisCoins x250; `40000BBA` icon x1 |
| `40000AEC` | 10onGothamHeights | General | Visible | Never | 116 | MatchComplete | 10 | `4000013E` |  | `40000AFC` -> `40000B03` [Grant] `48000D62` Merit x1000 |
| `40000AEB` | 10onCoastCity | General | Visible | Never | 117 | MatchComplete | 10 | `40000270` |  | `40000AFD` -> `40000B01` [Grant] `48000D62` Merit x1000 |
| `40000AED` | 10onGothamDivided | General | Visible | Never | 118 | MatchComplete | 10 | `40000399` |  | `40000B05` -> `40000AFA` [Grant] `48000D62` Merit x1000 |
| `40000AEE` | Win100 | General | Visible | Never | 119 | MatchWin | 100 | - | cd4=10 | `40000B04` -> `40000B02` [Grant] `48000D62` Merit x2000 |
| `40000AF0` | Win1000 | General | Visible | Never | 120 | MatchWin | 1000 | - | cd4=10 | `40000AFB` -> `40000AF5` [Grant] `48000D61` CrisisCoins x1000; `40000BBB` icon x1 |
| `40000AF2` | TheHalfCycle | General | Visible | Never | 121 | CharacterCycle | 5 | - | cd4=11 | `40000AF9` -> `40000AF8` [Grant] `40000BBC` icon x1 |
| `40000AF3` | TheCycle | General | Visible | Never | 122 | CharacterCycle | 10 | - | cd4=11 | `40000AF7` -> `40000B00` [Grant] `40000BB9` icon x1 |
| `40000E96` | TacoTuesday | General | Secret | Never | 175 | Game | 1 | - | cd4=11, ccf=1 | - |
| `40000ECA` | Justice League | General | Secret | Never | 182 | Game | 1 | - | ccf=1 | - |
| `40000EC9` | Championship Belt | General | Secret | Never | 183 | Game | 1 | - | ccf=1 | - |
| `40000EC8` | Good Kitty | General | Secret | Never | 184 | Game | 1 | - | ccf=1 | - |
| `40000EC7` | Spectrum Warriors | General | Secret | Never | 185 | Game | 1 | - | ccf=1 | - |
| `40000ECB` | We are the Night | General | Secret | Never | 186 | Game | 1 | - | ccf=1 | - |
| `40000ED3` | Play matches for a Champion. | General | Visible | Never | 187 | MatchComplete | 7 | - | cd4=42, featured=1, bb9=1, movie | `40000C51` -> `40000C56` [Grant] `40000280` Batman / The Dark Knight x1 |
| `40000F11` | Ready for Ranked: Champions | General | Visible | Never | 188 | ChampionOwned | 14 | - | featured=1 | `40000F18` -> `40000F20` [Grant] `40000F14` icon x1 |
| `40000F12` | Ready for Ranked: PvP Matches | General | Visible | Never | 189 | MatchComplete | 20 | `40000270` | featured=1 | `40000F19` -> `40000F1D` [Grant] `40000F13` icon x1 |
| `40000F0F` | Silver Tier Ranked | General | Hidden | Never | 190 | ProtectorLevel | 500 | - | ccf=1 | `40000F1B` -> `40000F1E` [Grant] `40000F15` icon x1 |
| `40000F10` | Gold Tier Ranked | General | Hidden | Never | 191 | ProtectorLevel | 501 | - | ccf=1 | `40000F1A` -> `40000F1F` [Grant] `40000F17` icon x1 |
| `40000F0E` | Justice League Ranked | General | Hidden | Never | 192 | ProtectorLevel | 502 | - | ccf=1 | `40000F1C` -> `40000F21` [Grant] `40000F16` icon x1 |
| `40000B08` | CompleteFirstTutorialMission | Training | Secret | Never | 1 | MatchWin | 1 | `40000991` | cd5=2, bb9=1, queue=40000991, movie | `40000B07` -> `40000B06` [Grant] `40000086` Gaslight Batman / The Sound of Justice x1 |
| `40000BD5` | CompleteSecondTutorialMission | Training | Secret | Never | 2 | MatchWin | 1 | `40000A81` | cd5=2, bb9=1, queue=40000A81, movie | `40000C57` -> `40000C52` [Grant] `4000034D` Green Lantern / Fearless Maverick x1; `48000F31` AccountXP(flat) x1 |
| `40000C59` | PlayOneLaneMapMatch | Training | Secret | Never | 5 | MatchComplete | 1 | `40000CA6` | bb9=1, queue=40000CA6, movie | `40000C55` -> `40000C53` [Grant] `40000260` Wonder Woman / Ambassador of Peace x1; `48000F31` AccountXP(flat) x1 |
| `40000C5B` | PlayGothamHeightsVsAIMatch | Training | Secret | Never | 6 | MatchComplete | 1 | `40000B6B` | cd5=1, bb9=1, ccf=1, queue=40000B6B, movie | `40000C7D` -> `40000C7E` [Grant] `4000015A` Doomsday / Ruthless Abomination x1; `48000F31` AccountXP(flat) x1 |
| `40000C5C` | PlayGothamDividedVsAIMatch | Training | Secret | Never | 7 | MatchComplete | 1 | `40000B6C` | cd5=1, bb9=1, ccf=1, queue=40000B6C, movie | `40000C58` -> `40000C5F` [Grant] `4000054A` Harley Quinn / Mad Love x1; `48000F31` AccountXP(flat) x1 |
| `40000C5A` | ReachProtectorLevel5 | Training | Secret | Never | 8 | ProtectorLevel | 5 | - | ccf=1, bad=1 | `40000C51` -> `40000C56` [Grant] `40000280` Batman / The Dark Knight x1 |
| `40000EB8` | TraineeCrimeAlleyDD | Training | Secret | Never | 176 | MatchComplete | 1 | `40000C82` | cd5=1, bb9=1, ccf=1, queue=40000C82, movie | `40000C7D` -> `40000C7E` [Grant] `4000015A` Doomsday / Ruthless Abomination x1; `48000F31` AccountXP(flat) x1 |
| `40000EB9` | TraineeCrimeAlleyHQ | Training | Secret | Never | 177 | MatchComplete | 2 | `40000C82` | cd5=1, bb9=1, queue=40000C82, movie | `40000C58` -> `40000C5F` [Grant] `4000054A` Harley Quinn / Mad Love x1; `48000F31` AccountXP(flat) x1 |
| `40000EBA` | TraineeCoastCityVsAIDD | Training | Secret | Never | 178 | MatchComplete | 3 | `40000B6A` | cd5=1, bb9=1, queue=40000B6A, movie | `40000C7D` -> `40000C7E` [Grant] `4000015A` Doomsday / Ruthless Abomination x1; `48000F31` AccountXP(flat) x1 |
| `40000EB6` | TraineeCoastCityVsAIHQ | Training | Secret | Never | 179 | MatchComplete | 1 | `40000B6A` | cd5=1, bb9=1, ccf=1, queue=40000B6A, movie | `40000C58` -> `40000C5F` [Grant] `4000054A` Harley Quinn / Mad Love x1; `48000F31` AccountXP(flat) x1 |
| `40000EBB` | TraineeCoastCityPvPDD | Training | Secret | Never | 180 | MatchComplete | 1 | `40000270` | bb9=1, ccf=1, queue=40000270, movie | `40000C7D` -> `40000C7E` [Grant] `4000015A` Doomsday / Ruthless Abomination x1; `48000F31` AccountXP(flat) x1 |
| `40000EB7` | TraineeCoastCityPvPHQ | Training | Secret | Never | 181 | MatchComplete | 1 | `40000270` | bb9=1, ccf=1, queue=40000270, movie | `40000C58` -> `40000C5F` [Grant] `4000054A` Harley Quinn / Mad Love x1; `48000F31` AccountXP(flat) x1 |
| `40000955` | ProtectorLevel2 | ProtectorLevel | Hidden | Never | 10 | ProtectorLevel | 2 | - | ccf=1 | - |
| `40000953` | ProtectorLevel3 | ProtectorLevel | Hidden | Never | 11 | ProtectorLevel | 3 | - | ccf=1 | - |
| `40000956` | ProtectorLevel4 | ProtectorLevel | Hidden | Never | 12 | ProtectorLevel | 4 | - | ccf=1 | - |
| `4000095A` | ProtectorLevel5 | ProtectorLevel | Hidden | Never | 13 | ProtectorLevel | 5 | - | ccf=1 | - |
| `40000958` | ProtectorLevel6 | ProtectorLevel | Hidden | Never | 14 | ProtectorLevel | 6 | - |  | `400008FC` -> `40000908` [Choice] `4000066F` augment x1 + `400008E1` [Choice] `40000659` augment x1 + `400008DC` [Choice] `4000067D` augment x1 |
| `40000959` | ProtectorLevel7 | ProtectorLevel | Hidden | Never | 15 | ProtectorLevel | 7 | - |  | `400008FA` -> `40000904` [Choice] `40000652` augment x1; `4000064B` augment x1; `40000676` augment x1; `40000664` augment x1; `40000692` augment x1; `4000068C` augment x1; `400006A1` augment x1; `400006DB` augment x1; `400006A3` augment x1; `40000679` augment x1; `40000674` augment x1; `400006C6` augment x1; `4000067A` augment x1; `40000695` augment x1; `400006BE` augment x1; `400006D6` augment x1; `4000067F` augment x1; `400006B1` augment x1; `400006E3` augment x1; `40000687` augment x1 + `400008E8` [Choice] `40000658` augment x1; `400006E6` augment x1; `400006C0` augment x1; `400006D8` augment x1; `4000069D` augment x1; `400006AB` augment x1; `4000069B` augment x1; `400006C7` augment x1; `4000068B` augment x1; `400006DD` augment x1; `400006A4` augment x1; `400006E7` augment x1; `400006B6` augment x1; `400006C9` augment x1; `40000662` augment x1; `400006AE` augment x1; `400006D1` augment x1; `400006B2` augment x1; `400006A9` augment x1; `4000067E` augment x1 + `400008E6` [Choice] `40000690` augment x1; `4000064C` augment x1; `40000688` augment x1; `400006CD` augment x1; `4000067C` augment x1; `400006DC` augment x1; `4000068E` augment x1; `40000673` augment x1; `400006BB` augment x1; `400006BA` augment x1; `4000069E` augment x1; `400006A0` augment x1; `40000699` augment x1; `400006B8` augment x1; `40000698` augment x1; `40000660` augment x1; `400006E5` augment x1; `400006DF` augment x1; `40000670` augment x1; `400006D3` augment x1 |
| `40000957` | ProtectorLevel8 | ProtectorLevel | Hidden | Never | 16 | ProtectorLevel | 8 | - |  | `40000903` -> `40000902` [Choice] `400008B0` mod x1 + `40000906` [Choice] `400008B7` mod x1 + `40000911` [Choice] `400008B6` mod x1 |
| `40000952` | ProtectorLevel9 | ProtectorLevel | Hidden | Never | 17 | ProtectorLevel | 9 | - |  | `400008FE` -> `40000904` [Choice] `40000652` augment x1; `4000064B` augment x1; `40000676` augment x1; `40000664` augment x1; `40000692` augment x1; `4000068C` augment x1; `400006A1` augment x1; `400006DB` augment x1; `400006A3` augment x1; `40000679` augment x1; `40000674` augment x1; `400006C6` augment x1; `4000067A` augment x1; `40000695` augment x1; `400006BE` augment x1; `400006D6` augment x1; `4000067F` augment x1; `400006B1` augment x1; `400006E3` augment x1; `40000687` augment x1 + `400008E8` [Choice] `40000658` augment x1; `400006E6` augment x1; `400006C0` augment x1; `400006D8` augment x1; `4000069D` augment x1; `400006AB` augment x1; `4000069B` augment x1; `400006C7` augment x1; `4000068B` augment x1; `400006DD` augment x1; `400006A4` augment x1; `400006E7` augment x1; `400006B6` augment x1; `400006C9` augment x1; `40000662` augment x1; `400006AE` augment x1; `400006D1` augment x1; `400006B2` augment x1; `400006A9` augment x1; `4000067E` augment x1 + `400008E6` [Choice] `40000690` augment x1; `4000064C` augment x1; `40000688` augment x1; `400006CD` augment x1; `4000067C` augment x1; `400006DC` augment x1; `4000068E` augment x1; `40000673` augment x1; `400006BB` augment x1; `400006BA` augment x1; `4000069E` augment x1; `400006A0` augment x1; `40000699` augment x1; `400006B8` augment x1; `40000698` augment x1; `40000660` augment x1; `400006E5` augment x1; `400006DF` augment x1; `40000670` augment x1; `400006D3` augment x1 |
| `400008D9` | ProtectorLevel10 | ProtectorLevel | Hidden | Never | 18 | ProtectorLevel | 10 | - |  | `400008E0` -> `40000904` [Choice] `40000652` augment x1; `4000064B` augment x1; `40000676` augment x1; `40000664` augment x1; `40000692` augment x1; `4000068C` augment x1; `400006A1` augment x1; `400006DB` augment x1; `400006A3` augment x1; `40000679` augment x1; `40000674` augment x1; `400006C6` augment x1; `4000067A` augment x1; `40000695` augment x1; `400006BE` augment x1; `400006D6` augment x1; `4000067F` augment x1; `400006B1` augment x1; `400006E3` augment x1; `40000687` augment x1 + `400008E8` [Choice] `40000658` augment x1; `400006E6` augment x1; `400006C0` augment x1; `400006D8` augment x1; `4000069D` augment x1; `400006AB` augment x1; `4000069B` augment x1; `400006C7` augment x1; `4000068B` augment x1; `400006DD` augment x1; `400006A4` augment x1; `400006E7` augment x1; `400006B6` augment x1; `400006C9` augment x1; `40000662` augment x1; `400006AE` augment x1; `400006D1` augment x1; `400006B2` augment x1; `400006A9` augment x1; `4000067E` augment x1 + `400008E6` [Choice] `40000690` augment x1; `4000064C` augment x1; `40000688` augment x1; `400006CD` augment x1; `4000067C` augment x1; `400006DC` augment x1; `4000068E` augment x1; `40000673` augment x1; `400006BB` augment x1; `400006BA` augment x1; `4000069E` augment x1; `400006A0` augment x1; `40000699` augment x1; `400006B8` augment x1; `40000698` augment x1; `40000660` augment x1; `400006E5` augment x1; `400006DF` augment x1; `40000670` augment x1; `400006D3` augment x1 |
| `40000980` | ProtectorLevel11 | ProtectorLevel | Hidden | Never | 19 | ProtectorLevel | 11 | - |  | `400008DE` -> `40000915` [Choice] `40000878` mod x1; `4000086D` mod x1; `40000832` mod x1; `4000087A` mod x1; `4000086A` mod x1; `4000084E` mod x1; `40000883` mod x1; `4000088F` mod x1; `400008AE` mod x1; `400008BD` mod x1 + `4000090C` [Choice] `40000855` mod x1; `400008B4` mod x1; `4000082C` mod x1; `40000862` mod x1; `4000085F` mod x1; `40000850` mod x1; `4000084A` mod x1; `400008AD` mod x1; `4000088E` mod x1; `4000085D` mod x1 + `40000917` [Choice] `40000867` mod x1; `4000082B` mod x1; `40000866` mod x1; `40000839` mod x1; `40000880` mod x1; `40000822` mod x1; `4000088D` mod x1; `40000852` mod x1; `40000890` mod x1; `400008B2` mod x1 |
| `4000096C` | ProtectorLevel12 | ProtectorLevel | Hidden | Never | 20 | ProtectorLevel | 12 | - |  | `4000090E` -> `40000904` [Choice] `40000652` augment x1; `4000064B` augment x1; `40000676` augment x1; `40000664` augment x1; `40000692` augment x1; `4000068C` augment x1; `400006A1` augment x1; `400006DB` augment x1; `400006A3` augment x1; `40000679` augment x1; `40000674` augment x1; `400006C6` augment x1; `4000067A` augment x1; `40000695` augment x1; `400006BE` augment x1; `400006D6` augment x1; `4000067F` augment x1; `400006B1` augment x1; `400006E3` augment x1; `40000687` augment x1 + `400008E8` [Choice] `40000658` augment x1; `400006E6` augment x1; `400006C0` augment x1; `400006D8` augment x1; `4000069D` augment x1; `400006AB` augment x1; `4000069B` augment x1; `400006C7` augment x1; `4000068B` augment x1; `400006DD` augment x1; `400006A4` augment x1; `400006E7` augment x1; `400006B6` augment x1; `400006C9` augment x1; `40000662` augment x1; `400006AE` augment x1; `400006D1` augment x1; `400006B2` augment x1; `400006A9` augment x1; `4000067E` augment x1 + `400008E6` [Choice] `40000690` augment x1; `4000064C` augment x1; `40000688` augment x1; `400006CD` augment x1; `4000067C` augment x1; `400006DC` augment x1; `4000068E` augment x1; `40000673` augment x1; `400006BB` augment x1; `400006BA` augment x1; `4000069E` augment x1; `400006A0` augment x1; `40000699` augment x1; `400006B8` augment x1; `40000698` augment x1; `40000660` augment x1; `400006E5` augment x1; `400006DF` augment x1; `40000670` augment x1; `400006D3` augment x1 |
| `40000971` | ProtectorLevel13 | ProtectorLevel | Hidden | Never | 21 | ProtectorLevel | 13 | - |  | `4000090B` -> `40000904` [Choice] `40000652` augment x1; `4000064B` augment x1; `40000676` augment x1; `40000664` augment x1; `40000692` augment x1; `4000068C` augment x1; `400006A1` augment x1; `400006DB` augment x1; `400006A3` augment x1; `40000679` augment x1; `40000674` augment x1; `400006C6` augment x1; `4000067A` augment x1; `40000695` augment x1; `400006BE` augment x1; `400006D6` augment x1; `4000067F` augment x1; `400006B1` augment x1; `400006E3` augment x1; `40000687` augment x1 + `400008E8` [Choice] `40000658` augment x1; `400006E6` augment x1; `400006C0` augment x1; `400006D8` augment x1; `4000069D` augment x1; `400006AB` augment x1; `4000069B` augment x1; `400006C7` augment x1; `4000068B` augment x1; `400006DD` augment x1; `400006A4` augment x1; `400006E7` augment x1; `400006B6` augment x1; `400006C9` augment x1; `40000662` augment x1; `400006AE` augment x1; `400006D1` augment x1; `400006B2` augment x1; `400006A9` augment x1; `4000067E` augment x1 + `400008E6` [Choice] `40000690` augment x1; `4000064C` augment x1; `40000688` augment x1; `400006CD` augment x1; `4000067C` augment x1; `400006DC` augment x1; `4000068E` augment x1; `40000673` augment x1; `400006BB` augment x1; `400006BA` augment x1; `4000069E` augment x1; `400006A0` augment x1; `40000699` augment x1; `400006B8` augment x1; `40000698` augment x1; `40000660` augment x1; `400006E5` augment x1; `400006DF` augment x1; `40000670` augment x1; `400006D3` augment x1 |
| `40000976` | ProtectorLevel14 | ProtectorLevel | Hidden | Never | 22 | ProtectorLevel | 14 | - |  | `40000913` -> `40000915` [Choice] `40000878` mod x1; `4000086D` mod x1; `40000832` mod x1; `4000087A` mod x1; `4000086A` mod x1; `4000084E` mod x1; `40000883` mod x1; `4000088F` mod x1; `400008AE` mod x1; `400008BD` mod x1 + `4000090C` [Choice] `40000855` mod x1; `400008B4` mod x1; `4000082C` mod x1; `40000862` mod x1; `4000085F` mod x1; `40000850` mod x1; `4000084A` mod x1; `400008AD` mod x1; `4000088E` mod x1; `4000085D` mod x1 + `40000917` [Choice] `40000867` mod x1; `4000082B` mod x1; `40000866` mod x1; `40000839` mod x1; `40000880` mod x1; `40000822` mod x1; `4000088D` mod x1; `40000852` mod x1; `40000890` mod x1; `400008B2` mod x1 |
| `4000098A` | ProtectorLevel15 | ProtectorLevel | Hidden | Never | 23 | ProtectorLevel | 15 | - |  | `40000910` -> `40000904` [Choice] `40000652` augment x1; `4000064B` augment x1; `40000676` augment x1; `40000664` augment x1; `40000692` augment x1; `4000068C` augment x1; `400006A1` augment x1; `400006DB` augment x1; `400006A3` augment x1; `40000679` augment x1; `40000674` augment x1; `400006C6` augment x1; `4000067A` augment x1; `40000695` augment x1; `400006BE` augment x1; `400006D6` augment x1; `4000067F` augment x1; `400006B1` augment x1; `400006E3` augment x1; `40000687` augment x1 + `400008E8` [Choice] `40000658` augment x1; `400006E6` augment x1; `400006C0` augment x1; `400006D8` augment x1; `4000069D` augment x1; `400006AB` augment x1; `4000069B` augment x1; `400006C7` augment x1; `4000068B` augment x1; `400006DD` augment x1; `400006A4` augment x1; `400006E7` augment x1; `400006B6` augment x1; `400006C9` augment x1; `40000662` augment x1; `400006AE` augment x1; `400006D1` augment x1; `400006B2` augment x1; `400006A9` augment x1; `4000067E` augment x1 + `400008E6` [Choice] `40000690` augment x1; `4000064C` augment x1; `40000688` augment x1; `400006CD` augment x1; `4000067C` augment x1; `400006DC` augment x1; `4000068E` augment x1; `40000673` augment x1; `400006BB` augment x1; `400006BA` augment x1; `4000069E` augment x1; `400006A0` augment x1; `40000699` augment x1; `400006B8` augment x1; `40000698` augment x1; `40000660` augment x1; `400006E5` augment x1; `400006DF` augment x1; `40000670` augment x1; `400006D3` augment x1 |
| `40000978` | ProtectorLevel16 | ProtectorLevel | Hidden | Never | 24 | ProtectorLevel | 16 | - |  | `400008FD` -> `40000904` [Choice] `40000652` augment x1; `4000064B` augment x1; `40000676` augment x1; `40000664` augment x1; `40000692` augment x1; `4000068C` augment x1; `400006A1` augment x1; `400006DB` augment x1; `400006A3` augment x1; `40000679` augment x1; `40000674` augment x1; `400006C6` augment x1; `4000067A` augment x1; `40000695` augment x1; `400006BE` augment x1; `400006D6` augment x1; `4000067F` augment x1; `400006B1` augment x1; `400006E3` augment x1; `40000687` augment x1 + `400008E8` [Choice] `40000658` augment x1; `400006E6` augment x1; `400006C0` augment x1; `400006D8` augment x1; `4000069D` augment x1; `400006AB` augment x1; `4000069B` augment x1; `400006C7` augment x1; `4000068B` augment x1; `400006DD` augment x1; `400006A4` augment x1; `400006E7` augment x1; `400006B6` augment x1; `400006C9` augment x1; `40000662` augment x1; `400006AE` augment x1; `400006D1` augment x1; `400006B2` augment x1; `400006A9` augment x1; `4000067E` augment x1 + `400008E6` [Choice] `40000690` augment x1; `4000064C` augment x1; `40000688` augment x1; `400006CD` augment x1; `4000067C` augment x1; `400006DC` augment x1; `4000068E` augment x1; `40000673` augment x1; `400006BB` augment x1; `400006BA` augment x1; `4000069E` augment x1; `400006A0` augment x1; `40000699` augment x1; `400006B8` augment x1; `40000698` augment x1; `40000660` augment x1; `400006E5` augment x1; `400006DF` augment x1; `40000670` augment x1; `400006D3` augment x1 |
| `4000097D` | ProtectorLevel17 | ProtectorLevel | Hidden | Never | 25 | ProtectorLevel | 17 | - |  | `400008FB` -> `40000915` [Choice] `40000878` mod x1; `4000086D` mod x1; `40000832` mod x1; `4000087A` mod x1; `4000086A` mod x1; `4000084E` mod x1; `40000883` mod x1; `4000088F` mod x1; `400008AE` mod x1; `400008BD` mod x1 + `4000090C` [Choice] `40000855` mod x1; `400008B4` mod x1; `4000082C` mod x1; `40000862` mod x1; `4000085F` mod x1; `40000850` mod x1; `4000084A` mod x1; `400008AD` mod x1; `4000088E` mod x1; `4000085D` mod x1 + `40000917` [Choice] `40000867` mod x1; `4000082B` mod x1; `40000866` mod x1; `40000839` mod x1; `40000880` mod x1; `40000822` mod x1; `4000088D` mod x1; `40000852` mod x1; `40000890` mod x1; `400008B2` mod x1 |
| `40000979` | ProtectorLevel18 | ProtectorLevel | Hidden | Never | 26 | ProtectorLevel | 18 | - |  | `40000907` -> `40000904` [Choice] `40000652` augment x1; `4000064B` augment x1; `40000676` augment x1; `40000664` augment x1; `40000692` augment x1; `4000068C` augment x1; `400006A1` augment x1; `400006DB` augment x1; `400006A3` augment x1; `40000679` augment x1; `40000674` augment x1; `400006C6` augment x1; `4000067A` augment x1; `40000695` augment x1; `400006BE` augment x1; `400006D6` augment x1; `4000067F` augment x1; `400006B1` augment x1; `400006E3` augment x1; `40000687` augment x1 + `400008E8` [Choice] `40000658` augment x1; `400006E6` augment x1; `400006C0` augment x1; `400006D8` augment x1; `4000069D` augment x1; `400006AB` augment x1; `4000069B` augment x1; `400006C7` augment x1; `4000068B` augment x1; `400006DD` augment x1; `400006A4` augment x1; `400006E7` augment x1; `400006B6` augment x1; `400006C9` augment x1; `40000662` augment x1; `400006AE` augment x1; `400006D1` augment x1; `400006B2` augment x1; `400006A9` augment x1; `4000067E` augment x1 + `400008E6` [Choice] `40000690` augment x1; `4000064C` augment x1; `40000688` augment x1; `400006CD` augment x1; `4000067C` augment x1; `400006DC` augment x1; `4000068E` augment x1; `40000673` augment x1; `400006BB` augment x1; `400006BA` augment x1; `4000069E` augment x1; `400006A0` augment x1; `40000699` augment x1; `400006B8` augment x1; `40000698` augment x1; `40000660` augment x1; `400006E5` augment x1; `400006DF` augment x1; `40000670` augment x1; `400006D3` augment x1 |
| `40000984` | ProtectorLevel19 | ProtectorLevel | Hidden | Never | 27 | ProtectorLevel | 19 | - |  | `40000900` -> `40000904` [Choice] `40000652` augment x1; `4000064B` augment x1; `40000676` augment x1; `40000664` augment x1; `40000692` augment x1; `4000068C` augment x1; `400006A1` augment x1; `400006DB` augment x1; `400006A3` augment x1; `40000679` augment x1; `40000674` augment x1; `400006C6` augment x1; `4000067A` augment x1; `40000695` augment x1; `400006BE` augment x1; `400006D6` augment x1; `4000067F` augment x1; `400006B1` augment x1; `400006E3` augment x1; `40000687` augment x1 + `400008E8` [Choice] `40000658` augment x1; `400006E6` augment x1; `400006C0` augment x1; `400006D8` augment x1; `4000069D` augment x1; `400006AB` augment x1; `4000069B` augment x1; `400006C7` augment x1; `4000068B` augment x1; `400006DD` augment x1; `400006A4` augment x1; `400006E7` augment x1; `400006B6` augment x1; `400006C9` augment x1; `40000662` augment x1; `400006AE` augment x1; `400006D1` augment x1; `400006B2` augment x1; `400006A9` augment x1; `4000067E` augment x1 + `400008E6` [Choice] `40000690` augment x1; `4000064C` augment x1; `40000688` augment x1; `400006CD` augment x1; `4000067C` augment x1; `400006DC` augment x1; `4000068E` augment x1; `40000673` augment x1; `400006BB` augment x1; `400006BA` augment x1; `4000069E` augment x1; `400006A0` augment x1; `40000699` augment x1; `400006B8` augment x1; `40000698` augment x1; `40000660` augment x1; `400006E5` augment x1; `400006DF` augment x1; `40000670` augment x1; `400006D3` augment x1 |
| `40000985` | ProtectorLevel20 | ProtectorLevel | Hidden | Never | 28 | ProtectorLevel | 20 | - |  | `40000905` -> `40000915` [Choice] `40000878` mod x1; `4000086D` mod x1; `40000832` mod x1; `4000087A` mod x1; `4000086A` mod x1; `4000084E` mod x1; `40000883` mod x1; `4000088F` mod x1; `400008AE` mod x1; `400008BD` mod x1 + `4000090C` [Choice] `40000855` mod x1; `400008B4` mod x1; `4000082C` mod x1; `40000862` mod x1; `4000085F` mod x1; `40000850` mod x1; `4000084A` mod x1; `400008AD` mod x1; `4000088E` mod x1; `4000085D` mod x1 + `40000917` [Choice] `40000867` mod x1; `4000082B` mod x1; `40000866` mod x1; `40000839` mod x1; `40000880` mod x1; `40000822` mod x1; `4000088D` mod x1; `40000852` mod x1; `40000890` mod x1; `400008B2` mod x1 |
| `40000972` | ProtectorLevel21 | ProtectorLevel | Hidden | Never | 29 | ProtectorLevel | 21 | - |  | `400008FF` -> `40000904` [Choice] `40000652` augment x1; `4000064B` augment x1; `40000676` augment x1; `40000664` augment x1; `40000692` augment x1; `4000068C` augment x1; `400006A1` augment x1; `400006DB` augment x1; `400006A3` augment x1; `40000679` augment x1; `40000674` augment x1; `400006C6` augment x1; `4000067A` augment x1; `40000695` augment x1; `400006BE` augment x1; `400006D6` augment x1; `4000067F` augment x1; `400006B1` augment x1; `400006E3` augment x1; `40000687` augment x1 + `400008E8` [Choice] `40000658` augment x1; `400006E6` augment x1; `400006C0` augment x1; `400006D8` augment x1; `4000069D` augment x1; `400006AB` augment x1; `4000069B` augment x1; `400006C7` augment x1; `4000068B` augment x1; `400006DD` augment x1; `400006A4` augment x1; `400006E7` augment x1; `400006B6` augment x1; `400006C9` augment x1; `40000662` augment x1; `400006AE` augment x1; `400006D1` augment x1; `400006B2` augment x1; `400006A9` augment x1; `4000067E` augment x1 + `400008E6` [Choice] `40000690` augment x1; `4000064C` augment x1; `40000688` augment x1; `400006CD` augment x1; `4000067C` augment x1; `400006DC` augment x1; `4000068E` augment x1; `40000673` augment x1; `400006BB` augment x1; `400006BA` augment x1; `4000069E` augment x1; `400006A0` augment x1; `40000699` augment x1; `400006B8` augment x1; `40000698` augment x1; `40000660` augment x1; `400006E5` augment x1; `400006DF` augment x1; `40000670` augment x1; `400006D3` augment x1 |
| `40000987` | ProtectorLevel22 | ProtectorLevel | Hidden | Never | 30 | ProtectorLevel | 22 | - |  | `400008F4` -> `40000904` [Choice] `40000652` augment x1; `4000064B` augment x1; `40000676` augment x1; `40000664` augment x1; `40000692` augment x1; `4000068C` augment x1; `400006A1` augment x1; `400006DB` augment x1; `400006A3` augment x1; `40000679` augment x1; `40000674` augment x1; `400006C6` augment x1; `4000067A` augment x1; `40000695` augment x1; `400006BE` augment x1; `400006D6` augment x1; `4000067F` augment x1; `400006B1` augment x1; `400006E3` augment x1; `40000687` augment x1 + `400008E8` [Choice] `40000658` augment x1; `400006E6` augment x1; `400006C0` augment x1; `400006D8` augment x1; `4000069D` augment x1; `400006AB` augment x1; `4000069B` augment x1; `400006C7` augment x1; `4000068B` augment x1; `400006DD` augment x1; `400006A4` augment x1; `400006E7` augment x1; `400006B6` augment x1; `400006C9` augment x1; `40000662` augment x1; `400006AE` augment x1; `400006D1` augment x1; `400006B2` augment x1; `400006A9` augment x1; `4000067E` augment x1 + `400008E6` [Choice] `40000690` augment x1; `4000064C` augment x1; `40000688` augment x1; `400006CD` augment x1; `4000067C` augment x1; `400006DC` augment x1; `4000068E` augment x1; `40000673` augment x1; `400006BB` augment x1; `400006BA` augment x1; `4000069E` augment x1; `400006A0` augment x1; `40000699` augment x1; `400006B8` augment x1; `40000698` augment x1; `40000660` augment x1; `400006E5` augment x1; `400006DF` augment x1; `40000670` augment x1; `400006D3` augment x1 |
| `4000098B` | ProtectorLevel23 | ProtectorLevel | Hidden | Never | 31 | ProtectorLevel | 23 | - |  | `400008F2` -> `40000915` [Choice] `40000878` mod x1; `4000086D` mod x1; `40000832` mod x1; `4000087A` mod x1; `4000086A` mod x1; `4000084E` mod x1; `40000883` mod x1; `4000088F` mod x1; `400008AE` mod x1; `400008BD` mod x1 + `4000090C` [Choice] `40000855` mod x1; `400008B4` mod x1; `4000082C` mod x1; `40000862` mod x1; `4000085F` mod x1; `40000850` mod x1; `4000084A` mod x1; `400008AD` mod x1; `4000088E` mod x1; `4000085D` mod x1 + `40000917` [Choice] `40000867` mod x1; `4000082B` mod x1; `40000866` mod x1; `40000839` mod x1; `40000880` mod x1; `40000822` mod x1; `4000088D` mod x1; `40000852` mod x1; `40000890` mod x1; `400008B2` mod x1 |
| `4000096A` | ProtectorLevel24 | ProtectorLevel | Hidden | Never | 32 | ProtectorLevel | 24 | - |  | `400008F8` -> `40000904` [Choice] `40000652` augment x1; `4000064B` augment x1; `40000676` augment x1; `40000664` augment x1; `40000692` augment x1; `4000068C` augment x1; `400006A1` augment x1; `400006DB` augment x1; `400006A3` augment x1; `40000679` augment x1; `40000674` augment x1; `400006C6` augment x1; `4000067A` augment x1; `40000695` augment x1; `400006BE` augment x1; `400006D6` augment x1; `4000067F` augment x1; `400006B1` augment x1; `400006E3` augment x1; `40000687` augment x1 + `400008E8` [Choice] `40000658` augment x1; `400006E6` augment x1; `400006C0` augment x1; `400006D8` augment x1; `4000069D` augment x1; `400006AB` augment x1; `4000069B` augment x1; `400006C7` augment x1; `4000068B` augment x1; `400006DD` augment x1; `400006A4` augment x1; `400006E7` augment x1; `400006B6` augment x1; `400006C9` augment x1; `40000662` augment x1; `400006AE` augment x1; `400006D1` augment x1; `400006B2` augment x1; `400006A9` augment x1; `4000067E` augment x1 + `400008E6` [Choice] `40000690` augment x1; `4000064C` augment x1; `40000688` augment x1; `400006CD` augment x1; `4000067C` augment x1; `400006DC` augment x1; `4000068E` augment x1; `40000673` augment x1; `400006BB` augment x1; `400006BA` augment x1; `4000069E` augment x1; `400006A0` augment x1; `40000699` augment x1; `400006B8` augment x1; `40000698` augment x1; `40000660` augment x1; `400006E5` augment x1; `400006DF` augment x1; `40000670` augment x1; `400006D3` augment x1 |
| `4000097F` | ProtectorLevel25 | ProtectorLevel | Hidden | Never | 33 | ProtectorLevel | 25 | - |  | `400008F6` -> `40000904` [Choice] `40000652` augment x1; `4000064B` augment x1; `40000676` augment x1; `40000664` augment x1; `40000692` augment x1; `4000068C` augment x1; `400006A1` augment x1; `400006DB` augment x1; `400006A3` augment x1; `40000679` augment x1; `40000674` augment x1; `400006C6` augment x1; `4000067A` augment x1; `40000695` augment x1; `400006BE` augment x1; `400006D6` augment x1; `4000067F` augment x1; `400006B1` augment x1; `400006E3` augment x1; `40000687` augment x1 + `400008E8` [Choice] `40000658` augment x1; `400006E6` augment x1; `400006C0` augment x1; `400006D8` augment x1; `4000069D` augment x1; `400006AB` augment x1; `4000069B` augment x1; `400006C7` augment x1; `4000068B` augment x1; `400006DD` augment x1; `400006A4` augment x1; `400006E7` augment x1; `400006B6` augment x1; `400006C9` augment x1; `40000662` augment x1; `400006AE` augment x1; `400006D1` augment x1; `400006B2` augment x1; `400006A9` augment x1; `4000067E` augment x1 + `400008E6` [Choice] `40000690` augment x1; `4000064C` augment x1; `40000688` augment x1; `400006CD` augment x1; `4000067C` augment x1; `400006DC` augment x1; `4000068E` augment x1; `40000673` augment x1; `400006BB` augment x1; `400006BA` augment x1; `4000069E` augment x1; `400006A0` augment x1; `40000699` augment x1; `400006B8` augment x1; `40000698` augment x1; `40000660` augment x1; `400006E5` augment x1; `400006DF` augment x1; `40000670` augment x1; `400006D3` augment x1 |
| `4000096B` | ProtectorLevel26 | ProtectorLevel | Hidden | Never | 34 | ProtectorLevel | 26 | - |  | `400008EA` -> `40000915` [Choice] `40000878` mod x1; `4000086D` mod x1; `40000832` mod x1; `4000087A` mod x1; `4000086A` mod x1; `4000084E` mod x1; `40000883` mod x1; `4000088F` mod x1; `400008AE` mod x1; `400008BD` mod x1 + `4000090C` [Choice] `40000855` mod x1; `400008B4` mod x1; `4000082C` mod x1; `40000862` mod x1; `4000085F` mod x1; `40000850` mod x1; `4000084A` mod x1; `400008AD` mod x1; `4000088E` mod x1; `4000085D` mod x1 + `40000917` [Choice] `40000867` mod x1; `4000082B` mod x1; `40000866` mod x1; `40000839` mod x1; `40000880` mod x1; `40000822` mod x1; `4000088D` mod x1; `40000852` mod x1; `40000890` mod x1; `400008B2` mod x1 |
| `40000970` | ProtectorLevel27 | ProtectorLevel | Hidden | Never | 35 | ProtectorLevel | 27 | - |  | `400008E7` -> `40000904` [Choice] `40000652` augment x1; `4000064B` augment x1; `40000676` augment x1; `40000664` augment x1; `40000692` augment x1; `4000068C` augment x1; `400006A1` augment x1; `400006DB` augment x1; `400006A3` augment x1; `40000679` augment x1; `40000674` augment x1; `400006C6` augment x1; `4000067A` augment x1; `40000695` augment x1; `400006BE` augment x1; `400006D6` augment x1; `4000067F` augment x1; `400006B1` augment x1; `400006E3` augment x1; `40000687` augment x1 + `400008E8` [Choice] `40000658` augment x1; `400006E6` augment x1; `400006C0` augment x1; `400006D8` augment x1; `4000069D` augment x1; `400006AB` augment x1; `4000069B` augment x1; `400006C7` augment x1; `4000068B` augment x1; `400006DD` augment x1; `400006A4` augment x1; `400006E7` augment x1; `400006B6` augment x1; `400006C9` augment x1; `40000662` augment x1; `400006AE` augment x1; `400006D1` augment x1; `400006B2` augment x1; `400006A9` augment x1; `4000067E` augment x1 + `400008E6` [Choice] `40000690` augment x1; `4000064C` augment x1; `40000688` augment x1; `400006CD` augment x1; `4000067C` augment x1; `400006DC` augment x1; `4000068E` augment x1; `40000673` augment x1; `400006BB` augment x1; `400006BA` augment x1; `4000069E` augment x1; `400006A0` augment x1; `40000699` augment x1; `400006B8` augment x1; `40000698` augment x1; `40000660` augment x1; `400006E5` augment x1; `400006DF` augment x1; `40000670` augment x1; `400006D3` augment x1 |
| `4000096E` | ProtectorLevel28 | ProtectorLevel | Hidden | Never | 36 | ProtectorLevel | 28 | - |  | `400008EF` -> `40000904` [Choice] `40000652` augment x1; `4000064B` augment x1; `40000676` augment x1; `40000664` augment x1; `40000692` augment x1; `4000068C` augment x1; `400006A1` augment x1; `400006DB` augment x1; `400006A3` augment x1; `40000679` augment x1; `40000674` augment x1; `400006C6` augment x1; `4000067A` augment x1; `40000695` augment x1; `400006BE` augment x1; `400006D6` augment x1; `4000067F` augment x1; `400006B1` augment x1; `400006E3` augment x1; `40000687` augment x1 + `400008E8` [Choice] `40000658` augment x1; `400006E6` augment x1; `400006C0` augment x1; `400006D8` augment x1; `4000069D` augment x1; `400006AB` augment x1; `4000069B` augment x1; `400006C7` augment x1; `4000068B` augment x1; `400006DD` augment x1; `400006A4` augment x1; `400006E7` augment x1; `400006B6` augment x1; `400006C9` augment x1; `40000662` augment x1; `400006AE` augment x1; `400006D1` augment x1; `400006B2` augment x1; `400006A9` augment x1; `4000067E` augment x1 + `400008E6` [Choice] `40000690` augment x1; `4000064C` augment x1; `40000688` augment x1; `400006CD` augment x1; `4000067C` augment x1; `400006DC` augment x1; `4000068E` augment x1; `40000673` augment x1; `400006BB` augment x1; `400006BA` augment x1; `4000069E` augment x1; `400006A0` augment x1; `40000699` augment x1; `400006B8` augment x1; `40000698` augment x1; `40000660` augment x1; `400006E5` augment x1; `400006DF` augment x1; `40000670` augment x1; `400006D3` augment x1 |
| `40000977` | ProtectorLevel29 | ProtectorLevel | Hidden | Never | 37 | ProtectorLevel | 29 | - |  | `400008EC` -> `40000915` [Choice] `40000878` mod x1; `4000086D` mod x1; `40000832` mod x1; `4000087A` mod x1; `4000086A` mod x1; `4000084E` mod x1; `40000883` mod x1; `4000088F` mod x1; `400008AE` mod x1; `400008BD` mod x1 + `4000090C` [Choice] `40000855` mod x1; `400008B4` mod x1; `4000082C` mod x1; `40000862` mod x1; `4000085F` mod x1; `40000850` mod x1; `4000084A` mod x1; `400008AD` mod x1; `4000088E` mod x1; `4000085D` mod x1 + `40000917` [Choice] `40000867` mod x1; `4000082B` mod x1; `40000866` mod x1; `40000839` mod x1; `40000880` mod x1; `40000822` mod x1; `4000088D` mod x1; `40000852` mod x1; `40000890` mod x1; `400008B2` mod x1 |
| `4000096D` | ProtectorLevel30 | ProtectorLevel | Hidden | Never | 38 | ProtectorLevel | 30 | - |  | `40000909` -> `40000904` [Choice] `40000652` augment x1; `4000064B` augment x1; `40000676` augment x1; `40000664` augment x1; `40000692` augment x1; `4000068C` augment x1; `400006A1` augment x1; `400006DB` augment x1; `400006A3` augment x1; `40000679` augment x1; `40000674` augment x1; `400006C6` augment x1; `4000067A` augment x1; `40000695` augment x1; `400006BE` augment x1; `400006D6` augment x1; `4000067F` augment x1; `400006B1` augment x1; `400006E3` augment x1; `40000687` augment x1 + `400008E8` [Choice] `40000658` augment x1; `400006E6` augment x1; `400006C0` augment x1; `400006D8` augment x1; `4000069D` augment x1; `400006AB` augment x1; `4000069B` augment x1; `400006C7` augment x1; `4000068B` augment x1; `400006DD` augment x1; `400006A4` augment x1; `400006E7` augment x1; `400006B6` augment x1; `400006C9` augment x1; `40000662` augment x1; `400006AE` augment x1; `400006D1` augment x1; `400006B2` augment x1; `400006A9` augment x1; `4000067E` augment x1 + `400008E6` [Choice] `40000690` augment x1; `4000064C` augment x1; `40000688` augment x1; `400006CD` augment x1; `4000067C` augment x1; `400006DC` augment x1; `4000068E` augment x1; `40000673` augment x1; `400006BB` augment x1; `400006BA` augment x1; `4000069E` augment x1; `400006A0` augment x1; `40000699` augment x1; `400006B8` augment x1; `40000698` augment x1; `40000660` augment x1; `400006E5` augment x1; `400006DF` augment x1; `40000670` augment x1; `400006D3` augment x1 |
| `4000098F` | ProtectorLevel31 | ProtectorLevel | Hidden | Never | 39 | ProtectorLevel | 31 | - |  | `40000901` -> `40000904` [Choice] `40000652` augment x1; `4000064B` augment x1; `40000676` augment x1; `40000664` augment x1; `40000692` augment x1; `4000068C` augment x1; `400006A1` augment x1; `400006DB` augment x1; `400006A3` augment x1; `40000679` augment x1; `40000674` augment x1; `400006C6` augment x1; `4000067A` augment x1; `40000695` augment x1; `400006BE` augment x1; `400006D6` augment x1; `4000067F` augment x1; `400006B1` augment x1; `400006E3` augment x1; `40000687` augment x1 + `400008E8` [Choice] `40000658` augment x1; `400006E6` augment x1; `400006C0` augment x1; `400006D8` augment x1; `4000069D` augment x1; `400006AB` augment x1; `4000069B` augment x1; `400006C7` augment x1; `4000068B` augment x1; `400006DD` augment x1; `400006A4` augment x1; `400006E7` augment x1; `400006B6` augment x1; `400006C9` augment x1; `40000662` augment x1; `400006AE` augment x1; `400006D1` augment x1; `400006B2` augment x1; `400006A9` augment x1; `4000067E` augment x1 + `400008E6` [Choice] `40000690` augment x1; `4000064C` augment x1; `40000688` augment x1; `400006CD` augment x1; `4000067C` augment x1; `400006DC` augment x1; `4000068E` augment x1; `40000673` augment x1; `400006BB` augment x1; `400006BA` augment x1; `4000069E` augment x1; `400006A0` augment x1; `40000699` augment x1; `400006B8` augment x1; `40000698` augment x1; `40000660` augment x1; `400006E5` augment x1; `400006DF` augment x1; `40000670` augment x1; `400006D3` augment x1 |
| `4000097C` | ProtectorLevel32 | ProtectorLevel | Hidden | Never | 40 | ProtectorLevel | 32 | - |  | `400008F5` -> `40000915` [Choice] `40000878` mod x1; `4000086D` mod x1; `40000832` mod x1; `4000087A` mod x1; `4000086A` mod x1; `4000084E` mod x1; `40000883` mod x1; `4000088F` mod x1; `400008AE` mod x1; `400008BD` mod x1 + `4000090C` [Choice] `40000855` mod x1; `400008B4` mod x1; `4000082C` mod x1; `40000862` mod x1; `4000085F` mod x1; `40000850` mod x1; `4000084A` mod x1; `400008AD` mod x1; `4000088E` mod x1; `4000085D` mod x1 + `40000917` [Choice] `40000867` mod x1; `4000082B` mod x1; `40000866` mod x1; `40000839` mod x1; `40000880` mod x1; `40000822` mod x1; `4000088D` mod x1; `40000852` mod x1; `40000890` mod x1; `400008B2` mod x1 |
| `40000982` | ProtectorLevel33 | ProtectorLevel | Hidden | Never | 41 | ProtectorLevel | 33 | - |  | `400008F3` -> `40000904` [Choice] `40000652` augment x1; `4000064B` augment x1; `40000676` augment x1; `40000664` augment x1; `40000692` augment x1; `4000068C` augment x1; `400006A1` augment x1; `400006DB` augment x1; `400006A3` augment x1; `40000679` augment x1; `40000674` augment x1; `400006C6` augment x1; `4000067A` augment x1; `40000695` augment x1; `400006BE` augment x1; `400006D6` augment x1; `4000067F` augment x1; `400006B1` augment x1; `400006E3` augment x1; `40000687` augment x1 + `400008E8` [Choice] `40000658` augment x1; `400006E6` augment x1; `400006C0` augment x1; `400006D8` augment x1; `4000069D` augment x1; `400006AB` augment x1; `4000069B` augment x1; `400006C7` augment x1; `4000068B` augment x1; `400006DD` augment x1; `400006A4` augment x1; `400006E7` augment x1; `400006B6` augment x1; `400006C9` augment x1; `40000662` augment x1; `400006AE` augment x1; `400006D1` augment x1; `400006B2` augment x1; `400006A9` augment x1; `4000067E` augment x1 + `400008E6` [Choice] `40000690` augment x1; `4000064C` augment x1; `40000688` augment x1; `400006CD` augment x1; `4000067C` augment x1; `400006DC` augment x1; `4000068E` augment x1; `40000673` augment x1; `400006BB` augment x1; `400006BA` augment x1; `4000069E` augment x1; `400006A0` augment x1; `40000699` augment x1; `400006B8` augment x1; `40000698` augment x1; `40000660` augment x1; `400006E5` augment x1; `400006DF` augment x1; `40000670` augment x1; `400006D3` augment x1 |
| `40000986` | ProtectorLevel34 | ProtectorLevel | Hidden | Never | 42 | ProtectorLevel | 34 | - |  | `400008F9` -> `40000904` [Choice] `40000652` augment x1; `4000064B` augment x1; `40000676` augment x1; `40000664` augment x1; `40000692` augment x1; `4000068C` augment x1; `400006A1` augment x1; `400006DB` augment x1; `400006A3` augment x1; `40000679` augment x1; `40000674` augment x1; `400006C6` augment x1; `4000067A` augment x1; `40000695` augment x1; `400006BE` augment x1; `400006D6` augment x1; `4000067F` augment x1; `400006B1` augment x1; `400006E3` augment x1; `40000687` augment x1 + `400008E8` [Choice] `40000658` augment x1; `400006E6` augment x1; `400006C0` augment x1; `400006D8` augment x1; `4000069D` augment x1; `400006AB` augment x1; `4000069B` augment x1; `400006C7` augment x1; `4000068B` augment x1; `400006DD` augment x1; `400006A4` augment x1; `400006E7` augment x1; `400006B6` augment x1; `400006C9` augment x1; `40000662` augment x1; `400006AE` augment x1; `400006D1` augment x1; `400006B2` augment x1; `400006A9` augment x1; `4000067E` augment x1 + `400008E6` [Choice] `40000690` augment x1; `4000064C` augment x1; `40000688` augment x1; `400006CD` augment x1; `4000067C` augment x1; `400006DC` augment x1; `4000068E` augment x1; `40000673` augment x1; `400006BB` augment x1; `400006BA` augment x1; `4000069E` augment x1; `400006A0` augment x1; `40000699` augment x1; `400006B8` augment x1; `40000698` augment x1; `40000660` augment x1; `400006E5` augment x1; `400006DF` augment x1; `40000670` augment x1; `400006D3` augment x1 |
| `40000973` | ProtectorLevel35 | ProtectorLevel | Hidden | Never | 43 | ProtectorLevel | 35 | - |  | `400008F7` -> `40000915` [Choice] `40000878` mod x1; `4000086D` mod x1; `40000832` mod x1; `4000087A` mod x1; `4000086A` mod x1; `4000084E` mod x1; `40000883` mod x1; `4000088F` mod x1; `400008AE` mod x1; `400008BD` mod x1 + `4000090C` [Choice] `40000855` mod x1; `400008B4` mod x1; `4000082C` mod x1; `40000862` mod x1; `4000085F` mod x1; `40000850` mod x1; `4000084A` mod x1; `400008AD` mod x1; `4000088E` mod x1; `4000085D` mod x1 + `40000917` [Choice] `40000867` mod x1; `4000082B` mod x1; `40000866` mod x1; `40000839` mod x1; `40000880` mod x1; `40000822` mod x1; `4000088D` mod x1; `40000852` mod x1; `40000890` mod x1; `400008B2` mod x1 |
| `40000988` | ProtectorLevel36 | ProtectorLevel | Hidden | Never | 44 | ProtectorLevel | 36 | - |  | `400008EB` -> `40000904` [Choice] `40000652` augment x1; `4000064B` augment x1; `40000676` augment x1; `40000664` augment x1; `40000692` augment x1; `4000068C` augment x1; `400006A1` augment x1; `400006DB` augment x1; `400006A3` augment x1; `40000679` augment x1; `40000674` augment x1; `400006C6` augment x1; `4000067A` augment x1; `40000695` augment x1; `400006BE` augment x1; `400006D6` augment x1; `4000067F` augment x1; `400006B1` augment x1; `400006E3` augment x1; `40000687` augment x1 + `400008E8` [Choice] `40000658` augment x1; `400006E6` augment x1; `400006C0` augment x1; `400006D8` augment x1; `4000069D` augment x1; `400006AB` augment x1; `4000069B` augment x1; `400006C7` augment x1; `4000068B` augment x1; `400006DD` augment x1; `400006A4` augment x1; `400006E7` augment x1; `400006B6` augment x1; `400006C9` augment x1; `40000662` augment x1; `400006AE` augment x1; `400006D1` augment x1; `400006B2` augment x1; `400006A9` augment x1; `4000067E` augment x1 + `400008E6` [Choice] `40000690` augment x1; `4000064C` augment x1; `40000688` augment x1; `400006CD` augment x1; `4000067C` augment x1; `400006DC` augment x1; `4000068E` augment x1; `40000673` augment x1; `400006BB` augment x1; `400006BA` augment x1; `4000069E` augment x1; `400006A0` augment x1; `40000699` augment x1; `400006B8` augment x1; `40000698` augment x1; `40000660` augment x1; `400006E5` augment x1; `400006DF` augment x1; `40000670` augment x1; `400006D3` augment x1 |
| `4000098C` | ProtectorLevel37 | ProtectorLevel | Hidden | Never | 45 | ProtectorLevel | 37 | - |  | `400008E9` -> `40000904` [Choice] `40000652` augment x1; `4000064B` augment x1; `40000676` augment x1; `40000664` augment x1; `40000692` augment x1; `4000068C` augment x1; `400006A1` augment x1; `400006DB` augment x1; `400006A3` augment x1; `40000679` augment x1; `40000674` augment x1; `400006C6` augment x1; `4000067A` augment x1; `40000695` augment x1; `400006BE` augment x1; `400006D6` augment x1; `4000067F` augment x1; `400006B1` augment x1; `400006E3` augment x1; `40000687` augment x1 + `400008E8` [Choice] `40000658` augment x1; `400006E6` augment x1; `400006C0` augment x1; `400006D8` augment x1; `4000069D` augment x1; `400006AB` augment x1; `4000069B` augment x1; `400006C7` augment x1; `4000068B` augment x1; `400006DD` augment x1; `400006A4` augment x1; `400006E7` augment x1; `400006B6` augment x1; `400006C9` augment x1; `40000662` augment x1; `400006AE` augment x1; `400006D1` augment x1; `400006B2` augment x1; `400006A9` augment x1; `4000067E` augment x1 + `400008E6` [Choice] `40000690` augment x1; `4000064C` augment x1; `40000688` augment x1; `400006CD` augment x1; `4000067C` augment x1; `400006DC` augment x1; `4000068E` augment x1; `40000673` augment x1; `400006BB` augment x1; `400006BA` augment x1; `4000069E` augment x1; `400006A0` augment x1; `40000699` augment x1; `400006B8` augment x1; `40000698` augment x1; `40000660` augment x1; `400006E5` augment x1; `400006DF` augment x1; `40000670` augment x1; `400006D3` augment x1 |
| `40000989` | ProtectorLevel38 | ProtectorLevel | Hidden | Never | 46 | ProtectorLevel | 38 | - |  | `400008F1` -> `40000915` [Choice] `40000878` mod x1; `4000086D` mod x1; `40000832` mod x1; `4000087A` mod x1; `4000086A` mod x1; `4000084E` mod x1; `40000883` mod x1; `4000088F` mod x1; `400008AE` mod x1; `400008BD` mod x1 + `4000090C` [Choice] `40000855` mod x1; `400008B4` mod x1; `4000082C` mod x1; `40000862` mod x1; `4000085F` mod x1; `40000850` mod x1; `4000084A` mod x1; `400008AD` mod x1; `4000088E` mod x1; `4000085D` mod x1 + `40000917` [Choice] `40000867` mod x1; `4000082B` mod x1; `40000866` mod x1; `40000839` mod x1; `40000880` mod x1; `40000822` mod x1; `4000088D` mod x1; `40000852` mod x1; `40000890` mod x1; `400008B2` mod x1 |
| `40000968` | ProtectorLevel39 | ProtectorLevel | Hidden | Never | 47 | ProtectorLevel | 39 | - |  | `400008EE` -> `40000904` [Choice] `40000652` augment x1; `4000064B` augment x1; `40000676` augment x1; `40000664` augment x1; `40000692` augment x1; `4000068C` augment x1; `400006A1` augment x1; `400006DB` augment x1; `400006A3` augment x1; `40000679` augment x1; `40000674` augment x1; `400006C6` augment x1; `4000067A` augment x1; `40000695` augment x1; `400006BE` augment x1; `400006D6` augment x1; `4000067F` augment x1; `400006B1` augment x1; `400006E3` augment x1; `40000687` augment x1 + `400008E8` [Choice] `40000658` augment x1; `400006E6` augment x1; `400006C0` augment x1; `400006D8` augment x1; `4000069D` augment x1; `400006AB` augment x1; `4000069B` augment x1; `400006C7` augment x1; `4000068B` augment x1; `400006DD` augment x1; `400006A4` augment x1; `400006E7` augment x1; `400006B6` augment x1; `400006C9` augment x1; `40000662` augment x1; `400006AE` augment x1; `400006D1` augment x1; `400006B2` augment x1; `400006A9` augment x1; `4000067E` augment x1 + `400008E6` [Choice] `40000690` augment x1; `4000064C` augment x1; `40000688` augment x1; `400006CD` augment x1; `4000067C` augment x1; `400006DC` augment x1; `4000068E` augment x1; `40000673` augment x1; `400006BB` augment x1; `400006BA` augment x1; `4000069E` augment x1; `400006A0` augment x1; `40000699` augment x1; `400006B8` augment x1; `40000698` augment x1; `40000660` augment x1; `400006E5` augment x1; `400006DF` augment x1; `40000670` augment x1; `400006D3` augment x1 |
| `40000969` | ProtectorLevel40 | ProtectorLevel | Hidden | Never | 48 | ProtectorLevel | 40 | - |  | `400008F0` -> `40000904` [Choice] `40000652` augment x1; `4000064B` augment x1; `40000676` augment x1; `40000664` augment x1; `40000692` augment x1; `4000068C` augment x1; `400006A1` augment x1; `400006DB` augment x1; `400006A3` augment x1; `40000679` augment x1; `40000674` augment x1; `400006C6` augment x1; `4000067A` augment x1; `40000695` augment x1; `400006BE` augment x1; `400006D6` augment x1; `4000067F` augment x1; `400006B1` augment x1; `400006E3` augment x1; `40000687` augment x1 + `400008E8` [Choice] `40000658` augment x1; `400006E6` augment x1; `400006C0` augment x1; `400006D8` augment x1; `4000069D` augment x1; `400006AB` augment x1; `4000069B` augment x1; `400006C7` augment x1; `4000068B` augment x1; `400006DD` augment x1; `400006A4` augment x1; `400006E7` augment x1; `400006B6` augment x1; `400006C9` augment x1; `40000662` augment x1; `400006AE` augment x1; `400006D1` augment x1; `400006B2` augment x1; `400006A9` augment x1; `4000067E` augment x1 + `400008E6` [Choice] `40000690` augment x1; `4000064C` augment x1; `40000688` augment x1; `400006CD` augment x1; `4000067C` augment x1; `400006DC` augment x1; `4000068E` augment x1; `40000673` augment x1; `400006BB` augment x1; `400006BA` augment x1; `4000069E` augment x1; `400006A0` augment x1; `40000699` augment x1; `400006B8` augment x1; `40000698` augment x1; `40000660` augment x1; `400006E5` augment x1; `400006DF` augment x1; `40000670` augment x1; `400006D3` augment x1 |
| `40000983` | ProtectorLevel41 | ProtectorLevel | Hidden | Never | 49 | ProtectorLevel | 41 | - |  | `400008ED` -> `40000915` [Choice] `40000878` mod x1; `4000086D` mod x1; `40000832` mod x1; `4000087A` mod x1; `4000086A` mod x1; `4000084E` mod x1; `40000883` mod x1; `4000088F` mod x1; `400008AE` mod x1; `400008BD` mod x1 + `4000090C` [Choice] `40000855` mod x1; `400008B4` mod x1; `4000082C` mod x1; `40000862` mod x1; `4000085F` mod x1; `40000850` mod x1; `4000084A` mod x1; `400008AD` mod x1; `4000088E` mod x1; `4000085D` mod x1 + `40000917` [Choice] `40000867` mod x1; `4000082B` mod x1; `40000866` mod x1; `40000839` mod x1; `40000880` mod x1; `40000822` mod x1; `4000088D` mod x1; `40000852` mod x1; `40000890` mod x1; `400008B2` mod x1 |
| `4000096F` | ProtectorLevel42 | ProtectorLevel | Hidden | Never | 50 | ProtectorLevel | 42 | - |  | `400008E3` -> `40000904` [Choice] `40000652` augment x1; `4000064B` augment x1; `40000676` augment x1; `40000664` augment x1; `40000692` augment x1; `4000068C` augment x1; `400006A1` augment x1; `400006DB` augment x1; `400006A3` augment x1; `40000679` augment x1; `40000674` augment x1; `400006C6` augment x1; `4000067A` augment x1; `40000695` augment x1; `400006BE` augment x1; `400006D6` augment x1; `4000067F` augment x1; `400006B1` augment x1; `400006E3` augment x1; `40000687` augment x1 + `400008E8` [Choice] `40000658` augment x1; `400006E6` augment x1; `400006C0` augment x1; `400006D8` augment x1; `4000069D` augment x1; `400006AB` augment x1; `4000069B` augment x1; `400006C7` augment x1; `4000068B` augment x1; `400006DD` augment x1; `400006A4` augment x1; `400006E7` augment x1; `400006B6` augment x1; `400006C9` augment x1; `40000662` augment x1; `400006AE` augment x1; `400006D1` augment x1; `400006B2` augment x1; `400006A9` augment x1; `4000067E` augment x1 + `400008E6` [Choice] `40000690` augment x1; `4000064C` augment x1; `40000688` augment x1; `400006CD` augment x1; `4000067C` augment x1; `400006DC` augment x1; `4000068E` augment x1; `40000673` augment x1; `400006BB` augment x1; `400006BA` augment x1; `4000069E` augment x1; `400006A0` augment x1; `40000699` augment x1; `400006B8` augment x1; `40000698` augment x1; `40000660` augment x1; `400006E5` augment x1; `400006DF` augment x1; `40000670` augment x1; `400006D3` augment x1 |
| `40000974` | ProtectorLevel43 | ProtectorLevel | Hidden | Never | 51 | ProtectorLevel | 43 | - |  | `400008E2` -> `40000904` [Choice] `40000652` augment x1; `4000064B` augment x1; `40000676` augment x1; `40000664` augment x1; `40000692` augment x1; `4000068C` augment x1; `400006A1` augment x1; `400006DB` augment x1; `400006A3` augment x1; `40000679` augment x1; `40000674` augment x1; `400006C6` augment x1; `4000067A` augment x1; `40000695` augment x1; `400006BE` augment x1; `400006D6` augment x1; `4000067F` augment x1; `400006B1` augment x1; `400006E3` augment x1; `40000687` augment x1 + `400008E8` [Choice] `40000658` augment x1; `400006E6` augment x1; `400006C0` augment x1; `400006D8` augment x1; `4000069D` augment x1; `400006AB` augment x1; `4000069B` augment x1; `400006C7` augment x1; `4000068B` augment x1; `400006DD` augment x1; `400006A4` augment x1; `400006E7` augment x1; `400006B6` augment x1; `400006C9` augment x1; `40000662` augment x1; `400006AE` augment x1; `400006D1` augment x1; `400006B2` augment x1; `400006A9` augment x1; `4000067E` augment x1 + `400008E6` [Choice] `40000690` augment x1; `4000064C` augment x1; `40000688` augment x1; `400006CD` augment x1; `4000067C` augment x1; `400006DC` augment x1; `4000068E` augment x1; `40000673` augment x1; `400006BB` augment x1; `400006BA` augment x1; `4000069E` augment x1; `400006A0` augment x1; `40000699` augment x1; `400006B8` augment x1; `40000698` augment x1; `40000660` augment x1; `400006E5` augment x1; `400006DF` augment x1; `40000670` augment x1; `400006D3` augment x1 |
| `4000097A` | ProtectorLevel44 | ProtectorLevel | Hidden | Never | 52 | ProtectorLevel | 44 | - |  | `400008E5` -> `40000915` [Choice] `40000878` mod x1; `4000086D` mod x1; `40000832` mod x1; `4000087A` mod x1; `4000086A` mod x1; `4000084E` mod x1; `40000883` mod x1; `4000088F` mod x1; `400008AE` mod x1; `400008BD` mod x1 + `4000090C` [Choice] `40000855` mod x1; `400008B4` mod x1; `4000082C` mod x1; `40000862` mod x1; `4000085F` mod x1; `40000850` mod x1; `4000084A` mod x1; `400008AD` mod x1; `4000088E` mod x1; `4000085D` mod x1 + `40000917` [Choice] `40000867` mod x1; `4000082B` mod x1; `40000866` mod x1; `40000839` mod x1; `40000880` mod x1; `40000822` mod x1; `4000088D` mod x1; `40000852` mod x1; `40000890` mod x1; `400008B2` mod x1 |
| `4000098E` | ProtectorLevel45 | ProtectorLevel | Hidden | Never | 53 | ProtectorLevel | 45 | - |  | `400008E4` -> `40000904` [Choice] `40000652` augment x1; `4000064B` augment x1; `40000676` augment x1; `40000664` augment x1; `40000692` augment x1; `4000068C` augment x1; `400006A1` augment x1; `400006DB` augment x1; `400006A3` augment x1; `40000679` augment x1; `40000674` augment x1; `400006C6` augment x1; `4000067A` augment x1; `40000695` augment x1; `400006BE` augment x1; `400006D6` augment x1; `4000067F` augment x1; `400006B1` augment x1; `400006E3` augment x1; `40000687` augment x1 + `400008E8` [Choice] `40000658` augment x1; `400006E6` augment x1; `400006C0` augment x1; `400006D8` augment x1; `4000069D` augment x1; `400006AB` augment x1; `4000069B` augment x1; `400006C7` augment x1; `4000068B` augment x1; `400006DD` augment x1; `400006A4` augment x1; `400006E7` augment x1; `400006B6` augment x1; `400006C9` augment x1; `40000662` augment x1; `400006AE` augment x1; `400006D1` augment x1; `400006B2` augment x1; `400006A9` augment x1; `4000067E` augment x1 + `400008E6` [Choice] `40000690` augment x1; `4000064C` augment x1; `40000688` augment x1; `400006CD` augment x1; `4000067C` augment x1; `400006DC` augment x1; `4000068E` augment x1; `40000673` augment x1; `400006BB` augment x1; `400006BA` augment x1; `4000069E` augment x1; `400006A0` augment x1; `40000699` augment x1; `400006B8` augment x1; `40000698` augment x1; `40000660` augment x1; `400006E5` augment x1; `400006DF` augment x1; `40000670` augment x1; `400006D3` augment x1 |
| `4000097B` | ProtectorLevel46 | ProtectorLevel | Hidden | Never | 54 | ProtectorLevel | 46 | - |  | `40000916` -> `40000904` [Choice] `40000652` augment x1; `4000064B` augment x1; `40000676` augment x1; `40000664` augment x1; `40000692` augment x1; `4000068C` augment x1; `400006A1` augment x1; `400006DB` augment x1; `400006A3` augment x1; `40000679` augment x1; `40000674` augment x1; `400006C6` augment x1; `4000067A` augment x1; `40000695` augment x1; `400006BE` augment x1; `400006D6` augment x1; `4000067F` augment x1; `400006B1` augment x1; `400006E3` augment x1; `40000687` augment x1 + `400008E8` [Choice] `40000658` augment x1; `400006E6` augment x1; `400006C0` augment x1; `400006D8` augment x1; `4000069D` augment x1; `400006AB` augment x1; `4000069B` augment x1; `400006C7` augment x1; `4000068B` augment x1; `400006DD` augment x1; `400006A4` augment x1; `400006E7` augment x1; `400006B6` augment x1; `400006C9` augment x1; `40000662` augment x1; `400006AE` augment x1; `400006D1` augment x1; `400006B2` augment x1; `400006A9` augment x1; `4000067E` augment x1 + `400008E6` [Choice] `40000690` augment x1; `4000064C` augment x1; `40000688` augment x1; `400006CD` augment x1; `4000067C` augment x1; `400006DC` augment x1; `4000068E` augment x1; `40000673` augment x1; `400006BB` augment x1; `400006BA` augment x1; `4000069E` augment x1; `400006A0` augment x1; `40000699` augment x1; `400006B8` augment x1; `40000698` augment x1; `40000660` augment x1; `400006E5` augment x1; `400006DF` augment x1; `40000670` augment x1; `400006D3` augment x1 |
| `40000981` | ProtectorLevel47 | ProtectorLevel | Hidden | Never | 55 | ProtectorLevel | 47 | - |  | `40000914` -> `40000915` [Choice] `40000878` mod x1; `4000086D` mod x1; `40000832` mod x1; `4000087A` mod x1; `4000086A` mod x1; `4000084E` mod x1; `40000883` mod x1; `4000088F` mod x1; `400008AE` mod x1; `400008BD` mod x1 + `4000090C` [Choice] `40000855` mod x1; `400008B4` mod x1; `4000082C` mod x1; `40000862` mod x1; `4000085F` mod x1; `40000850` mod x1; `4000084A` mod x1; `400008AD` mod x1; `4000088E` mod x1; `4000085D` mod x1 + `40000917` [Choice] `40000867` mod x1; `4000082B` mod x1; `40000866` mod x1; `40000839` mod x1; `40000880` mod x1; `40000822` mod x1; `4000088D` mod x1; `40000852` mod x1; `40000890` mod x1; `400008B2` mod x1 |
| `4000097E` | ProtectorLevel48 | ProtectorLevel | Hidden | Never | 56 | ProtectorLevel | 48 | - |  | `400008DF` -> `40000904` [Choice] `40000652` augment x1; `4000064B` augment x1; `40000676` augment x1; `40000664` augment x1; `40000692` augment x1; `4000068C` augment x1; `400006A1` augment x1; `400006DB` augment x1; `400006A3` augment x1; `40000679` augment x1; `40000674` augment x1; `400006C6` augment x1; `4000067A` augment x1; `40000695` augment x1; `400006BE` augment x1; `400006D6` augment x1; `4000067F` augment x1; `400006B1` augment x1; `400006E3` augment x1; `40000687` augment x1 + `400008E8` [Choice] `40000658` augment x1; `400006E6` augment x1; `400006C0` augment x1; `400006D8` augment x1; `4000069D` augment x1; `400006AB` augment x1; `4000069B` augment x1; `400006C7` augment x1; `4000068B` augment x1; `400006DD` augment x1; `400006A4` augment x1; `400006E7` augment x1; `400006B6` augment x1; `400006C9` augment x1; `40000662` augment x1; `400006AE` augment x1; `400006D1` augment x1; `400006B2` augment x1; `400006A9` augment x1; `4000067E` augment x1 + `400008E6` [Choice] `40000690` augment x1; `4000064C` augment x1; `40000688` augment x1; `400006CD` augment x1; `4000067C` augment x1; `400006DC` augment x1; `4000068E` augment x1; `40000673` augment x1; `400006BB` augment x1; `400006BA` augment x1; `4000069E` augment x1; `400006A0` augment x1; `40000699` augment x1; `400006B8` augment x1; `40000698` augment x1; `40000660` augment x1; `400006E5` augment x1; `400006DF` augment x1; `40000670` augment x1; `400006D3` augment x1 |
| `40000975` | ProtectorLevel49 | ProtectorLevel | Hidden | Never | 57 | ProtectorLevel | 49 | - |  | `400008DD` -> `40000904` [Choice] `40000652` augment x1; `4000064B` augment x1; `40000676` augment x1; `40000664` augment x1; `40000692` augment x1; `4000068C` augment x1; `400006A1` augment x1; `400006DB` augment x1; `400006A3` augment x1; `40000679` augment x1; `40000674` augment x1; `400006C6` augment x1; `4000067A` augment x1; `40000695` augment x1; `400006BE` augment x1; `400006D6` augment x1; `4000067F` augment x1; `400006B1` augment x1; `400006E3` augment x1; `40000687` augment x1 + `400008E8` [Choice] `40000658` augment x1; `400006E6` augment x1; `400006C0` augment x1; `400006D8` augment x1; `4000069D` augment x1; `400006AB` augment x1; `4000069B` augment x1; `400006C7` augment x1; `4000068B` augment x1; `400006DD` augment x1; `400006A4` augment x1; `400006E7` augment x1; `400006B6` augment x1; `400006C9` augment x1; `40000662` augment x1; `400006AE` augment x1; `400006D1` augment x1; `400006B2` augment x1; `400006A9` augment x1; `4000067E` augment x1 + `400008E6` [Choice] `40000690` augment x1; `4000064C` augment x1; `40000688` augment x1; `400006CD` augment x1; `4000067C` augment x1; `400006DC` augment x1; `4000068E` augment x1; `40000673` augment x1; `400006BB` augment x1; `400006BA` augment x1; `4000069E` augment x1; `400006A0` augment x1; `40000699` augment x1; `400006B8` augment x1; `40000698` augment x1; `40000660` augment x1; `400006E5` augment x1; `400006DF` augment x1; `40000670` augment x1; `400006D3` augment x1 |
| `4000098D` | ProtectorLevel50 | ProtectorLevel | Hidden | Never | 58 | ProtectorLevel | 50 | - |  | `40000918` -> `40000915` [Choice] `40000878` mod x1; `4000086D` mod x1; `40000832` mod x1; `4000087A` mod x1; `4000086A` mod x1; `4000084E` mod x1; `40000883` mod x1; `4000088F` mod x1; `400008AE` mod x1; `400008BD` mod x1 + `4000090C` [Choice] `40000855` mod x1; `400008B4` mod x1; `4000082C` mod x1; `40000862` mod x1; `4000085F` mod x1; `40000850` mod x1; `4000084A` mod x1; `400008AD` mod x1; `4000088E` mod x1; `4000085D` mod x1 + `40000917` [Choice] `40000867` mod x1; `4000082B` mod x1; `40000866` mod x1; `40000839` mod x1; `40000880` mod x1; `40000822` mod x1; `4000088D` mod x1; `40000852` mod x1; `40000890` mod x1; `400008B2` mod x1 |
| `40000B35` | ProtectorLevel51 | ProtectorLevel | Hidden | Never | 59 | ProtectorLevel | 51 | - |  | `40000B72` -> `40000BA7` [Grant] `48000D62` Merit x100 |
| `40000B36` | ProtectorLevel52 | ProtectorLevel | Hidden | Never | 60 | ProtectorLevel | 52 | - |  | `40000B73` -> `40000BA7` [Grant] `48000D62` Merit x100 |
| `40000B37` | ProtectorLevel53 | ProtectorLevel | Hidden | Never | 61 | ProtectorLevel | 53 | - |  | `40000B74` -> `40000BA7` [Grant] `48000D62` Merit x100 |
| `40000B38` | ProtectorLevel54 | ProtectorLevel | Hidden | Never | 62 | ProtectorLevel | 54 | - |  | `40000B75` -> `40000BA7` [Grant] `48000D62` Merit x100 |
| `40000B39` | ProtectorLevel55 | ProtectorLevel | Hidden | Never | 63 | ProtectorLevel | 55 | - |  | `40000B76` -> `40000BA7` [Grant] `48000D62` Merit x100 |
| `40000B3A` | ProtectorLevel56 | ProtectorLevel | Hidden | Never | 64 | ProtectorLevel | 56 | - |  | `40000B77` -> `40000BA7` [Grant] `48000D62` Merit x100 |
| `40000B3B` | ProtectorLevel57 | ProtectorLevel | Hidden | Never | 65 | ProtectorLevel | 57 | - |  | `40000B78` -> `40000BA7` [Grant] `48000D62` Merit x100 |
| `40000B3C` | ProtectorLevel58 | ProtectorLevel | Hidden | Never | 66 | ProtectorLevel | 58 | - |  | `40000B79` -> `40000BA7` [Grant] `48000D62` Merit x100 |
| `40000B3D` | ProtectorLevel59 | ProtectorLevel | Hidden | Never | 67 | ProtectorLevel | 59 | - |  | `40000B7A` -> `40000BA7` [Grant] `48000D62` Merit x100 |
| `40000B3E` | ProtectorLevel60 | ProtectorLevel | Hidden | Never | 68 | ProtectorLevel | 60 | - |  | `40000B7B` -> `40000BA7` [Grant] `48000D62` Merit x100 |
| `40000B3F` | ProtectorLevel61 | ProtectorLevel | Hidden | Never | 69 | ProtectorLevel | 61 | - |  | `40000B7C` -> `40000BA7` [Grant] `48000D62` Merit x100 |
| `40000B40` | ProtectorLevel62 | ProtectorLevel | Hidden | Never | 70 | ProtectorLevel | 62 | - |  | `40000B7D` -> `40000BA7` [Grant] `48000D62` Merit x100 |
| `40000B41` | ProtectorLevel63 | ProtectorLevel | Hidden | Never | 71 | ProtectorLevel | 63 | - |  | `40000B7E` -> `40000BA7` [Grant] `48000D62` Merit x100 |
| `40000B42` | ProtectorLevel64 | ProtectorLevel | Hidden | Never | 72 | ProtectorLevel | 64 | - |  | `40000B7F` -> `40000BA7` [Grant] `48000D62` Merit x100 |
| `40000B43` | ProtectorLevel65 | ProtectorLevel | Hidden | Never | 73 | ProtectorLevel | 65 | - |  | `40000B80` -> `40000BA7` [Grant] `48000D62` Merit x100 |
| `40000B44` | ProtectorLevel66 | ProtectorLevel | Hidden | Never | 74 | ProtectorLevel | 66 | - |  | `40000B81` -> `40000BA7` [Grant] `48000D62` Merit x100 |
| `40000B45` | ProtectorLevel67 | ProtectorLevel | Hidden | Never | 75 | ProtectorLevel | 67 | - |  | `40000B82` -> `40000BA7` [Grant] `48000D62` Merit x100 |
| `40000B46` | ProtectorLevel68 | ProtectorLevel | Hidden | Never | 76 | ProtectorLevel | 68 | - |  | `40000B83` -> `40000BA7` [Grant] `48000D62` Merit x100 |
| `40000B47` | ProtectorLevel69 | ProtectorLevel | Hidden | Never | 77 | ProtectorLevel | 69 | - |  | `40000B84` -> `40000BA7` [Grant] `48000D62` Merit x100 |
| `40000B48` | ProtectorLevel70 | ProtectorLevel | Hidden | Never | 78 | ProtectorLevel | 70 | - |  | `40000B85` -> `40000BA7` [Grant] `48000D62` Merit x100 |
| `40000B49` | ProtectorLevel71 | ProtectorLevel | Hidden | Never | 79 | ProtectorLevel | 71 | - |  | `40000B86` -> `40000BA7` [Grant] `48000D62` Merit x100 |
| `40000B4A` | ProtectorLevel72 | ProtectorLevel | Hidden | Never | 80 | ProtectorLevel | 72 | - |  | `40000B87` -> `40000BA7` [Grant] `48000D62` Merit x100 |
| `40000B4B` | ProtectorLevel73 | ProtectorLevel | Hidden | Never | 81 | ProtectorLevel | 73 | - |  | `40000B88` -> `40000BA7` [Grant] `48000D62` Merit x100 |
| `40000B4C` | ProtectorLevel74 | ProtectorLevel | Hidden | Never | 82 | ProtectorLevel | 74 | - |  | `40000B89` -> `40000BA7` [Grant] `48000D62` Merit x100 |
| `40000B4D` | ProtectorLevel75 | ProtectorLevel | Hidden | Never | 83 | ProtectorLevel | 75 | - |  | `40000B8A` -> `40000BA7` [Grant] `48000D62` Merit x100 |
| `40000B4E` | ProtectorLevel76 | ProtectorLevel | Hidden | Never | 84 | ProtectorLevel | 76 | - |  | `40000B8B` -> `40000BA7` [Grant] `48000D62` Merit x100 |
| `40000B4F` | ProtectorLevel77 | ProtectorLevel | Hidden | Never | 85 | ProtectorLevel | 77 | - |  | `40000B8C` -> `40000BA7` [Grant] `48000D62` Merit x100 |
| `40000B50` | ProtectorLevel78 | ProtectorLevel | Hidden | Never | 86 | ProtectorLevel | 78 | - |  | `40000B8D` -> `40000BA7` [Grant] `48000D62` Merit x100 |
| `40000B51` | ProtectorLevel79 | ProtectorLevel | Hidden | Never | 87 | ProtectorLevel | 79 | - |  | `40000B8E` -> `40000BA7` [Grant] `48000D62` Merit x100 |
| `40000B52` | ProtectorLevel80 | ProtectorLevel | Hidden | Never | 88 | ProtectorLevel | 80 | - |  | `40000B8F` -> `40000BA7` [Grant] `48000D62` Merit x100 |
| `40000B53` | ProtectorLevel81 | ProtectorLevel | Hidden | Never | 89 | ProtectorLevel | 81 | - |  | `40000B90` -> `40000BA7` [Grant] `48000D62` Merit x100 |
| `40000B54` | ProtectorLevel82 | ProtectorLevel | Hidden | Never | 90 | ProtectorLevel | 82 | - |  | `40000B91` -> `40000BA7` [Grant] `48000D62` Merit x100 |
| `40000B55` | ProtectorLevel83 | ProtectorLevel | Hidden | Never | 91 | ProtectorLevel | 83 | - |  | `40000B92` -> `40000BA7` [Grant] `48000D62` Merit x100 |
| `40000B56` | ProtectorLevel84 | ProtectorLevel | Hidden | Never | 92 | ProtectorLevel | 84 | - |  | `40000B93` -> `40000BA7` [Grant] `48000D62` Merit x100 |
| `40000B57` | ProtectorLevel85 | ProtectorLevel | Hidden | Never | 93 | ProtectorLevel | 85 | - |  | `40000B94` -> `40000BA7` [Grant] `48000D62` Merit x100 |
| `40000B58` | ProtectorLevel86 | ProtectorLevel | Hidden | Never | 94 | ProtectorLevel | 86 | - |  | `40000B95` -> `40000BA7` [Grant] `48000D62` Merit x100 |
| `40000B59` | ProtectorLevel87 | ProtectorLevel | Hidden | Never | 95 | ProtectorLevel | 87 | - |  | `40000B96` -> `40000BA7` [Grant] `48000D62` Merit x100 |
| `40000B5A` | ProtectorLevel88 | ProtectorLevel | Hidden | Never | 96 | ProtectorLevel | 88 | - |  | `40000B97` -> `40000BA7` [Grant] `48000D62` Merit x100 |
| `40000B5B` | ProtectorLevel89 | ProtectorLevel | Hidden | Never | 97 | ProtectorLevel | 89 | - |  | `40000B98` -> `40000BA7` [Grant] `48000D62` Merit x100 |
| `40000B5C` | ProtectorLevel90 | ProtectorLevel | Hidden | Never | 98 | ProtectorLevel | 90 | - |  | `40000B99` -> `40000BA7` [Grant] `48000D62` Merit x100 |
| `40000B5D` | ProtectorLevel91 | ProtectorLevel | Hidden | Never | 99 | ProtectorLevel | 91 | - |  | `40000B9A` -> `40000BA7` [Grant] `48000D62` Merit x100 |
| `40000B5E` | ProtectorLevel92 | ProtectorLevel | Hidden | Never | 100 | ProtectorLevel | 92 | - |  | `40000B9B` -> `40000BA7` [Grant] `48000D62` Merit x100 |
| `40000B5F` | ProtectorLevel93 | ProtectorLevel | Hidden | Never | 101 | ProtectorLevel | 93 | - |  | `40000B9C` -> `40000BA7` [Grant] `48000D62` Merit x100 |
| `40000B60` | ProtectorLevel94 | ProtectorLevel | Hidden | Never | 102 | ProtectorLevel | 94 | - |  | `40000B9D` -> `40000BA7` [Grant] `48000D62` Merit x100 |
| `40000B61` | ProtectorLevel95 | ProtectorLevel | Hidden | Never | 103 | ProtectorLevel | 95 | - |  | `40000B9E` -> `40000BA7` [Grant] `48000D62` Merit x100 |
| `40000B62` | ProtectorLevel96 | ProtectorLevel | Hidden | Never | 104 | ProtectorLevel | 96 | - |  | `40000B9F` -> `40000BA7` [Grant] `48000D62` Merit x100 |
| `40000B63` | ProtectorLevel97 | ProtectorLevel | Hidden | Never | 105 | ProtectorLevel | 97 | - |  | `40000BA0` -> `40000BA7` [Grant] `48000D62` Merit x100 |
| `40000B64` | ProtectorLevel98 | ProtectorLevel | Hidden | Never | 106 | ProtectorLevel | 98 | - |  | `40000BA1` -> `40000BA7` [Grant] `48000D62` Merit x100 |
| `40000B65` | ProtectorLevel99 | ProtectorLevel | Hidden | Never | 107 | ProtectorLevel | 99 | - |  | `40000BA2` -> `40000BA7` [Grant] `48000D62` Merit x100 |
| `40000B66` | ProtectorLevel100 | ProtectorLevel | Hidden | Never | 108 | ProtectorLevel | 100 | - |  | `40000BA3` -> `40000BA7` [Grant] `48000D62` Merit x100 |
| `400009B1` | InitiateoftheConstruct | ProtectorLevel | Visible | Never | 109 | ProtectorLevel | 10 | - |  | `400009AE` -> `400009AD` [Grant] `48000D62` Merit x500; `48000D61` CrisisCoins x50; `40000A9D` icon x1 |
| `400009A5` | SoldieroftheConstruct | ProtectorLevel | Visible | Never | 110 | ProtectorLevel | 20 | - |  | `400009B2` -> `400009A9` [Grant] `48000D62` Merit x1000; `48000D61` CrisisCoins x100; `40000AA1` icon x1 |
| `400009AB` | LieutenantoftheConstruct | ProtectorLevel | Visible | Never | 111 | ProtectorLevel | 30 | - |  | `400009A7` -> `400009A6` [Grant] `48000D62` Merit x1500; `48000D61` CrisisCoins x150; `40000AA0` icon x1 |
| `400009AF` | ChampionoftheConstruct | ProtectorLevel | Visible | Never | 112 | ProtectorLevel | 40 | - |  | `400009AC` -> `400009B0` [Grant] `48000D62` Merit x2000; `48000D61` CrisisCoins x200; `40000A9F` icon x1 |
| `400009A4` | OnewiththeConstruct | ProtectorLevel | Visible | Never | 113 | ProtectorLevel | 50 | - |  | `400009AA` -> `400009A8` [Grant] `48000D62` Merit x2500; `48000D61` CrisisCoins x250; `40000A9E` icon x1 |
| `40000D72` | AquamanProtectorIcon | ChampionLevel | Hidden | Never | 123 | ChampionLevel | 20 | - | a27=44 | `40000D73` -> `40000D76` [AutoGrant] `40000D75` icon x1 |
| `40000DAA` | AtrocitusProtectorIcon | ChampionLevel | Hidden | Never | 124 | ChampionLevel | 20 | - | a27=33 | `40000DDD` -> `40000E4B` [AutoGrant] `40000E35` icon x1 |
| `40000DA9` | BatmanProtectorIcon | ChampionLevel | Hidden | Never | 125 | ChampionLevel | 20 | - | a27=11 | `40000DDC` -> `40000E53` [AutoGrant] `40000E2C` icon x1 |
| `40000DA8` | BatmanGaslightProtectorIcon | ChampionLevel | Hidden | Never | 126 | ChampionLevel | 20 | - | a27=5 | `40000DDB` -> `40000E0E` [AutoGrant] `40000E42` icon x1 |
| `40000DA7` | BatmanNightmareProtectorIcon | ChampionLevel | Hidden | Never | 127 | ChampionLevel | 20 | - | a27=6 | `40000DDA` -> `40000DF1` [AutoGrant] `40000E3D` icon x1 |
| `40000DA6` | BlueBeetleProtectorIcon | ChampionLevel | Hidden | Never | 128 | ChampionLevel | 20 | - | a27=45 | `40000DD9` -> `40000E43` [AutoGrant] `40000E20` icon x1 |
| `40000DA5` | CatwomanProtectorIcon | ChampionLevel | Hidden | Never | 129 | ChampionLevel | 20 | - | a27=10 | `40000DD8` -> `40000E31` [AutoGrant] `40000E12` icon x1 |
| `40000DA4` | CatwomanGaslightProtectorIcon | ChampionLevel | Hidden | Never | 130 | ChampionLevel | 20 | - | a27=9 | `40000DD7` -> `40000DF7` [AutoGrant] `40000E38` icon x1 |
| `40000DA3` | CatwomanNightmareProtectorIcon | ChampionLevel | Hidden | Never | 131 | ChampionLevel | 20 | - | a27=70 | `40000DD6` -> `40000E2E` [AutoGrant] `40000E3C` icon x1 |
| `40000DA2` | CyborgProtectorIcon | ChampionLevel | Hidden | Never | 132 | ChampionLevel | 20 | - | a27=22 | `40000DD5` -> `40000E1B` [AutoGrant] `40000E4D` icon x1 |
| `40000DA1` | DeadshotProtectorIcon | ChampionLevel | Hidden | Never | 133 | ChampionLevel | 20 | - | a27=78 | `40000DD4` -> `40000E05` [AutoGrant] `40000E30` icon x1 |
| `40000DA0` | DeathstrokeProtectorIcon | ChampionLevel | Hidden | Never | 134 | ChampionLevel | 20 | - | a27=58 | `40000DD3` -> `40000E2B` [AutoGrant] `40000E33` icon x1 |
| `40000D9F` | DexStarrProtectorIcon | ChampionLevel | Hidden | Never | 135 | ChampionLevel | 20 | - | a27=104 | `40000DD2` -> `40000E1C` [AutoGrant] `40000E2A` icon x1 |
| `40000D9E` | DoomsdayProtectorIcon | ChampionLevel | Hidden | Never | 136 | ChampionLevel | 20 | - | a27=1 | `40000DD1` -> `40000E4C` [AutoGrant] `40000E47` icon x1 |
| `40000D9D` | FlashProtectorIcon | ChampionLevel | Hidden | Never | 137 | ChampionLevel | 20 | - | a27=16 | `40000DD0` -> `40000E09` [AutoGrant] `40000DFF` icon x1 |
| `40000D9C` | GreenArrowProtectorIcon | ChampionLevel | Hidden | Never | 138 | ChampionLevel | 20 | - | a27=24 | `40000DCF` -> `40000E22` [AutoGrant] `40000E3B` icon x1 |
| `40000D9B` | GreenLanternProtectorIcon | ChampionLevel | Hidden | Never | 139 | ChampionLevel | 20 | - | a27=15 | `40000DCE` -> `40000E04` [AutoGrant] `40000E49` icon x1 |
| `40000D9A` | GreenLanternArcaneProtectorIcon | ChampionLevel | Hidden | Never | 140 | ChampionLevel | 20 | - | a27=28 | `40000DCD` -> `40000E0A` [AutoGrant] `40000E32` icon x1 |
| `40000D99` | GreenLanternAtomicProtectorIcon | ChampionLevel | Hidden | Never | 141 | ChampionLevel | 20 | - | a27=35 | `40000DCC` -> `40000E1E` [AutoGrant] `40000DF5` icon x1 |
| `40000D98` | HarleyQuinnProtectorIcon | ChampionLevel | Hidden | Never | 142 | ChampionLevel | 20 | - | a27=8 | `40000DCB` -> `40000E25` [AutoGrant] `40000E11` icon x1 |
| `40000D97` | HarleyQuinnArcaneProtectorIcon | ChampionLevel | Hidden | Never | 143 | ChampionLevel | 20 | - | a27=72 | `40000DCA` -> `40000DF8` [AutoGrant] `40000E54` icon x1 |
| `40000D96` | HawkgirlProtectorIcon | ChampionLevel | Hidden | Never | 144 | ChampionLevel | 20 | - | a27=61 | `40000DC9` -> `40000E4A` [AutoGrant] `40000E15` icon x1 |
| `40000D95` | HuntressProtectorIcon | ChampionLevel | Hidden | Never | 145 | ChampionLevel | 20 | - | a27=68 | `40000DC8` -> `40000E2F` [AutoGrant] `40000DF0` icon x1 |
| `40000D94` | JokerProtectorIcon | ChampionLevel | Hidden | Never | 146 | ChampionLevel | 20 | - | a27=4 | `40000DC7` -> `40000E0F` [AutoGrant] `40000DF4` icon x1 |
| `40000D93` | JokerAtomicProtectorIcon | ChampionLevel | Hidden | Never | 147 | ChampionLevel | 20 | - | a27=48 | `40000DC6` -> `40000E23` [AutoGrant] `40000E52` icon x1 |
| `40000D92` | JokerGaslightProtectorIcon | ChampionLevel | Hidden | Never | 148 | ChampionLevel | 20 | - | a27=19 | `40000DC5` -> `40000DF6` [AutoGrant] `40000E27` icon x1 |
| `40000D91` | KatanaProtectorIcon | ChampionLevel | Hidden | Never | 149 | ChampionLevel | 20 | - | a27=69 | `40000DC4` -> `40000E36` [AutoGrant] `40000E24` icon x1 |
| `40000D90` | KryptoProtectorIcon | ChampionLevel | Hidden | Never | 150 | ChampionLevel | 20 | - | a27=46 | `40000DC3` -> `40000E19` [AutoGrant] `40000E18` icon x1 |
| `40000D8F` | LexLuthorProtectorIcon | ChampionLevel | Hidden | Never | 151 | ChampionLevel | 20 | - | a27=23 | `40000DC2` -> `40000E3F` [AutoGrant] `40000E40` icon x1 |
| `40000D8E` | PoisonIvyProtectorIcon | ChampionLevel | Hidden | Never | 152 | ChampionLevel | 20 | - | a27=2 | `40000DC1` -> `40000E0D` [AutoGrant] `40000DFD` icon x1 |
| `40000D8D` | PoisonIvyAtomicProtectorIcon | ChampionLevel | Hidden | Never | 153 | ChampionLevel | 20 | - | a27=26 | `40000DC0` -> `40000E4F` [AutoGrant] `40000DFB` icon x1 |
| `40000D8C` | RavenProtectorIcon | ChampionLevel | Hidden | Never | 154 | ChampionLevel | 20 | - | a27=31 | `40000DBF` -> `40000DF3` [AutoGrant] `40000E03` icon x1 |
| `40000D8B` | RobinProtectorIcon | ChampionLevel | Hidden | Never | 155 | ChampionLevel | 20 | - | a27=20 | `40000DBE` -> `40000E2D` [AutoGrant] `40000DFA` icon x1 |
| `40000D8A` | RobinNightmareProtectorIcon | ChampionLevel | Hidden | Never | 156 | ChampionLevel | 20 | - | a27=47 | `40000DBD` -> `40000E1A` [AutoGrant] `40000E39` icon x1 |
| `40000D89` | ShazamProtectorIcon | ChampionLevel | Hidden | Never | 157 | ChampionLevel | 20 | - | a27=17 | `40000DBC` -> `40000E13` [AutoGrant] `40000E17` icon x1 |
| `40000D88` | SinestroProtectorIcon | ChampionLevel | Hidden | Never | 158 | ChampionLevel | 20 | - | a27=13 | `40000DBB` -> `40000E00` [AutoGrant] `40000E01` icon x1 |
| `40000D87` | SolomonGrundyProtectorIcon | ChampionLevel | Hidden | Never | 159 | ChampionLevel | 20 | - | a27=76 | `40000DBA` -> `40000DF2` [AutoGrant] `40000E1D` icon x1 |
| `40000D86` | StargirlProtectorIcon | ChampionLevel | Hidden | Never | 160 | ChampionLevel | 20 | - | a27=57 | `40000DB9` -> `40000DFC` [AutoGrant] `40000E45` icon x1 |
| `40000D85` | StarroProtectorIcon | ChampionLevel | Hidden | Never | 161 | ChampionLevel | 20 | - | a27=36 | `40000DB8` -> `40000DFE` [AutoGrant] `40000E37` icon x1 |
| `40000D84` | StarSapphireProtectorIcon | ChampionLevel | Hidden | Never | 162 | ChampionLevel | 20 | - | a27=14 | `40000DB7` -> `40000E14` [AutoGrant] `40000E07` icon x1 |
| `40000D83` | SupergirlProtectorIcon | ChampionLevel | Hidden | Never | 163 | ChampionLevel | 20 | - | a27=38 | `40000DB6` -> `40000E06` [AutoGrant] `40000E48` icon x1 |
| `40000D82` | SupergirlArcaneProtectorIcon | ChampionLevel | Hidden | Never | 164 | ChampionLevel | 20 | - | a27=49 | `40000DB5` -> `40000E3A` [AutoGrant] `40000DF9` icon x1 |
| `40000D81` | SupermanProtectorIcon | ChampionLevel | Hidden | Never | 165 | ChampionLevel | 20 | - | a27=3 | `40000DB4` -> `40000E0C` [AutoGrant] `40000E1F` icon x1 |
| `40000D80` | SupermanMechaProtectorIcon | ChampionLevel | Hidden | Never | 166 | ChampionLevel | 20 | - | a27=40 | `40000DB3` -> `40000E21` [AutoGrant] `40000E16` icon x1 |
| `40000D7F` | SupermanNightmareProtectorIcon | ChampionLevel | Hidden | Never | 167 | ChampionLevel | 20 | - | a27=30 | `40000DB2` -> `40000E46` [AutoGrant] `40000E4E` icon x1 |
| `40000D7E` | SwampThingProtectorIcon | ChampionLevel | Hidden | Never | 168 | ChampionLevel | 20 | - | a27=29 | `40000DB1` -> `40000E50` [AutoGrant] `40000E34` icon x1 |
| `40000D7D` | WonderWomanProtectorIcon | ChampionLevel | Hidden | Never | 169 | ChampionLevel | 20 | - | a27=12 | `40000DB0` -> `40000E02` [AutoGrant] `40000E3E` icon x1 |
| `40000D7C` | WonderWomanAtomicProtectorIcon | ChampionLevel | Hidden | Never | 170 | ChampionLevel | 20 | - | a27=25 | `40000DAF` -> `40000E10` [AutoGrant] `40000E41` icon x1 |
| `40000D7B` | WonderWomanMechaProtectorIcon | ChampionLevel | Hidden | Never | 171 | ChampionLevel | 20 | - | a27=39 | `40000DAE` -> `40000E29` [AutoGrant] `40000E0B` icon x1 |
| `40000D7A` | ZatannaProtectorIcon | ChampionLevel | Hidden | Never | 172 | ChampionLevel | 20 | - | a27=7 | `40000DAD` -> `40000E08` [AutoGrant] `40000E51` icon x1 |
| `40000D79` | ZatannaArcaneProtectorIcon | ChampionLevel | Hidden | Never | 173 | ChampionLevel | 20 | - | a27=27 | `40000DAC` -> `40000E26` [AutoGrant] `40000E44` icon x1 |
| `40000D78` | ZodProtectorIcon | ChampionLevel | Hidden | Never | 174 | ChampionLevel | 20 | - | a27=51 | `40000DAB` -> `40000E28` [AutoGrant] `40000E55` icon x1 |

### 3.2 Reward sets and reward groups [C]

Reward set (`0x49`): `0x10000A1F` = array of `0x10000A18` {`0x10000A1B` reward group `0x40`} (134 sets x 1 group,
45 x 3 groups); `0x10000D90` quality = **RewardQualityType** 1 Gold, 2 Silver, 3 Bronze (7 sets) [P: values and the
login sets' names agree]; `0x10000A1C` 100 / 250 (96 sets; G: weight); `0x10000D96` bool (2); `0x10000DA1` icon (1);
`0x10000D8F` name (only the 5 login sets). Reward group (`0x49`): `0x10000A1D` = 30 x `0x10000A17` {`0x10000A36`
quantity, `0x10000A1A` item `0x40` DID **or** `0x10000AB7` currency/XP record `0x48`}; `0x10000A4D` **RewardBestowalType**
1 Choice (12 groups), 2 Grant (33), 3 AutoGrant (52) [P: matches the content: Choice groups hold 10 or 20 augments /
mods to pick from, AutoGrant the champion icons]. Shapes: 52 AutoGrant x1 item, 21 Grant x1, 7 Grant x2, 5 Grant x3,
6 Choice x1, 3 Choice x10, 3 Choice x20 (filled slots).

How they reach the client: `0x2125` elements `{set, source, 0, item, quantity, bestowal, u64 instance, icon, StringInfo}`
one element per item, consecutive elements with the same set = one set (`reward_re.txt`); claim C->S `0x2128`
`{set, choice, source, u64 instance, u32list items, u32list quantities, u32list bestowals}`; for a Choice group the
`choice` DID is the picked item [P]. Source type is hard-coded 1 Achievement in `0x2125` and 2 LoginReward in `0x2197`
(same element layout, ser `0x846680`) [C].

All 179 reward sets with their groups and items:

| Reward set (0x40) | Quality `D90` | `A1C` | `D96` | Icon `DA1` | Name `D8F` | Groups -> items | Used by |
|---|---|---|---|---|---|---|---|
| `400008DD` | - | 100 | - | - | - | `40000904` [Choice] `40000652` augment x1; `4000064B` augment x1; `40000676` augment x1; `40000664` augment x1; `40000692` augment x1; `4000068C` augment x1; `400006A1` augment x1; `400006DB` augment x1; `400006A3` augment x1; `40000679` augment x1; `40000674` augment x1; `400006C6` augment x1; `4000067A` augment x1; `40000695` augment x1; `400006BE` augment x1; `400006D6` augment x1; `4000067F` augment x1; `400006B1` augment x1; `400006E3` augment x1; `40000687` augment x1 + `400008E8` [Choice] `40000658` augment x1; `400006E6` augment x1; `400006C0` augment x1; `400006D8` augment x1; `4000069D` augment x1; `400006AB` augment x1; `4000069B` augment x1; `400006C7` augment x1; `4000068B` augment x1; `400006DD` augment x1; `400006A4` augment x1; `400006E7` augment x1; `400006B6` augment x1; `400006C9` augment x1; `40000662` augment x1; `400006AE` augment x1; `400006D1` augment x1; `400006B2` augment x1; `400006A9` augment x1; `4000067E` augment x1 + `400008E6` [Choice] `40000690` augment x1; `4000064C` augment x1; `40000688` augment x1; `400006CD` augment x1; `4000067C` augment x1; `400006DC` augment x1; `4000068E` augment x1; `40000673` augment x1; `400006BB` augment x1; `400006BA` augment x1; `4000069E` augment x1; `400006A0` augment x1; `40000699` augment x1; `400006B8` augment x1; `40000698` augment x1; `40000660` augment x1; `400006E5` augment x1; `400006DF` augment x1; `40000670` augment x1; `400006D3` augment x1 | 1 ach. |
| `400008DE` | - | 100 | - | - | - | `40000915` [Choice] `40000878` mod x1; `4000086D` mod x1; `40000832` mod x1; `4000087A` mod x1; `4000086A` mod x1; `4000084E` mod x1; `40000883` mod x1; `4000088F` mod x1; `400008AE` mod x1; `400008BD` mod x1 + `4000090C` [Choice] `40000855` mod x1; `400008B4` mod x1; `4000082C` mod x1; `40000862` mod x1; `4000085F` mod x1; `40000850` mod x1; `4000084A` mod x1; `400008AD` mod x1; `4000088E` mod x1; `4000085D` mod x1 + `40000917` [Choice] `40000867` mod x1; `4000082B` mod x1; `40000866` mod x1; `40000839` mod x1; `40000880` mod x1; `40000822` mod x1; `4000088D` mod x1; `40000852` mod x1; `40000890` mod x1; `400008B2` mod x1 | 1 ach. |
| `400008DF` | - | 100 | - | - | - | `40000904` [Choice] `40000652` augment x1; `4000064B` augment x1; `40000676` augment x1; `40000664` augment x1; `40000692` augment x1; `4000068C` augment x1; `400006A1` augment x1; `400006DB` augment x1; `400006A3` augment x1; `40000679` augment x1; `40000674` augment x1; `400006C6` augment x1; `4000067A` augment x1; `40000695` augment x1; `400006BE` augment x1; `400006D6` augment x1; `4000067F` augment x1; `400006B1` augment x1; `400006E3` augment x1; `40000687` augment x1 + `400008E8` [Choice] `40000658` augment x1; `400006E6` augment x1; `400006C0` augment x1; `400006D8` augment x1; `4000069D` augment x1; `400006AB` augment x1; `4000069B` augment x1; `400006C7` augment x1; `4000068B` augment x1; `400006DD` augment x1; `400006A4` augment x1; `400006E7` augment x1; `400006B6` augment x1; `400006C9` augment x1; `40000662` augment x1; `400006AE` augment x1; `400006D1` augment x1; `400006B2` augment x1; `400006A9` augment x1; `4000067E` augment x1 + `400008E6` [Choice] `40000690` augment x1; `4000064C` augment x1; `40000688` augment x1; `400006CD` augment x1; `4000067C` augment x1; `400006DC` augment x1; `4000068E` augment x1; `40000673` augment x1; `400006BB` augment x1; `400006BA` augment x1; `4000069E` augment x1; `400006A0` augment x1; `40000699` augment x1; `400006B8` augment x1; `40000698` augment x1; `40000660` augment x1; `400006E5` augment x1; `400006DF` augment x1; `40000670` augment x1; `400006D3` augment x1 | 1 ach. |
| `400008E0` | - | 100 | - | - | - | `40000904` [Choice] `40000652` augment x1; `4000064B` augment x1; `40000676` augment x1; `40000664` augment x1; `40000692` augment x1; `4000068C` augment x1; `400006A1` augment x1; `400006DB` augment x1; `400006A3` augment x1; `40000679` augment x1; `40000674` augment x1; `400006C6` augment x1; `4000067A` augment x1; `40000695` augment x1; `400006BE` augment x1; `400006D6` augment x1; `4000067F` augment x1; `400006B1` augment x1; `400006E3` augment x1; `40000687` augment x1 + `400008E8` [Choice] `40000658` augment x1; `400006E6` augment x1; `400006C0` augment x1; `400006D8` augment x1; `4000069D` augment x1; `400006AB` augment x1; `4000069B` augment x1; `400006C7` augment x1; `4000068B` augment x1; `400006DD` augment x1; `400006A4` augment x1; `400006E7` augment x1; `400006B6` augment x1; `400006C9` augment x1; `40000662` augment x1; `400006AE` augment x1; `400006D1` augment x1; `400006B2` augment x1; `400006A9` augment x1; `4000067E` augment x1 + `400008E6` [Choice] `40000690` augment x1; `4000064C` augment x1; `40000688` augment x1; `400006CD` augment x1; `4000067C` augment x1; `400006DC` augment x1; `4000068E` augment x1; `40000673` augment x1; `400006BB` augment x1; `400006BA` augment x1; `4000069E` augment x1; `400006A0` augment x1; `40000699` augment x1; `400006B8` augment x1; `40000698` augment x1; `40000660` augment x1; `400006E5` augment x1; `400006DF` augment x1; `40000670` augment x1; `400006D3` augment x1 | 1 ach. |
| `400008E2` | - | 100 | - | - | - | `40000904` [Choice] `40000652` augment x1; `4000064B` augment x1; `40000676` augment x1; `40000664` augment x1; `40000692` augment x1; `4000068C` augment x1; `400006A1` augment x1; `400006DB` augment x1; `400006A3` augment x1; `40000679` augment x1; `40000674` augment x1; `400006C6` augment x1; `4000067A` augment x1; `40000695` augment x1; `400006BE` augment x1; `400006D6` augment x1; `4000067F` augment x1; `400006B1` augment x1; `400006E3` augment x1; `40000687` augment x1 + `400008E8` [Choice] `40000658` augment x1; `400006E6` augment x1; `400006C0` augment x1; `400006D8` augment x1; `4000069D` augment x1; `400006AB` augment x1; `4000069B` augment x1; `400006C7` augment x1; `4000068B` augment x1; `400006DD` augment x1; `400006A4` augment x1; `400006E7` augment x1; `400006B6` augment x1; `400006C9` augment x1; `40000662` augment x1; `400006AE` augment x1; `400006D1` augment x1; `400006B2` augment x1; `400006A9` augment x1; `4000067E` augment x1 + `400008E6` [Choice] `40000690` augment x1; `4000064C` augment x1; `40000688` augment x1; `400006CD` augment x1; `4000067C` augment x1; `400006DC` augment x1; `4000068E` augment x1; `40000673` augment x1; `400006BB` augment x1; `400006BA` augment x1; `4000069E` augment x1; `400006A0` augment x1; `40000699` augment x1; `400006B8` augment x1; `40000698` augment x1; `40000660` augment x1; `400006E5` augment x1; `400006DF` augment x1; `40000670` augment x1; `400006D3` augment x1 | 1 ach. |
| `400008E3` | - | 100 | - | - | - | `40000904` [Choice] `40000652` augment x1; `4000064B` augment x1; `40000676` augment x1; `40000664` augment x1; `40000692` augment x1; `4000068C` augment x1; `400006A1` augment x1; `400006DB` augment x1; `400006A3` augment x1; `40000679` augment x1; `40000674` augment x1; `400006C6` augment x1; `4000067A` augment x1; `40000695` augment x1; `400006BE` augment x1; `400006D6` augment x1; `4000067F` augment x1; `400006B1` augment x1; `400006E3` augment x1; `40000687` augment x1 + `400008E8` [Choice] `40000658` augment x1; `400006E6` augment x1; `400006C0` augment x1; `400006D8` augment x1; `4000069D` augment x1; `400006AB` augment x1; `4000069B` augment x1; `400006C7` augment x1; `4000068B` augment x1; `400006DD` augment x1; `400006A4` augment x1; `400006E7` augment x1; `400006B6` augment x1; `400006C9` augment x1; `40000662` augment x1; `400006AE` augment x1; `400006D1` augment x1; `400006B2` augment x1; `400006A9` augment x1; `4000067E` augment x1 + `400008E6` [Choice] `40000690` augment x1; `4000064C` augment x1; `40000688` augment x1; `400006CD` augment x1; `4000067C` augment x1; `400006DC` augment x1; `4000068E` augment x1; `40000673` augment x1; `400006BB` augment x1; `400006BA` augment x1; `4000069E` augment x1; `400006A0` augment x1; `40000699` augment x1; `400006B8` augment x1; `40000698` augment x1; `40000660` augment x1; `400006E5` augment x1; `400006DF` augment x1; `40000670` augment x1; `400006D3` augment x1 | 1 ach. |
| `400008E4` | - | 100 | - | - | - | `40000904` [Choice] `40000652` augment x1; `4000064B` augment x1; `40000676` augment x1; `40000664` augment x1; `40000692` augment x1; `4000068C` augment x1; `400006A1` augment x1; `400006DB` augment x1; `400006A3` augment x1; `40000679` augment x1; `40000674` augment x1; `400006C6` augment x1; `4000067A` augment x1; `40000695` augment x1; `400006BE` augment x1; `400006D6` augment x1; `4000067F` augment x1; `400006B1` augment x1; `400006E3` augment x1; `40000687` augment x1 + `400008E8` [Choice] `40000658` augment x1; `400006E6` augment x1; `400006C0` augment x1; `400006D8` augment x1; `4000069D` augment x1; `400006AB` augment x1; `4000069B` augment x1; `400006C7` augment x1; `4000068B` augment x1; `400006DD` augment x1; `400006A4` augment x1; `400006E7` augment x1; `400006B6` augment x1; `400006C9` augment x1; `40000662` augment x1; `400006AE` augment x1; `400006D1` augment x1; `400006B2` augment x1; `400006A9` augment x1; `4000067E` augment x1 + `400008E6` [Choice] `40000690` augment x1; `4000064C` augment x1; `40000688` augment x1; `400006CD` augment x1; `4000067C` augment x1; `400006DC` augment x1; `4000068E` augment x1; `40000673` augment x1; `400006BB` augment x1; `400006BA` augment x1; `4000069E` augment x1; `400006A0` augment x1; `40000699` augment x1; `400006B8` augment x1; `40000698` augment x1; `40000660` augment x1; `400006E5` augment x1; `400006DF` augment x1; `40000670` augment x1; `400006D3` augment x1 | 1 ach. |
| `400008E5` | - | 100 | - | - | - | `40000915` [Choice] `40000878` mod x1; `4000086D` mod x1; `40000832` mod x1; `4000087A` mod x1; `4000086A` mod x1; `4000084E` mod x1; `40000883` mod x1; `4000088F` mod x1; `400008AE` mod x1; `400008BD` mod x1 + `4000090C` [Choice] `40000855` mod x1; `400008B4` mod x1; `4000082C` mod x1; `40000862` mod x1; `4000085F` mod x1; `40000850` mod x1; `4000084A` mod x1; `400008AD` mod x1; `4000088E` mod x1; `4000085D` mod x1 + `40000917` [Choice] `40000867` mod x1; `4000082B` mod x1; `40000866` mod x1; `40000839` mod x1; `40000880` mod x1; `40000822` mod x1; `4000088D` mod x1; `40000852` mod x1; `40000890` mod x1; `400008B2` mod x1 | 1 ach. |
| `400008E7` | - | 100 | - | - | - | `40000904` [Choice] `40000652` augment x1; `4000064B` augment x1; `40000676` augment x1; `40000664` augment x1; `40000692` augment x1; `4000068C` augment x1; `400006A1` augment x1; `400006DB` augment x1; `400006A3` augment x1; `40000679` augment x1; `40000674` augment x1; `400006C6` augment x1; `4000067A` augment x1; `40000695` augment x1; `400006BE` augment x1; `400006D6` augment x1; `4000067F` augment x1; `400006B1` augment x1; `400006E3` augment x1; `40000687` augment x1 + `400008E8` [Choice] `40000658` augment x1; `400006E6` augment x1; `400006C0` augment x1; `400006D8` augment x1; `4000069D` augment x1; `400006AB` augment x1; `4000069B` augment x1; `400006C7` augment x1; `4000068B` augment x1; `400006DD` augment x1; `400006A4` augment x1; `400006E7` augment x1; `400006B6` augment x1; `400006C9` augment x1; `40000662` augment x1; `400006AE` augment x1; `400006D1` augment x1; `400006B2` augment x1; `400006A9` augment x1; `4000067E` augment x1 + `400008E6` [Choice] `40000690` augment x1; `4000064C` augment x1; `40000688` augment x1; `400006CD` augment x1; `4000067C` augment x1; `400006DC` augment x1; `4000068E` augment x1; `40000673` augment x1; `400006BB` augment x1; `400006BA` augment x1; `4000069E` augment x1; `400006A0` augment x1; `40000699` augment x1; `400006B8` augment x1; `40000698` augment x1; `40000660` augment x1; `400006E5` augment x1; `400006DF` augment x1; `40000670` augment x1; `400006D3` augment x1 | 1 ach. |
| `400008E9` | - | 100 | - | - | - | `40000904` [Choice] `40000652` augment x1; `4000064B` augment x1; `40000676` augment x1; `40000664` augment x1; `40000692` augment x1; `4000068C` augment x1; `400006A1` augment x1; `400006DB` augment x1; `400006A3` augment x1; `40000679` augment x1; `40000674` augment x1; `400006C6` augment x1; `4000067A` augment x1; `40000695` augment x1; `400006BE` augment x1; `400006D6` augment x1; `4000067F` augment x1; `400006B1` augment x1; `400006E3` augment x1; `40000687` augment x1 + `400008E8` [Choice] `40000658` augment x1; `400006E6` augment x1; `400006C0` augment x1; `400006D8` augment x1; `4000069D` augment x1; `400006AB` augment x1; `4000069B` augment x1; `400006C7` augment x1; `4000068B` augment x1; `400006DD` augment x1; `400006A4` augment x1; `400006E7` augment x1; `400006B6` augment x1; `400006C9` augment x1; `40000662` augment x1; `400006AE` augment x1; `400006D1` augment x1; `400006B2` augment x1; `400006A9` augment x1; `4000067E` augment x1 + `400008E6` [Choice] `40000690` augment x1; `4000064C` augment x1; `40000688` augment x1; `400006CD` augment x1; `4000067C` augment x1; `400006DC` augment x1; `4000068E` augment x1; `40000673` augment x1; `400006BB` augment x1; `400006BA` augment x1; `4000069E` augment x1; `400006A0` augment x1; `40000699` augment x1; `400006B8` augment x1; `40000698` augment x1; `40000660` augment x1; `400006E5` augment x1; `400006DF` augment x1; `40000670` augment x1; `400006D3` augment x1 | 1 ach. |
| `400008EA` | - | 100 | - | - | - | `40000915` [Choice] `40000878` mod x1; `4000086D` mod x1; `40000832` mod x1; `4000087A` mod x1; `4000086A` mod x1; `4000084E` mod x1; `40000883` mod x1; `4000088F` mod x1; `400008AE` mod x1; `400008BD` mod x1 + `4000090C` [Choice] `40000855` mod x1; `400008B4` mod x1; `4000082C` mod x1; `40000862` mod x1; `4000085F` mod x1; `40000850` mod x1; `4000084A` mod x1; `400008AD` mod x1; `4000088E` mod x1; `4000085D` mod x1 + `40000917` [Choice] `40000867` mod x1; `4000082B` mod x1; `40000866` mod x1; `40000839` mod x1; `40000880` mod x1; `40000822` mod x1; `4000088D` mod x1; `40000852` mod x1; `40000890` mod x1; `400008B2` mod x1 | 1 ach. |
| `400008EB` | - | 100 | - | - | - | `40000904` [Choice] `40000652` augment x1; `4000064B` augment x1; `40000676` augment x1; `40000664` augment x1; `40000692` augment x1; `4000068C` augment x1; `400006A1` augment x1; `400006DB` augment x1; `400006A3` augment x1; `40000679` augment x1; `40000674` augment x1; `400006C6` augment x1; `4000067A` augment x1; `40000695` augment x1; `400006BE` augment x1; `400006D6` augment x1; `4000067F` augment x1; `400006B1` augment x1; `400006E3` augment x1; `40000687` augment x1 + `400008E8` [Choice] `40000658` augment x1; `400006E6` augment x1; `400006C0` augment x1; `400006D8` augment x1; `4000069D` augment x1; `400006AB` augment x1; `4000069B` augment x1; `400006C7` augment x1; `4000068B` augment x1; `400006DD` augment x1; `400006A4` augment x1; `400006E7` augment x1; `400006B6` augment x1; `400006C9` augment x1; `40000662` augment x1; `400006AE` augment x1; `400006D1` augment x1; `400006B2` augment x1; `400006A9` augment x1; `4000067E` augment x1 + `400008E6` [Choice] `40000690` augment x1; `4000064C` augment x1; `40000688` augment x1; `400006CD` augment x1; `4000067C` augment x1; `400006DC` augment x1; `4000068E` augment x1; `40000673` augment x1; `400006BB` augment x1; `400006BA` augment x1; `4000069E` augment x1; `400006A0` augment x1; `40000699` augment x1; `400006B8` augment x1; `40000698` augment x1; `40000660` augment x1; `400006E5` augment x1; `400006DF` augment x1; `40000670` augment x1; `400006D3` augment x1 | 1 ach. |
| `400008EC` | - | 100 | - | - | - | `40000915` [Choice] `40000878` mod x1; `4000086D` mod x1; `40000832` mod x1; `4000087A` mod x1; `4000086A` mod x1; `4000084E` mod x1; `40000883` mod x1; `4000088F` mod x1; `400008AE` mod x1; `400008BD` mod x1 + `4000090C` [Choice] `40000855` mod x1; `400008B4` mod x1; `4000082C` mod x1; `40000862` mod x1; `4000085F` mod x1; `40000850` mod x1; `4000084A` mod x1; `400008AD` mod x1; `4000088E` mod x1; `4000085D` mod x1 + `40000917` [Choice] `40000867` mod x1; `4000082B` mod x1; `40000866` mod x1; `40000839` mod x1; `40000880` mod x1; `40000822` mod x1; `4000088D` mod x1; `40000852` mod x1; `40000890` mod x1; `400008B2` mod x1 | 1 ach. |
| `400008ED` | - | 100 | - | - | - | `40000915` [Choice] `40000878` mod x1; `4000086D` mod x1; `40000832` mod x1; `4000087A` mod x1; `4000086A` mod x1; `4000084E` mod x1; `40000883` mod x1; `4000088F` mod x1; `400008AE` mod x1; `400008BD` mod x1 + `4000090C` [Choice] `40000855` mod x1; `400008B4` mod x1; `4000082C` mod x1; `40000862` mod x1; `4000085F` mod x1; `40000850` mod x1; `4000084A` mod x1; `400008AD` mod x1; `4000088E` mod x1; `4000085D` mod x1 + `40000917` [Choice] `40000867` mod x1; `4000082B` mod x1; `40000866` mod x1; `40000839` mod x1; `40000880` mod x1; `40000822` mod x1; `4000088D` mod x1; `40000852` mod x1; `40000890` mod x1; `400008B2` mod x1 | 1 ach. |
| `400008EE` | - | 100 | - | - | - | `40000904` [Choice] `40000652` augment x1; `4000064B` augment x1; `40000676` augment x1; `40000664` augment x1; `40000692` augment x1; `4000068C` augment x1; `400006A1` augment x1; `400006DB` augment x1; `400006A3` augment x1; `40000679` augment x1; `40000674` augment x1; `400006C6` augment x1; `4000067A` augment x1; `40000695` augment x1; `400006BE` augment x1; `400006D6` augment x1; `4000067F` augment x1; `400006B1` augment x1; `400006E3` augment x1; `40000687` augment x1 + `400008E8` [Choice] `40000658` augment x1; `400006E6` augment x1; `400006C0` augment x1; `400006D8` augment x1; `4000069D` augment x1; `400006AB` augment x1; `4000069B` augment x1; `400006C7` augment x1; `4000068B` augment x1; `400006DD` augment x1; `400006A4` augment x1; `400006E7` augment x1; `400006B6` augment x1; `400006C9` augment x1; `40000662` augment x1; `400006AE` augment x1; `400006D1` augment x1; `400006B2` augment x1; `400006A9` augment x1; `4000067E` augment x1 + `400008E6` [Choice] `40000690` augment x1; `4000064C` augment x1; `40000688` augment x1; `400006CD` augment x1; `4000067C` augment x1; `400006DC` augment x1; `4000068E` augment x1; `40000673` augment x1; `400006BB` augment x1; `400006BA` augment x1; `4000069E` augment x1; `400006A0` augment x1; `40000699` augment x1; `400006B8` augment x1; `40000698` augment x1; `40000660` augment x1; `400006E5` augment x1; `400006DF` augment x1; `40000670` augment x1; `400006D3` augment x1 | 1 ach. |
| `400008EF` | - | 100 | - | - | - | `40000904` [Choice] `40000652` augment x1; `4000064B` augment x1; `40000676` augment x1; `40000664` augment x1; `40000692` augment x1; `4000068C` augment x1; `400006A1` augment x1; `400006DB` augment x1; `400006A3` augment x1; `40000679` augment x1; `40000674` augment x1; `400006C6` augment x1; `4000067A` augment x1; `40000695` augment x1; `400006BE` augment x1; `400006D6` augment x1; `4000067F` augment x1; `400006B1` augment x1; `400006E3` augment x1; `40000687` augment x1 + `400008E8` [Choice] `40000658` augment x1; `400006E6` augment x1; `400006C0` augment x1; `400006D8` augment x1; `4000069D` augment x1; `400006AB` augment x1; `4000069B` augment x1; `400006C7` augment x1; `4000068B` augment x1; `400006DD` augment x1; `400006A4` augment x1; `400006E7` augment x1; `400006B6` augment x1; `400006C9` augment x1; `40000662` augment x1; `400006AE` augment x1; `400006D1` augment x1; `400006B2` augment x1; `400006A9` augment x1; `4000067E` augment x1 + `400008E6` [Choice] `40000690` augment x1; `4000064C` augment x1; `40000688` augment x1; `400006CD` augment x1; `4000067C` augment x1; `400006DC` augment x1; `4000068E` augment x1; `40000673` augment x1; `400006BB` augment x1; `400006BA` augment x1; `4000069E` augment x1; `400006A0` augment x1; `40000699` augment x1; `400006B8` augment x1; `40000698` augment x1; `40000660` augment x1; `400006E5` augment x1; `400006DF` augment x1; `40000670` augment x1; `400006D3` augment x1 | 1 ach. |
| `400008F0` | - | 100 | - | - | - | `40000904` [Choice] `40000652` augment x1; `4000064B` augment x1; `40000676` augment x1; `40000664` augment x1; `40000692` augment x1; `4000068C` augment x1; `400006A1` augment x1; `400006DB` augment x1; `400006A3` augment x1; `40000679` augment x1; `40000674` augment x1; `400006C6` augment x1; `4000067A` augment x1; `40000695` augment x1; `400006BE` augment x1; `400006D6` augment x1; `4000067F` augment x1; `400006B1` augment x1; `400006E3` augment x1; `40000687` augment x1 + `400008E8` [Choice] `40000658` augment x1; `400006E6` augment x1; `400006C0` augment x1; `400006D8` augment x1; `4000069D` augment x1; `400006AB` augment x1; `4000069B` augment x1; `400006C7` augment x1; `4000068B` augment x1; `400006DD` augment x1; `400006A4` augment x1; `400006E7` augment x1; `400006B6` augment x1; `400006C9` augment x1; `40000662` augment x1; `400006AE` augment x1; `400006D1` augment x1; `400006B2` augment x1; `400006A9` augment x1; `4000067E` augment x1 + `400008E6` [Choice] `40000690` augment x1; `4000064C` augment x1; `40000688` augment x1; `400006CD` augment x1; `4000067C` augment x1; `400006DC` augment x1; `4000068E` augment x1; `40000673` augment x1; `400006BB` augment x1; `400006BA` augment x1; `4000069E` augment x1; `400006A0` augment x1; `40000699` augment x1; `400006B8` augment x1; `40000698` augment x1; `40000660` augment x1; `400006E5` augment x1; `400006DF` augment x1; `40000670` augment x1; `400006D3` augment x1 | 1 ach. |
| `400008F1` | - | 100 | - | - | - | `40000915` [Choice] `40000878` mod x1; `4000086D` mod x1; `40000832` mod x1; `4000087A` mod x1; `4000086A` mod x1; `4000084E` mod x1; `40000883` mod x1; `4000088F` mod x1; `400008AE` mod x1; `400008BD` mod x1 + `4000090C` [Choice] `40000855` mod x1; `400008B4` mod x1; `4000082C` mod x1; `40000862` mod x1; `4000085F` mod x1; `40000850` mod x1; `4000084A` mod x1; `400008AD` mod x1; `4000088E` mod x1; `4000085D` mod x1 + `40000917` [Choice] `40000867` mod x1; `4000082B` mod x1; `40000866` mod x1; `40000839` mod x1; `40000880` mod x1; `40000822` mod x1; `4000088D` mod x1; `40000852` mod x1; `40000890` mod x1; `400008B2` mod x1 | 1 ach. |
| `400008F2` | - | 100 | - | - | - | `40000915` [Choice] `40000878` mod x1; `4000086D` mod x1; `40000832` mod x1; `4000087A` mod x1; `4000086A` mod x1; `4000084E` mod x1; `40000883` mod x1; `4000088F` mod x1; `400008AE` mod x1; `400008BD` mod x1 + `4000090C` [Choice] `40000855` mod x1; `400008B4` mod x1; `4000082C` mod x1; `40000862` mod x1; `4000085F` mod x1; `40000850` mod x1; `4000084A` mod x1; `400008AD` mod x1; `4000088E` mod x1; `4000085D` mod x1 + `40000917` [Choice] `40000867` mod x1; `4000082B` mod x1; `40000866` mod x1; `40000839` mod x1; `40000880` mod x1; `40000822` mod x1; `4000088D` mod x1; `40000852` mod x1; `40000890` mod x1; `400008B2` mod x1 | 1 ach. |
| `400008F3` | - | 100 | - | - | - | `40000904` [Choice] `40000652` augment x1; `4000064B` augment x1; `40000676` augment x1; `40000664` augment x1; `40000692` augment x1; `4000068C` augment x1; `400006A1` augment x1; `400006DB` augment x1; `400006A3` augment x1; `40000679` augment x1; `40000674` augment x1; `400006C6` augment x1; `4000067A` augment x1; `40000695` augment x1; `400006BE` augment x1; `400006D6` augment x1; `4000067F` augment x1; `400006B1` augment x1; `400006E3` augment x1; `40000687` augment x1 + `400008E8` [Choice] `40000658` augment x1; `400006E6` augment x1; `400006C0` augment x1; `400006D8` augment x1; `4000069D` augment x1; `400006AB` augment x1; `4000069B` augment x1; `400006C7` augment x1; `4000068B` augment x1; `400006DD` augment x1; `400006A4` augment x1; `400006E7` augment x1; `400006B6` augment x1; `400006C9` augment x1; `40000662` augment x1; `400006AE` augment x1; `400006D1` augment x1; `400006B2` augment x1; `400006A9` augment x1; `4000067E` augment x1 + `400008E6` [Choice] `40000690` augment x1; `4000064C` augment x1; `40000688` augment x1; `400006CD` augment x1; `4000067C` augment x1; `400006DC` augment x1; `4000068E` augment x1; `40000673` augment x1; `400006BB` augment x1; `400006BA` augment x1; `4000069E` augment x1; `400006A0` augment x1; `40000699` augment x1; `400006B8` augment x1; `40000698` augment x1; `40000660` augment x1; `400006E5` augment x1; `400006DF` augment x1; `40000670` augment x1; `400006D3` augment x1 | 1 ach. |
| `400008F4` | - | 100 | - | - | - | `40000904` [Choice] `40000652` augment x1; `4000064B` augment x1; `40000676` augment x1; `40000664` augment x1; `40000692` augment x1; `4000068C` augment x1; `400006A1` augment x1; `400006DB` augment x1; `400006A3` augment x1; `40000679` augment x1; `40000674` augment x1; `400006C6` augment x1; `4000067A` augment x1; `40000695` augment x1; `400006BE` augment x1; `400006D6` augment x1; `4000067F` augment x1; `400006B1` augment x1; `400006E3` augment x1; `40000687` augment x1 + `400008E8` [Choice] `40000658` augment x1; `400006E6` augment x1; `400006C0` augment x1; `400006D8` augment x1; `4000069D` augment x1; `400006AB` augment x1; `4000069B` augment x1; `400006C7` augment x1; `4000068B` augment x1; `400006DD` augment x1; `400006A4` augment x1; `400006E7` augment x1; `400006B6` augment x1; `400006C9` augment x1; `40000662` augment x1; `400006AE` augment x1; `400006D1` augment x1; `400006B2` augment x1; `400006A9` augment x1; `4000067E` augment x1 + `400008E6` [Choice] `40000690` augment x1; `4000064C` augment x1; `40000688` augment x1; `400006CD` augment x1; `4000067C` augment x1; `400006DC` augment x1; `4000068E` augment x1; `40000673` augment x1; `400006BB` augment x1; `400006BA` augment x1; `4000069E` augment x1; `400006A0` augment x1; `40000699` augment x1; `400006B8` augment x1; `40000698` augment x1; `40000660` augment x1; `400006E5` augment x1; `400006DF` augment x1; `40000670` augment x1; `400006D3` augment x1 | 1 ach. |
| `400008F5` | - | 100 | - | - | - | `40000915` [Choice] `40000878` mod x1; `4000086D` mod x1; `40000832` mod x1; `4000087A` mod x1; `4000086A` mod x1; `4000084E` mod x1; `40000883` mod x1; `4000088F` mod x1; `400008AE` mod x1; `400008BD` mod x1 + `4000090C` [Choice] `40000855` mod x1; `400008B4` mod x1; `4000082C` mod x1; `40000862` mod x1; `4000085F` mod x1; `40000850` mod x1; `4000084A` mod x1; `400008AD` mod x1; `4000088E` mod x1; `4000085D` mod x1 + `40000917` [Choice] `40000867` mod x1; `4000082B` mod x1; `40000866` mod x1; `40000839` mod x1; `40000880` mod x1; `40000822` mod x1; `4000088D` mod x1; `40000852` mod x1; `40000890` mod x1; `400008B2` mod x1 | 1 ach. |
| `400008F6` | - | 100 | - | - | - | `40000904` [Choice] `40000652` augment x1; `4000064B` augment x1; `40000676` augment x1; `40000664` augment x1; `40000692` augment x1; `4000068C` augment x1; `400006A1` augment x1; `400006DB` augment x1; `400006A3` augment x1; `40000679` augment x1; `40000674` augment x1; `400006C6` augment x1; `4000067A` augment x1; `40000695` augment x1; `400006BE` augment x1; `400006D6` augment x1; `4000067F` augment x1; `400006B1` augment x1; `400006E3` augment x1; `40000687` augment x1 + `400008E8` [Choice] `40000658` augment x1; `400006E6` augment x1; `400006C0` augment x1; `400006D8` augment x1; `4000069D` augment x1; `400006AB` augment x1; `4000069B` augment x1; `400006C7` augment x1; `4000068B` augment x1; `400006DD` augment x1; `400006A4` augment x1; `400006E7` augment x1; `400006B6` augment x1; `400006C9` augment x1; `40000662` augment x1; `400006AE` augment x1; `400006D1` augment x1; `400006B2` augment x1; `400006A9` augment x1; `4000067E` augment x1 + `400008E6` [Choice] `40000690` augment x1; `4000064C` augment x1; `40000688` augment x1; `400006CD` augment x1; `4000067C` augment x1; `400006DC` augment x1; `4000068E` augment x1; `40000673` augment x1; `400006BB` augment x1; `400006BA` augment x1; `4000069E` augment x1; `400006A0` augment x1; `40000699` augment x1; `400006B8` augment x1; `40000698` augment x1; `40000660` augment x1; `400006E5` augment x1; `400006DF` augment x1; `40000670` augment x1; `400006D3` augment x1 | 1 ach. |
| `400008F7` | - | 100 | - | - | - | `40000915` [Choice] `40000878` mod x1; `4000086D` mod x1; `40000832` mod x1; `4000087A` mod x1; `4000086A` mod x1; `4000084E` mod x1; `40000883` mod x1; `4000088F` mod x1; `400008AE` mod x1; `400008BD` mod x1 + `4000090C` [Choice] `40000855` mod x1; `400008B4` mod x1; `4000082C` mod x1; `40000862` mod x1; `4000085F` mod x1; `40000850` mod x1; `4000084A` mod x1; `400008AD` mod x1; `4000088E` mod x1; `4000085D` mod x1 + `40000917` [Choice] `40000867` mod x1; `4000082B` mod x1; `40000866` mod x1; `40000839` mod x1; `40000880` mod x1; `40000822` mod x1; `4000088D` mod x1; `40000852` mod x1; `40000890` mod x1; `400008B2` mod x1 | 1 ach. |
| `400008F8` | - | 100 | - | - | - | `40000904` [Choice] `40000652` augment x1; `4000064B` augment x1; `40000676` augment x1; `40000664` augment x1; `40000692` augment x1; `4000068C` augment x1; `400006A1` augment x1; `400006DB` augment x1; `400006A3` augment x1; `40000679` augment x1; `40000674` augment x1; `400006C6` augment x1; `4000067A` augment x1; `40000695` augment x1; `400006BE` augment x1; `400006D6` augment x1; `4000067F` augment x1; `400006B1` augment x1; `400006E3` augment x1; `40000687` augment x1 + `400008E8` [Choice] `40000658` augment x1; `400006E6` augment x1; `400006C0` augment x1; `400006D8` augment x1; `4000069D` augment x1; `400006AB` augment x1; `4000069B` augment x1; `400006C7` augment x1; `4000068B` augment x1; `400006DD` augment x1; `400006A4` augment x1; `400006E7` augment x1; `400006B6` augment x1; `400006C9` augment x1; `40000662` augment x1; `400006AE` augment x1; `400006D1` augment x1; `400006B2` augment x1; `400006A9` augment x1; `4000067E` augment x1 + `400008E6` [Choice] `40000690` augment x1; `4000064C` augment x1; `40000688` augment x1; `400006CD` augment x1; `4000067C` augment x1; `400006DC` augment x1; `4000068E` augment x1; `40000673` augment x1; `400006BB` augment x1; `400006BA` augment x1; `4000069E` augment x1; `400006A0` augment x1; `40000699` augment x1; `400006B8` augment x1; `40000698` augment x1; `40000660` augment x1; `400006E5` augment x1; `400006DF` augment x1; `40000670` augment x1; `400006D3` augment x1 | 1 ach. |
| `400008F9` | - | 100 | - | - | - | `40000904` [Choice] `40000652` augment x1; `4000064B` augment x1; `40000676` augment x1; `40000664` augment x1; `40000692` augment x1; `4000068C` augment x1; `400006A1` augment x1; `400006DB` augment x1; `400006A3` augment x1; `40000679` augment x1; `40000674` augment x1; `400006C6` augment x1; `4000067A` augment x1; `40000695` augment x1; `400006BE` augment x1; `400006D6` augment x1; `4000067F` augment x1; `400006B1` augment x1; `400006E3` augment x1; `40000687` augment x1 + `400008E8` [Choice] `40000658` augment x1; `400006E6` augment x1; `400006C0` augment x1; `400006D8` augment x1; `4000069D` augment x1; `400006AB` augment x1; `4000069B` augment x1; `400006C7` augment x1; `4000068B` augment x1; `400006DD` augment x1; `400006A4` augment x1; `400006E7` augment x1; `400006B6` augment x1; `400006C9` augment x1; `40000662` augment x1; `400006AE` augment x1; `400006D1` augment x1; `400006B2` augment x1; `400006A9` augment x1; `4000067E` augment x1 + `400008E6` [Choice] `40000690` augment x1; `4000064C` augment x1; `40000688` augment x1; `400006CD` augment x1; `4000067C` augment x1; `400006DC` augment x1; `4000068E` augment x1; `40000673` augment x1; `400006BB` augment x1; `400006BA` augment x1; `4000069E` augment x1; `400006A0` augment x1; `40000699` augment x1; `400006B8` augment x1; `40000698` augment x1; `40000660` augment x1; `400006E5` augment x1; `400006DF` augment x1; `40000670` augment x1; `400006D3` augment x1 | 1 ach. |
| `400008FA` | - | 100 | - | - | - | `40000904` [Choice] `40000652` augment x1; `4000064B` augment x1; `40000676` augment x1; `40000664` augment x1; `40000692` augment x1; `4000068C` augment x1; `400006A1` augment x1; `400006DB` augment x1; `400006A3` augment x1; `40000679` augment x1; `40000674` augment x1; `400006C6` augment x1; `4000067A` augment x1; `40000695` augment x1; `400006BE` augment x1; `400006D6` augment x1; `4000067F` augment x1; `400006B1` augment x1; `400006E3` augment x1; `40000687` augment x1 + `400008E8` [Choice] `40000658` augment x1; `400006E6` augment x1; `400006C0` augment x1; `400006D8` augment x1; `4000069D` augment x1; `400006AB` augment x1; `4000069B` augment x1; `400006C7` augment x1; `4000068B` augment x1; `400006DD` augment x1; `400006A4` augment x1; `400006E7` augment x1; `400006B6` augment x1; `400006C9` augment x1; `40000662` augment x1; `400006AE` augment x1; `400006D1` augment x1; `400006B2` augment x1; `400006A9` augment x1; `4000067E` augment x1 + `400008E6` [Choice] `40000690` augment x1; `4000064C` augment x1; `40000688` augment x1; `400006CD` augment x1; `4000067C` augment x1; `400006DC` augment x1; `4000068E` augment x1; `40000673` augment x1; `400006BB` augment x1; `400006BA` augment x1; `4000069E` augment x1; `400006A0` augment x1; `40000699` augment x1; `400006B8` augment x1; `40000698` augment x1; `40000660` augment x1; `400006E5` augment x1; `400006DF` augment x1; `40000670` augment x1; `400006D3` augment x1 | 1 ach. |
| `400008FB` | - | 100 | - | - | - | `40000915` [Choice] `40000878` mod x1; `4000086D` mod x1; `40000832` mod x1; `4000087A` mod x1; `4000086A` mod x1; `4000084E` mod x1; `40000883` mod x1; `4000088F` mod x1; `400008AE` mod x1; `400008BD` mod x1 + `4000090C` [Choice] `40000855` mod x1; `400008B4` mod x1; `4000082C` mod x1; `40000862` mod x1; `4000085F` mod x1; `40000850` mod x1; `4000084A` mod x1; `400008AD` mod x1; `4000088E` mod x1; `4000085D` mod x1 + `40000917` [Choice] `40000867` mod x1; `4000082B` mod x1; `40000866` mod x1; `40000839` mod x1; `40000880` mod x1; `40000822` mod x1; `4000088D` mod x1; `40000852` mod x1; `40000890` mod x1; `400008B2` mod x1 | 1 ach. |
| `400008FC` | Bronze | 100 | - | - | A bronze reward! | `40000908` [Choice] `4000066F` augment x1 + `400008E1` [Choice] `40000659` augment x1 + `400008DC` [Choice] `4000067D` augment x1 | 1 ach. |
| `400008FD` | - | 100 | - | - | - | `40000904` [Choice] `40000652` augment x1; `4000064B` augment x1; `40000676` augment x1; `40000664` augment x1; `40000692` augment x1; `4000068C` augment x1; `400006A1` augment x1; `400006DB` augment x1; `400006A3` augment x1; `40000679` augment x1; `40000674` augment x1; `400006C6` augment x1; `4000067A` augment x1; `40000695` augment x1; `400006BE` augment x1; `400006D6` augment x1; `4000067F` augment x1; `400006B1` augment x1; `400006E3` augment x1; `40000687` augment x1 + `400008E8` [Choice] `40000658` augment x1; `400006E6` augment x1; `400006C0` augment x1; `400006D8` augment x1; `4000069D` augment x1; `400006AB` augment x1; `4000069B` augment x1; `400006C7` augment x1; `4000068B` augment x1; `400006DD` augment x1; `400006A4` augment x1; `400006E7` augment x1; `400006B6` augment x1; `400006C9` augment x1; `40000662` augment x1; `400006AE` augment x1; `400006D1` augment x1; `400006B2` augment x1; `400006A9` augment x1; `4000067E` augment x1 + `400008E6` [Choice] `40000690` augment x1; `4000064C` augment x1; `40000688` augment x1; `400006CD` augment x1; `4000067C` augment x1; `400006DC` augment x1; `4000068E` augment x1; `40000673` augment x1; `400006BB` augment x1; `400006BA` augment x1; `4000069E` augment x1; `400006A0` augment x1; `40000699` augment x1; `400006B8` augment x1; `40000698` augment x1; `40000660` augment x1; `400006E5` augment x1; `400006DF` augment x1; `40000670` augment x1; `400006D3` augment x1 | 1 ach. |
| `400008FE` | - | 100 | - | - | - | `40000904` [Choice] `40000652` augment x1; `4000064B` augment x1; `40000676` augment x1; `40000664` augment x1; `40000692` augment x1; `4000068C` augment x1; `400006A1` augment x1; `400006DB` augment x1; `400006A3` augment x1; `40000679` augment x1; `40000674` augment x1; `400006C6` augment x1; `4000067A` augment x1; `40000695` augment x1; `400006BE` augment x1; `400006D6` augment x1; `4000067F` augment x1; `400006B1` augment x1; `400006E3` augment x1; `40000687` augment x1 + `400008E8` [Choice] `40000658` augment x1; `400006E6` augment x1; `400006C0` augment x1; `400006D8` augment x1; `4000069D` augment x1; `400006AB` augment x1; `4000069B` augment x1; `400006C7` augment x1; `4000068B` augment x1; `400006DD` augment x1; `400006A4` augment x1; `400006E7` augment x1; `400006B6` augment x1; `400006C9` augment x1; `40000662` augment x1; `400006AE` augment x1; `400006D1` augment x1; `400006B2` augment x1; `400006A9` augment x1; `4000067E` augment x1 + `400008E6` [Choice] `40000690` augment x1; `4000064C` augment x1; `40000688` augment x1; `400006CD` augment x1; `4000067C` augment x1; `400006DC` augment x1; `4000068E` augment x1; `40000673` augment x1; `400006BB` augment x1; `400006BA` augment x1; `4000069E` augment x1; `400006A0` augment x1; `40000699` augment x1; `400006B8` augment x1; `40000698` augment x1; `40000660` augment x1; `400006E5` augment x1; `400006DF` augment x1; `40000670` augment x1; `400006D3` augment x1 | 1 ach. |
| `400008FF` | - | 100 | - | - | - | `40000904` [Choice] `40000652` augment x1; `4000064B` augment x1; `40000676` augment x1; `40000664` augment x1; `40000692` augment x1; `4000068C` augment x1; `400006A1` augment x1; `400006DB` augment x1; `400006A3` augment x1; `40000679` augment x1; `40000674` augment x1; `400006C6` augment x1; `4000067A` augment x1; `40000695` augment x1; `400006BE` augment x1; `400006D6` augment x1; `4000067F` augment x1; `400006B1` augment x1; `400006E3` augment x1; `40000687` augment x1 + `400008E8` [Choice] `40000658` augment x1; `400006E6` augment x1; `400006C0` augment x1; `400006D8` augment x1; `4000069D` augment x1; `400006AB` augment x1; `4000069B` augment x1; `400006C7` augment x1; `4000068B` augment x1; `400006DD` augment x1; `400006A4` augment x1; `400006E7` augment x1; `400006B6` augment x1; `400006C9` augment x1; `40000662` augment x1; `400006AE` augment x1; `400006D1` augment x1; `400006B2` augment x1; `400006A9` augment x1; `4000067E` augment x1 + `400008E6` [Choice] `40000690` augment x1; `4000064C` augment x1; `40000688` augment x1; `400006CD` augment x1; `4000067C` augment x1; `400006DC` augment x1; `4000068E` augment x1; `40000673` augment x1; `400006BB` augment x1; `400006BA` augment x1; `4000069E` augment x1; `400006A0` augment x1; `40000699` augment x1; `400006B8` augment x1; `40000698` augment x1; `40000660` augment x1; `400006E5` augment x1; `400006DF` augment x1; `40000670` augment x1; `400006D3` augment x1 | 1 ach. |
| `40000900` | - | 100 | - | - | - | `40000904` [Choice] `40000652` augment x1; `4000064B` augment x1; `40000676` augment x1; `40000664` augment x1; `40000692` augment x1; `4000068C` augment x1; `400006A1` augment x1; `400006DB` augment x1; `400006A3` augment x1; `40000679` augment x1; `40000674` augment x1; `400006C6` augment x1; `4000067A` augment x1; `40000695` augment x1; `400006BE` augment x1; `400006D6` augment x1; `4000067F` augment x1; `400006B1` augment x1; `400006E3` augment x1; `40000687` augment x1 + `400008E8` [Choice] `40000658` augment x1; `400006E6` augment x1; `400006C0` augment x1; `400006D8` augment x1; `4000069D` augment x1; `400006AB` augment x1; `4000069B` augment x1; `400006C7` augment x1; `4000068B` augment x1; `400006DD` augment x1; `400006A4` augment x1; `400006E7` augment x1; `400006B6` augment x1; `400006C9` augment x1; `40000662` augment x1; `400006AE` augment x1; `400006D1` augment x1; `400006B2` augment x1; `400006A9` augment x1; `4000067E` augment x1 + `400008E6` [Choice] `40000690` augment x1; `4000064C` augment x1; `40000688` augment x1; `400006CD` augment x1; `4000067C` augment x1; `400006DC` augment x1; `4000068E` augment x1; `40000673` augment x1; `400006BB` augment x1; `400006BA` augment x1; `4000069E` augment x1; `400006A0` augment x1; `40000699` augment x1; `400006B8` augment x1; `40000698` augment x1; `40000660` augment x1; `400006E5` augment x1; `400006DF` augment x1; `40000670` augment x1; `400006D3` augment x1 | 1 ach. |
| `40000901` | - | 100 | - | - | - | `40000904` [Choice] `40000652` augment x1; `4000064B` augment x1; `40000676` augment x1; `40000664` augment x1; `40000692` augment x1; `4000068C` augment x1; `400006A1` augment x1; `400006DB` augment x1; `400006A3` augment x1; `40000679` augment x1; `40000674` augment x1; `400006C6` augment x1; `4000067A` augment x1; `40000695` augment x1; `400006BE` augment x1; `400006D6` augment x1; `4000067F` augment x1; `400006B1` augment x1; `400006E3` augment x1; `40000687` augment x1 + `400008E8` [Choice] `40000658` augment x1; `400006E6` augment x1; `400006C0` augment x1; `400006D8` augment x1; `4000069D` augment x1; `400006AB` augment x1; `4000069B` augment x1; `400006C7` augment x1; `4000068B` augment x1; `400006DD` augment x1; `400006A4` augment x1; `400006E7` augment x1; `400006B6` augment x1; `400006C9` augment x1; `40000662` augment x1; `400006AE` augment x1; `400006D1` augment x1; `400006B2` augment x1; `400006A9` augment x1; `4000067E` augment x1 + `400008E6` [Choice] `40000690` augment x1; `4000064C` augment x1; `40000688` augment x1; `400006CD` augment x1; `4000067C` augment x1; `400006DC` augment x1; `4000068E` augment x1; `40000673` augment x1; `400006BB` augment x1; `400006BA` augment x1; `4000069E` augment x1; `400006A0` augment x1; `40000699` augment x1; `400006B8` augment x1; `40000698` augment x1; `40000660` augment x1; `400006E5` augment x1; `400006DF` augment x1; `40000670` augment x1; `400006D3` augment x1 | 1 ach. |
| `40000903` | Gold | 100 | - | - | A gold reward! | `40000902` [Choice] `400008B0` mod x1 + `40000906` [Choice] `400008B7` mod x1 + `40000911` [Choice] `400008B6` mod x1 | 1 ach. |
| `40000905` | - | 100 | - | - | - | `40000915` [Choice] `40000878` mod x1; `4000086D` mod x1; `40000832` mod x1; `4000087A` mod x1; `4000086A` mod x1; `4000084E` mod x1; `40000883` mod x1; `4000088F` mod x1; `400008AE` mod x1; `400008BD` mod x1 + `4000090C` [Choice] `40000855` mod x1; `400008B4` mod x1; `4000082C` mod x1; `40000862` mod x1; `4000085F` mod x1; `40000850` mod x1; `4000084A` mod x1; `400008AD` mod x1; `4000088E` mod x1; `4000085D` mod x1 + `40000917` [Choice] `40000867` mod x1; `4000082B` mod x1; `40000866` mod x1; `40000839` mod x1; `40000880` mod x1; `40000822` mod x1; `4000088D` mod x1; `40000852` mod x1; `40000890` mod x1; `400008B2` mod x1 | 1 ach. |
| `40000907` | - | 100 | - | - | - | `40000904` [Choice] `40000652` augment x1; `4000064B` augment x1; `40000676` augment x1; `40000664` augment x1; `40000692` augment x1; `4000068C` augment x1; `400006A1` augment x1; `400006DB` augment x1; `400006A3` augment x1; `40000679` augment x1; `40000674` augment x1; `400006C6` augment x1; `4000067A` augment x1; `40000695` augment x1; `400006BE` augment x1; `400006D6` augment x1; `4000067F` augment x1; `400006B1` augment x1; `400006E3` augment x1; `40000687` augment x1 + `400008E8` [Choice] `40000658` augment x1; `400006E6` augment x1; `400006C0` augment x1; `400006D8` augment x1; `4000069D` augment x1; `400006AB` augment x1; `4000069B` augment x1; `400006C7` augment x1; `4000068B` augment x1; `400006DD` augment x1; `400006A4` augment x1; `400006E7` augment x1; `400006B6` augment x1; `400006C9` augment x1; `40000662` augment x1; `400006AE` augment x1; `400006D1` augment x1; `400006B2` augment x1; `400006A9` augment x1; `4000067E` augment x1 + `400008E6` [Choice] `40000690` augment x1; `4000064C` augment x1; `40000688` augment x1; `400006CD` augment x1; `4000067C` augment x1; `400006DC` augment x1; `4000068E` augment x1; `40000673` augment x1; `400006BB` augment x1; `400006BA` augment x1; `4000069E` augment x1; `400006A0` augment x1; `40000699` augment x1; `400006B8` augment x1; `40000698` augment x1; `40000660` augment x1; `400006E5` augment x1; `400006DF` augment x1; `40000670` augment x1; `400006D3` augment x1 | 1 ach. |
| `40000909` | - | 100 | - | - | - | `40000904` [Choice] `40000652` augment x1; `4000064B` augment x1; `40000676` augment x1; `40000664` augment x1; `40000692` augment x1; `4000068C` augment x1; `400006A1` augment x1; `400006DB` augment x1; `400006A3` augment x1; `40000679` augment x1; `40000674` augment x1; `400006C6` augment x1; `4000067A` augment x1; `40000695` augment x1; `400006BE` augment x1; `400006D6` augment x1; `4000067F` augment x1; `400006B1` augment x1; `400006E3` augment x1; `40000687` augment x1 + `400008E8` [Choice] `40000658` augment x1; `400006E6` augment x1; `400006C0` augment x1; `400006D8` augment x1; `4000069D` augment x1; `400006AB` augment x1; `4000069B` augment x1; `400006C7` augment x1; `4000068B` augment x1; `400006DD` augment x1; `400006A4` augment x1; `400006E7` augment x1; `400006B6` augment x1; `400006C9` augment x1; `40000662` augment x1; `400006AE` augment x1; `400006D1` augment x1; `400006B2` augment x1; `400006A9` augment x1; `4000067E` augment x1 + `400008E6` [Choice] `40000690` augment x1; `4000064C` augment x1; `40000688` augment x1; `400006CD` augment x1; `4000067C` augment x1; `400006DC` augment x1; `4000068E` augment x1; `40000673` augment x1; `400006BB` augment x1; `400006BA` augment x1; `4000069E` augment x1; `400006A0` augment x1; `40000699` augment x1; `400006B8` augment x1; `40000698` augment x1; `40000660` augment x1; `400006E5` augment x1; `400006DF` augment x1; `40000670` augment x1; `400006D3` augment x1 | 1 ach. |
| `4000090B` | - | 100 | - | - | - | `40000904` [Choice] `40000652` augment x1; `4000064B` augment x1; `40000676` augment x1; `40000664` augment x1; `40000692` augment x1; `4000068C` augment x1; `400006A1` augment x1; `400006DB` augment x1; `400006A3` augment x1; `40000679` augment x1; `40000674` augment x1; `400006C6` augment x1; `4000067A` augment x1; `40000695` augment x1; `400006BE` augment x1; `400006D6` augment x1; `4000067F` augment x1; `400006B1` augment x1; `400006E3` augment x1; `40000687` augment x1 + `400008E8` [Choice] `40000658` augment x1; `400006E6` augment x1; `400006C0` augment x1; `400006D8` augment x1; `4000069D` augment x1; `400006AB` augment x1; `4000069B` augment x1; `400006C7` augment x1; `4000068B` augment x1; `400006DD` augment x1; `400006A4` augment x1; `400006E7` augment x1; `400006B6` augment x1; `400006C9` augment x1; `40000662` augment x1; `400006AE` augment x1; `400006D1` augment x1; `400006B2` augment x1; `400006A9` augment x1; `4000067E` augment x1 + `400008E6` [Choice] `40000690` augment x1; `4000064C` augment x1; `40000688` augment x1; `400006CD` augment x1; `4000067C` augment x1; `400006DC` augment x1; `4000068E` augment x1; `40000673` augment x1; `400006BB` augment x1; `400006BA` augment x1; `4000069E` augment x1; `400006A0` augment x1; `40000699` augment x1; `400006B8` augment x1; `40000698` augment x1; `40000660` augment x1; `400006E5` augment x1; `400006DF` augment x1; `40000670` augment x1; `400006D3` augment x1 | 1 ach. |
| `4000090E` | - | 100 | - | - | - | `40000904` [Choice] `40000652` augment x1; `4000064B` augment x1; `40000676` augment x1; `40000664` augment x1; `40000692` augment x1; `4000068C` augment x1; `400006A1` augment x1; `400006DB` augment x1; `400006A3` augment x1; `40000679` augment x1; `40000674` augment x1; `400006C6` augment x1; `4000067A` augment x1; `40000695` augment x1; `400006BE` augment x1; `400006D6` augment x1; `4000067F` augment x1; `400006B1` augment x1; `400006E3` augment x1; `40000687` augment x1 + `400008E8` [Choice] `40000658` augment x1; `400006E6` augment x1; `400006C0` augment x1; `400006D8` augment x1; `4000069D` augment x1; `400006AB` augment x1; `4000069B` augment x1; `400006C7` augment x1; `4000068B` augment x1; `400006DD` augment x1; `400006A4` augment x1; `400006E7` augment x1; `400006B6` augment x1; `400006C9` augment x1; `40000662` augment x1; `400006AE` augment x1; `400006D1` augment x1; `400006B2` augment x1; `400006A9` augment x1; `4000067E` augment x1 + `400008E6` [Choice] `40000690` augment x1; `4000064C` augment x1; `40000688` augment x1; `400006CD` augment x1; `4000067C` augment x1; `400006DC` augment x1; `4000068E` augment x1; `40000673` augment x1; `400006BB` augment x1; `400006BA` augment x1; `4000069E` augment x1; `400006A0` augment x1; `40000699` augment x1; `400006B8` augment x1; `40000698` augment x1; `40000660` augment x1; `400006E5` augment x1; `400006DF` augment x1; `40000670` augment x1; `400006D3` augment x1 | 1 ach. |
| `40000910` | - | 100 | - | - | - | `40000904` [Choice] `40000652` augment x1; `4000064B` augment x1; `40000676` augment x1; `40000664` augment x1; `40000692` augment x1; `4000068C` augment x1; `400006A1` augment x1; `400006DB` augment x1; `400006A3` augment x1; `40000679` augment x1; `40000674` augment x1; `400006C6` augment x1; `4000067A` augment x1; `40000695` augment x1; `400006BE` augment x1; `400006D6` augment x1; `4000067F` augment x1; `400006B1` augment x1; `400006E3` augment x1; `40000687` augment x1 + `400008E8` [Choice] `40000658` augment x1; `400006E6` augment x1; `400006C0` augment x1; `400006D8` augment x1; `4000069D` augment x1; `400006AB` augment x1; `4000069B` augment x1; `400006C7` augment x1; `4000068B` augment x1; `400006DD` augment x1; `400006A4` augment x1; `400006E7` augment x1; `400006B6` augment x1; `400006C9` augment x1; `40000662` augment x1; `400006AE` augment x1; `400006D1` augment x1; `400006B2` augment x1; `400006A9` augment x1; `4000067E` augment x1 + `400008E6` [Choice] `40000690` augment x1; `4000064C` augment x1; `40000688` augment x1; `400006CD` augment x1; `4000067C` augment x1; `400006DC` augment x1; `4000068E` augment x1; `40000673` augment x1; `400006BB` augment x1; `400006BA` augment x1; `4000069E` augment x1; `400006A0` augment x1; `40000699` augment x1; `400006B8` augment x1; `40000698` augment x1; `40000660` augment x1; `400006E5` augment x1; `400006DF` augment x1; `40000670` augment x1; `400006D3` augment x1 | 1 ach. |
| `40000913` | - | 100 | - | - | - | `40000915` [Choice] `40000878` mod x1; `4000086D` mod x1; `40000832` mod x1; `4000087A` mod x1; `4000086A` mod x1; `4000084E` mod x1; `40000883` mod x1; `4000088F` mod x1; `400008AE` mod x1; `400008BD` mod x1 + `4000090C` [Choice] `40000855` mod x1; `400008B4` mod x1; `4000082C` mod x1; `40000862` mod x1; `4000085F` mod x1; `40000850` mod x1; `4000084A` mod x1; `400008AD` mod x1; `4000088E` mod x1; `4000085D` mod x1 + `40000917` [Choice] `40000867` mod x1; `4000082B` mod x1; `40000866` mod x1; `40000839` mod x1; `40000880` mod x1; `40000822` mod x1; `4000088D` mod x1; `40000852` mod x1; `40000890` mod x1; `400008B2` mod x1 | 1 ach. |
| `40000914` | - | 100 | - | - | - | `40000915` [Choice] `40000878` mod x1; `4000086D` mod x1; `40000832` mod x1; `4000087A` mod x1; `4000086A` mod x1; `4000084E` mod x1; `40000883` mod x1; `4000088F` mod x1; `400008AE` mod x1; `400008BD` mod x1 + `4000090C` [Choice] `40000855` mod x1; `400008B4` mod x1; `4000082C` mod x1; `40000862` mod x1; `4000085F` mod x1; `40000850` mod x1; `4000084A` mod x1; `400008AD` mod x1; `4000088E` mod x1; `4000085D` mod x1 + `40000917` [Choice] `40000867` mod x1; `4000082B` mod x1; `40000866` mod x1; `40000839` mod x1; `40000880` mod x1; `40000822` mod x1; `4000088D` mod x1; `40000852` mod x1; `40000890` mod x1; `400008B2` mod x1 | 1 ach. |
| `40000916` | - | 100 | - | - | - | `40000904` [Choice] `40000652` augment x1; `4000064B` augment x1; `40000676` augment x1; `40000664` augment x1; `40000692` augment x1; `4000068C` augment x1; `400006A1` augment x1; `400006DB` augment x1; `400006A3` augment x1; `40000679` augment x1; `40000674` augment x1; `400006C6` augment x1; `4000067A` augment x1; `40000695` augment x1; `400006BE` augment x1; `400006D6` augment x1; `4000067F` augment x1; `400006B1` augment x1; `400006E3` augment x1; `40000687` augment x1 + `400008E8` [Choice] `40000658` augment x1; `400006E6` augment x1; `400006C0` augment x1; `400006D8` augment x1; `4000069D` augment x1; `400006AB` augment x1; `4000069B` augment x1; `400006C7` augment x1; `4000068B` augment x1; `400006DD` augment x1; `400006A4` augment x1; `400006E7` augment x1; `400006B6` augment x1; `400006C9` augment x1; `40000662` augment x1; `400006AE` augment x1; `400006D1` augment x1; `400006B2` augment x1; `400006A9` augment x1; `4000067E` augment x1 + `400008E6` [Choice] `40000690` augment x1; `4000064C` augment x1; `40000688` augment x1; `400006CD` augment x1; `4000067C` augment x1; `400006DC` augment x1; `4000068E` augment x1; `40000673` augment x1; `400006BB` augment x1; `400006BA` augment x1; `4000069E` augment x1; `400006A0` augment x1; `40000699` augment x1; `400006B8` augment x1; `40000698` augment x1; `40000660` augment x1; `400006E5` augment x1; `400006DF` augment x1; `40000670` augment x1; `400006D3` augment x1 | 1 ach. |
| `40000918` | - | 100 | - | - | - | `40000915` [Choice] `40000878` mod x1; `4000086D` mod x1; `40000832` mod x1; `4000087A` mod x1; `4000086A` mod x1; `4000084E` mod x1; `40000883` mod x1; `4000088F` mod x1; `400008AE` mod x1; `400008BD` mod x1 + `4000090C` [Choice] `40000855` mod x1; `400008B4` mod x1; `4000082C` mod x1; `40000862` mod x1; `4000085F` mod x1; `40000850` mod x1; `4000084A` mod x1; `400008AD` mod x1; `4000088E` mod x1; `4000085D` mod x1 + `40000917` [Choice] `40000867` mod x1; `4000082B` mod x1; `40000866` mod x1; `40000839` mod x1; `40000880` mod x1; `40000822` mod x1; `4000088D` mod x1; `40000852` mod x1; `40000890` mod x1; `400008B2` mod x1 | 1 ach. |
| `400009A7` | - | - | - | - | - | `400009A6` [Grant] `48000D62` Merit x1500; `48000D61` CrisisCoins x150; `40000AA0` icon x1 | 1 ach. |
| `400009AA` | - | - | - | - | - | `400009A8` [Grant] `48000D62` Merit x2500; `48000D61` CrisisCoins x250; `40000A9E` icon x1 | 1 ach. |
| `400009AC` | - | - | - | - | - | `400009B0` [Grant] `48000D62` Merit x2000; `48000D61` CrisisCoins x200; `40000A9F` icon x1 | 1 ach. |
| `400009AE` | - | - | - | - | - | `400009AD` [Grant] `48000D62` Merit x500; `48000D61` CrisisCoins x50; `40000A9D` icon x1 | 1 ach. |
| `400009B2` | - | - | - | - | - | `400009A9` [Grant] `48000D62` Merit x1000; `48000D61` CrisisCoins x100; `40000AA1` icon x1 | 1 ach. |
| `40000AF4` | - | - | - | - | - | `40000AFE` [Grant] `48000D62` Merit x1500 | 1 ach. |
| `40000AF7` | - | - | - | - | - | `40000B00` [Grant] `40000BB9` icon x1 | 1 ach. |
| `40000AF9` | - | - | - | - | - | `40000AF8` [Grant] `40000BBC` icon x1 | 1 ach. |
| `40000AFB` | - | - | - | - | - | `40000AF5` [Grant] `48000D61` CrisisCoins x1000; `40000BBB` icon x1 | 1 ach. |
| `40000AFC` | - | - | - | - | - | `40000B03` [Grant] `48000D62` Merit x1000 | 1 ach. |
| `40000AFD` | - | - | - | - | - | `40000B01` [Grant] `48000D62` Merit x1000 | 1 ach. |
| `40000AFF` | - | - | - | - | - | `40000AF6` [Grant] `48000D61` CrisisCoins x250; `40000BBA` icon x1 | 1 ach. |
| `40000B04` | - | - | - | - | - | `40000B02` [Grant] `48000D62` Merit x2000 | 1 ach. |
| `40000B05` | - | - | - | - | - | `40000AFA` [Grant] `48000D62` Merit x1000 | 1 ach. |
| `40000B07` | - | - | - | - | - | `40000B06` [Grant] `40000086` Gaslight Batman / The Sound of Justice x1 | 1 ach. |
| `40000B72` | - | 100 | - | - | - | `40000BA7` [Grant] `48000D62` Merit x100 | 1 ach. |
| `40000B73` | - | 100 | - | - | - | `40000BA7` [Grant] `48000D62` Merit x100 | 1 ach. |
| `40000B74` | - | 100 | - | - | - | `40000BA7` [Grant] `48000D62` Merit x100 | 1 ach. |
| `40000B75` | - | 100 | - | - | - | `40000BA7` [Grant] `48000D62` Merit x100 | 1 ach. |
| `40000B76` | - | 100 | - | - | - | `40000BA7` [Grant] `48000D62` Merit x100 | 1 ach. |
| `40000B77` | - | 100 | - | - | - | `40000BA7` [Grant] `48000D62` Merit x100 | 1 ach. |
| `40000B78` | - | 100 | - | - | - | `40000BA7` [Grant] `48000D62` Merit x100 | 1 ach. |
| `40000B79` | - | 100 | - | - | - | `40000BA7` [Grant] `48000D62` Merit x100 | 1 ach. |
| `40000B7A` | - | 100 | - | - | - | `40000BA7` [Grant] `48000D62` Merit x100 | 1 ach. |
| `40000B7B` | - | 100 | - | - | - | `40000BA7` [Grant] `48000D62` Merit x100 | 1 ach. |
| `40000B7C` | - | 100 | - | - | - | `40000BA7` [Grant] `48000D62` Merit x100 | 1 ach. |
| `40000B7D` | - | 100 | - | - | - | `40000BA7` [Grant] `48000D62` Merit x100 | 1 ach. |
| `40000B7E` | - | 100 | - | - | - | `40000BA7` [Grant] `48000D62` Merit x100 | 1 ach. |
| `40000B7F` | - | 100 | - | - | - | `40000BA7` [Grant] `48000D62` Merit x100 | 1 ach. |
| `40000B80` | - | 100 | - | - | - | `40000BA7` [Grant] `48000D62` Merit x100 | 1 ach. |
| `40000B81` | - | 100 | - | - | - | `40000BA7` [Grant] `48000D62` Merit x100 | 1 ach. |
| `40000B82` | - | 100 | - | - | - | `40000BA7` [Grant] `48000D62` Merit x100 | 1 ach. |
| `40000B83` | - | 100 | - | - | - | `40000BA7` [Grant] `48000D62` Merit x100 | 1 ach. |
| `40000B84` | - | 100 | - | - | - | `40000BA7` [Grant] `48000D62` Merit x100 | 1 ach. |
| `40000B85` | - | 100 | - | - | - | `40000BA7` [Grant] `48000D62` Merit x100 | 1 ach. |
| `40000B86` | - | 100 | - | - | - | `40000BA7` [Grant] `48000D62` Merit x100 | 1 ach. |
| `40000B87` | - | 100 | - | - | - | `40000BA7` [Grant] `48000D62` Merit x100 | 1 ach. |
| `40000B88` | - | 100 | - | - | - | `40000BA7` [Grant] `48000D62` Merit x100 | 1 ach. |
| `40000B89` | - | 100 | - | - | - | `40000BA7` [Grant] `48000D62` Merit x100 | 1 ach. |
| `40000B8A` | - | 100 | - | - | - | `40000BA7` [Grant] `48000D62` Merit x100 | 1 ach. |
| `40000B8B` | - | 100 | - | - | - | `40000BA7` [Grant] `48000D62` Merit x100 | 1 ach. |
| `40000B8C` | - | 100 | - | - | - | `40000BA7` [Grant] `48000D62` Merit x100 | 1 ach. |
| `40000B8D` | - | 100 | - | - | - | `40000BA7` [Grant] `48000D62` Merit x100 | 1 ach. |
| `40000B8E` | - | 100 | - | - | - | `40000BA7` [Grant] `48000D62` Merit x100 | 1 ach. |
| `40000B8F` | - | 100 | - | - | - | `40000BA7` [Grant] `48000D62` Merit x100 | 1 ach. |
| `40000B90` | - | 100 | - | - | - | `40000BA7` [Grant] `48000D62` Merit x100 | 1 ach. |
| `40000B91` | - | 100 | - | - | - | `40000BA7` [Grant] `48000D62` Merit x100 | 1 ach. |
| `40000B92` | - | 100 | - | - | - | `40000BA7` [Grant] `48000D62` Merit x100 | 1 ach. |
| `40000B93` | - | 100 | - | - | - | `40000BA7` [Grant] `48000D62` Merit x100 | 1 ach. |
| `40000B94` | - | 100 | - | - | - | `40000BA7` [Grant] `48000D62` Merit x100 | 1 ach. |
| `40000B95` | - | 100 | - | - | - | `40000BA7` [Grant] `48000D62` Merit x100 | 1 ach. |
| `40000B96` | - | 100 | - | - | - | `40000BA7` [Grant] `48000D62` Merit x100 | 1 ach. |
| `40000B97` | - | 100 | - | - | - | `40000BA7` [Grant] `48000D62` Merit x100 | 1 ach. |
| `40000B98` | - | 100 | - | - | - | `40000BA7` [Grant] `48000D62` Merit x100 | 1 ach. |
| `40000B99` | - | 100 | - | - | - | `40000BA7` [Grant] `48000D62` Merit x100 | 1 ach. |
| `40000B9A` | - | 100 | - | - | - | `40000BA7` [Grant] `48000D62` Merit x100 | 1 ach. |
| `40000B9B` | - | 100 | - | - | - | `40000BA7` [Grant] `48000D62` Merit x100 | 1 ach. |
| `40000B9C` | - | 100 | - | - | - | `40000BA7` [Grant] `48000D62` Merit x100 | 1 ach. |
| `40000B9D` | - | 100 | - | - | - | `40000BA7` [Grant] `48000D62` Merit x100 | 1 ach. |
| `40000B9E` | - | 100 | - | - | - | `40000BA7` [Grant] `48000D62` Merit x100 | 1 ach. |
| `40000B9F` | - | 100 | - | - | - | `40000BA7` [Grant] `48000D62` Merit x100 | 1 ach. |
| `40000BA0` | - | 100 | - | - | - | `40000BA7` [Grant] `48000D62` Merit x100 | 1 ach. |
| `40000BA1` | - | 100 | - | - | - | `40000BA7` [Grant] `48000D62` Merit x100 | 1 ach. |
| `40000BA2` | - | 100 | - | - | - | `40000BA7` [Grant] `48000D62` Merit x100 | 1 ach. |
| `40000BA3` | - | 100 | - | - | - | `40000BA7` [Grant] `48000D62` Merit x100 | 1 ach. |
| `40000BD7` | - | - | - | - | - | `40000BDA` [Grant] `48000D62` Merit x1000 | 2 ach. |
| `40000C3B` | - | - | - | - | - | `40000C3C` [Grant] `48000D62` Merit x250 | 1 ach. |
| `40000C51` | - | - | - | - | - | `40000C56` [Grant] `40000280` Batman / The Dark Knight x1 | 2 ach. |
| `40000C55` | - | - | - | - | - | `40000C53` [Grant] `40000260` Wonder Woman / Ambassador of Peace x1; `48000F31` AccountXP(flat) x1 | 1 ach. |
| `40000C57` | - | - | - | - | - | `40000C52` [Grant] `4000034D` Green Lantern / Fearless Maverick x1; `48000F31` AccountXP(flat) x1 | 1 ach. |
| `40000C58` | - | - | - | - | - | `40000C5F` [Grant] `4000054A` Harley Quinn / Mad Love x1; `48000F31` AccountXP(flat) x1 | 4 ach. |
| `40000C7D` | - | - | - | - | - | `40000C7E` [Grant] `4000015A` Doomsday / Ruthless Abomination x1; `48000F31` AccountXP(flat) x1 | 4 ach. |
| `40000D73` | - | - | - | - | - | `40000D76` [AutoGrant] `40000D75` icon x1 | 1 ach. |
| `40000DAB` | - | - | - | - | - | `40000E28` [AutoGrant] `40000E55` icon x1 | 1 ach. |
| `40000DAC` | - | - | - | - | - | `40000E26` [AutoGrant] `40000E44` icon x1 | 1 ach. |
| `40000DAD` | - | - | - | - | - | `40000E08` [AutoGrant] `40000E51` icon x1 | 1 ach. |
| `40000DAE` | - | - | - | - | - | `40000E29` [AutoGrant] `40000E0B` icon x1 | 1 ach. |
| `40000DAF` | - | - | - | - | - | `40000E10` [AutoGrant] `40000E41` icon x1 | 1 ach. |
| `40000DB0` | - | - | - | - | - | `40000E02` [AutoGrant] `40000E3E` icon x1 | 1 ach. |
| `40000DB1` | - | - | - | - | - | `40000E50` [AutoGrant] `40000E34` icon x1 | 1 ach. |
| `40000DB2` | - | - | - | - | - | `40000E46` [AutoGrant] `40000E4E` icon x1 | 1 ach. |
| `40000DB3` | - | - | - | - | - | `40000E21` [AutoGrant] `40000E16` icon x1 | 1 ach. |
| `40000DB4` | - | - | - | - | - | `40000E0C` [AutoGrant] `40000E1F` icon x1 | 1 ach. |
| `40000DB5` | - | - | - | - | - | `40000E3A` [AutoGrant] `40000DF9` icon x1 | 1 ach. |
| `40000DB6` | - | - | - | - | - | `40000E06` [AutoGrant] `40000E48` icon x1 | 1 ach. |
| `40000DB7` | - | - | - | - | - | `40000E14` [AutoGrant] `40000E07` icon x1 | 1 ach. |
| `40000DB8` | - | - | - | - | - | `40000DFE` [AutoGrant] `40000E37` icon x1 | 1 ach. |
| `40000DB9` | - | - | - | - | - | `40000DFC` [AutoGrant] `40000E45` icon x1 | 1 ach. |
| `40000DBA` | - | - | - | - | - | `40000DF2` [AutoGrant] `40000E1D` icon x1 | 1 ach. |
| `40000DBB` | - | - | - | - | - | `40000E00` [AutoGrant] `40000E01` icon x1 | 1 ach. |
| `40000DBC` | - | - | - | - | - | `40000E13` [AutoGrant] `40000E17` icon x1 | 1 ach. |
| `40000DBD` | - | - | - | - | - | `40000E1A` [AutoGrant] `40000E39` icon x1 | 1 ach. |
| `40000DBE` | - | - | - | - | - | `40000E2D` [AutoGrant] `40000DFA` icon x1 | 1 ach. |
| `40000DBF` | - | - | - | - | - | `40000DF3` [AutoGrant] `40000E03` icon x1 | 1 ach. |
| `40000DC0` | - | - | - | - | - | `40000E4F` [AutoGrant] `40000DFB` icon x1 | 1 ach. |
| `40000DC1` | - | - | - | - | - | `40000E0D` [AutoGrant] `40000DFD` icon x1 | 1 ach. |
| `40000DC2` | - | - | - | - | - | `40000E3F` [AutoGrant] `40000E40` icon x1 | 1 ach. |
| `40000DC3` | - | - | - | - | - | `40000E19` [AutoGrant] `40000E18` icon x1 | 1 ach. |
| `40000DC4` | - | - | - | - | - | `40000E36` [AutoGrant] `40000E24` icon x1 | 1 ach. |
| `40000DC5` | - | - | - | - | - | `40000DF6` [AutoGrant] `40000E27` icon x1 | 1 ach. |
| `40000DC6` | - | - | - | - | - | `40000E23` [AutoGrant] `40000E52` icon x1 | 1 ach. |
| `40000DC7` | - | - | - | - | - | `40000E0F` [AutoGrant] `40000DF4` icon x1 | 1 ach. |
| `40000DC8` | - | - | - | - | - | `40000E2F` [AutoGrant] `40000DF0` icon x1 | 1 ach. |
| `40000DC9` | - | - | - | - | - | `40000E4A` [AutoGrant] `40000E15` icon x1 | 1 ach. |
| `40000DCA` | - | - | - | - | - | `40000DF8` [AutoGrant] `40000E54` icon x1 | 1 ach. |
| `40000DCB` | - | - | - | - | - | `40000E25` [AutoGrant] `40000E11` icon x1 | 1 ach. |
| `40000DCC` | - | - | - | - | - | `40000E1E` [AutoGrant] `40000DF5` icon x1 | 1 ach. |
| `40000DCD` | - | - | - | - | - | `40000E0A` [AutoGrant] `40000E32` icon x1 | 1 ach. |
| `40000DCE` | - | - | - | - | - | `40000E04` [AutoGrant] `40000E49` icon x1 | 1 ach. |
| `40000DCF` | - | - | - | - | - | `40000E22` [AutoGrant] `40000E3B` icon x1 | 1 ach. |
| `40000DD0` | - | - | - | - | - | `40000E09` [AutoGrant] `40000DFF` icon x1 | 1 ach. |
| `40000DD1` | - | - | - | - | - | `40000E4C` [AutoGrant] `40000E47` icon x1 | 1 ach. |
| `40000DD2` | - | - | - | - | - | `40000E1C` [AutoGrant] `40000E2A` icon x1 | 1 ach. |
| `40000DD3` | - | - | - | - | - | `40000E2B` [AutoGrant] `40000E33` icon x1 | 1 ach. |
| `40000DD4` | - | - | - | - | - | `40000E05` [AutoGrant] `40000E30` icon x1 | 1 ach. |
| `40000DD5` | - | - | - | - | - | `40000E1B` [AutoGrant] `40000E4D` icon x1 | 1 ach. |
| `40000DD6` | - | - | - | - | - | `40000E2E` [AutoGrant] `40000E3C` icon x1 | 1 ach. |
| `40000DD7` | - | - | - | - | - | `40000DF7` [AutoGrant] `40000E38` icon x1 | 1 ach. |
| `40000DD8` | - | - | - | - | - | `40000E31` [AutoGrant] `40000E12` icon x1 | 1 ach. |
| `40000DD9` | - | - | - | - | - | `40000E43` [AutoGrant] `40000E20` icon x1 | 1 ach. |
| `40000DDA` | - | - | - | - | - | `40000DF1` [AutoGrant] `40000E3D` icon x1 | 1 ach. |
| `40000DDB` | - | - | - | - | - | `40000E0E` [AutoGrant] `40000E42` icon x1 | 1 ach. |
| `40000DDC` | - | - | - | - | - | `40000E53` [AutoGrant] `40000E2C` icon x1 | 1 ach. |
| `40000DDD` | - | - | - | - | - | `40000E4B` [AutoGrant] `40000E35` icon x1 | 1 ach. |
| `40000EDD` | Bronze | - | - | - | Merit | `40000ED8` [Grant] `4800152C` Merit x50 | login calendar |
| `40000EDE` | Gold | - | 1 | - | A lot of Merit | `40000ED7` [Grant] `4800152C` Merit x250; `4800152D` CrisisCoins x50 | login calendar |
| `40000EDF` | Silver | - | 1 | - | More Merit | `40000ED6` [Grant] `4800152C` Merit x250 | login calendar |
| `40000EE0` | Gold | 250 | - | - | A champion | `40000EDA` [Grant] `40000213` The Joker / Clown Prince of Crime x1 | login calendar |
| `40000EE1` | Gold | - | - | `13002D5F` | A costume | `40000ED9` [Grant] `40000BD3` Gaslight Batman / Android x1 | login calendar |
| `40000F18` | - | - | - | - | - | `40000F20` [Grant] `40000F14` icon x1 | 1 ach. |
| `40000F19` | - | - | - | - | - | `40000F1D` [Grant] `40000F13` icon x1 | 1 ach. |
| `40000F1A` | - | - | - | - | - | `40000F1F` [Grant] `40000F17` icon x1 | 1 ach. |
| `40000F1B` | - | - | - | - | - | `40000F1E` [Grant] `40000F15` icon x1 | 1 ach. |
| `40000F1C` | - | - | - | - | - | `40000F21` [Grant] `40000F16` icon x1 | 1 ach. |

### 3.3 Currencies and account XP items [C]

Merit (soft, `PostMatchRewardType` 1): `0x48000722`, `0x48000CD7`, `0x48000D62` (achievements), `0x4800152C` (login
calendar). Crisis Coins (hard, 2): `0x48000723`, `0x48000D61` (achievements), `0x48000E3D`, `0x4800152D` (login).
Account XP: `0x48000F31` `0x10000B38 = 1` (flat, type 5) and `0x48000F30` = 2 (percent, type 6). Balance event `0x2081`
`(hard, soft)`; end-of-match / change `0x20B9` (base, daily first-win, f32 time to next daily, streak, potential daily,
potential streak, 2 tooltips, u32). No Merit-per-match or first-win amounts exist in the data [C].

`0x48000C71` (`0x1000099F` of `0x10000A0F`, 33 `0x48` DIDs): contains the 6 Merit/Coin records above plus 27 empty
records (`0x48000892`-`0x4800089D`, `0x48000A07`-`0x48000A0C`, `0x48000A31`, `0x48000A3E`, `0x48000BFE`,
`0x48000D2A`, `0x48000E59`, `0x48000E5A`, `0x48000E72`, `0x48001257`, `0x480014CE`): a list of reward/currency item
records whose server-side contents were stripped [P].

### 3.4 Login rewards [C data / P days]

Calendar `0x48001528` (`0x10000D94`, 110 entries `0x10000D95` {`0x10000D93` reward set, `0x10000D92` day}; the first
entry has no day = day 0). Five reward sets (`0x40000EDD`-`0x40000EE1`, pack `0xA00000B3`): 50 Merit (Bronze), 250
Merit (Silver), 250 Merit + 50 Coins (Gold), a champion (The Joker `0x40000213`, Gold, `0x10000A1C = 250`), a costume
(Gaslight Batman Android `0x40000BD3`, Gold, icon `0x13002D5F`). Days run 0..374 in steps of 3-4 (two rewards per week,
alternating) [P: `0x10000D92` = days since the account's first login].

Events: S->C `0x2197` (same layout as `0x2125`; Flash `DeliverLoginRewardSet(lastDay, eligible, days, labels, quality,
bestowal, rewardTypes, descriptions, mysteries, itemDIDs, icons, names, quantities)`), `0x219D` (u8 0: none eligible);
Flash notices `QueueLoginReward` / `ReadyForLoginRewardSet` (C->S event not located). UI config `0x48000E76`:
background movie `0x10000DA0`, image `0x10000D9F`.

| Entry | Day `D92` | Reward set `D93` -> contents |
|---|---|---|
| 0 | (absent) | `40000EDD` -> `40000ED8` [Grant] `4800152C` Merit x50 |
| 1 | 3 | `40000EE1` -> `40000ED9` [Grant] `40000BD3` Gaslight Batman / Android x1 |
| 2 | 4 | `40000EDF` -> `40000ED6` [Grant] `4800152C` Merit x250 |
| 3 | 6 | `40000EDE` -> `40000ED7` [Grant] `4800152C` Merit x250; `4800152D` CrisisCoins x50 |
| 4 | 7 | `40000EE0` -> `40000EDA` [Grant] `40000213` The Joker / Clown Prince of Crime x1 |
| 5 | 10 | `40000EDF` -> `40000ED6` [Grant] `4800152C` Merit x250 |
| 6 | 14 | `40000EDE` -> `40000ED7` [Grant] `4800152C` Merit x250; `4800152D` CrisisCoins x50 |
| 7 | 17 | `40000EDF` -> `40000ED6` [Grant] `4800152C` Merit x250 |
| 8 | 21 | `40000EDE` -> `40000ED7` [Grant] `4800152C` Merit x250; `4800152D` CrisisCoins x50 |
| 9 | 24 | `40000EDF` -> `40000ED6` [Grant] `4800152C` Merit x250 |
| 10 | 28 | `40000EDE` -> `40000ED7` [Grant] `4800152C` Merit x250; `4800152D` CrisisCoins x50 |
| 11 | 31 | `40000EDF` -> `40000ED6` [Grant] `4800152C` Merit x250 |
| 12 | 35 | `40000EDE` -> `40000ED7` [Grant] `4800152C` Merit x250; `4800152D` CrisisCoins x50 |
| 13 | 38 | `40000EDF` -> `40000ED6` [Grant] `4800152C` Merit x250 |
| 14 | 42 | `40000EDE` -> `40000ED7` [Grant] `4800152C` Merit x250; `4800152D` CrisisCoins x50 |
| 15 | 45 | `40000EDF` -> `40000ED6` [Grant] `4800152C` Merit x250 |
| 16 | 49 | `40000EDE` -> `40000ED7` [Grant] `4800152C` Merit x250; `4800152D` CrisisCoins x50 |
| 17 | 52 | `40000EDF` -> `40000ED6` [Grant] `4800152C` Merit x250 |
| 18 | 56 | `40000EDE` -> `40000ED7` [Grant] `4800152C` Merit x250; `4800152D` CrisisCoins x50 |
| 19 | 59 | `40000EDF` -> `40000ED6` [Grant] `4800152C` Merit x250 |
| 20 | 63 | `40000EDE` -> `40000ED7` [Grant] `4800152C` Merit x250; `4800152D` CrisisCoins x50 |
| 21 | 66 | `40000EDF` -> `40000ED6` [Grant] `4800152C` Merit x250 |
| 22 | 70 | `40000EDE` -> `40000ED7` [Grant] `4800152C` Merit x250; `4800152D` CrisisCoins x50 |
| 23 | 73 | `40000EDF` -> `40000ED6` [Grant] `4800152C` Merit x250 |
| 24 | 77 | `40000EDE` -> `40000ED7` [Grant] `4800152C` Merit x250; `4800152D` CrisisCoins x50 |
| 25 | 80 | `40000EDF` -> `40000ED6` [Grant] `4800152C` Merit x250 |
| 26 | 84 | `40000EDE` -> `40000ED7` [Grant] `4800152C` Merit x250; `4800152D` CrisisCoins x50 |
| 27 | 87 | `40000EDF` -> `40000ED6` [Grant] `4800152C` Merit x250 |
| 28 | 91 | `40000EDE` -> `40000ED7` [Grant] `4800152C` Merit x250; `4800152D` CrisisCoins x50 |
| 29 | 94 | `40000EDF` -> `40000ED6` [Grant] `4800152C` Merit x250 |
| 30 | 98 | `40000EDE` -> `40000ED7` [Grant] `4800152C` Merit x250; `4800152D` CrisisCoins x50 |
| 31 | 101 | `40000EDF` -> `40000ED6` [Grant] `4800152C` Merit x250 |
| 32 | 105 | `40000EDE` -> `40000ED7` [Grant] `4800152C` Merit x250; `4800152D` CrisisCoins x50 |
| 33 | 108 | `40000EDF` -> `40000ED6` [Grant] `4800152C` Merit x250 |
| 34 | 112 | `40000EDE` -> `40000ED7` [Grant] `4800152C` Merit x250; `4800152D` CrisisCoins x50 |
| 35 | 115 | `40000EDF` -> `40000ED6` [Grant] `4800152C` Merit x250 |
| 36 | 119 | `40000EDE` -> `40000ED7` [Grant] `4800152C` Merit x250; `4800152D` CrisisCoins x50 |
| 37 | 122 | `40000EDF` -> `40000ED6` [Grant] `4800152C` Merit x250 |
| 38 | 126 | `40000EDE` -> `40000ED7` [Grant] `4800152C` Merit x250; `4800152D` CrisisCoins x50 |
| 39 | 129 | `40000EDF` -> `40000ED6` [Grant] `4800152C` Merit x250 |
| 40 | 133 | `40000EDE` -> `40000ED7` [Grant] `4800152C` Merit x250; `4800152D` CrisisCoins x50 |
| 41 | 136 | `40000EDF` -> `40000ED6` [Grant] `4800152C` Merit x250 |
| 42 | 140 | `40000EDE` -> `40000ED7` [Grant] `4800152C` Merit x250; `4800152D` CrisisCoins x50 |
| 43 | 143 | `40000EDF` -> `40000ED6` [Grant] `4800152C` Merit x250 |
| 44 | 147 | `40000EDE` -> `40000ED7` [Grant] `4800152C` Merit x250; `4800152D` CrisisCoins x50 |
| 45 | 150 | `40000EDF` -> `40000ED6` [Grant] `4800152C` Merit x250 |
| 46 | 154 | `40000EDE` -> `40000ED7` [Grant] `4800152C` Merit x250; `4800152D` CrisisCoins x50 |
| 47 | 157 | `40000EDF` -> `40000ED6` [Grant] `4800152C` Merit x250 |
| 48 | 161 | `40000EDE` -> `40000ED7` [Grant] `4800152C` Merit x250; `4800152D` CrisisCoins x50 |
| 49 | 164 | `40000EDF` -> `40000ED6` [Grant] `4800152C` Merit x250 |
| 50 | 168 | `40000EDE` -> `40000ED7` [Grant] `4800152C` Merit x250; `4800152D` CrisisCoins x50 |
| 51 | 171 | `40000EDF` -> `40000ED6` [Grant] `4800152C` Merit x250 |
| 52 | 175 | `40000EDE` -> `40000ED7` [Grant] `4800152C` Merit x250; `4800152D` CrisisCoins x50 |
| 53 | 178 | `40000EDF` -> `40000ED6` [Grant] `4800152C` Merit x250 |
| 54 | 182 | `40000EDE` -> `40000ED7` [Grant] `4800152C` Merit x250; `4800152D` CrisisCoins x50 |
| 55 | 185 | `40000EDF` -> `40000ED6` [Grant] `4800152C` Merit x250 |
| 56 | 189 | `40000EDE` -> `40000ED7` [Grant] `4800152C` Merit x250; `4800152D` CrisisCoins x50 |
| 57 | 192 | `40000EDF` -> `40000ED6` [Grant] `4800152C` Merit x250 |
| 58 | 196 | `40000EDE` -> `40000ED7` [Grant] `4800152C` Merit x250; `4800152D` CrisisCoins x50 |
| 59 | 199 | `40000EDF` -> `40000ED6` [Grant] `4800152C` Merit x250 |
| 60 | 203 | `40000EDE` -> `40000ED7` [Grant] `4800152C` Merit x250; `4800152D` CrisisCoins x50 |
| 61 | 206 | `40000EDF` -> `40000ED6` [Grant] `4800152C` Merit x250 |
| 62 | 210 | `40000EDE` -> `40000ED7` [Grant] `4800152C` Merit x250; `4800152D` CrisisCoins x50 |
| 63 | 213 | `40000EDF` -> `40000ED6` [Grant] `4800152C` Merit x250 |
| 64 | 217 | `40000EDE` -> `40000ED7` [Grant] `4800152C` Merit x250; `4800152D` CrisisCoins x50 |
| 65 | 220 | `40000EDF` -> `40000ED6` [Grant] `4800152C` Merit x250 |
| 66 | 224 | `40000EDE` -> `40000ED7` [Grant] `4800152C` Merit x250; `4800152D` CrisisCoins x50 |
| 67 | 227 | `40000EDF` -> `40000ED6` [Grant] `4800152C` Merit x250 |
| 68 | 231 | `40000EDE` -> `40000ED7` [Grant] `4800152C` Merit x250; `4800152D` CrisisCoins x50 |
| 69 | 234 | `40000EDF` -> `40000ED6` [Grant] `4800152C` Merit x250 |
| 70 | 238 | `40000EDE` -> `40000ED7` [Grant] `4800152C` Merit x250; `4800152D` CrisisCoins x50 |
| 71 | 241 | `40000EDF` -> `40000ED6` [Grant] `4800152C` Merit x250 |
| 72 | 245 | `40000EDE` -> `40000ED7` [Grant] `4800152C` Merit x250; `4800152D` CrisisCoins x50 |
| 73 | 248 | `40000EDF` -> `40000ED6` [Grant] `4800152C` Merit x250 |
| 74 | 252 | `40000EDE` -> `40000ED7` [Grant] `4800152C` Merit x250; `4800152D` CrisisCoins x50 |
| 75 | 255 | `40000EDF` -> `40000ED6` [Grant] `4800152C` Merit x250 |
| 76 | 259 | `40000EDE` -> `40000ED7` [Grant] `4800152C` Merit x250; `4800152D` CrisisCoins x50 |
| 77 | 262 | `40000EDF` -> `40000ED6` [Grant] `4800152C` Merit x250 |
| 78 | 266 | `40000EDE` -> `40000ED7` [Grant] `4800152C` Merit x250; `4800152D` CrisisCoins x50 |
| 79 | 269 | `40000EDF` -> `40000ED6` [Grant] `4800152C` Merit x250 |
| 80 | 273 | `40000EDE` -> `40000ED7` [Grant] `4800152C` Merit x250; `4800152D` CrisisCoins x50 |
| 81 | 276 | `40000EDF` -> `40000ED6` [Grant] `4800152C` Merit x250 |
| 82 | 280 | `40000EDE` -> `40000ED7` [Grant] `4800152C` Merit x250; `4800152D` CrisisCoins x50 |
| 83 | 283 | `40000EDF` -> `40000ED6` [Grant] `4800152C` Merit x250 |
| 84 | 287 | `40000EDE` -> `40000ED7` [Grant] `4800152C` Merit x250; `4800152D` CrisisCoins x50 |
| 85 | 290 | `40000EDF` -> `40000ED6` [Grant] `4800152C` Merit x250 |
| 86 | 294 | `40000EDE` -> `40000ED7` [Grant] `4800152C` Merit x250; `4800152D` CrisisCoins x50 |
| 87 | 297 | `40000EDF` -> `40000ED6` [Grant] `4800152C` Merit x250 |
| 88 | 301 | `40000EDE` -> `40000ED7` [Grant] `4800152C` Merit x250; `4800152D` CrisisCoins x50 |
| 89 | 304 | `40000EDF` -> `40000ED6` [Grant] `4800152C` Merit x250 |
| 90 | 308 | `40000EDE` -> `40000ED7` [Grant] `4800152C` Merit x250; `4800152D` CrisisCoins x50 |
| 91 | 311 | `40000EDF` -> `40000ED6` [Grant] `4800152C` Merit x250 |
| 92 | 315 | `40000EDE` -> `40000ED7` [Grant] `4800152C` Merit x250; `4800152D` CrisisCoins x50 |
| 93 | 318 | `40000EDF` -> `40000ED6` [Grant] `4800152C` Merit x250 |
| 94 | 322 | `40000EDE` -> `40000ED7` [Grant] `4800152C` Merit x250; `4800152D` CrisisCoins x50 |
| 95 | 325 | `40000EDF` -> `40000ED6` [Grant] `4800152C` Merit x250 |
| 96 | 329 | `40000EDE` -> `40000ED7` [Grant] `4800152C` Merit x250; `4800152D` CrisisCoins x50 |
| 97 | 332 | `40000EDF` -> `40000ED6` [Grant] `4800152C` Merit x250 |
| 98 | 336 | `40000EDE` -> `40000ED7` [Grant] `4800152C` Merit x250; `4800152D` CrisisCoins x50 |
| 99 | 339 | `40000EDF` -> `40000ED6` [Grant] `4800152C` Merit x250 |
| 100 | 343 | `40000EDE` -> `40000ED7` [Grant] `4800152C` Merit x250; `4800152D` CrisisCoins x50 |
| 101 | 346 | `40000EDF` -> `40000ED6` [Grant] `4800152C` Merit x250 |
| 102 | 350 | `40000EDE` -> `40000ED7` [Grant] `4800152C` Merit x250; `4800152D` CrisisCoins x50 |
| 103 | 353 | `40000EDF` -> `40000ED6` [Grant] `4800152C` Merit x250 |
| 104 | 357 | `40000EDE` -> `40000ED7` [Grant] `4800152C` Merit x250; `4800152D` CrisisCoins x50 |
| 105 | 360 | `40000EDF` -> `40000ED6` [Grant] `4800152C` Merit x250 |
| 106 | 364 | `40000EDE` -> `40000ED7` [Grant] `4800152C` Merit x250; `4800152D` CrisisCoins x50 |
| 107 | 367 | `40000EDF` -> `40000ED6` [Grant] `4800152C` Merit x250 |
| 108 | 371 | `40000EDE` -> `40000ED7` [Grant] `4800152C` Merit x250; `4800152D` CrisisCoins x50 |
| 109 | 374 | `40000EDF` -> `40000ED6` [Grant] `4800152C` Merit x250 |

### 3.5 Accolades [C]

Record (`0x49`, 21 properties): `0x10000CD8` name, `0x10000C6A` **stat id** (the statistic of `0x48001172`, e.g. 30
Deaths for Survivor, 43 ChampionKills for Master Combatant), `0x10000C69` **scoreboard section** 1 Advancement, 2
Defense, 3 Offense, 4 Sector Objectives [P: matches the stats' sections in the grid records], `0x10000C68` 1-20 (G:
weight / priority), `0x10000C9C` bool (G: higher is better / shows all-time best), `0x10000C67` flag, `0x10000CE1`-
`0x10000CE3` icons (gold / silver / bronze [P]), texts `0x10000CD7`, `0x10000CD9`-`0x10000CDD`, `0x10000D2B`,
`0x10000D2C`, `0x10000D3C`, `0x10000D3D`, `0x10000D57`, `0x10000D5B` (summary, all-time-best and per-map variants).
`0x48001242` = the 46 per-match accolades; `0x48001490` maps 9 encounters to their "first match on this map" accolade.
Medal rank: `AccoladeRankType` 1 Gold, 2 Silver, 3 Bronze (`0x48000EF9`).

Events: `0x2188` end of match `(didEncounter, bRanked, didChampion, StringInfo, names[], descriptions[], summaries[],
icons[], medalTypes (bytelist), isAllTimeBest[])` and the same lists inside `0x2104`; `0x2186` best map / best champion
accolades `{u32 n x (u32, u32, u8, u32, u32, StringInfo)}` x 2 (C->S `UI_RequestBestAccolades`, event not located).

| DID (0x40) | Name `CD8` | `C68` | `C69` | `C6A` | `C9C` | Icon `CE1` | In list `0x48001242` | First-match accolade of encounter |
|---|---|---|---|---|---|---|---|---|
| `40000CE4` | Survivor | 6 | 2 | 30 | 1 | `13003787` | yes | - |
| `40000CE6` | Master Combatant | 4 | 3 | 43 | 1 | `13003795` | yes | - |
| `40000CEE` | Healing Sponge | 16 | 2 | 19 | 1 | `13003784` | yes | - |
| `40000CEF` | Awesome Attacker | 8 | 3 | 52 | 1 | `13003798` | yes | - |
| `40000CF0` | Quadra Killer | 2 | 3 | 6 | 1 | `1300379C` | yes | - |
| `40000CF1` | Cold Creature Comfort | 14 | 1 | 9 | 1 | `1300378E` | yes | - |
| `40000CF2` | Drone Experience | 18 | 1 | 37 | - | `13003777` | yes | - |
| `40000CF3` | Pro Heals | 16 | 2 | 46 | 1 | `1300379F` | yes | - |
| `40000CF4` | Big Creature Hunter | 8 | 3 | 41 | 1 | `13003791` | yes | - |
| `40000CF5` | Thick Skin | 12 | 2 | 27 | 1 | `130037A4` | yes | - |
| `40000CF6` | Moar Damagez! | 16 | 3 | 31 | 1 | `1300378A` | yes | - |
| `40000CF7` | Champion Cash | 14 | 1 | 10 | 1 | `1300378F` | yes | - |
| `40000CF8` | Down With Dampeners | 8 | 4 | 29 | 1 | `13003783` | yes | - |
| `40000CF9` | Tactical Expert | 8 | 4 | 36 | 1 | `130037A7` | yes | - |
| `40000CFA` | Attack Protection | 20 | 2 | 5 | - | `13003797` | yes | - |
| `40000CFB` | Master Blaster | 8 | 3 | 45 | 1 | `13003780` | yes | - |
| `40000CFC` | Ka-ching! | 10 | 1 | 11 | 1 | `13003794` | yes | - |
| `40000CFD` | Herald of Doom | 6 | 4 | 47 | 1 | `13003786` | yes | - |
| `40000CFE` | Barely A Scratch | 10 | 2 | 51 | 1 | `13003788` | yes | - |
| `40000CFF` | Can't Blast Me | 20 | 2 | 3 | - | `1300377E` | yes | - |
| `40000D00` | Nuke 'Em From Orbit | 4 | 4 | 4 | 1 | `13003782` | yes | - |
| `40000D01` | Triple Killer | 3 | 3 | 33 | 1 | `1300379B` | yes | - |
| `40000D03` | Power Protection | 20 | 2 | 38 | - | `1300377F` | yes | - |
| `40000D04` | Big Power | 16 | 3 | 21 | 1 | `13003781` | yes | - |
| `40000D05` | Are You Experienced? | 10 | 1 | 12 | 1 | `1300377A` | yes | - |
| `40000D06` | No Time To Rest | 8 | 2 | 1 | 1 | `1300377B` | yes | - |
| `40000D07` | Turret Terror | 8 | 4 | 32 | 1 | `1300379A` | yes | - |
| `40000D08` | Coin Stomper | 10 | 1 | 7 | 1 | `1300378B` | yes | - |
| `40000D09` | Creature Experience | 18 | 1 | 24 | - | `13003778` | yes | - |
| `40000D0A` | Dollars for Drones | 14 | 1 | 20 | 1 | `1300378D` | yes | - |
| `40000D0B` | Penta Killer | 1 | 3 | 18 | 1 | `1300379D` | yes | - |
| `40000D0C` | Can't Hit Me | 20 | 2 | 23 | - | `13003796` | yes | - |
| `40000D0D` | Deep Pockets | 4 | 1 | 40 | 1 | `13003790` | yes | - |
| `40000D0E` | Heavy Hitter | 16 | 3 | 15 | 1 | `13003799` | yes | - |
| `40000D0F` | Control All The Points | 6 | 4 | 17 | 1 | `13003793` | yes | - |
| `40000D10` | Objective Experience | 18 | 1 | 34 | - | `13003776` | yes | - |
| `40000D11` | I'm Helping! | 6 | 3 | 22 | 1 | `130037A8` | yes | - |
| `40000D12` | Objective Obsession | 14 | 1 | 8 | 1 | `1300378C` | yes | - |
| `40000D13` | Drone Bane | 8 | 3 | 13 | 1 | `130037A3` | yes | - |
| `40000D14` | Taking the Big Hits | 20 | 2 | 39 | - | `13003789` | yes | - |
| `40000D15` | Champion Experience | 18 | 1 | 28 | - | `13003779` | yes | - |
| `40000D16` | Not Your Point | 8 | 4 | 50 | 1 | `13003792` | yes | - |
| `40000D17` | Dooooooooom! | 4 | 4 | 49 | 1 | `13003785` | yes | - |
| `40000D18` | Power Relay Pro | 6 | 4 | 26 | 1 | `1300377D` | yes | - |
| `40000D19` | Raider Rustler | 8 | 4 | 44 | 1 | `1300377C` | yes | - |
| `40000E78` | Leviathan Sleeps | 4 | 4 | 60 | 1 | `1300379E` | yes | - |
| `40000E9D` | Lost Sector Explorer | 1 | 4 | - | 1 | `130037A0` | no | `4000013E` |
| `40000E9E` | Lost Sector Explorer | 1 | 4 | - | 1 | `130037A1` | no | `40000B6B` |
| `40000E9F` | Lost Sector Explorer | 1 | 4 | - | 1 | `130037A0` | no | `40000B6C` |
| `40000EA1` | Lost Sector Explorer | 1 | 4 | - | 1 | `130037A5` | no | `40000C82` |
| `40000EA2` | Lost Sector Explorer | 1 | 4 | - | 1 | `130037A1` | no | `40000399` |
| `40000EA3` | Lost Sector Explorer | 1 | 4 | - | 1 | `130037A5` | no | `40000E74` |
| `40000EA4` | Lost Sector Explorer | 1 | 4 | - | 1 | `130037A6` | no | `40000270` |
| `40000EA5` | Lost Sector Explorer | 1 | 4 | - | 1 | `130037A5` | no | `40000E68` |
| `40000EA6` | Lost Sector Explorer | 1 | 4 | - | 1 | `130037A6` | no | `40000B6A` |

### 3.6 Avatar (protector) icons [C]

134 records in `0xA00000D0` (`0x10000AB9 = 1`, image `0x100008F8`, strings `0x10000B77`-`0x10000B79` whose table
`0x2B0001BD` has no English text in the install). 66 of them are achievement rewards (52 champion-level icons, protector
level milestone icons `0x40000A9D`-`0x40000AA1`, ranked / misc icons). Header: `0x2190` (5 icon slots), `0x2154`
`(icon, slot)`; C->S `0x2093` UI_SetProtectorIcon `(u32 icon, u32 slot)` [C layout, P meaning].

| DID (0x40) | Image `0x100008F8` | Reward |
|---|---|---|
| `400005D4` | `13001929` | - |
| `400005D6` | `13001923` | - |
| `400005D7` | `13001928` | - |
| `400005D8` | `1300192A` | - |
| `400005D9` | `13001926` | - |
| `400005DA` | `13001927` | - |
| `400005DB` | `13001924` | - |
| `400005DC` | `13001290` | - |
| `400005DD` | `13001711` | - |
| `400005DE` | `13001710` | - |
| `400005DF` | `1300170F` | - |
| `400005E0` | `13001925` | - |
| `400005E2` | `1300187A` | - |
| `400005E3` | `13001879` | - |
| `400005E4` | `13001878` | - |
| `400005E5` | `13001877` | - |
| `400005E6` | `13001876` | - |
| `400005E7` | `13001875` | - |
| `400005E8` | `13001874` | - |
| `400005E9` | `13001873` | - |
| `400005EA` | `13001872` | - |
| `400005EB` | `13001871` | - |
| `400005EC` | `13001870` | - |
| `400005ED` | `1300186F` | - |
| `400005EE` | `1300186E` | - |
| `400005EF` | `1300186D` | - |
| `400005F0` | `1300186C` | - |
| `400005F1` | `1300186B` | - |
| `400005F2` | `1300186A` | - |
| `400005F3` | `13001869` | - |
| `400005F4` | `13001868` | - |
| `400005F5` | `13001867` | - |
| `400005F6` | `13001866` | - |
| `400005F7` | `13001865` | - |
| `400005F8` | `13001864` | - |
| `400005F9` | `13001863` | - |
| `400005FA` | `13001860` | - |
| `400005FB` | `1300185F` | - |
| `400005FC` | `13001862` | - |
| `400005FD` | `13001861` | - |
| `400005FE` | `1300185C` | - |
| `400005FF` | `1300185B` | - |
| `40000600` | `1300185A` | - |
| `40000601` | `13001859` | - |
| `40000602` | `13001858` | - |
| `40000603` | `13001857` | - |
| `40000604` | `1300185E` | - |
| `40000605` | `1300185D` | - |
| `40000606` | `13001856` | - |
| `40000607` | `13001855` | - |
| `40000608` | `13001854` | - |
| `40000609` | `13001853` | - |
| `400006F0` | `13001C71` | - |
| `40000812` | `130021C2` | - |
| `40000813` | `130021C1` | - |
| `40000814` | `130021C0` | - |
| `40000934` | `13002447` | - |
| `40000A6B` | `130026B0` | - |
| `40000A74` | `130026CA` | - |
| `40000A75` | `130026C9` | - |
| `40000A9D` | `1300241D` | yes |
| `40000A9E` | `1300241A` | yes |
| `40000A9F` | `13002421` | yes |
| `40000AA0` | `1300241C` | yes |
| `40000AA1` | `13002413` | yes |
| `40000AB4` | `13002A83` | - |
| `40000AB5` | `13002A84` | - |
| `40000AB6` | `13002A85` | - |
| `40000ABA` | `13002A8B` | - |
| `40000ABB` | `13002A8C` | - |
| `40000ABC` | `13002A8D` | - |
| `40000AE3` | `13002B08` | - |
| `40000BB9` | `13002CF3` | yes |
| `40000BBA` | `1300240E` | yes |
| `40000BBB` | `1300240C` | yes |
| `40000BBC` | `13002CF2` | yes |
| `40000D4B` | `130033DE` | - |
| `40000D75` | `1300197D` | yes |
| `40000DF0` | `130031EB` | yes |
| `40000DF4` | `13000B07` | yes |
| `40000DF5` | `13001652` | yes |
| `40000DF9` | `13002A64` | yes |
| `40000DFA` | `13001730` | yes |
| `40000DFB` | `130018A1` | yes |
| `40000DFD` | `1300077D` | yes |
| `40000DFF` | `1300112D` | yes |
| `40000E01` | `13001F72` | yes |
| `40000E03` | `13002FCA` | yes |
| `40000E07` | `130019EE` | yes |
| `40000E0B` | `1300169A` | yes |
| `40000E11` | `13001836` | yes |
| `40000E12` | `1300146E` | yes |
| `40000E15` | `13002B3F` | yes |
| `40000E16` | `13001C3A` | yes |
| `40000E17` | `13000FDE` | yes |
| `40000E18` | `13002D98` | yes |
| `40000E1D` | `13002F79` | yes |
| `40000E1F` | `1300011F` | yes |
| `40000E20` | `13001DC4` | yes |
| `40000E24` | `13002C9B` | yes |
| `40000E27` | `1300102C` | yes |
| `40000E2A` | `130030AA` | yes |
| `40000E2C` | `13000E6E` | yes |
| `40000E30` | `13003009` | yes |
| `40000E32` | `130014DA` | yes |
| `40000E33` | `13002EAB` | yes |
| `40000E34` | `13002BB7` | yes |
| `40000E35` | `1300243D` | yes |
| `40000E37` | `130028EC` | yes |
| `40000E38` | `13000CC4` | yes |
| `40000E39` | `1300238D` | yes |
| `40000E3B` | `13001CD3` | yes |
| `40000E3C` | `13003267` | yes |
| `40000E3D` | `130000B1` | yes |
| `40000E3E` | `13000C73` | yes |
| `40000E40` | `13002C90` | yes |
| `40000E41` | `1300130B` | yes |
| `40000E42` | `13000378` | yes |
| `40000E44` | `13002E1B` | yes |
| `40000E45` | `13002B2C` | yes |
| `40000E47` | `13000822` | yes |
| `40000E48` | `130021AE` | yes |
| `40000E49` | `13000F3C` | yes |
| `40000E4D` | `1300124F` | yes |
| `40000E4E` | `13001D2D` | yes |
| `40000E51` | `130008B4` | yes |
| `40000E52` | `130024C5` | yes |
| `40000E54` | `13003454` | yes |
| `40000E55` | `13003359` | yes |
| `40000F13` | `13002418` | yes |
| `40000F14` | `13003A27` | yes |
| `40000F15` | `13001290` | yes |
| `40000F16` | `13001290` | yes |
| `40000F17` | `13001290` | yes |

### 3.7 Account (protector) level [C data / G enum]

Level and XP are server data: `0x2080` `(level, prevLevel, xpToNext, xpTotal, xpEarned, xpBonus, f32 pct, f32
prevPct)`; `ProtectorAdvancementStatus` 1 Player / 2 Trainee / 3 FirstTimePlayer is computed by the client from the
trainee achievements (`scorecard.py`). No XP-per-level table exists in the data (scan of every record) [C]. The level
rewards are the 104 ProtectorLevel achievements (3.1): one per level 2-100, mostly 100 Merit, augment / mod Choice
groups every few levels, Merit + Coins + icon at 10/20/30/40/50.

`0x48000372` (`0x10000589` = 20 x {`0x1000058A` account level, `0x1000058C` enum}; `0x100006C0` = [13, 7, 4]):
level -> enum pairs below. The enum (1-25) is not one of the AS2 enums [G: features / UI unlocked at that level].

| Level `0x1000058A` | Enum `0x1000058C` |
|---|---|
| 1 | 24 |
| 3 | 15 |
| 5 | 25 |
| 10 | 8 |
| 20 | 16 |
| 30 | 1 |
| 40 | 11 |
| 50 | 12 |
| 50 | 10 |
| 50 | 6 |
| 55 | 17 |
| 55 | 2 |
| 60 | 5 |
| 70 | 3 |
| 80 | 18 |
| 90 | 20 |
| 150 | 7 |
| 200 | 13 |
| 210 | 4 |
| 175 | 23 |

### 3.8 Ranked standings [C data / P use]

`0x4800155F`: tiers (`0x10000DD5`: `0x10000DD8` RankedDisplayTier, `0x10000DD2` lowest team index of the tier) and 21
standings "teams" (`0x10000DBB`: `0x10000DB9` index 20..1 (+ top team with none), `0x10000DB7` name, `0x10000DE2`
mascot champion, `0x10000DBC` points threshold [P], `0x10000DBF` 2/3/4 [G], icons `0x10000DB6` / `0x10000DD9`,
quote string `0x10000DD4` (not reproduced)). Events: `0x219F` (static standings rebuilt by the client from data,
handler `0xa5c840` reads a table `0x100000FA`), `0x219E` account standings 10 x u32; C->S `0x2178`
RequestAccountStandingsData, `0x2193` RequestStaticStandingsData; leaderboards `0x21A2` / `0x21A3` (C->S `0x21A4`).

| Tier `DD8` | Name | `DD2` |
|---|---|---|
| 4 | Bronze Tier | 20 |
| 3 | Silver Tier | 15 |
| 2 | Gold Tier | 5 |
| 1 | Diamond Tier | None |

| `DB9` | Team `DB7` | Champion `DE2` | `DBF` | `DBC` | Icon `DB6` | Icon `DD9` |
|---|---|---|---|---|---|---|
| 20 | The Booster-Maniacs | - | 2 | None | `130039E1` | `13003A7A` |
| 19 | The Contract Killers | `40000C19` Deathstroke / The Terminator | 2 | 3 | `130039DE` | `13003A77` |
| 18 | The Soaring Defenders | `40000AE2` Hawkgirl / Winged Defender | 2 | 6 | `130039D8` | `13003A72` |
| 17 | The Reach Rebels | `400007FA` Blue Beetle / Reach Infiltrator | 2 | 9 | `130039E2` | `13003A7B` |
| 16 | The Suicide Squad | `4000054A` Harley Quinn / Mad Love | 2 | 12 | `130039D9` | `13003A73` |
| 15 | The Future Leaders | `4000052D` Robin / Young Detective | 3 | 15 | `130039D3` | `13003A6E` |
| 14 | The Lords of Atlantis | `400005C6` Aquaman / Lord of Atlantis | 3 | 19 | `130039E5` | `13003A7E` |
| 13 | The Red Lantern Corps | `40000932` Atrocitus / Survivor of Sector 666 | 3 | 23 | `130039E4` | `13003A7D` |
| 12 | The Green Lantern Corps | `4000034D` Green Lantern / Fearless Maverick | 3 | 27 | `130039DA` | `13003A74` |
| 11 | The Sinestro Corps | `40000805` Sinestro / The Fallen Lantern | 3 | 31 | `130039D1` | `13003A6D` |
| 10 | The House of Zod | `40000D29` Zod / Kryptonian Tyrant | 3 | 35 | `130039CC` | `13003A6A` |
| 9 | The Corporate Masters | `40000B70` Lex Luthor / The Greatest Mind of Our Time | 3 | 39 | `130039D5` | `13003A6F` |
| 8 | The Gotham Sirens | `4000041C` Catwoman / Feline Fatale | 3 | 43 | `130039E0` | `13003A79` |
| 7 | The A.R.G.U.S. Agents | `400003B2` Cyborg / Human Arsenal | 3 | 47 | `130039DF` | `13003A78` |
| 6 | The Emerald Archers | `400006F9` Green Arrow / Emerald Archer | 3 | 51 | `130039DB` | `13003A75` |
| 5 | Flash's Family | `40000396` Flash / The Fastest Man Alive | 4 | 55 | `130039DC` | `13003A76` |
| 4 | The Amazonian Warriors | `40000260` Wonder Woman / Ambassador of Peace | 4 | 60 | `130039CE` | `13003A6B` |
| 3 | Joker's Gang | `40000213` The Joker / Clown Prince of Crime | 4 | 65 | `130039D7` | `13003A71` |
| 2 | The Gotham Knights | `40000280` Batman / The Dark Knight | 4 | 70 | `130039E3` | `13003A7C` |
| 1 | The House of El | `4000002B` Superman / Man of Steel | 4 | 75 | `130039CF` | `13003A6C` |
| None | The Justice League | - | None | 80 | `130039D6` | `13003A70` |

### 3.9 Statistics (account stats, scoreboard, accolades share them) [C]

`0x48001172` (`0x10000C40`): 59 statistics, each `0x10000C3D` id, `0x10000C3E` key name, `0x10000C3C` / `0x10000CEE`
/ `0x10000C57` labels, `0x10000C47` encounters where it applies (count below), `0x10000C9A` flag (1 = per match [P]),
`0x10000CED` (objective stats). Id 25 is unused.

| Id | Key | Encounters | `C9A` |
|---|---|---|---|
| 1 | TimeSpentDeadStat | 9 | 1 |
| 2 | TurretsCapturedStat | 2 | - |
| 3 | PowerDamageTakenFromChampionsStat | 9 | 1 |
| 4 | OrbitalCannonCapturesStat | 2 | 1 |
| 5 | AttackDamageReducedFromChampionsStat | 9 | 1 |
| 6 | QuadraKillsStat | 9 | 1 |
| 7 | CreditsStompedStat | 9 | 1 |
| 8 | CreditsEarnedFromObjectivesStat | 9 | 1 |
| 9 | CreditsEarnedFromCreaturesStat | 7 | 1 |
| 10 | CreditsEarnedFromChampionsStat | 9 | 1 |
| 11 | CoinsCollectedStat | 9 | 1 |
| 12 | ExperienceEarnedStat | 9 | 1 |
| 13 | DroneKillsStat | 9 | 1 |
| 14 | DestructionCausedStat | 9 | 1 |
| 15 | AttackDamageDealtStat | 9 | 1 |
| 16 | DoomsdayDeviceActivationsStat | 2 | - |
| 17 | ControlPointsCapturedStat | 2 | 1 |
| 18 | PentaKillsStat | 9 | 1 |
| 19 | HealingReceivedStat | 9 | 1 |
| 20 | CreditsEarnedFromDronesStat | 9 | 1 |
| 21 | PowerDamageDealtStat | 9 | 1 |
| 22 | AssistsStat | 9 | 1 |
| 23 | AttackDamageTakenFromChampionsStat | 9 | 1 |
| 24 | ExperienceFromCreaturesStat | 7 | 1 |
| 26 | PowerRelaysCapturedStat | 2 | 1 |
| 27 | DamageTakenStat | 9 | 1 |
| 28 | ExperienceFromChampionsStat | 9 | 1 |
| 29 | DampenersDisabledStat | 5 | 1 |
| 30 | DeathsStat | 9 | 1 |
| 31 | DamageDealtStat | 9 | 1 |
| 32 | TurretsDestroyedStat | 7 | 1 |
| 33 | TripleKillsStat | 9 | 1 |
| 34 | ExperienceFromObjectivesStat | 9 | - |
| 35 | PowerRelayControlTimeStat | 2 | - |
| 36 | BeaconsDeployedStat | 5 | 1 |
| 37 | ExperienceFromDronesStat | 9 | 1 |
| 38 | PowerDamageReducedFromChampionsStat | 9 | 1 |
| 39 | DamageReducedStat | 9 | 1 |
| 40 | CreditsEarnedStat | 9 | 1 |
| 41 | CreatureKillsStat | 7 | 1 |
| 42 | DestructionValueStat | 9 | - |
| 43 | ChampionKillsStat | 9 | 1 |
| 44 | RaiderKillsStat | 4 | 1 |
| 45 | PowerDamageDealtToChampionsStat | 9 | 1 |
| 46 | HealingDoneStat | 9 | 1 |
| 47 | DoomsdayGuardiansDestroyedStat | 2 | 1 |
| 48 | TurretsNeutralizedStat | 2 | - |
| 49 | DoomsdayDeviceFiredStat | 2 | 1 |
| 50 | ControlPointsNeutralizedStat | 2 | 1 |
| 51 | DamageTakenFromChampionsStat | 9 | 1 |
| 52 | AttackDamageDealtToChampionsStat | 9 | 1 |
| 53 | MatchesPlayedStat | 2 | - |
| 54 | MatchesWonStat | 2 | - |
| 55 | AverageKDAStat | 9 | - |
| 56 | KDRatioStat | 9 | - |
| 57 | MaxLevelChampionsStat | 2 | - |
| 58 | MostPlayedChampionStat | 2 | - |
| 59 | MostWinsChampionStat | 2 | - |
| 60 | LeviathanKillsStat | 2 | 1 |

Account stats pages (`0x2115` per-encounter rows; C->S `0x2116`), scoreboard grids and the five columns:

- `48000F06`: Offense=31,15,52,21,45,43,30,22,33,6,18,13,41 / Defense=27,51,23,3,46,19,39,5,38,1 / Advancement=11,7,40,10,20,9,8,12,28,37,24,34 / Sector Objectives=50,17,4,47,49,26,32,29,36,41
- `48000F92`: Offense=31,15,52,21,45,43,30,22,33,6,18,13,41 / Defense=27,51,23,3,46,19,39,5,38,1 / Advancement=11,7,40,10,20,9,8,12,28,37,24,34 / Sector Objectives=50,17,4
- `48000F93`: Offense=31,15,52,21,45,43,30,22,33,6,18,13,41 / Defense=27,51,23,3,46,19,39,5,38,1 / Advancement=11,7,40,10,20,9,8,12,28,37,24,34 / Sector Objectives=32,29,36,44,60
- `48000F95`: Offense=31,15,52,21,45,43,30,22,33,6,18,13,41 / Defense=27,51,23,3,46,19,39,5,38,1 / Advancement=11,7,40,10,20,9,8,12,28,37,24,34 / Sector Objectives=47,49,26,32,44
- `48000FB0`: General=31,15,52,21,45,43,30,22,33,6,18,13,41,27,51,23,3,46,19,39,5,38,1,11,7,40,10,20,9,8,12,28,37,24,34,50,17,4,47,49,26,32,29,36,41
- `480012A4`: Offense=31,15,52,21,45,43,30,22,13,41 / Defense=27,51,23,3,46,19,39,5,38,1 / Advancement=11,7,40,10,20,9,8,12,28,37,24,34 / Sector Objectives=32,29,36
- `48000E29` columns: 32,17,50,42,7
- `48000E2B` columns: 11,36,32,29,7
- `48000E2C` columns: 11,50,17,4,7
- `48000F94` columns: 49,26,47,32,7
- `480012A3` columns: 11,36,32,29,7
- `48000D44` page "Global Stats": 53,54,43,30,22,55,56,57,58,59,13,41,33,6,18,31,27,39,46,19,44,60,17,26,32,16,29,36,11
- `48000D45` page "Gotham Divided Stats": 53,54,43,30,22,55,56,13,41,44,60,33,6,18,31,27,39,46,19,29,36,11
- `48000D46` page "Coast City Stats": 53,54,43,30,22,55,56,13,41,33,6,18,31,27,39,46,19,44,26,32,16,11
- `48000D47` page "Gotham Heights Stats": 53,54,43,30,22,55,56,13,17,33,6,18,31,27,39,46,19,4,11
- `48001598` page "": 53,54,43,30,22,55,56,13,41,31,27,39,46,19,32,11

---

## 4. End of match [C unless marked]

| Step | What | Data behind it |
|---|---|---|
| 1 | In-world result `0x100002EB` ShowAnnouncement (9 Win / 8 Loss / 7 Tie / 10, 11 team) | - |
| 2 | `0x1000000E` match ended notice + `0x2038` | - |
| 3 | `0x2045` end-of-match stats -> `UI_SendEndOfMatchStats(accountIIDs, playerIIDs, icons, names, protectorChampLevels, isBot, isFriend, isIgnored, inMatchLevels, teams, kills, deaths, assists, currency, coinPickups, amplifiers, column1..5, scorecardGridLabels / section flags / tooltips, grid values players 1-10, team sums, yourIID, ...)` | **column1..5 = the 5 stat ids of the map's column record** (`0x48000E29` etc.: e.g. 11 CoinsCollected, 36 BeaconsDeployed, 32 TurretsDestroyed, 29 DampenersDisabled, 7 CreditsStomped) and **the grid = the map's `0x10000B28` record** (Offense 13 stats, Defense 10, Advancement 12, Sector Objectives 3-10) [P: which map uses which record is not read; the section stats match the map objectives] |
| 4 | Scorecard prerequisites: `0x2190`, `0x2045`, `0x2188`, `0x2080`, `0x2081`, `0x20B9`, `0x2104`, `0x2090`, `0x219F` / `0x219E` (+ `0x20E2` power graph / current upgrades outside tutorials) | `scorecard.py` |
| 5 | Account XP / level `0x2080`, champion XP / level + accolades `0x2104`, Merits `0x20B9` + balance `0x2081` | none in data: amounts are the server's |
| 6 | Accolades `0x2188`: up to N of the 46 per-match accolades, ranked by the stat (`0x10000C6A`) and medal (Gold/Silver/Bronze); first match on a map -> the `0x48001490` accolade | 3.5 |
| 7 | Achievements `0x2120` (progress), then on the end page `0x212E` -> `0x211F`, `0x2124` -> `0x2125` (reward sets), claim `0x2128`, ribbon `0x2095` | 3.1, 3.2, `reward_re.txt` |
| 8 | Back home `0x2021`; client `0x20A6`, `0x20C4`, `0x20BA` | - |

**XP per match:** not in the data [C]. The only account-XP items are `0x48000F31` (flat) / `0x48000F30` (percent),
given x1 by the training reward sets (so their unit is server-defined). Stats 12 ExperienceEarned, 24/28/34/37
Experience From Creatures / Champions / Objectives / Drones are the in-match XP sources the server tracked.

---

## 5. Stolen Powers [C]

Catalog `0x480003CD` (`0x10000842` = 12 groups `0x10000841`, members `0x10000840`; first = base power). The skill
block `0x1000003F`: `0x100001C0` name, `0x1000083D` power type 1-12 (= group + 1), `0x10000302` icon. Every one of the
53 champion versions has `0x10000922` {`0x10000920` unlock string}: **unlocks at champion level 5 when the champion is
owned**; base powers have no unlock rule (always available) [C: 53/53 and 0/12]. John Stewart (`0x10000CE5`) points at
the base Meteor Drop `0x480005A2` (no own version); every other champion has exactly one version. Default pairs: the
loadout `0x1000064E` (count of loadout records using each power in the last column). Lobby protocol: C->S `0x2017`
RequestStolenPowerList `(u64, u32)`, `0x2064` RequestMyStolenPowers (empty), `GM_Lobby.SendNotice_RequestChangeStolenPower`;
S->C `0x2029` / `0x2060` (PlayerPickedStolenPowers fields `didStolenPowerOne/Two`). Ownership via `0x20B8` ContentType 2
[P].

| Group | Power type `0x1000083D` | Base power | Versions (DID, owner champion, unlock rule `0x10000922`) | In default pairs (count) |
|---|---|---|---|---|
| 0 | 1 | `4800056E` Consume (unlock: none) | `48000815` Atomic Green Lantern (lvl5+owned); `48000841` Nightmare Batman (lvl5+owned); `48000A3F` Mecha Superman (lvl5+owned); `48000F3C` Stargirl (lvl5+owned); `48000F9B` Swamp Thing (lvl5+owned) | 48000815=2 48000841=3 48000A3F=3 48000F9B=3 |
| 1 | 2 | `4800055F` Detonate (unlock: none) | `48000E21` Atomic Joker (lvl5+owned); `4800109F` Deathstroke (lvl5+owned); `48000872` Harley Quinn (lvl5+owned); `4800080C` The Joker (lvl5+owned) |  |
| 2 | 3 | `480007A8` Healing Wave (unlock: none) | `48000869` Arcane Green Lantern (lvl5+owned); `48001003` Krypto (lvl5+owned); `48000846` Poison Ivy (lvl5+owned) | 480007A8=26 48000869=3 48001003=3 48000846=3 |
| 3 | 4 | `48000780` Invulnerability (unlock: none) | `48000813` Doomsday (lvl5+owned); `48000FB1` Katana (lvl5+owned); `4800080E` Shazam (lvl5+owned); `48000D2C` Supergirl (lvl5+owned) | 48000780=40 48000813=3 48000FB1=1 4800080E=3 48000D2C=3 |
| 4 | 5 | `480005A2` Meteor Drop (unlock: none) | `48000863` Gaslight Joker (lvl5+owned); `4800085F` Green Lantern (lvl5+owned); `48000D28` Atrocitus (lvl5+owned); `48000F05` Arcane Supergirl (lvl5+owned); `48001333` Zod (lvl5+owned) | 480005A2=8 48000863=1 4800085F=3 48000D28=3 48000F05=3 |
| 5 | 6 | `48000785` Psychic Assault (unlock: none) | `4800131B` Arcane Harley Quinn (lvl5+owned); `48001060` Arcane Zatanna (lvl5+owned); `48001160` Raven (lvl5+owned); `48000BF2` Sinestro (lvl5+owned); `480009EE` Star Sapphire (lvl5+owned); `48000EF2` Starro (lvl5+owned); `48000852` Zatanna (lvl5+owned) | 48000785=9 4800131B=3 48001060=3 48001160=1 48000852=1 |
| 6 | 7 | `480003CB` Super Strength (unlock: none) | `48000913` Aquaman (lvl5+owned); `480012B6` Nightmare Catwoman (lvl5+owned); `480010E3` Solomon Grundy (lvl5+owned); `48000A3B` Superman (lvl5+owned); `4800081D` Wonder Woman (lvl5+owned) | 480003CB=43 48000913=3 480012B6=3 480010E3=3 48000A3B=4 4800081D=3 |
| 7 | 8 | `48000529` Super Speed (unlock: none) | `48000868` Atomic Wonder Woman (lvl5+owned); `48000807` Flash (lvl5+owned); `48000F57` Hawkgirl (lvl5+owned) | 48000529=56 48000868=4 48000807=3 48000F57=3 |
| 8 | 9 | `48000523` Surveillance Camera (unlock: none) | `48001114` Deadshot (lvl5+owned); `48000808` Gaslight Batman (lvl5+owned); `48000AA3` Green Arrow (lvl5+owned); `48000876` Robin (lvl5+owned) | 48000523=58 48000808=1 48000876=2 |
| 9 | 10 | `48000809` Teleport (unlock: none) | `4800080A` Catwoman (lvl5+owned); `48000867` Cyborg (lvl5+owned); `48001253` Dex-Starr (lvl5+owned); `48000A8F` Nightmare Superman (lvl5+owned) | 48000809=3 4800080A=3 48001253=3 |
| 10 | 11 | `480007AC` Trap (unlock: none) | `48000804` Batman (lvl5+owned); `48001298` Huntress (lvl5+owned); `48000FD8` Lex Luthor (lvl5+owned); `4800086C` Mecha Wonder Woman (lvl5+owned); `48001466` Nightwing (lvl5+owned) | 480007AC=3 48001466=3 |
| 11 | 12 | `48000549` X-Ray Vision (unlock: none) | `4800088F` Atomic Poison Ivy (lvl5+owned); `48000A8C` Blue Beetle (lvl5+owned); `48000854` Gaslight Catwoman (lvl5+owned); `48000D42` Nightmare Robin (lvl5+owned) |  |

---

## 6. Open questions

- The C->S events of the store (`UI_PurchaseContextualItem`), the login reward (`QueueLoginReward`,
  `ReadyForLoginRewardSet`) and `UI_RequestBestAccolades`: their senders are not in the inline-built event list
  (`cs_send` scan: 55 client events built inline; candidates with unknown purpose `0x2089`, `0x20BF`, `0x20C3`,
  `0x20D3`, `0x2156`, `0x21A8` (empty bodies), `0x207A` / `0x20F1` (u8), `0x20D5` / `0x2140` / `0x2160` (u32)).
- Meanings of `0x10000B23` (augment stat grade), `0x10000A1C`, `0x10000D96`, `0x10000CD4`, `0x10000CD5`, `0x10000C68`,
  `0x10000DBF`, `0x1000058C` (account level unlock enum) and `0x100006C0`.
- Which scoreboard grid / column record each map uses (the encounter template probably points to them; not read).
- Whether `0x200D` slot 0 selects the champion's default set (Flash passes the default-set DID but the wire has only the
  slot byte).
- The amounts the original server used (XP curve, XP / Merits per match, daily first win, streaks, prices): absent from
  the client data.
