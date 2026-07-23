"""
Read program-pathway items back out of the DynamoDB table.

The table has a single partition key (pathway_id), so exact-id lookups are
cheap get_item calls. Every other view is a scan with a filter — fine here
because the dataset is tiny (~238 items).

Usage:
    python scripts/pathways/query.py --count
    python scripts/pathways/query.py --id "2025 ADMJ all.pdf#1"
    python scripts/pathways/query.py --village "Physical Sciences and Technology"
    python scripts/pathways/query.py --program accounting
    python scripts/pathways/query.py --all
"""

import sys
import json
import argparse
from pathlib import Path

from boto3.dynamodb.conditions import Attr

# Make the shared helpers importable when run directly
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from common import get_table

DEFAULT_TABLE = "deanza-pathways"


def scan_all(table, filter_expr=None):
    """Scan the whole table, following pagination, optionally with a filter."""
    items = []
    kwargs = {}
    if filter_expr is not None:
        kwargs["FilterExpression"] = filter_expr

    # DynamoDB returns at most 1MB per scan page, so loop on LastEvaluatedKey
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
    parser = argparse.ArgumentParser(description="Query the pathways table")
    parser.add_argument("--table", default=DEFAULT_TABLE, help="DynamoDB table name")
    parser.add_argument("--id", help="Fetch one item by pathway_id")
    parser.add_argument("--village", help="List pathways in this village")
    parser.add_argument("--program", help="Match program_name substring (case-insensitive)")
    parser.add_argument("--all", action="store_true", help="Dump every item")
    parser.add_argument("--count", action="store_true", help="Show item count + a sample")
    args = parser.parse_args()

    table = get_table(args.table)

    # Exact key lookup: the only true key query, everything else scans
    if args.id:
        item = table.get_item(Key={"pathway_id": args.id}).get("Item")
        dump(item if item else {"error": f"no item with pathway_id '{args.id}'"})
        return

    if args.village:
        dump(scan_all(table, Attr("village").eq(args.village)))
        return

    if args.program:
        items = scan_all(table)
        term = args.program.lower()
        dump([i for i in items if term in i.get("program_name", "").lower()])
        return

    if args.all:
        dump(scan_all(table))
        return

    if args.count:
        items = scan_all(table)
        print(f"{len(items)} items in '{args.table}'.")
        if items:
            print("\nSample item:")
            dump(items[0])
        return

    parser.print_help()


if __name__ == "__main__":
    main()
