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

const CANVAS_H = 520
const P = 4

// ── Draw helpers ────────────────────────────────────────────────────────────

function px(ctx: CanvasRenderingContext2D, color: string, x: number, y: number, w: number, h: number) {
  ctx.fillStyle = color
  ctx.fillRect(Math.round(x), Math.round(y), Math.round(w), Math.round(h))
}

function setAlpha(ctx: CanvasRenderingContext2D, status: string) {
  ctx.globalAlpha = status === 'offline' ? 0.22 : 1
}

// ── CLAUDE — phosphor terminal head (HEAD, drawn at 2× scale) ───────────────

function drawClaude(ctx: CanvasRenderingContext2D, cx: number, cy: number, frame: number, status: string) {
  const s = P * 2
  setAlpha(ctx, status)
  ctx.save()

  const glow = status === 'orchestrating'
  if (glow) { ctx.shadowBlur = 18; ctx.shadowColor = '#57ff3b' }

  // Monitor shell
  px(ctx, '#1a2e1a', cx - 5.5 * s, cy - 6 * s, 11 * s, 10 * s)
  // Bezel
  px(ctx, '#0d1a0d', cx - 4.5 * s, cy - 5 * s, 9 * s, 8 * s)
  // Screen bg
  px(ctx, '#010801', cx - 3.5 * s, cy - 4 * s, 7 * s, 6 * s)

  // Scan line
  const scanY = ((frame * 3) % (6 * s))
  ctx.fillStyle = 'rgba(87,255,59,0.18)'
  ctx.fillRect(Math.round(cx - 3.5 * s), Math.round(cy - 4 * s + scanY), Math.round(7 * s), 2)

  // Eyes
  const blink = (Math.floor(frame / 55) % 8) === 0
  if (!blink) {
    ctx.shadowBlur = 8; ctx.shadowColor = '#57ff3b'
    px(ctx, '#57ff3b', cx - 2.5 * s, cy - 2.5 * s, 1.5 * s, 1.5 * s)
    px(ctx, '#57ff3b', cx + 1 * s, cy - 2.5 * s, 1.5 * s, 1.5 * s)
    // Pupils
    px(ctx, '#d8e8da', cx - 2 * s, cy - 2 * s, 0.5 * s, 0.5 * s)
    px(ctx, '#d8e8da', cx + 1.5 * s, cy - 2 * s, 0.5 * s, 0.5 * s)
  } else {
    // Blink lines
    px(ctx, '#38cc1e', cx - 2.5 * s, cy - 2 * s, 1.5 * s, Math.max(2, 0.2 * s))
    px(ctx, '#38cc1e', cx + 1 * s, cy - 2 * s, 1.5 * s, Math.max(2, 0.2 * s))
  }

  // Cursor at bottom of screen
  if (Math.floor(frame / 20) % 2 === 0) {
    ctx.shadowBlur = 6; ctx.shadowColor = '#57ff3b'
    px(ctx, '#57ff3b', cx - 3 * s, cy + 1.2 * s, 1.2 * s, 0.4 * s)
  }

  // Screen border glow lines
  ctx.shadowBlur = 0
  ctx.strokeStyle = '#38cc1e'
  ctx.lineWidth = 1
  ctx.strokeRect(Math.round(cx - 3.5 * s), Math.round(cy - 4 * s), Math.round(7 * s), Math.round(6 * s))

  // Antenna
  px(ctx, '#253028', cx - 0.4 * s, cy - 7.5 * s, 0.8 * s, 1.5 * s)
  px(ctx, '#57ff3b', cx - 1 * s, cy - 8.5 * s, 2 * s, 0.7 * s)
  px(ctx, '#d8e8da', cx - 0.4 * s, cy - 8.8 * s, 0.8 * s, 0.8 * s)

  // Stand/neck
  px(ctx, '#1a2e1a', cx - 1.5 * s, cy + 4 * s, 3 * s, 1 * s)
  px(ctx, '#253028', cx - 3 * s, cy + 5 * s, 6 * s, 0.8 * s)

  // Data particles when orchestrating
  if (status === 'orchestrating') {
    ctx.shadowBlur = 6; ctx.shadowColor = '#57ff3b'
    for (let i = 0; i < 5; i++) {
      const pf = (frame * (1.2 + i * 0.3) + i * 40) % 120
      const px2 = cx + (Math.sin(i * 2.1) * 4 * s)
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

// ── GEMMA — teal circuit leaf ────────────────────────────────────────────────

function drawGemma(ctx: CanvasRenderingContext2D, cx: number, cy: number, frame: number, status: string) {
  const s = P
  setAlpha(ctx, status)
  ctx.save()

  if (status === 'active') { ctx.shadowBlur = 12; ctx.shadowColor = '#22c4a1' }

  // Body (rounded rect via arc+rect)
  ctx.fillStyle = '#22c4a1'
  ctx.beginPath()
  ctx.ellipse(cx, cy - 1 * s, 3 * s, 4 * s, 0, 0, Math.PI * 2)
  ctx.fill()

  // Inner core
  ctx.fillStyle = '#196b56'
  ctx.beginPath()
  ctx.ellipse(cx, cy - 1 * s, 2 * s, 2.5 * s, 0, 0, Math.PI * 2)
  ctx.fill()

  // Circuit veins
  ctx.strokeStyle = '#22c4a1'
  ctx.lineWidth = 1
  ctx.shadowBlur = 0
  ctx.beginPath()
  ctx.moveTo(cx, cy - 4 * s); ctx.lineTo(cx, cy + 2 * s)
  ctx.stroke()
  ctx.beginPath()
  ctx.moveTo(cx, cy - 1.5 * s); ctx.lineTo(cx - 2 * s, cy - 3 * s)
  ctx.stroke()
  ctx.beginPath()
  ctx.moveTo(cx, cy - 1.5 * s); ctx.lineTo(cx + 2 * s, cy - 3 * s)
  ctx.stroke()

  // Leaf ears
  px(ctx, '#196b56', cx - 4 * s, cy - 1 * s, s, 2 * s)
  px(ctx, '#196b56', cx + 3 * s, cy - 1 * s, s, 2 * s)

  // Pulse ring when active
  if (status === 'active') {
    const pulseR = ((frame * 1.5) % (5 * s))
    const pulseAlpha = 1 - pulseR / (5 * s)
    ctx.strokeStyle = `rgba(34,196,161,${pulseAlpha.toFixed(2)})`
    ctx.lineWidth = 1.5
    ctx.beginPath()
    ctx.arc(cx, cy - s, pulseR, 0, Math.PI * 2)
    ctx.stroke()
  }

  ctx.restore()
  ctx.globalAlpha = 1
}

// ── QWEN — amber diamond dragon ──────────────────────────────────────────────

function drawQwen(ctx: CanvasRenderingContext2D, cx: number, cy: number, frame: number, status: string) {
  const s = P
  setAlpha(ctx, status)
  ctx.save()

  if (status === 'active') { ctx.shadowBlur = 14; ctx.shadowColor = '#ffb347' }

  // Wings
  ctx.fillStyle = '#cc7a1e'
  ctx.beginPath()
  ctx.moveTo(cx - 2 * s, cy - s); ctx.lineTo(cx - 6 * s, cy - 3 * s); ctx.lineTo(cx - 5 * s, cy + 2 * s)
  ctx.closePath(); ctx.fill()
  ctx.beginPath()
  ctx.moveTo(cx + 2 * s, cy - s); ctx.lineTo(cx + 6 * s, cy - 3 * s); ctx.lineTo(cx + 5 * s, cy + 2 * s)
  ctx.closePath(); ctx.fill()

  // Diamond body
  ctx.save()
  ctx.translate(cx, cy)
  ctx.rotate(Math.PI / 4)
  px(ctx, '#ffb347', -2.5 * s, -2.5 * s, 5 * s, 5 * s)
  px(ctx, '#cc7a1e', -1.5 * s, -1.5 * s, 3 * s, 3 * s)
  px(ctx, '#ffda80', -0.7 * s, -0.7 * s, 1.4 * s, 1.4 * s)
  ctx.restore()

  // Eyes
  ctx.shadowBlur = 0
  px(ctx, '#fff8e1', cx - 1.5 * s, cy - 1.5 * s, 0.7 * s, 0.7 * s)
  px(ctx, '#fff8e1', cx + 0.8 * s, cy - 1.5 * s, 0.7 * s, 0.7 * s)

  // Fire particles when active
  if (status === 'active') {
    for (let i = 0; i < 4; i++) {
      const pf = (frame * 2 + i * 15) % 50
      const px2 = cx + (i - 1.5) * 2 * s
      const py2 = cy - 4 * s - pf * 0.8
      const alpha = 1 - pf / 50
      const g = Math.floor(100 + (55 - 100) * (pf / 50))
      ctx.fillStyle = `rgba(255,${g},71,${alpha.toFixed(2)})`
      ctx.fillRect(Math.round(px2), Math.round(py2), s, s)
    }
  }

  ctx.restore()
  ctx.globalAlpha = 1
}

// ── KIMI — cyan cloud spirit ─────────────────────────────────────────────────

function drawKimi(ctx: CanvasRenderingContext2D, cx: number, cy: number, frame: number, status: string) {
  const s = P
  const bob = Math.sin(frame / 25) * 3
  const cy2 = cy + bob
  setAlpha(ctx, status)
  ctx.save()

  if (status === 'active') { ctx.shadowBlur = 16; ctx.shadowColor = '#87ceeb' }

  // Cloud body (3 overlapping circles)
  ctx.fillStyle = '#87ceeb'
  ctx.beginPath(); ctx.arc(cx, cy2 - s, 3 * s, 0, Math.PI * 2); ctx.fill()
  ctx.beginPath(); ctx.arc(cx - 2.5 * s, cy2, 2.2 * s, 0, Math.PI * 2); ctx.fill()
  ctx.beginPath(); ctx.arc(cx + 2.5 * s, cy2, 2.2 * s, 0, Math.PI * 2); ctx.fill()
  // Fill bottom
  px(ctx, '#87ceeb', cx - 4.5 * s, cy2, 9 * s, 2 * s)

  // Inner highlight
  ctx.shadowBlur = 0
  ctx.fillStyle = '#b8e4f5'
  ctx.beginPath(); ctx.arc(cx, cy2 - 1.5 * s, 1.5 * s, 0, Math.PI * 2); ctx.fill()

  // Orbiting stars (4-pointed cross)
  const orbitR = 5.5 * s
  for (let i = 0; i < 3; i++) {
    const angle = (frame / 60) * Math.PI * 2 + (i * Math.PI * 2) / 3
    const sx = cx + Math.cos(angle) * orbitR
    const sy = cy2 + Math.sin(angle) * orbitR * 0.5
    ctx.fillStyle = i === 0 ? '#d8e8da' : '#87ceeb'
    // 4-pointed star via two rects
    ctx.fillRect(Math.round(sx - 3), Math.round(sy - 1), 6, 2)
    ctx.fillRect(Math.round(sx - 1), Math.round(sy - 3), 2, 6)
  }

  ctx.restore()
  ctx.globalAlpha = 1
}

// ── HERMES — purple winged messenger ─────────────────────────────────────────

function drawHermes(ctx: CanvasRenderingContext2D, cx: number, cy: number, frame: number, status: string) {
  const s = P
  const legPhase = Math.sin(frame / 7) * s * (status === 'active' ? 1.2 : 0.3)
  setAlpha(ctx, status)
  ctx.save()

  if (status === 'active') { ctx.shadowBlur = 12; ctx.shadowColor = '#c280ff' }

  // Wings
  ctx.fillStyle = '#9b5fe0'
  ctx.beginPath()
  ctx.moveTo(cx - s, cy - s); ctx.lineTo(cx - 5 * s, cy - 4 * s); ctx.lineTo(cx - 4 * s, cy + s)
  ctx.closePath(); ctx.fill()
  ctx.beginPath()
  ctx.moveTo(cx + s, cy - s); ctx.lineTo(cx + 5 * s, cy - 4 * s); ctx.lineTo(cx + 4 * s, cy + s)
  ctx.closePath(); ctx.fill()

  // Body
  px(ctx, '#c280ff', cx - 1.5 * s, cy - 2.5 * s, 3 * s, 5 * s)
  px(ctx, '#9b5fe0', cx - 2 * s, cy - s, 4 * s, 1.5 * s) // chest band

  // Head
  ctx.shadowBlur = 0
  ctx.fillStyle = '#c280ff'
  ctx.beginPath(); ctx.arc(cx, cy - 4 * s, 1.8 * s, 0, Math.PI * 2); ctx.fill()
  // Eye
  px(ctx, '#d8e8da', cx - 0.4 * s, cy - 4.5 * s, 0.8 * s, 0.8 * s)

  // Legs (running animation)
  px(ctx, '#9b5fe0', cx - 1.5 * s, cy + 2.5 * s, s, 2 * s + legPhase)
  px(ctx, '#9b5fe0', cx + 0.5 * s, cy + 2.5 * s, s, 2 * s - legPhase)

  // Speed lines when active
  if (status === 'active') {
    ctx.strokeStyle = 'rgba(194,128,255,0.4)'
    ctx.lineWidth = 1
    for (let i = 0; i < 3; i++) {
      const len = (3 - i) * 2 * s
      ctx.globalAlpha = (0.6 - i * 0.15) * (status === 'offline' ? 0.22 : 1)
      ctx.beginPath()
      ctx.moveTo(cx - 7 * s, cy - 2 * s + i * 1.5 * s)
      ctx.lineTo(cx - 7 * s + len, cy - 2 * s + i * 1.5 * s)
      ctx.stroke()
    }
    ctx.globalAlpha = status === 'offline' ? 0.22 : 1
  }

  ctx.restore()
  ctx.globalAlpha = 1
}

// ── Main component ────────────────────────────────────────────────────────────

export function AgentEnvironment() {
  const canvasRef = useRef<HTMLCanvasElement>(null)
  const frameRef = useRef(0)
  const agentsRef = useRef<GloryAgent[]>([])
  const animRef = useRef(0)
  const [agents, setAgents] = useState<GloryAgent[]>([])
  const [swarmId, setSwarmId] = useState<string | null>(null)
  const [swarmStatus, setSwarmStatus] = useState('offline')

  const fetchAgents = useCallback(async () => {
    try {
      const r = await api.gloryAgents()
      setAgents(r.agents)
      agentsRef.current = r.agents
      setSwarmId(r.swarm_id)
      setSwarmStatus(r.swarm_status)
    } catch {}
  }, [])

  useEffect(() => {
    fetchAgents()
    const poll = setInterval(fetchAgents, 3000)
    return () => clearInterval(poll)
  }, [fetchAgents])

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

      ctx.clearRect(0, 0, W, CANVAS_H)
      ctx.fillStyle = '#090c08'
      ctx.fillRect(0, 0, W, CANVAS_H)

      // Dot grid
      ctx.fillStyle = '#0d120b'
      for (let x = 20; x < W; x += 20)
        for (let y = 20; y < CANVAS_H; y += 20)
          ctx.fillRect(x, y, 1, 1)

      // Header
      ctx.font = `${P * 2}px "Share Tech Mono", monospace`
      ctx.fillStyle = '#1a2e1a'
      ctx.textAlign = 'center'
      ctx.fillText('◈  GLORY AGENT WORKSPACE  ◈', W / 2, P * 5)
      ctx.textAlign = 'left'

      const head = currentAgents.find(a => a.role === 'head')
      const body = currentAgents.filter(a => a.role === 'body')
      const headCY = 175

      // Claude (HEAD) — top center
      if (head) {
        drawClaude(ctx, W / 2, headCY, frame, head.status)

        // Status label
        ctx.textAlign = 'center'
        ctx.font = `bold ${P * 3}px "Share Tech Mono", monospace`
        ctx.shadowBlur = head.status === 'orchestrating' ? 10 : 0
        ctx.shadowColor = '#57ff3b'
        ctx.fillStyle = head.status === 'orchestrating' ? '#57ff3b' : '#3d5040'
        ctx.fillText('CLAUDE', W / 2, headCY + P * 16)
        ctx.shadowBlur = 0
        ctx.font = `${P * 2}px "Share Tech Mono", monospace`
        ctx.fillStyle = '#3d5040'
        ctx.fillText('HEAD  ·  ORCHESTRATOR', W / 2, headCY + P * 19)
        ctx.textAlign = 'left'
      }

      // Body agents row
      if (body.length > 0) {
        const bodyY = 390
        const spacing = W / (body.length + 1)
        const bodyDrawers: Record<string, (ctx: CanvasRenderingContext2D, cx: number, cy: number, f: number, s: string) => void> = {
          gemma: drawGemma, qwen: drawQwen, kimi: drawKimi, hermes: drawHermes,
        }

        body.forEach((agent, i) => {
          const bx = spacing * (i + 1)

          // Connection line from HEAD to active body
          if (agent.status === 'active' && head) {
            const dashOffset = -(frame * 1.5) % 20
            ctx.setLineDash([5, 9])
            ctx.lineDashOffset = dashOffset
            ctx.strokeStyle = 'rgba(87,255,59,0.15)'
            ctx.lineWidth = 1
            ctx.beginPath()
            ctx.moveTo(W / 2, headCY + P * 12)
            ctx.lineTo(bx, bodyY - P * 10)
            ctx.stroke()
            ctx.setLineDash([])
            ctx.lineDashOffset = 0
          }

          // Character
          const drawer = bodyDrawers[agent.id]
          if (drawer) drawer(ctx, bx, bodyY, frame, agent.status)

          // Label
          ctx.textAlign = 'center'
          ctx.font = `bold ${P * 2 + 1}px "Share Tech Mono", monospace`
          ctx.shadowBlur = agent.status === 'active' ? 8 : 0
          ctx.shadowColor = agent.color
          ctx.fillStyle = agent.status !== 'offline' ? agent.color : '#253028'
          ctx.fillText(agent.name.toUpperCase(), bx, bodyY + P * 9)
          ctx.shadowBlur = 0
          ctx.font = `${P * 2}px "Share Tech Mono", monospace`
          ctx.fillStyle = '#253028'
          ctx.fillText(agent.status, bx, bodyY + P * 11)
          ctx.fillText(agent.backend, bx, bodyY + P * 13)
          ctx.textAlign = 'left'
        })
      }

      // Floor line
      ctx.strokeStyle = '#0e120d'
      ctx.lineWidth = 1
      ctx.setLineDash([4, 6])
      ctx.beginPath()
      ctx.moveTo(0, CANVAS_H - 30)
      ctx.lineTo(W, CANVAS_H - 30)
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
      <div className="flex items-center justify-between text-xs font-mono px-1">
        <span className="text-ink-500 tracking-wider">GLORY OS — AGENT WORKSPACE</span>
        <div className="flex items-center gap-4 text-ink-600">
          {swarmId && (
            <span>SWARM <span className="text-accent-500/70">{swarmId.slice(-8)}</span></span>
          )}
          <span className={swarmStatus === 'ready' ? 'text-accent-500' : 'text-ink-700'}>
            {swarmStatus.toUpperCase()}
          </span>
          <span>
            <span className="text-ink-300">{onlineCount}</span>/{agents.length} ONLINE
          </span>
        </div>
      </div>

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

      <div className="grid grid-cols-5 gap-2">
        {agents.map(a => (
          <div
            key={a.id}
            className="border border-ink-700 p-2.5 transition-colors"
            style={{
              borderLeftColor: a.status !== 'offline' ? a.color : '#18201a',
              borderLeftWidth: '2px',
            }}
          >
            <div className="text-xs font-mono mb-0.5" style={{ color: a.status !== 'offline' ? a.color : '#253028' }}>
              {a.name}
            </div>
            <div className="text-[10px] text-ink-600 uppercase tracking-wider">{a.status}</div>
            <div className="text-[10px] text-ink-700">{a.backend}</div>
          </div>
        ))}
      </div>
    </div>
  )
}
