import { lazy, Suspense } from 'react'
import { BrowserRouter, NavLink, Navigate, Route, Routes, useLocation, useNavigate } from 'react-router-dom'
import { BookOpenCheck, ChartNoAxesColumnIncreasing, CircleHelp, LogOut, MessagesSquare, Upload } from 'lucide-react'
import { AuthProvider } from './components/AuthContext'
import { useAuth } from './components/auth-context'
import LoadingStatus from './components/LoadingStatus'
import Logo from './components/Logo'
import ProtectedRoute from './components/ProtectedRoute'
import ErrorBoundary from './components/ErrorBoundary'
import './App.css'

const Chat = lazy(() => import('./pages/Chat'))
const Dashboard = lazy(() => import('./pages/Dashboard'))
const Quiz = lazy(() => import('./pages/Quiz'))
const UploadPage = lazy(() => import('./pages/Upload'))
const Login = lazy(() => import('./pages/Login'))
const Signup = lazy(() => import('./pages/Signup'))
const Home = lazy(() => import('./pages/Home'))
const Explain = lazy(() => import('./pages/ExplainModes'))
const Evaluate = lazy(() => import('./pages/Evaluate'))
const Ranking = lazy(() => import('./pages/Ranking'))

const navigation = [
  { label: 'Upload', to: '/upload', icon: Upload },
  { label: 'Explain', to: '/explain', icon: BookOpenCheck },
  { label: 'Chat', to: '/chat', icon: MessagesSquare },
  { label: 'Quiz', to: '/quiz', icon: CircleHelp },
  { label: 'Dashboard', to: '/dashboard', icon: ChartNoAxesColumnIncreasing },
]

function AppShell() {
  const { user, logout, loading } = useAuth()
  const location = useLocation()
  const navigate = useNavigate()
  const authPage = ['/login', '/signup'].includes(location.pathname)
  const publicHome = location.pathname === '/'

  const signOut = () => {
    logout()
    navigate('/login', { replace: true })
  }

  return (
    <div className="app-frame">
      {!publicHome && <header className="topbar">
        <NavLink aria-label="StudyMate home" className="brand-lockup" to={user ? '/dashboard' : '/'}>
          <Logo className="brand-logo" />
        </NavLink>
        {!authPage && <nav aria-label="Main navigation" className="main-nav">
          {navigation.map(({ label, to, icon: Icon }) => (
            <NavLink className={({ isActive }) => `nav-link${isActive ? ' nav-link-active' : ''}`} key={to} to={to}>
              <Icon size={16} strokeWidth={1.9} /><span>{label}</span>
            </NavLink>
          ))}
        </nav>}
        {!authPage && <div className="profile-mark">
          {user ? <><span title={user.name}>{user.name}</span><button aria-label="Log out" className="flex items-center gap-1 rounded px-2 py-1 text-xs font-semibold text-[#56665a] hover:bg-[#f0f1e9]" onClick={signOut} type="button"><LogOut size={14} /> Logout</button></> : <NavLink className="text-xs font-semibold text-[#386951]" to="/login">Sign in</NavLink>}
        </div>}
      </header>}
      <main className={publicHome ? 'public-home-main' : `main-content${authPage ? ' auth-page-content' : ''}`}>
        <ErrorBoundary>
        <Suspense fallback={<LoadingStatus className="route-loading" label="Opening your study space…" />}>
          <Routes>
            <Route element={loading ? <LoadingStatus className="route-loading" label="Checking your account…" /> : user ? <Navigate replace to="/dashboard" /> : <Home />} path="/" />
            <Route element={<Login />} path="/login" />
            <Route element={<Signup />} path="/signup" />
            <Route element={<ProtectedRoute><UploadPage /></ProtectedRoute>} path="/upload" />
            <Route element={<ProtectedRoute><Explain /></ProtectedRoute>} path="/explain" />
            <Route element={<ProtectedRoute><Evaluate /></ProtectedRoute>} path="/evaluate" />
            <Route element={<ProtectedRoute><Ranking /></ProtectedRoute>} path="/ranking" />
            <Route element={<ProtectedRoute><Chat /></ProtectedRoute>} path="/chat" />
            <Route element={<ProtectedRoute><Quiz /></ProtectedRoute>} path="/quiz" />
            <Route element={<ProtectedRoute><Dashboard /></ProtectedRoute>} path="/dashboard" />
            <Route element={<Navigate replace to="/upload" />} path="*" />
          </Routes>
        </Suspense>
        </ErrorBoundary>
      </main>
      {!authPage && !publicHome && <footer className="app-footer"><span>STUDYMATE AI</span><span>Learn it. Keep it. Own it.</span><span>PERSONAL LEARNING SPACE</span></footer>}
    </div>
  )
}

export default function App() {
  return <BrowserRouter><AuthProvider><AppShell /></AuthProvider></BrowserRouter>
}
