"""Custom events: reading their header comments, test assembly, writing (customevents.ts).

A custom event's code starts with comment properties:

    ; NAME: My Event
    ; GAMES: MP1_USA,MP2_USA
    ; EXECUTION: Direct
    ; PARAM: Number|coins
"""

import re

from ..types import (
    EVENT_PARAMETER_TYPES,
    EditorEventActivationType,
    EventCodeLanguage,
    Game,
    get_execution_type_by_name,
    get_game_name,
)
from ..utils.debug import log
from .events import Event
from .jsfmt import js_trim
from .prep_asm import prep_asm
from .prep_c import prep_c

# JavaScript's line terminators, for regexes that must behave like JS ones
# with the "m" flag (where "." stops at \r too, and ^/$ see \r as a line end).
_LT = "\n\r\u2028\u2029"
_BOL = "(?:^|(?<=[" + _LT + "]))"
_EOL = "(?=[" + _LT + "]|\\Z)"
_DOT = "[^" + _LT + "]"


def _property_regex(prop_name):
    return re.compile(_BOL + r"\s*[;\/]+\s*" + prop_name + ":(" + _DOT + "+)" + _EOL,
                      re.IGNORECASE)


def _js_error_string(e):
    """`"" + e` for a thrown Error: "Error: message"."""
    return "Error: " + str(e)


def _dummy_board_info():
    from ..adapter.boardinfobase import dummy_board_info
    return dummy_board_info


def _assemble(asm):
    from ..mips import assemble
    return assemble(asm)


def _compile(code):
    from ..utils.c_compiler import compile
    return compile(code)


class CustomAsmHelper:
    """Helpers for the comment properties of custom event code."""

    @staticmethod
    def read_discrete_property(asm, prop_name):
        match = _property_regex(prop_name).search(asm)
        if match:
            return match.group(1)
        return None

    @staticmethod
    def read_discrete_property_set(asm, prop_name):
        return [js_trim(m.group(1)) for m in _property_regex(prop_name).finditer(asm)]

    @staticmethod
    def clear_discrete_properties(asm, properties):
        for property_name in properties:
            regex = re.compile(_BOL + r"\s*[;\/]+\s*" + property_name + ":" + _DOT + "*[\r\n]*",
                               re.IGNORECASE)
            asm = regex.sub("", asm)
        return asm

    @staticmethod
    def write_discrete_property(asm, prop_name, value, comment_char):
        return f"{comment_char} {prop_name}: {value}\n" + asm

    @staticmethod
    def write_discrete_property_array(asm, prop_name, values, comment_char):
        for i in range(len(values) - 1, -1, -1):
            asm = f"{comment_char} {prop_name}: {values[i]}\n" + asm
        return asm

    @staticmethod
    def read_supported_games(asm):
        value = CustomAsmHelper.read_discrete_property(asm, "GAMES")
        if value is not None:
            ids = js_trim(value).split(",")
            supported_games = []
            for id in ids:
                if id in Game.__members__:
                    supported_games.append(Game[id])
            return supported_games
        return None

    @staticmethod
    def read_execution_type(asm):
        value = CustomAsmHelper.read_discrete_property(asm, "EXECUTION")
        if value:
            return get_execution_type_by_name(js_trim(value))
        return None

    @staticmethod
    def read_parameters(asm):
        entry_strings = CustomAsmHelper.read_discrete_property_set(asm, "PARAM")
        parameters = []
        for entry_str in entry_strings:
            pieces = entry_str.split("|")
            if len(pieces) != 2:
                continue
            parameter = {"name": pieces[1], "type": pieces[0]}  # hopefully
            try:
                CustomAsmHelper.validate_parameters([parameter])
                parameters.append(parameter)
            except Exception:
                pass  # It's invalid, just skip it.
        return parameters

    valid_parameter_name_regex = re.compile(r"[\w?!]*", re.ASCII)

    @staticmethod
    def validate_parameters(parameters):
        if not parameters:
            return
        for parameter in parameters:
            if not parameter.get("name"):
                raise ValueError("An event parameter didn't have a name")
            if not parameter.get("type"):
                raise ValueError("An event parameter didn't have a type")
            if not CustomAsmHelper.valid_parameter_name_regex.fullmatch(parameter["name"]):
                raise ValueError(f"Event parameter name '{parameter['name']}' is not valid")
            ptype = getattr(parameter["type"], "value", parameter["type"])
            if ptype not in EVENT_PARAMETER_TYPES:
                raise ValueError(f"Event parameter type {ptype} is not recognized")

    @staticmethod
    def test_custom_event(lang, code, parameters=None, info=None):
        info = info or {}
        if lang == EventCodeLanguage.MIPS:
            return CustomAsmHelper.test_assemble(code, parameters, info)
        if lang == EventCodeLanguage.C:
            return CustomAsmHelper.test_compile(code, parameters, info)
        raise ValueError(f"Unrecognized event code language: {lang}")

    @staticmethod
    def test_assemble(asm, parameters=None, info=None):
        """Does a test assembly of a custom event. Returns the bytes."""
        parameter_values = _make_fake_parameter_values(parameters)

        custom_event = create_custom_event(EventCodeLanguage.MIPS, asm)
        write_info = {
            "addr": 0,
            "audio_indices": [1] * 50,
            "board_info": _dummy_board_info(),
            "board": {
                # 50 is just some very high number; we don't know how many they need.
                "additionalbg": [""] * 50,
            },
            "test_compile": True,
        }
        write_info.update(info or {})
        prepped_asm = prep_asm(asm, custom_event, {"parameterValues": parameter_values},
                               write_info)
        return _assemble(prepped_asm)

    @staticmethod
    def test_compile(code, parameters=None, info=None):
        """Does a test compile and assembly of a C custom event. Returns the asm."""
        info = info or {}
        parameter_values = _make_fake_parameter_values(parameters)

        custom_event = create_custom_event(EventCodeLanguage.C, code)
        c_info = {
            "test_compile": True,
            "audio_indices": [1] * 50,
            "board_info": _dummy_board_info(),
            "board": {
                "additionalbg": [""] * 50,
            },
        }
        c_info.update(info)
        prepped_c = prep_c(code, custom_event, {"parameterValues": parameter_values}, c_info)
        log(prepped_c)

        asm = _compile(prepped_c)
        log(asm)

        asm_info = {
            "addr": 0,
            "audio_indices": [1] * 50,
            "board_info": _dummy_board_info(),
            "board": {
                "additionalbg": [""] * 50,
            },
        }
        asm_info.update(info)
        prepped_asm = prep_asm(asm, custom_event, {}, asm_info)
        _assemble(prepped_asm)

        return asm


def _make_fake_parameter_values(parameters):
    parameter_values = {}
    if parameters:
        for parameter in parameters:
            parameter_values[parameter["name"]] = 0
    return parameter_values


def _language(language):
    try:
        return EventCodeLanguage(language)
    except ValueError:
        return language


def create_custom_event(language, code):
    """Creates a custom event object from a code string."""
    event_name = CustomAsmHelper.read_discrete_property(code, "NAME")
    if not event_name or not js_trim(event_name):
        raise ValueError("Custom event must have a name")
    event_name = js_trim(event_name)
    event_id = event_name

    execution_type = CustomAsmHelper.read_execution_type(code)
    if not execution_type:
        raise ValueError("Custom event must have execution type")

    supported_games = CustomAsmHelper.read_supported_games(code)
    if supported_games is None:
        raise ValueError("Custom event must have supported games list")

    parameters = CustomAsmHelper.read_parameters(code)
    return Event(
        id=event_id,
        name=event_name,
        custom=True,
        language=_language(language),
        asm=code,
        activation_type=EditorEventActivationType.LANDON,
        execution_type=execution_type,
        supported_games=supported_games,
        parameters=parameters,
    )


def validate_custom_event(event):
    """Test-assembles (or compiles) the event for each claimed game.

    Raises ValueError with the TypeScript's message on failure."""
    language = event.language
    parameters = event.parameters
    supported_games = event.supported_games

    if parameters:
        CustomAsmHelper.validate_parameters(parameters)

    code = event.asm

    # Test that assembly works in all claimed supported versions.
    for game in supported_games:
        try:
            CustomAsmHelper.test_custom_event(language, code, parameters, {"game": game})
        except Exception as e:
            error_msg = ("Failed a test compile/assembly for "
                         + str(get_game_name(game))
                         + ". The event code may need adjustments before it can be used.\n\n"
                         + _js_error_string(e))
            log(error_msg + "\n\n" + code)
            raise ValueError(error_msg) from e

    return True


def write_custom_event(data_view, space_event, info, lang, code, temp):
    """Returns the assembly for a custom event (compiling C first)."""
    log("Writing custom event", space_event, info)

    custom_event = create_custom_event(lang, code)

    if lang == EventCodeLanguage.C:
        prepped_c = prep_c(code, custom_event, space_event, info)
        code = _compile(prepped_c)

    return code
