"""Busca en TODOS los paquetes del juego (rp\\*.rp) los scripts de lógica de juego.

La lógica de habilidades / progresión del cliente son scripts Lua que el
servidor manda iniciar. No están en los 6 paquetes que ya revisé, así que este
programa recorre los ~600 paquetes y anota cuáles contienen señales de scripts.
Solo lee; no modifica nada.

Uso:
    python tools\\buscar_scripts.py
Resultado: logs\\scripts.txt  (mándamelo). Tarda unos minutos.
"""
import bisect
import os
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, ROOT)

from icserver import config as config_mod   # noqa: E402
from icserver.rp import Pack                 # noqa: E402

WORDS = ["RankSkill", "InqCanRankSkill", "Advancement", "SkillPoint", "SkillRanked", "XPGained",
         "luaScript", "OnHandleEvent", "OnActivate", "Scriptlet", "gamelogic", "GameMode"]
SIGNATURES = {"lua bytecode": b"\x1bLua", "LuaQ": b"LuaQ", "LuaR": b"LuaR"}
for w in WORDS:
    SIGNATURES[w] = w.encode()
    SIGNATURES[w + " (utf16)"] = w.encode("utf-16-le")


def main():
    cfg = config_mod.load()
    rp_dir = os.path.join(cfg.game_dir, "rp")
    if not os.path.isdir(rp_dir):
        sys.exit(f"No encuentro la carpeta {rp_dir}. Revisa 'dir' en config.toml.")
    files = sorted(f for f in os.listdir(rp_dir) if f.lower().endswith(".rp"))
    os.makedirs(cfg.log_dir, exist_ok=True)
    out_path = os.path.join(cfg.log_dir, "scripts.txt")
    t0 = time.time()
    with open(out_path, "w", encoding="utf-8") as out:
        out.write(f"{len(files)} paquetes en {rp_dir}\n")
        for i, name in enumerate(files, 1):
            path = os.path.join(rp_dir, name)
            print(f"\r[{i}/{len(files)}] {name}          ", end="", flush=True)
            try:
                pack = Pack(path)
            except Exception as e:      # noqa: BLE001 - keep scanning
                out.write(f"{name}: no se pudo leer ({e})\n")
                continue
            hits = {}
            for label, sig in SIGNATURES.items():
                k, offs = pack.data.find(sig), []
                while k >= 0 and len(offs) < 2000:
                    offs.append(k)
                    k = pack.data.find(sig, k + 1)
                if offs:
                    hits[label] = offs
            prefixes = {}
            for did in pack.ids:
                prefixes[did >> 24] = prefixes.get(did >> 24, 0) + 1
            pre = " ".join(f"{p:02x}:{n}" for p, n in sorted(prefixes.items()))
            size = os.path.getsize(path) // 1024
            if not hits:
                out.write(f"{name} {size}KB {len(pack.ids)} registros [{pre}]\n")
                continue
            starts = pack.record_starts()
            offs_list = [o for o, _ in starts]
            out.write(f"{name} {size}KB {len(pack.ids)} registros [{pre}] ***\n")
            for label, offs in hits.items():
                recs = []
                for o in offs:
                    j = bisect.bisect_right(offs_list, o) - 1
                    did = starts[j][1] if j >= 0 else 0
                    if did not in recs:
                        recs.append(did)
                out.write(f"    {label}: {len(offs)} veces, registros "
                          + " ".join(f"{d:#010x}" for d in recs[:12])
                          + (" ..." if len(recs) > 12 else "") + "\n")
            out.flush()
    print(f"\nListo en {time.time() - t0:.0f} s: {out_path}")


if __name__ == "__main__":
    main()
