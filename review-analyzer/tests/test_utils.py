"""Unit tests for app.utils.clean_text and app.utils.chunk_text."""

import string

import pytest

from app.utils import chunk_text, clean_text


def test_strips_leading_and_trailing_whitespace():
    assert clean_text("  great shoes  ") == "great shoes"


def test_collapses_internal_whitespace():
    assert clean_text("great\n\nshoes   for\trunning") == "great shoes for running"


def test_blank_input_becomes_empty_string():
    assert clean_text("   \n\t  ") == ""
    assert clean_text("") == ""


def test_leaves_already_clean_text_unchanged():
    assert clean_text("great shoes") == "great shoes"


def test_drop_empties_from_a_review_list():
    """Caller-side pattern: filter out reviews that clean to nothing."""
    raw = ["  good fit  ", "   ", "\n\n", "runs narrow"]
    cleaned = [t for t in (clean_text(r) for r in raw) if t]
    assert cleaned == ["good fit", "runs narrow"]


def test_chunk_text_short_text_is_one_chunk():
    text = "runs a bit narrow, sizing up helped"
    assert chunk_text(text, max_chars=100, overlap=10) == [text]


def test_chunk_text_empty_text_is_no_chunks():
    assert chunk_text("", max_chars=100, overlap=10) == []


def test_chunk_text_rejects_overlap_not_smaller_than_max_chars():
    with pytest.raises(ValueError):
        chunk_text("some text", max_chars=10, overlap=10)


def test_chunk_text_long_text_overlaps_correctly():
    # 260 distinct chars (repeating a-z) so any shared substring proves overlap,
    # not coincidence.
    text = (string.ascii_lowercase * 10)[:260]
    max_chars, overlap = 100, 20

    chunks = chunk_text(text, max_chars=max_chars, overlap=overlap)

    # every chunk (but the last) is exactly max_chars; none exceed it
    assert all(len(c) <= max_chars for c in chunks)
    assert all(len(c) == max_chars for c in chunks[:-1])

    # consecutive chunks share exactly `overlap` chars at the boundary
    step = max_chars - overlap
    for i in range(len(chunks) - 1):
        assert chunks[i][step:] == chunks[i + 1][:overlap]

    # reassembling by dropping each chunk's overlapping prefix recovers the original
    rebuilt = chunks[0] + "".join(c[overlap:] for c in chunks[1:])
    assert rebuilt == text
