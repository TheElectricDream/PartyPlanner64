"""Code that picks the board music (getaudiochoice.ts)."""

from ..types import EventCodeLanguage, Game, get_game_name
from ..utils.debug import log
from .prep_asm import prep_generic_asm, scope_labels_static_by_default
from .prep_c import prep_generic_c

# Default assembly code used for audio selection.
default_get_audio_asm = """; Customize the background music used each turn!
; This function runs whenever the board music starts playing.
; Custom tracks you've added are available as MUSIC_TRACK_INDEX_#,
; e.g. MUSIC_TRACK_INDEX_1 for the first added custom song.
; (If you aren't using custom music, then only MUSIC_TRACK_INDEX_1
; exists and it is set to the in-game music index you chose.)
ADDIU SP SP -4
SW RA 0(SP)

; Return the audio index in V0.
LI V0 MUSIC_TRACK_INDEX_1

LW RA 0(SP)
JR RA
ADDIU SP SP 4"""

default_get_audio_c = """// Customize the background music used each turn!
// This function runs whenever the board music starts playing.
// Custom tracks you've added are available as MUSIC_TRACK_INDEX_#,
// e.g. MUSIC_TRACK_INDEX_1 for the first added custom song.
// (If you aren't using custom music, then only MUSIC_TRACK_INDEX_1
// exists and it is set to the in-game music index you chose.)

int PickAudioIndex() {
    return MUSIC_TRACK_INDEX_1;
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


def get_default_get_audio_code(language):
    if language == EventCodeLanguage.C:
        return default_get_audio_c
    if language == EventCodeLanguage.MIPS:
        return default_get_audio_asm
    raise ValueError(f"Unrecognized event code language {language}")


def test_get_audio_code_all_games(code, language, board):
    """Test-compiles the code for every game version of the board's game.
    Returns a list of failure messages (empty when one version works)."""
    possible_game_versions = _get_game_versions_to_test_compile(board)

    failures = []
    for game in possible_game_versions:
        failures = failures + test_get_audio_code_with_game(code, language, board, game)

    # If it doesn't fail all, that means it's OK for some game and that's good enough.
    if len(failures) == len(possible_game_versions):
        failures.insert(0, "All possible target game versions failed to compile/assemble.")
    else:
        failures = []

    return failures


def test_get_audio_code_with_game(code, language, board, game):
    failures = []

    fake_audio_indices = make_fake_get_audio_indices(board)

    if language == EventCodeLanguage.C:
        c_with_defines = prep_get_audio_c(code, fake_audio_indices)
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
        asm_with_syms = prep_get_audio_asm(code, fake_audio_indices)
        try:
            prepped_asm = prep_generic_asm(asm_with_syms, 0x80000000, game)
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


def get_audio_index_asm_for_overlay(board, audio_indices):
    from ..boards import get_audio_select_code

    audio_select_code = get_audio_select_code(board)
    if not audio_select_code:
        return prep_get_audio_asm(default_get_audio_asm, audio_indices)

    language = audio_select_code["language"]
    if language == EventCodeLanguage.C:
        c_with_defines = prep_get_audio_c(audio_select_code["code"], audio_indices)
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
        return prep_get_audio_asm(audio_select_code["code"], audio_indices)

    raise ValueError(f"Unrecognized event code language {language}")


def prep_get_audio_asm(asm, audio_indices):
    """Surrounds the audio index code with the necessary symbols."""
    syms = "\n".join(make_audio_symbol_labels(audio_indices))
    return scope_labels_static_by_default(
        f"""
    .beginfile ; Scopes static labels
    __PP64_INTERNAL_GET_BOARD_AUDIO_INDEX:
    {syms}
    {asm}
    .align 4
    .endfile
  """,
        True,
    )


def make_fake_get_audio_indices(board):
    if not board.get("audioData"):
        return [1]  # One for the in-game audio track.
    return [i + 1 for i in range(len(board["audioData"]))]


def make_audio_symbol_labels(audio_indices):
    return [f".definelabel MUSIC_TRACK_INDEX_{i + 1},{audio_index}"
            for i, audio_index in enumerate(audio_indices)]


def prep_get_audio_c(code, audio_indices):
    """Surrounds the get audio C code with the necessary symbols."""
    defines = "\n".join(make_audio_defines(audio_indices))
    return f"""
#define PickAudioIndex __PP64_INTERNAL_GET_BOARD_AUDIO_INDEX
{defines}
{code}
  """


def make_audio_defines(audio_indices):
    """Creates defines for music tracks."""
    if not audio_indices:
        return []
    return [f"#define MUSIC_TRACK_INDEX_{i + 1} {audio_index}"
            for i, audio_index in enumerate(audio_indices)]
