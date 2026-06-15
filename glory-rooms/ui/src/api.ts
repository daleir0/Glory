// Glory proxy client.

export interface Model {
  id: string
  backend: string
  underlying: string
}

export interface SessionSummary {
  id: string
  mode: string
  title: string
  updated_at: string
}

export interface MemoryEntry {
  key: string
  value: string
  author: string
  updated_at: string
}

export interface Stats {
  sessions_total: number
  total_tokens_in: number
  total_tokens_out: number
  models: {
    model: string
    messages: number
    tokens_in: number
    tokens_out: number
    avg_latency_ms: number
  }[]
}

export interface PortStatus {
  port: number
  service: string
  status: 'online' | 'offline'
  latency_ms: number | null
}

export interface ScheduleEntry {
  id: string
  source: 'manual' | 'claude-code' | 'hermes'
  title: string
  cron: string | null
  description: string | null
  created_at: string | null
}

export interface ResearchResult {
  url: string
  domain: string
  status: number
  server: string
  title: string
  description: string
  tech_stack: string[]
  links: { internal: string[]; external: string[] }
  assets: { url: string; type: string }[]
  api_patterns: string[]
  obsidian_path: string | null
  saved: boolean
}

export interface NetworkDevice {
  ip: string
  mac: string
  type: string
}

export const api = {
  models: () =>
    fetch('/v1/models').then(r => r.json()) as Promise<{ models: Model[] }>,

  sessions: () =>
    fetch('/v1/sessions').then(r => r.json()) as Promise<{ sessions: SessionSummary[] }>,

  stats: () =>
    fetch('/v1/stats').then(r => r.json()) as Promise<Stats>,

  memory: {
    list: () =>
      fetch('/v1/memory').then(r => r.json()) as Promise<{ entries: MemoryEntry[] }>,
    set: (key: string, value: string) =>
      fetch('/v1/memory', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ key, value }),
      }).then(r => r.json()),
    del: (key: string) =>
      fetch(`/v1/memory/${encodeURIComponent(key)}`, { method: 'DELETE' }).then(r => r.json()),
  },

  ports: () =>
    fetch('/v1/ports').then(r => r.json()) as Promise<{ ports: PortStatus[] }>,

  schedules: {
    list: () =>
      fetch('/v1/schedules').then(r => r.json()) as Promise<{ schedules: ScheduleEntry[] }>,
    add: (entry: { title: string; cron?: string; description?: string }) =>
      fetch('/v1/schedules', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(entry),
      }).then(r => r.json()) as Promise<{ ok: boolean; id: string }>,
    del: (id: string) =>
      fetch(`/v1/schedules/${id}`, { method: 'DELETE' }).then(r => r.json()) as Promise<{ ok: boolean }>,
  },

  network: () =>
    fetch('/v1/network').then(r => r.json()) as Promise<{ devices: NetworkDevice[] }>,

  gloryAgents: () =>
    fetch('/v1/glory-agents').then(r => r.json()) as Promise<{
      agents: Array<{ id: string; name: string; role: 'head' | 'body'; color: string; status: string; backend: string; description: string }>
      swarm_id: string | null
      swarm_status: string
    }>,

  research: (url: string) =>
    fetch('/v1/research', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ url }),
    }).then(r => r.json()) as Promise<ResearchResult>,

  tasks: {
    list: () =>
      fetch('/v1/tasks').then(r => r.json()) as Promise<{
        tasks: Array<{ id: string; name: string; prompt: string; schedule: string | null; enabled: number; last_run: string | null; last_result: string | null; run_count: number; created_at: string }>
      }>,
    create: (t: { name: string; prompt: string; schedule?: string }) =>
      fetch('/v1/tasks', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(t) }).then(r => r.json()),
    run: (id: string) =>
      fetch(`/v1/tasks/${id}/run`, { method: 'POST' }).then(r => r.json()),
    delete: (id: string) =>
      fetch(`/v1/tasks/${id}`, { method: 'DELETE' }).then(r => r.json()),
  },

  agentBus: {
    list: () =>
      fetch('/v1/agent-bus').then(r => r.json()) as Promise<{
        messages: Array<{ id: number; from_agent: string; to_agent: string; content: string; thread: string | null; created_at: string }>
      }>,
    post: (from_agent: string, content: string, to_agent = 'all', thread?: string) =>
      fetch('/v1/agent-bus', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ from_agent, content, to_agent, thread }) }).then(r => r.json()),
  },

  scout: (url: string) =>
    fetch('/v1/scout', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ url }),
    }).then(r => r.json()),

  glory: (prompt: string, context?: string) =>
    fetch('/v1/glory', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ prompt, context, save_session: true }),
    }).then(r => r.json()) as Promise<{
      prompt: string
      body_responses: Array<{ model: string; role: string; response: string; latency_ms: number; error?: string }>
      synthesis: string
      session_id: string
      total_latency_ms: number
    }>,
}
