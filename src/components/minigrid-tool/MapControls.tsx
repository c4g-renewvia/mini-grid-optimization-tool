'use client';

import React from 'react';

interface MapControlsProps {
  canUndo: boolean;
  canRedo: boolean;
  onUndo: () => void;
  onRedo: () => void;
  onReset: () => void;
  hasData: boolean;
}

export default function MapControls({
  canUndo,
  canRedo,
  onUndo,
  onRedo,
  onReset,
  hasData,
}: MapControlsProps) {
  return (
    <div className='fixed right-40 bottom-5 z-50 flex items-center gap-3'>
      {/* Undo Button */}
      <button
        onClick={onUndo}
        disabled={!canUndo}
        className='flex items-center gap-2 rounded-full bg-amber-600 px-5 py-3 text-sm font-medium text-white shadow-2xl transition-all hover:bg-amber-500 active:scale-95 disabled:cursor-not-allowed disabled:opacity-50'
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
        Undo
      </button>

      {/* Redo Button */}
      <button
        onClick={onRedo}
        disabled={!canRedo}
        className='flex items-center gap-2 rounded-full bg-amber-600 px-5 py-3 text-sm font-medium text-white shadow-2xl transition-all hover:bg-amber-500 active:scale-95 disabled:cursor-not-allowed disabled:opacity-50'
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
        Redo
      </button>

      {/* Reset Button */}
      <button
        onClick={onReset}
        disabled={!hasData}
        className='flex items-center gap-2 rounded-full bg-red-600 px-6 py-3 text-sm font-medium text-white shadow-2xl transition-all hover:bg-red-500 active:scale-95 disabled:opacity-50 dark:text-white'
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
        Reset
      </button>
    </div>
  );
}
