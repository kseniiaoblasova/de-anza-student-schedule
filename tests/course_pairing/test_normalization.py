"""Tests for the canonical course-code normalizer."""

import pytest

# scripts/ is placed on sys.path by the root conftest.py so `course_pairing`
# resolves to the real package under scripts/.
from course_pairing.normalization import (
    normalize_number,
    normalize_course,
    parse_course_code,
    iter_course_codes,
)


@pytest.mark.parametrize(
    "raw, expected",
    [
        # De Anza campus prefix + zero padding + trailing dot all removed
        ("D001A.", "1A"),
        ("D001A", "1A"),
        ("001A", "1A"),
        ("1A", "1A"),
        # plain numbers
        ("10", "10"),
        ("D010", "10"),
        # letter suffixes preserved
        ("064X", "64X"),
        ("D090A.", "90A"),
        # statewide C-number kept intact (prefix and zeros untouched)
        ("C1000", "C1000"),
        # surface noise
        (" d001a. ", "1A"),
        # unparseable -> None
        ("", None),
        (None, None),
        ("as required", None),
        ("List A", None),
    ],
)
def test_normalize_number(raw, expected):
    assert normalize_number(raw) == expected


@pytest.mark.parametrize(
    "subject, number, expected",
    [
        # the core schedule-vs-pathway equivalence
        ("MATH", "D001A.", "MATH 1A"),
        ("math", "1a", "MATH 1A"),
        ("ENGL", "C1000", "ENGL C1000"),
        ("ADMJ", "064X", "ADMJ 64X"),
        # missing pieces -> None
        ("MATH", None, None),
        ("", "1A", None),
        ("MATH", "as required", None),
    ],
)
def test_normalize_course(subject, number, expected):
    assert normalize_course(subject, number) == expected


def test_schedule_and_pathway_agree():
    """The whole point: both sources reduce to the same canonical identity."""
    assert normalize_course("MATH", "D001A.") == parse_course_code("MATH 1A")


@pytest.mark.parametrize(
    "text, expected",
    [
        ("MATH 1A", "MATH 1A"),
        ("ENGL C1000", "ENGL C1000"),
        ("ADMJ 64X", "ADMJ 64X"),
        # pulls the first code out of surrounding prose
        ("ENGL C1000 (formerly EWRT 1A)", "ENGL C1000"),
        ("DMT 53", "DMT 53"),
        # no digit -> no course
        ("MATH as required", None),
        ("", None),
        (None, None),
    ],
)
def test_parse_course_code_permissive(text, expected):
    assert parse_course_code(text) == expected


# A stand-in for the real subject allow-list the parser sources from the schedule.
SUBJECTS = {"MATH", "ENGL", "EWRT", "ESL", "ADMJ", "DMT", "COMM", "PSYC", "SOC"}


@pytest.mark.parametrize(
    "text, expected",
    [
        # prose that is course-shaped but has a non-subject "subject" is rejected
        ("Complete 25 units from List A:", None),
        ("GE Area 4 - 1st course", None),
        # a real subject inside prose still resolves
        ("ENGL C1000 (formerly EWRT 1A)", "ENGL C1000"),
    ],
)
def test_parse_course_code_with_subject_allowlist(text, expected):
    assert parse_course_code(text, valid_subjects=SUBJECTS) == expected


def test_iter_course_codes_extracts_all_with_allowlist():
    """Multi-course strings yield every valid, canonicalized code in order."""
    text = "ENGL C1000 (formerly EWRT 1A) or ESL 5 as required"
    assert list(iter_course_codes(text, valid_subjects=SUBJECTS)) == [
        "ENGL C1000",
        "EWRT 1A",
        "ESL 5",
    ]


def test_iter_course_codes_filters_prose():
    """List headers and area labels don't leak through when subjects are known."""
    text = "Complete 25 units from List A: ADMJ 3, ADMJ 6, ADMJ 11"
    assert list(iter_course_codes(text, valid_subjects=SUBJECTS)) == [
        "ADMJ 3",
        "ADMJ 6",
        "ADMJ 11",
    ]


def test_normalization_is_idempotent():
    """Normalizing an already-canonical code changes nothing."""
    canonical = normalize_course("MATH", "1A")
    assert parse_course_code(canonical) == canonical
