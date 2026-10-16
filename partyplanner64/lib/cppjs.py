"""cpp.js - Simple implementation of the C Preprocessor, ported to Python.

This is a port of the copy of cpp.js bundled with PartyPlanner64
(packages/lib/lib/cppjs/cppjs.js, https://github.com/acgessler/cpp.js).
It keeps the original's behaviour, quirks included, so that C events
preprocess exactly as they did. The original evaluated #if expressions with
JavaScript's eval(); here a small evaluator with JavaScript semantics does
that. Includes are synchronous: `include_func` calls its `resumer` before
returning.

Original licence:

cpp.js - Simple implementation of the C Preprocessor in Javascript

Copyright (c) 2011, Alexander Christoph Gessler
All rights reserved.

Redistribution and use of this software in source and binary forms,
with or without modification, are permitted provided that the
following conditions are met:

* Redistributions of source code must retain the above
  copyright notice, this list of conditions and the
  following disclaimer.

* Redistributions in binary form must reproduce the above
  copyright notice, this list of conditions and the
  following disclaimer in the documentation and/or other
  materials provided with the distribution.

* Neither the name of the cpp.js team, nor the names of its
  contributors may be used to endorse or promote products
  derived from this software without specific prior
  written permission of the cpp.js Development Team.

THIS SOFTWARE IS PROVIDED BY THE COPYRIGHT HOLDERS AND CONTRIBUTORS
"AS IS" AND ANY EXPRESS OR IMPLIED WARRANTIES, INCLUDING, BUT NOT
LIMITED TO, THE IMPLIED WARRANTIES OF MERCHANTABILITY AND FITNESS FOR
A PARTICULAR PURPOSE ARE DISCLAIMED. IN NO EVENT SHALL THE COPYRIGHT
OWNER OR CONTRIBUTORS BE LIABLE FOR ANY DIRECT, INDIRECT, INCIDENTAL,
SPECIAL, EXEMPLARY, OR CONSEQUENTIAL DAMAGES (INCLUDING, BUT NOT
LIMITED TO, PROCUREMENT OF SUBSTITUTE GOODS OR SERVICES; LOSS OF USE,
DATA, OR PROFITS; OR BUSINESS INTERRUPTION) HOWEVER CAUSED AND ON ANY
THEORY OF LIABILITY, WHETHER IN CONTRACT, STRICT LIABILITY, OR TORT
(INCLUDING NEGLIGENCE OR OTHERWISE) ARISING IN ANY WAY OUT OF THE USE
OF THIS SOFTWARE, EVEN IF ADVISED OF THE POSSIBILITY OF SUCH DAMAGE.
"""

import math
import re

__all__ = ["create", "CppError"]

# JavaScript's \s, \w and line terminators (its regular expressions differ
# from Python's on these).
_S = "\\t\\n\\v\\f\\r \\u00a0\\u1680\\u2000-\\u200a\\u2028\\u2029\\u202f\\u205f\\u3000\\ufeff"
_JS_SPACE = "\t\n\v\f\r            " \
            "      　﻿"
_W = "A-Za-z0-9_"
_DOT = "[^\\n\\r\\u2028\\u2029]"


def _trim(s):
    return s.strip(_JS_SPACE)


def _is_space(ch):
    return ch in _JS_SPACE


def _is_word(ch):
    return ("a" <= ch <= "z") or ("A" <= ch <= "Z") or ("0" <= ch <= "9") or ch == "_"


class CppError(Exception):
    """An error reported by the preprocessor (the message is what cpp.js threw)."""


def _strip_cpp_comments(s):
    # very loosely based on http://james.padolsey.com/javascript/removing-comments-in-javascript/,
    # but removed JS-specific stuff and added handling of line continuations. Also, newlines
    # are generally preserved to keep line numbers intact.
    chars = list("__" + s.replace("\r\n", "\n") + "__")
    n = len(chars)
    block_comment = line_comment = quote = False
    lines_lost = 0

    def at(i):
        return chars[i] if 0 <= i < n else None

    for i in range(n):
        if quote:
            if (chars[i] == "'" or chars[i] == "\"") and at(i - 1) != "\\":
                quote = False
            continue

        if block_comment:
            if chars[i] == "*" and at(i + 1) == "/":
                chars[i + 1] = ""
                block_comment = False
            chars[i] = ""
            # (The original then checks for a newline in the just-cleared
            # character, which never matches.)
            continue

        if line_comment:
            if at(i + 1) == "\n":
                line_comment = False
            chars[i] = ""
            continue

        if chars[i] == "\n":
            if at(i - 1) == "\\":
                # line continuation, replace by whitespace
                chars[i - 1] = ""
                chars[i] = ""
                lines_lost += 1
            else:
                while lines_lost > 0:
                    chars[i] += "\n"
                    lines_lost -= 1

        quote = chars[i] == "'" or chars[i] == "\""
        if chars[i] == "/":
            if at(i + 1) == "*":
                chars[i] = ""
                block_comment = True
                continue
            if at(i + 1) == "/":
                chars[i] = ""
                line_comment = True
                continue
    return "".join(chars)[2:-2]


def _is_string_boundary(text, idx):
    return ((text[idx] == "\"" or text[idx] == "'")
            and (not idx or text[idx - 1] != "\\" or (idx > 1 and text[idx - 2] == "\\")))


def _default_warn(s):
    import logging
    logging.getLogger("partyplanner64").warning("%s", s)


def _default_error(s):
    import logging
    logging.getLogger("partyplanner64").error("%s", s)
    raise CppError(s)


# match identifiers according to 6.4.2.1, do not match 'defined',
# do not match quote strings either
_is_identifier_re = re.compile("\\b(d(?!efined)|[a-ce-zA-Z_])[" + _W + "]*(?![" + _W + "\"])", re.ASCII)

# same, but checks if the entire string is an identifier
_is_identifier_only_re = re.compile("^(d(?!efined)|[a-ce-zA-Z_])[" + _W + "]*\\Z")

# same, but checks if the entire string is a macro
_is_macro_only_re = re.compile(
    "^((?:d(?!efined)|[a-ce-zA-Z_])[" + _W + "]*)[" + _S + "]*\\((" + _DOT + "*)\\)\\Z")

# defined <identifier>
_defined_no_parens_re = re.compile("defined[" + _S + "]+([a-zA-Z_][" + _W + "]*)")

# defined (<identifier>)
_defined_re = re.compile("defined[" + _S + "]*\\(([" + _S + "]*[a-zA-Z_][" + _W + "]*[" + _S + "]*)\\)")

# __defined_magic_<identifier>_ (a special sentinel value used to
# temporarily exclude operands to defined from macro substitution.
_defined_magic_sentinel_re = re.compile("__defined_magic_([a-zA-Z_][" + _W + "]*)_")

# Match hexadecimal, octal and decimal integer literals with or
# without L,l,U,u suffix and separate all components.
_is_integer_re = re.compile("\\b(\\+|-|)(0|0x|)([1-9a-f][0-9a-f]*|0)([ul]*)\\b", re.I | re.ASCII)

# Grab doubly quoted strings
_is_string_re = re.compile("\"(" + _DOT + "*?)\"")

# Grab compound assignments. Extra fix for !=, ==, <=, >= needed
_is_assignment_re = re.compile("[+\\-*%/&^|]?=")

# Grab instances of the increment/decrement operators
_is_increment_re = re.compile("--|\\+\\+")

# Grab <included_file> or "included_file"
_include_re = re.compile("(?:(<)(" + _DOT + "*)>|\"(" + _DOT + "*)\")(" + _DOT + "*)")

_word_space_word_re = re.compile("([" + _W + "])[" + _S + "]+([" + _W + "])")

_pragma_re = re.compile("_Pragma[" + _S + "]*\\([" + _S + "]*\"(" + _DOT + "*?([^\\\\]|\\\\\\\\))\"[" + _S
                        + "]*\\)")

# Matches a word boundary followed by a character, or a quote.
_boundary_re = re.compile("\\b" + _DOT + "|[\"']", re.ASCII)

# Magic token to signify the '##' token (to keep it from being
# treated as the operator of the same signature).
pseudo_token_doublesharp = "__doublesharp_magic__"

# Magic token to signify the ' ' token (to keep it from being
# treated as token boundary).
pseudo_token_space = "__whitespace_magic__"

pseudo_token_empty = "__empty_magic__"

pseudo_token_nosubs = "__nosubs__"

# List of preprocessing tokens.
pp_special_token_list = {
    "==", "!=", "+", "-", "*", "/", "%", "<=", ">=", "<", ">", "=", "+=", "*=", "/=", "&=",
    "|=", "^=", "#", "##", "->",
}

_TOTALLY_BLACK = 1e10

_simple_subs_cache = {}


def _block_re(signal_char):
    # generate a 3 tuple (command, arguments, code_block)
    # (JavaScript's multi-line ^ and $ also work around \r,   and  .)
    return re.compile("(?:(?<=[\\n\\r\\u2028\\u2029])|\\A)" + signal_char + "([" + _W + "]+)[ \\t]*("
                      + _DOT + "*?)[ \\t]*(?=[\\n\\r\\u2028\\u2029]|\\Z)")


class _Settings(dict):
    def __getattr__(self, name):
        return self.get(name)


class Cpp:
    """A C preprocessor instance (see `create`)."""

    def __init__(self, settings=None):
        default_settings = {
            "signal_char": "#",
            "warn_func": _default_warn,
            "error_func": _default_error,
            "comment_stripper": _strip_cpp_comments,
            "include_func": None,
            "completion_func": None,
            "pragma_func": lambda pragma: None,
        }
        if settings is not None:
            settings = _Settings(settings)
            for k, v in default_settings.items():
                if k not in settings:
                    settings[k] = v
        else:
            settings = _Settings(default_settings)

        if settings["include_func"] and not settings["completion_func"]:
            settings["error_func"]("include_func but not completion_func specified")

        # make sure that execution never continues when an error occurs.
        user_err = settings["error_func"]

        def error_func(e):
            user_err(e)
            raise CppError(e)

        settings["error_func"] = error_func
        self._settings = settings
        self._block_re = _block_re(settings["signal_char"])

        self._state = {}
        self._macro_cache = {}
        self._max_macro_length = 0
        self._macro_counts_by_length = {}

    # ----------------------
    def clear(self):
        """(public) Clear the current status code. i.e. reset all defines."""
        self._state = {}
        self._macro_counts_by_length = {}
        self._macro_cache = {}
        self._max_macro_length = 0

    def defined(self, k):
        """(public) Check if macro `k` is defined."""
        return k in self._state

    def define(self, k, v=None):
        """(public) Define macro `k` with replacement value `v`.

        To define macros with parameters, include the parameter list in the
        macro name, i.e. k <= "foo(a,b)", v <= "a ## b". The function invokes
        the error callback if the macro contains syntax errors.
        """
        macro = self._get_macro_info(k)
        if not self._is_identifier(k) and not macro:
            self._settings["error_func"]("not a valid preprocessor identifier: '" + k + "'")

        if isinstance(v, (int, float)) and not isinstance(v, bool):
            v = str(v)

        if macro:
            k = macro["name"]
            self.undefine(k)
            # This inserts the macro into the macro cache, which
            # holds pre-parsed data to simplify substitution.
            self._macro_cache[k] = macro
        else:
            self.undefine(k)

        self._state[k] = v or ""

        # macro length table housekeeping
        self._macro_counts_by_length[len(k)] = self._macro_counts_by_length.get(len(k), 0) + 1
        if len(k) > self._max_macro_length:
            self._max_macro_length = len(k)

    def undefine(self, k):
        """(public) Undefine `k`. A no-op if `k` is not defined."""
        if k in self._state:
            del self._state[k]

            # update macro length table
            nl = self._macro_counts_by_length.get(len(k), 0) - 1
            if len(k) == self._max_macro_length and not nl:
                self._max_macro_length = 0
                for i in range(len(k) - 1, -1, -1):
                    if self._macro_counts_by_length.get(i):
                        self._max_macro_length = i
                        break

            self._macro_counts_by_length[len(k)] = nl
            self._macro_cache.pop(k, None)
        else:
            # this happens if the user includes the parameter list
            # in the name. This is not part of the specification,
            # but implemented for reasons of API symmetry.
            macro = self._get_macro_info(k)
            if macro:
                self.undefine(macro["name"])

    def define_multiple(self, d):
        """(public) Given a dict of macro_name, replacement pairs, invoke `define` on all of them."""
        for k, v in d.items():
            self.define(k, v)

    # ----------------------
    def run(self, text, name=None):
        """(public) Preprocess `text` and return the preprocessed text.

        The completion callback also receives it. With an include, the
        result is only given to the completion callback, and run() returns
        None. `name` is an optional string used in error messages as file name.
        """
        settings = self._settings
        name = name or "<unnamed>"

        ctx = {"line": 1}

        # wrapped error function, augments line number and file
        def error(t):
            settings["error_func"]("(cpp) error # " + name + ":" + str(ctx["line"]) + ": " + t)

        # wrapped warning function, augments line number and file
        def warn(t):
            settings["warn_func"]("(cpp) warning # " + name + ":" + str(ctx["line"]) + ": " + t)

        if not text:
            # (The original calls its error function before defining it.)
            raise CppError("TypeError: error is not a function")

        text = settings["comment_stripper"](text)
        blocks = self._block_re.split(text)

        out = [""] * (len(blocks) // 3 + 2)
        st = {"out": out, "outi": 0, "ifs_failed": 0, "command": None}
        if_stack = []

        def set_out(value):
            o = st["out"]
            if st["outi"] < len(o):
                o[st["outi"]] = value
            else:
                o.extend([None] * (st["outi"] - len(o)))
                o.append(value)
            st["outi"] += 1

        def process_directive(command, elem, i):
            if command == "define":
                head = tail = None
                elem = _trim(elem)

                # (None stands for undefined; decrementing undefined gives NaN.)
                par_count = None
                for j in range(len(elem)):
                    if elem[j] == "(":
                        par_count = (par_count if isinstance(par_count, int) else 0) + 1 \
                            if par_count != "NaN" else "NaN"
                    else:
                        close = False
                        if elem[j] == ")":
                            if isinstance(par_count, int):
                                par_count -= 1
                                close = par_count == 0
                            else:
                                par_count = "NaN"
                        if close or (_is_space(elem[j]) and par_count is None):
                            if elem[j] == ")":
                                j += 1
                            head = elem[:j]
                            tail = _trim(elem[j:])
                            break

                if isinstance(par_count, int) and par_count:
                    error("unbalanced parentheses in define: " + elem)

                if head is None:
                    head = elem

                if self.defined(head):
                    warn(head + " redefined")

                if not self._is_identifier(head) and not self._is_macro(head):
                    error("not a valid preprocessor identifier: '" + head + "'")

                self.define(head, tail)

            elif command == "undef":
                self.undefine(elem)

            elif command == "include":
                elem = self.subs(elem, {}, error, warn)
                parts = _include_re.search(elem)
                if parts is None:
                    raise CppError("TypeError: Cannot read properties of null (reading '4')")
                if parts.group(4):
                    error("unrecognized characters in include: " + elem)
                file = (parts.group(2) or "") + (parts.group(3) or "")

                if not settings["include_func"]:
                    error("include directive not supported, no handler specified")

                def resumer(contents):
                    if contents is None:
                        error("failed to access include file: " + file)
                    s = _Settings(settings)

                    processor_box = []

                    def completion_func(data, lines, new_state):
                        del st["out"][st["outi"]:]
                        st["outi"] += len(lines)
                        st["out"] = st["out"] + list(lines)

                        # grab any state changes
                        self._set_state(processor_box[0])

                        for k in range(i + 1, len(blocks)):
                            if not process_block(k, blocks[k]):
                                return False
                        self._result(st["out"], self._state)

                    s["completion_func"] = completion_func

                    # construct a child preprocessor and let it share our
                    # state.
                    processor = Cpp(s)
                    processor_box.append(processor)
                    processor._set_state(self)
                    processor.run(contents, file)

                settings["include_func"](file, parts.group(1) == "<", resumer)
                return False

            elif command == "error":
                error("#error: " + elem)

            elif command == "pragma":
                if not settings["pragma_func"](elem):
                    warn("ignoring unrecognized #pragma: " + elem)

            else:
                warn("unrecognized preprocessor command: " + str(command))
            return True

        def process_block(i, elem):
            elem = blocks[i]
            kind = i % 3
            if kind == 0:
                # code line, apply macro substitutions and copy to output.
                ctx["line"] += elem.count("\n")
                if not st["ifs_failed"] and len(_trim(elem)):
                    # (The original passes its error and warn functions one
                    # argument off, so errors in code lines are warnings.)
                    set_out(self.subs(elem, None, warn, None))
            elif kind == 1:
                # preprocessor statement, such as ifdef, endif, ..
                st["command"] = elem
            else:
                # the rest of the preprocessor line, this is where expression
                # evaluation happens
                command = st["command"]
                done = True
                if command in ("ifdef", "ifndef", "if", "else", "elif"):
                    if command in ("ifdef", "ifndef"):
                        if not elem:
                            error("expected identifier after " + command)
                        # translate ifdef/ifndef to regular if by using defined()
                        elem = "(defined " + elem + ")"
                        if command == "ifndef":
                            elem = "!" + elem
                    if command in ("ifdef", "ifndef", "if"):
                        if_stack.append(False)
                        if not len(elem):
                            error("expected identifier after if")

                    not_reached = False
                    if command in ("elif", "else"):
                        not_reached = if_stack[-1] if if_stack else None
                        if st["ifs_failed"] > 0:
                            st["ifs_failed"] -= 1
                        if command == "else" and len(elem):
                            warn("ignoring tokens after else")

                    if (st["ifs_failed"] > 0 or not_reached
                            or (command != "else" and not self._eval(elem, error, warn))):
                        st["ifs_failed"] += 1
                    else:
                        # we run self branch, so skip any further else/
                        # elsif branches
                        if if_stack:
                            if_stack[-1] = True
                elif command == "endif":
                    if not if_stack:
                        error("endif with no matching if")
                    if st["ifs_failed"] > 0:
                        st["ifs_failed"] -= 1
                    if if_stack:
                        if_stack.pop()
                    # ignore trailing junk on endifs
                else:
                    done = st["ifs_failed"] > 0

                # not done yet, so this is a plain directive (i.e. include)
                if not done:
                    if not process_directive(command, elem, i):
                        return False
            return True

        for i in range(len(blocks)):
            if not process_block(i, blocks[i]):
                return None

        if if_stack:
            error("unexpected EOF, expected endif")

        return self._result(st["out"], self._state)

    # ----------------------
    def subs(self, text, blacklist_in=None, error=None, warn=None, nest_sub=0):
        """(public) Given a `text`, substitute macros until no further substitutions are possible.

        `blacklist_in` is an optional set of macro names to be ignored, these
        are not substituted and remain as is.
        """
        error = error or self._settings["error_func"]
        warn = warn or self._settings["warn_func"]

        # create a copy of the blacklist and make sure that all incoming
        # macros are totally blacked out.
        blacklist = {}
        if blacklist_in:
            for k in blacklist_in:
                blacklist[k] = _TOTALLY_BLACK

        nest_sub = nest_sub or 0
        state = self._state
        counts = self._macro_counts_by_length

        new_text = text
        pieces = []
        in_string = False
        pos = 0

        # XXX This scales terribly. Possible optimization:
        #   use KMP for substring searches
        while True:
            m_boundary = _boundary_re.search(new_text, pos)
            if not m_boundary:
                break
            idx = m_boundary.start()
            pos = m_boundary.end()
            if _is_string_boundary(new_text, idx):
                in_string = not in_string

            if in_string:
                continue

            for i in range(min(len(new_text) - idx, self._max_macro_length), 0, -1):
                if not counts.get(i):
                    continue
                k = new_text[idx:idx + i]
                if k not in state:
                    continue

                # if this would be a match, but the macro is blacklisted,
                # we need to skip it alltogether or parts of it might be
                # interpreted as macros on their own.
                if blacklist.get(k, -math.inf) > idx:
                    pieces.append(new_text[:idx])
                    pieces.append(pseudo_token_nosubs + k)
                    new_text = new_text[idx + len(k):]
                    pos = 0

                    # adjust blacklist indices
                    for kk in list(blacklist):
                        if blacklist[kk] != _TOTALLY_BLACK:
                            if blacklist[kk] > idx:
                                blacklist[kk] -= idx + len(k)
                            else:
                                del blacklist[kk]
                    break
                else:
                    blacklist.pop(k, None)

                if self._is_macro(k):
                    sub = self._subs_macro(new_text, k, {}, error, warn, nest_sub, idx)
                else:
                    sub = self._subs_simple(new_text, k, {}, error, warn, nest_sub, idx)
                if sub is None:
                    continue

                # handle # and ## operator
                sub[0] = self._handle_ops(sub[0], error, warn)

                # handle _Pragma()
                sub[0] = self._handle_pragma(sub[0], error, warn)

                # XXX a bit too expensive ... but not too easy to avoid.
                pieces.append(new_text[:idx])
                new_text = sub[0] + new_text[idx + sub[1]:]
                pos = 0

                # adjust blacklist indices
                for kk in list(blacklist):
                    if blacklist[kk] != _TOTALLY_BLACK:
                        if blacklist[kk] > idx:
                            blacklist[kk] = (len(sub[0]) - sub[1]) + (blacklist[kk] - idx)
                        else:
                            del blacklist[kk]

                # rescan this string, but keep the macro that we just replaced
                # blacklisted until we're beyond the replacement. This
                # prevents infinite recursion and is also mandated by the
                # standard and crucial for proper evaluation of several of
                # its more ... evil ehm elaborate samples.
                blacklist[k] = len(sub[0])
                break

        pieces.append(new_text)
        new_text = "".join(pieces)

        # if macro substitution is complete, re-introduce any
        # '##' tokens previously substituted in order to keep them
        # from being treated as operators. Same for spaces and empty
        # tokens.
        if not nest_sub:
            new_text = self._remove_sentinels(new_text)

        return new_text

    # ----------------------
    def _set_state(self, other):
        """Transfer the state from another cpp.js instance to us."""
        other = other._get_state()
        self._state = other["state"]
        self._macro_counts_by_length = other["macro_counts_by_length"]
        self._macro_cache = other["macro_cache"]
        self._max_macro_length = other["max_macro_length"]

    def _get_state(self):
        """Get a dictionary containing the full processing state of us."""
        return {
            "state": self._state,
            "macro_counts_by_length": self._macro_counts_by_length,
            "macro_cache": self._macro_cache,
            "max_macro_length": self._max_macro_length,
        }

    def _result(self, arr, state):
        """Merges the output lines, invokes the completion callback and returns the text."""
        # drop empty lines at the end
        while arr and not arr[-1]:
            arr.pop()

        text = "\n".join(a or "" for a in arr)
        if self._settings["completion_func"]:
            self._settings["completion_func"](text, arr, state)
        return text

    def _is_identifier(self, identifier):
        """Check if `identifier` is a well-formed identifier according to C rules."""
        return bool(_is_identifier_only_re.match(identifier))

    def _is_macro(self, macro):
        """Check if `macro` is a well-formed macro name."""
        return self._get_macro_info(macro) is not None

    def _is_pp_special_token(self, tok):
        """Check if `tok` is a special preprocessor token (such as ==, <=, >=)."""
        return _trim(tok) in pp_special_token_list

    def _get_macro_info(self, k):
        """Get the description dict for a macro named `k`, or None if malformed."""
        cached = self._macro_cache.get(k)
        if cached:
            return cached

        m = _is_macro_only_re.match(k)
        if not m:
            return None

        params = m.group(2).split(",")
        if len(params) == 1 and not _trim(params[0]):
            # parameterless macro (i.e. #define p () )
            params = []
        else:
            for i in range(len(params)):
                t = params[i] = _trim(params[i])
                if not self._is_identifier(t) and not self._is_macro(t):
                    return None

        pat = re.compile(m.group(1) + "[" + _S + "]*\\(")
        return {"params": params, "pat": pat, "name": m.group(1), "full": k}

    def _remove_sentinels(self, new_text):
        """Remove all sentinel strings from the given string."""
        new_text = new_text.replace(pseudo_token_doublesharp, "##")
        new_text = new_text.replace(pseudo_token_space, " ")
        new_text = new_text.replace(pseudo_token_empty, "")
        new_text = new_text.replace(pseudo_token_nosubs, "")
        return new_text

    def _handle_pragma(self, text, error, warn):
        """Evaluate the _Pragma(string) preprocessor operator."""
        if "_Pragma" not in text:
            return text

        def repl(match):
            pragma = match.group(1)
            # destringize
            pragma = pragma.replace("\\\"", "\"").replace("\\\\", "\\")
            pragma = self._remove_sentinels(pragma)
            pragma = self._concatenate_strings(pragma)

            if not self._settings["pragma_func"](pragma):
                warn("unrecognized _Pragma(): " + pragma)

            # always substitute an empty string so processing
            # can continue.
            return ""

        # XXX obviously RE aren't sufficient here either, do proper parse.
        return _pragma_re.sub(repl, text)

    def _concatenate_strings(self, text):
        """Concatenate neighbouring string literals such as " hello " "world "."""
        in_string = False
        last = None
        last_taken = 0
        text_out = []
        for i in range(len(text)):
            if _is_string_boundary(text, i):
                if in_string:
                    last = i
                elif last is not None:
                    text_out.append(text[last_taken:last])
                    last_taken = i + 1
                in_string = not in_string
            elif not _is_space(text[i]):
                text_out.append(text[last_taken:i])
                last_taken = i
                last = None
        text_out.append(text[last_taken:])
        return "".join(text_out)

    def _handle_ops(self, text, error, warn):
        """Evaluate the '##' and '#' preprocessor operators."""
        if "#" not in text:
            return text

        # XXX The code below is not only extremely slow, it also doesn't
        # take into account that the # operator can only be applied to
        # macro parameter, an information that is no longer available
        # at this point.

        # 6.10.3.2: "The order of evaluation of # and ## operators
        # is unspecified.". We pick '##' first.
        in_string = False
        op = 0
        while op < len(text) - 1:
            if _is_string_boundary(text, op):
                in_string = not in_string
                op += 1
                continue

            if text[op] != "#" or in_string:
                op += 1
                continue

            is_concat = text[op + 1] == "#"
            left = None
            right = None

            # identify the tokens on either side of the ## operator or
            # only on the right side of the # operator.
            in_inner_string = False
            nest = 0
            if is_concat:
                i = op - 1
                while i >= 0:
                    if not _is_space(text[i]):
                        if _is_string_boundary(text, i):
                            in_inner_string = not in_inner_string
                        elif text[i] == "(":
                            nest += 1
                        elif text[i] == ")":
                            nest -= 1
                        left = text[i] + (left or "")
                    elif left is not None:
                        if not in_inner_string and not nest:
                            break
                        left = " " + left
                    i -= 1
                i += 1
            else:
                i = op

            in_inner_string = False
            nest = 0

            first_space = True
            j = op + (2 if is_concat else 1)
            while j < len(text):
                if not _is_space(text[j]):
                    first_space = True
                    if _is_string_boundary(text, j):
                        in_inner_string = not in_inner_string
                    elif text[j] == "(":
                        nest += 1
                    elif text[j] == ")":
                        nest -= 1
                    right = (right or "") + text[j]
                elif right is not None and not in_inner_string and not nest:
                    break
                else:
                    # 6.10.3.2 (#): each occurrence of white space between the
                    # argument's preprocessing tokens becomes a single space
                    # character in the character string literal
                    if (is_concat or first_space or in_inner_string) and right is not None:
                        right = right + " "
                        first_space = False
                j += 1

            right = _trim(right or "")

            if is_concat:
                left = _trim(left or "")
                if not right or not left:
                    error("## cannot appear at either end of a macro expansion")

                # To my reading of the standard, it works like this:
                # if both sides are *not* preprocessing special tokens,
                # the concatenation is always ok. Otherwise the result
                # must be a valid preprocessing special token as well.
                if ((self._is_pp_special_token(left) or self._is_pp_special_token(right))
                        and not self._is_pp_special_token(left + right)):
                    error("pasting \"" + left + "\" and \"" + right
                          + "\" does not give a valid preprocessing token")

                # the result of the concatenation is another token, but
                # we must take care that the '##' token is not treated
                # as concatenation operator in further replacements.
                concat = left + right
                if concat == "##":
                    concat = pseudo_token_doublesharp
                else:
                    # tokens that we marked as no longer available for
                    # substitution become available again when they're
                    # concatenated with other tokens.
                    concat = concat.replace(pseudo_token_nosubs, "")
            else:
                if not right:
                    error("# cannot appear at the end of a macro expansion")
                concat = "\"" + right.replace("\\", "\\\\").replace("\"", "\\\"") + "\""

            pieces = [text[:i], concat]
            if j < len(text):
                pieces.append(text[j:])
            text = "".join(pieces)

            # (The original restarts at 0, then its loop increments.)
            op = 1

        return text

    def _subs_simple(self, text, macro_name, blacklist_in, error, warn, nest_sub, start_idx):
        """Substitute a simple macro (no parameter list) found at `start_idx`.

        Returns [substitution, substituted length], or None.
        """
        # no macro but just a parameterless substitution
        rex = _simple_subs_cache.get(macro_name)
        if rex is None:
            rex = re.compile(macro_name + "(\\b|" + pseudo_token_space + "|" + pseudo_token_empty + ")",
                             re.ASCII)
            if len(_simple_subs_cache) < 10000:
                _simple_subs_cache[macro_name] = rex

        m_found = rex.search(text, start_idx or 0)
        if not m_found or m_found.start() != start_idx:
            return None

        return [self._state[macro_name], len(m_found.group(0))]

    def _subs_macro(self, text, macro_name, blacklist, error, warn, nest_sub, start_idx):
        """Substitute a macro with parameters found at `start_idx`.

        Returns [substitution, substituted length], or None.
        """
        info = self._get_macro_info(macro_name)

        m_found = info["pat"].search(text, start_idx or 0)
        if not m_found or m_found.start() != start_idx:
            return None

        params_found = []
        last = 0
        nest = -1
        in_string = False

        # here macro invocations may be nested, so a regex is not
        # sufficient to "parse" this.
        for i in range(m_found.start(), len(text)):
            ch = text[i]
            if ch == "," and not nest:
                params_found.append(_trim(text[last:i]))
                last = i + 1

            if ch == "(":
                nest += 1
                if nest == 0:
                    last = i + 1
            elif (ch == "\"" or ch == "'") and (not i or text[i - 1] != "\\"):
                if in_string:
                    nest -= 1
                else:
                    nest += 1
                in_string = not in_string
            elif ch == ")":
                nest -= 1
                if nest == -1:
                    params_found.append(_trim(text[last:i]))
                    last = i + 1
                    break

        if nest != -1:
            error("unbalanced parentheses, expected )")

        if len(params_found) != len(info["params"]):
            # special case: if no arguments are expected and none passed either,
            # we will still get one empty argument from the previous logic.
            if info["params"] or len(params_found) > 1 or (params_found and params_found[0]):
                error("illegal invocation of macro " + macro_name + ", expected "
                      + str(len(info["params"])) + " parameters but got " + str(len(params_found)))
            else:
                params_found = []

        # macro parameters may potentially be empty, but this would lead
        # to trouble in subsequent substitutions. So substitute a sentinel
        # string.
        for i in range(len(params_found)):
            if not params_found[i]:
                params_found[i] = pseudo_token_empty

        # insert arguments into replacement list, but evaluate them
        # PRIOR to doing this (6.10.3.1). We need, however, to
        # exclude all arguments directly preceeded or succeeded by
        # either the stringization or the token concatenation operator
        repl = self._state[macro_name]

        for i in range(len(info["params"])):
            if i >= len(params_found):
                raise CppError("TypeError: Cannot read properties of undefined (reading 'replace')")
            # what applies to empty parameter applies to whitespace in the
            # parameter text as well (only whitespace that concates two
            # otherwise distinct tokens). Substitute by a magic sentinel.
            # This must be done PRIOR to evaluating the parameters -
            # a parameter might evaluate to something like '2, 4'
            # which should obviously not be escaped.
            param_subs = _word_space_word_re.sub("\\1" + pseudo_token_space + "\\2", params_found[i])
            param_subs = self.subs(param_subs, blacklist, error, warn, nest_sub + 1)

            rex = re.compile(info["params"][i] + "\\b", re.ASCII)
            ignore = False
            pieces = []
            bound = True
            j = 0
            while j < len(repl):
                if repl[j] == "#":
                    ignore = True
                else:
                    m = rex.match(repl, j) if bound else None
                    if m:
                        if not ignore:
                            for k in range(m.end(), len(repl)):
                                if repl[k] == "#":
                                    ignore = True
                                elif not _is_space(repl[k]):
                                    break

                        pieces.append(repl[:j])
                        pieces.append(params_found[i] if ignore else param_subs)
                        repl = repl[m.end():]
                        j = 0
                        continue
                    elif not _is_space(repl[j]):
                        ignore = False
                bound = not _is_word(repl[j])
                j += 1

            pieces.append(repl)
            repl = "".join(pieces)
        return [repl, last - start_idx]

    def _eval(self, val, error, warn):
        """Evaluate a raw and not yet preprocessed expression from a #if/#ifdef clause."""
        old_val = val
        # see 6.10.1.2-3

        # string literals are not allowed
        if _is_string_re.search(val):
            error("string literal not allowed in if expression")

        # neither are assignment or compound assignment ops
        if _is_assignment_re.search(re.sub("[=!<>]=", "", val)):
            error("assignment operator not allowed in if expression")

        # same for increment/decrement - we need to catch these
        # cases because they might be used to exploit eval().
        if _is_increment_re.search(val):
            error("--/++ operators not allowed in if expression")

        # XXX handle character constants

        # drop the L,l,U,u suffixes for integer literals
        val = _is_integer_re.sub(lambda m: m.group(1) + m.group(2) + m.group(3), val)

        # macro substitution - but do not touch unary operands to 'defined',
        # this is done by substituting a safe sentinel value (which starts
        # with two underscores and is thus reserved).
        val = _defined_no_parens_re.sub(lambda m: "defined(" + m.group(1) + ")", val)
        val = _defined_re.sub(lambda m: " __defined_magic_" + m.group(1) + "_ ", val)

        val = self.subs(val, {}, error, warn)

        # re-substitute defined() terms and quote the argument
        val = _defined_magic_sentinel_re.sub(lambda m: "defined(\"" + m.group(1) + "\")", val, count=1)

        # replace all remaining identifiers with '0'
        val = _is_identifier_re.sub(" 0 ", val)

        # what remains _should_ be safe to evaluate since it doesn't contain
        # any identifiers (the original used a masked eval() here).
        res = None
        try:
            res = _js_truthy(_JsExpr("(" + val + ")", self.defined).evaluate())
        except _JsEvalError as e:
            error("error in expression: " + old_val + " (" + str(e) + ")")

        return res


def create(settings=None):
    """Creates a preprocessor instance.

    `settings` is a dict with any of: signal_char, warn_func, error_func,
    pragma_func, include_func(file, is_global, resumer), completion_func(text,
    lines, state), comment_stripper.
    """
    return Cpp(settings)


# A small evaluator for the JavaScript expressions #if conditions become.

class _JsEvalError(Exception):
    pass


class _DefinedFn:
    """The `defined` function value."""


def _js_truthy(v):
    if isinstance(v, bool):
        return v
    if isinstance(v, (int, float)):
        return not (v == 0 or (isinstance(v, float) and math.isnan(v)))
    if isinstance(v, str):
        return v != ""
    return v is not None


def _to_number(v):
    if isinstance(v, bool):
        return int(v)
    if isinstance(v, (int, float)):
        return v
    if isinstance(v, str):
        s = v.strip(_JS_SPACE)
        if not s:
            return 0
        try:
            if s[:2].lower() == "0x":
                return int(s[2:], 16)
            f = float(s)
            return int(f) if f.is_integer() and abs(f) < 2 ** 53 else f
        except ValueError:
            return math.nan
    return math.nan


def _to_int32(v):
    n = _to_number(v)
    if isinstance(n, float):
        if math.isnan(n) or math.isinf(n):
            return 0
        n = int(n)
    n &= 0xFFFFFFFF
    return n - 0x100000000 if n & 0x80000000 else n


def _norm(n):
    if isinstance(n, float) and n.is_integer() and abs(n) < 2 ** 53:
        return int(n)
    return n


_token_re = re.compile(
    "[" + _S + "]+"
    "|(?P<num>0[xX][0-9a-fA-F]+|0[bB][01]+|0[oO][0-7]+|(?:\\d+\\.?\\d*|\\.\\d+)(?:[eE][+-]?\\d+)?)"
    "|(?P<str>\"(?:[^\"\\\\\\n]|\\\\.)*\"|'(?:[^'\\\\\\n]|\\\\.)*')"
    "|(?P<id>[A-Za-z_$][A-Za-z0-9_$]*)"
    "|(?P<op>>>>|===|!==|\\*\\*|<<|>>|<=|>=|==|!=|&&|\\|\\||[-+*/%<>!~&|^?:(),])")


class _JsExpr:
    def __init__(self, src, defined):
        self.defined = defined
        self.tokens = []
        pos = 0
        while pos < len(src):
            m = _token_re.match(src, pos)
            if not m or m.end() == pos:
                raise _JsEvalError("SyntaxError: Invalid or unexpected token")
            pos = m.end()
            if m.group("num") is not None:
                self.tokens.append(("num", m.group("num")))
            elif m.group("str") is not None:
                self.tokens.append(("str", m.group("str")))
            elif m.group("id") is not None:
                self.tokens.append(("id", m.group("id")))
            elif m.group("op") is not None:
                self.tokens.append(("op", m.group("op")))
        self.i = 0

    def peek(self):
        return self.tokens[self.i] if self.i < len(self.tokens) else (None, None)

    def take_op(self, *ops):
        kind, value = self.peek()
        if kind == "op" and value in ops:
            self.i += 1
            return value
        return None

    def unexpected(self):
        kind, value = self.peek()
        if kind is None:
            return _JsEvalError("SyntaxError: Unexpected end of input")
        if kind == "num":
            return _JsEvalError("SyntaxError: Unexpected number")
        if kind == "str":
            return _JsEvalError("SyntaxError: Unexpected string")
        if kind == "id":
            return _JsEvalError("SyntaxError: Unexpected identifier '%s'" % value)
        return _JsEvalError("SyntaxError: Unexpected token '%s'" % value)

    def expect(self, op):
        if not self.take_op(op):
            raise self.unexpected()

    def evaluate(self):
        v = self.comma()
        if self.i < len(self.tokens):
            raise self.unexpected()
        return v

    def comma(self):
        v = self.conditional()
        while self.take_op(","):
            v = self.conditional()
        return v

    def conditional(self):
        cond = self.binary(0)
        if self.take_op("?"):
            a = self.conditional()
            self.expect(":")
            b = self.conditional()
            return a if _js_truthy(cond) else b
        return cond

    _LEVELS = [
        ("||",), ("&&",), ("|",), ("^",), ("&",), ("==", "!=", "===", "!=="),
        ("<", ">", "<=", ">="), ("<<", ">>", ">>>"), ("+", "-"), ("*", "/", "%"),
    ]

    def binary(self, level):
        if level == len(self._LEVELS):
            return self.exponent()
        v = self.binary(level + 1)
        while True:
            op = self.take_op(*self._LEVELS[level])
            if not op:
                return v
            if op == "||":
                rhs = self.binary(level + 1)
                v = v if _js_truthy(v) else rhs
            elif op == "&&":
                rhs = self.binary(level + 1)
                v = rhs if _js_truthy(v) else v
            else:
                v = _binop(op, v, self.binary(level + 1))

    def exponent(self):
        v = self.unary()
        if self.take_op("**"):
            return _binop("**", v, self.exponent())
        return v

    def unary(self):
        op = self.take_op("!", "~", "-", "+")
        if op:
            v = self.unary()
            if op == "!":
                return not _js_truthy(v)
            if op == "~":
                return ~_to_int32(v)
            n = _to_number(v)
            if op == "-":
                return -n
            return n
        return self.primary()

    def primary(self):
        kind, value = self.peek()
        if kind is None or (kind == "op" and value != "("):
            raise self.unexpected()
        self.i += 1
        if kind == "num":
            return _parse_js_number(value)
        if kind == "str":
            return value[1:-1]
        if kind == "id":
            if value == "defined":
                if self.take_op("("):
                    arg = self.comma()
                    self.expect(")")
                    return self.defined(arg if isinstance(arg, str) else _js_str(arg))
                return _DefinedFn()
            if value == "true":
                return True
            if value == "false":
                return False
            raise _JsEvalError("ReferenceError: %s is not defined" % value)
        if value == "(":
            v = self.comma()
            self.expect(")")
            return v
        raise _JsEvalError("SyntaxError: Unexpected token '%s'" % value)


def _parse_js_number(s):
    low = s.lower()
    if low.startswith("0x"):
        return int(s[2:], 16)
    if low.startswith("0b"):
        return int(s[2:], 2)
    if low.startswith("0o"):
        return int(s[2:], 8)
    if len(s) > 1 and s[0] == "0" and s.isdigit():
        # Legacy octal literals (sloppy mode); 08 and 09 are decimal.
        return int(s, 8) if all(c in "01234567" for c in s) else int(s, 10)
    if s.isdigit():
        return int(s)
    return _norm(float(s))


def _js_str(v):
    if isinstance(v, bool):
        return "true" if v else "false"
    if isinstance(v, float):
        if math.isnan(v):
            return "NaN"
        if v.is_integer():
            return str(int(v))
        return repr(v)
    return str(v)


def _binop(op, a, b):
    if op in ("==", "!=", "===", "!=="):
        if op in ("===", "!=="):
            same_type = (isinstance(a, bool) == isinstance(b, bool)) and \
                        (isinstance(a, str) == isinstance(b, str))
            eq = same_type and a == b
            if isinstance(a, _DefinedFn) or isinstance(b, _DefinedFn):
                eq = a is b
        else:
            if isinstance(a, _DefinedFn) or isinstance(b, _DefinedFn):
                eq = a is b
            elif isinstance(a, str) and isinstance(b, str):
                eq = a == b
            else:
                eq = _to_number(a) == _to_number(b)
        return eq if op in ("==", "===") else not eq
    if op in ("<", ">", "<=", ">="):
        if isinstance(a, str) and isinstance(b, str):
            x, y = a, b
        else:
            x, y = _to_number(a), _to_number(b)
            if (isinstance(x, float) and math.isnan(x)) or (isinstance(y, float) and math.isnan(y)):
                return False
        return {"<": x < y, ">": x > y, "<=": x <= y, ">=": x >= y}[op]
    if op in ("&", "|", "^"):
        x, y = _to_int32(a), _to_int32(b)
        r = x & y if op == "&" else (x | y if op == "|" else x ^ y)
        return _to_int32(r)
    if op in ("<<", ">>", ">>>"):
        x = _to_int32(a)
        s = _to_int32(b) & 31
        if op == "<<":
            return _to_int32(x << s)
        if op == ">>":
            return x >> s
        return (x & 0xFFFFFFFF) >> s
    if op == "+" and (isinstance(a, str) or isinstance(b, str)):
        return _js_str(a) + _js_str(b)
    x, y = _to_number(a), _to_number(b)
    try:
        if op == "+":
            return _norm(x + y)
        if op == "-":
            return _norm(x - y)
        if op == "*":
            return _norm(x * y)
        if op == "/":
            if y == 0:
                if x == 0 or (isinstance(x, float) and math.isnan(x)):
                    return math.nan
                return math.copysign(math.inf, x) * math.copysign(1, y)
            return _norm(x / y)
        if op == "%":
            if y == 0:
                return math.nan
            return _norm(math.fmod(x, y)) if isinstance(x, float) or isinstance(y, float) \
                else (abs(x) % abs(y)) * (1 if x >= 0 else -1)
        if op == "**":
            return _norm(x ** y)
    except (OverflowError, ValueError, ZeroDivisionError):
        return math.nan
    raise _JsEvalError("SyntaxError: Unexpected token '%s'" % op)
