'use client';

import React from 'react';

interface SolverParam {
  name: string;
  type?: 'integer' | 'float' | 'number';
  default: number;
  min?: number;
  max?: number;
  description?: string;
}

interface Solvers {
  name: string;
  params: SolverParam[];
}

interface SolverConfigurationProps {
  solvers: Solvers[];
  selectedSolverName: string;
  onSolverChange: (_solverName: string) => void;
  paramValues: Record<string, number>;
  onParamChange: (_paramName: string, _value: string) => void;
  useExistingPoles: boolean;
  onUseExistingPolesChange: (_use: boolean) => void;
  poleCount: number;
  onRunSolver: () => void;
  computing: boolean;
  calcError?: string | null;
}

export default function SolverConfiguration({
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
}: SolverConfigurationProps) {
  const selectedSolver = solvers.find((s) => s.name === selectedSolverName);

  return (
    <div className='flex flex-col rounded-xl border border-zinc-200 bg-white p-7 backdrop-blur-sm dark:border-zinc-700 dark:bg-zinc-900/50'>
      <h3 className='mb-5 text-xl font-semibold text-zinc-900 dark:text-white'>
        Solver Configuration
      </h3>

      {/* Solver Selection */}
      <div className='relative mb-6'>
        <label
          htmlFor='solver-select'
          className='mb-2 block text-sm font-medium text-zinc-700 dark:text-zinc-300'
        >
          Select Solver
        </label>

        <select
          id='solver-select'
          value={selectedSolverName}
          onChange={(e) => onSolverChange(e.target.value)}
          className='w-full appearance-none rounded-lg border border-zinc-200 bg-white px-4 py-3 text-base font-medium text-zinc-900 focus:border-purple-500 focus:ring-2 focus:ring-purple-500/30 dark:border-zinc-700 dark:bg-zinc-900 dark:text-zinc-100'
        >
          <option value='' disabled>
            Choose a solver...
          </option>
          {solvers.map((solver) => (
            <option key={solver.name} value={solver.name}>
              {solver.name}
            </option>
          ))}
        </select>
      </div>

      {/* Dynamic Parameters */}
      {selectedSolver &&
        selectedSolver.params &&
        selectedSolver.params.length > 0 && (
          <div className='mb-6 space-y-5 rounded-lg border border-zinc-200 bg-zinc-50 p-5 dark:border-zinc-700/50 dark:bg-zinc-900/40'>
            <h4 className='text-lg font-medium text-zinc-900 dark:text-zinc-200'>
              {selectedSolver.name} Parameters
            </h4>
            <div className='grid gap-5 sm:grid-cols-2'>
              {selectedSolver.params.map((param) => (
                <div key={param.name} className='space-y-1.5'>
                  <label
                    htmlFor={`param-${param.name}`}
                    className='block text-sm font-medium text-zinc-700 dark:text-zinc-300'
                  >
                    {param.name}
                    <span className='ml-2 text-xs text-zinc-500 dark:text-zinc-400'>
                      (default: {param.default})
                    </span>
                  </label>
                  <input
                    id={`param-${param.name}`}
                    type='number'
                    min={param.min}
                    max={param.max}
                    step={param.type === 'integer' ? 1 : 0.01}
                    value={paramValues[param.name] ?? param.default}
                    onChange={(e) => onParamChange(param.name, e.target.value)}
                    className='w-full rounded-md border border-zinc-200 bg-white px-3 py-2 text-sm text-zinc-900 focus:border-purple-500 focus:ring-2 focus:ring-purple-500/30 dark:border-zinc-700 dark:bg-zinc-900 dark:text-zinc-100'
                  />
                  {param.description && (
                    <p className='text-xs text-zinc-500 dark:text-zinc-400'>
                      {param.description}
                    </p>
                  )}
                </div>
              ))}
            </div>
          </div>
        )}

      {/* Use Existing Poles Checkbox */}
      {poleCount > 0 && (
        <div className='mb-6 flex items-center gap-3 rounded-lg border border-zinc-200 bg-zinc-50 p-4 dark:border-zinc-700/50 dark:bg-zinc-900/40'>
          <input
            type='checkbox'
            id='use-poles'
            checked={useExistingPoles}
            onChange={(e) => onUseExistingPolesChange(e.target.checked)}
            className='h-5 w-5 rounded border-zinc-300 bg-white text-purple-600 focus:ring-purple-500 dark:border-zinc-600 dark:bg-zinc-800'
          />
          <label
            htmlFor='use-poles'
            className='cursor-pointer text-sm font-medium text-zinc-700 dark:text-zinc-300'
          >
            Use existing poles in calculation ({poleCount} poles detected)
          </label>
        </div>
      )}

      {/* Run Solver Button */}
      <div className='mt-auto pt-4'>
        <button
          onClick={onRunSolver}
          disabled={computing || !selectedSolverName}
          className='w-full rounded-xl bg-gradient-to-r from-purple-600 to-indigo-600 px-8 py-5 text-lg font-bold text-white shadow-xl shadow-purple-900/40 transition-all hover:scale-[1.02] hover:from-purple-500 hover:to-indigo-500 disabled:cursor-not-allowed disabled:opacity-50'
        >
          {computing ? 'Solving...' : 'Run Solver'}
        </button>

        <p className='mt-4 text-center text-xs text-zinc-500 dark:text-zinc-400'>
          Beta • Low Voltage Only • Limited to Single Power Source
        </p>
      </div>

      {calcError && (
        <p className='mt-4 text-center text-sm font-medium text-red-600 dark:text-red-400'>
          {calcError}
        </p>
      )}
    </div>
  );
}
