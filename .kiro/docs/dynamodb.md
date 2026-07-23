# DynamoDB — Data Store Reference

Core reference for the project's DynamoDB tables: what exists, how it's keyed,
what's loaded, and how to read/load it. For the challenge, these tables back the
schedule-vs-program-map conflict analysis.

## At a glance

| Table | Purpose | Key | Items |
|-------|---------|-----|-------|
| `deanza-pathways` | ~238 program-pathway maps | PK `pathway_id` | 238 |
| `deanza-class-schedule` | class sections, both schedule years | PK `term_code` + SK `section_key` | 25,811 |

- **Region:** `us-west-2`
- **Billing:** both tables are on-demand (`PAY_PER_REQUEST`) — no capacity
  tuning, negligible cost for these volumes.
- **Credentials:** temporary STS keys in `.env` (`AWS_ACCESS_KEY_ID` starting
  `ASIA`, plus `AWS_SECRET_ACCESS_KEY` and `AWS_SESSION_TOKEN`). They expire;
  refresh all three together when calls fail with an expired/invalid-token error.

## How to connect

All scripts load `.env` and build a boto3 session via `scripts/common.py`. In
your own code the minimum is:

```python
import boto3
table = boto3.resource("dynamodb", region_name="us-west-2").Table("deanza-class-schedule")
item = table.get_item(Key={"term_code": "202722", "section_key": "28143#0"})["Item"]
```

Or reuse the shared helper: `from common import get_table`.

---

## Table: `deanza-pathways`

One item per program-pathway map (the quarter-by-quarter course plan for a
credential).

- **Key:** partition `pathway_id` (S) = `"<source_file>#<page_number>"`.
  Program names aren't unique across the source PDFs; file + page is.
- **Attributes:** `program_name`, `village`, `credential_type`, `source_file`,
  `page_number`, `years` (nested map: `year_1/year_2` → `fall/winter/spring` →
  `required_courses[]`, `additional_courses[]`), `additional_notes[]`.
- **Source:** `s3://<bucket>/data/program-pathways/deanza_pathways.json`
  (238 pathways).
- **Access:** exact lookup by `pathway_id` is a `get_item`; village/program
  views are scans (fine at 238 items).

```bash
python scripts/pathways/query.py --count
python scripts/pathways/query.py --id "2025 ADMJ all.pdf#1"
python scripts/pathways/query.py --village "Physical Sciences and Technology"
python scripts/pathways/query.py --program accounting
```

---

## Table: `deanza-class-schedule`

One item per class section-meeting row, for **both** the 2026-27 published
schedule and the 2024-2026 historic schedule (with enrollment).

- **Key:** partition `term_code` (S, e.g. `202722`) + sort `section_key` (S) =
  `"<CRN>#<seq>"`. Partitioning by term makes "all sections in one quarter" a
  single efficient `query` — the unit of work for conflict detection. `seq`
  disambiguates sections that span multiple meeting rows (lecture + lab under one
  CRN) so they don't overwrite each other.
- **Promoted attributes** (from the SIS export via `COLUMN_MAP`): `division`,
  `subject`, `number`, `section`, `crn`, `instruction_method`, `section_status`,
  `part_term`, `start_date`, `end_date`, `meeting_type`, `meeting_days`,
  `meeting_times`, `room`, `building`, `instructor_first`, `instructor_last`,
  `instructor`, `max_enroll`, `total_enroll`, `waitlist_capacity`,
  `waitlist_count`, `units`.
- **Derived/added:** `course` = `"<subject> <number>"`, `academic_year` (coarse
  dataset tag — see gotchas), `source_file` (originating file), `raw` (map of all
  unmapped source columns, kept as strings so nothing is lost).
- **Numeric fields** (`max_enroll`, `total_enroll`, `waitlist_capacity`,
  `waitlist_count`, `units`) are stored as numbers (int/Decimal) so they can be
  summed/compared. Verified: all 25,811 items are numeric.

### Access

```bash
# Whole quarter (efficient query on the partition key)
python scripts/class_schedule/query.py --term 202722

# Narrow within a term
python scripts/class_schedule/query.py --term 202722 --course "MATH D001A."
python scripts/class_schedule/query.py --term 202722 --crn 28143

# Across all terms (scan + filter)
python scripts/class_schedule/query.py --subject MATH
python scripts/class_schedule/query.py --count
```

---

## What's loaded now (25,811 items)

| academic_year tag | quarters | rows |
|---|---|---|
| 2025-26 (8 CSVs) | `202512`–`202642` | 17,533 |
| 2026-27 (4 xlsx) | `202712`–`202742` | 8,278 |

### Term-code reference (verified against source files)

Format: `YYYY` + quarter suffix, where `YYYY` is the academic-year-ending year
and the suffix is **12=Summer, 22=Fall, 32=Winter, 42=Spring**.

| term_code | quarter | source file |
|---|---|---|
| 202512 | Summer 2024 | SU 2024.csv |
| 202522 | Fall 2024 | FA 2024.csv |
| 202532 | Winter 2025 | WI 2025.csv |
| 202542 | Spring 2025 | SP 2025.csv |
| 202612 | Summer 2025 | SU 2025.csv |
| 202622 | Fall 2025 | FA 2025.csv |
| 202632 | Winter 2026 | WI 2026.csv |
| 202642 | Spring 2026 | SP 2026.csv |
| 202712 | Summer 2026 | SU 202712.xlsx |
| 202722 | Fall 2026 | FA 202722.xlsx |
| 202732 | Winter 2027 | WI 202732.xlsx |
| 202742 | Spring 2027 | SP 202742.xlsx |

---

## Scripts

```
scripts/
  common.py              .env + boto3 helpers; TABLE_SCHEMAS registry;
                         create_table_if_absent / list_table_names / get_table
  create_tables.py       create any missing tables (no data); --list to inspect
  pull_s3_data.py        generic S3 -> local puller / --list bucket contents
  pathways/
    load.py   query.py   deanza-pathways
  class_schedule/
    load.py   query.py   deanza-class-schedule
```

`TABLE_SCHEMAS` in `common.py` is the single source of truth for key schemas;
both the loaders (`--create-table`) and `create_tables.py` provision from it, so
create and load can't disagree.

### Common commands

```bash
# Provision tables (idempotent)
python scripts/create_tables.py --list
python scripts/create_tables.py

# Load pathways
python scripts/pathways/load.py --create-table            # local copy
python scripts/pathways/load.py --from-s3                 # straight from S3

# Load schedule
python scripts/class_schedule/load.py --from-s3 --s3-prefix "data/2026-27-class-schedule/"
python scripts/class_schedule/load.py --format csv --from-s3 \
    --s3-prefix "data/2025-26-class-schedule/" --academic-year 2025-26
```

Loaders are idempotent — re-running overwrites items with the same key rather
than duplicating them.

## Design decisions & alternatives

- **One schedule table for both years, not one-per-year** — same entity, same
  query pattern, and the analysis compares the planned 2026-27 schedule against
  historic enrollment. DynamoDB has no joins, so separate tables would force
  app-side stitching.
- **Term-partitioned schedule key** over a unique-id key — analysis always works
  within a quarter, so partitioning by term is the natural efficient access path.
- **`CRN#seq` sort key** — 677 CRNs in one quarter alone have multiple meeting
  rows; the `seq` prevents them from overwriting each other.
- **Unique `source_file#page` key for pathways** — program names aren't unique.
- **Loader scripts over DynamoDB's native S3 import** — sources are a nested JSON
  array and typed spreadsheets, not the line-delimited CSV/DynamoDB-JSON/ION the
  native importer needs.
- **On-demand billing** — small, load-rarely datasets.

## Gotchas

- **STS creds expire.** Refresh all three `.env` values on auth failure.
- **`academic_year` is a coarse tag, not per-term truth.** The 2025-26 CSV load
  labels all 8 files `2025-26`, but their terms actually span AY2024-25
  (`202512`–`202542`) and AY2025-26 (`202612`–`202642`). Use **`term_code`**
  (decoded via the table above) as the authoritative term; `source_file`
  preserves the exact origin.
- **Keep numeric typing consistent across loads.** Enrollment fields must be
  numbers for cross-year comparison. If a batch is ever loaded by a different
  path that leaves them as strings, re-run the current loader for that batch
  (overwrites by key). Currently all items are numeric.
- **Course-code format differs from pathways.** Schedule `course` looks like
  `"MATH D001A."` (SIS `D`-prefix + trailing punctuation); pathway course codes
  look like `"MATH 1A"`. Matching the two tables needs a normalization step —
  a task for the analysis layer, not loading.
- **Scans vs queries.** Only term-scoped schedule reads and `pathway_id` lookups
  are true key queries; everything else scans. Cheap at these sizes, but if the
  data grows, add a GSI (e.g. on `course` or `subject`) rather than scanning.
