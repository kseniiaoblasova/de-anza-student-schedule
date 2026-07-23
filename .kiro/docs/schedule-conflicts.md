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
  conflict_engine.py  pure: build_sections, find_conflicts, classify_pairs
  lambda_handler.py   AWS entry (/conflicts): unwrap event, validate, engine, HTTP response
  section_lookup.py   I/O: term + course codes -> that term's section payloads (reads DynamoDB)
  plan_handler.py     AWS entry (/plan): term-aware student planner (lookup + classify)
tests/conflicts/      tests mirroring the above
infra/template.yaml   SAM: two Lambdas + REST API + API key/usage plan + CORS
```

## Student planner endpoint (`POST /plan`, no API key)

A second, **term-aware** entry point for the browser app. Where `/conflicts` is
handed a section list, `/plan` is given a term and canonical course codes and
looks the sections up itself, then returns the full overlap/clear split (not just
the collisions) so a student sees *which of their picks fit together and which
can't*.

```
term_code + courses ─► section_lookup (reads deanza-class-schedule)
                    ─► conflict_engine.classify_pairs  (every cross-course pair, Yes/No)
                    ─► student-facing summary + overlap %
```

**Request**

```json
{ "term_code": "202722", "courses": ["MATH 1A", "ENGL 1A", "HIST 1A"] }
```

- `term_code` (required): a schedule term (`202622/32/42` = AY2025-26 F/W/Sp,
  `202722/32/42` = AY2026-27). Both loaded years are valid.
- `courses` (required, non-empty): **canonical** codes (`"MATH 1A"`). Bridged to
  schedule rows (`"MATH D001A."`) with the shared `normalize_course`.

**Response 200**

```json
{
  "term_code": "202722",
  "requested_courses": ["MATH 1A", "ENGL 1A", "HIST 1A"],
  "offered_courses": ["MATH 1A", "ENGL 1A", "HIST 1A"],
  "not_offered_courses": [],
  "section_count": 14,
  "pairs_evaluated": 47,
  "overlap_count": 6,
  "clear_count": 41,
  "overlap_percentage": 12.8,
  "overlaps": [ { "course_a", "crn_a", "course_b", "crn_b",
                  "overlap": true, "overlap_detail": {days,time_a,time_b},
                  "meta_a", "meta_b" } ],
  "clear":    [ { "course_a", "crn_a", "course_b", "crn_b", "overlap": false,
                  "meta_a", "meta_b" } ]
}
```

- `overlap_percentage` = `overlap_count / pairs_evaluated * 100` (0 when no pairs).
  Unlike `/conflicts`, this endpoint *does* compute the percentage — it's the
  headline the UI shows.
- `not_offered_courses`: requested courses with no section in the term (not
  offered, or an alias twin like `EWRT 1A` vs `ENGL C1000`). Surfaced, not
  dropped.
- `overlap_detail` (shared days + both times) is present only on `overlaps`.

**How it reads the schedule.** `section_lookup` queries the term partition
(narrowed to the requested subjects via a filter), indexes rows by canonical
course (`pathway_conflicts.resolve.index_sections_by_course`), and collects every
section of each course (`build_section_payload`). It uses the **default AWS
credential chain** (the Lambda execution role), *not* `common.get_session()` —
that reads explicit env keys, which is right for the CLI loaders but wrong in
Lambda. So the function needs `dynamodb:Query` on `deanza-class-schedule`.

**No API key.** `/plan` is public (`ApiKeyRequired: false`) so the browser can
call it without shipping a secret. The data is read-only published-schedule info;
the usage plan's throttle still applies. Lock `CORS_ALLOW_ORIGIN` to the app's
origin for real use.

> `find_conflicts` is deliberately left untouched — the pathway-conflicts batch
> pipeline depends on its exact shape. `classify_pairs` is a sibling that reuses
> the same `build_sections`/`find_pair_conflict` internals and adds the
> non-colliding pairs; `overlap_count` is guaranteed to match the old
> `conflict_count` (regression-tested).

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
to build). CORS was added later with an `OPTIONS /conflicts` method (Lambda proxy,
no api key) plus CORS headers from the Lambda, then a fresh `prod` deployment.

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

**`/plan` (the planner) — deployed (workshop account, us-west-2).**

- Function `deanza-schedule-plan` (python3.12, handler
  `conflicts.plan_handler.handler`, timeout 30s, env
  `SCHEDULE_TABLE=deanza-class-schedule`, `CORS_ALLOW_ORIGIN=*`).
- Live endpoint (no API key):
  `https://63l5xpc4uk.execute-api.us-west-2.amazonaws.com/prod/plan` — a `POST /plan`
  resource on the **same** REST API as `/conflicts`, with `OPTIONS /plan` for CORS,
  both `AWS_PROXY` to the function.
- **Role.** Reuses the conflict Lambda's role
  (`deanza-bedrock-chatbot-ChatFunctionRole-…`) plus a new **read-only** inline
  policy `PlanFunctionDynamoRead` (`Query`/`Scan`/`GetItem`/`BatchGetItem` on
  `deanza-class-schedule` only). The scan permission covers the no-subject-filter
  fallback. This role grant is the *only* IAM change; the local load/query scripts
  are unaffected (they run as the SSO user, a different principal).
- **Packaging.** The zip is the whole `scripts/` tree, not just `conflicts/` —
  `plan_handler` transitively imports `class_schedule.query`,
  `pathway_conflicts.resolve`, `course_pairing.normalization`, and `common`.
  `common.py`'s `python-dotenv` import is optional (guarded) because that package
  isn't in the Lambda runtime.

To update the code: rezip `scripts/` and
`aws lambda update-function-code --function-name deanza-schedule-plan --zip-file fileb://<zip>`.

> Gotcha: after adding the `/plan` methods, the **first** `create-deployment` may
> still 403 with "Missing Authentication Token" until it propagates — redeploy the
> `prod` stage once more and it resolves.

> **Auth:** a REST API is used (not HTTP API) because API keys + usage plans are a
> REST API feature. Every call requires an `x-api-key` header; the usage plan
> throttles and caps monthly quota. Verified: a request without the key returns
> `403`.

### CORS (browser/React callers)

CORS is configured, so the endpoint is callable from a browser:

- The Lambda returns `Access-Control-Allow-Origin` (and `-Headers`/`-Methods`) on
  **every** response, including errors, so the browser can read them.
- An `OPTIONS /conflicts` method (Lambda proxy, **no API key**) answers the
  browser's preflight with `204` + CORS headers. Preflight carries no key because
  browsers don't send custom headers on it; the actual `POST` still requires the
  key.
- Allowed origin is `*` by default, from the `CORS_ALLOW_ORIGIN` Lambda env var.
  **Tighten it** to the frontend's origin (e.g. `https://app.example.edu`) for
  real use: `aws lambda update-function-configuration --function-name
  deanza-schedule-conflicts --environment "Variables={CORS_ALLOW_ORIGIN=https://…}"`.

Verified live: preflight `OPTIONS` → `204` with CORS headers (no key); `POST` with
key + `Origin` → `200` with `Access-Control-Allow-Origin`.

From React (`fetch`):

```js
await fetch(API_URL, {
  method: "POST",
  headers: { "Content-Type": "application/json", "x-api-key": API_KEY },
  body: JSON.stringify({ term_code: "202722", sections }),
});
```

Note: shipping the API key in browser code exposes it. For a public frontend,
prefer proxying through a small backend, or restrict the key's usage-plan quota.

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

- **`/conflicts` is not term-aware by itself** — the caller supplies the right
  term's sections (the batch pipeline maps year/quarter → term in
  `pathway_conflicts/resolve.py`). The `/plan` endpoint *is* term-aware: give it a
  `term_code` and it reads the sections itself.
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
