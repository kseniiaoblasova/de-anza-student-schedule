"""
AWS Lambda entry point for the student schedule PLANNER.

The sibling `lambda_handler` is handed a ready-made section list; this endpoint
is term-aware. Given a term and a list of canonical course codes, it reads that
term's sections from `deanza-class-schedule` itself (`section_lookup`),
classifies every cross-course section pair as overlapping or clear
(`conflict_engine.classify_pairs`), and returns a student-facing summary — an
overlap percentage plus the two pair lists — so the UI can show "which of these
can I take together, and which clash."

Request body:
    { "term_code": "202722", "courses": ["MATH 1A", "ENGL 1A", ...] }

Response 200:
    {
      "term_code": "202722",
      "requested_courses":  [...],           # echo of the input
      "offered_courses":    [...],           # had >=1 section this term
      "not_offered_courses":[...],           # requested but nothing scheduled
      "section_count":  int,
      "pairs_evaluated":int,                 # cross-course section pairs compared
      "overlap_count":  int,
      "clear_count":    int,
      "overlap_percentage": float,           # overlap_count / pairs_evaluated * 100
      "overlaps": [ pair, ... ],             # the clashing pairs (with overlap_detail)
      "clear":    [ pair, ... ]              # the compatible pairs
    }

No API key (public read of published schedule data). CORS headers on every
response, so a browser can call it directly.
"""

# Reuse the HTTP/event plumbing from the sibling handler verbatim — same package,
# same CORS/preflight/unwrap behavior, no reason to duplicate it.
from conflicts.lambda_handler import (
    _response, _request_method, _preflight_response, _extract_payload,
)
from conflicts.conflict_engine import classify_pairs
from conflicts.section_lookup import lookup_sections


def _percentage(part, whole):
    """Percentage of `part` out of `whole`, rounded to 1 dp; 0 when no whole."""
    if not whole:
        return 0.0
    return round(100.0 * part / whole, 1)


def _build_report(term_code, courses):
    """Do the real work: term lookup -> classify -> student-facing summary."""
    sections, offered, not_offered = lookup_sections(term_code, courses)
    classified = classify_pairs(sections)

    # Split the classified pairs into the two lists the UI renders separately.
    overlaps = [p for p in classified["pairs"] if p["overlap"]]
    clear = [p for p in classified["pairs"] if not p["overlap"]]

    return {
        "term_code": term_code,
        "requested_courses": courses,
        "offered_courses": offered,
        "not_offered_courses": not_offered,
        "section_count": classified["sections_evaluated"],
        "pairs_evaluated": classified["pairs_evaluated"],
        "overlap_count": classified["overlap_count"],
        "clear_count": len(clear),
        "overlap_percentage": _percentage(
            classified["overlap_count"], classified["pairs_evaluated"]),
        "overlaps": overlaps,
        "clear": clear,
    }


def handler(event, context=None):
    """Lambda handler: validate, resolve+classify, return an HTTP response."""
    # Answer the CORS preflight before any validation (no body, no key).
    if _request_method(event) == "OPTIONS":
        return _preflight_response()

    # Unwrap and parse the request body.
    try:
        payload = _extract_payload(event)
    except (ValueError, TypeError):
        return _response(400, {"error": "Request body is not valid JSON."})

    # Validate the two required fields.
    term_code = payload.get("term_code")
    if not isinstance(term_code, str) or not term_code.strip():
        return _response(400, {"error": "Field 'term_code' is required (a term code string)."})
    courses = payload.get("courses")
    if not isinstance(courses, list) or not courses:
        return _response(400, {"error": "Field 'courses' is required and must be a non-empty list."})

    # Read the term's sections, classify the pairs, and return the summary.
    try:
        return _response(200, _build_report(term_code.strip(), courses))
    except Exception as e:  # noqa: BLE001 - never leak a stack trace to the caller
        return _response(500, {"error": "Internal error computing the schedule plan.",
                               "detail": type(e).__name__})
