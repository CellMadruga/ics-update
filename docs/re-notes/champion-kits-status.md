# Champion kits vs AI in Crime Alley: headless status (2026-10-23)

Tool: `python tools\champion_check.py` (base variants; `--all` adds the costumes; `--only <did>`; `--trace <slot>`
prints every log line of that slot's cast). It builds a World + PvP match for Crime Alley v AI (`0x40000C82`) on a
simulated session (as `tests/test_match.py`), runs on a **virtual clock** (`time.time` = the session's clock, so the
scripts' timers advance with the simulation), creates each variant as the local champion, waits for the first wave,
levels to 6 with slots 0-4 at rank 1, freezes the minions in place and, for slot 0 and Q W E R, stands 2 m from an
enemy minion on a walkable spot and casts the way the client orders it for the skill's targeting type
(`0x1000003D`: 9 / 14 unit, 1 / 10 / 11 / 13 / 16 point, 5 / 7 instant), then runs 3 s.

A slot without damage is also tried: a basic attack right after it ("next basic"), a cast on a **dummy enemy
champion** 2.5 m in front, a cast on the champion itself (unit-target skills) and a cast with both a target and a
point. Experiments (`--fixes` = all three) monkeypatch the fixes proposed below, inside the tool only.

Verdicts: **DMG** damage dealt to an enemy; **CHMP** damage only on the dummy champion; **BUFF** the next basic
attack hit harder (>15 %); **FX** a status / missile / spawned entity / forced move / heal but no damage; **anim**
only scriptlets / cooldown / Will spent; **TGT** nothing until cast on itself or with target + point; **NONE** no
effect at all; **REF** refused by CanActivate.

JSON summaries (scratchpad, not in the repo): `champion_check_base.json` (current ics), `champion_check_base_fixes.json`
(`--fixes`), `champion_check_all.json` / `champion_check_all_fixes.json` (156 variants).

## Overall numbers

| run | slots | DMG | FX | anim | CHMP | BUFF | TGT | NONE | REF | EXC |
|---|---|---|---|---|---|---|---|---|---|---|
| 54 base variants, ics as is | 270 | 117 | 92 | 31 | 9 | 3 | 5 | 9 | 4 | 0 |
| 54 base variants, `--fixes` | 270 | 135 | 81 | 25 | 10 | 2 | 5 | 8 | 4 | 0 |
| 156 variants, ics as is | 780 | 342 | 264 | 87 | 23 | 8 | 17 | 29 | 10 | 0 |
| 156 variants, `--fixes` | 780 | 399 | 231 | 69 | 26 | 5 | 17 | 23 | 10 | 0 |

- No exception, no script error, no "not implemented" node, no "not decoded" script in any of the 780 casts.
- Every basic attack (54 / 54) deals damage. Every costume behaves exactly like its base champion (same skill set).
- **Packs**: every variant's model pack (`Data.champion_pack`), parent pack (`Data.champion_shared_packs`), light
  pack and skills pack exist in the install (156 / 156; table below for the base variants).
- FX is not "broken": it covers self buffs, ground zones whose damage ticks after 3 s, roots / slows / knockbacks.
  Heals are not seen (the champion is at full health before each cast).
- The scene matters for skillshots and dashes: a few slots flip DMG <-> FX between runs with other minion positions
  (Cyborg Q / R, Mecha Superman R, Catwoman R). The tool stands on the navmesh with a clear line to the target to keep
  this down.

## Failure causes and fixes in ics/ (ranked)

### 1. RaiseEvent ignores its target script (VM bug, severe) — `ics/script_nodes.py` `_raise_event_node`

`RaiseEvent(entity, ...) [event, script DID, ...]`: the second value is the script the event is for. Cyborg's basic
attack `0x34000238` does `RaiseEvent(SELF) [0x1000001D 0x34000237]` ("skill used" for his passive only); the node
sends the event to **every** script on the entity (`R.raise_event`), so each basic attack activated Q, W, E, R and
both Stolen Powers (trace: 0x34000236 / 235 / 234 / 233 / 2A2 / 19F all leave S0 at the impact). The same pattern:
257 RaiseEvent nodes with a script DID in 164 of the 875 scripts (0x1000001D, 0x10000141, 0x10000107, 0x10000140,
0x10000006, ...).

Fix: when `n.values[1]` is a `0x34xxxxxx` DID, deliver only to `R.scripts_on(world, ent)` instances whose
`script.did` equals it; keep the broadcast when it is 0; keep the `EVENT_IMPACT` status removal. Tested in
`champion_check.patch_raise_event`. In game this also stops free casts / cooldowns on every basic attack.

### 2. Missile templates cut before their 0x8E script list — `ics/gamedata.py` `Data.entity_scripts` (and `rp.Pack.record_starts`)

The record-start list also "starts" records at interior words of a template: after property `0x510` (its world-state
DID, e.g. `0x490003EB` ... `0x510 0x510 | 0x2E0008F2 ...`) or inside the `0x8E` list itself (`0x49000146`). The
template window then ends before the `0x8E` list, `entity_scripts` returns `[]` and the missile flies with no script:
no damage. 43 of the 93 skill projectiles had no scripts; searching on to the next template header
(`0x49xxxxxx | 3`, at most 4 KB) recovers 25:

`0x4000000A` Nightmare Batman Q, `0x40000146` Poison Ivy Q, `0x40000263` Wonder Woman Q, `0x4000026E` Gaslight
Catwoman Q, `0x4000039A` Gaslight Joker W, `0x400003EB` Batman Q (`0x34000251`), `0x40000485` Atomic GL Q,
`0x400005D3` Aquaman Q (`0x34000393`), `0x400007F0`, `0x400007F2`, `0x40000815` Blue Beetle Q, `0x400008C4`,
`0x400009B3`, `0x400009B5` (Atomic Joker E / W), `0x40000A5A` Atomic Joker Q, `0x40000B18`, `0x40000B1C`,
`0x40000BAF`, `0x40000BDB` Lex W, `0x40000BE5` Lex R, `0x40000C6B`, `0x40000D24` Nightmare Catwoman Q, `0x40000D2D`
Shazam Q, `0x40000E6F`, `0x40000EE5` Nightwing E.

Still empty (another record type sits between, or none): `0x400001E7 0x40000359 0x40000487 0x40000545 0x40000634
0x400007F6 0x400009B7 0x40000AE5 0x40000BCA 0x40000BD4 0x40000CA7 0x40000CC8 0x40000CD6 0x40000CD7 0x40000CD8
0x40000D55 0x40000ED1 0x40000ED2` (`0x40000634` has a list 1784 bytes on, `0x400007F6` 2584 bytes on, past other
records: a proper fix reads the template by property kind instead of a byte window). Tested in
`champion_check.patch_entity_scripts`; the better long-term fix is to drop false starts in `record_starts`.

### 3. IsInRangeAndAngle without a max range — `ics/script_nodes.py` `_in_range_and_angle`

Cone checks such as Katana's Slash `0x340005B8`: `IsInRangeAndAngle(-, -, $Angle, target, SELF) [1 1]`. With the
max operand unset the radius flags alone make `r = 1.0`, so every target 2 m away fails. Fix: apply the distance test
(and the radius additions) only when the max operand is set. Fixed Katana Q, Superman W (Frost Breath), Sinestro W,
Harley R in the run (`champion_check.patch_range_angle`).

### 4. Champion init event 0x10000088 never raised on the champion — `ics/world.py` `create_champion` / `respawn`

Arcane Green Lantern's passive `0x34000292` spawns his Lantern (`0x4000045F`, the shared variable his Q / W / E use)
on `0x10000088`; the server raises it only on match units (`ics/match/units.py EVENT_UNIT_INIT`). Without the
Lantern, E logs "LaunchLobbedMissile: no class and no entity" and W (Shackles) never leaves S0. Listeners: AGL
passive, Arcane Zatanna passive, Blue Beetle R, Star Sapphire passive. Fix: after `start_kit` (and after a respawn)
`R.raise_event(CastWorld(self, ent, None), ent, 0x10000088)`, behind an `[ics]` key. Tested with
`--init-events 0x10000088`: AGL W / E / R go from NONE / anim to FX.

### 5. "any -> X" transitions re-enter their own state every tick — `ics/script_runtime.py` (Region transition pick)

Starro's W `0x34000531`, graph S4: `any -> S1 when SkillCharges == 1` (polled, no event). The VM takes it again while
already in S1, re-running the enter chain: `StartScriptlet 0x10000D94` ~240 times a second (720-770 scriptlets in 3 s
in every Starro slot: a network flood in game). 56 such polled transitions in 17 scripts (`0x34000000, 0x340000E0,
0x34000161, 0x3400016C, 0x34000177, 0x340002D7, 0x340002DA, 0x340002E3, 0x340003D1, 0x34000480, 0x340004EB,
0x34000531, 0x340005AB, 0x340005D8, 0x34000628, 0x34000736, 0x34000838`). Fix: a polled transition from "any" does not
fire when its destination is the current state (event-triggered ones may still re-enter; check the client's HFSM).

### 6. Events the server never raises (need RE before a fix)

- `0x10000022` / `0x10000014` after node `0x10000005` (`_flag_node("attached_skill")`) + `0x1000000B`
  AddSkillTarget: Atomic Wonder Woman R `0x34000253`, Atrocitus E, Doomsday E, Nightmare Batman R, Nightmare Robin R
  (same S7 pattern), Zatanna R: they wait for one of the two events (with HoldsActionLock) and never get it, even on
  the dummy champion. Probably the "attached / grab started" confirmation; find who raises it in the client.
- `0x1000008B` (24 scripts): Zod's Solar Surge `0x34000748` counts basic attacks on it (`BasicAttackCounter >=
  RequiredBasicAttackCount` clears its disable condition 0x10000066: REF until then); Arcane GL passive. Probably
  "basic attack landed"; raise it from the basic-attack hit (World._attack_step / deal_damage with slot 0).
- `0x100000A9` (56 scripts, part of the re-init family): Aquaman's R `0x34000397` disables itself on `0x10000008`
  and only re-evaluates on `0x100000A9` (its slot's HFSM vs the basic ult): REF. With `CastWorld.set_slot_skill`
  returning False (form swaps not mapped) this slot cannot work yet.

### 7. Targets that do not exist vs AI (match / session, not the VM)

- **Enemy champion only** (`IsKind [8]`): Superman R, Atomic Wonder Woman R, Hawkgirl R (375 dmg on the dummy),
  Harley Q (Pies, 150 on the dummy), Zatanna R, Nightmare Robin R, Deathstroke Q, Raven E, Star Sapphire W, Lex E, WW Q
  (CHMP / NONE rows). Crime Alley v AI has no enemy champions: `ics/match/match.py _players` only adds the session's
  champion. Bots from the encounter's pool (HANDOFF step 8) are needed for these to be usable.
- **Ally champion only**: Arcane Green Lantern R `0x34000291` (`IsKind 8`, `CheckRelation 4`, not self).
- **Self / ally cast** (work on the champion itself): Harley E, Poison Ivy E, Wonder Woman W, Zatanna W. The client
  sends the caster as the target with UseSelfCast (full-combat-skills.md); check that `ev_order` passes it through
  when the target IID is the champion's.

### 8. By design / prerequisites (no fix needed, test artifacts)

Deadshot R (only from W's scope states S4 / S5 / S1), Arcane Supergirl R (needs `CurrentCharges > 0` from her
passive), Doomsday R (VitalThreshold), Katana E (Soultaker `0x340005B9` keeps 0x10000066 until hit events
0x10000140 / 0x10000141), Starro E (0x10000059 NoTargets: needs Parasites from W), Arcane GL W (needs the Lantern
near enemies). Self buffs whose effect is not damage in 3 s (anim / FX rows): Deathstroke W, Gaslight Joker E, Flash
E, Supergirl E, Green Arrow W / E (arrow modes), Deadshot W, Blue Beetle R, Cyborg E, Swamp Thing R (BUFF), Catwoman R.

**John Stewart** (`0x40000E57`): an unreleased placeholder kit (skill names `full_auto`, `claymore_mine`,
`forward_base`, `omni_turret`; all four scripts start the same 11.3 s cooldown and spend, no scriptlet, no damage).

### Ranked fix list

1. `script_nodes._raise_event_node`: honour the script DID (n.values[1]). Many kits, also free casts in game.
2. `gamedata.Data.entity_scripts`: read the 0x8E list past false record starts (25 projectiles get their damage).
3. `script_nodes._in_range_and_angle`: no range test when the max operand is unset (all cone skills).
4. `world.create_champion` / `respawn`: raise `0x10000088` on the champion's scripts (`[ics] champion_init_event`).
5. `script_runtime` Region: a polled "any -> X" transition does not re-enter X (Starro's scriptlet flood, 17 scripts).
6. `match.match`: enemy (and allied) bot champions in v AI maps, or champion-only skills stay unusable.
7. RE: events 0x10000022 / 0x10000014 (after node 0x10000005), 0x1000008B, 0x100000A9; `CastWorld.set_slot_skill`.
8. `gamedata.entity_scripts`: a template reader by property kind for the 18 projectiles still without scripts.

## Per champion (base variants; "a -> b" = ics as is -> with `--fixes`)

| Champion | Variant | Basic | Q | W | E | R | model pack | parent pack | packs present |
|---|---|---|---|---|---|---|---|---|---|
| Aquaman | `0x400005C6` | DMG | FX -> DMG | DMG | DMG | REF | `0xA0000192` | `0xA0000191` | yes |
| Arcane Green Lantern | `0x4000043B` | DMG | DMG | NONE | anim | NONE | `0xA0000144` | `0xA0000145` | yes |
| Arcane Harley Quinn | `0x40000D51` | DMG | DMG | FX | FX | FX | `0xA0000383` | `0xA0000384` | yes |
| Arcane Supergirl | `0x40000AB3` | DMG | FX | FX | anim | NONE | `0xA0000282` | `0xA0000281` | yes |
| Arcane Zatanna | `0x40000BF5` | DMG | DMG | FX | anim | FX | `0xA0000304` | `0xA0000303` | yes |
| Atomic Green Lantern | `0x4000047D` | DMG | FX -> DMG | DMG | FX | FX | `0xA0000151` | `0xA0000150` | yes |
| Atomic Joker | `0x40000962` | DMG | FX -> DMG | FX | FX -> CHMP | anim -> DMG | `0xA000024B` | `0xA000024A` | yes |
| Atomic Poison Ivy | `0x40000553` | DMG | DMG | DMG | FX | FX | `0xA000018E` | `0xA000018D` | yes |
| Atomic Wonder Woman | `0x400003EC` | DMG | DMG | FX | DMG | NONE | `0xA0000123` | `0xA0000124` | yes |
| Atrocitus | `0x40000932` | DMG | FX | FX | anim | FX | `0xA000023F` | `0xA000023E` | yes |
| Batman | `0x40000280` | DMG | FX -> DMG | DMG | DMG | FX | `0xA00000DD` | `0xA000011F` | yes |
| Blue Beetle | `0x400007FA` | DMG | FX -> DMG | FX | FX | anim | `0xA0000201` | `0xA0000202` | yes |
| Catwoman | `0x4000041C` | DMG | DMG | DMG | FX | BUFF -> FX | `0xA000012D` | `0xA000012C` | yes |
| Cyborg | `0x400003B2` | DMG | CHMP -> DMG | anim -> DMG | anim | CHMP | `0xA000010A` | `0xA0000112` | yes |
| Deadshot | `0x40000C68` | DMG | DMG | anim | FX | NONE | `0xA0000338` | `0xA0000337` | yes |
| Deathstroke | `0x40000C19` | DMG | CHMP | anim | DMG | FX | `0xA000030F` | `0xA000030E` | yes |
| Dex-Starr | `0x40000C75` | DMG | DMG | anim | DMG | DMG | `0xA0000340` | `0xA000033F` | yes |
| Doomsday | `0x4000015A` | DMG | DMG | FX | anim | NONE | `0xA00000A2` | `0xA000011C` | yes |
| Flash | `0x40000396` | DMG | DMG | FX | anim | DMG | `0xA00000F7` | `0xA0000121` | yes |
| Gaslight Batman | `0x40000086` | DMG | DMG | DMG | DMG | DMG | `0xA0000076` | `0xA0000122` | yes |
| Gaslight Catwoman | `0x40000262` | DMG | FX -> DMG | DMG | FX | DMG | `0xA00000CC` | `0xA000010B` | yes |
| Gaslight Joker | `0x4000038D` | DMG | FX | FX -> DMG | anim | FX | `0xA00000EB` | `0xA0000114` | yes |
| Green Arrow | `0x400006F9` | DMG | FX | anim | anim | anim | `0xA00001F2` | `0xA00001F3` | yes |
| Green Lantern | `0x4000034D` | DMG | DMG | FX | DMG | FX | `0xA00000E0` | `0xA0000115` | yes |
| Harley Quinn | `0x4000054A` | DMG | CHMP | DMG | TGT | anim -> DMG | `0xA0000187` | `0xA0000186` | yes |
| Hawkgirl | `0x40000AE2` | DMG | DMG | FX | FX | CHMP | `0xA00002B5` | `0xA00002B4` | yes |
| Huntress | `0x40000CD3` | DMG | FX | DMG | FX | FX | `0xA0000362` | `0xA0000361` | yes |
| John Stewart | `0x40000E57` | DMG | anim | anim | anim | anim | `0xA000039E` | `0xA000039F` | yes |
| Katana | `0x40000BA6` | DMG | anim -> DMG | FX | REF | DMG | `0xA00002E4` | `0xA00002E3` | yes |
| Krypto | `0x40000BE4` | DMG | FX | FX | FX | DMG | `0xA00002F8` | `0xA00002F7` | yes |
| Lex Luthor | `0x40000B70` | DMG | FX | FX | CHMP | FX | `0xA00002DF` | `0xA00002DE` | yes |
| Mecha Superman | `0x4000063D` | DMG | DMG | FX | FX | DMG -> FX | `0xA00001E9` | `0xA00001E8` | yes |
| Mecha Wonder Woman | `0x40000483` | DMG | DMG | FX | FX | anim | `0xA0000156` | `0xA0000157` | yes |
| Nightmare Batman | `0x40000009` | DMG | FX -> DMG | FX | FX | anim | `0xA0000073` | `0xA0000116` | yes |
| Nightmare Catwoman | `0x40000CEA` | DMG | FX -> DMG | DMG | DMG | FX | `0xA000036C` | `0xA000036D` | yes |
| Nightmare Robin | `0x4000091B` | DMG | DMG | FX | DMG | NONE | `0xA000022F` | `0xA000022E` | yes |
| Nightmare Superman | `0x400007C0` | DMG | FX | BUFF | DMG | FX | `0xA00001F9` | `0xA00001FA` | yes |
| Nightwing | `0x40000DEE` | DMG | FX | CHMP | FX -> DMG | DMG | `0xA0000399` | `0xA000039A` | yes |
| Poison Ivy | `0x40000145` | DMG | FX -> DMG | DMG | TGT | FX | `0xA000009B` | `0xA0000111` | yes |
| Raven | `0x40000C4F` | DMG | DMG | FX | CHMP | FX | `0xA0000333` | `0xA0000332` | yes |
| Robin | `0x4000052D` | DMG | DMG | FX | FX | DMG | `0xA0000175` | `0xA0000176` | yes |
| Shazam | `0x40000358` | DMG | FX -> DMG | FX | FX | DMG | `0xA00000E5` | `0xA0000120` | yes |
| Sinestro | `0x40000805` | DMG | DMG | anim -> DMG | DMG | FX | `0xA000020F` | `0xA000020E` | yes |
| Solomon Grundy | `0x40000C44` | DMG | DMG | DMG | FX | FX | `0xA0000327` | `0xA0000328` | yes |
| Star Sapphire | `0x400005D1` | DMG | FX | CHMP | DMG | DMG | `0xA00001D1` | `0xA00001D2` | yes |
| Stargirl | `0x40000AEA` | DMG | DMG | FX | FX | DMG | `0xA00002B2` | `0xA00002B1` | yes |
| Starro | `0x40000A96` | DMG | DMG | FX | REF | anim | `0xA000026D` | `0xA000026E` | yes |
| Supergirl | `0x40000810` | DMG | FX | DMG | anim | TGT | `0xA0000222` | `0xA0000221` | yes |
| Superman | `0x4000002B` | DMG | FX | anim -> DMG | DMG | NONE -> anim | `0xA0000075` | `0xA000011D` | yes |
| Swamp Thing | `0x40000B16` | DMG | anim -> FX | FX | FX | BUFF | `0xA00002CE` | `0xA00002CF` | yes |
| The Joker | `0x40000213` | DMG | DMG | FX | FX | FX | `0xA00000B4` | `0xA000011B` | yes |
| Wonder Woman | `0x40000260` | DMG | FX -> CHMP | TGT | DMG | FX | `0xA00000C9` | `0xA000011E` | yes |
| Zatanna | `0x4000015B` | DMG | FX | TGT | DMG | NONE | `0xA00000A3` | `0xA0000113` | yes |
| Zod | `0x40000D29` | DMG | FX | FX | REF | anim | `0xA0000379` | `0xA0000378` | yes |

Packs: model pack = `Data.champion_pack` (the roster's heavy pack), parent pack = `Data.champion_shared_packs`; the
light and skills packs were checked too. All exist for the 156 variants.
