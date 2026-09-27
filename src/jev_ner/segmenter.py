"""Full-text traversal and delimiter-based segmentation.

The text is walked character by character exactly once per level. Each level
cuts at a stronger or weaker class of delimiter, so a segment can be split
further (coarse -> fine) only when the recognizer decides it still contains
more than one thing.
"""

from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass

LEVEL_SENTENCE = 0
LEVEL_CLAUSE = 1
LEVEL_ENCLOSURE = 2
LEVEL_SPACE = 3
LEVEL_NAMES = {
    LEVEL_SENTENCE: "sentence",
    LEVEL_CLAUSE: "clause",
    LEVEL_ENCLOSURE: "enclosure",
    LEVEL_SPACE: "space",
}
MAX_LEVEL = LEVEL_SPACE

HARD_DELIMS = set("。！？!?；;\n\r…")
SEPARATOR_DELIMS = set("，,、：:/／|｜\t")
# Brackets and quotes are cut after separators: names such as 阿里巴巴（中国）有限公司 contain them.
ENCLOSURE_DELIMS = set("（）()［］[]【】《》〈〉<>「」『』“”\"‘’〔〕{}｛｝")
WIDE_SPACES = set("\t\u3000")

_ABBREVIATIONS = {
    "mr", "mrs", "ms", "dr", "prof", "st", "rd", "ave", "no", "inc", "ltd",
    "co", "corp", "jr", "sr", "vs", "etc", "dept", "univ", "u.s", "e.g", "i.e",
}

_WORD_RE = re.compile(r"[A-Za-z0-9]+(?:['’\-.&][A-Za-z0-9]+)*")


@dataclass(frozen=True)
class Segment:
    start: int
    end: int
    text: str
    level: int


def is_cjk(ch: str) -> bool:
    if not ch:
        return False
    code = ord(ch)
    return (
        0x4E00 <= code <= 0x9FFF
        or 0x3400 <= code <= 0x4DBF
        or 0x20000 <= code <= 0x2A6DF
        or 0xF900 <= code <= 0xFAFF
        or 0x3040 <= code <= 0x30FF
        or 0xAC00 <= code <= 0xD7AF
    )


CURRENCY = set("$¥￥€£₩₹")


def is_meaningful(text: str) -> bool:
    return any(ch.isalnum() or is_cjk(ch) for ch in text)


def can_bound_window(unit: str) -> bool:
    return is_meaningful(unit) or unit in CURRENCY


def _prev_word(text: str, i: int) -> str:
    j = i
    while j > 0 and (text[j - 1].isalnum() or text[j - 1] == "."):
        j -= 1
    return text[j:i].lower()


def _is_sentence_period(text: str, i: int) -> bool:
    """An ASCII '.' ends a sentence only when followed by a break and not an abbreviation."""
    nxt = text[i + 1] if i + 1 < len(text) else ""
    if nxt and not (nxt.isspace() or is_cjk(nxt)):
        return False
    word = _prev_word(text, i)
    if word in _ABBREVIATIONS:
        return False
    if len(word) == 1 and word.isalpha():
        return False
    return True


def _between_digits(text: str, i: int) -> bool:
    return 0 < i < len(text) - 1 and text[i - 1].isdigit() and text[i + 1].isdigit()


def _is_space_break(text: str, i: int, start: int, end: int) -> bool:
    ch = text[i]
    if not ch.isspace():
        return False
    if ch in WIDE_SPACES:
        return True
    j = i
    while j > start and text[j - 1].isspace():
        j -= 1
    k = i
    while k < end and text[k].isspace():
        k += 1
    if k - j >= 2:
        return True
    left = text[j - 1] if j > start else ""
    right = text[k] if k < end else ""
    return is_cjk(left) or is_cjk(right)


def is_delimiter(text: str, i: int, level: int, start: int = 0, end: int | None = None) -> bool:
    end = len(text) if end is None else end
    ch = text[i]
    if level == LEVEL_SENTENCE:
        if ch == ".":
            return _is_sentence_period(text, i)
        return ch in HARD_DELIMS
    if level == LEVEL_CLAUSE:
        if ch in (",", ":") and _between_digits(text, i):
            return False
        return ch in SEPARATOR_DELIMS
    if level == LEVEL_ENCLOSURE:
        return ch in ENCLOSURE_DELIMS
    if level == LEVEL_SPACE:
        return _is_space_break(text, i, start, end)
    raise ValueError(f"unknown level {level}")


def _make_segment(text: str, start: int, end: int, level: int) -> Segment | None:
    while start < end and (text[start].isspace() or unicodedata.category(text[start]).startswith("Z")):
        start += 1
    while end > start and text[end - 1].isspace():
        end -= 1
    if start >= end:
        return None
    piece = text[start:end]
    if not is_meaningful(piece):
        return None
    return Segment(start, end, piece, level)


def split(text: str, start: int, end: int, level: int) -> list[Segment]:
    """Traverse text[start:end] once and cut it at the delimiters of `level`."""
    segments: list[Segment] = []
    seg_start = start
    for i in range(start, end):
        if is_delimiter(text, i, level, start, end):
            seg = _make_segment(text, seg_start, i, level)
            if seg:
                segments.append(seg)
            seg_start = i + 1
    seg = _make_segment(text, seg_start, end, level)
    if seg:
        segments.append(seg)
    return segments


def split_sentences(text: str) -> list[Segment]:
    return split(text, 0, len(text), LEVEL_SENTENCE)


def split_finer(text: str, seg: Segment) -> tuple[int, list[Segment]] | None:
    """Split `seg` with the next level that actually produces more than one piece."""
    for level in range(seg.level + 1, MAX_LEVEL + 1):
        parts = split(text, seg.start, seg.end, level)
        if len(parts) > 1:
            return level, parts
        if len(parts) == 1 and (parts[0].start, parts[0].end) != (seg.start, seg.end):
            return level, parts
    return None


def units(text: str, start: int, end: int) -> list[tuple[int, int]]:
    """Atomic units for sliding windows: one CJK char, one Latin word/number, or one symbol."""
    out: list[tuple[int, int]] = []
    i = start
    while i < end:
        ch = text[i]
        if ch.isspace():
            i += 1
            continue
        if ch.isascii() and ch.isalnum():
            m = _WORD_RE.match(text, i, end)
            assert m is not None
            out.append((i, m.end()))
            i = m.end()
            continue
        out.append((i, i + 1))
        i += 1
    return out
