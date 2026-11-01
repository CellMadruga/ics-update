# Amplifier (augment / mod) icons: how the client composes them (2026-10-29)

User 2026-10-29: "extract all the images of the amplifiers and augments so they can be seen in the store; right now
only a few have images". Tags: **C** confirmed (code / data), **P** probable, **O** open.

Sources: AS2 `re-work/ui-as2/c_a00000d0_02189b08/scripts/__Packages` (`gameplay/singleton/AmplifierSetManager.as`,
`gameplay/amplifiers/display/AmplifierDisplay.as`, `GM_Amplifier.as`), the decompiled exe `re-work/decomp/c/*.c`, the
constants read from `InfiniteCrisis.exe`, the records of pack `0xA00000B3`.

## 1. No amplifier record holds an icon [C]

An augment's / mod's `0x49` record has 5 entries (augment: `0x10000950` stats, `0x10000951` name, `0x10000953`
description, `0x100009EF`, `0x10000956` brand; mod: `0x10000989` targets, `0x1000097D` / `0x1000097C` texts,
`0x100009F0`, `0x1000097B` brand). The 17 amplifiers for which `Data.template_properties` returned a `0x10000302`
(`0x40000675`, `0x400006B9`, `0x400006BC`, `0x400006C6`, `0x400006C7`, `0x400006CA`, `0x400006DC`, `0x400006DD`,
`0x400006E1`, `0x400006E3`, `0x400006E7`, `0x40000B29`, `0x40000BE6`, `0x40000BE7`, `0x40000BEA`, `0x40000BEB`,
`0x40000E6E`) do not have it in the record: the template reader's window ran into the next records (a tower picture,
skill icons). The store page showed wrong pictures for them.

## 2. Flash side [C]

- `AmplifierSetManager.OnItemStatusesChange` asks C++ `UI_InqModData(mods) -> aNames, aTooltips, aArtifactIcon,
  aBrandIcon, aArtifacts` and `UI_InqAugmentData(augments) -> aNames, aTooltips, aTopLeftIcon, aBottomRightIcon,
  aMiddleIcon`; it stores `didIconArtifact` / `didIconBrand` (mods) and `didIconStatTop` / `didIconStatBottom` /
  `didIconBrand` (augments).
- `AmplifierDisplay.SetAmplifierData`: three stacked icon clips `m_icTop`, `m_icMiddle`, `m_icBottom`. Augment: top =
  stat top-left, middle = stat bottom-right, bottom = brand. Mod: top = brand, middle = none, bottom = artifact icon.
  (The Assembler sorts augments on `[m_didIconStatTop, m_didIconStatBottom, m_didIconBrand]`.)

## 3. C++ side [C]

| Function | What |
|---|---|
| `0xA710F0` | Cache builder. Game-data key `0x100000AF` -> record `0x48000AAD`. `0x100009CB` entries -> table at `DAT_0186dc28..34`: per stat key `0x100009CA` the pair (`0x100009D0`, `0x100009CD`) plus two invalid slots (16 bytes). `0x100009CF` entries -> brand table `DAT_0186dc38..44`: brand `0x10000997` -> `0x100009C9` |
| `0xA21C90(out, stat, &prop)` | stat icon lookup: prop `0x100009CD` -> slot +4, `0x100009D0` -> slot +0 |
| `0xA21CF0(out, brand)` | brand background lookup in the `0x100009C9` table |
| `0xA26F70(augment, &topLeft, &bottomRight, &middle)` | reads `0x10000950` (1 or 2 stat lines); line 0's `0x10000958` with prop constant `0x16017F8` = `0x100009D0` -> top-left; line 1 with `0x16017EC` = `0x100009CD` -> bottom-right; `0x10000956` brand -> `0xA21CF0` -> middle |
| `0xA43xxx` (UI_InqAugmentData / UI_InqModData answer loop) | augment: names / tooltips + `0xA26F70`; mod: `0x1000097D` name, `0x1000097C` tooltip, `0xA271D0` artifact icon, `0x8655F0(0x1000097B)` brand icon, `0x865E80` -> `0x9D1910` root artifact |
| `0xA271D0(out, mod)` | for each `0x10000989` target: `0x1000098B` artifact; when its record loads, `0x8578E0` = its `0x10000436` icon. The last target wins |
| `0x8655F0(brand, out)` | game-data key `0x100000A7` -> record `0x48000A34`; `0x10000999` entries {`0x10000996`, `0x10000997`}; the entry of that brand -> `0x10000996`. Also the in-match `didModBrandOverlayIcon` (`0x9D1xxx` via `0x873540`) |

## 4. Data [C]

`0x48000AAD`: stats (`0x100009CA` -> top-left `0x100009D0`, bottom-right `0x100009CD`): `0x10000B76` Attack Damage
`0x13001F80` / `0x13001FD4`; `0x100006FE` Attack Speed `0x13001F7E` / `0x13001F91`; `0x10000B83` Attack Pen
`0x130020F0` / `0x130020F1`; `0x10000B46` and `0x10000B80` Crit `0x13001F81` / `0x13001F93`; `0x10000B7C` Attack
Lifesteal `0x13001F7F` / `0x13001F92`; `0x10000426` Health `0x13001F7C` / `0x13001F8E`; `0x10000B84` Attack Armor
`0x13001F82` / `0x13001F94`; `0x10000B7A` Power Armor `0x13001F7A` / `0x13001F8C`; `0x100005E4` Move Speed
`0x13001F7B` / `0x13001F8D`; `0x10000B75` Power Damage `0x13001F79` / `0x13001F8B`; `0x10000B7E` Power Pen
`0x130020F2` / `0x13001FD3`; `0x10000B7F` Power Lifesteal `0x13001F95` / `0x13001F8A`; `0x10000B7B` CDR `0x13001F7D` /
`0x13001F90`. Brand backgrounds `0x100009C9`: 2 `0x13001F89`, 3 Kord `0x13001F87`, 4 S.T.A.R. `0x13001F84`, 5 LexCorp
`0x13001F86`, 6 Queen `0x13001F85`, 7 Holt `0x13001F88`, 8 Wayne `0x13001F83`.

`0x48000A34` brand badges `0x10000996`: 2 `0x13001C8D`, 3 `0x13001C89`, 4 `0x13001C83`, 5 `0x13001C87`, 6 `0x13001C85`,
7 `0x13001C8B`, 8 `0x13001C81`.

All layers are 256 x 256 DXT3 with alpha, drawn at full size: the background orb fills 12..246 px, the top-left stat
glyph sits in 30..205, the bottom-right one in 45..230, the brand badge in 169..253 (bottom-right corner). Stacking them
in the Flash order gives the in-game picture.

## 5. Server (ics) [C for the resolution, P for the exact Flash clip offsets]

`ics/store_web.py` `_amp_icon` / `_amp_layers` / `_compose`, `[ics] store_amp_composed_icons` (default true): an
augment = [brand background, stat 2 bottom-right, stat 1 top-left]; a mod = [last target artifact's `0x10000436`
(else an earlier target's), brand badge]; stacked with Pillow (without Pillow: the bottom layer only), cached as
`data/uesrv_cache/store/amp_<did>_c.png`; the prewarm thread composes all 334 + the set slot. An icon really in the
amplifier's record (`0x10000302`, none today) still goes first; false = the old `template_properties` 0x10000302 path.
Coverage (scratchpad check over `AccountData.amplifiers()`): 334 / 334 decode (162 augments with 3 layers, 172 mods with
2 layers).

Open: the clips' positions / scales inside the AmplifierDisplay movie were not read from the GFX (the full-size alpha
layers make offsets unlikely) [O]; the mod fallback to an earlier target's icon when the last target lacks one differs
from the client (which would show none); no store mod needs it (all 172 last targets have `0x10000436`) [C].
