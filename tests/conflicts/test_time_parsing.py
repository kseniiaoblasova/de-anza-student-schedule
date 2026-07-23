"""Tests for meeting time/day parsing, against real schedule formats."""

import pytest

from conflicts.time_parsing import (
    parse_meeting_times,
    parse_meeting_days,
    times_overlap,
    days_overlap,
)


@pytest.mark.parametrize(
    "text, expected",
    [
        # real format: minutes since midnight
        ("12:30 pm-04:20 pm", (12 * 60 + 30, 16 * 60 + 20)),
        ("09:30 am-11:20 am", (9 * 60 + 30, 11 * 60 + 20)),
        ("06:30 pm-08:45 pm", (18 * 60 + 30, 20 * 60 + 45)),
        # noon / midnight edges
        ("12:00 pm-01:00 pm", (12 * 60, 13 * 60)),
        ("12:00 am-01:00 am", (0, 60)),
        # tolerant of spacing/case
        ("9:00 AM - 10:15 AM", (9 * 60, 10 * 60 + 15)),
        # no fixed time -> None
        ("TBA", None),
        ("", None),
        (None, None),
        ("garbage", None),
        # end not after start -> unusable
        ("10:00 am-10:00 am", None),
    ],
)
def test_parse_meeting_times(text, expected):
    assert parse_meeting_times(text) == expected


@pytest.mark.parametrize(
    "text, expected",
    [
        ("MW", {"M", "W"}),
        ("TR", {"T", "R"}),          # Tue + Thu
        ("MTWRF", set("MTWRF")),
        ("F", {"F"}),
        ("S", {"S"}),
        ("TBA", set()),
        ("", set()),
        (None, set()),
        ("MW ", {"M", "W"}),         # trailing space
        ("mw", {"M", "W"}),          # lowercase
    ],
)
def test_parse_meeting_days(text, expected):
    assert parse_meeting_days(text) == expected


@pytest.mark.parametrize(
    "a, b, expected",
    [
        ((600, 660), (630, 700), True),    # partial overlap
        ((600, 700), (620, 640), True),    # contained
        ((600, 660), (600, 660), True),    # identical
        ((600, 660), (660, 720), False),   # back-to-back, no overlap
        ((600, 660), (700, 760), False),   # disjoint
        (None, (600, 660), False),         # unscheduled side never conflicts
        ((600, 660), None, False),
    ],
)
def test_times_overlap(a, b, expected):
    assert times_overlap(a, b) is expected


def test_days_overlap():
    assert days_overlap({"M", "W"}, {"W", "F"}) is True
    assert days_overlap({"M", "W"}, {"T", "R"}) is False
    assert days_overlap(set(), {"M"}) is False
