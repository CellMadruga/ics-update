# Handoff — state at build fase3-ht (2026-10-25)

## Where ics stands
- Every v AI map plays (Crime Alley, Gotham Divided, Coast City, Gotham Heights): structures in protection order,
  waves, camps, stealth strips, gates, auras, announcer lines and events (0x2039), kill feed, scoreboard, rewards,
  surrender, end cinematics. Lighting key 0x956 per map; connection watchdog patched (`python ic.py patch`).
- fase3-ht (not yet tested in game): **bot champions on the map** (`World.create_bot_champion`, brain in
  `ics/match/bots.py`, `tools/bot_sim.py`); **bosses and scheduled objectives** (`ics/match/bosses.py`: CA Raider, GD
  pods / Raider / Leviathan / beacons, GH Orbital Cannon, CC Doomsday Device capture + strike, kill buffs, kept
  dampener bodies, jungle drops from their own scripts); status stacking; team tint as a change; Shards sphere;
  stealth tile mesh; Meteor Drop / Teleport / Super Strength lift and throw stage; Stolen Power versions unlocked
  (level 5 floor); SetSlotSkill, +Y local frames, stat scaling, chains, more raised events (recipes 2-7).
- Script VM: 875/875 scripts with no unknown node; champion_check (54 champions x Q/W/E/R) BUFF 14, CHMP 12, DMG 137,
  FX 103, REF 4 before the recipes; BUFF 16, CHMP 12, DMG 141, FX 98, REF 3 after.

## Next (in order)
1. The tester's report on fase3-ht: bots (nameplate, targeting, run animation with motion-only states, skill
   visuals), bosses, the dampener / gate tint, the Shards sphere.
2. The rest of skill-mechanics-recipes.md 6 (events still never raised: 0x100000B6 / B7 slot unavailable, 0x100000AF
   effect applied, 0x100000B3 blocked, the lifesteal / vital / CC events) and 7 (spawned objects with no candidate
   script: Green Lantern R, Nightmare Catwoman R, Zatanna Q, Gaslight Catwoman E, Nightwing R).
3. Open items listed at the end of the fase3-ht CHANGELOG entry (Trap trigger, Super Strength throw, stage / end graph
   events, 0x100006FE multiplier probe, usable pads' message, rubble rocks, CA relay).

# Earlier: state at build fase3-fy (2026-10-21)

## Direction now
The user asked (2026-10-21) for a **new server that runs the game from its own data**, with as few hand-written
adjustments as possible: `ics/` (`python -m ics play`). The old server (`icserver/`, below) stays as a reference;
new work goes to `ics/`. The project lives in `C:\Infinite Crisis Server\server`; the game copy is its parent folder
(`C:\Infinite Crisis Steam` belongs to another chat: do not touch it). The user wants everything found and built:
shop, inventory, augments, maps, every champion (also the "disabled" ones).

## Where ics stands
- Surveys of the whole client data are in `docs/re-notes/` (index: `master-plan.md`).
- fase3-fy (not yet tested in game): props placed (movement module + 0x50F = 8), scriptlet tables read from the
  packs, the tutorial's whole flow (`ics/director.py` + `ics/encounters/tutorial1.py`), unit and champion stats from
  their records, skill ranks with the patched "+", XP / levels outside a flow, Stolen Powers D / F, the shop
  (`ics/shop.py`), respawn notices, all 54 champions (`tools/roster.py`) and lobby pick, the play menu from the data.
- Tests: test_ics 27, test_director 17, test_shop 16, test_scriptvm 13, test_catalog.

## Next for ics (in order)
1. The tester's run of fase3-fy: props visible? doors' light walls? the flow's pacing and positions; the shop
   (0x20E2 / 0x2086 answers); D / F; the respawn panel; the login with 54 champions (`[ics] roster_limit` if not).
2. Master plan step 7: amplifier sets (0x2090, 0x20C7, 0x2052, 0x204A; client 0x200D / 0x20FC).
3. Step 8: PvP maps: structures at authored positions from the anchors (maps-encounters.md), minion waves, the
   capture point; bots from the encounter's pool (0x10000B3E).
4. More script nodes (`tools/script_coverage.py`); the 3 undecoded skill scripts 0x3400077A, 0x34000777, 0x340007A2.
5. Open: the actor key format of 0x20F5's binding list; who creates the client script class 0x233 (rank queries).

# Earlier: state at build fase3-fm (2026-10-16), the old server

Moving from the cloud chat to Claude Code on the user's machine. Read `CLAUDE.md` first.

## Goal
Finish **Tutorial 1** with all of Gaslight Batman's animations, actions and interactions.

## Confirmed working in game
- Full tutorial flow: street, bridge, finale, victory, Champion Unlocked banner, showcase movie.
- Replay of the tutorial (`0xEB` local player resent before each later match).
- HUD: basic attack and passive in colour, D places a Surveillance Camera at the cursor.

## Shipped in fase3-fm, NOT yet verified by the user
- Car carried centred on Batman (`CARRY_ORIGIN`, `carry_height` 2.1), throw arc + spin, F swapped to the throw
  skill `0x480003C9` while carrying (aim ring).
- Scriptlet `0x5` on the car for the explosion fire.
- Sphere / props scriptlet tables resolved automatically from world states (`tutorial1.resolve_script_tables`).
- Camera max range 10 m: Batman walks into range before placing (`bridge.camera_tick`).
- Knockdown always face-down (graph events Knockdown → Dead → GetUp).
- Victory voice line: conversation `0x250`.
- Second car moved back 1.6 m (`car_extra_back_shift`).

## Open work (in order)
1. Get the user's logs for fase3-fm and fix whatever above did not work.
2. **Explosion fire**: if `0x5` is not enough, spawn the destructible world state `0x2E00134F` (analog
   `0x1D0008EF`) at the impact point and run keys `0x10000078` / `0x10000016` / `0x10000079`.
3. **Emotes** (Ctrl+1..4): the input actions and graph events are known (catalog `emotes`), the client's wire
   event is not. Ask the user to press Ctrl+1..4 in game and send `logs/unhandled.log`.
4. Correct `icserver/abilities.py` cooldowns to the stat-15 values: Q 5 s, W 8 s, E 20 s (−2 per rank),
   R 110 s (−10 per rank). It still has the old guesses 9/12/14/80.
5. Skill animations for Q/W/E/R (phase 2 of the user's plan).
6. Aesthetics: meteor fall, craters, dust, the sphere that falls and opens (phase 3).
7. Champion base stats.

## Notes
- The heavy reverse-engineering artifacts from the cloud session (full disassembly, extracted packs) were not
  transferred. Regenerate what you need locally from `C:\Infinite Crisis Steam` (read-only; never copy game files
  into the repo). Addresses and findings are in `docs/re-notes/*.txt` and `docs/reverse-engineering.md`.
- `catalog/index.html` is the quickest way to look up an ID; `python ic.py find <text|id>` does the same in the
  console.
