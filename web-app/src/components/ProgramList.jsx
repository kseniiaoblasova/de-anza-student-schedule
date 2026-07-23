import ProgramCard from './ProgramCard'

export default function ProgramList({ programs, onSelectProgram }) {
  if (programs.length === 0) {
    return (
      <div className="empty-state">
        <svg viewBox="0 0 24 24" width="48" height="48" fill="none" stroke="currentColor" strokeWidth="1.5">
          <circle cx="11" cy="11" r="8" />
          <path d="m21 21-4.35-4.35" />
          <path d="M8 11h6" />
        </svg>
        <h3>No programs found</h3>
        <p>Try adjusting your search terms or filters.</p>
      </div>
    )
  }

  return (
    <div className="program-list">
      <div className="list-header">
        <span className="result-count">
          {programs.length} program{programs.length !== 1 ? 's' : ''} found
        </span>
      </div>
      <div className="card-grid">
        {programs.map((program) => (
          <ProgramCard
            key={program.id}
            program={program}
            onClick={onSelectProgram}
          />
        ))}
      </div>
    </div>
  )
}
