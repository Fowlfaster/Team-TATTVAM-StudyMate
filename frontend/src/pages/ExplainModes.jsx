import { useEffect, useState } from 'react'
import { ArrowRight, BookOpenCheck, RefreshCw, Sparkles, TriangleAlert } from 'lucide-react'
import { useNavigate, useSearchParams } from 'react-router-dom'
import { API_BASE_URL, explainKeyTopics, explainSimply, getApiErrorMessage, retryKeyTopic } from '../api'
import CitationChip from '../components/CitationChip'
import HighlightedText from '../components/HighlightedText'
import LoadingStatus from '../components/LoadingStatus'
import SubjectScopeSelector from '../components/SubjectScopeSelector'
import VideoModal from '../components/VideoModal'
import useSubjectScope from '../components/useSubjectScope'

export default function ExplainModes() {
  const [searchParams] = useSearchParams()
  const navigate = useNavigate()
  const params = new URLSearchParams(searchParams.toString())
  const scope = useSubjectScope({
    requestedSourceIds: params.getAll('source_ids').concat(params.get('source_id') ?? []).filter(Boolean),
    requestedTopicIds: [params.get('topic_id')].filter(Boolean),
    requestedTopics: params.getAll('topics'),
  })
  const { subjects, subjectId, selectSubject, sources, sourceId, selectSource, topics, selectedTopicIds, setSelectedTopicIds } = scope
  const [mode, setMode] = useState('')
  const [result, setResult] = useState(null)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState('')
  const [progressIndex, setProgressIndex] = useState(0)
  const [selectedCitation, setSelectedCitation] = useState(null)
  const [videoCitation, setVideoCitation] = useState(null)
  const [retryingTopicId, setRetryingTopicId] = useState(null)
  const topicIds = selectedTopicIds.map(Number).filter(Number.isInteger)
  const citationClicked = (citation) => {
    if (citation.source_type === 'video') setVideoCitation(citation)
    else setSelectedCitation(citation)
  }
  const videoUrl = videoCitation
    ? /^https?:\/\//i.test(videoCitation.file_name)
      ? videoCitation.file_name
      : `${API_BASE_URL}/sources/${videoCitation.source_id}/video`
    : ''

  useEffect(() => {
    if (!loading) return undefined
    const interval = window.setInterval(() => setProgressIndex((value) => value + 1), 1800)
    return () => window.clearInterval(interval)
  }, [loading])

  const runMode = async (nextMode, regenerate = false) => {
    if (!subjectId) return
    setMode(nextMode)
    setLoading(true)
    setError('')
    setResult(null)
    setProgressIndex(0)
    try {
      const generated = nextMode === 'simple'
        ? await explainSimply(Number(subjectId), sourceId || null, topicIds, regenerate)
        : await explainKeyTopics(Number(subjectId), sourceId || null, topicIds, 5, regenerate)
      setResult(generated)
    } catch (requestError) {
      setError(getApiErrorMessage(requestError, 'Could not generate this explanation.'))
    } finally {
      setLoading(false)
    }
  }

  const retryTopic = async (topic) => {
    setRetryingTopicId(topic.topic_id)
    try {
      const generated = await retryKeyTopic(topic, Number(subjectId), sourceId || null, topicIds, 5)
      setResult((current) => current ? {
        ...current,
        topics: current.topics.map((item) => item.topic_id === generated.topic_id ? generated : item),
      } : current)
    } catch (requestError) {
      setResult((current) => current ? {
        ...current,
        topics: current.topics.map((item) => item.topic_id === topic.topic_id
          ? { ...item, generation_failed: true, generation_error: getApiErrorMessage(requestError, 'Retry failed.') }
          : item),
      } : current)
    } finally {
      setRetryingTopicId(null)
    }
  }

  const progressLabel = mode === 'key-topics' && progressIndex > 1
    ? `Explaining topic ${Math.min(progressIndex - 1, 5)} of 5…`
    : mode === 'simple' && progressIndex > 1
      ? 'Connecting the ideas…'
      : 'Reading your material…'

  const openRelatedActivity = (path, topic) => {
    const query = new URLSearchParams({ source_id: String(topic.source_id), topic_id: String(topic.topic_id), subject_id: subjectId })
    navigate(`${path}?${query.toString()}`)
  }

  return (
    <div className="page-stack explain-modes-page">
      <header className="page-heading page-heading-row">
        <div><span className="eyebrow">GROUNDED IN YOUR MATERIAL</span><h1>Make the material click.</h1><p>Choose a subject, narrow the source or topics, then pick a way to learn.</p></div>
        <span className="heading-note"><Sparkles size={15} /> Source-backed explanations</span>
      </header>

      <SubjectScopeSelector
        onSelectedTopicIdsChange={setSelectedTopicIds}
        onSubjectChange={(value) => { selectSubject(value); setMode(''); setResult(null) }}
        onSourceChange={(value) => { selectSource(value); setMode(''); setResult(null) }}
        selectedTopicIds={selectedTopicIds}
        subjectId={subjectId}
        subjects={subjects}
        sources={sources}
        sourceId={sourceId}
        topics={topics}
      />
      {scope.error && <p className="inline-message message-error" role="alert">{scope.error}</p>}

      {scope.loading ? <LoadingStatus className="explain-content-loading" label="Loading your subjects and material…" /> : !subjectId ? (
        <div className="explain-state"><BookOpenCheck size={22} /><strong>Create a subject first</strong><p>Add or select a subject in your study library to begin.</p><button className="button button-dark" onClick={() => navigate('/upload')} type="button">Open study library <ArrowRight size={15} /></button></div>
      ) : (
        <>
          <section aria-label="Explanation mode" className="explain-mode-choices">
            <button aria-pressed={mode === 'simple'} className={mode === 'simple' ? 'explain-mode-choice explain-mode-choice-active' : 'explain-mode-choice'} onClick={() => runMode('simple')} type="button">
              <span className="explain-choice-mark">A</span><span><strong>Understand it simply</strong><small>A connected, beginner-friendly story for the selected material.</small></span><ArrowRight size={17} />
            </button>
            <button aria-pressed={mode === 'key-topics'} className={mode === 'key-topics' ? 'explain-mode-choice explain-mode-choice-active' : 'explain-mode-choice'} onClick={() => runMode('key-topics')} type="button">
              <span className="explain-choice-mark">B</span><span><strong>Key topics in detail</strong><small>Prioritized topics with examples, exam tips, and practice.</small></span><ArrowRight size={17} />
            </button>
          </section>

          {loading && <LoadingStatus className="explain-content-loading" label={progressLabel} />}
          {error && <div className="explain-state explain-error" role="alert"><TriangleAlert size={20} /><strong>Explanation unavailable</strong><p>{error}</p></div>}
          {result && !loading && <section className="explain-result-section">
            <header className="explain-result-heading"><div><span className="section-kicker">{mode === 'simple' ? 'THE BIG PICTURE' : 'PRIORITIZED STUDY GUIDE'}</span><h2>{result.title}</h2></div><button className="button button-outline" disabled={loading} onClick={() => runMode(mode, true)} type="button"><RefreshCw size={14} /> Regenerate</button></header>
            {mode === 'simple' ? <article className="simple-explanation-content">
              <HighlightedText className="simple-big-picture" highlights text={result.big_picture} />
              <section className="simple-story-sections"><h3>How the ideas unfold</h3>{(result.story_sections ?? []).map((section, index) => <article className="simple-story-section" key={`${section.topic}-${index}`}><span className="section-kicker">{String(index + 1).padStart(2, '0')}</span><div><h4>{section.topic}</h4><HighlightedText highlights text={section.simple_explanation} /><p className="everyday-analogy"><strong>Everyday analogy</strong><HighlightedText highlights text={section.everyday_analogy} /></p></div></article>)}</section>
              <section className="simple-connection"><span className="section-kicker">HOW IT CONNECTS</span><HighlightedText highlights text={result.how_topics_connect} /></section>
              <section className="simple-remember"><h3>Five things to remember</h3><ol>{result.five_things_to_remember.map((item, index) => <li key={`${index}-${item}`}><HighlightedText highlights text={item} /></li>)}</ol></section>
              {(result.glossary ?? []).length > 0 && <section className="simple-glossary"><h3>Plain-language glossary</h3><dl>{result.glossary.map((item) => <div key={item.term}><dt><HighlightedText highlights text={item.term} /></dt><dd><HighlightedText highlights text={item.simple_definition} /></dd></div>)}</dl></section>}
              <div className="citation-list">{(result.citations ?? []).map((citation, index) => <CitationChip citation={citation} key={`${citation.source_id}-${citation.n}-${index}`} onClick={() => citationClicked(citation)} />)}</div>
            </article> : <div className="key-topic-list">{result.topics.map((topic) => <details className="key-topic-card" key={`${topic.topic_id}-${topic.source_id}`}>
              <summary><span><small>{topic.generation_failed ? "COULDN'T GENERATE" : 'KEY TOPIC'}</small><strong>{topic.topic}</strong><em><HighlightedText highlights text={topic.why_it_matters} /></em></span><ArrowRight size={17} /></summary>
              <div className="key-topic-content">
                {topic.generation_failed ? <div className="key-topic-generation-error" role="alert"><p>{topic.generation_error || 'This topic could not be generated.'}</p><button className="button button-outline" disabled={retryingTopicId === topic.topic_id} onClick={() => retryTopic(topic)} type="button">{retryingTopicId === topic.topic_id ? 'Retrying…' : "Couldn't generate - Retry"}</button></div> : <>
                <HighlightedText highlights text={topic.detailed_explanation} />
                {(topic.step_by_step ?? []).length > 0 && <section><h3>Step by step</h3><ol>{topic.step_by_step.map((step, index) => <li key={`${index}-${step}`}><HighlightedText highlights text={step} /></li>)}</ol></section>}
                {topic.example && <section><h3>Example</h3><HighlightedText highlights text={topic.example} /></section>}
                {topic.diagram_description && <section><h3>Diagram description</h3><HighlightedText highlights text={topic.diagram_description} /></section>}
                {(topic.common_mistakes ?? []).length > 0 && <section><h3>Common mistakes</h3><ul>{topic.common_mistakes.map((item) => <li key={item}><HighlightedText highlights text={item} /></li>)}</ul></section>}
                {(topic.exam_tips ?? []).length > 0 && <section><h3>Exam tips</h3><ul>{topic.exam_tips.map((item) => <li key={item}><HighlightedText highlights text={item} /></li>)}</ul></section>}
                <section className="key-topic-practice"><h3>Practice question</h3><HighlightedText highlights text={topic.practice_question} /></section>
                <div className="citation-list">{topic.citations.map((citation, index) => <CitationChip citation={citation} key={`${citation.source_id}-${citation.n}-${index}`} onClick={() => citationClicked(citation)} />)}</div>
                <div className="analysis-section-actions"><button className="button button-dark" onClick={() => openRelatedActivity('/quiz', topic)} type="button">Take quiz on this</button><button className="button button-outline" onClick={() => openRelatedActivity('/evaluate', topic)} type="button">Evaluate my understanding</button></div>
                </>}
              </div>
            </details>)}</div>}
          </section>}
        </>
      )}
      {selectedCitation && <div className="modal-backdrop" onMouseDown={(event) => event.target === event.currentTarget && setSelectedCitation(null)}><section aria-modal="true" className="citation-modal" role="dialog"><button className="modal-close-text" onClick={() => setSelectedCitation(null)} type="button">Close</button><span className="eyebrow">SOURCE PASSAGE</span><h2>{selectedCitation.file_name}</h2><p className="citation-location">{selectedCitation.source_type === 'slides' ? 'Slide' : 'Page'} {selectedCitation.slide ?? selectedCitation.page}</p><blockquote><HighlightedText highlights text={selectedCitation.snippet} /></blockquote></section></div>}
      {videoCitation && <VideoModal citation={videoCitation} onClose={() => setVideoCitation(null)} url={videoUrl} />}
    </div>
  )
}
