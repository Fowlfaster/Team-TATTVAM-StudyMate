import { useEffect, useMemo, useState } from 'react'
import { ArrowRight, Award, BookOpenCheck, Brain, CircleHelp, RefreshCw, Target } from 'lucide-react'
import { Link, useSearchParams } from 'react-router-dom'
import {
  Bar,
  BarChart,
  CartesianGrid,
  Cell,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from 'recharts'
import { getApiErrorMessage, getRanking } from '../api'
import LoadingStatus from '../components/LoadingStatus'
import SubjectScopeSelector from '../components/SubjectScopeSelector'
import useSubjectScope from '../components/useSubjectScope'

function levelColor(level, status) {
  if (status === 'not enough data') return '#a5aaa1'
  if (level === 'Beginner') return '#c76550'
  if (level === 'Developing') return '#c1932f'
  if (level === 'Proficient') return '#668d72'
  return '#356a50'
}

function actionDetails(action) {
  if (action === 'explain') return { label: 'Explain', icon: BookOpenCheck, path: '/explain' }
  if (action === 'evaluate') return { label: 'Evaluate', icon: Brain, path: '/evaluate' }
  return { label: 'Quiz', icon: CircleHelp, path: '/quiz' }
}

function actionHref(topic, action) {
  const params = new URLSearchParams()
  topic.source_ids.forEach((sourceId) => params.append('source_ids', sourceId))
  params.append('topics', topic.topic)
  return `${actionDetails(action).path}?${params.toString()}`
}

export default function Ranking() {
  const [searchParams] = useSearchParams()
  const selectionKey = searchParams.toString()
  const initialParams = new URLSearchParams(selectionKey)
  const scope = useSubjectScope({
    requestedSourceIds: initialParams.getAll('source_ids').concat(initialParams.get('source_id') ?? []).filter(Boolean),
    requestedTopics: initialParams.getAll('topics'),
  })
  const { subjects, subjectId, selectSubject, sources, sourceId, selectSource, sourceIds, topics: topicOptions, selectedTopicIds, setSelectedTopicIds } = scope
  const selectedTopics = useMemo(
    () => topicOptions.filter((topic) => selectedTopicIds.includes(String(topic.id))).map((topic) => topic.name),
    [topicOptions, selectedTopicIds],
  )
  const [ranking, setRanking] = useState(null)
  const [error, setError] = useState('')
  const [loading, setLoading] = useState(true)
  const [refreshing, setRefreshing] = useState(false)

  const refresh = async () => {
    if (!subjectId) return
    setRefreshing(true)
    try {
      const result = await getRanking({
        sourceIds: sourceIds,
        topics: selectedTopics,
        subjectId: Number(subjectId),
      })
      setRanking(result)
      setError('')
    } catch (requestError) {
      setError(getApiErrorMessage(requestError, 'Could not load your understanding ranking.'))
    } finally {
      setLoading(false)
      setRefreshing(false)
    }
  }

  useEffect(() => {
    let active = true
    if (scope.loading || !subjectId) return () => { active = false }
    getRanking({
      sourceIds,
      topics: selectedTopics,
      subjectId: Number(subjectId),
    })
      .then((result) => {
        if (active) {
          setRanking(result)
          setError('')
        }
      })
      .catch((requestError) => {
        if (active) setError(getApiErrorMessage(requestError, 'Could not load your understanding ranking.'))
      })
      .finally(() => {
        if (active) setLoading(false)
      })
    return () => { active = false }
  }, [selectionKey, subjectId, sourceId, sourceIds, selectedTopics, scope.loading])

  const topics = ranking?.topics ?? []
  const chartHeight = Math.max(250, topics.length * 38)

  return (
    <div className="page-stack ranking-page">
      <header className="page-heading page-heading-row">
        <div><span className="eyebrow">YOUR UNDERSTANDING</span><h1>See what’s taking shape.</h1><p>A topic-by-topic view of your practice and explanations.</p></div>
        <button aria-label="Refresh ranking" aria-busy={refreshing} className="icon-button refresh-dashboard" disabled={loading || refreshing} onClick={refresh} title="Refresh ranking" type="button">{refreshing ? <span aria-hidden="true" className="loading-ring loading-ring-small" /> : <RefreshCw size={16} />}</button>
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
        topics={topicOptions}
      />

      {error && <p className="inline-message message-error" role="alert">{error}</p>}

      <section aria-label="Overall understanding score" className="ranking-overall">
        <div className="ranking-overall-icon"><Award size={19} /></div>
        <div className="ranking-overall-copy"><span className="stat-label">OVERALL UNDERSTANDING</span><strong>{loading ? <span className="loading-ring loading-ring-small" /> : ranking?.overall_score == null ? '—' : Math.round(ranking.overall_score)}<small>{!loading && ranking?.overall_score != null ? '/100' : ''}</small></strong><span className="stat-note">{loading ? 'Calculating your topic scores…' : `${ranking?.assessed_topics ?? 0} assessed ${ranking?.assessed_topics === 1 ? 'topic' : 'topics'}`}</span></div>
        <div className="ranking-overall-note"><Target size={16} /><span>Scores improve as you practice and explain ideas in your own words.</span></div>
      </section>

      {scope.loading || (Boolean(subjectId) && loading) ? <LoadingStatus className="ranking-loading" label="Ranking your topics…" /> : topics.length === 0 ? (
        <div className="chart-empty ranking-empty"><BookOpenCheck size={25} /><strong>Your ranking starts with a topic</strong><span>Add course material, then quiz yourself or try Concept Evaluation.</span><Link className="button button-dark" to="/upload">Go to your library <ArrowRight size={15} /></Link></div>
      ) : <>
        <section aria-labelledby="ranking-chart-title" className="ranking-chart-section">
          <div className="mastery-section-heading"><div><span className="section-kicker">TOPIC OVERVIEW</span><h2 id="ranking-chart-title">Understanding scores</h2></div><span className="ranking-chart-scale">0 to 100</span></div>
          <div className="ranking-chart" style={{ height: chartHeight }}>
            <ResponsiveContainer height="100%" width="100%">
              <BarChart data={topics} layout="vertical" margin={{ top: 8, right: 20, left: 12, bottom: 8 }}>
                <CartesianGrid stroke="#e9e7df" strokeDasharray="3 5" vertical />
                <XAxis axisLine={false} domain={[0, 100]} tick={{ fill: '#858980', fontSize: 10 }} tickLine={false} type="number" />
                <YAxis axisLine={false} dataKey="topic" tick={{ fill: '#566257', fontSize: 10 }} tickLine={false} type="category" width={130} />
                <Tooltip contentStyle={{ border: '1px solid #e6e3d8', borderRadius: 5, fontSize: 11 }} formatter={(value) => [`${Math.round(Number(value))}/100`, 'Understanding']} />
                <Bar dataKey="score" maxBarSize={20} radius={[0, 4, 4, 0]}>
                  {topics.map((topic) => <Cell fill={levelColor(topic.level, topic.assessment_status)} key={`${topic.topic}-${topic.source_ids.join('-')}`} />)}
                </Bar>
              </BarChart>
            </ResponsiveContainer>
          </div>
        </section>

        <section aria-labelledby="ranked-topics-title" className="ranking-list-section">
          <div className="mastery-section-heading"><div><span className="section-kicker">WEAKEST FIRST</span><h2 id="ranked-topics-title">Topic ranking</h2></div></div>
          <ol className="ranking-topic-list">
            {topics.map((topic, index) => {
              const action = actionDetails(topic.recommended_action)
              const ActionIcon = action.icon
              const notEnoughData = topic.assessment_status === 'not enough data'
              return (
                <li className="ranking-topic-row" key={`${topic.topic}-${topic.source_ids.join('-')}`}>
                  <span className="ranking-index">{String(index + 1).padStart(2, '0')}</span>
                  <div className="ranking-topic-main">
                    <div className="ranking-topic-heading"><strong>{topic.topic}</strong><span className={`ranking-level ranking-level-${notEnoughData ? 'none' : topic.level.toLowerCase()}`}>{notEnoughData ? 'Not enough data' : topic.level}</span>{topic.assessment_status === 'partially assessed' && <span className="ranking-status">Partially assessed</span>}</div>
                    <div aria-label={notEnoughData ? 'Not enough data to show a progress score' : `${Math.round(topic.score)} percent`} className="ranking-progress"><span style={{ width: `${topic.score}%`, backgroundColor: levelColor(topic.level, topic.assessment_status) }} /></div>
                    <small className="ranking-attempt-count">{topic.attempt_count} quiz {topic.attempt_count === 1 ? 'attempt' : 'attempts'}{topic.evaluation_component == null ? ' · no concept evaluation yet' : ' · evaluation included'}</small>
                  </div>
                  <strong className="ranking-score">{notEnoughData ? '—' : Math.round(topic.score)}<small>{notEnoughData ? '' : '/100'}</small></strong>
                  <Link aria-label={`${action.label} ${topic.topic}`} className="ranking-action" to={actionHref(topic, topic.recommended_action)}><ActionIcon size={15} /><span>{action.label}</span><ArrowRight size={13} /></Link>
                </li>
              )
            })}
          </ol>
        </section>
      </>}
    </div>
  )
}