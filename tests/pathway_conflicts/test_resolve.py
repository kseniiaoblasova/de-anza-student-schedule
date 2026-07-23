"""Tests for the pure pathway-conflict resolve/build helpers."""

from decimal import Decimal

from pathway_conflicts.resolve import (
    term_for,
    index_sections_by_course,
    build_section_payload,
    build_conflict_item,
    YEAR_QUARTER_TO_TERM,
)


def test_term_mapping_covers_all_six_quarters():
    assert term_for("year_1", "fall") == "202622"
    assert term_for("year_2", "spring") == "202742"
    assert len(YEAR_QUARTER_TO_TERM) == 6
    assert term_for("year_3", "fall") is None


def test_index_sections_by_course_canonicalizes_and_keeps_all_rows():
    rows = [
        {"subject": "MATH", "number": "D001A.", "crn": "1"},
        {"subject": "MATH", "number": "D001A.", "crn": "1"},   # lab row, same course
        {"subject": "ENGL", "number": "C1000", "crn": "2"},
        {"subject": "", "number": "", "crn": "x"},             # unindexable
    ]
    index = index_sections_by_course(rows)
    assert set(index) == {"MATH 1A", "ENGL C1000"}
    assert len(index["MATH 1A"]) == 2


def test_build_section_payload_splits_resolved_and_missing():
    index = {
        "MATH 1A": [{"crn": "1", "meeting_days": "MW", "meeting_times": "9-10", "section": "01"}],
        "ENGL 1A": [{"crn": "2", "meeting_days": "TR", "meeting_times": "9-10"},
                    {"crn": "3", "meeting_days": "F", "meeting_times": "1-2"}],
    }
    sections, resolved, missing = build_section_payload(
        ["MATH 1A", "ENGL 1A", "BOGUS 99"], index)
    assert resolved == ["MATH 1A", "ENGL 1A"]
    assert missing == ["BOGUS 99"]
    assert len(sections) == 3                       # 1 + 2 sections
    # canonical course is used as the section's course label
    assert {s["course"] for s in sections} == {"MATH 1A", "ENGL 1A"}
    # only non-empty fields carried through
    assert sections[0]["crn"] == "1"


def test_build_conflict_item_shape_and_percentage():
    pathway = {"pathway_id": "p#1", "program_name": "Prog", "village": "V",
               "credential_type": "AA"}
    report = {"conflict_count": 1, "sections_evaluated": 4, "pairs_evaluated": 4,
              "conflicts": [{"course_a": "MATH 1A", "course_b": "ENGL 1A"}]}
    item = build_conflict_item(pathway, "year_1", "fall", "202622",
                               report, ["MATH 1A", "ENGL 1A"], ["BOGUS 99"])
    assert item["pathway_id"] == "p#1"
    assert item["quarter_key"] == "year_1#fall"
    assert item["term_code"] == "202622"
    assert item["course_count"] == 2
    assert item["missing_courses"] == ["BOGUS 99"]
    assert item["conflict_count"] == 1
    assert item["conflict_percentage"] == Decimal("25.0")
    assert isinstance(item["conflict_percentage"], Decimal)   # DynamoDB-safe
    assert item["conflicts"][0]["course_a"] == "MATH 1A"


def test_build_conflict_item_zero_pairs_is_zero_percent():
    report = {"conflict_count": 0, "sections_evaluated": 1, "pairs_evaluated": 0,
              "conflicts": []}
    item = build_conflict_item({"pathway_id": "p"}, "year_1", "winter", "202632",
                               report, ["MATH 1A"], [])
    assert item["conflict_percentage"] == Decimal("0")
    assert item["conflict_count"] == 0
