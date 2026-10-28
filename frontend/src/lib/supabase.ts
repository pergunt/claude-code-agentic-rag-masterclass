import { createClient } from '@supabase/supabase-js'

const url = import.meta.env.VITE_SUPABASE_URL
const anonKey = import.meta.env.VITE_SUPABASE_ANON_KEY

export const supabaseConfigured = Boolean(url && anonKey)

// Placeholders keep the app rendering (with a warning on the login page) when .env is missing.
export const supabase = createClient(url || 'http://localhost:54321', anonKey || 'missing-anon-key')
