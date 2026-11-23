"""The reference's entries about events: the header, parameters, the ideas events are
built from (concepts), and the background and music code of the Details page."""


def _mips(title, code, check="mips", **kw):
    return dict(title=title, lang="mips", code=code.strip("\n"), check=check, **kw)


def _c(title, code, check="c", **kw):
    return dict(title=title, lang="c", code=code.strip("\n"), check=check, **kw)


def _hdr(name, summary, body, syntax, examples=(), see=(), tags=()):
    return dict(id="hdr:" + name.lower(), kind="header", category="Events", lang="any", name=name,
                words=[name.lower()], syntax=syntax, summary=summary, body=body,
                examples=list(examples), see=list(see), tags=list(tags))


def _param(id_, name, summary, body, examples=(), see=()):
    return dict(id="param:" + id_, kind="parameter", category="Events", lang="any", name=name,
                words=[name.lower()], syntax="; PARAM: %s|name" % name, summary=summary, body=body,
                examples=list(examples), see=["concept:parameters"] + list(see), tags=["parameter", "PARAM"])


def _concept(id_, name, summary, body, examples=(), see=(), tags=(), words=(), lang="any"):
    return dict(id="concept:" + id_, kind="concept", category="Events", lang=lang, name=name,
                words=list(words), summary=summary, body=body, examples=list(examples),
                see=list(see), tags=list(tags))


_EVENT_SKELETON = """
; NAME: Skeleton
; GAMES: MP3_USA
; EXECUTION: Direct

ADDIU SP SP -24  ; reserve stack
SW RA 20(SP)     ; save RA

; your code

LW RA 20(SP)     ; restore RA
JR RA            ; return
ADDIU SP SP 24   ; (delay slot) free stack"""


ENTRIES = [
    # The header
    _hdr("NAME", "Event name.",
         "First of the header comments PartyPlanner reads: `NAME`, [[hdr:games|GAMES]], [[hdr:execution|EXECUTION]], [[hdr:param|PARAM]]. `;` in MIPS, `//` in C.",
         "; NAME: Toll Booth",
         examples=[_mips("Empty event", _EVENT_SKELETON, check="event")],
         see=["hdr:games", "hdr:execution", "hdr:param"], tags=["header", "title"]),
    _hdr("GAMES", "Games the event supports, comma separated.",
         "Function addresses differ per game; this picks the symbols. MP3 boards: `MP3_USA`.",
         "; GAMES: MP3_USA", see=["hdr:name"], tags=["header", "version"]),
    _hdr("EXECUTION", "How the game runs the event: Direct or Process.",
         """- `Direct`: called as a function. Use this.
- `Process`: run by the game's process system. Advanced.""",
         "; EXECUTION: Direct", see=["hdr:name"], tags=["header", "direct", "process"]),
    _hdr("PARAM", "Declares a per-space value.",
         "`; PARAM: type|name`. The name becomes a symbol. See [[concept:parameters]].",
         "; PARAM: +Number|toll",
         examples=[_mips("Toll set per space", """
; NAME: Toll Booth
; GAMES: MP3_USA
; EXECUTION: Direct
; PARAM: +Number|toll

ADDIU SP SP -24
SW RA 20(SP)
JAL GetCurrentPlayerIndex
NOP
MOVE A0 V0
ADDIU A1 R0 toll
JAL AdjustPlayerCoins
SUBU A1 R0 A1    ; A1 = -toll
LW RA 20(SP)
JR RA
ADDIU SP SP 24""", check="event")],
         see=["concept:parameters"], tags=["header", "parameter", "option"]),
    # Parameter types
    _param("boolean", "Boolean", "1 or 0.", "Pairs with [[dir:if|.if]].",
           examples=[_c("Boolean in C", """
if (double_toll) {
    AdjustPlayerCoins(-1, -20);
}""", params=[["Boolean", "double_toll"]])], see=["dir:if"]),
    _param("number", "Number", "Whole number, any sign.", "",
           examples=[_mips("Give coins", """
JAL GetCurrentPlayerIndex
NOP
MOVE A0 V0
JAL AdjustPlayerCoins
ADDIU A1 R0 coins""", params=[["Number", "coins"]])]),
    _param("positive-number", "+Number", "Whole number, 1 or more.", "", see=["param:number"]),
    _param("space", "Space", "One board space.",
           """Parameter `target` gives:
- `target`: space index
- `target_chain_index`: its chain
- `target_chain_space_index`: position on the chain""",
           examples=[_mips("Warp to the space", """
JAL GetCurrentPlayerIndex
NOP
MOVE A0 V0
ADDIU A1 R0 target_chain_index
JAL SetPlayerOntoChain
ADDIU A2 R0 target_chain_space_index""", params=[["Space", "target"]])],
           see=["concept:chains", "game:SetPlayerOntoChain"]),
    _param("space-array", "Space[]", "Several board spaces.",
           """Parameter `targets` gives:
- `targets`: indices, comma separated
- `targets_length`: count
- `targets_chain_indices`, `targets_chain_space_indices`""",
           examples=[_c("As a C array", """
s32 spaces[] = { targets };
s32 count = targets_length;""", params=[["Space[]", "targets"]])],
           see=["param:space", "c:array"]),
    # Concepts
    _concept("events", "Events",
             "Code run when a player lands on or passes a space.",
             """Shape of a MIPS event:
- [[hdr:name|Header]]
- Save `RA` on the [[concept:stack|stack]]
- [[concept:calling-functions|Calls]] and [[concept:branches|branches]]
- Restore `RA`, `JR RA`

Check with **Test Compile**; run with **Test Play**.""",
             examples=[_mips("Skeleton", _EVENT_SKELETON, check="event")],
             see=["concept:stack", "concept:calling-functions", "hdr:name"], tags=["start", "beginner", "basics"]),
    _concept("delay-slot", "Delay Slot",
             "The instruction after a jump or branch runs first.",
             """Applies to `JAL`, `JR`, `J`, `BEQ`, `BNE`, etc.
- Default: [[mips:nop|NOP]].
- Or set the call's last argument there.
- Never another jump or an [[mips:li|LI]].""",
             examples=[_mips("Both uses", """
JAL GetCurrentPlayerIndex
NOP              ; nothing to do
MOVE A0 V0
JAL AdjustPlayerCoins
ADDIU A1 R0 10   ; runs before the call""")],
             see=["mips:nop", "mips:jal", "concept:branches"], tags=["branch delay", "nop", "pipeline"],
             words=["delay", "slot"], lang="mips"),
    _concept("stack", "Stack",
             "Memory a function borrows to save registers.",
             """- Subtract from `SP` (multiple of 8, at least 24).
- Save `RA` and any [[reg:s0|S registers]] used.
- Restore them; add the same amount back.

`0(SP)`-`15(SP)` belong to called functions; `16(SP)` up holds their 5th+ arguments. Keep yours above: `RA` at `20(SP)` with 24 bytes.""",
             examples=[_mips("Save RA and S0", """
ADDIU SP SP -32
SW RA 28(SP)
SW S0 24(SP)
; code using S0
LW S0 24(SP)
LW RA 28(SP)
ADDIU SP SP 32""")],
             see=["reg:sp", "reg:ra", "reg:s0", "concept:calling-functions"],
             tags=["sp", "frame", "save", "restore", "crash"], words=["stack"], lang="mips"),
    _concept("calling-functions", "Calling Functions",
             "Arguments in A0-A3, JAL the name, result in V0.",
             """Names come from the symbols of the event's [[hdr:games|GAMES]].
- Arguments 1-4: `A0`-`A3`; 5+: `16(SP)`, `20(SP)`, ...
- Result: `V0`
- Changed by the call: `V0`, `V1`, `A0`-`A3`, `T0`-`T9`, `RA`
- Kept: `S0`-`S7`, `SP`""",
             examples=[
                 _mips("Call, use the result", """
JAL GetCurrentPlayerIndex
NOP
MOVE A0 V0       ; result as argument 1
JAL PlayerHasCoins
ADDIU A1 R0 10   ; argument 2
; V0: 1 if 10+ coins"""),
                 _c("In C", """
s32 player = GetCurrentPlayerIndex();
s32 can_pay = PlayerHasCoins(player, 10);"""),
             ],
             see=["mips:jal", "reg:a0", "reg:v0", "reg:s0", "concept:stack"],
             tags=["call", "arguments", "return value", "abi", "convention"]),
    _concept("branches", "Branches and Loops",
             "Compare registers, jump to a label.",
             """- `BEQ a b label`: if equal
- `BNE a b label`: if not equal
- With `R0`: test for zero
- `SLT t a b`: t = 1 if a < b
- `BLTZ`, `BGEZ`, `BLEZ`, `BGTZ`: compare with zero

Loop: branch back. Else: `J` past it. Mind the [[concept:delay-slot|delay slot]].""",
             examples=[_mips("If / else", """
JAL GetCurrentPlayerIndex
NOP
MOVE A0 V0
JAL PlayerHasCoins
ADDIU A1 R0 10
BEQ V0 R0 else_part   ; can't pay
NOP
; can pay
J end_if
NOP
else_part:
; can't pay
end_if:""")],
             see=["mips:beq", "mips:bne", "mips:slt", "c:if"],
             tags=["if", "else", "loop", "compare", "condition"], lang="mips"),
    _concept("players", "Player Indices",
             "Players are 0-3; -1 often means the current player.",
             "Turn order, not character. [[game:GetCurrentPlayerIndex]] gives the current one.",
             examples=[_c("Everyone else", """
s32 me = GetCurrentPlayerIndex();
int i;
for (i = 0; i < 4; i++) {
    if (i != me) {
        AdjustPlayerCoins(i, -5);
    }
}""")],
             see=["game:GetCurrentPlayerIndex", "concept:player-struct"], tags=["player index", "who"]),
    _concept("player-struct", "MP3 Player Structure",
             "56 bytes per player: character, coins, stars, position, items.",
             """[[game:GetPlayerStruct]] returns it. Player 1 at `0x800D1108`; each next +56. Offsets:
- 2 controller (s8)
- 3 character (u8): 0 Mario, 1 Luigi, 2 Peach, 3 Yoshi, 4 Wario, 5 DK, 6 Waluigi, 7 Daisy
- 4 flags (u8): 1 = CPU
- 10 coins (s16), 12 mini-game coins (s16), 14 stars (s8)
- 15/16 chain/space, 17/18 next chain/space
- 23 status (0x80 = reversing)
- 24 items, 3 bytes (0xFF empty)

Change coins with [[game:AdjustPlayerCoins]], not directly.""",
             examples=[_mips("Is it Wario?", """
JAL GetPlayerStruct
ADDIU A0 R0 -1        ; current player
LBU T0 3(V0)          ; character
ADDIU T1 R0 4         ; Wario
BEQ T0 T1 is_wario
NOP
is_wario:""")],
             see=["game:GetPlayerStruct", "c:struct", "concept:players"],
             tags=["character", "coins", "stars", "items", "wario", "waluigi", "struct"]),
    _concept("chains", "Chains and Spaces",
             "Spaces are grouped in chains; players are tracked by chain and position.",
             "Moving players takes both: [[game:SetPlayerOntoChain]], [[game:SetNextChainAndSpace]]. A [[param:space|Space parameter]] gives both.",
             see=["param:space", "game:SetPlayerOntoChain"], tags=["path", "warp", "move"]),
    _concept("messages", "MP3 Messages",
             "ShowMessage, wait, close.",
             """1. [[game:ShowMessage]]: `A0` picture (-1 none), `A1` text address, `A2`, `A3`, `16(SP)`-`24(SP)`: up to 5 inserted values (0 if unused).
2. `func_800EC9DC`: wait for A.
3. [[game:CloseMessage]].
4. `func_800EC6EC`: clean up.

Text format: [[concept:message-text]].""",
             examples=[
                 _mips("Hello!", """
SW R0 16(SP)          ; values 3-5: none
SW R0 20(SP)
SW R0 24(SP)
ADDIU A0 R0 -1        ; no picture
LUI A1 hi(hello)
ADDIU A1 A1 lo(hello)
ADDU A2 R0 R0
JAL ShowMessage
ADDU A3 R0 R0
JAL func_800EC9DC     ; wait for A
NOP
JAL CloseMessage
NOP
JAL func_800EC6EC
NOP
J after_text
NOP
.align 4
hello:
.ascii "Hello",0xC2,0xFF,0
.align 4
after_text:"""),
                 _c("In C", r'''
ShowMessage(-1, "Hello\xC2\xFF", 0, 0, 0, 0, 0);
func_800EC9DC();
CloseMessage();
func_800EC6EC();'''),
             ],
             see=["game:ShowMessage", "concept:message-text", "concept:prompts"],
             tags=["text", "dialog", "message box", "talk"]),
    _concept("message-text", "Message Text",
             "Letters, digits and space are ASCII; the rest are game bytes (MP3).",
             """- `0xFF` wait for A; end with `0xFF,0`
- `0x0A` new line, `0x0B` message start
- `0x1A` gap (4 make room for the picture)
- `0x0C`/`0x0D` choice start/end ([[concept:prompts]])
- `0x11`-`0x15` inserted values 1-5
- Colors: `0x03` red, `0x05` green, `0x06` blue, `0x07` yellow, `0x08` white, `0x19` end
- `0xC2` !, `0xC3` ?, `0x85` ., `0x82` ,, `0x5C` ', `0x3D` -
- Icons: `0x29` coin, `0x2A` star, `0x21` A, `0x22` B

MIPS: `.ascii "Pay",0xC2,0xFF,0`. C: `"Pay\\xC2\\xFF"`.""",
             examples=[_mips("Two lines, coin icon", """
.align 4
toll_text:
.byte 0x0B
.ascii "That",0x5C,"s 10 ",0x29,0x0A
.ascii "Pay up",0xC2,0xFF,0""")],
             see=["dir:ascii", "c:strings", "concept:messages"],
             tags=["string", "encoding", "punctuation", "exclamation", "question", "newline", "colour", "color"]),
    _concept("prompts", "MP3 Prompts",
             "Message with choices; GetBasicPromptSelection returns the pick.",
             "Wrap choices in `0x0C`/`0x0D`, call [[game:ShowMessage]], then [[game:GetBasicPromptSelection]] (option number from 0 in `V0`). Close as usual; no wait for A.",
             examples=[_c("Yes or no", r'''
char *question =
    "\x0B"
    "Pay 10 coins"
    "\xC3"                       // ?
    "\x0A"
    "\x1A\x1A\x0C" "Yes" "\x0D"  // option 0
    "\x0A"
    "\x1A\x1A\x0C" "No" "\x0D";  // option 1

void Ask() {
    ShowMessage(-1, question, 0, 0, 0, 0, 0);
    s32 choice = GetBasicPromptSelection(2, 0);  // CPUs pick 0
    CloseMessage();
    func_800EC6EC();
    if (choice == 0) {
        AdjustPlayerCoins(-1, -10);
    }
}''', check="c-top")],
             see=["game:GetBasicPromptSelection", "concept:messages", "c:switch"],
             tags=["choice", "question", "yes no", "menu", "option"]),
    _concept("sleeping", "Waiting",
             "SleepProcess(n) pauses n frames (30 per second).",
             "[[game:SleepProcess]] for n frames, [[game:SleepVProcess]] for one. The game keeps running. Waiting loops must sleep each pass.",
             examples=[_mips("Give coins, wait 1 second", """
JAL GetCurrentPlayerIndex
NOP
MOVE A0 V0
JAL AdjustPlayerCoinsGradual
ADDIU A1 R0 10
JAL SleepProcess
ADDIU A0 R0 30""")],
             see=["game:SleepProcess", "game:SleepVProcess"], tags=["wait", "delay", "pause", "frames", "time"]),
    _concept("random", "Random Numbers",
             "guRandom for a number; RNGPercentChance for odds.",
             "Range: remainder of [[game:guRandom]] (`DIVU`, `MFHI`; C: `%` on unsigned). Odds: [[game:RNGPercentChance]].",
             examples=[_c("Lose 1-10 coins", """
u32 r = guRandom();
s32 lost = (r % 10) + 1;
AdjustPlayerCoins(-1, -lost);""")],
             see=["game:guRandom", "game:RNGPercentChance", "mips:divu"], tags=["chance", "dice", "luck", "rng"]),
    _concept("parameters", "Parameters",
             "Per-space values that become symbols in the code.",
             """Declare with [[hdr:param|PARAM]]; set per space in the Editor. MIPS: a label. C: a `#define`.

Types: [[param:boolean|Boolean]], [[param:number|Number]], [[param:positive-number|+Number]], [[param:space|Space]], [[param:space-array|Space[]]].""",
             see=["hdr:param", "param:space"], tags=["PARAM", "options", "settings", "per space"]),
    _concept("c-events", "C Events",
             "Compiled to MIPS for you, stack and delay slots included.",
             """- Header with `//`
- `#include "ultra64.h"`
- `void main()`
- Call game functions by name; [[c:extern]] checks arguments
- Exact types (`u8`, `s16`) for game data
- Messages: strings with `\\x` bytes""",
             see=["c:main", "c:extern", "c:include", "concept:events"], tags=["c", "smallerc", "compile"]),
]


# --- Board code (Details page) ----------------------------------------------------

def _board(id_, name, summary, body, words, contexts, examples=(), see=(), lang="any", kind="board"):
    return dict(id="board:" + id_, kind=kind, category="Board code", lang=lang, name=name,
                words=words, contexts=contexts, summary=summary, body=body,
                examples=list(examples), see=list(see))


BOARD_ENTRIES = [
    _board("code", "Board Code", "Code that picks the background or music.",
           """Details page. [[board:pickbackground|PickBackground]] runs each turn; [[board:pickaudioindex|PickAudioIndex]] when the music starts. Return the choice (MIPS: `V0`). Game data like [[game:current_turn]] helps decide.""",
           [], ["background", "music"], kind="concept",
           see=["board:pickbackground", "board:pickaudioindex", "game:current_turn"]),
    _board("pickbackground", "PickBackground", "Returns this turn's background.",
           "Return [[board:default_bg|DEFAULT_BG]] or [[board:additional_bg|ADDITIONAL_BG_n]].",
           ["pickbackground"], ["background"],
           examples=[dict(title="Alternate each turn", lang="c", check="background", code="""
#include "ultra64.h"

extern u8 current_turn;

int PickBackground() {
    if ((current_turn & 1) == 0) {
        return ADDITIONAL_BG_1;
    }
    return DEFAULT_BG;
}"""), dict(title="In MIPS", lang="mips", check="background", code="""
LUI T0 hi(current_turn)
LBU T0 lo(current_turn)(T0)
ANDI T0 T0 1
BEQ T0 R0 even
NOP
JR RA
ADDIU V0 R0 DEFAULT_BG
even:
JR RA
ADDIU V0 R0 ADDITIONAL_BG_1""")],
           see=["board:default_bg", "board:additional_bg", "board:code"]),
    _board("default_bg", "DEFAULT_BG", "The main background.", "",
           ["default_bg"], ["background"], see=["board:pickbackground"]),
    _board("additional_bg", "ADDITIONAL_BG_n", "An added background, from ADDITIONAL_BG_1.", "",
           ["additional_bg_%d" % i for i in range(1, 21)], ["background"], see=["board:pickbackground"]),
    _board("pickaudioindex", "PickAudioIndex", "Returns the song to play.",
           "Return [[board:music_track_index|MUSIC_TRACK_INDEX_n]].",
           ["pickaudioindex"], ["music"],
           examples=[dict(title="New music for the last 5 turns", lang="c", check="music", code="""
#include "ultra64.h"

extern u8 current_turn;
extern u8 total_turns;

int PickAudioIndex() {
    if (current_turn + 5 > total_turns) {
        return MUSIC_TRACK_INDEX_2;
    }
    return MUSIC_TRACK_INDEX_1;
}""")],
           see=["board:music_track_index", "board:code", "game:total_turns"]),
    _board("music_track_index", "MUSIC_TRACK_INDEX_n", "A board song, from MUSIC_TRACK_INDEX_1.",
           "Without custom music, only `MUSIC_TRACK_INDEX_1`: the chosen in-game song.",
           ["music_track_index_%d" % i for i in range(1, 21)], ["music"], see=["board:pickaudioindex"]),
]
