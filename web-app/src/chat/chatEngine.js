/**
 * Client-side retrieval "chatbot" for the pathway explorer.
 *
 * No LLM: it recognizes a few intents from the question (pathway/requirement
 * lookup, "which pathways include course X", and a live schedule-conflict check)
 * and answers from the bundled pathway/conflict data — reaching the deployed,
 * keyless `/plan` endpoint only for real-time conflict questions. This keeps the
 * demo reliable (no token limits, no credentials) while still hitting live data.
 */

import { pathwayData } from '../data/pathways'
import { TERMS, PLAN_API_URL } from '../config'

const YEAR_LABEL = { year_1: 'First Year', year_2: 'Second Year' }
const QUARTERS = ['fall', 'winter', 'spring']

// Words that are never a program-name signal, so they don't cause spurious
// pathway matches (they're the scaffolding of the questions themselves).
const STOP = new Set([
  'pathway', 'pathways', 'program', 'programs', 'course', 'courses', 'class',
  'classes', 'requirement', 'requirements', 'required', 'take', 'need', 'needed',
  'what', 'which', 'the', 'for', 'first', 'second', 'year', 'fall', 'winter',
  'spring', 'does', 'conflict', 'conflicts', 'with', 'and', 'include', 'includes',
  'have', 'has', 'offer', 'offers', 'contain', 'show', 'tell', 'about', 'list',
  'can', 'both', 'same', 'time', 'this', 'that', 'map', 'plan', 'schedule',
])

// Every subject code that appears in the data — used to separate a real course
// token ("MATH 1A") from prose that merely looks like one ("Area 3").
const KNOWN_SUBJECTS = new Set()
for (const p of pathwayData) {
  for (const c of p.courseCodes || []) KNOWN_SUBJECTS.add(c.split(' ')[0])
}

const cap = (s) => s.charAt(0).toUpperCase() + s.slice(1)

// ---- parsers ----------------------------------------------------------------

/** Canonical course codes mentioned in the text, validated against real subjects. */
export function parseCourses(text) {
  const re = /\b([A-Za-z]{2,8})\s*([A-Za-z]?\d{1,3}[A-Za-z]{0,2})\b/g
  const found = []
  const seen = new Set()
  let m
  while ((m = re.exec(text)) !== null) {
    const code = `${m[1].toUpperCase()} ${m[2].toUpperCase()}`
    if (!KNOWN_SUBJECTS.has(m[1].toUpperCase()) || seen.has(code)) continue
    seen.add(code)
    found.push(code)
  }
  return found
}

/** The term (quarter + year) named in the text, or null. */
export function parseTerm(text) {
  const m = text.toLowerCase().match(/(fall|winter|spring)\s*(20\d{2})/)
  if (!m) return null
  const label = `${cap(m[1])} ${m[2]}`
  return TERMS.find((t) => t.label.toLowerCase() === label.toLowerCase()) || null
}

/** Best pathway match by overlap of meaningful question words with its name. */
export function matchPathway(text) {
  const words = (text.toLowerCase().match(/[a-z]+/g) || [])
    .filter((w) => w.length >= 3 && !STOP.has(w))
  if (!words.length) return null
  let best = null
  for (const p of pathwayData) {
    const hay = `${p.programName} ${p.shortName} ${p.village}`.toLowerCase()
    let score = 0
    for (const w of words) if (hay.includes(w)) score++
    if (score > 0 && (!best || score > best.score)) best = { p, score }
  }
  return best ? best.p : null
}

// ---- data helpers -----------------------------------------------------------

/** Clean course codes a pathway recommends for one quarter (raw text fallback). */
function quarterCourses(program, year, quarter) {
  const c = program.conflictsByQuarter?.[`${year}#${quarter}`]
  if (c) return [...new Set([...(c.courses || []), ...(c.missing_courses || [])])]
  return program.years?.[year]?.[quarter]?.required_courses || []
}

// ---- intent answers ---------------------------------------------------------

/** "Which pathways include COURSE" — scan every pathway's course code set. */
function pathwaysIncluding(courses) {
  return courses.slice(0, 3).map((code) => {
    const hits = pathwayData.filter((p) => (p.courseCodes || []).includes(code))
    if (!hits.length) return `I don't see any pathway that lists ${code}.`
    const names = hits.slice(0, 8).map((p) => `• ${p.shortName} (${p.credentialType})`)
    const more = hits.length > 8 ? `\n…and ${hits.length - 8} more.` : ''
    return `${code} appears in ${hits.length} pathway${hits.length !== 1 ? 's' : ''}:\n${names.join('\n')}${more}`
  }).join('\n\n')
}

/** Pathway summary + its recommended courses (optionally filtered to a year/quarter). */
function pathwayInfo(program, lc) {
  const header =
    `${program.programName} — ${program.credentialType}, ${program.village}. ` +
    `${program.totalRequiredCourses} required courses over ${program.pathwayYears} year${program.pathwayYears !== 1 ? 's' : ''}.`

  // Narrow to a year/quarter if the question mentions one.
  const years =
    /second year|year\s*2|2nd year/.test(lc) ? ['year_2']
    : /first year|year\s*1|1st year/.test(lc) ? ['year_1']
    : ['year_1', 'year_2']
  const quarters = QUARTERS.filter((q) => new RegExp(`\\b${q}\\b`).test(lc))
  const qtrs = quarters.length ? quarters : QUARTERS

  const lines = []
  for (const y of years) {
    for (const q of qtrs) {
      const cs = quarterCourses(program, y, q)
      if (cs.length) lines.push(`${YEAR_LABEL[y]} · ${cap(q)}: ${cs.join(', ')}`)
    }
  }
  return lines.length ? `${header}\n\n${lines.join('\n')}` : header
}

/** Live conflict check via the /plan endpoint for 2+ courses in a term. */
async function conflictAnswer(courses, term) {
  let data
  try {
    const resp = await fetch(PLAN_API_URL, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ term_code: term.code, courses }),
    })
    data = await resp.json()
    if (!resp.ok) throw new Error(data.error || `HTTP ${resp.status}`)
  } catch (e) {
    return `I couldn't reach the schedule service to check that (${e.message}). Try again in a moment.`
  }

  const offered = data.offered_courses || []
  const notOffered = data.not_offered_courses || []
  const tail = notOffered.length ? ` (Not offered in ${term.label}: ${notOffered.join(', ')}.)` : ''

  if (offered.length < 2) {
    return `In ${term.label} I couldn't find offered sections for at least two of ${courses.join(', ')}.${tail}`
  }

  const { pairs_evaluated = 0, overlap_count = 0, clear_count = 0, overlap_percentage = 0 } = data
  const list = offered.join(', ')
  let verdict
  if (overlap_count === 0) {
    verdict = `✅ No time conflicts — every section pairing fits, so you can take ${list} together in ${term.label}.`
  } else if (clear_count === 0) {
    verdict = `⛔ In ${term.label}, ${list} can't all be taken together — every one of the ${pairs_evaluated} section pairings overlaps.`
  } else {
    verdict = `⚠️ You can still take ${list} together in ${term.label} if you pick sections carefully: ${overlap_count} of ${pairs_evaluated} section pairings overlap (${overlap_percentage}%), but ${clear_count} pairings are clear.`
  }
  return verdict + tail
}

// ---- router -----------------------------------------------------------------

export const GREETING =
  "Hi! I can help with De Anza pathways and schedules. Try:\n" +
  "• “What courses are in the Computer Science pathway first year?”\n" +
  "• “Does MATH 1A conflict with ENGL 1A in Fall 2026?”\n" +
  "• “Which pathways include CIS 22A?”"

const HELP =
  "I can answer three kinds of questions:\n" +
  "• Pathway courses — “requirements for Nursing”, “Biology second year winter”.\n" +
  "• Schedule conflicts — “does MATH 1A conflict with ENGL 1A in Fall 2026?” (needs two courses + a term).\n" +
  "• Course lookup — “which pathways include CIS 22A?”"

/** Route a question to an intent and produce an answer (async for conflict checks). */
export async function answer(question) {
  const text = (question || '').trim()
  if (!text) return GREETING

  const lc = text.toLowerCase()
  const courses = parseCourses(text)
  const term = parseTerm(text)

  const wantsConflict = /(conflict|overlap|clash|fit|together|same time|both|at the same)/.test(lc)
  const wantsPathwaySearch =
    /(which|what)\s+(pathway|program)/.test(lc) ||
    /pathways?\s+(include|includes|have|has|offer|offers|contain|with)/.test(lc)

  // 1) "which pathways include COURSE"
  if (wantsPathwaySearch && courses.length) return pathwaysIncluding(courses)

  // 2) schedule-conflict check (explicit intent, or 2+ courses with a term)
  if (wantsConflict || (courses.length >= 2 && term)) {
    if (courses.length < 2) {
      return 'Give me at least two courses to compare, e.g. “Does MATH 1A conflict with ENGL 1A in Fall 2026?”'
    }
    if (!term) {
      return `Which term? Options: ${TERMS.map((t) => t.label).join(', ')}. e.g. “${courses[0]} and ${courses[1]} in Fall 2026”.`
    }
    return await conflictAnswer(courses, term)
  }

  // 3) pathway info / requirements
  const program = matchPathway(text)
  if (program) return pathwayInfo(program, lc)

  // 4) a course with no pathway context → where it shows up
  if (courses.length) return pathwaysIncluding(courses)

  // 5) fallback
  return HELP
}
