# Backend Architecture — Overview

Start-here map of the backend for the student-centered scheduling challenge.
Detailed per-feature docs are linked from each section; this page is the mental
model and the pointers, not the details.

## Goal

Find, for the published class schedule, where required courses in a program's
pathway map are offered at overlapping times — so students can't take a full
quarter's load. The backend turns three messy inputs (pathway PDFs, the class
schedule, and course-code conventions) into a queryable per-pathway,
per-quarter conflict dataset that a React app and analysts can consume.

## End-to-end data flow

```
 raw pathway PDFs ─► deanza-pathways ─┐
                                      │ normalize course text  (course_pairing)
                                      ▼
                        deanza-pathways-normalized
                                      │
 class schedule xlsx/csv ─► deanza-class-schedule
                                      │
        ┌─────────────────────────────┘
        │  for each pathway quarter: courses ─► all sections in the term
        ▼
   conflict Lambda  (deanza-schedule-conflicts, behind API Gateway)
        │  day+time overlap among cross-course section pairs
        ▼
   deanza-pathway-conflicts  ──►  React app / analysis
```

## The four DynamoDB tables (us-west-2, on-demand)

| Table | Role |
|-------|------|
| `deanza-pathways` | Source program maps (~238), verbose course text per quarter. |
| `deanza-pathways-normalized` | Same pathways with cleaned canonical course codes. |
| `deanza-class-schedule` | ~25.8k section-meeting rows across two academic years, keyed by term. |
| `deanza-pathway-conflicts` | 983 per-pathway-per-quarter conflict results (the output). |

Full schemas, keys, term-code reference, and load commands: `dynamodb.md`.

## Components (in dependency order)

1. **Course pairing** — `scripts/course_pairing/` → doc: `course-pairing.md`
   Normalizes both sides to one canonical course identity (`"MATH D001A."` and
   `"MATH 1A"` → `MATH 1A`), parses verbose pathway text into clean course lists
   (writes `deanza-pathways-normalized`), and audits how well pathway courses
   pair with the schedule (~83% coverage). `normalization.py` is the shared
   identity function reused everywhere downstream.

2. **Conflict service** — `scripts/conflicts/` + `infra/` → doc: `schedule-conflicts.md`
   A stateless engine that takes a list of course sections and returns
   conflicting cross-course section pairs (shared meeting day AND overlapping
   time; async/TBA excluded; same-course pairs skipped). Deployed as an AWS
   Lambda (`deanza-schedule-conflicts`) behind an API-key-protected REST API.
   Pure logic (`time_parsing`, `conflict_engine`) is separate from the thin
   `lambda_handler`. A second, **term-aware** entry point (`plan_handler` +
   `section_lookup`, endpoint `/plan`, keyless) powers the browser app's live
   student planner: given a term + canonical course codes it reads the sections
   from `deanza-class-schedule` itself and returns the full overlap/clear split
   (via `conflict_engine.classify_pairs`) with a percentage.

3. **Pathway conflicts pipeline** — `scripts/pathway_conflicts/` → doc: `pathway-conflicts.md`
   The orchestrator that ties it together: for each normalized pathway quarter,
   maps to a term, pulls every section of every course from the schedule, calls
   the conflict Lambda, and writes results to `deanza-pathway-conflicts`.

## Key cross-cutting decisions

- **One canonical course identity** bridges pathways and schedule; everything
  joins on it. Statewide `C1000` codes the schedule doesn't use are kept but
  land in `missing_courses` (their "formerly" twin usually matches).
- **Conflicts are section-level pairs** (every section of A vs every section of
  B, same-course skipped), matching the whiteboard model. This is not yet a
  "can the student build one clash-free schedule" feasibility metric.
- **Day + time overlap**, strict (back-to-back is fine); `TBA`/async never
  conflicts; part-term A/B date separation is a wired-but-off toggle.
- **Term mapping**: pathway year_1 → AY2025-26 (`202622/202632/202642`),
  year_2 → AY2026-27 (`202722/202732/202742`) — both real published schedules.
  One dict in `pathway_conflicts/resolve.py`.
- **Pure-logic vs I/O split** in every component: parsing/engine logic is pure
  and unit-tested; DynamoDB/Lambda/argparse live in thin runnable entry points.
  119 tests total. See `.kiro/steering/project-organization.md`.

## Conventions

- `scripts/common.py` centralizes `.env`/boto3 wiring and `TABLE_SCHEMAS` (single
  source of truth for keys; `create_table_if_absent` provisions from it).
- Credentials are temporary STS keys in `.env`; they expire — refresh all three
  (`AWS_ACCESS_KEY_ID`/`SECRET`/`SESSION_TOKEN`) when calls fail with an expired
  token. Load them for CLI use with `set -a; . ./.env; set +a`.
- Runnable scripts default to a dry run; `--apply` writes. Loaders never mutate
  source tables (normalized/conflict data go to separate tables).

## Current state & open follow-ups

- Deployed and populated: conflict Lambda + API is live; all four tables exist
  and `deanza-pathway-conflicts` holds 983 items.
- **Git**: this work spans feature branches; `all-class-conflicts` currently
  integrates all of it but is not pushed to `origin` or merged to `main`.
- **CORS** is configured on the conflict API (OPTIONS preflight + headers), so a
  browser/React client can call it. Allowed origin defaults to `*` — tighten
  `CORS_ALLOW_ORIGIN` to the frontend origin for production.
- **UI**: a React pathway explorer (`web-app/`, doc `web-app.md`) browses the
  pathways from bundled data and, per pathway, runs a live term/course conflict
  check against the `/plan` endpoint. The `/plan` Lambda (`deanza-schedule-plan`)
  is **deployed and live** (keyless, reads the schedule table via a read-only
  inline policy on the reused role; see `schedule-conflicts.md`).
- **Not built yet**: a schedule-feasibility metric (can a full clash-free load be
  built). Enrollment weighting of "hot spots" is possible but unused.
- **Deploy note**: the workshop SSO role is denied the SAM/CloudFormation
  transform, so the Lambda + API were deployed imperatively via the `aws` CLI
  (details in `schedule-conflicts.md`); the SAM template is kept for other envs.
