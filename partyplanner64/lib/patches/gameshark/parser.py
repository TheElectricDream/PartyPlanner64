"""Parses Gameshark code text (port of patches/gameshark/parser.ts)."""

import re

from ...utils.debug import hexstr, log

Opcodes = {
    "WRITE8": 0x80,
    "WRITE16": 0x81,
    "IF8": 0xD0,
    "IF16": 0xD1,
    "IFNOT8": 0xD2,
    "IFNOT16": 0xD3,
}

_hex_prefix = re.compile(r"^[+-]?(?:0[xX])?([0-9A-Fa-f]+)")


def _parse_hex(s):
    """parseInt(s, 16); None for NaN."""
    m = _hex_prefix.match(s)
    if not m:
        return None
    value = int(m.group(1), 16)
    return -value if s.startswith("-") else value


class Parser:
    """Takes a string of gameshark codes and produces a list of dicts representing them.

    A code is {"opcode": str, "addr": int, "value": int} (ICode).
    """

    @staticmethod
    def parse(code_string):
        pieces = Parser.split_input(code_string)
        if not pieces:
            log("Gameshark code string was empty")
            return None

        if len(pieces) % 2:
            log("Gameshark code string was malformed")
            return None

        codes = []
        for i in range(0, len(pieces), 2):
            inst = _parse_hex(pieces[i])
            value = _parse_hex(pieces[i + 1])

            if not inst:
                log("Invalid code instruction: %s" % pieces[i])
                return None

            code = Parser.get_code(inst, value)
            if not code:
                log("Could not parse code: %s %s" % (hexstr(inst), "NaN" if value is None else hexstr(value)))
                return None

            codes.append(code)

        return codes

    @staticmethod
    def get_code(inst, value):
        opcode = Parser.get_opcode(inst)
        if opcode is None:
            return None

        addr = ((inst & 0x00FFFFFF) | 0x80000000)
        addr = addr - 0x100000000 if addr & 0x80000000 else addr  # (| gives a signed result.)

        if Parser.opcode_has8_bit_value(opcode):
            value = (value or 0) & 0x00FF

        return {"opcode": opcode, "addr": addr, "value": value}

    @staticmethod
    def get_opcode(inst):
        upper8 = (inst & 0xFF000000) >> 24
        if not upper8:
            return None
        for type_, bits in Opcodes.items():
            if bits == upper8:
                return type_
        return None

    @staticmethod
    def opcode_has8_bit_value(opcode):
        return opcode in ("WRITE8", "IF8", "IFNOT8")

    @staticmethod
    def split_input(code_string):
        if not code_string:
            return []
        return re.findall(r"\S+", code_string)

    @staticmethod
    def print_codes(codes):
        for code in codes:
            print("%s %s %s" % (code["opcode"], hexstr(code["addr"]), hexstr(code["value"])))
