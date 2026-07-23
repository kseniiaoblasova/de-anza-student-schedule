"""
Parse the schedule's meeting-time and meeting-day strings into comparable values.

Grounded in the real `deanza-class-schedule` formats:
    meeting_times : "12:30 pm-04:20 pm"   (hh:mm am/pm - hh:mm am/pm), or "TBA"
    meeting_days  : "MW", "TR", "MTWR", "F", "S", or "TBA"

Day codes follow the SIS convention: M=Mon, T=Tue, W=Wed, R=Thu, F=Fri, S=Sat,
U=Sun. "TBA" (and anything unparseable) means the meeting has no fixed
time/day — an async/arranged section that cannot collide with anything.

Pure functions only; no AWS, no I/O.
"""

import re

# Valid single-character day codes in SIS order (R=Thursday, U=Sunday).
DAY_CODES = set("MTWRFSU")

# Two clock times separated by a hyphen, e.g. "12:30 pm-04:20 pm". Tolerant of
# stray spacing around the hyphen and upper/lower-case meridiems.
_TIME_RANGE_RE = re.compile(
    r"(\d{1,2}):(\d{2})\s*([ap]m)\s*-\s*(\d{1,2}):(\d{2})\s*([ap]m)",
    re.IGNORECASE,
)


def _to_minutes(hour, minute, meridiem):
    """Convert a 12-hour clock time to minutes since midnight."""
    hour = int(hour) % 12  # 12am -> 0, 12pm handled by the pm branch below
    if meridiem.lower() == "pm":
        hour += 12
    return hour * 60 + int(minute)


def parse_meeting_times(text):
    """Return (start_minute, end_minute) for a meeting-time string, or None.

    None means no fixed time (e.g. "TBA", blank, or an unrecognized format), so
    the caller treats the meeting as non-conflicting. End-before-start is also
    rejected as unusable.
    """
    if not text:
        return None
    m = _TIME_RANGE_RE.search(str(text))
    if not m:
        return None
    start = _to_minutes(m.group(1), m.group(2), m.group(3))
    end = _to_minutes(m.group(4), m.group(5), m.group(6))
    if end <= start:
        return None
    return start, end


def parse_meeting_days(text):
    """Return the set of day codes in a meeting-days string (empty if none).

    "MW" -> {"M","W"}; "TBA"/blank/unknown -> empty set. Only recognized codes
    are kept, so noise never produces a phantom shared day.
    """
    if not text:
        return set()
    upper = str(text).upper()
    if "TBA" in upper:
        return set()
    return {ch for ch in upper if ch in DAY_CODES}


def times_overlap(a, b):
    """True if two (start, end) minute intervals overlap.

    Strict inequality, so back-to-back meetings (one ends exactly when the next
    begins) do NOT count as overlapping.
    """
    if a is None or b is None:
        return False
    return a[0] < b[1] and b[0] < a[1]


def days_overlap(a, b):
    """True if two day-code sets share at least one day."""
    return bool(a & b)
