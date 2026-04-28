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
  lowVoltagePoleToPoleMaxLength: number;
  lowVoltagePoleToTerminalMaxLength: number;
  highVoltagePoleToPoleLengthConstraint: number;
  highVoltagePoleToTerminalMaxLength: number;

  // Minimum Length Constraints
  lowVoltagePoleToTerminalMinLength: number;
  highVoltagePoleToTerminalMinLength: number;

  // Handlers
  onLowVoltagePoleToPoleChange: (_value: number) => void;
  onLowVoltagePoleToTerminalChange: (_value: number) => void; // Pole to Terminal (LV)
  onHighVoltagePoleToPoleChange: (_value: number) => void;
  onHighVoltagePoleToTerminalChange: (_value: number) => void; // Pole to Terminal (HV)

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
                                         lowVoltagePoleToPoleMaxLength,
                                         lowVoltagePoleToTerminalMaxLength,
                                         highVoltagePoleToPoleLengthConstraint,
                                         highVoltagePoleToTerminalMaxLength,

                                         // Min constraints
                                         lowVoltagePoleToTerminalMinLength,
                                         highVoltagePoleToTerminalMinLength,

                                         // Handlers
                                         onLowVoltagePoleToPoleChange,
                                         onLowVoltagePoleToTerminalChange,
                                         onHighVoltagePoleToPoleChange,
                                         onHighVoltagePoleToTerminalChange,

                                         onLowVoltagePoleToTerminalMinimumChange,
                                         onHighVoltagePoleToTerminalMinimumChange,
                                       }: CostParametersProps) {
  return (
    <div className='flex flex-col rounded-xl border border-zinc-200 bg-white p-7 backdrop-blur-sm dark:border-zinc-700 dark:bg-zinc-900/50'>
      <h3 className='mb-5 text-xl font-semibold text-zinc-900 dark:text-white'>
        Cost Parameters <br />
        (Currently Low Voltage Only)
      </h3>

      {/* Cost Inputs */}
      <div className='grid gap-6 sm:grid-cols-3'>
        {/* Pole Cost */}
        <div>
          <label className='mb-2 block text-sm font-medium text-zinc-700 dark:text-zinc-300'>
            Pole Cost
          </label>
          <div className='relative'>
            <div className='pointer-events-none absolute inset-y-0 left-0 flex items-center pl-4 font-medium text-zinc-500 dark:text-zinc-400'>
              $
            </div>
            <input
              type='number'
              min='0'
              value={poleCost}
              onChange={(e) =>
                onPoleCostChange(parseFloat(e.target.value) || 0)
              }
              className='w-full rounded-lg border border-zinc-200 bg-white py-2.5 pr-4 pl-10 text-sm text-zinc-900 focus:border-emerald-500 focus:ring-2 focus:ring-emerald-500/20 dark:border-zinc-700 dark:bg-zinc-900 dark:text-white'
            />
          </div>
        </div>

        {/* Low Voltage */}
        <div>
          <label className='mb-2 block text-sm font-medium text-zinc-700 dark:text-zinc-300'>
            Low Voltage
          </label>
          <div className='flex overflow-hidden rounded-lg border border-zinc-200 bg-white dark:border-zinc-700 dark:bg-zinc-900'>
            <div className='pointer-events-none flex items-center border-r border-zinc-200 bg-zinc-50 px-3 font-medium text-zinc-500 dark:border-zinc-700 dark:bg-zinc-800 dark:text-zinc-400'>
              $
            </div>
            <input
              type='number'
              min='0'
              value={lowVoltageCost}
              onChange={(e) =>
                onLowVoltageCostChange(parseFloat(e.target.value) || 0)
              }
              className='min-w-0 flex-1 border-0 bg-transparent px-3 py-2.5 text-sm text-zinc-900 focus:ring-0 dark:text-white'
            />
            <div className='flex items-center border-l border-zinc-200 bg-zinc-50 px-2.5 text-sm font-medium text-zinc-500 dark:border-zinc-700 dark:bg-zinc-800 dark:text-zinc-400'>
              /m
            </div>
          </div>
        </div>

        {/* High Voltage */}
        <div>
          <label className='mb-2 block text-sm font-medium text-zinc-700 dark:text-zinc-300'>
            High Voltage
          </label>
          <div className='flex overflow-hidden rounded-lg border border-zinc-200 bg-white dark:border-zinc-700 dark:bg-zinc-900'>
            <div className='pointer-events-none flex items-center border-r border-zinc-200 bg-zinc-50 px-3 font-medium text-zinc-500 dark:border-zinc-700 dark:bg-zinc-800 dark:text-zinc-400'>
              $
            </div>
            <input
              type='number'
              min='0'
              value={highVoltageCost}
              onChange={(e) =>
                onHighVoltageCostChange(parseFloat(e.target.value) || 0)
              }
              disabled={true}
              className='min-w-0 flex-1 border-0 bg-transparent px-3 py-2.5 text-sm text-zinc-900 focus:ring-0 dark:text-white'
            />
            <div className='flex items-center border-l border-zinc-200 bg-zinc-50 px-2.5 text-sm font-medium text-zinc-500 dark:border-zinc-700 dark:bg-zinc-800 dark:text-zinc-400'>
              /m
            </div>
          </div>
        </div>
      </div>

      {/* ====================== LENGTH CONSTRAINTS ====================== */}
      <div className='mt-6 space-y-6'>
        {/* Maximum Length Constraints */}
        <div className='rounded-xl border border-amber-200 bg-amber-50 p-5 dark:border-amber-500/30 dark:bg-amber-900/20'>
          <h4 className='mb-3 text-lg font-semibold text-amber-700 dark:text-amber-300'>
            Max Length Constraints (m)
          </h4>

          <div className='grid gap-5 sm:grid-cols-2'>
            {/* Low Voltage Max */}
            <div className='space-y-3'>
              <div className='text-sm font-medium text-amber-700 dark:text-amber-300'>
                Low Voltage
              </div>
              <div>
                <label className='mb-1 block text-xs text-zinc-600 dark:text-zinc-400'>
                  Pole to Pole
                </label>
                <input
                  type='number'
                  min='1'
                  value={lowVoltagePoleToPoleMaxLength}
                  onChange={(e) =>
                    onLowVoltagePoleToPoleChange(
                      parseFloat(e.target.value) || 30
                    )
                  }
                  className='w-full rounded-lg border border-zinc-200 bg-white px-4 py-2.5 text-sm text-zinc-900 focus:border-amber-500 focus:ring-2 focus:ring-amber-500/20 dark:border-zinc-700 dark:bg-zinc-900 dark:text-white'
                />
              </div>
              <div>
                <label className='mb-1 block text-xs text-zinc-600 dark:text-zinc-400'>
                  Pole to Terminal
                </label>
                <input
                  type='number'
                  min='1'
                  value={lowVoltagePoleToTerminalMaxLength}
                  onChange={(e) =>
                    onLowVoltagePoleToTerminalChange(
                      parseFloat(e.target.value) || 20
                    )
                  }
                  className='w-full rounded-lg border border-zinc-200 bg-white px-4 py-2.5 text-sm text-zinc-900 focus:border-amber-500 focus:ring-2 focus:ring-amber-500/20 dark:border-zinc-700 dark:bg-zinc-900 dark:text-white'
                />
              </div>
            </div>

            {/* High Voltage Max */}
            <div className='space-y-3'>
              <div className='text-sm font-medium text-amber-700 dark:text-amber-300'>
                High Voltage
              </div>
              <div>
                <label className='mb-1 block text-xs text-zinc-600 dark:text-zinc-400'>
                  Pole to Pole
                </label>
                <input
                  type='number'
                  min='1'
                  value={highVoltagePoleToPoleLengthConstraint}
                  onChange={(e) =>
                    onHighVoltagePoleToPoleChange(
                      parseFloat(e.target.value) || 50
                    )
                  }
                  disabled={true}
                  className='w-full rounded-lg border border-zinc-200 bg-white px-4 py-2.5 text-sm text-zinc-900 focus:border-amber-500 focus:ring-2 focus:ring-amber-500/20 dark:border-zinc-700 dark:bg-zinc-900 dark:text-white'
                />
              </div>
              <div>
                <label className='mb-1 block text-xs text-zinc-600 dark:text-zinc-400'>
                  Pole to Terminal
                </label>
                <input
                  type='number'
                  min='1'
                  value={highVoltagePoleToTerminalMaxLength}
                  onChange={(e) =>
                    onHighVoltagePoleToTerminalChange(
                      parseFloat(e.target.value) || 20
                    )
                  }
                  disabled={true}
                  className='w-full rounded-lg border border-zinc-200 bg-white px-4 py-2.5 text-sm text-zinc-900 focus:border-amber-500 focus:ring-2 focus:ring-amber-500/20 dark:border-zinc-700 dark:bg-zinc-900 dark:text-white'
                />
              </div>
            </div>
          </div>
        </div>

        {/* Minimum Length Constraints */}
        <div className='rounded-xl border border-blue-200 bg-blue-50 p-5 dark:border-blue-500/30 dark:bg-blue-900/20'>
          <h4 className='mb-3 text-lg font-semibold text-blue-700 dark:text-blue-300'>
            Min Length Constraints (m)
          </h4>

          <div className='grid gap-5 sm:grid-cols-2'>
            {/* Low Voltage Min */}
            <div className='space-y-3'>
              <div className='text-sm font-medium text-blue-700 dark:text-blue-300'>
                Low Voltage
              </div>
              <div>
                <label className='mb-1 block text-xs text-zinc-600 dark:text-zinc-400'>
                  Pole to Terminal
                </label>
                <input
                  type='number'
                  min='0'
                  value={lowVoltagePoleToTerminalMinLength}
                  onChange={(e) =>
                    onLowVoltagePoleToTerminalMinimumChange(
                      parseFloat(e.target.value)
                    )
                  }
                  className='w-full rounded-lg border border-zinc-200 bg-white px-4 py-2.5 text-sm text-zinc-900 focus:border-blue-500 focus:ring-2 focus:ring-blue-500/20 dark:border-zinc-700 dark:bg-zinc-900 dark:text-white'
                />
              </div>
            </div>

            {/* High Voltage Min */}
            <div className='space-y-3'>
              <div className='text-sm font-medium text-blue-700 dark:text-blue-300'>
                High Voltage
              </div>
              <div>
                <label className='mb-1 block text-xs text-zinc-600 dark:text-zinc-400'>
                  Pole to Terminal
                </label>
                <input
                  type='number'
                  min='0'
                  value={highVoltagePoleToTerminalMinLength}
                  onChange={(e) =>
                    onHighVoltagePoleToTerminalMinimumChange(
                      parseFloat(e.target.value)
                    )
                  }
                  disabled={true}
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