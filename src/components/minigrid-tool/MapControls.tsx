'use client';

import React from 'react';

interface MapControlsProps {
  canUndo: boolean;
  canRedo: boolean;
  onUndo: () => void;
  onRedo: () => void;
  onReset: () => void;
  hasData: boolean;
  sidebarOpen?: boolean; // ← Changed to optional (with ?)
}

export default function MapControls({
  canUndo,
  canRedo,
  onUndo,
  onRedo,
  onReset,
  hasData,
  sidebarOpen = false, // ← Default value
}: MapControlsProps) {
  return (
    <div
      className={`fixed bottom-5 left-4 z-50 flex flex-col gap-3 transition-all duration-300 md:right-40 md:bottom-5 md:left-auto md:flex-row md:items-center ${sidebarOpen ? 'hidden md:flex' : 'flex'} `}
    >
      {/* Undo Button */}
      <button
        onClick={onUndo}
        disabled={!canUndo}
        className='flex w-full items-center justify-center gap-2 rounded-full bg-amber-600 px-5 py-3 text-sm font-medium text-white shadow-2xl transition-all hover:bg-amber-500 active:scale-95 disabled:cursor-not-allowed disabled:opacity-50 md:w-auto'
        title='Undo (Ctrl/Cmd + Z)'
      >
        <svg
          xmlns='http://www.w3.org/2000/svg'
          className='h-4 w-4'
          fill='none'
          viewBox='0 0 24 24'
          stroke='currentColor'
          strokeWidth={2.5}
        >
          <path
            strokeLinecap='round'
            strokeLinejoin='round'
            d='M3 10h10a8 8 0 018 8v2M3 10l6 6 6-6'
          />
        </svg>
        <span>Undo</span>
      </button>

      {/* Redo Button */}
      <button
        onClick={onRedo}
        disabled={!canRedo}
        className='flex w-full items-center justify-center gap-2 rounded-full bg-amber-600 px-5 py-3 text-sm font-medium text-white shadow-2xl transition-all hover:bg-amber-500 active:scale-95 disabled:cursor-not-allowed disabled:opacity-50 md:w-auto'
        title='Redo (Ctrl/Cmd + Shift + Z)'
      >
        <svg
          xmlns='http://www.w3.org/2000/svg'
          className='h-4 w-4'
          fill='none'
          viewBox='0 0 24 24'
          stroke='currentColor'
          strokeWidth={2.5}
        >
          <path
            strokeLinecap='round'
            strokeLinejoin='round'
            d='M21 10h-10a8 8 0 00-8 8v2m18-10l-6 6-6-6'
          />
        </svg>
        <span>Redo</span>
      </button>

      {/* Reset Button */}
      <button
        onClick={onReset}
        disabled={!hasData}
        className='flex w-full items-center justify-center gap-2 rounded-full bg-red-600 px-6 py-3 text-sm font-medium text-white shadow-2xl transition-all hover:bg-red-500 active:scale-95 disabled:opacity-50 md:w-auto dark:text-white'
        title='Reset everything'
      >
        <svg
          xmlns='http://www.w3.org/2000/svg'
          className='h-4 w-4'
          fill='none'
          stroke='currentColor'
          viewBox='0 0 24 24'
          strokeWidth={2.5}
        >
          <path
            strokeLinecap='round'
            strokeLinejoin='round'
            d='M4 4v5h.582m15.356 2A8.001 8.001 0 004.582 9m0 0H9m11 11v-5h-.581m0 0a8.003 8.003 0 01-15.357-2m15.357 2H15'
          />
        </svg>
        <span>Reset</span>
      </button>
    </div>
  );
}
