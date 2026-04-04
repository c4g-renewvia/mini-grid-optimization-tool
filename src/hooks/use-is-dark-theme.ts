'use client';

import { useTheme } from 'next-themes';

export function useIsDarkTheme() {
  const { theme, systemTheme } = useTheme();

  // This runs on every render, but it's extremely cheap
  // and avoids any state + effect entirely
  return theme === 'dark' || (theme === 'system' && systemTheme === 'dark');
}
