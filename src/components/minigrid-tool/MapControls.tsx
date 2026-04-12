'use client';

import React from 'react';

interface MapControlsProps {
  canUndo: boolean;
  canRedo: boolean;
  onUndo: () => void;
  onRedo: () => void;
  onLocalOptimize: () => void;
  onReset: () => void;
  hasData: boolean;
  sidebarOpen?: boolean;
  isOptimizing?: boolean;
}

export default function MapControls({
  canUndo,
  canRedo,
  onUndo,
  onRedo,
  onLocalOptimize,
  onReset,
  hasData,
  sidebarOpen = false,
  isOptimizing = false,
}: MapControlsProps) {
  return (
    <div
      className={`fixed bottom-5 left-4 z-50 flex flex-col gap-3 transition-all duration-300 md:right-40 md:bottom-5 md:left-auto md:flex-row md:items-center ${
        sidebarOpen ? 'hidden md:flex' : 'flex'
      }`}
    >
      {/* Local Optimize Button - Blue (now LEFTMOST) */}
      <button
        onClick={onLocalOptimize}
        disabled={!hasData || isOptimizing}
        className='flex w-full items-center justify-center gap-2 rounded-full bg-blue-600 px-6 py-3 text-sm font-medium text-white shadow-2xl transition-all hover:bg-blue-500 active:scale-95 disabled:cursor-not-allowed disabled:opacity-50 md:w-auto'
        title='Run local optimization to fine-tune pole positions'
      >
        {isOptimizing ? (
          <>
            <svg
              className='h-4 w-4 animate-spin'
              xmlns='http://www.w3.org/2000/svg'
              fill='none'
              viewBox='0 0 24 24'
            >
              <circle
                className='opacity-25'
                cx='12'
                cy='12'
                r='10'
                stroke='currentColor'
                strokeWidth='4'
              ></circle>
              <path
                className='opacity-75'
                fill='currentColor'
                d='M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z'
              ></path>
            </svg>
            <span>Optimizing...</span>
          </>
        ) : (
          <>
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
                d='M14.752 11.168l-3.197-2.132A1 1 0 0010 9.87v4.263a1 1 0 001.555.832l3.197-2.132z'
              />
              <path
                strokeLinecap='round'
                strokeLinejoin='round'
                d='M21 12a9 9 0 01-9 9m9-9a9 9 0 00-9-9m9 9H3m9 4.01V8'
              />
            </svg>
            <span>Local Optimization</span>
          </>
        )}
      </button>

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
