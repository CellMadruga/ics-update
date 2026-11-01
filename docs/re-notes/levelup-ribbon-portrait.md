# The "Champion Level Up!" popup's portrait: a picture in an unloaded pack (2026-10-30, tester report 15:30)

Trigger: tester screenshot after a Crime Alley v AI match (Atomic Green Lantern costume `0x4000080C`, level 2 -> 3):
the popup on the home screen shows "3" and the name, the portrait box is black. Same complaint as 2026-10-29 12:45
(`unit-death-slide-levelup.md` 3), which made ics send `tex384` instead of 0.

## Evidence

* Traffic 16:58:55.719 (`logs/traffic.log`, run 16:37-16:58): `0x2104` = `u8 0 | 0x4000080C | 0x13001650 | "Atomic
  Green Lantern" | 3 | 2 | ...`; the icon field carried AGL's `tex384` (`data/champions.json`, the light record's small
  icon). So the field was filled, the picture just did not draw.
* AS2 (C): `WrapperMain.RecvNotice_Ribbon_CharLevelChanged(i_didCharacterIcon, ...)` -> `CharLevelUpRibbonData.didIcon`
  -> `CharLevelUpRibbon.SetData`: `m_icAccountIconContainer.SetIcon(didIcon)` (`utils.IconContainer` ->
  `utils.Icon.SetIcon`: `SetBgImage(did)` for any valid DID, no lookup of its own). At
  `OwnablesManager.ICON_REWARD_CHAMPION_LEVEL` the same DID is also shown as the account-icon reward.
* Pack DID tables (C, scan of the install's `rp\*.rp` id lists):

  | DID | field | packs |
  |---|---|---|
  | `0x13001650` | tex384 | `0xA000014F` only (AGL's light pack) |
  | `0x13001653` | tex799 | `0xA000014F` only |
  | `0x13001652` | grid_icon | `0xA00000D0` (UI pack), `0xA0000103` |
  | `0x13001659` | wallpaper | `0xA000014E` (wallpaper pack; the home screen shows it) |

  Over the roster's 54 grid icons: 54 in `0xA0000103`, 52 in `0xA00000D0`.
* The popup shows after the client left the world (menu). The champion's light pack belongs to the match, so the
  texture `0x13001650` is not resolvable there (P: the kill card, in the world, draws the same `tex384` fine). The grid
  icon is the champion grid's picture, drawn in the same menus.

## Fix

`[ics] level_up_icon` default `"grid_icon"` (was `"tex384"`, fase3-ih..fase3-ir); `ics/matchend.py champion_icon`
default follows. Costumes have no own grid icon in `data/champions.json` (AGL's two costumes repeat `0x13001652`), so
the champion's one is sent. The summary tab's champion portrait (`ScorecardManager.DidCharIcon`) takes the same field.

## Open

* **P**: which DID the original server sent (grid icon vs a dedicated account icon); the box is a square portrait and
  the grid icon is one. If it looks cropped or wrong, `level_up_icon = "tex384"` restores the old value.
* **P**: that pack residency is the reason (not proven in the exe's texture loader); the tester's next popup confirms.
* The tutorial's `0x2104` (`icserver/scorecard.py`) is unchanged.
