import { Navigate, Route, Routes, useLocation } from 'react-router-dom'
import './App.css'
import { useAuth } from './useAuth.js'
import LoginPage from './pages/Login/LoginPage.jsx'
import DashboardPage from './pages/Dashboard/DashboardPage.jsx'
import CreateExceptionPage from './pages/CreateException/CreateExceptionPage.jsx'
import AuditLogPage from './pages/AuditLog/AuditLogPage.jsx'

function getDashboardViewForUser(user) {
  const groups = user?.groups || []

  if (groups.includes('Security')) return 'security'
  if (groups.includes('Approver')) return 'approver'
  if (groups.includes('RiskOwner')) return 'risk-owner'
  if (groups.includes('Requestor')) return 'requestor'

  return 'requestor'
}

function getDashboardPathForUser(user) {
  return `/dashboard/${getDashboardViewForUser(user)}`
}

function ProtectedRoute({ children }) {
  const { user, loading } = useAuth()

  if (loading) {
    return <div className="centered">Loading...</div>
  }

  if (!user) {
    return <Navigate to="/login" replace />
  }

  return children
}

function RoleLanding() {
  const { user, loading } = useAuth()
  const location = useLocation()

  if (loading) {
    return <div className="centered">Loading...</div>
  }

  if (!user) {
    return <Navigate to="/login" replace />
  }

  return <Navigate to={getDashboardPathForUser(user)} replace state={location.state} />
}

function App() {
  return (
    <Routes>
      <Route path="/login" element={<LoginPage />} />
      <Route path="/" element={<RoleLanding />} />
      <Route
        path="/dashboard/requestor"
        element={
          <ProtectedRoute>
            <DashboardPage view="requestor" />
          </ProtectedRoute>
        }
      />
      <Route
        path="/dashboard/approver"
        element={
          <ProtectedRoute>
            <DashboardPage view="approver" />
          </ProtectedRoute>
        }
      />
      <Route
        path="/dashboard/risk-owner"
        element={
          <ProtectedRoute>
            <DashboardPage view="risk-owner" />
          </ProtectedRoute>
        }
      />
      <Route
        path="/dashboard/security"
        element={
          <ProtectedRoute>
            <DashboardPage view="security" />
          </ProtectedRoute>
        }
      />
      <Route
        path="/exceptions/new"
        element={
          <ProtectedRoute>
            <CreateExceptionPage />
          </ProtectedRoute>
        }
      />
      <Route
        path="/audit-log"
        element={
          <ProtectedRoute>
            <AuditLogPage />
          </ProtectedRoute>
        }
      />
      <Route path="*" element={<Navigate to="/" replace />} />
    </Routes>
  )
}

export default App