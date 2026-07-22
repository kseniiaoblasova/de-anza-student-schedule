---
inclusion: always
---

# Code Style

# Behavioral Rules

**Think before coding.** State assumptions out loud before writing anything.
If the request is ambiguous, ask. If a simpler approach exists, push back.
Stop when confused — name what is unclear and do not pick one interpretation
and run with it.

**Simplicity first.** Write the minimum code that solves the problem. No
speculative abstractions, no flexibility nobody asked for. The test: would
a senior engineer call this overcomplicated?

**Surgical changes.** Touch only what the task requires. Do not improve
neighboring code. Do not refactor what is not broken. Every changed line
should trace back to the request.

**Goal-driven execution.** Turn vague instructions into verifiable targets
before writing a line. "Add validation" becomes "write tests for invalid
inputs, then make them pass."

# Comments

**Block-level intent.** Above each meaningful chunk of code (a logical unit —
a setup phase, a transformation, a validation pass, a request/response cycle),
write a short comment stating the *goal* of that chunk: what it is trying to
achieve and why, not a line-by-line restatement of the code. A reader should
be able to skim only the block comments and understand the flow.

**Sub-comments for complexity.** Inside a chunk, add small inline comments only
where the logic is non-obvious — tricky algorithms, non-intuitive conditionals,
workarounds, edge-case handling, or anything a competent reader would have to
pause on. Explain the *why* or the mechanism, not the syntax.

**No noise.** Do not comment self-evident lines (`i++ // increment i`). If a
comment only repeats what the code plainly says, delete it. Comments earn their
place by adding information the code cannot express on its own.

**Keep them true.** When you change code, update or remove the comments around
it in the same edit. A stale comment is worse than no comment.