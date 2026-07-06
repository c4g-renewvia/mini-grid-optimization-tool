'use client';

import { useSession, signIn, signOut } from 'next-auth/react';
import { Button } from '@/components/ui/button';
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuTrigger,
  DropdownMenuSeparator,
} from '@/components/ui/dropdown-menu';
import { Avatar, AvatarFallback, AvatarImage } from '@/components/ui/avatar';
import { Bell, KeyRound, LogOut, UserCog } from 'lucide-react';
import { useState } from 'react';
import { useToast } from '@/hooks/use-toast';

import { EditProfileDialog } from '@/components/layout/edit-profile-dialog';
import { GoogleMapsApiKeyDialog } from '@/components/layout/google-maps-api-key-dialog';
import { NotificationSettings } from '@/components/layout/notification-settings';
import { ThemeSwitcher } from '@/components/layout/theme-switcher';

export function SidebarUserMenu() {
  const { data: session } = useSession();
  const { toast } = useToast();
  const [isEditProfileOpen, setIsEditProfileOpen] = useState(false);
  const [isNotificationSettingsOpen, setIsNotificationSettingsOpen] = useState(false);
  const [isMapsApiKeyOpen, setIsMapsApiKeyOpen] = useState(false);

  if (session?.user?.id === 'anonymous-user') {
    return <ThemeSwitcher />;
  }

  if (!session) {
    return (
      <Button
        onClick={() => signIn()}
        className="w-full rounded-full bg-emerald-600 hover:bg-emerald-700 text-white shadow-md transition-all active:scale-[0.8]"
      >
        Sign In
      </Button>
    );
  }

  const userInitials = session.user?.name
    ? session.user.name
        .split(' ')
        .map((n) => n[0])
        .join('')
        .toUpperCase()
    : '?';

  return (
    <>
      <DropdownMenu>
        <DropdownMenuTrigger asChild>
          <Button
            variant="ghost"
            className="w-full justify-start gap-3 px-4 py-4 h-auto hover:bg-zinc-100 dark:hover:bg-zinc-800 rounded-xl"
          >
            <Avatar className="h-9 w-9">
              <AvatarImage
                src={session.user?.image || undefined}
                alt={session.user?.name ?? ''}
              />
              <AvatarFallback className="bg-emerald-600 text-white">
                {userInitials}
              </AvatarFallback>
            </Avatar>

            <div className="flex flex-col items-start text-left">
              <div className="font-medium">{session.user?.name || 'User'}</div>
              <div className="text-xs text-zinc-500 dark:text-zinc-400">
                {session.user?.email}
              </div>
            </div>
          </Button>
        </DropdownMenuTrigger>

        <DropdownMenuContent className="w-64" align="end" forceMount>
          <DropdownMenuItem
            className="cursor-pointer"
            onSelect={() => setIsEditProfileOpen(true)}
          >
            <UserCog className="h-4 w-4 mr-2" />
            Edit Profile
          </DropdownMenuItem>

          <DropdownMenuItem
            className="cursor-pointer"
            onSelect={() => setIsNotificationSettingsOpen(true)}
          >
            <Bell className="h-4 w-4 mr-2" />
            Notifications
          </DropdownMenuItem>

          <DropdownMenuItem
            className="cursor-pointer"
            onSelect={() => setIsMapsApiKeyOpen(true)}
          >
            <KeyRound className="h-4 w-4 mr-2" />
            Google Maps API Key
          </DropdownMenuItem>

          <DropdownMenuSeparator />

          <DropdownMenuItem>
            <ThemeSwitcher />
          </DropdownMenuItem>

          <DropdownMenuSeparator />

          <DropdownMenuItem
            className="cursor-pointer text-red-600 focus:text-red-600"
            onSelect={() => {
              toast({
                title: 'Signed out',
                description: 'You have been successfully logged out.',
              });
              signOut({ callbackUrl: '/' });
            }}
          >
            <LogOut className="h-4 w-4 mr-2" />
            Sign out
          </DropdownMenuItem>
        </DropdownMenuContent>
      </DropdownMenu>

      <EditProfileDialog
        isOpen={isEditProfileOpen}
        onClose={() => setIsEditProfileOpen(false)}
      />
      <NotificationSettings
        isOpen={isNotificationSettingsOpen}
        onOpenChange={setIsNotificationSettingsOpen}
      />
      <GoogleMapsApiKeyDialog
        isOpen={isMapsApiKeyOpen}
        onOpenChangeAction={setIsMapsApiKeyOpen}
      />
    </>
  );
}