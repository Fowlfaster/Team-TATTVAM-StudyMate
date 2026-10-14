import { useEffect, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { ArrowRight, BookOpenCheck, Brain, ChartNoAxesColumnIncreasing, CircleHelp, Sparkles } from 'lucide-react'
import { getSourceTopics } from '../api'

const actions = [
  { title: 'Explanation', detail: 'Explore a topic at your level.', icon: BookOpenCheck, path: '/explain', mode: '' },
  { title: 'Quiz', detail: 'Practice with adaptive questions.', icon: CircleHelp, path: '/quiz', mode: '' },
  { title: 'Concept Evaluation', detail: 'Explain a concept in your own words.', icon: Brain, path: '/evaluate', mode: '' },
  { title: 'Understanding Ranking', detail: 'Review your topic mastery map.', icon: ChartNoAxesColumnIncreasing, path: '/ranking', mode: '' },
]

export default function ActionHub({ sources }) {
  const [selectedSourceIds, setSelectedSourceIds] = useState([])
  const [topicsBySource, setTopicsBySource] = useState({})
  const [selectedTopics, setSelectedTopics] = useState([])
  const [topicsLoading, setTopicsLoading] = useState(false)
  const [topicError, setTopicError] = useState('')
  const navigate = useNavigate()
  const sourceKey = sources.map((source) => source.id).join(',')

  useEffect(() => {
    let active = true
    const loadTopics = async () => {
      if (!sourceKey) return
      setTopicsLoading(true)
      setTopicError('')
      try {
        const sourceIds = sourceKey.split(',')
        const entries = await Promise.all(sourceIds.map(async (sourceId) => ({
          sourceId,
          topics: await getSourceTopics(sourceId),
        })))
        if (active) {
          setTopicsBySource(Object.fromEntries(entries.map(({ sourceId, topics }) => [sourceId, topics])))
        }
      } catch {
        if (active) setTopicError('Topics could not be loaded. You can still start with these sources.')
      } finally {
        if (active) setTopicsLoading(false)
      }
    }
    loadTopics()
    return () => { active = false }
  }, [sourceKey])

  const selectedTopicsForSources = selectedSourceIds.flatMap((sourceId) =>
    (topicsBySource[sourceId] ?? []).map((topic) => topic.name),
  )
  const topicOptions = [...new Set(selectedTopicsForSources)]

  const toggleSource = (sourceId) => {
    const value = String(sourceId)
    setSelectedSourceIds((current) => current.includes(value)
      ? current.filter((id) => id !== value)
      : [...current, value])
    setSelectedTopics([])
  }

  const toggleTopic = (topic) => {
    setSelectedTopics((current) => current.includes(topic)
      ? current.filter((name) => name !== topic)
      : [...current, topic])
  }

  const openAction = ({ path, mode }) => {
    const params = new URLSearchParams()
    selectedSourceIds.forEach((sourceId) => params.append('source_ids', sourceId))
    selectedTopics.forEach((topic) => params.append('topics', topic))
    if (mode) params.set('mode', mode)
    navigate(`${path}?${params.toString()}`)
  }

  return (
    <section aria-labelledby="action-hub-title" className="rounded-md border border-[#dfe4da] bg-[#fffefa] p-5 shadow-sm sm:p-7">
      <div className="flex flex-col justify-between gap-4 sm:flex-row sm:items-end">
        <div>
          <span className="section-kicker">READY TO STUDY</span>
          <h2 className="mt-1 text-xl font-semibold text-[#29372f]" id="action-hub-title">Your material is ready. What would you like to do?</h2>
        </div>
        <span className="flex items-center gap-1.5 text-xs font-semibold text-[#63816b]"><Sparkles size={14} /> {sources.length} ready {sources.length === 1 ? 'source' : 'sources'}</span>
      </div>

      <div className="mt-5 grid gap-5 lg:grid-cols-[1fr_1fr]">
        <fieldset className="min-w-0">
          <legend className="mb-2 text-xs font-bold uppercase tracking-[0.08em] text-[#777f76]">Choose one or more sources</legend>
          <div className="grid gap-2 sm:grid-cols-2">
            {sources.map((source) => {
              const checked = selectedSourceIds.includes(String(source.id))
              return (
                <label className={`flex min-w-0 cursor-pointer items-center gap-3 rounded border px-3 py-3 text-sm transition-colors ${checked ? 'border-[#71917a] bg-[#f0f5ed]' : 'border-[#e4e7de] hover:bg-[#fafaf6]'}`} key={source.id}>
                  <input checked={checked} className="accent-[#386951]" onChange={() => toggleSource(source.id)} type="checkbox" />
                  <span className="truncate font-medium text-[#405047]" title={source.file_name}>{source.file_name}</span>
                </label>
              )
            })}
          </div>
        </fieldset>

        <fieldset className="min-w-0">
          <legend className="mb-2 text-xs font-bold uppercase tracking-[0.08em] text-[#777f76]">Topics <span className="font-normal normal-case tracking-normal">(optional)</span></legend>
          {selectedSourceIds.length === 0 ? (
            <p className="rounded border border-dashed border-[#dfe4da] px-3 py-3 text-xs text-[#92988f]">Choose a source to see its topics.</p>
          ) : topicsLoading ? (
            <p className="rounded border border-dashed border-[#dfe4da] px-3 py-3 text-xs text-[#777f76]">Loading topics…</p>
          ) : topicOptions.length ? (
            <div className="grid max-h-28 gap-2 overflow-y-auto rounded border border-[#e4e7de] p-3 sm:grid-cols-2">
              {topicOptions.map((topic) => (
                <label className="flex min-w-0 cursor-pointer items-center gap-2 text-xs text-[#56665a]" key={topic}>
                  <input checked={selectedTopics.includes(topic)} className="accent-[#386951]" onChange={() => toggleTopic(topic)} type="checkbox" />
                  <span className="truncate" title={topic}>{topic}</span>
                </label>
              ))}
            </div>
          ) : (
            <p className="rounded border border-dashed border-[#dfe4da] px-3 py-3 text-xs text-[#777f76]">No topics available yet; all source material will be included.</p>
          )}
          {topicError && <p className="mt-2 text-xs text-[#a3483e]" role="status">{topicError}</p>}
          {selectedTopics.length > 0 && <p className="mt-2 text-[11px] text-[#777f76]">{selectedTopics.length} topic{selectedTopics.length === 1 ? '' : 's'} selected</p>}
        </fieldset>
      </div>

      <div className="mt-5 grid gap-2 sm:grid-cols-2 xl:grid-cols-4">
        {actions.map(({ title, detail, icon: Icon, path, mode }) => (
          <button className="group flex min-h-20 items-center gap-3 rounded border border-[#e4e7de] bg-white px-3 py-3 text-left transition-all hover:-translate-y-0.5 hover:border-[#a7bba4] hover:shadow-sm disabled:cursor-not-allowed disabled:opacity-45 disabled:hover:translate-y-0 disabled:hover:shadow-none" disabled={!selectedSourceIds.length} key={title} onClick={() => openAction({ path, mode })} type="button">
            <span className="grid h-9 w-9 shrink-0 place-items-center rounded bg-[#e8efe6] text-[#386951]"><Icon size={17} /></span>
            <span className="min-w-0 flex-1"><strong className="block text-xs text-[#29372f]">{title}</strong><small className="mt-1 block text-[10px] leading-4 text-[#777f76]">{detail}</small></span>
            <ArrowRight className="shrink-0 text-[#a65d44] transition-transform group-hover:translate-x-0.5" size={15} />
          </button>
        ))}
      </div>
      <p className="mt-3 flex items-center gap-1.5 text-[10px] text-[#90968b]"><Brain size={12} /> With no topics selected, the chosen sources are used in full.</p>
    </section>
  )
}