'use client';

import React from 'react';
import SolverConfiguration from './SolverConfiguration';
import type { MiniGridNode, Solvers } from '@/types/minigrid';

interface SolverSectionProps {
  isExpanded: boolean;
  onToggle: () => void;

  // All SolverConfiguration props
  solvers: Solvers[];
  selectedSolverName: string;
  onSolverChange: (name: string) => void;
  paramValues: Record<string, any>;
  onParamChange: (paramName: string, value: any) => void;
  useExistingPoles: boolean;
  onUseExistingPolesChange: (value: boolean) => void;
  poleCount: number;
  onRunSolver: () => void;
  computing: boolean;
  calcError: string | null;
  miniGridNodes: MiniGridNode[];
}

export default function SolverSection({
                                        isExpanded,
                                        onToggle,
                                        solvers,
                                        selectedSolverName,
                                        onSolverChange,
                                        paramValues,
                                        onParamChange,
                                        useExistingPoles,
                                        onUseExistingPolesChange,
                                        poleCount,
                                        onRunSolver,
                                        computing,
                                        calcError,
                                        miniGridNodes,
                                      }: SolverSectionProps) {
  return (
    <section>
      <button
        onClick={onToggle}
        className='mb-6 flex w-full items-center justify-between rounded-2xl border border-purple-200 bg-purple-50 px-5 py-4 transition-all hover:bg-purple-100 dark:border-purple-500/30 dark:bg-purple-900/20 dark:hover:bg-purple-900/30'
      >
        <h2 className='text-xl font-bold text-purple-700 dark:text-purple-300'>
          3. Run Solver
        </h2>
        <svg
          className={`h-5 w-5 text-purple-600 transition-transform dark:text-purple-400 ${
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

      {isExpanded && (
        <SolverConfiguration
          solvers={solvers}
          selectedSolverName={selectedSolverName}
          onSolverChange={onSolverChange}
          paramValues={paramValues}
          onParamChange={onParamChange}
          useExistingPoles={useExistingPoles}
          onUseExistingPolesChange={onUseExistingPolesChange}
          poleCount={poleCount}
          onRunSolver={onRunSolver}
          computing={computing}
          calcError={calcError}
          miniGridNodes={miniGridNodes}
        />
      )}
    </section>
  );
}