import { useEffect, useRef, useState, useCallback } from 'react'
import { api } from '../api'

interface GloryAgent {
  id: string
  name: string
  role: 'head' | 'body'
  color: string
  status: string
  backend: string
  description: string
}

const CANVAS_H = 400
const P = 4

// ─── draw helpers ─────────────────────────────────────────────────────────────

function px(
  ctx: CanvasRenderingContext2D,
  color: string,
  x: number,
  y: number,
  w: number,
  h: number,
) {
  ctx.fillStyle = color
  ctx.fillRect(Math.round(x), Math.round(y), Math.round(w), Math.round(h))
}

// ─── Claude (HEAD) — large terminal sprite at 2× scale ───────────────────────

function drawClaude(
  ctx: CanvasRenderingContext2D,
  cx: number,
  cy: number,
  frame: number,
  status: string,
) {
  const s = P * 2
  ctx.globalAlpha = status === 'offline' ? 0.22 : 1
  ctx.save()

  if (status === 'orchestrating') {
    ctx.shadowBlur = 18
    ctx.shadowColor = '#57ff3b'
  }

  // Monitor shell
  px(ctx, '#1a2e1a', cx - 5.5 * s, cy - 6 * s, 11 * s, 10 * s)
  // Bezel
  px(ctx, '#0d1a0d', cx - 4.5 * s, cy - 5 * s, 9 * s, 8 * s)
  // Screen bg
  px(ctx, '#010801', cx - 3.5 * s, cy - 4 * s, 7 * s, 6 * s)

  // Scan line
  const scanY = (frame * 3) % (6 * s)
  ctx.fillStyle = 'rgba(87,255,59,0.18)'
  ctx.fillRect(Math.round(cx - 3.5 * s), Math.round(cy - 4 * s + scanY), Math.round(7 * s), 2)

  // Eyes
  const blink = Math.floor(frame / 55) % 8 === 0
  if (!blink) {
    ctx.shadowBlur = 8
    ctx.shadowColor = '#57ff3b'
    px(ctx, '#57ff3b', cx - 2.5 * s, cy - 2.5 * s, 1.5 * s, 1.5 * s)
    px(ctx, '#57ff3b', cx + 1 * s, cy - 2.5 * s, 1.5 * s, 1.5 * s)
    px(ctx, '#d8e8da', cx - 2 * s, cy - 2 * s, 0.5 * s, 0.5 * s)
    px(ctx, '#d8e8da', cx + 1.5 * s, cy - 2 * s, 0.5 * s, 0.5 * s)
  } else {
    px(ctx, '#38cc1e', cx - 2.5 * s, cy - 2 * s, 1.5 * s, Math.max(2, 0.2 * s))
    px(ctx, '#38cc1e', cx + 1 * s, cy - 2 * s, 1.5 * s, Math.max(2, 0.2 * s))
  }

  // Cursor blink
  if (Math.floor(frame / 20) % 2 === 0) {
    ctx.shadowBlur = 6
    ctx.shadowColor = '#57ff3b'
    px(ctx, '#57ff3b', cx - 3 * s, cy + 1.2 * s, 1.2 * s, 0.4 * s)
  }

  // Screen border
  ctx.shadowBlur = 0
  ctx.strokeStyle = '#38cc1e'
  ctx.lineWidth = 1
  ctx.strokeRect(Math.round(cx - 3.5 * s), Math.round(cy - 4 * s), Math.round(7 * s), Math.round(6 * s))

  // Antenna
  px(ctx, '#253028', cx - 0.4 * s, cy - 7.5 * s, 0.8 * s, 1.5 * s)
  px(ctx, '#57ff3b', cx - 1 * s, cy - 8.5 * s, 2 * s, 0.7 * s)
  px(ctx, '#d8e8da', cx - 0.4 * s, cy - 8.8 * s, 0.8 * s, 0.8 * s)

  // Stand/neck
  px(ctx, '#1a2e1a', cx - 1.5 * s, cy + 4 * s, 3 * s, s)
  px(ctx, '#253028', cx - 3 * s, cy + 5 * s, 6 * s, 0.8 * s)

  // Crown symbol
  ctx.shadowBlur = 8
  ctx.shadowColor = '#57ff3b'
  ctx.fillStyle = '#57ff3b'
  const crownY = cy - 10.5 * s
  // 3 teeth
  px(ctx, '#57ff3b', cx - 2.5 * s, crownY, s, 1.5 * s)
  px(ctx, '#57ff3b', cx - 0.5 * s, crownY - s, s, 2.5 * s)
  px(ctx, '#57ff3b', cx + 1.5 * s, crownY, s, 1.5 * s)
  // base
  px(ctx, '#57ff3b', cx - 2.5 * s, crownY + 1.5 * s, 5 * s, s)
  ctx.shadowBlur = 0

  // Orchestrating particles
  if (status === 'orchestrating') {
    ctx.shadowBlur = 6
    ctx.shadowColor = '#57ff3b'
    for (let i = 0; i < 5; i++) {
      const pf = (frame * (1.2 + i * 0.3) + i * 40) % 120
      const px2 = cx + Math.sin(i * 2.1) * 4 * s
      const py2 = cy - 4 * s - pf * 0.6
      const alpha = 1 - pf / 120
      ctx.fillStyle = `rgba(87,255,59,${alpha.toFixed(2)})`
      ctx.fillRect(Math.round(px2), Math.round(py2), Math.max(2, Math.round(0.4 * s)), Math.max(2, Math.round(0.4 * s)))
    }
    ctx.shadowBlur = 0
  }

  ctx.restore()
  ctx.globalAlpha = 1
}

// ─── Generic worker agent sprite ──────────────────────────────────────────────

function drawWorker(
  ctx: CanvasRenderingContext2D,
  cx: number,
  cy: number,
  frame: number,
  color: string,
  status: string,
) {
  const s = P
  const offline = status === 'offline'
  ctx.globalAlpha = offline ? 0.22 : 1
  ctx.save()

  if (status === 'active') {
    ctx.shadowBlur = 8
    ctx.shadowColor = color
  }

  // Walk cycle
  const walk = Math.sin(frame / 12) * s * (status === 'active' ? 0.8 : 0.2)

  // Head
  ctx.fillStyle = color
  ctx.beginPath()
  ctx.arc(cx, cy - 3.5 * s, 1.5 * s, 0, Math.PI * 2)
  ctx.fill()
  // Eye dot
  ctx.shadowBlur = 0
  px(ctx, '#d8e8da', cx - 0.3 * s, cy - 3.8 * s, 0.6 * s, 0.6 * s)

  // Body
  px(ctx, color, cx - s, cy - 2 * s, 2 * s, 3 * s)

  // Arms
  px(ctx, color, cx - 2 * s, cy - 2 * s + walk, s, 0.7 * s)
  px(ctx, color, cx + s, cy - 2 * s - walk, s, 0.7 * s)

  // Legs
  px(ctx, color, cx - s, cy + s, 0.8 * s, 2 * s + walk)
  px(ctx, color, cx + 0.2 * s, cy + s, 0.8 * s, 2 * s - walk)

  ctx.restore()
  ctx.globalAlpha = 1
}

// ─── Message packet ───────────────────────────────────────────────────────────

interface Packet {
  agentIdx: number
  progress: number // 0..1
  direction: 'toHead' | 'fromHead'
}

// ─── component ────────────────────────────────────────────────────────────────

export function AgentsRoom() {
  const canvasRef = useRef<HTMLCanvasElement>(null)
  const frameRef = useRef(0)
  const animRef = useRef(0)
  const agentsRef = useRef<GloryAgent[]>([])
  const packetsRef = useRef<Packet[]>([])

  const [agents, setAgents] = useState<GloryAgent[]>([])
  const [swarmId, setSwarmId] = useState<string | null>(null)
  const [swarmStatus, setSwarmStatus] = useState('offline')
  const [busMessages, setBusMessages] = useState<Array<{ id: number; from_agent: string; to_agent: string; content: string; created_at: string }>>([])
  const [busInput, setBusInput] = useState('')

  const fetchAgents = useCallback(async () => {
    try {
      const r = await api.gloryAgents()
      setAgents(r.agents)
      agentsRef.current = r.agents
      setSwarmId(r.swarm_id)
      setSwarmStatus(r.swarm_status)
    } catch {
      // proxy offline
    }
  }, [])

  useEffect(() => {
    fetchAgents()
    const poll = setInterval(fetchAgents, 3000)
    const busPoll = setInterval(async () => {
      try {
        const r = await api.agentBus.list()
        setBusMessages(r.messages.slice(-20))
      } catch {}
    }, 2000)
    return () => { clearInterval(poll); clearInterval(busPoll) }
  }, [fetchAgents])

  // Spawn packets periodically
  useEffect(() => {
    const id = setInterval(() => {
      const body = agentsRef.current.filter(a => a.role === 'body')
      body.forEach((agent, i) => {
        if (agent.status === 'active' && Math.random() < 0.6) {
          packetsRef.current.push({
            agentIdx: i,
            progress: 0,
            direction: Math.random() < 0.5 ? 'toHead' : 'fromHead',
          })
        }
      })
      // Limit packet count
      if (packetsRef.current.length > 20) {
        packetsRef.current = packetsRef.current.slice(-20)
      }
    }, 800)
    return () => clearInterval(id)
  }, [])

  useEffect(() => {
    const canvas = canvasRef.current
    if (!canvas) return
    const ctx = canvas.getContext('2d')!

    const resize = () => {
      canvas.width = canvas.offsetWidth || 800
      canvas.height = CANVAS_H
    }
    resize()
    const ro = new ResizeObserver(resize)
    ro.observe(canvas.parentElement!)

    const draw = () => {
      frameRef.current++
      const frame = frameRef.current
      const W = canvas.width
      const currentAgents = agentsRef.current
      const head = currentAgents.find(a => a.role === 'head')
      const body = currentAgents.filter(a => a.role === 'body')

      ctx.clearRect(0, 0, W, CANVAS_H)
      ctx.fillStyle = '#090c08'
      ctx.fillRect(0, 0, W, CANVAS_H)

      // Dot grid
      ctx.fillStyle = '#0d120b'
      for (let x = 20; x < W; x += 20)
        for (let y = 20; y < CANVAS_H; y += 20)
          ctx.fillRect(x, y, 1, 1)

      // Header label
      ctx.font = `${P * 2}px "Share Tech Mono", monospace`
      ctx.fillStyle = '#1a2e1a'
      ctx.textAlign = 'center'
      ctx.fillText('◈  GLORY AGENT WORKSPACE  ◈', W / 2, P * 5)
      ctx.textAlign = 'left'

      // Positions
      const headCX = W / 2
      const headCY = 150

      // Worker positions — spread across lower area
      const bodyY = 310
      const spacing = W / (body.length + 1)
      const workerPositions = body.map((_, i) => ({
        x: spacing * (i + 1),
        y: bodyY,
      }))

      // ─── connection lines ───────────────────────────────────────────────────
      body.forEach((agent, i) => {
        const wp = workerPositions[i]
        if (!wp) return

        const active = agent.status === 'active'
        const dashOffset = -(frame * 1.5) % 20
        ctx.setLineDash([5, 9])
        ctx.lineDashOffset = dashOffset
        ctx.strokeStyle = active ? 'rgba(87,255,59,0.18)' : 'rgba(30,50,32,0.5)'
        ctx.lineWidth = 1
        ctx.beginPath()
        ctx.moveTo(headCX, headCY + P * 12)
        ctx.lineTo(wp.x, wp.y - P * 7)
        ctx.stroke()
        ctx.setLineDash([])
        ctx.lineDashOffset = 0
      })

      // ─── packets ────────────────────────────────────────────────────────────
      packetsRef.current = packetsRef.current.filter(pkt => pkt.progress < 1)
      packetsRef.current.forEach(pkt => {
        pkt.progress += 0.012

        const wp = workerPositions[pkt.agentIdx]
        if (!wp) return

        const t = pkt.direction === 'toHead' ? pkt.progress : 1 - pkt.progress
        const lx = wp.x + (headCX - wp.x) * t
        const ly = (wp.y - P * 7) + (headCY + P * 12 - (wp.y - P * 7)) * t

        const alpha = 1 - Math.abs(pkt.progress - 0.5) * 2
        ctx.fillStyle = `rgba(87,255,59,${(alpha * 0.9).toFixed(2)})`
        ctx.shadowBlur = 6
        ctx.shadowColor = '#57ff3b'
        ctx.fillRect(Math.round(lx - 3), Math.round(ly - 2), 6, 4)
        ctx.shadowBlur = 0
      })

      // ─── Claude (HEAD) ───────────────────────────────────────────────────────
      drawClaude(ctx, headCX, headCY, frame, head?.status ?? 'offline')

      ctx.textAlign = 'center'
      ctx.font = `bold ${P * 3}px "Share Tech Mono", monospace`
      ctx.shadowBlur = head?.status === 'orchestrating' ? 10 : 0
      ctx.shadowColor = '#57ff3b'
      ctx.fillStyle = head?.status !== 'offline' ? '#57ff3b' : '#3d5040'
      ctx.fillText('GLORY', headCX, headCY + P * 16)
      ctx.shadowBlur = 0
      ctx.font = `${P * 2}px "Share Tech Mono", monospace`
      ctx.fillStyle = '#3d5040'
      ctx.fillText('HEAD · ORCHESTRATOR', headCX, headCY + P * 19)
      ctx.textAlign = 'left'

      // ─── Body workers ────────────────────────────────────────────────────────
      body.forEach((agent, i) => {
        const wp = workerPositions[i]
        if (!wp) return

        // Subtle drift
        const drift = Math.sin(frame / 90 + i * 1.3) * 4
        const wx = wp.x + drift
        const wy = wp.y

        drawWorker(ctx, wx, wy, frame, agent.color, agent.status)

        // Task badge above
        if (agent.status === 'active') {
          const badgeW = agent.id.length * 6 + 12
          const badgeX = wx - badgeW / 2
          const badgeY = wy - P * 10
          px(ctx, '#0e1a0e', badgeX, badgeY, badgeW, 12)
          ctx.strokeStyle = agent.color + '66'
          ctx.lineWidth = 1
          ctx.strokeRect(Math.round(badgeX), Math.round(badgeY), badgeW, 12)
          ctx.font = `${P * 1.5}px "Share Tech Mono", monospace`
          ctx.fillStyle = agent.color
          ctx.textAlign = 'center'
          ctx.fillText(agent.id.toUpperCase(), wx, badgeY + 9)
        }

        // Name
        ctx.textAlign = 'center'
        ctx.font = `${P * 2}px "Share Tech Mono", monospace`
        ctx.shadowBlur = agent.status === 'active' ? 6 : 0
        ctx.shadowColor = agent.color
        ctx.fillStyle = agent.status !== 'offline' ? agent.color : '#253028'
        ctx.fillText(agent.name.toUpperCase(), wx, wy + P * 9)
        ctx.shadowBlur = 0
        ctx.fillStyle = '#253028'
        ctx.font = `${P * 1.8}px "Share Tech Mono", monospace`
        ctx.fillText(agent.status, wx, wy + P * 11.5)
        ctx.textAlign = 'left'
      })

      // ─── Floor line ─────────────────────────────────────────────────────────
      ctx.strokeStyle = '#0e120d'
      ctx.lineWidth = 1
      ctx.setLineDash([4, 6])
      ctx.beginPath()
      ctx.moveTo(0, CANVAS_H - 24)
      ctx.lineTo(W, CANVAS_H - 24)
      ctx.stroke()
      ctx.setLineDash([])

      animRef.current = requestAnimationFrame(draw)
    }

    animRef.current = requestAnimationFrame(draw)
    return () => {
      cancelAnimationFrame(animRef.current)
      ro.disconnect()
    }
  }, [])

  const onlineCount = agents.filter(a => a.status !== 'offline').length

  return (
    <div className="space-y-3">
      {/* Status bar */}
      <div className="flex items-center justify-between text-xs px-1">
        <span className="text-ink-500 tracking-wider">GLORY OS — AGENT WORKSPACE</span>
        <div className="flex items-center gap-4 text-ink-600">
          {swarmId && (
            <span>
              SWARM <span className="text-accent-500/70">{swarmId.slice(-8)}</span>
            </span>
          )}
          <span className={swarmStatus === 'ready' ? 'text-accent-500' : 'text-ink-700'}>
            {swarmStatus.toUpperCase()}
          </span>
          <span>
            <span className="text-ink-300">{onlineCount}</span>/{agents.length} ONLINE
          </span>
        </div>
      </div>

      {/* Canvas */}
      <div className="border border-ink-700 overflow-hidden">
        <canvas
          ref={canvasRef}
          style={{
            width: '100%',
            height: `${CANVAS_H}px`,
            display: 'block',
            imageRendering: 'pixelated',
          }}
        />
      </div>

      {/* Agent status cards */}
      <div className="grid grid-cols-5 gap-2">
        {agents.map(a => (
          <div
            key={a.id}
            className="border border-ink-700 p-2.5 transition-colors"
            style={{ borderLeftColor: a.status !== 'offline' ? a.color : '#18201a', borderLeftWidth: '2px' }}
          >
            <div className="text-xs mb-0.5" style={{ color: a.status !== 'offline' ? a.color : '#253028' }}>
              {a.name}
            </div>
            <div className="text-[10px] text-ink-600 uppercase tracking-wider">{a.status}</div>
            <div className="text-[10px] text-ink-700">{a.backend}</div>
          </div>
        ))}
      </div>

      {/* Agent Communication Bus */}
      <div className="border border-ink-700" style={{ borderTopColor: '#57ff3b33', borderTopWidth: '1px' }}>
        <div className="flex items-center gap-2 px-3 py-2 border-b border-ink-800">
          <span className="w-1.5 h-1.5 bg-accent-500 pulse-glow" />
          <span className="text-[10px] text-ink-400 uppercase tracking-[0.2em]">Agent Communication Bus</span>
          <span className="text-[10px] text-ink-700 ml-auto">{busMessages.length} messages</span>
        </div>

        {/* Message log */}
        <div className="h-40 overflow-y-auto p-2 space-y-1 font-mono" style={{ background: '#030503' }}>
          {busMessages.length === 0 && (
            <div className="text-[10px] text-ink-700 text-center py-4 italic">No messages — agents are idle</div>
          )}
          {busMessages.map(m => {
            const agentColor: Record<string, string> = {
              claude: '#57ff3b', gemma: '#22c4a1', qwen: '#ffb347', kimi: '#87ceeb', hermes: '#c280ff'
            }
            const col = agentColor[m.from_agent.toLowerCase()] || '#5a7560'
            return (
              <div key={m.id} className="flex items-start gap-2 text-[10px]">
                <span className="shrink-0" style={{ color: col }}>{m.from_agent}</span>
                <span className="text-ink-700 shrink-0">→</span>
                <span className="text-ink-600 shrink-0">{m.to_agent}</span>
                <span className="text-ink-400 flex-1 break-words">{m.content}</span>
                <span className="text-ink-800 shrink-0 text-[9px]">
                  {new Date(m.created_at).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit', second: '2-digit' })}
                </span>
              </div>
            )
          })}
        </div>

        {/* Send message input */}
        <div className="flex gap-2 p-2 border-t border-ink-800">
          <span className="text-[10px] text-accent-500 font-mono self-center shrink-0">glory→</span>
          <input
            className="input flex-1 text-xs py-1"
            placeholder="Send message to agent bus…"
            value={busInput}
            onChange={e => setBusInput(e.target.value)}
            onKeyDown={async e => {
              if (e.key === 'Enter' && busInput.trim()) {
                await api.agentBus.post('glory', busInput.trim())
                setBusInput('')
                const r = await api.agentBus.list()
                setBusMessages(r.messages.slice(-20))
              }
            }}
          />
        </div>
      </div>
    </div>
  )
}
