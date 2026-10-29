import type { Session } from '@supabase/supabase-js'
import { createContext, useContext, useEffect, useState, type ReactNode } from 'react'

import { api } from '@/lib/api'
import { supabase } from '@/lib/supabase'

type AuthContextValue = {
  session: Session | null
  loading: boolean
  isAdmin: boolean
  signOut: () => Promise<void>
}

const AuthContext = createContext<AuthContextValue | null>(null)

export function AuthProvider({ children }: { children: ReactNode }) {
  const [session, setSession] = useState<Session | null>(null)
  const [loading, setLoading] = useState(true)
  const [adminFor, setAdminFor] = useState<string | null>(null)
  const userId = session?.user.id

  useEffect(() => {
    supabase.auth.getSession().then(({ data }) => {
      setSession(data.session)
      setLoading(false)
    })
    const { data } = supabase.auth.onAuthStateChange((_event, nextSession) => {
      setSession(nextSession)
    })
    return () => data.subscription.unsubscribe()
  }, [])

  // Fetched once per signed-in user; false until loaded or on error.
  useEffect(() => {
    if (!userId) return
    let cancelled = false
    api
      .me()
      .then((me) => {
        if (!cancelled && me.is_admin === true) setAdminFor(userId)
      })
      .catch(() => {})
    return () => {
      cancelled = true
    }
  }, [userId])

  const isAdmin = !!userId && adminFor === userId

  const signOut = async () => {
    await supabase.auth.signOut()
  }

  return <AuthContext value={{ session, loading, isAdmin, signOut }}>{children}</AuthContext>
}

export function useAuth(): AuthContextValue {
  const context = useContext(AuthContext)
  if (!context) throw new Error('useAuth must be used inside AuthProvider')
  return context
}
