# HUD XP ring (level / experience indicator next to the portrait) (static analysis, 2026-10-26)

Client `InfiniteCrisis.exe` (base 0x400000, VA), AS2 dump `old_files/tools/gfx/classes_all.txt` (HUD movie
`021336ac`, element `0x20000011` / `LevelAndExperience`), WLib `0x39000001` (pack `0xA0000038`), data packs read with
`ics.gamedata`. Tags: **[C]** confirmed from code or data, **[P]** probable, **[G]** guessed. Nothing here was run.

## 1. Cause (one line)

The ring's thresholds come only from the local query `GM_Advancement.InqXPForLevel` (`0x10000011`). No script handler
is registered for it in our sessions, so the C++ query echoes the in/out arguments (0, 0); the ring's span is
`0 - 0 = 0` and `CalculateRelativePercentage` returns 0 when the span is 0, so the ring stays empty whatever XP the
server sends [C for the Flash logic; the "0/0" text was seen in the client, `old_files/HANDOFF.md` item 4].
The XP table itself **is in the packs** (section 3); `[ics] xp_levels` is invented and differs from it.

## 2. What the HUD reads [C, AS2]

`gameplay.experience.ExperienceConsole` (wraps `ExperienceBar`):

| Input | Source | Use |
|---|---|---|
| `m_nLevel` | property `0x10000167` Level of the controlled agent (`ControlledAgentDispatcher.GetLevel`, `LEVEL_CHANGED`) | level text; on change -> `InquireMaxEpxerienceForLevel` |
| `m_nExperience` | property `0x10000142` XP (`GetExperience`, `EXPERIENCE_CHANGED/ADDED`) | **cumulative** total XP |
| `m_nMaxLevel` | `SendQuery_InqLevelCap` (`0x10000009`) -> `iMaxLevel`, asked once in `OnLoadComplete` | no threshold query at max level; max-level effect |
| `m_nMaxXPForLevel`, `m_nOldMaxXPForLevel` | `SendQuery_InqXPForLevel(m_nLevel + 1, io_iXP, io_iXPPreviousLevel)` -> `iXP`, `iXPPreviousLevel` | thresholds |

Ring fill = `(XP - iXPPreviousLevel) / (iXP - iXPPreviousLevel)`. In detail, `DisplayExperienceChanged` calls
`ExperienceBar.OnUpdateValues(oldXP - prev, XP - prev, prev - prevprev, iXP - prev)`, and the bar draws
`round(value / span * 100)` %, or 0 when the span is 0. `iXP` = cumulative XP to reach level L+1, and
`iXPPreviousLevel` = cumulative XP to reach level L.

Things that matter for the server:
- The fallback `TestSetNewXPLevelMax` (L*1000 thresholds) runs only when `iXP` is null, undefined or NaN. An
  unanswered query returns the io arguments (0), so the fallback never runs.
- The thresholds are queried only from `DisplayLevelChanged`, which runs at HUD load (`SetupControlledAgentDispatcher`)
  and on `LEVEL_CHANGED`. `RecvEvent_LevelAdded` (the property appearing for the first time) does **not** query again.
- `ShowExperienceRings` (`0x10000302`) is only Flash -> C++ on mouse-over (tooltip). It is not needed.
- Flash ids [C, AS2 getters]: InqLevelCap = `0x10000009`, InqXPForLevel = `0x10000011`. The `ADVANCEMENT_IDS` labels in
  `tools/diag.py` are shifted by one (they call `0x10000009` "InqXPForLevel" and `0x100004F7` "InqLevelCap").

## 3. Where the client gets the thresholds [C]

The WLib advancement class `0x233` handler InqXPForLevel `0x9B70`, with level argument `n`, returns
`iXP = F(n)` and `iXPPreviousLevel = F(n-1)` (the second only when `n > 1`). It does nothing unless the agent is the
local controlled agent (`0xF80001`).
- `F(level)` = `0x91B8` -> `0xE154`: `0x340001(0xB, 0x10000027)` = `0x439E00` -> DB manager vt+0x30 `0x43E0E0`. This is a
  two-level lookup in the 0x31 enum tables of pack `0xA0000039`: master `0x31000000` key `0xB` -> `0x3100000D`, then
  key `0x10000027` -> **class `0x40000010`**. The same table maps `0x10000030` -> `0x4000007C` (the player class).
  Class `0x40000010` (pack `0xA00000B3`) has **WLib type `0x21D`**, the type that `0xE154` casts to (`0xBE0010`, 541).
- `0xE194(level, agent, table)`: returns 0 unless `1 <= level <= cap(agent)`. Otherwise it returns `array[level - 1]`
  (native `0x290036`). The array comes from `0xE240`: the global flag `0x1000064A` (default 0, set nowhere in the
  packs) selects `0x1000064C` when set, and `0x10000067` otherwise.
- Level cap `0x91E4(agent)` = `min(int property 0x10000975 of the agent (default 19), 100)`. With no local agent it is 19.
  This is also the InqLevelCap handler `0x9BF8`. [P: the `0xA9F0` early-out branch.]

**Data: entity definition `0x49000010`** (pack `0xA00000B3`, record offset `0x865F54`; the twin of class `0x40000010`
by the usual 0x40/0x49 convention [P for the link]), 6 entries:

| Key | Kind | Value |
|---|---|---|
| `0x1000088B` / `0x1000088C` | DID | `0x48000866` / `0x4800085D` (two 0x48 effect records, probably the level-up FX) |
| `0x10000A44` / `0x10000A45` | f32 | 15.0 / 5.0 (meaning unknown) |
| **`0x10000067`** | array of 100 int (element `0x10000223`) | **cumulative XP to reach level L = element L-1**: 0, 300, 700, 1200, 1800, 2500, 3300, 4200, 5200, 6300, 7500, 8800, 10200, 11700, 13300, 15000, 16800, 18700, 20700 (levels 1-19), then 20701 ... 20781 (padding up to 100) |
| `0x1000064C` | array of 19 int | 350, 750, 1200, 1700, 2250, 2850, 3500, 4200, 4950, 5750, 6600, 7500, 8450, 9450, 10500, 11600, 12750, 13950, 15200 (alternative curve, used only when the global `0x1000064A` is set, which never happens) |

Element 0 of `0x10000067` is stored "present without value" (`0x50000223`), i.e. 0. The padding after level 19 and
the default cap of 19 agree with the build records' 19 skill points (one per level, levels 1-19). **The level cap
is 19, not 20** [C for the client's default; P that the original server used it].

## 4. Recipe (what the server must do)

**Step 1 [C data, P that it takes effect]: register the advancement handlers.** Send event `0x9F` to the player object
`LOCAL_PLAYER_ID` (`0x0200000000000001`, class `0x4000007C`, WLib type `0x21C` <- `0x22E`). The message is
`0x81A1000B` (class `0x1A1` method 11 -> `0xC164` -> player slot 198 -> `0x9654`, which registers InqXPForLevel,
InqLevelCap, InqSkillRank, InqCanRankSkill, RankSkill and NextRecommended). The blob is empty.
- Body [P framing]: `u8 0 | u32 0x81A1000B | u32 0` (as `M.set_property` builds it: `build_message(LOCAL_PLAYER_ID, 0x9F,
  ...)`). Client -> server 0x9F arrived without the leading u8 (`ics/session.py ev_script_rpc`), so keep a config
  switch for the form without it, and one for a 4-byte zero blob (`u32 4 | 00000000`) if the log shows no effect
  (`client-scripts-and-ui.md` 1.7).
- **When:** after the player object exists and **before the HUD finishes loading**, i.e. before the client's load
  complete / HUD `OnLoadComplete`. The champion bundle (Level `0x10000167`) must also exist by then, so that
  `GetLevel` at HUD load returns the real level and the first threshold query uses it. If the 0x9F can only be sent
  later, the ring starts working at the first level-up (LEVEL_CHANGED). To repair it at once, send the Level once
  more with a *different* value, then the real one. This plays the level-up effect [P].
- Suggested config: `[ics] advancement_handlers = true`, `advancement_rpc_leading_u8 = true`,
  `advancement_rpc_blob4 = false` (CLAUDE.md rule 4; reason: this report).
- Risk [P]: the same call registers the script InqCanRankSkill / InqSkillRank / RankSkill handlers that the exe
  patches (caves A-E) replace. The patched call sites do not consult the handler list for those queries. The script
  RankSkill (`0x9A88`) may also send `0x9F 0x81910003` beside the ping cave. `ev_script_rpc` only logs it ("not
  handled"), which is harmless. Test with the patches on first.

**Step 2 [C]: properties (no change in kinds).** The champion's `0x10000142` XP = int (kind `0x10`), **cumulative**
(do not reset it at a level-up). `0x10000167` Level = int (kind `0x10`), 1-19. Send changes with the single-property
event (`M.set_property`, 0x6) as now. Do not send `0x10000975` (cap 19 is the default). Nothing else is read for the ring.

**Step 3 [C]: use the game's curve.** Replace `[ics] xp_levels` (total XP for level i+2) with the table's levels
2-19, and set `level_cap = 19`:

```
xp_levels = [300, 700, 1200, 1800, 2500, 3300, 4200, 5200, 6300, 7500, 8800, 10200, 11700, 13300, 15000, 16800, 18700, 20700]
level_cap = 19
```

With the old values (280 ... 22420, cap 20) and the handlers registered, the ring would be wrong. For example a
server level 2 at 280 XP shows -20/400. A server level 20 queries F(21) = 0 and the ring is empty. Better still, read
the table at server start: `Data.record(0x49000010)` returns None today because the reader lacks kinds for
`0x1000088B`/`0x1000088C`/`0x10000A44`/`0x10000A45` or their order. Decode array `0x10000067` directly from the
record, or add the kinds and use it, falling back to the list above. XP per kill is not in this record
(`xp_per_kill` stays a server rule).

**If step 1 cannot work (fallback, G):** an exe cave in `icserver/patcher.py` that answers InqXPForLevel in C++ with the
same table. This means hooking the C++ query dispatcher for id `0x10000011` and writing the two out arguments.
The site is not located here.

## 5. Open points

- Runtime check: `tools\diag.py` breakpoints on `0x962FE0` (register InqXPForLevel) and `0x962EC0` (InqLevelCap)
  after the 0x9F is sent. Then the HUD tooltip should show `XP - F(L) / F(L+1) - F(L)` (for example 0/300 at level 1).
- Exact 0x9F server -> client framing (u8 prefix, empty vs. 4-byte blob).
- Meaning of `0x10000A44` = 15.0 and `0x10000A45` = 5.0 on `0x49000010`, and of the `0xA9F0` branch of the cap.
