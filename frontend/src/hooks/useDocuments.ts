import { useCallback, useEffect, useState } from 'react'

import { api, type DocumentRow } from '@/lib/api'
import { supabase } from '@/lib/supabase'

function errorMessage(error: unknown): string {
  return error instanceof Error ? error.message : String(error)
}

/** Documents list kept live through Supabase Realtime (status changes arrive without polling). */
export function useDocuments(userId: string) {
  const [documents, setDocuments] = useState<DocumentRow[]>([])
  const [loadError, setLoadError] = useState<string | null>(null)

  // Replace by id only when the incoming row is not older: the POST response (pending)
  // can arrive after the Realtime UPDATE (processing). Compare parsed times: the API and Realtime
  // format timestamps differently ("Z" vs "+00:00"), so string order isn't time order.
  const upsert = useCallback((row: DocumentRow) => {
    setDocuments((current) => {
      const index = current.findIndex((d) => d.id === row.id)
      if (index === -1) return [row, ...current]
      if (Date.parse(row.updated_at) < Date.parse(current[index].updated_at)) return current
      return current.map((d, i) => (i === index ? row : d))
    })
  }, [])

  const remove = useCallback((id: string) => {
    setDocuments((current) => current.filter((d) => d.id !== id))
  }, [])

  useEffect(() => {
    let cancelled = false
    const reload = async () => {
      try {
        const rows = await api.listDocuments()
        if (!cancelled) {
          setDocuments(rows)
          setLoadError(null)
        }
      } catch (e) {
        if (!cancelled) setLoadError(errorMessage(e))
      }
    }

    // Subscribe first, then load, so no update is missed between the fetch and the subscription.
    // SUBSCRIBED also fires again after a reconnect, which refetches.
    const channel = supabase
      .channel(`documents-${userId}`)
      .on(
        'postgres_changes',
        { event: '*', schema: 'public', table: 'documents', filter: `user_id=eq.${userId}` },
        (payload) => {
          const row = (payload.eventType === 'DELETE' ? payload.old : payload.new) as Partial<DocumentRow>
          console.debug('[documents]', payload.eventType, row.id, row.status)
          if (payload.eventType === 'DELETE') {
            if (row.id) remove(row.id)
          } else {
            upsert(payload.new as DocumentRow)
          }
        },
      )
      .subscribe((status) => {
        if (status === 'SUBSCRIBED') void reload()
      })

    return () => {
      cancelled = true
      void supabase.removeChannel(channel)
    }
  }, [userId, upsert, remove])

  return { documents, loadError, upsert, remove }
}
