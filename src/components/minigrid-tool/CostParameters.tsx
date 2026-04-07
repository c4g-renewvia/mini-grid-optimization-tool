'use client';

import React from 'react';

interface CostParametersProps {
  poleCost: number;
  lowVoltageCost: number;
  highVoltageCost: number;
  onPoleCostChange: (_value: number) => void;
  onLowVoltageCostChange: (_value: number) => void;
  onHighVoltageCostChange: (_value: number) => void;
  onRandomCosts: () => void;

  // Maximum Length Constraints
  lowVoltagePoleToPoleLengthConstraint: number;
  lowVoltagePoleToTerminalLengthConstraint: number;
  highVoltagePoleToPoleLengthConstraint: number;
  highVoltagePoleToTerminalLengthConstraint: number;

  // Minimum Length Constraints
  lowVoltagePoleToTerminalMinimumLength: number;
  highVoltagePoleToTerminalMinimumLength: number;

  // Handlers
  onLowVoltagePoleToPoleChange: (_value: number) => void;
  onLowVoltagePoleToHouseChange: (_value: number) => void; // Pole to Terminal (LV)
  onHighVoltagePoleToPoleChange: (_value: number) => void;
  onHighVoltagePoleToHouseChange: (_value: number) => void; // Pole to Terminal (HV)

  onLowVoltagePoleToTerminalMinimumChange: (_value: number) => void;
  onHighVoltagePoleToTerminalMinimumChange: (_value: number) => void;
}

export default function CostParameters({
                                         poleCost,
                                         lowVoltageCost,
                                         highVoltageCost,
                                         onPoleCostChange,
                                         onLowVoltageCostChange,
                                         onHighVoltageCostChange,
                                         onRandomCosts,

                                         // Max constraints
                                         lowVoltagePoleToPoleLengthConstraint,
                                         lowVoltagePoleToTerminalLengthConstraint,
                                         highVoltagePoleToPoleLengthConstraint,
                                         highVoltagePoleToTerminalLengthConstraint,

                                         // Min constraints
                                         lowVoltagePoleToTerminalMinimumLength,
                                         highVoltagePoleToTerminalMinimumLength,

                                         // Handlers
                                         onLowVoltagePoleToPoleChange,
                                         onLowVoltagePoleToHouseChange,
                                         onHighVoltagePoleToPoleChange,
                                         onHighVoltagePoleToHouseChange,

                                         onLowVoltagePoleToTerminalMinimumChange,
                                         onHighVoltagePoleToTerminalMinimumChange,
                                       }: CostParametersProps) {
  return (
    <div className='flex flex-col rounded-xl border border-zinc-200 bg-white p-7 backdrop-blur-sm dark:border-zinc-700 dark:bg-zinc-900/50'>
      <h3 className='mb-5 text-xl font-semibold text-zinc-900 dark:text-white'>
        Cost Parameters
      </h3>

      {/* Cost Inputs */}
      <div className='grid gap-6 sm:grid-cols-3'>
        <div>
          <label className='mb-2 block text-sm font-medium text-zinc-700 dark:text-zinc-300'>
            Pole Cost ($)
          </label>
          <input
            type='number'
            step='0.01'
            min='0'
            value={poleCost}
            onChange={(e) => onPoleCostChange(parseFloat(e.target.value) || 0)}
            className='w-full rounded-lg border border-zinc-200 bg-white px-4 py-2.5 text-sm text-zinc-900 focus:border-emerald-500 focus:ring-2 focus:ring-emerald-500/20 dark:border-zinc-700 dark:bg-zinc-900 dark:text-white'
          />
        </div>

        <div>
          <label className='mb-2 block text-sm font-medium text-zinc-700 dark:text-zinc-300'>
            Low Voltage ($/m)
          </label>
          <input
            type='number'
            step='0.01'
            min='0'
            value={lowVoltageCost}
            onChange={(e) =>
              onLowVoltageCostChange(parseFloat(e.target.value) || 0)
            }
            className='w-full rounded-lg border border-zinc-200 bg-white px-4 py-2.5 text-sm text-zinc-900 focus:border-emerald-500 focus:ring-2 focus:ring-emerald-500/20 dark:border-zinc-700 dark:bg-zinc-900 dark:text-white'
          />
        </div>

        <div>
          <label className='mb-2 block text-sm font-medium text-zinc-700 dark:text-zinc-300'>
            High Voltage ($/m)
          </label>
          <input
            type='number'
            step='0.01'
            min='0'
            value={highVoltageCost}
            onChange={(e) =>
              onHighVoltageCostChange(parseFloat(e.target.value) || 0)
            }
            className='w-full rounded-lg border border-zinc-200 bg-white px-4 py-2.5 text-sm text-zinc-900 focus:border-emerald-500 focus:ring-2 focus:ring-emerald-500/20 dark:border-zinc-700 dark:bg-zinc-900 dark:text-white'
          />
        </div>
      </div>

      {/* ====================== LENGTH CONSTRAINTS ====================== */}
      <div className='mt-8 space-y-8'>
        {/* Maximum Length Constraints */}
        <div className='rounded-xl border border-amber-200 bg-amber-50 p-6 dark:border-amber-500/30 dark:bg-amber-900/20'>
          <h4 className='mb-4 text-lg font-semibold text-amber-700 dark:text-amber-300'>
            Maximum Length Constraints (meters)
          </h4>
          <p className='mb-5 text-sm text-amber-600 dark:text-amber-400'>
            Maximum allowed distances between components.
          </p>

          <div className='grid gap-6 sm:grid-cols-2'>
            {/* Low Voltage Max */}
            <div className='space-y-4'>
              <div className='font-medium text-amber-700 dark:text-amber-300'>
                Low Voltage
              </div>
              <div>
                <label className='mb-1.5 block text-sm text-zinc-600 dark:text-zinc-400'>
                  Pole to Pole
                </label>
                <input
                  type='number'
                  step='1'
                  min='1'
                  value={lowVoltagePoleToPoleLengthConstraint}
                  onChange={(e) =>
                    onLowVoltagePoleToPoleChange(parseFloat(e.target.value) || 30)
                  }
                  className='w-full rounded-lg border border-zinc-200 bg-white px-4 py-2.5 text-sm text-zinc-900 focus:border-amber-500 focus:ring-2 focus:ring-amber-500/20 dark:border-zinc-700 dark:bg-zinc-900 dark:text-white'
                />
              </div>
              <div>
                <label className='mb-1.5 block text-sm text-zinc-600 dark:text-zinc-400'>
                  Pole to Terminal
                </label>
                <input
                  type='number'
                  step='1'
                  min='1'
                  value={lowVoltagePoleToTerminalLengthConstraint}
                  onChange={(e) =>
                    onLowVoltagePoleToHouseChange(parseFloat(e.target.value) || 20)
                  }
                  className='w-full rounded-lg border border-zinc-200 bg-white px-4 py-2.5 text-sm text-zinc-900 focus:border-amber-500 focus:ring-2 focus:ring-amber-500/20 dark:border-zinc-700 dark:bg-zinc-900 dark:text-white'
                />
              </div>
            </div>

            {/* High Voltage Max */}
            <div className='space-y-4'>
              <div className='font-medium text-amber-700 dark:text-amber-300'>
                High Voltage
              </div>
              <div>
                <label className='mb-1.5 block text-sm text-zinc-600 dark:text-zinc-400'>
                  Pole to Pole
                </label>
                <input
                  type='number'
                  step='1'
                  min='1'
                  value={highVoltagePoleToPoleLengthConstraint}
                  onChange={(e) =>
                    onHighVoltagePoleToPoleChange(parseFloat(e.target.value) || 50)
                  }
                  className='w-full rounded-lg border border-zinc-200 bg-white px-4 py-2.5 text-sm text-zinc-900 focus:border-amber-500 focus:ring-2 focus:ring-amber-500/20 dark:border-zinc-700 dark:bg-zinc-900 dark:text-white'
                />
              </div>
              <div>
                <label className='mb-1.5 block text-sm text-zinc-600 dark:text-zinc-400'>
                  Pole to Terminal
                </label>
                <input
                  type='number'
                  step='1'
                  min='1'
                  value={highVoltagePoleToTerminalLengthConstraint}
                  onChange={(e) =>
                    onHighVoltagePoleToHouseChange(parseFloat(e.target.value) || 20)
                  }
                  className='w-full rounded-lg border border-zinc-200 bg-white px-4 py-2.5 text-sm text-zinc-900 focus:border-amber-500 focus:ring-2 focus:ring-amber-500/20 dark:border-zinc-700 dark:bg-zinc-900 dark:text-white'
                />
              </div>
            </div>
          </div>
        </div>

        {/* Minimum Length Constraints */}
        <div className='rounded-xl border border-blue-200 bg-blue-50 p-6 dark:border-blue-500/30 dark:bg-blue-900/20'>
          <h4 className='mb-4 text-lg font-semibold text-blue-700 dark:text-blue-300'>
            Minimum Length Constraints (meters)
          </h4>
          <p className='mb-5 text-sm text-blue-600 dark:text-blue-400'>
            Minimum required distances (e.g., for safety or practical spacing).
          </p>

          <div className='grid gap-6 sm:grid-cols-2'>
            {/* Low Voltage Minimum */}
            <div className='space-y-4'>
              <div className='font-medium text-blue-700 dark:text-blue-300'>
                Low Voltage
              </div>
              <div>
                <label className='mb-1.5 block text-sm text-zinc-600 dark:text-zinc-400'>
                  Pole to Terminal Minimum
                </label>
                <input
                  type='number'
                  step='0.1'
                  min='0'
                  value={lowVoltagePoleToTerminalMinimumLength}
                  onChange={(e) =>
                    onLowVoltagePoleToTerminalMinimumChange(parseFloat(e.target.value) || 5)
                  }
                  className='w-full rounded-lg border border-zinc-200 bg-white px-4 py-2.5 text-sm text-zinc-900 focus:border-blue-500 focus:ring-2 focus:ring-blue-500/20 dark:border-zinc-700 dark:bg-zinc-900 dark:text-white'
                />
              </div>
            </div>

            {/* High Voltage Minimum */}
            <div className='space-y-4'>
              <div className='font-medium text-blue-700 dark:text-blue-300'>
                High Voltage
              </div>
              <div>
                <label className='mb-1.5 block text-sm text-zinc-600 dark:text-zinc-400'>
                  Pole to Terminal Minimum
                </label>
                <input
                  type='number'
                  step='0.1'
                  min='0'
                  value={highVoltagePoleToTerminalMinimumLength}
                  onChange={(e) =>
                    onHighVoltagePoleToTerminalMinimumChange(parseFloat(e.target.value) || 8)
                  }
                  className='w-full rounded-lg border border-zinc-200 bg-white px-4 py-2.5 text-sm text-zinc-900 focus:border-blue-500 focus:ring-2 focus:ring-blue-500/20 dark:border-zinc-700 dark:bg-zinc-900 dark:text-white'
                />
              </div>
            </div>
          </div>
        </div>
      </div>

      <button
        onClick={onRandomCosts}
        className='mt-6 text-sm text-emerald-600 transition-colors hover:text-emerald-700 hover:underline dark:text-emerald-400 dark:hover:text-emerald-300'
      >
        Use realistic random values
      </button>
    </div>
  );
}