"""The in-match shop (ics/shop.py) on the game's own artifact data: buy, upgrade a tier (paying the difference,
reusing the slot), stats on the champion, sell, and the refusals the client's own checks give.

    python tests\\test_shop.py
"""
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from ics import config                       # noqa: E402
from ics import messages as M                # noqa: E402
from ics import shop as S                    # noqa: E402
from ics.gamedata import Data                # noqa: E402
from ics.world import STAT_ATTACK_DAMAGE, STAT_HEALTH, World    # noqa: E402

ENCOUNTER = 0x40000991
SPAWN = [1, 0x13, 0xCB, 0, 18.7, 60.4, 200.3]
results = []


def check(name, cond, detail=""):
    results.append(bool(cond))
    print(f"  {'ok  ' if cond else 'FAIL'} {name}" + (f"  ({detail})" if detail and not cond else ""))


def main():
    cfg = config.load()
    cfg["ics"]["trace_scripts"] = False
    data = Data(cfg.game_dir)
    sent = []
    w = World(data, cfg, ENCOUNTER, SPAWN, send=lambda label, d: sent.append(label), schedule=lambda d, fn: None,
              log=lambda t: None)
    w.create_champion(cfg["ics"]["champion"], SPAWN)
    ch = w.champion
    check("champion stats from its stats record (455 health, 47 attack damage)",
          ch.max_health == 455 and round(ch.stats[STAT_ATTACK_DAMAGE]) == 47, (ch.max_health, ch.stats.get(STAT_ATTACK_DAMAGE)))
    shop = S.Shop(w, ENCOUNTER)
    check("the encounter's shop list read from the data (210)", len(shop.offered) == 210, len(shop.offered))

    # a line of three tiers: Batman's Utility Belt (3) 0x4000048B <- (2) <- (1)
    t3 = 0x4000048B
    t2 = data.artifact(t3)["prev"]
    t1 = data.artifact(t2)["prev"]
    c1, c2, c3 = (data.artifact(d)["cost"] for d in (t1, t2, t3))
    check("a three-tier line with rising costs", t1 and t2 and c1 < c2 < c3, (hex(t1), c1, c2, c3))

    ch.gold = 0.0
    check("no credits: refused (the client's result 7)", shop.can_buy(ch, t1) == S.TOO_EXPENSIVE)
    ch.gold = 10000.0
    health0 = ch.max_health
    check("buy tier 1", shop.buy(ch, t1) and ch.inventory[0] == t1 and ch.gold == 10000.0 - c1)
    check("its stats reach the champion", ch.max_health > health0 or ch.stats.get(STAT_ATTACK_DAMAGE, 0) > 47,
          (ch.max_health, ch.stats.get(STAT_ATTACK_DAMAGE)))
    check("the same artifact again: refused (owned)", shop.can_buy(ch, t1) == S.OWNED)
    gold = ch.gold
    check("upgrade to tier 2 pays only the difference and keeps the slot",
          shop.buy(ch, t2) and ch.inventory[0] == t2 and abs(gold - ch.gold - (c2 - c1)) < 0.01,
          (gold - ch.gold, c2 - c1, ch.inventory))
    shop.buy(ch, t3)
    check("tier 3: Health +200 and Attack Damage +30 (the data's bonuses)",
          ch.max_health == health0 + 200 and round(ch.stats[STAT_ATTACK_DAMAGE]) == 77,
          (ch.max_health, ch.stats.get(STAT_ATTACK_DAMAGE)))
    gold = ch.gold
    sell = data.artifact(t3)["sell"]
    check("sell refunds the sell value and empties the slot",
          shop.sell(ch, t3, 0) and ch.inventory[0] == 0 and abs(ch.gold - gold - sell) < 0.01)
    check("the stats go with the item", ch.max_health == health0 and round(ch.stats[STAT_ATTACK_DAMAGE]) == 47)
    check("selling what is not there: refused", not shop.sell(ch, t3, 0))

    # six slots, then a seventh item: refused unless it upgrades one of them
    tier1 = [d for d in sorted(shop.offered) if data.artifact(d) and not data.artifact(d)["prev"]][:7]
    for d in tier1[:6]:
        shop.buy(ch, d)
    check("six slots filled", all(ch.inventory), ch.inventory)
    check("a seventh item: refused (slots full)", shop.can_buy(ch, tier1[6]) == S.SLOTS_FULL)
    check("an artifact outside the encounter's list: refused",
          shop.can_buy(ch, 0x40000493) in (S.NOT_ALLOWED, S.SLOTS_FULL))

    body = M.inventory(ch.eid, ch.inventory)
    check("0x20E2 inventory message built", body and len(body) > 60)

    # an amplifier set's augments (ics.account): their own part of the stats, kept apart from the items'
    from ics import account as A
    adata = A.AccountData.of(data)
    acct = A.Account("ShopTester", cfg["ics"], path=os.devnull)
    add, pct = acct.amplifier_bonuses(adata, {"amplifiers": [0x40000689, 0x40000662]})   # FORTRESS, EARTHQUAKE
    check("augment stats from the records (FORTRESS armor x2, EARTHQUAKE health + move speed)",
          len(add) == 4 and round(add.get(STAT_HEALTH, 0), 2) == 20.05 and not pct, (add, pct))
    hp, items = ch.max_health, dict(ch.item_add)
    ch.amp_add, ch.amp_pct = add, pct
    w.recompute_stats(ch)
    check("the set's Health reaches the champion; the items' bonuses are unchanged",
          ch.max_health == round(hp + 20.05) and ch.item_add == items, (hp, ch.max_health))
    print(f"\n{sum(results)}/{len(results)} shop checks")
    return 0 if all(results) else 1


if __name__ == "__main__":
    sys.exit(main())
