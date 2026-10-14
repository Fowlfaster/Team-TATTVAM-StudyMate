import { useEffect, useMemo, useRef, useState } from 'react'
import { getApiErrorMessage, getSources, getSubjects, getSourceTopics } from '../api'

export default function useSubjectScope({ requestedSourceIds = [], requestedTopicIds = [], requestedTopics = [] } = {}) {
  const initialRequest = useRef({ requestedSourceIds, requestedTopicIds, requestedTopics })
  const [subjects, setSubjects] = useState([])
  const [subjectId, setSubjectId] = useState('')
  const [sources, setSources] = useState([])
  const [sourceId, setSourceId] = useState('')
  const [topics, setTopics] = useState([])
  const [selectedTopicIds, setSelectedTopicIds] = useState([])
  const [subjectsLoaded, setSubjectsLoaded] = useState(false)
  const [loadedSubjectId, setLoadedSubjectId] = useState('')
  const [error, setError] = useState('')

  useEffect(() => {
    let active = true
    Promise.all([getSubjects(), getSources()])
      .then(([subjectRows, allSources]) => {
        if (!active) return
        setSubjects(subjectRows)
        const requested = allSources.find((source) => initialRequest.current.requestedSourceIds.includes(String(source.id)))
        const stored = window.localStorage.getItem('studymate_subject_id')
        const selected = requested?.subject_id
          ?? (subjectRows.some((subject) => String(subject.id) === stored) ? Number(stored) : subjectRows[0]?.id)
          ?? ''
        setSubjectId(String(selected))
      })
      .catch((requestError) => {
        if (active) setError(getApiErrorMessage(requestError, 'Could not load subjects.'))
      })
      .finally(() => { if (active) setSubjectsLoaded(true) })
    return () => { active = false }
  }, [])

  useEffect(() => {
    if (!subjectId) {
      return undefined
    }
    let active = true
    getSources(subjectId)
      .then((items) => {
        if (!active) return
        const readySources = items.filter((source) => source.status === 'ready')
        setSources(items)
        const requested = initialRequest.current.requestedSourceIds.find((id) => readySources.some((source) => String(source.id) === id))
        setSourceId((current) => requested ?? (readySources.some((source) => String(source.id) === current) ? current : ''))
        setError('')
      })
      .catch((requestError) => {
        if (active) {
          setSources([])
          setError(getApiErrorMessage(requestError, 'Could not load sources.'))
        }
      })
      .finally(() => { if (active) setLoadedSubjectId(subjectId) })
    return () => { active = false }
  }, [subjectId])

  const readySources = useMemo(() => sources.filter((source) => source.status === 'ready'), [sources])
  const applicableSources = useMemo(
    () => sourceId ? readySources.filter((source) => String(source.id) === sourceId) : readySources,
    [sourceId, readySources],
  )
  const applicableSourceIds = useMemo(() => applicableSources.map((source) => source.id), [applicableSources])
  const topicSourceKey = applicableSources.map((source) => source.id).join(',')
  const loading = !subjectsLoaded || (Boolean(subjectId) && loadedSubjectId !== subjectId)

  useEffect(() => {
    if (!subjectId) return undefined
    let active = true
    const load = async () => {
      try {
        const groups = await Promise.all(applicableSources.map((source) => getSourceTopics(source.id)))
        const available = groups.flat()
        if (!active) return
        setTopics(available)
        setSelectedTopicIds((current) => {
          const valid = current.filter((id) => available.some((topic) => String(topic.id) === id))
          if (valid.length) return valid
          const requestedId = initialRequest.current.requestedTopicIds.find((id) => available.some((topic) => String(topic.id) === id))
          if (requestedId) return [requestedId]
          return available.filter((topic) => initialRequest.current.requestedTopics.includes(topic.name)).map((topic) => String(topic.id))
        })
      } catch (requestError) {
        if (active) {
          setTopics([])
          setError(getApiErrorMessage(requestError, 'Could not load topics.'))
        }
      }
    }
    load()
    return () => { active = false }
  }, [subjectId, topicSourceKey, applicableSources])

  const selectSubject = (value) => {
    const nextValue = String(value)
    setSubjectId(nextValue)
    window.localStorage.setItem('studymate_subject_id', nextValue)
    setSourceId('')
    setSources([])
    setTopics([])
    setSelectedTopicIds([])
  }

  const selectSource = (value) => {
    setSourceId(String(value))
    setSelectedTopicIds([])
  }

  return {
    subjects,
    subjectId,
    subject: subjects.find((item) => String(item.id) === subjectId),
    selectSubject,
    sources,
    readySources,
    sourceId,
    selectSource,
    sourceIds: applicableSourceIds,
    topics,
    selectedTopicIds,
    setSelectedTopicIds,
    loading,
    error,
    setError,
  }
}
