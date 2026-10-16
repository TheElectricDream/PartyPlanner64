"""Preprocesses C event code (port of utils/c-preprocessor.ts), using the cpp.js port."""

import logging

from .. import cppjs

_logger = logging.getLogger("partyplanner64")


class PreprocessError(ValueError):
    """The preprocessor reported an error; the message is cpp.js's."""


def preprocess(contents):
    """Preprocess a given file (C source). Returns the preprocessed text.

    `#include <ultra64.h>` (or "ultra64.h") is supported; other includes fail.
    """
    result = []

    def include_func(file, is_global, resumer):
        if file.lower() == "ultra64.h":
            from ..events.includes.ultra64h import ultra64h
            resumer(ultra64h)
            return
        # TODO: Handle other file includes.
        resumer(None)

    def completion_func(preprocessed_text, lines=None, state=None):
        if not result:
            result.append(preprocessed_text)

    def warn_func(message):
        _logger.warning("%s", message)

    def error_func(message):
        _logger.error("%s", message)

    preprocessor = cppjs.create({
        "include_func": include_func,
        "completion_func": completion_func,
        "warn_func": warn_func,
        "error_func": error_func,
    })

    try:
        preprocessor.run(contents)
    except cppjs.CppError as e:
        raise PreprocessError(str(e)) from None

    return result[0] if result else ""
