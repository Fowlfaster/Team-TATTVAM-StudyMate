import { lazy, Suspense, useEffect, useRef, useState } from 'react'
import { X } from 'lucide-react'
import LoadingStatus from './LoadingStatus'

const ReactPlayer = lazy(() => import('react-player'))

export default function VideoModal({ citation, url, onClose }) {
  const playerRef = useRef(null)
  const [videoLoading, setVideoLoading] = useState(true)
  const [videoError, setVideoError] = useState('')

  useEffect(() => {
    const closeOnEscape = (event) => {
      if (event.key === 'Escape') onClose()
    }
    window.addEventListener('keydown', closeOnEscape)
    return () => window.removeEventListener('keydown', closeOnEscape)
  }, [onClose])

  const seekToCitation = () => {
    setVideoLoading(false)
    if (citation?.start && playerRef.current) {
      playerRef.current.currentTime = citation.start
    }
  }

  return (
    <div className="modal-backdrop" onMouseDown={(event) => event.target === event.currentTarget && onClose()}>
      <section aria-labelledby="video-modal-title" aria-modal="true" className="video-modal" role="dialog">
        <header className="modal-header">
          <div>
            <span className="eyebrow">VIDEO SOURCE · {Math.floor(citation?.start ?? 0)} SEC</span>
            <h2 id="video-modal-title">{citation?.file_name}</h2>
          </div>
          <button aria-label="Close video" className="icon-button" onClick={onClose} type="button">
            <X size={19} />
          </button>
        </header>
        <div aria-busy={videoLoading} className="video-player-wrap">
          {videoError ? <p className="player-error" role="alert">{videoError}</p> : <>
            <Suspense fallback={<LoadingStatus className="player-loading" label="Loading video player…" />}>
              <ReactPlayer
                ref={playerRef}
                controls
                height="100%"
                onError={() => {
                  setVideoLoading(false)
                  setVideoError('This video could not be loaded. Check the source link and try again.')
                }}
                onReady={seekToCitation}
                playing
                src={url}
                width="100%"
              />
            </Suspense>
            {videoLoading && <LoadingStatus className="player-loading player-status" label="Loading video…" />}
          </>}
        </div>
        <p className="video-modal-caption">Started at {Math.floor(citation?.start ?? 0)} seconds from your cited passage.</p>
      </section>
    </div>
  )
}
