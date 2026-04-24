'use client';

import React from 'react';
import ExportSummary from './ExportSummary';
import type { CostBreakdown, MiniGridNode } from '@/types/minigrid';

interface ExportAndSummarySectionProps {
  isExpanded: boolean;
  onToggle: () => void;

  // ExportSummary props
  costBreakdown: CostBreakdown;
  solverOriginalCost: number;
  poleCost: number;
  lowVoltageCost: number;
  highVoltageCost: number;
  miniGridNodes: MiniGridNode[];
  allowDragTerminals: boolean;
  onAllowDragTerminalsChange: (value: boolean) => void;
  showEdgeLengths: boolean;           // ← NEW
  onShowEdgeLengthsChange: (_show: boolean) => void; // ← NEW
  onDownloadKml: () => void;
  onSaveToDatabase: () => void;
  isAuthenticated: boolean;
  savedRunsCount: number;
  computingMiniGrid: boolean;
}

export default function ExportAndSummarySection({
  isExpanded,
  onToggle,
  costBreakdown,
  solverOriginalCost,
  poleCost,
  lowVoltageCost,
  highVoltageCost,
  miniGridNodes,
  allowDragTerminals,
  showEdgeLengths,
  onShowEdgeLengthsChange,
  onAllowDragTerminalsChange,
  onDownloadKml,
  onSaveToDatabase,
  isAuthenticated,
  savedRunsCount,
  computingMiniGrid,
}: ExportAndSummarySectionProps) {
  return (
    <section>
      {/* Collapsible Header */}
      <button
        onClick={onToggle}
        className='mb-6 flex w-full items-center justify-between rounded-2xl border border-blue-200 bg-blue-50 px-5 py-4 transition-all hover:bg-blue-100 dark:border-blue-500/30 dark:bg-blue-900/20 dark:hover:bg-blue-900/30'
      >
        <h2 className='text-xl font-bold text-blue-700 dark:text-blue-300'>
          3. Export & Summary
        </h2>
        <svg
          className={`h-5 w-5 text-blue-600 transition-transform dark:text-blue-400 ${
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
        <ExportSummary
          costBreakdown={costBreakdown}
          solverOriginalCost={solverOriginalCost}
          poleCost={poleCost}
          lowVoltageCost={lowVoltageCost}
          highVoltageCost={highVoltageCost}
          miniGridNodes={miniGridNodes}
          allowDragTerminals={allowDragTerminals}
          onAllowDragTerminalsChange={onAllowDragTerminalsChange}
          showEdgeLengths={showEdgeLengths}
          onShowEdgeLengthsChange={onShowEdgeLengthsChange}
          onDownloadKml={onDownloadKml}
          onSaveToDatabase={onSaveToDatabase}
          isAuthenticated={isAuthenticated}
          savedRunsCount={savedRunsCount}
          computingMiniGrid={computingMiniGrid}
        />
      )}
    </section>
  );
}
