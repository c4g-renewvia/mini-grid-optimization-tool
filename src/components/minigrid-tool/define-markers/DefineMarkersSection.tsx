'use client';

import React from 'react';
import TestDataGenerator from './TestDataGenerator';
import FileUploadArea from './FileUploadArea';
import ManualPointInput from './ManualPointInput';
import MapSearchBar from './MapSearchBar';

interface DefineMarkersSectionProps {
  isExpanded: boolean;
  onToggle: () => void;
  map: google.maps.Map | null;

  // TestDataGenerator
  selectedCount: number;
  onCountChange: (count: number) => void;
  onGenerate: () => void;
  loading: boolean;
  error: string | null;

  // FileUploadArea
  isDragOver: boolean;
  fileName: string | null;
  dataPointsLength: number;
  onDragOver: (e: React.DragEvent<HTMLDivElement>) => void;
  onDragLeave: (e: React.DragEvent<HTMLDivElement>) => void;
  onDrop: (e: React.DragEvent<HTMLDivElement>) => void;
  onFileSelect: (e: React.ChangeEvent<HTMLInputElement>) => void;

  // MapSearchBar
  onPlaceSelected: (lat: number, lng: number, name: string) => void;

  // ManualPointInput
  manualPoint: {
    name: string;
    lat: string;
    lng: string;
    type: 'source' | 'terminal' | 'pole';
  };
  onManualPointChange: (point: any) => void;
  onAddManualPoint: (e: React.FormEvent) => void;
}

export default function DefineMarkersSection({
  isExpanded,
  onToggle,
  map,
  selectedCount,
  onCountChange,
  onGenerate,
  loading,
  error,
  isDragOver,
  fileName,
  dataPointsLength,
  onDragOver,
  onDragLeave,
  onDrop,
  onFileSelect,
  onPlaceSelected,
  manualPoint,
  onManualPointChange,
  onAddManualPoint,
}: DefineMarkersSectionProps) {
  return (
    <section>
      {/* Collapsible Header */}
      <button
        onClick={onToggle}
        className='mb-6 flex w-full items-center justify-between rounded-2xl border border-emerald-200 bg-emerald-50 px-5 py-4 transition-all hover:bg-emerald-100 dark:border-emerald-500/30 dark:bg-emerald-900/20 dark:hover:bg-emerald-900/30'
      >
        <h2 className='text-xl font-bold text-emerald-700 dark:text-emerald-300'>
          1. Define Markers
        </h2>
        <svg
          className={`h-5 w-5 text-emerald-600 transition-transform dark:text-emerald-400 ${
            isExpanded ? 'rotate-180' : ''
          }`}
          fill='none'
          stroke='currentColor'
          viewBox='0 0 24 24'
          strokeWidth={2}
        >
          <path
            strokeLinecap='round'
            strokeLinejoin='round'
            d='M19 14l-7 7m0 0l-7-7m7 7V3'
          />
        </svg>
      </button>

      {/* Expanded Content */}
      {isExpanded && (
        <div className='space-y-4'>
          {/* Instructions */}
          <div className='rounded-xl border border-zinc-200 bg-white p-6 backdrop-blur-sm dark:border-zinc-700 dark:bg-zinc-900/50'>
            <ul className='space-y-3 text-sm'>
              <li className='flex items-start gap-3'>
                <span className='mt-1 text-emerald-500'>•</span>
                <span>
                  <strong>Click on the map</strong> to place a marker. Click the{' '}
                  <strong>×</strong> button to delete a marker.
                </span>
              </li>
              <li className='flex items-start gap-3'>
                <span className='mt-1 text-emerald-500'>•</span>
                <span>
                  <strong>Drag markers</strong> to adjust their placement. Edges
                  cannot exceed <strong>30 meters</strong>.
                </span>
              </li>
              <li className='flex items-start gap-3'>
                <span className='mt-1 text-emerald-500'>•</span>
                <span>
                  <strong>Click on an Edge</strong> to delete it.
                </span>
              </li>
            </ul>
          </div>

          {/* Google Maps Search Bar */}
          <MapSearchBar map={map} onPlaceSelected={onPlaceSelected}/>

          {/* Test Data Generator */}
          <TestDataGenerator
            selectedCount={selectedCount}
            onCountChange={onCountChange}
            onGenerate={onGenerate}
            loading={loading}
            error={error}
          />

          {/* File Upload */}
          <FileUploadArea
            isDragOver={isDragOver}
            fileName={fileName}
            dataPointsLength={dataPointsLength}
            loading={loading}
            error={error}
            onDragOver={onDragOver}
            onDragLeave={onDragLeave}
            onDrop={onDrop}
            onFileSelect={onFileSelect}
          />

          {/* Manual Coordinate Input */}
          <ManualPointInput
            manualPoint={manualPoint}
            onManualPointChange={onManualPointChange}
            onAddPoint={onAddManualPoint}
          />
        </div>
      )}
    </section>
  );
}
