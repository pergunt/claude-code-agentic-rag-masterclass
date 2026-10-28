import type { ReactNode } from 'react'
import { Navigate, useLocation } from 'react-router'

import { useAuth } from '@/context/AuthProvider'

export function ProtectedRoute({ children }: { children: ReactNode }) {
  const { session, loading } = useAuth()
  const location = useLocation()
  if (loading) return null
  if (!session) return <Navigate to="/login" replace state={{ from: location }} />
  return children
}
