import { FileText, Play, Presentation } from 'lucide-react'

function formatTime(seconds = 0) {
  const totalSeconds = Math.max(0, Math.floor(seconds))
  const hours = Math.floor(totalSeconds / 3600)
  const minutes = Math.floor((totalSeconds % 3600) / 60)
  const remainder = totalSeconds % 60
  return [hours, minutes, remainder].map((part) => String(part).padStart(2, '0')).join(':')
}

export default function CitationChip({ citation, onClick }) {
  const isVideo = citation.source_type === 'video'
  const isSlides = citation.source_type === 'slides'
  const Icon = isVideo ? Play : isSlides ? Presentation : FileText
  const location = isVideo
    ? formatTime(citation.start)
    : isSlides
      ? `Slide ${citation.slide ?? '—'}`
      : `Page ${citation.page ?? '—'}`

  return (
    <button
      className={`citation-chip ${isVideo ? 'citation-chip-video' : ''}`}
      onClick={onClick}
      title={`Open ${citation.file_name}, ${location}`}
      type="button"
    >
      <Icon size={13} strokeWidth={2.1} />
      <span className="citation-chip-name">{citation.file_name}</span>
      <span className="citation-chip-location">{location}</span>
    </button>
  )
}
