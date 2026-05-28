import { useEffect, useState } from 'react'
import { api, type Session } from '../api'
import { Transcript } from '../components/Transcript'
import { modelTone } from '../components/ModelPicker'

export function SessionDetail({ id, onClose }: { id: string; onClose: () => void }) {
  const [sess, setSess] = useState<Session | null>(null)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    let live = true
    api.session(id)
      .then((s) => { if (live) setSess(s) })
      .catch((e) => { if (live) setError(e.message) })
    return () => { live = false }
  }, [id])

  if (error) return <div className="card border-red-500/40 text-red-300 text-sm">{error}</div>
  if (!sess) return <div className="text-ink-400 text-sm">Loading…</div>

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between">
        <div>
          <h2 className="text-lg font-semibold text-ink-100">
            {sess.meta.topic || sess.meta.prompt || sess.meta.input || sess.id}
          </h2>
          <div className="text-xs text-ink-500 font-mono mt-1">
            {sess.id} · <span className={`pill ${modelTone(sess.mode)}`}>{sess.mode}</span> · {sess.updated_at}
          </div>
        </div>
        <button className="btn-ghost" onClick={onClose}>close</button>
      </div>
      <Transcript
        items={sess.messages.map((m) => ({
          turn: m.turn_idx,
          speaker: m.speaker,
          model: m.model,
          text: m.content,
          error: m.error,
        }))}
        label="Messages"
      />
    </div>
  )
}
