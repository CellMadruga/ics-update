# Profile customization (protector icons) — research notes

Status: in progress. Tags: C confirmed, P probable, G guess.

## 1. Known from earlier notes

- Avatar / protector icon records: `0x10000AB9 = 1` (+ `0x100008F8` image, `0x10000B77..79` strings), DIDs
  `0x490005D4`-`0x49000F17`, **134** records, pack `0xA00000D0`; 66 of them are given by reward groups
  (account-systems-data.md §0, §2.1) [C].
- Ownership: `0x20B8` ownables, ContentType 3 AvatarIcon [C].
- Selection: client `0x2093 u32 icon DID | u32 index` (UI_SetProtectorIcon) -> server `0x2154 u32 | u32` or a full
  `0x2190` (header name + 5 icon DIDs + names/descriptions) (full-account-social.md §7) [C/P].

## 2. What ics does today

- `ics/account.py`: `profile = {"icons": [0]*5, "status": ""}`; `ownable_items()` sends champions, skins, amplifiers,
  Stolen Powers, and only the icons in `owned` (grant() falls back to CT_ICON). `data/accounts/Player.json`:
  `owned` is empty -> **no icon is sent as owned** -> the picker has nothing.
- `ics/session.py` `ev_set_protector_icon` (0x2093) stores `icons[index]` and answers `0x2154`.
- `ics/matchend.py` sends `0x2190` (header + icons) with `account.d["profile"]["icons"]`.

## 3. Client Flash side (movie `0xA00000D0` package `c_a00000d0_02189b08`, `__Packages/gameplay/...`) [C]

- **Profile card = `dialogs.CallingCardDialog`** (opened from the header profile). Shows name, account level, XP bar
  and **5 icon slot buttons** (`m_btSubMenuButton0..4`) + `m_ccDisplay` (the 5 current icons). It is the only
  customization the profile offers: no banners / titles / status picker exist in this dialog (the status message is
  `SelfPresenceDisplay` -> `GM_Contacts.UI_AddStatusMessage`, social; ranked banners are standings display only).
- Listens `UI.SendHeaderNameAndProtectorIcons(name, aIconDIDs, aNames, aDescs, aUnlockDescs)` (from `0x2190` /
  `0x2154`) and `Character.SendAccountLevelAndXP`.
- **Icon list = ownables**: `OnItemStatusesChange()` takes `OwnablesManager.GetAllOwnableDatasOfType(AvatarIcon=3)`
  (from `0x20B8`), prepends an empty "none" entry, maps each ownable DID (`didIconWC`) to its image with
  `ProtectorIconManager.GetIconData(did)`. Refreshes on incremental `0x20B8` containing a type-3 item.
- `ProtectorIconManager` builds its table once from C++ query `GM_Character.SendQuery_RequestProtectorIcons`
  (`0x1000047D`, no wire traffic): parallel arrays `aProtectorIconWCs` (item DIDs), `aProtectorIconDIDs` (images),
  names, descs, unlock descs. So the table comes from the client's own data; the server only says which WCs it owns.
- `ProtectorIconSubmenu`: 4 columns of 80x80 buttons; an icon is **listed** unless
  `CalculateOwnableUIState(status, owned, inViewMatch)` gives UNLISTED / UNDEFINED; **clickable** only when OWNED or
  FREE (else error sound). Slot 0 hides the "none" entry (slot 0 must always hold an icon; 1-4 can be cleared).
- Click -> `CallingCardDialog.SetProtectorIcon(GetIconWC(image), slot)` -> `GM_Character.UI_SetProtectorIcon`
  (`0x1000047E`, `didNewIconWC, uIndex`) -> wire `0x2093 u32 WC DID | u32 slot`. Note: **the WC (item) DID**, not
  the image. The dialog shows the change only when a header notice comes back.

## 4. The icon table in the data [C]

- C++ query handler for `RequestProtectorIcons` = `FUN_00a40ef0`: reads config `0x10000093` -> property
  **`0x10000848`** (array); for each entry (`0x10000847` = WC DID) calls `FUN_0086dba0` which reads the WC's
  record: `0x100008F8` image (`0x13......`), `0x10000B79` name, `0x10000B78` desc, `0x10000B77` unlock desc.
- That list is record **`0x48000803`** in pack **`0xA00000D0`** (file offset `0x1CD0A78`): `0x48000803 | 0 | 1 |
  0x10000848 | 0x86 (134) x {0x10000847, WC}`. 134 distinct WCs `0x400005D4`-`0x40000F17` (first `0x40000AE3`);
  every one has `0x10000AB9 = 1` and an image. These WCs are the **ownable DIDs** (`0x20B8` type 3, reward-group
  items) and the values carried by `0x2093` / `0x2154` / `0x2190`.
- `FUN_0086dba0(wc, index, ...)`: if index == 0 and the WC is invalid, it falls back to a default WC read from a
  game config (`0x10000036`, kind `0xB`) -> slot 0 always shows something [C code, default value not read].
- Header store (`FUN_00a571a0` = `0x2154`: `icons[slot] = wc` if slot < count; `FUN_00a57200` = `0x2190`: 5 WCs +
  2 u32 at +0xC8/+0xCC + 2 StringInfo + u32/u8 into another object) then `FUN_00a56560` -> `FUN_00a3f340` turns
  every stored WC into (image, name, desc, unlock) and raises `UI.SendHeaderNameAndProtectorIcons`. So **the server
  sends WCs, never images**; names come from the client data.

## 5. Where the chosen icons show [C unless tagged]

- Header (`HeaderProfile`), calling card, `SelfPresenceDisplay`, `TraineeAchievements`: all 5 from the header notice.
- End-of-match scorecard: `ScorecardManager` waits for the header notice (it is one of its prerequisites) and uses
  `aIconDIDs[0]` for `AccoladesProtectorDisplay`; `AccoladeManager` also stores icon[0] for accolade cards.
  `PlayerRowData.didAccountIcon` exists but nothing sets it.
- Level-up ribbon (`LevelUpRibbonData` account icon), reward ribbons (`RewardGrant/ChoiceAccountIcon` map a reward WC
  through `GetIconDID`).
- Contacts: `Contact.SetAccountIcons(5 WCs)` (contact list `0x203B` entries, `0x20EC` icon changed). Group
  `0x217D` / custom match `0x217C` `UpdateProtectorIcon(iidAccount, WC)`; custom match roster `0x2012` / data
  carry an icon per player (ics `lobby.py` sends 0) [WC: P].
- **Not shown**: the in-match Tab scoreboard (`0x1000005B` rows have no icon field), the loading curtain
  (`gameplay.lobby.Curtain` / `TeamDisplay`: champions + load %), the HUD. Nothing to send there.
- Status message (`SelfPresenceDisplay` -> `GM_Contacts.UI_AddStatusMessage`) is the only other profile text;
  ics has `profile.status` for it (social, separate).

## 6. Ownership states (`OwnablesManager.CalculateOwnableUIState`) [C]

owned + Available/AlwaysOwned/Innate/Hidden -> OWNED (clickable); Free -> FREE (clickable); not owned +
Available -> PURCHASABLE (listed, locked: error sound, tooltip shows the unlock text); not owned + Hidden ->
UNLISTED (not shown); Unavailable -> UNAVAILABLE.

## 7. Gaps in ics and recipe

1. `0x20B8`: add the 134 WCs of `0x48000803` as ContentType 3, status Available (2), owned = config
   (`own_all_icons`, default true) or `owns(wc)`; count 1. Read the list from the data (records.get(record
   0x48000803, 0x10000848)) - add an `adata.protector_icons()` next to `amplifiers()`. Unowned + Available show
   locked with their unlock text (progression mode). [C]
2. `0x2093`: keep storing `icons[slot] = wc`; validate wc in the list (or 0 for slots 1-4), owned unless
   own_all_icons; on reject resend `0x2154` with the old value. Save Player.json. [C]
3. Answer stays `0x2154 u8 0 | u32 wc | u32 slot` (client stores it and refreshes every header listener). [C]
4. New accounts: icons `[0,0,0,0,0]` works (slot 0 falls back to the client default) but an explicit default
   (e.g. the first list entry `0x40000AE3`) makes the scorecard / accolades show a picture [P].
5. `0x2190` at login (`_login_extras` header_again) and at match end already carry `profile.icons`. [C]
6. Reward-granted icons (achievement / champion level 20) already go through `grant()` -> CT_ICON; when
   own_all_icons is false they become owned and the incremental `0x20B8` refreshes the picker. [C]
7. Optional: custom-match / group rosters send `icons[0]` instead of 0. [P]
