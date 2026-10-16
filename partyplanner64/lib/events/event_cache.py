"""Stores junk that the events want to keep around.

In particular, cached data from parsing the original game events.
"""

_cache = {}


class EventCache:
    @staticmethod
    def get(key):
        return _cache.get(key)

    @staticmethod
    def set(key, value):
        _cache[key] = value
