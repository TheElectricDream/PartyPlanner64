"""The reference's entries for the games' functions and data most events use.

What a function takes and returns comes from the symbol tables' comments (the
`symbols` repository) and the PartyPlanner64 example events; every example here
is compiled by the tests against the named games' symbols. Functions without an
entry are still shown in the editor and the Reference, from the symbol tables.
"""

ALL = ["MP1_USA", "MP2_USA", "MP3_USA"]
MP3 = ["MP3_USA"]


def _mips(title, code, check="mips", **kw):
    return dict(title=title, lang="mips", code=code.strip("\n"), check=check, **kw)


def _c(title, code, check="c", **kw):
    return dict(title=title, lang="c", code=code.strip("\n"), check=check, **kw)


def _fn(name, games, signature, summary, body="", examples=(), see=(), tags=(), kind="function"):
    return dict(id="game:" + name, kind=kind, category="Game", lang="any", name=name,
                words=[name.lower()], games=games, syntax=signature, summary=summary, body=body,
                examples=list(examples), see=list(see), tags=list(tags))


def _var(name, games, ctype, summary, body="", examples=(), see=(), tags=()):
    return _fn(name, games, "extern %s %s;" % (ctype, name), summary, body, examples, see, tags,
               kind="variable")


ENTRIES = [
    # Players
    _fn("GetCurrentPlayerIndex", ALL, "s16 GetCurrentPlayerIndex()",
        "Returns whose turn it is, 0-3.", "",
        examples=[_mips("Who landed here?", """
JAL GetCurrentPlayerIndex
NOP
MOVE A0 V0       ; player, for the next call"""),
                  _c("In C", "s32 player = GetCurrentPlayerIndex();")],
        see=["concept:players", "game:current_player_index"], tags=["turn", "who", "player"]),
    _fn("GetPlayerStruct", ALL, "struct player *GetPlayerStruct(s32 player_index)",
        "Returns the address of a player's data; -1 means the current player.", "Layout: [[concept:player-struct]].",
        examples=[_mips("Current character", """
JAL GetPlayerStruct
ADDIU A0 R0 -1
LBU T0 3(V0)     ; 4 Wario, 6 Waluigi""")],
        see=["concept:player-struct", "c:struct"], tags=["player", "character", "data"]),
    _fn("PlayerIsCPU", ALL, "s32 PlayerIsCPU(s32 player_index)",
        "Returns 1 if the computer controls the player; -1 means the current player.", "",
        examples=[_c("Humans only", """
if (!PlayerIsCPU(-1)) {
    PlaySound(0x106);
}""")], see=["concept:players"], tags=["computer", "ai", "human"]),
    # Coins
    _fn("AdjustPlayerCoins", ALL, "void AdjustPlayerCoins(s32 player_index, s32 amount)",
        "Gives a player coins, or takes them with a negative amount (kept within 0-999).",
        "Instant and silent. Animated: [[game:AdjustPlayerCoinsGradual]]. On-screen +/-: [[game:ShowPlayerCoinChange]].",
        examples=[_mips("Take 10", """
JAL GetCurrentPlayerIndex
NOP
MOVE A0 V0
JAL AdjustPlayerCoins
ADDIU A1 R0 -10"""),
                  _c("Everyone +5", """
int i;
for (i = 0; i < 4; i++) {
    AdjustPlayerCoins(i, 5);
}""")],
        see=["game:AdjustPlayerCoinsGradual", "game:ShowPlayerCoinChange", "game:PlayerHasCoins"],
        tags=["coins", "money", "give", "take", "pay", "toll"]),
    _fn("AdjustPlayerCoinsGradual", ALL, "void AdjustPlayerCoinsGradual(s32 player_index, s32 amount)",
        "Gives or takes coins one at a time, with a sound for each.",
        "Follow with [[game:ShowPlayerCoinChange]] and ~30 frames of [[game:SleepProcess]].",
        examples=[_c("Like a blue space", """
s32 player = GetCurrentPlayerIndex();
AdjustPlayerCoinsGradual(player, 3);
ShowPlayerCoinChange(player, 3);
SleepProcess(30);""")],
        see=["game:AdjustPlayerCoins", "game:ShowPlayerCoinChange", "concept:sleeping"], tags=["coins", "sound"]),
    _fn("ShowPlayerCoinChange", ALL, "void ShowPlayerCoinChange(s32 player_index, s32 amount)",
        "Shows a +/- coin number next to a player's coins without changing them.", "",
        see=["game:AdjustPlayerCoinsGradual"], tags=["coins", "display", "hud"]),
    _fn("PlayerHasCoins", ALL, "s32 PlayerHasCoins(s32 player_index, s32 min_coins)",
        "Returns 1 if a player has at least min_coins coins.", "",
        examples=[_mips("Can pay 20?", """
JAL GetCurrentPlayerIndex
NOP
MOVE A0 V0
JAL PlayerHasCoins
ADDIU A1 R0 20
BEQ V0 R0 too_poor    ; 0: no
NOP
too_poor:""")],
        see=["game:AdjustPlayerCoins", "concept:branches"], tags=["coins", "afford", "enough", "check"]),
    # Items
    _fn("PlayerHasItem", MP3, "s32 PlayerHasItem(s32 player_index, s32 item)",
        "Returns the slot (0-2) holding an item, or -1 if the player doesn't have it.",
        "Items: 0 Mushroom, 1 Skeleton Key, 2 Poison Mushroom, 3 Reverse Mushroom, 4 Cellular Shopper, 5 Warp Block, 6 Plunder Chest, 7 Bowser Phone, 8 Dueling Glove, 9 Lucky Lamp, 10 Golden Mushroom, 11 Boo Bell, 12 Boo Repellent, 13 Bowser Suit, 14 Magic Lamp, 15 Koopa Kard, 16 Barter Box, 17 Lucky Coin, 18 Wacky Watch.",
        examples=[_c("Has a Skeleton Key?", """
if (PlayerHasItem(GetCurrentPlayerIndex(), 1) != -1) {
    PlaySound(0x106);
}""")],
        see=["game:PlayerHasEmptyItemSlot"], tags=["items", "key", "mushroom"]),
    _fn("PlayerHasEmptyItemSlot", MP3, "s32 PlayerHasEmptyItemSlot(s32 player_index)",
        "Returns a player's first empty item slot (0-2), or -1 if full.",
        "To give an item, write its number to `items` (offset 24, [[concept:player-struct]]).",
        examples=[_c("Give a Golden Mushroom", """
s32 player = GetCurrentPlayerIndex();
s32 slot = PlayerHasEmptyItemSlot(player);
if (slot != -1) {
    u8 *items = (u8 *)GetPlayerStruct(player) + 24;
    items[slot] = 0x0A;
}""")],
        see=["game:PlayerHasItem", "concept:player-struct"], tags=["items", "give"]),
    # Waiting and sound
    _fn("SleepProcess", ALL, "void SleepProcess(s32 frames)", "Pauses the event for a number of frames (30 per second).", "",
        examples=[_mips("1 second", """
JAL SleepProcess
ADDIU A0 R0 30""")],
        see=["concept:sleeping", "game:SleepVProcess"], tags=["wait", "delay", "frames", "pause"]),
    _fn("SleepVProcess", ALL, "void SleepVProcess()", "Pauses the event for one frame.", "Use in waiting loops.",
        see=["concept:sleeping", "game:SleepProcess"], tags=["wait", "frame"]),
    _fn("PlaySound", ALL, "void PlaySound(s32 sound_index)", "Plays a sound effect.",
        "MP3 examples: `0x106`, `0x107` Warp Block, `0x1AE` Thwomp, `345` Millennium Star, `582` coin, `583` register. More on the Audio page.",
        examples=[_mips("Ka-ching", """
JAL PlaySound
ADDIU A0 R0 583""")],
        tags=["sound", "sfx", "audio", "noise"]),
    _fn("PlayMusic", MP3, "void PlayMusic(s32 song_index)", "Starts a song.",
        "Board music: [[board:pickaudioindex|PickAudioIndex]].",
        see=["board:pickaudioindex"], tags=["music", "song", "bgm"]),
    # Messages
    _fn("ShowMessage", MP3,
        "void ShowMessage(s32 character, char *text, s32 value1, s32 value2, s32 value3, s32 value4, s32 value5)",
        "Opens a message window, with a character's picture if given.",
        """- `A0` picture: -1 none, 8 Thwomp, 0x16 Millennium Star
- `A1` text address
- `A2`, `A3`, `16(SP)`, `20(SP)`, `24(SP)`: values for `0x11`-`0x15`; 0 if unused

Then `func_800EC9DC`, [[game:CloseMessage]], `func_800EC6EC`. See [[concept:messages]].""",
        examples=[_c("Show a number", r'''
char text[16];
sprintf(text, "%d", 25);
ShowMessage(-1, "It costs \x11 coins\xFF", text, 0, 0, 0, 0);
func_800EC9DC();
CloseMessage();
func_800EC6EC();''')],
        see=["concept:messages", "concept:message-text", "game:CloseMessage", "game:sprintf"],
        tags=["message", "text", "dialog", "talk"]),
    _fn("CloseMessage", MP3, "void CloseMessage()", "Closes the message window.",
        "Then `func_800EC6EC`.", see=["game:ShowMessage", "concept:messages"]),
    _fn("GetBasicPromptSelection", MP3, "s32 GetBasicPromptSelection(void *cpu_choice, s32 option)",
        "Waits for the player to pick an option and returns its number, from 0.",
        """CPU pick, by the first argument:
- 0 or 1: that option
- 2: the second argument
- AI data address: AI decides

From PartyPlanner, not the symbol tables. See [[concept:prompts]].""",
        see=["concept:prompts", "game:ShowMessage", "game:ViewBoardMap"], tags=["choice", "question", "menu"]),
    _fn("ViewBoardMap", MP3, "void ViewBoardMap()", "Lets the player view the map.",
        "From PartyPlanner. Show the prompt again after.",
        see=["concept:prompts"], tags=["map"]),
    _fn("sprintf", ALL, "s32 sprintf(char *out, char *format, ...)",
        "Writes formatted text into memory; %d writes a number.",
        "`A0` output buffer, `A1` format (`.asciiz`), `A2`+ values.",
        examples=[_mips("Number to text", """
LUI A0 hi(number_text)
ADDIU A0 A0 lo(number_text)
LUI A1 hi(format)
ADDIU A1 A1 lo(format)
JAL sprintf
ADDIU A2 R0 25
J after_data
NOP
format:
.asciiz "%d"
.align 4
number_text:
.fill 8
.align 4
after_data:""")],
        see=["game:ShowMessage", "dir:asciiz"], tags=["format", "number", "text", "printf"]),
    # Random
    _fn("guRandom", ALL, "u32 guRandom()", "Returns a random 32-bit number.", "Ranges: [[concept:random]].",
        examples=[_c("1-6", "s32 roll = (guRandom() % 6) + 1;")],
        see=["concept:random", "game:RNGPercentChance"], tags=["random", "dice", "rng"]),
    _fn("RNGPercentChance", ["MP1_USA", "MP3_USA"], "s32 RNGPercentChance(s32 percent)",
        "Returns 1 with the given percent chance, else 0.", "",
        examples=[_c("25%", """
if (RNGPercentChance(25)) {
    AdjustPlayerCoins(-1, 10);
}""")],
        see=["concept:random", "game:guRandom"], tags=["random", "chance", "odds"]),
    # Moving players
    _fn("SetPlayerOntoChain", ALL, "void SetPlayerOntoChain(s32 player_index, s32 chain, s32 space)",
        "Puts a player on a chain position; they continue to the space after it.",
        "Use a [[param:space|Space parameter]]. Fade out first ([[game:InitFadeOut]]). Last space of a chain: also [[game:SetNextChainAndSpace]].",
        see=["param:space", "concept:chains", "game:SetNextChainAndSpace", "game:InitFadeOut"],
        tags=["warp", "teleport", "move"]),
    _fn("SetNextChainAndSpace", ["MP1_USA", "MP3_USA"], "void SetNextChainAndSpace(s32 player_index, s32 chain, s32 space)",
        "Sets where a player goes next.", "-1: current player.",
        see=["concept:chains", "game:SetPrevChainAndSpace", "game:SetPlayerOntoChain"], tags=["path", "direction"]),
    _fn("SetPrevChainAndSpace", MP3, "void SetPrevChainAndSpace(s32 player_index, s32 chain, s32 space)",
        "Sets where a player goes in reverse.", see=["game:SetNextChainAndSpace"], tags=["reverse"]),
    _fn("GetSpaceData", ALL, "struct spacedata *GetSpaceData(s32 space_index)",
        "Returns the address of a space's data.", "Bytes 8-19: x, z, y floats.", see=["concept:chains"], tags=["space", "position"]),
    _fn("SetSpaceType", ["MP1_USA", "MP3_USA"], "void SetSpaceType(s32 space_index, s32 type)",
        "Changes a space's type for the rest of the game.", "",
        see=["param:space"], tags=["space", "color", "type"]),
    _fn("GetAbsSpaceIndexFromChainSpaceIndex", ALL,
        "s32 GetAbsSpaceIndexFromChainSpaceIndex(s32 chain, s32 space)",
        "Turns a chain and a position on it into a space index.", see=["concept:chains"]),
    # Fades
    _fn("InitFadeOut", ["MP2_USA", "MP3_USA"], "void InitFadeOut(s32 fade_type, s32 frames)",
        "Starts fading the screen out.",
        "Types: 0 bars, 1 circle. Wait with [[game:GetFadeStatus]]; undo with [[game:InitFadeIn]].",
        examples=[_c("Out, then in (MP3)", games=MP3, code="""
InitFadeOut(1, 20);
while (GetFadeStatus() != 0) {
    SleepVProcess();
}
InitFadeIn(1, 20);""")],
        see=["game:InitFadeIn", "game:GetFadeStatus"], tags=["fade", "screen", "transition"]),
    _fn("InitFadeIn", ["MP2_USA", "MP3_USA"], "void InitFadeIn(s32 fade_type, s32 frames)",
        "Starts fading the screen in.", see=["game:InitFadeOut"], tags=["fade"]),
    _fn("GetFadeStatus", MP3, "s32 GetFadeStatus()", "Returns 0 when the fade has finished, 1 while it runs.",
        see=["game:InitFadeOut"], tags=["fade"]),
    # Data
    _var("current_turn", MP3, "u8", "Holds the current turn number, counting from 1.",
         "Read with `LBU` ([[syntax:hi-lo]]) or `extern u8`. MP2: u16.",
         examples=[_c("Last turn?", """
extern u8 current_turn;
extern u8 total_turns;

s32 IsLastTurn() {
    return current_turn == total_turns;
}""", check="c-top")],
         see=["game:total_turns", "board:code"], tags=["turn", "round"]),
    _var("total_turns", MP3, "u8", "Holds how many turns the game lasts.", see=["game:current_turn"], tags=["turns", "length"]),
    _var("current_player_index", MP3, "u8", "Holds whose turn it is, 0-3.",
         see=["game:GetCurrentPlayerIndex"]),
    _var("current_space_index", MP3, "u8", "Holds the space the current player is on.", tags=["space"]),
]
