import { villages, credentialTypes } from '../data/pathways'

export default function SearchFilter({ filters, onFilterChange }) {
  return (
    <div className="search-filter">
      <div className="search-bar">
        <svg className="search-icon" viewBox="0 0 24 24" width="20" height="20" fill="none" stroke="currentColor" strokeWidth="2">
          <circle cx="11" cy="11" r="8" />
          <path d="m21 21-4.35-4.35" />
        </svg>
        <input
          type="text"
          placeholder="Search programs by name or course..."
          value={filters.search}
          onChange={(e) => onFilterChange('search', e.target.value)}
          className="search-input"
        />
        {filters.search && (
          <button
            className="clear-btn"
            onClick={() => onFilterChange('search', '')}
            aria-label="Clear search"
          >
            &times;
          </button>
        )}
      </div>

      <div className="filter-row">
        <div className="filter-group">
          <label htmlFor="filter-credential">Degree Type</label>
          <select
            id="filter-credential"
            value={filters.credentialType}
            onChange={(e) => onFilterChange('credentialType', e.target.value)}
          >
            <option value="">All Degree Types</option>
            {credentialTypes.map((type) => (
              <option key={type} value={type}>{type}</option>
            ))}
          </select>
        </div>

        <div className="filter-group">
          <label htmlFor="filter-village">Department</label>
          <select
            id="filter-village"
            value={filters.village}
            onChange={(e) => onFilterChange('village', e.target.value)}
          >
            <option value="">All Departments</option>
            {villages.map((v) => (
              <option key={v} value={v}>{v}</option>
            ))}
          </select>
        </div>

        {(filters.credentialType || filters.village || filters.search) && (
          <button
            className="reset-filters-btn"
            onClick={() => {
              onFilterChange('search', '')
              onFilterChange('credentialType', '')
              onFilterChange('village', '')
            }}
          >
            Reset Filters
          </button>
        )}
      </div>
    </div>
  )
}
