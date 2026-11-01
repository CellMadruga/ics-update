"""Rebuild data/champions.json (the account's champion roster) from the game data.

Every champion variant (base or costume) is an entity 0x40xxxxxx whose definition, the twin 0x49xxxxxx
("did | 4 | count | entries"), has template 0x1000048B = 0x48000732 and names everything the client needs
(docs/re-notes/champions-all.md section 2): light record 0x100005E7, pregame record 0x100005E6, skill set 0x100005E9,
own pack 0x1000035C, shared pack 0x10000730, light pack 0x100005E0, wallpaper pack 0x100005DF, skills pack 0x10000B0D.
Variants with the same skill set are one champion; the base is the one whose light record has the champion-select
voice 0x10000575 (else the lowest DID).

The earlier extraction (old_files/tools/champions.py) kept only the light records with 10 or 12 properties: it
dropped 11 champions (Deadshot, Deathstroke, Nightwing, Raven, Zod ...) and took a stats record for the variant in
14 entries (2026-10-21). The file stays local (.gitignore): it holds the game's names.

    python tools\\roster.py            write data/champions.json (the old one is kept as champions.json.bak)
    python tools\\roster.py --check    only compare with the current file
"""
import json
import os
import re
import shutil
import struct
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
from ics import config, records as R          # noqa: E402
from ics.gamedata import Data, pack_header     # noqa: E402
from icserver import gamedata as gd            # noqa: E402  (string tables)

CHAMPION_TEMPLATE = 0x48000732
P_TEMPLATE, P_NAME, P_SKIN = 0x1000048B, 0x10000433, 0x1000077F
P_LIGHT, P_PREGAME, P_SKILLS, P_HEAVY, P_PARENT = 0x100005E7, 0x100005E6, 0x100005E9, 0x1000035C, 0x10000730
P_LIGHT_PACK, P_WALL_PACK, P_SKILLS_PACK = 0x100005E0, 0x100005DF, 0x10000B0D
P_SMALL_ICON, P_MINI_WALL, P_GRID_ICON, P_WALLPAPER, P_SELECT_VO = 0x10000384, 0x10000799, 0x1000072E, 0x100005B0, \
    0x10000575
PACK_VARIANT = 7


def clean(name):
    """A string table's grammar tag ("Batman[mn]", "Raven [fn]") off."""
    return re.sub(r"\s*\[[a-z]{1,3}\]\s*$", "", name or "").strip()


def variants(data):
    """[twin entries] of every champion variant."""
    out = []
    for name in sorted(os.listdir(data.rp_dir)):
        if not name.endswith(".rp"):
            continue
        path = os.path.join(data.rp_dir, name)
        try:
            with open(path, "rb") as f:
                head = f.read(8)
            if struct.unpack_from("<I", head, 4)[0] != PACK_VARIANT:
                continue
            ids = pack_header(path)[1]
        except (OSError, struct.error):
            continue
        for did in ids:
            if did >> 24 != 0x49 or (0x40000000 | (did & 0xFFFFFF)) not in ids:
                continue
            e = data.record(did)
            if e and R.get(e, P_TEMPLATE) == CHAMPION_TEMPLATE:
                out.append((0x40000000 | (did & 0xFFFFFF), did, e))
    return out


def build(data, game):
    groups = {}
    for variant, twin, e in variants(data):
        light = R.get(e, P_LIGHT) or 0
        lrec = data.record(light) or []
        pre = data.record(R.get(e, P_PREGAME) or 0) or []
        v = {"variant": variant, "heavy_dbpc": twin, "light": light, "pregame_heavy": R.get(e, P_PREGAME) or 0,
             "heavy_pack": R.get(e, P_HEAVY) or 0, "parent_pack": R.get(e, P_PARENT) or 0,
             "light_pack": R.get(e, P_LIGHT_PACK) or 0, "wallpaper_pack": R.get(e, P_WALL_PACK) or 0,
             "skills_key": R.get(e, P_SKILLS) or 0, "skills_pack": R.get(e, P_SKILLS_PACK) or 0,
             "tex384": R.get(lrec, P_SMALL_ICON) or 0, "tex799": R.get(lrec, P_MINI_WALL) or 0,
             "grid_icon": R.get(e, P_GRID_ICON) or R.get(lrec, 0x100001FC) or 0,
             "wallpaper": R.get(pre, P_WALLPAPER) or 0,
             "name": clean(game.text(R.get(e, P_NAME)) or game.text(R.get(lrec, P_NAME))),
             "skin": clean(game.text(R.get(e, P_SKIN)) or game.text(R.get(lrec, P_SKIN))),
             "select_vo": R.get(lrec, P_SELECT_VO) is not None}
        groups.setdefault(v["skills_key"], []).append(v)
    roster = []
    for skills, vs in groups.items():
        vs.sort(key=lambda v: (not v["select_vo"], v["variant"]))
        base, costumes = vs[0], vs[1:]
        c = {"name": base["name"] or f"Champion {base['variant']:#x}", "id": base["light"],
             "costumes": [s["light"] for s in costumes]}
        for k in ("tex384", "tex799", "light_pack", "variant", "heavy_pack", "parent_pack", "heavy_dbpc", "wallpaper",
                  "wallpaper_pack", "pregame_heavy", "skills_pack", "skills_key", "grid_icon"):
            c[k] = base[k]
        c["skin"] = base["skin"]
        c["costume_info"] = [{"light": s["light"], "light_pack": s["light_pack"], "variant": s["variant"],
                              "heavy_pack": s["heavy_pack"], "heavy_dbpc": s["heavy_dbpc"], "wallpaper": s["wallpaper"],
                              "wallpaper_pack": s["wallpaper_pack"], "pregame_heavy": s["pregame_heavy"],
                              "grid_icon": s["grid_icon"] or base["grid_icon"], "skin": s["skin"]} for s in costumes]
        roster.append(c)
    roster.sort(key=lambda c: c["name"])
    return roster


def main():
    cfg = config.load()
    data = Data(cfg.game_dir)
    game = gd.Game(os.path.join(cfg.game_dir, "rp"))
    roster = build(data, game)
    path = os.path.join(ROOT, "data", "champions.json")
    old = []
    if os.path.isfile(path):
        with open(path, encoding="utf-8") as f:
            old = json.load(f)
    old_variants = {c["variant"] for c in old} | {s["variant"] for c in old for s in c.get("costume_info", [])}
    new_variants = {c["variant"] for c in roster} | {s["variant"] for c in roster for s in c["costume_info"]}
    print(f"{len(roster)} champions, {len(new_variants)} variants (the current file: {len(old)} / {len(old_variants)})")
    added = sorted({c["name"] for c in roster} - {c["name"] for c in old})
    if added:
        print("  new champions: " + ", ".join(added))
    fixed = sorted(old_variants - new_variants)
    if fixed:
        print("  variant DIDs of the current file that are no champion variant: " + " ".join(hex(v) for v in fixed))
    if "--check" in sys.argv:
        return 0
    if os.path.isfile(path):
        shutil.copyfile(path, path + ".bak")
    with open(path, "w", encoding="utf-8") as f:
        json.dump(roster, f, indent=1)
    print(f"written {path}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
