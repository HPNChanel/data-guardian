import { useCallback, useEffect, useMemo, useRef, useState } from 'react'
import type { KeyboardEvent as ReactKeyboardEvent } from 'react'
import { listen } from '@tauri-apps/api/event'
import type { UnlistenFn } from '@tauri-apps/api/event'
import { Command } from '@tauri-apps/plugin-shell'
import type { Child } from '@tauri-apps/plugin-shell'
import './App.css'
import { decryptFile, encryptFile } from './api/dg'

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

type JobStatus = 'idle' | 'queued' | 'running' | 'succeeded' | 'failed'

type FileJob = {
  id: string
  path: string
  status: JobStatus
  message?: string
  outputPath?: string
}

type ControllerMessage = {
  id: string
  kind: 'progress' | 'error'
  message: string
  timestamp: string
}

type CliLogEntry = {
  id: string
  stream: 'stdout' | 'stderr'
  message: string
}

type CliCommandDefinition = {
  id: string
  command: string
  label: string
  summary: string
  sample: string
  validate: (tokens: string[]) => { valid: true } | { valid: false; reason: string }
}

type DialogOpenOptions = {
  directory?: boolean
  multiple?: boolean
  defaultPath?: string
  filters?: { name: string; extensions: string[] }[]
}

const openSystemPath = async (path: string) => {
  const tauri = (window as unknown as {
    __TAURI__?: { shell?: { open?: (target: string) => Promise<void> } }
  }).__TAURI__
  if (tauri?.shell?.open) {
    return tauri.shell.open(path)
  }
  console.warn('Tauri shell open API is unavailable in this environment')
  return undefined
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

const STATUS_LABELS: Record<JobStatus, string> = {
  idle: 'Waiting',
  queued: 'Queued',
  running: 'Running',
  succeeded: 'Done',
  failed: 'Failed',
}

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
    return 'C\\Users\\Public\\AppData\\Roaming\\DataGuardian\\pipe'
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

const ENCRYPT_RECIPIENT_SUGGESTIONS = [
  'security-team@dataguardian.internal',
  'finance@dataguardian.internal',
  'policy@dataguardian.internal',
]

const ENCRYPT_LABEL_SUGGESTIONS = ['confidential', 'restricted', 'pii', 'finance-q1']

const DECRYPT_EXTENSIONS = ['dgenc', 'dgd']

const CLI_DEFINITIONS: CliCommandDefinition[] = [
  {
    id: 'version',
    command: '--version',
    label: '--version',
    summary: 'Show the installed CLI version',
    sample: 'data-guardian --version',
    validate: (tokens) =>
      tokens.length === 1 && tokens[0] === '--version'
        ? { valid: true }
        : { valid: false, reason: 'Expected --version with no additional arguments.' },
  },
  {
    id: 'selftest',
    command: 'selftest',
    label: 'selftest',
    summary: 'Run the local self-test suite',
    sample: 'data-guardian selftest',
    validate: (tokens) =>
      tokens.length === 1 && tokens[0] === 'selftest'
        ? { valid: true }
        : { valid: false, reason: 'selftest does not accept additional arguments.' },
  },
  {
    id: 'doctor',
    command: 'doctor',
    label: 'doctor',
    summary: 'Inspect the environment for common issues',
    sample: 'data-guardian doctor',
    validate: (tokens) =>
      tokens.length === 1 && tokens[0] === 'doctor'
        ? { valid: true }
        : { valid: false, reason: 'doctor does not accept additional arguments.' },
  },
  {
    id: 'keygen-rsa',
    command: 'keygen-rsa',
    label: 'keygen-rsa --label <label>',
    summary: 'Generate a new RSA key with the provided label(s)',
    sample: 'data-guardian keygen-rsa --label ops-team',
    validate: (tokens) => {
      if (tokens[0] !== 'keygen-rsa') {
        return { valid: false, reason: 'Command must begin with keygen-rsa.' }
      }
      if (tokens.length < 3) {
        return { valid: false, reason: 'keygen-rsa requires at least one --label value.' }
      }
      let index = 1
      let labels = 0
      while (index < tokens.length) {
        if (tokens[index] !== '--label') {
          return { valid: false, reason: 'Only --label options are supported for keygen-rsa.' }
        }
        if (!tokens[index + 1]) {
          return { valid: false, reason: 'Each --label must be followed by a value.' }
        }
        labels += 1
        index += 2
      }
      if (labels === 0) {
        return { valid: false, reason: 'Provide at least one label.' }
      }
      return { valid: true }
    },
  },
  {
    id: 'encrypt',
    command: 'encrypt',
    label: 'encrypt -i <in> -o <out> --kid <kid> [--label <label>...]',
    summary: 'Encrypt a file using an existing key identifier',
    sample: 'data-guardian encrypt -i sample.txt -o sample.txt.dgenc --kid user@domain',
    validate: (tokens) => {
      if (tokens[0] !== 'encrypt') {
        return { valid: false, reason: 'Command must begin with encrypt.' }
      }
      if (tokens.length < 7) {
        return { valid: false, reason: 'encrypt requires -i, -o, and --kid parameters.' }
      }
      if (tokens[1] !== '-i' || !tokens[2]) {
        return { valid: false, reason: 'Missing input flag (-i <path>).' }
      }
      if (tokens[3] !== '-o' || !tokens[4]) {
        return { valid: false, reason: 'Missing output flag (-o <path>).' }
      }
      if (tokens[5] !== '--kid' || !tokens[6]) {
        return { valid: false, reason: 'Missing key identifier (--kid <value>).' }
      }
      let index = 7
      while (index < tokens.length) {
        if (tokens[index] !== '--label') {
          return { valid: false, reason: 'Only --label may follow the required encrypt arguments.' }
        }
        if (!tokens[index + 1]) {
          return { valid: false, reason: 'Each --label must be followed by a value.' }
        }
        index += 2
      }
      return { valid: true }
    },
  },
  {
    id: 'decrypt',
    command: 'decrypt',
    label: 'decrypt -i <in> -o <out>',
    summary: 'Decrypt an existing envelope',
    sample: 'data-guardian decrypt -i sample.txt.dgenc -o sample.txt',
    validate: (tokens) => {
      if (tokens[0] !== 'decrypt') {
        return { valid: false, reason: 'Command must begin with decrypt.' }
      }
      if (tokens.length !== 5) {
        return { valid: false, reason: 'decrypt requires exactly -i <path> -o <path>.' }
      }
      if (tokens[1] !== '-i' || !tokens[2]) {
        return { valid: false, reason: 'Missing input flag (-i <path>).' }
      }
      if (tokens[3] !== '-o' || !tokens[4]) {
        return { valid: false, reason: 'Missing output flag (-o <path>).' }
      }
      return { valid: true }
    },
  },
]

const tokenizeCommand = (command: string) => {
  const tokens: string[] = []
  let current = ''
  let quote: '"' | '\'' | null = null

  for (let i = 0; i < command.length; i += 1) {
    const char = command[i]
    const isQuote = char === '"' || char === '\''

    if (isQuote) {
      if (quote === char) {
        quote = null
        continue
      }
      if (!quote) {
        quote = char as '"' | '\''
        continue
      }
    }

    if (!quote && /\s/.test(char)) {
      if (current) {
        tokens.push(current)
        current = ''
      }
      continue
    }

    current += char
  }

  if (current) {
    tokens.push(current)
  }

  return tokens
}

const sanitizeTokens = (tokens: string[]) =>
  tokens.map((token) => token.trim()).filter((token) => token.length > 0)
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
  const [logFilter, setLogFilter] = useState<'all' | LogLevel>('all')
  const [controllerMessages, setControllerMessages] = useState<ControllerMessage[]>([])

  const [isEncryptDialogOpen, setIsEncryptDialogOpen] = useState(false)
  const [encryptJobs, setEncryptJobs] = useState<FileJob[]>([])
  const [encryptRecipients, setEncryptRecipients] = useState<string[]>([])
  const [encryptRecipientDraft, setEncryptRecipientDraft] = useState('')
  const [encryptLabels, setEncryptLabels] = useState<string[]>([])
  const [encryptLabelDraft, setEncryptLabelDraft] = useState('')
  const [encryptOutputMode, setEncryptOutputMode] = useState<'sibling' | 'directory'>('sibling')
  const [encryptOutputDirectory, setEncryptOutputDirectory] = useState('')

  const [isDecryptDialogOpen, setIsDecryptDialogOpen] = useState(false)
  const [decryptJobs, setDecryptJobs] = useState<FileJob[]>([])
  const [decryptOutputMode, setDecryptOutputMode] = useState<'sibling' | 'directory'>('sibling')
  const [decryptOutputDirectory, setDecryptOutputDirectory] = useState('')

  const [isCliDialogOpen, setIsCliDialogOpen] = useState(false)
  const [cliCommandText, setCliCommandText] = useState('')
  const [cliLogs, setCliLogs] = useState<CliLogEntry[]>([])
  const [cliError, setCliError] = useState('')
  const [cliIsRunning, setCliIsRunning] = useState(false)
  const cliChildRef = useRef<Child | null>(null)

  const [activeOperation, setActiveOperation] = useState<'encrypt' | 'decrypt' | null>(null)

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

  const openEncryptDialog = useCallback(() => {
    setIsEncryptDialogOpen(true)
    setActiveOperation(null)
  }, [])

  const openDecryptDialog = useCallback(() => {
    setIsDecryptDialogOpen(true)
    setActiveOperation(null)
  }, [])

  const openCliDialog = useCallback(() => {
    setIsCliDialogOpen(true)
    setCliError('')
  }, [])

  const showDialog = useCallback(async (options: DialogOpenOptions = {}) => {
    const tauri = (window as unknown as {
      __TAURI__?: { dialog?: { open?: (opts: Record<string, unknown>) => Promise<unknown> } }
    }).__TAURI__
    if (tauri?.dialog?.open) {
      return tauri.dialog.open(options)
    }
    console.warn('Tauri dialog API is unavailable in this environment')
    return null
  }, [])

  const handleGlobalShortcuts = useCallback(
    (event: KeyboardEvent) => {
      if (!(event.metaKey || event.ctrlKey)) {
        return
      }
      const key = event.key.toLowerCase()
      if (key === 'k') {
        event.preventDefault()
        setIsPaletteOpen((previous) => !previous)
      }
      if (key === 'e') {
        event.preventDefault()
        openEncryptDialog()
      }
      if (key === 'd') {
        event.preventDefault()
        openDecryptDialog()
      }
    },
    [openDecryptDialog, openEncryptDialog],
  )

  useEffect(() => {
    window.addEventListener('keydown', handleGlobalShortcuts)
    return () => window.removeEventListener('keydown', handleGlobalShortcuts)
  }, [handleGlobalShortcuts])

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
    if (!isPaletteOpen) return

    const timeout = window.setTimeout(() => {
      commandInputRef.current?.focus()
      commandInputRef.current?.select()
    }, 10)
    return () => window.clearTimeout(timeout)
  }, [isPaletteOpen])

  useEffect(() => {
    let unlisten: UnlistenFn | undefined

    const subscribe = async () => {
      try {
        unlisten = await listen('dg://controller', (event) => {
          const payload = event.payload as { kind: 'progress' | 'error'; message: string }
          setControllerMessages((previous) => {
            const next = [
              ...previous,
              {
                id: createId(),
                kind: payload.kind,
                message: payload.message,
                timestamp: new Date().toISOString(),
              },
            ]
            return next.slice(-100)
          })
          if (payload.kind === 'error') {
            addToast(payload.message, 'error')
            appendLog({ level: 'error', message: payload.message, context: 'ui' })
          }
        })
      } catch (error) {
        console.error(error)
        appendLog({
          level: 'warn',
          message: `Failed to subscribe to controller events: ${String(error)}`,
          context: 'ui',
        })
      }
    }

    subscribe()

    return () => {
      if (unlisten) {
        unlisten()
      }
    }
  }, [addToast, appendLog])

  useEffect(() => {
    return () => {
      const child = cliChildRef.current
      if (child) {
        child.kill().catch(() => undefined)
      }
    }
  }, [])

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
      ...logs.map((log) => `${log.timestamp} [${log.level.toUpperCase()}] (${log.context}) ${log.message}\n`),
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
  const addRecipient = useCallback((value: string) => {
    const normalized = value.trim()
    if (!normalized) return
    setEncryptRecipients((previous) =>
      previous.includes(normalized) ? previous : [...previous, normalized],
    )
  }, [])

  const removeRecipient = useCallback((value: string) => {
    setEncryptRecipients((previous) => previous.filter((item) => item !== value))
  }, [])

  const addLabel = useCallback((value: string) => {
    const normalized = value.trim()
    if (!normalized) return
    setEncryptLabels((previous) =>
      previous.includes(normalized) ? previous : [...previous, normalized],
    )
  }, [])

  const removeLabel = useCallback((value: string) => {
    setEncryptLabels((previous) => previous.filter((item) => item !== value))
  }, [])

  const handleRecipientKeyDown = useCallback(
    (event: ReactKeyboardEvent<HTMLInputElement>) => {
      if ((event.key === 'Enter' || event.key === ',') && encryptRecipientDraft.trim()) {
        event.preventDefault()
        addRecipient(encryptRecipientDraft)
        setEncryptRecipientDraft('')
        return
      }
      if (event.key === 'Backspace' && !encryptRecipientDraft && encryptRecipients.length > 0) {
        event.preventDefault()
        const last = encryptRecipients[encryptRecipients.length - 1]
        removeRecipient(last)
      }
    },
    [addRecipient, encryptRecipientDraft, encryptRecipients, removeRecipient],
  )

  const handleLabelKeyDown = useCallback(
    (event: ReactKeyboardEvent<HTMLInputElement>) => {
      if ((event.key === 'Enter' || event.key === ',') && encryptLabelDraft.trim()) {
        event.preventDefault()
        addLabel(encryptLabelDraft)
        setEncryptLabelDraft('')
        return
      }
      if (event.key === 'Backspace' && !encryptLabelDraft && encryptLabels.length > 0) {
        event.preventDefault()
        const last = encryptLabels[encryptLabels.length - 1]
        removeLabel(last)
      }
    },
    [addLabel, encryptLabelDraft, encryptLabels, removeLabel],
  )

  const handleRecipientSuggestion = useCallback(
    (value: string) => {
      addRecipient(value)
      setEncryptRecipientDraft('')
    },
    [addRecipient],
  )

  const handleLabelSuggestion = useCallback(
    (value: string) => {
      addLabel(value)
      setEncryptLabelDraft('')
    },
    [addLabel],
  )

  const handleSelectEncryptFiles = useCallback(async () => {
    try {
      const selection = await showDialog({ multiple: true })
      if (!selection) return
      const files = Array.isArray(selection) ? selection : [selection]
      const normalized = files.filter((file): file is string => typeof file === 'string')
      setEncryptJobs(normalized.map((path) => ({ id: createId(), path, status: 'idle' })))
    } catch (error) {
      addToast('Unable to select files for encryption', 'error')
      appendLog({ level: 'error', message: `Failed to open encrypt selector: ${String(error)}`, context: 'ui' })
    }
  }, [addToast, appendLog])

  const handleSelectDecryptFiles = useCallback(async () => {
    try {
      const selection = await showDialog({
        multiple: true,
        filters: [{ name: 'Encrypted files', extensions: DECRYPT_EXTENSIONS }],
      })
      if (!selection) return
      const files = Array.isArray(selection) ? selection : [selection]
      const normalized = files.filter((file): file is string => typeof file === 'string')
      setDecryptJobs(normalized.map((path) => ({ id: createId(), path, status: 'idle' })))
    } catch (error) {
      addToast('Unable to select files for decryption', 'error')
      appendLog({ level: 'error', message: `Failed to open decrypt selector: ${String(error)}`, context: 'ui' })
    }
  }, [addToast, appendLog])

  const handleSelectEncryptOutputDirectory = useCallback(async () => {
    try {
      const selection = await showDialog({ directory: true })
      if (typeof selection === 'string') {
        setEncryptOutputDirectory(selection)
        setEncryptOutputMode('directory')
      }
    } catch (error) {
      addToast('Unable to select an output directory', 'error')
      appendLog({ level: 'error', message: `Failed to select encrypt output directory: ${String(error)}`, context: 'ui' })
    }
  }, [addToast, appendLog])

  const handleSelectDecryptOutputDirectory = useCallback(async () => {
    try {
      const selection = await showDialog({ directory: true })
      if (typeof selection === 'string') {
        setDecryptOutputDirectory(selection)
        setDecryptOutputMode('directory')
      }
    } catch (error) {
      addToast('Unable to select an output directory', 'error')
      appendLog({ level: 'error', message: `Failed to select decrypt output directory: ${String(error)}`, context: 'ui' })
    }
  }, [addToast, appendLog])

  const handleRevealPath = useCallback(
    async (path: string) => {
      try {
        await openSystemPath(path)
      } catch (error) {
        addToast('Unable to open the requested path', 'error')
        appendLog({ level: 'error', message: `Failed to open path ${path}: ${String(error)}`, context: 'ui' })
      }
    },
    [addToast, appendLog],
  )

  const handleEncryptSubmit = useCallback(
    async (event?: React.FormEvent<HTMLFormElement>) => {
      if (event) {
        event.preventDefault()
      }

      if (encryptJobs.length === 0) {
        addToast('Select files to encrypt first.', 'warning')
        return
      }
      if (encryptRecipients.length === 0) {
        addToast('Add at least one recipient.', 'warning')
        return
      }
      if (encryptOutputMode === 'directory' && !encryptOutputDirectory) {
        addToast('Choose an output directory.', 'warning')
        return
      }

      setActiveOperation('encrypt')
      setEncryptJobs((previous) =>
        previous.map((job) => ({
          ...job,
          status: 'queued',
          message: 'Queued',
        })),
      )

      const outputs: string[] = []
      const recipients = [...encryptRecipients]
      const labels = [...encryptLabels]
      const outDir =
        encryptOutputMode === 'directory' && encryptOutputDirectory
          ? encryptOutputDirectory
          : undefined

      for (const job of encryptJobs) {
        setEncryptJobs((previous) =>
          previous.map((item) =>
            item.id === job.id
              ? {
                  ...item,
                  status: 'running',
                  message: 'Running',
                }
              : item,
          ),
        )

        try {
          const output = await encryptFile({
            path: job.path,
            recipients,
            labels: labels.length > 0 ? labels : undefined,
            outDir,
          })
          outputs.push(output)
          setEncryptJobs((previous) =>
            previous.map((item) =>
              item.id === job.id
                ? {
                    ...item,
                    status: 'succeeded',
                    message: 'Done',
                    outputPath: output,
                  }
                : item,
            ),
          )
          appendLog({
            level: 'info',
            message: `Encrypted ${job.path} to ${output}`,
            context: 'ui',
          })
        } catch (error) {
          const message = error instanceof Error ? error.message : String(error)
          setEncryptJobs((previous) =>
            previous.map((item) =>
              item.id === job.id
                ? {
                    ...item,
                    status: 'failed',
                    message,
                  }
                : item,
            ),
          )
          addToast(message || 'Encryption failed', 'error')
          appendLog({
            level: 'error',
            message: `Encryption failed for ${job.path}: ${message}`,
            context: 'ui',
          })
        }
      }

      if (outputs.length > 0) {
        addToast(`Encrypted ${outputs.length} file${outputs.length > 1 ? 's' : ''}`, 'success')
      }

      setActiveOperation(null)
    },
    [
      addToast,
      appendLog,
      encryptJobs,
      encryptLabels,
      encryptOutputDirectory,
      encryptOutputMode,
      encryptRecipients,
    ],
  )

  const handleDecryptSubmit = useCallback(
    async (event?: React.FormEvent<HTMLFormElement>) => {
      if (event) {
        event.preventDefault()
      }

      if (decryptJobs.length === 0) {
        addToast('Select files to decrypt first.', 'warning')
        return
      }
      if (decryptOutputMode === 'directory' && !decryptOutputDirectory) {
        addToast('Choose an output directory.', 'warning')
        return
      }

      setActiveOperation('decrypt')
      setDecryptJobs((previous) =>
        previous.map((job) => ({
          ...job,
          status: 'queued',
          message: 'Queued',
        })),
      )

      const outputs: string[] = []
      const outDir =
        decryptOutputMode === 'directory' && decryptOutputDirectory
          ? decryptOutputDirectory
          : undefined

      for (const job of decryptJobs) {
        setDecryptJobs((previous) =>
          previous.map((item) =>
            item.id === job.id
              ? {
                  ...item,
                  status: 'running',
                  message: 'Running',
                }
              : item,
          ),
        )

        try {
          const output = await decryptFile({
            path: job.path,
            outDir,
          })
          outputs.push(output)
          setDecryptJobs((previous) =>
            previous.map((item) =>
              item.id === job.id
                ? {
                    ...item,
                    status: 'succeeded',
                    message: 'Done',
                    outputPath: output,
                  }
                : item,
            ),
          )
          appendLog({
            level: 'info',
            message: `Decrypted ${job.path} to ${output}`,
            context: 'ui',
          })
        } catch (error) {
          const message = error instanceof Error ? error.message : String(error)
          setDecryptJobs((previous) =>
            previous.map((item) =>
              item.id === job.id
                ? {
                    ...item,
                    status: 'failed',
                    message,
                  }
                : item,
            ),
          )
          addToast(message || 'Decryption failed', 'error')
          appendLog({
            level: 'error',
            message: `Decryption failed for ${job.path}: ${message}`,
            context: 'ui',
          })
        }
      }

      if (outputs.length > 0) {
        addToast(`Decrypted ${outputs.length} file${outputs.length > 1 ? 's' : ''}`, 'success')
      }

      setActiveOperation(null)
    },
    [
      addToast,
      appendLog,
      decryptJobs,
      decryptOutputDirectory,
      decryptOutputMode,
    ],
  )

  const stopCliCommand = useCallback(async () => {
    const child = cliChildRef.current
    if (!child) return
    try {
      await child.kill()
      appendLog({ level: 'warn', message: 'CLI command aborted by user', context: 'ui' })
    } catch (error) {
      console.error(error)
    } finally {
      cliChildRef.current = null
      setCliIsRunning(false)
    }
  }, [appendLog])

  const closeCliDialog = useCallback(() => {
    void stopCliCommand()
    setIsCliDialogOpen(false)
  }, [stopCliCommand])

  const handleCliTemplate = useCallback((definition: CliCommandDefinition) => {
    const hadPlaceholder = /<[^>]+>/.test(definition.label)
    let template = definition.label
      .replace(/\[|\]/g, '')
      .replace(/<[^>]+>/g, '')
      .replace(/\s+/g, ' ')
      .trim()
    if (hadPlaceholder && !template.endsWith(' ')) {
      template = `${template} `
    }
    setCliCommandText(template)
    setCliError('')
    setCliLogs([])
  }, [])

  const handleRunCli = useCallback(
    async (event?: React.FormEvent<HTMLFormElement>) => {
      if (event) {
        event.preventDefault()
      }

      const normalized = cliCommandText.trim()
      if (!normalized) {
        setCliError('Enter a command to run.')
        return
      }

      const tokens = sanitizeTokens(tokenizeCommand(normalized))
      if (tokens.length === 0) {
        setCliError('Unable to parse the provided command.')
        return
      }

      const definition = CLI_DEFINITIONS.find((item) => item.command === tokens[0])
      if (!definition) {
        const message = 'This command is not permitted in the CLI runner.'
        setCliError(message)
        addToast(message, 'error')
        appendLog({ level: 'warn', message: `Blocked CLI command: ${normalized}`, context: 'ui' })
        return
      }

      const validation = definition.validate(tokens)
      if (!validation.valid) {
        setCliError(validation.reason)
        addToast(validation.reason, 'warning')
        appendLog({ level: 'warn', message: `Invalid CLI arguments: ${validation.reason}`, context: 'ui' })
        return
      }

      setCliLogs([])
      setCliError('')
      setCliIsRunning(true)
      appendLog({ level: 'info', message: `Running CLI command: ${definition.label}`, context: 'ui' })

      try {
        const command = Command.create('data-guardian', tokens, { encoding: 'utf-8' })
        command.stdout.on('data', (line) => {
          setCliLogs((previous) => [...previous, { id: createId(), stream: 'stdout', message: line }])
        })
        command.stderr.on('data', (line) => {
          setCliLogs((previous) => [...previous, { id: createId(), stream: 'stderr', message: line }])
        })
        command.on('error', (message) => {
          setCliError(message)
          addToast(message, 'error')
          appendLog({ level: 'error', message: `CLI command error: ${message}`, context: 'ui' })
        })
        command.on('close', (payload) => {
          cliChildRef.current = null
          setCliIsRunning(false)
          if (payload.code === 0) {
            addToast('CLI command finished successfully', 'success')
            appendLog({ level: 'info', message: `CLI command completed: ${definition.label}`, context: 'ui' })
          } else {
            const message = `CLI exited with code ${payload.code ?? -1}`
            setCliError(message)
            addToast(message, 'warning')
            appendLog({ level: 'warn', message, context: 'ui' })
          }
        })

        const child = await command.spawn()
        cliChildRef.current = child
      } catch (error) {
        const message = error instanceof Error ? error.message : String(error)
        setCliError(message)
        setCliIsRunning(false)
        cliChildRef.current = null
        addToast(`Unable to run CLI: ${message}`, 'error')
        appendLog({ level: 'error', message: `Failed to spawn CLI: ${message}`, context: 'ui' })
      }
    },
    [addToast, appendLog, cliCommandText],
  )
  const actions: CommandAction[] = useMemo(
    () => [
      {
        id: 'encrypt-files',
        label: 'Encrypt files…',
        description: 'Protect plaintext files with envelope encryption',
        keywords: 'encrypt files security ctrl+e',
        run: openEncryptDialog,
      },
      {
        id: 'decrypt-files',
        label: 'Decrypt files…',
        description: 'Restore plaintext from encrypted envelopes',
        keywords: 'decrypt files security ctrl+d',
        run: openDecryptDialog,
      },
      {
        id: 'run-cli',
        label: 'Run CLI…',
        description: 'Execute a whitelisted data-guardian CLI command',
        keywords: 'cli terminal command shell',
        run: openCliDialog,
      },
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
    [
      handleLoadPolicy,
      handleOpenConfig,
      handleOpenLogs,
      handlePingCore,
      handleRedactFile,
      handleSelectPath,
      openCliDialog,
      openDecryptDialog,
      openEncryptDialog,
    ],
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

  const recentControllerMessages = useMemo(
    () => controllerMessages.slice(-6).reverse(),
    [controllerMessages],
  )

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
            <div className="quick-actions">
              <button type="button" className="primary-action" onClick={openEncryptDialog}>
                <span className="action-title">Encrypt files…</span>
                <span className="shortcut-hint">Ctrl/Cmd + E</span>
              </button>
              <button type="button" className="primary-action" onClick={openDecryptDialog}>
                <span className="action-title">Decrypt files…</span>
                <span className="shortcut-hint">Ctrl/Cmd + D</span>
              </button>
            </div>
            <div className="controller-card">
              <h3>Controller activity</h3>
              <ul className="controller-feed">
                {recentControllerMessages.map((message) => (
                  <li key={message.id} className={message.kind}>
                    <span className="timestamp">{formatTimestamp(message.timestamp)}</span>
                    <span className="message">{message.message}</span>
                  </li>
                ))}
                {recentControllerMessages.length === 0 && (
                  <li className="empty">Waiting for controller events.</li>
                )}
              </ul>
            </div>
            <div className="helper-card">
              <h3>Need something fast?</h3>
              <p>
                Press <strong>Ctrl/Cmd + K</strong> for the command palette, or jump straight into
                encryption with <strong>Ctrl/Cmd + E</strong> and decryption with{' '}
                <strong>Ctrl/Cmd + D</strong>.
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
                <span>Core binary override</span>
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

      {isEncryptDialogOpen && (
        <div className="modal" role="dialog" aria-modal="true" onClick={() => setIsEncryptDialogOpen(false)}>
          <div className="dialog-surface" role="document" onClick={(event) => event.stopPropagation()}>
            <header className="dialog-header">
              <h3>Encrypt files</h3>
              <button
                className="dialog-close"
                type="button"
                onClick={() => setIsEncryptDialogOpen(false)}
                aria-label="Close encrypt dialog"
              >
                ×
              </button>
            </header>
            <form className="dialog-body" onSubmit={handleEncryptSubmit}>
              <div className="field-group">
                <label>Files to encrypt</label>
                <div className="stacked">
                  <button type="button" onClick={handleSelectEncryptFiles}>
                    Choose files…
                  </button>
                  <ul className="job-list">
                    {encryptJobs.map((job) => (
                      <li key={job.id}>
                        <div>
                          <p className="job-path">{job.path}</p>
                          <span className={`job-status ${job.status}`}>
                            {job.message ?? STATUS_LABELS[job.status]}
                          </span>
                        </div>
                        {job.outputPath && (
                          <button type="button" onClick={() => handleRevealPath(job.outputPath)}>
                            Open output
                          </button>
                        )}
                      </li>
                    ))}
                    {encryptJobs.length === 0 && <li className="empty">No files selected yet.</li>}
                  </ul>
                </div>
              </div>

              <div className="field-group">
                <label>Recipients</label>
                <div className="token-input">
                  {encryptRecipients.map((recipient) => (
                    <span key={recipient} className="token">
                      {recipient}
                      <button
                        type="button"
                        onClick={() => removeRecipient(recipient)}
                        aria-label={`Remove recipient ${recipient}`}
                      >
                        ×
                      </button>
                    </span>
                  ))}
                  <input
                    value={encryptRecipientDraft}
                    onChange={(event) => setEncryptRecipientDraft(event.target.value)}
                    onKeyDown={handleRecipientKeyDown}
                    placeholder="Type a recipient and press Enter"
                  />
                </div>
                <div className="suggestions">
                  {ENCRYPT_RECIPIENT_SUGGESTIONS.map((recipient) => (
                    <button
                      key={recipient}
                      type="button"
                      onClick={() => handleRecipientSuggestion(recipient)}
                      disabled={encryptRecipients.includes(recipient)}
                    >
                      {recipient}
                    </button>
                  ))}
                </div>
              </div>

              <div className="field-group">
                <label>Labels (optional)</label>
                <div className="token-input">
                  {encryptLabels.map((label) => (
                    <span key={label} className="token">
                      {label}
                      <button
                        type="button"
                        onClick={() => removeLabel(label)}
                        aria-label={`Remove label ${label}`}
                      >
                        ×
                      </button>
                    </span>
                  ))}
                  <input
                    value={encryptLabelDraft}
                    onChange={(event) => setEncryptLabelDraft(event.target.value)}
                    onKeyDown={handleLabelKeyDown}
                    placeholder="Add a label and press Enter"
                  />
                </div>
                <div className="suggestions">
                  {ENCRYPT_LABEL_SUGGESTIONS.map((label) => (
                    <button
                      key={label}
                      type="button"
                      onClick={() => handleLabelSuggestion(label)}
                      disabled={encryptLabels.includes(label)}
                    >
                      {label}
                    </button>
                  ))}
                </div>
              </div>

              <div className="field-group">
                <label className="checkbox">
                  <input
                    type="checkbox"
                    checked={encryptOutputMode === 'sibling'}
                    onChange={(event) =>
                      setEncryptOutputMode(event.target.checked ? 'sibling' : 'directory')
                    }
                  />
                  <span>Write output next to source</span>
                </label>
                {encryptOutputMode === 'directory' && (
                  <div className="stacked">
                    <button type="button" onClick={handleSelectEncryptOutputDirectory}>
                      Choose output folder…
                    </button>
                    {encryptOutputDirectory && <p className="field-hint">{encryptOutputDirectory}</p>}
                  </div>
                )}
              </div>

              <div className="field-group">
                <h4>Recent progress</h4>
                <ul className="controller-feed">
                  {recentControllerMessages.map((message) => (
                    <li key={`${message.id}-encrypt`} className={message.kind}>
                      <span className="timestamp">{formatTimestamp(message.timestamp)}</span>
                      <span className="message">{message.message}</span>
                    </li>
                  ))}
                  {recentControllerMessages.length === 0 && (
                    <li className="empty">No controller messages yet.</li>
                  )}
                </ul>
              </div>

              <footer className="dialog-footer">
                <button type="button" onClick={() => setIsEncryptDialogOpen(false)}>
                  Cancel
                </button>
                <button
                  type="submit"
                  className="primary"
                  disabled=
                    {activeOperation !== null ||
                      encryptJobs.length === 0 ||
                      encryptRecipients.length === 0 ||
                      (encryptOutputMode === 'directory' && !encryptOutputDirectory)}
                >
                  Encrypt
                </button>
              </footer>
            </form>
          </div>
        </div>
      )}

      {isDecryptDialogOpen && (
        <div className="modal" role="dialog" aria-modal="true" onClick={() => setIsDecryptDialogOpen(false)}>
          <div className="dialog-surface" role="document" onClick={(event) => event.stopPropagation()}>
            <header className="dialog-header">
              <h3>Decrypt files</h3>
              <button
                className="dialog-close"
                type="button"
                onClick={() => setIsDecryptDialogOpen(false)}
                aria-label="Close decrypt dialog"
              >
                ×
              </button>
            </header>
            <form className="dialog-body" onSubmit={handleDecryptSubmit}>
              <div className="field-group">
                <label>Encrypted files</label>
                <div className="stacked">
                  <button type="button" onClick={handleSelectDecryptFiles}>
                    Choose files…
                  </button>
                  <ul className="job-list">
                    {decryptJobs.map((job) => (
                      <li key={job.id}>
                        <div>
                          <p className="job-path">{job.path}</p>
                          <span className={`job-status ${job.status}`}>
                            {job.message ?? STATUS_LABELS[job.status]}
                          </span>
                        </div>
                        {job.outputPath && (
                          <button type="button" onClick={() => handleRevealPath(job.outputPath)}>
                            Open output
                          </button>
                        )}
                      </li>
                    ))}
                    {decryptJobs.length === 0 && <li className="empty">No files selected yet.</li>}
                  </ul>
                </div>
              </div>

              <div className="field-group">
                <label className="checkbox">
                  <input
                    type="checkbox"
                    checked={decryptOutputMode === 'sibling'}
                    onChange={(event) =>
                      setDecryptOutputMode(event.target.checked ? 'sibling' : 'directory')
                    }
                  />
                  <span>Write output next to source</span>
                </label>
                {decryptOutputMode === 'directory' && (
                  <div className="stacked">
                    <button type="button" onClick={handleSelectDecryptOutputDirectory}>
                      Choose output folder…
                    </button>
                    {decryptOutputDirectory && <p className="field-hint">{decryptOutputDirectory}</p>}
                  </div>
                )}
              </div>

              <div className="field-group">
                <h4>Recent progress</h4>
                <ul className="controller-feed">
                  {recentControllerMessages.map((message) => (
                    <li key={`${message.id}-decrypt`} className={message.kind}>
                      <span className="timestamp">{formatTimestamp(message.timestamp)}</span>
                      <span className="message">{message.message}</span>
                    </li>
                  ))}
                  {recentControllerMessages.length === 0 && (
                    <li className="empty">No controller messages yet.</li>
                  )}
                </ul>
              </div>

              <footer className="dialog-footer">
                <button type="button" onClick={() => setIsDecryptDialogOpen(false)}>
                  Cancel
                </button>
                <button
                  type="submit"
                  className="primary"
                  disabled=
                    {activeOperation !== null ||
                      decryptJobs.length === 0 ||
                      (decryptOutputMode === 'directory' && !decryptOutputDirectory)}
                >
                  Decrypt
                </button>
              </footer>
            </form>
          </div>
        </div>
      )}

      {isCliDialogOpen && (
        <div className="modal" role="dialog" aria-modal="true" onClick={closeCliDialog}>
          <div
            className="dialog-surface dialog-surface--wide"
            role="document"
            onClick={(event) => event.stopPropagation()}
          >
            <header className="dialog-header">
              <h3>Run CLI command</h3>
              <button className="dialog-close" type="button" onClick={closeCliDialog} aria-label="Close CLI dialog">
                ×
              </button>
            </header>
            <form className="dialog-body" onSubmit={handleRunCli}>
              <div className="field-group">
                <label>Command</label>
                <input
                  value={cliCommandText}
                  onChange={(event) => {
                    setCliCommandText(event.target.value)
                    setCliError('')
                  }}
                  placeholder="e.g. --version"
                  list="cli-commands"
                />
                <datalist id="cli-commands">
                  {CLI_DEFINITIONS.map((definition) => (
                    <option key={definition.id} value={definition.label} />
                  ))}
                </datalist>
                <p className="field-hint">
                  data-guardian is invoked automatically. Only safe commands are allowed.
                </p>
                {cliError && <p className="field-error">{cliError}</p>}
              </div>

              <div className="field-group">
                <label>Examples</label>
                <div className="cli-suggestions">
                  {CLI_DEFINITIONS.map((definition) => (
                    <button key={definition.id} type="button" onClick={() => handleCliTemplate(definition)}>
                      {definition.sample}
                    </button>
                  ))}
                </div>
              </div>

              <div className="field-group">
                <label>Output</label>
                <div className="cli-output">
                  {cliLogs.map((entry) => (
                    <pre key={entry.id} className={`cli-line ${entry.stream}`}>
                      {entry.message}
                    </pre>
                  ))}
                  {cliLogs.length === 0 && <p className="empty">Output will appear here.</p>}
                </div>
              </div>

              <footer className="dialog-footer">
                <div className="spacer" />
                {cliIsRunning && (
                  <button type="button" onClick={stopCliCommand}>
                    Stop
                  </button>
                )}
                <button type="button" onClick={closeCliDialog}>
                  Close
                </button>
                <button type="submit" className="primary" disabled={cliIsRunning || !cliCommandText.trim()}>
                  Run command
                </button>
              </footer>
            </form>
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
