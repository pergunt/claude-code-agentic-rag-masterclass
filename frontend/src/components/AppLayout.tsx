import { Outlet } from 'react-router'

import { AppHeader } from '@/components/AppHeader'

export function AppLayout() {
  return (
    <div className="flex h-svh flex-col">
      <AppHeader />
      <div className="min-h-0 flex-1">
        <Outlet />
      </div>
    </div>
  )
}
