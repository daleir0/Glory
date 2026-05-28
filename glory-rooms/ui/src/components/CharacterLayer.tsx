import { useState, useEffect, useCallback, useRef } from 'react'

// ─── Types ────────────────────────────────────────────────────────────────────

interface CharacterDef {
  id: string
  name: string
  model: string
  primary: string
  secondary: string
  thoughts: string[]
}

interface ActiveWalk {
  characterId: string
  direction: 'left' | 'right'
  showBubble: boolean
  bubbleText: string
  startedAt: number
  durationMs: number
}

// ─── Character Definitions ────────────────────────────────────────────────────

const CHARACTERS: CharacterDef[] = [
  {
    id: 'sol',
    name: 'Sol',
    model: 'Claude',
    primary: '#FFD700',
    secondary: '#FFFEF0',
    thoughts: [
      'Processing...',
      'Routing prompt...',
      'All systems nominal',
      'Calibrating response...',
      'Wisdom engaged.',
    ],
  },
  {
    id: 'gem',
    name: 'Gem',
    model: 'Gemma',
    primary: '#2DDDB0',
    secondary: '#A5F3FC',
    thoughts: [
      'Gemma active',
      'Crystal clear',
      'Analyzing patterns',
      'Prism mode on',
      'Frequencies aligned',
    ],
  },
  {
    id: 'sage',
    name: 'Sage',
    model: 'Qwen',
    primary: '#A78BFA',
    secondary: '#F5C842',
    thoughts: [
      'Qwen reasoning',
      'Consulting scrolls...',
      'Deep thought',
      'Ancient wisdom unlocked',
      'The owl sees all',
    ],
  },
  {
    id: 'hermes',
    name: 'Hermes',
    model: 'Hermes',
    primary: '#E2E8F0',
    secondary: '#94A3B8',
    thoughts: [
      'Message delivered',
      'Running research',
      'On the move',
      'Dispatching agent...',
      'Wind at my back',
    ],
  },
  {
    id: 'luna',
    name: 'Luna',
    model: 'Kimi',
    primary: '#7BBFFF',
    secondary: '#C7D2FE',
    thoughts: [
      'Kimi navigating',
      'Charting course',
      'Reading the stars',
      'Lunar cycle active',
      'Stars aligned',
    ],
  },
]

// ─── SVG Sprite Components ────────────────────────────────────────────────────

function SolSprite({ primary, secondary }: { primary: string; secondary: string }) {
  return (
    <svg width="48" height="64" viewBox="0 0 12 16" xmlns="http://www.w3.org/2000/svg" style={{ imageRendering: 'pixelated' }}>
      {/* Crown points */}
      <rect x="2" y="0" width="2" height="2" fill={primary} />
      <rect x="5" y="0" width="2" height="2" fill={primary} />
      <rect x="8" y="0" width="2" height="2" fill={primary} />
      {/* Crown base */}
      <rect x="2" y="2" width="8" height="1" fill={primary} />
      {/* Head */}
      <rect x="3" y="3" width="6" height="5" fill={secondary} />
      {/* Eyes */}
      <rect x="4" y="5" width="1" height="1" fill="#8B6914" />
      <rect x="7" y="5" width="1" height="1" fill="#8B6914" />
      {/* Halo glow ring */}
      <rect x="1" y="3" width="1" height="5" fill={primary} opacity="0.5" />
      <rect x="10" y="3" width="1" height="5" fill={primary} opacity="0.5" />
      {/* Body / robe */}
      <rect x="3" y="8" width="6" height="5" fill={primary} />
      {/* Cape */}
      <rect x="1" y="8" width="2" height="4" fill="#C8A000" />
      <rect x="9" y="8" width="2" height="4" fill="#C8A000" />
      {/* Belt */}
      <rect x="3" y="12" width="6" height="1" fill="#C8A000" />
      {/* Legs */}
      <rect x="4" y="13" width="2" height="3" fill={secondary} />
      <rect x="7" y="13" width="2" height="3" fill={secondary} />
      {/* Boots */}
      <rect x="3" y="15" width="3" height="1" fill="#8B6914" />
      <rect x="6" y="15" width="3" height="1" fill="#8B6914" />
    </svg>
  )
}

function GemSprite({ primary, secondary }: { primary: string; secondary: string }) {
  return (
    <svg width="48" height="64" viewBox="0 0 12 16" xmlns="http://www.w3.org/2000/svg" style={{ imageRendering: 'pixelated' }}>
      {/* Fairy wings (left) */}
      <rect x="0" y="6" width="3" height="2" fill={secondary} opacity="0.8" />
      <rect x="0" y="8" width="2" height="2" fill={secondary} opacity="0.5" />
      {/* Fairy wings (right) */}
      <rect x="9" y="6" width="3" height="2" fill={secondary} opacity="0.8" />
      <rect x="10" y="8" width="2" height="2" fill={secondary} opacity="0.5" />
      {/* Head */}
      <rect x="3" y="2" width="6" height="5" fill="#FFDDE1" />
      {/* Hair */}
      <rect x="3" y="2" width="6" height="1" fill={primary} />
      <rect x="2" y="3" width="1" height="3" fill={primary} />
      <rect x="9" y="3" width="1" height="3" fill={primary} />
      {/* Eyes */}
      <rect x="4" y="4" width="1" height="1" fill="#0A6655" />
      <rect x="7" y="4" width="1" height="1" fill="#0A6655" />
      {/* Body - teal dress */}
      <rect x="3" y="7" width="6" height="5" fill={primary} />
      {/* Gem diamond on chest */}
      <rect x="5" y="8" width="1" height="1" fill={secondary} />
      <rect x="6" y="8" width="1" height="1" fill={secondary} />
      <rect x="5" y="9" width="1" height="1" fill="#FFFFFF" />
      <rect x="6" y="9" width="1" height="1" fill="#FFFFFF" />
      {/* Skirt flare */}
      <rect x="2" y="11" width="8" height="2" fill="#1ACDAA" />
      {/* Legs */}
      <rect x="4" y="13" width="2" height="3" fill="#FFDDE1" />
      <rect x="7" y="13" width="2" height="3" fill="#FFDDE1" />
      {/* Slippers */}
      <rect x="3" y="15" width="3" height="1" fill={primary} />
      <rect x="6" y="15" width="3" height="1" fill={primary} />
    </svg>
  )
}

function SageSprite({ primary, secondary }: { primary: string; secondary: string }) {
  return (
    <svg width="48" height="64" viewBox="0 0 12 16" xmlns="http://www.w3.org/2000/svg" style={{ imageRendering: 'pixelated' }}>
      {/* Wizard hat brim */}
      <rect x="2" y="3" width="8" height="1" fill={secondary} />
      {/* Wizard hat cone */}
      <rect x="4" y="1" width="4" height="2" fill={secondary} />
      <rect x="5" y="0" width="2" height="1" fill={secondary} />
      {/* Owl head */}
      <rect x="3" y="4" width="6" height="4" fill="#D4B896" />
      {/* Big owl eyes */}
      <rect x="3" y="5" width="2" height="2" fill="#F5C842" />
      <rect x="7" y="5" width="2" height="2" fill="#F5C842" />
      <rect x="4" y="5" width="1" height="2" fill="#2D1B00" />
      <rect x="8" y="5" width="1" height="2" fill="#2D1B00" />
      {/* Beak */}
      <rect x="5" y="7" width="2" height="1" fill="#C8A000" />
      {/* Robe body */}
      <rect x="2" y="8" width="8" height="5" fill={primary} />
      {/* Robe details */}
      <rect x="5" y="9" width="2" height="3" fill="#8B6FD4" />
      {/* Staff (held to right side) */}
      <rect x="10" y="4" width="1" height="9" fill={secondary} />
      <rect x="9" y="3" width="3" height="2" fill={secondary} />
      {/* Legs */}
      <rect x="4" y="13" width="2" height="3" fill={primary} />
      <rect x="7" y="13" width="2" height="3" fill={primary} />
      {/* Boots */}
      <rect x="3" y="15" width="3" height="1" fill="#4A3580" />
      <rect x="6" y="15" width="3" height="1" fill="#4A3580" />
    </svg>
  )
}

function HermesSprite({ primary, secondary }: { primary: string; secondary: string }) {
  return (
    <svg width="48" height="64" viewBox="0 0 12 16" xmlns="http://www.w3.org/2000/svg" style={{ imageRendering: 'pixelated' }}>
      {/* Wing left (on head) */}
      <rect x="1" y="2" width="2" height="2" fill={secondary} />
      <rect x="0" y="1" width="2" height="1" fill={secondary} opacity="0.7" />
      {/* Wing right (on head) */}
      <rect x="9" y="2" width="2" height="2" fill={secondary} />
      <rect x="10" y="1" width="2" height="1" fill={secondary} opacity="0.7" />
      {/* Head */}
      <rect x="3" y="2" width="6" height="5" fill={primary} />
      {/* Eyes */}
      <rect x="4" y="4" width="1" height="1" fill={secondary} />
      <rect x="7" y="4" width="1" height="1" fill={secondary} />
      {/* Helmet visor line */}
      <rect x="3" y="3" width="6" height="1" fill={secondary} opacity="0.5" />
      {/* Body — armor */}
      <rect x="3" y="7" width="6" height="5" fill={primary} />
      {/* Chest plate detail */}
      <rect x="4" y="8" width="4" height="3" fill={secondary} opacity="0.4" />
      {/* Caduceus staff */}
      <rect x="10" y="5" width="1" height="8" fill={secondary} />
      <rect x="9" y="5" width="3" height="1" fill="#7FC9FF" />
      <rect x="9" y="6" width="1" height="1" fill="#7FC9FF" />
      <rect x="11" y="6" width="1" height="1" fill="#7FC9FF" />
      {/* Legs */}
      <rect x="4" y="12" width="2" height="3" fill={secondary} />
      <rect x="7" y="12" width="2" height="3" fill={secondary} />
      {/* Winged sandals */}
      <rect x="3" y="14" width="3" height="2" fill={primary} />
      <rect x="6" y="14" width="3" height="2" fill={primary} />
      <rect x="2" y="14" width="1" height="1" fill={secondary} />
      <rect x="9" y="14" width="1" height="1" fill={secondary} />
    </svg>
  )
}

function LunaSprite({ primary, secondary }: { primary: string; secondary: string }) {
  return (
    <svg width="48" height="64" viewBox="0 0 12 16" xmlns="http://www.w3.org/2000/svg" style={{ imageRendering: 'pixelated' }}>
      {/* Crescent moon halo */}
      <rect x="2" y="0" width="7" height="1" fill={secondary} />
      <rect x="1" y="1" width="2" height="2" fill={secondary} />
      <rect x="8" y="1" width="2" height="1" fill={secondary} />
      {/* Head */}
      <rect x="3" y="2" width="6" height="5" fill="#D8EDFF" />
      {/* Eyes — star-shaped accent */}
      <rect x="4" y="4" width="1" height="1" fill={primary} />
      <rect x="7" y="4" width="1" height="1" fill={primary} />
      <rect x="3" y="4" width="1" height="1" fill={secondary} opacity="0.5" />
      <rect x="8" y="4" width="1" height="1" fill={secondary} opacity="0.5" />
      {/* Hair */}
      <rect x="3" y="2" width="6" height="1" fill={secondary} />
      <rect x="2" y="3" width="1" height="3" fill={secondary} />
      {/* Body / cloak */}
      <rect x="3" y="7" width="6" height="5" fill={primary} />
      {/* Star-map cape dots */}
      <rect x="1" y="8" width="2" height="5" fill="#4A7FD4" />
      <rect x="9" y="8" width="2" height="5" fill="#4A7FD4" />
      <rect x="2" y="9" width="1" height="1" fill={secondary} opacity="0.8" />
      <rect x="10" y="10" width="1" height="1" fill={secondary} opacity="0.8" />
      <rect x="1" y="11" width="1" height="1" fill={secondary} opacity="0.6" />
      {/* Cape star pattern on body */}
      <rect x="4" y="8" width="1" height="1" fill={secondary} opacity="0.6" />
      <rect x="7" y="10" width="1" height="1" fill={secondary} opacity="0.6" />
      {/* Legs */}
      <rect x="4" y="12" width="2" height="3" fill={primary} />
      <rect x="7" y="12" width="2" height="3" fill={primary} />
      {/* Boots */}
      <rect x="3" y="14" width="3" height="2" fill={secondary} />
      <rect x="6" y="14" width="3" height="2" fill={secondary} />
    </svg>
  )
}

function CharacterSprite({ character, direction }: { character: CharacterDef; direction: 'left' | 'right' }) {
  const scale = direction === 'left' ? 'scaleX(-1)' : 'scaleX(1)'
  const { primary, secondary } = character

  const spriteStyle: React.CSSProperties = {
    transform: scale,
    display: 'block',
    imageRendering: 'pixelated',
  }

  return (
    <div style={spriteStyle}>
      {character.id === 'sol'    && <SolSprite    primary={primary} secondary={secondary} />}
      {character.id === 'gem'    && <GemSprite    primary={primary} secondary={secondary} />}
      {character.id === 'sage'   && <SageSprite   primary={primary} secondary={secondary} />}
      {character.id === 'hermes' && <HermesSprite primary={primary} secondary={secondary} />}
      {character.id === 'luna'   && <LunaSprite   primary={primary} secondary={secondary} />}
    </div>
  )
}

// ─── Thought Bubble ───────────────────────────────────────────────────────────

function ThoughtBubble({ text, color }: { text: string; color: string }) {
  return (
    <div
      style={{
        position: 'absolute',
        bottom: '70px',
        left: '50%',
        transform: 'translateX(-50%)',
        background: 'rgba(10, 12, 10, 0.92)',
        border: `1px solid ${color}`,
        borderRadius: '4px',
        padding: '4px 8px',
        whiteSpace: 'nowrap',
        fontSize: '9px',
        letterSpacing: '0.08em',
        color: color,
        boxShadow: `0 0 8px ${color}44`,
        animation: 'bubble-pop 0.3s cubic-bezier(0.34, 1.56, 0.64, 1) forwards',
        pointerEvents: 'none',
        zIndex: 1,
      }}
    >
      {text}
      {/* tail */}
      <div
        style={{
          position: 'absolute',
          bottom: '-5px',
          left: '50%',
          transform: 'translateX(-50%)',
          width: 0,
          height: 0,
          borderLeft: '4px solid transparent',
          borderRight: '4px solid transparent',
          borderTop: `5px solid ${color}`,
        }}
      />
    </div>
  )
}

// ─── Walking Character ────────────────────────────────────────────────────────

function WalkingCharacter({ walk, character }: { walk: ActiveWalk; character: CharacterDef }) {
  const animName = walk.direction === 'right' ? 'walk-right' : 'walk-left'

  return (
    <div
      style={{
        position: 'absolute',
        bottom: '12px',
        left: 0,
        width: '48px',
        animation: `${animName} ${walk.durationMs}ms linear forwards`,
        pointerEvents: 'none',
      }}
    >
      {walk.showBubble && (
        <ThoughtBubble text={walk.bubbleText} color={character.primary} />
      )}
      {/* Name tag */}
      <div
        style={{
          position: 'absolute',
          bottom: '66px',
          left: '50%',
          transform: 'translateX(-50%)',
          fontSize: '8px',
          letterSpacing: '0.12em',
          color: character.primary,
          opacity: 0.7,
          whiteSpace: 'nowrap',
        }}
      >
        {character.name}
      </div>
      <CharacterSprite character={character} direction={walk.direction} />
    </div>
  )
}

// ─── Injected Keyframes ───────────────────────────────────────────────────────

const STYLE_ID = 'character-layer-keyframes'

function ensureKeyframes() {
  if (typeof document === 'undefined') return
  if (document.getElementById(STYLE_ID)) return
  const style = document.createElement('style')
  style.id = STYLE_ID
  style.textContent = `
    @keyframes walk-right {
      from { transform: translateX(-120px); }
      to   { transform: translateX(calc(100vw + 120px)); }
    }
    @keyframes walk-left {
      from { transform: translateX(calc(100vw + 120px)); }
      to   { transform: translateX(-120px); }
    }
    @keyframes bubble-pop {
      from { opacity: 0; transform: translateX(-50%) scale(0.6); }
      to   { opacity: 1; transform: translateX(-50%) scale(1); }
    }
    @keyframes float {
      0%, 100% { transform: translateY(0px); }
      50%       { transform: translateY(-4px); }
    }
  `
  document.head.appendChild(style)
}

// ─── Main Component ───────────────────────────────────────────────────────────

export function CharacterLayer() {
  const [activeWalks, setActiveWalks] = useState<Map<string, ActiveWalk>>(new Map())
  const timersRef = useRef<Map<string, ReturnType<typeof setTimeout>>>(new Map())

  const pickThought = (character: CharacterDef) =>
    character.thoughts[Math.floor(Math.random() * character.thoughts.length)]

  const scheduleNext = useCallback((characterId: string) => {
    // Random interval 30–90 seconds
    const delay = 30_000 + Math.random() * 60_000
    const timer = setTimeout(() => {
      const character = CHARACTERS.find(c => c.id === characterId)!
      const direction: 'left' | 'right' = Math.random() < 0.5 ? 'left' : 'right'
      const durationMs = 8_000 + Math.random() * 4_000
      const showBubble = Math.random() < 0.2
      const bubbleText = showBubble ? pickThought(character) : ''

      const walk: ActiveWalk = {
        characterId,
        direction,
        showBubble,
        bubbleText,
        startedAt: Date.now(),
        durationMs,
      }

      setActiveWalks(prev => {
        const next = new Map(prev)
        next.set(characterId, walk)
        return next
      })

      // Remove walk after animation completes, then schedule again
      const cleanupTimer = setTimeout(() => {
        setActiveWalks(prev => {
          const next = new Map(prev)
          next.delete(characterId)
          return next
        })
        scheduleNext(characterId)
      }, durationMs + 200)

      timersRef.current.set(`${characterId}_cleanup`, cleanupTimer)
    }, delay)

    timersRef.current.set(characterId, timer)
  }, [])

  useEffect(() => {
    ensureKeyframes()

    // Stagger initial schedule so they don't all activate at once
    CHARACTERS.forEach((char, idx) => {
      const initialDelay = setTimeout(() => {
        scheduleNext(char.id)
      }, idx * 4_000)
      timersRef.current.set(`${char.id}_init`, initialDelay)
    })

    return () => {
      timersRef.current.forEach(t => clearTimeout(t))
      timersRef.current.clear()
    }
  }, [scheduleNext])

  return (
    <div
      style={{
        position: 'fixed',
        inset: 0,
        zIndex: 50,
        pointerEvents: 'none',
        overflow: 'hidden',
      }}
      aria-hidden="true"
    >
      {Array.from(activeWalks.values()).map(walk => {
        const character = CHARACTERS.find(c => c.id === walk.characterId)
        if (!character) return null
        return (
          <WalkingCharacter
            key={`${walk.characterId}-${walk.startedAt}`}
            walk={walk}
            character={character}
          />
        )
      })}
    </div>
  )
}
