export default function ProgramDetails({ program, onClose }) {
  if (!program) return null

  const quarterLabel = { fall: 'Fall', winter: 'Winter', spring: 'Spring' }
  const yearLabel = { year_1: 'First Year', year_2: 'Second Year' }

  // Collect all unique prerequisite-like notes
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

        {/* Pathway Timeline */}
        <div className="pathway-timeline">
          {Object.entries(yearLabel).map(([yearKey, yearName]) => {
            const yearData = program.years[yearKey]
            const hasContent = Object.values(yearData).some(
              (q) => q.required_courses.length > 0 || q.additional_courses.length > 0
            )
            if (!hasContent) return null

            return (
              <div key={yearKey} className="year-section">
                {program.pathwayYears > 1 && (
                  <h3 className="year-heading">{yearName}</h3>
                )}
                <div className="quarters-grid">
                  {Object.entries(quarterLabel).map(([qKey, qName]) => {
                    const quarter = yearData[qKey]
                    const hasCourses = quarter.required_courses.length > 0 || quarter.additional_courses.length > 0
                    if (!hasCourses) return <div key={qKey} className="quarter-block empty" />

                    return (
                      <div key={qKey} className="quarter-block">
                        <h4 className="quarter-heading">{qName}</h4>
                        {quarter.required_courses.length > 0 && (
                          <ul className="course-list required">
                            {quarter.required_courses.map((course, i) => (
                              <li key={i} className="course-item">{course}</li>
                            ))}
                          </ul>
                        )}
                        {quarter.additional_courses.length > 0 && (
                          <div className="additional-section">
                            <span className="additional-label">Additional:</span>
                            <ul className="course-list additional">
                              {quarter.additional_courses.map((course, i) => (
                                <li key={i} className="course-item additional">{course}</li>
                              ))}
                            </ul>
                          </div>
                        )}
                      </div>
                    )
                  })}
                </div>
              </div>
            )
          })}
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
