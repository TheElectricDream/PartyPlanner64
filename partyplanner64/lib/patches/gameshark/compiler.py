"""Produces MIPS code from parsed Gameshark codes (port of patches/gameshark/compiler.ts)."""

from ...mips import parse
from ...mips._js import js_str
from ...utils.dataview import DataView
from ...utils.debug import log


def _num(value):
    return "NaN" if value is None else js_str(value)


class Compiler:
    """Compiler is a gross exaggeration.

    This produces the MIPS ASM equivalent of parsed gameshark codes.
    """

    def __init__(self):
        # Use the stack and saved registers instead of K0/K1?
        self.REG1 = "A3"
        self.REG2 = "AT"

    def compile(self, codes):
        """Returns a bytearray of MIPS instructions for a Gameshark hook, or None."""
        insts = []
        for code in codes:
            result = None
            method = getattr(self, "compile" + code["opcode"], None)
            if callable(method):
                result = method(code)

            if not result:
                log("Error compiling code", code)
                return None

            insts.extend(result if isinstance(result, list) else [result])

        # Somewhat awkward to ensure big endianness in output.
        out_buffer = bytearray(len(insts) * 4)
        out_view = DataView(out_buffer)
        for i, inst in enumerate(insts):
            out_view.set_uint32(i * 4, inst)
        return out_buffer

    # http://gamehacking.org/wiki/Hacking_N64#Code_Handler_Hacks

    def _load_addr(self, code):
        return ("LUI %s %s\n      ORI %s %s %s\n"
                % (self.REG1, js_str(self.get_addr_upper(code["addr"])), self.REG1, self.REG1,
                   js_str(self.get_addr_lower(code["addr"]))))

    def compileWRITE8(self, code):
        return parse("\n      " + self._load_addr(code)
                     + "      ADDIU %s R0 %s\n      SB %s 0(%s)\n    "
                     % (self.REG2, _num(code["value"]), self.REG2, self.REG1))

    def compileWRITE16(self, code):
        return parse("\n      " + self._load_addr(code)
                     + "      ADDIU %s R0 %s\n      SH %s 0(%s)\n    "
                     % (self.REG2, _num(code["value"]), self.REG2, self.REG1))

    def compileIF8(self, code):
        return parse("\n      " + self._load_addr(code)
                     + "      LB %s 0(%s)\n      ADDIU %s R0 %s\n      BNE %s %s 4\n    "
                     % (self.REG1, self.REG1, self.REG2, _num(code["value"]), self.REG1, self.REG2))

    def compileIF16(self, code):
        return parse("\n      " + self._load_addr(code)
                     + "      LH %s 0(%s)\n      ADDIU %s R0 %s\n      BNE %s %s 4\n    "
                     % (self.REG1, self.REG1, self.REG2, _num(code["value"]), self.REG1, self.REG2))

    def compileIFNOT8(self, code):
        return parse("\n      " + self._load_addr(code)
                     + "      LB %s 0(%s)\n      ADDIU %s R0 %s\n      BEQ %s %s 4\n    "
                     % (self.REG1, self.REG1, self.REG2, _num(code["value"]), self.REG1, self.REG2))

    def compileIFNOT16(self, code):
        return parse("\n      " + self._load_addr(code)
                     + "      LH %s 0(%s)\n      ADDIU %s R0 %s\n      BEQ %s %s 4\n    "
                     % (self.REG1, self.REG1, self.REG2, _num(code["value"]), self.REG1, self.REG2))

    # snake_case aliases (by the naming rule)
    compile_write8 = compileWRITE8
    compile_write16 = compileWRITE16
    compile_if8 = compileIF8
    compile_if16 = compileIF16
    compile_ifnot8 = compileIFNOT8
    compile_ifnot16 = compileIFNOT16

    def get_addr_upper(self, addr):
        return (addr & 0xFFFF0000) >> 16

    def get_addr_lower(self, addr):
        return addr & 0x0000FFFF
