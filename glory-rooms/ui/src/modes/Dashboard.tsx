import { useEffect, useState, useCallback } from 'react'
import { api, type Model, type SessionSummary, type MemoryEntry, type Stats, type PortStatus, type ScheduleEntry, type NetworkDevice, type ResearchResult } from '../api'
import { TaskScheduler } from './TaskScheduler'

type ProxyStatus = 'online' | 'offline' | 'checking'

export function Dashboard({ onSessionClick }: { onSessionClick: (id: string) => void }) {
  const [proxyStatus, setProxyStatus] = useState<ProxyStatus>('checking')
  const [models, setModels] = useState<Model[]>([])
  const [sessions, setSessions] = useState<SessionSummary[]>([])
  const [memory, setMemory] = useState<MemoryEntry[]>([])
  const [stats, setStats] = useState<Stats | null>(null)
  const [newKey, setNewKey] = useState('')
  const [newValue, setNewValue] = useState('')
  const [editingKey, setEditingKey] = useState<string | null>(null)
  const [editValue, setEditValue] = useState('')
  const [lastRefresh, setLastRefresh] = useState<Date | null>(null)
  const [ports, setPorts] = useState<PortStatus[]>([])
  const [schedules, setSchedules] = useState<ScheduleEntry[]>([])
  const [network, setNetwork] = useState<NetworkDevice[]>([])
  const [schTitle, setSchTitle] = useState('')
  const [schCron, setSchCron] = useState('')
  const [schDesc, setSchDesc] = useState('')
  const [researchUrl, setResearchUrl] = useState('')
  const [researchLoading, setResearchLoading] = useState(false)
  const [researchResult, setResearchResult] = useState<ResearchResult | null>(null)
  const [researchError, setResearchError] = useState('')

  // New hero panels state
  const todayKey = new Date().toISOString().slice(0, 10)
  const [dailyNotes, setDailyNotes] = useState<string>(() => localStorage.getItem(`glory-daily-${todayKey}`) ?? '')
  const [portfolio, setPortfolio] = useState<{ name: string; amount: number }[]>(() => {
    try { return JSON.parse(localStorage.getItem('glory-portfolio') ?? '[]') } catch { return [] }
  })
  const [newStreamName, setNewStreamName] = useState('')
  const [newStreamAmount, setNewStreamAmount] = useState('')

  const refresh = useCallback(async () => {
    try {
      const [m, s, mem, st, p, sch, net] = await Promise.all([
        api.models(),
        api.sessions(),
        api.memory.list(),
        api.stats(),
        api.ports(),
        api.schedules.list(),
        api.network(),
      ])
      setModels(m.models)
      setSessions(s.sessions)
      setMemory(mem.entries)
      setStats(st)
      setPorts(p.ports)
      setSchedules(sch.schedules)
      setNetwork(net.devices)
      setProxyStatus('online')
      setLastRefresh(new Date())
    } catch {
      setProxyStatus('offline')
    }
  }, [])

  useEffect(() => {
    refresh()
    const t = setInterval(refresh, 10_000)
    const portsInterval = setInterval(() => {
      api.ports().then(r => setPorts(r.ports)).catch(() => {})
    }, 5_000)
    return () => { clearInterval(t); clearInterval(portsInterval) }
  }, [refresh])

  const addMemory = async () => {
    if (!newKey.trim() || !newValue.trim()) return
    await api.memory.set(newKey.trim(), newValue.trim())
    setNewKey('')
    setNewValue('')
    refresh()
  }

  const saveEdit = async (key: string) => {
    await api.memory.set(key, editValue)
    setEditingKey(null)
    refresh()
  }

  const deleteMemory = async (key: string) => {
    await api.memory.del(key)
    refresh()
  }

  const addSchedule = async () => {
    if (!schTitle.trim()) return
    await api.schedules.add({ title: schTitle.trim(), cron: schCron.trim() || undefined, description: schDesc.trim() || undefined })
    setSchTitle(''); setSchCron(''); setSchDesc('')
    refresh()
  }

  const delSchedule = async (id: string) => {
    await api.schedules.del(id)
    refresh()
  }

  const runResearch = async () => {
    if (!researchUrl.trim()) return
    setResearchLoading(true)
    setResearchError('')
    setResearchResult(null)
    try {
      const r = await api.research(researchUrl.trim())
      setResearchResult(r)
    } catch {
      setResearchError('Fetch failed — check URL and proxy.')
    } finally {
      setResearchLoading(false)
    }
  }

  const addStream = () => {
    const amt = parseFloat(newStreamAmount)
    if (!newStreamName.trim() || isNaN(amt)) return
    const updated = [...portfolio, { name: newStreamName.trim(), amount: amt }]
    setPortfolio(updated)
    localStorage.setItem('glory-portfolio', JSON.stringify(updated))
    setNewStreamName('')
    setNewStreamAmount('')
  }

  const removeStream = (idx: number) => {
    const updated = portfolio.filter((_, i) => i !== idx)
    setPortfolio(updated)
    localStorage.setItem('glory-portfolio', JSON.stringify(updated))
  }

  const portfolioTotal = portfolio.reduce((sum, s) => sum + s.amount, 0)

  // Context window calculation (estimate 200k max)
  const CONTEXT_MAX = 200_000
  const contextUsed = stats ? stats.total_tokens_in + stats.total_tokens_out : 0
  const contextPct = Math.min(100, Math.round((contextUsed / CONTEXT_MAX) * 100))

  // Research feed: sessions from last 24h with mode solo or pipeline
  const oneDayAgo = Date.now() - 24 * 60 * 60 * 1000
  const researchFeed = sessions.filter(s =>
    (s.mode === 'solo' || s.mode === 'pipeline') &&
    new Date(s.updated_at).getTime() > oneDayAgo
  )

  return (
    <div className="space-y-6">

      {/* ── HERO PANELS ── */}

      {/* 1. Context Window Meter */}
      <section>
        <div className="label" style={{ color: '#FFD700' }}>Context Window</div>
        <div className="card" style={{ borderColor: '#2A1E00' }}>
          <div className="flex items-center justify-between mb-2">
            <span className="text-xs font-mono" style={{ color: '#FFD700' }}>CONTEXT WINDOW</span>
            <span className="text-xs font-mono text-ink-400">
              {fmtK(contextUsed)} / {fmtK(CONTEXT_MAX)} tokens · <span style={{ color: '#FFD700' }}>{contextPct}%</span>
            </span>
          </div>
          <div className="w-full rounded-full overflow-hidden" style={{ background: '#1A1200', height: '6px' }}>
            <div
              className="h-full rounded-full transition-all duration-700"
              style={{
                width: `${contextPct}%`,
                background: 'linear-gradient(90deg, #FFD700, #FF9500)',
              }}
            />
          </div>
          <div className="flex justify-between mt-1">
            <span className="text-[10px] text-ink-600">0</span>
            <span className="text-[10px] text-ink-600">200k</span>
          </div>
        </div>
      </section>

      {/* 2. Daily List */}
      <section>
        <div className="label" style={{ color: '#FFD700' }}>Today — {todayKey}</div>
        <div className="card" style={{ borderColor: '#2A1E00' }}>
          <textarea
            className="w-full text-sm font-mono text-ink-200 bg-transparent resize-none outline-none placeholder-ink-700 leading-relaxed"
            style={{ minHeight: '120px' }}
            placeholder="notes, todos, thoughts…"
            value={dailyNotes}
            onChange={e => {
              setDailyNotes(e.target.value)
              localStorage.setItem(`glory-daily-${todayKey}`, e.target.value)
            }}
          />
          <div className="text-[10px] text-ink-700 text-right mt-1">auto-saved</div>
        </div>
      </section>

      {/* 3. Portfolio Panel */}
      <section>
        <div className="label" style={{ color: '#FFD700' }}>Portfolio</div>
        <div className="card space-y-3" style={{ borderColor: '#2A1E00' }}>
          <div className="flex gap-2">
            <input
              className="input flex-1 text-sm"
              placeholder="Stream name"
              value={newStreamName}
              onChange={e => setNewStreamName(e.target.value)}
              onKeyDown={e => e.key === 'Enter' && addStream()}
            />
            <input
              className="input w-32 text-sm"
              placeholder="$/mo"
              type="number"
              value={newStreamAmount}
              onChange={e => setNewStreamAmount(e.target.value)}
              onKeyDown={e => e.key === 'Enter' && addStream()}
            />
            <button
              className="btn-primary shrink-0 cursor-pointer disabled:opacity-40"
              disabled={!newStreamName.trim() || !newStreamAmount.trim()}
              onClick={addStream}
            >
              Add
            </button>
          </div>
          <div className="space-y-1.5">
            {portfolio.length === 0 && (
              <div className="text-xs text-ink-500 italic text-center py-2">No revenue streams yet.</div>
            )}
            {portfolio.map((s, i) => (
              <div key={i} className="flex items-center gap-3 border border-ink-700 px-3 py-2 hover:border-ink-600 transition-colors group">
                <span className="flex-1 text-sm text-ink-200">{s.name}</span>
                <span className="font-mono text-sm" style={{ color: '#FFD700' }}>${s.amount.toLocaleString()}/mo</span>
                <button
                  className="opacity-0 group-hover:opacity-100 text-xs px-2 py-0.5 border border-red-900/40 text-red-400 hover:bg-red-900/20 transition-colors cursor-pointer"
                  onClick={() => removeStream(i)}
                >
                  Del
                </button>
              </div>
            ))}
          </div>
          {portfolio.length > 0 && (
            <div className="flex justify-between items-center border-t border-ink-700 pt-2">
              <span className="text-xs text-ink-500 uppercase tracking-wider">Total Projected</span>
              <span className="font-bold font-mono" style={{ color: '#FFD700' }}>${portfolioTotal.toLocaleString()}/mo</span>
            </div>
          )}
        </div>
      </section>

      {/* 4. Research Feed (24h auto-research) */}
      <section>
        <div className="label" style={{ color: '#FFD700' }}>Research Feed — Last 24h</div>
        <div className="card space-y-1.5" style={{ borderColor: '#2A1E00' }}>
          {researchFeed.length === 0 && (
            <div className="text-xs text-ink-500 italic text-center py-3">No research activity in last 24h.</div>
          )}
          {researchFeed.slice(0, 10).map(s => (
            <button
              key={s.id}
              onClick={() => onSessionClick(s.id)}
              className="w-full text-left flex items-center gap-3 border border-ink-700 px-3 py-2 hover:border-ink-600 transition-colors cursor-pointer"
            >
              <span className="pill bg-ink-800 border border-ink-700 text-ink-300 shrink-0 text-[10px]">{s.mode}</span>
              <span className="text-sm text-ink-200 truncate flex-1">{s.title || <span className="italic text-ink-500">untitled</span>}</span>
              <span className="text-xs text-ink-600 shrink-0">{relTime(s.updated_at)}</span>
            </button>
          ))}
        </div>
      </section>

      {/* ── END HERO PANELS ── */}

      {/* Header row */}
      <div className="flex items-center justify-between">
        <div>
          <h2 className="text-xl font-semibold text-ink-100">Glory OS</h2>
          <p className="text-xs text-ink-500 mt-0.5">
            {lastRefresh ? `Last sync ${relTime(lastRefresh.toISOString())}` : 'Connecting…'}
          </p>
        </div>
        <button className="btn-ghost text-xs cursor-pointer" onClick={refresh}>Refresh</button>
      </div>

      {/* System status cards */}
      <section>
        <div className="label">System</div>
        <div className="grid grid-cols-4 gap-3">
          <StatusCard title="Glory Proxy" sub="localhost:8082" status={proxyStatus} />
          <StatusCard title="LM Studio" sub="localhost:1234" status={proxyStatus === 'online' && models.some(m => m.backend === 'lm-studio') ? 'online' : 'unknown'} />
          <StatusCard title="OpenRouter" sub="cloud API" status={proxyStatus === 'online' && models.some(m => m.backend === 'openrouter') ? 'online' : 'unknown'} />
          <StatusCard title="Sessions DB" sub="SQLite WAL" status={proxyStatus === 'online' ? 'online' : 'offline'} />
        </div>
      </section>

      {/* Models + Token stats */}
      <div className="grid grid-cols-2 gap-4">
        <section>
          <div className="label">Models</div>
          <div className="space-y-2">
            {models.length === 0 && proxyStatus !== 'checking' && (
              <div className="card text-sm text-ink-500 italic">No models registered.</div>
            )}
            {models.map((m) => (
              <div key={m.id} className="card flex items-center justify-between py-3">
                <div className="flex items-center gap-2.5">
                  <span className={`w-2 h-2 rounded-full ${m.backend === 'openrouter' ? 'bg-kimi' : 'bg-gemma'}`} style={{ boxShadow: m.backend === 'openrouter' ? '0 0 6px #ff7a59' : '0 0 6px #22c4a1' }} />
                  <span className="font-mono text-sm text-ink-100">{m.id}</span>
                </div>
                <div className="text-right">
                  <div className="text-xs text-ink-400">{m.backend}</div>
                  <div className="text-xs text-ink-600 font-mono truncate max-w-[140px]">{m.underlying}</div>
                </div>
              </div>
            ))}
          </div>
        </section>

        <section>
          <div className="label">Token Usage</div>
          <div className="space-y-2">
            {!stats && <div className="card text-sm text-ink-500 italic">Loading…</div>}
            {stats?.models.length === 0 && (
              <div className="card text-sm text-ink-500 italic">No usage yet.</div>
            )}
            {stats?.models.map((m) => (
              <div key={m.model} className="card py-3">
                <div className="flex items-center justify-between mb-1.5">
                  <span className="font-mono text-sm text-ink-100">{m.model}</span>
                  <span className="text-xs text-ink-500">{m.messages} msgs</span>
                </div>
                <div className="flex gap-4 text-xs">
                  <span className="text-gemma">{fmtK(m.tokens_in)} in</span>
                  <span className="text-accent-400">{fmtK(m.tokens_out)} out</span>
                  <span className="text-ink-500">{m.avg_latency_ms}ms avg</span>
                </div>
              </div>
            ))}
            {stats && (
              <div className="card py-2.5 border-accent-500/20">
                <div className="flex justify-between text-xs">
                  <span className="text-ink-400">{stats.sessions_total} sessions</span>
                  <span className="text-ink-400">{fmtK(stats.total_tokens_in + stats.total_tokens_out)} tokens total</span>
                </div>
              </div>
            )}
          </div>
        </section>
      </div>

      {/* Shared Mind */}
      <section>
        <div className="label">Shared Mind</div>
        <div className="card space-y-4">
          <p className="text-xs text-ink-500 leading-relaxed">
            Persistent memory shared across all model instances. Pass <code className="font-mono text-accent-400 bg-ink-800 px-1 rounded">inject_memory: true</code> in any Room or Pipeline request to prime models from this shared context.
          </p>

          <div className="flex gap-2">
            <input
              className="input w-36 shrink-0 text-sm"
              placeholder="key"
              value={newKey}
              onChange={(e) => setNewKey(e.target.value)}
              onKeyDown={(e) => e.key === 'Enter' && addMemory()}
            />
            <input
              className="input flex-1 text-sm"
              placeholder="value"
              value={newValue}
              onChange={(e) => setNewValue(e.target.value)}
              onKeyDown={(e) => e.key === 'Enter' && addMemory()}
            />
            <button
              className="btn-primary shrink-0 cursor-pointer disabled:opacity-40"
              disabled={!newKey.trim() || !newValue.trim()}
              onClick={addMemory}
            >
              Add
            </button>
          </div>

          <div className="space-y-2 max-h-72 overflow-y-auto pr-1">
            {memory.length === 0 && (
              <div className="text-xs text-ink-500 italic py-3 text-center">
                No entries yet. The shared mind is empty.
              </div>
            )}
            {memory.map((e) => (
              <div
                key={e.key}
                className="group flex items-start gap-3 border border-ink-700 hover:border-ink-600 rounded-md px-3 py-2.5 transition-colors"
              >
                <div className="flex-1 min-w-0">
                  <div className="flex items-center gap-2 mb-1">
                    <span className="font-mono text-xs text-accent-400">{e.key}</span>
                    <span className="text-ink-600 text-xs">· {e.author}</span>
                    <span className="text-ink-700 text-xs ml-auto">{relTime(e.updated_at)}</span>
                  </div>
                  {editingKey === e.key ? (
                    <div className="flex gap-2 mt-1">
                      <input
                        className="input flex-1 text-xs py-1"
                        value={editValue}
                        autoFocus
                        onChange={(ev) => setEditValue(ev.target.value)}
                        onKeyDown={(ev) => {
                          if (ev.key === 'Enter') saveEdit(e.key)
                          if (ev.key === 'Escape') setEditingKey(null)
                        }}
                      />
                      <button className="btn-primary text-xs px-2.5 py-1 cursor-pointer" onClick={() => saveEdit(e.key)}>Save</button>
                      <button className="btn-ghost text-xs px-2.5 py-1 cursor-pointer" onClick={() => setEditingKey(null)}>Cancel</button>
                    </div>
                  ) : (
                    <p className="text-sm text-ink-200 break-words">{e.value}</p>
                  )}
                </div>
                {editingKey !== e.key && (
                  <div className="flex gap-1 opacity-0 group-hover:opacity-100 transition-opacity shrink-0">
                    <button
                      className="btn-ghost text-xs px-2 py-1 cursor-pointer"
                      onClick={() => { setEditingKey(e.key); setEditValue(e.value) }}
                    >
                      Edit
                    </button>
                    <button
                      className="text-xs px-2 py-1 rounded border border-red-900/40 text-red-400 hover:bg-red-900/20 transition-colors cursor-pointer"
                      onClick={() => deleteMemory(e.key)}
                    >
                      Del
                    </button>
                  </div>
                )}
              </div>
            ))}
          </div>
        </div>
      </section>

      {/* Ports */}
      <section>
        <div className="label">Ports</div>
        <div className="grid grid-cols-3 gap-2">
          {ports.map(p => (
            <div key={p.port} className={`card py-2.5 flex items-center gap-2.5 border-l-2 ${p.status === 'online' ? 'border-accent-500' : 'border-red-700'}`}>
              <span className={`w-1.5 h-1.5 shrink-0 ${p.status === 'online' ? 'bg-accent-500 pulse-glow' : 'bg-red-700'}`} />
              <div className="min-w-0">
                <div className="text-xs text-ink-200 font-mono">{p.service}</div>
                <div className="text-[10px] text-ink-600 font-mono">:{p.port}{p.latency_ms != null ? ` · ${p.latency_ms}ms` : ''}</div>
              </div>
            </div>
          ))}
          {ports.length === 0 && <div className="col-span-3 text-sm text-ink-500 italic">Scanning…</div>}
        </div>
      </section>

      {/* Schedules */}
      <section>
        <div className="label">Schedules</div>
        <div className="card space-y-4">
          <div className="grid grid-cols-3 gap-2">
            <input className="input text-sm col-span-3" placeholder="Title" value={schTitle} onChange={e => setSchTitle(e.target.value)} />
            <input className="input text-sm" placeholder="Cron (optional)" value={schCron} onChange={e => setSchCron(e.target.value)} />
            <input className="input text-sm col-span-2" placeholder="Description (optional)" value={schDesc} onChange={e => setSchDesc(e.target.value)} />
            <button className="btn-primary col-span-3 cursor-pointer disabled:opacity-40" disabled={!schTitle.trim()} onClick={addSchedule}>Add Entry</button>
          </div>
          <div className="space-y-1.5 max-h-64 overflow-y-auto">
            {schedules.length === 0 && <div className="text-xs text-ink-500 italic text-center py-3">No schedules.</div>}
            {schedules.map(s => (
              <div key={s.id} className="flex items-start gap-3 border border-ink-700 px-3 py-2 hover:border-ink-600 transition-colors group">
                <div className="flex-1 min-w-0">
                  <div className="flex items-center gap-2 mb-0.5">
                    <span className={`text-[9px] px-1.5 py-0.5 uppercase tracking-wider ${
                      s.source === 'manual' ? 'bg-ink-800 text-ink-400' :
                      s.source === 'claude-code' ? 'bg-accent-500/10 text-accent-500' :
                      'bg-kimi/10 text-kimi'
                    }`}>{s.source}</span>
                    <span className="text-sm text-ink-200 truncate">{s.title}</span>
                  </div>
                  {s.cron && <div className="font-mono text-xs text-ink-500">{s.cron}</div>}
                  {s.description && <div className="text-xs text-ink-600 truncate">{s.description}</div>}
                </div>
                {s.source === 'manual' && (
                  <button className="opacity-0 group-hover:opacity-100 text-xs px-2 py-1 border border-red-900/40 text-red-400 hover:bg-red-900/20 transition-colors cursor-pointer shrink-0" onClick={() => delSchedule(s.id)}>Del</button>
                )}
              </div>
            ))}
          </div>
        </div>
      </section>

      {/* Network */}
      <section>
        <div className="label">Network</div>
        <div className="space-y-1">
          {network.length === 0 && <div className="text-sm text-ink-500 italic">Scanning ARP table…</div>}
          {network.map(d => (
            <div key={d.ip} className={`card py-2 flex items-center gap-3 ${d.ip === '192.168.0.31' ? 'border-accent-500/40' : ''}`}>
              <span className={`w-1.5 h-1.5 shrink-0 ${d.ip === '192.168.0.31' ? 'bg-accent-500' : 'bg-ink-600'}`} />
              <span className="font-mono text-sm text-ink-200">{d.ip}</span>
              <span className="font-mono text-xs text-ink-600 flex-1">{d.mac}</span>
              <span className="text-[10px] text-ink-700 uppercase tracking-wider">{d.type}</span>
              {d.ip === '192.168.0.31' && <span className="text-[9px] text-accent-500 tracking-wider uppercase">this machine</span>}
            </div>
          ))}
        </div>
      </section>

      {/* Task Scheduler */}
      <TaskScheduler />

      {/* Research */}
      <section>
        <div className="label">Web Researcher</div>
        <div className="card space-y-3">
          <p className="text-xs text-ink-500">Scrape any URL — extracts tech stack, API patterns, links, assets. Saves to Obsidian vault.</p>
          <div className="flex gap-2">
            <input
              className="input flex-1 text-sm"
              placeholder="https://example.com"
              value={researchUrl}
              onChange={e => setResearchUrl(e.target.value)}
              onKeyDown={e => e.key === 'Enter' && runResearch()}
            />
            <button
              className="btn-primary shrink-0 cursor-pointer disabled:opacity-40"
              disabled={!researchUrl.trim() || researchLoading}
              onClick={runResearch}
            >
              {researchLoading ? '…' : 'Scrape'}
            </button>
          </div>

          {researchError && <div className="text-xs text-red-400 font-mono">{researchError}</div>}

          {researchResult && (
            <div className="space-y-3 border-t border-ink-700 pt-3" style={{ borderTopStyle: 'dashed' }}>
              {/* Status row */}
              <div className="flex items-center gap-3 flex-wrap">
                <span className={`text-xs font-mono px-2 py-0.5 ${researchResult.status < 400 ? 'bg-accent-500/10 text-accent-500' : 'bg-red-900/20 text-red-400'}`}>
                  {researchResult.status}
                </span>
                <span className="text-sm text-ink-200 font-mono">{researchResult.domain}</span>
                {researchResult.server && <span className="text-xs text-ink-500">{researchResult.server}</span>}
                {researchResult.saved && (
                  <span className="text-[10px] text-accent-500/70 ml-auto">✓ saved to vault</span>
                )}
              </div>

              {researchResult.title && (
                <div className="text-xs text-ink-300 italic">"{researchResult.title}"</div>
              )}

              {/* Tech stack */}
              {researchResult.tech_stack.length > 0 && (
                <div>
                  <div className="text-[9px] text-ink-600 uppercase tracking-wider mb-1">Tech Stack</div>
                  <div className="flex flex-wrap gap-1.5">
                    {researchResult.tech_stack.map(t => (
                      <span key={t} className="text-[10px] px-1.5 py-0.5 bg-ink-800 text-ink-300 border border-ink-700">{t}</span>
                    ))}
                  </div>
                </div>
              )}

              {/* API patterns */}
              {researchResult.api_patterns.length > 0 && (
                <div>
                  <div className="text-[9px] text-ink-600 uppercase tracking-wider mb-1">API Patterns ({researchResult.api_patterns.length})</div>
                  <div className="max-h-28 overflow-y-auto space-y-0.5">
                    {researchResult.api_patterns.map(p => (
                      <div key={p} className="font-mono text-xs text-accent-400">{p}</div>
                    ))}
                  </div>
                </div>
              )}

              {/* Assets + links summary */}
              <div className="grid grid-cols-3 gap-3 text-center">
                <div className="border border-ink-700 py-2">
                  <div className="text-base text-ink-200 font-mono">{researchResult.assets.length}</div>
                  <div className="text-[9px] text-ink-600 uppercase tracking-wider">Assets</div>
                </div>
                <div className="border border-ink-700 py-2">
                  <div className="text-base text-ink-200 font-mono">{researchResult.links.internal.length}</div>
                  <div className="text-[9px] text-ink-600 uppercase tracking-wider">Int. Links</div>
                </div>
                <div className="border border-ink-700 py-2">
                  <div className="text-base text-ink-200 font-mono">{researchResult.links.external.length}</div>
                  <div className="text-[9px] text-ink-600 uppercase tracking-wider">Ext. Links</div>
                </div>
              </div>

              {/* Obsidian path */}
              {researchResult.obsidian_path && (
                <div className="text-[10px] font-mono text-ink-600 break-all border border-ink-800 px-2 py-1">
                  {researchResult.obsidian_path}
                </div>
              )}
            </div>
          )}
        </div>
      </section>

      {/* Recent sessions */}
      <section>
        <div className="label">Recent Sessions</div>
        <div className="space-y-1.5">
          {sessions.length === 0 && (
            <div className="text-sm text-ink-500 italic">No sessions yet.</div>
          )}
          {sessions.slice(0, 12).map((s) => (
            <button
              key={s.id}
              onClick={() => onSessionClick(s.id)}
              className="w-full text-left card py-2.5 hover:border-ink-600 transition-colors cursor-pointer flex items-center gap-3"
            >
              <span className="pill bg-ink-800 border border-ink-700 text-ink-300 shrink-0">{s.mode}</span>
              <span className="font-mono text-ink-600 text-xs shrink-0">{s.id}</span>
              <span className="text-sm text-ink-300 truncate flex-1">
                {s.title || <span className="italic text-ink-500">untitled</span>}
              </span>
              <span className="text-xs text-ink-700 shrink-0">{relTime(s.updated_at)}</span>
            </button>
          ))}
        </div>
      </section>
    </div>
  )
}

function StatusCard({ title, sub, status }: {
  title: string
  sub: string
  status: 'online' | 'offline' | 'checking' | 'unknown'
}) {
  const dot: Record<string, string> = {
    online: 'bg-gemma shadow-[0_0_6px_#22c4a1]',
    offline: 'bg-red-500 shadow-[0_0_6px_#ef4444]',
    checking: 'bg-yellow-500 animate-pulse',
    unknown: 'bg-ink-700',
  }
  const label: Record<string, string> = {
    online: 'text-gemma',
    offline: 'text-red-400',
    checking: 'text-yellow-400',
    unknown: 'text-ink-600',
  }
  return (
    <div className="card py-3 space-y-2">
      <div className="flex items-center gap-2">
        <span className={`w-2 h-2 rounded-full shrink-0 ${dot[status]}`} />
        <span className="text-sm font-medium text-ink-200 truncate">{title}</span>
      </div>
      <div className="font-mono text-xs text-ink-500">{sub}</div>
      <div className={`text-xs font-semibold uppercase tracking-wide ${label[status]}`}>
        {status}
      </div>
    </div>
  )
}

function fmtK(n: number) {
  if (n >= 1_000_000) return `${(n / 1_000_000).toFixed(1)}M`
  if (n >= 1_000) return `${(n / 1_000).toFixed(1)}k`
  return String(n)
}

function relTime(iso: string) {
  const ms = Date.now() - new Date(iso).getTime()
  const m = Math.floor(ms / 60_000)
  if (m < 1) return 'just now'
  if (m < 60) return `${m}m ago`
  const h = Math.floor(m / 60)
  if (h < 24) return `${h}h ago`
  return `${Math.floor(h / 24)}d ago`
}
