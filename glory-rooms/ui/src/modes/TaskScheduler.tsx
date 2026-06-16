import { useEffect, useState, useCallback } from 'react'
import { api } from '../api'

interface GloryTask {
  id: string
  name: string
  prompt: string
  schedule: string | null
  enabled: number
  last_run: string | null
  last_result: string | null
  run_count: number
  created_at: string
}

function relTime(iso: string | null) {
  if (!iso) return 'never'
  const ms = Date.now() - new Date(iso).getTime()
  const m = Math.floor(ms / 60_000)
  if (m < 1) return 'just now'
  if (m < 60) return `${m}m ago`
  const h = Math.floor(m / 60)
  if (h < 24) return `${h}h ago`
  return `${Math.floor(h / 24)}d ago`
}

export function TaskScheduler() {
  const [tasks, setTasks] = useState<GloryTask[]>([])
  const [name, setName] = useState('')
  const [prompt, setPrompt] = useState('')
  const [schedule, setSchedule] = useState('')
  const [running, setRunning] = useState<string | null>(null)
  const [expandedResult, setExpandedResult] = useState<string | null>(null)

  const refresh = useCallback(async () => {
    try {
      const r = await api.tasks.list()
      setTasks(r.tasks)
    } catch {}
  }, [])

  useEffect(() => {
    refresh()
    const t = setInterval(refresh, 8_000)
    return () => clearInterval(t)
  }, [refresh])

  const createTask = async () => {
    if (!name.trim() || !prompt.trim()) return
    await api.tasks.create({ name: name.trim(), prompt: prompt.trim(), schedule: schedule.trim() || undefined })
    setName(''); setPrompt(''); setSchedule('')
    refresh()
  }

  const runTask = async (id: string) => {
    setRunning(id)
    try {
      await api.tasks.run(id)
      refresh()
    } finally {
      setRunning(null)
    }
  }

  const deleteTask = async (id: string) => {
    await api.tasks.delete(id)
    refresh()
  }

  return (
    <section>
      <div className="label">Task Scheduler</div>
      <div className="card space-y-4">
        <p className="text-xs text-ink-500">
          Schedule prompts to run against Glory body (Gemma). Manual trigger or cron schedule.
        </p>

        {/* Create form */}
        <div className="space-y-2 border border-ink-800 p-3">
          <div className="text-[9px] text-ink-600 uppercase tracking-wider mb-2">New Task</div>
          <div className="grid grid-cols-2 gap-2">
            <input className="input text-sm" placeholder="Task name" value={name} onChange={e => setName(e.target.value)} />
            <input className="input text-sm" placeholder="Schedule (e.g. 0 9 * * *) — optional" value={schedule} onChange={e => setSchedule(e.target.value)} />
          </div>
          <textarea
            className="input w-full text-sm resize-none"
            rows={2}
            placeholder="Prompt to run…"
            value={prompt}
            onChange={e => setPrompt(e.target.value)}
          />
          <button
            className="btn-primary cursor-pointer disabled:opacity-40"
            disabled={!name.trim() || !prompt.trim()}
            onClick={createTask}
          >
            Add Task
          </button>
        </div>

        {/* Task list */}
        <div className="space-y-2 max-h-80 overflow-y-auto">
          {tasks.length === 0 && (
            <div className="text-xs text-ink-600 italic text-center py-4">No tasks scheduled.</div>
          )}
          {tasks.map(t => (
            <div key={t.id} className="border border-ink-700 hover:border-ink-600 transition-colors">
              <div className="flex items-center gap-3 px-3 py-2">
                <span className={`w-1.5 h-1.5 shrink-0 ${t.enabled ? 'bg-accent-500 pulse-glow' : 'bg-ink-700'}`} />
                <span className="text-sm text-ink-200 font-mono flex-1 truncate">{t.name}</span>
                {t.schedule && (
                  <span className="text-[10px] text-ink-600 font-mono shrink-0">{t.schedule}</span>
                )}
                <span className="text-[10px] text-ink-700 shrink-0">×{t.run_count}</span>
                <span className="text-[10px] text-ink-700 shrink-0">{relTime(t.last_run)}</span>
                <button
                  className="btn-primary text-xs px-2 py-1 cursor-pointer disabled:opacity-40 shrink-0"
                  disabled={running === t.id}
                  onClick={() => runTask(t.id)}
                >
                  {running === t.id ? '…' : '▶'}
                </button>
                <button
                  className="text-xs px-2 py-1 border border-red-900/40 text-red-400 hover:bg-red-900/20 cursor-pointer shrink-0"
                  onClick={() => deleteTask(t.id)}
                >
                  ✕
                </button>
              </div>
              {t.last_result && (
                <div className="border-t border-ink-800 px-3 py-1">
                  <button
                    className="text-[10px] text-ink-600 hover:text-ink-400 cursor-pointer"
                    onClick={() => setExpandedResult(expandedResult === t.id ? null : t.id)}
                  >
                    {expandedResult === t.id ? '▲ hide result' : '▼ last result'}
                  </button>
                  {expandedResult === t.id && (
                    <p className="text-xs text-ink-400 mt-1 leading-relaxed">{t.last_result}</p>
                  )}
                </div>
              )}
            </div>
          ))}
        </div>
      </div>
    </section>
  )
}
