import { useState, useRef, useEffect } from 'react'
import { ask, GREETING } from '../chat/chatAgent'

const SUGGESTIONS = [
  'Which classes have no room in Fall 2025?',
  'Which pathways include CIS 22A?',
  'What does the Computer Science pathway require in year 1?',
]

export default function ChatWidget() {
  const [open, setOpen] = useState(false)
  const [messages, setMessages] = useState([{ role: 'bot', text: GREETING }])
  const [input, setInput] = useState('')
  const [busy, setBusy] = useState(false)
  const endRef = useRef(null)

  // Keep the latest message in view as the conversation grows.
  useEffect(() => {
    endRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [messages, open])

  // Send a question: echo it, ask the LLM agent, append the answer.
  const send = async (text) => {
    const q = (text ?? input).trim()
    if (!q || busy) return
    setInput('')
    setMessages((m) => [...m, { role: 'user', text: q }])
    setBusy(true)
    try {
      const reply = await ask(q)
      setMessages((m) => [...m, { role: 'bot', text: reply }])
    } catch (e) {
      setMessages((m) => [...m, { role: 'bot', text: `Sorry, something went wrong (${e.message}). Try again in a moment.` }])
    } finally {
      setBusy(false)
    }
  }

  const onKeyDown = (e) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault()
      send()
    }
  }

  return (
    <>
      {/* Floating launcher */}
      <button
        className="chat-fab"
        onClick={() => setOpen((o) => !o)}
        aria-label={open ? 'Close assistant' : 'Open assistant'}
      >
        {open ? '×' : 'Ask'}
      </button>

      {open && (
        <div className="chat-panel" role="dialog" aria-label="Pathway assistant">
          <div className="chat-header">
            <span className="chat-title">Pathway Assistant</span>
            <button className="chat-close" onClick={() => setOpen(false)} aria-label="Close">×</button>
          </div>

          <div className="chat-messages">
            {messages.map((m, i) => (
              <div key={i} className={`chat-msg ${m.role}`}>
                {m.text}
              </div>
            ))}
            {busy && <div className="chat-msg bot chat-typing">…</div>}
            <div ref={endRef} />
          </div>

          {/* Suggested prompts (only before the first question) */}
          {messages.length <= 1 && (
            <div className="chat-suggestions">
              {SUGGESTIONS.map((s) => (
                <button key={s} className="chat-suggestion" onClick={() => send(s)}>
                  {s}
                </button>
              ))}
            </div>
          )}

          <div className="chat-input-row">
            <textarea
              className="chat-input"
              rows={1}
              placeholder="Ask about courses or conflicts…"
              value={input}
              onChange={(e) => setInput(e.target.value)}
              onKeyDown={onKeyDown}
            />
            <button className="chat-send" onClick={() => send()} disabled={busy || !input.trim()}>
              Send
            </button>
          </div>
        </div>
      )}
    </>
  )
}
