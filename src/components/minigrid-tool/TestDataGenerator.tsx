'use client';

import React from 'react';

interface TestDataGeneratorProps {
  selectedCount: number;
  onCountChange: (_count: number) => void;
  onGenerate: () => void;
  loading: boolean;
  error?: string | null;
}

export default function TestDataGenerator({
  selectedCount,
  onCountChange,
  onGenerate,
  loading,
  error,
}: TestDataGeneratorProps) {
  return (
    <div className='rounded-xl border border-zinc-200 bg-white p-6 backdrop-blur-sm dark:border-zinc-700 dark:bg-zinc-900/50'>
      <h3 className='mb-3 text-lg font-semibold text-zinc-900 dark:text-white'>
        Generate Test Data
      </h3>
      <p className='mb-4 text-sm leading-snug text-zinc-600 dark:text-zinc-400'>
        Random points in ~1 mi² area – good for quick testing
      </p>

      <div className='flex flex-wrap items-center gap-4'>
        <select
          value={selectedCount}
          onChange={(e) => onCountChange(Number(e.target.value))}
          className='min-w-[140px] rounded-lg border border-zinc-200 bg-white px-4 py-2.5 text-sm text-zinc-900 transition focus:border-emerald-500 focus:ring-2 focus:ring-emerald-500/20 dark:border-zinc-700 dark:bg-zinc-800 dark:text-white'
          disabled={loading}
        >
          {Array.from({ length: 91 }, (_, i) => i + 10).map((n) => (
            <option key={n} value={n}>
              {n} points
            </option>
          ))}
        </select>

        <button
          onClick={onGenerate}
          disabled={loading}
          className={`rounded-lg px-6 py-2.5 text-sm font-medium transition-all ${
            loading
              ? 'cursor-wait bg-blue-600/70 text-white'
              : 'bg-blue-600 text-white shadow-sm hover:bg-blue-700 active:scale-97'
          }`}
        >
          {loading ? (
            <span className='flex items-center gap-2'>
              <svg className='h-4 w-4 animate-spin' viewBox='0 0 24 24'>
                <circle
                  className='opacity-25'
                  cx='12'
                  cy='12'
                  r='10'
                  stroke='currentColor'
                  strokeWidth='4'
                  fill='none'
                />
                <path
                  className='opacity-75'
                  fill='currentColor'
                  d='M4 12a8 8 0 018-8v8h8a8 8 0 01-16 0z'
                />
              </svg>
              Generating…
            </span>
          ) : (
            'Generate'
          )}
        </button>
      </div>

      {error && (
        <p className='mt-3 text-center text-sm text-red-600 dark:text-red-400'>
          {error}
        </p>
      )}
    </div>
  );
}
