"""Tests for the conflict engine (pure)."""

import pytest

from conflicts.conflict_engine import build_sections, find_conflicts, classify_pairs


def sec(course, crn, days, times, **extra):
    """Build one section-meeting row like a schedule item."""
    row = {"course": course, "crn": crn,
           "meeting_days": days, "meeting_times": times}
    row.update(extra)
    return row


def test_exact_time_overlap_same_day_conflicts():
    rows = [
        sec("MATH 1A", "100", "MW", "09:30 am-10:20 am"),
        sec("ENGL 1A", "200", "MW", "09:30 am-10:20 am"),
    ]
    report = find_conflicts(rows)
    assert report["conflict_count"] == 1
    assert report["pairs_evaluated"] == 1
    c = report["conflicts"][0]
    assert {c["course_a"], c["course_b"]} == {"MATH 1A", "ENGL 1A"}
    assert c["overlap"]["days"] == ["M", "W"]


def test_partial_overlap_conflicts():
    rows = [
        sec("MATH 1A", "100", "MW", "09:30 am-10:45 am"),
        sec("ENGL 1A", "200", "MW", "10:30 am-11:20 am"),
    ]
    assert find_conflicts(rows)["conflict_count"] == 1


def test_same_time_different_days_no_conflict():
    """Day-aware: same clock time on disjoint days is not a conflict."""
    rows = [
        sec("MATH 1A", "100", "MW", "09:30 am-10:20 am"),
        sec("ENGL 1A", "200", "TR", "09:30 am-10:20 am"),
    ]
    assert find_conflicts(rows)["conflict_count"] == 0


def test_back_to_back_no_conflict():
    rows = [
        sec("MATH 1A", "100", "MW", "09:30 am-10:20 am"),
        sec("ENGL 1A", "200", "MW", "10:20 am-11:10 am"),
    ]
    assert find_conflicts(rows)["conflict_count"] == 0


def test_same_course_pair_skipped():
    """Two sections of the same course are never compared (the X diagonal)."""
    rows = [
        sec("MATH 1A", "100", "MW", "09:30 am-10:20 am"),
        sec("MATH 1A", "101", "MW", "09:30 am-10:20 am"),
    ]
    report = find_conflicts(rows)
    assert report["conflict_count"] == 0
    assert report["pairs_evaluated"] == 0
    assert report["sections_evaluated"] == 2


def test_async_tba_never_conflicts():
    rows = [
        sec("MATH 1A", "100", "TBA", "TBA", instruction_method="OA"),
        sec("ENGL 1A", "200", "MW", "09:30 am-10:20 am"),
    ]
    report = find_conflicts(rows)
    assert report["conflict_count"] == 0
    assert report["pairs_evaluated"] == 1  # still a pair, just no collision


def test_multi_meeting_lab_conflicts():
    """A section's lab row (2nd meeting under same CRN) can be the collision."""
    rows = [
        sec("BIOL 6A", "100", "MW", "09:30 am-10:20 am"),   # lecture
        sec("BIOL 6A", "100", "F", "01:00 pm-03:50 pm"),    # lab, same CRN
        sec("CHEM 1A", "200", "F", "02:00 pm-03:00 pm"),    # overlaps the lab
    ]
    report = find_conflicts(rows)
    assert report["sections_evaluated"] == 2   # BIOL grouped into one section
    assert report["conflict_count"] == 1
    c = report["conflicts"][0]
    assert c["overlap"]["days"] == ["F"]


def test_no_conflicts_all_disjoint():
    rows = [
        sec("MATH 1A", "100", "MW", "08:00 am-08:50 am"),
        sec("ENGL 1A", "200", "MW", "09:00 am-09:50 am"),
        sec("HIST 1A", "300", "TR", "10:00 am-10:50 am"),
    ]
    report = find_conflicts(rows)
    assert report["conflict_count"] == 0
    assert report["pairs_evaluated"] == 3  # 3 courses -> 3 cross-course pairs


def test_build_sections_groups_by_crn():
    rows = [
        sec("BIOL 6A", "100", "MW", "09:30 am-10:20 am"),
        sec("BIOL 6A", "100", "F", "01:00 pm-03:50 pm"),
    ]
    sections = build_sections(rows)
    assert len(sections) == 1
    assert len(sections[0]["meetings"]) == 2


def test_metadata_echoed_on_conflict():
    rows = [
        sec("MATH 1A", "100", "MW", "09:30 am-10:20 am",
            instructor="Ada L", room="S11"),
        sec("ENGL 1A", "200", "MW", "09:30 am-10:20 am",
            instructor="Bob K", room="L42"),
    ]
    c = find_conflicts(rows)["conflicts"][0]
    # sections sort by course, so ENGL is side A and MATH is side B
    by_course = {c["course_a"]: c["meta_a"], c["course_b"]: c["meta_b"]}
    assert by_course["MATH 1A"]["instructor"] == "Ada L"
    assert by_course["MATH 1A"]["room"] == "S11"
    assert by_course["ENGL 1A"]["room"] == "L42"


def test_require_date_overlap_separates_part_terms():
    """With date checking on, part A vs part B at the same time don't conflict."""
    rows = [
        sec("MATH 1A", "100", "MW", "09:30 am-10:20 am",
            start_date="2026-09-21", end_date="2026-10-30", part_term="A"),
        sec("ENGL 1A", "200", "MW", "09:30 am-10:20 am",
            start_date="2026-11-02", end_date="2026-12-11", part_term="B"),
    ]
    # default: dates ignored
    assert find_conflicts(rows)["conflict_count"] == 1
    assert find_conflicts(rows, require_date_overlap=True)[
        "conflict_count"] == 0


# ---- classify_pairs: the full Yes/No split for the student planner ----

def test_classify_pairs_splits_overlap_and_clear():
    """Every cross-course pair is returned, tagged overlap true/false."""
    rows = [
        sec("MATH 1A", "100", "MW", "09:30 am-10:20 am"),
        sec("ENGL 1A", "200", "MW", "09:30 am-10:20 am"),   # clashes with MATH
        # clashes with neither
        sec("HIST 1A", "300", "TR", "01:00 pm-01:50 pm"),
    ]
    result = classify_pairs(rows)
    assert result["sections_evaluated"] == 3
    assert result["pairs_evaluated"] == 3          # 3 courses -> 3 cross pairs
    assert result["overlap_count"] == 1
    overlaps = [p for p in result["pairs"] if p["overlap"]]
    clears = [p for p in result["pairs"] if not p["overlap"]]
    assert len(overlaps) == 1 and len(clears) == 2
    assert {overlaps[0]["course_a"], overlaps[0]
            ["course_b"]} == {"MATH 1A", "ENGL 1A"}


def test_classify_pairs_overlap_detail_only_on_collision():
    """overlap_detail (shared days + times) is present only on colliding pairs."""
    rows = [
        sec("MATH 1A", "100", "MW", "09:30 am-10:20 am"),
        sec("ENGL 1A", "200", "MW", "09:30 am-10:20 am"),
        sec("HIST 1A", "300", "TR", "01:00 pm-01:50 pm"),
    ]
    for pair in classify_pairs(rows)["pairs"]:
        if pair["overlap"]:
            assert pair["overlap_detail"]["days"] == ["M", "W"]
        else:
            assert "overlap_detail" not in pair


def test_classify_pairs_skips_same_course():
    """Same-course section pairs are excluded, just like find_conflicts."""
    rows = [
        sec("MATH 1A", "100", "MW", "09:30 am-10:20 am"),
        sec("MATH 1A", "101", "TR", "09:30 am-10:20 am"),
    ]
    result = classify_pairs(rows)
    assert result["pairs_evaluated"] == 0
    assert result["pairs"] == []


def test_classify_pairs_agrees_with_find_conflicts():
    """Regression guard: the shared engine keeps find_conflicts intact —
    classify_pairs' overlap_count must equal find_conflicts' conflict_count."""
    rows = [
        sec("MATH 1A", "100", "MW", "09:30 am-10:20 am"),
        sec("ENGL 1A", "200", "MW", "09:30 am-10:20 am"),
        sec("HIST 1A", "300", "MW", "10:00 am-10:50 am"),
        sec("BIOL 6A", "400", "F", "01:00 pm-03:50 pm"),
    ]
    legacy = find_conflicts(rows)
    split = classify_pairs(rows)
    assert split["overlap_count"] == legacy["conflict_count"]
    assert split["pairs_evaluated"] == legacy["pairs_evaluated"]
    assert split["sections_evaluated"] == legacy["sections_evaluated"]
