"""
Populate deanza-pathway-conflicts: one item per pathway quarter with the time
conflicts among that quarter's course sections.

For every pathway in deanza-pathways-normalized, for every quarter that has
courses: map (year, quarter) -> term, pull ALL sections of each course from the
schedule for that term, send the whole section list to the deployed conflict
Lambda, and store the returned conflicts.

Dry run by default (calls the Lambda but writes nothing). --apply writes to the
table; --create-table provisions it first.

Usage:
    python scripts/pathway_conflicts/build_conflicts.py                 # dry run
    python scripts/pathway_conflicts/build_conflicts.py --limit 5       # first 5 pathways
    python scripts/pathway_conflicts/build_conflicts.py --apply --create-table
"""

import sys
import argparse
from pathlib import Path

from boto3.dynamodb.conditions import Key

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from common import get_table, get_session, create_table_if_absent  # noqa: E402
from pathway_conflicts.resolve import (  # noqa: E402
    YEAR_QUARTER_TO_TERM, term_for, index_sections_by_course,
    build_section_payload, build_conflict_item,
)
from pathway_conflicts.conflict_client import make_caller  # noqa: E402

NORMALIZED_TABLE = "deanza-pathways-normalized"
SCHEDULE_TABLE = "deanza-class-schedule"
CONFLICTS_TABLE = "deanza-pathway-conflicts"

# An empty report for quarters we don't need to send to the Lambda (fewer than
# two resolvable courses means no cross-course pair can exist).
def _empty_report(section_count):
    return {"conflict_count": 0, "sections_evaluated": section_count,
            "pairs_evaluated": 0, "conflicts": []}


def load_normalized_pathways(table_name=NORMALIZED_TABLE, session=None):
    """Scan all normalized pathway items."""
    table = get_table(table_name, session)
    items, kwargs = [], {}
    while True:
        resp = table.scan(**kwargs)
        items.extend(resp.get("Items", []))
        if "LastEvaluatedKey" not in resp:
            break
        kwargs["ExclusiveStartKey"] = resp["LastEvaluatedKey"]
    return items


def load_term_index(term_code, session=None):
    """Query one term's schedule rows and index them by canonical course."""
    table = get_table(SCHEDULE_TABLE, session)
    rows, kwargs = [], {"KeyConditionExpression": Key("term_code").eq(term_code)}
    while True:
        resp = table.query(**kwargs)
        rows.extend(resp.get("Items", []))
        if "LastEvaluatedKey" not in resp:
            break
        kwargs["ExclusiveStartKey"] = resp["LastEvaluatedKey"]
    return index_sections_by_course(rows)


def load_all_indexes(session=None):
    """Build the per-term section index for every term the mapping references."""
    indexes = {}
    for term in sorted(set(YEAR_QUARTER_TO_TERM.values())):
        indexes[term] = load_term_index(term, session)
        print(f"  term {term}: {len(indexes[term])} distinct courses indexed")
    return indexes


def process_pathway(pathway, indexes, caller):
    """Build a conflict item for each non-empty quarter of one pathway."""
    items = []
    for year_key, quarters in pathway.get("years", {}).items():
        for quarter_key, quarter in quarters.items():
            courses = quarter.get("normalized_courses", [])
            if not courses:
                continue  # nothing to analyze this quarter
            term = term_for(year_key, quarter_key)
            if term is None:
                continue
            sections, resolved, missing = build_section_payload(courses, indexes[term])

            # Only call the service when a cross-course pair is possible.
            if len(resolved) >= 2:
                report = caller({"sections": sections, "term_code": term})
            else:
                report = _empty_report(len(sections))

            items.append(build_conflict_item(
                pathway, year_key, quarter_key, term, report, resolved, missing))
    return items


def write_items(table, items):
    """Batch-write items (idempotent by pathway_id + quarter_key)."""
    with table.batch_writer() as batch:
        for item in items:
            batch.put_item(Item=item)
    return len(items)


def summarize(items):
    quarters_with_conflicts = sum(1 for i in items if i["conflict_count"] > 0)
    total_conflicts = sum(i["conflict_count"] for i in items)
    return {
        "pathway_quarters": len(items),
        "quarters_with_conflicts": quarters_with_conflicts,
        "total_conflict_pairs": total_conflicts,
    }


def main():
    parser = argparse.ArgumentParser(description="Populate the pathway-conflicts table (dry run by default)")
    parser.add_argument("--apply", action="store_true", help="Write results to the table")
    parser.add_argument("--create-table", action="store_true", help="Create the table first if absent")
    parser.add_argument("--mode", choices=["direct", "http"], default="direct",
                        help="How to call the conflict Lambda (default: direct invoke)")
    parser.add_argument("--limit", type=int, default=None, help="Process only the first N pathways")
    parser.add_argument("--samples", type=int, default=3, help="Sample items to print")
    args = parser.parse_args()

    session = get_session()
    caller = make_caller(args.mode, session=session)

    print("Loading schedule indexes per term...")
    indexes = load_all_indexes(session)

    pathways = load_normalized_pathways(session=session)
    if args.limit:
        pathways = pathways[: args.limit]
    print(f"Processing {len(pathways)} pathways...")

    items = []
    for n, pathway in enumerate(pathways, 1):
        items.extend(process_pathway(pathway, indexes, caller))
        if n % 25 == 0:
            print(f"  ...{n} pathways, {len(items)} quarter-items so far")

    stats = summarize(items)
    print("\n=== Pathway-conflict results ===")
    for k, v in stats.items():
        print(f"  {k:24} {v}")

    print(f"\n=== {args.samples} sample items (with conflicts) ===")
    shown = 0
    for item in items:
        if item["conflict_count"] > 0 and shown < args.samples:
            shown += 1
            first = item["conflicts"][0]
            print(f"\n- {item['pathway_id']} | {item['quarter_key']} (term {item['term_code']})")
            print(f"    courses={item['course_count']} pairs={item['pairs_evaluated']} "
                  f"conflicts={item['conflict_count']} ({item['conflict_percentage']}%)")
            print(f"    e.g. {first['course_a']} vs {first['course_b']} on {first['overlap']['days']}")

    if args.apply:
        if args.create_table:
            created = create_table_if_absent(CONFLICTS_TABLE, session)
            print(f"\n{'Created' if created else 'Already exists'}: {CONFLICTS_TABLE}")
        table = get_table(CONFLICTS_TABLE, session)
        written = write_items(table, items)
        print(f"Wrote {written} items to '{CONFLICTS_TABLE}'.")
    else:
        print(f"\nDry run — nothing written. Re-run with --apply "
              f"(and --create-table the first time) to populate '{CONFLICTS_TABLE}'.")


if __name__ == "__main__":
    main()
