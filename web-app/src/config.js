/**
 * Frontend runtime config.
 *
 * PLAN_API_URL is the keyless student-planner endpoint (POST { term_code,
 * courses } -> overlap/clear split). Defaults to the deployed REST API's /plan
 * route; override at build time with VITE_PLAN_API_URL for other environments.
 */
export const PLAN_API_URL =
  import.meta.env.VITE_PLAN_API_URL ||
  'https://63l5xpc4uk.execute-api.us-west-2.amazonaws.com/prod/plan'

/**
 * Selectable terms, newest-catalog first. Codes match deanza-class-schedule
 * partitions (…22 = Fall, …32 = Winter, …42 = Spring); both loaded academic
 * years are offered.
 */
export const TERMS = [
  { code: '202722', label: 'Fall 2026' },
  { code: '202732', label: 'Winter 2027' },
  { code: '202742', label: 'Spring 2027' },
  { code: '202622', label: 'Fall 2025' },
  { code: '202632', label: 'Winter 2026' },
  { code: '202642', label: 'Spring 2026' },
]
