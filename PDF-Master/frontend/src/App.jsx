import React, { useCallback, useEffect, useMemo, useRef, useState } from 'react'
import { AnimatePresence, motion } from 'motion/react'
import {
  Activity, ArrowDownToLine, ArrowLeft, ArrowRight, ArrowUpRight, BadgeCheck,
  Check, CheckCircle2, ChevronRight, CircleHelp, Clock3, CloudUpload, Code2,
  FileArchive, FileCheck2, FileSearch, FileText, Files, Folder, Gauge, Grid2X2,
  History, Image, KeyRound, LayoutDashboard, Lock, LockKeyhole, Menu,
  MoreHorizontal, Search, Shield, ShieldCheck, Sparkles, WandSparkles, X, Zap
} from 'lucide-react'

const API = '/api'

const groups = [
  { id: 'all', label: 'All tools', icon: Grid2X2 },
  { id: 'pdf', label: 'PDF tools', icon: FileText },
  { id: 'convert', label: 'Convert files', icon: Files },
  { id: 'security', label: 'Security', icon: ShieldCheck },
]

const iconFor = (slug) => {
  if (slug.includes('folder')) return Folder
  if (slug.includes('lock') || slug.includes('unlock') || slug.includes('encrypt') || slug.includes('protect')) return LockKeyhole
  if (slug.includes('image') || slug.includes('jpg')) return Image
  if (slug.includes('scanner')) return FileSearch
  if (slug.includes('word') || slug.includes('text')) return FileText
  if (slug.includes('merge')) return Files
  if (slug.includes('split')) return FileArchive
  if (slug.includes('compress')) return Gauge
  if (slug.includes('rotate')) return Activity
  if (slug.includes('watermark')) return WandSparkles
  if (slug.includes('html')) return Code2
  return FileCheck2
}

const groupFor = (slug) => {
  if (['word-to-pdf', 'text-to-word', 'word-to-text', 'txt-to-pdf', 'html-to-pdf'].includes(slug)) return 'convert'
  if (['pdf-locker', 'pdf-unlocker', 'text-locker', 'text-unlocker', 'folder-locker', 'folder-unlocker', 'lock-file', 'unlock-file', 'encrypt-message'].includes(slug)) return 'security'
  return 'pdf'
}

const specs = {
  merge: { accept: '.pdf,application/pdf', multiple: true, hint: 'Add at least two PDF files.' },
  split: { accept: '.pdf,application/pdf', fields: [{ name: 'pages', label: 'Pages to extract', placeholder: '1-3,5' }] },
  'remove-pages': { accept: '.pdf,application/pdf', fields: [{ name: 'pages', label: 'Pages to remove', placeholder: '2,4-6' }] },
  'page-numbers': { accept: '.pdf,application/pdf', fields: [{ name: 'position', label: 'Number position', type: 'select', options: [['bottom', 'Bottom'], ['top', 'Top']] }] },
  repair: { accept: '.pdf,application/pdf' },
  compress: { accept: '.pdf,application/pdf' },
  rotate: { accept: '.pdf,application/pdf', fields: [{ name: 'degrees', label: 'Rotation', type: 'select', options: [['90', '90° clockwise'], ['180', '180°'], ['270', '270° clockwise']] }] },
  watermark: { accept: '.pdf,application/pdf', fields: [{ name: 'watermark', label: 'Watermark text', placeholder: 'CONFIDENTIAL' }] },
  'pdf-locker': { accept: '.pdf,application/pdf', password: 'create', hint: 'The output PDF itself will require this password when opened.' },
  'pdf-unlocker': { accept: '.pdf,application/pdf', password: 'unlock' },
  'pdf-scanner': { accept: '.pdf,application/pdf', optionalPassword: true, hint: 'The scanner reports structural indicators; it is not antivirus software.' },
  'pdf-to-jpg': { accept: '.pdf,application/pdf' },
  'jpg-to-pdf': { accept: '.jpg,.jpeg,.png,.webp,image/jpeg,image/png,image/webp', multiple: true },
  'extract-text': { accept: '.pdf,application/pdf' },
  'pdf-to-word': { accept: '.pdf,application/pdf', hint: 'Best results with text-based PDFs. Scanned pages require OCR.' },
  'word-to-pdf': { accept: '.doc,.docx,application/msword,application/vnd.openxmlformats-officedocument.wordprocessingml.document' },
  'text-to-word': { accept: '.txt,text/plain' },
  'word-to-text': { accept: '.docx,application/vnd.openxmlformats-officedocument.wordprocessingml.document' },
  'txt-to-pdf': { accept: '.txt,text/plain' },
  'pdf-to-html': { accept: '.pdf,application/pdf' },
  'html-to-pdf': { accept: '.html,.htm,text/html' },
  'text-locker': { accept: '.txt,text/plain', password: 'create' },
  'text-unlocker': { accept: '.pmx,application/octet-stream', password: 'unlock' },
  'folder-locker': { desktopOnly: true },
  'folder-unlocker': { accept: '.pmf,application/octet-stream', password: 'unlock' },
  'lock-file': { accept: '*/*', password: 'create' },
  'unlock-file': { accept: '.pme,application/octet-stream', password: 'unlock' },
  'encrypt-message': { message: true, password: 'create' },
}

const formatBytes = (size) => {
  if (!size && size !== 0) return ''
  if (size < 1024) return `${size} B`
  if (size < 1024 * 1024) return `${(size / 1024).toFixed(1)} KB`
  return `${(size / (1024 * 1024)).toFixed(2)} MB`
}

const cookie = (name) => document.cookie.split('; ').find((part) => part.startsWith(`${name}=`))?.split('=').slice(1).join('=')

function App() {
  const [route, setRoute] = useState(window.location.pathname)
  const [bootstrap, setBootstrap] = useState({ tools: [], recent: [] })
  const [history, setHistory] = useState([])
  const [loading, setLoading] = useState(true)
  const [query, setQuery] = useState('')
  const [activeGroup, setActiveGroup] = useState('all')
  const [mobileNav, setMobileNav] = useState(false)
  const [toast, setToast] = useState('')

  const navigate = useCallback((path) => {
    if (window.location.pathname !== path) window.history.pushState({}, '', path)
    setRoute(path)
    setMobileNav(false)
    window.scrollTo({ top: 0, behavior: 'smooth' })
  }, [])

  useEffect(() => {
    const onPop = () => setRoute(window.location.pathname)
    window.addEventListener('popstate', onPop)
    return () => window.removeEventListener('popstate', onPop)
  }, [])

  const refreshData = useCallback(async () => {
    try {
      const [configRes, historyRes] = await Promise.all([fetch(`${API}/bootstrap/`), fetch(`${API}/history/`)])
      if (!configRes.ok || !historyRes.ok) throw new Error('Could not load PDF Master data.')
      const configData = await configRes.json()
      const historyData = await historyRes.json()
      setBootstrap(configData)
      setHistory(historyData.records || [])
    } catch (error) {
      setToast(error.message || 'Could not connect to PDF Master.')
    } finally {
      setLoading(false)
    }
  }, [])

  useEffect(() => { refreshData() }, [refreshData])

  useEffect(() => {
    if (!toast) return undefined
    const timer = window.setTimeout(() => setToast(''), 3600)
    return () => window.clearTimeout(timer)
  }, [toast])

  const visibleTools = useMemo(() => {
    return (bootstrap.tools || []).filter((tool) => !['protect', 'unlock', 'encrypt-text', 'decrypt-text'].includes(tool.slug))
  }, [bootstrap.tools])

  const activeSlug = route.match(/^\/tool\/([^/]+)\/?$/)?.[1]
  const activeTool = activeSlug ? visibleTools.find((tool) => tool.slug === activeSlug) : null
  const isHistory = route.startsWith('/history')

  const filteredTools = visibleTools.filter((tool) => {
    const matchesGroup = activeGroup === 'all' || groupFor(tool.slug) === activeGroup
    const search = `${tool.name} ${tool.description}`.toLowerCase()
    return matchesGroup && search.includes(query.toLowerCase())
  })

  return (
    <div className="app-shell">
      <div className={`mobile-scrim ${mobileNav ? 'show' : ''}`} onClick={() => setMobileNav(false)} />
      <Sidebar activeGroup={activeGroup} setActiveGroup={setActiveGroup} navigate={navigate} mobileNav={mobileNav} />
      <main className="main-shell">
        <Topbar query={query} setQuery={setQuery} onMenu={() => setMobileNav((v) => !v)} />
        <AnimatePresence mode="wait">
          {activeTool ? (
            <ToolWorkspace key={activeTool.slug} tool={activeTool} navigate={navigate} setToast={setToast} onProcessed={refreshData} />
          ) : isHistory ? (
            <HistoryPage key="history" records={history} navigate={navigate} />
          ) : (
            <Dashboard
              key="dashboard"
              tools={filteredTools}
              totalTools={visibleTools.length}
              recent={history.slice(0, 5)}
              query={query}
              setQuery={setQuery}
              activeGroup={activeGroup}
              setActiveGroup={setActiveGroup}
              navigate={navigate}
              loading={loading}
            />
          )}
        </AnimatePresence>
      </main>
      <AnimatePresence>
        {toast && <motion.div className="toast" initial={{ opacity: 0, y: 18 }} animate={{ opacity: 1, y: 0 }} exit={{ opacity: 0, y: 12 }}><CircleHelp size={17} />{toast}</motion.div>}
      </AnimatePresence>
    </div>
  )
}

function Sidebar({ activeGroup, setActiveGroup, navigate, mobileNav }) {
  return (
    <motion.aside className={`sidebar ${mobileNav ? 'mobile-open' : ''}`} initial={false}>
      <button className="brand" onClick={() => { setActiveGroup('all'); navigate('/') }}>
        <span className="brand-mark"><FileText size={19} strokeWidth={2.3} /></span>
        <span>pdf<span className="brand-accent">master</span><small>DOCUMENT WORKSPACE</small></span>
      </button>
      <div className="sidebar-section-label">WORKSPACE</div>
      <button className={`nav-item ${!window.location.pathname.startsWith('/history') && activeGroup === 'all' ? 'active' : ''}`} onClick={() => { setActiveGroup('all'); navigate('/') }}><LayoutDashboard size={18} />Dashboard<span className="nav-dot" /></button>
      <button className={`nav-item ${window.location.pathname.startsWith('/history') ? 'active' : ''}`} onClick={() => navigate('/history/')}><History size={18} />Recent files</button>
      <div className="sidebar-section-label tools-label">TOOL CATEGORIES</div>
      {groups.slice(1).map((group) => {
        const Icon = group.icon
        return <button key={group.id} className={`nav-item ${activeGroup === group.id && !window.location.pathname.startsWith('/history') ? 'active' : ''}`} onClick={() => { setActiveGroup(group.id); navigate('/') }}><Icon size={18} />{group.label}</button>
      })}
      <div className="sidebar-spacer" />
      <div className="sidebar-security">
        <div className="security-icon"><ShieldCheck size={19} /></div>
        <b>Your files, your control</b>
        <p>No public account. Processing history is scoped to this browser session.</p>
        <div className="security-status"><span /> PRIVATE SESSION</div>
      </div>
      <div className="sidebar-footer"><span className="avatar">PM</span><div><b>PDF Master</b><small>Personal workspace</small></div><MoreHorizontal size={18} /></div>
    </motion.aside>
  )
}

function Topbar({ query, setQuery, onMenu }) {
  return (
    <header className="topbar">
      <button className="mobile-menu icon-button" onClick={onMenu}><Menu size={20} /></button>
      <div className="breadcrumb"><span>Workspace</span><ChevronRight size={14} /><b>Overview</b></div>
      <div className="topbar-right">
        <label className="global-search"><Search size={16} /><input value={query} onChange={(e) => setQuery(e.target.value)} placeholder="Search tools..." /><kbd>⌘ K</kbd></label>
        <span className="topbar-divider" />
        <div className="topbar-status"><span /> All systems ready</div>
        <span className="avatar avatar-top">PM</span>
      </div>
    </header>
  )
}

function Dashboard({ tools, totalTools, recent, query, setQuery, activeGroup, setActiveGroup, navigate, loading }) {
  return (
    <motion.div className="page-content" initial={{ opacity: 0, y: 14 }} animate={{ opacity: 1, y: 0 }} exit={{ opacity: 0, y: -8 }} transition={{ duration: .28 }}>
      <section className="welcome-row">
        <div><div className="eyebrow"><Sparkles size={13} /> YOUR FILE WORKSPACE</div><h1>Make files <span>work smarter.</span></h1><p>Everything you need to convert, organize, inspect and protect your documents.</p></div>
        <div className="welcome-actions"><div className="local-badge"><span /> PRIVATE BY DEFAULT</div><button className="button button-primary" onClick={() => document.getElementById('tool-library')?.scrollIntoView({ behavior: 'smooth' })}>Explore tools <ArrowRight size={16} /></button></div>
      </section>

      <section className="hero-panel">
        <div className="hero-copy">
          <div className="hero-kicker"><span className="sparkle-dot"><Zap size={13} fill="currentColor" /></span> YOUR DOCUMENTS, SIMPLIFIED</div>
          <h2>One workspace.<br /><em>Every file handled.</em></h2>
          <p>Convert formats, safeguard sensitive files, and get useful insights from PDFs — without juggling different apps.</p>
          <div className="hero-buttons"><button className="button button-light" onClick={() => { setActiveGroup('all'); document.getElementById('tool-library')?.scrollIntoView({ behavior: 'smooth' }) }}>Browse all tools <ArrowUpRight size={16} /></button><span className="hero-trust"><ShieldCheck size={15} /> No sign-up required</span></div>
        </div>
        <div className="hero-visual" aria-hidden="true">
          <motion.div className="orbit orbit-one" animate={{ rotate: 360 }} transition={{ duration: 42, repeat: Infinity, ease: 'linear' }} />
          <motion.div className="orbit orbit-two" animate={{ rotate: -360 }} transition={{ duration: 54, repeat: Infinity, ease: 'linear' }} />
          <motion.div className="hero-file-card" initial={{ y: 10, rotate: -7 }} animate={{ y: [0, -8, 0], rotate: [-7, -5, -7] }} transition={{ duration: 5, repeat: Infinity, ease: 'easeInOut' }}><div className="file-card-top"><span className="pdf-chip">PDF</span><MoreHorizontal size={17} /></div><div className="file-lines"><i /><i /><i /><i /></div><div className="file-card-bottom"><span>Document ready</span><CheckCircle2 size={17} /></div></motion.div>
          <motion.div className="floating-chip chip-convert" animate={{ y: [0, -6, 0] }} transition={{ duration: 3.7, repeat: Infinity }}><FileCheck2 size={16} /> Smart convert</motion.div>
          <motion.div className="floating-chip chip-secure" animate={{ y: [0, 7, 0] }} transition={{ duration: 4.2, repeat: Infinity }}><Lock size={15} /> Protected</motion.div>
          <div className="glow-ring" />
        </div>
        <div className="hero-bottom"><span><b>{totalTools || '—'}</b> tools ready</span><span className="hero-separator" /><span><b>25 MB</b> max file size per upload</span><span className="hero-separator" /><span><b>AES-256</b> protected vault format</span></div>
      </section>

      <section className="metrics-row">
        <MetricCard icon={Grid2X2} label="Available tools" value={totalTools || '—'} note="Across your workflow" tone="violet" />
        <MetricCard icon={ShieldCheck} label="Security tools" value={tools.filter((t) => groupFor(t.slug) === 'security').length || '—'} note="Lock, unlock and inspect" tone="green" />
        <MetricCard icon={Clock3} label="Recent activity" value={recent.length} note="In this browser session" tone="blue" />
        <MetricCard icon={Zap} label="Quick access" value="Ready" note="No account setup needed" tone="amber" />
      </section>

      <section className="tool-section" id="tool-library">
        <div className="section-heading"><div><div className="eyebrow">THE TOOLKIT</div><h2>Find the right tool</h2><p>Purpose-built utilities for your everyday documents.</p></div><div className="tool-count"><span>{tools.length}</span> shown</div></div>
        <div className="tool-toolbar">
          <div className="filter-tabs">
            {groups.map((group) => <button key={group.id} className={activeGroup === group.id ? 'selected' : ''} onClick={() => setActiveGroup(group.id)}>{group.label}</button>)}
          </div>
          <label className="library-search"><Search size={15} /><input value={query} onChange={(e) => setQuery(e.target.value)} placeholder="Filter tools" /><kbd>/</kbd></label>
        </div>
        {loading ? <div className="loading-grid">{Array.from({ length: 8 }).map((_, i) => <div key={i} className="skeleton-card" />)}</div> : tools.length ? <motion.div layout className="tool-grid">
          {tools.map((tool, index) => <ToolCard key={tool.slug} tool={tool} index={index} onClick={() => navigate(`/tool/${tool.slug}/`)} />)}
        </motion.div> : <div className="empty-state"><Search size={24} /><b>No matching tools</b><p>Try a different search term or category.</p><button className="button button-quiet" onClick={() => { setQuery(''); setActiveGroup('all') }}>Clear filters</button></div>}
      </section>

      <section className="bottom-grid">
        <div className="desktop-callout">
          <div className="callout-icon"><Folder size={22} /></div><div><div className="eyebrow">WINDOWS DESKTOP COMPANION</div><h3>Want a folder shortcut that asks for a password?</h3><p>On Windows, run desktop_locker\run_locker.bat and choose Lock a Folder. It replaces the original with a folder-icon shortcut; double-click it in File Explorer to unlock.</p></div><div className="callout-label">WINDOWS ONLY <ArrowUpRight size={15} /></div>
        </div>
        <div className="recent-panel"><div className="recent-heading"><div><div className="eyebrow">ACTIVITY</div><h3>Recently processed</h3></div><button className="text-button" onClick={() => navigate('/history/')}>View all <ArrowRight size={14} /></button></div>
          {recent.length ? recent.slice(0, 4).map((item) => <RecentRow key={item.id} item={item} />) : <div className="recent-empty"><Clock3 size={19} /><span>Your recent files will show up here after you run a tool.</span></div>}
        </div>
      </section>
      <footer className="workspace-footer"><span>PDF Master <b>v6</b></span><span>Made for focused document work <Sparkles size={13} /></span><span className="repo-note">GitHub-ready source <ArrowUpRight size={13} /></span></footer>
    </motion.div>
  )
}

function MetricCard({ icon: Icon, label, value, note, tone }) {
  return <motion.div className="metric-card" whileHover={{ y: -3 }} transition={{ type: 'spring', stiffness: 320, damping: 24 }}><div className={`metric-icon ${tone}`}><Icon size={18} /></div><div className="metric-label">{label}</div><div className="metric-value">{value}</div><div className="metric-note">{note}</div></motion.div>
}

function ToolCard({ tool, index, onClick }) {
  const Icon = iconFor(tool.slug)
  const group = groupFor(tool.slug)
  return <motion.button className="tool-card" onClick={onClick} layout initial={{ opacity: 0, y: 16 }} animate={{ opacity: 1, y: 0 }} transition={{ delay: Math.min(index * .025, .18), duration: .25 }} whileHover={{ y: -5, scale: 1.012 }} whileTap={{ scale: .985 }}>
    <div className="tool-card-top"><div className={`tool-icon ${group}`}><Icon size={19} /></div><ArrowUpRight className="tool-arrow" size={17} /></div>
    <b>{tool.name}</b><p>{tool.description}</p><div className={`tool-tag ${group}`}>{group === 'pdf' ? 'PDF TOOL' : group === 'convert' ? 'CONVERT' : 'SECURITY'}</div>
  </motion.button>
}

function ToolWorkspace({ tool, navigate, setToast, onProcessed }) {
  const spec = specs[tool.slug] || { accept: '.pdf,application/pdf' }
  const inputRef = useRef(null)
  const [files, setFiles] = useState([])
  const [dragging, setDragging] = useState(false)
  const [password, setPassword] = useState('')
  const [confirmPassword, setConfirmPassword] = useState('')
  const [message, setMessage] = useState('')
  const [fields, setFields] = useState({})
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState('')
  const [result, setResult] = useState(null)

  const addFiles = (list) => {
    const next = Array.from(list || [])
    setFiles(spec.multiple || spec.folder ? next : next.slice(0, 1))
    setError('')
    setResult(null)
  }

  const submit = async (event) => {
    event.preventDefault()
    setError('')
    if (!spec.message && !files.length) { setError(spec.folder ? 'Choose a folder first.' : 'Add a file to continue.'); return }
    if (spec.password && password.length < 8) { setError('Use a password with at least 8 characters.'); return }
    if (spec.password === 'create' && password !== confirmPassword) { setError('The password confirmation does not match.'); return }
    if (spec.message && !message.trim()) { setError('Enter a message to encrypt.'); return }
    if (files.some((file) => file.size > 25 * 1024 * 1024)) { setError('Each file must be 25 MB or smaller.'); return }
    if (spec.folder && files.reduce((total, file) => total + file.size, 0) > 25 * 1024 * 1024) { setError('The selected folder must be 25 MB or smaller in total.'); return }

    const body = new FormData()
    files.forEach((file) => body.append('files', file, file.name))
    if (spec.folder) body.append('folder_manifest', JSON.stringify(files.map((file) => ({ path: file.webkitRelativePath || file.name }))))
    if (spec.password || spec.optionalPassword) body.append('password', password)
    if (spec.message) body.append('message', message)
    Object.entries(fields).forEach(([key, value]) => body.append(key, value))

    setBusy(true)
    try {
      const response = await fetch(`${API}/process/${tool.slug}/`, {
        method: 'POST', body,
        headers: { 'X-CSRFToken': decodeURIComponent(cookie('csrftoken') || '') },
      })
      const data = await response.json().catch(() => ({}))
      if (!response.ok) throw new Error(data.error || 'The operation could not be completed.')
      setResult(data)
      onProcessed()
    } catch (err) {
      setError(err.message || 'Processing failed. Please try again.')
    } finally {
      setBusy(false)
    }
  }

  const changeField = (name, value) => setFields((current) => ({ ...current, [name]: value }))
  const Icon = iconFor(tool.slug)

  if (spec.desktopOnly) return <DesktopFolderLockerWorkspace tool={tool} navigate={navigate} />

  return <motion.div className="page-content tool-page" initial={{ opacity: 0, y: 14 }} animate={{ opacity: 1, y: 0 }} exit={{ opacity: 0, y: -8 }} transition={{ duration: .25 }}>
    <div className="tool-breadcrumb"><button onClick={() => navigate('/')}><ArrowLeft size={15} /> All tools</button><ChevronRight size={14} /><span>{tool.name}</span></div>
    <div className="tool-page-header"><div className={`large-tool-icon ${groupFor(tool.slug)}`}><Icon size={25} /></div><div><div className="eyebrow">{groupFor(tool.slug).toUpperCase()} WORKSPACE</div><h1>{tool.name}</h1><p>{tool.description}</p></div></div>
    <div className="tool-workspace-grid">
      <form className="process-card" onSubmit={submit}>
        <div className="process-card-heading"><div><h2>{result ? 'Your file is ready' : 'Add your files'}</h2><p>{result ? 'Processing completed successfully.' : 'Select or drop the content you want to work with.'}</p></div><span className="step-count">{result ? 'DONE' : '01 / INPUT'}</span></div>
        {!result ? <>
          {!spec.message && <>
            <div className={`dropzone ${dragging ? 'dragging' : ''} ${files.length ? 'has-files' : ''}`} onClick={() => inputRef.current?.click()} onDragOver={(e) => { e.preventDefault(); setDragging(true) }} onDragLeave={() => setDragging(false)} onDrop={(e) => { e.preventDefault(); setDragging(false); addFiles(e.dataTransfer.files) }}>
              <input ref={inputRef} type="file" hidden accept={spec.accept || '*/*'} multiple={!!(spec.multiple || spec.folder)} onChange={(e) => addFiles(e.target.files)} {...(spec.folder ? { webkitdirectory: '', directory: '' } : {})} />
              <div className="dropzone-graphic"><CloudUpload size={25} /></div>
              <b>{spec.folder ? 'Choose a folder' : 'Drag and drop your files here'}</b>
              <span>{spec.folder ? 'Select a folder from your computer' : 'or click to browse from your device'}</span>
              <small>{spec.folder ? 'Folder structure is preserved · 25 MB total limit' : spec.multiple ? 'Multiple files supported · 25 MB per file' : 'One file · 25 MB maximum'}</small>
            </div>
            {files.length > 0 && <div className="selected-files"><div className="selected-heading"><span>{files.length} {files.length === 1 ? 'file' : 'files'} selected</span><button type="button" onClick={() => setFiles([])}>Remove all</button></div>{files.slice(0, 6).map((file, index) => <div className="selected-file" key={`${file.name}-${index}`}><div className="mini-file-icon"><FileText size={16} /></div><div className="selected-file-name"><b>{file.webkitRelativePath || file.name}</b><small>{formatBytes(file.size)}</small></div><CheckCircle2 size={17} className="file-check" /></div>)}{files.length > 6 && <div className="more-files">+ {files.length - 6} more files</div>}</div>}
          </>}
          {spec.message && <label className="field-label">Message to encrypt<textarea className="message-input" rows="6" value={message} onChange={(e) => setMessage(e.target.value)} placeholder="Write your private message..." /></label>}
          {spec.fields?.map((field) => <label className="field-label" key={field.name}>{field.label}{field.type === 'select' ? <select value={fields[field.name] || field.options[0][0]} onChange={(e) => changeField(field.name, e.target.value)}>{field.options.map(([value, label]) => <option key={value} value={value}>{label}</option>)}</select> : <input value={fields[field.name] || ''} onChange={(e) => changeField(field.name, e.target.value)} placeholder={field.placeholder} required />}</label>)}
          {(spec.password || spec.optionalPassword) && <div className="password-fields">
            <label className="field-label">{spec.password === 'unlock' ? 'Password' : spec.password === 'create' ? 'Create password' : 'PDF password (optional)'}<div className="password-input-wrap"><KeyRound size={16} /><input type="password" value={password} onChange={(e) => setPassword(e.target.value)} placeholder={spec.password === 'unlock' ? 'Enter your password' : 'At least 8 characters'} required={!!spec.password} autoComplete="new-password" /></div></label>
            {spec.password === 'create' && <label className="field-label">Confirm password<div className="password-input-wrap"><Lock size={16} /><input type="password" value={confirmPassword} onChange={(e) => setConfirmPassword(e.target.value)} placeholder="Re-enter password" required /></div></label>}
          </div>}
          {spec.hint && <div className="hint-banner"><CircleHelp size={16} /><span>{spec.hint}</span></div>}
          {error && <motion.div className="inline-error" initial={{ opacity: 0, y: -5 }} animate={{ opacity: 1, y: 0 }}><X size={15} />{error}</motion.div>}
          <button className="button button-primary process-button" disabled={busy}>{busy ? <><span className="spinner" /> Working on it...</> : <>{tool.slug.includes('scanner') ? 'Scan document' : tool.slug.includes('locker') || tool.slug === 'lock-file' ? 'Lock securely' : tool.slug.includes('unlock') ? 'Unlock file' : tool.slug === 'encrypt-message' ? 'Encrypt message' : 'Process file'} <ArrowRight size={16} /></>}</button>
        </> : <div className="success-state"><div className="success-check"><Check size={27} /></div><h3>Ready to download</h3><p>{result.filename} has been created.</p><div className="result-file"><div className="result-file-icon"><FileCheck2 size={21} /></div><div><b>{result.filename}</b><small>Processed by {tool.name}</small></div><BadgeCheck size={19} /></div><a className="button button-primary download-button" href={result.download_url}><ArrowDownToLine size={17} /> Download result</a><button className="button button-quiet" onClick={() => { setResult(null); setFiles([]); setPassword(''); setConfirmPassword(''); setMessage(''); setFields({}) }}>Process another file</button></div>}
        <div className="process-card-foot"><ShieldCheck size={15} /><span>Passwords are not stored. Use files you are authorized to process.</span><span className="secure-dot" /></div>
      </form>

      <aside className="tool-info-column">
        <div className="info-card info-card-accent"><div className="info-card-icon"><Sparkles size={19} /></div><h3>Designed for clarity</h3><p>Keep your workflow simple: upload, choose options, process and download the result.</p><div className="info-points"><span><Check size={14} /> Clear output naming</span><span><Check size={14} /> Session-scoped file history</span><span><Check size={14} /> No public account required</span></div></div>
        <div className="info-card"><h3>Before you start</h3><div className="info-line"><span>Maximum upload</span><b>25 MB</b></div><div className="info-line"><span>Supported operation</span><b>{spec.multiple ? 'Multiple files' : spec.folder ? 'Folder selection' : 'Single file'}</b></div><div className="info-line"><span>Processing</span><b>On server</b></div><p className="small-note">For production deployment, use HTTPS and configure private media storage.</p></div>
      </aside>
    </div>
  </motion.div>
}

function DesktopFolderLockerWorkspace({ tool, navigate }) {
  return <motion.div className="page-content tool-page" initial={{ opacity: 0, y: 14 }} animate={{ opacity: 1, y: 0 }} exit={{ opacity: 0, y: -8 }} transition={{ duration: .25 }}>
    <div className="tool-breadcrumb"><button onClick={() => navigate('/')}><ArrowLeft size={15} /> All tools</button><ChevronRight size={14} /><span>{tool.name}</span></div>
    <div className="tool-page-header"><div className="large-tool-icon security"><Folder size={25} /></div><div><div className="eyebrow">WINDOWS DESKTOP SECURITY</div><h1>Folder Locker</h1><p>Double-click a folder-shaped shortcut in File Explorer and enter its password to open the protected folder.</p></div></div>
    <div className="desktop-locker-layout">
      <section className="process-card desktop-locker-card">
        <div className="desktop-locker-kicker"><ShieldCheck size={16} /> WINDOWS DESKTOP COMPANION</div>
        <h2>Lock a folder. Keep a familiar click-to-open workflow.</h2>
        <p className="desktop-locker-lead">The website cannot replace folders on your PC or intercept File Explorer double-clicks. The Windows companion does that local step.</p>
        <div className="desktop-steps">
          <div className="desktop-step"><span>01</span><div><b>Start the desktop locker</b><p>From the extracted project folder, run this Windows batch file:</p><code>desktop_locker\run_locker.bat</code></div></div>
          <div className="desktop-step"><span>02</span><div><b>Choose “Lock a Folder”</b><p>Select your folder, set a password of at least 10 characters, and read the replacement warning.</p></div></div>
          <div className="desktop-step"><span>03</span><div><b>Double-click the folder shortcut</b><p>After the encrypted vault is verified, the original folder is replaced by a folder-icon shortcut. Double-click it in File Explorer to get the password prompt.</p></div></div>
        </div>
        <div className="desktop-locker-command"><div><small>RUN FROM THE PROJECT ROOT</small><code>desktop_locker\run_locker.bat</code></div><button className="button button-quiet" onClick={() => navigator.clipboard?.writeText('desktop_locker\\run_locker.bat')}>Copy command</button></div>
        <div className="hint-banner"><CircleHelp size={16} /><span>Windows requires a shortcut or a dedicated mounted vault for this behaviour. The shortcut opens a decrypted working copy in your Windows profile; use “Clear Unlocked Copies” when finished. It does not automatically re-lock edited files when Explorer closes.</span></div>
      </section>
      <aside className="tool-info-column">
        <div className="info-card info-card-accent"><div className="info-card-icon"><LockKeyhole size={19} /></div><h3>What stays protected?</h3><p>The encrypted <b>.pmlock</b> container is kept inside the hidden <b>.PDFMasterVault</b> folder. The folder-shaped shortcut does not contain the documents.</p></div>
        <div className="info-card"><h3>Before locking</h3><div className="info-line"><span>Password</span><b>10+ characters</b></div><div className="info-line"><span>Encryption</span><b>AES-256-GCM</b></div><div className="info-line"><span>Platform</span><b>Windows 10 / 11</b></div><p className="small-note">Keep the hidden vault and its shortcut. Do not delete either. Ordinary deletion is not secure erasure.</p></div>
      </aside>
    </div>
  </motion.div>
}

function HistoryPage({ records, navigate }) {
  return <motion.div className="page-content history-page" initial={{ opacity: 0, y: 12 }} animate={{ opacity: 1, y: 0 }} exit={{ opacity: 0, y: -8 }}>
    <div className="eyebrow">YOUR WORKSPACE</div><div className="section-heading history-heading"><div><h1>Recent files</h1><p>Outputs created in this browser session.</p></div><button className="button button-quiet" onClick={() => navigate('/')}>Back to dashboard</button></div>
    <div className="history-table"><div className="history-table-head"><span>FILE</span><span>TOOL</span><span>DATE</span><span>DOWNLOAD</span></div>
      {records.length ? records.map((item) => <div className="history-table-row" key={item.id}><div className="history-name"><div className="mini-file-icon"><FileText size={16} /></div><b>{item.original_name || item.filename}</b></div><span className="history-tool">{item.tool_name}</span><span className="history-date">{new Date(item.created_at).toLocaleString()}</span><a href={item.download_url} className="history-download"><ArrowDownToLine size={15} /> Download</a></div>) : <div className="history-empty"><History size={23} /><b>No activity yet</b><p>Processed files will appear here.</p><button className="button button-primary" onClick={() => navigate('/')}>Explore tools <ArrowRight size={15} /></button></div>}
    </div>
    <div className="history-disclaimer"><Shield size={16} /><span>This list is limited to the current browser session. Processed files are stored on the Django server until deployment-specific cleanup is configured.</span></div>
  </motion.div>
}

function RecentRow({ item }) {
  return <div className="recent-row"><div className="recent-file-icon"><FileText size={16} /></div><div className="recent-file-main"><b>{item.original_name || item.filename}</b><small>{item.tool_name} · {new Date(item.created_at).toLocaleString()}</small></div><a href={item.download_url} title="Download"><ArrowDownToLine size={16} /></a></div>
}

export default App
