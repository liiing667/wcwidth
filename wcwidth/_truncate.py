"""This is a python implementation of truncate()."""
from __future__ import annotations

# std imports
import re
from typing import Literal, Optional

# local
from ._clip import clip
from ._width import width as _width
from .hyperlink import HYPERLINK_CLOSE_RE, HyperlinkParams

# Matches any OSC 8 sequence (open or close).  The close form (empty params
# and url) matches both; test it against HYPERLINK_CLOSE_RE first to tell
# them apart.
_HYPERLINK_ANY_RE = re.compile(r'\x1b]8;[^;]*;[^\x07\x1b]*(?:\x07|\x1b\\)')
_HYPERLINK_CLOSE_AT_END_RE = re.compile(r'\x1b]8;;(?:\x07|\x1b\\)$')


def _unclosed_hyperlink_close(text: str) -> str:
    """
    Return an OSC 8 close sequence when *text* leaves a hyperlink open.

    Hyperlinks are a state attribute: an open sequence is in effect until the next close.
    Returns the close sequence matching the terminator (BEL or ST) of the last unclosed
    open, or ``''`` when everything is closed.
    """
    pending: Optional[HyperlinkParams] = None
    for match in _HYPERLINK_ANY_RE.finditer(text):
        seq = match.group()
        if HYPERLINK_CLOSE_RE.fullmatch(seq) is not None:
            pending = None
        elif (params := HyperlinkParams.parse(seq)) is not None:
            pending = params
    return pending.make_close() if pending is not None else ''


def truncate(
    text: str,
    width: int,
    ellipsis: str = '…',
    *,
    tabsize: int = 8,
    ambiguous_width: int = 1,
    control_codes: Literal['parse', 'strict', 'ignore'] = 'parse',
    term_program: bool | str = False,
) -> str:
    r"""
    Truncate text to at most *width* display columns, appending an ellipsis.

    Like :func:`str` slicing, but measured by display width: wide characters (width of 2)
    and grapheme clusters, such as emoji joined with ZWJ, are never split.  The display
    width of *ellipsis* counts against *width*::

        >>> truncate('hello world', 8)
        'hello w…'
        >>> truncate('\U0001F468\u200D\U0001F469\u200D\U0001F467 world', 4)
        '👨‍👩‍👧 …'

    Any SGR (terminal styling) state still active at the truncation point is closed
    with a reset appended to the result, and an unterminated OSC 8 hyperlink is closed.
    Styles already closed within the visible text are not closed again::

        >>> truncate('\x1b[1;31mhello world', 8)
        '\x1b[1;31mhello w…\x1b[0m'

    :param text: String to truncate, may contain terminal escape sequences.
    :param width: Maximum display width in terminal cells.
    :param ellipsis: String appended when truncation occurs (default ``'…'``).
        Its display width counts against *width*.
    :param tabsize: Tab stop width (default 8), passed to :func:`clip`.
    :param ambiguous_width: Width to use for East Asian Ambiguous (A)
        characters. Default is ``1`` (narrow). Set to ``2`` for CJK contexts.
    :param control_codes: How to handle control characters and sequences,
        passed to :func:`clip` and :func:`width`:

        - ``'parse'`` (default): Track cursor movement and clip hyperlink text.
        - ``'strict'``: Like ``'parse'``, but raises :exc:`ValueError` on
          sequences with indeterminate effects.
        - ``'ignore'``: All control characters are treated as zero-width.
    :param term_program: Terminal software identifier for table correction.
        ``False`` (default) disables override lookup.  ``True`` reads the
        ``TERM_PROGRAM`` or ``TERM`` environment variable for auto-detection.

    :returns: *text* unchanged when its display width does not exceed *width*.
        Otherwise, a truncated string ending in *ellipsis*, with any open SGR
        state and OSC 8 hyperlink closed.  Returns ``''`` when *width* is less
        than or equal to ``0``, or when *ellipsis* itself does not fit.

    .. versionadded:: 0.9.3
    """
    if width <= 0:
        return ''

    text_width = _width(
        text, control_codes=control_codes, tabsize=tabsize,
        ambiguous_width=ambiguous_width, term_program=term_program,
    )
    if text_width <= width:
        return text

    ellipsis_width = _width(
        ellipsis, control_codes=control_codes,
        ambiguous_width=ambiguous_width, term_program=term_program,
    )
    if ellipsis_width > width:
        return ''

    clipped = clip(
        text, 0, width - ellipsis_width,
        tabsize=tabsize, ambiguous_width=ambiguous_width,
        control_codes=control_codes, term_program=term_program,
    )

    # clip() propagates SGR and rebuilds hyperlinks, so the result may end
    # with a hyperlink close and/or an SGR reset, in either order.  Place the
    # ellipsis before them so it keeps the style and hyperlink of the
    # truncation point.  An already-closed style leaves the text at the
    # default state, so no reset is appended by clip() and none is duplicated
    # here.
    suffix = ''
    while True:
        if clipped.endswith('\x1b[0m'):
            suffix = '\x1b[0m' + suffix
            clipped = clipped[:-len('\x1b[0m')]
        elif close_match := _HYPERLINK_CLOSE_AT_END_RE.search(clipped):
            suffix = close_match.group() + suffix
            clipped = clipped[:close_match.start()]
        else:
            break
    result = clipped + ellipsis + suffix

    # clip() rebuilds hyperlinks whose close is inside the clip window, but a
    # hyperlink that was never closed in the source remains open: finish it.
    result += _unclosed_hyperlink_close(result)
    return result
