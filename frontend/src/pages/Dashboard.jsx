import { useEffect, useState } from 'react'
import { ArrowDownRight, ArrowUpRight, BookOpenCheck, RefreshCw, Target } from 'lucide-react'
import { useSearchParams } from 'react-router-dom'
import { getApiErrorMessage, getMastery } from '../api'
import LoadingStatus from '../components/LoadingStatus'
import MasteryChart from '../components/MasteryChart'

function levelForScore(score) {
  if (score < 0.4) return 'Needs a revisit'
  if (score < 0.7) return 'Taking shape'
  return 'Strong recall'
}

export default function Dashboard() {
  const [searchParams] = useSearchParams()
  const selectionKey = searchParams.toString()
  const filters = {
    sourceIds: searchParams.getAll('source_ids').map(Number).filter(Number.isInteger),
    topics: searchParams.getAll('topics'),
  }
  const [topics, setTopics] = useState([])
  const [error, setError] = useState('')
  const [loading, setLoading] = useState(true)
  const [refreshing, setRefreshing] = useState(false)

  const refresh = async () => {
    setRefreshing(true)
    try {
      setTopics(await getMastery(filters))
      setError('')
    } catch (requestError) {
      setError(getApiErrorMessage(requestError, 'Could not load your mastery dashboard.'))
    } finally {
      setLoading(false)
      setRefreshing(false)
    }
  }

  useEffect(() => {
    let active = true
    const params = new URLSearchParams(selectionKey)
    getMastery({
      sourceIds: params.getAll('source_ids').map(Number).filter(Number.isInteger),
      topics: params.getAll('topics'),
    })
      .then((items) => {
        if (!active) return
        setTopics(items)
        setError('')
      })
      .catch((requestError) => {
        if (active) setError(getApiErrorMessage(requestError, 'Could not load your mastery dashboard.'))
      })
      .finally(() => {
        if (active) setLoading(false)
      })
    return () => { active = false }
  }, [selectionKey])

  const average = topics.length ? topics.reduce((total, item) => total + item.score, 0) / topics.length : 0
  const needsWork = topics.filter((topic) => topic.score < 0.4).length
  const strongest = [...topics].sort((a, b) => b.score - a.score)[0]

  return (
    <div className="page-stack">
      <header className="page-heading page-heading-row"><div><span className="eyebrow">YOUR LEARNING PICTURE</span><h1>Notice what’s sticking.</h1><p>Mastery shifts with every quiz answer, so your next review has a clear direction.</p></div><button aria-label="Refresh mastery" aria-busy={refreshing} className={`icon-button refresh-dashboard${refreshing ? ' dashboard-refreshing' : ''}`} disabled={loading || refreshing} onClick={refresh} title="Refresh mastery" type="button">{refreshing ? <span aria-hidden="true" className="loading-ring loading-ring-small" /> : <RefreshCw size={16} />}</button></header>
      {error && <p className="inline-message message-error" role="alert">{error}</p>}
      <section aria-label="Mastery summary" className="dashboard-stats">
        <article className="stat-panel stat-featured"><span className="stat-icon"><Target size={18} /></span><span className="stat-label">AVERAGE MASTERY</span><strong>{loading ? <span className="loading-ring loading-ring-small" /> : <>{Math.round(average * 100)}<small>%</small></>}</strong><span className="stat-note">{loading ? 'Loading progress…' : `Across ${topics.length} ${topics.length === 1 ? 'topic' : 'topics'}`}</span></article>
        <article className="stat-panel"><span className="stat-icon stat-icon-warm"><ArrowDownRight size={18} /></span><span className="stat-label">READY TO REVISIT</span><strong>{loading ? <span className="loading-ring loading-ring-small" /> : <>{needsWork}<small> topics</small></>}</strong><span className="stat-note">Below 40% mastery</span></article>
        <article className="stat-panel"><span className="stat-icon stat-icon-green"><ArrowUpRight size={18} /></span><span className="stat-label">STRONGEST TOPIC</span><strong className="strongest-topic">{loading ? <span className="loading-ring loading-ring-small" /> : strongest?.topic ?? '—'}</strong><span className="stat-note">{loading ? 'Loading progress…' : strongest ? `${Math.round(strongest.score * 100)}% · ${levelForScore(strongest.score)}` : 'Keep practicing to build your map'}</span></article>
      </section>

      <section className="mastery-section">
        <div className="mastery-section-heading"><div><span className="section-kicker">TOPIC BY TOPIC</span><h2>Mastery map</h2></div><div className="chart-legend"><span><i className="legend-dot legend-red" /> Revisit</span><span><i className="legend-dot legend-yellow" /> Building</span><span><i className="legend-dot legend-green" /> Strong</span></div></div>
        {loading ? <LoadingStatus className="chart-empty" label="Loading your progress…" /> : topics.length ? <MasteryChart topics={topics} /> : <div className="chart-empty"><BookOpenCheck size={25} /><strong>Your learning map starts with a quiz</strong><span>Add course material, then try your first adaptive question.</span></div>}
      </section>
      {topics.length > 0 && <section className="topic-table-section"><div className="mastery-section-heading"><div><span className="section-kicker">CURRENT SNAPSHOT</span><h2>All topics</h2></div></div><div className="topic-table">{topics.map((topic) => <div className="topic-table-row" key={topic.topic}><span className="topic-name">{topic.topic}</span><div className="topic-meter"><span style={{ width: `${topic.score * 100}%` }} /></div><strong>{Math.round(topic.score * 100)}%</strong><span className={`topic-level level-${topic.difficulty}`}>{levelForScore(topic.score)}</span></div>)}</div></section>}
    </div>
  )
}
