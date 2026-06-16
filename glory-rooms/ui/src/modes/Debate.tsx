import { useState } from 'react'
import { api, type Model, type DebateParticipant, type DebateResult } from '../api'
import { ModelPicker, modelTone } from '../components/ModelPicker'

export function Debate({ models, onSession }: {
  models: Model[]
  onSession?: (sid: string) => void
}) {
  const defaultModel = models[0]?.id || 'gemma'
  const [prompt, setPrompt] = useState('')
  const [participants, setParticipants] = useState<DebateParticipant[]>([
    { model: defaultModel, name: 'Pro', stance: 'argue strongly in favor' },
    { model: defaultModel, name: 'Con', stance: 'argue strongly against' },
  ])
  const [synthModel, setSynthModel] = useState(defaultModel)
  const [synthInstr, setSynthInstr] = useState(
    'Pick the winner, or merge if both have merit. One paragraph.'
  )
  const [result, setResult] = useState<DebateResult | null>(null)
  const [running, setRunning] = useState(false)
  const [error, setError] = useState<string | null>(null)

  function setP(i: number, patch: Partial<DebateParticipant>) {
    setParticipants((s) => s.map((p, j) => (j === i ? { ...p, ...patch } : p)))
  }
  const addP = () =>
    setParticipants((s) => [...s, {
      model: defaultModel, name: `P${s.length + 1}`, stance: '',
    }])
  const removeP = (i: number) =>
    setParticipants((s) => s.filter((_, j) => j !== i))

  async function run() {
    setRunning(true); setError(null); setResult(null)
    try {
      const r = await api.debate(prompt, participants, {
        model: synthModel, instruction: synthInstr,
      })
      setResult(r)
      if (r.session_id && onSession) onSession(r.session_id)
    } catch (e: any) { setError(e.message) }
    finally { setRunning(false) }
  }

  return (
    <div className="space-y-5">
      <div>
        <label className="label">Prompt</label>
        <textarea
          className="input min-h-[80px]"
          value={prompt}
          onChange={(e) => setPrompt(e.target.value)}
          placeholder="What are they debating?"
        />
      </div>

      <div className="space-y-3">
        <div className="flex items-center justify-between">
          <label className="label !mb-0">Debaters</label>
          <button className="btn-ghost text-xs" onClick={addP}>+ add</button>
        </div>
        {participants.map((p, i) => (
          <div key={i} className="card">
            <div className="flex items-center justify-between mb-3">
              <span className="text-ink-500 text-xs font-mono">#{i}</span>
              {participants.length > 2 && (
                <button className="btn-ghost text-xs" onClick={() => removeP(i)}>remove</button>
              )}
            </div>
            <div className="grid grid-cols-[140px_120px_1fr] gap-3 items-start">
              <ModelPicker
                value={p.model}
                onChange={(m) => setP(i, { model: m })}
                models={models}
              />
              <input
                className="input"
                placeholder="Name"
                value={p.name || ''}
                onChange={(e) => setP(i, { name: e.target.value })}
              />
              <input
                className="input"
                placeholder="Stance — what to argue"
                value={p.stance || ''}
                onChange={(e) => setP(i, { stance: e.target.value })}
              />
            </div>
          </div>
        ))}
      </div>

      <div className="card border-accent-500/30">
        <label className="label">Synthesizer</label>
        <div className="grid grid-cols-[140px_1fr] gap-3 items-start">
          <ModelPicker value={synthModel} onChange={setSynthModel} models={models} />
          <input
            className="input"
            placeholder="Instruction for the synthesizer…"
            value={synthInstr}
            onChange={(e) => setSynthInstr(e.target.value)}
          />
        </div>
      </div>

      <div className="flex justify-end">
        <button
          className="btn-primary"
          disabled={running || !prompt.trim() || participants.some((p) => !p.model)}
          onClick={run}
        >
          {running ? 'Debating…' : 'Run debate'}
        </button>
      </div>

      {error && <div className="card border-red-500/40 text-red-300 text-sm">{error}</div>}

      {result?.answers && (
        <div>
          <div className="label">Answers</div>
          <div className="grid md:grid-cols-2 gap-3">
            {result.answers.map((a, i) => (
              <div key={i} className="card">
                <div className="flex items-center gap-2 mb-2">
                  <span className="font-semibold text-ink-100">{participants[i]?.name || `#${i}`}</span>
                  <span className={`pill ${modelTone(a.model)}`}>{a.model}</span>
                </div>
                {a.stance && (
                  <div className="text-xs text-ink-400 italic mb-2">stance: {a.stance}</div>
                )}
                <pre className="whitespace-pre-wrap font-sans text-sm text-ink-200 leading-relaxed">
                  {a.error ? `(error: ${a.error})` : a.text}
                </pre>
              </div>
            ))}
          </div>
        </div>
      )}

      {result?.synthesis && (
        <div className="card border-accent-500/40 bg-accent-500/5">
          <div className="flex items-center gap-2 mb-2">
            <span className="label !mb-0">Synthesis</span>
            <span className={`pill ${modelTone(result.synthesis.model)}`}>{result.synthesis.model}</span>
          </div>
          <pre className="whitespace-pre-wrap font-sans text-sm text-ink-100 leading-relaxed">
            {result.synthesis.text}
          </pre>
        </div>
      )}
    </div>
  )
}
