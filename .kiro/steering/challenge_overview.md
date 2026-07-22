# Challenge Overview: Student-Centered Scheduling — Cross-department schedule conflict analysis against program maps

## Project Objectives
- Analyze the currently published academic-year schedule to identify conflicts that prevent students from enrolling in the full set of courses required by their program maps.
- Enable cross-department schedule coordination that today happens in disconnected silos.
- Improve the student experience by ensuring courses across departments are offered at times/modalities that allow completion of a full quarterly course load.
- Reduce time-to-degree (associate's in two years vs. 4–6), cut scheduler workload, and drive high enrollment (≥80% of course caps filled).
- Leave room to scale to any CCC campus, since each maintains a comparable program-mapper tool.

## Current Workflow
- Scheduling data lives in per-department spreadsheets, emails, and Word documents; the published schedule and program maps live on the college website.
- Each department chair builds their department's schedule; deans aggregate by division and forward to the Office of Instruction.
- A lead scheduler in the Office of Instruction performs final data entry and verification.
- Manual artifacts include department spreadsheets, ~80 program maps (static PDFs), and the published schedule of classes.
- Program Mapper is a static, PDF-based tool with no programmatic interface; internal enrollment portals hold historic course-level data.

## Key Pain Points
- No coordination across departments, so courses required in the same quarter get scheduled at overlapping times, locking students out.
- No visibility into whether the published schedule actually supports completing any given program map on time.
- No systematic workflow or platform; process is entirely manual across spreadsheets, emails, and documents.
- Optimizing by declared-major volume isn't currently possible due to inaccurate/unavailable major-declaration data.
- Enrollment data exists but exports carry confidential fields, requiring de-identification before sharing.

## Ideal Solution Vision
- An analysis tool producing a conflict/"hot spot" report that maps the published schedule against each program map. *(Addresses: no visibility into program-map feasibility.)*
- Example: for the Accounting pathway, flag that Accounting 1A and a required Math/English course are scheduled at the same time in the fall, preventing progression. *(Addresses: cross-department conflicts locking students out.)*
- Index from the published schedule of classes and the ~80 program-map PDFs, supplemented by historic course-level enrollment counts. *(Addresses: siloed, manual data sources.)*
- Optional per-department deconfliction insight reports, including which scheduler to contact to resolve top conflicts. *(Addresses: no coordination across departments.)*
- Should extend into a dynamic scheduler-facing coordination tool and scale to other CCC campuses using their equivalent program-mapper tools.

## Data Availability
- Published schedule of classes (college website) and program maps (~80 static PDFs via Program Mapper); underlying PDFs to be sourced.
- Consolidated ("giant") scheduling spreadsheet aggregated from department submissions to the Office of Instruction.
- Historic course-level enrollment data (enrolled counts, waitlists) from internal portals; enrolled counts preferred over waitlist as impact signal.
- Human resources: SMEs in the Office of Instruction, lead scheduler, and part-time schedulers in each division.
- Known gaps: no accurate major-declaration data (cannot optimize by major volume); enrollment exports include confidential fields requiring anonymization; Program Mapper has no API (static PDFs only).

> **Note:** Sample/synthetic data was reported as not available; sources above are to be provided pending access and de-identification.