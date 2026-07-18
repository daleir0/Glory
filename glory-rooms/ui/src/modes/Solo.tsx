import { useState } from 'react'
import { api, type Model } from '../api'
import { ModelPicker, modelTone } from '../components/ModelPicker'

export function Solo({ models }: { models: Model[] }) {
  const [model, setModel] = useState<string>(models[0]?.id || 'gemma')
  const [prompt, setPrompt] = useState('')
  const [output, setOutput] = useState('')
  const [running, setRunning] = useState(false)
  const [error, setError] = useState<string | null>(null)

  async function run() {
    setRunning(true); setError(null); setOutput('')
    try {
      const r = await api.solo(model, prompt)
      setOutput(r?.content?.[0]?.text || '(empty)')
    } catch (e: any) {
      setError(e.message)
    } finally {
      setRunning(false)
    }
  }

  return (
    <div className="space-y-5">
      <div className="grid grid-cols-[160px_1fr] gap-4 items-end">
        <div>
          <label className="label">Model</label>
          <ModelPicker value={model} onChange={setModel} models={models} />
        </div>
        <div>
          <label className="label">Prompt</label>
          <textarea
            className="input min-h-[100px] font-mono text-sm"
            value={prompt}
            onChange={(e) => setPrompt(e.target.value)}
            placeholder="Ask anything…"
          />
        </div>
      </div>
      <div className="flex justify-end">
        <button
          className="btn-primary"
          disabled={running || !prompt.trim()}
          onClick={run}
        >
          {running ? 'Running…' : 'Send'}
        </button>
      </div>
      {error && (
        <div className="card border-red-500/40 text-red-300 text-sm">{error}</div>
      )}
      {output && (
        <div className="card">
          <div className="flex items-center gap-2 mb-2">
            <span className={`pill ${modelTone(model)}`}>{model}</span>
          </div>
          <pre className="whitespace-pre-wrap font-sans text-sm text-ink-200 leading-relaxed">
            {output}
          </pre>
        </div>
      )}
    </div>
  )
}
