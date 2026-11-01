"""Tests for the UE5 server: protocol, auth and (if the game is installed) texture export.
Usage: python tests/test_uesrv.py [game dir]"""
import os
import struct
import sys
import tempfile
import urllib.request

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from icserver import config  # noqa: E402
from uesrv.client import Client  # noqa: E402
from uesrv.server import Server  # noqa: E402

TEXTURE = 0x130002CB     # Gaslight Batman, 1024x1024 DXT5, pack 0xA0000076
fails = 0


def check(name, ok):
    global fails
    print(("ok   " if ok else "FAIL ") + name)
    fails += not ok


cfg = config.load()
if len(sys.argv) > 1:
    cfg["game"]["dir"] = sys.argv[1]
tmp = tempfile.mkdtemp()
cfg["uesrv"].update(control_port=19100, asset_port=19101, accounts=os.path.join(tmp, "acc.json"),
                    cache_dir=os.path.join(tmp, "cache"))
srv = Server(cfg)
srv.start()
try:
    c = Client("127.0.0.1", 19100)
    check("hello", c.call("hello")["protocol"] == 1)
    check("profile needs login", c.call("profile")["error"] == "not_logged_in")
    check("bad login", c.login("zed", "pw12")["type"] == "error")
    check("register", c.login("zed", "pw12", register=True)["type"] == "session")
    check("duplicate register", Client("127.0.0.1", 19100).login("ZED", "other", register=True)["type"] == "error")
    check("profile", c.call("profile")["profile"]["name"] == "zed")
    check("unknown type", c.call("nope")["error"] == "unknown_type")
    if os.path.isdir(os.path.join(cfg.game_dir, "rp")):
        png = c.fetch_asset("texture", TEXTURE, "png")
        check("texture png", png[:8] == b"\x89PNG\r\n\x1a\n" and len(png) > 1000)
        dds = c.fetch_asset("texture", TEXTURE, "dds")
        check("texture dds", dds[:4] == b"DDS " and len(dds) == 128 + 1398096)
        obj = c.fetch_asset("mesh", 0x170000CB, "obj").decode()
        check("mesh obj", obj.count("\nv ") == 1064 and obj.count("\nf ") == 532)
        from icserver.rp import Pack
        from uesrv import gltf, havok, meshes
        pack = Pack(os.path.join(cfg.game_dir, "rp", "0xa0000076.rp"))
        skinned = meshes.find_skinned(pack.data)
        check("batman skinned meshes", [len(m["vertices"]) for m in skinned] == [6558, 1531])
        skels = {s["name"]: s for h in havok.find_packfiles(pack.data)
                 for s in havok.skeletons(havok.Packfile(pack.data, h))}
        check("batman skeleton", len(skels["MainSkeleton"]["bones"]) == 86 and skels["MainSkeleton"]["parents"][0] == -1)
        keys = gltf.material_textures(pack.data, pack.find_all(gltf.binding_material(pack.data, pack, 0x170000DB)))
        check("batman material textures", keys.get(gltf.BASE) == 0x130002CD and keys.get(gltf.NORMAL) == 0x130002CB)
        glb = gltf.build_glb("t", skinned, skels["MainSkeleton"], {})
        check("batman glb", glb[:4] == b"glTF" and struct.unpack_from("<I", glb, 8)[0] == len(glb))
        from uesrv import havok_anim
        beh = Pack(os.path.join(cfg.game_dir, "rp", "0xa0000122.rp"))
        anims, ends_ok = [], True
        for h in havok.find_packfiles(beh.data):
            try:
                pf = havok.Packfile(beh.data, h)
            except Exception:
                continue
            for a in havok_anim.animations(pf):
                anims.append(a)
                nxt = list(a.block_offsets[1:]) + [a.data_size]
                ends_ok &= all(0 <= e - n < 16 for e, n in zip(nxt, a.block_ends))
        check("batman spline animations", len(anims) == 69 and ends_ok)
        check("batman clip DIDs", len(havok_anim.clip_dids(beh, anims)) == 69)
        body = [a for a in anims if a.tracks == 86]
        joints = havok_anim.bone_map(body[0].track_names, skels["MainSkeleton"]["bones"])
        check("animation tracks map to bones", sorted(joints) == list(range(86)))
        by_did = dict(zip(havok_anim.clip_dids(beh, anims), anims))
        speeds_ok = True
        for did, mps in ((0x1A000798, 1.25), (0x1A000173, 2.5), (0x1A0006C8, 3.7), (0x1A0006C6, 5.0),
                         (0x1A0006C4, 9.0)):
            a = by_did[did]
            r0, r1 = a.sample(0)[1][0], a.sample(a.frames - 1)[1][0]   # track 1 = Root
            speeds_ok &= abs(((r1[0] - r0[0]) ** 2 + (r1[1] - r0[1]) ** 2) ** 0.5 / a.duration - mps) < 0.05
        check("named locomotion clips have their root speed", speeds_ok)
        open(os.path.join(tmp, "sample.png"), "wb").write(png)
        print("sample png:", os.path.join(tmp, "sample.png"))
    else:
        print("skip texture checks: no game dir")
    try:
        urllib.request.urlopen("http://127.0.0.1:19101/asset/texture/130002cb.png")
        check("asset without token rejected", False)
    except Exception as e:
        check("asset without token rejected", getattr(e, "code", 0) == 401)
finally:
    srv.stop()
sys.exit(1 if fails else 0)
