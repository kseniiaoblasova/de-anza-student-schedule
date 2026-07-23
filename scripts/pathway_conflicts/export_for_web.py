"""
Export pathway-conflict data from DynamoDB to a static JSON file for the web app.

Scans the deanza-pathway-conflicts table and reshapes it into a compact
structure keyed by pathway_id -> quarter_key, containing only the fields
the React frontend needs to display conflict indicators.

Output: web-app/src/data/pathway_conflicts.json

Usage:
    python scripts/pathway_conflicts/export_for_web.py
    python scripts/pathway_conflicts/export_for_web.py --dest path/to/output.json
    python scripts/pathway_conflicts/export_for_web.py --pretty  # human-readable
"""

import sys
import json
import argparse
from pathlib import Path
from decimal import Decimal

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from common import get_table, get_session, PROJECT_ROOT  # noqa: E402

CONFLICTS_TABLE = "deanza-pathway-conflicts"
DEFAULT_DEST = PROJECT_ROOT / "web-app" / "src" / "data" / "pathway_conflicts.json"


def _decimal_to_number(obj):
    """JSON serializer hook: convert DynamoDB Decimals to int or float."""
    if isinstance(obj, Decimal):
        return int(obj) if obj == int(obj) else float(obj)
    raise TypeError(f"Object of type {type(obj)} is not JSON serializable")


def scan_all(table):
    """Scan the entire conflicts table and return all items."""
    items, kwargs = [], {}
    while True:
        resp = table.scan(**kwargs)
        items.extend(resp.get("Items", []))
        if "LastEvaluatedKey" not in resp:
            break
        kwargs["ExclusiveStartKey"] = resp["LastEvaluatedKey"]
    return items


def _slim_conflict(conflict):
    """Extract only the fields the frontend needs for one conflict pair."""
    overlap = conflict.get("overlap", {})
    return {
        "course_a": conflict.get("course_a", ""),
        "course_b": conflict.get("course_b", ""),
        "days": overlap.get("days", []),
        "time_a": overlap.get("time_a", ""),
        "time_b": overlap.get("time_b", ""),
    }


def reshape_for_web(items):
    """Transform DynamoDB items into a compact lookup dict.

    Structure:
    {
      "<pathway_id>": {
        "<quarter_key>": {
          "conflict_count": int,
          "resolved_courses": [...],
          "missing_courses": [...],
          "conflicts": [ {course_a, course_b, days, time_a, time_b} ]
        }
      }
    }

    Quarter keys are stored as "year_1#fall" in DynamoDB; we convert to
    "year_1|fall" so the React app can split on "|" (matching the dropdown
    value format).
    """
    output = {}
    for item in items:
        pid = item.get("pathway_id", "")
        # Convert DynamoDB separator "#" to the web app's "|" separator
        quarter_key = item.get("quarter_key", "").replace("#", "|")

        if not pid or not quarter_key:
            continue

        pathway_entry = output.setdefault(pid, {})
        pathway_entry[quarter_key] = {
            "conflict_count": item.get("conflict_count", 0),
            "resolved_courses": item.get("resolved_courses", []),
            "missing_courses": item.get("missing_courses", []),
            "conflicts": [_slim_conflict(c) for c in item.get("conflicts", [])],
        }

    return output


def main():
    parser = argparse.ArgumentParser(
        description="Export pathway conflicts from DynamoDB to static JSON for the web app"
    )
    parser.add_argument(
        "--dest", default=str(DEFAULT_DEST),
        help=f"Output file path (default: {DEFAULT_DEST})"
    )
    parser.add_argument(
        "--pretty", action="store_true",
        help="Pretty-print the JSON (larger file, easier to inspect)"
    )
    parser.add_argument(
        "--table", default=CONFLICTS_TABLE,
        help=f"DynamoDB table to scan (default: {CONFLICTS_TABLE})"
    )
    args = parser.parse_args()

    session = get_session()
    table = get_table(args.table, session)

    # Pull all conflict records from DynamoDB
    print(f"Scanning '{args.table}'...")
    items = scan_all(table)
    print(f"  {len(items)} items retrieved")

    # Reshape for the web app
    web_data = reshape_for_web(items)
    pathway_count = len(web_data)
    quarters_with_conflicts = sum(
        1 for pathway in web_data.values()
        for q in pathway.values()
        if q["conflict_count"] > 0
    )
    print(f"  {pathway_count} pathways, {quarters_with_conflicts} quarters with conflicts")

    # Write the output
    dest = Path(args.dest)
    dest.parent.mkdir(parents=True, exist_ok=True)

    indent = 2 if args.pretty else None
    with open(dest, "w", encoding="utf-8") as f:
        json.dump(web_data, f, indent=indent, default=_decimal_to_number)

    size_kb = dest.stat().st_size / 1024
    print(f"\nWrote {dest} ({size_kb:.1f} KB)")


if __name__ == "__main__":
    main()
