import { useState } from 'react'
import { Link, useNavigate } from 'react-router-dom'
import { getApiErrorMessage, setAuthToken, signup } from '../api'
import { useAuth } from '../components/auth-context'

export default function Signup() {
  const [name, setName] = useState('')
  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [error, setError] = useState('')
  const [busy, setBusy] = useState(false)
  const { setUser } = useAuth()
  const navigate = useNavigate()

  const submit = async (event) => {
    event.preventDefault()
    setBusy(true)
    setError('')
    try {
      const result = await signup(name, email, password)
      setAuthToken(result.token)
      setUser(result.user)
      navigate('/upload', { replace: true })
    } catch (requestError) {
      setError(getApiErrorMessage(requestError, 'Could not create your account. Please try again.'))
    } finally {
      setBusy(false)
    }
  }

  return (
    <section className="mx-auto w-full max-w-md py-10">
      <div className="rounded-lg border border-[#e2e5dc] bg-white p-7 shadow-sm sm:p-9">
        <p className="text-xs font-bold tracking-[0.12em] text-[#386951]">YOUR STUDY SPACE</p>
        <h1 className="mt-2 font-serif text-3xl text-[#29372f]">Create an account</h1>
        <form className="mt-7 space-y-5" onSubmit={submit}>
          <label className="block text-sm font-semibold text-[#405047]">
            Name
            <input autoComplete="name" className="mt-2 w-full rounded border border-[#dfe4da] px-3 py-2.5 text-sm outline-none focus:border-[#71917a]" onChange={(event) => setName(event.target.value)} required value={name} />
          </label>
          <label className="block text-sm font-semibold text-[#405047]">
            Email
            <input autoComplete="email" className="mt-2 w-full rounded border border-[#dfe4da] px-3 py-2.5 text-sm outline-none focus:border-[#71917a]" onChange={(event) => setEmail(event.target.value)} required type="email" value={email} />
          </label>
          <label className="block text-sm font-semibold text-[#405047]">
            Password
            <input autoComplete="new-password" className="mt-2 w-full rounded border border-[#dfe4da] px-3 py-2.5 text-sm outline-none focus:border-[#71917a]" minLength={6} onChange={(event) => setPassword(event.target.value)} required type="password" value={password} />
            <span className="mt-1 block text-xs font-normal text-[#777f76]">At least 6 characters</span>
          </label>
          {error && <p className="text-sm text-[#a33f34]" role="alert">{error}</p>}
          <button className="w-full rounded bg-[#284e3c] px-4 py-3 text-sm font-bold !text-white hover:bg-[#1d3e2d] disabled:opacity-50" disabled={busy} type="submit">{busy ? 'Creating account…' : 'Create account'}</button>
        </form>
        <p className="mt-6 text-center text-sm text-[#777f76]">Already registered? <Link className="font-semibold text-[#386951] underline" to="/login">Sign in</Link></p>
      </div>
    </section>
  )
}