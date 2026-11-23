"""The reference's MIPS entries: instructions, registers, directives, assembler syntax.

Every opcode the assembler knows (lib/mips/inst/opcodes.py) gets an entry: the
ones events use are explained here (_INSTRUCTIONS); the rest get a sentence from
sentences.OPCODES and a syntax line made from the opcode table.
"""

from ..mips.inst.opcodes import opcode_details
from .sentences import OPCODES


def _mips(title, code, check="mips", **kw):
    return dict(title=title, lang="mips", code=code.strip("\n"), check=check, **kw)


# --- Instructions -------------------------------------------------------------------

_INSTRUCTIONS = [
    # Doing nothing, copying and loading numbers
    dict(name="NOP", syntax="NOP", summary="Does nothing; fills a delay slot.",
         body="Fills [[concept:delay-slot|delay slots]]. Same as `SLL R0 R0 0`.",
         examples=[_mips("In a delay slot", """
JAL GetCurrentPlayerIndex
NOP""")],
         see=["concept:delay-slot", "mips:jal"], tags=["no operation", "delay slot"]),
    dict(name="LI", kind="pseudo", syntax="LI rt value",
         summary="Loads a number or parameter into a register.",
         body="""Becomes:
- -32768 to 32767: `ADDIU rt R0 value`
- 0 to 65535: `ORI rt R0 value`
- larger: `LUI` + `ADDIU`

Can be two instructions: not in a [[concept:delay-slot|delay slot]].""",
         examples=[
             _mips("-10 into A1", "LI A1 -10"),
             _mips("Parameter value", "LI A1 toll", params=[["+Number", "toll"]]),
         ],
         see=["mips:addiu", "mips:lui", "mips:ori", "concept:delay-slot"], tags=["load", "number", "constant"]),
    dict(name="MOVE", kind="pseudo", syntax="MOVE rd rs",
         summary="Copies one register into another.", body="Same as `ADDU rd rs R0`.",
         examples=[_mips("Result to argument", """
JAL GetCurrentPlayerIndex
NOP
MOVE A0 V0""")],
         see=["mips:addu", "concept:calling-functions"], tags=["copy", "register"]),
    # Arithmetic
    dict(name="ADDIU", syntax="ADDIU rt rs immediate",
         summary="Adds a constant to a register: rt = rs + constant (-32768 to 32767).",
         body="""- `ADDIU A1 R0 -10`: load a number
- `ADDIU SP SP -24`: reserve [[concept:stack|stack]]
- `ADDIU A0 A0 lo(label)`: address low half ([[syntax:hi-lo]])

Never traps on overflow.""",
         examples=[_mips("Reserve and free stack", """
ADDIU SP SP -8
ADDIU SP SP 8""")],
         see=["mips:addu", "mips:li", "concept:stack"], tags=["add", "plus", "constant", "number"]),
    dict(name="ADDI", syntax="ADDI rt rs immediate",
         summary="Adds a constant like ADDIU, but crashes on overflow. Use ADDIU.", see=["mips:addiu"]),
    dict(name="ADDU", syntax="ADDU rd rs rt", summary="Adds two registers and puts the sum in a third: rd = rs + rt.",
         body="With `R0`: copy ([[mips:move|MOVE]]).",
         examples=[_mips("Add", """
ADDIU T0 R0 20
ADDIU T1 R0 22
ADDU T2 T0 T1    ; 42""")],
         see=["mips:addiu", "mips:subu", "mips:move"], tags=["add", "plus"]),
    dict(name="ADD", syntax="ADD rd rs rt", summary="Adds two registers like ADDU, but crashes on overflow. Use ADDU.",
         see=["mips:addu"]),
    dict(name="SUBU", syntax="SUBU rd rs rt", summary="Subtracts one register from another: rd = rs - rt.",
         body="No subtract-constant: `ADDIU T0 T0 -5`. Negate: `SUBU T0 R0 T0`.",
         examples=[_mips("Subtract", """
ADDIU T0 R0 30
ADDIU T1 R0 12
SUBU T2 T0 T1    ; 18""")],
         see=["mips:addu", "mips:addiu"], tags=["subtract", "minus", "negate"]),
    dict(name="SUB", syntax="SUB rd rs rt", summary="Subtracts like SUBU, but crashes on overflow. Use SUBU.",
         see=["mips:subu"]),
    dict(name="MULT", syntax="MULT rs rt", summary="Multiplies two registers; get the result with MFLO.",
         body="Result: [[mips:mflo|MFLO]]. No `MULT`/`DIV` within 2 instructions after `MFHI`/`MFLO`. Powers of 2: [[mips:sll|SLL]].",
         examples=[_mips("3 x 7", """
ADDIU T0 R0 3
ADDIU T1 R0 7
MULT T0 T1
MFLO T2          ; 21""")],
         see=["mips:mflo", "mips:mfhi", "mips:div", "mips:sll"], tags=["multiply", "times"]),
    dict(name="MULTU", syntax="MULTU rs rt", summary="Multiplies two registers as unsigned numbers; get the result with MFLO.", see=["mips:mult"]),
    dict(name="DIV", syntax="DIV rs rt", summary="Divides one register by another: MFLO gets the quotient, MFHI the remainder.",
         body="Divide by 0 gives garbage, no crash.",
         examples=[_mips("17 / 5", """
ADDIU T0 R0 17
ADDIU T1 R0 5
DIV T0 T1
MFLO T2          ; 3
MFHI T3          ; 2""")],
         see=["mips:divu", "mips:mflo", "mips:mfhi", "game:guRandom"], tags=["divide", "remainder", "modulo"]),
    dict(name="DIVU", syntax="DIVU rs rt", summary="Divides as unsigned numbers: MFLO gets the quotient, MFHI the remainder.",
         body="Random ranges: remainder of [[game:guRandom]].",
         examples=[_mips("Random 0-19", """
JAL guRandom
NOP
ADDIU T0 R0 20
DIVU V0 T0
MFHI S0          ; 0-19""")],
         see=["mips:div", "game:guRandom", "reg:s0"], tags=["random", "range"]),
    dict(name="MFLO", syntax="MFLO rd", summary="Copies the LO result of MULT or DIV into a register.", see=["mips:mult", "mips:div", "mips:mfhi"]),
    dict(name="MFHI", syntax="MFHI rd", summary="Copies the HI result of MULT or DIV (the remainder) into a register.", see=["mips:mult", "mips:div", "mips:mflo"]),
    dict(name="MTLO", syntax="MTLO rs", summary="Copies a register into LO.", see=["mips:mflo"]),
    dict(name="MTHI", syntax="MTHI rs", summary="Copies a register into HI.", see=["mips:mfhi"]),
    # Logic and shifts
    dict(name="AND", syntax="AND rd rs rt", summary="Keeps only the bits set in both registers.", see=["mips:andi", "mips:or"], tags=["bits", "mask", "flags"]),
    dict(name="ANDI", syntax="ANDI rt rs immediate", summary="Keeps only the bits set in both a register and a constant (0-65535).",
         body="`ANDI T0 T0 1`: 1 if odd.",
         examples=[_mips("Even turn?", """
LUI T0 hi(current_turn)
LBU T0 lo(current_turn)(T0)
ANDI T0 T0 1
BEQ T0 R0 even_turn
NOP
even_turn:""")],
         see=["mips:and", "mips:ori", "game:current_turn"], tags=["bits", "mask", "odd", "even"]),
    dict(name="OR", syntax="OR rd rs rt", summary="Combines the bits set in either register.", see=["mips:ori", "mips:and"], tags=["bits", "flags"]),
    dict(name="ORI", syntax="ORI rt rs immediate", summary="Combines a register's bits with a constant's (0-65535); also loads 0-65535.",
         body="`ORI T0 R0 0xFFFF`: load 0-65535.", see=["mips:or", "mips:li"], tags=["bits", "flags"]),
    dict(name="XOR", syntax="XOR rd rs rt", summary="Sets the bits that differ between two registers.", body="0 when equal.",
         see=["mips:xori"], tags=["bits", "toggle"]),
    dict(name="XORI", syntax="XORI rt rs immediate", summary="Flips a register's bits where a constant (0-65535) has them set.",
         body="`XORI T0 T0 1` flips 0/1.",
         examples=[_mips("Toggle", """
ADDIU T0 R0 0
XORI T0 T0 1     ; 1
XORI T0 T0 1     ; 0""")],
         see=["mips:xor"], tags=["toggle", "flip", "switch"]),
    dict(name="NOR", syntax="NOR rd rs rt", summary="Sets the bits set in neither register; with R0 it flips every bit.", body="`NOR rd rs R0`: NOT.", see=["mips:or"]),
    dict(name="SLL", syntax="SLL rd rt shift", summary="Shifts a register's bits left, multiplying by 2 per step.",
         body="`SLL T0 T0 2`: index to word offset.",
         examples=[_mips("Index 3 to offset 12", """
ADDIU T0 R0 3
SLL T0 T0 2""")],
         see=["mips:srl", "mips:sra", "mips:sllv"], tags=["shift", "multiply", "times"]),
    dict(name="SRL", syntax="SRL rd rt shift", summary="Shifts a register's bits right, halving an unsigned number per step.",
         see=["mips:sra", "mips:sll"], tags=["shift", "divide"]),
    dict(name="SRA", syntax="SRA rd rt shift", summary="Shifts a register's bits right, halving a signed number per step.",
         see=["mips:srl"], tags=["shift"]),
    dict(name="SLLV", syntax="SLLV rd rt rs", summary="Shifts left like SLL, by the amount in a register.", see=["mips:sll"]),
    dict(name="SRLV", syntax="SRLV rd rt rs", summary="Shifts right like SRL, by the amount in a register.", see=["mips:srl"]),
    dict(name="SRAV", syntax="SRAV rd rt rs", summary="Shifts right like SRA, by the amount in a register.", see=["mips:sra"]),
    dict(name="SLT", syntax="SLT rd rs rt", summary="Sets rd to 1 if rs is less than rt, else 0 (signed).",
         body="Then branch on rd: no branch-if-less for two registers.",
         examples=[_mips("12 < 20?", """
ADDIU T0 R0 12
ADDIU T1 R0 20
SLT T2 T0 T1     ; 1
BNE T2 R0 less
NOP
less:""")],
         see=["mips:slti", "mips:sltu", "mips:bne", "game:PlayerHasCoins"], tags=["compare", "less than"]),
    dict(name="SLTI", syntax="SLTI rt rs immediate", summary="Sets rt to 1 if rs is less than a constant, else 0 (signed).",
         see=["mips:slt"], tags=["compare"]),
    dict(name="SLTU", syntax="SLTU rd rs rt", summary="Sets rd to 1 if rs is less than rt, else 0 (unsigned).", see=["mips:slt"]),
    dict(name="SLTIU", syntax="SLTIU rt rs immediate", summary="Sets rt to 1 if rs is less than a constant, else 0 (unsigned).", see=["mips:slti"]),
    dict(name="LUI", syntax="LUI rt immediate", summary="Loads a constant into a register's upper half; the lower half becomes 0.",
         body="Upper half of an address; lower half from `ADDIU` or a load offset. See [[syntax:hi-lo]].",
         examples=[
             _mips("Message address", """
LUI A1 hi(message)
ADDIU A1 A1 lo(message)
.align 4
message:
.ascii "Hello",0xFF,0"""),
             _mips("Read game byte", """
LUI T0 hi(current_turn)
LBU T1 lo(current_turn)(T0)"""),
         ],
         see=["syntax:hi-lo", "mips:addiu", "mips:lbu"], tags=["address", "upper", "load"]),
    # Loads and stores
    dict(name="LW", syntax="LW rt offset(base)", summary="Loads 4 bytes from memory into a register.",
         body="Address: multiple of 4.",
         examples=[_mips("Save, restore", """
SW S0 24(SP)
LW S0 24(SP)""")],
         see=["mips:sw", "mips:lh", "mips:lb", "concept:stack"], tags=["load", "memory", "read"]),
    dict(name="SW", syntax="SW rt offset(base)", summary="Stores a register's 4 bytes into memory.",
         body="Address: multiple of 4. `SW RA 20(SP)` saves RA.",
         see=["mips:lw", "concept:stack", "reg:ra"], tags=["store", "memory", "write", "save"]),
    dict(name="LH", syntax="LH rt offset(base)", summary="Loads 2 bytes from memory, signed (-32768 to 32767).",
         body="Address: multiple of 2. Coins are s16.",
         examples=[_mips("Player 1 coins", """
LUI T0 hi(p1_coins)
LH T1 lo(p1_coins)(T0)""")],
         see=["mips:lhu", "mips:sh"], tags=["load", "s16"]),
    dict(name="LHU", syntax="LHU rt offset(base)", summary="Loads 2 bytes from memory, unsigned (0 to 65535).", see=["mips:lh"], tags=["load", "u16"]),
    dict(name="SH", syntax="SH rt offset(base)", summary="Stores a register's low 2 bytes into memory.", see=["mips:lh"], tags=["store", "s16", "u16"]),
    dict(name="LB", syntax="LB rt offset(base)", summary="Loads 1 byte from memory, signed (-128 to 127).", see=["mips:lbu", "mips:sb"], tags=["load", "s8"]),
    dict(name="LBU", syntax="LBU rt offset(base)", summary="Loads 1 byte from memory, unsigned (0 to 255).",
         body="Most counters (turn, space, stars) are u8.",
         examples=[_mips("Current turn", """
LUI T0 hi(current_turn)
LBU A0 lo(current_turn)(T0)""")],
         see=["mips:lb", "mips:sb", "game:current_turn"], tags=["load", "u8"]),
    dict(name="SB", syntax="SB rt offset(base)", summary="Stores a register's low byte into memory.",
         examples=[_mips("Player 1 +1 star", """
LUI T0 hi(p1_stars)
LBU T1 lo(p1_stars)(T0)
ADDIU T1 T1 1
SB T1 lo(p1_stars)(T0)""")],
         see=["mips:lbu"], tags=["store", "u8", "s8"]),
    # Jumps and branches
    dict(name="JAL", syntax="JAL label", summary="Calls a function, saving the way back in RA.",
         body="""Arguments in `A0`-`A3`; result in `V0`. See [[concept:calling-functions]].
- Has a [[concept:delay-slot|delay slot]].
- Overwrites `RA`: save it first ([[concept:stack]]).""",
         examples=[_mips("Two arguments", """
JAL GetCurrentPlayerIndex
NOP
MOVE A0 V0
JAL AdjustPlayerCoins
ADDIU A1 R0 5    ; delay slot: set before the call""")],
         see=["concept:calling-functions", "concept:delay-slot", "reg:ra", "mips:jr"], tags=["call", "function"]),
    dict(name="JR", syntax="JR rs", summary="Jumps to the address in a register; JR RA returns.",
         body="Delay slot often frees the stack: `ADDIU SP SP 24`.",
         see=["reg:ra", "concept:stack", "mips:jal"], tags=["return"]),
    dict(name="J", syntax="J label", summary="Jumps to a label.", body="Has a delay slot.",
         examples=[_mips("Skip code", """
J done
NOP
ADDIU T0 R0 1    ; skipped
done:""")],
         see=["mips:beq", "concept:branches"], tags=["goto", "loop"]),
    dict(name="JALR", syntax="JALR rs", summary="Calls the function whose address is in a register.", see=["mips:jal"], tags=["call"]),
    dict(name="BEQ", syntax="BEQ rs rt label", summary="Jumps to a label if two registers are equal.",
         body="`BEQ V0 R0 label`: if the call returned 0. Has a delay slot. See [[concept:branches]].",
         examples=[_mips("Can't pay: skip", """
JAL GetCurrentPlayerIndex
NOP
MOVE A0 V0
JAL PlayerHasCoins
ADDIU A1 R0 10
BEQ V0 R0 cannot_pay
NOP
; take coins
cannot_pay:""")],
         see=["mips:bne", "concept:branches", "mips:beqz"], tags=["if", "compare", "equal", "branch"]),
    dict(name="BNE", syntax="BNE rs rt label", summary="Jumps to a label if two registers differ.",
         body="`BNE V0 R0 label`: if the call returned non-zero.",
         examples=[_mips("Loop over 4 players", """
ADDIU S0 R0 0
next_player:
; use player S0
ADDIU S0 S0 1
ADDIU T0 R0 4
BNE S0 T0 next_player
NOP""")],
         see=["mips:beq", "concept:branches", "mips:bnez"], tags=["if", "compare", "loop", "branch"]),
    dict(name="BEQZ", kind="pseudo", syntax="BEQZ rs label", summary="Jumps to a label if a register is 0.", body="`BEQ rs R0 label`.",
         see=["mips:beq"], tags=["branch"]),
    dict(name="BNEZ", kind="pseudo", syntax="BNEZ rs label", summary="Jumps to a label if a register isn't 0.", body="`BNE rs R0 label`.",
         see=["mips:bne"], tags=["branch"]),
    dict(name="BNEZL", kind="pseudo", syntax="BNEZL rs label", summary="Jumps if a register isn't 0; the delay slot runs only if it jumps.", body="`BNEL rs R0 label`.",
         see=["mips:bnel"]),
    dict(name="BGEZ", syntax="BGEZ rs label", summary="Jumps to a label if a register is 0 or more.", see=["mips:bltz", "concept:branches"]),
    dict(name="BGTZ", syntax="BGTZ rs label", summary="Jumps to a label if a register is above 0.", see=["mips:blez", "concept:branches"]),
    dict(name="BLEZ", syntax="BLEZ rs label", summary="Jumps to a label if a register is 0 or less.", see=["mips:bgtz", "concept:branches"]),
    dict(name="BLTZ", syntax="BLTZ rs label", summary="Jumps to a label if a register is below 0.",
         body="Tests -1 results, e.g. [[game:PlayerHasItem]].", see=["mips:bgez", "concept:branches"]),
    dict(name="BEQL", syntax="BEQL rs rt label", summary="Jumps if two registers are equal; the delay slot runs only if it jumps.",
         body="All \"likely\" branches (`BNEL`, `BGEZL`...) work this way.", see=["mips:beq", "concept:delay-slot"]),
    dict(name="BNEL", syntax="BNEL rs rt label", summary="Jumps if two registers differ; the delay slot runs only if it jumps.",
         see=["mips:bne", "mips:beql"]),
    # Floating point basics
    dict(name="LWC1", syntax="LWC1 ft offset(base)", summary="Loads a 4-byte float from memory into a float register.",
         see=["mips:swc1", "reg:f0", "mips:mtc1"], tags=["float", "load"]),
    dict(name="SWC1", syntax="SWC1 ft offset(base)", summary="Stores a float register's 4 bytes into memory.",
         see=["mips:lwc1", "reg:f0"], tags=["float", "store"]),
    dict(name="MTC1", syntax="MTC1 rt fs", summary="Copies a register's bits into a float register, unconverted.",
         body="No conversion; follow with `CVT.S.W`.",
         see=["mips:mfc1", "mips:cvt.s", "reg:f0"], tags=["float"]),
    dict(name="MFC1", syntax="MFC1 rt fs", summary="Copies a float register's bits into a register, unconverted.",
         see=["mips:mtc1"], tags=["float"]),
    dict(name="SYSCALL", syntax="SYSCALL", summary="Calls the operating system; unused by the games."),
    dict(name="BREAK", syntax="BREAK", summary="Stops the game at a breakpoint."),
]


def _syntax(op, details):
    display = details.get("display", [])
    names = {"uint16": "immediate", "int16": "offset", "uint5": "shift", "uint26shift2": "label",
             "uint26": "code", "uint20?": "[code]", "rd?": "[rd]", "cc?": "[cc]"}
    out = ""
    for piece in display:
        word = names.get(piece, piece)
        if piece in ("(", ")") or out.endswith("("):
            out += word
        else:
            out += (" " if out else "") + word
    if op.startswith("b") and display and display[-1] == "uint16":
        out = out[: -len("immediate")] + "label"
    name = op.replace(".cond", ".eq").replace(".fmt", ".s").upper()
    return (name + " " + out).strip()


_FLOAT_CONDS = ["f", "un", "eq", "ueq", "olt", "ult", "ole", "ule", "sf", "ngle", "seq", "ngl",
                "lt", "nge", "le", "ngt"]


def _words(op, details):
    if op == "c.cond.fmt":
        return ["c.%s.%s" % (c, f.lower()) for c in _FLOAT_CONDS for f in details.get("fmts", [])]
    if op.endswith(".fmt"):
        return [op[:-3] + f.lower() for f in details.get("fmts", [])]
    return [op]


def entries():
    explained = {}
    for raw in _INSTRUCTIONS:
        e = dict(raw)
        e.setdefault("kind", "instruction")
        e["id"] = "mips:" + e["name"].lower()
        e["category"] = "MIPS"
        e["lang"] = "mips"
        explained[e["name"].lower()] = e
    out = list(explained.values())
    for op in sorted(opcode_details):
        details = opcode_details[op]
        words = _words(op, details)
        if op in explained:
            continue
        if op == "c.cond.fmt":
            name, entry_id = "C.cond.fmt", "mips:c.cond"
        elif op.endswith(".fmt"):
            # e.g. ADD.fmt (ADD.S, ADD.D); "mips:add" is the integer ADD, so "mips:add.fmt".
            name = op[:-4].upper() + ".fmt"
            entry_id = "mips:" + (op if op[:-4] in opcode_details else op[:-4])
        else:
            name, entry_id = op.upper(), "mips:" + op
        out.append(dict(
            id=entry_id, kind="instruction", category="MIPS", lang="mips",
            name=name, words=words, syntax=_syntax(op, details),
            summary=OPCODES[op],
            body=("Formats: %s." % ", ".join("." + f for f in details["fmts"])) if details.get("fmts") else "",
        ))
    for e in out:
        if e["id"].startswith("mips:") and "syntax" not in e:
            e["syntax"] = e["name"]
    return _REGISTERS + _DIRECTIVES + _SYNTAX + out


# --- Registers ----------------------------------------------------------------------

def _reg(name, words, summary, body="", see=(), tags=(), examples=()):
    return dict(id="reg:" + name.lower(), kind="register", category="MIPS", lang="mips",
                name=name, words=words, summary=summary, body=body, see=list(see),
                tags=list(tags), examples=list(examples))


_REGISTERS = [
    _reg("R0", ["r0", "zero", "$zero", "$0"], "Always 0.",
         """- `ADDIU A1 R0 -10`: load a number
- `ADDU A0 V0 R0`: copy
- `BEQ V0 R0 label`: test for 0
- `SW R0 16(SP)`: store 0""",
         see=["mips:addiu", "mips:beq"], tags=["zero"]),
    _reg("AT", ["at", "$at"], "Assembler temporary. Don't use."),
    _reg("V0", ["v0", "$v0"], "Return value.",
         "Not kept across calls; copy it to an `S` register first. Board code returns its choice here.",
         see=["reg:v1", "concept:calling-functions"], tags=["return", "result"],
         examples=[_mips("Keep a result", """
JAL GetCurrentPlayerIndex
NOP
MOVE S0 V0""")]),
    _reg("V1", ["v1", "$v1"], "Second return value; scratch.", see=["reg:v0"]),
    _reg("A0", ["a0", "$a0"], "Argument 1.",
         """`A0`-`A3`: arguments 1-4; more on the stack ([[concept:calling-functions]]). Player functions take the index here (-1: current). Not kept across calls.

At event start, seemingly the space index (unconfirmed).""",
         see=["reg:a1", "concept:calling-functions", "concept:players"], tags=["argument", "parameter"],
         examples=[_mips("Two arguments", """
ADDIU A0 R0 0    ; player 1
JAL AdjustPlayerCoins
ADDIU A1 R0 10   ; +10""")]),
    _reg("A1", ["a1", "$a1"], "Argument 2.", see=["reg:a0"]),
    _reg("A2", ["a2", "$a2"], "Argument 3.", see=["reg:a0"]),
    _reg("A3", ["a3", "$a3"], "Argument 4.", "Argument 5 at `16(SP)`, 6 at `20(SP)`...",
         see=["reg:a0", "concept:calling-functions"]),
    _reg("T0", ["t0", "t1", "t2", "t3", "t4", "t5", "t6", "t7", "t8", "t9",
                "$t0", "$t1", "$t2", "$t3", "$t4", "$t5", "$t6", "$t7", "$t8", "$t9"],
         "Temporaries T0-T9; calls may overwrite them.",
         "Values that must survive a call: [[reg:s0|S registers]].",
         see=["reg:s0"], tags=["temporary", "scratch"]),
    _reg("S0", ["s0", "s1", "s2", "s3", "s4", "s5", "s6", "s7", "$s0", "$s1", "$s2", "$s3",
                "$s4", "$s5", "$s6", "$s7"],
         "Saved registers S0-S7: survive calls.",
         "Your event must save and restore any it uses ([[concept:stack]]).",
         see=["concept:stack", "reg:t0"], tags=["saved", "callee-saved", "keep"],
         examples=[_mips("Keep across calls", """
SW S0 24(SP)     ; save caller's S0
JAL GetCurrentPlayerIndex
NOP
MOVE S0 V0
JAL PlaySound
ADDIU A0 R0 0x106
MOVE A0 S0
JAL AdjustPlayerCoins
ADDIU A1 R0 5
LW S0 24(SP)     ; restore""")]),
    _reg("SP", ["sp", "$sp", "r29"], "Stack pointer.",
         "Grows down. Subtract to reserve, add back before returning. Multiple of 8.",
         see=["concept:stack"], tags=["stack"]),
    _reg("RA", ["ra", "$ra", "r31"], "Return address.",
         "`JAL` overwrites it: save on the [[concept:stack|stack]] before calling, restore before `JR RA`. Forgetting crashes.",
         see=["concept:stack", "mips:jal", "mips:jr"], tags=["return"]),
    _reg("FP", ["fp", "s8", "$fp", "$s8"], "Frame pointer (S8). Treat as an S register.", see=["reg:s0"]),
    _reg("GP", ["gp", "$gp"], "Global pointer. Don't change."),
    _reg("K0", ["k0", "k1", "$k0", "$k1"], "Interrupt registers K0, K1. Don't use."),
    _reg("F0", ["f0", "f1", "f2", "f3", "f4", "f5", "f6", "f7", "f8", "f9", "f10", "f11", "f12",
                "f13", "f14", "f15", "f16", "f17", "f18", "f19", "f20", "f21", "f22", "f23", "f24",
                "f25", "f26", "f27", "f28", "f29", "f30", "f31"],
         "Float registers F0-F31.",
         "Float result: `F0`. Float arguments: `F12`, `F14`. Move with [[mips:lwc1]], [[mips:swc1]], [[mips:mtc1]], [[mips:mfc1]].",
         see=["mips:lwc1", "c:f32"], tags=["float"]),
]


# --- Directives ----------------------------------------------------------------------

def _dir(name, summary, body="", syntax=None, examples=(), see=(), tags=(), words=None):
    return dict(id="dir:" + name, kind="directive", category="MIPS", lang="mips", name="." + name,
                words=words or [name, "." + name], syntax=syntax or "." + name,
                summary=summary, body=body, examples=list(examples), see=list(see), tags=list(tags))


_DIRECTIVES = [
    _dir("ascii", "Writes text and bytes; no final 0.",
         "Mix strings and bytes: `.ascii \"Hi\",0xC2,0xFF`. `\\x` escapes work. Game bytes: [[concept:message-text]]. Place after code, after `.align 4`.",
         syntax='.ascii "text"[,byte,...]',
         examples=[_mips("Hello!", """
.align 4
message:
.ascii "Hello",0xC2,0xFF,0   ; 0xC2 is !, 0xFF waits""")],
         see=["dir:asciiz", "concept:message-text", "dir:align"], tags=["string", "text", "message"]),
    _dir("asciiz", "Writes text plus a final 0.",
         "For C functions like [[game:sprintf]]. Game messages end `0xFF,0` instead.",
         syntax='.asciiz "text"',
         examples=[_mips("sprintf format", """
percent_d:
.asciiz "%d\"""")],
         see=["dir:ascii", "game:sprintf"], tags=["string"]),
    _dir("byte", "Writes bytes.", "`.db` is the same.",
         syntax=".byte value[,value,...]", words=["byte", ".byte", ".db", "db"],
         examples=[_mips("Message control bytes", """
.byte 0x0B                ; message start
.byte 0x1A,0x1A,0x1A,0x1A ; picture gap""")],
         see=["concept:message-text", "dir:halfword", "dir:word"], tags=["data"]),
    _dir("halfword", "Writes 2-byte values.", "`.dh` is the same. Align to 2.",
         syntax=".halfword value[,value,...]", words=["halfword", ".halfword", ".dh", "dh"], see=["dir:byte"]),
    _dir("word", "Writes 4-byte values or label addresses.", "`.dw` is the same. Align to 4.",
         syntax=".word value[,value,...]", words=["word", ".word", ".dw", "dw"],
         examples=[_mips("Table", """
.align 4
table:
.word 10, 20, 30""")],
         see=["dir:align", "dir:byte"], tags=["data", "table"]),
    _dir("float", "Writes 4-byte floats.", syntax=".float value[,value,...]", see=["reg:f0"]),
    _dir("fill", "Writes length bytes of one value (default 0).", "`.fill 8`: room for [[game:sprintf]] output.",
         syntax=".fill length[,value]",
         examples=[_mips("Text buffer", """
coin_text:
.fill 8""")], tags=["buffer", "space"]),
    _dir("skip", "Skips bytes without writing.", syntax=".skip length"),
    _dir("align", "Pads with 0 to a multiple of n (power of 2).",
         "`.align 4` before data words and text.",
         syntax=".align n", examples=[_mips("Before data", """
.align 4
numbers:
.word 1,2,3""")], see=["dir:word", "dir:ascii"]),
    _dir("definelabel", "Names a number.",
         "PartyPlanner defines game functions and [[concept:parameters|parameters]] this way.",
         syntax=".definelabel name,value",
         examples=[_mips("Constant", """
.definelabel TOLL,10
ADDIU A1 R0 TOLL""")], see=["concept:parameters", "syntax:labels", "syntax:equ"], tags=["constant", "define"]),
    _dir("if", "Assembles lines only if a value isn't 0.",
         "Decided when assembling, not at run time. Pairs with Boolean parameters.",
         syntax=".if value", words=["if", ".if", ".else", "else", ".elseif", "elseif", ".endif", "endif"],
         examples=[_mips("Per-space code", """
.if double
ADDIU A1 R0 20
.else
ADDIU A1 R0 10
.endif""", params=[["Boolean", "double"]])],
         see=["param:boolean", "concept:branches"], tags=["condition", "conditional assembly"]),
    _dir("beginstatic", "Code or data shared by every space using the event.",
         "Not at the top. Values don't persist between turns. Test Compile rejects it; board writes accept it.",
         syntax=".beginstatic ... .endstatic", words=["beginstatic", ".beginstatic", "endstatic", ".endstatic"],
         examples=[_mips("Shared message", """
J done
NOP
.beginstatic
.align 4
shared_message:
.ascii "Shared",0xFF,0
.endstatic
.align 4
done:""", check="none")], tags=["shared"]),
]


# --- Assembler syntax --------------------------------------------------------------

_SYNTAX = [
    dict(id="syntax:hi-lo", kind="syntax", category="MIPS", lang="mips", name="hi() and lo()",
         words=["hi", "lo"], syntax="LUI rt hi(label) / ADDIU rt rt lo(label)",
         summary="Upper and lower halves of an address.",
         body="Use as a pair: `hi()` corrects for `lo()` being signed.",
         examples=[_mips("Address and data", """
LUI A1 hi(message)
ADDIU A1 A1 lo(message)       ; A1 = address
LUI T0 hi(current_turn)
LBU T1 lo(current_turn)(T0)   ; T1 = byte
.align 4
message:
.ascii "Hi",0xFF,0""")],
         see=["mips:lui", "mips:addiu", "mips:lbu"], tags=["address", "upper", "lower", "pointer"]),
    dict(id="syntax:labels", kind="syntax", category="MIPS", lang="mips", name="Labels",
         words=["label", "main"], syntax="name:",
         summary="name: marks a place in code or data.",
         body="Targets for branches and jumps; addresses for `hi()`/`lo()`. Scoped per space. Execution starts at the top, or at `main:`. Never put data first.",
         examples=[_mips("Loop", """
ADDIU T0 R0 3
again:
ADDIU T0 T0 -1
BNE T0 R0 again
NOP""")],
         see=["concept:branches", "syntax:hi-lo"], tags=["jump target", "name"]),
    dict(id="syntax:comments", kind="syntax", category="MIPS", lang="mips", name="Comments",
         words=[], syntax="; text   // text   /* text */",
         summary="Ignored text.",
         body="Header lines are comments too ([[hdr:name]]). No `\"` in a comment after a data line.",
         see=["hdr:name"]),
    dict(id="syntax:operands", kind="syntax", category="MIPS", lang="mips", name="Operands and Numbers",
         words=[], syntax="ADDIU A1 R0 0x10",
         summary="Spaces or commas between operands; numbers 10, -10, 0x0A, 0b1010, 0o12.",
         body="""Registers: any case, `$` optional. No arithmetic: `toll+1` and `0-toll` are errors. Negate a value:""",
         examples=[_mips("Minus a parameter", """
ADDIU A1 R0 toll
SUBU A1 R0 A1        ; A1 = -toll""", params=[["+Number", "toll"]])],
         see=["syntax:labels"], tags=["syntax", "hex", "comma", "expression", "negative"]),
    dict(id="syntax:equ", kind="syntax", category="MIPS", lang="mips", name="equ",
         words=["equ"], syntax="name equ text",
         summary="Text replacement.",
         body="Can stand for a list; used by [[param:space-array|Space[] parameters]].",
         examples=[_mips("Replace", """
COINS equ 15
ADDIU A1 R0 COINS""")], see=["dir:definelabel"]),
    dict(id="syntax:func-addr", kind="syntax", category="MIPS", lang="any", name="func_ and D_ Names",
         words=[], syntax="JAL func_800EC9DC   /   D_800CD098",
         summary="Unnamed functions and data by address.",
         body="`func_` + address calls; `D_` + address is data. Work in C too.",
         examples=[_mips("Wait for A", """
JAL func_800EC9DC
NOP""")], see=["concept:messages"], tags=["address", "unnamed"]),
]
