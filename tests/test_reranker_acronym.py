"""Which query words may earn the course-abbreviation bonus in the reranker."""
import pytest

from rat.engine.reranker import may_be_course_acronym
from rat.engine.context_parser import remove_accents


def _check(word):
    return may_be_course_acronym(word, remove_accents(word).lower())


# Vietnamese syllables that collide with English path words: "tổ"/to, "ôn"/on, "máy"/may.
@pytest.mark.parametrize("word", ["tổ", "ôn", "máy", "thi", "ghi", "chú", "tính"])
def test_vietnamese_syllables_are_not_course_abbreviations(word):
    assert not _check(word)


# Real abbreviations students type for courses.
@pytest.mark.parametrize("word", ["pttkht", "ctdl", "ktlt", "xstk", "PTTKHT"])
def test_course_abbreviations_still_count(word):
    assert _check(word)
