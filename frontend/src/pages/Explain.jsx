import { useEffect, useState } from 'react'
import { ArrowRight, BookOpenCheck, CircleHelp, FileText, Lightbulb, ListChecks, TriangleAlert } from 'lucide-react'
import { Link, useNavigate, useSearchParams } from 'react-router-dom'
import { API_BASE, analyzeSource, explainTopic, getApiErrorMessage, getSources, getSourceTopics } from '../api'
import CitationChip from '../components/CitationChip'
import HighlightedText from '../components/HighlightedText'
import LoadingStatus from '../components/LoadingStatus'
import SourceTopicSelector from '../components/SourceTopicSelector'
import VideoModal from '../components/VideoModal'

const levels = [
  { value: 'beginner', label: 'Beginner' },
  { value: 'intermediate', label: 'Intermediate' },
  { value: 'advanced', label: 'Advanced' },
]

function sourceIdsFrom(searchParams) {
  const sourceIds = searchParams.getAll('source_ids')
  if (!sourceIds.length && searchParams.get('source_id')) sourceIds.push(searchParams.get('source_id'))
  return sourceIds.map(Number).filter(Number.isInteger)
}

export default function Explain() {
  const [searchParams] = useSearchParams()
  const navigate = useNavigate()
  const selectionKey = searchParams.toString()
  const [topics, setTopics] = useState([])
  const [sources, setSources] = useState([])
  const [selectedSourceIds, setSelectedSourceIds] = useState([])
  const [analysisSourceId, setAnalysisSourceId] = useState('')
  const [loadedSelectionKey, setLoadedSelectionKey] = useState(null)
  const [loadedTopicSourceKey, setLoadedTopicSourceKey] = useState('')
  const [topicsError, setTopicsError] = useState('')
  const [selectedTopicIds, setSelectedTopicIds] = useState([])
  const [level, setLevel] = useState('beginner')
  const [activeTab, setActiveTab] = useState('topic')
  const [highlights, setHighlights] = useState(true)
  const [analysis, setAnalysis] = useState(null)
  const [loadedAnalysisKey, setLoadedAnalysisKey] = useState('')
  const [analysisError, setAnalysisError] = useState(null)
  const [activeSectionId, setActiveSectionId] = useState(null)
  const [explanation, setExplanation] = useState(null)
  const [loadedKey, setLoadedKey] = useState('')
  const [explanationError, setExplanationError] = useState(null)
  const [selectedCitation, setSelectedCitation] = useState(null)
  const [videoCitation, setVideoCitation] = useState(null)

  useEffect(() => {
    let active = true
    const params = new URLSearchParams(selectionKey)
    const requestedSourceIds = sourceIdsFrom(params).map(String)
    const loadSources = async () => {
      setTopicsError('')
      try {
        const allSources = await getSources()
        const visibleSources = allSources.filter((source) => source.status !== 'failed')
        const readySources = visibleSources.filter((source) => source.status === 'ready')
        const selected = requestedSourceIds.length
          ? readySources.filter((source) => requestedSourceIds.includes(String(source.id))).map((source) => String(source.id))
          : readySources.map((source) => String(source.id))
        if (active) {
          setSources(visibleSources)
          setSelectedSourceIds(selected)
          setAnalysisSourceId((current) => selected.includes(current) ? current : selected[0] ?? '')
        }
      } catch (requestError) {
        if (active) {
          setSources([])
          setTopics([])
          setSelectedSourceIds([])
          setSelectedTopicIds([])
          setTopicsError(getApiErrorMessage(requestError, 'Could not load topics from your sources.'))
        }
      } finally {
        if (active) setLoadedSelectionKey(selectionKey)
      }
    }
    loadSources()
    return () => { active = false }
  }, [selectionKey])

  const sourceSelectionKey = selectedSourceIds.join(',')
  useEffect(() => {
    if (loadedSelectionKey !== selectionKey) return undefined
    let active = true
    const loadTopics = async () => {
      const params = new URLSearchParams(selectionKey)
      const requestedTopics = params.getAll('topics')
      const requestedTopicId = params.get('topic_id')
      try {
        const sourceIds = sourceSelectionKey ? sourceSelectionKey.split(',') : []
        const topicGroups = await Promise.all(sourceIds.map((id) => getSourceTopics(id)))
        const availableTopics = topicGroups.flat()
        const matchedTopicIds = requestedTopicId
          ? availableTopics.filter((topic) => String(topic.id) === requestedTopicId).map((topic) => String(topic.id))
          : requestedTopics.length
            ? availableTopics.filter((topic) => requestedTopics.includes(topic.name)).map((topic) => String(topic.id))
            : []
        if (active) {
          setTopics(availableTopics)
          setSelectedTopicIds((current) => {
            const validSelection = current.filter((id) => availableTopics.some((topic) => String(topic.id) === id))
            if (validSelection.length) return validSelection
            if (matchedTopicIds.length) return matchedTopicIds
            return requestedTopics.length ? [] : availableTopics[0] ? [String(availableTopics[0].id)] : []
          })
          setTopicsError('')
        }
      } catch (requestError) {
        if (active) {
          setTopics([])
          setSelectedTopicIds([])
          setTopicsError(getApiErrorMessage(requestError, 'Could not load topics from your sources.'))
        }
      } finally {
        if (active) setLoadedTopicSourceKey(sourceSelectionKey)
      }
    }
    loadTopics()
    return () => { active = false }
  }, [loadedSelectionKey, selectionKey, sourceSelectionKey])

  const topicsLoading = loadedSelectionKey !== selectionKey || loadedTopicSourceKey !== sourceSelectionKey
  const selectedTopicId = selectedTopicIds[0] ?? ''
  const requestKey = selectedTopicId ? `${selectedTopicId}:${level}` : ''
  const explanationLoading = Boolean(requestKey) && (loadedKey !== requestKey || topicsLoading)

  useEffect(() => {
    if (!selectedTopicId || topicsLoading) return undefined
    let active = true
    const currentKey = `${selectedTopicId}:${level}`
    explainTopic(Number(selectedTopicId), level)
      .then((result) => {
        if (active) {
          setExplanationError(null)
          setExplanation(result)
          setLoadedKey(currentKey)
        }
      })
      .catch((requestError) => {
        if (active) {
          setExplanation(null)
          setExplanationError({
            key: currentKey,
            message: getApiErrorMessage(requestError, 'Could not generate this explanation.'),
          })
          setLoadedKey(currentKey)
        }
      })
    return () => { active = false }
  }, [selectedTopicId, level, topicsLoading])

  const selectedAnalysisSource = analysisSourceId || selectedSourceIds[0] || ''
  const analysisRequestKey = selectedAnalysisSource ? `${selectedAnalysisSource}:${level}` : ''
  const analysisLoading = activeTab === 'analysis'
    && Boolean(analysisRequestKey)
    && loadedAnalysisKey !== analysisRequestKey

  useEffect(() => {
    if (activeTab !== 'analysis' || !selectedAnalysisSource) return undefined
    let active = true
    const key = `${selectedAnalysisSource}:${level}`
    analyzeSource(Number(selectedAnalysisSource), level)
      .then((result) => {
        if (active) {
          setAnalysis({ key, result })
          setAnalysisError(null)
          setLoadedAnalysisKey(key)
          setActiveSectionId(result.sections[0]?.topic_id ?? null)
        }
      })
      .catch((requestError) => {
        if (active) {
          setAnalysisError({ key, message: getApiErrorMessage(requestError, 'Could not analyze this source.') })
          setLoadedAnalysisKey(key)
        }
      })
    return () => { active = false }
  }, [activeTab, selectedAnalysisSource, level])

  const selectedTopic = topics.find((topic) => String(topic.id) === selectedTopicId)
  const readySources = sources.filter((source) => source.status === 'ready')
  const currentAnalysis = analysis?.key === analysisRequestKey ? analysis.result : null
  const currentAnalysisError = analysisError?.key === analysisRequestKey ? analysisError.message : ''
  const activeAnalysisSection = currentAnalysis?.sections.find((section) => section.topic_id === activeSectionId)
    ?? currentAnalysis?.sections[0]
  const activeGlossary = activeTab === 'analysis'
    ? activeAnalysisSection?.glossary ?? currentAnalysis?.glossary ?? []
    : explanation?.glossary ?? []
  const error = explanationError?.key === requestKey ? explanationError.message : ''
  const citationClicked = (citation) => {
    if (citation.source_type === 'video') setVideoCitation(citation)
    else setSelectedCitation(citation)
  }

  const testTopic = () => {
    if (!selectedTopic) return
    const params = new URLSearchParams()
    params.append('source_id', String(selectedTopic.source_id))
    params.append('topic_id', String(selectedTopic.id))
    params.append('topics', selectedTopic.name)
    navigate(`/quiz?${params.toString()}`)
  }

  const openTopic = (topic) => {
    const params = new URLSearchParams()
    params.append('source_id', String(selectedAnalysisSource))
    params.append('topic_id', String(topic.topic_id))
    params.append('topics', topic.topic)
    navigate(`/explain?${params.toString()}`)
  }

  const takeSectionQuiz = (section) => {
    const params = new URLSearchParams()
    params.append('source_id', String(selectedAnalysisSource))
    params.append('topic_id', String(section.topic_id))
    params.append('topics', section.topic)
    navigate(`/quiz?${params.toString()}`)
  }

  const videoUrl = videoCitation
    ? /^https?:\/\//i.test(videoCitation.file_name)
      ? videoCitation.file_name
      : `${API_BASE}/sources/${videoCitation.source_id}/video`
    : ''

  return (
    <div className="explain-page">
      <aside aria-label="Topic list" className="explain-sidebar">
        <div className="explain-sidebar-heading">
          <span className="eyebrow">YOUR COURSE MATERIAL</span>
          <h1>Choose a topic.</h1>
          <p>Pick a concept to explore at your level.</p>
        </div>
        {topicsLoading ? <LoadingStatus className="explain-topic-loading" label="Loading sources and topics…" /> : topicsError ? (
          <div className="explain-topic-empty"><strong>Topics unavailable</strong><span>{topicsError}</span></div>
        ) : sources.length === 0 ? (
          <div className="explain-topic-empty"><BookOpenCheck size={20} /><strong>Upload material first</strong><span>Ready sources and their topics will appear here.</span><Link to="/upload">Go to your library <ArrowRight size={13} /></Link></div>
        ) : (
          <SourceTopicSelector
            onSelectedTopicIdsChange={setSelectedTopicIds}
            onSourceIdsChange={(ids) => {
              setSelectedSourceIds(ids)
              setAnalysisSourceId(ids[0] ?? '')
              setSelectedTopicIds([])
            }}
            selectedSourceIds={selectedSourceIds}
            selectedTopicIds={selectedTopicIds}
            sources={sources}
            topicMode="single"
            topics={topics}
          />
        )}
      </aside>

      <section aria-live="polite" className="explain-workspace">
        <header className="explain-toolbar">
          <div><span className="section-kicker">{activeTab === 'analysis' ? 'FULL MATERIAL' : 'EXPLANATION MODE'}</span><h2>{activeTab === 'analysis' ? currentAnalysis?.title ?? sources.find((source) => String(source.id) === selectedAnalysisSource)?.file_name ?? 'Analyze your material' : selectedTopic?.name ?? 'Explore your material'}</h2></div>
          <label className="explain-level-control"><span>EXPLANATION LEVEL</span><select aria-label="Explanation level" onChange={(event) => setLevel(event.target.value)} value={level}>{levels.map((item) => <option key={item.value} value={item.value}>{item.label}</option>)}</select></label>
        </header>
        <div className="explain-mode-toolbar">
          <div aria-label="Explanation view" className="explain-tabs" role="tablist">
            <button aria-selected={activeTab === 'analysis'} className={activeTab === 'analysis' ? 'explain-tab explain-tab-active' : 'explain-tab'} onClick={() => setActiveTab('analysis')} role="tab" type="button"><FileText size={14} /> Full material</button>
            <button aria-selected={activeTab === 'topic'} className={activeTab === 'topic' ? 'explain-tab explain-tab-active' : 'explain-tab'} onClick={() => setActiveTab('topic')} role="tab" type="button"><BookOpenCheck size={14} /> By topic</button>
          </div>
          <label className="highlights-toggle"><input checked={highlights} onChange={(event) => setHighlights(event.target.checked)} type="checkbox" /><span>Highlights</span></label>
        </div>

        {activeTab === 'analysis' ? (
          <div className="full-analysis-pane">
            {readySources.length > 0 && <label className="analysis-source-select"><span>ANALYZE SOURCE</span><select aria-label="Source to analyze" onChange={(event) => { setAnalysisSourceId(event.target.value); setActiveSectionId(null) }} value={selectedAnalysisSource}>{readySources.map((source) => <option key={source.id} value={source.id}>{source.file_name}</option>)}</select></label>}
            {topicsLoading ? <LoadingStatus className="explain-content-loading" label="Preparing your material…" /> : readySources.length === 0 ? (
              <div className="explain-state"><BookOpenCheck size={22} /><strong>{sources.some((source) => source.status === 'processing') ? 'Material is processing' : 'Upload material first'}</strong><p>{sources.some((source) => source.status === 'processing') ? 'Your uploaded material will be ready for a whole-material overview when processing finishes.' : 'Ready sources will appear here for a whole-material overview.'}</p><Link className="button button-dark" to="/upload">Go to your library <ArrowRight size={15} /></Link></div>
            ) : currentAnalysisError ? (
              <div className="explain-state explain-error" role="alert"><TriangleAlert size={20} /><strong>Analysis unavailable</strong><p>{currentAnalysisError}</p></div>
            ) : analysisLoading ? (
              <LoadingStatus className="explain-content-loading" label={`Analyzing all topics at ${level} level…`} />
            ) : currentAnalysis ? (
              <div className="analysis-content-layout">
                <article className="source-analysis-content">
                  <span className="section-kicker">WHOLE-SOURCE OVERVIEW</span>
                  <HighlightedText className="source-analysis-overview" glossary={currentAnalysis.glossary} highlights={highlights} text={currentAnalysis.overview} />
                  <section className="analysis-objectives"><h3><ListChecks size={17} /> Learning objectives</h3><ul>{currentAnalysis.learning_objectives.map((objective, index) => <li key={`${index}-${objective}`}><span>{String(index + 1).padStart(2, '0')}</span><HighlightedText glossary={currentAnalysis.glossary} highlights={highlights} text={objective} /></li>)}</ul></section>
                  <section className="analysis-sections"><h3>Topic-by-topic guide <small>{currentAnalysis.sections.length} sections</small></h3>
                    {currentAnalysis.sections.map((section) => (
                      <details className="source-analysis-section" key={section.topic_id} onToggle={(event) => { if (event.currentTarget.open) setActiveSectionId(section.topic_id) }}>
                        <summary><span>{section.topic}</span><ArrowRight aria-hidden="true" size={15} /></summary>
                        <div className="source-analysis-section-body">
                          <HighlightedText glossary={section.glossary} highlights={highlights} text={section.explanation} />
                          <ul className="analysis-key-points">{section.key_points.map((point, index) => <li key={`${index}-${point}`}><HighlightedText glossary={section.glossary} highlights={highlights} text={point} /></li>)}</ul>
                          {section.example && <div className="explanation-example"><h3><Lightbulb size={16} /> Example</h3><HighlightedText glossary={section.glossary} highlights={highlights} text={section.example} /></div>}
                          <div className="citation-list analysis-citations">{section.citations.map((citation, index) => <CitationChip citation={citation} key={`${section.topic_id}-${index}-${citation.source_id}`} onClick={() => citationClicked(citation)} />)}</div>
                          <div className="analysis-section-actions"><button className="button button-dark" onClick={() => openTopic(section)} type="button">Explain more</button><button className="button button-outline" onClick={() => takeSectionQuiz(section)} type="button">Take quiz on this</button></div>
                        </div>
                      </details>
                    ))}
                  </section>
                  <section className="explanation-citations"><span className="section-kicker">SOURCE REFERENCES</span><div className="citation-list">{currentAnalysis.citations.map((citation, index) => <CitationChip citation={citation} key={`${citation.source_id}-${index}-${citation.file_name}`} onClick={() => citationClicked(citation)} />)}</div></section>
                </article>
                <aside aria-label="Key terms" className="explain-key-terms"><span className="section-kicker">KEY TERMS</span><h3>{activeAnalysisSection?.topic ?? 'This source'}</h3>{activeGlossary.length ? <dl>{activeGlossary.map((entry) => <div key={entry.term}><dt>{entry.term}</dt><dd><HighlightedText glossary={activeGlossary} highlights={highlights} text={entry.definition} /></dd></div>)}</dl> : <p>Terms for this section will appear here.</p>}</aside>
              </div>
            ) : <div className="explain-state"><BookOpenCheck size={22} /><strong>Select a ready source</strong><p>StudyMate will explain each topic, then bring the ideas together.</p></div>}
          </div>
        ) : topicsLoading ? <LoadingStatus className="explain-content-loading" label="Preparing your topics…" /> : error ? (
          <div className="explain-state explain-error" role="alert"><TriangleAlert size={20} /><strong>Explanation unavailable</strong><p>{error}</p></div>
        ) : explanationLoading ? (
          <LoadingStatus className="explain-content-loading" label={`Preparing a ${level} explanation…`} />
        ) : explanation ? (
          <div className="analysis-content-layout">
            <article className="explanation-content">
              <HighlightedText className="explanation-summary" glossary={explanation.glossary} highlights={highlights} text={explanation.summary} />
              <section className="explanation-section"><h3><BookOpenCheck size={17} /> Key points</h3><ul className="explanation-points">{explanation.key_points.map((point, index) => <li key={`${index}-${point}`}><span>{String(index + 1).padStart(2, '0')}</span><p><HighlightedText glossary={explanation.glossary} highlights={highlights} text={point} /></p></li>)}</ul></section>
              <section className="explanation-example"><h3><Lightbulb size={17} /> Example</h3><HighlightedText glossary={explanation.glossary} highlights={highlights} text={explanation.example} /></section>
              {explanation.common_mistakes.length > 0 && <section className="explanation-mistakes"><h3><TriangleAlert size={17} /> Common mistakes</h3><ul>{explanation.common_mistakes.map((mistake) => <li key={mistake}><HighlightedText glossary={explanation.glossary} highlights={highlights} text={mistake} /></li>)}</ul></section>}
              <section className="explanation-check"><div><span className="section-kicker">QUICK CHECK</span><h3><CircleHelp size={17} /> <HighlightedText glossary={explanation.glossary} highlights={highlights} text={explanation.check_question} /></h3></div><button className="button button-dark" onClick={testTopic} type="button">Test me on this <ArrowRight size={15} /></button></section>
              <section className="explanation-citations"><span className="section-kicker">KEEP THE SOURCE CLOSE</span><div className="citation-list">{explanation.citations.map((citation) => <CitationChip citation={citation} key={`${citation.source_id}-${citation.n}-${citation.file_name}`} onClick={() => citationClicked(citation)} />)}</div></section>
            </article>
            <aside aria-label="Key terms" className="explain-key-terms"><span className="section-kicker">KEY TERMS</span><h3>{selectedTopic?.name}</h3>{explanation.glossary.length ? <dl>{explanation.glossary.map((entry) => <div key={entry.term}><dt>{entry.term}</dt><dd><HighlightedText glossary={explanation.glossary} highlights={highlights} text={entry.definition} /></dd></div>)}</dl> : <p>No glossary terms for this topic.</p>}</aside>
          </div>
        ) : (
          <div className="explain-state"><BookOpenCheck size={22} /><strong>Select a topic to begin</strong><p>Your explanation will stay grounded in the selected source passages.</p></div>
        )}
      </section>

      {selectedCitation && <div className="modal-backdrop" onMouseDown={(event) => event.target === event.currentTarget && setSelectedCitation(null)}><section aria-labelledby="explain-citation-title" aria-modal="true" className="citation-modal" role="dialog"><button aria-label="Close citation" className="modal-close-text" onClick={() => setSelectedCitation(null)} type="button">Close</button><span className="eyebrow">SOURCE PASSAGE</span><h2 id="explain-citation-title">{selectedCitation.file_name}</h2><p className="citation-location">{selectedCitation.source_type === 'slides' ? 'Slide' : selectedCitation.source_type === 'video' ? 'Video time' : 'Page'} {selectedCitation.slide ?? selectedCitation.page ?? `${Math.floor(selectedCitation.start ?? 0)} sec`}</p><blockquote><HighlightedText glossary={activeGlossary} highlights={highlights} highlightTerms={activeGlossary.map((entry) => entry.term)} text={selectedCitation.snippet} /></blockquote></section></div>}
      {videoCitation && <VideoModal citation={videoCitation} onClose={() => setVideoCitation(null)} url={videoUrl} />}
    </div>
  )
}