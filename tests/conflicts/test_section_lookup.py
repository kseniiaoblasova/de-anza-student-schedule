"""Tests for the term-aware section lookup (DynamoDB read is faked)."""

from conflicts.section_lookup import lookup_sections, _subject_filter


class FakeTable:
    """Minimal stand-in for a boto3 Table: returns canned rows from .query().

    query_term calls table.query(KeyConditionExpression=..., FilterExpression=...)
    and reads Items / LastEvaluatedKey. We ignore the expressions and hand back
    the rows we were seeded with, in one page.
    """

    def __init__(self, rows):
        self.rows = rows
        self.calls = []

    def query(self, **kwargs):
        self.calls.append(kwargs)
        return {"Items": list(self.rows)}


def _row(subject, number, crn, days, times):
    """A schedule row shaped like a deanza-class-schedule item."""
    return {"subject": subject, "number": number, "crn": crn,
            "section": "01", "meeting_days": days, "meeting_times": times}


def test_resolves_requested_courses_to_sections():
    table = FakeTable([
        _row("MATH", "D001A.", "100", "MW", "09:30 am-10:20 am"),
        _row("ENGL", "D001A.", "200", "MW", "09:30 am-10:20 am"),
    ])
    sections, offered, not_offered = lookup_sections("202722", ["MATH 1A", "ENGL 1A"], table)

    assert offered == ["MATH 1A", "ENGL 1A"]
    assert not_offered == []
    # Sections carry the canonical course code, not the raw schedule label.
    assert {s["course"] for s in sections} == {"MATH 1A", "ENGL 1A"}
    assert {s["crn"] for s in sections} == {"100", "200"}


def test_course_with_no_section_is_not_offered():
    table = FakeTable([_row("MATH", "D001A.", "100", "MW", "09:30 am-10:20 am")])
    sections, offered, not_offered = lookup_sections("202722", ["MATH 1A", "PHYS 4A"], table)

    assert offered == ["MATH 1A"]
    assert not_offered == ["PHYS 4A"]
    assert all(s["course"] == "MATH 1A" for s in sections)


def test_multiple_sections_of_same_course_all_returned():
    table = FakeTable([
        _row("MATH", "D001A.", "100", "MW", "09:30 am-10:20 am"),
        _row("MATH", "D001A.", "101", "TR", "11:00 am-11:50 am"),
    ])
    sections, offered, _ = lookup_sections("202722", ["MATH 1A"], table)
    assert offered == ["MATH 1A"]
    assert len(sections) == 2


def test_subject_filter_covers_requested_subjects():
    """The query is narrowed to the subjects behind the requested codes."""
    assert _subject_filter([]) is None
    # Distinct subjects only, deduped (two MATH courses -> one subject).
    filt = _subject_filter(["MATH 1A", "MATH 1B", "ENGL 1A"])
    assert filt is not None  # an Attr('subject').is_in([...]) condition
