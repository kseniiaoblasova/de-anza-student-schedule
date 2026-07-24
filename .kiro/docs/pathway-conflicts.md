# Pathway Conflicts — per-quarter conflict table

## What

Populates `deanza-pathway-conflicts`: one item per pathway per quarter holding
the time conflicts among that quarter's course sections. Built by walking every
pathway in `deanza-pathways-normalized`, resolving each quarter's courses to all
their schedule sections, and sending them to the deployed conflict Lambda. This
is the dataset the React app displays and the basis for further analysis.

## Why

Ties the three pieces together: normalized pathway courses + the schedule +
the conflict engine. Precomputing and storing per-quarter results means the UI
(and any analysis) reads ready-made conflict data instead of recomputing.

## How it works

```
deanza-pathways-normalized ─┐
                            │  for each pathway quarter:
                            ├─ courses ─► resolve to ALL sections in the term
deanza-class-schedule ──────┘                     │
                                                  ▼
                                    POST section list ─► conflict Lambda
                                                  │
                                                  ▼
                              store report ─► deanza-pathway-conflicts
```

Per quarter: map `(year, quarter)` → `term_code`, collect **every section** of
every course (multiple sections of the same course are all included — the engine
skips same-course pairs), call the Lambda once, store the result.

Files (`scripts/pathway_conflicts/`):
- `resolve.py` — pure: term mapping, section indexing by canonical course,
  payload assembly, item building.
- `conflict_client.py` — calls the Lambda (direct boto3 invoke by default; HTTP
  via API key optional).
- `build_conflicts.py` — orchestrator (dry-run by default; `--apply` writes).

## Term mapping (a key decision)

Pathway quarters map to real published terms; the schedule holds two academic
years, so both pathway years use a real schedule (no proxy):

| pathway year/quarter | term_code | term          |
|----------------------|-----------|---------------|
| year_1 fall/win/spr  | 202622 / 202632 / 202642 | AY2025-26 (matches catalog year) |
| year_2 fall/win/spr  | 202722 / 202732 / 202742 | AY2026-27 |

Override `YEAR_QUARTER_TO_TERM` in `resolve.py` to analyze a different alignment.
Summer terms are ignored (pathways only list fall/winter/spring).

## Table: `deanza-pathway-conflicts`

- **Key:** partition `pathway_id`, sort `quarter_key` = `"{year}#{quarter}"`
  (e.g. `year_1#fall`). "All quarters of a pathway" is one query — the per-pathway
  React view.
- **GSI `term-index`:** partition `term_code`, sort `pathway_id` — "all pathways
  in a quarter" for the cross-pathway view.
- **Attributes:** `program_name`, `village`, `credential_type`, `year`,
  `quarter`, `term_code`, `resolved_courses`, `missing_courses`, `course_count`,
  `section_count`, `pairs_evaluated`, `conflict_count`, `conflict_percentage`
  (Decimal), `conflicts` (list of `{course_a, crn_a, course_b, crn_b, overlap,
  meta_a, meta_b}` from the Lambda).

`conflict_percentage` = `conflict_count / pairs_evaluated * 100` (cross-course
section pairs), computed here for convenience; 0 when there are no pairs.

## Commands

```bash
# Dry run (calls the Lambda, writes nothing); --limit N for a quick subset
python scripts/pathway_conflicts/build_conflicts.py --limit 5

# Create + populate the table (idempotent: overwrites by pathway_id+quarter_key)
python scripts/pathway_conflicts/build_conflicts.py --apply --create-table

# Use the public HTTP endpoint instead of direct invoke
CONFLICTS_API_URL=... CONFLICTS_API_KEY=... \
  python scripts/pathway_conflicts/build_conflicts.py --mode http --apply
```

## Web export

`export_web_data.py` dumps this table to the JSON the React app bundles
(`web-app/src/data/pathway_conflicts.json`): a scan, trimmed to the fields the UI
renders (Decimals → numbers), nested as `pathway_id → quarter_key → summary`.
Course codes are already canonical here, so no reshaping is needed. Rerun it
after any `--apply` rebuild. See `.kiro/docs/web-app.md` for the frontend join.

```bash
python scripts/pathway_conflicts/export_web_data.py
```

## Current load (workshop account, us-west-2)

- 238 pathways → **983 pathway-quarter items** (quarters with courses).
- 442 quarters have at least one conflict; 10,173 total conflict pairs.
- Quarters with no courses are skipped; quarters with fewer than two resolvable
  courses are stored with zero conflicts (no Lambda call needed).

## Aggregate by department

`aggregate_by_department.py` reads the stored conflict pairs and counts how
often each subject (department) appears in a conflict. Each pair credits both
sides — "MATH 1A vs CHEM 1A" counts once for MATH and once for CHEM.

Outputs three views:
1. **Per-subject ranking** — subjects sorted by total conflict appearances,
   with the number of distinct pathways affected and the division label.
2. **Division totals** — administrative divisions (from the schedule CSV
   `Division` column) summed, showing which parts of the college generate
   the most scheduling pressure.
3. **Top cross-department pairs** — which two subjects most often collide
   (includes intra-department pairs like "COMM vs COMM" meaning two different
   COMM courses at the same time).

```bash
# All terms
python scripts/pathway_conflicts/aggregate_by_department.py

# One term only (Fall 2025)
python scripts/pathway_conflicts/aggregate_by_department.py --term 202622

# Write CSV files to data/reports/pathway_conflicts/
python scripts/pathway_conflicts/aggregate_by_department.py --csv-report

# Write JSON for the React web app to web-app/src/data/department_conflicts.json
python scripts/pathway_conflicts/aggregate_by_department.py --json
```

Division mapping is built from the `Division` column in the schedule CSVs at
`data/2025-26-class-schedule/`. If a subject isn't in those files it shows as
`???`.

### JSON output for the web app (`--json`)

Writes `web-app/src/data/department_conflicts.json` — a single file the React
app imports directly. Structure:

```json
{
  "generated_at": "...",
  "total_conflict_pairs": 10173,
  "pathway_quarters_analyzed": 983,
  "departments": [
    { "subject": "COMM", "division_code": "2LA", "division_label": "Language Arts",
      "conflict_appearances": 7912, "pathway_count": 111 }
  ],
  "divisions": [
    { "division_code": "2LA", "division_label": "Language Arts",
      "conflict_appearances": 8383, "subject_count": 5, "subjects": [...] }
  ],
  "pairs": [
    { "subject_a": "CHEM", "subject_b": "MATH", "conflict_count": 993,
      "is_intra_department": false }
  ],
  "terms": [
    { "term_code": "202622", "total_conflicts": 2124,
      "top_subjects": [{ "subject": "MATH", "count": 1223 }, ...] }
  ]
}
```

Visualization approaches the frontend can use:
- `departments` → horizontal bar chart ranked by conflict count, colored by division.
- `divisions` → pie/donut chart of scheduling pressure by college division.
- `pairs` → chord diagram or heatmap showing which subjects clash most.
- `terms` → grouped bar chart comparing conflict hotspots across quarters.

## Limitations & gotchas

- **Section-level pairs.** `pairs_evaluated`/`conflict_count` are counted over
  cross-course *section* pairs (every section of course A vs every section of
  B). A course with many sections inflates the pair count; the percentage is
  relative to that. This matches the whiteboard model but is not "can the
  student build one clash-free schedule" (that's a future feasibility metric).
- **`missing_courses`.** Courses with no section in the term (not offered, or a
  pairing gap like statewide `C1000` codes the schedule doesn't use) are recorded
  and excluded from the analysis — surface them, don't treat them as clash-free.
- **Aliases counted separately.** `ENGL C1000` and its `EWRT 1A` twin are distinct
  courses; one usually resolves and the other lands in `missing_courses`.
- **Online-scheduled classes can conflict.** Only `TBA`/async sections are
  exempt; synchronous-online sections have real meeting times and do collide.
- **Idempotent.** Re-running overwrites by `pathway_id + quarter_key`, so it's
  safe to re-run after schedule or normalization updates.
- Depends on `course_pairing.normalization` (course-code bridging) and the
  deployed `deanza-schedule-conflicts` Lambda.
