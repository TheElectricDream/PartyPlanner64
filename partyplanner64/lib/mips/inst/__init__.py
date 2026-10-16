"""Python port of mips-inst v3 (https://github.com/wnayes/mips-inst).

mips-inst parses and prints MIPS instructions. It is by Will Nayes (the
author of PartyPlanner64) and MIT-licensed: see LICENSE-mips-inst.txt in
the parent package.
"""

from .parse import parse
from .print import print

__all__ = ["parse", "print"]
