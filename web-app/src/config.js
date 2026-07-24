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
 * CHAT_API_URL is the LLM assistant endpoint (POST { message, sessionId } ->
 * { answer, sessionId }). It fronts a Bedrock AgentCore agent that answers from
 * the DynamoDB tables via tool calls. Override with VITE_CHAT_API_URL.
 */
export const CHAT_API_URL =
  import.meta.env.VITE_CHAT_API_URL ||
  'https://km7w10xv4e.execute-api.us-west-2.amazonaws.com/'

/**
 * Selectable terms, newest-catalog first. Codes match deanza-class-schedule
 * partitions (…22 = Fall, …32 = Winter, …42 = Spring); both loaded academic
 * years are offered. `quarterKey` ties a term to the pathway quarter it maps to
 * (same mapping as the backend's YEAR_QUARTER_TO_TERM) so the UI can surface that
 * quarter's recommended courses; it matches the keys in `conflictsByQuarter`.
 */
export const TERMS = [
  { code: '202722', label: 'Fall 2026', quarterKey: 'year_2#fall' },
  { code: '202732', label: 'Winter 2027', quarterKey: 'year_2#winter' },
  { code: '202742', label: 'Spring 2027', quarterKey: 'year_2#spring' },
  { code: '202622', label: 'Fall 2025', quarterKey: 'year_1#fall' },
  { code: '202632', label: 'Winter 2026', quarterKey: 'year_1#winter' },
  { code: '202642', label: 'Spring 2026', quarterKey: 'year_1#spring' },
]
