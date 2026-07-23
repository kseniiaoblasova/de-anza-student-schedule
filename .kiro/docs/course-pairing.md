# Course Pairing — normalize pathway courses & audit against the schedule

## What

Make `deanza-pathways` and `deanza-class-schedule` join on a shared course
identity. Pathways store courses as messy free text (`"ENGL C1000 (formerly
EWRT 1A) or ESL 5 as required"`); the schedule stores them SIS-style
(`subject="MATH"`, `number="D001A."`). This feature normalizes both to one
canonical form, writes the cleaned courses to a **new** `deanza-pathways-normalized`
table (the source table is never mutated), and audits how many pathway courses
actually pair with a scheduled course.

This is the foundation for the later conflict-detection Lambda: without reliable
pairing, Ashmeet's per-quarter conflict analysis has nothing to feed.

## Why

The two datasets name the same course differently, so a naive join matches
almost nothing. Cleaning pathways into concrete course lists and measuring match
coverage tells us whether the pairing is trustworthy before anything is built on
top of it.

## Canonical form

A course is the string `"<SUBJECT> <NUMBER>"`, uppercase. The number is reduced by:

- stripping whitespace and trailing punctuation (`D001A.` → `D001A`)
- dropping the De Anza campus `D` prefix when it precedes digits (`D001A` → `001A`)
- stripping leading zeros from the digit run (`001A` → `1A`)
- **keeping** statewide `C` numbers intact (`C1000` stays `C1000`)
- **keeping** letter suffixes (`64X`, `90A`)

Examples: `MATH D001A.` → `MATH 1A`; `ENGL C1000` → `ENGL C1000`;
`ADMJ 064X` → `ADMJ 64X`.

Implemented in `scripts/course_pairing/normalization.py` (pure, no I/O):
`normalize_number`, `normalize_course(subject, number)`,
`iter_course_codes(text, valid_subjects=None)`, `parse_course_code(...)`.

## Pairing rules

1. Only exact canonical-identity matches count as automatic matches (no fuzzy matching).
2. Both datasets normalize through the same functions.
3. Every explicit course in a pathway quarter is extracted — from required,
   additional, elective-list, "A or B", and "(formerly X)" entries — and all are
   treated as equal courses for the MVP.
4. Courses are deduplicated within a pathway quarter.
5. Aliases (e.g. `ENGL C1000` and its "formerly" `EWRT 1A`) are kept as separate
   courses for the MVP.
6. Vague requirements with no concrete course (`"MATH as required"`,
   `"Complete 25 units from List A:"`) are **not** guessed — they go to
   `unresolved_entries`.
7. Suspected source typos (`ADM 54` vs `ADMJ 54`) are **not** auto-corrected; the
   audit surfaces them instead.
8. Prose that is course-shaped ("Complete 25", "Area 3") is rejected via a
   subject allow-list sourced from real schedule subjects.
9. The MVP audit matches across **all** schedule terms; per-quarter availability
   is deferred.
10. Duplicate schedule rows / CRNs for one course do not inflate audit totals.

## Data sources observed

- Pathways: 238 pathways, 4,666 quarter course entries — ~3,117 simple,
  ~576 with "or", ~790 list/units, ~183 "as required" placeholders.
- Course lists split across adjacent array entries (a subject on one line, its
  numbers on the next), so parsing must carry subject context across entries.

## Parser (subject-carry)

`pathway_parser.py` walks a quarter's tokens carrying the "current subject" so a
subject dangling at an entry's end applies to the next entry's bare numbers; any
non-subject word resets the carry so list prose can't inherit a stale subject.
The subject allow-list is sourced from the schedule's distinct subjects (83).
An entry that yields no course is kept verbatim in `unresolved_entries`.

First dry-run coverage (238 pathways, local JSON): 1,428 quarters, 996 distinct
courses extracted, ~1,410 unresolved entries (mostly "GE Area N", "Complete N
units from List A", and "... as required" — genuinely course-less lines).

## Audit results & tuning

Run: `python scripts/course_pairing/audit_matches.py` (add `--use-cache` to reuse
the cached schedule course set instead of rescanning 25k rows). Writes
`data/reports/course-pairing/pairing_audit.json`.

- Schedule: 1,441 distinct courses from 25,811 rows.
- Baseline coverage: **826 / 996 = 82.9%** matched.
- After tuning (ordinal fix): **826 / 994 = 83.1%** matched.

The 168 unmatched pathway courses break down as:
- **~8 statewide-numbering twins** (`ENGL C1000`, `COMM C1000`, `POLS C1000`,
  `STAT C1000`, `COMM 1000`, `ENGL 1001`, …). The schedule uses old De Anza
  numbers, not the new statewide `C1000` codes. This is expected: the pathway
  text carries both (`"ENGL C1000 (formerly EWRT 1A)"`) and the "formerly" twin
  (`EWRT 1A`) *does* match, so the requirement is still covered. Kept separate
  per the MVP alias rule.
- **2 ordinals** (`AUTO 1ST`, `AUTO 2ND`) — fixed: ordinal tokens ("1st course")
  are no longer read as course numbers.
- **~158 real absences** — elective/"List A" courses (`ADMJ 64X`, `DMT 60B-E`,
  language/arts electives) that simply aren't offered in the loaded schedule
  years. Not a normalization problem.

No further normalization rules are justified; the residue is genuine data, not
parser error. One rare artifact remains (`BIOL 6BOR`, an "or" glued to a suffix
with no space in the source) — a single occurrence, not worth a special rule.

## Architecture & data flow

```
deanza-pathways (read only) ──┐
                              ├─ normalize_pathways.py ─→ deanza-pathways-normalized
schedule subjects (allow-list)┘        (pathway_parser + normalization)

deanza-pathways-normalized ─┐
                            ├─ audit_matches.py ─→ data/reports/course-pairing/pairing_audit.json
deanza-class-schedule ──────┘        (normalization, dedup, compare)
```

Files (all under `scripts/course_pairing/`):
- `normalization.py` — pure canonical-form functions (no I/O).
- `pathway_parser.py` — pure extraction from verbose quarter text (subject-carry).
- `normalize_pathways.py` — runnable: source → normalized table (dry-run by default).
- `audit_matches.py` — runnable: pathway↔schedule coverage report.

Tests mirror these under `tests/course_pairing/` (59 tests).

## Table: `deanza-pathways-normalized`

- **Key:** partition `pathway_id` (S) — same identity as `deanza-pathways`
  (`"<source_file>#<page_number>"`), so a normalized item lines up 1:1 with its
  source. Separate table so the source is never mutated.
- **Attributes:** `program_name`, `village`, `credential_type`, `source_file`,
  `page_number`, `normalization_version` (currently `1`), and `years`
  (`year_1/year_2` → `fall/winter/spring` → `{normalized_courses[],
  unresolved_entries[]}`).
- **Items:** 238 (one per source pathway). On-demand billing.
- The verbose source arrays (`required_courses`, `additional_courses`) are **not**
  copied here; read the source table if you need the original text.

## Commands

```bash
# Normalize (dry run — prints coverage, writes nothing)
python scripts/course_pairing/normalize_pathways.py --from-table

# Apply: create + populate the normalized table (idempotent, re-runnable)
python scripts/course_pairing/normalize_pathways.py --from-table --apply --create-table

# Audit coverage against the live normalized table (cache the 25k-row schedule scan)
python scripts/course_pairing/audit_matches.py --source normalized-table --use-cache

# Audit straight from source pathways without loading the table (for tuning)
python scripts/course_pairing/audit_matches.py --source build

# Tests
./venv/bin/python -m pytest tests/course_pairing/ -q
```

## For the conflict pipeline (Ashmeet)

- Read a pathway's quarter courses from `deanza-pathways-normalized`:
  `item["years"]["year_1"]["fall"]["normalized_courses"]` is a clean list of
  canonical codes (e.g. `"MATH 1A"`).
- Match them to sections by normalizing the schedule side the same way:
  `normalize_course(section["subject"], section["number"])` from
  `course_pairing.normalization`. **Do not** string-compare raw fields — the
  formats differ (`"MATH D001A."` vs `"MATH 1A"`).
- Pathway quarter → schedule term mapping is **not** done here. Year_1 fall/winter/
  spring correspond to `202722/202732/202742` (Fall 2026 / Winter 2027 / Spring
  2027); year_2 has no future schedule loaded (see limitations).
- Expect ~83% of distinct courses to resolve to a real course; the rest are
  statewide-number twins (covered by their "formerly" alias) or electives not
  offered in the loaded years.

## Limitations & gotchas

- **~17% of distinct courses don't pair.** Mostly electives not offered in the
  loaded schedule years, plus statewide `C1000` twins the schedule doesn't use.
  Coverage is course-identity across all terms, not per-quarter availability.
- **Aliases are separate courses** (`ENGL C1000` and `EWRT 1A` both kept). Good
  for coverage, but will double-count if fed naively into conflict-pair counts —
  group aliases before counting if that matters.
- **Elective lists are flattened to individual courses**, all treated as equally
  required for the MVP. This overstates the true course set ("choose N of these").
- **Unknown subjects are dropped** — a course whose subject isn't in the schedule's
  83 subjects is treated as prose and won't appear in `normalized_courses`.
- **Year_2 can't be schedule-checked** — no AY2027-28 schedule is loaded; only
  year_1 maps to real terms.
- **`unresolved_entries`** holds course-less requirements (`"MATH as required"`,
  GE-area lines, list headers). Surface these to schedulers rather than dropping.
- Re-running the loader overwrites by `pathway_id` (safe). Bump
  `normalization_version` if the parser changes so stale items are identifiable.

## Status

- [x] Canonical normalizer + tests
- [x] Pathway parser + tests (subject-carry, dry-run coverage)
- [x] `deanza-pathways-normalized` loader (dry-run default, --apply gated, source-write guard)
- [x] Pairing audit + tests (console + JSON report, schedule cache)
- [x] Real-data tuning (ordinal fix; 83.1% coverage; residue categorized)
- [x] Loaded 238 items to `deanza-pathways-normalized`; audit reproduced from the live table
