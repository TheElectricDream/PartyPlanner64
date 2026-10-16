"""Preparing event C code so that it compiles in isolation (prepC.ts)."""

from ..types import EventParameterType
from .jsfmt import js_join, js_str


def _get_chain_index_values_from_absolute_index(chains, abs_space_index):
    from ..adapter.boarddef import get_chain_index_values_from_absolute_index
    return get_chain_index_values_from_absolute_index(chains, abs_space_index)


def prep_c(code, event, space_event, info):
    """Takes event C code, and makes it able to compile (in isolation)."""
    from .additionalbg import get_board_additional_bg_hvq_indices, make_additional_bg_defines
    from .getaudiochoice import make_audio_defines

    parameter_defines = make_parameter_symbol_defines(event, space_event, info)
    audio_defines = make_audio_defines(info.get("audio_indices"))
    bg_defines = make_additional_bg_defines(
        info["board_info"]["bg_dir"],
        get_board_additional_bg_hvq_indices(info.get("board")),
    )
    code_with_defines = "\n".join(parameter_defines + audio_defines + bg_defines + [code])

    return prep_generic_c(code_with_defines, info.get("game"))


def prep_generic_c(code, game):
    """Takes event C code, and makes it able to compile (in isolation)."""
    # TODO: Add in game-specific pre-made types.
    # const syms = getGameLibraryHeaders(game, true);
    return "\n".join([
        # ...syms,
        code,
    ])


def make_parameter_symbol_defines(event, space_event, info):
    """Creates C pre-processor defines for parameters."""
    parameter_symbols = []
    parameters = event.parameters
    parameter_values = space_event.get("parameterValues")
    if parameters and parameter_values is not None:
        for parameter in parameters:
            name = parameter["name"]
            parameter_value = parameter_values.get(name)
            ptype = getattr(parameter["type"], "value", parameter["type"])
            if ptype == EventParameterType.Boolean:
                parameter_symbols.append(f"#define {name} {1 if parameter_value else 0}")

            elif ptype in (EventParameterType.Number, EventParameterType.PositiveNumber):
                if isinstance(parameter_value, (int, float)) and not isinstance(parameter_value, bool):
                    parameter_symbols.append(f"#define {name} {js_str(parameter_value)}")
                else:
                    parameter_symbols.append(f"#define {name} 0")

            elif ptype == EventParameterType.NumberArray:
                pass  # TODO: Maybe expose labels for these?

            elif ptype == EventParameterType.Space:
                if info.get("test_compile"):
                    parameter_symbols.append(f"#define {name} 0")
                    parameter_symbols.append(f"#define {name}_chain_index 0")
                    parameter_symbols.append(f"#define {name}_chain_space_index 0")
                else:
                    parameter_symbols.append(f"#define {name} {js_str(parameter_value)}")
                    if info.get("chains") is not None:
                        indices = _get_chain_index_values_from_absolute_index(
                            info["chains"], parameter_value)
                        parameter_symbols.append(f"#define {name}_chain_index {indices[0]}")
                        parameter_symbols.append(
                            f"#define {name}_chain_space_index {indices[1]}")

            elif ptype == EventParameterType.SpaceArray:
                if info.get("test_compile"):
                    parameter_symbols.append(f"#define {name} 0")
                    parameter_symbols.append(f"#define {name}_length 1")
                    parameter_symbols.append(f"#define {name}_chain_indices 0")
                    parameter_symbols.append(f"#define {name}_chain_space_indices 0")
                else:
                    space_arr = parameter_value or []
                    parameter_symbols.append(f"#define {name} {js_join(space_arr)}")
                    parameter_symbols.append(f"#define {name}_length {len(space_arr)}")

                    all_indices = [_get_chain_index_values_from_absolute_index(info.get("chains"), s)
                                   for s in space_arr]
                    chain_indices = [x[0] for x in all_indices]
                    chain_space_indices = [x[1] for x in all_indices]
                    parameter_symbols.append(
                        f"#define {name}_chain_indices {js_join(chain_indices)}")
                    parameter_symbols.append(
                        f"#define {name}_chain_space_indices {js_join(chain_space_indices)}")

            else:
                if parameter_value is not None:
                    parameter_symbols.append(f"#define {name} {js_str(parameter_value)}")
    return parameter_symbols
