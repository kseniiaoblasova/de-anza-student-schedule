import { useState } from 'react'

export default function ProgramDetails({ program, onClose }) {
  if (!program) return null

  const quarterLabel = { fall: 'Fall', winter: 'Winter', spring: 'Spring' }
  const yearLabel = { year_1: 'Year 1', year_2: 'Year 2' }

  // Build dropdown options: "Year 1 — Fall", "Year 1 — Winter", etc.
  const quarterOptions = []
  for (const [yearKey, yearName] of Object.entries(yearLabel)) {
    const yearData = program.years[yearKey]
    const yearHasContent = Object.values(yearData).some(
      (q) => q.required_courses.length > 0 || q.additional_courses.length > 0
    )
    if (!yearHasContent) continue

    for (const [qKey, qName] of Object.entries(quarterLabel)) {
      const quarter = yearData[qKey]
      if (quarter.required_courses.length > 0 || quarter.additional_courses.length > 0) {
        quarterOptions.push({ value: `${yearKey}|${qKey}`, label: `${yearName} — ${qName}`, yearKey, qKey })
      }
    }
  }

  const [selectedQuarter, setSelectedQuarter] = useState('')

  // Parse the selected value to get quarter data
  const selectedData = (() => {
    if (!selectedQuarter) return null
    const [yearKey, qKey] = selectedQuarter.split('|')
    return program.years[yearKey][qKey]
  })()

  // Collect prerequisite-like notes
  const prerequisites = program.additionalNotes.filter(
    (note) =>
      note.toLowerCase().includes('prerequisite') ||
      note.toLowerCase().includes('placement test') ||
      note.toLowerCase().includes('must also take')
  )

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

        {/* Quarter selector dropdown */}
        <div className="quarter-selector">
          <label htmlFor="quarter-select" className="quarter-selector-label">
            Select a quarter to view required courses
          </label>
          <select
            id="quarter-select"
            className="quarter-select"
            value={selectedQuarter}
            onChange={(e) => setSelectedQuarter(e.target.value)}
          >
            <option value="">— Choose a quarter —</option>
            {quarterOptions.map((opt) => (
              <option key={opt.value} value={opt.value}>{opt.label}</option>
            ))}
          </select>
        </div>

        {/* Show courses for the selected quarter */}
        {selectedData && (
          <div className="quarter-courses">
            {selectedData.required_courses.length > 0 && (
              <div className="quarter-courses-section">
                <h4 className="quarter-courses-heading">Required Courses</h4>
                <ul className="course-list required">
                  {selectedData.required_courses.map((course, i) => (
                    <li key={i} className="course-item">{course}</li>
                  ))}
                </ul>
              </div>
            )}
            {selectedData.additional_courses.length > 0 && (
              <div className="quarter-courses-section">
                <h4 className="quarter-courses-heading additional-heading">Additional / Elective</h4>
                <ul className="course-list additional">
                  {selectedData.additional_courses.map((course, i) => (
                    <li key={i} className="course-item additional">{course}</li>
                  ))}
                </ul>
              </div>
            )}
          </div>
        )}

        {/* Prompt when nothing selected */}
        {!selectedData && (
          <div className="quarter-placeholder">
            <p>Pick a quarter above to see what courses you need.</p>
          </div>
        )}

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
