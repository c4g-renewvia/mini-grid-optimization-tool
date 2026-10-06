'use client';

import { useEffect, useState } from 'react';

import type {
  CostBreakdown,
  MiniGridEdge,
  MiniGridNode,
} from '@/types/minigrid';

const storageKey = 'mini-grid-tool-workspace-v1';

export interface PersistedMiniGridWorkspace {
  version: 1;
  miniGridNodes: MiniGridNode[];
  miniGridEdges: MiniGridEdge[];
  originalMiniGridNodes: MiniGridNode[];
  originalFileName: string | null;
  fileName: string | null;
  costBreakdown: CostBreakdown;
  solverOriginalCost: number;
  poleCost: number;
  lowVoltageCost: number;
  highVoltageCost: number;
  lowVoltagePoleToPoleMaxLength: number;
  lowVoltagePoleToTerminalMaxLength: number;
  lowVoltagePoleToTerminalMinLength: number;
  highVoltagePoleToPoleLengthConstraint: number;
  highVoltagePoleToTerminalMaxLength: number;
  highVoltagePoleToTerminalMinLength: number;
  selectedCount: number;
  allowDragTerminals: boolean;
  showEdgeLengths: boolean;
  selectedSolverName: string;
  paramValues: Record<string, unknown>;
  useExistingPoles: boolean;
}

function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === 'object' && value !== null && !Array.isArray(value);
}

function isFiniteNumber(value: unknown): value is number {
  return typeof value === 'number' && Number.isFinite(value);
}

function isMiniGridNode(value: unknown): value is MiniGridNode {
  return (
    isRecord(value) &&
    isFiniteNumber(value.index) &&
    typeof value.name === 'string' &&
    isFiniteNumber(value.lat) &&
    isFiniteNumber(value.lng) &&
    ['source', 'terminal', 'pole', 'info', 'pme'].includes(value.type as string)
  );
}

function isMiniGridEdge(value: unknown): value is MiniGridEdge {
  return (
    isRecord(value) &&
    isMiniGridNode(value.start) &&
    isMiniGridNode(value.end) &&
    isFiniteNumber(value.lengthMeters) &&
    (value.voltage === 'low' || value.voltage === 'high')
  );
}

function isCostBreakdown(value: unknown): value is CostBreakdown {
  return (
    isRecord(value) &&
    [
      'lowVoltageMeters',
      'highVoltageMeters',
      'totalMeters',
      'lowWireCost',
      'highWireCost',
      'wireCost',
      'poleCount',
      'poleCost',
      'pointCount',
      'grandTotal',
    ].every((key) => isFiniteNumber(value[key]))
  );
}

function isPersistedWorkspace(
  value: unknown
): value is PersistedMiniGridWorkspace {
  if (!isRecord(value) || value.version !== 1) return false;

  return (
    Array.isArray(value.miniGridNodes) &&
    value.miniGridNodes.every(isMiniGridNode) &&
    Array.isArray(value.miniGridEdges) &&
    value.miniGridEdges.every(isMiniGridEdge) &&
    Array.isArray(value.originalMiniGridNodes) &&
    value.originalMiniGridNodes.every(isMiniGridNode) &&
    (typeof value.originalFileName === 'string' ||
      value.originalFileName === null) &&
    (typeof value.fileName === 'string' || value.fileName === null) &&
    isCostBreakdown(value.costBreakdown) &&
    [
      'solverOriginalCost',
      'poleCost',
      'lowVoltageCost',
      'highVoltageCost',
      'lowVoltagePoleToPoleMaxLength',
      'lowVoltagePoleToTerminalMaxLength',
      'lowVoltagePoleToTerminalMinLength',
      'highVoltagePoleToPoleLengthConstraint',
      'highVoltagePoleToTerminalMaxLength',
      'highVoltagePoleToTerminalMinLength',
      'selectedCount',
    ].every((key) => isFiniteNumber(value[key])) &&
    typeof value.allowDragTerminals === 'boolean' &&
    typeof value.showEdgeLengths === 'boolean' &&
    typeof value.selectedSolverName === 'string' &&
    isRecord(value.paramValues) &&
    typeof value.useExistingPoles === 'boolean'
  );
}

interface UseMiniGridWorkspacePersistenceOptions {
  workspace: PersistedMiniGridWorkspace;
  onRestore: (_workspace: PersistedMiniGridWorkspace) => void;
  onError: (_message: string) => void;
}

export function useMiniGridWorkspacePersistence({
  workspace,
  onRestore,
  onError,
}: UseMiniGridWorkspacePersistenceOptions) {
  const [isRestored, setIsRestored] = useState(false);

  useEffect(() => {
    try {
      const storedWorkspace = window.localStorage.getItem(storageKey);
      if (!storedWorkspace) return;

      const parsedWorkspace: unknown = JSON.parse(storedWorkspace);
      if (!isPersistedWorkspace(parsedWorkspace)) {
        window.localStorage.removeItem(storageKey);
        onError('Saved workspace data was invalid and has been discarded.');
        return;
      }

      onRestore(parsedWorkspace);
    } catch (storageError) {
      console.error('Failed to restore saved workspace:', storageError);
      onError('Could not restore the saved workspace.');
    } finally {
      setIsRestored(true);
    }
  }, [onError, onRestore]);

  useEffect(() => {
    if (!isRestored) return;

    try {
      window.localStorage.setItem(storageKey, JSON.stringify(workspace));
    } catch (storageError) {
      console.error('Failed to save workspace locally:', storageError);
      onError('Could not save the workspace locally.');
    }
  }, [isRestored, onError, workspace]);

  return isRestored;
}
