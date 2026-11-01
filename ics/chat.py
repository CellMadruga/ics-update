"""Chat: channel joins, say and tell, echoed back to the one human player (full-account-social.md 8.4).

Client events: 0x20A6 channel list (u32 n x StringInfo: "Wrapper", "Team" ...), 0x20F6 say (StringInfo channel |
wstr text), 0x20CD tell (wstr target | wstr text). Which server event shows a line in the chat window is not known
yet (0x2183 or 0x20B0, [G]); [ics] chat_echo_event picks it (0 = no echo). 0x2135 lists a channel's members.
"""
import struct

from . import messages as M
from .wire import read_compact


def _wstr(body, pos):
    n, pos = read_compact(body, pos)
    return body[pos:pos + 2 * n].decode("utf-16-le", "replace"), pos + 2 * n


def _string_info(body, pos):
    """A StringInfo: literal (u8 1 | wstr | variables table) or token (u8 0 | u32 token | u32 table | table)."""
    mode = body[pos]
    pos += 1
    if mode == 1:
        text, pos = _wstr(body, pos)
    else:
        token, table = struct.unpack_from("<II", body, pos)
        text, pos = f"{token:#x}@{table:#x}", pos + 8
    pos += 1                                   # variables table: size class
    n, pos = read_compact(body, pos)
    if n:
        raise ValueError("StringInfo variables are not read")
    return text, pos


def parse_channels(body):
    """0x20A6 body -> channel names, or None when it is not a channel list."""
    try:
        if len(body) < 4:
            return None
        n = struct.unpack_from("<I", body, 0)[0]
        if not 0 < n < 16:
            return None
        pos, out = 4, []
        for _ in range(n):
            text, pos = _string_info(body, pos)
            out.append(text)
        return out if pos == len(body) else None
    except (IndexError, ValueError, struct.error):
        return None


def parse_say(body):
    try:
        channel, pos = _string_info(body, 0)
        text, pos = _wstr(body, pos)
        return channel, text
    except (IndexError, ValueError, struct.error):
        return None


def parse_tell(body):
    try:
        target, pos = _wstr(body, 0)
        text, pos = _wstr(body, pos)
        return target, text
    except (IndexError, ValueError, struct.error):
        return None


def echo(ic, sender, channel, text):
    """The line back to the player, as [ics] chat_echo_event says."""
    ev = int(ic.get("chat_echo_event", 0x2183) or 0)
    line = f"{sender}: {text}"
    if ev == 0x2183:
        return [(f"chat line [{channel}] {line!r} (0x2183)", M.chat_line(channel, line))]
    if ev == 0x20B0:
        return [(f"chat line [{channel}] {line!r} (0x20b0)", M.chat_toggle_unread(sender, channel, text))]
    return []
