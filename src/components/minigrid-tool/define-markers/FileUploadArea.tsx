'use client';

import React from 'react';

interface FileUploadAreaProps {
  isDragOver: boolean;
  fileName: string | null;
  dataPointsLength: number;
  loading: boolean;
  error: string | null;
  onDragOver: (_e: React.DragEvent<HTMLDivElement>) => void;
  onDragLeave: (_e: React.DragEvent<HTMLDivElement>) => void;
  onDrop: (_e: React.DragEvent<HTMLDivElement>) => void;
  onFileSelect: (_e: React.ChangeEvent<HTMLInputElement>) => void;
}

export default function FileUploadArea({
  isDragOver,
  fileName,
  dataPointsLength,
  loading,
  error,
  onDragOver,
  onDragLeave,
  onDrop,
  onFileSelect,
}: FileUploadAreaProps) {
  return (
    <div className='rounded-xl border border-zinc-200 bg-white p-6 backdrop-blur-sm dark:border-zinc-700 dark:bg-zinc-900/50'>
      <h3 className='mb-3 text-lg font-semibold text-zinc-900 dark:text-white'>
        Upload File
      </h3>

      <div className='mb-4 space-y-1.5 text-xs text-zinc-500 dark:text-zinc-400'>
        <p>
          CSV or KML files supported.{' '}
          <span className='cursor-help text-emerald-600 underline dark:text-emerald-400'>
            See format examples
          </span>
        </p>
      </div>

      {/* Drag & Drop Area */}
      <div
        className={`relative rounded-lg border-2 border-dashed p-5 text-center transition-colors ${
          isDragOver
            ? 'border-emerald-500 bg-emerald-50 dark:bg-emerald-900/25'
            : 'border-zinc-300 hover:border-zinc-400 dark:border-zinc-700 dark:hover:border-zinc-600'
        }`}
        onDragOver={onDragOver}
        onDragLeave={onDragLeave}
        onDrop={onDrop}
      >
        <div className='flex flex-wrap items-center justify-center gap-4'>
          <div className='shrink-0 text-3xl opacity-90'>📄</div>

          <div className='flex flex-col items-center gap-2'>
            <p className='text-base font-medium text-zinc-700 dark:text-zinc-200'>
              {isDragOver
                ? 'Drop your file here'
                : 'Drag & drop or click to upload'}
            </p>

            <label className='inline-flex cursor-pointer items-center rounded bg-emerald-600 px-5 py-2.5 text-sm font-medium text-white transition hover:bg-emerald-700 active:scale-97'>
              Select File
              <input
                type='file'
                accept='.csv,.kml'
                onChange={onFileSelect}
                className='hidden'
              />
            </label>
          </div>
        </div>
      </div>

      {/* Status Messages */}
      <div className='mt-3 text-center text-sm'>
        <div className='flex flex-wrap items-center justify-center gap-x-6 gap-y-1.5'>
          {fileName && (
            <p className='truncate font-medium text-zinc-700 dark:text-zinc-300'>
              Selected:{' '}
              <span className='text-zinc-500 dark:text-zinc-400'>
                {fileName}
              </span>
            </p>
          )}

          {dataPointsLength > 0 && !loading && (
            <p className='font-medium text-emerald-600 dark:text-emerald-300'>
              Loaded {dataPointsLength} point{dataPointsLength !== 1 ? 's' : ''}
            </p>
          )}
        </div>

        {error && (
          <p className='mt-1.5 text-red-600 dark:text-red-400'>{error}</p>
        )}

        {loading && (
          <p className='mt-1.5 animate-pulse text-emerald-600 dark:text-emerald-400'>
            Processing file...
          </p>
        )}
      </div>
    </div>
  );
}
