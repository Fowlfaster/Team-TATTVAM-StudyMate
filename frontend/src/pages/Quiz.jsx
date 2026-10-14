import { useMemo, useState } from 'react'
import { ArrowRight, Check, CircleHelp, RotateCw, X } from 'lucide-react'
import { Link, useSearchParams } from 'react-router-dom'
import { getApiErrorMessage, getNextQuiz, startQuizSession, submitQuizAnswer } from '../api'
import CitationChip from '../components/CitationChip'
import HighlightedText from '../components/HighlightedText'
import LoadingStatus from '../components/LoadingStatus'
import SubjectScopeSelector from '../components/SubjectScopeSelector'
import useSubjectScope from '../components/useSubjectScope'
import VideoModal from '../components/VideoModal'
import { API_BASE_URL } from '../api'

const optionLetters = ['A', 'B', 'C', 'D']

export default function Quiz() {
  const [searchParams] = useSearchParams()
  const selectionKey = searchParams.toString()
  const initialParams = new URLSearchParams(selectionKey)
  const scope = useSubjectScope({
    requestedSourceIds: initialParams.getAll('source_ids').concat(initialParams.get('source_id') ?? []).filter(Boolean),
    requestedTopicIds: [initialParams.get('topic_id')].filter(Boolean),
    requestedTopics: initialParams.getAll('topics'),
  })
  const subjects = Array.isArray(scope?.subjects) ? scope.subjects : []
  const subjectId = scope?.subjectId ?? ''
  const selectSubject = scope?.selectSubject
  const sources = Array.isArray(scope?.sources) ? scope.sources : []
  const sourceId = scope?.sourceId ?? ''
  const selectSource = scope?.selectSource
  const sourceIds = Array.isArray(scope?.sourceIds) ? scope.sourceIds : []
  const topics = Array.isArray(scope?.topics) ? scope.topics : []
  const selectedTopicIds = Array.isArray(scope?.selectedTopicIds) ? scope.selectedTopicIds : []
  const setSelectedTopicIds = scope?.setSelectedTopicIds
  const sourceError = scope?.error ?? ''
  const evaluationMode = searchParams.get('mode') === 'evaluation'
  const [quiz, setQuiz] = useState(null)
  const [result, setResult] = useState(null)
  const [loading, setLoading] = useState(false)
  const [answering, setAnswering] = useState(false)
  const [error, setError] = useState('')
  const [videoCitation, setVideoCitation] = useState(null)
  const [session, setSession] = useState(null)
  const [numQuestions, setNumQuestions] = useState(5)

  const sourceLoading = scope.loading
  const topicsLoading = sourceLoading
  const sessionTopicId = selectedTopicIds.length === 1 ? Number(selectedTopicIds[0]) : undefined
  const selectedTopics = useMemo(
    () => topics.filter((topic) => selectedTopicIds.includes(String(topic.id))).map((topic) => topic.name),
    [topics, selectedTopicIds],
  )

  const loadQuestion = async (sessionId = session?.id) => {
    if (!sessionId) return
    setLoading(true)
    setError('')
    try {
      const nextQuestion = await getNextQuiz({
        sourceIds,
        topics: selectedTopics,
        sourceId: sourceId ? Number(sourceId) : undefined,
        topicId: sessionTopicId,
        sessionId,
        subjectId: Number(subjectId),
      })
      setQuiz(nextQuestion)
      setResult(null)
    } catch (requestError) {
      setQuiz(null)
      setError(getApiErrorMessage(requestError, 'Could not load a quiz question.'))
    } finally {
      setLoading(false)
    }
  }

  const startQuiz = async () => {
    if (!subjectId || !sourceIds.length || loading) return
    setLoading(true)
    setError('')
    setQuiz(null)
    setResult(null)
    try {
      const created = await startQuizSession({
        subjectId: Number(subjectId),
        sourceIds,
        topicIds: selectedTopicIds.map(Number).filter(Number.isInteger),
        numQuestions,
      })
      const activeSession = { id: created.session_id, total: created.num_questions }
      setSession(activeSession)
      await loadQuestion(activeSession.id)
    } catch (requestError) {
      setSession(null)
      setError(getApiErrorMessage(requestError, 'Could not start this quiz.'))
      setLoading(false)
    }
  }

  const changeSubject = (value) => {
    selectSubject(value)
    setSession(null)
    setQuiz(null)
    setResult(null)
  }

  const changeSource = (value) => {
    selectSource(value)
    setSession(null)
    setQuiz(null)
    setResult(null)
  }

  const changeTopics = (values) => {
    setSelectedTopicIds(values)
    setSession(null)
    setQuiz(null)
    setResult(null)
  }

  const chooseAnswer = async (selectedIndex) => {
    if (!quiz || result || answering) return
    setAnswering(true)
    setError('')
    try {
      const answer = await submitQuizAnswer(quiz.question_id, selectedIndex)
      setResult({ ...answer, selectedIndex })
    } catch (requestError) {
      setError(getApiErrorMessage(requestError, 'Could not submit your answer.'))
    } finally {
      setAnswering(false)
    }
  }

  const restartSession = () => {
    setSession(null)
    setQuiz(null)
    setResult(null)
    startQuiz()
  }

  const videoUrl = videoCitation
    ? /^https?:\/\//i.test(videoCitation.file_name)
      ? videoCitation.file_name
      : `${API_BASE_URL}/sources/${videoCitation.source_id}/video`
    : ''
  const selectedTopicName = topics.find((topic) => String(topic.id) === (selectedTopicIds[0] ?? ''))?.name ?? (quiz?.topic ?? 'Topic')

  return (
    <div className="quiz-page">
      <header className="page-heading quiz-heading"><div><span className="eyebrow">{evaluationMode ? 'CONCEPT EVALUATION' : 'PRACTICE THAT ADAPTS'}</span><h1>{evaluationMode ? 'Check your understanding, concept by concept.' : `Quiz: ${selectedTopicName}`}</h1><p>{evaluationMode ? 'Work through concepts from the sources you selected.' : 'Your next question follows your progress, not a fixed worksheet.'}</p></div><span className="quiz-spark"><CircleHelp size={25} /></span></header>

      {!sourceLoading && <SubjectScopeSelector
        onSelectedTopicIdsChange={changeTopics}
        onSubjectChange={changeSubject}
        onSourceChange={changeSource}
        selectedTopicIds={selectedTopicIds}
        subjectId={subjectId}
        subjects={subjects}
        sources={sources}
        sourceId={sourceId}
        topics={topics}
      />}
      {sourceError && <p className="inline-message message-error" role="alert">{sourceError}</p>}
      {!sourceLoading && subjectId && <label className="style-select-label quiz-question-count"><span>NUMBER OF QUESTIONS</span><select aria-label="Number of questions" onChange={(event) => setNumQuestions(Number(event.target.value))} value={numQuestions}><option value={5}>5 questions</option><option value={10}>10 questions</option><option value={15}>15 questions</option></select></label>}

      <section aria-live="polite" className="quiz-stage">
        {sourceLoading ? <LoadingStatus className="quiz-loading" label="Loading your subjects…" />
          : sourceError ? <div className="quiz-empty"><h2>Could not load study material</h2><p>{sourceError}</p></div>
            : !subjectId ? <div className="quiz-empty"><h2>Create a subject first</h2><p>Select a subject folder to find your study material.</p><Link className="button button-dark" to="/upload">Open study library <ArrowRight size={15} /></Link></div>
              : sourceIds.length === 0 ? <div className="quiz-empty"><span className="quiz-empty-icon"><CircleHelp size={24} /></span><h2>Upload material first</h2><p>This subject has no ready sources yet.</p><Link className="button button-dark" to="/upload">Go to your library <ArrowRight size={15} /></Link></div>
                : topics.length === 0 ? <div className="quiz-empty"><h2>No topics found</h2><p>Ready sources in this subject do not have topics yet.</p></div>
                  : !session ? <div className="quiz-empty"><span className="quiz-empty-icon"><CircleHelp size={24} /></span><h2>Ready when you are</h2><p>{sourceIds.length} source{sourceIds.length === 1 ? '' : 's'} · {selectedTopicIds.length ? `${selectedTopicIds.length} topic${selectedTopicIds.length === 1 ? '' : 's'} selected` : 'all topics'}</p>{error && <p className="message-error" role="alert">{error}</p>}<button className="button button-dark" disabled={loading} onClick={startQuiz} type="button">{loading ? 'Starting…' : 'Start quiz'}</button></div>
                    : loading ? <LoadingStatus className="quiz-loading" label="Finding the right question for you…" />
                      : error && !quiz ? <div className="quiz-empty"><span className="quiz-empty-icon"><CircleHelp size={24} /></span><h2>No question just yet</h2><p>{error}</p><button className="button button-dark" onClick={() => loadQuestion()} type="button"><RotateCw size={15} /> Try again</button></div>
                        : quiz ? <>
          <div className="quiz-meta"><span className={`difficulty-pill difficulty-${quiz.difficulty}`}>{quiz.difficulty}</span><span className="bloom-pill">{quiz.bloom_level ?? 'remember'}</span><span>{quiz.topic}</span><span className="question-count">Question <b>{quiz.question_number ?? '01'}{quiz.num_questions ? ` / ${quiz.num_questions}` : ''}</b></span></div>
          <h2 className="quiz-question"><HighlightedText glossary={quiz.glossary ?? []} text={quiz.question} /></h2>
          <div className="quiz-options">
            {(quiz.options ?? []).map((option, index) => {
              const isCorrect = result && index === result.correct_index
              const isSelectedWrong = result && index === result.selectedIndex && !result.correct
              return <button className={`quiz-option ${isCorrect ? 'option-correct' : ''} ${isSelectedWrong ? 'option-wrong' : ''}`} disabled={Boolean(result) || answering} key={`${index}-${option}`} onClick={() => chooseAnswer(index)} type="button"><span className="option-letter">{optionLetters[index]}</span><span><HighlightedText glossary={quiz.glossary ?? []} text={option} /></span>{isCorrect && <Check className="option-feedback" size={18} />}{isSelectedWrong && <X className="option-feedback" size={18} />}</button>
            })}
          </div>
          {error && <p className="inline-message message-error" role="alert">{error}</p>}
          {answering && <LoadingStatus className="answer-saving" label="Checking your answer…" />}
          {result && <div className={`answer-result ${result.correct ? 'result-correct' : 'result-incorrect'}`}>
            <div className="result-heading"><span className="result-icon">{result.correct ? <Check size={17} /> : <X size={17} />}</span><div><strong>{result.correct ? 'That’s right.' : 'Not quite.'}</strong><span>Mastery is now {Math.round(result.mastery_score * 100)}% · next up: {result.next_difficulty}</span></div></div>
            <p className="result-explanation"><HighlightedText glossary={quiz?.glossary ?? []} text={result.explanation} /></p>
            {result.re_explanation && <div className="reteach-note"><span className="section-kicker">LET’S TRY A SIMPLER EXPLANATION</span><p><HighlightedText glossary={result.re_glossary ?? []} text={result.re_explanation} /></p></div>}
            {result.session_progress?.weak_points?.length > 0 && <div className="quiz-summary-panel"><span className="section-kicker">WEAK POINTS</span><ul>{result.session_progress.weak_points.slice(0, 3).map((point, index) => <li key={`${point.topic}-${index}`}><Link to={`/explain?source_id=${point.source_id}&topic_id=${point.topic_id ?? ''}&topics=${encodeURIComponent(point.topic)}`}>{point.topic}</Link> missed {point.missed} time(s)</li>)}</ul></div>}
            {result.session_progress && <div className="quiz-summary-panel"><span className="section-kicker">SESSION SUMMARY</span><p>{result.session_progress.answered}/{result.session_progress.total} answered • {result.session_progress.score}% accuracy</p></div>}
            {result.citation && <div className="result-citation"><span className="section-kicker">FROM YOUR MATERIAL</span><CitationChip citation={result.citation} onClick={() => result.citation.source_type === 'video' ? setVideoCitation(result.citation) : setVideoCitation(null)} /></div>}
            {result.session_progress?.completed
              ? <button className="button button-dark next-question-button" onClick={restartSession} type="button"><RotateCw size={15} /> Start another set</button>
                : <button className="button button-dark next-question-button" onClick={() => loadQuestion()} type="button">Next question <ArrowRight size={15} /></button>}
          </div>}
              </> : <div className="quiz-empty"><h2>Start a quiz when you’re ready</h2><p>Choose your filters above, then start a question set.</p><button className="button button-dark" disabled={loading} onClick={startQuiz} type="button">Start quiz</button></div>}
      </section>
      <p className="quiz-footnote">Questions are generated from your uploaded course material.</p>
      {videoCitation && <VideoModal citation={videoCitation} onClose={() => setVideoCitation(null)} url={videoUrl} />}
    </div>
  )
}
