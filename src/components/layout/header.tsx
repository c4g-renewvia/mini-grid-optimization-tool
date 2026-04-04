'use client';

import Image from 'next/image';
import Link from 'next/link';
import { useSession } from 'next-auth/react';
import { useState } from 'react';
import { Menu, X } from 'lucide-react'; // ← Install lucide-react if you don't have it
import { UserMenu } from './user-menu';

export function Header() {
  const { data, status } = useSession();
  const [isMobileMenuOpen, setIsMobileMenuOpen] = useState(false);

  const toggleMobileMenu = () => setIsMobileMenuOpen(!isMobileMenuOpen);

  return (
    <header className='bg-background fixed top-0 right-0 left-0 z-50 border-b px-4 py-4 md:px-6'>
      <div className='flex items-center justify-between'>
        {/* Logo + Brand */}
        <div className='flex items-center gap-3'>
          <Link href='/' className='flex items-center gap-2'>
            <Image
              src='/c4g-logo.png'
              alt='Computing for Good'
              width={32}
              height={32}
            />
          </Link>
        </div>

        {/* Desktop Navigation */}
        <div className='hidden items-center gap-8 lg:flex'>

          {status === 'authenticated' && data?.user.role === 'ADMIN' && (
            <Link
              href='/users'
              className='hover:text-primary text-sm font-medium transition-colors'
            >
              Users
            </Link>
          )}
        </div>

        {/* Right Side: User Menu + Hamburger */}
        <div className='flex items-center gap-3'>
          <UserMenu />

          {/* Hamburger Button - Visible only on mobile */}
          <button
            onClick={toggleMobileMenu}
            className='rounded-lg p-2 transition-colors hover:bg-zinc-200 lg:hidden dark:hover:bg-zinc-800'
            aria-label='Toggle menu'
          >
            {isMobileMenuOpen ? (
              <X className='h-6 w-6' />
            ) : (
              <Menu className='h-6 w-6' />
            )}
          </button>
        </div>
      </div>

      {/* Mobile Menu Dropdown */}
      {isMobileMenuOpen && (
        <div className='bg-background mt-4 border-t pt-4 lg:hidden'>
          <div className='flex flex-col gap-4 px-2'>

            {status === 'authenticated' && data?.user.role === 'ADMIN' && (
              <Link
                href='/users'
                className='hover:text-primary rounded-lg px-3 py-2 text-sm font-medium transition-colors hover:bg-zinc-100 dark:hover:bg-zinc-800'
                onClick={() => setIsMobileMenuOpen(false)}
              >
                Users
              </Link>
            )}
          </div>
        </div>
      )}
    </header>
  );
}
