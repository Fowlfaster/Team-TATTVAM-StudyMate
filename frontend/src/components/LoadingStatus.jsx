export default function LoadingStatus({ label = 'Loading…', className = '' }) {
  const classes = ['loading-status', className].filter(Boolean).join(' ')

  return (
    <div aria-live="polite" className={classes} role="status">
      <span aria-hidden="true" className="loading-ring" />
      <span>{label}</span>
    </div>
  )
}