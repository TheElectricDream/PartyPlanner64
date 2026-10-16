"""Python port of mips-assembler v2 (https://github.com/wnayes/mips-assembler).

An armips-like MIPS assembler: labels (global, @static, @@local),
directives (.org, .orga, .definelabel, equ, .align, .skip, .fill, .ascii,
.asciiz, .byte, .halfword, .word, .float, .if/.elseif/.else/.endif,
.include, .beginfile/.endfile), macros (li, move, beqz, bnez, bnezl) and
the functions hi(), lo(), abs() and org(). It is by Will Nayes (the author
of PartyPlanner64) and MIT-licensed: see LICENSE-mips-assembler.txt in the
parent package.
"""

from .assembler import assemble
from .state import AssemblerError

__all__ = ["assemble", "AssemblerError"]
