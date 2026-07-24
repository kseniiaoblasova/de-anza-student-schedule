---
name: schedule-conflict-analysis
description: >
  Analysis of scheduling conflicts between classes at De Anza College, organized by
  pathway, by village (department group), by term, by credential type, and by course
  pair. Documents the methodology, real findings from the data, and multiple analysis
  techniques. This is the analytical foundation — visualization is a separate task.
---

# Schedule Conflict Analysis — De Anza Guided Pathways

## Summary of Findings

We analyzed **235 program pathways** across **983 pathway-quarter combinations**,
comparing every cross-course section pair for meeting-time overlap.

| Metric | Value |
|--------|-------|
| Pathways analyzed | 235 |
| Pathway-quarters analyzed | 983 |
| Quarters WITH at least one conflict | 442 (45.0%) |
| Quarters with zero conflicts | 541 (55.0%) |
| Total section pairs evaluated | 158,783 |
| Total conflicting section pairs | 10,173 |
| **Overall conflict rate** | **6.41%** |

**Key takeaways:**
- Nearly half (45%) of all pathway-quarters have at least one scheduling conflict
- The overall rate of 6.41% means ~1 in 16 section combinations clash
- **COMM 1 × COMM 10** is the single worst course pair — conflicts across 98 pathways
- **Health and Life Sciences** village has the highest conflict rate (10.2%)
- **Fall terms** (202622, 202722) have the highest conflict density (~9.1% and 6.9%)
- Automotive/noncredit programs show 100% conflict rates (few sections, all overlap)
- Transfer-prep programs have 10.4% conflict rate — worst among credential types

---

## Methodology

### What is a "conflict"?

Two class sections conflict when a student cannot physically attend both:
1. They are sections of **different courses** (same-course pairs skipped)
2. They share at least one **meeting day** (M, T, W, R, F, S)
3. Their **time intervals strictly overlap**: `start_A < end_B AND start_B < end_A`

- Back-to-back classes do NOT conflict
- TBA/async sections (no fixed time) never conflict with anything
- Same-course pairs are irrelevant (student picks one section)

### How the pipeline works

```
For each of 235 pathways:
  For each quarter with courses (up to 6: year_1/year_2 × fall/winter/spring):
    1. Take normalized course list (e.g. ["CIS 22A", "MATH 1A", "ENGL 1A"])
    2. Map (year, quarter) → real schedule term_code
    3. Pull ALL sections of each course from deanza-class-schedule
    4. Send to conflict engine: compare every cross-course section pair
    5. Store: courses resolved, courses missing, pairs evaluated,
       conflicts found, conflict percentage, full pair detail
```

### Key metric: `conflict_percentage`

`conflict_percentage = conflict_count / pairs_evaluated × 100`

This is the % of **section-pair combinations** that clash — not the probability a
student is blocked. A student only needs ONE compatible combination.

| Range | Severity | Meaning |
|-------|----------|---------|
| 0% | None | All section combinations work |
| 1–10% | Low | Most combinations work; few specific clashes |
| 11–25% | Moderate | Limited scheduling flexibility |
| 26–50% | High | Many combinations fail |
| 51–100% | Critical | Most/all combinations clash; likely blocked |

### Term mapping

| Pathway quarter | term_code | Real schedule |
|---|---|---|
| Year 1 Fall | 202622 | Fall 2025 |
| Year 1 Winter | 202632 | Winter 2026 |
| Year 1 Spring | 202642 | Spring 2026 |
| Year 2 Fall | 202722 | Fall 2026 |
| Year 2 Winter | 202732 | Winter 2027 |
| Year 2 Spring | 202742 | Spring 2027 |

---

## Analysis 1: Conflicts by Village (Department Group)

Villages are De Anza's organizational groupings for related programs.

| Village | Pathways | Conflict Rate | Total Conflicts |
|---------|----------|---------------|-----------------|
| Health and Life Sciences | 32 | **10.2%** | 3,014 |
| Physical Sciences and Technology | 92 | **7.6%** | 2,617 |
| Artistic Expression | 30 | **5.6%** | 1,534 |
| Language and Communications | 3 | 5.0% | 105 |
| Language and Communication | 31 | 4.7% | 712 |
| Social Sciences and Humanities | 44 | **4.4%** | 2,079 |
| Business & Finance + PST (joint) | 1 | 4.8% | 46 |

**Findings:**
- **Health and Life Sciences** has the highest conflict rate (10.2%) — biology,
  nursing, and environmental science programs require many concurrent lab/lecture
  courses that cluster in the same morning time blocks
- **Physical Sciences and Technology** is second (7.6%) but has BY FAR the most
  pathways (92), so its 2,617 conflict pairs affect the most students
- **Artistic Expression** (5.6%) — studio/lab courses are long 3-4 hour blocks
  that overlap with everything in the same time range
- **Social Sciences** has a moderate rate (4.4%) but high absolute count (2,079)
  because it has 44 pathways all sharing the same COMM/PHIL/PSYC courses

**Why this matters for schedulers:**
- A scheduler in Health & Life Sciences should know their term schedules produce
  conflicts across 32 programs at a 10% rate — higher than any other group
- The COMM department (Language and Communication) contributes to conflicts across
  the entire college because COMM 1, COMM 10, and PHIL courses are required by
  nearly every transfer pathway

---

## Analysis 2: Conflicts by Term

| Term Code | Quarter | Pathways | Conflicts | Conflict Rate |
|-----------|---------|----------|-----------|---------------|
| 202622 | Fall 2025 (Y1) | 224 | 2,124 | **9.1%** |
| 202632 | Winter 2026 (Y1) | 227 | 4,166 | **5.7%** |
| 202642 | Spring 2026 (Y1) | 203 | 1,931 | **5.8%** |
| 202722 | Fall 2026 (Y2) | 130 | 916 | **6.9%** |
| 202732 | Winter 2027 (Y2) | 110 | 727 | **6.3%** |
| 202742 | Spring 2027 (Y2) | 89 | 309 | **6.8%** |

**Findings:**
- **Fall 2025 (202622)** is the worst term at 9.1% — this is Year 1 Fall, when
  students begin their pathways and take gateway courses simultaneously
- **Winter 2026** has the highest absolute conflict count (4,166) but a lower rate
  (5.7%) because there are more section pairs evaluated (more courses offered)
- Year 2 terms have fewer pathways analyzed (some programs are 1-year certificates)
  but maintain 6-7% conflict rates
- Fall consistently runs higher than Winter/Spring (likely because of enrollment
  pressure concentrating popular sections in prime time slots)

**Why this matters:**
- Schedulers building the Fall schedule should know it's the most conflict-prone
- The sheer volume in Winter (4,166 conflicts) means many students face scheduling
  friction even though the rate is moderate

---

## Analysis 3: Top Conflicting Course Pairs

The highest-leverage analysis — identifies which specific course pairs clash across
the most pathways. Fixing ONE of these fixes conflicts for dozens of programs.

| Rank | Course Pair | Pathways Affected | Section-Pair Conflicts |
|------|-------------|-------------------|------------------------|
| 1 | **COMM 1 × COMM 10** | **98** | 1,859 |
| 2 | COMM 1 × COMM 15 | 54 | 173 |
| 3 | COMM 1 × COMM 8 | 54 | 93 |
| 4 | COMM 1 × PHIL 3 | 52 | 276 |
| 5 | COMM 1 × COMM 9 | 52 | 52 |
| 6 | COMM 1 × MATH 44 | 52 | 96 |
| 7 | COMM 10 × COMM 15 | 52 | 124 |
| 8 | COMM 10 × PHIL 3 | 52 | 56 |
| 9 | COMM 1 × PHIL 7 | 51 | 223 |
| 10 | COMM 10 × PHIL 7 | 51 | 51 |
| 11 | COMM 8 × MATH 44 | 50 | 50 |
| 12 | PHIL 3 × PHIL 7 | 36 | 36 |
| 13 | COMM 10 × COMM 8 | 17 | 34 |
| 14 | COMM 10 × MATH 44 | 16 | 18 |
| 15 | COMM 15 × PHIL 7 | 14 | 14 |
| 16 | ESL 5 × MATH 1A | 14 | 112 |
| 17 | COMM 7 × JOUR 2 | 13 | 24 |
| 18 | ANTH 2 × COMM 7 | 12 | 12 |
| 19 | CIS 22A × ESL 5 | 9 | 9 |
| 20 | PSYC 1 × SOC 1 | 9 | 34 |

**Critical findings:**

1. **COMM and PHIL dominate the conflict landscape.** The top 15 pairs ALL involve
   COMM 1, COMM 10, COMM 15, COMM 8, COMM 9, PHIL 3, PHIL 7, or MATH 44. These
   are the oral communication and critical thinking GE requirements that nearly
   every transfer pathway includes.

2. **COMM 1 × COMM 10 is the #1 systemic bottleneck.** It conflicts across 98 of
   235 pathways (42% of all programs!) with 1,859 section-pair clashes. This single
   pair likely affects thousands of students per year.

3. **The fix is concentrated.** Adjusting COMM 1 and COMM 10 section times (or
   adding async sections) could eliminate conflicts for ~100 pathways simultaneously.
   This is a scheduling coordination issue within ONE department (Language & Communication).

4. **ESL 5 × MATH 1A** (rank 16) — important because these are prerequisite/gateway
   courses for non-native English speakers entering STEM. 14 pathways affected, 112
   section-pair clashes. This is a cross-department issue (Language vs Math).

5. **PSYC 1 × SOC 1** (rank 20) — common GE pair across Social Sciences programs.
   Only 9 pathways affected but 34 section-pair clashes suggest limited time diversity.

---

## Analysis 4: Conflicts by Credential Type

| Credential Type | Pathways | Conflict Rate | Total Conflicts |
|---|---|---|---|
| Noncredit Certificate of Completion | 29 | **26.0%** | 19 |
| Associate in Science for Transfer (AS-T) | 6 | **10.5%** | 1,175 |
| Transfer Preparation | 22 | **10.4%** | 3,634 |
| Associate in Science (AS) | 17 | 5.6% | 1,161 |
| Associate in Arts (AA) | 38 | 5.1% | 2,666 |
| Certificate of Achievement Advanced (COA-A) | 44 | 5.0% | 204 |
| Associate in Arts for Transfer (AA-T) | 16 | 3.8% | 1,066 |
| Certificate of Achievement (COA) | 62 | 3.3% | 248 |
| Bachelor of Science (BS) | 1 | 0.0% | 0 |

**Findings:**

- **Noncredit certificates** have 26% rate but only 19 actual conflicts — these are
  small programs (mostly automotive) with very few sections that ALL overlap
- **AS-T and Transfer Prep** programs are the real concern: 10.4-10.5% conflict rate
  with thousands of actual conflict pairs affecting students pursuing 4-year transfer
- **COA certificates** have the lowest rate (3.3%) — shorter programs with fewer
  concurrent courses per quarter
- The **sole BS program** has zero conflicts (likely well-scheduled as a flagship)

**Pattern:** Programs requiring MORE concurrent courses per quarter (transfer degrees)
have higher conflict rates because more pairs exist to potentially clash. Certificates
requiring 1-2 courses per quarter have few or no conflicts by construction.

---

## Analysis 5: Most-Conflicted Pathways (Top 15)

| Conflict % | Program | Village |
|---|---|---|
| 100% | Advanced Engine Performance Technology (NC) | Physical Sciences & Technology |
| 100% | Automotive Technician: Advanced Engine Performance | Physical Sciences & Technology |
| 100% | Automotive Technician: Advanced Automotive Technology | Physical Sciences & Technology |
| 100% | Alternative Fuels Technology (NC) | Physical Sciences & Technology |
| 100% | Automotive Technician: Autonomous & Electric Vehicle | Physical Sciences & Technology |
| 100% | Intermediate Engine Performance Technology (NC) | Physical Sciences & Technology |
| 100% | Basic Engine Performance Technology (NC) | Physical Sciences & Technology |
| 100% | Automotive Technician: Automotive Chassis Technology | Physical Sciences & Technology |
| 100% | Automotive Chassis Technology (NC) | Physical Sciences & Technology |
| 100% | Automotive Technician: Automotive Powertrain | Physical Sciences & Technology |
| 100% | Autonomous & Electric Vehicle Technician Level 2 (NC) | Physical Sciences & Technology |
| 100% | Project Management Practitioner (NC) | Physical Sciences & Technology |
| 100% | Automotive Technician: Basic Engine Performance | Physical Sciences & Technology |
| 50% | ESL Intermediate Level (NC) | Language & Communication |

**Findings:**

- **ALL 100% conflict pathways are Automotive or technical noncredit certificates.**
  These programs have very few sections (often 1-2 per course) that all meet at the
  same time block. Every possible combination clashes.
- The auto programs are clustered in one department — this is a fixable scheduling
  decision (stagger the few sections across different time slots)
- **ESL Intermediate** at 50% — ESL courses have limited section options and
  conflict with gateway math/english courses required in the same quarter
- Transfer degree programs (CS, Engineering, Biology) likely appear in the 5-15%
  range — moderate but affecting far more students due to enrollment

---

## Analysis 6: Most Frequently Missing Courses

Courses that appear in pathway requirements but have NO sections in the scheduled term:

| Missing In (quarters) | Course | Explanation |
|---|---|---|
| 144 | ENGL C1000 | Statewide Cal-GETC code; schedule uses EWRT 1A |
| 144 | EWRT 1A | Listed alongside ENGL C1000 as alias; one resolves |
| 101 | COMM C1000 | Statewide code; schedule uses COMM 1 |
| 76 | STAT C1000 | Statewide code; schedule uses MATH 10 |
| 75 | MATH 10 | May be offered under different numbering in some terms |
| 61 | EWRT 2 | Not offered in all terms |
| 53 | PHIL 4 | Not offered in all terms |
| 52 | MATH 17 | Not offered in all terms |
| 46 | ENGL C1001 | Statewide code; schedule uses EWRT 2 |
| 17 | PSYC C1000 | Statewide code |
| 15 | ENGL 1001 | Alias issue |
| 15 | INTL 5 | Rarely offered course |
| 14 | ADMJ 55 | Not offered in loaded terms |
| 14 | ADMJ 64X | Specialized elective, rarely offered |
| 14 | ADMJ 64Y | Specialized elective, rarely offered |

**Findings:**

- The top 4 are all **statewide Cal-GETC renaming issues** — pathways reference
  the new statewide codes (C1000) while the schedule still uses legacy De Anza codes.
  These aren't real availability gaps; the course IS offered under its old name.
- **EWRT 1A appearing as "missing"** is misleading — it resolves under ENGL C1000
  in many pathways. This is an alias duplication, not a scheduling gap.
- **PHIL 4, MATH 17, EWRT 2** — these are real availability concerns. Courses
  required by many pathways but not offered every quarter.
- **ADMJ courses** — specialized criminal justice electives not offered frequently.

**Impact:** Missing courses can't be conflict-analyzed. They represent a DIFFERENT
problem (availability gap vs time conflict) but surface them alongside conflict data
because a student with 2 available courses and 1 missing course faces both issues.

---

## Analysis 7: Cross-Department Conflict Patterns

Many conflicts involve courses from different departments, requiring coordination
between separate scheduling teams to fix.

**From the top 20 pairs:**

| Pair | Departments involved | Fix requires |
|---|---|---|
| COMM 1 × MATH 44 | Language & Communication + Math | Cross-dept coordination |
| ESL 5 × MATH 1A | Language + Math | Cross-dept coordination |
| CIS 22A × ESL 5 | Computer Science + Language | Cross-dept coordination |
| PSYC 1 × SOC 1 | Psychology + Sociology | Within Social Sciences |
| ANTH 2 × COMM 7 | Anthropology + Communication | Cross-dept coordination |
| COMM 7 × JOUR 2 | Communication + Journalism | Within Language & Comm |

**Within-department conflicts (easier to fix):**
- COMM 1 × COMM 10, COMM 1 × COMM 15, COMM 1 × COMM 8, COMM 1 × COMM 9
- PHIL 3 × PHIL 7
- All automotive courses

**Pattern:** The hardest conflicts to resolve are cross-department because no single
scheduler has authority to move both sides. The top pair (COMM 1 × COMM 10) is
within-department — theoretically fixable by one scheduling decision.

---

## Analysis 8: Conflict Concentration

Of 983 pathway-quarters:
- **541 (55%)** have zero conflicts — perfectly schedulable
- **442 (45%)** have at least one conflict
- The 10,173 conflict pairs are NOT evenly distributed — they concentrate in
  specific quarters of specific programs

**Concentration pattern:**
- A small number of "gateway" course combinations (COMM + PHIL + MATH) drive the
  majority of conflicts across many pathways
- Automotive programs account for 14 of the top 15 worst pathways (100% rate) but
  affect relatively few students
- The high-enrollment transfer pathways (CS, Biology, Business) have moderate rates
  (5-10%) but affect thousands of students

---

## Analysis Techniques Available

### Technique 1: Per-Pathway Drill-Down
Query `deanza-pathway-conflicts` by `pathway_id` to get all 6 quarters for one program.
Shows which quarter is the bottleneck, which courses are involved, what's missing.

### Technique 2: Per-Village Aggregation
Group all items by `village` field. Compare conflict rates across department groups.
Identifies which scheduling teams have the most work to do.

### Technique 3: Per-Term Comparison
Group by `term_code`. Identifies whether the problem is seasonal (Fall worse than
Winter) or consistent. Uses GSI `term-index` for efficient queries.

### Technique 4: Course-Pair Frequency
Iterate all `conflicts[]` lists, extract `(course_a, course_b)` pairs, count distinct
pathways affected. Reveals systemic bottlenecks vs one-off issues.

### Technique 5: Credential-Type Stratification
Group by `credential_type`. Shows whether transfer degrees are more impacted than
certificates (they are — 10.5% vs 3.3%).

### Technique 6: Course Load Correlation
Group by `course_count` (courses per quarter). Determines whether heavier quarters
have disproportionately more conflicts or if the schedule scales well.

### Technique 7: Missing Course Impact
Count frequency of each course in `missing_courses[]` across all items. Separates
"not offered" gaps from "offered but clashing" time conflicts.

### Technique 8: Cross-Department Analysis
For each conflict pair, check if the two courses belong to different subjects
(department proxy). Cross-dept conflicts need escalation; within-dept are easier.

### Technique 9: Severity Tiers
Classify each pathway-quarter into severity tiers (None/Low/Moderate/High/Critical)
based on conflict_percentage. Provides actionable prioritization.

---

## How to Run This Analysis

```bash
# Requires: Python 3.10+, boto3, python-dotenv, valid AWS creds in .env

# Full analysis (prints report + writes JSON)
C:\Python310\python.exe scripts/pathway_conflicts/analyze_conflicts.py --output analysis_report.json

# Just the console report
C:\Python310\python.exe scripts/pathway_conflicts/analyze_conflicts.py

# If conflict data is stale, rebuild it first:
C:\Python310\python.exe scripts/pathway_conflicts/build_conflicts.py --apply
```

---

## Data Sources

| Table | Records | Role |
|-------|---------|------|
| `deanza-pathway-conflicts` | 983 | Precomputed conflict results (this analysis reads from here) |
| `deanza-pathways-normalized` | 238 | Cleaned pathway course lists (input to pipeline) |
| `deanza-class-schedule` | 25,811 | All class sections, 2025-26 and 2026-27 (input to pipeline) |
| `deanza-pathways` | 238 | Original pathway maps, verbose text (source of truth) |

---

## Conflict Item Structure (what each record contains)

```
pathway_id:          "2025 CS all.pdf#3"        (unique pathway ID)
quarter_key:         "year_1#fall"              (which quarter)
term_code:           "202622"                   (real schedule term analyzed)
program_name:        "Computer Science -- AS-T"
village:             "Physical Sciences and Technology"
credential_type:     "Associate in Science for Transfer (AS-T)"
resolved_courses:    ["CIS 22A", "MATH 1A", "ENGL 1A"]
missing_courses:     ["ENGL C1000"]
course_count:        3                          (resolved count)
section_count:       47                         (total sections across all courses)
pairs_evaluated:     198                        (cross-course section pairs compared)
conflict_count:      14                         (pairs that overlap)
conflict_percentage: 7.07                       (14/198 × 100)
conflicts: [                                    (full detail of each clash)
  { course_a, crn_a, course_b, crn_b, overlap: {days, time_a, time_b}, meta_a, meta_b }
]
```

---

## Limitations

1. **Section-pair level, not feasibility.** We count clashing combinations, not
   whether a student can build ONE clash-free schedule. Even at 30% rate,
   compatible combinations may exist.
2. **No enrollment weighting.** A conflict in a 400-seat course affects more
   students than one in a 25-seat seminar. Both count equally here.
3. **~17% of pathway courses don't resolve to schedule sections.** Mostly
   statewide C1000 codes and rarely-offered electives.
4. **Year 2 uses a future schedule** that may change before students reach it.
5. **Aliases counted separately.** ENGL C1000 and EWRT 1A are distinct courses
   in the data; one usually resolves and the other is "missing."

---

## Related Documentation

| Document | Covers |
|----------|--------|
| `pathway-conflicts.md` | Pipeline: how conflicts are computed and stored |
| `schedule-conflicts.md` | Lambda engine: overlap rules, input/output contracts |
| `course-pairing.md` | Normalization: how pathway codes map to schedule codes |
| `dynamodb.md` | Table schemas, keys, access patterns |
| `backend-architecture.md` | End-to-end system overview |
