# Infinite Crisis preservation server

A private server for the 2015 Steam client of **Infinite Crisis** (Turbine / Warner Bros., shut down in 2015), so
the game can be played again with your own copy of it.

The server, `ics`, runs the game from the game's own data: champions, skills, maps, units and the game's server
scripts are read from your install rather than written by hand.

> Infinite Crisis is a trademark of Warner Bros. Entertainment / DC Comics. This project ships **no game files** and
> no data extracted from them, only IDs, short names and numbers. You need your own Steam copy of the game.

## Credits

- **Manuel Moreno ([@krizalidx4](https://github.com/krizalidx4))** wrote the current server: decompiling the client,
  the data-driven `ics` server, the script engine, the vs-AI maps, bots, the shop, the menus, the ID catalog and the
  reverse-engineering notes in `docs/`.
- **Eric Hardiman ([@EricHardiman](https://github.com/EricHardiman))** and **Zach ([@zperkinson](https://github.com/zperkinson))**
  built the first server: SOAP login, the key exchange and exe patches, the message format and event IDs, the menus
  and the first steps into Tutorial 1. It is kept on the
  [`archive/original-server`](https://github.com/EricHardiman/infinite-crisis-server/tree/archive/original-server)
  branch, and `tests/test_compat.py` checks that the shared messages are still byte-for-byte the same.

## Status

Latest build: **fase3-iz (2026-10-30)**. [`docs/CHANGELOG.md`](docs/CHANGELOG.md) has every build, including what
was tried and what failed; [`docs/HANDOFF.md`](docs/HANDOFF.md) has the current state and the next steps.

**Working**
- Login, lobby, queue, champion select and the rewards screen; **all 54 champions** (156 variants, including the
  ones the original game disabled), costumes and profile icons.
- **vs-AI on every map**: Crime Alley, Gotham Divided, Coast City and Gotham Heights, with structures, minion waves,
  jungle camps, stealth areas, gates, bosses and timed objectives (Raider, Leviathan, Orbital Cannon, Doomsday
  Device), the announcer, kill feed, scoreboard, surrender and end cinematics.
- **Bot champions** that lane, siege behind minions, trade, retreat, recall and shop.
- **The shop**: items change stats; Crisis Coin prices; account amplifiers.
- **Abilities from the game's own scripts**: the script engine runs all 875 of the game's server scripts with no
  unknown step; `tools/champion_check.py` tests every champion's Q/W/E/R without the client.
- **Tutorial 1** with Gaslight Batman plays through to the end (street, bridge, Super Strength, the Destroyer and the
  victory), with the gaps listed below.
- About 1,300 automated checks (see [Testing](#testing)).

**Known issues and next steps**
- Tutorial 1, bridge (tested 2026-11-01): the camera can't be unlocked, and clicking the minimap doesn't move it, so
  the "unlock the camera" and "pan to the highlighted spot" steps only pass when their timeouts run out
  (`camera_unlock_wait`). Some of the AI doesn't behave as it should.
- Some ability animations: Batman's Bat Flight, the grappling hooks of Atom and Green Lantern, and a few spawned
  objects with no script yet (Green Lantern R, Nightmare Catwoman R, Zatanna Q, Gaslight Catwoman E, Nightwing R).
- Crime Alley: turret heads vanish after a fight, and a strip in the middle of the map does not render (being
  narrowed down with `tools/diag.py --strip3`).
- The fase3-ht to fase3-iz changes (bots, bosses, Shards sphere, team tints, hover highlight) have only partly been
  tested in game.
- Planned: a configuration dashboard for game values (damage, health, speed, minions, jungle), account bans and
  turning champions on and off.
- The "Modern" client UI was removed on 2026-10-30 and will be redone from scratch (notes in
  `docs/re-notes/ui-modern-*.md`).

## Installation

1. **Python 3.11 or newer (64-bit)**, then:
   ```
   python -m pip install -r requirements.txt
   ```
2. Clone this repository anywhere; it does not need to be inside the game folder.
3. Copy `config.example.toml` to `config.toml` and set `dir` under `[game]` to your game folder (the one with
   `InfiniteCrisis.exe` and the `rp` folder).
4. Check the setup, patch the client and build the champion list:
   ```
   python ic.py doctor        checks everything and tells you how to fix each problem
   python ic.py patch         creates the server key and InfiniteCrisis_patched.exe in the game folder
   python tools\roster.py     builds data\champions.json from your install
   ```
   Re-run `python ic.py patch` whenever a build adds exe patches (the changelog says so); `doctor` reports which
   are missing.

## Usage

```
python -m ics play      starts the server and launches the patched game
python -m ics server    server only (launch the game yourself)
python -m ics skills [variant]   a champion's kit as the server reads it from the data
```

In game, log in with any name and password, then **Play Now → VS A.I.** and pick a map, or **Tutorial → Tutorial 1**.

### Logs (`logs\`)

| File | Contents |
|---|---|
| `server.log` | Every step of loading and of the match, one line each. Start here. |
| `traffic.log` | Every message with a hex dump (`[debug] hexdump`). Gets large. |
| `unhandled.log` | Messages the client sends that the server does not handle yet. This is where missing features show up. |

## Configuration

Everything lives in `config.toml` (see `config.example.toml`). The defaults, each with the date and the reason it
was chosen, are in `ics/config.py` (the `[ics]` section and the match settings) and `icserver/config.py` (game
folder, ports, key, timing). Every behaviour change has a setting, so it can be switched back from `config.toml`.

## Repository layout

| Path | What |
|---|---|
| `ics/` | **The server** (`python -m ics play`). `session.py` (one connection), `world.py` (objects, movement, fog), `gamedata.py` + `records.py` (game data), `script_model.py` + `script_runtime.py` + `script_nodes.py` (the game's server scripts), `director.py` + `encounters/` (Tutorial 1's flow), `match/` (vs-AI maps, waves, bots, bosses), `shop.py`, `account.py`, `lobby.py`, `matchend.py`. |
| `icserver/` | The earlier hand-written Tutorial 1 server, kept as a reference. `ic.py` uses it for `doctor` and `patch`, which `ics` needs. |
| `uesrv/` | **Experimental**: groundwork for an Unreal Engine 5 client (asset server, texture, mesh and Havok animation export). Not needed to play. |
| `ic.py` | Command line for setup and data lookups: `doctor`, `patch`, `catalog`, `find <text or ID>`, `layout`, `variants`, `entities`, `dump`, `carriers`. |
| `tools/` | Diagnostics and data tools: `diag.py` (+ `tracer.py`) logs what the running client does; `roster.py`, `skill_graphs.py`, `champion_check.py`, `bot_sim.py`, `script_coverage.py`, `build_catalog.py`. |
| `catalog/` | Every game ID the server uses, as `data/*.tsv` and a searchable `index.html`. Rebuild with `python ic.py catalog`. |
| `docs/` | [`reverse-engineering.md`](docs/reverse-engineering.md) (how the client works, every exe patch), `CHANGELOG.md`, `HANDOFF.md`, `AI_GUIDE.md` (where everything is), `re-notes/` (raw notes from the client decompilation; index: `re-notes/full-index.md`). |
| `tests/` | See below. |

These stay local and are kept out of the repository by `.gitignore`: `config.toml`, `keys\*.pem`, `logs\`,
`data\champions.json`, account and progress files, caches and every `.exe`.

## Testing

```
python tests\test_catalog.py                          catalog tables are well formed
python tests\test_ics.py                              the server (40)
python tests\test_session_flow.py                     login -> queue -> select -> match -> rewards -> menu (91)
python tests\test_match.py                            vs-AI maps and mechanics (608)
python tests\test_director.py                         Tutorial 1's flow (43)
python tests\test_scriptvm.py / test_graph.py         the script engine (78) and champion graphs (34)
python tests\test_shop.py / test_navmesh.py           shop (18), pathing (13)
python tests\test_meltdown.py                         Atomic Green Lantern's R and Q on a bot (77)
python tests\test_terrainfix.py [--real]              the map-pack terrain patch (33)
python tests\test_e2e.py tests\e2e.example.toml       a simulated client through the old Tutorial 1 server (178)
python tools\script_coverage.py                       how many game scripts run with no unknown step (875/875)
```

`tests\e2e.example.toml` uses other ports than the real server; adjust its paths first. `ICS_TEST_PORT` and
`SESSION_TEST_PORT` move the ports of `test_ics` and `test_session_flow`.

## Contributing

`main` is protected: changes go through a pull request approved by a code owner (see `.github/CODEOWNERS`).
`CLAUDE.md` has the project's working rules; the most important ones:

1. Never commit game files: no `.rp`, `.exe`, images or extracted game text (descriptions, dialogue).
2. Record every discovery in the catalog (`catalog/data/*.tsv`), `docs/reverse-engineering.md` and a new
   `docs/CHANGELOG.md` entry, then rebuild the catalog with `python ic.py catalog`.
3. Give every behaviour change a config default with a comment saying when and why.
