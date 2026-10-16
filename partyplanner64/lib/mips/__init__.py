"""MIPS instruction parsing/printing and assembly.

Python ports of two MIT-licensed npm packages by Will Nayes, the author of
PartyPlanner64 (their licences are LICENSE-mips-inst.txt and
LICENSE-mips-assembler.txt next to this file):

- mips-inst v3 (https://github.com/wnayes/mips-inst): `parse` and `print`.
- mips-assembler v2 (https://github.com/wnayes/mips-assembler): `assemble`.

`print` shadows the builtin only inside this namespace; `print_inst` is the
same function.
"""

from .assembler import AssemblerError, assemble
from .inst import parse, print

print_inst = print

__all__ = ["parse", "print", "print_inst", "assemble", "AssemblerError"]
