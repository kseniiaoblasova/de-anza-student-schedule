---
inclusion: always
---

# Documentation & Decision Logging

**Document substantial work.** When you write a significant chunk of code — a
new module, a feature, a non-trivial refactor, or any change that involves an
architectural or design decision — write a short companion doc to `.kiro/docs/`.
Skip this for trivial edits (typos, one-liners, renames, formatting). A doc
nobody needs is noise.

**Where and how.** One markdown file per feature or area, named for it:
`.kiro/docs/<feature-name>.md`. If a doc for that area already exists, update it
in the same session instead of creating a duplicate.

**What to capture.** Keep it skimmable — a reader should get the picture in
under a minute:
- **What** — what you built or changed, in 1–3 sentences.
- **Why** — the rationale; the problem it solves.
- **How** — the architecture and key patterns (main components, data flow,
  libraries chosen) and any important tradeoffs.
- **Decisions & alternatives** — notable choices and what you rejected, one line
  of reasoning each. This is the part a human cannot recover by reading the code.
- **Gotchas** — anything non-obvious a future maintainer must know.

**Succinct, not verbose.** Explain the shape and the reasoning, not every line.
Do not restate the code. No filler, no ceremony. If a bullet does not help
someone understand or maintain the system, cut it.

**Keep it true.** When you later change the code, update its doc in the same
edit. A stale decision log is worse than none.