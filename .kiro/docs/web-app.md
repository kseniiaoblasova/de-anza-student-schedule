# Web App — Pathway Explorer

A single-page React app that lets anyone browse, search, and inspect De Anza's
~238 program pathways. It is the first user-facing surface for the scheduling
challenge: it makes the pathway maps (today locked in ~80 static PDFs) skimmable
and searchable in a browser.

## What

A Vite + React 19 SPA under `web-app/`. It renders a filterable grid of program
cards; clicking one opens a full-screen detail panel. The panel shows a single
quarter's course load at a time: the student picks a quarter ("Year 1 — Fall",
"Year 1 — Winter", ...) from a dropdown, and the panel lists that quarter's
required and additional/elective courses **plus the precomputed schedule
conflicts for that quarter** — the pairs of course sections whose meeting times
overlap so a student can't take both — along with prerequisites, notes, and the
source PDF + page. Each card also carries a conflict badge (a hot-spot signal),
and the quarter dropdown flags which quarters have conflicts. Search matches
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
- **Data is static, bundled at build time.** Two JSON files are imported directly
  by `src/data/pathways.js` and transformed into one app-friendly array at module
  load — no runtime API calls:
  - `src/data/deanza_pathways.json` — same shape as the `deanza-pathways` table
    (pathway metadata + verbose per-quarter course text).
  - `src/data/pathway_conflicts.json` — the precomputed conflict analysis,
    exported from `deanza-pathway-conflicts` (see "Conflict data" below).
- **State flow:** `App` holds `filters` and `selectedProgram`. `filteredPrograms`
  is a `useMemo` over the transform output. Components are presentational and
  receive props + callbacks:
  - `SearchFilter` — search box + degree/department selects + reset.
  - `ProgramList` → `ProgramCard` — the result grid (empty state when zero).
  - `ProgramDetails` — the modal overlay. Holds its own local `selectedQuarter`
    state and shows one quarter's courses at a time via a dropdown (see below).
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
- **Per-quarter course view (`ProgramDetails`).** The panel now shows one quarter
  at a time instead of the whole two-year plan at once. On open it builds a
  dropdown from only the quarters that actually have courses (label
  `"Year N — Quarter"`, value `"year_1|fall"`); `selectedQuarter` local state
  drives which quarter renders. Selecting one shows that quarter's *Required
  Courses* and *Additional / Elective* lists, then the *Schedule Conflicts* panel
  (below); until then a placeholder prompts the user to pick a quarter.
- **Conflict data & join.** `pathways.js` also imports `pathway_conflicts.json`,
  keyed by `pathway_id` = `"<source_file>#<page_number>"` — the same identity the
  backend tables use. `transformPathway` builds that id from the pathway's
  `sourceFile`/`pageNumber`, attaches the pathway's `conflictsByQuarter` map
  (keyed by `quarter_key`, e.g. `"year_1#fall"`), and rolls up `totalConflicts`
  for the card. Each quarter entry carries `courses`, `missing_courses`,
  `section_count`, `conflict_count`, `conflict_percentage`, and a `conflicts`
  list of section-pair clashes (`course_a`/`crn_a` × `course_b`/`crn_b` +
  day/time overlap). Codes are canonical (`"MATH 1A"`) — the backend derives them
  from the normalized pathways, so nothing needs renormalizing client-side.
- **Where conflicts render.** `ProgramCard` shows a badge ("N time conflicts" /
  "No time conflicts", only when conflict data exists). `ProgramDetails` annotates
  each dropdown option with its conflict count and, for the selected quarter,
  renders the conflict pairs with their overlapping days/times, a summary line,
  and a muted "not offered / unmatched this term" list from `missing_courses`.
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

- **Static JSON export, not a live API.** Both pathway and conflict data are
  bundled at build time rather than fetched from the conflict Lambda. Simplest
  thing that ships, needs no API key in the browser, and the conflict analysis is
  precomputed and read-heavy anyway. Cost: data is only as fresh as the last
  `export_web_data.py` run, and the conflict JSON (~1.8 MB) inflates the bundle.
  A live fetch is a later swap if freshness matters.
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
- **One quarter at a time, not a full timeline.** The details panel used to
  render every quarter's courses simultaneously in a year/quarter grid. It was
  replaced with a dropdown that reveals a single quarter's course load on demand.
  Trades an at-a-glance overview for a focused, less cluttered view that frames
  the question the challenge cares about — "what must a student take *this*
  quarter" — one term at a time. The full-grid styles (`pathway-timeline`,
  `quarters-grid`, `quarter-block`) are gone; the new markup uses
  `quarter-selector` / `quarter-courses`.

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
