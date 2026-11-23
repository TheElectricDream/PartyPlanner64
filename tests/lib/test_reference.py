"""The code reference (lib/reference): its entries hold together, and every example in
it assembles or compiles, for each game its entry is about."""

import pytest

import re

from partyplanner64.lib import reference
from partyplanner64.lib.reference.sentences import FUNCTIONS
from partyplanner64.lib.events import additionalbg, getaudiochoice
from partyplanner64.lib.events.customevents import CustomAsmHelper
from partyplanner64.lib.mips.inst.opcodes import opcode_details
from partyplanner64.lib.symbols.symbols import get_symbol_notes, get_symbols
from partyplanner64.lib.types import EventCodeLanguage, Game

# Provided by PartyPlanner (prep_asm.make_game_symbol_labels), not the symbol tables.
_OVERLAY_SYMBOLS = {"GetBasicPromptSelection", "ViewBoardMap", "GetRandPromptSelection",
                    "GetBoardAudioIndex"}


def test_entries_hold_together():
    assert reference.problems() == []


def test_every_opcode_has_an_entry():
    words = {w for e in reference.get_entries() if e["id"].startswith("mips:") for w in e["words"]}
    for op in opcode_details:
        if op == "c.cond.fmt":
            assert "c.eq.s" in words
        elif op.endswith(".fmt"):
            assert op[:-3] + "s" in words or op[:-3] + "d" in words or op[:-3] + "w" in words, op
        else:
            assert op in words, op


def _is_sentence(text):
    """Starts with a capitalized word (not a formula like "rd = rs + rt") and ends with a period."""
    return bool(re.match(r"^[A-Z][a-z]+[ ,;]", text)) and text.endswith(".") and len(text.split()) >= 3


def test_every_instruction_and_function_says_what_it_does():
    for e in reference.get_entries():
        if e["kind"] in ("instruction", "pseudo", "function"):
            assert _is_sentence(e["summary"]), (e["id"], e["summary"])
    for name, sentence in FUNCTIONS.items():
        assert _is_sentence(sentence), (name, sentence)


def test_every_named_game_function_has_a_sentence():
    named = set()
    for game in Game:
        try:
            symbols = get_symbols(game, "code") or []
        except ValueError:   # no symbols for this game (MP2 PAL)
            continue
        for sym in symbols:
            if not sym["name"].startswith("func_"):
                named.add(sym["name"])
    assert sorted(named - set(FUNCTIONS)) == []
    assert sorted(set(FUNCTIONS) - named) == []   # none left over from renamed symbols


def test_game_entries_name_real_symbols():
    for e in reference.get_entries():
        if e["category"] != "Game":
            continue
        assert e["games"], e["id"]
        for game in e["games"]:
            names = {s["name"] for s in get_symbols(Game[game])} | _OVERLAY_SYMBOLS
            assert e["name"] in names, (e["id"], game)


def test_symbol_notes_keep_the_whole_comment():
    notes = get_symbol_notes(Game.MP3_USA)
    assert notes["AdjustPlayerCoins"] == "A0=player_index,A1=amount (signed), ensures 0 <= coins <= 999"
    desc = {s["name"]: s.get("desc") for s in get_symbols(Game.MP3_USA)}
    assert desc["AdjustPlayerCoins"] == "A0=player_index"     # the table keeps the first piece
    assert get_symbol_notes(Game.MP2_PAL) == {}


def _header(lang, params):
    cc = "//" if lang == "c" else ";"
    lines = [f"{cc} NAME: Reference example", f"{cc} GAMES: MP3_USA", f"{cc} EXECUTION: Direct"]
    lines += [f"{cc} PARAM: {t}|{n}" for t, n in params]
    return "\n".join(lines) + "\n"


def _event_code(ex):
    params = ex.get("params", [])
    code = ex["code"]
    check = ex["check"]
    if check == "event":
        return code
    if check == "mips":
        return (_header("mips", params) + "ADDIU SP SP -32\nSW RA 28(SP)\n" + code
                + "\nLW RA 28(SP)\nJR RA\nADDIU SP SP 32\n")
    if check == "c":
        return _header("c", params) + '#include "ultra64.h"\nvoid main() {\n' + code + "\n}\n"
    if check == "c-top":
        return _header("c", params) + '#include "ultra64.h"\n' + code + "\nvoid main() {\n}\n"
    raise AssertionError(check)


def _params(code):
    from partyplanner64.lib.events.customevents import create_custom_event
    language = EventCodeLanguage.C if code.lstrip().startswith("//") else EventCodeLanguage.MIPS
    return create_custom_event(language, code).parameters


def _cases():
    out = []
    for entry_id, ex in reference.examples_to_check():
        entry = reference.get_entry(entry_id)
        games = ex.get("games") or entry.get("games") or ["MP3_USA"]
        for game in games:
            out.append(pytest.param(entry_id, ex, game, id=f"{entry_id}:{ex['title']}:{game}"))
    return out


@pytest.mark.parametrize("entry_id,example,game", _cases())
def test_example_compiles(entry_id, example, game):
    lang = EventCodeLanguage.C if example["lang"] == "c" else EventCodeLanguage.MIPS
    if example["check"] in ("background", "music"):
        board = {"game": int(game[2]), "additionalbg": ["a", "b"], "audioData": [{}, {}]}
        test = (additionalbg.test_additional_bg_code_with_game if example["check"] == "background"
                else getaudiochoice.test_get_audio_code_with_game)
        assert test(example["code"], lang, board, Game[game]) == []
        return
    code = _event_code(example)
    if example["check"] == "event":
        code = code.replace("GAMES: MP3_USA", "GAMES: " + game)
    CustomAsmHelper.test_custom_event(lang, code, _params(code), {"game": Game[game]})


def test_the_assembler_errors_the_reference_mentions():
    """syntax:operands and syntax:comments describe these; if the assembler changes, so must they."""
    from partyplanner64.lib.mips import assemble

    for value in ("0-toll", "toll+1", "0X10"):
        with pytest.raises(Exception):
            assemble(".definelabel toll,5\nADDIU A1 R0 " + value)
    with pytest.raises(Exception):
        assemble('.ascii "Hi",0xFF ; a "quote"')
