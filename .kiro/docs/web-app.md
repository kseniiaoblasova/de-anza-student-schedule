# Web App — Pathway Explorer

A single-page React app that lets anyone browse, search, and inspect De Anza's
~238 program pathways, and — once a pathway is open — check live whether a chosen
term's courses fit together. It is the first user-facing surface for the
scheduling challenge: it makes the pathway maps (today locked in ~80 static PDFs)
skimmable and searchable, and answers "can I actually take these together this
term" on demand.

## What

A Vite + React 19 SPA under `web-app/`. It renders a filterable grid of program
cards; clicking one opens a full-screen detail panel with an **interactive
planner**: the student picks a term (any of the six loaded quarters) and clicks
the pathway's course chips, then hits "Check my schedule." The app calls the
keyless `/plan` endpoint, which pulls that term's sections and compares every
cross-course section pair, and renders a **user-friendly result** — an overlap
percentage headline, a "can't take together" list of clashing section pairs (with
the overlapping days/times), a collapsible "fit together" list, and a muted
"not offered this term" line. Prerequisites, notes, and the source PDF + page
still show below. Cards show no conflict count — conflicts are only ever shown
dynamically, per the term/courses a student picks in the planner. Search matches
program name, department ("village"), or any required course code; two dropdowns
filter by degree type and department.

## Why

The pathway maps are the human-readable half of the challenge but exist only as
PDFs with no interface. This app turns the parsed pathway dataset into something
a student, advisor, or scheduler can actually explore, and surfaces the
backend's per-quarter conflict analysis (`deanza-pathway-conflicts`) so the
"can I actually take this quarter's courses" question is answered right in the UI.

## How

- **Stack:** React 19 + Vite 8, plain CSS (no UI framework). No router — a single
  `App` with local `useState`.
- **Pathway data is static; the planner is live.** Two JSON files are
  imported directly by `src/data/pathways.js` and transformed at module load —
  these drive the grid and search with no runtime call:
  - `src/data/deanza_pathways.json` — same shape as the `deanza-pathways` table
    (pathway metadata + verbose per-quarter course text).
  - `src/data/pathway_conflicts.json` — the precomputed conflict analysis,
    exported from `deanza-pathway-conflicts` (see "Conflict data" below). No
    longer surfaced as a card badge; now used only to derive each pathway's
    canonical course codes for the planner chips.
  The detail-panel planner, by contrast, calls the `/plan` endpoint at runtime
  (`src/config.js` → `PLAN_API_URL`, overridable with `VITE_PLAN_API_URL`).
- **State flow:** `App` holds `filters` and `selectedProgram`. `filteredPrograms`
  is a `useMemo` over the transform output. Components are presentational and
  receive props + callbacks:
  - `SearchFilter` — search box + degree/department selects + reset.
  - `ProgramList` → `ProgramCard` — the result grid (empty state when zero).
  - `ProgramDetails` — the modal overlay. Holds the planner's local state (chosen
    `termCode`, the `Set` of selected course codes, and request `status`/`result`)
    and renders the term picker, chips, and results (see the planner section).
- **`pathways.js` is where the real logic lives.** Two notable pieces:
  - `transformPathway` flattens the nested year/quarter JSON into per-program
    fields (short name, credential type, flattened course lists, 1- vs 2-year
    duration inferred from whether year 2 has any courses).
  - `countDistinctCourses` counts *actual* course requirements from the verbose,
    multi-line pathway text (a "Complete N units from List A: ..." block spanning
    four lines counts as one requirement, not four). This drives the "N courses"
    figure on each card.
  - `popularitySort` orders programs by hard-coded demand tiers (STEM/tech first,
    trades/misc last), breaking ties by credential weight (transfer > bachelor >
    AS > AA > certificate).
- **Interactive planner (`ProgramDetails`).** Three steps: pick a term (the six
  `TERMS` from `config.js`), click the pathway's course chips (multi-select), then
  "Check my schedule" (enabled once a term and ≥2 courses are chosen). Once a term
  is chosen, a **"Recommended this quarter"** chip row appears above the full list,
  showing just the courses the program map places in the quarter that term maps to
  (`TERMS[].quarterKey` → `conflictsByQuarter`). Both rows render via one shared
  `renderChip` and toggle the same `selected` Set, so picking a recommended course
  also lights it up in the full list — the two rows are alternate entry points into
  one selection, not independent state. That POSTs
  `{ term_code, courses }` to `PLAN_API_URL` and renders the `<PlanResult>` child:
  a percentage verdict, the "can't take together" overlap list (each pair's shared
  days + times), a collapsed "fit together" list, and the "not offered this term"
  line. Loading/error states are handled inline; changing the term or a chip
  invalidates the shown result, and the whole planner resets when a different
  pathway opens (keyed on `pathwayId` in a `useEffect`).
- **Recommended course map (`ProgramMap`).** Below the planner, an informational
  grid shows the pathway's suggested plan by year and quarter, rendering the
  verbose `required_courses` / `additional_courses` text straight from the pathway
  JSON (De Anza red year banner, gold quarter headers). Read-only — it's the
  overall picture; selection still happens through the chips. Note the electives
  it lists are already selectable as chips: the real elective options live inside
  `required_courses` text ("Complete N units from List A: …", GE-area course
  choices) and were extracted into `courseCodes` by the backend normalization;
  the `additional_courses` field is mostly sparse footnotes.
- **Where the chips come from.** The verbose `required_courses` text isn't clean
  codes, so `transformPathway` derives `courseCodes` — the sorted union of every
  quarter's `courses` + `missing_courses` from the precomputed conflict data
  (already canonical, `"MATH 1A"`). No client-side normalization; pathways with no
  conflict data simply have no chips.
- **Conflict-data join (chips only).** `pathways.js` imports
  `pathway_conflicts.json`, keyed by `pathway_id` = `"<source_file>#<page_number>"`
  — the same identity the backend tables use. `transformPathway` still attaches
  `conflictsByQuarter` (kept as the source for `courseCodes`), but the precomputed
  counts are **no longer shown anywhere in the UI**: the card badge was removed so
  conflicts appear only dynamically, from the planner's live `/plan` call.
- **Styling:** `src/styles.css` defines De Anza brand tokens (red `#8c1515`, gold
  `#c49a1a`) as CSS variables; cards and badges are color-coded by credential
  type in `ProgramCard`.

## Run it locally

Requires Node (tested on v24) and npm. From `web-app/`:

```bash
npm install       # first time only
npm run dev       # Vite dev server, hot reload — http://localhost:5173
```

Other scripts: `npm run build` (production bundle to `dist/`) and
`npm run preview` (serve the built bundle). `node_modules/` and `dist/` are
git-ignored, so a fresh clone needs `npm install`.

To refresh the pathway data, replace `src/data/deanza_pathways.json` with a newer
export of the same shape (`{ institution, catalog_year, total_pathways,
pathways: [...] }`); no code change needed.

To refresh the conflict data, regenerate the bundled JSON from DynamoDB (needs
valid AWS creds in `.env`):

```bash
python scripts/pathway_conflicts/export_web_data.py   # writes src/data/pathway_conflicts.json
```

Rerun it whenever `deanza-pathway-conflicts` is rebuilt. Both data files are
committed (like `deanza_pathways.json`), so a clone builds without AWS access.

## Decisions & alternatives

- **Hybrid: static data for browsing, a live call for planning.** Pathway and
  precomputed-conflict data stay bundled (fast grid/search/badges, no key needed),
  but the detail-panel planner fetches from the keyless `/plan` endpoint so a
  student can check *any* term + course combination against the current schedule —
  not just the precomputed pathway-quarter mapping. The endpoint is keyless
  precisely so the browser needs no secret. Cost: the planner needs the API up and
  reachable (CORS), whereas browsing works fully offline from the bundle.
- **Join on `pathway_id`, computed client-side.** The conflict export is keyed by
  `"<source_file>#<page_number>"`; the frontend already carries those fields, so
  the join is a string concat with no extra backend work. Verified: all 235
  conflict pathways resolve against the bundled pathway list (0 orphans).
- **No state library / router.** One screen, shallow state — `useState` +
  `useMemo` is enough; Redux/Router would be overhead.
- **Course counting lives in the client.** The source pathway text is verbose and
  multi-line; rather than pre-compute counts, `countDistinctCourses` heuristically
  collapses continuation lines. It is a heuristic (pattern-matched line
  classification), so odd formatting in a new pathway can miscount — see gotchas.
- **Hard-coded popularity tiers.** Real major-declaration data isn't available
  (a known challenge gap), so ordering uses a keyword-based demand proxy. Swap
  `getPopularityRank`/`popularitySort` when enrollment data lands.
- **Student picks courses, rather than viewing a fixed quarter.** The details
  panel evolved from rendering a pathway quarter's precomputed conflicts to an
  interactive planner where the student chooses the term and the specific courses
  to attempt. This matches the real question ("can I take *these* together?") and
  frees the check from the pathway's year→term mapping. Tradeoff: the answer now
  depends on a live endpoint, and the chips are limited to the pathway's known
  course codes (from the conflict data), not every course offered in the term.

## Gotchas

- **`deanza_pathways.json` is duplicated.** A copy also lives at
  `data/s3-raw/data/program-pathways/`. The app reads only its own
  `src/data/` copy; keep them in sync manually if the source changes.
- **`countDistinctCourses` is heuristic.** It classifies each line as a new
  requirement vs a continuation via regex patterns. New pathways with unusual
  formatting may over- or under-count the "N courses" badge; the underlying
  detail view still shows every raw line correctly.
- **Modal locks body scroll** via `document.body.style.overflow`; it is reset on
  close. If the details component is ever unmounted by another path, scroll could
  stay locked.
- **`index.html` still references the default `vite.svg` favicon**, though a
  `public/favicon.svg` exists — cosmetic mismatch.
- **Conflict counts are section-pair based.** `conflict_count` / the card badge
  count *pairs of overlapping sections*, not "is a clash-free schedule possible."
  A course with many sections inflates the number. The UI wording says "time
  conflicts between sections" to avoid implying a feasibility verdict.
- **`missing_courses` aren't clash-free.** Courses with no section in the term
  (not offered, or a pairing gap) are excluded from the analysis and shown in a
  separate muted line — don't read their absence from the conflict list as "fine."
- **~3 pathways have no conflict data** (no quarter with two resolvable courses);
  their cards simply omit the badge (`hasConflictData` is false).
- **Bundled conflict JSON grows the main chunk** past Vite's 500 kB warning
  (~222 kB gzipped total). Fine for now; if it matters, split per-pathway files
  into `public/` and fetch on demand.
