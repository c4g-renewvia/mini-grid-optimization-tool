'use client';

import React, { useState } from 'react';

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
  const [showExamples, setShowExamples] = useState(false);

  // Sample content from your provided files
  const csvExample = `name,type,lat,lng
Power Source,source,3.75689,34.721477
Building,terminal,3.757086,34.720849
Building,terminal,3.756774,34.720935
Building,terminal,3.757295,34.721001
Building,terminal,3.757632,34.720844
Building,terminal,3.757501,34.721527
Building,terminal,3.757336,34.721818
Building,terminal,3.757683,34.721864
Building,terminal,3.757585,34.722007
Building,terminal,3.75772,34.722045`;

  const kmlExample = `<?xml version="1.0" encoding="UTF-8"?>
<kml xmlns="http://www.opengis.net/kml/2.2">
  <Document>
    <name>Minigrid Test Coordinates</name>
    
    <!-- Power Source -->
    <Placemark>
      <name>Power Source</name>
      <description>Type: source</description>
      <Point>
        <coordinates>34.721477,3.75689,0</coordinates>
      </Point>
    </Placemark>

    <!-- Terminal buildings -->
    <Placemark>
      <name>Terminal 1</name>
      <description>Type: terminal</description>
      <Point>
        <coordinates>34.720849,3.757086,0</coordinates>
      </Point>
    </Placemark>

    <!-- Add more Placemarks as needed... -->
  </Document>
</kml>`;

  return (
    <>
      <div className='rounded-xl border border-zinc-200 bg-white p-6 backdrop-blur-sm dark:border-zinc-700 dark:bg-zinc-900/50'>
        <h3 className='mb-3 text-lg font-semibold text-zinc-900 dark:text-white'>
          Upload File
        </h3>

        <div className='mb-4 space-y-1.5 text-xs text-zinc-500 dark:text-zinc-400'>
          <p>
            CSV or KML files supported.{' '}
            <button
              onClick={() => setShowExamples(true)}
              className='cursor-help text-emerald-600 underline transition-colors hover:text-emerald-700 dark:text-emerald-400 dark:hover:text-emerald-300'
            >
              See format examples
            </button>
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
                Loaded {dataPointsLength} point
                {dataPointsLength !== 1 ? 's' : ''}
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

      {/* Format Examples Modal */}
      {showExamples && (
        <div className='fixed inset-0 z-50 flex items-center justify-center bg-black/70 p-4'>
          <div className='w-full max-w-4xl overflow-hidden rounded-2xl bg-white shadow-xl dark:bg-zinc-900'>
            {/* Modal Header */}
            <div className='flex items-center justify-between border-b border-zinc-200 px-6 py-4 dark:border-zinc-700'>
              <h2 className='text-xl font-semibold text-zinc-900 dark:text-white'>
                Supported File Formats
              </h2>
              <button
                onClick={() => setShowExamples(false)}
                className='text-2xl leading-none text-zinc-400 hover:text-zinc-600 dark:hover:text-zinc-300'
              >
                ×
              </button>
            </div>

            <div className='max-h-[80vh] space-y-8 overflow-auto p-6'>
              {/* CSV Example */}
              <div>
                <div className='mb-3 flex items-center gap-3'>
                  <div className='text-xl'>📊</div>
                  <h3 className='text-lg font-semibold text-zinc-900 dark:text-white'>
                    CSV Format
                  </h3>
                </div>
                <p className='mb-3 text-sm text-zinc-500 dark:text-zinc-400'>
                  Required columns:{' '}
                  <code className='rounded bg-zinc-100 px-1 py-0.5 dark:bg-zinc-800'>
                    name
                  </code>
                  ,{' '}
                  <code className='rounded bg-zinc-100 px-1 py-0.5 dark:bg-zinc-800'>
                    type
                  </code>
                  ,{' '}
                  <code className='rounded bg-zinc-100 px-1 py-0.5 dark:bg-zinc-800'>
                    lat
                  </code>
                  ,{' '}
                  <code className='rounded bg-zinc-100 px-1 py-0.5 dark:bg-zinc-800'>
                    lng
                  </code>
                </p>
                <pre className='overflow-auto rounded-xl bg-zinc-950 p-4 font-mono text-sm whitespace-pre text-emerald-300'>
                  {csvExample}
                </pre>
              </div>

              {/* KML Example */}
              <div>
                <div className='mb-3 flex items-center gap-3'>
                  <div className='text-xl'>🗺️</div>
                  <h3 className='text-lg font-semibold text-zinc-900 dark:text-white'>
                    KML Format
                  </h3>
                </div>
                <p className='mb-3 text-sm text-zinc-500 dark:text-zinc-400'>
                  Simple KML with Placemarks containing coordinates with <br/>
                  (Name, `Type:` in Description, and Point)
                </p>
                <pre className='overflow-auto rounded-xl bg-zinc-950 p-4 font-mono text-sm whitespace-pre text-emerald-300'>
                  {kmlExample}
                </pre>
              </div>
            </div>

            {/* Modal Footer */}
            <div className='flex justify-end border-t border-zinc-200 px-6 py-4 dark:border-zinc-700'>
              <button
                onClick={() => setShowExamples(false)}
                className='rounded-lg bg-zinc-100 px-6 py-2.5 text-sm font-medium transition-colors hover:bg-zinc-200 dark:bg-zinc-800 dark:hover:bg-zinc-700'
              >
                Close
              </button>
            </div>
          </div>
        </div>
      )}
    </>
  );
}
