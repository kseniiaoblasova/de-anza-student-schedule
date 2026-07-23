export default function ProgramCard({ program, onClick }) {
  // Color coding by credential type — De Anza red & gold
  const getAccentColor = (type) => {
    if (type.includes('AS-T') || type.includes('AA-T')) return 'var(--da-red)'
    if (type.includes('Associate in Science')) return 'var(--da-red-light)'
    if (type.includes('Associate in Arts')) return '#b84545'
    if (type.includes('Advanced')) return 'var(--da-gold-dark)'
    if (type.includes('COA') || type.includes('Certificate of Achievement')) return 'var(--da-gold)'
    if (type.includes('Noncredit')) return 'var(--color-noncredit)'
    if (type.includes('Transfer')) return 'var(--da-red)'
    if (type.includes('Bachelor')) return 'var(--da-red-dark)'
    return 'var(--color-default)'
  }

  const accentColor = getAccentColor(program.credentialType)

  return (
    <div
      className="program-card"
      onClick={() => onClick(program)}
      style={{ borderTopColor: accentColor }}
      role="button"
      tabIndex={0}
      onKeyDown={(e) => { if (e.key === 'Enter') onClick(program) }}
      aria-label={`View details for ${program.shortName}`}
    >
      <div className="card-header">
        <span className="credential-badge" style={{ backgroundColor: accentColor }}>
          {program.credentialType}
        </span>
      </div>

      <h3 className="card-title">{program.shortName}</h3>

      <div className="card-meta">
        <span className="meta-item">
          <svg viewBox="0 0 24 24" width="14" height="14" fill="none" stroke="currentColor" strokeWidth="2">
            <path d="M2 3h6a4 4 0 0 1 4 4v14a3 3 0 0 0-3-3H2z" />
            <path d="M22 3h-6a4 4 0 0 0-4 4v14a3 3 0 0 1 3-3h7z" />
          </svg>
          {program.totalRequiredCourses} courses
        </span>
        <span className="meta-item">
          <svg viewBox="0 0 24 24" width="14" height="14" fill="none" stroke="currentColor" strokeWidth="2">
            <rect x="3" y="4" width="18" height="18" rx="2" ry="2" />
            <line x1="16" y1="2" x2="16" y2="6" />
            <line x1="8" y1="2" x2="8" y2="6" />
            <line x1="3" y1="10" x2="21" y2="10" />
          </svg>
          {program.pathwayYears}-year pathway
        </span>
      </div>

      <div className="card-village">{program.village}</div>

      {/* Schedule-conflict signal: hot-spot programs stand out in the grid.
          Only shown when the pathway has conflict analysis data. */}
      {program.hasConflictData && (
        <div className={`conflict-flag ${program.hasConflicts ? 'has-conflicts' : 'no-conflicts'}`}>
          {program.hasConflicts
            ? `${program.totalConflicts} time conflict${program.totalConflicts !== 1 ? 's' : ''}`
            : 'No time conflicts'}
        </div>
      )}
    </div>
  )
}
