"""The main menu's SHOP screen: a small web page this server serves (docs/re-notes/store-amplifiers.md).

The client's store screen (UI movie 0x2000007C, AS2 gameplay.wrapper.store.Store) is a CEF browser: on open it raises
its own web-ticket notice (C++ listener 0x420B90 answers at once), then loads the login's URL.Store pair
(AuthSelect nameValuePairs, read at 0xA9B890) with "webticket" / "shard" headers; an HTTP status >= 400 closes the
screen with an error dialog. The original page was Turbine's web store (Steam MicroTxn); here URL.Store points at
GET /store of the SOAP port ([ics] store_url, store_web_page): the account's wallet, the store entries of
Session._boutique ([ics] store_prices in Merits, store_prices_hc in Crisis Coins) and a Buy button per entry and
currency. A purchase (POST /store/buy, fields did and cur = "SC" / "HC") runs in the logged-in session like the
client's own contextual purchase 0x210E: wallet, grant, then 0x210C, 0x20B8, 0x2081 (0x2095 with [ics]
store_purchase_ribbon, 0x2090 for a set slot) on the login connection, so the header and the screens update at once.
The URL reaches the client only in the nested AuthSelect form (store-fix.md 2.3, [ics] auth_pairs_nested).

2026-10-29 (user: "a nice, modern, friendly store that uses the champions' portraits and their backgrounds, for the
champions and the skins"): [ics] store_page_style = "cards" (default) draws a card grid with tabs, search and a detail
dialog; each champion / skin card shows its wallpaper (champions.json "wallpaper", per costume too) and the portrait
(grid_icon). The images are converted at run time from the player's own installed packs (DXT -> JPEG / PNG, mip level
by size) and cached in data/uesrv_cache/store (git-ignored); they are only sent to the local game client, never stored
in the repository. "table" = the fase3-ie plain table.
"""
import csv
import html
import io
import json
import os
import re
import threading
from urllib.parse import parse_qs, quote_plus, urlparse

from . import account as A

_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
_CATALOG = os.path.join(_ROOT, "catalog", "data")
_CACHE = os.path.join(_ROOT, "data", "uesrv_cache", "store")
_IMG_RE = re.compile(r"^/store/img/(icon|card|art|amp)/(0x[0-9a-fA-F]{8})\.(png|jpg)$")
_assets = {"store": None, "lock": threading.Lock(), "prewarm": False}


def _amp_names():
    try:
        with open(os.path.join(_CATALOG, "amplifiers.tsv"), encoding="utf-8") as f:
            return {int(r["id"], 16): (r.get("name") or "", r.get("stats") or "")
                    for r in csv.DictReader(f, delimiter="\t") if r.get("id", "").startswith("0x")}
    except (OSError, ValueError):
        return {}


def live_session(server):
    """The newest logged-in session (one player per server)."""
    with server.lock:
        live = [s for s in server.sessions if not s.user.closed and s.account is not None]
    return live[-1] if live else None


def owned(session, did, ct):
    acct, ic = session.account, session.ic
    if ct == A.CT_CHARACTER:
        return acct.champion_owned(did)
    if ct == A.CT_SKIN:
        return acct.skin_owned(did)
    if ct in (A.CT_AUGMENT, A.CT_MOD):
        return bool(ic.get("grant_all_amplifiers", True)) or acct.owns(did)
    return False


def entries(session):
    """[(section, did, name, detail, Merit price, Crisis Coin price, owned)] of what the store sells (0 = not sold in
    that currency)."""
    amp_names = _amp_names()
    acct = session.account
    out = []
    for _bid, (did, ct, soft) in sorted(session._boutique().items()):
        hard = session.store_price(ct, "hard")
        if ct == A.CT_AMP_SLOT:
            maximum = int(session.ic.get("amplifier_set_max", 12) or 0)
            out.append(("Amplifier set slots", did, "Amplifier Set Slot",
                        f"{acct.d['max_amplifier_sets']} of {maximum} slots", soft, hard,
                        acct.d["max_amplifier_sets"] >= maximum))
        elif ct in (A.CT_CHARACTER, A.CT_SKIN):
            name = session.data.champion_name(did)[0]
            if ct == A.CT_SKIN:
                skin = next((s.get("skin", "") for c in session.roster() for s in c.get("costume_info", [])
                             if s["variant"] == did), "")
                name = f"{name}: {skin}" if skin else name
            out.append(("Champions" if ct == A.CT_CHARACTER else "Skins", did, name, "", soft, hard,
                        owned(session, did, ct)))
        else:
            name, stats = amp_names.get(did, (f"{did:#x}", ""))
            out.append(("Augments" if ct == A.CT_AUGMENT else "Mods", did, name, stats, soft, hard,
                        owned(session, did, ct)))
    order = ["Amplifier set slots", "Champions", "Skins", "Augments", "Mods"]
    return sorted(out, key=lambda e: (order.index(e[0]), e[2]))


def buy(session, did, cur="SC"):
    """One purchase from the page in currency cur ("SC" Merits / "HC" Crisis Coins; with [ics]
    store_boutique_currency_keys = false the fase3-ie charge: store_currency's wallet, the Merit price). Returns a short
    result text."""
    from .session import STORE_WALLETS
    with session.lock:
        bid = session_boutique_id(did)
        item = session._boutique().get(bid)
        if item is None:
            return "not sold"
        if item[1] != A.CT_AMP_SLOT and owned(session, did, item[1]):
            return "already owned"
        wallet = price = None
        if session._store_keys():
            wallet = STORE_WALLETS.get(str(cur).strip().lower())
            price = session.store_price(item[1], wallet) if wallet else 0
            if not price:
                return f"not sold for {cur}"
        session.log(f"store page purchase {did:#x} for {item[2] if price is None else price} "
                    f"{wallet or session.legacy_store_wallet()}")
        return "bought" if session._complete_purchase(bid, item, wallet, price) else "refused (funds or slots)"


def session_boutique_id(did):
    from .session import BOUTIQUE_BASE
    return BOUTIQUE_BASE | did


# ---- artwork from the player's own packs ---------------------------------------------------------------------------
def art_map(session):
    """{variant DID: {"icon": portrait texture, "art": wallpaper texture, "skin": costume name, "champion": name}} for
    every champion and skin of the roster (data/champions.json)."""
    out = {}
    for c in session.roster():
        base = {"icon": c.get("grid_icon"), "art": c.get("wallpaper"), "skin": c.get("skin", ""), "champion": c["name"]}
        out[c["variant"]] = base
        for s in c.get("costume_info", []):
            out[s["variant"]] = {"icon": s.get("grid_icon") or base["icon"], "art": s.get("wallpaper") or base["art"],
                                 "skin": s.get("skin", ""), "champion": c["name"]}
    return out


def _store(session):
    with _assets["lock"]:
        if _assets["store"] is None:
            from uesrv.assets import AssetStore
            rp = os.path.join(session.cfg.game_dir, "rp")
            _assets["store"] = AssetStore(rp if os.path.isdir(rp) else session.cfg.game_dir,
                                          os.path.join(_ROOT, "data", "uesrv_cache"))
        return _assets["store"]


def _mip(tex, level):
    """The texture's mip `level` as a one-mip texture (level 0 when the chain is shorter)."""
    w, h, blk = tex["width"], tex["height"], 8 if tex["fourcc"] == b"DXT1" else 16
    off = 0
    for _ in range(level):
        off += max(1, (w + 3) // 4) * max(1, (h + 3) // 4) * blk
        w, h = max(1, w // 2), max(1, h // 2)
    size = max(1, (w + 3) // 4) * max(1, (h + 3) // 4) * blk
    if level <= 0 or level >= tex["mips"] or off + size > len(tex["data"]):
        return tex
    return dict(tex, width=w, height=h, mips=1, size=size, data=tex["data"][off:off + size])


def _encode(tex, fmt):
    """JPEG / PNG bytes of a DXT texture: Pillow's DDS decoder when installed, else the pure-Python PNG path."""
    from uesrv import textures
    try:
        from PIL import Image
        img = Image.open(io.BytesIO(textures.to_dds(dict(tex, mips=1)))).convert("RGBA" if fmt == "png" else "RGB")
        buf = io.BytesIO()
        if fmt == "png":
            img.save(buf, "PNG", optimize=True)
        else:
            img.save(buf, "JPEG", quality=84, optimize=True, progressive=True)
        return buf.getvalue(), "image/png" if fmt == "png" else "image/jpeg"
    except ImportError:
        return textures.to_png(tex), "image/png"


# 2026-10-29 (user: "extract all the images of the amplifiers and augments so they can be seen in the store; right
# now only a few have images"): the client never reads an icon from the amplifier itself; it composes it from layers
# (docs/re-notes/amplifier-icons.md). Augment (UI_InqAugmentData, 0xA43xxx -> 0xA26F70): stat 1's 0x100009D0 icon
# (top-left), stat 2's 0x100009CD icon (bottom-right) and the brand's background 0x100009C9, all from the stat /
# brand table 0x48000AAD (cached by 0xA710F0, looked up by 0xA21C90 / 0xA21CF0). Mod (UI_InqModData): the target
# artifact's icon 0x10000436 (0xA271D0, the last target of 0x10000989) under the brand's corner badge 0x10000996 of
# 0x48000A34 (0x8655F0). The layers are 256 px DXT3 pictures with alpha, meant to be stacked at full size (Flash
# AmplifierDisplay: m_icBottom, m_icMiddle, m_icTop).
AMP_STAT_ICONS = 0x48000AAD          # 0x100009CB {0x100009CA stat, 0x100009D0, 0x100009CD} + 0x100009CF brands
AMP_BRAND_BADGES = 0x48000A34        # 0x10000999 {0x10000996 badge, 0x10000997 brand}


def _amp_tables(session):
    """({stat key: (top-left icon, bottom-right icon)}, {brand: background}, {brand: corner badge}) from the packs."""
    from . import records as R
    cache = _assets.get("amp_tables")
    if cache is None:
        stats, backs, badges = {}, {}, {}
        e = session.data.record(AMP_STAT_ICONS)
        for _k, _kind, el in R.get(e, 0x100009CB) or []:
            d = R.as_dict(el)
            if d.get(0x100009CA) and d.get(0x100009CA) not in stats:      # first match wins (0xA21C90 index lookup)
                stats[int(d[0x100009CA])] = (d.get(0x100009D0), d.get(0x100009CD))
        for _k, _kind, el in R.get(e, 0x100009CF) or []:
            d = R.as_dict(el)
            backs.setdefault(int(d.get(0x10000997) or 0), d.get(0x100009C9))
        for _k, _kind, el in R.get(session.data.record(AMP_BRAND_BADGES), 0x10000999) or []:
            d = R.as_dict(el)
            badges.setdefault(int(d.get(0x10000997) or 0), d.get(0x10000996))
        cache = _assets["amp_tables"] = (stats, backs, badges)
    return cache


def _amp_layers(session, did, ct):
    """The texture DIDs the client stacks for an augment / mod, bottom first ([] when nothing resolves)."""
    from . import records as R
    stats, backs, badges = _amp_tables(session)
    e = session.data.record(0x49000000 | (did & 0xFFFFFF)) or []
    if ct == A.CT_AUGMENT:
        lines = [R.as_dict(el) for _k, _kind, el in R.get(e, 0x10000950) or []]
        top = stats.get(int(lines[0].get(0x10000958) or 0), (None, None))[0] if lines else None
        bottom = stats.get(int(lines[1].get(0x10000958) or 0), (None, None))[1] if len(lines) > 1 else None
        layers = [backs.get(int(R.get(e, 0x10000956) or 0)), bottom, top]
    else:
        art_icon = None
        for _k, _kind, el in R.get(e, 0x10000989) or []:
            target = R.as_dict(el).get(0x1000098B)
            te = session.data.record(0x49000000 | (int(target) & 0xFFFFFF)) if target else None
            if te:
                art_icon = R.get(te, 0x10000436) or art_icon   # the client keeps the last target's
        layers = [art_icon, badges.get(int(R.get(e, 0x1000097B) or 0))]
    return [x for x in layers if x and x >> 24 == 0x13]


def _amp_icon(session, did):
    """An amplifier's picture: its template's 0x10000302 or the set slot's record 0x1000095E (one texture DID), else
    ([ics] store_amp_composed_icons) the layers the client composes (a list, bottom first), else None."""
    if did == A.AMP_SLOT_ITEM:
        return next((v for p, _k, v in (session.data.record(did) or []) if p == 0x1000095E), None)
    ct = session.adata.amplifiers().get(did)
    if ct is None:
        return None
    if not session.ic.get("store_amp_composed_icons", True):
        return (session.data.template_properties(did).get(0x10000302) or [None])[0]
    # the 17 "0x10000302" icons template_properties found were the next records' pictures read past the amplifier's
    # 5-entry record (no amplifier record holds 0x10000302): only an icon really in the record is used
    from . import records as R
    own = R.get(session.data.record(0x49000000 | (did & 0xFFFFFF)) or [], 0x10000302)
    if own:
        return own
    layers = _amp_layers(session, did, ct)
    return layers[0] if len(layers) == 1 else (layers or None)


def _compose(session, layers):
    """PNG bytes of the layers stacked at the bottom layer's size (Pillow), or the bottom layer alone without it."""
    texs = [t for t in (_store(session).texture(d) for d in layers) if t]
    if not texs:
        return None
    try:
        from PIL import Image
    except ImportError:
        return _encode(_mip(texs[0], 0), "png")[0]
    from uesrv import textures
    base = None
    for t in texs:
        img = Image.open(io.BytesIO(textures.to_dds(dict(_mip(t, 0), mips=1)))).convert("RGBA")
        if base is None:
            base = img
        else:
            base.alpha_composite(img if img.size == base.size else img.resize(base.size, Image.LANCZOS))
    buf = io.BytesIO()
    base.save(buf, "PNG", optimize=True)
    return buf.getvalue()


def _save(path, body):
    """Write a cached picture atomically (the prewarm thread and a page request may convert the same one)."""
    os.makedirs(_CACHE, exist_ok=True)
    tmp = f"{path}.{threading.get_ident()}.tmp"
    with open(tmp, "wb") as f:
        f.write(body)
    os.replace(tmp, path)


def image(session, kind, variant):
    """(bytes, content type) of a store picture, or None. kind: icon = the portrait (128 px), card = the wallpaper's
    512 px mip, art = the full 1024 px wallpaper, amp = an amplifier's / the set slot's icon. Only DIDs of the
    roster's champions / skins and of the store's amplifiers are served."""
    if kind == "amp":
        if variant in _assets.setdefault("no_icon", set()):
            return None
        did = _amp_icon(session, variant)
        if not did:
            _assets["no_icon"].add(variant)        # nothing resolves: answered at once next time
            return None
        if isinstance(did, list):                  # composed layers: cached per amplifier
            path = os.path.join(_CACHE, f"amp_{variant:08x}_c.png")
            if os.path.exists(path):
                with open(path, "rb") as f:
                    return f.read(), "image/png"
            body = _compose(session, did)
            if not body:
                _assets["no_icon"].add(variant)
                return None
            _save(path, body)
            return body, "image/png"
    else:
        meta = art_map(session).get(variant)
        if not meta:
            return None
        did = meta["icon"] if kind == "icon" else meta["art"]
    if not did:
        return None
    fmt = "png" if kind in ("icon", "amp") else "jpg"
    path = os.path.join(_CACHE, f"{kind}_{did:08x}.{fmt}")
    ctype = "image/png" if fmt == "png" else "image/jpeg"
    if os.path.exists(path):
        with open(path, "rb") as f:
            return f.read(), ctype
    tex = _store(session).texture(did)
    if not tex:
        return None
    level = {"icon": 0, "amp": 0, "card": int(session.ic.get("store_card_mip", 1)), "art": 0}[kind]
    body, ctype = _encode(_mip(tex, level), fmt)
    if ctype == "image/png" and fmt == "jpg":
        path = path[:-3] + "png"
    _save(path, body)
    return body, ctype


def prewarm(session):
    """Convert every card / portrait once in the background, so the grid shows at once on the next visits
    ([ics] store_prewarm_images)."""
    if _assets["prewarm"] or not session.ic.get("store_prewarm_images", True):
        return
    _assets["prewarm"] = True
    variants = list(art_map(session))
    amps = sorted(session.adata.amplifiers()) + [A.AMP_SLOT_ITEM]

    def run():
        for v in variants:
            for kind in ("icon", "card"):
                try:
                    image(session, kind, v)
                except Exception:          # noqa: BLE001 - a picture the packs lack stays a placeholder
                    pass
        for v in amps:                     # the composed amplifier icons (store_amp_composed_icons)
            try:
                image(session, "amp", v)
            except Exception:              # noqa: BLE001
                pass
    threading.Thread(target=run, name="store-prewarm", daemon=True).start()


# ---- the page ------------------------------------------------------------------------------------------------------
_TABS = [("champions", "Champions"), ("skins", "Skins"), ("amps", "Amplifiers"), ("slots", "Set slots")]
_TAB_OF = {"Champions": "champions", "Skins": "skins", "Augments": "amps", "Mods": "amps",
           "Amplifier set slots": "slots"}


def render(session, note="", tab=""):
    if str(session.ic.get("store_page_style", "cards")) == "table":
        return render_table(session, note)
    return render_cards(session, note, tab)


def render_cards(session, note="", tab=""):
    keys = session._store_keys()
    soft_name = "Merits" if keys else str(session.ic.get("store_currency", "Merits"))
    w = session.account.wallet
    arts = art_map(session)
    counts = {t: 0 for t, _l in _TABS}
    cards = []
    for sec, did, name, detail, soft, hard, have in entries(session):
        tab_id = _TAB_OF.get(sec, "amps")
        counts[tab_id] += 1
        meta = arts.get(did)
        prices = [{"cur": code, "value": value, "label": label}
                  for code, value, label in (("SC", soft, soft_name), ("HC", hard, "Crisis Coins")) if value]
        if meta:
            title = meta["champion"]
            sub = meta["skin"] if sec == "Champions" else (meta["skin"] or "Skin")
            if sec == "Skins":
                title = meta["skin"] or name
                sub = meta["champion"]
            art = f"/store/img/card/{did:#010x}.jpg"
            big = f"/store/img/art/{did:#010x}.jpg"
            face = f"/store/img/icon/{did:#010x}.png"
        else:
            title, sub = name, detail or {"Augments": "Augment", "Mods": "Mod"}.get(sec, sec)
            art = big = face = ""
        kind = {"Augments": "augment", "Mods": "mod", "Amplifier set slots": "slot"}.get(sec, "hero")
        data = json.dumps({"did": f"{did:#010x}", "title": title, "sub": sub, "detail": detail, "art": big,
                           "face": face, "kind": kind, "owned": bool(have), "prices": prices,
                           "icon": "" if big else f"/store/img/amp/{did:#010x}.png"})
        chips = "".join(f'<span class="chip {p["cur"].lower()}">{p["value"]}</span>' for p in prices)
        visual = (f'<div class="art" style="background-image:url(\'{art}\')"></div>' if art
                  else f'<div class="art glyph {kind}"><span>{html.escape(_glyph(kind))}</span>'
                       f'<img class="ampicon" src="/store/img/amp/{did:#010x}.png" alt="" '
                       f'onerror="this.parentNode.removeChild(this)"></div>')
        face_img = f'<img class="face" src="{face}" alt="">' if face else ""
        cards.append(
            f'<div class="card{" owned" if have else ""}" data-tab="{tab_id}" '
            f'data-q="{html.escape((title + " " + sub + " " + detail).lower(), quote=True)}" '
            f"data-item='{html.escape(data, quote=True)}' onclick=\"openCard(this)\">{visual}"
            f'<div class="shade"></div>{"<div class=ribbon>OWNED</div>" if have else ""}'
            f'<div class="info">{face_img}<div class="txt"><div class="name">{html.escape(title)}</div>'
            f'<div class="sub">{html.escape(sub)}</div></div></div>'
            f'<div class="prices">{chips if not have else ""}</div></div>')
    tab = tab if tab in counts else next((t for t, _l in _TABS if counts[t]), "champions")
    tabs = "".join(f'<button class="tab{" on" if t == tab else ""}" data-tab="{t}" onclick="setTab(\'{t}\')">'
                   f'{html.escape(label)}<span class="n">{counts[t]}</span></button>'
                   for t, label in _TABS if counts[t])
    toast = (f'<div id="toast" class="toast{" bad" if not note.startswith("bought") else ""}">'
             f'{html.escape(_note_text(note))}</div>') if note else ""
    # 2026-10-30 (tester: "remove from the store the STORE / INFINITE CRISIS title and the Merits / Crisis Coins on the
    # right"; the client's own header already shows the wallet): [ics] store_page_header false = no title / wallet row
    top = ""
    if session.ic.get("store_page_header", False):
        top = (f'<div class="top"><div class="brand">STORE<small>INFINITE CRISIS</small></div>'
               f'<div class="wallet"><span class="coin sc"><i></i>{w["soft"]} {html.escape(soft_name)}</span>'
               f'<span class="coin hc"><i></i>{w["hard"]} Crisis Coins</span></div></div>')
    return _PAGE.format(top=top, tabs=tabs, toast=toast, cards="".join(cards), tab=tab)


def _glyph(kind):
    return {"augment": "+", "mod": "⚙", "slot": "▣"}.get(kind, "★")


def _note_text(note):
    return {"bought": "Purchase complete!", "already owned": "You already own this.",
            "refused (funds or slots)": "Not enough currency (or no free slot).",
            "no player logged in": "No player is logged in."}.get(note, note)


# Chromium 31 (the client's CEF 3.1650): flexbox, ES5, -webkit- prefixes; no CSS grid, variables or arrow functions.
_PAGE = """<!doctype html><html><head><meta charset="utf-8"><title>Store</title><style>
*{{box-sizing:border-box}}
html,body{{margin:0;height:100%}}
body{{background:#0b1016;background-image:-webkit-radial-gradient(20% 0%,circle,#1c3550 0%,#0b1016 55%);
  color:#e9eef4;font:14px "Segoe UI",Arial,sans-serif;overflow-y:auto}}
.top{{display:-webkit-flex;display:flex;-webkit-align-items:center;align-items:center;padding:18px 28px 10px}}
.brand{{font-size:28px;font-weight:700;letter-spacing:6px;color:#fff;text-shadow:0 0 18px rgba(80,170,255,.55)}}
.brand small{{display:block;font-size:11px;letter-spacing:3px;color:#7fa6c9;font-weight:400}}
.wallet{{margin-left:auto;display:-webkit-flex;display:flex}}
.coin{{margin-left:12px;padding:8px 16px;border-radius:20px;background:rgba(255,255,255,.06);
  border:1px solid rgba(255,255,255,.12);font-weight:600}}
.coin i{{display:inline-block;width:12px;height:12px;border-radius:50%;margin-right:8px;vertical-align:-1px}}
.coin.sc i{{background:#52b6ff;box-shadow:0 0 8px #52b6ff}} .coin.hc i{{background:#f4c542;box-shadow:0 0 8px #f4c542}}
.bar{{display:-webkit-flex;display:flex;-webkit-align-items:center;align-items:center;padding:6px 28px 14px;
  border-bottom:1px solid rgba(255,255,255,.08)}}
.tab{{background:transparent;border:0;color:#9db3c8;font:600 14px "Segoe UI",Arial;padding:9px 16px;margin-right:6px;
  border-radius:18px;cursor:pointer;-webkit-transition:all .15s}}
.tab:hover{{color:#fff;background:rgba(255,255,255,.06)}}
.tab.on{{color:#06121e;background:-webkit-linear-gradient(left,#7fd3ff,#4f9dff);box-shadow:0 2px 12px rgba(79,157,255,.45)}}
.tab .n{{margin-left:8px;font-size:11px;opacity:.7}}
.tools{{margin-left:auto;display:-webkit-flex;display:flex;-webkit-align-items:center;align-items:center}}
#q{{background:rgba(255,255,255,.07);border:1px solid rgba(255,255,255,.14);color:#fff;border-radius:18px;
  padding:8px 14px;width:220px;font:14px "Segoe UI",Arial;outline:none}}
#q:focus{{border-color:#4f9dff}}
.tools label{{margin-left:14px;color:#9db3c8;cursor:pointer;font-size:13px}}
.grid{{display:-webkit-flex;display:flex;-webkit-flex-wrap:wrap;flex-wrap:wrap;padding:20px 22px 40px}}
.card{{position:relative;width:206px;height:290px;margin:8px;border-radius:14px;overflow:hidden;cursor:pointer;
  background:#13202d;box-shadow:0 6px 18px rgba(0,0,0,.45);border:1px solid rgba(255,255,255,.08);
  -webkit-transition:-webkit-transform .18s,box-shadow .18s}}
.card:hover{{-webkit-transform:translateY(-4px) scale(1.02);box-shadow:0 12px 28px rgba(0,0,0,.6),0 0 0 2px #4f9dff}}
.card .art{{position:absolute;left:0;top:0;right:0;bottom:0;background-size:cover;background-position:50% 20%;
  -webkit-transition:-webkit-transform .4s}}
.card:hover .art{{-webkit-transform:scale(1.07)}}
.card.owned .art{{-webkit-filter:saturate(.55) brightness(.8)}}
.shade{{position:absolute;left:0;right:0;bottom:0;height:62%;
  background:-webkit-linear-gradient(top,rgba(8,14,22,0),rgba(8,14,22,.92) 70%)}}
.ribbon{{position:absolute;top:12px;right:-30px;-webkit-transform:rotate(35deg);background:#2fb36b;color:#fff;
  font:700 11px "Segoe UI",Arial;letter-spacing:2px;padding:4px 36px}}
.info{{position:absolute;left:12px;right:12px;bottom:44px;display:-webkit-flex;display:flex;
  -webkit-align-items:center;align-items:center}}
.face{{width:46px;height:46px;border-radius:50%;border:2px solid #7fd3ff;box-shadow:0 0 10px rgba(79,157,255,.6);
  margin-right:10px;-webkit-flex-shrink:0;flex-shrink:0;background:#0b1016}}
.name{{font-weight:700;font-size:15px;line-height:18px;text-shadow:0 1px 3px #000}}
.sub{{color:#a9c3da;font-size:12px;margin-top:2px}}
.prices{{position:absolute;left:12px;right:12px;bottom:12px}}
.chip{{display:inline-block;padding:3px 10px 3px 8px;border-radius:12px;font-weight:700;font-size:12px;margin-right:6px;
  background:rgba(0,0,0,.55);border:1px solid rgba(255,255,255,.15)}}
.chip:before{{content:"";display:inline-block;width:9px;height:9px;border-radius:50%;margin-right:6px}}
.chip.sc:before{{background:#52b6ff}} .chip.hc:before{{background:#f4c542}}
.glyph{{display:-webkit-flex;display:flex;-webkit-align-items:center;align-items:center;-webkit-justify-content:center;
  justify-content:center}}
.glyph span{{font-size:86px;color:rgba(255,255,255,.85);margin-bottom:70px;text-shadow:0 0 30px rgba(255,255,255,.35)}}
.glyph.augment{{background:-webkit-linear-gradient(135deg,#1f6f5c,#0d2b3a)}}
.glyph.mod{{background:-webkit-linear-gradient(135deg,#6b3fa0,#1b1838)}}
.glyph.slot{{background:-webkit-linear-gradient(135deg,#b07a1d,#2b1a0a)}}
.empty{{color:#7f97ad;padding:40px;width:100%;text-align:center}}
.toast{{margin:14px 28px 0;padding:10px 16px;border-radius:10px;background:rgba(47,179,107,.18);
  border:1px solid #2fb36b;color:#bff2d5;font-weight:600}}
.toast.bad{{background:rgba(220,70,70,.16);border-color:#d64545;color:#ffd1d1}}
.modal{{position:fixed;left:0;top:0;right:0;bottom:0;background:rgba(3,7,12,.78);display:-webkit-flex;display:flex;
  -webkit-align-items:center;align-items:center;-webkit-justify-content:center;justify-content:center;z-index:9}}
.modal.hidden{{display:none}}
.box{{position:relative;width:780px;max-width:94%;height:470px;border-radius:18px;overflow:hidden;background:#0e1822;
  box-shadow:0 20px 60px rgba(0,0,0,.7);border:1px solid rgba(127,211,255,.25);display:-webkit-flex;display:flex}}
.box .big{{width:470px;background-size:cover;background-position:50% 20%;position:relative}}
.box .big:after{{content:"";position:absolute;top:0;bottom:0;right:0;width:120px;
  background:-webkit-linear-gradient(left,rgba(14,24,34,0),#0e1822)}}
.box .side{{-webkit-flex:1;flex:1;padding:34px 30px;display:-webkit-flex;display:flex;-webkit-flex-direction:column;
  flex-direction:column}}
.box .t{{font-size:26px;font-weight:700}} .box .s{{color:#a9c3da;margin-top:4px;font-size:15px}}
.box .d{{color:#8fa9bf;margin-top:16px;line-height:20px}}
.box .acts{{margin-top:auto}}
.buy{{display:block;width:100%;margin-top:10px;border:0;border-radius:12px;padding:13px;font:700 15px "Segoe UI",Arial;
  cursor:pointer;color:#071420;-webkit-transition:-webkit-filter .15s}}
.buy:hover{{-webkit-filter:brightness(1.12)}}
.buy.sc{{background:-webkit-linear-gradient(left,#8fdcff,#3f8dff)}} .buy.hc{{background:-webkit-linear-gradient(left,#ffd866,#f0a92e)}}
.have{{margin-top:10px;padding:13px;border-radius:12px;text-align:center;background:rgba(47,179,107,.18);
  border:1px solid #2fb36b;color:#bff2d5;font-weight:700}}
.x{{position:absolute;top:12px;right:14px;width:34px;height:34px;border-radius:50%;border:0;background:rgba(0,0,0,.5);
  color:#fff;font-size:18px;cursor:pointer;z-index:2}}
.ampicon{{position:absolute;left:50%;top:38%;width:128px;height:128px;margin:-64px 0 0 -64px;border-radius:18px;
  box-shadow:0 0 0 2px rgba(255,255,255,.25),0 8px 24px rgba(0,0,0,.6)}}
.big .ampicon{{width:220px;height:220px;margin:-110px 0 0 -110px;top:50%}}
</style></head><body>
{top}<div class="bar"><div class="tabs">{tabs}</div><div class="tools"><input id="q" placeholder="Search..." oninput="filter()">
<label><input type="checkbox" id="hide" onchange="filter()"> Hide owned</label></div></div>
{toast}
<div class="grid" id="grid">{cards}<div class="empty" id="empty" style="display:none">Nothing here.</div></div>
<div class="modal hidden" id="modal" onclick="if(event.target===this)closeCard()"><div class="box">
<button class="x" onclick="closeCard()">&#x2715;</button><div class="big" id="mbig"></div>
<div class="side"><div class="t" id="mt"></div><div class="s" id="ms"></div><div class="d" id="md"></div>
<div class="acts" id="ma"></div></div></div></div>
<script>
var TAB = "{tab}";
function esc(s) {{ return String(s).replace(/[&<>"']/g, function (c) {{ return "&#" + c.charCodeAt(0) + ";"; }}); }}
function setTab(t) {{
  TAB = t; var b = document.querySelectorAll(".tab");
  for (var i = 0; i < b.length; i++) b[i].className = "tab" + (b[i].getAttribute("data-tab") === t ? " on" : "");
  filter();
}}
function filter() {{
  var q = document.getElementById("q").value.toLowerCase(), hide = document.getElementById("hide").checked;
  var c = document.querySelectorAll(".card"), shown = 0;
  for (var i = 0; i < c.length; i++) {{
    var ok = c[i].getAttribute("data-tab") === TAB && c[i].getAttribute("data-q").indexOf(q) >= 0 &&
             !(hide && c[i].className.indexOf("owned") >= 0);
    c[i].style.display = ok ? "" : "none"; if (ok) shown++;
  }}
  document.getElementById("empty").style.display = shown ? "none" : "";
}}
function openCard(el) {{
  var it = JSON.parse(el.getAttribute("data-item"));
  var big = document.getElementById("mbig");
  big.style.backgroundImage = it.art ? "url('" + it.art + "')" : "none";
  big.className = "big" + (it.art ? "" : " glyph " + it.kind);
  big.innerHTML = it.art ? "" : "<span>" + el.querySelector(".glyph span").innerHTML + "</span>" +
    (el.querySelector(".ampicon") ? "<img class='ampicon' src='" + it.icon + "' alt=''>" : "");
  document.getElementById("mt").innerHTML = esc(it.title);
  document.getElementById("ms").innerHTML = esc(it.sub);
  document.getElementById("md").innerHTML = esc(it.detail || "");
  var a = "";
  if (it.owned) a = "<div class='have'>&#x2714; Owned</div>";
  else for (var i = 0; i < it.prices.length; i++) {{
    var p = it.prices[i];
    a += "<form method='post' action='/store/buy'><input type='hidden' name='did' value='" + it.did + "'>" +
         "<input type='hidden' name='cur' value='" + p.cur + "'><input type='hidden' name='tab' value='" + TAB + "'>" +
         "<button class='buy " + p.cur.toLowerCase() + "'>Buy for " + p.value + " " + esc(p.label) + "</button></form>";
  }}
  document.getElementById("ma").innerHTML = a;
  document.getElementById("modal").className = "modal";
}}
function closeCard() {{ document.getElementById("modal").className = "modal hidden"; }}
document.onkeydown = function (e) {{ if ((e || window.event).keyCode === 27) closeCard(); }};
var t = document.getElementById("toast"); if (t) setTimeout(function () {{ t.style.display = "none"; }}, 4000);
filter();
</script></body></html>"""


def render_table(session, note=""):
    keys = session._store_keys()
    # fase3-ie (store_boutique_currency_keys = false): one price, named by store_currency
    soft_name = "Merits" if keys else str(session.ic.get("store_currency", "Merits"))
    w = session.account.wallet
    rows, section = [], None
    for sec, did, name, detail, soft, hard, have in entries(session):
        if sec != section:
            section = sec
            rows.append(f'<tr><th colspan="4">{html.escape(sec)}</th></tr>')
        prices = [(code, value, label)
                  for code, value, label in (("SC", soft, soft_name), ("HC", hard, "Crisis Coins")) if value]
        if have:
            button = "<span class=own>owned</span>"
        else:
            button = "".join(f'<form method="post" action="/store/buy"><input type="hidden" name="did" '
                             f'value="{did:#010x}"><input type="hidden" name="cur" value="{code}">'
                             f'<button>Buy ({value} {html.escape(label)})</button></form>'
                             for code, value, label in prices)
        cost = " / ".join(f"{value} {html.escape(label)}" for _code, value, label in prices)
        rows.append(f"<tr><td>{html.escape(name)}</td><td class=d>{html.escape(detail)}</td>"
                    f"<td class=p>{cost}</td><td class=b>{button}</td></tr>")
    msg = f'<p class=note>{html.escape(note)}</p>' if note else ""
    return f"""<!doctype html><html><head><meta charset="utf-8"><title>Store</title><style>
body{{background:#101418;color:#e8e8e8;font:14px Arial,sans-serif;margin:16px}}
h1{{font-size:20px;margin:0 0 8px}} .w{{color:#f0c040}} table{{border-collapse:collapse;width:100%}}
th{{text-align:left;background:#22303c;padding:6px}} td{{padding:4px 6px;border-bottom:1px solid #222}}
.d{{color:#9aa}} .p{{white-space:nowrap}} .own{{color:#6c6}} .note{{color:#f0c040}}
.b{{white-space:nowrap}} form{{display:inline;margin:0 6px 0 0}}
button{{background:#2a6;color:#fff;border:0;padding:3px 12px;cursor:pointer}}
</style></head><body><h1>Store</h1>
<p class=w>Merits: {w['soft']} &nbsp; Crisis Coins: {w['hard']}</p>{msg}
<table>{''.join(rows)}</table></body></html>"""


def handle(server, req):
    """GET /store, POST /store/buy (req: the BaseHTTPRequestHandler). Returns True when answered."""
    url = urlparse(req.path)
    if not url.path.startswith("/store"):
        return False
    session = live_session(server)
    img = _IMG_RE.match(url.path)
    if img:
        got = None
        if session is not None and session.ic.get("store_page_images", True):
            try:
                got = image(session, img.group(1), int(img.group(2), 16))
            except Exception:              # noqa: BLE001 - a broken picture must not break the page
                got = None
        if got is None:
            req.send_response(404)
            req.send_header("Content-Length", "0")
            req.end_headers()
            return True
        body, ctype = got
        req.send_response(200)
        req.send_header("Content-Type", ctype)
        req.send_header("Cache-Control", "max-age=86400")
        req.send_header("Content-Length", str(len(body)))
        req.end_headers()
        if req.command != "HEAD":
            req.wfile.write(body)
        return True
    if req.command == "POST" and url.path == "/store/buy":
        length = int(req.headers.get("Content-Length") or 0)
        form = parse_qs((req.rfile.read(length) if length else b"").decode("ascii", "replace"))
        try:
            did = int((form.get("did") or ["0"])[0], 0)
        except ValueError:
            did = 0
        cur = (form.get("cur") or ["SC"])[0]
        tab = (form.get("tab") or [""])[0]
        note = buy(session, did, cur) if session is not None and did else "no player logged in"
        req.send_response(303)
        req.send_header("Location", "/store?note=" + quote_plus(note) + ("&tab=" + quote_plus(tab) if tab else ""))
        req.send_header("Content-Length", "0")
        req.end_headers()
        return True
    if session is None:
        body = b"<!doctype html><html><body>No player is logged in.</body></html>"
    else:
        query = parse_qs(url.query)
        note = (query.get("note") or [""])[0]
        if session.ic.get("store_page_images", True):
            prewarm(session)
        body = render(session, note, (query.get("tab") or [""])[0]).encode("utf-8")
    req.send_response(200)
    req.send_header("Content-Type", "text/html; charset=utf-8")
    req.send_header("Content-Length", str(len(body)))
    req.end_headers()
    req.wfile.write(body)
    return True
