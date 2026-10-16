"""Compiles C source to MIPS assembly (port of utils/c-compiler.ts).

The compiler is SmallerC (https://github.com/alexfru/SmallerC), built with
Emscripten as lib/vendor/smlrc.wasm. The TypeScript ran it with the
Emscripten JavaScript glue (smlrc.js); here it runs with wasmtime, an
optional dependency (only needed to compile C events), and this module
provides what the glue did and SmallerC uses: the memory layout, a small
in-memory file system for /input.c and /output.s, the console streams, and
the system calls (open, fcntl, ioctl, read, write, seek, close, exit).
"""

import os
import struct

from .c_preprocessor import preprocess

_WASM_PATH = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                          "vendor", "smlrc.wasm")

# From the Emscripten glue (smlrc.js).
_DYNAMIC_BASE = 5285248
_DYNAMICTOP_PTR = 42208
_MEMORY_PAGES = 256  # INITIAL_TOTAL_MEMORY / WASM_PAGE_SIZE (16 MB, fixed)
_TABLE_SIZE = 9

# Emscripten errno values.
_EBADF = 8
_EINVAL = 28
_EISDIR = 31
_ENOENT = 44
_ENOTTY = 59
_EEXIST = 20
_ESPIPE = 70

# musl open() flags.
_O_ACCMODE = 3
_O_WRONLY = 1
_O_RDWR = 2
_O_CREAT = 0o100
_O_EXCL = 0o200
_O_TRUNC = 0o1000
_O_APPEND = 0o2000

_engine = None
_module = None


class CompileError(ValueError):
    """The C source could not be compiled."""


def _load_module():
    global _engine, _module
    if _module is None:
        try:
            import wasmtime
        except ImportError:
            raise RuntimeError(
                "Compiling C events needs the optional 'wasmtime' package "
                "(pip install wasmtime).") from None
        _engine = wasmtime.Engine()
        _module = wasmtime.Module.from_file(_engine, _WASM_PATH)
    return _module


class _ExitStatus(Exception):
    def __init__(self, status):
        super().__init__("Program terminated with exit(%d)" % status)
        self.status = status


class _Abort(Exception):
    pass


class _Errno(Exception):
    def __init__(self, errno):
        super().__init__(errno)
        self.errno = errno


class _Stream:
    __slots__ = ("path", "flags", "position", "tty")

    def __init__(self, path, flags, tty=None):
        self.path = path
        self.flags = flags
        self.position = 0
        self.tty = tty


class _SmallerC:
    """One instance of the SmallerC module, with its file system and console."""

    def __init__(self, print_func):
        import wasmtime

        self._print = print_func
        self.files = {}  # path -> bytearray
        self.streams = {
            0: _Stream("/dev/tty", 0, tty=bytearray()),
            1: _Stream("/dev/tty", 1, tty=bytearray()),
            2: _Stream("/dev/tty1", 1, tty=bytearray()),
        }

        module = _load_module()
        store = self._store = wasmtime.Store(_engine)
        i32 = wasmtime.ValType.i32()

        def func(params, results, fn):
            return wasmtime.Func(store, wasmtime.FuncType([i32] * params, [i32] * results), fn)

        self._memory = wasmtime.Memory(
            store, wasmtime.MemoryType(wasmtime.Limits(_MEMORY_PAGES, _MEMORY_PAGES)))
        table = wasmtime.Table(
            store, wasmtime.TableType(wasmtime.ValType.funcref(),
                                      wasmtime.Limits(_TABLE_SIZE, _TABLE_SIZE)), None)

        provided = {
            "a": func(1, 0, lambda *a: None),          # ___unlock
            "b": func(1, 1, self._fd_close),           # _fd_close
            "c": func(2, 1, self._syscall_fcntl64),    # ___syscall221
            "d": func(1, 1, self._resize_heap),        # _emscripten_resize_heap
            "e": func(4, 1, self._fd_write),           # _fd_write
            "f": func(1, 0, lambda *a: None),          # ___lock
            "g": func(4, 1, self._fd_read),            # _fd_read
            "h": func(2, 1, self._syscall_ioctl),      # ___syscall54
            "i": func(5, 1, self._fd_seek),            # _fd_seek
            "j": func(3, 1, self._memcpy_big),         # _emscripten_memcpy_big
            "k": func(2, 1, self._syscall_open),       # ___syscall5
            "l": func(1, 0, self._exit),               # _exit
            "memory": self._memory,
            "table": table,
        }
        imports = [provided[imp.name] for imp in module.imports]
        instance = wasmtime.Instance(store, module, imports)
        exports = instance.exports(store)
        self._call_ctors = exports["m"]
        self._main = exports["n"]
        self._malloc = exports["p"]

        self._write_i32(_DYNAMICTOP_PTR, _DYNAMIC_BASE)
        self._call_ctors(store)

    # Memory helpers

    def _read(self, ptr, length):
        return bytes(self._memory.read(self._store, ptr, ptr + length))

    def _write(self, ptr, data):
        self._memory.write(self._store, bytes(data), ptr)

    def _read_i32(self, ptr):
        return struct.unpack("<i", self._read(ptr, 4))[0]

    def _write_i32(self, ptr, value):
        self._write(ptr, struct.pack("<I", value & 0xFFFFFFFF))

    def _read_cstr(self, ptr):
        out = bytearray()
        while True:
            chunk = self._read(ptr, 64)
            end = chunk.find(0)
            if end >= 0:
                out += chunk[:end]
                return out.decode("utf-8", "replace")
            out += chunk
            ptr += 64

    # File system

    def write_file(self, path, text):
        self.files[path] = bytearray(text.encode("utf-8"))

    def read_file(self, path):
        if path not in self.files:
            raise CompileError("Error during event compile:\nCould not read " + path)
        return bytes(self.files[path]).decode("utf-8", "replace")

    def _stream(self, fd):
        stream = self.streams.get(fd)
        if stream is None:
            raise _Errno(_EBADF)
        return stream

    def _open(self, path, flags):
        if path.endswith("/") or path in ("/", "/dev", "/tmp", "/home"):
            if flags & _O_ACCMODE:
                raise _Errno(_EISDIR)
        if path not in self.files:
            if not flags & _O_CREAT:
                raise _Errno(_ENOENT)
            self.files[path] = bytearray()
        elif flags & _O_CREAT and flags & _O_EXCL:
            raise _Errno(_EEXIST)
        if flags & _O_TRUNC:
            del self.files[path][:]
        fd = 0
        while fd in self.streams:
            fd += 1
        self.streams[fd] = _Stream(path, flags & ~(_O_CREAT | _O_EXCL | _O_TRUNC))
        return fd

    def _tty_put(self, fd, data):
        buf = self.streams[fd].tty
        for byte in data:
            if byte == 10:
                self._print(bytes(buf).decode("utf-8", "replace"))
                del buf[:]
            elif byte != 0:
                buf.append(byte)

    def _readv_writev(self, stream_fd, iov, iovcnt, write):
        stream = self._stream(stream_fd)
        total = 0
        for i in range(iovcnt):
            ptr = self._read_i32(iov + i * 8)
            length = self._read_i32(iov + i * 8 + 4)
            if write:
                data = self._read(ptr, length)
                if stream.tty is not None:
                    self._tty_put(stream_fd, data)
                else:
                    content = self.files[stream.path]
                    if stream.flags & _O_APPEND:
                        stream.position = len(content)
                    end = stream.position + length
                    if end > len(content):
                        content.extend(bytes(end - len(content)))
                    content[stream.position:end] = data
                    stream.position = end
                total += length
            else:
                if stream.tty is not None:
                    break  # No console input.
                content = self.files[stream.path]
                data = content[stream.position:stream.position + length]
                self._write(ptr, data)
                stream.position += len(data)
                total += len(data)
                if len(data) < length:
                    break
        return total

    # Imports

    def _syscall_open(self, which, varargs):
        try:
            path = self._read_cstr(self._read_i32(varargs))
            flags = self._read_i32(varargs + 4)
            return self._open(path, flags)
        except _Errno as e:
            return -e.errno

    def _syscall_fcntl64(self, which, varargs):
        try:
            fd = self._read_i32(varargs)
            stream = self._stream(fd)
            cmd = self._read_i32(varargs + 4)
            if cmd == 0:
                arg = self._read_i32(varargs + 8)
                if arg < 0:
                    return -_EINVAL
                new_fd = arg
                while new_fd in self.streams:
                    new_fd += 1
                copy = _Stream(stream.path, stream.flags, stream.tty)
                copy.position = stream.position
                self.streams[new_fd] = copy
                return new_fd
            if cmd in (1, 2):
                return 0
            if cmd == 3:
                return stream.flags
            if cmd == 4:
                stream.flags |= self._read_i32(varargs + 8)
                return 0
            if cmd == 12:
                arg = self._read_i32(varargs + 8)
                self._write(arg, struct.pack("<h", 2))
                return 0
            if cmd in (13, 14):
                return 0
            return -_EINVAL
        except _Errno as e:
            return -e.errno

    def _syscall_ioctl(self, which, varargs):
        try:
            stream = self._stream(self._read_i32(varargs))
            op = self._read_i32(varargs + 4)
            if op in (21509, 21505, 21510, 21511, 21512, 21506, 21507, 21508, 21523, 21524):
                return 0 if stream.tty is not None else -_ENOTTY
            if op == 21519:
                if stream.tty is None:
                    return -_ENOTTY
                self._write_i32(self._read_i32(varargs + 8), 0)
                return 0
            if op == 21520:
                return -_EINVAL if stream.tty is not None else -_ENOTTY
            if op == 21531:
                return -_ENOTTY
            raise _Abort("bad ioctl syscall %d" % op)
        except _Errno as e:
            return -e.errno

    def _fd_write(self, fd, iov, iovcnt, pnum):
        try:
            num = self._readv_writev(fd, iov, iovcnt, True)
        except _Errno as e:
            return e.errno
        self._write_i32(pnum, num)
        return 0

    def _fd_read(self, fd, iov, iovcnt, pnum):
        try:
            num = self._readv_writev(fd, iov, iovcnt, False)
        except _Errno as e:
            return e.errno
        self._write_i32(pnum, num)
        return 0

    def _fd_seek(self, fd, offset_low, offset_high, whence, new_offset):
        try:
            stream = self._stream(fd)
            offset = offset_high * 4294967296 + (offset_low & 0xFFFFFFFF)
            if stream.tty is not None:
                raise _Errno(_ESPIPE)
            if whence == 0:
                position = offset
            elif whence == 1:
                position = stream.position + offset
            elif whence == 2:
                position = len(self.files[stream.path]) + offset
            else:
                raise _Errno(_EINVAL)
            if position < 0:
                raise _Errno(_EINVAL)
            stream.position = position
            self._write(new_offset, struct.pack("<Q", position))
            return 0
        except _Errno as e:
            return e.errno

    def _fd_close(self, fd):
        try:
            self._stream(fd)
        except _Errno as e:
            return e.errno
        del self.streams[fd]
        return 0

    def _memcpy_big(self, dest, src, num):
        self._write(dest, self._read(src, num))
        return dest

    def _resize_heap(self, requested_size):
        raise _Abort("OOM")

    def _exit(self, status):
        raise _ExitStatus(status)

    # Running

    def malloc(self, size):
        return self._malloc(self._store, size) & 0xFFFFFFFF

    def str2ptr(self, s):
        ptr = self.malloc(len(s) + 1)
        if not ptr:
            raise CompileError("Null pointer returned in str2ptr")
        self._write(ptr, bytes((ord(c) & 0xFF) for c in s) + b"\0")
        return ptr

    def str2ptrs(self, str_list):
        list_ptr = self.malloc(len(str_list) * 4)
        if not list_ptr:
            raise CompileError("Null pointer returned in str2ptrs")
        for idx, s in enumerate(str_list):
            self._write_i32(list_ptr + 4 * idx, self.str2ptr(s))
        return list_ptr

    def main(self, argv):
        return self._main(self._store, len(argv), self.str2ptrs(argv))


def compile(source):
    """Compiles C source to MIPS assembly.

    Args:
        source: C source code string.
    Returns:
        The assembly text (fused sections, named registers, float helpers).
    """
    source = preprocess(source)

    errors = []

    def add_error(text):
        text = text.replace("in \"/input.c\"", "", 1)  # Input file not useful in error messages.
        errors.append(text)

    instance = _SmallerC(add_error)
    instance.write_file("/input.c", source)

    output_file = "/output.s"
    argv = ["./smallerc", "/input.c", output_file]

    try:
        instance.main(argv)
    except Exception:  # noqa: BLE001 (exit(), traps and aborts all mean the compile failed)
        raise CompileError("Error during event compile:\n" + "\n".join(errors)) from None

    result = instance.read_file(output_file)
    result = _fuse_sections(result)
    result = _convert_to_named_registers(result)
    result = _include_float_helpers(result)
    return result


_reg_names = [
    ["r0", "$0"], ["at", "$1"], ["v0", "$2"], ["v1", "$3"], ["a0", "$4"], ["a1", "$5"],
    ["a2", "$6"], ["a3", "$7"], ["t0", "$8"], ["t1", "$9"], ["t2", "$10"], ["t3", "$11"],
    ["t4", "$12"], ["t5", "$13"], ["t6", "$14"], ["t7", "$15"], ["s0", "$16"], ["s1", "$17"],
    ["s2", "$18"], ["s3", "$19"], ["s4", "$20"], ["s5", "$21"], ["s6", "$22"], ["s7", "$23"],
    ["t8", "$24"], ["t9", "$25"], ["k0", "$26"], ["k1", "$27"], ["gp", "$28"], ["sp", "$29"],
    ["fp", "$30"], ["ra", "$31"],
]


def _convert_to_named_registers(assembly):
    # Backwards to replace $31 before $3
    for name, reg in reversed(_reg_names):
        assembly = assembly.replace(reg, name)
    return assembly


_JS_SPACE = "\t\n\v\f\r            " \
            "      　﻿"


def _fuse_sections(assembly):
    """The compiler emits each section in fragments.

    They need to be fused into one, otherwise some labels could be broken.
    """
    sections = {"text": [], "data": [], "rdata": [], "bss": []}
    cur_section = "text"
    for line in assembly.split("\n"):
        trimmed = line.strip(_JS_SPACE)
        if trimmed in (".text", ".data", ".rdata", ".bss"):
            cur_section = trimmed[1:]
        else:
            sections[cur_section].append(line)

    return ("; .text\n" + "\n".join(sections["text"])
            + "\n; .data\n" + "\n".join(sections["data"])
            + "\n; .rdata\n" + "\n".join(sections["rdata"])
            + "\n; .bss\n" + "\n".join(sections["bss"]))


# The compiler implements soft float operations.

__floatsisf = """__floatsisf:
__floatunsisf:
  mtc1 A0, F12
  cvt.s.w F12, F12
  mfc1 V0, F12
  JR RA
  NOP"""

# TODO: Is this implemented differently?
# const __floatunsisf =
#   `__floatunsisf:
#
#   JR RA
#   NOP`;

# TODO: __fixunssfsi
__fixsfsi = """__fixsfsi:
__fixunssfsi:
  mtc1 A0, F12
  cvt.w.s F12, F12
  mfc1 V0, F12
  JR RA
  NOP"""

__addsf3 = """__addsf3:
  mtc1 A0, F12
  mtc1 A1, F13
  add.s F12, F12, F13
  mfc1 V0, F12
  JR RA
  NOP"""

__subsf3 = """__subsf3:
  mtc1 A0, F12
  mtc1 A1, F13
  sub.s F12, F12, F13
  mfc1 V0, F12
  JR RA
  NOP"""

__negsf2 = """__negsf2:
  mtc1 A0, F12
  neg.s F12, F12
  mfc1 V0, F12
  JR RA
  NOP"""

__mulsf3 = """__mulsf3:
  mtc1 A0, F12
  mtc1 A1, F13
  mul.s F12, F12, F13
  mfc1 V0, F12
  JR RA
  NOP"""

__divsf3 = """__divsf3:
  mtc1 A0, F12
  mtc1 A1, F13
  div.s F12, F12, F13
  mfc1 V0, F12
  JR RA
  NOP"""

# return +1 if either a or b (or both) is a NaN (TODO)
# return 0 if a == b
# return -1 if a < b
# return +1 if a > b
__lesf2 = """__lesf2:
  mtc1 A0, F12
  mtc1 A1, F13

  c.eq.s F12, F13
  bc1t __lesf2_ret ; a == b
  li V0, 0

  c.lt.s F12, F13
  li V0, -1 ; a < b
  bc1t __lesf2_ret
  nop

  li V0, 1 ; a > b

  mfc1 V0, F12
__lesf2_ret:
  JR RA
  NOP"""

# return -1 if either a or b (or both) is a NaN (TODO)
# return 0 if a == b
# return -1 if a < b
# return +1 if a > b
__gesf2 = """__gesf2:
  mtc1 A0, F12
  mtc1 A1, F13

  c.eq.s F12, F13
  bc1t __gesf2_ret ; a == b
  li V0, 0

  c.lt.s F12, F13
  li V0, -1 ; a < b
  bc1t __gesf2_ret
  nop

  li V0, 1 ; a > b

  mfc1 V0, F12
__gesf2_ret:
  JR RA
  NOP"""

_FLOAT_HELPERS = [
    ("__floatsisf", __floatsisf), ("__floatunsisf", __floatsisf), ("__fixsfsi", __fixsfsi),
    ("__fixunssfsi", __fixsfsi), ("__addsf3", __addsf3), ("__subsf3", __subsf3),
    ("__negsf2", __negsf2), ("__mulsf3", __mulsf3), ("__divsf3", __divsf3),
    ("__lesf2", __lesf2), ("__gesf2", __gesf2),
]


def _include_float_helpers(assembly):
    float_ops = ""
    for name, code in _FLOAT_HELPERS:
        if name in assembly:
            float_ops += "\n" + code

    if float_ops:
        assembly += "\n; .text\n.align 4\n" + float_ops.strip(_JS_SPACE)

    return assembly
