"""
Export deanza-pathway-conflicts to the single JSON the web app bundles at build
time (web-app/src/data/pathway_conflicts.json).

The conflict pipeline already stores canonical course codes (built from the
normalized pathways), so this is a straight read-trim-write: scan the table,
keep only the fields the UI renders, convert DynamoDB Decimals to numbers, and
nest the result as pathway_id -> quarter_key for O(1) lookup in the frontend.

Static-export tradeoff: the app is only as fresh as the last run. Re-run this
after rebuilding deanza-pathway-conflicts (build_conflicts.py --apply).

Usage:
    python scripts/pathway_conflicts/export_web_data.py
    python scripts/pathway_conflicts/export_web_data.py --out some/other.json
"""

import sys
import json
import argparse
from decimal import Decimal
from pathlib import Path

# Make shared helpers importable when run directly.
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from common import get_table, PROJECT_ROOT  # noqa: E402

CONFLICTS_TABLE = "deanza-pathway-conflicts"
DEFAULT_OUT = PROJECT_ROOT / "web-app" / "src" / "data" / "pathway_conflicts.json"


def _num(value):
    """DynamoDB stores numbers as Decimal; JSON needs int/float."""
    if isinstance(value, Decimal):
        return int(value) if value == value.to_integral_value() else float(value)
    return value


def scan_conflicts(table_name=CONFLICTS_TABLE):
    """Read every pathway-quarter item from the conflicts table."""
    table = get_table(table_name)
    items, kwargs = [], {}
    while True:
        resp = table.scan(**kwargs)
        items.extend(resp.get("Items", []))
        if "LastEvaluatedKey" not in resp:
            break
        kwargs["ExclusiveStartKey"] = resp["LastEvaluatedKey"]
    return items


def slim_conflict(pair):
    """Keep only the fields the UI shows for one conflicting section pair."""
    overlap = pair.get("overlap", {}) or {}
    return {
        "course_a": pair.get("course_a"),
        "crn_a": pair.get("crn_a"),
        "course_b": pair.get("course_b"),
        "crn_b": pair.get("crn_b"),
        "overlap": {
            "days": overlap.get("days", []),
            "time_a": overlap.get("time_a"),
            "time_b": overlap.get("time_b"),
        },
    }


def build_quarter(item):
    """Flatten one conflict item into the per-quarter shape the app renders."""
    return {
        "term_code": item.get("term_code"),
        "courses": item.get("resolved_courses", []),
        "missing_courses": item.get("missing_courses", []),
        "course_count": _num(item.get("course_count", 0)),
        "section_count": _num(item.get("section_count", 0)),
        "conflict_count": _num(item.get("conflict_count", 0)),
        "conflict_percentage": _num(item.get("conflict_percentage", 0)),
        "conflicts": [slim_conflict(c) for c in item.get("conflicts", [])],
    }


def build_export(items):
    """Nest items as { pathway_id: { quarter_key: quarter_summary } }."""
    out = {}
    for item in items:
        out.setdefault(item["pathway_id"], {})[item["quarter_key"]] = build_quarter(item)
    return out


def main():
    parser = argparse.ArgumentParser(
        description="Export pathway conflicts to the web app's bundled JSON")
    parser.add_argument("--out", default=str(DEFAULT_OUT), help="Output JSON path")
    args = parser.parse_args()

    items = scan_conflicts()
    print(f"Scanned {len(items)} pathway-quarter items from {CONFLICTS_TABLE}.")

    export = build_export(items)
    quarters = sum(len(p) for p in export.values())
    total_conflicts = sum(q["conflict_count"] for p in export.values() for q in p.values())
    print(f"{len(export)} pathways, {quarters} quarters, {total_conflicts} conflict pairs.")

    out_path = Path(args.out)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    # Compact separators: this is a bundled build artifact, not meant for reading.
    with open(out_path, "w") as f:
        json.dump(export, f, separators=(",", ":"))
    print(f"Wrote {out_path} ({out_path.stat().st_size / 1024:.0f} KB).")


if __name__ == "__main__":
    main()
