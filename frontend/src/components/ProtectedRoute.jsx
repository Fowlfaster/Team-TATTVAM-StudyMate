import { Navigate, useLocation } from 'react-router-dom'
import LoadingStatus from './LoadingStatus'
import { useAuth } from './auth-context'

export default function ProtectedRoute({ children }) {
  const { user, loading } = useAuth()
  const location = useLocation()

  if (loading) return <LoadingStatus className="route-loading" label="Checking your account…" />
  if (!user) return <Navigate replace state={{ from: location }} to="/login" />
  return children
}