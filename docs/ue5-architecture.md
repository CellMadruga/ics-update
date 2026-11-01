# UE5 migration: architecture (draft, step 1)

Private, personal-use project. Game assets are read from the owner's own install and are **never committed**
(CLAUDE.md hard rule 1). They are served only to authenticated clients of the owner's own server.

## Principles

- The Python server is the single source of truth: accounts, progress, catalog, rules (skills, stats, shop),
  match state. The UE5 client only renders, sends input, shows UI and plays animations.
- A new, versioned protocol (not the original Turbine one). The legacy server (`icserver/`) keeps working for the
  original client until the new stack replaces it.
- Assets are converted once by the server (`assets/` cache, git-ignored) and downloaded by the client on demand,
  then cached locally. The client package contains no game data.

## Components

| Component | Role |
|---|---|
| `uesrv/` (new) | New server: auth, profile, catalog API, asset service, later match simulation |
| `tools/export_*.py` (new) | `.rp` -> PNG/DDS (textures first), later meshes/skeletons/animations |
| `ue5/` (later, separate UE project) | Thin client; connects, downloads assets, renders |
| `icserver/` (existing) | Legacy server and rule logic (Tutorial 1, Batman); logic is reused, not rewritten |

## Transport (proposal)

- Control channel: TLS-less TCP (LAN) with length-prefixed JSON messages `{v, type, id, payload}`.
- Asset channel: HTTP GET `/asset/<kind>/<did>` with a session token, `ETag` = content hash.
- Real-time match state (phase 4+): UDP or the same TCP at first; decided when gameplay starts.

## Steps

1. Server base: protocol, auth, profile, asset service, texture exporter. Testable with a Python test client,
   no Unreal needed.
2. Login + home in UE5 against that server.
3. Maps + loading. 4. Characters + animations. 5. Gameplay (Tutorial 1 first). 6. Shop + stats.
