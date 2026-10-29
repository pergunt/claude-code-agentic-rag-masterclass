import { createContext, useContext } from 'react'

// DOM element inside the sidebar where a page can portal its own content (ChatPage: thread list).
export const SidebarSlotContext = createContext<HTMLElement | null>(null)

export function useSidebarSlot(): HTMLElement | null {
  return useContext(SidebarSlotContext)
}
