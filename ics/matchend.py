"""The end of a match as the client expects it (docs/re-notes/client-cinematics-matchend.md, full-protocol.md 4.5):
VICTORY / DEFEAT in the world first (0x2038 + the boxed billboard, notice 0x100002EB type 9 / 8), then the
match-ended notice 0x1000000E (the client leaves the world at once) with what the end page needs: completed
encounters 0x214B, the stats 0x2045, achievement progress 0x2120 and the scorecard's prerequisites (0x2190, 0x2081,
0x2080, 0x20B9, 0x2104, 0x2188, 0x2090, 0x219F, 0x219E). The rewards are pulled by the client: 0x212E -> 0x211F,
0x2124 -> 0x2125, claim 0x2128.

Two kinds of match end here:
  tutorial  the earlier server's fase3-ff sequence (icserver/scorecard.py, worked in game): trainee achievement and
            the Champion Unlocked reward set;
  PvP       account XP / champion XP / Merits from [ics] pvp_rewards (the amounts are not in the client data),
            achievements advanced from their records (ics/account.py), their reward sets pending.
Progress is kept in the account (ics/account.py); data/progress.json is only read once to seed a new account.
"""
import struct
import time

from icserver import scorecard

from . import messages as M
from .account import AccountData, SOURCE_ACHIEVEMENT

TRAINEE = set(scorecard.TRAINEE_LIST)


def champion_icon(ic, data, variant):
    """Tester report 2026-10-29 12:45 (the "Champion Level Up!" popup's portrait box was empty): the picture [ics]
    level_up_icon names (a data/champions.json field: tex384, grid_icon, tex799) of the variant (a costume's own one
    first), 0 when off or unknown. Tester report 2026-10-30 15:30: tex384 is only in the champion's light pack, not
    loaded in the menus where the popup shows, so the default is now grid_icon (UI pack 0xA00000D0)."""
    field = str(ic.get("level_up_icon", "grid_icon") or "")
    if not field or field == "0" or data is None:
        return 0
    for c in getattr(data, "roster", None) or ():
        for s in [c] + list(c.get("costume_info", []) or []):
            if s.get("variant") == variant:
                return int(s.get(field) or c.get(field) or 0)
    return 0


def tutorials_done(done):
    n = 0
    while n + 1 in scorecard.TUTORIALS and scorecard.TUTORIALS[n + 1][1] in done:
        n += 1
    return n


def trainee_entries(completed=0, just_completed=None, now=0):
    """The 5 trainee achievements' 0x2120 entries (as scorecard.trainee_progress)."""
    out = []
    for i, did in enumerate(scorecard.TRAINEE_LIST, 1):
        if i <= completed:
            cur, prev, times = 1, 1, 1
        elif just_completed == i:
            cur, prev, times = 1, 0, 1
        else:
            cur, prev, times = 0, 0, 0
        out.append(scorecard.progress_entry(did, times, 0, [
            scorecard.objective(scorecard.OBJECTIVE_ID, cur, prev, 0, now if cur != prev else 0, 1 if cur else 0)]))
    return out


def achievements_msg(account, data, just_completed=None, now=0):
    """One 0x2120 with the trainee progress (only once a tutorial is done, as before) and every other achievement
    with progress on the account."""
    done = account.completed if account else []
    n = tutorials_done(done)
    entries = trainee_entries(n, just_completed, now) if (n or just_completed) else []
    if account is not None and data is not None:
        entries += account.achievement_entries(AccountData.of(data), exclude=TRAINEE)
    return (f"achievements (0x2120): {n} tutorial(s) done, {len(entries)} entries", M.achievement_progress(entries))


def login_events(ic, account=None, data=None):
    """What the menu needs before 0x2080: completed encounters 0x214B and achievement progress 0x2120."""
    done = account.completed if account is not None else []
    out = []
    if done:
        out.append((f"completed encounters (0x214b): {', '.join(hex(d) for d in done)}",
                    M.completed_encounters(done, done[-1])))
    if done or (account is not None and account.d["achievements"]):
        out.append(achievements_msg(account, data))
    return out


# ---- the sequence --------------------------------------------------------------------------------------------------
def victory_banner(ic, team, won=True):
    """In the world: the client's MatchEnded UI event and the big boxed VICTORY (type 9) / DEFEAT (type 8)."""
    msgs = [(f"match ended (0x2038) room {ic['room_id']}", scorecard.match_ended(ic["room_id"])),
            (f"announcement {'VICTORY' if won else 'DEFEAT'} (notice 0x100002eb, type {9 if won else 8})",
             M.show_announcement("VICTORY" if won else "DEFEAT", 9 if won else 8, 0, 0, team, team, 0))]
    if won:
        for line in ic.get("victory_voice_lines", [0x250]) or []:
            msgs.append((f"victory voice: announcer line {int(line):#x} (0x2001)", M.start_conversation(int(line))))
    return msgs


def match_end(ic, encounter, team, seconds, level=7, account=None, data=None):
    """The tutorial's match-ended notice and end page. Returns (messages, pending reward or None)."""
    msgs = [("objective cleared (0x2009)", M.objective_update(M.objective(1, text="", active=False, banner=""))),
            ("objective tracker off (0x2075)", M.objective_tracker_enabled(False))]
    pref = f"User.HasSeenPostEncounterVideo@{encounter:#010x}"
    msgs.append((f"preference {pref} = False (0x216a)", M.server_preferences([(pref, False)])))
    msgs.append((f"match ended: team {team} wins (notice 0x1000000e)", M.match_ended(team, seconds, b=team)))
    done = account.complete_encounter(encounter) if account is not None else [encounter]
    msgs.append((f"completed encounters (0x214b): {', '.join(hex(d) for d in done)}",
                 M.completed_encounters(done, encounter)))
    msgs.append(("end-of-match stats (0x2045)", M.end_of_match_stats(seconds)))
    pending = None
    tut = {d[1]: n for n, d in scorecard.TUTORIALS.items()}
    if encounter in tut:
        n = tut[encounter]
        msgs.append((f"achievement progress: Tutorial {n} newly complete (0x2120)",
                     scorecard.tutorial_completed(n, int(time.time()))))
        reward = int(ic.get("reward_champion", 0x40000086) or 0)
        if reward:
            pending = (f"pending reward: {reward:#x} for Tutorial {n} (0x2125)",
                       scorecard.tutorial_reward(n, int(time.time()) & 0x7FFFFFFF, reward))
            if account is not None:
                account.own(reward, 1)
    if account is not None:
        account.record_match(encounter, True)
        account.save()
    msgs += scorecard_bundle(ic, encounter, level, account)
    return msgs, pending


def scorecard_bundle(ic, encounter, level=7, account=None):
    name = str(ic.get("player_name", "Player"))
    if account is None:
        return scorecard.scorecard_bundle(name, account_level=int(ic.get("account_level", 30)), encounter=encounter,
                                          level=int(level))
    w, lvl = account.wallet, int(account.d["level"])
    return scorecard.scorecard_bundle(name, hard=w["hard"], soft=w["soft"], account_level=lvl, encounter=encounter,
                                      level=int(level))


def pvp_match_end(session, encounter, my_team, winning_team, seconds, champion, players, stats=None, notice=True):
    """Rewards and the end page of a lobby match. Returns (banner messages, end messages, pending reward message or
    None). stats: {"kills": n, "players": [(player iid, champion iid)]} from the mode layer (optional). notice =
    the end messages start with the match-ended notice 0x1000000E (not when the mode layer sent it)."""
    ic, data, account = session.ic, session.data, session.account
    adata = AccountData.of(data)
    stats = stats or {}
    won = winning_team == my_team
    rw = dict(ic.get("pvp_rewards") or {})
    pick = (lambda k, d=0: int(rw.get(f"{k}_{'win' if won else 'loss'}", d) or 0))
    axp, cxp, merits = pick("account_xp"), pick("champion_xp"), pick("merits")
    now = int(time.time())
    daily = 0
    if won and now - int(account.wallet.get("last_daily", 0)) >= 86400:
        daily = int(rw.get("first_win_merits", 0) or 0)
        account.wallet["last_daily"] = now
    prev_level, prev_xp = account.add_account_xp(axp)
    base = data.base_variant(champion) or champion      # a costume's XP and level are its champion's
    c = account.champion(base)
    cprev = account.add_champion_xp(base, cxp)
    account.wallet["soft"] += merits + daily
    account.record_match(encounter, won)
    account.complete_encounter(encounter)
    owned = sum(1 for c2 in data.roster if account.champion_owned(c2["variant"]))
    ctx = {"encounter": encounter, "won": won, "matchmade": not stats.get("custom"), "kills": int(stats.get("kills", 0)),
           "champion": champion, "protector_level": account.d["level"], "owned_champions": owned,
           "champions_played": len(account.d["champions"]),
           "champions_level5": sum(1 for v in account.d["champions"].values() if v["level"] >= 5)}
    newly = account.evaluate(adata, ctx)
    for a in newly:
        if a["reward_set"]:
            account.add_pending_reward(adata, a["reward_set"], a["did"], SOURCE_ACHIEVEMENT)
    account.save()
    session.log(f"match result: {'won' if won else 'lost'}; +{axp} account XP (level {prev_level} -> "
                f"{account.d['level']}), +{cxp} champion XP ({cprev[0]} -> {c['level']}), +{merits + daily} Merits; "
                f"{len(newly)} achievement(s) completed")

    banner = victory_banner(ic, my_team, won)
    lvl, need = account.d["level"], account.xp_to_next(account.d["level"])
    cneed = account.xp_to_next(c["level"], True)
    name = data.champion_name(champion)[0]
    plist = stats.get("players") or [(p["iid"], M.CHAMPION_AGENT_ID if p["iid"] == M.LOCAL_PLAYER_ID else 0)
                                     for p in players]
    end = [("objective tracker off (0x2075)", M.objective_tracker_enabled(False))]
    if notice:
        end.append((f"match ended: team {winning_team} wins (notice 0x1000000e)",
                    M.match_ended(winning_team, seconds, b=winning_team)))
    end += [(f"completed encounters (0x214b)", M.completed_encounters(account.completed, encounter)),
           (f"end-of-match stats (0x2045): {len(plist)} players", M.end_of_match_stats_all(seconds, plist)),
           achievements_msg(account, data),
           ("header + icons (0x2190)", scorecard.header_and_protector_icons(
               account.d["profile"]["icons"], header_name=str(ic.get("player_name", "Player")))),
           (f"currency balance (0x2081): {account.wallet['hard']} / {account.wallet['soft']}",
            M.currency_balance(account.wallet["hard"], account.wallet["soft"])),
           (f"account level/XP (0x2080): {prev_level} -> {lvl}",
            M.account_level(lvl, prev_level, *xp_numbers(ic, account, lvl, account.d["xp"]), axp, 0,
                            account.d["xp"] / max(1, need), prev_xp / max(1, account.xp_to_next(prev_level)),
                            layout=str(ic.get("account_level_layout", "client")))),
           (f"Merits earned (0x20b9): {merits} + daily {daily}",
            M.soft_currency_reward(merits, daily, 86400.0 - (now - account.wallet["last_daily"]) if daily else 0.0,
                                   account.wallet["streak"])),
           (f"champion level/XP (0x2104): {cprev[0]} -> {c['level']}",
            M.character_level(champion, name, c["level"], cprev[0], *xp_numbers(ic, account, c["level"], c["xp"], True),
                              cxp, 0,
                              c["xp"] / max(1, cneed), cprev[1] / max(1, account.xp_to_next(cprev[0], True)),
                              icon=champion_icon(ic, data, champion),
                              layout=str(ic.get("character_level_layout", "client")),
                              encounter=encounter if ic.get("scorecard_level_encounter", True) else 0)),
           ("accolades (0x2188)", M.accolades_earned(encounter, champion)),
           ("amplifier sets (0x2090)", amplifier_sets_msg(account)),
           ("standings (0x219f)", M.static_standings()),
           ("account standings (0x219e)", M.account_standings(ranked_values(account, encounter, ic.get("standings_layout", "reader"))))]
    session.scorecard_chat = scorecard_chat_summary(
        ic, won, seconds, (lvl, *xp_numbers(ic, account, lvl, account.d["xp"]), axp), merits + daily,
        account.wallet["soft"], (c["level"], *xp_numbers(ic, account, c["level"], c["xp"], True), cxp))
    pending = None
    if account.d["rewards"]["pending"]:
        pending = (f"pending reward sets (0x2125): {len(account.d['rewards']['pending'])}",
                   M.reward_sets(account.reward_elements()))
    return banner, end, pending


def scorecard_chat_summary(ic, won, seconds, protector, merits_earned, merits_total, champion):
    """2026-10-30 tester report 14:51 (scorecard-rewards-side-panel.md): the original's end screen (screenshot 79,
    another client build) has a "Victory / Match Duration / Rewards" panel to the right of the team tables. This
    client has no such panel on its Scorecard view (movie 0x2000008C: SummaryTab = the two TeamContainers only; the
    same parts live in the first tab, "Summary" = ScorecardAccolades of 0x200000AD). The Scorecard view's right side
    holds the chat window (SummaryTab.show -> ChatManager.ShowChat(All)), so the panel's lines go there as chat lines
    (0x2183, the form [ics] chat_echo_event already shows in game). protector / champion = (level, to next, total,
    earned) as xp_numbers gives them. [] when [ics] scorecard_chat_summary is false."""
    if not ic.get("scorecard_chat_summary", True):
        return []
    channel = str(ic.get("scorecard_chat_summary_channel", "All") or "All")
    s = max(0, int(round(float(seconds or 0))))
    plvl, pnext, ptotal, pgain = protector
    clvl, cnext, ctotal, cgain = champion
    lines = [f"{'Victory' if won else 'Defeat'} - Match Duration: {s // 60}:{s % 60:02d}",
             f"Rewards - Protector XP: Lvl {plvl}  {ptotal} / {pnext}  (+{pgain})",
             f"Rewards - Merit: Earned {merits_earned}  Total {merits_total}",
             f"Rewards - Champion XP: Lvl {clvl}  {ctotal} / {cnext}  (+{cgain})"]
    return [(f"scorecard summary in the chat (0x2183): {t!r}", M.chat_line(channel, t)) for t in lines]


def xp_numbers(ic, account, level, xp, champion=False):
    """(to next, total) for 0x2080 / 0x2104. Tester report 2026-10-29 21:10 (the original's reward panel, screenshot
    79: "247793 / 273500" at Protector level 54 with the bar ~10 % full, "6625 / 7200" at champion level 12 with the bar
    ~33 % full; aggro-recall-scorepanel.md 3): the text is the cumulative XP / the cumulative XP of the next level,
    the bar is the share inside the level. [ics] xp_numbers "cumulative"; "remainder" = XP inside the level / XP still
    missing (to fase3-in)."""
    if str(ic.get("xp_numbers", "cumulative")) != "cumulative":
        return max(0, account.xp_to_next(level, champion) - xp), xp
    below = sum(account.xp_to_next(lv, champion) for lv in range(1, max(1, int(level))))
    return below + account.xp_to_next(level, champion), below + xp


def amplifier_sets_msg(account):
    # 2026-10-28 (store-amplifiers.md): built by the account (total = set slots, [ics] amplifier_sets_total_slots)
    return account.amplifier_sets_msg()


def ranked_values(account, encounter=0, layout="reader"):
    """0x219E's 10 u32 in wire order (C, end-screen-crash.md: serializer 0x83FEB0 -> event +0x20..+0x44, handler
    0xA37DC0 -> UI_DeliverAccountStandingsData): last played encounter, rank, previous rank, sub-rank, previous
    sub-rank, rank position, streak, previous streak, matches played, matches won. The client indexes a byte table by
    rank (and previous rank) with NO bounds check whenever streak >= the 0x219F minimum streak, so a DID in a rank
    slot crashes it ([ics] standings_layout; "old" = the fase3-ic order that put the encounter in the rank slot)."""
    r = account.d["ranked"].get(f"0x{encounter:08X}", {}) if (account is not None and encounter) else {}
    s = account.d["stats"].get(f"0x{encounter:08X}", {}) if (account is not None and encounter) else {}
    if layout == "old":
        return [0, encounter, r.get("rank", 0), r.get("sub", 0), r.get("position", 0), r.get("streak", 0),
                r.get("previous", 0), s.get("ranked_played", 0), s.get("ranked_won", 0), 0]
    return [encounter, r.get("rank", 0), r.get("previous", 0), r.get("sub", 0), r.get("previous_sub", 0),
            r.get("position", 0), r.get("streak", 0), r.get("previous_streak", 0), s.get("ranked_played", 0),
            s.get("ranked_won", 0)]


def achievement_banners(account=None, data=None):
    """0x211F: the account's completed achievements not yet acknowledged (0x211E) [P: same entries as 0x2120]."""
    if account is None or data is None:
        return ("achievement banners: none (0x211f)", M.achievement_banners())
    pending = {int(k, 16) for k, v in account.d["achievements"].items() if v.get("times") and not v.get("acknowledged")}
    entries = account.achievement_entries(AccountData.of(data), only=pending) if pending else []
    return (f"achievement banners: {len(entries)} (0x211f)", M.achievement_banners(entries))


def header_again(ic, account=None):
    icons = account.d["profile"]["icons"] if account is not None else (0, 0, 0, 0, 0)
    return ("header + icons again: pending rewards to the UI (0x2190)",
            scorecard.header_and_protector_icons(icons, header_name=str(ic.get("player_name", "Player"))))


def claimed_set(body):
    return struct.unpack_from("<I", body, 0)[0] if len(body) >= 4 else 0
