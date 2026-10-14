import { Component } from 'react'

export default class ErrorBoundary extends Component {
  state = { error: null }

  static getDerivedStateFromError(error) {
    return { error }
  }

  render() {
    if (this.state.error) {
      return (
        <section aria-live="assertive" className="route-error" role="alert">
          <span className="eyebrow">STUDYMATE</span>
          <h1>Something went wrong</h1>
          <p>{this.state.error.message || 'An unexpected error occurred.'}</p>
          <button className="button button-dark" onClick={() => window.history.back()} type="button">Go back</button>
        </section>
      )
    }
    return this.props.children
  }
}
