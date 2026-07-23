"""
Resolve a term + canonical course list to schedule section payloads (I/O).

This is the term-aware front half of the student planner: given a term and the
canonical course codes a student wants ("MATH 1A", "ENGL 1A", ...), it reads
those courses' sections out of `deanza-class-schedule` and shapes them like the
conflict engine's section input. Everything but the DynamoDB read is reused —
`query_term` for the term query, and `index_sections_by_course` /
`build_section_payload` from the pathway pipeline for the canonical-code bridge —
so this module is thin composition and the only side effect is the table read.

Kept separate from the pure engine and from the Lambda handler so the DynamoDB
dependency stays isolated (and swappable in tests via the `table` argument).
"""

import os
import sys
from pathlib import Path

import boto3
from boto3.dynamodb.conditions import Attr

# Reuse the shared query + canonical-code resolution logic from sibling packages.
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from class_schedule.query import query_term
from pathway_conflicts.resolve import index_sections_by_course, build_section_payload

DEFAULT_TABLE = os.environ.get("SCHEDULE_TABLE", "deanza-class-schedule")


def _get_table(table_name):
    """DynamoDB Table via the default credential chain (Lambda role / local env).

    Deliberately does NOT use `common.get_session()`: that reads explicit access
    keys from the environment, which is right for the CLI loaders but wrong in
    Lambda, where credentials come from the execution role. Region falls back
    through the Lambda-provided AWS_REGION, then AWS_DEFAULT_REGION, then us-west-2.
    """
    region = os.environ.get("AWS_REGION") or os.environ.get("AWS_DEFAULT_REGION") or "us-west-2"
    return boto3.resource("dynamodb", region_name=region).Table(table_name)


def _subject_filter(courses):
    """Attribute filter narrowing the term query to the requested subjects.

    Canonical codes are "<SUBJECT> <NUMBER>"; the schedule stores the same
    subject code. Filtering to those subjects trims the term partition (a whole
    quarter) down to the handful of relevant rows before indexing. Returns None
    when no subject can be derived (then the whole term is read).
    """
    subjects = sorted({c.split()[0] for c in courses if c and c.split()})
    if not subjects:
        return None
    return Attr("subject").is_in(subjects)


def lookup_sections(term_code, courses, table=None):
    """Return (sections, offered_courses, not_offered_courses) for a term.

    Queries the term partition (filtered to the requested subjects), indexes the
    rows by canonical course, and collects every section of each requested
    course. Courses with no section in the term come back as not_offered so the
    caller can surface them rather than silently drop them.
    """
    table = table or _get_table(DEFAULT_TABLE)
    rows = query_term(table, term_code, _subject_filter(courses))
    index = index_sections_by_course(rows)
    return build_section_payload(courses, index)
