"""The PvP / menu flow of the new server (ics/session.py, account.py, lobby.py, matchend.py) with a simulated client:
login (account data, 0x2080 last, the extras), the account screens (amplifier sets, boutique, store purchase,
protector icon, achievements, standings, leaderboards, preferences, chat), queue / leave queue, queue again, accept,
champion select with bots (pick, Stolen Power, lock, launch), loading, the match (stub: the mode layer ics/match is
not needed), its end (VICTORY, rewards, end page), back to the menu, the account file, and a custom match launch.

    python tests\\test_session_flow.py

Uses ports 2888x / 2900x and a temporary account directory.
"""
import json
import os
import socket
import struct
import sys
import tempfile
import time

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
sys.path.insert(0, os.path.join(ROOT, "tests"))

from ics import config, log                                       # noqa: E402
from ics import messages as M                                     # noqa: E402
from ics.server import SOAP_ENVELOPE, Server                      # noqa: E402
from ics.wire import read_compact, string_info, wstring           # noqa: E402
from test_ics import Client, auth_pairs, hello_blob, object_class # noqa: E402

SVC = 0x0600000000000403
PLAYER = 0x0200000000000001
CHAMPION = 0x0200000000000002
ENCOUNTER = 0x40000B6C          # Gotham Heights v AI: 5 per team, a bot pool of 14 champions
QFLAGS = (1 << 21) | (1 << 17)
results = []


def check(name, cond, detail=""):
    results.append(bool(cond))
    print(f"  {'ok  ' if cond else 'FAIL'} {name}" + (f"  ({detail})" if detail and not cond else ""))


def ids(events):
    return [e[2] for e in events]


def batch_kinds(body):
    """The sub-event ids of a 0x4 batch body (u8 base | compact n | n x (compact id | u32 length | body))."""
    n, p = read_compact(body, 1)
    out = []
    for _ in range(n):
        ev, p = read_compact(body, p)
        p += 4 + struct.unpack_from("<I", body, p)[0]
        out.append(ev)
    return out


def str8(text):
    return bytes([len(text)]) + text.encode()


def boutique_entries(body):
    """0x2107: u8 0 | u32 n | n x (u64 boutique id | u32 DID | str8 currency | u32 price) -> (entries, whole body)."""
    n, pos, out = struct.unpack_from("<I", body, 1)[0], 5, []
    for _ in range(n):
        bid, did = struct.unpack_from("<QI", body, pos)
        k, pos = read_compact(body, pos + 12)
        cur = body[pos:pos + k].decode("ascii", "replace")
        out.append((bid, did, cur, struct.unpack_from("<I", body, pos + k)[0]))
        pos += k + 4
    return out, pos == len(body)


def purchase(bid, did, cur, price):
    """0x210E as the client's dialogs send it: u64 boutique | u32 DID | str8 "SC"/"HC" | u32 cost | str8 language."""
    return struct.pack("<QI", bid, did) + str8(cur) + struct.pack("<I", price & 0xFFFFFFFF) + str8("en")


def main():
    cfg = config.load()
    s = cfg["server"]
    # SESSION_TEST_PORT shifts every port (several test runs at once): soap base, user base + 112, game base + 113
    base = int(os.environ.get("SESSION_TEST_PORT", "28888"))
    s.update({"soap_port": base, "user_port": base + 112, "game_port": base + 113})
    cfg["timing"].update({"objects_min_delay": 0.3, "link_delay": 0.2, "units_delay": 30.0})
    ic = cfg["ics"]
    acct_dir = tempfile.mkdtemp(prefix="ics_accounts_")
    ic.update({"account_dir": acct_dir, "progress_file": os.path.join(acct_dir, "none.json"), "start_merits": 5000,
               "trace_scripts": False, "queue_pop_seconds": 0.3, "select_seconds": 30, "launch_delay": 1.5, "lobby_slot_resend": 0,
               "pvp_stub_seconds": 0.8, "victory_hold": 0.3, "login_extras_delay": 0.2, "bot_seed": 7,
               "spawn_layout": False, "player_name": "FlowTester", "pvp_mode_layer": False,
               "menu_refresh_after_match": 0.3, "start_crisis_coins": 200,
               "own_all_except": [], "account_grants": [],
               # 2026-11-06: a local config.toml's bot_champions (one forced variant) left 3 champions in the match;
               # the 10-champion checks need the roster pool
               "bot_champions": []})
    # 2026-10-29 22:30 (tester's store test): [ics] own_all_except and account_grants
    from ics import account as A2
    ic2 = dict(ic, own_all_except=["0x400007FA", "0x40000999"], account_grants=[{"id": "t", "soft": 10, "hard": 2}])
    a2 = A2.Account("ExceptTester", ic2)
    w0 = dict(a2.wallet)
    first, again = a2.apply_grants(), a2.apply_grants()
    check("own_all_except: Blue Beetle and a listed skin are not owned until bought, others are; a grant applies once",
          not a2.champion_owned(0x400007FA) and not a2.skin_owned(0x40000999) and a2.champion_owned(0x40000086)
          and first == ["t"] and again == [] and a2.wallet["soft"] - w0["soft"] == 10 and a2.wallet["hard"] - w0["hard"] == 2)
    a2.own(0x400007FA, A2.CT_CHARACTER)
    check("own_all_except: a bought champion is owned", a2.champion_owned(0x400007FA))
    log.setup(tempfile.mkdtemp(prefix="ics_flow_"), False)
    server = Server(cfg)
    server.start()

    # ---- login -----------------------------------------------------------------------------------------------
    u = Client(s["user_port"])
    u.sock.sendall(hello_blob(server.key.n))
    check("account data delivered", u.wait_for(lambda e: e[2] == 0x2080, 10))
    u.wait_for(lambda e: e[2] == 0x203B, 30)     # the extras (the login calendar is read from the packs)
    time.sleep(0.2)
    seq = ids(u.since(0))
    core = [0xEB, 0x20B8, 0x20ED, 0x209D, 0x2024, 0x216A, 0x218B, 0x215D, 0xCE, 0x2080]
    pos = [seq.index(x) if x in seq else -1 for x in core]
    check("login order: 0xEB 0x20B8 0x20ED 0x209D 0x2024 0x216A 0x218B 0x215D 0xCE ... 0x2080",
          -1 not in pos and pos == sorted(pos), [hex(x) for x in seq[:14]])
    i80 = seq.index(0x2080)
    check("0x2080 is the last of the login data (the extras come after it)",
          not set(seq[:i80]) & {0x2081, 0x2190, 0x2186, 0x2197, 0x219D, 0x203B})
    check("extras: currencies 0x2081, header 0x2190, accolades 0x2186, login reward 0x2197/0x219D, contacts 0x203B",
          {0x2081, 0x2190, 0x2186, 0x203B} <= set(seq[i80:]) and (0x2197 in seq or 0x219D in seq),
          [hex(x) for x in seq[i80:]])
    path = os.path.join(acct_dir, "FlowTester.json")
    check("account file written", os.path.isfile(path))
    sess = server.sessions[-1]
    merits0 = sess.account.wallet["soft"]

    # ---- the play menu's encounter list (0x2024) and queue eligibility (0x2101) --------------------------------
    encs = server.data.encounter_list()
    enc_ev = u.since(0, 0x2024)
    b = enc_ev[0][3] if enc_ev else b""
    dids, flags, strings, extra, ok24 = [], [], b"", [], False
    try:
        n = struct.unpack_from("<I", b, 1)[0]
        dids = list(struct.unpack_from("<%dI" % n, b, 5))
        p24 = 5 + 4 * n
        flags = list(struct.unpack_from("<%dI" % n, b, p24 + 4)) if struct.unpack_from("<I", b, p24)[0] == n else []
        p24 += 4 + 4 * n
        ns = struct.unpack_from("<I", b, p24)[0]
        strings = b[p24 + 4:p24 + 4 + ns]
        p24 += 4 + ns
        extra = list(struct.unpack_from("<%dI" % n, b, p24 + 4))
        ok24 = ns == n and struct.unpack_from("<I", b, p24)[0] == n
    except struct.error:
        pass
    check("0x2024: the installed encounters, in the data's order", dids == [d for d, _c in encs] and ENCOUNTER in dids,
          [hex(d) for d in dids])
    want_flags = [0 if c == 4 else M.QUEUE_BLIND | M.QUEUE_DRAFT for _d, c in encs]
    check("0x2024: queue flags = blind (bit 21) + draft (bit 17), tutorials 0; empty access strings; list 4 zeros",
          ok24 and flags == want_flags and strings == b"\x00" * len(dids) and not any(extra),
          ([hex(f) for f in flags], strings, extra))
    elig = u.since(0, 0x2101)
    ok01 = False
    if elig:
        e = elig[0][3]
        lvl, cap, ne = struct.unpack_from("<III", e, 1)
        el = list(struct.unpack_from("<%dI" % ne, e, 13))
        nz = struct.unpack_from("<I", e, 13 + 4 * ne)[0]
        min_lvl, draft_req = struct.unpack_from("<II", e, 17 + 8 * ne)
        ok01 = (lvl == sess.account.d["level"] and cap >= 10 and el == dids and nz == ne and min_lvl <= lvl
                and draft_req == 0 and len(e) == 25 + 8 * ne)
    check("0x2101 queue eligibility before 0x2080: level, the same encounters, eligible",
          ok01 and 0x2101 in seq and seq.index(0x2101) < i80)

    # ---- account screens --------------------------------------------------------------------------------------
    t = time.monotonic()
    u.send_event(SVC, 0x20BA, b"")
    got = u.wait_for(lambda e: e[0] >= t and e[2] == 0x2090)
    check("0x20BA -> amplifier sets 0x2090", got)
    tot = struct.unpack_from("<III", got[0][3], 1) if got else ()
    check("0x2090 total = the account's set slots (the client makes empty sets to edit), max = amplifier_set_max",
          tot and tot[0] == ic["amplifier_set_slots"] and tot[1] == ic["amplifier_set_max"] and tot[2] == 0, tot)
    owned_slot = [e for e in u.since(0, 0x20B8)]
    check("0x20B8 lists the set slot item (type 5) for the 'buy a set slot' row",
          owned_slot and struct.pack("<III", 0x49000AA2, 2, 5) in owned_slot[0][3])
    t = time.monotonic()
    u.send_event(SVC, 0x2106, str8("NA"))
    boutique = u.wait_for(lambda e: e[0] >= t and e[2] == 0x2107)
    n_prices = struct.unpack_from("<I", boutique[0][3], 1)[0] if boutique else 0
    check("0x2106 -> boutique prices 0x2107", n_prices > 300, n_prices)
    entries, whole = boutique_entries(boutique[0][3]) if boutique else ([], False)
    slot_e = [(b, c, p) for b, d, c, p in entries if d == 0x49000AA2]
    aug_e = [(c, p) for _b, d, c, p in entries if d == 0x40000689]
    check("0x2107 names every price 'SC' / 'HC' (BoutiqueDataManager keeps no other, store-fix.md 3.1); the set slot "
          "has both under one boutique id; an augment both too (2026-10-29: every item also for Crisis Coins)",
          whole and {c for _b, _d, c, _p in entries} == {"SC", "HC"}
          and sorted(slot_e) == [(0x0B00000049000AA2, "HC", ic["store_prices_hc"]["amp_slot"]),
                                 (0x0B00000049000AA2, "SC", ic["store_prices"]["amp_slot"])]
          and sorted(aug_e) == sorted([("SC", ic["store_prices"]["augment"]), ("HC", ic["store_prices_hc"]["augment"])]),
          (whole, slot_e, aug_e))
    # save an amplifier set (Gaslight Batman's default: 4 augments + 3 mods)
    amps = [0x40000652, 0x400006B0, 0x400006BE, 0x40000693, 0x40000824, 0x400008B0, 0x40000AC7]
    t = time.monotonic()
    u.send_event(SVC, 0x20FC, M.amplifier_set(0, 0, 0x40000086, "Mine", 0x130037AB, amps))
    check("0x20FC save -> 0x20C7 stored", u.wait_for(lambda e: e[0] >= t and e[2] == 0x20C7))
    t = time.monotonic()
    u.send_event(SVC, 0x20FC, M.amplifier_set(0, 0, 0x40000086, "Twice", 0, [amps[0], amps[0]]))
    check("a set with a DID twice -> 0x2052 error", u.wait_for(lambda e: e[0] >= t and e[2] == 0x2052))
    # store (store-fix.md 3): the client's dialogs send "SC" / "HC" with the cost the 0x2107 gave them
    aug = 0x40000689
    bid = 0x0B00000000000000 | aug
    aug_price = ic["store_prices"]["augment"]
    t = time.monotonic()
    u.send_event(SVC, 0x210E, purchase(bid, aug, "SC", aug_price))
    got = u.wait_for(lambda e: e[0] >= t and e[2] == 0x2081)     # the batch's last message
    time.sleep(0.15)
    after = ids(u.since(t))
    check("0x210E 'SC' at the 0x2107 price -> 0x210C, ownables 0x20B8, balance 0x2081; no 0x2095 ribbon "
          "(store_purchase_ribbon), no error", got and {0x210C, 0x20B8} <= set(after)
          and not {0x2095, 0x210D, 0x210F} & set(after), [hex(x) for x in after])
    check("... paid in Merits", sess.account.wallet["soft"] == merits0 - aug_price
          and sess.account.wallet["hard"] == 200, sess.account.wallet)
    t = time.monotonic()
    u.send_event(SVC, 0x210E, struct.pack("<QI", bid, aug) + str8("Merits") + struct.pack("<I", aug_price) + str8(""))
    check("the fase3-ie currency name 'Merits' is still accepted -> 0x210C, paid in Merits",
          u.wait_for(lambda e: e[0] >= t and e[2] == 0x210C) and sess.account.wallet["soft"] == merits0 - 2 * aug_price,
          sess.account.wallet)
    soft0, coins0 = sess.account.wallet["soft"], sess.account.wallet["hard"]
    t = time.monotonic()
    u.send_event(SVC, 0x210E, purchase(bid, aug, "SC", -1))
    err = u.wait_for(lambda e: e[0] >= t and e[2] == 0x210D)
    again = u.wait_for(lambda e: e[0] >= t and e[2] == 0x2107)
    check("0x210E at price 0xFFFFFFFF (the client had no price) -> 0x210D general error + a fresh 0x2107; no 0x210F "
          "(no UI listens to it), nothing paid",
          err and struct.unpack_from("<QI", err[0][3], 1) == (bid, M.PURCHASE_GENERAL_ERROR) and again
          and not u.since(t, 0x210F) and not u.since(t, 0x210C) and sess.account.wallet["soft"] == soft0,
          (err and err[0][3].hex(), ids(u.since(t))))
    t = time.monotonic()
    u.send_event(SVC, 0x210E, purchase(bid, aug, "HC", -1))
    err = u.wait_for(lambda e: e[0] >= t and e[2] == 0x210D)
    check("0x210E 'HC' for an augment (no Crisis Coin price) -> 0x210D, nothing paid",
          err and not u.since(t, 0x210C) and sess.account.wallet["hard"] == coins0, sess.account.wallet)
    # store_price_mismatch = "changed": the fase3-ie 0x210F, confirmed with 0x2110 at the server's price
    ic["store_price_mismatch"] = "changed"
    t = time.monotonic()
    u.send_event(SVC, 0x210E, purchase(bid, aug, "SC", 1))
    check("store_price_mismatch = 'changed': a stale price -> 0x210F price changed",
          u.wait_for(lambda e: e[0] >= t and e[2] == 0x210F) and not u.since(t, 0x210D))
    t = time.monotonic()
    u.send_event(SVC, 0x2110, struct.pack("<QQI", 0, bid, aug) + str8("SC") + struct.pack("<I", aug_price))
    check("0x2110 confirm -> 0x210C, paid the server's price",
          u.wait_for(lambda e: e[0] >= t and e[2] == 0x210C) and sess.account.wallet["soft"] == soft0 - aug_price,
          sess.account.wallet)
    ic["store_price_mismatch"] = "error"
    ic["store_boutique_currency_keys"] = False
    t = time.monotonic()
    u.send_event(SVC, 0x2106, str8("en"))
    old = u.wait_for(lambda e: e[0] >= t and e[2] == 0x2107)
    ic["store_boutique_currency_keys"] = True
    old_e = boutique_entries(old[0][3])[0] if old else []
    check("store_boutique_currency_keys = false: the fase3-ie 0x2107 (every price named store_currency, no HC entry)",
          old_e and {c for _b, _d, c, _p in old_e} == {ic["store_currency"]}
          and len(old_e) == len([e for e in entries if e[2] == "SC"]), (len(old_e), old_e[:2]))
    # amplifier sets as the client's Assembler saves them: a client-only set's id (slot 3), no champion
    spent0 = sess.account.wallet["soft"]
    t = time.monotonic()
    u.send_event(SVC, 0x20FC, M.amplifier_set(3, 0, 0, "Any", 0x130037AA, amps))
    got = u.wait_for(lambda e: e[0] >= t and e[2] == 0x20C7)
    check("0x20FC for client-only set 3 -> 0x20C7 with slot 3",
          got and struct.unpack_from("<I", got[0][3], 1)[0] == 3 and len(sess.account.amplifier_sets()) == 2)
    add, pct = sess.account.amplifier_bonuses(sess.adata, sess.account.amplifier_sets(0)[-1])
    check("the set's augments give stats from their records (op 9 add / op 10 percent)", add and (add or pct),
          (add, pct))
    # one more set slot with Crisis Coins (the slot's DualCurrencyPurchaseDialog sends "HC") -> 0x2090 total + 1
    slot_bid = 0x0B00000000000000 | 0x49000AA2
    price, price_hc = ic["store_prices"]["amp_slot"], ic["store_prices_hc"]["amp_slot"]
    soft0, coins0, slots0 = sess.account.wallet["soft"], sess.account.wallet["hard"], sess.account.d["max_amplifier_sets"]
    t = time.monotonic()
    u.send_event(SVC, 0x210E, purchase(slot_bid, 0x49000AA2, "HC", price_hc))
    got = u.wait_for(lambda e: e[0] >= t and e[2] == 0x2090)
    check("buying a set slot with 'HC' -> 0x210C and 0x2090 with total 7, paid in Crisis Coins",
          u.since(t, 0x210C) and got and struct.unpack_from("<I", got[0][3], 1)[0] == slots0 + 1
          and sess.account.wallet["hard"] == coins0 - price_hc and sess.account.wallet["soft"] == soft0,
          sess.account.wallet)
    keep, sess.account.wallet["hard"] = sess.account.wallet["hard"], price_hc - 1
    t = time.monotonic()
    u.send_event(SVC, 0x210E, purchase(slot_bid, 0x49000AA2, "HC", price_hc))
    err = u.wait_for(lambda e: e[0] >= t and e[2] == 0x210D)
    check("... without the Crisis Coins -> 0x210D insufficient funds 0x10000069, no slot",
          err and struct.unpack_from("<QI", err[0][3], 1) == (slot_bid, M.PURCHASE_INSUFFICIENT_FUNDS)
          and not u.since(t, 0x210C) and sess.account.d["max_amplifier_sets"] == slots0 + 1,
          err and err[0][3].hex())
    sess.account.wallet["hard"] = keep
    # the SHOP screen: URL.Store in AuthSelect, the page, a purchase from the page
    auth = server.auth_select()
    check("AuthSelect: URL.Store nested as the client's NameValuePairArray reads it (store-fix.md 2.3), after "
          "loginTicket, before randomID", auth_pairs(SOAP_ENVELOPE.format(body=auth)).get("URL.Store", "")
          == server.store_url() and server.store_url().endswith("/store")
          and auth.index("</loginTicket>") < auth.index("<nameValuePairs><nameValuePairs>") < auth.index("<randomID>"),
          auth)
    ic["auth_pairs_nested"] = False
    flat = server.auth_select()
    ic["auth_pairs_nested"] = True
    check("auth_pairs_nested = false: the fase3-ie flat pair, which the client reads as an empty array",
          "<nameValuePairs><name>URL.Store</name>" in flat and auth_pairs(SOAP_ENVELOPE.format(body=flat)) == {})
    import urllib.request
    import urllib.error
    base = f"http://{s['host']}:{s['soap_port']}"
    page = urllib.request.urlopen(base + "/store", timeout=10).read().decode()
    # 2026-10-29: the card page (store_page_style "cards"): tabs, a card per item with its prices in its data-item
    check("GET /store -> the store page (wallet, tabs, set slot card with its Merit and Crisis Coin prices)",
          "Amplifier Set Slot" in page and "Crisis Coins" in page and 'data-tab="slots"' in page
          and 'data-tab="amps"' in page and 'data-tab="champions"' in page
          and f"&quot;cur&quot;: &quot;SC&quot;, &quot;value&quot;: {price}" in page
          and f"&quot;cur&quot;: &quot;HC&quot;, &quot;value&quot;: {price_hc}" in page)
    first = sess.roster()[0]["variant"]
    with urllib.request.urlopen(base + f"/store/img/icon/{first:#010x}.png", timeout=60) as r:
        ok_png = r.status == 200 and r.headers.get("Content-Type") == "image/png" and r.read(8) == b"\x89PNG\r\n\x1a\n"
    try:
        urllib.request.urlopen(base + "/store/img/card/0x13001980.jpg", timeout=10)
        stranger = 200
    except urllib.error.HTTPError as e:
        stranger = e.code
    check("store pictures: a champion's portrait from the installed packs; a DID outside the roster is refused",
          ok_png and stranger == 404, stranger)
    # 2026-10-29 (store_amp_composed_icons): an augment's and a mod's icon composed as the client's amplifier screen
    # does (brand background + stat corners / artifact icon + brand badge), 256 px with alpha
    amp_ok = {}
    for amp in (0x40000689, 0x40000824):
        with urllib.request.urlopen(base + f"/store/img/amp/{amp:#010x}.png", timeout=60) as r:
            body = r.read()
        amp_ok[f"{amp:#x}"] = (r.status == 200 and body[:8] == b"\x89PNG\r\n\x1a\n"
                               and struct.unpack(">II", body[16:24]) == (256, 256))
    from ics import store_web
    layers = store_web._amp_icon(sess, 0x40000689)
    check("store pictures: augment 0x40000689 = Holt background 0x13001F88 + Power Armor 0x13001F8C (bottom-right) + "
          "Attack Armor 0x13001F82 (top-left); a mod gets its artifact + brand badge; both served as 256 px PNGs",
          all(amp_ok.values()) and layers == [0x13001F88, 0x13001F8C, 0x13001F82]
          and isinstance(store_web._amp_icon(sess, 0x40000824), list), (amp_ok, layers))
    t = time.monotonic()
    before = sess.account.wallet["soft"]
    req = urllib.request.Request(base + "/store/buy", data=b"did=0x49000aa2", method="POST")
    after_page = urllib.request.urlopen(req, timeout=10).read().decode()
    got = u.wait_for(lambda e: e[0] >= t and e[2] == 0x2090)
    check("POST /store/buy (set slot) -> paid, 0x210C + 0x2090 on the login connection, page shows 'bought'",
          sess.account.wallet["soft"] == before - price and got and u.since(t, 0x210C) and "Purchase complete" in after_page,
          (before, sess.account.wallet["soft"]))
    t = time.monotonic()
    coins1 = sess.account.wallet["hard"]
    req = urllib.request.Request(base + "/store/buy", data=b"did=0x49000aa2&cur=HC", method="POST")
    after_page = urllib.request.urlopen(req, timeout=10).read().decode()
    got = u.wait_for(lambda e: e[0] >= t and e[2] == 0x2090)
    check("POST /store/buy cur=HC (set slot) -> paid in Crisis Coins, 0x210C + 0x2090, page shows 'bought'",
          sess.account.wallet["hard"] == coins1 - price_hc and got and u.since(t, 0x210C) and "Purchase complete" in after_page,
          (coins1, sess.account.wallet["hard"]))
    t = time.monotonic()
    u.send_event(0x0600000000000415, 0x95, b"")
    time.sleep(0.3)
    logs = {}
    for name in ("server.log", "unhandled.log"):
        try:
            with open(os.path.join(log._dir or "", name), encoding="utf-8") as f:
                logs[name] = f.read()
        except OSError:
            logs[name] = ""
    check("client event 0x95 (one SHOP open) -> a server.log line, no answer (0xC2), not in unhandled.log",
          "web ticket request (0x95)" in logs["server.log"] and "event 0x0095" not in logs["unhandled.log"]
          and not u.since(t, 0xC2))
    sess.account.wallet["soft"] += spent0 - sess.account.wallet["soft"]   # the match-end check counts from spent0
    t = time.monotonic()
    u.send_event(SVC, 0x2093, struct.pack("<II", 0x13003A6C, 2))
    check("0x2093 protector icon -> 0x2154", u.wait_for(lambda e: e[0] >= t and e[2] == 0x2154))
    for ask, answer, name in ((0x212E, 0x211F, "achievement banners"), (0x211D, 0x2120, "achievements"),
                              (0x2178, 0x219E, "account standings"), (0x2193, 0x219F, "static standings"),
                              (0x2116, 0x2115, "encounter stats")):
        t = time.monotonic()
        u.send_event(SVC, ask, b"")
        check(f"{ask:#x} -> {name} {answer:#x}", u.wait_for(lambda e: e[0] >= t and e[2] == answer))
    t = time.monotonic()
    u.send_event(SVC, 0x21A4, struct.pack("<I", ENCOUNTER))
    check("0x21A4 -> leaderboards 0x21A2 + 0x21A3",
          u.wait_for(lambda e: e[0] >= t and e[2] == 0x21A2) and u.wait_for(lambda e: e[0] >= t and e[2] == 0x21A3))
    u.send_event(SVC, 0x216E, str8("User.CameraLocked") + wstring("true") + struct.pack("<I", 0x10000C33))
    u.send_event(SVC, 0x216E, str8("User.ZoomLevel") + wstring("3") + struct.pack("<I", 0x10000A0E))
    for _ in range(50):
        if len(sess.account.d["preferences"]) >= 2:
            break
        time.sleep(0.05)
    check("0x216E preferences kept on the account",
          sess.account.d["preferences"].get("User.CameraLocked") == [0x10000C33, "true"])
    check("... and sent back as server options at the next login",
          {n for n, _t, _v in sess.account.server_options()} == {"User.CameraLocked", "User.ZoomLevel"})
    t = time.monotonic()
    u.send_event(SVC, 0x20A6, struct.pack("<I", 1) + string_info("Wrapper"))
    check("0x20A6 channel list -> member list 0x2135", u.wait_for(lambda e: e[0] >= t and e[2] == 0x2135))
    t = time.monotonic()
    u.send_event(SVC, 0x20F6, string_info("Wrapper") + wstring("hello"))
    check("0x20F6 say -> echoed (0x2183)", u.wait_for(lambda e: e[0] >= t and e[2] == 0x2183))

    # ---- queue, leave, queue again -----------------------------------------------------------------------------
    t = time.monotonic()
    u.send_event(SVC, 0x20EB, struct.pack("<II", 0, 0) + b"\x01" + struct.pack("<i", -1))
    check("0x20EB for encounter 0 (template not loaded on the client) -> 0x20E0 + 0x20FF list again, no queue",
          u.wait_for(lambda e: e[0] >= t and e[2] == 0x20E0) and u.wait_for(lambda e: e[0] >= t and e[2] == 0x20FF)
          and not u.since(t, 0x20C0) and sess.phase == "MENU", sess.phase)
    upd = u.since(t, 0x20FF)
    check("0x20FF = the four lists of 0x2024", upd and upd[0][3][1:] == b[1:len(upd[0][3])])
    key = struct.pack("<II", ENCOUNTER, QFLAGS) + b"\x00" + struct.pack("<i", -1)
    t = time.monotonic()
    u.send_event(SVC, 0x20EB, key)
    # the first join reads the encounter templates / bot pools (slow while the pack index is being built)
    check("0x20EB -> joined queue 0x20C0", u.wait_for(lambda e: e[0] >= t and e[2] == 0x20C0, 60))
    u.send_event(SVC, 0x20C3, b"")
    check("0x20C3 leave queue -> 0x20E0", u.wait_for(lambda e: e[0] >= t and e[2] == 0x20E0))
    time.sleep(0.5)
    check("no match found after leaving", not u.since(t, 0x20FA) and sess.phase == "MENU", sess.phase)
    t = time.monotonic()
    u.send_event(SVC, 0x20EB, key)
    check("queue again -> 0x20C0, then match found 0x20FA",
          u.wait_for(lambda e: e[0] >= t and e[2] == 0x20C0) and u.wait_for(lambda e: e[0] >= t and e[2] == 0x20FA))
    t_acc = time.monotonic()
    u.send_event(SVC, 0x20CA, b"")
    check("accept -> 0x20AD players accepted, 0x2028 room, referral",
          u.wait_for(lambda e: e[0] >= t_acc and e[2] == 0x2028)
          and u.wait_for(lambda e: e[0] >= t_acc and e[2] == 0x20AD))
    time.sleep(0.2)
    check("referral packet 0x800", any(p[1] == 0x800 and p[0] >= t_acc for p in u.packets))

    # ---- game connection, champion select ------------------------------------------------------------------------
    g = Client(s["game_port"])
    g.sock.sendall(b"\x00" * 40)
    time.sleep(0.3)
    check("no 0x20AF before the countdown's end (it stops the lobby's costume / portrait packs)",
          not u.since(t_acc, 0x20AF))
    t = time.monotonic()
    g.send_event(SVC, 0x20F2, struct.pack("<QIBB", PLAYER, 0, 0, 0) + struct.pack("<I", 0))
    u.wait_for(lambda e: e[0] >= t and e[2] == 0x204A)
    time.sleep(0.3)
    lob = u.since(t)
    slots = [e for e in lob if e[2] == 0x2029]
    check("lobby: details 0x204C, 10 slots 0x2029, Stolen Powers 0x2004, amplifier set 0x204A",
          {0x204C, 0x2004, 0x204A} <= set(ids(lob)) and len(slots) == 10, (len(slots), [hex(x) for x in ids(lob)]))
    det = next((e for e in lob if e[2] == 0x204C), None)
    n_owned = struct.unpack_from("<I", det[3], 1 + 16 + 8 + 8) [0] if det else 0
    owned = [struct.unpack_from("<IIIBI", det[3], 1 + 16 + 8 + 8 + 4 + 17 * k) for k in range(n_owned)] if det else []
    check("0x204C lists the owned champions (type 1) and costumes (type 4): the skin picker's source",
          sum(1 for o in owned if o[2] == 1) >= 54 and sum(1 for o in owned if o[2] == 4) >= 100,
          (len(owned), owned[:3]))
    check("champion select stays open: no 0x2016 (to the loading screen) / 0x206D before the launch",
          not {0x2016, 0x206D} & set(ids(u.since(t_acc))), [hex(x) for x in ids(u.since(t_acc))])
    m = sess.match
    check("9 bots with champions from the encounter's pool, 5 per team",
          m and m.lobby and sum(1 for x in m.lobby.slots if x.bot) == 9
          and sorted(x.team for x in m.lobby.slots).count(1) == 5)
    skinned = {c["variant"]: [x["variant"] for x in c.get("costume_info", [])] for c in server.data.roster}
    bots = [x.champion for x in m.lobby.slots if x.bot]
    check("bot_random_skin: every bot whose champion has costumes plays one of them, never the base look",
          bots and all((server.data.base_variant(v) not in skinned or not skinned[server.data.base_variant(v)])
                       or v in skinned[server.data.base_variant(v)] for v in bots), [hex(v) for v in bots])
    pick, skin = next((c["variant"], c["costume_info"][0]["variant"]) for c in server.data.roster
                      if server.data.kit(c["variant"]) and c.get("costume_info")
                      and c["variant"] not in m.lobby.champions())
    t = time.monotonic()
    g.send_event(SVC, 0x20E4, struct.pack("<IBI", pick, 1, 0))
    got = u.wait_for(lambda e: e[0] >= t and e[2] == 0x2029)
    check("0x20E4 pick -> my slot 0x2029 with that champion",
          got and struct.unpack_from("<I", got[0][3], 1 + 1 + 16 + len(string_info("FlowTester")) + 1)[0] == pick,
          hex(pick))
    t = time.monotonic()
    g.send_event(SVC, 0x2102, struct.pack("<IB", 0x20000, 1))
    check("0x2102 with 0x20000 = custom-match draft toggle -> 0x2103", u.wait_for(lambda e: e[0] >= t and e[2] == 0x2103))
    t = time.monotonic()
    g.send_event(SVC, 0x207D, struct.pack("<II", 1, 0x48000529))
    sp = u.wait_for(lambda e: e[0] >= t and e[2] == 0x2004)
    check("0x207D Stolen Power -> 0x2004 with it", sp and struct.unpack_from("<I", sp[0][3], 9)[0] == 0x48000529)
    t_lock = time.monotonic()
    g.send_event(SVC, 0x208E, struct.pack("<IBI", pick, 1, 0))
    warn = u.wait_for(lambda e: e[0] >= t_lock and e[2] == 0x204B)
    times = struct.unpack_from("<dd", warn[0][3], 1) if warn else (0, 0)
    check("lock 0x208E -> launch warning 0x204B with f64 game-clock times (the costume countdown)",
          warn and abs(times[0] - time.time()) < 5 and 1.0 <= times[1] - times[0] <= 2.0, times)
    t = time.monotonic()
    g.send_event(SVC, 0x20E4, struct.pack("<IBI", skin, 1, 0))
    got = u.wait_for(lambda e: e[0] >= t and e[2] == 0x2029)
    check("costume pick after the lock -> my slot 0x2029 with the costume",
          got and struct.unpack_from("<I", got[0][3], 1 + 1 + 16 + len(string_info("FlowTester")) + 1)[0] == skin,
          hex(skin))
    check("at the countdown's end: 0x2016 (to the loading screen) and 0x206D, no 0x2053 (view-match mode)",
          u.wait_for(lambda e: e[0] >= t_lock and e[2] == 0x2016, 10)
          and u.wait_for(lambda e: e[0] >= t_lock and e[2] == 0x206D, 2) and not u.since(t_lock, 0x2053))
    enter = u.wait_for(lambda e: e[0] >= t_lock and e[2] == 0x20AF)
    n_champs = struct.unpack_from("<I", enter[0][3], 5)[0] if enter else 0
    check("at the countdown's end 0x20AF names the 10 champions (player + 9 bots)", n_champs >= 10, n_champs)
    packs_sent = []
    if enter:
        body = enter[0][3]
        at = 9 + 4 * n_champs
        packs_sent = list(struct.unpack_from(f"<{struct.unpack_from('<I', body, at)[0]}I", body, at + 4))
    resident = set(server.cfg["ics"]["resident_packs"])
    check("0x20AF names no start-up pack (they would be unloaded at the match's end)",
          packs_sent and not resident & set(packs_sent), [hex(p) for p in packs_sent])

    # ---- loading, the match, its end -----------------------------------------------------------------------------
    g.send_event(SVC, 0x20D5, struct.pack("<I", 30))
    check("loading percent -> 0x2031", u.wait_for(lambda e: e[0] >= t_lock and e[2] == 0x2031))
    g.send_event(SVC, 0xCC, b"")                 # level loaded (35 %): the objects go out (objects_on_level_loaded)
    objs = u.wait_for(lambda e: e[0] >= t_lock and e[2] == 0x4 and e[1] == CHAMPION, 5)
    check("the picked costume is created", objs and object_class(objs[0][3]) == skin,
          objs and hex(object_class(objs[0][3])))
    t_load = time.monotonic()
    g.send_event(PLAYER, 0x2, bytes.fromhex("5e010010") + bytes(8))
    check("in the world (PLAYING)", u.wait_for(lambda e: sess.phase == "PLAYING", 3))
    ch = sess.match.world.champion if sess.match and sess.match.world else None
    check("the lobby's amplifier set (the 'Any' set) gives its augment stats to the champion",
          ch is not None and (ch.amp_add or ch.amp_pct) and sess.match.lobby.me.amp.get("name") == "Any",
          ch and (ch.amp_add, ch.amp_pct))
    # 2026-10-28 15:00 (tester report 2026-10-28 15:00; docs/re-notes/object-update-bundles.md 11.4 / 13): [ics]
    # object_update_mode "delta" = once linked and in the world, the champion's per-tick updates are motion-only states,
    # with no full champion bundle and no player-object bundle (Session._tick sent both every tick)
    if str(ic.get("object_update_mode", "delta")) == "delta" and ch is not None:
        u.wait_for(lambda e: bool(getattr(sess.match, "linked", False)), 2)
        window = ic.get("delta_create_window")
        ic["delta_create_window"] = 0.0       # this whole load fits in 0.5 s (a real one takes seconds)
        t_walk = time.monotonic()
        ch.dest, ch.path = [ch.pos[0] + 2.0, ch.pos[1], ch.pos[2]], []
        time.sleep(0.35)
        ic["delta_create_window"] = window
        # from the walk's first state on (the in-world _objects bundles may still be on their way when PLAYING is seen)
        evs = u.since(t_walk, 0x4, CHAMPION)
        c4 = [batch_kinds(e[3]) for e in evs]
        first = next((i for i, k in enumerate(c4) if k == [0xB0]), None)
        walk = c4[first:] if first is not None else []
        p4 = u.since(evs[first][0], 0x4, PLAYER) if first is not None else []
        check("in the world: the champion walks by motion-only states (0x4 with only the 0xB0), no full champion bundle "
              "and no player-object bundle per tick", len(walk) >= 3 and all(k == [0xB0] for k in walk) and not p4,
              (c4[:6], len(p4)))
    end = u.wait_for(lambda e: e[0] >= t_load and e[2] == 0x219E, 6)
    time.sleep(0.2)
    seq = ids(u.since(t_load))
    want = [0x2038, 0x2, 0x214B, 0x2045, 0x2120, 0x2190, 0x2081, 0x2080, 0x20B9, 0x2104, 0x2188, 0x2090, 0x219F,
            0x219E]
    check("match end: 0x2038, VICTORY, 0x1000000E, 0x214B, 0x2045, 0x2120, 0x2190, 0x2081, 0x2080, 0x20B9, 0x2104, "
          "0x2188, 0x2090, 0x219F, 0x219E", end and all(x in seq for x in want), [hex(x) for x in seq if x != 0x4])
    st = [e for e in u.since(t_load) if e[2] == 0x219E]
    vals = struct.unpack_from("<10I", st[0][3], 1) if st and len(st[0][3]) >= 41 else ()
    check("0x219E in the handler's order: last played encounter first, rank / previous rank small (end-screen-crash)",
          vals and vals[0] == ENCOUNTER and vals[1] < 64 and vals[2] < 64, [hex(v) for v in vals])
    # tester report 2026-10-29 21:10 (aggro-recall-scorepanel.md 3): 0x2080 in the handler's order, cumulative XP text
    a80 = [e for e in u.since(t_load) if e[2] == 0x2080]
    v80 = struct.unpack_from("<6Iff", a80[-1][3], 1) if a80 and len(a80[-1][3]) >= 33 else ()
    acc = sess.account
    lv, cur = acc.d["level"], acc.d["xp"]
    below = sum(acc.xp_to_next(x) for x in range(1, lv))
    check("0x2080 at the match end: level | prev | total | earned | bonus | to next (0xA7DFB0), cumulative totals",
          v80 and v80[0] == lv and v80[2] == below + cur and v80[3] > 0 and v80[5] == below + acc.xp_to_next(lv)
          and 0.0 <= v80[6] <= 1.0, v80)
    old80 = struct.unpack_from("<6I", M.account_level(5, 4, 900, 100, 20, 0, layout="old")[-32:], 0) \
        if hasattr(M, "account_level") else ()
    check("[ics] account_level_layout \"old\" keeps the fase3-in order (to next before total)",
          old80[:4] == (5, 4, 900, 100), old80)
    notice = [e for e in u.since(t_load, 0x2) if e[3][1:5] == struct.pack("<I", 0x1000000E)]
    check("match-ended notice: our team wins", notice and struct.unpack_from("<I", notice[0][3], 9)[0] == ic["team"])
    a = sess.account
    check("account XP, champion XP, Merits and the match are recorded",
          a.d["stats"].get(f"0x{ENCOUNTER:08X}", {}).get("won") == 1 and a.champion(pick)["xp"] > 0
          and a.wallet["soft"] > spent0, (a.d["stats"], a.champion(pick), a.wallet, spent0))
    t = time.monotonic()
    u.send_event(SVC, 0x2124, b"")
    time.sleep(0.2)
    g.send_event(0x0600000000000008, 0x12D, b"")
    check("left the world 0x12D -> back in the menu, no exit lobby 0x2021 (timeline-kda-endscreen 3)",
          u.wait_for(lambda e: sess.phase == "MENU", 3) and not u.since(t, 0x2021), sess.phase)
    check("back in the menu: the encounter list again 0x20FF and eligibility 0x2101 (the menu rebuilds its maps)",
          u.wait_for(lambda e: e[0] >= t and e[2] == 0x20FF, 3) and u.wait_for(lambda e: e[0] >= t and e[2] == 0x2101))
    check("back in the menu: champions 0x20B8 and champion levels / last used 0x209D again (2026-10-28 tester)",
          u.wait_for(lambda e: e[0] >= t and e[2] == 0x20B8, 3) and u.wait_for(lambda e: e[0] >= t and e[2] == 0x209D))
    # tester report 2026-10-29 23:03 (scorecard-accolades-meteor-aura.md 1) + 2026-10-30 11:23
    # (scorecard-panel-turret-head.md 1): the scorecard's 0x212E -> the match-end 0x2104 again (its trailing u32 = the
    # encounter, so 0xA7E0A0 hands Flash the accolades notice live) [ics] scorecard_accolades_resend s later, once
    first04 = [e for e in u.since(t_load) if e[2] == 0x2104]
    enc04 = struct.unpack_from("<I", first04[0][3], len(first04[0][3]) - 5)[0] if first04 else None
    check("0x2104 at the match end carries the encounter after its accolade lists (0xA7E0A0 param_21, "
          "[ics] scorecard_level_encounter)", enc04 == ENCOUNTER and first04[0][3][-1] == 0, enc04)
    t = time.monotonic()
    u.send_event(SVC, 0x212E, b"")
    late = u.wait_for(lambda e: e[0] >= t and e[2] == 0x2104, 4)
    lat = [e for e in u.since(t) if e[2] == 0x2104]
    check("scorecard: 0x212E -> 0x211F at once, the same 0x2104 again ~scorecard_accolades_resend s later, once, "
          "no late 0x2188 (an empty one never reaches Flash, 0xA61DA0)",
          late and len(lat) == 1 and first04 and lat[0][3] == first04[0][3] and not u.since(t, 0x2188)
          and lat[0][0] - t >= float(ic.get("scorecard_accolades_resend", 1.5)) - 0.2
          and u.since(t, 0x211F) and getattr(sess, "late_accolades", 1) is None,
          (len(lat), [round(e[0] - t, 2) for e in lat]))
    u.send_event(SVC, 0x212E, b"")
    time.sleep(float(ic.get("scorecard_accolades_resend", 1.5)) + 0.4)
    check("scorecard: a later 0x212E (another screen) sends no 0x2104", len(u.since(t, 0x2104)) == 1)
    # tester report 2026-10-30 14:51 (scorecard-rewards-side-panel.md): the original's side panel (result, duration,
    # Protector XP, Merit, Champion XP) has no clip on this client's Scorecard view -> four chat lines (0x2183), once
    u.wait_for(lambda e: e[0] >= t and e[2] == 0x2183, 3)
    chat_lines = [e for e in u.since(t) if e[2] == 0x2183]
    check("scorecard: 0x212E -> the result / duration / rewards as 4 chat lines (0x2183) ~scorecard_chat_summary_delay "
          "s later, once (scorecard_chat_summary)",
          len(chat_lines) == 4 and "Match Duration".encode("utf-16-le") in chat_lines[0][3]
          and "Merit".encode("utf-16-le") in chat_lines[2][3]
          and chat_lines[0][0] - t >= float(ic.get("scorecard_chat_summary_delay", 2.5)) - 0.2
          and getattr(sess, "scorecard_chat", 1) is None, (len(chat_lines),))
    with open(path, encoding="utf-8") as f:
        stored = json.load(f)
    check("the account file holds the result", stored["stats"].get(f"0x{ENCOUNTER:08X}", {}).get("played") == 1
          and ENCOUNTER in stored["encounters"]["completed"] and stored["amplifier_sets"])

    # ---- a custom match --------------------------------------------------------------------------------------------
    g.sock.close()
    time.sleep(0.3)
    t = time.monotonic()
    u.send_event(SVC, 0x202D, struct.pack("<II", 0x40000B6A, 0))
    check("0x202D from the menu = create custom match -> 0x2012, 0x2109, 0x2103",
          u.wait_for(lambda e: e[0] >= t and e[2] == 0x2012) and u.wait_for(lambda e: e[0] >= t and e[2] == 0x2109))
    t = time.monotonic()
    u.send_event(SVC, 0x2108, struct.pack("<I", ENCOUNTER))
    check("0x2108 set encounter -> 0x2109", u.wait_for(lambda e: e[0] >= t and e[2] == 0x2109))
    t = time.monotonic()
    u.send_event(SVC, 0x2057, b"")
    check("0x2057 launch -> 0x2040, then the lobby flow (0x2028 + referral)",
          u.wait_for(lambda e: e[0] >= t and e[2] == 0x2040, 60) and u.wait_for(lambda e: e[0] >= t and e[2] == 0x2028)
          and sess.match and sess.match.custom and sess.match.lobby)

    u.sock.close()
    print(f"\n{sum(results)}/{len(results)} checks passed")
    return 0 if all(results) else 1


if __name__ == "__main__":
    code = main()
    sys.stdout.flush()
    os._exit(code)                 # the server's daemon threads may still be printing
