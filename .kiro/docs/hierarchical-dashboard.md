# Hierarchical Conflict Dashboard — Prototype

## What

A standalone HTML dashboard at `data/reports/pathway_conflicts/hierarchical_dashboard.html`
that visualizes scheduling conflict data through a drill-down hierarchy:

```
Overview → Academic Area → Department → Pathway → Quarter → Courses + Conflict Pairs
```

Uses De Anza College brand colors (red `#8c1515`, gold `#c49a1a`) and the same
light-background visual style as the existing React app (`web-app/`). Opens
directly in a browser with no build step or server.

## Why

The existing `dashboard.html` shows flat, tab-based views (by department, by
division, by pair, by term). This prototype explores a different UX: a single
progressive drill-down where each click narrows scope, giving schedulers a
top-to-bottom path from "which part of the college has the most conflicts" down
to "which courses in this pathway quarter are clashing."

## Data Sources

Two files embedded directly into the HTML (no API calls at runtime):

| Source | What it provides | Embedded as |
|--------|-----------------|-------------|
| `web-app/src/data/department_conflicts.json` | Division/department/pair/term aggregates (full, ~20KB) | `const CONFLICT_DATA` |
| `web-app/src/data/deanza_pathways.json` | 29 curated pathways from the top-conflict departments (subset, ~58KB) | `const PATHWAY_DATA` |

To include all 238 pathways, replace the `PATHWAY_DATA` array with the full
`pathways` array from `deanza_pathways.json`. File size grows to ~350KB.

## Hierarchy Mapping

| UI Level | Data field | Source |
|----------|-----------|--------|
| Academic Area | `division_code` + `division_label` | `department_conflicts.json → divisions[]` |
| Department | `subject` (e.g., MATH, COMM) | `department_conflicts.json → departments[]` |
| Pathway | `program_name` + `credential_type` | `deanza_pathways.json → pathways[]` |
| Quarter | `years.year_1.fall` etc. mapped to term_code | Pathway JSON + static term lookup |
| Courses | `required_courses[]` + `additional_courses[]` | Pathway JSON (raw text) |
| Conflict pairs | `subject_a` vs `subject_b` + count | `department_conflicts.json → pairs[]` |

## Key Decisions

- **Academic Area = Division** (the schedule's administrative grouping), not the
  pathway's student-facing "village." Divisions are the correct anchor because
  conflicts are subject-level and each subject belongs to exactly one division.

- **Pathway → Department link is heuristic.** Derived from the `program_name`
  prefix (e.g., "ADMJ:" → ADMJ) or keyword matching ("Chemistry" → CHEM). Not
  perfect for multi-department programs, but correct for ~85% of pathways and
  sufficient for a prototype.

- **Conflict detail is aggregate only.** The local files contain subject-pair
  counts (e.g., "CHEM vs MATH: 993") but not individual section-level conflicts
  (specific CRN, day, time). That detail lives in DynamoDB
  (`deanza-pathway-conflicts` table). The dashboard shows "potential conflict
  pairs" per quarter by cross-referencing detected course subjects against the
  aggregate pair data.

- **Course extraction from raw text is heuristic.** A regex
  (`/\b[A-Z]{2,5}\s+[A-Z]?\d{1,4}[A-Z]{0,3}\b/`) pulls course codes from the
  verbose pathway text. This matches the same patterns as the backend's
  `pathway_parser.py` subject-carry logic, but without the subject allow-list
  filtering, so it can over-match on prose (acceptable for a prototype).

- **De Anza brand theme** (red header, gold accents, light background) matches
  the React app's look so the dashboard feels like part of the same product.
  Card styling, shadows, and font choices mirror `web-app/src/styles.css`.

## Architecture

```
hierarchical_dashboard.html (single file, ~112KB)
├── <style>   — CSS variables, dark theme, cards, bars, breadcrumb
├── <div>     — container with breadcrumb, stats row, content area
└── <script>
    ├── CONFLICT_DATA (embedded JSON — full department_conflicts.json)
    ├── PATHWAY_DATA  (embedded JSON — 29-pathway subset)
    ├── TERMS         (static term_code → label lookup)
    ├── Data transformation (derive primarySubject, build indexes)
    └── Rendering functions per level (overview/area/department/pathway/quarter)
```

Navigation is a stack (`navStack`). Each `navigate({level, ...params})` pushes a
state; `navigateTo(index)` pops back via the breadcrumb.

## Limitations

- **29 of 238 pathways** are embedded. Pathways for subjects not in the subset
  show a "no pathways in embedded subset" message at the Department level.
- **No section-level conflict detail.** "MATH 1A section 01 conflicts with
  CHEM 1A section 03 on MW 9:30–10:20" is not available without a DynamoDB
  export. The quarter view shows aggregate pair counts instead.
- **Heuristic subject derivation** fails for ~15% of pathways whose names don't
  start with a subject code or a recognized keyword. These pathways won't appear
  under any department.
- **No chart library.** Uses CSS bar charts for simplicity and zero dependencies.

## Extending

1. **Full pathway set**: replace `const PATHWAY_DATA = [...]` with the full
   238-item array from `deanza_pathways.json`.
2. **Section-level details**: export the `deanza-pathway-conflicts` table
   (983 items) to a JSON file, embed it, and add a `renderConflictDetails`
   function at a new level below quarter.
3. **Live API**: replace embedded data with `fetch()` calls to an API endpoint
   (would require a backend or Lambda proxy).
