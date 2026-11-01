"""Busca registros del juego por su ID (DID) en todos los paquetes y los copia.

Uso:
    python tools\\extraer_registros.py 0x34000037 0x34000038 ...
    python tools\\extraer_registros.py            (sin IDs: los scriptlets de Gaslight Batman)

Escribe logs\\registros\\<DID>.bin (los bytes del registro) y logs\\registros\\indice.txt
(en qué paquete está cada uno). Mándame la carpeta logs\\registros comprimida en un zip.
Solo lee los paquetes; no modifica nada.
"""
import os
import struct
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, ROOT)

from icserver import config as config_mod   # noqa: E402
from icserver.rp import Pack                 # noqa: E402

# Scriptlets that Gaslight Batman's class (twin 0x49000086) refers to.
DEFAULT = [0x34000037, 0x34000038, 0x34000039, 0x3400003A, 0x3400003B, 0x34000048]


def main():
    wanted = [int(a, 16) for a in sys.argv[1:]] or DEFAULT
    cfg = config_mod.load()
    rp_dir = os.path.join(cfg.game_dir, "rp")
    if not os.path.isdir(rp_dir):
        sys.exit(f"No encuentro la carpeta {rp_dir}. Revisa 'dir' en config.toml.")
    out_dir = os.path.join(cfg.log_dir, "registros")
    os.makedirs(out_dir, exist_ok=True)
    pending = set(wanted)
    found_refs = set()
    lines = []
    files = sorted(f for f in os.listdir(rp_dir) if f.lower().endswith(".rp"))
    for i, name in enumerate(files, 1):
        if not pending:
            break
        print(f"\r[{i}/{len(files)}] {name}          ", end="", flush=True)
        try:
            pack = Pack(os.path.join(rp_dir, name))
        except Exception as e:      # noqa: BLE001
            lines.append(f"{name}: no se pudo leer ({e})")
            continue
        hit = pending.intersection(pack.ids)
        if not hit:
            continue
        starts = pack.record_starts()
        for j, (off, did) in enumerate(starts):
            if did not in hit:
                continue
            end = starts[j + 1][0] if j + 1 < len(starts) else len(pack.data)
            data = pack.data[off:end]
            with open(os.path.join(out_dir, f"{did:#010x}.bin"), "wb") as f:
                f.write(data)
            lines.append(f"{did:#010x} en {name}, {len(data)} bytes")
            pending.discard(did)
            # other scriptlets / script records it refers to
            for k in range(0, len(data) - 3):
                v = struct.unpack_from("<I", data, k)[0]
                if v >> 24 == 0x34 and (v & 0xFFFFFF) < 0x4000 and v not in wanted:
                    found_refs.add(v)
    for did in sorted(pending):
        lines.append(f"{did:#010x} NO ENCONTRADO")
    if found_refs:
        lines.append("otros scriptlets mencionados: " + " ".join(f"{d:#010x}" for d in sorted(found_refs)))
    with open(os.path.join(out_dir, "indice.txt"), "w", encoding="utf-8") as f:
        f.write("\n".join(lines) + "\n")
    print("\n" + "\n".join(lines))
    print(f"\nListo: {out_dir}")


if __name__ == "__main__":
    main()
