import { useState, type FormEvent } from 'react'
import { Navigate } from 'react-router'

import { Button } from '@/components/ui/button'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { Input } from '@/components/ui/input'
import { useAuth } from '@/context/AuthProvider'
import { supabase, supabaseConfigured } from '@/lib/supabase'

type Mode = 'sign-in' | 'sign-up'

export function LoginPage() {
  const { session, loading } = useAuth()
  const [mode, setMode] = useState<Mode>('sign-in')
  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [submitting, setSubmitting] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [notice, setNotice] = useState<string | null>(null)

  if (loading) return null
  if (session) return <Navigate to="/" replace />

  const handleSubmit = async (event: FormEvent) => {
    event.preventDefault()
    setSubmitting(true)
    setError(null)
    setNotice(null)
    const credentials = { email, password }
    const { data, error } =
      mode === 'sign-in'
        ? await supabase.auth.signInWithPassword(credentials)
        : await supabase.auth.signUp(credentials)
    if (error) setError(error.message)
    else if (mode === 'sign-up' && !data.session) {
      setNotice('Check your email to confirm your account, then sign in.')
    }
    setSubmitting(false)
  }

  const isSignIn = mode === 'sign-in'

  return (
    <div className="flex min-h-svh items-center justify-center bg-muted/40 p-4">
      <Card className="w-full max-w-sm">
        <CardHeader>
          <CardTitle>{isSignIn ? 'Sign in' : 'Create an account'}</CardTitle>
          <CardDescription>Agentic RAG Masterclass</CardDescription>
        </CardHeader>
        <CardContent>
          {!supabaseConfigured && (
            <p className="mb-4 rounded-md bg-destructive/10 p-3 text-sm text-destructive">
              Supabase is not configured. Copy <code>frontend/.env.example</code> to{' '}
              <code>frontend/.env</code> and fill in your project URL and anon key.
            </p>
          )}
          <form onSubmit={handleSubmit} className="flex flex-col gap-3">
            <Input
              type="email"
              placeholder="Email"
              autoComplete="email"
              required
              value={email}
              onChange={(e) => setEmail(e.target.value)}
            />
            <Input
              type="password"
              placeholder="Password"
              autoComplete={isSignIn ? 'current-password' : 'new-password'}
              required
              minLength={6}
              value={password}
              onChange={(e) => setPassword(e.target.value)}
            />
            {error && <p className="text-sm text-destructive">{error}</p>}
            {notice && <p className="text-sm text-muted-foreground">{notice}</p>}
            <Button type="submit" disabled={submitting}>
              {isSignIn ? 'Sign in' : 'Sign up'}
            </Button>
          </form>
          <button
            type="button"
            className="mt-4 w-full text-center text-sm text-muted-foreground hover:underline"
            onClick={() => {
              setMode(isSignIn ? 'sign-up' : 'sign-in')
              setError(null)
              setNotice(null)
            }}
          >
            {isSignIn ? "Don't have an account? Sign up" : 'Already have an account? Sign in'}
          </button>
        </CardContent>
      </Card>
    </div>
  )
}
