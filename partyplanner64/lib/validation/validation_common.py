"""Validation rules shared by the games (validation.common.ts).

Importing this module creates the rules (see validationrules.get_rule).
"""

import logging
import re

from ..boards import (
    BoardAudioType,
    get_additional_background_code,
    get_audio_select_code,
    get_board_event,
    get_connections,
    get_dead_ends,
    get_link,
    get_link_start_indices,
    get_spaces_of_sub_type,
    get_start_space_index,
)
from ..events.customevents import CustomAsmHelper
from ..events.event_library import get_events_in_library
from ..events.events import get_event, is_unsupported
from ..events.jsfmt import js_str
from ..types import Space, SpaceSubtype, ValidationLevel, is_array_event_parameter_type
from .validationrules import create_rule

logger = logging.getLogger("partyplanner64")


def _romhandler():
    from ..romhandler import romhandler
    return romhandler


def _is_number(value):
    return isinstance(value, (int, float)) and not isinstance(value, bool)


def _space_at(board, index):
    spaces = board["spaces"]
    try:
        i = int(index)
    except (TypeError, ValueError):
        return None
    if 0 <= i < len(spaces):
        return spaces[i]
    return None


HasStart = create_rule("HASSTART", "Has start space", ValidationLevel.ERROR)


@HasStart.set_fails
def _has_start_fails(context, args=None):
    cur_idx = get_start_space_index(context["board"])
    if cur_idx < 0:
        return "No start space found on board."
    return False


GameVersionMatch = create_rule("GAMEVERSION", "Game version mismatch", ValidationLevel.ERROR)


@GameVersionMatch.set_fails
def _game_version_fails(context, args=None):
    board = context["board"]
    rom_game = _romhandler().get_game_version()
    if rom_game != board.get("game"):
        return f"Board is for MP{js_str(board.get('game'))}, but ROM is MP{js_str(rom_game)}"
    return False


DeadEnd = create_rule("DEADEND", "No dead ends", ValidationLevel.WARNING)


@DeadEnd.set_fails
def _dead_end_fails(context, args=None):
    board = context["board"]
    dead_ends = get_dead_ends(board)

    start_index = get_start_space_index(board)
    if start_index < 0:
        return False  # Let HASSTART rule complain.

    if start_index in dead_ends:
        return "Start space does not lead anywhere."

    if len(dead_ends):
        return "There is a dead end on the board."

    return False


TooManySpaces = create_rule("TOOMANYSPACES", "Too many spaces", ValidationLevel.ERROR)


@TooManySpaces.set_fails
def _too_many_spaces_fails(context, args=None):
    if len(context["board"]["spaces"]) > 0xFFFF:
        return "There is a hard limit of 65535 spaces."
    return False


OverRecommendedSpaces = create_rule(
    "OVERRECOMMENDEDSPACES", "Over recommended spaces", ValidationLevel.WARNING)


@OverRecommendedSpaces.set_fails
def _over_recommended_spaces_fails(context, args=None):
    space_count = len(context["board"]["spaces"])
    if space_count > args["max"]:
        return (f"{space_count} spaces present, more than {js_str(args['max'])} "
                f"spaces can be unstable.")
    return False


def _make_too_many_of_subtype_rule(subtype, name):
    rule = create_rule(
        "TOOMANY" + re.sub(r"\s+", "", name.upper()),
        f"Too many {name}",
        ValidationLevel.ERROR,
    )

    def fails(context, args=None):
        args = args if args is not None else {}
        limit = args.get("limit") or 0
        count = len([space for space in context["board"]["spaces"]
                     if space and space.get("subtype") == subtype
                     and space.get("subtype") is not None])
        if count > limit:
            return f"There are {count} {name}, but the limit is {js_str(limit)} for this board."
        return False

    rule.fails = fails


_make_too_many_of_subtype_rule(SpaceSubtype.BOO, "Boos")
_make_too_many_of_subtype_rule(SpaceSubtype.BOWSER, "Bowsers")
_make_too_many_of_subtype_rule(SpaceSubtype.KOOPA, "Koopas")
_make_too_many_of_subtype_rule(SpaceSubtype.BANK, "Banks")
_make_too_many_of_subtype_rule(SpaceSubtype.ITEMSHOP, "Item Shops")
_make_too_many_of_subtype_rule(SpaceSubtype.GATE, "Gates")


def _get_star_space_count(board):
    return len([space for space in board["spaces"] if space and space.get("star")])


BadStarCount = create_rule("BADSTARCOUNT", "Bad star count", ValidationLevel.ERROR)


@BadStarCount.set_fails
def _bad_star_count_fails(context, args=None):
    count = _get_star_space_count(context["board"])

    disallowed = args.get("disallowed") or {}
    if disallowed.get(count) or disallowed.get(str(count)):
        if count == 1:
            return "There cannot be exactly 1 star space."
        return f"There cannot be exactly {count} star spaces."

    low = args.get("low") or 0
    high = args.get("high") or 0

    if count < low or count > high:
        if low != high:
            return f"There are {count} stars, but the range is {low}-{high} for this board."
        return f"There are {count} stars, but the count must be {low} for this board."
    return False


WarnNoStarSpaces = create_rule("WARNNOSTARSPACES", "No star spaces", ValidationLevel.WARNING)


@WarnNoStarSpaces.set_fails
def _warn_no_star_spaces_fails(context, args=None):
    count = _get_star_space_count(context["board"])
    if count == 0:
        return "There are no star spaces, this may be unintentional."
    return False


def _make_too_few_of_space_type_rule(type, name):
    rule = create_rule(
        "TOOFEW" + re.sub(r"\s+", "", name.upper()) + "SPACES",
        f"Too few {name} spaces",
        ValidationLevel.ERROR,
    )

    def fails(context, args=None):
        args = args if args is not None else {}
        low = args.get("low") or 0
        count = len([space for space in context["board"]["spaces"]
                     if space and space.get("type") == type])
        if count < low:
            return (f"There are {count} {name} spaces, "
                    f"need at least {js_str(low)} spaces of this type.")
        return False

    rule.fails = fails


_make_too_few_of_space_type_rule(Space.BLUE, "Blue")
_make_too_few_of_space_type_rule(Space.RED, "Red")


TooManyOfEvent = create_rule("TOOMANYOFEVENT", "Too many of event", ValidationLevel.ERROR)


@TooManyOfEvent.set_fails
def _too_many_of_event_fails(context, args=None):
    count = 0
    for space in context["board"]["spaces"]:
        if not space or not space.get("events"):
            continue
        for event in space["events"]:
            if event["id"] == args["event"].id:
                count += 1

    low = args.get("low") or 0
    high = args.get("high") or 0
    name = args["event"].name
    if count < low or count > high:
        if low and high:
            return (f"There are {count} of event {name}, "
                    f"but the range is {low}-{high} for this board.")
        if low:
            return (f"There are {count} of event {name}, "
                    f"but there must be at least {low} for this board.")
        elif high:
            return (f"There are {count} of event {name}, "
                    f"but there can be at most {high} for this board.")
    return False


UnrecognizedEvents = create_rule("UNRECOGNIZEDEVENTS", "Unrecognized events", ValidationLevel.ERROR)


@UnrecognizedEvents.set_fails
def _unrecognized_events_fails(context, args=None):
    board = context["board"]
    unrecognized_events = {}
    for space in board["spaces"]:
        if not space or not space.get("events"):
            continue
        for space_event in space["events"]:
            if not get_event(space_event["id"], board, get_events_in_library()):
                unrecognized_events[space_event["id"]] = True

    ids = _js_key_order(unrecognized_events)

    if not ids:
        return False

    error = "The following events were unrecognized:\n"
    for id in ids:
        error += "\t" + js_str(id) + "\n"
    return error


UnsupportedEvents = create_rule("UNSUPPORTEDEVENTS", "Unsupported events", ValidationLevel.ERROR)


@UnsupportedEvents.set_fails
def _unsupported_events_fails(context, args=None):
    board = context["board"]
    unsupported_events = {}
    game_id = _romhandler().get_rom_game()
    for space in board["spaces"]:
        if not space or not space.get("events"):
            continue
        for space_event in space["events"]:
            event = get_event(space_event["id"], board, get_events_in_library())
            if not event:
                continue  # Let the other rule handle this.
            if is_unsupported(event, game_id):
                unsupported_events[space_event["id"]] = True

    ids = _js_key_order(unsupported_events)

    if not ids:
        return False

    error = "The following events cannot be written to this ROM:\n"
    for id in ids:
        error += "\t" + js_str(id) + "\n"
    return error


FailingCustomEvents = create_rule("CUSTOMEVENTFAIL", "Custom event errors", ValidationLevel.ERROR)


@FailingCustomEvents.set_fails
def _failing_custom_events_fails(context, args=None):
    from ..events.getaudiochoice import make_fake_get_audio_indices

    board = context["board"]
    board_info = context["board_info"]
    failing_events = {}
    game_id = _romhandler().get_rom_game()

    def test_event(event):
        try:
            custom_event = get_event(event["id"], board, get_events_in_library())
            board_event = get_board_event(board, event["id"])
            CustomAsmHelper.test_custom_event(
                board_event["language"],
                board_event["code"],
                custom_event.parameters,
                {
                    "game": game_id,
                    "audio_indices": make_fake_get_audio_indices(board),
                    "board": board,
                    "board_info": board_info,
                },
            )
        except Exception as e:
            logger.error("%s", e)
            if not failing_events.get(event["id"]):
                failing_events[event["id"]] = True

    for space in board["spaces"]:
        if not space or not space.get("events"):
            continue
        for event in space["events"]:
            if not event:
                continue  # Let the other rule handle this.
            if not event.get("custom"):
                continue
            test_event(event)

    if board.get("boardevents"):
        for event in board["boardevents"]:
            if not event.get("custom"):
                continue
            test_event(event)

    ids = _js_key_order(failing_events)

    if not ids:
        return False

    error = "The following custom events fail to assemble:\n"
    for id in ids:
        error += "\t" + js_str(id) + "\n"
    return error


BadCustomEventParameters = create_rule(
    "CUSTOMEVENTBADPARAMS", "Custom event parameter issues", ValidationLevel.ERROR)


@BadCustomEventParameters.set_fails
def _bad_custom_event_parameters_fails(context, args=None):
    board = context["board"]
    missing_params = {}

    def test_parameters(event):
        custom_event = get_event(event["id"], board, get_events_in_library())
        parameters = custom_event.parameters
        if parameters:
            for parameter in parameters:
                if is_array_event_parameter_type(parameter["type"]):
                    continue  # Not enforcing these are set right now.
                values = event.get("parameterValues")
                if not values or parameter["name"] not in values:
                    if not missing_params.get(parameter["name"]):
                        missing_params[parameter["name"]] = 0
                    missing_params[parameter["name"]] += 1

    for space in board["spaces"]:
        if not space or not space.get("events"):
            continue
        for event in space["events"]:
            if not event:
                continue  # Let the other rule handle this.
            if not event.get("custom"):
                continue
            test_parameters(event)

    if board.get("boardevents"):
        for event in board["boardevents"]:
            if not event.get("custom"):
                continue
            test_parameters(event)

    error_lines = []
    # (JavaScript visits integer-like keys first.)
    for id in _js_key_order(missing_params):
        count = missing_params[id]
        if not count:
            continue  # ?
        error_lines.append(
            f"\t{count} {id} event parameter{'s are ' if count > 1 else ' is '}not set")

    if not error_lines:
        return False

    return "Some event parameters need to be set:\n" + "\n".join(error_lines)


def _js_key_order(obj):
    index_keys = sorted((k for k in obj if isinstance(k, str) and k.isdigit() and k.isascii()
                         and (k == "0" or not k.startswith("0"))), key=int)
    return index_keys + [k for k in obj if k not in index_keys]


TooManyPathOptions = create_rule("TOOMANYPATHOPTIONS", "Too many path options", ValidationLevel.ERROR)


@TooManyPathOptions.set_fails
def _too_many_path_options_fails(context, args=None):
    board = context["board"]
    args = args if args is not None else {}
    limit = args.get("limit") or 2
    for space in get_link_start_indices(board):
        links = get_link(board, space)
        if isinstance(links, list) and len(links) > limit:
            return f"A space branches in {len(links)} directions, but the maximum is {limit}."
    return False


CharactersOnPath = create_rule("CHARACTERSONPATH", "Characters are on path", ValidationLevel.WARNING)


@CharactersOnPath.set_fails
def _characters_on_path_fails(context, args=None):
    board = context["board"]
    for space_idx in get_link_start_indices(board):
        space = _space_at(board, space_idx)
        if "subtype" in space and space["subtype"] != SpaceSubtype.GATE:
            return ("Characters and objects <a href='https://github.com/PartyPlanner64/PartyPlanner64"
                    "/wiki/Creating-a-Board#special-charactersobjects' target='_blank'>should not "
                    "be on the player path</a>.")
    return False


SplitAtNonInvisibleSpace = create_rule(
    "SPLITATNONINVISIBLESPACE", "Split at non-invisible space", ValidationLevel.WARNING)


@SplitAtNonInvisibleSpace.set_fails
def _split_at_non_invisible_space_fails(context, args=None):
    board = context["board"]
    preferred_split_types = [
        Space.OTHER,
        Space.STAR,
        Space.START,
        Space.BLACKSTAR,
        Space.ARROW,
    ]
    for space_idx in get_link_start_indices(board):
        links = get_connections(int(space_idx), board)
        if len(links) > 1:
            space = _space_at(board, space_idx)
            if space["type"] not in preferred_split_types:
                return ("There is a <a href='https://github.com/PartyPlanner64/PartyPlanner64/wiki"
                        "/Creating-a-Board#board-flow' target='_blank'>non-conventional path "
                        "split</a>.")
    return False


TooManyArrowRotations = create_rule(
    "TOOMANYARROWROTATIONS", "Too many arrow rotations", ValidationLevel.WARNING)


@TooManyArrowRotations.set_fails
def _too_many_arrow_rotations_fails(context, args=None):
    args = args if args is not None else {}
    rotation_count = 0
    for space in context["board"]["spaces"]:
        if not space:
            continue
        if _is_number(space.get("rotation")):
            rotation_count += 1
    limit = args.get("limit")
    if limit is not None and rotation_count > limit:
        return f"Only {js_str(limit)} arrows will be rotated in-game."
    return False


GateSetup = create_rule("GATESETUP", "Incorrect gate setup", ValidationLevel.ERROR)


@GateSetup.set_fails
def _gate_setup_fails(context, args=None):
    board = context["board"]
    gate_space_indices = get_spaces_of_sub_type(SpaceSubtype.GATE, board)

    def _get_pointing_space_indices(pointed_at_index):
        pointing_indices = []
        for start_idx in get_link_start_indices(board):
            ends = get_connections(int(start_idx), board)
            for end in ends:
                if end == pointed_at_index:
                    pointing_indices.append(int(start_idx))
        return pointing_indices

    for gate_space_index in gate_space_indices:
        # We want the gate to be on an invisible space.
        gate_space = board["spaces"][gate_space_index]
        if gate_space["type"] != Space.OTHER:
            return "Only invisible spaces can have gates."  # UI should prevent this pretty well

        # Check space/link structure after gate space.
        exiting_spaces = get_connections(gate_space_index, board)
        if len(exiting_spaces) != 1:
            return "A single path should leave a gate space."
        exit_space_index = exiting_spaces[0]
        exit_space = _space_at(board, exit_space_index)
        if not exit_space or exit_space["type"] != Space.OTHER:
            return "Space after a gate space must be invisible."
        if exit_space.get("subtype") == SpaceSubtype.GATE:
            return "Gate spaces must be 2 or more spaces apart."
        if len(_get_pointing_space_indices(exit_space_index)) != 1:
            return "A single path should connect to the space after a gate space."

        next_spaces = get_connections(exit_space_index, board)
        if len(next_spaces) != 1:
            return "A single path should leave the space after a gate space"
        next_space_index = next_spaces[0]
        next_space = _space_at(board, next_space_index)
        if next_space.get("subtype") == SpaceSubtype.GATE:
            return "Gate spaces must be 2 or more spaces apart."

        # Check space/link structure before gate space.
        entering_spaces = _get_pointing_space_indices(gate_space_index)
        if len(entering_spaces) != 1:
            return "A single path should connect to a gate space."
        entering_space_index = entering_spaces[0]
        entering_space = _space_at(board, entering_space_index)
        if not entering_space or entering_space["type"] != Space.OTHER:
            return "Space before a gate space must be invisible."
        if entering_space.get("subtype") == SpaceSubtype.GATE:
            return "Gate spaces must be 2 or more spaces apart."

        prev_spaces = _get_pointing_space_indices(entering_space_index)
        if len(prev_spaces) != 1:
            return "A single path should connect to the space before a gate space."
        # FIXME: This is broken.
        # if (prevSpaces[0].subtype === SpaceSubtype.GATE)
        #   return "Gate spaces must be 2 or more spaces apart.";

    return False


AdditionalBackgroundCodeIssue = create_rule(
    "ADDITIONALBGCODEISSUE", "Additional background code issue", ValidationLevel.ERROR)


@AdditionalBackgroundCodeIssue.set_fails
def _additional_bg_code_issue_fails(context, args=None):
    from ..events.additionalbg import test_additional_bg_code_with_game

    board = context["board"]
    bg_code = get_additional_background_code(board)
    if not bg_code:
        return False

    game = _romhandler().get_rom_game()
    failures = test_additional_bg_code_with_game(bg_code["code"], bg_code["language"], board, game)

    if failures:
        logger.error("%s", failures)
        return "The additional background code failed a test assembly."

    return False


GetAudioIndexCodeIssue = create_rule(
    "GETAUDIOINDEXCODEISSUE", "Audio selection code issue", ValidationLevel.ERROR)


@GetAudioIndexCodeIssue.set_fails
def _get_audio_index_code_issue_fails(context, args=None):
    from ..events.getaudiochoice import test_get_audio_code_with_game

    board = context["board"]
    code = get_audio_select_code(board)
    if not code:
        return False

    game = _romhandler().get_rom_game()
    failures = test_get_audio_code_with_game(code["code"], code["language"], board, game)

    if failures:
        logger.error("%s", failures)
        return "The music selection code failed a test assembly."

    return False


AudioDetailsIssue = create_rule("AUDIODETAILSISSUE", "Audio details issue", ValidationLevel.ERROR)


@AudioDetailsIssue.set_fails
def _audio_details_issue_fails(context, args=None):
    board = context["board"]
    audio_type = board.get("audioType")
    if not _is_number(audio_type):
        return "Expected audioType to be defined."

    if audio_type == BoardAudioType.InGame:
        if not _is_number(board.get("audioIndex")):
            return "Expected an audio track index to be defined."
        # TODO: Validate range of audio index?

    elif audio_type == BoardAudioType.Custom:
        audio_data = board.get("audioData")
        if not audio_data and not isinstance(audio_data, (list, dict)):
            return "Expected custom audio data to be defined."
        if not isinstance(audio_data, list):
            return "Expected custom audio data to be an array."
        if not len(audio_data):
            return "Custom audio was chosen, but a midi file was not uploaded."

        from ..audio.midi import create_game_midi
        from ..utils.arrays import data_url_to_array_buffer

        audio = _romhandler().get_rom().get_audio()
        for audio_entry in audio_data:
            soundbank_index = audio_entry.get("soundbankIndex")
            seq_table = audio.get_sequence_table(0)
            bank_count = len(seq_table.soundbanks.banks)
            # (A missing index compares false both ways in JavaScript.)
            if _is_number(soundbank_index) and (soundbank_index < 0 or soundbank_index >= bank_count):
                return f"Soundbank index for custom audio is out of range (0 - {bank_count - 1})"

            if not audio_entry.get("data"):
                return "Custom audio was chosen, but a midi file was not uploaded."
            try:
                midi_buffer = data_url_to_array_buffer(audio_entry["data"])
            except Exception:
                return "Custom audio midi data could not be parsed into an ArrayBuffer."

            try:
                game_midi = create_game_midi(midi_buffer, {"loop": True})
            except Exception:
                return "Custom audio midi data could not be converted into game audio."
            if not game_midi:
                return "Custom audio midi data could not be converted into game audio."

    return False
