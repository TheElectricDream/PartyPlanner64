"""Finding and starting a Nintendo 64 emulator, for test play.

The emulator is a command line (a setting of the Test Play options), e.g.

    /home/me/Applications/RMG-K.AppImage --fullscreen %f

where %f (or %F, %u, %U) is replaced by the ROM file; without one the ROM file
is added at the end. When it is not set, an installed emulator is looked for:
on Linux, the applications that open N64 ROMs (their .desktop files), then
well-known emulators on the PATH.
"""

import logging
import os
import shlex
import shutil
import signal
import subprocess
import sys
import threading
import time

logger = logging.getLogger("partyplanner64")

N64_MIME_TYPES = ("application/x-n64-rom",)

# Emulators that take a ROM file on their command line, by executable name.
KNOWN_EMULATORS = ("RMG-K", "RMG", "rmg", "simple64-gui", "mupen64plus-qt", "m64p", "mupen64plus",
                   "ares", "gopher64", "Project64", "cen64")

_lock = threading.Lock()
_process = None          # the emulator started last


class EmulatorError(Exception):
    """The emulator could not be found or started; the message says why."""


def _desktop_dirs():
    data_home = os.environ.get("XDG_DATA_HOME") or os.path.expanduser("~/.local/share")
    data_dirs = os.environ.get("XDG_DATA_DIRS")
    if data_dirs:
        dirs = [data_home] + [d for d in data_dirs.split(":") if d]
    else:
        # A service's environment may not have it: the usual places, and Flatpak's.
        dirs = [data_home, "/usr/local/share", "/usr/share",
                os.path.expanduser("~/.local/share/flatpak/exports/share"),
                "/var/lib/flatpak/exports/share"]
    seen = []
    for d in dirs:
        d = os.path.join(d, "applications")
        if d not in seen:
            seen.append(d)
    return seen


def _read_desktop_entry(path):
    """The [Desktop Entry] keys of a .desktop file, or None."""
    entry = {}
    try:
        with open(path, encoding="utf-8", errors="replace") as f:
            section = None
            for line in f:
                line = line.strip()
                if line.startswith("["):
                    section = line
                elif section == "[Desktop Entry]" and "=" in line and not line.startswith("#"):
                    key, value = line.split("=", 1)
                    entry.setdefault(key.strip(), value.strip())
    except OSError:
        return None
    return entry


def desktop_emulators():
    """Installed applications that open N64 ROMs: [{"name", "command"}] (Linux)."""
    found = []
    seen = set()
    if not sys.platform.startswith("linux"):
        return found
    for directory in _desktop_dirs():
        try:
            names = sorted(os.listdir(directory))
        except OSError:
            continue
        for name in names:
            if not name.endswith(".desktop") or name in seen:
                continue
            entry = _read_desktop_entry(os.path.join(directory, name))
            if not entry or entry.get("Type", "Application") != "Application":
                continue
            mime_types = [m for m in entry.get("MimeType", "").split(";") if m]
            if not any(m in N64_MIME_TYPES for m in mime_types):
                continue
            command = entry.get("Exec")
            if not command or entry.get("Hidden") == "true":
                continue
            seen.add(name)
            found.append({"name": entry.get("Name") or name[:-8], "command": command})
    return found


def detect():
    """An installed emulator: {"name", "command"}, or None."""
    emulators = desktop_emulators()
    if emulators:
        return emulators[0]
    for name in KNOWN_EMULATORS:
        path = shutil.which(name)
        if path:
            return {"name": name, "command": shlex.quote(path) + " %f"}
    return None


def command_line(command, rom_path):
    """The arguments to run: `command` with its field codes filled in for rom_path.

    Field codes are those of .desktop files: %f %F %u %U are the ROM file, %% is a
    percent sign, the others are dropped. Without a file code the ROM file is added.
    """
    try:
        parts = shlex.split(command or "")
    except ValueError as e:
        raise EmulatorError("The emulator command is not valid: %s" % e)
    if not parts:
        raise EmulatorError("No emulator is set.")
    rom_path = str(rom_path)
    args = []
    has_file = False
    for part in parts:
        out = []
        i = 0
        drop = False
        while i < len(part):
            c = part[i]
            if c == "%" and i + 1 < len(part):
                code = part[i + 1]
                i += 2
                if code in "fFuU":
                    out.append(rom_path)
                    has_file = True
                elif code == "%":
                    out.append("%")
                elif part == "%" + code:
                    drop = True        # a code alone (%i, %c, %k): nothing
                continue
            out.append(c)
            i += 1
        if not drop:
            args.append("".join(out))
    if not has_file:
        args.append(rom_path)
    return args


def stop():
    """Stop the emulator started last, if it still runs."""
    global _process
    with _lock:
        process, _process = _process, None
    if process is None or process.poll() is not None:
        return False
    try:
        if os.name == "posix":
            os.killpg(process.pid, signal.SIGTERM)
        else:
            process.terminate()
        try:
            process.wait(timeout=1.5)
        except subprocess.TimeoutExpired:
            # Some emulators (RMG) take their time over a polite request.
            if os.name == "posix":
                os.killpg(process.pid, signal.SIGKILL)
            else:
                process.kill()
            process.wait(timeout=3)
    except (OSError, ProcessLookupError, subprocess.TimeoutExpired):
        pass
    return True


def launch(command, rom_path, log_path=None, settle=1.0):
    """Start the emulator with a ROM file; the emulator started before is stopped.

    log_path: a file for what the emulator prints (written anew each time).
    Returns the arguments run. Raises EmulatorError when the command cannot be run,
    or exits with an error within `settle` seconds.
    """
    global _process
    args = command_line(command, rom_path)
    stop()
    log = open(log_path, "wb") if log_path else None
    kwargs = {"stdin": subprocess.DEVNULL, "stdout": log or subprocess.DEVNULL,
              "stderr": subprocess.STDOUT}
    if os.name == "posix":
        kwargs["start_new_session"] = True
    try:
        process = subprocess.Popen(args, **kwargs)
    except OSError as e:
        raise EmulatorError("The emulator could not be started (%s): %s"
                            % (args[0], e.strerror or e))
    finally:
        if log:
            log.close()            # the emulator has its own handle
    deadline = time.monotonic() + settle
    while time.monotonic() < deadline and process.poll() is None:
        time.sleep(0.05)
    code = process.poll()
    if code not in (None, 0):
        tail = ""
        if log_path:
            try:
                with open(log_path, "rb") as f:
                    tail = f.read()[-600:].decode("utf-8", "replace").strip()
            except OSError:
                pass
        raise EmulatorError("The emulator stopped at once (exit code %s)%s"
                            % (code, ":\n\n" + tail if tail else "."))
    with _lock:
        _process = process
    logger.info("Started the emulator: %s", " ".join(shlex.quote(a) for a in args))
    return args
