# Schedule Conflict Service — Lambda + API Gateway

## What

A stateless HTTP service that takes a list of course sections and returns the
pairs that **can't both be taken** because their meeting times overlap. Given
the sections offered for the courses in one pathway quarter, it reports every
conflicting cross-course section pair with metadata. It does not read DynamoDB
and does not compute percentages — it's a pure overlap engine behind an API.

## Why

This is the core of the conflict analysis. Future script walks each pathway
quarter, pulls that quarter's course sections from `deanza-class-schedule`, and
calls this service to find the time clashes; the scheduler-facing tool calls the
same endpoint. Keeping it stateless and pure makes it trivial to test and reuse
by both callers.

## How it fits

```
                        pathway quarter's course sections (JSON)
pathway-conflict script  ─┐
                          ├─► POST /conflicts ─► Lambda ─► conflict_engine ─► conflict pairs
scheduler-facing tool  ──┘        (API key)      (handler)   (pure logic)
```

## Input contract

`POST /conflicts` with a JSON body. Section objects mirror `deanza-class-schedule`
items, so a caller passes rows straight from the table with no reshaping.

```json
{
  "sections": [
    { "course": "MATH D001A.", "crn": "28143", "meeting_days": "MW",
      "meeting_times": "09:30 am-10:20 am", "section": "01",
      "instruction_method": "IP", "instructor": "Ada L", "room": "S11",
      "start_date": "2026-09-21", "end_date": "2026-12-11", "part_term": "1" }
  ],
  "require_day_overlap": true,
  "require_date_overlap": false,
  "term_code": "202722"
}
```

- **Required per section:** `course`, `crn`, `meeting_days`, `meeting_times`.
  Everything else is optional and echoed back as conflict metadata.
- **Options:** `require_day_overlap` (default `true`), `require_date_overlap`
  (default `false`), `term_code` (optional, echoed back).
- Multi-meeting sections (lecture + lab) are just multiple items sharing a `crn`.

### Grounding in the real schedule metadata

- `meeting_times`: `"12:30 pm-04:20 pm"` (`hh:mm am/pm-hh:mm am/pm`) or `"TBA"`.
- `meeting_days`: day letters `M T W R(Thu) F S(Sat) U(Sun)`, e.g. `"MW"`, `"TR"`,
  `"MTWR"`, or `"TBA"`.
- `part_term`: `"1"` full term, `"A"` first half, `"B"` second half — with matching
  `start_date`/`end_date`.
- One CRN can span multiple meeting rows via `section_key = "CRN#seq"`.

## Overlap rules

Two section-meetings conflict when **they share a meeting day AND their time
intervals overlap**:

- Times parse to minutes since midnight; overlap is strict
  (`start1 < end2 and start2 < end1`), so back-to-back classes don't conflict.
  Any real overlap counts — identical, partial, or one contained in the other.
- Days must intersect (`MW` vs `TR` → no conflict even at the same clock time).
- `meeting_times`/`meeting_days` = `"TBA"` (or unparseable) → no fixed schedule,
  so the section **never conflicts** (cleanly excludes online-async `OA` sections).
- `require_date_overlap` (off by default) additionally requires overlapping
  `start_date`/`end_date`, so a part-`A` and part-`B` section at the same time
  don't count. Left off for the MVP.

## Algorithm

1. Group input rows into sections by `crn` (a section = the union of its meeting rows).
2. Compare every section against every section of a **different** course, skipping
   same-course pairs (a student picks one section per course — the X'd diagonal).
3. A pair conflicts if *any* meeting of one overlaps *any* meeting of the other.
4. `O(n²)` over sections (`n(n−1)/2`), trivial for a pathway quarter's handful of courses.

## Output contract

```json
{
  "conflict_count": 1,
  "sections_evaluated": 12,
  "pairs_evaluated": 63,
  "term_code": "202722",
  "conflicts": [
    {
      "course_a": "ENGL D001A.", "crn_a": "31002",
      "course_b": "MATH D001A.", "crn_b": "28143",
      "overlap": { "days": ["M", "W"], "time_a": "09:30 am-10:20 am", "time_b": "09:30 am-10:20 am" },
      "meta_a": { "section": "02", "instructor": "Bob K", "room": "L42", "instruction_method": "IP" },
      "meta_b": { "section": "01", "instructor": "Ada L", "room": "S11", "instruction_method": "IP" }
    }
  ]
}
```

`pairs_evaluated` (cross-course section pairs considered) is the denominator the
downstream aggregation uses to compute a conflict percentage — this service does
not compute it. Sides are ordered alphabetically by course.

## Files

```
scripts/conflicts/
  time_parsing.py     pure: parse_meeting_times / parse_meeting_days / *_overlap
  conflict_engine.py  pure: build_sections, find_conflicts
  lambda_handler.py   AWS entry: unwrap event, validate, call engine, HTTP response
tests/conflicts/      49 tests mirroring the above
infra/template.yaml   SAM: Lambda + REST API + API key/usage plan + CORS
```

The engine and parser import nothing AWS; the handler is a thin adapter, so the
same code runs in tests and in Lambda.

## Deploy

Two paths. All deploys need valid credentials (the `.env` STS creds are
short-lived — refresh before deploying).

### SAM (preferred, when permissions allow)

```bash
sam build -t infra/template.yaml
sam deploy --guided
```

**Blocked in the workshop account:** the `IsbUsersPS` SSO role is denied the SAM
transform (`cloudformation:CreateChangeSet` on `transform/Serverless-2016-10-09`),
so CloudFormation/SAM can't be used there. The template is kept for environments
that do allow it.

### Direct CLI deploy (used for the current deployment)

Because CloudFormation is denied, the live deployment was built imperatively with
the `aws` CLI: `lambda create-function` (reusing an existing Lambda execution
role, since `iam:CreateRole` isn't needed and the function only logs), then
`apigateway` calls to create the REST API, `/conflicts` POST (api-key required),
`AWS_PROXY` integration, `lambda add-permission`, a `prod` deployment, and an API
key + usage plan. No IAM role was created; no Docker needed (pure stdlib, nothing
to build).

### Current live deployment (workshop account, us-west-2)

- Function: `deanza-schedule-conflicts` (role reused:
  `deanza-bedrock-chatbot-ChatFunctionRole-…`)
- REST API id `63l5xpc4uk`, stage `prod`
- Endpoint: `https://63l5xpc4uk.execute-api.us-west-2.amazonaws.com/prod/conflicts`
- Usage plan `jzk6yb` (10 rps, burst 20, 100k/month); API key required.
- Retrieve the key value:
  `aws apigateway get-api-key --api-key 8dzyidlzm6 --include-value --query value --output text`

To update the function code after a change: rezip `scripts/conflicts` (as
`conflicts/…`) and `aws lambda update-function-code --function-name
deanza-schedule-conflicts --zip-file fileb://<zip>`.

> **Auth:** a REST API is used (not HTTP API) because API keys + usage plans are a
> REST API feature. Every call requires an `x-api-key` header; the usage plan
> throttles and caps monthly quota. Verified: a request without the key returns
> `403`. **CORS is not yet configured** (no OPTIONS/browser preflight) — the
> current callers are server-side; add CORS before the browser tool calls it.

## Calling it

```bash
API=https://63l5xpc4uk.execute-api.us-west-2.amazonaws.com/prod/conflicts
KEY=$(aws apigateway get-api-key --api-key 8dzyidlzm6 --include-value --query value --output text)
curl -X POST "$API" \
  -H "x-api-key: $KEY" \
  -H "Content-Type: application/json" \
  -d '{"term_code":"202722","sections":[
        {"course":"MATH D001A.","crn":"28143","meeting_days":"MW","meeting_times":"09:30 am-10:20 am"},
        {"course":"ENGL D001A.","crn":"31002","meeting_days":"MW","meeting_times":"09:30 am-10:20 am"}
      ]}'
```

For the pathway-conflict script: per pathway quarter, map year/quarter →
`term_code`, query `deanza-class-schedule` for the quarter's `normalized_courses`
(from `deanza-pathways-normalized`), POST the returned section rows, and store
the conflict pairs. Reuse `course_pairing.normalization.normalize_course` on both
sides so pathway codes (`"MATH 1A"`) line up with schedule courses (`"MATH D001A."`).

## Limitations & gotchas

- **Not term-aware by itself** — the caller supplies the right term's sections.
  Year/quarter → term mapping (year_1 = `202722`/`202732`/`202742`) is **not**
  built yet; year_2 has no future schedule loaded.
- **`TBA`/async sections never conflict** — no fixed time. If two async sections
  "should" be flagged for some other reason, this service won't.
- **Part-term A vs B** — with `require_date_overlap` off (default), same-time
  A and B sections are reported as conflicting though their dates don't overlap.
  Turn the toggle on to separate them.
- **Same-course pairs are skipped** — intra-course section clashes are intentionally
  ignored (student takes one section).
- **Percentages are downstream** — this returns raw pairs + counts only.
- Sides are ordered by course, so `course_a`/`course_b` are alphabetical, not
  input order.
```
