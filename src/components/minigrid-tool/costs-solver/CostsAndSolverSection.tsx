'use client';

import React from 'react';
import CostParameters from './CostParameters';
import SolverConfiguration from './SolverConfiguration';
import type { MiniGridNode, Solvers } from '@/types/minigrid';

interface CostsAndSolverSectionProps {
  isExpanded: boolean;
  onToggle: () => void;

  // CostParameters props
  poleCost: number;
  lowVoltageCost: number;
  highVoltageCost: number;
  onPoleCostChange: (value: number) => void;
  onLowVoltageCostChange: (value: number) => void;
  onHighVoltageCostChange: (value: number) => void;
  onRandomCosts: () => void;

  lowVoltagePoleToPoleLengthConstraint: number;
  lowVoltagePoleToTerminalLengthConstraint: number;
  lowVoltagePoleToTerminalMinimumLength: number;
  highVoltagePoleToPoleLengthConstraint: number;
  highVoltagePoleToTerminalLengthConstraint: number;
  highVoltagePoleToTerminalMinimumLength: number;

  onLowVoltagePoleToPoleChange: (value: number) => void;
  onLowVoltagePoleToTerminalChange: (value: number) => void;
  onLowVoltagePoleToTerminalMinimumChange: (value: number) => void;
  onHighVoltagePoleToPoleChange: (value: number) => void;
  onHighVoltagePoleToTerminalChange: (value: number) => void;
  onHighVoltagePoleToTerminalMinimumChange: (value: number) => void;

  // SolverConfiguration props
  solvers: Solvers[];
  selectedSolverName: string;
  onSolverChange: (name: string) => void;
  paramValues: Record<string, number>;
  onParamChange: (paramName: string, value: string) => void;
  useExistingPoles: boolean;
  onUseExistingPolesChange: (value: boolean) => void;
  poleCount: number;
  onRunSolver: () => void;
  computing: boolean;
  calcError: string | null;
  miniGridNodes: MiniGridNode[];
}

export default function CostsAndSolverSection({
  isExpanded,
  onToggle,
  poleCost,
  lowVoltageCost,
  highVoltageCost,
  onPoleCostChange,
  onLowVoltageCostChange,
  onHighVoltageCostChange,
  onRandomCosts,
  lowVoltagePoleToPoleLengthConstraint,
  lowVoltagePoleToTerminalLengthConstraint,
  lowVoltagePoleToTerminalMinimumLength,
  highVoltagePoleToPoleLengthConstraint,
  highVoltagePoleToTerminalLengthConstraint,
  highVoltagePoleToTerminalMinimumLength,
  onLowVoltagePoleToPoleChange,
  onLowVoltagePoleToTerminalChange,
  onLowVoltagePoleToTerminalMinimumChange,
  onHighVoltagePoleToPoleChange,
  onHighVoltagePoleToTerminalChange,
  onHighVoltagePoleToTerminalMinimumChange,
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
}: CostsAndSolverSectionProps) {
  return (
    <section>
      {/* Collapsible Header */}
      <button
        onClick={onToggle}
        className='mb-6 flex w-full items-center justify-between rounded-2xl border border-purple-200 bg-purple-50 px-5 py-4 transition-all hover:bg-purple-100 dark:border-purple-500/30 dark:bg-purple-900/20 dark:hover:bg-purple-900/30'
      >
        <h2 className='text-xl font-bold text-purple-700 dark:text-purple-300'>
          2. Costs & Solver
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
        <div className='space-y-4'>
          <CostParameters
            poleCost={poleCost}
            lowVoltageCost={lowVoltageCost}
            highVoltageCost={highVoltageCost}
            onPoleCostChange={onPoleCostChange}
            onLowVoltageCostChange={onLowVoltageCostChange}
            onHighVoltageCostChange={onHighVoltageCostChange}
            onRandomCosts={onRandomCosts}
            lowVoltagePoleToPoleLengthConstraint={
              lowVoltagePoleToPoleLengthConstraint
            }
            lowVoltagePoleToTerminalLengthConstraint={
              lowVoltagePoleToTerminalLengthConstraint
            }
            lowVoltagePoleToTerminalMinimumLength={
              lowVoltagePoleToTerminalMinimumLength
            }
            highVoltagePoleToPoleLengthConstraint={
              highVoltagePoleToPoleLengthConstraint
            }
            highVoltagePoleToTerminalLengthConstraint={
              highVoltagePoleToTerminalLengthConstraint
            }
            highVoltagePoleToTerminalMinimumLength={
              highVoltagePoleToTerminalMinimumLength
            }
            onLowVoltagePoleToPoleChange={onLowVoltagePoleToPoleChange}
            onLowVoltagePoleToTerminalChange={onLowVoltagePoleToTerminalChange}
            onHighVoltagePoleToPoleChange={onHighVoltagePoleToPoleChange}
            onHighVoltagePoleToTerminalChange={
              onHighVoltagePoleToTerminalChange
            }
            onLowVoltagePoleToTerminalMinimumChange={
              onLowVoltagePoleToTerminalMinimumChange
            }
            onHighVoltagePoleToTerminalMinimumChange={
              onHighVoltagePoleToTerminalMinimumChange
            }
          />

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
        </div>
      )}
    </section>
  );
}
