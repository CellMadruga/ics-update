# Capturing real draw calls (RenderDoc) to finish the mesh format

The client renders with Direct3D 11 (`GraphicsCore = D3D11` in `Documents\InfiniteCrisis\UserPreferences.ini`), so
RenderDoc can capture a frame. Its vertex/index buffers are exactly what the engine decoded from the packs, which
gives the ground truth for the skinned-mesh layout and the submesh table (see the "Skinned character mesh" notes in
`reverse-engineering.md`).

1. Install RenderDoc (renderdoc.org, 64-bit build is fine for a 32-bit game).
2. `python ic.py server` in one console.
3. RenderDoc > Launch Application: executable `<game dir>\InfiniteCrisis_patched.exe`, working directory `<game dir>`,
   arguments = output of `python ic.py client-args`. Launch.
4. Log in and enter Tutorial 1 so Gaslight Batman is on screen; press F12 once (one capture). Close the game.
5. Open the capture (.rdc) in RenderDoc, Window > Python Shell, run:
   `OUT = r"C:\ic_capture"` then `exec(open(r"<repo>\tools\renderdoc_dump.py").read())`.
6. `python tools\rdoc_analyze.py C:\ic_capture --match "<game dir>\rp\0xa0000076.rp" --obj C:\ic_capture\obj`
   lists the draws (skinned first), writes OBJ files and prints where each buffer sits in the pack.

Keep the dump folder outside the repository (it contains game geometry; CLAUDE.md hard rule 1).
