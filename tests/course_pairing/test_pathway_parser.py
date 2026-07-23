"""Tests for the pathway quarter parser (pure, subject allow-list injected)."""

import pytest

from course_pairing.pathway_parser import extract_courses, normalize_pathway_years

# Stand-in for the real subject allow-list sourced from the schedule.
SUBJECTS = {"ADMJ", "DMT", "ENGL", "EWRT", "ESL", "MATH", "PSYC", "SOC", "COMM", "STAT"}


def test_simple_single_course():
    courses, unresolved = extract_courses(["DMT 53"], SUBJECTS)
    assert courses == ["DMT 53"]
    assert unresolved == []


def test_or_alternatives_are_all_kept():
    courses, unresolved = extract_courses(["DMT 60A or DMT 65A"], SUBJECTS)
    assert courses == ["DMT 60A", "DMT 65A"]
    assert unresolved == []


def test_formerly_alias_kept_as_separate_course():
    courses, unresolved = extract_courses(
        ["ENGL C1000 (formerly EWRT 1A) or ESL 5 as required"], SUBJECTS
    )
    assert courses == ["ENGL C1000", "EWRT 1A", "ESL 5"]
    assert unresolved == []


def test_subject_continuation_across_split_entries():
    """A subject dangling at an entry's end applies to the next entry's numbers."""
    entries = [
        "ADMJ 3, ADMJ 6, ADMJ 11, ADMJ",
        "53, ADMJ 54, ADMJ 55",
    ]
    courses, unresolved = extract_courses(entries, SUBJECTS)
    assert courses == ["ADMJ 3", "ADMJ 6", "ADMJ 11", "ADMJ 53", "ADMJ 54", "ADMJ 55"]


def test_list_header_and_placeholder_are_unresolved():
    courses, unresolved = extract_courses(
        ["Complete 25 units from List A:", "MATH as required"], SUBJECTS
    )
    assert courses == []
    assert unresolved == ["Complete 25 units from List A:", "MATH as required"]


def test_prose_does_not_inherit_stale_subject():
    """After a real course, list prose must not borrow its subject."""
    # "DMT 57" sets subject DMT; "Complete 4 units" must NOT become "DMT 4".
    entries = ["DMT 57", "Complete 4 units from List A: DMT 60A, DMT 60B"]
    courses, _ = extract_courses(entries, SUBJECTS)
    assert courses == ["DMT 57", "DMT 60A", "DMT 60B"]
    assert "DMT 4" not in courses


def test_duplicates_deduped_first_seen_order():
    courses, _ = extract_courses(["MATH 1A", "MATH 1A", "ENGL C1000"], SUBJECTS)
    assert courses == ["MATH 1A", "ENGL C1000"]


def test_unknown_subject_is_dropped_not_matched():
    # BIOL is not in the allow-list -> treated as prose, no course emitted.
    courses, unresolved = extract_courses(["BIOL 6"], SUBJECTS)
    assert courses == []
    assert unresolved == ["BIOL 6"]


def test_empty_and_none_entries():
    courses, unresolved = extract_courses([None, "", "  "], SUBJECTS)
    assert courses == []
    assert unresolved == []


def test_ordinals_are_not_courses():
    """'1st course' / '2nd course' must not become AUTO 1ST / AUTO 2ND."""
    courses, _ = extract_courses(
        ["AUTO 1st course", "AUTO 2nd course", "AUTO 53A"], SUBJECTS | {"AUTO"}
    )
    assert courses == ["AUTO 53A"]
    assert "AUTO 1ST" not in courses


def test_star_suffix_stripped_by_tokenizer():
    courses, _ = extract_courses(["SOC 15* or PSYC 15* or COMM 10"], SUBJECTS)
    assert courses == ["SOC 15", "PSYC 15", "COMM 10"]


def test_normalize_pathway_years_shape():
    years = {
        "year_1": {
            "fall": {"required_courses": ["DMT 53"], "additional_courses": []},
            "winter": {
                "required_courses": ["DMT 54"],
                "additional_courses": ["DMT 60A or DMT 65A"],
            },
        }
    }
    out = normalize_pathway_years(years, SUBJECTS)
    assert out["year_1"]["fall"]["normalized_courses"] == ["DMT 53"]
    assert out["year_1"]["fall"]["unresolved_entries"] == []
    assert out["year_1"]["winter"]["normalized_courses"] == ["DMT 54", "DMT 60A", "DMT 65A"]
    # source is untouched
    assert years["year_1"]["fall"]["required_courses"] == ["DMT 53"]
