'use client';

import React from 'react';
import { ManualPoint } from '@/types/minigrid';

interface ManualPointInputProps {
  manualPoint: ManualPoint;
  onManualPointChange: (_point: ManualPoint) => void;
  onAddPoint: (_e: React.FormEvent) => void;
}

export default function ManualPointInput({
  manualPoint,
  onManualPointChange,
  onAddPoint,
}: ManualPointInputProps) {
  return (
    <div className='rounded-xl border border-zinc-200 bg-white p-6 backdrop-blur-sm dark:border-zinc-700 dark:bg-zinc-900/50'>
      <h3 className='mb-3 text-lg font-semibold text-zinc-900 dark:text-white'>
        Input Coordinates Manually
      </h3>

      <form onSubmit={onAddPoint} className='space-y-4'>
        <div className='grid gap-4 sm:grid-cols-2 lg:grid-cols-4'>
          {/* Name */}
          <div>
            <label className='mb-1.5 block text-xs font-medium text-zinc-700 dark:text-zinc-400'>
              Name
            </label>
            <input
              type='text'
              placeholder='e.g. House A'
              value={manualPoint.name}
              onChange={(e) =>
                onManualPointChange({ ...manualPoint, name: e.target.value })
              }
              className='w-full rounded-lg border border-zinc-200 bg-white px-3 py-2 text-sm text-zinc-900 outline-none focus:border-emerald-500 focus:ring-emerald-500 dark:border-zinc-700 dark:bg-zinc-900 dark:text-white'
            />
          </div>

          {/* Latitude */}
          <div>
            <label className='mb-1.5 block text-xs font-medium text-zinc-700 dark:text-zinc-400'>
              Latitude
            </label>
            <input
              type='text'
              placeholder='33.777...'
              value={manualPoint.lat}
              onChange={(e) =>
                onManualPointChange({ ...manualPoint, lat: e.target.value })
              }
              className='w-full rounded-lg border border-zinc-200 bg-white px-3 py-2 text-sm text-zinc-900 outline-none focus:border-emerald-500 focus:ring-emerald-500 dark:border-zinc-700 dark:bg-zinc-900 dark:text-white'
            />
          </div>

          {/* Longitude */}
          <div>
            <label className='mb-1.5 block text-xs font-medium text-zinc-700 dark:text-zinc-400'>
              Longitude
            </label>
            <input
              type='text'
              placeholder='-84.396...'
              value={manualPoint.lng}
              onChange={(e) =>
                onManualPointChange({ ...manualPoint, lng: e.target.value })
              }
              className='w-full rounded-lg border border-zinc-200 bg-white px-3 py-2 text-sm text-zinc-900 outline-none focus:border-emerald-500 focus:ring-emerald-500 dark:border-zinc-700 dark:bg-zinc-900 dark:text-white'
            />
          </div>

          {/* Type */}
          <div>
            <label className='mb-1.5 block text-xs font-medium text-zinc-700 dark:text-zinc-400'>
              Type
            </label>
            <select
              value={manualPoint.type}
              onChange={(e) =>
                onManualPointChange({
                  ...manualPoint,
                  type: e.target.value as 'source' | 'terminal' | 'pole',
                })
              }
              className='w-full rounded-lg border border-zinc-200 bg-white px-3 py-2 text-sm text-zinc-900 outline-none focus:border-emerald-500 focus:ring-emerald-500 dark:border-zinc-700 dark:bg-zinc-900 dark:text-white'
            >
              <option value='terminal'>Terminal</option>
              <option value='source'>Source</option>
              <option value='pole'>Pole</option>
            </select>
          </div>
        </div>

        <button
          type='submit'
          className='w-full rounded-lg bg-emerald-600 py-2.5 text-sm font-medium text-white transition hover:bg-emerald-700 active:scale-95'
        >
          Add Marker to Map
        </button>
      </form>
    </div>
  );
}
