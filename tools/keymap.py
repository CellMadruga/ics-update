"""Bind the emotes to Ctrl + the top-row number keys in the player's keymap.

2026-10-24 (tester: emotes work, but only on Alt + numpad; many laptops have no numpad): the client reads
Documents\\InfiniteCrisis\\infinitecrisis.keymap (MetaKeys: 1 = Shift, 2 = Ctrl, 4 = Alt). Its in-match section binds
Ctrl+1..4 to DoNothing; this replaces them with Dance / Joke / Laugh / Taunt and adds Ctrl+5 = Oath. 2026-10-24 23:55
(tester: only the top-row numbers, drop the numpad): the default Alt + numpad emote bindings are removed. A backup is
written next to the file first. Close the game before running it (the client
rewrites the file when it exits).

    python tools\\keymap.py            apply
    python tools\\keymap.py --check    only show what would change
"""
import os
import re
import shutil
import sys
import time

KEYMAP = os.path.join(os.path.expanduser("~"), "Documents", "InfiniteCrisis", "infinitecrisis.keymap")
CTRL = 0x00000002
EMOTES = [("Dance", "DIK_1"), ("Joke", "DIK_2"), ("Laugh", "DIK_3"), ("Taunt", "DIK_4"), ("Oath", "DIK_5")]


def binding(action, key, meta):
    return f"    {action} [ Old [ 0 {key} ] 0x{meta:08X} ]"


def main():
    check = "--check" in sys.argv
    path = next((a for a in sys.argv[1:] if not a.startswith("--")), KEYMAP)
    if not os.path.exists(path):
        sys.exit(f"keymap not found: {path} (start the game once so it writes it)")
    with open(path, encoding="latin-1", newline="") as f:
        text = f.read()
    nl = "\r\n" if "\r\n" in text else "\n"
    lines = text.split(nl)
    changed = []
    for action, key in EMOTES:
        want = binding(action, key, CTRL)
        if want in lines:
            continue
        # the same key + modifiers may be bound only once: drop whatever holds Ctrl+<key> now (DoNothing)
        pat = re.compile(rf"^\s*\w+ \[ Old \[ 0 {key} \] 0x0*{CTRL:X} \]\s*$", re.I)
        old = [i for i, l in enumerate(lines) if pat.match(l)]
        anchor = next((i for i, l in enumerate(lines) if re.match(rf"^\s*{action} \[", l)), None)
        for i in reversed(old):
            changed.append(f"- {lines[i].strip()}")
            del lines[i]
            if anchor is not None and i < anchor:
                anchor -= 1
        if anchor is None:
            sys.exit(f"no {action} binding found in {path}: not an Infinite Crisis keymap?")
        lines.insert(anchor + 1, want)
        changed.append(f"+ {want.strip()}")
    names = "|".join(a for a, _k in EMOTES)
    numpad = re.compile(rf"^\s*({names}) \[ Old \[ 0 DIK_NUMPAD\d \]", re.I)
    for i in reversed([i for i, l in enumerate(lines) if numpad.match(l)]):
        changed.append(f"- {lines[i].strip()}")
        del lines[i]
    if not changed:
        print("emotes already on Ctrl+1..5 only")
        return
    print("\n".join(changed))
    if check:
        return
    backup = f"{path}.{time.strftime('%Y%m%d-%H%M%S')}.bak"
    shutil.copy2(path, backup)
    with open(path, "w", encoding="latin-1", newline="") as f:
        f.write(nl.join(lines))
    print(f"written {path} (backup {backup})")


if __name__ == "__main__":
    main()
