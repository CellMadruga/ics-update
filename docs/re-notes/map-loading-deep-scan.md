# Map loading deep scan: from 0x20AF to a drawn Crime Alley (2026-10-25)

Written incrementally. Scope: Crime Alley (encounter `0x40000C82`, map pack `0xA0C112BA`, packs `0xA00002E5/E6/E7`).
Tags: C = confirmed in code / data, P = probable, G = guess, O = open. Builds on `full-maps-world.md` (sections 1, 2,
5, 7), `cinematics-vfx-audio.md` 5.1, `crime-alley-visuals.md` (c), `crime-alley-video-compare.md`.

## 0. Starting facts (from earlier notes, not redone)

- ics sends **`0x956 = 0x10000016` on the player object and on the champion** (`ics/messages.py` `PLAYER_PROPERTIES`,
  `champion_properties`), a value inherited from Tutorial 1 (fase3-cd: `lighting_env = 0` left Tutorial 1 dark).
  `0x10000016` is the value **every cinematic script sets on enter** (and clears on exit) (C,
  `cinematics-vfx-audio.md` 5.1). The lighting-key reader `0x7E35C0` takes the local player's `0x956` first, so
  ics forces the cinematic lighting setup for the whole match instead of the map's own key (`0x216` of the
  block / region) (C for the code path; the visual effect is the lead for "original darker and bluer").

## 1. Lighting environment: region table, key -> env record (C) — the "darker and bluer" gap

- **Region environment table = record `0x04000000`** (pack `0xA0000038`, offset 0xAA28, ~0x300 bytes). Format (C, matches
  the lookup code): `did | 0 | f64 1.0 | f64 10.0 | default env DID 0x08000000 | 1 | count 23 | entries`; the simple
  entry is `key | key | 1 | 1 | f64 0.0 | env DID` (a few keys, e.g. `0x10000005`, carry 5 sub-entries that point
  at other keys: P time-of-day cycles). The two doubles are what `0x7EF240` copies to its +0xC8 / +0xD0 refresh
  intervals; `0x5A3570` is the hash lookup (key -> value of property `0x22E`), falling back to the default at
  region +0x30 (C).
- `0x7EF240` (`EWorldRender__UpdateWorldLighting`): region = `0x50CAF0(region id)`, env DID =
  `0x5A3570(key)`, then `0x5DFBA0(env, DB 0x2E)`; **if the record does not load the function returns before any
  sky / key light / fog / ambient is set** (C) -> black scene.
- Simple key -> env mapping read from `0x04000000` (C): `0x1000001C`->`0x0800001C`, `0x10000007`->`0x08000006`,
  `0x1000000A`->`0x08000008`, `0x1000000B`->`0x08000007`, `0x1000000D`->`0x0800000A`, `0x1000000E`->`0x0800000B`,
  `0x1000000F`->`0x0800000C`, `0x10000010`->`0x08000012`, `0x10000011`->`0x08000011`, `0x10000012`->`0x08000010`,
  `0x10000014`->`0x08000014`, `0x10000015`->`0x08000015`, **`0x10000016`->`0x08000016`**, `0x10000001`->`0x08000001`,
  `0x10000019`->`0x08000019`, **`0x10000002`->`0x08000003`**, `0x1000001A`->`0x0800001A`, `0x10000003`->`0x08000002`,
  `0x1000001B`->`0x0800001B`. The map victory-script values fit their map's packs (CC `0x1000001B` -> `0x0800001B`
  in `0xA00000D2`, GD `0x1000001C` -> `0x0800001C` in `0xA00000FC`, GH `0x1000000A/B/D` -> `0x08000008/7/A` in
  `0xA000016B`) (C).
- **Default `0x08000000` is not an environment record**: the DID in core pack `0xA0000037` is a 2 KB shader blob
  (`POSITION`, `BLENDINDICES` ... strings) (C). So with no key (no `0x956`, no block `0x216`) the DB 0x2E load fails
  and the scene is unlit: this explains fase3-cf ("`lighting_env = 0` left everything dark") (P strong).
- Crime Alley's pack `0xA00002E5` (sent) holds **two** env records, `0x08000003` and `0x08000016` (also in
  Tutorial 1's `0xA000024C`). `full-maps-world.md` section 1 "none in its packs" is wrong (C, pack id lists).
- Colour fields (ARGB words in the 440-byte records, C values, P roles):
  - `0x08000003` (key `0x10000002`): `ff040404`, sky / horizon `ff87b5ef` (light blue), `ff60382e`,
    ambient-like `ff53586f`, `ff586f86` (**blue-grey**); floats 0.5 / 50 / 150 near the top (P fog / light ranges).
  - `0x08000016` (key `0x10000016`, the **cinematic** setup): `ff201d18`, `ff99abdd`, `ff603b2e`, `ff24231c`,
    `ff262523` (warm / neutral dark); first floats 0.5 / -10 / 100.
- **Gap and fix (P, high)**: ics forces `0x956 = 0x10000016` (cinematic lighting) for the whole match. The map's
  own outdoor setup is `0x08000003`, reached with **`0x956 = 0x10000002`**; its blue-grey ambient matches the
  original's darker blue look. Recipe: make the value per encounter (`[ics] lighting_env`, Crime Alley / Tutorial 1
  = `0x10000002`), keep `0x10000016` only while a cinematic runs (the cinematic scripts set / clear it themselves via
  node `0x1000009C`; on clear (0) the reader falls back to `0x5CC` / `0x216`, i.e. darkness, so re-send the map's
  value after each cinematic). Same property on the player object (`PLAYER_PROPERTIES`) and champion
  (`champion_properties`). Tutorial 1's 2026-10-05 "lit" result with `0x10000016` proves only that a valid key is
  needed, not which.
- Env record `0x08000003` also names world states `0x2E000052` (+0x114) and `0x2E00033F` (+0x164) (C): P the sky
  objects that `0x7ED100` creates (sky dome / moon). They only appear when that record is the active one, i.e.
  never with the current `0x10000016`.

## 2. Landblock info, terrain layers (C)

- `0x810113BB` = `did | 0x0C | 0x100 | 0 | 0x0400001D | texture 0x1300274E | 2 | 3 | 1 | 3 | 256 | 256 | "DXT1" |
  0xA800 bytes` (C). The embedded 256 x 256 DXT1 is **uniform pure red** (65 522 of 65 536 texels `ff0000`): a
  one-layer blend mask, no crack / lava channel (C, decoded). The same `0x81` layout on every map (T1 `0x0400001B`,
  CA / T2 `0x0400001D`, GH `0x06000010`, GD `0x06000017`, CC `0x0A000014`; meaning of that word O).
- So the lava cracks are **not** a terrain mask in the landblock info (C), and terrain / statics are all present in
  the sent packs (earlier notes). Remaining candidates: (a) the lighting: with the cinematic env active, emissive /
  glow terms of the street material may be washed out (P, test with `0x956 = 0x10000002` first); (b) decals.

## 3. Decals (C names, P reading)

- Decal rendering is a **local render option**: console / prefs variables `Render.EnableDecals` ("Enables decals.")
  and `Render.DecalPriorityLevel` ("render priority culling level for decals"), draw pass `Decals.DrawDecals`
  (string xrefs at `0x6DFE78`, `0x6E039D`), counter `DecalsRendered`, warning "A decal is using a material that will
  not correctly render decals" (C strings). No server message touches them (C: no protocol entry names decals).
- `DecalMapType` (`DECAL_MAP_EMPTY / DECAL / DECORATION / DECORATION_BASE`, `hkdDecalMapAction*`) is the Havok
  Destruction decal map (scorch marks on destructibles), not map scenery (C names).
- Reading (P): if the cracks / craters are decals, they are drawn by the client from data (statics / terrain) and
  depend on the player's graphics setting, not on ics; the tester's client quality setting is worth checking
  (decals off at low quality would remove exactly flat ground details). Not verified further: REA calls were
  blocked during this scan (auto-mode classifier errors), so the decal source records (`0x548920` frill engine,
  terrain +0x1A4 surface table) remain O.

## 4. Pipeline summary (addresses from this scan + earlier notes)

| Step | Client function | Needs | From | ics |
|---|---|---|---|---|
| Match entry | `0xA99F00` (0x20AF) -> `0xA99E20` | encounter, pack list | server | yes (`_match_content`) |
| Encounter template | `0x8535D0`; `0x1000028A` ruleset -> `[[0x1B73518]+0xA4]+0x24`; `0x10000406` map pack | encounter record | packs | yes |
| Packs | `0xA99370` LoadParentRPs -> `0xA09E50` | named packs + packs of named DIDs | 0x20AF | yes; CA env records are in `0xA00002E5` (sent) |
| Loaded | `0xA097A0` -> client 0xCC | - | client | yes |
| Landblock | `0x548F30` -> `0x5EC890` -> `0x549510` (terrain 0x80, statics 0x82, bags `0x5921E0` / `0x592130`, nav 0x85 -> 0x90, mesh `0x53E290`, entities `0x548550`, render-only `0x5EC4F0`) | records in map pack | client | n/a (client) |
| Lighting | `0x7F3390` -> `0x7E35C0` key (player `0x956`, `0x5CC`, `0x216`, else 2) -> `0x7F2AA0` -> `0x7EF240` -> `0x5A3570` (region table `0x04000000`) -> DB 0x2E env -> sky `0x7ED100`, key light `0x64F050`, fog `0x64E4E0`, ambient `0x6509A0` | lighting key | **server (`0x956`)** | **wrong value** (cinematic `0x10000016`) |
| Map managers | `0xA6A8E0` on `0x100001D3` -> `0xA4C2C0` LoadMap (minimap `0x10000287`), shop `0xA908F0`, client 0x201A | encounter property | server | yes (patched caves M/N/S/R) |
| Music | `0xA8F890` CEncounterEnvironmentSystem (template `0x10000ADC`, CA `0x4800128C`) | team / LifeState | server state | partly |
| Ambient / switchable env objects | `0xA813F0` on `0x1000065C/D` (only if `0x10000554`) | property change | server (O who) | no |

## 5. Ranked gaps

1. **Lighting key** (C mechanism / mapping, P that it is the original's): send `0x956 = 0x10000002` (env
   `0x08000003`, blue-grey ambient, sky objects `0x2E000052` / `0x2E00033F`) on Crime Alley and Tutorial 1 instead of
   `0x10000016`; config key per encounter; re-send after cinematics clear it. Never send 0 (default `0x08000000` is a
   shader blob -> unlit).
2. **Lava cracks / ember craters** (O source): not the landblock-info mask (uniform, C); first re-test with gap 1
   (glow may be an env-dependent term, P); then check the client's decal / quality setting (`Render.EnableDecals`,
   local, P). Fallback substitute from `crime-alley-visuals.md` (c): crater world state `0x2E0004BE` + Vfx_Active (G).
3. **Map ambience objects** (P): `0x1000065C/D` environment-state changes are never sent; statics with
   `_CEntitySystem_EnvironmentStateChange` tables stay in their default state. Test `0x1000065D = n` on such a static's IID.
4. Type-3 emitter world states of Crime Alley (`0x2E00110F/1110/1118/111B/1121`) exist in no installed pack (C,
   earlier notes): unfixable from data, a probable part of the missing ambient fire / embers (G).
5. `full-maps-world.md` section 1 table must say Crime Alley / Tutorial 2 env records are in `0xA00002E5` (C).
