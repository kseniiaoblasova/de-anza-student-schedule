"""
Turn a pathway quarter's verbose course text into clean canonical course codes.

Pathway quarters store courses as free text split across list entries, e.g.

    ["ADMJ 3, ADMJ 6, ADMJ 11, ADMJ", "53, ADMJ 54, ADMJ 55"]
    ["ENGL C1000 (formerly EWRT 1A) or ESL 5 as required"]
    ["MATH as required"]

The parser walks the tokens in order, carrying the "current subject" so a
subject dangling at the end of one entry ("... ADMJ") applies to the bare
numbers that open the next entry ("53, ..."). Any word that isn't a known
subject resets the carry, so list prose ("Complete 25 units from List A")
cannot inherit a stale subject and invent a course.

Pure logic only (no AWS/I/O). The subject allow-list is injected by the caller
— the runnable entry point sources it from the real schedule subjects.
"""

import re

from course_pairing.normalization import normalize_course

# Alphanumeric runs; punctuation and whitespace are separators. "C1000", "64X",
# "ADMJ" and "53" each come out as one token.
_TOKEN_RE = re.compile(r"[A-Z0-9]+")

# A token shaped like a course number: optional leading letter (statewide "C"),
# 1-4 digits, up to 3 trailing letters. Subjects (pure letters) never match this.
_NUMBER_TOKEN_RE = re.compile(r"^[A-Z]?\d{1,4}[A-Z]{0,3}$")

# Ordinals ("1ST", "2ND") are course-number-shaped but are prose ("1st course").
# No real De Anza course number ends in these, so they're never courses.
_ORDINAL_RE = re.compile(r"^\d{1,4}(ST|ND|RD|TH)$")


def _tokens(text):
    return _TOKEN_RE.findall(str(text).upper())


def extract_courses(entries, valid_subjects):
    """Extract canonical courses from one quarter's course entries.

    Returns (normalized_courses, unresolved_entries):
      - normalized_courses: canonical "SUBJECT NUMBER" codes, deduplicated with
        first-seen order preserved across the whole quarter.
      - unresolved_entries: the original text of any entry that yielded no course
        (vague requirements like "MATH as required", list headers, etc.), kept so
        nothing is silently dropped.

    `valid_subjects` is a set of uppercase subject codes; only these anchor a
    course. A course whose subject isn't in the set is treated as prose and does
    not appear in the output (documented limitation — such subjects aren't offered
    in the schedule anyway, so they could never pair).
    """
    courses = []
    seen = set()
    unresolved = []
    current_subject = None

    for entry in entries or []:
        if entry is None:
            continue
        produced = 0
        for tok in _tokens(entry):
            if tok in valid_subjects:
                # A recognized subject anchors any numbers that follow it.
                current_subject = tok
            elif _ORDINAL_RE.match(tok):
                # "1st"/"2nd" is list prose, not a course; break the carry.
                current_subject = None
            elif _NUMBER_TOKEN_RE.match(tok):
                # A number attaches to the carried subject, if any.
                if current_subject:
                    code = normalize_course(current_subject, tok)
                    if code:
                        produced += 1
                        if code not in seen:
                            seen.add(code)
                            courses.append(code)
            else:
                # Prose word / single letter / unknown subject: break the carry
                # so a stale subject can't leak into unrelated list text.
                current_subject = None

        text = str(entry).strip()
        if produced == 0 and text:
            unresolved.append(text)

    return courses, unresolved


def normalize_pathway_years(years, valid_subjects):
    """Apply extract_courses to every quarter of a pathway's `years` map.

    Returns a new years map of the same year/quarter shape, where each quarter
    is `{"normalized_courses": [...], "unresolved_entries": [...]}` built from
    the source `required_courses` + `additional_courses`. The source arrays are
    read only, never mutated.
    """
    out = {}
    for year_key, quarters in (years or {}).items():
        out[year_key] = {}
        for quarter_key, quarter in (quarters or {}).items():
            entries = list(quarter.get("required_courses", [])) + list(
                quarter.get("additional_courses", [])
            )
            courses, unresolved = extract_courses(entries, valid_subjects)
            out[year_key][quarter_key] = {
                "normalized_courses": courses,
                "unresolved_entries": unresolved,
            }
    return out
