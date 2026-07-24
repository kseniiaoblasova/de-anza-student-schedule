/**
 * Client for the LLM scheduling assistant (Bedrock AgentCore agent).
 *
 * Posts the user's message to the chat endpoint and returns the assistant's
 * answer. A session id is kept for the lifetime of the page so the agent's
 * short-term memory can carry context across follow-up questions.
 */

import { CHAT_API_URL } from '../config'

export const GREETING =
  "Hi! I'm the De Anza scheduling assistant. Ask me about program pathways, " +
  'class schedules, room assignments, or scheduling conflicts — for example, ' +
  '"Which classes have no room in Fall 2025?" or "What does the Accounting ' +
  'pathway require in the first year?"'

// One session id per page load so multi-turn context works without persisting
// anything server-side beyond the agent's own short-term memory.
let sessionId = null

/** Send a question to the agent and return its answer text. */
export async function ask(question) {
  const message = (question || '').trim()
  if (!message) return GREETING

  const resp = await fetch(CHAT_API_URL, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(sessionId ? { message, sessionId } : { message }),
  })

  const data = await resp.json().catch(() => ({}))
  if (!resp.ok) {
    throw new Error(data.error || `Request failed (${resp.status})`)
  }

  // Remember the session id the backend assigns so later turns keep context.
  if (data.sessionId) sessionId = data.sessionId
  return data.answer || "I couldn't find an answer to that."
}
