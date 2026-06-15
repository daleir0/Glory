import { useState } from 'react'
import { api, type Model, type PipelineStep, type PipelineResult } from '../api'
import { ModelPicker } from '../components/ModelPicker'
import { Transcript } from '../components/Transcript'

export function Pipeline({ models, onSession }: {
  models: Model[]
  onSession?: (sid: string) => void
}) {
  const defaultModel = models[0]?.id || 'gemma'
  const [input, setInput] = useState('')
  const [steps, setSteps] = useState<PipelineStep[]>([
    { model: defaultModel, system: 'Draft a clear, terse first answer.' },
    { model: defaultModel, system: 'Critique the previous answer in one sentence.' },
    { model: defaultModel, system: 'Revise based on the critique.' },
  ])
  const [result, setResult] = useState<PipelineResult | null>(null)
  const [running, setRunning] = useState(false)
  const [error, setError] = useState<string | null>(null)

  function setStep(i: number, patch: Partial<PipelineStep>) {
    setSteps((s) => s.map((st, j) => (j === i ? { ...st, ...patch } : st)))
  }
  const addStep = () =>
    setSteps((s) => [...s, { model: defaultModel, system: '' }])
  const removeStep = (i: number) =>
    setSteps((s) => s.filter((_, j) => j !== i))

  async function run() {
    setRunning(true); setError(null); setResult(null)
    try {
      const r = await api.pipeline(input, steps)
      setResult(r)
      if (r.session_id && onSession) onSession(r.session_id)
    } catch (e: any) { setError(e.message) }
    finally { setRunning(false) }
  }

  return (
    <div className="space-y-5">
      <div>
        <label className="label">Initial input</label>
        <textarea
          className="input min-h-[80px] font-mono text-sm"
          value={input}
          onChange={(e) => setInput(e.target.value)}
          placeholder="Seed text fed into step 1…"
        />
      </div>

      <div className="space-y-3">
        <div className="flex items-center justify-between">
          <label className="label !mb-0">Steps</label>
          <button className="btn-ghost text-xs" onClick={addStep}>+ add step</button>
        </div>
        {steps.map((st, i) => (
          <div key={i} className="card">
            <div className="flex items-center justify-between mb-3">
              <span className="text-ink-500 text-xs font-mono">step {i}</span>
              {steps.length > 1 && (
                <button className="btn-ghost text-xs" onClick={() => removeStep(i)}>remove</button>
              )}
            </div>
            <div className="grid grid-cols-[140px_1fr] gap-3 items-start">
              <ModelPicker
                value={st.model}
                onChange={(m) => setStep(i, { model: m })}
                models={models}
              />
              <input
                className="input"
                placeholder="System instruction for this step…"
                value={st.system || ''}
                onChange={(e) => setStep(i, { system: e.target.value })}
              />
            </div>
          </div>
        ))}
      </div>

      <div className="flex justify-end">
        <button
          className="btn-primary"
          disabled={running || !input.trim() || steps.some((s) => !s.model)}
          onClick={run}
        >
          {running ? `Running ${steps.length} steps…` : `Run pipeline (${steps.length})`}
        </button>
      </div>

      {error && (
        <div className="card border-red-500/40 text-red-300 text-sm">{error}</div>
      )}

      {result && (
        <>
          <Transcript items={result.trace as any} label="Trace" />
          {result.output && (
            <div className="card border-accent-500/30">
              <div className="label">Final output</div>
              <pre className="whitespace-pre-wrap font-sans text-sm text-ink-100">
                {result.output}
              </pre>
            </div>
          )}
        </>
      )}
    </div>
  )
}
