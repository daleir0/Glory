import { useState } from 'react'
import { api, type Model, type RoomParticipant, type RoomResult } from '../api'
import { ModelPicker } from '../components/ModelPicker'
import { Transcript } from '../components/Transcript'

export function Room({ models, onSession }: {
  models: Model[]
  onSession?: (sid: string) => void
}) {
  const defaultModel = models[0]?.id || 'gemma'
  const [topic, setTopic] = useState('')
  const [turns, setTurns] = useState(4)
  const [participants, setParticipants] = useState<RoomParticipant[]>([
    { model: defaultModel, name: 'A', persona: 'pragmatic, terse' },
    { model: defaultModel, name: 'B', persona: 'minimalist, contrarian' },
  ])
  const [result, setResult] = useState<RoomResult | null>(null)
  const [running, setRunning] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [sessionId, setSessionId] = useState<string | null>(null)

  function setP(i: number, patch: Partial<RoomParticipant>) {
    setParticipants((s) => s.map((p, j) => (j === i ? { ...p, ...patch } : p)))
  }
  const addP = () =>
    setParticipants((s) => [...s, {
      model: defaultModel, name: String.fromCharCode(65 + s.length), persona: '',
    }])
  const removeP = (i: number) =>
    setParticipants((s) => s.filter((_, j) => j !== i))

  async function run() {
    setRunning(true); setError(null); setResult(null); setSessionId(null)
    try {
      const r = await api.room(topic, participants, turns)
      setResult(r); setSessionId(r.session_id)
      if (r.session_id && onSession) onSession(r.session_id)
    } catch (e: any) { setError(e.message) }
    finally { setRunning(false) }
  }

  async function continueRoom(more: number) {
    if (!sessionId) return
    setRunning(true); setError(null)
    try {
      const r = await api.continueRoom(sessionId, more)
      setResult(r)
    } catch (e: any) { setError(e.message) }
    finally { setRunning(false) }
  }

  return (
    <div className="space-y-5">
      <div className="grid grid-cols-[1fr_120px] gap-4 items-end">
        <div>
          <label className="label">Topic</label>
          <input
            className="input"
            value={topic}
            onChange={(e) => setTopic(e.target.value)}
            placeholder="What are they discussing?"
          />
        </div>
        <div>
          <label className="label">Turns</label>
          <input
            type="number" min={1} max={50}
            className="input"
            value={turns}
            onChange={(e) => setTurns(parseInt(e.target.value || '1', 10))}
          />
        </div>
      </div>

      <div className="space-y-3">
        <div className="flex items-center justify-between">
          <label className="label !mb-0">Participants</label>
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
                value={p.name}
                onChange={(e) => setP(i, { name: e.target.value })}
              />
              <input
                className="input"
                placeholder="Persona — short description"
                value={p.persona || ''}
                onChange={(e) => setP(i, { persona: e.target.value })}
              />
            </div>
          </div>
        ))}
      </div>

      <div className="flex justify-end gap-2">
        {sessionId && (
          <>
            <button className="btn-ghost" disabled={running} onClick={() => continueRoom(2)}>+2 turns</button>
            <button className="btn-ghost" disabled={running} onClick={() => continueRoom(4)}>+4 turns</button>
          </>
        )}
        <button
          className="btn-primary"
          disabled={running || !topic.trim() || participants.some((p) => !p.name || !p.model)}
          onClick={run}
        >
          {running ? 'Running…' : sessionId ? 'New room' : `Start (${turns} turns)`}
        </button>
      </div>

      {error && <div className="card border-red-500/40 text-red-300 text-sm">{error}</div>}
      {result && <Transcript items={result.transcript as any} label="Transcript" />}
    </div>
  )
}
