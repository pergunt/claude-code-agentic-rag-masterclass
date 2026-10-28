import type { ReactNode } from 'react'
import { Navigate } from 'react-router'

import { useAuth } from '@/context/AuthProvider'

export function ProtectedRoute({ children }: { children: ReactNode }) {
  const { session, loading } = useAuth()
  if (loading) return null
  if (!session) return <Navigate to="/login" replace />
  return children
}
