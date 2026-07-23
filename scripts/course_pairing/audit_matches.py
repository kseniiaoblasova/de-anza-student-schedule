"""
Audit how well normalized pathway courses pair with the class schedule.

Coverage question for the MVP: of the distinct canonical courses named across
all pathway maps, how many exist as a real course somewhere in
`deanza-class-schedule`? This is course-identity coverage across all terms —
per-quarter availability is a later concern.

Pure comparison logic (schedule_course_set, collect_pathway_courses,
compute_audit) is separated from I/O so it can be unit-tested without AWS. The
runnable `main` reads the schedule (with an optional local cache so repeated
runs during tuning don't rescan 25k rows), builds the pathway side, and writes a
console summary plus a JSON report to data/reports/course-pairing/.

Pathway courses can come from the normalized table (--source normalized-table)
or be built on the fly from the source pathways (--source build, the default)
so the audit can run before the normalized table is loaded.
"""

import sys
import json
import argparse
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from common import PROJECT_ROOT, get_table  # noqa: E402
from course_pairing.normalization import normalize_course  # noqa: E402
from course_pairing.normalize_pathways import (  # noqa: E402
    NORMALIZED_TABLE, SCHEDULE_TABLE,
    load_subjects, load_source_pathways, build_all,
)

REPORT_DIR = PROJECT_ROOT / "data" / "reports" / "course-pairing"


# ---- pure comparison logic ----

def schedule_course_set(schedule_items):
    """Canonical course codes present in the schedule (deduped across rows).

    Many rows share a course (multi-meeting CRNs, multiple sections), so a set
    keeps the count at course identity rather than meeting-row volume.
    """
    courses = set()
    for item in schedule_items:
        code = normalize_course(item.get("subject"), item.get("number"))
        if code:
            courses.add(code)
    return courses


def collect_pathway_courses(normalized_items):
    """Map each distinct pathway course to where it appears, and count unresolved.

    Returns (occurrences, unresolved_total) where occurrences is
    {canonical_course: [ {pathway_id, program_name, year, quarter}, ... ]}.
    """
    occurrences = {}
    unresolved_total = 0
    for item in normalized_items:
        pid = item.get("pathway_id", "")
        program = item.get("program_name", "")
        for year_key, quarters in item.get("years", {}).items():
            for quarter_key, quarter in quarters.items():
                unresolved_total += len(quarter.get("unresolved_entries", []))
                for course in quarter.get("normalized_courses", []):
                    occurrences.setdefault(course, []).append({
                        "pathway_id": pid,
                        "program_name": program,
                        "year": year_key,
                        "quarter": quarter_key,
                    })
    return occurrences, unresolved_total


def compute_audit(pathway_occurrences, schedule_set, unresolved_total=0):
    """Compare distinct pathway courses to the schedule set and build the report."""
    distinct = sorted(pathway_occurrences)
    matched = [c for c in distinct if c in schedule_set]
    unmatched = [c for c in distinct if c not in schedule_set]
    total = len(distinct)
    pct = round(100.0 * len(matched) / total, 2) if total else 0.0

    return {
        "distinct_pathway_courses": total,
        "matched": len(matched),
        "unmatched": len(unmatched),
        "match_percentage": pct,
        "schedule_distinct_courses": len(schedule_set),
        "unresolved_entries_total": unresolved_total,
        # unmatched courses with the pathways/quarters that reference them
        "unmatched_courses": [
            {"course": c, "occurrences": pathway_occurrences[c]} for c in unmatched
        ],
    }


# ---- I/O ----

def read_schedule_items(table_name=SCHEDULE_TABLE):
    """Scan the schedule projecting only subject/number (all terms)."""
    table = get_table(table_name)
    items = []
    kwargs = {"ProjectionExpression": "subject, #n", "ExpressionAttributeNames": {"#n": "number"}}
    while True:
        resp = table.scan(**kwargs)
        items.extend(resp.get("Items", []))
        if "LastEvaluatedKey" not in resp:
            break
        kwargs["ExclusiveStartKey"] = resp["LastEvaluatedKey"]
    return items


def load_schedule_set(cache_path=None, use_cache=False):
    """Return the schedule course set, reading/writing an optional JSON cache."""
    if use_cache and cache_path and Path(cache_path).exists():
        with open(cache_path) as f:
            courses = set(json.load(f))
        print(f"Schedule course set: {len(courses)} courses (cache).")
        return courses
    items = read_schedule_items()
    courses = schedule_course_set(items)
    print(f"Schedule course set: {len(courses)} distinct courses "
          f"from {len(items)} schedule rows.")
    if cache_path:
        Path(cache_path).parent.mkdir(parents=True, exist_ok=True)
        with open(cache_path, "w") as f:
            json.dump(sorted(courses), f)
    return courses


def read_normalized_items(source, json_path):
    """Get normalized pathway items from the normalized table or by building them."""
    if source == "normalized-table":
        table = get_table(NORMALIZED_TABLE)
        items, kwargs = [], {}
        while True:
            resp = table.scan(**kwargs)
            items.extend(resp.get("Items", []))
            if "LastEvaluatedKey" not in resp:
                break
            kwargs["ExclusiveStartKey"] = resp["LastEvaluatedKey"]
        return items
    # build: normalize source pathways on the fly (works before the table exists)
    subjects = load_subjects()
    records = load_source_pathways(from_table=False, json_path=json_path)
    return build_all(records, subjects)


def print_summary(report, examples=15):
    print("\n=== Pathway -> schedule pairing audit ===")
    for k in ("distinct_pathway_courses", "matched", "unmatched", "match_percentage",
              "schedule_distinct_courses", "unresolved_entries_total"):
        print(f"  {k:28} {report[k]}")
    print(f"\n  first {examples} unmatched courses:")
    for entry in report["unmatched_courses"][:examples]:
        occ = entry["occurrences"][0]
        n = len(entry["occurrences"])
        print(f"    {entry['course']:14} ({n:3} occ)  e.g. {occ['program_name'][:48]} "
              f"[{occ['year']}/{occ['quarter']}]")


def main():
    parser = argparse.ArgumentParser(description="Audit pathway/schedule course pairing")
    parser.add_argument("--source", choices=["build", "normalized-table"], default="build",
                        help="Where pathway courses come from (default: build from source)")
    parser.add_argument("--json", default=None, help="Source pathways JSON (for --source build)")
    parser.add_argument("--use-cache", action="store_true",
                        help="Reuse the cached schedule course set if present")
    parser.add_argument("--out", default=str(REPORT_DIR / "pairing_audit.json"),
                        help="Where to write the JSON report")
    args = parser.parse_args()

    from course_pairing.normalize_pathways import DEFAULT_JSON
    json_path = args.json or str(DEFAULT_JSON)
    cache_path = REPORT_DIR / "schedule_courses.json"

    schedule_set = load_schedule_set(cache_path=cache_path, use_cache=args.use_cache)
    normalized_items = read_normalized_items(args.source, json_path)
    occurrences, unresolved_total = collect_pathway_courses(normalized_items)
    report = compute_audit(occurrences, schedule_set, unresolved_total)

    print_summary(report)

    Path(args.out).parent.mkdir(parents=True, exist_ok=True)
    with open(args.out, "w") as f:
        json.dump(report, f, indent=2)
    print(f"\nFull report written to {args.out}")


if __name__ == "__main__":
    main()
