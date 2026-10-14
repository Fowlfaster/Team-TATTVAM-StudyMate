import { useEffect, useState } from 'react'
import { clearAuthToken, getAuthToken, getCurrentUser } from '../api'
import { AuthContext } from './auth-context'

export function AuthProvider({ children }) {
  const [user, setUser] = useState(null)
  const [loading, setLoading] = useState(Boolean(getAuthToken()))

  useEffect(() => {
    if (!getAuthToken()) return
    let active = true
    getCurrentUser()
      .then((currentUser) => { if (active) setUser(currentUser) })
      .catch(() => { if (active) { clearAuthToken(); setUser(null) } })
      .finally(() => { if (active) setLoading(false) })
    return () => { active = false }
  }, [])

  const logout = () => {
    clearAuthToken()
    setUser(null)
  }

  return (
    <AuthContext.Provider value={{ user, setUser, logout, loading }}>
      {children}
    </AuthContext.Provider>
  )
}