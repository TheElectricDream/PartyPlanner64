"""hashEqual for the built-in events' code recognition (utils/arrays.ts's hash/hashEqual)."""

import hashlib


def hash(arr, start_offset, length):
    """MD5 hex digest of arr[start_offset:start_offset + length] ("" if out of bounds)."""
    # Can't be equal if our length would extend out of bounds.
    if start_offset + length > len(arr):
        return ""
    return hashlib.md5(bytes(arr[start_offset:start_offset + length])).hexdigest()


def hash_equal(hash_args, expected):
    """hash(*hash_args) == expected, ignoring case."""
    return hash(*hash_args).lower() == expected.lower()
