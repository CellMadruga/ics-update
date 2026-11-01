# Emotes (Joke / Taunt / Laugh / Dance / Oath): client path and what the server must answer

Static analysis, 2026-10-23. Exe `InfiniteCrisis.exe` (VA, base 0x400000), WLib record `0x39000001` (pack
`0xA0000038`), data pack `0xA00000B3`, the tester's keymap `Documents\InfiniteCrisis\infinitecrisis.keymap`.
Tags: [C] confirmed from code/data, [P] probable, [G] guess.

## 1. Why Ctrl+1..5 sent nothing [C]

The tester's keymap (the client reads `Documents\InfiniteCrisis\infinitecrisis.keymap`; meta bits from its `MetaKeys`
table: 1 = Shift, 2 = Ctrl, 4 = Alt) binds:

| Keys | Action |
|---|---|
| **Alt+Numpad1..5** (`0x00000004`) | **Dance, Joke, Laugh, Taunt, Oath** |
| Ctrl+1..4 (`0x00000002`) | `DoNothing` |
| Alt+1..6 | SmartSelfCastItem1..6 |
| Ctrl+Q/W/E/R/Tab | RankUpSkill / RankUpPassive |

So Ctrl+number never reaches the emote code. The packed default keymap (pack `0xA0000038` offset `0x12AF3C`,
16-byte rows `action | DIK << 16 | meta | 3`) also puts the emotes on numpad keys with a modifier (0x7D Numpad1,
Dance Numpad2, Joke Numpad3, Laugh Numpad4, Taunt Numpad5, Oath Shift+Tab-like `0x0F`/`0x40000000`). Typing a chat
emote command is a second path (`0xA314E2`, name -> code via `0xA30550`) [C for the call, command names not checked].

## 2. Client path once the right key is pressed

1. `0xA8A8E0` (input action handler): gates = not in text entry (`0xABEE50`), `[0x1B771F0]+0xB1 == 0`,
   `this+0x168 == 0`, controlled agent present (`0x85C150`: local player's property `0x100005E8` -> object); key
   down (`[esi+0x3C]`). Actions `0x100000CC..CF, 0xDB` -> `0xA0AB70` -> code Joke `0x16`, Taunt `0x15`, Laugh `0x17`,
   Dance `0x18`, Oath `0x1C` [C].
2. `0x964060(player, code)`: the object is the **local player** (`0x6351D0`, IID in `0x1B6A710`), not the agent
   (`a8af70`-`a8af8c`). Needs `player+0x30` (GameComponent, created for DB-type 0x40 classes: the player class
   `0x4000007C` qualifies) and its `+0x18` (script context). Pushes `int code`, `object player`, runs
   `0x4A5440(stack, 0x28F0001)` [C].
3. WLib `0x28F:1` (`CEmoteSystem::DoCmdPrefabEmote`, code `0xA60C`) [C]:
   - `0x172:8` (`0xA7EC`, `EmoteDirectory::GetEmoteFromCmd`): singleton = native `0x340001(0xB, 0x1000002D)` cast to
     WLib type `0x172` = class record **`0x40000012`** (pack `0xA00000B3`), list `0x1000002D` of 5 emote definitions
     (WLib type `0x171`); returns the one whose enum property **`0x10000A8F`** equals the code (`0xA700` ->
     native `0x970030`).
   - Emote definitions (property `0x10000A8F` = code, `0x10000AD3` = order): `0x40000241` Joke 0x16, `0x40000240`
     Taunt 0x15, `0x40000242` Laugh 0x17, `0x4000023F` Dance 0x18, `0x40000EE6` Oath 0x1C (property bags `0x49xxxxxx`
     of the same index). All data present locally.
   - Not found -> logs "Failed to locate Emote data..." on the player and returns 0.
   - Found -> `0x197` stub `0xBF5C`: new argument stream, `0x830004` writes **u32 = the emote definition entry**
     (DID, e.g. `0x40000241`) [P: which value is arg0], then `0xC2000C(target = player, 0x81970006, stream)`.
   - **Nothing is played locally**: no graph event, no scriptlet [C]; the client waits for the server.
4. `0x4A1C90` requires the target script object to be bound to a C++ object (flag `0x08000000`, owner at `[3]`),
   then `0x5624F0` builds event **`0x9F`** and sends it (`0x444A90`) [C].

**Wire (client -> server):** event `0x9F`, target `0x0200000000000001`, body `u8 0 | u32 0x81970006 | u32 n | blob`,
blob = one u32 from `0x830004` (emote definition DID) [P for the blob framing, same as rank-up `0x81910003`].
`0x197` method 6 (`0xBFA4`) is the server body (client copy returns 0); `0x197` has no server -> client handler, so
the answer is not a script RPC.

## 3. What the server should send back [P]

The champion graphs hold the emotes (Gaslight Batman `0x1A0002E7`: events `Emote_Joke 0x1000022E`, `Emote_Taunt
0x1000022C`, `Emote_Laugh 0x1000022D`, `Emote_Dance 0x100001F1`, `Emote_End 0x100001F0`, `Emote_Abort 0x100001F2`; the
graph itself raises `RunScript_Vfx_Chr_Emote_*` 0x10000231-0x10000234 for the effects and aborts when the champion
moves or turns). So on `0x9F 0x81970006` the server raises the graph event on the **agent**, to every client that
sees it: scriptlet `0x100001E3` + variable `0x780` = event (`ics/world.py` graph-event helper). Map:
`0x40000241`/0x16 -> `0x1000022E`, `0x40000240`/0x15 -> `0x1000022C`, `0x40000242`/0x17 -> `0x1000022D`,
`0x4000023F`/0x18 -> `0x100001F1`. Oath (0x1C) has no `Emote_Oath` graph event in the Batman list; the champion
scriptlet `Emote_Oath_Start 0x1000115E` (0x8D) is the candidate [G]. Fallback if a graph ignores the event: run the
champion's `Emote_*_Start` scriptlet through `0x8D` (some are in his table: `0x100001D3` Laugh_Start, `0x1000115E`).
Server-side rules (no movement while emoting, cooldown) are not in the client.
