"""
Canonical course-code normalization shared by both sides of the pairing.

The pathway maps and the class schedule name the same course differently:

    schedule:  subject="MATH", number="D001A."   ->  "MATH 1A"
    pathway:   "MATH 1A"                          ->  "MATH 1A"
    pathway:   "ENGL C1000"                       ->  "ENGL C1000"  (statewide, kept)

Everything here is pure (no AWS, no I/O) so it can be unit-tested in isolation
and reused by the pathway parser, the loader, and the audit. The canonical form
is the string "<SUBJECT> <NUMBER>", uppercase, with the De Anza campus "D"
prefix and zero-padding removed but statewide "C" numbers and letter suffixes
(1A, 64X, 90A) preserved.
"""

import re

# A course number decomposed into: optional leading letters (prefix such as the
# De Anza campus "D" or the statewide "C"), the digit run, and an optional
# letter suffix (A, X, ...). Anchored so it only matches a clean whole number.
_NUMBER_RE = re.compile(r"^([A-Z]*)(\d{1,4})([A-Z]{0,3})$")

# A single "SUBJECT NUMBER" course code embedded in free text: a 2-8 letter
# subject, whitespace, then a number token (optional prefix letter, 1-4 digits,
# up to 3 suffix letters). Used to pull a code out of a pathway string.
_COURSE_RE = re.compile(r"\b([A-Z]{2,8})\s+([A-Z]?\d{1,4}[A-Z]{0,3})\b")


def normalize_number(raw):
    """Reduce a raw course number to canonical form, or return None.

    Drops the De Anza campus "D" prefix and leading zeros, strips trailing
    punctuation/whitespace, and keeps statewide "C" prefixes and letter
    suffixes. Returns None when the input isn't a parseable course number so
    callers can treat it as unresolved rather than guess.
    """
    if raw is None:
        return None

    # Clean surface noise: uppercase, drop internal spaces, strip trailing dots.
    cleaned = str(raw).strip().upper().replace(" ", "").rstrip(".")
    if not cleaned:
        return None

    m = _NUMBER_RE.match(cleaned)
    if not m:
        return None

    prefix, digits, suffix = m.groups()

    # "D" is the De Anza campus code and never part of the shared identity; any
    # other prefix (notably statewide "C") is meaningful and kept.
    if prefix == "D":
        prefix = ""

    # Strip zero-padding from the digit run ("001" -> "1"), but never empty it.
    digits = digits.lstrip("0") or "0"

    return f"{prefix}{digits}{suffix}"


def normalize_course(subject, number):
    """Canonicalize a split subject/number pair (the schedule's shape).

    Returns "<SUBJECT> <NUMBER>" or None if either part is missing or the
    number can't be parsed.
    """
    if not subject:
        return None
    subject_norm = str(subject).strip().upper()
    number_norm = normalize_number(number)
    if not subject_norm or not number_norm:
        return None
    return f"{subject_norm} {number_norm}"


def iter_course_codes(text, valid_subjects=None):
    """Yield every canonical course code found in a free-text string.

    A course-shaped token is "<SUBJECT> <NUMBER>". Prose like "Complete 25" or
    "Area 3" is also course-shaped, so when `valid_subjects` (a set of real
    subject codes, e.g. from the schedule) is given, only tokens whose subject
    is in that set are yielded — this is what separates real courses from
    English words. Without it the match is permissive (best effort).
    """
    if not text:
        return
    for subject, number in _COURSE_RE.findall(str(text).upper()):
        if valid_subjects is not None and subject not in valid_subjects:
            continue
        code = normalize_course(subject, number)
        if code:
            yield code


def parse_course_code(text, valid_subjects=None):
    """Return the first canonical course code in `text`, or None.

    Convenience wrapper over `iter_course_codes` for callers that expect a
    single course. Pass `valid_subjects` to reject prose that merely looks like
    a course code.
    """
    return next(iter_course_codes(text, valid_subjects), None)
