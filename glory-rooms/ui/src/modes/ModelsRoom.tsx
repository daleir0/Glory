import { useEffect, useRef, useState, useCallback } from 'react'
import { api, type Stats } from '../api'

interface GloryAgent {
  id: string
  name: string
  role: 'head' | 'body'
  color: string
  status: string
  backend: string
  description: string
}

interface BodyAgent extends GloryAgent {
  bodyPart: string
  badgeColor: string
}

const BODY_META: Record<string, { part: string; badgeColor: string }> = {
  gemma:  { part: 'LEG',   badgeColor: '#22c4a1' },
  qwen:   { part: 'ARM',   badgeColor: '#ffb347' },
  kimi:   { part: 'CHEST', badgeColor: '#87ceeb' },
  hermes: { part: 'ARM',   badgeColor: '#c280ff' },
}

const P = 4 // pixels per unit

// ─── pixel helpers ────────────────────────────────────────────────────────────

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

// ─── character drawers ────────────────────────────────────────────────────────

function drawGemmaChar(
  ctx: CanvasRenderingContext2D,
  cx: number,
  cy: number,
  frame: number,
  status: string,
) {
  const s = P
  const offline = status === 'offline'
  ctx.globalAlpha = offline ? 0.22 : 1
  ctx.save()

  const pulse = Math.sin(frame / 30) * 0.4 + 0.6
  if (status === 'active') {
    ctx.shadowBlur = 14 * pulse
    ctx.shadowColor = '#22c4a1'
  }

  // Frame 0: neutral, Frame 1 (frame%60>30): slight sway
  const sway = (frame % 60 > 30) ? 1 : 0

  // Roots
  px(ctx, '#196b56', cx - 3 * s, cy + 3 * s + sway, s, 2 * s)
  px(ctx, '#196b56', cx - s, cy + 3.5 * s, s, 1.5 * s)
  px(ctx, '#196b56', cx + s, cy + 3 * s + sway, s, 2 * s)
  px(ctx, '#196b56', cx + 2 * s, cy + 3.5 * s, s, 1.5 * s)

  // Main stem
  px(ctx, '#22c4a1', cx - 0.5 * s, cy - 3 * s, s, 7 * s)

  // Body oval (approximated with rects)
  px(ctx, '#22c4a1', cx - 2 * s, cy - 2 * s, 4 * s, 4 * s)
  px(ctx, '#22c4a1', cx - 1.5 * s, cy - 3 * s, 3 * s, s)
  px(ctx, '#22c4a1', cx - 1.5 * s, cy + 2 * s, 3 * s, s)
  // Inner
  ctx.shadowBlur = 0
  px(ctx, '#196b56', cx - s, cy - s, 2 * s, 2 * s)

  // Top leaf
  px(ctx, '#22c4a1', cx - 1.5 * s, cy - 4 * s, 3 * s, s)
  px(ctx, '#4de8c6', cx - 0.5 * s, cy - 5 * s, s, s)

  // Side buds — frame-animated
  if (frame % 60 < 30) {
    px(ctx, '#22c4a1', cx - 3 * s, cy - s, s, s)
    px(ctx, '#22c4a1', cx + 2 * s, cy - s, s, s)
  } else {
    px(ctx, '#22c4a1', cx - 3.5 * s, cy - 1.5 * s, s, 2 * s)
    px(ctx, '#22c4a1', cx + 2.5 * s, cy - 1.5 * s, s, 2 * s)
  }

  // Active pulse ring
  if (status === 'active') {
    const r = ((frame * 1.2) % (6 * s))
    const a = 1 - r / (6 * s)
    ctx.strokeStyle = `rgba(34,196,161,${a.toFixed(2)})`
    ctx.lineWidth = 1.5
    ctx.beginPath()
    ctx.arc(cx, cy, r, 0, Math.PI * 2)
    ctx.stroke()
  }

  ctx.restore()
  ctx.globalAlpha = 1
}

function drawQwenChar(
  ctx: CanvasRenderingContext2D,
  cx: number,
  cy: number,
  frame: number,
  status: string,
) {
  const s = P
  ctx.globalAlpha = status === 'offline' ? 0.22 : 1
  ctx.save()

  if (status === 'active') {
    ctx.shadowBlur = 12
    ctx.shadowColor = '#ffb347'
  }

  // Arm upper segment — frame toggle for motion
  const reach = (frame % 60 < 30) ? 0 : s * 0.5

  // Upper arm (horizontal)
  px(ctx, '#ffb347', cx - 3 * s, cy - 3 * s, 5 * s, 2 * s)
  // Joint
  px(ctx, '#cc7a1e', cx + 1.5 * s, cy - 3.5 * s, 2 * s, 3 * s)
  // Lower arm (vertical, pointing down-right)
  px(ctx, '#ffb347', cx + 2 * s, cy - 0.5 * s + reach, 2 * s, 3.5 * s)
  // Claw / hand
  ctx.shadowBlur = 0
  px(ctx, '#ffd080', cx + 1 * s, cy + 3 * s + reach, s, s)
  px(ctx, '#ffd080', cx + 2 * s, cy + 3.5 * s + reach, s, s)
  px(ctx, '#ffd080', cx + 3.5 * s, cy + 3 * s + reach, s, s)

  // Shoulder base
  px(ctx, '#cc7a1e', cx - 4 * s, cy - 4 * s, 3 * s, 4 * s)
  px(ctx, '#ffb347', cx - 3.5 * s, cy - 3.5 * s, 2 * s, 3 * s)

  // Active spark
  if (status === 'active') {
    const sf = frame % 20
    if (sf < 10) {
      ctx.shadowBlur = 8
      ctx.shadowColor = '#ffb347'
      px(ctx, '#fff8e1', cx + 2 * s, cy + 4 * s + reach, 2 * s, 2 * s)
    }
  }

  ctx.restore()
  ctx.globalAlpha = 1
}

function drawKimiChar(
  ctx: CanvasRenderingContext2D,
  cx: number,
  cy: number,
  frame: number,
  status: string,
) {
  const s = P
  const beat = Math.sin(frame / 20) * s * 0.3
  ctx.globalAlpha = status === 'offline' ? 0.22 : 1
  ctx.save()

  if (status === 'active') {
    ctx.shadowBlur = 16 + beat * 2
    ctx.shadowColor = '#87ceeb'
  }

  // Heart/shield shape
  // Top lobes
  ctx.fillStyle = '#87ceeb'
  ctx.beginPath()
  ctx.arc(cx - 1.5 * s, cy - 2 * s + beat, 2 * s, 0, Math.PI * 2)
  ctx.fill()
  ctx.beginPath()
  ctx.arc(cx + 1.5 * s, cy - 2 * s + beat, 2 * s, 0, Math.PI * 2)
  ctx.fill()

  // Body fill (trapezoid via rects)
  px(ctx, '#87ceeb', cx - 3 * s, cy - 2 * s + beat, 6 * s, 3 * s)

  // Pointed bottom
  px(ctx, '#87ceeb', cx - 2 * s, cy + 1 * s + beat, 4 * s, s)
  px(ctx, '#87ceeb', cx - s, cy + 2 * s + beat, 2 * s, s)
  px(ctx, '#87ceeb', cx - 0.5 * s, cy + 3 * s + beat, s, s)

  // Inner glow core
  ctx.shadowBlur = 0
  ctx.fillStyle = status === 'active' ? '#b8e4f5' : '#4a8fa0'
  ctx.beginPath()
  ctx.arc(cx, cy - s + beat, s, 0, Math.PI * 2)
  ctx.fill()

  // Pulse rings
  if (status === 'active') {
    for (let i = 0; i < 2; i++) {
      const r = ((frame * 1.5 + i * 30) % (5 * s))
      const a = 1 - r / (5 * s)
      ctx.strokeStyle = `rgba(135,206,235,${(a * 0.7).toFixed(2)})`
      ctx.lineWidth = 1
      ctx.beginPath()
      ctx.arc(cx, cy + beat, r, 0, Math.PI * 2)
      ctx.stroke()
    }
  }

  ctx.restore()
  ctx.globalAlpha = 1
}

function drawHermesChar(
  ctx: CanvasRenderingContext2D,
  cx: number,
  cy: number,
  frame: number,
  status: string,
) {
  const s = P
  const flutter = Math.sin(frame / 8) * s * 0.6
  ctx.globalAlpha = status === 'offline' ? 0.22 : 1
  ctx.save()

  if (status === 'active') {
    ctx.shadowBlur = 12
    ctx.shadowColor = '#c280ff'
  }

  // Wings spread — flutter animation
  ctx.fillStyle = '#9b5fe0'
  // Left wing
  ctx.beginPath()
  ctx.moveTo(cx - s, cy)
  ctx.lineTo(cx - 5 * s, cy - 3 * s - flutter)
  ctx.lineTo(cx - 4 * s, cy + s + flutter)
  ctx.closePath()
  ctx.fill()
  // Right wing
  ctx.beginPath()
  ctx.moveTo(cx + s, cy)
  ctx.lineTo(cx + 5 * s, cy - 3 * s - flutter)
  ctx.lineTo(cx + 4 * s, cy + s + flutter)
  ctx.closePath()
  ctx.fill()

  // Body
  px(ctx, '#c280ff', cx - 1.5 * s, cy - 2 * s, 3 * s, 5 * s)
  // Chest sash
  px(ctx, '#9b5fe0', cx - 2 * s, cy - s, 4 * s, 1.5 * s)

  // Head
  ctx.shadowBlur = 0
  ctx.fillStyle = '#c280ff'
  ctx.beginPath()
  ctx.arc(cx, cy - 3.5 * s, 1.8 * s, 0, Math.PI * 2)
  ctx.fill()
  // Eye
  px(ctx, '#e8d8f8', cx - 0.4 * s, cy - 4 * s, 0.8 * s, 0.8 * s)

  // Message packet (carried)
  const packetX = cx + 1.5 * s
  const packetY = cy + s
  px(ctx, '#d8e8da', packetX, packetY, 2 * s, 1.5 * s)
  px(ctx, '#9b5fe0', packetX + 0.3 * s, packetY + 0.3 * s, 1.4 * s, 0.9 * s)

  // Speed lines when active
  if (status === 'active') {
    for (let i = 0; i < 3; i++) {
      const len = (3 - i) * s * 2
      const alpha = 0.5 - i * 0.12
      ctx.strokeStyle = `rgba(194,128,255,${alpha.toFixed(2)})`
      ctx.lineWidth = 1
      ctx.beginPath()
      ctx.moveTo(cx - 7 * s, cy - s + i * 1.5 * s)
      ctx.lineTo(cx - 7 * s + len, cy - s + i * 1.5 * s)
      ctx.stroke()
    }
  }

  ctx.restore()
  ctx.globalAlpha = 1
}

const CHAR_DRAWERS: Record<
  string,
  (ctx: CanvasRenderingContext2D, cx: number, cy: number, frame: number, status: string) => void
> = {
  gemma: drawGemmaChar,
  qwen: drawQwenChar,
  kimi: drawKimiChar,
  hermes: drawHermesChar,
}

// ─── cell layout ──────────────────────────────────────────────────────────────

const CELL_W = 240
const CELL_H = 260
const CANVAS_W = CELL_W * 2
const CANVAS_H = CELL_H * 2

// Grid positions for each character (cx, cy = center of canvas sprite area)
const CELL_POSITIONS = [
  { col: 0, row: 0 }, // gemma  top-left
  { col: 1, row: 0 }, // qwen   top-right
  { col: 0, row: 1 }, // kimi   bottom-left
  { col: 1, row: 1 }, // hermes bottom-right
]
const AGENT_ORDER = ['gemma', 'qwen', 'kimi', 'hermes']

function formatNum(n: number): string {
  if (n >= 1000) return `${(n / 1000).toFixed(1)}k`
  return String(n)
}

// ─── component ────────────────────────────────────────────────────────────────

export function ModelsRoom() {
  const canvasRef = useRef<HTMLCanvasElement>(null)
  const frameRef = useRef(0)
  const animRef = useRef(0)
  const agentsRef = useRef<BodyAgent[]>([])
  const statsRef = useRef<Stats | null>(null)

  const [agents, setAgents] = useState<BodyAgent[]>([])
  const [stats, setStats] = useState<Stats | null>(null)
  const [swarmStatus, setSwarmStatus] = useState('offline')

  const fetchData = useCallback(async () => {
    try {
      const [agentRes, statsRes] = await Promise.all([
        api.gloryAgents(),
        api.stats(),
      ])
      const body = agentRes.agents
        .filter(a => a.role === 'body')
        .map(a => ({
          ...a,
          bodyPart: BODY_META[a.id]?.part ?? 'PART',
          badgeColor: BODY_META[a.id]?.badgeColor ?? a.color,
        }))
      setAgents(body)
      agentsRef.current = body
      setSwarmStatus(agentRes.swarm_status)
      setStats(statsRes)
      statsRef.current = statsRes
    } catch {
      // proxy offline — keep stale data
    }
  }, [])

  useEffect(() => {
    fetchData()
    const poll = setInterval(fetchData, 3000)
    return () => clearInterval(poll)
  }, [fetchData])

  useEffect(() => {
    const canvas = canvasRef.current
    if (!canvas) return
    const ctx = canvas.getContext('2d')!

    canvas.width = CANVAS_W
    canvas.height = CANVAS_H

    const draw = () => {
      frameRef.current++
      const frame = frameRef.current
      const currentAgents = agentsRef.current

      ctx.clearRect(0, 0, CANVAS_W, CANVAS_H)
      ctx.fillStyle = '#090c08'
      ctx.fillRect(0, 0, CANVAS_W, CANVAS_H)

      // Dot grid
      ctx.fillStyle = '#0d120b'
      for (let x = 12; x < CANVAS_W; x += 12)
        for (let y = 12; y < CANVAS_H; y += 12)
          ctx.fillRect(x, y, 1, 1)

      // Grid lines
      ctx.strokeStyle = '#0e140d'
      ctx.lineWidth = 1
      // vertical center
      ctx.beginPath()
      ctx.moveTo(CANVAS_W / 2, 0)
      ctx.lineTo(CANVAS_W / 2, CANVAS_H)
      ctx.stroke()
      // horizontal center
      ctx.beginPath()
      ctx.moveTo(0, CANVAS_H / 2)
      ctx.lineTo(CANVAS_W, CANVAS_H / 2)
      ctx.stroke()

      // Draw each cell
      AGENT_ORDER.forEach((agentId, idx) => {
        const pos = CELL_POSITIONS[idx]
        const cellX = pos.col * CELL_W
        const cellY = pos.row * CELL_H
        const cx = cellX + CELL_W / 2
        // Center of sprite area — upper 70% of cell
        const cy = cellY + CELL_H * 0.38

        const agent = currentAgents.find(a => a.id === agentId)
        const status = agent?.status ?? 'offline'
        const color = agent?.badgeColor ?? '#253028'

        const drawer = CHAR_DRAWERS[agentId]
        if (drawer) drawer(ctx, cx, cy, frame, status)

        // Cell border glow for active
        if (status === 'active') {
          ctx.strokeStyle = color + '33'
          ctx.lineWidth = 1
          ctx.strokeRect(cellX + 2, cellY + 2, CELL_W - 4, CELL_H - 4)
        }
      })

      animRef.current = requestAnimationFrame(draw)
    }

    animRef.current = requestAnimationFrame(draw)
    return () => cancelAnimationFrame(animRef.current)
  }, [])

  // Per-model stats lookup
  function modelStats(agentId: string) {
    if (!stats) return null
    return stats.models.find(m => m.model.toLowerCase().includes(agentId))
  }

  return (
    <div className="space-y-4">
      {/* Header */}
      <div className="flex items-center justify-between px-1">
        <div>
          <div className="text-[9px] text-ink-600 tracking-[0.28em] uppercase mb-0.5">Glory OS</div>
          <h2 className="text-sm text-ink-100 tracking-[0.2em] uppercase">Body Agents</h2>
        </div>
        <div className="flex items-center gap-4 text-[10px] text-ink-600">
          <span>SWARM <span className={swarmStatus === 'ready' ? 'text-accent-500' : 'text-ink-700'}>{swarmStatus.toUpperCase()}</span></span>
          <span><span className="text-ink-300">{agents.filter(a => a.status !== 'offline').length}</span>/{agents.length} ONLINE</span>
        </div>
      </div>

      {/* Canvas grid */}
      <div className="border border-ink-700 overflow-hidden">
        <canvas
          ref={canvasRef}
          style={{
            width: '100%',
            height: `${CANVAS_H}px`,
            display: 'block',
            imageRendering: 'pixelated',
            maxWidth: `${CANVAS_W}px`,
          }}
        />
      </div>

      {/* Stats grid */}
      <div className="grid grid-cols-2 gap-2">
        {AGENT_ORDER.map(agentId => {
          const agent = agents.find(a => a.id === agentId)
          const mstats = modelStats(agentId)
          const meta = BODY_META[agentId] ?? { part: 'PART', badgeColor: '#253028' }
          const active = agent?.status === 'active'
          const offline = !agent || agent.status === 'offline'

          return (
            <div
              key={agentId}
              className="border border-ink-700 p-3"
              style={{
                borderLeftColor: offline ? '#18201a' : meta.badgeColor,
                borderLeftWidth: '2px',
              }}
            >
              {/* Name + badge */}
              <div className="flex items-center justify-between mb-2">
                <div className="flex items-center gap-2">
                  <span
                    className="text-xs tracking-wider uppercase"
                    style={{ color: offline ? '#253028' : meta.badgeColor }}
                  >
                    {agentId.toUpperCase()}
                  </span>
                  <span
                    className="text-[9px] px-1.5 py-0.5 uppercase tracking-wider"
                    style={{
                      background: offline ? '#18201a' : meta.badgeColor + '22',
                      color: offline ? '#253028' : meta.badgeColor,
                    }}
                  >
                    {meta.part}
                  </span>
                </div>
                <div className="flex items-center gap-1.5">
                  <span
                    className="w-1.5 h-1.5"
                    style={{
                      background: offline ? '#253028' : active ? meta.badgeColor : '#3d5040',
                    }}
                  />
                  <span className="text-[9px] text-ink-600 tracking-wider uppercase">
                    {agent?.status ?? 'offline'}
                  </span>
                </div>
              </div>

              {/* Analytics bar */}
              <div className="space-y-1 text-[10px]">
                {mstats ? (
                  <>
                    <div className="flex justify-between">
                      <span className="text-ink-600">TOKENS IN</span>
                      <span className="text-ink-300">{formatNum(mstats.tokens_in)}</span>
                    </div>
                    <div className="flex justify-between">
                      <span className="text-ink-600">TOKENS OUT</span>
                      <span className="text-ink-300">{formatNum(mstats.tokens_out)}</span>
                    </div>
                    <div className="flex justify-between">
                      <span className="text-ink-600">AVG LATENCY</span>
                      <span className="text-ink-300">{mstats.avg_latency_ms.toFixed(0)}ms</span>
                    </div>
                    <div className="flex justify-between">
                      <span className="text-ink-600">MESSAGES</span>
                      <span className="text-ink-300">{mstats.messages}</span>
                    </div>
                  </>
                ) : (
                  <div className="flex justify-between">
                    <span className="text-ink-700">backend</span>
                    <span className="text-ink-600">{agent?.backend ?? '—'}</span>
                  </div>
                )}
              </div>
            </div>
          )
        })}
      </div>
    </div>
  )
}
