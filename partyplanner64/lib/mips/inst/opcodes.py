"""The MIPS opcode table and instruction matching (port of mips-inst opcodes.js).

Each opcode has a `format` (its bit layout, most significant piece first:
binary literals, or value names like rs/rt/int16; a list gives
alternatives), optional `fmts` (allowed .fmt values) and `display` (the
order values are written in assembly).
"""

from .bitstrings import compare_bits, is_binary_literal, make_bit_mask_from_string, pad_bit_string
from .immediates import get_imm_format_details
from .regs import get_fmt3_bits, get_fmt_bits


def get_opcode_details(opcode):
    return opcode_details.get(opcode.lower())


_value_bit_lengths = {}


def get_value_bit_length(s):
    try:
        return _value_bit_lengths[s]
    except KeyError:
        pass
    calculated = _compute_value_bit_length(s)
    _value_bit_lengths[s] = calculated
    return calculated


def _compute_value_bit_length(s):
    if is_binary_literal(s):
        return len(s)

    s = s.replace("?", "", 1)
    if s in ("cc", "fmt3"):
        return 3
    if s == "cond":
        return 4
    if s in ("rs", "rt", "rd", "fs", "ft", "fd", "fr", "sa", "fmt"):
        return 5

    imm_details = get_imm_format_details(s)
    if imm_details:
        return imm_details["bits"]

    raise ValueError("Unrecongized format value: %s" % s)


def find_match(inst):
    """Returns the name of the opcode that best matches the instruction, or ""."""
    inst &= 0xFFFFFFFF
    best_match = ""
    best_match_score = 0
    for op_name, compiled in _compiled_formats:
        if compiled is None:
            details = opcode_details[op_name]
            score = _format_matches(inst, details["format"], details.get("fmts"))
        else:
            mask, value, literal_score, fmt_checks = compiled
            if (inst & mask) != value:
                continue
            score = literal_score
            for offset, choices in fmt_checks:
                bits = (inst >> offset) & 0x1F if choices[0][1] == 5 else (inst >> offset) & 0x7
                for choice_bits, length in choices:
                    if bits == choice_bits:
                        score += length
                        break
                else:
                    score = 0
                    break
        if score > best_match_score:
            best_match = op_name
            best_match_score = score
    return best_match


def _format_matches(number, fmt_list, fmts):
    """Returns number of literal bits matched, if the overall format matches."""
    score = 0
    bit_offset = 0
    for piece in reversed(fmt_list):
        if isinstance(piece, list):
            matched_one = False
            for alt in piece:
                temp_score = _check_piece(alt, number, bit_offset, fmts)
                if temp_score >= 0:
                    matched_one = True
                    score += temp_score
                    bit_length = get_value_bit_length(alt)
                    break
            if not matched_one:
                return 0
        else:
            temp_score = _check_piece(piece, number, bit_offset, fmts)
            if temp_score >= 0:
                score += temp_score
                bit_length = get_value_bit_length(piece)
            else:
                return 0
        bit_offset += bit_length
    return score


def _check_piece(piece, number, bit_offset, fmts):
    if not is_binary_literal(piece):
        if piece == "fmt":
            for f in fmts:
                fmt_bit_string = pad_bit_string(format(get_fmt_bits(f), "b"), 5)
                if compare_bits(number, fmt_bit_string, bit_offset):
                    return len(fmt_bit_string)
            return -1
        if piece == "fmt3":
            for f in fmts:
                fmt_bit_string = pad_bit_string(format(get_fmt3_bits(f), "b"), 3)
                if compare_bits(number, fmt_bit_string, bit_offset):
                    return len(fmt_bit_string)
            return -1
        return 0  # non-literal contributes nothing

    if compare_bits(number, piece, bit_offset):
        return len(piece)
    return -1


def _compile_format(details):
    """Precomputes a mask/value test equivalent to _format_matches, when possible.

    Lists of alternatives whose first entry is a value name always match
    (contributing nothing), so they only need skipping. Returns None for
    formats this shortcut doesn't cover.
    """
    mask = 0
    value = 0
    literal_score = 0
    fmt_checks = []
    bit_offset = 0
    for piece in reversed(details["format"]):
        if isinstance(piece, list):
            if is_binary_literal(piece[0]):
                return None
            length = get_value_bit_length(piece[0])
        elif is_binary_literal(piece):
            length = len(piece)
            mask |= ((1 << length) - 1) << bit_offset
            value |= make_bit_mask_from_string(piece) << bit_offset
            literal_score += length
        elif piece in ("fmt", "fmt3"):
            length = 5 if piece == "fmt" else 3
            get_bits = get_fmt_bits if piece == "fmt" else get_fmt3_bits
            fmt_checks.append((bit_offset, [(get_bits(f), length) for f in details["fmts"]]))
        else:
            length = get_value_bit_length(piece)
        bit_offset += length
    return (mask, value, literal_score, fmt_checks)


opcode_details = {
    "abs.fmt": {"format": ["010001", "fmt", "00000", "fs", "fd", "000101"], "fmts": ["S", "D"], "display": ["fd", "fs"]},
    "add": {"format": ["000000", "rs", "rt", "rd", "00000100000"], "display": ["rd", "rs", "rt"]},
    "add.fmt": {"format": ["010001", "fmt", "ft", "fs", "fd", "000000"], "fmts": ["S", "D"], "display": ["fd", "fs", "ft"]},
    "addi": {"format": ["001000", "rs", "rt", "int16"], "display": ["rt", "rs", "int16"]},
    "addiu": {"format": ["001001", "rs", "rt", "uint16"], "display": ["rt", "rs", "uint16"]},
    "addu": {"format": ["000000", "rs", "rt", "rd", "00000100001"], "display": ["rd", "rs", "rt"]},
    "and": {"format": ["000000", "rs", "rt", "rd", "00000100100"], "display": ["rd", "rs", "rt"]},
    "andi": {"format": ["001100", "rs", "rt", "uint16"], "display": ["rt", "rs", "uint16"]},
    "bc1f": {"format": ["010001", "01000", ["cc", "000"], "00", "int16"], "display": ["cc?", "int16"]},
    "bc1fl": {"format": ["010001", "01000", ["cc", "000"], "10", "int16"], "display": ["cc?", "int16"]},
    "bc1t": {"format": ["010001", "01000", ["cc", "000"], "01", "int16"], "display": ["cc?", "int16"]},
    "bc1tl": {"format": ["010001", "01000", ["cc", "000"], "11", "int16"], "display": ["cc?", "int16"]},
    "beq": {"format": ["000100", "rs", "rt", "uint16"], "display": ["rs", "rt", "uint16"]},
    "beql": {"format": ["010100", "rs", "rt", "uint16"], "display": ["rs", "rt", "uint16"]},
    "bgez": {"format": ["000001", "rs", "00001", "uint16"], "display": ["rs", "uint16"]},
    "bgezal": {"format": ["000001", "rs", "10001", "uint16"], "display": ["rs", "uint16"]},
    "bgezall": {"format": ["000001", "rs", "10011", "uint16"], "display": ["rs", "uint16"]},
    "bgezl": {"format": ["000001", "rs", "00011", "uint16"], "display": ["rs", "uint16"]},
    "bgtz": {"format": ["000111", "rs", "00000", "uint16"], "display": ["rs", "uint16"]},
    "bgtzl": {"format": ["010111", "rs", "00000", "uint16"], "display": ["rs", "uint16"]},
    "blez": {"format": ["000110", "rs", "00000", "uint16"], "display": ["rs", "uint16"]},
    "blezl": {"format": ["010110", "rs", "00000", "uint16"], "display": ["rs", "uint16"]},
    "bltz": {"format": ["000001", "rs", "00000", "uint16"], "display": ["rs", "uint16"]},
    "bltzal": {"format": ["000001", "rs", "10000", "uint16"], "display": ["rs", "uint16"]},
    "bltzall": {"format": ["000001", "rs", "10010", "uint16"], "display": ["rs", "uint16"]},
    "bltzl": {"format": ["000001", "rs", "00010", "uint16"], "display": ["rs", "uint16"]},
    "bne": {"format": ["000101", "rs", "rt", "uint16"], "display": ["rs", "rt", "uint16"]},
    "bnel": {"format": ["010101", "rs", "rt", "uint16"], "display": ["rs", "rt", "uint16"]},
    "break": {"format": ["000000", ["uint20", "00000000000000000000"], "001101"], "display": ["uint20?"]},
    "c.cond.fmt": {"format": ["010001", "fmt", "ft", "fs", ["cc", "000"], "00", "11", "cond"], "fmts": ["S", "D"], "display": ["cc?", "fs", "ft"]},
    "ceil.l.fmt": {"format": ["010001", "fmt", "00000", "fs", "fd", "001010"], "fmts": ["S", "D"], "display": ["fd", "fs"]},
    "ceil.w.fmt": {"format": ["010001", "fmt", "00000", "fs", "fd", "001110"], "fmts": ["S", "D"], "display": ["fd", "fs"]},
    "cfc1": {"format": ["010001", "00010", "rt", "fs", "00000000000"], "display": ["rt", "fs"]},
    "ctc1": {"format": ["010001", "00110", "rt", "fs", "00000000000"], "display": ["rt", "fs"]},
    "cop0": {"format": ["010000", "uint26"], "display": ["uint26"]},
    "cop1": {"format": ["010001", "uint26"], "display": ["uint26"]},
    "cop2": {"format": ["010010", "uint26"], "display": ["uint26"]},
    "cop3": {"format": ["010011", "uint26"], "display": ["uint26"]},
    "cvt.d.fmt": {"format": ["010001", "fmt", "00000", "fs", "fd", "100001"], "fmts": ["S", "W", "L"], "display": ["fd", "fs"]},
    "cvt.l.fmt": {"format": ["010001", "fmt", "00000", "fs", "fd", "100101"], "fmts": ["S", "D"], "display": ["fd", "fs"]},
    "cvt.s.fmt": {"format": ["010001", "fmt", "00000", "fs", "fd", "100000"], "fmts": ["D", "W", "L"], "display": ["fd", "fs"]},
    "cvt.w.fmt": {"format": ["010001", "fmt", "00000", "fs", "fd", "100100"], "fmts": ["S", "D"], "display": ["fd", "fs"]},
    "dadd": {"format": ["000000", "rs", "rt", "rd", "00000101100"], "display": ["rd", "rs", "rt"]},
    "daddi": {"format": ["011000", "rs", "rt", "int16"], "display": ["rt", "rs", "int16"]},
    "daddiu": {"format": ["011001", "rs", "rt", "uint16"], "display": ["rt", "rs", "uint16"]},
    "daddu": {"format": ["000000", "rs", "rt", "rd", "00000101101"], "display": ["rd", "rs", "rt"]},
    "ddiv": {"format": ["000000", "rs", "rt", "0000000000011110"], "display": ["rs", "rt"]},
    "ddivu": {"format": ["000000", "rs", "rt", "0000000000011111"], "display": ["rs", "rt"]},
    "div": {"format": ["000000", "rs", "rt", "0000000000011010"], "display": ["rs", "rt"]},
    "div.fmt": {"format": ["010001", "fmt", "ft", "fs", "fd", "000011"], "fmts": ["S", "D"], "display": ["fd", "fs", "ft"]},
    "divu": {"format": ["000000", "rs", "rt", "0000000000011011"], "display": ["rs", "rt"]},
    "dmfc1": {"format": ["010001", "00001", "rt", "fs", "00000000000"], "display": ["rt", "fs"]},
    "dmult": {"format": ["000000", "rs", "rt", "0000000000011100"], "display": ["rs", "rt"]},
    "dmultu": {"format": ["000000", "rs", "rt", "0000000000011101"], "display": ["rs", "rt"]},
    "dmtc1": {"format": ["010001", "00101", "rt", "fs", "00000000000"], "display": ["rt", "fs"]},
    "dsll": {"format": ["00000000000", "rt", "rd", "uint5", "111000"], "display": ["rd", "rt", "uint5"]},
    "dsll32": {"format": ["00000000000", "rt", "rd", "uint5", "111100"], "display": ["rd", "rt", "uint5"]},
    "dsllv": {"format": ["000000", "rs", "rt", "rd", "00000010100"], "display": ["rd", "rt", "rs"]},
    "dsra": {"format": ["00000000000", "rt", "rd", "uint5", "111011"], "display": ["rd", "rt", "uint5"]},
    "dsra32": {"format": ["00000000000", "rt", "rd", "uint5", "111111"], "display": ["rd", "rt", "uint5"]},
    "dsrav": {"format": ["000000", "rs", "rt", "rd", "00000010111"], "display": ["rd", "rt", "rs"]},
    "dsrl": {"format": ["00000000000", "rt", "rd", "uint5", "111010"], "display": ["rd", "rt", "uint5"]},
    "dsrl32": {"format": ["00000000000", "rt", "rd", "uint5", "111110"], "display": ["rd", "rt", "uint5"]},
    "dsrlv": {"format": ["000000", "rs", "rt", "rd", "00000010110"], "display": ["rd", "rt", "rs"]},
    "dsub": {"format": ["000000", "rs", "rt", "rd", "00000101110"], "display": ["rd", "rs", "rt"]},
    "dsubu": {"format": ["000000", "rs", "rt", "rd", "00000101111"], "display": ["rd", "rs", "rt"]},
    "floor.l.fmt": {"format": ["010001", "fmt", "00000", "fs", "fd", "001011"], "fmts": ["S", "D"], "display": ["fd", "fs"]},
    "floor.w.fmt": {"format": ["010001", "fmt", "00000", "fs", "fd", "001111"], "fmts": ["S", "D"], "display": ["fd", "fs"]},
    "j": {"format": ["000010", "uint26shift2"], "display": ["uint26shift2"]},
    "jal": {"format": ["000011", "uint26shift2"], "display": ["uint26shift2"]},
    "jalr": {"format": ["000000", "rs", "00000", ["rd", "11111"], "00000", "001001"], "display": ["rd?", "rs"]},
    "jr": {"format": ["000000", "rs", "000000000000000", "001000"], "display": ["rs"]},
    "lb": {"format": ["100000", "rs", "rt", "int16"], "display": ["rt", "int16", "(", "rs", ")"]},
    "lbu": {"format": ["100100", "rs", "rt", "uint16"], "display": ["rt", "uint16", "(", "rs", ")"]},
    "ld": {"format": ["110111", "rs", "rt", "int16"], "display": ["rt", "int16", "(", "rs", ")"]},
    "ldc1": {"format": ["110101", "rs", "ft", "int16"], "display": ["ft", "int16", "(", "rs", ")"]},
    "ldc2": {"format": ["110110", "rs", "rt", "int16"], "display": ["rt", "int16", "(", "rs", ")"]},
    "ldl": {"format": ["011010", "rs", "rt", "int16"], "display": ["rt", "int16", "(", "rs", ")"]},
    "ldr": {"format": ["011011", "rs", "rt", "int16"], "display": ["rt", "int16", "(", "rs", ")"]},
    "ldxc1": {"format": ["010011", "rs", "rt", "00000", "fd", "000001"], "display": ["fd", "rt", "(", "rs", ")"]},
    "lh": {"format": ["100001", "rs", "rt", "int16"], "display": ["rt", "int16", "(", "rs", ")"]},
    "lhu": {"format": ["100101", "rs", "rt", "int16"], "display": ["rt", "int16", "(", "rs", ")"]},
    "ll": {"format": ["110000", "rs", "rt", "int16"], "display": ["rt", "int16", "(", "rs", ")"]},
    "lld": {"format": ["110100", "rs", "rt", "int16"], "display": ["rt", "int16", "(", "rs", ")"]},
    "lui": {"format": ["001111", "00000", "rt", "uint16"], "display": ["rt", "uint16"]},
    "lw": {"format": ["100011", "rs", "rt", "int16"], "display": ["rt", "int16", "(", "rs", ")"]},
    "lwc1": {"format": ["110001", "rs", "ft", "int16"], "display": ["ft", "int16", "(", "rs", ")"]},
    "lwc2": {"format": ["110010", "rs", "rt", "int16"], "display": ["rt", "int16", "(", "rs", ")"]},
    "lwc3": {"format": ["110011", "rs", "rt", "int16"], "display": ["rt", "int16", "(", "rs", ")"]},
    "lwl": {"format": ["100010", "rs", "rt", "int16"], "display": ["rt", "int16", "(", "rs", ")"]},
    "lwr": {"format": ["100110", "rs", "rt", "int16"], "display": ["rt", "int16", "(", "rs", ")"]},
    "lwu": {"format": ["100111", "rs", "rt", "int16"], "display": ["rt", "int16", "(", "rs", ")"]},
    "lwxc1": {"format": ["010011", "rs", "rt", "00000", "fd", "000000"], "display": ["fd", "rt", "(", "rs", ")"]},
    "madd.fmt": {"format": ["010011", "fr", "ft", "fs", "fd", "100", "fmt3"], "fmts": ["S", "D"], "display": ["fd", "fr", "fs", "ft"]},
    "mfc1": {"format": ["010001", "00000", "rt", "fs", "00000000000"], "display": ["rt", "fs"]},
    "mfhi": {"format": ["000000", "0000000000", "rd", "00000", "010000"], "display": ["rd"]},
    "mflo": {"format": ["000000", "0000000000", "rd", "00000", "010010"], "display": ["rd"]},
    "mov.fmt": {"format": ["010001", "fmt", "00000", "fs", "fd", "000110"], "fmts": ["S", "D"], "display": ["fd", "fs"]},
    "movf": {"format": ["000000", "rs", "cc", "00", "rd", "00000", "000001"], "display": ["rd", "rs", "cc"]},
    "movf.fmt": {"format": ["010001", "fmt", "cc", "00", "fs", "fd", "010001"], "fmts": ["S", "D"], "display": ["fd", "fs", "cc"]},
    "movn": {"format": ["000000", "rs", "rt", "rd", "00000", "001011"], "display": ["rd", "rs", "rt"]},
    "movn.fmt": {"format": ["010001", "fmt", "rt", "fs", "fd", "010011"], "fmts": ["S", "D"], "display": ["fd", "fs", "rt"]},
    "movt": {"format": ["000000", "rs", "cc", "01", "rd", "00000", "000001"], "display": ["rd", "rs", "cc"]},
    "movt.fmt": {"format": ["010001", "fmt", "cc", "01", "fs", "fd", "010001"], "fmts": ["S", "D"], "display": ["fd", "fs", "cc"]},
    "movz": {"format": ["000000", "rs", "rt", "rd", "00000", "001010"], "display": ["rd", "rs", "rt"]},
    "movz.fmt": {"format": ["010001", "fmt", "rt", "fs", "fd", "010010"], "fmts": ["S", "D"], "display": ["fd", "fs", "rt"]},
    "msub.fmt": {"format": ["010011", "fr", "ft", "fs", "fd", "101", "fmt3"], "fmts": ["S", "D"], "display": ["fd", "fr", "fs", "ft"]},
    "mtc1": {"format": ["010001", "00100", "rt", "fs", "00000000000"], "display": ["rt", "fs"]},
    "mthi": {"format": ["000000", "rs", "000000000000000", "010001"], "display": ["rs"]},
    "mtlo": {"format": ["000000", "rs", "000000000000000", "010011"], "display": ["rs"]},
    "mul.fmt": {"format": ["010001", "fmt", "ft", "fs", "fd", "000010"], "fmts": ["S", "D"], "display": ["fd", "fs", "ft"]},
    "mult": {"format": ["000000", "rs", "rt", "0000000000", "011000"], "display": ["rs", "rt"]},
    "multu": {"format": ["000000", "rs", "rt", "0000000000", "011001"], "display": ["rs", "rt"]},
    "neg.fmt": {"format": ["010001", "fmt", "00000", "fs", "fd", "000111"], "fmts": ["S", "D"], "display": ["fd", "fs"]},
    "nmadd.fmt": {"format": ["010011", "fr", "ft", "fs", "fd", "110", "fmt3"], "fmts": ["S", "D"], "display": ["fd", "fr", "fs", "ft"]},
    "nmsub.fmt": {"format": ["010011", "fr", "ft", "fs", "fd", "111", "fmt3"], "fmts": ["S", "D"], "display": ["fd", "fr", "fs", "ft"]},
    "nop": {"format": ["00000000000000000000000000000000"], "display": []},
    "nor": {"format": ["000000", "rs", "rt", "rd", "00000", "100111"], "display": ["rd", "rs", "rt"]},
    "or": {"format": ["000000", "rs", "rt", "rd", "00000", "100101"], "display": ["rd", "rs", "rt"]},
    "ori": {"format": ["001101", "rs", "rt", "uint16"], "display": ["rt", "rs", "uint16"]},
    "pref": {"format": ["110011", "rs", "uint5", "int16"], "display": ["uint5", "int16", "(", "rs", ")"]},
    "prefx": {"format": ["010011", "rs", "rt", "uint5", "00000", "001111"], "display": ["uint5", "rt", "(", "rs", ")"]},
    "recip.fmt": {"format": ["010001", "fmt", "00000", "fs", "fd", "010101"], "fmts": ["S", "D"], "display": ["fd", "fs"]},
    "round.l.fmt": {"format": ["010001", "fmt", "00000", "fs", "fd", "001000"], "fmts": ["S", "D"], "display": ["fd", "fs"]},
    "round.w.fmt": {"format": ["010001", "fmt", "00000", "fs", "fd", "001100"], "fmts": ["S", "D"], "display": ["fd", "fs"]},
    "rsqrt.fmt": {"format": ["010001", "fmt", "00000", "fs", "fd", "010110"], "fmts": ["S", "D"], "display": ["fd", "fs"]},
    "sb": {"format": ["101000", "rs", "rt", "int16"], "display": ["rt", "int16", "(", "rs", ")"]},
    "sc": {"format": ["111000", "rs", "rt", "int16"], "display": ["rt", "int16", "(", "rs", ")"]},
    "scd": {"format": ["111100", "rs", "rt", "int16"], "display": ["rt", "int16", "(", "rs", ")"]},
    "sd": {"format": ["111111", "rs", "rt", "int16"], "display": ["rt", "int16", "(", "rs", ")"]},
    "sdc1": {"format": ["111101", "rs", "ft", "int16"], "display": ["ft", "int16", "(", "rs", ")"]},
    "sdc2": {"format": ["111110", "rs", "rt", "int16"], "display": ["rt", "int16", "(", "rs", ")"]},
    "sdl": {"format": ["101100", "rs", "rt", "int16"], "display": ["rt", "int16", "(", "rs", ")"]},
    "sdr": {"format": ["101101", "rs", "rt", "int16"], "display": ["rt", "int16", "(", "rs", ")"]},
    "sdxc1": {"format": ["010011", "rs", "uint5", "fs", "00000", "001001"], "display": ["fs", "uint5", "(", "rs", ")"]},
    "sh": {"format": ["101001", "rs", "rt", "int16"], "display": ["rt", "int16", "(", "rs", ")"]},
    "sll": {"format": ["000000", "00000", "rt", "rd", "uint5", "000000"], "display": ["rd", "rt", "uint5"]},
    "sllv": {"format": ["000000", "rs", "rt", "rd", "00000", "000100"], "display": ["rd", "rt", "rs"]},
    "slt": {"format": ["000000", "rs", "rt", "rd", "00000", "101010"], "display": ["rd", "rs", "rt"]},
    "slti": {"format": ["001010", "rs", "rt", "int16"], "display": ["rt", "rs", "int16"]},
    "sltiu": {"format": ["001011", "rs", "rt", "uint16"], "display": ["rt", "rs", "uint16"]},
    "sltu": {"format": ["000000", "rs", "rt", "rd", "00000", "101011"], "display": ["rd", "rs", "rt"]},
    "sqrt.fmt": {"format": ["010001", "fmt", "00000", "fs", "fd", "000100"], "fmts": ["S", "D"], "display": ["fd", "fs"]},
    "sra": {"format": ["000000", "00000", "rt", "rd", "uint5", "000011"], "display": ["rd", "rt", "uint5"]},
    "srav": {"format": ["000000", "rs", "rt", "rd", "00000", "000111"], "display": ["rd", "rt", "rs"]},
    "srl": {"format": ["000000", "00000", "rt", "rd", "uint5", "000010"], "display": ["rd", "rt", "uint5"]},
    "srlv": {"format": ["000000", "rs", "rt", "rd", "00000", "000110"], "display": ["rd", "rt", "rs"]},
    "sub": {"format": ["000000", "rs", "rt", "rd", "00000", "100010"], "display": ["rd", "rs", "rt"]},
    "sub.fmt": {"format": ["010001", "fmt", "ft", "fs", "fd", "000001"], "fmts": ["S", "D"], "display": ["fd", "fs", "ft"]},
    "subu": {"format": ["000000", "rs", "rt", "rd", "00000", "100011"], "display": ["rd", "rs", "rt"]},
    "sw": {"format": ["101011", "rs", "rt", "int16"], "display": ["rt", "int16", "(", "rs", ")"]},
    "swc1": {"format": ["111001", "rs", "ft", "int16"], "display": ["ft", "int16", "(", "rs", ")"]},
    "swc2": {"format": ["111010", "rs", "rt", "int16"], "display": ["rt", "int16", "(", "rs", ")"]},
    "swc3": {"format": ["111011", "rs", "rt", "int16"], "display": ["rt", "int16", "(", "rs", ")"]},
    "swl": {"format": ["101010", "rs", "rt", "int16"], "display": ["rt", "int16", "(", "rs", ")"]},
    "swr": {"format": ["101110", "rs", "rt", "int16"], "display": ["rt", "int16", "(", "rs", ")"]},
    "swxc1": {"format": ["010011", "rs", "uint5", "fs", "00000", "001000"], "display": ["fs", "uint5", "(", "rs", ")"]},
    "sync": {"format": ["000000", "000000000000000", "00000", "001111"], "display": []},
    "syscall": {"format": ["000000", ["uint20", "00000000000000000000"], "001100"], "display": []},
    "teq": {"format": ["000000", "rs", "rt", "uint10", "110100"], "display": ["rs", "rt"]},
    "teqi": {"format": ["000001", "rs", "01100", "int16"], "display": ["rs", "int16"]},
    "tge": {"format": ["000000", "rs", "rt", "uint10", "110000"], "display": ["rs", "rt"]},
    "tgei": {"format": ["000001", "rs", "01000", "int16"], "display": ["rs", "int16"]},
    "tgeiu": {"format": ["000001", "rs", "01001", "uint16"], "display": ["rs", "uint16"]},
    "tgeu": {"format": ["000000", "rs", "rt", "uint10", "110001"], "display": ["rs", "rt"]},
    "tlt": {"format": ["000000", "rs", "rt", "uint10", "110010"], "display": ["rs", "rt"]},
    "tlti": {"format": ["000001", "rs", "01010", "int16"], "display": ["rs", "int16"]},
    "tltiu": {"format": ["000001", "rs", "01011", "uint16"], "display": ["rs", "uint16"]},
    "tltu": {"format": ["000000", "rs", "rt", "uint10", "110011"], "display": ["rs", "rt"]},
    "tne": {"format": ["000000", "rs", "rt", "uint10", "110110"], "display": ["rs", "rt"]},
    "tnei": {"format": ["000001", "rs", "01110", "int16"], "display": ["rs", "int16"]},
    "trunc.l.fmt": {"format": ["010001", "fmt", "00000", "fs", "fd", "001001"], "fmts": ["S", "D"], "display": ["fd", "fs"]},
    "trunc.w.fmt": {"format": ["010001", "fmt", "00000", "fs", "fd", "001101"], "fmts": ["S", "D"], "display": ["fd", "fs"]},
    "xor": {"format": ["000000", "rs", "rt", "rd", "00000", "100110"], "display": ["rd", "rs", "rt"]},
    "xori": {"format": ["001110", "rs", "rt", "uint16"], "display": ["rt", "rs", "uint16"]},
}

_compiled_formats = [(name, _compile_format(details)) for name, details in opcode_details.items()]
