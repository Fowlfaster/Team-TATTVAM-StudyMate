import { BookOpenCheck, ChevronDown, FileText } from 'lucide-react'

export default function SourceTopicSelector({
  sources,
  selectedSourceIds,
  onSourceIdsChange,
  topics,
  selectedTopicIds,
  onSelectedTopicIdsChange,
  topicMode = 'checkbox',
}) {
  const toggleSource = (sourceId) => {
    const value = String(sourceId)
    onSourceIdsChange(selectedSourceIds.includes(value)
      ? selectedSourceIds.filter((id) => id !== value)
      : [...selectedSourceIds, value])
  }

  const toggleTopic = (topicId) => {
    const value = String(topicId)
    if (topicMode === 'single') {
      onSelectedTopicIdsChange(selectedTopicIds.includes(value) ? [] : [value])
      return
    }
    onSelectedTopicIdsChange(selectedTopicIds.includes(value)
      ? selectedTopicIds.filter((topicIdValue) => topicIdValue !== value)
      : [...selectedTopicIds, value])
  }

  const readySources = sources.filter((source) => source.status === 'ready')
  const sourceLabel = selectedSourceIds.length === readySources.length && readySources.length > 0
    ? 'All ready sources'
    : `${selectedSourceIds.length} source${selectedSourceIds.length === 1 ? '' : 's'} selected`

  return (
    <section className="source-topic-selector" aria-label="Source and topic selection">
      <details className="source-picker-dropdown">
        <summary><FileText size={14} /><span>{sourceLabel}</span><ChevronDown aria-hidden="true" size={14} /></summary>
        <div className="source-picker-options">
          <label><input checked={selectedSourceIds.length === readySources.length && readySources.length > 0} disabled={readySources.length === 0} onChange={() => onSourceIdsChange(selectedSourceIds.length === readySources.length ? [] : readySources.map((source) => String(source.id)))} type="checkbox" /><span>All ready sources</span></label>
          {sources.map((source) => (
            <label key={source.id}>
              <input checked={selectedSourceIds.includes(String(source.id))} disabled={source.status !== 'ready'} onChange={() => toggleSource(source.id)} type="checkbox" />
              <span className="source-picker-copy" title={source.file_name}>{source.file_name}<small>{source.status === 'ready' ? 'Ready' : 'Processing'}</small></span>
            </label>
          ))}
        </div>
      </details>
      <div className="source-topic-options">
        {topics.length ? topics.map((topic) => (
          <label className="source-topic-option" key={topic.id}>
            <input checked={selectedTopicIds.includes(String(topic.id))} onChange={() => toggleTopic(topic.id)} type={topicMode === 'single' ? 'radio' : 'checkbox'} name={topicMode === 'single' ? 'selected-explanation-topic' : undefined} />
            <span><strong>{topic.name}</strong><small>{topic.summary}</small></span>
          </label>
        )) : <p className="source-topic-empty"><BookOpenCheck size={15} />No topics for the selected sources yet.</p>}
      </div>
    </section>
  )
}
