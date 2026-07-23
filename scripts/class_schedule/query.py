"""
Read class-schedule section rows out of the DynamoDB table.

Because the table is partitioned by term_code, "everything in one quarter" is an
efficient Query. Narrower lookups (by course/subject) filter within a term, or
fall back to a table scan when no term is given.

Usage:
    python scripts/class_schedule/query.py --count
    python scripts/class_schedule/query.py --term 202722                 # whole quarter
    python scripts/class_schedule/query.py --term 202722 --course "MATH 1A"
    python scripts/class_schedule/query.py --term 202722 --crn 28143
    python scripts/class_schedule/query.py --subject MATH                # scan all terms
"""

import sys
import json
import argparse
from pathlib import Path

from boto3.dynamodb.conditions import Key, Attr

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from common import get_table

DEFAULT_TABLE = "deanza-class-schedule"


def query_term(table, term_code, filter_expr=None):
    """Query one term partition, following pagination, with an optional filter."""
    items = []
    kwargs = {"KeyConditionExpression": Key("term_code").eq(term_code)}
    if filter_expr is not None:
        kwargs["FilterExpression"] = filter_expr
    while True:
        resp = table.query(**kwargs)
        items.extend(resp.get("Items", []))
        if "LastEvaluatedKey" not in resp:
            break
        kwargs["ExclusiveStartKey"] = resp["LastEvaluatedKey"]
    return items


def scan_all(table, filter_expr=None):
    """Scan the whole table (all terms) with an optional filter."""
    items = []
    kwargs = {}
    if filter_expr is not None:
        kwargs["FilterExpression"] = filter_expr
    while True:
        resp = table.scan(**kwargs)
        items.extend(resp.get("Items", []))
        if "LastEvaluatedKey" not in resp:
            break
        kwargs["ExclusiveStartKey"] = resp["LastEvaluatedKey"]
    return items


def dump(items):
    """Print items as readable JSON (default=str handles Decimal from DynamoDB)."""
    print(json.dumps(items, indent=2, default=str))


def main():
    parser = argparse.ArgumentParser(description="Query the class-schedule table")
    parser.add_argument("--table", default=DEFAULT_TABLE, help="DynamoDB table name")
    parser.add_argument("--term", help="Term code, e.g. 202722 (enables efficient query)")
    parser.add_argument("--course", help="Course label to match, e.g. 'MATH 1A'")
    parser.add_argument("--subject", help="Subject code to match, e.g. MATH")
    parser.add_argument("--crn", help="Fetch sections with this CRN (needs --term for a direct query)")
    parser.add_argument("--all", action="store_true", help="Dump every item")
    parser.add_argument("--count", action="store_true", help="Show item count + a sample")
    args = parser.parse_args()

    table = get_table(args.table)

    # Build an optional attribute filter shared by query and scan paths
    filt = None
    if args.course:
        filt = Attr("course").eq(args.course)
    elif args.subject:
        filt = Attr("subject").eq(args.subject)
    if args.crn:
        crn_filt = Attr("crn").eq(str(args.crn))
        filt = crn_filt if filt is None else (filt & crn_filt)

    # Prefer a term-scoped query when a term is given; otherwise scan
    if args.term and not args.count and not args.all:
        dump(query_term(table, args.term, filt))
        return

    if args.all:
        dump(query_term(table, args.term, filt) if args.term else scan_all(table, filt))
        return

    if args.count:
        items = query_term(table, args.term, filt) if args.term else scan_all(table, filt)
        scope = f"term {args.term}" if args.term else "all terms"
        print(f"{len(items)} items ({scope}) in '{args.table}'.")
        if items:
            print("\nSample item:")
            dump(items[0])
        return

    # No term: fall back to a filtered scan (or help if no filter given)
    if filt is not None:
        dump(scan_all(table, filt))
        return

    parser.print_help()


if __name__ == "__main__":
    main()
