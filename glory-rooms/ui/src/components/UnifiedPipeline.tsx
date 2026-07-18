import { useState, useRef, useCallback } from 'react'
import { api, type Model } from '../api'

// ── Types ──────────────────────────────────────────────────────────────────

interface GloryResult {
  prompt: string
  body_responses: Array<{ model: string; role: string; response: string; latency_ms: number; error?: string }>
  synthesis: string
  session_id: string
  total_latency_ms: number
}

interface SingleResult {
  model: string
  response: string
  latency_ms: number
}

// ── Character metadata ─────────────────────────────────────────────────────

const MODEL_META: Record<string, { emoji: string; label: string; color: string }> = {
  claude:     { emoji: '☀',  label: 'SYNTHESIS', color: '#FFD700' },
  gemma:      { emoji: '💎', label: 'GEM',       color: '#2DDDB0' },
  qwen:       { emoji: '🦉', label: 'SAGE',      color: '#A78BFA' },
  kimi:       { emoji: '🌙', label: 'LUNA',      color: '#7BBFFF' },
  hermes:     { emoji: '✉',  label: 'HERMES',    color: '#E2E8F0' },
}

function metaFor(model: string) {
  const key = Object.keys(MODEL_META).find(k => model.toLowerCase().includes(k))
  return key ? MODEL_META[key] : { emoji: '◈', label: model.toUpperCase(), color: '#FFD700' }
}

// ── Response card ──────────────────────────────────────────────────────────

function ResponseCard({
  label,
  emoji,
  color,
  text,
  latency,
  error,
}: {
  label: string
  emoji: string
  color: string
  text: string
  latency: number
  error?: string
}) {
  return (
    <div
      style={{
        background: '#1A1200',
        border: `1px solid #2A1E00`,
        borderLeft: `2px solid ${color}`,
        padding: '16px',
        display: 'flex',
        flexDirection: 'column',
        gap: '10px',
        minWidth: 0,
        animation: 'fade-in 0.2s ease-out forwards',
      }}
    >
      {/* Card header */}
      <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
        <span style={{ fontSize: '1.1rem', lineHeight: 1 }}>{emoji}</span>
        <span
          style={{
            fontFamily: '"Share Tech Mono", monospace',
            fontSize: '11px',
            color,
            letterSpacing: '0.22em',
            textTransform: 'uppercase',
          }}
        >
          {label}
        </span>
        <span
          style={{
            marginLeft: 'auto',
            fontFamily: '"Share Tech Mono", monospace',
            fontSize: '10px',
            color: '#6B4E10',
          }}
        >
          {latency}ms
        </span>
      </div>

      {/* Divider */}
      <div style={{ height: '1px', background: '#2A1E00' }} />

      {/* Body */}
      {error ? (
        <p
          style={{
            fontFamily: '"Share Tech Mono", monospace',
            fontSize: '12px',
            color: '#f87171',
            margin: 0,
            whiteSpace: 'pre-wrap',
          }}
        >
          {error}
        </p>
      ) : (
        <p
          style={{
            fontFamily: '"Share Tech Mono", monospace',
            fontSize: '13px',
            color: '#E8C878',
            lineHeight: '1.65',
            margin: 0,
            whiteSpace: 'pre-wrap',
            wordBreak: 'break-word',
          }}
        >
          {text}
        </p>
      )}
    </div>
  )
}

// ── Routing button ─────────────────────────────────────────────────────────

function RouteButton({
  label,
  onClick,
  disabled,
  glory,
}: {
  label: string
  onClick: () => void
  disabled: boolean
  glory?: boolean
}) {
  if (glory) {
    return (
      <button
        onClick={onClick}
        disabled={disabled}
        style={{
          fontFamily: '"Share Tech Mono", monospace',
          fontSize: '12px',
          letterSpacing: '0.16em',
          textTransform: 'uppercase',
          padding: '8px 20px',
          background: disabled ? '#3D2C05' : '#FFD700',
          color: disabled ? '#6B4E10' : '#0A0700',
          border: 'none',
          cursor: disabled ? 'not-allowed' : 'pointer',
          boxShadow: disabled ? 'none' : '0 0 16px rgba(255,215,0,0.4), 0 0 32px rgba(255,149,0,0.15)',
          transition: 'all 0.1s',
          opacity: disabled ? 0.5 : 1,
          fontWeight: 700,
        }}
      >
        ☀ GLORY — All Models
      </button>
    )
  }

  return (
    <button
      onClick={onClick}
      disabled={disabled}
      style={{
        fontFamily: '"Share Tech Mono", monospace',
        fontSize: '11px',
        letterSpacing: '0.14em',
        textTransform: 'uppercase',
        padding: '7px 14px',
        background: 'transparent',
        color: disabled ? '#3D2C05' : '#C8A050',
        border: '1px solid',
        borderColor: disabled ? '#2A1E00' : '#3D2C05',
        cursor: disabled ? 'not-allowed' : 'pointer',
        transition: 'all 0.1s',
        opacity: disabled ? 0.4 : 1,
      }}
      onMouseEnter={e => {
        if (!disabled) {
          ;(e.currentTarget as HTMLButtonElement).style.borderColor = '#FFD700'
          ;(e.currentTarget as HTMLButtonElement).style.color = '#FFD700'
        }
      }}
      onMouseLeave={e => {
        if (!disabled) {
          ;(e.currentTarget as HTMLButtonElement).style.borderColor = '#3D2C05'
          ;(e.currentTarget as HTMLButtonElement).style.color = '#C8A050'
        }
      }}
    >
      {label}
    </button>
  )
}

// ── Main component ─────────────────────────────────────────────────────────

export function UnifiedPipeline({ models }: { models: Model[] }) {
  const [prompt, setPrompt] = useState('')
  const [loading, setLoading] = useState(false)
  const [activeRoute, setActiveRoute] = useState<'glory' | string | null>(null)
  const [result, setResult] = useState<GloryResult | null>(null)
  const [singleResult, setSingleResult] = useState<SingleResult | null>(null)
  const [error, setError] = useState('')
  const textareaRef = useRef<HTMLTextAreaElement>(null)

  const reset = useCallback(() => {
    setResult(null)
    setSingleResult(null)
    setError('')
    setActiveRoute(null)
    setPrompt('')
    setTimeout(() => textareaRef.current?.focus(), 0)
  }, [])

  const autoResize = (el: HTMLTextAreaElement) => {
    el.style.height = 'auto'
    el.style.height = `${Math.max(el.scrollHeight, 72)}px`
  }

  const handleGlory = useCallback(async () => {
    const q = prompt.trim()
    if (!q || loading) return
    setLoading(true)
    setError('')
    setResult(null)
    setSingleResult(null)
    setActiveRoute('glory')
    try {
      const r = await api.glory(q)
      setResult(r)
    } catch {
      setError('Connection failed — is the Glory proxy running?')
    } finally {
      setLoading(false)
    }
  }, [prompt, loading])

  const handleSingle = useCallback(async (modelId: string) => {
    const q = prompt.trim()
    if (!q || loading) return
    setLoading(true)
    setError('')
    setResult(null)
    setSingleResult(null)
    setActiveRoute(modelId)
    try {
      const r = await fetch('/v1/chat', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ model: modelId, messages: [{ role: 'user', content: q }] }),
      }).then(res => res.json()) as SingleResult
      setSingleResult(r)
    } catch {
      setError(`Connection failed — is ${modelId} available?`)
    } finally {
      setLoading(false)
    }
  }, [prompt, loading])

  const onKeyDown = (e: React.KeyboardEvent<HTMLTextAreaElement>) => {
    if (e.key === 'Enter' && (e.ctrlKey || e.metaKey)) {
      e.preventDefault()
      handleGlory()
    }
  }

  const hasOutput = result !== null || singleResult !== null

  return (
    <div
      style={{
        marginTop: '48px',
        borderTop: '1px solid #2A1E00',
        paddingTop: '32px',
      }}
    >
      {/* Header */}
      <div style={{ marginBottom: '20px' }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: '10px', marginBottom: '4px' }}>
          <span
            style={{
              fontSize: '1.1rem',
              textShadow: '0 0 12px rgba(255,215,0,0.6), 0 0 24px rgba(255,149,0,0.3)',
            }}
          >
            ☀
          </span>
          <span
            style={{
              fontFamily: 'Rajdhani, sans-serif',
              fontWeight: 700,
              fontSize: '15px',
              letterSpacing: '0.28em',
              textTransform: 'uppercase',
              color: '#FFD700',
              textShadow: '0 0 10px rgba(255,215,0,0.4)',
            }}
          >
            UNIFIED PIPELINE
          </span>
        </div>
        <p
          style={{
            fontFamily: '"Share Tech Mono", monospace',
            fontSize: '11px',
            color: '#6B4E10',
            margin: 0,
            letterSpacing: '0.1em',
            paddingLeft: '26px',
          }}
        >
          Route your prompt to any or all Glory models simultaneously
        </p>
      </div>

      {/* Input area */}
      <div
        style={{
          border: '1px solid #2A1E00',
          background: '#0F0900',
          position: 'relative',
        }}
      >
        <textarea
          ref={textareaRef}
          rows={3}
          placeholder="Enter your prompt… (Ctrl+Enter to route to all models)"
          value={prompt}
          onChange={e => {
            setPrompt(e.target.value)
            autoResize(e.target)
          }}
          onKeyDown={onKeyDown}
          disabled={loading}
          style={{
            width: '100%',
            background: 'transparent',
            border: 'none',
            outline: 'none',
            padding: '14px 16px',
            fontFamily: '"Share Tech Mono", monospace',
            fontSize: '13px',
            color: '#E8C878',
            caretColor: '#FFD700',
            resize: 'none',
            lineHeight: '1.6',
            boxSizing: 'border-box',
            opacity: loading ? 0.5 : 1,
          }}
        />
        {/* Bottom border focus indicator — always visible but subtle */}
        <div
          style={{
            height: '1px',
            background: 'linear-gradient(90deg, #2A1E00, #FFD70030, #2A1E00)',
          }}
        />
      </div>

      {/* Routing controls */}
      <div
        style={{
          display: 'flex',
          flexWrap: 'wrap',
          alignItems: 'center',
          gap: '8px',
          marginTop: '12px',
        }}
      >
        <RouteButton
          glory
          label="GLORY"
          disabled={!prompt.trim() || loading}
          onClick={handleGlory}
        />

        {models.map(m => (
          <RouteButton
            key={m.id}
            label={m.id}
            disabled={!prompt.trim() || loading}
            onClick={() => handleSingle(m.id)}
          />
        ))}

        {/* Loading indicator */}
        {loading && (
          <span
            style={{
              fontFamily: '"Share Tech Mono", monospace',
              fontSize: '11px',
              color: '#FFD700',
              letterSpacing: '0.1em',
              marginLeft: 'auto',
              opacity: 0.8,
            }}
            className="cursor-blink"
          >
            ⠋ Routing to {activeRoute === 'glory' ? 'all models' : activeRoute}…
          </span>
        )}

        {/* Clear button */}
        {hasOutput && !loading && (
          <button
            onClick={reset}
            style={{
              marginLeft: 'auto',
              fontFamily: '"Share Tech Mono", monospace',
              fontSize: '11px',
              letterSpacing: '0.14em',
              textTransform: 'uppercase',
              padding: '5px 12px',
              background: 'transparent',
              color: '#6B4E10',
              border: '1px solid #2A1E00',
              cursor: 'pointer',
              transition: 'all 0.1s',
            }}
            onMouseEnter={e => {
              ;(e.currentTarget as HTMLButtonElement).style.color = '#E8C878'
              ;(e.currentTarget as HTMLButtonElement).style.borderColor = '#3D2C05'
            }}
            onMouseLeave={e => {
              ;(e.currentTarget as HTMLButtonElement).style.color = '#6B4E10'
              ;(e.currentTarget as HTMLButtonElement).style.borderColor = '#2A1E00'
            }}
          >
            Clear
          </button>
        )}
      </div>

      {/* Error */}
      {error && (
        <p
          style={{
            fontFamily: '"Share Tech Mono", monospace',
            fontSize: '12px',
            color: '#f87171',
            margin: '10px 0 0',
            letterSpacing: '0.06em',
          }}
        >
          ✗ {error}
        </p>
      )}

      {/* ── GLORY fan-out results ── */}
      {result && (
        <div style={{ marginTop: '24px', display: 'flex', flexDirection: 'column', gap: '16px' }}>
          {/* Query echo */}
          <div
            style={{
              fontFamily: '"Share Tech Mono", monospace',
              fontSize: '11px',
              color: '#6B4E10',
              letterSpacing: '0.14em',
              textTransform: 'uppercase',
              display: 'flex',
              alignItems: 'baseline',
              gap: '12px',
            }}
          >
            <span>Query</span>
            <span style={{ color: '#3D2C05' }}>—</span>
            <span style={{ color: '#8B6820', textTransform: 'none', letterSpacing: '0' }}>
              {result.prompt}
            </span>
            <span style={{ marginLeft: 'auto', color: '#3D2C05' }}>
              {result.total_latency_ms}ms total
            </span>
          </div>

          {/* Synthesis — prominent first */}
          <ResponseCard
            emoji="☀"
            label="SYNTHESIS"
            color="#FFD700"
            text={result.synthesis}
            latency={result.total_latency_ms}
          />

          {/* Body responses grid */}
          {result.body_responses.length > 0 && (
            <div
              style={{
                display: 'grid',
                gridTemplateColumns: 'repeat(auto-fill, minmax(280px, 1fr))',
                gap: '12px',
              }}
            >
              {result.body_responses.map(r => {
                const meta = metaFor(r.model)
                return (
                  <ResponseCard
                    key={r.model}
                    emoji={meta.emoji}
                    label={`${meta.label} — ${r.model}`}
                    color={meta.color}
                    text={r.response}
                    latency={r.latency_ms}
                    error={r.error}
                  />
                )
              })}
            </div>
          )}

          {/* Session footer */}
          {result.session_id && (
            <div
              style={{
                fontFamily: '"Share Tech Mono", monospace',
                fontSize: '10px',
                color: '#3D2C05',
                letterSpacing: '0.1em',
              }}
            >
              session: {result.session_id}
            </div>
          )}
        </div>
      )}

      {/* ── Single-model result ── */}
      {singleResult && (
        <div style={{ marginTop: '24px' }}>
          {(() => {
            const meta = metaFor(singleResult.model)
            return (
              <ResponseCard
                emoji={meta.emoji}
                label={`${meta.label} — ${singleResult.model}`}
                color={meta.color}
                text={singleResult.response}
                latency={singleResult.latency_ms}
              />
            )
          })()}
        </div>
      )}
    </div>
  )
}
