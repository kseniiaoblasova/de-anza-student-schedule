"""Tests for the pairing audit's pure comparison logic."""

import pytest

from course_pairing.audit_matches import (
    schedule_course_set,
    collect_pathway_courses,
    compute_audit,
)


def test_schedule_course_set_dedupes_rows():
    """Multiple meeting rows / sections for one course collapse to one identity."""
    rows = [
        {"subject": "MATH", "number": "D001A."},   # -> MATH 1A
        {"subject": "MATH", "number": "D001A."},   # duplicate row
        {"subject": "MATH", "number": "001A"},     # another section, same course
        {"subject": "ENGL", "number": "C1000"},
        {"subject": "", "number": ""},             # junk row ignored
    ]
    assert schedule_course_set(rows) == {"MATH 1A", "ENGL C1000"}


def _item(pid, program, course_lists, unresolved=None):
    """Build a minimal normalized item: {year_1: {fall: {...}}} from one list."""
    return {
        "pathway_id": pid,
        "program_name": program,
        "years": {
            "year_1": {
                "fall": {
                    "normalized_courses": course_lists,
                    "unresolved_entries": unresolved or [],
                }
            }
        },
    }


def test_collect_pathway_courses_tracks_occurrences_and_unresolved():
    items = [
        _item("p1", "Prog One", ["MATH 1A", "ENGL C1000"], unresolved=["MATH as required"]),
        _item("p2", "Prog Two", ["MATH 1A"]),
    ]
    occ, unresolved_total = collect_pathway_courses(items)
    assert set(occ) == {"MATH 1A", "ENGL C1000"}
    assert len(occ["MATH 1A"]) == 2  # referenced by both pathways
    assert occ["MATH 1A"][0]["pathway_id"] == "p1"
    assert unresolved_total == 1


def test_compute_audit_percentages_and_unmatched_context():
    occ = {
        "MATH 1A": [{"pathway_id": "p1", "program_name": "P1", "year": "year_1", "quarter": "fall"}],
        "ENGL C1000": [{"pathway_id": "p1", "program_name": "P1", "year": "year_1", "quarter": "fall"}],
        "BOGUS 99": [{"pathway_id": "p2", "program_name": "P2", "year": "year_1", "quarter": "fall"}],
    }
    schedule = {"MATH 1A", "ENGL C1000"}
    report = compute_audit(occ, schedule, unresolved_total=3)

    assert report["distinct_pathway_courses"] == 3
    assert report["matched"] == 2
    assert report["unmatched"] == 1
    assert report["match_percentage"] == round(200 / 3, 2)
    assert report["unresolved_entries_total"] == 3
    # unmatched carries its pathway context
    assert report["unmatched_courses"] == [
        {"course": "BOGUS 99", "occurrences": occ["BOGUS 99"]}
    ]


def test_compute_audit_empty_denominator():
    report = compute_audit({}, {"MATH 1A"})
    assert report["distinct_pathway_courses"] == 0
    assert report["match_percentage"] == 0.0
    assert report["unmatched_courses"] == []


def test_compute_audit_all_matched():
    occ = {"MATH 1A": [{"pathway_id": "p", "program_name": "P", "year": "year_1", "quarter": "fall"}]}
    report = compute_audit(occ, {"MATH 1A", "OTHER 2"})
    assert report["match_percentage"] == 100.0
    assert report["unmatched"] == 0
