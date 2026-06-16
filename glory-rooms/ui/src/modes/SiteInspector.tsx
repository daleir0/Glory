import { useState, useRef } from 'react'

interface ScoutResult {
  url: string
  domain: string
  status: number
  server: string
  powered_by: string
  title: string
  description: string
  og: Record<string, string>
  tech_stack: string[]
  security_audit: { header: string; present: boolean; value: string | null; risk: string }[]
  security_score: string
  all_headers: Record<string, string>
  cookies: { raw: string; httponly: boolean; secure: boolean; samesite: string | null }[]
  api_patterns: string[]
  secrets_found: { type: string; count: number; sample: string }[]
  forms: { action: string; method: string; inputs: { type: string; name: string }[] }[]
  assets: { url: string; type: string }[]
  links: { internal: string[]; external: string[] }
  probe_results: { path: string; status: number | null; content_type: string; size: number }[]
  robots: { status: number | null; disallowed: string[] }
  sitemap: { status: number | null; urls: string[] }
  ai_summary: string | null
  ai_error: string | null
}

const SEC_COLOR: Record<string, string> = { low: '#57ff3b', high: '#ff4444', medium: '#ffb347' }
const STATUS_COLOR = (s: number | null) => {
  if (!s) return '#555'
  if (s < 300) return '#57ff3b'
  if (s < 400) return '#ffb347'
  if (s === 403) return '#c280ff'
  if (s === 404) return '#555'
  return '#ff4444'
}

function Panel({ title, children, defaultOpen = true }: { title: string; children: React.ReactNode; defaultOpen?: boolean }) {
  const [open, setOpen] = useState(defaultOpen)
  return (
    <div className="border border-ink-700 mb-3" style={{ background: '#0a0f09' }}>
      <button
        onClick={() => setOpen(o => !o)}
        className="w-full flex items-center justify-between px-4 py-2.5 text-left"
        style={{ background: '#050805' }}
      >
        <span className="text-accent-500 text-xs tracking-[0.2em] font-mono">{title}</span>
        <span className="text-ink-600 text-xs">{open ? '▲' : '▼'}</span>
      </button>
      {open && <div className="px-4 py-3">{children}</div>}
    </div>
  )
}

function Badge({ color, children }: { color: string; children: React.ReactNode }) {
  return (
    <span
      className="inline-block text-[10px] px-1.5 py-0.5 tracking-wider mr-1 mb-1"
      style={{ background: color + '22', color, border: `1px solid ${color}44`, fontFamily: 'inherit' }}
    >
      {children}
    </span>
  )
}

function Row({ label, value, mono = true }: { label: string; value: React.ReactNode; mono?: boolean }) {
  return (
    <div className="flex gap-3 mb-1.5 text-xs">
      <span className="text-ink-500 shrink-0" style={{ minWidth: '140px' }}>{label}</span>
      <span className={`text-ink-200 break-all ${mono ? 'font-mono' : ''}`}>{value}</span>
    </div>
  )
}

export function SiteInspector() {
  const [url, setUrl] = useState('')
  const [loading, setLoading] = useState(false)
  const [result, setResult] = useState<ScoutResult | null>(null)
  const [error, setError] = useState<string | null>(null)
  const inputRef = useRef<HTMLInputElement>(null)

  async function runScan() {
    if (!url.trim() || loading) return
    setLoading(true)
    setResult(null)
    setError(null)
    try {
      const resp = await fetch('/v1/scout', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ url: url.trim() }),
      })
      const data = await resp.json()
      if (!resp.ok) throw new Error(data.error?.message || `HTTP ${resp.status}`)
      setResult(data)
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : String(e))
    } finally {
      setLoading(false)
    }
  }

  function handleKey(e: React.KeyboardEvent) {
    if (e.key === 'Enter') runScan()
  }

  const secPassed = result ? result.security_audit.filter(s => s.present).length : 0
  const secTotal = result ? result.security_audit.length : 0
  const secPct = secTotal > 0 ? Math.round((secPassed / secTotal) * 100) : 0

  return (
    <div className="h-full flex flex-col overflow-hidden font-mono" style={{ background: '#090c08' }}>
      {/* URL Input Bar */}
      <div
        className="shrink-0 border-b border-ink-700 flex items-center gap-3 px-5 py-3"
        style={{ background: '#050805' }}
      >
        <span className="text-accent-500 text-xs tracking-[0.2em] shrink-0">SCOUT TARGET</span>
        <input
          ref={inputRef}
          value={url}
          onChange={e => setUrl(e.target.value)}
          onKeyDown={handleKey}
          placeholder="https://example.com"
          className="flex-1 bg-transparent border border-ink-700 text-ink-200 text-xs px-3 py-1.5 outline-none focus:border-accent-500 transition-colors font-mono"
          style={{ caretColor: '#57ff3b' }}
          disabled={loading}
        />
        <button
          onClick={runScan}
          disabled={loading || !url.trim()}
          className="shrink-0 px-5 py-1.5 text-xs tracking-[0.15em] transition-colors disabled:opacity-40"
          style={{
            background: loading ? '#1a2a1a' : '#57ff3b22',
            border: '1px solid #57ff3b55',
            color: '#57ff3b',
          }}
        >
          {loading ? 'SCANNING...' : 'SCAN'}
        </button>
      </div>

      {/* Loading bar */}
      {loading && (
        <div className="shrink-0 h-0.5" style={{ background: '#111' }}>
          <div
            className="h-full"
            style={{ background: '#57ff3b', width: '60%', animation: 'pulse 1.5s ease-in-out infinite' }}
          />
        </div>
      )}

      {/* Results */}
      <div className="flex-1 overflow-y-auto p-4">
        {error && (
          <div className="border border-red-800 p-4 mb-4 text-xs text-red-400">
            SCAN ERROR: {error}
          </div>
        )}

        {!result && !loading && !error && (
          <div className="flex items-center justify-center h-full">
            <div className="text-center">
              <div className="text-ink-600 text-xs tracking-[0.3em] mb-3">SITE INTELLIGENCE SCANNER</div>
              <div className="text-ink-700 text-[10px] tracking-wider">
                Enter a URL above to begin deep recon
              </div>
            </div>
          </div>
        )}

        {result && (
          <div>
            {/* Header summary */}
            <div
              className="border border-accent-500 p-4 mb-4"
              style={{ background: '#0d1a0d', boxShadow: '0 0 20px rgba(87,255,59,0.05)' }}
            >
              <div className="flex items-start justify-between gap-4 flex-wrap">
                <div>
                  <div className="text-accent-500 text-sm tracking-wider mb-1">{result.domain}</div>
                  <div className="text-ink-400 text-xs mb-2">{result.title || '(no title)'}</div>
                  {result.description && (
                    <div className="text-ink-600 text-[10px] max-w-xl">{result.description}</div>
                  )}
                </div>
                <div className="text-right shrink-0">
                  <div className="text-xs mb-1">
                    <span className="text-ink-500">STATUS </span>
                    <span style={{ color: STATUS_COLOR(result.status) }}>{result.status}</span>
                  </div>
                  <div className="text-xs mb-1">
                    <span className="text-ink-500">SERVER </span>
                    <span className="text-ink-200">{result.server || '—'}</span>
                  </div>
                  {result.powered_by && (
                    <div className="text-xs mb-1">
                      <span className="text-ink-500">POWERED BY </span>
                      <span className="text-ink-200">{result.powered_by}</span>
                    </div>
                  )}
                  <div className="text-xs">
                    <span className="text-ink-500">SECURITY </span>
                    <span style={{ color: secPct > 60 ? '#57ff3b' : secPct > 30 ? '#ffb347' : '#ff4444' }}>
                      {result.security_score} ({secPct}%)
                    </span>
                  </div>
                </div>
              </div>

              {result.tech_stack.length > 0 && (
                <div className="mt-3 pt-3 border-t border-ink-800">
                  <div className="text-ink-600 text-[10px] tracking-wider mb-2">TECH STACK</div>
                  <div>{result.tech_stack.map(t => <Badge key={t} color="#57ff3b">{t}</Badge>)}</div>
                </div>
              )}
            </div>

            {/* AI Summary */}
            {(result.ai_summary || result.ai_error) && (
              <Panel title="AI ANALYSIS — GEMMA">
                {result.ai_error ? (
                  <div className="text-red-400 text-xs">{result.ai_error}</div>
                ) : (
                  <div className="text-ink-300 text-xs leading-relaxed whitespace-pre-wrap">
                    {result.ai_summary}
                  </div>
                )}
              </Panel>
            )}

            {/* Security Audit */}
            <Panel title="SECURITY HEADERS">
              <div className="grid grid-cols-1 gap-1">
                {result.security_audit.map(s => (
                  <div key={s.header} className="flex items-start gap-3 text-xs py-1 border-b border-ink-800">
                    <span
                      className="shrink-0 text-[9px] px-1.5 py-0.5 tracking-wider"
                      style={{
                        background: s.present ? '#57ff3b22' : '#ff444422',
                        color: s.present ? '#57ff3b' : '#ff4444',
                        border: `1px solid ${s.present ? '#57ff3b44' : '#ff444444'}`,
                      }}
                    >
                      {s.present ? 'PASS' : 'MISS'}
                    </span>
                    <div className="flex-1 min-w-0">
                      <span className="text-ink-300">{s.header}</span>
                      {s.value && (
                        <div className="text-ink-600 text-[10px] truncate mt-0.5">{s.value}</div>
                      )}
                    </div>
                  </div>
                ))}
              </div>
            </Panel>

            {/* Secrets */}
            {result.secrets_found.length > 0 && (
              <Panel title={`SECRETS DETECTED (${result.secrets_found.length})`}>
                {result.secrets_found.map((s, i) => (
                  <div key={i} className="mb-2 p-2 border border-red-900" style={{ background: '#1a0808' }}>
                    <div className="text-red-400 text-xs mb-1">{s.type} × {s.count}</div>
                    <div className="text-ink-500 text-[10px] font-mono break-all">{s.sample}</div>
                  </div>
                ))}
              </Panel>
            )}

            {/* API Patterns */}
            {result.api_patterns.length > 0 && (
              <Panel title={`API ENDPOINTS (${result.api_patterns.length})`}>
                <div className="grid grid-cols-2 gap-1">
                  {result.api_patterns.map((p, i) => (
                    <div key={i} className="text-[10px] text-ink-400 truncate">{p}</div>
                  ))}
                </div>
              </Panel>
            )}

            {/* Path Probes */}
            <Panel title="PATH PROBE RESULTS" defaultOpen={false}>
              <div className="grid grid-cols-2 gap-1">
                {result.probe_results.map(p => (
                  <div key={p.path} className="flex items-center gap-2 text-[10px]">
                    <span style={{ color: STATUS_COLOR(p.status), minWidth: '32px' }}>
                      {p.status ?? '—'}
                    </span>
                    <span className="text-ink-500 truncate">{p.path}</span>
                  </div>
                ))}
              </div>
            </Panel>

            {/* All HTTP Headers */}
            <Panel title="HTTP RESPONSE HEADERS" defaultOpen={false}>
              {Object.entries(result.all_headers).map(([k, v]) => (
                <Row key={k} label={k} value={v} />
              ))}
            </Panel>

            {/* Cookies */}
            {result.cookies.length > 0 && (
              <Panel title={`COOKIES (${result.cookies.length})`} defaultOpen={false}>
                {result.cookies.map((c, i) => (
                  <div key={i} className="mb-2 text-xs border-b border-ink-800 pb-2">
                    <div className="text-ink-200 mb-1 break-all">{c.raw}</div>
                    <div className="flex gap-2">
                      <Badge color={c.httponly ? '#57ff3b' : '#ff4444'}>
                        {c.httponly ? 'HttpOnly' : 'NO HttpOnly'}
                      </Badge>
                      <Badge color={c.secure ? '#57ff3b' : '#ff4444'}>
                        {c.secure ? 'Secure' : 'NO Secure'}
                      </Badge>
                      {c.samesite && <Badge color="#c280ff">{c.samesite}</Badge>}
                    </div>
                  </div>
                ))}
              </Panel>
            )}

            {/* Forms */}
            {result.forms.length > 0 && (
              <Panel title={`FORMS (${result.forms.length})`} defaultOpen={false}>
                {result.forms.map((f, i) => (
                  <div key={i} className="mb-3 text-xs border-b border-ink-800 pb-3">
                    <Row label="action" value={f.action || '(none)'} />
                    <Row label="method" value={f.method.toUpperCase()} />
                    {f.inputs.length > 0 && (
                      <div className="ml-2 mt-1">
                        {f.inputs.map((inp, j) => (
                          <div key={j} className="text-ink-600 text-[10px]">
                            [{inp.type}] {inp.name}
                          </div>
                        ))}
                      </div>
                    )}
                  </div>
                ))}
              </Panel>
            )}

            {/* Robots */}
            <Panel title="ROBOTS.TXT" defaultOpen={false}>
              <Row label="status" value={String(result.robots.status ?? 'unreachable')} />
              {result.robots.disallowed.length > 0 ? (
                <div>
                  <div className="text-ink-600 text-[10px] mb-1">Disallowed paths:</div>
                  {result.robots.disallowed.map((p, i) => (
                    <div key={i} className="text-ink-400 text-[10px]">{p}</div>
                  ))}
                </div>
              ) : (
                <div className="text-ink-700 text-[10px]">No disallowed paths</div>
              )}
            </Panel>

            {/* Sitemap */}
            {result.sitemap.urls.length > 0 && (
              <Panel title={`SITEMAP (${result.sitemap.urls.length} urls)`} defaultOpen={false}>
                {result.sitemap.urls.slice(0, 20).map((u, i) => (
                  <div key={i} className="text-ink-500 text-[10px] truncate">{u}</div>
                ))}
              </Panel>
            )}

            {/* OpenGraph */}
            {Object.keys(result.og).length > 0 && (
              <Panel title="OPENGRAPH / SOCIAL META" defaultOpen={false}>
                {Object.entries(result.og).map(([k, v]) => (
                  <Row key={k} label={`og:${k}`} value={v} mono={false} />
                ))}
              </Panel>
            )}

            {/* Assets */}
            {result.assets.length > 0 && (
              <Panel title={`ASSETS (${result.assets.length})`} defaultOpen={false}>
                {result.assets.map((a, i) => (
                  <div key={i} className="flex gap-2 text-[10px] mb-1">
                    <Badge color={a.type === 'script' ? '#ffb347' : '#87ceeb'}>{a.type}</Badge>
                    <span className="text-ink-500 truncate">{a.url}</span>
                  </div>
                ))}
              </Panel>
            )}

            {/* Links */}
            <Panel title={`LINKS — ${result.links.internal.length} internal / ${result.links.external.length} external`} defaultOpen={false}>
              <div className="mb-3">
                <div className="text-ink-600 text-[10px] mb-1">INTERNAL</div>
                {result.links.internal.slice(0, 30).map((l, i) => (
                  <div key={i} className="text-ink-500 text-[10px] truncate">{l}</div>
                ))}
              </div>
              <div>
                <div className="text-ink-600 text-[10px] mb-1">EXTERNAL</div>
                {result.links.external.slice(0, 20).map((l, i) => (
                  <div key={i} className="text-ink-500 text-[10px] truncate">{l}</div>
                ))}
              </div>
            </Panel>
          </div>
        )}
      </div>
    </div>
  )
}
