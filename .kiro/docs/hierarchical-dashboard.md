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
| `data/2025-26-class-schedule/FA 2025.csv` | 594 section-meeting rows for 12 top-conflict subjects, Fall 2025 (~83KB) | `const SCHEDULE_DATA` |

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
hierarchical_dashboard.html (single file, ~216KB)
├── <style> ×5  — CSS variables, De Anza brand theme, cards, bars, breadcrumb,
│                 weekly calendar grid, scheduler controls
├── <div>       — header, breadcrumb, stats row, content area
├── <script #1> — CONFLICT_DATA, PATHWAY_DATA, TERMS, hierarchy logic,
│                 rendering functions (overview/area/department/pathway/quarter)
└── <script #2> — SCHEDULE_DATA (594 section rows), scheduler comparison logic,
                   weekly calendar renderer, dropdown handlers
```

Navigation is a stack (`navStack`). Each `navigate({level, ...params})` pushes a
state; `navigateTo(index)` pops back via the breadcrumb. The scheduler view
monkey-patches `render()` and `renderOverview()` to add its entry point and
handle the `'scheduler'` nav level without modifying the original rendering code.

## Limitations

- **29 of 238 pathways** are embedded. Pathways for subjects not in the subset
  show a "no pathways in embedded subset" message at the Department level.
- **No section-level conflict detail** in the hierarchy view. "MATH 1A section
  01 conflicts with CHEM 1A section 03 on MW 9:30–10:20" is not available
  without a DynamoDB export. The quarter view shows aggregate pair counts. (The
  scheduler comparison view *does* show section-level overlaps using the
  embedded CSV data.)
- **Scheduler view covers 12 subjects only** (MATH, COMM, CHEM, BIOL, PHYS,
  CIS, ECON, PSYC, ACCT, ESL, ENGL, PHIL) for Fall 2025. Other departments
  and terms are not in `SCHEDULE_DATA`.
- **Heuristic subject derivation** fails for ~15% of pathways whose names don't
  start with a subject code or a recognized keyword. These pathways won't appear
  under any department.
- **No chart library.** Uses CSS bar charts and a CSS grid calendar for
  simplicity and zero dependencies.

## Scheduler Comparison View

A scheduler-focused feature accessed from the Overview via a launcher card.
Designed for department schedulers who want to visually understand how another
department's sections are positioned around their own course.

### Workflow

```
Select anchor department → course → section
Select comparison department → course
→ Weekly calendar shows both side by side with overlap detection
```

### UI Components

1. **Anchor selector** — 3 cascading dropdowns (department → course → section).
   Defaults to MATH. Changing department resets course and section.
2. **Comparison selector** — 2 dropdowns (department → course). Shows all
   sections of the selected course on the calendar.
3. **Weekly calendar** — CSS grid, Monday–Friday columns, 7 AM–10 PM time axis
   (40px per hour). Section blocks are absolutely positioned by their parsed
   meeting time.
4. **Block styling**:
   - Red (anchor) — the scheduler's own section
   - Blue (compare) — comparison sections with no time overlap
   - Red/warning (overlap) — comparison sections that share a day AND overlap
     in time with the anchor
5. **Section summary table** — all sections of the comparison course with
   day/time/instructor/room and an overlap indicator.

### Data

Uses `SCHEDULE_DATA` (594 rows from `FA 2025.csv`, subjects with non-TBA
meeting times). Fields per row:
- `s` (subject), `n` (number), `sec` (section), `crn`, `d` (meeting days),
  `t` (meeting times), `im` (instruction method), `ins` (instructor),
  `rm` (room), `div` (division code)

Course numbers are normalized with the same `D`-prefix / zero-stripping logic
as the backend (`normNum()`), so canonical codes like "MATH 1A" match across
the system.

### Per-Section Analysis

The view does NOT label a course as "conflicting" based on one section. Instead,
`analyzeCompareSections()` evaluates each section individually and classifies the
course as a whole:

| Constraint Level | Meaning |
|---|---|
| `clear` | No sections overlap — full scheduling flexibility |
| `partial` | Some sections overlap, but alternatives exist |
| `limited` | Only 1 non-overlapping section available — tight constraint |
| `blocked` | All sections overlap — students cannot take both courses |

This helps the scheduler distinguish between "one bad section" (not a real
problem — students pick another) and "every option conflicts" (a real barrier).

### Key Design Decisions

- **Anchor stays fixed** while the comparison department/course changes. The
  scheduler's own section is the constant frame of reference.
- **All sections shown, not just conflicts.** The purpose is spatial awareness,
  not just flagging overlaps. A scheduler needs to see where open slots exist.
- **Overlap detection is day + time** (strict: `start_a < end_b && start_b <
  end_a` on a shared day). Same rule as the conflict engine. Multi-meeting
  sections (lecture + lab) are checked across all their meeting rows.
- **Constraint-level indicator** gives an at-a-glance answer: "is this a real
  scheduling concern?" without requiring the scheduler to count.
- **Dropdowns update in place** without leaving the view — no page navigation
  needed to switch comparison courses.
- **Monkey-patching** keeps the scheduler code separate from the hierarchy code.
  The second `<script>` overrides `renderOverview` and `render` without editing
  the first script block, so both features can evolve independently.

## Extending

1. **Full pathway set**: replace `const PATHWAY_DATA = [...]` with the full
   238-item array from `deanza_pathways.json`.
2. **Section-level details in the hierarchy**: export the
   `deanza-pathway-conflicts` table (983 items) to a JSON file, embed it, and
   add a `renderConflictDetails` function at a new level below quarter.
3. **All terms in the scheduler**: load additional CSV files (WI 2026, SP 2026,
   etc.) into `SCHEDULE_DATA` and add a term selector dropdown. Currently only
   Fall 2025 is embedded.
4. **All subjects in the scheduler**: remove the 12-subject filter when building
   `SCHEDULE_DATA` to cover the full catalog (~2,000 rows for one term).
5. **Live API**: replace embedded data with `fetch()` calls to an API endpoint
   (would require a backend or Lambda proxy).
