import { useState, useEffect } from 'react'
import { PLAN_API_URL, TERMS } from '../config'

export default function ProgramDetails({ program, onClose }) {
  if (!program) return null

  // Planner state: chosen term, the set of selected course codes, and the
  // async request lifecycle (loading / error / result) for the conflict check.
  const [termCode, setTermCode] = useState('')
  const [selected, setSelected] = useState(() => new Set())
  const [status, setStatus] = useState('idle') // idle | loading | done | error
  const [result, setResult] = useState(null)
  const [error, setError] = useState('')

  // Reset the planner whenever a different pathway opens (the component stays
  // mounted across selections, so local state would otherwise leak over).
  useEffect(() => {
    setTermCode('')
    setSelected(new Set())
    setStatus('idle')
    setResult(null)
    setError('')
  }, [program.pathwayId])

  const toggleCourse = (code) => {
    setSelected((prev) => {
      const next = new Set(prev)
      next.has(code) ? next.delete(code) : next.add(code)
      return next
    })
    // A changed selection invalidates any shown result.
    setStatus('idle')
    setResult(null)
  }

  const courseCodes = program.courseCodes || []
  const canCheck = termCode && selected.size >= 2 && status !== 'loading'

  // One chip, shared by the "recommended" and "all courses" rows so a click in
  // either toggles the same selection.
  const renderChip = (code) => (
    <button
      key={code}
      type="button"
      className={`chip${selected.has(code) ? ' selected' : ''}`}
      aria-pressed={selected.has(code)}
      onClick={() => toggleCourse(code)}
    >
      {code}
    </button>
  )

  // Call the keyless planner endpoint with the chosen term + courses.
  const checkSchedule = async () => {
    setStatus('loading')
    setError('')
    setResult(null)
    try {
      const resp = await fetch(PLAN_API_URL, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ term_code: termCode, courses: [...selected] }),
      })
      const body = await resp.json()
      if (!resp.ok) throw new Error(body.error || `Request failed (${resp.status})`)
      setResult(body)
      setStatus('done')
    } catch (e) {
      setError(e.message || 'Something went wrong contacting the planner.')
      setStatus('error')
    }
  }

  // Collect prerequisite-like notes for the context section at the bottom.
  const prerequisites = program.additionalNotes.filter(
    (note) =>
      note.toLowerCase().includes('prerequisite') ||
      note.toLowerCase().includes('placement test') ||
      note.toLowerCase().includes('must also take')
  )

  const selectedTerm = TERMS.find((t) => t.code === termCode)
  const termLabel = selectedTerm?.label || ''

  // Courses the program map recommends for the quarter this term maps to — a
  // subset of the full list, from the same precomputed conflict data. Selecting
  // one toggles the shared selection, so it also lights up in the full list.
  const recommendedCourses = (() => {
    const q = selectedTerm && program.conflictsByQuarter?.[selectedTerm.quarterKey]
    if (!q) return []
    return [...new Set([...(q.courses || []), ...(q.missing_courses || [])])].sort()
  })()

  return (
    <div className="details-overlay" onClick={onClose}>
      <div className="details-panel" onClick={(e) => e.stopPropagation()}>
        <button className="close-btn" onClick={onClose} aria-label="Close details">
          <svg viewBox="0 0 24 24" width="24" height="24" fill="none" stroke="currentColor" strokeWidth="2">
            <line x1="18" y1="6" x2="6" y2="18" />
            <line x1="6" y1="6" x2="18" y2="18" />
          </svg>
        </button>

        <div className="details-header">
          <span className="details-credential">{program.credentialType}</span>
          <h2 className="details-title">{program.programName}</h2>
          <div className="details-meta">
            <span>{program.village}</span>
            <span>&middot;</span>
            <span>{program.totalRequiredCourses} required courses</span>
            {program.totalAdditionalCourses > 0 && (
              <>
                <span>&middot;</span>
                <span>{program.totalAdditionalCourses} additional/elective</span>
              </>
            )}
          </div>
        </div>

        {/* ===== Interactive planner ===== */}
        <div className="planner">
          <p className="planner-intro">
            Pick a term and the courses you want to take. We'll check every pair of
            offered sections and show which ones fit together and which overlap.
          </p>

          {/* Step 1 — term */}
          <div className="planner-step">
            <label htmlFor="term-select" className="planner-label">1. Choose a term</label>
            <select
              id="term-select"
              className="quarter-select"
              value={termCode}
              onChange={(e) => { setTermCode(e.target.value); setStatus('idle'); setResult(null) }}
            >
              <option value="">— Select a term —</option>
              {TERMS.map((t) => (
                <option key={t.code} value={t.code}>{t.label}</option>
              ))}
            </select>
          </div>

          {/* Recommended for the quarter this term maps to (program map). Shares
              the selection with the full list below — a click here lights up there. */}
          {termCode && recommendedCourses.length > 0 && (
            <div className="planner-step">
              <label className="planner-label recommended-label">
                Recommended this quarter <span className="recommended-hint">from the {program.shortName} map</span>
              </label>
              <div className="course-chips">
                {recommendedCourses.map(renderChip)}
              </div>
            </div>
          )}

          {/* Step 2 — full course list (chips) */}
          <div className="planner-step">
            <label className="planner-label">
              2. Choose courses{selected.size > 0 ? ` (${selected.size} selected)` : ''}
            </label>
            {courseCodes.length === 0 ? (
              <p className="conflicts-note muted">
                No course codes are available for this pathway.
              </p>
            ) : (
              <div className="course-chips">
                {courseCodes.map(renderChip)}
              </div>
            )}
          </div>

          {/* Step 3 — run */}
          <div className="planner-step">
            <button className="check-btn" disabled={!canCheck} onClick={checkSchedule}>
              {status === 'loading' ? 'Checking…' : 'Check my schedule'}
            </button>
            {selected.size < 2 && (
              <span className="planner-hint">Pick at least two courses to compare.</span>
            )}
          </div>

          {/* Results */}
          {status === 'error' && (
            <p className="conflicts-note error-note">{error}</p>
          )}

          {status === 'done' && result && (
            <PlanResult result={result} termLabel={termLabel} />
          )}
        </div>

        {/* Prerequisites */}
        {prerequisites.length > 0 && (
          <div className="details-section">
            <h3>Prerequisites &amp; Placement</h3>
            <ul className="notes-list">
              {prerequisites.map((note, i) => (
                <li key={i}>{note}</li>
              ))}
            </ul>
          </div>
        )}

        {/* Additional Notes */}
        {program.additionalNotes.length > 0 && (
          <div className="details-section">
            <h3>Additional Notes</h3>
            <ul className="notes-list">
              {program.additionalNotes
                .filter((n) => !prerequisites.includes(n))
                .map((note, i) => (
                  <li key={i}>{note}</li>
                ))}
            </ul>
          </div>
        )}

        <div className="details-footer">
          <span className="source-info">
            Source: {program.sourceFile} (page {program.pageNumber})
          </span>
        </div>
      </div>
    </div>
  )
}

/** One side of a section pair: course code + CRN + section number. */
function PairSide({ course, crn, meta }) {
  return (
    <span className="conflict-course">
      {course}{' '}
      <span className="conflict-crn">
        CRN {crn}{meta?.section ? ` · sec ${meta.section}` : ''}
      </span>
    </span>
  )
}

/** The student-facing result: headline verdict, then the two pair lists. */
function PlanResult({ result, termLabel }) {
  const {
    offered_courses = [], not_offered_courses = [], section_count = 0,
    pairs_evaluated = 0, overlap_count = 0, overlap_percentage = 0,
    overlaps = [], clear = [],
  } = result

  // No comparison possible — fewer than two courses actually have sections.
  if (pairs_evaluated === 0) {
    return (
      <div className="plan-result">
        <p className="conflicts-note muted">
          Not enough offered courses to compare in {termLabel}. At least two of your
          selected courses need scheduled sections this term.
        </p>
        {not_offered_courses.length > 0 && (
          <p className="conflicts-missing muted">
            Not offered this term: {not_offered_courses.join(', ')}
          </p>
        )}
      </div>
    )
  }

  const clean = overlap_count === 0

  return (
    <div className="plan-result">
      {/* Headline verdict with the overlap percentage. */}
      <div className={`plan-verdict ${clean ? 'ok' : 'warn'}`}>
        <span className="plan-pct">{overlap_percentage}%</span>
        <span className="plan-verdict-text">
          {clean
            ? `All ${pairs_evaluated} section pairings fit together in ${termLabel}.`
            : `${overlap_count} of ${pairs_evaluated} section pairings overlap in ${termLabel}.`}
        </span>
      </div>

      <p className="plan-subline">
        {offered_courses.length} course{offered_courses.length !== 1 ? 's' : ''} offered
        {' · '}{section_count} sections checked
      </p>

      {/* Overlapping pairs — the ones a student can't take together. */}
      {overlaps.length > 0 && (
        <div className="plan-group">
          <h4 className="quarter-courses-heading conflicts-heading">
            Can't take together ({overlaps.length})
          </h4>
          <ul className="conflict-list">
            {overlaps.map((c, i) => (
              <li key={i} className="conflict-item">
                <div className="conflict-pair">
                  <PairSide course={c.course_a} crn={c.crn_a} meta={c.meta_a} />
                  <span className="conflict-x">&times;</span>
                  <PairSide course={c.course_b} crn={c.crn_b} meta={c.meta_b} />
                </div>
                {c.overlap_detail && (
                  <div className="conflict-overlap">
                    Overlaps {(c.overlap_detail.days || []).join('/')} &middot;{' '}
                    {c.overlap_detail.time_a}
                    {c.overlap_detail.time_b && c.overlap_detail.time_b !== c.overlap_detail.time_a
                      ? ` / ${c.overlap_detail.time_b}`
                      : ''}
                  </div>
                )}
              </li>
            ))}
          </ul>
        </div>
      )}

      {/* Compatible pairs — collapsed by default to keep the focus on clashes. */}
      {clear.length > 0 && (
        <details className="plan-clear">
          <summary>Fit together ({clear.length})</summary>
          <ul className="conflict-list">
            {clear.map((c, i) => (
              <li key={i} className="conflict-item ok">
                <div className="conflict-pair">
                  <PairSide course={c.course_a} crn={c.crn_a} meta={c.meta_a} />
                  <span className="conflict-check">✓</span>
                  <PairSide course={c.course_b} crn={c.crn_b} meta={c.meta_b} />
                </div>
              </li>
            ))}
          </ul>
        </details>
      )}

      {/* Selected courses with no section this term. */}
      {not_offered_courses.length > 0 && (
        <p className="conflicts-missing muted">
          Not offered this term: {not_offered_courses.join(', ')}
        </p>
      )}
    </div>
  )
}
