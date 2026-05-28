import { modelTone } from './ModelPicker'

export interface TurnLike {
  speaker?: string
  model: string
  text?: string
  content?: string
  step?: number
  turn?: number
  error?: string | null
}

export function Transcript({ items, label = 'Output' }: { items: TurnLike[]; label?: string }) {
  if (!items?.length) return null
  return (
    <div className="space-y-3">
      <div className="label">{label}</div>
      {items.map((it, i) => {
        const text = it.text ?? it.content ?? ''
        const idx = it.turn ?? it.step ?? i
        const speaker = it.speaker || it.model
        return (
          <div key={i} className="card">
            <div className="flex items-center justify-between mb-2">
              <div className="flex items-center gap-2">
                <span className="text-ink-500 text-xs font-mono">#{idx}</span>
                <span className="font-semibold text-ink-100">{speaker}</span>
                <span className={`pill ${modelTone(it.model)}`}>{it.model}</span>
              </div>
              {it.error && (
                <span className="pill bg-red-500/20 text-red-300 border border-red-500/40">
                  error
                </span>
              )}
            </div>
            <pre className="whitespace-pre-wrap font-sans text-sm text-ink-200 leading-relaxed">
              {it.error ? `(error: ${it.error})` : text}
            </pre>
          </div>
        )
      })}
    </div>
  )
}
