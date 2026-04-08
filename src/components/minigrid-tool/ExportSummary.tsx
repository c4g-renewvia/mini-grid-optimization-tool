'use client';

import React from 'react';
import type {
  CostBreakdown,
  MiniGridNode,
} from '@/types/minigrid';

interface ExportSummaryProps {
  costBreakdown: CostBreakdown;
  solverOriginalCost: number;
  poleCost: number;
  lowVoltageCost: number;
  highVoltageCost: number;
  miniGridNodes: MiniGridNode[];
  allowDragTerminals: boolean;
  onAllowDragTerminalsChange: (_allow: boolean) => void;
  onDownloadKml: () => void;
  onSaveToDatabase: () => void;
  isAuthenticated: boolean;
  savedRunsCount: number;
  computingMiniGrid: boolean;
}

const formatMeters = (m: number) =>
  m.toLocaleString(undefined, { maximumFractionDigits: 0 });

const formatUSD = (v: number) =>
  v.toLocaleString(undefined, {
    minimumFractionDigits: 2,
    maximumFractionDigits: 2,
  });

export default function ExportSummary({
  costBreakdown,
  solverOriginalCost,
  poleCost,
  lowVoltageCost,
  highVoltageCost,
  miniGridNodes,
  allowDragTerminals,
  onAllowDragTerminalsChange,
  onDownloadKml,
  onSaveToDatabase,
  isAuthenticated,
  savedRunsCount,
  computingMiniGrid,
}: ExportSummaryProps) {
  const poleCount = miniGridNodes.filter((n) => n.type === 'pole').length;
  const costDiff = costBreakdown.grandTotal - solverOriginalCost;
  const isNegative = costDiff <= 0;

  return (
    <div className='space-y-4'>
      {/* Allow Dragging Terminals */}
        <div className='flex items-center gap-3 rounded-lg border border-zinc-200 bg-white p-4 dark:border-zinc-700 dark:bg-zinc-900/50'>
          <input
            type='checkbox'
            id='allow-drag-terminals'
            checked={allowDragTerminals}
            onChange={(e) => onAllowDragTerminalsChange(e.target.checked)}
            className='h-5 w-5 rounded border-zinc-300 bg-white text-purple-600 focus:ring-purple-500 dark:border-zinc-600 dark:bg-zinc-800'
          />
          <label
            htmlFor='allow-drag-terminals'
            className='cursor-pointer text-sm font-medium text-zinc-700 dark:text-zinc-300'
          >
            Allow dragging of{' '}
            <span className='font-semibold text-blue-600 dark:text-blue-400'>
              Terminals
            </span>{' '}
            (Poles can always be dragged)
          </label>
        </div>

      {/* Solver Cost Box */}
        <div className='rounded-2xl border border-purple-200 bg-purple-50 p-6 text-center dark:border-purple-500/30 dark:bg-purple-900/20'>
          <p className='text-xs font-bold tracking-widest text-purple-600 uppercase dark:text-purple-400'>
            Solver Cost
          </p>
          <p className='mt-1 text-4xl font-extrabold text-purple-700 dark:text-purple-300'>
            ${formatUSD(solverOriginalCost)}
          </p>
          <div className='mt-4 grid grid-cols-2 gap-x-4 border-t border-purple-200 pt-4 text-left text-[10px] text-purple-600/70 dark:border-purple-500/20 dark:text-purple-300/70'>
            <div className='space-y-1'>
              <p className='text-xs font-semibold text-purple-700 dark:text-purple-400'>
                Poles
              </p>
              <p>
                {costBreakdown.poleCount} @ $
                {formatUSD(costBreakdown.usedPoleCost || poleCost)}
              </p>
              <p className='pt-1 font-medium text-purple-800 dark:text-purple-200'>
                Total: ${formatUSD(costBreakdown.poleCost)}
              </p>
            </div>
            <div className='space-y-3 border-l border-purple-200 pl-4 dark:border-purple-500/10'>
              <div className='space-y-0.5'>
                <p className='text-xs font-semibold text-purple-700 dark:text-purple-400'>
                  LV Wire
                </p>
                <p>
                  {formatMeters(costBreakdown.lowVoltageMeters)}m @ $
                  {formatUSD(
                    costBreakdown.usedLowCostPerMeter || lowVoltageCost
                  )}
                  /m
                </p>
                <p className='font-medium text-purple-800 dark:text-purple-200'>
                  Total: ${formatUSD(costBreakdown.lowWireCost)}
                </p>
              </div>
              <div className='space-y-0.5'>
                <p className='text-xs font-semibold text-purple-700 dark:text-purple-400'>
                  HV Wire
                </p>
                <p>
                  {formatMeters(costBreakdown.highVoltageMeters)}m @ $
                  {formatUSD(
                    costBreakdown.usedHighCostPerMeter || highVoltageCost
                  )}
                  /m
                </p>
                <p className='font-medium text-purple-800 dark:text-purple-200'>
                  Total: ${formatUSD(costBreakdown.highWireCost)}
                </p>
              </div>
            </div>
          </div>
        </div>

      {/* Live Cost Box */}
        <div className='rounded-2xl border border-emerald-200 bg-emerald-50 p-6 text-center dark:border-emerald-500/30 dark:bg-emerald-900/20'>
          <p className='text-xs font-bold tracking-widest text-emerald-600 uppercase dark:text-emerald-400'>
            Live Cost
          </p>
          <p className='mt-1 text-4xl font-extrabold text-emerald-700 dark:text-emerald-300'>
            ${formatUSD(costBreakdown.grandTotal)}
          </p>
          <div className='mt-4 grid grid-cols-2 gap-x-4 border-t border-emerald-200 pt-4 text-left text-[10px] text-emerald-600/70 dark:border-emerald-500/20 dark:text-emerald-400/70'>
            <div className='space-y-1'>
              <p className='text-xs font-semibold text-emerald-700 dark:text-emerald-500'>
                Poles
              </p>
              <p>
                {poleCount} @ ${formatUSD(poleCost)}
              </p>
              <p className='pt-1 font-medium text-emerald-800 dark:text-emerald-200'>
                Total: ${formatUSD(poleCount * poleCost)}
              </p>
            </div>
            <div className='space-y-3 border-l border-emerald-200 pl-4 dark:border-emerald-500/10'>
              <div className='space-y-0.5'>
                <p className='text-xs font-semibold text-emerald-700 dark:text-emerald-500'>
                  LV Wire
                </p>
                <p>
                  {formatMeters(costBreakdown.lowVoltageMeters)}m @ $
                  {formatUSD(lowVoltageCost)}/m
                </p>
                <p className='font-medium text-emerald-800 dark:text-emerald-200'>
                  Total: $
                  {formatUSD(costBreakdown.lowVoltageMeters * lowVoltageCost)}
                </p>
              </div>
              <div className='space-y-0.5'>
                <p className='text-xs font-semibold text-emerald-700 dark:text-emerald-500'>
                  HV Wire
                </p>
                <p>
                  {formatMeters(costBreakdown.highVoltageMeters)}m @ $
                  {formatUSD(highVoltageCost)}/m
                </p>
                <p className='font-medium text-emerald-800 dark:text-emerald-200'>
                  Total: $
                  {formatUSD(costBreakdown.highVoltageMeters * highVoltageCost)}
                </p>
              </div>
            </div>
          </div>
        </div>

      {/* Cost Difference */}
        <div
          className={`rounded-2xl border p-6 text-center ${
            isNegative
              ? 'border-emerald-200 bg-emerald-50 dark:border-emerald-500/30 dark:bg-emerald-900/20'
              : 'border-red-200 bg-red-50 dark:border-red-500/30 dark:bg-red-900/20'
          }`}
        >
          <p
            className={`text-xs font-bold tracking-widest uppercase ${
              isNegative
                ? 'text-emerald-600 dark:text-emerald-400'
                : 'text-red-600 dark:text-red-400'
            }`}
          >
            Cost Difference
          </p>
          <p
            className={`mt-1 text-4xl font-extrabold ${
              isNegative
                ? 'text-emerald-700 dark:text-emerald-300'
                : 'text-red-700 dark:text-red-300'
            }`}
          >
            ${formatUSD(costDiff)}
          </p>
          <p className='mt-2 text-[10px] text-zinc-500 italic dark:text-zinc-400'>
            {isNegative
              ? 'Savings vs Solver baseline'
              : 'Additional cost vs Solver baseline'}
          </p>
        </div>

      {/* Export Options */}
        <div className='pt-4'>
          <h3 className='mb-4 text-xl font-semibold text-emerald-700 dark:text-emerald-300'>
            Export Options
          </h3>
          <div className='flex flex-col gap-3'>
            <button
              onClick={onDownloadKml}
              className='w-full rounded-xl bg-purple-600 py-4 font-semibold text-white hover:bg-purple-700 disabled:opacity-50 dark:text-white'
            >
              📥 Download KML
            </button>

            <button
              onClick={onSaveToDatabase}
              disabled={
                computingMiniGrid ||
                savedRunsCount >= 10
              }
              className='w-full rounded-xl bg-emerald-600 py-4 font-semibold text-white hover:bg-emerald-700 disabled:opacity-50 dark:text-white'
            >
              💾 Save to My Mini-Grids
            </button>

            {!isAuthenticated && (
              <p className='text-center text-xs text-zinc-500 dark:text-zinc-400'>
                Sign in to save your mini-grid
              </p>
            )}
          </div>
        </div>
    </div>
  );
}
