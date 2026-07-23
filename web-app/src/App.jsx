import { useState, useMemo } from 'react'
import SearchFilter from './components/SearchFilter'
import ProgramList from './components/ProgramList'
import ProgramDetails from './components/ProgramDetails'
import ChatWidget from './components/ChatWidget'
import { pathwayData, metadata } from './data/pathways'

export default function App() {
  const [filters, setFilters] = useState({
    search: '',
    credentialType: '',
    village: '',
  })

  const [selectedProgram, setSelectedProgram] = useState(null)

  // Filter programs based on current filter state
  const filteredPrograms = useMemo(() => {
    return pathwayData.filter((program) => {
      // Search filter - matches program name, short name, or course names
      if (filters.search) {
        const query = filters.search.toLowerCase()
        const matchesName =
          program.programName.toLowerCase().includes(query) ||
          program.shortName.toLowerCase().includes(query)
        const matchesCourse = program.allRequiredCourses.some((c) =>
          c.toLowerCase().includes(query)
        )
        const matchesVillage = program.village.toLowerCase().includes(query)
        if (!matchesName && !matchesCourse && !matchesVillage) return false
      }

      // Credential type filter
      if (filters.credentialType && program.credentialType !== filters.credentialType) {
        return false
      }

      // Village/department filter
      if (filters.village && program.village !== filters.village) {
        return false
      }

      return true
    })
  }, [filters])

  const handleFilterChange = (key, value) => {
    setFilters((prev) => ({ ...prev, [key]: value }))
  }

  const handleSelectProgram = (program) => {
    setSelectedProgram(program)
    document.body.style.overflow = 'hidden'
  }

  const handleCloseDetails = () => {
    setSelectedProgram(null)
    document.body.style.overflow = ''
  }

  return (
    <div className="app">
      <header className="app-header">
        <div className="header-content">
          <div className="header-text">
            <h1>De Anza College — Pathway Explorer</h1>
            <p className="header-subtitle">
              {metadata.catalogYear} Program Pathways &middot; {metadata.totalPathways} programs
            </p>
          </div>
        </div>
      </header>

      <main className="app-main">
        <SearchFilter filters={filters} onFilterChange={handleFilterChange} />
        <ProgramList programs={filteredPrograms} onSelectProgram={handleSelectProgram} />
      </main>

      {selectedProgram && (
        <ProgramDetails program={selectedProgram} onClose={handleCloseDetails} />
      )}

      <ChatWidget />
    </div>
  )
}
