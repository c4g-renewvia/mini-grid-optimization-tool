'use client';

import React from 'react';
import CostParameters from './CostParameters';

interface CostsSectionProps {
  isExpanded: boolean;
  onToggle: () => void;

  // All CostParameters props
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
}

export default function CostsSection({
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
                                     }: CostsSectionProps) {
  return (
    <section>
      {/* Collapsible Header */}
      <button
        onClick={onToggle}
        className='mb-6 flex w-full items-center justify-between rounded-2xl border border-emerald-200 bg-emerald-50 px-5 py-4 transition-all hover:bg-emerald-100 dark:border-emerald-500/30 dark:bg-emerald-900/20 dark:hover:bg-emerald-900/30'
      >
        <h2 className='text-xl font-bold text-emerald-700 dark:text-emerald-300'>
          2. Parameters
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

      {isExpanded && (
        <CostParameters
          poleCost={poleCost}
          lowVoltageCost={lowVoltageCost}
          highVoltageCost={highVoltageCost}
          onPoleCostChange={onPoleCostChange}
          onLowVoltageCostChange={onLowVoltageCostChange}
          onHighVoltageCostChange={onHighVoltageCostChange}
          onRandomCosts={onRandomCosts}
          lowVoltagePoleToPoleLengthConstraint={lowVoltagePoleToPoleLengthConstraint}
          lowVoltagePoleToTerminalLengthConstraint={lowVoltagePoleToTerminalLengthConstraint}
          lowVoltagePoleToTerminalMinimumLength={lowVoltagePoleToTerminalMinimumLength}
          highVoltagePoleToPoleLengthConstraint={highVoltagePoleToPoleLengthConstraint}
          highVoltagePoleToTerminalLengthConstraint={highVoltagePoleToTerminalLengthConstraint}
          highVoltagePoleToTerminalMinimumLength={highVoltagePoleToTerminalMinimumLength}
          onLowVoltagePoleToPoleChange={onLowVoltagePoleToPoleChange}
          onLowVoltagePoleToTerminalChange={onLowVoltagePoleToTerminalChange}
          onLowVoltagePoleToTerminalMinimumChange={onLowVoltagePoleToTerminalMinimumChange}
          onHighVoltagePoleToPoleChange={onHighVoltagePoleToPoleChange}
          onHighVoltagePoleToTerminalChange={onHighVoltagePoleToTerminalChange}
          onHighVoltagePoleToTerminalMinimumChange={onHighVoltagePoleToTerminalMinimumChange}
        />
      )}
    </section>
  );
}