# Artifact Foundry UI: how the item list reaches Flash (static analysis, 2026-10-23)

Context: Crime Alley match, the foundry window opens but lists no items, although patch cave S now runs
`0xA908F0(encounter)` (ecx = Upgrade manager `U = [[0x1B758D4]+0x80]`) and a breakpoint saw `0xA8EBB0` / `0x9D1B00`
load list `0x48000EA9` (210 artifacts). Sources: `InfiniteCrisis.exe` (Ghidra via REA + capstone, VAs, base
0x400000) and the AS2 dump `old_files/tools/gfx/classes_all.txt` (line numbers below). Companion of
`shop-items-inventory.md`. Tags: **[C]** read directly, **[P]** probable, **[?]** open.

## 1. Nothing is pushed: Flash PULLS the list once, synchronously [C]

- No C++ code pushes the catalogue to Flash. `0xA908F0` only calls `0x9D1B00` (via `U` vfunc +4 = `0xA894B0`, fills
  `U+4` = array {ptr, cap, count at `U+0xC`} from the foundry record's `0x1000042C`, elements of kind 0x15) and
  `0xA8EBB0` (filters `0x10000844` / `0x10000837` / `0x1000083A` / `0x10000843` / `0x10000845`); `0xA8EBB0` makes no
  Flash call.
- Flash side: class `gameplay.artifacts.data.ArtifactDataManager` (AS2 l.341000-343300) is a **singleton**
  (`GetInstance`, l.341118, creates `m_admInstance` if null). Its constructor (l.341060) calls `ResetAllData`
  (l.341235) = `RequestAllData` + `GetAllDeepData` + `SetupDIDs` + `SetupFilters`. `ResetAllData` has **no other
  caller** and `m_admInstance` is never cleared, so the data is read **once per movie lifetime**.
- `RequestAllData` (l.341536) calls `GM_Artifact.SendQuery_InqAvailableArtifacts(..., bShowArtifactTiers=true,
  nGraphCategory=Invalid(0))`; `SetupDIDs` calls it per category (`RetrieveAndProcessArtifactDIDs`, l.342656,
  `bShowArtifactTiers=false`, categories Invalid 0 / Attack 1 / Health 2 / Power 3 / General 4 = artifact `0x1000048A`).
- Empty answer: `RequestAllData` calls `GenerateFakeAllData` (9 fake DIDs 1..9); `RetrieveAndProcessArtifactDIDs`
  calls its fake generator as a plain function (`this` undefined, so nothing is stored): the tier-1 / category arrays
  that the foundry grid uses stay **empty**.
- The foundry grid (`CategorizedItemDisplay.OnLoadComplete` -> `SetupArtifactsAndButtons`, l.107029-107060) reads
  `ArtifactDataManager.GetInstance().GetTier1DataByCategory(cat)`, i.e. those cached arrays.
- First `GetInstance` in the HUD: e.g. `ArtifactsCollectionActionButtons.OnLoadComplete` (item skill buttons,
  l.155124-155290), at HUD load. So **the catalogue must be in `U` before the HUD movie loads**; built later, the
  foundry stays empty for the whole match. Cave S runs from the HUD's "re-deliver the map" (`0xA0D810`, once when
  the HUD has loaded): most probably too late. **[P]** (fits the symptom; ordering not traced at run time)

## 2. C++ answer of `Query_Artifact__InqAvailableArtifacts` (`0x100002CC`) [C]

- Registration: `0x878BA0` maps the 7 GM_Artifact query ids (`0x186716C..0x1867184` = `0x100002CB/CC/CD/D9/ED/30B/3DB`)
  to glue `0x92D600 / 0x929F50 / 0x9286C0 / 0x929AA0 / 0x92C370 / 0x928650 / 0x92BB90`. Glue `0x929F50` checks 12 args,
  calls `0x90FAA0`, which looks up the implementor registered by `0xA13240` (`0x878B20` x6) and calls its vfunc +0xC.
  Implementor vtable `0x1601E78`: +0xC = **`0xA44FE0`**.
- `0xA44FE0`: champion = `0x85C150` (local player `0x6351D0` -> player property **`0x100005E8`** iid -> object; may be
  null); list = `0xA12D50()` (`[0x1B758D4]`, created lazily) `+0x80` -> `0x9CFB60` = `U+4`; for every DID calls
  `0x9D2520`.
- `0x9D2520` filters only:
  1. the record must load: `0x8535D0` -> `0x4FDDD0` -> `0x478880` maps a `0x40xxxxxx` class to its **`0x49` twin**
     (`(did & 0x0FFFFFFF) + 0x1000000 + 0x48000000`); a missing record skips the item;
  2. `nGraphCategory != 0` and artifact `0x1000048A` != it -> skip;
  3. `bShowArtifactTiers == false`: `0x9D23A0` walks `0x10000698`/`0x10000697`; only the line's first tier is kept.
  The champion is used only for the mod discount (`0x873450`) and brand overlay icon (`0x873540`/`0x8655F0`).
  **No** check of `0x10000A23`, `0x1000035E`, base, `0x10000B52`/`0x10000B55`, the upgrade component or `0x100000CF`:
  those only grey out items (`InqCanBuyUpgrade` `0x9D1CF0`, refreshed by `RecvNotice_UI_RefreshPurchasability`).

## 3. What a server / patch must do

1. Build the catalogue **before the HUD loads**: run `0xA908F0(encounter)` on `U` at match start, e.g. from the
   `0x20AF` handler (`0xA99F00`, where the encounter is stored at `[[0x1B763C0]+0xC4]`) or the world-load path,
   instead of the HUD re-deliver; or make the original listener `0xA91670` fire early: player property
   `0x100001D3`, **kind 0x15 (DID)** (other kinds read as null and are ignored, `0xA9169F`), a real change, while the
   player object is bound. **[P]**
2. Check: breakpoint at `0xA45001` (after `0x9CFB60`): `[eax+8]` = list count at the first Flash query. 0 = timing
   confirmed. **[C]** (method)
3. No server event/property makes Flash reload the list (no refresh notice exists). Leaving and re-entering the
   HUD movie (a new match) re-runs the query. **[C]**
4. Purchasability (not listing): `0x1000035E` credits, `0x10000A23 = true` (or dead), upgrade component on the
   champion (`obj+0xA4`), no `0x10000B52` whitelist (or `0x10000B55 = true`). See shop-items-inventory.md 3.2.

## 4. Stats of bought items

The client only displays: `0x10000684` is read for tooltips and the power graph (`0xA51760`), not applied. The
server must send the new champion stat property values (and statuses, item skills). See shop-items-inventory.md 4.
