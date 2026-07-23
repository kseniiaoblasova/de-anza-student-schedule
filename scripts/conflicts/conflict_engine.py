"""
Detect scheduling conflicts among a list of course sections.

Input is a flat list of section-meeting rows shaped like `deanza-class-schedule`
items (course, crn, meeting_days, meeting_times, ...). The engine:

  1. Groups rows into sections by CRN (a section = the union of its meeting rows,
     e.g. a lecture row + a lab row under one CRN).
  2. Compares every section against every section of a DIFFERENT course, skipping
     same-course pairs (a student takes one section of a course, so intra-course
     overlap is irrelevant — the X'd diagonal of the whiteboard matrix).
  3. Flags a pair when ANY meeting of one overlaps ANY meeting of the other:
     a shared meeting day AND overlapping time interval (day + time, per spec).

Sections with no fixed time (async/TBA) parse to no schedule and never conflict.
Pure logic; no AWS, no I/O.
"""

from datetime import date

from conflicts.time_parsing import (
    parse_meeting_times, parse_meeting_days, times_overlap, days_overlap,
)

# Section-level metadata echoed back on each side of a conflict, for the caller.
_META_FIELDS = ("section", "instructor", "room", "building",
                "instruction_method", "part_term", "units")


def _course_key(row):
    """Normalized course label used to group and to skip same-course pairs."""
    return " ".join(str(row.get("course", "")).split())


def _section_id(row):
    """Stable section identity: CRN when present, else the section_key."""
    crn = str(row.get("crn", "")).strip()
    return crn or str(row.get("section_key", "")).strip()


def _parse_date(value):
    """Parse an ISO date/datetime string to a date, or None."""
    if not value:
        return None
    try:
        return date.fromisoformat(str(value)[:10])
    except ValueError:
        return None


def build_sections(rows):
    """Group meeting rows into sections keyed by (course, section id).

    Returns a list of section dicts, each with its parsed meetings and a
    representative row for metadata. Deterministically ordered by course then id.
    """
    sections = {}
    for row in rows:
        key = (_course_key(row), _section_id(row))
        section = sections.get(key)
        if section is None:
            section = {
                "course": _course_key(row),
                "section_id": _section_id(row),
                "row": row,          # representative row for metadata
                "meetings": [],
            }
            sections[key] = section
        section["meetings"].append({
            "days": parse_meeting_days(row.get("meeting_days")),
            "times": parse_meeting_times(row.get("meeting_times")),
            "times_raw": str(row.get("meeting_times", "")),
            "start": _parse_date(row.get("start_date")),
            "end": _parse_date(row.get("end_date")),
        })
    return [sections[k] for k in sorted(sections)]


def _dates_overlap(a, b):
    """Inclusive date-range overlap; missing dates are treated as overlapping."""
    if a["start"] is None or a["end"] is None or b["start"] is None or b["end"] is None:
        return True
    return a["start"] <= b["end"] and b["start"] <= a["end"]


def _meetings_conflict(m1, m2, require_day_overlap, require_date_overlap):
    """True if two meetings collide, per the configured rules."""
    if not times_overlap(m1["times"], m2["times"]):
        return False
    if require_day_overlap and not days_overlap(m1["days"], m2["days"]):
        return False
    if require_date_overlap and not _dates_overlap(m1, m2):
        return False
    return True


def find_pair_conflict(s1, s2, require_day_overlap=True, require_date_overlap=False):
    """Return the first colliding (meeting, meeting) between two sections, or None."""
    for m1 in s1["meetings"]:
        for m2 in s2["meetings"]:
            if _meetings_conflict(m1, m2, require_day_overlap, require_date_overlap):
                return m1, m2
    return None


def _meta(row):
    return {f: row.get(f) for f in _META_FIELDS if row.get(f) not in (None, "")}


def _conflict_entry(s1, s2, m1, m2):
    """Shape one conflict, with the offending meeting detail and side metadata."""
    return {
        "course_a": s1["course"], "crn_a": s1["section_id"],
        "course_b": s2["course"], "crn_b": s2["section_id"],
        "overlap": {
            "days": sorted(m1["days"] & m2["days"]),
            "time_a": m1["times_raw"],
            "time_b": m2["times_raw"],
        },
        "meta_a": _meta(s1["row"]),
        "meta_b": _meta(s2["row"]),
    }


def _pair_entry(s1, s2, hit):
    """Shape one classified cross-course pair.

    Same identity/metadata as a conflict entry, plus an explicit `overlap` flag
    so the student planner can render the "these clash" vs "these are fine" split.
    `overlap_detail` (the shared days + both times) is present only on a collision.
    """
    entry = {
        "course_a": s1["course"], "crn_a": s1["section_id"],
        "course_b": s2["course"], "crn_b": s2["section_id"],
        "overlap": hit is not None,
        "meta_a": _meta(s1["row"]),
        "meta_b": _meta(s2["row"]),
    }
    if hit:
        m1, m2 = hit
        entry["overlap_detail"] = {
            "days": sorted(m1["days"] & m2["days"]),
            "time_a": m1["times_raw"],
            "time_b": m2["times_raw"],
        }
    return entry


def classify_pairs(rows, require_day_overlap=True, require_date_overlap=False):
    """Compare all cross-course section pairs, tagging each as overlap or clear.

    Same pairing rules as `find_conflicts` (group by CRN, skip same-course pairs,
    TBA/async never overlaps), but returns EVERY evaluated pair with an `overlap`
    flag — the full "Yes/No" split the student-facing planner shows — rather than
    only the collisions. `find_conflicts` is left as the lean report other callers
    (the pathway pipeline) depend on.

    Returns:
        {
          "sections_evaluated": int,
          "pairs_evaluated": int,        # cross-course section pairs considered
          "overlap_count": int,          # how many of them collide
          "pairs": [ {course_a, crn_a, course_b, crn_b, overlap,
                      overlap_detail?, meta_a, meta_b} ]
        }
    """
    sections = build_sections(rows)
    pairs = []
    overlap_count = 0

    # Pairwise over sections, skipping same-course pairs (the diagonal blocks) —
    # identical to find_conflicts, but we keep the non-colliding pairs too.
    for i in range(len(sections)):
        for j in range(i + 1, len(sections)):
            s1, s2 = sections[i], sections[j]
            if s1["course"] == s2["course"]:
                continue
            hit = find_pair_conflict(
                s1, s2, require_day_overlap, require_date_overlap)
            pairs.append(_pair_entry(s1, s2, hit))
            if hit:
                overlap_count += 1

    return {
        "sections_evaluated": len(sections),
        "pairs_evaluated": len(pairs),
        "overlap_count": overlap_count,
        "pairs": pairs,
    }


def find_conflicts(rows, require_day_overlap=True, require_date_overlap=False):
    """Compare all cross-course section pairs and build the conflict report.

    Returns:
        {
          "conflict_count": int,
          "sections_evaluated": int,
          "pairs_evaluated": int,        # cross-course section pairs considered
          "conflicts": [ {course_a, crn_a, course_b, crn_b, overlap, meta_a, meta_b} ]
        }
    """
    sections = build_sections(rows)
    conflicts = []
    pairs_evaluated = 0

    # Pairwise over sections, skipping same-course pairs (the diagonal blocks).
    for i in range(len(sections)):
        for j in range(i + 1, len(sections)):
            s1, s2 = sections[i], sections[j]
            if s1["course"] == s2["course"]:
                continue
            pairs_evaluated += 1
            hit = find_pair_conflict(
                s1, s2, require_day_overlap, require_date_overlap)
            if hit:
                conflicts.append(_conflict_entry(s1, s2, hit[0], hit[1]))

    return {
        "conflict_count": len(conflicts),
        "sections_evaluated": len(sections),
        "pairs_evaluated": pairs_evaluated,
        "conflicts": conflicts,
    }
