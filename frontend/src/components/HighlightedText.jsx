import { Fragment } from 'react'

function cleanMarkers(value) {
  return value.replace(/\[\[|\]\]|\{\{|\}\}/g, '')
}

function escapeRegExp(value) {
  return value.replace(/[.*+?^${}()|[\]\\]/g, '\\$&')
}

export default function HighlightedText({
  text = '',
  glossary = [],
  highlightTerms = [],
  highlights = true,
  className = '',
}) {
  const glossaryMap = new Map(
    glossary
      .filter((entry) => entry?.term)
      .map((entry) => [entry.term.trim().toLocaleLowerCase(), entry.definition ?? '']),
  )
  const extraTerms = [...new Set([
    ...highlightTerms,
    ...glossary.map((entry) => entry?.term).filter(Boolean),
  ].map((term) => String(term).trim()).filter((term) => term.length > 1))]
    .sort((left, right) => right.length - left.length)

  const renderPlain = (value, prefix) => {
    const safeText = cleanMarkers(value)
    if (!highlights || extraTerms.length === 0) return safeText
    const pattern = new RegExp(`(${extraTerms.map(escapeRegExp).join('|')})`, 'gi')
    return safeText.split(pattern).map((part, index) => {
      const definition = glossaryMap.get(part.toLocaleLowerCase())
      if (definition === undefined && !extraTerms.some((term) => term.toLocaleLowerCase() === part.toLocaleLowerCase())) {
        return <Fragment key={`${prefix}-${index}`}>{part}</Fragment>
      }
      return <strong className="highlight-keyword highlight-keyword-context" key={`${prefix}-${index}`} title={definition || undefined}>{part}</strong>
    })
  }

  const nodes = []
  const markers = /\[\[([\s\S]+?)\]\]|\{\{([\s\S]+?)\}\}/g
  let cursor = 0
  let match
  let markerIndex = 0
  while ((match = markers.exec(text)) !== null) {
    if (match.index > cursor) {
      nodes.push(...[].concat(renderPlain(text.slice(cursor, match.index), `plain-${markerIndex}`)))
    }
    const keyword = match[1]
    const keySentence = match[2]
    if (keyword !== undefined) {
      const term = keyword.trim()
      const definition = glossaryMap.get(term.toLocaleLowerCase())
      nodes.push(highlights
        ? <strong className="highlight-keyword" key={`keyword-${markerIndex}`} title={definition || undefined}>{term}</strong>
        : <Fragment key={`keyword-${markerIndex}`}>{term}</Fragment>)
    } else {
      nodes.push(highlights
        ? <mark className="highlight-key-sentence" key={`sentence-${markerIndex}`}>{renderPlain(keySentence, `sentence-${markerIndex}`)}</mark>
        : <Fragment key={`sentence-${markerIndex}`}>{cleanMarkers(keySentence)}</Fragment>)
    }
    cursor = markers.lastIndex
    markerIndex += 1
  }
  if (cursor < text.length) {
    nodes.push(...[].concat(renderPlain(text.slice(cursor), `plain-${markerIndex}`)))
  }
  return <span className={`highlighted-text ${className}`.trim()}>{nodes}</span>
}
