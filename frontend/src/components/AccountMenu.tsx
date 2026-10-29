import { LogOut, Settings } from 'lucide-react'
import { useState } from 'react'

import { SettingsDialog } from '@/components/settings/SettingsDialog'
import { Button } from '@/components/ui/button'
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuLabel,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from '@/components/ui/dropdown-menu'
import { useAuth } from '@/context/AuthProvider'

// Local part split on . _ + -, first letter of the first two parts, uppercased.
function initialsFor(email: string): string {
  const local = email.split('@')[0] ?? ''
  const parts = local.split(/[._+-]/).filter(Boolean)
  const letters = parts.slice(0, 2).map((p) => p[0])
  return (letters.join('') || '?').toUpperCase()
}

export function AccountMenu() {
  const { session, isAdmin, signOut } = useAuth()
  const [settingsOpen, setSettingsOpen] = useState(false)
  const email = session?.user.email ?? ''

  return (
    <>
      <DropdownMenu>
        <DropdownMenuTrigger asChild>
          <Button
            variant="ghost"
            className="h-auto w-full justify-start gap-2 px-2 py-2"
            aria-label="Account menu"
          >
            <span className="flex size-8 shrink-0 items-center justify-center rounded-full bg-primary text-xs font-medium text-primary-foreground">
              {initialsFor(email)}
            </span>
            <span className="truncate text-sm font-normal">{email}</span>
          </Button>
        </DropdownMenuTrigger>
        <DropdownMenuContent side="top" align="start" className="w-56">
          <DropdownMenuLabel className="truncate font-normal text-muted-foreground">
            {email}
          </DropdownMenuLabel>
          {isAdmin && (
            <DropdownMenuItem onSelect={() => setSettingsOpen(true)}>
              <Settings /> Settings
            </DropdownMenuItem>
          )}
          <DropdownMenuSeparator />
          <DropdownMenuItem onSelect={() => void signOut()}>
            <LogOut /> Sign out
          </DropdownMenuItem>
        </DropdownMenuContent>
      </DropdownMenu>
      {isAdmin && <SettingsDialog open={settingsOpen} onOpenChange={setSettingsOpen} />}
    </>
  )
}
