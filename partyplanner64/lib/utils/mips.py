"""MIPS asm helper library (port of utils/MIPS.ts)."""

from ..mips import parse
from ..mips._js import js_str, to_int32


class _RegTable(dict):
    """A dict of register numbers that also allows REG.A0."""

    def __getattr__(self, name):
        try:
            return self[name]
        except KeyError:
            raise AttributeError(name) from None


REG = _RegTable(
    R0=0, AT=1, V0=2, V1=3, A0=4, A1=5, A2=6, A3=7,
    T0=8, T1=9, T2=10, T3=11, T4=12, T5=13, T6=14, T7=15,
    S0=16, S1=17, S2=18, S3=19, S4=20, S5=21, S6=22, S7=23,
    T8=24, T9=25, K0=26, K1=27, GP=28, SP=29, S8=30, RA=31,
)


def _i(value):
    # JavaScript bit operations give signed 32-bit results.
    return to_int32(value)


def _addiu(dst, reg, imm):
    return _i(0x24000000 | (reg << 21) | (dst << 16) | (_i(imm) & 0xFFFF))


def _addu(dst, reg1, reg2):
    return _i(0x00000021 | (reg1 << 21) | (reg2 << 16) | (dst << 11))


def _beq(r1, r2, offset):
    return _i(0x10000000 | (r1 << 21) | (r2 << 16) | ((_i(offset) >> 2) & 0xFFFF))


def _bne(r1, r2, offset):
    return _i(0x14000000 | (r1 << 21) | (r2 << 16) | ((_i(offset) >> 2) & 0xFFFF))


def _bgtz(reg, offset):
    return _i(0x1C000000 | (reg << 21) | ((_i(offset) >> 2) & 0xFFFF))


def _blez(reg, offset):
    return _i(0x18000000 | (reg << 21) | ((_i(offset) >> 2) & 0xFFFF))


def _j(addr):
    return _i(0x08000000 | ((_i(addr) & 0xFFFFFFFF) >> 2))


def _jr(reg):
    return _i(0x00000008 | (reg << 21))


def _jal(addr):
    return _i(0x0C000000 | ((_i(addr) & 0xFFFFFFFF) >> 2))


def _lb(dst, reg, offset):
    """dst = MEM[reg + offset]"""
    return _i(0x80000000 | (reg << 21) | (dst << 16) | (_i(offset) & 0xFFFF))


def _sb(src, dst, offset):
    """MEM[dst + offset] = (0xff & src);"""
    return _i(0xA0000000 | (dst << 21) | (src << 16) | (_i(offset) & 0xFFFF))


def _lh(dst, reg, offset):
    """dst = MEM[reg + offset]"""
    return _i(0x84000000 | (reg << 21) | (dst << 16) | (_i(offset) & 0xFFFF))


def _sh(src, dst, offset):
    """MEM[dst + offset] = (0xffff & src);"""
    return _i(0xA4000000 | (dst << 21) | (src << 16) | (_i(offset) & 0xFFFF))


def _lui(dst, imm):
    return _i(0x3C000000 | (dst << 16) | (_i(imm) & 0xFFFF))


def _lw(dst, reg, offset):
    """dst = MEM[reg + offset]"""
    return _i(0x8C000000 | (reg << 21) | (dst << 16) | (_i(offset) & 0xFFFF))


def _sw(src, dst, offset):
    """MEM[reg + offset]"""
    return _i(0xAC000000 | (dst << 21) | (src << 16) | (_i(offset) & 0xFFFF))


def _ori(r1, r2, imm):
    """r1 = r2 | imm"""
    return _i(0x34000000 | (r1 << 21) | (r2 << 16) | (_i(imm) & 0xFFFF))


_methods = {
    "addiu": _addiu, "addu": _addu, "beq": _beq, "bne": _bne, "bgtz": _bgtz, "blez": _blez,
    "j": _j, "jr": _jr, "jal": _jal, "lb": _lb, "sb": _sb, "lh": _lh, "sh": _sh, "lui": _lui,
    "lw": _lw, "sw": _sw, "ori": _ori,
}


def make_inst(inst=None, *extras):
    """Encodes a few instructions: make_inst("ADDIU", REG.SP, REG.SP, -0x18).

    Like the original, the result is a signed 32-bit number.
    """
    if inst is None:
        return None
    method = _methods.get(inst.lower())
    if method is not None:
        # Missing arguments are undefined in JavaScript, which bit operations treat as 0.
        arity = method.__code__.co_argcount
        args = [_i(a) for a in extras[:arity]]
        args += [0] * (arity - len(args))
        return method(*args)
    raise ValueError("MIPS.makeInst: Unrecognized instruction %s" % inst)


def get_jal_addr(word):
    if (word & 0x0C000000) != 0x0C000000:
        raise ValueError("MIPS.getJALAddr: %s is not a JAL instruction." % format(word, "x"))
    return (word & 0x03FFFFFF) << 2


def get_reg_set_upper_and_lower(address):
    lower = address & 0x0000FFFF
    upper = (address & 0xFFFFFFFF) >> 16
    if lower & 0x8000:
        upper += 1
    return [upper, lower]


def get_reg_set_address(upper, lower):
    upper = upper & 0x0000FFFF
    lower = lower & 0x0000FFFF
    if lower & 0x8000:
        upper -= 1
    return ((upper << 16) | lower) & 0x7FFFFFFF


def get_function_length(data_view, start_offset):
    offset = start_offset + 4
    while data_view.get_uint32(offset) != 0x03E00008 and offset < start_offset + 0x2000:
        offset += 4

    if data_view.get_uint32(offset) == 0x03E00008:
        offset += 8
    else:
        return None

    return offset - start_offset


def _jal_inst(jal_addr):
    return parse("JAL " + ("undefined" if jal_addr is None else js_str(jal_addr)))


def find_calls(data_view, jal_addr):
    """Finds JALs to a given address contained in a DataView.

    Returns a list of offsets of the JALs.
    """
    jal_inst = _jal_inst(jal_addr)
    calls = []
    for i in range(0, data_view.byte_length, 4):
        if data_view.get_uint32(i) == jal_inst:
            calls.append(i)
    return calls


def find_calls_in_function(data_view, start_offset, jal_addr):
    """Finds JALs to a given address within the given function.

    Returns a list of offsets of the JALs.
    """
    jal_inst = _jal_inst(jal_addr)
    calls = []
    i = start_offset
    while i < data_view.byte_length:
        inst = data_view.get_uint32(i)
        if inst == 0x03E00008:
            break
        if inst == jal_inst:
            calls.append(i)
        i += 4
    return calls
