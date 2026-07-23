/**
 * De Anza College Program Pathways Data
 * Source: 2025-2026 PDF pathway maps
 * This data will eventually come from Amazon Bedrock Knowledge Base
 */

import rawData from './deanza_pathways.json'
import conflictData from './pathway_conflicts.json'

/**
 * Count the actual number of distinct course requirements in a quarter's course list.
 *
 * The key insight: once a multi-line block starts (Complete..., GE Area..., or any line
 * ending open), ALL following lines are continuations UNLESS they match one of the
 * unambiguous "new requirement" patterns.
 */
function countDistinctCourses(courseLines) {
  if (!courseLines || courseLines.length === 0) return 0

  let count = 0
  let inListContext = false

  for (let i = 0; i < courseLines.length; i++) {
    const line = courseLines[i].trim()
    if (!line) continue

    if (inListContext) {
      // Only break out of context if this line is DEFINITELY a new requirement
      if (isDefinitelyNewRequirement(line)) {
        count++
        inListContext = startsMultiLineBlock(line)
      }
      // Otherwise stays as continuation — don't count
    } else {
      // Not in list context — this is a new requirement
      count++
      inListContext = startsMultiLineBlock(line)
    }
  }

  return count
}

/**
 * A line that DEFINITELY starts a new requirement, even within a list context.
 * These are unambiguous top-level starters that would never appear as list options.
 */
function isDefinitelyNewRequirement(line) {
  const lower = line.toLowerCase()

  // "Complete..." always starts a new requirement
  if (lower.startsWith('complete ')) return true

  // "GE Area..." always starts a new requirement
  if (/^ge area/i.test(line)) return true

  // "Option 1:", "Option 2:" = new requirement
  if (/^option \d/i.test(line)) return true

  // "Choose...", "Select..." = new requirement
  if (lower.startsWith('choose ') || lower.startsWith('select ')) return true

  // "Elective..." = new requirement
  if (lower.startsWith('elective ')) return true

  // "CRITICAL THINKING as required"
  if (lower.startsWith('critical thinking')) return true

  // "MATH as required", "PHYS 50 as required"
  if (/^[A-Z]{2,5}\s+(\d+[A-Z]?\s+)?as required/i.test(line)) return true

  // A clean standalone course code on its own line (e.g. "ARTS 2B", "CIS 22A", "MATH 1A")
  // Must be ONLY a course code with nothing else
  if (/^[A-Z]{2,5}\s+\d+[A-Z]?\s*$/.test(line)) return true

  // A course code with "(formerly...)" qualifier — self-contained entry
  // e.g. "ENGL C1000 (formerly EWRT 1A) or ESL 5 as required"
  if (/^[A-Z]{2,5}\s+[A-Z]?\d+/.test(line) &&
    line.includes('(formerly') &&
    !line.includes(';')) return true

  // A course with "-- six weeks" type annotation (auto programs)
  if (/^[A-Z]{2,5}\s+\d+[A-Z]?\s+--\s+/.test(line)) return true

  // A simple course code + short description with no list indicators
  // e.g. "PHYS 4A", "BIOL 6A" — but NOT "ARTS 2A, ARTS 2G or ARTS 2J"
  // Must: start with course code, no commas, no semicolons, no "or" with another code after
  if (/^[A-Z]{2,5}\s+\d+[A-Z]?\s/.test(line) &&
    !line.includes(',') && !line.includes(';') &&
    !/\sor\s+[A-Z]{2,5}\s+\d/.test(line)) {
    // But exclude things like "Science, complete one" or "Quarter Area: ARTS..."
    if (!/^(Science|Drawing|Painting|Ceramics|Sculpture|Digital|Photography|Color|Quarter)/i.test(line)) {
      return true
    }
  }

  return false
}

/**
 * Whether a line starts a multi-line block whose content may span following lines.
 */
function startsMultiLineBlock(line) {
  const lower = line.toLowerCase()

  // "Complete..." blocks always span multiple lines listing options
  if (lower.startsWith('complete ')) return true

  // "GE Area" requirements often have continuation lines
  if (/^ge area/i.test(line)) return true

  // Any line ending with colon, comma, semicolon, "or"
  if (line.endsWith(':') || line.endsWith(',') || line.endsWith(';') ||
    line.endsWith(' or')) return true

  // Lines ending with "(formerly" or "(formerly "
  if (line.endsWith('(formerly') || line.endsWith('(formerly ')) return true

  // Lines that end with an incomplete course prefix (e.g. "formerly COMM", "from List B")
  if (/\s[A-Z]{2,5}$/.test(line)) return true

  // "or Physical" / "or ESL" — clearly continues on next line
  if (/\s(or|and)\s+[A-Z]/.test(line) && !line.endsWith(')')) return true

  return false
}

/**
 * Count total distinct required courses across all quarters for a pathway
 */
function countTotalRequiredCourses(years) {
  let total = 0
  for (const year of ['year_1', 'year_2']) {
    for (const quarter of ['fall', 'winter', 'spring']) {
      total += countDistinctCourses(years[year][quarter].required_courses)
    }
  }
  return total
}

// Transform raw pathway data into app-friendly format
function transformPathway(pathway, index) {
  const allRequired = []
  const allAdditional = []

  for (const year of ['year_1', 'year_2']) {
    for (const quarter of ['fall', 'winter', 'spring']) {
      const q = pathway.years[year][quarter]
      allRequired.push(...q.required_courses)
      allAdditional.push(...q.additional_courses)
    }
  }

  // Extract a clean short name (before the credential type indicator)
  const separators = [' -- ', '--', ' - Associate', ' - Certificate', ' -Certificate', ' - Bachelor']
  let shortName = pathway.program_name
  for (const sep of separators) {
    if (shortName.includes(sep)) {
      shortName = shortName.split(sep)[0]
      break
    }
  }

  // Smart course count - counts actual distinct course requirements
  const totalRequiredCourses = countTotalRequiredCourses(pathway.years)

  // Determine pathway duration based on whether year 2 has any courses
  const year2HasCourses = ['fall', 'winter', 'spring'].some(
    (q) => pathway.years.year_2[q].required_courses.length > 0 ||
      pathway.years.year_2[q].additional_courses.length > 0
  )
  const pathwayYears = year2HasCourses ? 2 : 1

  // Join precomputed schedule conflicts by the backend's identity key
  // ("<source_file>#<page_number>"). conflictsByQuarter is keyed by quarter_key
  // ("year_1#fall"); totalConflicts rolls the section-pair clashes up for the card.
  const pathwayId = `${pathway.source_file}#${pathway.page_number}`
  const conflictsByQuarter = conflictData[pathwayId] || {}
  const quarterKeys = Object.keys(conflictsByQuarter)
  const totalConflicts = quarterKeys.reduce(
    (sum, k) => sum + (conflictsByQuarter[k].conflict_count || 0),
    0
  )

  return {
    id: index + 1,
    programName: pathway.program_name,
    shortName: shortName.trim(),
    credentialType: pathway.credential_type,
    village: pathway.village,
    pathwayYears,
    years: pathway.years,
    totalRequiredCourses,
    totalAdditionalCourses: allAdditional.length,
    allRequiredCourses: allRequired,
    allAdditionalCourses: allAdditional,
    additionalNotes: pathway.additional_notes,
    sourceFile: pathway.source_file,
    pageNumber: pathway.page_number,
    pathwayId,
    conflictsByQuarter,
    hasConflictData: quarterKeys.length > 0,
    totalConflicts,
    hasConflicts: totalConflicts > 0,
  }
}

export const pathwayData = rawData.pathways.map(transformPathway).sort(popularitySort)

/**
 * Sort programs by popularity/demand. Programs matching earlier entries
 * in the priority list appear first. Within the same priority tier,
 * transfer degrees sort above certificates.
 */
function popularitySort(a, b) {
  const aPriority = getPopularityRank(a)
  const bPriority = getPopularityRank(b)
  if (aPriority !== bPriority) return aPriority - bPriority
  // Within same tier, sort transfers first, then degrees, then certificates
  return getCredentialWeight(a) - getCredentialWeight(b)
}

function getCredentialWeight(program) {
  const t = program.credentialType
  if (t.includes('Transfer')) return 0
  if (t.includes('Bachelor')) return 1
  if (t.includes('Associate in Science (AS)')) return 2
  if (t.includes('Associate in Arts (AA)')) return 3
  if (t.includes('Advanced')) return 4
  if (t.includes('COA')) return 5
  if (t.includes('Noncredit')) return 6
  return 7
}

/**
 * Popularity tiers based on enrollment demand at community colleges.
 * Lower number = higher popularity = appears first.
 */
function getPopularityRank(program) {
  const name = program.programName.toLowerCase()
  const short = program.shortName.toLowerCase()

  const tiers = [
    // Tier 1: Highest demand STEM & tech
    ['computer science', 'cybersecurity', 'programming', 'web development', 'software'],
    // Tier 2: Engineering & math
    ['engineering', 'math'],
    // Tier 3: Business & accounting
    ['business', 'accounting', 'finance', 'economics'],
    // Tier 4: Health sciences
    ['nursing', 'biology', 'health sci', 'medical lab', 'nutrition'],
    // Tier 5: Psychology & social sciences
    ['psychology', 'sociology', 'political', 'administration of justice', 'admj'],
    // Tier 6: Communication, English, arts
    ['communication', 'english', 'journalism', 'public relation'],
    // Tier 7: Physical/natural sciences
    ['physics', 'chemistry', 'astronomy', 'geology', 'geography', 'earth sci', 'environmental'],
    // Tier 8: Creative arts & media
    ['art', 'graphic design', 'film', 'photo', 'music', 'dance', 'theater'],
    // Tier 9: CIS/IT/Networking
    ['network', 'database', 'information tech', 'project manage'],
    // Tier 10: Education & child dev
    ['child dev', 'early childhood', 'education'],
    // Tier 11: Humanities & languages
    ['history', 'philosophy', 'humanities', 'linguistics', 'women', 'global', 'anthropology'],
    // Tier 12: Liberal arts & transfer studies
    ['liberal arts', 'transfer studies'],
    // Tier 13: Trades & vocational
    ['automotive', 'auto ', 'machinist', 'machining', 'cnc', 'manufacturing', 'welding', 'smog',
      'chassis', 'powertrain', 'engine perform', 'paralegal'],
    // Tier 14: Kinesiology & misc
    ['kinesiology', 'leadership'],
  ]

  for (let i = 0; i < tiers.length; i++) {
    for (const keyword of tiers[i]) {
      if (name.includes(keyword) || short.includes(keyword)) {
        return i
      }
    }
  }
  return tiers.length // Unmatched goes to the end
}

export const metadata = {
  institution: rawData.institution,
  catalogYear: rawData.catalog_year,
  totalPathways: rawData.total_pathways,
}

// Extract unique filter values
export const villages = [...new Set(pathwayData.map(p => p.village))].filter(Boolean).sort()
export const credentialTypes = [...new Set(pathwayData.map(p => p.credentialType))].filter(Boolean).sort()
