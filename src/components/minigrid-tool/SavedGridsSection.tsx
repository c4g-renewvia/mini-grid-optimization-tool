'use client';

import React from 'react';
import type { MiniGridRun } from '@/types/minigrid';

interface SavedGridsSectionProps {
  savedRuns: MiniGridRun[];
  loadingSaved: boolean;
  expanded: boolean;
  onToggle: () => void;
  onLoadRun: (_run: MiniGridRun) => void;
  onDeleteRun: (_runId: string, _runName?: string) => void;
}

export default function SavedGridsSection({
  savedRuns,
  loadingSaved,
  expanded,
  onToggle,
  onLoadRun,
  onDeleteRun,
}: SavedGridsSectionProps) {
  return (
    <section>
      <button
        onClick={onToggle}
        className='mb-6 flex w-full items-center justify-between rounded-2xl border border-emerald-200 bg-emerald-50 px-5 py-4 transition-all hover:bg-emerald-100 dark:border-emerald-500/30 dark:bg-emerald-900/20 dark:hover:bg-emerald-900/30'
      >
        <h2 className='text-lg font-bold text-emerald-700 dark:text-emerald-300'>
          Saved Mini-grids ({savedRuns.length}/10)
        </h2>
        <svg
          className={`h-5 w-5 text-emerald-600 transition-transform dark:text-emerald-400 ${
            expanded ? 'rotate-180' : ''
          }`}
          fill='none'
          stroke='currentColor'
          viewBox='0 0 24 24'
        >
          <path
            strokeLinecap='round'
            strokeLinejoin='round'
            strokeWidth={2}
            d='M19 14l-7 7m0 0l-7-7m7 7V3'
          />
        </svg>
      </button>

      {expanded && (
        <div className='rounded-xl border border-zinc-200 bg-white p-6 backdrop-blur-sm dark:border-zinc-700 dark:bg-zinc-900/50'>
          {loadingSaved ? (
            <p className='py-8 text-center text-sm text-emerald-600 dark:text-emerald-400'>
              Loading saved runs...
            </p>
          ) : savedRuns.length === 0 ? (
            <p className='py-8 text-center text-sm text-zinc-500 italic dark:text-zinc-400'>
              No saved mini-grids yet. Solve a network and save it!
            </p>
          ) : (
            <div className='scrollbar-thin scrollbar-thumb-zinc-300 scrollbar-track-zinc-100 dark:scrollbar-thumb-zinc-700 dark:scrollbar-track-zinc-900/50 -mr-2 max-h-96 overflow-y-auto pr-2'>
              <div className='grid gap-4'>
                {savedRuns.map((run) => (
                  <div
                    key={run.id}
                    className='group relative cursor-pointer rounded-lg border border-zinc-200 bg-white p-4 transition-all hover:border-emerald-500 hover:bg-emerald-50 dark:border-zinc-800/60 dark:bg-zinc-950/40 dark:hover:border-emerald-700/50 dark:hover:bg-zinc-900/60'
                    onClick={() => onLoadRun(run)}
                  >
                    {/* Delete Button */}
                    <button
                      onClick={(e) => {
                        e.stopPropagation();
                        onDeleteRun(run.id, run.name);
                      }}
                      className='absolute top-3 right-3 rounded-full bg-red-100 p-1.5 text-red-600 transition hover:bg-red-200 dark:bg-red-900/60 dark:text-red-300 dark:hover:bg-red-900 dark:hover:text-red-200'
                      title='Delete this run'
                    >
                      <svg
                        className='h-4 w-4'
                        fill='none'
                        stroke='currentColor'
                        viewBox='0 0 24 24'
                      >
                        <path
                          strokeLinecap='round'
                          strokeLinejoin='round'
                          strokeWidth={2}
                          d='M6 18L18 6M6 6l12 12'
                        />
                      </svg>
                    </button>

                    <h4 className='truncate font-medium text-emerald-700 group-hover:text-emerald-600 dark:text-emerald-300/90 dark:group-hover:text-emerald-200'>
                      {run.name || 'Untitled Mini-Grid'}
                    </h4>

                    <p className='mt-1 text-xs text-zinc-500 dark:text-zinc-400'>
                      {run.fileName
                        ? `File: ${run.fileName}`
                        : 'Generated test data'}
                    </p>

                    <p className='mt-1 text-xs text-zinc-600 dark:text-zinc-500'>
                      {new Date(run.createdAt).toLocaleString()}
                      <br />
                      {run.miniGridNodes?.length || 0} nodes •{' '}
                      <span className='font-medium text-emerald-600 dark:text-green-400'>
                        ${run.costBreakdown.grandTotal.toLocaleString()}
                      </span>
                    </p>
                  </div>
                ))}
              </div>
            </div>
          )}
        </div>
      )}
    </section>
  );
}
