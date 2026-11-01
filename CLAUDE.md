# CLAUDE.md — Infinite Crisis preservation server

Read this first, then `docs/HANDOFF.md` (current state and pending work) and `docs/AI_GUIDE.md` (where
everything is). The whole client is decompiled: `docs/re-notes/full-index.md`. Everything in the repository is written in **English**.

## Working with the user

- **Reply to the user in Spanish.** Code, comments, docs, commit messages and the catalog stay in English.
- The user tests in the real game client on this Windows machine and sends back `logs\server.log`,
  `logs\traffic.log`, `logs\unhandled.log` and, when asked, `logs\diag.log` (from `python tools\diag.py ...`,
  run in a second console while the game is open). Screenshots describe what is wrong on screen.
- Never ask the user to do something you can check yourself in the code, the logs or the catalog.

## Hard rules

1. **Never distribute game files**: no `.rp`, no `.exe`, no images, no extracted game texts (descriptions,
   dialogue). IDs, short names and numbers are fine (they make up the catalog).
2. Do not commit: `data/champions.json`, `data/progress.json`, `data/stolen_powers.json`, `keys/*.pem`,
   `logs/*`, `config.toml`, `__pycache__/`, `*.pyc` (see `.gitignore`).
3. **Every discovery is recorded in three places**: the right catalog table (`catalog/data/*.tsv`, with a short
   English description and a `server_status`), `docs/reverse-engineering.md` (how it works, addresses,
   evidence) and `docs/CHANGELOG.md` (a new `## fase3-xx` entry per build: what the tester reported, what changed,
   config keys). Then `python ic.py catalog` to rebuild `catalog/index.html`.
4. Every behaviour change gets a `config.py` default with a comment (date/time of the tester's report and why), so
   it can be switched back from `config.toml`.
5. Exe patches live in `icserver/patcher.py` (original and new bytes are checked); after changing them the user
   must run `python ic.py patch`.

## Layout

| Path | What |
|---|---|
| `ics/` | **The new, data-driven server** (`python -m ics play`): `session.py`, `world.py`, `gamedata.py`, `records.py` (any record by property kind), `script_model.py` + `script_runtime.py` (the server-script VM), `director.py` + `encounters/` (an encounter's flow), `shop.py`, `config.py` (`[ics]`), `match/` (PvP maps and mechanics), `account.py` / `lobby.py` / `chat.py` / `matchend.py` (menus, queue, champion select, rewards), `combat.py` + `script_nodes.py` (script VM nodes). New work goes here |
| `ic.py` | CLI of the old server: `doctor`, `patch` (also needed by `ics`), `server`, `play`, `catalog [--scan]`, `find <text or ID>`, `stolen-powers [text]`, `layout`, `variants`, `entities`, `dump`, `carriers` |
| `icserver/` | The old, hand-written server (Tutorial 1); kept as a reference |
| `icserver/session.py` | One login session: phases, lobby/loading, object creation, every client event handler (`HANDLERS` at the end), the Match class (champion bundle, ranks, Stolen Power slots) |
| `icserver/tutorial1.py` | Tutorial 1 part 1 (street), HUD ids, knockdown, props built on carriers, prop scriptlet tables |
| `icserver/bridge.py` | Part 2 (the bridge): camera (D), gates, Bat Scream, `start_at` shortcuts |
| `icserver/finale.py` | Part 3: Super Strength (lift / carry / throw / explosion), Destroyer, victory, match end |
| `icserver/batman.py`, `abilities.py` | Gaslight Batman's Q/W/E/R and cooldowns |
| `icserver/messages.py`, `scorecard.py`, `wire.py` | Message builders and wire format |
| `icserver/skilldata.py`, `stolenpowers.py`, `gamedata.py`, `rp.py` | Reading the game data from the player's install (records, kinds, English strings, packs) |
| `icserver/config.py` | Every setting with its default and the reason for it |
| `tools/diag.py` + `tools/tracer.py` | Breakpoint logger for the running client (`--scripts`, `--skills`, `--reward`, `--replay`, `--props`, ...) |
| `tools/build_catalog.py`, `tools/catalog_scan.py` | The ID catalog page and the full-install scanner |
| `tools/roster.py` | Rebuilds `data/champions.json` (54 champions, 156 variants) from the champion definitions |
| `catalog/` | `data/*.tsv` (source of truth) and the generated `index.html` |
| `docs/` | `reverse-engineering.md`, `CHANGELOG.md`, `AI_GUIDE.md`, `HANDOFF.md`, `re-notes/` (raw static-analysis notes with exe addresses) |

## Testing

- `python tests\test_catalog.py` — catalog tables are well formed.
- `python tests\test_e2e.py tests\e2e.example.toml` (178 checks) and `python tests\test_jump.py tests\e2e.example.toml`
  (24) — a simulated client against the server; adjust the paths in the example config first. They use other
  ports than the real server.
- `python tests\test_ics.py` (40), `python tests\test_director.py` (43, the tutorial's flow), `python tests\test_shop.py`
  (18), `python tests\test_navmesh.py` (13), `python tests\test_scriptvm.py` (78) and `python tests\test_graph.py` (34)
  — the new server, its flow, shop, navmesh paths, script VM and the champions' behaviour graphs.
  `python tools\script_coverage.py` — how many scripts its runtime runs with no unknown node (875/875).
- `python tests\test_match.py` (608, PvP maps and mechanics), `python tests\test_meltdown.py` (77, AGL's R and Q on a still /
  walking bot) and `python tests\test_session_flow.py` (91, login -> queue -> select -> match -> rewards -> menu).
  `ICS_TEST_PORT` / `SESSION_TEST_PORT` move the ports of test_ics / test_session_flow.
- `python tests\test_terrainfix.py` (33; `--real` adds 3 on copies of the installed packs) — the map-pack terrain patch.
  `python tools\champion_check.py --vs-champion --window 5 --out <json>` — every champion's kit headless (verdict and
  damage per slot); compare with the previous build's JSON.
- The Modern client UI code was removed on 2026-10-30 (archived outside the repo); its findings stay in
  docs/re-notes/ui-modern-*.md and the design canvas https://claude.ai/artifact/AM81tAMYhGA9J4o8huiddu. It will be redone from scratch.
- Then the user tests in the game. Build tags continue from `fase3-iz` (next: `fase3-ja`).

## Facts that are easy to get wrong

- Two name tables: scriptlet keys (`0x33000000`, run with event `0x8D`) and animation-graph events (`0x300000A4`,
  raised with scriptlet `0x100001E3` + script variable `0x780` = event id). The same number means different things.
- A prop built on a carrier class (`0x4A......`) only accepts scriptlets if it gets its world state's templates
  (property `0x7D2` + graph `0x5B5`); they are read from the packs at server start.
- Skill stats: 3 = cost (Will, negative), 5 = damage, 15 = cooldown, 18 = range, 22 = missile width / radius, 30 = missile speed (probable).
- World state records: `did | 7 | .entity | 0 | count | entries`; other records: `did | 0 | count | entries`.
