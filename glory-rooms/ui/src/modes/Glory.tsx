import { useState, useRef } from 'react'
import { api } from '../api'

interface BodyResponse {
  model: string
  role: string
  response: string
  latency_ms: number
  error?: string
}

interface GloryResult {
  prompt: string
  body_responses: BodyResponse[]
  synthesis: string
  session_id: string
  total_latency_ms: number
  synthesis_error?: string
}

const BODY_META: Record<string, { role: string; color: string; emoji: string }> = {
  gemma:  { role: 'LEG',   color: '#22c4a1', emoji: '🦵' },
  qwen:   { role: 'ARM',   color: '#ffb347', emoji: '💪' },
  hermes: { role: 'ARM',   color: '#c280ff', emoji: '🪽' },
  kimi:   { role: 'CHEST', color: '#87ceeb', emoji: '❤️' },
}

function BodyCard({ r, loading }: { r: BodyResponse; loading?: boolean }) {
  const meta = BODY_META[r.model] || { role: 'BODY', color: '#57ff3b', emoji: '◈' }
  const [expanded, setExpanded] = useState(true)

  return (
    <div className="border border-ink-700" style={{ borderLeftColor: meta.color, borderLeftWidth: '2px' }}>
      <button
        className="w-full flex items-center gap-3 px-3 py-2 cursor-pointer hover:bg-ink-800/50 transition-colors"
        onClick={() => setExpanded(e => !e)}
      >
        <span className="text-xs" style={{ color: meta.color }}>
          {loading ? '⠋' : r.error ? '✗' : '✓'}
        </span>
        <span className="font-mono text-sm text-ink-200 uppercase tracking-wider">{r.model}</span>
        <span
          className="text-[9px] px-1.5 py-0.5 uppercase tracking-widest"
          style={{ background: `${meta.color}18`, color: meta.color }}
        >
          {meta.role}
        </span>
        {!loading && (
          <span className="text-[10px] text-ink-600 ml-auto font-mono">{r.latency_ms}ms</span>
        )}
        <span className="text-ink-600 text-xs ml-1">{expanded ? '▲' : '▼'}</span>
      </button>
      {expanded && (
        <div className="px-3 pb-3 border-t border-ink-800">
          {r.error ? (
            <p className="text-xs text-red-400 font-mono mt-2">{r.error}</p>
          ) : (
            <p className="text-sm text-ink-200 leading-relaxed mt-2 whitespace-pre-wrap">{r.response}</p>
          )}
        </div>
      )}
    </div>
  )
}

export function Glory() {
  const [prompt, setPrompt] = useState('')
  const [loading, setLoading] = useState(false)
  const [result, setResult] = useState<GloryResult | null>(null)
  const [error, setError] = useState('')
  const textRef = useRef<HTMLTextAreaElement>(null)

  const submit = async () => {
    const q = prompt.trim()
    if (!q || loading) return
    setLoading(true)
    setError('')
    setResult(null)
    try {
      const r = await api.glory(q)
      setResult(r)
    } catch (e) {
      setError('Connection failed — is the proxy running?')
    } finally {
      setLoading(false)
    }
  }

  const onKey = (e: React.KeyboardEvent) => {
    if (e.key === 'Enter' && (e.ctrlKey || e.metaKey)) submit()
  }

  return (
    <div className="space-y-5 max-w-3xl">
      {/* Header */}
      <div>
        <div className="flex items-center gap-3 mb-1">
          <span className="text-accent-500 text-xl" style={{ textShadow: '0 0 12px rgba(87,255,59,0.6)' }}>◈</span>
          <h2 className="text-base text-accent-500 tracking-[0.25em] uppercase"
            style={{ textShadow: '0 0 10px rgba(87,255,59,0.4)' }}>
            Glory — Multi-Confirmational
          </h2>
        </div>
        <p className="text-xs text-ink-500 leading-relaxed ml-8">
          Your question routes simultaneously to all Glory body parts.
          Each responds independently. Claude synthesizes a unified answer.
        </p>
      </div>

      {/* Body diagram */}
      <div className="flex items-center gap-2 flex-wrap">
        {Object.entries(BODY_META).map(([id, m]) => (
          <div key={id} className="flex items-center gap-1.5 border border-ink-700 px-2 py-1"
            style={{ borderLeftColor: m.color, borderLeftWidth: '2px' }}>
            <span className="text-[10px] font-mono" style={{ color: m.color }}>{id}</span>
            <span className="text-[9px] text-ink-600 uppercase tracking-wider">{m.role}</span>
          </div>
        ))}
        <span className="text-ink-700 text-xs">→ synthesis by HEAD</span>
      </div>

      {/* Input */}
      <div className="space-y-2">
        <textarea
          ref={textRef}
          className="input w-full resize-none text-sm"
          rows={4}
          placeholder="Ask anything — all body parts will respond, then synthesize…"
          value={prompt}
          onChange={e => setPrompt(e.target.value)}
          onKeyDown={onKey}
          disabled={loading}
        />
        <div className="flex items-center gap-3">
          <button
            className="btn-primary cursor-pointer disabled:opacity-40"
            disabled={!prompt.trim() || loading}
            onClick={submit}
          >
            {loading ? 'Consulting body…' : 'Ask Glory'}
          </button>
          <span className="text-[10px] text-ink-700">Ctrl+Enter to submit</span>
          {loading && (
            <span className="text-xs text-accent-500/60 font-mono animate-pulse ml-auto">
              ⠋ Querying Gemma · Qwen · Hermes simultaneously…
            </span>
          )}
        </div>
      </div>

      {error && <p className="text-xs text-red-400 font-mono">{error}</p>}

      {/* Results */}
      {result && (
        <div className="space-y-4 fade-in">
          {/* Asked */}
          <div className="border border-ink-800 px-4 py-3" style={{ borderTopStyle: 'solid' }}>
            <div className="text-[9px] text-ink-600 uppercase tracking-wider mb-1">Query</div>
            <p className="text-sm text-ink-300">{result.prompt}</p>
          </div>

          {/* Body responses */}
          <div className="space-y-2">
            <div className="text-[9px] text-ink-600 uppercase tracking-wider">Body Responses</div>
            {result.body_responses.map(r => (
              <BodyCard key={r.model} r={r} />
            ))}
          </div>

          {/* Synthesis */}
          <div className="border border-accent-500/30 p-4"
            style={{ background: 'rgba(87,255,59,0.03)', boxShadow: '0 0 20px rgba(87,255,59,0.05)' }}>
            <div className="flex items-center gap-2 mb-3">
              <span className="text-accent-500 text-sm">◈</span>
              <div className="text-[9px] text-accent-500/70 uppercase tracking-[0.25em]">Glory Synthesis — Unified Answer</div>
              <div className="ml-auto text-[10px] text-ink-600 font-mono">{result.total_latency_ms}ms total</div>
            </div>
            {result.synthesis_error ? (
              <p className="text-xs text-red-400 font-mono">{result.synthesis_error}</p>
            ) : (
              <p className="text-sm text-ink-100 leading-relaxed whitespace-pre-wrap">{result.synthesis}</p>
            )}
          </div>

          {/* Session link */}
          {result.session_id && (
            <div className="text-[10px] text-ink-700 font-mono">
              session: {result.session_id}
            </div>
          )}
        </div>
      )}
    </div>
  )
}
