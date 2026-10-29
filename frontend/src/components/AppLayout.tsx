import { useState } from 'react'
import { Outlet } from 'react-router'

import { AppSidebar } from '@/components/AppSidebar'
import { SidebarSlotContext } from '@/components/sidebar-slot'

export function AppLayout() {
  const [slot, setSlot] = useState<HTMLElement | null>(null)

  return (
    <SidebarSlotContext value={slot}>
      <div className="flex h-svh">
        <AppSidebar slotRef={setSlot} />
        <div className="min-h-0 min-w-0 flex-1">
          <Outlet />
        </div>
      </div>
    </SidebarSlotContext>
  )
}
