# Skill buttons dimmed for lack of Will (static analysis, 2026-10-23)

Tester report 2026-10-23: in a match Gaslight Batman's skill buttons never dim when he lacks the Will for them.
Client `C:\Infinite Crisis Steam\InfiniteCrisis.exe` (unpatched copy), VAs (image base 0x400000), `.text` file
offset = VA - 0x400C00. C = confirmed from code, P = probable.

## 1. Who draws the "not enough Will" look (C)

Not the disable conditions. The Flash `gameplay.skills2.SkillControl.OnSecondaryVitalChange(v)` sets
`m_mcNotEnoughVitalOverlay._visible = (m_stdData.fCost > 0 && v < m_stdData.fCost)` (classes_all.txt ~466642).
It is called from `SkillsPanel.UpdateSkillControlsForSecondaryVital` with `m_fCurrentSecondaryVitalAmount`, which is
set (a) once in `SkillsPanel.SetupForAgent` from `GM_Vitals.InqVital(agent, InqSecondaryVitalType)` and (b) by
`SkillsPanel.RecvNotice_UI_NotifyVitalChange(eVitalType, fNewValue)` for every `eVitalType != Health`.

- `fCost` comes from `RecvNotice_UI_SkillUpdate` (notice `0x10000275`), raised by the HUD loop `0xa7c640` at
  `0xa7c93f` (`0x8f7870`); the same loop caches it per slot at `0xa7c87d` (`[0x1b75968 + slot*4]`). It is the
  skill's stat 3 at the current rank, absolute value (hud_re.txt). The server sends nothing per slot for it.
- `UI_NotifyVitalChange` (notice `0x10000274`, wrapper `0x8a12c0`) has one C++ caller: the 0x42 handler
  `0xab1bd0` at `0xab2153`, per vital index, only if byte `[vitals+0x64] != 0` (`0xab213c`) and the type is not 3.

## 2. The two client states our champion lacks (C)

**a) Secondary vital type = property `0x1000000C` (enum, mapper `0x30000019`).** The vitals component's attach
(`0x972940`, called first by the client component's attach `0xaa6270`) reads it once from the owner
(`0x513a90(ent, 0x1000000C, &[vit+0x1C])` at `0x972950`) and sizes the vital list `[vit+0x18]` to
`1 + (type != 0)` (`0x9729b4`). Consequences when it is missing (ics never sends it):
- the 0x42 loop runs `min(n, list size)` = 1 entry (`0xab2005`), so the Will pair is dropped: no Will notice, and
  the component never stores Will;
- index -> type `0x96cb80` / type -> index `0x96cb50`, `0x96e620`: 2 = Health (index 0), `[vit+0x1C]` = index 1;
- CanActivate cost test (`0x870b05` -> `0xa0e5d0` cost cache, `0x85d320` resource type = `[vit+0x1C]` or 2 if 0,
  `0x9700c0`): with 0 it compares the cost with **Health**. Evidence in today's traffic.log: the client sent Q
  orders (`0x20EE` slot 1) with Will 1-3 (16:19:54, 16:22:20, 16:23:40); the server answered `0x20DC 0x10000055`.
- the attribute aliases (`0x96F4F0`: `0x10000486` etc. need resource type 5) also fail.
Will is vital type 5 (Mana_VitalType; items' `0x10000486`/`0x10000483` are "resource 5"; full-combat-skills B.1).

**b) "Controlled agent" flag `[vit+0x64]` = local bool property `0x100000CE`.** Set by the property listener
`0xaafcd0` (vtable `0x1609bf0` slot 3, `this` = component+0x40, `[esi+0x24]`), registered in `0xaa6270`
(`0xaa633b`). The client sets `0x100000CE` itself in the controlled-agent-changed handler `0xa16730` (vtable entry
`0x16041a4`): old agent false (`0xa1675a`), new agent true (`0xa16815`), but only if `0x4daf10(iid)` is false
(`0xa16807`/`0xa16809 jne 0xa168da`), and `0x4daf10` = "IID top byte == 2". Every ics object has top byte 2
(diag.log: `iid_hi=0x2000000`), so the flag stays 0 and the same jump also skips the listeners on `0x3CB`,
LifeState `0x100000FA`, `0x10000B2D` and `0x85d130` for the champion. With the flag 0 no `UI_NotifyVitalChange`
is ever raised (also the type-5 HUD path at `0xab21b4`).

## 3. The 'slot available' patch (rva 0x61d3e4) is unrelated (C)

`0xa230c0` enables a button iff every entry of `[0x1b75928 + slot*4]` passes `0xa1d380`. That list is filled only
by S->C `0x20A0` (`0x8bc4a0` -> `0xa6dd10`), which ics never sends, so the list is empty and the patch is a no-op;
`0xa1d380` knows only `0x1000003B`, `0x10000050`, `0x1000006B` (any other key always disables) and has no Will
check. `Skill_NoResources 0x10000055` is only a CanActivate result (`0x870b60`), not a button condition.

## 4. Fix options (ranked)

1. (high) Champion create properties: add `(0x1000000C, KIND_ENUM, 5)` so it is there when the vitals component
   attaches. Fixes the Will list, the client cost check (Skill_NoResources locally) and the Will notices' type.
2. (medium-high, needs 1) Make `[vit+0x64]` true: either send `0x100000CE` = true (bool) on the champion with the
   set-property event `0x6` after the create (the listener only fires on a change; network mode 0 but the reader
   accepts any id, P), or an exe patch at VA `0xa16809` (file `0x615C09`) `0f85cb000000` -> `909090909090`
   (treat top-byte-2 agents like the original's; also enables the skipped listeners - test for side effects).
3. (low) Changing the champion IID top byte: would touch creation pools (`0x54B940`) and many `0x4daf10` callers.

Without 2, after 1 the overlay is still evaluated only at SetupForAgent.
