"""Register, format and condition names (port of mips-inst regs.js)."""

regs = {
    "r0": 0, "zero": 0, "at": 1, "v0": 2, "v1": 3, "a0": 4, "a1": 5, "a2": 6, "a3": 7,
    "t0": 8, "t1": 9, "t2": 10, "t3": 11, "t4": 12, "t5": 13, "t6": 14, "t7": 15,
    "s0": 16, "s1": 17, "s2": 18, "s3": 19, "s4": 20, "s5": 21, "s6": 22, "s7": 23,
    "t8": 24, "t9": 25, "k0": 26, "k1": 27, "gp": 28, "sp": 29, "fp": 30, "ra": 31,
}

_reg_names = {}
for _name, _bits in regs.items():
    _reg_names.setdefault(_bits, _name)


def get_reg_bits(reg):
    if not reg:
        return None
    return regs.get(reg.lower())


def get_reg_name(bits):
    return _reg_names.get(bits, "")


def get_float_reg_name(bits):
    if not isinstance(bits, (int, float)) or isinstance(bits, bool):
        raise ValueError("getFloatRegName encountered non-number")
    from .._js import num_to_string
    return "F" + num_to_string(bits)


fmts = {"S": 16, "D": 17, "W": 20, "L": 21}


def get_fmt_bits(fmt_str):
    return fmts.get(fmt_str.upper())


def get_fmt_name(bits):
    for name, value in fmts.items():
        if value == bits:
            return name
    return ""


fmt3s = {"S": 0, "D": 1, "W": 4, "L": 5}


def get_fmt3_bits(fmt_str):
    return fmt3s.get(fmt_str.upper())


def get_fmt3_name(bits):
    for name, value in fmt3s.items():
        if value == bits:
            return name
    return ""


def is_fmt_string(fmt_str):
    return fmt_str.upper() in fmts or fmt_str.upper() in fmt3s


conds = {
    "F": 0, "UN": 1, "EQ": 2, "UEQ": 3, "OLT": 4, "ULT": 5, "OLE": 6, "ULE": 7,
    "SF": 8, "NGLE": 9, "SEQ": 10, "NGL": 11, "LT": 12, "NGE": 13, "LE": 14, "NGT": 15,
}


def get_cond_bits(cond_str):
    return conds.get(cond_str.upper())


def get_cond_name(bits):
    for name, value in conds.items():
        if value == bits:
            return name
    return ""


def is_cond_string(cond_str):
    return cond_str.upper() in conds
