"""String helpers (port of mips-assembler strings.js)."""

_OCTAL = "01234567"
_HEX = "0123456789ABCDEF"
_SIMPLE_ESCAPES = {"\\": "\\", "\"": "\"", "'": "'", "?": "?", "n": "\n", "r": "\r", "t": "\t",
                   "b": "\b"}


def _is_hex_digit(ch):
    return ch is not None and len(ch) == 1 and ch.upper() in _HEX


def _is_octal_digit(ch):
    return ch is not None and len(ch) == 1 and ch in _OCTAL


def unescape_string(s):
    """Takes a string like "\\"has quotes\\"" and returns "has quotes".

    Also handles escape sequences.
    Returns the parsed string, or None if it could not be parsed.
    """
    if len(s) < 2:
        return None
    start_quote_char = s[0]
    if s[-1] != start_quote_char:
        return None
    if start_quote_char != "\"" and start_quote_char != "'":
        return None  # Not a string
    if "\\" not in s:
        return s[1:-1]

    def at(index):
        return s[index] if index < len(s) else None

    output = []
    i = 1
    end = len(s) - 1
    while i < end:
        ch = s[i]
        if ch == "\\":
            next_char = at(i + 1)
            char_two_over = at(i + 2)
            char_three_over = at(i + 3)
            if next_char in _SIMPLE_ESCAPES:
                output.append(_SIMPLE_ESCAPES[next_char])
                i += 2
                continue
            if next_char == "x":
                if not _is_hex_digit(char_two_over):
                    raise ValueError("Hex escape sequence followed by non-hex character: " + next_char)
                # This only supports \xN or \xNN currently.
                if _is_hex_digit(char_three_over):
                    output.append(chr(int(char_two_over + char_three_over, 16)))
                    i += 4
                else:
                    output.append(chr(int(char_two_over, 16)))
                    i += 3
                continue
            if _is_octal_digit(next_char):
                if _is_octal_digit(char_two_over):
                    if _is_octal_digit(char_three_over):
                        # \nnn
                        output.append(chr(int(next_char + char_two_over + char_three_over, 8)))
                        i += 4
                    else:
                        # \nn
                        output.append(chr(int(next_char + char_two_over, 8)))
                        i += 3
                else:
                    # \n
                    output.append(chr(int(next_char, 8)))
                    i += 2
                continue
        output.append(ch)
        i += 1
    return "".join(output)


def first_index_of(s, *search_tokens):
    results = [i for i in (s.find(t) for t in search_tokens) if i >= 0]
    if not results:
        return -1  # Didn't find any search token.
    return min(results)
