import { useEffect, useRef, useState } from 'react'
import { ArrowDownToLine, Check, CloudUpload, FileText, FolderPlus, Link2, MoreHorizontal, Presentation, RefreshCw, Trash2, Video } from 'lucide-react'
import { createSubject, deleteSource, deleteSubject, getApiErrorMessage, getSources, getSubjects, updateSubject, uploadFile, uploadYoutube } from '../api'
import ActionHub from '../components/ActionHub'
import LoadingStatus from '../components/LoadingStatus'

const acceptedTypes = ['.pdf', '.pptx', '.mp4']
const subjectColors = ['#4f8a72', '#c76550', '#c1932f', '#4f79a4', '#916b9c', '#3f8584']

function SourceIcon({ sourceType }) {
  if (sourceType === 'slides') return <Presentation size={17} />
  if (sourceType === 'video') return <Video size={17} />
  return <FileText size={17} />
}

function statusLabel(status) {
  return status === 'ready' ? 'Ready' : status === 'failed' ? 'Needs attention' : 'Processing'
}

export default function Upload() {
  const inputRef = useRef(null)
  const [subjects, setSubjects] = useState([])
  const [subjectsLoading, setSubjectsLoading] = useState(true)
  const [selectedSubjectId, setSelectedSubjectId] = useState(() => window.localStorage.getItem('studymate_subject_id') ?? '')
  const [showSubjectForm, setShowSubjectForm] = useState(false)
  const [subjectName, setSubjectName] = useState('')
  const [subjectColor, setSubjectColor] = useState(subjectColors[0])
  const [subjectBusy, setSubjectBusy] = useState(false)
  const [sources, setSources] = useState([])
  const [loadedSourcesSubjectId, setLoadedSourcesSubjectId] = useState('')
  const [refreshingSources, setRefreshingSources] = useState(false)
  const [sourceError, setSourceError] = useState('')
  const [youtubeUrl, setYoutubeUrl] = useState('')
  const [busy, setBusy] = useState(false)
  const [dragging, setDragging] = useState(false)
  const [error, setError] = useState('')
  const [notice, setNotice] = useState('')
  const [deletingSource, setDeletingSource] = useState(null)
  const [toast, setToast] = useState('')

  useEffect(() => {
    let active = true
    const loadSubjects = async () => {
      try {
        const items = await getSubjects()
        if (!active) return
        setSubjects(items)
        const storedSubjectId = window.localStorage.getItem('studymate_subject_id') ?? ''
        const current = items.some((subject) => String(subject.id) === storedSubjectId)
          ? storedSubjectId
          : items[0] ? String(items[0].id) : ''
        setSelectedSubjectId(current)
      } catch (requestError) {
        if (active) setSourceError(getApiErrorMessage(requestError, 'Could not load your subjects.'))
      } finally {
        if (active) setSubjectsLoading(false)
      }
    }
    loadSubjects()
    return () => { active = false }
  }, [])

  useEffect(() => {
    window.localStorage.setItem('studymate_subject_id', selectedSubjectId)
    if (!selectedSubjectId) return undefined
    let active = true
    const loadSources = async () => {
      try {
        const items = await getSources(selectedSubjectId)
        if (active) setSources(items)
        if (active) setSourceError('')
      } catch (requestError) {
        if (active) setSourceError(getApiErrorMessage(requestError, 'Could not load your sources.'))
      } finally {
        if (active) setLoadedSourcesSubjectId(selectedSubjectId)
      }
    }
    loadSources()
    const interval = window.setInterval(loadSources, 3000)
    return () => {
      active = false
      window.clearInterval(interval)
    }
  }, [selectedSubjectId])

  const sourcesLoading = subjectsLoading || (Boolean(selectedSubjectId) && loadedSourcesSubjectId !== selectedSubjectId)

  const refreshSources = async () => {
    setRefreshingSources(true)
    try {
      setSources(await getSources(selectedSubjectId))
      setSubjects(await getSubjects())
      setSourceError('')
    } catch (requestError) {
      setSourceError(getApiErrorMessage(requestError, 'Could not load your sources.'))
    } finally {
      setRefreshingSources(false)
    }
  }

  const sendFile = async (file) => {
    if (!file) return
    if (!selectedSubjectId) {
      setError('Create or select a subject before uploading material.')
      return
    }
    const extension = `.${file.name.split('.').pop().toLowerCase()}`
    if (!acceptedTypes.includes(extension)) {
      setError('Choose a PDF, PPTX, or MP4 file.')
      return
    }
    setBusy(true)
    setError('')
    setNotice('')
    try {
      const source = await uploadFile(file, selectedSubjectId)
      setNotice(`${source.file_name} added to your study library.`)
      setSources((current) => [source, ...current.filter((item) => item.id !== source.id)])
      setSubjects(await getSubjects())
    } catch (requestError) {
      setError(getApiErrorMessage(requestError, 'Upload failed. Please try again.'))
    } finally {
      setBusy(false)
      if (inputRef.current) inputRef.current.value = ''
    }
  }

  const submitYoutube = async (event) => {
    event.preventDefault()
    if (!youtubeUrl.trim()) return
    if (!selectedSubjectId) {
      setError('Create or select a subject before adding a video.')
      return
    }
    setBusy(true)
    setError('')
    setNotice('')
    try {
      const source = await uploadYoutube(youtubeUrl.trim(), selectedSubjectId)
      setSources((current) => [source, ...current.filter((item) => item.id !== source.id)])
      setSubjects(await getSubjects())
      setNotice('Video added. Its transcript will appear when processing finishes.')
      setYoutubeUrl('')
    } catch (requestError) {
      setError(getApiErrorMessage(requestError, 'Could not add this YouTube link.'))
    } finally {
      setBusy(false)
    }
  }

  const onDrop = (event) => {
    event.preventDefault()
    setDragging(false)
    sendFile(event.dataTransfer.files?.[0])
  }

  const removeSource = async (source) => {
    const confirmed = window.confirm(`Delete ${source.file_name}? This removes it from your knowledge base and can't be undone.`)
    if (!confirmed) return
    setDeletingSource(source.id)
    try {
      await deleteSource(source.id)
      setSources((current) => current.filter((item) => item.id !== source.id))
      setSubjects(await getSubjects())
      setToast(`${source.file_name} deleted.`)
      window.setTimeout(() => setToast(''), 3500)
    } catch (requestError) {
      setSourceError(getApiErrorMessage(requestError, 'Could not delete this source.'))
    } finally {
      setDeletingSource(null)
    }
  }

  const createNewSubject = async (event) => {
    event.preventDefault()
    if (!subjectName.trim()) return
    setSubjectBusy(true)
    try {
      const created = await createSubject({ name: subjectName.trim(), color: subjectColor })
      setSubjects((current) => [...current, created])
      setSelectedSubjectId(String(created.id))
      setSubjectName('')
      setShowSubjectForm(false)
      setSourceError('')
    } catch (requestError) {
      setSourceError(getApiErrorMessage(requestError, 'Could not create this subject.'))
    } finally {
      setSubjectBusy(false)
    }
  }

  const renameSubject = async (subject) => {
    const name = window.prompt('Rename subject', subject.name)?.trim()
    if (!name || name === subject.name) return
    try {
      const updated = await updateSubject(subject.id, { name })
      setSubjects((current) => current.map((item) => item.id === updated.id ? updated : item))
    } catch (requestError) {
      setSourceError(getApiErrorMessage(requestError, 'Could not rename this subject.'))
    }
  }

  const removeSubject = async (subject) => {
    const confirmed = window.confirm(`Delete "${subject.name}" and its ${subject.source_count} ${subject.source_count === 1 ? 'file' : 'files'}? This also removes its topics and stored material.`)
    if (!confirmed) return
    try {
      await deleteSubject(subject.id)
      const remaining = await getSubjects()
      setSubjects(remaining)
      if (String(subject.id) === selectedSubjectId) {
        setSources([])
        setSelectedSubjectId(remaining[0] ? String(remaining[0].id) : '')
      }
    } catch (requestError) {
      setSourceError(getApiErrorMessage(requestError, 'Could not delete this subject.'))
    }
  }

  const readySources = sources.filter((source) => source.status === 'ready')

  return (
    <div className="page-stack">
      <section className="page-heading page-heading-row">
        <div>
          <span className="eyebrow">YOUR STUDY LIBRARY</span>
          <h1>Bring your course material together.</h1>
          <p>StudyMate turns lectures and notes into a searchable learning space.</p>
        </div>
        <div className="heading-note"><span className="live-dot" /> Sources sync automatically</div>
      </section>

      <div className="upload-library-layout">
        <aside aria-label="Subjects" className="subject-sidebar">
          <div className="subject-sidebar-heading"><span className="section-kicker">FOLDERS</span><h2>Subjects</h2></div>
          <button className="button button-outline subject-new-button" onClick={() => setShowSubjectForm((visible) => !visible)} type="button"><FolderPlus size={15} /> New subject</button>
          {showSubjectForm && <form className="subject-create-form" onSubmit={createNewSubject}>
            <label htmlFor="new-subject-name">Subject name</label>
            <input autoFocus id="new-subject-name" maxLength={80} onChange={(event) => setSubjectName(event.target.value)} placeholder="OS, ML, DBMS" value={subjectName} />
            <span className="section-kicker">COLOR</span>
            <div aria-label="Subject color" className="subject-color-options" role="radiogroup">
              {subjectColors.map((color) => <button aria-label={`Select ${color} color`} aria-checked={subjectColor === color} className={subjectColor === color ? 'subject-color-swatch subject-color-selected' : 'subject-color-swatch'} key={color} onClick={() => setSubjectColor(color)} role="radio" style={{ backgroundColor: color }} type="button" />)}
            </div>
            <div className="subject-form-actions"><button className="button button-dark" disabled={subjectBusy || !subjectName.trim()} type="submit">Create</button><button className="button button-quiet" onClick={() => setShowSubjectForm(false)} type="button">Cancel</button></div>
          </form>}
          {subjectsLoading ? <LoadingStatus label="Loading subjects…" /> : subjects.length ? (
            <ul className="subject-folder-list">
              {subjects.map((subject) => <li className="subject-folder-item" key={subject.id}>
                <button aria-current={selectedSubjectId === String(subject.id) ? 'page' : undefined} className={selectedSubjectId === String(subject.id) ? 'subject-folder subject-folder-active' : 'subject-folder'} onClick={() => setSelectedSubjectId(String(subject.id))} type="button">
                  <i aria-hidden="true" style={{ backgroundColor: subject.color }} /><span>{subject.name}</span><small>{subject.source_count}</small>
                </button>
                <details className="subject-folder-menu"><summary aria-label={`Actions for ${subject.name}`}><MoreHorizontal size={17} /></summary><div><button onClick={() => renameSubject(subject)} type="button">Rename</button><button onClick={() => removeSubject(subject)} type="button">Delete</button></div></details>
              </li>)}
            </ul>
          ) : <p className="subject-empty-prompt">Create a subject folder to start organizing your material.</p>}
        </aside>

        <div className="upload-library-main">
      {readySources.length > 0 && <ActionHub sources={readySources} />}

      {!selectedSubjectId && !subjectsLoading ? <section className="empty-sources subject-required-prompt"><FolderPlus size={22} /><strong>Create a subject first</strong><span>Every upload belongs to a subject folder.</span><button className="button button-dark" onClick={() => setShowSubjectForm(true)} type="button">Create subject</button></section> : <div className="upload-layout">
        <section className="upload-workspace">
          <div className="section-title-row">
            <div>
              <span className="section-kicker">ADD MATERIAL</span>
              <h2>Start with a source</h2>
            </div>
            <span className="step-mark">01 / 02</span>
          </div>

          <button
            className={`drop-zone ${dragging ? 'drop-zone-active' : ''}`}
            disabled={busy || !selectedSubjectId}
            onClick={() => inputRef.current?.click()}
            onDragEnter={(event) => { event.preventDefault(); setDragging(true) }}
            onDragLeave={(event) => { event.preventDefault(); setDragging(false) }}
            onDragOver={(event) => event.preventDefault()}
            onDrop={onDrop}
            type="button"
          >
            <span className="drop-icon"><CloudUpload size={24} /></span>
            <span className="drop-title">{busy && <span aria-hidden="true" className="loading-ring loading-ring-small" />}{busy ? 'Adding your source…' : 'Drop a file here or browse'}</span>
            <span className="drop-subtitle">PDF, PowerPoint, or MP4 · one file at a time</span>
            <span className="drop-types">
              <span><FileText size={14} /> PDF</span>
              <span><Presentation size={14} /> PPTX</span>
              <span><Video size={14} /> MP4</span>
            </span>
          </button>
          <input
            accept=".pdf,.pptx,.mp4,application/pdf,application/vnd.openxmlformats-officedocument.presentationml.presentation,video/mp4"
            className="visually-hidden"
            onChange={(event) => sendFile(event.target.files?.[0])}
            ref={inputRef}
            type="file"
          />

          <div className="or-divider"><span>OR ADD A VIDEO LINK</span></div>
          <form className="youtube-form" onSubmit={submitYoutube}>
            <div className="youtube-input-wrap"><Link2 size={17} /><input aria-label="YouTube video URL" onChange={(event) => setYoutubeUrl(event.target.value)} placeholder="Paste a YouTube URL" type="url" value={youtubeUrl} /></div>
            <button className="button button-dark" disabled={busy || !selectedSubjectId || !youtubeUrl.trim()} type="submit">{busy ? <span aria-hidden="true" className="loading-ring loading-ring-button" /> : <ArrowDownToLine size={15} />}{busy ? 'Adding…' : 'Add video'}</button>
          </form>
          {error && <p className="inline-message message-error" role="alert">{error}</p>}
          {notice && <p className="inline-message message-success" role="status"><Check size={15} /> {notice}</p>}
        </section>

        <section aria-labelledby="sources-heading" className="source-list-section">
          <div className="section-title-row source-list-heading">
            <div>
              <span className="section-kicker">YOUR MATERIAL</span>
              <h2 id="sources-heading">Sources <span className="count-bubble">{sources.length}</span></h2>
            </div>
            <button aria-label="Refresh sources" aria-busy={refreshingSources} className="icon-button subtle-icon-button" disabled={refreshingSources} onClick={refreshSources} type="button">{refreshingSources ? <span aria-hidden="true" className="loading-ring loading-ring-small" /> : <RefreshCw size={16} />}</button>
          </div>

          {sourcesLoading ? <LoadingStatus className="sources-loading" label="Loading your sources…" /> : sourceError ? (
            <div className="empty-sources source-load-error"><strong>Could not load your sources</strong><span>{sourceError}</span><button className="button button-dark" onClick={refreshSources} type="button">Try again</button></div>
          ) : sources.length === 0 ? (
            <div className="empty-sources"><div className="empty-file-stack"><FileText size={21} /><Presentation size={19} /><Video size={18} /></div><strong>Your library is ready</strong><span>Sources you add will appear here with their processing status.</span></div>
          ) : (
            <ul className="source-list">
              {sources.map((source) => (
                <li className="source-row" key={source.id}>
                  <span className={`source-file-icon source-${source.source_type}`}><SourceIcon sourceType={source.source_type} /></span>
                  <span className="source-copy"><strong title={source.file_name}>{source.file_name}</strong><small>{source.source_type === 'slides' ? 'Slides' : source.source_type.toUpperCase()} · {new Date(source.created_at).toLocaleDateString()}</small>{source.error_message && <small className="source-error-message" role="alert">{source.error_message}</small>}</span>
                  <span className={`status-badge status-${source.status}`}><i />{statusLabel(source.status)}</span>
                  <button aria-label={`Delete ${source.file_name}`} className="icon-button source-delete-button" disabled={source.status === 'processing' || deletingSource === source.id} onClick={() => removeSource(source)} title={source.status === 'processing' ? 'Cannot delete while processing' : 'Delete source'} type="button">
                    {deletingSource === source.id ? <span aria-hidden="true" className="loading-ring loading-ring-small" /> : <Trash2 size={15} />}
                  </button>
                </li>
              ))}
            </ul>
          )}
          <div className="sync-footnote"><RefreshCw size={12} /> Updating every 3 seconds</div>
        </section>
      </div>}
        </div>
      </div>
      {toast && <div className="source-toast" role="status"><Check size={15} />{toast}</div>}
    </div>
  )
}
