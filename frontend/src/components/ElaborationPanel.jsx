import { useState } from 'react'
import { LoaderCircle } from 'lucide-react'
import { elaborateExplanation, getApiErrorMessage } from '../api'
import RichExplanation from './RichExplanation'

export default function ElaborationPanel({
  subjectId,
  sourceId = null,
  topicIds = [],
  topicId = null,
  baseExplanation,
  focus,
}) {
  const [additions, setAdditions] = useState([])
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState('')

  const elaborate = async () => {
    if (!subjectId || loading || additions.length >= 3) return
    setLoading(true)
    setError('')
    try {
      const previousExplanation = [baseExplanation, ...additions.map((item) => item.html)]
        .filter(Boolean)
        .join('\n')
      const result = await elaborateExplanation({
        subjectId: Number(subjectId),
        sourceId,
        topicIds,
        topicId,
        previousExplanation,
        depth: additions.length + 1,
        focus,
      })
      if (!result.html?.trim()) throw new Error('No elaboration was returned. Please try again.')
      setAdditions((current) => [...current, result])
    } catch (requestError) {
      setError(getApiErrorMessage(requestError, requestError.message || 'Could not elaborate further.'))
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="elaboration-panel">
      <button
        className="button button-outline elaborate-button"
        disabled={loading || additions.length >= 3}
        onClick={elaborate}
        type="button"
      >
        <LoaderCircle aria-hidden="true" className={loading ? 'animate-spin' : ''} size={15} />
        {loading ? 'Elaborating…' : 'Elaborate further'}
      </button>
      {error && <p className="inline-message message-error" role="alert">{error}</p>}
      {additions.map((item, index) => (
        <article className="elaboration-addition" key={`${index}-${item.depth}`}>
          <span className="section-kicker">LEVEL {item.depth}</span>
          {item.key_points?.length > 0 && <section className="explanation-key-points">
            <h3>New key points</h3>
            <ul>{item.key_points.map((point, pointIndex) => <li key={`${pointIndex}-${point}`}>{point}</li>)}</ul>
          </section>}
          <RichExplanation html={item.html} />
        </article>
      ))}
    </div>
  )
}
