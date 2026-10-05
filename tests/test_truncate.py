"""Tests for truncate() function."""

# local
from wcwidth import width, truncate

SGR_RED = '\x1b[31m'
SGR_BOLD_RED = '\x1b[1;31m'
SGR_RESET = '\x1b[0m'
HL_OPEN = '\x1b]8;;http://example.com\x07'
HL_CLOSE = '\x1b]8;;\x07'
HL_OPEN_ST = '\x1b]8;;http://example.com\x1b\\'
HL_CLOSE_ST = '\x1b]8;;\x1b\\'
EMOJI_FAMILY = '\U0001F468\u200D\U0001F469\u200D\U0001F467'


def test_truncate_fits():
    """Text within width is returned unchanged."""
    assert truncate('', 5) == ''
    assert truncate('hello', 5) == 'hello'
    assert truncate('hello', 10) == 'hello'
    assert truncate('hello world', 11) == 'hello world'
    # sequences are preserved as-is when no truncation occurs
    assert truncate(f'{SGR_RED}hi{SGR_RESET}', 10) == f'{SGR_RED}hi{SGR_RESET}'
    assert truncate(f'{HL_OPEN}hi{HL_CLOSE}', 10) == f'{HL_OPEN}hi{HL_CLOSE}'


def test_truncate_basic():
    """Text is truncated to width, ellipsis included in the budget."""
    assert truncate('hello world', 10) == 'hello wor…'
    assert truncate('hello world', 8) == 'hello w…'
    assert truncate('hello world', 5) == 'hell…'
    assert truncate('hello', 1) == '…'
    assert width(truncate('hello world', 8)) == 8


def test_truncate_nonpositive_width():
    """A width of zero or less always yields an empty string."""
    assert truncate('hello', 0) == ''
    assert truncate('hello', -1) == ''
    assert truncate('', 0) == ''


def test_truncate_ellipsis_too_wide():
    """An ellipsis that does not fit yields an empty string."""
    assert truncate('hello', 2, ellipsis='...') == ''
    assert truncate('hello', 0, ellipsis='...') == ''
    # U+2026 is East Asian Ambiguous: width 2 in CJK contexts
    assert truncate('hello', 1, ambiguous_width=2) == ''
    assert truncate('hello world', 5, ambiguous_width=2) == 'hel…'


def test_truncate_custom_ellipsis():
    """Custom and empty ellipsis strings are honored."""
    assert truncate('hello world', 6, ellipsis='...') == 'hel...'
    assert truncate('hello world', 5, ellipsis='') == 'hello'
    assert truncate('hello world', 8, ellipsis='~') == 'hello w~'


def test_truncate_wide_characters():
    """Wide characters are never split by the truncation point."""
    assert truncate('中文字', 5) == '中文…'
    assert truncate('中文字', 4) == '中 …'
    assert truncate('中文字', 2) == ' …'
    assert truncate('中文字', 1) == '…'
    assert width(truncate('中文字', 5)) == 5


def test_truncate_grapheme_clusters():
    """Grapheme clusters (ZWJ emoji, combining marks) are kept whole."""
    assert truncate(f'{EMOJI_FAMILY}ab', 3) == f'{EMOJI_FAMILY}…'
    assert truncate(f'{EMOJI_FAMILY}ab', 2) == ' …'
    assert truncate(EMOJI_FAMILY, 2) == EMOJI_FAMILY
    # combining mark stays attached to its base character
    assert truncate('cafe\u0301xy', 5) == 'cafe\u0301…'
    assert width(truncate('cafe\u0301xy', 5)) == 5


def test_truncate_sgr_open_style_closed():
    """An SGR style still open at the truncation point is reset at the end."""
    result = truncate(f'{SGR_BOLD_RED}hello world', 8)
    assert result == f'{SGR_BOLD_RED}hello w…{SGR_RESET}'
    assert width(result) == 8


def test_truncate_sgr_already_closed_not_duplicated():
    """A style closed within the visible text is not closed again."""
    result = truncate(f'{SGR_RED}red{SGR_RESET} normal text', 10)
    assert result == f'{SGR_RED}red{SGR_RESET} norma…'
    assert result.count(SGR_RESET) == 1


def test_truncate_sgr_style_change_inside():
    """Style changes inside the kept region are preserved."""
    result = truncate(f'{SGR_RED}red\x1b[32mgreen tail', 9)
    assert result == f'{SGR_RED}red\x1b[32mgreen…{SGR_RESET}'


def test_truncate_hyperlink_closed():
    """A hyperlink closed in the source is rebuilt around the kept text."""
    result = truncate(f'{HL_OPEN}click here now{HL_CLOSE}', 8)
    assert result == f'{HL_OPEN}click h…{HL_CLOSE}'
    assert width(result) == 8


def test_truncate_hyperlink_unclosed():
    """A hyperlink never closed in the source is closed at the end."""
    result = truncate(f'{HL_OPEN}click here now', 8)
    assert result == f'{HL_OPEN}click h…{HL_CLOSE}'
    assert width(result) == 8


def test_truncate_hyperlink_st_terminator():
    """Hyperlinks terminated by ST are closed with a matching ST form."""
    result = truncate(f'{HL_OPEN_ST}click here now', 8)
    assert result == f'{HL_OPEN_ST}click h…{HL_CLOSE_ST}'


def test_truncate_hyperlink_and_sgr_unclosed():
    """Both an open SGR style and an open hyperlink are closed."""
    result = truncate(f'{HL_OPEN}{SGR_RED}click here', 8)
    assert result == f'{SGR_RED}{HL_OPEN}click h…{SGR_RESET}{HL_CLOSE}'
    assert width(result) == 8


def test_truncate_tab_expansion():
    """Tabs are expanded by clip() when truncation occurs."""
    assert truncate('a\tb', 4) == 'a  …'


def test_truncate_result_never_exceeds_width():
    """Property: display width of the result never exceeds the limit."""
    texts = [
        'hello world',
        '中文字 test',
        f'{EMOJI_FAMILY} family',
        f'{SGR_RED}styled text here{SGR_RESET}',
        f'{SGR_RED}open style text',
        f'{HL_OPEN}link text here{HL_CLOSE}',
        f'{HL_OPEN}unclosed link text',
        'cafe\u0301 au lait',
        'a\tb\tc',
    ]
    for text in texts:
        for limit in range(0, 12):
            result = truncate(text, limit)
            assert width(result) <= max(limit, 0), (text, limit, result)
