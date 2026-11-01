# Every champion in the game data (survey, 2026-10-21)

Read-only survey of the player's install (`C:\Infinite Crisis Server\rp`, 616 packs) and of `InfiniteCrisis.exe`, for the
preservation server. Only IDs, short names (champion, skin and skill names) and numbers are written here; no
descriptions, bios or other game texts. Scratch scripts (not in the project) did the scans; the method is described
so the result can be reproduced with `icserver.gamedata.Game` / `ics.gamedata.Data`.

**Confidence:** **C** = confirmed in the data or the client code; **G** = guess / probable.

## 1. Summary

| Fact | Value | |
|---|---|---|
| Champions (distinct skill sets) | **54** | C |
| Champion variants (base + costumes) | **156** (54 base + 102 costumes) | C |
| Champion light records (`0x48`, template `0x1000048B` = `0x48000732`) | 156, one per variant | C |
| Champion definitions (`0x49` twin of each `0x40` variant, template `0x48000732`) | 156 | C |
| Packs per champion | 5 per variant (cat 5 wallpaper, 6 light, 7 variant) + 1 shared (cat 8) + 1 skills (cat 4) per champion: 156 + 156 + 158 cat 7, 57 cat 8, 54 cat 4 | C |
| Packs missing from the install | **none** (every pack named by every champion exists) | C |
| Kits | 54 × 6 slots, every slot filled (324 skills) | C |
| Skill scripts (`0x34`) without a decoded tree in `data/script_trees` | 3: `0x3400077A`, `0x34000777` (Arcane Harley Quinn), `0x340007A2` (Arcane Zatanna); the records exist (packs `0xA0000384`, `0xA0000303`), the decoder failed on them (49 of 875 `0x34` records have no tree) | C |
| In `data/champions.json` / `catalog/data/champions.tsv` | 43 champions, 116 variants; **11 champions (34 variants) absent**; **14 entries carry a wrong variant DID** | C |
| In `catalog/data/skills.tsv` | the 43 roster kits (258 rows), byte-identical to the data; **66 rows of 11 champions missing** | C |
| Client-side master champion list / enable / release / visibility flag | **none found**: the roster, ownership, free rotation and "disabled / unreleased / hidden" all come from the server (0x20ED, 0x209D, 0x20B8) | C (no record lists the roster; G that none exists anywhere) |
| Hard-coded champion names or DIDs in the exe | none (string search for champion names: no hits; the exe is data-driven) | C |

### The 11 champions missing from champions.json

Arcane Harley Quinn, Arcane Zatanna, Deadshot, Deathstroke, Dex-Starr, Huntress, John Stewart, Nightmare Catwoman,
Nightwing, Raven, Zod. All have complete data: light, wallpaper, variant, shared and skills packs, a full 6-slot kit,
an own Stolen Power version, default loadouts, stats records.

**Why they are missing (C):** `champions.json` came from the earlier project's `old_files/tools/champions.py`, which
listed the `0x48` light records. The roster is exactly the set of light records with **10 or 12 properties** (44
records; the 44th, `0x480012BE`, is a Harley Quinn costume and was folded into Harley). Those are the original 43
champions' base records, which carry the champion-select voice `0x10000575` and the portrait audio
`0x10000C87`/`0x10000C88`. The later champions' base light records have only 8 properties (they keep `0x10000575`
but have no `0x10000C87`/`0x10000C88`); Deathstroke's and John Stewart's have 7 (no `0x10000575` either). So they
were dropped by the extraction rule, **not by any flag in the data**. The variant twin (`0x49...`) of these
champions is as complete as any other.

**Why some variant DIDs are wrong (C):** `old_files/tools/heavy_packs.py` took the `0x40` DIDs of the pack that holds a
light record's heavy data; when that pack also holds the champion's **stats record** (`0x100008E2`, a `0x40`/`0x49`
pair holding only base/per-level stats) or another costume, the wrong one was picked. The correct variant is the
`0x40` whose `0x49` twin has template `0x48000732` and names the light record in `0x100005E7`. Wrong entries:

| Champion | Entry | champions.json variant | Correct variant |
|---|---|---|---|
| Arcane Green Lantern | costume Jade Warrior | 0x40000ABD | 0x400007FB |
| Arcane Supergirl | base Herald of Rao | 0x40000AB2 (stats record) | 0x40000AB3 |
| Arcane Supergirl | costume Radiant Avatar | 0x40000AB2 | 0x40000BBF |
| Atomic Joker | base Head Honcho | 0x40000961 (stats record) | 0x40000962 |
| Atomic Joker | costume Gaggy 9000 | 0x40000D4E | 0x40000D2F |
| Atomic Joker | costume Ringleader | 0x40000BAE | 0x40000AB0 |
| Nightmare Robin | base Scourge of the Night | 0x4000091A (stats record) | 0x4000091B |
| Robin | base Young Detective | 0x400005B4 (stats record) | 0x4000052D |
| Robin | costume Garuda Monk | 0x400005B4 | 0x4000094D |
| Star Sapphire | base Love's True Champion | 0x400005CF (stats record) | 0x400005D1 |
| Star Sapphire | costume Classic | 0x400005CF | 0x4000092E |
| Star Sapphire | costume Goddess of Love | 0x400005CF | 0x40000C4A |
| Starro | costume Cookie Conqueror | 0x40000D22 | 0x40000CCB |
| Swamp Thing | costume Defender of the Deep | 0x40000B1B | 0x40000B1D |

Effect (G, not tested): the account screens show these entries (0x20ED / 0x20B8 only need *a* DID plus the metadata
packs), but a match started with such a DID spawns a class with no champion definition, and `ics.gamedata.Data.kit()`
finds no kit for the real variant DID (it maps variants from `champions.tsv`). Every other field of these entries
(packs, light/pregame records, skill set) is right.

## 2. Where a champion's data lives

| Record / pack | What | Found from | |
|---|---|---|---|
| `0x40xxxxxx` variant (pack cat 7, "own pack") | The character variant (base or costume): entity class header only (`did | 2 | 1 | ...`) | `0x1000035C` of the twin | C |
| `0x49xxxxxx` twin, same low 24 bits | **The full champion definition** (`did | 4 | count | entries`, ~190 entries): template `0x1000048B` = `0x48000732`, name `0x10000433`, skin name `0x1000077F` (`Character_Skin_Name`), alignment `0x1000077A`, universe `0x1000077B`, ratings `0x1000077C`-`0x10000780` (power / health / difficulty / attack bars), the six skill slot collections `0x100008E3`...`0x100008EF` (identical to the skill set's, checked for all 156), own Stolen Power `0x10000CE5`, loadouts `0x10000CE9` / `0x10000CEB`, world state `0x510` (+ `0x50F` = 7), every pack and record below | — | C |
| `0x48` light record (pack cat 6) | Pregame/selection data: name, description, icons `0x10000384` / `0x10000799`, roles `0x100005F0`, skin name, voice `0x10000575`, portrait audio `0x10000C87`/`C88`, turntable movie `0x10000C58` (7 records only) | `0x100005E7` | C |
| `0x48` pregame / wallpaper record = light − 1 (pack cat 5) | One property: wallpaper image `0x100005B0` | `0x100005E6` | C |
| `0x48` skill set (pack cat 4 "skills UI" pack, also copied in the shared pack) | Kit: 6 slots, bio `0x10000778`, playstyle `0x10000779`, ratings, `0x10000593` champion index, `0x10000CE5`, `0x10000CE9`, `0x10000CEB` | `0x100005E9` | C |
| cat 4 skills pack | skill set + skill icons + the champion's string table (`0x2B`) + loadout records | `0x10000B0D` | C |
| cat 8 shared pack ("parent") | assets shared by all variants (animation graphs `0x1A`, FX, scripts `0x34`, models of some variants) + stats record + loadouts | `0x10000730` | C |
| cat 6 light pack | light record, two icons, champion-select sound bank (`0x52`) | `0x100005E0` | C |
| cat 5 wallpaper pack | pregame record + wallpaper image | `0x100005DF` | C |
| Stats record `0x100008E2` (`0x40`/`0x49` pair, in the shared or own pack) | Base stats and per-level growth (array `0x100008E0`: stat `0x100008DD`, base `0x100008DE`, per level `0x100008DF`) | `0x100008E2` | C (meaning of the fields G) |
| `0x1000076A` | A `0x40` DID next to the stats record (`stats + 2` or `+ 1`), not present in any pack | — | unknown |
| Loadout records (`0x10000CE9` entries: `0x10000CEB` record + `0x10000CE4` map id 3, 4, 5, 6) | Default amplifier/artifact set per map: default Stolen Power pair `0x1000064E`, artifacts `0x10000478`/`0x1000084C`-`F`, `0x10000A12`, `0x1000098F`, `0x10000893`, `0x1000034B`; name string says "<map>: Default Amplifier ..." (Gotham Divided = 4, Gotham Heights = 3 and 6, Coast City = 5) | `0x10000CE9`, default `0x10000CEB` | C (map-id meaning G) |

Light-record property names come from the UI scripts (`old_files/tools/ui_properties.json`):
`0x10000384` Character_SmallIcon, `0x10000799` Character_MiniWallpaperImage, `0x100005B0`
Character_WallpaperImage, `0x100001FC` Character_Billboard_Icon (= `0x1000072E`, champions.json `grid_icon`),
`0x10000338` Character_ConsoleVitals_Portrait, `0x10000575` Character_CharSelectVO, `0x10000C58`
Character_Turntable_Movie, `0x10000C87`/`C88` Character_Portrait_Audio(_Stop), `0x1000077A` Alignment,
`0x1000077B` Multiverse, `0x1000077F` Skin_Name, `0x10000778` About, `0x10000779` Powerset_PlayStyle (C).

Base variant: the variant whose light record has `0x10000575` (one per champion; Zatanna has two, the base is
Showstopper `0x4000015B`, New 52 `0x40000275` also has it). Deathstroke and John Stewart have none: the lowest DID is
taken (G).

How to find every champion again: scan the packs for `u32 did(0x49..) | u32 4 | u32 count` records whose entries hold
`0x1000048B = 0x48000732`, whose `0x40` twin is in the same pack (156 hits, all in cat 7 packs, ~7 s). The light
records are the `0x48` records whose first entry is `0x1000048B 0x1000048B 0x48000732` (156 hits, `old_files/tools/champions.py`).
No other record type uses template `0x48000732` (C). Units with kit slots that are **not** champions (NPC
guardians in the map variant packs, e.g. `0x4900012D`, `0x49000430`, `0x49000937`) have other templates.

## 3. Champions

"Variants" counts base + costumes. "champions.json" = how many of its variants the roster file has (and how many
of those carry a wrong DID). "Default pair" = the Stolen Powers of the default loadout (`0x10000CEB` record's
`0x1000064E`; the pair is not always the champion's own power, C). Index `0x10000593` = a per-champion number
(1 Doomsday ... 104 Dex-Starr), probably the original database's champion id (G).

| # | Champion | Index `0x10000593` | Skill set | Base variant | Base light record | Alignment / universe | Variants | Own Stolen Power (`0x10000CE5`) | Default pair (`0x10000CEB` -> `0x1000064E`) | champions.json | Kit | Scripts decoded |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| 1 | Aquaman | 44 | 0x48000911 | 0x400005C6 | 0x48000915 | Hero / Prime | 3 | 0x48000913 Super Strength | 0x48000523 Surveillance Camera + 0x48000913 Super Strength | 3/3 | 6/6 | all |
| 2 | Arcane Green Lantern | 28 | 0x4800076A | 0x4000043B | 0x4800076F | Hero / Arcane | 4 | 0x48000869 Healing Wave | 0x48000523 Surveillance Camera + 0x48000869 Healing Wave | 4/4, 1 wrong variant DID | 6/6 | all |
| 3 | Arcane Harley Quinn | 72 | 0x480012F2 | 0x40000D51 | 0x480012F0 | Villain / Arcane | 1 | 0x4800131B Psychic Assault | 0x480003CB Super Strength + 0x4800131B Psychic Assault | absent | 6/6 | missing 0x3400077A 0x34000777 |
| 4 | Arcane Supergirl | 49 | 0x48000EA8 | 0x40000AB3 | 0x48000EA6 | Hero / Arcane | 2 | 0x48000F05 Meteor Drop | 0x48000523 Surveillance Camera + 0x48000F05 Meteor Drop | 2/2, 2 wrong variant DID | 6/6 | all |
| 5 | Arcane Zatanna | 27 | 0x48001000 | 0x40000BF5 | 0x48000FFE | Hero / Arcane | 3 | 0x48001060 Psychic Assault | 0x48000523 Surveillance Camera + 0x48001060 Psychic Assault | absent | 6/6 | missing 0x340007A2 |
| 6 | Atomic Green Lantern | 35 | 0x480007A2 | 0x4000047D | 0x480007A0 | Hero / Atomic | 3 | 0x48000815 Consume | 0x480003CB Super Strength + 0x48000815 Consume | 3/3 | 6/6 | all |
| 7 | Atomic Joker | 48 | 0x48000D37 | 0x40000962 | 0x48000D35 | Villain / Atomic | 3 | 0x48000E21 Detonate | 0x48000780 Invulnerability + 0x48000529 Super Speed | 3/3, 3 wrong variant DID | 6/6 | all |
| 8 | Atomic Poison Ivy | 26 | 0x48000883 | 0x40000553 | 0x48000888 | Villain / Atomic | 3 | 0x4800088F X-Ray Vision | 0x480003CB Super Strength + 0x48000523 Surveillance Camera | 3/3 | 6/6 | all |
| 9 | Atomic Wonder Woman | 25 | 0x480006D4 | 0x400003EC | 0x480006D5 | Hero / Atomic | 3 | 0x48000868 Super Speed | 0x48000780 Invulnerability + 0x48000868 Super Speed | 3/3 | 6/6 | all |
| 10 | Atrocitus | 33 | 0x48000D01 | 0x40000932 | 0x48000CFF | Hero / Prime | 3 | 0x48000D28 Meteor Drop | 0x480003CB Super Strength + 0x48000D28 Meteor Drop | 3/3 | 6/6 | all |
| 11 | Batman | 11 | 0x480005C9 | 0x40000280 | 0x480005CB | Hero / Prime | 4 | 0x48000804 Trap | 0x48000523 Surveillance Camera + 0x48000780 Invulnerability | 4/4 | 6/6 | all |
| 12 | Blue Beetle | 45 | 0x48000A8B | 0x400007FA | 0x48000A89 | Hero / Prime | 3 | 0x48000A8C X-Ray Vision | 0x48000780 Invulnerability + 0x48000529 Super Speed | 3/3 | 6/6 | all |
| 13 | Catwoman | 10 | 0x4800072A | 0x4000041C | 0x4800072B | Vigilante / Prime | 3 | 0x4800080A Teleport | 0x48000523 Surveillance Camera + 0x4800080A Teleport | 3/3 | 6/6 | all |
| 14 | Cyborg | 22 | 0x480006A4 | 0x400003B2 | 0x480006A5 | Hero / Prime | 2 | 0x48000867 Teleport | 0x48000780 Invulnerability + 0x48000529 Super Speed | 2/2 | 6/6 | all |
| 15 | Deadshot | 78 | 0x480010C6 | 0x40000C68 | 0x480010C4 | Villain / Prime | 2 | 0x48001114 Surveillance Camera | 0x48000780 Invulnerability + 0x48000529 Super Speed | absent | 6/6 | all |
| 16 | Deathstroke | 58 | 0x48001032 | 0x40000C19 *(guess: no light record has `0x10000575`)* | 0x48001030 | Villain / Prime | 3 | 0x4800109F Detonate | 0x480003CB Super Strength + 0x48000523 Surveillance Camera | absent | 6/6 | all |
| 17 | Dex-Starr | 104 | 0x480010EF | 0x40000C75 | 0x480010F1 | Villain / Prime | 1 | 0x48001253 Teleport | 0x480007AC Trap + 0x48001253 Teleport | absent | 6/6 | all |
| 18 | Doomsday | 1 | 0x4800061B | 0x4000015A | 0x4800061D | Villain / Prime | 3 | 0x48000813 Invulnerability | 0x480003CB Super Strength + 0x48000813 Invulnerability | 3/3 | 6/6 | all |
| 19 | Flash | 16 | 0x48000670 | 0x40000396 | 0x4800066F | Hero / Prime | 3 | 0x48000807 Super Speed | 0x48000785 Psychic Assault + 0x48000807 Super Speed | 3/3 | 6/6 | all |
| 20 | Gaslight Batman | 5 | 0x48000615 | 0x40000086 | 0x48000617 | Hero / Gaslight | 4 | 0x48000808 Surveillance Camera | 0x48000780 Invulnerability + 0x48000529 Super Speed | 4/4 | 6/6 | all |
| 21 | Gaslight Catwoman | 9 | 0x48000627 | 0x40000262 | 0x48000629 | Vigilante / Gaslight | 3 | 0x48000854 X-Ray Vision | 0x48000529 Super Speed + 0x48000785 Psychic Assault | 3/3 | 6/6 | all |
| 22 | Gaslight Joker | 19 | 0x48000652 | 0x4000038D | 0x48000655 | Villain / Gaslight | 4 | 0x48000863 Meteor Drop | 0x48000529 Super Speed + 0x48000523 Surveillance Camera | 4/4 | 6/6 | all |
| 23 | Green Arrow | 24 | 0x48000A27 | 0x400006F9 | 0x48000A26 | Hero / Prime | 4 | 0x48000AA3 Surveillance Camera | 0x48000780 Invulnerability + 0x48000529 Super Speed | 4/4 | 6/6 | all |
| 24 | Green Lantern | 15 | 0x4800062E | 0x4000034D | 0x48000630 | Hero / Prime | 3 | 0x4800085F Meteor Drop | 0x48000523 Surveillance Camera + 0x4800085F Meteor Drop | 3/3 | 6/6 | all |
| 25 | Harley Quinn | 8 | 0x48000871 | 0x4000054A | 0x48000873 | Villain / Prime | 4 | 0x48000872 Detonate | 0x480007A8 Healing Wave + 0x48000523 Surveillance Camera | 4/4 | 6/6 | all |
| 26 | Hawkgirl | 61 | 0x48000EEA | 0x40000AE2 | 0x48000EE8 | Hero / Prime | 3 | 0x48000F57 Super Speed | 0x480003CB Super Strength + 0x48000F57 Super Speed | 3/3 | 6/6 | all |
| 27 | Huntress | 68 | 0x48001197 | 0x40000CD3 | 0x48001195 | Hero / Earth 2 | 1 | 0x48001298 Trap | 0x48000780 Invulnerability + 0x48000529 Super Speed | absent | 6/6 | all |
| 28 | John Stewart | 60 | 0x480013E4 | 0x40000E57 *(guess: no light record has `0x10000575`)* | 0x480013E6 | Hero / Prime | 1 | 0x480005A2 Meteor Drop | 0x480003CB Super Strength + 0x480005A2 Meteor Drop | absent | 6/6 | all |
| 29 | Katana | 69 | 0x48000F6B | 0x40000BA6 | 0x48000F69 | Hero / Prime | 3 | 0x48000FB1 Invulnerability | 0x48000529 Super Speed + 0x480003CB Super Strength | 3/3 | 6/6 | all |
| 30 | Krypto | 46 | 0x48000FCF | 0x40000BE4 | 0x48000FCD | Hero / Prime | 4 | 0x48001003 Healing Wave | 0x48000523 Surveillance Camera + 0x48001003 Healing Wave | 4/4 | 6/6 | all |
| 31 | Lex Luthor | 23 | 0x48000F5F | 0x40000B70 | 0x48000F5E | Villain / Prime | 2 | 0x48000FD8 Trap | 0x480007A8 Healing Wave + 0x48000523 Surveillance Camera | 2/2 | 6/6 | all |
| 32 | Mecha Superman | 40 | 0x480009F7 | 0x4000063D | 0x480009F5 | Hero / Mecha | 3 | 0x48000A3F Consume | 0x480003CB Super Strength + 0x48000A3F Consume | 3/3 | 6/6 | all |
| 33 | Mecha Wonder Woman | 39 | 0x480007C1 | 0x40000483 | 0x480007BF | Hero / Mecha | 3 | 0x4800086C Trap | 0x48000780 Invulnerability + 0x48000529 Super Speed | 3/3 | 6/6 | all |
| 34 | Nightmare Batman | 6 | 0x4800060B | 0x40000009 | 0x4800060D | Villain / Nightmare | 4 | 0x48000841 Consume | 0x48000785 Psychic Assault + 0x48000841 Consume | 4/4 | 6/6 | all |
| 35 | Nightmare Catwoman | 70 | 0x4800124F | 0x40000CEA | 0x4800124D | Hero / Prime | 1 | 0x480012B6 Super Strength | 0x480005A2 Meteor Drop + 0x480012B6 Super Strength | absent | 6/6 | all |
| 36 | Nightmare Robin | 47 | 0x48000CE0 | 0x4000091B | 0x48000CDE | Hero / Nightmare | 2 | 0x48000D42 X-Ray Vision | 0x48000529 Super Speed + 0x48000780 Invulnerability | 2/2, 1 wrong variant DID | 6/6 | all |
| 37 | Nightmare Superman | 30 | 0x48000A3A | 0x400007C0 | 0x48000A38 | Villain / Nightmare | 3 | 0x48000A8F Teleport | 0x480007A8 Healing Wave + 0x48000523 Surveillance Camera | 3/3 | 6/6 | all |
| 38 | Nightwing | 43 | 0x4800132F | 0x40000DEE | 0x4800132D | Hero / Prime | 1 | 0x48001466 Trap | 0x480003CB Super Strength + 0x48001466 Trap | absent | 6/6 | all |
| 39 | Poison Ivy | 2 | 0x48000618 | 0x40000145 | 0x4800061A | Villain / Prime | 4 | 0x48000846 Healing Wave | 0x48000523 Surveillance Camera + 0x48000846 Healing Wave | 4/4 | 6/6 | all |
| 40 | Raven | 31 | 0x480010B4 | 0x40000C4F | 0x480010B2 | Hero / Prime | 2 | 0x48001160 Psychic Assault | 0x480007A8 Healing Wave + 0x48000523 Surveillance Camera | absent | 6/6 | all |
| 41 | Robin | 20 | 0x48000817 | 0x4000052D | 0x48000823 | Hero / Prime | 3 | 0x48000876 Surveillance Camera | 0x480007A8 Healing Wave + 0x48000876 Surveillance Camera | 3/3, 2 wrong variant DID | 6/6 | all |
| 42 | Shazam | 17 | 0x48000641 | 0x40000358 | 0x48000643 | Hero / Prime | 3 | 0x4800080E Invulnerability | 0x48000809 Teleport + 0x4800080E Invulnerability | 3/3 | 6/6 | all |
| 43 | Sinestro | 13 | 0x48000AAC | 0x40000805 | 0x48000AAA | Villain / Prime | 4 | 0x48000BF2 Psychic Assault | 0x48000780 Invulnerability + 0x48000523 Surveillance Camera | 4/4 | 6/6 | all |
| 44 | Solomon Grundy | 76 | 0x48001097 | 0x40000C44 | 0x48001095 | Villain / Prime | 2 | 0x480010E3 Super Strength | 0x48000523 Surveillance Camera + 0x480010E3 Super Strength | 2/2 | 6/6 | all |
| 45 | Star Sapphire | 14 | 0x4800093B | 0x400005D1 | 0x48000939 | Hero / Prime | 3 | 0x480009EE Psychic Assault | 0x48000780 Invulnerability + 0x48000523 Surveillance Camera | 3/3, 3 wrong variant DID | 6/6 | all |
| 46 | Stargirl | 57 | 0x48000F02 | 0x40000AEA | 0x48000F00 | Hero / Prime | 4 | 0x48000F3C Consume | 0x480007A8 Healing Wave + 0x48000523 Surveillance Camera | 4/4 | 6/6 | all |
| 47 | Starro | 36 | 0x48000E69 | 0x40000A96 | 0x48000E6A | Villain / Prime | 3 | 0x48000EF2 Psychic Assault | 0x48000523 Surveillance Camera + 0x48000529 Super Speed | 3/3, 1 wrong variant DID | 6/6 | all |
| 48 | Supergirl | 38 | 0x48000B72 | 0x40000810 | 0x48000B70 | Hero / Prime | 3 | 0x48000D2C Invulnerability | 0x480003CB Super Strength + 0x48000D2C Invulnerability | 3/3 | 6/6 | all |
| 49 | Superman | 3 | 0x4800060E | 0x4000002B | 0x48000610 | Hero / Prime | 6 | 0x48000A3B Super Strength | 0x48000A3B Super Strength + 0x48000523 Surveillance Camera | 6/6 | 6/6 | all |
| 50 | Swamp Thing | 29 | 0x48000F1A | 0x40000B16 | 0x48000F1C | Hero / Prime | 2 | 0x48000F9B Consume | 0x48000523 Surveillance Camera + 0x48000F9B Consume | 2/2, 1 wrong variant DID | 6/6 | all |
| 51 | The Joker | 4 | 0x48000621 | 0x40000213 | 0x48000623 | Villain / Prime | 5 | 0x4800080C Detonate | 0x480007A8 Healing Wave + 0x48000523 Surveillance Camera | 5/5 | 6/6 | all |
| 52 | Wonder Woman | 12 | 0x48000624 | 0x40000260 | 0x48000625 | Hero / Prime | 3 | 0x4800081D Super Strength | 0x48000523 Surveillance Camera + 0x4800081D Super Strength | 3/3 | 6/6 | all |
| 53 | Zatanna | 7 | 0x4800061E | 0x4000015B | 0x48000620 | Hero / Prime | 3 | 0x48000852 Psychic Assault | 0x480007A8 Healing Wave + 0x48000523 Surveillance Camera | 3/3 | 6/6 | all |
| 54 | Zod | 51 | 0x480012B0 | 0x40000D29 | 0x480012AE | Villain / Prime | 1 | 0x48001333 Meteor Drop | 0x480003CB Super Strength + 0x48000523 Surveillance Camera | absent | 6/6 | all |

## 4. Every variant (base + costumes)

Pack categories (header +4): 4 skills UI, 5 wallpaper, 6 light, 7 variant (own), 8 shared. "champions.json" = ok / wrong (the DID it has) / absent. Every pack listed exists in the install (C).

| Champion | Skin (`0x1000077F`) | Variant | Light record | Pregame (wallpaper) record | Own pack (cat 7) | Light pack (6) | Wallpaper pack (5) | Shared pack (8) | Skills pack (4) | World state `0x510` | Small icon `0x10000384` | Grid icon `0x1000072E` | Mini wallpaper `0x10000799` | Wallpaper `0x100005B0` | Stats `0x100008E2` | champions.json |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| Aquaman | Lord of Atlantis (base) | 0x400005C6 | 0x48000915 | 0x48000914 | 0xA0000192 | 0xA0000190 | 0xA000018F | 0xA0000191 | 0xA0000289 | 0x2E000CBC | 0x1300197C | 0x1300197D | 0x1300197F | 0x13001980 | 0x400005C5 | ok |
| Aquaman | Lord of the Deep | 0x40000998 | 0x48000D5A | 0x48000D59 | 0xA0000251 | 0xA0000250 | 0xA000024F | 0xA0000191 | 0xA0000289 | 0x2E000FB7 | 0x13002577 | 0x1300197D | 0x13002578 | 0x13002576 | 0x400005C5 | ok |
| Aquaman | Lifeguard | 0x40000B12 | 0x48000F10 | 0x48000F0F | 0xA00002C1 | 0xA00002C0 | 0xA00002BF | 0xA0000191 | 0xA0000289 | 0x2E0010A8 | 0x13002B8C | 0x1300197D | 0x13002B92 | 0x13002B93 | 0x400005C5 | ok |
| Arcane Green Lantern | Emerald Knight (base) | 0x4000043B | 0x4800076F | 0x4800076C | 0xA0000144 | 0xA0000142 | 0xA0000143 | 0xA0000145 | 0xA0000288 | 0x2E000B86 | 0x130014DB | 0x130014DA | 0x130014FF | 0x130014E9 | 0x400005AC | ok |
| Arcane Green Lantern | Jade Warrior | 0x400007FB | 0x48000A9B | 0x48000A9A | 0xA0000205 | 0xA0000204 | 0xA0000203 | 0xA0000145 | 0xA0000288 | 0x2E000E76 | 0x13001DF7 | 0x130014DA | 0x13001DF5 | 0x13001DF6 | 0x400005AC | wrong (0x40000ABD) |
| Arcane Green Lantern | Emerald Patriot | 0x40000BC0 | 0x48000F82 | 0x48000F81 | 0xA00002F0 | 0xA00002EF | 0xA00002EE | 0xA0000145 | 0xA0000288 | 0x2E00115D | 0x13002D05 | 0x130014DA | 0x13002D06 | 0x13002D04 | 0x400005AC | ok |
| Arcane Green Lantern | Northern Light | 0x40000C09 | 0x4800101F | 0x48001020 | 0xA000030A | 0xA0000309 | 0xA0000308 | 0xA0000145 | 0xA0000288 | 0x2E00120E | 0x13002E80 | 0x130014DA | 0x13002E7A | 0x13002E79 | 0x400005AC | ok |
| Arcane Harley Quinn | Twisted Fae (base) | 0x40000D51 | 0x480012F0 | 0x480012F1 | 0xA0000383 | 0xA0000382 | 0xA0000381 | 0xA0000384 | 0xA0000380 | 0x2E001296 | 0x1300344E | 0x13003454 | 0x1300344F | 0x13003450 | 0x40000D50 | absent |
| Arcane Supergirl | Herald of Rao (base) | 0x40000AB3 | 0x48000EA6 | 0x48000EA7 | 0xA0000282 | 0xA0000280 | 0xA000027F | 0xA0000281 | 0xA00002B8 | 0x2E000F23 | 0x13002A61 | 0x13002A64 | 0x13002A62 | 0x13002A63 | 0x40000AB2 | wrong (0x40000AB2) |
| Arcane Supergirl | Radiant Avatar | 0x40000BBF | 0x48000F80 | 0x48000F7F | 0xA00002ED | 0xA00002EC | 0xA00002EB | 0xA0000281 | 0xA00002B8 | 0x2E001173 | 0x13002CFD | 0x13002A64 | 0x13002CFE | 0x13002CFC | 0x40000AB2 | wrong (0x40000AB2) |
| Arcane Zatanna | The Silent Sorceress (base) | 0x40000BF5 | 0x48000FFE | 0x48000FFF | 0xA0000304 | 0xA0000301 | 0xA0000300 | 0xA0000303 | 0xA0000302 | 0x2E001086 | 0x13002E18 | 0x13002E1B | 0x13002E19 | 0x13002E1A | 0x40000BF4 | absent |
| Arcane Zatanna | Death Mage | 0x40000C85 | 0x48001121 | 0x48001120 | 0xA0000349 | 0xA0000348 | 0xA0000347 | 0xA0000303 | 0xA0000302 | 0x2E0012B8 | 0x13003107 | 0x13002E1B | 0x1300310D | 0x1300310E | 0x40000BF4 | absent |
| Arcane Zatanna | School of Magic | 0x40000E5E | 0x48001408 | 0x48001407 | 0xA00003A6 | 0xA00003A5 | 0xA00003A4 | 0xA0000303 | 0xA0000302 | 0x2E0013AE | 0x130035A3 | 0x13002E1B | 0x130035A4 | 0x130035A2 | 0x40000BF4 | absent |
| Atomic Green Lantern | The Light that Burns (base) | 0x4000047D | 0x480007A0 | 0x480007A1 | 0xA0000151 | 0xA000014F | 0xA000014E | 0xA0000150 | 0xA0000287 | 0x2E000BB9 | 0x13001650 | 0x13001652 | 0x13001653 | 0x13001659 | 0x400005AE | ok |
| Atomic Green Lantern | Shattered Light | 0x4000080C | 0x48000AC2 | 0x48000AC1 | 0xA000021B | 0xA000021A | 0xA0000219 | 0xA0000150 | 0xA0000287 | 0x2E000EBD | 0x13002032 | 0x13001652 | 0x13002033 | 0x13002034 | 0x400005AE | ok |
| Atomic Green Lantern | Deep Sea Fisherman | 0x40000C1B | 0x48001036 | 0x48001035 | 0xA0000312 | 0xA0000310 | 0xA0000311 | 0xA0000150 | 0xA0000287 | 0x2E001234 | 0x13002EBE | 0x13001652 | 0x13002EBF | 0x13002EBD | 0x400005AE | ok |
| Atomic Joker | Head Honcho (base) | 0x40000962 | 0x48000D35 | 0x48000D36 | 0xA000024B | 0xA0000249 | 0xA0000248 | 0xA000024A | 0xA00002A5 | 0x2E000EEF | 0x130024C2 | 0x130024C5 | 0x130024C3 | 0x130024C4 | 0x40000961 | wrong (0x40000961) |
| Atomic Joker | Ringleader | 0x40000AB0 | 0x48000EA1 | 0x48000EA0 | 0xA000027C | 0xA000027D | 0xA000027E | 0xA000024A | 0xA00002A5 | 0x2E0010BE | 0x13002A55 | 0x130024C5 | 0x13002A56 | 0x13002A57 | 0x40000961 | wrong (0x40000BAE) |
| Atomic Joker | Gaggy 9000 | 0x40000D2F | 0x480012C0 | 0x480012BF | 0xA000037C | 0xA000037B | 0xA000037A | 0xA000024A | 0xA00002A5 | 0x2E001340 | 0x130033BC | 0x130024C5 | 0x130033BD | 0x130033BB | 0x40000961 | wrong (0x40000D4E) |
| Atomic Poison Ivy | Mistress of the Toxic Forest (base) | 0x40000553 | 0x48000888 | 0x48000887 | 0xA000018E | 0xA000018C | 0xA000018B | 0xA000018D | 0xA0000285 | 0x2E000CBF | 0x130018A2 | 0x130018A1 | 0x130018A6 | 0x130018A4 | 0x400005B0 | ok |
| Atomic Poison Ivy | Nightbloom | 0x4000091D | 0x48000CE4 | 0x48000CE3 | 0xA0000235 | 0xA0000234 | 0xA0000233 | 0xA000018D | 0xA0000285 | 0x2E000EF7 | 0x130023A8 | 0x130018A1 | 0x130023A9 | 0x130023A7 | 0x400005B0 | ok |
| Atomic Poison Ivy | Fungal Queen | 0x40000CD4 | 0x4800119F | 0x4800119E | 0xA0000365 | 0xA0000364 | 0xA0000363 | 0xA000018D | 0xA0000285 | 0x2E0012F9 | 0x1300320E | 0x130018A1 | 0x1300320F | 0x1300320D | 0x400005B0 | ok |
| Atomic Wonder Woman | The Reclaimer (base) | 0x400003EC | 0x480006D5 | 0x480006D6 | 0xA0000123 | 0xA0000125 | 0xA0000126 | 0xA0000124 | 0xA0000284 | 0x2E000B0F | 0x1300130A | 0x1300130B | 0x13001392 | 0x13001308 | 0x400005AF | ok |
| Atomic Wonder Woman | Relentless Reclaimer | 0x40000802 | 0x48000AA2 | 0x48000AA1 | 0xA0000208 | 0xA0000206 | 0xA0000207 | 0xA0000124 | 0xA0000284 | 0x2E000E66 | 0x13001F2D | 0x1300130B | 0x13001F2E | 0x13001F2C | 0x400005AF | ok |
| Atomic Wonder Woman | Infinite Metal | 0x40000BED | 0x48000FED | 0x48000FEC | 0xA00002F9 | 0xA00002FA | 0xA00002FB | 0xA0000124 | 0xA0000284 | 0x2E001193 | 0x13002DF0 | 0x1300130B | 0x13002DF1 | 0x13002DEF | 0x400005AF | ok |
| Atrocitus | Survivor of Sector 666 (base) | 0x40000932 | 0x48000CFF | 0x48000D00 | 0xA000023F | 0xA000023D | 0xA000023C | 0xA000023E | 0xA0000283 | 0x2E000E54 | 0x1300243A | 0x1300243D | 0x1300243B | 0x1300243C | 0x40000931 | ok |
| Atrocitus | Diablo Rojo | 0x40000A92 | 0x48000E5F | 0x48000E5E | 0xA000026A | 0xA0000269 | 0xA0000268 | 0xA000023E | 0xA0000283 | 0x2E000FC8 | 0x13002839 | 0x1300243D | 0x1300283A | 0x13002838 | 0x40000931 | ok |
| Atrocitus | Anger Management | 0x40000E76 | 0x4800146E | 0x4800146D | 0xA00003B3 | 0xA00003B2 | 0xA00003B1 | 0xA000023E | 0xA0000283 | 0x2E0013EA | 0x13002FC2 | 0x1300243D | 0x13002FBC | 0x13002FBB | 0x40000931 | ok |
| Batman | The Dark Knight (base) | 0x40000280 | 0x480005CB | 0x480005CA | 0xA00000DD | 0xA00000DC | 0xA00000DB | 0xA000011F | 0xA000028A | 0x2E0008F0 | 0x13000E6F | 0x13000E6E | 0x1300137F | 0x13000E8B | 0x400005B3 | ok |
| Batman | Arkham City | 0x40000546 | 0x4800083F | 0x48000840 | 0xA0000180 | 0xA000017F | 0xA000017E | 0xA000011F | 0xA000028A | 0x2E000C8B | 0x130017C8 | 0x13000E6E | 0x130017CA | 0x130017C9 | 0x400005B3 | ok |
| Batman | High Seas | 0x4000063A | 0x480009ED | 0x480009EC | 0xA00001E5 | 0xA00001E4 | 0xA00001E3 | 0xA000011F | 0xA000028A | 0x2E000DBD | 0x13001C2D | 0x13000E6E | 0x13001C2E | 0x13001C2C | 0x400005B3 | ok |
| Batman | Desert Armor | 0x40000CC0 | 0x48001177 | 0x48001176 | 0xA0000357 | 0xA0000356 | 0xA0000355 | 0xA000011F | 0xA000028A | 0x2E0012E0 | 0x130031A2 | 0x13000E6E | 0x130031A3 | 0x130031A1 | 0x400005B3 | ok |
| Blue Beetle | Reach Infiltrator (base) | 0x400007FA | 0x48000A89 | 0x48000A8A | 0xA0000201 | 0xA00001FF | 0xA0000200 | 0xA0000202 | 0xA00002A1 | 0x2E000E42 | 0x13001DC2 | 0x13001DC4 | 0x13001DC1 | 0x13001DC0 | 0x400007F9 | ok |
| Blue Beetle | Jaime Reyes | 0x40000999 | 0x48000D5C | 0x48000D5B | 0xA0000254 | 0xA0000253 | 0xA0000252 | 0xA0000202 | 0xA00002A1 | 0x2E000FAA | 0x13002582 | 0x13001DC4 | 0x13002583 | 0x13002581 | 0x400007F9 | ok |
| Blue Beetle | Día de Muertos | 0x40000CA8 | 0x48001156 | 0x48001157 | 0xA000034C | 0xA000034B | 0xA000034A | 0xA0000202 | 0xA00002A1 | 0x2E0012DB | 0x13003159 | 0x13001DC4 | 0x1300315A | 0x1300315B | 0x400007F9 | ok |
| Catwoman | Feline Fatale (base) | 0x4000041C | 0x4800072B | 0x4800072C | 0xA000012D | 0xA000012B | 0xA000012A | 0xA000012C | 0xA0000299 | 0x2E000995 | 0x1300146B | 0x1300146E | 0x1300146C | 0x1300146D | 0x400005B2 | ok |
| Catwoman | Classic | 0x4000080A | 0x48000AC0 | 0x48000ABF | 0xA0000218 | 0xA0000217 | 0xA0000216 | 0xA000012C | 0xA0000299 | 0x2E000E84 | 0x13002018 | 0x1300146E | 0x13002019 | 0x13002017 | 0x400005B2 | ok |
| Catwoman | Beach Party | 0x40000B15 | 0x48000F16 | 0x48000F15 | 0xA00002CA | 0xA00002C9 | 0xA00002C8 | 0xA000012C | 0xA0000299 | 0x2E00110A | 0x13002BAB | 0x1300146E | 0x13002BA9 | 0x13002BAA | 0x400005B2 | ok |
| Cyborg | Human Arsenal (base) | 0x400003B2 | 0x480006A5 | 0x480006A6 | 0xA000010A | 0xA0000109 | 0xA0000108 | 0xA0000112 | 0xA0000298 | 0x2E000A04 | 0x1300124D | 0x1300124F | 0x1300137A | 0x1300124C | 0x400005B1 | ok |
| Cyborg | A.R.G.U.S. Agent | 0x4000081F | 0x48000C00 | 0x48000BFF | 0xA000022B | 0xA000022A | 0xA0000229 | 0xA0000112 | 0xA0000298 | 0x2E000EA9 | 0x13002265 | 0x1300124F | 0x13002266 | 0x13002264 | 0x400005B1 | ok |
| Deadshot | Contract Killer (base) | 0x40000C68 | 0x480010C4 | 0x480010C5 | 0xA0000338 | 0xA0000335 | 0xA0000334 | 0xA0000337 | 0xA0000336 | 0x2E001169 | 0x13003006 | 0x13003009 | 0x13003007 | 0x13003008 | 0x40000C67 | absent |
| Deadshot | Deadeye | 0x40000EBF | 0x480014D2 | 0x480014D1 | 0xA00003C6 | 0xA00003C5 | 0xA00003C4 | 0xA0000337 | 0xA0000336 | 0x2E00140F | 0x130037F3 | 0x13003009 | 0x130037F4 | 0x130037F2 | 0x40000C67 | absent |
| Deathstroke | The Terminator | 0x40000C19 | 0x48001030 | 0x48001031 | 0xA000030F | 0xA000030C | 0xA000030B | 0xA000030E | 0xA000030D | 0x2E0010E3 | 0x13002EA8 | 0x13002EAB | 0x13002EA9 | 0x13002EAA | 0x40000C17 | absent |
| Deathstroke | High Seas | 0x40000D56 | 0x480012FC | 0x480012FD | 0xA0000387 | 0xA0000386 | 0xA0000385 | 0xA000030E | 0xA000030D | 0x2E001365 | 0x13003474 | 0x13002EAB | 0x1300346E | 0x1300346D | 0x40000C17 | absent |
| Deathstroke | New 52 | 0x40000EBE | 0x480014D0 | 0x480014CF | 0xA00003C3 | 0xA00003C2 | 0xA00003C1 | 0xA000030E | 0xA000030D | 0x2E001410 | 0x130037E6 | 0x13002EAB | 0x130037E7 | 0x130037E5 | 0x40000C17 | absent |
| Dex-Starr | Good Kitty (base) | 0x40000C75 | 0x480010F1 | 0x480010F2 | 0xA0000340 | 0xA000033D | 0xA000033C | 0xA000033F | 0xA000033E | 0x2E001186 | 0x130030A7 | 0x130030AA | 0x130030A8 | 0x130030A9 | 0x40000C74 | absent |
| Doomsday | Ruthless Abomination (base) | 0x4000015A | 0x4800061D | 0x4800061C | 0xA00000A2 | 0xA00000C4 | 0xA00000C3 | 0xA000011C | 0xA000028F | 0x2E000157 | 0x1300081B | 0x13000822 | 0x13001367 | 0x13000C01 | 0x400005B6 | ok |
| Doomsday | Flashpoint | 0x4000039B | 0x48000682 | 0x48000683 | 0xA0000100 | 0xA00000FF | 0xA00000FE | 0xA000011C | 0xA000028F | 0x2E0009F5 | 0x130011AF | 0x13000822 | 0x13001379 | 0x130011B0 | 0x400005B6 | ok |
| Doomsday | First Date | 0x4000091C | 0x48000CE1 | 0x48000CE2 | 0xA0000232 | 0xA0000231 | 0xA0000230 | 0xA000011C | 0xA000028F | 0x2E000F26 | 0x1300239B | 0x13000822 | 0x13002395 | 0x13002394 | 0x400005B6 | ok |
| Flash | The Fastest Man Alive (base) | 0x40000396 | 0x4800066F | 0x4800066E | 0xA00000F7 | 0xA00000F5 | 0xA00000F6 | 0xA0000121 | 0xA0000297 | 0x2E00096E | 0x1300112E | 0x1300112D | 0x13001378 | 0x1300112F | 0x400005C2 | ok |
| Flash | Hypersonic | 0x4000063E | 0x480009F9 | 0x480009F8 | 0xA00001EC | 0xA00001EB | 0xA00001EA | 0xA0000121 | 0xA0000297 | 0x2E000D02 | 0x13001C3D | 0x1300112D | 0x13001C3E | 0x13001C3C | 0x400005C2 | ok |
| Flash | Olympian | 0x40000CB1 | 0x48001165 | 0x48001164 | 0xA000034F | 0xA000034E | 0xA000034D | 0xA0000121 | 0xA0000297 | 0x2E0012BC | 0x13003184 | 0x1300112D | 0x13003185 | 0x13003183 | 0x400005C2 | ok |
| Gaslight Batman | The Sound of Justice (base) | 0x40000086 | 0x48000617 | 0x48000616 | 0xA0000076 | 0xA00000B8 | 0xA00000B7 | 0xA0000122 | 0xA000028D | 0x2E0001B2 | 0x130002E5 | 0x13000378 | 0x13001380 | 0x13000C02 | 0x400005C3 | ok |
| Gaslight Batman | Samurai | 0x400003C7 | 0x480006AE | 0x480006AD | 0xA000010C | 0xA0000110 | 0xA000010F | 0xA0000122 | 0xA000028D | 0x2E000A86 | 0x13001260 | 0x13000378 | 0x13001381 | 0x1300125F | 0x400005C3 | ok |
| Gaslight Batman | Renaissance | 0x40000549 | 0x48000857 | 0x48000858 | 0xA0000183 | 0xA0000181 | 0xA0000182 | 0xA0000122 | 0xA000028D | 0x2E000C94 | 0x130017E7 | 0x13000378 | 0x130017E5 | 0x130017E6 | 0x400005C3 | ok |
| Gaslight Batman | Android | 0x40000BD3 | 0x48000FB5 | 0x48000FB4 | 0xA00002F3 | 0xA00002F1 | 0xA00002F2 | 0xA0000122 | 0xA000028D | 0x2E0011C1 | 0x13002D5F | 0x13000378 | 0x13002D59 | 0x13002D58 | 0x400005C3 | ok |
| Gaslight Catwoman | Claws of Vengeance (base) | 0x40000262 | 0x48000629 | 0x48000628 | 0xA00000CC | 0xA00000CE | 0xA00000CD | 0xA000010B | 0xA0000293 | 0x2E0007C0 | 0x13000CC2 | 0x13000CC4 | 0x1300137B | 0x13000CC5 | 0x400005B5 | ok |
| Gaslight Catwoman | Ame-Comi | 0x40000397 | 0x48000673 | 0x48000674 | 0xA00000FA | 0xA00000F8 | 0xA00000F9 | 0xA000010B | 0xA0000293 | 0x2E000A0F | 0x13001138 | 0x13000CC4 | 0x1300137C | 0x13001137 | 0x400005B5 | ok |
| Gaslight Catwoman | High Seas | 0x40000AAD | 0x48000E8A | 0x48000E89 | 0xA0000275 | 0xA0000273 | 0xA0000274 | 0xA000010B | 0xA0000293 | 0x2E001096 | 0x130029F3 | 0x13000CC4 | 0x13002B07 | 0x130029F2 | 0x400005B5 | ok |
| Gaslight Joker | The Laughing Butcher (base) | 0x4000038D | 0x48000655 | 0x48000656 | 0xA00000EB | 0xA00000E9 | 0xA00000EA | 0xA0000114 | 0xA0000296 | 0x2E00095E | 0x1300102D | 0x1300102C | 0x13001376 | 0x13001034 | 0x400005B8 | ok |
| Gaslight Joker | Sinister Santa | 0x40000610 | 0x48000999 | 0x48000998 | 0xA00001DC | 0xA00001DA | 0xA00001DB | 0xA0000114 | 0xA0000296 | 0x2E000D56 | 0x13001A33 | 0x1300102C | 0x13001A35 | 0x13001A34 | 0x400005B8 | ok |
| Gaslight Joker | Sushi Chef | 0x400007F3 | 0x48000A70 | 0x48000A6F | 0xA00001FE | 0xA00001FC | 0xA00001FD | 0xA0000114 | 0xA0000296 | 0x2E000E19 | 0x13001D7A | 0x1300102C | 0x13001D7B | 0x13001D79 | 0x400005B8 | ok |
| Gaslight Joker | Plague Baron | 0x40000C1D | 0x4800103D | 0x4800103C | 0xA0000313 | 0xA0000314 | 0xA0000315 | 0xA0000114 | 0xA0000296 | 0x2E001217 | 0x13002ECA | 0x1300102C | 0x13002ECB | 0x13002EC9 | 0x400005B8 | ok |
| Green Arrow | Emerald Archer (base) | 0x400006F9 | 0x48000A26 | 0x48000A2B | 0xA00001F2 | 0xA00001F1 | 0xA00001F0 | 0xA00001F3 | 0xA000029F | 0x2E000DFC | 0x13001CBA | 0x13001CD3 | 0x13001CBB | 0x13001CC2 | 0x400006FB | ok |
| Green Arrow | Achilles' End | 0x40000A7A | 0x48000E32 | 0x48000E31 | 0xA0000262 | 0xA0000261 | 0xA0000260 | 0xA00001F3 | 0xA000029F | 0x2E000F7D | 0x13002711 | 0x13001CD3 | 0x13002712 | 0x13002710 | 0x400006FB | ok |
| Green Arrow | Shipwrecked | 0x40000C81 | 0x48001117 | 0x48001118 | 0xA0000343 | 0xA0000342 | 0xA0000341 | 0xA00001F3 | 0xA000029F | 0x2E0012A8 | 0x130030F8 | 0x13001CD3 | 0x130030F6 | 0x130030F7 | 0x400006FB | ok |
| Green Arrow | Starling City | 0x40000CB6 | 0x48001170 | 0x4800116F | 0xA0000354 | 0xA0000353 | 0xA0000352 | 0xA00001F3 | 0xA000029F | 0x2E0012C3 | 0x1300318F | 0x13001CD3 | 0x13003190 | 0x1300318E | 0x400006FB | ok |
| Green Lantern | Fearless Maverick (base) | 0x4000034D | 0x48000630 | 0x4800062F | 0xA00000E0 | 0xA00000E1 | 0xA00000E2 | 0xA0000115 | 0xA0000294 | 0x2E000156 | 0x13000F3A | 0x13000F3C | 0x13001377 | 0x13000F3B | 0x400005BB | ok |
| Green Lantern | Callsign: Highball | 0x400006EB | 0x48000A0E | 0x48000A0D | 0xA00001EF | 0xA00001ED | 0xA00001EE | 0xA0000115 | 0xA0000294 | 0x2E000DBC | 0x13001C5D | 0x13000F3C | 0x13001C5B | 0x13001C5C | 0x400005BB | ok |
| Green Lantern | SoCal Hal | 0x40000C07 | 0x48001015 | 0x48001014 | 0xA0000307 | 0xA0000306 | 0xA0000305 | 0xA0000115 | 0xA0000294 | 0x2E0011F5 | 0x13002E56 | 0x13000F3C | 0x13002E57 | 0x13002E55 | 0x400005BB | ok |
| Harley Quinn | Mad Love (base) | 0x4000054A | 0x48000873 | 0x48000870 | 0xA0000187 | 0xA0000185 | 0xA0000184 | 0xA0000186 | 0xA000029C | 0x2E000BE5 | 0x13001837 | 0x13001836 | 0x1300183F | 0x13001838 | 0x400005BF | ok |
| Harley Quinn | Slumber Party | 0x40000807 | 0x48000ABB | 0x48000ABA | 0xA0000215 | 0xA0000213 | 0xA0000214 | 0xA0000186 | 0xA000029C | 0x2E000E3C | 0x13002009 | 0x13001836 | 0x1300200A | 0x13002008 | 0x400005BF | ok |
| Harley Quinn | Candy Cane | 0x4000080D | 0x48000AC4 | 0x48000AC5 | 0xA000021E | 0xA000021D | 0xA000021C | 0xA0000186 | 0xA000029C | 0x2E0013E2 | 0x1300204F | 0x13001836 | 0x1300204E | 0x1300204D | 0x400005BF | ok |
| Harley Quinn | Bombshell | 0x40000D2E | 0x480012BE | 0x480012BD | 0xA000037F | 0xA000037E | 0xA000037D | 0xA0000186 | 0xA000029C | 0x2E001345 | 0x130033B7 | 0x13001836 | 0x130033B8 | 0x130033B9 | 0x400005BF | ok |
| Hawkgirl | Winged Defender (base) | 0x40000AE2 | 0x48000EE8 | 0x48000EE9 | 0xA00002B5 | 0xA00002B6 | 0xA00002B3 | 0xA00002B4 | 0xA00002B7 | 0x2E000F09 | 0x13002AFF | 0x13002B3F | 0x13002B00 | 0x13002B01 | 0x40000AE1 | ok |
| Hawkgirl | Armored Vigil | 0x40000B6E | 0x48000F5D | 0x48000F5C | 0xA00002DA | 0xA00002D9 | 0xA00002D8 | 0xA00002B4 | 0xA00002B7 | 0x2E0010A0 | 0x13002C74 | 0x13002B3F | 0x13002C75 | 0x13002C73 | 0x40000AE1 | ok |
| Hawkgirl | Jazzercise | 0x40000E70 | 0x48001465 | 0x48001464 | 0xA00003C0 | 0xA00003BF | 0xA00003BE | 0xA00002B4 | 0xA00002B7 | 0x2E001400 | 0x13003678 | 0x13002B3F | 0x13003679 | 0x1300367A | 0x40000AE1 | ok |
| Huntress | The Legacy of Gotham (base) | 0x40000CD3 | 0x48001195 | 0x48001196 | 0xA0000362 | 0xA000035F | 0xA000035E | 0xA0000361 | 0xA0000360 | 0x2E0011B9 | 0x130031E8 | 0x130031EB | 0x130031E9 | 0x130031EA | 0x40000CD2 | absent |
| John Stewart | Frontline Architect | 0x40000E57 | 0x480013E6 | 0x480013E5 | 0xA000039E | 0xA000039D | 0xA000039C | 0xA000039F | 0xA000039B | 0x2E00124B | 0x1300356B | 0x1300356D | 0x1300356C | 0x1300356A | 0x40000E59 | absent |
| Katana | Mistress of the Soultaker (base) | 0x40000BA6 | 0x48000F69 | 0x48000F6A | 0xA00002E4 | 0xA00002E1 | 0xA00002E0 | 0xA00002E3 | 0xA00002E2 | 0x2E0010E2 | 0x13002C98 | 0x13002C9B | 0x13002C99 | 0x13002C9A | 0x40000BA5 | ok |
| Katana | Vengeful Kabuki | 0x40000C26 | 0x48001076 | 0x48001075 | 0xA000031F | 0xA000031E | 0xA000031D | 0xA00002E3 | 0xA00002E2 | 0x2E001245 | 0x13002F16 | 0x13002C9B | 0x13002F17 | 0x13002F15 | 0x40000BA5 | ok |
| Katana | Oni's Wrath | 0x40000D5A | 0x48001300 | 0x480012FF | 0xA000038A | 0xA0000389 | 0xA0000388 | 0xA00002E3 | 0xA00002E2 | 0x2E001376 | 0x13003494 | 0x13002C9B | 0x13003495 | 0x13003493 | 0x40000BA5 | ok |
| Krypto | Super Dog (base) | 0x40000BE4 | 0x48000FCD | 0x48000FCE | 0xA00002F8 | 0xA00002F5 | 0xA00002F4 | 0xA00002F7 | 0xA00002F6 | 0x2E001049 | 0x13002D95 | 0x13002D98 | 0x13002D96 | 0x13002D97 | 0x40000BE3 | ok |
| Krypto | New 52 | 0x40000CC1 | 0x4800117A | 0x48001179 | 0xA000035A | 0xA0000359 | 0xA0000358 | 0xA00002F7 | 0xA00002F6 | 0x2E0012E2 | 0x130031AB | 0x13002D98 | 0x130031AC | 0x130031AA | 0x40000BE3 | ok |
| Krypto | Top Dog | 0x40000E77 | 0x48001470 | 0x4800146F | 0xA00003B6 | 0xA00003B5 | 0xA00003B4 | 0xA00002F7 | 0xA00002F6 | 0x2E0013E9 | 0x1300369E | 0x13002D98 | 0x1300369F | 0x1300369D | 0x40000BE3 | ok |
| Krypto | Big Bad Wolf-Cat | 0x40000ED4 | 0x4800152F | 0x48001530 | 0xA00003D0 | 0xA00003CF | 0xA00003CE | 0xA00002F7 | 0xA00002F6 | 0x2E001425 | 0x130038DA | 0x13002D98 | 0x130038D4 | 0x130038D3 | 0x40000BE3 | ok |
| Lex Luthor | The Greatest Mind of Our Time (base) | 0x40000B70 | 0x48000F5E | 0x48000F64 | 0xA00002DF | 0xA00002DC | 0xA00002DB | 0xA00002DE | 0xA00002DD | 0x2E000FE7 | 0x13002C8F | 0x13002C90 | 0x13002C88 | 0x13002C87 | 0x40000B71 | ok |
| Lex Luthor | Trench Diver | 0x40000C84 | 0x4800111E | 0x4800111F | 0xA0000344 | 0xA0000345 | 0xA0000346 | 0xA00002DE | 0xA00002DD | 0x2E0012AB | 0x13003105 | 0x13002C90 | 0x13003103 | 0x13003104 | 0x40000B71 | ok |
| Mecha Superman | The Agent of Hope (base) | 0x4000063D | 0x480009F5 | 0x480009F6 | 0xA00001E9 | 0xA00001E7 | 0xA00001E6 | 0xA00001E8 | 0xA000029E | 0x2E000D21 | 0x13001C37 | 0x13001C3A | 0x13001C38 | 0x13001C39 | 0x4000063C | ok |
| Mecha Superman | Siege Breaker | 0x40000A72 | 0x48000E27 | 0x48000E26 | 0xA000025C | 0xA000025B | 0xA000025A | 0xA00001E8 | 0xA000029E | 0x2E000F9F | 0x130026DF | 0x13001C3A | 0x130026E0 | 0x130026DE | 0x4000063C | ok |
| Mecha Superman | Five Alarm | 0x40000E60 | 0x4800141C | 0x4800141B | 0xA00003AC | 0xA00003AB | 0xA00003AA | 0xA00001E8 | 0xA000029E | 0x2E0013A6 | 0x130035BD | 0x13001C3A | 0x130035BE | 0x130035BC | 0x4000063C | ok |
| Mecha Wonder Woman | The Warden of Truth (base) | 0x40000483 | 0x480007BF | 0x480007C0 | 0xA0000156 | 0xA0000158 | 0xA0000155 | 0xA0000157 | 0xA000029A | 0x2E000B89 | 0x130016B2 | 0x1300169A | 0x130016B1 | 0x130016B0 | 0x400005C4 | ok |
| Mecha Wonder Woman | Sky Racer | 0x40000818 | 0x48000B82 | 0x48000B81 | 0xA0000225 | 0xA0000223 | 0xA0000224 | 0xA0000157 | 0xA000029A | 0x2E000EF6 | 0x130021D2 | 0x1300169A | 0x130021D0 | 0x130021D1 | 0x400005C4 | ok |
| Mecha Wonder Woman | D1A-NA Prototype | 0x40000CDB | 0x4800123B | 0x4800123A | 0xA0000368 | 0xA0000367 | 0xA0000366 | 0xA0000157 | 0xA000029A | 0x2E0012C4 | 0x1300323A | 0x1300169A | 0x1300323B | 0x13003239 | 0x400005C4 | ok |
| Nightmare Batman | Vampire (base) | 0x40000009 | 0x4800060D | 0x4800060C | 0xA0000073 | 0xA00000BA | 0xA00000B9 | 0xA0000116 | 0xA000028B | 0x2E00004A | 0x130000B2 | 0x130000B1 | 0x1300137D | 0x13000BFB | 0x400005C1 | ok |
| Nightmare Batman | Krampus | 0x4000043C | 0x4800076B | 0x4800076D | 0xA0000148 | 0xA0000147 | 0xA0000146 | 0xA0000116 | 0xA000028B | 0x2E000BBA | 0x130014E8 | 0x130000B1 | 0x13001508 | 0x130014EA | 0x400005C1 | ok |
| Nightmare Batman | Revenant | 0x40000639 | 0x480009EA | 0x480009E9 | 0xA00001E2 | 0xA00001E0 | 0xA00001E1 | 0xA0000116 | 0xA000028B | 0x2E000DBE | 0x13001C17 | 0x130000B1 | 0x13001C15 | 0x13001C16 | 0x400005C1 | ok |
| Nightmare Batman | Crimson Lord | 0x40000D1C | 0x48001292 | 0x48001291 | 0xA0000374 | 0xA0000373 | 0xA0000372 | 0xA0000116 | 0xA000028B | 0x2E00132B | 0x13003329 | 0x130000B1 | 0x1300332A | 0x13003328 | 0x400005C1 | ok |
| Nightmare Catwoman | Warrior of Bast (base) | 0x40000CEA | 0x4800124D | 0x4800124E | 0xA000036C | 0xA000036A | 0xA000036B | 0xA000036D | 0xA0000369 | 0x2E00122B | 0x13003265 | 0x13003267 | 0x1300325F | 0x1300325E | 0x40000CE9 | absent |
| Nightmare Robin | Scourge of the Night (base) | 0x4000091B | 0x48000CDE | 0x48000CDF | 0xA000022F | 0xA000022D | 0xA000022C | 0xA000022E | 0xA00002A4 | 0x2E000EF3 | 0x1300238A | 0x1300238D | 0x1300238B | 0x1300238C | 0x4000091A | wrong (0x4000091A) |
| Nightmare Robin | Crimson Dusk | 0x40000AE6 | 0x48000EFB | 0x48000EFA | 0xA00002AD | 0xA00002AC | 0xA00002AB | 0xA000022E | 0xA00002A4 | 0x2E0010A1 | 0x13002B1B | 0x1300238D | 0x13002B1C | 0x13002B1A | 0x4000091A | ok |
| Nightmare Superman | The Phantom King (base) | 0x400007C0 | 0x48000A38 | 0x48000A39 | 0xA00001F9 | 0xA00001F8 | 0xA00001F7 | 0xA00001FA | 0xA00002A0 | 0x2E000E23 | 0x13001D1E | 0x13001D2D | 0x13001D1F | 0x13001D20 | 0x400007BF | ok |
| Nightmare Superman | Harbinger of Madness | 0x40000BBE | 0x48000F7E | 0x48000F7D | 0xA00002EA | 0xA00002E9 | 0xA00002E8 | 0xA00001FA | 0xA00002A0 | 0x2E001174 | 0x13002CF5 | 0x13001D2D | 0x13002CF6 | 0x13002CF4 | 0x400007BF | ok |
| Nightmare Superman | Cyber Armor | 0x40000D5D | 0x48001306 | 0x48001305 | 0xA000038D | 0xA000038C | 0xA000038B | 0xA00001FA | 0xA00002A0 | 0x2E001382 | 0x130034AB | 0x13001D2D | 0x130034AC | 0x130034AA | 0x400007BF | ok |
| Nightwing | Daring Vigilante (base) | 0x40000DEE | 0x4800132D | 0x4800132E | 0xA0000399 | 0xA0000398 | 0xA0000397 | 0xA000039A | 0xA0000396 | 0x2E001286 | 0x130034E7 | 0x130034E9 | 0x130034E1 | 0x130034E0 | 0x40000DED | absent |
| Poison Ivy | Deadly Rose (base) | 0x40000145 | 0x4800061A | 0x48000619 | 0xA000009B | 0xA00000C2 | 0xA00000C1 | 0xA0000111 | 0xA000028E | 0x2E00028B | 0x1300077C | 0x1300077D | 0x13001372 | 0x13000BFF | 0x400005B7 | ok |
| Poison Ivy | Classic | 0x4000027A | 0x4800062D | 0x4800062C | 0xA00000D9 | 0xA00000D8 | 0xA00000DA | 0xA0000111 | 0xA000028E | 0x2E0008DF | 0x13000E60 | 0x1300077D | 0x13001373 | 0x13000E5F | 0x400005B7 | ok |
| Poison Ivy | Dressed to Kill | 0x40000AAB | 0x48000E81 | 0x48000E80 | 0xA0000272 | 0xA0000270 | 0xA0000271 | 0xA0000111 | 0xA000028E | 0x2E00109F | 0x130029DB | 0x1300077D | 0x130029DC | 0x130029DA | 0x400005B7 | ok |
| Poison Ivy | Autumn Queen | 0x40000AAE | 0x48000E97 | 0x48000E96 | 0xA0000278 | 0xA0000276 | 0xA0000277 | 0xA0000111 | 0xA000028E | 0x2E00107C | 0x13002A3F | 0x1300077D | 0x13002A3D | 0x13002A3E | 0x400005B7 | ok |
| Raven | Dark Omen (base) | 0x40000C4F | 0x480010B2 | 0x480010B3 | 0xA0000333 | 0xA0000330 | 0xA000032F | 0xA0000332 | 0xA0000331 | 0x2E001166 | 0x13002FB7 | 0x13002FCA | 0x13002FB8 | 0x13002FB9 | 0x40000C4E | absent |
| Raven | Introvert | 0x40000E5D | 0x48001406 | 0x48001405 | 0xA00003A9 | 0xA00003A8 | 0xA00003A7 | 0xA0000332 | 0xA0000331 | 0x2E0013B1 | 0x130035A0 | 0x13002FCA | 0x130035A1 | 0x1300359F | 0x40000C4E | absent |
| Robin | Young Detective (base) | 0x4000052D | 0x48000823 | 0x48000824 | 0xA0000175 | 0xA0000173 | 0xA0000174 | 0xA0000176 | 0xA000029B | 0x2E000A83 | 0x13001731 | 0x13001730 | 0x1300174B | 0x1300174C | 0x400005B4 | wrong (0x400005B4) |
| Robin | Garuda Monk | 0x4000094D | 0x48000D23 | 0x48000D22 | 0xA0000244 | 0xA0000243 | 0xA0000242 | 0xA0000176 | 0xA000029B | 0x2E000EF4 | 0x13002463 | 0x13001730 | 0x13002464 | 0x13002462 | 0x400005B4 | wrong (0x400005B4) |
| Robin | Track & Field | 0x40000B13 | 0x48000F12 | 0x48000F11 | 0xA00002C4 | 0xA00002C3 | 0xA00002C2 | 0xA0000176 | 0xA000029B | 0x2E0010A9 | 0x13002B94 | 0x13001730 | 0x13002B9A | 0x13002B9B | 0x400005B4 | ok |
| Shazam | Earth's Mightiest Mortal (base) | 0x40000358 | 0x48000643 | 0x48000642 | 0xA00000E5 | 0xA00000E4 | 0xA00000E3 | 0xA0000120 | 0xA0000295 | 0x2E000927 | 0x13000FDF | 0x13000FDE | 0x13001371 | 0x13000FE1 | 0x400005BC | ok |
| Shazam | Olympian | 0x4000060D | 0x48000963 | 0x48000962 | 0xA00001D8 | 0xA00001D7 | 0xA00001D6 | 0xA0000120 | 0xA0000295 | 0x2E000D00 | 0x13001A0F | 0x13000FDE | 0x13001A0D | 0x13001A0E | 0x400005BC | ok |
| Shazam | Infinite Fanboy | 0x40000C27 | 0x48001078 | 0x48001077 | 0xA0000322 | 0xA0000321 | 0xA0000320 | 0xA0000120 | 0xA0000295 | 0x2E001248 | 0x13002F24 | 0x13000FDE | 0x13002F22 | 0x13002F23 | 0x400005BC | ok |
| Sinestro | The Fallen Lantern (base) | 0x40000805 | 0x48000AAA | 0x48000AAB | 0xA000020F | 0xA000020D | 0xA000020C | 0xA000020E | 0xA00002A2 | 0x2E000E46 | 0x13001F6F | 0x13001F72 | 0x13001F70 | 0x13001F71 | 0x40000804 | ok |
| Sinestro | Fearsome Tyrant | 0x40000BEE | 0x48000FEF | 0x48000FEE | 0xA00002FE | 0xA00002FD | 0xA00002FC | 0xA000020E | 0xA00002A2 | 0x2E001195 | 0x13002DF8 | 0x13001F72 | 0x13002DF9 | 0x13002DF7 | 0x40000804 | ok |
| Sinestro | Matador | 0x40000E75 | 0x4800146C | 0x4800146B | 0xA00003B0 | 0xA00003AF | 0xA00003AE | 0xA000020E | 0xA00002A2 | 0x2E0013EB | 0x13003696 | 0x13001F72 | 0x13003697 | 0x13003695 | 0x40000804 | ok |
| Sinestro | Parallax | 0x40000ED5 | 0x48001532 | 0x48001531 | 0xA00003D3 | 0xA00003D2 | 0xA00003D1 | 0xA000020E | 0xA00002A2 | 0x2E001426 | 0x130038E4 | 0x13001F72 | 0x130038E5 | 0x130038E3 | 0x40000804 | ok |
| Solomon Grundy | Deathless Brute (base) | 0x40000C44 | 0x48001095 | 0x48001096 | 0xA0000327 | 0xA0000326 | 0xA0000325 | 0xA0000328 | 0xA0000324 | 0x2E0010DE | 0x13002F6A | 0x13002F79 | 0x13002F6B | 0x13002F6C | 0x40000C43 | ok |
| Solomon Grundy | Monday Mangler | 0x40000C4B | 0x480010A7 | 0x480010A6 | 0xA000032E | 0xA000032D | 0xA000032C | 0xA0000328 | 0xA0000324 | 0x2E001238 | 0x13002FAD | 0x13002F79 | 0x13002FAE | 0x13002FAC | 0x40000C43 | ok |
| Star Sapphire | Love's True Champion (base) | 0x400005D1 | 0x48000939 | 0x4800093A | 0xA00001D1 | 0xA00001CF | 0xA00001D0 | 0xA00001D2 | 0xA000029D | 0x2E000CB4 | 0x130019E5 | 0x130019EE | 0x130019E6 | 0x130019E7 | 0x400005CF | wrong (0x400005CF) |
| Star Sapphire | Classic | 0x4000092E | 0x48000CFA | 0x48000CF9 | 0xA000023B | 0xA000023A | 0xA0000239 | 0xA00001D2 | 0xA000029D | 0x2E000F0E | 0x1300242D | 0x130019EE | 0x1300242E | 0x1300242C | 0x400005CF | wrong (0x400005CF) |
| Star Sapphire | Goddess of Love | 0x40000C4A | 0x480010A5 | 0x480010A4 | 0xA000032B | 0xA000032A | 0xA0000329 | 0xA00001D2 | 0xA000029D | 0x2E00125B | 0x13002FA1 | 0x130019EE | 0x13002FA7 | 0x13002FA8 | 0x400005CF | wrong (0x400005CF) |
| Stargirl | Cosmic Superstar (base) | 0x40000AEA | 0x48000F00 | 0x48000F01 | 0xA00002B2 | 0xA00002AF | 0xA00002AE | 0xA00002B1 | 0xA00002B0 | 0x2E000F3A | 0x13002B29 | 0x13002B2C | 0x13002B2A | 0x13002B2B | 0x40000AE9 | ok |
| Stargirl | Galactic Voyager | 0x40000B11 | 0x48000F0E | 0x48000F0D | 0xA00002BE | 0xA00002BD | 0xA00002BC | 0xA00002B1 | 0xA00002B0 | 0x2E0010AA | 0x13002B84 | 0x13002B2C | 0x13002B8A | 0x13002B8B | 0x40000AE9 | ok |
| Stargirl | Bombshell | 0x40000CED | 0x48001255 | 0x48001254 | 0xA0000371 | 0xA0000370 | 0xA000036F | 0xA00002B1 | 0xA00002B0 | 0x2E001320 | 0x130032A1 | 0x13002B2C | 0x130032A2 | 0x130032A0 | 0x40000AE9 | ok |
| Stargirl | Pop Star | 0x40000E88 | 0x4800147E | 0x4800147D | 0xA00003BA | 0xA00003B9 | 0xA00003B8 | 0xA00002B1 | 0xA00002B0 | 0x2E0013FB | 0x13003724 | 0x13002B2C | 0x13003725 | 0x13003723 | 0x40000AE9 | ok |
| Starro | The Conqueror (base) | 0x40000A96 | 0x48000E6A | 0x48000E68 | 0xA000026D | 0xA000026C | 0xA000026B | 0xA000026E | 0xA00002A6 | 0x2E000F0A | 0x130028EA | 0x130028EC | 0x130028EB | 0x130028E9 | 0x40000A99 | ok |
| Starro | Molten Overlord | 0x40000B14 | 0x48000F14 | 0x48000F13 | 0xA00002C7 | 0xA00002C6 | 0xA00002C5 | 0xA000026E | 0xA00002A6 | 0x2E001154 | 0x13002B9D | 0x130028EC | 0x13002B9E | 0x13002B9C | 0x40000A99 | ok |
| Starro | Cookie Conqueror | 0x40000CCB | 0x48001185 | 0x48001184 | 0xA000035D | 0xA000035C | 0xA000035B | 0xA000026E | 0xA00002A6 | 0x2E0012E7 | 0x130031BB | 0x130028EC | 0x130031BC | 0x130031BA | 0x40000A99 | wrong (0x40000D22) |
| Supergirl | Last Daughter of Krypton (base) | 0x40000810 | 0x48000B70 | 0x48000B71 | 0xA0000222 | 0xA0000220 | 0xA000021F | 0xA0000221 | 0xA00002A3 | 0x2E000E78 | 0x130021AB | 0x130021AE | 0x130021AC | 0x130021AD | 0x4000080F | ok |
| Supergirl | Varsity | 0x40000B20 | 0x48000F2C | 0x48000F2B | 0xA00002D5 | 0xA00002D4 | 0xA00002D3 | 0xA0000221 | 0xA00002A3 | 0x2E0010CB | 0x13002BFC | 0x130021AE | 0x13002BFA | 0x13002BFB | 0x4000080F | ok |
| Supergirl | Wolf Slayer | 0x40000E87 | 0x4800147C | 0x4800147B | 0xA00003BD | 0xA00003BB | 0xA00003BC | 0xA0000221 | 0xA00002A3 | 0x2E0013FF | 0x13003721 | 0x130021AE | 0x13003722 | 0x13003720 | 0x4000080F | ok |
| Superman | Man of Steel (base) | 0x4000002B | 0x48000610 | 0x4800060F | 0xA0000075 | 0xA00000BC | 0xA00000BB | 0xA000011D | 0xA000028C | 0x2E0000DD | 0x13000120 | 0x1300011F | 0x1300136F | 0x13000BFD | 0x400005B9 | ok |
| Superman | Classic | 0x40000806 | 0x48000AB4 | 0x48000AB3 | 0xA0000212 | 0xA0000211 | 0xA0000210 | 0xA000011D | 0xA000028C | 0x2E000E79 | 0x13001FF7 | 0x1300011F | 0x13001FF8 | 0x13001FF6 | 0x400005B9 | ok |
| Superman | Clark Kent | 0x4000092D | 0x48000CF6 | 0x48000CF5 | 0xA0000238 | 0xA0000237 | 0xA0000236 | 0xA000011D | 0xA000028C | 0x2E000F1F | 0x130023FD | 0x1300011F | 0x130023FE | 0x130023FC | 0x400005B9 | ok |
| Superman | Gold | 0x40000AAF | 0x48000E9E | 0x48000E9F | 0xA000027B | 0xA000027A | 0xA0000279 | 0xA000011D | 0xA000028C | 0x2E0010B4 | 0x13002A4B | 0x1300011F | 0x13002A4C | 0x13002A4A | 0x400005B9 | ok |
| Superman | Red Son | 0x40000B10 | 0x48000F0C | 0x48000F0B | 0xA00002BB | 0xA00002BA | 0xA00002B9 | 0xA000011D | 0xA000028C | 0x2E0010F2 | 0x13002B78 | 0x1300011F | 0x13002B79 | 0x13002B7A | 0x400005B9 | ok |
| Superman | Regeneration Matrix | 0x40000C6A | 0x480010C9 | 0x480010C8 | 0xA000033B | 0xA000033A | 0xA0000339 | 0xA000011D | 0xA000028C | 0x2E001295 | 0x1300301C | 0x1300011F | 0x1300301D | 0x1300301B | 0x400005B9 | ok |
| Swamp Thing | Avatar of the Green (base) | 0x40000B16 | 0x48000F1C | 0x48000F1B | 0xA00002CE | 0xA00002CD | 0xA00002CC | 0xA00002CF | 0xA00002CB | 0x2E00104C | 0x13002BCD | 0x13002BB7 | 0x13002BCE | 0x13002BCC | 0x40000B1B | ok |
| Swamp Thing | Defender of the Deep | 0x40000B1D | 0x48000F26 | 0x48000F25 | 0xA00002D2 | 0xA00002D1 | 0xA00002D0 | 0xA00002CF | 0xA00002CB | 0x2E0010E1 | 0x13002BDC | 0x13002BB7 | 0x13002BDD | 0x13002BDB | 0x40000B1B | wrong (0x40000B1B) |
| The Joker | Clown Prince of Crime (base) | 0x40000213 | 0x48000623 | 0x48000622 | 0xA00000B4 | 0xA00000C8 | 0xA00000C7 | 0xA000011B | 0xA0000291 | 0x2E000155 | 0x13000B06 | 0x13000B07 | 0x13001374 | 0x13000C00 | 0x400005C0 | ok |
| The Joker | Gangster | 0x40000395 | 0x48000668 | 0x48000669 | 0xA00000F3 | 0xA00000F2 | 0xA00000F1 | 0xA000011B | 0xA0000291 | 0x2E00099B | 0x13001127 | 0x13000B07 | 0x13001375 | 0x13001129 | 0x400005C0 | ok |
| The Joker | Arkham Origins | 0x40000636 | 0x480009DF | 0x480009DE | 0xA00001DF | 0xA00001DE | 0xA00001DD | 0xA000011B | 0xA0000291 | 0x2E000D9B | 0x13001BCA | 0x13000B07 | 0x13001BC8 | 0x13001BC9 | 0x400005C0 | ok |
| The Joker | Original Gangster | 0x40000701 | 0x48000A33 | 0x48000A32 | 0xA00001F6 | 0xA00001F5 | 0xA00001F4 | 0xA000011B | 0xA0000291 | 0x2E000E05 | 0x13001D11 | 0x13000B07 | 0x13001D0F | 0x13001D10 | 0x400005C0 | ok |
| The Joker | Summer Laughs | 0x40000A76 | 0x48000E2F | 0x48000E2E | 0xA000025F | 0xA000025E | 0xA000025D | 0xA000011B | 0xA0000291 | 0x2E000F80 | 0x130026FE | 0x13000B07 | 0x130026FF | 0x130026FD | 0x400005C0 | ok |
| Wonder Woman | Ambassador of Peace (base) | 0x40000260 | 0x48000625 | 0x48000626 | 0xA00000C9 | 0xA00000CB | 0xA00000CA | 0xA000011E | 0xA0000292 | 0x2E000652 | 0x13000C70 | 0x13000C73 | 0x1300136E | 0x13000C6F | 0x400005BD | ok |
| Wonder Woman | Greek Goddess of War | 0x4000047F | 0x480007A6 | 0x480007A7 | 0xA0000154 | 0xA0000153 | 0xA0000152 | 0xA000011E | 0xA0000292 | 0x2E000BEC | 0x1300167F | 0x13000C73 | 0x13001674 | 0x13001680 | 0x400005BD | ok |
| Wonder Woman | Sgt. Diana | 0x4000095F | 0x48000D2F | 0x48000D30 | 0xA0000247 | 0xA0000245 | 0xA0000246 | 0xA000011E | 0xA0000292 | 0x2E000F3B | 0x130024BA | 0x13000C73 | 0x130024BB | 0x130024BC | 0x400005BD | ok |
| Zatanna | Showstopper (base) | 0x4000015B | 0x48000620 | 0x4800061F | 0xA00000A3 | 0xA00000C6 | 0xA00000C5 | 0xA0000113 | 0xA0000290 | 0x2E0004BF | 0x130008B3 | 0x130008B4 | 0x1300136C | 0x13000BF7 | 0x400005BE | ok |
| Zatanna | New 52 (base) | 0x40000275 | 0x4800062A | 0x4800062B | 0xA00000D7 | 0xA00000D5 | 0xA00000D6 | 0xA0000113 | 0xA0000290 | 0x2E0008DC | 0x13000E16 | 0x130008B4 | 0x1300136D | 0x13000E17 | 0x400005BE | ok |
| Zatanna | Ame-Comi | 0x40000AE4 | 0x48000EEE | 0x48000EED | 0xA00002AA | 0xA00002A9 | 0xA00002A8 | 0xA0000113 | 0xA0000290 | 0x2E0010BC | 0x13002B0B | 0x130008B4 | 0x13002B0C | 0x13002B0A | 0x400005BE | ok |
| Zod | Kryptonian Tyrant (base) | 0x40000D29 | 0x480012AE | 0x480012AF | 0xA0000379 | 0xA0000376 | 0xA0000375 | 0xA0000378 | 0xA0000377 | 0x2E00122F | 0x13003357 | 0x13003359 | 0x13003351 | 0x13003350 | 0x40000D28 | absent |

## 5. Kits

A slot's skill is not a DID: it is a property collection inside the skill set record (slot property `0x100008E3` Basic, `E8` Q, `EA` W, `EC` E, `E6` R, `EF` Passive), named here `skill set:slot` as in `skills.tsv`. Stats: 3 = cost (Will, negative), 5 = damage, 15 = cooldown, 18 = range (probable); `base(+per rank)`. Targeting `0x1000003D`. The twin of every variant embeds the same six collections (name, script and stats equal for all 156, C).

**Comparison with `catalog/data/skills.tsv` (C):** all 258 rows of the 43 roster champions match the data exactly (name, icon, targeting, script, stats). Missing: the 66 rows of the 11 champions below. No other difference.

### All 54 kits (skill name and script)

| Champion | Skill set | Basic | Q | W | E | R | Passive |
|---|---|---|---|---|---|---|---|
| Aquaman | 0x48000911 | Basic Attack `0x34000374` | Trident of the King `0x34000394` | Stagger `0x34000396` | Undertow `0x3400037A` | Might of Atlantis `0x34000397` | Rising Tide `0x34000395` |
| Arcane Green Lantern | 0x4800076A | Basic Attack `0x34000295` | Construct Champion `0x34000293` | Shackles `0x34000294` | Emerald Lantern `0x34000290` | Deny the Black `0x34000291` | Emerald Light `0x34000292` |
| Arcane Harley Quinn | 0x480012F2 | Basic Attack `0x3400077A` | Pirouette `0x34000776` | Flit `0x34000775` | Glamour `0x34000778` | Delirium `0x3400077B` | Spiteful Sprite `0x34000777` |
| Arcane Supergirl | 0x48000EA8 | Basic Attack `0x3400054A` | Breath of Rao `0x3400054E` | Firewall `0x3400054C` | Pyrolyze `0x3400054B` | Rao's Wrath `0x3400054D` | Daughter of Rao `0x34000550` |
| Arcane Zatanna | 0x48001000 | Basic Attack `0x34000615` | Spectral Slash `0x3400061A` | Runic Gate `0x340007A1` | Mystic Feedback `0x34000618` | Silent Sorceress `0x34000617` | Mage Hunter `0x340007A2` |
| Atomic Green Lantern | 0x480007A2 | Basic Attack `0x340002B6` | Grab `0x340002B5` | Scorched Earth `0x340002B2` | Shards of Will `0x340002B1` | Meltdown `0x340002B4` | Radiation Sickness `0x340002B3` |
| Atomic Joker | 0x48000D37 | Basic Attack `0x340004DF` | Hot Potato `0x340004DD` | Plutonium Peel `0x340004DC` | Acid Balloon `0x340004DB` | Jack in the Box `0x340004DA` | The Punch Line `0x340004DE` |
| Atomic Poison Ivy | 0x48000883 | Basic Attack `0x34000352` | Poisoned Earth `0x34000354` | Bramble Rapture `0x34000353` | Wall of Thorns `0x34000356` | Secrets of the Forest `0x34000355` | Toxic Growth `0x34000357` |
| Atomic Wonder Woman | 0x480006D4 | Basic Attack `0x34000257` | Vault `0x34000256` | Smite `0x34000255` | Savage Sweep `0x34000254` | Reclaimer `0x34000253` | Rev `0x34000265` |
| Atrocitus | 0x48000D01 | Basic Attack `0x340004CC` | Crimson Slash `0x340004CD` | Come At Me `0x340004CE` | Overwhelming Rage `0x340004CF` | Plasma Wave `0x340004D0` | Red Lantern's Rage `0x340004D1` |
| Batman | 0x480005C9 | Basic Attack `0x34000178` | Batarang `0x34000244` | Martial Arts `0x34000243` | Cape Sweep `0x34000242` | The Dark Knight `0x34000248` | Watching, Waiting `0x340002AE` |
| Blue Beetle | 0x48000A8B | Basic Attack `0x34000457` | Energy Cannon `0x34000451` | Scarab Scanner `0x34000454` | Stick And Move `0x34000455` | Infiltrator Mode `0x3400044F` | Reach Directive: Disrupt `0x34000456` |
| Catwoman | 0x4800072A | Basic Attack `0x34000279` | Whip Strike `0x34000276` | Cat's Paw `0x34000277` | Acrobat `0x3400027B` | Bad Kitty `0x3400027A` | Cat Burglar `0x34000278` |
| Cyborg | 0x480006A4 | Basic Attack `0x34000238` | Tracer Shot `0x34000236` | Charged Burst `0x34000235` | Cascade `0x34000234` | Plasma Cannon `0x34000233` | Cybernetic Targeting `0x34000237` |
| Deadshot | 0x480010C6 | Basic Attack `0x34000697` | Called Shot `0x34000696` | Sniper's Eye `0x34000692` | Cover To Cover `0x34000695` | One Shot, One Kill `0x34000694` | Shadowy Employers `0x34000693` |
| Deathstroke | 0x48001032 | Basic Attack `0x34000637` | Blade Rush `0x340007DB` | Healing Factor `0x340007DF` | Explosive Rounds `0x340007DE` | Bullet Rain `0x340007DD` | Battle Fury `0x340007DC` |
| Dex-Starr | 0x480010EF | Basic Attack `0x340006BA` | Lacerate `0x340006B9` | Pounce `0x340006B7` | Caustic Flood `0x340006B6` | Shred The World `0x340006B5` | Vengeful Rage `0x340006B8` |
| Doomsday | 0x4800061B | Basic Attack `0x340000A9` | Pummeling Assault `0x340000DF` | Berserk `0x3400015D` | Charge `0x340000E0` | Kryptonian Rage `0x340000E1` | Revenge `0x340000E6` |
| Flash | 0x48000670 | Basic Attack `0x3400021A` | Flash Attack `0x3400021B` | F=MA `0x34000219` | Hyper Vibration `0x34000218` | Speed Storm `0x34000217` | Speed Force `0x34000216` |
| Gaslight Batman | 0x48000615 | Basic Attack `0x34000037` | Sonic Batarang `0x3400003B` | Sonic Shell `0x3400003A` | Bat Flight `0x34000038` | Bat Scream `0x34000039` | Echoes `0x34000048` |
| Gaslight Catwoman | 0x48000627 | Basic Attack `0x3400018E` | Steampowered Claws `0x340001B7` | Shred `0x3400034C` | Blood Hunt `0x340001C6` | Predator's Grace `0x340001CE` | Sharpened Claws `-` |
| Gaslight Joker | 0x48000652 | Basic Attack `0x34000200` | Fetid Cleaver `0x34000205` | Ham Toss `0x3400020A` | Snack Time! `0x34000202` | Rat Swarm `0x34000201` | Blood Money `0x34000203` |
| Green Arrow | 0x48000A27 | Basic Attack `0x34000411` | Superfoam Arrows `0x3400040E` | Ballistic Arrows `0x3400040D` | Thermite Arrows `0x34000410` | Bullseye `0x3400040C` | Adaptable Ammo `0x34000412` |
| Green Lantern | 0x4800062E | Basic Attack `0x340001E7` | Slam `0x340001E6` | Constrict `0x340001E4` | Missile Barrage `0x340001E3` | Green Lantern's Light `0x340001E2` | Indomitable Will `0x340001E5` |
| Harley Quinn | 0x48000871 | Basic Attack `0x34000343` | Pies! `0x34000342` | Back Off `0x34000341` | Best Medicine `0x3400033F` | Puddin' Time! `0x3400033E` | BFFs `0x34000340` |
| Hawkgirl | 0x48000EEA | Basic Attack `0x34000579` | Mace Throw `0x34000574` | Soar `0x34000575` | Haymaker `0x34000576` | Howling Eye `0x34000577` | Thrill of Battle `0x34000578` |
| Huntress | 0x48001197 | Basic Attack `0x3400070F` | Snap Shot `0x3400070C` | Hunter's Quarrel `0x3400070B` | Grapple Bolt `0x3400070A` | Rapid Deployment `0x3400070D` | Tech Bolts `0x34000709` |
| John Stewart | 0x480013E4 | Basic Attack `0x340007A6` | full_auto `0x340007A7` | claymore_mine `0x340007A8` | forward_base `0x340007A9` | omni_turret `0x340007AA` | architects_will `0x340007AB` |
| Katana | 0x48000F6B | Basic Attack `0x340005BB` | Slash `0x340005B8` | Cross Step `0x340005B7` | Kendo `0x340005BA` | Thousand Cuts `0x340005B6` | Soultaker `0x340005B9` |
| Krypto | 0x48000FCF | Basic Attack `0x340005F5` | Fetch! `0x340005EE` | Man's Best Friend `0x340005F2` | On The Hunt `0x340005F0` | Piercing Howl `0x340005F1` | Vigilance `0x340005EF` |
| Lex Luthor | 0x48000F5F | Basic Attack `0x340005AD` | LexCorp Sentry `0x340005AB` | Tactical Disruption `0x340005A9` | Critical Mass `0x340007CB` | Orbital Remediation `0x340005A8` | Neural Networking `0x340005AC` |
| Mecha Superman | 0x480009F7 | Basic Attack `0x340003ED` | Drill Attack `0x340003F0` | Sunstone Eruption `0x340003EF` | Fissure `0x340003F1` | Terraformer `0x340003F2` | Agent of Hope `0x340003E6` |
| Mecha Wonder Woman | 0x480007C1 | Basic Attack `0x340002CC` | Glaive Storm `0x340002CB` | Afterburn `0x340002CA` | Celerity `0x340002C9` | Tempest `0x340002C8` | Implacable Judgement `0x340002C7` |
| Nightmare Batman | 0x4800060B | Basic Attack `0x340000C8` | Silver Batarang `0x340000C4` | Bat Swarm `0x340000C5` | Savagery `0x340000C9` | Feral Embrace `0x340000C6` | Eternal Hunger `0x340000C7` |
| Nightmare Catwoman | 0x4800124F | Basic Attack `0x34000725` | Rip & Tear `0x34000728` | Soul Siphon `0x3400072A` | Scar the Land `0x34000726` | Inevitability `0x34000729` | Mangle `0x34000727` |
| Nightmare Robin | 0x48000CE0 | Basic Attack `0x340004B9` | Arcing Blades `0x340004B7` | Impale `0x340004B6` | Unnatural Reflexes `0x340004B5` | Feed the Beast `0x340004B4` | The Hunger `0x340004B8` |
| Nightmare Superman | 0x48000A3A | Basic Attack `0x3400041F` | Phantom Collector `0x3400041B` | Vortex `0x3400041A` | Siphon/Infuse `0x3400041D` | Condemn `0x3400041E` | Possession `0x3400041C` |
| Nightwing | 0x4800132F | Basic Attack `0x34000799` | Eskrima `0x34000795` | Thunderbolt `0x34000793` | Rolling Thunder `0x34000797` | Let's Ride `0x34000794` | Static Burn `0x34000796` |
| Poison Ivy | 0x48000618 | Basic Attack `0x3400009D` | Root Strike `0x34000095` | Blow Kiss `0x34000099` | Thorn Shield `0x34000158` | Deadly Flora `0x34000097` | Healthy Glow `0x34000098` |
| Raven | 0x480010B4 | Basic Attack `0x34000681` | Gloom `0x3400067F` | Empathic Link `0x3400067E` | Isolation `0x3400067D` | Astral Projection `0x3400067C` | Blessing of Darkness `0x34000680` |
| Robin | 0x48000817 | Basic Attack `0x3400030E` | Vault Kick `0x3400030D` | Bo Master `0x3400030C` | Dynamic Duo `0x3400030B` | Emergent Leader `0x3400030A` | This Guy! `0x34000309` |
| Shazam | 0x48000641 | Basic Attack `0x340001F6` | Mystic Power `0x34000756` | Mystic Defense `0x34000757` | Lightning Field `0x340001F5` | SHAZAM! `0x340001F8` | Power of Zeus `0x340001FD` |
| Sinestro | 0x48000AAC | Basic Attack `0x3400046F` | Saw-blade `0x3400046C` | Dread Scythe `0x3400046A` | Cull the Weak `0x3400046E` | Fear Incarnate `0x3400046B` | Yellow Impurity `0x3400046D` |
| Solomon Grundy | 0x48001097 | Basic Attack `0x3400066C` | Clobber `0x34000666` | Crush `0x34000665` | The March `0x34000664` | Buried on Sunday `0x34000663` | Born on a Monday `0x34000662` |
| Star Sapphire | 0x4800093B | Basic Attack `0x34000390` | Crystal Bomb `0x3400038D` | Violet Harvest `0x3400038A` | Bonds of Love `0x3400038E` | Manifest `0x3400038B` | Glimpse of the Predator `0x3400038C` |
| Stargirl | 0x48000F02 | Basic Attack `0x3400056A` | Cosmic Blast `0x3400056E` | Shooting Stars `0x3400056D` | Gravity Well `0x3400056C` | Energy Conversion `0x3400056B` | Family Heirlooms `0x3400056F` |
| Starro | 0x48000E69 | Basic Attack `0x3400052B` | Star Shot `0x34000530` | Parasite `0x34000531` | Telepathic Warlord `0x3400052E` | Mind Control `0x3400052D` | The Conqueror Comes `0x34000532` |
| Supergirl | 0x48000B72 | Basic Attack `0x34000481` | Worldbreaker `0x34000483` | Bounding Strike `0x3400047F` | Determination `0x34000482` | Comet `0x34000480` | Solar Furnace `0x3400047E` |
| Superman | 0x4800060E | Basic Attack `0x3400000C` | Kryptonian Might `0x340003D7` | Frost Breath `0x340000F7` | Heat Vision `0x340003D6` | Speeding Bullet `0x340003D5` | Man of Steel `0x340000F8` |
| Swamp Thing | 0x48000F1A | Basic Attack `0x3400057F` | Vine Leash `0x34000582` | Husk `0x34000581` | Earth Strike `0x34000584` | Warrior King `0x34000580` | Bio-regenerative Formula `0x34000583` |
| The Joker | 0x48000621 | Basic Attack `0x3400011C` | Mr. Punchy `0x3400010A` | Surprise! `0x34000114` | Vanish `0x34000111` | Last Laugh `0x3400011B` | Sadist `0x34000110` |
| Wonder Woman | 0x48000624 | Basic Attack `0x3400017E` | Lasso Grab `0x34000185` | Protection `0x34000192` | Amazonian Prowess `0x3400018C` | Blocking Bracers `0x3400017D` | Child of Olympus `0x34000189` |
| Zatanna | 0x4800061E | Basic Attack `0x340000ED` | Skewer `0x340000E9` | Dash / Dazzle `0x340000EC` | Protect / Punish `0x340000EB` | Be a Rabbit `0x340000EA` | Stage Presence `0x34000107` |
| Zod | 0x480012B0 | Basic Attack `0x3400074D` | Shield Breaker `0x34000749` | Relentless `0x3400074A` | Solar Surge `0x34000748` | Kneel Before Zod `0x3400074B` | Born in Battle `0x3400074C` |

### Full kits of the 11 champions missing from skills.tsv

| Skill (set:slot) | Champion | Key | Name | Icon | Targeting `0x1000003D` | Script `0x10000328` | Stats (`id=base(+per rank)`) | Decoded |
|---|---|---|---|---|---|---|---|---|
| 0x480012F2:0 | Arcane Harley Quinn | Basic | Basic Attack | 0x13003462 | 9 | 0x3400077A | 18=1 30=18 | no |
| 0x480012F2:1 | Arcane Harley Quinn | Q | Pirouette | 0x13003468 | 7 | 0x34000776 | 5=50(+35/rank) 3=-35(-15/rank) 18=2 15=6 | yes |
| 0x480012F2:2 | Arcane Harley Quinn | W | Flit | 0x13003469 | 13 | 0x34000775 | 5=30(+25/rank) 18=3 30=16 14=4 3=-25(-15/rank) 15=10(-0.5/rank) | yes |
| 0x480012F2:3 | Arcane Harley Quinn | E | Glamour | 0x1300346A | 1 | 0x34000778 | 5=0.4(+0.1/rank) 23=7 14=0.75 19=8 12=2 3=-35(-20/rank) 15=20(-2/rank) | yes |
| 0x480012F2:4 | Arcane Harley Quinn | R | Delirium | 0x1300346C | 14 | 0x3400077B | 8=0.2(+0.1/rank) 18=4 17=3 14=5(+1/rank) 19=-0.5 15=115(-15/rank) | yes |
| 0x480012F2:5 | Arcane Harley Quinn | Passive | Spiteful Sprite | 0x1300346B | - | 0x34000777 | 4=0.2(+0.05/rank) 27=0.15(+0.05/rank) 14=3 15=10 | no |
| 0x48001000:0 | Arcane Zatanna | Basic | Basic Attack | 0x13002E23 | 9 | 0x34000615 | 18=1 30=18 | yes |
| 0x48001000:1 | Arcane Zatanna | Q | Spectral Slash | 0x13002E24 | 13 | 0x3400061A | 5=30(+20/rank) 1=45(+30/rank) 18=2.25 24=135 23=9 22=1.2 30=15 3=-40(-20/rank) 15=9(-1/rank) | yes |
| 0x48001000:2 | Arcane Zatanna | W | Runic Gate | 0x13002E28 | 1 | 0x340007A1 | 1=60(+40/rank) 23=7.5 18=1.75 27=5 14=0.2 3=-70(-20/rank) 15=15(-1/rank) | yes |
| 0x48001000:3 | Arcane Zatanna | E | Mystic Feedback | 0x13002E26 | 5 | 0x34000618 | 5=25(+25/rank) 14=1 3=-70(-5/rank) 15=20(-1/rank) 30=6 | yes |
| 0x48001000:4 | Arcane Zatanna | R | Silent Sorceress | 0x13002E27 | 7 | 0x34000617 | 5=-60(-30/rank) 1=-150(-75/rank) 40=20(+10/rank) 18=1.75 17=7 22=2 30=15 14=5 12=0.05 33=0.5 15=120 | yes |
| 0x48001000:5 | Arcane Zatanna | Passive | Mage Hunter | 0x13002E25 | - | 0x340007A2 | 18=9 14=4 15=14(-2/rank) 5=20(+20/rank) 19=1 21=6 33=0.4 30=6 44=0.5 23=2 22=6 | no |
| 0x480010C6:0 | Deadshot | Basic | Basic Attack | 0x13003044 | 9 | 0x34000697 | 18=4.5 30=18 44=0.12 | yes |
| 0x480010C6:1 | Deadshot | Q | Called Shot | 0x13003043 | 14 | 0x34000696 | 5=60(+35/rank) 18=6 22=0.6 30=11 3=-0.15 14=-0.15 12=0.05(+0.05/rank) 15=9 | yes |
| 0x480010C6:2 | Deadshot | W | Sniper's Eye | 0x13003042 | 5 | 0x34000692 | 38=3(+3/rank) 27=0.08(+0.02/rank) 14=6 18=1.5 3=-20(-5/rank) 15=1 | yes |
| 0x480010C6:3 | Deadshot | E | Cover To Cover | 0x13003041 | 5 | 0x34000695 | 4=0.2(+0.05/rank) 7=0.7 14=2.5 19=-1.5 3=-80(-5/rank) 15=22(-2/rank) | yes |
| 0x480010C6:4 | Deadshot | R | One Shot, One Kill | 0x13003040 | 13 | 0x34000694 | 5=250(+75/rank) 12=0.5 18=150 22=0.6 14=0.5 19=1.5 15=100(-20/rank) | yes |
| 0x480010C6:5 | Deadshot | Passive | Shadowy Employers | 0x1300303F | - | 0x34000693 | 5=0.2(+0.05/rank) 14=6 19=0.75 33=0.4 12=40(+20/rank) 18=10 15=45 | yes |
| 0x48001032:0 | Deathstroke | Basic | Basic Attack | 0x13002EB2 | 9 | 0x34000637 | 18=1 | yes |
| 0x48001032:1 | Deathstroke | Q | Blade Rush | 0x130038BC | 13 | 0x340007DB | 5=50(+30/rank) 1=30(+25/rank) 20=0.08 18=5 17=8 30=14 22=1 3=-25(-5/rank) 15=10 | yes |
| 0x48001032:2 | Deathstroke | W | Healing Factor | 0x130038BD | 5 | 0x340007DF | 19=8 21=5 8=0.5(+0.1/rank) 1=10(+10/rank) 5=0.25(+0.1/rank) 42=8(+4/rank) 15=16 3=-60(-10/rank) | yes |
| 0x48001032:3 | Deathstroke | E | Explosive Rounds | 0x13002EB5 | 13 | 0x340007DE | 5=30(+25/rank) 18=4.5 22=1.5 30=12 17=4 44=12 23=1.375 12=2 21=2 1=50(+35/rank) 9=-0.4 3=-50(-15/rank) 15=14(-2/rank) | yes |
| 0x48001032:4 | Deathstroke | R | Bullet Rain | 0x130038BE | 1 | 0x340007DD | 5=75(+75/rank) 1=0.15 23=7 18=2 17=2 44=1 30=16 14=0.75 19=0.15 9=-0.3 15=90 | yes |
| 0x48001032:5 | Deathstroke | Passive | Battle Fury | 0x13002EB7 | - | 0x340007DC | 27=0.25(+0.05/rank) 42=-4(-1/rank) 14=3 19=3 | yes |
| 0x480010EF:0 | Dex-Starr | Basic | Basic Attack | 0x130030B1 | 9 | 0x340006BA | 18=1 | yes |
| 0x480010EF:1 | Dex-Starr | Q | Lacerate | 0x130030B2 | 7 | 0x340006B9 | 5=50(+35/rank) 15=5 18=2.25 14=3 42=6(+2/rank) | yes |
| 0x480010EF:2 | Dex-Starr | W | Pounce | 0x130030B3 | 1 | 0x340006B7 | 15=15.5(-2.5/rank) 30=16 14=3 19=1.25 21=2 1=0.7(+0.15/rank) 5=0.7(+0.15/rank) 33=3 23=2.5 17=8 9=0.15 | yes |
| 0x480010EF:3 | Dex-Starr | E | Caustic Flood | 0x130030B4 | 13 | 0x340006B6 | 5=30(+30/rank) 15=14(-2/rank) 18=7 22=1.25 14=3 19=1.5 21=1 | yes |
| 0x480010EF:4 | Dex-Starr | R | Shred The World | 0x130030B5 | 13 | 0x340006B5 | 5=50(+50/rank) 15=90 30=12 22=1 18=7 24=40 17=2 1=0.5 19=0.25 | yes |
| 0x480010EF:5 | Dex-Starr | Passive | Vengeful Rage | 0x130030B6 | - | 0x340006B8 | 4=0.3(+0.05/rank) 15=5 14=1 19=5 12=-5 39=-10 38=2 42=0.5 5=10 | yes |
| 0x48001197:0 | Huntress | Basic | Basic Attack | 0x13003203 | 9 | 0x3400070F | 18=5.25 30=18 44=0.08 | yes |
| 0x48001197:1 | Huntress | Q | Snap Shot | 0x13003204 | 7 | 0x3400070C | 5=10(+10/rank) 18=5.75 30=18 27=0.08(+0.04/rank) 14=3 3=-1 15=6(-1/rank) | yes |
| 0x48001197:2 | Huntress | W | Hunter's Quarrel | 0x13003205 | 13 | 0x3400070B | 5=60(+60/rank) 18=8.5 22=1 30=14 14=5 4=0.1(+0.05/rank) 19=2 3=-1 15=5 | yes |
| 0x48001197:3 | Huntress | E | Grapple Bolt | 0x1300321B | 13 | 0x3400070A | 5=35(+30/rank) 18=7 22=0.7 30=20 27=18 17=2.5 14=0.3 3=-1 15=10(-1.5/rank) | yes |
| 0x48001197:4 | Huntress | R | Rapid Deployment | 0x1300321C | 5 | 0x3400070D | 5=1(+0.1/rank) 1=0.35(+0.15/rank) 14=10 19=1 15=120(-15/rank) | yes |
| 0x48001197:5 | Huntress | Passive | Tech Bolts | 0x1300321D | - | 0x34000709 | 31=1.5 32=3(+1/rank) 15=10(-1/rank) | yes |
| 0x480013E4:0 | John Stewart | Basic | Basic Attack | 0x1300356E | 9 | 0x340007A6 | 18=5.25 30=18 | yes |
| 0x480013E4:1 | John Stewart | Q | full_auto | 0x1300356F | 13 | 0x340007A7 | 5=40(+40/rank) 3=-30(-10/rank) 15=14(-2/rank) | yes |
| 0x480013E4:2 | John Stewart | W | claymore_mine | 0x13003570 | 13 | 0x340007A8 | 5=40(+40/rank) 3=-30(-10/rank) 15=14(-2/rank) | yes |
| 0x480013E4:3 | John Stewart | E | forward_base | 0x13003571 | 13 | 0x340007A9 | 5=40(+40/rank) 3=-30(-10/rank) 15=14(-2/rank) | yes |
| 0x480013E4:4 | John Stewart | R | omni_turret | 0x13003572 | 13 | 0x340007AA | 5=40(+40/rank) 15=14(-2/rank) | yes |
| 0x480013E4:5 | John Stewart | Passive | architects_will | 0x13003573 | - | 0x340007AB | 5=40(+40/rank) 15=20(-3/rank) | yes |
| 0x4800124F:0 | Nightmare Catwoman | Basic | Basic Attack | 0x1300326A | 9 | 0x34000725 | 18=1 30=18 | yes |
| 0x4800124F:1 | Nightmare Catwoman | Q | Rip & Tear | 0x13003270 | 13 | 0x34000728 | 5=60(+50/rank) 30=14 22=1 18=11 33=0.5 3=-70(-10/rank) 15=20(-2/rank) | yes |
| 0x4800124F:2 | Nightmare Catwoman | W | Soul Siphon | 0x1300326B | 14 | 0x3400072A | 5=60 1=0.06(+0.02/rank) 14=3 18=1.5 3=-50(-10/rank) 15=16(-1/rank) | yes |
| 0x4800124F:3 | Nightmare Catwoman | E | Scar the Land | 0x1300326C | 13 | 0x34000726 | 5=40(+30/rank) 42=-0.1(-0.05/rank) 14=3 19=5 18=1.414 17=4 22=1.5 44=1 24=-45 3=-30(-10/rank) 15=12(-1/rank) | yes |
| 0x4800124F:4 | Nightmare Catwoman | R | Inevitability | 0x1300326F | 1 | 0x34000729 | 5=100(+50/rank) 1=100(+50/rank) 18=4 23=5 14=2 19=0.3 21=1.5 15=180(-15/rank) | yes |
| 0x4800124F:5 | Nightmare Catwoman | Passive | Mangle | 0x1300326E | - | 0x34000727 | 9=-0.1(-0.04/rank) 14=3 19=5 18=5.5 | yes |
| 0x4800132F:0 | Nightwing | Basic | Basic Attack | 0x13003521 | 9 | 0x34000799 | 18=1 | yes |
| 0x4800132F:1 | Nightwing | Q | Eskrima | 0x13003522 | 5 | 0x34000795 | 12=0.55(+0.05/rank) 27=0.8 3=-30 15=6 32=3 14=6 | yes |
| 0x4800132F:2 | Nightwing | W | Thunderbolt | 0x13003523 | 1 | 0x34000793 | 3=-30 15=10 23=5 18=2 5=50(+40/rank) 21=0.25 19=2 | yes |
| 0x4800132F:3 | Nightwing | E | Rolling Thunder | 0x13003524 | 14 | 0x34000797 | 5=40(+30/rank) 3=-30(-10/rank) 15=20(-2/rank) 18=5 30=12 9=0.25 14=2 | yes |
| 0x4800132F:4 | Nightwing | R | Let's Ride | 0x13003525 | 5 | 0x34000794 | 5=165(+65/rank) 15=150(-10/rank) 18=9 17=3 22=1 14=10 4=5 12=1 21=5 30=12 | yes |
| 0x4800132F:5 | Nightwing | Passive | Static Burn | 0x13003526 | - | 0x34000796 | 5=10(+10/rank) 1=30 14=3 15=20 21=4 4=0.6 | yes |
| 0x480010B4:0 | Raven | Basic | Basic Attack | 0x13002FC4 | 9 | 0x34000681 | 18=5.25 30=18 44=0.07 | yes |
| 0x480010B4:1 | Raven | Q | Gloom | 0x13002FC5 | 1 | 0x3400067F | 5=60(+35/rank) 1=10(+5/rank) 18=1.375 23=7.5 14=2 19=0.5 32=3 3=-25(-10/rank) 15=3.5 | yes |
| 0x480010B4:2 | Raven | W | Empathic Link | 0x13002FC6 | 14 | 0x3400067E | 18=4 19=6 14=3 17=7.5 44=6 1=0.1 32=100 4=0.04(+0.04/rank) 9=-0.15(-0.05/rank) 12=0.2 3=-50(-25/rank) 15=14 | yes |
| 0x480010B4:3 | Raven | E | Isolation | 0x13002FC7 | 13 | 0x3400067D | 5=65(+45/rank) 21=1.5 3=-65(-10/rank) 15=18(-1/rank) 14=3 19=1.5 22=1 18=10 30=12 17=2 | yes |
| 0x480010B4:4 | Raven | R | Astral Projection | 0x13002FC8 | 1 | 0x3400067C | 18=4 23=60 14=4 21=1 19=2 10=125(+50/rank) 4=0.2 30=25 17=1 15=180(-20/rank) | yes |
| 0x480010B4:5 | Raven | Passive | Blessing of Darkness | 0x13002FC9 | - | 0x34000680 | 8=0.1 1=0.01 12=0.025(-0.005/rank) | yes |
| 0x480012B0:0 | Zod | Basic | Basic Attack | 0x1300335B | 9 | 0x3400074D | 18=1 30=15 45=1 17=14 | yes |
| 0x480012B0:1 | Zod | Q | Shield Breaker | 0x1300335C | 5 | 0x34000749 | 5=40(+15/rank) 9=-0.25 19=2 21=6 3=-30(-5/rank) 15=8 | yes |
| 0x480012B0:2 | Zod | W | Relentless | 0x1300335D | 5 | 0x3400074A | 14=4 18=3 19=-1 3=-50(-15/rank) 15=20(-2/rank) | yes |
| 0x480012B0:3 | Zod | E | Solar Surge | 0x1300335E | 13 | 0x34000748 | 27=0.25(+0.05/rank) 32=5 5=60(+40/rank) 18=3 24=180 3=-40(-20/rank) | yes |
| 0x480012B0:4 | Zod | R | Kneel Before Zod | 0x1300335F | 1 | 0x3400074B | 5=250(+100/rank) 12=0.5 15=150(-10/rank) 18=4.5 23=60 14=2 19=1.5 21=1 4=10 | yes |
| 0x480012B0:5 | Zod | Passive | Born in Battle | 0x13003360 | - | 0x3400074C | 42=5(+1/rank) 18=6 14=4 23=1.5 | yes |
## 6. Stolen Powers and other skill sources

| Source | Slot | Where | |
|---|---|---|---|
| Own kit | 0 Basic, 1–4 Q/W/E/R, 5 Passive | skill set (`0x100005E9`) = twin slots `0x100008E3`/`E8`/`EA`/`EC`/`E6`/`EF` | C |
| Own Stolen Power version | 7 (D) or 8 (F) | twin / skill set `0x10000CE5`: 53 champions have their own version (all listed in `catalog/data/stolen_powers.tsv`, including the 11 missing champions); **John Stewart has none and points at the base Meteor Drop `0x480005A2`** | C |
| Default Stolen Power pair | 7 + 8 | default loadout `0x10000CEB` -> `0x1000064E` (table in section 3); per-map loadouts in `0x10000CE9` (table below) | C (that the lobby pre-selects it: G) |
| Any other Stolen Power | 7 / 8 | catalog `0x480003CD` (12 groups); chosen in the lobby (`0x2017` RequestStolenPowerList, `GM_Lobby.SendNotice_RequestChangeStolenPower`, `0x2029` PlayerPickedStolenPowers) | C (protocol), G (server rules) |
| Artifacts with an active skill | 10–15 (items) | `catalog/data/artifacts.tsv` column `active_skill`: 32 artifacts, 29 distinct skills | C |
| Recall, Bonus | 6, 9 | not in any champion definition (`0x100008E4` / `0x100008F2` absent in all 156 twins): engine/global | C |
| Default amplifier sets | — | loadout records (artifacts `0x10000478`, `0x1000084C`–`F`, augments/mods `0x10000A12`, `0x1000098F`) | C (G for the field meanings) |

The Stolen Power versions on top of the base power merge their `0x1000003F` block onto the base's (see
reverse-engineering.md, "Stolen Powers"). The 11 missing champions' versions have no icon in `stolen_powers.tsv`
(empty `icon`); their records are in the packs.

### Loadouts per champion

| Champion | Loadouts `0x10000CE9` (record -> map id `0x10000CE4`) | Default `0x10000CEB` |
|---|---|---|
| Aquaman | 0x480013BD->3, 0x480013BE->5, 0x480013BC->4, 0x480013BD->6 | 0x480013BC |
| Arcane Green Lantern | 0x4800136B->3, 0x4800136C->5, 0x4800136A->4, 0x4800136B->6 | 0x4800136A |
| Arcane Harley Quinn | 0x48001393->3, 0x48001394->5, 0x48001392->4 | 0x48001392 |
| Arcane Supergirl | 0x480013C9->3, 0x480013CA->5, 0x480013C8->4, 0x480013C9->6 | 0x480013C8 |
| Arcane Zatanna | 0x480013A8->3, 0x480013A9->5, 0x480013A7->4, 0x480013A8->6 | 0x480013A7 |
| Atomic Green Lantern | 0x48001365->3, 0x48001366->5, 0x48001364->4, 0x48001365->6 | 0x48001364 |
| Atomic Joker | 0x480013C3->3, 0x480013C4->5, 0x480013C2->4, 0x480013C3->6 | 0x480013C2 |
| Atomic Poison Ivy | 0x48001381->3, 0x48001382->5, 0x48001380->4, 0x48001381->6 | 0x48001380 |
| Atomic Wonder Woman | 0x48001387->3, 0x48001388->5, 0x48001386->4, 0x48001387->6 | 0x48001386 |
| Atrocitus | 0x480013AE->3, 0x480013AF->5, 0x480013AD->4, 0x480013AE->6 | 0x480013AD |
| Batman | 0x48001341->3, 0x48001342->5, 0x48001340->4, 0x48001341->6 | 0x48001340 |
| Blue Beetle | 0x480013B4->3, 0x480013B5->5, 0x480013B3->4, 0x480013B4->6 | 0x480013B3 |
| Catwoman | 0x4800135C->3, 0x4800135D->5, 0x4800135B->4, 0x4800135C->6 | 0x4800135B |
| Cyborg | 0x480013A5->3, 0x480013A6->5, 0x480013A4->4, 0x480013A5->6 | 0x480013A4 |
| Deadshot | 0x480013C0->3, 0x480013C1->5, 0x480013BF->4, 0x480013C0->6 | 0x480013BF |
| Deathstroke | 0x480013A2->3, 0x480013A3->5, 0x480013A1->4, 0x480013A2->6 | 0x480013A1 |
| Dex-Starr | 0x480013CC->3, 0x480013CD->5, 0x480013CB->4, 0x480013CC->6 | 0x480013CB |
| Doomsday | 0x48001353->3, 0x48001354->5, 0x48001352->4, 0x48001353->6 | 0x48001352 |
| Flash | 0x48001399->3, 0x4800139A->5, 0x48001398->4, 0x48001399->6 | 0x48001398 |
| Gaslight Batman | 0x4800137D->3, 0x4800137E->5, 0x4800137C->4, 0x4800137D->6, 0x4800137F->1, 0x4800137F->7, 0x4800137F->8, 0x4800137F->9 | 0x4800137C |
| Gaslight Catwoman | 0x48001347->3, 0x48001348->5, 0x48001346->4, 0x48001347->6 | 0x48001346 |
| Gaslight Joker | 0x4800134A->3, 0x4800134B->5, 0x48001349->4, 0x4800134A->6 | 0x48001349 |
| Green Arrow | 0x4800135F->3, 0x48001360->5, 0x4800135E->4, 0x4800135F->6 | 0x4800135E |
| Green Lantern | 0x48001344->3, 0x48001345->5, 0x48001343->4, 0x48001344->6 | 0x48001343 |
| Harley Quinn | 0x4800134D->3, 0x4800134E->5, 0x4800134C->4, 0x4800134D->6 | 0x4800134C |
| Hawkgirl | 0x48001390->3, 0x48001391->5, 0x4800138F->4, 0x48001390->6 | 0x4800138F |
| Huntress | 0x480013D5->3, 0x480013D6->5, 0x480013D4->4 | 0x480013D4 |
| John Stewart | 0x48001412->3, 0x48001413->5, 0x48001411->4 | 0x48001411 |
| Katana | 0x480013B1->3, 0x480013B2->5, 0x480013B0->4, 0x480013B1->6 | 0x480013B0 |
| Krypto | 0x4800137A->3, 0x4800137B->5, 0x48001379->4, 0x4800137A->6 | 0x48001379 |
| Lex Luthor | 0x480013D8->3, 0x480013D9->5, 0x480013D7->4, 0x480013D8->6 | 0x480013D7 |
| Mecha Superman | 0x480013DB->3, 0x480013DC->5, 0x480013DA->4, 0x480013DB->6 | 0x480013DA |
| Mecha Wonder Woman | 0x48001384->3, 0x48001385->5, 0x48001383->4, 0x48001384->6 | 0x48001383 |
| Nightmare Batman | 0x48001371->3, 0x48001372->5, 0x48001370->4, 0x48001371->6 | 0x48001370 |
| Nightmare Catwoman | 0x48001362->3, 0x48001363->5, 0x48001361->4 | 0x48001361 |
| Nightmare Robin | 0x48001377->3, 0x48001378->5, 0x48001376->4, 0x48001377->6 | 0x48001376 |
| Nightmare Superman | 0x4800138D->3, 0x4800138E->5, 0x4800138C->4, 0x4800138D->6 | 0x4800138C |
| Nightwing | 0x480013DE->3, 0x480013DF->5, 0x480013DD->4 | 0x480013DD |
| Poison Ivy | 0x48001359->3, 0x4800135A->5, 0x48001358->4, 0x48001359->6 | 0x48001358 |
| Raven | 0x480013B7->3, 0x480013B8->5, 0x480013B6->4, 0x480013B7->6 | 0x480013B6 |
| Robin | 0x480013C6->3, 0x480013C7->5, 0x480013C5->4, 0x480013C6->6 | 0x480013C5 |
| Shazam | 0x480013AB->3, 0x480013AC->5, 0x480013AA->4, 0x480013AB->6 | 0x480013AA |
| Sinestro | 0x48001396->3, 0x48001397->5, 0x48001395->4, 0x48001396->6 | 0x48001395 |
| Solomon Grundy | 0x4800138A->3, 0x4800138B->5, 0x48001389->4, 0x4800138A->6 | 0x48001389 |
| Star Sapphire | 0x4800139F->3, 0x480013A0->5, 0x4800139E->4, 0x4800139F->6 | 0x4800139E |
| Stargirl | 0x4800136E->3, 0x4800136F->5, 0x4800136D->4, 0x4800136E->6 | 0x4800136D |
| Starro | 0x480013BA->3, 0x480013BB->5, 0x480013B9->4, 0x480013BA->6 | 0x480013B9 |
| Supergirl | 0x48001374->3, 0x48001375->5, 0x48001373->4, 0x48001374->6 | 0x48001373 |
| Superman | 0x48001350->3, 0x48001351->5, 0x4800134F->4, 0x48001350->6 | 0x4800134F |
| Swamp Thing | 0x480013D2->3, 0x480013D3->5, 0x480013D1->4, 0x480013D2->6 | 0x480013D1 |
| The Joker | 0x48001368->3, 0x48001369->5, 0x48001367->4, 0x48001368->6 | 0x48001367 |
| Wonder Woman | 0x48001356->3, 0x48001357->5, 0x48001355->4, 0x48001356->6 | 0x48001355 |
| Zatanna | 0x4800139C->3, 0x4800139D->5, 0x4800139B->4, 0x4800139C->6 | 0x4800139B |
| Zod | 0x480013CF->3, 0x480013D0->5, 0x480013CE->4 | 0x480013CE |

## 7. What the client needs to list, select and load a champion

All of this is **server data**; the client has no champion list of its own (C: the exe has no champion names or
DIDs; no record lists the roster).

| Step | Event | What it must carry | |
|---|---|---|---|
| Ownership | `0x20B8` item statuses (handler `0xa88030` -> `UI.RecvNotice_ItemStatuses`, `RecvNotice_AvailableCharacterList` once 0x20ED arrived) | ownables `u32 did | u32 content status | u32 content type | u8 owned | u32 count` for every variant (type 1 Character for the base, 4 Skins for costumes) | C |
| Roster + metadata | `0x20ED` champion data (exec `0x8ab100`, handler `0xa833d0`, `Character.RecvNotice_MasterCharacterListReceived`) | groups `[base, costumes..., skills pseudo-item]` (no group may be empty) + one metadata entry per DID: `variant | ? | parent pack (cat 8, 0x10000730) | heavy pack (cat 7, 0x1000035C) | light pack (cat 6, 0x100005E0) | wallpaper pack (cat 5, 0x100005DF) | pregame record (0x100005E6) | light record (0x100005E7) | twin 0x49 | bool | grid icon | name`; for the skills pseudo-item the light pack = skills pack (0x10000B0D) | C (see `ics/messages.py`) |
| Advancement | `0x209D` master character list (`RecvNotice_CharacterAdvancementData`) | `did | level | xp | next xp | last used | ranked last used` per champion; table must not be empty | C |
| Selection | client `0x2102` SelectCharacter `u32 DID, u8`, `0x2025` RequestCharacterPickerInformation; server `0x2029` / `0x204C` lobby slot and state (owned list) | | C (formats probable) |
| Match | `0x20AF` enter match: champion DIDs (players, bots, cinematic actors) + pack list | each champion's own cat 7 pack must be in the pack list (`ics/session.py _match_content`); the shared cat 8 pack is named by the 0x20ED metadata (`parent`). For Raven Dark Omen (own pack 11 KB), Arcane Harley Quinn (9 KB) and Nightmare Superman The Phantom King (19 KB) the model lives in the shared pack | C (packs), G (that the parent pack is loaded from the metadata) |

### Content statuses and the UI (from the Flash UI, `OwnablesManager.CalculateOwnableUIState`, C)

`ContentStatusList`: 1 Free, 2 Available, 3 Disabled, 4 Unreleased, 5 Hidden, 6 AlwaysOwned, 1001 Innate, 1002
Unavailable. `ContentType`: 1 Character, 2 StolenPower, 3 AvatarIcon, 4 Skins, 5 Amplifier, 6 Boost, 7 Currency,
8 Bundle, 9 Skill, 10 Texture, 11 Artifact, 12 Augments, 13 Mods, 14 Entitlement, 15 GenericDataID, 16 SubCurrency,
17 Achievement, 18 RewardSet, 19 RewardGroup, 20 AccountXP, 21 Encounter, 22 Effect, 23 TrainingLesson, 24 Accolade,
25 LoginReward.

UI state (args: status, owned, in view match, tutorial mode, tutorial override):

| Status | owned | not owned | |
|---|---|---|---|
| tutorial mode with override | OWNED | OWNED | C |
| 1002 Unavailable | UNAVAILABLE | UNAVAILABLE | C |
| 1 Free (free rotation) | OWNED (FREE in view-match) | FREE (playable) | C |
| 2 Available | OWNED | PURCHASABLE | C |
| 3 Disabled | DISABLED | DISABLED | C |
| 1001 Innate | OWNED (INNATE) | INNATE | C |
| 4 Unreleased | OWNED | UNRELEASED | C |
| 5 Hidden | OWNED | UNLISTED (not shown; used by the server for the skills pseudo-item) | C |
| 6 AlwaysOwned | OWNED | OWNED | C |

So "free rotation", "locked", "disabled" and "unreleased" are only the status/owned pair the server sends per
variant; any champion with data can be offered by sending it as Available/AlwaysOwned + owned. The client UI has
the matching visuals (`m_mcUnreleased`, `OWNABLE_UI_STATE_DISABLED`/`PURCHASABLE`/`UNRELEASED`).

### Adding the 11 missing champions (what the server would need; nothing changed here)

1. A roster entry per variant built from the twin (`0x49`): `id` = `0x100005E7`, `pregame_heavy` = `0x100005E6`,
   `variant` = the `0x40`, `heavy_pack` = `0x1000035C`, `parent_pack` = `0x10000730`, `light_pack` = `0x100005E0`,
   `wallpaper_pack` = `0x100005DF`, `skills_key` = `0x100005E9`, `skills_pack` = `0x10000B0D`, `heavy_dbpc` = the
   twin, `tex384` = `0x10000384`, `tex799` = `0x10000799`, `wallpaper` = `0x100005B0` (pregame record),
   `grid_icon` = `0x1000072E` (all values in section 4). Fix the 14 wrong variant DIDs the same way.
2. Their 66 kit rows in `skills.tsv` (section 5) and their rows in `champions.tsv`.
3. Risk (G): the pack manager has 16 slots per pack category (light packs = cat 6, old server note in
   `old_files/login_server.py`); 54 champions name 54+ light packs in one 0x20ED.

## 8. Champions in bot pools

Encounter templates carry a bot champion pool (`0x10000B3E` entries `0x10000B3D` = variant DID; see
`maps-encounters.md`). The pools read here (`0x49000B6C` Gotham Heights v AI, `0x49000E62` Gotham Divided
Intermediate [test]: 14 entries; `0x49000E65` Multi-bot Push [test]: 15) use only six champions, all in the roster:
Gaslight Batman (`0x40000086`, `0x40000549`, `0x400003C7`, + `0x40000BD3` in E65), Gaslight Joker (`0x4000038D`,
`0x40000610`, `0x400007F3`), Superman (`0x4000002B`, `0x4000092D`, `0x40000806`), Green Lantern (`0x4000034D`,
`0x400006EB`), Atomic Wonder Woman (`0x400003EC`, `0x40000802`), Zatanna (`0x4000015B`) (C).

## 9. Open questions

- `0x1000076A`: a `0x40` DID per champion that no pack contains (unknown; maybe the original database's powerset id).
- `0x10000593` champion index and `0x100005F0` roles (values 1–11): names not confirmed.
- Whether the client loads the cat 8 shared pack from the 0x20ED `parent` field by itself (G; Gaslight Batman works).
- Why the decoder fails on `0x3400077A`, `0x34000777`, `0x340007A2` (and 46 other `0x34` records).
- The 28 variants whose world state (`0x510`) is not a plain `did | 7 | entity | 0 | n` record (e.g. Gaslight Batman
  `0x40000086`): their entity is still found through the own/shared pack (G).
