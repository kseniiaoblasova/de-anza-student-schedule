# Report template and output schemas

Every markdown file under `analysis/` uses the section order below. Same headings, same
order, every time — that is what makes terms diffable and lets the dashboard parse them.
Content varies by scope; structure does not.

---

## Standard section order

```markdown
# <Scope> — Schedule Conflict Analysis

**Run:** <timestamp> | **Inputs:** <files> | **Weighting:** weighted | unweighted
**Confidence:** high | medium | low — <one line on what limits it>

## Summary
3-6 sentences. What is broken, how badly, and what would fix the most of it.
No tables here.

## Key findings
Numbered, ordered by impact. Each finding is one paragraph and ends with an evidence tag.

## Conflicts
Table. Ranked by impact score.

## Prerequisites
Entry blockers first, then chain risks, then rare-offering single points of failure.

## Supply and demand
Sections offered, seats, historical fill rate, where supply is the binding constraint
rather than timing.

## Pathway impact
Which pathways are hurt, how many required courses they lose, estimated quarters added.

## Recommendations
Ranked moves, each with conflicts resolved, sections touched, and the owning division.

## Assumptions and limitations
Every assumption that a finding depends on. Missing inputs. Crosswalk rows relied upon.

## Sources
Input files with hashes, catalog year of the maps, rule definitions used.
```

Scope-specific notes:

- **`overview.md`** — aggregate across terms and pathways. Recommendations section holds the
  cross-division moves worth escalating.
- **`terms/<TERM>.md`** — one term. Conflicts and Supply sections are the substance.
- **`pathways/<slug>.md`** — one pathway across its full six-quarter map, plus the
  completion simulation result.
- **`dependencies.md`** — Conflicts section becomes co-requirement clusters; Pathway impact
  becomes which pathways share each cluster.

---

## Table formats

**Conflicts** (verdict `BLOCKED` before `TIGHT`; suppress `CLEAR` except in appendices):

```markdown
| Course A | Course B | Verdict | Compat. pairs | Compat. seats | Pathways | Impact | Evidence |
|---|---|---|---|---|---|---|---|
| ARTS 4A | ARTS 8 | BLOCKED | 0 | 0 | 4 | 3.21 | [E: term=202742 \| rule=R1-BLOCKED \| crns=45228/47181 \| src=SP_202742.xlsx] |
```

**Recommendations**:

```markdown
| # | Move | Resolves | Sections touched | Division | Risk |
|---|---|---|---|---|---|
| 1 | ARTS 8 CRN 47181 → TR 08:30–10:20 | 3 BLOCKED, 2 TIGHT | 1 | 2CA | Room E12 free; no instructor clash |
```

**Pathway impact**:

```markdown
| Pathway | Award | Blocked reqs | Tight reqs | Min deferrals | Quarters to complete | Δ vs plan |
|---|---|---|---|---|---|---|
| Studio Arts | AA-T | 3 | 5 | 2 | 8 | +2 |
```

---

## Writing rules

- **Explain the mechanism, not just the number.** "ARTS 4A and ARTS 8 are both required in
  Year 1 Winter; ARTS 8's only section meets TR 10:30–12:20 and both ARTS 4A sections meet
  inside that window, so a student following the map must defer one" beats "impact 3.21".
- **Quote the map when a requirement is ambiguous.** Use the `raw` field from the pathway
  JSON. Conditional language ("as required", "if not already taken") changes what the finding
  means and must be surfaced, not smoothed over.
- **Separate what the data shows from what it implies.** Findings are data. Recommendations
  are inference and are labeled as such.
- **State every assumption where it is used**, not only in the Assumptions section. A reader
  scanning the Conflicts table should see when a row depends on a crosswalk mapping.
- **No instructor names anywhere.** Sections are identified by CRN.
- **No unsourced comparison to other colleges or prior years** unless that data was loaded.

---

## Output JSON schemas

The markdown is for humans; these files are the interface for the dashboard, the alternative
schedule generator, and any downstream agent. Keep them stable and versioned.

```json
// conflicts.json
{
  "schema_version": "1.0",
  "run_id": "2026-07-22T20:41:00Z",
  "conflicts": [
    {
      "term_code": "202742",
      "course_a": "ARTS 4A",
      "course_b": "ARTS 8",
      "verdict": "BLOCKED",
      "compatible_pairs": [],
      "blocking_pairs": [{ "a_crn": 45228, "b_crn": 47181, "overlap_min": 110, "days": ["T","R"] }],
      "compatible_seats": 0,
      "pathways": ["studio-arts-aat", "painting-aa"],
      "criticality": "major_prep",
      "demand_weight": 0.71,
      "impact": 3.21,
      "rule": "R1-BLOCKED"
    }
  ]
}
```

```json
// pathway_feasibility.json
{
  "schema_version": "1.0",
  "pathways": [
    {
      "pathway_id": "studio-arts-aat",
      "terms": [
        {
          "year": 1, "quarter": "FALL", "term_code": "202612",
          "status": "partial", "required": 4, "satisfiable": 2,
          "min_deferrals": 2,
          "blocked_requirements": ["y1-fa-1", "y1-fa-2"],
          "notes": ["GE requirements not evaluated: ge_areas.json absent"]
        }
      ],
      "simulation": {
        "summer_mode": "off",
        "quarters_to_complete": 8,
        "planned_quarters": 6,
        "delta": 2,
        "critical_path": ["ARTS 4A", "ARTS 4B", "ARTS 37A"]
      }
    }
  ]
}
```

```json
// recommendations.json
{
  "schema_version": "1.0",
  "recommendations": [
    {
      "rank": 1,
      "type": "move_time",
      "term_code": "202742",
      "crn": 47181,
      "course_id": "ARTS 8",
      "from": { "days": ["T","R"], "start": "10:30", "end": "12:20" },
      "to":   { "days": ["T","R"], "start": "08:30", "end": "10:20" },
      "resolves": [{ "pair": ["ARTS 4A","ARTS 8"], "from_verdict": "BLOCKED", "to_verdict": "CLEAR" }],
      "creates": [],
      "sections_touched": 1,
      "division": "2CA",
      "room_check": "pass",
      "instructor_check": "pass",
      "score": 3.0
    }
  ]
}
```

`unresolved.json` holds every course code that failed to resolve, every meeting row that
failed to parse, and every pathway requirement that could not be evaluated — each with the
source file and line or page. This file is the honest accounting of what the analysis does
not know, and reports must reference its counts in their Confidence line.

`run_manifest.json` holds input filenames with SHA-256 hashes, parameter values, the
term-code mapping, the `SectionStat` codebook actually used, weight values, and the
timestamp. Two runs without manifests cannot be compared.
