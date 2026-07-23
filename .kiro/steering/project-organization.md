---
inclusion: always
---

# Project Organization

Keep the file tree tidy and predictable. A new file should have one obvious home,
and a reader should be able to guess where something lives without searching.

## Layout

```text
scripts/
  common.py            shared AWS/.env helpers (single source of truth)
  <domain>/            one folder per problem area (e.g. course_pairing/)
    __init__.py
    <module>.py        importable logic (pure where possible)
    <action>.py        runnable entry points (load/audit/migrate)
tests/
  <domain>/            mirrors scripts/<domain>/ one-to-one
    test_<module>.py
data/                  source data + pulled artifacts (git-ignored)
  reports/<domain>/    generated reports — never mixed with source data
.kiro/
  docs/                one markdown doc per feature/area
  steering/            always-on guidance
```

## Rules

- **Group by domain, not by file type.** Related scripts live together under
  `scripts/<domain>/`; do not scatter a feature across the tree.
- **No loose scripts at the repo root.** Every script belongs in `scripts/` (in a
  domain folder once one exists for its area).
- **Tests mirror source.** `tests/<domain>/test_<module>.py` matches
  `scripts/<domain>/<module>.py`. Keep the shapes in sync.
- **Generated output goes to `data/reports/<domain>/`,** never beside source data
  or code. Treat it as disposable.
- **Reuse `scripts/common.py`** for AWS/.env wiring instead of re-implementing it.
- **Separate logic from I/O.** Put pure, testable logic in a `<module>.py`; keep
  DynamoDB/S3/argparse in the runnable entry points. This keeps tests fast and
  side-effect-free.
- **When you add a new area,** create its `scripts/<domain>/` and `tests/<domain>/`
  folders together, and give it a `.kiro/docs/<domain>.md`.
