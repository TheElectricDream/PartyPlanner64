"""The reference's C entries: the parts of C (as SmallerC compiles it) events use."""


def _c(title, code, check="c", **kw):
    return dict(title=title, lang="c", code=code.strip("\n"), check=check, **kw)


def _e(id_, name, summary, body="", kind="c-keyword", **kw):
    e = dict(id="c:" + id_, kind=kind, category="C", lang="c", name=name, summary=summary, body=body)
    e.update(kw)
    return e


_INT_TYPES = [
    ("s8", "signed char", "-128 to 127", "LB"),
    ("u8", "unsigned char", "0 to 255", "LBU"),
    ("s16", "signed short", "-32768 to 32767", "LH"),
    ("u16", "unsigned short", "0 to 65535", "LHU"),
    ("s32", "signed int", "-2147483648 to 2147483647", "LW"),
    ("u32", "unsigned int", "0 to 4294967295", "LW"),
]


def _int_type(name, c_name, values, load):
    size = {"8": 1, "16": 2, "32": 4}[name[1:]]
    return _e(name, name, "%d-byte %s integer, %s." % (
        size, "signed" if name[0] == "s" else "unsigned", values),
        "`%s`. From `ultra64.h`. MIPS load: `%s`." % (c_name, load),
        kind="c-type", syntax="%s name = value;" % name,
        examples=[_c("Declare", "%s value = 1;" % name)],
        see=["c:include", "c:int", "concept:player-struct"], tags=["type", "integer", c_name])


ENTRIES = [
    _e("main", "main", "Where a C event starts running.",
       "The game calls `main`; returning ends the event. Board code uses [[board:pickbackground|PickBackground]] or [[board:pickaudioindex|PickAudioIndex]] instead.",
       syntax="void main() { ... }",
       examples=[_c("Whole event: charge 10 coins", """
// NAME: Toll (C example)
// GAMES: MP3_USA
// EXECUTION: Direct

#include "ultra64.h"

extern s16 GetCurrentPlayerIndex();
extern void AdjustPlayerCoins(s32 player_index, s32 amount);

void main() {
    s32 player = GetCurrentPlayerIndex();
    AdjustPlayerCoins(player, -10);
}""", check="event")],
       see=["c:extern", "c:include", "concept:c-events"], tags=["entry point", "start"]),
    _e("include", "#include", 'Includes ultra64.h, the only header.',
       "Gives the sized types ([[c:s8|s8]]...[[c:f32|f32]]), `TRUE`, `FALSE`, `NULL`, button names. No `stdio.h`; call game functions like [[game:sprintf]].",
       syntax='#include "ultra64.h"', words=["include", "#include", "ultra64", "ultra64.h"],
       examples=[_c("Top of a C event", '#include "ultra64.h"', check="c-top")],
       see=["c:s32", "c:true"], tags=["header"]),
    _e("define", "#define", "Gives a value a name.",
       "Text replacement. [[concept:parameters|Parameters]] arrive as `#define`s.",
       syntax="#define NAME value", words=["define", "#define"],
       examples=[_c("Constant", """
#define TOLL 10
s32 cost = TOLL;""", check="c-top")],
       see=["concept:parameters"], tags=["constant", "macro"]),
    _e("extern", "extern", "Declares a game function or variable.",
       """- Function: `extern void AdjustPlayerCoins(s32 player_index, s32 amount);` checks arguments. Undeclared calls also work, unchecked.
- Variable: `extern u8 current_turn;` reads and writes the game's memory.

Match the symbol table's type.""",
       syntax="extern type name;",
       examples=[_c("Function and variable", """
extern void AdjustPlayerCoins(s32 player_index, s32 amount);
extern u8 current_turn;

void Bonus() {
    if (current_turn > 5) {
        AdjustPlayerCoins(0, 5);
    }
}""", check="c-top")],
       see=["concept:calling-functions", "game:current_turn"], tags=["declaration", "symbol"]),
    _e("void", "void", "Means no value, or no arguments.", "`void *`: pointer to anything.", kind="c-type", see=["c:main"]),
    _e("int", "int", "4-byte signed integer, same as s32.", "", kind="c-type",
       words=["int", "long", "short", "signed", "unsigned"],
       examples=[_c("Counting", """
int i;
int total = 0;
for (i = 0; i < 4; i++) {
    total = total + i;
}""")], see=["c:s32", "c:char"], tags=["type", "integer", "number"]),
    _e("char", "char", "1 byte; char * points at text.",
       "Game text uses `\\x` bytes: [[concept:message-text]].", kind="c-type",
       examples=[_c("Message", r'char *message = "Hello\xC2\xFF";', check="c-top")],
       see=["concept:message-text", "c:u8"], tags=["string", "text", "byte"]),
    *[_int_type(*t) for t in _INT_TYPES],
    _e("f32", "f32", "4-byte float.", "Same as `float`. Constants need `f`: `10.0f`.",
       kind="c-type", words=["f32", "float"],
       examples=[_c("Add", """
f32 height = 1.5f;
height = height + 10.0f;""")],
       see=["reg:f0"], tags=["float", "decimal"]),
    _e("true", "TRUE / FALSE", "1 and 0.",
       "0 is false, anything else true. `NULL`: no pointer. From `ultra64.h`.",
       kind="c-type", words=["true", "false", "null"],
       examples=[_c("Flag", """
s32 paid = FALSE;
if (paid == FALSE) {
    paid = TRUE;
}""")], see=["c:if"]),
    _e("if", "if / else", "Runs code when a condition isn't 0.",
       "Compare: `== != < <= > >=`. Combine: `&& || !`. `=` assigns, `==` compares.",
       syntax="if (condition) { ... } else { ... }", words=["if", "else"],
       examples=[_c("Pay if possible", """
s32 player = GetCurrentPlayerIndex();
if (PlayerHasCoins(player, 10)) {
    AdjustPlayerCoins(player, -10);
} else {
    PlaySound(0x106);
}""")],
       see=["concept:branches", "c:switch"], tags=["condition", "branch", "decision"]),
    _e("while", "while", "Repeats while a condition holds.",
       "Waiting loops must call [[game:SleepVProcess]].",
       syntax="while (condition) { ... }", words=["while", "do"],
       examples=[_c("Wait for a fade", """
InitFadeOut(1, 20);
while (GetFadeStatus() != 0) {
    SleepVProcess();
}""")],
       see=["c:for", "c:break", "game:SleepVProcess"], tags=["loop", "repeat"]),
    _e("for", "for", "Repeats code a counted number of times.", "Declare the counter first.",
       syntax="for (start; condition; step) { ... }",
       examples=[_c("Every player +5 coins", """
int i;
for (i = 0; i < 4; i++) {
    AdjustPlayerCoins(i, 5);
}""")],
       see=["c:while", "concept:players"], tags=["loop", "repeat", "counter"]),
    _e("switch", "switch / case", "Runs the code for whichever case matches a value.",
       "End each case with `break`.",
       syntax="switch (value) { case 0: ... break; default: ... }",
       words=["switch", "case", "default"],
       examples=[_c("Act on a choice", """
s32 choice = 1;
switch (choice) {
    case 0:
        AdjustPlayerCoins(0, 10);
        break;
    case 1:
        AdjustPlayerCoins(0, -10);
        break;
    default:
        break;
}""")],
       see=["c:if", "c:break", "concept:prompts"], tags=["choice", "branch"]),
    _e("break", "break / continue", "Leaves a loop or switch, or skips to the loop's next pass.",
       "", words=["break", "continue"], see=["c:while", "c:switch"]),
    _e("return", "return", "Ends the function, with a value if it has one.", "",
       syntax="return value;",
       examples=[_c("Leave early", """
if (PlayerIsCPU(-1)) {
    return;
}
PlaySound(0x106);""")], see=["c:main"], tags=["exit", "result"]),
    _e("struct", "struct", "Groups named fields at fixed offsets, like the game's player data.",
       "`p->field` reads through a pointer. Mirror game layouts: [[concept:player-struct]].",
       syntax="struct name { type field; ... };", words=["struct", "union", "typedef"],
       examples=[_c("Current player's stars", """
struct player {
    s8 unk0;
    s8 cpu_difficulty;
    s8 controller;
    u8 character;
    u8 flags;
    s8 pad0[5];
    s16 coins;
    s16 minigame_coins;
    s8 stars;
};
extern struct player *GetPlayerStruct(s32 player_index);

s32 CurrentStars() {
    struct player *p = GetPlayerStruct(-1);
    return p->stars;
}""", check="c-top")],
       see=["concept:player-struct", "game:GetPlayerStruct"], tags=["fields", "record", "->"]),
    _e("enum", "enum", "Gives names to a list of numbers.", "", syntax="enum name { A = 0, B = 1 };",
       examples=[_c("Items", """
enum item { ITEM_MUSHROOM = 0, ITEM_GOLDEN_MUSHROOM = 0x0A };
s32 wanted = ITEM_GOLDEN_MUSHROOM;""", check="c-top")],
       see=["game:PlayerHasItem"], tags=["constant", "names"]),
    _e("array", "Arrays", "Several values of one type, indexed from 0.",
       "Fill from a [[param:space-array|Space[] parameter]]: `s32 spaces[] = { targets };`.",
       kind="c-keyword", syntax="type name[count];", words=[],
       examples=[_c("One per player", """
s32 scores[4];
int i;
for (i = 0; i < 4; i++) {
    scores[i] = 0;
}""")], see=["c:for"], tags=["list", "[]"]),
    _e("pointer", "Pointers", "Addresses: * reads through one, & takes one.",
       "`p->field`: struct field through a pointer. [[game:GetPlayerStruct]] returns one.",
       kind="c-keyword", words=[], see=["c:struct"], tags=["address", "*", "&", "->"]),
    _e("static", "static", "Makes a variable keep its value between calls.", "", words=["static", "const", "volatile"]),
    _e("sizeof", "sizeof", "Gives the size of a type or value in bytes.", "", syntax="sizeof(type)"),
    _e("operators", "Operators", "Symbols that calculate and compare: + - * / % == != < > && || ! & | ^ << >>.",
       """- Math: `+ - * /`, `%` remainder
- Compare: `== != < <= > >=`
- Logic: `&& || !`
- Bits: `& | ^ ~ << >>`
- Update: `+= -= ++ --`""",
       kind="c-keyword", words=[], tags=["math", "arithmetic", "compare", "modulo"]),
    _e("strings", "Strings", 'Text in quotes; game bytes as \\x: "Hi\\xC2\\xFF".',
       "C adds a final 0. Adjacent strings join. Split after a `\\x` byte so letters aren't read as hex. Bytes: [[concept:message-text]].",
       kind="c-keyword", words=[],
       examples=[_c("Message in pieces", r'''
char *greeting =
    "\x0B"            // start
    "Welcome"
    "\xC2"            // !
    "\xFF";           // wait for A''', check="c-top")],
       see=["concept:message-text", "concept:messages"], tags=["text", "message", "escape"]),
]
