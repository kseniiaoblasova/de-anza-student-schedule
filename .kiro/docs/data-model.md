# Data model

Contents:
1. Schedule export (source of truth for offerings)
2. Canonical course id
3. Pathway JSON (target format for the program-map parser)
4. prereqs.json
5. crosswalk.csv
6. ge_areas.json
7. enrollment/
8. Normalized internal tables

---

## 1. Schedule export

One file per term, `.csv` or `.xlsx`, same schema in both. The `.xlsx` adds `ActivityDate`
and `OverrideButton`; the sheet name (e.g. "Build A Schedule Report - Night") is a report
label, not a filter — day sections are present.

Columns that matter for analysis:

| Column | Use |
|---|---|
| `Term_Code` | Term identity. Authoritative; do not trust the filename. |
| `Division` | Owning division (`2LA`, `2SS`, `2PS`, `2CB`, `2CA`, `2BH`, `2AT`, `2IC`, `2PE`, `2DS`, `2ST`, `2LR`). Used to route recommendations to a scheduler. |
| `Subject`, `Number` | Course identity. See §2. Note subjects with spaces/slashes: `C D`, `E S`, `P E`, `F/TV`. |
| `Section` | Section label. Suffixes (`01Y`, `50Z`) hint at modality — do not rely on them. |
| `CRN` | Section key, with `Term_Code`. Repeats across rows. |
| `SectionStat` | `O` active, `X` and `C` excluded. Confirm meanings with the college; record in manifest. |
| `InstructMethCode` | Modality label only: `OA` `IP` `HB` `OC` `O1` `OS` `XX`. Classify from meetings instead. |
| `PartTermCode`, `AcadCalenType` | Session block. `1` = full term; `A`/`B` = six-week halves; `S` = short. |
| `Start_Date`, `End_Date` | Meeting date window. Required for conflict tests. |
| `MeetingType` | `CLAS`, `LAB`, `TBA`, `OICH`, `OWRK`. |
| `Meeting_Days` | Character string or `TBA`. |
| `Meeting_Times` | `hh:mm am-hh:mm pm` or `TBA`. |
| `Room`, `Building` | Room double-booking checks on recommendations. |
| `EvisionsId` | Hash to `instructor_ref`. |
| `LastName`, `FirstName` | **Drop at load. Never persist, never emit.** |
| `MaxEnroll` | Seat supply. |
| `TotalEnroll` | Realized demand. Zero in future terms — historical only. |
| `WaitlistCapacity`, `WaitlistCount` | Secondary demand signal. Weaker than `TotalEnroll`: waitlists are capped and inconsistently used. |
| `Units` | Load modeling for the completion simulation. |

Ignore for analysis (payroll/workload): `AcctMethCode`, `RespPercent`, `WorkLoad`,
`WorkLoadAdj`, `LOAD`, `AssignType`, `ContractType`, `Position`, `PosSuffix`,
`SSRMEET_SessCredit`, `HrsWeek`, `HrsDay`, `SSRMEET.SSRMEET_HRS_TOTAL`, `ApproveTypeCode`,
`SessionInd`, `1stBlock_SchedCode`, `MeetingBlock_SchdCode`.

---

## 2. Canonical course id

Format: `SUBJECT NUMBER`, single space, uppercase.

From the schedule: strip the leading `D`, strip a trailing `.`, strip leading zeros, keep
trailing letters.

```
ARTS  D001A  -> ARTS 1A
APRN  D060.  -> APRN 60
EWRT  D68AX  -> EWRT 68AX
STAT  D010.  -> STAT 10
F/TV  D017G  -> F/TV 17G
```

From program maps: already short form (`ARTS 2B`, `PHTG 1`, `HUMI 16`) — uppercase and
collapse whitespace only.

Cal-GETC codes (`ENGL C1000`, `COMM C1000`, `STAT C1000`, `ENGL 1001`) do **not** normalize
mechanically. They resolve through `crosswalk.csv`. Note that `EWRT` still exists as a live
subject alongside `ENGL`, so a wrong guess here produces a plausible-looking but false
result — always route through the crosswalk, and put failures in `unresolved.json`.

---

## 3. Pathway JSON

One file per pathway. This is the **target format for the program-map parser** — build the
parser to emit this, rather than fitting the analysis to whatever the parser happens to
produce.

```json
{
  "pathway_id": "studio-arts-aat",
  "pathway_name": "Studio Arts",
  "award": "Associate in Arts for Transfer",
  "village": "Artistic Expression",
  "source": { "file": "2025_ART_All.pdf", "page": 1, "catalog_year": "2025-2026" },
  "terms": [
    {
      "year": 1,
      "quarter": "FALL",
      "requirements": [
        {
          "req_id": "y1-fa-1",
          "type": "course",
          "courses": ["ARTS 2B"],
          "units": null,
          "criticality": "major_prep",
          "raw": "ARTS 2B"
        },
        {
          "req_id": "y1-fa-3",
          "type": "choose",
          "courses": ["ENGL C1000", "ESL 5"],
          "choose_n": 1,
          "criticality": "major_prep",
          "raw": "ENGL C1000 (formerly EWRT 1A) or ESL 5 as required",
          "conditional": true
        },
        {
          "req_id": "y1-fa-4",
          "type": "ge_area",
          "ge_area": "2",
          "courses": [],
          "criticality": "ge",
          "raw": "MATH as required"
        }
      ]
    }
  ],
  "notes": [
    "ARTS 3TE, 4C, 14A, 14B, 14C, 16A, 16B and 16C are offered rarely..."
  ]
}
```

Field rules:

- `type`: `course` (all listed courses required), `choose` (pick `choose_n` or `units` worth
  from `courses`), `ge_area` (satisfied by any course in that GE area), `elective`.
- `criticality`: `major_prep` | `restricted_choice` | `ge` | `elective`. Drives scoring
  weights. A `choose` block from a named major list is `restricted_choice`, not `ge`.
- `units`: use instead of `choose_n` when the map specifies units ("Complete 4 units from
  List A", "Complete 12 units from List B"). Both may be null for a plain `course`.
- `conditional: true` for "as required" / "if not already taken" — these are placement- or
  history-dependent and must not be counted as hard blockers without saying so.
- `raw`: the exact source text. Required. Reports quote it when explaining a finding, and it
  is the only way to audit a parsing error.
- Cross-term repeats ("Complete 12 units from List B (if not already taken)" appearing in
  three consecutive terms) are one logical requirement spread across terms. Emit each term's
  entry with a shared `req_group` field so the analysis doesn't count it three times.

Parser hazards specific to these PDFs: the tables are multi-column with wrapped cells, so
text extraction interleaves columns; course lists run across line breaks mid-code
(`ARTS 18B, ARTS\n18C`); and the same PDF holds several pathways (the ART file has nine).
Validate every emitted course code against the schedule catalog and report unknowns rather
than dropping them.

---

## 4. prereqs.json

Prerequisites are boolean expressions, not lists.

```json
{
  "CHEM 1A": {
    "prereq": {
      "all": [
        { "any": ["CHEM 10", "CHEM 25", "placement:chem"] },
        { "any": ["MATH 114", "placement:math-precalc"] }
      ]
    },
    "coreq": [],
    "advisory": ["ENGL C1000"],
    "source": "catalog 2025-2026 p.142"
  }
}
```

- `all` / `any` nest arbitrarily. Leaves are canonical course ids or `placement:<test>`.
- `advisory` is recorded but never treated as blocking.
- `coreq` must be schedulable in the *same* term — so a coreq pair that conflicts is
  automatically `BLOCKED`, a stronger finding than an ordinary same-term pair.
- Missing entry means "no prerequisite on record", which is different from "no
  prerequisite". Track coverage and state it in the report header.

---

## 5. crosswalk.csv

```csv
map_code,schedule_code,note
ENGL C1000,ENGL 1A,Cal-GETC rename of EWRT 1A
STAT C1000,STAT 10,formerly MATH 10
COMM C1000,COMM 1,
ENGL 1001,EWRT 2,
```

One row per mapping. `note` is surfaced in reports whenever a finding depends on that row,
because a wrong crosswalk row produces a confident wrong answer.

---

## 6. ge_areas.json

```json
{ "3": { "name": "Arts and Humanities", "courses": ["ARTS 1A", "HUMI 1", "..."] } }
```

Optional. Without it, `ge_area` requirements cannot be conflict-tested — report GE coverage
as `not evaluated` in every affected report rather than assuming GE requirements are
satisfiable. Since GE is low priority by design, missing this file degrades the analysis
gracefully; a missing crosswalk does not.

---

## 7. enrollment/

Optional. Any of:

- Historical section enrollment — already present in the schedule exports as `TotalEnroll`.
- Headcount by major or by pathway — improves `demand_weight` substantially.
- Term headcount totals — lets reports express impact as students affected, not just scores.

The college has stated major-declaration data is unreliable. If it is provided anyway,
record its source and known accuracy in the manifest, and keep an `unweighted` variant of
every ranking so conclusions can be checked without it.

---

## 8. Normalized internal tables

```
sections(term_code, crn, course_id, subject, number, section_label, division,
         section_stat, instruct_meth, part_term, max_enroll, total_enroll,
         waitlist_count, units, instructor_ref, is_async, n_meetings)

meetings(term_code, crn, meeting_seq, meeting_type, days[], start_min, end_min,
         start_date, end_date, room, building, is_timed)

courses(course_id, subject, number, division, terms_offered[], sections_per_term{},
        seats_per_term{}, mean_enroll, mean_fill_rate, is_rare)
```

`is_rare` = offered in fewer than half the observed terms, or a single section in every term
it appears. Rare courses are where a one-quarter slip becomes a one-year slip, so they carry
elevated severity in prereq chains.
