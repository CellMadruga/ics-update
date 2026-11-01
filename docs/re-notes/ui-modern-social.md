# Modern UI, area "social": custom match lobby, group screen, chat, friends (2026-10-30)

Builds on `ui-modern-build.md` (pipeline, module convention, section 8) and `ui-complete.md` (classes). Four movie
modules; nothing here has run in the real client yet (tester's step, section 5). Design: the approved canvas (navy
`#0A1220`, panels `#0F1B2E` ~70 %, accent `#2FA8FF`, green `#6FD08C`, gold `#F2B33D`, red `#E5484D`, grey).

Tags: **[C]** confirmed (decompiled library / the movies / a run in the test VM), **[P]** probable, **[G]** guess.

## 0. Short version

| Movie | Module | Modern |
|---|---|---|
| `0x20000093` custom match | `ui/modern/movies/0x20000093_custom_match/` | header strip `HOST <name>   <n>V<n>` + map name, panels behind both team columns (blue / red rule), bench, invite list and chat; slot cards (team-colour bar, portrait glow fading right) with HOST / READY / AI tags; OPEN slot cards up to the team size; PENDING / JOINED / DECLINED tags in the invite list; big pointed plate behind START, START tinted accent; Legacy backdrops darkened / faded |
| `0x20000082` group screen | `.../0x20000082_group/` | same family: panels, slot cards with HOST / READY, OPEN for the empty of the 5 fixed slots, invite tags PENDING / JOINED / LEFT / DECLINED, pointed plate behind LAUNCH |
| `0x20000083` chat | `.../0x20000083_chat/` | panel behind the chat log, the click blocker made transparent; chat button tinted accent with a red unread badge |
| `0x2000008B` contacts | `.../0x2000008B_contacts/` | friends panel on our panel; selected-list underline; `<n> ONLINE` count; friend cards with the design's presence colours (dot + text), name white, pointed plate behind the per-friend Invite button |

Shared by the four (first in the custom match folder, now in `ui/modern/common/` (integrated 2026-10-30, `ui-modern-build.md` 10)): `social_art.py` (art: `tag`, `card`, `open_slot`, `panel`, `plate`, `badge`, `underline`,
a 4 x 6 stroke font `word()` so status words are vector shapes, no font or text widget; tint constants) and
`social.as` (AS2 helpers `ics_Tint / Accent / Darken / Fade / AtDepth / Colour / Uncolour / Fit / ShowOne / Hide /
Reveal`). Test: `python tests\test_ui_social.py` (557 checks).

## 1. What the movies allow [C]

- Every behaviour is library code bound by instance name; the edits only add placements at free depths and one frame-1
  script per exported symbol. Instance names, clip actions, `stop()`, exports and registerClass init actions are kept
  byte-identical (tested).
- **Depth limits.** A new art can only go *behind* an original if a free depth exists below it. Where depth 1 holds
  the Legacy background (CustomMatchScreen, InviteDisplay, HoldingPen, GroupDisplay, the team columns,
  ContactsComponent), the Legacy art is faded / darkened by script and our panel is drawn in the parent symbol behind
  the whole widget. Cards use depth 2 (between the hover highlight `m_mcBackgroundLit` at 1 and the name at 3).
- **Unnamed Legacy backgrounds** are reached with `MovieClip.getInstanceAtDepth(d)` (FP7 AS2) [P: GFx support not
  checked in game; when it is missing the helper returns undefined and the background just stays].
- **The chat log is native** [C]: `Chat.m_wcChat` is `UIWidget_Chat` imported from `0x20000000`; the engine draws the
  lines and input (`ChatManager.RegisterChatWidget`, `ExSetDescPos`, UIL descriptor). Flash cannot restyle lines:
  **no bubbles, no per-conversation windows, no INVITE / minimise / close header, no minimised tabs** — the client
  has one log with channels (General / Team / CustomMatch / whispers), not conversations. Modern frames it.
- **Tabs Friends / Channels / Requests**: the client's friends panel has Online / Offline / Ignored list buttons
  (`ContactsPanelHeader`) and a notifications view (friend / group / custom-match invites = "requests") switched by
  `ContactsNotificationsTabButton` / `MainTabButton`, which are placed outside this movie's ContactsComponent [P].
  Channels are chat-log types (native). Modern keeps the client's tabs and underlines the selected one.
- **Unread badge on friends**: there is no per-friend unread state; the notifications count lives in the 41-frame
  `ContactsNotificationsTabButton` (not edited: a timeline that re-enters frame 1 would re-run our script; possible
  later). The chat button's unread state (`Chat.ToggleUnreadChat` -> `ChatButton.ToggleUnreadChat`) gets the red badge.
- **Custom match: no ready check, no "Add AI" / "Join team" buttons in the client** [C]: bots come from the encounter
  (`FillTeamOneWithBots`), players move with the existing arrows `m_btAssignTeam1/2` (kept) and the player submenu.
  READY therefore means "a player in a team"; INVITED shows in the invite list as PENDING. The per-friend Invite
  buttons are the contacts panel's `ContactDisplay.m_btInvite` (invite mode), which get the pointed plate.
- Text: our two header labels are new `UIWidget_Text` instances (clones of `StartMatchError.m_wtStartMatchHint`'s
  character with our own `on(construct)`: template `TitleRegularTinyLeft`, white), sized with `setSize`; the online
  count is a copy of the header title. No new font: the Rajdhani-like look is only in the vector tags.

## 2. Per symbol (Modern; Legacy = our clips hidden, every changed original put back)

### 0x20000093 custom match (CRC `0x9138103F`)

| Symbol | Added (depth) | Script |
|---|---|---|
| CustomMatchScreen | - | backdrop (depth 1, char 195) darkened navy |
| CustomMatchInterface | `m_icHeaderPanel` 2, `m_icTeam1Panel` 10, `m_icTeam2Panel` 11, `m_icStartPlate` 16, `m_icInvitePanel` 49, `m_icBenchPanel` 64, `m_icChatPanel` 72, `m_icHeaderText` 80, `m_icMapText` 81 (clones), `m_icTicker` 82 | host = the player with `iidAccount == iidCoordinator` in `CustomMatchManager.Team1/2/0Players`; team size = `EncounterData.nMaxPlayers / nNumTeams`; map = `sName`; panels follow `m_tdTeam1/2`, `m_idInviteDisplay`, `m_hpHoldingPen`, `m_cChat.m_mcClickBlocker` each frame; plate around `m_btStartMatch` (half alpha while disabled), START tinted |
| CustomMatchTeam1Display / Team2Display | `m_icOpen0..4` 15-19, ticker 20 | column background (depth 2) faded; OPEN cards in the rows after the last card of `m_aTeamPlayerDisplays` (step from the cards' `m_mcBackgroundLit`, else 46 px), up to team size (max 5); with no player, from the scroll view's top left [P] |
| AssignedTeamPlayer1Display / 2Display | `m_icCard` 2 (blue / red), `m_icTagHost` 33, `m_icTagReady` 34, `m_icTagAI` 35, ticker 36 | card = `m_mcBackgroundLit` bounds (240 x 33); tag from `m_pdoPlayerData` (IsABot -> AI, coordinator -> HOST, else READY) at `K_TAG_X1` 178 / `K_TAG_X2` 215 from the slot's left; name white |
| UnassignedPlayerDisplay | `m_icCard` 2, ticker 26 | card (320 x 36), name white (host keeps the class's organizer icon) |
| CustomMatchInvitedPlayerDisplay | tags PENDING 5 / JOINED 6 / DECLINED 7, ticker 8 | `m_mcInviteStatus` faded, the tag at its place from `m_ipInvitedPlayerData.InviteStatus` |
| InviteDisplay, HoldingPen | - | unnamed backgrounds (1 + 13; 1 + 2) faded |

### 0x20000082 group screen (CRC `0x6443BBF5`)

PVPGroupComponent (backdrop depth 1 darkened), PVPGroupingInterface (`m_icInvitePanel` 10, `m_icLaunchPlate` 11,
`m_icGroupPanel` 21, `m_icChatPanel` 152, ticker 157; LAUNCH tinted), GroupDisplay / GroupInviteDisplay (backgrounds
1 + 2 / 1 + 6 faded), GroupPlayerDisplay (`m_icCard` 2, `m_icOpen` 5 covering the "..." of an empty slot =
`!UIUtils.IsValidIID(m_data.iidAccount)`, HOST 25 / READY 26 at `K_GTAG_X` 214, ticker 27), GroupInvitedPlayerDisplay
(PENDING / JOINED (accepted + IsInGroup) / LEFT (accepted, not in group) / DECLINED at 5-8, ticker 9).

### 0x20000083 chat (CRC `0xE0901902`)

Chat (`m_icChatPanel` 2 between the click blocker and the log, fitted to `m_mcClickBlocker` + 6 px; blocker alpha 0 —
it still takes clicks), ChatLauncher (`m_icUnread` 2 at the button's top right while `m_btChat.ToggleUnreadChat`,
ticker 3; `m_btChat` tinted accent). Chat is placed by the wrapper, lobby, group, custom match and scorecard, so the
frame follows it everywhere this movie's symbol is used (the champion-select lobby's own widget is `0x20000067`, not
here).

### 0x2000008B contacts (CRC `0x47876CBB`)

ContactsComponent (`m_icPanel` 2 over the union of `m_mcBackgroundTop / m_mcBackground / m_mcBackgroundBottom`, which
are faded every frame — frame 2 removes them and a re-entered frame 1 recreates them; hidden when gone), ContactsPanelHeader
(`m_icTabLine` 27 under the selected visible list button, `m_icOnlineCount` 28 = copy of `m_wtTabTitle` at +150 / +4 px,
text `<sum of ContactsManager.onlineGroups[i].numContacts> ONLINE` in green, shown in the contacts view), ContactDisplay
(`m_icCard` 2 fitted to `m_mcBackground` (368 x 60), which is faded; presence colour from `m_cdData.ePresence`:
Online green, Away light grey, InGame / InLobby / InCustomMatch / InGroup / InQueue / InGroupQueued gold, else grey —
the dot `m_mcPresenceIndicator` gets a solid colour transform, `m_wtPresenceDesc` the text colour; name white;
`m_icInvitePlate` 15 behind `m_btInvite` while visible; back to Legacy calls the class's `UpdateStatusAndPresence()`).

## 3. Uncertainties

- `getInstanceAtDepth` in GFx [P]; the depth of each unnamed Legacy background is from the movie (static).
- Overlapping polygons in one shape (tag border / inside, font joints) rely on GFx's tessellation as the header's
  nested plates did [P].
- The clone `UIWidget_Text`'s size: `setSize(330 / 380, 22)` and the template name are from the game's own text
  widgets; the header strip's position (CustomMatchInterface y 0..28, x 140..890) is estimated from the placements
  (teams' names start at y 31) [P]. `EncounterData.sName` may be a `#id|` string token; it is put alone in its widget
  so the engine's token lookup applies [P].
- OPEN slots without any player in the team use the scroll view's top left; the scroll view's 2.45 placement scale
  is assumed reset by the widget [P].
- Tag x positions (`K_TAG_X1/2`, `K_GTAG_X`) avoid the name boxes and the assign / invite buttons by the placements;
  a very long name may reach the tag [G].
- Per-frame tickers on every card (team, bench, group, contact rows): cheap (bounds + a few properties) but untested
  for frame time with a long friends list.

## 4. Shared changes needed (not made: outside this area)

- `tests/test_ui_build.py` `installed()`: `check("install: manifest movies", set(man["movies"]) == {"0x20000077",
  "0x2000005f"})` fails as soon as any other module exists; it should compare with the layout's DIDs. Its `codes`
  dict is keyed by symbol name only: `ChatLauncher` exists in `0x20000083` and `0x20000067` (and `InlineInviteEditor`
  in `0x20000093` / `0x2000008B`), so key it by (DID, symbol) if both get scripts.
- Done (integrated 2026-10-30, `ui-modern-build.md` 10): `social_art.py` / `social.as` are in `ui/modern/common/` (`import social_art as sa`); scripts are
  keyed by (DID, symbol) in `tests/test_ui_build.py`.
- `docs/CHANGELOG.md` (`fase3-im`), `reverse-engineering.md`, `AI_GUIDE.md` and the catalog: record this area.

## 5. In-game test (tester)

`python ic.py ui build` + `ui apply` (game closed), tick "Modern interface (beta)", then: PLAY > custom match (create,
change map, assign players, add bots by the map, invite a friend by name and from the friends panel, START, Leave);
PLAY > group (invite, leave); open the friends panel (Online / Offline / Ignored, notifications), set status; open the
chat from the button, get a message while it is closed (red badge). Untick: everything Legacy. Send `logs\server.log`,
`logs\unhandled.log`, screenshots of both looks. Revert with `python ic.py ui revert` if anything breaks.
