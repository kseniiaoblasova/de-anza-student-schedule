"""
Pure helpers for turning a pathway quarter into a conflict-table item.

The flow per pathway quarter:
  normalized_courses (canonical codes)  ─►  schedule sections for the term
                                        ─►  section payload for the conflict Lambda
                                        ─►  conflict report  ─►  DynamoDB item

Course identity is bridged with the same `normalize_course` used everywhere else,
so pathway codes ("MATH 1A") line up with schedule rows ("MATH D001A.").

Pure logic only (no AWS, no I/O).
"""

from decimal import Decimal

from course_pairing.normalization import normalize_course

# Maps a pathway (year, quarter) to a schedule term_code.
#
# Term codes end 22/32/42 = Fall/Winter/Spring. The pathway catalog is 2025-26
# and a two-year associate spans two academic years, so year_1 uses the real
# AY2025-26 schedule and year_2 the real AY2026-27 schedule. Both are published
# schedules actually loaded in deanza-class-schedule (no proxy/duplication).
# Override this dict to analyze a different term alignment.
YEAR_QUARTER_TO_TERM = {
    ("year_1", "fall"): "202622",
    ("year_1", "winter"): "202632",
    ("year_1", "spring"): "202642",
    ("year_2", "fall"): "202722",
    ("year_2", "winter"): "202732",
    ("year_2", "spring"): "202742",
}

# Schedule fields forwarded to the conflict Lambda for each section. `course` is
# set to the canonical code (not the raw schedule label) so same-course pairs are
# grouped correctly and the conflict output reads in pathway terms.
_SECTION_FIELDS = ("crn", "section", "meeting_days", "meeting_times",
                   "instruction_method", "instructor", "room", "building",
                   "part_term", "start_date", "end_date")


def term_for(year_key, quarter_key, mapping=YEAR_QUARTER_TO_TERM):
    """Return the term_code for a (year, quarter), or None if unmapped."""
    return mapping.get((year_key, quarter_key))


def index_sections_by_course(rows):
    """Index schedule rows by canonical course code.

    Returns {canonical_course: [row, ...]}. Rows whose subject/number can't be
    canonicalized are skipped. Every meeting row is kept (the Lambda groups by
    CRN), so multi-meeting sections stay intact.
    """
    index = {}
    for row in rows:
        code = normalize_course(row.get("subject"), row.get("number"))
        if code:
            index.setdefault(code, []).append(row)
    return index


def _section_payload(row, canonical_course):
    """Shape one schedule row into a Lambda section object."""
    section = {"course": canonical_course}
    for f in _SECTION_FIELDS:
        val = row.get(f)
        if val not in (None, ""):
            section[f] = str(val)
    return section


def build_section_payload(courses, section_index):
    """Collect all sections for a quarter's courses into the Lambda payload.

    Returns (sections, resolved_courses, missing_courses):
      - sections: flat list of section objects (all sections of every course).
      - resolved_courses: courses that had at least one section in the term.
      - missing_courses: courses with no section (not offered that term, or a
        pairing gap such as a statewide C-number the schedule doesn't use).
    """
    sections, resolved, missing = [], [], []
    for course in courses:
        rows = section_index.get(course)
        if rows:
            resolved.append(course)
            for row in rows:
                sections.append(_section_payload(row, course))
        else:
            missing.append(course)
    return sections, resolved, missing


def _percentage(conflict_count, pairs_evaluated):
    """Conflict rate as a Decimal (DynamoDB rejects float); 0 when no pairs."""
    if not pairs_evaluated:
        return Decimal("0")
    return Decimal(str(round(100.0 * conflict_count / pairs_evaluated, 2)))


def build_conflict_item(pathway, year_key, quarter_key, term_code,
                        report, resolved_courses, missing_courses):
    """Assemble the DynamoDB item for one pathway quarter.

    Combines pathway identity, the term analyzed, the conflict report from the
    Lambda, and which courses resolved vs were missing.
    """
    return {
        "pathway_id": pathway["pathway_id"],
        "quarter_key": f"{year_key}#{quarter_key}",
        "year": year_key,
        "quarter": quarter_key,
        "term_code": term_code,
        "program_name": pathway.get("program_name", ""),
        "village": pathway.get("village", ""),
        "credential_type": pathway.get("credential_type", ""),
        "resolved_courses": resolved_courses,
        "missing_courses": missing_courses,
        "course_count": len(resolved_courses),
        "section_count": report.get("sections_evaluated", 0),
        "pairs_evaluated": report.get("pairs_evaluated", 0),
        "conflict_count": report.get("conflict_count", 0),
        "conflict_percentage": _percentage(
            report.get("conflict_count", 0), report.get("pairs_evaluated", 0)),
        "conflicts": report.get("conflicts", []),
    }
