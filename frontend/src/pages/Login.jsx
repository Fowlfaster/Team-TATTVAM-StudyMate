import { useState } from 'react'
import { Link, useLocation, useNavigate } from 'react-router-dom'
import { DEMO_EMAIL, DEMO_PASSWORD, getApiErrorMessage, login, setAuthToken } from '../api'
import { useAuth } from '../components/auth-context'

export default function Login() {
  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [error, setError] = useState('')
  const [busy, setBusy] = useState(false)
  const { setUser } = useAuth()
  const navigate = useNavigate()
  const location = useLocation()

  const submit = async (event) => {
    event.preventDefault()
    setBusy(true)
    setError('')
    try {
      const result = await login(email, password)
      setAuthToken(result.token)
      setUser(result.user)
      navigate(location.state?.from?.pathname || '/upload', { replace: true })
    } catch (requestError) {
      setError(getApiErrorMessage(requestError, 'Could not sign in. Check your details and try again.'))
    } finally {
      setBusy(false)
    }
  }

  const useDemoAccount = async () => {
    setBusy(true)
    setError('')
    try {
      const result = await login(DEMO_EMAIL, DEMO_PASSWORD)
      setAuthToken(result.token)
      setUser(result.user)
      navigate('/explain', { replace: true })
    } catch (requestError) {
      setError(getApiErrorMessage(requestError, 'Could not sign in with the demo account.'))
    } finally {
      setBusy(false)
    }
  }

  return (
    <section className="mx-auto w-full max-w-md py-10">
      <div className="rounded-lg border border-[#e2e5dc] bg-white p-7 shadow-sm sm:p-9">
        <p className="text-xs font-bold tracking-[0.12em] text-[#386951]">WELCOME BACK</p>
        <h1 className="mt-2 font-serif text-3xl text-[#29372f]">Sign in to StudyMate</h1>
        <form className="mt-7 space-y-5" onSubmit={submit}>
          <label className="block text-sm font-semibold text-[#405047]">
            Email
            <input autoComplete="email" className="mt-2 w-full rounded border border-[#dfe4da] px-3 py-2.5 text-sm outline-none focus:border-[#71917a]" onChange={(event) => setEmail(event.target.value)} required type="email" value={email} />
          </label>
          <label className="block text-sm font-semibold text-[#405047]">
            Password
            <input autoComplete="current-password" className="mt-2 w-full rounded border border-[#dfe4da] px-3 py-2.5 text-sm outline-none focus:border-[#71917a]" onChange={(event) => setPassword(event.target.value)} required type="password" value={password} />
          </label>
          {error && <p className="text-sm text-[#a33f34]" role="alert">{error}</p>}
          <button className="w-full rounded bg-[#284e3c] px-4 py-3 text-sm font-bold !text-white hover:bg-[#1d3e2d] disabled:opacity-50" disabled={busy} type="submit">{busy ? 'Signing in…' : 'Sign in'}</button>
          <button className="w-full rounded border border-[#cfd5cf] bg-[#f6f8f4] px-4 py-3 text-sm font-bold text-[#2d4d3f] hover:bg-[#edf2ea] disabled:opacity-50" disabled={busy} onClick={useDemoAccount} type="button">Try demo account</button>
        </form>
        <p className="mt-6 text-center text-sm text-[#777f76]">New to StudyMate? <Link className="font-semibold text-[#386951] underline" to="/signup">Create an account</Link></p>
      </div>
    </section>
  )
}