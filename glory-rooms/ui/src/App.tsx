import { useEffect, useState, useCallback } from 'react'
import { api, type Model, type SessionSummary } from './api'
import { Solo } from './modes/Solo'
import { Pipeline } from './modes/Pipeline'
import { Room } from './modes/Room'
import { Debate } from './modes/Debate'
import { SessionDetail } from './modes/SessionDetail'
import { Dashboard } from './modes/Dashboard'
import { AgentEnvironment } from './modes/AgentEnvironment'
import { ModelsRoom } from './modes/ModelsRoom'
import { AgentsRoom } from './modes/AgentsRoom'
import { Glory } from './modes/Glory'
import { SiteInspector } from './modes/SiteInspector'
import { CharacterLayer } from './components/CharacterLayer'
import { UnifiedPipeline } from './components/UnifiedPipeline'

type ModeKey = 'dashboard' | 'glory' | 'solo' | 'pipeline' | 'room' | 'debate' | 'agents' | 'models' | 'scout'

const MODES: { key: ModeKey; label: string; desc: string }[] = [
  { key: 'dashboard', label: 'DASHBOARD', desc: 'System status · shared mind · token metrics' },
  { key: 'glory',     label: 'GLORY',     desc: 'Multi-confirmational — all body parts answer as one' },
  { key: 'models',    label: 'MODELS',    desc: 'Glory body — Gemma · Qwen · Kimi · Hermes' },
  { key: 'agents',    label: 'AGENTS',    desc: 'Active Claude Code agents — live workspace' },
  { key: 'scout',     label: 'SCOUT',     desc: 'Site intelligence — deep backend recon + AI analysis' },
  { key: 'solo',      label: 'SOLO',      desc: 'Single model prompt execution' },
  { key: 'pipeline',  label: 'PIPELINE',  desc: 'Sequential model chain — output feeds input' },
  { key: 'room',      label: 'ROOM',      desc: 'Round-robin multi-model dialog' },
  { key: 'debate',    label: 'DEBATE',    desc: 'Parallel fan-out with synthesis' },
]

function useUptime() {
  const [t, setT] = useState(0)
  useEffect(() => {
    const id = setInterval(() => setT(s => s + 1), 1000)
    return () => clearInterval(id)
  }, [])
  const h = Math.floor(t / 3600).toString().padStart(2, '0')
  const m = Math.floor((t % 3600) / 60).toString().padStart(2, '0')
  const s = (t % 60).toString().padStart(2, '0')
  return `${h}:${m}:${s}`
}

export default function App() {
  const [mode, setMode] = useState<ModeKey>('dashboard')
  const [models, setModels] = useState<Model[]>([])
  const [sessions, setSessions] = useState<SessionSummary[]>([])
  const [openSession, setOpenSession] = useState<string | null>(null)
  const [proxyOnline, setProxyOnline] = useState(false)
  const uptime = useUptime()

  const refreshSessions = useCallback(() => {
    api.sessions().then(r => setSessions(r.sessions)).catch(() => {})
  }, [])

  useEffect(() => {
    api.models()
      .then(r => { setModels(r.models); setProxyOnline(true) })
      .catch(() => setProxyOnline(false))
    refreshSessions()
  }, [refreshSessions])

  const onSession = (sid: string) => { refreshSessions(); void sid }
  const currentMode = MODES.find(m => m.key === mode)!

  const handleNavClick = (key: ModeKey) => {
    setMode(key)
    setOpenSession(null)
  }

  return (
    <div className="h-full flex flex-col" style={{ background: '#0A0700' }}>

      {/* CHARACTER LAYER — fixed overlay, no layout impact */}
      <CharacterLayer />

      {/* TOP NAVBAR */}
      <header
        className="shrink-0 flex items-center border-b border-ink-700 z-50"
        style={{ height: '56px', background: '#0A0700', borderBottomColor: '#2A1E00' }}
      >
        {/* Left: wordmark */}
        <div className="flex items-center gap-3 px-5 shrink-0">
          <span
            className="text-2xl leading-none select-none"
            style={{ textShadow: '0 0 12px rgba(255,215,0,0.6), 0 0 24px rgba(255,149,0,0.3)' }}
            aria-hidden="true"
          >
            ☀
          </span>
          <span
            className="font-display font-bold tracking-widest text-accent-500 text-xl leading-none uppercase"
            style={{ textShadow: '0 0 12px rgba(255,215,0,0.6), 0 0 24px rgba(255,149,0,0.3)' }}
          >
            GLORY
          </span>
        </div>

        {/* Center: nav links */}
        <nav className="flex-1 flex items-center justify-center gap-1 overflow-x-auto px-4">
          {MODES.map(m => {
            const active = mode === m.key && !openSession
            return (
              <button
                key={m.key}
                onClick={() => handleNavClick(m.key)}
                title={m.desc}
                className={[
                  'px-3 py-1 text-sm tracking-widest uppercase font-display transition-colors duration-100 cursor-pointer shrink-0 border-b-2',
                  active
                    ? 'text-accent-500 border-accent-500 solar-glow'
                    : 'text-ink-400 border-transparent hover:text-accent-500 hover:border-accent-500/40',
                ].join(' ')}
              >
                {m.label}
              </button>
            )
          })}
        </nav>

        {/* Right: status strip */}
        <div
          className="flex items-center gap-4 px-5 shrink-0 text-[10px] tracking-[0.18em] font-mono"
          style={{ color: '#6B4E10' }}
        >
          <div className="flex items-center gap-1.5">
            <span
              className={`w-1.5 h-1.5 shrink-0 ${proxyOnline ? 'bg-accent-500 pulse-glow' : 'bg-kimi opacity-60'}`}
            />
            <span style={{ color: proxyOnline ? '#FFD700' : '#7BBFFF' }}>
              {proxyOnline ? 'PROXY:OK' : 'OFFLINE'}
            </span>
          </div>
          <div>
            <span style={{ color: '#E8C878' }}>{models.length}</span>
            <span> MDL</span>
          </div>
          <div style={{ fontVariantNumeric: 'tabular-nums', color: '#8B6820' }}>
            {uptime}
          </div>
        </div>
      </header>

      {/* MAIN CONTENT */}
      <main className="flex-1 overflow-y-auto" style={{ background: '#0A0700' }}>
        <div className="max-w-6xl mx-auto px-6 py-6">

          {/* Mode content */}
          {openSession ? (
            <div className="fade-in">
              <SessionDetail id={openSession} onClose={() => setOpenSession(null)} />
            </div>
          ) : mode === 'dashboard' ? (
            <div className="fade-in">
              <Dashboard onSessionClick={id => setOpenSession(id)} />
            </div>
          ) : mode === 'glory' ? (
            <div className="fade-in">
              <Glory />
            </div>
          ) : mode === 'models' ? (
            <div className="fade-in">
              <ModelsRoom />
            </div>
          ) : mode === 'agents' ? (
            <div className="fade-in">
              <AgentsRoom />
            </div>
          ) : mode === 'scout' ? (
            <div className="fade-in">
              <SiteInspector />
            </div>
          ) : (
            <div className="fade-in">
              <div
                className="mb-6 pb-3 border-b border-ink-700"
                style={{ borderBottomStyle: 'dashed', borderBottomColor: '#2A1E00' }}
              >
                <div className="text-[9px] text-ink-600 tracking-[0.28em] uppercase mb-1">Mode</div>
                <h2 className="font-display font-semibold text-xl text-ink-100 tracking-[0.2em] uppercase">
                  {currentMode.label}
                </h2>
                <p className="text-xs text-ink-500 mt-1 tracking-wider">{currentMode.desc}</p>
              </div>
              {mode === 'solo'     && <Solo     models={models} />}
              {mode === 'pipeline' && <Pipeline models={models} onSession={onSession} />}
              {mode === 'room'     && <Room     models={models} onSession={onSession} />}
              {mode === 'debate'   && <Debate   models={models} onSession={onSession} />}
            </div>
          )}

          {/* Unified pipeline strip — rendered below all mode content */}
          <UnifiedPipeline models={models} />

        </div>
      </main>
    </div>
  )
}
