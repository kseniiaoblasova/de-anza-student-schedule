"""
Analyze pathway conflicts from DynamoDB and produce a comprehensive report.

Queries deanza-pathway-conflicts, computes per-pathway, per-village (group),
per-term, and per-course-pair analytics, then writes a JSON report and prints
a human-readable summary.

Usage:
    python scripts/pathway_conflicts/analyze_conflicts.py
    python scripts/pathway_conflicts/analyze_conflicts.py --output analysis_report.json
"""

import sys
import json
import argparse
from pathlib import Path
from collections import defaultdict
from decimal import Decimal

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from common import get_table  # noqa: E402


class DecimalEncoder(json.JSONEncoder):
    def default(self, o):
        if isinstance(o, Decimal):
            return float(o)
        if isinstance(o, set):
            return list(o)
        return super().default(o)


def scan_all_conflicts():
    """Scan the entire pathway-conflicts table."""
    table = get_table("deanza-pathway-conflicts")
    items, kwargs = [], {}
    while True:
        resp = table.scan(**kwargs)
        items.extend(resp.get("Items", []))
        if "LastEvaluatedKey" not in resp:
            break
        kwargs["ExclusiveStartKey"] = resp["LastEvaluatedKey"]
    return items


def analyze(items):
    """Run all analyses on the conflict items."""
    results = {}

    # --- Overall summary ---
    total_quarters = len(items)
    quarters_with_conflicts = [i for i in items if int(i.get("conflict_count", 0)) > 0]
    total_conflict_pairs = sum(int(i.get("conflict_count", 0)) for i in items)
    total_pairs_evaluated = sum(int(i.get("pairs_evaluated", 0)) for i in items)
    overall_pct = (total_conflict_pairs / total_pairs_evaluated * 100) if total_pairs_evaluated else 0

    results["overall"] = {
        "total_pathways": len(set(i["pathway_id"] for i in items)),
        "total_pathway_quarters": total_quarters,
        "quarters_with_conflicts": len(quarters_with_conflicts),
        "quarters_without_conflicts": total_quarters - len(quarters_with_conflicts),
        "total_conflict_pairs": total_conflict_pairs,
        "total_pairs_evaluated": total_pairs_evaluated,
        "overall_conflict_percentage": round(overall_pct, 2),
    }

    # --- Per-pathway analysis ---
    by_pathway = defaultdict(list)
    for item in items:
        by_pathway[item["pathway_id"]].append(item)

    pathway_summaries = []
    for pid, quarters in by_pathway.items():
        total_c = sum(int(q.get("conflict_count", 0)) for q in quarters)
        total_p = sum(int(q.get("pairs_evaluated", 0)) for q in quarters)
        pct = (total_c / total_p * 100) if total_p else 0
        worst_q = max(quarters, key=lambda q: float(q.get("conflict_percentage", 0)))
        pathway_summaries.append({
            "pathway_id": pid,
            "program_name": quarters[0].get("program_name", ""),
            "village": quarters[0].get("village", ""),
            "credential_type": quarters[0].get("credential_type", ""),
            "quarters_analyzed": len(quarters),
            "total_conflicts": total_c,
            "total_pairs_evaluated": total_p,
            "conflict_percentage": round(pct, 2),
            "worst_quarter": worst_q["quarter_key"],
            "worst_quarter_pct": float(worst_q.get("conflict_percentage", 0)),
        })

    pathway_summaries.sort(key=lambda x: x["conflict_percentage"], reverse=True)
    results["per_pathway"] = pathway_summaries

    # --- Per-village (group) analysis ---
    by_village = defaultdict(list)
    for item in items:
        by_village[item.get("village", "Unknown")].append(item)

    village_summaries = []
    for village, v_items in by_village.items():
        total_c = sum(int(q.get("conflict_count", 0)) for q in v_items)
        total_p = sum(int(q.get("pairs_evaluated", 0)) for q in v_items)
        pct = (total_c / total_p * 100) if total_p else 0
        n_pathways = len(set(i["pathway_id"] for i in v_items))
        village_summaries.append({
            "village": village,
            "pathways_count": n_pathways,
            "quarters_analyzed": len(v_items),
            "total_conflicts": total_c,
            "total_pairs_evaluated": total_p,
            "conflict_percentage": round(pct, 2),
            "quarters_with_conflicts": sum(1 for i in v_items if int(i.get("conflict_count", 0)) > 0),
        })

    village_summaries.sort(key=lambda x: x["conflict_percentage"], reverse=True)
    results["per_village"] = village_summaries

    # --- Per-term analysis ---
    by_term = defaultdict(list)
    for item in items:
        by_term[item.get("term_code", "")].append(item)

    term_summaries = []
    for term, t_items in by_term.items():
        total_c = sum(int(q.get("conflict_count", 0)) for q in t_items)
        total_p = sum(int(q.get("pairs_evaluated", 0)) for q in t_items)
        pct = (total_c / total_p * 100) if total_p else 0
        term_summaries.append({
            "term_code": term,
            "pathways_in_term": len(t_items),
            "total_conflicts": total_c,
            "total_pairs_evaluated": total_p,
            "conflict_percentage": round(pct, 2),
        })

    term_summaries.sort(key=lambda x: x["term_code"])
    results["per_term"] = term_summaries

    # --- Top conflicting course pairs ---
    pair_stats = defaultdict(lambda: {"pathways": set(), "occurrences": 0, "quarters": set()})
    for item in items:
        for conflict in item.get("conflicts", []):
            key = (conflict["course_a"], conflict["course_b"])
            pair_stats[key]["pathways"].add(item["pathway_id"])
            pair_stats[key]["occurrences"] += 1
            pair_stats[key]["quarters"].add(item["quarter_key"])

    top_pairs = []
    for (ca, cb), stats in pair_stats.items():
        top_pairs.append({
            "course_a": ca,
            "course_b": cb,
            "pathways_affected": len(stats["pathways"]),
            "total_occurrences": stats["occurrences"],
            "quarters_affected": len(stats["quarters"]),
        })

    top_pairs.sort(key=lambda x: x["pathways_affected"], reverse=True)
    results["top_conflict_pairs"] = top_pairs[:50]

    # --- Per-credential-type analysis ---
    by_cred = defaultdict(list)
    for item in items:
        by_cred[item.get("credential_type", "Unknown")].append(item)

    cred_summaries = []
    for cred, c_items in by_cred.items():
        total_c = sum(int(q.get("conflict_count", 0)) for q in c_items)
        total_p = sum(int(q.get("pairs_evaluated", 0)) for q in c_items)
        pct = (total_c / total_p * 100) if total_p else 0
        cred_summaries.append({
            "credential_type": cred,
            "pathways_count": len(set(i["pathway_id"] for i in c_items)),
            "total_conflicts": total_c,
            "total_pairs_evaluated": total_p,
            "conflict_percentage": round(pct, 2),
        })

    cred_summaries.sort(key=lambda x: x["conflict_percentage"], reverse=True)
    results["per_credential_type"] = cred_summaries

    # --- Most missing courses (not offered) ---
    missing_counts = defaultdict(int)
    for item in items:
        for course in item.get("missing_courses", []):
            missing_counts[course] += 1

    results["most_missing_courses"] = sorted(
        [{"course": c, "quarters_missing": n} for c, n in missing_counts.items()],
        key=lambda x: x["quarters_missing"], reverse=True
    )[:30]

    return results


def print_report(results):
    """Print a human-readable summary."""
    o = results["overall"]
    print("=" * 70)
    print("  DE ANZA PATHWAY SCHEDULE CONFLICT ANALYSIS")
    print("=" * 70)
    print(f"\n  Pathways analyzed:          {o['total_pathways']}")
    print(f"  Pathway-quarters analyzed:  {o['total_pathway_quarters']}")
    print(f"  Quarters WITH conflicts:    {o['quarters_with_conflicts']} ({o['quarters_with_conflicts']/o['total_pathway_quarters']*100:.1f}%)")
    print(f"  Total section pairs eval'd: {o['total_pairs_evaluated']:,}")
    print(f"  Total conflict pairs:       {o['total_conflict_pairs']:,}")
    print(f"  Overall conflict rate:      {o['overall_conflict_percentage']:.2f}%")

    print(f"\n{'─' * 70}")
    print("  TOP 15 MOST-CONFLICTED PATHWAYS")
    print(f"{'─' * 70}")
    for p in results["per_pathway"][:15]:
        print(f"  {p['conflict_percentage']:5.1f}%  {p['program_name'][:55]}")
        print(f"         ({p['village']}, worst quarter: {p['worst_quarter']} at {p['worst_quarter_pct']:.1f}%)")

    print(f"\n{'─' * 70}")
    print("  CONFLICTS BY VILLAGE (DEPARTMENT GROUP)")
    print(f"{'─' * 70}")
    for v in results["per_village"]:
        print(f"  {v['conflict_percentage']:5.1f}%  {v['village']}")
        print(f"         ({v['pathways_count']} pathways, {v['total_conflicts']:,} conflict pairs)")

    print(f"\n{'─' * 70}")
    print("  CONFLICTS BY TERM")
    print(f"{'─' * 70}")
    for t in results["per_term"]:
        print(f"  {t['term_code']}  {t['conflict_percentage']:5.1f}%  "
              f"({t['pathways_in_term']} pathways, {t['total_conflicts']:,} conflicts)")

    print(f"\n{'─' * 70}")
    print("  TOP 20 CONFLICTING COURSE PAIRS (by pathways affected)")
    print(f"{'─' * 70}")
    for p in results["top_conflict_pairs"][:20]:
        print(f"  {p['pathways_affected']:3d} pathways  {p['course_a']} × {p['course_b']}"
              f"  ({p['total_occurrences']} section-pair conflicts)")

    print(f"\n{'─' * 70}")
    print("  CONFLICTS BY CREDENTIAL TYPE")
    print(f"{'─' * 70}")
    for c in results["per_credential_type"]:
        print(f"  {c['conflict_percentage']:5.1f}%  {c['credential_type']}")
        print(f"         ({c['pathways_count']} pathways, {c['total_conflicts']:,} conflicts)")

    print(f"\n{'─' * 70}")
    print("  TOP 15 MOST FREQUENTLY MISSING COURSES")
    print(f"{'─' * 70}")
    for m in results["most_missing_courses"][:15]:
        print(f"  {m['quarters_missing']:3d} quarters  {m['course']}")


def main():
    parser = argparse.ArgumentParser(description="Analyze pathway conflicts")
    parser.add_argument("--output", type=str, default=None, help="Write JSON report to file")
    args = parser.parse_args()

    print("Scanning deanza-pathway-conflicts table...")
    items = scan_all_conflicts()
    print(f"  Retrieved {len(items)} items.\n")

    results = analyze(items)
    print_report(results)

    if args.output:
        Path(args.output).write_text(json.dumps(results, indent=2, cls=DecimalEncoder))
        print(f"\nFull report written to: {args.output}")


if __name__ == "__main__":
    main()
