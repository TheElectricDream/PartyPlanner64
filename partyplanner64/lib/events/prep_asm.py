"""Preparing event assembly so that it assembles in isolation (prepAsm.ts)."""

import re

from ..types import EventParameterType, Game
from ..utils.debug import hexstr
from .jsfmt import js_join, js_str, js_trim


def _get_chain_index_values_from_absolute_index(chains, abs_space_index):
    from ..adapter.boarddef import get_chain_index_values_from_absolute_index
    return get_chain_index_values_from_absolute_index(chains, abs_space_index)


def _get_symbols(game):
    from ..symbols.symbols import get_symbols
    return get_symbols(game)


def _sym_field(symbol, field):
    if isinstance(symbol, dict):
        return symbol[field]
    return getattr(symbol, field)


def prep_asm(asm, event, space_event, info):
    """Takes event asm, and makes it assemble (in isolation)."""
    from .additionalbg import get_board_additional_bg_hvq_indices, make_bg_symbol_labels
    from .getaudiochoice import make_audio_symbol_labels

    parameter_symbols = make_parameter_symbol_labels(event, space_event, info)
    audio_symbols = make_audio_symbol_labels(info.get("audio_indices"))
    bg_symbols = make_bg_symbol_labels(
        info["board_info"]["bg_dir"],
        get_board_additional_bg_hvq_indices(info.get("board")),
    )
    asm_with_param_syms = "\n".join(
        parameter_symbols + audio_symbols + bg_symbols + [asm])

    return prep_generic_asm(asm_with_param_syms, info.get("addr"), info.get("game"))


def prep_generic_asm(asm, addr, game):
    """Takes asm, and makes it assemble (in isolation)."""
    org_directive = f".org {hexstr(addr)}"
    addr_syms = make_generic_symbols_for_addresses(asm)
    game_syms = make_game_symbol_labels(game, True)
    return "\n".join(
        [org_directive] + addr_syms + game_syms + [asm, ".align 4"])  # it better!


def prep_single_event_asm(asm, event, space_event, info, keep_static, event_num):
    # We either define a label at the top, or an alias to the main: label if present.
    has_main_entry = next(
        (value for value in asm.split("\n") if value.startswith("main:")), None)
    event_label = create_event_instance_label(info["cur_space_index"], event_num)
    top_label = (not has_main_entry) and f"{event_label}:"
    bottom_label = bool(has_main_entry) and f".definelabel {event_label},main"

    params = "\n".join(make_parameter_symbol_labels(event, space_event, info))
    return scope_labels_static_by_default(
        f"""
    .beginfile ; Scopes static labels
    {top_label or ""}
    {params}
    {asm}
    {bottom_label or ""}
    .align 4
    .endfile
  """,
        keep_static,
    )


def make_game_symbol_labels(game, need_overlay_stubs):
    symbols = _get_symbols(game)
    syms = [".definelabel %s,0x%x" % (_sym_field(s, "name"), _sym_field(s, "addr"))
            for s in symbols]

    # Add symbols that are aliased from the board overlay.
    if game == Game.MP1_USA:
        if need_overlay_stubs:
            syms.append(".definelabel GetBoardAudioIndex,0")
        else:
            syms.append(".definelabel GetBoardAudioIndex,__PP64_INTERNAL_GET_BOARD_AUDIO_INDEX")
    elif game == Game.MP2_USA:
        if need_overlay_stubs:
            syms.append(".definelabel ViewBoardMap,0")
            syms.append(".definelabel GetBoardAudioIndex,0")
            syms.append(".definelabel GetRandPromptSelection,0")
        else:
            syms.append(".definelabel ViewBoardMap,__PP64_INTERNAL_VIEW_MAP")
            syms.append(".definelabel GetBoardAudioIndex,__PP64_INTERNAL_GET_BOARD_AUDIO_INDEX")
            syms.append(
                ".definelabel GetRandPromptSelection,__PP64_INTERNAL_RAND_MESSAGE_CHOICE")
    elif game == Game.MP3_USA:
        if need_overlay_stubs:
            syms.append(".definelabel GetBasicPromptSelection,0")
            syms.append(".definelabel ViewBoardMap,0")
            syms.append(".definelabel GetBoardAudioIndex,0")
        else:
            syms.append(
                ".definelabel GetBasicPromptSelection,__PP64_INTERNAL_BASIC_MESSAGE_CHOICE")
            syms.append(".definelabel ViewBoardMap,__PP64_INTERNAL_VIEW_MAP")
            syms.append(".definelabel GetBoardAudioIndex,__PP64_INTERNAL_GET_BOARD_AUDIO_INDEX")

    return syms


_func_regex = re.compile(r"func_(8[0-9A-Fa-f]{7})")
_addr_regex = re.compile(r"D_(8[0-9A-Fa-f]{7})")


def make_generic_symbols_for_addresses(asm):
    """Creates labels for any "obvious" symbols:
      func_80012345
      D_80012345
    """
    results = []

    for m in _func_regex.finditer(asm):
        match = m.group(0)
        if (match + ":") in asm:
            # Don't create an alias if there's a label for "func_x" already,
            # since the generated label is most likely going to corrupt things.
            continue
        addr = match[5:].upper()
        results.append(f".definelabel {match},0x{addr}")

    for m in _addr_regex.finditer(asm):
        match = m.group(0)
        if (match + ":") in asm:
            continue
        addr = match[2:].upper()
        results.append(f".definelabel {match},0x{addr}")

    # Remove duplicates.
    return list(dict.fromkeys(results))


def _ptype(parameter):
    t = parameter["type"]
    return getattr(t, "value", t)


def make_parameter_symbol_labels(event, space_event, info):
    parameter_symbols = []
    parameters = event.parameters
    parameter_values = space_event.get("parameterValues")
    if parameters and parameter_values is not None:
        for parameter in parameters:
            name = parameter["name"]
            parameter_value = parameter_values.get(name)
            ptype = _ptype(parameter)
            if ptype == EventParameterType.Boolean:
                parameter_symbols.append(f".definelabel {name},{1 if parameter_value else 0}")

            elif ptype == EventParameterType.Number:
                if isinstance(parameter_value, (int, float)) and not isinstance(parameter_value, bool):
                    parameter_symbols.append(f".definelabel {name},{js_str(parameter_value)}")

            elif ptype == EventParameterType.NumberArray:
                pass  # TODO: Maybe expose labels for these?

            elif ptype == EventParameterType.Space:
                parameter_symbols.append(f".definelabel {name},{js_str(parameter_value)}")
                if info.get("chains") is not None:
                    indices = _get_chain_index_values_from_absolute_index(
                        info["chains"], parameter_value)
                    parameter_symbols.append(f".definelabel {name}_chain_index,{indices[0]}")
                    parameter_symbols.append(
                        f".definelabel {name}_chain_space_index,{indices[1]}")
                else:
                    # Mostly for testAssemble
                    parameter_symbols.append(f".definelabel {name}_chain_index,-1")
                    parameter_symbols.append(f".definelabel {name}_chain_space_index,-1")

            elif ptype == EventParameterType.SpaceArray:
                if info.get("test_compile"):
                    parameter_symbols.append(f"{name} equ 0")
                    parameter_symbols.append(f"{name}_length equ 1")
                    parameter_symbols.append(f"{name}_chain_indices equ 0")
                    parameter_symbols.append(f"{name}_chain_space_indices equ 0")
                else:
                    space_arr = parameter_value or []
                    parameter_symbols.append(f"{name} equ {js_join(space_arr)}")
                    parameter_symbols.append(f"{name}_length equ {len(space_arr)}")

                    all_indices = [_get_chain_index_values_from_absolute_index(info.get("chains"), s)
                                   for s in space_arr]
                    chain_indices = [x[0] for x in all_indices]
                    chain_space_indices = [x[1] for x in all_indices]
                    parameter_symbols.append(f"{name}_chain_indices equ {js_join(chain_indices)}")
                    parameter_symbols.append(
                        f"{name}_chain_space_indices equ {js_join(chain_space_indices)}")

            else:
                if parameter_value is not None:
                    parameter_symbols.append(f".definelabel {name},{js_str(parameter_value)}")
    return parameter_symbols


_label_char_regex = re.compile(r"[@\w!?]", re.ASCII)


def scope_labels_static_by_default(asm, keep_static):
    """Events are written assuming their global labels are scoped to themselves,
    but during assembly they need to be scoped using the static labels feature.
    """
    lines = [js_trim(line) for line in asm.split("\n")]

    # We always find labels to scope without static sections...
    lines_without_static_sections = _remove_static_sections(lines, keep_static)
    labels = _find_labels_to_scope(lines_without_static_sections)

    # But only keep the static section when replacing the first time.
    asm = (_replace_static_region_directives(lines) if keep_static
           else "\n".join(lines_without_static_sections))

    for label in labels:
        current_index = -1
        while True:
            current_index = asm.find(label, max(current_index, 0))
            if current_index < 0:
                break
            if current_index > 0:
                prev_char = asm[current_index - 1]
                if _label_char_regex.match(prev_char):
                    # Something odd comes before this instance of the label.
                    current_index += len(label)
                    continue
            if current_index + len(label) < len(asm):
                next_char = asm[current_index + len(label)]
                if _label_char_regex.match(next_char):
                    # Something odd comes after this instance of the label.
                    current_index += len(label)
                    continue

            asm = asm[:current_index] + "@" + asm[current_index:]
            current_index += len(label) + 1

    return asm


_define_label_regex = re.compile(r"^\.definelabel\s+([^,]+)", re.IGNORECASE)
_label_regex = re.compile(r"^([@\w!?]+):", re.IGNORECASE | re.ASCII)
_equ_regex = re.compile(r"^\s*([@\w!?]+)\s+equ(?:\Z|\s+)", re.IGNORECASE | re.ASCII)


def _find_labels_to_scope(lines):
    """Obtains an array of all the labels within the given lines of assembly.
    Only gets labels that should be scoped for event assembly.
    """
    found_labels = []
    for line in lines:
        match = _define_label_regex.search(line)
        if match:
            found_labels.append(match.group(1))
            continue

        match = _equ_regex.search(line)
        if match:
            found_labels.append(match.group(1))
            continue

        while True:
            match = _label_regex.search(line)
            if not match:
                break
            found_labels.append(match.group(1))
            line = line[len(match.group(0)):]
    return [label for label in found_labels if _label_should_be_scoped(label)]


def _label_should_be_scoped(label):
    if "__PP64_INTERNAL" in label:
        return False  # Don't scope internal labels.
    if label[0] == "@":
        return False  # Don't scope already somewhat-scoped labels.
    return True


def _remove_static_sections(lines, keeping_statics):
    within_static = False
    filtered_lines = []
    for line in lines:
        if line == ".beginstatic":
            if within_static:
                raise ValueError("Cannot repeat .beginstatic within a static section")
            within_static = True
            if not keeping_statics:
                filtered_lines.append("; omitted statics")
            continue
        elif line == ".endstatic":
            if not within_static:
                raise ValueError("Saw .endstatic without .beginstatic")
            within_static = False
            continue

        if not within_static:
            filtered_lines.append(line)

    if within_static:
        raise ValueError("Saw .beginstatic without .endstatic")

    return filtered_lines


def _replace_static_region_directives(lines):
    """Just comments out the .beginstatic and .endstatic lines"""
    adjusted_lines = []
    for line in lines:
        if line == ".beginstatic":
            adjusted_lines.append("; .beginstatic")
        elif line == ".endstatic":
            adjusted_lines.append("; .endstatic")
        else:
            adjusted_lines.append(line)
    return "\n".join(adjusted_lines)


def create_event_instance_label(space_index, event_number):
    str_index = ("minus" + str(abs(space_index))) if space_index < 0 else str(space_index)
    return f"__PP64_INTERNAL_EVENT_{str_index}_{event_number}"
