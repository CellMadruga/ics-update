# The complete Flash UI: classes, C++ <-> Flash entry points, and what the server must feed per screen (static analysis, 2026-10-22)

Input: the JPEXS decompilation of every GFx movie of pack `0xA00000D0` in `C:\Infinite Crisis Server\re-work\ui-as2\`
(one folder per movie, named by its stream offset; the AS2 class library is `c_a00000d0_02189b08`, DID `0x20000025`).
This note **extends and corrects** `client-scripts-and-ui.md` section 2-3 (read that first: pack layout, record format,
the singleton table 2.3 and the movie table 2.4 are not repeated). Network ids come from `protocol-complete.md`,
`protocol-server-to-client.md`, `protocol-client-to-server.md` and `progression-meta.md`. Nothing here was run against
the client. Only ids, class/function names and argument names are quoted; no game texts.

Tags: **[C]** confirmed from the AS2 code, **[P]** probable (name or layout match), **[G]** guess.

Navigation:
0. Short version - 1. Inventory and corrections - 2. The C++ <-> Flash contract - 3. Every class -
4. C++ -> Flash notices (every `RecvNotice_*`) - 5. Flash -> C++ calls (every `SendNotice_*` / `SendQuery_*` and
`Turbine.*`) - 6. Screen by screen - 7. Per-movie appendix - 8. Enums used by the notices - 9. Top gaps and runtime
tests - 10. Method.

---

## 0. Short version

1. **One code library, 992 classes** [C]. All AS2 code lives in `__Packages` of `0x20000025`; the 81 dumped movies
   contain only timeline stops, component parameter blocks (`on(construct)`: inspectable properties and text tokens
   such as `#0300xxxx|`) and empty `DoInitAction` stubs. Movies bind symbols to library classes by their full dotted
   name (504 classes are linked directly by at least one movie; 22 classes are dead code, list in 3.0).
2. **Three channels from C++ into Flash** [C]: (a) `GM_<Sys>.RecvNotice_<Name>(args)` - **315** notices in 36 systems,
   each forwarded to the AS2 listeners registered with `engNoticeSystemImpl.Register(id, instanceKey, obj, fn)`;
   (b) `PropertySystem.OnPropertyAdded/Changed/Removed(iid, propId, ...)` for registered properties;
   (c) query results written into `GM_<Sys>.gameOutputArgs` during a synchronous `SendQuery_*`.
   Plus `engNoticeSystemImpl/PropertySystem.OnEntityDestruction(iid)`, `input.InputSystem.OnSetTextMode/OnClearTextMode`
   and the `UI.ActionEnumEvent` input notice. 271 notices have a Flash listener, **44 are dead** (no listener).
3. **Flash into C++** [C]: `ExternalInterface.call("Turbine.SendNotice", id, args...)` for **276 notices + 144
   queries** (45 of them never called), and **86 other `Turbine.*` natives** (properties, input maps, floaty
   descriptors, CEF browser, Bink movies, 3D viewports, timers). There is no `fscommand` and no `getURL` anywhere.
4. **Notice ids** [C]: 730 ids in 36 `event_gen.*NoticeIDList` classes (the old note's "2200 getters" counted every
   getter of the library). **35 notices are keyed on an entity IID** instead of `"0"`: the client delivers them only for
   that object (mostly the local player `GetThePlayerInstanceID()`, or the agent of a vitals bar), see 2.2.
5. **Network coverage**: 181 of the 315 C++ -> Flash notices now have a known source (network event, network notice,
   layout match, or "local"); 134 have none yet - most of them are client-local (skills, vitals, minimap, options,
   browser), the rest are the gaps in section 9. Only 50 of the 420 Flash -> C++ calls are known to produce a network
   event (44 by dispatcher name, 6 probable); every other `Request*` is answered by the client from what the server sent earlier (2.3).
6. **New feeder identifications** [P, by argument layout]: `0x2060` = `Lobby.UpdateLobbyState` (parallel arrays team,
   index, IID, name, bot, champion, level, ...), `0x209D` = `UI.CharacterAdvancementData` (6 arrays: champion, level,
   XP, next-level XP, last used, last used ranked), `0x203B` = `Contacts.UI_NotifyContactList`, `0x2071` =
   `Grouping.GroupInformation`; tutorial hint notices `0x1000027F` / `0x10000288` / `0x100004A5` -> `UI_ShowTutorialHint`
   / `UI_ShowTutorialHints` / `UI_CloseTutorialHint`.
7. **Screen switching is client-local** [C]: Flash sends `UI.UIStateMachineEvent(Transition*)`; the C++ state
   machine answers with `UI.UIStateMachineEvent(Load*)` and `WrapperMain` swaps the screen (2.5). The server only
   drives it through the events that already raise `UIStateMachineEvent` (`0x2038` match ended, `0x2053`).
8. **The landing screen depends on `UI.ProtectorAdvancementStatus`** [C] (`FirstTimePlayer`=3 / `Trainee`=2 -> trainee
   landing with the on-rails achievements; `Player`=1 -> veteran landing with nav bar). `ScreenSettings` builds the
   layout of every wrapper screen from it.

---

## 1. Inventory and corrections

### 1.1 The dump [C]

| Item | Count | Note |
|---|---|---|
| `.as` files | 56 922 | 992 in `__Packages` (all distinct), 55 930 per-movie (6 442 non-empty, **2 299 distinct by MD5**) |
| movie folders | 81 + library | `02074ae4` (`0x20000004`, images only) has no scripts; **`0x2000008A` (selection panel) is missing** from this dump and from `old_files/tools/gfx` (its classes `gameplay.selectionpanel.*` are in the library) |
| library classes | 992 | 125 `emp_gen` enums/property lists, 38 `event_gen` id lists, 33 GreenSock (`com.greensock`, tweening), 27 CLIK (`gfx.*`), 41 root, the rest `gameplay.*`, `ui_sys`, `utils`, `liquid`, `template`, `input`, `system` |
| per-movie scripts | - | frame `stop()` / label logic, sprite `on(construct)` parameter blocks (button texts as string tokens, tooltip alignment, sound maps), no logic beyond that |

Stream offset (folder name) -> DID: identical byte sizes with the table of `client-scripts-and-ui.md` 2.4 (all 81
matched exactly).

| folder | DID | folder | DID | folder | DID | folder | DID |
|---|---|---|---|---|---|---|---|
| `0206b4f0` | `0x20000000` | `0256ca74` | `0x20000057` | `026baefc` | `0x20000074` | `02930734` | `0x2000009D` |
| `0206e544` | `0x20000001` | `02573470` | `0x20000058` | `026cd8f8` | `0x20000075` | `0293826c` | `0x2000009E` |
| `0206ea30` | `0x20000002` | `025874ac` | `0x20000059` | `026d5430` | `0x20000077` | `029408f8` | `0x2000009F` |
| `02074ae4` | `0x20000004` | `025bc9ec` | `0x2000005A` | `026e4704` | `0x20000078` | `0299eb68` | `0x200000A0` |
| `02075470` | `0x20000006` | `025c3954` | `0x2000005B` | `026edeb8` | `0x2000007C` | `029a63e0` | `0x200000A1` |
| `02088a24` | `0x20000007` | `025cbbc8` | `0x2000005C` | `026f3910` | `0x2000007F` | `029b276c` | `0x200000A2` |
| `02101ce0` | `0x2000000C` | `025d2884` | `0x2000005E` | `026f8554` | `0x20000080` | `029c2308` | `0x200000A3` |
| `021103bc` | `0x2000000D` | `025dbcc0` | `0x2000005F` | `02709080` | `0x20000082` | `029ca950` | `0x200000A4` |
| `0211b06c` | `0x2000000F` | `025fe1e8` | `0x20000062` | `02714fa0` | `0x20000083` | `029eb824` | `0x200000A5` |
| `0212e9f4` | `0x20000010` | `026384b8` | `0x20000063` | `0271b90c` | `0x20000084` | `02a326b0` | `0x200000A7` |
| `021336ac` | `0x20000011` | `0263d62c` | `0x20000064` | `0273052c` | `0x20000086` | `02a49fb4` | `0x200000A8` |
| `0213ed14` | `0x20000013` | `0264adac` | `0x20000065` | `0273ee84` | `0x20000087` | `02a66eb8` | `0x200000A9` |
| `0214b0e4` | `0x20000015` | `0265763c` | `0x20000066` | `02757180` | `0x2000008B` | `02a70580` | `0x200000AA` |
| `0216400c` | `0x20000016` | `0265c5dc` | `0x20000067` | `02767b98` | `0x2000008C` | `02a830f4` | `0x200000AB` |
| `0217aafc` | `0x20000020` | `0266dfa0` | `0x2000006B` | `027a0ea0` | `0x2000008D` | `02a910e0` | `0x200000AD` |
| `0217bafc` | `0x20000022` | `0267f87c` | `0x2000006C` | `027c0d98` | `0x20000090` | `02aa1c48` | `0x200000AE` |
| `c_a00000d0_02189b08` | `0x20000025` (library) | `02682e84` | `0x2000006D` | `027e9120` | `0x20000093` | `02b260a0` | `0x200000B0` |
| `02253790` | `0x2000002B` | `0268b05c` | `0x2000006E` | `02804204` | `0x20000094` | `02b559a0` | `0x200000B1` |
| `025424d8` | `0x20000051` | `026a6944` | `0x2000006F` | `02824308` | `0x20000099` | `02b8b24c` | `0x200000B2` |
| `0254810c` | `0x20000052` | `026adcd8` | `0x20000070` | `0282f8e4` | `0x2000009A` |  |  |
| `0255bfdc` | `0x20000056` | `026b71ac` | `0x20000073` | `02929710` | `0x2000009C` |  |  |

### 1.2 Corrections to `client-scripts-and-ui.md`

| Where | Old | Corrected |
|---|---|---|
| 2.2 | "2200 getters" of notice ids | **730** notice/query ids in 36 lists (31 `GM_*` + 5 `EM_*` systems); 315 Recv + 276 Send + 144 Query functions (5 ids are both sent and received: `UI.UIStateMachineEvent`, `UI.ToggleMainMenu`, `UI.ShowURLDialog`, `UI.SetupSettingsButtons`, `UI.ForceOnSized`) |
| 2.2 | notices are global | 35 notices carry an instance key = an entity IID (2.2 below); a notice sent with the wrong target object never reaches Flash |
| 2.1 / 2.4 | 82 movies parsed | 82 movie records, but both extractions (old `.gfx` set and the JPEXS dump) have only 81: `0x2000008A` is missing |
| 2.4 | `0x20000067` feeders include `0x2060` for amplifier / Stolen Power picks | `0x2060` is the **full lobby state** -> `Lobby.UpdateLobbyState` [P, layout]; `0x2029` the single slot -> `UpdateLobbyStateSingle` |
| 3 (collection row) | "`0x209D` (advancement per champion)" | confirmed by layout: `0x209D` -> `UI.CharacterAdvancementData(characters, levels, currentXP, nextLevelXP, lastUsed, rankedLastUsed)` [P] |
| 3 (friends row) | "`0x203B` list n=0 is probably enough" | `0x203B` -> `Contacts.UI_NotifyContactList` (18 parallel arrays, 2.4 of section 4) [P] |
| 2.3 (singleton table) | listeners per singleton | complete per class in section 3 and per notice in section 4 (several singletons also listen to `UI.ExitingWorld` / `ActionEnumEvent`) |
---

## 2. The C++ <-> Flash contract [C]

### 2.1 Notices

- **Flash -> C++**: `GM_<Sys>.SendNotice_<X>(args)` = `ExternalInterface.call("Turbine.SendNotice", <id>, args...)`.
  `SendQuery_<X>(in..., io_out...)` makes the same call and then reads `GM_<Sys>.gameOutputArgs[0..n]`, which C++
  filled during the call (synchronous; the returned object names the outputs, e.g. `{iRank: ...}`). Every wrapper has a
  `Playback` branch (recording/replay tool), unused in the shipped client.
- **C++ -> Flash**: C++ calls the static `GM_<Sys>.RecvNotice_<X>(args)` directly; it looks up
  `engNoticeSystemImpl.m_Listeners[String(id + instanceKey)]` and calls every registered function with the same
  arguments. `engNoticeSystemImpl.Register(id, key, obj, fn)` calls **`Turbine.RegisterNotice(id, key)`** the first
  time a key is used, so C++ knows who listens (and `Turbine.UnregisterNotice` when the last listener leaves).
  `OnEntityDestruction(iid)` drops every listener keyed on that IID.
- Arrays arrive as AS2 arrays of primitives; almost every notice with lists uses **parallel arrays** (one array per
  field, same index = same row). No listener reads object fields from an array element (checked for all 410
  registrations), so the argument lists in section 4 are the complete data contract.
- Argument names keep the original Hungarian prefixes: `iid` 64-bit instance id, `did` 32-bit data id, `e` enum (section
  8), `n`/`i`/`u`/`ui` integer, `f` float, `b` bool, `si` StringInfo (localized string, arrives as text), `s`/`str`
  plain string, `tt` game time (seconds, `system.GameplaySystem.GetTime` clock), `a` array of (`aiid`, `adid`, `asi`...),
  `h` native handle.

### 2.2 Notices keyed on an entity (35) [C]

The listener registers with an IID instead of `"0"`; the client raises the notice for that object only. Network
notices of this kind must be sent (event `0x2`) **to that object**.

| Key used by the listeners | Notices |
|---|---|
| local player (`system.GameplaySystem.GetThePlayerInstanceID()`, `0x0200000000000001`) | `Character.ShowAnnouncement`, `ClearAnnouncement`, `StopProcessingNewBillboards`, `NotifyPlayerDied`, `AgentControlledByThePlayerChanged`, `ActiveAgentControlledByThePlayerChanged`; `Encounter.NotifyMatchEnded`, `SetMatchTime`, `UI_InitialTeamHealthUpdate`, `UI_UpdateTeamHealth`, `UI_PlayerJoined`, `UI_PlayerLeft`, `UpdateSurrenderData`, `SurrenderVoteConcluded`; `UI.DefeatStatusUpdated`, `DefeatStatusUpdatedForEntity`, `TimerClockSync`; `Skill.UpdateSkillUIOverlay` |
| the entity a floaty / overhead bar is attached to (`m_iidAttachEntity`) | `Vitals.VitalsChanged`, `DOTUpdate`, `VOTUpdate`, `DisplayFloatyStatus`; `Advancement.XPGained`; `Upgrade.DisplayFloatyCurrencyChanged`, `DisplayFloatyCurrencyDenied`; `Character.UpdateRegenValues` |
| the controlled agent or tracked target | `Character.UpdateCharacterPanelInfo` (also `VitalsChanged` for the skill bar's agent) |
| the agent whose status row is shown (`m_iidAgent`) | `StatusIcon.AddStatusIcon`, `BatchAddStatusIcon`, `RemoveStatusIcon`, `UpdateStatusIcon`, `UpdateStatusIconTooltip` |
| declared with an IID, no listener | `SelectionSystem.UsableTargetInRange` / `OutOfRange`, `UI.PauseDefeatStatusTimerForEntity` |

### 2.3 What the server can and cannot reach

- A Flash `Request*` notice with no network event in section 5 is **answered by the client from its own cache** of
  the last network event (or from DB records). The server's job is to have sent that event before the screen opens.
  Examples [P]: `GM_Character.RequestAccountCurrencyBalance` -> last `0x2081`; `GM_UI.RequestHeaderUIData` -> last
  `0x2190`/`0x2154`; `GM_UI.RequestCharacterAdvancementData` -> last `0x209D`; `GM_UI.RequestItemStatuses` -> last
  `0x20B8`; `GM_Amplifier.UI_RequestAllAmplifierSets` -> last `0x2090`; `GM_UI.RequestProtectorAdvancementStatus` ->
  last status event. The only cache refill known to go back to the server is `0x21A5` (champion list empty).
- **Queries** (`SendQuery_*`, 144) are always local and synchronous; data the client cannot have (e.g. ranked
  standings) arrives as notices instead.
- Properties feed the HUD without notices (2.4).

### 2.4 Properties read by Flash [C]

`PropertySystem.Register(propId, iid, obj)` -> `Turbine.RegisterProperty(propId, iid)`; C++ then calls
`PropertySystem.OnPropertyAdded(iid, id, value)` / `OnPropertyChanged(iid, id, old, new)` / `OnPropertyRemoved`.
`InqProperty(iid, id)` reads an entity once, `InqPropertyDID(did, id)` reads a **DB record** (no server involved);
`SetProperty` exists but no class calls it. Entity properties the server must set: `XP`, `Level`, `SkillPoints`,
`Upgrade_Currency`, `PVP_Team` on the controlled agent (`ControlledAgentDispatcher`, listened); `PVP_Team`, `Level`,
`Name`, `Character_ControllableAgentToPlayer_InstanceID` on every entity with an overhead bar (team colour, level,
owner); `Name`, `Level`, `PerceivedType`, `Upgrade_Facade` on the selected target; `Name` of the killer (kill card).
The `Character_*` ids read with `InqPropertyDID` come from the champion's light / heavy / power-set records.

| property | id | list | used by (Register / InqProperty / SetProperty) |
|---|---|---|---|
| Name | `0x000003CE` | EngineStringInfoPropertyList | CharacterPanel, KillCard, OverheadVitalsDeluxe |
| Character_ControllableAgentToPlayer_InstanceID | `0x10000064` | gmCharacterPropertyList | OverheadVitalsDeluxe |
| PVP_Team | `0x1000009C` | gmPVPPropertyList | BillboardManager, ControlledAgentDispatcher, MainHUD, MatchManager, OverheadVitalsBase |
| Character_PlayerToControllableAgent_InstanceID | `0x100000CF` | gmCharacterPropertyList | - (declared only) |
| XP | `0x10000142` | gmAdvancementPropertyList | ControlledAgentDispatcher, ExperienceAward, TestButtonsExperience |
| Level | `0x10000167` | gmAdvancementPropertyList | AnnouncementsManager, ControlledAgentDispatcher, OverheadVitalsDeluxe, SelectionPanel, TestButtonsExperience |
| PerceivedType | `0x1000019D` | gmPerceptionPropertyList | SelectionPanel |
| SkillPoints | `0x100001AF` | gmAdvancementPropertyList | AnnouncementsManager, ControlledAgentDispatcher |
| Character_Billboard_Icon | `0x100001FC` | gmCharacterPropertyList | - (declared only) |
| Character_LargeIcon | `0x10000337` | gmCharacterPropertyList | - (declared only) |
| Character_ConsoleVitals_Portrait | `0x10000338` | gmCharacterPropertyList | CharacterPanel |
| Upgrade_Currency | `0x1000035E` | gmUpgradePropertyList | ControlledAgentDispatcher |
| Character_SmallIcon | `0x10000384` | gmCharacterPropertyList | ChampionDetailPanel, CharacterBrowserButton, CharacterButton, CharacterSkinButton, SkinButton, VeteranChampion |
| Character_Name | `0x10000433` | gmCharacterPropertyList | ChampionDetailPanel, CharacterBrowserButton, CharacterPreview, CurtainPlayerDisplay, SkinButton, SuperRewardRibbon, VeteranChampion |
| Character_Description | `0x10000434` | gmCharacterPropertyList | - (declared only) |
| Character_CharSelectVO | `0x10000575` | gmCharacterPropertyList | - (declared only) |
| Character_WallpaperImage | `0x100005B0` | gmCharacterPropertyList | AnimatedRankedDisplay, ChampionDetailPanel, CharacterPreview, Ranked, Scorecard, SuperRewardRibbon, VeteranLanding |
| Character_ActiveAgent_InstanceID | `0x100005E8` | gmCharacterPropertyList | - (declared only) |
| Character_Role_Description | `0x100005EE` | gmCharacterPropertyList | - (declared only) |
| Character_Role_Name | `0x100005F2` | gmCharacterPropertyList | - (declared only) |
| Character_About | `0x10000778` | gmCharacterPropertyList | ChampionDetailPanel |
| Character_Powerset_PlayStyle | `0x10000779` | gmCharacterPropertyList | - (declared only) |
| Character_Alignment | `0x1000077A` | gmCharacterPropertyList | - (declared only) |
| Character_Multiverse | `0x1000077B` | gmCharacterPropertyList | - (declared only) |
| Character_Powerset_PowerBar | `0x1000077C` | gmCharacterPropertyList | - (declared only) |
| Character_Powerset_HealthBar | `0x1000077D` | gmCharacterPropertyList | - (declared only) |
| Character_Powerset_DifficultyBar | `0x1000077E` | gmCharacterPropertyList | - (declared only) |
| Character_Skin_Name | `0x1000077F` | gmCharacterPropertyList | ChampionDetailPanel, CharacterPreview, CurtainPlayerDisplay, SuperRewardRibbon, VeteranChampion |
| Character_Powerset_AttackBar | `0x10000780` | gmCharacterPropertyList | - (declared only) |
| Character_MiniWallpaperImage | `0x10000799` | gmCharacterPropertyList | VeteranChampion |
| Character_Turntable_Movie | `0x10000C58` | gmCharacterPropertyList | - (declared only) |
| Character_Portrait_Audio_Stop | `0x10000C87` | gmCharacterPropertyList | ChampionDetailPanel, Ranked, VeteranLanding |
| Character_Portrait_Audio | `0x10000C88` | gmCharacterPropertyList | ChampionDetailPanel, Ranked, VeteranLanding |
| Character_Superbanner_Audio | `0x10000CA2` | gmCharacterPropertyList | SuperRewardRibbon |
| Upgrade_CurrentItemCount | `0x10000CD6` | gmUpgradePropertyList | - (declared only) |
| Upgrade_Facade | `0x10000D40` | gmUpgradePropertyList | SelectionPanel |

### 2.5 UI state machine [C]

Flash sends `GM_UI.SendNotice_UIStateMachineEvent(e)` (id `0x10000020`) with `Transition*` values (usually through
`gameplay.state.StateMachineHelpers`); the C++ state machine (`old_files/tools/ui_sm.hkx`) answers with
`GM_UI.RecvNotice_UIStateMachineEvent(e)` carrying `Load*` / `SetWrapperCookieMode*` / `MatchEnded`, which
`WrapperMain` turns into a screen (`ScreenSettings.GetScreenSettings(name, protectorStatus)`). Values without a Flash
sender or handler are raised and consumed inside C++ (logos, connection, HUD load). Network events known to raise it:
`0x2038` (match ended) and `0x2053`.

| id | event | sent by Flash (classes) | handled in Flash (classes) |
|---|---|---|---|
| 1 | TransitionToEncounterSelectScreen | EncMapSelectionScreen, EncSoloGroupScreen, EncTutorialSelectionScreen, PVPLauncher | - |
| 2 | TransitionToMapSelectionScreenBlind | - | - |
| 3 | TransitionToMapSelectionScreenAI | - | - |
| 4 | TransitionToMapSelectionScreenDraft | - | - |
| 5 | TransitionToMapSelectionScreenRanked | - | - |
| 6 | TransitionToMapSelectionScreenTutorials | - | - |
| 7 | LoadEncounterSelectScreen | - | WrapperMain |
| 8 | TransitionToPVPGroupingScreen | PVPLauncher, Scorecard, StateMachineHelpers, WrapperMain | - |
| 9 | Transition | StateMachineHelpers | - |
| 10 | UnloadHUD | - | - |
| 12 | TransitionToScorecard_Stats | Scorecard | - |
| 13 | TransitionToTutorialDetails | - | - |
| 15 | TitleLoopComplete | - | - |
| 16 | DCLogoComplete | - | - |
| 18 | MatchEnded | - | WrapperMain |
| 19 | TransitionToLogin | - | - |
| 20 | TransitionToLobby | StateMachineHelpers | WrapperMain |
| 21 | LoadTestHarness | - | - |
| 23 | LoadEncounterDetails | - | WrapperMain |
| 24 | LoadCharactersScreen | - | LandingNav, WrapperMain |
| 25 | TurbineLogoComplete | - | - |
| 26 | TransitionToCustomMatch | PVPLauncher, Scorecard | - |
| 27 | TransitionToCharacters | LandingNav, VeteranLanding | LandingNav |
| 28 | TransitionExitScorecard | StateMachineHelpers | - |
| 29 | WBLogoComplete | - | - |
| 30 | LoadHUDPVE | - | - |
| 31 | UnloadLoadingScreen | - | - |
| 32 | TransitionToWorldLoadPVE | - | - |
| 33 | TransitionToScorecard | StateMachineHelpers | - |
| 34 | Connection_Connected | - | - |
| 35 | TransitionToWorldLoad | - | - |
| 37 | ScorecardLoadComplete | Scorecard | - |
| 38 | LoadHUDPVP | - | - |
| 39 | RequestScreenName | WrapperMain | - |
| 40 | DereferenceDIDs | - | LobbyWrapper |
| 41 | Connection_ExitToMainMenu | - | - |
| 42 | Connection_Disconnected_Involuntary | - | - |
| 43 | SetWrapperCookieModeTutorials | - | WrapperMain |
| 44 | LoadStatsScreen | - | LandingNav, WrapperMain |
| 45 | TransitionToAmplifiers | LandingNav | LandingNav |
| 46 | Connection_ExitToMainMenu_DEMO | - | - |
| 47 | HUDCurtainTransitionDownComplete | MainHUD, PvPLobby | - |
| 48 | StartHUDCurtainTransitionDown | PvPLobby | LobbyHeaderRight, MainHUD, PvPLobby |
| 49 | TransitionToSoloGroupScreen | MapBigButton | - |
| 50 | LegalComplete | - | - |
| 51 | ServerLoadComplete | - | - |
| 52 | HideHUD | - | - |
| 53 | SetWrapperCookieModeBlind | - | WrapperMain |
| 54 | LoadCustomMatchScreen | - | WrapperMain |
| 55 | LoadAmplifiersScreen | - | LandingNav, WrapperMain |
| 56 | TransitionOutComplete | StateMachineHelpers | - |
| 57 | ShowHUD | - | - |
| 58 | LoadTutorialDetailsScreen | - | WrapperMain |
| 59 | LoadTutorialSelectionScreen | - | WrapperMain |
| 61 | TransitionToStats | LandingNav | LandingNav |
| 63 | HUDCurtainTransitionUpComplete | LobbyWrapper, MainHUD | - |
| 64 | LoadLoginScreen | - | WrapperMain |
| 65 | LoadLandingScreen | LandingSwitcher, NewPlayerScreen, TraineeAchievements | LandingNav, WrapperMain |
| 66 | TransitionToAchievements | LandingNav, VeteranLanding | LandingNav |
| 67 | Connection_Connecting | - | - |
| 68 | LoadStoreScreen | - | WrapperMain |
| 69 | TransitionLoadGFXComplete | WrapperMain | - |
| 71 | Login_Success | WrapperMain | WrapperMain |
| 72 | LoadScorecard_Summary | - | Scorecard |
| 73 | TransitionToMapSelectionScreen | EncFeaturedMapScreen, EncSoloGroupScreen, GameModeBigButton | - |
| 74 | ScreenNameAccepted | - | - |
| 75 | SetWrapperCookieModeDraft | - | WrapperMain |
| 76 | LoadBlankScreen | - | WrapperMain |
| 77 | TransitionBack | StateMachineHelpers | - |
| 78 | StartHUDCurtainTransitionUp | - | LobbyHeaderCenter, LobbyWrapper, MainHUD |
| 79 | LoadMapSelectionScreen | - | WrapperMain |
| 80 | TransitionToTutorialSelection | EncounterDetails, GameModeBigButton | - |
| 81 | ReadyForHud | - | - |
| 82 | LoadSoloGroupScreen | - | WrapperMain |
| 83 | TransitionToIntroMovie | LoginScreen | - |
| 84 | TransitionToLandingScreen | CustomMatchInterface, EncFeaturedMapScreen, EncGameModeScreen, EncounterDetails, HeaderCenter, LandingNav, LoginRewards, MatchmakingIndicator, NavButtons, NextChallenge, PVPGroupManager, Scorecard, Store, WrapperMain | LandingNav |
| 85 | TitleComplete | - | - |
| 86 | Connection_Disconnected_Voluntary | - | - |
| 87 | SetWrapperCookieModeAI | - | WrapperMain |
| 89 | EnterWorldWithoutCinematicIntro | - | - |
| 90 | WrapperCookieSetComplete | WrapperMain | - |
| 91 | LoadScorecard_Stats | - | Scorecard |
| 93 | TransitionToStore | NavButtons | - |
| 94 | TransitionToEncounterDetails | TraineeAchievements, TutorialBigButton | - |
| 95 | TransitionLobbyAbandoned | StateMachineHelpers | WrapperMain |
| 96 | LoadNewPlayerScreen | - | - |
| 97 | SetWrapperCookieModeRanked | - | WrapperMain |
| 98 | LoadPVPGroupingScreen | - | WrapperMain |
| 100 | LoadScorecardScreen | - | WrapperMain |
| 101 | LoadLandingDemoScreen | - | WrapperMain |
| 102 | LoadAchievementsScreen | - | LandingNav, WrapperMain |
| 103 | TransitionToScorecard_Summary | Scorecard | - |
| 104 | TransitionToHQMenu | - | - |
| 105 | WrapperOnlyResourcesLoaded | - | - |
| 106 | LoadScorecard_Accolades | - | Scorecard |
| 107 | TransitionToScorecard_Accolades | Scorecard | - |
| 108 | LoadLoginRewardsScreen | - | WrapperMain |
| 109 | TransitionToLoginRewards | StartMenuDialog | - |
| 111 | DeliveredProtectorAdvancementStatus | - | - |
| 112 | LoadRankedScreen | - | LandingNav, WrapperMain |
| 113 | TransitionToRanked | HeaderProfile, LandingNav | LandingNav |

### 2.6 Other `Turbine.*` natives (86) [C]

Called by the toolkit classes; none of them reaches the network directly (the browser ones drive the embedded CEF:
store, news, social media).

| call | arguments (as passed) | wrapper class |
|---|---|---|
| `Agent.GetControllingPlayerIID` | i_iidAgent | gmGameplaySystem |
| `Browser.CanGoBack` | m_hBrowserDesc | UIWidget_Browser |
| `Browser.CanGoForward` | m_hBrowserDesc | UIWidget_Browser |
| `Browser.CreateDesc` | _loc2_.x, _loc2_.y, _loc2_.w, _loc2_.h | UIWidget_Browser |
| `Browser.DestroyDesc` | m_hBrowserDesc | UIWidget_Browser |
| `Browser.ExecuteJavaScript` | m_hBrowserDesc, i_strJS, i_strFrameName, i_strSource, i_nLine | UIWidget_Browser |
| `Browser.GetZoomLevel` | m_hBrowserDesc | UIWidget_Browser |
| `Browser.GoBack` | m_hBrowserDesc | UIWidget_Browser |
| `Browser.GoForward` | m_hBrowserDesc | UIWidget_Browser |
| `Browser.LoadHTML` | m_hBrowserDesc, i_strHTML | UIWidget_Browser |
| `Browser.NavigateByInfo` | m_hBrowserDesc, i_cNav.hDesc | UIWidget_Browser |
| `Browser.NavigateInfo_AddHeader` | m_hDesc, i_strHeaderName, i_strHeaderValue | NavigateInfo |
| `Browser.NavigateInfo_CreateDesc` | i_strURL | NavigateInfo |
| `Browser.NavigateInfo_DestroyDesc` | m_hDesc | NavigateInfo |
| `Browser.NavigateInfo_SetPostData` | m_hDesc, i_strPOSTData | NavigateInfo |
| `Browser.NavigateToURL` | m_hBrowserDesc, i_strURL | UIWidget_Browser |
| `Browser.OnBrowserFocus` | m_hBrowserDesc, false / m_hBrowserDesc, true | UIWidget_Browser |
| `Browser.OnMouseMove` | m_hBrowserDesc, _loc3_.x, _loc3_.y | UIWidget_Browser |
| `Browser.OnMousePress` | m_hBrowserDesc, _loc2_.x, _loc2_.y, MBT_LEFT, false / m_hBrowserDesc, _loc2_.x, _loc2_.y, MBT_LEFT, true / m_hBrowserDesc, _loc2_.x, _loc2_.y, MBT_RIGHT, false / m_hBrowserDesc, _loc2_.x, _loc2_.y, MBT_RIGHT, true | UIWidget_Browser |
| `Browser.OnMouseWheelEvent` | m_hBrowserDesc, _loc4_.x, _loc4_.y, 0, i_nDeltaY * SCROLL_WHEEL_DELTA_MOD | UIWidget_Browser |
| `Browser.PurgeHistory` | m_hBrowserDesc | UIWidget_Browser |
| `Browser.Refresh` | m_hBrowserDesc, _loc3_ | UIWidget_Browser |
| `Browser.RegisterJSCallback` | m_hBrowserDesc, i_strCallbackName, i_strFrameName | UIWidget_Browser |
| `Browser.SetAccessToken` | m_hBrowserDesc, i_nSocialNetworkType, i_sAccessToken, i_sAccessTokenSecret | UIWidget_Browser |
| `Browser.SetDescPos` | m_hBrowserDesc, _loc2_.x, _loc2_.y, _loc2_.w, _loc2_.h | UIWidget_Browser |
| `Browser.SetZoomLevel` | m_hBrowserDesc, i_nZoomLevel | UIWidget_Browser |
| `Browser.StopNavigation` | m_hBrowserDesc | UIWidget_Browser |
| `Debug.Assert` | i_bCondition | Debug |
| `Floaty.CreateFloatyDesc` | m_iidAttachEntity | FloatyBase, FloatyVerb, OverheadVitalsBase |
| `Floaty.DestroyFloatyDesc` | m_hFloatyDesc | FloatyBase, FloatyVerb, OverheadVitalsBase |
| `Floaty.SetDescAttachType` | m_hFloatyDesc, emp_gen.FloatyAttachTypeList.PhysicsBottom_FloatyAttachType / m_hFloatyDesc, emp_gen.FloatyAttachTypeList.PhysicsCenter_FloatyAttachType / m_hFloatyDesc, emp_gen.FloatyAttachTypeList.PhysicsTop_FloatyAttachType / m_hFloatyDesc, emp_gen.FloatyAttachTypeList.SmoothSkinnedTop_FloatyAttachType, i_fDampen,  | FloatyBase |
| `Floaty.SetDescDistanceScale` | m_hFloatyDesc, i_fMinScaleDistance, i_fMaxScaleDistance, i_fNearScale, i_fFarScale | FloatyBase |
| `Floaty.SetDescEdgeClamp` | m_hFloatyDesc, i_bEdgeClamp, i_fEdgeClipBias | FloatyBase |
| `Floaty.SetDescHasDepth` | m_hFloatyDesc, i_bHasDepth | FloatyBase |
| `Floaty.SetDescScreenOffset` | m_hFloatyDesc, i_fOffsetX, i_fOffsetY | FloatyBase |
| `Floaty.SetDescSize` | m_hFloatyDesc, m_cPos.w, m_cPos.h | FloatyBase |
| `Floaty.SetDescWorldOffset` | m_hFloatyDesc, i_fVerticalOffsetFromTarget | FloatyBase |
| `Input.AllocateInputMapHandle` | i_eInputMap, i_nPriority | InputMap |
| `Input.RegisterInputMap` | _loc5_, true | InputMap |
| `Input.UnregisterInputMap` | m_nHandles[i_nMapIndex], true | InputMap |
| `InqProperty` | i_iid, i_nPropID | PropertySystem |
| `InqPropertyDID` | i_did, i_nPropID | PropertySystem |
| `MovieTheatre.AudioOn` | m_hMovieTheatreDesc, i_enable | UIWidget_MovieTheatre |
| `MovieTheatre.CreateDesc` | - | UIWidget_MovieTheatre |
| `MovieTheatre.DestroyDesc` | m_hMovieTheatreDesc | UIWidget_MovieTheatre |
| `MovieTheatre.Loop` | m_hMovieTheatreDesc, i_enable | UIWidget_MovieTheatre |
| `MovieTheatre.Pause` | m_hMovieTheatreDesc, i_enable | UIWidget_MovieTheatre |
| `MovieTheatre.VideoOn` | m_hMovieTheatreDesc, i_enable | UIWidget_MovieTheatre |
| `Player.GetControlledAgentIID` | - | gmGameplaySystem |
| `Player.GetIID` | - | GameplaySystem |
| `RegisterNotice` | i_NoticeID, i_InstanceID | engNoticeSystemImpl |
| `RegisterProperty` | i_PropertyID, i_InstanceID | PropertySystem |
| `SetProperty` | i_iid, i_nPropID, i_Value | PropertySystem |
| `Timer.GetTime` | - | GameplaySystem |
| `UIElement.KillFocus` | - | InputSystem |
| `UIElement.SetFocus` | - | InputSystem |
| `UIElement.SetTextMode` | false / true | InputSystem |
| `UIL.CreateDesc` | _loc2_.x, _loc2_.y, _loc2_.w, _loc2_.h, m_sUIL | UIWidget_Chat |
| `UIL.DestroyDesc` | m_hChatDesc | UIWidget_Chat |
| `UIL.SetDescPos` | m_hChatDesc, _loc2_.x, _loc2_.y, _loc2_.w, _loc2_.h | UIWidget_Chat |
| `UnregisterNotice` | _loc3_, i_iid / i_NoticeID, i_InstanceID | engNoticeSystemImpl |
| `UnregisterProperty` | _loc3_, i_iid / i_PropertyID, i_InstanceID | PropertySystem |
| `Viewport.CreateDesc` | - | UIWidget_Viewport |
| `Viewport.DestroyDesc` | m_hViewportDesc | UIWidget_Viewport |
| `Viewport.SetDescAllowVideoPost` | m_hViewportDesc, i_bAllowVideoPost | UIWidget_Viewport |
| `Viewport.SetDescAmbientLight` | m_hViewportDesc, Number(i_cAmbientLight | UIWidget_Viewport |
| `Viewport.SetDescBackgroundMaterialDataID` | m_hViewportDesc, i_didBackgroundMaterial | UIWidget_Viewport |
| `Viewport.SetDescBloomCompensationAmount` | m_hViewportDesc, i_fBloomCompensationAmount | UIWidget_Viewport |
| `Viewport.SetDescBloomIntensity` | m_hViewportDesc, i_fBloomIntensity | UIWidget_Viewport |
| `Viewport.SetDescCameraID` | m_hViewportDesc, i_CameraID | UIWidget_Viewport |
| `Viewport.SetDescDeshadeStrength` | m_hViewportDesc, i_fDeshadeStrength | UIWidget_Viewport |
| `Viewport.SetDescFakeShadowColor` | m_hViewportDesc, Number(i_cFakeShadowColor | UIWidget_Viewport |
| `Viewport.SetDescFogColor` | m_hViewportDesc, Number(i_cFogColor | UIWidget_Viewport |
| `Viewport.SetDescFogFarDistance` | m_hViewportDesc, i_fFogFarDistance | UIWidget_Viewport |
| `Viewport.SetDescFogNearDistance` | m_hViewportDesc, i_fFogNearDistance | UIWidget_Viewport |
| `Viewport.SetDescPos` | m_hViewportDesc, _loc3_.xMin, _loc3_.yMin, _loc3_.xMax - _loc3_.xMin, _loc3_.yMax - _loc3_ / m_hViewportDesc, _loc5_.xMin, _loc5_.yMin, _loc5_.xMax - _loc5_.xMin, _loc5_.yMax - _loc5_ | UIWidget_Viewport |
| `Viewport.SetDescRenderTextureBackgroundColor` | m_hViewportDesc, Number(i_cRenderTextureBackgroundColor | UIWidget_Viewport |
| `Viewport.SetDescRenderTextureHeight` | m_hViewportDesc, Number(i_nRenderTextureHeight | UIWidget_Viewport |
| `Viewport.SetDescRenderTextureIndex` | m_hViewportDesc, Number(i_nRenderTextureIndex | UIWidget_Viewport |
| `Viewport.SetDescRenderTextureWidth` | m_hViewportDesc, Number(i_nRenderTextureWidth | UIWidget_Viewport |
| `Viewport.SetDescRimLightingIntensity` | m_hViewportDesc, i_fRimLightingIntensity | UIWidget_Viewport |
| `Viewport.SetDescSceneID` | m_hViewportDesc, i_didSceneID | UIWidget_Viewport |
| `Viewport.SetDescSkyGlowAmount` | m_hViewportDesc, i_fSkyGlowAmount | UIWidget_Viewport |
| `Viewport.SetDescUseFog` | m_hViewportDesc, i_bUseFog | UIWidget_Viewport |
| `Viewport.SetDescUseShadows` | m_hViewportDesc, i_bUseShadows | UIWidget_Viewport |
| `__handleEvent` | _name, event | UIComponent |
---

## 3. Every class of the library (992)

### 3.0 How to read the tables

- One table per package. Columns: class name, base class (`gameplay.` dropped), role (hand-written for the key
  classes and every package, plus what the code links to: **listens** = notices it registers, **sends** = its
  `GM_*` calls, `?` = query, **props** = properties it reads, **native** = other `Turbine.*` calls), and the movies that
  use it (low byte of the DID `0x200000xx`; "N movies" when more than 8; "not linked; used by ..." when no movie names
  it and it is only reached through other classes).
- Movie attribution = the classes a movie names (504) plus what they reference, up to 4 levels, without walking
  through hubs (singletons, tooltips, dialogs, classes with 15+ references) [C for the direct links, P for the rest].
- **Dead code** (no movie and no live class reaches it): `gameplay.announcements.*` (level / skill-point
  announcements), `gameplay.combometer.*`, `gameplay.titleMenu.*`, `gameplay.state.DynamicLoadingScreen`,
  `BootupInputHandlerWorld`, `gameplay.skills2.RecallButton`, `gameplay.menus.HudMenuFullControl`,
  `gameplay.timers.TimerTextComposite`, `gameplay.wrapper.characters.CharactersComponent`,
  `gameplay.wrapper.landing.VeteranMainScreenComponent`, `gameplay.wrapper.missionSelect.LevelImageDialog`,
  `gameplay.dialogs.GroupInviteDialogData`, `gameplay.ribbons.data.PurchaseSuccessfulRibbonData`, several
  `TestButtons*`. `gameplay.selectionpanel.SelectionPanel` is live but its movie (`0x2000008A`) is missing.

### 3.1 Generated packages (summarised)

| package | classes | content |
|---|---|---|
| `event_gen` | 38 | `NoticeID` base, `EngineLanguageType`, and one `<Sys>NoticeIDList` per system: static getters `Notice_<Sys>__<Name>_ID` / `Query_<Sys>__<Name>_ID` returning the 730 ids used in sections 4-5 |
| `emp_gen` | 125 | enums (`<Name>Type` = invalid value, `<Name>List` = values; section 8), property-id lists (`gm*PropertyList`, 2.4), input actions / maps, Wwise event ids (273), dialog element keys (87), HUD element / highlight ids, UI state-machine events |
| `com.greensock` | 33 | TweenLite / TweenMax / TimelineLite and plugins (animation only) |

### 3.2 Hand-written and engine packages


#### `(root)` - the C++ bridge: GM_*/EM_* notice systems, the notice and property registries, image/viewport loaders

| class | extends | role / C++ link | movies (DID low byte) |
|---|---|---|---|
| ArrayParam |  | wrapper for array arguments from C++ | unused (nothing references it) |
| DataCache |  | builds img:// style URLs for DIDs, dynamic textures, browser / chat / bink / viewport descriptors | not linked; used by ui_sys.UIWidget_Base, ui_sys.UIWidget_Browser, ui_sys.UIWidget_Chat +2 |
| EM_SocialMedia | engNoticeSystemImpl | notice system: 1 RecvNotice, 1 SendNotice, 0 SendQuery (sections 4-5) | not linked; used by test.BrowserSocialMedia, test.BrowserTest |
| EM_Sound | engNoticeSystemImpl | notice system: 1 RecvNotice, 2 SendNotice, 0 SendQuery (sections 4-5) | not linked; used by accolades.AccoladeButton, amplifiers.Assembler, artifacts.display.ArtifactsCollectionActionButtons +87 |
| EM_UI | engNoticeSystemImpl | notice system: 4 RecvNotice, 2 SendNotice, 1 SendQuery (sections 4-5) | not linked; used by resolution.ResolutionSizer, settings.GraphicsPaneContents, ui_sys.UIWidgetManager |
| EM_WebBrowser | engNoticeSystemImpl | notice system: 14 RecvNotice, 0 SendNotice, 1 SendQuery (sections 4-5) | not linked; used by wrapper.WrapperMain |
| EM_WebTicket | engNoticeSystemImpl | notice system: 2 RecvNotice, 1 SendNotice, 0 SendQuery (sections 4-5) | not linked; used by amplifiers.Assembler, wrapper.store.Store |
| GM_Achievement | engNoticeSystemImpl | notice system: 6 RecvNotice, 5 SendNotice, 1 SendQuery (sections 4-5) | not linked; used by newplayer.NewPlayerScreen, ribbons.RewardRibbon, ribbons.SuperRewardRibbon +7 |
| GM_AdminAlert | engNoticeSystemImpl | notice system: 1 RecvNotice, 1 SendNotice, 0 SendQuery (sections 4-5) | not linked; used by wrapper.header.HeaderCenter |
| GM_Advancement | engNoticeSystemImpl | notice system: 2 RecvNotice, 2 SendNotice, 6 SendQuery (sections 4-5) | not linked; used by defeat.DefeatRecommendationsPanel, experience.ExperienceBar, experience.ExperienceConsole +1 |
| GM_Amplifier | engNoticeSystemImpl | notice system: 4 RecvNotice, 3 SendNotice, 8 SendQuery (sections 4-5) | not linked; used by amplifiers.Assembler, lobby.amplifierSetPicker.AmplifierSetPicker, singleton.AmplifierSetManager +1 |
| GM_Artifact | engNoticeSystemImpl | notice system: 0 RecvNotice, 1 SendNotice, 6 SendQuery (sections 4-5) | not linked; used by artifacts.data.ArtifactDataManager, artifactsFoundry.AdvancedPanel, defeat.killcard.ContributorRow +1 |
| GM_Camera | engNoticeSystemImpl | notice system: 2 RecvNotice, 1 SendNotice, 0 SendQuery (sections 4-5) | not linked; used by singleton.HudModeManager |
| GM_Character | engNoticeSystemImpl | notice system: 26 RecvNotice, 17 SendNotice, 8 SendQuery (sections 4-5) | not linked; used by charPicker.CharacterPreview, dialogs.CallingCardDialog, lobby.PlayerDisplay +17 |
| GM_Chat | engNoticeSystemImpl | notice system: 3 RecvNotice, 10 SendNotice, 0 SendQuery (sections 4-5) | not linked; used by contacts.ContactDisplay, contacts.ContactSubmenu, contacts.notifications.GroupInviteNotification +8 |
| GM_ConnectionManager | engNoticeSystemImpl | notice system: 2 RecvNotice, 2 SendNotice, 2 SendQuery (sections 4-5) | not linked; used by login.LoginScreen, wrapper.WrapperMain |
| GM_Contacts | engNoticeSystemImpl | notice system: 19 RecvNotice, 12 SendNotice, 1 SendQuery (sections 4-5) | not linked; used by contacts.ContactDisplay, contacts.ContactSubmenu, contacts.ContactsComponent +12 |
| GM_Contextual | engNoticeSystemImpl | notice system: 3 RecvNotice, 3 SendNotice, 0 SendQuery (sections 4-5) | not linked; used by dialogs.AmplifierPurchaseDialog, dialogs.DualCurrencyPurchaseDialog |
| GM_CustomMatch | engNoticeSystemImpl | notice system: 19 RecvNotice, 17 SendNotice, 1 SendQuery (sections 4-5) | not linked; used by contacts.ContactDisplay, contacts.notifications.CustomMatchInviteNotification, contacts.notifications.CustomMatchInvitePreview +18 |
| GM_Dialog | engNoticeSystemImpl | notice system: 4 RecvNotice, 6 SendNotice, 0 SendQuery (sections 4-5) | not linked; used by charPicker.CharacterPicker, conversation.Speaker, lobby.LaunchWarning +5 |
| GM_Encounter | engNoticeSystemImpl | notice system: 45 RecvNotice, 15 SendNotice, 13 SendQuery (sections 4-5) | not linked; used by artifactsFoundry.FoundryManager, charPicker.CharacterPicker, defeat.DefeatManager +30 |
| GM_Grouping | engNoticeSystemImpl | notice system: 5 RecvNotice, 6 SendNotice, 1 SendQuery (sections 4-5) | not linked; used by dialogs.GroupInviteDialog, singleton.PVPGroupManager, wrapper.encounters.EncSoloGroupScreen +7 |
| GM_KeyBinding | engNoticeSystemImpl | notice system: 2 RecvNotice, 5 SendNotice, 0 SendQuery (sections 4-5) | not linked; used by settings.KeybindingPane, singleton.SettingsManager |
| GM_Lobby | engNoticeSystemImpl | notice system: 25 RecvNotice, 17 SendNotice, 2 SendQuery (sections 4-5) | not linked; used by charPicker.CharacterPicker, charPicker.skinPicker.SkinPicker, lobby.LobbyHeaderRight +13 |
| GM_LoginReward | engNoticeSystemImpl | notice system: 2 RecvNotice, 2 SendNotice, 0 SendQuery (sections 4-5) | not linked; used by wrapper.loginReward.RewardTimeline |
| GM_MapManager | engNoticeSystemImpl | notice system: 13 RecvNotice, 7 SendNotice, 1 SendQuery (sections 4-5) | not linked; used by artifacts.display.ArtifactsCollectionRollover, herograph.HeroGraph2Display, minimap.MinimapMouseTarget +3 |
| GM_Options | engNoticeSystemImpl | notice system: 2 RecvNotice, 53 SendNotice, 49 SendQuery (sections 4-5) | not linked; used by defeat.DefeatManager, dialogs.SettingsPanelDialog, dialogs.StartMenuDialog +11 |
| GM_PlayerReport | engNoticeSystemImpl | notice system: 0 RecvNotice, 1 SendNotice, 1 SendQuery (sections 4-5) | not linked; used by dialogs.ReportAPlayerDialog, dialogs.ReportAPlayerDialogData |
| GM_ProfileUI | engNoticeSystemImpl | notice system: 4 RecvNotice, 1 SendNotice, 0 SendQuery (sections 4-5) | not linked; used by wrapper.characters.ChampionDetailPanel, wrapper.landing.VeteranLanding |
| GM_SelectionSystem | engNoticeSystemImpl | notice system: 8 RecvNotice, 0 SendNotice, 1 SendQuery (sections 4-5) | unused (nothing references it) |
| GM_Skill | engNoticeSystemImpl | notice system: 5 RecvNotice, 3 SendNotice, 2 SendQuery (sections 4-5) | not linked; used by artifacts.display.ArtifactActionButton, artifacts.display.ArtifactsCollectionActionButtons, charPicker.CharacterPreview +5 |
| GM_Sound | engNoticeSystemImpl | notice system: 0 RecvNotice, 1 SendNotice, 0 SendQuery (sections 4-5) | not linked; used by artifactsFoundry.PowerGraphCategorizedItemDisplay, artifactsFoundry.RecommendedPowerBar |
| GM_StatusIcon | engNoticeSystemImpl | notice system: 5 RecvNotice, 1 SendNotice, 0 SendQuery (sections 4-5) | not linked; used by statusicondisplay.StatusIconDisplay |
| GM_Tutorial | engNoticeSystemImpl | notice system: 3 RecvNotice, 1 SendNotice, 0 SendQuery (sections 4-5) | not linked; used by hints.HintManager |
| GM_UI | engNoticeSystemImpl | notice system: 54 RecvNotice, 55 SendNotice, 19 SendQuery (sections 4-5) | not linked; used by artifacts.display.ArtifactsCollectionActionButtons, chat.ChatLauncher, contacts.SelfPresenceDisplay +65 |
| GM_Upgrade | engNoticeSystemImpl | notice system: 13 RecvNotice, 12 SendNotice, 13 SendQuery (sections 4-5) | not linked; used by artifacts.data.ArtifactDataManager, artifacts.display.PurchasableArtifactWidget, artifactsFoundry.ArtifactFoundry +5 |
| GM_ViewMatch | engNoticeSystemImpl | notice system: 12 RecvNotice, 10 SendNotice, 4 SendQuery (sections 4-5) | not linked; used by billboard.BillboardManager, charPicker.CharacterPicker, charPicker.skinPicker.SkinPicker +22 |
| GM_Vitals | engNoticeSystemImpl | notice system: 4 RecvNotice, 0 SendNotice, 3 SendQuery (sections 4-5) | not linked; used by skills2.SkillsPanel, vitals.OverheadVitalsDeluxe, vitals.OverheadVitalsSimple +1 |
| IPropertyChangeListener |  | interface for PropertySystem listeners | not linked; used by announcements.AnnouncementsManager, mainhud.MainHUD, properties.PropertyObserver +4 |
| PropertySystem |  | property registry; C++ calls OnPropertyAdded / OnPropertyChanged / OnPropertyRemoved / OnEntityDestruction; native: InqProperty, InqPropertyDID, RegisterProperty, SetProperty, UnregisterProperty | not linked; used by announcements.AnnouncementsManager, billboard.BillboardManager, charPanel.CharacterPanel +22 |
| TraceHandler |  | trace sink | unused (nothing references it) |
| engNoticeSystemImpl |  | notice registry; Register() calls Turbine.RegisterNotice(id, instance); C++ calls GM_*.RecvNotice_* and OnEntityDestruction; native: RegisterNotice, UnregisterNotice | unused (nothing references it) |
| gmInputMapPriority |  | input map priorities | unused (nothing references it) |

#### `floaty` - base of world-attached Flash elements (Turbine.Floaty descriptors)

| class | extends | role / C++ link | movies (DID low byte) |
|---|---|---|---|
| FloatyBase | ui_sys.UIWidget_Base | native: Floaty.CreateFloatyDesc, Floaty.DestroyFloatyDesc, Floaty.SetDescAttachType, Floaty.SetDescDistanceScale, Floaty.SetDescEdgeClamp, Floaty.SetDescHasDepth | `06` `10` `AB` |

#### `gameplay.accolades` - accolade strip (best champion / map / merit medals) on the stats, profile and scorecard screens

| class | extends | role / C++ link | movies (DID low byte) |
|---|---|---|---|
| Accolade | gfx.core.UIComponent | - | `AE` |
| AccoladeButton | gfx.controls.Button | sends: EM_Sound.Play | `AE` |
| AccoladeNavigator | ui_sys.UIWidget_Base | - | `AE` |
| Accolades | ui_sys.UIWidget_Base | - | `AE` |

#### `gameplay.amplifiers` - Amplifiers (loadout) screen: list of sets, slot assembler, purchase

| class | extends | role / C++ link | movies (DID low byte) |
|---|---|---|---|
| AmplifiersComponent | wrapper.ScreenComponent | - | `94` |
| AmplifiersScreen | wrapper.WrapperScreen | - | `94` |
| Assembler | ui_sys.UIWidget_Base | listens: Contextual.PurchaseContextualItemError, Contextual.PurchaseContextualItemSuccess, WebTicket.UI_OnWebTicketUpdated; sends: EM_Sound.Play, EM_WebTicket.UI_RequestWebTicket, GM_Amplifier.UI_RequestAllAmplifierBoutiqueData, GM_Amplifier.UI_RequestAllAmplifierSets, GM_Amplifier.UI_SaveAmplifierSet, GM_Amplifier.?UI_InqAmplifierSetIcons, GM_Amplifier.?UI_InqAmplifierSetSlotInfo, GM_Amplifier.?UI_InqAugmentModStoreUrls +2 | `75` `77` `94` `A8` |

#### `gameplay.amplifiers.data` - value objects for one amplifier (augment/mod) and one amplifier set

| class | extends | role / C++ link | movies (DID low byte) |
|---|---|---|---|
| AmplifierData | ownables.OwnableData | - | `6B` `6E` `94` |
| AmplifierSetData |  | - | `67` `6B` `94` `A5` |

#### `gameplay.amplifiers.display` - amplifier icons, list items, set icon picker, save ribbon

| class | extends | role / C++ link | movies (DID low byte) |
|---|---|---|---|
| AmplifierDisplay | ui_sys.UIWidget_Base | - | `6B` `94` |
| AmplifierDisplayButton | common.buttons.DoubleClickButton | - | `94` |
| AmplifierListItem | ui_sys.UIWidget_Base | - | `94` |
| AmplifierSetForSaleListItem | common.buttons.BasicTooltipButton | - | `94` |
| AmplifierSetIconButton | common.buttons.BasicTooltipButton | - | `94` |
| AmplifierSetIconSubmenu | ui_sys.UIWidget_Base | - | `94` |
| AmplifierSetListItem | common.buttons.BasicTooltipButton | - | `94` |
| AmplifierSlot | common.buttons.DoubleClickButton | - | `94` |
| SaveMiniRibbon | ui_sys.UIWidget_Base | - | `94` |

#### `gameplay.announcements` - dead code: level-up / skill-point announcements driven by properties (no movie links it)

| class | extends | role / C++ link | movies (DID low byte) |
|---|---|---|---|
| Announcement | ui_sys.UIWidget_Base | - | not linked; used by announcements.AnnouncementsManager |
| AnnouncementsManager | ui_sys.UIWidget_Base | listens: Advancement.SkillRanked, Character.AgentControlledByThePlayerChanged, Encounter.UI_AddObjective, UI.ExitingWorld; props: Level, SkillPoints | unused (nothing references it) |

#### `gameplay.artifacts.data` - in-match shop (artifact) catalogue: item data read from C++ queries (GM_Artifact) and the provider used by the foundry

| class | extends | role / C++ link | movies (DID low byte) |
|---|---|---|---|
| ArtifactBasicData |  | - | `84` `87` |
| ArtifactData |  | - | `13` `84` `87` |
| ArtifactDataManager | gfx.events.EventDispatcher | listens: Upgrade.SetUIArtifactSkillSlotMapping; sends: GM_Artifact.?InqArtifactDetails, GM_Artifact.?InqAvailableArtifacts, GM_Artifact.?InqRecommendedArtifacts, GM_Artifact.?InqRemainingRecommendedArtifacts, GM_Upgrade.ChangeArtifactSkillSlotMapping, GM_Upgrade.RequestArtifactSkillSlotMapping, GM_Upgrade.?InqUpgradeFilters | `13` `84` `87` |
| ArtifactDataProvider |  | - | `84` `87` |
| CategoryFilterOption |  | - | `13` `84` `87` |
| IArtifactBasicDataProvider |  | - | `84` |

#### `gameplay.artifacts.display` - artifact buttons, drag avatars, rollovers and purchasable-item widgets (foundry + skill bar item slots)

| class | extends | role / C++ link | movies (DID low byte) |
|---|---|---|---|
| ArtifactActionButton | artifacts.display.ArtifactButton | sends: GM_Skill.?InqSkillToolTipInfo | `84` |
| ArtifactActionButtonDragTarget | gfx.controls.DragTarget | - | `84` |
| ArtifactBase | ui_sys.UIWidget_Base | - | `84` |
| ArtifactButton | common.buttons.DoubleClickButton | - | `84` `87` |
| ArtifactButtonDragAvatar | ui_sys.UIWidget_Base | - | `84` |
| ArtifactRollover | common.RolloverTarget | - | `84` |
| ArtifactsCollectionActionButtons | ui_sys.UIWidget_Base | listens: Skill.EnableSkillButton, Skill.UI_SkillUpdate, Skill.UpdateSkillUIOverlay, UI.ExecuteSkillError, UI.StartSkillCooldown, UI.UpdateSkillStackCountString; sends: EM_Sound.Play, GM_Skill.OnArtifactButtonRollover, GM_UI.SkillButtonPressed | `13` `5A` `84` |
| ArtifactsCollectionRollover | ui_sys.UIWidget_Base | sends: GM_MapManager.FlashUIToWorldClick | `84` |
| DetailedPurchasableArtifactButton | artifacts.display.PurchasableArtifactButton | - | `84` |
| FoundryCurrentArtifactWidget | artifacts.display.PurchasableArtifactWidget | - | `84` `87` |
| FoundryPADetailsPathWidget | artifacts.display.PurchasableArtifactWidget | - | `84` `87` |
| FoundryPurchasableArtifactWidget | artifacts.display.PurchasableArtifactWidget | - | `84` `87` |
| PurchasableArtifactButton | artifacts.display.ArtifactButton | - | `84` `87` |
| PurchasableArtifactWidget | ui_sys.UIWidget_Base | sends: GM_Upgrade.?InqSellDifferenceByDID | `84` `87` |

#### `gameplay.artifactsFoundry` - in-match shop (Artifact Foundry): tabs, recommended items, power-graph categories, buy/sell

| class | extends | role / C++ link | movies (DID low byte) |
|---|---|---|---|
| AdvancedPanel | artifactsFoundry.FoundryTabPanel | sends: GM_Artifact.?InqArtifactsMatchingCategoryFilterSet | `87` |
| ArtifactFoundry | common.BaseHudElement | listens: UI.ActionEnumEvent; sends: EM_Sound.Play, GM_Upgrade.Tutorial_ArtifactFoundryClosed, GM_Upgrade.Tutorial_ArtifactFoundryOpened | `87` |
| CategorizedItemDisplay | ui_sys.UIWidget_Base | - | `87` |
| CategoryFilterDisplay | ui_sys.UIWidget_Base | - | `87` |
| FoundryManager | gfx.events.EventDispatcher | listens: Advancement.SkillRanked, Encounter.UI_UpdateHasVendorAccess, UI.ExitingWorld, Upgrade.ActivatedArtifacts, Upgrade.ReturnedUpgradeArrayPreview, Upgrade.UI_RefreshPurchasability, Upgrade.UpdateCurrentUpgrades, Upgrade.UpdateNextRecommendedUpgrade; sends: EM_Sound.Play, GM_Encounter.UI_Mission_RaiseEvent, GM_Encounter.?InqCharacterCanShop, GM_Upgrade.PurchaseUpgrade, GM_Upgrade.RequestCurrentUpgrades, GM_Upgrade.RequestUpgradeArrayPreview, GM_Upgrade.SellUpgrade, GM_Upgrade.?InqCanBuyUpgrade +1 | `84` `87` |
| FoundryTabPanel | ui_sys.UIWidget_Base | - | `87` |
| GeneralItemDisplay | artifactsFoundry.CategorizedItemDisplay | - | `87` |
| PowerGraphCategorizedItemDisplay | artifactsFoundry.CategorizedItemDisplay | sends: EM_Sound.Play, GM_Sound.SetParameterAndPlay | `87` |
| RecommendedItemsDisplay | artifactsFoundry.CategorizedItemDisplay | - | `87` |
| RecommendedPanel | artifactsFoundry.FoundryTabPanel | - | `87` |
| RecommendedPowerBar | ui_sys.UIWidget_Base | sends: EM_Sound.Play, GM_Sound.SetParameterAndPlay | `87` |
| RecommendedSituationalItemsDisplay | artifactsFoundry.CategorizedItemDisplay | - | `87` |
| SelectedItemPanel | ui_sys.UIWidget_Base | - | `87` |

#### `gameplay.billboard` - full-screen billboards: announcements, map welcome banners, VICTORY/DEFEAT

| class | extends | role / C++ link | movies (DID low byte) |
|---|---|---|---|
| BasicIconBillboard | billboard.Billboard | - | `15` |
| Billboard | ui_sys.UIWidget_Base | - | `15` |
| BillboardManager | common.BaseHudElement | listens: Character.ClearAnnouncement, Character.ShowAnnouncement, Character.StopProcessingNewBillboards, Encounter.UI_PlayerJoined, Encounter.UI_PlayerLeft, Lobby.ClearLightResourcePackReferences; sends: GM_ViewMatch.?RequestInViewMatchMode; props: PVP_Team | `15` |
| CoastCityWelcomeBillboard | billboard.GenericTextBillboard | sends: EM_Sound.Play | `15` |
| GenericTextBillboard | billboard.Billboard | - | `15` |
| GothamHeightsWelcomeBillboard | billboard.GenericTextBillboard | sends: EM_Sound.Play | `15` |
| PlayerAnnounceBillboard | billboard.BasicIconBillboard | - | `15` |
| TestButtonsBillboard | MovieClip | - | `15` |
| WinLossBillboard | billboard.Billboard | - | `15` |

#### `gameplay.callingCard` - calling card (account icon + name + rank) shown in dialogs and tooltips

| class | extends | role / C++ link | movies (DID low byte) |
|---|---|---|---|
| CallingCardData | Object | - | `6B` `77` `80` `8B` `A0` |
| CallingCardDisplay | ui_sys.UIWidget_Base | - | `A0` |

#### `gameplay.charPanel` - in-match character panel (attributes / stats of the controlled or selected agent)

| class | extends | role / C++ link | movies (DID low byte) |
|---|---|---|---|
| AttributeDisplay | ui_sys.UIWidget_Base | - | `13` `5A` |
| CharacterPanel | common.BaseHudElement | props: Character_ConsoleVitals_Portrait, Name | `13` `5A` |
| IAttributeDisplayParent |  | - | `13` `5A` |
| StatsPanel | common.BaseHudElement | - | `13` `5A` |

#### `gameplay.charPicker` - champion picker grid used in the lobby (select, lock, role/skill preview)

| class | extends | role / C++ link | movies (DID low byte) |
|---|---|---|---|
| CharacterButton | common.buttons.BasicButton | sends: EM_Sound.Play; props: Character_SmallIcon | `22` |
| CharacterPicker | common.BaseHudElement | listens: Lobby.Draft_Selecting; sends: EM_Sound.Play, GM_Dialog.PlayUIDialogElement, GM_Encounter.UI_Mission_RaiseEvent, GM_Lobby.PlayerChangedCharacterLockStatus, GM_Lobby.RequestCharacterPickerInformation, GM_Lobby.SelectCharacter, GM_Lobby.TriggerWaitAfterReadyFlag, GM_ViewMatch.?RequestInViewMatchMode | `22` `67` |
| CharacterPreview | ui_sys.UIWidget_Base | listens: Lobby.ClearHeavyResourcePackReferences, Lobby.HeavyResourcePackLoaded; sends: GM_Character.?InqCharacterRoles, GM_Skill.?InqSkillToolTipInfo; props: Character_Name, Character_Skin_Name, Character_WallpaperImage | `22` |
| ReadyButton | common.buttons.TextButton | - | `22` |
| RolePreview | ui_sys.UIWidget_Base | - | `13` `22` `67` `6F` `A5` |
| SkillPreview | ui_sys.UIWidget_Base | - | `22` `6E` `A5` |

#### `gameplay.charPicker.skinPicker` - costume (variant) picker under the champion picker

| class | extends | role / C++ link | movies (DID low byte) |
|---|---|---|---|
| SkinButton | common.buttons.BasicButton | props: Character_Name, Character_SmallIcon | `22` |
| SkinPicker | ui_sys.UIWidget_Base | listens: Lobby.CharacterVariantsLoaded, Lobby.ClearLightResourcePackReferences; sends: EM_Sound.Play, GM_Lobby.SelectCharacter, GM_ViewMatch.?RequestInViewMatchMode | `22` |

#### `gameplay.chat` - chat window, chat tab button and launcher (C++ draws the text through UIWidget_Chat)

| class | extends | role / C++ link | movies (DID low byte) |
|---|---|---|---|
| Chat | common.BaseHudElement | - | `67` `75` `82` `83` `93` |
| ChatButton | common.buttons.TextButton | - | `83` |
| ChatLauncher | ui_sys.UIWidget_Base | listens: Chat.ToggleUnreadChat; sends: GM_UI.?InqChatButtonTooltip | `67` `75` `83` |

#### `gameplay.combometer` - dead code: kill-streak combometer test widgets

| class | extends | role / C++ link | movies (DID low byte) |
|---|---|---|---|
| AnimatingText | ui_sys.UIWidget_Base | - | unused (nothing references it) |
| Combometer | ui_sys.UIWidget_Base | - | unused (nothing references it) |
| Multiplier | MovieClip | - | unused (nothing references it) |
| StreakScore | ui_sys.UIWidget_Base | - | unused (nothing references it) |
| TestButtonsCombometer | MovieClip | - | unused (nothing references it) |

#### `gameplay.common` - shared base classes: HUD element base, rollover/tooltip targets, account XP bar, context menu

| class | extends | role / C++ link | movies (DID low byte) |
|---|---|---|---|
| AccountXPDisplay | ui_sys.UIWidget_Base | - | `6E` `78` `80` |
| BaseHudElement | ui_sys.UIWidget_Base | sends: EM_Sound.Play | 22 movies |
| ContextMenu | ui_sys.UIWidget_Base | - | `82` `8B` `93` |
| DragData |  | - | `84` |
| MoreEventTypes |  | - | 47 movies |
| RolloverIconContainer | utils.IconContainer | - | 13 movies |
| RolloverTarget | gfx.core.UIComponent | - | 12 movies |
| TooltipableComponent | common.RolloverTarget | - | `77` `8C` `9D` `9F` `A4` `AD` |

#### `gameplay.common.buttonBar` - tab bar

| class | extends | role / C++ link | movies (DID low byte) |
|---|---|---|---|
| TurbineButtonBar | gfx.controls.ButtonBar | - | `52` `5F` |

#### `gameplay.common.buttons` - button variants (tooltip, double click, queue, timer, glow, check box, inline text editor)

| class | extends | role / C++ link | movies (DID low byte) |
|---|---|---|---|
| BasicButton | gfx.controls.Button | sends: EM_Sound.Play | 44 movies |
| BasicTooltipButton | common.buttons.BasicButton | - | 26 movies |
| CheckBoxButton | common.buttons.TextButton | sends: EM_Sound.Play | `59` |
| DoubleClickButton | common.buttons.BasicTooltipButton | - | `6E` `82` `84` `87` `8B` `93` `94` |
| InlineTextEditor | ui_sys.UIWidget_Base | listens: UI.ActionEnumEvent; sends: EM_Sound.Play | `82` `8B` `93` |
| NarrowButton | common.buttons.BasicButton | - | `59` |
| QueueButton | gfx.controls.Button | - | `59` `6B` |
| TextButton | common.buttons.BasicButton | - | 12 movies |
| TextGlowButton | common.buttons.TextButton | - | `8B` `A5` `A8` |
| TextTimerButton | common.buttons.TextButton | - | `59` |

#### `gameplay.common.dropdown` - drop-down menu

| class | extends | role / C++ link | movies (DID low byte) |
|---|---|---|---|
| BasicDropDownMenu | gfx.controls.DropdownMenu | - | `59` `93` |
| DropDownListItem | gfx.controls.ListItemRenderer | - | `59` |

#### `gameplay.contacts` - friends / contacts panel: lists, groups, presence, invites, news panel

| class | extends | role / C++ link | movies (DID low byte) |
|---|---|---|---|
| ContactDisplay | ui_sys.UIWidget_Base | sends: GM_Chat.RunCmd, GM_Contacts.UI_AddNoteToContact, GM_CustomMatch.Invite_CustomMatch | `8B` |
| ContactListView | ui_sys.UIWidget_Base | - | `8B` |
| ContactSubmenu | common.ContextMenu | sends: GM_Chat.StartPlayerTell, GM_Contacts.UI_IgnoreUnignoreContact, GM_Contacts.UI_MoveContactToGroup, GM_Contacts.UI_RemoveContact | `8B` |
| ContactUtils |  | - | `8B` |
| ContactsComponent | ui_sys.UIWidget_Base | listens: Contacts.UI_ContactListNotification, Contacts.UI_NotifyContactOfInvitations, Contacts.UI_NotifyContactOfInvite, Contacts.UI_NotifyContactOfPendingInvites, CustomMatch.UI_CustomMatch_InviteCancelled, CustomMatch.UI_CustomMatch_Invited, Grouping.GroupInviteCanceled, Grouping.ShowGroupInviteDialog; sends: EM_Sound.Play, GM_Contacts.UI_ContactList_Ready | `75` `82` `8B` `90` `93` |
| ContactsPanelHeader | ui_sys.UIWidget_Base | sends: GM_Contacts.UI_InviteSteamFriends | `8B` |
| ContactsTabButton | common.buttons.TextButton | sends: EM_Sound.Play | `8B` `90` |
| ContactsTabPanel | ui_sys.UIWidget_Base | - | `8B` |
| GroupHeader | ui_sys.UIWidget_Base | sends: EM_Sound.Play | `8B` |
| GroupListExpandButton | common.buttons.TextButton | sends: EM_Sound.Play | `8B` |
| GroupSubmenu | common.ContextMenu | sends: GM_Contacts.UI_DestroyContactGroup | `8B` |
| InlineInviteEditor | common.buttons.InlineTextEditor | - | `8B` |
| InlineNewGroupEditor | common.buttons.InlineTextEditor | sends: GM_Contacts.UI_CreateContactGroup | `8B` |
| InviteForm | ui_sys.UIWidget_Base | sends: GM_Contacts.UI_InviteContact | `8B` |
| NewsPanel | contacts.ContactsTabPanel | - | `8B` |
| NotificationsTabButton | common.buttons.TextButton | - | `8B` `90` |
| SelfPresenceDisplay | ui_sys.UIWidget_Base | listens: Contacts.UI_NotifySelfChangedPresence, Contacts.UI_NotifySelfChangedStatusMessage, UI.SendHeaderNameAndProtectorIcons; sends: GM_Contacts.UI_AddStatusMessage, GM_Contacts.UI_UpdatePresence, GM_UI.RequestHeaderUIData | `8B` |

#### `gameplay.contacts.data` - contact and contact-group value objects

| class | extends | role / C++ link | movies (DID low byte) |
|---|---|---|---|
| Contact |  | - | `6B` `8B` |
| Group |  | - | `8B` |

#### `gameplay.contacts.notifications` - notification list and toast previews (friend, group, custom-match invites)

| class | extends | role / C++ link | movies (DID low byte) |
|---|---|---|---|
| CustomMatchInviteNotification | contacts.notifications.NotificationBase | sends: EM_Sound.Play, GM_CustomMatch.InviteResponse_CustomMatch | `8B` |
| CustomMatchInvitePreview | contacts.notifications.NotificationPreviewBase | sends: EM_Sound.Play, GM_CustomMatch.InviteResponse_CustomMatch | `8B` |
| FriendInviteNotification | contacts.notifications.NotificationBase | sends: EM_Sound.Play, GM_Contacts.UI_InviteResponse | `8B` |
| FriendInvitePreview | contacts.notifications.NotificationPreviewBase | sends: EM_Sound.Play, GM_Contacts.UI_InviteResponse | `8B` |
| GroupInviteNotification | contacts.notifications.NotificationBase | sends: EM_Sound.Play, GM_Chat.RunCmd | `8B` |
| GroupInvitePreview | contacts.notifications.NotificationPreviewBase | sends: EM_Sound.Play, GM_Chat.RunCmd | `8B` |
| NotificationBase | ui_sys.UIWidget_Base | - | `8B` |
| NotificationPreviewBase | ui_sys.UIWidget_Base | - | `8B` |

#### `gameplay.contacts.notifications.data` - notification value objects

| class | extends | role / C++ link | movies (DID low byte) |
|---|---|---|---|
| CustomMatchInviteData | contacts.notifications.data.NotificationDataBase | - | `8B` |
| FriendInviteData | contacts.notifications.data.NotificationDataBase | - | `8B` |
| GroupInviteData | contacts.notifications.data.NotificationDataBase | - | `8B` |
| NotificationDataBase |  | - | `8B` |

#### `gameplay.conversation` - conversation (dialogue) banner with speaker portraits

| class | extends | role / C++ link | movies (DID low byte) |
|---|---|---|---|
| ConversationBanner | conversation.ConversationDisplay | - | `9A` |
| ConversationDisplay | ui_sys.UIWidget_Base | - | `9A` |
| Fullscreen | conversation.ConversationDisplay | - | `9A` |
| Speaker | conversation.ConversationDisplay | sends: GM_Dialog.UI_AdvanceConversation | `9A` |

#### `gameplay.currency` - in-match currency counter (Upgrade_Currency property)

| class | extends | role / C++ link | movies (DID low byte) |
|---|---|---|---|
| UpgradeCurrencyDisplay | ui_sys.UIWidget_Base | listens: Encounter.UI_UpdateHasVendorAccess; sends: GM_Upgrade.ShowCurrencyCollectionRings | `13` `57` `5A` |

#### `gameplay.defeat` - death / respawn panel with the recommended-item purchase list

| class | extends | role / C++ link | movies (DID low byte) |
|---|---|---|---|
| DefeatManager | common.BaseHudElement | listens: Character.HideKillCard, Character.UI_ShowKillCard, Encounter.UI_UpdateHasBaseAccess, Encounter.UI_UpdateHasVendorAccess, UI.DefeatStatusUpdated; sends: GM_Encounter.?InqCharacterCanShop, GM_Options.?GetUIRecommendedPanelOption, GM_ViewMatch.?RequestInViewMatchMode | `13` |
| DefeatRecommendationsPanel | common.BaseHudElement | listens: Advancement.SkillRanked, Upgrade.UpdateNextRecommendedUpgrade; sends: EM_Sound.Play, GM_Advancement.RankSkill, GM_Advancement.?InqCanRankSkill, GM_Advancement.?InqNextRecommendedSkillToRank, GM_Advancement.?InqSkillPointsAvailableString, GM_Skill.?InqSkillToolTipInfo, GM_Upgrade.PurchaseUpgrade, GM_Upgrade.?InqCanBuyUpgrade +1 | `13` |
| PlusButton | common.buttons.BasicTooltipButton | - | `13` |
| TestButtonsDefeat | MovieClip | - | `13` |

#### `gameplay.defeat.killcard` - kill card: killer, contributors and damage sources

| class | extends | role / C++ link | movies (DID low byte) |
|---|---|---|---|
| ContributorRow | ui_sys.UIWidget_Base | sends: GM_Artifact.?InqKillCardArtifactTooltip | `13` `6F` |
| DamageSourceIcon | common.RolloverTarget | - | `6F` |
| KillCard | ui_sys.UIWidget_Base | props: Name | `13` `6F` |
| KillCardData |  | - | `13` |

#### `gameplay.defeat.statuses` - defeat status entry

| class | extends | role / C++ link | movies (DID low byte) |
|---|---|---|---|
| DefeatStatus | ui_sys.UIWidget_Base | - | `13` |

#### `gameplay.dialogs` - modal dialogs (confirm, purchase, browser, report a player, calling card, start menu, settings host, text entry)

| class | extends | role / C++ link | movies (DID low byte) |
|---|---|---|---|
| AmplifierPurchaseCompleteDialog | dialogs.DialogBase | sends: EM_Sound.Play | `80` |
| AmplifierPurchaseCompleteDialogData |  | - | `94` |
| AmplifierPurchaseDialog | dialogs.DialogBase | sends: EM_Sound.Play, GM_Contextual.UI_PurchaseContextualItem | `80` |
| AmplifierPurchaseDialogData |  | - | `94` |
| BrowserDialog | dialogs.DialogBase | listens: WebBrowser.OnJavaScriptCallback, WebBrowser.OnJavaScriptContextCreated, WebBrowser.OnLoadEnd, WebBrowser.OnLoadStart | `80` |
| BrowserDialogData |  | - | `0D` `75` `80` `94` |
| BrowserErrorDialog | dialogs.DialogBase | sends: EM_Sound.Play | `80` |
| CallingCardDialog | dialogs.DialogBase | listens: Character.SendAccountLevelAndXP, UI.SendHeaderNameAndProtectorIcons; sends: EM_Sound.Play, GM_Character.UI_SetProtectorIcon | `80` |
| CallingCardDialogData | Object | - | `77` |
| ConfirmationDialog | dialogs.DialogBase | sends: EM_Sound.Play | `80` |
| ConfirmationDialogData |  | - | `0D` `5F` `67` `75` `77` `82` `8B` |
| CustomMatchExitConfirmationDialog | dialogs.ConfirmationDialog | sends: GM_CustomMatch.Cancel_CustomMatch, GM_CustomMatch.Leave_CustomMatch | `80` |
| CustomMatchExitDialogData | dialogs.ConfirmationDialogData | - | `77` `80` `93` |
| DialogBase | menus.HudMenuFullControl | - | `0D` `5F` `80` |
| DualCurrencyPurchaseCompleteDialog | dialogs.DialogBase | sends: EM_Sound.Play | `80` |
| DualCurrencyPurchaseDialog | dialogs.DialogBase | sends: EM_Sound.Play, GM_Contextual.UI_PurchaseContextualItem | `80` |
| ErrorDialogData |  | - | `5F` `75` `7C` `80` `82` `94` |
| GroupExitConfirmationDialog | dialogs.ConfirmationDialog | - | `80` |
| GroupInviteDialog | dialogs.DialogBase | listens: UI.FoundMatch; sends: EM_Sound.Play, GM_Chat.RunCmd, GM_Grouping.ClearInvite | `80` |
| GroupInviteDialogData |  | - | unused (nothing references it) |
| MajorUpdateDialog | dialogs.DialogBase | sends: GM_UI.AcknowledgeMajorUpdateNews | `80` |
| MovieDialog | dialogs.DialogBase | sends: EM_Sound.Play, GM_UI.OnEndOfMatchMovieEnded | `80` |
| ReportAPlayerDialog | dialogs.DialogBase | sends: EM_Sound.Play, GM_PlayerReport.ReportAPlayer | `80` |
| ReportAPlayerDialogData |  | sends: GM_PlayerReport.?InqReportAPlayerOptions | `8C` |
| SaveDiscardCancelDialog | dialogs.DialogBase | sends: EM_Sound.Play | `80` |
| SaveDiscardCancelDialogData |  | - | `75` `77` `80` `94` `A8` |
| SettingsPanelDialog | dialogs.DialogBase | sends: EM_Sound.Play, GM_Options.OnApplyOptions, GM_Options.SetConstrainCursorOption, GM_UI.?IsLoggedIntoGame | `5F` |
| StartMenuDialog | dialogs.DialogBase | sends: GM_Encounter.SurrenderResponse, GM_Options.SetConstrainCursorOption, GM_UI.ExitToMainMenu, GM_UI.RequestExitGame, GM_UI.ShowHelp, GM_UI.UIStateMachineEvent, GM_UI.?InqCreditsURL | `0D` |
| StartMenuDialogData | Object | - | `0D` `67` `75` |
| TextEntryDialog | dialogs.ConfirmationDialog | listens: UI.ActionEnumEvent; sends: EM_Sound.Play | `80` |
| TextEntryDialogData | dialogs.ConfirmationDialogData | - | `8B` |

#### `gameplay.disconnect` - disconnect / error dialog

| class | extends | role / C++ link | movies (DID low byte) |
|---|---|---|---|
| DisconnectDialog | ui_sys.UIWidget_Base | - | `67` `6C` `75` |
| DisconnectManager | ui_sys.UIWidget_Base | listens: UI.gmWErrorMessageOccurred | `67` `6C` `75` |

#### `gameplay.eventTimer` - match event timeline (timeline banners and events)

| class | extends | role / C++ link | movies (DID low byte) |
|---|---|---|---|
| EventAnnouncementDisplay | ui_sys.UIWidget_Base | sends: EM_Sound.Play | `65` |
| EventTimelineDisplay | ui_sys.UIWidget_Base | - | `65` |
| EventTimerV2 | ui_sys.UIWidget_Base | listens: Encounter.UI_MissionEvent_AddTimelineBanner, Encounter.UI_MissionEvent_AddTimelineEvent, Encounter.UI_MissionEvent_BatchAddTimelineEvent, Encounter.UI_MissionEvent_RemoveTimelineBanner, Encounter.UI_MissionEvent_RemoveTimelineEvent, Encounter.UI_MissionEvent_StartTimeline; sends: EM_Sound.Play, GM_Encounter.UI_ReadyForTimelineData | `0C` `65` `A1` |

#### `gameplay.eventTimer.timeline` - timeline event buttons and data

| class | extends | role / C++ link | movies (DID low byte) |
|---|---|---|---|
| NowMarkerButton | ui_sys.UIWidget_Base | - | `65` |
| TimelineEvent | ui_sys.UIWidget_Base | - | `65` |
| TimelineEventButton | common.buttons.BasicTooltipButton | - | `65` |
| TimelineEventData |  | - | `65` `6B` |

#### `gameplay.experience` - in-match experience bar and XP award animation

| class | extends | role / C++ link | movies (DID low byte) |
|---|---|---|---|
| ExperienceAnimation | ui_sys.UIWidget_Base | - | `11` |
| ExperienceAward | utils.EntityPropertyObserver | listens: Character.AgentControlledByThePlayerChanged; props: XP | `11` |
| ExperienceBar | ui_sys.UIWidget_Base | sends: GM_Advancement.ShowExperienceRings | `11` |
| ExperienceConsole | common.BaseHudElement | sends: GM_Advancement.?InqLevelCap, GM_Advancement.?InqXPForLevel | `11` |
| TestButtonsExperience | MovieClip | props: Level, XP | `11` |
| TestButtonsExperienceAward | MovieClip | - | `11` |

#### `gameplay.floaty` - managers for floaty vital bars and floaty training text

| class | extends | role / C++ link | movies (DID low byte) |
|---|---|---|---|
| FloatyVerb | floaty.FloatyBase | native: Floaty.CreateFloatyDesc, Floaty.DestroyFloatyDesc | `10` `AB` |
| FloatyVerbsManager | ui_sys.UIWidget_Base | listens: UI.UpdateTrainingFloatyText; sends: GM_UI.TrainingFloatyManager_OnLoadComplete, GM_UI.TrainingFloatyManager_OnUnloadComplete | `10` |
| FloatyVitalsManager | ui_sys.UIWidget_Base | listens: UI.FadeFloatyVitals, UI.UpdateFloatyVitalArray; sends: GM_Encounter.?IsLoginEncounterPVP, GM_UI.FloatyVitalsManager_OnLoadComplete, GM_UI.FloatyVitalsManager_OnUnloadComplete | `10` |
| VitalsVerb | ui_sys.UIWidget_Base | - | `06` `10` `AB` |

#### `gameplay.fps` - FPS counter

| class | extends | role / C++ link | movies (DID low byte) |
|---|---|---|---|
| FPSDisplay | common.TooltipableComponent | listens: UI.FPSUpdate; sends: GM_ViewMatch.?RequestInViewMatchMode | `9F` |

#### `gameplay.herograph` - hero graph / power bar (stat growth from purchased items)

| class | extends | role / C++ link | movies (DID low byte) |
|---|---|---|---|
| HeroGraph | ui_sys.UIWidget_Base | listens: Upgrade.UpdatePowerGraphValues; sends: GM_Upgrade.?InqBasePowerGraphValues | `13` `5E` `62` `6B` `8C` |
| HeroGraph2 | ui_sys.UIWidget_Base | - | `5E` |
| HeroGraph2Button | common.buttons.BasicTooltipButton | - | `0C` `13` `5A` `5E` `62` `6F` `8C` |
| HeroGraph2Display | ui_sys.UIWidget_Base | sends: GM_MapManager.FlashUIToWorldClick | `5E` |
| HeroGraphData | Object | - | `13` `5E` `62` `6B` `8C` |
| IPowerBarContainer |  | - | `5E` `87` |
| LineGraph | ui_sys.UIWidget_Base | - | `13` `5E` `62` |
| PowerBar | ui_sys.UIWidget_Base | - | `5E` |

#### `gameplay.hints` - tutorial hint popups

| class | extends | role / C++ link | movies (DID low byte) |
|---|---|---|---|
| Hint | ui_sys.UIWidget_Base | sends: EM_Sound.Play | `70` |
| HintButton | common.buttons.BasicTooltipButton | - | `70` |
| HintManager | common.BaseHudElement | listens: Tutorial.UI_CloseTutorialHint, Tutorial.UI_ShowTutorialHint, Tutorial.UI_ShowTutorialHints; sends: GM_Tutorial.UIReadyForTutorialHints | `70` |

#### `gameplay.hints.data` - hint value object

| class | extends | role / C++ link | movies (DID low byte) |
|---|---|---|---|
| HintData | Object | - | `6B` `70` |

#### `gameplay.killdisplay` - kill feed

| class | extends | role / C++ link | movies (DID low byte) |
|---|---|---|---|
| KillDisplay | ui_sys.UIWidget_Base | - | `5B` |
| KillDisplayData |  | - | `5B` |
| KillDisplayManager | common.BaseHudElement | listens: Character.NotifyPlayerDied; sends: GM_ViewMatch.?RequestInViewMatchMode | `5B` |
| PlayerDisplay | ui_sys.UIWidget_Base | - | `5B` |

#### `gameplay.lobby` - pre-match lobby: team displays, header, curtain, launch warning, tips, draft/ban

| class | extends | role / C++ link | movies (DID low byte) |
|---|---|---|---|
| BannedDisplay | ui_sys.UIWidget_Base | - | `67` |
| Curtain | ui_sys.UIWidget_Base | - | `67` |
| CurtainPlayerDisplay | lobby.PlayerDisplay | props: Character_Name, Character_Skin_Name | `67` |
| ForceLaunchText | ui_sys.UIWidget_Base | - | `67` |
| LaunchWarning | ui_sys.UIWidget_Base | sends: EM_Sound.Play, GM_Dialog.PlayUIDialogElement | `67` |
| LobbyHeader | common.BaseHudElement | - | `67` |
| LobbyHeaderCenter | lobby.LobbyHeader | listens: Lobby.LobbyEncounterDetails, UI.UIStateMachineEvent | `67` |
| LobbyHeaderLeft | lobby.LobbyHeader | - | `67` |
| LobbyHeaderRight | lobby.LobbyHeader | listens: Lobby.HideBackButton, Lobby.MatchLaunchWarning, Lobby.PlayerSelectedEarlyLaunchFromServer, UI.ActionEnumEvent, UI.UIStateMachineEvent; sends: GM_Lobby.ExitLobbyToMainMenu | `67` |
| LobbyPlayerDisplay | lobby.PlayerDisplay | listens: Lobby.Draft_PlayersTrading; sends: GM_Lobby.Draft_RequestTrade | `67` |
| LobbyTeamDisplay | lobby.TeamDisplay | listens: Lobby.Draft_Banning, Lobby.Draft_EnableTrade, Lobby.Draft_Selecting | `67` |
| LobbyWrapper | ui_sys.UIWidget_Base | lobby host: curtains, header, character picker; listens: UI.ActionEnumEvent, UI.BatchNotifyHUDElements, UI.GameFrontUIDestroyedInCPP, UI.NotifyHUDElement, UI.ToggleMainMenu, UI.UIStateMachineEvent; sends: EM_Sound.Play, GM_Options.?GetUIConversationGroupScalingOption, GM_UI.UIStateMachineEvent, GM_ViewMatch.?RequestInViewMatchMode | `5F` `67` `75` `82` `83` `93` |
| PlayerDisplay | ui_sys.UIWidget_Base | sends: GM_Character.?InqCharacterRoles, GM_ViewMatch.?RequestInViewMatchMode | `67` |
| PlayerSecondaryPowerDisplay | ui_sys.UIWidget_Base | - | `67` |
| PvPLobby | common.BaseHudElement | lobby controller: team slots, lock state, picks, early launch; listens: Lobby.ClearLightResourcePackReferences, Lobby.Draft_Banning, Lobby.Draft_TradeRequest, Lobby.LobbyEncounterDetails, Lobby.MatchLaunchWarning, Lobby.PlayerPickedAmplifierSet, Lobby.PlayerPickedStolenPowers, Lobby.UpdateEarlyLaunchTime +6; sends: EM_Sound.Play, GM_Dialog.PlayUIDialogElement, GM_Dialog.SetUIDialogIdleState, GM_Dialog.SetUIDialogInQueueState, GM_Encounter.UI_Mission_RaiseEvent, GM_Lobby.Draft_TradeResponse, GM_Lobby.LobbyUIReady, GM_Lobby.PlayerSelectedEarlyLaunch +2 | `67` `75` `82` `83` `93` |
| TeamDisplay | ui_sys.UIWidget_Base | sends: GM_Lobby.TeamDisplayReady, GM_ViewMatch.?RequestInViewMatchMode | `67` |
| TipDisplay | ui_sys.UIWidget_Base | - | `67` |

#### `gameplay.lobby.amplifierSetPicker` - amplifier-set picker in the lobby

| class | extends | role / C++ link | movies (DID low byte) |
|---|---|---|---|
| AmplifierSetPicker | common.BaseHudElement | listens: Lobby.PlayerPickedAmplifierSet; sends: GM_Amplifier.?UI_InqCharacterDefaultAmplifierSet, GM_Lobby.RequestMyAmplifierSet | `67` |
| AmplifierSetPickerListItem | common.buttons.BasicTooltipButton | - | `67` `A5` |
| AmplifierSetPickerMenu | ui_sys.UIWidget_Base | sends: GM_Lobby.RequestChangeAmplifierSet, GM_ViewMatch.?RequestInViewMatchMode | `67` |

#### `gameplay.lobby.secondaryPower` - Stolen Power slots in the lobby

| class | extends | role / C++ link | movies (DID low byte) |
|---|---|---|---|
| SecondaryPowerButton | common.buttons.BasicTooltipButton | - | `67` `A4` `A5` |
| SecondaryPowerDisplay | common.BaseHudElement | listens: Lobby.PlayerPickedStolenPowers; sends: GM_Encounter.UI_Mission_RaiseEvent, GM_Lobby.RequestMyStolenPowers | `67` |

#### `gameplay.lobby.secondaryPower.powerPicker` - Stolen Power picker menu

| class | extends | role / C++ link | movies (DID low byte) |
|---|---|---|---|
| PowerPicker | common.BaseHudElement | sends: EM_Sound.Play, GM_Encounter.UI_Mission_RaiseEvent, GM_Lobby.RequestChangeStolenPower, GM_ViewMatch.?RequestInViewMatchMode | `67` |
| PowerPickerSubmenu | common.BaseHudElement | sends: GM_Character.?UI_RequestAspirationalTooltip | `67` |

#### `gameplay.login` - login, connecting and display-name screens

| class | extends | role / C++ link | movies (DID low byte) |
|---|---|---|---|
| ConnectingScreen | wrapper.WrapperScreen | listens: ConnectionManager.UpdateConnectionState; sends: EM_Sound.Play, GM_Character.?InqCharactersLoaded | `6D` |
| DisplayNameRequestScreen | wrapper.WrapperScreen | listens: UI.ActionEnumEvent, UI.ChargenError; sends: GM_UI.SubmitScreenName, GM_UI.?GetChargenError, GM_UI.?InqDefaultAccountName | `6D` |
| LoginScreen | wrapper.WrapperScreen | listens: ConnectionManager.ShowLoginError, UI.ActionEnumEvent; sends: EM_Sound.Play, GM_ConnectionManager.LoginWithWBID, GM_Options.SetSavedUsername, GM_UI.CreateAccount, GM_UI.ForgotPassword, GM_UI.ShowCursor, GM_UI.UIStateMachineEvent, GM_UI.?InqDefaultAccountName +1 | `6D` |
| LoginTextButton | common.buttons.TextButton | - | `6D` |

#### `gameplay.mainhud` - the in-match HUD root (attaches every HUD element) and dev test HUDs

| class | extends | role / C++ link | movies (DID low byte) |
|---|---|---|---|
| MainHUD | ui_sys.UIWidget_Base | in-match HUD root; listens: Character.StopProcessingNewBillboards, Encounter.NotifyMatchEnded, MapManager.ToggleMiniMap, UI.ActionEnumEvent, UI.BatchNotifyHUDElements, UI.DisplayDialogText, UI.ExitingWorld, UI.HideToViewMatchLayout +4; sends: GM_Chat.ShowChatWindow, GM_Encounter.?InqEncounterIdentifierType, GM_Options.SetIntOption, GM_Options.?GetIntOption, GM_Options.?GetShowUIFramingFillOption, GM_Options.?GetUICharPanelGroupScalingOption, GM_Options.?GetUIConversationGroupScalingOption, GM_Options.?GetUIKillCardGroupScalingOption +12; props: PVP_Team | 14 movies |
| TestButtonsMainHud | MovieClip | - | `51` `52` |
| TestButtonsTestHud | MovieClip | - | unused (nothing references it) |
| TestHUD | ui_sys.UIWidget_Base | listens: UI.ActionEnumEvent | `52` |
| WidgetTarget | ui_sys.UIWidget_Base | - | 33 movies |

#### `gameplay.match` - match bar: timer, team health, personal score, sector objectives

| class | extends | role / C++ link | movies (DID low byte) |
|---|---|---|---|
| MatchManager | common.BaseHudElement | listens: Encounter.NotifyMatchEnded, Encounter.SetMatchTime, Lobby.ClearLightResourcePackReferences; sends: GM_Encounter.?InqMatchTimes, GM_ViewMatch.?RequestInViewMatchMode, GM_ViewMatch.?RequestTeamGhostedAs; props: PVP_Team | `0C` |
| MatchTeamDisplay | ui_sys.UIWidget_Base | sends: GM_Encounter.UI_ReadyForDefeatStatus | `0C` |
| MatchTimer | ui_sys.UIWidget_Base | - | `0C` `6B` `A1` |
| PersonalScore | ui_sys.UIWidget_Base | - | `0C` |
| SectorObjective | ui_sys.UIWidget_Base | - | `0C` `A1` |
| SectorObjectiveTracker | ui_sys.UIWidget_Base | listens: Encounter.UI_BatchUpdateTrackerStatus, Encounter.UI_UpdateTrackerStatus; sends: GM_Encounter.?UI_InqSectorObjectives | `0C` `A1` |
| TeamDisplayContainer | ui_sys.UIWidget_Base | - | `0C` |
| TeamHealthDisplay | ui_sys.UIWidget_Base | listens: Encounter.UI_InitialTeamHealthUpdate, Encounter.UI_UpdateTeamHealth; sends: EM_Sound.Play, GM_Encounter.RequestCurrentTeamHealth | `0C` `A1` |
| TeamPlayerDisplay | ui_sys.UIWidget_Base | - | `0C` |
| TestButtonsMatch | MovieClip | - | `0C` |

#### `gameplay.menus` - HUD menu control (unused) and test buttons

| class | extends | role / C++ link | movies (DID low byte) |
|---|---|---|---|
| HudMenuFullControl | ui_sys.UIWidget_Base | listens: UI.ActionEnumEvent | not linked; used by dialogs.DialogBase |
| TestButtonsStartMenu | MovieClip | - | `0D` |

#### `gameplay.minimap` - minimap, map notes, pings, effects

| class | extends | role / C++ link | movies (DID low byte) |
|---|---|---|---|
| Effect | ui_sys.UIWidget_Base | - | `0F` |
| MapNote | ui_sys.UIWidget_Base | - | `0F` |
| MinimapMouseTarget | ui_sys.UIWidget_Base | listens: MapManager.SetPingPrepped, UI.ActionEnumEvent; sends: GM_MapManager.SendMiniMapMouseCoords, GM_MapManager.TriggerMiniMapNotice, GM_MapManager.TriggerPreparedPing | `0F` |
| MinimappyThing | common.BaseHudElement | listens: Encounter.UI_BatchUpdateTrackerStatus, Encounter.UI_UpdateTrackerStatus, MapManager.AddMapNotes, MapManager.AddStaticMapNote, MapManager.DeliverMapData, MapManager.MapNote_UnderAttack, MapManager.RemoveMapNote, MapManager.ShowMiniMapTargetingRing +4; sends: GM_Encounter.RequestSectorObjectiveState, GM_MapManager.ReadyForMapData, GM_MapManager.SetAlertPingPreppedFromUI, GM_MapManager.SetRetreatPingPreppedFromUI, GM_MapManager.?InqMapNotes | `0F` |
| TestButtonsMinimap | MovieClip | - | `0F` |

#### `gameplay.newplayer` - first-time-player screen

| class | extends | role / C++ link | movies (DID low byte) |
|---|---|---|---|
| NewPlayerScreen | wrapper.WrapperScreen | listens: Achievement.AchievementDetails; sends: GM_Achievement.RequestAchievementDetails, GM_UI.DisplayedTutorialTakeover, GM_UI.?IsAdmin | `74` |

#### `gameplay.numbers` - bitmap number renderer

| class | extends | role / C++ link | movies (DID low byte) |
|---|---|---|---|
| GraphicalNumbers | gfx.core.UIComponent | - | `06` `65` `8D` |

#### `gameplay.objectiveUpdates2` - objectives tracker (categories, objectives, banners)

| class | extends | role / C++ link | movies (DID low byte) |
|---|---|---|---|
| CategoryData | Object | - | `64` |
| CategoryDisplay | ui_sys.UIWidget_Base | - | `64` |
| CategoryHeader | ui_sys.UIWidget_Base | sends: EM_Sound.Play | `64` |
| CategoryTooltip | ui_sys.UIWidget_Base | - | `64` |
| ObjectiveBannerDisplay | common.BaseHudElement | - | `64` |
| ObjectiveData | Object | - | `64` |
| ObjectiveDisplay | ui_sys.UIWidget_Base | sends: EM_Sound.Play | `64` |
| ObjectiveListDisplay | ui_sys.UIWidget_Base | sends: EM_Sound.Play | `64` |
| ObjectiveUpdates2 | common.BaseHudElement | listens: Encounter.UI_AddObjective, Encounter.UI_DeliverCurrentObjectives, Encounter.UI_DeliverObjectiveCategories, Encounter.UI_RemoveObjective, Encounter.UI_RemoveObjectiveCategory, Encounter.UI_SetObjectiveTrackerEnabled, Encounter.UI_UpdateObjectiveCategory_State, Encounter.UI_UpdateObjective_BannerText +8; sends: GM_Encounter.ReadyForObjectives | `64` |
| ProcessQueueItem | Object | - | `64` |

#### `gameplay.objectiveupdates` - old objective test buttons

| class | extends | role / C++ link | movies (DID low byte) |
|---|---|---|---|
| ObjectiveUpdatesTestButtons | MovieClip | - | unused (nothing references it) |

#### `gameplay.ownables` - owned-content value object (item statuses)

| class | extends | role / C++ link | movies (DID low byte) |
|---|---|---|---|
| OwnableData |  | - | `6B` `6E` `94` |

#### `gameplay.playerinfopanel` - player portraits panel (teams)

| class | extends | role / C++ link | movies (DID low byte) |
|---|---|---|---|
| PlayerInfoListItem | ui_sys.UIWidget_Base | sends: GM_Chat.RunCmd, GM_MapManager.FlashUIToWorldClick | `62` |
| PlayerInfoPanel | common.BaseHudElement | sends: GM_ViewMatch.?RequestInViewMatchMode | `62` |
| PlayerPortraitGroup | ui_sys.UIWidget_Base | - | `62` |

#### `gameplay.primitives` - simple meter

| class | extends | role / C++ link | movies (DID low byte) |
|---|---|---|---|
| SimpleMeter | ui_sys.UIWidget_Base | - | `0C` `13` `64` `65` `67` `A4` `A5` |

#### `gameplay.properties` - property observer helper

| class | extends | role / C++ link | movies (DID low byte) |
|---|---|---|---|
| PropertyObserver | gfx.events.EventDispatcher | - | `06` `10` |

#### `gameplay.ranks` - ranked tier badges and animated rank display

| class | extends | role / C++ link | movies (DID low byte) |
|---|---|---|---|
| AnimatedRankedDisplay | ranks.RankedDisplay | listens: ProfileUI.ProfileUI_HeavyResourcePackData; sends: EM_Sound.Play, GM_Dialog.PlayUIDialogElement, GM_UI.RankedBanner_SelectCharacter; props: Character_WallpaperImage | `B0` |
| BorderStar | gfx.core.UIComponent | - | `6E` `A4` `A5` `AD` `B0` |
| RankedButton | gfx.controls.Button | sends: EM_Sound.Play | `B0` |
| RankedDisplay | ui_sys.UIWidget_Base | - | `B0` |
| RankedDisplaySmall | ranks.RankedDisplay | - | `B0` |

#### `gameplay.resolution` - resolution sizer

| class | extends | role / C++ link | movies (DID low byte) |
|---|---|---|---|
| ResolutionSizer | ui_sys.UIWidget_Base | sends: EM_UI.ForceOnSized | `16` `20` `22` `67` `75` `80` `A7` |

#### `gameplay.ribbons` - toast ribbons (level up, match found, joined queue, rewards, purchases, dodge penalty)

| class | extends | role / C++ link | movies (DID low byte) |
|---|---|---|---|
| CharLevelUpRibbon | ribbons.RibbonBase | listens: UI.Scorecard_HeavyOnlyLoaded; sends: GM_UI.Scorecard_LoadCharacterHeavyOnly | `6E` |
| DodgerRibbon | ribbons.RibbonBase | - | `6E` |
| JoinedQueueRibbon | ribbons.RibbonBase | - | `6E` |
| LevelUpRibbon | ribbons.RibbonBase | sends: EM_Sound.Play | `6E` |
| MatchFoundRibbon | ribbons.RibbonBase | listens: Lobby.LobbyRoomCreated, UI.NumPlayersAcceptedMatch; sends: EM_Sound.Play, GM_UI.AcceptMatch, GM_UI.LeaveQueue | `6E` |
| PurchaseSuccessfulRibbon | ribbons.RibbonBase | - | `6E` |
| RankRibbon | ribbons.RibbonBase | sends: EM_Sound.Play, GM_UI.PlayerAcknowledgedStandingsChange | `6E` |
| RewardRibbon | ribbons.RibbonBase | sends: EM_Sound.Play, GM_Achievement.AcknowledgeAchievementDisplayed, GM_Character.UI_ClaimPostMatchReward | `6E` |
| RibbonBase | ui_sys.UIWidget_Base | - | `6E` |
| SuperRewardRibbon | ribbons.RibbonBase | listens: ProfileUI.ProfileUI_HeavyResourcePackData; sends: EM_Sound.Play, GM_Achievement.?InqSuperBannerVideoForAchievement, GM_Character.UI_ClaimPostMatchReward, GM_Skill.?InqSkillToolTipInfo, GM_UI.RewardBanner_SelectCharacter; props: Character_Name, Character_Skin_Name, Character_Superbanner_Audio, Character_WallpaperImage | `6E` |
| UpgradeUnlockRibbon | ribbons.RibbonBase | - | `6E` |

#### `gameplay.ribbons.data` - ribbon value objects

| class | extends | role / C++ link | movies (DID low byte) |
|---|---|---|---|
| CharLevelUpRibbonData | Object | - | `75` |
| LevelUpRibbonData | Object | - | not linked; used by singleton.RibbonManager |
| MatchFoundRibbonData |  | - | `77` |
| PurchaseSuccessfulRibbonData |  | - | unused (nothing references it) |
| RankRibbonData |  | - | `8C` `AD` `B2` |
| RewardDataItem | Object | - | `6E` `75` `B1` |
| RewardRibbonData | Object | - | `75` |
| UpgradeUnlockRibbonData |  | - | `75` |

#### `gameplay.ribbons.matchFound` - match-found ready indicators

| class | extends | role / C++ link | movies (DID low byte) |
|---|---|---|---|
| PlayerReadyIndicator | ui_sys.UIWidget_Base | - | `6E` |

#### `gameplay.ribbons.reward` - reward-choice and reward-grant items per PostMatchRewardType

| class | extends | role / C++ link | movies (DID low byte) |
|---|---|---|---|
| RewardChoice | ui_sys.UIWidget_Base | - | `6E` |
| RewardChoiceAccountIcon | ribbons.reward.RewardChoice | - | `6E` |
| RewardChoiceAmplifier | ribbons.reward.RewardChoice | - | `6E` |
| RewardChoiceMerit | ribbons.reward.RewardChoice | - | `6E` |
| RewardChoiceServerOriginated | ribbons.reward.RewardChoice | - | `6E` |
| RewardChoiceXP | ribbons.reward.RewardChoice | - | `6E` |
| RewardChoiceXPPercent | ribbons.reward.RewardChoice | - | `6E` |
| RewardGrant | ui_sys.UIWidget_Base | - | `6E` |
| RewardGrantAccountIcon | ribbons.reward.RewardGrant | - | `6E` |
| RewardGrantAmplifier | ribbons.reward.RewardGrant | - | `6E` |
| RewardGrantMerit | ribbons.reward.RewardGrant | - | `6E` |
| RewardGrantServerOriginated | ribbons.reward.RewardGrant | - | `6E` |
| RewardGrantXP | ribbons.reward.RewardGrant | - | `6E` |
| RewardGrantXPPercent | ribbons.reward.RewardGrant | - | `6E` |
| RewardSource | ui_sys.UIWidget_Base | - | `6E` |
| RewardSourceAchievement | ribbons.reward.RewardSource | - | `6E` |

#### `gameplay.roles` - role button

| class | extends | role / C++ link | movies (DID low byte) |
|---|---|---|---|
| RoleButton | common.buttons.BasicTooltipButton | sends: EM_Sound.Play | `22` `6F` `A5` `B2` |

#### `gameplay.secondaryPowers` - Stolen Power value object

| class | extends | role / C++ link | movies (DID low byte) |
|---|---|---|---|
| SecondaryPowerData |  | - | `67` `6B` `A4` `A5` |

#### `gameplay.selectionpanel` - selection (target) panel; its movie 0x2000008A is missing from the dump

| class | extends | role / C++ link | movies (DID low byte) |
|---|---|---|---|
| SelectionPanel | common.BaseHudElement | listens: Character.UpdateCharacterPanelInfo, SelectionSystem.ClearTrackedEntity, SelectionSystem.FoundTrackedEntity, SelectionSystem.LostTrackedEntity, SelectionSystem.UpdateTrackedEntity; props: Level, PerceivedType, Upgrade_Facade | not linked; used by mainhud.MainHUD |

#### `gameplay.settings` - settings panes (general, graphics, audio, UI, gameplay, coaching, key bindings)

| class | extends | role / C++ link | movies (DID low byte) |
|---|---|---|---|
| AudioPane | ui_sys.UIWidget_Base | listens: Sound.AudioQualityChanged; sends: GM_Options.SetAudioBinkVolumeOption, GM_Options.SetAudioCharacterThemeVolumeOption, GM_Options.SetAudioMasterVolumeOption, GM_Options.SetAudioMusicVolumeOption, GM_Options.SetAudioSFXVolumeOption, GM_Options.SetAudioVOAnnouncerVolumeOption, GM_Options.SetAudioVOCharacterVolumeOption, GM_Options.SetSoundQualityLevel +8 | `5F` |
| CoachingPane | ui_sys.UIWidget_Base | sends: GM_Options.RequestTrainingLessonsReset, GM_Options.SetCoachingContextualTipsEnabledOption, GM_Options.SetCoachingEnabledOption, GM_Options.SetCoachingPlayerOverheadTipsEnabledOption, GM_Options.SetTurretWarningEnabled, GM_Options.?GetCoachingContextualTipsEnabledOption, GM_Options.?GetCoachingEnabledOption, GM_Options.?GetCoachingPlayerOverheadTipsEnabledOption +1 | `5F` |
| GameplayPane | ui_sys.UIWidget_Base | listens: Camera.CameraLockedPreference; sends: GM_Options.SetAutoAttackOption, GM_Options.SetBoolOption, GM_Options.SetCharacterOutlineOption, GM_Options.SetFloatOption, GM_Options.SetSelfCastingOption, GM_Options.SetSmartCastingOption, GM_Options.?GetAutoAttackOption, GM_Options.?GetBoolOption +4 | `5F` |
| GeneralPane | ui_sys.UIWidget_Base | - | `5F` |
| GraphicsPane | ui_sys.UIWidget_Base | - | `5F` |
| GraphicsPaneContents | ui_sys.UIWidget_Base | listens: Options.InGameFullScreenOptionChanged, Options.OutOfGameFullScreenOptionChanged, UI.GraphicsQualityChanged; sends: EM_UI.DetectAppropriateRenderSettings, EM_UI.?InqIsWindowsXP, GM_Options.SetAspectRatio, GM_Options.SetBoolOption, GM_Options.SetCinematicDrawDistance, GM_Options.SetDisplayAdapterOption, GM_Options.SetFloatOption, GM_Options.SetGraphicsCore +28 | `5F` |
| ISettingsPane |  | - | `5F` |
| KeybindingListItem | ui_sys.UIWidget_Base | - | `5F` |
| KeybindingPane | ui_sys.UIWidget_Base | listens: KeyBinding.UI_KeyBindingData, KeyBinding.UI_UpdateKeyBinding; sends: GM_KeyBinding.UI_CancelAllRebinds, GM_KeyBinding.UI_CommitAllRebinds, GM_KeyBinding.UI_RebindKey, GM_KeyBinding.UI_RequestKeyBindingData, GM_KeyBinding.UI_ResetAllToDefault | `5F` |
| SettingsViewStack | gfx.controls.ViewStack | - | `5F` |
| SliderGroup | ui_sys.UIWidget_Base | - | `5F` |
| UIPane | ui_sys.UIWidget_Base | - | `5F` |
| UIPaneContents | ui_sys.UIWidget_Base | sends: GM_Options.SetBoolOption, GM_Options.SetIntOption, GM_Options.SetShowUIFramingFillOption, GM_Options.SetTeamIndicator, GM_Options.SetUICharPanelGroupScalingOption, GM_Options.SetUIConversationGroupScalingOption, GM_Options.SetUIKillCardGroupScalingOption, GM_Options.SetUILetterboxGroupScalingOption +24 | `5F` |

#### `gameplay.singleton` - singleton data managers: they register the notices, cache the data and dispatch Flash events to the screens

| class | extends | role / C++ link | movies (DID low byte) |
|---|---|---|---|
| AccoladeManager | gfx.events.EventDispatcher | caches best champion / map accolades and end-of-match accolades; listens: Character.SendAccountEndOfMatchAccoladesEarned, Character.SendBestChampAccolades, Character.SendBestMapAccolades, UI.SendHeaderNameAndProtectorIcons; sends: GM_Character.RequestAccountEndOfMatchAccoladesEarned, GM_Character.UI_RequestBestAccolades, GM_UI.RequestHeaderUIData | `A3` `A4` `A5` `AA` |
| AchievementsManager | singleton.EventDispatchingSingletonManager | caches achievement definitions + progress, trainee achievements, protector advancement status; listens: Achievement.SetAchievementData, Achievement.SetAchievementObjectiveData, Achievement.SetDeprecatedAchievements, Achievement.TraineeAchievements, UI.ProtectorAdvancementStatus; sends: GM_Achievement.RequestAllAchievementData, GM_Achievement.RequestTraineeAchievements | 10 movies |
| AmplifierSetManager | singleton.EventDispatchingSingletonManager | caches the player's amplifier sets; answers icon / augment / mod queries from C++; listens: Amplifier.NotifyAmplifierSet, Amplifier.NotifyListAmplifierSets; sends: GM_Amplifier.UI_RequestAllAmplifierSets, GM_Amplifier.?UI_InqAmplifierSetIcons, GM_Amplifier.?UI_InqAugmentData, GM_Amplifier.?UI_InqModData | `67` `6E` `94` `A5` |
| BoutiqueDataManager | singleton.EventDispatchingSingletonManager | caches amplifier boutique (store) prices; listens: Amplifier.NotifyContextualAmplifierData; sends: GM_Amplifier.UI_RequestAllAmplifierBoutiqueData | `94` |
| ChatManager | singleton.EventDispatchingSingletonManager | shows/hides the chat window, browser chat hide; listens: Chat.UI_ShowWrapperGeneralChatWindow; sends: GM_Chat.HideChatForBrowser, GM_Chat.HideChatWindow, GM_Chat.RestoreChatForBrowser, GM_Chat.ShowChatWindow | 23 movies |
| ContactsManager | singleton.EventDispatchingSingletonManager | caches the contact list, groups and presence; listens: Contacts.UI_NotifyContactAccountIconChanged, Contacts.UI_NotifyContactAdded, Contacts.UI_NotifyContactChangeNote, Contacts.UI_NotifyContactChangeStatusMessage, Contacts.UI_NotifyContactChangeSteamName, Contacts.UI_NotifyContactChangedGroup, Contacts.UI_NotifyContactGroupCreated, Contacts.UI_NotifyContactGroupDestroyed +6 | `6B` `75` `8B` |
| ControlledAgentDispatcher | singleton.EventDispatchingSingletonManager | tracks the controlled agent IID and its Level/XP/SkillPoints/Upgrade_Currency/PVP_Team properties; listens: Character.ActiveAgentControlledByThePlayerChanged, Character.AgentControlledByThePlayerChanged, Character.UpdateCharacterPanelInfo, UI.ExitingWorld; sends: GM_Character.?InqCharacterPanelInfo, GM_Character.?InqCharacterPanelMetaData, GM_ViewMatch.?RequestInViewMatchMode, GM_ViewMatch.?RequestTeamGhostedAs; props: Level, PVP_Team, SkillPoints, Upgrade_Currency, XP | 22 movies |
| ConversationManager |  | conversation slots (show/hide/advance); listens: Dialog.HideAllConversationSlots, Dialog.HideConversationSlot, Dialog.HighlightConversationAdvanceButton, Dialog.ShowConversationSlot; sends: GM_Dialog.UI_ReadyForConversation, GM_Dialog.UI_SkipConversation | `67` `9A` |
| CustomMatchManager | singleton.EventDispatchingSingletonManager | caches the custom-match room; listens: CustomMatch.UI_CustomMatch_SetDraftMode, CustomMatch.UI_CustomMatch_SetEncounter, CustomMatch.UI_CustomMatch_SetTeamName, CustomMatch.UI_CustomMatch_UpdateProtectorIcon, CustomMatch.UI_DeliverCustomMatchData; sends: GM_CustomMatch.RequestCustomMatchData, GM_Lobby.?RequestTeamNames | `75` `77` `78` `93` `A4` |
| DataReferencesManager |  | drops DID references on ExitingWorld; listens: UI.ExitingWorld | 45 movies |
| DialogsManager | gfx.events.EventDispatcher | opens modal dialogs; tells C++ when the in-game menu opens/closes; sends: GM_UI.InGameMenuClosed, GM_UI.InGameMenuOpened, GM_UI.?IsBinkFileValid | 18 movies |
| EncounterManager | singleton.EventDispatchingSingletonManager | list of PvP encounters (C++ query), queue eligibility, protector status, map list reset; listens: Encounter.ResetMapSelectionList, UI.ProtectorAdvancementStatus, UI.QueueEligibility; sends: GM_Encounter.?InqPVPEncounters, GM_UI.?InqQueueEligibility | 16 movies |
| EventDispatchingSingletonManager | gfx.events.EventDispatcher | base class of the singletons | not linked; used by singleton.AchievementsManager, singleton.AmplifierSetManager, singleton.BoutiqueDataManager +10 |
| GameTimer |  | game clock synced every 5 s with Turbine.Timer.GetTime | `6E` `75` |
| HudModeManager |  | full-screen UI mode (camera); sends: GM_Camera.FullScreenUIActive | `87` |
| LanguageManager | gfx.events.EventDispatcher | client language; listens: UI.ClientLanguage; sends: GM_UI.RequestClientLanguage | `67` `75` |
| LeaderBoardManager | singleton.EventDispatchingSingletonManager | friends / regional leaderboards; listens: UI.DeliverFriendsLeaderboard, UI.DeliverRegionalLeaderboard; sends: GM_UI.RequestLeaderboards | `6B` `B0` `B2` |
| MatchData | singleton.EventDispatchingSingletonManager | in-match participants, teams, scorecard, upgrades, power graph, defeat status; listens: Encounter.AddParticipant, Encounter.RemoveParticipant, Encounter.UI_UpdateMatchScorecard, UI.DefeatStatusUpdatedForEntity, UI.ExitingWorld, UI.gmWErrorMessageOccurred, Upgrade.UpdateCurrentUpgrades, Upgrade.UpdatePowerGraphValues +1; sends: GM_Encounter.RequestMatchScorecard, GM_Lobby.?RequestTeamNames, GM_Skill.?InqSkillToolTipInfo, GM_Skill.?RequestStolenPowersForCharacter, GM_Upgrade.RequestSendEveryonesUpgrades, GM_ViewMatch.?RequestInViewMatchMode | 12 movies |
| NotificationPreviewsManager |  | notification toast queue; sends: EM_Sound.Play | `8B` |
| OwnablesManager | singleton.EventDispatchingSingletonManager | available champions, item statuses (ownership), champion advancement; listens: UI.AvailableCharacterList, UI.CharacterAdvancementData, UI.Incremental_ItemStatuses, UI.ItemStatuses; sends: GM_UI.RequestCharacterAdvancementData, GM_UI.RequestItemStatuses, GM_ViewMatch.?RequestInViewMatchMode | 13 movies |
| PVPGroupManager | gfx.events.EventDispatcher | PvP group state; listens: Grouping.GroupInformation, Grouping.PlayerLeftGroup, Grouping.UI_Grouping_UpdateProtectorIcon; sends: GM_Chat.RunCmd, GM_Contacts.UI_InviteContact, GM_Grouping.LeaveGroup, GM_Grouping.OnGroupPage, GM_Grouping.RequestGroupInformation, GM_UI.UIStateMachineEvent | `77` `82` |
| ProtectorIconManager |  | account (protector) icons list; sends: GM_Character.?RequestProtectorIcons | `6B` `6E` `80` `8B` |
| RankedManager | singleton.EventDispatchingSingletonManager | ranked standings (account and static tiers); listens: UI.UI_DeliverAccountStandingsData, UI.UI_DeliverStaticStandingsData; sends: GM_UI.RequestAccountStandingsData, GM_UI.RequestStaticStandingsData | `75` `77` `8C` `AD` `B2` |
| RibbonManager | gfx.events.EventDispatcher | queues ribbons (toasts); listens: UI.PendingMatchFailure | 10 movies |
| ScorecardManager | gfx.events.EventDispatcher | end-of-match data: stats, header, currency, XP, accolades, upgrades; listens: Character.SendAccountCurrencyBalance, Character.SendAccountEndOfMatchAccoladesEarned, Character.SendAccountEndOfMatchCharacterLevelAndXP, Character.SendAccountEndOfMatchLevelAndXP, Character.SendAccountEndOfMatchSoftCurrencyReward, Encounter.UI_SendEndOfMatchStats, Encounter.UI_SetEndOfMatchStatsHeader, UI.SendHeaderNameAndProtectorIcons +2; sends: GM_Character.RequestAccountCurrencyBalance, GM_Character.RequestAccountCurrencyBalanceChanges, GM_Character.RequestAccountEndOfMatchAccoladesEarned, GM_Character.RequestAccountEndOfMatchAccountLevelAndXP, GM_Character.RequestAccountEndOfMatchCharacterLevelAndXP, GM_Character.RequestAccountEndOfMatchSoftCurrencyReward, GM_Encounter.RequestPostMatchScorecard, GM_UI.RequestHeaderUIData | `75` `8C` `9D` `AD` |
| SecondaryPowerManager |  | Stolen Power list; sends: GM_Lobby.?RequestStolenPowerList | `67` `6E` `A4` `A5` `AD` |
| SettingsManager | singleton.EventDispatchingSingletonManager | key bindings and bool options; listens: KeyBinding.UI_KeyBindingData, KeyBinding.UI_UpdateKeyBinding; sends: GM_KeyBinding.UI_RequestKeyBindingData, GM_Options.SetBoolOption, GM_Options.?GetBoolOption | `56` `5F` `67` `6D` `75` `84` `9E` `9F` |
| TipManager |  | pre-game tips; listens: Lobby.PreGameTips; sends: GM_Lobby.RequestAllPregameTips | `67` |
| TooltipManager |  | shows every tooltip; sends: EM_Sound.Play | 56 movies |
| WrapperCookie |  | remembers the selected mode/encounter between wrapper screens (local only) | 11 movies |

#### `gameplay.singleton.attributes` - attribute metadata for the character panel

| class | extends | role / C++ link | movies (DID low byte) |
|---|---|---|---|
| AttributeMetadata |  | - | `13` `5A` |

#### `gameplay.singleton.data` - value objects cached by the singletons

| class | extends | role / C++ link | movies (DID low byte) |
|---|---|---|---|
| AccoladeData | Object | - | `6B` `AD` `AE` |
| AccountRankData |  | - | `B0` `B2` |
| AchievementData | Object | - | `78` `A2` |
| BoutiqueData |  | - | `80` |
| EncounterDataObject |  | - | `93` `A3` |
| KeyBindingsData |  | - | not linked; used by singleton.SettingsManager |
| ProtectorIconData | Object | - | not linked; used by singleton.ProtectorIconManager |
| RankData |  | - | `B0` |
| ScorecardData | Object | - | not linked; used by singleton.ScorecardManager |

#### `gameplay.singleton.datareferences` - interface for objects that hold DID references (cleared on ExitingWorld)

| class | extends | role / C++ link | movies (DID low byte) |
|---|---|---|---|
| IDataReferenceHolder |  | - | 45 movies |

#### `gameplay.singleton.matchdata` - per-agent and per-team data cached by MatchData

| class | extends | role / C++ link | movies (DID low byte) |
|---|---|---|---|
| AgentData |  | - | `0C` `62` `86` `A1` |
| TeamData |  | - | not linked; used by singleton.MatchData |

#### `gameplay.skills2` - skill bar: skill buttons, rank-up (+) buttons, cooldowns, item slots

| class | extends | role / C++ link | movies (DID low byte) |
|---|---|---|---|
| BasicSkillData |  | - | `56` `86` |
| RecallButton | common.buttons.BasicButton | sends: EM_Sound.Play | unused (nothing references it) |
| SkillButton | common.buttons.BasicTooltipButton | sends: EM_Sound.Play | `22` `56` `6E` `A5` |
| SkillControl | ui_sys.UIWidget_Base | sends: EM_Sound.Play, GM_Skill.OnSkillRollover, GM_Skill.?InqSkillToolTipInfo, GM_UI.SkillButtonPressed | `56` |
| SkillFeedback | ui_sys.UIWidget_Base | - | `56` |
| SkillsPanel | common.BaseHudElement | listens: Advancement.SkillRanked, Encounter.UI_UpdateHasBaseAccess, Skill.EnableSkillButton, Skill.UI_NotifySkillButtonUpdateIsSuppressed, Skill.UI_NotifyVitalChange, Skill.UI_SkillUpdate, Skill.UpdateSkillUIOverlay, UI.ActionEnumEvent +4; sends: EM_Sound.Play, GM_Advancement.RankSkill, GM_Advancement.?InqCanRankSkill, GM_Advancement.?InqNextRecommendedSkillToRank, GM_Advancement.?InqSkillPointsAvailableString, GM_Advancement.?InqSkillRank, GM_Character.?InqCharacterSkills, GM_Encounter.?InqCharacterIsInBase +3 | `56` |
| UpgradeButton | common.buttons.BasicTooltipButton | - | `56` |

#### `gameplay.state` - boot input handler, loading-into-world screen, UI state-machine helpers

| class | extends | role / C++ link | movies (DID low byte) |
|---|---|---|---|
| BootupInputHandler | ui_sys.UIWidget_Base | listens: Character.MasterCharacterListReceived, UI.ActionEnumEvent; sends: GM_Character.?InqCharactersLoaded | `20` `6D` |
| BootupInputHandlerWorld | state.BootupInputHandler | - | unused (nothing references it) |
| DynamicLoadingScreen | state.BootupInputHandler | sends: GM_Encounter.?InqLoadingScreen | unused (nothing references it) |
| LoadingIntoWorld | state.BootupInputHandler | - | `20` |
| StateMachineHelpers |  | sends Transition* UIStateMachineEvent notices; sends: GM_UI.ConnectToGameServer, GM_UI.UIStateMachineEvent | `20` `22` `67` `6D` `6E` `75` `A7` |

#### `gameplay.statusicondisplay` - buff / debuff icon row

| class | extends | role / C++ link | movies (DID low byte) |
|---|---|---|---|
| StatusIconContainer | utils.IconContainer | sends: GM_MapManager.FlashUIToWorldClick | `63` |
| StatusIconData |  | - | `63` |
| StatusIconDisplay | common.BaseHudElement | listens: StatusIcon.AddStatusIcon, StatusIcon.BatchAddStatusIcon, StatusIcon.RemoveStatusIcon, StatusIcon.UpdateStatusIcon, StatusIcon.UpdateStatusIconTooltip; sends: GM_StatusIcon.RequestStatusIcons | `63` |

#### `gameplay.surrender` - surrender vote panel

| class | extends | role / C++ link | movies (DID low byte) |
|---|---|---|---|
| SurrenderPanel | common.BaseHudElement | listens: Encounter.SurrenderVoteConcluded, Encounter.UpdateSurrenderData; sends: GM_Encounter.SurrenderResponse | `9C` |
| TimerBar | ui_sys.UIWidget_Base | - | `9C` |

#### `gameplay.test` - developer test movies

| class | extends | role / C++ link | movies (DID low byte) |
|---|---|---|---|
| Animation | test.Test | - | `52` |
| Attach | test.Test | - | `52` |
| BrowserSocialMedia | ui_sys.UIWidget_Base | listens: SocialMedia.UI_OnSocialMediaURLUpdated, UI.ActionEnumEvent, WebBrowser.OnConsoleMessage, WebBrowser.OnJavaScriptAlert, WebBrowser.OnJavaScriptCallback, WebBrowser.OnJavaScriptContextCreated, WebBrowser.OnLoadEnd, WebBrowser.OnPopUpWindowRequested +1; sends: EM_SocialMedia.UI_RequestSocialMediaURL | `73` |
| BrowserTest | ui_sys.UIWidget_Base | listens: SocialMedia.UI_OnSocialMediaURLUpdated, UI.ActionEnumEvent, WebBrowser.OnAddressChange, WebBrowser.OnConsoleMessage, WebBrowser.OnJavaScriptAlert, WebBrowser.OnJavaScriptCallback, WebBrowser.OnJavaScriptContextCreated, WebBrowser.OnLoadEnd +4; sends: EM_SocialMedia.UI_RequestSocialMediaURL | `73` |
| Components | test.Test | - | `52` |
| DDD | test.Test | - | `52` |
| DisplayTest | test.Test | - | `52` |
| Draw | test.Test | - | `52` |
| MoviePlayback | test.Test | - | `52` |
| Test | MovieClip | - | `52` |
| TestMode | MovieClip | - | `52` |
| Text | test.Test | - | `52` |

#### `gameplay.timers` - interval timers (countdown text)

| class | extends | role / C++ link | movies (DID low byte) |
|---|---|---|---|
| IntervalTimer |  | - | 12 movies |
| IntervalTimerPlus | timers.IntervalTimer | - | `59` `65` `67` |
| TimerTextComposite | MovieClip | - | unused (nothing references it) |

#### `gameplay.titleMenu` - dead code: old title menu

| class | extends | role / C++ link | movies (DID low byte) |
|---|---|---|---|
| GameStartButton | common.buttons.BasicButton | - | unused (nothing references it) |
| TitleMenu | state.BootupInputHandler | - | unused (nothing references it) |

#### `gameplay.tooltips` - every tooltip layout (driven by TooltipManager)

| class | extends | role / C++ link | movies (DID low byte) |
|---|---|---|---|
| AccoladeTooltip | tooltips.Tooltip | - | `6B` |
| AccountIconTooltip | tooltips.Tooltip | - | `6B` |
| AchievementTooltip | tooltips.Tooltip | - | `6B` |
| AmplifierSetTooltip | tooltips.Tooltip | - | `6B` |
| AmplifierTooltip | tooltips.Tooltip | - | `6B` `6E` |
| ArtifactLoreTooltip | tooltips.ArtifactTooltipBase | - | `6B` |
| ArtifactTooltip | tooltips.ArtifactTooltipBase | - | `6B` |
| ArtifactTooltipBase | tooltips.Tooltip | - | `6B` |
| AspirationalOption | ui_sys.UIWidget_Base | - | `6B` |
| AspirationalSubtip | ui_sys.UIWidget_Base | - | `6B` |
| AttributeTooltip | tooltips.Tooltip | - | `6B` |
| BasicTitledTooltip | tooltips.Tooltip | - | `6B` |
| BasicTooltip | tooltips.Tooltip | - | `6B` |
| BonusMeritTooltip | tooltips.Tooltip | - | `6B` |
| BorderStarTooltip | tooltips.Tooltip | - | `6B` |
| CallingCardTooltip | tooltips.Tooltip | - | `6B` |
| CharacterSimpleTooltip | tooltips.Tooltip | - | `6B` |
| ContactTooltip | tooltips.Tooltip | - | `6B` |
| DamageSourceTooltip | tooltips.Tooltip | - | `6B` |
| EventTimelineTooltip | tooltips.Tooltip | - | `65` `6B` |
| HeroGraphTooltip | tooltips.Tooltip | - | `6B` |
| HintTooltip | tooltips.Tooltip | - | `6B` |
| PlayerAgentTooltip | tooltips.Tooltip | - | `6B` |
| QueueTooltip | tooltips.Tooltip | - | `6B` |
| RankTooltip | tooltips.Tooltip | - | `6B` |
| RoleTooltip | tooltips.Tooltip | - | `6B` |
| ScorecardIconTooltip | tooltips.Tooltip | - | `6B` |
| SecondaryPowerTooltip | tooltips.Tooltip | - | `6B` |
| SingleSubtip | ui_sys.UIWidget_Base | - | `6B` |
| SkillTooltip | tooltips.Tooltip | - | `6B` |
| SkillTooltipGridRow | ui_sys.UIWidget_Base | - | `6B` |
| StatusIconTooltip | tooltips.Tooltip | - | `6B` |
| TeamPlayerDisplayTooltip | tooltips.Tooltip | - | `6B` |
| Tooltip | ui_sys.UIWidget_Base | - | `6B` `6E` |
| ValueText2Tooltip | tooltips.Tooltip | - | `6B` |
| ValueTextTooltip | tooltips.Tooltip | - | `6B` |

#### `gameplay.tooltips.data` - tooltip value objects

| class | extends | role / C++ link | movies (DID low byte) |
|---|---|---|---|
| AccountIconTooltipData | Object | - | `6B` `A4` `A5` |
| ArtifactTooltipData |  | sends: GM_Artifact.?InqArtifactDetails, GM_Artifact.?InqKillCardArtifactTooltip | `84` `87` |
| AspirationalSubtipData |  | - | `67` `6B` `A4` `A5` `AD` |
| AttributeTooltipData |  | - | `13` `5A` `6B` |
| BonusMeritTooltipData | Object | - | `77` `AD` |
| BorderStarTooltipData | Object | - | `6B` `6E` `A4` `A5` `AD` `B0` |
| CharacterSimpleTooltipData |  | - | `6B` `B2` |
| DamageSourceTooltipData |  | - | `13` `6B` `6F` |
| QueueTooltipData | Object | - | `59` `6B` |
| RankTooltipData |  | - | `6B` `B0` |
| RoleData |  | - | `13` `22` `67` `6B` `6F` `A5` |
| SkillTooltipData |  | - | `13` `22` `56` `62` `6B` `6E` `84` `A5` |
| ValueText2TooltipData | Object | - | `AD` |

#### `gameplay.topBar` - in-match top bar (menu, store, settings buttons)

| class | extends | role / C++ link | movies (DID low byte) |
|---|---|---|---|
| TopBar | ui_sys.UIWidget_Base | - | `5C` |
| TopBarLeft | topBar.TopBar | sends: GM_UI.TakeScreenShot, GM_UI.ToggleMainMenu | `5C` |

#### `gameplay.tutorialHighlight` - tutorial highlight tips (arrows on HUD elements)

| class | extends | role / C++ link | movies (DID low byte) |
|---|---|---|---|
| TutorialHighlightManager | ui_sys.UIWidget_Base | - | 23 movies |
| TutorialTip | ui_sys.UIWidget_Base | sends: EM_Sound.Play | 23 movies |
| TutorialTipData | Object | - | 24 movies |

#### `gameplay.viewmatch` - spectator HUD

| class | extends | role / C++ link | movies (DID low byte) |
|---|---|---|---|
| ViewMatchControls | ui_sys.UIWidget_Base | - | `86` |
| ViewMatchControlsBottom | viewmatch.ViewMatchControls | listens: ViewMatch.ViewMatchCameraChange, ViewMatch.ViewMatchFOWControls; sends: GM_ViewMatch.DirectedCameraButtonPressed, GM_ViewMatch.LockedCameraButtonPressed, GM_ViewMatch.RequestCameraInformation, GM_ViewMatch.RequestKillCardInfo, GM_ViewMatch.SwitchFOWTeam, GM_ViewMatch.ToggleFogOfWar | `86` |
| ViewMatchTop | common.BaseHudElement | listens: Encounter.NotifyMatchEnded, Encounter.SetMatchTime; sends: GM_Encounter.?InqMatchTimes | `A1` |
| ViewMatchTopCoastCity | viewmatch.ViewMatchTopMapSpecificBase | listens: ViewMatch.ViewMatch_UpdateTurretCounts; sends: GM_ViewMatch.RequestMatchStartCounts | `A1` |
| ViewMatchTopDivided | viewmatch.ViewMatchTopMapSpecificBase | listens: ViewMatch.ViewMatch_UpdateDampenerCounts, ViewMatch.ViewMatch_UpdateTurretCounts; sends: GM_ViewMatch.RequestMatchStartCounts | `A1` |
| ViewMatchTopMapSpecificBase | ui_sys.UIWidget_Base | - | `A1` |

#### `gameplay.viewmatch.players` - spectator player panels

| class | extends | role / C++ link | movies (DID low byte) |
|---|---|---|---|
| VMPlayers | common.BaseHudElement | - | `86` |
| VMPlayersSinglePlayerDisplay | ui_sys.UIWidget_Base | listens: ViewMatch.ViewMatchCameraChange, ViewMatch.ViewMatchPlayerSkillUse; sends: GM_ViewMatch.CameraGoToAgentClick | `86` |
| VMPlayersTeamPanel | ui_sys.UIWidget_Base | sends: GM_ViewMatch.RequestCameraInformation | `86` |
| VMSkillDisplay | ui_sys.UIWidget_Base | listens: Vitals.VitalsChanged | `86` |

#### `gameplay.viewmatch.scoreboard` - spectator scoreboard

| class | extends | role / C++ link | movies (DID low byte) |
|---|---|---|---|
| VMScoreboard | common.BaseHudElement | - | `86` |
| VMScoreboardRow | ui_sys.UIWidget_Base | - | `86` |
| VMScoreboardTeamPanel | ui_sys.UIWidget_Base | - | `86` |

#### `gameplay.vitals` - overhead vitals, large player/selection vitals, floaty damage / XP / currency / status text

| class | extends | role / C++ link | movies (DID low byte) |
|---|---|---|---|
| FloatyCurrencyContainer | ui_sys.UIWidget_Base | - | `06` |
| FloatyCurrencyText | MovieClip | - | `06` `10` |
| FloatyDamageContainer | ui_sys.UIWidget_Base | - | `06` |
| FloatyDamageText | MovieClip | - | `06` |
| FloatyExperienceContainer | ui_sys.UIWidget_Base | - | `06` |
| FloatyExperienceText | MovieClip | - | `06` |
| FloatyStatusContainer | ui_sys.UIWidget_Base | - | `06` |
| FloatyStatusText | MovieClip | - | `06` |
| OverheadVitalsBase | floaty.FloatyBase | listens: UI.ExitingWorld, Upgrade.UI_ShowFloatyCurrencyOverEntity, Vitals.DOTUpdate, Vitals.VitalsChanged; props: PVP_Team; native: Floaty.CreateFloatyDesc, Floaty.DestroyFloatyDesc | `06` `10` |
| OverheadVitalsDeluxe | vitals.OverheadVitalsBase | listens: Advancement.XPGained, Upgrade.DisplayFloatyCurrencyChanged, Upgrade.DisplayFloatyCurrencyDenied, Vitals.DisplayFloatyStatus, Vitals.VOTUpdate; sends: GM_UI.CharacterFloatyVitalsAdded, GM_Vitals.?InqSecondaryVitalType, GM_Vitals.?InqTemporaryVital, GM_Vitals.?InqVital; props: Character_ControllableAgentToPlayer_InstanceID, Level, Name | `06` `10` `86` |
| OverheadVitalsSimple | vitals.OverheadVitalsBase | sends: GM_Vitals.?InqTemporaryVital, GM_Vitals.?InqVital | `06` `10` |
| PlayerVitalsLarge | vitals.VitalsLarge | - | `2B` |
| SelectionVitalsLarge | vitals.VitalsLarge | - | `2B` |
| VitalBarColors |  | - | `06` |
| VitalsLarge | common.BaseHudElement | listens: Character.UpdateRegenValues, Vitals.VitalsChanged; sends: GM_Character.?InqRegenValues, GM_Vitals.?InqSecondaryVitalType, GM_Vitals.?InqTemporaryVital, GM_Vitals.?InqVital | `2B` |

#### `gameplay.vitals.vitalobservers` - vital bars and numbers bound to vitals

| class | extends | role / C++ link | movies (DID low byte) |
|---|---|---|---|
| ComboBarDisplay | vitals.vitalobservers.VitalBarBase | - | `06` `2B` |
| UtilityBarDisplay | vitals.vitalobservers.VitalBarBase | - | `06` `2B` |
| VitalBarBase | ui_sys.UIWidget_Base | - | `06` `10` `2B` |
| VitalBarScaling | vitals.vitalobservers.VitalBarBase | - | `06` `10` `2B` |
| VitalBarScalingLarge | vitals.vitalobservers.VitalBarScaling | - | `2B` |
| VitalNumberDisplay | vitals.vitalobservers.VitalPropertyObserver | - | `06` |
| VitalPropertyObserver | ui_sys.UIWidget_Base | listens: UI.ExitingWorld | `06` |
| VitalTextDisplay | vitals.vitalobservers.VitalPropertyObserver | - | `06` |

#### `gameplay.wrapper` - out-of-match shell: WrapperMain (screen state machine), screen base classes, per-screen settings

| class | extends | role / C++ link | movies (DID low byte) |
|---|---|---|---|
| ScreenComponent | ui_sys.UIWidget_Base | - | 12 movies |
| ScreenSettings |  | per-screen layout flags; LandingScreen variant depends on ProtectorAdvancementStatus | `75` |
| ScreenSettingsData | Object | - | `75` |
| WrapperBackground | ui_sys.UIWidget_Base | sends: GM_UI.?InqWrapperDisplayData | `67` `75` `9E` |
| WrapperBlankScreen | wrapper.WrapperScreen | sends: EM_Sound.Play | `75` |
| WrapperMain | ui_sys.UIWidget_Base | out-of-match shell: receives UIStateMachineEvent Load* events, swaps screens, header/footer/contacts/chat per ScreenSettings; listens: Achievement.AllPendingAchivementBanners, Character.RewardSetsData, Character.Ribbon_CharacterLevelChanged, Character.Ribbon_FinishedItemsFulfilled, Character.Ribbon_ItemFulfilled, Character.SendAccountCurrencyBalance, Character.SendAccountLevelAndXP, CustomMatch.UI_CustomMatch_Cancelled +16; sends: EM_Sound.Play, EM_WebBrowser.?InqFoundCEF3SubprocessExecutable, GM_Achievement.RequestAllPendingRewardlessAchievementNotifications, GM_Character.RequestAccountCurrencyBalance, GM_Character.RequestAccountLevelAndXP, GM_Character.RequestPostMatchChanges, GM_Character.Ribbon_ReceivedItemsFulfilled, GM_Character.UI_RequestPendingRewardUpdateFromServer +15 | 26 movies |
| WrapperScreen | ui_sys.UIWidget_Base | sends: EM_Sound.Play | 18 movies |

#### `gameplay.wrapper.achievements` - Achievements screen

| class | extends | role / C++ link | movies (DID low byte) |
|---|---|---|---|
| AchievementBar | ui_sys.UIWidget_Base | - | `A2` `A4` |
| AchievementButton | common.buttons.BasicButton | - | `A2` |
| AchievementDetail | ui_sys.UIWidget_Base | - | `A2` |
| AchievementDetailData | Object | - | `A2` `A4` `AD` |
| AchievementObjectiveListItem | gfx.core.UIComponent | - | `A2` |
| AchievementReward | gfx.core.UIComponent | - | `A2` `A4` |
| AchievementRewardListItem | gfx.core.UIComponent | - | `A2` |
| Achievements | ui_sys.UIWidget_Base | listens: Achievement.AchievementDetails; sends: GM_Achievement.RequestAchievementDetails | `A2` |
| AchievementsComponent | wrapper.ScreenComponent | - | `A2` |
| AchievementsScreen | wrapper.WrapperScreen | - | `A2` |

#### `gameplay.wrapper.characters` - Characters (collection) screen with champion details and costumes

| class | extends | role / C++ link | movies (DID low byte) |
|---|---|---|---|
| ChampionDetailPanel | ui_sys.UIWidget_Base | listens: ProfileUI.ProfileUI_AmplifierSetData, ProfileUI.ProfileUI_CharacterVariantsLoaded, ProfileUI.ProfileUI_HeavyResourcePackData, ProfileUI.ProfileUI_SpecialSecondaryPower; sends: EM_Sound.Play, GM_Character.?InqCharacterRoles, GM_Character.?UI_RequestAspirationalTooltip, GM_ProfileUI.ProfileUI_SelectCharacter, GM_Skill.?InqSkillToolTipInfo; props: Character_About, Character_Name, Character_Portrait_Audio, Character_Portrait_Audio_Stop, Character_Skin_Name, Character_SmallIcon, Character_WallpaperImage | `A5` |
| CharacterBrowser | ui_sys.UIWidget_Base | listens: UI.ActionEnumEvent | `A5` |
| CharacterBrowserButton | common.buttons.BasicTooltipButton | props: Character_Name, Character_SmallIcon | `A5` |
| CharacterData |  | - | not linked; used by singleton.OwnablesManager |
| CharacterSkinButton | common.buttons.BasicTooltipButton | props: Character_SmallIcon | `A5` |
| CharactersComponent | wrapper.ScreenComponent | - | unused (nothing references it) |
| CharactersScreen | wrapper.WrapperScreen | - | `A5` |

#### `gameplay.wrapper.customMatch` - Custom match screen: teams, holding pen, invites

| class | extends | role / C++ link | movies (DID low byte) |
|---|---|---|---|
| AssignedTeamPlayerDisplay | wrapper.customMatch.PlayerDisplayBase | sends: GM_CustomMatch.MovePosition_CustomMatch | `93` |
| CMPlayerSubmenu | common.ContextMenu | sends: GM_Contacts.UI_InviteContact, GM_CustomMatch.AssignTeam_CustomMatch, GM_CustomMatch.ChangeCoordinator_CustomMatch, GM_CustomMatch.GivePerm_CustomMatch, GM_CustomMatch.Kick_CustomMatch | `93` |
| CustomMatchComponent | wrapper.ScreenComponent | - | `93` |
| CustomMatchInlineInviteEditor | common.buttons.InlineTextEditor | - | `93` |
| CustomMatchInterface | ui_sys.UIWidget_Base | listens: Contacts.UI_NotifyContactAdded, CustomMatch.UI_CustomMatch_Cancelled, CustomMatch.UI_CustomMatch_Kicked, CustomMatch.UI_CustomMatch_Launched, CustomMatch.UI_CustomMatch_Left; sends: GM_CustomMatch.ForceLaunch, GM_CustomMatch.Launch_CustomMatch, GM_CustomMatch.SetDraftMode, GM_CustomMatch.SetEncounter, GM_UI.UIStateMachineEvent | `93` |
| CustomMatchInviteForm | ui_sys.UIWidget_Base | sends: GM_CustomMatch.Invite_CustomMatch | `93` |
| CustomMatchScreen | wrapper.WrapperScreen | - | `93` |
| CustomMatchTeamDisplay | ui_sys.UIWidget_Base | listens: UI.ActionEnumEvent; sends: GM_CustomMatch.SetTeamNames, GM_ViewMatch.?RequestAbleToViewMatch | `93` |
| HoldingPen | ui_sys.UIWidget_Base | sends: GM_CustomMatch.GivePerm_CustomMatch, GM_CustomMatch.Randomize | `93` |
| InviteDisplay | ui_sys.UIWidget_Base | - | `93` |
| InvitedPlayerDisplay | ui_sys.UIWidget_Base | sends: GM_Contacts.UI_InviteContact | `93` |
| PlayerDisplayBase | ui_sys.UIWidget_Base | sends: GM_CustomMatch.AssignTeam_CustomMatch | `93` |
| UnassignedPlayerDisplay | wrapper.customMatch.PlayerDisplayBase | sends: GM_CustomMatch.GivePerm_CustomMatch, GM_CustomMatch.Kick_CustomMatch | `93` |

#### `gameplay.wrapper.customMatch.data` - custom-match player value objects

| class | extends | role / C++ link | movies (DID low byte) |
|---|---|---|---|
| InvitedPlayerDataObject | Object | - | `93` |
| PlayerDataObject |  | - | `93` |

#### `gameplay.wrapper.encounterDetails` - encounter details screen

| class | extends | role / C++ link | movies (DID low byte) |
|---|---|---|---|
| EncounterDetails | ui_sys.UIWidget_Base | sends: GM_Encounter.PlayedEncounterOverviewMovie, GM_UI.UIStateMachineEvent | `A9` |

#### `gameplay.wrapper.encounters` - play flow: featured map, game mode, map selection, solo/group, tutorial selection

| class | extends | role / C++ link | movies (DID low byte) |
|---|---|---|---|
| EncFeaturedMapScreen | wrapper.WrapperScreen | sends: GM_UI.UIStateMachineEvent | `AA` |
| EncGameModeScreen | wrapper.WrapperScreen | sends: GM_UI.UIStateMachineEvent | `AA` |
| EncMapSelectionScreen | wrapper.WrapperScreen | sends: GM_UI.UIStateMachineEvent | `AA` |
| EncSoloGroupScreen | wrapper.WrapperScreen | sends: EM_Sound.Play, GM_CustomMatch.Create_CustomMatch, GM_Encounter.PlayedEncounterOverviewMovie, GM_Grouping.CacheQueueForGrouping, GM_UI.CanUserCreateGroup, GM_UI.UIStateMachineEvent, GM_UI.?GetWaitTimeForQueue | `AA` |
| EncTutorialSelectionScreen | wrapper.WrapperScreen | sends: GM_UI.UIStateMachineEvent | `AA` |
| HistoryBar | ui_sys.UIWidget_Base | - | `AA` |
| HumanBotDisplay | ui_sys.UIWidget_Base | - | `AA` |

#### `gameplay.wrapper.encounters.bigbuttons` - big tile buttons of the play flow

| class | extends | role / C++ link | movies (DID low byte) |
|---|---|---|---|
| EncBigButtonBase | ui_sys.UIWidget_Base | - | `AA` |
| FeaturedMapBigButton | wrapper.encounters.bigbuttons.MapBigButton | - | `AA` |
| GameModeBigButton | wrapper.encounters.bigbuttons.EncBigButtonBase | sends: GM_UI.UIStateMachineEvent | `AA` |
| MapBigButton | wrapper.encounters.bigbuttons.EncBigButtonBase | sends: GM_Encounter.DisplayEncounterWebInfo, GM_Encounter.PlayedEncounterOverviewMovie, GM_UI.UIStateMachineEvent, GM_UI.?GetWaitTimeForQueue | `AA` |
| TutorialBigButton | wrapper.encounters.bigbuttons.EncBigButtonBase | sends: GM_Encounter.DisplayEncounterWebInfo, GM_UI.UIStateMachineEvent | `AA` |

#### `gameplay.wrapper.footer` - wrapper footer (release notes link)

| class | extends | role / C++ link | movies (DID low byte) |
|---|---|---|---|
| FooterBkgd | ui_sys.UIWidget_Base | - | `67` `75` `90` |
| FooterCenter | ui_sys.UIWidget_Base | - | `75` `90` |
| FooterLogoLeft | ui_sys.UIWidget_Base | - | `75` `90` |
| FooterRight | ui_sys.UIWidget_Base | - | `75` `90` |
| ReleaseNotesElement | ui_sys.UIWidget_Base | listens: UI.ReleaseNotesUrl; sends: GM_UI.OpenURL, GM_UI.RequestReleaseNotesURL | `75` `90` |

#### `gameplay.wrapper.header` - wrapper header: profile, protector level, currency, matchmaking indicator, nav buttons, admin alerts

| class | extends | role / C++ link | movies (DID low byte) |
|---|---|---|---|
| Alert | gfx.core.UIComponent | - | `77` |
| HeaderBkgd | ui_sys.UIWidget_Base | - | `67` `75` `77` |
| HeaderCenter | ui_sys.UIWidget_Base | listens: AdminAlert.UI_NotifyAdminAlertsUpdated; sends: GM_AdminAlert.UI_RequestAdminAlerts, GM_CustomMatch.?IsInCustomMatch, GM_Grouping.?IsInGroup, GM_UI.UIStateMachineEvent | `75` `77` |
| HeaderController |  | - | `75` |
| HeaderCurrencyDisplay | ui_sys.UIWidget_Base | - | `77` |
| HeaderLeft | ui_sys.UIWidget_Base | listens: Character.SendAccountCurrencyBalance; sends: GM_Character.RequestAccountCurrencyBalance, GM_UI.RequestHeaderUIData | `75` `77` |
| HeaderProfile | ui_sys.UIWidget_Base | listens: UI.SendHeaderNameAndProtectorIcons; sends: GM_UI.UIStateMachineEvent | `77` |
| HeaderRight | ui_sys.UIWidget_Base | sends: GM_Dialog.PlayUIDialogElement, GM_UI.RequestExitGame, GM_UI.ShowHelp | `75` `77` |
| MatchmakingIndicator | ui_sys.UIWidget_Base | listens: UI.FindMatchFailure, UI.Matchmaking_NewUpdateInterval, UI.QueueWaitTimesUpdated; sends: EM_Sound.Play, GM_UI.ForceQueue, GM_UI.LeaveQueue, GM_UI.UIStateMachineEvent, GM_UI.?GetWaitTimeForQueue, GM_UI.?InqAccountMeritBonus | `77` |
| NavButtons | ui_sys.UIWidget_Base | sends: GM_UI.UIStateMachineEvent | `77` |
| ProtectorLevelDisplay | ui_sys.UIWidget_Base | - | `77` |

#### `gameplay.wrapper.landing` - landing screens (trainee / veteran), landing nav, PvP launcher

| class | extends | role / C++ link | movies (DID low byte) |
|---|---|---|---|
| LandingNav | ui_sys.UIWidget_Base | listens: UI.UIStateMachineEvent; sends: GM_UI.UIStateMachineEvent | `75` `A8` |
| LandingScreen | wrapper.WrapperScreen | - | `78` |
| LandingSwitcher | ui_sys.UIWidget_Base | sends: EM_Sound.Play, GM_UI.SetProtectorAdvancementStatusForSession | `A8` |
| MissionTypeButton | common.buttons.TextButton | sends: EM_Sound.Play | `59` |
| PVPLauncher | ui_sys.UIWidget_Base | listens: Achievement.TraineeAchievements; sends: GM_CustomMatch.?IsInCustomMatch, GM_Grouping.LeaveGroup, GM_Grouping.?IsInGroup, GM_Lobby.AttemptToRejoinLobbyRoom, GM_UI.UIStateMachineEvent | `77` |
| TooltipableReward | common.TooltipableComponent | - | `A4` |
| TraineeAchievementButton | common.buttons.BasicButton | - | `78` |
| TraineeAchievements | ui_sys.UIWidget_Base | listens: Achievement.AchievementDetails, UI.ProtectorAdvancementStatus, UI.SendHeaderNameAndProtectorIcons; sends: EM_Sound.Play, GM_Achievement.RequestAchievementDetails, GM_CustomMatch.?IsInCustomMatch, GM_Encounter.PlayedEncounterOverviewMovie, GM_Grouping.?IsInGroup, GM_UI.JoinQueueForPromotedMap, GM_UI.RequestHeaderUIData, GM_UI.UIStateMachineEvent +1 | `78` |
| VeteranAchievement | ui_sys.UIWidget_Base | listens: Achievement.AchievementDetails; sends: GM_Achievement.RequestAchievementDetails | `A4` |
| VeteranChampion | ui_sys.UIWidget_Base | listens: ProfileUI.ProfileUI_HeavyResourcePackData, ProfileUI.ProfileUI_SpecialSecondaryPower; sends: GM_Character.?UI_RequestAspirationalTooltip; props: Character_MiniWallpaperImage, Character_Name, Character_Skin_Name, Character_SmallIcon | `A4` |
| VeteranLanding | ui_sys.UIWidget_Base | listens: ProfileUI.ProfileUI_HeavyResourcePackData; sends: EM_Sound.Play, GM_ProfileUI.ProfileUI_SelectCharacter, GM_UI.UIStateMachineEvent; props: Character_Portrait_Audio, Character_Portrait_Audio_Stop, Character_WallpaperImage | `A4` |
| VeteranLandingScreen | wrapper.WrapperScreen | - | `A4` |
| VeteranLevelReward | ui_sys.UIWidget_Base | - | `A4` |
| VeteranMainScreenComponent | wrapper.ScreenComponent | - | unused (nothing references it) |
| VeteranMap | ui_sys.UIWidget_Base | listens: Encounter.UI_LastMapPlayed; sends: GM_CustomMatch.?IsInCustomMatch, GM_Encounter.RequestLastMapPlayed, GM_Grouping.?IsInGroup, GM_UI.JoinQueue | `A4` |

#### `gameplay.wrapper.landing.demo` - landing demo contents

| class | extends | role / C++ link | movies (DID low byte) |
|---|---|---|---|
| LandingDemoContents | ui_sys.UIWidget_Base | sends: GM_UI.JoinQueue | `7F` |

#### `gameplay.wrapper.launch` - launch movie player

| class | extends | role / C++ link | movies (DID low byte) |
|---|---|---|---|
| LaunchMoviePlayer | ui_sys.UIWidget_Base | listens: UI.ActionEnumEvent; sends: GM_Options.TemporaryFullScreen, GM_UI.?InqWrapperDisplayData, GM_UI.?IsBinkFileValid | `A7` |
| TheatreContainer | ui_sys.UIWidget_Base | - | `A7` |

#### `gameplay.wrapper.loginReward` - login rewards screen (daily reward timeline)

| class | extends | role / C++ link | movies (DID low byte) |
|---|---|---|---|
| LoginRewardScreen | wrapper.WrapperScreen | - | `B1` |
| LoginRewards | ui_sys.UIWidget_Base | sends: EM_Sound.Play, GM_UI.UIStateMachineEvent | `B1` |
| RewardCrisisCoins | wrapper.loginReward.RewardDisplay | - | `B1` |
| RewardDay | ui_sys.UIWidget_Base | sends: EM_Sound.Play | `B1` |
| RewardDayData |  | - | `B1` |
| RewardDisplay | ui_sys.UIWidget_Base | - | `B1` |
| RewardIcon | wrapper.loginReward.RewardDisplay | - | `B1` |
| RewardMerit | wrapper.loginReward.RewardDisplay | - | `B1` |
| RewardTimeline | ui_sys.UIWidget_Base | listens: LoginReward.UI_DeliverLoginRewardSet, LoginReward.UI_NoEligibleLoginReward; sends: EM_Sound.Play, GM_LoginReward.QueueLoginReward, GM_LoginReward.ReadyForLoginRewardSet | `B1` |

#### `gameplay.wrapper.missionSelect` - launch button and level image

| class | extends | role / C++ link | movies (DID low byte) |
|---|---|---|---|
| LaunchButton | common.buttons.TextButton | sends: EM_Sound.Play | `82` |
| LevelImage | ui_sys.UIWidget_Base | sends: GM_Encounter.DisplayEncounterWebInfo, GM_Encounter.PlayedEncounterOverviewMovie | `82` `8C` `93` `A9` |
| LevelImageDialog | wrapper.missionSelect.LevelImage | - | unused (nothing references it) |
| MissionButtonDataObject |  | - | `77` `A9` |

#### `gameplay.wrapper.profile` - account standings (ranked) on the profile

| class | extends | role / C++ link | movies (DID low byte) |
|---|---|---|---|
| PlayerAccountStandings | ui_sys.UIWidget_Base | - | `78` |

#### `gameplay.wrapper.profile.card` - protector icon (account icon) picker

| class | extends | role / C++ link | movies (DID low byte) |
|---|---|---|---|
| ProtectorIconButton | common.buttons.BasicTooltipButton | - | `80` |
| ProtectorIconSubmenu | ui_sys.UIWidget_Base | sends: EM_Sound.Play, GM_ViewMatch.?RequestInViewMatchMode | `80` |

#### `gameplay.wrapper.pvpGroup` - PvP group (party) screen

| class | extends | role / C++ link | movies (DID low byte) |
|---|---|---|---|
| IPVPGroupDisplay |  | - | `82` |
| IPVPGroupInviteForm |  | - | `82` |
| IPVPGroupPlayerDisplay |  | - | `82` |
| PVPGroupDisplay | ui_sys.UIWidget_Base | - | `82` |
| PVPGroupInlineInviteEditor | common.buttons.InlineTextEditor | - | `82` |
| PVPGroupInviteDisplay | ui_sys.UIWidget_Base | - | `82` |
| PVPGroupInviteForm | ui_sys.UIWidget_Base | sends: GM_Chat.RunCmd | `82` |
| PVPGroupInvitedPlayerDisplay | gfx.core.UIComponent | - | `82` |
| PVPGroupPlayerDisplay | gfx.core.UIComponent | - | `82` |
| PVPGroupPlayerSubmenu | common.ContextMenu | - | `82` |
| PVPGroupingInterface | ui_sys.UIWidget_Base | listens: Contacts.UI_NotifyContactAdded, UI.QueueWaitTimesUpdated; sends: GM_Grouping.LeaveGroup, GM_UI.JoinQueue, GM_UI.?GetWaitTimeForQueue | `82` |
| PVPGroupingScreen | wrapper.WrapperScreen | - | `82` |

#### `gameplay.wrapper.pvpGroup.data` - group member value objects

| class | extends | role / C++ link | movies (DID low byte) |
|---|---|---|---|
| PVPGroupInvitedPlayer | Object | - | `82` |
| PVPGroupPlayer | Object | - | `82` |

#### `gameplay.wrapper.ranked` - Ranked screen and leaderboards

| class | extends | role / C++ link | movies (DID low byte) |
|---|---|---|---|
| LeaderBoard | ui_sys.UIWidget_Base | - | `B2` |
| LeaderBoardEntry | ui_sys.UIWidget_Base | - | `B2` |
| LeaderBoardEntryData |  | - | not linked; used by singleton.LeaderBoardManager |
| Ranked | ui_sys.UIWidget_Base | listens: ProfileUI.ProfileUI_HeavyResourcePackData; sends: EM_Sound.Play, GM_UI.RequestLeaderboards; props: Character_Portrait_Audio, Character_Portrait_Audio_Stop, Character_WallpaperImage | `B2` |
| RankedComponent | wrapper.ScreenComponent | - | `B2` |
| RankedScreen | wrapper.WrapperScreen | - | `B2` |
| RankedStatus | ui_sys.UIWidget_Base | - | `B2` |

#### `gameplay.wrapper.scorecard` - end-of-match scorecard (summary, stats, accolades tabs)

| class | extends | role / C++ link | movies (DID low byte) |
|---|---|---|---|
| HeaderRow | ui_sys.UIWidget_Base | - | `8C` |
| MultiBar | ui_sys.UIWidget_Base | - | `AD` |
| NextChallenge | ui_sys.UIWidget_Base | listens: Achievement.AchievementDetails; sends: GM_Achievement.RequestAchievementDetails, GM_UI.UIStateMachineEvent | `8C` |
| PlayerRowData | Object | - | `8C` |
| ScoreFieldWithHighlight | ui_sys.UIWidget_Base | - | `8C` |
| Scorecard | ui_sys.UIWidget_Base | scorecard controller (tabs, rewards, exit); listens: Encounter.PlayEndOfMatchEncounterMovie, UI.Scorecard_HeavyOnlyLoaded, UI.UIStateMachineEvent; sends: EM_Sound.Play, GM_CustomMatch.?IsInCustomMatch, GM_Encounter.OnScorecard, GM_Grouping.?IsInGroup, GM_Lobby.?RequestTeamNames, GM_UI.Scorecard_LoadCharacterHeavyOnly, GM_UI.UIStateMachineEvent; props: Character_WallpaperImage | `8C` |
| ScorecardAccolades | wrapper.scorecard.ScorecardTabBase | - | `8C` `AD` |
| ScorecardRow | ui_sys.UIWidget_Base | listens: Contacts.UI_NotifyContactAdded, Contacts.UI_NotifyContactIgnored, Contacts.UI_NotifyContactUnignored; sends: GM_Chat.RunCmd, GM_Contacts.UI_InviteContact | `8C` |
| ScorecardScreen | wrapper.WrapperScreen | sends: GM_Encounter.OnScorecard | `8C` |
| ScorecardTabBase | ui_sys.UIWidget_Base | - | `8C` `9D` `AD` |
| ScorecardTabStats | wrapper.scorecard.ScorecardTabBase | - | `8C` `9D` |
| ScorecardTabStatsRow | gfx.core.UIComponent | - | `8C` `9D` |
| SummaryTab | wrapper.scorecard.ScorecardTabBase | - | `8C` |
| TeamContainer | ui_sys.UIWidget_Base | listens: Chat.UpdatedMemberList | `8C` |

#### `gameplay.wrapper.scorecard.accolades` - scorecard accolades tab widgets

| class | extends | role / C++ link | movies (DID low byte) |
|---|---|---|---|
| AccoladesChampionDisplay | ui_sys.UIWidget_Base | sends: EM_Sound.Play, GM_Character.?UI_RequestAspirationalTooltip | `AD` |
| AccoladesDisplay | ui_sys.UIWidget_Base | - | `AD` |
| AccoladesMapDisaply | ui_sys.UIWidget_Base | listens: Encounter.UI_LastMapPlayed; sends: EM_Sound.Play, GM_CustomMatch.?IsInCustomMatch, GM_Encounter.RequestLastMapPlayed, GM_Grouping.?IsInGroup | `AD` |
| AccoladesMeritDisplay | ui_sys.UIWidget_Base | sends: EM_Sound.Play | `AD` |
| AccoladesProtectorDisplay | ui_sys.UIWidget_Base | listens: Achievement.AchievementDetails; sends: EM_Sound.Play, GM_Achievement.RequestAchievementDetails | `AD` |

#### `gameplay.wrapper.stats` - account stats screen

| class | extends | role / C++ link | movies (DID low byte) |
|---|---|---|---|
| StatHeading | ui_sys.UIWidget_Base | - | `A3` |
| StatRow | ui_sys.UIWidget_Base | - | `A3` |
| StatRowData |  | - | `A3` |
| Stats | ui_sys.UIWidget_Base | listens: Character.SendAccountEncounterStats; sends: EM_Sound.Play, GM_Character.RequestAccountEncounterStats | `A3` |
| StatsComponent | wrapper.ScreenComponent | - | `A3` |
| StatsScreen | wrapper.WrapperScreen | - | `A3` |

#### `gameplay.wrapper.store` - store screen (CEF browser)

| class | extends | role / C++ link | movies (DID low byte) |
|---|---|---|---|
| LoadingClickBlocker | ui_sys.UIWidget_Base | - | `7C` `80` |
| Store | ui_sys.UIWidget_Base | listens: WebBrowser.OnJavaScriptCallback, WebBrowser.OnJavaScriptContextCreated, WebBrowser.OnLoadEnd, WebBrowser.OnLoadStart, WebTicket.UI_OnMicroTxnAuthorizationResponse, WebTicket.UI_OnWebTicketUpdated; sends: EM_WebTicket.UI_RequestWebTicket, GM_UI.UIStateMachineEvent, GM_UI.?InqStoreURL | `7C` |

#### `gfx.controls` - Scaleform CLIK controls

| class | extends | role / C++ link | movies (DID low byte) |
|---|---|---|---|
| Button | gfx.core.UIComponent | - | `59` `5E` `5F` `94` |
| ButtonBar | gfx.core.UIComponent | - | not linked; used by common.buttonBar.TurbineButtonBar |
| ButtonGroup | gfx.events.EventDispatcher | - | not linked; used by amplifiers.Assembler, artifactsFoundry.ArtifactFoundry, artifactsFoundry.FoundryTabPanel +8 |
| CoreList | gfx.core.UIComponent | - | not linked; used by gfx.controls.ScrollingList |
| DragTarget | gfx.core.UIComponent | - | not linked; used by artifacts.display.ArtifactActionButtonDragTarget |
| DropdownMenu | gfx.controls.Button | - | not linked; used by common.dropdown.BasicDropDownMenu |
| ListItemRenderer | gfx.controls.Button | - | not linked; used by common.dropdown.DropDownListItem |
| ScrollBar | gfx.controls.ScrollIndicator | - | `59` |
| ScrollIndicator | gfx.core.UIComponent | - | not linked; used by gfx.controls.ScrollBar |
| ScrollingList | gfx.controls.CoreList | - | `59` |
| Slider | gfx.core.UIComponent | - | `59` |
| ViewStack | gfx.core.UIComponent | - | `52` |

#### `gfx.core` - CLIK base component

| class | extends | role / C++ link | movies (DID low byte) |
|---|---|---|---|
| UIComponent | MovieClip | native: __handleEvent | `A5` |

#### `gfx.data` - CLIK data provider

| class | extends | role / C++ link | movies (DID low byte) |
|---|---|---|---|
| DataProvider | Array | - | not linked; used by gfx.controls.ButtonBar, gfx.controls.CoreList, gfx.controls.DropdownMenu |

#### `gfx.events` - CLIK event dispatcher

| class | extends | role / C++ link | movies (DID low byte) |
|---|---|---|---|
| EventDispatcher |  | - | not linked; used by artifacts.data.ArtifactDataManager, artifactsFoundry.FoundryManager, common.RolloverIconContainer +15 |
| EventTypes |  | - | not linked; used by accolades.AccoladeNavigator, amplifiers.Assembler, amplifiers.display.AmplifierListItem +173 |

#### `gfx.managers` - CLIK managers (focus, drag, popups, input)

| class | extends | role / C++ link | movies (DID low byte) |
|---|---|---|---|
| DragManager | gfx.events.EventDispatcher | - | not linked; used by artifacts.display.ArtifactsCollectionActionButtons, gfx.controls.DragTarget |
| FocusHandler |  | - | not linked; used by gfx.core.UIComponent |
| InputDelegate | gfx.events.EventDispatcher | - | not linked; used by gfx.managers.DragManager, gfx.managers.FocusHandler |
| PopUpManager |  | - | not linked; used by gfx.controls.DropdownMenu, gfx.managers.DragManager |

#### `gfx.ui` - CLIK input details / navigation codes

| class | extends | role / C++ link | movies (DID low byte) |
|---|---|---|---|
| InputDetails |  | - | not linked; used by gfx.managers.InputDelegate |
| NavigationCode |  | - | not linked; used by gfx.controls.Button, gfx.controls.ButtonBar, gfx.controls.DropdownMenu +4 |

#### `gfx.utils` - CLIK utils (Delegate, Locale, Constraints)

| class | extends | role / C++ link | movies (DID low byte) |
|---|---|---|---|
| Constraints |  | - | not linked; used by gfx.controls.Button, gfx.controls.ScrollBar, gfx.controls.Slider |
| Delegate | Object | - | not linked; used by gfx.managers.DragManager |
| Locale |  | - | not linked; used by gfx.controls.Button |

#### `input` - input maps (Turbine.Input.*) and text-mode focus

| class | extends | role / C++ link | movies (DID low byte) |
|---|---|---|---|
| InputMap |  | native: Input.AllocateInputMapHandle, Input.RegisterInputMap, Input.UnregisterInputMap | 27 movies |
| InputSystem |  | native: UIElement.KillFocus, UIElement.SetFocus, UIElement.SetTextMode | 16 movies |

#### `liquid` - liquid layout (anchored, resolution-independent positioning)

| class | extends | role / C++ link | movies (DID low byte) |
|---|---|---|---|
| ILiquidNode |  | - | not linked; used by liquid.LiquidNode |
| ILiquidRoot |  | - | not linked; used by liquid.LiquidRoot |
| LiquidAttachment |  | - | not linked; used by objectiveUpdates2.ObjectiveBannerDisplay, liquid.LiquidNode, liquid.LiquidRoot +1 |
| LiquidNode |  | - | not linked; used by liquid.LiquidRoot, ui_sys.UIWidget_Base, ui_sys.UIWidget_Browser +1 |
| LiquidPos |  | - | not linked; used by liquid.LiquidNode, liquid.LiquidRoot, ui_sys.UIWidgetManager +5 |
| LiquidRoot | liquid.LiquidNode | - | not linked; used by ui_sys.UIWidgetManager, ui_sys.UIWidget_ScrollView |

#### `system` - player / controlled agent IIDs and game clock from C++

| class | extends | role / C++ link | movies (DID low byte) |
|---|---|---|---|
| GameplaySystem |  | native: Player.GetIID, Timer.GetTime | 14 movies |
| gmGameplaySystem |  | native: Agent.GetControllingPlayerIID, Player.GetControlledAgentIID | 11 movies |

#### `template` - XML template loader for ui_sys widgets

| class | extends | role / C++ link | movies (DID low byte) |
|---|---|---|---|
| TemplateFileListLoader |  | - | not linked; used by template.TemplateRegistry |
| TemplateRegistry |  | - | not linked; used by ui_sys.UIWidget_Bar, ui_sys.UIWidget_Browser, ui_sys.UIWidget_Button +7 |
| XMLTemplateLoader |  | - | not linked; used by template.TemplateRegistry |

#### `ui_sys` - Turbine widget toolkit (lists, popups, scroll views, meters) and native-backed widgets (Browser, Chat, MovieTheatre, Viewport)

| class | extends | role / C++ link | movies (DID low byte) |
|---|---|---|---|
| IClickable |  | - | not linked; used by ui_sys.StandardPopupMenuItem, ui_sys.StandardPopupMenuProvider |
| IFocusDisplay |  | - | not linked; used by ui_sys.UIWidget_List |
| IGridListProvider |  | - | unused (nothing references it) |
| IInitializable |  | - | not linked; used by ui_sys.UIInitializer, ui_sys.UIInitializerRegistry, ui_sys.UIWidget_Base |
| IListItem |  | - | not linked; used by ui_sys.IStandardListItem, ui_sys.UIWidget_ComboBox, ui_sys.UIWidget_List |
| IListProvider |  | - | not linked; used by ui_sys.IPopupMenuProvider, ui_sys.StandardListProvider |
| IPopupMenuProvider |  | - | not linked; used by ui_sys.StandardPopupMenuProvider |
| ISelectable |  | - | not linked; used by ui_sys.StandardPopupMenuItem, ui_sys.UIWidget_GridList, ui_sys.UIWidget_List +1 |
| IStandardListItem |  | - | not linked; used by ui_sys.IStandardPopupMenuItem, ui_sys.StandardListProvider, ui_sys.StandardPopupMenuProvider |
| IStandardPopupMenuItem |  | - | not linked; used by ui_sys.StandardPopupMenuItem |
| StandardListProvider |  | - | not linked; used by ui_sys.UIWidget_GridList |
| StandardPopupMenuItem | ui_sys.UIWidget_Base | - | `00` |
| StandardPopupMenuProvider |  | - | unused (nothing references it) |
| TagRegistry |  | - | not linked; used by ui_sys.UIWidget_Text |
| UIInitializer |  | - | not linked; used by ui_sys.UIInitializerRegistry |
| UIInitializerRegistry |  | - | unused (nothing references it) |
| UIMsgRegistry |  | - | not linked; used by ui_sys.UIWidgetManager, ui_sys.UIWidget_Base |
| UIWidgetManager |  | listens: UI.ActionEnumEvent | not linked; used by ui_sys.UIWidget_Base, ui_sys.UIWidget_Button |
| UIWidget_Bar | ui_sys.UIWidget_Base | - | `00` |
| UIWidget_Base | MovieClip | - | 16 movies |
| UIWidget_Browser | ui_sys.UIWidget_Base | listens: UI.ForceOnSized; native: Browser.CanGoBack, Browser.CanGoForward, Browser.CreateDesc, Browser.DestroyDesc, Browser.ExecuteJavaScript, Browser.GetZoomLevel | `00` |
| UIWidget_Button | ui_sys.UIWidget_Text | - | `00` `59` |
| UIWidget_Chat | ui_sys.UIWidget_Base | listens: UI.ForceOnSized; native: UIL.CreateDesc, UIL.DestroyDesc, UIL.SetDescPos | `00` `52` |
| UIWidget_ComboBox | ui_sys.UIWidget_Base | - | `00` |
| UIWidget_GridList | ui_sys.UIWidget_ScrollView | - | `00` |
| UIWidget_Initializer | MovieClip | - | unused (nothing references it) |
| UIWidget_List | ui_sys.UIWidget_ScrollView | - | `00` |
| UIWidget_Meter | ui_sys.UIWidget_Base | - | `00` |
| UIWidget_MovieTheatre | ui_sys.UIWidget_Base | native: MovieTheatre.AudioOn, MovieTheatre.CreateDesc, MovieTheatre.DestroyDesc, MovieTheatre.Loop, MovieTheatre.Pause, MovieTheatre.VideoOn | `00` |
| UIWidget_PopupMenu | ui_sys.UIWidget_List | - | `00` |
| UIWidget_ScrollBar | ui_sys.UIWidget_Base | - | `00` `59` |
| UIWidget_ScrollView | ui_sys.UIWidget_Base | - | `00` |
| UIWidget_Text | ui_sys.UIWidget_Base | - | `00` |
| UIWidget_Viewport | ui_sys.UIWidget_Base | native: Viewport.CreateDesc, Viewport.DestroyDesc, Viewport.SetDescAllowVideoPost, Viewport.SetDescAmbientLight, Viewport.SetDescBackgroundMaterialDataID, Viewport.SetDescBloomCompensationAmount | unused (nothing references it) |

#### `utils` - helpers (icons by DID, IID utils, logging, string/team/perceived-type utils, tweening)

| class | extends | role / C++ link | movies (DID low byte) |
|---|---|---|---|
| ArrayUtils |  | - | unused (nothing references it) |
| CountdownTimer |  | listens: UI.TimerClockSync | not linked; used by announcements.AnnouncementsManager, billboard.BillboardManager, objectiveUpdates2.ObjectiveDisplay +3 |
| Debug |  | native: Debug.Assert | unused (nothing references it) |
| EntityPropertyObserver | ui_sys.UIWidget_Base | - | not linked; used by experience.ExperienceAward |
| IIDUtils |  | - | not linked; used by floaty.FloatyBase, announcements.AnnouncementsManager, artifacts.data.ArtifactBasicData +38 |
| Icon | ui_sys.UIWidget_Base | - | 45 movies |
| IconContainer | ui_sys.UIWidget_Base | - | 38 movies |
| Logger |  | - | not linked; used by mainhud.WidgetTarget, utils.CountdownTimer |
| MathUtils |  | - | not linked; used by billboard.TestButtonsBillboard, combometer.Combometer, defeat.TestButtonsDefeat +19 |
| NavigateInfo | Object | native: Browser.NavigateInfo_AddHeader, Browser.NavigateInfo_CreateDesc, Browser.NavigateInfo_DestroyDesc, Browser.NavigateInfo_SetPostData | not linked; used by amplifiers.Assembler, test.BrowserTest, wrapper.store.Store |
| PerceivedTypeUtils |  | - | not linked; used by floaty.FloatyVitalsManager, selectionpanel.SelectionPanel, vitals.VitalsLarge |
| RootFrameEvent |  | - | not linked; used by liquid.LiquidRoot, ui_sys.UIWidgetManager |
| StringUtils |  | - | not linked; used by dialogs.BrowserDialog, settings.GraphicsPaneContents, wrapper.store.Store +2 |
| TeamUtils |  | sends: GM_Options.?GetBoolOption, GM_Options.?GetUIntOption | not linked; used by billboard.BasicIconBillboard, billboard.BillboardManager, billboard.PlayerAnnounceBillboard +59 |
| UITweenUtils |  | - | not linked; used by experience.ExperienceBar, primitives.SimpleMeter |
| UIUtils |  | sends: GM_UI.LogError | not linked; used by accolades.Accolade, accolades.AccoladeButton, amplifiers.Assembler +276 |
| XMLUtils |  | - | not linked; used by template.XMLTemplateLoader |

#### `utils.animation` - animation clip pool

| class | extends | role / C++ link | movies (DID low byte) |
|---|---|---|---|
| AnimationClip | MovieClip | - | `07` |
| AnimationPool | ui_sys.UIWidget_Base | - | `07` |
| TestButtonsAnimationPool | MovieClip | - | `07` |
---

## 4. C++ -> Flash: every `RecvNotice_*` (315)

Per system (`GM_*` / `EM_*` class): notice name, id, arguments in order (prefix legend in 2.1), key (`0` = global,
`IID` = per entity, 2.2), the AS2 classes that listen, and the network source. Source column: a plain event id is a
server -> client event whose handler raises the notice (from the protocol notes; name match = [P], several generic
names over-match), `notice 0x1...` = a network notice sent inside event `0x2` with the same id (or the named one),
"layout match" = identified in this pass by argument layout [P], "local" = raised by the client itself. `-` = unknown
(most are client-local: skills, vitals, minimap, options, browser, selection). **none** in the listener column = dead
notice (nothing in Flash consumes it; the server need not send it for the UI).

#### `EM_SocialMedia` (1)

| notice | id | arguments | key | Flash listeners | network feeder |
|---|---|---|---|---|---|
| UI_OnSocialMediaURLUpdated | `0x0000008B` | strSocialMediaURL | 0 | BrowserSocialMedia, BrowserTest | - |

#### `EM_Sound` (1)

| notice | id | arguments | key | Flash listeners | network feeder |
|---|---|---|---|---|---|
| AudioQualityChanged | `0x000000C0` | - | 0 | AudioPane | - |

#### `EM_UI` (4)

| notice | id | arguments | key | Flash listeners | network feeder |
|---|---|---|---|---|---|
| ActionEnumEvent | `0x00000009` | actionClass, actionEnum, actionExtent, start, timeActionBegan, repeatDelta, repeatTotal | 0 | ArtifactFoundry, BootupInputHandler, BrowserSocialMedia, BrowserTest, CharacterBrowser, CustomMatchTeamDisplay, DisplayNameRequestScreen, HudMenuFullControl, InlineTextEditor, LaunchMoviePlayer, LobbyHeaderRight, LobbyWrapper, LoginScreen, MainHUD, MinimapMouseTarget, SkillsPanel, TestHUD, TextEntryDialog, UIWidgetManager, WrapperMain | - |
| ForceOnSized | `0x00000092` | - | 0 | UIWidget_Browser, UIWidget_Chat | - |
| GraphicsQualityChanged | `0x000000BF` | - | 0 | GraphicsPaneContents | - |
| Suppress_InputMap | `0x0000002E` | nInputMapTarget, bSuppressed | 0 | **none** | - |

#### `EM_WebBrowser` (14)

| notice | id | arguments | key | Flash listeners | network feeder |
|---|---|---|---|---|---|
| OnAddressChange | `0x00000057` | nHandle, strFrameName, strURL | 0 | BrowserTest | - |
| OnConsoleMessage | `0x0000005D` | nHandle, strMessage, strSource, nLine | 0 | BrowserSocialMedia, BrowserTest | - |
| OnJavaScriptAlert | `0x00000055` | nHandle, strFrameName, strMsg | 0 | BrowserSocialMedia, BrowserTest | - |
| OnJavaScriptCallback | `0x00000051` | nHandle, strCallbackName, astrArgs | 0 | BrowserDialog, BrowserSocialMedia, BrowserTest, Store | - |
| OnJavaScriptContextCreated | `0x00000050` | nHandle, strFrameName | 0 | BrowserDialog, BrowserSocialMedia, BrowserTest, Store | - |
| OnLoadEnd | `0x00000060` | nHandle, strFrameName, bIsMainFrame, strURL, bIsSecure, bHasCertError, bCertDisplayName, nHTTPStatusCode | 0 | BrowserDialog, BrowserSocialMedia, BrowserTest, Store | - |
| OnLoadStart | `0x0000005F` | nHandle, strFrameName, bIsMainFrame | 0 | BrowserDialog, BrowserTest, Store | - |
| OnNavStateChange | `0x00000056` | nHandle, bCanGoBack, bCanGoForward | 0 | BrowserTest | - |
| OnPopUpWindowRequested | `0x00000052` | nHandle, nX, nY, nWidth, nHeight, strURL | 0 | BrowserSocialMedia, BrowserTest | - |
| OnStatusMessage_KeyBoardFocusURL | `0x0000005C` | nHandle, strText | 0 | **none** | - |
| OnStatusMessage_MouseOverURL | `0x0000005B` | nHandle, strText | 0 | **none** | - |
| OnStatusMessage_Text | `0x0000005A` | nHandle, strText | 0 | **none** | - |
| OnTitleChange | `0x00000058` | nHandle, strTitle | 0 | BrowserSocialMedia, BrowserTest | - |
| OnTooltip | `0x00000059` | nHandle, strText | 0 | **none** | - |

#### `EM_WebTicket` (2)

| notice | id | arguments | key | Flash listeners | network feeder |
|---|---|---|---|---|---|
| UI_OnMicroTxnAuthorizationResponse | `0x000000C1` | strOrderID, bAuthorized | 0 | Store | - |
| UI_OnWebTicketUpdated | `0x00000064` | strWebTicket, shardId | 0 | Assembler, Store | - |

#### `GM_Achievement` (6)

| notice | id | arguments | key | Flash listeners | network feeder |
|---|---|---|---|---|---|
| AchievementDetails | `0x10000416` | didAchievement, siName, siDescription, didIcon, uOverallProgress, uPreviousProgress, siOverallProgressString, asiObjectiveNames, asiObjectiveDescriptions, asiObjectiveProgressStrings, adidObjectiveIcons, aPreviousProgresses, aCurrentProgressArray, aRewardBestowalTypes, aRewardTypes, didRewardIcon, aRewardQuantities, aRewardNames | 0 | AccoladesProtectorDisplay, Achievements, NewPlayerScreen, NextChallenge, TraineeAchievements, VeteranAchievement | - |
| AllPendingAchivementBanners | `0x10000415` | adidAchievementID | 0 | WrapperMain | `0x211f` |
| SetAchievementData | `0x1000045B` | didAchievement, siAchievementName, siAchievementDescription, didAchievementIcon, didPromotionImage, didPromotionImage2, bIsFeatured, eCategoryType, eVisiblityType, eRepeatType, eAchievementObjectiveType, uObjectiveTotalCount, aeRewardBestowalType, aeRewardTypes, didRewardIcon, aRewardNames | 0 | AchievementsManager | `local: built from achievement records after 0x2120 (guess)` |
| SetAchievementObjectiveData | `0x10000459` | didAchievement, uOverallProgress, uPreviousProgress, bHasProgress, siTimeValid, bTimeInFuture, siTimesCompleted, aObjectiveProgess, uLastUpdatedInUnixSeconds | 0 | AchievementsManager | `0x2120` `0x21a6` |
| SetDeprecatedAchievements | `0x100004E7` | aDeprecatedAchievements | 0 | AchievementsManager | `0x2120` `0x21a6` |
| TraineeAchievements | `0x10000497` | aAchievements, aTurntableMovies, aClickAction_Queue, aClickAction_UITransition, nNumStepsOnRails | 0 | AchievementsManager, PVPLauncher | - |

#### `GM_AdminAlert` (1)

| notice | id | arguments | key | Flash listeners | network feeder |
|---|---|---|---|---|---|
| UI_NotifyAdminAlertsUpdated | `0x10000457` | aAlertTitles, aAlertMessages, aAlertLinks | 0 | HeaderCenter | - |

#### `GM_Advancement` (2)

| notice | id | arguments | key | Flash listeners | network feeder |
|---|---|---|---|---|---|
| SkillRanked | `0x10000054` | iidAgent, eSkill, iRank, eError | 0 | AnnouncementsManager, DefeatRecommendationsPanel, FoundryManager, SkillsPanel | - |
| XPGained | `0x100004F9` | iid, nXPGained | IID | OverheadVitalsDeluxe | - |

#### `GM_Amplifier` (4)

| notice | id | arguments | key | Flash listeners | network feeder |
|---|---|---|---|---|---|
| NotifyAmplifierSet | `0x100003C3` | uiAmplifierSlotID, didCharacterReference, strAmplifierNames, didIcon, didEntryOne, didEntryTwo, didEntryThree, didEntryFour, didEntryFive, didEntrySix, didEntrySeven | 0 | AmplifierSetManager | `0x20c7` |
| NotifyAmplifierSetError | `0x100003BE` | eContactError | 0 | **none** | `0x2052` |
| NotifyContextualAmplifierData | `0x100003F9` | aBoutiqueIDs, aAmplifierDIDs, aCurrencyNames, aCurrencyValues | 0 | BoutiqueDataManager | `0x2107` |
| NotifyListAmplifierSets | `0x100003BD` | uiTotalAmplfierSets, uiMaxAmplifierSets, aAmplifierSlotID, aCharacterReference, aAmplifierNames, aIcons, aEntryOne, aEntryTwo, aEntryThree, aEntryFour, aEntryFive, aEntrySix, aEntrySeven | 0 | AmplifierSetManager | `0x2090` |

#### `GM_Camera` (2)

| notice | id | arguments | key | Flash listeners | network feeder |
|---|---|---|---|---|---|
| CameraLocked | `0x10000175` | bIsLocked | 0 | **none** | - |
| CameraLockedPreference | `0x10000228` | bIsLocked | 0 | GameplayPane | - |

#### `GM_Character` (26)

| notice | id | arguments | key | Flash listeners | network feeder |
|---|---|---|---|---|---|
| ActiveAgentControlledByThePlayerChanged | `0x100001DF` | iid, iidOldAgent, iidNewAgent | IID | ControlledAgentDispatcher | - |
| AgentControlledByThePlayerChanged | `0x10000080` | iid, iidOldAgent, iidNewAgent | IID | AnnouncementsManager, ControlledAgentDispatcher, ExperienceAward | - |
| ClearAnnouncement | `0x100002EC` | iid | IID | BillboardManager | `notice 0x100002ec` |
| HideKillCard | `0x100002B3` | - | 0 | DefeatManager | - |
| MasterCharacterListReceived | `0x1000007F` | - | 0 | BootupInputHandler | `0x20ed` |
| NotifyPlayerDied | `0x10000127` | iid, iidVictim, didVictimIcon, iVictimTeam, iidKiller, iKillerTeam, aKillerAndAssists | IID | KillDisplayManager | - |
| RewardSetsData | `0x10000402` | aRewardSetDIDs, aRewardSourceDIDs, aUseAdvancedBanners, aRewardSourceTypes, aRewardSourceNames, aRewardBestowalTypes, aRewardItemDIDs, aRewardItemTypes, aRewardItemQuantities, aRewardIcons, aRewardNames | 0 | WrapperMain | `0x2125` `0x2197` |
| Ribbon_CharacterLevelChanged | `0x10000253` | didCharacterIcon, siCharacterName, previousLevel, currentLevel, totalXP, percentToNextLevel, nextLevelXP, didCharacter | 0 | WrapperMain | `0x2104` |
| Ribbon_FinishedItemsFulfilled | `0x100003D3` | - | 0 | WrapperMain | `0x2095` |
| Ribbon_ItemFulfilled | `0x100002E0` | didIcon, siName | 0 | WrapperMain | `0x2095` |
| SendAccountCharacterLevelAndXP | `0x100003A1` | didCharIcon, siCharName, characterLevel, totalXP, percentToNextLevel | 0 | **none** | - |
| SendAccountCurrencyBalance | `0x1000028A` | hardCurrency, softCurrency | 0 | HeaderLeft, ScorecardManager, WrapperMain | `0x2081` |
| SendAccountCurrencyBalanceChanges | `0x10000291` | hardCurrency, softCurrency | 0 | **none** | `0x20b9` |
| SendAccountEncounterStats | `0x10000419` | adidEncounters, aRanked, asiStatLables, asiStatValues | 0 | Stats | `0x2115` |
| SendAccountEndOfMatchAccoladesEarned | `0x100004E4` | didEncounter, bRanked, didChampion, asiAccoladeNames, asiAccoladeDescriptions, asiAccoladeSummaries, adidAccoladeIcons, aAccoladeMedalTypes, aIsAllTimeBest | 0 | AccoladeManager, ScorecardManager | `0x2104` `0x2188` |
| SendAccountEndOfMatchCharacterLevelAndXP | `0x100003EE` | didCharacter, didCharIcon, siCharName, characterLevel, prevCharacterLevel, xpTotal, xpToNextLevel, xpEarned, xpBonus, percentToNextLevel, prevPercentToNextLevel | 0 | ScorecardManager | `0x2104` |
| SendAccountEndOfMatchLevelAndXP | `0x100003F0` | accountLevel, prevAccountLevel, xpToNextLevel, xpTotal, xpEarned, xpBonus, percentToNextLevel, prevPercentToNextLevel | 0 | ScorecardManager | `0x2080` |
| SendAccountEndOfMatchSoftCurrencyReward | `0x100003ED` | uBaseReward, uDailyReward, fTimeTillNextDailyBonus, uStreakReward, uPotentialDailyReward, uPotentialStreakReward, siStreakBonusTooltipMsg, siQueueBonusTooltipMsg | 0 | ScorecardManager | `0x20b9` |
| SendAccountLevelAndXP | `0x10000262` | accountLevel, totalXP, percentToNextLevel, xpToNextLevel | 0 | CallingCardDialog, WrapperMain | `0x2080` |
| SendBestChampAccolades | `0x100004EF` | aAccolades, aIcons, aChampions, bRanked, asiAccoladeNames, asiAccoladeDescriptions, asiAccoladeSummaries | 0 | AccoladeManager | `0x2186` |
| SendBestMapAccolades | `0x100004EE` | aAccolades, aIcons, aChampions, aMaps, aRanked, asiAccoladeNames, asiAccoladeDescriptions, asiAccoladeSummaries | 0 | AccoladeManager | `0x2186` |
| ShowAnnouncement | `0x100002EB` | iid, siAnnouncement, eBillboardType, didSourceIcon, didTargetIcon, iSourceTeam, iTargetTeam, bUseTargetTeamColor | IID | BillboardManager | `notice 0x100002eb` |
| StopProcessingNewBillboards | `0x100002BC` | iid | IID | BillboardManager, MainHUD | `notice 0x100002bc` |
| UI_ShowKillCard | `0x10000222` | aAttackerIIDs, aAttackerIconDID, siKillerNameOverride, aTotalDamage, aSkillSlot1Damage, aSkillSlot2Damage, aSkillSlot3Damage, aSkillSlot4Damage, aSkillSlot1SlotType, aSkillSlot2SlotType, aSkillSlot3SlotType, aSkillSlot4SlotType, aSkillSlot1DamageType, aSkillSlot2DamageType, aSkillSlot3DamageType, aSkillSlot4DamageType, aSkillSlot1IconDID, aSkillSlot2IconDID, aSkillSlot3IconDID, aSkillSlot4IconDID, aSkillSlot1SourceArtifactDID, aSkillSlot2SourceArtifactDID, aSkillSlot3SourceArtifactDID, aSkillSlot4SourceArtifactDID, aSkillSlot1SourceModDID, aSkillSlot2SourceModDID, aSkillSlot3SourceModDID, aSkillSlot4SourceModDID, aSlot1NameOverride, aSlot2NameOverride, aSlot3NameOverride, aSlot4NameOverride, aSlot1TooltipOverride, aSlot2TooltipOverride, aSlot3TooltipOverride, aSlot4TooltipOverride, aDamageTypeTotals, aDamageTypePercentages, aTeamInts | 0 | DefeatManager | - |
| UpdateCharacterPanelInfo | `0x100001F4` | iid, identifiers, values, aValuePrecisions, tooltips | IID | ControlledAgentDispatcher, SelectionPanel | - |
| UpdateRegenValues | `0x10000232` | iid, healthRegenValue, secondaryRegenValue | IID | VitalsLarge | - |

#### `GM_Chat` (3)

| notice | id | arguments | key | Flash listeners | network feeder |
|---|---|---|---|---|---|
| ToggleUnreadChat | `0x100003DF` | bShowUnreadChat | 0 | ChatLauncher | `0x20b0` `0x20b6` |
| UI_ShowWrapperGeneralChatWindow | `0x10000451` | - | 0 | ChatManager | - |
| UpdatedMemberList | `0x1000043E` | siRoomName, aMembers | 0 | TeamContainer | `0x2135` |

#### `GM_ConnectionManager` (2)

| notice | id | arguments | key | Flash listeners | network feeder |
|---|---|---|---|---|---|
| ShowLoginError | `0x10000225` | sErrorString | 0 | LoginScreen | - |
| UpdateConnectionState | `0x10000159` | nIndex | 0 | ConnectingScreen | `0x2024` `0x20ed` `0x20ff` |

#### `GM_Contacts` (19)

| notice | id | arguments | key | Flash listeners | network feeder |
|---|---|---|---|---|---|
| UI_ContactListNotification | `0x1000036A` | eContactError | 0 | ContactsComponent | `0x2065` |
| UI_NotifyContactAccountIconChanged | `0x10000350` | aContactIIDs, aIcons1, aIcons2, aIcons3, aIcons4, aIcons5 | 0 | ContactsManager | `0x20ec` |
| UI_NotifyContactAdded | `0x1000031D` | iidContact, strSteamName, strContactName, iGroupID, strGroupName, strNote, eContactType, didIcon1, didIcon2, didIcon3, didIcon4, didIcon5, uiLevel, strStatusMessage, ePresence | 0 | ContactsManager, CustomMatchInterface, PVPGroupingInterface, ScorecardRow | `0x2051` `0x20cc` |
| UI_NotifyContactChangeNote | `0x10000322` | iidContact, strNote | 0 | ContactsManager | `0x208f` |
| UI_NotifyContactChangeStatusMessage | `0x10000337` | iidContact, strStatusMessage | 0 | ContactsManager | `0x20c5` |
| UI_NotifyContactChangeSteamName | `0x10000510` | iidContact, strSteamName | 0 | ContactsManager | - |
| UI_NotifyContactChangedGroup | `0x1000031E` | iidContact, strGroupID | 0 | ContactsManager | `0x20cb` |
| UI_NotifyContactGroupCreated | `0x10000320` | strGroupID, strGroupName, siMoveToGroup | 0 | ContactsManager | `0x2014` |
| UI_NotifyContactGroupDestroyed | `0x10000324` | strGroupID | 0 | ContactsManager | `0x205e` |
| UI_NotifyContactIgnored | `0x1000031C` | iidContact | 0 | ContactsManager, ScorecardRow | `0x2051` |
| UI_NotifyContactList | `0x10000323` | aContactIIDs, aSteamNames, aContactNames, aGroupIDs, aGroupNames, aContactNotes, aContactType, aIcons1, aIcons2, aIcons3, aIcons4, aIcons5, aLevels, aStatusMessage, aPresence, aAllGroupIDs, aAllGroupNames, aAllMoveToGroupStrings | 0 | ContactsManager | `0x203b (layout, probable)` |
| UI_NotifyContactOfInvitations | `0x10000515` | strMessage | 0 | ContactsComponent | `0x219c` |
| UI_NotifyContactOfInvite | `0x1000031B` | iidContact, strContactSteamName, strContactName | 0 | ContactsComponent | `0x2003` |
| UI_NotifyContactOfPendingInvites | `0x10000361` | aContactIIDs, aContactSteamNames, aContactNames | 0 | ContactsComponent | `0x2013` |
| UI_NotifyContactPresenceChanged | `0x10000326` | aContactIIDs, aSteamNames, aPresence | 0 | ContactsManager | `0x2018` `0x20ae` |
| UI_NotifyContactRemoved | `0x1000031F` | iidContact | 0 | ContactsManager | `0x2020` `0x2051` `0x20cc` |
| UI_NotifyContactUnignored | `0x10000321` | iidContact | 0 | ContactsManager, ScorecardRow | `0x204f` `0x20cc` |
| UI_NotifySelfChangedPresence | `0x10000339` | ePresence | 0 | SelfPresenceDisplay | `0x203a` |
| UI_NotifySelfChangedStatusMessage | `0x10000338` | strStatusMessage | 0 | SelfPresenceDisplay | `0x2058` |

#### `GM_Contextual` (3)

| notice | id | arguments | key | Flash listeners | network feeder |
|---|---|---|---|---|---|
| PurchaseContextualItemError | `0x1000040B` | strBoutiqueID, eError | 0 | Assembler | `0x210d` |
| PurchaseContextualItemSuccess | `0x1000040A` | strBoutiqueID | 0 | Assembler | `0x210c` |
| PurchasePriceChanged | `0x10000410` | strBoutiqueID, didItem, strCurrencyName, uiIntialPrice, strOrderID, uiFinalPrice | 0 | **none** | `0x210f` |

#### `GM_CustomMatch` (19)

| notice | id | arguments | key | Flash listeners | network feeder |
|---|---|---|---|---|---|
| UI_CustomMatch_AddedParticipant | `0x1000039A` | iidAccount, strName, nLevel, didIcon, ePerm, bIsFriend | 0 | **none** | `0x2012` |
| UI_CustomMatch_AssignedTeam | `0x10000394` | iidAccount, nTeam | 0 | **none** | `0x2076` |
| UI_CustomMatch_Cancelled | `0x1000038C` | - | 0 | CustomMatchInterface, WrapperMain | `0x2011` |
| UI_CustomMatch_ChangedCoordinator | `0x10000397` | iidOld, iidNew | 0 | **none** | `0x2036` |
| UI_CustomMatch_CreationFailed | `0x10000391` | siReason | 0 | **none** | `0x2042` |
| UI_CustomMatch_InvitationStatus | `0x10000396` | strName, eStatus, bIsFriend | 0 | **none** | `0x202e` |
| UI_CustomMatch_InviteCancelled | `0x1000039E` | idCustomMatch | 0 | ContactsComponent | `0x2027` |
| UI_CustomMatch_Invited | `0x10000399` | siMsg, idCustomMatch | 0 | ContactsComponent | `0x201f` |
| UI_CustomMatch_Kicked | `0x1000039F` | idCustomMatch | 0 | CustomMatchInterface, WrapperMain | `0x2041` |
| UI_CustomMatch_Launched | `0x10000393` | - | 0 | CustomMatchInterface | `0x2040` |
| UI_CustomMatch_Left | `0x1000046B` | idCustomMatch | 0 | CustomMatchInterface, WrapperMain | `0x203f` |
| UI_CustomMatch_MovedPosition | `0x1000039B` | iidAccount, nDirection | 0 | **none** | `0x2048` |
| UI_CustomMatch_PermissionChanged | `0x10000398` | iidAccount, ePerm, bGrant | 0 | **none** | `0x2035` |
| UI_CustomMatch_RemovedParticipant | `0x10000395` | iidAccount | 0 | **none** | `0x205d` |
| UI_CustomMatch_SetDraftMode | `0x100003E9` | bEnable | 0 | CustomMatchManager | `0x2103` |
| UI_CustomMatch_SetEncounter | `0x100003FE` | didEncounter | 0 | CustomMatchManager | `0x2109` |
| UI_CustomMatch_SetTeamName | `0x10000484` | nTeam, siTeamLongName, siTeamShortName | 0 | CustomMatchManager | `0x2151` |
| UI_CustomMatch_UpdateProtectorIcon | `0x100004DD` | iidAccount, didIcon | 0 | CustomMatchManager | `0x217c` |
| UI_DeliverCustomMatchData | `0x10000389` | iidCoordinator, iidMe, bIsAdmin, didEncounter, bDraftLobby, eMatchPerm, aAccountIIDs, aNames, aLevels, aIcons, aPermissions, aTeams, aEligibleForDraftMode, aParticipantAreFriends, aInviteNames, aInviteAreFriends, aInviteStatus, siDraftErrorGeneral, siDraftErrorPlayer, nRequiredPlayers, siNotEnoughPlayersError | 0 | CustomMatchManager | `client cache of the room (0x2012 0x2035 0x2036 0x2048 0x205d 0x2076 have no Flash listener of their own; probable)` |

#### `GM_Dialog` (4)

| notice | id | arguments | key | Flash listeners | network feeder |
|---|---|---|---|---|---|
| HideAllConversationSlots | `0x1000044C` | bNoDelay | 0 | ConversationManager | `0x2001 (C++ conversation player)` |
| HideConversationSlot | `0x10000449` | iSlot, bNoDelay | 0 | ConversationManager | `0x2001 (C++ conversation player)` |
| HighlightConversationAdvanceButton | `0x10000448` | - | 0 | ConversationManager | - |
| ShowConversationSlot | `0x1000044B` | iSlot, didImage, siMovieFileName, siName, siText, bNoDelay, bCannotSkip | 0 | ConversationManager | `0x2001 (conversation; C++ drives the slots)` |

#### `GM_Encounter` (45)

| notice | id | arguments | key | Flash listeners | network feeder |
|---|---|---|---|---|---|
| AddParticipant | `0x1000001E` | iidPlayer, iidAgent, didAgent, nTeam, siName, bIsIgnored, didPortraitIcon, didBillboardIcon, siCharacterName, asiRoleNames, asiRoleDescriptions, adidRoleIcons, siDescription, uiAmplifierSetSlot, didAmplifierSetIcon, strAmplifierSetName, aAmplifierSetModifiers | 0 | MatchData | `local: raised when player/agent objects are created (probable)` |
| MasterEncounterListReceived | `0x100000A9` | - | 0 | **none** | `0x2024` `0x20ff` |
| NotifyMatchEnded | `0x1000000E` | iid, uWinningTeam, uPlayerTeam, fMatchDuration, nTier, fTargetTime | IID | MainHUD, MatchManager, ViewMatchTop | `notice 0x1000000e` |
| PlayEndOfMatchEncounterMovie | `0x100004A7` | strMovie | 0 | Scorecard | `0x2045` |
| RemoveParticipant | `0x10000006` | iidAgent, nTeam, siName, didIcon | 0 | MatchData | `local: object destroyed (probable)` |
| ResetMapSelectionList | `0x100003DA` | - | 0 | EncounterManager | `0x2024` `0x20ff` |
| SetMatchTime | `0x10000109` | iid, ttMatchStartTime, ttMatchEndTime, bIsPreStartTime | IID | MatchManager, ViewMatchTop | `notice 0x10000109` |
| SurrenderVoteConcluded | `0x10000456` | iid | IID | SurrenderPanel | `notice 0x10000456` |
| UI_AddObjective | `0x100000BE` | eID, siText, didIcon, eCategory, nSortOrder, bOptional, eState, nDuration, bCountDown, nCount, nMaxCount, fProgressPercent, eTeamRelationship, siBannerText | 0 | AnnouncementsManager, ObjectiveUpdates2 | - |
| UI_BatchUpdateTrackerStatus | `0x10000380` | aIIDs, aCurrentTeams, aContentionResponsibleTeams, aLockedToTeams, aIcons, hudPositions, mapnoteCategorys, obscured, bTeamBackground | 0 | MinimappyThing, SectorObjectiveTracker | - |
| UI_CompletedEncounters | `0x10000472` | aCompletedEncounters | 0 | **none** | `0x214b` |
| UI_DeliverCurrentObjectives | `0x1000019A` | aIDs, aText, aIcons, eCategories, nSortOrders, bOptionals, aStates, aDurations, aCountDowns, aCounts, aMaxCounts, aProgressPercents, aTeamRelationships, aBannerText | 0 | ObjectiveUpdates2 | - |
| UI_DeliverObjectiveCategories | `0x1000019C` | aCategories, aTitles, aDescriptions, aSortOrders, aStates, aVisibility | 0 | ObjectiveUpdates2 | `0x2034` |
| UI_InitialTeamHealthUpdate | `0x100004FB` | iid, aTeams, aTeamStartingHealthValues, aTeamHealthValues | IID | TeamHealthDisplay | `notice 0x100004fb` |
| UI_LastMapPlayed | `0x100004C0` | didLastEncounter, bIsRanked, bIsDraft | 0 | AccoladesMapDisaply, VeteranMap | `0x214b` |
| UI_MissionEvent_AddTimelineBanner | `0x10000422` | iidAgent, nHandleID, eSeverity, siMessage, ttCountdown, ttCurrentTime | 0 | EventTimerV2 | - |
| UI_MissionEvent_AddTimelineEvent | `0x100002A5` | iidAgent, nHandleID, eSeverity, didTimelineIcon, didExaminationIcon, bTintTimelineIcon, iOwningTeam, siTitle, siDescription, ttEventTime, ttCurrentTime | 0 | EventTimerV2 | - |
| UI_MissionEvent_BatchAddTimelineEvent | `0x100002A6` | aAgentIIDs, aHandleIDs, aSeverities, aTimelineIconDIDs, aExaminationIconDIDs, aTintTeamIcons, aOwningTeams, aTitles, aDescriptions, aEventTimes, ttCurrentTime | 0 | EventTimerV2 | - |
| UI_MissionEvent_RemoveTimelineBanner | `0x10000421` | iidAgent, nHandleID | 0 | EventTimerV2 | - |
| UI_MissionEvent_RemoveTimelineEvent | `0x100002A7` | iidAgent, nHandleID | 0 | EventTimerV2 | - |
| UI_MissionEvent_StartTimeline | `0x100002A8` | ttCurrentTime | 0 | EventTimerV2 | - |
| UI_PlayerJoined | `0x100000CB` | iid, iidPlayer, iidAgent, siName, didIcon, nTeam | IID | BillboardManager | `notice 0x100000cb` |
| UI_PlayerLeft | `0x100000CE` | iid, iidPlayer, iidAgent, siName, didIcon, nTeam | IID | BillboardManager | `notice 0x100000ce` |
| UI_RemoveObjective | `0x100000B0` | eID | 0 | ObjectiveUpdates2 | - |
| UI_RemoveObjectiveCategory | `0x10000196` | eCategory | 0 | ObjectiveUpdates2 | `0x2023` |
| UI_SendEndOfMatchStats | `0x10000366` | aAccountIIDs, aPlayerIIDs, aIconDIDs, aNames, aChampLevels, aIsBot, aIsFriend, aIsIgnored, aLevels, aTeams, aPlayerKills, aDeaths, aAssists, aCurrency, aCoinPickups, aAmplifiers, aColumn1, aColumn2, aColumn3, aColumn4, aColumn5, aScorecardGridLabels, aIsScorecardGridLabelASectionLabel, aScorecardGridLabelTooltips, aScorecardGridValuesPlayer1, aScorecardGridValuesPlayer2, aScorecardGridValuesPlayer3, aScorecardGridValuesPlayer4, aScorecardGridValuesPlayer5, aScorecardGridValuesPlayer6, aScorecardGridValuesPlayer7, aScorecardGridValuesPlayer8, aScorecardGridValuesPlayer9, aScorecardGridValuesPlayer10, aScorecardGridSumsTeam1, aScorecardGridSumsTeam2, iidYourIID, uYourTeam, fDuration, iWinningTeam, didEncounter, bIsRanked | 0 | ScorecardManager | `0x2045 (progression-meta)` |
| UI_SetEndOfMatchStatsHeader | `0x10000387` | aIconDIDs, aTooltips | 0 | ScorecardManager | `0x2028` `0x2045` |
| UI_SetObjectiveTrackerEnabled | `0x1000019D` | bEnabled | 0 | ObjectiveUpdates2 | `0x2034` `0x2075` |
| UI_UpdateHasBaseAccess | `0x100003FC` | bHasBaseAccess | 0 | DefeatManager, SkillsPanel | - |
| UI_UpdateHasVendorAccess | `0x100002FA` | bHasVendorAccess | 0 | DefeatManager, FoundryManager, UpgradeCurrencyDisplay | - |
| UI_UpdateMatchScorecard | `0x1000007E` | aIIDs, aPlayerIIDs, aDIDs, aNames, aIsBot, aIsIgnored, aLevels, aTeams, aPlayerKills, aDeaths, aAssists, aMoneyEarned, iidYourIID, uYourTeam | 0 | MatchData | - |
| UI_UpdateObjectiveCategory_State | `0x10000195` | eCategory, eState | 0 | ObjectiveUpdates2 | `0x2023` |
| UI_UpdateObjective_BannerText | `0x100004A3` | eID, siBannerText | 0 | ObjectiveUpdates2 | - |
| UI_UpdateObjective_Count | `0x100000BF` | eID, nCount | 0 | ObjectiveUpdates2 | `0x2009` |
| UI_UpdateObjective_CountDown | `0x100000B5` | eID, bCountDown | 0 | ObjectiveUpdates2 | - |
| UI_UpdateObjective_CountMax | `0x100000B9` | eID, nCountMax | 0 | ObjectiveUpdates2 | `0x2009` |
| UI_UpdateObjective_ProgressPercent | `0x100000BD` | eID, fPercent | 0 | ObjectiveUpdates2 | - |
| UI_UpdateObjective_State | `0x100000AE` | eID, eState | 0 | ObjectiveUpdates2 | `0x2009` |
| UI_UpdateObjective_TeamRelationship | `0x1000018D` | eID, eTeamOwner | 0 | ObjectiveUpdates2 | - |
| UI_UpdateObjective_Text | `0x100000AB` | eID, siText | 0 | ObjectiveUpdates2 | - |
| UI_UpdateObjective_TimerDuration | `0x100000B4` | eID, nDuration | 0 | ObjectiveUpdates2 | - |
| UI_UpdateObjectivesForScorecard | `0x100000C1` | aOptionalsText | 0 | **none** | - |
| UI_UpdateTeamHealth | `0x10000134` | iid, aTeams, aTeamHealthValues | IID | TeamHealthDisplay | `notice 0x10000134` |
| UI_UpdateTrackerStatus | `0x1000037E` | iidEntity, iCurrentTeam, iContentionResponsibleTeam, eLockedToTeam, didIcon, hudPosition, mapnoteCategory, mapnoteDecoration, obscured | 0 | MinimappyThing, SectorObjectiveTracker | `0x2069` |
| UpdateSurrenderData | `0x10000455` | iid, aVotes, nNumExpectedVotes, bCanVote, fTimeRemaining, fTotalTime | IID | SurrenderPanel | `notice 0x10000455` |

#### `GM_Grouping` (5)

| notice | id | arguments | key | Flash listeners | network feeder |
|---|---|---|---|---|---|
| GroupInformation | `0x10000286` | siGroupName, iidLeader, iidMe, didEncounter, bAllCanInvite, aAccountIIDs, aNames, aLevels, aIcons, aCanInvite, aEligibleForDraftMode, aParticipantAreFriends, aInviteNames, aInviteAreFriends, aInviteStatus | 0 | PVPGroupManager | `0x2071 (layout, probable)` |
| GroupInviteCanceled | `0x10000478` | - | 0 | ContactsComponent | `0x214c` |
| PlayerLeftGroup | `0x10000444` | - | 0 | PVPGroupManager, WrapperMain | `0x2071` |
| ShowGroupInviteDialog | `0x1000028D` | siMsg | 0 | ContactsComponent | `0x2033` |
| UI_Grouping_UpdateProtectorIcon | `0x100004DF` | iidAccount, didIcon | 0 | PVPGroupManager | `0x217d` |

#### `GM_KeyBinding` (2)

| notice | id | arguments | key | Flash listeners | network feeder |
|---|---|---|---|---|---|
| UI_KeyBindingData | `0x100003C9` | aKeyBindIndices, aActionNames, aInputActions, aInputMaps, aInputNames | 0 | KeybindingPane, SettingsManager | - |
| UI_UpdateKeyBinding | `0x100003C7` | iKeyBindIndex, siActionName, eInputAction, eInputMap, strInputName, iKeyUnbindIndex | 0 | KeybindingPane, SettingsManager | - |

#### `GM_Lobby` (25)

| notice | id | arguments | key | Flash listeners | network feeder |
|---|---|---|---|---|---|
| CharacterLockFail | `0x100001D0` | - | 0 | **none** | `0x2005` |
| CharacterPurchased | `0x10000201` | didCharacter, nCost | 0 | **none** | - |
| CharacterVariantsLoaded | `0x10000200` | aSkinUIRequestedDIDs, aPregameIDsArray | 0 | SkinPicker | `local: after the costume packs load` |
| ClearHeavyResourcePackReferences | `0x100001EA` | - | 0 | CharacterPreview | `0x204b` `0x206c` |
| ClearLightResourcePackReferences | `0x100001E9` | didsComingIn | 0 | BillboardManager, MatchManager, PvPLobby, SkinPicker | `0x2021` `0x2028` `0x204b` `0x206c` |
| Draft_Banning | `0x100002F5` | nTeam, aBannedCharacters, aBannedIcons, nTimer | 0 | LobbyTeamDisplay, PvPLobby | - |
| Draft_EnableTrade | `0x100002FF` | nTeam | 0 | LobbyTeamDisplay | - |
| Draft_PlayersTrading | `0x10000301` | aPlayersTrading | 0 | LobbyPlayerDisplay | - |
| Draft_Selecting | `0x100002F4` | nTeam, nSlot, nTimer, bIsMe | 0 | CharacterPicker, LobbyTeamDisplay | - |
| Draft_TradeRequest | `0x100002FC` | siText | 0 | PvPLobby | `0x2054` |
| HeavyResourcePackLoaded | `0x100001DE` | didHeavy, didPowerSet, didLight | 0 | CharacterPreview | `local: after the heavy pack loads` |
| HideBackButton | `0x10000224` | - | 0 | LobbyHeaderRight | `0x2016` `0x206d` |
| LobbyEncounterDetails | `0x100001C6` | uNumTeams, uNumPlayersPerTeam, didEncounterDID, bDraftMode, bRankedMode, bCustomMatch, iidMyPlayer, uMyTeamNumber, bRunAsAdmin, mapName, nRequiredPlayers, bIsTutorial, bSkipsLobby, bIsRejoin, eType, bDiamondMinimap | 0 | LobbyHeaderCenter, PvPLobby | `0x204c` |
| LobbyRejoinRoom | `0x1000024D` | - | 0 | WrapperMain | `0x205b` |
| LobbyRoomCreated | `0x1000024B` | - | 0 | MatchFoundRibbon | `0x2028` |
| MatchLaunchWarning | `0x100001D1` | ttMatchLaunchTimeStart, ttMatchLaunchTimeEnd | 0 | LobbyHeaderRight, PvPLobby | `0x204b` |
| PlayerPickedAmplifierSet | `0x1000038D` | nTeam, nTeamIdx, iidPlayerID, uiAmplifierSetSlot, didAmplifierSetIcon, strAmplifierSetName, aAmplifierSet, bMyAmplifierSet | 0 | AmplifierSetPicker, PvPLobby | `0x2029` `0x204a` `0x2060` |
| PlayerPickedStolenPowers | `0x100001FA` | nTeam, nTeamIdx, iidPlayerID, didStolenPowerOne, didStolenPowerTwo, bIsMyStolenPowers | 0 | PvPLobby, SecondaryPowerDisplay | `0x2004` `0x2029` `0x2060` |
| PlayerSelectedEarlyLaunchFromServer | `0x100001D2` | siPlayerWhoClicked | 0 | LobbyHeaderRight | `0x206c` |
| PreGameTips | `0x1000026D` | asiPregameTips | 0 | TipManager | - |
| UpdateEarlyLaunchTime | `0x100001CB` | ttEarlyLaunchBegginingTime, ttEarlyLaunchEndTime | 0 | PvPLobby | `0x2061` |
| UpdateLobbyLoadingPercent | `0x100001D4` | auTeamNumbers, auTeamIndexes, anLoadingPercents | 0 | PvPLobby | `0x2031` |
| UpdateLobbyLoadingPercentForViewmatch | `0x100003D9` | iLoadingPercent | 0 | PvPLobby | `0x206d` |
| UpdateLobbyState | `0x100001C5` | auTeamNumbers, auTeamIndexes, aiidPlayerIIDs, asiPlayerNames, abIsBot, adidCharacterDIDs, anCharacterLevels, adidCharacterPreGameDIDs, abLockedStatus, bDoReveal, adidStolenPowersOne, adidStolenPowersTwo, adidMiniWallpapers, adidCharacterIcons, adidBaseCharacterDIDs, aAmplifierSetSlots, aAmplifierSetIcons, aAmplifierSetNames, aAmplifierSetModifierOne, aAmplifierSetModifierTwo, aAmplifierSetModifierThree, aAmplifierSetModifierFour, aAmplifierSetModifierFive, aAmplifierSetModifierSix, aAmplifierSetModifierSeven | 0 | PvPLobby | `0x2060 (layout match)` |
| UpdateLobbyStateSingle | `0x100001D6` | uTeamNumber, uTeamIndex, iidPlayerID, siPlayerName, bIsBot, didCharacterDID, nCharacterLevel, didCharacterIconDID, didCharacterPreGameDID, bLockedStatus, didStolenPowerOne, didStolenPowerTwo, didBaseCharacterDID, uiAmplifierSetSlot, didAmplifierSetIcon, strAmplifierSetName, aAmplifierSetModifiers | 0 | PvPLobby | `0x2029` `0x204c` `0x2060` |

#### `GM_LoginReward` (2)

| notice | id | arguments | key | Flash listeners | network feeder |
|---|---|---|---|---|---|
| UI_DeliverLoginRewardSet | `0x10000509` | nLastLoginRewardDay, bLoginRewardEligible, aRewardDays, aRewardDayFocusLabels, aRewardDayLabels, aQualityTypes, aBestowalTypes, aRewardTypes, aDescriptions, aIsMysteries, aItemDIDs, aItemIconDIDs, aItemNames, aItemQuantities | 0 | RewardTimeline | `0x2197 (progression-meta)` |
| UI_NoEligibleLoginReward | `0x10000516` | - | 0 | RewardTimeline | `0x219d` |

#### `GM_MapManager` (13)

| notice | id | arguments | key | Flash listeners | network feeder |
|---|---|---|---|---|---|
| AddMapNotes | `0x100001B4` | aEntities, aPos, aIcon, aTeam, aZLevel, aMapNoteCategory, aMapNoteDecoration | 0 | MinimappyThing | - |
| AddStaticMapNote | `0x100001B2` | nPos, didIcon | 0 | MinimappyThing | - |
| DeliverMapData | `0x100001B0` | didMapImage | 0 | MinimappyThing | - |
| MapNote_UnderAttack | `0x100001B1` | iidEntity | 0 | MinimappyThing | - |
| RemoveMapNote | `0x100001AD` | iidEntity, didIconDead | 0 | MinimappyThing | `0x2137` |
| SetPingPrepped | `0x100001E8` | bAlertPrepped, bRetreatPrepped | 0 | MinimapMouseTarget | - |
| ShowMiniMapTargetingRing | `0x10000300` | bDisplay, fRadius | 0 | MinimappyThing | `0x209f` `0x217f` `0x2180` |
| ToggleMiniMap | `0x100001AF` | - | 0 | MainHUD | - |
| ToggleMiniMap_PlayersOnly | `0x100001AC` | - | 0 | **none** | - |
| UI_StartTeleportEffects | `0x100004F6` | iidEntity | 0 | MinimappyThing | `0x2189` `0x218a` |
| UI_StopTeleportEffects | `0x100004F5` | iidEntity | 0 | MinimappyThing | `0x2189` `0x218a` |
| UpdateMapNotes | `0x100001B7` | aEntities, aPos | 0 | MinimappyThing | - |
| UpdateMapNotesDecorations | `0x100001AE` | aEntities, aDecorations | 0 | MinimappyThing | - |

#### `GM_Options` (2)

| notice | id | arguments | key | Flash listeners | network feeder |
|---|---|---|---|---|---|
| InGameFullScreenOptionChanged | `0x100004B7` | bValue | 0 | GraphicsPaneContents | - |
| OutOfGameFullScreenOptionChanged | `0x100004BA` | bValue | 0 | GraphicsPaneContents | - |

#### `GM_ProfileUI` (4)

| notice | id | arguments | key | Flash listeners | network feeder |
|---|---|---|---|---|---|
| ProfileUI_AmplifierSetData | `0x1000043B` | aEncounters, aAmplifierSets, aSlots, aIcons, aNames, aAmplifiers | 0 | ChampionDetailPanel | - |
| ProfileUI_CharacterVariantsLoaded | `0x10000446` | aSkinUIRequestedDIDs, aPregameIDsArray | 0 | ChampionDetailPanel | - |
| ProfileUI_HeavyResourcePackData | `0x1000043C` | didCharacter, didHeavyDBPC, didPowerSetDBPC, didLightDBPC | 0 | AnimatedRankedDisplay, ChampionDetailPanel, Ranked, SuperRewardRibbon, VeteranChampion, VeteranLanding | - |
| ProfileUI_SpecialSecondaryPower | `0x1000043D` | didSecondaryPower | 0 | ChampionDetailPanel, VeteranChampion | - |

#### `GM_SelectionSystem` (8)

| notice | id | arguments | key | Flash listeners | network feeder |
|---|---|---|---|---|---|
| AddUsableTarget | `0x100000B3` | iidTarget, eUsage | 0 | **none** | - |
| ClearTrackedEntity | `0x10000309` | - | 0 | SelectionPanel | - |
| FoundTrackedEntity | `0x10000487` | - | 0 | SelectionPanel | - |
| LostTrackedEntity | `0x10000486` | - | 0 | SelectionPanel | - |
| RemoveUsableTarget | `0x100000B2` | iidTarget | 0 | **none** | - |
| UpdateTrackedEntity | `0x10000304` | iidEntity, eType, eDisplay, siName, didIcon, nTeam | 0 | SelectionPanel | - |
| UsableTargetInRange | `0x100000AC` | iid | IID | **none** | - |
| UsableTargetOutOfRange | `0x100000B1` | iid | IID | **none** | - |

#### `GM_Skill` (5)

| notice | id | arguments | key | Flash listeners | network feeder |
|---|---|---|---|---|---|
| EnableSkillButton | `0x100002D7` | eSkill, bEnable | 0 | ArtifactsCollectionActionButtons, SkillsPanel | `0x207b` `0x20a0` `0x2187` |
| UI_NotifySkillButtonUpdateIsSuppressed | `0x10000250` | eSkill, bSuppressed | 0 | SkillsPanel | `0x208c` |
| UI_NotifyVitalChange | `0x10000274` | eVitalType, fNewValue | 0 | SkillsPanel | - |
| UI_SkillUpdate | `0x10000275` | eSkillSlot, siCost, fCost, siCooldown, siDescription, siSkillName, didIcon, iRank, bSkillCanBeActivated, eDamageType, eCanRankSkill, eRecommnedSkillToRank, bCharacterIsInBase, aGridDetailsColOne, aGridDetailsColTwo, aGridDetailsColThree, aGridDetailsColFour, aGridDetailsColFive, aGridDetailsColSix | 0 | ArtifactsCollectionActionButtons, SkillsPanel | - |
| UpdateSkillUIOverlay | `0x1000015A` | iid, eSkill, eOverlay, bEnable | IID | ArtifactsCollectionActionButtons, SkillsPanel | `0x2091` `notice 0x1000015a` |

#### `GM_StatusIcon` (5)

| notice | id | arguments | key | Flash listeners | network feeder |
|---|---|---|---|---|---|
| AddStatusIcon | `0x10000191` | iid, didIcon, siDescription, siTitle, siHeading, nPriority, nGameHandleID, iidStatusIconGameHandle, nCount, ttEndTime, fDuration, didTooltipIcon, siPlayerName, siAgentName | IID | StatusIconDisplay | `0x20a2` `0x20c8` |
| BatchAddStatusIcon | `0x100001A6` | iid, adidIcon, asiDescription, asiTitle, asiHeading, anPriority, anGameHandleID, aiidStatusIconGameHandle, anCount, attEndTime, afDuration, adidTooltipIcon, asiPlayerName, asiAgentName | IID | StatusIconDisplay | - |
| RemoveStatusIcon | `0x10000190` | iid, nGameHandleID, iidStatusIconGameHandle | IID | StatusIconDisplay | `0x20e9` |
| UpdateStatusIcon | `0x1000018F` | iid, nGameHandleID, iidStatusIconGameHandle, siDescription, nCount, ttEndTime, fDuration, didTooltipIcon, siPlayerName, siAgentName | IID | StatusIconDisplay | `0x20a8` |
| UpdateStatusIconTooltip | `0x1000029A` | iid, nGameHandleID, iidStatusIconGameHandle, siDescription | IID | StatusIconDisplay | `0x20d0` `0x2127` |

#### `GM_Tutorial` (3)

| notice | id | arguments | key | Flash listeners | network feeder |
|---|---|---|---|---|---|
| UI_CloseTutorialHint | `0x100004A6` | eHintID | 0 | HintManager | `notice 0x100004a5 (u32, same reader block; probable)` |
| UI_ShowTutorialHint | `0x10000285` | eHintID, didIcon, siHeader, siShortDescription, siFullDescription, didTooltipGraphic, bForceOpen | 0 | HintManager | `notice 0x1000027f (hint id + force flag; C++ fills the texts)` |
| UI_ShowTutorialHints | `0x10000284` | aHintIDs, aIconDIDs, aHeaders, aShortDescriptions, aFullDescriptions, aTooltipGraphics | 0 | HintManager | `notice 0x10000288 (list<u32>; probable)` |

#### `GM_UI` (54)

| notice | id | arguments | key | Flash listeners | network feeder |
|---|---|---|---|---|---|
| AvailableCharacterList | `0x100002E2` | adidsAvailableCharacters, adidsCharacterCharPickerIcons, asiCharacterNames | 0 | OwnablesManager | `0x20b8` |
| BarredFromMatching | `0x100003A7` | nTimeout | 0 | WrapperMain | `0x20f3` |
| BatchNotifyHUDElements | `0x10000440` | aElementIDs, aEventIDs, aHighlights, aHighlightDIDs | 0 | LobbyWrapper, MainHUD | `0x213e` |
| CharacterAdvancementData | `0x100002E8` | aCharacters, aLevels, aCurrentXP, aNextLevelXP, aCharacterLastUsedInUnixSeconds, aCharacterRankedLastUsedInUnixSeconds | 0 | OwnablesManager | `0x209d (layout match)` |
| ChargenError | `0x10000231` | strErr | 0 | DisplayNameRequestScreen | - |
| ClientLanguage | `0x10000518` | eLanguage | 0 | LanguageManager | - |
| DefeatStatusUpdated | `0x10000090` | iid, eNewLifeState, ttNextState | IID | DefeatManager | `notice 0x10000090` |
| DefeatStatusUpdatedForEntity | `0x100000BC` | iid, iidEntity, ePerceivedType, eNewLifeState, ttNextState | IID | MatchData | `notice 0x100000bc` |
| DeliverFriendsLeaderboard | `0x10000529` | aAccountIIDs, aNames, aRanks, aSubPips, aPositions, aChampionDIDs, siTitle, iidMyAccount | 0 | LeaderBoardManager | `0x21a2` `0x21a3` |
| DeliverRegionalLeaderboard | `0x10000528` | aAccountIIDs, aNames, aRanks, aSubPips, aPositions, aChampionDIDs, siTitle, iidMyAccount | 0 | LeaderBoardManager | `0x21a2` `0x21a3` |
| DisplayDialogText | `0x1000010A` | siName, siDialogText | 0 | MainHUD, WrapperMain | `0x2087` `0x20ed` `0x210a` `0x210b` |
| ExecuteSkillError | `0x1000008A` | skillSlot, skillError, fMouseX, fMouseY | 0 | ArtifactsCollectionActionButtons, SkillsPanel | `0x2092` `0x20dc` |
| ExitingWorld | `0x10000103` | - | 0 | AnnouncementsManager, ContactsManager, ControlledAgentDispatcher, DataReferencesManager, FoundryManager, MainHUD, MatchData, OverheadVitalsBase, VitalPropertyObserver | `0x2021` `local` |
| FPSUpdate | `0x10000467` | nFPS, nLatency, siTooltip | 0 | FPSDisplay | - |
| FadeFloatyVitals | `0x10000016` | iidEntity, bFadeOut | 0 | FloatyVitalsManager | - |
| FindMatchFailure | `0x100004FC` | siMsg, nBonusPercent, siQueueTooltip | 0 | MatchmakingIndicator | `0x218d` |
| FogOfWarSettingsDirty | `0x100002AA` | - | 0 | **none** | - |
| FoundMatch | `0x1000023A` | nNumAccounts, nTimeout | 0 | GroupInviteDialog, WrapperMain | `0x20fa` |
| GameFrontUIDestroyedInCPP | `0x100001D7` | - | 0 | LobbyWrapper, PvPLobby | `0x2021` |
| HideDialogText | `0x1000010B` | - | 0 | **none** | - |
| HideToViewMatchLayout | `0x10000227` | - | 0 | MainHUD | - |
| Incremental_ItemStatuses | `0x100004F3` | aItems, aItemStatuses, aItemTypes, aOwned, aCount | 0 | OwnablesManager | `0x204c` `0x20b8` |
| ItemStatuses | `0x100002E1` | aItems, aItemStatuses, aItemTypes, aOwned, aCounts | 0 | OwnablesManager | `0x20b8` |
| JoinedQueue | `0x10000239` | didEncounter, fWaitTime, fUpdateInterval, fNextUpdate, bAdmin, bRejoin, bTimeout, bGroup | 0 | WrapperMain | `0x20c0` |
| LoggedIntoGame | `0x100003B9` | bLoggedIn | 0 | **none** | - |
| Matchmaking_NewUpdateInterval | `0x100004FD` | fUpdateInterval, fNextUpdate | 0 | MatchmakingIndicator | `0x218e` |
| NotifyHUDElement | `0x10000420` | eElementID, eElementEvent, eHighlightID, didHighlightArtifact, strHighlightTitle, strHighlightMessage | 0 | LobbyWrapper, MainHUD | `0x213d` |
| NotifyUISkillButtonPressed | `0x100001B9` | skillSlot | 0 | **none** | - |
| NumPlayersAcceptedMatch | `0x10000243` | nNumPlayers | 0 | MatchFoundRibbon | `0x20ad` |
| PauseDefeatStatusTimerForEntity | `0x100000BA` | iid, iidEntity, eCurrentLifeState | IID | **none** | `notice 0x100000ba` |
| PendingMatchFailure | `0x10000244` | bTimeout | 0 | RibbonManager, WrapperMain | `0x20d7` `0x210b` |
| ProtectorAdvancementStatus | `0x10000492` | eStatus, strMovieToPlay | 0 | AchievementsManager, EncounterManager, TraineeAchievements, WrapperMain | `0x215d (account flags; probable)` |
| QueueEligibility | `0x10000500` | bMeetsLevelReq, siLevelReqMsg, aEncounters, aRankedGamesEligibility, aRankedGamesReqMsgs, aDraftEligibility, aDraftRequirementMsgs | 0 | EncounterManager | `0x2101` |
| QueueWaitTimesUpdated | `0x1000052F` | - | 0 | MatchmakingIndicator, PVPGroupingInterface | `0x218f` |
| ReleaseNotesUrl | `0x1000048C` | strReleaseNotesUrl | 0 | ReleaseNotesElement | - |
| RemoveSkillStackCountString | `0x100004DE` | eSlot | 0 | SkillsPanel | `0x20e9` |
| RemovedFromQueue | `0x10000289` | - | 0 | WrapperMain | `0x20e0` `0x210b` |
| Scorecard_HeavyOnlyLoaded | `0x100004ED` | didHeavyDBPC, didSecondaryPower | 0 | CharLevelUpRibbon, Scorecard | - |
| SendHeaderNameAndProtectorIcons | `0x1000047F` | strHeaderName, aIconDIDs, aIconNameStrings, aIconDescStrings, aIconUnlockDescStrings | 0 | AccoladeManager, CallingCardDialog, HeaderProfile, ScorecardManager, SelfPresenceDisplay, TraineeAchievements | `0x2154` `0x2190` |
| SetupSettingsButtons | `0x100003EA` | - | 0 | **none** | - |
| ShowURLDialog | `0x10000265` | strURL | 0 | WrapperMain | - |
| StartHUDCurtainTransition | `0x1000015B` | bLowerCurtain | 0 | **none** | - |
| StartSkillCooldown | `0x10000055` | eSlot, fCooldownTime | 0 | ArtifactsCollectionActionButtons, SkillsPanel | `0x20f8` |
| TimerClockSync | `0x10000076` | iid, nServerClock | IID | CountdownTimer | `notice 0x10000076` |
| ToggleMainMenu | `0x1000006D` | - | 0 | LobbyWrapper, MainHUD, WrapperMain | - |
| UIStateMachineEvent | `0x10000020` | eEvent | 0 | LandingNav, LobbyHeaderCenter, LobbyHeaderRight, LobbyWrapper, MainHUD, PvPLobby, Scorecard, WrapperMain | `0x2038` `0x2053` |
| UI_DeliverAccountStandingsData | `0x1000051E` | didFeaturedEncounter, didLastPlayedEncounter, aEncounters, aRanks, aSubRanks, aRankPositions, aStreakActives, aPreviousRanks, aPreviousSubRanks, aPreviousRankPositions, aPreviousStreakActives, aMatchesPlayed, aMatchesWon, aWonLastMatch, bShowBanner | 0 | RankedManager | `0x219e` `0x219f` |
| UI_DeliverStaticStandingsData | `0x10000521` | nDefaultRank, nDefaultSubRank, aRanks, aSubRanks, aRankNames, aRankIcons, aSmallRankIcons, aLoreStrings, aCharacterVOs, aAssociatedCharacterWCs, aStreakEligibilities, aLossProtections, aWelcomeToStrings, aWelcomeBackStrings, aRankedTiers, aRankedTierDescriptions, aRankedTierMinRanks | 0 | RankedManager | `0x219e/0x219f (one of)` |
| UpdateFloatyVitalArray | `0x100004A8` | aEntityIIDs, aAdd, aPerceivedType, aDisplayType, aDisplayPosition, aDisplayPositionOffset | 0 | FloatyVitalsManager | - |
| UpdateHUDVisibility | `0x10000048` | bShow | 0 | MainHUD | `0x20f5` `0x2150` |
| UpdateSkillStackCountString | `0x1000030C` | eSlot, strCount | 0 | ArtifactsCollectionActionButtons, SkillsPanel | `0x20a2` `0x20a8` `0x20c8` |
| UpdateTrainingFloatyText | `0x100004A1` | iidEntity, bAdd, eTrainingFloatyDisplayType, eDisplayPosition, fDisplayPositionOffset, strText | 0 | FloatyVerbsManager | `0x2171` `0x2172` `0x2173` |
| UserCanCreateGroup | `0x100003B0` | - | 0 | WrapperMain | `0x2070` |
| gmWErrorMessageOccurred | `0x100001F9` | eReason | 0 | DisconnectManager, MatchData | - |

#### `GM_Upgrade` (13)

| notice | id | arguments | key | Flash listeners | network feeder |
|---|---|---|---|---|---|
| ActivatedArtifacts | `0x10000470` | aArtifactsActivated, bAllArtifactsSelectable | 0 | FoundryManager | - |
| BoughtItemListReceived | `0x100001F8` | adidBoughtItems | 0 | **none** | - |
| DisplayFloatyCurrencyChanged | `0x10000506` | iid, fOldCurrencyValue, fNewCurrencyValue | IID | OverheadVitalsDeluxe | - |
| DisplayFloatyCurrencyDenied | `0x10000505` | iid, fCurrency | IID | OverheadVitalsDeluxe | - |
| ReturnedUpgradeArrayPreview | `0x10000277` | aPowerGraphValues | 0 | FoundryManager | - |
| SendAvailableUpgrades | `0x100001C1` | aUpgrades, aUpgradeImages, aAmplifierIcons, aUpgradeNames, aUpgradeCost, aUpgradeSellBackAmount, aUpgradeStackLimits | 0 | **none** | - |
| SetUIArtifactSkillSlotMapping | `0x1000042A` | aSkillSlotOrder | 0 | ArtifactDataManager | - |
| UI_RefreshPurchasability | `0x1000046D` | - | 0 | FoundryManager | - |
| UI_ShowFloatyCurrencyOverEntity | `0x100004D5` | iidAgent, fCurrency | 0 | OverheadVitalsBase | - |
| UpdateCurrentUpgrades | `0x1000012F` | iidAgent, aUpgrades, aUpgradeIconDIDs, aUpgradeStackSize, aModDIDs, aModBrandOverlayIconDIDs | 0 | FoundryManager, MatchData, ScorecardManager | `0x20e2` |
| UpdateNextRecommendedUpgrade | `0x10000272` | didNewUpgrade, bCanBuy | 0 | DefeatRecommendationsPanel, FoundryManager | `0x2078` |
| UpdatePowerGraphValues | `0x10000160` | iidAgent, aAmounts | 0 | HeroGraph, MatchData, ScorecardManager | `0x20e2` |
| UpgradeCooldown | `0x10000235` | didItem, cooldownDuration, cooldownEndTime | 0 | **none** | - |

#### `GM_ViewMatch` (12)

| notice | id | arguments | key | Flash listeners | network feeder |
|---|---|---|---|---|---|
| ViewMatchCameraChange | `0x100002C1` | bDirectedCameraOn, bCameraLocked, iidAgent | 0 | VMPlayersSinglePlayerDisplay, ViewMatchControlsBottom | - |
| ViewMatchCameraTarget | `0x100002D2` | iidAgent | 0 | **none** | - |
| ViewMatchFOWControls | `0x100002DA` | nTeam | 0 | ViewMatchControlsBottom | - |
| ViewMatchGoldTotal | `0x100002D4` | nTeamID, nGoldAmount | 0 | **none** | - |
| ViewMatchKDATotal | `0x100002D3` | nTeamID, nKillAmount, nDeathAmount, nAssistAmount | 0 | **none** | - |
| ViewMatchPlayerSkillUse | `0x100002C4` | iidAgent, eSlot, ttEndTime | 0 | VMPlayersSinglePlayerDisplay | - |
| ViewMatchScoreboardData | `0x1000046C` | aTeamGoldAmounts, aTeamKillAmounts, aDeathAmounts, aAssistAmounts | 0 | MatchData | - |
| ViewMatch_ShowAllPlayersPanel | `0x10000483` | - | 0 | **none** | `0x206d` |
| ViewMatch_ShowTeamInfoPanel | `0x10000481` | - | 0 | **none** | - |
| ViewMatch_ToggleBottomDisplay | `0x10000480` | - | 0 | **none** | - |
| ViewMatch_UpdateDampenerCounts | `0x1000048F` | aTeamDampenerCounts | 0 | ViewMatchTopDivided | `0x215c` |
| ViewMatch_UpdateTurretCounts | `0x1000048A` | aTeamTurretCounts | 0 | ViewMatchTopCoastCity, ViewMatchTopDivided | - |

#### `GM_Vitals` (4)

| notice | id | arguments | key | Flash listeners | network feeder |
|---|---|---|---|---|---|
| DOTUpdate | `0x10000311` | iid, aDamageTypes, aDamageValues | IID | OverheadVitalsBase | - |
| DisplayFloatyStatus | `0x1000038B` | iid, eStatusType | IID | OverheadVitalsDeluxe | `0x0044` `0x208d` `0x20bd` |
| VOTUpdate | `0x10000310` | iid, aDamageTypes, aDamageValues | IID | OverheadVitalsDeluxe | - |
| VitalsChanged | `0x10000018` | iid, eVitalType, fOldCurrentVital, fNewCurrentVital, fOldMaxVital, fNewMaxVital, fTempCurrent, fTempMax, aDamageTypes, aDamageValues, aVitalValues, bShowFloatyDamage, bShowFloatyHeal | IID | OverheadVitalsBase, VMSkillDisplay, VitalsLarge | `0x0042` |

---

## 5. Flash -> C++: every `SendNotice_*` and `SendQuery_*` (420)

`?` marks a query (synchronous, answered locally through `gameOutputArgs`; the "returns" column lists the output
names). "network event" = the client -> server event the C++ listener sends (from `protocol-complete.md` 2.2-2.3:
dispatcher-slot names [C], others [P]); `-` = handled inside the client (or not yet traced). **never called** = no
AS2 class calls the wrapper.

#### `EM_SocialMedia` (1)

| call | id | arguments | returns | called by | network event |
|---|---|---|---|---|---|
| UI_RequestSocialMediaURL | `0x00000089` | - | - | BrowserSocialMedia, BrowserTest | - |

#### `EM_Sound` (2)

| call | id | arguments | returns | called by | network event |
|---|---|---|---|---|---|
| Play | `0x0000003E` | eEvent | - | AccoladeButton, AccoladesChampionDisplay, AccoladesMapDisaply, AccoladesMeritDisplay, AccoladesProtectorDisplay, AmplifierPurchaseCompleteDialog, AmplifierPurchaseDialog, AnimatedRankedDisplay, ArtifactFoundry, ArtifactsCollectionActionButtons, Assembler, BaseHudElement, BasicButton, BrowserErrorDialog, CallingCardDialog, CategoryHeader, ChampionDetailPanel, CharacterButton, CharacterPicker, CheckBoxButton, CoastCityWelcomeBillboard, ConfirmationDialog, ConnectingScreen, ContactsComponent, ContactsTabButton, CustomMatchInviteNotification, CustomMatchInvitePreview, DefeatRecommendationsPanel, DualCurrencyPurchaseCompleteDialog, DualCurrencyPurchaseDialog, EncSoloGroupScreen, EventAnnouncementDisplay, EventTimerV2, FoundryManager, FriendInviteNotification, FriendInvitePreview, GothamHeightsWelcomeBillboard, GroupHeader, GroupInviteDialog, GroupInviteNotification, GroupInvitePreview, GroupListExpandButton, Hint, InlineTextEditor, LandingSwitcher, LaunchButton, LaunchWarning, LevelUpRibbon, LobbyWrapper, LoginRewards, LoginScreen, MatchFoundRibbon, MatchmakingIndicator, MissionTypeButton, MovieDialog, NotificationPreviewsManager, ObjectiveDisplay, ObjectiveListDisplay, PowerGraphCategorizedItemDisplay, PowerPicker, ProtectorIconSubmenu, PvPLobby, RankRibbon, Ranked, RankedButton, RecallButton, RecommendedPowerBar, ReportAPlayerDialog, RewardDay, RewardRibbon, RewardTimeline, RoleButton, SaveDiscardCancelDialog, Scorecard, SettingsPanelDialog, SkillButton, SkillControl, SkillsPanel, SkinPicker, Stats, SuperRewardRibbon, TeamHealthDisplay, TextEntryDialog, TooltipManager, TraineeAchievements, TutorialTip, VeteranLanding, WrapperBlankScreen, WrapperMain, WrapperScreen | - |
| Stop | `0x00000042` | eEvent | - | **never called** | - |

#### `EM_UI` (3)

| call | id | arguments | returns | called by | network event |
|---|---|---|---|---|---|
| DetectAppropriateRenderSettings | `0x000000BA` | - | - | GraphicsPaneContents | - |
| ForceOnSized | `0x00000092` | - | - | ResolutionSizer | - |
| ?InqIsWindowsXP | `0x000000B8` | - | - | GraphicsPaneContents | - |

#### `EM_WebBrowser` (1)

| call | id | arguments | returns | called by | network event |
|---|---|---|---|---|---|
| ?InqFoundCEF3SubprocessExecutable | `0x000000BD` | - | - | WrapperMain | - |

#### `EM_WebTicket` (1)

| call | id | arguments | returns | called by | network event |
|---|---|---|---|---|---|
| UI_RequestWebTicket | `0x00000063` | - | - | Assembler, Store | - |

#### `GM_Achievement` (6)

| call | id | arguments | returns | called by | network event |
|---|---|---|---|---|---|
| AcknowledgeAchievementDisplayed | `0x1000041C` | didAchievement | - | RewardRibbon | `0x211e? (u32; guess)` |
| RequestAchievementDetails | `0x1000041B` | didAchievement | - | AccoladesProtectorDisplay, Achievements, NewPlayerScreen, NextChallenge, TraineeAchievements, VeteranAchievement | - |
| RequestAllAchievementData | `0x1000041A` | - | - | AchievementsManager | `0x211d` |
| RequestAllPendingRewardlessAchievementNotifications | `0x1000042E` | - | - | WrapperMain | `0x212e` |
| RequestTraineeAchievements | `0x10000498` | - | - | AchievementsManager | - |
| ?InqSuperBannerVideoForAchievement | `0x1000049B` | didAchievement | siVideoName | SuperRewardRibbon | - |

#### `GM_AdminAlert` (1)

| call | id | arguments | returns | called by | network event |
|---|---|---|---|---|---|
| UI_RequestAdminAlerts | `0x10000458` | - | - | HeaderCenter | - |

#### `GM_Advancement` (8)

| call | id | arguments | returns | called by | network event |
|---|---|---|---|---|---|
| RankSkill | `0x1000009B` | iidAgent, eSkill | - | DefeatRecommendationsPanel, SkillsPanel | `0x2136 (patched client only; unpatched: script RPC 0x9F 0x81910003)` |
| ShowExperienceRings | `0x10000302` | bDisplay | - | ExperienceBar | - |
| ?InqCanRankSkill | `0x1000006A` | iidAgent, eSkill | eError | DefeatRecommendationsPanel, SkillsPanel | - |
| ?InqLevelCap | `0x10000009` | - | iMaxLevel | ExperienceConsole | - |
| ?InqNextRecommendedSkillToRank | `0x1000023C` | iidAgent | eSkill | DefeatRecommendationsPanel, SkillsPanel | - |
| ?InqSkillPointsAvailableString | `0x10000423` | iidAgent | siAvailablePointsString | DefeatRecommendationsPanel, SkillsPanel | - |
| ?InqSkillRank | `0x10000063` | iidAgent, eSkill | iRank | SkillsPanel | - |
| ?InqXPForLevel | `0x10000011` | iLevel | iXP, iXPPreviousLevel | ExperienceConsole | - |

#### `GM_Amplifier` (11)

| call | id | arguments | returns | called by | network event |
|---|---|---|---|---|---|
| UI_RequestAllAmplifierBoutiqueData | `0x10000405` | - | - | Assembler, BoutiqueDataManager | - |
| UI_RequestAllAmplifierSets | `0x100003C1` | - | - | AmplifierSetManager, Assembler | - |
| UI_SaveAmplifierSet | `0x100003C0` | uiAmplifierSlotID, didCharacterReference, strAmplifierNames, didIcon, didEntryOne, didEntryTwo, didEntryThree, didEntryFour, didEntryFive, didEntrySix, didEntrySeven | - | Assembler | `0x20fc (probable: same fields)` |
| ?UI_InqAmplifierSetIcons | `0x100003D8` | - | - | AmplifierSetManager, Assembler | - |
| ?UI_InqAmplifierSetSlotInfo | `0x1000044F` | - | strName, didIcon | Assembler | - |
| ?UI_InqAugmentData | `0x100003CF` | aAugments | - | AmplifierSetManager | - |
| ?UI_InqAugmentModStoreUrls | `0x10000406` | - | strAugmentUrl, strModUrl | Assembler | - |
| ?UI_InqAugmentsPassingFilter | `0x10000460` | aAugments, strFilter | - | Assembler | - |
| ?UI_InqCharacterDefaultAmplifierSet | `0x100003EF` | didCharacter | didDefaultAmplifierSet | AmplifierSetPicker | - |
| ?UI_InqModData | `0x100003D0` | aMods | - | AmplifierSetManager | - |
| ?UI_InqModsPassingFilter | `0x1000045F` | aMods, strFilter | - | Assembler | - |

#### `GM_Artifact` (7)

| call | id | arguments | returns | called by | network event |
|---|---|---|---|---|---|
| FakeFoundryNotice | `0x1000030B` | - | - | **never called** | - |
| ?InqArtifactDetails | `0x100002CD` | iidUpgradeOwner, didUpgrade | fArtifactCost, fArtifactSellBackAmount, siArtifactName, didSkill, siSkillKeyword, siSkillDescription, siLore, didModIcon, didModBrandOverlayIcon, siModDescription | ArtifactDataManager, ArtifactTooltipData | - |
| ?InqArtifactsMatchingCategoryFilterSet | `0x100002D9` | aOptions, strFilter | - | AdvancedPanel | - |
| ?InqAvailableArtifacts | `0x100002CC` | bShowArtifactTiers, nGraphCategory | - | ArtifactDataManager | - |
| ?InqKillCardArtifactTooltip | `0x100003DB` | didArtifact, didMod | siArtifactName, siArtifactDescription, didModIcon, didModBrandOverlayIcon, siModDescription | ArtifactTooltipData, ContributorRow | - |
| ?InqRecommendedArtifacts | `0x100002ED` | - | - | ArtifactDataManager | - |
| ?InqRemainingRecommendedArtifacts | `0x100002CB` | - | - | ArtifactDataManager | - |

#### `GM_Camera` (1)

| call | id | arguments | returns | called by | network event |
|---|---|---|---|---|---|
| FullScreenUIActive | `0x10000174` | bActive | - | HudModeManager | - |

#### `GM_Character` (25)

| call | id | arguments | returns | called by | network event |
|---|---|---|---|---|---|
| CharacterSelected | `0x100000AA` | didVariant | - | **never called** | - |
| RequestAccountCharacterData | `0x100003A2` | - | - | **never called** | - |
| RequestAccountCurrencyBalance | `0x1000028B` | - | - | HeaderLeft, ScorecardManager, WrapperMain | - |
| RequestAccountCurrencyBalanceChanges | `0x10000292` | - | - | ScorecardManager | - |
| RequestAccountEncounterStats | `0x10000418` | - | - | Stats | `0x2116` |
| RequestAccountEndOfMatchAccoladesEarned | `0x100004E6` | - | - | AccoladeManager, ScorecardManager | - |
| RequestAccountEndOfMatchAccountLevelAndXP | `0x100003FA` | - | - | ScorecardManager | - |
| RequestAccountEndOfMatchCharacterLevelAndXP | `0x100003F1` | - | - | ScorecardManager | - |
| RequestAccountEndOfMatchSoftCurrencyReward | `0x100003F2` | - | - | ScorecardManager | - |
| RequestAccountLevelAndXP | `0x10000261` | - | - | WrapperMain | - |
| RequestPostMatchChanges | `0x10000251` | - | - | WrapperMain | `0x20ba` |
| Ribbon_ReceivedItemsFulfilled | `0x100003D4` | - | - | WrapperMain | - |
| UI_ClaimPostMatchReward | `0x100003F5` | didReward, didChoice | - | RewardRibbon, SuperRewardRibbon | `0x2128` |
| UI_RequestBestAccolades | `0x100004F0` | - | - | AccoladeManager | - |
| UI_RequestPendingPostMatchRewards | `0x100003F4` | - | - | **never called** | - |
| UI_RequestPendingRewardUpdateFromServer | `0x1000042F` | - | - | WrapperMain | `0x2124` |
| UI_SetProtectorIcon | `0x1000047E` | didNewIconWC, uIndex | - | CallingCardDialog | `0x2093` |
| ?InqCharacterPanelInfo | `0x100001F3` | iid | - | ControlledAgentDispatcher | - |
| ?InqCharacterPanelMetaData | `0x100001F2` | iid | - | ControlledAgentDispatcher | - |
| ?InqCharacterRoles | `0x100001EB` | didCharacter | - | ChampionDetailPanel, CharacterPreview, PlayerDisplay | - |
| ?InqCharacterSkills | `0x10000092` | iidAgent | - | SkillsPanel | - |
| ?InqCharactersLoaded | `0x10000091` | - | bLoaded | BootupInputHandler, ConnectingScreen | - |
| ?InqRegenValues | `0x10000233` | iid | healthRegenValue, secondaryRegenValue | VitalsLarge | - |
| ?RequestProtectorIcons | `0x1000047D` | - | - | ProtectorIconManager | - |
| ?UI_RequestAspirationalTooltip | `0x10000370` | didItem | - | AccoladesChampionDisplay, ChampionDetailPanel, PowerPickerSubmenu, VeteranChampion | - |

#### `GM_Chat` (10)

| call | id | arguments | returns | called by | network event |
|---|---|---|---|---|---|
| AdjustActiveChatWindow | `0x1000027E` | nX, nY, nWidth, nHeight | - | **never called** | - |
| HideChatForBrowser | `0x10000299` | - | - | ChatManager | - |
| HideChatWindow | `0x1000026F` | bClearLogs | - | ChatManager | - |
| HideWrapperChatLog | `0x10000504` | eLog | - | **never called** | - |
| LeaveChatRooms | `0x10000270` | aRooms | - | **never called** | - |
| RestoreChatForBrowser | `0x10000298` | - | - | ChatManager | - |
| RunCmd | `0x1000028F` | siCmd | - | ContactDisplay, GroupInviteDialog, GroupInviteNotification, GroupInvitePreview, PVPGroupInviteForm, PVPGroupManager, PlayerInfoListItem, ScorecardRow | - |
| SetActiveWrapperChatTab | `0x10000411` | eLog | - | **never called** | - |
| ShowChatWindow | `0x1000026E` | eLog, bClearLogs, bIsInMatchChat | - | ChatManager, MainHUD | - |
| StartPlayerTell | `0x100003DE` | strTargetPlayer | - | ContactSubmenu | `0x20cd? (guess)` |

#### `GM_ConnectionManager` (4)

| call | id | arguments | returns | called by | network event |
|---|---|---|---|---|---|
| LoginWithWBID | `0x10000208` | sWBID, sPassword | - | LoginScreen | - |
| ResetLastConnectionErrorString | `0x100003A6` | - | - | WrapperMain | - |
| ?CheckLobbyConnection | `0x100003A5` | - | bConnected | WrapperMain | - |
| ?InqLastConnectionErrorString | `0x1000022D` | - | sErrorString | WrapperMain | - |

#### `GM_Contacts` (13)

| call | id | arguments | returns | called by | network event |
|---|---|---|---|---|---|
| UI_AddNoteToContact | `0x10000315` | iidContact, strNote | - | ContactDisplay | - |
| UI_AddStatusMessage | `0x10000336` | strStatusMessage | - | SelfPresenceDisplay | - |
| UI_ContactList_Ready | `0x1000031A` | - | - | ContactsComponent | - |
| UI_CreateContactGroup | `0x10000313` | strGroupName | - | InlineNewGroupEditor | - |
| UI_DestroyContactGroup | `0x10000314` | iGroupID | - | GroupSubmenu | - |
| UI_IgnoreUnignoreContact | `0x10000312` | iidContact, strContactName, bIgnore | - | ContactSubmenu | - |
| UI_InviteContact | `0x10000319` | strContactName | - | CMPlayerSubmenu, InviteForm, InvitedPlayerDisplay, PVPGroupManager, ScorecardRow | - |
| UI_InviteResponse | `0x10000316` | iidInviter, strInviterName, bResponse | - | FriendInviteNotification, FriendInvitePreview | - |
| UI_InviteSteamFriends | `0x10000512` | - | - | ContactsPanelHeader | - |
| UI_MoveContactToGroup | `0x10000318` | iidContact, iGroupID | - | ContactSubmenu | - |
| UI_RemoveContact | `0x10000317` | iidContact | - | ContactSubmenu | - |
| UI_UpdatePresence | `0x10000335` | ePresence | - | SelfPresenceDisplay | - |
| ?UI_CanInviteSteamFriends | `0x10000513` | - | bCanInvite | WrapperMain | - |

#### `GM_Contextual` (3)

| call | id | arguments | returns | called by | network event |
|---|---|---|---|---|---|
| UI_CancelContextualPurchase | `0x1000040F` | strBoutiqueID, didItem, strCurrencyName, uiIntialPrice, strOrderID, uiFinalPrice | - | **never called** | - |
| UI_ConfirmContextualPurchase | `0x1000040E` | strBoutiqueID, didItem, strCurrencyName, uiIntialPrice, strOrderID, uiFinalPrice | - | **never called** | - |
| UI_PurchaseContextualItem | `0x1000040D` | strBoutiqueID, didItem, strCurrencyName, uiPrice | - | AmplifierPurchaseDialog, DualCurrencyPurchaseDialog | - |

#### `GM_CustomMatch` (18)

| call | id | arguments | returns | called by | network event |
|---|---|---|---|---|---|
| AssignTeam_CustomMatch | `0x10000379` | iidTarget, nTeam | - | CMPlayerSubmenu, PlayerDisplayBase | - |
| Cancel_CustomMatch | `0x10000373` | - | - | CustomMatchExitConfirmationDialog | - |
| ChangeCoordinator_CustomMatch | `0x10000386` | iidAccount | - | CMPlayerSubmenu | - |
| Create_CustomMatch | `0x10000372` | didMatch | - | EncSoloGroupScreen | `0x20c1` |
| ForceLaunch | `0x100003A0` | - | - | CustomMatchInterface | `0x2094` |
| GivePerm_CustomMatch | `0x1000037C` | iidTarget, ePerm, bGrant | - | CMPlayerSubmenu, HoldingPen, UnassignedPlayerDisplay | - |
| InviteResponse_CustomMatch | `0x1000037B` | bAccept | - | CustomMatchInviteNotification, CustomMatchInvitePreview | `0x20e6` |
| Invite_CustomMatch | `0x10000375` | strName | - | ContactDisplay, CustomMatchInviteForm | - |
| Kick_CustomMatch | `0x1000037A` | iidTarget | - | CMPlayerSubmenu, UnassignedPlayerDisplay | `0x2199` `0x219a` |
| Launch_CustomMatch | `0x1000037D` | - | - | CustomMatchInterface | `0x20a1` |
| Leave_CustomMatch | `0x10000376` | - | - | CustomMatchExitConfirmationDialog | `0x20c6` |
| MovePosition_CustomMatch | `0x10000378` | iidTarget, nDirection | - | AssignedTeamPlayerDisplay | `0x219b` |
| Randomize | `0x100003D1` | - | - | HoldingPen | `0x20f4` |
| RequestCustomMatchData | `0x1000038A` | - | - | CustomMatchManager | `0x2066` |
| SetDraftMode | `0x100003E8` | bDraftMode | - | CustomMatchInterface | `0x200b` |
| SetEncounter | `0x100003FD` | didEncounter | - | CustomMatchInterface | - |
| SetTeamNames | `0x1000047C` | nTeam, siTeamLongName, siTeamShortName | - | CustomMatchTeamDisplay | - |
| ?IsInCustomMatch | `0x100003E7` | - | bInCustomMatch | AccoladesMapDisaply, HeaderCenter, PVPLauncher, Scorecard, TraineeAchievements, VeteranMap, WrapperMain | `0x20fb` |

#### `GM_Dialog` (6)

| call | id | arguments | returns | called by | network event |
|---|---|---|---|---|---|
| PlayUIDialogElement | `0x100003C6` | eKey | - | AnimatedRankedDisplay, CharacterPicker, HeaderRight, LaunchWarning, PvPLobby | - |
| SetUIDialogIdleState | `0x100003C5` | bState | - | PvPLobby, WrapperMain | - |
| SetUIDialogInQueueState | `0x100003C4` | bState | - | PvPLobby, WrapperMain | - |
| UI_AdvanceConversation | `0x1000044A` | - | - | Speaker | - |
| UI_ReadyForConversation | `0x1000044D` | - | - | ConversationManager | - |
| UI_SkipConversation | `0x10000447` | - | - | ConversationManager | - |

#### `GM_Encounter` (28)

| call | id | arguments | returns | called by | network event |
|---|---|---|---|---|---|
| DisplayEncounterWebInfo | `0x1000048D` | didEncounter | - | LevelImage, MapBigButton, TutorialBigButton | - |
| OnScorecard | `0x1000030E` | bOnScorecard | - | Scorecard, ScorecardScreen | - |
| PlayedEncounterOverviewMovie | `0x100004A9` | didEncounter | - | EncSoloGroupScreen, EncounterDetails, LevelImage, MapBigButton, TraineeAchievements | - |
| ReadyForObjectives | `0x100000C0` | - | - | ObjectiveUpdates2 | - |
| RequestCurrentTeamHealth | `0x10000137` | iid | - | TeamHealthDisplay | `notice 0x10000137` |
| RequestLastMapPlayed | `0x100004C1` | - | - | AccoladesMapDisaply, VeteranMap | - |
| RequestMatchScorecard | `0x10000098` | - | - | MatchData | - |
| RequestPostMatchScorecard | `0x10000264` | - | - | ScorecardManager | - |
| RequestSectorObjectiveState | `0x1000041D` | - | - | MinimappyThing | - |
| SurrenderResponse | `0x10000454` | iid, bSurrendered | - | StartMenuDialog, SurrenderPanel | `notice 0x10000454` |
| UI_Mission_RaiseEvent | `0x10000464` | eMissionEvent | - | CharacterPicker, FoundryManager, PowerPicker, PvPLobby, SecondaryPowerDisplay | - |
| UI_ReadyForDefeatStatus | `0x100003E6` | - | - | MatchTeamDisplay | - |
| UI_ReadyForTimelineData | `0x100002AD` | iid | - | EventTimerV2 | `notice 0x100002ad` |
| UI_RequestBatchUpdateTrackerStatus | `0x1000037F` | - | - | **never called** | - |
| UI_RequestCompletedEncounters | `0x10000471` | - | - | **never called** | - |
| ?InqCharacterCanShop | `0x100003FB` | iid | bCharacterCanShop | DefeatManager, FoundryManager | - |
| ?InqCharacterIsInBase | `0x10000135` | iid | bCharacterIsInBase | SkillsPanel | - |
| ?InqEncounterIdentifierType | `0x100001AB` | - | eType, bDiamondMinimap, bIsTutorial | MainHUD | - |
| ?InqLoadingScreen | `0x100000CC` | - | didImage, siMissionName, siMissionDesc | DynamicLoadingScreen | - |
| ?InqMatchTimes | `0x100001B8` | - | ttStartTime, ttEndTime, bIsPreStartTime | MatchManager, ViewMatchTop | - |
| ?InqPVEEncounters | `0x10000042` | - | - | **never called** | - |
| ?InqPVPEncounters | `0x10000071` | - | didFeaturedPVPMap, didFeaturedBotMap | EncounterManager | - |
| ?InqPromotedMap | `0x10000432` | - | didEncounter, didImage, didButtonImage, didPromotedImage, didMinimapImage, didLoadingScreenImage, siName, siMissionDesc, siBulletedDesc, siCompletionSummary | **never called** | - |
| ?InqTeamColor | `0x10000084` | - | nColor | **never called** | - |
| ?InqTeamData | `0x10000036` | - | fMapRotation | **never called** | - |
| ?InqTeamMapRotation | `0x1000003C` | - | fMapRotation | **never called** | - |
| ?IsLoginEncounterPVP | `0x100000B8` | - | bPVP | FloatyVitalsManager | - |
| ?UI_InqSectorObjectives | `0x1000041E` | - | - | SectorObjectiveTracker | - |

#### `GM_Grouping` (7)

| call | id | arguments | returns | called by | network event |
|---|---|---|---|---|---|
| CacheQueueForGrouping | `0x100004A4` | didEncounter, bDraft, bRanked | - | EncSoloGroupScreen | - |
| ClearInvite | `0x100004E0` | - | - | GroupInviteDialog | - |
| LeaveGroup | `0x10000381` | - | - | PVPGroupManager, PVPGroupingInterface, PVPLauncher | - |
| OnGroupPage | `0x100002A3` | bOnPage | - | PVPGroupManager | - |
| RequestGroupInformation | `0x10000290` | - | - | PVPGroupManager | - |
| SendGroupInvite | `0x100003E0` | strTargetPlayer | - | **never called** | - |
| ?IsInGroup | `0x100003C2` | - | bInGroup | AccoladesMapDisaply, HeaderCenter, PVPLauncher, Scorecard, TraineeAchievements, VeteranMap | - |

#### `GM_KeyBinding` (5)

| call | id | arguments | returns | called by | network event |
|---|---|---|---|---|---|
| UI_CancelAllRebinds | `0x100003CD` | - | - | KeybindingPane | - |
| UI_CommitAllRebinds | `0x100003CE` | - | - | KeybindingPane | - |
| UI_RebindKey | `0x100003CA` | iKeyBindIndex | - | KeybindingPane | - |
| UI_RequestKeyBindingData | `0x100003C8` | - | - | KeybindingPane, SettingsManager | - |
| UI_ResetAllToDefault | `0x100003CC` | - | - | KeybindingPane | - |

#### `GM_Lobby` (19)

| call | id | arguments | returns | called by | network event |
|---|---|---|---|---|---|
| AttemptToRejoinLobbyRoom | `0x100002D1` | - | - | PVPLauncher | - |
| Draft_RequestTrade | `0x100002FD` | iidAccount | - | LobbyPlayerDisplay | - |
| Draft_TradeResponse | `0x100002FB` | bAccepted | - | PvPLobby | - |
| ExitLobbyToMainMenu | `0x100001D3` | - | - | LobbyHeaderRight | `0x200a` |
| LobbyUIReady | `0x100001CA` | - | - | PvPLobby | `0x202d` |
| PlayerChangedCharacterLockStatus | `0x100001CF` | didSelectedCharacter, bLockStatus | - | CharacterPicker | - |
| PlayerSelectedEarlyLaunch | `0x100001CC` | - | - | PvPLobby | `0x206a` |
| RequestAllPregameTips | `0x1000026C` | - | - | TipManager | `0x201e` |
| RequestChangeAmplifierSet | `0x1000038F` | uiAmplifierSet, didDefaultAmplifierSet | - | AmplifierSetPickerMenu | `0x200d` |
| RequestChangeStolenPower | `0x100001F1` | nSlot, didStolenPower | - | PowerPicker | - |
| RequestCharacterPickerInformation | `0x100002B7` | - | - | CharacterPicker | `0x2025` |
| RequestMyAmplifierSet | `0x1000038E` | - | - | AmplifierSetPicker | `0x2057` |
| RequestMyStolenPowers | `0x100001FC` | - | - | SecondaryPowerDisplay | `0x2064` |
| RequestToPurchaseVariant | `0x100001FF` | didCharacter | - | **never called** | - |
| SelectCharacter | `0x100001CE` | didCharacterSelected | - | CharacterPicker, SkinPicker | `0x2102` |
| TeamDisplayReady | `0x100002FE` | - | - | TeamDisplay | `0x2108` |
| TriggerWaitAfterReadyFlag | `0x10000489` | - | - | CharacterPicker | `0x214e` |
| ?RequestStolenPowerList | `0x100001F6` | - | - | SecondaryPowerManager | `0x2017` |
| ?RequestTeamNames | `0x10000485` | - | - | CustomMatchManager, MatchData, PvPLobby, Scorecard | `0x20fd` |

#### `GM_LoginReward` (2)

| call | id | arguments | returns | called by | network event |
|---|---|---|---|---|---|
| QueueLoginReward | `0x1000050B` | - | - | RewardTimeline | - |
| ReadyForLoginRewardSet | `0x1000050A` | - | - | RewardTimeline | - |

#### `GM_MapManager` (8)

| call | id | arguments | returns | called by | network event |
|---|---|---|---|---|---|
| FlashUIToWorldClick | `0x1000047B` | bLeftClick, bPress | - | ArtifactsCollectionRollover, HeroGraph2Display, PlayerInfoListItem, StatusIconContainer | - |
| ReadyForMapData | `0x100001B5` | - | - | MinimappyThing | - |
| SendMiniMapMouseCoords | `0x100002F1` | uX, uY, bOverMinimap | - | MinimapMouseTarget | - |
| SetAlertPingPreppedFromUI | `0x100001E7` | bPrepped | - | MinimappyThing | - |
| SetRetreatPingPreppedFromUI | `0x100001E6` | bPrepped | - | MinimappyThing | - |
| TriggerMiniMapNotice | `0x100001B3` | nX, nY, bOutsideRect, eMessage | - | MinimapMouseTarget | - |
| TriggerPreparedPing | `0x100001E3` | nX, nY, bIsRetreatPing | - | MinimapMouseTarget | - |
| ?InqMapNotes | `0x100001B6` | - | - | MinimappyThing | - |

#### `GM_Options` (102)

| call | id | arguments | returns | called by | network event |
|---|---|---|---|---|---|
| OnApplyOptions | `0x10000479` | - | - | SettingsPanelDialog | - |
| RequestTrainingLessonsReset | `0x100004D3` | - | - | CoachingPane | - |
| SetAspectRatio | `0x1000035F` | uValue | - | GraphicsPaneContents | - |
| SetAudioBinkVolumeOption | `0x100004BD` | uValue | - | AudioPane | - |
| SetAudioCharacterThemeVolumeOption | `0x1000050E` | uValue | - | AudioPane | - |
| SetAudioMasterVolumeOption | `0x10000146` | uValue | - | AudioPane | - |
| SetAudioMusicVolumeOption | `0x10000182` | uValue | - | AudioPane | - |
| SetAudioSFXVolumeOption | `0x1000017C` | uValue | - | AudioPane | - |
| SetAudioVOAnnouncerVolumeOption | `0x1000017D` | uValue | - | AudioPane | - |
| SetAudioVOCharacterVolumeOption | `0x10000181` | uValue | - | AudioPane | - |
| SetAutoAttackOption | `0x100001BC` | bValue | - | GameplayPane | - |
| SetBoolOption | `0x1000013F` | sOption, bValue | - | GameplayPane, GraphicsPaneContents, SettingsManager, UIPaneContents | - |
| SetCharacterOutlineOption | `0x100004C5` | bValue | - | GameplayPane | - |
| SetCinematicDrawDistance | `0x100004E2` | uValue | - | GraphicsPaneContents | - |
| SetCoachingContextualTipsEnabledOption | `0x100004CE` | bValue | - | CoachingPane | - |
| SetCoachingEnabledOption | `0x100004C6` | bValue | - | CoachingPane | - |
| SetCoachingPlayerOverheadTipsEnabledOption | `0x100004CD` | bValue | - | CoachingPane | - |
| SetConstrainCursorOption | `0x10000163` | bValue | - | SettingsPanelDialog, StartMenuDialog | - |
| SetDisplayAdapterOption | `0x100004D1` | uValue | - | GraphicsPaneContents | - |
| SetFloatOption | `0x10000214` | sOption, fValue | - | GameplayPane, GraphicsPaneContents | - |
| SetGraphicsCore | `0x10000305` | uValue | - | GraphicsPaneContents | - |
| SetGraphicsQualityLevel | `0x100002F2` | uValue | - | GraphicsPaneContents | - |
| SetInGameBorderlessWindowOption | `0x100004AB` | bValue | - | GraphicsPaneContents | - |
| SetInGameFullScreenOption | `0x100004B1` | bValue | - | GraphicsPaneContents | - |
| SetInGameResolutionOption | `0x100004AA` | uValue | - | GraphicsPaneContents | - |
| SetInGameWindowedResolutionOption | `0x100004B0` | uValue | - | GraphicsPaneContents | - |
| SetIntOption | `0x1000013D` | sOption, iValue | - | MainHUD, UIPaneContents | - |
| SetOutOfGameBorderlessWindowOption | `0x100004B3` | bValue | - | GraphicsPaneContents | - |
| SetOutOfGameFullScreenOption | `0x100004B4` | bValue | - | GraphicsPaneContents | - |
| SetOutOfGameResolutionOption | `0x100004B6` | uValue | - | GraphicsPaneContents | - |
| SetOutOfGameWindowedResolutionOption | `0x100004B9` | uValue | - | GraphicsPaneContents | - |
| SetSavedUsername | `0x100002F7` | sUsername | - | LoginScreen | - |
| SetSelfCastingOption | `0x100001C7` | bValue | - | GameplayPane | - |
| SetShadowMapQuality | `0x10000307` | uValue | - | GraphicsPaneContents | - |
| SetShowUIFramingFillOption | `0x10000267` | bValue | - | UIPaneContents | - |
| SetSmartCastingOption | `0x10000149` | eValue | - | GameplayPane | - |
| SetSoundQualityLevel | `0x10000507` | uValue | - | AudioPane | - |
| SetTeamIndicator | `0x10000362` | uValue | - | UIPaneContents | - |
| SetTurretWarningEnabled | `0x100004C3` | bValue | - | CoachingPane | - |
| SetUICharPanelGroupScalingOption | `0x10000258` | uValue | - | UIPaneContents | - |
| SetUIConversationGroupScalingOption | `0x100004D8` | uValue | - | UIPaneContents | - |
| SetUIKillCardGroupScalingOption | `0x100003B4` | uValue | - | UIPaneContents | - |
| SetUILetterboxGroupScalingOption | `0x10000266` | uValue | - | UIPaneContents | - |
| SetUIMatchGroupScalingOption | `0x100003B6` | uValue | - | UIPaneContents | - |
| SetUIMinimapGroupScalingOption | `0x10000256` | uValue | - | UIPaneContents | - |
| SetUIPlayerInfoGroupScalingOption | `0x100003AA` | uValue | - | UIPaneContents | - |
| SetUIRecommendedPanelOption | `0x10000428` | bValue | - | UIPaneContents | - |
| SetUIScalesLinkedOption | `0x1000026A` | bValue | - | UIPaneContents | - |
| SetUISelectionPanelGroupScalingOption | `0x100003B2` | uValue | - | UIPaneContents | - |
| SetUISkillsGroupScalingOption | `0x10000259` | uValue | - | UIPaneContents | - |
| SetUITopBarGroupScalingOption | `0x100003BB` | uValue | - | UIPaneContents | - |
| SetUIntOption | `0x1000039C` | sOption, iValue | - | GraphicsPaneContents | - |
| TemporaryFullScreen | `0x100004C2` | bOn | - | LaunchMoviePlayer | - |
| ?GetAspectRatio | `0x10000360` | - | uCurrentValue | GraphicsPaneContents | - |
| ?GetAudioBinkVolumeOption | `0x100004BE` | - | uCurrentValue | AudioPane | - |
| ?GetAudioCharacterThemeVolumeOption | `0x1000050F` | - | uCurrentValue, uMinValue, uMaxValue | AudioPane | - |
| ?GetAudioMasterVolumeOption | `0x10000147` | - | uCurrentValue, uMinValue, uMaxValue | AudioPane | - |
| ?GetAudioMusicVolumeOption | `0x1000017E` | - | uCurrentValue | AudioPane | - |
| ?GetAudioSFXVolumeOption | `0x1000017F` | - | uCurrentValue | AudioPane | - |
| ?GetAudioVOAnnouncerVolumeOption | `0x10000180` | - | uCurrentValue | AudioPane | - |
| ?GetAudioVOCharacterVolumeOption | `0x10000183` | - | uCurrentValue | AudioPane | - |
| ?GetAutoAttackOption | `0x100001BD` | - | bValue | GameplayPane | - |
| ?GetBoolOption | `0x1000013E` | sOption | bValue | GameplayPane, GraphicsPaneContents, SettingsManager, TeamUtils, UIPaneContents | - |
| ?GetCharacterOutlineOption | `0x100004C9` | - | bValue | GameplayPane | - |
| ?GetCinematicDrawDistance | `0x100004E3` | - | uCurrentValue | GraphicsPaneContents | - |
| ?GetCoachingContextualTipsEnabledOption | `0x100004D0` | - | bValue | CoachingPane | - |
| ?GetCoachingEnabledOption | `0x100004C8` | - | bValue | CoachingPane | - |
| ?GetCoachingPlayerOverheadTipsEnabledOption | `0x100004CF` | - | bValue | CoachingPane | - |
| ?GetDisplayAdapterOption | `0x100004D2` | - | uCurrentValue | GraphicsPaneContents | - |
| ?GetFloatOption | `0x10000215` | sOption | fValue | GameplayPane, GraphicsPaneContents | - |
| ?GetGraphicsCore | `0x10000306` | - | uCurrentValue | GraphicsPaneContents | - |
| ?GetGraphicsQualityLevel | `0x100002F3` | - | uCurrentValue | GraphicsPaneContents | - |
| ?GetInGameBorderlessWindowOption | `0x100004AC` | - | bValue | GraphicsPaneContents | - |
| ?GetInGameFullScreenOption | `0x100004AE` | - | bValue | GraphicsPaneContents | - |
| ?GetInGameResolutionOption | `0x100004AD` | - | uCurrentValue | GraphicsPaneContents | - |
| ?GetInGameWindowedResolutionOption | `0x100004AF` | - | uCurrentValue | GraphicsPaneContents | - |
| ?GetIntOption | `0x1000013A` | sOption | iValue | MainHUD, UIPaneContents | - |
| ?GetOutOfGameBorderlessWindowOption | `0x100004BB` | - | bValue | GraphicsPaneContents | - |
| ?GetOutOfGameFullScreenOption | `0x100004BC` | - | bValue | GraphicsPaneContents | - |
| ?GetOutOfGameResolutionOption | `0x100004B8` | - | uCurrentValue | GraphicsPaneContents | - |
| ?GetOutOfGameWindowedResolutionOption | `0x100004B5` | - | uCurrentValue | GraphicsPaneContents | - |
| ?GetSavedUsername | `0x100002F6` | - | sUsername | **never called** | - |
| ?GetSelfCastingOption | `0x100001C8` | - | bValue | GameplayPane | - |
| ?GetShadowMapQuality | `0x10000308` | - | uCurrentValue, bDisabled | GraphicsPaneContents | - |
| ?GetShowUIFramingFillOption | `0x10000269` | - | bValue | MainHUD, UIPaneContents | - |
| ?GetSmartCastingOption | `0x1000014A` | - | eValue | GameplayPane | - |
| ?GetSoundQualityLevel | `0x10000508` | - | uCurrentValue | AudioPane | - |
| ?GetTeamIndicatorInfo | `0x10000363` | - | uCurrentValue | UIPaneContents | - |
| ?GetTurretWarningEnabled | `0x100004C7` | - | bValue | CoachingPane | - |
| ?GetUICharPanelGroupScalingOption | `0x10000257` | - | uCurrentValue | MainHUD, UIPaneContents | - |
| ?GetUIConversationGroupScalingOption | `0x100004D9` | - | uCurrentValue | LobbyWrapper, MainHUD, UIPaneContents | - |
| ?GetUIKillCardGroupScalingOption | `0x100003B5` | - | uCurrentValue | MainHUD, UIPaneContents | - |
| ?GetUILetterboxGroupScalingOption | `0x10000268` | - | uCurrentValue | MainHUD, UIPaneContents | - |
| ?GetUIMatchGroupScalingOption | `0x100003B7` | - | uCurrentValue | MainHUD, UIPaneContents | - |
| ?GetUIMinimapGroupScalingOption | `0x10000254` | - | uCurrentValue | MainHUD, UIPaneContents | - |
| ?GetUIPlayerInfoGroupScalingOption | `0x100003AB` | - | uCurrentValue | MainHUD, UIPaneContents | - |
| ?GetUIRecommendedPanelOption | `0x10000429` | - | bValue | DefeatManager, UIPaneContents | - |
| ?GetUIScalesLinkedOption | `0x1000026B` | - | bValue | UIPaneContents | - |
| ?GetUISelectionPanelGroupScalingOption | `0x100003B3` | - | uCurrentValue | MainHUD, UIPaneContents | - |
| ?GetUISkillsGroupScalingOption | `0x10000255` | - | uCurrentValue | MainHUD, UIPaneContents | - |
| ?GetUITopBarGroupScalingOption | `0x100003BC` | - | uCurrentValue | MainHUD, UIPaneContents | - |
| ?GetUIntOption | `0x1000039D` | sOption | iValue | GraphicsPaneContents, TeamUtils | - |

#### `GM_PlayerReport` (2)

| call | id | arguments | returns | called by | network event |
|---|---|---|---|---|---|
| ReportAPlayer | `0x10000401` | strTargetPlayer, uReportChoice, strAdditionalInfo | - | ReportAPlayerDialog | - |
| ?InqReportAPlayerOptions | `0x10000403` | - | - | ReportAPlayerDialogData | - |

#### `GM_ProfileUI` (1)

| call | id | arguments | returns | called by | network event |
|---|---|---|---|---|---|
| ProfileUI_SelectCharacter | `0x10000438` | didVariant | - | ChampionDetailPanel, VeteranLanding | - |

#### `GM_SelectionSystem` (1)

| call | id | arguments | returns | called by | network event |
|---|---|---|---|---|---|
| ?InqUsableTargets | `0x100000C9` | - | - | **never called** | - |

#### `GM_Skill` (5)

| call | id | arguments | returns | called by | network event |
|---|---|---|---|---|---|
| AbandonBonusSkill | `0x100002C7` | - | - | **never called** | - |
| OnArtifactButtonRollover | `0x10000374` | didArtifact, eSkillSlot, bRollover | - | ArtifactsCollectionActionButtons | - |
| OnSkillRollover | `0x10000223` | eSkillSlot, bRollover | - | SkillControl | - |
| ?InqSkillToolTipInfo | `0x10000164` | didDBPCToLoad, eSkill | siCost, fCost, siCooldown, siDescription, siSkillName, didIcon, iRank, bSkillCanBeActivated, eDamageType | ArtifactActionButton, ChampionDetailPanel, CharacterPreview, DefeatRecommendationsPanel, MatchData, SkillControl, SuperRewardRibbon | - |
| ?RequestStolenPowersForCharacter | `0x1000030F` | iidCharacter | didSecondary1Icon, didSecondary2Icon, strSecondary1Name, strSecondary2Name, strSecondary1Description, strSecondary2Description | MatchData | - |

#### `GM_Sound` (1)

| call | id | arguments | returns | called by | network event |
|---|---|---|---|---|---|
| SetParameterAndPlay | `0x10000202` | eEvent, eParamID, fParamValue | - | PowerGraphCategorizedItemDisplay, RecommendedPowerBar | - |

#### `GM_StatusIcon` (1)

| call | id | arguments | returns | called by | network event |
|---|---|---|---|---|---|
| RequestStatusIcons | `0x100001A5` | - | - | StatusIconDisplay | - |

#### `GM_Tutorial` (1)

| call | id | arguments | returns | called by | network event |
|---|---|---|---|---|---|
| UIReadyForTutorialHints | `0x10000283` | - | - | HintManager | - |

#### `GM_UI` (74)

| call | id | arguments | returns | called by | network event |
|---|---|---|---|---|---|
| AcceptMatch | `0x10000242` | - | - | MatchFoundRibbon | `0x20ca` |
| AcknowledgeMajorUpdateNews | `0x1000052A` | - | - | MajorUpdateDialog | - |
| CanUserCreateGroup | `0x100003B1` | - | - | EncSoloGroupScreen | - |
| CharacterFloatyVitalsAdded | `0x100004E9` | iidEntity | - | OverheadVitalsDeluxe | - |
| ConnectToGameServer | `0x10000040` | - | - | StateMachineHelpers | - |
| CreateAccount | `0x1000029F` | - | - | LoginScreen | - |
| DisplayPendingDodgePenaltyNotifications | `0x1000052C` | - | - | WrapperMain | `0x21a8` |
| DisplaySurvey | `0x100002A0` | - | - | **never called** | - |
| DisplayedTutorialTakeover | `0x10000499` | - | - | NewPlayerScreen | - |
| ExitToMainMenu | `0x100000BB` | - | - | StartMenuDialog | - |
| FloatyVitalsManager_OnLoadComplete | `0x10000032` | - | - | FloatyVitalsManager | - |
| FloatyVitalsManager_OnUnloadComplete | `0x10000079` | - | - | FloatyVitalsManager | - |
| ForceQueue | `0x10000241` | - | - | MatchmakingIndicator | - |
| ForgotPassword | `0x1000029E` | - | - | LoginScreen | - |
| HUDCurtainTransitionComplete | `0x1000015D` | bLoweredCurtain | - | **never called** | - |
| HUDInitialized | `0x1000015C` | - | - | MainHUD | - |
| HUDLoaded | `0x1000046A` | bLoaded | - | MainHUD | - |
| InGameMenuClosed | `0x10000477` | - | - | DialogsManager | - |
| InGameMenuOpened | `0x10000476` | - | - | DialogsManager | - |
| JoinQueue | `0x10000240` | didMatch, bSolo, bDraft, bRanked | - | LandingDemoContents, PVPGroupingInterface, VeteranMap, WrapperMain | `0x20eb` |
| JoinQueueForPromotedMap | `0x10000473` | didMatch | - | TraineeAchievements, WrapperMain | `0x20eb` |
| LeaveQueue | `0x1000023F` | - | - | MatchFoundRibbon, MatchmakingIndicator | `0x20c3` |
| LogError | `0x10000524` | strErrorMsg | - | UIUtils | - |
| OnEndOfMatchMovieEnded | `0x100004DA` | - | - | MovieDialog | - |
| OpenURL | `0x1000048E` | strURLKey | - | ReleaseNotesElement | - |
| PlayerAcknowledgedStandingsChange | `0x10000523` | - | - | RankRibbon | - |
| RankedBanner_SelectCharacter | `0x1000052E` | didVariant | - | AnimatedRankedDisplay | - |
| RequestAccountStandingsData | `0x10000520` | - | - | RankedManager | `0x2178 (probable)` |
| RequestCharacterAdvancementData | `0x100002E7` | - | - | OwnablesManager | - |
| RequestClientLanguage | `0x10000517` | - | - | LanguageManager | - |
| RequestExitGame | `0x10000238` | - | - | HeaderRight, StartMenuDialog | - |
| RequestHeaderUIData | `0x1000025D` | - | - | AccoladeManager, HeaderLeft, ScorecardManager, SelfPresenceDisplay, TraineeAchievements | - |
| RequestItemStatuses | `0x100004F4` | - | - | OwnablesManager | - |
| RequestLeaderboards | `0x10000527` | didEncounter | - | LeaderBoardManager, Ranked | `0x21a4` |
| RequestProtectorAdvancementStatus | `0x10000495` | - | - | WrapperMain | - |
| RequestReleaseNotesURL | `0x10000496` | - | - | ReleaseNotesElement | - |
| RequestStaticStandingsData | `0x10000522` | - | - | RankedManager | `0x2193 (probable)` |
| RewardBanner_SelectCharacter | `0x100004BF` | didVariant | - | SuperRewardRibbon | - |
| Scorecard_LoadCharacterHeavyOnly | `0x100004EC` | didVariant | - | CharLevelUpRibbon, Scorecard | - |
| SetCachedUIValue | `0x1000025B` | iValue | - | **never called** | - |
| SetProtectorAdvancementStatusForSession | `0x1000049C` | eStatus | - | LandingSwitcher | - |
| SetUIState | `0x1000011C` | nUIState | - | **never called** | - |
| SetupSettingsButtons | `0x100003EA` | - | - | **never called** | - |
| ShowCursor | `0x1000049D` | bShow | - | LoginScreen | - |
| ShowHelp | `0x1000029C` | - | - | HeaderRight, StartMenuDialog | - |
| ShowURLDialog | `0x10000265` | strURL | - | **never called** | - |
| SkillButtonPressed | `0x1000012A` | eSlot, bPress | - | ArtifactsCollectionActionButtons, SkillControl, SkillsPanel | - |
| SubmitScreenName | `0x10000230` | strName | - | DisplayNameRequestScreen | `0x2148 (probable: name request)` |
| TakeScreenShot | `0x10000141` | - | - | TopBarLeft | - |
| ToggleMainMenu | `0x1000006D` | - | - | TopBarLeft | - |
| TraceInfoFromFlash | `0x10000294` | text | - | MainHUD | - |
| TrainingFloatyManager_OnLoadComplete | `0x1000049F` | - | - | FloatyVerbsManager | - |
| TrainingFloatyManager_OnUnloadComplete | `0x1000049E` | - | - | FloatyVerbsManager | - |
| UIStateMachineEvent | `0x10000020` | eEvent | - | CustomMatchInterface, EncFeaturedMapScreen, EncGameModeScreen, EncMapSelectionScreen, EncSoloGroupScreen, EncTutorialSelectionScreen, EncounterDetails, GameModeBigButton, HeaderCenter, HeaderProfile, LandingNav, LobbyWrapper, LoginRewards, LoginScreen, MainHUD, MapBigButton, MatchmakingIndicator, NavButtons, NextChallenge, PVPGroupManager, PVPLauncher, PvPLobby, Scorecard, StartMenuDialog, StateMachineHelpers, Store, TraineeAchievements, TutorialBigButton, VeteranLanding, WrapperMain | - |
| UserActionMetric | `0x100004FA` | eAction | - | TraineeAchievements | `0x218c` |
| ?GetChargenError | `0x10000234` | - | sChargenError | DisplayNameRequestScreen | - |
| ?GetConnectionStatus | `0x10000078` | - | sConnectionStatus | **never called** | - |
| ?GetWaitTimeForQueue | `0x100004FE` | didEncounter, bDraft, bRanked | nWaitTime | EncSoloGroupScreen, MapBigButton, MatchmakingIndicator, PVPGroupingInterface | - |
| ?InqAccountMeritBonus | `0x10000503` | - | nQueueBonus, nStreakBonus, siStreakTooltip, siQueueTooltip | MatchmakingIndicator | - |
| ?InqCachedUIValue | `0x1000025C` | - | iValue | **never called** | - |
| ?InqChatButtonTooltip | `0x10000439` | - | siChatTooltip | ChatLauncher | - |
| ?InqCreditsURL | `0x100004E5` | - | strURL | StartMenuDialog | - |
| ?InqDefaultAccountName | `0x1000022C` | - | acctName | DisplayNameRequestScreen, LoginScreen | - |
| ?InqHUDVisibility | `0x10000108` | - | bShown | **never called** | - |
| ?InqQueueEligibility | `0x10000501` | - | bMeetsLevelReq, siLevelReqMsg | EncounterManager | - |
| ?InqRegenRateText | `0x10000279` | - | sText | **never called** | - |
| ?InqRegionDisplayName | `0x10000452` | - | strRegionDisplayName | LoginScreen | - |
| ?InqStoreURL | `0x10000287` | - | strURL | Store | - |
| ?InqUIState | `0x1000011D` | - | nUIState | **never called** | - |
| ?InqWrapperDisplayData | `0x1000049A` | - | strLoginMovie, didLoginBackground, strLandingMovie, didLandingBackground, strLoginRewardMovie, didLoginRewardBackground | LaunchMoviePlayer, WrapperBackground | - |
| ?IsAdmin | `0x10000431` | - | bIsAdmin | NewPlayerScreen | - |
| ?IsBinkFileValid | `0x100004D7` | siFileName | bIsValid | DialogsManager, LaunchMoviePlayer | - |
| ?IsLoggedIntoGame | `0x100003BA` | - | bLoggedIn | SettingsPanelDialog, WrapperMain | - |
| ?NeedsUpdateNews | `0x10000526` | - | bNeedsUpdate, strNewsURL | WrapperMain | - |

#### `GM_Upgrade` (25)

| call | id | arguments | returns | called by | network event |
|---|---|---|---|---|---|
| ActivateItemSlot | `0x100001EF` | nSlotIndex | - | **never called** | - |
| ChangeArtifactSkillSlotMapping | `0x1000042C` | aSkillSlotOrder | - | ArtifactDataManager | - |
| PurchaseUpgrade | `0x10000125` | didUpgrade | - | DefeatRecommendationsPanel, FoundryManager | `0x208b` |
| RequestAllAvailableUpgrades | `0x100001C3` | bShowUpgrades, nGraphEffect | - | **never called** | - |
| RequestArtifactSkillSlotMapping | `0x1000042D` | - | - | ArtifactDataManager | - |
| RequestCurrentUpgrades | `0x10000138` | - | - | FoundryManager | - |
| RequestSendEveryonesUpgrades | `0x100002B0` | - | - | MatchData | - |
| RequestUpgradeArrayPreview | `0x10000278` | didUpgrade | - | FoundryManager | - |
| SellUpgrade | `0x10000144` | didUpgrade, uSlot | - | FoundryManager | `0x20a7` |
| ShowCurrencyCollectionRings | `0x100003FF` | bDisplay | - | UpgradeCurrencyDisplay | - |
| Tutorial_ArtifactFoundryClosed | `0x10000468` | - | - | ArtifactFoundry | - |
| Tutorial_ArtifactFoundryOpened | `0x10000462` | - | - | ArtifactFoundry | - |
| ?InqAvailableUpgrades | `0x10000128` | bShowUpgrades, nGraphEffect | - | **never called** | - |
| ?InqBasePowerGraphValue | `0x10000155` | nGraphEffect | fAmount | **never called** | - |
| ?InqBasePowerGraphValues | `0x10000154` | - | - | HeroGraph | - |
| ?InqBuildOrder | `0x1000014B` | - | - | **never called** | - |
| ?InqCanBuyUpgrade | `0x100002F8` | didUpgrade | eResult | DefeatRecommendationsPanel, FoundryManager | - |
| ?InqCanSellUpgrade | `0x100002F9` | didUpgrade | eResult | FoundryManager | - |
| ?InqNextRecommendedUpgrade | `0x10000271` | - | didUpgrade, bCanBuy | DefeatRecommendationsPanel | - |
| ?InqPurchasedItems | `0x100001F7` | - | - | **never called** | - |
| ?InqRemainingRecommendedUpgrades | `0x100002BD` | - | - | **never called** | - |
| ?InqSellDifferenceByDID | `0x10000384` | didBase, didUpgrade | fCostDifference | PurchasableArtifactWidget | - |
| ?InqSellDifferenceSlot | `0x1000014D` | slotIndex, didUpgrade | fCostDifference | **never called** | - |
| ?InqUpgradeDetails | `0x10000145` | didUpgrade | didSkill, siSkillDescription | **never called** | - |
| ?InqUpgradeFilters | `0x100002D8` | - | - | ArtifactDataManager | - |

#### `GM_ViewMatch` (14)

| call | id | arguments | returns | called by | network event |
|---|---|---|---|---|---|
| CameraGoToAgentClick | `0x100002D6` | iidAgent | - | VMPlayersSinglePlayerDisplay | - |
| DirectedCameraButtonPressed | `0x100002CF` | - | - | ViewMatchControlsBottom | - |
| HideKillCardForViewMatch | `0x10000368` | - | - | **never called** | - |
| LockedCameraButtonPressed | `0x100002CE` | - | - | ViewMatchControlsBottom | - |
| RequestAllPlayersInformation | `0x100002BE` | - | - | **never called** | - |
| RequestCameraInformation | `0x100002C0` | - | - | VMPlayersTeamPanel, ViewMatchControlsBottom | - |
| RequestKillCardInfo | `0x100002DE` | - | - | ViewMatchControlsBottom | - |
| RequestMatchStartCounts | `0x10000490` | - | - | ViewMatchTopCoastCity, ViewMatchTopDivided | - |
| SwitchFOWTeam | `0x100002DC` | - | - | ViewMatchControlsBottom | - |
| ToggleFogOfWar | `0x100002DB` | bEnable | - | ViewMatchControlsBottom | - |
| ?RequestAbleToViewMatch | `0x100004DC` | - | bValue | CustomMatchTeamDisplay | - |
| ?RequestInViewMatchMode | `0x10000237` | - | bValue | AmplifierSetPickerMenu, BillboardManager, CharacterPicker, ControlledAgentDispatcher, DefeatManager, FPSDisplay, KillDisplayManager, LobbyWrapper, MainHUD, MatchData, MatchManager, OwnablesManager, PlayerDisplay, PlayerInfoPanel, PowerPicker, ProtectorIconSubmenu, SkinPicker, TeamDisplay | - |
| ?RequestInViewMatchModeLastMatch | `0x100004DB` | - | bValue | WrapperMain | - |
| ?RequestTeamGhostedAs | `0x10000236` | - | nValue | ControlledAgentDispatcher, MatchManager | - |

#### `GM_Vitals` (3)

| call | id | arguments | returns | called by | network event |
|---|---|---|---|---|---|
| ?InqSecondaryVitalType | `0x10000064` | iid | eVitalType | OverheadVitalsDeluxe, SkillsPanel, VitalsLarge | - |
| ?InqTemporaryVital | `0x10000151` | iid, eVitalType | fCurrentVital, fMaxVital | OverheadVitalsDeluxe, OverheadVitalsSimple, VitalsLarge | - |
| ?InqVital | `0x10000088` | iid, eVitalType | fCurrentVital, fMaxVital | OverheadVitalsDeluxe, OverheadVitalsSimple, SkillsPanel, VitalsLarge | - |
---

## 6. Screen by screen: data, what the server sends, what is unknown

For what `ics` sends today see `client-scripts-and-ui.md` section 3 (not repeated). "S->C" = server -> client
events / notices, "C->S" = what the client sends. Flash names are `System.Notice`; arguments are in section 4.

### 6.1 Out of match (wrapper)

| Screen (movies) | Data the screen consumes (Flash notices) | Server must send (S->C) | Client sends (C->S) | Unknown / notes |
|---|---|---|---|---|
| **Login, connecting, display name** (`6D`, `6C` disconnect, `9E` background, `90` footer) | `ConnectionManager.UpdateConnectionState(nIndex)`, `ShowLoginError`, `Character.MasterCharacterListReceived()`, `UI.ChargenError(strErr)`, `UI.gmWErrorMessageOccurred`, `UI.ReleaseNotesUrl`, `UI.ClientLanguage` | handshake; `0x20ED` (raises `MasterCharacterListReceived`, which `BootupInputHandler` waits for) | `LoginWithWBID`, `ConnectToGameServer`, `CreateAccount`, `ForgotPassword` are client-local (login server / browser); `SubmitScreenName` -> `0x2148` [P] | connection-state values are raised by the client's connection code (`0x2024`/`0x20FF` name matches are noise); `ChargenError` source; release notes URL is a client query |
| **Shell + header + footer** (`75` WrapperMain, `77` header, `90`, `A8` nav) | `UI.ProtectorAdvancementStatus(eStatus, strMovieToPlay)` (chooses trainee vs. veteran layout, 2.5), `UI.SendHeaderNameAndProtectorIcons(name, iconDIDs, names, descs, unlockDescs)`, `Character.SendAccountCurrencyBalance(hard, soft)`, `Character.SendAccountLevelAndXP(level, totalXP, pct, xpToNext)`, `AdminAlert.UI_NotifyAdminAlertsUpdated`, matchmaking (6.3), ribbons (6.6), `UI.DisplayDialogText`, `UI.ShowURLDialog`, `UI.UserCanCreateGroup`, `Lobby.LobbyRejoinRoom` | `0x215D` (protector status [P]), `0x2190`/`0x2154` (header), `0x2081` (currency), `0x2080` (account level/XP), `0x2070`, `0x205B` | `RequestHeaderUIData`, `RequestAccountCurrencyBalance`, `RequestAccountLevelAndXP`, `RequestProtectorAdvancementStatus` (all answered from the cache, 2.3); `0x212E` -> answer `0x211F`; `0x2124` -> answer `0x2125`; `0x20BA` (post-match changes); `0x21A8` | admin alerts feeder; whether `0x215D` alone sets the status (the name matcher also tags `0x2080`, `0x216A`, `0x218B`) |
| **Landing: trainee / new player** (`78`, `74`) | `Achievement.TraineeAchievements(achievements, turntableMovies, clickAction_Queue, clickAction_UITransition, nNumStepsOnRails)`, `Achievement.AchievementDetails`, `SetAchievementData` / `SetAchievementObjectiveData`, `CustomMatch.UI_DeliverCustomMatchData` | `0x2120` (+ `0x21A6`) achievement progress; status Trainee/FirstTimePlayer | `RequestTraineeAchievements`, `RequestAllAchievementData` (`0x211D`), `UserActionMetric` (`0x218C`), `JoinQueue` (`0x20EB`) | **source of `TraineeAchievements`** (no network match; probably built by the client from records + `0x2120` [G]) |
| **Landing: veteran / profile overview** (`A4`) | `Encounter.UI_LastMapPlayed`, `ProfileUI.ProfileUI_HeavyResourcePackData` / `SpecialSecondaryPower` (local, after the pack load), `Character.SendBestChampAccolades` / `SendBestMapAccolades`, achievements, `UI.CharacterAdvancementData` | `0x214B` (last map + completed encounters), `0x2186` (best accolades), `0x209D` | `RequestLastMapPlayed`, `UI_RequestBestAccolades`, `ProfileUI_SelectCharacter`, `RequestStolenPowerList` (`0x2017`) | - |
| **Play flow: mode / map / solo-group / tutorials / details** (`AA`, `A9`) | `Encounter.ResetMapSelectionList`, `UI.QueueEligibility(meetsLevelReq, msg, encounters, rankedEligible, rankedMsgs, draftEligible, draftMsgs)`, `UI.ProtectorAdvancementStatus`; encounter list = query `Encounter.InqPVPEncounters` (local, filled by `0x2024`/`0x218B`) | `0x2024`, `0x218B` (featured), `0x2101` (eligibility), `0x20FF` | `JoinQueue(didMatch, bSolo, bDraft, bRanked)` -> `0x20EB`; `Create_CustomMatch` -> `0x20C1`; `CacheQueueForGrouping`, `GetWaitTimeForQueue` (local) | `0x2101` layout vs. the 7 arguments not checked |
| **Matchmaking / queue** (header `77` `MatchmakingIndicator`, ribbons `6E`) | `UI.JoinedQueue(didEncounter, fWaitTime, fUpdateInterval, fNextUpdate, bAdmin, bRejoin, bTimeout, bGroup)`, `QueueWaitTimesUpdated()`, `Matchmaking_NewUpdateInterval`, `FindMatchFailure(msg, bonus%, tooltip)`, `FoundMatch(nNumAccounts, nTimeout)`, `NumPlayersAcceptedMatch`, `PendingMatchFailure(bTimeout)`, `RemovedFromQueue()`, `BarredFromMatching(nTimeout)` | `0x20C0`, `0x218F`, `0x218E`, `0x218D`, `0x20FA`, `0x20AD`, `0x20D7`/`0x210B`, `0x20E0`, `0x20F3` | `0x20EB` join, `0x20CA` accept, `0x20C3` leave | `QueueWaitTimesUpdated` has no arguments: the times are read later with the query `GetWaitTimeForQueue` (client cache of `0x218F`) |
| **Champion select / lobby** (`67` PvPLobby, `22` picker, `6E` ribbons) | `Lobby.LobbyEncounterDetails` (16 args: teams, players per team, encounter, draft, ranked, custom, my player, my team, admin, map name, required players, tutorial, skips lobby, rejoin, type, diamond minimap), `UpdateLobbyState` (25 arguments, 24 of them parallel arrays), `UpdateLobbyStateSingle`, `PlayerPickedAmplifierSet`, `PlayerPickedStolenPowers`, `UpdateLobbyLoadingPercent`, `UpdateEarlyLaunchTime`, `MatchLaunchWarning`, `PlayerSelectedEarlyLaunchFromServer`, `HideBackButton`, `PreGameTips`, `Draft_*` (5), `CharacterVariantsLoaded` / `HeavyResourcePackLoaded` (local), `UI.AvailableCharacterList`, `UI.ItemStatuses`, `UI.CharacterAdvancementData`, `UI.NotifyHUDElement` / `BatchNotifyHUDElements` (tutorial lobby), `UI.UIStateMachineEvent` | `0x204C`, **`0x2060`** (full state), `0x2029` (one slot), `0x204A`, `0x2004`, `0x2031`, `0x2061`, `0x204B`, `0x206C`, `0x2016`/`0x206D`, `0x2054` (trade request), `0x20B8`, `0x209D`, `0x213D`/`0x213E`, `0x2053` (match starts) | `0x202D` LobbyUIReady, `0x2025` picker info, `0x2102` SelectCharacter, `0x214E`, `0x2108`, `0x206A`, `0x200D` change amplifier set, `0x2057`/`0x2064` my set / my Stolen Powers, `0x200A` exit, `0x201E` tips; local: `PlayerChangedCharacterLockStatus`, `RequestChangeStolenPower` | network source of `PreGameTips` and the 5 `Draft_*` notices (draft mode only); C->S event of `RequestChangeStolenPower` and `PlayerChangedCharacterLockStatus` (lock button) |
| **Loadouts: amplifiers** (`94`, dialogs `80`) | `Amplifier.NotifyListAmplifierSets(total, max, slotIDs, characters, names, icons, entry1..7)`, `NotifyAmplifierSet` (one set, same fields), `NotifyContextualAmplifierData(boutiqueIDs, amplifierDIDs, currencyNames, values)`, `Contextual.PurchaseContextualItemSuccess/Error`, `UI.ItemStatuses` (owned augments = content type 12, mods = 13), `WebTicket.UI_OnWebTicketUpdated` | `0x2090`, `0x20C7`, `0x2052` (error; no Flash listener), `0x2107`, `0x210C`/`0x210D`, `0x20B8` | `UI_SaveAmplifierSet` -> `0x20FC` [P]; `UI_PurchaseContextualItem` (C->S event unknown); queries `UI_InqAugmentData` / `UI_InqModData` / `...PassingFilter` / `UI_InqAmplifierSetIcons` / `SlotInfo` (local, from records + `0x2090`) | contextual purchase C->S event; boutique ids are store strings (preservation: grant directly) |
| **Store** (`7C`, `80` browser dialog) | CEF only: `WebBrowser.On*`, `WebTicket.UI_OnWebTicketUpdated`, `UI_OnMicroTxnAuthorizationResponse` | nothing from the game server; balance `0x2081` after a purchase | `InqStoreURL` (query), `EM_WebTicket.UI_RequestWebTicket` (Steam) | disable the tab or serve a local page |
| **Characters (collection)** (`A5`) | `UI.AvailableCharacterList`, `ItemStatuses` / `Incremental_ItemStatuses(items, statuses, types, owned, counts)`, `CharacterAdvancementData`, `ProfileUI.ProfileUI_AmplifierSetData` / `CharacterVariantsLoaded` / `HeavyResourcePackData` / `SpecialSecondaryPower` (local), best accolades | `0x20B8`, `0x204C` (incremental), `0x209D`, `0x2090`, `0x2186` | `ProfileUI_SelectCharacter` (local pack load), `RequestStolenPowerList` (`0x2017`) | `ProfileUI_AmplifierSetData` per-encounter sets: built by the client from `0x2090` [P] |
| **Profile / calling card** (`A4`, `A0`, `80` calling-card dialog, header) | `SendHeaderNameAndProtectorIcons`, `SendAccountLevelAndXP`, `ProtectorIconManager` (query `RequestProtectorIcons`), ranked standings (6.4) | `0x2190`/`0x2154`, `0x2080`, `0x219E`/`0x219F` | `UI_SetProtectorIcon(didIconWC, index)` -> `0x2093` | - |
| **Achievements** (`A2`) | `Achievement.SetAchievementData(did, name, desc, icon, promo1, promo2, featured, category, visibility, repeat, objectiveType, total, rewardBestowal[], rewardTypes[], rewardIcon, rewardNames[])`, `SetAchievementObjectiveData(did, overall, previous, hasProgress, timeValid, timeInFuture, timesCompleted, objectiveProgress[], lastUpdated)`, `SetDeprecatedAchievements`, `AchievementDetails`, `AllPendingAchivementBanners(achievementIDs)` | `0x2120` (+ `0x21A6`), `0x211F` | `0x211D` all data, `0x212E` banners, `RequestAchievementDetails(did)` / `AcknowledgeAchievementDisplayed(did)` (`0x211E`? [G]) | whether `SetAchievementData` is raised from the records (no network event carries names/descriptions [G]) |
| **Stats** (`A3`) | `Character.SendAccountEncounterStats(encounters, ranked, statLabels, statValues)`, accolades | `0x2115` (answer to `0x2116`), `0x2186` | `0x2116`, `UI_RequestBestAccolades` | - |
| **Friends / contacts / notifications** (`8B`) | `Contacts.UI_NotifyContactList` (18 arrays: IIDs, Steam names, names, group ids/names, notes, type, 5 icons, levels, status, presence, all groups, move-to strings), `...Added/Removed/Ignored/Unignored/PresenceChanged/ChangedGroup/GroupCreated/GroupDestroyed/ChangeNote/ChangeStatusMessage/AccountIconChanged`, invites (`UI_NotifyContactOfInvite(s)`, `PendingInvites`, `UI_ContactListNotification`), self presence/status, group and custom-match invites | `0x203B` [P], `0x2051`, `0x20CC`, `0x2020`, `0x204F`, `0x2018`/`0x20AE`, `0x20CB`, `0x2014`, `0x205E`, `0x208F`, `0x20C5`, `0x20EC`, `0x2003`, `0x2013`, `0x219C`, `0x2065`, `0x203A`, `0x2058`, `0x2033`, `0x214C`, `0x201F`, `0x2027` | `UI_ContactList_Ready`, `UI_InviteContact(name)`, `UI_InviteResponse`, `UI_RemoveContact`, `UI_IgnoreUnignoreContact`, `UI_MoveContactToGroup`, `UI_CreateContactGroup`, `UI_DestroyContactGroup`, `UI_AddNoteToContact`, `UI_AddStatusMessage`, `UI_UpdatePresence`; `ReportAPlayer` | **every Contacts C->S event** (none mapped; candidates `0x2112` invite by name, `0x20CD`); an empty `0x203B` should be enough for a solo server [G] |
| **Party (PvP group)** (`82`) | `Grouping.GroupInformation(groupName, leader, me, encounter, allCanInvite, accountIIDs, names, levels, icons, canInvite, draftEligible, areFriends, inviteNames, inviteAreFriends, inviteStatus)`, `PlayerLeftGroup`, `ShowGroupInviteDialog`, `GroupInviteCanceled`, `UI_Grouping_UpdateProtectorIcon`, `QueueWaitTimesUpdated` | `0x2071` [P], `0x2033`, `0x214C`, `0x217D`, `0x2070` | `RequestGroupInformation`, `LeaveGroup`, `OnGroupPage`, `Chat.RunCmd` (invites are chat commands), `UI_InviteContact` | C->S events of the group calls |
| **Chat** (`83` + ChatManager, `UIWidget_Chat`) | Flash shows only the launcher (`Chat.ToggleUnreadChat`), the general window toggle and the scorecard room list (`Chat.UpdatedMemberList(roomName, members)`); **chat lines are drawn by C++** inside the `UIWidget_Chat` descriptor (`DataCache.LoadChat`) | `0x20B0`/`0x20B6` unread, `0x2135` member list, lines `0xAB`/`0xC9` (see protocol notes) | `0x20A6` channel list, `0x20F6` text (sent by the C++ chat widget, not by Flash); `RunCmd(siCmd)`, `StartPlayerTell(name)` (`0x20CD`? [G]) | line delivery format (outside Flash) |
| **Custom match** (`93`) | `CustomMatch.UI_DeliverCustomMatchData` (21 args: coordinator, me, admin, encounter, draft, perm, participant arrays, invite arrays, draft errors, required players), `UI_CustomMatch_Cancelled/Kicked/Launched/Left`, `SetDraftMode/SetEncounter/SetTeamName/UpdateProtectorIcon`, `Contacts.UI_NotifyContactAdded` | `0x2011`, `0x2041`, `0x2040`, `0x203F`, `0x2103`, `0x2109`, `0x2151`, `0x217C`; room changes `0x2012` `0x2035` `0x2036` `0x2048` `0x205D` `0x2076` `0x202E` `0x2042` have **no Flash listener**: the client rebuilds `UI_DeliverCustomMatchData` from its room cache [P] | `0x2066` request data, `0x20C1` create, `0x20A1` launch, `0x2094` force launch, `0x2199`/`0x219A` kick, `0x219B` move, `0x20F4` randomize, `0x200B` draft, `0x20E6` invite response, `0x20C6` leave; `AssignTeam_CustomMatch`, `ChangeCoordinator_CustomMatch`, `GivePerm_CustomMatch`, `Invite_CustomMatch`, `SetEncounter`, `SetTeamNames` (C->S unmapped; probably the lobby client object slots `0x20D6`... in `protocol-complete.md` [G]) | the 6 unmapped custom-match sends |
| **Ranked, leaderboards** (`B2`, `B0` badges, `AD` scorecard tab) | `UI.UI_DeliverStaticStandingsData` (17 arrays: rank ids, sub-ranks, names, icons, small icons, lore, VO, wallpapers, streak eligibility, loss protection, welcome strings, tiers, tier descriptions, tier min ranks), `UI_DeliverAccountStandingsData` (15: featured / last encounter, per-encounter rank, sub-rank, position, streak, previous values, played, won, won last, banner), `DeliverRegionalLeaderboard` / `DeliverFriendsLeaderboard(accountIIDs, names, ranks, subPips, positions, championDIDs, title, myAccount)` | `0x219E`/`0x219F` (which is which: open), `0x21A2`/`0x21A3` | `0x2178` / `0x2193` [P], `0x21A4` leaderboards, `PlayerAcknowledgedStandingsChange`, `RankedBanner_SelectCharacter` (local) | static vs. account standings event assignment |
| **Rewards, login rewards, ribbons** (`B1`, `6E`, wrapper) | `LoginReward.UI_DeliverLoginRewardSet` (14 args), `UI_NoEligibleLoginReward`, `Character.RewardSetsData` (11 arrays), `Ribbon_ItemFulfilled` / `Ribbon_FinishedItemsFulfilled` / `Ribbon_CharacterLevelChanged`, `UI.PendingMatchFailure`, `Achievement.AllPendingAchivementBanners` | `0x2197` or `0x219D` (the screen waits for one of them), `0x2125`, `0x2095`, `0x2104`, `0x211F` | `ReadyForLoginRewardSet`, `QueueLoginReward` (C->S unknown), `0x2124`, `0x2128` claim (`UI_ClaimPostMatchReward(didReward, didChoice)`), `Ribbon_ReceivedItemsFulfilled` | login-reward C->S events; which of `0x2125`/`0x2197` feeds `RewardSetsData` |
| **Settings, key bindings** (`5F`, `9F` FPS) | `KeyBinding.UI_KeyBindingData` / `UI_UpdateKeyBinding`, `Options.*FullScreenOptionChanged`, `Camera.CameraLockedPreference`, `EM_Sound.AudioQualityChanged`, `EM_UI.GraphicsQualityChanged`, `UI.FPSUpdate` | none (all local); `0x216A` server preferences only seeds them | `Options.Set*` (50 setters; `GM_Options` has 105 functions, all local), `RequestTrainingLessonsReset`; user preference save `0x216E`; camera lock `0x213A` | - |

### 6.2 In match (HUD)

| Element (movies) | Data (Flash notices / properties) | Server must send | Client sends | Unknown / notes |
|---|---|---|---|---|
| **HUD root, curtains, visibility** (`MainHUD`, `5C` top bar, `0D` Esc menu) | `UI.NotifyHUDElement(element, event, highlight, didHighlightArtifact, title, message)` / `BatchNotifyHUDElements` (ids: section 8 `gmUIHUDElementIDList`, `gmUIHUDElementEventList`, `gmUIHUDHighlightIDList`), `UI.UpdateHUDVisibility`, `UI.UIStateMachineEvent` (curtain), `UI.ToggleMainMenu`, `UI.HideToViewMatchLayout`, `Character.StopProcessingNewBillboards` | `0x213D`/`0x213E`, `0x20F5`/`0x2150`, notice `0x100002BC` | `HUDLoaded`, `HUDInitialized` (local); load complete `0x1000015E`; HUD ready `0x100000D2` [P] | - |
| **Vitals, floaties** (`2B`, `06`, `10`, `AB`) | `Vitals.VitalsChanged(iid, type, old/new current, old/new max, temp, damage arrays, flags)` (keyed on the entity), `DOTUpdate`, `VOTUpdate`, `DisplayFloatyStatus(iid, eStatus)`, `Advancement.XPGained(iid, n)`, `Upgrade.DisplayFloatyCurrencyChanged/Denied`, `UI_ShowFloatyCurrencyOverEntity`, `UI.UpdateFloatyVitalArray`, `FadeFloatyVitals`, `Character.UpdateRegenValues`; properties `PVP_Team`, `Level`, `Name`, `Character_ControllableAgentToPlayer_InstanceID` | `0x42` (vitals), `0x44` / `0x208D` / `0x20BD` (status floaty), properties, `0x2171`-`0x2173` (training floaty text) | `CharacterFloatyVitalsAdded(iid)` (local) | XPGained / currency floaties are raised by the client from property deltas [P] |
| **Skill bar** (`56`, `84`) | `Skill.UI_SkillUpdate(slot, cost, cooldown, description, name, icon, rank, canActivate, damageType, canRank, recommended, inBase, grid columns...)` (local, from the skill records and properties), `EnableSkillButton`, `UpdateSkillUIOverlay` (IID), `UI_NotifyVitalChange`, `UI_NotifySkillButtonUpdateIsSuppressed`, `UI.StartSkillCooldown(slot, time)`, `ExecuteSkillError(slot, error, x, y)`, `Update/RemoveSkillStackCountString`, `Advancement.SkillRanked`; queries `InqSkillRank`, `InqCanRankSkill`, `InqSkillPointsAvailableString`, `InqNextRecommendedSkillToRank`, `InqXPForLevel`, `InqLevelCap` (answered by the WLib handlers, `client-scripts-and-ui.md` 1.7) | properties (ranks `0x100000AF`, `SkillPoints`), `0x20F8` cooldown, `0x207B`/`0x20A0`/`0x2187` enable, `0x2091`/notice `0x1000015A` overlay, `0x208C`, `0x2092`/`0x20DC` errors, `0x20A2`/`0x20A8`/`0x20C8`/`0x20E9` stacks; **`0x9F 0x81A1000B`** to register the advancement handlers | `RankSkill(iidAgent, eSkill)` -> `0x9F 0x81910003` (unpatched) / `0x2136` (patched); `SkillButtonPressed`, `OnSkillRollover` (local) | - |
| **XP bar** (`11`) | properties `XP`, `Level`, `SkillPoints` of the controlled agent; thresholds from `InqXPForLevel` | properties | - | - |
| **Status icons** (`63`) | `StatusIcon.Add/BatchAdd/Remove/Update/UpdateTooltip` keyed on the agent | `0x20A2`/`0x20C8` add, `0x20A8` update, `0x20E9` remove, `0x20D0`/`0x2127` tooltip [P, name match] | - | `BatchAddStatusIcon` source |
| **Objectives** (`64`) | 16 `Encounter.UI_*Objective*` notices (add, deliver current, categories, remove, enable tracker, state, banner text, count, countdown, max, progress %, team relationship, text, timer) | `0x2034` categories, `0x2009` (flag-driven objective update), `0x2023` category state, `0x2075` tracker enable | `ReadyForObjectives` (local) | which `0x2009` flags raise `BannerText` / `CountDown` / `ProgressPercent` / `TeamRelationship` / `Text` / `TimerDuration` |
| **Timeline / event timer** (`65`) | `Encounter.UI_MissionEvent_StartTimeline`, `AddTimelineEvent`, `BatchAddTimelineEvent`, `RemoveTimelineEvent`, `AddTimelineBanner`, `RemoveTimelineBanner` | notices `0x100002AF`/`0x100002B1`, `0x10000424` (after `0x100002AD`) [P] | `UI_ReadyForTimelineData(iid)` -> notice `0x100002AD` | mapping of the 3 network notices onto the 6 Flash notices |
| **Match bar, team health, sector trackers** (`0C`, `A1` spectator) | `Encounter.SetMatchTime(iid, start, end, preStart)`, `UI_InitialTeamHealthUpdate` / `UI_UpdateTeamHealth(iid, teams, values)`, `NotifyMatchEnded`, `UI_UpdateTrackerStatus` / `UI_BatchUpdateTrackerStatus`, `UI.TimerClockSync`; property `PVP_Team` | notices `0x10000109`, `0x100004FB`, `0x10000134`, `0x1000000E`, `0x10000076`; `0x2069` trackers (all to the player object, 2.2) | `RequestCurrentTeamHealth(iid)` -> notice `0x10000137`; `RequestSectorObjectiveState` (local?) | `UI_BatchUpdateTrackerStatus` source |
| **Minimap, pings** (`0F`) | `MapManager.DeliverMapData(didMapImage)`, `AddMapNotes(entities, pos, icon, team, z, category, decoration)`, `UpdateMapNotes`, `UpdateMapNotesDecorations`, `RemoveMapNote`, `AddStaticMapNote`, `MapNote_UnderAttack`, `SetPingPrepped`, `ShowMiniMapTargetingRing`, `UI_Start/StopTeleportEffects`, `ToggleMiniMap` | mostly client-local (map notes follow the visible entities); `0x2137` remove, `0x209F`/`0x217F`/`0x2180` ring, `0x2189`/`0x218A` teleport [P] | `ReadyForMapData`, `TriggerPreparedPing`, `TriggerMiniMapNotice`, `SendMiniMapMouseCoords`, `FlashUIToWorldClick` (local; pings may produce a network event, not traced) | ping network event |
| **Billboards, kill feed, kill card** (`15`, `5B`, `6F`) | `Character.ShowAnnouncement(iid, text, type, srcIcon, tgtIcon, srcTeam, tgtTeam, useTargetColour)` / `ClearAnnouncement`, `Encounter.UI_PlayerJoined/Left`, `Character.NotifyPlayerDied` (kill feed), `UI_ShowKillCard` / `HideKillCard` (kill card; data via `KillCardData`) | notices `0x100002EB`, `0x100002EC`, `0x100000CB`, `0x100000CE` (to the player object) | - | sources of `NotifyPlayerDied` and `UI_ShowKillCard` (probably the client's death handling after the defeat notices [P]) |
| **Defeat / respawn, recommendations** (`13`) | `UI.DefeatStatusUpdated(iid, lifeState, nextStateTime)`, `DefeatStatusUpdatedForEntity`, `Upgrade.UpdateNextRecommendedUpgrade(did, canBuy)`, `Encounter.UI_UpdateHasBaseAccess` / `HasVendorAccess` | notices `0x10000090`, `0x100000BC`, `0x100000BA` (pause), `0x2078` | `UI_ReadyForDefeatStatus` (local), `RankSkill` / `PurchaseUpgrade` from the panel | base / vendor access source (client region check [P]) |
| **Currency, artifact foundry (shop), hero graph** (`57`, `87`, `84`, `5E`) | property `Upgrade_Currency`; `Upgrade.UpdateCurrentUpgrades(iidAgent, upgrades, icons, stack sizes, mods, mod overlays)`, `UpdatePowerGraphValues(iidAgent, amounts)`, `ReturnedUpgradeArrayPreview`, `ActivatedArtifacts`, `SetUIArtifactSkillSlotMapping`, `UI_RefreshPurchasability`, `UpdateNextRecommendedUpgrade`, `Encounter.UI_UpdateHasVendorAccess`; catalogue = queries `GM_Artifact.Inq*` (local records) | property, `0x20E2` (both upgrade notices), `0x2078`, `0x2086` | `PurchaseUpgrade(did)` -> `0x208B`, `SellUpgrade(did, slot)` -> `0x20A7`; `RequestCurrentUpgrades`, `RequestUpgradeArrayPreview`, `ChangeArtifactSkillSlotMapping`, `RequestSendEveryonesUpgrades` (local / unmapped) | whether `RequestSendEveryonesUpgrades` (scoreboard) needs the server |
| **Character / selection / player-info panels** (`5A`, `8A` missing, `62`) | `Character.UpdateCharacterPanelInfo` (IID), queries `InqCharacterPanelInfo` / `MetaData` / `InqCharacterSkills`, `SelectionSystem.Found/Lost/Update/ClearTrackedEntity`, `MatchData` (participants) | properties of the agents; `Encounter.AddParticipant` is client-side when the player/agent objects exist [P] | - | - |
| **Conversation, hints, highlight tips** (`9A`, `70`, `99`) | `Dialog.ShowConversationSlot(slot, image, movie, name, text, noDelay, cannotSkip)`, `HideConversationSlot`, `HideAllConversationSlots`, `HighlightConversationAdvanceButton`; `Tutorial.UI_ShowTutorialHint(hintID, icon, header, short, full, tooltipGraphic, forceOpen)`, `UI_ShowTutorialHints`, `UI_CloseTutorialHint`; HUD highlights via `NotifyHUDElement` | `0x2001` (conversation), notice `0x1000027F` (+ `0x10000288`, `0x100004A5` [P]), `0x213D` | `UI_ReadyForConversation`, `UI_SkipConversation`, `UIReadyForTutorialHints`, `UI_Mission_RaiseEvent(eClientMissionEvent)` (section 8: foundry opened/closed, lobby ready, Stolen Power chosen...) - C->S event not traced | `UI_Mission_RaiseEvent` route (needed by tutorial scripts that wait on lobby / foundry steps) |
| **In-match scoreboard (Tab)** | `Encounter.UI_UpdateMatchScorecard(IIDs, playerIIDs, DIDs, names, isBot, isIgnored, levels, teams, kills, deaths, assists, money, yourIID, yourTeam)`, `ViewMatch.ViewMatchScoreboardData` | **unknown**: no network match; candidate notice `0x1000005B` (old note) [G] | `RequestMatchScorecard` (no network event found) | open |
| **Surrender** (`9C`) | `Encounter.UpdateSurrenderData`, `SurrenderVoteConcluded` (player key) | notices `0x10000455`, `0x10000456` | `SurrenderResponse(iid, bSurrendered)` -> notice `0x10000454` | - |
| **Spectator** (`86`, `A1`) | `ViewMatch.*` (camera, FOW, skill use, scoreboard, dampener / turret counts) | `0x215C`, `0x206D` (not needed for preservation play) | - | - |

### 6.3 End of match

| Screen (movies) | Data | Server must send | Client sends | Unknown |
|---|---|---|---|---|
| **Victory / defeat, transition** (`15`, `0C`) | `Encounter.NotifyMatchEnded(iid, winningTeam, playerTeam, duration, tier, targetTime)`, billboard `WinLossBillboard` | notice `0x1000000E` (to the player), then `0x2038` (UI event `MatchEnded`) | - | - |
| **Scorecard: summary / stats / accolades** (`8C`, `9D`, `AD`, `AE`, `80`) | `ScorecardManager`: `Encounter.UI_SendEndOfMatchStats` (42 args: per-player arrays, grid labels, 10 player value columns, team sums, your IID/team, duration, winner, encounter, ranked), `UI_SetEndOfMatchStatsHeader(iconDIDs, tooltips)`, `PlayEndOfMatchEncounterMovie`, `Character.SendAccountEndOfMatchLevelAndXP`, `...CharacterLevelAndXP`, `...SoftCurrencyReward`, `...AccoladesEarned`, `SendAccountCurrencyBalance`, `UI.SendHeaderNameAndProtectorIcons`, `Upgrade.UpdateCurrentUpgrades` / `UpdatePowerGraphValues`, ranked standings, `Chat.UpdatedMemberList`, `UI.Scorecard_HeavyOnlyLoaded` (local) | `0x2045`, `0x2080`, `0x2104`, `0x20B9`, `0x2188`, `0x2081`, `0x2190`, `0x20E2`, `0x219E`/`0x219F`, `0x2135`; rewards `0x2125`, `0x2095`, `0x211F` | `RequestPostMatchScorecard`, `RequestAccountEndOfMatch*` (cache), `OnScorecard`, `Scorecard_LoadCharacterHeavyOnly` (local), `UI_ClaimPostMatchReward` -> `0x2128`; exit = UI state machine (`TransitionExitScorecard`) then `0x2021` | `SendAccountCharacterLevelAndXP` and `SendAccountCurrencyBalanceChanges` have no listener; `0x2028` is tagged as the stats header by name only |
---

## 7. Per-movie appendix

Every dumped movie: the notices its classes listen to (with the source in brackets when known; `n:` = network
notice) and the Flash -> C++ calls they make (with the network event). Computed from the class closure of 3.0, so the
wrapper screens inherit the shared machinery of `WrapperScreen` / `WrapperMain` (requests for header, currency,
pending rewards, queue) and the HUD elements inherit `MainHUD`'s. `UI.ExitingWorld` (every singleton) and
`EM_Sound.Play` are left out.

| DID | stream offset | role | linked classes | C++ -> Flash notices (feeder events in brackets) | Flash -> C++ calls (network event in brackets) |
|---|---|---|---|---|---|
| `0x20000000` | `0206b4f0` | shared library (imports font lib 0x20000003) | 15 | UI.ForceOnSized | - |
| `0x20000001` | `0206e544` | shared widget target | 1 | - | - |
| `0x20000002` | `0206ea30` | shared library (imports 0x20000008) | 0 | - | - |
| `0x20000004` | `02074ae4` | shared images | 0 | - | - |
| `0x20000006` | `02075470` | HUD: overhead vitals + floaty damage/XP/currency/status | 16 | Advancement.XPGained; Character.ActiveAgentControlledByThePlayerChanged; Character.AgentControlledByThePlayerChanged; Character.StopProcessingNewBillboards [n:0x100002bc]; Character.UpdateCharacterPanelInfo; Encounter.NotifyMatchEnded [n:0x1000000e]; MapManager.ToggleMiniMap; UI.ActionEnumEvent; UI.BatchNotifyHUDElements [0x213e]; UI.DisplayDialogText [0x2087 0x20ed 0x210a 0x210b]; UI.HideToViewMatchLayout; UI.NotifyHUDElement [0x213d]; UI.ToggleMainMenu; UI.UIStateMachineEvent [0x2038 0x2053]; UI.UpdateHUDVisibility [0x20f5 0x2150]; Upgrade.DisplayFloatyCurrencyChanged; Upgrade.DisplayFloatyCurrencyDenied; Upgrade.UI_ShowFloatyCurrencyOverEntity; Vitals.DOTUpdate; Vitals.DisplayFloatyStatus [0x0044 0x208d 0x20bd]; Vitals.VOTUpdate; Vitals.VitalsChanged [0x0042] | GM_Character.?InqCharacterPanelInfo; GM_Character.?InqCharacterPanelMetaData; GM_Chat.ShowChatWindow; GM_Encounter.?InqEncounterIdentifierType; GM_Options.SetIntOption; GM_Options.?GetIntOption; GM_Options.?GetShowUIFramingFillOption; GM_Options.?GetUICharPanelGroupScalingOption; GM_Options.?GetUIConversationGroupScalingOption; GM_Options.?GetUIKillCardGroupScalingOption; GM_Options.?GetUILetterboxGroupScalingOption; GM_Options.?GetUIMatchGroupScalingOption; GM_Options.?GetUIMinimapGroupScalingOption; GM_Options.?GetUIPlayerInfoGroupScalingOption; GM_Options.?GetUISelectionPanelGroupScalingOption; GM_Options.?GetUISkillsGroupScalingOption; GM_Options.?GetUITopBarGroupScalingOption; GM_UI.CharacterFloatyVitalsAdded; GM_UI.HUDInitialized; GM_UI.HUDLoaded; GM_UI.TraceInfoFromFlash; GM_UI.UIStateMachineEvent; GM_ViewMatch.?RequestInViewMatchMode; GM_ViewMatch.?RequestTeamGhostedAs; GM_Vitals.?InqSecondaryVitalType; GM_Vitals.?InqTemporaryVital; GM_Vitals.?InqVital |
| `0x20000007` | `02088a24` | animation utilities | 3 | - | - |
| `0x2000000c` | `02101ce0` | HUD: match bar (team health, timer, score, sector objectives) | 15 | Character.ActiveAgentControlledByThePlayerChanged; Character.AgentControlledByThePlayerChanged; Character.StopProcessingNewBillboards [n:0x100002bc]; Character.UpdateCharacterPanelInfo; Encounter.AddParticipant [local: raised when player/agent objects are created (probable)]; Encounter.NotifyMatchEnded [n:0x1000000e]; Encounter.RemoveParticipant [local: object destroyed (probable)]; Encounter.SetMatchTime [n:0x10000109]; Encounter.UI_BatchUpdateTrackerStatus; Encounter.UI_InitialTeamHealthUpdate [n:0x100004fb]; Encounter.UI_MissionEvent_AddTimelineBanner; Encounter.UI_MissionEvent_AddTimelineEvent; Encounter.UI_MissionEvent_BatchAddTimelineEvent; Encounter.UI_MissionEvent_RemoveTimelineBanner; Encounter.UI_MissionEvent_RemoveTimelineEvent; Encounter.UI_MissionEvent_StartTimeline; Encounter.UI_UpdateMatchScorecard; Encounter.UI_UpdateTeamHealth [n:0x10000134]; Encounter.UI_UpdateTrackerStatus [0x2069]; Lobby.ClearLightResourcePackReferences [0x2021 0x2028 0x204b 0x206c]; MapManager.ToggleMiniMap; UI.ActionEnumEvent; UI.BatchNotifyHUDElements [0x213e]; UI.DefeatStatusUpdatedForEntity [n:0x100000bc]; UI.DisplayDialogText [0x2087 0x20ed 0x210a 0x210b]; UI.HideToViewMatchLayout; UI.NotifyHUDElement [0x213d]; UI.ToggleMainMenu; UI.UIStateMachineEvent [0x2038 0x2053]; UI.UpdateHUDVisibility [0x20f5 0x2150]; UI.gmWErrorMessageOccurred; Upgrade.UpdateCurrentUpgrades [0x20e2]; Upgrade.UpdatePowerGraphValues [0x20e2]; ViewMatch.ViewMatchScoreboardData | GM_Character.?InqCharacterPanelInfo; GM_Character.?InqCharacterPanelMetaData; GM_Chat.ShowChatWindow; GM_Encounter.RequestCurrentTeamHealth [notice 0x10000137]; GM_Encounter.RequestMatchScorecard; GM_Encounter.UI_ReadyForDefeatStatus; GM_Encounter.UI_ReadyForTimelineData [notice 0x100002ad]; GM_Encounter.?InqEncounterIdentifierType; GM_Encounter.?InqMatchTimes; GM_Encounter.?UI_InqSectorObjectives; GM_Lobby.?RequestTeamNames [0x20fd]; GM_Options.SetIntOption; GM_Options.?GetIntOption; GM_Options.?GetShowUIFramingFillOption; GM_Options.?GetUICharPanelGroupScalingOption; GM_Options.?GetUIConversationGroupScalingOption; GM_Options.?GetUIKillCardGroupScalingOption; GM_Options.?GetUILetterboxGroupScalingOption; GM_Options.?GetUIMatchGroupScalingOption; GM_Options.?GetUIMinimapGroupScalingOption; GM_Options.?GetUIPlayerInfoGroupScalingOption; GM_Options.?GetUISelectionPanelGroupScalingOption; GM_Options.?GetUISkillsGroupScalingOption; GM_Options.?GetUITopBarGroupScalingOption; GM_Skill.?InqSkillToolTipInfo; GM_Skill.?RequestStolenPowersForCharacter; GM_UI.HUDInitialized; GM_UI.HUDLoaded; GM_UI.TraceInfoFromFlash; GM_UI.UIStateMachineEvent; GM_Upgrade.RequestSendEveryonesUpgrades; GM_ViewMatch.?RequestInViewMatchMode; GM_ViewMatch.?RequestTeamGhostedAs |
| `0x2000000d` | `021103bc` | in-game start menu (Esc) | 2 | - | GM_Encounter.SurrenderResponse [notice 0x10000454]; GM_Options.SetConstrainCursorOption; GM_UI.ExitToMainMenu; GM_UI.InGameMenuClosed; GM_UI.InGameMenuOpened; GM_UI.RequestExitGame; GM_UI.ShowHelp; GM_UI.UIStateMachineEvent; GM_UI.?InqCreditsURL; GM_UI.?IsBinkFileValid |
| `0x2000000f` | `0211b06c` | HUD: minimap + map notes / pings | 8 | Character.ActiveAgentControlledByThePlayerChanged; Character.AgentControlledByThePlayerChanged; Character.UpdateCharacterPanelInfo; Encounter.UI_BatchUpdateTrackerStatus; Encounter.UI_UpdateTrackerStatus [0x2069]; MapManager.AddMapNotes; MapManager.AddStaticMapNote; MapManager.DeliverMapData; MapManager.MapNote_UnderAttack; MapManager.RemoveMapNote [0x2137]; MapManager.SetPingPrepped; MapManager.ShowMiniMapTargetingRing [0x209f 0x217f 0x2180]; MapManager.UI_StartTeleportEffects [0x2189 0x218a]; MapManager.UI_StopTeleportEffects [0x2189 0x218a]; MapManager.UpdateMapNotes; MapManager.UpdateMapNotesDecorations; UI.ActionEnumEvent | GM_Character.?InqCharacterPanelInfo; GM_Character.?InqCharacterPanelMetaData; GM_Encounter.RequestSectorObjectiveState; GM_MapManager.ReadyForMapData; GM_MapManager.SendMiniMapMouseCoords; GM_MapManager.SetAlertPingPreppedFromUI; GM_MapManager.SetRetreatPingPreppedFromUI; GM_MapManager.TriggerMiniMapNotice; GM_MapManager.TriggerPreparedPing; GM_MapManager.?InqMapNotes; GM_ViewMatch.?RequestInViewMatchMode; GM_ViewMatch.?RequestTeamGhostedAs |
| `0x20000010` | `0212e9f4` | HUD: floaty vitals/verbs managers | 2 | Advancement.XPGained; Character.ActiveAgentControlledByThePlayerChanged; Character.AgentControlledByThePlayerChanged; Character.StopProcessingNewBillboards [n:0x100002bc]; Character.UpdateCharacterPanelInfo; Encounter.NotifyMatchEnded [n:0x1000000e]; MapManager.ToggleMiniMap; UI.ActionEnumEvent; UI.BatchNotifyHUDElements [0x213e]; UI.DisplayDialogText [0x2087 0x20ed 0x210a 0x210b]; UI.FadeFloatyVitals; UI.HideToViewMatchLayout; UI.NotifyHUDElement [0x213d]; UI.ToggleMainMenu; UI.UIStateMachineEvent [0x2038 0x2053]; UI.UpdateFloatyVitalArray; UI.UpdateHUDVisibility [0x20f5 0x2150]; UI.UpdateTrainingFloatyText [0x2171 0x2172 0x2173]; Upgrade.DisplayFloatyCurrencyChanged; Upgrade.DisplayFloatyCurrencyDenied; Upgrade.UI_ShowFloatyCurrencyOverEntity; Vitals.DOTUpdate; Vitals.DisplayFloatyStatus [0x0044 0x208d 0x20bd]; Vitals.VOTUpdate; Vitals.VitalsChanged [0x0042] | GM_Character.?InqCharacterPanelInfo; GM_Character.?InqCharacterPanelMetaData; GM_Chat.ShowChatWindow; GM_Encounter.?InqEncounterIdentifierType; GM_Encounter.?IsLoginEncounterPVP; GM_Options.SetIntOption; GM_Options.?GetIntOption; GM_Options.?GetShowUIFramingFillOption; GM_Options.?GetUICharPanelGroupScalingOption; GM_Options.?GetUIConversationGroupScalingOption; GM_Options.?GetUIKillCardGroupScalingOption; GM_Options.?GetUILetterboxGroupScalingOption; GM_Options.?GetUIMatchGroupScalingOption; GM_Options.?GetUIMinimapGroupScalingOption; GM_Options.?GetUIPlayerInfoGroupScalingOption; GM_Options.?GetUISelectionPanelGroupScalingOption; GM_Options.?GetUISkillsGroupScalingOption; GM_Options.?GetUITopBarGroupScalingOption; GM_UI.CharacterFloatyVitalsAdded; GM_UI.FloatyVitalsManager_OnLoadComplete; GM_UI.FloatyVitalsManager_OnUnloadComplete; GM_UI.HUDInitialized; GM_UI.HUDLoaded; GM_UI.TraceInfoFromFlash; GM_UI.TrainingFloatyManager_OnLoadComplete; GM_UI.TrainingFloatyManager_OnUnloadComplete; GM_UI.UIStateMachineEvent; GM_ViewMatch.?RequestInViewMatchMode; GM_ViewMatch.?RequestTeamGhostedAs; GM_Vitals.?InqSecondaryVitalType; GM_Vitals.?InqTemporaryVital; GM_Vitals.?InqVital |
| `0x20000011` | `021336ac` | HUD: experience bar | 7 | Character.ActiveAgentControlledByThePlayerChanged; Character.AgentControlledByThePlayerChanged; Character.UpdateCharacterPanelInfo | GM_Advancement.ShowExperienceRings; GM_Advancement.?InqLevelCap; GM_Advancement.?InqXPForLevel; GM_Character.?InqCharacterPanelInfo; GM_Character.?InqCharacterPanelMetaData; GM_ViewMatch.?RequestInViewMatchMode; GM_ViewMatch.?RequestTeamGhostedAs |
| `0x20000013` | `0213ed14` | HUD: defeat (death/respawn panel, recommendations) | 13 | Advancement.SkillRanked; Character.ActiveAgentControlledByThePlayerChanged; Character.AgentControlledByThePlayerChanged; Character.HideKillCard; Character.StopProcessingNewBillboards [n:0x100002bc]; Character.UI_ShowKillCard; Character.UpdateCharacterPanelInfo; Encounter.AddParticipant [local: raised when player/agent objects are created (probable)]; Encounter.NotifyMatchEnded [n:0x1000000e]; Encounter.RemoveParticipant [local: object destroyed (probable)]; Encounter.UI_UpdateHasBaseAccess; Encounter.UI_UpdateHasVendorAccess; Encounter.UI_UpdateMatchScorecard; MapManager.ToggleMiniMap; Skill.EnableSkillButton [0x207b 0x20a0 0x2187]; Skill.UI_SkillUpdate; Skill.UpdateSkillUIOverlay [0x2091 n:0x1000015a]; UI.ActionEnumEvent; UI.BatchNotifyHUDElements [0x213e]; UI.DefeatStatusUpdated [n:0x10000090]; UI.DefeatStatusUpdatedForEntity [n:0x100000bc]; UI.DisplayDialogText [0x2087 0x20ed 0x210a 0x210b]; UI.ExecuteSkillError [0x2092 0x20dc]; UI.HideToViewMatchLayout; UI.NotifyHUDElement [0x213d]; UI.StartSkillCooldown [0x20f8]; UI.ToggleMainMenu; UI.UIStateMachineEvent [0x2038 0x2053]; UI.UpdateHUDVisibility [0x20f5 0x2150]; UI.UpdateSkillStackCountString [0x20a2 0x20a8 0x20c8]; UI.gmWErrorMessageOccurred; Upgrade.SetUIArtifactSkillSlotMapping; Upgrade.UpdateCurrentUpgrades [0x20e2]; Upgrade.UpdateNextRecommendedUpgrade [0x2078]; Upgrade.UpdatePowerGraphValues [0x20e2]; ViewMatch.ViewMatchScoreboardData | GM_Advancement.RankSkill [0x2136]; GM_Advancement.?InqCanRankSkill; GM_Advancement.?InqNextRecommendedSkillToRank; GM_Advancement.?InqSkillPointsAvailableString; GM_Artifact.?InqArtifactDetails; GM_Artifact.?InqAvailableArtifacts; GM_Artifact.?InqKillCardArtifactTooltip; GM_Artifact.?InqRecommendedArtifacts; GM_Artifact.?InqRemainingRecommendedArtifacts; GM_Character.?InqCharacterPanelInfo; GM_Character.?InqCharacterPanelMetaData; GM_Chat.ShowChatWindow; GM_Encounter.RequestMatchScorecard; GM_Encounter.?InqCharacterCanShop; GM_Encounter.?InqEncounterIdentifierType; GM_Lobby.?RequestTeamNames [0x20fd]; GM_Options.SetIntOption; GM_Options.?GetIntOption; GM_Options.?GetShowUIFramingFillOption; GM_Options.?GetUICharPanelGroupScalingOption; GM_Options.?GetUIConversationGroupScalingOption; GM_Options.?GetUIKillCardGroupScalingOption; GM_Options.?GetUILetterboxGroupScalingOption; GM_Options.?GetUIMatchGroupScalingOption; GM_Options.?GetUIMinimapGroupScalingOption; GM_Options.?GetUIPlayerInfoGroupScalingOption; GM_Options.?GetUIRecommendedPanelOption; GM_Options.?GetUISelectionPanelGroupScalingOption; GM_Options.?GetUISkillsGroupScalingOption; GM_Options.?GetUITopBarGroupScalingOption; GM_Skill.OnArtifactButtonRollover; GM_Skill.?InqSkillToolTipInfo; GM_Skill.?RequestStolenPowersForCharacter; GM_UI.HUDInitialized; GM_UI.HUDLoaded; GM_UI.SkillButtonPressed; GM_UI.TraceInfoFromFlash; GM_UI.UIStateMachineEvent; GM_Upgrade.ChangeArtifactSkillSlotMapping; GM_Upgrade.PurchaseUpgrade [0x208b]; GM_Upgrade.RequestArtifactSkillSlotMapping; GM_Upgrade.RequestSendEveryonesUpgrades; GM_Upgrade.ShowCurrencyCollectionRings; GM_Upgrade.?InqBasePowerGraphValues; GM_Upgrade.?InqCanBuyUpgrade; GM_Upgrade.?InqNextRecommendedUpgrade; GM_Upgrade.?InqUpgradeFilters; GM_ViewMatch.?RequestInViewMatchMode; GM_ViewMatch.?RequestTeamGhostedAs |
| `0x20000015` | `0214b0e4` | HUD: billboards (announcements, VICTORY/DEFEAT) | 10 | Character.ClearAnnouncement [n:0x100002ec]; Character.ShowAnnouncement [n:0x100002eb]; Character.StopProcessingNewBillboards [n:0x100002bc]; Encounter.NotifyMatchEnded [n:0x1000000e]; Encounter.UI_PlayerJoined [n:0x100000cb]; Encounter.UI_PlayerLeft [n:0x100000ce]; Lobby.ClearLightResourcePackReferences [0x2021 0x2028 0x204b 0x206c]; MapManager.ToggleMiniMap; UI.ActionEnumEvent; UI.BatchNotifyHUDElements [0x213e]; UI.DisplayDialogText [0x2087 0x20ed 0x210a 0x210b]; UI.HideToViewMatchLayout; UI.NotifyHUDElement [0x213d]; UI.ToggleMainMenu; UI.UIStateMachineEvent [0x2038 0x2053]; UI.UpdateHUDVisibility [0x20f5 0x2150] | GM_Chat.ShowChatWindow; GM_Encounter.?InqEncounterIdentifierType; GM_Options.SetIntOption; GM_Options.?GetIntOption; GM_Options.?GetShowUIFramingFillOption; GM_Options.?GetUICharPanelGroupScalingOption; GM_Options.?GetUIConversationGroupScalingOption; GM_Options.?GetUIKillCardGroupScalingOption; GM_Options.?GetUILetterboxGroupScalingOption; GM_Options.?GetUIMatchGroupScalingOption; GM_Options.?GetUIMinimapGroupScalingOption; GM_Options.?GetUIPlayerInfoGroupScalingOption; GM_Options.?GetUISelectionPanelGroupScalingOption; GM_Options.?GetUISkillsGroupScalingOption; GM_Options.?GetUITopBarGroupScalingOption; GM_UI.HUDInitialized; GM_UI.HUDLoaded; GM_UI.TraceInfoFromFlash; GM_UI.UIStateMachineEvent; GM_ViewMatch.?RequestInViewMatchMode |
| `0x20000016` | `0216400c` | resolution sizer | 2 | - | EM_UI.ForceOnSized |
| `0x20000020` | `0217aafc` | loading into world | 2 | Character.MasterCharacterListReceived [0x20ed]; UI.ActionEnumEvent | EM_UI.ForceOnSized; GM_Character.?InqCharactersLoaded; GM_UI.ConnectToGameServer; GM_UI.UIStateMachineEvent |
| `0x20000022` | `0217bafc` | champion picker (lobby / select) | 14 | Lobby.CharacterVariantsLoaded [local: after the costume packs load]; Lobby.ClearHeavyResourcePackReferences [0x204b 0x206c]; Lobby.ClearLightResourcePackReferences [0x2021 0x2028 0x204b 0x206c]; Lobby.Draft_Selecting; Lobby.HeavyResourcePackLoaded [local: after the heavy pack loads]; UI.AvailableCharacterList [0x20b8]; UI.CharacterAdvancementData [0x209d (layout match)]; UI.Incremental_ItemStatuses [0x204c 0x20b8]; UI.ItemStatuses [0x20b8] | EM_UI.ForceOnSized; GM_Character.?InqCharacterRoles; GM_Dialog.PlayUIDialogElement; GM_Encounter.UI_Mission_RaiseEvent; GM_Lobby.PlayerChangedCharacterLockStatus; GM_Lobby.RequestCharacterPickerInformation [0x2025]; GM_Lobby.SelectCharacter [0x2102]; GM_Lobby.TriggerWaitAfterReadyFlag [0x214e]; GM_Skill.?InqSkillToolTipInfo; GM_UI.ConnectToGameServer; GM_UI.RequestCharacterAdvancementData; GM_UI.RequestItemStatuses; GM_UI.UIStateMachineEvent; GM_ViewMatch.?RequestInViewMatchMode |
| `0x2000002b` | `02253790` | HUD: player + selection vitals | 6 | Character.ActiveAgentControlledByThePlayerChanged; Character.AgentControlledByThePlayerChanged; Character.StopProcessingNewBillboards [n:0x100002bc]; Character.UpdateCharacterPanelInfo; Character.UpdateRegenValues; Encounter.NotifyMatchEnded [n:0x1000000e]; MapManager.ToggleMiniMap; UI.ActionEnumEvent; UI.BatchNotifyHUDElements [0x213e]; UI.DisplayDialogText [0x2087 0x20ed 0x210a 0x210b]; UI.HideToViewMatchLayout; UI.NotifyHUDElement [0x213d]; UI.ToggleMainMenu; UI.UIStateMachineEvent [0x2038 0x2053]; UI.UpdateHUDVisibility [0x20f5 0x2150]; Vitals.VitalsChanged [0x0042] | GM_Character.?InqCharacterPanelInfo; GM_Character.?InqCharacterPanelMetaData; GM_Character.?InqRegenValues; GM_Chat.ShowChatWindow; GM_Encounter.?InqEncounterIdentifierType; GM_Options.SetIntOption; GM_Options.?GetIntOption; GM_Options.?GetShowUIFramingFillOption; GM_Options.?GetUICharPanelGroupScalingOption; GM_Options.?GetUIConversationGroupScalingOption; GM_Options.?GetUIKillCardGroupScalingOption; GM_Options.?GetUILetterboxGroupScalingOption; GM_Options.?GetUIMatchGroupScalingOption; GM_Options.?GetUIMinimapGroupScalingOption; GM_Options.?GetUIPlayerInfoGroupScalingOption; GM_Options.?GetUISelectionPanelGroupScalingOption; GM_Options.?GetUISkillsGroupScalingOption; GM_Options.?GetUITopBarGroupScalingOption; GM_UI.HUDInitialized; GM_UI.HUDLoaded; GM_UI.TraceInfoFromFlash; GM_UI.UIStateMachineEvent; GM_ViewMatch.?RequestInViewMatchMode; GM_ViewMatch.?RequestTeamGhostedAs; GM_Vitals.?InqSecondaryVitalType; GM_Vitals.?InqTemporaryVital; GM_Vitals.?InqVital |
| `0x20000051` | `025424d8` | HUD test buttons (dev) | 1 | - | - |
| `0x20000052` | `0254810c` | HUD test harness (dev) | 17 | UI.ActionEnumEvent; UI.ForceOnSized | - |
| `0x20000056` | `0255bfdc` | HUD: skill bar | 9 | Advancement.SkillRanked; Character.ActiveAgentControlledByThePlayerChanged; Character.AgentControlledByThePlayerChanged; Character.StopProcessingNewBillboards [n:0x100002bc]; Character.UpdateCharacterPanelInfo; Encounter.AddParticipant [local: raised when player/agent objects are created (probable)]; Encounter.NotifyMatchEnded [n:0x1000000e]; Encounter.RemoveParticipant [local: object destroyed (probable)]; Encounter.UI_UpdateHasBaseAccess; Encounter.UI_UpdateMatchScorecard; KeyBinding.UI_KeyBindingData; KeyBinding.UI_UpdateKeyBinding; MapManager.ToggleMiniMap; Skill.EnableSkillButton [0x207b 0x20a0 0x2187]; Skill.UI_NotifySkillButtonUpdateIsSuppressed [0x208c]; Skill.UI_NotifyVitalChange; Skill.UI_SkillUpdate; Skill.UpdateSkillUIOverlay [0x2091 n:0x1000015a]; UI.ActionEnumEvent; UI.BatchNotifyHUDElements [0x213e]; UI.DefeatStatusUpdatedForEntity [n:0x100000bc]; UI.DisplayDialogText [0x2087 0x20ed 0x210a 0x210b]; UI.ExecuteSkillError [0x2092 0x20dc]; UI.HideToViewMatchLayout; UI.NotifyHUDElement [0x213d]; UI.RemoveSkillStackCountString [0x20e9]; UI.StartSkillCooldown [0x20f8]; UI.ToggleMainMenu; UI.UIStateMachineEvent [0x2038 0x2053]; UI.UpdateHUDVisibility [0x20f5 0x2150]; UI.UpdateSkillStackCountString [0x20a2 0x20a8 0x20c8]; UI.gmWErrorMessageOccurred; Upgrade.UpdateCurrentUpgrades [0x20e2]; Upgrade.UpdatePowerGraphValues [0x20e2]; ViewMatch.ViewMatchScoreboardData | GM_Advancement.RankSkill [0x2136]; GM_Advancement.?InqCanRankSkill; GM_Advancement.?InqNextRecommendedSkillToRank; GM_Advancement.?InqSkillPointsAvailableString; GM_Advancement.?InqSkillRank; GM_Character.?InqCharacterPanelInfo; GM_Character.?InqCharacterPanelMetaData; GM_Character.?InqCharacterSkills; GM_Chat.ShowChatWindow; GM_Encounter.RequestMatchScorecard; GM_Encounter.?InqCharacterIsInBase; GM_Encounter.?InqEncounterIdentifierType; GM_KeyBinding.UI_RequestKeyBindingData; GM_Lobby.?RequestTeamNames [0x20fd]; GM_Options.SetBoolOption; GM_Options.SetIntOption; GM_Options.?GetBoolOption; GM_Options.?GetIntOption; GM_Options.?GetShowUIFramingFillOption; GM_Options.?GetUICharPanelGroupScalingOption; GM_Options.?GetUIConversationGroupScalingOption; GM_Options.?GetUIKillCardGroupScalingOption; GM_Options.?GetUILetterboxGroupScalingOption; GM_Options.?GetUIMatchGroupScalingOption; GM_Options.?GetUIMinimapGroupScalingOption; GM_Options.?GetUIPlayerInfoGroupScalingOption; GM_Options.?GetUISelectionPanelGroupScalingOption; GM_Options.?GetUISkillsGroupScalingOption; GM_Options.?GetUITopBarGroupScalingOption; GM_Skill.OnSkillRollover; GM_Skill.?InqSkillToolTipInfo; GM_Skill.?RequestStolenPowersForCharacter; GM_UI.HUDInitialized; GM_UI.HUDLoaded; GM_UI.SkillButtonPressed; GM_UI.TraceInfoFromFlash; GM_UI.UIStateMachineEvent; GM_Upgrade.RequestSendEveryonesUpgrades; GM_ViewMatch.?RequestInViewMatchMode; GM_ViewMatch.?RequestTeamGhostedAs; GM_Vitals.?InqSecondaryVitalType; GM_Vitals.?InqVital |
| `0x20000057` | `0256ca74` | HUD: in-match currency | 2 | Character.ActiveAgentControlledByThePlayerChanged; Character.AgentControlledByThePlayerChanged; Character.StopProcessingNewBillboards [n:0x100002bc]; Character.UpdateCharacterPanelInfo; Encounter.NotifyMatchEnded [n:0x1000000e]; Encounter.UI_UpdateHasVendorAccess; MapManager.ToggleMiniMap; UI.ActionEnumEvent; UI.BatchNotifyHUDElements [0x213e]; UI.DisplayDialogText [0x2087 0x20ed 0x210a 0x210b]; UI.HideToViewMatchLayout; UI.NotifyHUDElement [0x213d]; UI.ToggleMainMenu; UI.UIStateMachineEvent [0x2038 0x2053]; UI.UpdateHUDVisibility [0x20f5 0x2150] | GM_Character.?InqCharacterPanelInfo; GM_Character.?InqCharacterPanelMetaData; GM_Chat.ShowChatWindow; GM_Encounter.?InqEncounterIdentifierType; GM_Options.SetIntOption; GM_Options.?GetIntOption; GM_Options.?GetShowUIFramingFillOption; GM_Options.?GetUICharPanelGroupScalingOption; GM_Options.?GetUIConversationGroupScalingOption; GM_Options.?GetUIKillCardGroupScalingOption; GM_Options.?GetUILetterboxGroupScalingOption; GM_Options.?GetUIMatchGroupScalingOption; GM_Options.?GetUIMinimapGroupScalingOption; GM_Options.?GetUIPlayerInfoGroupScalingOption; GM_Options.?GetUISelectionPanelGroupScalingOption; GM_Options.?GetUISkillsGroupScalingOption; GM_Options.?GetUITopBarGroupScalingOption; GM_UI.HUDInitialized; GM_UI.HUDLoaded; GM_UI.TraceInfoFromFlash; GM_UI.UIStateMachineEvent; GM_Upgrade.ShowCurrencyCollectionRings; GM_ViewMatch.?RequestInViewMatchMode; GM_ViewMatch.?RequestTeamGhostedAs |
| `0x20000058` | `02573470` | shared art library (211 images) | 1 | - | - |
| `0x20000059` | `025874ac` | common controls (buttons, dropdowns, lists) | 17 | - | - |
| `0x2000005a` | `025bc9ec` | HUD: character panel (attributes) | 7 | Character.ActiveAgentControlledByThePlayerChanged; Character.AgentControlledByThePlayerChanged; Character.StopProcessingNewBillboards [n:0x100002bc]; Character.UpdateCharacterPanelInfo; Encounter.AddParticipant [local: raised when player/agent objects are created (probable)]; Encounter.NotifyMatchEnded [n:0x1000000e]; Encounter.RemoveParticipant [local: object destroyed (probable)]; Encounter.UI_UpdateHasVendorAccess; Encounter.UI_UpdateMatchScorecard; MapManager.ToggleMiniMap; Skill.EnableSkillButton [0x207b 0x20a0 0x2187]; Skill.UI_SkillUpdate; Skill.UpdateSkillUIOverlay [0x2091 n:0x1000015a]; UI.ActionEnumEvent; UI.BatchNotifyHUDElements [0x213e]; UI.DefeatStatusUpdatedForEntity [n:0x100000bc]; UI.DisplayDialogText [0x2087 0x20ed 0x210a 0x210b]; UI.ExecuteSkillError [0x2092 0x20dc]; UI.HideToViewMatchLayout; UI.NotifyHUDElement [0x213d]; UI.StartSkillCooldown [0x20f8]; UI.ToggleMainMenu; UI.UIStateMachineEvent [0x2038 0x2053]; UI.UpdateHUDVisibility [0x20f5 0x2150]; UI.UpdateSkillStackCountString [0x20a2 0x20a8 0x20c8]; UI.gmWErrorMessageOccurred; Upgrade.UpdateCurrentUpgrades [0x20e2]; Upgrade.UpdatePowerGraphValues [0x20e2]; ViewMatch.ViewMatchScoreboardData | GM_Character.?InqCharacterPanelInfo; GM_Character.?InqCharacterPanelMetaData; GM_Chat.ShowChatWindow; GM_Encounter.RequestMatchScorecard; GM_Encounter.?InqEncounterIdentifierType; GM_Lobby.?RequestTeamNames [0x20fd]; GM_Options.SetIntOption; GM_Options.?GetIntOption; GM_Options.?GetShowUIFramingFillOption; GM_Options.?GetUICharPanelGroupScalingOption; GM_Options.?GetUIConversationGroupScalingOption; GM_Options.?GetUIKillCardGroupScalingOption; GM_Options.?GetUILetterboxGroupScalingOption; GM_Options.?GetUIMatchGroupScalingOption; GM_Options.?GetUIMinimapGroupScalingOption; GM_Options.?GetUIPlayerInfoGroupScalingOption; GM_Options.?GetUISelectionPanelGroupScalingOption; GM_Options.?GetUISkillsGroupScalingOption; GM_Options.?GetUITopBarGroupScalingOption; GM_Skill.OnArtifactButtonRollover; GM_Skill.?InqSkillToolTipInfo; GM_Skill.?RequestStolenPowersForCharacter; GM_UI.HUDInitialized; GM_UI.HUDLoaded; GM_UI.SkillButtonPressed; GM_UI.TraceInfoFromFlash; GM_UI.UIStateMachineEvent; GM_Upgrade.RequestSendEveryonesUpgrades; GM_Upgrade.ShowCurrencyCollectionRings; GM_ViewMatch.?RequestInViewMatchMode; GM_ViewMatch.?RequestTeamGhostedAs |
| `0x2000005b` | `025c3954` | HUD: kill feed | 6 | Character.ActiveAgentControlledByThePlayerChanged; Character.AgentControlledByThePlayerChanged; Character.NotifyPlayerDied; Character.UpdateCharacterPanelInfo | GM_Character.?InqCharacterPanelInfo; GM_Character.?InqCharacterPanelMetaData; GM_ViewMatch.?RequestInViewMatchMode; GM_ViewMatch.?RequestTeamGhostedAs |
| `0x2000005c` | `025cbbc8` | HUD: top bar | 3 | - | GM_UI.TakeScreenShot; GM_UI.ToggleMainMenu |
| `0x2000005e` | `025d2884` | HUD: hero graph / power bar | 7 | Character.ActiveAgentControlledByThePlayerChanged; Character.AgentControlledByThePlayerChanged; Character.UpdateCharacterPanelInfo; Encounter.AddParticipant [local: raised when player/agent objects are created (probable)]; Encounter.RemoveParticipant [local: object destroyed (probable)]; Encounter.UI_UpdateMatchScorecard; UI.DefeatStatusUpdatedForEntity [n:0x100000bc]; UI.gmWErrorMessageOccurred; Upgrade.UpdateCurrentUpgrades [0x20e2]; Upgrade.UpdatePowerGraphValues [0x20e2]; ViewMatch.ViewMatchScoreboardData | GM_Character.?InqCharacterPanelInfo; GM_Character.?InqCharacterPanelMetaData; GM_Encounter.RequestMatchScorecard; GM_Lobby.?RequestTeamNames [0x20fd]; GM_MapManager.FlashUIToWorldClick; GM_Skill.?InqSkillToolTipInfo; GM_Skill.?RequestStolenPowersForCharacter; GM_Upgrade.RequestSendEveryonesUpgrades; GM_Upgrade.?InqBasePowerGraphValues; GM_ViewMatch.?RequestInViewMatchMode; GM_ViewMatch.?RequestTeamGhostedAs |
| `0x2000005f` | `025dbcc0` | settings dialog | 16 | Camera.CameraLockedPreference; Character.StopProcessingNewBillboards [n:0x100002bc]; Encounter.NotifyMatchEnded [n:0x1000000e]; KeyBinding.UI_KeyBindingData; KeyBinding.UI_UpdateKeyBinding; MapManager.ToggleMiniMap; Options.InGameFullScreenOptionChanged; Options.OutOfGameFullScreenOptionChanged; Sound.AudioQualityChanged; UI.ActionEnumEvent; UI.BatchNotifyHUDElements [0x213e]; UI.DisplayDialogText [0x2087 0x20ed 0x210a 0x210b]; UI.GameFrontUIDestroyedInCPP [0x2021]; UI.GraphicsQualityChanged; UI.HideToViewMatchLayout; UI.NotifyHUDElement [0x213d]; UI.ToggleMainMenu; UI.UIStateMachineEvent [0x2038 0x2053]; UI.UpdateHUDVisibility [0x20f5 0x2150] | EM_UI.DetectAppropriateRenderSettings; EM_UI.?InqIsWindowsXP; GM_Chat.ShowChatWindow; GM_Encounter.?InqEncounterIdentifierType; GM_KeyBinding.UI_CancelAllRebinds; GM_KeyBinding.UI_CommitAllRebinds; GM_KeyBinding.UI_RebindKey; GM_KeyBinding.UI_RequestKeyBindingData; GM_KeyBinding.UI_ResetAllToDefault; GM_Options.OnApplyOptions; GM_Options.RequestTrainingLessonsReset; GM_Options.SetAspectRatio; GM_Options.SetAudioBinkVolumeOption; GM_Options.SetAudioCharacterThemeVolumeOption; GM_Options.SetAudioMasterVolumeOption; GM_Options.SetAudioMusicVolumeOption; GM_Options.SetAudioSFXVolumeOption; GM_Options.SetAudioVOAnnouncerVolumeOption; GM_Options.SetAudioVOCharacterVolumeOption; GM_Options.SetAutoAttackOption; GM_Options.SetBoolOption; GM_Options.SetCharacterOutlineOption; GM_Options.SetCinematicDrawDistance; GM_Options.SetCoachingContextualTipsEnabledOption; GM_Options.SetCoachingEnabledOption; GM_Options.SetCoachingPlayerOverheadTipsEnabledOption; GM_Options.SetConstrainCursorOption; GM_Options.SetDisplayAdapterOption; GM_Options.SetFloatOption; GM_Options.SetGraphicsCore; GM_Options.SetGraphicsQualityLevel; GM_Options.SetInGameBorderlessWindowOption; GM_Options.SetInGameFullScreenOption; GM_Options.SetInGameResolutionOption; GM_Options.SetInGameWindowedResolutionOption; GM_Options.SetIntOption; GM_Options.SetOutOfGameBorderlessWindowOption; GM_Options.SetOutOfGameFullScreenOption; GM_Options.SetOutOfGameResolutionOption; GM_Options.SetOutOfGameWindowedResolutionOption; GM_Options.SetSelfCastingOption; GM_Options.SetShadowMapQuality; GM_Options.SetShowUIFramingFillOption; GM_Options.SetSmartCastingOption; GM_Options.SetSoundQualityLevel; GM_Options.SetTeamIndicator; GM_Options.SetTurretWarningEnabled; GM_Options.SetUICharPanelGroupScalingOption; GM_Options.SetUIConversationGroupScalingOption; GM_Options.SetUIKillCardGroupScalingOption; GM_Options.SetUILetterboxGroupScalingOption; GM_Options.SetUIMatchGroupScalingOption; GM_Options.SetUIMinimapGroupScalingOption; GM_Options.SetUIPlayerInfoGroupScalingOption; GM_Options.SetUIRecommendedPanelOption; GM_Options.SetUIScalesLinkedOption; GM_Options.SetUISelectionPanelGroupScalingOption; GM_Options.SetUISkillsGroupScalingOption; GM_Options.SetUITopBarGroupScalingOption; GM_Options.SetUIntOption; GM_Options.?GetAspectRatio; GM_Options.?GetAudioBinkVolumeOption; GM_Options.?GetAudioCharacterThemeVolumeOption; GM_Options.?GetAudioMasterVolumeOption; GM_Options.?GetAudioMusicVolumeOption; GM_Options.?GetAudioSFXVolumeOption; GM_Options.?GetAudioVOAnnouncerVolumeOption; GM_Options.?GetAudioVOCharacterVolumeOption; GM_Options.?GetAutoAttackOption; GM_Options.?GetBoolOption; GM_Options.?GetCharacterOutlineOption; GM_Options.?GetCinematicDrawDistance; GM_Options.?GetCoachingContextualTipsEnabledOption; GM_Options.?GetCoachingEnabledOption; GM_Options.?GetCoachingPlayerOverheadTipsEnabledOption; GM_Options.?GetDisplayAdapterOption; GM_Options.?GetFloatOption; GM_Options.?GetGraphicsCore; GM_Options.?GetGraphicsQualityLevel; GM_Options.?GetInGameBorderlessWindowOption; GM_Options.?GetInGameFullScreenOption; GM_Options.?GetInGameResolutionOption; GM_Options.?GetInGameWindowedResolutionOption; GM_Options.?GetIntOption; GM_Options.?GetOutOfGameBorderlessWindowOption; GM_Options.?GetOutOfGameFullScreenOption; GM_Options.?GetOutOfGameResolutionOption; GM_Options.?GetOutOfGameWindowedResolutionOption; GM_Options.?GetSelfCastingOption; GM_Options.?GetShadowMapQuality; GM_Options.?GetShowUIFramingFillOption; GM_Options.?GetSmartCastingOption; GM_Options.?GetSoundQualityLevel; GM_Options.?GetTeamIndicatorInfo; GM_Options.?GetTurretWarningEnabled; GM_Options.?GetUICharPanelGroupScalingOption; GM_Options.?GetUIConversationGroupScalingOption; GM_Options.?GetUIKillCardGroupScalingOption; GM_Options.?GetUILetterboxGroupScalingOption; GM_Options.?GetUIMatchGroupScalingOption; GM_Options.?GetUIMinimapGroupScalingOption; GM_Options.?GetUIPlayerInfoGroupScalingOption; GM_Options.?GetUIRecommendedPanelOption; GM_Options.?GetUIScalesLinkedOption; GM_Options.?GetUISelectionPanelGroupScalingOption; GM_Options.?GetUISkillsGroupScalingOption; GM_Options.?GetUITopBarGroupScalingOption; GM_Options.?GetUIntOption; GM_UI.HUDInitialized; GM_UI.HUDLoaded; GM_UI.InGameMenuClosed; GM_UI.InGameMenuOpened; GM_UI.TraceInfoFromFlash; GM_UI.UIStateMachineEvent; GM_UI.?IsBinkFileValid; GM_UI.?IsLoggedIntoGame; GM_ViewMatch.?RequestInViewMatchMode |
| `0x20000062` | `025fe1e8` | HUD: player info panel (portraits) | 7 | Character.ActiveAgentControlledByThePlayerChanged; Character.AgentControlledByThePlayerChanged; Character.StopProcessingNewBillboards [n:0x100002bc]; Character.UpdateCharacterPanelInfo; Encounter.AddParticipant [local: raised when player/agent objects are created (probable)]; Encounter.NotifyMatchEnded [n:0x1000000e]; Encounter.RemoveParticipant [local: object destroyed (probable)]; Encounter.UI_UpdateMatchScorecard; MapManager.ToggleMiniMap; UI.ActionEnumEvent; UI.BatchNotifyHUDElements [0x213e]; UI.DefeatStatusUpdatedForEntity [n:0x100000bc]; UI.DisplayDialogText [0x2087 0x20ed 0x210a 0x210b]; UI.HideToViewMatchLayout; UI.NotifyHUDElement [0x213d]; UI.ToggleMainMenu; UI.UIStateMachineEvent [0x2038 0x2053]; UI.UpdateHUDVisibility [0x20f5 0x2150]; UI.gmWErrorMessageOccurred; Upgrade.UpdateCurrentUpgrades [0x20e2]; Upgrade.UpdatePowerGraphValues [0x20e2]; ViewMatch.ViewMatchScoreboardData | GM_Character.?InqCharacterPanelInfo; GM_Character.?InqCharacterPanelMetaData; GM_Chat.RunCmd; GM_Chat.ShowChatWindow; GM_Encounter.RequestMatchScorecard; GM_Encounter.?InqEncounterIdentifierType; GM_Lobby.?RequestTeamNames [0x20fd]; GM_MapManager.FlashUIToWorldClick; GM_Options.SetIntOption; GM_Options.?GetIntOption; GM_Options.?GetShowUIFramingFillOption; GM_Options.?GetUICharPanelGroupScalingOption; GM_Options.?GetUIConversationGroupScalingOption; GM_Options.?GetUIKillCardGroupScalingOption; GM_Options.?GetUILetterboxGroupScalingOption; GM_Options.?GetUIMatchGroupScalingOption; GM_Options.?GetUIMinimapGroupScalingOption; GM_Options.?GetUIPlayerInfoGroupScalingOption; GM_Options.?GetUISelectionPanelGroupScalingOption; GM_Options.?GetUISkillsGroupScalingOption; GM_Options.?GetUITopBarGroupScalingOption; GM_Skill.?InqSkillToolTipInfo; GM_Skill.?RequestStolenPowersForCharacter; GM_UI.HUDInitialized; GM_UI.HUDLoaded; GM_UI.TraceInfoFromFlash; GM_UI.UIStateMachineEvent; GM_Upgrade.RequestSendEveryonesUpgrades; GM_Upgrade.?InqBasePowerGraphValues; GM_ViewMatch.?RequestInViewMatchMode; GM_ViewMatch.?RequestTeamGhostedAs |
| `0x20000063` | `026384b8` | HUD: status icons | 4 | Character.ActiveAgentControlledByThePlayerChanged; Character.AgentControlledByThePlayerChanged; Character.UpdateCharacterPanelInfo; StatusIcon.AddStatusIcon [0x20a2 0x20c8]; StatusIcon.BatchAddStatusIcon; StatusIcon.RemoveStatusIcon [0x20e9]; StatusIcon.UpdateStatusIcon [0x20a8]; StatusIcon.UpdateStatusIconTooltip [0x20d0 0x2127] | GM_Character.?InqCharacterPanelInfo; GM_Character.?InqCharacterPanelMetaData; GM_MapManager.FlashUIToWorldClick; GM_StatusIcon.RequestStatusIcons; GM_ViewMatch.?RequestInViewMatchMode; GM_ViewMatch.?RequestTeamGhostedAs |
| `0x20000064` | `0263d62c` | HUD: objectives tracker | 10 | Character.ActiveAgentControlledByThePlayerChanged; Character.AgentControlledByThePlayerChanged; Character.UpdateCharacterPanelInfo; Encounter.UI_AddObjective; Encounter.UI_DeliverCurrentObjectives; Encounter.UI_DeliverObjectiveCategories [0x2034]; Encounter.UI_RemoveObjective; Encounter.UI_RemoveObjectiveCategory [0x2023]; Encounter.UI_SetObjectiveTrackerEnabled [0x2034 0x2075]; Encounter.UI_UpdateObjectiveCategory_State [0x2023]; Encounter.UI_UpdateObjective_BannerText; Encounter.UI_UpdateObjective_Count [0x2009]; Encounter.UI_UpdateObjective_CountDown; Encounter.UI_UpdateObjective_CountMax [0x2009]; Encounter.UI_UpdateObjective_ProgressPercent; Encounter.UI_UpdateObjective_State [0x2009]; Encounter.UI_UpdateObjective_TeamRelationship; Encounter.UI_UpdateObjective_Text; Encounter.UI_UpdateObjective_TimerDuration | GM_Character.?InqCharacterPanelInfo; GM_Character.?InqCharacterPanelMetaData; GM_Encounter.ReadyForObjectives; GM_ViewMatch.?RequestInViewMatchMode; GM_ViewMatch.?RequestTeamGhostedAs |
| `0x20000065` | `0264adac` | HUD: event timer / timeline banners | 9 | Character.ActiveAgentControlledByThePlayerChanged; Character.AgentControlledByThePlayerChanged; Character.StopProcessingNewBillboards [n:0x100002bc]; Character.UpdateCharacterPanelInfo; Encounter.AddParticipant [local: raised when player/agent objects are created (probable)]; Encounter.NotifyMatchEnded [n:0x1000000e]; Encounter.RemoveParticipant [local: object destroyed (probable)]; Encounter.UI_MissionEvent_AddTimelineBanner; Encounter.UI_MissionEvent_AddTimelineEvent; Encounter.UI_MissionEvent_BatchAddTimelineEvent; Encounter.UI_MissionEvent_RemoveTimelineBanner; Encounter.UI_MissionEvent_RemoveTimelineEvent; Encounter.UI_MissionEvent_StartTimeline; Encounter.UI_UpdateMatchScorecard; MapManager.ToggleMiniMap; UI.ActionEnumEvent; UI.BatchNotifyHUDElements [0x213e]; UI.DefeatStatusUpdatedForEntity [n:0x100000bc]; UI.DisplayDialogText [0x2087 0x20ed 0x210a 0x210b]; UI.HideToViewMatchLayout; UI.NotifyHUDElement [0x213d]; UI.ToggleMainMenu; UI.UIStateMachineEvent [0x2038 0x2053]; UI.UpdateHUDVisibility [0x20f5 0x2150]; UI.gmWErrorMessageOccurred; Upgrade.UpdateCurrentUpgrades [0x20e2]; Upgrade.UpdatePowerGraphValues [0x20e2]; ViewMatch.ViewMatchScoreboardData | GM_Character.?InqCharacterPanelInfo; GM_Character.?InqCharacterPanelMetaData; GM_Chat.ShowChatWindow; GM_Encounter.RequestMatchScorecard; GM_Encounter.UI_ReadyForTimelineData [notice 0x100002ad]; GM_Encounter.?InqEncounterIdentifierType; GM_Lobby.?RequestTeamNames [0x20fd]; GM_Options.SetIntOption; GM_Options.?GetIntOption; GM_Options.?GetShowUIFramingFillOption; GM_Options.?GetUICharPanelGroupScalingOption; GM_Options.?GetUIConversationGroupScalingOption; GM_Options.?GetUIKillCardGroupScalingOption; GM_Options.?GetUILetterboxGroupScalingOption; GM_Options.?GetUIMatchGroupScalingOption; GM_Options.?GetUIMinimapGroupScalingOption; GM_Options.?GetUIPlayerInfoGroupScalingOption; GM_Options.?GetUISelectionPanelGroupScalingOption; GM_Options.?GetUISkillsGroupScalingOption; GM_Options.?GetUITopBarGroupScalingOption; GM_Skill.?InqSkillToolTipInfo; GM_Skill.?RequestStolenPowersForCharacter; GM_UI.HUDInitialized; GM_UI.HUDLoaded; GM_UI.TraceInfoFromFlash; GM_UI.UIStateMachineEvent; GM_Upgrade.RequestSendEveryonesUpgrades; GM_ViewMatch.?RequestInViewMatchMode; GM_ViewMatch.?RequestTeamGhostedAs |
| `0x20000066` | `0265763c` | video player | 1 | - | - |
| `0x20000067` | `0265c5dc` | pre-match lobby (PvP lobby, amplifier set / Stolen Power pickers) | 26 | Achievement.AllPendingAchivementBanners [0x211f]; Amplifier.NotifyAmplifierSet [0x20c7]; Amplifier.NotifyListAmplifierSets [0x2090]; Character.RewardSetsData [0x2125 0x2197]; Character.Ribbon_CharacterLevelChanged [0x2104]; Character.Ribbon_FinishedItemsFulfilled [0x2095]; Character.Ribbon_ItemFulfilled [0x2095]; Character.SendAccountCurrencyBalance [0x2081]; Character.SendAccountLevelAndXP [0x2080]; Chat.ToggleUnreadChat [0x20b0 0x20b6]; Chat.UI_ShowWrapperGeneralChatWindow; CustomMatch.UI_CustomMatch_Cancelled [0x2011]; CustomMatch.UI_CustomMatch_Kicked [0x2041]; CustomMatch.UI_CustomMatch_Left [0x203f]; Dialog.HideAllConversationSlots [0x2001 (C++ conversation player)]; Dialog.HideConversationSlot [0x2001 (C++ conversation player)]; Dialog.HighlightConversationAdvanceButton; Dialog.ShowConversationSlot [0x2001 (conversation; C++ drives the slots)]; Encounter.ResetMapSelectionList [0x2024 0x20ff]; Grouping.PlayerLeftGroup [0x2071]; KeyBinding.UI_KeyBindingData; KeyBinding.UI_UpdateKeyBinding; Lobby.ClearLightResourcePackReferences [0x2021 0x2028 0x204b 0x206c]; Lobby.Draft_Banning; Lobby.Draft_EnableTrade; Lobby.Draft_PlayersTrading; Lobby.Draft_Selecting; Lobby.Draft_TradeRequest [0x2054]; Lobby.HideBackButton [0x2016 0x206d]; Lobby.LobbyEncounterDetails [0x204c]; Lobby.LobbyRejoinRoom [0x205b]; Lobby.MatchLaunchWarning [0x204b]; Lobby.PlayerPickedAmplifierSet [0x2029 0x204a 0x2060]; Lobby.PlayerPickedStolenPowers [0x2004 0x2029 0x2060]; Lobby.PlayerSelectedEarlyLaunchFromServer [0x206c]; Lobby.PreGameTips; Lobby.UpdateEarlyLaunchTime [0x2061]; Lobby.UpdateLobbyLoadingPercent [0x2031]; Lobby.UpdateLobbyLoadingPercentForViewmatch [0x206d]; Lobby.UpdateLobbyState [0x2060 (layout match)]; Lobby.UpdateLobbyStateSingle [0x2029 0x204c 0x2060]; UI.ActionEnumEvent; UI.AvailableCharacterList [0x20b8]; UI.BarredFromMatching [0x20f3]; UI.BatchNotifyHUDElements [0x213e]; UI.CharacterAdvancementData [0x209d (layout match)]; UI.ClientLanguage; UI.DisplayDialogText [0x2087 0x20ed 0x210a 0x210b]; UI.FoundMatch [0x20fa]; UI.GameFrontUIDestroyedInCPP [0x2021]; UI.Incremental_ItemStatuses [0x204c 0x20b8]; UI.ItemStatuses [0x20b8]; UI.JoinedQueue [0x20c0]; UI.NotifyHUDElement [0x213d]; UI.PendingMatchFailure [0x20d7 0x210b]; UI.ProtectorAdvancementStatus [0x215d (account flags; probable)]; UI.QueueEligibility [0x2101]; UI.RemovedFromQueue [0x20e0 0x210b]; UI.ShowURLDialog; UI.ToggleMainMenu; UI.UIStateMachineEvent [0x2038 0x2053]; UI.UserCanCreateGroup [0x2070]; UI.gmWErrorMessageOccurred | EM_UI.ForceOnSized; EM_WebBrowser.?InqFoundCEF3SubprocessExecutable; GM_Achievement.RequestAllPendingRewardlessAchievementNotifications [0x212e]; GM_Amplifier.UI_RequestAllAmplifierSets; GM_Amplifier.?UI_InqAmplifierSetIcons; GM_Amplifier.?UI_InqAugmentData; GM_Amplifier.?UI_InqCharacterDefaultAmplifierSet; GM_Amplifier.?UI_InqModData; GM_Character.RequestAccountCurrencyBalance; GM_Character.RequestAccountLevelAndXP; GM_Character.RequestPostMatchChanges [0x20ba]; GM_Character.Ribbon_ReceivedItemsFulfilled; GM_Character.UI_RequestPendingRewardUpdateFromServer [0x2124]; GM_Character.?InqCharacterRoles; GM_Character.?UI_RequestAspirationalTooltip; GM_Chat.HideChatForBrowser; GM_Chat.HideChatWindow; GM_Chat.RestoreChatForBrowser; GM_Chat.ShowChatWindow; GM_ConnectionManager.ResetLastConnectionErrorString; GM_ConnectionManager.?CheckLobbyConnection; GM_ConnectionManager.?InqLastConnectionErrorString; GM_Contacts.?UI_CanInviteSteamFriends; GM_CustomMatch.?IsInCustomMatch [0x20fb]; GM_Dialog.PlayUIDialogElement; GM_Dialog.SetUIDialogIdleState; GM_Dialog.SetUIDialogInQueueState; GM_Dialog.UI_ReadyForConversation; GM_Dialog.UI_SkipConversation; GM_Encounter.UI_Mission_RaiseEvent; GM_Encounter.?InqPVPEncounters; GM_KeyBinding.UI_RequestKeyBindingData; GM_Lobby.Draft_RequestTrade; GM_Lobby.Draft_TradeResponse; GM_Lobby.ExitLobbyToMainMenu [0x200a]; GM_Lobby.LobbyUIReady [0x202d]; GM_Lobby.PlayerChangedCharacterLockStatus; GM_Lobby.PlayerSelectedEarlyLaunch [0x206a]; GM_Lobby.RequestAllPregameTips [0x201e]; GM_Lobby.RequestChangeAmplifierSet [0x200d]; GM_Lobby.RequestChangeStolenPower; GM_Lobby.RequestCharacterPickerInformation [0x2025]; GM_Lobby.RequestMyAmplifierSet [0x2057]; GM_Lobby.RequestMyStolenPowers [0x2064]; GM_Lobby.SelectCharacter [0x2102]; GM_Lobby.TeamDisplayReady [0x2108]; GM_Lobby.TriggerWaitAfterReadyFlag [0x214e]; GM_Lobby.?RequestStolenPowerList [0x2017]; GM_Lobby.?RequestTeamNames [0x20fd]; GM_Options.SetBoolOption; GM_Options.?GetBoolOption; GM_Options.?GetUIConversationGroupScalingOption; GM_UI.ConnectToGameServer; GM_UI.DisplayPendingDodgePenaltyNotifications [0x21a8]; GM_UI.InGameMenuClosed; GM_UI.InGameMenuOpened; GM_UI.JoinQueue [0x20eb]; GM_UI.JoinQueueForPromotedMap [0x20eb]; GM_UI.RequestCharacterAdvancementData; GM_UI.RequestClientLanguage; GM_UI.RequestItemStatuses; GM_UI.RequestProtectorAdvancementStatus; GM_UI.UIStateMachineEvent; GM_UI.?InqChatButtonTooltip; GM_UI.?InqQueueEligibility; GM_UI.?InqWrapperDisplayData; GM_UI.?IsBinkFileValid; GM_UI.?IsLoggedIntoGame; GM_UI.?NeedsUpdateNews; GM_ViewMatch.?RequestInViewMatchMode; GM_ViewMatch.?RequestInViewMatchModeLastMatch |
| `0x2000006b` | `0266dfa0` | tooltips | 39 | Character.ActiveAgentControlledByThePlayerChanged; Character.AgentControlledByThePlayerChanged; Character.UpdateCharacterPanelInfo; Contacts.UI_NotifyContactAccountIconChanged [0x20ec]; Contacts.UI_NotifyContactAdded [0x2051 0x20cc]; Contacts.UI_NotifyContactChangeNote [0x208f]; Contacts.UI_NotifyContactChangeStatusMessage [0x20c5]; Contacts.UI_NotifyContactChangeSteamName; Contacts.UI_NotifyContactChangedGroup [0x20cb]; Contacts.UI_NotifyContactGroupCreated [0x2014]; Contacts.UI_NotifyContactGroupDestroyed [0x205e]; Contacts.UI_NotifyContactIgnored [0x2051]; Contacts.UI_NotifyContactList [0x203b (layout, probable)]; Contacts.UI_NotifyContactPresenceChanged [0x2018 0x20ae]; Contacts.UI_NotifyContactRemoved [0x2020 0x2051 0x20cc]; Contacts.UI_NotifyContactUnignored [0x204f 0x20cc]; UI.AvailableCharacterList [0x20b8]; UI.CharacterAdvancementData [0x209d (layout match)]; UI.DeliverFriendsLeaderboard [0x21a2 0x21a3]; UI.DeliverRegionalLeaderboard [0x21a2 0x21a3]; UI.Incremental_ItemStatuses [0x204c 0x20b8]; UI.ItemStatuses [0x20b8]; Upgrade.UpdatePowerGraphValues [0x20e2] | GM_Character.?InqCharacterPanelInfo; GM_Character.?InqCharacterPanelMetaData; GM_Character.?RequestProtectorIcons; GM_UI.RequestCharacterAdvancementData; GM_UI.RequestItemStatuses; GM_UI.RequestLeaderboards [0x21a4]; GM_Upgrade.?InqBasePowerGraphValues; GM_ViewMatch.?RequestInViewMatchMode; GM_ViewMatch.?RequestTeamGhostedAs |
| `0x2000006c` | `0267f87c` | disconnect dialog | 2 | UI.gmWErrorMessageOccurred | - |
| `0x2000006d` | `02682e84` | login / connecting / display-name screens | 5 | Achievement.AllPendingAchivementBanners [0x211f]; Character.MasterCharacterListReceived [0x20ed]; Character.RewardSetsData [0x2125 0x2197]; Character.Ribbon_CharacterLevelChanged [0x2104]; Character.Ribbon_FinishedItemsFulfilled [0x2095]; Character.Ribbon_ItemFulfilled [0x2095]; Character.SendAccountCurrencyBalance [0x2081]; Character.SendAccountLevelAndXP [0x2080]; Chat.UI_ShowWrapperGeneralChatWindow; ConnectionManager.ShowLoginError; ConnectionManager.UpdateConnectionState [0x2024 0x20ed 0x20ff]; CustomMatch.UI_CustomMatch_Cancelled [0x2011]; CustomMatch.UI_CustomMatch_Kicked [0x2041]; CustomMatch.UI_CustomMatch_Left [0x203f]; Grouping.PlayerLeftGroup [0x2071]; KeyBinding.UI_KeyBindingData; KeyBinding.UI_UpdateKeyBinding; Lobby.LobbyRejoinRoom [0x205b]; UI.ActionEnumEvent; UI.BarredFromMatching [0x20f3]; UI.ChargenError; UI.DisplayDialogText [0x2087 0x20ed 0x210a 0x210b]; UI.FoundMatch [0x20fa]; UI.JoinedQueue [0x20c0]; UI.PendingMatchFailure [0x20d7 0x210b]; UI.ProtectorAdvancementStatus [0x215d (account flags; probable)]; UI.RemovedFromQueue [0x20e0 0x210b]; UI.ShowURLDialog; UI.ToggleMainMenu; UI.UIStateMachineEvent [0x2038 0x2053]; UI.UserCanCreateGroup [0x2070] | EM_WebBrowser.?InqFoundCEF3SubprocessExecutable; GM_Achievement.RequestAllPendingRewardlessAchievementNotifications [0x212e]; GM_Character.RequestAccountCurrencyBalance; GM_Character.RequestAccountLevelAndXP; GM_Character.RequestPostMatchChanges [0x20ba]; GM_Character.Ribbon_ReceivedItemsFulfilled; GM_Character.UI_RequestPendingRewardUpdateFromServer [0x2124]; GM_Character.?InqCharactersLoaded; GM_Chat.HideChatForBrowser; GM_Chat.HideChatWindow; GM_Chat.RestoreChatForBrowser; GM_Chat.ShowChatWindow; GM_ConnectionManager.LoginWithWBID; GM_ConnectionManager.ResetLastConnectionErrorString; GM_ConnectionManager.?CheckLobbyConnection; GM_ConnectionManager.?InqLastConnectionErrorString; GM_Contacts.?UI_CanInviteSteamFriends; GM_CustomMatch.?IsInCustomMatch [0x20fb]; GM_Dialog.SetUIDialogIdleState; GM_Dialog.SetUIDialogInQueueState; GM_KeyBinding.UI_RequestKeyBindingData; GM_Options.SetBoolOption; GM_Options.SetSavedUsername; GM_Options.?GetBoolOption; GM_UI.ConnectToGameServer; GM_UI.CreateAccount; GM_UI.DisplayPendingDodgePenaltyNotifications [0x21a8]; GM_UI.ForgotPassword; GM_UI.JoinQueue [0x20eb]; GM_UI.JoinQueueForPromotedMap [0x20eb]; GM_UI.RequestProtectorAdvancementStatus; GM_UI.ShowCursor; GM_UI.SubmitScreenName [0x2148 (probable: name request)]; GM_UI.UIStateMachineEvent; GM_UI.?GetChargenError; GM_UI.?InqDefaultAccountName; GM_UI.?InqRegionDisplayName; GM_UI.?IsLoggedIntoGame; GM_UI.?NeedsUpdateNews; GM_ViewMatch.?RequestInViewMatchModeLastMatch |
| `0x2000006e` | `0268b05c` | ribbons (level up, match found, queue...) | 34 | Achievement.AllPendingAchivementBanners [0x211f]; Achievement.SetAchievementData [local: built from achievement records after 0x2120 (guess)]; Achievement.SetAchievementObjectiveData [0x2120 0x21a6]; Achievement.SetDeprecatedAchievements [0x2120 0x21a6]; Achievement.TraineeAchievements; Amplifier.NotifyAmplifierSet [0x20c7]; Amplifier.NotifyListAmplifierSets [0x2090]; Character.RewardSetsData [0x2125 0x2197]; Character.Ribbon_CharacterLevelChanged [0x2104]; Character.Ribbon_FinishedItemsFulfilled [0x2095]; Character.Ribbon_ItemFulfilled [0x2095]; Character.SendAccountCurrencyBalance [0x2081]; Character.SendAccountLevelAndXP [0x2080]; Chat.UI_ShowWrapperGeneralChatWindow; CustomMatch.UI_CustomMatch_Cancelled [0x2011]; CustomMatch.UI_CustomMatch_Kicked [0x2041]; CustomMatch.UI_CustomMatch_Left [0x203f]; Encounter.ResetMapSelectionList [0x2024 0x20ff]; Grouping.PlayerLeftGroup [0x2071]; Lobby.LobbyRejoinRoom [0x205b]; Lobby.LobbyRoomCreated [0x2028]; ProfileUI.ProfileUI_HeavyResourcePackData; UI.ActionEnumEvent; UI.AvailableCharacterList [0x20b8]; UI.BarredFromMatching [0x20f3]; UI.CharacterAdvancementData [0x209d (layout match)]; UI.DisplayDialogText [0x2087 0x20ed 0x210a 0x210b]; UI.FoundMatch [0x20fa]; UI.Incremental_ItemStatuses [0x204c 0x20b8]; UI.ItemStatuses [0x20b8]; UI.JoinedQueue [0x20c0]; UI.NumPlayersAcceptedMatch [0x20ad]; UI.PendingMatchFailure [0x20d7 0x210b]; UI.ProtectorAdvancementStatus [0x215d (account flags; probable)]; UI.QueueEligibility [0x2101]; UI.RemovedFromQueue [0x20e0 0x210b]; UI.Scorecard_HeavyOnlyLoaded; UI.ShowURLDialog; UI.ToggleMainMenu; UI.UIStateMachineEvent [0x2038 0x2053]; UI.UserCanCreateGroup [0x2070] | EM_WebBrowser.?InqFoundCEF3SubprocessExecutable; GM_Achievement.AcknowledgeAchievementDisplayed [0x211e? (u32; guess)]; GM_Achievement.RequestAllAchievementData [0x211d]; GM_Achievement.RequestAllPendingRewardlessAchievementNotifications [0x212e]; GM_Achievement.RequestTraineeAchievements; GM_Achievement.?InqSuperBannerVideoForAchievement; GM_Amplifier.UI_RequestAllAmplifierSets; GM_Amplifier.?UI_InqAmplifierSetIcons; GM_Amplifier.?UI_InqAugmentData; GM_Amplifier.?UI_InqModData; GM_Character.RequestAccountCurrencyBalance; GM_Character.RequestAccountLevelAndXP; GM_Character.RequestPostMatchChanges [0x20ba]; GM_Character.Ribbon_ReceivedItemsFulfilled; GM_Character.UI_ClaimPostMatchReward [0x2128]; GM_Character.UI_RequestPendingRewardUpdateFromServer [0x2124]; GM_Character.?RequestProtectorIcons; GM_Chat.HideChatForBrowser; GM_Chat.HideChatWindow; GM_Chat.RestoreChatForBrowser; GM_Chat.ShowChatWindow; GM_ConnectionManager.ResetLastConnectionErrorString; GM_ConnectionManager.?CheckLobbyConnection; GM_ConnectionManager.?InqLastConnectionErrorString; GM_Contacts.?UI_CanInviteSteamFriends; GM_CustomMatch.?IsInCustomMatch [0x20fb]; GM_Dialog.SetUIDialogIdleState; GM_Dialog.SetUIDialogInQueueState; GM_Encounter.?InqPVPEncounters; GM_Lobby.?RequestStolenPowerList [0x2017]; GM_Skill.?InqSkillToolTipInfo; GM_UI.AcceptMatch [0x20ca]; GM_UI.ConnectToGameServer; GM_UI.DisplayPendingDodgePenaltyNotifications [0x21a8]; GM_UI.InGameMenuClosed; GM_UI.InGameMenuOpened; GM_UI.JoinQueue [0x20eb]; GM_UI.JoinQueueForPromotedMap [0x20eb]; GM_UI.LeaveQueue [0x20c3]; GM_UI.PlayerAcknowledgedStandingsChange; GM_UI.RequestCharacterAdvancementData; GM_UI.RequestItemStatuses; GM_UI.RequestProtectorAdvancementStatus; GM_UI.RewardBanner_SelectCharacter; GM_UI.Scorecard_LoadCharacterHeavyOnly; GM_UI.UIStateMachineEvent; GM_UI.?InqQueueEligibility; GM_UI.?IsBinkFileValid; GM_UI.?IsLoggedIntoGame; GM_UI.?NeedsUpdateNews; GM_ViewMatch.?RequestInViewMatchMode; GM_ViewMatch.?RequestInViewMatchModeLastMatch |
| `0x2000006f` | `026a6944` | HUD: kill card | 10 | Character.ActiveAgentControlledByThePlayerChanged; Character.AgentControlledByThePlayerChanged; Character.UpdateCharacterPanelInfo; Encounter.AddParticipant [local: raised when player/agent objects are created (probable)]; Encounter.RemoveParticipant [local: object destroyed (probable)]; Encounter.UI_UpdateMatchScorecard; UI.DefeatStatusUpdatedForEntity [n:0x100000bc]; UI.gmWErrorMessageOccurred; Upgrade.UpdateCurrentUpgrades [0x20e2]; Upgrade.UpdatePowerGraphValues [0x20e2]; ViewMatch.ViewMatchScoreboardData | GM_Artifact.?InqKillCardArtifactTooltip; GM_Character.?InqCharacterPanelInfo; GM_Character.?InqCharacterPanelMetaData; GM_Encounter.RequestMatchScorecard; GM_Lobby.?RequestTeamNames [0x20fd]; GM_Skill.?InqSkillToolTipInfo; GM_Skill.?RequestStolenPowersForCharacter; GM_Upgrade.RequestSendEveryonesUpgrades; GM_ViewMatch.?RequestInViewMatchMode; GM_ViewMatch.?RequestTeamGhostedAs |
| `0x20000070` | `026adcd8` | tutorial hints | 5 | Tutorial.UI_CloseTutorialHint [n:0x100004a5 (u32, same reader block; probable)]; Tutorial.UI_ShowTutorialHint [n:0x1000027f (hint id + force flag; C++ fills the texts)]; Tutorial.UI_ShowTutorialHints [n:0x10000288 (list<u32>; probable)] | GM_Tutorial.UIReadyForTutorialHints |
| `0x20000073` | `026b71ac` | browser / social media test (dev) | 3 | SocialMedia.UI_OnSocialMediaURLUpdated; UI.ActionEnumEvent; WebBrowser.OnAddressChange; WebBrowser.OnConsoleMessage; WebBrowser.OnJavaScriptAlert; WebBrowser.OnJavaScriptCallback; WebBrowser.OnJavaScriptContextCreated; WebBrowser.OnLoadEnd; WebBrowser.OnLoadStart; WebBrowser.OnNavStateChange; WebBrowser.OnPopUpWindowRequested; WebBrowser.OnTitleChange | EM_SocialMedia.UI_RequestSocialMediaURL |
| `0x20000074` | `026baefc` | new player screen | 3 | Achievement.AchievementDetails; Achievement.AllPendingAchivementBanners [0x211f]; Achievement.SetAchievementData [local: built from achievement records after 0x2120 (guess)]; Achievement.SetAchievementObjectiveData [0x2120 0x21a6]; Achievement.SetDeprecatedAchievements [0x2120 0x21a6]; Achievement.TraineeAchievements; Character.RewardSetsData [0x2125 0x2197]; Character.Ribbon_CharacterLevelChanged [0x2104]; Character.Ribbon_FinishedItemsFulfilled [0x2095]; Character.Ribbon_ItemFulfilled [0x2095]; Character.SendAccountCurrencyBalance [0x2081]; Character.SendAccountLevelAndXP [0x2080]; Chat.UI_ShowWrapperGeneralChatWindow; CustomMatch.UI_CustomMatch_Cancelled [0x2011]; CustomMatch.UI_CustomMatch_Kicked [0x2041]; CustomMatch.UI_CustomMatch_Left [0x203f]; Encounter.ResetMapSelectionList [0x2024 0x20ff]; Grouping.PlayerLeftGroup [0x2071]; Lobby.LobbyRejoinRoom [0x205b]; UI.ActionEnumEvent; UI.BarredFromMatching [0x20f3]; UI.DisplayDialogText [0x2087 0x20ed 0x210a 0x210b]; UI.FoundMatch [0x20fa]; UI.JoinedQueue [0x20c0]; UI.PendingMatchFailure [0x20d7 0x210b]; UI.ProtectorAdvancementStatus [0x215d (account flags; probable)]; UI.QueueEligibility [0x2101]; UI.RemovedFromQueue [0x20e0 0x210b]; UI.ShowURLDialog; UI.ToggleMainMenu; UI.UIStateMachineEvent [0x2038 0x2053]; UI.UserCanCreateGroup [0x2070] | EM_WebBrowser.?InqFoundCEF3SubprocessExecutable; GM_Achievement.RequestAchievementDetails; GM_Achievement.RequestAllAchievementData [0x211d]; GM_Achievement.RequestAllPendingRewardlessAchievementNotifications [0x212e]; GM_Achievement.RequestTraineeAchievements; GM_Character.RequestAccountCurrencyBalance; GM_Character.RequestAccountLevelAndXP; GM_Character.RequestPostMatchChanges [0x20ba]; GM_Character.Ribbon_ReceivedItemsFulfilled; GM_Character.UI_RequestPendingRewardUpdateFromServer [0x2124]; GM_Chat.HideChatForBrowser; GM_Chat.HideChatWindow; GM_Chat.RestoreChatForBrowser; GM_Chat.ShowChatWindow; GM_ConnectionManager.ResetLastConnectionErrorString; GM_ConnectionManager.?CheckLobbyConnection; GM_ConnectionManager.?InqLastConnectionErrorString; GM_Contacts.?UI_CanInviteSteamFriends; GM_CustomMatch.?IsInCustomMatch [0x20fb]; GM_Dialog.SetUIDialogIdleState; GM_Dialog.SetUIDialogInQueueState; GM_Encounter.?InqPVPEncounters; GM_UI.DisplayPendingDodgePenaltyNotifications [0x21a8]; GM_UI.DisplayedTutorialTakeover; GM_UI.JoinQueue [0x20eb]; GM_UI.JoinQueueForPromotedMap [0x20eb]; GM_UI.RequestProtectorAdvancementStatus; GM_UI.UIStateMachineEvent; GM_UI.?InqQueueEligibility; GM_UI.?IsAdmin; GM_UI.?IsLoggedIntoGame; GM_UI.?NeedsUpdateNews; GM_ViewMatch.?RequestInViewMatchModeLastMatch |
| `0x20000075` | `026cd8f8` | wrapper main (out-of-match shell; imports every wrapper screen) | 3 | Achievement.AllPendingAchivementBanners [0x211f]; Achievement.SetAchievementData [local: built from achievement records after 0x2120 (guess)]; Achievement.SetAchievementObjectiveData [0x2120 0x21a6]; Achievement.SetDeprecatedAchievements [0x2120 0x21a6]; Achievement.TraineeAchievements; AdminAlert.UI_NotifyAdminAlertsUpdated; Character.RewardSetsData [0x2125 0x2197]; Character.Ribbon_CharacterLevelChanged [0x2104]; Character.Ribbon_FinishedItemsFulfilled [0x2095]; Character.Ribbon_ItemFulfilled [0x2095]; Character.SendAccountCurrencyBalance [0x2081]; Character.SendAccountEndOfMatchAccoladesEarned [0x2104 0x2188]; Character.SendAccountEndOfMatchCharacterLevelAndXP [0x2104]; Character.SendAccountEndOfMatchLevelAndXP [0x2080]; Character.SendAccountEndOfMatchSoftCurrencyReward [0x20b9]; Character.SendAccountLevelAndXP [0x2080]; Chat.ToggleUnreadChat [0x20b0 0x20b6]; Chat.UI_ShowWrapperGeneralChatWindow; Contacts.UI_ContactListNotification [0x2065]; Contacts.UI_NotifyContactAccountIconChanged [0x20ec]; Contacts.UI_NotifyContactAdded [0x2051 0x20cc]; Contacts.UI_NotifyContactChangeNote [0x208f]; Contacts.UI_NotifyContactChangeStatusMessage [0x20c5]; Contacts.UI_NotifyContactChangeSteamName; Contacts.UI_NotifyContactChangedGroup [0x20cb]; Contacts.UI_NotifyContactGroupCreated [0x2014]; Contacts.UI_NotifyContactGroupDestroyed [0x205e]; Contacts.UI_NotifyContactIgnored [0x2051]; Contacts.UI_NotifyContactList [0x203b (layout, probable)]; Contacts.UI_NotifyContactOfInvitations [0x219c]; Contacts.UI_NotifyContactOfInvite [0x2003]; Contacts.UI_NotifyContactOfPendingInvites [0x2013]; Contacts.UI_NotifyContactPresenceChanged [0x2018 0x20ae]; Contacts.UI_NotifyContactRemoved [0x2020 0x2051 0x20cc]; Contacts.UI_NotifyContactUnignored [0x204f 0x20cc]; Contextual.PurchaseContextualItemError [0x210d]; Contextual.PurchaseContextualItemSuccess [0x210c]; CustomMatch.UI_CustomMatch_Cancelled [0x2011]; CustomMatch.UI_CustomMatch_InviteCancelled [0x2027]; CustomMatch.UI_CustomMatch_Invited [0x201f]; CustomMatch.UI_CustomMatch_Kicked [0x2041]; CustomMatch.UI_CustomMatch_Left [0x203f]; CustomMatch.UI_CustomMatch_SetDraftMode [0x2103]; CustomMatch.UI_CustomMatch_SetEncounter [0x2109]; CustomMatch.UI_CustomMatch_SetTeamName [0x2151]; CustomMatch.UI_CustomMatch_UpdateProtectorIcon [0x217c]; CustomMatch.UI_DeliverCustomMatchData [client cache of the room (0x2012 0x2035 0x2036 0x2048 0x205d 0x2076 have no Flash listener of their own; probable)]; Encounter.ResetMapSelectionList [0x2024 0x20ff]; Encounter.UI_SendEndOfMatchStats [0x2045 (progression-meta)]; Encounter.UI_SetEndOfMatchStatsHeader [0x2028 0x2045]; Grouping.GroupInviteCanceled [0x214c]; Grouping.PlayerLeftGroup [0x2071]; Grouping.ShowGroupInviteDialog [0x2033]; KeyBinding.UI_KeyBindingData; KeyBinding.UI_UpdateKeyBinding; Lobby.ClearLightResourcePackReferences [0x2021 0x2028 0x204b 0x206c]; Lobby.Draft_Banning; Lobby.Draft_TradeRequest [0x2054]; Lobby.LobbyEncounterDetails [0x204c]; Lobby.LobbyRejoinRoom [0x205b]; Lobby.MatchLaunchWarning [0x204b]; Lobby.PlayerPickedAmplifierSet [0x2029 0x204a 0x2060]; Lobby.PlayerPickedStolenPowers [0x2004 0x2029 0x2060]; Lobby.UpdateEarlyLaunchTime [0x2061]; Lobby.UpdateLobbyLoadingPercent [0x2031]; Lobby.UpdateLobbyLoadingPercentForViewmatch [0x206d]; Lobby.UpdateLobbyState [0x2060 (layout match)]; Lobby.UpdateLobbyStateSingle [0x2029 0x204c 0x2060]; UI.ActionEnumEvent; UI.BarredFromMatching [0x20f3]; UI.BatchNotifyHUDElements [0x213e]; UI.ClientLanguage; UI.DisplayDialogText [0x2087 0x20ed 0x210a 0x210b]; UI.FoundMatch [0x20fa]; UI.GameFrontUIDestroyedInCPP [0x2021]; UI.JoinedQueue [0x20c0]; UI.NotifyHUDElement [0x213d]; UI.PendingMatchFailure [0x20d7 0x210b]; UI.ProtectorAdvancementStatus [0x215d (account flags; probable)]; UI.QueueEligibility [0x2101]; UI.ReleaseNotesUrl; UI.RemovedFromQueue [0x20e0 0x210b]; UI.SendHeaderNameAndProtectorIcons [0x2154 0x2190]; UI.ShowURLDialog; UI.ToggleMainMenu; UI.UIStateMachineEvent [0x2038 0x2053]; UI.UI_DeliverAccountStandingsData [0x219e 0x219f]; UI.UI_DeliverStaticStandingsData [0x219e/0x219f (one of)]; UI.UserCanCreateGroup [0x2070]; UI.gmWErrorMessageOccurred; Upgrade.UpdateCurrentUpgrades [0x20e2]; Upgrade.UpdatePowerGraphValues [0x20e2]; WebTicket.UI_OnWebTicketUpdated | EM_UI.ForceOnSized; EM_WebBrowser.?InqFoundCEF3SubprocessExecutable; EM_WebTicket.UI_RequestWebTicket; GM_Achievement.RequestAllAchievementData [0x211d]; GM_Achievement.RequestAllPendingRewardlessAchievementNotifications [0x212e]; GM_Achievement.RequestTraineeAchievements; GM_AdminAlert.UI_RequestAdminAlerts; GM_Amplifier.UI_RequestAllAmplifierBoutiqueData; GM_Amplifier.UI_RequestAllAmplifierSets; GM_Amplifier.UI_SaveAmplifierSet [0x20fc (probable: same fields)]; GM_Amplifier.?UI_InqAmplifierSetIcons; GM_Amplifier.?UI_InqAmplifierSetSlotInfo; GM_Amplifier.?UI_InqAugmentModStoreUrls; GM_Amplifier.?UI_InqAugmentsPassingFilter; GM_Amplifier.?UI_InqModsPassingFilter; GM_Character.RequestAccountCurrencyBalance; GM_Character.RequestAccountCurrencyBalanceChanges; GM_Character.RequestAccountEndOfMatchAccoladesEarned; GM_Character.RequestAccountEndOfMatchAccountLevelAndXP; GM_Character.RequestAccountEndOfMatchCharacterLevelAndXP; GM_Character.RequestAccountEndOfMatchSoftCurrencyReward; GM_Character.RequestAccountLevelAndXP; GM_Character.RequestPostMatchChanges [0x20ba]; GM_Character.Ribbon_ReceivedItemsFulfilled; GM_Character.UI_RequestPendingRewardUpdateFromServer [0x2124]; GM_Chat.HideChatForBrowser; GM_Chat.HideChatWindow; GM_Chat.RestoreChatForBrowser; GM_Chat.ShowChatWindow; GM_ConnectionManager.ResetLastConnectionErrorString; GM_ConnectionManager.?CheckLobbyConnection; GM_ConnectionManager.?InqLastConnectionErrorString; GM_Contacts.UI_ContactList_Ready; GM_Contacts.?UI_CanInviteSteamFriends; GM_CustomMatch.RequestCustomMatchData [0x2066]; GM_CustomMatch.?IsInCustomMatch [0x20fb]; GM_Dialog.PlayUIDialogElement; GM_Dialog.SetUIDialogIdleState; GM_Dialog.SetUIDialogInQueueState; GM_Encounter.RequestPostMatchScorecard; GM_Encounter.UI_Mission_RaiseEvent; GM_Encounter.?InqPVPEncounters; GM_Grouping.?IsInGroup; GM_KeyBinding.UI_RequestKeyBindingData; GM_Lobby.Draft_TradeResponse; GM_Lobby.LobbyUIReady [0x202d]; GM_Lobby.PlayerSelectedEarlyLaunch [0x206a]; GM_Lobby.?RequestTeamNames [0x20fd]; GM_Options.SetBoolOption; GM_Options.?GetBoolOption; GM_Options.?GetUIConversationGroupScalingOption; GM_UI.ConnectToGameServer; GM_UI.DisplayPendingDodgePenaltyNotifications [0x21a8]; GM_UI.InGameMenuClosed; GM_UI.InGameMenuOpened; GM_UI.JoinQueue [0x20eb]; GM_UI.JoinQueueForPromotedMap [0x20eb]; GM_UI.OpenURL; GM_UI.RequestAccountStandingsData [0x2178 (probable)]; GM_UI.RequestClientLanguage; GM_UI.RequestExitGame; GM_UI.RequestHeaderUIData; GM_UI.RequestProtectorAdvancementStatus; GM_UI.RequestReleaseNotesURL; GM_UI.RequestStaticStandingsData [0x2193 (probable)]; GM_UI.ShowHelp; GM_UI.UIStateMachineEvent; GM_UI.?InqChatButtonTooltip; GM_UI.?InqQueueEligibility; GM_UI.?InqWrapperDisplayData; GM_UI.?IsBinkFileValid; GM_UI.?IsLoggedIntoGame; GM_UI.?NeedsUpdateNews; GM_ViewMatch.?RequestInViewMatchMode; GM_ViewMatch.?RequestInViewMatchModeLastMatch |
| `0x20000077` | `026d5430` | wrapper header (profile, currency, matchmaking indicator) | 18 | Achievement.AllPendingAchivementBanners [0x211f]; Achievement.SetAchievementData [local: built from achievement records after 0x2120 (guess)]; Achievement.SetAchievementObjectiveData [0x2120 0x21a6]; Achievement.SetDeprecatedAchievements [0x2120 0x21a6]; Achievement.TraineeAchievements; AdminAlert.UI_NotifyAdminAlertsUpdated; Character.RewardSetsData [0x2125 0x2197]; Character.Ribbon_CharacterLevelChanged [0x2104]; Character.Ribbon_FinishedItemsFulfilled [0x2095]; Character.Ribbon_ItemFulfilled [0x2095]; Character.SendAccountCurrencyBalance [0x2081]; Character.SendAccountLevelAndXP [0x2080]; Contextual.PurchaseContextualItemError [0x210d]; Contextual.PurchaseContextualItemSuccess [0x210c]; CustomMatch.UI_CustomMatch_Cancelled [0x2011]; CustomMatch.UI_CustomMatch_Kicked [0x2041]; CustomMatch.UI_CustomMatch_Left [0x203f]; CustomMatch.UI_CustomMatch_SetDraftMode [0x2103]; CustomMatch.UI_CustomMatch_SetEncounter [0x2109]; CustomMatch.UI_CustomMatch_SetTeamName [0x2151]; CustomMatch.UI_CustomMatch_UpdateProtectorIcon [0x217c]; CustomMatch.UI_DeliverCustomMatchData [client cache of the room (0x2012 0x2035 0x2036 0x2048 0x205d 0x2076 have no Flash listener of their own; probable)]; Encounter.ResetMapSelectionList [0x2024 0x20ff]; Grouping.GroupInformation [0x2071 (layout, probable)]; Grouping.PlayerLeftGroup [0x2071]; Grouping.UI_Grouping_UpdateProtectorIcon [0x217d]; Lobby.LobbyRejoinRoom [0x205b]; UI.ActionEnumEvent; UI.BarredFromMatching [0x20f3]; UI.DisplayDialogText [0x2087 0x20ed 0x210a 0x210b]; UI.FindMatchFailure [0x218d]; UI.FoundMatch [0x20fa]; UI.JoinedQueue [0x20c0]; UI.Matchmaking_NewUpdateInterval [0x218e]; UI.PendingMatchFailure [0x20d7 0x210b]; UI.ProtectorAdvancementStatus [0x215d (account flags; probable)]; UI.QueueEligibility [0x2101]; UI.QueueWaitTimesUpdated [0x218f]; UI.RemovedFromQueue [0x20e0 0x210b]; UI.SendHeaderNameAndProtectorIcons [0x2154 0x2190]; UI.ShowURLDialog; UI.ToggleMainMenu; UI.UIStateMachineEvent [0x2038 0x2053]; UI.UI_DeliverAccountStandingsData [0x219e 0x219f]; UI.UI_DeliverStaticStandingsData [0x219e/0x219f (one of)]; UI.UserCanCreateGroup [0x2070]; WebTicket.UI_OnWebTicketUpdated | EM_WebBrowser.?InqFoundCEF3SubprocessExecutable; EM_WebTicket.UI_RequestWebTicket; GM_Achievement.RequestAllAchievementData [0x211d]; GM_Achievement.RequestAllPendingRewardlessAchievementNotifications [0x212e]; GM_Achievement.RequestTraineeAchievements; GM_AdminAlert.UI_RequestAdminAlerts; GM_Amplifier.UI_RequestAllAmplifierBoutiqueData; GM_Amplifier.UI_RequestAllAmplifierSets; GM_Amplifier.UI_SaveAmplifierSet [0x20fc (probable: same fields)]; GM_Amplifier.?UI_InqAmplifierSetIcons; GM_Amplifier.?UI_InqAmplifierSetSlotInfo; GM_Amplifier.?UI_InqAugmentModStoreUrls; GM_Amplifier.?UI_InqAugmentsPassingFilter; GM_Amplifier.?UI_InqModsPassingFilter; GM_Character.RequestAccountCurrencyBalance; GM_Character.RequestAccountLevelAndXP; GM_Character.RequestPostMatchChanges [0x20ba]; GM_Character.Ribbon_ReceivedItemsFulfilled; GM_Character.UI_RequestPendingRewardUpdateFromServer [0x2124]; GM_Chat.RunCmd; GM_ConnectionManager.ResetLastConnectionErrorString; GM_ConnectionManager.?CheckLobbyConnection; GM_ConnectionManager.?InqLastConnectionErrorString; GM_Contacts.UI_InviteContact; GM_Contacts.?UI_CanInviteSteamFriends; GM_CustomMatch.RequestCustomMatchData [0x2066]; GM_CustomMatch.?IsInCustomMatch [0x20fb]; GM_Dialog.PlayUIDialogElement; GM_Dialog.SetUIDialogIdleState; GM_Dialog.SetUIDialogInQueueState; GM_Encounter.?InqPVPEncounters; GM_Grouping.LeaveGroup; GM_Grouping.OnGroupPage; GM_Grouping.RequestGroupInformation; GM_Grouping.?IsInGroup; GM_Lobby.AttemptToRejoinLobbyRoom; GM_Lobby.?RequestTeamNames [0x20fd]; GM_UI.DisplayPendingDodgePenaltyNotifications [0x21a8]; GM_UI.ForceQueue; GM_UI.InGameMenuClosed; GM_UI.InGameMenuOpened; GM_UI.JoinQueue [0x20eb]; GM_UI.JoinQueueForPromotedMap [0x20eb]; GM_UI.LeaveQueue [0x20c3]; GM_UI.RequestAccountStandingsData [0x2178 (probable)]; GM_UI.RequestExitGame; GM_UI.RequestHeaderUIData; GM_UI.RequestProtectorAdvancementStatus; GM_UI.RequestStaticStandingsData [0x2193 (probable)]; GM_UI.ShowHelp; GM_UI.UIStateMachineEvent; GM_UI.?GetWaitTimeForQueue; GM_UI.?InqAccountMeritBonus; GM_UI.?InqQueueEligibility; GM_UI.?IsBinkFileValid; GM_UI.?IsLoggedIntoGame; GM_UI.?NeedsUpdateNews; GM_ViewMatch.?RequestInViewMatchModeLastMatch |
| `0x20000078` | `026e4704` | landing (home) screen | 8 | Achievement.AchievementDetails; Achievement.AllPendingAchivementBanners [0x211f]; Achievement.SetAchievementData [local: built from achievement records after 0x2120 (guess)]; Achievement.SetAchievementObjectiveData [0x2120 0x21a6]; Achievement.SetDeprecatedAchievements [0x2120 0x21a6]; Achievement.TraineeAchievements; Character.RewardSetsData [0x2125 0x2197]; Character.Ribbon_CharacterLevelChanged [0x2104]; Character.Ribbon_FinishedItemsFulfilled [0x2095]; Character.Ribbon_ItemFulfilled [0x2095]; Character.SendAccountCurrencyBalance [0x2081]; Character.SendAccountLevelAndXP [0x2080]; Chat.UI_ShowWrapperGeneralChatWindow; CustomMatch.UI_CustomMatch_Cancelled [0x2011]; CustomMatch.UI_CustomMatch_Kicked [0x2041]; CustomMatch.UI_CustomMatch_Left [0x203f]; CustomMatch.UI_CustomMatch_SetDraftMode [0x2103]; CustomMatch.UI_CustomMatch_SetEncounter [0x2109]; CustomMatch.UI_CustomMatch_SetTeamName [0x2151]; CustomMatch.UI_CustomMatch_UpdateProtectorIcon [0x217c]; CustomMatch.UI_DeliverCustomMatchData [client cache of the room (0x2012 0x2035 0x2036 0x2048 0x205d 0x2076 have no Flash listener of their own; probable)]; Encounter.ResetMapSelectionList [0x2024 0x20ff]; Grouping.PlayerLeftGroup [0x2071]; Lobby.LobbyRejoinRoom [0x205b]; UI.ActionEnumEvent; UI.BarredFromMatching [0x20f3]; UI.DisplayDialogText [0x2087 0x20ed 0x210a 0x210b]; UI.FoundMatch [0x20fa]; UI.JoinedQueue [0x20c0]; UI.PendingMatchFailure [0x20d7 0x210b]; UI.ProtectorAdvancementStatus [0x215d (account flags; probable)]; UI.QueueEligibility [0x2101]; UI.RemovedFromQueue [0x20e0 0x210b]; UI.SendHeaderNameAndProtectorIcons [0x2154 0x2190]; UI.ShowURLDialog; UI.ToggleMainMenu; UI.UIStateMachineEvent [0x2038 0x2053]; UI.UserCanCreateGroup [0x2070] | EM_WebBrowser.?InqFoundCEF3SubprocessExecutable; GM_Achievement.RequestAchievementDetails; GM_Achievement.RequestAllAchievementData [0x211d]; GM_Achievement.RequestAllPendingRewardlessAchievementNotifications [0x212e]; GM_Achievement.RequestTraineeAchievements; GM_Character.RequestAccountCurrencyBalance; GM_Character.RequestAccountLevelAndXP; GM_Character.RequestPostMatchChanges [0x20ba]; GM_Character.Ribbon_ReceivedItemsFulfilled; GM_Character.UI_RequestPendingRewardUpdateFromServer [0x2124]; GM_Chat.HideChatForBrowser; GM_Chat.HideChatWindow; GM_Chat.RestoreChatForBrowser; GM_Chat.ShowChatWindow; GM_ConnectionManager.ResetLastConnectionErrorString; GM_ConnectionManager.?CheckLobbyConnection; GM_ConnectionManager.?InqLastConnectionErrorString; GM_Contacts.?UI_CanInviteSteamFriends; GM_CustomMatch.RequestCustomMatchData [0x2066]; GM_CustomMatch.?IsInCustomMatch [0x20fb]; GM_Dialog.SetUIDialogIdleState; GM_Dialog.SetUIDialogInQueueState; GM_Encounter.PlayedEncounterOverviewMovie; GM_Encounter.?InqPVPEncounters; GM_Grouping.?IsInGroup; GM_Lobby.?RequestTeamNames [0x20fd]; GM_UI.DisplayPendingDodgePenaltyNotifications [0x21a8]; GM_UI.InGameMenuClosed; GM_UI.InGameMenuOpened; GM_UI.JoinQueue [0x20eb]; GM_UI.JoinQueueForPromotedMap [0x20eb]; GM_UI.RequestHeaderUIData; GM_UI.RequestProtectorAdvancementStatus; GM_UI.UIStateMachineEvent; GM_UI.UserActionMetric [0x218c]; GM_UI.?InqQueueEligibility; GM_UI.?IsBinkFileValid; GM_UI.?IsLoggedIntoGame; GM_UI.?NeedsUpdateNews; GM_ViewMatch.?RequestInViewMatchModeLastMatch |
| `0x2000007c` | `026edeb8` | store (web) | 5 | Achievement.AllPendingAchivementBanners [0x211f]; Character.RewardSetsData [0x2125 0x2197]; Character.Ribbon_CharacterLevelChanged [0x2104]; Character.Ribbon_FinishedItemsFulfilled [0x2095]; Character.Ribbon_ItemFulfilled [0x2095]; Character.SendAccountCurrencyBalance [0x2081]; Character.SendAccountLevelAndXP [0x2080]; Chat.UI_ShowWrapperGeneralChatWindow; CustomMatch.UI_CustomMatch_Cancelled [0x2011]; CustomMatch.UI_CustomMatch_Kicked [0x2041]; CustomMatch.UI_CustomMatch_Left [0x203f]; Grouping.PlayerLeftGroup [0x2071]; Lobby.LobbyRejoinRoom [0x205b]; UI.ActionEnumEvent; UI.BarredFromMatching [0x20f3]; UI.DisplayDialogText [0x2087 0x20ed 0x210a 0x210b]; UI.FoundMatch [0x20fa]; UI.JoinedQueue [0x20c0]; UI.PendingMatchFailure [0x20d7 0x210b]; UI.ProtectorAdvancementStatus [0x215d (account flags; probable)]; UI.RemovedFromQueue [0x20e0 0x210b]; UI.ShowURLDialog; UI.ToggleMainMenu; UI.UIStateMachineEvent [0x2038 0x2053]; UI.UserCanCreateGroup [0x2070]; WebBrowser.OnJavaScriptCallback; WebBrowser.OnJavaScriptContextCreated; WebBrowser.OnLoadEnd; WebBrowser.OnLoadStart; WebTicket.UI_OnMicroTxnAuthorizationResponse; WebTicket.UI_OnWebTicketUpdated | EM_WebBrowser.?InqFoundCEF3SubprocessExecutable; EM_WebTicket.UI_RequestWebTicket; GM_Achievement.RequestAllPendingRewardlessAchievementNotifications [0x212e]; GM_Character.RequestAccountCurrencyBalance; GM_Character.RequestAccountLevelAndXP; GM_Character.RequestPostMatchChanges [0x20ba]; GM_Character.Ribbon_ReceivedItemsFulfilled; GM_Character.UI_RequestPendingRewardUpdateFromServer [0x2124]; GM_Chat.HideChatForBrowser; GM_Chat.HideChatWindow; GM_Chat.RestoreChatForBrowser; GM_Chat.ShowChatWindow; GM_ConnectionManager.ResetLastConnectionErrorString; GM_ConnectionManager.?CheckLobbyConnection; GM_ConnectionManager.?InqLastConnectionErrorString; GM_Contacts.?UI_CanInviteSteamFriends; GM_CustomMatch.?IsInCustomMatch [0x20fb]; GM_Dialog.SetUIDialogIdleState; GM_Dialog.SetUIDialogInQueueState; GM_UI.DisplayPendingDodgePenaltyNotifications [0x21a8]; GM_UI.InGameMenuClosed; GM_UI.InGameMenuOpened; GM_UI.JoinQueue [0x20eb]; GM_UI.JoinQueueForPromotedMap [0x20eb]; GM_UI.RequestProtectorAdvancementStatus; GM_UI.UIStateMachineEvent; GM_UI.?InqStoreURL; GM_UI.?IsBinkFileValid; GM_UI.?IsLoggedIntoGame; GM_UI.?NeedsUpdateNews; GM_ViewMatch.?RequestInViewMatchModeLastMatch |
| `0x2000007f` | `026f3910` | landing demo | 3 | Achievement.AllPendingAchivementBanners [0x211f]; Character.RewardSetsData [0x2125 0x2197]; Character.Ribbon_CharacterLevelChanged [0x2104]; Character.Ribbon_FinishedItemsFulfilled [0x2095]; Character.Ribbon_ItemFulfilled [0x2095]; Character.SendAccountCurrencyBalance [0x2081]; Character.SendAccountLevelAndXP [0x2080]; Chat.UI_ShowWrapperGeneralChatWindow; CustomMatch.UI_CustomMatch_Cancelled [0x2011]; CustomMatch.UI_CustomMatch_Kicked [0x2041]; CustomMatch.UI_CustomMatch_Left [0x203f]; Encounter.ResetMapSelectionList [0x2024 0x20ff]; Grouping.PlayerLeftGroup [0x2071]; Lobby.LobbyRejoinRoom [0x205b]; UI.ActionEnumEvent; UI.BarredFromMatching [0x20f3]; UI.DisplayDialogText [0x2087 0x20ed 0x210a 0x210b]; UI.FoundMatch [0x20fa]; UI.JoinedQueue [0x20c0]; UI.PendingMatchFailure [0x20d7 0x210b]; UI.ProtectorAdvancementStatus [0x215d (account flags; probable)]; UI.QueueEligibility [0x2101]; UI.RemovedFromQueue [0x20e0 0x210b]; UI.ShowURLDialog; UI.ToggleMainMenu; UI.UIStateMachineEvent [0x2038 0x2053]; UI.UserCanCreateGroup [0x2070] | EM_WebBrowser.?InqFoundCEF3SubprocessExecutable; GM_Achievement.RequestAllPendingRewardlessAchievementNotifications [0x212e]; GM_Character.RequestAccountCurrencyBalance; GM_Character.RequestAccountLevelAndXP; GM_Character.RequestPostMatchChanges [0x20ba]; GM_Character.Ribbon_ReceivedItemsFulfilled; GM_Character.UI_RequestPendingRewardUpdateFromServer [0x2124]; GM_Chat.HideChatForBrowser; GM_Chat.HideChatWindow; GM_Chat.RestoreChatForBrowser; GM_Chat.ShowChatWindow; GM_ConnectionManager.ResetLastConnectionErrorString; GM_ConnectionManager.?CheckLobbyConnection; GM_ConnectionManager.?InqLastConnectionErrorString; GM_Contacts.?UI_CanInviteSteamFriends; GM_CustomMatch.?IsInCustomMatch [0x20fb]; GM_Dialog.SetUIDialogIdleState; GM_Dialog.SetUIDialogInQueueState; GM_Encounter.?InqPVPEncounters; GM_UI.DisplayPendingDodgePenaltyNotifications [0x21a8]; GM_UI.JoinQueue [0x20eb]; GM_UI.JoinQueueForPromotedMap [0x20eb]; GM_UI.RequestProtectorAdvancementStatus; GM_UI.UIStateMachineEvent; GM_UI.?InqQueueEligibility; GM_UI.?IsLoggedIntoGame; GM_UI.?NeedsUpdateNews; GM_ViewMatch.?RequestInViewMatchModeLastMatch |
| `0x20000080` | `026f8554` | dialogs (purchase, confirm, report, group invite, calling card...) | 25 | Achievement.AllPendingAchivementBanners [0x211f]; Character.RewardSetsData [0x2125 0x2197]; Character.Ribbon_CharacterLevelChanged [0x2104]; Character.Ribbon_FinishedItemsFulfilled [0x2095]; Character.Ribbon_ItemFulfilled [0x2095]; Character.SendAccountCurrencyBalance [0x2081]; Character.SendAccountLevelAndXP [0x2080]; Chat.UI_ShowWrapperGeneralChatWindow; CustomMatch.UI_CustomMatch_Cancelled [0x2011]; CustomMatch.UI_CustomMatch_Kicked [0x2041]; CustomMatch.UI_CustomMatch_Left [0x203f]; Grouping.PlayerLeftGroup [0x2071]; Lobby.LobbyRejoinRoom [0x205b]; UI.ActionEnumEvent; UI.AvailableCharacterList [0x20b8]; UI.BarredFromMatching [0x20f3]; UI.CharacterAdvancementData [0x209d (layout match)]; UI.DisplayDialogText [0x2087 0x20ed 0x210a 0x210b]; UI.FoundMatch [0x20fa]; UI.Incremental_ItemStatuses [0x204c 0x20b8]; UI.ItemStatuses [0x20b8]; UI.JoinedQueue [0x20c0]; UI.PendingMatchFailure [0x20d7 0x210b]; UI.ProtectorAdvancementStatus [0x215d (account flags; probable)]; UI.RemovedFromQueue [0x20e0 0x210b]; UI.SendHeaderNameAndProtectorIcons [0x2154 0x2190]; UI.ShowURLDialog; UI.ToggleMainMenu; UI.UIStateMachineEvent [0x2038 0x2053]; UI.UserCanCreateGroup [0x2070]; WebBrowser.OnJavaScriptCallback; WebBrowser.OnJavaScriptContextCreated; WebBrowser.OnLoadEnd; WebBrowser.OnLoadStart | EM_UI.ForceOnSized; EM_WebBrowser.?InqFoundCEF3SubprocessExecutable; GM_Achievement.RequestAllPendingRewardlessAchievementNotifications [0x212e]; GM_Character.RequestAccountCurrencyBalance; GM_Character.RequestAccountLevelAndXP; GM_Character.RequestPostMatchChanges [0x20ba]; GM_Character.Ribbon_ReceivedItemsFulfilled; GM_Character.UI_RequestPendingRewardUpdateFromServer [0x2124]; GM_Character.UI_SetProtectorIcon [0x2093]; GM_Character.?RequestProtectorIcons; GM_Chat.HideChatForBrowser; GM_Chat.HideChatWindow; GM_Chat.RestoreChatForBrowser; GM_Chat.RunCmd; GM_Chat.ShowChatWindow; GM_ConnectionManager.ResetLastConnectionErrorString; GM_ConnectionManager.?CheckLobbyConnection; GM_ConnectionManager.?InqLastConnectionErrorString; GM_Contacts.?UI_CanInviteSteamFriends; GM_Contextual.UI_PurchaseContextualItem; GM_CustomMatch.Cancel_CustomMatch; GM_CustomMatch.Leave_CustomMatch [0x20c6]; GM_CustomMatch.?IsInCustomMatch [0x20fb]; GM_Dialog.SetUIDialogIdleState; GM_Dialog.SetUIDialogInQueueState; GM_Grouping.ClearInvite; GM_PlayerReport.ReportAPlayer; GM_UI.AcknowledgeMajorUpdateNews; GM_UI.DisplayPendingDodgePenaltyNotifications [0x21a8]; GM_UI.InGameMenuClosed; GM_UI.InGameMenuOpened; GM_UI.JoinQueue [0x20eb]; GM_UI.JoinQueueForPromotedMap [0x20eb]; GM_UI.OnEndOfMatchMovieEnded; GM_UI.RequestCharacterAdvancementData; GM_UI.RequestItemStatuses; GM_UI.RequestProtectorAdvancementStatus; GM_UI.UIStateMachineEvent; GM_UI.?IsBinkFileValid; GM_UI.?IsLoggedIntoGame; GM_UI.?NeedsUpdateNews; GM_ViewMatch.?RequestInViewMatchMode; GM_ViewMatch.?RequestInViewMatchModeLastMatch |
| `0x20000082` | `02709080` | party / PvP group screen | 16 | Achievement.AllPendingAchivementBanners [0x211f]; Character.RewardSetsData [0x2125 0x2197]; Character.Ribbon_CharacterLevelChanged [0x2104]; Character.Ribbon_FinishedItemsFulfilled [0x2095]; Character.Ribbon_ItemFulfilled [0x2095]; Character.SendAccountCurrencyBalance [0x2081]; Character.SendAccountLevelAndXP [0x2080]; Chat.UI_ShowWrapperGeneralChatWindow; Contacts.UI_ContactListNotification [0x2065]; Contacts.UI_NotifyContactAdded [0x2051 0x20cc]; Contacts.UI_NotifyContactOfInvitations [0x219c]; Contacts.UI_NotifyContactOfInvite [0x2003]; Contacts.UI_NotifyContactOfPendingInvites [0x2013]; CustomMatch.UI_CustomMatch_Cancelled [0x2011]; CustomMatch.UI_CustomMatch_InviteCancelled [0x2027]; CustomMatch.UI_CustomMatch_Invited [0x201f]; CustomMatch.UI_CustomMatch_Kicked [0x2041]; CustomMatch.UI_CustomMatch_Left [0x203f]; Encounter.ResetMapSelectionList [0x2024 0x20ff]; Grouping.GroupInformation [0x2071 (layout, probable)]; Grouping.GroupInviteCanceled [0x214c]; Grouping.PlayerLeftGroup [0x2071]; Grouping.ShowGroupInviteDialog [0x2033]; Grouping.UI_Grouping_UpdateProtectorIcon [0x217d]; Lobby.ClearLightResourcePackReferences [0x2021 0x2028 0x204b 0x206c]; Lobby.Draft_Banning; Lobby.Draft_TradeRequest [0x2054]; Lobby.LobbyEncounterDetails [0x204c]; Lobby.LobbyRejoinRoom [0x205b]; Lobby.MatchLaunchWarning [0x204b]; Lobby.PlayerPickedAmplifierSet [0x2029 0x204a 0x2060]; Lobby.PlayerPickedStolenPowers [0x2004 0x2029 0x2060]; Lobby.UpdateEarlyLaunchTime [0x2061]; Lobby.UpdateLobbyLoadingPercent [0x2031]; Lobby.UpdateLobbyLoadingPercentForViewmatch [0x206d]; Lobby.UpdateLobbyState [0x2060 (layout match)]; Lobby.UpdateLobbyStateSingle [0x2029 0x204c 0x2060]; UI.ActionEnumEvent; UI.BarredFromMatching [0x20f3]; UI.BatchNotifyHUDElements [0x213e]; UI.DisplayDialogText [0x2087 0x20ed 0x210a 0x210b]; UI.FoundMatch [0x20fa]; UI.GameFrontUIDestroyedInCPP [0x2021]; UI.JoinedQueue [0x20c0]; UI.NotifyHUDElement [0x213d]; UI.PendingMatchFailure [0x20d7 0x210b]; UI.ProtectorAdvancementStatus [0x215d (account flags; probable)]; UI.QueueEligibility [0x2101]; UI.QueueWaitTimesUpdated [0x218f]; UI.RemovedFromQueue [0x20e0 0x210b]; UI.ShowURLDialog; UI.ToggleMainMenu; UI.UIStateMachineEvent [0x2038 0x2053]; UI.UserCanCreateGroup [0x2070] | EM_WebBrowser.?InqFoundCEF3SubprocessExecutable; GM_Achievement.RequestAllPendingRewardlessAchievementNotifications [0x212e]; GM_Character.RequestAccountCurrencyBalance; GM_Character.RequestAccountLevelAndXP; GM_Character.RequestPostMatchChanges [0x20ba]; GM_Character.Ribbon_ReceivedItemsFulfilled; GM_Character.UI_RequestPendingRewardUpdateFromServer [0x2124]; GM_Chat.HideChatForBrowser; GM_Chat.HideChatWindow; GM_Chat.RestoreChatForBrowser; GM_Chat.RunCmd; GM_Chat.ShowChatWindow; GM_ConnectionManager.ResetLastConnectionErrorString; GM_ConnectionManager.?CheckLobbyConnection; GM_ConnectionManager.?InqLastConnectionErrorString; GM_Contacts.UI_ContactList_Ready; GM_Contacts.UI_InviteContact; GM_Contacts.?UI_CanInviteSteamFriends; GM_CustomMatch.?IsInCustomMatch [0x20fb]; GM_Dialog.PlayUIDialogElement; GM_Dialog.SetUIDialogIdleState; GM_Dialog.SetUIDialogInQueueState; GM_Encounter.DisplayEncounterWebInfo; GM_Encounter.PlayedEncounterOverviewMovie; GM_Encounter.UI_Mission_RaiseEvent; GM_Encounter.?InqPVPEncounters; GM_Grouping.LeaveGroup; GM_Grouping.OnGroupPage; GM_Grouping.RequestGroupInformation; GM_Lobby.Draft_TradeResponse; GM_Lobby.LobbyUIReady [0x202d]; GM_Lobby.PlayerSelectedEarlyLaunch [0x206a]; GM_Lobby.?RequestTeamNames [0x20fd]; GM_Options.?GetUIConversationGroupScalingOption; GM_UI.DisplayPendingDodgePenaltyNotifications [0x21a8]; GM_UI.InGameMenuClosed; GM_UI.InGameMenuOpened; GM_UI.JoinQueue [0x20eb]; GM_UI.JoinQueueForPromotedMap [0x20eb]; GM_UI.RequestProtectorAdvancementStatus; GM_UI.UIStateMachineEvent; GM_UI.?GetWaitTimeForQueue; GM_UI.?InqQueueEligibility; GM_UI.?IsBinkFileValid; GM_UI.?IsLoggedIntoGame; GM_UI.?NeedsUpdateNews; GM_ViewMatch.?RequestInViewMatchMode; GM_ViewMatch.?RequestInViewMatchModeLastMatch |
| `0x20000083` | `02714fa0` | chat | 3 | Achievement.AllPendingAchivementBanners [0x211f]; Character.RewardSetsData [0x2125 0x2197]; Character.Ribbon_CharacterLevelChanged [0x2104]; Character.Ribbon_FinishedItemsFulfilled [0x2095]; Character.Ribbon_ItemFulfilled [0x2095]; Character.SendAccountCurrencyBalance [0x2081]; Character.SendAccountLevelAndXP [0x2080]; Chat.ToggleUnreadChat [0x20b0 0x20b6]; Chat.UI_ShowWrapperGeneralChatWindow; CustomMatch.UI_CustomMatch_Cancelled [0x2011]; CustomMatch.UI_CustomMatch_Kicked [0x2041]; CustomMatch.UI_CustomMatch_Left [0x203f]; Grouping.PlayerLeftGroup [0x2071]; Lobby.ClearLightResourcePackReferences [0x2021 0x2028 0x204b 0x206c]; Lobby.Draft_Banning; Lobby.Draft_TradeRequest [0x2054]; Lobby.LobbyEncounterDetails [0x204c]; Lobby.LobbyRejoinRoom [0x205b]; Lobby.MatchLaunchWarning [0x204b]; Lobby.PlayerPickedAmplifierSet [0x2029 0x204a 0x2060]; Lobby.PlayerPickedStolenPowers [0x2004 0x2029 0x2060]; Lobby.UpdateEarlyLaunchTime [0x2061]; Lobby.UpdateLobbyLoadingPercent [0x2031]; Lobby.UpdateLobbyLoadingPercentForViewmatch [0x206d]; Lobby.UpdateLobbyState [0x2060 (layout match)]; Lobby.UpdateLobbyStateSingle [0x2029 0x204c 0x2060]; UI.ActionEnumEvent; UI.BarredFromMatching [0x20f3]; UI.BatchNotifyHUDElements [0x213e]; UI.DisplayDialogText [0x2087 0x20ed 0x210a 0x210b]; UI.FoundMatch [0x20fa]; UI.GameFrontUIDestroyedInCPP [0x2021]; UI.JoinedQueue [0x20c0]; UI.NotifyHUDElement [0x213d]; UI.PendingMatchFailure [0x20d7 0x210b]; UI.ProtectorAdvancementStatus [0x215d (account flags; probable)]; UI.RemovedFromQueue [0x20e0 0x210b]; UI.ShowURLDialog; UI.ToggleMainMenu; UI.UIStateMachineEvent [0x2038 0x2053]; UI.UserCanCreateGroup [0x2070] | EM_WebBrowser.?InqFoundCEF3SubprocessExecutable; GM_Achievement.RequestAllPendingRewardlessAchievementNotifications [0x212e]; GM_Character.RequestAccountCurrencyBalance; GM_Character.RequestAccountLevelAndXP; GM_Character.RequestPostMatchChanges [0x20ba]; GM_Character.Ribbon_ReceivedItemsFulfilled; GM_Character.UI_RequestPendingRewardUpdateFromServer [0x2124]; GM_Chat.HideChatForBrowser; GM_Chat.HideChatWindow; GM_Chat.RestoreChatForBrowser; GM_Chat.ShowChatWindow; GM_ConnectionManager.ResetLastConnectionErrorString; GM_ConnectionManager.?CheckLobbyConnection; GM_ConnectionManager.?InqLastConnectionErrorString; GM_Contacts.?UI_CanInviteSteamFriends; GM_CustomMatch.?IsInCustomMatch [0x20fb]; GM_Dialog.PlayUIDialogElement; GM_Dialog.SetUIDialogIdleState; GM_Dialog.SetUIDialogInQueueState; GM_Encounter.UI_Mission_RaiseEvent; GM_Lobby.Draft_TradeResponse; GM_Lobby.LobbyUIReady [0x202d]; GM_Lobby.PlayerSelectedEarlyLaunch [0x206a]; GM_Lobby.?RequestTeamNames [0x20fd]; GM_Options.?GetUIConversationGroupScalingOption; GM_UI.DisplayPendingDodgePenaltyNotifications [0x21a8]; GM_UI.JoinQueue [0x20eb]; GM_UI.JoinQueueForPromotedMap [0x20eb]; GM_UI.RequestProtectorAdvancementStatus; GM_UI.UIStateMachineEvent; GM_UI.?InqChatButtonTooltip; GM_UI.?IsLoggedIntoGame; GM_UI.?NeedsUpdateNews; GM_ViewMatch.?RequestInViewMatchMode; GM_ViewMatch.?RequestInViewMatchModeLastMatch |
| `0x20000084` | `0271b90c` | artifact widgets (shared by foundry / skill bar) | 15 | Advancement.SkillRanked; Character.ActiveAgentControlledByThePlayerChanged; Character.AgentControlledByThePlayerChanged; Character.UpdateCharacterPanelInfo; Encounter.AddParticipant [local: raised when player/agent objects are created (probable)]; Encounter.RemoveParticipant [local: object destroyed (probable)]; Encounter.UI_UpdateHasVendorAccess; Encounter.UI_UpdateMatchScorecard; KeyBinding.UI_KeyBindingData; KeyBinding.UI_UpdateKeyBinding; Skill.EnableSkillButton [0x207b 0x20a0 0x2187]; Skill.UI_SkillUpdate; Skill.UpdateSkillUIOverlay [0x2091 n:0x1000015a]; UI.DefeatStatusUpdatedForEntity [n:0x100000bc]; UI.ExecuteSkillError [0x2092 0x20dc]; UI.StartSkillCooldown [0x20f8]; UI.UpdateSkillStackCountString [0x20a2 0x20a8 0x20c8]; UI.gmWErrorMessageOccurred; Upgrade.ActivatedArtifacts; Upgrade.ReturnedUpgradeArrayPreview; Upgrade.SetUIArtifactSkillSlotMapping; Upgrade.UI_RefreshPurchasability; Upgrade.UpdateCurrentUpgrades [0x20e2]; Upgrade.UpdateNextRecommendedUpgrade [0x2078]; Upgrade.UpdatePowerGraphValues [0x20e2]; ViewMatch.ViewMatchScoreboardData | GM_Artifact.?InqArtifactDetails; GM_Artifact.?InqAvailableArtifacts; GM_Artifact.?InqKillCardArtifactTooltip; GM_Artifact.?InqRecommendedArtifacts; GM_Artifact.?InqRemainingRecommendedArtifacts; GM_Character.?InqCharacterPanelInfo; GM_Character.?InqCharacterPanelMetaData; GM_Encounter.RequestMatchScorecard; GM_Encounter.UI_Mission_RaiseEvent; GM_Encounter.?InqCharacterCanShop; GM_KeyBinding.UI_RequestKeyBindingData; GM_Lobby.?RequestTeamNames [0x20fd]; GM_MapManager.FlashUIToWorldClick; GM_Options.SetBoolOption; GM_Options.?GetBoolOption; GM_Skill.OnArtifactButtonRollover; GM_Skill.?InqSkillToolTipInfo; GM_Skill.?RequestStolenPowersForCharacter; GM_UI.SkillButtonPressed; GM_Upgrade.ChangeArtifactSkillSlotMapping; GM_Upgrade.PurchaseUpgrade [0x208b]; GM_Upgrade.RequestArtifactSkillSlotMapping; GM_Upgrade.RequestCurrentUpgrades; GM_Upgrade.RequestSendEveryonesUpgrades; GM_Upgrade.RequestUpgradeArrayPreview; GM_Upgrade.SellUpgrade [0x20a7]; GM_Upgrade.?InqCanBuyUpgrade; GM_Upgrade.?InqCanSellUpgrade; GM_Upgrade.?InqSellDifferenceByDID; GM_Upgrade.?InqUpgradeFilters; GM_ViewMatch.?RequestInViewMatchMode; GM_ViewMatch.?RequestTeamGhostedAs |
| `0x20000086` | `0273052c` | spectator (view match) HUD | 14 | Advancement.XPGained; Encounter.AddParticipant [local: raised when player/agent objects are created (probable)]; Encounter.RemoveParticipant [local: object destroyed (probable)]; Encounter.UI_UpdateMatchScorecard; UI.DefeatStatusUpdatedForEntity [n:0x100000bc]; UI.gmWErrorMessageOccurred; Upgrade.DisplayFloatyCurrencyChanged; Upgrade.DisplayFloatyCurrencyDenied; Upgrade.UpdateCurrentUpgrades [0x20e2]; Upgrade.UpdatePowerGraphValues [0x20e2]; ViewMatch.ViewMatchCameraChange; ViewMatch.ViewMatchFOWControls; ViewMatch.ViewMatchPlayerSkillUse; ViewMatch.ViewMatchScoreboardData; Vitals.DisplayFloatyStatus [0x0044 0x208d 0x20bd]; Vitals.VOTUpdate; Vitals.VitalsChanged [0x0042] | GM_Encounter.RequestMatchScorecard; GM_Lobby.?RequestTeamNames [0x20fd]; GM_Skill.?InqSkillToolTipInfo; GM_Skill.?RequestStolenPowersForCharacter; GM_UI.CharacterFloatyVitalsAdded; GM_Upgrade.RequestSendEveryonesUpgrades; GM_ViewMatch.CameraGoToAgentClick; GM_ViewMatch.DirectedCameraButtonPressed; GM_ViewMatch.LockedCameraButtonPressed; GM_ViewMatch.RequestCameraInformation; GM_ViewMatch.RequestKillCardInfo; GM_ViewMatch.SwitchFOWTeam; GM_ViewMatch.ToggleFogOfWar; GM_ViewMatch.?RequestInViewMatchMode; GM_Vitals.?InqSecondaryVitalType; GM_Vitals.?InqTemporaryVital; GM_Vitals.?InqVital |
| `0x20000087` | `0273ee84` | artifact foundry (in-match shop) | 13 | Advancement.SkillRanked; Character.ActiveAgentControlledByThePlayerChanged; Character.AgentControlledByThePlayerChanged; Character.StopProcessingNewBillboards [n:0x100002bc]; Character.UpdateCharacterPanelInfo; Encounter.NotifyMatchEnded [n:0x1000000e]; Encounter.UI_UpdateHasVendorAccess; MapManager.ToggleMiniMap; UI.ActionEnumEvent; UI.BatchNotifyHUDElements [0x213e]; UI.DisplayDialogText [0x2087 0x20ed 0x210a 0x210b]; UI.HideToViewMatchLayout; UI.NotifyHUDElement [0x213d]; UI.ToggleMainMenu; UI.UIStateMachineEvent [0x2038 0x2053]; UI.UpdateHUDVisibility [0x20f5 0x2150]; Upgrade.ActivatedArtifacts; Upgrade.ReturnedUpgradeArrayPreview; Upgrade.SetUIArtifactSkillSlotMapping; Upgrade.UI_RefreshPurchasability; Upgrade.UpdateCurrentUpgrades [0x20e2]; Upgrade.UpdateNextRecommendedUpgrade [0x2078] | GM_Artifact.?InqArtifactDetails; GM_Artifact.?InqArtifactsMatchingCategoryFilterSet; GM_Artifact.?InqAvailableArtifacts; GM_Artifact.?InqKillCardArtifactTooltip; GM_Artifact.?InqRecommendedArtifacts; GM_Artifact.?InqRemainingRecommendedArtifacts; GM_Camera.FullScreenUIActive; GM_Character.?InqCharacterPanelInfo; GM_Character.?InqCharacterPanelMetaData; GM_Chat.ShowChatWindow; GM_Encounter.UI_Mission_RaiseEvent; GM_Encounter.?InqCharacterCanShop; GM_Encounter.?InqEncounterIdentifierType; GM_Options.SetIntOption; GM_Options.?GetIntOption; GM_Options.?GetShowUIFramingFillOption; GM_Options.?GetUICharPanelGroupScalingOption; GM_Options.?GetUIConversationGroupScalingOption; GM_Options.?GetUIKillCardGroupScalingOption; GM_Options.?GetUILetterboxGroupScalingOption; GM_Options.?GetUIMatchGroupScalingOption; GM_Options.?GetUIMinimapGroupScalingOption; GM_Options.?GetUIPlayerInfoGroupScalingOption; GM_Options.?GetUISelectionPanelGroupScalingOption; GM_Options.?GetUISkillsGroupScalingOption; GM_Options.?GetUITopBarGroupScalingOption; GM_Sound.SetParameterAndPlay; GM_UI.HUDInitialized; GM_UI.HUDLoaded; GM_UI.TraceInfoFromFlash; GM_UI.UIStateMachineEvent; GM_Upgrade.ChangeArtifactSkillSlotMapping; GM_Upgrade.PurchaseUpgrade [0x208b]; GM_Upgrade.RequestArtifactSkillSlotMapping; GM_Upgrade.RequestCurrentUpgrades; GM_Upgrade.RequestUpgradeArrayPreview; GM_Upgrade.SellUpgrade [0x20a7]; GM_Upgrade.Tutorial_ArtifactFoundryClosed; GM_Upgrade.Tutorial_ArtifactFoundryOpened; GM_Upgrade.?InqCanBuyUpgrade; GM_Upgrade.?InqCanSellUpgrade; GM_Upgrade.?InqSellDifferenceByDID; GM_Upgrade.?InqUpgradeFilters; GM_ViewMatch.?RequestInViewMatchMode; GM_ViewMatch.?RequestTeamGhostedAs |
| `0x2000008b` | `02757180` | friends / contacts / notifications | 27 | Achievement.AllPendingAchivementBanners [0x211f]; Character.RewardSetsData [0x2125 0x2197]; Character.Ribbon_CharacterLevelChanged [0x2104]; Character.Ribbon_FinishedItemsFulfilled [0x2095]; Character.Ribbon_ItemFulfilled [0x2095]; Character.SendAccountCurrencyBalance [0x2081]; Character.SendAccountLevelAndXP [0x2080]; Chat.UI_ShowWrapperGeneralChatWindow; Contacts.UI_ContactListNotification [0x2065]; Contacts.UI_NotifyContactAccountIconChanged [0x20ec]; Contacts.UI_NotifyContactAdded [0x2051 0x20cc]; Contacts.UI_NotifyContactChangeNote [0x208f]; Contacts.UI_NotifyContactChangeStatusMessage [0x20c5]; Contacts.UI_NotifyContactChangeSteamName; Contacts.UI_NotifyContactChangedGroup [0x20cb]; Contacts.UI_NotifyContactGroupCreated [0x2014]; Contacts.UI_NotifyContactGroupDestroyed [0x205e]; Contacts.UI_NotifyContactIgnored [0x2051]; Contacts.UI_NotifyContactList [0x203b (layout, probable)]; Contacts.UI_NotifyContactOfInvitations [0x219c]; Contacts.UI_NotifyContactOfInvite [0x2003]; Contacts.UI_NotifyContactOfPendingInvites [0x2013]; Contacts.UI_NotifyContactPresenceChanged [0x2018 0x20ae]; Contacts.UI_NotifyContactRemoved [0x2020 0x2051 0x20cc]; Contacts.UI_NotifyContactUnignored [0x204f 0x20cc]; Contacts.UI_NotifySelfChangedPresence [0x203a]; Contacts.UI_NotifySelfChangedStatusMessage [0x2058]; CustomMatch.UI_CustomMatch_Cancelled [0x2011]; CustomMatch.UI_CustomMatch_InviteCancelled [0x2027]; CustomMatch.UI_CustomMatch_Invited [0x201f]; CustomMatch.UI_CustomMatch_Kicked [0x2041]; CustomMatch.UI_CustomMatch_Left [0x203f]; Grouping.GroupInviteCanceled [0x214c]; Grouping.PlayerLeftGroup [0x2071]; Grouping.ShowGroupInviteDialog [0x2033]; Lobby.LobbyRejoinRoom [0x205b]; UI.ActionEnumEvent; UI.BarredFromMatching [0x20f3]; UI.DisplayDialogText [0x2087 0x20ed 0x210a 0x210b]; UI.FoundMatch [0x20fa]; UI.JoinedQueue [0x20c0]; UI.PendingMatchFailure [0x20d7 0x210b]; UI.ProtectorAdvancementStatus [0x215d (account flags; probable)]; UI.RemovedFromQueue [0x20e0 0x210b]; UI.SendHeaderNameAndProtectorIcons [0x2154 0x2190]; UI.ShowURLDialog; UI.ToggleMainMenu; UI.UIStateMachineEvent [0x2038 0x2053]; UI.UserCanCreateGroup [0x2070] | EM_WebBrowser.?InqFoundCEF3SubprocessExecutable; GM_Achievement.RequestAllPendingRewardlessAchievementNotifications [0x212e]; GM_Character.RequestAccountCurrencyBalance; GM_Character.RequestAccountLevelAndXP; GM_Character.RequestPostMatchChanges [0x20ba]; GM_Character.Ribbon_ReceivedItemsFulfilled; GM_Character.UI_RequestPendingRewardUpdateFromServer [0x2124]; GM_Character.?RequestProtectorIcons; GM_Chat.HideChatForBrowser; GM_Chat.HideChatWindow; GM_Chat.RestoreChatForBrowser; GM_Chat.RunCmd; GM_Chat.ShowChatWindow; GM_Chat.StartPlayerTell [0x20cd? (guess)]; GM_ConnectionManager.ResetLastConnectionErrorString; GM_ConnectionManager.?CheckLobbyConnection; GM_ConnectionManager.?InqLastConnectionErrorString; GM_Contacts.UI_AddNoteToContact; GM_Contacts.UI_AddStatusMessage; GM_Contacts.UI_ContactList_Ready; GM_Contacts.UI_CreateContactGroup; GM_Contacts.UI_DestroyContactGroup; GM_Contacts.UI_IgnoreUnignoreContact; GM_Contacts.UI_InviteContact; GM_Contacts.UI_InviteResponse; GM_Contacts.UI_InviteSteamFriends; GM_Contacts.UI_MoveContactToGroup; GM_Contacts.UI_RemoveContact; GM_Contacts.UI_UpdatePresence; GM_Contacts.?UI_CanInviteSteamFriends; GM_CustomMatch.InviteResponse_CustomMatch [0x20e6]; GM_CustomMatch.Invite_CustomMatch; GM_CustomMatch.?IsInCustomMatch [0x20fb]; GM_Dialog.SetUIDialogIdleState; GM_Dialog.SetUIDialogInQueueState; GM_UI.DisplayPendingDodgePenaltyNotifications [0x21a8]; GM_UI.InGameMenuClosed; GM_UI.InGameMenuOpened; GM_UI.JoinQueue [0x20eb]; GM_UI.JoinQueueForPromotedMap [0x20eb]; GM_UI.RequestHeaderUIData; GM_UI.RequestProtectorAdvancementStatus; GM_UI.UIStateMachineEvent; GM_UI.?IsBinkFileValid; GM_UI.?IsLoggedIntoGame; GM_UI.?NeedsUpdateNews; GM_ViewMatch.?RequestInViewMatchModeLastMatch |
| `0x2000008c` | `02767b98` | scorecard (end of match) | 16 | Achievement.AchievementDetails; Achievement.AllPendingAchivementBanners [0x211f]; Achievement.SetAchievementData [local: built from achievement records after 0x2120 (guess)]; Achievement.SetAchievementObjectiveData [0x2120 0x21a6]; Achievement.SetDeprecatedAchievements [0x2120 0x21a6]; Achievement.TraineeAchievements; Character.ActiveAgentControlledByThePlayerChanged; Character.AgentControlledByThePlayerChanged; Character.RewardSetsData [0x2125 0x2197]; Character.Ribbon_CharacterLevelChanged [0x2104]; Character.Ribbon_FinishedItemsFulfilled [0x2095]; Character.Ribbon_ItemFulfilled [0x2095]; Character.SendAccountCurrencyBalance [0x2081]; Character.SendAccountEndOfMatchAccoladesEarned [0x2104 0x2188]; Character.SendAccountEndOfMatchCharacterLevelAndXP [0x2104]; Character.SendAccountEndOfMatchLevelAndXP [0x2080]; Character.SendAccountEndOfMatchSoftCurrencyReward [0x20b9]; Character.SendAccountLevelAndXP [0x2080]; Character.UpdateCharacterPanelInfo; Chat.UI_ShowWrapperGeneralChatWindow; Chat.UpdatedMemberList [0x2135]; Contacts.UI_NotifyContactAdded [0x2051 0x20cc]; Contacts.UI_NotifyContactIgnored [0x2051]; Contacts.UI_NotifyContactUnignored [0x204f 0x20cc]; CustomMatch.UI_CustomMatch_Cancelled [0x2011]; CustomMatch.UI_CustomMatch_Kicked [0x2041]; CustomMatch.UI_CustomMatch_Left [0x203f]; Encounter.PlayEndOfMatchEncounterMovie [0x2045]; Encounter.ResetMapSelectionList [0x2024 0x20ff]; Encounter.UI_SendEndOfMatchStats [0x2045 (progression-meta)]; Encounter.UI_SetEndOfMatchStatsHeader [0x2028 0x2045]; Grouping.PlayerLeftGroup [0x2071]; Lobby.LobbyRejoinRoom [0x205b]; UI.ActionEnumEvent; UI.AvailableCharacterList [0x20b8]; UI.BarredFromMatching [0x20f3]; UI.CharacterAdvancementData [0x209d (layout match)]; UI.DisplayDialogText [0x2087 0x20ed 0x210a 0x210b]; UI.FoundMatch [0x20fa]; UI.Incremental_ItemStatuses [0x204c 0x20b8]; UI.ItemStatuses [0x20b8]; UI.JoinedQueue [0x20c0]; UI.PendingMatchFailure [0x20d7 0x210b]; UI.ProtectorAdvancementStatus [0x215d (account flags; probable)]; UI.QueueEligibility [0x2101]; UI.RemovedFromQueue [0x20e0 0x210b]; UI.Scorecard_HeavyOnlyLoaded; UI.SendHeaderNameAndProtectorIcons [0x2154 0x2190]; UI.ShowURLDialog; UI.ToggleMainMenu; UI.UIStateMachineEvent [0x2038 0x2053]; UI.UI_DeliverAccountStandingsData [0x219e 0x219f]; UI.UI_DeliverStaticStandingsData [0x219e/0x219f (one of)]; UI.UserCanCreateGroup [0x2070]; Upgrade.UpdateCurrentUpgrades [0x20e2]; Upgrade.UpdatePowerGraphValues [0x20e2] | EM_WebBrowser.?InqFoundCEF3SubprocessExecutable; GM_Achievement.RequestAchievementDetails; GM_Achievement.RequestAllAchievementData [0x211d]; GM_Achievement.RequestAllPendingRewardlessAchievementNotifications [0x212e]; GM_Achievement.RequestTraineeAchievements; GM_Character.RequestAccountCurrencyBalance; GM_Character.RequestAccountCurrencyBalanceChanges; GM_Character.RequestAccountEndOfMatchAccoladesEarned; GM_Character.RequestAccountEndOfMatchAccountLevelAndXP; GM_Character.RequestAccountEndOfMatchCharacterLevelAndXP; GM_Character.RequestAccountEndOfMatchSoftCurrencyReward; GM_Character.RequestAccountLevelAndXP; GM_Character.RequestPostMatchChanges [0x20ba]; GM_Character.Ribbon_ReceivedItemsFulfilled; GM_Character.UI_RequestPendingRewardUpdateFromServer [0x2124]; GM_Character.?InqCharacterPanelInfo; GM_Character.?InqCharacterPanelMetaData; GM_Chat.HideChatForBrowser; GM_Chat.HideChatWindow; GM_Chat.RestoreChatForBrowser; GM_Chat.RunCmd; GM_Chat.ShowChatWindow; GM_ConnectionManager.ResetLastConnectionErrorString; GM_ConnectionManager.?CheckLobbyConnection; GM_ConnectionManager.?InqLastConnectionErrorString; GM_Contacts.UI_InviteContact; GM_Contacts.?UI_CanInviteSteamFriends; GM_CustomMatch.?IsInCustomMatch [0x20fb]; GM_Dialog.SetUIDialogIdleState; GM_Dialog.SetUIDialogInQueueState; GM_Encounter.DisplayEncounterWebInfo; GM_Encounter.OnScorecard; GM_Encounter.PlayedEncounterOverviewMovie; GM_Encounter.RequestPostMatchScorecard; GM_Encounter.?InqPVPEncounters; GM_Grouping.?IsInGroup; GM_Lobby.?RequestTeamNames [0x20fd]; GM_PlayerReport.?InqReportAPlayerOptions; GM_UI.DisplayPendingDodgePenaltyNotifications [0x21a8]; GM_UI.InGameMenuClosed; GM_UI.InGameMenuOpened; GM_UI.JoinQueue [0x20eb]; GM_UI.JoinQueueForPromotedMap [0x20eb]; GM_UI.RequestAccountStandingsData [0x2178 (probable)]; GM_UI.RequestCharacterAdvancementData; GM_UI.RequestHeaderUIData; GM_UI.RequestItemStatuses; GM_UI.RequestProtectorAdvancementStatus; GM_UI.RequestStaticStandingsData [0x2193 (probable)]; GM_UI.Scorecard_LoadCharacterHeavyOnly; GM_UI.UIStateMachineEvent; GM_UI.?InqQueueEligibility; GM_UI.?IsBinkFileValid; GM_UI.?IsLoggedIntoGame; GM_UI.?NeedsUpdateNews; GM_Upgrade.?InqBasePowerGraphValues; GM_ViewMatch.?RequestInViewMatchMode; GM_ViewMatch.?RequestInViewMatchModeLastMatch; GM_ViewMatch.?RequestTeamGhostedAs |
| `0x2000008d` | `027a0ea0` | graphical numbers | 1 | - | - |
| `0x20000090` | `027c0d98` | wrapper footer | 9 | Contacts.UI_ContactListNotification [0x2065]; Contacts.UI_NotifyContactOfInvitations [0x219c]; Contacts.UI_NotifyContactOfInvite [0x2003]; Contacts.UI_NotifyContactOfPendingInvites [0x2013]; CustomMatch.UI_CustomMatch_InviteCancelled [0x2027]; CustomMatch.UI_CustomMatch_Invited [0x201f]; Grouping.GroupInviteCanceled [0x214c]; Grouping.ShowGroupInviteDialog [0x2033]; UI.ReleaseNotesUrl | GM_Contacts.UI_ContactList_Ready; GM_UI.OpenURL; GM_UI.RequestReleaseNotesURL |
| `0x20000093` | `027e9120` | custom match | 18 | Achievement.AllPendingAchivementBanners [0x211f]; Character.RewardSetsData [0x2125 0x2197]; Character.Ribbon_CharacterLevelChanged [0x2104]; Character.Ribbon_FinishedItemsFulfilled [0x2095]; Character.Ribbon_ItemFulfilled [0x2095]; Character.SendAccountCurrencyBalance [0x2081]; Character.SendAccountLevelAndXP [0x2080]; Chat.UI_ShowWrapperGeneralChatWindow; Contacts.UI_ContactListNotification [0x2065]; Contacts.UI_NotifyContactAdded [0x2051 0x20cc]; Contacts.UI_NotifyContactOfInvitations [0x219c]; Contacts.UI_NotifyContactOfInvite [0x2003]; Contacts.UI_NotifyContactOfPendingInvites [0x2013]; CustomMatch.UI_CustomMatch_Cancelled [0x2011]; CustomMatch.UI_CustomMatch_InviteCancelled [0x2027]; CustomMatch.UI_CustomMatch_Invited [0x201f]; CustomMatch.UI_CustomMatch_Kicked [0x2041]; CustomMatch.UI_CustomMatch_Launched [0x2040]; CustomMatch.UI_CustomMatch_Left [0x203f]; CustomMatch.UI_CustomMatch_SetDraftMode [0x2103]; CustomMatch.UI_CustomMatch_SetEncounter [0x2109]; CustomMatch.UI_CustomMatch_SetTeamName [0x2151]; CustomMatch.UI_CustomMatch_UpdateProtectorIcon [0x217c]; CustomMatch.UI_DeliverCustomMatchData [client cache of the room (0x2012 0x2035 0x2036 0x2048 0x205d 0x2076 have no Flash listener of their own; probable)]; Encounter.ResetMapSelectionList [0x2024 0x20ff]; Grouping.GroupInviteCanceled [0x214c]; Grouping.PlayerLeftGroup [0x2071]; Grouping.ShowGroupInviteDialog [0x2033]; Lobby.ClearLightResourcePackReferences [0x2021 0x2028 0x204b 0x206c]; Lobby.Draft_Banning; Lobby.Draft_TradeRequest [0x2054]; Lobby.LobbyEncounterDetails [0x204c]; Lobby.LobbyRejoinRoom [0x205b]; Lobby.MatchLaunchWarning [0x204b]; Lobby.PlayerPickedAmplifierSet [0x2029 0x204a 0x2060]; Lobby.PlayerPickedStolenPowers [0x2004 0x2029 0x2060]; Lobby.UpdateEarlyLaunchTime [0x2061]; Lobby.UpdateLobbyLoadingPercent [0x2031]; Lobby.UpdateLobbyLoadingPercentForViewmatch [0x206d]; Lobby.UpdateLobbyState [0x2060 (layout match)]; Lobby.UpdateLobbyStateSingle [0x2029 0x204c 0x2060]; UI.ActionEnumEvent; UI.BarredFromMatching [0x20f3]; UI.BatchNotifyHUDElements [0x213e]; UI.DisplayDialogText [0x2087 0x20ed 0x210a 0x210b]; UI.FoundMatch [0x20fa]; UI.GameFrontUIDestroyedInCPP [0x2021]; UI.JoinedQueue [0x20c0]; UI.NotifyHUDElement [0x213d]; UI.PendingMatchFailure [0x20d7 0x210b]; UI.ProtectorAdvancementStatus [0x215d (account flags; probable)]; UI.QueueEligibility [0x2101]; UI.RemovedFromQueue [0x20e0 0x210b]; UI.ShowURLDialog; UI.ToggleMainMenu; UI.UIStateMachineEvent [0x2038 0x2053]; UI.UserCanCreateGroup [0x2070] | EM_WebBrowser.?InqFoundCEF3SubprocessExecutable; GM_Achievement.RequestAllPendingRewardlessAchievementNotifications [0x212e]; GM_Character.RequestAccountCurrencyBalance; GM_Character.RequestAccountLevelAndXP; GM_Character.RequestPostMatchChanges [0x20ba]; GM_Character.Ribbon_ReceivedItemsFulfilled; GM_Character.UI_RequestPendingRewardUpdateFromServer [0x2124]; GM_Chat.HideChatForBrowser; GM_Chat.HideChatWindow; GM_Chat.RestoreChatForBrowser; GM_Chat.ShowChatWindow; GM_ConnectionManager.ResetLastConnectionErrorString; GM_ConnectionManager.?CheckLobbyConnection; GM_ConnectionManager.?InqLastConnectionErrorString; GM_Contacts.UI_ContactList_Ready; GM_Contacts.UI_InviteContact; GM_Contacts.?UI_CanInviteSteamFriends; GM_CustomMatch.AssignTeam_CustomMatch; GM_CustomMatch.ChangeCoordinator_CustomMatch; GM_CustomMatch.ForceLaunch [0x2094]; GM_CustomMatch.GivePerm_CustomMatch; GM_CustomMatch.Invite_CustomMatch; GM_CustomMatch.Kick_CustomMatch [0x2199 0x219a]; GM_CustomMatch.Launch_CustomMatch [0x20a1]; GM_CustomMatch.MovePosition_CustomMatch [0x219b]; GM_CustomMatch.Randomize [0x20f4]; GM_CustomMatch.RequestCustomMatchData [0x2066]; GM_CustomMatch.SetDraftMode [0x200b]; GM_CustomMatch.SetEncounter; GM_CustomMatch.SetTeamNames; GM_CustomMatch.?IsInCustomMatch [0x20fb]; GM_Dialog.PlayUIDialogElement; GM_Dialog.SetUIDialogIdleState; GM_Dialog.SetUIDialogInQueueState; GM_Encounter.DisplayEncounterWebInfo; GM_Encounter.PlayedEncounterOverviewMovie; GM_Encounter.UI_Mission_RaiseEvent; GM_Encounter.?InqPVPEncounters; GM_Lobby.Draft_TradeResponse; GM_Lobby.LobbyUIReady [0x202d]; GM_Lobby.PlayerSelectedEarlyLaunch [0x206a]; GM_Lobby.?RequestTeamNames [0x20fd]; GM_Options.?GetUIConversationGroupScalingOption; GM_UI.DisplayPendingDodgePenaltyNotifications [0x21a8]; GM_UI.InGameMenuClosed; GM_UI.InGameMenuOpened; GM_UI.JoinQueue [0x20eb]; GM_UI.JoinQueueForPromotedMap [0x20eb]; GM_UI.RequestProtectorAdvancementStatus; GM_UI.UIStateMachineEvent; GM_UI.?InqQueueEligibility; GM_UI.?IsBinkFileValid; GM_UI.?IsLoggedIntoGame; GM_UI.?NeedsUpdateNews; GM_ViewMatch.?RequestAbleToViewMatch; GM_ViewMatch.?RequestInViewMatchMode; GM_ViewMatch.?RequestInViewMatchModeLastMatch |
| `0x20000094` | `02804204` | amplifiers screen | 16 | Achievement.AllPendingAchivementBanners [0x211f]; Amplifier.NotifyAmplifierSet [0x20c7]; Amplifier.NotifyContextualAmplifierData [0x2107]; Amplifier.NotifyListAmplifierSets [0x2090]; Character.RewardSetsData [0x2125 0x2197]; Character.Ribbon_CharacterLevelChanged [0x2104]; Character.Ribbon_FinishedItemsFulfilled [0x2095]; Character.Ribbon_ItemFulfilled [0x2095]; Character.SendAccountCurrencyBalance [0x2081]; Character.SendAccountLevelAndXP [0x2080]; Chat.UI_ShowWrapperGeneralChatWindow; Contextual.PurchaseContextualItemError [0x210d]; Contextual.PurchaseContextualItemSuccess [0x210c]; CustomMatch.UI_CustomMatch_Cancelled [0x2011]; CustomMatch.UI_CustomMatch_Kicked [0x2041]; CustomMatch.UI_CustomMatch_Left [0x203f]; Grouping.PlayerLeftGroup [0x2071]; Lobby.LobbyRejoinRoom [0x205b]; UI.ActionEnumEvent; UI.AvailableCharacterList [0x20b8]; UI.BarredFromMatching [0x20f3]; UI.CharacterAdvancementData [0x209d (layout match)]; UI.DisplayDialogText [0x2087 0x20ed 0x210a 0x210b]; UI.FoundMatch [0x20fa]; UI.Incremental_ItemStatuses [0x204c 0x20b8]; UI.ItemStatuses [0x20b8]; UI.JoinedQueue [0x20c0]; UI.PendingMatchFailure [0x20d7 0x210b]; UI.ProtectorAdvancementStatus [0x215d (account flags; probable)]; UI.RemovedFromQueue [0x20e0 0x210b]; UI.ShowURLDialog; UI.ToggleMainMenu; UI.UIStateMachineEvent [0x2038 0x2053]; UI.UserCanCreateGroup [0x2070]; WebTicket.UI_OnWebTicketUpdated | EM_WebBrowser.?InqFoundCEF3SubprocessExecutable; EM_WebTicket.UI_RequestWebTicket; GM_Achievement.RequestAllPendingRewardlessAchievementNotifications [0x212e]; GM_Amplifier.UI_RequestAllAmplifierBoutiqueData; GM_Amplifier.UI_RequestAllAmplifierSets; GM_Amplifier.UI_SaveAmplifierSet [0x20fc (probable: same fields)]; GM_Amplifier.?UI_InqAmplifierSetIcons; GM_Amplifier.?UI_InqAmplifierSetSlotInfo; GM_Amplifier.?UI_InqAugmentData; GM_Amplifier.?UI_InqAugmentModStoreUrls; GM_Amplifier.?UI_InqAugmentsPassingFilter; GM_Amplifier.?UI_InqModData; GM_Amplifier.?UI_InqModsPassingFilter; GM_Character.RequestAccountCurrencyBalance; GM_Character.RequestAccountLevelAndXP; GM_Character.RequestPostMatchChanges [0x20ba]; GM_Character.Ribbon_ReceivedItemsFulfilled; GM_Character.UI_RequestPendingRewardUpdateFromServer [0x2124]; GM_Chat.HideChatForBrowser; GM_Chat.HideChatWindow; GM_Chat.RestoreChatForBrowser; GM_Chat.ShowChatWindow; GM_ConnectionManager.ResetLastConnectionErrorString; GM_ConnectionManager.?CheckLobbyConnection; GM_ConnectionManager.?InqLastConnectionErrorString; GM_Contacts.?UI_CanInviteSteamFriends; GM_CustomMatch.?IsInCustomMatch [0x20fb]; GM_Dialog.SetUIDialogIdleState; GM_Dialog.SetUIDialogInQueueState; GM_UI.DisplayPendingDodgePenaltyNotifications [0x21a8]; GM_UI.InGameMenuClosed; GM_UI.InGameMenuOpened; GM_UI.JoinQueue [0x20eb]; GM_UI.JoinQueueForPromotedMap [0x20eb]; GM_UI.RequestCharacterAdvancementData; GM_UI.RequestItemStatuses; GM_UI.RequestProtectorAdvancementStatus; GM_UI.UIStateMachineEvent; GM_UI.?IsBinkFileValid; GM_UI.?IsLoggedIntoGame; GM_UI.?NeedsUpdateNews; GM_ViewMatch.?RequestInViewMatchMode; GM_ViewMatch.?RequestInViewMatchModeLastMatch |
| `0x20000099` | `02824308` | tutorial highlight tips | 3 | - | - |
| `0x2000009a` | `0282f8e4` | conversation banner | 6 | Dialog.HideAllConversationSlots [0x2001 (C++ conversation player)]; Dialog.HideConversationSlot [0x2001 (C++ conversation player)]; Dialog.HighlightConversationAdvanceButton; Dialog.ShowConversationSlot [0x2001 (conversation; C++ drives the slots)] | GM_Dialog.UI_AdvanceConversation; GM_Dialog.UI_ReadyForConversation; GM_Dialog.UI_SkipConversation |
| `0x2000009c` | `02929710` | surrender vote | 2 | Encounter.AddParticipant [local: raised when player/agent objects are created (probable)]; Encounter.RemoveParticipant [local: object destroyed (probable)]; Encounter.SurrenderVoteConcluded [n:0x10000456]; Encounter.UI_UpdateMatchScorecard; Encounter.UpdateSurrenderData [n:0x10000455]; UI.DefeatStatusUpdatedForEntity [n:0x100000bc]; UI.gmWErrorMessageOccurred; Upgrade.UpdateCurrentUpgrades [0x20e2]; Upgrade.UpdatePowerGraphValues [0x20e2]; ViewMatch.ViewMatchScoreboardData | GM_Encounter.RequestMatchScorecard; GM_Encounter.SurrenderResponse [notice 0x10000454]; GM_Lobby.?RequestTeamNames [0x20fd]; GM_Skill.?InqSkillToolTipInfo; GM_Skill.?RequestStolenPowersForCharacter; GM_Upgrade.RequestSendEveryonesUpgrades; GM_ViewMatch.?RequestInViewMatchMode |
| `0x2000009d` | `02930734` | scorecard stats tab | 6 | Character.SendAccountCurrencyBalance [0x2081]; Character.SendAccountEndOfMatchAccoladesEarned [0x2104 0x2188]; Character.SendAccountEndOfMatchCharacterLevelAndXP [0x2104]; Character.SendAccountEndOfMatchLevelAndXP [0x2080]; Character.SendAccountEndOfMatchSoftCurrencyReward [0x20b9]; Encounter.UI_SendEndOfMatchStats [0x2045 (progression-meta)]; Encounter.UI_SetEndOfMatchStatsHeader [0x2028 0x2045]; UI.SendHeaderNameAndProtectorIcons [0x2154 0x2190]; Upgrade.UpdateCurrentUpgrades [0x20e2]; Upgrade.UpdatePowerGraphValues [0x20e2] | GM_Character.RequestAccountCurrencyBalance; GM_Character.RequestAccountCurrencyBalanceChanges; GM_Character.RequestAccountEndOfMatchAccoladesEarned; GM_Character.RequestAccountEndOfMatchAccountLevelAndXP; GM_Character.RequestAccountEndOfMatchCharacterLevelAndXP; GM_Character.RequestAccountEndOfMatchSoftCurrencyReward; GM_Encounter.RequestPostMatchScorecard; GM_UI.RequestHeaderUIData |
| `0x2000009e` | `0293826c` | wrapper background | 4 | KeyBinding.UI_KeyBindingData; KeyBinding.UI_UpdateKeyBinding | GM_KeyBinding.UI_RequestKeyBindingData; GM_Options.SetBoolOption; GM_Options.?GetBoolOption; GM_UI.?InqWrapperDisplayData |
| `0x2000009f` | `029408f8` | FPS display | 1 | KeyBinding.UI_KeyBindingData; KeyBinding.UI_UpdateKeyBinding; UI.FPSUpdate | GM_KeyBinding.UI_RequestKeyBindingData; GM_Options.SetBoolOption; GM_Options.?GetBoolOption; GM_ViewMatch.?RequestInViewMatchMode |
| `0x200000a0` | `0299eb68` | calling card | 3 | - | - |
| `0x200000a1` | `029a63e0` | spectator top bar | 5 | Character.ActiveAgentControlledByThePlayerChanged; Character.AgentControlledByThePlayerChanged; Character.StopProcessingNewBillboards [n:0x100002bc]; Character.UpdateCharacterPanelInfo; Encounter.AddParticipant [local: raised when player/agent objects are created (probable)]; Encounter.NotifyMatchEnded [n:0x1000000e]; Encounter.RemoveParticipant [local: object destroyed (probable)]; Encounter.SetMatchTime [n:0x10000109]; Encounter.UI_BatchUpdateTrackerStatus; Encounter.UI_InitialTeamHealthUpdate [n:0x100004fb]; Encounter.UI_MissionEvent_AddTimelineBanner; Encounter.UI_MissionEvent_AddTimelineEvent; Encounter.UI_MissionEvent_BatchAddTimelineEvent; Encounter.UI_MissionEvent_RemoveTimelineBanner; Encounter.UI_MissionEvent_RemoveTimelineEvent; Encounter.UI_MissionEvent_StartTimeline; Encounter.UI_UpdateMatchScorecard; Encounter.UI_UpdateTeamHealth [n:0x10000134]; Encounter.UI_UpdateTrackerStatus [0x2069]; MapManager.ToggleMiniMap; UI.ActionEnumEvent; UI.BatchNotifyHUDElements [0x213e]; UI.DefeatStatusUpdatedForEntity [n:0x100000bc]; UI.DisplayDialogText [0x2087 0x20ed 0x210a 0x210b]; UI.HideToViewMatchLayout; UI.NotifyHUDElement [0x213d]; UI.ToggleMainMenu; UI.UIStateMachineEvent [0x2038 0x2053]; UI.UpdateHUDVisibility [0x20f5 0x2150]; UI.gmWErrorMessageOccurred; Upgrade.UpdateCurrentUpgrades [0x20e2]; Upgrade.UpdatePowerGraphValues [0x20e2]; ViewMatch.ViewMatchScoreboardData; ViewMatch.ViewMatch_UpdateDampenerCounts [0x215c]; ViewMatch.ViewMatch_UpdateTurretCounts | GM_Character.?InqCharacterPanelInfo; GM_Character.?InqCharacterPanelMetaData; GM_Chat.ShowChatWindow; GM_Encounter.RequestCurrentTeamHealth [notice 0x10000137]; GM_Encounter.RequestMatchScorecard; GM_Encounter.UI_ReadyForTimelineData [notice 0x100002ad]; GM_Encounter.?InqEncounterIdentifierType; GM_Encounter.?InqMatchTimes; GM_Encounter.?UI_InqSectorObjectives; GM_Lobby.?RequestTeamNames [0x20fd]; GM_Options.SetIntOption; GM_Options.?GetIntOption; GM_Options.?GetShowUIFramingFillOption; GM_Options.?GetUICharPanelGroupScalingOption; GM_Options.?GetUIConversationGroupScalingOption; GM_Options.?GetUIKillCardGroupScalingOption; GM_Options.?GetUILetterboxGroupScalingOption; GM_Options.?GetUIMatchGroupScalingOption; GM_Options.?GetUIMinimapGroupScalingOption; GM_Options.?GetUIPlayerInfoGroupScalingOption; GM_Options.?GetUISelectionPanelGroupScalingOption; GM_Options.?GetUISkillsGroupScalingOption; GM_Options.?GetUITopBarGroupScalingOption; GM_Skill.?InqSkillToolTipInfo; GM_Skill.?RequestStolenPowersForCharacter; GM_UI.HUDInitialized; GM_UI.HUDLoaded; GM_UI.TraceInfoFromFlash; GM_UI.UIStateMachineEvent; GM_Upgrade.RequestSendEveryonesUpgrades; GM_ViewMatch.RequestMatchStartCounts; GM_ViewMatch.?RequestInViewMatchMode; GM_ViewMatch.?RequestTeamGhostedAs |
| `0x200000a2` | `029b276c` | achievements | 11 | Achievement.AchievementDetails; Achievement.AllPendingAchivementBanners [0x211f]; Achievement.SetAchievementData [local: built from achievement records after 0x2120 (guess)]; Achievement.SetAchievementObjectiveData [0x2120 0x21a6]; Achievement.SetDeprecatedAchievements [0x2120 0x21a6]; Achievement.TraineeAchievements; Character.RewardSetsData [0x2125 0x2197]; Character.Ribbon_CharacterLevelChanged [0x2104]; Character.Ribbon_FinishedItemsFulfilled [0x2095]; Character.Ribbon_ItemFulfilled [0x2095]; Character.SendAccountCurrencyBalance [0x2081]; Character.SendAccountLevelAndXP [0x2080]; Chat.UI_ShowWrapperGeneralChatWindow; CustomMatch.UI_CustomMatch_Cancelled [0x2011]; CustomMatch.UI_CustomMatch_Kicked [0x2041]; CustomMatch.UI_CustomMatch_Left [0x203f]; Grouping.PlayerLeftGroup [0x2071]; Lobby.LobbyRejoinRoom [0x205b]; UI.ActionEnumEvent; UI.BarredFromMatching [0x20f3]; UI.DisplayDialogText [0x2087 0x20ed 0x210a 0x210b]; UI.FoundMatch [0x20fa]; UI.JoinedQueue [0x20c0]; UI.PendingMatchFailure [0x20d7 0x210b]; UI.ProtectorAdvancementStatus [0x215d (account flags; probable)]; UI.RemovedFromQueue [0x20e0 0x210b]; UI.ShowURLDialog; UI.ToggleMainMenu; UI.UIStateMachineEvent [0x2038 0x2053]; UI.UserCanCreateGroup [0x2070] | EM_WebBrowser.?InqFoundCEF3SubprocessExecutable; GM_Achievement.RequestAchievementDetails; GM_Achievement.RequestAllAchievementData [0x211d]; GM_Achievement.RequestAllPendingRewardlessAchievementNotifications [0x212e]; GM_Achievement.RequestTraineeAchievements; GM_Character.RequestAccountCurrencyBalance; GM_Character.RequestAccountLevelAndXP; GM_Character.RequestPostMatchChanges [0x20ba]; GM_Character.Ribbon_ReceivedItemsFulfilled; GM_Character.UI_RequestPendingRewardUpdateFromServer [0x2124]; GM_Chat.HideChatForBrowser; GM_Chat.HideChatWindow; GM_Chat.RestoreChatForBrowser; GM_Chat.ShowChatWindow; GM_ConnectionManager.ResetLastConnectionErrorString; GM_ConnectionManager.?CheckLobbyConnection; GM_ConnectionManager.?InqLastConnectionErrorString; GM_Contacts.?UI_CanInviteSteamFriends; GM_CustomMatch.?IsInCustomMatch [0x20fb]; GM_Dialog.SetUIDialogIdleState; GM_Dialog.SetUIDialogInQueueState; GM_UI.DisplayPendingDodgePenaltyNotifications [0x21a8]; GM_UI.JoinQueue [0x20eb]; GM_UI.JoinQueueForPromotedMap [0x20eb]; GM_UI.RequestProtectorAdvancementStatus; GM_UI.UIStateMachineEvent; GM_UI.?IsLoggedIntoGame; GM_UI.?NeedsUpdateNews; GM_ViewMatch.?RequestInViewMatchModeLastMatch |
| `0x200000a3` | `029c2308` | stats screen | 8 | Achievement.AllPendingAchivementBanners [0x211f]; Character.RewardSetsData [0x2125 0x2197]; Character.Ribbon_CharacterLevelChanged [0x2104]; Character.Ribbon_FinishedItemsFulfilled [0x2095]; Character.Ribbon_ItemFulfilled [0x2095]; Character.SendAccountCurrencyBalance [0x2081]; Character.SendAccountEncounterStats [0x2115]; Character.SendAccountEndOfMatchAccoladesEarned [0x2104 0x2188]; Character.SendAccountLevelAndXP [0x2080]; Character.SendBestChampAccolades [0x2186]; Character.SendBestMapAccolades [0x2186]; Chat.UI_ShowWrapperGeneralChatWindow; CustomMatch.UI_CustomMatch_Cancelled [0x2011]; CustomMatch.UI_CustomMatch_Kicked [0x2041]; CustomMatch.UI_CustomMatch_Left [0x203f]; Encounter.ResetMapSelectionList [0x2024 0x20ff]; Grouping.PlayerLeftGroup [0x2071]; Lobby.LobbyRejoinRoom [0x205b]; UI.ActionEnumEvent; UI.BarredFromMatching [0x20f3]; UI.DisplayDialogText [0x2087 0x20ed 0x210a 0x210b]; UI.FoundMatch [0x20fa]; UI.JoinedQueue [0x20c0]; UI.PendingMatchFailure [0x20d7 0x210b]; UI.ProtectorAdvancementStatus [0x215d (account flags; probable)]; UI.QueueEligibility [0x2101]; UI.RemovedFromQueue [0x20e0 0x210b]; UI.SendHeaderNameAndProtectorIcons [0x2154 0x2190]; UI.ShowURLDialog; UI.ToggleMainMenu; UI.UIStateMachineEvent [0x2038 0x2053]; UI.UserCanCreateGroup [0x2070] | EM_WebBrowser.?InqFoundCEF3SubprocessExecutable; GM_Achievement.RequestAllPendingRewardlessAchievementNotifications [0x212e]; GM_Character.RequestAccountCurrencyBalance; GM_Character.RequestAccountEncounterStats [0x2116]; GM_Character.RequestAccountEndOfMatchAccoladesEarned; GM_Character.RequestAccountLevelAndXP; GM_Character.RequestPostMatchChanges [0x20ba]; GM_Character.Ribbon_ReceivedItemsFulfilled; GM_Character.UI_RequestBestAccolades; GM_Character.UI_RequestPendingRewardUpdateFromServer [0x2124]; GM_Chat.HideChatForBrowser; GM_Chat.HideChatWindow; GM_Chat.RestoreChatForBrowser; GM_Chat.ShowChatWindow; GM_ConnectionManager.ResetLastConnectionErrorString; GM_ConnectionManager.?CheckLobbyConnection; GM_ConnectionManager.?InqLastConnectionErrorString; GM_Contacts.?UI_CanInviteSteamFriends; GM_CustomMatch.?IsInCustomMatch [0x20fb]; GM_Dialog.SetUIDialogIdleState; GM_Dialog.SetUIDialogInQueueState; GM_Encounter.?InqPVPEncounters; GM_UI.DisplayPendingDodgePenaltyNotifications [0x21a8]; GM_UI.JoinQueue [0x20eb]; GM_UI.JoinQueueForPromotedMap [0x20eb]; GM_UI.RequestHeaderUIData; GM_UI.RequestProtectorAdvancementStatus; GM_UI.UIStateMachineEvent; GM_UI.?InqQueueEligibility; GM_UI.?IsLoggedIntoGame; GM_UI.?NeedsUpdateNews; GM_ViewMatch.?RequestInViewMatchModeLastMatch |
| `0x200000a4` | `029ca950` | veteran landing (profile overview) | 17 | Achievement.AchievementDetails; Achievement.AllPendingAchivementBanners [0x211f]; Achievement.SetAchievementData [local: built from achievement records after 0x2120 (guess)]; Achievement.SetAchievementObjectiveData [0x2120 0x21a6]; Achievement.SetDeprecatedAchievements [0x2120 0x21a6]; Achievement.TraineeAchievements; Character.RewardSetsData [0x2125 0x2197]; Character.Ribbon_CharacterLevelChanged [0x2104]; Character.Ribbon_FinishedItemsFulfilled [0x2095]; Character.Ribbon_ItemFulfilled [0x2095]; Character.SendAccountCurrencyBalance [0x2081]; Character.SendAccountEndOfMatchAccoladesEarned [0x2104 0x2188]; Character.SendAccountLevelAndXP [0x2080]; Character.SendBestChampAccolades [0x2186]; Character.SendBestMapAccolades [0x2186]; Chat.UI_ShowWrapperGeneralChatWindow; CustomMatch.UI_CustomMatch_Cancelled [0x2011]; CustomMatch.UI_CustomMatch_Kicked [0x2041]; CustomMatch.UI_CustomMatch_Left [0x203f]; CustomMatch.UI_CustomMatch_SetDraftMode [0x2103]; CustomMatch.UI_CustomMatch_SetEncounter [0x2109]; CustomMatch.UI_CustomMatch_SetTeamName [0x2151]; CustomMatch.UI_CustomMatch_UpdateProtectorIcon [0x217c]; CustomMatch.UI_DeliverCustomMatchData [client cache of the room (0x2012 0x2035 0x2036 0x2048 0x205d 0x2076 have no Flash listener of their own; probable)]; Encounter.ResetMapSelectionList [0x2024 0x20ff]; Encounter.UI_LastMapPlayed [0x214b]; Grouping.PlayerLeftGroup [0x2071]; Lobby.LobbyRejoinRoom [0x205b]; ProfileUI.ProfileUI_HeavyResourcePackData; ProfileUI.ProfileUI_SpecialSecondaryPower; UI.ActionEnumEvent; UI.AvailableCharacterList [0x20b8]; UI.BarredFromMatching [0x20f3]; UI.CharacterAdvancementData [0x209d (layout match)]; UI.DisplayDialogText [0x2087 0x20ed 0x210a 0x210b]; UI.FoundMatch [0x20fa]; UI.Incremental_ItemStatuses [0x204c 0x20b8]; UI.ItemStatuses [0x20b8]; UI.JoinedQueue [0x20c0]; UI.PendingMatchFailure [0x20d7 0x210b]; UI.ProtectorAdvancementStatus [0x215d (account flags; probable)]; UI.QueueEligibility [0x2101]; UI.RemovedFromQueue [0x20e0 0x210b]; UI.SendHeaderNameAndProtectorIcons [0x2154 0x2190]; UI.ShowURLDialog; UI.ToggleMainMenu; UI.UIStateMachineEvent [0x2038 0x2053]; UI.UserCanCreateGroup [0x2070] | EM_WebBrowser.?InqFoundCEF3SubprocessExecutable; GM_Achievement.RequestAchievementDetails; GM_Achievement.RequestAllAchievementData [0x211d]; GM_Achievement.RequestAllPendingRewardlessAchievementNotifications [0x212e]; GM_Achievement.RequestTraineeAchievements; GM_Character.RequestAccountCurrencyBalance; GM_Character.RequestAccountEndOfMatchAccoladesEarned; GM_Character.RequestAccountLevelAndXP; GM_Character.RequestPostMatchChanges [0x20ba]; GM_Character.Ribbon_ReceivedItemsFulfilled; GM_Character.UI_RequestBestAccolades; GM_Character.UI_RequestPendingRewardUpdateFromServer [0x2124]; GM_Character.?UI_RequestAspirationalTooltip; GM_Chat.HideChatForBrowser; GM_Chat.HideChatWindow; GM_Chat.RestoreChatForBrowser; GM_Chat.ShowChatWindow; GM_ConnectionManager.ResetLastConnectionErrorString; GM_ConnectionManager.?CheckLobbyConnection; GM_ConnectionManager.?InqLastConnectionErrorString; GM_Contacts.?UI_CanInviteSteamFriends; GM_CustomMatch.RequestCustomMatchData [0x2066]; GM_CustomMatch.?IsInCustomMatch [0x20fb]; GM_Dialog.SetUIDialogIdleState; GM_Dialog.SetUIDialogInQueueState; GM_Encounter.RequestLastMapPlayed; GM_Encounter.?InqPVPEncounters; GM_Grouping.?IsInGroup; GM_Lobby.?RequestStolenPowerList [0x2017]; GM_Lobby.?RequestTeamNames [0x20fd]; GM_ProfileUI.ProfileUI_SelectCharacter; GM_UI.DisplayPendingDodgePenaltyNotifications [0x21a8]; GM_UI.InGameMenuClosed; GM_UI.InGameMenuOpened; GM_UI.JoinQueue [0x20eb]; GM_UI.JoinQueueForPromotedMap [0x20eb]; GM_UI.RequestCharacterAdvancementData; GM_UI.RequestHeaderUIData; GM_UI.RequestItemStatuses; GM_UI.RequestProtectorAdvancementStatus; GM_UI.UIStateMachineEvent; GM_UI.?InqQueueEligibility; GM_UI.?IsBinkFileValid; GM_UI.?IsLoggedIntoGame; GM_UI.?NeedsUpdateNews; GM_ViewMatch.?RequestInViewMatchMode; GM_ViewMatch.?RequestInViewMatchModeLastMatch |
| `0x200000a5` | `029eb824` | characters (collection) screen | 19 | Achievement.AllPendingAchivementBanners [0x211f]; Amplifier.NotifyAmplifierSet [0x20c7]; Amplifier.NotifyListAmplifierSets [0x2090]; Character.RewardSetsData [0x2125 0x2197]; Character.Ribbon_CharacterLevelChanged [0x2104]; Character.Ribbon_FinishedItemsFulfilled [0x2095]; Character.Ribbon_ItemFulfilled [0x2095]; Character.SendAccountCurrencyBalance [0x2081]; Character.SendAccountEndOfMatchAccoladesEarned [0x2104 0x2188]; Character.SendAccountLevelAndXP [0x2080]; Character.SendBestChampAccolades [0x2186]; Character.SendBestMapAccolades [0x2186]; Chat.UI_ShowWrapperGeneralChatWindow; CustomMatch.UI_CustomMatch_Cancelled [0x2011]; CustomMatch.UI_CustomMatch_Kicked [0x2041]; CustomMatch.UI_CustomMatch_Left [0x203f]; Grouping.PlayerLeftGroup [0x2071]; Lobby.LobbyRejoinRoom [0x205b]; ProfileUI.ProfileUI_AmplifierSetData; ProfileUI.ProfileUI_CharacterVariantsLoaded; ProfileUI.ProfileUI_HeavyResourcePackData; ProfileUI.ProfileUI_SpecialSecondaryPower; UI.ActionEnumEvent; UI.AvailableCharacterList [0x20b8]; UI.BarredFromMatching [0x20f3]; UI.CharacterAdvancementData [0x209d (layout match)]; UI.DisplayDialogText [0x2087 0x20ed 0x210a 0x210b]; UI.FoundMatch [0x20fa]; UI.Incremental_ItemStatuses [0x204c 0x20b8]; UI.ItemStatuses [0x20b8]; UI.JoinedQueue [0x20c0]; UI.PendingMatchFailure [0x20d7 0x210b]; UI.ProtectorAdvancementStatus [0x215d (account flags; probable)]; UI.RemovedFromQueue [0x20e0 0x210b]; UI.SendHeaderNameAndProtectorIcons [0x2154 0x2190]; UI.ShowURLDialog; UI.ToggleMainMenu; UI.UIStateMachineEvent [0x2038 0x2053]; UI.UserCanCreateGroup [0x2070] | EM_WebBrowser.?InqFoundCEF3SubprocessExecutable; GM_Achievement.RequestAllPendingRewardlessAchievementNotifications [0x212e]; GM_Amplifier.UI_RequestAllAmplifierSets; GM_Amplifier.?UI_InqAmplifierSetIcons; GM_Amplifier.?UI_InqAugmentData; GM_Amplifier.?UI_InqModData; GM_Character.RequestAccountCurrencyBalance; GM_Character.RequestAccountEndOfMatchAccoladesEarned; GM_Character.RequestAccountLevelAndXP; GM_Character.RequestPostMatchChanges [0x20ba]; GM_Character.Ribbon_ReceivedItemsFulfilled; GM_Character.UI_RequestBestAccolades; GM_Character.UI_RequestPendingRewardUpdateFromServer [0x2124]; GM_Character.?InqCharacterRoles; GM_Character.?UI_RequestAspirationalTooltip; GM_Chat.HideChatForBrowser; GM_Chat.HideChatWindow; GM_Chat.RestoreChatForBrowser; GM_Chat.ShowChatWindow; GM_ConnectionManager.ResetLastConnectionErrorString; GM_ConnectionManager.?CheckLobbyConnection; GM_ConnectionManager.?InqLastConnectionErrorString; GM_Contacts.?UI_CanInviteSteamFriends; GM_CustomMatch.?IsInCustomMatch [0x20fb]; GM_Dialog.SetUIDialogIdleState; GM_Dialog.SetUIDialogInQueueState; GM_Lobby.?RequestStolenPowerList [0x2017]; GM_ProfileUI.ProfileUI_SelectCharacter; GM_Skill.?InqSkillToolTipInfo; GM_UI.DisplayPendingDodgePenaltyNotifications [0x21a8]; GM_UI.JoinQueue [0x20eb]; GM_UI.JoinQueueForPromotedMap [0x20eb]; GM_UI.RequestCharacterAdvancementData; GM_UI.RequestHeaderUIData; GM_UI.RequestItemStatuses; GM_UI.RequestProtectorAdvancementStatus; GM_UI.UIStateMachineEvent; GM_UI.?IsLoggedIntoGame; GM_UI.?NeedsUpdateNews; GM_ViewMatch.?RequestInViewMatchMode; GM_ViewMatch.?RequestInViewMatchModeLastMatch |
| `0x200000a7` | `02a326b0` | launch movie player | 3 | UI.ActionEnumEvent | EM_UI.ForceOnSized; GM_Options.TemporaryFullScreen; GM_UI.ConnectToGameServer; GM_UI.UIStateMachineEvent; GM_UI.?InqWrapperDisplayData; GM_UI.?IsBinkFileValid |
| `0x200000a8` | `02a49fb4` | landing nav / switcher | 4 | Achievement.AllPendingAchivementBanners [0x211f]; Achievement.SetAchievementData [local: built from achievement records after 0x2120 (guess)]; Achievement.SetAchievementObjectiveData [0x2120 0x21a6]; Achievement.SetDeprecatedAchievements [0x2120 0x21a6]; Achievement.TraineeAchievements; Character.RewardSetsData [0x2125 0x2197]; Character.Ribbon_CharacterLevelChanged [0x2104]; Character.Ribbon_FinishedItemsFulfilled [0x2095]; Character.Ribbon_ItemFulfilled [0x2095]; Character.SendAccountCurrencyBalance [0x2081]; Character.SendAccountLevelAndXP [0x2080]; Contextual.PurchaseContextualItemError [0x210d]; Contextual.PurchaseContextualItemSuccess [0x210c]; CustomMatch.UI_CustomMatch_Cancelled [0x2011]; CustomMatch.UI_CustomMatch_Kicked [0x2041]; CustomMatch.UI_CustomMatch_Left [0x203f]; Grouping.PlayerLeftGroup [0x2071]; Lobby.LobbyRejoinRoom [0x205b]; UI.ActionEnumEvent; UI.BarredFromMatching [0x20f3]; UI.DisplayDialogText [0x2087 0x20ed 0x210a 0x210b]; UI.FoundMatch [0x20fa]; UI.JoinedQueue [0x20c0]; UI.PendingMatchFailure [0x20d7 0x210b]; UI.ProtectorAdvancementStatus [0x215d (account flags; probable)]; UI.RemovedFromQueue [0x20e0 0x210b]; UI.ShowURLDialog; UI.ToggleMainMenu; UI.UIStateMachineEvent [0x2038 0x2053]; UI.UserCanCreateGroup [0x2070]; WebTicket.UI_OnWebTicketUpdated | EM_WebBrowser.?InqFoundCEF3SubprocessExecutable; EM_WebTicket.UI_RequestWebTicket; GM_Achievement.RequestAllAchievementData [0x211d]; GM_Achievement.RequestAllPendingRewardlessAchievementNotifications [0x212e]; GM_Achievement.RequestTraineeAchievements; GM_Amplifier.UI_RequestAllAmplifierBoutiqueData; GM_Amplifier.UI_RequestAllAmplifierSets; GM_Amplifier.UI_SaveAmplifierSet [0x20fc (probable: same fields)]; GM_Amplifier.?UI_InqAmplifierSetIcons; GM_Amplifier.?UI_InqAmplifierSetSlotInfo; GM_Amplifier.?UI_InqAugmentModStoreUrls; GM_Amplifier.?UI_InqAugmentsPassingFilter; GM_Amplifier.?UI_InqModsPassingFilter; GM_Character.RequestAccountCurrencyBalance; GM_Character.RequestAccountLevelAndXP; GM_Character.RequestPostMatchChanges [0x20ba]; GM_Character.Ribbon_ReceivedItemsFulfilled; GM_Character.UI_RequestPendingRewardUpdateFromServer [0x2124]; GM_ConnectionManager.ResetLastConnectionErrorString; GM_ConnectionManager.?CheckLobbyConnection; GM_ConnectionManager.?InqLastConnectionErrorString; GM_Contacts.?UI_CanInviteSteamFriends; GM_CustomMatch.?IsInCustomMatch [0x20fb]; GM_Dialog.SetUIDialogIdleState; GM_Dialog.SetUIDialogInQueueState; GM_UI.DisplayPendingDodgePenaltyNotifications [0x21a8]; GM_UI.InGameMenuClosed; GM_UI.InGameMenuOpened; GM_UI.JoinQueue [0x20eb]; GM_UI.JoinQueueForPromotedMap [0x20eb]; GM_UI.RequestProtectorAdvancementStatus; GM_UI.SetProtectorAdvancementStatusForSession; GM_UI.UIStateMachineEvent; GM_UI.?IsBinkFileValid; GM_UI.?IsLoggedIntoGame; GM_UI.?NeedsUpdateNews; GM_ViewMatch.?RequestInViewMatchModeLastMatch |
| `0x200000a9` | `02a66eb8` | encounter details | 6 | Achievement.AllPendingAchivementBanners [0x211f]; Character.RewardSetsData [0x2125 0x2197]; Character.Ribbon_CharacterLevelChanged [0x2104]; Character.Ribbon_FinishedItemsFulfilled [0x2095]; Character.Ribbon_ItemFulfilled [0x2095]; Character.SendAccountCurrencyBalance [0x2081]; Character.SendAccountLevelAndXP [0x2080]; Chat.UI_ShowWrapperGeneralChatWindow; CustomMatch.UI_CustomMatch_Cancelled [0x2011]; CustomMatch.UI_CustomMatch_Kicked [0x2041]; CustomMatch.UI_CustomMatch_Left [0x203f]; Encounter.ResetMapSelectionList [0x2024 0x20ff]; Grouping.PlayerLeftGroup [0x2071]; Lobby.LobbyRejoinRoom [0x205b]; UI.ActionEnumEvent; UI.BarredFromMatching [0x20f3]; UI.DisplayDialogText [0x2087 0x20ed 0x210a 0x210b]; UI.FoundMatch [0x20fa]; UI.JoinedQueue [0x20c0]; UI.PendingMatchFailure [0x20d7 0x210b]; UI.ProtectorAdvancementStatus [0x215d (account flags; probable)]; UI.QueueEligibility [0x2101]; UI.RemovedFromQueue [0x20e0 0x210b]; UI.ShowURLDialog; UI.ToggleMainMenu; UI.UIStateMachineEvent [0x2038 0x2053]; UI.UserCanCreateGroup [0x2070] | EM_WebBrowser.?InqFoundCEF3SubprocessExecutable; GM_Achievement.RequestAllPendingRewardlessAchievementNotifications [0x212e]; GM_Character.RequestAccountCurrencyBalance; GM_Character.RequestAccountLevelAndXP; GM_Character.RequestPostMatchChanges [0x20ba]; GM_Character.Ribbon_ReceivedItemsFulfilled; GM_Character.UI_RequestPendingRewardUpdateFromServer [0x2124]; GM_Chat.HideChatForBrowser; GM_Chat.HideChatWindow; GM_Chat.RestoreChatForBrowser; GM_Chat.ShowChatWindow; GM_ConnectionManager.ResetLastConnectionErrorString; GM_ConnectionManager.?CheckLobbyConnection; GM_ConnectionManager.?InqLastConnectionErrorString; GM_Contacts.?UI_CanInviteSteamFriends; GM_CustomMatch.?IsInCustomMatch [0x20fb]; GM_Dialog.SetUIDialogIdleState; GM_Dialog.SetUIDialogInQueueState; GM_Encounter.DisplayEncounterWebInfo; GM_Encounter.PlayedEncounterOverviewMovie; GM_Encounter.?InqPVPEncounters; GM_UI.DisplayPendingDodgePenaltyNotifications [0x21a8]; GM_UI.InGameMenuClosed; GM_UI.InGameMenuOpened; GM_UI.JoinQueue [0x20eb]; GM_UI.JoinQueueForPromotedMap [0x20eb]; GM_UI.RequestProtectorAdvancementStatus; GM_UI.UIStateMachineEvent; GM_UI.?InqQueueEligibility; GM_UI.?IsBinkFileValid; GM_UI.?IsLoggedIntoGame; GM_UI.?NeedsUpdateNews; GM_ViewMatch.?RequestInViewMatchModeLastMatch |
| `0x200000aa` | `02a70580` | encounter / map / mode / tutorial selection | 16 | Achievement.AllPendingAchivementBanners [0x211f]; Character.RewardSetsData [0x2125 0x2197]; Character.Ribbon_CharacterLevelChanged [0x2104]; Character.Ribbon_FinishedItemsFulfilled [0x2095]; Character.Ribbon_ItemFulfilled [0x2095]; Character.SendAccountCurrencyBalance [0x2081]; Character.SendAccountEndOfMatchAccoladesEarned [0x2104 0x2188]; Character.SendAccountLevelAndXP [0x2080]; Character.SendBestChampAccolades [0x2186]; Character.SendBestMapAccolades [0x2186]; Chat.UI_ShowWrapperGeneralChatWindow; CustomMatch.UI_CustomMatch_Cancelled [0x2011]; CustomMatch.UI_CustomMatch_Kicked [0x2041]; CustomMatch.UI_CustomMatch_Left [0x203f]; Encounter.ResetMapSelectionList [0x2024 0x20ff]; Grouping.PlayerLeftGroup [0x2071]; Lobby.LobbyRejoinRoom [0x205b]; UI.ActionEnumEvent; UI.BarredFromMatching [0x20f3]; UI.DisplayDialogText [0x2087 0x20ed 0x210a 0x210b]; UI.FoundMatch [0x20fa]; UI.JoinedQueue [0x20c0]; UI.PendingMatchFailure [0x20d7 0x210b]; UI.ProtectorAdvancementStatus [0x215d (account flags; probable)]; UI.QueueEligibility [0x2101]; UI.RemovedFromQueue [0x20e0 0x210b]; UI.SendHeaderNameAndProtectorIcons [0x2154 0x2190]; UI.ShowURLDialog; UI.ToggleMainMenu; UI.UIStateMachineEvent [0x2038 0x2053]; UI.UserCanCreateGroup [0x2070] | EM_WebBrowser.?InqFoundCEF3SubprocessExecutable; GM_Achievement.RequestAllPendingRewardlessAchievementNotifications [0x212e]; GM_Character.RequestAccountCurrencyBalance; GM_Character.RequestAccountEndOfMatchAccoladesEarned; GM_Character.RequestAccountLevelAndXP; GM_Character.RequestPostMatchChanges [0x20ba]; GM_Character.Ribbon_ReceivedItemsFulfilled; GM_Character.UI_RequestBestAccolades; GM_Character.UI_RequestPendingRewardUpdateFromServer [0x2124]; GM_Chat.HideChatForBrowser; GM_Chat.HideChatWindow; GM_Chat.RestoreChatForBrowser; GM_Chat.ShowChatWindow; GM_ConnectionManager.ResetLastConnectionErrorString; GM_ConnectionManager.?CheckLobbyConnection; GM_ConnectionManager.?InqLastConnectionErrorString; GM_Contacts.?UI_CanInviteSteamFriends; GM_CustomMatch.Create_CustomMatch [0x20c1]; GM_CustomMatch.?IsInCustomMatch [0x20fb]; GM_Dialog.SetUIDialogIdleState; GM_Dialog.SetUIDialogInQueueState; GM_Encounter.DisplayEncounterWebInfo; GM_Encounter.PlayedEncounterOverviewMovie; GM_Encounter.?InqPVPEncounters; GM_Grouping.CacheQueueForGrouping; GM_UI.CanUserCreateGroup; GM_UI.DisplayPendingDodgePenaltyNotifications [0x21a8]; GM_UI.InGameMenuClosed; GM_UI.InGameMenuOpened; GM_UI.JoinQueue [0x20eb]; GM_UI.JoinQueueForPromotedMap [0x20eb]; GM_UI.RequestHeaderUIData; GM_UI.RequestProtectorAdvancementStatus; GM_UI.UIStateMachineEvent; GM_UI.?GetWaitTimeForQueue; GM_UI.?InqQueueEligibility; GM_UI.?IsBinkFileValid; GM_UI.?IsLoggedIntoGame; GM_UI.?NeedsUpdateNews; GM_ViewMatch.?RequestInViewMatchModeLastMatch |
| `0x200000ab` | `02a830f4` | floaty verbs | 2 | - | - |
| `0x200000ad` | `02a910e0` | scorecard accolades tab | 13 | Achievement.AchievementDetails; Achievement.AllPendingAchivementBanners [0x211f]; Achievement.SetAchievementData [local: built from achievement records after 0x2120 (guess)]; Achievement.SetAchievementObjectiveData [0x2120 0x21a6]; Achievement.SetDeprecatedAchievements [0x2120 0x21a6]; Achievement.TraineeAchievements; Character.RewardSetsData [0x2125 0x2197]; Character.Ribbon_CharacterLevelChanged [0x2104]; Character.Ribbon_FinishedItemsFulfilled [0x2095]; Character.Ribbon_ItemFulfilled [0x2095]; Character.SendAccountCurrencyBalance [0x2081]; Character.SendAccountEndOfMatchAccoladesEarned [0x2104 0x2188]; Character.SendAccountEndOfMatchCharacterLevelAndXP [0x2104]; Character.SendAccountEndOfMatchLevelAndXP [0x2080]; Character.SendAccountEndOfMatchSoftCurrencyReward [0x20b9]; Character.SendAccountLevelAndXP [0x2080]; CustomMatch.UI_CustomMatch_Cancelled [0x2011]; CustomMatch.UI_CustomMatch_Kicked [0x2041]; CustomMatch.UI_CustomMatch_Left [0x203f]; Encounter.ResetMapSelectionList [0x2024 0x20ff]; Encounter.UI_LastMapPlayed [0x214b]; Encounter.UI_SendEndOfMatchStats [0x2045 (progression-meta)]; Encounter.UI_SetEndOfMatchStatsHeader [0x2028 0x2045]; Grouping.PlayerLeftGroup [0x2071]; Lobby.LobbyRejoinRoom [0x205b]; UI.ActionEnumEvent; UI.AvailableCharacterList [0x20b8]; UI.BarredFromMatching [0x20f3]; UI.CharacterAdvancementData [0x209d (layout match)]; UI.DisplayDialogText [0x2087 0x20ed 0x210a 0x210b]; UI.FoundMatch [0x20fa]; UI.Incremental_ItemStatuses [0x204c 0x20b8]; UI.ItemStatuses [0x20b8]; UI.JoinedQueue [0x20c0]; UI.PendingMatchFailure [0x20d7 0x210b]; UI.ProtectorAdvancementStatus [0x215d (account flags; probable)]; UI.QueueEligibility [0x2101]; UI.RemovedFromQueue [0x20e0 0x210b]; UI.SendHeaderNameAndProtectorIcons [0x2154 0x2190]; UI.ShowURLDialog; UI.ToggleMainMenu; UI.UIStateMachineEvent [0x2038 0x2053]; UI.UI_DeliverAccountStandingsData [0x219e 0x219f]; UI.UI_DeliverStaticStandingsData [0x219e/0x219f (one of)]; UI.UserCanCreateGroup [0x2070]; Upgrade.UpdateCurrentUpgrades [0x20e2]; Upgrade.UpdatePowerGraphValues [0x20e2] | EM_WebBrowser.?InqFoundCEF3SubprocessExecutable; GM_Achievement.RequestAchievementDetails; GM_Achievement.RequestAllAchievementData [0x211d]; GM_Achievement.RequestAllPendingRewardlessAchievementNotifications [0x212e]; GM_Achievement.RequestTraineeAchievements; GM_Character.RequestAccountCurrencyBalance; GM_Character.RequestAccountCurrencyBalanceChanges; GM_Character.RequestAccountEndOfMatchAccoladesEarned; GM_Character.RequestAccountEndOfMatchAccountLevelAndXP; GM_Character.RequestAccountEndOfMatchCharacterLevelAndXP; GM_Character.RequestAccountEndOfMatchSoftCurrencyReward; GM_Character.RequestAccountLevelAndXP; GM_Character.RequestPostMatchChanges [0x20ba]; GM_Character.Ribbon_ReceivedItemsFulfilled; GM_Character.UI_RequestPendingRewardUpdateFromServer [0x2124]; GM_Character.?UI_RequestAspirationalTooltip; GM_ConnectionManager.ResetLastConnectionErrorString; GM_ConnectionManager.?CheckLobbyConnection; GM_ConnectionManager.?InqLastConnectionErrorString; GM_Contacts.?UI_CanInviteSteamFriends; GM_CustomMatch.?IsInCustomMatch [0x20fb]; GM_Dialog.SetUIDialogIdleState; GM_Dialog.SetUIDialogInQueueState; GM_Encounter.RequestLastMapPlayed; GM_Encounter.RequestPostMatchScorecard; GM_Encounter.?InqPVPEncounters; GM_Grouping.?IsInGroup; GM_Lobby.?RequestStolenPowerList [0x2017]; GM_UI.DisplayPendingDodgePenaltyNotifications [0x21a8]; GM_UI.JoinQueue [0x20eb]; GM_UI.JoinQueueForPromotedMap [0x20eb]; GM_UI.RequestAccountStandingsData [0x2178 (probable)]; GM_UI.RequestCharacterAdvancementData; GM_UI.RequestHeaderUIData; GM_UI.RequestItemStatuses; GM_UI.RequestProtectorAdvancementStatus; GM_UI.RequestStaticStandingsData [0x2193 (probable)]; GM_UI.UIStateMachineEvent; GM_UI.?InqQueueEligibility; GM_UI.?IsLoggedIntoGame; GM_UI.?NeedsUpdateNews; GM_ViewMatch.?RequestInViewMatchMode; GM_ViewMatch.?RequestInViewMatchModeLastMatch |
| `0x200000ae` | `02aa1c48` | accolades widget | 5 | UI.AvailableCharacterList [0x20b8]; UI.CharacterAdvancementData [0x209d (layout match)]; UI.Incremental_ItemStatuses [0x204c 0x20b8]; UI.ItemStatuses [0x20b8] | GM_UI.RequestCharacterAdvancementData; GM_UI.RequestItemStatuses; GM_ViewMatch.?RequestInViewMatchMode |
| `0x200000b0` | `02b260a0` | ranked badges | 8 | ProfileUI.ProfileUI_HeavyResourcePackData; UI.AvailableCharacterList [0x20b8]; UI.CharacterAdvancementData [0x209d (layout match)]; UI.DeliverFriendsLeaderboard [0x21a2 0x21a3]; UI.DeliverRegionalLeaderboard [0x21a2 0x21a3]; UI.Incremental_ItemStatuses [0x204c 0x20b8]; UI.ItemStatuses [0x20b8] | GM_Dialog.PlayUIDialogElement; GM_UI.RankedBanner_SelectCharacter; GM_UI.RequestCharacterAdvancementData; GM_UI.RequestItemStatuses; GM_UI.RequestLeaderboards [0x21a4]; GM_ViewMatch.?RequestInViewMatchMode |
| `0x200000b1` | `02b559a0` | login rewards | 12 | Achievement.AllPendingAchivementBanners [0x211f]; Character.RewardSetsData [0x2125 0x2197]; Character.Ribbon_CharacterLevelChanged [0x2104]; Character.Ribbon_FinishedItemsFulfilled [0x2095]; Character.Ribbon_ItemFulfilled [0x2095]; Character.SendAccountCurrencyBalance [0x2081]; Character.SendAccountLevelAndXP [0x2080]; Chat.UI_ShowWrapperGeneralChatWindow; CustomMatch.UI_CustomMatch_Cancelled [0x2011]; CustomMatch.UI_CustomMatch_Kicked [0x2041]; CustomMatch.UI_CustomMatch_Left [0x203f]; Grouping.PlayerLeftGroup [0x2071]; Lobby.LobbyRejoinRoom [0x205b]; LoginReward.UI_DeliverLoginRewardSet [0x2197 (progression-meta)]; LoginReward.UI_NoEligibleLoginReward [0x219d]; UI.ActionEnumEvent; UI.BarredFromMatching [0x20f3]; UI.DisplayDialogText [0x2087 0x20ed 0x210a 0x210b]; UI.FoundMatch [0x20fa]; UI.JoinedQueue [0x20c0]; UI.PendingMatchFailure [0x20d7 0x210b]; UI.ProtectorAdvancementStatus [0x215d (account flags; probable)]; UI.RemovedFromQueue [0x20e0 0x210b]; UI.ShowURLDialog; UI.ToggleMainMenu; UI.UIStateMachineEvent [0x2038 0x2053]; UI.UserCanCreateGroup [0x2070] | EM_WebBrowser.?InqFoundCEF3SubprocessExecutable; GM_Achievement.RequestAllPendingRewardlessAchievementNotifications [0x212e]; GM_Character.RequestAccountCurrencyBalance; GM_Character.RequestAccountLevelAndXP; GM_Character.RequestPostMatchChanges [0x20ba]; GM_Character.Ribbon_ReceivedItemsFulfilled; GM_Character.UI_RequestPendingRewardUpdateFromServer [0x2124]; GM_Chat.HideChatForBrowser; GM_Chat.HideChatWindow; GM_Chat.RestoreChatForBrowser; GM_Chat.ShowChatWindow; GM_ConnectionManager.ResetLastConnectionErrorString; GM_ConnectionManager.?CheckLobbyConnection; GM_ConnectionManager.?InqLastConnectionErrorString; GM_Contacts.?UI_CanInviteSteamFriends; GM_CustomMatch.?IsInCustomMatch [0x20fb]; GM_Dialog.SetUIDialogIdleState; GM_Dialog.SetUIDialogInQueueState; GM_LoginReward.QueueLoginReward; GM_LoginReward.ReadyForLoginRewardSet; GM_UI.DisplayPendingDodgePenaltyNotifications [0x21a8]; GM_UI.JoinQueue [0x20eb]; GM_UI.JoinQueueForPromotedMap [0x20eb]; GM_UI.RequestProtectorAdvancementStatus; GM_UI.UIStateMachineEvent; GM_UI.?IsLoggedIntoGame; GM_UI.?NeedsUpdateNews; GM_ViewMatch.?RequestInViewMatchModeLastMatch |
| `0x200000b2` | `02b8b24c` | ranked / leaderboards screen | 10 | Achievement.AllPendingAchivementBanners [0x211f]; Character.RewardSetsData [0x2125 0x2197]; Character.Ribbon_CharacterLevelChanged [0x2104]; Character.Ribbon_FinishedItemsFulfilled [0x2095]; Character.Ribbon_ItemFulfilled [0x2095]; Character.SendAccountCurrencyBalance [0x2081]; Character.SendAccountLevelAndXP [0x2080]; Chat.UI_ShowWrapperGeneralChatWindow; CustomMatch.UI_CustomMatch_Cancelled [0x2011]; CustomMatch.UI_CustomMatch_Kicked [0x2041]; CustomMatch.UI_CustomMatch_Left [0x203f]; Encounter.ResetMapSelectionList [0x2024 0x20ff]; Grouping.PlayerLeftGroup [0x2071]; Lobby.LobbyRejoinRoom [0x205b]; ProfileUI.ProfileUI_HeavyResourcePackData; UI.ActionEnumEvent; UI.AvailableCharacterList [0x20b8]; UI.BarredFromMatching [0x20f3]; UI.CharacterAdvancementData [0x209d (layout match)]; UI.DeliverFriendsLeaderboard [0x21a2 0x21a3]; UI.DeliverRegionalLeaderboard [0x21a2 0x21a3]; UI.DisplayDialogText [0x2087 0x20ed 0x210a 0x210b]; UI.FoundMatch [0x20fa]; UI.Incremental_ItemStatuses [0x204c 0x20b8]; UI.ItemStatuses [0x20b8]; UI.JoinedQueue [0x20c0]; UI.PendingMatchFailure [0x20d7 0x210b]; UI.ProtectorAdvancementStatus [0x215d (account flags; probable)]; UI.QueueEligibility [0x2101]; UI.RemovedFromQueue [0x20e0 0x210b]; UI.ShowURLDialog; UI.ToggleMainMenu; UI.UIStateMachineEvent [0x2038 0x2053]; UI.UI_DeliverAccountStandingsData [0x219e 0x219f]; UI.UI_DeliverStaticStandingsData [0x219e/0x219f (one of)]; UI.UserCanCreateGroup [0x2070] | EM_WebBrowser.?InqFoundCEF3SubprocessExecutable; GM_Achievement.RequestAllPendingRewardlessAchievementNotifications [0x212e]; GM_Character.RequestAccountCurrencyBalance; GM_Character.RequestAccountLevelAndXP; GM_Character.RequestPostMatchChanges [0x20ba]; GM_Character.Ribbon_ReceivedItemsFulfilled; GM_Character.UI_RequestPendingRewardUpdateFromServer [0x2124]; GM_Chat.HideChatForBrowser; GM_Chat.HideChatWindow; GM_Chat.RestoreChatForBrowser; GM_Chat.ShowChatWindow; GM_ConnectionManager.ResetLastConnectionErrorString; GM_ConnectionManager.?CheckLobbyConnection; GM_ConnectionManager.?InqLastConnectionErrorString; GM_Contacts.?UI_CanInviteSteamFriends; GM_CustomMatch.?IsInCustomMatch [0x20fb]; GM_Dialog.SetUIDialogIdleState; GM_Dialog.SetUIDialogInQueueState; GM_Encounter.?InqPVPEncounters; GM_UI.DisplayPendingDodgePenaltyNotifications [0x21a8]; GM_UI.JoinQueue [0x20eb]; GM_UI.JoinQueueForPromotedMap [0x20eb]; GM_UI.RequestAccountStandingsData [0x2178 (probable)]; GM_UI.RequestCharacterAdvancementData; GM_UI.RequestItemStatuses; GM_UI.RequestLeaderboards [0x21a4]; GM_UI.RequestProtectorAdvancementStatus; GM_UI.RequestStaticStandingsData [0x2193 (probable)]; GM_UI.UIStateMachineEvent; GM_UI.?InqQueueEligibility; GM_UI.?IsLoggedIntoGame; GM_UI.?NeedsUpdateNews; GM_ViewMatch.?RequestInViewMatchMode; GM_ViewMatch.?RequestInViewMatchModeLastMatch |

---

## 8. Enums used by the notices

Values of the `emp_gen.*List` classes (suffix `_<Type>` dropped). The 101 UI state-machine events are in 2.5; input
actions (174 + 144), Wwise events (273) and dialog element keys (87) are not listed (client-local).

| enum | n | values |
|---|---|---|
| AccoladeRankTypeList | 3 | Gold=1, Silver=2, Bronze=3 |
| AchievementCategoryTypeList | 4 | General=1, Training=2, ProtectorLevel=3, ChampionLevel=4 |
| AchievementObjectiveTypeList | 11 | ProtectorLevel=1, Kill=2, MatchComplete=3, MatchWin=4, Game=5, CharacterCycle=6, CharacterLevel5=7, MatchmadeComplete=8, MatchmadeWin=9, ChampionLevel=10, ChampionOwned=11 |
| AchievementRepeatTypeList | 5 | Never=1, Daily=2, Weekly=3, Monthly=4, BiWeekly=5 |
| AchievementVisibilityTypeList | 4 | Hidden=1, Hidden_Until_Dependencies_Cleared=2, Visible=3, Secret=4 |
| ActionClassList | 6 | ActionClass_Debug=2, ActionClass_emote=3, ActionClass_movement=4, ActionClass_UI=5, ActionClass_camera=6, ActionClass_gsys=7 |
| BillboardUpdateTypeList | 7 | GenericText=2, Location=6, MatchTie=7, MatchLoss=8, MatchWin=9, Team2Victory=10, Team1Victory=11 |
| ClientMissionEventList | 10 | SelectedArtifact=1, FoundryClosed=2, FoundryOpened=3, LobbyReady=4, CorrectStolenPowerChosen=5, ReadyButtonPressed=6, StolenPowerSubMenuOpened=7, StolenPowerMenuOpened=8, LobbyMatchWarningStart=9, LobbyAbandoned=10 |
| ContactListTypeList | 2 | Friend=1, Ignored=2 |
| ContactPresenceTypeList | 9 | Online=1, Away=2, Offline=3, InGame=4, InQueue=5, InLobby=6, InGroup=7, InGroupQueued=8, InCustomMatch=9 |
| ContentStatusList | 8 | Free=1, Available=2, Disabled=3, Unreleased=4, Hidden=5, AlwaysOwned=6, Innate=1001, Unavailable=1002 |
| ContentTypeList | 25 | Character=1, StolenPower=2, AvatarIcon=3, Skins=4, Amplifier=5, Boost=6, Currency=7, Bundle=8, Skill=9, Texture=10, Artifact=11, Augments=12, Mods=13, Entitlement=14, GenericDataID=15, SubCurrency=16, Achievement=17, RewardSet=18, RewardGroup=19, AccountXP=20, Encounter=21, Effect=22, TrainingLesson=23, Accolade=24, LoginReward=25 |
| CustomMatchPermissionsList | 9 | Can_Launch=1, Can_Assign_Self=2, Can_Assign_All=4, Can_Invite=8, All_Participants=32, Can_Kick=64, Coordinator=77, GlobalInvite=40, GlobalAssign=36 |
| DamageTypeList | 5 | Attack=1, Power=2, TrueDamage=3, MixedDamage=4, MAX=3 |
| DialogElementKeyList | 87 | (not listed: CODE_UI_ANC_Wrapper_AccountCreate_Universe_43_DialogElementKey, CODE_UI_ANC_Wrapper_Profile_DialogElementKey, CODE_UI_ANC_Wrapper_Initialization_DialogElementKey, ...) |
| EncounterIdentifierTypeList | 12 | Gas_Lane=1, Gas_Lane_Tournament=2, Got_Dominion=3, Got_Rift=4, Cst_Onslaught=5, Mch_Aram=6, Tutorial_Basic=7, Tutorial_Intermediate=8, Tutorial_Advanced=9, Test=10, Destruction=11, Unknown=12 |
| EncounterLobbyRulesList | 3 | BlindPick=1, Draft=2, AllRandom=3 |
| EnumVitalTypeList | 8 | Katana_QQ=1, Katana_Q=2, Katana_WQ=3, Katana_QW=4, Katana_W=5, Katana_WW=6, Katana_None=7, Last=8 |
| FloatyAttachTypeList | 5 | SmoothSkinnedTop=1, PhysicsBottom=2, PhysicsCenter=3, PhysicsTop=4, ApplyTargetFX_0=5 |
| FloatyStatusTypeList | 15 | Silence=1, Stun=2, Blind=3, KnockedUp=4, Slow=5, Fear=6, Blocked=7, Cleanse=8, Taunt=9, Root=10, KnockedDown=11, Suppressed=12, Wounded=13, Immune=14, Crippled=16 |
| InputActionList | 174 | (not listed: InputAction_Console_MenuConfirm, InputAction_TestInterpolation, InputAction_AlternateTapRight, ...) |
| InputMapIDList | 13 | DialogBoxes=1, ScrollableControls_Mouse=2, DebugInputMode=3, DebugConsole=4, IgnoreRemainingMaps=5, ScrollableControls=6, EditControls=7, CSM=8, StringTokenDebugger=9, CopyAndPasteControls=10, EatKeyboardInput=11, Main=12, DebugConsoleActive=13 |
| InviteStatusList | 3 | Declined=1, Accepted=2, Pending=3 |
| LifeStateList | 5 | DeadAndFaded=1, Dead=2, Incapacitated=3, Alive=4, Respawning=5 |
| MapNoteCategoryList | 27 | PING=1, CHARACTER=2, TURRET=3, METEOR_PICKUP=4, HEALTH_PICKUP=5, BASE=6, AGENT=7, CAPTURE_POINT=8, MINION=9, BLANK=11, STORMSHIELD_PICKUP=12, SPEED_PICKUP=13, SKILL_BAT_SCREAM=14, GENERIC_PICKUP=15, CAMERA=16, ALERT_PING=17, ALERT_PING_INGAME=18, PING_INGAME=19, RETREAT_PING_INGAME=21, RETREAT_PING=22, STATIC=23, SMALL_CAPTURABLE=26, LARGE_CAPTURABLE=27, LARGE_MAPOBJECTIVE=28, BEACON=29, POWERCORE=30, DEVICE=31 |
| MapNoteDecorationTypeList | 10 | Meteor_Impact_Zone=1, DOOMSDAY_REVENGE_OVERLAY=2, Meteor_Devastation_Zone=3, RetreatPingTarget=5, AlertPingTarget=6, Locked=7, Disabled=8, BeaconAlert=9, Highlight=10, WonderWoman_Reclaimer=11 |
| MapNoteMessageTypeList | 11 | TriggerGetAwayPing=1, TriggerKnowledgePing=2, TriggerMiniMapMoveToCoordinates=3, TriggerMiniMapCameraMove=4, MiniMapCameraMoveDragEnd=5, MiniMapCameraMoveDragStart=6, MiniMapCharacterMoveDragEnd=7, MiniMapCharacterMoveDragStart=8, MiniMapCameraMoveDragUpdate=9, MiniMapCharacterMoveDragUpdate=10, TriggerMiniMapClicked=20 |
| MissionEventNotificationSeverityList | 3 | High=1, Medium=2, Low=3 |
| ObjectiveCategoryStateList | 7 | Team02Won=3, Team01Won=4, Completed=5, Failed=6, Remove=7, Show=8, Hide=9 |
| ObjectiveStateList | 5 | Failed=1, Completed=2, NearCompletion=4, Team02Won=5, Team01Won=6 |
| PerceivedTypeList | 37 | Boss=1, SmallEnvironmentalObject=2, Loot=4, Character=8, Turret=16, Missile=32, CharacterInteractive=64, LargeEnvironmentalObject=128, Creature=256, Objective=512, Siege=1024, Inhibitor=2048, Destructible=4096, Deco=8192, Base=16384, AutomatedPlayer=32768, Minion=65536, Device=131072, DoomsdayDevice=262144, CapturePoint=524288, Pet=1048576, Player=2097152, Lieutenant=4194304, All=8388607, HasMapNote=589848, PersistAfterDeath=2064, CannotBeCombatTargeted=524288, WalkingEntities=1114120, EnvironmentalObject=130, DefaultBasicAttackTarget=5593433, DefaultCombatTarget=4522249, Structures=542736, FogOfWar_Friend=2050424, FogOfWar_MustFadeOut=1245480, CreateGameComponents=8346107, ComplexAI=935952, AlwaysPerceived=166 |
| PostMatchRewardTypeList | 10 | Merit=1, CrisisCoins=2, AccountIcon=3, ServerOriginated=4, AccountXPFlat=5, AccountXPPercent=6, Character=7, Augment=8, Mod=9, Costume=10 |
| PowerGraphCategoryList | 4 | Attack=1, Health=2, Power=3, General=4 |
| ProtectorAdvancementStatusTypeList | 3 | Player=1, Trainee=2, FirstTimePlayer=3 |
| RankedDisplayTierList | 4 | Diamond=1, Gold=2, Silver=3, Bronze=4 |
| RelationshipList | 4 | Neutral=1, Enemy=2, Friend=4, All=7 |
| RewardBestowalTypeList | 3 | Choice=1, Grant=2, AutoGrant=3 |
| RewardQualityTypeList | 3 | Gold=1, Silver=2, Bronze=3 |
| RewardSourceTypeList | 2 | Achievement=1, LoginReward=2 |
| SkillSlotList | 27 | BasicAttack=0, Skill1=1, Skill2=2, Skill3=3, UltimateAttack=4, Passive=5, Recall=6, Secondary1=7, Secondary2=8, Bonus=9, Item1=10, Item2=11, Item3=12, Item4=13, Item5=14, Item6=15, AllCharacterSkills=-3, All=-2, Invalid=-1, First=0, Last=15, LastActiveCharacter=4, LastRankable=5, FirstItemSkill=10, LastItemSkill=15, FirstPowerSetSkill=1, LastPowerSetSkill=4 |
| SkillSmartcastOptionList | 4 | None=0, OnRelease=1, OnPress=2, Invalid=-1 |
| SkillUIOverlayList | 4 | MultiPress=1, Toggle=2, Pulse=3, LoadAndFire=4 |
| TeamUsageLockList | 3 | Team1=1, Team2=2, AllTeams=3 |
| TrainingFloatyDisplayTypeList | 2 | Simple=5, SpendSkillPoints=10 |
| UpgradeTransactionResultList | 12 | CANNOT_SELL_INVALID_UPGRADE=1, BUY_OK=2, CANNOT_BUY_INVALID_UPGRADE=3, CANNOT_BUY_NO_VENDOR_ACCESS=4, CANNOT_BUY_NO_AVAILABLE_SLOTS=5, CANNOT_BUY_ALREADY_OWN_MAX=6, CANNOT_BUY_NOT_ENOUGH_CURRENCY=7, CANNOT_SELL_NO_VENDOR_ACCESS=8, SELL_OK=9, CANNOT_SELL_DO_NOT_OWN=10, CANNOT_BUY_CURRENTLY_RESTRICTED=11, CANNOT_SELL_CURRENTLY_RESTRICTED=12 |
| UserActionMetricList | 1 | Trainee_LastStep_PlayButtonPressed_UserActionMetric=1 |
| VitalDisplayTypeList | 9 | Expanded=1, SimpleElite=2, Simple=3, Champion=4, ExpandedElite=5, ExpandedLargeElite=6, ExpandedLarge=7, SimpleLargeElite=8, SimpleLarge=9 |
| VitalTypeList | 7 | Energy=1, Health=2, CaptureBuffer=3, Fury=4, Mana=5, Utility=6, Enum=7 |
| gmChatLogTypeList | 6 | CustomMatch=1, General=2, Private=3, Group=4, All=8, Team=9 |
| gmErrorTypeList | 48 | Invalid=0, SkillRank_InvalidRank=0x10000008, Skill_OutOfHealth=0x10000009, SkillRank_NotEnoughSkillPoints=0x10000014, Skill_OutOfEnergy=0x10000016, SkillRank_NotManuallyChanged=0x10000017, SkillRank_AtMaxRank=0x10000018, SkillRank_NotHighEnoughLevel=0x10000022, Usage_Interrupted=0x1000002c, SkillRank_Skill_NotDefined=0x1000002d, Usage_TemporarilyBlocked=0x10000031, Skill_InCooldown=0x10000033, Skill_PathBlocked=0x10000034, ActionInProgress=0x10000035, Disconnect_SixtySeconds=0x10000036, Disconnect_ThirtySeconds=0x10000037, Disconnect_TenSeconds=0x10000038, Disconnect_Reconnect=0x10000039, Skill_Silenced=0x1000003b, Skill_InvalidTarget=0x1000003c, Skill_NoCharges=0x10000045, Skill_Rooted=0x10000050, Skill_Stunned=0x10000051, Skill_NotRanked=0x10000053, Skill_UserNotAlive=0x10000054, Skill_NoResources=0x10000055, Skill_NoMutex=0x10000056, Skill_NoValidTargets=0x10000059, Contact_InviteFailed_InvalidName=0x1000005a, Contact_NoteTooLong=0x1000005c, Contact_Group_NameTooLong=0x1000005d, Contact_Contact_NameTooLong=0x1000005e, Contact_StatusMessageTooLong=0x1000005f, Contact_InviteFailed_CannotInviteSelf=0x10000060, Contact_InviteFailed_AlreadyContact=0x10000061, Contact_InviteSent=0x10000062, Amplifier_SaveAmplifierSet_Failed=0x10000063, Amplifier_LoadAmplifierSets_Failed=0x10000064, Amplifier_SetNameTooLarge=0x10000065, Skill_NotUsable=0x10000066, ContextualPurchase_GeneralError=0x10000068, ContextualPurchase_InsufficentFunds=0x10000069, Skill_Crippled=0x1000006b, Skill_QueueBlocked=0x1000006c, Contact_IgnoreListTooLarge=0x1000006e, Contact_InviteFailed_TheirFriendsListTooLarge=0x1000006f, Contact_InviteFailed_YourFriendsListTooLarge=0x10000070, SkillRank_NeedPrerequisite=0x10000072 |
| gmInputActionList | 144 | (not listed: InputAction_UIBasic_Start, InputAction_CameraShift, InputAction_BasicAttack, ...) |
| gmInputMapIDList | 9 | UIActive_HUD=0x10000001, UIBasic=0x10000004, CinematicCamera=0x10000008, BlockInput=0x10000009, UITest_HUD=0x1000000a, UIEscape=0x1000000c, ViewMatch=0x1000000d, EndOfMatch_CinematicCamera=0x1000000f, CinematicCamera_NoSkip=0x10000010 |
| gmMaterialInstanceIDList | 1 | gmFogOfWar_MaterialInstanceID=0x10000001 |
| gmUIHUDElementEventList | 18 | ShowElement=1, HideElement=2, EnterTutorialMode=3, ExitTutorialMode=4, EnableClosing=5, DisableClosing=6, ShowHighlight=7, HideHighlight=8, ShowArrowHighlight=9, HideArrowHighlight=10, OpenElement=11, CloseElement=12, TriggerElement=13, LockdownElement=14, UnLockdownElement=15, Advance=16, FirstRestored=1, LastRestored=10 |
| gmUIHUDElementIDList | 55 | ArtifactFoundry=1, PlayerVitalBars=2, ConversationUI=3, SkillButtonWUpgradeButton=4, SkillButtonRUpgradeButton=5, SkillButtonBasic=6, SkillButtonPassive=7, TeamDisplay=8, SkillButtonQ=9, ReccommendationsPanel=10, CharacterPanel=11, SkillButtonR=12, Timeline=13, SkillsBar=14, Minimap=15, StatsPanel=16, SkillButtonW=17, Portrait=18, SkillButtonPassiveUpgradeButton=19, LevelAndExperience=20, SkillButtonStolenPowerTSkill=21, SkillButtonStolenPower1=22, SkillButtonStolenPower2=23, ArtifactFoundryButton=24, SkillButtonE=25, SkillPointSpendReminder=27, SkillButtonEUpgradeButton=28, CurrentArtifactSlots=29, SkillButtonQUpgradeButton=30, StatusIconDisplay=31, HintManager=32, MatchDisplays=33, SectorObjectiveTracker=34, MissionObjectiveTracker=35, Billboards=36, KillDisplay=37, Defeat=38, SelectionPanel=39, PlayerInfoPanel=40, KillCard=41, SurrenderPanel=42, SkillButtonRecall=43, StatsPanelStatsDisplay=44, SkillsBarUpgradeReccommendedText=45, VMScoreboard=46, StolenPowerPicker=48, CharacterPicker=49, AmplifierSetPicker=50, Lobby=51, CharacterPickerReadyButton=52, VMPlayers=53, StolenPowerPickerPower2=56, StolenPowerPickerPower1=57, LobbyChat=58, RecommendedText=59 |
| gmUIHUDHighlightIDList | 50 | CharacterPortraitReveal=1, SkillsPanelQSkill=2, SkillsPanelStolenPower1Skill=3, SkillsPanelESkill=4, SkillsPanelWUpgradeButton=7, SkillsPanelTSkill=8, SkillsPanelPassiveUpgradeButton=9, SkillsPanelWSkill=10, SkillsPanelEUpgradeButton=11, SkillsPanelRUpgradeButton=12, SkillsPanelRSkill=13, SkillsPanelQUpgradeButton=15, SkillsPanelStolenPower2Skill=16, SkillsPanelPassiveSkill=17, ReccommendationsPanel=18, ObjectiveTracker=19, MiniMap=20, ObjectiveTrackerObjective1=22, ObjectiveTrackerObjective2=23, LevelAndExperience=24, PlayerVitalBars=25, FoundryCurrentlyEquippedArtifacts=26, FoundryReccommendedTab=27, FoundryCurrentlyEquippedSlot1=28, FoundryAllTab=29, FoundrySalvageButton=30, SkillsPanelRecallSkill=31, FoundrySelectedItemPanel=32, FoundryCreditsDisplay=33, FoundryPowerBars=34, FoundryBuildButton=35, FoundryLoreIcon=36, FoundryReccommendedArtifacts=37, StatsPanelStatsDisplay=38, FoundryLaunchButton=39, CharPickerSkillsRoles=40, LobbyAllyPortraits=41, CharPickerCharButtons=42, LobbyChat=43, LobbyYourPortrait=44, LobbyTimeLimit=45, LobbyEnemeyPortraits=46, StolenPowerPickerSlots=47, StolenPowerPickerSlot1=48, StolenPowerPickerSlot2=49, AmplifierSetPicker=50, CharPickerReadyButton=51, CharPicker=52, PlayerSecondaryVitalBar=53, Timeline=54 |
| gmUIStateMachineEventIDList | 101 | (not listed: TransitionToEncounterSelectScreen_UIStateMachineEventID, TransitionToMapSelectionScreenBlind_UIStateMachineEventID, TransitionToMapSelectionScreenAI_UIStateMachineEventID, ...) |
| gmWwiseEventIDList | 273 | (not listed: AS_UI_DROPDOWN_ROLLOVERITEM_WwiseEventID, AS_UI_ITEMS_SELL_WwiseEventID, AS_UI_SUPERBANNER_MAIN_GREENLANTERN_WwiseEventID, ...) |
| gmWwiseParameterIDList | 2 | AS_MVENDERPIP=0x50143568, AS_OMEGA_VENDER_ENHANCEMENT_VALUE=0x665ffab5 |

---

## 9. Top gaps and runtime tests

1. **In-match scoreboard** (`Encounter.UI_UpdateMatchScorecard`, `ViewMatch.ViewMatchScoreboardData`): no network
   source known; `RequestMatchScorecard` has no C->S event. Test: `tools\diag.py` breakpoint on the Flash notice
   dispatch for `0x1000007E` while pressing Tab, then trace back to the network handler.
2. **Trainee landing data** (`Achievement.TraineeAchievements`) and **achievement definitions**
   (`SetAchievementData`): no network event carries them; check whether the client builds them from records after
   `0x2120`. Without them the first-time landing (status 2/3) is empty; status 1 (veteran) avoids it.
3. **Lobby extras**: `Lobby.PreGameTips`, the five `Draft_*` notices, `RequestChangeStolenPower` and
   `PlayerChangedCharacterLockStatus` (C->S) are unmapped; blind pick works without them.
4. **Social C->S**: every `GM_Contacts.*`, `GM_Grouping.*`, six `GM_CustomMatch.*` sends, `PlayerReport.ReportAPlayer`
   and `Contextual.UI_PurchaseContextualItem` have no traced network event. Candidates in `protocol-complete.md` 2.2
   (`0x2112`, `0x20CD`, `0x20E5`, the lobby-client-object slots `0x20C4`...`0x2156`).
5. **Login rewards**: `ReadyForLoginRewardSet` / `QueueLoginReward` C->S; the screen needs `0x2197` or `0x219D`.
6. **Standings**: which of `0x219E` / `0x219F` is the static table (17 arrays) and which the account standings (15).
7. **`0x2009` flags -> objective notices**: the 6 objective setters without a mapped flag (banner text, countdown,
   progress %, team relationship, text, timer duration).
8. **Timeline**: how notices `0x100002AF` / `0x100002B1` / `0x10000424` split into the six `UI_MissionEvent_*` calls.
9. **`UI_Mission_RaiseEvent(eClientMissionEvent)`** (foundry opened/closed, lobby ready, Stolen Power chosen, ready
   pressed): tutorial scripts may wait on these; find the C->S route (script RPC or event).
10. **Selection panel movie `0x2000008A`**: re-extract it from the pack (it exists in `client-scripts-and-ui.md` 2.4,
    22 387 bytes) and add it to the dump.
11. Confirm the layout identifications of 0.6 (`0x2060`, `0x209D`, `0x203B`, `0x2071`) with a breakpoint on the
    handlers' Flash dispatch (`tools\diag.py`).

---

## 10. Method (reproducible)

- Inventory: walk `re-work\ui-as2\*\scripts`, MD5 every file (56 922 files, 992 + 2 299 distinct); offsets mapped to
  DIDs by exact file size of `old_files\tools\gfx\<offset>.gfx` against `client-scripts-and-ui.md` 2.4.
- Movie -> class links: every dotted identifier in the raw `.gfx` bytes that equals a library class, plus class names
  referenced from the movie's frame / clip scripts; closure through class references (fully qualified names and
  same-name classes in the code), depth 4, not through hubs.
- Notice ids: `event_gen\*NoticeIDList.as` getters. GM/EM wrappers: every `static function` with its `event_gen`
  constant, argument list, `getKeyName(id, key)` key and `gameOutputArgs` outputs. Listeners: every
  `engNoticeSystemImpl.Register(event_gen...ID, key, this, this.fn)` and the field accesses on `fn`'s parameters.
  Callers: every `GM_*.SendNotice_*` / `SendQuery_*` in a class. Properties: every `emp_gen.*PropertyList.*_Property`.
  UI state machine: every `gmUIStateMachineEventIDList.*` use (`case`/`==` = handled, otherwise sent).
- Network mapping: `[System.RecvNotice_X]` and `Notice_X__Y` names in the rows of the three protocol notes, numeric
  notice ids of the network-notice table, dispatcher-slot names of the client -> server listeners; plus the layout
  matches and overrides marked in sections 4-5.
- Scripts (temporary, not in the repo): Python over the dump; they can be rebuilt from this description.
