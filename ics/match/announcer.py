"""The announcer: lines the server asks the client to play (the client never speaks by itself).

0x2039 (ics/messages.py announcer) names a match event; the client picks the line from the encounter's announcer sets,
which 0xa35dc0 puts on dialog channels: 1 = the shared set (template 0x10000803, 0x4000047A), 2 = the encounter's set
(0x10000802, Crime Alley 0x40000D4C). The dialog system must have been enabled by notice 0x10000205 first. The lines
are also conversation keys, so 0x2001 with a line id plays one directly (as 0x250 does): LINES lists each event's
own-team ("ally") and enemy-team line from the sets' 0x10000829 / 0x1000082A columns. Which event means what is not in
the client; [ics] announcer_events maps the match's events to these ids once known by ear.
"""

SHARED_EVENTS = (8, 18, 19, 20, 21, 22, 23, 24, 25, 26, 27, 28, 29, 30, 52)

# event -> (0x10000829 line: the other team, 0x1000082A line: the acting team); 0 = none. Sets 0x4900047A (shared) and 0x49000D4C (Crime Alley).
LINES = {
    8: (160, 201), 18: (169, 177), 19: (158, 192), 20: (164, 198), 21: (167, 200), 22: (171, 202), 23: (205, 181),
    24: (388, 389), 25: (175, 150), 26: (199, 196), 27: (195, 180), 28: (185, 154), 29: (392, 393), 30: (191, 186),
    52: (390, 387),
    10: (218, 228), 15: (220, 206), 17: (226, 213), 31: (303, 0), 32: (292, 0), 33: (307, 309), 34: (305, 0),
    35: (291, 0), 36: (315, 312), 37: (302, 304), 40: (384, 380), 41: (382, 0), 49: (436, 437), 50: (251, 275),
    55: (428, 431), 56: (433, 0), 58: (447, 448), 61: (0, 697), 63: (725, 718), 64: (721, 719),
}

EVENTS = sorted(LINES)


def channel(event):
    """The dialog channel holding the event's set."""
    return 1 if event in SHARED_EVENTS else 2


def line(event, own_team=True):
    """2026-10-25 (announcer-and-map-elements.md, C): the set's 0x1000082A line goes to the ACTING team (destroyer,
    winner, killer), 0x10000829 to the other; LINES holds (0x10000829, 0x1000082A). The old order played our own
    victory as "Defeat" in the 2001 / both modes. "Under attack" events have only 0x10000829: silent for the attacker."""
    other, acting = LINES.get(int(event), (0, 0))
    return acting if own_team else other
