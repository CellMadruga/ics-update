# Timeline tooltip pictures and the jungle's 30-second phase-in (2026-10-30)

Tester 2026-10-30 13:18 (Crime Alley run 13:05-13:18): (1) hovering a mark of the timeline strip under the clock
shows a black box with only the countdown; the original also shows the picture of what comes (a drone for the drones'
arrival, a jungle creature for the jungle); (2) the jungle creatures' spawn effect must show from the "Online in 30
seconds" announcement, and with about one second left the creatures appear. Sources: Flash AS2
(`re-work/ui-as2/c_a00000d0_02189b08`, movie pack `0xA00000D0`, read only), the decoded server script
`data/script_trees/340002cf.json`, the player's install through `ics.gamedata` (nothing copied). Tags: **C**
confirmed, **P** probable, **G** guessed, **O** open.

## 1. What the strip's tooltip reads (C)

- `gameplay.eventTimer.timeline.TimelineEvent.ShowTooltip` -> `TooltipManager.ShowEventTimelineTooltip(mc, data)` ->
  `gameplay.tooltips.EventTimelineTooltip.SetData(TimelineEventData)`:
  - `m_wtTitle.Text = siEventTitle` (tinted by severity: Low 0x66FF00, Medium 0xFFFF00, High 0xFF0000);
  - `m_wtDescription.Text = siEventDescription`;
  - **`m_IconContainer.SetIcon(didExaminationIcon)`** = the picture;
  - the countdown (`m_gnTimer`, ticked by the match timer) = `ttEventTime - game time`, hidden at 0.
- `TimelineEventData(iidHandleIID, nHandleID, eSeverity, didTimelineIcon, didExaminationIcon, bTintTimelineIcon,
  iOwningTeam, siEventTitle, siEventDescription, ttEventTime)` comes from notice `0x100002AB`: descriptor `[5]` =
  `didTimelineIcon` (the strip's own icon; 0 = the default button in the severity's colour), `[6]` =
  **`didExaminationIcon`** (the tooltip's picture), `[7]` u8 tint, title / description = the entry's two StringInfos.
- ics sent `[5] = [6] = 0` and empty strings: the tooltip had no picture and no title, only the countdown (the
  tester's black box).

### 1.1 What the original put there (C data)

The only server script that builds these descriptors is the Gotham Heights cannon controller `0x340002CF`, node
`0x1000011A` ShowAnnouncement (fields: severity @+0x9C6FF4 reader, timeline icon @0x9C7006, examination icon
@0x9C7018, tint u8 @0x9C702A, audience 7). Its instances: severity 2, strip icon `0x130029AD`, examination icon
**`0x130016CD`**, tint 1; severity 1, strip `0x130029C4`, examination `0x13000AFE`; several with examination
`0x13000AFE` only. `0x130016CD` is the Character_Billboard_Icon (`0x100001FC`) of the super drone `0x40000EAA`: the
tooltip's picture is a unit's billboard portrait, the same image the kill banner uses. The drone / jungle events of
Crime Alley have no script (the C++ map rules), so their DIDs are not in data; we use the same rule (P).

### 1.2 What ics sends now

`[ics] match_timeline` entries take `icon` (the tooltip picture), `strip_icon` (descriptor `[5]`, absent = the default
marker as before) and `title` (our own words). `icon` is an image DID or a source read from the data at run time
(`Match._timeline_icon`): `"melee"` / `"ranged"` / `"siege"` = the map's drone class, `"camps"` = the first camp's
first unit, `"raider"` = `match_raider[map].cls`, or a class DID; the class's template `0x100001FC` (fallback
`Data.record_u32` on `0x49......`, which the template reader misses for the Raider).

| Event | at | severity | tooltip picture (CA) | title |
|---|---|---|---|---|
| start | 0 | 1 | none | Match start |
| drones | match_waves first | 2 | `0x13000F9D` (melee drone `0x40000BF8`) | Drones |
| jungle | camps first (45 s CA) | 3 | `0x13001A37` (Tripod `0x40000CA0` / Heavy `CA1`) | Jungle Creatures |
| raider (new) | match_raider at (300 s CA, G) | 2 | `0x13001A37` (Raider `0x40000CA2`) | Raider |

Ranged drone `0x40000BFA` = `0x13000F9C`, siege `0x40000BF9` = `0x130020DB` (C). `[ics] match_timeline_icons = false`
sends icons 0 (fase3-ir). Handles stay 900 + index of the sorted names (the Raider shifts "start" from 902 to 903).

O: the original's small strip icons for these events (the cannon used `0x130029AD` / `0x130029C4`); whether a
billboard portrait fits the tooltip's container size (P: the same container class as the other tooltips).

## 2. The jungle's 30-second phase-in (tester's rule, P against the video)

- The phase-in is `Vfx_Spawn_Alt01` of table `0x1D000674` (jungle-camps-spawn.md 1): a persistent type-8 render effect
  (yellow wireframe overlay `0x17001445` + sparkles) that lasts while its run lives; ics ends it with a signal at
  "phasing complete". No separate camp spawner object or pre-spawn portal exists in the CA data (the jungle classes'
  tables hold only Vfx_Spawn_Event01..04 / Alt01 / Alt02; C, crime-alley-jungle.md 3).
- So the first camps now **spawn in their phase-in at the jungle time + `match_camp_prespawn_from` (-30 s = the
  "Online in 30 seconds" line 673)** and complete it **`match_camp_prespawn_appear_before` (1 s) before the jungle
  time** (line 671 "Phasing Complete"): the wireframe shows for 29 s, then the creatures are solid, targetable and
  attackable. While phasing they are invulnerable, unprovoked, flags held, re-sent after a full bundle (unchanged
  machinery, `Match._spawn_camp` / `_camp_phase_end`). The phase length is computed from the absolute end time, so
  a late timer still ends on time.
- Respawns have no announcer countdown (the jungle lines play once), so they keep `match_camp_phase_seconds` (3 s,
  the video's 590.4 -> 593.6 s).
- `match_camp_prespawn_from = 0` restores `match_camp_phase_lead` (3 s before the line).
- The 2v2 video shows only ~3 s of wireframe on a respawn; the first spawn's look between 0:15 and 0:45 was not
  checked frame by frame (O). The tester's report is the rule here.
- O: the camp's minimap diamond (heavy creature's note, `match_camp_map_notes`) goes with the creation bundle, so it
  now shows from -30 s; the original showed it at "Phasing Complete" (crime-alley-2v2-video.md 4). If the tester
  objects, hold `0x100004DA` / `0x2A1` until the phase end.
- O: the Raider (bosses.py, lines 696 / 699 at -30 / -10) still spawns at its time with `Vfx_Spawn_Event01`; the same
  pre-spawn could apply if the original did it.

## 3. Tests

`tests/test_match.py`: tooltip pictures and titles per event, the Raider's mark at 300 s, the switch-back; camps none
before -30 s, phasing from -30 s, still phasing at -1.5 s, solid at -0.75 s, and the 3 s lead with the key at 0.
