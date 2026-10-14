import { useEffect, useState } from 'react'
import { ArrowRight, Brain, CircleCheck, CircleX, LoaderCircle, TriangleAlert } from 'lucide-react'
import { Link, useNavigate, useSearchParams } from 'react-router-dom'
import { API_BASE_URL, createEvaluationQuestion, getApiErrorMessage, submitEvaluationAnswer } from '../api'
import CitationChip from '../components/CitationChip'
import LoadingStatus from '../components/LoadingStatus'
import SubjectScopeSelector from '../components/SubjectScopeSelector'
import useSubjectScope from '../components/useSubjectScope'
import VideoModal from '../components/VideoModal'

function countWords(value) {
  return value.trim() ? value.trim().split(/\s+/).length : 0
}

export default function Evaluate() {
  const [searchParams] = useSearchParams()
  const navigate = useNavigate()
  const selectionKey = searchParams.toString()
  const params = new URLSearchParams(selectionKey)
  const scope = useSubjectScope({
    requestedSourceIds: params.getAll('source_ids').concat(params.get('source_id') ?? []).filter(Boolean),
    requestedTopicIds: [params.get('topic_id')].filter(Boolean),
    requestedTopics: params.getAll('topics'),
  })
  const { subjects, subjectId, selectSubject, sources, sourceId, selectSource, topics, selectedTopicIds, setSelectedTopicIds } = scope
  const selectedTopicId = selectedTopicIds[0] ?? ''
  const setSelectedTopicId = (value) => setSelectedTopicIds(value ? [String(value)] : [])
  const topicsError = scope.error
  const [evaluation, setEvaluation] = useState(null)
  const [loadedQuestionTopicId, setLoadedQuestionTopicId] = useState('')
  const [questionError, setQuestionError] = useState(null)
  const [answer, setAnswer] = useState('')
  const [result, setResult] = useState(null)
  const [answerError, setAnswerError] = useState('')
  const [submitting, setSubmitting] = useState(false)
  const [selectedCitation, setSelectedCitation] = useState(null)
  const [videoCitation, setVideoCitation] = useState(null)

  const topicsLoading = scope.loading
  const questionLoading = Boolean(selectedTopicId) && loadedQuestionTopicId !== selectedTopicId

  useEffect(() => {
    if (!selectedTopicId || topicsLoading) return undefined
    let active = true
    createEvaluationQuestion(Number(selectedTopicId))
      .then((generated) => {
        if (active) {
          setEvaluation({ ...generated, topicId: selectedTopicId })
          setLoadedQuestionTopicId(selectedTopicId)
          setQuestionError(null)
          setAnswer('')
          setResult(null)
          setAnswerError('')
        }
      })
      .catch((requestError) => {
        if (active) {
          setEvaluation(null)
          setLoadedQuestionTopicId(selectedTopicId)
          setQuestionError({ topicId: selectedTopicId, message: getApiErrorMessage(requestError, 'Could not create an evaluation question.') })
        }
      })
    return () => { active = false }
  }, [selectedTopicId, topicsLoading])

  const selectedTopic = topics.find((topic) => String(topic.id) === selectedTopicId)
  const currentEvaluation = evaluation?.topicId === selectedTopicId ? evaluation : null
  const currentResult = result?.topicId === selectedTopicId ? result : null
  const currentQuestionError = questionError?.topicId === selectedTopicId ? questionError.message : ''
  const words = countWords(answer)

  const citationClicked = (citation) => {
    if (citation.source_type === 'video') setVideoCitation(citation)
    else setSelectedCitation(citation)
  }

  const videoUrl = videoCitation
    ? /^https?:\/\//i.test(videoCitation.file_name)
      ? videoCitation.file_name
      : `${API_BASE_URL}/sources/${videoCitation.source_id}/video`
    : ''

  const submitAnswer = async (event) => {
    event.preventDefault()
    if (!currentEvaluation || submitting) return
    if (words < 20) {
      setAnswerError('Please write at least 20 words so I can evaluate your explanation.')
      return
    }
    setSubmitting(true)
    setAnswerError('')
    try {
      const grade = await submitEvaluationAnswer(currentEvaluation.evaluation_id, answer)
      setResult({ ...grade, topicId: selectedTopicId })
    } catch (requestError) {
      setAnswerError(getApiErrorMessage(requestError, 'Could not evaluate this answer. Please try again.'))
    } finally {
      setSubmitting(false)
    }
  }

  const learnMissedParts = () => {
    if (!selectedTopic) return
    const params = new URLSearchParams()
    params.append('source_ids', String(selectedTopic.source_id))
    params.append('topics', selectedTopic.name)
    navigate(`/explain?${params.toString()}`)
  }

  return (
    <div className="evaluation-page">
      <aside aria-label="Evaluation topics" className="evaluation-sidebar">
        <span className="eyebrow">FEYNMAN TECHNIQUE</span>
        <h1>Explain what you know.</h1>
        <p>Choose a topic and teach it back in your own words.</p>
        <SubjectScopeSelector
          onSelectedTopicIdsChange={setSelectedTopicIds}
          onSubjectChange={selectSubject}
          onSourceChange={selectSource}
          selectedTopicIds={selectedTopicIds}
          subjectId={subjectId}
          subjects={subjects}
          sources={sources}
          sourceId={sourceId}
          topicMode="single"
          topics={topics}
        />
        {topicsLoading ? <LoadingStatus className="evaluation-topic-loading" label="Loading topics…" /> : topicsError ? (
          <div className="evaluation-topics-empty"><strong>Topics unavailable</strong><span>{topicsError}</span></div>
        ) : topics.length ? (
          <ul className="evaluation-topic-list">
            {topics.map((topic) => <li key={topic.id}><button aria-current={selectedTopicId === String(topic.id) ? 'true' : undefined} className={`evaluation-topic-button${selectedTopicId === String(topic.id) ? ' evaluation-topic-active' : ''}`} onClick={() => setSelectedTopicId(String(topic.id))} type="button"><strong>{topic.name}</strong><span>{topic.summary}</span></button></li>)}
          </ul>
        ) : (
          <div className="evaluation-topics-empty"><Brain size={20} /><strong>No topics found</strong><span>Upload course material to create an evaluation.</span><Link to="/upload">Go to your library <ArrowRight size={13} /></Link></div>
        )}
      </aside>

      <main aria-live="polite" className="evaluation-workspace">
        <header className="evaluation-header"><div><span className="section-kicker">CONCEPT EVALUATION</span><h2>{selectedTopic?.name ?? 'Your explanation'}</h2></div><span className="evaluation-method"><Brain size={15} /> Teach it back</span></header>
        {topicsLoading ? <LoadingStatus className="evaluation-empty" label="Preparing your evaluation…" /> : currentQuestionError ? (
          <div className="evaluation-empty evaluation-error" role="alert"><TriangleAlert size={22} /><strong>Question unavailable</strong><p>{currentQuestionError}</p></div>
        ) : questionLoading ? (
          <LoadingStatus className="evaluation-empty" label="Creating your question…" />
        ) : currentResult ? (
          <section className="evaluation-results">
            <div className="evaluation-score-row">
              <div aria-label={`Total score ${currentResult.total_score} out of 10`} className="evaluation-score-ring" style={{ '--score-angle': `${currentResult.total_score * 36}deg` }}><span><strong>{currentResult.total_score}</strong><small>/ 10</small></span></div>
              <div className="evaluation-score-copy"><span className="section-kicker">YOUR UNDERSTANDING</span><h3>{currentResult.feedback}</h3><div className="evaluation-dimensions"><span>Coverage <b>{currentResult.coverage}/10</b></span><span>Accuracy <b>{currentResult.accuracy}/10</b></span><span>Clarity <b>{currentResult.clarity}/10</b></span></div></div>
            </div>

            <section className="evaluation-ideas"><h3>Key ideas</h3><ul>{currentResult.key_ideas.map((item, index) => <li className={item.covered ? 'evaluation-idea-covered' : 'evaluation-idea-missed'} key={`${index}-${item.idea}`}><span className="evaluation-idea-icon">{item.covered ? <CircleCheck size={19} /> : <CircleX size={19} />}</span><span className="evaluation-idea-copy"><strong>{item.idea}</strong><small>{item.covered ? 'Covered in your explanation' : 'Worth another look'}</small></span><CitationChip citation={item.citation} onClick={() => citationClicked(item.citation)} /></li>)}</ul></section>

            {currentResult.misconceptions.length > 0 && <section className="evaluation-misconceptions"><h3><TriangleAlert size={17} /> Let’s correct a couple of things</h3><div className="evaluation-misconception-list">{currentResult.misconceptions.map((item, index) => <article className="evaluation-misconception-card" key={`${index}-${item.claim}`}><p><strong>You wrote</strong>{item.claim}</p><p><strong>A clearer version</strong>{item.correction}</p><CitationChip citation={item.citation} onClick={() => citationClicked(item.citation)} /></article>)}</div></section>}

            <button className="button button-dark evaluation-learn-button" onClick={learnMissedParts} type="button">Learn the missed parts <ArrowRight size={15} /></button>
          </section>
        ) : currentEvaluation ? (
          <form className="evaluation-answer-form" onSubmit={submitAnswer}>
            <div className="evaluation-question"><span className="section-kicker">EXPLAIN IN YOUR OWN WORDS</span><h3>{currentEvaluation.question}</h3></div>
            <label className="evaluation-answer-label" htmlFor="evaluation-answer">Your explanation</label>
            <textarea id="evaluation-answer" onChange={(event) => { setAnswer(event.target.value); setAnswerError('') }} placeholder="Explain the idea as if you were teaching it to a friend…" value={answer} />
            <div className="evaluation-answer-footer"><span className={words < 20 ? 'evaluation-word-count evaluation-word-count-short' : 'evaluation-word-count'}>{words} words <small>{words < 20 ? `· ${20 - words} more to go` : '· ready to submit'}</small></span><button className="button button-dark" disabled={submitting || words === 0} type="submit">{submitting ? <><LoaderCircle className="animate-spin" size={15} /> Checking…</> : <>Check my understanding <ArrowRight size={15} /></>}</button></div>
            {answerError && <p className="evaluation-form-error" role="alert">{answerError}</p>}
          </form>
        ) : (
          <div className="evaluation-empty"><Brain size={23} /><strong>Select a topic to begin</strong><p>Your question will be based on the selected topic’s source material.</p></div>
        )}
      </main>
      {selectedCitation && <div className="modal-backdrop" onMouseDown={(event) => event.target === event.currentTarget && setSelectedCitation(null)}><section aria-labelledby="evaluation-citation-title" aria-modal="true" className="citation-modal" role="dialog"><button aria-label="Close citation" className="modal-close-text" onClick={() => setSelectedCitation(null)} type="button">Close</button><span className="eyebrow">SOURCE PASSAGE</span><h2 id="evaluation-citation-title">{selectedCitation.file_name}</h2><p className="citation-location">{selectedCitation.source_type === 'slides' ? 'Slide' : 'Page'} {selectedCitation.slide ?? selectedCitation.page}</p><blockquote>{selectedCitation.snippet}</blockquote></section></div>}
      {videoCitation && <VideoModal citation={videoCitation} onClose={() => setVideoCitation(null)} url={videoUrl} />}
    </div>
  )
}