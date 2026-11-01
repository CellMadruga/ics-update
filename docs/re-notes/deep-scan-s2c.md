# Deep scan: server -> client match events and notices vs what ics sends (2026-10-26)

Coverage audit of every S2C event and network notice the client handles during a match, against the `ics/` tree
of 2026-10-26 (build after fase3-hz) and `logs/traffic.log` (session 2026-10-26 16:17-19:53, Crime Alley v AI).
Builds on, and does not repeat: `sweep-s2c-match.md`, `sweep-s2c-ui.md`, `sweep-flash-hud.md`, `sweep-summary.md`,
`hud-shop-timeline-kills.md`, `announcer-and-map-elements.md`, `destructible-vehicles.md`, `end-stats-2045.md`.

Method. Client side: the local Ghidra decompilation (`C:\Infinite Crisis Server\re-work\decomp\c`, base 0x400000, all
addresses VA; REA / Ghidra were not opened, the other agents had it), the listener vtables read from the read-only
exe with pefile (`0x1605930`), and the 83 exported Flash movies (`re-work\ui-as2`). ics side: every builder of
`ics/messages.py` and its call sites in `ics/`, and the unique `>>` labels / ids of `traffic.log` (114 ids, 763
labels; extracted with grep into the scratchpad, nothing copied into the repository). Tags: **C** confirmed in code,
**P** probable, **G** guess.

---------------------------------------------------------------------------------------------------------------------

## 0. Results in short

1. **No floating damage / heal numbers and no shield bar are possible with what ics sends** (C). The client builds
   `Vitals.VitalsChanged`'s `aDamageTypes / aDamageValues / aVitalValues` and the ablative (shield) values **only from
   the 0x42 message itself**: the third list ("VOT" in earlier notes) is really the list of damage / heal events of
   this update, and the second pair list is the shield layer. ics always sends the third list empty and the second
   list zero (`World.vitals` -> `M.vitals_long(ent.eid, pairs)`). Section 1.
2. **CC floaties ("Stunned", "Rooted", "Silenced" ...) only come from the server** (C): the Flash status floaty has
   exactly three feeders, all network or server-script (0x20BD, 0x208D, 0x44, node 0x100001AD). ics sends 0x20BD only
   when a script runs node 0x100001AD / 0x100000FA (two scripts); never when it applies a CC status. Section 2.
3. **The level-up effect `_Advancement_LevelUp` 0x10000201 is never sent** (C grep; the key has no client caller,
   cinematics-vfx-audio.md 2.3, and lives in the shared champion table 0x1D0000EF). Section 3.
4. **Cast bar and channel bar have no HUD in this build** (C): no `GM_Usage` class and no `UsageNoticeIDList` in any
   of the 83 Flash movies (36 event_gen lists, 31 GM_* classes). 0x2077 / 0x20CE / 0x2096 (sent) and 0x2082 / 0x20B2
   (not sent) feed only C++ state. `sweep-summary.md` P1 #6 (channel bar) drops to P3.
5. **0x207C is not a skill-button swap** (C): it stores a per-slot tooltip number (f32 value, percent flag, format)
   that the skill tooltip formats into its text. `sweep-summary.md` P1 #7 (0x207C part) drops to P3. Section 4.
6. **0x10D / 0x138 layouts decoded** (C). Needed only for broken / moving destructible pieces; 0x8B (sent) is enough
   for intact vehicles. Section 5.
7. Crits have **no HUD marker of their own** (C: `FloatyDamageText.Animate` has only heal / strike / power / true /
   default frames). The crit is the attack's own crit scriptlet, which ics already plays.
8. Kill streaks have **no HUD widget** (C: `gameplay.combometer` / `StreakScore` are dead code, nothing links them).
   The streak "UI" is the announcer line + the client-raised kill billboard, both already sent (0x2039 with the entity
   fields). Accolades exist only on the post-match Summary (AccoladeManager listens only to end-of-match notices).

---------------------------------------------------------------------------------------------------------------------

## 1. Vitals 0x42: damage numbers, heal numbers, shields (C)

### 1.1 Wire (serializer 0x846FC0, handler 0xAB2880 -> 0xAB1BD0)

```
u8 0
cint n | n x {Vit cur, Vit max}            list 1: the vitals (index 0 Health, 1 the resource)
cint n | n x {Vit cur, Vit max}            list 2: ABLATIVE layer per vital (shield value, shield capacity)
cint m | m x Entry                         list 3: damage / heal events of this update (reader 0x975E70)
u8 hit                                      (P) "hit by an enemy" flag
Entry = u8 dmgType | u8 vitalType | u8 overTime (0/1, anything else is a read error)
        | cint k | k x Element               (list reader 0x974700)
Element (0x96E9F0) = u8 key | Vit amount16   key = (viewerIsCharacter << 7) | (viewerTeam & 7) << 4 | (sub & 0xF);
                                             amount16 = amount x 16 (fixed point 1/16, writer 0x96D360(v * 16))
```

`Vit` is the same 15-bit / long form as the vitals (ics `vital_word`); the client's reader keeps only the second
word of the long form, so keep `|amount x 16| < 16384`, i.e. |amount| < 1024 per element (C).

### 1.2 What the client does with it

- List 1 -> component +0x18 (current / max); list 2 -> component +0x50 (C, 0xAB1BD0 copies both per index).
  `VitalsChanged(iid, vitalType, oldCur, newCur, oldMax, newMax, tempCur, tempMax, ...)` gets list 2 as
  `fTempCurrent / fTempMax`; Flash `VitalBarScaling.OnUpdateVitals` calls them `i_fNewCurrentAblativeValue /
  Capacity` and draws **total = value + ablative** on the bar (C). This is the shield bar. Send list 2 with the same
  count as list 1 (the copy loop runs over list 1's count).
- List 3, per entry (C, 0xAB1BD0):
  - amount = the element value **seen by the local viewer**: for an entity the local player controls (owner chain
    0x8631A0 / 0x635200) the **sum of all elements**; otherwise the element whose key equals the viewer key built by
    0x96CBB0 from the local controlled agent: bit 7 = agent unit flags 0x1000019D & 8, team = PVP_Team 0x1000009C,
    sub = property 0x10000637 (int, default -1, meaning unknown). With the user option `User.ShowFloatyAlly`
    (DAT_01b758fe) an ally entity sums every element of the viewer's team instead (0xA9E7A0).
  - overTime = 0: if `vitalType == 0 || amount <= 0`: with `dmgType != 0` and amount != 0 ->
    `aDamageTypes.push(dmgType)`, `aDamageValues.push(round(amount))`. If `vitalType != 0 && amount > 0` ->
    `aVitalValues.push(round(amount))` (heals).
  - overTime = 1: accumulated in the DoT map (+0x70, by dmgType) or VoT map (+0x84, by vitalType) and flushed every 5th
    0x42 as `GM_Vitals.DOTUpdate / VOTUpdate` (0x909240 / 0x90A3E0).
- `VitalsChanged` is raised per vital with these arrays and the options `User.ShowFloatyDamage` / `ShowFloatyHeal`
  (DAT_0186cdfc / fd). Flash (`OverheadVitalsDeluxe` / `OverheadVitalsSimple`, every overhead bar):
  `FloatyDamageContainer.ShowDamage(types, values)`; `FloatyDamageText.Animate`: value > 0 = green heal; else by type
  1 Attack "strike", 2 Power "power", 3 TrueDamage "true", other "default". **Damage amounts must be negative**
  (an untyped amount <= 0 is reported as an error and skipped).
- Trailing u8 (P): when 1, stamps the vitals component's last-hit time (+0x68) and, for the local champion above
  15 % health, runs a 1-s throttled local hit feedback (0xA12BB0, key 0x100003AE through 0x588A00; G what it shows).

### 1.3 Recipe (P1, every hit)

- `World.damage(source, target, amount, dtype=1)`: thread the damage type (ApplyDamage's 0x1000069B / skill
  0x10000706: 1 Attack, 2 Power, 3 True, 4 Mixed) through `CastWorld.damage`; queue on the target
  `pending_hits.append((dtype, 0, 0, [(key(attacker), -absorbed_and_dealt)]))` where `key(e) = 0x80 * (e is a
  Character, unit flag 8) | (e.team & 7) << 4 | (sub & 0xF)`; the attacker = the missile's owner as `damage()` already
  resolves it. Using the attacker's key shows the number to the attacker's team (exact key) and to the victim's
  controller (sum of all); the victim's allies see it only with ShowFloatyAlly (P: the original's intent).
- `World.heal`: `(0, 2, 0, [(key(source), +healed)])` (vitalType 2 = Health).
- `World.vitals(ent)`: `M.vitals_long(ent.eid, pairs, second=[(shield_total, shield_max), (0, 0)...], vots=entries)`
  with each element amount x 16 (clamp |amount| to 1023), then clear the queue. `CombatState.shields` already holds
  [vital, amount, max, source] per handle: `second[0] = (sum amount, sum max)` for vital 2.
- Set `0x10000637 = 0` (int) on every champion in the creation bundle so `sub` is deterministic (P: an unset value
  may read as -1 and the key would never match; test both).
- `[ics] vitals_floaty_numbers = true`, `vitals_shield_layer = true`, `vitals_floaty_key = "attacker"`.
- Test: hit a minion; a red / blue number must rise over it; take turret damage, numbers over the champion; AGL E
  (AddTempVital) must show the white layer on the bar and shrink it as it absorbs.

---------------------------------------------------------------------------------------------------------------------

## 2. CC status floaties (C feeders, P trigger)

`GM_Vitals.RecvNotice_DisplayFloatyStatus (0x1000038B)` -> `OverheadVitalsDeluxe.NoticeDisplayFloatyStatus(iid,
eStatusType)` -> `FloatyStatusContainer.ShowStatus`. The C++ deliverer `0x8C2790` has exactly three callers:
`0xA0F050` (from `0xAADCD0` = event 0x44 handler path, and `0xAB4D30` = node 0x100001AD), `0xA16DD0` (event 0x208D) and
`0xA16E20` (event 0x20BD). Nothing in the client raises it when a status is applied, so the original server sent it.
`emp_gen.FloatyStatusTypeList`: 1 Silence, 2 Stun, 3 Blind, 4 KnockedUp, 5 Slow, 6 Fear, 7 Blocked, 8 Cleanse,
9 Taunt, 10 Root, 11 KnockedDown, 12 Suppressed, 13 Wounded, 14 Immune, 16 Crippled.

Recipe (P1 visible on every CC): when a status applies an attribute modifier of a CC attribute to an entity with a
vitals component, send `0x20BD u8 0 | u64 entity | u32 type` (`M.floaty_status`) to the local player:
Stunned 0x100003F3 -> 2, Silenced 0x100005A3 -> 1, Rooted 0x100007FE -> 10, Crippled 0x10000B39 -> 16, knock-up /
knock-down statuses (0x48000295 family, `0x1000096E`) -> 4 / 11, negative move-speed modifier -> 5, cleanse -> 8,
immunity -> 14 (mapping P; type values C). Once per application, not per refresh. `[ics] cc_floaty_status = {attr:
type}`.

---------------------------------------------------------------------------------------------------------------------

## 3. Level up (C absence, P effect)

`_Advancement_LevelUp` 0x10000201 has no client caller (constant only in data), sits in the shared champion script
table 0x1D0000EF that every champion's 0x7D2 list reaches, and ics never sends it (grep: 0 in `ics/`, 0 in
traffic.log). Recipe: in `World.set_level` (local) and `World.bot_level` (bots), after the level property,
`self.scriptlet(ent, 0x10000201, f"{ent.name}: _Advancement_LevelUp (0x8d)")`. `[ics] level_up_scriptlet =
0x10000201` (0 = off). The XP ring, "+" buttons and "N points" already follow 0x10000167 / 0x100001AF (C,
hud-xp-ring.md). G: `_Advancement_UltimateUnlocked` 0x1000065D at the level that unlocks R (its number collides with a
property; test by ear / eye only).

---------------------------------------------------------------------------------------------------------------------

## 4. Corrections to earlier notes

| Item | Earlier | Now |
|---|---|---|
| 0x42 third list | "VOT: regen / DoT prediction" (full-combat-skills B.1) | the update's damage / heal events, keyed by viewer; over-time entries feed DOT/VOTUpdate (1.2) (C) |
| 0x42 second list | "P: base vs temp / shield" | ablative value / capacity, drawn on the bar (C) |
| "no separate damage-number message" | correct, but the numbers are not derived from the vital delta | numbers exist only if list 3 carries entries (C) |
| 0x2082 / 0x20B2 channel bar (P1), 0x2077 cast bar | Flash Usage notices | no Flash consumer in any movie: invisible; C++ only (0xAAC620 keeps the user list, 0xA9E4E0 refresh) (C) |
| 0x207C "slot override / button swap" (P1) | skill-second-stages | `u8 0 \| u32 slot (<5) \| f32 value \| u8 percent \| u32 format (u16 used) \| u32 slot to refresh`; stored at 0x1B76008 + slot x 12, read by 0xA170D0 which formats the value (x100 if percent) into the slot tooltip (0x5A7F40) and redraws slot `refresh` (0xA39D60) (C store / P tooltip) -> P3 |
| notices 0x100000CA / 0x100000CD | "probable kill / assist" | listener vtable 0x1605930 slots 0x5C / 0x60 = 0xA0B5A0, an empty function; no other listener found -> P3 (G meaning) |
| Encounter listener 0x1605930 | partly mapped | 0x38 AddTimelineBanner 0xA488D0, 0x3C AddTimelineEvent 0xA786F0, 0x40 batch 0xA72340, 0x44 start (AF) 0xA68000, 0x48 remove (AC) 0xA48A50, 0x4C start (B1) 0xA5A240, 0x68 dialog enable (205) 0xA8EA40, 0x7C SetMatchTime 0xA902F0, 0x98 scoreboard 0xA901F0 (C) |

---------------------------------------------------------------------------------------------------------------------

## 5. Destruction 0x10D / 0x138 (C layouts)

- **0x10D** (serializer 0x4486B0 -> 0x4482B0, exec 0x697EE0, handler 0x630160 -> 0x62FB20), to the object:
  `u8 0 | u64 object IID | u32 n | n x Piece | u32 state`, `Piece` (0x4451A0, 0x3C bytes in memory) = `Position`
  (reader 0x47C610; flag 0x20 adds the orientation quaternion, which 0x62FB20 compares) `| u32 piece id (+0x2C) |
  u32 flags (+0x30 -> piece+0x194) | u32 motion (+0x34) | u32 (+0x38 -> piece+0x44, P damage stage)`. The list is the
  **complete** set of live pieces: a listed id that exists is moved to its Position (0x62C290 when the frame differs
  by > 0.0002) and gets the motion type (2 -> Havok mode 4 keyframed, 3 -> mode 3 dynamic, 0 / 4 -> mode 5 fixed;
  0xEA5E90); a listed id that does not exist is built (0x62F540 + body 0x62CFE0); **pieces not listed are detached /
  removed** (0x62EBF0). Piece ids resolve through the destruction record (0x4E1030). If the object's property
  0x8FA is true the message only clears all pieces (0x62ED50).
- **0x138** (serializer 0x4488B0, handler 0x631550): `u8 0 | u32 n | n x (u64 IID | u32 m | m x Piece | u32
  state)`: every object's piece state at join, kept in the global list 0x18628CC and applied when that object is
  built later (0x630650).
- Use: after a vehicle breaks (`0x3400015F` explosion), a 0x10D with the surviving pieces in dynamic mode (3) at the
  impact frame would let the client simulate the debris; 0x138 only for a late joiner. Ordinary match: P3 (the
  break works visually with Vfx_OnExplode + removal today).

---------------------------------------------------------------------------------------------------------------------

## 6. Coverage table (match HUD and combat feedback)

"ics" = sent in a match today (yes / no / partly), from builder + call site + traffic.log. Priority by what a player
sees in an ordinary match: **P1** every match, **P2** some kits / maps / moments, **P3** invisible or rare.

| # | Event / notice | On screen | Layout (wire, after the event id) | When the original sent it | ics | Prio | Conf |
|---|---|---|---|---|---|---|---|
| 1 | 0x42 list 3 | floating damage (red / blue / white by type) and green heal numbers over every bar | see 1.1 | every damage / heal, to everyone who sees the target | no (empty) | P1 | C |
| 2 | 0x42 list 2 | shield (ablative) layer on health bars | `cint n \| n x {Vit value, Vit capacity}` | every shield add / absorb / expiry | no (zeros) | P1 | C |
| 3 | 0x20BD | "Stunned" / "Rooted" / "Silenced" ... text over the unit | `u8 0 \| u64 entity \| u32 FloatyStatusType` | CC application | scripts only | P1 | C feeders / P trigger |
| 4 | 0x8D `_Advancement_LevelUp` 0x10000201 | level-up burst on the champion | 0x8D entry, key 0x10000201 | each level gained | no | P1 | C absence / P look |
| 5 | notice 0x10000424 + 0x100002AC | centre banners under the clock (countdown 30 / 10, initiating, drones -10 / operational, jungle) and their removal | desc `{Handle u32,u64 \| u32 sev \| u32 icon \| u32 icon2 \| u8 tint \| u32 team \| f64 time \| u8 0 \| u32 1 \| StringInfo title \| StringInfo text \| u32 audience 7}` `\| f64 now`; remove `Handle{u32,u64}` | with the countdown / wave / jungle announcer lines | no (builders exist; only timeline icons 0x100002AB sent) | P1 | C |
| 6 | 0x2188 | Summary tab accolade cards | `u8 0 \| u32 enc \| u8 ranked \| u32 champion \| StringInfo \| 5 parallel lists of equal non-zero length (u32 / u32 / u32 / {u32,u8} / u32, then u32)`; 0xA56DB0 refuses unequal lengths, 0xA61DA0 skips n = 0 | match end, with 0x2104 | empty lists | P1 (post-match) | C lengths / P field roles |
| 7 | 0x2045 rows | Scorecard / Stats tabs | end-stats-2045.md | match end | empty rows; filled rows crashed the client 2026-10-26 19:53 (end_stats_from_ledger false) | P1 (post-match) | see that note |
| 8 | attribute 0x10000A23 (via base aura) | shop / foundry button and Recommended widget only in base or while dead | 0x20F0 modifier or 0x6 | entering / leaving the base aura | forced true (`shop_anywhere`) | P2 | C client rule / P original |
| 9 | 0x2034 + 0x2009 + 0x2075 | left objective panel ("Crime Alley Clash!" rules) | ics builders `objective_list`, `objective_update` | match start | tutorial only; PvP sends tracker off at the end | P2 | C |
| 10 | 0x2143 / 0x2142 | cuts announcer / VO lines (match end, cinematic) | `u8 0 \| u8 queue` / `u8 0 \| list<u32> ids \| u8 queue` | match end, pre-empting lines | no | P2 | C |
| 11 | 0x2150 | HUD hidden / shown | `u8 0 \| u32 show` | cinematics, victory | no (0x20F5 covers the cinematic) | P3 | C |
| 12 | notice 0x10000076 | CountdownTimer sync (billboard / objective timers) | `u32 server clock` | HUD ready, match start | no | P3 | C |
| 13 | 0x0044 / 0x0043 / 0x201D | handle-tracked status floaty / removal / list | `u8 0 \| Handle \| u32 type \| u32` ... | long CC | no | P3 (0x20BD suffices) | C |
| 14 | 0x2082 / 0x20B2, 0x2077 / 0x20CE / 0x2096 / 0x20BB | (no HUD: no Flash consumer) | `u8 0 \| u64 user` / `+ u8 interrupted` | channel / cast | cast yes, channel no | P3 | C |
| 15 | 0x207C | number inside a skill tooltip | section 4 | stacking bonuses | no | P3 | C / P |
| 16 | 0x10D / 0x138 | destructible debris pieces | section 5 | piece breaks / join | no (0x8B yes) | P3 | C |
| 17 | 0x209F / 0x217F / 0x2180 | minimap targeting ring for global ults | sweep-s2c-match.md | node 0x10000022 / 0x10000056 | no | P2 | C |
| 18 | 0x20F9 | skill availability events 0x100000B6 / B7 on client skill scripts | `u8 0 \| u64 agent \| u32 slot \| u8 on` | slot usable / unusable | no | P2 | C |
| 19 | 0x2008 / 0x204E / 0x202C / 0x203D / 0x2019 | events / variables on mirrored client effects | sweep-s2c-match.md | status events | 0x2008 for structure pings only; `status_mirror` off, so moot | P3 | C |
| 20 | 0x2039 event 52 / line 215 | "victim was shut down" voice; map title voice (GD / GH / CC) | 0x2039 | shutdown kill; intro | no (config id exists, never raised) | P3 | C data |
| 21 | notices 0x100000CB / 0x100000CE | join / leave billboards | `u64 player \| u64 agent \| StringInfo \| u32 icon \| u32 team` | a human joins / drops | no | P3 (bots only) | C |
| 22 | notices 0x100000CA / CD, 0x10000059 / 4A / B6, 0x100004F7, 0x10000118 / 192 / 229, 0x100004A5 / 288, 0x100003D5-7, 0x10000414 / 364, 0x100002AE / 2B2 | unidentified (reader only; 0x100000CA / CD: no-op in the encounter listener) | full-protocol.tsv | - | no | P3 | G |

Already sent and matching the client (no action; spot-checked in traffic.log): 0x8D, 0x42 list 1, 0x6, 0x3, 0x4,
0x20F8 cooldowns, 0x20C8 / 0x20A8 / 0x20E9 / 0x20D0 / 0x2127 status icons (also on bots), 0x20F0 / 0x20E8 modifiers,
0x1000015A overlay, 0x20C9 skill events, 0x207B, 0x20A0, 0x20DC / 0x2092, 0x213D, 0x2039 / 0x202A announcer (streaks,
multi-kills, first blood, shutdown, ace, structures, under attack, core %), 0x100002EB billboards + 0x100002BC,
0x1000021C kill card (reader layout + damage ledger), 0x217A kill feed, 0x1000005B scoreboard, 0x10000090 /
0x100000BC death and respawn, 0x10000109 clock (pre-start countdown), 0x100002AF / B1 / AB timeline, 0x2069
trackers, 0x10000134 / 0x100004FB team health, 0x215C, 0x10000455 / 456 surrender, 0x100004D6 credits floaty,
0x2078 recommended, 0x20E2 for every champion (bots too), 0x218A / 0x2189, 0x2198, 0x8B, 0x1000000E.

---------------------------------------------------------------------------------------------------------------------

## 7. Top 10 recommended additions (exact recipes)

1. **Damage / heal numbers** (0x42 list 3): section 1.3. Entry bytes for a 120 Power hit by a team-1 champion:
   `02 00 00 | 01 | 90 | Vit(-1920)` (-120 x 16 = -1920 -> 15-bit form `0x7880`). Heal 50 by a team-2 caster:
   `00 02 00 | 01 | A0 | Vit(800)`. Config `vitals_floaty_numbers`.
2. **Shield layer** (0x42 list 2): `second = [(sum shield amount, sum shield max) for Health, (0, 0) for the
   resource]` on every `vitals()` while a shield exists and once more at 0 when it ends (`_drop_shield` already calls
   `vitals_changed`). Config `vitals_shield_layer`.
3. **CC floaties** 0x20BD on CC application (section 2). Config `cc_floaty_status`.
4. **Level-up burst** `_Advancement_LevelUp` 0x10000201 by 0x8D in `set_level` / `bot_level` (section 3). Config
   `level_up_scriptlet`.
5. **Centre timeline banners** 0x10000424 at -30 / -10 / 0 s and wave / jungle -10 / 0 s, removed with
   `M.pvp_timeline_remove(handle)` after 4 s; title as `(token, table)` = the caption token of the announcer line
   played at the same moment (keys 187 / 151 / 174 / 668-672, tables found by the announcer scan,
   announcer-and-map-elements.md 0), so no game text is in the server; countdown time = `clock(at)` or -1. Config
   `match_timeline_banners`.
6. **Accolade cards** 0x2188: up to 3 accolades of 0x48001242 picked by the match ledger (hud-shop-timeline-kills.md
   6.2), all five lists the same length (C, 0xA56DB0), else the client drops the whole message. Verify field roles with
   `tools\diag.py` on 0xA56DB0 before shipping. Config `match_accolades`.
7. **Shop only in base or dead**: `shop_anywhere = false` for PvP encounters (keep true for the tutorial); the base
   aura status 0x48001109 already carries the may-shop attribute, the client opens the shop when `dead ||
   0x10000A23`. Verify 0x20F0 for 0x10000A23 reaches the client on aura entry. Config `shop_anywhere_by_mode`.
8. **PvP objective panel**: at HUD ready `M.objective_list([...])` with one category and the map's rules objective
   (the encounter's objective records, as the tutorial's director does), `M.objective_tracker_enabled(True)`; update
   with 0x2009 when structures fall. Config `match_objective_panel`.
9. **Stop dialog at match end**: `0x2143 u8 0 | u8 queue` for the announcer queues (both u8 values, 0xA475C0 picks
   +0xA0 / +0x90) right before the result billboard, so a late kill line does not talk over VICTORY. Config
   `match_end_stop_dialog`.
10. **Minimap targeting ring** for global ultimates (0x209F `u8 0 | u32 | u64`, 0x217F `u32 | u8`, 0x2180 `u32`)
    from nodes ShowMinimapTargetingRing 0x10000022 / Hide 0x10000056, and **0x20F9** availability events for client
    skill scripts that wait on 0x100000B6 / B7 (HANDOFF next item 2). Lower than 1-9.

Deliberately not recommended: channel / cast bar work (no HUD), 0x207C (tooltip number), kill-streak widget (dead
code), in-match accolades (none exist), crit marker (none exists), 0x138 (no late join).

## 8. Open

- O: the role of 0x10000637 in the viewer key (default -1); test 1.3 with and without sending it as 0.
- O: what the 0x42 trailing u8 (hit flag) shows (0xA12BB0 -> key 0x100003AE through 0x588A00 on 0x6575E0's object).
- O: 0x2188 field roles of lists 2-5 (medal type, all-time-best flag, stat values) at 0xA344C0.
- O: the 17 unidentified network notices of row 22 (their C++ listeners are in vtables without RTTI; slot offsets are
  in each deliverer: e.g. 0x10000059 -> slot 0x28, 0x100000B6 -> slot 0x3C of the GM_UI notice interface).
