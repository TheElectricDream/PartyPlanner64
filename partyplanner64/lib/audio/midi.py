"""Game MIDI <-> standard MIDI conversion (port of audio/midi.ts).

The parsing here is shamelessly derived from Subdrag's
N64SoundTools / N64MidiTool MidiParse.cpp

https://github.com/derselbst/N64SoundTools/blob/master/N64MidiTool/N64MidiLibrary/MidiParse.cpp#L296

The output is byte-identical to the TypeScript, including its quirks (for
instance _write_vl_bytes writes only three bytes of a four-byte length, as
the original did). JavaScript's 32-bit bit operations are reproduced with
_i32.
"""

import logging

from ..utils.dataview import DataView
from ..utils.debug import assert_

logger = logging.getLogger("partyplanner64")

LENGTH_HEADER = 0x44
MIDI_HEADER_MAGIC = 0x4D546864  # MThd
MIDI_TRACK_MAGIC = 0x4D54726B  # MTrk

_MAX_TRACK_EVENTS = 0x30000


def _i32(x):
    """ToInt32, as JavaScript applies before bit operations."""
    return ((int(x) + 0x80000000) & 0xFFFFFFFF) - 0x80000000


class _Refs:
    __slots__ = ("alt_pattern", "alt_offset", "alt_length", "position", "original")

    def __init__(self, position, original):
        self.alt_pattern = None
        self.alt_offset = 0
        self.alt_length = 0
        self.position = position
        self.original = original


class TrackEvent:
    __slots__ = ("obsolete_event", "delta_time", "duration_time", "absolute_time", "type",
                 "contents", "content_size")

    def __init__(self):
        self.obsolete_event = False
        self.delta_time = 0
        self.duration_time = 0
        self.absolute_time = 0
        self.type = 0x00
        self.contents = None
        self.content_size = 0


class _OutBuffer:
    """A DataView-like writer over a bytearray that grows as needed."""

    def __init__(self, size):
        self.buffer = bytearray(size)

    def _ensure(self, end):
        if end > len(self.buffer):
            self.buffer.extend(bytes(max(end - len(self.buffer), len(self.buffer))))

    def set_uint8(self, offset, value):
        self._ensure(offset + 1)
        # DataView.setUint8(undefined) writes 0.
        self.buffer[offset] = 0 if value is None else int(value) & 0xFF

    def set_uint16(self, offset, value):
        self._ensure(offset + 2)
        value = int(value) & 0xFFFF
        self.buffer[offset] = value >> 8
        self.buffer[offset + 1] = value & 0xFF

    def set_uint32(self, offset, value):
        self._ensure(offset + 4)
        self.buffer[offset:offset + 4] = (int(value) & 0xFFFFFFFF).to_bytes(4, "big")

    def get_uint8(self, offset):
        return self.buffer[offset]


def _ensure_view(view):
    if isinstance(view, DataView):
        return view
    return DataView(view)


def parse_game_midi(in_view, input_size):
    """This parses an entry of MIDI data that the S2 structure contains.

    Args:
        in_view: A DataView (or bytes) of the game MIDI.
        input_size: Its length.

    Returns:
        A standard MIDI file (bytearray).
    """
    in_view = _ensure_view(in_view)
    # TODO: inputs?
    use_pitch_bend_sensitity = False
    pitch_bend_sensitity = 0
    extend_tracks_to_highest = False

    out_view = _OutBuffer(100000)  # TODO: How big?

    track_count = _get_track_count(in_view)
    division = in_view.get_uint32(0x40)
    _write_midi_header(out_view, track_count, division)

    out_pos = 14

    num_instruments = 0
    highest_track_length = 0
    for i in range(0, LENGTH_HEADER - 4, 4):
        absolute_time = 0
        offset = in_view.get_uint32(i)
        if offset == 0:
            continue

        previous_event_value = 0
        loop_ends_with_count = {}

        refs = _Refs(offset, -1)

        end_flag = False
        while refs.position < input_size and not end_flag:
            refs.original = -1
            time_tag = _get_vl_bytes(in_view, refs, True)

            absolute_time += time_tag
            if absolute_time > highest_track_length:
                highest_track_length = absolute_time

            event_val = _read_midi_byte(in_view, refs, True)
            status_bit = event_val < 0x80

            if event_val == 0xFF or (status_bit and previous_event_value == 0xFF):
                # meta event
                if status_bit:
                    sub_type = event_val
                else:
                    sub_type = _read_midi_byte(in_view, refs, True)

                if sub_type == 0x51:
                    # tempo
                    _read_midi_byte(in_view, refs, True)
                    _read_midi_byte(in_view, refs, True)
                    _read_midi_byte(in_view, refs, True)
                elif sub_type == 0x2D:
                    # end loop
                    loop_count = _read_midi_byte(in_view, refs, True)
                    _read_midi_byte(in_view, refs, True)  # currentLoopCount
                    offset_to_beginning_loop = _read_loop_offset(in_view, refs)

                    if loop_count == 0xFF or loop_count == 0x00:
                        break
                    else:
                        if refs.position in loop_ends_with_count:
                            count_left = loop_ends_with_count[refs.position]
                            if count_left == 0:
                                del loop_ends_with_count[refs.position]
                            else:
                                loop_ends_with_count[refs.position] = count_left - 1
                        else:
                            loop_ends_with_count[refs.position] = loop_count - 1

                        if refs.alt_pattern is None:
                            refs.position = refs.position - offset_to_beginning_loop
                        else:
                            loop_ends_with_count.pop(refs.position, None)
                elif sub_type == 0x2E:
                    # start loop
                    _read_midi_byte(in_view, refs, True)  # loopNumber
                    _read_midi_byte(in_view, refs, True)  # endLoop, Always FF
                elif sub_type == 0x2F:
                    end_flag = True

                if not status_bit:
                    previous_event_value = event_val
            elif (0x90 <= event_val < 0xA0) or (status_bit and 0x90 <= previous_event_value < 0xA0):
                if not status_bit:
                    _read_midi_byte(in_view, refs, True)  # noteNumber
                _read_midi_byte(in_view, refs, True)  # velocity
                _get_vl_bytes(in_view, refs, True)  # timeDuration

                if not status_bit:
                    previous_event_value = event_val
            elif (0xB0 <= event_val < 0xC0) or (status_bit and 0xB0 <= previous_event_value < 0xC0):
                # controller change
                if not status_bit:
                    _read_midi_byte(in_view, refs, True)  # controllerType
                _read_midi_byte(in_view, refs, True)  # controllerValue

                if not status_bit:
                    previous_event_value = event_val
            elif (0xC0 <= event_val < 0xD0) or (status_bit and 0xC0 <= previous_event_value < 0xD0):
                # change instrument
                if not status_bit:
                    _read_midi_byte(in_view, refs, True)  # instrument
                    previous_event_value = event_val
            elif (0xD0 <= event_val < 0xE0) or (status_bit and 0xD0 <= previous_event_value < 0xE0):
                # channel aftertouch
                if not status_bit:
                    _read_midi_byte(in_view, refs, True)  # amount
                    previous_event_value = event_val
            elif (0xE0 <= event_val < 0xF0) or (status_bit and 0xE0 <= previous_event_value < 0xF0):
                # pitch bend
                if not status_bit:
                    _read_midi_byte(in_view, refs, True)  # valueLSB
                _read_midi_byte(in_view, refs, True)  # valueMSB

                if not status_bit:
                    previous_event_value = event_val
            elif event_val == 0xFE:
                # repeat operation
                # should not be here...
                # no prev event set
                pass

    # Second loop over tracks.
    for i in range(0, LENGTH_HEADER - 4, 4):
        absolute_time = 0
        channel_status = 0xB0 | ((i // 4) & 0xF)

        events = []  # trackEventsSub; events[count] is the slot being filled.
        count = 0

        def slot(k):
            while len(events) <= k:
                events.append(TrackEvent())
            return events[k]

        offset = in_view.get_uint32(i)

        if offset != 0:
            out_view.set_uint32(out_pos, 0x4D54726B)  # MTrk
            out_pos += 4

            previous_event_value = 0

            loop_ends_with_count = {}
            loop_numbers = []

            refs = _Refs(offset, -1)

            end_flag = False

            if use_pitch_bend_sensitity:
                # https://www.midikits.net/midi_analyser/pitch_bend.htm
                if pitch_bend_sensitity > 0x18:
                    pitch_bend_sensitity = 0x18
                for controller, value in ((0x64, 0x00), (0x65, 0x00), (0x06, pitch_bend_sensitity),
                                          (0x64, 0x7F), (0x65, 0x7F)):
                    ev = slot(count)
                    ev.type = channel_status
                    ev.content_size = 2
                    ev.contents = [controller, value]
                    count += 1

            while refs.position < input_size and not end_flag:
                if extend_tracks_to_highest:
                    if absolute_time >= highest_track_length:
                        ev = slot(count)
                        ev.absolute_time = highest_track_length
                        ev.delta_time = highest_track_length - absolute_time
                        ev.type = 0xFF
                        ev.content_size = 2
                        ev.contents = [0x2F, 0x0]
                        count += 1
                        end_flag = True
                        break

                if count >= _MAX_TRACK_EVENTS:
                    logger.error("Overflow? trackEventCountSub >= 0x30000")
                    return _overflow_result(out_view)

                refs.original = -1
                # trackEventsSub[trackEventCountSub].deltaTime is for loops
                time_tag = _get_vl_bytes(in_view, refs, True)

                if extend_tracks_to_highest:
                    if absolute_time + time_tag > highest_track_length:
                        ev = slot(count)
                        ev.absolute_time = highest_track_length
                        ev.delta_time = highest_track_length - absolute_time
                        ev.type = 0xFF
                        ev.content_size = 2
                        ev.contents = [0x2F, 0x0]
                        count += 1
                        end_flag = True
                        break

                cur = slot(count)
                cur.delta_time += time_tag

                absolute_time += time_tag
                cur.absolute_time = absolute_time

                event_val = _read_midi_byte(in_view, refs, True)

                status_bit = event_val < 0x80

                if event_val == 0xFF or (status_bit and previous_event_value == 0xFF):
                    # meta event
                    if status_bit:
                        sub_type = event_val
                    else:
                        sub_type = _read_midi_byte(in_view, refs, True)

                    if sub_type == 0x51:
                        # tempo
                        b0 = _read_midi_byte(in_view, refs, True)
                        b1 = _read_midi_byte(in_view, refs, True)
                        b2 = _read_midi_byte(in_view, refs, True)
                        microseconds_since_quarter_note = _i32(_i32(_i32(b0 << 8) | b1) << 8) | b2

                        cur.type = 0xFF
                        cur.content_size = 5
                        cur.contents = [
                            0x51,
                            0x3,
                            (microseconds_since_quarter_note >> 16) & 0xFF,
                            (microseconds_since_quarter_note >> 8) & 0xFF,
                            (microseconds_since_quarter_note >> 0) & 0xFF,
                        ]
                        count += 1
                    elif sub_type == 0x2D:
                        # end loop
                        loop_number = 0
                        if len(loop_numbers) > 0:
                            loop_number = loop_numbers.pop()

                        # Fake loop end, controller 103
                        cur.type = channel_status
                        cur.content_size = 2
                        cur.contents = [103, loop_number]
                        count += 1

                        loop_count = _read_midi_byte(in_view, refs, True)
                        _read_midi_byte(in_view, refs, True)  # currentLoopCount
                        offset_to_beginning_loop = _read_loop_offset(in_view, refs)

                        if loop_count == 0xFF or loop_count == 0x00:
                            # hasLoopPoint = True; loopEnd = absoluteTime

                            if extend_tracks_to_highest:
                                if refs.alt_pattern is None:
                                    refs.position = refs.position - offset_to_beginning_loop
                        else:
                            if refs.position in loop_ends_with_count:
                                count_left = loop_ends_with_count[refs.position]

                                if count_left == 0:
                                    del loop_ends_with_count[refs.position]
                                else:
                                    loop_ends_with_count[refs.position] = count_left - 1
                            else:
                                loop_ends_with_count[refs.position] = loop_count - 1

                            if refs.alt_pattern is None:
                                refs.position = refs.position - offset_to_beginning_loop
                            else:
                                loop_ends_with_count.pop(refs.position, None)
                    elif sub_type == 0x2E:
                        # start loop
                        loop_number = _read_midi_byte(in_view, refs, True)
                        _read_midi_byte(in_view, refs, True)  # endLoop, Always FF
                        # hasLoopPoint = True; loopStart = absoluteTime

                        # Fake loop start, controller 102
                        cur.type = channel_status
                        cur.content_size = 2
                        cur.contents = [102, loop_number]
                        count += 1

                        loop_numbers.append(loop_number)
                    elif sub_type == 0x2F:
                        cur.type = 0xFF
                        cur.content_size = 2
                        cur.contents = [0x2F, 0x0]
                        count += 1

                        end_flag = True

                    if not status_bit:
                        previous_event_value = event_val
                elif (0x90 <= event_val < 0xA0) or (status_bit and 0x90 <= previous_event_value < 0xA0):
                    if status_bit:
                        cur.type = previous_event_value
                        note_number = event_val
                    else:
                        cur.type = event_val
                        note_number = _read_midi_byte(in_view, refs, True)
                    velocity = _read_midi_byte(in_view, refs, True)

                    time_duration = _get_vl_bytes(in_view, refs, True)

                    cur.duration_time = time_duration  # to be filled in
                    cur.content_size = 2
                    cur.contents = [note_number, velocity]

                    count += 1

                    if not status_bit:
                        previous_event_value = event_val
                elif (0xB0 <= event_val < 0xC0) or (status_bit and 0xB0 <= previous_event_value < 0xC0):
                    # controller change
                    if status_bit:
                        controller_type = event_val
                        cur.type = previous_event_value
                    else:
                        controller_type = _read_midi_byte(in_view, refs, True)
                        cur.type = event_val
                    controller_value = _read_midi_byte(in_view, refs, True)

                    cur.content_size = 2
                    cur.contents = [controller_type, controller_value]

                    count += 1

                    if not status_bit:
                        previous_event_value = event_val
                elif (0xC0 <= event_val < 0xD0) or (status_bit and 0xC0 <= previous_event_value < 0xD0):
                    # change instrument
                    if status_bit:
                        instrument = event_val
                        cur.type = previous_event_value
                    else:
                        instrument = _read_midi_byte(in_view, refs, True)
                        cur.type = event_val

                    cur.content_size = 1
                    cur.contents = [instrument]
                    if instrument >= num_instruments:
                        num_instruments = instrument + 1

                    count += 1

                    if not status_bit:
                        previous_event_value = event_val
                elif (0xD0 <= event_val < 0xE0) or (status_bit and 0xD0 <= previous_event_value < 0xE0):
                    # channel aftertouch
                    if status_bit:
                        amount = event_val
                        cur.type = previous_event_value
                    else:
                        amount = _read_midi_byte(in_view, refs, True)
                        cur.type = event_val

                    cur.content_size = 1
                    cur.contents = [amount]

                    count += 1

                    if not status_bit:
                        previous_event_value = event_val
                elif (0xE0 <= event_val < 0xF0) or (status_bit and 0xE0 <= previous_event_value < 0xF0):
                    # pitch bend
                    if status_bit:
                        value_lsb = event_val
                        cur.type = previous_event_value
                    else:
                        value_lsb = _read_midi_byte(in_view, refs, True)
                        cur.type = event_val

                    value_msb = _read_midi_byte(in_view, refs, True)

                    cur.content_size = 2
                    cur.contents = [value_lsb, value_msb]

                    count += 1

                    if not status_bit:
                        previous_event_value = event_val
                elif event_val == 0xFE:
                    # repeat operation
                    # should not be here...
                    # no prev event set
                    pass
                else:
                    logger.error("%s ERROR MISSING PARSE OF TYPE", event_val)

            # Split note durations out into note offs (a note on with velocity 0).
            # Inserting at index e is what the TypeScript did by shifting the
            # events after e up one slot (the inserted event keeps the
            # obsoleteEvent flag of the event it displaced).
            event_count = 0
            while event_count < count:
                if count >= _MAX_TRACK_EVENTS:
                    logger.error("Overflow 2? trackEventCountSub >= 0x30000")
                    return _overflow_result(out_view)

                track_event = events[event_count]
                if 0x90 <= track_event.type < 0xA0:
                    # need to split out
                    if track_event.duration_time > 0:
                        shutoff_time = track_event.absolute_time + track_event.duration_time
                        if event_count != count - 1:
                            for e in range(event_count + 1, count):
                                if (events[e].absolute_time >= shutoff_time and e != count - 1) \
                                        or e == count - 1:
                                    note_off = TrackEvent()
                                    note_off.type = track_event.type
                                    note_off.absolute_time = shutoff_time
                                    note_off.delta_time = shutoff_time - events[e - 1].absolute_time
                                    note_off.content_size = track_event.content_size
                                    note_off.duration_time = 0
                                    note_off.contents = [None] * note_off.content_size
                                    note_off.contents[0] = track_event.contents[0]
                                    note_off.contents[1] = 0
                                    note_off.obsolete_event = events[e].obsolete_event
                                    events.insert(e, note_off)

                                    events[e + 1].delta_time = \
                                        events[e + 1].absolute_time - note_off.absolute_time

                                    count += 1
                                    break
                        else:
                            if event_count == 0:
                                # trackEventsSub[-1] is undefined in the TypeScript.
                                raise TypeError("Cannot read properties of undefined "
                                                "(reading 'absoluteTime')")
                            # The note is the last event: it is copied one slot up, and its
                            # slot becomes a note off whose note number was lost (undefined).
                            note_off = TrackEvent()
                            note_off.type = track_event.type
                            note_off.absolute_time = shutoff_time
                            note_off.delta_time = shutoff_time - events[event_count - 1].absolute_time
                            note_off.content_size = track_event.content_size
                            note_off.duration_time = 0
                            note_off.contents = [None] * note_off.content_size
                            note_off.contents[1] = 0
                            note_off.obsolete_event = track_event.obsolete_event
                            events.insert(event_count, note_off)

                            events[event_count + 1].delta_time = \
                                events[event_count + 1].absolute_time - note_off.absolute_time
                            count += 1
                event_count += 1

            time_offset = 0

            size_data = 0
            previous_track_event = 0x0

            for j in range(count):
                track_event = events[j]
                if track_event.obsolete_event:
                    time_offset += track_event.delta_time
                else:
                    _time_delta, length_time_delta = _return_vl_bytes(
                        track_event.delta_time + time_offset)
                    time_offset = 0

                    size_data += length_time_delta

                    if track_event.type != previous_track_event or track_event.type == 0xFF:
                        size_data += 1

                    size_data += track_event.content_size

                    previous_track_event = track_event.type

            out_view.set_uint32(out_pos, size_data)
            out_pos += 4

            time_offset = 0
            previous_track_event = 0x0
            for j in range(count):
                track_event = events[j]

                if track_event.obsolete_event:
                    time_offset += track_event.delta_time
                else:
                    time_delta, length_time_delta = _return_vl_bytes(
                        track_event.delta_time + time_offset)
                    time_offset = 0
                    out_pos = _write_vl_bytes(out_view, out_pos, time_delta, length_time_delta, True)

                    if track_event.type != previous_track_event or track_event.type == 0xFF:
                        out_view.set_uint8(out_pos, track_event.type)
                        out_pos += 1

                    for z in range(track_event.content_size):
                        out_view.set_uint8(out_pos, track_event.contents[z])
                        out_pos += 1

                    previous_track_event = track_event.type

    return bytearray(out_view.buffer[:out_pos])


def _overflow_result(out_view):
    # The TypeScript returned its whole (100000 byte) output buffer.
    return bytearray(out_view.buffer[:100000])


def _read_loop_offset(in_view, refs):
    b0 = _read_midi_byte(in_view, refs, False)
    b1 = _read_midi_byte(in_view, refs, False)
    b2 = _read_midi_byte(in_view, refs, False)
    b3 = _read_midi_byte(in_view, refs, False)
    return _i32(_i32(_i32(_i32(_i32(b0 << 8) | b1) << 8) | b2) << 8) | b3


def create_game_midi(midi_file, options=None):
    """Converts a normal midi file to a midi that can be put in the game.

    https://github.com/derselbst/N64SoundTools/blob/master/N64MidiTool/N64MidiLibrary/MidiParse.cpp#L12837

    Args:
        midi_file: Normal midi file (bytes).
        options: {"loop": bool} (optional).

    Returns:
        The game midi (bytearray), or None if the file couldn't be processed.
    """
    loop = bool((options or {}).get("loop", False))
    loop_point = 0

    track_event_count = [0] * 32
    track_events = [[] for _ in range(32)]

    def set_event(track_num, index, event):
        lst = track_events[track_num]
        while len(lst) <= index:
            lst.append(None)
        lst[index] = event
        return event

    def get_event(track_num, index):
        lst = track_events[track_num]
        if index < 0 or index >= len(lst) or lst[index] is None:
            raise TypeError("Cannot read properties of undefined")
        return lst[index]

    data_view = DataView(bytes(midi_file))
    midi_file_byte_length = data_view.byte_length

    if data_view.get_uint32(0) != MIDI_HEADER_MAGIC:
        return None

    type_ = data_view.get_uint16(8)
    num_tracks = data_view.get_uint16(10)
    tempo = data_view.get_uint16(12)

    if num_tracks > 16:
        logger.info("Too many tracks, truncating to 16.")
        num_tracks = 16

    if type_ != 0 and type_ != 1:
        logger.info("Invalid midi type")
        return None

    refs = _Refs(0xE, 0)
    unknowns_hit = False

    highest_absolute_time = 0
    highest_absolute_time_by_track = [0] * 16

    for track_num in range(num_tracks):
        absolute_time = 0

        if data_view.get_uint32(refs.position) != MIDI_TRACK_MAGIC:
            logger.info("Invalid track midi header")
            return None

        refs.position += 8

        previous_event_value = 0xFF
        end_flag = False

        while not end_flag and refs.position < midi_file_byte_length:
            refs.original = 0
            time_tag = _get_vl_bytes(data_view, refs, False)
            absolute_time += time_tag

            event_val = _read_midi_byte(data_view, refs, False)
            status_bit = event_val <= 0x7F

            if event_val == 0xFF:
                # meta event.
                sub_type = _read_midi_byte(data_view, refs, False)

                if sub_type == 0x2F:
                    # End of Track Event.
                    absolute_time -= time_tag
                    end_flag = True
                    _read_midi_byte(data_view, refs, False)  # end 00 in real mid
                elif sub_type == 0x51:
                    # Set Tempo Event.
                    _read_midi_byte(data_view, refs, False)
                    _read_midi_byte(data_view, refs, False)
                    _read_midi_byte(data_view, refs, False)
                    _read_midi_byte(data_view, refs, False)
                elif sub_type < 0x7F and not (sub_type == 0x51 or sub_type == 0x2F):
                    # Various Unused Meta Events.
                    length = _get_vl_bytes(data_view, refs, False)  # Was _readMidiByte in Subdrag code.
                    for _ in range(length):
                        _read_midi_byte(data_view, refs, False)
                elif sub_type == 0x7F:
                    # Unused Sequencer Specific Event
                    length = _get_vl_bytes(data_view, refs, False)
                    for _ in range(length):
                        _read_midi_byte(data_view, refs, False)

                previous_event_value = event_val
            elif (0x80 <= event_val < 0x90) or (status_bit and 0x80 <= previous_event_value < 0x90):
                if not status_bit:
                    _read_midi_byte(data_view, refs, False)  # noteNumber
                _read_midi_byte(data_view, refs, False)  # velocity
                if not status_bit:
                    previous_event_value = event_val
            elif (0x90 <= event_val < 0xA0) or (status_bit and 0x90 <= previous_event_value < 0xA0):
                if not status_bit:
                    _read_midi_byte(data_view, refs, False)  # noteNumber
                _read_midi_byte(data_view, refs, False)  # velocity
                if not status_bit:
                    previous_event_value = event_val
            elif (0xB0 <= event_val < 0xC0) or (status_bit and 0xB0 <= previous_event_value < 0xC0):
                # controller change
                if not status_bit:
                    _read_midi_byte(data_view, refs, False)  # controllerType
                _read_midi_byte(data_view, refs, False)  # controllerValue
                if not status_bit:
                    previous_event_value = event_val
            elif (0xC0 <= event_val < 0xD0) or (status_bit and 0xC0 <= previous_event_value < 0xD0):
                # change instrument
                if not status_bit:
                    _read_midi_byte(data_view, refs, False)  # instrument
                    previous_event_value = event_val
            elif (0xD0 <= event_val < 0xE0) or (status_bit and 0xD0 <= previous_event_value < 0xE0):
                # channel aftertouch
                if not status_bit:
                    _read_midi_byte(data_view, refs, False)  # amount
                    previous_event_value = event_val
            elif (0xE0 <= event_val < 0xF0) or (status_bit and 0xE0 <= previous_event_value < 0xF0):
                # pitch bend
                if not status_bit:
                    _read_midi_byte(data_view, refs, False)  # valueLSB
                _read_midi_byte(data_view, refs, False)  # valueMSB
                if not status_bit:
                    previous_event_value = event_val
            elif event_val == 0xF0 or event_val == 0xF7:
                length = _get_vl_bytes(data_view, refs, False)
                # subtract length
                for _ in range(length):
                    _read_midi_byte(data_view, refs, False)
            else:
                if not unknowns_hit:
                    logger.warning("Invalid midi character found")
                    unknowns_hit = True

        if absolute_time > highest_absolute_time:
            highest_absolute_time = absolute_time
        if absolute_time > highest_absolute_time_by_track[track_num]:
            highest_absolute_time_by_track[track_num] = absolute_time

    refs = _Refs(0xE, 0)

    for track_num in range(num_tracks):
        absolute_time = 0
        if data_view.get_uint32(refs.position) != MIDI_TRACK_MAGIC:
            logger.info("Invalid track midi header")
            return None

        refs.position += 8

        previous_event_value = 0xFF
        end_flag = False
        did_loop = False

        if loop and loop_point == 0 and highest_absolute_time_by_track[track_num] > 0:
            new_track_event = set_event(track_num, track_event_count[track_num], TrackEvent())
            new_track_event.type = 0xFF
            new_track_event.absolute_time = 0
            new_track_event.content_size = 3
            new_track_event.contents = [0x2E, 0x00, 0xFF]
            new_track_event.delta_time = 0
            new_track_event.obsolete_event = False

            track_event_count[track_num] += 1
            did_loop = True

        while not end_flag and refs.position < midi_file_byte_length:
            refs.original = 0
            time_tag = _get_vl_bytes(data_view, refs, False)
            absolute_time += time_tag

            new_track_event = set_event(track_num, track_event_count[track_num], TrackEvent())
            new_track_event.delta_time = time_tag
            new_track_event.obsolete_event = False
            new_track_event.contents = None
            new_track_event.absolute_time = absolute_time

            if loop and not did_loop and highest_absolute_time_by_track[track_num] > loop_point:
                if absolute_time == loop_point:
                    new_track_event.type = 0xFF
                    new_track_event.absolute_time = absolute_time
                    new_track_event.content_size = 3
                    new_track_event.contents = [0x2E, 0x00, 0xFF]
                    new_track_event.delta_time = time_tag
                    new_track_event.obsolete_event = False

                    track_event_count[track_num] += 1

                    new_track_event = set_event(track_num, track_event_count[track_num], TrackEvent())
                    new_track_event.delta_time = time_tag
                    new_track_event.obsolete_event = False
                    new_track_event.contents = None
                    new_track_event.absolute_time = absolute_time

                    did_loop = True
                elif absolute_time > loop_point:
                    new_track_event.type = 0xFF
                    new_track_event.absolute_time = loop_point
                    new_track_event.content_size = 3
                    new_track_event.contents = [0x2E, 0x00, 0xFF]
                    if track_event_count[track_num] > 0:
                        new_track_event.delta_time = loop_point - get_event(
                            track_num, track_event_count[track_num] - 1).absolute_time
                    else:
                        new_track_event.delta_time = loop_point
                    new_track_event.obsolete_event = False

                    track_event_count[track_num] += 1

                    new_track_event = set_event(track_num, track_event_count[track_num], TrackEvent())
                    new_track_event.delta_time = absolute_time - loop_point
                    new_track_event.obsolete_event = False
                    new_track_event.contents = None
                    new_track_event.absolute_time = absolute_time

                    did_loop = True

            event_val = _read_midi_byte(data_view, refs, False)
            status_bit = event_val <= 0x7F
            if event_val == 0xFF:
                sub_type = _read_midi_byte(data_view, refs, False)
                if sub_type == 0x2F:
                    end_flag = True
                    if loop and highest_absolute_time_by_track[track_num] > loop_point:
                        prev_event = get_event(track_num, track_event_count[track_num] - 1)
                        if prev_event.type == 0xFF and prev_event.content_size > 0 \
                                and prev_event.contents[0] == 0x2E:
                            new_track_event = prev_event
                            new_track_event.type = 0xFF
                            new_track_event.content_size = 1
                            new_track_event.contents = [0x2F]
                        else:
                            new_track_event_last = set_event(
                                track_num, track_event_count[track_num] + 1, TrackEvent())
                            new_track_event_last.absolute_time = highest_absolute_time
                            new_track_event_last.delta_time = 0
                            new_track_event_last.duration_time = new_track_event.duration_time
                            new_track_event_last.obsolete_event = new_track_event.obsolete_event

                            new_track_event_last.type = 0xFF
                            new_track_event_last.content_size = 1
                            new_track_event_last.contents = [0x2F]

                            new_track_event.type = 0xFF
                            if highest_absolute_time > prev_event.absolute_time + prev_event.duration_time:
                                new_track_event.delta_time = highest_absolute_time - (
                                    prev_event.absolute_time + prev_event.duration_time)
                                new_track_event.absolute_time = highest_absolute_time
                            else:
                                new_track_event.delta_time = 0
                                new_track_event.absolute_time = prev_event.absolute_time

                            new_track_event.content_size = 7
                            new_track_event.contents = [
                                0x2D,
                                0xFF,
                                0xFF,
                                0x0,  # todo write location
                                0x0,
                                0x0,
                                0x0,
                            ]
                            new_track_event.obsolete_event = False

                            track_event_count[track_num] += 1
                    else:
                        new_track_event.type = 0xFF
                        new_track_event.content_size = 1
                        new_track_event.contents = [0x2F]

                    _read_midi_byte(data_view, refs, False)  # end 00 in real midi
                elif sub_type == 0x51:
                    _read_midi_byte(data_view, refs, False)  # length

                    new_track_event.type = 0xFF
                    new_track_event.content_size = 4
                    t0 = _read_midi_byte(data_view, refs, False)
                    t1 = _read_midi_byte(data_view, refs, False)
                    t2 = _read_midi_byte(data_view, refs, False)
                    new_track_event.contents = [0x51, t0, t1, t2]
                elif sub_type < 0x7F and not (sub_type == 0x51 or sub_type == 0x2F):
                    new_track_event.type = 0xFF
                    length = _get_vl_bytes(data_view, refs, False)  # Was _readMidiByte in Subdrag code.
                    for _ in range(length):
                        _read_midi_byte(data_view, refs, False)
                    new_track_event.obsolete_event = True
                elif sub_type == 0x7F:
                    # Unused sequencer specific event.
                    new_track_event.type = 0xFF
                    length = _get_vl_bytes(data_view, refs, False)
                    for _ in range(length):
                        _read_midi_byte(data_view, refs, False)
                    new_track_event.obsolete_event = True

                previous_event_value = event_val
            elif (0x80 <= event_val < 0x90) or (status_bit and 0x80 <= previous_event_value < 0x90):
                if status_bit:
                    new_track_event.type = previous_event_value
                    note_number = event_val
                    cur_event_val = previous_event_value
                else:
                    new_track_event.type = event_val
                    note_number = _read_midi_byte(data_view, refs, False)
                    cur_event_val = event_val
                velocity = _read_midi_byte(data_view, refs, False)

                for test_backwards in range(track_event_count[track_num] - 1, -1, -1):
                    ev = get_event(track_num, test_backwards)
                    if ev.type == (0x90 | (cur_event_val & 0xF)) and not ev.obsolete_event:
                        if ev.contents[0] == note_number:
                            ev.duration_time = absolute_time - ev.absolute_time
                            break

                new_track_event.duration_time = 0
                new_track_event.content_size = 2
                new_track_event.contents = [note_number, velocity]
                new_track_event.obsolete_event = True

                if not status_bit:
                    previous_event_value = event_val
            elif (0x90 <= event_val < 0xA0) or (status_bit and 0x90 <= previous_event_value < 0xA0):
                if status_bit:
                    new_track_event.type = previous_event_value
                    note_number = event_val
                    cur_event_val = previous_event_value
                else:
                    new_track_event.type = event_val
                    note_number = _read_midi_byte(data_view, refs, False)
                    cur_event_val = event_val
                velocity = _read_midi_byte(data_view, refs, False)

                if velocity == 0:
                    # simulate note off
                    for test_backwards in range(track_event_count[track_num] - 1, -1, -1):
                        ev = get_event(track_num, test_backwards)
                        if ev.type == cur_event_val and not ev.obsolete_event:
                            if ev.contents[0] == note_number:
                                ev.duration_time = absolute_time - ev.absolute_time
                                break

                    new_track_event.duration_time = 0
                    new_track_event.content_size = 2
                    new_track_event.contents = [note_number, velocity]
                    new_track_event.obsolete_event = True
                else:
                    # check if no note off received, if so, turn it off and restart note
                    for test_backwards in range(track_event_count[track_num] - 1, -1, -1):
                        ev = get_event(track_num, test_backwards)
                        if ev.type == cur_event_val and not ev.obsolete_event:
                            if ev.contents[0] == note_number:
                                if ev.duration_time == 0:
                                    # means unfinished note
                                    ev.duration_time = absolute_time - ev.absolute_time
                                break

                    new_track_event.duration_time = 0  # to be filled in
                    new_track_event.content_size = 2
                    new_track_event.contents = [note_number, velocity]

                if not status_bit:
                    previous_event_value = event_val
            elif (0xB0 <= event_val < 0xC0) or (status_bit and 0xB0 <= previous_event_value < 0xC0):
                # controller change
                if status_bit:
                    controller_type = event_val
                    new_track_event.type = previous_event_value
                else:
                    controller_type = _read_midi_byte(data_view, refs, False)
                    new_track_event.type = event_val

                controller_value = _read_midi_byte(data_view, refs, False)

                new_track_event.content_size = 2
                new_track_event.contents = [controller_type, controller_value]

                if not status_bit:
                    previous_event_value = event_val
            elif (0xC0 <= event_val < 0xD0) or (status_bit and 0xC0 <= previous_event_value < 0xD0):
                # change instrument
                if status_bit:
                    instrument = event_val
                    new_track_event.type = previous_event_value
                else:
                    instrument = _read_midi_byte(data_view, refs, False)
                    new_track_event.type = event_val

                # (Drums in GM, channel 9, keep their instrument too.)

                new_track_event.content_size = 1
                new_track_event.contents = [instrument]

                if not status_bit:
                    previous_event_value = event_val
            elif (0xD0 <= event_val < 0xE0) or (status_bit and 0xD0 <= previous_event_value < 0xE0):
                # channel aftertouch
                if status_bit:
                    amount = event_val
                    new_track_event.type = previous_event_value
                else:
                    amount = _read_midi_byte(data_view, refs, False)
                    new_track_event.type = event_val

                new_track_event.content_size = 1
                new_track_event.contents = [amount]
                # newTrackEvent.obsoleteEvent = true; // temporary?

                if not status_bit:
                    previous_event_value = event_val
            elif (0xE0 <= event_val < 0xF0) or (status_bit and 0xE0 <= previous_event_value < 0xF0):
                # pitch bend
                if status_bit:
                    value_lsb = event_val
                    new_track_event.type = previous_event_value
                else:
                    value_lsb = _read_midi_byte(data_view, refs, False)
                    new_track_event.type = event_val

                value_msb = _read_midi_byte(data_view, refs, False)

                new_track_event.content_size = 2
                new_track_event.contents = [value_lsb, value_msb]
                # newTrackEvent.obsoleteEvent = true; // temporary?

                if not status_bit:
                    previous_event_value = event_val
            elif event_val == 0xF0 or event_val == 0xF7:
                new_track_event.type = event_val
                length = _get_vl_bytes(data_view, refs, False)
                # subtract length
                for _ in range(length):
                    _read_midi_byte(data_view, refs, False)

                new_track_event.obsolete_event = True
            else:
                if not unknowns_hit:
                    logger.error("Invalid midi character found")
                    unknowns_hit = True

            track_event_count[track_num] += 1

    out_view = _OutBuffer(0x100000)  # TOOD: What size?
    out_pos = 0

    time_offset = 0
    start_position = 0x44
    for i in range(num_tracks):
        size_data = 0
        loop_start_position = 0
        previous_track_event = 0

        if track_event_count[i] > 0:
            out_view.set_uint32(out_pos, start_position)
            out_pos += 4

            for j in range(track_event_count[i]):
                track_event = get_event(i, j)
                _time_delta, length_time_delta = _return_vl_bytes(track_event.delta_time + time_offset)

                if track_event.obsolete_event:
                    time_offset += track_event.delta_time
                else:
                    if track_event.type == 0xFF and track_event.contents[0] == 0x2E:
                        loop_start_position = (start_position + size_data + 1
                                               + track_event.content_size + length_time_delta)

                    time_offset = 0
                    size_data += length_time_delta

                    if track_event.type == 0xFF and track_event.contents[0] == 0x2D:
                        offset_back = start_position + size_data - loop_start_position + 8
                        track_event.contents[3] = (_i32(offset_back) >> 24) & 0xFF
                        track_event.contents[4] = (_i32(offset_back) >> 16) & 0xFF
                        track_event.contents[5] = (_i32(offset_back) >> 8) & 0xFF
                        track_event.contents[6] = (_i32(offset_back) >> 0) & 0xFF

                    if track_event.type != previous_track_event or track_event.type == 0xFF:
                        size_data += 1

                    size_data += track_event.content_size

                    if 0x90 <= track_event.type < 0xA0:
                        _duration, length_duration_bytes = _return_vl_bytes(track_event.duration_time)
                        size_data += length_duration_bytes

                    previous_track_event = track_event.type
            start_position += size_data
        else:
            out_view.set_uint32(out_pos, 0)
            out_pos += 4

    for i in range(num_tracks, 16):
        out_view.set_uint32(out_pos, 0)
        out_pos += 4

    out_view.set_uint32(out_pos, tempo)
    out_pos += 4

    for i in range(num_tracks):
        if track_event_count[i] > 0:
            previous_track_event = 0
            for j in range(track_event_count[i]):
                track_event = get_event(i, j)
                if track_event.obsolete_event:
                    time_offset += track_event.delta_time
                else:
                    time_delta, length_time_delta = _return_vl_bytes(track_event.delta_time + time_offset)
                    time_offset = 0
                    out_pos = _write_vl_bytes(out_view, out_pos, time_delta, length_time_delta, False)

                    if track_event.type != previous_track_event or track_event.type == 0xFF:
                        out_view.set_uint8(out_pos, track_event.type)
                        out_pos += 1

                    # (copyRange of the contents)
                    for z in range(track_event.content_size):
                        out_view.set_uint8(out_pos + z, track_event.contents[z])
                    out_pos += track_event.content_size

                    if 0x90 <= track_event.type < 0xA0:
                        duration, length_duration_bytes = _return_vl_bytes(track_event.duration_time)
                        out_pos = _write_vl_bytes(out_view, out_pos, duration, length_duration_bytes, False)

                    previous_track_event = track_event.type

    in_array = bytearray(out_view.buffer[:out_pos])
    if len(in_array) < 0x40:
        raise IndexError("Offset is outside the bounds of the DataView")
    offsetheader = []
    extra_offsets = []
    for x in range(0, 0x40, 4):
        offsetheader.append(_i32(int.from_bytes(in_array[x:x + 4], "big")))
        extra_offsets.append(0)

    for x in range(0x45, out_pos):
        if in_array[x] == 0xFE:
            # need to write twice
            for y in range(num_tracks):
                if offsetheader[y] > x:
                    extra_offsets[y] += 1

    for x in range(16):
        in_array[x * 4:x * 4 + 4] = ((offsetheader[x] + extra_offsets[x]) & 0xFFFFFFFF).to_bytes(4, "big")

    out = bytearray()
    for x in range(out_pos):
        out.append(in_array[x])
        if x > 0x44:
            if in_array[x] == 0xFE:
                # need to write twice
                out.append(in_array[x])

    assert_(len(out) >= out_pos)

    # if (useRepeaters) // TODO?

    return out


def _get_track_count(in_view):
    """The start of the MIDI data in the ROM is a bunch of offsets to track data.

    This counts these offsets.
    """
    track_count = 0

    # -4 because the last number in the header is the "division"
    # which is not an offset.
    for i in range(0, LENGTH_HEADER - 4, 4):
        track_offset = in_view.get_uint32(i)

        # At some point the offsets end and there are zeroes.
        if track_offset != 0:
            track_count += 1
    return track_count


def _write_midi_header(out_view, track_count, division):
    # Write magic "MThd"
    out_view.set_uint32(0, 0x4D546864)
    # Write header length
    out_view.set_uint32(4, 0x00000006)
    # Write MIDI format, always 1 (multi-track)
    out_view.set_uint16(8, 1)
    # Write track count
    out_view.set_uint16(10, track_count)
    # Write division
    out_view.set_uint16(12, division)


def _start_repeat(in_view, refs, byte_at_position):
    repeat_first_byte = byte_at_position
    refs.position += 1

    repeat_distance_from_beginning_marker = (repeat_first_byte << 8) | in_view.get_uint8(refs.position)
    refs.position += 1
    repeat_count = in_view.get_uint8(refs.position)
    refs.position += 1

    alt_pattern_start = refs.position - 4 - repeat_distance_from_beginning_marker
    refs.alt_pattern = [in_view.get_uint8(copy)
                        for copy in range(alt_pattern_start, alt_pattern_start + repeat_count)]
    refs.alt_offset = 0
    refs.alt_length = repeat_count
    byte = refs.alt_pattern[refs.alt_offset] if repeat_count else None
    refs.alt_offset += 1
    return byte


def _get_vl_bytes(in_view, refs, include_fe_repeats):
    vl_val = 0
    temp_byte = 0

    while True:
        if refs.alt_pattern is not None:
            temp_byte = refs.alt_pattern[refs.alt_offset]
            refs.alt_offset += 1
            if refs.alt_offset == refs.alt_length:
                refs.alt_pattern = None
                refs.alt_offset = 0
                refs.alt_length = 0
        else:
            temp_byte = in_view.get_uint8(refs.position)
            refs.position += 1
            byte_at_position = in_view.get_uint8(refs.position)
            if include_fe_repeats and temp_byte == 0xFE:
                if byte_at_position != 0xFE:
                    temp_byte = _start_repeat(in_view, refs, byte_at_position)
                else:
                    # byteAtPosition === 0xFE
                    # Skip duplicate 0xFE
                    refs.position += 1

                if refs.alt_offset == refs.alt_length and refs.alt_pattern is not None:
                    refs.alt_pattern = None
                    refs.alt_offset = 0
                    refs.alt_length = 0

        if temp_byte >> 7 == 0x1:
            vl_val += temp_byte
            vl_val = _i32(_i32(vl_val) << 8)
        else:
            vl_val += temp_byte
            break

    refs.original = vl_val

    vlength = 0
    vl_val = _i32(vl_val)
    for c, a in ((0, 0), (8, 7), (16, 14), (24, 21)):
        vlength += ((vl_val >> c) & 0x7F) << a

    return vlength


def _read_midi_byte(in_view, refs, include_fe_repeats):
    if refs.alt_pattern is not None:
        return_byte = refs.alt_pattern[refs.alt_offset]
        refs.alt_offset += 1
    else:
        return_byte = in_view.get_uint8(refs.position)
        refs.position += 1

        if include_fe_repeats and return_byte == 0xFE:
            byte_at_position = in_view.get_uint8(refs.position)
            if byte_at_position != 0xFE:
                return_byte = _start_repeat(in_view, refs, byte_at_position)
            else:
                # Skip duplicate 0xFE
                refs.position += 1

    if refs.alt_offset == refs.alt_length and refs.alt_pattern is not None:
        refs.alt_pattern = None
        refs.alt_offset = 0
        refs.alt_length = 0

    return return_byte


def _write_vl_bytes(out_view, out_pos, value, length, include_fe_repeats):
    """Writes variable-length bytes. Returns the new out_pos value."""
    value = _i32(value)
    if length == 1:
        out_view.set_uint8(out_pos, value & 0xFF)
        out_pos += 1
    elif length == 2:
        out_view.set_uint8(out_pos, (value >> 8) & 0xFF)
        out_pos += 1
        out_view.set_uint8(out_pos, value & 0xFF)
        out_pos += 1
    elif length == 3:
        out_view.set_uint8(out_pos, (value >> 16) & 0xFF)
        out_pos += 1
        out_view.set_uint8(out_pos, (value >> 8) & 0xFF)
        out_pos += 1
        out_view.set_uint8(out_pos, value & 0xFF)
        out_pos += 1
    else:
        out_view.set_uint8(out_pos, (value >> 24) & 0xFF)
        out_pos += 1
        out_view.set_uint8(out_pos, (value >> 8) & 0xFF)
        out_pos += 1
        out_view.set_uint8(out_pos, value & 0xFF)
        out_pos += 1
    return out_pos


def _return_vl_bytes(value):
    v = _i32(value)
    sub_value1 = (v >> 21) & 0x7F
    sub_value2 = (v >> 14) & 0x7F
    sub_value3 = (v >> 7) & 0x7F
    sub_value4 = (v >> 0) & 0x7F

    if sub_value1 > 0:
        new_value = _i32(0x80808000 | (sub_value1 << 24) | (sub_value2 << 16)
                         | (sub_value3 << 8) | sub_value4)
        return new_value, 4
    elif sub_value2 > 0:
        new_value = 0x00808000 | (sub_value2 << 16) | (sub_value3 << 8) | sub_value4
        return new_value, 3
    elif sub_value3 > 0:
        new_value = 0x00008000 | (sub_value3 << 8) | sub_value4
        return new_value, 2
    else:
        return value, 1
