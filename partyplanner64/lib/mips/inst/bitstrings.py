"""Bit string helpers (port of mips-inst bitstrings.js)."""


def is_binary_literal(s):
    return s[0] == "0" or s[0] == "1"  # Checking first char is enough for now


def compare_bits(number, bit_string, bit_offset):
    shifted = ((number & 0xFFFFFFFF) >> bit_offset) & make_bit_mask(len(bit_string))
    mask = make_bit_mask_from_string(bit_string)
    return shifted == mask


def make_bit_mask_from_string(bit_string):
    mask = 0
    for ch in bit_string:
        mask = (mask << 1) | (1 if ch == "1" else 0)
    return mask


def make_bit_mask(length):
    if length <= 0:
        raise ValueError("makeBitMask cannot make mask of length %d" % length)
    return (1 << length) - 1


def pad_bit_string(s, min_len):
    return s.rjust(min_len, "0")
