"""Code that picks the background shown each turn (additionalbg.ts)."""

from ..types import EventCodeLanguage, Game, get_game_name
from ..utils.debug import log
from .prep_asm import prep_generic_asm, scope_labels_static_by_default
from .prep_c import prep_generic_c

# Default assembly code used for background selection.
default_additional_bg_asm = """; Customize the background used each turn!
; This function runs at the start of each turn.
; The default background is available as DEFAULT_BG.
; Additional backgrounds are available as ADDITIONAL_BG_#,
; e.g. ADDITIONAL_BG_1 for the first added background.
ADDIU SP SP -4
SW RA 0(SP)

; Return the background index in V0.
LI V0 DEFAULT_BG

LW RA 0(SP)
JR RA
ADDIU SP SP 4"""

default_additional_bg_c = """// Customize the background used each turn!
// This function runs at the start of each turn.
// The default background is available as DEFAULT_BG.
// Additional backgrounds are available as ADDITIONAL_BG_#,
// e.g. ADDITIONAL_BG_1 for the first added background.

int PickBackground() {
    return DEFAULT_BG;
}"""


def _romhandler():
    from ..romhandler import romhandler
    return romhandler


def _compile(code):
    from ..utils.c_compiler import compile
    return compile(code)


def _assemble(asm):
    from ..mips import assemble
    return assemble(asm)


def get_default_additional_bg_code(language):
    if language == EventCodeLanguage.C:
        return default_additional_bg_c
    if language == EventCodeLanguage.MIPS:
        return default_additional_bg_asm
    raise ValueError(f"Unrecognized event code language {language}")


def _make_fake_bg_syms(board):
    if not board.get("additionalbg"):
        return []
    return [i + 1 for i in range(len(board["additionalbg"]))]


def test_additional_bg_code_all_games(code, language, board):
    """Test-compiles the code for every game version of the board's game.
    Returns a list of failure messages (empty when one version works)."""
    possible_game_versions = _get_game_versions_to_test_compile(board)

    failures = []
    for game in possible_game_versions:
        failures = failures + test_additional_bg_code_with_game(code, language, board, game)

    # If it doesn't fail all, that means it's OK for some game and that's good enough.
    if len(failures) == len(possible_game_versions):
        failures.insert(0, "All possible target game versions failed to compile/assemble.")
    else:
        failures = []

    return failures


def test_additional_bg_code_with_game(code, language, board, game):
    failures = []

    bg_indices = _make_fake_bg_syms(board)

    if language == EventCodeLanguage.C:
        c_with_defines = prep_additional_bg_c(code, 0, bg_indices)
        try:
            prepped_c = prep_generic_c(c_with_defines, game)
            log(prepped_c)
            asm = _compile(prepped_c)
            log(asm)
            prepped_asm = prep_generic_asm(asm, 0x80000000, game)
            _assemble(prepped_asm)
        except Exception as e:
            failures.append(
                f"Failed test compile/assemble for {get_game_name(game)}:\nError: {e}\n")
    else:
        asm_with_bg_syms = prep_additional_bg_asm(code, 0, bg_indices)
        try:
            prepped_asm = prep_generic_asm(asm_with_bg_syms, 0x80000000, game)
            log(prepped_asm)
            _assemble(prepped_asm)
        except Exception as e:
            failures.append(f"Failed test assembly for {get_game_name(game)}:\nError: {e}\n")

    return failures


def _get_game_versions_to_test_compile(board):
    game = board.get("game")
    if game == 1:
        return [Game.MP1_USA, Game.MP1_PAL, Game.MP1_JPN]
    if game == 2:
        return [Game.MP2_USA, Game.MP2_PAL, Game.MP2_JPN]
    if game == 3:
        return [Game.MP3_USA, Game.MP3_PAL, Game.MP3_JPN]
    return None


def get_additional_bg_asm_for_overlay(board, bg_dir, additional_bg_indices):
    from ..boards import get_additional_background_code

    bg_code = get_additional_background_code(board)
    if not bg_code:
        return prep_additional_bg_asm(default_additional_bg_asm, bg_dir, additional_bg_indices)

    language = bg_code["language"]
    if language == EventCodeLanguage.C:
        c_with_defines = prep_additional_bg_c(bg_code["code"], bg_dir, additional_bg_indices)
        game = _romhandler().get_rom_game()
        prepped_c = prep_generic_c(c_with_defines, game)
        asm = _compile(prepped_c)
        return scope_labels_static_by_default(
            f"""
        .beginfile ; Scopes static labels
        {asm}
        .align 4
        .endfile
      """,
            True,
        )
    if language == EventCodeLanguage.MIPS:
        return prep_additional_bg_asm(bg_code["code"], bg_dir, additional_bg_indices)

    raise ValueError(f"Unrecognized event code language {language}")


def prep_additional_bg_asm(asm, default_bg_index, additional_bg_indices=None):
    """Surrounds the additional bg code with the necessary bg symbols."""
    syms = "\n".join(make_bg_symbol_labels(default_bg_index, additional_bg_indices))
    return scope_labels_static_by_default(
        f"""
    .beginfile ; Scopes static labels
    __PP64_INTERNAL_ADDITIONAL_BG_CHOICE:
    {syms}
    {asm}
    .align 4
    .endfile
  """,
        True,
    )


def make_bg_symbol_labels(default_bg_index, additional_bg_indices=None):
    syms = [f".definelabel DEFAULT_BG,{default_bg_index}"]

    if additional_bg_indices:
        for i, bg_index in enumerate(additional_bg_indices):
            syms.append(f".definelabel ADDITIONAL_BG_{i + 1},{bg_index}")

    return syms


def prep_additional_bg_c(code, default_bg_index, additional_bg_indices=None):
    """Surrounds the additional bg C code with the necessary symbols."""
    defines = "\n".join(make_additional_bg_defines(default_bg_index, additional_bg_indices))
    return f"""
#define PickBackground __PP64_INTERNAL_ADDITIONAL_BG_CHOICE
{defines}
{code}
  """


def make_additional_bg_defines(default_bg_index, additional_bg_indices=None):
    """Creates defines for additional bg symbols."""
    syms = [f"#define DEFAULT_BG {default_bg_index}"]

    if additional_bg_indices:
        for i, bg_index in enumerate(additional_bg_indices):
            syms.append(f"#define ADDITIONAL_BG_{i + 1} {bg_index}")

    return syms


def get_board_additional_bg_hvq_indices(board):
    """Assumes a call before the HVQ additional bgs have been written."""
    if board and board.get("additionalbg") is not None:
        result = []
        for i, _bg in enumerate(board["additionalbg"]):
            romhandler = _romhandler()
            if romhandler.rom_is_loaded():
                hvqfs = romhandler.get_rom().get_hvqfs()
                result.append(hvqfs.get_directory_count() + i)
            else:
                result.append(i)  # Must be a test compile.
        return result
    return None
