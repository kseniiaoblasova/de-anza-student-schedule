/**
 * Parse raw course lines into structured requirements.
 *
 * Raw pathway data stores courses as plain text lines split arbitrarily by the
 * PDF parser. This module groups continuation lines back into logical requirements,
 * then classifies each as either a "fixed" course or a "choice" (has "or" options).
 *
 * The grouping logic mirrors the counting rules in pathways.js (isDefinitelyNewRequirement /
 * startsMultiLineBlock) so the displayed count stays consistent.
 */

// --- Line classification (same rules as pathways.js) ---

function isDefinitelyNewRequirement(line) {
  const lower = line.toLowerCase()
  if (lower.startsWith('complete ')) return true
  if (/^ge area/i.test(line)) return true
  if (/^option \d/i.test(line)) return true
  if (lower.startsWith('choose ') || lower.startsWith('select ')) return true
  if (lower.startsWith('elective ')) return true
  if (lower.startsWith('critical thinking')) return true
  if (/^[A-Z]{2,5}\s+(\d+[A-Z]?\s+)?as required/i.test(line)) return true
  if (/^[A-Z]{2,5}\s+\d+[A-Z]?\s*$/.test(line)) return true
  if (/^[A-Z]{2,5}\s+[A-Z]?\d+/.test(line) && line.includes('(formerly') && !line.includes(';')) return true
  if (/^[A-Z]{2,5}\s+\d+[A-Z]?\s+--\s+/.test(line)) return true
  if (/^[A-Z]{2,5}\s+\d+[A-Z]?\s/.test(line) && !line.includes(',') && !line.includes(';') && !/\sor\s+[A-Z]{2,5}\s+\d/.test(line)) {
    if (!/^(Science|Drawing|Painting|Ceramics|Sculpture|Digital|Photography|Color|Quarter)/i.test(line)) return true
  }
  return false
}

function startsMultiLineBlock(line) {
  const lower = line.toLowerCase()
  if (lower.startsWith('complete ')) return true
  if (/^ge area/i.test(line)) return true
  if (line.endsWith(':') || line.endsWith(',') || line.endsWith(';') || line.endsWith(' or')) return true
  if (line.endsWith('(formerly') || line.endsWith('(formerly ')) return true
  if (/\s[A-Z]{2,5}$/.test(line)) return true
  if (/\s(or|and)\s+[A-Z]/.test(line) && !line.endsWith(')')) return true
  return false
}

// --- Grouping: merge continuation lines into logical requirements ---

/**
 * Group raw course text lines into logical requirement blocks.
 * Returns an array of strings, each representing one complete requirement.
 */
export function groupCourseLines(courseLines) {
  if (!courseLines || courseLines.length === 0) return []

  const groups = []
  let current = ''
  let inListContext = false

  for (let i = 0; i < courseLines.length; i++) {
    const line = courseLines[i].trim()
    if (!line) continue

    if (inListContext) {
      if (isDefinitelyNewRequirement(line)) {
        // Save previous group, start a new one
        if (current) groups.push(current)
        current = line
        inListContext = startsMultiLineBlock(line)
      } else {
        // Continuation of the current block
        current += ' ' + line
      }
    } else {
      // New requirement starts
      if (current) groups.push(current)
      current = line
      inListContext = startsMultiLineBlock(line)
    }
  }
  if (current) groups.push(current)

  return groups
}

// --- Choice detection: split grouped requirements into structured items ---

/**
 * Check if a grouped requirement represents a choice between courses.
 * Only matches clear "COURSE or COURSE" patterns, not "Complete one from list" blocks.
 */
function isSimpleChoice(text) {
  // Skip "Complete..." / "GE Area..." / "Choose..." blocks — these are list-style
  // requirements that are too complex for a simple radio button.
  const lower = text.toLowerCase()
  if (lower.startsWith('complete ')) return false
  if (/^ge area/i.test(text)) return false
  if (lower.startsWith('choose ')) return false
  if (lower.startsWith('select ')) return false

  // Must contain " or " between what look like course codes or course references
  return /\sor\s/i.test(text)
}

/**
 * Split a choice string into individual options.
 * Handles patterns like "COMM C1000 (formerly COMM 1) or COMM 10"
 * and "STAT C1000 (formerly MATH 10) or SOC 15 or PSYC 15 or COMM 10"
 */
function splitChoiceOptions(text) {
  // Split on " or " but not inside parentheses.
  // Strategy: temporarily replace content inside parens, split, then restore.
  const parenPlaceholders = []
  const cleaned = text.replace(/\([^)]*\)/g, (match) => {
    parenPlaceholders.push(match)
    return `__PAREN_${parenPlaceholders.length - 1}__`
  })

  const parts = cleaned.split(/\s+or\s+/i)

  // Restore parenthesized content
  return parts.map(part => {
    return part.replace(/__PAREN_(\d+)__/g, (_, idx) => parenPlaceholders[parseInt(idx)])
  }).map(p => p.trim()).filter(Boolean)
}

/**
 * Parse a list of raw course lines into structured requirement items.
 *
 * Returns an array of:
 *   { type: 'fixed', text: string }         — a single required course/block
 *   { type: 'choice', text: string, options: string[] } — pick one from options
 */
export function parseCourseRequirements(courseLines) {
  const grouped = groupCourseLines(courseLines)

  return grouped.map(text => {
    if (isSimpleChoice(text)) {
      const options = splitChoiceOptions(text)
      // Only treat as a choice if we got 2+ meaningful options
      if (options.length >= 2) {
        return { type: 'choice', text, options }
      }
    }
    return { type: 'fixed', text }
  })
}
