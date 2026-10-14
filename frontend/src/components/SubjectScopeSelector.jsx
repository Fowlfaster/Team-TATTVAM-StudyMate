import { FolderOpen } from 'lucide-react'

function normalizeTopicName(value) {
  return value.normalize('NFKC').toLocaleLowerCase().replace(/[^\p{L}\p{N}]+/gu, '')
}

export default function SubjectScopeSelector({
  subjects,
  subjectId,
  onSubjectChange,
  sources,
  sourceId,
  onSourceChange,
  topics = [],
  selectedTopicIds = [],
  onSelectedTopicIdsChange = () => {},
  topicMode = 'checkbox',
}) {
  const toggleTopic = (topicId) => {
    const value = String(topicId)
    if (topicMode === 'single') {
      onSelectedTopicIdsChange(selectedTopicIds.includes(value) ? [] : [value])
      return
    }
    onSelectedTopicIdsChange(selectedTopicIds.includes(value)
      ? selectedTopicIds.filter((id) => id !== value)
      : [...selectedTopicIds, value])
  }

  const topicGroups = sourceId ? topics.map((topic) => ({
    key: String(topic.id),
    name: topic.name,
    topicIds: [String(topic.id)],
  })) : [...topics.reduce((groups, topic) => {
    const key = normalizeTopicName(topic.name)
    const group = groups.get(key) ?? { key, name: topic.name, topicIds: [] }
    group.topicIds.push(String(topic.id))
    groups.set(key, group)
    return groups
  }, new Map()).values()]

  const toggleTopicGroup = (topicIds) => {
    if (topicMode === 'single') {
      onSelectedTopicIdsChange(topicIds)
      return
    }
    const allSelected = topicIds.every((id) => selectedTopicIds.includes(id))
    onSelectedTopicIdsChange(allSelected
      ? selectedTopicIds.filter((id) => !topicIds.includes(id))
      : [...new Set([...selectedTopicIds, ...topicIds])])
  }

  return (
    <section aria-label="Subject, source, and topic filters" className="subject-scope-selector">
      <label>
        <span><FolderOpen size={14} /> Subject</span>
        <select aria-label="Subject" onChange={(event) => onSubjectChange(event.target.value)} value={subjectId}>
          <option value="">Choose a subject</option>
          {subjects.map((subject) => <option key={subject.id} value={subject.id}>{subject.name}</option>)}
        </select>
      </label>
      <label>
        <span>Source</span>
        <select aria-label="Source" disabled={!subjectId} onChange={(event) => onSourceChange(event.target.value)} value={sourceId}>
          <option value="">All sources in this subject</option>
          {sources.map((source) => <option disabled={source.status !== 'ready'} key={source.id} value={source.id}>{source.file_name}{source.status !== 'ready' ? ' (processing)' : ''}</option>)}
        </select>
      </label>
      {subjectId && <fieldset className="subject-topic-filter">
        <legend>Topics</legend>
        {topicGroups.length ? topicGroups.map((group) => (
          <label key={group.key}>
            <input
              checked={group.topicIds.every((id) => selectedTopicIds.includes(id))}
              name={topicMode === 'single' ? 'subject-topic' : undefined}
              onChange={() => toggleTopicGroup(group.topicIds)}
              type={topicMode === 'single' ? 'radio' : 'checkbox'}
            />
            <span>{group.name}</span>
          </label>
        )) : <small>No topics in this selection yet.</small>}
      </fieldset>}
    </section>
  )
}
