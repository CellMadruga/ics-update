# Crime Alley 2v2: original-game video survey (2026-10-24)

Source: a recording of an original-game 2v2 match on Crime Alley (local file, not distributed; 69.8 min,
60 fps, 1280x720). Frames were sampled with cv2 into a scratch folder (never into the repo). Tags: C = clearly
seen, P = probable, G = guessed, O = open. Times are video time (mm:ss); match timer values are quoted as shown.

Complete (sections 0-8).

## 0. What the video contains (C)

Not one match but five custom matches on Crime Alley, all with the recorder playing Katana:

| # | Mode | Video span (lobby -> load -> in game -> result) |
|---|---|---|
| M1 | Crime Alley Clash 2v2 (Gaslight Batman + Katana vs Nightmare Batman + Katana-style bots) | lobby 0:00, select 0:30, load 1:30, in game ~1:50-11:50, post-match 12:00 |
| M2 | 2v2 | lobby 12:30, select 13:00, load 14:30, in game ~14:50-24:30 (DEFEAT banner 24:30), scoreboard 25:00 |
| M3 | 2v2 (Nightmare Superman + Katana vs Atomic Green Lantern + Katana) | select 27:00, load 28:00, in game ~28:20-39:30, scoreboard 40:00 |
| M4 | Crime Alley Clash 1v1 | lobby 40:30, select 41:30, load 42:00, in game ~42:20-47:30 (core explosion 47:30) |
| M5 | 1v1 | lobby 48:00, select 48:30, load 49:30, in game ~50:00-57:00, scoreboard 57:30-69:50 (static) |

## 1. Pre-match and opening timeline, M1 (C: notice text and timer read from frames)

Load screen 1:30-1:45; intro cinematic 1:46 (camera on the blue core platform, glowing blue cylinder), 1:49 (red
core, red cylinder, "Monarch" theatre facade behind it), 1:52-1:55 close-up of the player's champion on the
street; HUD appears 1:58.

The top-centre clock counts **down** during the pre-game and then up from 0:

| Video | Clock | Notice (centre, under the top bar) |
|---|---|---|
| 1:58 | 00:40 (so the pre-game is ~45 s from world entry; first readable value 00:42 at 1:56) | - |
| 2:08 | 00:30 | "The match begins in 30 seconds." |
| 2:28 | 00:10 | "The match begins in 10 seconds." |
| ~2:38 | 00:00, the clock's timeline bar flashes green | "Match: Initiating" (2:38-2:41) |
| 2:40 | 00:02 counting up | - |
| 2:44 | 00:06 | "Drones in 10 seconds!" |
| 2:54 | 00:16 | "Drones operational!" (first minion wave leaves the bases) |
| 3:14 | 00:36 | "Jungle Creatures: Online in 10 seconds" |
| 3:24 | 00:46 | "Jungle Creatures: Phasing Complete" (camps become active) |

So: pre-game 45 s (P: maybe 60 s counting the load; the HUD clock showed 00:42 when control was given), drones at
match time +15 s, jungle at +45 s. Notices are announced only at 30 and 10 s (no 5-4-3-2-1 captions seen).

**Timeline bar** under the clock (C): a horizontal strip with a fixed "now" tick at its left end and event icons
that scroll left at constant speed (~1.7 px/s at 1280x720) and fire when they reach the tick: red X = match start
(reached the tick at 2:37), blue marker = drones (2:54), green marker = jungle creatures (3:24). A server must
send these scheduled events (the HUD reads them, P from the game's timer/objective messages).

## 2. The core mechanic of "Clash": Power Core health = team score (C)

The two long bars at the top (blue left, red right) with a number are the teams' **Power Core** health, max ~300
(first values 296/289 at match 1:22). Evidence, M1 (top bar crops):

- 4:28 -> 4:31: the player's teammate dies (portrait greys, skull + respawn countdown 0:10) and blue drops
  294 -> 219 (**-75 = 25 %** of 300); notice "Our Power Core is at 75% health." at 4:32, then kill-feed banner
  "IC_Phax claimed First Blood!" at 4:37.
- 6:55 -> 7:00: an enemy champion dies, red 234 -> 159 (-75), "The enemy Power Core is at 75% health." 7:00,
  then "Nap defeated IC_Phax" 7:05.
- Between deaths the bars also drain slowly (blue 296 -> 294 -> 214 -> 183 -> 157 -> 98 -> 17; red 289 -> 276 ->
  241 -> 141 -> 77 -> 58 over match 1:22-9:03): drones / champions damaging the lane structures and the core
  itself (P; see section 3).
- Notices fire at 75 / 50 / 25 % thresholds for both sides ("Our Power Core is at N% health." / "The enemy Power
  Core is at N% health."; the 25 % one ends with "!").
- M1 end: blue at 17, "coL_Ayuki defeated Nap" 11:47 -> core destroyed (white flash / explosion cinematic 11:52)
  -> post-match. M2 end the same way (kill 24:23, DEFEAT banner 24:29).

So a champion death costs its team 75 core points; the match ends when a core reaches 0. K/D/A counter
top-right (0/0/0 -> 0/1/0 -> 1/1/0 -> 1/2/0). Respawn timer ~10 s in the first 9 minutes (skull 0:10 at death,
M1 4:31, 7:00, 11:41 shows 0:09) — short and apparently flat (P).

Core drain detail (M1, values every 3 s): both cores sit at exactly **300** until match 0:39; the first drops
(blue 300 -> 298 at 0:39, red 300 -> 298 -> 296 at 0:42-0:45) come right after the first drone waves meet
(drones left at 0:16). After that the values fall by 1-4 points at a time while waves fight, i.e. **each drone
killed costs its own team ~1-2 core points** (P, G for the exact amount; -75 per champion is C). Structure kills
were not seen to cost a fixed chunk in M1 (O).

## 3. Minimap and map positions (C icons, G coordinates)

Minimap (bottom right, partly off-screen) scale from the core icons: core 17.5 / 142.5. Icons on the lane: blue
core, blue dot at x ~42 (dampener 40), blue dot ~67 (turret 65), red dot ~97 (turret 95), red ~121 (dampener
120), red core; base hexagon at the far left.
- A **padlock icon** at (~80, ~98) — the nook north of the lane centre — is on the minimap from the very first
  frame (2:30) and stays (5:40...). P: a locked objective / power-up spot that unlocks later (see section 4).
- **White diamond icons** at (~51, ~90) and (~113, ~90) — the two jungle passages — appear once the jungle comes
  online (right one visible at 3:23, both at 5:00): the jungle camps' minimap markers.

## 4. Jungle camps (C look, P/G positions and timing)

- **Two camps**, one per side, symmetric: minimap diamonds at ~(52, 90) and ~(113, 90) (G, +-3 m), i.e. in the
  jungle passages north of the lane, on the raised street with a parked SUV and a brick building east of it.
- **Composition (C, 7:21, 11:02, 33:30, 37:30):** one large spider-legged robot + two small robots (golden,
  outlined yellow when hovered = neutral/hostile). Each kill pops floating "+50" credits (11:02 shows two
  "+50"; 11:05 "+100" on the big one, P). Dead ones leave golden wreckage on the ground (7:30, 37:30).
- **First appearance:** "Jungle Creatures: Online in 10 seconds" at match 0:36, "Jungle Creatures: Phasing
  Complete" at 0:46; the diamonds appear at that moment (3:25). Creatures materialise with a translucent yellow
  "phase-in" look (10:57, M1).
- **Respawn (P):** M1 right-camp diamond gone 7:30 (cleared ~7:28) -> back 8:30; gone again ~9:45 -> back
  11:00 with the phase-in visual at 10:57. So roughly **60-75 s** after the camp is cleared. The minimap
  diamond is shown only while the camp is alive.
- **Interactable props:** the SUV next to the camp turns yellow when hovered (7:21, 7:24) like an enemy — an
  environment object a champion can use (P: the Crime Alley throwable/destroyable car; it later stands moved,
  11:00 vs 7:30). O: what it does; check the map's 0x4A carriers near (110, 95).
- **Locked plate at the nook:** a round platform with a spiral emblem north of the lane centre, a yellow padlock
  icon over it when hovered (7:17) and a red glowing emitter beside it (3:14, 3:24, 7:17). Matches the minimap
  padlock at (~80, ~98). It stayed locked in every match segment checked (O: unlock condition / what it grants).

## 5. Structures and the end of a match (C)

- "Our Middle Turret is under attack!" is the only structure notice during play (M1-M5, dozens of times, also
  when champions hit it). The "Middle Turret" is the lane turret (round plate with a glowing column, next to
  the purple hex strip; x ~65 / ~95 on the minimap).
- **M3, 39:15-39:16: the enemy kills our Middle Turret -> our core value jumps 128 -> 0 in the same second**,
  notice "Our Middle Turret has been destroyed!" (red banner with the killer's portrait), and the match ends.
  So in Clash the turret is the core's last guard: its death destroys the Power Core outright (C for the
  sequence, P for the rule).
- Other ends: a core reaching 0 by drones/kills (M4 47:20-47:23 blue 5 -> 0 with drones only; M1 / M5 after a
  champion death below 75).
- **End cinematic** (M3): 39:16 camera cuts to the losing team's core platform (the base's courthouse facade),
  the winners' champions standing on it; 39:17 lightning around the core; 39:21 the core sinks into a pit with a
  light shaft; 39:24 white flash; 39:27 "DEFEAT" banner (VICTORY for the winner); 39:32 post-match screen
  (Accolades, Scorecard, Stats tabs; "Back to Custom" button). ~16 s from turret death to the result screen.
- 1v1 (M4): cores start lower (195 at match 1:14, P max 200); a death still costs 75 (188 -> 113 at 44:50).

## 6. Rules panel, base gate, shop (C)

- **Objective tracker** (left edge, from world entry, M1 2:06): a "Crime Alley Clash!" panel states the win
  rule (paraphrased): destroy the enemy's outer turret, or bring their Power Core to zero; the core loses
  **1 point per 25 credits the enemy team collects** and **75 points per champion the enemy kills**. This
  explains the slow drain in section 2: core damage = enemy credit income / 25 (so drone and jungle kills,
  which pop credits, drain the opponent's core). The structure called "outer turret" here is the one the
  notices call "Middle Turret".
- **Base gate:** a tall blue light wall across the lane just east of the blue core platform (seen edge-on as a
  vertical beam, 2:30-2:38). Champions mill inside it during the countdown; it fades at 2:38.5 (clock 00:00,
  "Match: Initiating") and the player walks out at 2:39-2:42. A lane turret on a round plate stands right
  outside it (2:37-2:40). Matches `crime-alley-missing-elements.md` 1.1.
- **Shop ("Artifact Foundry")**, opened in base during the countdown (2:10-2:22): vertical tabs "Recommended"
  and "All Artifacts" on the left (the player used All Artifacts; the Recommended tab is still there at 8:35 and
  32:00, so the video does **not** show the Recommended tab disappearing after buying — O). Categories Attack /
  Health / Power / General with stat filters, prices 100-1500 on the icons, a right pane with the selected
  artifact's upgrade tree (4 tiers), Build and Salvage buttons, Credits counter. **Starting credits 750**; the
  player built a 250 -> 500 chain and ended at 0 credits (2:20). Later visits 8:35 (139 credits), 32:00 (599).
- Hold-key scoreboard overlay (56:10): per team K/D/A, Credits, Stolen Powers, Graph, Artifacts columns.

## 7. HUD "Recommended" widget, waves, income, 1v1 numbers

- **Recommended widget (HUD, above the inventory/credits box, not the shop tab):** title "Recommended", left slot
  "+ / N Point Available" (unspent skill point; shown only while one is unspent) and right slot the next
  recommended artifact with its price and a "Build" button. Seen 2:00-2:25 (in base), 5:00 and 8:35 (standing
  at our turret, minimap x ~64), 15:10-15:56, 18:15, 20:00, 28:20-29:00; **absent** in the jungle / mid-lane
  (3:20, 7:00, 8:40, 10:00, 30:00, 33:20). After buying, it does not vanish — it advances to the next item
  (2:21 shows the next tier, 500). So: it is visible while the champion is in a shop-allowed zone (base aura,
  and apparently around the own turret — P, the shop was also opened at the turret, 8:35) and shows the next
  recommended purchase. O: whether it hides once the whole recommended list is bought.
- **Waves (P):** 3-4 small drones per side per wave (teal for blue, red for red). First wave leaves at
  match 0:16 and meets the defenders around the blue turret at ~0:29-0:31 (M2 16:08, M5 51:04); a fresh
  wave is fighting again at ~1:03 (M5 51:36) -> roughly a **30 s** wave interval. Only the first wave and the
  jungle have markers on the timeline bar.
- **Starting credits:** 750 in 2v2 (shop 2:10), **1000 in 1v1** (scoreboard 50:40). Passive income about
  +10 credits per 8 s (1000 -> 1009 -> 1019, 50:40-50:56; P ~1.25/s).
- **1v1 cores start at 200** (50:40, C), 2v2 at 300. A champion death costs 75 in both.
- **Stealth brush (hex strips):** flat purple hexagon fields; one along the lane's south edge just east of
  each turret (~8-10 m long, 2-3 m deep, 16:02, 51:04), and L-shaped / curved strips at the jungle mouths
  (2:43, 7:30, 11:00, 30:00, 39:10). A champion inside one is drawn translucent (16:08). Matches the earlier
  survey (status `0x4800028C`).
- **Red-veined rock with a glowing red orb** on the lane edge next to each turret (15:56, 16:08, 51:04) and
  near the locked nook plate: static scenery (P: already a client static; check the 0x13BB list if absent).

## 8. Ranked server tasks from this video

1. Clash scoring: core 300 (2v2) / 200 (1v1); -75 per champion death; -1 per 25 credits the enemy collects;
   match ends at 0. Threshold notices 75/50/25 % for own and enemy core. (C)
2. Turret death = instant core loss (128 -> 0) + "Our Middle Turret has been destroyed!" banner, then the core
   cinematic and VICTORY/DEFEAT (~16 s to the result screen). (C)
3. Pre-game: clock counts down 45 s (shows 00:42 at control), notices at 30 and 10 s, "Match: Initiating" at 0,
   base gate wall removed at 0, clock then counts up. (C)
4. Scheduled events on the timeline bar: drones at +15 s ("Drones in 10 seconds!" at +5, "Drones operational!"),
   jungle at +45 s ("Jungle Creatures: Online in 10 seconds" at +35, "Phasing Complete"). (C)
5. Two jungle camps (~(52, 90), ~(113, 90)): 1 big spider robot + 2 small robots, credit pops (+50/+100),
   phase-in visual, minimap diamond while alive, respawn ~60-75 s. (C look, P numbers)
6. "Our Middle Turret is under attack!" notice (throttled, seen every 30-60 s while hit). (C)
7. Kill feed banners: "X claimed First Blood!", "X defeated Y"; respawn ~10 s; K/D/A counter. (C)
8. Recommended HUD widget shown only in shop zones; starting credits 750 / 1000; passive income ~1.25/s. (C/P)
9. Waves 3-4 drones every ~30 s. (P)
10. Open: the locked nook plate (padlock) — never unlocked in 5 matches; the hover-highlighted SUV prop near the
    camps.

Announcer audio was not analysed (no audio pass); every caption above is on-screen text, and the original
announcer lines are expected at the same moments.
