"""The in-match shop (Artifact Foundry): buying, selling, upgrading, the six item slots and what the items do.

Everything about the items comes from the data (shop-items-inventory.md): the encounter's list (template
0x1000081E), each artifact's cost 0x1000036C (the cumulative price of its tier), sell value 0x1000045E, previous
tier 0x10000698, stat bonuses 0x10000684 (op 9 add, op 10 percent), passives 0x100004EA (status records) and active
ability 0x100008E1. The client shows the catalogue by itself; it sends a purchase / sale and waits for the server's
answer: the credits (champion 0x1000035E), the slots (0x20E2 to the champion) and the transaction's handle (0x2086).

The rules mirror the client's own checks (0x9D1CF0 can-buy, 0x9D0620 can-sell): a buy needs the artifact in the
encounter's list, not already owned, a free slot or a lower tier of the same line to replace, and the price
(cost - cost of the replaced lower tier); a sale refunds the sell value.
"""
from . import records
from . import script_runtime as R

OP_ADD, OP_PERCENT = 9, 10
KIND_F32 = 0x09
SLOTS = 6
FIRST_ITEM_SKILL_SLOT = 10                  # the champion's item skill slots 10-15 (0x100008E5 ...)
# items name some stats by other keys than the champion stats records (probable: same meaning)
STAT_ALIASES = {0x10000486: 0x10000432, 0x10000483: 0x10000484}
# can-buy results (client 0x9D1CF0)
CAN_BUY, NO_RECORD, CANNOT_SHOP, SLOTS_FULL, OWNED, TOO_EXPENSIVE, NOT_ALLOWED = 2, 3, 4, 5, 6, 7, 11
CAN_SELL, NOT_OWNED = 9, 10


class Shop:
    def __init__(self, world, encounter):
        self.w, self.data = world, world.data
        self.offered = set(self.data.shop_list(encounter))
        self.ic = world.ic

    # ---- rules ----------------------------------------------------------------------------------
    def lower_tier_slot(self, ch, did):
        """The slot holding a lower tier of did's line (its 0x10000698 chain), or None."""
        seen, prev = set(), (self.data.artifact(did) or {}).get("prev", 0)
        while prev and prev not in seen:
            seen.add(prev)
            if prev in ch.inventory:
                return ch.inventory.index(prev)
            prev = (self.data.artifact(prev) or {}).get("prev", 0)
        return None

    def price(self, ch, did):
        art = self.data.artifact(did)
        slot = self.lower_tier_slot(ch, did)
        paid = (self.data.artifact(ch.inventory[slot]) or {}).get("cost", 0.0) if slot is not None else 0.0
        return max(0.0, art["cost"] - paid), slot

    def can_buy(self, ch, did):
        art = self.data.artifact(did)
        if not art:
            return NO_RECORD
        if self.offered and did not in self.offered:
            return NOT_ALLOWED
        if not (ch.alive is False or self.ic.get("shop_anywhere", True)):
            return CANNOT_SHOP
        if did in ch.inventory:
            return OWNED
        cost, slot = self.price(ch, did)
        if slot is None and 0 not in ch.inventory:
            return SLOTS_FULL
        if cost > ch.gold + 1e-6:
            return TOO_EXPENSIVE
        return CAN_BUY

    # ---- transactions ---------------------------------------------------------------------------
    def buy(self, ch, did):
        result = self.can_buy(ch, did)
        if result != CAN_BUY:
            self.w.log(f"shop: buying {did:#x} refused (result {result}; {ch.gold:.0f} credits)")
            return False
        cost, slot = self.price(ch, did)
        if slot is None:
            slot = ch.inventory.index(0)
        else:
            self._unequip(ch, slot)
        ch.inventory[slot] = did
        ch.gold -= cost
        self._equip(ch, slot)
        self.w.log(f"shop: {did:#x} bought for {cost:.0f} into slot {slot} ({ch.gold:.0f} credits left)")
        return True

    def sell(self, ch, did, slot):
        if not 0 <= slot < SLOTS or ch.inventory[slot] != did:
            self.w.log(f"shop: selling {did:#x} from slot {slot} refused (not there)")
            return False
        refund = (self.data.artifact(did) or {}).get("sell", 0.0)
        self._unequip(ch, slot)
        ch.inventory[slot] = 0
        ch.gold += refund
        self.w.log(f"shop: {did:#x} sold for {refund:.0f} ({ch.gold:.0f} credits)")
        return True

    # ---- effects --------------------------------------------------------------------------------
    def _equip(self, ch, slot):
        self._restat(ch)
        art = self.data.artifact(ch.inventory[slot])
        cw = self._cast_world(ch)
        for status in art["passives"]:
            R.apply_status(cw, ch, ch, status, {})
        if art["active"]:
            skill = self.data.item_skill(art["active"])
            if skill and skill.script:
                skill.slot = FIRST_ITEM_SKILL_SLOT + slot
                ch.kit[skill.slot] = skill
                ch.ranks[skill.slot] = 1
                self.w.start_kit_slot(ch, skill.slot)
                # 2026-10-25 19:28 (tester: the consumables do nothing; no order for slots 10-15 reached the server):
                # the client enables an item's button only with its skill block in the champion's slot property
                # (0x100008E5 / E7 / E9 / EB / ED / EE, full-combat-skills.md S3.5), as for the Stolen Powers
                e = self.data.record(art["active"])
                blk = records.get(e, 0x100008E5) or records.get(e, 0x1000003F)
                if blk and self.ic.get("item_skill_blocks", True):
                    from .gamedata import _wire_entries
                    ch.__dict__.setdefault("item_blocks", {})[skill.slot] = _wire_entries(blk)

    def _unequip(self, ch, slot):
        did = ch.inventory[slot]
        art = self.data.artifact(did) if did else None
        if not art:
            return
        cw = self._cast_world(ch)
        for status in art["passives"]:
            R.remove_status(cw, ch, status)
        self.w.stop_kit_slot(ch, FIRST_ITEM_SKILL_SLOT + slot)
        getattr(ch, "item_blocks", {}).pop(FIRST_ITEM_SKILL_SLOT + slot, None)
        ch.inventory[slot] = 0
        self._restat(ch)
        ch.inventory[slot] = did            # the caller decides what the slot holds next

    def _restat(self, ch):
        add, pct = {}, {}
        for did in ch.inventory:
            art = self.data.artifact(did) if did else None
            for op, values in (art or {}).get("stats", ()):
                for stat, v in values.items():
                    stat = STAT_ALIASES.get(stat, stat)
                    table = pct if op == OP_PERCENT else add
                    table[stat] = table.get(stat, 0.0) + float(v)
        ch.item_add, ch.item_pct = add, pct
        self.w.recompute_stats(ch)
        # 2026-10-28 (store-amplifiers.md): the HUD modifiers also carry the amplifier set's bonuses (the server's
        # stats keep them apart: amp_add / amp_pct)
        amp_add, amp_pct = getattr(ch, "amp_add", {}), getattr(ch, "amp_pct", {})
        self._client_modifiers(ch, {k: add.get(k, 0.0) + amp_add.get(k, 0.0) for k in set(add) | set(amp_add)},
                               {k: pct.get(k, 0.0) + amp_pct.get(k, 0.0) for k in set(pct) | set(amp_pct)})

    def _client_modifiers(self, ch, add, pct):
        """2026-10-23 18:40 (tester: the items do not change the champion's health, attack speed, damage...): the HUD's
        stats are attributes (template base + attribute modifiers), not the stat properties; the client never applies
        an artifact's 0x10000684 itself. Each item bonus goes to the client as a modifier (0x20F0, op 9 add / 10
        percent), the old ones removed (0x20E8). The server's own numbers already hold the bonuses (recompute_stats),
        so these are not added to its combat state. [ics] item_client_modifiers."""
        if not self.ic.get("item_client_modifiers", True) or ch is not self.w.champion:
            return
        from . import messages as M
        from .combat import Handle
        for attr, n in getattr(ch, "item_mod_handles", []):
            self.w.send(f"{ch.name}: item modifier {attr:#x} removed (0x20e8)", M.attribute_modifier_remove(ch.eid, attr, n))
        handles = []
        for op, table in ((OP_ADD, add), (OP_PERCENT, pct)):
            for attr, v in sorted(table.items()):
                if not v:
                    continue
                n = Handle("modifier", ch).n
                handles.append((attr, n))
                self.w.send(f"{ch.name}: item modifier {attr:#x} op {op} {v:g} (0x20f0)",
                            M.attribute_modifier_add(ch.eid, attr, 0, n, op, KIND_F32, float(v)))
        ch.item_mod_handles = handles

    def _cast_world(self, ch):
        from .world import CastWorld
        return CastWorld(self.w, ch, None)
