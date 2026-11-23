#!/usr/bin/env python3
"""Game Boy music to a MIDI file and a soundbank for it (PartyPlanner64 custom audio).

    gbsplay -o iodumper -t SECONDS -T 0 -f 0 -g 0 -q SONG.gbs SUBSONG SUBSONG > song.dump
    python3 scripts/gbs_to_midi.py song.dump OUT_NAME [--name "Bank name"]

writes OUT_NAME.mid and OUT_NAME.soundbank.json. In PartyPlanner64's Details page, upload
the MIDI as a custom song, import the soundbank (Soundbanks card, Import…) and choose it as
the song's soundbank. Dump at least two passes of the song (SECONDS): the loop is found in
the dump, and the MIDI holds what comes before it (once) and one pass of the loop, marked
with a "loopStart" marker, which the game repeats.

The dump is gbsplay's iodumper output: each line is "CYCLES ADDR=VALUE", the CPU cycles
(4194304 a second) since the line before and a write to a sound register. The script plays
the sound chip's state forward as the Game Boy does (its 512 Hz frame sequencer clocks the
lengths, channel 1's sweep and the volume envelopes) and writes what it hears:

- each channel is a MIDI channel (1-4 on 0-3): a trigger starts a note at the exact pitch
  (rounded to a key, the rest as a pitch bend); later pitch changes are pitch bends (a whole
  new note past two semitones); a channel switching off ends its note;
- volume (envelope, wave level, master volume, a channel panned nowhere) is controller 7
  (as its square root: the game squares channel volume), panning controller 10;
- the instruments are what the channels played: each pulse duty, each wave-RAM pattern and
  each noise width, as soundbank instruments (lib/audio/custom_bank.py) in the order first
  heard. A noise note's key picks its clock: key 60 is 4096 Hz, 12 keys an octave.

Only the standard library is used.
"""

import argparse
import json
import math
import struct
import sys

CLOCK = 4194304
PPQ = 480
TEMPO = 500000                 # microseconds a beat: 960 ticks a second
TICKS_PER_SECOND = PPQ * 1000000 / TEMPO
BEND_RANGE = 2.0               # semitones (custom_bank instruments bend 200 cents)
DUTIES = (0.125, 0.25, 0.5, 0.75)


def hz_to_key(hz):
    return 69 + 12 * math.log2(hz / 440.0)


class Channel:
    def __init__(self, n):
        self.n = n                  # 1-4
        self.on = False             # sounding (enabled and its DAC on)
        self.dac = False
        self.vol = 0
        self.env_init = self.env_up = self.env_period = 0
        self.env_timer = 0
        self.length = 0
        self.length_on = False
        self.freq = 0
        self.duty = 2
        self.note = None            # MIDI key of the sounding note
        self.sweep = (0, 0, 0)      # period, negate, shift
        self.sweep_timer = 0
        self.sweep_on = False


class Converter:
    def __init__(self):
        self.regs = bytearray(0x30)
        self.wave = bytearray(16)
        self.ch = {n: Channel(n) for n in (1, 2, 3, 4)}
        self.events = []            # (seconds, order, channel 0-3, kind, value...)
        self.order = 0
        self.instruments = []       # source dicts, program = index
        self.cur_program = {}
        self.cur_cc = {}
        self.cur_bend = {}
        self.master = 7
        self.pan = 0xFF
        self.power = True
        self.pending = set()        # channels whose frequency changed in this burst of writes

    # --- output helpers ---------------------------------------------------------------

    def emit(self, t, chan, kind, *vals):
        self.order += 1
        self.events.append((t, self.order, chan, kind) + vals)

    def program_for(self, source):
        if source not in self.instruments:
            self.instruments.append(source)
        return self.instruments.index(source)

    def set_cc(self, t, c, num, value):
        if self.cur_cc.get((c.n, num)) != value:
            self.cur_cc[(c.n, num)] = value
            self.emit(t, c.n - 1, "cc", num, value)

    def set_bend(self, t, c, semis):
        value = max(0, min(16383, 8192 + int(round(semis / BEND_RANGE * 8192))))
        if self.cur_bend.get(c.n, 8192) != value:
            self.cur_bend[c.n] = value
            self.emit(t, c.n - 1, "bend", value)

    # --- what a channel sounds like ---------------------------------------------------

    def hz(self, c):
        if c.n == 3:
            return 65536.0 / (2048 - c.freq)
        if c.n == 4:
            poly = self.regs[0x22]
            r = poly & 7
            return 524288.0 / (r or 0.5) / 2 ** ((poly >> 4) + 1)
        return 131072.0 / (2048 - c.freq)

    def source(self, c):
        if c.n == 3:
            return ("wave", self.wave.hex().upper())
        if c.n == 4:
            return ("noise", bool(self.regs[0x22] & 8))
        return ("pulse", DUTIES[c.duty])

    def key(self, c):
        if c.n == 4:
            return 60 + 12 * math.log2(self.hz(c) / 4096.0)
        return hz_to_key(self.hz(c))

    def volume(self, c):
        """Controller 7 for the channel's loudness now (0-127)."""
        if not c.on or not self.power:
            return 0
        if c.n == 3:
            level = (0, 1.0, 0.5, 0.25)[(self.regs[0x1C] >> 5) & 3]
        else:
            level = c.vol / 15.0
        left = self.pan & (0x10 << (c.n - 1))
        right = self.pan & (1 << (c.n - 1))
        if not left and not right:
            return 0
        # The game's channel volume is squared (Mario Party 3, measured: controller 7 at 64
        # plays at a quarter), so the square root keeps the Game Boy's levels.
        return int(round(127 * math.sqrt(level * (self.master + 1) / 8)))

    def update(self, t, c):
        """Volume and panning controllers; ends a note that went silent."""
        vol = self.volume(c)
        if c.note is not None and vol == 0 and (not c.on or (c.n != 3 and not c.env_up)):
            self.note_off(t, c)
            return
        if c.note is not None:
            self.set_cc(t, c, 7, max(vol, 1))
        left = self.pan & (0x10 << (c.n - 1))
        right = self.pan & (1 << (c.n - 1))
        self.set_cc(t, c, 10, 64 if (left and right) or not (left or right) else (0 if left else 127))

    def note_off(self, t, c):
        if c.note is not None:
            self.emit(t, c.n - 1, "off", c.note)
            c.note = None

    def note_on(self, t, c):
        self.note_off(t, c)
        if not c.on or self.volume(c) == 0:
            return
        exact = self.key(c)
        key = max(0, min(127, int(round(exact))))
        program = self.program_for(self.source(c))
        if self.cur_program.get(c.n) != program:
            self.cur_program[c.n] = program
            self.emit(t, c.n - 1, "program", program)
        self.set_bend(t, c, exact - key)
        self.set_cc(t, c, 7, self.volume(c))
        c.note = key
        self.emit(t, c.n - 1, "on", key)

    def pitch_changed(self, t, c):
        if c.note is None:
            return
        exact = self.key(c)
        if abs(exact - c.note) <= BEND_RANGE:
            self.set_bend(t, c, exact - c.note)
        else:
            self.note_on(t, c)

    # --- the sound chip -------------------------------------------------------------

    def frame_step(self, t, step):
        """One step of the 512 Hz frame sequencer (step 0-7)."""
        if step % 2 == 0:                       # lengths, 256 Hz
            for c in self.ch.values():
                if c.on and c.length_on and c.length > 0:
                    c.length -= 1
                    if c.length == 0:
                        c.on = False
                        self.update(t, c)
        if step in (2, 6):                      # channel 1's sweep, 128 Hz
            c = self.ch[1]
            period, negate, shift = c.sweep
            if c.on and c.sweep_on and period:
                c.sweep_timer -= 1
                if c.sweep_timer <= 0:
                    c.sweep_timer = period
                    new = c.freq - (c.freq >> shift) if negate else c.freq + (c.freq >> shift)
                    if new > 2047:
                        c.on = False
                        self.update(t, c)
                    elif shift:
                        c.freq = new
                        self.pitch_changed(t, c)
        if step == 7:                           # envelopes, 64 Hz
            for n in (1, 2, 4):
                c = self.ch[n]
                if c.on and c.env_period:
                    c.env_timer -= 1
                    if c.env_timer <= 0:
                        c.env_timer = c.env_period
                        if c.env_up and c.vol < 15:
                            c.vol += 1
                            self.update(t, c)
                        elif not c.env_up and c.vol > 0:
                            c.vol -= 1
                            self.update(t, c)

    def trigger(self, t, c):
        c.on = c.dac
        if c.length == 0:
            c.length = 256 if c.n == 3 else 64
        if c.n != 3:
            c.vol = c.env_init
            c.env_timer = c.env_period
        if c.n == 1:
            period, negate, shift = c.sweep
            c.sweep_timer = period or 8
            c.sweep_on = bool(period or shift)
        self.note_on(t, c)

    def write(self, t, addr, val):
        if 0xFF30 <= addr <= 0xFF3F:
            self.wave[addr - 0xFF30] = val
            return
        if not 0xFF10 <= addr <= 0xFF26:
            return
        r = addr - 0xFF00
        self.regs[r] = val
        if r == 0x26:
            self.power = bool(val & 0x80)
            if not self.power:
                for c in self.ch.values():
                    c.on = False
                    self.note_off(t, c)
            return
        if r == 0x24:
            self.master = max((val >> 4) & 7, val & 7)
            for c in self.ch.values():
                self.update(t, c)
            return
        if r == 0x25:
            self.pan = val
            for c in self.ch.values():
                self.update(t, c)
            return
        n = 1 if r <= 0x14 else 2 if r <= 0x19 else 3 if r <= 0x1E else 4
        c = self.ch[n]
        reg = (r - 0x10) % 5 if n == 1 else (r - 0x15) % 5 if n == 2 else (r - 0x1A) % 5 if n == 3 else (r - 0x1F) % 5
        if n == 1 and reg == 0:
            c.sweep = ((val >> 4) & 7, (val >> 3) & 1, val & 7)
        elif reg == 1:
            if n == 3:
                c.length = 256 - val
            else:
                c.length = 64 - (val & 63)
                if n != 4:
                    c.duty = val >> 6
        elif reg == 2:
            if n == 3:
                self.update(t, c)               # wave level
            else:
                c.env_init, c.env_up, c.env_period = val >> 4, (val >> 3) & 1, val & 7
                c.dac = bool(val & 0xF8)
                if not c.dac and c.on:
                    c.on = False
                    self.update(t, c)
        elif reg == 0 and n == 3:
            c.dac = bool(val & 0x80)
            if not c.dac and c.on:
                c.on = False
                self.update(t, c)
        elif reg == 3:
            # A frequency's low byte (or the noise's clock, NR43): its high byte and a trigger
            # usually follow at once, so the pitch is taken when the burst of writes ends.
            if n != 4:
                c.freq = (c.freq & 0x700) | val
            self.pending.add(c)
        elif reg == 4:
            if n != 4:
                c.freq = (c.freq & 0xFF) | ((val & 7) << 8)
            c.length_on = bool(val & 0x40)
            if val & 0x80:
                self.pending.discard(c)
                self.trigger(t, c)
            elif n != 4:
                self.pending.add(c)

    def flush(self, t):
        for c in sorted(self.pending, key=lambda c: c.n):
            self.pitch_changed(t, c)
        self.pending.clear()

    def run(self, lines):
        cycles = 0
        frame = 0                               # frame sequencer steps done
        last = 0.0
        for line in lines:
            parts = line.split()
            if len(parts) != 2 or "=" not in parts[1]:
                continue
            delta = int(parts[0], 16)
            cycles += delta
            t = cycles / CLOCK
            if delta > 256 and self.pending:     # the burst before this write is over
                self.flush(last)
            last = t
            while (frame + 1) * CLOCK // 512 <= cycles:
                frame += 1
                self.frame_step(frame / 512, frame % 8)
            addr, val = parts[1].split("=")
            self.write(t, int(addr, 16), int(val, 16))
        self.flush(last)
        self.end = cycles / CLOCK
        for c in self.ch.values():
            self.note_off(self.end, c)


# --- the loop ---------------------------------------------------------------------

def find_loop(events, tolerance=0.02):
    """(start, length) in seconds of the song's loop, or None: the earliest start and then
    the shortest length such that every note from the start on comes again (same channel and
    key) a length later, to the end of the dump. A repeated phrase inside the song doesn't
    pass, as the notes after it differ.

    Drivers play on frames (16.7 ms) while a loop is rarely a whole number of them, so a
    note comes back up to a frame early or late (tolerance); the length is then the mean of
    all the matched notes' distances."""
    notes = [(e[0], e[2], e[4], ) for e in events if e[3] == "on"]
    if len(notes) < 8:
        return None
    by_sig = {}
    for i, (t, ch, key) in enumerate(notes):
        by_sig.setdefault((ch, key), []).append(i)
    times = [n[0] for n in notes]
    import bisect

    def matches(i, j):
        """The matched distances if everything from note i on repeats a period later (to
        the end of the dump), else None."""
        period = times[j] - times[i]
        end = times[-1] - period - tolerance
        k = i
        deltas = []
        misses = 0                              # a stray note or two (1%) is let through
        while k < len(notes) and times[k] < end:
            t, ch, key = notes[k]
            target = t + period
            lo = bisect.bisect_left(times, target - tolerance)
            best = None
            while lo < len(notes) and times[lo] <= target + tolerance:
                if notes[lo][1] == ch and notes[lo][2] == key and (
                        best is None or abs(times[lo] - target) < abs(best - target)):
                    best = times[lo]
                lo += 1
            if best is None:
                misses += 1
                if misses > max(2, (len(notes) - i) // 100):
                    return None
            else:
                deltas.append(best - t)
            k += 1
        return deltas

    for i in range(min(len(notes), 400)):
        t, ch, key = notes[i]
        for j in by_sig[(ch, key)]:
            if j <= i or times[j] - times[i] < 1.0:
                continue
            if times[j] + (times[j] - times[i]) > times[-1] + 1.0:
                break                           # not a whole second pass in the dump
            deltas = matches(i, j)
            if deltas:
                # A loop of a fractional number of frames comes back a frame early or on time
                # by turns; the mean of the distances is its length.
                return times[i], sum(deltas) / len(deltas)
    return None


# --- writing --------------------------------------------------------------------

def _vl(v):
    out = [v & 0x7F]
    v >>= 7
    while v:
        out.insert(0, (v & 0x7F) | 0x80)
        v >>= 7
    return bytes(out)


def write_midi(events, start, length, intro=0.0):
    """A type-1 MIDI file of the events in [start - intro, start + length), time 0 at
    start - intro: the intro once, then the loop, marked with a "loopStart" marker that
    PartyPlanner64 loops back to. Every channel's controllers and program are restated at
    time 0, and there is an event at the loop end (songs loop at their last event)."""
    loop_tick = int(round(intro * TICKS_PER_SECOND))
    start -= intro
    length += intro
    end_tick = int(round(length * TICKS_PER_SECOND))
    # Notes come back up to half a frame early or late: what starts within half a frame of
    # the loop's end is the next pass (its first notes), and of the start, this one.
    edge = 0.5 / 59.7275
    state = {}                                  # (channel, kind[, num]) -> value before start
    tracks = {}
    for e in sorted(events, key=lambda e: (e[0], e[1])):
        t, _, ch, kind = e[:4]
        if t < start - edge:
            if kind == "program":
                state[(ch, "program")] = e[4]
            elif kind == "cc":
                state[(ch, "cc", e[4])] = e[5]
            elif kind == "bend":
                state[(ch, "bend")] = e[4]
            continue
        if t >= start + length - edge:
            continue
        tick = max(0, int(round((t - start) * TICKS_PER_SECOND)))
        tracks.setdefault(ch, []).append((tick, e[1], kind, e[4:]))
    conductor = b"\x00\xff\x51\x03" + TEMPO.to_bytes(3, "big") + b"\x00\xff\x58\x04\x04\x02\x18\x08"
    if loop_tick:
        conductor += _vl(loop_tick) + b"\xff\x06\x09loopStart" + _vl(end_tick - loop_tick)
    else:
        conductor += _vl(end_tick)
    out = [conductor + b"\xff\x2f\x00"]
    for ch in sorted(set(tracks) | {k[0] for k in state}):
        evs = []
        for key, value in state.items():
            if key[0] != ch:
                continue
            if key[1] == "program":
                evs.append((0, -3, "program", (value,)))
            elif key[1] == "cc":
                evs.append((0, -2, "cc", (key[2], value)))
            else:
                evs.append((0, -1, "bend", (value,)))
        evs += tracks.get(ch, [])
        sounding = set()
        body = bytearray()
        now = 0
        for tick, _, kind, vals in sorted(evs, key=lambda e: (e[0], e[1])):
            body += _vl(tick - now)
            now = tick
            if kind == "on":
                body += bytes([0x90 | ch, vals[0], 110])
                sounding.add(vals[0])
            elif kind == "off":
                body += bytes([0x80 | ch, vals[0], 0])
                sounding.discard(vals[0])
            elif kind == "program":
                body += bytes([0xC0 | ch, vals[0]])
            elif kind == "cc":
                body += bytes([0xB0 | ch, vals[0], vals[1]])
            elif kind == "bend":
                body += bytes([0xE0 | ch, vals[0] & 0x7F, vals[0] >> 7])
        for key in sorted(sounding):            # notes held over the loop end
            body += _vl(end_tick - now) + bytes([0x80 | ch, key, 0])
            now = end_tick
        # The loop end, on every track: a controller that changes nothing.
        vol = None
        for tick, _, kind, vals in sorted(evs, key=lambda e: (e[0], e[1])):
            if kind == "cc" and vals[0] == 7:
                vol = vals[1]
        body += _vl(end_tick - now) + bytes([0xB0 | ch, 7, vol if vol is not None else 100])
        body += b"\x00\xff\x2f\x00"
        out.append(bytes(body))
    data = b"MThd" + struct.pack(">IHHH", 6, 1, len(out), PPQ)
    for body in out:
        data += b"MTrk" + struct.pack(">I", len(body)) + body
    return data


def soundbank(name, instruments):
    insts = []
    wave_no = 0
    for kind, arg in instruments:
        if kind == "pulse":
            label, source = "Pulse %g%%" % (arg * 100), {"type": "pulse", "duty": arg}
        elif kind == "wave":
            wave_no += 1
            label, source = "Wave %d" % wave_no, {"type": "wave", "pattern": arg}
        else:
            label, source = "Noise (Short)" if arg else "Noise", {"type": "noise", "short": arg}
        insts.append({"name": label, "volume": 110, "pan": 64, "attack": 0, "decay": 1,
                      "sustain": 127, "release": 3, "source": source})
    return {"name": name, "instruments": insts}


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("dump", help="gbsplay -o iodumper output")
    ap.add_argument("out", help="output name (OUT.mid, OUT.soundbank.json)")
    ap.add_argument("--name", help="the soundbank's name")
    ap.add_argument("--start", type=float, help="loop start in seconds (default: found)")
    ap.add_argument("--length", type=float, help="loop length in seconds (default: found)")
    ap.add_argument("--no-intro", dest="intro", action="store_false",
                    help="leave out what plays before the loop (default: played once, then the loop)")
    args = ap.parse_args(argv)

    conv = Converter()
    with open(args.dump) as f:
        conv.run(f)
    loop = (args.start, args.length) if args.start is not None and args.length else find_loop(conv.events)
    if loop is None:
        first = min((e[0] for e in conv.events if e[3] == "on"), default=0.0)
        loop = (first, conv.end - first)
        print("No repeat found in the dump: the MIDI is all of it (dump two passes to loop it).",
              file=sys.stderr)
    start, length = loop
    # The intro: from the first note to the loop's start (played once).
    first = min((e[0] for e in conv.events if e[3] == "on"), default=start)
    intro = max(0.0, start - first) if args.intro else 0.0
    with open(args.out + ".mid", "wb") as f:
        f.write(write_midi(conv.events, start, length, intro))
    bank = soundbank(args.name or args.out.rsplit("/", 1)[-1], conv.instruments)
    with open(args.out + ".soundbank.json", "w") as f:
        json.dump(bank, f, indent=1)
    notes = sum(1 for e in conv.events if e[3] == "on" and start <= e[0] < start + length)
    print("intro %.3f s, then a %.3f s loop (from %.3f s); %d notes in the loop; instruments: %s" % (
        intro, length, start, notes, ", ".join(i["name"] for i in bank["instruments"])))


if __name__ == "__main__":
    main()
