"""Finding and starting the emulator (partyplanner64/emulator.py)."""

import os
import stat
import sys
import time

import pytest

from partyplanner64 import emulator
from partyplanner64.emulator import EmulatorError

posix = pytest.mark.skipif(os.name != "posix", reason="uses a shell script")


@pytest.fixture(autouse=True)
def _stop_after():
    yield
    emulator.stop()


def test_command_line():
    rom = "/tmp/My Test (MP3).z64"
    assert emulator.command_line("RMG", rom) == ["RMG", rom]
    assert emulator.command_line("RMG --fullscreen %f", rom) == ["RMG", "--fullscreen", rom]
    assert emulator.command_line("env A=1 '/opt/my emu/run' %U --x", rom) == \
        ["env", "A=1", "/opt/my emu/run", rom, "--x"]
    # A code inside an argument; an icon code alone; a percent sign.
    assert emulator.command_line("emu %i --rom=%f --speed=100%%", rom) == \
        ["emu", "--rom=" + rom, "--speed=100%"]
    for bad in ("", "   ", None):
        with pytest.raises(EmulatorError):
            emulator.command_line(bad, rom)
    with pytest.raises(EmulatorError) as e:
        emulator.command_line("emu 'unclosed", rom)
    assert "not valid" in str(e.value)


def _desktop_file(directory, name, text):
    apps = directory / "applications"
    apps.mkdir(parents=True, exist_ok=True)
    (apps / name).write_text(text, encoding="utf-8")


@pytest.mark.skipif(not sys.platform.startswith("linux"), reason="desktop entries")
def test_desktop_emulators(tmp_path, monkeypatch):
    home = tmp_path / "home"
    system = tmp_path / "usr"
    monkeypatch.setenv("XDG_DATA_HOME", str(home))
    monkeypatch.setenv("XDG_DATA_DIRS", str(system))
    monkeypatch.setattr(emulator.os.path, "expanduser", lambda p: str(tmp_path / "none"))
    assert emulator.desktop_emulators() == []

    _desktop_file(system, "editor.desktop",
                  "[Desktop Entry]\nType=Application\nName=Editor\nExec=edit %f\nMimeType=text/plain;\n")
    _desktop_file(system, "mupen.desktop",
                  "[Desktop Entry]\nType=Application\nName=Mupen\nExec=mupen64plus %f\n"
                  "MimeType=application/x-n64-rom;\n")
    _desktop_file(home, "RMG-K.desktop",
                  "[Desktop Entry]\nType=Application\nName=RMG-K\n"
                  "Exec=env X=1 /apps/RMG-K.AppImage %f\nMimeType=application/x-n64-rom;\n"
                  "\n[Desktop Action other]\nExec=other\n")
    _desktop_file(home, "hidden.desktop",
                  "[Desktop Entry]\nType=Application\nName=Hidden\nExec=hidden %f\nHidden=true\n"
                  "MimeType=application/x-n64-rom;\n")
    assert emulator.desktop_emulators() == [
        {"name": "RMG-K", "command": "env X=1 /apps/RMG-K.AppImage %f"},     # the user's first
        {"name": "Mupen", "command": "mupen64plus %f"},
    ]
    assert emulator.detect()["name"] == "RMG-K"


def test_detect_on_the_path(monkeypatch):
    monkeypatch.setattr(emulator, "desktop_emulators", lambda: [])
    monkeypatch.setattr(emulator.shutil, "which",
                        lambda name: "/usr/local/bin/my emus/" + name if name == "ares" else None)
    assert emulator.detect() == {"name": "ares", "command": "'/usr/local/bin/my emus/ares' %f"}
    monkeypatch.setattr(emulator.shutil, "which", lambda name: None)
    assert emulator.detect() is None


def _script(tmp_path, body):
    path = tmp_path / "emu.sh"
    path.write_text("#!/bin/sh\n" + body, encoding="utf-8")
    path.chmod(path.stat().st_mode | stat.S_IXUSR)
    return path


def _wait_for(path, timeout=5):
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if path.exists() and path.read_text():
            return path.read_text()
        time.sleep(0.02)
    raise AssertionError("%s was not written" % path)


@posix
def test_launch_and_stop(tmp_path):
    out = tmp_path / "args.txt"
    script = _script(tmp_path, 'echo "$$ $@" >> "%s"\nexec sleep 60\n' % out)
    rom = tmp_path / "Test (MP3).z64"
    rom.write_bytes(b"rom")
    args = emulator.launch("%s --fullscreen %%f" % script, rom, log_path=tmp_path / "log.txt", settle=0.2)
    assert args == [str(script), "--fullscreen", str(rom)]
    first_pid, _, rest = _wait_for(out).strip().partition(" ")
    assert rest == "--fullscreen %s" % rom               # one argument, spaces and all
    first_pid = int(first_pid)
    os.kill(first_pid, 0)                               # it runs

    # Starting it again stops the one before.
    emulator.launch(str(script), rom, settle=0.2)
    with pytest.raises(ProcessLookupError):
        os.kill(first_pid, 0)
    second_pid = int(_wait_for(out).splitlines()[1].split()[0])
    os.kill(second_pid, 0)
    assert emulator.stop() is True
    with pytest.raises(ProcessLookupError):
        os.kill(second_pid, 0)
    assert emulator.stop() is False


@posix
def test_launch_errors(tmp_path):
    rom = tmp_path / "test.z64"
    with pytest.raises(EmulatorError) as e:
        emulator.launch(str(tmp_path / "not-there"), rom)
    assert "could not be started" in str(e.value)

    script = _script(tmp_path, 'echo "cannot open display" >&2\nexit 3\n')
    with pytest.raises(EmulatorError) as e:
        emulator.launch(str(script), rom, log_path=tmp_path / "log.txt", settle=2)
    assert "exit code 3" in str(e.value) and "cannot open display" in str(e.value)

    # One that ends at once without an error (it handed over to a running copy) is fine.
    script = _script(tmp_path, "exit 0\n")
    emulator.launch(str(script), rom, settle=1)
