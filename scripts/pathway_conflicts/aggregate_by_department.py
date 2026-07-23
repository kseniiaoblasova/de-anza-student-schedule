"""
Aggregate pathway conflicts by department (subject code).

Scans the deanza-pathway-conflicts table and counts how many conflict pairs
each department is involved in. A conflict pair like "MATH 1A vs ENGL 1A"
credits one conflict to both MATH and ENGL — each department sees its share of
scheduling collisions.

Also builds a subject-to-division mapping from the schedule CSV so the output
can group subjects under their administrative division (e.g. "2PS" covers MATH,
PHYS, STAT, etc.).

Usage:
    python scripts/pathway_conflicts/aggregate_by_department.py
    python scripts/pathway_conflicts/aggregate_by_department.py --term 202622
    python scripts/pathway_conflicts/aggregate_by_department.py --csv-report
"""

import sys
import csv
import argparse
from pathlib import Path
from collections import defaultdict

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from common import get_table, get_session, PROJECT_ROOT  # noqa: E402

CONFLICTS_TABLE = "deanza-pathway-conflicts"
SCHEDULE_DIR = PROJECT_ROOT / "data" / "2025-26-class-schedule"


# --- Division mapping from CSV ---

def build_subject_division_map():
    """Read all schedule CSVs and return {subject: division} from the source data."""
    mapping = {}
    for csv_path in SCHEDULE_DIR.glob("*.csv"):
        with open(csv_path, encoding="utf-8") as f:
            for row in csv.DictReader(f):
                subj = row.get("Subject", "").strip()
                div = row.get("Division", "").strip()
                if subj and div:
                    mapping[subj] = div
    return mapping


# --- Friendly division labels ---

DIVISION_LABELS = {
    "2AT": "Applied Technologies",
    "2BH": "Biological & Health Sciences",
    "2CA": "Creative Arts",
    "2CB": "Business & CIS",
    "2DI": "Distance Learning",
    "2DS": "Disability Support / Student Services",
    "2IC": "Intercultural Studies / World Languages",
    "2LA": "Language Arts",
    "2LR": "Library",
    "2PE": "Physical Education & Athletics",
    "2PS": "Physical Sciences, Math & Engineering",
    "2SS": "Social Sciences & Humanities",
    "2ST": "Student Success",
}


# --- Core aggregation ---

def extract_subject(course_code):
    """Pull the subject prefix from a canonical code like 'MATH 1A'."""
    parts = course_code.split()
    return parts[0] if parts else None


def scan_all_conflicts(session, term_filter=None):
    """Scan the pathway-conflicts table, optionally filtered to one term."""
    table = get_table(CONFLICTS_TABLE, session)
    items, kwargs = [], {}
    while True:
        resp = table.scan(**kwargs)
        items.extend(resp.get("Items", []))
        if "LastEvaluatedKey" not in resp:
            break
        kwargs["ExclusiveStartKey"] = resp["LastEvaluatedKey"]

    if term_filter:
        items = [i for i in items if i.get("term_code") == term_filter]
    return items


def aggregate_conflicts(items):
    """Count conflict involvement per subject and per subject-pair.

    Returns:
        by_subject: {subject: {"conflict_appearances": int, "unique_pathways": set}}
        by_pair: {(subj_a, subj_b): int}  — alphabetically ordered pairs
    """
    by_subject = defaultdict(lambda: {"conflict_appearances": 0, "pathways": set()})
    by_pair = defaultdict(int)

    for item in items:
        pathway_id = item.get("pathway_id", "")
        for conflict in item.get("conflicts", []):
            subj_a = extract_subject(conflict.get("course_a", ""))
            subj_b = extract_subject(conflict.get("course_b", ""))
            if not subj_a or not subj_b:
                continue

            # Credit both departments for being in a conflict
            by_subject[subj_a]["conflict_appearances"] += 1
            by_subject[subj_a]["pathways"].add(pathway_id)
            by_subject[subj_b]["conflict_appearances"] += 1
            by_subject[subj_b]["pathways"].add(pathway_id)

            # Track the inter-department pair
            pair = tuple(sorted([subj_a, subj_b]))
            by_pair[pair] += 1

    return by_subject, by_pair


# --- Output ---

def print_report(by_subject, by_pair, subject_to_division):
    """Print a formatted console report."""

    # Group subjects by division for a structured view
    division_groups = defaultdict(list)
    for subj, stats in by_subject.items():
        div = subject_to_division.get(subj, "???")
        division_groups[div].append((subj, stats))

    # Sort divisions by total conflicts descending
    div_totals = {
        div: sum(s["conflict_appearances"] for _, s in subjects)
        for div, subjects in division_groups.items()
    }

    print("=" * 72)
    print(f"{'AGGREGATE CONFLICTS BY DEPARTMENT':^72}")
    print("=" * 72)
    print(f"\n{'Subject':<10} {'Conflicts':<12} {'Pathways':<10} {'Division'}")
    print(f"{'─' * 10} {'─' * 12} {'─' * 10} {'─' * 30}")

    # Flat view sorted by conflict count
    ranked = sorted(by_subject.items(),
                    key=lambda x: x[1]["conflict_appearances"], reverse=True)
    for subj, stats in ranked:
        div = subject_to_division.get(subj, "???")
        label = DIVISION_LABELS.get(div, div)
        print(f"{subj:<10} {stats['conflict_appearances']:<12} "
              f"{len(stats['pathways']):<10} {label}")

    # Division-level totals
    print(f"\n{'─' * 72}")
    print(f"\n{'DIVISION TOTALS':^72}\n")
    print(f"{'Division':<8} {'Label':<40} {'Conflicts':<12} {'Subjects'}")
    print(f"{'─' * 8} {'─' * 40} {'─' * 12} {'─' * 8}")
    for div, total in sorted(div_totals.items(), key=lambda x: x[1], reverse=True):
        label = DIVISION_LABELS.get(div, div)
        n_subj = len(division_groups[div])
        print(f"{div:<8} {label:<40} {total:<12} {n_subj}")

    # Top inter-department pairs
    print(f"\n{'─' * 72}")
    print(f"\n{'TOP 20 CROSS-DEPARTMENT CONFLICT PAIRS':^72}\n")
    print(f"{'Pair':<20} {'Conflicts'}")
    print(f"{'─' * 20} {'─' * 10}")
    top_pairs = sorted(by_pair.items(), key=lambda x: x[1], reverse=True)[:20]
    for (a, b), count in top_pairs:
        print(f"{a + ' vs ' + b:<20} {count}")


def write_csv_report(by_subject, by_pair, subject_to_division, output_dir):
    """Write CSV files for further analysis or dashboarding."""
    output_dir.mkdir(parents=True, exist_ok=True)

    # Per-subject report
    subj_path = output_dir / "conflicts_by_subject.csv"
    with open(subj_path, "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["subject", "division", "division_label",
                    "conflict_appearances", "pathway_count"])
        for subj, stats in sorted(by_subject.items(),
                                   key=lambda x: x[1]["conflict_appearances"],
                                   reverse=True):
            div = subject_to_division.get(subj, "")
            label = DIVISION_LABELS.get(div, div)
            w.writerow([subj, div, label,
                        stats["conflict_appearances"], len(stats["pathways"])])
    print(f"\nWrote: {subj_path}")

    # Per-pair report
    pair_path = output_dir / "conflicts_by_pair.csv"
    with open(pair_path, "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["subject_a", "subject_b", "conflict_count"])
        for (a, b), count in sorted(by_pair.items(),
                                     key=lambda x: x[1], reverse=True):
            w.writerow([a, b, count])
    print(f"Wrote: {pair_path}")


def build_json_payload(by_subject, by_pair, subject_to_division, items):
    """Build a structured JSON object ready for the React web app.

    Shapes the aggregation into three visualization-friendly datasets:
      - departments: per-subject stats (for bar charts / ranked tables)
      - divisions: rolled-up division stats (for pie/donut charts)
      - pairs: top cross-department pairs (for chord diagrams / heatmaps)
      - terms: per-term breakdown (for time-series or term comparison)
    """
    import json
    from decimal import Decimal

    # Per-subject list sorted by conflicts descending
    departments = []
    for subj, stats in sorted(by_subject.items(),
                               key=lambda x: x[1]["conflict_appearances"],
                               reverse=True):
        div = subject_to_division.get(subj, "")
        departments.append({
            "subject": subj,
            "division_code": div,
            "division_label": DIVISION_LABELS.get(div, div),
            "conflict_appearances": stats["conflict_appearances"],
            "pathway_count": len(stats["pathways"]),
        })

    # Division-level aggregation
    div_agg = defaultdict(lambda: {"conflict_appearances": 0, "subjects": []})
    for dept in departments:
        div = dept["division_code"]
        div_agg[div]["conflict_appearances"] += dept["conflict_appearances"]
        div_agg[div]["subjects"].append(dept["subject"])

    divisions = []
    for div, data in sorted(div_agg.items(),
                             key=lambda x: x[1]["conflict_appearances"],
                             reverse=True):
        divisions.append({
            "division_code": div,
            "division_label": DIVISION_LABELS.get(div, div),
            "conflict_appearances": data["conflict_appearances"],
            "subject_count": len(data["subjects"]),
            "subjects": data["subjects"],
        })

    # Top pairs (limit to 50 for reasonable payload)
    pairs = []
    for (a, b), count in sorted(by_pair.items(), key=lambda x: x[1], reverse=True)[:50]:
        pairs.append({
            "subject_a": a,
            "subject_b": b,
            "conflict_count": count,
            "is_intra_department": a == b,
        })

    # Per-term breakdown for term comparison view
    term_subjects = defaultdict(lambda: defaultdict(int))
    for item in items:
        term = item.get("term_code", "")
        for conflict in item.get("conflicts", []):
            subj_a = extract_subject(conflict.get("course_a", ""))
            subj_b = extract_subject(conflict.get("course_b", ""))
            if subj_a:
                term_subjects[term][subj_a] += 1
            if subj_b:
                term_subjects[term][subj_b] += 1

    terms = []
    for term in sorted(term_subjects.keys()):
        top_subjects = sorted(term_subjects[term].items(),
                              key=lambda x: x[1], reverse=True)[:15]
        terms.append({
            "term_code": term,
            "total_conflicts": sum(term_subjects[term].values()) // 2,
            "top_subjects": [{"subject": s, "count": c} for s, c in top_subjects],
        })

    return {
        "generated_at": __import__("datetime").datetime.utcnow().isoformat() + "Z",
        "total_conflict_pairs": sum(int(i.get("conflict_count", 0)) for i in items),
        "pathway_quarters_analyzed": len(items),
        "departments": departments,
        "divisions": divisions,
        "pairs": pairs,
        "terms": terms,
    }


def write_json_report(payload, output_path):
    """Write the JSON payload for the web app."""
    import json
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(payload, f, indent=2)
    print(f"Wrote: {output_path}")


def main():
    parser = argparse.ArgumentParser(
        description="Aggregate pathway conflicts by department/subject")
    parser.add_argument("--term", default=None,
                        help="Filter to one term_code (e.g. 202622 for FA 2025)")
    parser.add_argument("--csv-report", action="store_true",
                        help="Write CSV report files to data/reports/pathway_conflicts/")
    parser.add_argument("--json", action="store_true",
                        help="Write a JSON file to web-app/src/data/ for the frontend")
    args = parser.parse_args()

    session = get_session()

    # Load division mapping from schedule CSVs
    subject_to_division = build_subject_division_map()

    # Scan conflicts from DynamoDB
    print(f"Scanning {CONFLICTS_TABLE}...")
    items = scan_all_conflicts(session, term_filter=args.term)
    print(f"  {len(items)} pathway-quarter items loaded"
          f"{f' (term={args.term})' if args.term else ' (all terms)'}.")

    total_conflicts = sum(int(i.get("conflict_count", 0)) for i in items)
    print(f"  {total_conflicts} total conflict pairs across all items.\n")

    if not total_conflicts:
        print("No conflicts found — nothing to aggregate.")
        return

    # Aggregate
    by_subject, by_pair = aggregate_conflicts(items)

    # Output
    print_report(by_subject, by_pair, subject_to_division)

    if args.csv_report:
        output_dir = PROJECT_ROOT / "data" / "reports" / "pathway_conflicts"
        write_csv_report(by_subject, by_pair, subject_to_division, output_dir)

    if args.json:
        payload = build_json_payload(by_subject, by_pair, subject_to_division, items)
        json_path = PROJECT_ROOT / "web-app" / "src" / "data" / "department_conflicts.json"
        write_json_report(payload, json_path)


if __name__ == "__main__":
    main()
