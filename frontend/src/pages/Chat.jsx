import { useEffect, useRef, useState } from 'react'
import { ArrowUp, BookOpen, RotateCcw, Sparkles } from 'lucide-react'
import { useSearchParams } from 'react-router-dom'
import { API_BASE_URL, askQuestion, getApiErrorMessage } from '../api'
import CitationChip from '../components/CitationChip'
import HighlightedText from '../components/HighlightedText'
import LoadingStatus from '../components/LoadingStatus'
import SubjectScopeSelector from '../components/SubjectScopeSelector'
import useSubjectScope from '../components/useSubjectScope'
import VideoModal from '../components/VideoModal'

const styles = [
  { value: 'simple', label: 'Simple' },
  { value: 'detailed', label: 'Detailed' },
  { value: 'example-based', label: 'Example-based' },
  { value: 'hinglish', label: 'Hinglish' },
]

export default function Chat() {
  const [searchParams] = useSearchParams()
  const params = new URLSearchParams(searchParams.toString())
  const scope = useSubjectScope({
    requestedSourceIds: params.getAll('source_ids').concat(params.get('source_id') ?? []).filter(Boolean),
    requestedTopicIds: [params.get('topic_id')].filter(Boolean),
    requestedTopics: params.getAll('topics'),
  })
  const { subjects, subjectId, selectSubject, sources, sourceId, selectSource, sourceIds, topics, selectedTopicIds, setSelectedTopicIds } = scope
  const selectedTopics = topics.filter((topic) => selectedTopicIds.includes(String(topic.id))).map((topic) => topic.name)
  const [messages, setMessages] = useState([
    { id: 'welcome', role: 'assistant', content: 'Hi! Ask me about your uploaded notes or lectures. I’ll keep the answer grounded in your material and point you to the source.', citations: [] },
  ])
  const [question, setQuestion] = useState('')
  const [style, setStyle] = useState('simple')
  const [busy, setBusy] = useState(false)
  const [videoCitation, setVideoCitation] = useState(null)
  const [selectedCitation, setSelectedCitation] = useState(null)
  const bottomRef = useRef(null)

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: 'smooth', block: 'end' })
  }, [messages])

  const sendQuestion = async (event) => {
    event.preventDefault()
    const prompt = question.trim()
    if (!prompt || busy || scope.loading || !subjectId) return
    const userMessage = { id: crypto.randomUUID(), role: 'user', content: prompt, citations: [] }
    setMessages((current) => [...current, userMessage])
    setQuestion('')
    setBusy(true)
    try {
      const response = await askQuestion(prompt, style, {
        sourceIds: sourceIds,
        topics: selectedTopics,
        subjectId: Number(subjectId) || undefined,
      })
      setMessages((current) => [...current, {
        id: crypto.randomUUID(),
        role: 'assistant',
        content: response.answer,
        citations: response.citations ?? [],
      }])
    } catch (error) {
      setMessages((current) => [...current, {
        id: crypto.randomUUID(),
        role: 'assistant',
        content: getApiErrorMessage(error, 'I could not get an answer. Please try again.'),
        citations: [],
        isError: true,
      }])
    } finally {
      setBusy(false)
    }
  }

  const citationClicked = (citation) => {
    if (citation.source_type === 'video') setVideoCitation(citation)
    else setSelectedCitation(citation)
  }

  const videoUrl = videoCitation
    ? /^https?:\/\//i.test(videoCitation.file_name)
      ? videoCitation.file_name
      : `${API_BASE_URL}/sources/${videoCitation.source_id}/video`
    : ''

  return (
    <div className="chat-page">
      <header className="chat-heading">
        <div><span className="eyebrow">YOUR COURSE COMPANION</span><h1>Ask your material.</h1><p>Answers are grounded in your sources, with a trail back to the exact passage.</p></div>
        <label className="style-select-label"><span>EXPLANATION STYLE</span><select aria-label="Explanation style" onChange={(event) => setStyle(event.target.value)} value={style}>{styles.map((item) => <option key={item.value} value={item.value}>{item.label}</option>)}</select></label>
      </header>

      <SubjectScopeSelector
        onSelectedTopicIdsChange={setSelectedTopicIds}
        onSubjectChange={selectSubject}
        onSourceChange={selectSource}
        selectedTopicIds={selectedTopicIds}
        subjectId={subjectId}
        subjects={subjects}
        sources={sources}
        sourceId={sourceId}
        topics={topics}
      />
      {scope.error && <p className="inline-message message-error" role="alert">{scope.error}</p>}

      <section aria-label="Chat conversation" className="chat-panel">
        <div className="chat-toolbar"><span><span className="live-dot" /> StudyMate tutor</span><span className="grounded-label"><BookOpen size={14} /> Source-grounded</span></div>
        <div className="chat-thread" aria-live="polite">
          {messages.map((message) => (
            <article className={`message-row message-${message.role}`} key={message.id}>
              {message.role === 'assistant' && <span className="assistant-mark"><Sparkles size={15} /></span>}
              <div className={`message-content ${message.isError ? 'message-content-error' : ''}`}>
                {message.role === 'assistant' && <span className="message-author">STUDYMATE</span>}
                {message.role === 'assistant' ? <HighlightedText glossary={message.glossary ?? []} text={message.content} /> : <p>{message.content}</p>}
                {message.citations?.length > 0 && <div className="citation-list">{message.citations.map((citation) => <CitationChip citation={citation} key={`${message.id}-${citation.n}`} onClick={() => citationClicked(citation)} />)}</div>}
              </div>
            </article>
          ))}
          {busy && <div className="message-row message-assistant"><span className="assistant-mark"><Sparkles size={15} /></span><div className="message-content"><span className="message-author">STUDYMATE</span><LoadingStatus className="chat-loading" label="Thinking through your material…" /></div></div>}
          <div ref={bottomRef} />
        </div>
        <form className="chat-compose" onSubmit={sendQuestion}>
          <textarea aria-label="Your question" onChange={(event) => setQuestion(event.target.value)} onKeyDown={(event) => { if (event.key === 'Enter' && !event.shiftKey) { event.preventDefault(); sendQuestion(event) } }} placeholder="Ask about a concept, a lecture, or a page…" rows={1} value={question} />
          <div className="compose-footer"><span><RotateCcw size={13} /> Answers stay within your uploaded sources</span><button aria-label="Send question" className="send-button" disabled={!question.trim() || busy || scope.loading || !subjectId} type="submit"><ArrowUp size={18} /></button></div>
        </form>
      </section>

      {selectedCitation && <div className="modal-backdrop" onMouseDown={(event) => event.target === event.currentTarget && setSelectedCitation(null)}><section aria-labelledby="citation-modal-title" aria-modal="true" className="citation-modal" role="dialog"><button aria-label="Close citation" className="modal-close-text" onClick={() => setSelectedCitation(null)} type="button">Close</button><span className="eyebrow">SOURCE PASSAGE</span><h2 id="citation-modal-title">{selectedCitation.file_name}</h2><p className="citation-location">{selectedCitation.source_type === 'slides' ? 'Slide' : 'Page'} {selectedCitation.slide ?? selectedCitation.page}</p><blockquote>{selectedCitation.snippet}</blockquote></section></div>}
      {videoCitation && <VideoModal citation={videoCitation} onClose={() => setVideoCitation(null)} url={videoUrl} />}
    </div>
  )
}
