# Skill rank level requirements: the 19th point (2026-10-30)

Tester report (2026-10-30, Crime Alley v AI): "on reaching level 19 the skill level-up prompt appears but it does not
let me rank: the button stays in 'Recommended' and on the HUD; neither the '+' nor Ctrl + skill key ranks up."

Tags: [C] confirmed from code or data, [P] probable, [G] guessed.

## 1. Cause [C]

- The level cap is 19 (`[ics] level_cap`, the client's InqLevelCap default, `hud-xp-ring.md`), so a champion gets
  19 skill points (1 at the start + 18 level-ups). Every champion's build spends them 4/4/4/4/3 (Q/W/E/R/passive).
- The fase3-gz rule `[ics] rank_min_levels = {"4": [6, 11, 16, 20]}` put the **4th R rank at level 20**, above the cap.
  At level 19 every other slot was full by our rules, so the 19th point could never be spent.
- The client runs its own GM_Advancement handlers (registered by `0x9F 0x81A1000B`, `advancement_handlers`): its
  InqCanRankSkill and InqNextRecommendedSkillToRank offered the R's 4th rank from level 18, so the "+" and the
  Recommended marker stayed lit. The click went to the server (ping "KNAR" + script RPC `0x81910003`), and
  `ics/session.py ev_ping` dropped it **without a log line** (`not rankable -> return`).
- The 11:05-11:23 logs only reach ~level 12 (12 ranks, each "(0 points left)"), so they show the round trip but not
  the level-19 case; the headless replay (`tests/test_match.py rank_levels_1_to_19`, `rank_levels_from_client =
  false`) reproduces it: R rank 4 refused at 19 with 1 point left.

## 2. The client's rule (WLib record `0x39000001`) [C for the structure, P for the opcode meanings]

InqCanRankSkill handler `0x9788` -> `0x9A30` (max rank, `SkillRank_AtMaxRank 0x10000018`) -> **`0x926C`**:
skill defined (native `0x1050005`, else `Skill_NotDefined 0x1000002D`); slot > 5 -> `NotManuallyChanged
0x10000017`; rank range (`0x9644` returns 4) -> `InvalidRank 0x10000008`; level `0x9194` (property `0x10000167`)
checked by **`0x94E4`** -> `NotHighEnoughLevel 0x10000022`; skill points `0x9248` (`0x100001AF`) ->
`NotEnoughSkillPoints 0x10000014`; prerequisites native `0x105000D` -> `NeedPrerequisite 0x10000072`.

`0x94E4(slot, level, rank)` returns "too low":
1. Native `0x1050008` (exe `0x8509A0` -> `0x86EF10`) reads property **`0x1000099C`** (int array) of the slot's skill.
   If it exists and `1 <= rank <= len`: too low = `level < array[rank - 1]` (array get native `0x170004`, count
   `0x17000F`).
2. Otherwise a built-in table (immediates in the bytecode at `0x9564`-`0x9640`):
   - slot 4 (R): rank 4 at level 18, rank 3 at 14, rank 2 at 10, rank 1 at 6;
   - every other slot: rank 4 at 9, rank 3 at 6, rank 2 at 3; rank 1 at level 1 [P: the decoded fall-through reads
     as "too low" for rank 1, which cannot be right since the tester ranks Q at level 1 through these handlers; one
     compare opcode is probably read the wrong way round].

Data [C, scan of the 54 skill sets]: only two skill blocks carry `0x1000099C`: Green Arrow's R (`0x100008E6`)
`[1, 6, 11, 16]` and Starro's E (`0x100008EC`) `[2]`.

Cross-check [C]: all 156 variants' build orders (`0x1000034B`, the Recommended order) satisfy this rule point by point
(point n at level n), and none satisfies the old one (R rank 2 at point 10 < 11). The old non-R rule (rank r at 2r - 1:
1/3/5/7) also let the server offer ranks 3 / 4 earlier than the client (5 vs 6, 7 vs 9).

## 3. Fix (ics)

- `Data.skill_rank_levels(variant)` reads `0x1000099C` from each slot block of the skill set.
- `World.rank_level_needed(ent, slot, rank)`: the client's rule (`[ics] rank_levels_from_client = true`,
  `rank_level_table = {"4": [6, 10, 14, 18], "default": [1, 3, 6, 9]}`); false = the fase3-gz keys. Bots use the
  same function (`ics/match/bots.py`).
- `World.rank_refusal` gives the reason; `World.refuse_rank` logs "rank request slot N: refused, <reason> (level,
  points, ranks)" and (`[ics] rank_refused_refresh = true`) sends the champion's rank state again (at most once a
  second, so a HUD refresh burst cannot loop). `ev_ping` now lets a lone refused request reach it; the RankSkill
  script RPC log line says when the server will refuse.
- `max_skill_ranks` unchanged (4/4/4/4/3 matches every build).

## 4. Open

- The exact opcode semantics of the WLib compares (rank 1 of non-R slots, above).
- What the client does when the server refuses: it has no answer message wired (`0x9F 0x81910001` is the original's
  "ranked" notice; nothing for a refusal). The resent properties (`SkillPoints`, `0x100000AF`, `0x100006C1`) let its
  own handlers re-evaluate.
