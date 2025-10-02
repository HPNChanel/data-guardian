import { useCallback, useEffect, useMemo, useRef, useState } from 'react'
import type { KeyboardEvent as ReactKeyboardEvent } from 'react'
import './App.css'

type LogLevel = 'debug' | 'info' | 'warn' | 'error'

type LogEntry = {
  id: string
  level: LogLevel
  message: string
  context: string
  timestamp: string
}

type ToastTone = 'success' | 'info' | 'warning' | 'error'

type Toast = {
  id: string
  message: string
  tone: ToastTone
}

type CommandAction = {
  id: string
  label: string
  description: string
  keywords: string
  run: () => void
}

const initialLogs: LogEntry[] = [
  {
    id: 'log-1',
    level: 'info',
    message: 'Desktop shell initialized',
    context: 'ui',
    timestamp: new Date(Date.now() - 120000).toISOString(),
  },
  {
    id: 'log-2',
    level: 'debug',
    message: 'Loaded policy bundle v1.3.2',
    context: 'policy-engine',
    timestamp: new Date(Date.now() - 90000).toISOString(),
  },
  {
    id: 'log-3',
    level: 'warn',
    message: 'Redaction rule set missing optional transforms',
    context: 'core',
    timestamp: new Date(Date.now() - 45000).toISOString(),
  },
  {
    id: 'log-4',
    level: 'error',
    message: 'Previous scan interrupted by user',
    context: 'scanner',
    timestamp: new Date(Date.now() - 15000).toISOString(),
  },
]

const formatTimestamp = (iso: string) =>
  new Date(iso).toLocaleTimeString([], {
    hour: '2-digit',
    minute: '2-digit',
    second: '2-digit',
  })

const createId = () => `${Date.now()}-${Math.round(Math.random() * 10_000)}`

const getDefaultSocketPath = () => {
  if (typeof navigator === 'undefined') {
    return '/tmp/data-guardian.sock'
  }
  const normalizedAgent = navigator.userAgent.toLowerCase()
  if (normalizedAgent.includes('win')) {
    return 'C:\\Users\\Public\\AppData\\Roaming\\DataGuardian\\pipe'
  }
  if (normalizedAgent.includes('mac') || normalizedAgent.includes('darwin')) {
    return '~/Library/Application Support/DataGuardian/socket'
  }
  return '/tmp/data-guardian.sock'
}

const getPlatformPrefix = () => {
  if (typeof navigator === 'undefined') {
    return 'unix'
  }
  const normalizedAgent = navigator.userAgent.toLowerCase()
  if (normalizedAgent.includes('win')) return 'win'
  if (normalizedAgent.includes('mac') || normalizedAgent.includes('darwin')) return 'mac'
  return 'unix'
}

function App() {
  const [isPaletteOpen, setIsPaletteOpen] = useState(false)
  const [paletteQuery, setPaletteQuery] = useState('')
  const [activeTab, setActiveTab] = useState<'overview' | 'settings' | 'logs'>('overview')
  const [notifications, setNotifications] = useState<Toast[]>([])
  const [corePathOverride, setCorePathOverride] = useState('')
  const [socketPath, setSocketPath] = useState(getDefaultSocketPath)
  const [logLevel, setLogLevel] = useState<LogLevel>('info')
  const [logRetentionDays, setLogRetentionDays] = useState(30)
  const [logs, setLogs] = useState<LogEntry[]>(initialLogs)
  const [scanPath, setScanPath] = useState('/var/workspace')
  const commandInputRef = useRef<HTMLInputElement | null>(null)

  const addToast = useCallback((message: string, tone: ToastTone = 'info') => {
    const toast: Toast = { id: createId(), message, tone }
    setNotifications((previous) => [...previous, toast])
    const timer = window.setTimeout(() => {
      setNotifications((previous) => previous.filter((item) => item.id !== toast.id))
    }, 4000)
    return () => window.clearTimeout(timer)
  }, [])

  const appendLog = useCallback(
    (entry: Omit<LogEntry, 'id' | 'timestamp'> & { timestamp?: string }) => {
      setLogs((previous) => [
        ...previous,
        {
          id: createId(),
          timestamp: entry.timestamp ?? new Date().toISOString(),
          ...entry,
        },
      ])
    },
    [],
  )

  const closePalette = useCallback(() => {
    setIsPaletteOpen(false)
    setPaletteQuery('')
  }, [])

  const handleCommandPaletteToggle = useCallback(
    (event: KeyboardEvent) => {
      if ((event.metaKey || event.ctrlKey) && event.key.toLowerCase() === 'k') {
        event.preventDefault()
        setIsPaletteOpen((previous) => !previous)
      }
    },
    [],
  )

  useEffect(() => {
    window.addEventListener('keydown', handleCommandPaletteToggle)
    return () => window.removeEventListener('keydown', handleCommandPaletteToggle)
  }, [handleCommandPaletteToggle])

  useEffect(() => {
    if (!isPaletteOpen) return

    const handleEsc = (event: KeyboardEvent) => {
      if (event.key === 'Escape') {
        event.preventDefault()
        closePalette()
      }
    }

    window.addEventListener('keydown', handleEsc)
    return () => window.removeEventListener('keydown', handleEsc)
  }, [closePalette, isPaletteOpen])

  useEffect(() => {
    if (isPaletteOpen) {
      const timeout = window.setTimeout(() => {
        commandInputRef.current?.focus()
        commandInputRef.current?.select()
      }, 10)
      return () => window.clearTimeout(timeout)
    }
    return undefined
  }, [isPaletteOpen])

  const handlePingCore = useCallback(() => {
    const latency = Math.floor(Math.random() * 40) + 20
    addToast(`Core responded in ${latency}ms`, 'success')
    appendLog({ level: 'info', message: 'Ping Core executed', context: 'ui' })
  }, [addToast, appendLog])

  const handleLoadPolicy = useCallback(() => {
    addToast('Latest policy bundle loaded', 'success')
    appendLog({ level: 'debug', message: 'Policy bundle refreshed by user', context: 'policy-engine' })
  }, [addToast, appendLog])

  const handleSelectPath = useCallback(() => {
    const proposed = window.prompt('Enter a path to scan', scanPath)
    if (proposed && proposed.trim()) {
      const normalized = proposed.trim()
      setScanPath(normalized)
      addToast(`Scan path set to ${normalized}`, 'success')
      appendLog({ level: 'info', message: `Scan path updated to ${normalized}`, context: 'scanner' })
    } else {
      addToast('Scan path unchanged', 'info')
    }
  }, [addToast, appendLog, scanPath])

  const handleRedactFile = useCallback(() => {
    const target = window.prompt('Enter a file to redact', 'example.txt')
    if (target && target.trim()) {
      addToast(`Redaction queued for ${target.trim()}`, 'success')
      appendLog({ level: 'warn', message: `Redaction requested for ${target.trim()}`, context: 'redactor' })
    } else {
      addToast('No file provided for redaction', 'warning')
    }
  }, [addToast, appendLog])

  const handleOpenLogs = useCallback(() => {
    setActiveTab('logs')
    addToast('Showing most recent logs', 'info')
    appendLog({ level: 'debug', message: 'Logs viewed from command palette', context: 'ui' })
  }, [addToast, appendLog])

  const handleOpenConfig = useCallback(() => {
    addToast('Config folder opened in a new window', 'info')
    appendLog({ level: 'info', message: 'Config folder opened via command palette', context: 'filesystem' })
  }, [addToast, appendLog])

  const actions: CommandAction[] = useMemo(
    () => [
      {
        id: 'ping-core',
        label: 'Ping Core',
        description: 'Check connectivity with the guardian core binary',
        keywords: 'ping connectivity health check',
        run: handlePingCore,
      },
      {
        id: 'load-policy',
        label: 'Load Policy',
        description: 'Refresh the currently loaded policy bundle',
        keywords: 'policy reload update',
        run: handleLoadPolicy,
      },
      {
        id: 'select-scan-path',
        label: 'Select Path to Scan',
        description: 'Choose which directory should be scanned next',
        keywords: 'scan directory path select choose',
        run: handleSelectPath,
      },
      {
        id: 'redact-file',
        label: 'Redact File',
        description: 'Queue redaction for a specific file',
        keywords: 'redact scrub sanitize',
        run: handleRedactFile,
      },
      {
        id: 'view-logs',
        label: 'View Logs',
        description: 'Jump straight to the logs view',
        keywords: 'logs history output',
        run: handleOpenLogs,
      },
      {
        id: 'open-config',
        label: 'Open Config Folder',
        description: 'Reveal the configuration directory in your file browser',
        keywords: 'config folder open preferences files',
        run: handleOpenConfig,
      },
    ],
    [handleLoadPolicy, handleOpenConfig, handleOpenLogs, handlePingCore, handleRedactFile, handleSelectPath],
  )

  const filteredActions = useMemo(() => {
    const query = paletteQuery.trim().toLowerCase()
    if (!query) return actions
    return actions.filter(
      (action) =>
        action.label.toLowerCase().includes(query) ||
        action.description.toLowerCase().includes(query) ||
        action.keywords.includes(query),
    )
  }, [actions, paletteQuery])

  const [logFilter, setLogFilter] = useState<'all' | LogLevel>('all')

  const visibleLogs = useMemo(() => {
    if (logFilter === 'all') return logs
    return logs.filter((log) => log.level === logFilter)
  }, [logFilter, logs])

  const handleCopyLogs = useCallback(async () => {
    if (visibleLogs.length === 0) {
      addToast('There are no logs for the selected level', 'warning')
      return
    }

    const logText = visibleLogs
      .map((log) => `${log.timestamp} [${log.level.toUpperCase()}] (${log.context}) ${log.message}`)
      .join('\n')

    try {
      if (navigator.clipboard && 'writeText' in navigator.clipboard) {
        await navigator.clipboard.writeText(logText)
      } else {
        const textArea = document.createElement('textarea')
        textArea.value = logText
        textArea.style.position = 'fixed'
        textArea.style.opacity = '0'
        document.body.appendChild(textArea)
        textArea.focus()
        textArea.select()
        document.execCommand('copy')
        document.body.removeChild(textArea)
      }
      addToast('Logs copied to clipboard', 'success')
    } catch (error) {
      console.error(error)
      addToast('Unable to copy logs to clipboard', 'error')
    }
  }, [addToast, visibleLogs])

  const handleExportLogs = useCallback(() => {
    if (logs.length === 0) {
      addToast('There are no logs to export', 'warning')
      return
    }

    const archiveName = `data-guardian-logs-${new Date().toISOString().slice(0, 10)}.zip`
    const blob = new Blob([
      'Placeholder zip archive. Replace with real export when connected to backend.\n',
      ...logs.map(
        (log) => `${log.timestamp} [${log.level.toUpperCase()}] (${log.context}) ${log.message}\n`,
      ),
    ])

    const url = URL.createObjectURL(blob)
    const anchor = document.createElement('a')
    anchor.href = url
    anchor.download = archiveName
    anchor.click()
    URL.revokeObjectURL(url)

    addToast('Logs exported to your desktop downloads folder', 'success')
    appendLog({ level: 'info', message: 'Logs exported as archive', context: 'ui' })
  }, [addToast, appendLog, logs])

  const handleRecreateSocket = useCallback(() => {
    const platform = getPlatformPrefix()
    const updatedPath =
      platform === 'win'
        ? `\\\\.\\pipe\\data-guardian-${Date.now()}`
        : platform === 'mac'
          ? `~/Library/Application Support/DataGuardian/socket-${Date.now()}`
          : `/tmp/data-guardian-${Date.now()}.sock`
    setSocketPath(updatedPath)
    addToast('Socket path recreated', 'success')
    appendLog({ level: 'debug', message: `Socket path recreated: ${updatedPath}`, context: 'core' })
  }, [addToast, appendLog])

  const handleSaveSettings = useCallback(() => {
    addToast('Settings saved', 'success')
    appendLog({ level: 'info', message: 'Settings updated from UI', context: 'ui' })
  }, [addToast, appendLog])

  const runFirstAction = useCallback(
    (event: ReactKeyboardEvent<HTMLInputElement>) => {
      if (event.key === 'Enter' && filteredActions.length > 0) {
        event.preventDefault()
        filteredActions[0].run()
        closePalette()
      }
    },
    [closePalette, filteredActions],
  )

  return (
    <div className="app-shell">
      <header className="app-header">
        <div>
          <h1>Data Guardian Desktop</h1>
          <p className="tagline">Protect sensitive data with confidence.</p>
        </div>
        <button className="command-trigger" onClick={() => setIsPaletteOpen(true)}>
          ⌘K Command Palette
        </button>
      </header>

      <nav className="primary-nav">
        <button
          className={activeTab === 'overview' ? 'active' : ''}
          onClick={() => setActiveTab('overview')}
        >
          Overview
        </button>
        <button
          className={activeTab === 'settings' ? 'active' : ''}
          onClick={() => setActiveTab('settings')}
        >
          Settings
        </button>
        <button className={activeTab === 'logs' ? 'active' : ''} onClick={() => setActiveTab('logs')}>
          Logs
        </button>
      </nav>

      <main className="content-area">
        {activeTab === 'overview' && (
          <section className="panel">
            <h2>Quick status</h2>
            <div className="status-grid">
              <article>
                <h3>Core connection</h3>
                <p>Core binary located at {corePathOverride || 'auto-detected path'}.</p>
                <button onClick={handlePingCore}>Ping core</button>
              </article>
              <article>
                <h3>Active policy</h3>
                <p>Policy bundle refreshed when the application starts.</p>
                <button onClick={handleLoadPolicy}>Reload policy</button>
              </article>
              <article>
                <h3>Scan scope</h3>
                <p>Current path: {scanPath}</p>
                <button onClick={handleSelectPath}>Update path</button>
              </article>
            </div>
            <div className="helper-card">
              <h3>Need something fast?</h3>
              <p>
                Press <strong>Ctrl/Cmd + K</strong> at any time to open the command palette. All essential
                automation shortcuts live there.
              </p>
            </div>
          </section>
        )}

        {activeTab === 'settings' && (
          <section className="panel">
            <h2>Settings</h2>
            <form
              className="settings-form"
              onSubmit={(event) => {
                event.preventDefault()
                handleSaveSettings()
              }}
            >
              <label>
                <span>Core binary path override</span>
                <input
                  value={corePathOverride}
                  onChange={(event) => setCorePathOverride(event.target.value)}
                  placeholder="/usr/local/bin/dg-core"
                  autoComplete="off"
                />
              </label>
              <label>
                <span>Socket / pipe path</span>
                <div className="inline-input">
                  <input value={socketPath} readOnly />
                  <button type="button" onClick={handleRecreateSocket}>
                    Recreate
                  </button>
                </div>
              </label>
              <label>
                <span>Log level</span>
                <select value={logLevel} onChange={(event) => setLogLevel(event.target.value as LogLevel)}>
                  <option value="debug">Debug</option>
                  <option value="info">Info</option>
                  <option value="warn">Warn</option>
                  <option value="error">Error</option>
                </select>
              </label>
              <label>
                <span>Log retention (days)</span>
                <input
                  type="number"
                  min={1}
                  max={365}
                  value={logRetentionDays}
                  onChange={(event) => {
                    const value = Number(event.target.value)
                    setLogRetentionDays(Number.isNaN(value) ? logRetentionDays : value)
                  }}
                />
              </label>
              <div className="form-actions">
                <button type="submit">Save changes</button>
              </div>
            </form>
          </section>
        )}

        {activeTab === 'logs' && (
          <section className="panel">
            <div className="logs-header">
              <div>
                <h2>Logs</h2>
                <p>Review what Data Guardian has been up to.</p>
              </div>
              <div className="logs-actions">
                <select value={logFilter} onChange={(event) => setLogFilter(event.target.value as 'all' | LogLevel)}>
                  <option value="all">All levels</option>
                  <option value="debug">Debug</option>
                  <option value="info">Info</option>
                  <option value="warn">Warn</option>
                  <option value="error">Error</option>
                </select>
                <button onClick={handleCopyLogs}>Copy</button>
                <button onClick={handleExportLogs}>Export</button>
              </div>
            </div>
            <div className="log-list" role="list">
              {visibleLogs.map((log) => (
                <article key={log.id} className={`log-entry level-${log.level}`} role="listitem">
                  <header>
                    <span className="timestamp">{formatTimestamp(log.timestamp)}</span>
                    <span className="level">{log.level.toUpperCase()}</span>
                    <span className="context">{log.context}</span>
                  </header>
                  <p>{log.message}</p>
                </article>
              ))}
              {visibleLogs.length === 0 && <p className="empty">No log entries for this level yet.</p>}
            </div>
          </section>
        )}
      </main>

      {isPaletteOpen && (
        <div className="command-palette" role="dialog" aria-modal="true">
          <div className="command-surface">
            <header>
              <input
                ref={commandInputRef}
                value={paletteQuery}
                onChange={(event) => setPaletteQuery(event.target.value)}
                onKeyDown={runFirstAction}
                placeholder="Search actions"
                aria-label="Search commands"
              />
            </header>
            <ul>
              {filteredActions.map((action) => (
                <li key={action.id}>
                  <button
                    onClick={() => {
                      action.run()
                      closePalette()
                    }}
                  >
                    <span className="action-label">{action.label}</span>
                    <span className="action-description">{action.description}</span>
                  </button>
                </li>
              ))}
              {filteredActions.length === 0 && <li className="empty">No commands match your search.</li>}
            </ul>
          </div>
        </div>
      )}

      <div className="toast-stack" role="status" aria-live="polite">
        {notifications.map((toast) => (
          <div key={toast.id} className={`toast ${toast.tone}`}>
            {toast.message}
          </div>
        ))}
      </div>
    </div>
  )
}

export default App
