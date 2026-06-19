import { useState, useEffect, useRef, useCallback } from 'react'
import './App.css'

const WS_URL = import.meta.env.VITE_WS_URL || 'ws://localhost:8000/ws'
const API_URL = import.meta.env.VITE_API_URL || 'http://localhost:8000/api'

const DEPARTMENTS = ['Engineering', 'Product', 'Design', 'Marketing', 'Sales', 'HR', 'Finance', 'Operations']
const ROLES = ['Software Engineer', 'Product Manager', 'UX Designer', 'Data Analyst', 'DevOps Engineer', 'Marketing Manager', 'Sales Representative', 'HR Specialist']

const MOCK_SESSIONS = [
  {
    room_id: 'room-001',
    employee_name: 'Sarah Chen',
    department: 'Engineering',
    role: 'Software Engineer',
    status: 'completed',
    progress: 100,
    start_time: new Date(Date.now() - 3600000).toISOString(),
    agents: [
      { name: 'Planner', status: 'done', framework: 'LangGraph', output: 'Generated 12-task onboarding plan' },
      { name: 'HR Policy', status: 'done', framework: 'CrewAI', output: 'Compliance score: 94/100 ✓' },
      { name: 'IT Provisioning', status: 'done', framework: 'LangGraph', output: '8 accounts + 3 devices provisioned' },
      { name: 'Manager Review', status: 'done', framework: 'PydanticAI', output: 'Approved — Ready to start Monday' },
    ],
    messages: [
      { agent: 'Planner', text: 'Onboarding plan created: 12 tasks across 4 weeks', ts: '10:00' },
      { agent: 'HR Policy', text: 'Compliance validated. Equipment policy: ✓ Access policy: ✓', ts: '10:02' },
      { agent: 'IT Provisioning', text: 'GitHub, Slack, Jira accounts created. MacBook Pro ordered.', ts: '10:04' },
      { agent: 'Manager Review', text: '✅ APPROVED — Welcome Sarah to the team!', ts: '10:06' },
    ],
    report: {
      compliance_score: 94,
      accounts: ['GitHub', 'Slack', 'Jira', 'Google Workspace', 'Notion', 'Linear', 'Figma', 'AWS'],
      equipment: ['MacBook Pro 14"', 'External Monitor', 'Ergonomic Chair'],
      access: ['Engineering Repo', 'Dev VPN', 'CI/CD Pipeline', 'AWS Dev'],
      approved: true,
      manager_notes: 'Strong candidate. Fast-track onboarding approved.',
    }
  },
  {
    room_id: 'room-002',
    employee_name: 'Marcus Johnson',
    department: 'Product',
    role: 'Product Manager',
    status: 'pending_approval',
    progress: 75,
    start_time: new Date(Date.now() - 1800000).toISOString(),
    agents: [
      { name: 'Planner', status: 'done', framework: 'LangGraph', output: 'Generated 15-task onboarding plan' },
      { name: 'HR Policy', status: 'done', framework: 'CrewAI', output: 'Compliance score: 88/100 ✓' },
      { name: 'IT Provisioning', status: 'done', framework: 'LangGraph', output: '6 accounts + 2 devices provisioned' },
      { name: 'Manager Review', status: 'pending', framework: 'PydanticAI', output: 'Awaiting manager approval...' },
    ],
    messages: [
      { agent: 'Planner', text: 'Onboarding plan created for PM role: stakeholder mapping, roadmap review', ts: '11:30' },
      { agent: 'HR Policy', text: 'Policy check complete. Minor: remote work policy addendum required.', ts: '11:33' },
      { agent: 'IT Provisioning', text: 'Productboard, Confluence, Zoom licenses requested.', ts: '11:36' },
      { agent: 'Manager Review', text: '⏳ Report ready. Awaiting VP Product approval...', ts: '11:38' },
    ],
    report: {
      compliance_score: 88,
      accounts: ['Productboard', 'Confluence', 'Zoom', 'Slack', 'Google Workspace', 'Notion'],
      equipment: ['MacBook Air 15"', 'iPad Pro'],
      access: ['Product Roadmap', 'Analytics Dashboard', 'Customer Data (read)'],
      approved: false,
      manager_notes: '',
    }
  },
  {
    room_id: 'room-003',
    employee_name: 'Aisha Patel',
    department: 'Design',
    role: 'UX Designer',
    status: 'running',
    progress: 40,
    start_time: new Date(Date.now() - 600000).toISOString(),
    agents: [
      { name: 'Planner', status: 'done', framework: 'LangGraph', output: 'Design-focused onboarding plan created' },
      { name: 'HR Policy', status: 'active', framework: 'CrewAI', output: 'Validating design tool licenses...' },
      { name: 'IT Provisioning', status: 'waiting', framework: 'LangGraph', output: '' },
      { name: 'Manager Review', status: 'waiting', framework: 'PydanticAI', output: '' },
    ],
    messages: [
      { agent: 'Planner', text: 'Design onboarding plan: portfolio review, design system walkthrough, team sync', ts: '12:50' },
      { agent: 'HR Policy', text: '🔄 Checking Figma Enterprise license slots...', ts: '12:53' },
    ],
    report: null,
  }
]

function timeAgo(isoString) {
  const diff = (Date.now() - new Date(isoString)) / 1000
  if (diff < 60) return `${Math.floor(diff)}s ago`
  if (diff < 3600) return `${Math.floor(diff / 60)}m ago`
  return `${Math.floor(diff / 3600)}h ago`
}

function statusConfig(status) {
  const map = {
    completed: { label: 'Completed', cls: 'badge-green', dot: 'status-dot-done' },
    pending_approval: { label: 'Awaiting Approval', cls: 'badge-amber', dot: 'status-dot-pending' },
    running: { label: 'In Progress', cls: 'badge-cyan', dot: 'status-dot-active' },
    failed: { label: 'Failed', cls: 'badge-red', dot: 'status-dot-error' },
    idle: { label: 'Idle', cls: 'badge-gray', dot: 'status-dot-idle' },
  }
  return map[status] || map.idle
}

function agentStatusIcon(status) {
  const icons = { done: '✓', active: '⟳', pending: '⏳', waiting: '·', error: '✗' }
  return icons[status] || '·'
}

function agentStatusCls(status) {
  const cls = { done: 'agent-done', active: 'agent-active', pending: 'agent-pending', waiting: 'agent-waiting', error: 'agent-error' }
  return cls[status] || 'agent-waiting'
}

function frameworkColor(fw) {
  const map = { LangGraph: 'badge-cyan', CrewAI: 'badge-purple', PydanticAI: 'badge-green' }
  return map[fw] || 'badge-gray'
}

export default function App() {
  const [view, setView] = useState('dashboard') // 'dashboard' | 'session' | 'new'
  const [sessions, setSessions] = useState([])
  const [selectedSession, setSelectedSession] = useState(null)
  const [wsConnected, setWsConnected] = useState(false)
  const [toasts, setToasts] = useState([])
  const [filter, setFilter] = useState('all')
  const wsRef = useRef(null)
  const wsHandlerRef = useRef(null)  // ref so WS always calls the latest handler

  const addToast = useCallback((text, type = 'info') => {
    const id = Date.now()
    setToasts(prev => [...prev, { id, text, type }])
    setTimeout(() => setToasts(prev => prev.filter(t => t.id !== id)), 4000)
  }, [])

  const handleWsMessage = useCallback((msg) => {
    if (msg.type === 'init') {
      if (msg.sessions && msg.sessions.length > 0) {
        setSessions(msg.sessions)
      }
    }
    if (msg.type === 'session_update') {
      setSessions(prev => prev.map(s => s.room_id === msg.room_id ? { ...s, ...msg.data } : s))
    }
    if (msg.type === 'new_session') {
      setSessions(prev => {
        const exists = prev.some(s => s.room_id === msg.data.room_id)
        if (exists) {
          return prev.map(s => s.room_id === msg.data.room_id ? { ...s, ...msg.data } : s)
        }
        return [msg.data, ...prev]
      })
      addToast(`New onboarding started: ${msg.data.employee_name}`, 'info')
    }
    if (msg.type === 'approved') {
      addToast(`${msg.employee_name} approved!`, 'success')
    }
  }, [addToast])

  // Keep the ref in sync so WS onmessage always calls the latest handler
  useEffect(() => { wsHandlerRef.current = handleWsMessage }, [handleWsMessage])

  // WebSocket connection — uses ref so onmessage is never stale
  useEffect(() => {
    const connect = () => {
      try {
        const ws = new WebSocket(WS_URL)
        ws.onopen = () => setWsConnected(true)
        ws.onclose = () => {
          setWsConnected(false)
          setTimeout(connect, 3000)
        }
        ws.onmessage = (e) => {
          try {
            const msg = JSON.parse(e.data)
            wsHandlerRef.current?.(msg)
          } catch {}
        }
        wsRef.current = ws
      } catch {
        setTimeout(connect, 3000)
      }
    }
    connect()
    return () => wsRef.current?.close()
  }, [])

  const handleNewOnboarding = async (formData) => {
    setView('dashboard')

    // Try real API first — backend will send the real room_id via WebSocket
    try {
      const res = await fetch(`${API_URL}/onboard`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(formData),
      })
      if (!res.ok) throw new Error('API error')
      const data = await res.json()
      // Backend responded — WebSocket will push the real session shortly
      // Add optimistic placeholder so UI responds immediately
      const optimistic = {
        room_id: data.room_id,
        employee_name: `${formData.first_name} ${formData.last_name}`.trim(),
        department: formData.department,
        role: formData.role,
        status: 'running',
        progress: 0,
        start_time: new Date().toISOString(),
        agents: [
          { name: 'Planner', status: 'active', framework: 'LangGraph', output: 'Initializing...' },
          { name: 'HR Policy', status: 'waiting', framework: 'CrewAI', output: '' },
          { name: 'IT Provisioning', status: 'waiting', framework: 'LangGraph', output: '' },
          { name: 'Manager Review', status: 'waiting', framework: 'PydanticAI', output: '' },
        ],
        messages: [],
        report: null,
      }
      setSessions(prev => {
        const exists = prev.some(s => s.room_id === data.room_id)
        return exists ? prev : [optimistic, ...prev]
      })
      addToast(`Onboarding started for ${optimistic.employee_name}`, 'success')
    } catch {
      // Backend offline — use local simulation
      const localId = `local-${Date.now()}`
      const newSession = {
        room_id: localId,
        employee_name: `${formData.first_name} ${formData.last_name}`.trim(),
        department: formData.department,
        role: formData.role,
        status: 'running',
        progress: 0,
        start_time: new Date().toISOString(),
        agents: [
          { name: 'Planner', status: 'active', framework: 'LangGraph', output: 'Initializing...' },
          { name: 'HR Policy', status: 'waiting', framework: 'CrewAI', output: '' },
          { name: 'IT Provisioning', status: 'waiting', framework: 'LangGraph', output: '' },
          { name: 'Manager Review', status: 'waiting', framework: 'PydanticAI', output: '' },
        ],
        messages: [],
        report: null,
      }
      setSessions(prev => [newSession, ...prev])
      addToast(`Onboarding started (offline mode)`, 'info')
      simulateProgress(localId)
    }
  }

  const simulateProgress = (roomId) => {
    const steps = [
      { delay: 2000, progress: 25, agentIdx: 0, status: 'done', output: '12-task onboarding plan generated', nextActive: 1 },
      { delay: 5000, progress: 50, agentIdx: 1, status: 'done', output: 'Compliance score: 91/100 ✓', nextActive: 2 },
      { delay: 9000, progress: 75, agentIdx: 2, status: 'done', output: '7 accounts provisioned, equipment ordered', nextActive: 3 },
      { delay: 13000, progress: 75, agentIdx: 3, status: 'pending', output: 'Awaiting manager approval...', nextActive: -1, sessionStatus: 'pending_approval' },
    ]
    steps.forEach(({ delay, progress, agentIdx, status, output, nextActive, sessionStatus }) => {
      setTimeout(() => {
        setSessions(prev => prev.map(s => {
          if (s.room_id !== roomId) return s
          const agents = s.agents.map((a, i) => {
            if (i === agentIdx) return { ...a, status, output }
            if (i === nextActive) return { ...a, status: 'active' }
            return a
          })
          return { ...s, progress, agents, status: sessionStatus || s.status }
        }))
      }, delay)
    })
  }

  const handleApprove = async (session, decision) => {
    try {
      await fetch(`${API_URL}/approve`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ room_id: session.room_id, decision }),
      })
    } catch {}
    setSessions(prev => prev.map(s => {
      if (s.room_id !== session.room_id) return s
      return {
        ...s,
        status: decision === 'approve' ? 'completed' : 'failed',
        progress: decision === 'approve' ? 100 : s.progress,
        agents: s.agents.map(a => a.name === 'Manager Review' ? { ...a, status: decision === 'approve' ? 'done' : 'error', output: decision === 'approve' ? '✅ APPROVED' : '❌ REJECTED' } : a),
      }
    }))
    addToast(decision === 'approve' ? `${session.employee_name} approved!` : `${session.employee_name} rejected.`, decision === 'approve' ? 'success' : 'error')
    setView('dashboard')
  }

  const filteredSessions = sessions.filter(s => filter === 'all' || s.status === filter)

  return (
    <div className="app-layout">
      <Sidebar view={view} setView={setView} wsConnected={wsConnected} sessions={sessions} />
      <main className="app-main">
        {view === 'dashboard' && (
          <Dashboard
            sessions={filteredSessions}
            allSessions={sessions}
            filter={filter}
            setFilter={setFilter}
            onSelect={(s) => { setSelectedSession(s); setView('session') }}
            onNew={() => setView('new')}
          />
        )}
        {view === 'session' && selectedSession && (
          <SessionView
            session={sessions.find(s => s.room_id === selectedSession.room_id) || selectedSession}
            onBack={() => setView('dashboard')}
            onApprove={handleApprove}
          />
        )}
        {view === 'new' && (
          <NewOnboardingForm
            onSubmit={handleNewOnboarding}
            onCancel={() => setView('dashboard')}
          />
        )}
        {view === 'settings' && (
          <SettingsView
            onSave={() => {
              addToast('Settings saved successfully', 'success')
              setView('dashboard')
            }}
            onCancel={() => setView('dashboard')}
          />
        )}
      </main>
      <ToastContainer toasts={toasts} />
    </div>
  )
}

function Sidebar({ view, setView, wsConnected, sessions }) {
  const pending = sessions.filter(s => s.status === 'pending_approval').length
  const running = sessions.filter(s => s.status === 'running').length

  return (
    <aside className="sidebar">
      <div className="sidebar-logo">
        <div className="logo-icon">
          <svg width="22" height="22" viewBox="0 0 24 24" fill="none">
            <circle cx="12" cy="12" r="10" stroke="url(#lg1)" strokeWidth="2"/>
            <path d="M8 12l2.5 2.5L16 9" stroke="url(#lg1)" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"/>
            <defs>
              <linearGradient id="lg1" x1="0%" y1="0%" x2="100%" y2="100%">
                <stop offset="0%" stopColor="#7c3aed"/>
                <stop offset="100%" stopColor="#06b6d4"/>
              </linearGradient>
            </defs>
          </svg>
        </div>
        <div>
          <div className="logo-name">OnboardAI</div>
          <div className="logo-sub">Band of Agents</div>
        </div>
      </div>

      <nav className="sidebar-nav">
        <button
          id="nav-dashboard"
          className={`sidebar-item ${view === 'dashboard' ? 'active' : ''}`}
          onClick={() => setView('dashboard')}
        >
          <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
            <rect x="3" y="3" width="7" height="7" rx="1"/>
            <rect x="14" y="3" width="7" height="7" rx="1"/>
            <rect x="3" y="14" width="7" height="7" rx="1"/>
            <rect x="14" y="14" width="7" height="7" rx="1"/>
          </svg>
          Dashboard
          {running > 0 && <span className="nav-badge">{running}</span>}
        </button>
        <button
          id="nav-new"
          className={`sidebar-item ${view === 'new' ? 'active' : ''}`}
          onClick={() => setView('new')}
        >
          <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
            <circle cx="12" cy="12" r="10"/>
            <line x1="12" y1="8" x2="12" y2="16"/>
            <line x1="8" y1="12" x2="16" y2="12"/>
          </svg>
          New Onboarding
        </button>
        <button
          id="nav-settings"
          className={`sidebar-item ${view === 'settings' ? 'active' : ''}`}
          onClick={() => setView('settings')}
        >
          <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
            <circle cx="12" cy="12" r="3"/>
            <path d="M19.4 15a1.65 1.65 0 0 0 .33 1.82l.06.06a2 2 0 0 1 0 2.83 2 2 0 0 1-2.83 0l-.06-.06a1.65 1.65 0 0 0-1.82-.33 1.65 1.65 0 0 0-1 1.51V21a2 2 0 0 1-2 2 2 2 0 0 1-2-2v-.09A1.65 1.65 0 0 0 9 19.4a1.65 1.65 0 0 0-1.82.33l-.06.06a2 2 0 0 1-2.83 0 2 2 0 0 1 0-2.83l.06-.06a1.65 1.65 0 0 0 .33-1.82 1.65 1.65 0 0 0-1.51-1H3a2 2 0 0 1-2-2 2 2 0 0 1 2-2h.09A1.65 1.65 0 0 0 4.6 9a1.65 1.65 0 0 0-.33-1.82l-.06-.06a2 2 0 0 1 0-2.83 2 2 0 0 1 2.83 0l.06.06a1.65 1.65 0 0 0 1.82.33H9a1.65 1.65 0 0 0 1-1.51V3a2 2 0 0 1 2-2 2 2 0 0 1 2 2v.09a1.65 1.65 0 0 0 1 1.51 1.65 1.65 0 0 0 1.82-.33l.06-.06a2 2 0 0 1 2.83 0 2 2 0 0 1 0 2.83l-.06.06a1.65 1.65 0 0 0-.33 1.82V9a1.65 1.65 0 0 0 1.51 1H21a2 2 0 0 1 2 2 2 2 0 0 1-2 2h-.09a1.65 1.65 0 0 0-1.51 1z"/>
          </svg>
          Settings
        </button>
      </nav>

      <div className="sidebar-stats">
        <div className="stat-row">
          <span className="stat-label">Total Sessions</span>
          <span className="stat-val">{sessions.length}</span>
        </div>
        <div className="stat-row">
          <span className="stat-label">Completed</span>
          <span className="stat-val green">{sessions.filter(s => s.status === 'completed').length}</span>
        </div>
        <div className="stat-row">
          <span className="stat-label">Pending Approval</span>
          <span className="stat-val amber">{pending}</span>
        </div>
        <div className="stat-row">
          <span className="stat-label">In Progress</span>
          <span className="stat-val cyan">{running}</span>
        </div>
      </div>

      <div className="sidebar-footer">
        <div className={`ws-status ${wsConnected ? 'connected' : 'disconnected'}`}>
          <span className={`status-dot ${wsConnected ? 'status-dot-active' : 'status-dot-error'}`}></span>
          {wsConnected ? 'Live' : 'Demo Mode'}
        </div>
        <div className="band-badge">
          <span>Powered by</span>
          <strong>Band</strong>
        </div>
      </div>
    </aside>
  )
}

function Dashboard({ sessions, allSessions, filter, setFilter, onSelect, onNew }) {
  const completed = allSessions.filter(s => s.status === 'completed').length
  const pending = allSessions.filter(s => s.status === 'pending_approval').length
  const running = allSessions.filter(s => s.status === 'running').length
  const avgCompliance = allSessions
    .filter(s => s.report?.compliance_score)
    .reduce((acc, s, _, arr) => acc + s.report.compliance_score / arr.length, 0)

  return (
    <div className="page animate-fade-in">
      <div className="page-header">
        <div>
          <h1>HR Onboarding Hub</h1>
          <p>Multi-agent pipeline powered by Band's coordination layer</p>
        </div>
        <button id="btn-new-onboarding" className="btn btn-primary btn-lg" onClick={onNew}>
          <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5">
            <line x1="12" y1="5" x2="12" y2="19"/><line x1="5" y1="12" x2="19" y2="12"/>
          </svg>
          New Onboarding
        </button>
      </div>

      {/* KPI Cards */}
      <div className="kpi-grid">
        <KPICard title="Total Sessions" value={allSessions.length} icon="📋" color="purple" delay="0" />
        <KPICard title="Completed" value={completed} icon="✅" color="green" delay="100" />
        <KPICard title="Awaiting Approval" value={pending} icon="⏳" color="amber" delay="200" />
        <KPICard title="Avg Compliance" value={avgCompliance ? `${Math.round(avgCompliance)}%` : '—'} icon="🛡️" color="cyan" delay="300" />
      </div>

      {/* Agent Pipeline Overview */}
      <div className="card animate-fade-in-up delay-200">
        <h3 className="section-title">Agent Pipeline</h3>
        <div className="pipeline-row">
          {['Planner Agent', 'HR Policy Agent', 'IT Provisioning Agent', 'Manager Review Agent'].map((name, i) => (
            <div key={name} className="pipeline-step">
              <div className="pipeline-node">
                <span className="pipeline-num">{i + 1}</span>
              </div>
              <div className="pipeline-info">
                <div className="pipeline-name">{name}</div>
                <span className={`badge ${['badge-cyan', 'badge-purple', 'badge-cyan', 'badge-green'][i]}`}>
                  {['LangGraph', 'CrewAI', 'LangGraph', 'PydanticAI'][i]}
                </span>
              </div>
              {i < 3 && <div className="pipeline-arrow">→</div>}
            </div>
          ))}
        </div>
      </div>

      {/* Session List */}
      <div className="sessions-section animate-fade-in-up delay-300">
        <div className="sessions-header">
          <h3 className="section-title">Onboarding Sessions</h3>
          <div className="filter-tabs">
            {['all', 'running', 'pending_approval', 'completed'].map(f => (
              <button
                key={f}
                id={`filter-${f}`}
                className={`filter-tab ${filter === f ? 'active' : ''}`}
                onClick={() => setFilter(f)}
              >
                {f === 'all' ? 'All' : f === 'running' ? 'Active' : f === 'pending_approval' ? 'Pending' : 'Done'}
              </button>
            ))}
          </div>
        </div>
        {sessions.length === 0 ? (
          <div className="empty-state">
            <div className="empty-icon">👤</div>
            <h3>No sessions found</h3>
            <p>Start a new onboarding to see it here</p>
            <button className="btn btn-primary" onClick={onNew}>Start Onboarding</button>
          </div>
        ) : (
          <div className="session-list">
            {sessions.map((s, i) => (
              <SessionCard key={s.room_id} session={s} onClick={() => onSelect(s)} delay={i * 50} />
            ))}
          </div>
        )}
      </div>
    </div>
  )
}

function KPICard({ title, value, icon, color, delay }) {
  return (
    <div className={`kpi-card card animate-fade-in-up delay-${delay}`} data-color={color}>
      <div className="kpi-icon">{icon}</div>
      <div className="kpi-value">{value}</div>
      <div className="kpi-label">{title}</div>
    </div>
  )
}

function SessionCard({ session, onClick, delay }) {
  const sc = statusConfig(session.status)
  const initials = session.employee_name.split(' ').map(n => n[0]).join('')

  return (
    <div
      id={`session-${session.room_id}`}
      className="session-card card animate-fade-in-up"
      style={{ animationDelay: `${delay}ms` }}
      onClick={onClick}
      role="button"
      tabIndex={0}
      onKeyDown={e => e.key === 'Enter' && onClick()}
    >
      <div className="session-card-left">
        <div className="avatar">{initials}</div>
        <div className="session-info">
          <div className="session-name">{session.employee_name}</div>
          <div className="session-meta">{session.role} · {session.department}</div>
          <div className="session-time">{timeAgo(session.start_time)}</div>
        </div>
      </div>
      <div className="session-card-right">
        <span className={`badge ${sc.cls}`}>
          <span className={`status-dot ${sc.dot}`}></span>
          {sc.label}
        </span>
        <div className="session-agents-mini">
          {session.agents.map(a => (
            <span key={a.name} className={`agent-pip ${agentStatusCls(a.status)}`} title={`${a.name}: ${a.status}`}></span>
          ))}
        </div>
        <div className="progress-bar">
          <div className="progress-fill" style={{ width: `${session.progress}%` }}></div>
        </div>
        <div className="progress-pct">{session.progress}%</div>
      </div>
    </div>
  )
}

function SessionView({ session, onBack, onApprove }) {
  const sc = statusConfig(session.status)
  const [activeTab, setActiveTab] = useState('live')
  const messagesEndRef = useRef(null)

  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [session.messages])

  return (
    <div className="page animate-fade-in">
      <div className="page-header">
        <div className="flex items-center gap-md">
          <button className="btn btn-secondary btn-sm" onClick={onBack} id="btn-back">
            ← Back
          </button>
          <div>
            <h1>{session.employee_name}</h1>
            <p>{session.role} · {session.department}</p>
          </div>
        </div>
        <span className={`badge ${sc.cls}`}>
          <span className={`status-dot ${sc.dot}`}></span>
          {sc.label}
        </span>
      </div>

      {/* Progress */}
      <div className="card session-progress-card animate-fade-in-up">
        <div className="flex justify-between items-center" style={{ marginBottom: 12 }}>
          <span className="form-label">Overall Progress</span>
          <span className="progress-pct large">{session.progress}%</span>
        </div>
        <div className="progress-bar" style={{ height: 8 }}>
          <div className="progress-fill" style={{ width: `${session.progress}%` }}></div>
        </div>
      </div>

      {/* Agent Pipeline */}
      <div className="card animate-fade-in-up delay-100">
        <h3 className="section-title">Agent Pipeline Status</h3>
        <div className="agent-pipeline">
          {session.agents.map((agent, i) => (
            <div key={agent.name} className={`agent-card ${agentStatusCls(agent.status)}`}>
              <div className="agent-header">
                <div className="agent-icon-wrap">
                  <span className="agent-status-icon">{agentStatusIcon(agent.status)}</span>
                </div>
                <div className="agent-meta">
                  <div className="agent-name">{agent.name} Agent</div>
                  <span className={`badge ${frameworkColor(agent.framework)}`}>{agent.framework}</span>
                </div>
                <span className="agent-step">Step {i + 1}</span>
              </div>
              {agent.output && (
                <div className="agent-output">{agent.output}</div>
              )}
              {agent.status === 'active' && (
                <div className="agent-loading">
                  <div className="spinner"></div>
                  <span>Processing via {agent.framework}...</span>
                </div>
              )}
            </div>
          ))}
        </div>
      </div>

      {/* Tabs */}
      <div className="tab-bar animate-fade-in-up delay-200">
        {['live', 'report'].map(tab => (
          <button
            key={tab}
            id={`tab-${tab}`}
            className={`tab-btn ${activeTab === tab ? 'active' : ''}`}
            onClick={() => setActiveTab(tab)}
          >
            {tab === 'live' ? '💬 Band Chat Room' : '📄 Onboarding Report'}
          </button>
        ))}
      </div>

      {activeTab === 'live' && (
        <div className="card chat-card animate-fade-in">
          <div className="chat-header">
            <div className="flex items-center gap-sm">
              <span className="status-dot status-dot-active"></span>
              <span className="chat-room-name">Band Room: {session.room_id}</span>
            </div>
            <span className="badge badge-purple">Band Platform</span>
          </div>
          <div className="chat-messages scroll-area">
            {session.messages.length === 0 ? (
              <div className="chat-empty">Waiting for agents to connect...</div>
            ) : (
              session.messages.map((msg, i) => (
                <div key={i} className="chat-message animate-fade-in-up">
                  <div className="msg-agent-badge">
                    <span className={`badge ${frameworkColor(session.agents.find(a => a.name === msg.agent)?.framework || '')}`}>
                      {msg.agent}
                    </span>
                    <span className="msg-time">{msg.ts}</span>
                  </div>
                  <div className="msg-text">{msg.text}</div>
                </div>
              ))
            )}
            <div ref={messagesEndRef} />
          </div>
        </div>
      )}

      {activeTab === 'report' && session.report && (
        <div className="report-grid animate-fade-in">
          <div className="card">
            <h4>Compliance Score</h4>
            <div className="compliance-score" style={{ '--score': session.report.compliance_score }}>
              <div className="score-ring">
                <svg viewBox="0 0 100 100" className="score-svg">
                  <circle cx="50" cy="50" r="40" className="score-track"/>
                  <circle
                    cx="50" cy="50" r="40"
                    className="score-fill"
                    style={{ strokeDashoffset: `${251 - (251 * session.report.compliance_score / 100)}` }}
                  />
                </svg>
                <div className="score-number">{session.report.compliance_score}</div>
              </div>
            </div>
            {session.report.manager_notes && (
              <div className="manager-notes">
                <div className="form-label">Manager Notes</div>
                <p>{session.report.manager_notes}</p>
              </div>
            )}
          </div>
          <div className="card">
            <h4>IT Provisioning</h4>
            <div className="report-section">
              <div className="form-label">Accounts ({session.report.accounts.length})</div>
              <div className="tag-list">
                {session.report.accounts.map(a => <span key={a} className="tag">{a}</span>)}
              </div>
            </div>
            <div className="report-section">
              <div className="form-label">Equipment</div>
              <div className="tag-list">
                {session.report.equipment.map(e => <span key={e} className="tag tag-cyan">{e}</span>)}
              </div>
            </div>
            <div className="report-section">
              <div className="form-label">Access Permissions</div>
              <div className="tag-list">
                {session.report.access.map(a => <span key={a} className="tag tag-green">{a}</span>)}
              </div>
            </div>
          </div>
        </div>
      )}

      {activeTab === 'report' && !session.report && (
        <div className="card empty-state animate-fade-in">
          <div className="empty-icon">📄</div>
          <h3>Report Not Ready Yet</h3>
          <p>The manager review agent will generate the full report once all agents complete.</p>
        </div>
      )}

      {/* Approval Panel */}
      {session.status === 'pending_approval' && (
        <div className="card approval-card animate-fade-in-up">
          <div className="approval-header">
            <span className="approval-icon">👔</span>
            <div>
              <h3>Manager Approval Required</h3>
              <p>Review the onboarding plan and approve or request changes</p>
            </div>
          </div>
          <div className="approval-actions">
            <button
              id="btn-approve"
              className="btn btn-success btn-lg"
              onClick={() => onApprove(session, 'approve')}
            >
              ✓ Approve Onboarding
            </button>
            <button
              id="btn-reject"
              className="btn btn-danger"
              onClick={() => onApprove(session, 'reject')}
            >
              ✗ Reject
            </button>
          </div>
        </div>
      )}
    </div>
  )
}

function NewOnboardingForm({ onSubmit, onCancel }) {
  const [form, setForm] = useState({
    first_name: '', last_name: '', email: '', department: '', role: '',
    start_date: '', manager_email: '', employment_type: 'full-time',
  })
  const [loading, setLoading] = useState(false)

  const set = (k, v) => setForm(f => ({ ...f, [k]: v }))
  const valid = form.first_name && form.last_name && form.email && form.department && form.role

  const handleSubmit = async (e) => {
    e.preventDefault()
    if (!valid) return
    setLoading(true)
    await onSubmit(form)
    setLoading(false)
  }

  return (
    <div className="page animate-fade-in">
      <div className="page-header">
        <div>
          <h1>New Onboarding</h1>
          <p>Start the 4-agent onboarding pipeline for a new hire</p>
        </div>
        <button className="btn btn-secondary" onClick={onCancel} id="btn-cancel">Cancel</button>
      </div>

      <div className="form-layout">
        <form className="card form-card animate-fade-in-up" onSubmit={handleSubmit} id="onboarding-form">
          <div className="form-section">
            <h3 className="section-title">Employee Information</h3>
            <div className="grid-2">
              <div className="form-group">
                <label className="form-label" htmlFor="inp-first">First Name *</label>
                <input id="inp-first" className="form-input" placeholder="Sarah" value={form.first_name} onChange={e => set('first_name', e.target.value)} required />
              </div>
              <div className="form-group">
                <label className="form-label" htmlFor="inp-last">Last Name *</label>
                <input id="inp-last" className="form-input" placeholder="Chen" value={form.last_name} onChange={e => set('last_name', e.target.value)} required />
              </div>
            </div>
            <div className="form-group">
              <label className="form-label" htmlFor="inp-email">Work Email *</label>
              <input id="inp-email" className="form-input" type="email" placeholder="sarah.chen@company.com" value={form.email} onChange={e => set('email', e.target.value)} required />
            </div>
          </div>

          <div className="divider" />

          <div className="form-section">
            <h3 className="section-title">Role & Department</h3>
            <div className="grid-2">
              <div className="form-group">
                <label className="form-label" htmlFor="sel-dept">Department *</label>
                <select id="sel-dept" className="form-select" value={form.department} onChange={e => set('department', e.target.value)} required>
                  <option value="">Select department</option>
                  {DEPARTMENTS.map(d => <option key={d} value={d}>{d}</option>)}
                </select>
              </div>
              <div className="form-group">
                <label className="form-label" htmlFor="sel-role">Role *</label>
                <select id="sel-role" className="form-select" value={form.role} onChange={e => set('role', e.target.value)} required>
                  <option value="">Select role</option>
                  {ROLES.map(r => <option key={r} value={r}>{r}</option>)}
                </select>
              </div>
            </div>
            <div className="grid-2">
              <div className="form-group">
                <label className="form-label" htmlFor="sel-type">Employment Type</label>
                <select id="sel-type" className="form-select" value={form.employment_type} onChange={e => set('employment_type', e.target.value)}>
                  <option value="full-time">Full-time</option>
                  <option value="part-time">Part-time</option>
                  <option value="contractor">Contractor</option>
                  <option value="intern">Intern</option>
                </select>
              </div>
              <div className="form-group">
                <label className="form-label" htmlFor="inp-start">Start Date</label>
                <input id="inp-start" className="form-input" type="date" value={form.start_date} onChange={e => set('start_date', e.target.value)} />
              </div>
            </div>
          </div>

          <div className="divider" />

          <div className="form-section">
            <h3 className="section-title">Manager Details</h3>
            <div className="form-group">
              <label className="form-label" htmlFor="inp-mgr">Manager Email</label>
              <input id="inp-mgr" className="form-input" type="email" placeholder="manager@company.com" value={form.manager_email} onChange={e => set('manager_email', e.target.value)} />
            </div>
          </div>

          <div className="form-actions">
            <button type="button" className="btn btn-secondary" onClick={onCancel}>Cancel</button>
            <button id="btn-submit-onboarding" type="submit" className="btn btn-primary btn-lg" disabled={!valid || loading}>
              {loading ? <><div className="spinner"></div> Starting...</> : '🚀 Start Onboarding Pipeline'}
            </button>
          </div>
        </form>

        {/* Pipeline Preview */}
        <div className="pipeline-preview animate-fade-in-up delay-200">
          <div className="card">
            <h3 className="section-title">What Happens Next</h3>
            <div className="pipeline-steps-list">
              {[
                { num: 1, name: 'Planner Agent', fw: 'LangGraph', desc: 'Parses employee data, generates a structured 12-task onboarding plan via LLM', color: 'cyan' },
                { num: 2, name: 'HR Policy Agent', fw: 'CrewAI', desc: 'Validates plan against company HR policies, checks compliance, flags issues', color: 'purple' },
                { num: 3, name: 'IT Provisioning Agent', fw: 'LangGraph', desc: 'Creates accounts, orders equipment, sets access permissions checklist', color: 'cyan' },
                { num: 4, name: 'Manager Review Agent', fw: 'PydanticAI', desc: 'Synthesizes all outputs into final report, posts to Band room, requests approval', color: 'green' },
              ].map(step => (
                <div key={step.num} className="pipeline-step-item">
                  <div className={`pipeline-step-num color-${step.color}`}>{step.num}</div>
                  <div className="pipeline-step-content">
                    <div className="flex items-center gap-sm">
                      <span className="pipeline-step-name">{step.name}</span>
                      <span className={`badge badge-${step.color}`}>{step.fw}</span>
                    </div>
                    <p className="pipeline-step-desc">{step.desc}</p>
                  </div>
                </div>
              ))}
            </div>
          </div>

          <div className="card band-info-card">
            <div className="band-logo-row">
              <div className="band-dot"></div>
              <span>Band Platform</span>
            </div>
            <p>All agents coordinate through a shared Band room — a persistent messaging layer for real-time handoffs, approvals, and audit trails.</p>
          </div>
        </div>
      </div>
    </div>
  )
}

function SettingsView({ onSave, onCancel }) {
  const [demoMode, setDemoMode] = useState(() => localStorage.getItem('DEMO_MODE') !== 'false')
  const [bandKey, setBandKey] = useState(localStorage.getItem('BAND_API_KEY') || '')
  const [aimlKey, setAimlKey] = useState(localStorage.getItem('AIML_API_KEY') || '')
  const [featherlessKey, setFeatherlessKey] = useState(localStorage.getItem('FEATHERLESS_API_KEY') || '')
  const [saving, setSaving] = useState(false)

  const handleSave = async () => {
    setSaving(true)
    localStorage.setItem('DEMO_MODE', demoMode)
    localStorage.setItem('BAND_API_KEY', bandKey)
    localStorage.setItem('AIML_API_KEY', aimlKey)
    localStorage.setItem('FEATHERLESS_API_KEY', featherlessKey)
    
    try {
      await fetch(`${API_URL}/settings`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          DEMO_MODE: demoMode,
          BAND_API_KEY: bandKey,
          AIML_API_KEY: aimlKey,
          FEATHERLESS_API_KEY: featherlessKey
        })
      })
    } catch (e) {
      console.error('Failed to save settings to backend:', e)
    }

    setTimeout(() => { setSaving(false); onSave() }, 300)
  }

  return (
    <div className="page animate-fade-in">
      <div className="page-header">
        <div>
          <h1>Settings</h1>
          <p>Configure API keys and system mode</p>
        </div>
        <button className="btn btn-secondary" onClick={onCancel}>Cancel</button>
      </div>
      <div className="form-layout">
        <form className="card form-card animate-fade-in-up" onSubmit={e => { e.preventDefault(); handleSave() }}>
          <div className="form-section">
            <h3 className="section-title">System Mode</h3>
            <div className="form-group">
              <div className="flex items-center justify-between">
                <div>
                  <div className="form-label">Demo Mode</div>
                  <p style={{ fontSize: '0.8rem', color: 'var(--text-muted)', marginTop: 4 }}>
                    Uses smart mock responses instead of real LLM calls
                  </p>
                </div>
                <label className="toggle">
                  <input type="checkbox" checked={demoMode} onChange={e => setDemoMode(e.target.checked)} />
                  <span className="toggle-slider"></span>
                </label>
              </div>
            </div>
          </div>

          <div className="divider" />

          <div className="form-section">
            <h3 className="section-title">API Keys</h3>
            <p style={{ fontSize: '0.8rem', color: 'var(--text-muted)', marginBottom: 16 }}>
              Stored in browser localStorage. Restart required after changing.
            </p>
            <div className="form-group" style={{ marginBottom: 16 }}>
              <label className="form-label">Band API Key</label>
              <input className="form-input" type="password" placeholder="band_u_..." value={bandKey} onChange={e => setBandKey(e.target.value)} />
            </div>
            <div className="form-group" style={{ marginBottom: 16 }}>
              <label className="form-label">AI/ML API Key</label>
              <input className="form-input" type="password" placeholder="aiml_..." value={aimlKey} onChange={e => setAimlKey(e.target.value)} />
            </div>
            <div className="form-group">
              <label className="form-label">Featherless API Key</label>
              <input className="form-input" type="password" placeholder="rc_..." value={featherlessKey} onChange={e => setFeatherlessKey(e.target.value)} />
            </div>
          </div>

          <div className="form-actions">
            <button type="button" className="btn btn-secondary" onClick={onCancel}>Cancel</button>
            <button type="submit" className="btn btn-primary" disabled={saving}>
              {saving ? 'Saving...' : 'Save Settings'}
            </button>
          </div>
        </form>
        <div className="pipeline-preview animate-fade-in-up delay-200">
          <div className="card band-info-card" style={{ marginBottom: 16 }}>
            <div className="band-logo-row">
              <div className="band-dot"></div>
              <span>Current Status</span>
            </div>
            <div className="stat-row"><span className="stat-label">Backend</span><span className="stat-val green">Ready</span></div>
            <div className="stat-row"><span className="stat-label">Demo Mode</span><span className={`stat-val ${demoMode ? 'amber' : 'cyan'}`}>{demoMode ? 'ON' : 'OFF'}</span></div>
            <div className="stat-row"><span className="stat-label">Band Key</span><span className={`stat-val ${bandKey ? 'green' : 'amber'}`}>{bandKey ? 'Set' : 'Missing'}</span></div>
            <div className="stat-row"><span className="stat-label">AI/ML Key</span><span className={`stat-val ${aimlKey ? 'green' : 'amber'}`}>{aimlKey ? 'Set' : 'Missing'}</span></div>
            <div className="stat-row"><span className="stat-label">Featherless</span><span className={`stat-val ${featherlessKey ? 'green' : 'amber'}`}>{featherlessKey ? 'Set' : 'Missing'}</span></div>
          </div>
        </div>
      </div>
    </div>
  )
}

function ToastContainer({ toasts }) {
  return (
    <div className="toast-container">
      {toasts.map(toast => (
        <div key={toast.id} className={`toast toast-${toast.type}`}>
          <span className="toast-icon">
            {toast.type === 'success' ? '✅' : toast.type === 'error' ? '❌' : 'ℹ️'}
          </span>
          {toast.text}
        </div>
      ))}
    </div>
  )
}
