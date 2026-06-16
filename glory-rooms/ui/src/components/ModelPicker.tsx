import type { ModelId } from '../api'

export function ModelPicker({
  value, onChange, models,
}: {
  value: ModelId
  onChange: (m: ModelId) => void
  models: { id: string }[]
}) {
  return (
    <select
      className="input pr-8 cursor-pointer"
      value={value}
      onChange={(e) => onChange(e.target.value)}
    >
      {models.map((m) => (
        <option key={m.id} value={m.id}>{m.id}</option>
      ))}
    </select>
  )
}

export function modelTone(model: string): string {
  const m = model.toLowerCase()
  if (m.includes('kimi')) return 'bg-kimi/15 text-kimi border border-kimi/30'
  if (m.includes('gemma')) return 'bg-gemma/15 text-gemma border border-gemma/30'
  return 'bg-ink-700 text-ink-200 border border-ink-600'
}
